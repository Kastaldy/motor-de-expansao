# -*- coding: utf-8 -*-
"""BLK-UNI-10, item 3 (protocolo_bateria.md §7 + §9.9 + §20 + §21): PREPARO do lado do Censo. Sem desfecho e sem dado de aluno.
1) Le' o arquivo oficial do IBGE (Censo 2022, Agregados por Setores Censitarios, tema Demografia; baixado em 05/10 com
   autorizacao do Felipe para data/raw/ibge/censo2022_setores/) e grava as 11 faixas de idade por setor (V01031..V01041).
   Sigilo (§21): o IBGE suprime ("X") a CELULA com 1 ou 2 pessoas. Com o total do setor (V01006) publicado, o que falta
   (R = V01006 - soma publicada) e' repartido igualmente entre as celulas X (erro de no maximo 1 pessoa por celula; trava:
   nX <= R <= 2*nX). Setor com o total suprimido fica fora. A versao so' com setores completos e' sensibilidade (sufixo _comp).
2) Para cada area de influencia (Smart Fit do laboratorio = isocrona real ou circulo do item 2; Ultra = isocrona dos pinos
   corrigidos), soma a populacao de cada faixa pelo MESMO metodo do pipeline de isocronas (04_atributos): poligono invalido ->
   make_valid e a maior parte; > 40 km2 -> setor entra inteiro se o ponto representativo cai dentro; menor -> fracao de area.
Saidas em insumos_item3/: idade_setor_2022.parquet e idade_areas.parquet.
Uso: item3_prep_idade_setor.py  (.venv, PYTHONPATH=src). Um script por vez."""
import importlib.util
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
ROOT = UNI.parent.parent.parent
ZIP = ROOT / "data" / "raw" / "ibge" / "censo2022_setores" / "Agregados_por_setores_demografia_BR.zip"
OUT = AQUI / "insumos_item3"
FAIXAS = {"V01031": "0_4", "V01032": "5_9", "V01033": "10_14", "V01034": "15_19", "V01035": "20_24", "V01036": "25_29",
          "V01037": "30_39", "V01038": "40_49", "V01039": "50_59", "V01040": "60_69", "V01041": "70_mais"}
NOMES = list(FAIXAS.values())
AREA_RAPIDA_M2 = 40e6
TF = Transformer.from_crs(4326, 5880, always_xy=True)


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def ler_ibge():
    z = zipfile.ZipFile(ZIP)
    D = pd.read_csv(z.open("Agregados_por_setores_demografia_BR.csv"), sep=";", dtype=str, encoding="latin-1",
                    usecols=["CD_setor", "V01006"] + list(FAIXAS))
    X = D[["V01006"] + list(FAIXAS)].apply(pd.to_numeric, errors="coerce")
    B = X[list(FAIXAS)].to_numpy(float)
    tot = X.V01006.to_numpy(float)
    nx = np.isnan(B).sum(axis=1)
    R = tot - np.nansum(B, axis=1)
    tem_tot = ~np.isnan(tot)
    ok = tem_tot & (nx > 0)
    assert np.all(R[tem_tot & (nx == 0)] == 0), "setor completo com soma das faixas != moradores"
    assert np.all((R[ok] >= nx[ok]) & (R[ok] <= 2 * nx[ok])), "celula X fora de 1-2 pessoas"
    Bi = np.where(np.isnan(B) & tem_tot[:, None], (R / np.where(nx > 0, nx, 1))[:, None], B)
    T = pd.DataFrame({"cod_setor": D.CD_setor.astype(str), "pop_ibge": tot, "tem_total": tem_tot, "completo": nx == 0, "n_x": nx})
    for k, nome in enumerate(NOMES):
        T[f"p_{nome}"] = np.where(tem_tot, Bi[:, k], np.nan)
    return T


def main():
    OUT.mkdir(exist_ok=True)
    T = ler_ibge()
    T.to_parquet(OUT / "idade_setor_2022.parquet", index=False)
    print(f"IBGE demografia: {len(T):,} setores; total publicado {int(T.tem_total.sum()):,} ({T.loc[T.tem_total, 'pop_ibge'].sum() / T.pop_ibge.sum():.2%} "
          f"da pop.); completos {int(T.completo.sum()):,}; com celula X recuperada {int((T.tem_total & ~T.completo).sum()):,}", flush=True)
    i5 = mod("i5", AQUI / "item5_faculdades.py")  # it2 + captura das geometrias do laboratorio (nao roda o item 5)
    it2, tm, ex, op = i5.it2, i5.tm, i5.ex, i5.op
    S, _ = it2.amostra_lab(it2.ler_comodidades())
    f, d = ex.carregar(); tr, te, *_ = tm.bases(f, d)
    pv = pd.read_csv(op.PV, sep=";", encoding="utf-8-sig", index_col=0)
    PU = it2.poligonos_ultra(list(tr.index) + list(te.index) + list(pv.index))
    areas = [("lab", s, i5.GEOM[s]) for s in S.sigla] + [("ultra", u, g) for u, g in PU.geom.items()]
    _, gset = it2.setores_para_circulos([g for _, _, g in areas])  # setores (EPSG:5880) cujo bbox cruza algum poligono
    gset["cod_setor"] = gset.cod_setor.astype(str)
    gset = gset.merge(T, on="cod_setor", how="left", indicator=True)
    sem_linha = int((gset._merge == "left_only").sum())
    print(f"setores carregados: {len(gset):,}; sem linha no IBGE demografia: {sem_linha:,} (pop da malha {gset.loc[gset._merge == 'left_only', 'pop_total_setor_2022'].sum():,.0f}); "
          f"total suprimido: {int((gset._merge == 'both').sum() - gset.tem_total.fillna(False).sum()):,}", flush=True)
    tree, tree_rp = shapely.STRtree(gset.geometry.values), shapely.STRtree(gset.rp.values)
    area = gset["area"].to_numpy(float)
    pop_malha = gset.pop_total_setor_2022.clip(lower=0).fillna(0).to_numpy(float)
    tem = gset.tem_total.fillna(False).to_numpy(bool)
    comp = gset.completo.fillna(False).to_numpy(bool) & tem
    P = gset[[f"p_{n}" for n in NOMES]].fillna(0).to_numpy(float)
    linhas, invalidos = [], 0
    for (orig, chave, g4326) in areas:
        poly = shapely.transform(g4326, lambda c: np.column_stack(TF.transform(c[:, 0], c[:, 1])))
        if not poly.is_valid:  # como no 04_atributos: make_valid e a maior parte poligonal
            invalidos += 1
            mv = shapely.make_valid(poly)
            partes = [p for p in getattr(mv, "geoms", [mv]) if p.geom_type == "Polygon"]
            poly = max(partes, key=lambda p: p.area) if partes else poly.buffer(0)
        if poly.area > AREA_RAPIDA_M2:
            idx = tree_rp.query(poly, predicate="contains"); frac = np.ones(len(idx)); met = "ponto_representativo"
        else:
            idx = tree.query(poly, predicate="intersects")
            inter = shapely.area(shapely.intersection(gset.geometry.values[idx], poly)) if len(idx) else np.array([])
            frac = np.nan_to_num(np.clip(inter / np.where(area[idx] > 0, area[idx], np.nan), 0, 1)); met = "fracao_area"
        r = {"origem": orig, "chave": chave, "metodo": met, "area_km2": poly.area / 1e6, "pop_malha": float((pop_malha[idx] * frac).sum())}
        for suf, msk in (("", tem), ("_comp", comp)):
            w = frac * msk[idx]
            pf = (P[idx] * w[:, None]).sum(axis=0)
            r[f"pop_com_faixa{suf}"] = float(pf.sum())
            r.update({f"pop_{n}{suf}": float(v) for n, v in zip(NOMES, pf)})
        linhas.append(r)
    R = pd.DataFrame(linhas)
    R["cobertura_faixa"] = R.pop_com_faixa / R.pop_malha.where(R.pop_malha > 0)
    R["cobertura_faixa_comp"] = R.pop_com_faixa_comp / R.pop_malha.where(R.pop_malha > 0)
    R["gerado"] = f"{datetime.now():%Y-%m-%d %H:%M}"
    R.to_parquet(OUT / "idade_areas.parquet", index=False)
    print(f"poligonos invalidos tratados: {invalidos}")
    for o in ("lab", "ultra"):
        q = R[R.origem == o]
        print(f"{o}: {len(q)} areas; cobertura (pop com faixa / pop da malha) p10 {q.cobertura_faixa.quantile(.1):.1%}, mediana {q.cobertura_faixa.median():.1%} "
              f"(so' completos: p10 {q.cobertura_faixa_comp.quantile(.1):.1%}, mediana {q.cobertura_faixa_comp.median():.1%}); metodo {q.metodo.value_counts().to_dict()}")


if __name__ == "__main__":
    main()
