# -*- coding: utf-8 -*-
"""Testes sobre a base v2 (protocolo_isocronas.md + protocolo_isocronas_v2_adendo.md).

T1, T3, T5: mesmas funcoes do 07 (importadas). T2: especificacao pre-registrada restrita a carro 15 nao truncado
+ sensibilidade sem carro 15; bootstrap por METRO. T4: recorte + cascata do funil sem a camada 3. T6: forma x tamanho
(isocrona x circulo de area equivalente). Saida: testes_v2/resultados_08.md e .json
"""
import importlib.util
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
ISO = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad\iso")
T = ISO / "testes_v2"
spec = importlib.util.spec_from_file_location("t07", ISO / "07_testes.py"); t07 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t07)
t07.T = T
R = t07.R
md = t07.md
SEED = 42


def auc_oof(df, cols, y, g):
    X = t07.log1p_cols(df, cols).to_numpy()
    oof = np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=min(5, len(np.unique(g)))).split(X, y, g):
        m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=3000)).fit(X[tr], y[tr])
        oof[te] = m.predict_proba(X[te])[:, 1]
    return oof


def boot_metro(y, g, pa, pb, B=2000):
    rng = np.random.default_rng(SEED)
    metros = np.unique(g); idx_m = {m: np.nonzero(g == m)[0] for m in metros}
    vals = []
    for _ in range(B):
        amostra = rng.choice(metros, len(metros), replace=True)
        idx = np.concatenate([idx_m[m] for m in amostra])
        yy = y[idx]
        if 0 < yy.sum() < len(yy):
            vals.append(roc_auc_score(yy, pa[idx]) - roc_auc_score(yy, pb[idx]))
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def universo(pr, rotulo):
    df = pr.copy()
    if rotulo == "independentes":
        df = df[df["tipo"].eq("controle") | df["subtipo"].eq("independente_agregador")]
    elif rotulo == "cadeias":
        df = df[df["tipo"].eq("controle") | df["subtipo"].isin(["cadeia_mapeada", "cadeia_agregador_sem_pin"])]
    else:
        df = df[df["tipo"].eq("controle") | ~df["subtipo"].eq("cadeia_agregador_com_pin")]
    return df


def t2_v2(pr):
    md("\n## T2 (v2) — Preferência revelada, bootstrap por metro")
    B = ["pop__circulo_1km", "renda_pc__circulo_1km", "oferta_ponderada__circulo_1km", "pop__hex_r7", "renda_pc__hex_r7", "oferta_ponderada__hex_r7"]
    iso = lambda cens: [f"{v}__{c}" for c in cens for v in ("pop", "renda_pc", "oferta_ponderada", "km_rua", "n_nos")]
    out = {}
    specs = {
        "pre_registrada_carro15_nao_truncado": (["carro_5", "carro_15", "pe_15"], True),
        "sem_carro15_todos": (["carro_5", "pe_15"], False),
    }
    for rotulo in ("todas", "independentes", "cadeias"):
        for nome, (cens, filtra_trunc) in specs.items():
            df = universo(pr, rotulo)
            if filtra_trunc:
                df = df[df["truncada__carro_15"].fillna(1) == 0]
            cols = B + iso(cens)
            df = df.dropna(subset=cols)
            y = df["tipo"].eq("academia").astype(int).to_numpy(); g = df["metro"].to_numpy()
            if y.sum() < 50 or (1 - y).sum() < 50 or len(np.unique(g)) < 3:
                continue
            pb = auc_oof(df, B, y, g); pi = auc_oof(df, cols, y, g)
            a_b, a_i = roc_auc_score(y, pb), roc_auc_score(y, pi)
            ic = boot_metro(y, g, pi, pb)
            ok = bool(a_i - a_b >= 0.02 and ic[0] > 0)
            out[f"{rotulo}|{nome}"] = {"n": int(len(y)), "n_acad": int(y.sum()), "auc_B": a_b, "auc_I": a_i, "ganho": a_i - a_b, "ic95_metro": ic, "criterio": ok}
            md(f"- **{rotulo} / {nome}**: N={len(y)} ({int(y.sum())} academias) — AUC B {a_b:.3f} | I {a_i:.3f} | ganho {a_i-a_b:+.3f} IC95 (metro) [{ic[0]:+.3f}; {ic[1]:+.3f}] → {'ATENDIDO' if ok else 'não atendido'}")
    R["T2_v2"] = out


def t6(pr, bu, bh):
    md("\n## T6 — Forma da rede x tamanho do catchment (círculo de área equivalente)")
    out = {}
    # T6a
    B = ["pop__circulo_1km", "renda_pc__circulo_1km", "oferta_ponderada__circulo_1km", "pop__hex_r7", "renda_pc__hex_r7", "oferta_ponderada__hex_r7"]
    V = ("pop", "renda_pc", "oferta_ponderada")
    for rotulo in ("todas", "independentes", "cadeias"):
        df = universo(pr, rotulo)
        ci = [f"{v}__{c}" for c in ("carro_5", "pe_15") for v in V]
        ce = [f"{v}__circeq_{c}" for c in ("carro_5", "pe_15") for v in V]
        df = df.dropna(subset=B + ci + ce)
        y = df["tipo"].eq("academia").astype(int).to_numpy(); g = df["metro"].to_numpy()
        pb = auc_oof(df, B, y, g); pi = auc_oof(df, B + ci, y, g); pe = auc_oof(df, B + ce, y, g)
        a_b, a_i, a_e = (roc_auc_score(y, p) for p in (pb, pi, pe))
        ic = boot_metro(y, g, pi, pe)
        ok = bool(a_i - a_e >= 0.01 and ic[0] > 0)
        out[f"T6a|{rotulo}"] = {"n": int(len(y)), "auc_B": a_b, "auc_iso": a_i, "auc_circ_eq": a_e, "iso_menos_circeq": a_i - a_e, "ic95_metro": ic, "criterio_forma": ok}
        md(f"- **T6a {rotulo}**: N={len(y)} — AUC B {a_b:.3f} | B+isócrona {a_i:.3f} | B+círculo de área equivalente {a_e:.3f} | isócrona − círculo eq {a_i-a_e:+.3f} IC95 (metro) [{ic[0]:+.3f}; {ic[1]:+.3f}] → forma da rede {'ACRESCENTA' if ok else 'não acrescenta'} (critério ≥ +0,01)")
    # T6b
    md("\n**T6b — concordância isócrona x círculo de área equivalente (Spearman)**\n")
    linhas = []
    for nome, df in (("ultra", bu), ("hex_carteira", bh)):
        for c in ("carro_5", "pe_15"):
            for v in V:
                a, b = df.get(f"{v}__{c}"), df.get(f"{v}__circeq_{c}")
                if a is None or b is None:
                    continue
                m = a.notna() & b.notna()
                if m.sum() < 10:
                    continue
                rho = spearmanr(a[m], b[m])[0]
                ra, rb = a[m].rank(), b[m].rank()
                troca = float(((ra - rb).abs() > 10).mean())
                linhas.append({"base": nome, "cenario": c, "variavel": v, "n": int(m.sum()), "rho": float(rho), "frac_troca_rank_gt10": troca})
    tb = pd.DataFrame(linhas)
    out["T6b"] = tb.to_dict("records")
    md(tb.round(3).to_markdown(index=False))
    # T6c
    md("\n**T6c — previsão (descritivo): mesmas colunas, isócrona x círculo equivalente**\n")
    df = bu[bu["metragem"].notna() & bu["n_meses"].ge(6) & ~bu["confianca"].eq("baixa")].copy()
    B2 = ["pop__circulo_1km", "renda_pc__circulo_1km", "oferta_ponderada__circulo_1km"]
    for desf in ["ativos_por_m2_mad", "fat_por_m2_mad", "churn_med_12m"]:
        res = {}
        for nome, c in (("isocrona", ""), ("circulo_eq", "circeq_")):
            cols = B2 + [f"{v}__{c}{s}" for s in ("carro_5", "pe_15") for v in V]
            d = df.dropna(subset=[desf] + cols)
            r2, _ = t07.r2_oof(t07.log1p_cols(d, cols).to_numpy(), d[desf].to_numpy(float))
            res[nome] = (float(r2), int(len(d)))
        out[f"T6c|{desf}"] = res
        md(f"- {desf}: R² OOF LOO isócrona {res['isocrona'][0]:+.3f} (N={res['isocrona'][1]}) | círculo equivalente {res['circulo_eq'][0]:+.3f}")
    R["T6"] = out


def t4_v2(bh):
    md("\n## T4 (v2) — rótulo do funil com hexágonos de snap 700 m e na cascata real")
    t07.t4(bh)
    df = bh[bh["pop__carro_5"].notna()].copy()
    pop_hex = pd.to_numeric(df.get("pop_hex_base"), errors="coerce")
    cascata = (pd.to_numeric(df["score_setor_2022_calibrado"], errors="coerce") >= 30) & (pop_hex >= 5000) & (pd.to_numeric(df["oferta_efetiva_disponivel"], errors="coerce") >= 2000)
    d = df[cascata]
    n1 = d["n_concorrentes_influencia_1km"].fillna(0).round()
    n2 = d["n_cadeia_mapeada__carro_5"].fillna(0) + d["n_cadeia_agregador_sem_pin__carro_5"].fillna(0)
    r1, r2 = t07.rotulo(n1), t07.rotulo(n2)
    ct = pd.crosstab(pd.Series(r1, name="funil"), pd.Series(r2, name="carro_5"))
    R["T4_v2_cascata"] = {"n": int(len(d)), "troca": float((r1 != r2).mean()) if len(d) else None, "crosstab": ct.to_dict(),
                          "comporta_entrada_funil": int((n1 <= t07.CONC_ADENSAR_MAX).sum()), "comporta_entrada_carro5": int((n2 <= t07.CONC_ADENSAR_MAX).sum())}
    md(f"\n**Cascata sem a camada 3** (score ≥ 30, pop hex ≥ 5.000, residual ≥ 2.000): N={len(d)}; troca de rótulo {R['T4_v2_cascata']['troca']:.1%}; passam a camada 3 hoje: {R['T4_v2_cascata']['comporta_entrada_funil']} | com carro 5 min: {R['T4_v2_cascata']['comporta_entrada_carro5']}\n")
    md(ct.to_markdown())


def main():
    bu = pd.read_parquet(T / "base_ultra.parquet"); pr = pd.read_parquet(T / "base_pref_revelada.parquet")
    bh = pd.read_parquet(T / "base_hex_funil.parquet"); bc = pd.read_parquet(T / "base_canibal.parquet")
    md("# Resultados v2 (08_testes_v2.py)\n")
    md(f"Bases v2: ultra {len(bu)} (com isócrona de carro {bu['pop__carro_5'].notna().sum()}, a pé {bu['pop__pe_15'].notna().sum()}) | pref_revelada {len(pr)} {pr['tipo'].value_counts().to_dict()} | hex_funil {len(bh)} | canibal {len(bc)} | metros {pr['metro'].nunique()}")
    for c in ("carro_5", "carro_10", "carro_15"):
        if f"truncada__{c}" in pr:
            md(f"- truncamento {c}: academias {pr.loc[pr.tipo=='academia', f'truncada__{c}'].mean():.1%} | controles {pr.loc[pr.tipo=='controle', f'truncada__{c}'].mean():.1%} | Ultra {bu[f'truncada__{c}'].mean():.1%}")
    t07.t1(bu, bh); t2_v2(pr); t07.t3(bu); t4_v2(bh); t07.t5(bc, bu); t6(pr, bu, bh)
    json.dump(R, open(T / "resultados_08.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    (T / "resultados_08.md").write_text("\n".join(t07.MD), encoding="utf-8")
    print("\n".join(t07.MD))


if __name__ == "__main__":
    main()
