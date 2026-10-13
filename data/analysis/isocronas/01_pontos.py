# -*- coding: utf-8 -*-
"""Etapa 1 — universo de pontos para as isocronas.

Saidas (em SCRATCH/iso/):
  ultra_pontos.parquet     : unidades Ultra da Growth (97) com coordenada, origem e confianca do casamento
  academias_pontos.parquet : concorrentes de cadeia (concorrentes_mapeados validos) + independentes e cadeias
                             do agregador (vulnerabilidade_ma_*), dedup por coordenada (~25 m)
  metros.json              : caixas (bbox) das regioes metropolitanas-alvo, derivadas por cluster dos pontos Ultra
                             (unidades Growth + pins do cadastro), com margem

Casamento Growth -> cadastro: chave normalizada + UF (66 diretos) e mapa manual para os 31 restantes;
os incertos sao geocodificados no Nominatim (1 req/s, User-Agent declarado) e recebem `confianca`.
"""
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import requests

SCRATCH = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad")
REPO = Path(r"C:\dev\motor-de-expansao")
OUT = SCRATCH / "iso"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(REPO / "src"))
from motor_expansao.dashboard import rede_metricas as rm  # noqa: E402

UFS = "AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO"


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper()
    s = re.sub(rf"(?:\s*[/-]\s*|\s+)(?:{UFS})$", "", s.strip())
    return re.sub(r"\s+", " ", s).strip()


# nome Growth (normalizado) -> (nome no cadastro, confianca, consulta Nominatim opcional)
MAPA_MANUAL = {
    "AMERICANA CENTRO": ("Americana / SP", "alta", None),
    "ARAPOANGA PLANALTINA": ("Arapoanga - Planaltina / DF", "alta", None),
    "CAMBUI CAMPINAS": ("Cambuí", "alta", None),
    "CAXIAS": ("Duque de Caxias", "alta", None),
    "CESARIO": ("Cesário Alvim / MG", "alta", None),
    "FLORIANO": ("Floriano Peixoto / MG", "alta", None),
    "FLOW": ("Curitiba Flow (Uberaba) / PR", "alta", None),
    "JARDIM APURA": ("Jd Apurá /SP", "alta", None),
    "NOROESTE": ("Noroeste (Brasília) / DF", "alta", None),
    "PATIO BRASIL": ("Pátio Shopping Brasil / DF", "alta", None),
    "PICARRAS": ("Balneário Piçarras / SC", "alta", None),
    "POA BARRA SUL": ("Porto Alegre / RS", "media", "Barra Shopping Sul, Porto Alegre, RS"),
    "SAMAMBAIA": ("Samambaia Norte / DF", "alta", None),
    "SAO CARLOS - CENTRO": ("São Carlos / SP", "alta", None),
    "SAO GONCALO - CENTRO": ("São Gonçalo RJ", "alta", None),
    "SAO GONCALO SHOPPING": ("Shopping Partage RJ", "alta", None),
    "VALPARAISO": ("Valparaíso de Goiás / GO", "media", None),
    "VICENTE PIRES RUA 8": ("Vicente Pires 2", "media", "Rua 8, Vicente Pires, Brasília, DF"),
    "VILLA BRANCA": ("Jacareí", "media", "Villa Branca, Jacareí, SP"),
    "VISCONDE DE RIO CLARO": ("Rio Claro", "media", None),
    "JARDIM BOTANICO": ("Jd. Botânico / DF", "media", None),
    "BOTANIC MALL": ("Jardim Botânico II / DF", "baixa", "Botanic Mall, Jardim Botânico, Brasília, DF"),
    "PARANOA PARQUE": ("Paranoá / DF", "baixa", "Paranoá Parque, Brasília, DF"),
    "CPA": ("Cuiabá", "baixa", "CPA, Cuiabá, MT"),
    # A consulta antiga era "Sagrada Família, CUIABÁ, MT" e caia ~200 km da praca certa: a
    # unidade e' em RONDONOPOLIS. Coordenada conferida pelo Felipe -> COORD_MANUAL abaixo.
    "SAGRADA FAMILIA": (None, "alta", None),
    "DOMINGOS FERREIRA": (None, "baixa", "Avenida Domingos Ferreira, Boa Viagem, Recife, PE"),
    "BOA VISTA": (None, "baixa", "Boa Vista, Vitória da Conquista, BA"),
    "BOQUEIRAO": (None, "baixa", "Boqueirão, Santos, SP"),
    "CEILANDIA QNM24": (None, "media", "QNM 24, Ceilândia, Brasília, DF"),
    "CEILANDIA QNM33": (None, "media", "QNM 33, Ceilândia, Brasília, DF"),
    "CEILANDIA QNN32": (None, "media", "QNN 32, Ceilândia, Brasília, DF"),
}
# Coordenada INFORMADA pelo Felipe (2026-09-28), que vence TODAS as fontes -- inclusive o
# casamento por chave+UF no cadastro. Existe porque nos dois casos o cadastro nao resolve:
#
#   PLAZA SUL       o cadastro TEM a linha certa ("Plaza / SP", a 6,4 m daqui), mas tambem tem
#                   uma linha "Plaza Sul" a 1.340,7 m -- e e' esta que a chave normalizada
#                   casa. O casamento por nome escolhe o pino ERRADO, com confianca "alta".
#   SAGRADA FAMILIA nao tem linha propria no cadastro; a do municipio se chama "Rondonopolis"
#                   (a 1,5 m daqui) e a consulta manual antiga procurava em CUIABA.
#
# Espelha `_EXEC_COORD_CORRIGIDA` em web/server/app.py, que faz a mesma correcao na producao.
COORD_MANUAL = {
    "PLAZA SUL": (-23.619836588209818, -46.62658767878267),
    "SAGRADA FAMILIA": (-16.472689780537294, -54.60695014754936),
}

# pins do cadastro que sao DUPLICADOS e nao devem ser usados (ver parecer §4)
PINS_IGNORAR = {"Sobradinho / DF"}


def nominatim(q):
    r = requests.get("https://nominatim.openstreetmap.org/search", params={"q": q, "format": "json", "limit": 1, "countrycodes": "br"},
                     headers={"User-Agent": "motor-expansao-ultra/isocronas (analise interna; contato: felipe.silva@ultraacademia.com.br)"}, timeout=30)
    r.raise_for_status()
    js = r.json()
    time.sleep(1.1)
    if not js:
        return None
    return float(js[0]["lat"]), float(js[0]["lon"]), js[0].get("display_name", "")


def main():
    base = rm.carregar_base(SCRATCH / "vps" / "growth_api_historico.parquet")
    cat = rm.catalogo_de(base)
    g = pd.DataFrame([{"unidade_id": k, "nome": u.nome, "uf": u.uf, "master": u.master, "inauguracao": u.inauguracao} for k, u in cat.items()])
    g["chave"] = g["nome"].map(norm)
    m = pd.read_parquet(SCRATCH / "vps" / "unidades_ultra_mapeadas.parquet")
    m = m[~m["unidade"].isin(PINS_IGNORAR)].copy()
    m["chave"] = m["unidade"].map(norm)
    por_nome = m.set_index("unidade")
    linhas = []
    for _, r in g.iterrows():
        # ANTES do casamento por chave: para a Plaza Sul o cadastro CASA, e casa no pino
        # errado. Consultar depois seria nunca consultar.
        manual = COORD_MANUAL.get(r["chave"])
        if manual is not None:
            linhas.append({**r.to_dict(), "lat": manual[0], "lng": manual[1],
                           "pin_cadastro": None, "origem_coord": "manual_felipe", "confianca": "alta"})
            continue
        hit = m[(m["chave"] == r["chave"]) & (m["uf"] == r["uf"])]
        if len(hit) == 1:
            h = hit.iloc[0]
            linhas.append({**r.to_dict(), "lat": h["lat"], "lng": h["lng"], "pin_cadastro": h["unidade"], "origem_coord": "cadastro", "confianca": "alta"})
            continue
        if len(hit) > 1:
            h = hit.iloc[0]
            linhas.append({**r.to_dict(), "lat": h["lat"], "lng": h["lng"], "pin_cadastro": h["unidade"], "origem_coord": "cadastro_1o_de_varios", "confianca": "media"})
            continue
        mp = MAPA_MANUAL.get(r["chave"])
        if mp is None:
            linhas.append({**r.to_dict(), "lat": np.nan, "lng": np.nan, "pin_cadastro": None, "origem_coord": "sem_coord", "confianca": "nenhuma"})
            continue
        pin, conf, q = mp
        lat = lng = np.nan
        origem = None
        if pin is not None and pin in por_nome.index:
            lat, lng = por_nome.loc[pin, "lat"], por_nome.loc[pin, "lng"]
            origem = "cadastro_manual"
        if q is not None:
            try:
                geo = nominatim(q)
            except Exception as exc:  # noqa: BLE001
                geo = None
                print("nominatim falhou:", q, exc)
            if geo is not None:
                glat, glng, disp = geo
                if origem is None:
                    lat, lng, origem = glat, glng, "nominatim"
                else:
                    # cruzamento: se o pin manual e o Nominatim divergem > 3 km, rebaixa a confianca
                    from math import radians, sin, cos, asin, sqrt
                    p = np.pi / 180
                    d = 2 * 6371 * asin(sqrt(sin((glat - lat) * p / 2) ** 2 + cos(lat * p) * cos(glat * p) * sin((glng - lng) * p / 2) ** 2))
                    if d > 3.0:
                        # pin manual e Nominatim discordam: fica o Nominatim (consulta especifica) com confianca baixa
                        lat, lng, conf = glat, glng, "baixa"
                        origem = f"nominatim(divergente_do_pin_{d:.1f}km)"
                    elif d <= 0.3:
                        conf = "alta"
                        origem = "cadastro_manual(confirmado_nominatim)"
                    elif d <= 1.5:
                        conf = "media"
                        origem = f"cadastro_manual(nominatim_a_{d:.1f}km)"
                print(f"  nominatim {q!r} -> {glat:.5f},{glng:.5f} | {disp[:80]}")
        linhas.append({**r.to_dict(), "lat": lat, "lng": lng, "pin_cadastro": pin, "origem_coord": origem or "sem_coord", "confianca": conf if origem else "nenhuma"})
    u = pd.DataFrame(linhas)
    u.to_parquet(OUT / "ultra_pontos.parquet", index=False)
    print("ultra_pontos:", len(u), "| com coord:", u["lat"].notna().sum(), "| confianca:", u["confianca"].value_counts().to_dict())
    print(u[u["confianca"].isin(["media", "baixa", "nenhuma"])][["nome", "uf", "pin_cadastro", "origem_coord", "confianca", "lat", "lng"]].to_string())

    # ---- academias (oferta)
    c = pd.read_parquet(REPO / "data/staging/concorrentes_mapeados.parquet")
    c = c[c["status_registro"] == "valido"][["concorrente_id", "rede", "nome_unidade", "lat", "lng"]].rename(columns={"concorrente_id": "id", "nome_unidade": "nome"})
    c["uf"] = None
    c["tipo"] = "cadeia_mapeada"
    n = pd.read_parquet(REPO / "data/staging/vulnerabilidade_ma_nomeadas.parquet", columns=["chave_snapshot", "nome", "lat", "lng"]).dropna(subset=["lat", "lng"])
    n = n.rename(columns={"chave_snapshot": "id"}); n["rede"] = None; n["uf"] = None; n["tipo"] = "independente_agregador"
    rd = pd.read_parquet(REPO / "data/staging/vulnerabilidade_ma_redes.parquet", columns=["chave_snapshot", "nome", "rede", "lat", "lng", "tem_pin_proprio"]).dropna(subset=["lat", "lng"])
    rd = rd.rename(columns={"chave_snapshot": "id"}); rd["uf"] = None; rd["tipo"] = np.where(rd["tem_pin_proprio"], "cadeia_agregador_sem_pin", "cadeia_agregador_com_pin")
    # v2: universo de oferta do motor — sem estudios boutique (DEC-056, lista do dono em
    # enriquecimento_espacial_hexagonos.REDES_ESTUDIO_BOUTIQUE) e sem a propria Ultra listada no
    # agregador como "independente" (regra de movimentacao_concorrencia.filtrar_concorrencia)
    ESTUDIOS = {"velocity", "my_box", "vidya_studio", "tonus_gym", "aera_pilates", "race_bootcamp", "kore", "nadarte", "jab_house"}
    n_ant = (len(c), len(n), len(rd))
    c = c[~c["rede"].isin(ESTUDIOS)]
    rd = rd[~rd["rede"].isin(ESTUDIOS)]
    n = n[~n["nome"].str.contains(r"\bultra\s+academia\b", case=False, regex=True, na=False)]
    print(f"v2 exclusoes: cadeias mapeadas {n_ant[0]}->{len(c)} | independentes {n_ant[1]}->{len(n)} (Ultra) | cadeias agregador {n_ant[2]}->{len(rd)} (estudios)")
    a = pd.concat([c, n, rd.drop(columns=["tem_pin_proprio"])], ignore_index=True)
    # dedup por coordenada arredondada (~25 m) mantendo a cadeia mapeada quando houver
    a["_k"] = (a["lat"].round(4).astype(str) + "," + a["lng"].round(4).astype(str))
    prio = {"cadeia_mapeada": 0, "cadeia_agregador_sem_pin": 1, "cadeia_agregador_com_pin": 2, "independente_agregador": 3}
    a = a.sort_values("_k").assign(_p=a["tipo"].map(prio)).sort_values(["_k", "_p"]).drop_duplicates("_k").drop(columns=["_k", "_p"])
    a.to_parquet(OUT / "academias_pontos.parquet", index=False)
    print("academias_pontos:", len(a), a["tipo"].value_counts().to_dict())

    # ---- metros: clusters dos pontos Ultra (Growth + cadastro), margem 12 km
    pts = pd.concat([u.dropna(subset=["lat"])[["lat", "lng"]], m[["lat", "lng"]]], ignore_index=True)
    from sklearn.cluster import DBSCAN
    lab = DBSCAN(eps=35 / 111.0, min_samples=1).fit(pts[["lat", "lng"]].values).labels_
    pts["cl"] = lab
    metros = []
    for cl, grp in pts.groupby("cl"):
        mlat = 12 / 111.0; mlng = 12 / (111.0 * np.cos(np.radians(grp["lat"].mean())))
        metros.append({"id": int(cl), "n_pontos": int(len(grp)), "lat_min": float(grp["lat"].min() - mlat), "lat_max": float(grp["lat"].max() + mlat),
                       "lng_min": float(grp["lng"].min() - mlng), "lng_max": float(grp["lng"].max() + mlng), "lat_c": float(grp["lat"].mean()), "lng_c": float(grp["lng"].mean())})
    json.dump(metros, open(OUT / "metros.json", "w", encoding="utf-8"), indent=1)
    area = sum((mm["lat_max"] - mm["lat_min"]) * 111 * (mm["lng_max"] - mm["lng_min"]) * 111 * np.cos(np.radians(mm["lat_c"])) for mm in metros)
    print("metros:", len(metros), "| area total bbox km2:", round(area), "| maiores:", sorted([(mm["n_pontos"], round(mm["lat_c"], 2), round(mm["lng_c"], 2)) for mm in metros], reverse=True)[:8])


if __name__ == "__main__":
    main()
