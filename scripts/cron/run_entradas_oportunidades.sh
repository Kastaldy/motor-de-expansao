#!/usr/bin/env bash
# ============================================================================
# Entradas do MODELO DE PRACA por imovel da aba de oportunidades (DEC-086)
#     viaveis.parquet -> isocrona de 10 min (Valhalla) + malha de setores ->
#     pop_c10 / dom_c10 / renda_pc_c10 por coordenada -> entradas_c10.parquet
#
# O site aplica o modelo de praca (o mesmo do simulador) na leitura da lista; sem a
# entrada do imovel, ele cai na curva de densidade. Este job so' calcula as entradas
# que FALTAM (incremental pela coordenada em 5 casas): a 1a rodada leva ~1,2 h
# (8.010 coordenadas x 0,54 s, medido em 13/11/2026), as seguintes so' os imoveis
# novos de cada envio da lista. READ-ONLY sobre o M1 e sobre o `viaveis.parquet`:
# escreve SO' `data/oportunidades/entradas_c10.parquet`, por temporario + rename.
#
# SEM RESTART: o site compara mtime e tamanho da lista e das entradas a cada leitura
# (`_carregar_oportunidades`) e remonta sozinho quando o arquivo muda.
#
# Roda no container do SITE (`docker compose run ... web`): e' ele que tem o
# `MOTOR_ROTAS_URL`, a malha de setores e o perfil montados, e a mesma imagem que
# serve a tela -- o calculo e' o da sugestao da Viabilidade, byte a byte. A pasta da
# lista entra uma 2a vez, GRAVAVEL, em /oportunidades-rw; `-u 0:0` porque ela e' do
# root (grupo motor-ops) e o container do site roda como `appuser`.
#
# GUARDRAIL (o mesmo dos outros crons): nunca copia nada entre maquinas, nunca abre
# sessao remota, nunca faz deploy. Instalar e agendar e' passo MANUAL (CLAUDE.md §6).
#
# ---------------------------------------------------------------------------
# CODIGOS DO JOB (o wrapper repassa)
#   0  ok (inclusive "nada novo": o arquivo nao e' regravado)
#   2  lista ausente ou sem latitude/longitude: nada gravado
#   3  servico de rotas fora: o lote PAROU, o que ja' foi calculado ficou salvo e o
#      resto volta na proxima noite
#
# ANTES DE AGENDAR, o modo seco: calcula 5 pontos e grava SO' dentro do container
# descartavel (/tmp), sem tocar a pasta da lista e sem Telegram:
#     DRY_RUN=1 /opt/motor-expansao-infra/run_entradas_oportunidades.sh
#
# INSTALACAO (uma vez). O checkout da VPS (/opt/motor-expansao/app) esta parado e NAO
# tem este script: ele vai da estacao para a home da conta deploy, e o root instala:
#     (estacao) scp -i ~/.ssh/id_ultra_deploy scripts/cron/run_entradas_oportunidades.sh deploy@<vps>:
#     (root)    install -m 0755 -o root -g root /home/deploy/run_entradas_oportunidades.sh /opt/motor-expansao-infra/run_entradas_oportunidades.sh
#     (root)    sha256sum /opt/motor-expansao-infra/run_entradas_oportunidades.sh   # o mesmo da main
#
# LINHA DE CRONTAB (todo dia, 04:15 UTC = 01:15 BRT):
#     15 4 * * * /opt/motor-expansao-infra/run_entradas_oportunidades.sh
#
# Por que diario e de madrugada: a lista chega por envio manual, sem dia fixo; rodar
# toda noite pega o envio do dia, e sem imovel novo o job sai em segundos. Madrugada
# porque o Valhalla tem 1 CPU, e fora da janela de domingo (06:00 UTC).
# ============================================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/motor-expansao/app}"
COMPOSE_FILE="${COMPOSE_FILE:-${APP_DIR}/docker-compose.prod.yml}"
HOST_OPORT="${HOST_OPORT:-/opt/motor-expansao/data/oportunidades}"
LOG_DIR="${LOG_DIR:-/var/log/motor-snapshots}"
LOCK_FILE="${LOCK_FILE:-/var/lock/motor-entradas-oportunidades.lock}"
DRY_RUN="${DRY_RUN:-0}"

# LOG ANTES DO LOCK (molde dos outros crons): uma rodada travada deixaria as
# seguintes sairem com exit 0 e nenhum arquivo de log.
TS="$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR"
LOG="${LOG_DIR}/entradas_oportunidades_${TS}.log"
exec > >(tee -a "$LOG") 2>&1
ln -sfn "$LOG" "${LOG_DIR}/entradas_oportunidades_latest.log"

exec 9>"$LOCK_FILE"
flock -n 9 || { echo ">> ja rodando (lock $LOCK_FILE); saindo"; exit 0; }

echo ">> [$(date -u +%FT%TZ)] entradas do modelo de praca - inicio (dry_run=${DRY_RUN})"

# A variavel do SHELL vence o `.env` na interpolacao do compose (docs/banco_deploy.md):
# este job nao usa o banco, mas o container do site nao pode subir com uma URL errada.
unset MOTOR_DATABASE_URL MOTOR_DATABASE_URL_AR

# Le VAR=valor do .env do compose (o mesmo `_env_do_compose` dos outros crons).
_env_do_compose() {
  local valor
  valor="$(grep -E "^${1}=" "${APP_DIR}/.env" | head -1 | cut -d= -f2- | tr -d '\r' || true)"
  valor="${valor%\"}"; valor="${valor#\"}"
  valor="${valor%\'}"; valor="${valor#\'}"
  printf '%s' "$valor"
}

WEB_IMAGE="$(_env_do_compose WEB_IMAGE)"
API_IMAGE="$(_env_do_compose API_IMAGE)"
[ -n "$WEB_IMAGE" ] || { echo "!! WEB_IMAGE nao encontrado em ${APP_DIR}/.env"; exit 1; }
echo ">> WEB_IMAGE=${WEB_IMAGE}"

API_TELEGRAM_TOKEN="$(_env_do_compose API_TELEGRAM_TOKEN)"
MONITOR_TELEGRAM_CHAT_ID="$(_env_do_compose MONITOR_TELEGRAM_CHAT_ID)"
export API_TELEGRAM_TOKEN MONITOR_TELEGRAM_CHAT_ID
if [ "$DRY_RUN" != "1" ] && { [ -z "$API_TELEGRAM_TOKEN" ] || [ -z "$MONITOR_TELEGRAM_CHAT_ID" ] || [ -z "$API_IMAGE" ]; }; then
  echo "!! AVISO: API_TELEGRAM_TOKEN/MONITOR_TELEGRAM_CHAT_ID/API_IMAGE ausentes no .env — a rodada segue, mas NENHUM aviso chegara ao chat de ops"
fi

# Aviso ao chat de ops pelo MESMO enviador dos outros crons (`crescimento.aviso`): le
# token e chat do AMBIENTE, texto por STDIN. So' na rodada real.
_avisar() {
  if [ "$DRY_RUN" = "1" ]; then
    echo ">> DRY-RUN: aviso que SERIA enviado ao chat de ops:"
    cat
    return 0
  fi
  [ -n "$API_IMAGE" ] || { echo "!! sem API_IMAGE: aviso nao enviado"; cat >/dev/null; return 0; }
  docker run --rm -i -e API_TELEGRAM_TOKEN -e MONITOR_TELEGRAM_CHAT_ID "$API_IMAGE" \
    python -c 'import sys; from motor_expansao.crescimento.aviso import enviar; enviar(sys.stdin.read())' \
    || echo "!! aviso nao foi enviado ao chat de ops"
}

# --------------------------------------------------------------------------
# Pre-checagens que abortam CEDO, com mensagem acionavel.
# --------------------------------------------------------------------------
[ -f "${HOST_OPORT}/viaveis.parquet" ] || { echo "!! lista de imoveis ausente: ${HOST_OPORT}/viaveis.parquet"; exit 1; }
[ -n "$(_env_do_compose MOTOR_ROTAS_URL)" ] || { echo "!! MOTOR_ROTAS_URL vazio no .env: sem Valhalla nao ha isocrona"; exit 1; }
docker image inspect "$WEB_IMAGE" >/dev/null 2>&1 || { echo "!! imagem ${WEB_IMAGE} ausente"; exit 1; }
docker compose -f "$COMPOSE_FILE" run --rm --no-deps -T web \
  python -c "import motor_expansao.dimensionamento.entradas_oportunidades" >/dev/null 2>&1 \
  || { echo "!! a imagem do site nao tem o modulo das entradas — aplique a imagem nova antes de agendar"; exit 1; }

# --------------------------------------------------------------------------
# Passo 1 - JOB (incremental; grava por temporario + rename a cada 500 pontos)
# --------------------------------------------------------------------------
if [ "$DRY_RUN" = "1" ]; then
  # Modo seco: a pasta da lista NAO entra gravavel; a saida fica no /tmp do container.
  MONTAGEM=()
  JOB_ARGS=(--oportunidades /app/data/oportunidades/viaveis.parquet
            --saida /tmp/entradas_c10_seco.parquet --limite 5)
else
  MONTAGEM=(-u 0:0 -v "${HOST_OPORT}:/oportunidades-rw")
  JOB_ARGS=(--oportunidades /oportunidades-rw/viaveis.parquet
            --saida /oportunidades-rw/entradas_c10.parquet)
fi

echo ">> [$(date -u +%FT%TZ)] passo 1 - calculo das entradas que faltam"
set +e
# `${A[@]+"${A[@]}"}`: o array vazio do modo seco nao derruba o `set -u` (bash < 4.4).
docker compose -f "$COMPOSE_FILE" run --rm --no-deps -T ${MONTAGEM[@]+"${MONTAGEM[@]}"} \
  -e PYTHONIOENCODING=utf-8 \
  web python -m motor_expansao.dimensionamento.entradas_oportunidades "${JOB_ARGS[@]}"
JOB_RC=$?
set -e

case "$JOB_RC" in
  0)
    echo ">> [$(date -u +%FT%TZ)] entradas do modelo de praca - OK"
    ;;
  3)
    _avisar <<EOF
⚠️ [Motor] Entradas do modelo de praça: o serviço de rotas (Valhalla) não respondeu e o lote PAROU.
O que já foi calculado ficou salvo; os imóveis que faltam seguem na curva de densidade e entram na próxima noite.
Log: ${LOG}
EOF
    exit 3
    ;;
  *)
    _avisar <<EOF
🔴 [Motor] Entradas do modelo de praça FALHARAM (rc=${JOB_RC}).
Nada novo foi publicado; a aba de imóveis segue com as entradas anteriores (e a curva de densidade onde faltam).
Log: ${LOG}
EOF
    exit "$JOB_RC"
    ;;
esac
