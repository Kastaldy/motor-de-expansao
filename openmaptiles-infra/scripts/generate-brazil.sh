#!/usr/bin/env bash
# ============================================================================
# Gera data/mbtiles/brazil.mbtiles (schema OpenMapTiles, z0-14) com planetiler.
# planetiler = 1 jar Java; baixa o extract do Brasil (Geofabrik) e gera os tiles.
# Zero licença (só atribuição OSM). Saída ~3-6 GB.
#
# REGRA DE OPERAÇÃO (do sizing do servidor):
#   - NÃO rodar no domingo 2h (janela do job pesado do motor).
#   - Ideal: rodar FORA da caixa (outra máquina) e copiar o .mbtiles pro servidor,
#     pra não competir por CPU/RAM com o motor. Se rodar na caixa, use off-peak.
#
# Uso:   bash scripts/generate-brazil.sh
# RAM:   ajuste JAVA_XMX (default 6g). Flags mmap/array reduzem uso de memória.
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

PLANETILER_JAR="planetiler.jar"
JAVA_XMX="${JAVA_XMX:-6g}"
AREA="${AREA:-brazil}"          # troque para uma UF (ex.: 'sao-paulo') p/ encolher

mkdir -p data/mbtiles data/sources

if [ ! -f "$PLANETILER_JAR" ]; then
  echo ">> Baixando planetiler.jar..."
  curl -L -o "$PLANETILER_JAR" \
    https://github.com/onthegomap/planetiler/releases/latest/download/planetiler.jar
fi

echo ">> Gerando tiles de '$AREA' (Xmx=$JAVA_XMX). Isso baixa o OSM e processa..."
java -Xmx"$JAVA_XMX" -jar "$PLANETILER_JAR" \
  --download --area="$AREA" \
  --storage=mmap --nodemap-type=array \
  --download-dir=data/sources \
  --output=data/mbtiles/brazil.mbtiles --force

echo ">> OK -> data/mbtiles/brazil.mbtiles"
echo ">> Agora: docker compose up -d   (ou reinicie o tileserver p/ recarregar)"

# ----------------------------------------------------------------------------
# ALTERNATIVA sem gerar (se preferir um .mbtiles pronto):
#   1) baixe um extract OpenMapTiles do Brasil (.mbtiles)
#   2) salve como data/mbtiles/brazil.mbtiles
#   3) docker compose up -d
# ----------------------------------------------------------------------------
