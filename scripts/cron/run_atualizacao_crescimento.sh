#!/usr/bin/env bash
# ============================================================================
# Atualizacao TRIMESTRAL da camada de crescimento municipal (DEC-049)
#     CAGED novo -> cadeia 01..10 -> validacao -> publicacao atomica -> restart
#     -> aviso no chat de ops do Telegram (bot "Paulo"), nos DOIS desfechos.
#
# Antes deste cron a camada era ESTATICA desde a publicacao (2026-08-07): sem
# cadencia, sem alarme, e o passo 4 do piloto envelhecia em silencio. Agora o
# EMPREGO (CAGED, fonte mensal) avanca a cada trimestre; as dimensoes anuais
# (renda/populacao/empresas; predios via satelite e' 2016-2023 estatico) avancam
# quando as safras das fontes avancarem —
# e o aviso do bot diz isso com todas as letras, para ninguem ler "atualizado"
# como "tudo novo".
#
# READ-ONLY sobre o M1: escreve SO os dois parquets de crescimento no staging e o
# consolidado do CAGED nos insumos. `outputs/` e' montado :ro por construcao.
#
# GUARDRAIL DESTE SCRIPT (mesmo do wrapper dos agregadores): ele NUNCA copia nada
# entre maquinas, NUNCA abre sessao remota e NUNCA faz deploy de imagem. Instalar,
# agendar e atualizar insumos estaticos e' passo MANUAL do dono (CLAUDE.md §6).
#
# ---------------------------------------------------------------------------
# O QUE ELE FAZ, EM 4 PASSOS
#
#   1. JOB        container efemero com a imagem da API roda
#                 `python -m motor_expansao.crescimento.atualizar`:
#                 baixa meses novos do CAGED (FTP publico do PDET), roda a cadeia
#                 copiada do checkout num diretorio de trabalho, valida e publica
#                 por rename atomico. Falhou qualquer etapa: staging intacto.
#   2. PROVA      confere DENTRO do container do web que os dois parquets estao
#                 legiveis (33/3 colunas) — o passo 4 do runbook de publicacao.
#   3. RESTART    `docker restart motor_expansao_web` — os loaders sao
#                 `lru_cache(maxsize=1)`; sem restart, publicar nao muda a tela.
#                 NUNCA `up -d --force-recreate` (reaplicaria o compose inteiro e
#                 poderia trocar a versao do piloto junto com o dado).
#   4. AVISO      `python -m motor_expansao.crescimento.aviso` manda o resumo ao
#                 chat de ops; em falha, manda qual etapa caiu. Token/chat vao por
#                 `-e NOME` SEM valor (nunca no argv do docker, visivel em `ps`).
#
# ---------------------------------------------------------------------------
# INSUMOS NA VPS (repasse inicial — docs/infra_producao.md, secao da atualizacao
# trimestral, lista arquivo a arquivo):
#
#   ${HOST_INSUMOS}/socioeconomico/{caged,rais,cnpj,pib}   (~90 MB de agregados)
#   ${HOST_INSUMOS}/crescimento_tec/*.csv                  (3 CSVs do projeto TEC)
#   ${HOST_INSUMOS}/poc_satelite/data/uf=XX/...            (mosaicos, 12 UFs)
#   ${HOST_INSUMOS}/eixo/_eixo_trajetoria.parquet          (projeto poc_satelite)
#
# Os scripts da cadeia vem do CHECKOUT (${APP_DIR}/data/reports/crescimento),
# montado :ro — o orquestrador os COPIA para um tmp interno, entao a arvore git
# do checkout nunca fica suja (licao do wrapper dos agregadores).
#
# ANTES DE AGENDAR: rode o modo seco (passo obrigatorio, como nos outros crons):
#     DRY_RUN=1 /opt/motor-expansao-infra/run_atualizacao_crescimento.sh
#   DRY_RUN valida tudo e imprime o aviso no stdout SEM publicar, SEM restart e
#   SEM Telegram. Depois do primeiro real, confira `crescimento` no healthcheck.
#
# INSTALACAO (uma vez):
#     install -d -m 0755 /opt/motor-expansao-infra
#     cp /opt/motor-expansao/app/scripts/cron/run_atualizacao_crescimento.sh /opt/motor-expansao-infra/
#     chmod +x /opt/motor-expansao-infra/run_atualizacao_crescimento.sh
#
# LINHA DE CRONTAB (dia 5 de fev/mai/ago/nov, 03:00 UTC = 00:00 BRT):
#     0 3 5 2,5,8,11 * /opt/motor-expansao-infra/run_atualizacao_crescimento.sh
#
# Por que ESSES meses: o CAGED de um mes sai ~40 dias depois dele; no dia 5 de
# fev/mai/ago/nov o trimestre-calendario anterior (ate dez/mar/jun/set) ja' esta
# publicado inteiro. Madrugada de dia 5: fora das janelas de domingo (06:00) e
# terca (02:00) dos outros crons — e mesmo colidindo, os locks sao distintos e o
# docker serializa sem drama; a janela aqui mede MINUTOS, nao horas.
# ============================================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/motor-expansao/app}"
HOST_STAGING="${HOST_STAGING:-/opt/motor-expansao/data/staging}"
HOST_OUTPUTS="${HOST_OUTPUTS:-/opt/motor-expansao/data/outputs}"
HOST_INSUMOS="${HOST_INSUMOS:-/opt/motor-expansao/data/insumos_crescimento}"
LOG_DIR="${LOG_DIR:-/var/log/motor-snapshots}"
LOCK_FILE="${LOCK_FILE:-/var/lock/motor-atualizacao-crescimento.lock}"
RUN_DIR="${RUN_DIR:-/opt/motor-expansao-infra/crescimento_run}"
DRY_RUN="${DRY_RUN:-0}"
WEB_CONTAINER="${WEB_CONTAINER:-motor_expansao_web}"

# LOG ANTES DO LOCK (molde dos agregadores): uma rodada travada deixaria as
# seguintes sairem com exit 0 e NENHUM arquivo de log — colisao silenciosa.
TS="$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR" "$RUN_DIR"
LOG="${LOG_DIR}/atualizacao_crescimento_${TS}.log"
exec > >(tee -a "$LOG") 2>&1
# O symlink `_latest` aponta para ESTA rodada desde o inicio — e' o caminho que o
# aviso de falha e o healthcheck citam; se so' o sucesso o atualizasse, a PRIMEIRA
# falha mandaria ops depurar o log da rodada anterior (defeito pego na revisao).
ln -sfn "$LOG" "${LOG_DIR}/atualizacao_crescimento_latest.log"

exec 9>"$LOCK_FILE"
flock -n 9 || { echo ">> ja rodando (lock $LOCK_FILE); saindo"; exit 0; }

echo ">> [$(date -u +%FT%TZ)] atualizacao trimestral do crescimento - inicio (dry_run=${DRY_RUN})"

# Le VAR=valor do .env do compose (mesmo espirito do get_env_var do healthcheck).
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
# Credencial ausente NAO aborta a atualizacao (o dado vale mais que o aviso), mas
# fica GRITADO no log: sem isso os avisos morreriam engolidos pelo `|| true` e
# ninguem saberia que ops ficou surdo.
if [ "$DRY_RUN" != "1" ] && { [ -z "$API_TELEGRAM_TOKEN" ] || [ -z "$MONITOR_TELEGRAM_CHAT_ID" ]; }; then
  echo "!! AVISO: API_TELEGRAM_TOKEN/MONITOR_TELEGRAM_CHAT_ID ausentes no .env — a rodada segue, mas NENHUM aviso chegara ao chat de ops"
fi

# Pre-checagens que abortam CEDO, com mensagem acionavel.
[ -d "${APP_DIR}/data/reports/crescimento" ] || { echo "!! cadeia ausente no checkout: ${APP_DIR}/data/reports/crescimento"; exit 1; }
for d in socioeconomico crescimento_tec poc_satelite eixo; do
  [ -d "${HOST_INSUMOS}/${d}" ] || { echo "!! insumo ausente: ${HOST_INSUMOS}/${d} (repasse inicial nao feito? ver docs/infra_producao.md)"; exit 1; }
done
docker image inspect "$API_IMAGE" >/dev/null 2>&1 || { echo "!! imagem ${API_IMAGE} ausente"; exit 1; }
# Imagem antiga (sem o modulo/py7zr) falharia a cada trimestre com erro criptico.
docker run --rm "$API_IMAGE" python -c "import motor_expansao.crescimento.atualizar, py7zr" 2>/dev/null \
  || { echo "!! a imagem nao tem o modulo de crescimento ou o py7zr (extra [crescimento]) — aplique a imagem nova antes de agendar"; exit 1; }

# Aviso de falha SO' quando a rodada e' real: um DRY_RUN quebrado nao acorda ops.
_avisar_falha() {
  local etapa="$1"
  [ "$DRY_RUN" = "1" ] && { echo ">> DRY-RUN: falha em '${etapa}' (aviso suprimido)"; return 0; }
  docker run --rm -e API_TELEGRAM_TOKEN -e MONITOR_TELEGRAM_CHAT_ID "$API_IMAGE" \
    python -m motor_expansao.crescimento.aviso --falha "$etapa" || true
}

# --------------------------------------------------------------------------
# Passo 1 - JOB (CAGED + cadeia + validacao + publicacao atomica)
# --------------------------------------------------------------------------
JOB_ARGS=(--scripts-dir /insumos/scripts --eixo /insumos/eixo/_eixo_trajetoria.parquet --resumo /saida/resumo.json)
MOUNT_STAGING="${HOST_STAGING}:/app/data/staging"
MOUNT_SOCIO="${HOST_INSUMOS}/socioeconomico:/insumos/socioeconomico"
if [ "$DRY_RUN" = "1" ]; then
  # Modo seco nao escreve em staging NEM nos insumos (:ro, sem publicar, sem baixar
  # CAGED — valida a cadeia com o consolidado que ja' existe). O que ele grava e'
  # so' o proprio log e o resumo.json em $RUN_DIR.
  JOB_ARGS+=(--sem-publicar --pular-caged)
  MOUNT_STAGING="${MOUNT_STAGING}:ro"
  MOUNT_SOCIO="${MOUNT_SOCIO}:ro"
fi

echo ">> [$(date -u +%FT%TZ)] passo 1 - job de atualizacao"
set +e
docker run --rm --user 0:0 \
  -v "$MOUNT_STAGING" \
  -v "${HOST_OUTPUTS}:/app/data/outputs:ro" \
  -v "${APP_DIR}/data/reports/crescimento:/insumos/scripts:ro" \
  -v "$MOUNT_SOCIO" \
  -v "${HOST_INSUMOS}/crescimento_tec:/insumos/crescimento_tec:ro" \
  -v "${HOST_INSUMOS}/poc_satelite:/insumos/poc_satelite:ro" \
  -v "${HOST_INSUMOS}/eixo:/insumos/eixo:ro" \
  -v "${RUN_DIR}:/saida" \
  -e MOTOR_DATA_DIR=/app/data \
  -e SOCIOECONOMICO_DIR=/insumos/socioeconomico \
  -e CRESCIMENTO_TEC_DIR=/insumos/crescimento_tec \
  -e POC_SATELITE_DIR=/insumos/poc_satelite \
  "$API_IMAGE" \
  python -m motor_expansao.crescimento.atualizar "${JOB_ARGS[@]}"
JOB_RC=$?
set -e
if [ "$JOB_RC" -ne 0 ]; then
  # Traducao por exit code (contrato no docstring do atualizar.py): so' o 5 pode
  # ter tocado o staging — todos os outros abortam ANTES de publicar.
  case "$JOB_RC" in
    5) _avisar_falha "publicação no staging (rc=5): a janela entre os dois renames PODE ter deixado municipal novo + hex antigo — conferir o log e, se preciso, rollback do runbook da camada" ;;
    4) _avisar_falha "validação do artefato reprovou (rc=4) — nada publicado, staging intacto" ;;
    3) _avisar_falha "cadeia 01..10 falhou (rc=3) — nada publicado, staging intacto" ;;
    *) _avisar_falha "insumo/ambiente do job (rc=${JOB_RC}) — nada publicado, staging intacto" ;;
  esac
  exit "$JOB_RC"
fi

if [ "$DRY_RUN" = "1" ]; then
  echo ">> DRY-RUN: nada publicado, sem prova no web, sem restart, sem Telegram."
  echo ">> aviso que SERIA enviado:"
  docker run --rm -v "${RUN_DIR}:/saida:ro" "$API_IMAGE" \
    python -m motor_expansao.crescimento.aviso --resumo /saida/resumo.json --stdout || true
  echo ">> [$(date -u +%FT%TZ)] atualizacao trimestral (dry-run) - OK"
  exit 0
fi

# --------------------------------------------------------------------------
# Passo 2 - PROVA de legibilidade DENTRO do container do web (runbook, passo 4)
# --------------------------------------------------------------------------
echo ">> [$(date -u +%FT%TZ)] passo 2 - prova de legibilidade no web"
if ! docker exec "$WEB_CONTAINER" python -c "import pyarrow.parquet as pq; [print(p, len(pq.read_schema(p).names)) for p in ('/app/data/staging/crescimento_municipal.parquet','/app/data/staging/crescimento_hex.parquet')]"; then
  _avisar_falha "prova de legibilidade no container do web (restart NAO feito; container atual segue servindo o estado anterior)"
  exit 4
fi

# --------------------------------------------------------------------------
# Passo 3 - RESTART (lru_cache: sem ele, a tela nao muda)
# --------------------------------------------------------------------------
echo ">> [$(date -u +%FT%TZ)] passo 3 - restart do ${WEB_CONTAINER}"
if ! docker restart "$WEB_CONTAINER"; then
  _avisar_falha "docker restart ${WEB_CONTAINER} (artefato novo publicado, tela ainda no cache antigo)"
  exit 5
fi

# --------------------------------------------------------------------------
# Passo 4 - AVISO de sucesso no chat de ops
# --------------------------------------------------------------------------
echo ">> [$(date -u +%FT%TZ)] passo 4 - aviso no Telegram"
docker run --rm -v "${RUN_DIR}:/saida:ro" \
  -e API_TELEGRAM_TOKEN -e MONITOR_TELEGRAM_CHAT_ID "$API_IMAGE" \
  python -m motor_expansao.crescimento.aviso --resumo /saida/resumo.json \
  || echo "!! aviso de sucesso nao foi enviado (rodada em si esta' OK)"

echo ">> [$(date -u +%FT%TZ)] atualizacao trimestral do crescimento - OK"
