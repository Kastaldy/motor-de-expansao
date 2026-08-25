#!/usr/bin/env bash
# ============================================================================
# Relatorio de acessos do piloto -> chat de alertas do Telegram, a cada 3h.
# (pedido do Felipe, 2026-08-18: "rodar automaticamente em 3/3h nos alertas")
#
# O que envia: o AGREGADO por usuario do dia BRT (quem, janela, abas) a partir da
# trilha de acesso da DEC-027 — nunca rota/detalhe. Mesmo texto do comando
# /acessos do bot; gerador unico: motor_expansao/api/relatorio_acessos.py.
# Relatorio VAZIO nao e enviado (--pular-vazio): evita ruido de madrugada.
#
# Padrao espelhado do run_growth_daily.sh: container EFEMERO com a imagem da API
# (que ja contem o modulo), trilha do host montada READ-ONLY, credenciais do .env
# do compose EXPORTADAS no ambiente e repassadas por `-e NOME` SEM valor — o token
# nunca aparece no argv do docker (visivel em `ps`); /proc/PID/environ e root-only.
#
# INSTALACAO (uma vez, SO DEPOIS do deploy da imagem com o modulo — imagem antiga
# nao tem `relatorio_acessos` e o run falharia a cada 3h):
#   cp scripts/cron/run_relatorio_acessos.sh /opt/motor-expansao-infra/run_relatorio_acessos.sh
#   chmod +x /opt/motor-expansao-infra/run_relatorio_acessos.sh
#   install -m 600 /dev/null /var/log/motor-monitoring/relatorio_acessos.log
#   /opt/motor-expansao-infra/run_relatorio_acessos.sh   # smoke: tem de ENVIAR (ou pular por vazio)
#   ( crontab -l 2>/dev/null; echo '7 */3 * * * /opt/motor-expansao-infra/run_relatorio_acessos.sh >> /var/log/motor-monitoring/relatorio_acessos.log 2>&1' ) | crontab -
#   # 7 */3 = a cada 3h no minuto 7 (fora do pico dos :00); servidor em UTC.
# ============================================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/motor-expansao/app}"
HOST_TRILHA="${HOST_TRILHA:-/opt/motor-expansao/logs/acesso}"
LOG_CRON="${LOG_CRON:-/var/log/motor-monitoring/relatorio_acessos.log}"

# O relatorio contem dado pessoal (logins): o log do cron nao cresce sem teto —
# acima de 512 KiB, recomeca (o conteudo relevante e sempre o run mais recente).
if [ -f "$LOG_CRON" ] && [ "$(stat -c%s "$LOG_CRON" 2>/dev/null || echo 0)" -gt 524288 ]; then
  : > "$LOG_CRON"
fi

echo ">> [$(date -u +%FT%TZ)] relatorio de acessos - inicio"

# Le VAR=valor do .env do compose, tirando aspas e CR (mesmo espirito do
# get_env_var do healthcheck_vps.sh). `|| true`: sob `set -e`, um grep sem match
# abortaria o script ANTES das mensagens de erro logo abaixo (codigo morto —
# defeito pego na revisao adversarial).
_env_do_compose() {
  local valor
  valor="$(grep -E "^${1}=" "${APP_DIR}/.env" | head -1 | cut -d= -f2- | tr -d '\r' || true)"
  valor="${valor%\"}"; valor="${valor#\"}"
  valor="${valor%\'}"; valor="${valor#\'}"
  printf '%s' "$valor"
}

API_IMAGE="$(_env_do_compose API_IMAGE)"
[ -n "$API_IMAGE" ] || { echo "!! API_IMAGE nao encontrado em ${APP_DIR}/.env"; exit 1; }

API_TELEGRAM_TOKEN="$(_env_do_compose API_TELEGRAM_TOKEN)"
MONITOR_TELEGRAM_CHAT_ID="$(_env_do_compose MONITOR_TELEGRAM_CHAT_ID)"
[ -n "$API_TELEGRAM_TOKEN" ] && [ -n "$MONITOR_TELEGRAM_CHAT_ID" ] || {
  echo "!! API_TELEGRAM_TOKEN/MONITOR_TELEGRAM_CHAT_ID ausentes no .env"; exit 1; }
export API_TELEGRAM_TOKEN MONITOR_TELEGRAM_CHAT_ID

# Guarda de imagem antiga (sem o modulo): mensagem clara em vez de falha criptica.
if ! docker run --rm "$API_IMAGE" python -c "import motor_expansao.api.relatorio_acessos" 2>/dev/null; then
  echo "!! a imagem da API nao tem o modulo relatorio_acessos — deploy pendente?"; exit 1
fi

# Container efemero: so leitura da trilha; credenciais herdadas do ambiente
# (`-e NOME` sem valor); sem rede do compose (sendMessage vai direto ao Telegram).
docker run --rm \
  -e API_TELEGRAM_TOKEN \
  -e MONITOR_TELEGRAM_CHAT_ID \
  -v "$HOST_TRILHA":/app/logs/acesso:ro \
  "$API_IMAGE" \
  python -m motor_expansao.api.relatorio_acessos --dir /app/logs/acesso --enviar --pular-vazio

echo ">> [$(date -u +%FT%TZ)] relatorio de acessos - fim"
