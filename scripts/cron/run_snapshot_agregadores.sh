#!/usr/bin/env bash
# ============================================================================
# Snapshot SEMANAL dos AGREGADORES (WellHub + TotalPass) -- terca, 02:00 UTC
#     -> data/staging/snapshots_concorrentes/semana=AAAA-SS/fonte=<fonte>/
#
# E' o BLK-MA-21 / DEC-039: o relogio dos INDEPENDENTES, que nunca foi ligado.
# Os independentes -- o universo-alvo do funil de M&A -- vivem SO' nesses dois
# agregadores. O cron de DOMINGO (`run_snapshot_concorrentes.sh`) fotografa o feed
# `unidades`, que e' de CADEIAS: sem este script, S3 (churn) e S4 (staleness)
# sobre independentes NUNCA amadurecem. As duas cadencias sao SEMANAIS e caem na
# MESMA semana ISO (medido: terca e domingo da mesma semana dao a mesma chave
# `semana=`) -- e' por isso que a particao tem DUAS chaves, `semana=/fonte=`.
#
# READ-ONLY sobre o M1: nao toca score_priorizacao, pesos, config.py, pipelines/m1
# nem artefato oficial. Escreve SO em data/staging/snapshots_concorrentes/ e no
# diretorio de agregadores curados.
#
# GUARDRAIL DESTE SCRIPT: ele NUNCA atualiza o clone do coletor, NUNCA copia nada
# entre maquinas, NUNCA abre sessao remota e NUNCA faz deploy. Tudo isso e' passo
# MANUAL do Felipe, comando a comando (CLAUDE.md secao 6).
#
# ---------------------------------------------------------------------------
# O QUE ELE FAZ, EM 3 PASSOS (D2: o wrapper faz tudo, numa linha de cron so')
#
#   0. ROTACAO  do CSV consolidado de cada coletor (ver bloco proprio abaixo).
#   1. COLETA   ~21h45: TotalPass (~1h45) e depois WellHub (~20h), na imagem
#               `gymscraping:local`, os DOIS com `--no-resume`. Falha de coletor
#               NAO aborta -- quem decide e' a guarda de frescor do passo 2.
#   2. CURADORIA escolhe o diretorio certo de cada agregador no clone, RECUSA
#               feed velho e publica os CSVs onde o snapshot os procura.
#   3. SNAPSHOT fotografa SO as fontes que a curadoria publicou.
#
# Um `flock` cobre os tres passos. A janela e' de ~21h45: sem ele, uma reexecucao
# manual no meio duplicaria as duas sessoes HTTP e a curadoria leria diretorio
# sendo escrito.
#
# ---------------------------------------------------------------------------
# POR QUE O PASSO 0 EXISTE: `--no-resume` NAO limpa o consolidado
#
# Nos dois coletores, `--no-resume` faz APENAS `args.checkpoint.unlink()`
# (`Wellhub/coletor_wellhub.py:138-140`, `TotalPass/coletor_totalpass.py`). O CSV
# consolidado (`Wellhub/unidades_wellhub.csv`, `TotalPass/unidades_totalpass.csv`)
# e' escrito por `csv_writer.append_rows` em modo "a", e `ensure_header` RETORNA
# CEDO quando o arquivo ja' existe com conteudo: NADA trunca o consolidado. Na 2a
# SEMANA as duas safras coexistem no mesmo arquivo, e `split_by_state` (modo "w")
# propaga as duas para os 27 CSVs por UF.
#
# O estrago nao e' volume, e' INVERSAO DE SINAL. `montar_snapshot` desempata por
# `sort_values([fonte, chave_snapshot, hash_campos_raspados])` + `drop_duplicates
# (keep="first")`: sobrevive o MENOR HASH, que e' arbitrario em relacao a' safra
# (`data_coleta` esta em CAMPOS_NUNCA_HASHEADOS, logo a safra nova nao se distingue
# pelo hash). Academia que MUDOU tem ~metade de chance de sobreviver com a linha
# VELHA -- `semanas_sem_mudanca` cresce sozinho e o S4 le "parado" exatamente em
# quem se mexeu. E mudanca de NOME gera chave nova SEM a velha sumir do feed, entao
# `sumiu_recente` (S1, o de maior peso) nunca dispara e nasce pin fantasma.
#
# ROTACIONAR, nao apagar: o consolidado vira `<nome>.<TS>.bak` ao lado do original.
# A coleta nasce limpa e o historico continua no disco para auditoria. So' roda
# quando a COLETA vai rodar -- com DRY_RUN=1 ou PULAR_COLETA=1 rotacionar destruiria
# justamente o feed que se quer reaproveitar.
#
# ---------------------------------------------------------------------------
# POR QUE A CURADORIA EXISTE, E POR QUE ELA PODE RECUSAR UMA FONTE
#
# Fotografar um feed que NAO foi recoletado e' pior do que nao fotografar: o
# `hash_campos_raspados` sai identico ao da semana anterior, `semanas_sem_mudanca`
# cresce sozinho e o S4 marca o universo INTEIRO daquela fonte como "parado" --
# que e' exatamente o sinal de vulnerabilidade que o funil de M&A procura. Falso
# positivo em massa, no sinal de segundo maior peso, e com codigo de saida 0.
#
# Se o coletor do WellHub morrer no meio da janela de 20h, os CSVs antigos ficam
# no disco. A curadoria mede a idade da linha mais VELHA ainda no diretorio
# (`min(data_coleta)`) e recusa publicar acima de MAX_IDADE_DIAS; este script
# entao tira aquela fonte do `--fontes`. A particao sai com meia foto -- e o
# parquet carimba `fontes_lidas` dizendo qual metade. A regua e' o MINIMO, nao o
# maximo: uma coleta que recolhe SO' uma UF e deixa as outras 26 velhas mediria
# idade 0 pelo maximo, e o piso relativo de volume nao dispararia (o total nao cai).
#
# ---------------------------------------------------------------------------
# ANTES DE AGENDAR: rode o modo seco. E' passo OBRIGATORIO.
#
#     DRY_RUN=1 /opt/motor-expansao-infra/run_snapshot_agregadores.sh
#
# Confira na saida, nesta ordem:
#   * `fontes_publicadas=` -- se vier vazio, o caminho ou o frescor estao errados;
#   * `regua_idade`        -- por agregador: `data_coleta_min` (regua boa) ou `mtime`
#                             (fallback; o feed nao trouxe data legivel). Idade medida
#                             por `mtime` num feed nao recoletado da' ~0 dia mesmo com
#                             85 dias de atraso -- foi medido no clone real;
#   * `linhas_snapshot`    -- se vier 0, o caminho dos CSVs curados esta errado. ATENCAO:
#                             na PRIMEIRA instalacao, com o destino ainda vazio, `0` e' o
#                             esperado por construcao -- a curadoria em DRY_RUN nao copia
#                             nada, entao nao ha o que o snapshot leia. Rode o modo seco
#                             uma 2a vez DEPOIS da 1a execucao real para a leitura valer;
#   * `versao_contrato`    -- tem de ser `snapshots_concorrentes_v4`. Se vier `v3`,
#                             a VPS esta rodando IMAGEM ANTIGA, que escreve com UMA
#                             chave de particao e APAGA a folha da outra cadencia.
#                             NAO agende: aplique a imagem nova primeiro.
#   * `retencao_semanas`   -- tem de ser 26. O `78` e' o valor da premissa MENSAL,
#                             que morreu: sob cadencia SEMANAL N particoes = N
#                             observacoes de CADA fonte, e o piso MEDIDO para o v4
#                             saturar e' 13 (`semanas_sem_mudanca` vale k-1 contra
#                             STALE_SEMANAS=12). 26 = 2x o piso. NUNCA abaixo de 13.
#
# INSTALACAO (uma vez):
#     install -d -m 0755 /opt/motor-expansao-infra   # idempotente
#     cp /opt/motor-expansao/app/scripts/cron/run_snapshot_agregadores.sh /opt/motor-expansao-infra/
#     chmod +x /opt/motor-expansao-infra/run_snapshot_agregadores.sh
#
# LINHA DE CRONTAB (D1 -- TODA terca, 02:00 UTC = segunda 23:00 BRT):
#     0 2 * * 2 /opt/motor-expansao-infra/run_snapshot_agregadores.sh
#
# SEM guarda de dia do mes: a cadencia e' SEMANAL, e com ela cai tambem o `%`
# escapado que o crontab exigia para emular "1a terca".
#
# A janela sequencial mede ~21h45: comecando 02:00 UTC de terca, fecha ~23h45 de
# terca. Folga de 39h DEPOIS do runner de domingo (06:00 UTC) e de ~102h ANTES do
# proximo -- as duas janelas nunca se encostam, nem na banda alta de 31h medida
# para o WellHub. Terca tambem deixa a retentativa manual caber na MESMA semana
# ISO: falha na terca -> FAIL do healthcheck na quinta 12:00 -> retentativa fecha
# sexta, e a observacao da semana e' salva.
#
# ORDEM DE APLICACAO (a ordem e' a defesa contra o modo destrutivo -- ver runbook
# em docs/infra_producao.md, secao "Coleta semanal dos agregadores (BLK-MA-21)").
# ============================================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/motor-expansao/app}"
HOST_STAGING="${HOST_STAGING:-/opt/motor-expansao/data/staging}"
# Clone do repo de coleta (docs/infra_producao.md, secao do GymScraping). E' de onde a
# curadoria LE -- montado :ro no passo 2.
HOST_GYMSCRAPING="${HOST_GYMSCRAPING:-/opt/gymscraping}"
# Destino da curadoria: FORA do clone do coletor de proposito. Escrever de volta dentro
# de um checkout versionado faria o proximo `git` do clone ver arvore suja, e o proximo
# sync sobrescrever a curadoria em silencio.
HOST_AGREGADORES="${HOST_AGREGADORES:-/opt/motor-expansao/data/agregadores}"
LOG_DIR="${LOG_DIR:-/var/log/motor-snapshots}"
LOCK_FILE="${LOCK_FILE:-/var/lock/motor-snapshot-agregadores.lock}"
DRY_RUN="${DRY_RUN:-0}"
# `PULAR_COLETA=1` reaproveita os CSVs ja' no disco: util para depurar os passos 2 e 3
# sem pagar 21h de coleta. A guarda de frescor continua valendo -- feed velho continua
# sendo recusado, e e' isso que torna o atalho seguro.
PULAR_COLETA="${PULAR_COLETA:-0}"
# 3 dias (nao 7): a borda da guarda e' INCLUSIVA, e o feed da rodada anterior mede exatamente
# 7 dias com o cron comecando 02:00 UTC -- com o default antigo, `7 <= 7` PUBLICAVA o feed
# velho, e a seguranca da guarda virava acidente do horario do cron.
MAX_IDADE_DIAS="${MAX_IDADE_DIAS:-3}"
MAX_LINHAS_WELLHUB="${MAX_LINHAS_WELLHUB:-}"
MAX_LINHAS_TOTALPASS="${MAX_LINHAS_TOTALPASS:-}"
# Piso RELATIVO de volume (fracao do que ja' esta publicado no destino). O teto acima pega universo
# que INFLA; o piso pega coleta que morreu na metade -- CSVs frescos, metade das linhas, e as que
# faltam viram `sumiu_recente` em massa no S1. Inerte na 1a execucao (sem baseline). `0` desliga.
PISO_RELATIVO="${PISO_RELATIVO:-0.5}"
IMAGEM_COLETOR="${IMAGEM_COLETOR:-gymscraping:local}"
# Consolidados que o passo 0 rotaciona, relativos ao clone. Ver o bloco "POR QUE O PASSO 0 EXISTE".
CONSOLIDADO_TOTALPASS="${CONSOLIDADO_TOTALPASS:-TotalPass/unidades_totalpass.csv}"
CONSOLIDADO_WELLHUB="${CONSOLIDADO_WELLHUB:-Wellhub/unidades_wellhub.csv}"

# LOG ANTES DO LOCK, de proposito. Sob cadencia SEMANAL, uma rodada TRAVADA (nao apenas
# atrasada) segura o lock e faz TODA semana seguinte sair com `exit 0`. Se o `tee` so'
# comecasse depois do `flock`, a colisao nao deixaria arquivo NENHUM em $LOG_DIR: o unico
# destino do aviso seria o stdout do cron (mail do root, que pode nem estar configurado) e o
# symlink `_latest.log` continuaria apontando para a ultima rodada COMPLETA -- o script
# pularia EM SILENCIO. Agora cada colisao deixa o proprio arquivo de log, datado.
TS="$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR"
LOG="${LOG_DIR}/snapshot_agregadores_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

# `flock -n` sobre o script INTEIRO: a janela e' de ~21h45 e duas execucoes concorrentes
# duplicariam as sessoes HTTP dos coletores e fariam a curadoria ler diretorio em escrita.
# Sair com 0 quando ja' ha' uma instancia e' deliberado: "ja' esta rodando" nao e' falha.
exec 9>"$LOCK_FILE"
flock -n 9 || { echo ">> ja rodando (lock $LOCK_FILE); saindo"; exit 0; }

echo ">> [$(date -u +%FT%TZ)] snapshot SEMANAL dos agregadores - inicio (dry_run=${DRY_RUN}, pular_coleta=${PULAR_COLETA})"

# --------------------------------------------------------------------------
# Pre-checagens que abortam CEDO, com mensagem acionavel (antes de qualquer passo)
# --------------------------------------------------------------------------
[ -d "$HOST_GYMSCRAPING" ] || { echo "!! clone do coletor ausente: $HOST_GYMSCRAPING"; exit 1; }
# Caixa EXATA. No Linux `TotalPass` != `Totalpass`, e o clone so' tem a forma certa depois
# do PR #11 do GymScraping. Sem ele, `python -m TotalPass.coletor_totalpass` morre com
# ModuleNotFoundError ANTES de qualquer log -- sintoma que aponta para o lugar errado.
[ -d "${HOST_GYMSCRAPING}/TotalPass" ] || {
  echo "!! ${HOST_GYMSCRAPING}/TotalPass ausente (caixa exata)."
  echo "   O clone esta desatualizado: atualize-o A MAO antes de rodar (bloqueador (1) do BLK-MA-21)."
  exit 1
}
[ -d "${HOST_GYMSCRAPING}/Wellhub" ] || { echo "!! ${HOST_GYMSCRAPING}/Wellhub ausente (caixa exata)"; exit 1; }

# Imagem da API pinada por digest no .env do compose (carrega o motor completo).
# `tr -d '\r'` NAO e' paranoia: o .env da VPS chegou por rsync de uma maquina Windows e
# pode ter CRLF. Sem isso o `\r` final entra no nome da imagem e o `docker run` morre com
# "invalid reference format" -- mensagem que parece digest torto.
API_IMAGE="$(grep -E '^API_IMAGE=' "${APP_DIR}/.env" | head -1 | cut -d= -f2- | tr -d '\r' || true)"
API_IMAGE="${API_IMAGE%\"}"; API_IMAGE="${API_IMAGE#\"}"
API_IMAGE="${API_IMAGE%\'}"; API_IMAGE="${API_IMAGE#\'}"
[ -n "$API_IMAGE" ] || { echo "!! API_IMAGE nao encontrado em ${APP_DIR}/.env"; exit 1; }
echo ">> API_IMAGE=${API_IMAGE}"

mkdir -p "$HOST_AGREGADORES"

# --------------------------------------------------------------------------
# Passo 0 - ROTACAO do consolidado (so' quando a coleta vai rodar)
#
# `--no-resume` apaga o CHECKPOINT, nao o consolidado -- e o consolidado e' escrito
# em modo "a". Sem esta rotacao, a semana 2 anexa safra sobre safra e o desempate por
# menor hash congela a linha VELHA de quem mudou. Detalhe no cabecalho.
# --------------------------------------------------------------------------
rotacionar_consolidado() {
  local arq="$1" rotulo="$2" destino
  if [ ! -s "$arq" ]; then
    echo ">> passo 0 (${rotulo}): consolidado ausente ou vazio (${arq}); nada a rotacionar"
    return 0
  fi
  # Sufixo SEM `.csv` de proposito: nenhum glob de curadoria ou de `split_by_state` pode
  # voltar a casar o arquivo rotacionado.
  destino="${arq%.csv}.${TS}.bak"
  mv "$arq" "$destino"
  echo ">> passo 0 (${rotulo}): consolidado rotacionado -> ${destino}"
}

# --------------------------------------------------------------------------
# Passo 1 - COLETA (~21h45). Pulada em modo seco e com PULAR_COLETA=1.
# --------------------------------------------------------------------------
if [ "$DRY_RUN" = "1" ] || [ "$PULAR_COLETA" = "1" ]; then
  echo ">> passos 0 e 1 (rotacao + coleta) PULADOS; usando os CSVs ja no clone"
else
  docker image inspect "$IMAGEM_COLETOR" >/dev/null 2>&1 || {
    echo "!! imagem ${IMAGEM_COLETOR} ausente; ela e construida pelo runner semanal do coletor"
    exit 1
  }
  # TotalPass primeiro (~1h45), WellHub depois (~20h): o mais curto primeiro faz uma falha
  # de ambiente aparecer em minutos, nao no dia seguinte.
  #
  # `--no-resume` nos DOIS. Sem ele no TotalPass, `pipeline.py` filtra
  # `pending = [s for s in slugs if not checkpoint.already_processed(s)]` e retorna cedo com
  # `if not pending` -- com o checkpoint cheio (34.982 slugs medidos nesta estacao) NADA e'
  # recoletado. E o coletor NAO para ali: `split_by_state` roda em seguida e reescreve os 27
  # CSVs por UF em modo "w", com conteudo identico e mtime de AGORA. O coletor sai com
  # SUCESSO, entao o `|| echo` abaixo nunca dispara, e uma guarda de frescor por mtime veria
  # idade ~0 num feed de 85 dias (medido). Por isso a guarda mede `data_coleta`, nao mtime.
  echo ">> [$(date -u +%FT%TZ)] passo 1a - coletor TotalPass"
  rotacionar_consolidado "${HOST_GYMSCRAPING}/${CONSOLIDADO_TOTALPASS}" TotalPass
  docker run --rm --user 0:0 -v "${HOST_GYMSCRAPING}:/app" "$IMAGEM_COLETOR" \
    python -m TotalPass.coletor_totalpass --workers 5 --delay 0.3 --no-resume \
    || echo ">> coletor TotalPass falhou; a curadoria vai recusar o feed velho"

  echo ">> [$(date -u +%FT%TZ)] passo 1b - coletor WellHub"
  rotacionar_consolidado "${HOST_GYMSCRAPING}/${CONSOLIDADO_WELLHUB}" WellHub
  docker run --rm --user 0:0 -v "${HOST_GYMSCRAPING}:/app" "$IMAGEM_COLETOR" \
    python -m Wellhub.coletor_wellhub --workers 2 --delay 1.0 --no-resume \
    || echo ">> coletor WellHub falhou; a curadoria vai recusar o feed velho"
fi

# --------------------------------------------------------------------------
# Passo 2 - CURADORIA (na imagem da API; clone :ro, destino :rw)
# --------------------------------------------------------------------------
echo ">> [$(date -u +%FT%TZ)] passo 2 - curadoria dos agregadores"
CUR_ARGS=(--origem gymscraping --destino concorrentes --max-idade-dias "$MAX_IDADE_DIAS")
CUR_ARGS+=(--piso-relativo "$PISO_RELATIVO")
[ -n "$MAX_LINHAS_WELLHUB" ] && CUR_ARGS+=(--max-linhas-wellhub "$MAX_LINHAS_WELLHUB")
[ -n "$MAX_LINHAS_TOTALPASS" ] && CUR_ARGS+=(--max-linhas-totalpass "$MAX_LINHAS_TOTALPASS")
[ "$DRY_RUN" = "1" ] && CUR_ARGS+=(--dry-run)

set +e
CUR_OUT="$(docker run --rm --user 0:0 \
  -v "${HOST_GYMSCRAPING}:/app/gymscraping:ro" \
  -v "${HOST_AGREGADORES}:/app/concorrentes" \
  "$API_IMAGE" \
  python -m motor_expansao.vulnerabilidade.curadoria_agregadores "${CUR_ARGS[@]}" 2>&1)"
CUR_RC=$?
set -e
echo "$CUR_OUT"
[ "$CUR_RC" -eq 0 ] || { echo "!! curadoria falhou (rc=${CUR_RC})"; exit "$CUR_RC"; }

# A linha de contrato entre o modulo e o shell: formato FIXO, para o shell nunca precisar
# parsear dicionario Python (que muda de forma a cada campo novo).
FONTES_CSV="$(printf '%s\n' "$CUR_OUT" | grep -E '^fontes_publicadas=' | tail -1 | cut -d= -f2- | tr -d '\r')"
FONTES="$(printf '%s' "$FONTES_CSV" | tr ',' ' ')"
echo ">> fontes publicadas pela curadoria: '${FONTES_CSV}'"

# Nada fresco para fotografar e' FALHA, nao sucesso silencioso: se sairmos com 0 aqui, o
# healthcheck de idade da particao seria a unica coisa a perceber -- 9 dias depois.
if [ -z "$FONTES_CSV" ]; then
  echo "!! nenhuma fonte publicada: os dois feeds estao velhos ou ausentes."
  echo "   Confira a saida da curadoria acima (motivo_recusa por agregador) e o log dos coletores."
  exit 3
fi

# --------------------------------------------------------------------------
# Passo 3 - SNAPSHOT (mesmo modulo do cron de domingo, outro dia da semana)
# --------------------------------------------------------------------------
echo ">> [$(date -u +%FT%TZ)] passo 3 - snapshot das fontes publicadas"
SNAP_ARGS=(--fontes)
# shellcheck disable=SC2206  # split intencional: `--fontes` recebe N valores
SNAP_ARGS+=($FONTES)
SNAP_ARGS+=(--dir-wellhub concorrentes/wellhub/csvs --dir-totalpass concorrentes/totalpass/csvs)
if [ "$DRY_RUN" = "1" ]; then
  SNAP_ARGS+=(--dry-run)
  MOUNT_STAGING="${HOST_STAGING}:/app/data/staging:ro"   # modo seco nem monta RW
else
  MOUNT_STAGING="${HOST_STAGING}:/app/data/staging"
fi

# `--user 0:0` pelo mesmo motivo dos outros one-shots: staging e CSVs do host sao root:root
# e a imagem roda como appuser(1000) -> sem root, PermissionError.
docker run --rm \
  --user 0:0 \
  -v "$MOUNT_STAGING" \
  -v "${HOST_AGREGADORES}:/app/concorrentes:ro" \
  "$API_IMAGE" \
  python -m motor_expansao.vulnerabilidade.snapshots "${SNAP_ARGS[@]}"

if [ "$DRY_RUN" = "1" ]; then
  echo '>> DRY-RUN: nada gravado, nenhuma semana podada.'
  echo '   Confira acima: fontes_publicadas, linhas_snapshot, retencao_semanas=26 e'
  echo '   versao_contrato=snapshots_concorrentes_v4 (v3 = imagem ANTIGA; NAO agende).'
else
  echo ">> particoes em ${HOST_STAGING}/snapshots_concorrentes/"
  ls -la "${HOST_STAGING}/snapshots_concorrentes/" 2>/dev/null || echo "   (primeira execucao?)"
fi

echo ">> [$(date -u +%FT%TZ)] snapshot SEMANAL dos agregadores - OK"
ln -sfn "$LOG" "${LOG_DIR}/snapshot_agregadores_latest.log"
