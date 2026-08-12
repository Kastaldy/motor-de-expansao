#!/usr/bin/env bash
# ============================================================================
# Snapshot SEMANAL de concorrentes -> data/staging/snapshots_concorrentes/
#     semana=AAAA-SS/parte-*.parquet
#
# E' o passo do BLK-MA-06: fotografa o feed de concorrentes ANTES de a coleta da
# semana seguinte sobrescrever os CSVs crus. Sem ele, S3 (churn) e S4 (staleness)
# nunca tem serie -- e toda semana nao fotografada esta perdida para sempre.
#
# READ-ONLY sobre o M1: nao toca score_priorizacao, pesos, config.py, pipelines/m1
# nem artefato oficial. Escreve SO em data/staging/snapshots_concorrentes/.
#
# ---------------------------------------------------------------------------
# POR QUE `--fontes unidades` E NAO OS TRES FEEDS  (decisao de 2026-08-11)
#
# O cron semanal (`run_weekly_90.sh`, dom 06:00 UTC) recoleta SO os 90 coletores,
# que atualizam `Unidades/unidades_<rede>.csv`. WellHub e TotalPass dependem de um
# cron mensal que AINDA NAO EXISTE (docs/infra_producao.md, "Pendentes").
#
# Fotografar um feed que nao foi recoletado e' pior que nao fotografar: o
# `hash_campos_raspados` sai identico semana apos semana, `semanas_sem_mudanca`
# cresce sozinho, e o S4 marca o universo INTEIRO daquela fonte como "parado" --
# que e' exatamente o sinal de vulnerabilidade que alimenta o funil de M&A. Falso
# positivo em massa, no sinal de segundo maior peso, e silencioso.
#
# Quando o cron mensal dos agregadores existir, ele invoca este mesmo script com
# `--fontes totalpass wellhub` (ou os tres), na SUA cadencia.
#
# ---------------------------------------------------------------------------
# ANTES DE LIGAR NO CRON: rode o modo seco e confira o caminho dos CSVs.
#
# Este script NAO consegue adivinhar onde os CSVs de concorrentes moram na VPS --
# o layout nao esta versionado. `--dry-run` roda a cadeia inteira sem gravar e SEM
# PODAR, e imprime a auditoria: se `linhas_snapshot` vier 0, o caminho esta errado.
#
#     DRY_RUN=1 /opt/motor-expansao-infra/run_snapshot_concorrentes.sh
#
# So' depois de ver contagem plausivel, agende. O passo entra no
# `run_weekly_90.sh` DEPOIS da coleta (passo 2) e pode ficar junto do regen
# (passo 4) -- a ordem entre eles e' indiferente, porque o snapshot le os CSVs e
# o regen le/escreve a camada de mercado.
#
# INSTALACAO (uma vez):
#     cp scripts/cron/run_snapshot_concorrentes.sh /opt/motor-expansao-infra/
#     chmod +x /opt/motor-expansao-infra/run_snapshot_concorrentes.sh
#     # e uma linha no /opt/gymscraping-infra/run_weekly_90.sh, apos a coleta:
#     /opt/motor-expansao-infra/run_snapshot_concorrentes.sh || echo "snapshot falhou (nao aborta o lote)"
#
# O `|| echo` e' deliberado: uma falha no snapshot NAO pode abortar a coleta nem o
# regen, no mesmo espirito do "falhas individuais de coletor nao abortam o lote".
# ============================================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/motor-expansao/app}"
HOST_STAGING="${HOST_STAGING:-/opt/motor-expansao/data/staging}"
# Raiz que contem `Unidades/`, `wellhub/csvs/` e `totalpass/csvs/`. CONFIRA com --dry-run.
HOST_CONCORRENTES="${HOST_CONCORRENTES:-/opt/motor-expansao/data/concorrentes}"
FONTES="${FONTES:-unidades}"
LOG_DIR="${LOG_DIR:-/var/log/motor-snapshots}"
DRY_RUN="${DRY_RUN:-0}"

TS="$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR"
LOG="${LOG_DIR}/snapshot_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

echo ">> [$(date -u +%FT%TZ)] snapshot de concorrentes - inicio (fontes=${FONTES}, dry_run=${DRY_RUN})"

[ -d "$HOST_CONCORRENTES" ] || { echo "!! diretorio de concorrentes ausente: $HOST_CONCORRENTES"; exit 1; }

# Imagem da API pinada por digest no .env do compose (ja carrega o motor completo).
API_IMAGE="$(grep -E '^API_IMAGE=' "${APP_DIR}/.env" | head -1 | cut -d= -f2-)"
[ -n "$API_IMAGE" ] || { echo "!! API_IMAGE nao encontrado em ${APP_DIR}/.env"; exit 1; }

ARGS=(--fontes ${FONTES})
if [ "$DRY_RUN" = "1" ]; then
  ARGS+=(--dry-run)
  MOUNT_STAGING="${HOST_STAGING}:/app/data/staging:ro"   # modo seco nem monta RW
else
  MOUNT_STAGING="${HOST_STAGING}:/app/data/staging"
fi

# `--user 0:0` pelo mesmo motivo dos outros one-shots: staging/CSVs do host sao
# root:root e a imagem roda como appuser(1000) -> sem root, PermissionError.
# Concorrentes montado :ro -- este passo LE os CSVs, nunca os altera.
docker run --rm \
  --user 0:0 \
  -v "$MOUNT_STAGING" \
  -v "${HOST_CONCORRENTES}:/app/concorrentes:ro" \
  "$API_IMAGE" \
  python -m motor_expansao.vulnerabilidade.snapshots "${ARGS[@]}"

if [ "$DRY_RUN" = "1" ]; then
  echo '>> DRY-RUN: nada gravado, nenhuma semana podada. Confira linhas_snapshot acima.'
else
  echo ">> particoes em ${HOST_STAGING}/snapshots_concorrentes/"
  ls -la "${HOST_STAGING}/snapshots_concorrentes/" 2>/dev/null || echo "   (primeira execucao?)"
fi

echo ">> [$(date -u +%FT%TZ)] snapshot de concorrentes - OK"
ln -sfn "$LOG" "${LOG_DIR}/snapshot_latest.log"
