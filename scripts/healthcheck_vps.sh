#!/usr/bin/env bash
# BLK-SEC-05 — Observabilidade mínima da VPS de produção (alertas via bot Telegram).
#
# Instalado em /opt/motor-monitoring/healthcheck_vps.sh e agendado via cron do root
# (cadências e runbook em docs/infra_producao.md, seção "Alertas automáticos").
#
# Subcomandos:
#   containers  containers esperados up/healthy + edge HTTPS do dashboard (cron */5)
#   host        disco e memória do host (cron horário)
#   authelia    resumo diário de falhas de login (cron 1x/dia)
#   coleta      domingo pós-coleta: resumo do relatório GymScraping ou alerta de falha
#   agregadores idade da última partição de snapshot de cada agregador (cron semanal, BLK-MA-21)
#   crescimento idade do artefato da camada de crescimento municipal (cron trimestral, DEC-052)
#   mercado     coerência da camada de mercado com o cadastro de concorrentes (cron semanal, DEC-059)
#   pins        idade da última PROMOÇÃO dos pins de M&A + quantos são desenháveis (cron semanal)
#   banco       backup (dump do dia, última execução, cópia semanal, off-box), expurgo das sessões
#               e saúde interna do Postgres: tamanho, conexões, transação parada, lock (cron diário)
#   test        envia mensagem de teste ao chat de ops
#
# Anti-spam: alerta só na transição OK->FAIL, lembrete a cada REMIND_SECS enquanto
# durar a falha, e aviso de recuperação em FAIL->OK (estado em MONITOR_STATE_DIR).
# Nível AVISO (🟡), abaixo do FAIL: a mesma máquina de estados, com lembrete a cada
# AVISO_REMIND_SECS — para risco conhecido e aceito, que não pode virar vermelho diário.
#
# Segredos: token do bot (API_TELEGRAM_TOKEN) e chat de ops (MONITOR_TELEGRAM_CHAT_ID)
# são lidos do .env de produção em runtime. NUNCA logar/echoar esses valores.
set -euo pipefail

ENV_FILE="${MONITOR_ENV_FILE:-/opt/motor-expansao/app/.env}"
STATE_DIR="${MONITOR_STATE_DIR:-/var/lib/motor-monitoring}"
LOG_FILE="${MONITOR_LOG_FILE:-/var/log/motor-monitoring/healthcheck.log}"
REMIND_SECS="${MONITOR_REMIND_SECS:-3600}"
# Lembrete do nível AVISO: semanal. O caso de origem é a cópia off-box do backup do banco,
# desligada por decisão pendente — repetir todo dia ensinaria o grupo a não ler o canal.
AVISO_REMIND_SECS="${MONITOR_AVISO_REMIND_SECS:-604800}"
DISK_PCT_MAX="${MONITOR_DISK_PCT_MAX:-80}"
MEM_AVAIL_PCT_MIN="${MONITOR_MEM_AVAIL_PCT_MIN:-10}"
EDGE_URL="${MONITOR_EDGE_URL:-https://piloto.ultra-expansao.tech}"
# Cookie de sessão FALSO da sonda `auth` (ver `check_auth`). O NOME tem de ser o de produção
# (`COOKIE_SESSAO` em web/server/acesso.py; travado por teste): com outro nome, o `/api/verify`
# volta a ver "sem cookie" e responde 401 sem consultar o banco. O VALOR não importa — não
# existe sessão com ele.
COOKIE_SONDA_AUTH="__Host-motor_sessao=sonda-do-healthcheck"
GYM_REPORT_DIR="${MONITOR_GYM_REPORT_DIR:-/opt/gymscraping-infra}"
GYM_LOG_HINT="/var/log/gymscraping/weekly_latest.log"
# Série de snapshots de concorrentes (BLK-MA-21). O cron SEMANAL dos agregadores (terça 02:00
# UTC) é o único produtor de `fonte=wellhub` / `fonte=totalpass`; se ele parar, nada mais
# acusa — o score continua saindo, só que sobre uma série congelada, e o S4 lê a estagnação
# como sinal.
SNAPSHOTS_DIR="${MONITOR_SNAPSHOTS_DIR:-/opt/motor-expansao/data/staging/snapshots_concorrentes}"
# 9 dias, sob a cadência SEMANAL (terça 02:00 UTC) com o check na quinta 12:00 UTC: a rodada
# da própria semana dá 3 dias de idade (a régua sai da SEGUNDA da semana ISO, não do instante
# da coleta) e uma rodada perdida dá 10. A faixa que separa os dois casos é [3, 9] inteira —
# 9 é o TETO dela, escolhido por ser o mais tolerante a uma rodada que escorregue dentro da
# semana, não por unicidade. Com o `45` herdado da premissa mensal seriam até 6 rodadas
# perdidas antes do primeiro FAIL.
AGREGADOR_MAX_DIAS="${MONITOR_AGREGADOR_MAX_DIAS:-9}"
AGREGADORES=(wellhub totalpass)
# Camada de crescimento municipal (DEC-052): cadencia TRIMESTRAL (dia 5 de
# fev/mai/ago/nov). 100 = um trimestre (~92 dias) + folga para retentativa manual;
# com o check SEMANAL (quinta), uma rodada perdida dispara na 1a quinta depois de
# a idade passar de 100 — ~1-2 semanas apos o cron falhar, nao um mes. A regua e'
# o MTIME do parquet publicado — aqui ele e' confiavel porque o unico produtor e' o
# rename atomico do proprio job (nao ha rsync/migracao rejuvenescendo a folha, o
# defeito que tirou o mtime da regua dos agregadores). Arquivo que NUNCA existiu
# tambem e' FAIL: e' o estado real enquanto o repasse de insumos nao acontecer.
# O default 100 tem PARIDADE com `crescimento/constantes.py` (teste trava os dois).
CRESCIMENTO_MAX_DIAS="${MONITOR_CRESCIMENTO_MAX_DIAS:-100}"
CRESCIMENTO_PARQUET="${MONITOR_CRESCIMENTO_PARQUET:-/opt/motor-expansao/data/staging/crescimento_municipal.parquet}"
# Camada de mercado/residual (DEC-059): cron SEMANAL, dentro da janela de domingo.
#
# 9 dias pelo mesmo raciocínio do limiar dos agregadores: a rodada da própria semana
# dá até 7 dias de idade no pior caso (check na quinta, rodada no domingo anterior =
# 4 dias; um domingo perdido = 11). A faixa que separa é [7, 10] e o 9 fica no meio,
# com paridade de valor com `AGREGADOR_MAX_DIAS` de propósito — dois limiares
# semanais diferentes seriam duas coisas para manter.
MERCADO_MAX_DIAS="${MONITOR_MERCADO_MAX_DIAS:-9}"
MERCADO_LOG="${MONITOR_MERCADO_LOG:-/var/log/motor-snapshots/regen_mercado_latest.log}"
# O container que já monta os dois parquets `:ro` — é dentro dele que a régua de
# CONTEÚDO é medida (o host não tem Python com pyarrow).
MERCADO_CONTAINER="${MONITOR_MERCADO_CONTAINER:-motor_expansao_web}"
# Pins de vulnerabilidade M&A (passo 4.5 do lote de domingo). Aqui o MTIME é HONESTO, e a
# diferença em relação ao `mercado` é a razão de este monitor existir: o arquivo só é tocado
# pelo `mv` da PROMOÇÃO. Quando a guarda de desenhabilidade (ou a de coerência de chave) barra
# a safra nova, nada é escrito — e o arquivo ENVELHECE, que é exatamente o sinal que faltou
# entre 30/08 e 17/09, três semanas com os pins congelados e ninguém sabendo.
# Ressalva declarada, a mesma do `crescimento`: `rsync`/restore do volume rejuvenesce mtime.
PINS_MAX_DIAS="${MONITOR_PINS_MAX_DIAS:-9}"
PINS_PARQUET="${MONITOR_PINS_PARQUET:-/opt/motor-expansao/data/staging/vulnerabilidade_ma_nomeadas.parquet}"
# Piso de pins DESENHÁVEIS, em paridade com a guarda do `run_weekly_90.sh`: um artefato
# promovido antes da guarda existir (incidente de 30/08: 42.862 linhas, todas SEM coordenada)
# ficaria eternamente verde num monitor que só olhasse idade.
PINS_MIN_DESENHAVEIS="${MONITOR_PINS_MIN_DESENHAVEIS:-100}"
PINS_CONTAINER="${MONITOR_PINS_CONTAINER:-motor_expansao_web}"
CONTAINERS=(
    motor_expansao_caddy
    motor_expansao_authelia
    motor_expansao_api
    motor_expansao_telegram_bot
    # Tileserver do basemap self-host (BLK-BASEMAP-01, stack em /opt/openmaptiles-infra).
    # Vale monitorar apesar de nao servir o edge: se ele cair, a geracao de PDF NAO quebra --
    # `_fetch_basemap` engole a falha e o relatorio sai SEM ruas, em silencio. Sem este alerta,
    # a degradacao so apareceria quando alguem olhasse um PDF.
    motor_expansao_tileserver
    # Piloto web (`Dockerfile.web`, servico `web` do compose): o app de producao desde a
    # DEC-022 (o container motor_expansao_streamlit saiu da vigilancia no corte).
    motor_expansao_web
    # Instancia ARGENTINA (Bloco E / BLK-INTL-08, servico `web_ar` do docker-compose.ar.yml,
    # MESMA VPS): entra na vigilancia junto com a subida. EDGE_URL segue escalar (so o host
    # BR) -- debito consciente ate o BLK-INTL-09.
    motor_expansao_web_ar
    # Postgres/PostGIS. ATENCAO A QUEM RECEBER ESTE ALERTA DE MADRUGADA: a gravidade MUDA
    # com o corte do P19, e o texto antigo aqui dizia so' a metade tranquilizadora.
    #
    #   ANTES do corte: o `web` NAO cai junto. O piloto foi desenhado para servir sem banco
    #   (leitura de parquet nao passa por ele) e o healthcheck do container deliberadamente
    #   nao o consulta. Banco fora = degradacao: so' o RBAC comeca a negar.
    #
    #   DEPOIS do corte (`MOTOR_AUTENTICACAO_PROPRIA` preenchida): e' INDISPONIBILIDADE
    #   TOTAL do piloto BR. A sessao vive em TABELA, entao sem banco o `/api/verify` responde
    #   503, o Caddy nega tudo que nao for 2xx e NINGUEM entra -- inclusive quem ja' estava
    #   dentro. E o login tambem nao funciona, porque depende do mesmo banco.
    #
    # Conferir o estado: `grep '^MOTOR_AUTENTICACAO_PROPRIA=' /opt/motor-expansao/app/.env`.
    #
    # Total: 8. Os dois acima entraram em paralelo, em branches diferentes, e cada lado
    # escreveu "Total: 7" contando apenas o proprio acrescimo -- o numero certo so' aparece
    # aqui, depois do merge.
    motor_expansao_postgres
)
# Servico de rotas (Valhalla, DEC-074; stack em /opt/valhalla-infra). NAO entra no array
# acima de proposito, e a diferenca para o tileserver e' de natureza, nao de importancia:
# o tileserver e' parte fixa da producao (todo PDF passa por ele), enquanto o Valhalla e'
# OPCIONAL por construcao -- sem `MOTOR_ROTAS_URL` no .env, a opcao "10 min de carro" some da
# tela e nada chama o servico. Vigiar o container incondicionalmente daria FAIL eterno numa
# VPS onde a stack ainda nao foi instalada, e alerta que nunca para vira ruido que esconde o
# alerta real. A chave e' a MESMA que liga a funcao: com a env preenchida, container ausente
# e' falha de verdade (a opcao aparece e cada clique devolve 503); com ela vazia, ausente e' o
# estado correto. Ver `check_containers`.
ROTAS_CONTAINER="${MONITOR_ROTAS_CONTAINER:-motor_expansao_valhalla}"
# Banco (Postgres/PostGIS) — subcomando `banco`, DIÁRIO. O `containers` só sabe se o container
# está de pé; o backup, o expurgo e a saúde de dentro do banco ficam com este.
#
# Os DEFAULTS são os caminhos do runbook (cabeçalho de `scripts/cron/run_backup_banco.sh` e de
# `run_expurgo_sessoes.sh`, com teste travando a paridade). A PRODUÇÃO não segue o runbook:
# desde 17/10/2026 os dois crons rodam no crontab do usuário `deploy`, com dumps em
# /home/deploy/backups/banco e logs em /home/deploy/logs. O root aponta os três caminhos na
# própria linha do crontab — às 12:00 UTC (09:00 BRT), pelo motivo do limiar logo abaixo:
#   0 12 * * * MONITOR_BANCO_BACKUP_DIR=/home/deploy/backups/banco MONITOR_BANCO_BACKUP_LOG=/home/deploy/logs/backup_banco.log MONITOR_BANCO_EXPURGO_LOG=/home/deploy/logs/expurgo_sessoes.log /opt/motor-monitoring/healthcheck_vps.sh banco
BANCO_BACKUP_DIR="${MONITOR_BANCO_BACKUP_DIR:-/opt/motor-expansao/backups/banco}"
BANCO_BACKUP_LOG="${MONITOR_BANCO_BACKUP_LOG:-/var/log/motor-monitoring/backup_banco.log}"
BANCO_EXPURGO_LOG="${MONITOR_BANCO_EXPURGO_LOG:-/var/log/motor-monitoring/expurgo_sessoes.log}"
BANCO_CONTAINER="${MONITOR_BANCO_CONTAINER:-motor_expansao_postgres}"
# 26 h. O backup roda às 05:10 UTC e o check, às 12:00 UTC: o dump do dia tem ~7 h na hora do
# check, e um dia sem backup deixa o anterior com ~31 h. A régua só pega o dia perdido NO PRÓPRIO
# DIA enquanto o check rodar mais de 2 h (26 - 24) depois do backup — por isso 12:00, e não logo
# depois das 05:10. O expurgo (04:40 UTC) segue a mesma conta.
BANCO_DUMP_MAX_HORAS="${MONITOR_BANCO_DUMP_MAX_HORAS:-26}"
BANCO_EXPURGO_MAX_HORAS="${MONITOR_BANCO_EXPURGO_MAX_HORAS:-26}"
# A cópia semanal nasce no backup de DOMINGO (hardlink do diário). 8 dias = a semana + a folga
# do horário: um domingo perdido aparece na segunda.
BANCO_SEMANAL_MAX_DIAS="${MONITOR_BANCO_SEMANAL_MAX_DIAS:-8}"
# Execução sem a linha de fim, começada há menos que isto, está EM ANDAMENTO e não falhou: o
# veredito fica para a próxima rodada (só acontece em rodada manual no meio do backup).
BANCO_EM_ANDAMENTO_MIN="${MONITOR_BANCO_EM_ANDAMENTO_MIN:-60}"
# Saúde interna, medida por `docker exec` no próprio container do banco.
#   tamanho: guarda de crescimento FORA DO ESPERADO, não de capacidade (o disco é do `host`). O
#     limiar fica muito acima do banco de hoje (20 usuários e o seed do RBAC); suba-o quando
#     chegar carga legítima (o ETL da fase 5).
#   conexões: % do `max_connections`. No teto, o Postgres RECUSA conexão nova — inclusive a do
#     pool do piloto.
#   transação parada ("idle in transaction"): segura lock e impede o VACUUM. O pool do piloto
#     faz transações de milissegundos; 10 min é sessão esquecida (um psql manual com BEGIN).
#   lock: o pool do piloto desiste em 1 s (`lock_timeout`); esperar minutos é manutenção ou
#     sessão manual presa atrás de outra.
BANCO_TAMANHO_MAX_MB="${MONITOR_BANCO_TAMANHO_MAX_MB:-5120}"
BANCO_CONEXOES_PCT_MAX="${MONITOR_BANCO_CONEXOES_PCT_MAX:-80}"
BANCO_OCIOSA_MAX_MIN="${MONITOR_BANCO_OCIOSA_MAX_MIN:-10}"
BANCO_LOCK_MAX_MIN="${MONITOR_BANCO_LOCK_MAX_MIN:-5}"
BANCO_TIMEOUT_S="${MONITOR_BANCO_TIMEOUT_S:-60}"
# As frases que os dois wrappers ESCREVEM no log (`echo`), com teste travando a paridade. Se um
# wrapper mudar a frase, este monitor passa a dizer "nenhuma execução registrada": falha alta,
# nunca verde falso. A exceção é o off-box — lá a frase AUSENTE quer dizer "ligada" —, e por
# isso o monitor procura DUAS (o aviso e o fim "somente local").
BANCO_BACKUP_INICIO="backup do banco - inicio"
BANCO_BACKUP_FIM="backup do banco - fim"
BANCO_OFFBOX_DESLIGADA="copia off-box DESLIGADA"
BANCO_SO_LOCAL="fim (somente local)"
BANCO_EXPURGO_INICIO="expurgo da origem das sessoes - inicio"
BANCO_EXPURGO_FIM="expurgo da origem das sessoes - fim"

mkdir -p "$STATE_DIR" "$(dirname "$LOG_FILE")"

log() { printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" >>"$LOG_FILE"; }

get_env_var() { # get_env_var NOME — lê valor do .env sem exportar nem logar
    grep -E "^$1=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' || true
}

send_telegram() { # send_telegram "mensagem"
    local token chat
    token="$(get_env_var API_TELEGRAM_TOKEN)"
    chat="$(get_env_var MONITOR_TELEGRAM_CHAT_ID)"
    if [[ -z "$token" || -z "$chat" ]]; then
        log "ERRO: API_TELEGRAM_TOKEN/MONITOR_TELEGRAM_CHAT_ID ausentes em $ENV_FILE"
        return 1
    fi
    if ! curl -fsS -m 15 "https://api.telegram.org/bot${token}/sendMessage" \
        --data-urlencode "chat_id=${chat}" \
        --data-urlencode "text=$1" >/dev/null; then
        log "ERRO: falha ao enviar alerta ao Telegram (rede/API)"
        return 1
    fi
}

report() { # report <chave> <OK|FAIL|AVISO> <mensagem-de-falha>
    # AVISO é o nível ABAIXO do FAIL: a mesma máquina de estados (transição, lembrete,
    # recuperação), em amarelo e com lembrete a cada AVISO_REMIND_SECS. Uma chave é de um nível
    # só — a cópia off-box desligada, por exemplo, nunca vira FAIL.
    local key="$1" status="$2" msg="$3"
    local sf="$STATE_DIR/$key.state" now prev last icone lembrete rotulo
    now=$(date +%s)
    prev="OK" last=0
    if [[ -f "$sf" ]]; then
        read -r prev last <"$sf" || { prev="OK"; last=0; }
    fi
    if [[ "$status" == "AVISO" ]]; then
        icone="🟡" lembrete="$AVISO_REMIND_SECS" rotulo="(lembrete)"
    else
        icone="🔴" lembrete="$REMIND_SECS" rotulo="(ainda em falha)"
    fi
    if [[ "$status" != "OK" ]]; then
        log "$status $key: $msg"
        if [[ "$prev" != "$status" ]]; then
            send_telegram "$icone [VPS Ultra] $msg" || true
            echo "$status $now" >"$sf"
        elif ((now - last >= lembrete)); then
            send_telegram "$icone [VPS Ultra] $rotulo $msg" || true
            echo "$status $now" >"$sf"
        fi
    else
        if [[ "$prev" != "OK" ]]; then
            send_telegram "🟢 [VPS Ultra] Recuperado: $key" || true
            log "RECOVER $key"
        fi
        echo "OK $now" >"$sf"
    fi
}

check_containers() {
    local c st hs code
    local alvos=("${CONTAINERS[@]}")
    # So' vigia o Valhalla quando a funcao esta' LIGADA (ver o comentario de ROTAS_CONTAINER).
    if [[ -n "$(get_env_var MOTOR_ROTAS_URL)" ]]; then
        alvos+=("$ROTAS_CONTAINER")
    fi
    for c in "${alvos[@]}"; do
        st=$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null || echo "ausente")
        hs=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' "$c" 2>/dev/null || echo "n/a")
        if [[ "$st" != "running" || "$hs" == "unhealthy" ]]; then
            report "container_$c" FAIL "Container $c com problema: status=$st, health=$hs"
        else
            report "container_$c" OK ""
        fi
    done
    # Edge externo: 2xx/3xx (redirect do Authelia) ou 401 = vivo.
    code=$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$EDGE_URL" || echo "000")
    if [[ "$code" =~ ^(2|3|401) ]]; then
        report edge OK ""
    else
        report edge FAIL "Dashboard fora do ar: $EDGE_URL respondeu HTTP $code"
    fi

    check_auth
}

# AUTENTICACAO, e este check existe porque o `edge` (em `check_containers`) DEIXA DE MEDI-LA no
# corte do P19. A raiz do `EDGE_URL` esta' hoje atras do `forward_auth`, entao o codigo dela
# reflete a autenticacao. Depois do corte o matcher `@protegido` cobre so' `/api/*`: a raiz
# passa a servir o SPA com 200 SEMPRE, com ou sem ninguem conseguindo entrar -- o `edge`
# ficaria verde para sempre, que e' pior que nao existir.
#
# `/api/me` com um cookie de sessao INVALIDO tem de ser 401. Se vier 200, a API esta' aberta
# (a borda deixou passar e, depois do corte, o portao de sessao tambem); se vier 503, o banco
# nao respondeu e ninguem entra (ver o comentario do `postgres` acima). ANTES do corte tambem
# vale: o Authelia responde 302 ou 401, e os dois sao aceitos.
#
# POR QUE O COOKIE (achado de 24/10/2026). A sonda ia SEM cookie, e assim o ramo do 503 nunca
# disparava: sem token, o `/api/verify` responde 401 ANTES de abrir conexao
# (`sessoes.validar("")` sai com `None`), entao banco fora passava como "auth OK" -- inclusive
# depois do corte, quando banco fora e' o piloto BR inteiro fora. Com um token qualquer, ele
# faz a MESMA consulta que faz para uma pessoa: token que nao existe = 401; banco que nao
# responde = 503. O token nao abre nada nem escreve nada: e' um SELECT que nao acha linha.
# Antes do corte, nada muda: o Authelia ignora este cookie (o dele e' outro), e o `auth` nao
# acusa banco fora -- ali, banco fora e' degradacao, e quem acusa e' o `containers`.
check_auth() {
    local code
    code=$(curl -s -o /dev/null -m 15 -w '%{http_code}' -H "Cookie: ${COOKIE_SONDA_AUTH}" \
        "$EDGE_URL/api/me" || echo "000")
    case "$code" in
        401|30*) report auth OK "" ;;
        200)     report auth FAIL "GRAVE: $EDGE_URL/api/me respondeu 200 a uma sonda sem sessão válida — a API está aberta" ;;
        503)     report auth FAIL "$EDGE_URL/api/me respondeu 503 a uma sonda com cookie inválido: o banco não respondeu (fora do ar ou saturado). Com o P19 ligado, ninguém entra" ;;
        *)       report auth FAIL "$EDGE_URL/api/me respondeu HTTP $code (esperado 401)" ;;
    esac
}

check_host() {
    local pct avail total availpct
    pct=$(df --output=pcent / | tail -1 | tr -dc '0-9')
    if ((pct >= DISK_PCT_MAX)); then
        report disk FAIL "Disco da VPS em ${pct}% de uso (limiar ${DISK_PCT_MAX}%)"
    else
        report disk OK ""
    fi
    avail=$(awk '/MemAvailable/{print $2}' /proc/meminfo)
    total=$(awk '/MemTotal/{print $2}' /proc/meminfo)
    availpct=$((avail * 100 / total))
    if ((availpct <= MEM_AVAIL_PCT_MIN)); then
        report mem FAIL "Memória disponível em ${availpct}% (limiar ${MEM_AVAIL_PCT_MIN}%)"
    else
        report mem OK ""
    fi
}

check_authelia() {
    # Resumo diário; só notifica se houve falha de login nas últimas 24h.
    local n
    n=$(docker logs --since 24h motor_expansao_authelia 2>&1 |
        grep -ci "unsuccessful.*authentication" || true)
    log "authelia: $n falha(s) de login em 24h"
    if ((n > 0)); then
        send_telegram "🟡 [VPS Ultra] Authelia: ${n} tentativa(s) de login malsucedida(s) nas últimas 24h" || true
    fi
}

check_coleta() {
    # Roda domingo após a janela da coleta (cron 06:00 UTC). O relatório mais
    # novo em GYM_REPORT_DIR deve ser datado de HOJE; senão, a coleta falhou.
    local latest today total deltas falhas msg
    today=$(date +%F)
    latest=$(ls -t "$GYM_REPORT_DIR"/relatorio_crescimento_*.txt 2>/dev/null | head -1 || true)
    if [[ -z "$latest" || "$latest" != *"$today"* ]]; then
        report coleta FAIL "Coleta semanal de concorrentes NÃO gerou relatório hoje ($today). Último: ${latest:-nenhum}. Ver $GYM_LOG_HINT"
        return
    fi
    report coleta OK ""
    total=$(sed -n '2p' "$latest")
    deltas=$(awk '$4 ~ /^[+-][0-9]+$/ && $4 != "+0"' "$latest")
    falhas=$(sed -n '/NAO atualizadas/,$p' "$latest")
    msg="📊 [VPS Ultra] Coleta semanal concluída — ${total}
Mudanças por rede:
${deltas:-nenhuma}"
    [[ -n "$falhas" ]] && msg="${msg}

${falhas}"
    send_telegram "$msg" || true
}

# Epoch (UTC) da SEGUNDA-FEIRA da semana ISO `AAAA-SS`, ou vazio se a chave não casar.
#
# `date -d` não parseia data ISO-week em nenhuma versão do coreutils, então a conversão é feita à
# mão pela definição da ISO-8601: **4 de janeiro cai sempre na semana 1**. A segunda da semana 1 é
# `04/01 - (dia_da_semana - 1)`, e a da semana W está `(W-1)` semanas adiante.
epoch_da_semana_iso() {
    local chave="$1" ano semana jan4 dow seg1
    [[ "$chave" =~ ^([0-9]{4})-([0-9]{2})$ ]] || return 1
    ano="${BASH_REMATCH[1]}"
    semana="$((10#${BASH_REMATCH[2]}))"   # `10#` : `08`/`09` não podem ser lidos como octal
    ((semana >= 1 && semana <= 53)) || return 1
    jan4=$(date -u -d "${ano}-01-04" +%s 2>/dev/null) || return 1
    dow=$(date -u -d "${ano}-01-04" +%u 2>/dev/null) || return 1
    seg1=$((jan4 - (dow - 1) * 86400))
    echo $((seg1 + (semana - 1) * 604800))
}

check_agregadores() {
    # Idade da última partição de cada agregador na série de snapshots (BLK-MA-21).
    #
    # Por que por FONTE e não pela série inteira: o cron de DOMINGO escreve `fonte=unidades`
    # toda semana, então a série nunca parece velha — olhar só a partição mais recente
    # esconderia, para sempre, um cron dos agregadores que morreu. Cada agregador tem chave de
    # estado própria, para que a falha de um não silencie o alerta do outro.
    #
    # A idade sai da CHAVE `semana=AAAA-SS`, não do mtime do diretório `fonte=`
    # [emenda de 2026-08-25 à DEC-039]. O mtime mentia, e mentia justamente onde dói: o passo 2
    # OBRIGATÓRIO da ordem de aplicação roda `--migrar-layout`, que CRIA a folha `fonte=` com
    # mtime de agora. Medido sobre cópia da partição viva: dado de 2026-08-05 (20 dias) reportado
    # como `0d`, e com o limiar herdado de 45 dias o FAIL atrasaria ~20 dias. A distância é arbitrária para
    # qualquer `rsync`/restore do volume, que também rejuvenesce mtime.
    #
    # A régua nova pode ADIANTAR o alerta em até ~1 dia (a segunda da semana ISO é anterior ao
    # instante da coleta), nunca atrasá-lo — que é a direção segura para um monitor. Quando a
    # chave não for parseável, cai no mtime e DIZ que caiu.
    local f alvo idade_seg idade_dias particao referencia regua
    for f in "${AGREGADORES[@]}"; do
        # Ordena pela CHAVE `semana=` (lexicográfica == cronológica, graças ao zero-padding),
        # nunca por mtime: é o mtime que este bloco deixou de confiar.
        particao=$(find "$SNAPSHOTS_DIR" -mindepth 2 -maxdepth 2 -type d -name "fonte=$f" \
            -printf '%p\n' 2>/dev/null \
            | sed -n 's#.*/semana=\([0-9]\{4\}-[0-9]\{2\}\)/fonte=.*#\1#p' | sort | tail -1 || true)
        alvo=$(find "$SNAPSHOTS_DIR" -mindepth 2 -maxdepth 2 -type d -name "fonte=$f" \
            -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2- || true)
        if [[ -z "$alvo" ]]; then
            report "agregador_$f" FAIL "Snapshot do agregador ${f} NUNCA foi fotografado (nenhuma partição em ${SNAPSHOTS_DIR}). O cron semanal dos agregadores foi agendado?"
            continue
        fi
        referencia=$(epoch_da_semana_iso "$particao" 2>/dev/null || true)
        if [[ -n "$referencia" ]]; then
            regua="semana="
        else
            regua="mtime (fallback: chave semana= ilegível)"
            referencia=$(stat -c %Y "$alvo")
            particao="${particao:-desconhecida}"
        fi
        idade_seg=$(($(date +%s) - referencia))
        idade_dias=$((idade_seg / 86400))
        if ((idade_dias > AGREGADOR_MAX_DIAS)); then
            report "agregador_$f" FAIL "Snapshot do agregador ${f} com ${idade_dias} dias (limiar ${AGREGADOR_MAX_DIAS}, régua ${regua}). Última partição: ${particao}. Ver /var/log/motor-snapshots/snapshot_agregadores_latest.log"
        else
            log "agregadores: ${f} OK (${idade_dias}d por ${regua}, ${particao})"
            report "agregador_$f" OK ""
        fi
    done
}

check_crescimento() {
    # Idade do artefato da camada de crescimento municipal (DEC-052). Sem este
    # check, um cron trimestral morto seria invisivel: a camada e' OPCIONAL por
    # desenho — o passo 4 degrada sem erro e sem log, e /api/health continua 200.
    local idade_seg idade_dias
    if [[ ! -f "$CRESCIMENTO_PARQUET" ]]; then
        report crescimento FAIL "Camada de crescimento municipal NUNCA publicada (${CRESCIMENTO_PARQUET} ausente). O repasse de insumos e o cron trimestral foram instalados?"
        return
    fi
    idade_seg=$(($(date +%s) - $(stat -c %Y "$CRESCIMENTO_PARQUET")))
    idade_dias=$((idade_seg / 86400))
    if ((idade_dias > CRESCIMENTO_MAX_DIAS)); then
        report crescimento FAIL "Camada de crescimento municipal com ${idade_dias} dias (limiar ${CRESCIMENTO_MAX_DIAS}). O cron trimestral rodou? Ver /var/log/motor-snapshots/atualizacao_crescimento_latest.log"
    else
        log "crescimento: OK (${idade_dias}d)"
        report crescimento OK ""
    fi
}

check_mercado() {
    # Coerência da camada de mercado com o cadastro de concorrentes (DEC-059).
    #
    # A régua é de CONTEÚDO, e não de mtime, porque **o mtime MENTE aqui**: a etapa 4
    # do lote semanal reescreve `hexagonos_mercado_mapeado.parquet` toda semana, então
    # o arquivo parece sempre fresco — inclusive no regime antigo, em que as colunas
    # espaciais de 1 km ficavam estagnadas por nove domingos seguidos (DEC-048: 60,46%
    # dos hexágonos se moveram quando alguém finalmente rodou o Bloco 3 à mão). Um
    # monitor por data teria ficado VERDE o tempo todo.
    #
    # O que se compara é o carimbo de auditoria `n_redes_mapeadas` (gravado pelo
    # `calcular_colunas_mercado` no momento em que a camada foi gerada) contra o
    # `rede.nunique()` do cadastro de concorrentes que está no disco AGORA. Divergiu:
    # o cadastro andou e a camada não — que é exatamente a dívida que o cron fecha.
    local saida carimbado atual idade_dias
    if [[ ! -f "$MERCADO_LOG" ]]; then
        report mercado FAIL "Regeneração semanal da camada de mercado NUNCA rodou (${MERCADO_LOG} ausente). O wrapper run_regen_mercado.sh foi instalado no run_weekly_90.sh?"
        return
    fi
    idade_dias=$((($(date +%s) - $(stat -c %Y "$MERCADO_LOG")) / 86400))
    if ((idade_dias > MERCADO_MAX_DIAS)); then
        report mercado FAIL "Regeneração da camada de mercado com ${idade_dias} dias sem rodar (limiar ${MERCADO_MAX_DIAS}). Ver ${MERCADO_LOG}"
        return
    fi
    # Medido DENTRO do container, que já monta os dois parquets `:ro`. Não medir é
    # FAIL: um monitor cego não pode ser lido como "está tudo bem".
    saida=$(docker exec "$MERCADO_CONTAINER" python -c '
import pandas as pd
m = pd.read_parquet("/app/data/staging/hexagonos_mercado_mapeado.parquet", columns=["n_redes_mapeadas"])
c = pd.read_parquet("/app/data/staging/concorrentes_mapeados.parquet", columns=["rede", "status_registro"])
print(int(m["n_redes_mapeadas"].dropna().iloc[0]), int(c.loc[c["status_registro"] == "valido", "rede"].nunique()))
' 2>/dev/null) || {
        report mercado FAIL "Não foi possível medir a camada de mercado (docker exec em ${MERCADO_CONTAINER} falhou). Monitor cego conta como falha."
        return
    }
    carimbado=$(echo "$saida" | awk '{print $1}')
    atual=$(echo "$saida" | awk '{print $2}')
    if [[ "$carimbado" != "$atual" ]]; then
        report mercado FAIL "Camada de mercado DESSINCRONIZADA do cadastro: carimbo n_redes_mapeadas=${carimbado}, cadastro atual=${atual} redes. A coleta andou e a oferta espacial de 1 km não. Ver ${MERCADO_LOG}"
    else
        log "mercado: OK (${carimbado} redes, regen há ${idade_dias}d)"
        report mercado OK ""
    fi
}

check_pins() {
    # Idade e conteúdo dos pins de M&A do mapa (passo 4.5 do lote de domingo).
    #
    # Por que este monitor existe: a guarda de desenhabilidade do wrapper faz o CERTO ao barrar
    # artefato ruim, mas o efeito dela é INVISÍVEL — de 30/08 a 17/09 ela preservou os pins bons
    # por três semanas seguidas enquanto o mapa servia dado cada vez mais velho, e nada alertou.
    # Uma guarda que só bloqueia, sem relógio, troca "pin errado" por "pin velho em silêncio".
    #
    # A régua de IDADE é o mtime, e aqui ele é confiável — ao contrário do `mercado`, em que o
    # arquivo é reescrito toda semana e o mtime mente: este só é tocado pelo `mv` da promoção.
    local idade_dias desenhaveis
    if [[ ! -f "$PINS_PARQUET" ]]; then
        report pins FAIL "Pins de M&A NUNCA foram publicados (${PINS_PARQUET} ausente). O passo 4.5 do lote de domingo rodou alguma vez?"
        return
    fi
    idade_dias=$((($(date +%s) - $(stat -c %Y "$PINS_PARQUET")) / 86400))
    if ((idade_dias > PINS_MAX_DIAS)); then
        report pins FAIL "Pins de M&A sem promoção há ${idade_dias} dias (limiar ${PINS_MAX_DIAS}). A guarda do passo 4.5 está barrando a safra nova, ou o lote de domingo não rodou. Ver /var/log/gymscraping/weekly_latest.log"
        return
    fi
    # Medido DENTRO do container, que já monta o parquet (o host não tem Python com pyarrow).
    # Não conseguir medir é FAIL, pelo mesmo motivo do `mercado`: monitor cego não pode ser lido
    # como "está tudo bem".
    desenhaveis=$(docker exec "$PINS_CONTAINER" python -c '
import pandas as pd
d = pd.read_parquet("/app/data/staging/vulnerabilidade_ma_nomeadas.parquet", columns=["lat"])
print(int(d["lat"].notna().sum()))
' 2>/dev/null) || {
        report pins FAIL "Não foi possível medir os pins de M&A (docker exec em ${PINS_CONTAINER} falhou). Monitor cego conta como falha."
        return
    }
    if ((desenhaveis < PINS_MIN_DESENHAVEIS)); then
        report pins FAIL "Pins de M&A publicados com apenas ${desenhaveis} academias desenháveis (piso ${PINS_MIN_DESENHAVEIS}). O mapa está servindo artefato sem coordenada — foi o incidente de 2026-08-30."
        return
    fi
    log "pins: OK (${desenhaveis} desenháveis, promoção há ${idade_dias}d)"
    report pins OK ""
}

# ── Banco (Postgres/PostGIS) ────────────────────────────────────────────────────────────

# Linhas da ÚLTIMA execução registrada no log de um wrapper de cron: do último marcador de
# início até o fim do arquivo. Execução de `--simular` NÃO conta (o expurgo aceita a flag, e ela
# não escreve nada): a coleta para nela sem zerar o bloco real anterior, então uma simulação
# manual depois do cron não esconde o resultado dele.
ultima_execucao() { # ultima_execucao <log> <marcador-de-inicio>
    awk -v m="$2" '
        index($0, m) { if (index($0, "--simular")) { dentro = 0 } else { dentro = 1; bloco = "" } }
        dentro { bloco = bloco $0 "\n" }
        END { printf "%s", bloco }' "$1"
}

# Início de um bloco: o carimbo `[AAAA-MM-DDTHH:MM:SSZ]` (o `date -u +%FT%TZ` dos wrappers) da
# 1ª linha; sem carimbo legível, o mtime do log — e a régua devolvida diz que caiu nele.
inicio_do_bloco() { # inicio_do_bloco "<bloco>" <log> -> "<epoch> <carimbo|mtime>"
    local primeira="${1%%$'\n'*}" e
    if [[ "$primeira" =~ \[([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)\] ]]; then
        e=$(date -u -d "${BASH_REMATCH[1]}" +%s 2>/dev/null || true)
        if [[ -n "$e" ]]; then
            echo "$e carimbo"
            return 0
        fi
    fi
    echo "$(stat -c %Y "$2" 2>/dev/null || echo 0) mtime"
}

# Último "!! " (o prefixo de erro e aviso dos wrappers) de um bloco. O texto vai para o Telegram,
# então credencial em URL (`esquema://usuario:senha@`) e `NOME=valor` saem mascarados: os
# wrappers não ecoam segredo hoje, e a máscara é para o dia em que um deles passar a ecoar.
ultimo_aviso() { # ultimo_aviso "<bloco>"
    printf '%s\n' "$1" | grep '^!! ' | tail -1 |
        sed -E 's#://[^/@[:space:]]+@#://***@#g; s/([A-Za-z_][A-Za-z0-9_]*)=[^[:space:]]+/\1=***/g' || true
}

# Dump mais novo de um diretório do backup, pelo CARIMBO do nome (`<banco>_AAAAMMDDTHHMMSSZ.dump`,
# o `date -u` do início do `pg_dump`) e não pelo mtime: `rsync`/restore do diretório rejuvenesce
# mtime — a lição do monitor dos agregadores — e um backup de uma semana atrás pareceria de hoje.
# Nome fora do padrão cai no mtime, e a régua diz que caiu. `*.dump` não casa o `.dump.parcial`
# de um backup em andamento ou morto no meio. Imprime "<epoch> <carimbo|mtime> <caminho>", ou
# nada se não houver dump.
dump_mais_novo() { # dump_mais_novo <diretório>
    local f c e m melhor="" melhor_c="" velho="" velho_m=0
    for f in "$1"/*.dump; do
        [[ -f "$f" ]] || continue
        if [[ "${f##*/}" =~ _([0-9]{8})T([0-9]{6})Z\.dump$ ]]; then
            c="${BASH_REMATCH[1]}${BASH_REMATCH[2]}"
            if [[ -z "$melhor_c" || "$c" > "$melhor_c" ]]; then
                melhor_c="$c" melhor="$f"
            fi
        else
            m=$(stat -c %Y "$f" 2>/dev/null || echo 0)
            if ((m > velho_m)); then
                velho_m="$m" velho="$f"
            fi
        fi
    done
    if [[ -n "$melhor" ]]; then
        e=$(date -u -d "${melhor_c:0:4}-${melhor_c:4:2}-${melhor_c:6:2} ${melhor_c:8:2}:${melhor_c:10:2}:${melhor_c:12:2}" +%s 2>/dev/null || true)
        if [[ -n "$e" ]]; then
            echo "$e carimbo $melhor"
            return 0
        fi
        velho="$melhor" velho_m=$(stat -c %Y "$melhor" 2>/dev/null || echo 0)
    fi
    if [[ -n "$velho" ]]; then
        echo "$velho_m mtime $velho"
    fi
    return 0
}

# Por que um dump NÃO serve para restaurar, ou nada se ele estiver íntegro. O
# `run_backup_banco.sh` só renomeia o `.parcial` depois de um `pg_restore --list` de ponta a
# ponta, e grava o sha256 LOGO DEPOIS: conferir o sha256 aqui amarra o arquivo de hoje àquela
# validação, sem o container e sem repetir o I/O do `pg_restore`.
motivo_dump_ruim() { # motivo_dump_ruim <arquivo>
    local f="$1" nome="${1##*/}" esperado atual
    if [[ ! -s "$f" ]]; then
        echo "${nome} está VAZIO (0 byte)"
    elif [[ "$(head -c 5 -- "$f" 2>/dev/null | tr -d '\000')" != "PGDMP" ]]; then
        echo "${nome} não tem a assinatura PGDMP do formato -Fc"
    elif [[ ! -f "$f.sha256" ]]; then
        echo "${nome} está sem o ${nome}.sha256, então a integridade não tem como ser provada"
    else
        esperado=$(awk 'NR == 1 { print $1 }' "$f.sha256" 2>/dev/null || true)
        atual=$(sha256sum -- "$f" 2>/dev/null | awk '{ print $1 }' || true)
        if [[ -z "$atual" || "$atual" != "$esperado" ]]; then
            echo "${nome} está CORROMPIDO: o sha256 não bate com o ${nome}.sha256 gravado na hora do dump"
        fi
    fi
    return 0
}

banco_dumps() {
    # Dump mais novo do DIÁRIO (idade, tamanho, assinatura, sha256) e da cópia SEMANAL.
    local agora linha epoch regua f motivo idade_s
    agora=$(date +%s)
    linha=$(dump_mais_novo "$BANCO_BACKUP_DIR/diario")
    if [[ -z "$linha" ]]; then
        report banco_dump FAIL "Backup do banco: NENHUM dump em ${BANCO_BACKUP_DIR}/diario. O cron do backup (05:10 UTC) foi instalado? Na produção ele roda na conta deploy: confira MONITOR_BANCO_BACKUP_DIR."
    else
        read -r epoch regua f <<<"$linha"
        [[ "$regua" == "mtime" ]] && regua="mtime (fallback: nome sem carimbo)"
        idade_s=$((agora - epoch))
        motivo=$(motivo_dump_ruim "$f")
        if ((idade_s > BANCO_DUMP_MAX_HORAS * 3600)); then
            report banco_dump FAIL "Backup do banco PARADO: o dump mais novo tem $((idade_s / 3600)) h (limiar ${BANCO_DUMP_MAX_HORAS} h, régua ${regua}): ${f##*/}. O cron das 05:10 UTC rodou? Ver ${BANCO_BACKUP_LOG}"
        elif [[ -n "$motivo" ]]; then
            report banco_dump FAIL "Backup do banco INUTILIZÁVEL: ${motivo}. Ver ${BANCO_BACKUP_LOG}"
        else
            log "banco: dump OK (${f##*/}, $((idade_s / 3600)) h pela régua ${regua}, $(stat -c %s "$f") bytes, sha256 confere)"
            report banco_dump OK ""
        fi
    fi

    linha=$(dump_mais_novo "$BANCO_BACKUP_DIR/semanal")
    if [[ -z "$linha" ]]; then
        report banco_semanal FAIL "Backup do banco sem NENHUMA cópia semanal em ${BANCO_BACKUP_DIR}/semanal: a cobertura de 4 semanas não existe. Ela nasce no backup de domingo; numa instalação nova, este alerta dura até o primeiro domingo."
        return
    fi
    read -r epoch regua f <<<"$linha"
    [[ "$regua" == "mtime" ]] && regua="mtime (fallback: nome sem carimbo)"
    idade_s=$((agora - epoch))
    motivo=$(motivo_dump_ruim "$f")
    # Dias E horas na mensagem: no caso típico (o domingo perdido, acusado no check de segunda) a
    # cópia tem 8 dias e ~7 h, e "8 dias (limiar 8)" leria como se o limiar não tivesse passado.
    if ((idade_s > BANCO_SEMANAL_MAX_DIAS * 86400)); then
        report banco_semanal FAIL "Cópia semanal do backup do banco com $((idade_s / 86400)) dias e $((idade_s % 86400 / 3600)) h (limiar ${BANCO_SEMANAL_MAX_DIAS} dias, régua ${regua}): ${f##*/}. O backup de domingo falhou? Ver ${BANCO_BACKUP_LOG}"
    elif [[ -n "$motivo" ]]; then
        report banco_semanal FAIL "Cópia semanal do backup do banco INUTILIZÁVEL: ${motivo}."
    else
        report banco_semanal OK ""
    fi
}

banco_backup_log() {
    # A ÚLTIMA execução do backup terminou? E com ou sem a cópia off-box? O dump de ontem ainda
    # parece novo na manhã seguinte: sem ler o log, o backup que falhou hoje só apareceria amanhã.
    local bloco inicio regua quando aviso
    if [[ ! -f "$BANCO_BACKUP_LOG" ]]; then
        report banco_backup FAIL "Log do backup do banco ausente (${BANCO_BACKUP_LOG}): sem ele não há como saber se a última execução terminou. Na produção o backup roda na conta deploy: confira MONITOR_BANCO_BACKUP_LOG."
        return
    fi
    bloco=$(ultima_execucao "$BANCO_BACKUP_LOG" "$BANCO_BACKUP_INICIO")
    if [[ -z "$bloco" ]]; then
        report banco_backup FAIL "Log do backup do banco sem NENHUMA execução registrada (${BANCO_BACKUP_LOG}). O cron das 05:10 UTC escreve nele?"
        return
    fi
    if [[ "$bloco" == *"$BANCO_BACKUP_FIM"* ]]; then
        report banco_backup OK ""
        # Off-box só se lê numa execução que TERMINOU: numa que morreu no meio, não se sabe.
        if [[ "$bloco" == *"$BANCO_OFFBOX_DESLIGADA"* || "$bloco" == *"$BANCO_SO_LOCAL"* ]]; then
            report banco_offbox AVISO "Backup do banco SÓ LOCAL: a cópia off-box (restic) está desligada, e o dump vive no mesmo disco que deveria proteger. Ligar exige BACKUP_RESTIC_* no .env (decisão pendente)."
        else
            report banco_offbox OK ""
        fi
        return
    fi
    read -r inicio regua <<<"$(inicio_do_bloco "$bloco" "$BANCO_BACKUP_LOG")"
    if (($(date +%s) - inicio < BANCO_EM_ANDAMENTO_MIN * 60)); then
        log "banco: backup em andamento (começou há menos de ${BANCO_EM_ANDAMENTO_MIN} min); o veredito fica para a próxima rodada"
        return
    fi
    quando=$(date -u -d "@${inicio}" +'%d/%m %H:%M' 2>/dev/null || echo "?")
    aviso=$(ultimo_aviso "$bloco")
    report banco_backup FAIL "A última execução do backup do banco (início ${quando} UTC, pela régua ${regua}) NÃO terminou. Último aviso do script: ${aviso:-nenhum}. Ver ${BANCO_BACKUP_LOG}"
}

banco_expurgo() {
    # O expurgo da origem das sessões (retenção de 90 dias, P15) rodou e TERMINOU? Ele roda às
    # 04:40, antes do backup das 05:10: parado, o dump do dia passa a guardar IP vencido.
    local bloco inicio regua idade_s aviso
    if [[ ! -f "$BANCO_EXPURGO_LOG" ]]; then
        report banco_expurgo FAIL "Log do expurgo das sessões ausente (${BANCO_EXPURGO_LOG}). O cron do expurgo (04:40 UTC) foi instalado? Na produção ele roda na conta deploy: confira MONITOR_BANCO_EXPURGO_LOG."
        return
    fi
    bloco=$(ultima_execucao "$BANCO_EXPURGO_LOG" "$BANCO_EXPURGO_INICIO")
    if [[ -z "$bloco" ]]; then
        report banco_expurgo FAIL "Log do expurgo das sessões sem NENHUMA execução real (${BANCO_EXPURGO_LOG}); rodada com --simular não conta."
        return
    fi
    read -r inicio regua <<<"$(inicio_do_bloco "$bloco" "$BANCO_EXPURGO_LOG")"
    idade_s=$(($(date +%s) - inicio))
    if [[ "$bloco" != *"$BANCO_EXPURGO_FIM"* ]]; then
        if ((idade_s < BANCO_EM_ANDAMENTO_MIN * 60)); then
            log "banco: expurgo em andamento (começou há menos de ${BANCO_EM_ANDAMENTO_MIN} min); o veredito fica para a próxima rodada"
            return
        fi
        aviso=$(ultimo_aviso "$bloco")
        report banco_expurgo FAIL "A última execução do expurgo das sessões (há $((idade_s / 3600)) h, pela régua ${regua}) NÃO terminou: a retenção de 90 dias da origem das sessões (P15) não foi aplicada, e o backup das 05:10 pode guardar o que deveria ter saído. Último aviso do script: ${aviso:-nenhum}. Ver ${BANCO_EXPURGO_LOG}"
        return
    fi
    if ((idade_s > BANCO_EXPURGO_MAX_HORAS * 3600)); then
        report banco_expurgo FAIL "Expurgo das sessões sem rodar há $((idade_s / 3600)) h (limiar ${BANCO_EXPURGO_MAX_HORAS} h, régua ${regua}): a retenção de 90 dias da origem das sessões (P15) deixa de ser cumprida. O cron das 04:40 UTC rodou? Ver ${BANCO_EXPURGO_LOG}"
    else
        report banco_expurgo OK ""
    fi
}

banco_medidas() {
    # Tamanho, conexões, transação parada e espera por lock, medidos DENTRO do container.
    #
    # As credenciais são as do PRÓPRIO container, expandidas lá dentro: o `sh -c` vai entre aspas
    # SIMPLES, então `$POSTGRES_*` chega literal ao container e nunca passa pelo argv nem pela
    # saída do host. A senha viaja em `PGPASSWORD`, no ambiente do psql (não no argv), e só pesa
    # se o `pg_hba` local pedir senha — a imagem oficial confia no socket local. O SQL entra pela
    # entrada padrão e devolve só NÚMEROS; o stderr é descartado e a saída é validada contra o
    # formato antes de qualquer uso, então nada do que vier do container é ecoado no alerta.
    local saida bytes conexoes max_conexoes ociosas idade_ociosa locks idade_lock pct
    local formato='^[0-9]+( [0-9]+){6}$'
    # shellcheck disable=SC2016
    saida=$(timeout "$BANCO_TIMEOUT_S" docker exec -i "$BANCO_CONTAINER" sh -c \
        'PGPASSWORD="$POSTGRES_PASSWORD" PGCONNECT_TIMEOUT=10 exec psql -X -q -A -t -F " " -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
        2>/dev/null <<'SQL'
SET statement_timeout = '15s';
SELECT pg_database_size(current_database()),
       (SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'client backend'),
       current_setting('max_connections')::int,
       (SELECT count(*) FROM pg_stat_activity WHERE state LIKE 'idle in transaction%'),
       (SELECT greatest(0, coalesce(max(extract(epoch FROM clock_timestamp() - state_change)), 0))::bigint
          FROM pg_stat_activity WHERE state LIKE 'idle in transaction%'),
       (SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock'),
       (SELECT greatest(0, coalesce(max(extract(epoch FROM clock_timestamp() - query_start)), 0))::bigint
          FROM pg_stat_activity WHERE wait_event_type = 'Lock');
SQL
    ) || saida=""
    if ! [[ "$saida" =~ $formato ]]; then
        report banco_medicao FAIL "Não foi possível medir o banco (docker exec em ${BANCO_CONTAINER} falhou, passou de ${BANCO_TIMEOUT_S} s ou devolveu algo fora do formato). Monitor cego conta como falha."
        return
    fi
    report banco_medicao OK ""
    read -r bytes conexoes max_conexoes ociosas idade_ociosa locks idade_lock <<<"$saida"
    if ((bytes > BANCO_TAMANHO_MAX_MB * 1048576)); then
        report banco_tamanho FAIL "Banco com $((bytes / 1048576)) MB (limiar ${BANCO_TAMANHO_MAX_MB} MB): crescimento fora do esperado. Ver quais tabelas cresceram antes de subir o limiar."
    else
        report banco_tamanho OK ""
    fi
    pct=$((max_conexoes > 0 ? conexoes * 100 / max_conexoes : 100))
    if ((pct >= BANCO_CONEXOES_PCT_MAX)); then
        report banco_conexoes FAIL "Banco com ${conexoes} conexões abertas de ${max_conexoes} permitidas (${pct}%, limiar ${BANCO_CONEXOES_PCT_MAX}%). No teto, o Postgres recusa conexão nova, inclusive a do piloto."
    else
        report banco_conexoes OK ""
    fi
    if ((idade_ociosa > BANCO_OCIOSA_MAX_MIN * 60)); then
        report banco_transacoes FAIL "Banco com transação aberta e PARADA (idle in transaction) há $((idade_ociosa / 60)) min (limiar ${BANCO_OCIOSA_MAX_MIN} min; ${ociosas} sessão(ões) nesse estado). Ela segura lock e impede o VACUUM. Encontre-a em pg_stat_activity (pg_terminate_backend encerra)."
    else
        report banco_transacoes OK ""
    fi
    if ((idade_lock > BANCO_LOCK_MAX_MIN * 60)); then
        report banco_locks FAIL "Banco com ${locks} sessão(ões) esperando lock, a mais antiga há $((idade_lock / 60)) min (limiar ${BANCO_LOCK_MAX_MIN} min). Quem bloqueia: pg_blocking_pids(pid), em pg_stat_activity."
    else
        report banco_locks OK ""
    fi
    log "banco: medido ($((bytes / 1048576)) MB; conexões ${conexoes}/${max_conexoes}; em transação parada ${ociosas}, a mais antiga há ${idade_ociosa} s; esperando lock ${locks}, a mais antiga há ${idade_lock} s)"
}

check_banco() {
    # O que o `containers` NÃO vê: o container pode estar `healthy` (o `pg_isready` responde) com
    # o backup parado há dias, o expurgo da retenção de 90 dias sem rodar ou uma sessão esquecida
    # segurando lock. Até aqui essas falhas existiam só como linha de log — os dois wrappers saem
    # com `exit 1` e mais nada.
    #
    # Cada aspecto tem chave de estado PRÓPRIA, no molde dos agregadores: um defeito não silencia
    # o alerta do outro, e a recuperação diz exatamente o que voltou. Nada daqui lê segredo do
    # banco no `.env`: o único segredo que este script toca continua sendo o token do bot, no
    # envio do alerta.
    banco_dumps
    banco_backup_log
    banco_expurgo
    banco_medidas
}

case "${1:-}" in
containers) check_containers ;;
host) check_host ;;
authelia) check_authelia ;;
coleta) check_coleta ;;
agregadores) check_agregadores ;;
crescimento) check_crescimento ;;
mercado) check_mercado ;;
pins) check_pins ;;
banco) check_banco ;;
test)
    send_telegram "✅ [VPS Ultra] Monitoramento ativo — mensagem de teste"
    echo "mensagem de teste enviada"
    ;;
*)
    echo "uso: $0 {containers|host|authelia|coleta|agregadores|crescimento|mercado|pins|banco|test}" >&2
    exit 2
    ;;
esac
