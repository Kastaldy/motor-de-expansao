#!/usr/bin/env bash
# ============================================================================
# Atualizacao MENSAL da base GeoIP do piloto (DEC-082)
#     baixa DB-IP Country Lite do mes -> valida DENTRO do container -> troca por
#     rename atomico -> restart do web e do web_ar (o leitor e' memoizado por
#     caminho, entao trocar o arquivo sem restart NAO recarrega a base).
#
# PARA QUE SERVE: a aba Acessos (DEC-027 + DEC-082) mostra o PAIS do IP de quem
# acessa sem conta e marca "fora do pais". O pais vem de uma base .mmdb (MaxMind)
# lida em runtime; a DB-IP Country Lite e' atualizada todo mes. Sem este cron a base
# envelhece e, com o tempo, erra o pais de faixas de IP reatribuidas.
#
# OPCIONAL por design: GeoIP e' liga-desliga. Sem MOTOR_GEOIP_DB (ou sem base) a aba
# degrada o pais para "n/d" e NADA quebra -- /api/health segue 200. Por isso a staleness
# precisa do monitor `geoip` do healthcheck_vps.sh (DEC-082): cron morto e' invisivel.
#
# READ-ONLY sobre o M1 (CLAUDE.md pargr. 1/3): nao toca score, pesos nem artefato oficial.
# A base NAO guarda PII -- e' um mapa faixa-de-IP -> pais, publico (CC BY, DB-IP).
#
# GUARDRAIL (mesmo dos outros wrappers de cron do repo): NUNCA copia nada entre
# maquinas, NUNCA abre sessao remota, NUNCA faz deploy de imagem. Instalar e agendar
# sao passos MANUAIS do dono, comando a comando (CLAUDE.md pargr. 6). Runbook:
# docs/geoip_atualizacao.md.
# ---------------------------------------------------------------------------
set -uo pipefail

GEO_DIR="${MOTOR_GEOIP_DIR:-/opt/motor-expansao/data/geoip}"
BASE="${MOTOR_GEOIP_BASE:-$GEO_DIR/dbip-country-lite.mmdb}"
RASCUNHO="$GEO_DIR/.rascunho-geoip.mmdb"
GZ="$GEO_DIR/.rascunho-geoip.mmdb.gz"
CONTAINER_WEB="${MOTOR_GEOIP_CONTAINER_WEB:-motor_expansao_web}"
CONTAINER_WEB_AR="${MOTOR_GEOIP_CONTAINER_WEB_AR:-motor_expansao_web_ar}"
# Caminho da base DENTRO do container (o GEO_DIR e' montado :ro em /app/data/geoip).
RASCUNHO_NO_CONTAINER="/app/data/geoip/$(basename "$RASCUNHO")"
LOG_DIR="${MOTOR_GEOIP_LOG_DIR:-/var/log/motor-snapshots}"
LOG="$LOG_DIR/geoip_latest.log"
URL_BASE="${MOTOR_GEOIP_URL_BASE:-https://download.db-ip.com/free}"
MIN_BYTES="${MOTOR_GEOIP_MIN_BYTES:-1000000}"      # base real tem alguns MB; <1MB e' feed quebrado
MAX_BYTES="${MOTOR_GEOIP_MAX_BYTES:-100000000}"    # guarda de absurdo (100MB)
IP_PROVA="${MOTOR_GEOIP_IP_PROVA:-8.8.8.8}"        # 8.8.8.8 -> US em qualquer base sadia

mkdir -p "$GEO_DIR" "$LOG_DIR"
exec > >(tee -a "$LOG") 2>&1
echo "==== $(date -u +'%Y-%m-%dT%H:%M:%SZ') run_geoip_update ===="

aborta() { echo "[ABORTA] $*"; rm -f "$GZ" "$RASCUNHO"; exit "${2:-1}"; }

# 1) baixar o mes corrente; se ainda nao publicado (inicio do mes), cai no anterior.
baixou=""
for off in 0 1; do
  mes="$(date -u -d "-${off} month" +%Y-%m 2>/dev/null || date -u +%Y-%m)"
  url="$URL_BASE/dbip-country-lite-${mes}.mmdb.gz"
  echo "-- tentando $url"
  if curl -fsS -m 120 -o "$GZ" "$url"; then baixou="$mes"; break; fi
done
[ -n "$baixou" ] || aborta "nao baixei a base (mes corrente nem anterior em $URL_BASE)"

# 2) descompactar
gunzip -f "$GZ" || aborta "gunzip falhou"
[ -f "$RASCUNHO" ] || aborta "rascunho ausente apos gunzip"
bytes="$(stat -c %s "$RASCUNHO")"
echo "-- base $baixou: $bytes bytes"
{ [ "$bytes" -ge "$MIN_BYTES" ] && [ "$bytes" -le "$MAX_BYTES" ]; } \
  || aborta "tamanho fora da faixa ($bytes; [$MIN_BYTES,$MAX_BYTES]) -- feed suspeito"

# 3) VALIDAR dentro do container (que tem a lib maxminddb desta imagem), no rascunho.
#    O GEO_DIR e' montado :ro, entao o container ja' enxerga o rascunho recem-escrito.
iso="$(docker exec -i "$CONTAINER_WEB" python - "$RASCUNHO_NO_CONTAINER" "$IP_PROVA" <<'PY'
import sys
try:
    import maxminddb
    r = maxminddb.open_database(sys.argv[1])
    rec = r.get(sys.argv[2]) or {}
    print((rec.get("country") or {}).get("iso_code") or "")
except Exception as e:  # noqa: BLE001
    print("ERRO:" + type(e).__name__)
PY
)"
echo "-- validacao: $IP_PROVA -> '${iso}'"
case "$iso" in
  "" )      aborta "base ilegivel ou sem pais para $IP_PROVA (lib maxminddb na imagem?)" ;;
  ERRO:* )  aborta "falha ao abrir a base no container ($iso)" ;;
esac

# 4) troca ATOMICA (mesmo filesystem) e restart p/ reabrir o leitor memoizado por caminho.
mv -f "$RASCUNHO" "$BASE" || aborta "mv atomico falhou"
echo "-- base publicada: $BASE ($bytes bytes, mes $baixou, $IP_PROVA=$iso)"
for c in "$CONTAINER_WEB" "$CONTAINER_WEB_AR"; do
  if docker restart "$c" >/dev/null 2>&1; then echo "-- restart $c [ok]"; else echo "-- restart $c [pulado: container ausente]"; fi
done
echo "RESULTADO: GeoIP atualizado (mes $baixou). Monitor: /opt/motor-monitoring/healthcheck_vps.sh geoip"
