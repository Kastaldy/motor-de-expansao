# -*- coding: utf-8 -*-
"""Aproveitamento v2: faturamento do FECHAMENTO DO FINANCEIRO (agosto/2026 e mediana 12 m), versao em alunos com
Ultra + Engenharia do Corpo, e crescimento (hexagono e municipio) testado tambem na SkyFit (replicacao independente).
Mesma conta declarada do 13 (demanda por isocrona x renda x crescimento; oferta com alunos reais; canibalizacao;
captura proporcional a metragem), 2.000 sorteios, normalizado pela mediana da rede em cada sorteio.
Saidas: iso/aproveitamento_v2/*.csv, resultados.md
"""
import json
import re
import unicodedata
import warnings
from pathlib import Path

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from shapely import wkb
from shapely.geometry import Point
from shapely.strtree import STRtree

warnings.filterwarnings("ignore")
SC = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad")
REPO = Path(r"C:\dev\motor-de-expansao")
ISO = SC / "iso"; MR = ISO / "multirede"; OUT = ISO / "aproveitamento_v2"; OUT.mkdir(exist_ok=True)
RNG = np.random.default_rng(42)
CEN = {"carro_5": ("carro", 300), "carro_10": ("carro", 600), "pe_15": ("pe", 900)}
FAIXAS = {"taxa": (0.10, 0.25), "elast_renda": (0.0, 1.0), "elast_ticket": (0.0, 0.6), "proxy_indep": (150, 800),
          "proxy_cadeia": (1000, 2500), "dens_ref": (1.2, 2.2), "peso_cresc": (0.0, 0.3)}
N_SORTEIOS = 2000
MD = []


# ------------------------------------------------------------------ insumos comuns
def oferta():
    ac = pd.read_parquet(ISO / "academias_pontos.parquet")
    ac = ac[ac["tipo"] != "cadeia_agregador_com_pin"].reset_index(drop=True)
    cw = pd.read_parquet(SC / "vps" / "alunos_reais_por_unidade.parquet")
    cw = cw[(cw.confianca_match == "alta") & (cw.alunos_total > 0)]
    ac["cap_real"] = ac["id"].map(cw.groupby("concorrente_id")["alunos_total"].median())
    ac["cap_rede"] = ac["rede"].map(cw.groupby("rede")["alunos_total"].median())
    ac["classe"] = np.where(ac.cap_real.notna(), "real", np.where(ac.cap_rede.notna(), "mediana_rede", np.where(ac.tipo == "independente_agregador", "indep", "cadeia_proxy")))
    g = gpd.GeoSeries([Point(x, y) for x, y in zip(ac.lng, ac.lat)], crs=4326).to_crs(5880)
    ac["x"] = [p.x for p in g.values]; ac["y"] = [p.y for p in g.values]
    return ac, STRtree(g.values)


def crescimento(df):
    ch = pd.read_parquet(SC / "vps" / "crescimento_hex.parquet").set_index("hex_id")
    cm = pd.read_parquet(SC / "vps" / "crescimento_municipal.parquet").set_index("cod6")
    muni = pd.read_parquet(REPO / "data/staging/brasil_priorizados.parquet", columns=["hex_id", "cod_municipio"]).drop_duplicates("hex_id").set_index("hex_id")["cod_municipio"].astype(str).str[:6]
    df = df.copy()
    df["hex7"] = [h3.latlng_to_cell(a, b, 7) for a, b in zip(df.lat, df.lng)]
    df["cres_hex_taxa"] = df["hex7"].map(ch["cres_hex_taxa"])
    df["cod6"] = df["hex7"].map(muni)
    for c in ["dim_renda_pct", "dim_pop_pct", "dim_empresas_por1k", "dim_emprego_pct", "dim_predios_pct", "dim_media"]:
        df[c] = df["cod6"].map(cm[c])
    return df


def componentes(df, polys, ac, tree, ultra_ref, auto_m):
    gu = gpd.GeoSeries([Point(x, y) for x, y in zip(ultra_ref.lng, ultra_ref.lat)], crs=4326).to_crs(5880)
    tree_u = STRtree(gu.values)
    gp = gpd.GeoSeries([Point(x, y) for x, y in zip(df.lng, df.lat)], crs=4326).to_crs(5880)
    linhas = []
    for (_, r), pt in zip(df.iterrows(), gp.values):
        o = {"pid": r.pid}
        for c in CEN:
            p = polys[c].get(r.pid)
            if p is None:
                continue
            ia = tree.query(p, predicate="contains")
            sub = ac.iloc[ia]
            sub = sub[np.hypot(sub.x - pt.x, sub.y - pt.y) >= auto_m]
            o[f"cap_real__{c}"] = float(sub.cap_real.fillna(0).sum())
            o[f"cap_rede__{c}"] = float(sub.loc[sub.classe == "mediana_rede", "cap_rede"].sum())
            o[f"n_cadeia_proxy__{c}"] = int((sub.classe == "cadeia_proxy").sum())
            o[f"n_indep__{c}"] = int((sub.classe == "indep").sum())
            iu = tree_u.query(p, predicate="contains")
            outras = ultra_ref.iloc[iu]
            outras = outras[np.hypot(np.array([q.x for q in gu.values[iu]]) - pt.x, np.array([q.y for q in gu.values[iu]]) - pt.y) >= 75]
            o[f"ultra_outras__{c}"] = float(outras["ativos_ref"].fillna(0).sum())
        linhas.append(o)
    return df.merge(pd.DataFrame(linhas), on="pid", how="left")


def esperado(d, pr, w, renda_ref, cres_z, ticket_ref=None):
    E = np.zeros(len(d))
    for j, c in enumerate(CEN):
        pop = d[f"pop__{c}"].fillna(0).to_numpy(float); renda = d[f"renda_pc__{c}"].fillna(renda_ref).to_numpy(float)
        D = pop * pr["taxa"] * (renda / renda_ref) ** pr["elast_renda"] * (1 + pr["peso_cresc"] * cres_z)
        C = (d[f"cap_real__{c}"] + d[f"cap_rede__{c}"] + d[f"n_cadeia_proxy__{c}"] * pr["proxy_cadeia"] + d[f"n_indep__{c}"] * pr["proxy_indep"]).fillna(0).to_numpy(float)
        U = d[f"ultra_outras__{c}"].fillna(0).to_numpy(float); K = d["metragem"].to_numpy(float) * pr["dens_ref"]
        E += w[j] * D * K / (K + C + U)
    if ticket_ref is None:
        return E
    return E * ticket_ref * (d["renda_pc__carro_10"].fillna(renda_ref).to_numpy(float) / renda_ref) ** pr["elast_ticket"]


def monte_carlo(d, y, grupo, ticket_ref=None):
    renda_ref = float(np.nanmedian(d["renda_pc__carro_10"]))
    cz = d["cres_hex_taxa"]; cres_z = ((cz - cz.median()) / cz.std()).fillna(0).clip(-2, 2).to_numpy()
    apr = np.zeros((N_SORTEIOS, len(d))); esp = np.zeros((N_SORTEIOS, len(d)))
    g = d[grupo].to_numpy()
    for i in range(N_SORTEIOS):
        pr = {k: RNG.uniform(*v) for k, v in FAIXAS.items()}; w = RNG.dirichlet([1, 1, 1])
        e = esperado(d, pr, w, renda_ref, cres_z, ticket_ref)
        esp[i] = e; a = y / e
        for gg in np.unique(g):
            m = g == gg; a[m] = a[m] / np.median(a[m])
        apr[i] = a
    return apr, esp


def resumo(d, apr, esp, y):
    r = pd.DataFrame({"pid": d.pid, "rede": d.rede, "metragem": d.metragem, "real": y, "esperado_mediana": np.median(esp, axis=0).round(0),
                      "aprov_mediana": np.median(apr, axis=0), "aprov_p10": np.percentile(apr, 10, axis=0), "aprov_p90": np.percentile(apr, 90, axis=0),
                      "frac_acima": (apr > 1).mean(axis=0)})
    r["leitura"] = np.where(r.frac_acima >= 0.8, "acima (robusto)", np.where(r.frac_acima <= 0.2, "abaixo (robusto)", "depende das premissas"))
    return r.sort_values("aprov_mediana", ascending=False)


def teste_diretor(d, y, rotulo):
    praca = d["renda_pc__carro_10"].rank(pct=True) * 0.5 + d["pop__carro_10"].rank(pct=True) * 0.5
    conc = (d["cap_real__carro_10"] + d["cap_rede__carro_10"] + d["n_cadeia_proxy__carro_10"] * 1800 + d["n_indep__carro_10"] * 400) / d["pop__carro_10"]
    # dentro de cada rede: ranks para tirar a escala da rede
    yr = pd.Series(y).groupby(d.rede.values).rank(pct=True).to_numpy(); m2 = d.groupby("rede")["metragem"].rank(pct=True).to_numpy()
    for nome, mod in (("praça boa", (praca > praca.median()).to_numpy()), ("concorrência per capita baixa", (conc < conc.median()).to_numpy())):
        a = spearmanr(m2[mod], yr[mod])[0]; b = spearmanr(m2[~mod], yr[~mod])[0]; bs = []
        for _ in range(2000):
            i = RNG.integers(0, len(yr), len(yr)); mm = mod[i]
            if mm.sum() > 6 and (~mm).sum() > 6:
                bs.append(spearmanr(m2[i][mm], yr[i][mm])[0] - spearmanr(m2[i][~mm], yr[i][~mm])[0])
        MD.append(f"- {rotulo} | metragem x desempenho em {nome}: rho {a:+.2f} (n={int(mod.sum())}) x {b:+.2f} fora (n={int((~mod).sum())}); diferença {a-b:+.2f} IC95 [{np.percentile(bs,2.5):+.2f}; {np.percentile(bs,97.5):+.2f}]")


def teste_cresc(d, alvo, rotulo, controle_df=True):
    MD.append(f"\n**Crescimento x {rotulo}** (Spearman; parcial = controlando DF e renda do carro 10)\n")
    linhas = []
    for c in ["cres_hex_taxa", "dim_renda_pct", "dim_pop_pct", "dim_empresas_por1k", "dim_emprego_pct", "dim_predios_pct", "dim_media"]:
        ok = d[c].notna() & pd.notna(alvo)
        if ok.sum() < 15:
            continue
        x = d.loc[ok, c].rank().to_numpy(); yv = pd.Series(alvo[ok.to_numpy()]).rank().to_numpy()
        Z = np.c_[np.ones(ok.sum()), (d.loc[ok, "uf"] == "DF").astype(float), d.loc[ok, "renda_pc__carro_10"].rank().fillna(0)]
        rx = x - Z @ np.linalg.lstsq(Z, x, rcond=None)[0]; ry = yv - Z @ np.linalg.lstsq(Z, yv, rcond=None)[0]
        rho = spearmanr(d.loc[ok, c], alvo[ok.to_numpy()])[0]; par = np.corrcoef(rx, ry)[0, 1]
        perm = [abs(np.corrcoef(RNG.permutation(rx), ry)[0, 1]) >= abs(par) for _ in range(2000)]
        bs = []
        for _ in range(1000):
            i = RNG.integers(0, len(x), len(x)); bs.append(spearmanr(d.loc[ok, c].to_numpy()[i], alvo[ok.to_numpy()][i])[0])
        linhas.append({"variavel": c, "n": int(ok.sum()), "rho": rho, "ic95": f"[{np.percentile(bs,2.5):+.2f}; {np.percentile(bs,97.5):+.2f}]", "rho_parcial": par, "p_parcial": float(np.mean(perm))})
    MD.append(pd.DataFrame(linhas).round(3).to_markdown(index=False))


def main():
    ac, tree = oferta()
    # ---------------- A) Ultra, faturamento do Financeiro
    fech = pd.read_parquet(SC / "fech_mensal_financeiro.parquet")
    fin = fech[fech.origem_faturamento.eq("financeiro") & fech.mes_completo & fech.operacao_mes_cheio]
    fat_ago = fin[fin.competencia == "2026-08"].set_index("unidade_id")["faturamento"].copy()
    # correcao informada por Felipe em 25/09: Guaruja contado 2x no Financeiro de agosto/26 (real R$ 217.525,74)
    CORRECOES_AGO = {"guaruja-sp": 217525.74}
    for k, v in CORRECOES_AGO.items():
        fat_ago.loc[k] = v
    fat_12 = fin[fin.competencia.between("2025-09", "2026-08")].groupby("unidade_id")["faturamento"].median()
    ativos_12 = fech[fech.competencia.between("2025-09", "2026-08")].groupby("unidade_id")["ativos"].median()
    bu = pd.read_parquet(ISO / "testes_v2" / "base_ultra.parquet").rename(columns={"unidade_id": "pid"})
    bu["rede"] = "ultra"; bu["fat_fin_ago"] = bu.pid.map(fat_ago); bu["fat_fin_12m"] = bu.pid.map(fat_12); bu["ativos_ref"] = bu.pid.map(ativos_12)
    ultra_ref = bu.dropna(subset=["lat"])[["pid", "lat", "lng", "ativos_ref"]]
    polys = {}
    frames = [pd.read_parquet(f, columns=["ponto_id", "tipo", "modo", "limite_s", "poligono_wkb"], filters=[("tipo", "==", "ultra")]) for f in sorted((ISO / "isocronas_v2").glob("metro_*.parquet"))]
    iso = pd.concat(frames)
    for c, (modo, lim) in CEN.items():
        s = iso[(iso.modo == modo) & (iso.limite_s == lim) & iso.poligono_wkb.notna()]
        polys[c] = dict(zip(s.ponto_id, gpd.GeoSeries([wkb.loads(b) for b in s.poligono_wkb], crs=4326).to_crs(5880).values))
    A = bu[bu.metragem.notna() & bu.fat_fin_ago.notna() & ~bu.confianca.eq("baixa") & bu["pop__carro_10"].notna()].reset_index(drop=True)
    A = crescimento(componentes(A, polys, ac, tree, ultra_ref, auto_m=2.0))
    ticket = float(np.median(A.fat_fin_ago / A.ativos_ref))
    MD.append(f"# Aproveitamento v2 — faturamento do fechamento do Financeiro\n\nUltra: N = {len(A)} (metragem + faturamento Financeiro de agosto/2026 + isócrona). Receita por ativo de referência R$ {ticket:,.0f}.\n")
    res = {}
    for nome, col in (("agosto/2026", "fat_fin_ago"), ("mediana 12 m (set/25–ago/26)", "fat_fin_12m")):
        y = A[col].to_numpy(float)
        apr, esp = monte_carlo(A, y, "rede", ticket)
        r = resumo(A, apr, esp, y); res[col] = r
        fe = np.median(esp, axis=0)
        MD.append(f"\n## Ultra — {nome}\n")
        MD.append(f"Leitura: {r.leitura.value_counts().to_dict()} | esperado x real rho {spearmanr(fe, y)[0]:+.2f}; por m² {spearmanr(fe / A.metragem, y / A.metragem)[0]:+.2f}; aproveitamento x faturamento/m² {spearmanr(r.set_index('pid').loc[A.pid,'aprov_mediana'], y / A.metragem)[0]:+.2f}")
        r.to_csv(OUT / f"ultra_{col}.csv", sep=";", encoding="utf-8-sig", index=False)
    rj = res["fat_fin_ago"].set_index("pid")[["aprov_mediana", "leitura"]].join(res["fat_fin_12m"].set_index("pid")[["aprov_mediana", "leitura"]], lsuffix="_ago", rsuffix="_12m")
    MD.append(f"\nConcordância agosto x 12 m: rho {spearmanr(rj.aprov_mediana_ago, rj.aprov_mediana_12m)[0]:+.2f}; mesma leitura em {(rj.leitura_ago == rj.leitura_12m).mean():.0%}.")
    MD.append("\n**Ultra — agosto/2026, todas as unidades**\n")
    MD.append(res["fat_fin_ago"].round(2).to_markdown(index=False))
    MD.append("\n## Hipótese do diretor e crescimento — Ultra (faturamento Financeiro agosto)\n")
    y = A.fat_fin_ago.to_numpy(float)
    teste_diretor(A, y, "Ultra faturamento")
    teste_cresc(A, res["fat_fin_ago"].set_index("pid").loc[A.pid, "aprov_mediana"].to_numpy(), "aproveitamento (Ultra, agosto)")
    teste_cresc(A, y / A.metragem.to_numpy(), "faturamento/m² (Ultra, agosto)")
    # ---------------- B) Ultra + EdC em alunos
    p = pd.read_parquet(MR / "perfil.parquet").rename(columns={"ponto_id": "pid", "marca": "rede"})
    B = p[p.rede.isin(["ultra", "engenharia_do_corpo"]) & p.metragem.notna() & (p.alunos_reais > 0) & p["pop__carro_10"].notna()].reset_index(drop=True)
    mpolys = {c: {} for c in CEN}
    for f in sorted((MR / "atributos").glob("poligonos_metro_*.parquet")):
        s = pd.read_parquet(f)
        for c, (modo, lim) in CEN.items():
            ss = s[(s.modo == modo) & (s.limite_s == lim) & s.poligono_wkb.notna()]
            mpolys[c].update(dict(zip(ss.ponto_id, gpd.GeoSeries([wkb.loads(b) for b in ss.poligono_wkb], crs=4326).to_crs(5880).values)))
    B = crescimento(componentes(B, mpolys, ac, tree, ultra_ref, auto_m=75.0))
    y = B.alunos_reais.to_numpy(float)
    apr, esp = monte_carlo(B, y, "rede")
    r = resumo(B, apr, esp, y); r.to_csv(OUT / "ultra_edc_alunos.csv", sep=";", encoding="utf-8-sig", index=False)
    MD.append(f"\n## Ultra + Engenharia do Corpo — alunos (N = {len(B)}: {B.rede.value_counts().to_dict()})\n")
    MD.append(f"Leitura: {r.leitura.value_counts().to_dict()} | esperado x real rho {spearmanr(np.median(esp,axis=0), y)[0]:+.2f} (dentro da rede: Ultra {spearmanr(np.median(esp,axis=0)[B.rede=='ultra'], y[B.rede=='ultra'])[0]:+.2f}, EdC {spearmanr(np.median(esp,axis=0)[B.rede!='ultra'], y[B.rede!='ultra'])[0]:+.2f})")
    teste_diretor(B, y, "Ultra+EdC alunos")
    teste_cresc(B, r.set_index("pid").loc[B.pid, "aprov_mediana"].to_numpy(), "aproveitamento em alunos (Ultra + EdC)")
    # ---------------- C) SkyFit: replicacao do crescimento (sem metragem)
    S = p[(p.rede == "skyfit") & (p.alunos_reais > 0) & p["pop__carro_10"].notna()].reset_index(drop=True)
    S = crescimento(S)
    MD.append(f"\n## Replicação independente na SkyFit (N = {len(S)}, alunos relativos à mediana da rede; sem metragem)\n")
    teste_cresc(S, (S.alunos_reais / S.alunos_reais.median()).to_numpy(), "alunos SkyFit")
    (OUT / "resultados.md").write_text("\n".join(MD), encoding="utf-8")
    print("\n".join(l for l in MD if not l.startswith("|") or "variavel" in l or l.count("|") < 12))


if __name__ == "__main__":
    main()
