#!/usr/bin/env bash
# ============================================================================
# Expurgo da ORIGEM das sessoes: zera `ip_sessao` e `user_agent_sessao` alem do
# prazo de retencao. Fecha o P15, cujo PRAZO o dono decidiu em 23/09/2026:
# TRES MESES (90 dias).
#
# ANONIMIZA, NAO APAGA. O que tem prazo e' o dado pessoal, nao o registro da
# sessao: zeradas as duas colunas, a linha continua respondendo "entrou em tal
# dia, revogada em tal outro" -- auditoria sem PII. Apagar a linha contrariaria o
# desenho da migration 018, em que revogar e' `UPDATE` e NUNCA `DELETE` (o papel
# `app` nem tem `DELETE`).
#
# POR QUE ANTES DO BACKUP, e nao depois: o `run_backup_banco.sh` roda as 05:10
# UTC e o dump CONTEM o banco inteiro. Expurgando as 04:40, o dump do dia ja'
# nasce sem os IPs vencidos -- caso contrario a copia off-box carregaria, por ate'
# 28 dias (retencao semanal), exatamente o dado que este script existe para
# remover. A ordem entre os dois crons E' a politica de retencao; invertida, ela
# vira encenacao.
#
# POR QUE NAO TEM SQL AQUI. A consulta e o prazo vivem em
# `db/sessoes.py` (`SQL_EXPURGAR_ORIGEM`, `RETENCAO_ORIGEM_DIAS`), com teste e
# sabotagem. Repeti-los neste shell criaria duas redacoes da mesma regra -- e a
# segunda e' sempre a que esquece de ser atualizada. Este arquivo so' ORQUESTRA.
#
# A SENHA VAI FORA DA URL, de proposito: `MOTOR_DATABASE_URL_ADMIN` sai daqui SEM
# credencial e a senha viaja em `PGPASSWORD`, que a libpq le'. Isso elimina a
# necessidade de codificar `@`, `:` ou `/` na senha -- erro silencioso que custa
# uma sessao de depuracao para ser achado, porque a mensagem e' "autenticacao
# falhou" e nao "sua URL esta' malformada". Medido em 23/09/2026.
#
# INSTALACAO (uma vez, DEPOIS de as migrations 018/019/020 estarem aplicadas):
#   cp scripts/cron/run_expurgo_sessoes.sh /opt/motor-expansao-infra/run_expurgo_sessoes.sh
#   chmod +x /opt/motor-expansao-infra/run_expurgo_sessoes.sh
#   install -m 600 /dev/null /var/log/motor-monitoring/expurgo_sessoes.log
#   /opt/motor-expansao-infra/run_expurgo_sessoes.sh --simular   # smoke: nao escreve nada
#   ( crontab -l 2>/dev/null; echo '40 4 * * * /opt/motor-expansao-infra/run_expurgo_sessoes.sh >> /var/log/motor-monitoring/expurgo_sessoes.log 2>&1' ) | crontab -
#   # 04:40 UTC = 01:40 BRT: 30 min ANTES do backup (05:10), pelo motivo acima.
#
# DIARIO, e nao semanal: o custo e' uma consulta numa tabela pequena (19 pessoas),
# e diario significa que o atraso maximo entre "venceu" e "foi apagado" e' 24h em
# vez de 7 dias. Numa politica de retencao, esse atraso E' a politica.
# ============================================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/motor-expansao/app}"
LOG_CRON="${LOG_CRON:-/var/log/motor-monitoring/expurgo_sessoes.log}"
CONTAINER_PG="${PG_CONTAINER:-motor_expansao_postgres}"
COMPOSE="${COMPOSE_FILE:-docker-compose.prod.yml}"

SIMULAR=""
[ "${1:-}" = "--simular" ] && SIMULAR="--simular"

# O log do cron nao cresce sem teto (mesmo espirito do run_backup_banco.sh).
if [ -f "$LOG_CRON" ] && [ "$(stat -c%s "$LOG_CRON" 2>/dev/null || echo 0)" -gt 524288 ]; then
  : > "$LOG_CRON"
fi

# Le VAR=valor do .env do compose, tirando aspas e CR. `|| true`: sob `set -e` um
# grep sem match abortaria antes das mensagens de erro logo abaixo.
_env_do_compose() {
  local valor
  valor="$(grep -E "^${1}=" "${APP_DIR}/.env" | head -1 | cut -d= -f2- | tr -d '\r' || true)"
  valor="${valor%\"}"; valor="${valor#\"}"
  valor="${valor%\'}"; valor="${valor#\'}"
  printf '%s' "$valor"
}

echo ">> [$(date -u +%FT%TZ)] expurgo da origem das sessoes - inicio ${SIMULAR}"

cd "$APP_DIR" || { echo "!! ${APP_DIR} nao existe"; exit 1; }

POSTGRES_DB="$(_env_do_compose POSTGRES_DB)"
POSTGRES_OWNER_USER="$(_env_do_compose POSTGRES_OWNER_USER)"
PGPASSWORD="$(_env_do_compose POSTGRES_OWNER_PASSWORD)"
[ -n "$POSTGRES_DB" ] && [ -n "$POSTGRES_OWNER_USER" ] && [ -n "$PGPASSWORD" ] || {
  echo "!! POSTGRES_DB/POSTGRES_OWNER_USER/POSTGRES_OWNER_PASSWORD ausentes em ${APP_DIR}/.env"
  exit 1; }
export PGPASSWORD

# O DONO do schema, e nao o papel `app`: expurgo e' manutencao, fora do RBAC de
# usuario, e o `app` nao precisa deste poder. `postgres` e' o nome do SERVICO na
# rede do compose -- e' assim que o container efemero o alcanca.
export MOTOR_DATABASE_URL_ADMIN="postgresql://${POSTGRES_OWNER_USER}@postgres:5432/${POSTGRES_DB}"

docker ps --format '{{.Names}}' | grep -qx "$CONTAINER_PG" || {
  echo "!! container ${CONTAINER_PG} nao esta de pe — nada a fazer"; exit 1; }

# `-e VAR` SEM valor herda do ambiente: a senha nunca aparece no argv do docker,
# que e' legivel por qualquer usuario em `ps`.
# `--no-deps`: se o banco estiver fora, a falha tem de ser clara, e nao "o cron
# subiu o Postgres as 4h40 da manha".
docker compose -f "$COMPOSE" run --rm --no-deps \
  -e MOTOR_DATABASE_URL_ADMIN -e PGPASSWORD \
  web python -m motor_expansao.db expurgar ${SIMULAR}

echo "<< [$(date -u +%FT%TZ)] expurgo da origem das sessoes - fim"
