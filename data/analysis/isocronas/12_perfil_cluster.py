# -*- coding: utf-8 -*-
"""Multirede — etapas 3 e 4: ficha de perfil por unidade, clusterizacao em dois niveis e leitura de desempenho.

Nivel 1 (REGIAO, todas as unidades com isocrona): log pop 1 km, razao de alcance (pop carro 5 / pop 1 km),
km de rua em 5 min, fracao a pe' (pop a pe' 15 / pop 1 km), renda carro 5, pressao de oferta (academias
ponderadas por 10 mil hab em carro 5). KMeans k=3..6, escolha por silhueta + estabilidade (ARI em 200 bootstraps).
Nivel 2 (IMOVEL, Ultra + EdC com metragem): metragem, vagas por 1.000 m2, tipo de imovel (so' EdC).
Desempenho (descritivo): alunos RELATIVOS a mediana da propria rede (redes tem escalas diferentes) por cluster;
alunos/m2 por cluster (Ultra+EdC). Modelo simples out-of-fold: log(alunos) ~ rede + [1 km] + [isocrona],
GroupKFold por metro, ridge, bootstrap do ganho.
Saidas: iso/multirede/perfil.parquet, cluster_resultados.md, cluster_mapa.png
"""
import re
import unicodedata
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kruskal, spearmanr
from sklearn.cluster import KMeans
from sklearn.linear_model import Ridge
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
ISO = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad\iso")
REPO = Path(r"C:\dev\motor-de-expansao")
MR = ISO / "multirede"
RNG = np.random.default_rng(42)
MD = []


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper()
    s = re.sub(r"^EC\s*-\s*", "", s.strip())
    s = re.sub(r"[,/-]\s*(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)\s*$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def perfil():
    pts = pd.read_parquet(MR / "pontos.parquet")
    a = pd.concat([pd.read_parquet(f) for f in sorted((MR / "atributos").glob("metro_*.parquet"))], ignore_index=True)
    a["cenario"] = a["cenario"].str.replace("min", "", regex=False)
    w = a.pivot_table(index="ponto_id", columns="cenario", values=["pop", "renda_pc", "oferta_ponderada", "km_rua", "area_km2", "n_ultra", "truncada"], aggfunc="first")
    w.columns = [f"{v}__{c}" for v, c in w.columns]
    p = pts.set_index("ponto_id").join(w, how="inner").reset_index()
    p["razao_alcance"] = p["pop__carro_5"] / p["pop__circulo_1km"].replace(0, np.nan)
    p["fracao_pe"] = p["pop__pe_15"] / p["pop__circulo_1km"].replace(0, np.nan)
    p["pressao_oferta"] = 1e4 * p["oferta_ponderada__carro_5"] / p["pop__carro_5"].replace(0, np.nan)
    # vagas e tipo de imovel
    u = pd.read_excel(REPO / "data/ultra/dados_academias.xlsx", sheet_name="Plan1"); u.columns = [str(c).strip() for c in u.columns]
    u = pd.DataFrame({"chave": u["LOCALIZACAO"].map(norm), "vagas": pd.to_numeric(u["Vagas"], errors="coerce")})
    e = pd.read_excel(REPO / "data/validacao/academias_engenharia_do_corpo.xlsx", sheet_name="Academias"); e.columns = [str(c).strip() for c in e.columns]
    e = pd.DataFrame({"chave": e["Unidade"].map(norm), "vagas": pd.to_numeric(e["Vagas"], errors="coerce"), "tipo_imovel": e["Tipo de Imóvel"]})
    p["chave"] = p["unidade"].map(norm)
    pu = p[p.marca == "ultra"].merge(u.drop_duplicates("chave"), on="chave", how="left")
    pe = p[p.marca == "engenharia_do_corpo"].merge(e.drop_duplicates("chave"), on="chave", how="left")
    p = pd.concat([pu, pe, p[p.marca == "skyfit"]], ignore_index=True)
    p["alunos_por_m2"] = p["alunos_reais"] / p["metragem"]
    p["vagas_por_1000m2"] = 1000 * p["vagas"] / p["metragem"]
    p["alunos_rel_rede"] = p["alunos_reais"] / p.groupby("marca")["alunos_reais"].transform("median")
    MD.append(f"Ficha: {len(p)} unidades {p.marca.value_counts().to_dict()} | vagas casadas: Ultra {pu.vagas.notna().sum()}/{len(pu)}, EdC {pe.vagas.notna().sum()}/{len(pe)} | tipo de imóvel EdC {pe.tipo_imovel.notna().sum()}/{len(pe)}")
    return p


FEAT_REG = {"log_pop_1km": lambda p: np.log1p(p["pop__circulo_1km"]), "log_razao_alcance": lambda p: np.log(p["razao_alcance"].clip(lower=0.5)),
            "log_km_rua_5min": lambda p: np.log1p(p["km_rua__carro_5"]), "fracao_pe": lambda p: p["fracao_pe"].clip(upper=1.5),
            "log_renda_5min": lambda p: np.log(p["renda_pc__carro_5"].clip(lower=300)), "log_pressao_oferta": lambda p: np.log1p(p["pressao_oferta"])}


def cluster_regiao(p):
    X = pd.DataFrame({k: f(p) for k, f in FEAT_REG.items()})
    ok = X.notna().all(axis=1)
    Xs = StandardScaler().fit_transform(X[ok])
    MD.append("\n## Nível 1 — perfil de região\n")
    MD.append(f"N = {ok.sum()} unidades (sem dado completo: {(~ok).sum()}). Variáveis: {', '.join(FEAT_REG)}.\n")
    linhas = []
    for k in range(3, 7):
        km = KMeans(k, n_init=20, random_state=42).fit(Xs)
        sil = silhouette_score(Xs, km.labels_)
        aris = []
        for b in range(200):
            idx = RNG.integers(0, len(Xs), len(Xs))
            kb = KMeans(k, n_init=5, random_state=b).fit(Xs[idx])
            aris.append(adjusted_rand_score(km.labels_, kb.predict(Xs)))
        linhas.append({"k": k, "silhueta": sil, "estabilidade_ARI_mediana": float(np.median(aris)), "ARI_p10": float(np.percentile(aris, 10))})
    t = pd.DataFrame(linhas); MD.append(t.round(3).to_markdown(index=False))
    kbest = int(t.sort_values(["estabilidade_ARI_mediana", "silhueta"], ascending=False).query("estabilidade_ARI_mediana >= 0.75").k.min()) if (t.estabilidade_ARI_mediana >= 0.75).any() else int(t.sort_values("estabilidade_ARI_mediana").k.iloc[-1])
    km = KMeans(kbest, n_init=50, random_state=42).fit(Xs)
    p.loc[ok, "cluster_regiao"] = km.labels_
    MD.append(f"\nEscolhido k = {kbest} (menor k com estabilidade ARI ≥ 0,75; senão o mais estável).\n")
    desc = p[ok].groupby("cluster_regiao").agg(n=("ponto_id", "size"), ultra=("marca", lambda s: (s == "ultra").sum()), edc=("marca", lambda s: (s == "engenharia_do_corpo").sum()),
                                              skyfit=("marca", lambda s: (s == "skyfit").sum()), pop_1km=("pop__circulo_1km", "median"), pop_5min=("pop__carro_5", "median"),
                                              razao_alcance=("razao_alcance", "median"), km_rua_5min=("km_rua__carro_5", "median"), fracao_pe=("fracao_pe", "median"),
                                              renda_5min=("renda_pc__carro_5", "median"), pressao_oferta=("pressao_oferta", "median"),
                                              alunos_rel_rede=("alunos_rel_rede", "median"), alunos_por_m2=("alunos_por_m2", "median"))
    MD.append(desc.round(2).to_markdown())
    grupos = [g["alunos_rel_rede"].dropna().values for _, g in p[ok].groupby("cluster_regiao")]
    h, pv = kruskal(*grupos)
    MD.append(f"\nAlunos relativos à mediana da própria rede, por cluster: Kruskal-Wallis H={h:.2f}, p={pv:.3f}.")
    for marca in ("ultra", "skyfit"):
        gm = [g["alunos_rel_rede"].dropna().values for _, g in p[ok & (p.marca == marca)].groupby("cluster_regiao") if len(g) >= 5]
        if len(gm) >= 2:
            h, pv = kruskal(*gm); MD.append(f"- só {marca}: H={h:.2f}, p={pv:.3f}")
    gm = [g["alunos_por_m2"].dropna().values for _, g in p[ok & p.metragem.notna()].groupby("cluster_regiao") if g["alunos_por_m2"].notna().sum() >= 5]
    if len(gm) >= 2:
        h, pv = kruskal(*gm); MD.append(f"- alunos/m² (Ultra + EdC): H={h:.2f}, p={pv:.3f}")
    return p


def nivel_imovel(p):
    MD.append("\n## Nível 2 — imóvel (Ultra + Engenharia do Corpo com metragem)\n")
    d = p[p.metragem.notna()].copy()
    d["porte"] = pd.cut(d["metragem"], [0, 1300, 1800, 1e9], labels=["até 1.300 m²", "1.300–1.800 m²", "> 1.800 m²"])
    d["estacionamento"] = pd.cut(d["vagas_por_1000m2"], [-1, 5, 25, 1e9], labels=["sem/pouca vaga", "média", "muita vaga"])
    MD.append(f"N = {len(d)}; vagas presentes em {d.vagas.notna().sum()}.\n")
    for col in ("porte", "estacionamento", "tipo_imovel"):
        t = d.groupby([col, "marca"], observed=True).agg(n=("ponto_id", "size"), alunos_por_m2=("alunos_por_m2", "median")).unstack("marca")
        MD.append(f"\n**{col}**\n"); MD.append(t.round(2).to_markdown())
    ct = pd.crosstab(d["cluster_regiao"], d["porte"]); MD.append("\n**cluster de região x porte (contagem)**\n"); MD.append(ct.to_markdown())
    rho = spearmanr(d["vagas_por_1000m2"], d["alunos_por_m2"], nan_policy="omit")[0]
    MD.append(f"\nSpearman vagas/1.000 m² x alunos/m²: {rho:+.2f}")


def modelo_oof(p):
    MD.append("\n## Modelo simples out-of-fold (log alunos), GroupKFold por metro\n")
    d = p[p["alunos_reais"] > 0].dropna(subset=["pop__circulo_1km", "pop__carro_5", "renda_pc__carro_5", "renda_pc__circulo_1km", "pop__pe_15", "km_rua__carro_5"]).copy()
    y = np.log(d["alunos_reais"].to_numpy(float)); g = d["metro"].to_numpy()
    rede = pd.get_dummies(d["marca"], drop_first=True).astype(float)
    blocos = {
        "B0 só rede": rede,
        "B1 rede + círculo 1 km": pd.concat([rede, np.log1p(d[["pop__circulo_1km", "oferta_ponderada__circulo_1km"]]), np.log(d[["renda_pc__circulo_1km"]].clip(lower=300))], axis=1),
        "I rede + círculo + isócrona": pd.concat([rede, np.log1p(d[["pop__circulo_1km", "oferta_ponderada__circulo_1km", "pop__carro_5", "oferta_ponderada__carro_5", "km_rua__carro_5", "pop__pe_15"]]),
                                                 np.log(d[["renda_pc__circulo_1km", "renda_pc__carro_5"]].clip(lower=300))], axis=1),
    }
    oofs = {}
    for nome, X in blocos.items():
        X = X.to_numpy(float); oof = np.zeros(len(y))
        for tr, te in GroupKFold(n_splits=10).split(X, y, g):
            oof[te] = make_pipeline(StandardScaler(), Ridge(alpha=1.0)).fit(X[tr], y[tr]).predict(X[te])
        oofs[nome] = oof
    r2 = lambda o, i: 1 - ((y[i] - o[i]) ** 2).sum() / ((y[i] - y[i].mean()) ** 2).sum()
    tudo = np.arange(len(y))
    for nome in blocos:
        MD.append(f"- {nome}: R² OOF {r2(oofs[nome], tudo):+.3f}")
    ganhos = []
    for _ in range(2000):
        i = RNG.integers(0, len(y), len(y)); ganhos.append(r2(oofs["I rede + círculo + isócrona"], i) - r2(oofs["B1 rede + círculo 1 km"], i))
    MD.append(f"- ganho da isócrona sobre o círculo: {r2(oofs['I rede + círculo + isócrona'], tudo) - r2(oofs['B1 rede + círculo 1 km'], tudo):+.3f} IC95 [{np.percentile(ganhos, 2.5):+.3f}; {np.percentile(ganhos, 97.5):+.3f}] (N = {len(y)}, {len(np.unique(g))} metros)")


def mapa(p):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    d = p.dropna(subset=["cluster_regiao"])
    fig, ax = plt.subplots(1, 2, figsize=(14, 6))
    for c, g in d.groupby("cluster_regiao"):
        ax[0].scatter(np.log10(g["pop__circulo_1km"] + 1), g["razao_alcance"], s=18, label=f"cluster {int(c)} (n={len(g)})")
        ax[1].scatter(g["lng"], g["lat"], s=10)
    ax[0].set_yscale("log"); ax[0].set_xlabel("log10 população no raio de 1 km"); ax[0].set_ylabel("razão de alcance (pop 5 min carro / pop 1 km)"); ax[0].legend(fontsize=8)
    ax[1].set_title("posição das unidades"); ax[1].set_aspect("equal")
    fig.tight_layout(); fig.savefig(MR / "cluster_mapa.png", dpi=120)


def main():
    p = perfil(); p = cluster_regiao(p); nivel_imovel(p); modelo_oof(p); mapa(p)
    p.to_parquet(MR / "perfil.parquet", index=False)
    (MR / "cluster_resultados.md").write_text("\n".join(MD), encoding="utf-8"); print("\n".join(MD))


if __name__ == "__main__":
    main()
