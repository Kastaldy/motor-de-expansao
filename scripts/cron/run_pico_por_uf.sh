#!/usr/bin/env bash
# ============================================================================
# Atualizacao MENSAL do pico de maturacao padrao por ESTADO (emenda de
# 2026-10-29 da DEC-078)
#     fechamento mensal da Growth -> regua do UNI-03 -> portao -> corte de 5,
#     peso n/(n+10), freio de 1 mes -> publicacao atomica -> aviso no chat de ops
#
# O padrao NACIONAL (10 meses, curva do UNI-03) NAO muda aqui. O job so' publica,
# para cada estado com 5+ unidades maduras, o padrao proprio que a Viabilidade usa
# quando o operador nao escolhe o pico no contador. READ-ONLY sobre o M1 e sobre a
# Growth: escreve SO' `staging/pico_rampa_por_uf.json`.
#
# SEM RESTART: a leitura (`pico_por_uf.ler_artefato`) confere o mtime do arquivo a
# cada consulta; publicar ja' muda a tela, a planilha, o PDF e a API.
#
# GUARDRAIL (o mesmo dos outros crons): nunca copia nada entre maquinas, nunca abre
# sessao remota, nunca faz deploy. Instalar e agendar e' passo MANUAL (CLAUDE.md §6).
#
# ---------------------------------------------------------------------------
# PASSOS
#   1. JOB    container efemero da imagem da API roda
#             `python -m motor_expansao.dimensionamento.pico_por_uf`: mede na
#             base da Growth, aplica corte/peso/freio e publica por rename
#             atomico. Portao reprovado (rc=2): nada publicado, arquivo anterior
#             intacto. Com `--avisar`, o proprio job manda o resumo ao chat de ops
#             nos dois desfechos.
#   2. FALHA  qualquer outro codigo: o wrapper manda ao chat de ops QUAL etapa
#             caiu (`--falha`), e o arquivo anterior segue valendo.
#
# O job roda com MOTOR_DATA_DIR + o bind do `perfil.json` de producao: desde a
# DEC-047 o pacote resolve o perfil no IMPORT, e sem os dois o loader procura o
# arquivo ao lado do pacote instalado e morre (licao do BLK-SAUDE-08).
#
# ANTES DE AGENDAR: o modo seco (mede e imprime; staging :ro; sem Telegram):
#     DRY_RUN=1 /opt/motor-expansao-infra/run_pico_por_uf.sh
#
# INSTALACAO (uma vez):
#     install -d -m 0755 /opt/motor-expansao-infra
#     cp /opt/motor-expansao/app/scripts/cron/run_pico_por_uf.sh /opt/motor-expansao-infra/
#     chmod +x /opt/motor-expansao-infra/run_pico_por_uf.sh
#
# LINHA DE CRONTAB (dia 3 de cada mes, 04:00 UTC = 01:00 BRT):
#     0 4 3 * * /opt/motor-expansao-infra/run_pico_por_uf.sh
#
# Por que dia 3: o job usa so' o ultimo mes COMPLETO, e no dia 3 o mes anterior ja'
# fechou na Growth (ingestao diaria). Madrugada, fora das janelas de domingo (06:00)
# e do dia 5 (crescimento); o job mede MINUTOS.
# ============================================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/motor-expansao/app}"
HOST_DATA="${HOST_DATA:-/opt/motor-expansao/data}"
HOST_STAGING="${HOST_STAGING:-${HOST_DATA}/staging}"
LOG_DIR="${LOG_DIR:-/var/log/motor-snapshots}"
LOCK_FILE="${LOCK_FILE:-/var/lock/motor-pico-por-uf.lock}"
DRY_RUN="${DRY_RUN:-0}"

# LOG ANTES DO LOCK (molde dos outros crons): uma rodada travada deixaria as
# seguintes sairem com exit 0 e nenhum arquivo de log.
TS="$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR"
LOG="${LOG_DIR}/pico_por_uf_${TS}.log"
exec > >(tee -a "$LOG") 2>&1
ln -sfn "$LOG" "${LOG_DIR}/pico_por_uf_latest.log"

exec 9>"$LOCK_FILE"
flock -n 9 || { echo ">> ja rodando (lock $LOCK_FILE); saindo"; exit 0; }

echo ">> [$(date -u +%FT%TZ)] pico por estado - inicio (dry_run=${DRY_RUN})"

# Le VAR=valor do .env do compose (o mesmo `_env_do_compose` da rotina do crescimento).
_env_do_compose() {
  local valor
  valor="$(grep -E "^${1}=" "${APP_DIR}/.env" | head -1 | cut -d= -f2- | tr -d '\r' || true)"
  valor="${valor%\"}"; valor="${valor#\"}"
  valor="${valor%\'}"; valor="${valor#\'}"
  printf '%s' "$valor"
}

API_IMAGE="$(_env_do_compose API_IMAGE)"
[ -n "$API_IMAGE" ] || { echo "!! API_IMAGE nao encontrado em ${APP_DIR}/.env"; exit 1; }
echo ">> API_IMAGE=${API_IMAGE}"

API_TELEGRAM_TOKEN="$(_env_do_compose API_TELEGRAM_TOKEN)"
MONITOR_TELEGRAM_CHAT_ID="$(_env_do_compose MONITOR_TELEGRAM_CHAT_ID)"
export API_TELEGRAM_TOKEN MONITOR_TELEGRAM_CHAT_ID
# Credencial ausente NAO aborta (o dado vale mais que o aviso), mas fica GRITADO.
if [ "$DRY_RUN" != "1" ] && { [ -z "$API_TELEGRAM_TOKEN" ] || [ -z "$MONITOR_TELEGRAM_CHAT_ID" ]; }; then
  echo "!! AVISO: API_TELEGRAM_TOKEN/MONITOR_TELEGRAM_CHAT_ID ausentes no .env — a rodada segue, mas NENHUM aviso chegara ao chat de ops"
fi

# Pre-checagens que abortam CEDO, com mensagem acionavel.
[ -f "${HOST_STAGING}/growth_api_historico.parquet" ] || { echo "!! base da Growth ausente: ${HOST_STAGING}/growth_api_historico.parquet"; exit 1; }
[ -f "${HOST_DATA}/perfil.json" ] || { echo "!! perfil ausente: ${HOST_DATA}/perfil.json"; exit 1; }
docker image inspect "$API_IMAGE" >/dev/null 2>&1 || { echo "!! imagem ${API_IMAGE} ausente"; exit 1; }
PERFIL_MOUNT="${HOST_DATA}/perfil.json:/app/data/perfil.json:ro"
docker run --rm -e MOTOR_DATA_DIR=/app/data -v "$PERFIL_MOUNT" "$API_IMAGE" \
  python -c "import motor_expansao.dimensionamento.pico_por_uf" 2>/dev/null \
  || { echo "!! a imagem nao tem o modulo do pico por estado — aplique a imagem nova antes de agendar"; exit 1; }

# Aviso de falha SO' quando a rodada e' real: um DRY_RUN quebrado nao acorda ops.
_avisar_falha() {
  local etapa="$1"
  [ "$DRY_RUN" = "1" ] && { echo ">> DRY-RUN: falha em '${etapa}' (aviso suprimido)"; return 0; }
  docker run --rm -e API_TELEGRAM_TOKEN -e MONITOR_TELEGRAM_CHAT_ID \
    -e MOTOR_DATA_DIR=/app/data -v "$PERFIL_MOUNT" "$API_IMAGE" \
    python -m motor_expansao.dimensionamento.pico_por_uf --falha "$etapa" || true
}

# --------------------------------------------------------------------------
# Passo 1 - JOB (medicao, corte/peso/freio, publicacao atomica, aviso)
# --------------------------------------------------------------------------
JOB_ARGS=(--staging /app/data/staging)
MOUNT_STAGING="${HOST_STAGING}:/app/data/staging"
if [ "$DRY_RUN" = "1" ]; then
  # Modo seco nao escreve no staging (:ro) e imprime o aviso em vez de mandar.
  JOB_ARGS+=(--seco)
  MOUNT_STAGING="${MOUNT_STAGING}:ro"
else
  JOB_ARGS+=(--avisar)
fi

echo ">> [$(date -u +%FT%TZ)] passo 1 - medicao e publicacao"
set +e
docker run --rm --user 0:0 --memory 1536m --memory-swap 1536m --cpus 1 \
  -v "$MOUNT_STAGING" \
  -v "$PERFIL_MOUNT" \
  -e MOTOR_DATA_DIR=/app/data \
  -e PYTHONIOENCODING=utf-8 \
  -e API_TELEGRAM_TOKEN -e MONITOR_TELEGRAM_CHAT_ID \
  "$API_IMAGE" \
  python -m motor_expansao.dimensionamento.pico_por_uf "${JOB_ARGS[@]}"
JOB_RC=$?
set -e

case "$JOB_RC" in
  0) echo ">> [$(date -u +%FT%TZ)] pico por estado - OK" ;;
  2) echo ">> [$(date -u +%FT%TZ)] portao reprovou: nada publicado, arquivo anterior intacto (o job ja' avisou)"; exit 2 ;;
  *) _avisar_falha "job do pico por estado (rc=${JOB_RC}) — nada publicado, arquivo anterior intacto"; exit "$JOB_RC" ;;
esac
