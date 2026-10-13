# -*- coding: utf-8 -*-
"""Aproveitamento do potencial por unidade Ultra (itens 1, 2, 4, 5 + crescimento). Modelo DECLARADO, nao preditivo.

Para cada unidade Ultra e cada cenario de catchment (isocrona v2 de carro 5 / carro 10 / a pe' 15):
  demanda D   = pop * taxa * (renda / renda_ref) ** elast_renda * (1 + peso_cresc * cres_hex_padronizado)
  oferta C    = soma da capacidade dos concorrentes DENTRO da isocrona: alunos reais (crosswalk, confianca alta)
                > mediana real da rede > proxy de cadeia; independentes do agregador = proxy_indep
  Ultra outra = ativos (12 m) das OUTRAS unidades Ultra dentro da isocrona
  capacidade propria K = metragem * dens_ref (alunos/m2)
  alunos esperados  E = D * K / (K + C + Ultra_outra)          (captura proporcional a capacidade: hipotese do diretor,
                                                              academia maior leva mais onde a concorrencia e' menor)
  faturamento esperado F = E * ticket_ref * (renda / renda_ref) ** elast_ticket
  aproveitamento = real / esperado  (alunos: ativos 12 m; faturamento: faturamento 12 m)
Estresse: 2.000 sorteios das premissas (faixas abaixo). Por unidade: mediana, IC80 do aproveitamento, fracao dos
sorteios acima de 1 e estabilidade do rank. Testes: correlacao esperado x real; interacao metragem x praca/concorrencia;
crescimento (hex e municipio) x desempenho e x aproveitamento.
Saidas: iso/aproveitamento/unidades.csv, resultados.md, graficos.
"""
import json
import math
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from shapely import wkb
from shapely.geometry import Point
from shapely.strtree import STRtree

warnings.filterwarnings("ignore")
SC = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad")
ISO = SC / "iso"; OUT = ISO / "aproveitamento"; OUT.mkdir(exist_ok=True)
RNG = np.random.default_rng(42)
CEN = {"carro_5": ("carro", 300), "carro_10": ("carro", 600), "pe_15": ("pe", 900)}
FAIXAS = {  # premissas estressadas (min, max) — uniforme
    "taxa": (0.10, 0.25),            # penetracao fitness (DEC-060 = 17,35%)
    "elast_renda": (0.0, 1.0),       # quanto a renda amplia a demanda
    "elast_ticket": (0.0, 0.6),      # quanto a renda amplia o ticket
    "proxy_indep": (150, 800),       # alunos de uma independente sem dado
    "proxy_cadeia": (1000, 2500),    # alunos de uma cadeia sem dado
    "dens_ref": (1.2, 2.2),          # alunos/m2 da capacidade propria
    "peso_cresc": (0.0, 0.3),        # efeito do crescimento do hexagono na demanda
}
MD = []


def poligonos_ultra():
    frames = []
    for f in sorted((ISO / "isocronas_v2").glob("metro_*.parquet")):
        d = pd.read_parquet(f, columns=["ponto_id", "tipo", "modo", "limite_s", "poligono_wkb"], filters=[("tipo", "==", "ultra")])
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    out = {}
    for nome, (modo, lim) in CEN.items():
        s = d[(d.modo == modo) & (d.limite_s == lim) & d.poligono_wkb.notna()]
        out[nome] = dict(zip(s.ponto_id, gpd.GeoSeries([wkb.loads(b) for b in s.poligono_wkb], crs=4326).to_crs(5880).values))
    return out


def main():
    bu = pd.read_parquet(ISO / "testes_v2" / "base_ultra.parquet")
    polys = poligonos_ultra()
    # ---- oferta: pontos com capacidade real quando existe
    ac = pd.read_parquet(ISO / "academias_pontos.parquet")
    ac = ac[ac["tipo"] != "cadeia_agregador_com_pin"].reset_index(drop=True)
    cw = pd.read_parquet(SC / "vps" / "alunos_reais_por_unidade.parquet")
    cw = cw[(cw.confianca_match == "alta") & (cw.alunos_total > 0)]
    real = cw.groupby("concorrente_id")["alunos_total"].median()
    med_rede = cw.groupby("rede")["alunos_total"].median()
    ac["cap_real"] = ac["id"].map(real)
    ac["cap_rede"] = ac["rede"].map(med_rede)
    ac["classe"] = np.where(ac["cap_real"].notna(), "real", np.where(ac["cap_rede"].notna(), "mediana_rede", np.where(ac["tipo"] == "independente_agregador", "indep", "cadeia_proxy")))
    MD.append(f"Oferta: {len(ac):,} academias; capacidade real {int((ac.classe=='real').sum())}, mediana da rede {int((ac.classe=='mediana_rede').sum())}, cadeia sem dado {int((ac.classe=='cadeia_proxy').sum())}, independentes {int((ac.classe=='indep').sum())}.")
    ga = gpd.GeoSeries([Point(x, y) for x, y in zip(ac.lng, ac.lat)], crs=4326).to_crs(5880)
    tree = STRtree(ga.values)
    # Ultra: ativos 12 m como "capacidade" das outras unidades
    ug = bu.dropna(subset=["lat"]).reset_index(drop=True)
    gu = gpd.GeoSeries([Point(x, y) for x, y in zip(ug.lng, ug.lat)], crs=4326).to_crs(5880)
    tree_u = STRtree(gu.values)
    # crescimento
    ch = pd.read_parquet(SC / "vps" / "crescimento_hex.parquet").set_index("hex_id")
    cm = pd.read_parquet(SC / "vps" / "crescimento_municipal.parquet")
    import h3
    bu["hex7"] = [h3.latlng_to_cell(a, b, 7) if pd.notna(a) else None for a, b in zip(bu.lat, bu.lng)]
    bu["cres_hex_taxa"] = bu["hex7"].map(ch["cres_hex_taxa"])
    # municipio via cod da carteira de hexagonos (cod_municipio) -> cod6
    cart = pd.read_parquet(Path(r"C:\dev\motor-de-expansao\data\staging\hexagonos_mercado_mapeado.parquet"), columns=["hex_id"]) if False else None
    # ---- componentes por unidade e cenario (independem das premissas, exceto capacidades proxy)
    comp = []
    for _, u in bu.iterrows():
        r = {"unidade_id": u.unidade_id}
        for c, pd_ in polys.items():
            p = pd_.get(u.unidade_id)
            if p is None:
                continue
            ia = tree.query(p, predicate="contains")
            sub = ac.iloc[ia]
            r[f"cap_real__{c}"] = float(sub.cap_real.fillna(0).sum())
            r[f"cap_rede__{c}"] = float(sub.loc[sub.classe == "mediana_rede", "cap_rede"].sum())
            r[f"n_cadeia_proxy__{c}"] = int((sub.classe == "cadeia_proxy").sum())
            r[f"n_indep__{c}"] = int((sub.classe == "indep").sum())
            iu = tree_u.query(p, predicate="contains")
            outras = ug.iloc[iu]; outras = outras[outras.unidade_id != u.unidade_id]
            r[f"ultra_outras__{c}"] = float(outras["ativos_med_12m"].fillna(outras["ativos_med"]).fillna(0).sum())
        comp.append(r)
    comp = pd.DataFrame(comp)
    d = bu.merge(comp, on="unidade_id", how="left")
    alvo = d[d.metragem.notna() & d.fat_med_12m.notna() & d["pop__carro_10"].notna() & ~d.confianca.eq("baixa")].reset_index(drop=True)
    MD.append(f"Unidades no modelo: {len(alvo)} (metragem + faturamento 12 m + isócrona; coordenada não baixa).")
    renda_ref = float(np.nanmedian(alvo["renda_pc__carro_10"]))
    ticket_ref = float(np.nanmedian(alvo["fat_med_12m"] / alvo["ativos_med_12m"]))
    cres_z = ((alvo["cres_hex_taxa"] - alvo["cres_hex_taxa"].median()) / alvo["cres_hex_taxa"].std()).fillna(0).clip(-2, 2)
    # ---- Monte Carlo
    N = 2000
    apr_fat = np.zeros((N, len(alvo))); apr_al = np.zeros((N, len(alvo))); esp_fat = np.zeros((N, len(alvo)))
    pesos_cen = np.zeros((N, 3))
    for i in range(N):
        pr = {k: RNG.uniform(*v) for k, v in FAIXAS.items()}
        w = RNG.dirichlet([1, 1, 1]); pesos_cen[i] = w
        E = np.zeros(len(alvo))
        for j, c in enumerate(CEN):
            pop = alvo[f"pop__{c}"].to_numpy(float); renda = alvo[f"renda_pc__{c}"].fillna(renda_ref).to_numpy(float)
            D = pop * pr["taxa"] * (renda / renda_ref) ** pr["elast_renda"] * (1 + pr["peso_cresc"] * cres_z.to_numpy())
            C = (alvo[f"cap_real__{c}"] + alvo[f"cap_rede__{c}"] + alvo[f"n_cadeia_proxy__{c}"] * pr["proxy_cadeia"] + alvo[f"n_indep__{c}"] * pr["proxy_indep"]).fillna(0).to_numpy(float)
            U = alvo[f"ultra_outras__{c}"].fillna(0).to_numpy(float)
            K = alvo["metragem"].to_numpy(float) * pr["dens_ref"]
            E += w[j] * D * K / (K + C + U)
        renda10 = alvo["renda_pc__carro_10"].fillna(renda_ref).to_numpy(float)
        F = E * ticket_ref * (renda10 / renda_ref) ** pr["elast_ticket"]
        esp_fat[i] = F
        apr_fat[i] = alvo["fat_med_12m"].to_numpy(float) / F
        apr_al[i] = alvo["ativos_med_12m"].to_numpy(float) / E
        # nivel absoluto nao e' calibrado (depende quase so' da taxa): normaliza pela mediana da rede no sorteio
        apr_fat[i] /= np.median(apr_fat[i]); apr_al[i] /= np.median(apr_al[i])
    # ---- resumo por unidade
    rank = np.argsort(np.argsort(-apr_fat, axis=1), axis=1) + 1
    res = pd.DataFrame({
        "unidade_id": alvo.unidade_id, "uf": alvo.uf, "metragem": alvo.metragem, "fat_12m": alvo.fat_med_12m, "ativos_12m": alvo.ativos_med_12m,
        "pop_carro10": alvo["pop__carro_10"].round(0), "renda_carro10": alvo["renda_pc__carro_10"].round(0), "cres_hex_taxa": alvo.cres_hex_taxa,
        "fat_esperado_mediana": np.median(esp_fat, axis=0).round(0),
        "aprov_fat_mediana": np.median(apr_fat, axis=0), "aprov_fat_p10": np.percentile(apr_fat, 10, axis=0), "aprov_fat_p90": np.percentile(apr_fat, 90, axis=0),
        "frac_acima_de_1": (apr_fat > 1).mean(axis=0), "aprov_alunos_mediana": np.median(apr_al, axis=0),
        "rank_mediano": np.median(rank, axis=0), "rank_p10": np.percentile(rank, 10, axis=0), "rank_p90": np.percentile(rank, 90, axis=0),
    })
    res["leitura"] = np.where(res.frac_acima_de_1 >= 0.8, "acima da rede para o potencial (robusto)", np.where(res.frac_acima_de_1 <= 0.2, "abaixo da rede para o potencial (robusto)", "depende das premissas"))
    res = res.sort_values("aprov_fat_mediana", ascending=False)
    res.to_csv(OUT / "unidades.csv", sep=";", encoding="utf-8-sig", index=False)
    MD.append(f"\nPremissas estressadas (2.000 sorteios): {json.dumps(FAIXAS)}; pesos dos catchments (carro 5, carro 10, a pé 15) sorteados; renda de referência R$ {renda_ref:,.0f}; receita por aluno de referência R$ {ticket_ref:,.0f}.\n")
    MD.append("**Leitura por unidade:** " + ", ".join(f"{k} {v}" for k, v in res.leitura.value_counts().items()))
    MD.append(f"Amplitude do rank (p90 − p10) mediana: {np.median(res.rank_p90 - res.rank_p10):.0f} posições em {len(res)}.\n")
    cols = ["unidade_id", "metragem", "fat_12m", "fat_esperado_mediana", "aprov_fat_mediana", "aprov_fat_p10", "aprov_fat_p90", "frac_acima_de_1", "rank_p10", "rank_p90", "leitura"]
    MD.append("**10 com maior aproveitamento**\n"); MD.append(res[cols].head(10).round(2).to_markdown(index=False))
    MD.append("\n**10 com menor aproveitamento**\n"); MD.append(res[cols].tail(10).round(2).to_markdown(index=False))
    # ---- testes
    MD.append("\n## Testes\n")
    fe = np.median(esp_fat, axis=0)
    r1 = spearmanr(fe, alvo.fat_med_12m)[0]; r1m = spearmanr(fe / alvo.metragem, alvo.fat_med_12m / alvo.metragem)[0]
    rs = [spearmanr(esp_fat[i], alvo.fat_med_12m)[0] for i in range(0, N, 10)]
    MD.append(f"- Esperado x real (faturamento): rho {r1:+.2f} (entre sorteios p10–p90: {np.percentile(rs,10):+.2f} a {np.percentile(rs,90):+.2f}); por m²: {r1m:+.2f}. Sem correlação, o aproveitamento é dominado pelo real e o ranking vira o de faturamento/m² com ajuste de premissas.")
    rr = spearmanr(res.set_index("unidade_id").loc[alvo.unidade_id, "aprov_fat_mediana"], alvo.fat_med_12m / alvo.metragem)[0]
    MD.append(f"- Aproveitamento x faturamento/m²: rho {rr:+.2f}.")
    # hipotese do diretor: metragem rende mais em praca boa / concorrencia menor
    praca = alvo["renda_pc__carro_10"].rank(pct=True) * 0.5 + alvo["pop__carro_10"].rank(pct=True) * 0.5
    conc = (alvo["cap_real__carro_10"] + alvo["cap_rede__carro_10"] + alvo["n_cadeia_proxy__carro_10"] * 1800 + alvo["n_indep__carro_10"] * 400) / alvo["pop__carro_10"]
    y = alvo.fat_med_12m.to_numpy(float); m2 = alvo.metragem.to_numpy(float)
    for nome, mod in (("praça boa (renda+pop acima da mediana)", praca > 0.5), ("concorrência per capita abaixo da mediana", conc < conc.median())):
        a = spearmanr(m2[mod], y[mod])[0]; b = spearmanr(m2[~mod], y[~mod])[0]
        boots = []
        for _ in range(2000):
            idx = RNG.integers(0, len(y), len(y)); mm = mod.to_numpy()[idx]
            if mm.sum() > 5 and (~mm).sum() > 5:
                boots.append(spearmanr(m2[idx][mm], y[idx][mm])[0] - spearmanr(m2[idx][~mm], y[idx][~mm])[0])
        MD.append(f"- Metragem x faturamento em {nome}: rho {a:+.2f} (n={int(mod.sum())}) contra {b:+.2f} fora (n={int((~mod).sum())}); diferença {a-b:+.2f} IC95 [{np.percentile(boots,2.5):+.2f}; {np.percentile(boots,97.5):+.2f}].")
    vag = pd.read_excel(Path(r"C:\dev\motor-de-expansao\data\ultra\dados_academias.xlsx"), sheet_name="Plan1")
    vag.columns = [str(c).strip() for c in vag.columns]
    import re, unicodedata
    nrm = lambda s: re.sub(r"\s+", " ", re.sub(r"(?:\s*[/-]\s*|\s+)(?:[A-Z]{2})$", "", unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip())).strip()
    vmap = dict(zip(vag["LOCALIZACAO"].map(nrm), pd.to_numeric(vag["Vagas"], errors="coerce")))
    alvo["vagas"] = alvo["nome"].map(nrm).map(vmap)
    ok = alvo.vagas.notna()
    MD.append(f"- Vagas x faturamento: rho {spearmanr(alvo.vagas[ok], alvo.fat_med_12m[ok])[0]:+.2f}; vagas x faturamento/m²: {spearmanr(alvo.vagas[ok], (alvo.fat_med_12m/alvo.metragem)[ok])[0]:+.2f} (n={int(ok.sum())}).")
    # crescimento
    cmi = cm.set_index("cod6")
    pts_muni = pd.read_parquet(Path(r"C:\dev\motor-de-expansao\data\staging\brasil_priorizados.parquet"), columns=["hex_id", "cod_municipio"]) if Path(r"C:\dev\motor-de-expansao\data\staging\brasil_priorizados.parquet").exists() else None
    if pts_muni is not None and "cod_municipio" in pts_muni:
        mm = pts_muni.drop_duplicates("hex_id").set_index("hex_id")["cod_municipio"].astype(str).str[:6]
        alvo["cod6"] = alvo["hex7"].map(mm)
    for c in ["dim_renda_pct", "dim_empresas_por1k", "dim_emprego_pct", "dim_pop_pct", "dim_media"]:
        if "cod6" in alvo and c in cmi:
            alvo[c] = alvo["cod6"].map(cmi[c])
    aprov = res.set_index("unidade_id").loc[alvo.unidade_id, "aprov_fat_mediana"].to_numpy()
    for c in ["cres_hex_taxa", "dim_renda_pct", "dim_empresas_por1k", "dim_emprego_pct", "dim_pop_pct", "dim_media"]:
        if c in alvo and alvo[c].notna().sum() > 10:
            ok = alvo[c].notna()
            MD.append(f"- Crescimento {c} (n={int(ok.sum())}): x faturamento/m² rho {spearmanr(alvo[c][ok], (alvo.fat_med_12m/alvo.metragem)[ok])[0]:+.2f}; x aproveitamento rho {spearmanr(alvo[c][ok], aprov[ok.to_numpy()])[0]:+.2f}; x churn {spearmanr(alvo[c][ok], alvo.churn_med_12m[ok], nan_policy='omit')[0]:+.2f}")
    # sensibilidade: qual premissa mais mexe no rank
    MD.append("\n## Qual premissa mais mexe no resultado\n")
    # refaz com cada premissa variando sozinha (demais no meio da faixa)
    base_pr = {k: (a + b) / 2 for k, (a, b) in FAIXAS.items()}
    def calcula(pr, w=(1/3, 1/3, 1/3)):
        E = np.zeros(len(alvo))
        for j, c in enumerate(CEN):
            pop = alvo[f"pop__{c}"].to_numpy(float); renda = alvo[f"renda_pc__{c}"].fillna(renda_ref).to_numpy(float)
            D = pop * pr["taxa"] * (renda / renda_ref) ** pr["elast_renda"] * (1 + pr["peso_cresc"] * cres_z.to_numpy())
            C = (alvo[f"cap_real__{c}"] + alvo[f"cap_rede__{c}"] + alvo[f"n_cadeia_proxy__{c}"] * pr["proxy_cadeia"] + alvo[f"n_indep__{c}"] * pr["proxy_indep"]).fillna(0).to_numpy(float)
            U = alvo[f"ultra_outras__{c}"].fillna(0).to_numpy(float); K = alvo["metragem"].to_numpy(float) * pr["dens_ref"]
            E += w[j] * D * K / (K + C + U)
        F = E * ticket_ref * (alvo["renda_pc__carro_10"].fillna(renda_ref).to_numpy(float) / renda_ref) ** pr["elast_ticket"]
        return alvo.fat_med_12m.to_numpy(float) / F
    _c = calcula
    calcula = lambda pr, w=(1/3, 1/3, 1/3): (lambda x: x / np.median(x))(_c(pr, w))
    ref = calcula(base_pr)
    linhas = []
    for k, (a, b) in FAIXAS.items():
        lo = calcula({**base_pr, k: a}); hi = calcula({**base_pr, k: b})
        linhas.append({"premissa": k, "faixa": f"{a}–{b}", "rho_rank_extremos": spearmanr(lo, hi)[0], "unidades_que_trocam_de_lado_de_1": int(((lo > 1) != (hi > 1)).sum())})
    for nome, w in (("só carro 5", (1, 0, 0)), ("só carro 10", (0, 1, 0)), ("só a pé 15", (0, 0, 1))):
        x = calcula(base_pr, w); linhas.append({"premissa": f"catchment {nome}", "faixa": "vs peso igual", "rho_rank_extremos": spearmanr(ref, x)[0], "unidades_que_trocam_de_lado_de_1": int(((ref > 1) != (x > 1)).sum())})
    MD.append(pd.DataFrame(linhas).round(3).to_markdown(index=False))
    alvo.to_parquet(OUT / "base_modelo.parquet", index=False)
    (OUT / "resultados.md").write_text("\n".join(MD), encoding="utf-8")
    print("\n".join(MD))


if __name__ == "__main__":
    main()
