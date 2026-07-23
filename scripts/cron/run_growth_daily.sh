#!/usr/bin/env bash
# ============================================================================
# Ingestao DIARIA da Growth API -> data/staging/growth_api_historico.parquet
# (alimenta a Visao Executiva do piloto web; os dados atualizam TODO DIA).
#
# Padrao espelhado do GymScraping (docs/infra_producao.md, DEC-013): infra na VPS,
# roda a ingestao e reinicia o web (que cacheia o parquet via lru_cache).
#
# DESENHO (menos invasivo, sem tocar na API viva): a ingestao roda num container
# EFEMERO (`docker run --rm`) usando a MESMA imagem da API (que ja tem o motor +
# scripts/ingerir_growth_api.py), com as credenciais isoladas num env-file
# root-only e o staging do HOST montado READ-WRITE (so este one-shot escreve).
# Assim NENHUM segredo mora no container de longa duracao e a API/bot nao reinicia.
#
# ---------------------------------------------------------------------------
# PRE-REQUISITO (uma vez): o arquivo de credenciais em $GROWTH_ENV com as 2 linhas
#       GROWTH_API_USUARIO=...
#       GROWTH_API_SENHA=...
#   (chmod 600, root-only; NUNCA entra no repo). Sem ele a ingestao aborta com
#   "Credenciais ausentes".
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
GROWTH_ENV="${GROWTH_ENV:-/opt/motor-expansao-infra/growth.env}"
WEB_CONTAINER="${WEB_CONTAINER:-motor_expansao_web}"
LOG_DIR="${LOG_DIR:-/var/log/growth}"

TS="$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR"
LOG="${LOG_DIR}/daily_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

echo ">> [$(date -u +%FT%TZ)] Growth diario - inicio"

[ -f "$GROWTH_ENV" ] || { echo "!! credenciais ausentes em $GROWTH_ENV"; exit 1; }

# Imagem da API pinada por digest no .env do compose (mesma que ja tem motor + scripts).
API_IMAGE="$(grep -E '^API_IMAGE=' "${APP_DIR}/.env" | head -1 | cut -d= -f2-)"
[ -n "$API_IMAGE" ] || { echo "!! API_IMAGE nao encontrado em ${APP_DIR}/.env"; exit 1; }

# 1) Ingestao num container efemero. Staging do HOST montado RW: le o perf parquet
#    (insumo obrigatorio) e escreve growth_api_historico.parquet no caminho DEFAULT
#    (config.STAGING_DIR = data/staging, relativo ao CWD /app da imagem) -> cai direto
#    no staging do host. (Nao usa --out: a imagem da API em prod pode ser anterior a
#    essa flag; o mount RW no default ja resolve.)
docker run --rm \
  --env-file "$GROWTH_ENV" \
  -v "${HOST_STAGING}:/app/data/staging" \
  "$API_IMAGE" \
  python scripts/ingerir_growth_api.py

echo ">> parquet publicado em ${HOST_STAGING}/growth_api_historico.parquet"
ls -la "${HOST_STAGING}/growth_api_historico.parquet"

# 2) Restart do web p/ limpar o lru_cache de _carregar_growth e servir o dado novo.
docker restart "$WEB_CONTAINER" >/dev/null
echo ">> ${WEB_CONTAINER} reiniciado (cache do growth invalidado)"

echo ">> [$(date -u +%FT%TZ)] Growth diario - OK"
ln -sfn "$LOG" "${LOG_DIR}/daily_latest.log"
