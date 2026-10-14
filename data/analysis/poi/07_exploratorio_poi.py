# -*- coding: utf-8 -*-
"""EXPLORATORIO, pos-desfecho (protocolo_poi_uni00 §8/§9): nada aqui decide. Pedido pelos ceticos da verificacao.
Todos os p sao sem correcao; o numero de testes e' impresso no fim.
E1  S1 sem isocrona a pe degenerada (area pe_15 < 0,5 km2; ex.: lago-sul-df 0,16 km2) e S1 sem DF
E2  quais unidades mudaram de F3 entre o run1 (sem relacoes OSM) e o run2
E3  "S1 idade>=12, F3" (unica linha da §8 com p < 0,05) com dummy de DF e com GroupKFold por UF
E4  S2 DENTRO do metro (efeito fixo de metro): a pergunta de escolher ponto dentro da cidade
E5  shopping: F3 v em_shopping e em_shopping como covariavel
E6  F1/F2 com contagem e pop a pe como regressores separados (a razao e' caso particular)
E7  qualidade de geocodificacao por metro na S2 e S2 sem os metros de baixa qualidade
E8  limiar do teste em R$ (sigma do residuo base de S1)
E9  checagem do crosswalk da Smart Fit (desfecho x alunos do crosswalk)
"""
import importlib.util
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

warnings.filterwarnings("ignore")
HERE = Path(__file__).parent
s = importlib.util.spec_from_file_location("t", HERE / "06_teste_poi.py"); t = importlib.util.module_from_spec(s); s.loader.exec_module(t)
rng = np.random.default_rng(7)
L, MD = [], ["# Exploratório pós-desfecho do teste de POI (não decide; p sem correção)\n"]


def teste(nome, Xb, f, y, grupos=None, oof="loo", B=499):
    o = np.isfinite(f) & np.isfinite(y) & np.isfinite(Xb).all(1)
    Xb, f, y = Xb[o], f[o], y[o]; g = grupos[o] if grupos is not None else None
    if oof == "loo":
        of = t.oof_loo
    else:
        fo = t.folds_metro(g, min(oof, len(np.unique(g)))); of = lambda X, y_: t.oof_grupos(X, y_, fo)
    d, p = t.freedman_lane(Xb, f, y, of, B, t.permutador(g, rng))
    L.append({"teste": nome, "N": int(o.sum()), "dR2": round(d, 4), "p_perm": round(p, 3), "coef_padr": round(t.coef_ols(np.column_stack([Xb, f]), y), 3)})


def main():
    B1, X1, c1, D1, sf, X2, c2, D2, k = t.dados_base()
    fam = pd.read_parquet(t.OUT / "familias_por_poligono.parquet")
    y1 = np.log(t.desfecho_S1(B1)[0]); g1 = B1.uf.to_numpy(); X1n = X1.to_numpy(float)
    y2 = np.log(t.desfecho_S2(sf, k)); g2 = D2.metro.to_numpy(); X2n = X2.to_numpy(float)
    # ---------------- E8
    Xi = t.com_intercepto(X1n); e = y1 - Xi @ np.linalg.lstsq(Xi, y1, rcond=None)[0]
    sig = e.std(ddof=X1n.shape[1] + 1)
    MD.append("## E8 Limiar do teste em R$\n")
    for pr2, pw in [(0.10, "0,38–0,55"), (0.20, "0,79–0,89")]:
        b = np.sqrt(pr2 / (1 - pr2)) * sig  # efeito de 1 DP de F (residualizada) em log
        MD.append(f"- R² parcial {pr2:.2f} (poder {pw}) = {100 * (np.exp(b) - 1):.0f}% de faturamento por 1 desvio-padrão de F (resíduo base σ = {sig:.3f} em log)")
    # ---------------- E1 / E10
    area = B1["area_km2__pe_15"].to_numpy(float)
    deg = area < 0.5
    MD.append(f"\n## E1 Isócrona a pé degenerada (< 0,5 km²): {list(B1.unidade_id[deg])} (áreas {np.round(area[deg], 2).tolist()})\n")
    for f in ["F1", "F3"]:
        teste(f"E1 S1 sem pe degenerada | {f}", X1n[~deg], D1[f].to_numpy(float)[~deg], y1[~deg], g1[~deg])
        ndf = g1 != "DF"
        teste(f"E1 S1 sem DF | {f}", X1n[ndf], D1[f].to_numpy(float)[ndf], y1[ndf], g1[ndf])
    # ---------------- E2
    rel = pd.concat([pd.read_parquet(f) for f in sorted(t.ROOT.joinpath("data", "staging", "poi").glob("osm_poi_rel_*.parquet"))])
    rel = rel[(rel.chave + "=" + rel.valor).isin(["shop=mall", "railway=station", "public_transport=station", "amenity=bus_station"])]
    anc = pd.read_parquet(t.OUT / "ancoras_pe15.parquet")
    chave = set(zip(rel.lat.round(7), rel.lng.round(7)))
    sem_rel = anc[~pd.Series(list(zip(anc.lat.round(7), anc.lng.round(7)))).isin(chave).to_numpy()]
    MD.append(f"\n## E2 Âncoras vindas de relação OSM: {len(anc) - len(sem_rel)} de {len(anc)}\n")
    for origem, ids, D, lat, lng in [("ultra_v2", B1.unidade_id, D1, B1.lat, B1.lng)]:
        f3r1 = t.f3_por_unidade(sem_rel[sem_rel.origem.eq(origem)], pd.DataFrame({"origem": origem, "ponto_id": ids, "lat": lat, "lng": lng, "tem_pe": True})).set_index("ponto_id").F3
        mud = D.F3[D.F3.to_numpy() != f3r1.reindex(D.index).to_numpy()]
        MD.append(f"- S1: unidades cuja F3 muda com as relações: {list(mud.index)} (F3 run2 = {mud.tolist()})")
    # ---------------- E3
    m12 = (B1.idade_m >= 12).to_numpy()
    f3 = D1.F3.to_numpy(float)
    teste("E3 S1 idade>=12 | F3 + dummy DF", np.column_stack([X1n, (g1 == "DF").astype(float)])[m12], f3[m12], y1[m12], g1[m12])
    teste("E3 S1 idade>=12 | F3 GroupKFold UF", X1n[m12], f3[m12], y1[m12], g1[m12], oof=8)
    teste("E3 S1 idade>=12 sem DF | F3", X1n[m12 & (g1 != "DF")], f3[m12 & (g1 != "DF")], y1[m12 & (g1 != "DF")], g1[m12 & (g1 != "DF")])
    # ---------------- E4 dentro do metro
    vc = pd.Series(g2).value_counts(); m5 = pd.Series(g2).isin(vc[vc >= 5].index).to_numpy()  # LOO com metro unitario tem alavancagem 1
    g4, y4, X4 = g2[m5], y2[m5], X2n[m5]
    X2m = np.column_stack([X4, pd.get_dummies(g4, drop_first=True).to_numpy(float)])
    MD.append(f"\n## E4 S2 com efeito fixo de metrô (metrôs com >= 5 unidades): {len(np.unique(g4))} metrôs, N = {m5.sum()}; maior = {vc.iloc[0]} unidades\n")
    MD.append(f"- R² LOO base com efeito fixo de metrô = {t.r2(y4, t.oof_loo(X2m, y4)):+.3f} (sem = {t.r2(y4, t.oof_loo(X4, y4)):+.3f})")
    for f in ["F1", "F2", "F3", "F5"]:
        Xb = np.column_stack([X2m, c2[m5]]) if f == "F5" else X2m
        teste(f"E4 S2 dentro do metrô | {f}", Xb, D2[f].to_numpy(float)[m5], y4, g4)
    # E4b: a razao F1 = log n - log pop_pe15 separada, dentro do metro (qual metade carrega o sinal?)
    pe2 = fam[fam.origem.eq("smartfit") & fam.area.eq("pe_15")].set_index("ponto_id").reindex(D2.index)
    ln1 = np.log1p(pe2.F1_fil.to_numpy(float))[m5]; lpop = ln1 - D2.F1.to_numpy(float)[m5]
    teste("E4b S2 dentro do metrô | log pop a pé sozinha", X2m, lpop, y4, g4)
    teste("E4b S2 dentro do metrô | log n F1 com log pop a pé na base", np.column_stack([X2m, lpop]), ln1, y4, g4)
    # ---------------- E5 shopping
    for nome, X, D, y, g in [("S1", X1n, D1, y1, g1), ("S2", X2n, D2, y2, g2)]:
        sh = D.em_shopping.to_numpy(float)
        teste(f"E5 {nome} | F3 ou em_shopping", X, np.maximum(D.F3.to_numpy(float), sh), y, g, oof="loo" if nome == "S1" else 10)
        teste(f"E5 {nome} | em_shopping", X, sh, y, g, oof="loo" if nome == "S1" else 10)
        teste(f"E5 {nome} | F3 com em_shopping na base", np.column_stack([X, sh]), D.F3.to_numpy(float), y, g, oof="loo" if nome == "S1" else 10)
    # ---------------- E6 contagem e pop a pe separadas
    for nome, X, D, y, g, origem in [("S1", X1n, D1, y1, g1, "ultra_v2"), ("S2", X2n, D2, y2, g2, "smartfit")]:
        pe = fam[fam.origem.eq(origem) & fam.area.eq("pe_15")].set_index("ponto_id").reindex(D.index)
        for f, col in [("F1", "F1_fil"), ("F2", "F2_fil")]:
            ln = np.log1p(pe[col].to_numpy(float)); lpop = ln - D[f].to_numpy(float)
            teste(f"E6 {nome} | log n {f} com log pop a pé na base", np.column_stack([X, lpop]), ln, y, g, oof="loo" if nome == "S1" else 10)
    # ---------------- E7 qualidade por metro na S2
    fx = D2.frac_exato_F2.to_numpy(float)
    q = pd.DataFrame({"metro": g2, "frac_exato_F2": fx}).groupby("metro").frac_exato_F2.median()
    ruins = set(q[q < 0.2].index)
    MD.append(f"\n## E7 S2: mediana da fração exata de F2 por metrô: {q.round(2).sort_values().head(8).to_dict()} ... metrôs com < 0,2: {sorted(ruins)}\n")
    ok = ~pd.Series(g2).isin(ruins).to_numpy()
    for f in ["F1", "F3", "F5"]:
        Xb = np.column_stack([X2n, c2]) if f == "F5" else X2n
        teste(f"E7 S2 sem metrôs de geocodificação ruim | {f}", Xb[ok], D2[f].to_numpy(float)[ok], y2[ok], g2[ok], oof=10)
    # ---------------- E9 crosswalk
    al = pd.read_parquet(t.SC / "vps" / "alunos_reais_por_unidade.parquet").query("rede == 'smart_fit'").drop_duplicates("concorrente_id").set_index("concorrente_id")
    cw = np.log(al.alunos_total.reindex(sf.concorrente_id).to_numpy(float))
    o = np.isfinite(cw) & np.isfinite(y2)
    MD.append(f"\n## E9 Crosswalk Smart Fit: Spearman(log alunos 2025 mediana, log alunos crosswalk jan/26) = {spearmanr(y2[o], cw[o])[0]:+.3f} (N = {o.sum()})")
    MD.append("\n## Testes exploratórios\n")
    MD.append(pd.DataFrame(L).to_markdown(index=False))
    MD.append(f"\n{len(L)} testes sem correção: com α = 0,05, espera-se ~{0.05 * len(L):.1f} 'p < 0,05' só por acaso.")
    (t.OUT / "exploratorio_poi.md").write_text("\n".join(MD), encoding="utf-8")
    print("\n".join(MD))


if __name__ == "__main__":
    main()
