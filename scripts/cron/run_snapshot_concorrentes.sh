#!/usr/bin/env bash
# ============================================================================
# Snapshot SEMANAL de concorrentes -> data/staging/snapshots_concorrentes/
#     semana=AAAA-SS/fonte=<fonte>/parte-*.parquet
#
# E' o passo do BLK-MA-06: fotografa o feed de concorrentes ANTES de a coleta da
# semana seguinte sobrescrever os CSVs crus. Sem ele, S3 (churn) e S4 (staleness)
# nunca tem serie -- e toda semana nao fotografada esta perdida para sempre.
#
# ATENCAO -- a particao tem DUAS chaves desde o BLK-MA-21 / DEC-038. Se este script
# rodar numa IMAGEM ANTIGA (que escreve so' `semana=`), ele APAGA a folha gravada
# pela cadencia mensal na mesma semana ISO. Antes de instalar, confira na saida do
# `DRY_RUN=1` que `versao_contrato` e' `snapshots_concorrentes_v4`; com `v3`, NAO
# agende -- aplique a imagem nova primeiro (ordem de 6 passos em
# docs/infra_producao.md, "Coleta mensal dos agregadores").
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
# O CRON MENSAL DOS AGREGADORES **NAO** PASSA POR AQUI (BLK-MA-21 / DEC-038).
#
# Esta linha dizia, ate' 2026-08-25, que a cadencia mensal invocaria "este mesmo
# script com `--fontes totalpass wellhub`". Seguir a instrucao PULARIA a curadoria
# inteira: a escolha do diretorio de origem do WellHub (dois universos que diferem
# por 2-3x) e a guarda de frescor -- que sao a razao de o bloco existir. O mensal
# tem wrapper proprio, `scripts/cron/run_snapshot_agregadores.sh`, que faz coleta +
# curadoria + snapshot sob um `flock` so'.
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
#     install -d -m 0755 /opt/motor-expansao-infra     # idempotente; nada no repo cria este dir
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
#
# `/opt/gymscraping` e' o CLONE do repo de coleta (docs/infra_producao.md, secao do GymScraping):
# e' la' que existe `Unidades/unidades_<rede>.csv`, que e' o que o glob do snapshot procura
# (`concorrentes/Unidades/*.csv`, relativo ao mount `/app/concorrentes`).
#
# O default anterior era `/opt/motor-expansao/data/concorrentes`, que NAO EXISTE na VPS -- o script
# abortava na checagem logo abaixo. E o palpite seguinte, `/opt/motor-expansao/concorrentes`, e' uma
# armadilha pior: ele existe, mas guarda os CSVs ACHATADOS (o sync copia
# `/opt/gymscraping/Unidades/unidades_<slug>.csv` direto para a raiz, sem o subdiretorio), entao o
# glob nao casa com nada e o dry-run devolve `linhas_snapshot = 0` SEM erro nenhum -- que le como
# "nao ha dado" em vez de "caminho errado".
HOST_CONCORRENTES="${HOST_CONCORRENTES:-/opt/gymscraping}"
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
#
# `tr -d '\r'` NAO e' paranoia: o `.env` da VPS chegou por rsync de uma maquina Windows, entao
# pode ter CRLF. Sem isso o `\r` final entra no nome da imagem e o `docker run` morre com
# "invalid reference format" -- mensagem que aponta para o lugar errado (parece digest torto).
# Mesmo tratamento que `run_relatorio_acessos.sh:44` ja fazia; este script tinha ficado de fora.
# As aspas tambem sao removidas: `API_IMAGE="ghcr.io/..."` e' forma valida de .env.
API_IMAGE="$(grep -E '^API_IMAGE=' "${APP_DIR}/.env" | head -1 | cut -d= -f2- | tr -d '\r' || true)"
API_IMAGE="${API_IMAGE%\"}"; API_IMAGE="${API_IMAGE#\"}"
API_IMAGE="${API_IMAGE%\'}"; API_IMAGE="${API_IMAGE#\'}"
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
