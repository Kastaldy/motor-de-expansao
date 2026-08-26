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
#   agregadores idade da última partição de snapshot de cada agregador (cron mensal, BLK-MA-21)
#   test        envia mensagem de teste ao chat de ops
#
# Anti-spam: alerta só na transição OK->FAIL, lembrete a cada REMIND_SECS enquanto
# durar a falha, e aviso de recuperação em FAIL->OK (estado em MONITOR_STATE_DIR).
#
# Segredos: token do bot (API_TELEGRAM_TOKEN) e chat de ops (MONITOR_TELEGRAM_CHAT_ID)
# são lidos do .env de produção em runtime. NUNCA logar/echoar esses valores.
set -euo pipefail

ENV_FILE="${MONITOR_ENV_FILE:-/opt/motor-expansao/app/.env}"
STATE_DIR="${MONITOR_STATE_DIR:-/var/lib/motor-monitoring}"
LOG_FILE="${MONITOR_LOG_FILE:-/var/log/motor-monitoring/healthcheck.log}"
REMIND_SECS="${MONITOR_REMIND_SECS:-3600}"
DISK_PCT_MAX="${MONITOR_DISK_PCT_MAX:-80}"
MEM_AVAIL_PCT_MIN="${MONITOR_MEM_AVAIL_PCT_MIN:-10}"
EDGE_URL="${MONITOR_EDGE_URL:-https://piloto.ultra-expansao.tech}"
GYM_REPORT_DIR="${MONITOR_GYM_REPORT_DIR:-/opt/gymscraping-infra}"
GYM_LOG_HINT="/var/log/gymscraping/weekly_latest.log"
# Série de snapshots de concorrentes (BLK-MA-21). O cron MENSAL dos agregadores é o único
# produtor de `fonte=wellhub` / `fonte=totalpass`; se ele parar, nada mais acusa — o score
# continua saindo, só que sobre uma série congelada, e o S4 lê a estagnação como sinal.
SNAPSHOTS_DIR="${MONITOR_SNAPSHOTS_DIR:-/opt/motor-expansao/data/staging/snapshots_concorrentes}"
# 45 dias = cadência de 28-35 dias (1ª terça do mês) + margem para uma execução perdida.
AGREGADOR_MAX_DIAS="${MONITOR_AGREGADOR_MAX_DIAS:-45}"
AGREGADORES=(wellhub totalpass)
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
    # DEC-022 (o container motor_expansao_streamlit saiu da vigilancia no corte). Total: 6.
    motor_expansao_web
)

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

report() { # report <chave> <OK|FAIL> <mensagem-de-falha>
    local key="$1" status="$2" msg="$3"
    local sf="$STATE_DIR/$key.state" now prev last
    now=$(date +%s)
    prev="OK" last=0
    if [[ -f "$sf" ]]; then
        read -r prev last <"$sf" || { prev="OK"; last=0; }
    fi
    if [[ "$status" == "FAIL" ]]; then
        log "FAIL $key: $msg"
        if [[ "$prev" != "FAIL" ]]; then
            send_telegram "🔴 [VPS Ultra] $msg" || true
            echo "FAIL $now" >"$sf"
        elif ((now - last >= REMIND_SECS)); then
            send_telegram "🔴 [VPS Ultra] (ainda em falha) $msg" || true
            echo "FAIL $now" >"$sf"
        fi
    else
        if [[ "$prev" == "FAIL" ]]; then
            send_telegram "🟢 [VPS Ultra] Recuperado: $key" || true
            log "RECOVER $key"
        fi
        echo "OK $now" >"$sf"
    fi
}

check_containers() {
    local c st hs code
    for c in "${CONTAINERS[@]}"; do
        st=$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null || echo "ausente")
        hs=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' "$c" 2>/dev/null || echo "n/a")
        if [[ "$st" != "running" || "$hs" == "unhealthy" ]]; then
            report "container_$c" FAIL "Container $c com problema: status=$st, health=$hs"
        else
            report "container_$c" OK ""
        fi
    done
    # Edge externo: 2xx/3xx (redirect do Authelia) ou 401 = vivo
    code=$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$EDGE_URL" || echo "000")
    if [[ "$code" =~ ^(2|3|401) ]]; then
        report edge OK ""
    else
        report edge FAIL "Dashboard fora do ar: $EDGE_URL respondeu HTTP $code"
    fi
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
    # Por que por FONTE e não pela série inteira: o cron SEMANAL escreve `fonte=unidades` toda
    # semana, então a série nunca parece velha — olhar só a partição mais recente esconderia,
    # para sempre, um cron mensal que morreu. Cada agregador tem chave de estado própria, para
    # que a falha de um não silencie o alerta do outro.
    #
    # A idade sai da CHAVE `semana=AAAA-SS`, não do mtime do diretório `fonte=`
    # [emenda de 2026-08-25 à DEC-039]. O mtime mentia, e mentia justamente onde dói: o passo 2
    # OBRIGATÓRIO da ordem de aplicação roda `--migrar-layout`, que CRIA a folha `fonte=` com
    # mtime de agora. Medido sobre cópia da partição viva: dado de 2026-08-05 (20 dias) reportado
    # como `0d`, e com limiar de 45 dias o FAIL atrasaria ~20 dias. A distância é arbitrária para
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
            report "agregador_$f" FAIL "Snapshot do agregador ${f} NUNCA foi fotografado (nenhuma partição em ${SNAPSHOTS_DIR}). O cron mensal foi agendado?"
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

case "${1:-}" in
containers) check_containers ;;
host) check_host ;;
authelia) check_authelia ;;
coleta) check_coleta ;;
agregadores) check_agregadores ;;
test)
    send_telegram "✅ [VPS Ultra] Monitoramento ativo — mensagem de teste"
    echo "mensagem de teste enviada"
    ;;
*)
    echo "uso: $0 {containers|host|authelia|coleta|agregadores|test}" >&2
    exit 2
    ;;
esac
