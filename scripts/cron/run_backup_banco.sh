#!/usr/bin/env bash
# ============================================================================
# Backup do PostgreSQL/PostGIS -> disco da VPS + copia off-box cifrada (restic).
# Reabre o BLK-SEC-04, cujo gatilho declarado e "crescimento material dos dados
# nao-regeneraveis": RBAC, eventos, areas de estudo e contratos nascem no app e
# NENHUM pipeline os regenera. O snapshot semanal da Hostinger sozinho significa
# ate uma semana de trabalho do time perdida, com restore tudo-ou-nada.
#
# Formato `-Fc` (custom) de proposito, e nao SQL puro: e' o que permite
# `pg_restore -t eventos` — restaurar UMA tabela sem derrubar o resto. Foi
# exatamente o "restore granular" que a resolucao de 13/07 listou como gap aceito.
#
# O dump CONTEM DADO PESSOAL: e-mail, login, `senha_hash` e o `ip` dos eventos
# (cuja base legal e prazo seguem abertos no P15). Por isso a copia off-box e'
# restic e nao rclone: restic cifra ANTES de sair da maquina, com chave que o
# provedor do bucket nao tem. Nao troque por sync de arquivo cru.
#
# INSTALACAO (uma vez, DEPOIS de o servico `postgres` estar de pe):
#   cp scripts/cron/run_backup_banco.sh /opt/motor-expansao-infra/run_backup_banco.sh
#   chmod +x /opt/motor-expansao-infra/run_backup_banco.sh
#   install -d -m 700 /opt/motor-expansao/backups/banco
#   install -m 600 /dev/null /var/log/motor-monitoring/backup_banco.log
#   /opt/motor-expansao-infra/run_backup_banco.sh    # smoke: tem de gerar dump + checksum
#   ( crontab -l 2>/dev/null; echo '10 5 * * * /opt/motor-expansao-infra/run_backup_banco.sh >> /var/log/motor-monitoring/backup_banco.log 2>&1' ) | crontab -
#   # 05:10 UTC = 02:10 BRT: dentro da janela 2h-5h BRT do BLK-SEC-04 e 50 min
#   # ANTES da coleta de domingo (06:00 UTC), que e' o outro consumidor de I/O.
#
# RESTORE: docs/banco_deploy.md, secao "Restaurar". Backup que ninguem restaurou
# e' backup que ninguem tem — o teste em base limpa faz parte do aceite.
# ============================================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/motor-expansao/app}"
DEST_DIR="${BACKUP_DIR:-/opt/motor-expansao/backups/banco}"
LOG_CRON="${LOG_CRON:-/var/log/motor-monitoring/backup_banco.log}"
CONTAINER="${PG_CONTAINER:-motor_expansao_postgres}"

# Retencao. Diarios cobrem o erro de ontem; semanais cobrem o erro que ninguem viu
# por tres semanas. Os numeros sao os do BLK-SEC-04 (7d / 4w).
RETENCAO_DIARIA_DIAS="${BACKUP_RETENCAO_DIARIA:-7}"
RETENCAO_SEMANAL_DIAS="${BACKUP_RETENCAO_SEMANAL:-28}"

# O log do cron nao cresce sem teto (mesmo espirito do run_relatorio_acessos.sh).
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

echo ">> [$(date -u +%FT%TZ)] backup do banco - inicio"

POSTGRES_DB="$(_env_do_compose POSTGRES_DB)"
POSTGRES_OWNER_USER="$(_env_do_compose POSTGRES_OWNER_USER)"
PGPASSWORD="$(_env_do_compose POSTGRES_OWNER_PASSWORD)"
[ -n "$POSTGRES_DB" ] && [ -n "$POSTGRES_OWNER_USER" ] && [ -n "$PGPASSWORD" ] || {
  echo "!! POSTGRES_DB/POSTGRES_OWNER_USER/POSTGRES_OWNER_PASSWORD ausentes em ${APP_DIR}/.env"; exit 1; }
export PGPASSWORD

# O dono do schema e' quem dumpa. O papel `app` do D20 NAO consegue: ele nao le
# `perfil_permissoes_historico` (so `auditoria` le), e um dump silenciosamente sem
# a tabela de auditoria seria pior que nenhum dump.
docker ps --format '{{.Names}}' | grep -qx "$CONTAINER" || {
  echo "!! container ${CONTAINER} nao esta de pe — nada a fazer"; exit 1; }

install -d -m 700 "${DEST_DIR}/diario" "${DEST_DIR}/semanal"

CARIMBO="$(date -u +%Y%m%dT%H%M%SZ)"
ARQ="${DEST_DIR}/diario/${POSTGRES_DB}_${CARIMBO}.dump"

# `-e PGPASSWORD` SEM valor: herda do ambiente e nunca aparece no argv do docker
# (visivel em `ps` para qualquer usuario); /proc/PID/environ e' root-only.
# Escreve num .parcial e so renomeia no fim: um dump interrompido pela metade nao
# fica com nome de dump bom, esperando alguem tentar restaurar dele.
docker exec -e PGPASSWORD "$CONTAINER" \
  pg_dump -U "$POSTGRES_OWNER_USER" -d "$POSTGRES_DB" -Fc --no-owner \
  > "${ARQ}.parcial"

# Prova que o arquivo e' um archive legivel de ponta a ponta. Custa milissegundos e
# pega truncamento/corrupcao AGORA, e nao no dia do incidente. Um `pg_dump` que
# morre no meio pode sair com exit 0 se o disco encher durante o redirecionamento.
docker exec -i "$CONTAINER" pg_restore --list > /dev/null < "${ARQ}.parcial" || {
  echo "!! dump ilegivel por pg_restore --list — descartado"; rm -f "${ARQ}.parcial"; exit 1; }

mv "${ARQ}.parcial" "$ARQ"
chmod 600 "$ARQ"
sha256sum "$ARQ" | sed "s#${DEST_DIR}/diario/##" > "${ARQ}.sha256"
echo "   dump: $(basename "$ARQ") ($(stat -c%s "$ARQ") bytes)"

# Domingo vira copia semanal. Hardlink: ocupa zero disco extra enquanto os dois
# existirem, e sobrevive a poda do diario (o inode so morre com o ultimo nome).
if [ "$(date -u +%u)" = "7" ]; then
  ln -f "$ARQ" "${DEST_DIR}/semanal/$(basename "$ARQ")"
  ln -f "${ARQ}.sha256" "${DEST_DIR}/semanal/$(basename "${ARQ}.sha256")"
  echo "   copia semanal criada"
fi

# Poda. `-mtime +N` conta dias INTEIROS: +7 apaga o que tem mais de 7 dias, nao 7.
find "${DEST_DIR}/diario"  -type f -mtime "+${RETENCAO_DIARIA_DIAS}"  -delete
find "${DEST_DIR}/semanal" -type f -mtime "+${RETENCAO_SEMANAL_DIAS}" -delete

# ── Copia off-box (restic) ──────────────────────────────────────────────────
# Sem ela o dump morre junto com o disco, e o cenario "conta Hostinger
# comprometida = servidor e backups juntos" — gap (ii) aceito em 13/07 — continua
# aberto. Fica condicional para o cron poder ser instalado ANTES de o bucket
# existir, mas o aviso e' ruidoso de proposito: backup que so vive na maquina que
# ele deveria proteger nao e' backup.
BACKUP_RESTIC_REPOSITORY="$(_env_do_compose BACKUP_RESTIC_REPOSITORY)"
BACKUP_RESTIC_PASSWORD="$(_env_do_compose BACKUP_RESTIC_PASSWORD)"

if [ -z "$BACKUP_RESTIC_REPOSITORY" ] || [ -z "$BACKUP_RESTIC_PASSWORD" ]; then
  echo "!! AVISO: copia off-box DESLIGADA (BACKUP_RESTIC_* ausentes no .env)."
  echo "!! O backup existe apenas no MESMO disco que ele deveria proteger."
  echo ">> [$(date -u +%FT%TZ)] backup do banco - fim (somente local)"
  exit 0
fi

command -v restic >/dev/null 2>&1 || {
  echo "!! restic nao instalado (apt-get install -y restic) — copia off-box NAO feita"; exit 1; }

export RESTIC_REPOSITORY="$BACKUP_RESTIC_REPOSITORY"
export RESTIC_PASSWORD="$BACKUP_RESTIC_PASSWORD"
export AWS_ACCESS_KEY_ID="$(_env_do_compose BACKUP_S3_KEY_ID)"
export AWS_SECRET_ACCESS_KEY="$(_env_do_compose BACKUP_S3_KEY_SECRET)"

restic backup --tag banco --host motor-expansao "${DEST_DIR}/diario" "${DEST_DIR}/semanal"
restic forget --tag banco --keep-daily 7 --keep-weekly 4 --prune

# `check` le a estrutura do repositorio remoto. Sem isso, corrupcao no destino so
# apareceria na tentativa de restore — que e' o pior momento possivel para saber.
restic check --read-data-subset=5%

echo ">> [$(date -u +%FT%TZ)] backup do banco - fim (local + off-box)"
