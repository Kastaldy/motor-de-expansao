#!/usr/bin/env bash
# ============================================================================
# Ingestao DIARIA da Growth API -> data/staging/growth_api_historico.parquet
# (alimenta a Visao Executiva do piloto web; os dados atualizam TODO DIA).
#
# Padrao espelhado do GymScraping (docs/infra_producao.md, DEC-013): infra na VPS,
# roda a ingestao num container que JA tem o motor + as credenciais, deposita o
# parquet no staging do HOST e reinicia o web (que cacheia o parquet via lru_cache).
#
# POR QUE `docker cp` e nao escrita direta: os containers montam
# /opt/motor-expansao/data/staging como READ-ONLY (:ro) -> a ingestao escreve num
# caminho gravavel do container (--out /tmp/...) e ESTE script copia para o staging
# do host, exatamente como os uplifts foram por scp no ciclo de renda domiciliar.
#
# ---------------------------------------------------------------------------
# PRE-REQUISITO (uma vez, MANUAL do Felipe -- envolve SEGREDO):
#   O container `motor_expansao_api` HOJE NAO tem GROWTH_API_USUARIO/GROWTH_API_SENHA
#   no ambiente (verificado 2026-07-23) -> a ingestao aborta com "Credenciais
#   ausentes". Adicionar ao /opt/motor-expansao/app/.env:
#       GROWTH_API_USUARIO=...
#       GROWTH_API_SENHA=...
#   e recriar o servico api:  cd /opt/motor-expansao/app && docker compose up -d api
#   (a chave NUNCA entra neste script nem no repo).
#
# INSTALACAO (uma vez): copie este script para a VPS e agende no cron do root
#   (servidor em UTC; 06:30 UTC = 03:30 BRT, evita a janela dom 06:00 do GymScraping):
#       cp scripts/cron/run_growth_daily.sh /opt/motor-expansao-infra/run_growth_daily.sh
#       chmod +x /opt/motor-expansao-infra/run_growth_daily.sh
#       ( crontab -l 2>/dev/null; echo '30 6 * * * /opt/motor-expansao-infra/run_growth_daily.sh >> /var/log/growth/cron.log 2>&1' ) | crontab -
# ============================================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/motor-expansao/app}"
HOST_STAGING="${HOST_STAGING:-/opt/motor-expansao/data/staging}"
API_CONTAINER="${API_CONTAINER:-motor_expansao_api}"
WEB_CONTAINER="${WEB_CONTAINER:-motor_expansao_web}"
LOG_DIR="${LOG_DIR:-/var/log/growth}"
TMP_IN_CONTAINER="/tmp/growth_api_historico.parquet"
OUT_PARQUET="${HOST_STAGING}/growth_api_historico.parquet"

TS="$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR"
LOG="${LOG_DIR}/daily_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

echo ">> [$(date -u +%FT%TZ)] Growth diario - inicio"

# 1) Ingestao dentro do container api (motor + creds via .env do compose). Escreve
#    num caminho GRAVAVEL do container (o staging montado e :ro).
docker exec "$API_CONTAINER" python scripts/ingerir_growth_api.py --out "$TMP_IN_CONTAINER"

# 2) Copia o parquet para o staging do HOST (read-write no host; visivel ao web/api).
docker cp "${API_CONTAINER}:${TMP_IN_CONTAINER}" "$OUT_PARQUET"
docker exec "$API_CONTAINER" rm -f "$TMP_IN_CONTAINER" || true
echo ">> parquet publicado em ${OUT_PARQUET}"
ls -la "$OUT_PARQUET"

# 3) Restart do web para limpar o lru_cache de _carregar_growth e servir o dado novo.
docker restart "$WEB_CONTAINER" >/dev/null
echo ">> ${WEB_CONTAINER} reiniciado (cache do growth invalidado)"

echo ">> [$(date -u +%FT%TZ)] Growth diario - OK"
ln -sfn "$LOG" "${LOG_DIR}/daily_latest.log"
