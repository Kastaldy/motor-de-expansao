#!/usr/bin/env bash
# Pipeline: espera cada PBF terminar de baixar -> extrai grafos (02) -> isocronas (03) -> atributos (04) -> bases (05)
# Metro 1 (DF) ja' esta' sendo processado em outro job; e' pulado em 03/04.
set -u
S="/c/Users/Felipe/AppData/Local/Temp/claude/C--dev-motor-de-expansao/9259d0a1-7dda-49bd-a390-c88f3d4ac1a6/scratchpad"
PY="$S/venv-iso/Scripts/python.exe"
PBF="/c/dev/motor-de-expansao/data/osm_cache/pbf"
cd "$S/iso"
declare -A SIZE=( [sudeste]=859034857 [sul]=425030009 [nordeste]=441775759 [norte]=160319969 )
for reg in sudeste sul nordeste norte; do
  f="$PBF/$reg-latest.osm.pbf"
  for i in $(seq 1 240); do
    sz=$(stat -c %s "$f" 2>/dev/null || echo 0)
    if [ "$sz" -ge "${SIZE[$reg]}" ]; then break; fi
    sleep 15
  done
  sz=$(stat -c %s "$f" 2>/dev/null || echo 0)
  if [ "$sz" -lt "${SIZE[$reg]}" ]; then echo "[$reg] download incompleto ($sz) — pulado"; continue; fi
  echo "[$reg] extraindo grafo $(date +%H:%M:%S)"
  "$PY" 02_grafo.py "$reg" 2>&1 | grep -v Warning
done
echo "== isocronas $(date +%H:%M:%S)"
ids=$(ls -d grafo/metro_* | sed 's/.*metro_//' | grep -vx 1 | sort -n | tr '\n' ' ')
echo "metros: $ids"
"$PY" 03_isocronas.py $ids --procs 8 2>&1 | grep -v Warning
echo "== atributos $(date +%H:%M:%S)"
"$PY" 04_atributos.py $ids 2>&1 | grep -v Warning
echo "== bases $(date +%H:%M:%S)"
"$PY" 05_base_testes.py 2>&1 | grep -v Warning
echo "== fim $(date +%H:%M:%S)"
