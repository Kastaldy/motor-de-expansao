#!/usr/bin/env bash
# ============================================================================
# Alerta de borda — varreduras COM ASSINATURA contra os hosts do piloto.
# (pedido do Felipe, 2026-09-23, depois da investigacao do "login desconhecido")
#
# O que envia: o agregado por IP das requisicoes que pediram caminho sem leitura
# inocente neste servidor (.env, .git, wp-*, xmlrpc, phpmyadmin, id_rsa, .sql,
# .php), do dia BRT ANTERIOR — janela ja fechada, o que dispensa guardar estado
# do que ja foi alertado. Gerador unico: motor_expansao/api/alerta_borda.py.
#
# `--so-notavel` e o coracao da instalacao, nao um detalhe: sondagem de fundo
# existe TODO dia (23 dos 36 dias medidos), e enviar todas faria o alerta falar
# em 2 de cada 3 dias ate' ninguem mais ler. So' sai mensagem quando o dia cruza
# um limiar (>= 5 IPs, >= 20 requisicoes) ou quando alguma sondagem foi ATENDIDA
# com 2xx — esta ultima sozinha, sem limiar. Medido: 0,28 mensagem/dia.
#
# Padrao espelhado do run_relatorio_acessos.sh: container EFEMERO com a imagem da
# API, log do Caddy montado READ-ONLY, credenciais do .env do compose EXPORTADAS
# no ambiente e repassadas por `-e NOME` SEM valor — o token nunca aparece no
# argv do docker (visivel em `ps`).
#
# INSTALACAO (uma vez, SO DEPOIS do deploy da imagem com o modulo — imagem antiga
# nao tem `alerta_borda` e o run falharia todo dia):
#   cp scripts/cron/run_alerta_borda.sh /opt/motor-expansao-infra/run_alerta_borda.sh
#   chmod +x /opt/motor-expansao-infra/run_alerta_borda.sh
#   install -m 600 /dev/null /var/log/motor-monitoring/alerta_borda.log
#   # smoke de LEITURA antes de deixar qualquer mensagem sair (sem --enviar):
#   docker run --rm --user 0:0 -v /opt/motor-expansao/logs/caddy:/var/log/caddy:ro \
#     "$API_IMAGE" python -m motor_expansao.api.alerta_borda --dir /var/log/caddy --dia AAAA-MM-DD
#   /opt/motor-expansao-infra/run_alerta_borda.sh   # 1o run de verdade (envia ou pula)
#   ( crontab -l 2>/dev/null; echo '23 8 * * * /opt/motor-expansao-infra/run_alerta_borda.sh >> /var/log/motor-monitoring/alerta_borda.log 2>&1' ) | crontab -
#   # 08:23 UTC = 05:23 BRT: o dia BRT anterior ja fechou ha 5h, e a mensagem
#   # chega antes do expediente. Servidor em UTC.
# ============================================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/motor-expansao/app}"
HOST_CADDY_LOG="${HOST_CADDY_LOG:-/opt/motor-expansao/logs/caddy}"
LOG_CRON="${LOG_CRON:-/var/log/motor-monitoring/alerta_borda.log}"

# O log do cron carrega IP de terceiro: nao cresce sem teto — acima de 512 KiB,
# recomeca (o conteudo relevante e sempre o run mais recente).
if [ -f "$LOG_CRON" ] && [ "$(stat -c%s "$LOG_CRON" 2>/dev/null || echo 0)" -gt 524288 ]; then
  : > "$LOG_CRON"
fi

echo ">> [$(date -u +%FT%TZ)] alerta de borda - inicio"

# Le VAR=valor do .env do compose, tirando aspas e CR. `|| true`: sob `set -e`,
# um grep sem match abortaria antes das mensagens de erro logo abaixo.
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
if ! docker run --rm "$API_IMAGE" python -c "import motor_expansao.api.alerta_borda" 2>/dev/null; then
  echo "!! a imagem da API nao tem o modulo alerta_borda — deploy pendente?"; exit 1
fi

# `--user 0:0` — a UNICA diferenca real contra o run_relatorio_acessos.sh, e ela
# nao e' cosmetica. A imagem roda como `appuser` (uid 1000), e os dois diretorios
# de log tem donos DIFERENTES: a trilha da DEC-027 e' `ubuntu:ubuntu 0700` (uid
# 1000 — o container le), mas o access log do Caddy e' `root:root 0700` e o
# container morria com `PermissionError: /var/log/caddy`. Espelhar o outro cron
# sem olhar o dono foi o defeito; pego no smoke de instalacao em 2026-09-23.
#
# Rodar como root aqui e' a opcao MENOS invasiva das duas: o mount e' `:ro`, o
# container e' efemero e nao ve a rede do compose. A alternativa seria afrouxar a
# permissao do diretorio no HOST — e esse log guarda IP de terceiro, e' root-only
# por desenho, e o relaxamento valeria para todo processo da maquina, nao so'
# para este run de 2 segundos.
docker run --rm \
  --user 0:0 \
  -e API_TELEGRAM_TOKEN \
  -e MONITOR_TELEGRAM_CHAT_ID \
  -v "$HOST_CADDY_LOG":/var/log/caddy:ro \
  "$API_IMAGE" \
  python -m motor_expansao.api.alerta_borda --dir /var/log/caddy --enviar --so-notavel

echo ">> [$(date -u +%FT%TZ)] alerta de borda - fim"
