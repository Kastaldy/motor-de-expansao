# -*- coding: utf-8 -*-
"""Etapa 5 — monta as bases de teste (largas) a partir dos atributos por isocrona de todos os metros.

Saidas em SCRATCH/iso/testes/:
  base_ultra.parquet          : 1 linha por unidade Ultra (97) — atributos por cenario (colunas <atrib>__<cenario>)
                                + desfechos Growth (regime maduro, 12 m, agosto/2026), metragem, uf, master, confianca
  base_pref_revelada.parquet  : academias + controles, atributos largos, metro, tipo, subtipo
  base_hex_funil.parquet      : hexagonos da carteira acionavel com atributos largos + colunas originais do funil
  base_canibal.parquet        : pares de unidades Ultra no mesmo metro com fracao de sobreposicao das isocronas
                                (carro 5 e 10 min) e distancia
  dicionario.md               : significado das colunas
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from shapely import wkb

SCRATCH = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad")
REPO = Path(r"C:\dev\motor-de-expansao")
ISO = SCRATCH / "iso"
import os
SUF = os.environ.get("ISO_VERSAO", "")
OUT = ISO / f"testes{SUF}"
OUT.mkdir(exist_ok=True)
ATRIBS = ["area_km2", "pop", "domicilios", "renda_pc", "n_academias", "n_cadeia_mapeada", "n_cadeia_agregador_sem_pin", "n_cadeia_agregador_com_pin",
          "n_independente_agregador", "oferta_ponderada", "n_ultra", "n_nos", "km_rua", "n_setores", "truncada", "r_max_m", "raio_eq_m", "n_auto_excluida"]
CAP_CADEIA = 2500.0  # capacidade default do motor (CLAUDE.md §4)


def largo(a):
    a = a.copy()
    a["cenario"] = a["cenario"].str.replace("min", "", regex=False)
    vals = [c for c in ATRIBS if c in a.columns]
    if "truncada" in a:
        a["truncada"] = a["truncada"].astype(float)
    w = a.pivot_table(index="ponto_id", columns="cenario", values=vals, aggfunc="first", dropna=False)
    w.columns = [f"{v}__{c}" for v, c in w.columns]
    meta = a.drop_duplicates("ponto_id").set_index("ponto_id")[["tipo", "subtipo", "lat", "lng", "metro", "snap_dist_m"]]
    w = meta.join(w)
    # derivadas: residual por catchment (pop x taxa de penetracao do motor - oferta x capacidade) e pop por academia
    for c in ["carro_5", "carro_10", "carro_15", "pe_10", "pe_15", "circulo_1km", "hex_r7", "circeq_carro_5", "circeq_pe_15"]:
        if f"pop__{c}" in w:
            w[f"pop_por_academia__{c}"] = w[f"pop__{c}"] / (w[f"oferta_ponderada__{c}"].fillna(0) + 1.0)
            w[f"dens_hab_km2__{c}"] = w[f"pop__{c}"] / w[f"area_km2__{c}"].replace(0, np.nan)
            w[f"residual_alunos__{c}"] = w[f"pop__{c}"] * 0.1735 - w[f"oferta_ponderada__{c}"].fillna(0) * CAP_CADEIA  # taxa DEC-060 (17,35%)
    return w


def main():
    files = sorted((ISO / f"atributos{SUF}").glob("metro_*.parquet"))
    a = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    print("atributos:", len(a), "linhas |", a["metro"].nunique(), "metros |", a["tipo"].value_counts().to_dict())
    w = largo(a)
    # --- Ultra
    u = pd.read_parquet(ISO / "ultra_pontos.parquet")
    o = pd.read_parquet(SCRATCH / "outcomes_maduro_e_12m.parquet").reset_index().rename(columns={"index": "unidade_id"})
    if "unidade_id" not in o.columns:
        o = o.rename(columns={o.columns[0]: "unidade_id"})
    ago = pd.read_parquet(SCRATCH / "fech_ago2026.parquet")[["unidade_id", "faturamento", "pagantes", "ativos", "agregadores", "visitas", "churn_pct", "nps", "meses_operacao"]]
    ago.columns = ["unidade_id"] + [f"ago_{c}" for c in ago.columns[1:]]
    import re, unicodedata
    def norm(s):
        s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper()
        s = re.sub(r"(?:\s*[/-]\s*|\s+)(?:AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)$", "", s.strip())
        return re.sub(r"\s+", " ", s).strip()
    h = pd.read_parquet(SCRATCH / "vps" / "unidades_ultra_performance_hex.parquet")[["unidade", "metragem"]]
    h["chave"] = h["unidade"].map(norm)  # v2: sem o remapeamento SAMAMBAIA -> SAMAMBAIA NORTE (a Growth usa SAMAMBAIA; o join perdia a metragem)
    u["chave"] = u["nome"].map(norm)
    u = u.merge(h[["chave", "metragem"]].drop_duplicates("chave"), on="chave", how="left")
    bu = u.merge(o, on="unidade_id", how="left").merge(ago, on="unidade_id", how="left")
    bu = bu.set_index("unidade_id").join(w.drop(columns=["tipo", "subtipo", "lat", "lng"]), how="left").reset_index()
    for c in ["carro_5", "carro_10", "carro_15", "pe_10", "pe_15", "circulo_1km", "hex_r7", "circeq_carro_5", "circeq_pe_15"]:
        if f"n_ultra__{c}" in bu:
            bu[f"n_ultra_outras__{c}"] = (bu[f"n_ultra__{c}"] - 1).clip(lower=0)  # a propria unidade sempre esta' dentro
    bu["ativos_por_m2_mad"] = bu["ativos_med"] / bu["metragem"]
    bu["fat_por_m2_mad"] = bu["fat_med"] / bu["metragem"]
    bu["pag_por_m2_mad"] = bu["pag_med"] / bu["metragem"]
    bu["pct_agregador_mad"] = 100 * bu["agreg_med"] / (bu["pag_med"] + bu["agreg_med"])
    bu.to_parquet(OUT / "base_ultra.parquet", index=False)
    print("base_ultra:", bu.shape, "| com isocrona:", bu["pop__carro_5"].notna().sum(), "| com metragem:", bu["metragem"].notna().sum(), "| maduras c/ metragem:", (bu["metragem"].notna() & bu["n_meses"].ge(6)).sum())
    # --- preferencia revelada
    pr = w[w["tipo"].isin(["academia", "controle"])].reset_index()
    pr.to_parquet(OUT / "base_pref_revelada.parquet", index=False)
    print("base_pref_revelada:", pr.shape, pr["tipo"].value_counts().to_dict(), pr["subtipo"].value_counts().to_dict())
    # --- funil
    cart = pd.read_parquet(REPO / "data/outputs/carteira_expansao_acionavel.parquet")
    hx = w[w["tipo"] == "hex_carteira"].reset_index().rename(columns={"ponto_id": "hex_id"})
    bh = hx.merge(cart, on="hex_id", how="left", suffixes=("", "_cart"))
    bh.to_parquet(OUT / "base_hex_funil.parquet", index=False)
    print("base_hex_funil:", bh.shape)
    # --- canibalizacao: sobreposicao das isocronas entre unidades Ultra do mesmo metro
    iso_files = sorted((ISO / f"isocronas{SUF}").glob("metro_*.parquet"))
    pares = []
    for f in iso_files:
        d = pd.read_parquet(f)
        d = d[(d["tipo"] == "ultra") & (d["modo"] == "carro") & (d["poligono_wkb"].notna())]
        for lim in (300, 600):
            dd = d[d["limite_s"] == lim].reset_index(drop=True)
            polys = [wkb.loads(b) for b in dd["poligono_wkb"]]
            for i in range(len(dd)):
                for j in range(i + 1, len(dd)):
                    inter = polys[i].intersection(polys[j]).area
                    if inter <= 0:
                        continue
                    p = np.pi / 180
                    dist = 2 * 6371 * np.arcsin(np.sqrt(np.sin((dd.lat[j] - dd.lat[i]) * p / 2) ** 2 + np.cos(dd.lat[i] * p) * np.cos(dd.lat[j] * p) * np.sin((dd.lng[j] - dd.lng[i]) * p / 2) ** 2))
                    pares.append({"a": dd.ponto_id[i], "b": dd.ponto_id[j], "metro": int(dd.metro[i]), "limite_min": lim // 60, "dist_km": float(dist),
                                  "frac_a": inter / polys[i].area, "frac_b": inter / polys[j].area})
    pc = pd.DataFrame(pares)
    pc.to_parquet(OUT / "base_canibal.parquet", index=False)
    print("base_canibal:", pc.shape)
    dic = """# Dicionário das bases de teste
- Sufixo `__<cenario>`: carro_5 / carro_10 / carro_15 (isócrona de carro, min), pe_10 / pe_15 (a pé), circulo_1km (raio euclidiano de 1 km), hex_r7 (hexágono H3 res-7 do ponto).
- `pop`, `domicilios`: soma dos setores censitários 2022 ponderada pela fração de área do setor dentro do polígono. `renda_pc`: renda per capita calibrada média ponderada por população (escala do artefato setorial; NÃO é a mesma da tela do Relatório Pontual, que aplica uplift).
- `n_academias`: academias dentro do polígono (cadeias mapeadas + cadeias do agregador SEM pin mapeado + independentes); `n_<tipo>` por tipo; `n_cadeia_agregador_com_pin` é unidade de rede do WellHub que já colapsa contra um pin de concorrentes_mapeados (DEC-034/035) e por isso NÃO entra em `n_academias` nem em `oferta_ponderada` (peso 0). `oferta_ponderada`: cadeia 1,0 / independente 0,5 (DEC-033). `n_ultra`: unidades Ultra dentro (inclui a própria quando o ponto é Ultra).
- `n_nos`, `km_rua`: nós e km de rua alcançados dentro do limite (0 e polígono nulo quando o ponto não tem malha a <= 250 m).
- `pop_por_academia`, `dens_hab_km2`, `residual_alunos` (= pop × 17,35% − oferta_ponderada × 2.500; taxa da DEC-060 e capacidade default): derivadas ilustrativas.
- base_ultra: desfechos `*_med` = mediana do regime maduro (>= 12 meses de operação), `*_med_12m` = mediana dos últimos 12 meses fechados, `ago_*` = agosto/2026 fechado; `metragem` só nas 54 do performance parquet; `confianca` da coordenada (alta/media/baixa).
- base_pref_revelada: `tipo` academia (subtipo = cadeia_mapeada, cadeia_agregador_*, independente_agregador) ou controle (ponto aleatório sobre a malha).
- base_hex_funil: colunas do funil vêm de carteira_expansao_acionavel.parquet (`n_concorrentes_influencia_1km`, `oferta_efetiva_disponivel`, `faixa_oportunidade`...); atributos das isócronas calculados no CENTROIDE do hexágono.
- base_canibal: pares de unidades Ultra do mesmo metro com isócronas de carro sobrepostas; `frac_a` = área da interseção / área da isócrona de a.
"""
    (OUT / "dicionario.md").write_text(dic, encoding="utf-8")


if __name__ == "__main__":
    main()
