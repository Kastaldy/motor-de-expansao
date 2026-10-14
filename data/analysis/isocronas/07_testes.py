# -*- coding: utf-8 -*-
"""Etapa 7 — implementacao de referencia dos testes pre-registrados (protocolo_isocronas.md).

Uso: venv-iso\\python 07_testes.py
Saida: SCRATCH/iso/testes/resultados_07.json e resultados_07.md
T1 medicao | T2 preferencia revelada (AUC OOF, GroupKFold por metro) | T3 previsao E8 (LOO/GroupKFold, ridge)
T4 funil (troca de rotulo Livre/Adensar/Disputa) | T5 canibalizacao (descritivo)
"""
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold, LeaveOneOut
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
SCRATCH = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad")
T = SCRATCH / "iso" / "testes"
SEED = 42
RNG = np.random.default_rng(SEED)
CONC_ADENSAR_MAX = 2
R = {}
MD = []


def md(s=""):
    MD.append(s)


def log1p_cols(df, cols):
    X = df[cols].copy()
    for c in cols:
        if not c.startswith("renda"):
            X[c] = np.log1p(X[c].clip(lower=0))
        else:
            X[c] = np.log(X[c].clip(lower=50))
    return X


def boot_ci(stat_fn, n, B=2000):
    vals = []
    for _ in range(B):
        idx = RNG.integers(0, n, n)
        vals.append(stat_fn(idx))
    vals = np.array(vals)
    return float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5))


# ------------------------------------------------------------------ T1
def t1(bu, bh):
    md("## T1 — Medição: isócrona x círculo de 1 km x hexágono res-7")
    out = {}
    for nome, df in (("ultra", bu), ("hex_carteira", bh)):
        df = df[df["pop__carro_5"].notna()]
        linhas = []
        for c in ["carro_5", "carro_10", "carro_15", "pe_10", "pe_15", "hex_r7"]:
            razao = (df[f"pop__{c}"] / df["pop__circulo_1km"].replace(0, np.nan))
            rho_pop = spearmanr(df[f"pop__{c}"], df["pop__circulo_1km"], nan_policy="omit")[0]
            rho_of = spearmanr(df[f"oferta_ponderada__{c}"], df["oferta_ponderada__circulo_1km"], nan_policy="omit")[0]
            rho_re = spearmanr(df[f"renda_pc__{c}"], df["renda_pc__circulo_1km"], nan_policy="omit")[0]
            linhas.append({"cenario": c, "n": int(len(df)), "area_km2_med": float(df[f"area_km2__{c}"].median()), "razao_pop_med": float(razao.median()), "razao_pop_p10": float(razao.quantile(.1)), "razao_pop_p90": float(razao.quantile(.9)),
                           "rho_pop_vs_1km": float(rho_pop), "rho_oferta_vs_1km": float(rho_of), "rho_renda_vs_1km": float(rho_re)})
        t = pd.DataFrame(linhas)
        out[nome] = t.to_dict("records")
        md(f"\n**{nome}** (N={len(df)})\n"); md(t.round(3).to_markdown(index=False))
    R["T1"] = out


# ------------------------------------------------------------------ T2
def t2(pr):
    md("\n## T2 — Preferência revelada (academia x ponto aleatório da malha)")
    B_cols = ["pop__circulo_1km", "renda_pc__circulo_1km", "oferta_ponderada__circulo_1km", "pop__hex_r7", "renda_pc__hex_r7", "oferta_ponderada__hex_r7"]
    I_cols = B_cols + [f"{v}__{c}" for c in ("carro_5", "carro_15", "pe_15") for v in ("pop", "renda_pc", "oferta_ponderada", "km_rua", "n_nos")]
    out = {}
    for rotulo, sub in (("todas", None), ("independentes", "independente_agregador"), ("cadeias", ["cadeia_mapeada", "cadeia_agregador_sem_pin", "cadeia_agregador_com_pin"])):
        df = pr.copy()
        if sub is not None:
            keep = df["tipo"].eq("controle") | df["subtipo"].isin([sub] if isinstance(sub, str) else sub)
            df = df[keep]
        n0 = len(df)
        df = df.dropna(subset=I_cols)
        y = df["tipo"].eq("academia").astype(int).to_numpy()
        g = df["metro"].to_numpy()
        if y.sum() < 50 or (1 - y).sum() < 50 or len(np.unique(g)) < 3:
            md(f"\n**{rotulo}**: N insuficiente"); continue
        res = {}
        preds = {}
        for nome, cols in (("B_circulo_hex", B_cols), ("I_isocronas", I_cols), ("I_so_isocronas", [c for c in I_cols if c not in B_cols])):
            X = log1p_cols(df, cols).to_numpy()
            oof = np.zeros(len(y))
            gkf = GroupKFold(n_splits=min(5, len(np.unique(g))))
            for tr, te in gkf.split(X, y, g):
                m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))
                m.fit(X[tr], y[tr]); oof[te] = m.predict_proba(X[te])[:, 1]
            preds[nome] = oof
            res[nome] = float(roc_auc_score(y, oof))
        d = boot_ci(lambda idx: roc_auc_score(y[idx], preds["I_isocronas"][idx]) - roc_auc_score(y[idx], preds["B_circulo_hex"][idx]) if 0 < y[idx].sum() < len(idx) else np.nan, len(y))
        res.update({"ganho_I_menos_B": res["I_isocronas"] - res["B_circulo_hex"], "ic95_ganho": d, "n": int(len(y)), "n_academias": int(y.sum()), "n_controles": int((1 - y).sum()), "n_excluidos_sem_rede": int(n0 - len(df)),
                    "criterio_ganho_ge_0.02_ic_exclui_zero": bool(res["I_isocronas"] - res["B_circulo_hex"] >= 0.02 and d[0] > 0)})
        out[rotulo] = res
        md(f"\n**{rotulo}**: N={res['n']} (academias {res['n_academias']}, controles {res['n_controles']}; {res['n_excluidos_sem_rede']} excluídos sem rede) — AUC OOF B={res['B_circulo_hex']:.3f} | I={res['I_isocronas']:.3f} | só isócronas={res['I_so_isocronas']:.3f} | ganho I−B={res['ganho_I_menos_B']:+.3f} IC95 [{d[0]:+.3f}; {d[1]:+.3f}] → critério {'ATENDIDO' if res['criterio_ganho_ge_0.02_ic_exclui_zero'] else 'não atendido'}")
        # importancias (coeficientes padronizados do modelo I ajustado em tudo)
        X = log1p_cols(df, I_cols).to_numpy(); m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)).fit(X, y)
        coef = pd.Series(m[-1].coef_[0], index=I_cols).sort_values(key=abs, ascending=False)
        out[rotulo]["coef_padronizados_top"] = coef.head(8).round(3).to_dict()
        md("coeficientes padronizados (modelo I, in-sample, só para leitura): " + ", ".join(f"{k}={v:+.2f}" for k, v in coef.head(8).round(2).items()))
    R["T2"] = out


# ------------------------------------------------------------------ T3
def r2_oof(X, y, groups=None, alpha=1.0):
    oof = np.zeros(len(y))
    splitter = LeaveOneOut().split(X) if groups is None else GroupKFold(n_splits=len(np.unique(groups))).split(X, y, groups)
    for tr, te in splitter:
        m = make_pipeline(StandardScaler(), Ridge(alpha=alpha)).fit(X[tr], y[tr]); oof[te] = m.predict(X[te])
    ss = ((y - oof) ** 2).sum(); st = ((y - y.mean()) ** 2).sum()
    return 1 - ss / st, oof


def t3(bu):
    md("\n## T3 — Previsão de desempenho (E8, molde E7)")
    df = bu[bu["metragem"].notna() & bu["n_meses"].ge(6) & ~bu["confianca"].eq("baixa") & bu["pop__carro_5"].notna()].copy()
    md(f"\nN = {len(df)} unidades maduras com metragem, coordenada de confiança alta/média e isócrona.")
    B2 = ["pop__circulo_1km", "renda_pc__circulo_1km", "oferta_ponderada__circulo_1km"]
    I = B2 + ["pop__carro_5", "pop__pe_15", "oferta_ponderada__carro_5", "n_ultra__carro_10", "pop_por_academia__carro_5"]
    out = {}
    for desf in ["ativos_por_m2_mad", "fat_por_m2_mad", "pag_por_m2_mad", "pct_agregador_mad", "churn_med_12m"]:
        d = df.dropna(subset=[desf] + I)
        y = d[desf].to_numpy(float)
        res = {"n": int(len(d))}
        oofs = {}
        for nome, cols in (("B1_metragem", ["metragem"]), ("B2_circulo", B2), ("I_isocronas", I), ("I_so_isocronas", [c for c in I if c not in B2])):
            X = log1p_cols(d, cols).to_numpy() if nome != "B1_metragem" else d[cols].to_numpy(float)
            r2, oof = r2_oof(X, y); oofs[nome] = oof
            r2g, _ = r2_oof(X, y, groups=d["uf"].to_numpy())
            res[nome] = {"r2_oof_loo": float(r2), "r2_oof_groupkfold_uf": float(r2g)}
        def r2_from(oof, idx):
            yy, oo = y[idx], oof[idx]; return 1 - ((yy - oo) ** 2).sum() / ((yy - yy.mean()) ** 2).sum()
        ic_I = boot_ci(lambda idx: r2_from(oofs["I_isocronas"], idx), len(y))
        ic_g = boot_ci(lambda idx: r2_from(oofs["I_isocronas"], idx) - r2_from(oofs["B2_circulo"], idx), len(y))
        res["ic95_r2_I"] = ic_I; res["ganho_I_menos_B2"] = res["I_isocronas"]["r2_oof_loo"] - res["B2_circulo"]["r2_oof_loo"]; res["ic95_ganho"] = ic_g
        res["GO"] = bool(res["I_isocronas"]["r2_oof_loo"] > 0 and ic_I[0] > 0 and res["ganho_I_menos_B2"] > 0 and ic_g[0] > 0)
        # correlacoes simples (leitura)
        res["spearman_desfecho_x_features"] = {c: float(spearmanr(d[c], y, nan_policy="omit")[0]) for c in I + ["metragem"]}
        out[desf] = res
        md(f"\n**{desf}** (N={len(d)}): R² OOF LOO — B1 metragem {res['B1_metragem']['r2_oof_loo']:+.3f} | B2 círculo {res['B2_circulo']['r2_oof_loo']:+.3f} | I isócronas {res['I_isocronas']['r2_oof_loo']:+.3f} IC95 [{ic_I[0]:+.2f}; {ic_I[1]:+.2f}] | só isócronas {res['I_so_isocronas']['r2_oof_loo']:+.3f} | ganho I−B2 {res['ganho_I_menos_B2']:+.3f} IC95 [{ic_g[0]:+.2f}; {ic_g[1]:+.2f}] | GroupKFold por UF: I {res['I_isocronas']['r2_oof_groupkfold_uf']:+.3f} → **{'GO' if res['GO'] else 'NO-GO'}**")
        md("Spearman desfecho x feature: " + ", ".join(f"{k}={v:+.2f}" for k, v in res["spearman_desfecho_x_features"].items()))
    R["T3"] = out


# ------------------------------------------------------------------ T4
def rotulo(n):
    n = np.asarray(n, float)
    return np.where(n == 0, "Livre", np.where(n <= CONC_ADENSAR_MAX, "Adensar", "Disputa"))


def t4(bh):
    md("\n## T4 — Funil: rótulo de concorrência com isócrona de 5 min de carro x raio de 1 km")
    df = bh[bh["pop__carro_5"].notna()].copy()
    out = {"n_hex": int(len(df)), "n_sem_rede": int(bh["pop__carro_5"].isna().sum())}
    n1 = df["n_concorrentes_influencia_1km"].fillna(0).round()
    r1 = rotulo(n1)
    for nome, col in (("cadeias_carro_5", None), ("total_carro_5", "n_academias__carro_5"), ("cadeias_pe_15", None)):
        if nome == "cadeias_carro_5":
            n2 = df["n_cadeia_mapeada__carro_5"].fillna(0) + df["n_cadeia_agregador_sem_pin__carro_5"].fillna(0)
        elif nome == "cadeias_pe_15":
            n2 = df["n_cadeia_mapeada__pe_15"].fillna(0) + df["n_cadeia_agregador_sem_pin__pe_15"].fillna(0)
        else:
            n2 = df[col].fillna(0)
        r2 = rotulo(n2)
        ct = pd.crosstab(pd.Series(r1, name="funil_1km"), pd.Series(r2, name=nome))
        troca = float((r1 != r2).mean())
        out[nome] = {"taxa_troca_rotulo": troca, "crosstab": ct.to_dict(), "rho_contagem": float(spearmanr(n1, n2)[0]),
                     "mediana_n_1km": float(n1.median()), "mediana_n_iso": float(n2.median())}
        md(f"\n**{nome}**: troca de rótulo em {troca:.1%} dos {len(df)} hexágonos; rho contagem = {out[nome]['rho_contagem']:+.2f}; mediana 1 km = {n1.median():.0f}, isócrona = {n2.median():.0f}\n")
        md(ct.to_markdown())
    # residual: ordenacao 1 km x isocrona
    for c in ("carro_5", "pe_15"):
        rho = spearmanr(df["residual_alunos__circulo_1km"], df[f"residual_alunos__{c}"], nan_policy="omit")[0] if "residual_alunos__circulo_1km" in df else np.nan
        out[f"rho_residual_1km_vs_{c}"] = float(rho)
    md(f"\nrho do residual (pop×17,35% − oferta×2.500) 1 km x carro 5 min = {out['rho_residual_1km_vs_carro_5']:+.2f}; x a pé 15 min = {out['rho_residual_1km_vs_pe_15']:+.2f}")
    R["T4"] = out


# ------------------------------------------------------------------ T5
def t5(bc, bu):
    md("\n## T5 — Canibalização (descritivo)")
    out = {}
    for lim in (5, 10):
        d = bc[bc["limite_min"] == lim]
        if d.empty:
            continue
        frac = pd.concat([d[["a", "frac_a"]].rename(columns={"a": "u", "frac_a": "f"}), d[["b", "frac_b"]].rename(columns={"b": "u", "frac_b": "f"})]).groupby("u")["f"].sum().clip(upper=1.0)
        s = bu.set_index("unidade_id").join(frac.rename("sobreposicao"), how="left"); s["sobreposicao"] = s["sobreposicao"].fillna(0)
        s = s[s["pop__carro_5"].notna()]
        res = {"n_pares": int(len(d)), "n_unidades_com_sobreposicao": int((s["sobreposicao"] > 0).sum()), "mediana_sobreposicao_quem_tem": float(s.loc[s["sobreposicao"] > 0, "sobreposicao"].median()) if (s["sobreposicao"] > 0).any() else np.nan}
        for desf in ["ativos_por_m2_mad", "fat_por_m2_mad", "pct_agregador_mad", "churn_med_12m"]:
            dd = s.dropna(subset=[desf])
            res[f"spearman_sobreposicao_x_{desf}"] = float(spearmanr(dd["sobreposicao"], dd[desf])[0]) if len(dd) > 5 else np.nan
        out[f"carro_{lim}"] = res
        md(f"\ncarro {lim} min: {res['n_pares']} pares; {res['n_unidades_com_sobreposicao']} unidades com sobreposição (mediana {res['mediana_sobreposicao_quem_tem']:.0%} entre as que têm); " + ", ".join(f"rho x {k.split('_x_')[1]}={v:+.2f}" for k, v in res.items() if k.startswith("spearman")))
    R["T5"] = out


def main():
    bu = pd.read_parquet(T / "base_ultra.parquet")
    pr = pd.read_parquet(T / "base_pref_revelada.parquet")
    bh = pd.read_parquet(T / "base_hex_funil.parquet")
    bc = pd.read_parquet(T / "base_canibal.parquet")
    md("# Resultados dos testes pré-registrados (07_testes.py)\n")
    md(f"Bases: ultra {len(bu)} | pref_revelada {len(pr)} ({pr['tipo'].value_counts().to_dict()}) | hex_funil {len(bh)} | canibal {len(bc)} pares | metros com isócronas: {pr['metro'].nunique()}")
    t1(bu, bh); t2(pr); t3(bu); t4(bh); t5(bc, bu)
    json.dump(R, open(T / "resultados_07.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    (T / "resultados_07.md").write_text("\n".join(MD), encoding="utf-8")
    print("\n".join(MD))


if __name__ == "__main__":
    main()
