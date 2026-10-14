# -*- coding: utf-8 -*-
"""BLK-UNI-09 (uni09/protocolo_uni09.md v1.1): faturamento em duas partes, BALCAO (vendas_ux - tem_saude) + AGREGADOR (gympass +
totalpass), cada uma com as covariaveis da v2, somadas com o fator de ACEITE (1 / 1 - s_TP / s_TP / 0). Compara com a v2 no LOO
das 39 maduras de 2025 (c2) e no teste das 18 de 2026 (c3, cru e recentrado). Nas 39/18 isso testa a DECOMPOSICAO (o aceite quase
nao varia). Na turma de 2026 congela as PECAS por unidade (log do balcao e do agregador no nivel de 2025, calibracoes, k e o fator
do cadastro) para a conferencia recombinar com o aceite OBSERVADO na receita (decisao do Felipe, 05/10: "misto / nao sei").
Le' o LOCAL_demanda_totalpass_por_unidade (via ex.carregar, pela cadeia da v2) e nao o grava em nenhuma saida.
Uso: 01_duas_partes.py --seco | --ensaio | (sem flag = teste; exige REGISTRO_CONGELAMENTO.txt). .venv, PYTHONPATH=src."""
import hashlib
import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
ROOT = UNI.parent.parent.parent
PROT, REG = AQUI / "protocolo_uni09.md", AQUI / "REGISTRO_CONGELAMENTO.txt"
PV = UNI / "previsao_2026" / "previsoes_turma_2026_v2_domiciliar.csv"
PV_SHA = "999bd027263459ecf2a2eafc914ad832c0e863f2d36d385a23386e37d1ad6df9"
MET = UNI / "coleta_metragem" / "metragem_estimada_2026-09-29.csv"
DIM = ROOT / "src" / "motor_expansao" / "dimensionamento"
RENDE_AGREGADOR = 0.60   # §11: um aluno de agregador rende ~60% da receita de um de balcao (premissa do backlog BLK-UNI-09 / simulador)
MIN_MESES_A = 3


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


tm = mod("tm", UNI / "termometro" / "01_termometro.py")
ex, X_, ajustar, et = tm.ex, tm.X_, tm.ajustar, tm.et
INSUMOS = [PROT, Path(__file__), PV, MET, tm.KPI, UNI / "fato_unidade_mes.parquet", UNI / "dim_unidade.parquet",
           UNI / "LOCAL_demanda_totalpass_por_unidade.parquet", UNI / "alavancas" / "master_id_cadastro.csv",
           UNI / "uni02" / "confirmacao_por_unidade.csv", UNI / "termometro" / "01_termometro.py", UNI / "manaus_volume" / "02_evidencias.py",
           UNI / "uni07" / "01_incerteza.py", UNI / "uni01" / "01_exploracao.py", UNI / "alavancas" / "01_alavancas.py",
           UNI / "simulacoes" / "manaus_premissas_corrigidas.py", UNI / "uni02" / "01_confirmacao.py",
           UNI / "coleta_metragem" / "02_consolidar.py", UNI / "uni05" / "01_comparacao.py",
           DIM / "config.py", DIM / "simulador.py", DIM / "viabilidade_ponto.py"]
DESFECHOS_REAIS = ["l_fat", "l_ativos", "l_ticket", "agr", "churn", "l_pag"]


# ------------------------------------------------------------------ desfechos por parte (mesmas regras da v2)
def partes(f, ini, fim):
    g = f[f.valido & (f.competencia >= ini) & (f.competencia <= fim) & (f.mv >= 12)].copy()
    n = g.groupby("unidade_id").size(); g = g[g.unidade_id.isin(n[n >= 3].index)]
    g["B"] = g.fin_vendas_ux - g.fin_tem_saude.fillna(0)
    g["TP"] = g.fin_totalpass.fillna(0); g["A"] = g.fin_gympass.fillna(0) + g.TP
    assert (g.B > 0).all(), "mes com balcao <= 0"
    assert ((g.B + g.A - g.faturamento).abs() <= 0.01 * g.faturamento).all(), "soma por tipo != faturamento"
    u = g.unidade_id
    Y = pd.DataFrame({"Y_tot": np.log(g.faturamento).groupby(u).mean(), "Y_B": np.log(g.B).groupby(u).mean(), "n_meses": u.value_counts()})
    ga = g[g.A > 0]
    Y["n_meses_A"] = ga.groupby("unidade_id").size().reindex(Y.index).fillna(0).astype(int)
    Y["Y_A"] = np.log(ga.A).groupby(ga.unidade_id).mean().where(Y.n_meses_A >= MIN_MESES_A)  # §11: so' meses com A > 0, minimo de 3
    Y["s_TP"] = (ga.TP / ga.A).groupby(ga.unidade_id).mean()
    Y["l_pag"] = np.log(g.pagantes.where(g.pagantes > 0).astype(float)).groupby(u).mean()
    Y["l_agr_n"] = np.log(g.agregadores.where(g.agregadores > 0).astype(float)).groupby(u).mean()
    Y["Y_B_TS"] = np.log(g.fin_vendas_ux).groupby(u).mean()  # sensibilidade: tem saude descontado do agregador
    gs = ga[(ga.A - ga.fin_tem_saude.fillna(0)) > 0]
    Y["Y_A_TS"] = np.log(gs.A - gs.fin_tem_saude.fillna(0)).groupby(gs.unidade_id).mean()
    return Y


def _bool(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return str(v).strip().lower() in ("true", "1", "sim")


def aceite(d, idx):
    wh = d.wh_tem_agregador_cadastro.reindex(idx).astype(object).map(_bool)
    tp = d.tp_tem_agregador_cadastro.reindex(idx).astype(object).map(_bool)
    aus = wh.isna() | tp.isna()
    return wh.where(wh.notna(), True).astype(bool), tp.where(tp.notna(), True).astype(bool), aus


def fator(wh, tp, s_tp):
    s = s_tp.reindex(wh.index).to_numpy(float) if isinstance(s_tp, pd.Series) else np.full(len(wh), float(s_tp))
    return pd.Series(np.where(wh & tp, 1.0, np.where(wh, 1 - s, np.where(tp, s, 0.0))), index=wh.index)


def lse(pB, pA, fac):
    return np.log(np.exp(pB) + np.asarray(fac, float) * np.exp(pA))


# ------------------------------------------------------------------ modelo em duas partes
def duas_partes(tr, te, V2, d, s_tp, cal, extraA=(), normalizar=True, prever_com_fator=True, cal_unico=False, colB="Y_B", colA="Y_A"):
    """Ajusta B e A* nas unidades de tr; LOO do total; teste nas de te. cal = dict com calB/calA/calT (e as versoes _TS)."""
    whr, tpr, _ = aceite(d, tr.index); wht, tpt, _ = aceite(d, te.index)
    fr = fator(whr, tpr, s_tp)
    ft = fator(wht, tpt, s_tp) if prever_com_fator else pd.Series(1.0, index=te.index)
    fr_pred = fr if prever_com_fator else pd.Series(1.0, index=tr.index)
    a = tr.copy(); a["Y_As"] = a[colA] - (np.log(fr.where(fr > 0)) if normalizar else 0.0)
    assert a.Y_As.notna().all(), "unidade do treino sem agregador (o protocolo supoe receita de agregador nas 39)"
    CA = V2 + list(extraA)
    bB, sB, lB, eB, hB = ajustar(a, V2, colB)
    bA, sA, lA, eA, hA = ajustar(a, CA, "Y_As")
    fitB, fitA = a[colB].to_numpy(float) - eB, a.Y_As.to_numpy(float) - eA
    kfit = a.Y_tot.to_numpy(float) - lse(fitB, fitA, fr_pred)       # §11: k pelos valores ajustados (zera o residuo medio no nivel)
    n = len(a); k_full = float(kfit.mean()); k_loo = (kfit.sum() - kfit) / (n - 1)
    pB_loo, pA_loo = a[colB].to_numpy(float) - lB, a.Y_As.to_numpy(float) - lA
    r_loo = a.Y_tot.to_numpy(float) - (lse(pB_loo, pA_loo, fr_pred) + k_loo)
    cB, cA = (cal["calT"], cal["calT"]) if cal_unico else (cal[f"cal_{colB}"], cal[f"cal_{colA}"])
    pBt, pAt = X_(te, V2) @ bB + cB, X_(te, CA) @ bA + cA
    r_te = te.Y_tot.to_numpy(float) - (lse(pBt, pAt, ft) + k_full)
    return dict(r_loo=r_loo, r_te=r_te, bB=bB, sB=sB, bA=bA, sA=sA, k=k_full, calB=cB, calA=cA, CA=CA, ft=ft,
                r2B=float(ex.r2_loo(a[colB].to_numpy(float), eB, hB)), r2A=float(ex.r2_loo(a.Y_As.to_numpy(float), eA, hA)))


def comparar(r0l, r1l, r0t, r1t, rng):
    rec = lambda r: r - np.median(r)
    bl = [et(r0l[ii]) - et(r1l[ii]) for ii in (rng.integers(0, len(r0l), len(r0l)) for _ in range(2000))]
    bt, br = [], []
    for ii in (rng.integers(0, len(r0t), len(r0t)) for _ in range(2000)):
        bt.append(et(r0t[ii]) - et(r1t[ii])); br.append(et(rec(r0t[ii])) - et(rec(r1t[ii])))
    return dict(e_l0=et(r0l), e_l1=et(r1l), dl=et(r0l) - et(r1l), ic_dl=np.quantile(bl, [.05, .95]),
                e_t0=et(r0t), e_t1=et(r1t), dt=et(r0t) - et(r1t), ic_dt=np.quantile(bt, [.05, .95]),
                dt_rec=et(rec(r0t)) - et(rec(r1t)), ic_rec=np.quantile(br, [.05, .95]),
                vies0=float(np.median(np.exp(r0t) - 1)), vies1=float(np.median(np.exp(r1t) - 1)), k18=int((np.abs(r1t) < np.abs(r0t)).sum()))


def rotulo(M):
    """§11: sem c1 (desvio declarado do §4.1 da bateria) e simetrico: 'CANDIDATA' pelo c2 exige o teste sem piorar."""
    c2, c3, c3r = M["dl"] >= 0.02, M["dt"] >= 0.02, M["dt_rec"] >= 0.02
    if c2 and c3 and c3r:
        r = "MELHORA A PRECISÃO"
    elif c2 and c3:
        r = "CANDIDATA (o c3 só passa por nível)"
    elif (c2 and M["dt"] >= 0) or (c3 and c3r and M["dl"] >= 0):
        r = "CANDIDATA"
    else:
        r = "NÃO MELHORA"
    return r + " — na decomposição; o aceite quase não varia nas 39/18 e é testado na turma"


# ------------------------------------------------------------------ principal
def main():
    seco, ensaio = "--seco" in sys.argv, "--ensaio" in sys.argv
    out_dir = AQUI / "ensaio" if ensaio else AQUI
    arq, res = out_dir / "previsoes_turma_2026_duas_partes.csv", out_dir / "resultado_uni09.md"
    if ensaio:
        out_dir.mkdir(exist_ok=True)
        for p in out_dir.iterdir():
            p.unlink()
    if not seco:
        assert not arq.exists() and not res.exists(), "resultado do UNI-09 ja existe"
    if not seco and not ensaio:
        reg = REG.read_text(encoding="utf-8") if REG.exists() else ""
        for p in INSUMOS:
            assert sha(p) in reg, f"TRAVA: {p} nao esta congelado (ou mudou) em {REG.name}"
    assert sha(PV) == PV_SHA, "previsao congelada da turma mudou"
    rng = np.random.default_rng(20261008)
    f, d = ex.carregar()
    tr, te, DUM, cal_v2, A, dummies = tm.bases(f, d)
    V2 = ["l_m2", "l_renda_dom", "l_pop"] + DUM + ["studios"]
    Y25, Y26 = partes(f, "2025-01", "2025-12"), partes(f, "2026-01", "2026-08")
    if ensaio:  # §11: TODO desfecho real sai antes; o ruido entra no lugar
        rz = np.random.default_rng(3)
        tr = tr.drop(columns=[c for c in DESFECHOS_REAIS if c in tr.columns]); te = te.drop(columns=[c for c in DESFECHOS_REAIS if c in te.columns])
        for Y in (Y25, Y26):
            Y["Y_B"] = rz.normal(11.8, 0.3, len(Y)); Y["Y_A"] = Y.Y_B - 1.1 + rz.normal(0, 0.3, len(Y))
            Y["Y_tot"] = np.log(np.exp(Y.Y_B) + np.exp(Y.Y_A)); Y["Y_B_TS"] = Y.Y_B; Y["Y_A_TS"] = Y.Y_A
            Y["l_pag"] = rz.normal(7.5, 0.3, len(Y)); Y["l_agr_n"] = rz.normal(7.0, 0.3, len(Y)); Y["s_TP"] = rz.uniform(0.3, 0.45, len(Y))
    else:
        tr = tr.drop(columns=["l_pag"], errors="ignore")  # §11: o l_pag do diagnostico e' o de partes() (mesmos filtros)
    tr = tr.join(Y25.drop(columns=[c for c in Y25.columns if c in tr.columns]), how="left")
    te = te.join(Y26.drop(columns=[c for c in Y26.columns if c in te.columns]), how="left")
    assert tr.Y_tot.notna().all() and te.Y_tot.notna().all() and tr.Y_A.notna().all(), "unidade sem parte"
    if not ensaio:
        assert np.allclose(tr.Y_tot, tr.l_fat) and np.allclose(te.Y_tot, te.l_fat), "Y_tot != desfecho da v2"
    whr, tpr, _ = aceite(d, tr.index)
    s_tp = float(tr.loc[whr & tpr, "s_TP"].median())
    nao_sp = tr.uf.ne("SP") if "uf" in tr.columns else d.uf.reindex(tr.index).ne("SP")
    s_tp_reg = pd.Series(np.where(d.uf.reindex(list(tr.index) + list(te.index)).eq("SP"), s_tp, float(tr.loc[whr & tpr & nao_sp, "s_TP"].median())),
                         index=list(tr.index) + list(te.index))
    # ---- calibracao de calendario por parte (§11: so' maduras com aceite estavel nos dois anos)
    amb = tr.index.intersection(Y26.index)
    est = [u for u in amb if pd.notna(Y25.Y_A.get(u)) and pd.notna(Y26.Y_A.get(u)) and (Y25.s_TP.get(u, 0) > 0) == (Y26.s_TP.get(u, 0) > 0)]
    cal = {"calT": float(np.median(Y26.reindex(amb).Y_tot - Y25.reindex(amb).Y_tot))}
    for c in ("Y_B", "Y_A", "Y_B_TS", "Y_A_TS"):
        cal[f"cal_{c}"] = float(np.median(Y26.reindex(est)[c] - Y25.reindex(est)[c]))
    # ---- v2 (referencia)
    b0, s0, l0, e0, h0 = ajustar(tr, V2, "Y_tot")
    r2v2 = float(ex.r2_loo(tr.Y_tot.to_numpy(float), e0, h0))
    r0t = te.Y_tot.to_numpy(float) - (X_(te, V2) @ b0 + cal["calT"])
    if not ensaio:
        assert abs(cal["calT"] - cal_v2["l_fat"]) < 1e-9 and abs(r2v2 - 0.264) <= 0.005 and abs(et(r0t) - 0.221) <= 0.003, (r2v2, et(r0t))
    pv = pd.read_csv(PV, sep=";", encoding="utf-8-sig", index_col=0)
    metr = pd.read_csv(MET, sep=";", encoding="utf-8-sig", index_col=0).metragem_estimada_m2.dropna()
    of = d.tam_metragem_m2.dropna(); m2 = pd.concat([of, metr[~metr.index.isin(of.index)]])
    cand = A.reindex(pv.index).drop(columns=["l_m2"]).join(np.log(m2).rename("l_m2"))
    cand["master_id"] = pv.master_id
    cand = dummies(cand)
    okm = cand[V2].notna().all(axis=1)
    if not ensaio:  # §11: a montagem da turma reproduz a v2 congelada
        rep = np.exp(X_(cand[okm], V2) @ b0 + cal["calT"]) / pv.prev_v2dom_cal2026[okm].to_numpy(float) - 1
        assert np.nanmax(np.abs(rep)) <= 0.005, f"turma montada nao reproduz a v2 congelada (max {np.nanmax(np.abs(rep)):.4f})"
    wht, tpt, aust = aceite(d, te.index); whv, tpv, ausv = aceite(d, pv.index)
    if seco:
        print("CHECAGEM SECA OK UNI-09 v1.1 (so' desenho e constantes descritivas; nenhum modelo por parte ajustado).")
        print(f"  treino {len(tr)}, teste {len(te)}, turma {len(pv)} ({int(okm.sum())} com covariaveis); v2: R2 LOO {r2v2:.3f}, erro no teste {100 * et(r0t):.1f}%")
        print(f"  turma: v2 remontada x congelada: max |dif| {np.nanmax(np.abs(rep)):.5f}")
        print(f"  s_TP nacional {s_tp:.3f}; fora de SP {float(tr.loc[whr & tpr & nao_sp, 's_TP'].median()):.3f}; unidades do treino com algum mes de A = 0: "
              f"{int((tr.n_meses_A < tr.n_meses).sum())} (minimo de meses com A {int(tr.n_meses_A.min())})")
        print(f"  calibracao (maduras com aceite estavel: {len(est)} de {len(amb)}): total {cal['calT']:+.3f}; balcao {cal['cal_Y_B']:+.3f}; agregador {cal['cal_Y_A']:+.3f}")
        for nm, wh, tp, au, idx in (("treino", whr, tpr, None, tr.index), ("teste", wht, tpt, aust, te.index), ("turma", whv, tpv, ausv, pv.index)):
            fac = fator(wh, tp, s_tp)
            print(f"  {nm}: fator do aceite (cadastro) {fac.round(3).value_counts().to_dict()}" + (f"; ausente {int(au.sum())}" if au is not None else ""))
        print(f"  covariaveis das sensibilidades no treino: poi_F1 {int(d.poi_F1.reindex(tr.index).notna().sum())}/39; wh_ord {int(d.wh_ord_ultra_cadastro.reindex(tr.index).notna().sum())}/39; "
              f"wh/tp_n_conc {int(d.wh_n_conc_c10.reindex(tr.index).notna().sum())}/{int(d.tp_n_conc_c10.reindex(tr.index).notna().sum())}")
        return
    # ---------------- principal
    M2 = duas_partes(tr, te, V2, d, s_tp, cal)
    C = comparar(l0, M2["r_loo"], r0t, M2["r_te"], rng)
    v = rotulo(C)
    nomes = ["intercepto"] + V2
    gl = len(tr) - len(V2) - 1
    ci = lambda b, s, j: (b[j] - stats.t.ppf(.95, gl) * s[j], b[j] + stats.t.ppf(.95, gl) * s[j])
    L = ["# BLK-UNI-09 — faturamento em duas partes: balcão + agregador (pré-registro uni09/protocolo_uni09.md v1.1, congelado antes de rodar)", "",
         f"Treino: {len(tr)} maduras de 2025; teste: {len(te)} unidades de 2026 (UNI-02); turma: {len(pv)}. s_TP = {s_tp:.3f}; k = {M2['k']:+.4f}; "
         f"calibração 2025→2026: balcão {M2['calB']:+.3f}, agregador {M2['calA']:+.3f} (total da v2 {cal['calT']:+.3f}).", "",
         "## Resultado principal (faturamento total)", "",
         f"- **v2:** R² LOO {r2v2:.3f}; erro típico LOO {100 * C['e_l0']:.1f}%; teste {100 * C['e_t0']:.1f}%.",
         f"- **Duas partes:** erro típico LOO {100 * C['e_l1']:.1f}% (queda {100 * C['dl']:+.1f} pp; IC 90% {100 * C['ic_dl'][0]:+.1f} a {100 * C['ic_dl'][1]:+.1f}); "
         f"teste {100 * C['e_t1']:.1f}% (queda {100 * C['dt']:+.1f} pp; IC 90% {100 * C['ic_dt'][0]:+.1f} a {100 * C['ic_dt'][1]:+.1f}; recentrado {100 * C['dt_rec']:+.1f} pp, "
         f"IC 90% {100 * C['ic_rec'][0]:+.1f} a {100 * C['ic_rec'][1]:+.1f}; {C['k18']} de {len(te)} melhoram); viés no teste {100 * C['vies0']:+.1f}% → {100 * C['vies1']:+.1f}%. "
         "(IC condicionais aos ajustes: descritivos, não decidem.)",
         f"- R² LOO de cada parte: balcão {M2['r2B']:.3f}; agregador {M2['r2A']:.3f}.", "",
         f"**Veredito do UNI-09: {v}.**", ""]
    grp = np.where((wht & tpt).to_numpy(), "aceita os dois", "não aceita algum (cadastro)")
    L += ["### Teste por grupo de aceite (descritivo)", "", "| grupo | n | erro v2 | erro duas partes |", "|---|---|---|---|"]
    for gname in ("aceita os dois", "não aceita algum (cadastro)"):
        m = grp == gname
        if m.any():
            L.append(f"| {gname} | {int(m.sum())} | {100 * et(r0t[m]):.1f}% | {100 * et(M2['r_te'][m]):.1f}% |")
    # ---------------- diagnosticos
    L += ["", "## Diagnóstico: coeficientes por parte (log; IC 90% HC3)", "", "| variável | v2 (total) | balcão | agregador | balcão em volume (pagantes) | agregador em volume (contagem) |",
          "|---|---|---|---|---|---|"]
    bP, sP, *_ = ajustar(tr, V2, "l_pag"); bN, sN, *_ = ajustar(tr.dropna(subset=["l_agr_n"]), V2, "l_agr_n")
    for j, nm in enumerate(nomes):
        if nm == "intercepto":
            continue
        cel = lambda b, s: f"{b[j]:+.3f} [{ci(b, s, j)[0]:+.2f}; {ci(b, s, j)[1]:+.2f}]"
        L.append(f"| {nm} | {cel(b0, s0)} | {cel(M2['bB'], M2['sB'])} | {cel(M2['bA'], M2['sA'])} | {cel(bP, sP)} | {cel(bN, sN)} |")
    L += ["", "Leitura: sinais opostos de uma master entre balcão e agregador indicam que o efeito dela no total é composição de mix. "
          "O mr_M3 do treino vem só das unidades de SP (todas aceitam agregador).", ""]
    # ---------------- sensibilidades (isoladas: uma falha e' registrada, nao derruba a rodada)
    L += ["## Sensibilidades (descritivas)", "", "| versão | n | erro LOO v2 → duas partes | queda LOO | erro teste v2 → duas partes | queda teste | queda recentrada |",
          "|---|---|---|---|---|---|---|"]

    def sens(rot, cols=None, subset=None, **kw):
        try:
            tt, ee = tr.copy(), te.copy()
            for c_, s_ in (cols or {}).items():
                tt[c_] = s_.reindex(tt.index).to_numpy(float); ee[c_] = s_.reindex(ee.index).to_numpy(float)
            if subset is not None:
                tt, ee = tt[subset(tt)], ee[subset(ee)]
            bv, _, lv, _, _ = ajustar(tt, V2, "Y_tot")
            rv = ee.Y_tot.to_numpy(float) - (X_(ee, V2) @ bv + cal["calT"])
            M = duas_partes(tt, ee, V2, d, kw.pop("s_tp", s_tp), cal, **kw)
            Cs = comparar(lv, M["r_loo"], rv, M["r_te"], rng)
            L.append(f"| {rot} | {len(tt)}/{len(ee)} | {100 * Cs['e_l0']:.1f}% → {100 * Cs['e_l1']:.1f}% | {100 * Cs['dl']:+.1f} pp | "
                     f"{100 * Cs['e_t0']:.1f}% → {100 * Cs['e_t1']:.1f}% | {100 * Cs['dt']:+.1f} pp | {100 * Cs['dt_rec']:+.1f} pp |")
        except Exception as err:  # noqa: BLE001
            L.append(f"| {rot} | — | falhou: {type(err).__name__}: {str(err)[:80]} | | | | |")
    sens("previsão sem o fator de aceite (mesmo ajuste, fator 1)", prever_com_fator=False)
    sens("treino sem normalizar o agregador das 2 sem TotalPass", normalizar=False)
    sens("calendário único (o do total) nas duas partes", cal_unico=True)
    sens("s_TP fora de SP para quem não aceita TotalPass", s_tp=s_tp_reg)
    sens("Tem Saúde descontado do agregador", colB="Y_B_TS", colA="Y_A_TS")
    sens("agregador + escritórios a pé (poi_F1; só unidades com o dado)", cols={"poi_F1": d.poi_F1.astype(float)}, extraA=("poi_F1",),
         subset=lambda D: D.poi_F1.notna())
    sens("agregador + parceiros Wellhub e TotalPass na isócrona (foto set/2026: associação)", extraA=("l_whn", "l_tpn"),
         cols={"l_whn": np.log1p(d.wh_n_conc_c10.astype(float)), "l_tpn": np.log1p(d.tp_n_conc_c10.astype(float))},
         subset=lambda D: D.l_whn.notna() & D.l_tpn.notna())
    sens("agregador + tier Wellhub (ordinal do cadastro, foto ago/2026)", extraA=("wh_ord",), cols={"wh_ord": d.wh_ord_ultra_cadastro.astype(float)},
         subset=lambda D: D.wh_ord.notna())
    # ---------------- turma 2026: pecas por unidade (congela sempre)
    lpB = X_(cand[okm], V2) @ M2["bB"]; lpA = X_(cand[okm], V2) @ M2["bA"]; lpV = X_(cand[okm], V2) @ b0
    fv = fator(whv, tpv, s_tp)
    out = pd.DataFrame(index=pv.index)
    out["aceita_wellhub_cad"], out["aceita_totalpass_cad"], out["aceite_ausente_cad"] = whv, tpv, ausv
    out["fator_cadastro"] = fv.round(4)
    for nome_, val in (("log_balcao_2025", lpB), ("log_agregador_ambos_2025", lpA), ("log_v2_2025", lpV)):
        s_ = pd.Series(np.nan, index=pv.index); s_[okm] = val; out[nome_] = s_.round(5)
    out["k"], out["calB_2026"], out["calA_2026"], out["calT_2026"], out["s_TP"] = round(M2["k"], 5), round(M2["calB"], 5), round(M2["calA"], 5), round(cal["calT"], 5), round(s_tp, 5)
    B26, A26 = np.exp(out.log_balcao_2025 + M2["calB"]), np.exp(out.log_agregador_ambos_2025 + M2["calA"])
    kk = np.exp(M2["k"])
    out["prev_v2dom_cal2026"] = pv.prev_v2dom_cal2026
    out["prev_partes_neutro_2026"] = ((B26 + A26) * kk).round(0)                                   # fator 1
    out["prev_partes_cadastro_2026"] = ((B26 + fv * A26) * kk).round(0)                           # foto do cadastro, sem substituicao
    out["prev_partes_cadastro_subst_total_2026"] = ((B26 + fv * A26 + (1 - fv) * A26 / RENDE_AGREGADOR) * kk).round(0)
    out.to_csv(arq, sep=";", encoding="utf-8-sig")
    h = sha(arq)
    with (out_dir / REG.name).open("a", encoding="utf-8") as fh:
        fh.write(f"Turma 2026 congelada pelo UNI-09 em {datetime.now():%Y-%m-%d %H:%M} (s_TP {s_tp:.4f}; k {M2['k']:+.5f}; calB {M2['calB']:+.5f}; calA {M2['calA']:+.5f}; "
                 f"calT {cal['calT']:+.5f}; veredito {v}): {h} *{arq.name}\n")
    L += ["", "## Turma de 2026 congelada (as peças, para recombinar na conferência)", "",
          f"`{arq.name}`: {len(out)} unidades ({int(okm.sum())} com covariáveis); pelo cadastro de ago/2026, {int((fv[okm] == 0).sum())} sem agregador, "
          f"{int(((fv[okm] > 0) & (fv[okm] < 1)).sum())} com um só. SHA-256 `{h}`.",
          "Conferência (protocolo §11): o fator usa o aceite OBSERVADO na receita da janela; o calendário é o do ano conferido, por parte. "
          "A foto do cadastro é leitura secundária.", ""]
    res.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
