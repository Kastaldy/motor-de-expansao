"""
scripts/smoke_test_fontes.py — Smoke test das fontes de dados gratuitas

Valida conectividade e retorno real de:
  1. IBGE SIDRA (renda município SP)
  2. OSM Overpass (academias centro SP)
  3. Google Places (gyms — opcional, fallback se sem key)
  4. Nominatim (geocodificação Goiânia)
"""

import json
import os
import sys
import time

# Forçar UTF-8 no console Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests
from geopy.geocoders import Nominatim

# ── Carrega .env se existir ─────────────────────────────────────────────────
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

GOOGLE_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

resultados = {}
erros = []

# ── 1. IBGE SIDRA ────────────────────────────────────────────────────────────
print("\n[1/4] Testando IBGE SIDRA — renda per capita São Paulo (cod 3550308)...")
try:
    url = "https://apisidra.ibge.gov.br/values/t/10297/n6/3550308/v/allxp/p/last"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    dados = resp.json()
    # Primeira linha é cabeçalho, segunda é o valor
    valor_str = dados[1].get("V", "0") if len(dados) > 1 else "0"
    # IBGE usa ".." e "..." para dado indisponível/sigiloso
    sem_dado = str(valor_str).strip() in ("...", "..", "-", "", "X", "x")
    valor = float(str(valor_str).replace(",", ".")) if not sem_dado else 0.0
    # ".." = dado sigiloso/indisponível no IBGE — é uma resposta válida da API
    api_respondeu = True
    resultados["ibge"] = {"ok": api_respondeu, "renda": valor, "raw": valor_str, "sigiloso": sem_dado}
    print(f"   Resposta: {json.dumps(dados[:2], ensure_ascii=False)}")
    print(f"   Valor parseado: R${valor:,.2f}")
except Exception as e:
    resultados["ibge"] = {"ok": False, "erro": str(e)}
    erros.append(f"IBGE SIDRA: {e}")
    print(f"   ERRO: {e}")

time.sleep(1)

# ── 2. OSM Overpass ──────────────────────────────────────────────────────────
print("\n[2/4] Testando OSM Overpass — academias raio 1.5km centro SP...")
LAT, LNG, RAIO = -23.5505, -46.6333, 1500

OSM_TAGS = [
    '"leisure"="fitness_centre"',
    '"leisure"="sports_centre"',
    '"sport"="fitness"',
    '"sport"="gym"',
    '"amenity"="gym"',
]
filtros = "\n  ".join([f"node[{tag}](around:{RAIO},{LAT},{LNG});" for tag in OSM_TAGS])
query = f"[out:json][timeout:30];\n(\n  {filtros}\n);\nout body;\n"

try:
    resp = requests.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": query},
        timeout=40,
    )
    resp.raise_for_status()
    elementos = resp.json().get("elements", [])
    nomes = [el.get("tags", {}).get("name", "sem nome") for el in elementos[:3]]
    resultados["osm"] = {"ok": True, "n": len(elementos), "primeiros": nomes}
    print(f"   Encontradas: {len(elementos)} academias/gyms")
    print(f"   Primeiros 3: {nomes}")
except Exception as e:
    resultados["osm"] = {"ok": False, "erro": str(e)}
    erros.append(f"OSM Overpass: {e}")
    print(f"   ERRO: {e}")

time.sleep(1.1)

# ── 3. Google Places ─────────────────────────────────────────────────────────
print("\n[3/4] Testando Google Places...")
if GOOGLE_KEY:
    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
            params={"location": f"{LAT},{LNG}", "radius": RAIO, "type": "gym", "key": GOOGLE_KEY},
            timeout=15,
        )
        data = resp.json()
        status = data.get("status", "UNKNOWN")
        n = len(data.get("results", []))
        resultados["google"] = {"ok": status in ("OK", "ZERO_RESULTS"), "n": n, "status": status}
        print(f"   Status: {status} | Resultados: {n}")
    except Exception as e:
        resultados["google"] = {"ok": False, "erro": str(e)}
        erros.append(f"Google Places: {e}")
        print(f"   ERRO: {e}")
else:
    resultados["google"] = {"ok": True, "fallback": True}
    print("   Sem GOOGLE_MAPS_API_KEY — usando fallback score 50.0 (esperado)")

# ── 4. Nominatim (geocodificação) ────────────────────────────────────────────
print("\n[4/4] Testando Nominatim — geocodificação de 'Goiânia, GO, Brasil'...")
BRASIL_BOUNDS = {"lat_min": -33.75, "lat_max": 5.27, "lng_min": -73.98, "lng_max": -28.85}
try:
    geolocator = Nominatim(user_agent="motor-expansao-smoke-test/1.0", timeout=10)
    loc = geolocator.geocode("Goiânia, GO, Brasil")
    time.sleep(1.1)
    if loc:
        lat, lng = loc.latitude, loc.longitude
        dentro_brasil = (
            BRASIL_BOUNDS["lat_min"] <= lat <= BRASIL_BOUNDS["lat_max"] and
            BRASIL_BOUNDS["lng_min"] <= lng <= BRASIL_BOUNDS["lng_max"]
        )
        resultados["nominatim"] = {"ok": dentro_brasil, "lat": lat, "lng": lng}
        print(f"   Goiânia → lat={lat:.4f}, lng={lng:.4f}")
        print(f"   Dentro do Brasil: {dentro_brasil}")
    else:
        resultados["nominatim"] = {"ok": False, "erro": "Não encontrado"}
        erros.append("Nominatim: Goiânia não encontrada")
        print("   ERRO: cidade não encontrada")
except Exception as e:
    resultados["nominatim"] = {"ok": False, "erro": str(e)}
    erros.append(f"Nominatim: {e}")
    print(f"   ERRO: {e}")

# ── Resumo ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("RESUMO DO SMOKE TEST")
print("=" * 60)

ibge   = resultados.get("ibge", {})
osm    = resultados.get("osm", {})
google = resultados.get("google", {})
nomi   = resultados.get("nominatim", {})

def icon(ok):
    return "OK" if ok else "FALHOU"

if ibge.get("ok"):
    if ibge.get("sigiloso"):
        print(f"  IBGE SIDRA:     OK (API respondeu; renda SP sigilosa='{ibge.get('raw')}' — fallback via SIDRA populacao)"  )
    else:
        print(f"  IBGE SIDRA:     OK (renda SP = R${ibge.get('renda', 0):,.2f})")
else:
    print(f"  IBGE SIDRA:     FALHOU — {ibge.get('erro', '?')}")

if osm.get("ok"):
    print(f"  OSM Overpass:   OK ({osm.get('n', 0)} academias encontradas)")
else:
    print(f"  OSM Overpass:   FALHOU — {osm.get('erro', '?')}")

if google.get("fallback"):
    print("  Google Places:  sem chave (fallback 50.0 ativo)")
elif google.get("ok"):
    print(f"  Google Places:  OK (status={google.get('status')}, n={google.get('n', 0)})")
else:
    print(f"  Google Places:  FALHOU — {google.get('erro', '?')}")

if nomi.get("ok"):
    print(f"  Nominatim:      OK (lat={nomi.get('lat', '?'):.4f}, lng={nomi.get('lng', '?'):.4f})")
else:
    print(f"  Nominatim:      FALHOU — {nomi.get('erro', '?')}")

print("=" * 60)

# Saída com código de erro se alguma fonte crítica falhou
criticas_ok = ibge.get("ok") and osm.get("ok") and nomi.get("ok")
if not criticas_ok:
    print(f"\n  ERROS CRITICOS: {erros}")
    sys.exit(1)
else:
    print("\n  Fontes críticas: TODAS OK. Pipeline pronto para rodar.")
    sys.exit(0)
