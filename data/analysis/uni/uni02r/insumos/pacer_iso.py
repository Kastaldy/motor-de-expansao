# -*- coding: utf-8 -*-
"""Isocronas + atributos das unidades Pacer (UNI-02 reforco), reusando o 11_iso_multirede com saida propria.

So' as 9 unidades dentro do grafo do metro 43 (Ribeirao Preto / Bonfim); as 2 de Sertaozinho ficam fora (sem grafo).
Saida: iso/pacer/atributos/metro_43.parquet (+ iso e poligonos). Nao le alunos (so' coordenadas).
"""
import importlib.util
import json
from pathlib import Path

import pandas as pd

ISO = Path(__file__).resolve().parent
REPO = Path(r"C:\dev\motor-de-expansao")
spec = importlib.util.spec_from_file_location("m11", ISO / "11_iso_multirede.py")
m11 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m11)

PAC = ISO / "pacer"
(PAC / "atributos").mkdir(parents=True, exist_ok=True)
r = pd.read_parquet(REPO / "data" / "staging" / "alunos_reais_por_unidade.parquet", columns=["concorrente_id", "rede", "nome_unidade", "lat", "lng", "uf"])
r = r[r.rede == "pacer"].copy()
mt = {m["id"]: m for m in json.load(open(ISO / "metros.json", encoding="utf-8"))}[43]
r = r[r.lat.between(mt["lat_min"], mt["lat_max"]) & r.lng.between(mt["lng_min"], mt["lng_max"])]
pts = pd.DataFrame({"unidade": r.nome_unidade, "marca": "pacer", "uf": r.uf, "cidade": None, "lat": r.lat, "lng": r.lng,
                    "alunos_reais": None, "metragem": None, "flag_qualidade_match": None, "ponto_id": r.concorrente_id, "metro": 43})
pts.to_parquet(PAC / "pontos.parquet", index=False)
(PAC / "metros_novos.json").write_text("[]", encoding="utf-8")
print(f"{len(pts)} pontos Pacer no metro 43")
m11.MR, m11.OUT = PAC, PAC / "atributos"
m11.main(["43"])
