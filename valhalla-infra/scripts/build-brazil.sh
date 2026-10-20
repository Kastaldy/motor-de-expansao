#!/usr/bin/env bash
# ============================================================================
# Tiles do Valhalla (malha viaria do Brasil) — build FORA da VPS e publicacao
# atomica na VPS. Servico de rotas do motor, DEC-074.
#
# Dois subcomandos, em duas maquinas diferentes, e a separacao e' o ponto:
#
#   build      (estacao de trabalho / maquina com folga de RAM)
#              baixa o extrato OSM da Geofabrik, confere o md5, gera os tiles
#              num RASCUNHO, sobe um Valhalla TEMPORARIO sobre ele e roda o smoke
#              (isocrona de 10 min num ponto conhecido). So' empacota se o smoke
#              passar. Nada aqui toca a VPS.
#
#   publicar   (na VPS, em /opt/valhalla-infra, com o pacote ja' copiado)
#              desempacota no rascunho -> rename atomico -> `docker compose up -d`
#              -> smoke DE DENTRO da app_net (pelo container do piloto, que e'
#              quem chama de verdade). Smoke reprovado = volta o anterior.
#
# Por que o build e' fora: o build do Brasil inteiro disputa RAM e CPU com o
# motor (a KVM4 ja' tem tetos declarados acima dos 16 GB fisicos), e o custo
# dele AINDA NAO FOI MEDIDO (DEC-074, "Numeros a medir antes de aprovar").
# Mesma regra do generate-brazil.sh do openmaptiles-infra.
#
# REGRA DE OPERACAO: cada comando na VPS exige confirmacao explicita do dono
# (CLAUDE.md §6). Este script NUNCA faz ssh/scp — so' imprime o proximo passo.
#
# Uso:
#   bash scripts/build-brazil.sh build                 # na estacao
#   bash scripts/build-brazil.sh publicar <pacote>     # na VPS
#
# Variaveis (todas opcionais):
#   AREA            extrato da Geofabrik em south-america/ (default: brazil)
#   BUILD_MEM       --memory do container de build (ex.: 12g); vazio = sem teto
#   PORTA_SMOKE     porta LOCAL (127.0.0.1) do Valhalla temporario (default 8012)
#   ESPERA_MAX_MIN  quanto esperar o build/subida antes de desistir (default 720;
#                   teto generoso de proposito ate' o tempo real ser medido)
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

# MESMA imagem do docker-compose.yml, pelo mesmo digest: tiles gerados por uma
# versao e servidos por outra sao a forma mais barata de quebrar o servico.
# (Paridade travada por tests/contracts/test_compose_rotas.py.)
IMAGEM="ghcr.io/valhalla/valhalla-scripted:3.9.0@sha256:89daaf61547167893cf58c03defd43c6eba0071dc965988c16a629260f8ac683"
AREA="${AREA:-brazil}"
URL_PBF="https://download.geofabrik.de/south-america/${AREA}-latest.osm.pbf"
# Nomes FIXOS e relativos ao diretorio da stack (o `cd` acima): os `rm -rf`
# abaixo usam `${VAR:?}`, entao uma variavel vazia aborta em vez de apagar `/`.
RASCUNHO="custom_files.novo"
VIVO="custom_files"
ANTERIOR="custom_files.anterior"
PORTA_SMOKE="${PORTA_SMOKE:-8012}"
ESPERA_MAX_MIN="${ESPERA_MAX_MIN:-720}"
CONTAINER_PILOTO="${CONTAINER_PILOTO:-motor_expansao_web}"
URL_INTERNA="http://motor_expansao_valhalla:8002"

# Smoke: isocrona de 10 min, sem transito, na Av. Paulista (Sao Paulo). Ponto
# urbano denso de proposito — se a malha veio quebrada, e' aqui que aparece.
# Criterio de aprovacao e' ESTRUTURAL (GeoJSON com Polygon/MultiPolygon e area
# > 0), sem faixa de area: a faixa plausivel ainda NAO foi medida (DEC-074) e um
# numero inventado aqui reprovaria um build bom ou aprovaria um ruim.
# A area e o tempo impressos sao registro para a medicao, nao criterio.
# shellcheck disable=SC2016
SMOKE_PY='
import json, math, sys, time, urllib.request
base = sys.argv[1].rstrip("/")
lat, lng = -23.5614, -46.6559
corpo = {"locations": [{"lat": lat, "lon": lng}], "costing": "auto",
         "contours": [{"time": 10}], "polygons": True, "denoise": 0.5, "generalize": 25}
req = urllib.request.Request(base + "/isochrone", data=json.dumps(corpo).encode(),
                             headers={"Content-Type": "application/json"})
t0 = time.time()
with urllib.request.urlopen(req, timeout=60) as r:
    fc = json.load(r)
dt = time.time() - t0
geoms = [f.get("geometry") or {} for f in fc.get("features", [])]
geoms = [g for g in geoms if g.get("type") in ("Polygon", "MultiPolygon")]
if not geoms:
    sys.exit("smoke REPROVADO: a isocrona nao devolveu Polygon/MultiPolygon")
def anel_km2(anel):
    # projecao equiretangular local: basta para registro, nao e a regua do motor
    kx = 111.320 * math.cos(math.radians(lat)); ky = 110.574
    pts = [((x - lng) * kx, (y - lat) * ky) for x, y in anel]
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:]))) / 2
area = 0.0
for g in geoms:
    polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
    for p in polys:
        area += anel_km2(p[0]) - sum(anel_km2(b) for b in p[1:])
if area <= 0:
    sys.exit("smoke REPROVADO: isocrona com area zero")
st = {}
try:
    with urllib.request.urlopen(base + "/status", timeout=10) as r:
        st = json.load(r)
except Exception:
    pass
tipo = geoms[0]["type"]
versao = st.get("version")
tiles = st.get("tileset_last_modified")
print(f"smoke OK: {tipo}, ~{area:.1f} km2, {dt:.1f} s; versao={versao} tileset_last_modified={tiles}")
'

erro() { echo "ERRO: $*" >&2; exit 1; }

uid_da_imagem() { # o usuario com que a imagem roda (nao cravar o numero: muda entre versoes)
    docker run --rm --entrypoint id "$IMAGEM" -u
}

liberar_escrita() { # liberar_escrita <dir> — a imagem roda sem root e precisa escrever no volume
    local dir="$1" uid
    uid="$(uid_da_imagem)"
    if ! chown -R "$uid:$uid" "$dir" 2>/dev/null; then
        echo "aviso: sem permissao para chown $uid em $dir; liberando escrita para todos" >&2
        chmod -R a+rwX "$dir"
    fi
}

esperar_status() { # esperar_status <comando que testa /status>
    local fim=$(( $(date +%s) + ESPERA_MAX_MIN * 60 ))
    until eval "$1" >/dev/null 2>&1; do
        (( $(date +%s) < fim )) || return 1
        sleep 30
    done
}

cmd_build() {
    command -v docker >/dev/null || erro "docker nao encontrado"
    local py; py="$(command -v python3 || command -v python)" || erro "python nao encontrado (smoke)"
    mkdir -p fontes

    echo ">> Baixando o extrato '$AREA' da Geofabrik e o .md5 publicado ao lado..."
    curl -fL -o "fontes/${AREA}-latest.osm.pbf" "$URL_PBF"
    curl -fL -o "fontes/${AREA}-latest.osm.pbf.md5" "${URL_PBF}.md5"
    # O .md5 da Geofabrik referencia o nome do arquivo: conferir DENTRO de fontes/.
    (cd fontes && md5sum -c "${AREA}-latest.osm.pbf.md5") || erro "md5 do extrato nao confere"
    local md5; md5="$(cut -d' ' -f1 "fontes/${AREA}-latest.osm.pbf.md5")"
    local data_osm; data_osm="$(curl -fsSI "$URL_PBF" | tr -d '\r' | sed -n 's/^[Ll]ast-[Mm]odified: //p')"

    echo ">> Rascunho limpo em $RASCUNHO (o vivo, se existir, nao e' tocado)..."
    rm -rf "${RASCUNHO:?}"
    mkdir -p "$RASCUNHO"
    cp "fontes/${AREA}-latest.osm.pbf" "$RASCUNHO/"
    liberar_escrita "$RASCUNHO"

    docker rm -f valhalla-build >/dev/null 2>&1 || true
    local mem=()
    if [[ -n "${BUILD_MEM:-}" ]]; then mem=(--memory "$BUILD_MEM"); fi
    local inicio; inicio=$(date +%s)
    echo ">> Build dos tiles (container temporario, porta 127.0.0.1:$PORTA_SMOKE)..."
    # build_admins: fronteiras e lado de circulacao. build_time_zones: so' importa
    # com `date_time`, que o motor NAO manda (tempo SEM transito, DEC-074) — fora,
    # para encurtar o build.
    docker run -d --name valhalla-build "${mem[@]}" \
        -p "127.0.0.1:${PORTA_SMOKE}:8002" \
        -v "$PWD/$RASCUNHO:/custom_files" \
        -e use_tiles_ignore_pbf=False -e force_rebuild=True \
        -e build_elevation=False -e build_transit=False \
        -e build_admins=True -e build_time_zones=False \
        -e build_tar=True -e serve_tiles=True -e server_threads=2 \
        "$IMAGEM" >/dev/null

    if ! esperar_status "curl -fs http://127.0.0.1:${PORTA_SMOKE}/status"; then
        docker logs --tail 50 valhalla-build || true
        docker rm -f valhalla-build >/dev/null || true
        erro "build nao subiu em ${ESPERA_MAX_MIN} min"
    fi
    local duracao=$(( $(date +%s) - inicio ))
    # Registro de memoria para a DEC-074. ATENCAO: `docker stats` ve o INSTANTE
    # (o servico ja' de pe), nao o pico do build — o pico sai do cgroup
    # (`memory.peak`) ou de um `docker stats` em laco durante o build.
    docker stats --no-stream valhalla-build || true

    if ! "$py" -c "$SMOKE_PY" "http://127.0.0.1:${PORTA_SMOKE}"; then
        docker rm -f valhalla-build >/dev/null || true
        erro "smoke reprovado — nada empacotado"
    fi
    docker rm -f valhalla-build >/dev/null

    [[ -f "$RASCUNHO/valhalla_tiles.tar" ]] || erro "build sem valhalla_tiles.tar"
    # Servir com use_tiles_ignore_pbf=True nao precisa do extrato (GBs a menos no pacote).
    find "${RASCUNHO:?}" -maxdepth 1 -name '*.pbf' -delete

    # Carimbo de AUDITORIA (DEC-074): de qual OSM e de qual imagem saiu a malha
    # que respondeu cada isocrona. O motor carimba tambem o `/status` do servico.
    cat >"$RASCUNHO/VERSAO_TILES" <<VERSAO
area=$AREA
fonte=$URL_PBF
md5_pbf=$md5
osm_last_modified=$data_osm
imagem=$IMAGEM
build_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
build_segundos=$duracao
VERSAO

    local pacote; pacote="valhalla-tiles-${AREA}-$(date -u +%Y%m%d).tar.gz"
    tar czf "$pacote" -C "$RASCUNHO" .
    echo ">> OK -> $pacote ($(du -h "$pacote" | cut -f1)); tiles: $(du -sh "$RASCUNHO" | cut -f1); build: ${duracao}s"
    echo ">> Proximo passo (com confirmacao do dono, CLAUDE.md §6):"
    echo "   copiar $pacote para /opt/valhalla-infra/ na VPS e rodar"
    echo "   bash scripts/build-brazil.sh publicar $pacote"
}

smoke_interno() { # smoke pela app_net, de dentro do container que chama o servico de verdade
    docker exec -i "$CONTAINER_PILOTO" python - "$URL_INTERNA" <<<"$SMOKE_PY"
}

cmd_publicar() {
    local pacote="${1:-}"
    [[ -n "$pacote" && -f "$pacote" ]] || erro "uso: $0 publicar <pacote.tar.gz>"

    rm -rf "${RASCUNHO:?}"
    mkdir -p "$RASCUNHO"
    tar xzf "$pacote" -C "$RASCUNHO"
    [[ -f "$RASCUNHO/valhalla_tiles.tar" && -f "$RASCUNHO/VERSAO_TILES" ]] \
        || erro "pacote incompleto (falta valhalla_tiles.tar ou VERSAO_TILES); vivo intacto"
    liberar_escrita "$RASCUNHO"

    # Rename atomico: o vivo vira `anterior` (rollback em um passo) e o rascunho
    # vira vivo. Um so' anterior guardado: os tiles do Brasil nao sao pequenos.
    rm -rf "${ANTERIOR:?}"
    if [[ -d "$VIVO" ]]; then mv "$VIVO" "$ANTERIOR"; fi
    mv "$RASCUNHO" "$VIVO"
    docker compose up -d --force-recreate valhalla

    if esperar_status "docker exec $CONTAINER_PILOTO python -c 'import urllib.request;urllib.request.urlopen(\"$URL_INTERNA/status\",timeout=5)'" \
        && smoke_interno; then
        echo ">> Publicado: $(grep -E '^(osm_last_modified|build_utc)=' "$VIVO/VERSAO_TILES" | tr '\n' ' ')"
        return 0
    fi

    echo "ERRO: smoke reprovado depois da troca — voltando os tiles anteriores" >&2
    if [[ -d "$ANTERIOR" ]]; then
        rm -rf "${VIVO:?}"
        mv "$ANTERIOR" "$VIVO"
        docker compose up -d --force-recreate valhalla
    fi
    exit 1
}

case "${1:-}" in
build) cmd_build ;;
publicar) shift; cmd_publicar "$@" ;;
*) echo "uso: $0 {build|publicar <pacote.tar.gz>}" >&2; exit 2 ;;
esac
