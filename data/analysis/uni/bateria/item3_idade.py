# -*- coding: utf-8 -*-
"""BLK-UNI-10, item 3 (bateria/protocolo_bateria.md §7 + §9.9 + §17.3 + §20 + §21): % da populacao na faixa etaria REAL dos alunos.
Faixa (regra do §7/§9.9, so' com a idade dos alunos, sem desfecho): o menor intervalo (em anos) de grupos de idade do Censo
2022 que contem >= 60% dos alunos ativos, peso igual por unidade, sem as 18 do teste e sem a turma; desempate: maior
cobertura, depois o mais jovem. Alunos: Growth /alunos-frequencia (vencimento 05-11/10/2026, so' agregados). Resultado
congelado no §20: 20 a 49. F = populacao de 20 a 49 anos / populacao com faixa, na area de influencia, pelos setores do
Censo 2022 com as celulas de sigilo recuperadas pelo total do setor (§21). Teste primario no LABORATORIO SMART FIT, direcao
POSITIVA (§3), p primario = o MAIOR entre as quadriculas com G* >= 10 (§17.3). Tres guardas (§21): sem a maior area; com os
controles de oferta e centralidade; e p <= 0,05 tambem com cluster por area e na grade de 30 km. Na Ultra: descritivo e
c2/c3. Turma de 2026 congelada sempre. Nao le dado sensivel (alunos so' em agregado por unidade).
Uso: item3_idade.py --seco | --ensaio | (sem flag = teste; exige REGISTRO_CONGELAMENTO_item3.txt). .venv, PYTHONPATH=src."""
import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
ROOT = UNI.parent.parent.parent
INS = AQUI / "insumos_item3"
IBGE = ROOT / "data" / "raw" / "ibge" / "censo2022_setores"
ALUNOS = UNI / "idade" / "idade_alunos_por_unidade_sonda_censo.parquet"
REG3 = AQUI / "REGISTRO_CONGELAMENTO_item3.txt"
GRUPOS = [("0_4", 0, 4), ("5_9", 5, 9), ("10_14", 10, 14), ("15_19", 15, 19), ("20_24", 20, 24), ("25_29", 25, 29), ("30_39", 30, 39),
          ("40_49", 40, 49), ("50_59", 50, 59), ("60_69", 60, 69), ("70_mais", 70, 79)]  # 70+ conta como 10 anos na amplitude
FAIXA_CONGELADA = "20-49"                 # §20: saida da regra, conferida pelo script
P_OUTROS = {"1 operador": 0.1554, "6 modalidades": 0.6890, "2 comodidades": 0.3002, "5 faculdades": 0.1918, "4 visibilidade": 0.7206}
COB_MIN_SENS = 0.90
CORTE_LAB = "20250101"
DIRECAO = "unilateral, coef > 0"
PASSO = 0.05                              # efeito relatado por +5 p.p. da populacao na faixa (e tambem por DP residual)


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


i5 = mod("i5", AQUI / "item5_faculdades.py")  # it2 (laboratorio), op, tm, ex; ler_cnpj/_vizinhos (filiais); nao roda o item 5
it2, op, tm, ex, X_, et, sha = i5.it2, i5.op, i5.tm, i5.ex, i5.X_, i5.et, i5.sha
INSUMOS3 = (i5.INSUMOS5 + [Path(__file__), AQUI / "item3_prep_idade_setor.py", INS / "idade_setor_2022.parquet", INS / "idade_areas.parquet",
                           IBGE / "Agregados_por_setores_demografia_BR.zip", IBGE / "dicionario_de_dados_agregados_por_setores_censitarios_20260520.xlsx",
                           UNI / "idade" / "01_idade_alunos.py", ALUNOS, UNI / "depara_unidade.parquet",
                           ROOT / "src" / "motor_expansao" / "dashboard" / "rede_metricas.py"])


def limiar_holm():
    """Limiar efetivo do item 3 pelo Holm (k = 6), com os 5 p ja obtidos: o item 3 so' e' rejeitado no posto r se todos os
    anteriores tambem forem; com os 5 acima de 0,05, so' o 1o posto (alfa/6) pode rejeitar."""
    assert abs(op.LIMIAR - 0.05 / 6) < 1e-12 and op.K_FAMILIA == 6
    menores = sorted(p for p in P_OUTROS.values() if p <= 0.05)
    lim, r = 0.05 / 6, 1
    for p in menores:  # (vazio hoje) cada p menor ja rejeitado empurra o item 3 um posto
        if p <= 0.05 / (7 - r):
            r += 1; lim = 0.05 / (7 - r)
        else:
            break
    return lim


# ------------------------------------------------------------------ faixa (so' alunos)
def faixa_alunos(excluir):
    from motor_expansao.dashboard import rede_metricas as rm
    D = pd.read_parquet(UNI / "depara_unidade.parquet"); mp = {}
    for uid, nc in zip(D.unidade_id, D.nomes_crus.fillna("")):
        for n in nc.split(" | "):
            if n:
                mp.setdefault(rm._sem_acento(n).strip().upper(), set()).add(uid)
    U = pd.read_parquet(ALUNOS)
    U["uid"] = [next(iter(mp[k])) if len(mp.get(k, ())) == 1 else None for k in (rm._sem_acento(str(n)).strip().upper() for n in U.unidade)]
    R = U[U.uid.notna() & ~U.uid.isin(excluir)]
    C = R[[f"n_censo_{g}" for g, _, _ in GRUPOS]].to_numpy(float)
    m = (C / C.sum(axis=1, keepdims=True)).mean(axis=0)
    cand = []
    for i in range(len(GRUPOS)):
        for j in range(i, len(GRUPOS)):
            cob = float(m[i:j + 1].sum())
            if cob >= 0.60:
                cand.append((GRUPOS[j][2] - GRUPOS[i][1] + 1, -cob, GRUPOS[i][1], i, j, cob))
    cand.sort()
    lar, _, _, i, j, cob = cand[0]
    rot = f"{GRUPOS[i][1]}-{GRUPOS[j][2] if GRUPOS[j][0] != '70_mais' else '+'}"
    return dict(rot=rot, grupos=[g for g, _, _ in GRUPOS[i:j + 1]], cobertura=cob, n_unidades=len(R), media=dict(zip([g for g, _, _ in GRUPOS], m)),
                candidatos=[(f"{GRUPOS[c[3]][1]}-{GRUPOS[c[4]][2]}", c[0], round(c[5], 3)) for c in cand[:5]], sem_par=int(U.uid.isna().sum()))


def share(A, grupos, suf=""):
    return A[[f"pop_{g}{suf}" for g in grupos]].sum(axis=1) / A[f"pop_com_faixa{suf}"].where(A[f"pop_com_faixa{suf}"] > 0)


def efeito_referencia(AL, FX):
    """Efeito que a COMPOSICAO etaria implica (sem desfecho): demanda relativa D = soma_g propensao_g x participacao_g, com
    propensao = participacao do grupo entre os alunos / na populacao do lab; d ln D / dF pela covariacao das faixas com F entre
    as areas do lab. Devolve o efeito em log por +1 de F."""
    blocos = {"0_14": ["0_4", "5_9", "10_14"], "15_19": ["15_19"], "F": FX["grupos"], "50_59": ["50_59"], "60_mais": ["60_69", "70_mais"]}
    sh = {k: share(AL, g) for k, g in blocos.items()}
    al = {k: sum(FX["media"][x] for x in g) for k, g in blocos.items()}
    prop = {k: al[k] / sh[k].mean() for k in blocos}
    vF = sh["F"].var()
    b = {k: (1.0 if k == "F" else float(np.cov(sh[k], sh["F"])[0, 1] / vF)) for k in blocos}
    dlnD = sum(prop[k] * b[k] for k in blocos) / sum(prop[k] * sh[k].mean() for k in blocos)
    return float(dlnD), {k: round(v, 2) for k, v in prop.items()}, {k: round(v, 2) for k, v in b.items()}


# ------------------------------------------------------------------ inferencia (unilateral, coef > 0)
def lab3(S, cl, xq="F", cols_extra=(), rng=None, boot=True):
    """y ~ x + l_renda_dom + l_pop + extra + FE de area (it2.preparar_lab chama a candidata de 'Qf'). op.wcr devolve
    (p coef > 0, p coef < 0, t, coef)."""
    S, base, inc = it2.preparar_lab(S, xq, cols_extra)
    assert not inc and S.semQ.sum() == 0, "candidata com ausencia"
    Xm = X_(S, base + ["Qf"]); yv = S.y.to_numpy(float); j = Xm.shape[1] - 1
    op._posto(Xm, f"lab {xq} {cols_extra}")
    b, e, h, XtXi = ex.ols(yv, Xm); assert h.max() < 1 - 1e-9, "alavancagem 1 no laboratorio"
    g = op.regua(S[cl].astype(str)); G = len(np.unique(g))
    out = dict(coef=float(b[j]), n=len(S), G=G, Gst=float(np.nanmin([it2.g_estrela(Xm, j, g, 0.0), it2.g_estrela(Xm, j, g, 1.0)])),
               areas=int(S.metro.nunique()))
    if boot:
        p_pos, p_neg, t, _ = op.wcr(yv, Xm, j, g, rng)
        out.update(p=float(p_pos), p_oposto=float(p_neg), t=float(t))
    Xb_ = X_(S, base); b0, e0, h0, _ = ex.ols(yv, Xb_); sst = np.sum((yv - yv.mean()) ** 2)
    out["r2loo0"], out["r2loo1"] = float(1 - np.sum((e0 / (1 - h0)) ** 2) / sst), float(1 - np.sum((e / (1 - h)) ** 2) / sst)
    return out


def pc(b, passo=PASSO):
    return 100 * (np.exp(b * passo) - 1)


# ------------------------------------------------------------------ principal
def main():
    seco, ensaio = "--seco" in sys.argv, "--ensaio" in sys.argv
    out_dir = AQUI / "ensaio_item3" if ensaio else AQUI
    arq, res = out_dir / "previsoes_turma_2026_v2_I.csv", out_dir / "resultado_item3_idade.md"
    if ensaio:
        out_dir.mkdir(exist_ok=True)
        for p in out_dir.iterdir():
            p.unlink()
    if not seco:
        assert not arq.exists() and not res.exists(), "congelamento/resultado do item 3 ja existem"
    if not seco and not ensaio:
        reg = REG3.read_text(encoding="utf-8") if REG3.exists() else ""
        for p in INSUMOS3:
            assert sha(p) in reg, f"TRAVA: {p} nao esta congelado (ou mudou) em {REG3.name}"
    assert sha(op.PV) == op.PV_SHA, "previsao congelada da turma mudou"
    LIM = limiar_holm()
    rng = np.random.default_rng(20261007)
    t2 = pd.read_csv(UNI / "uni02" / "confirmacao_por_unidade.csv", sep=";", encoding="utf-8-sig", index_col=0)
    pv = pd.read_csv(op.PV, sep=";", encoding="utf-8-sig", index_col=0)
    FX = faixa_alunos(set(t2.index) | set(pv.index))
    assert FX["rot"] == FAIXA_CONGELADA, f"a regra da faixa deu {FX['rot']}, diferente da congelada no §20 ({FAIXA_CONGELADA})"
    A = pd.read_parquet(INS / "idade_areas.parquet")
    A["F"] = share(A, FX["grupos"])
    A["F_comp"] = share(A, FX["grupos"], "_comp")
    for rot, gr in (("F_15_49", ["15_19", "20_24", "25_29", "30_39", "40_49"]), ("F_25_59", ["25_29", "30_39", "40_49", "50_59"]),
                    ("F_20_59", ["20_24", "25_29", "30_39", "40_49", "50_59"]), ("F_60mais", ["60_69", "70_mais"]), ("F_0_14", ["0_4", "5_9", "10_14"])):
        A[rot] = share(A, gr)
    A["F_adultos"] = A[[f"pop_{g}" for g in FX["grupos"]]].sum(axis=1) / A[[f"pop_{g}" for g in ("15_19", "20_24", "25_29", "30_39", "40_49", "50_59", "60_69", "70_mais")]].sum(axis=1)
    c = it2.ler_comodidades()
    f, d = ex.carregar()
    S, F = it2.amostra_lab(c, ensaio=ensaio)
    AL = A[A.origem == "lab"].set_index("chave")
    assert set(AL.index) == set(S.sigla), "areas do preparo diferentes da amostra do laboratorio (rodar item3_prep_idade_setor.py)"
    for col in ("F", "F_comp", "F_15_49", "F_25_59", "F_20_59", "F_60mais", "F_0_14", "F_adultos", "cobertura_faixa", "pop_malha"):
        S[col] = S.sigla.map(AL[col]).to_numpy(float)
    dif = (S.pop_malha / S["pop"] - 1).abs()
    assert dif.max() <= 0.05, f"pop do preparo diverge da amostra (max {dif.max():.3f}): geometria ou malha mudou"
    S["l_mor"] = np.log(S["pop"] / S.dom)
    S["l_nrede"] = np.log1p(S.n_rede_site)
    _, Fl = i5.ler_cnpj()
    ind, _ = i5._vizinhos(S[["lat", "lng"]], Fl, 500); fdt = Fl.data_inicio.to_numpy()
    S["lf500"] = np.log1p([int((fdt[ii] < CORTE_LAB).sum()) for ii in ind])
    assert S.F.notna().all(), "area sem populacao com faixa"
    # ---- Ultra
    tr, te, DUM, cal, Aa, dummies = tm.bases(f, d)
    if ensaio:  # o desfecho da Ultra vira ruido ANTES de qualquer conta com ele
        rz = np.random.default_rng(2)
        for D in (tr, te):
            D["l_fat"] = np.where(D.l_fat.notna(), rz.normal(12.0, 0.3, len(D)), np.nan)
    AU = A[A.origem == "ultra"].set_index("chave")
    assert pv.index.isin(AU.index).all(), "turma sem area no preparo"
    for D in (tr, te):
        assert D.index.isin(AU.index).all(), "Ultra sem area no preparo"
        for col in ("F", "cobertura_faixa"):
            D[col] = AU[col].reindex(D.index).to_numpy(float)
        D["metro"] = d.iso_metro.reindex(D.index)
        D["cl_metro"] = D.metro.astype(str).where(D.metro.notna(), "u_" + D.index.astype(str))
    V2 = ["l_m2", "l_renda_dom", "l_pop"] + DUM + ["studios"]
    if not ensaio:
        _, rt, _ = op.residuos_v2(tr, te, V2, "l_fat", cal["l_fat"])
        r2v2 = float(ex.r2_loo(tr.l_fat.to_numpy(float), *ex.ols(tr.l_fat.to_numpy(float), X_(tr, V2))[1:3]))
        assert abs(r2v2 - 0.264) <= 0.005 and abs(et(rt.to_numpy()) - 0.221) <= 0.003, (r2v2, et(rt.to_numpy()))
    # ---- desenho (sem a medida contra o desfecho): G* em todas as quadriculas (regra do §17.3)
    DS = {f"{km}{suf}": it2.desenho(S, f"cel{km}{suf}", xq="F") for km in it2.KMS for suf in ("", "s")}
    VALIDAS = [k for k in DS if DS[k]["Gst"] >= it2.G_MIN]
    ok_km = [km for km in it2.KMS if DS[str(km)]["Gst"] >= it2.G_MIN]
    cl0 = f"cel{max(ok_km)}" if ok_km else f"cel{min(it2.KMS)}"
    D0 = DS[cl0[3:]]
    Sd, base_d, _ = it2.preparar_lab(S, "F")
    cnt = Sd.metro.value_counts(); big = cnt.index[0]; share_big = cnt.iloc[0] / len(Sd)
    Xd = X_(Sd, base_d); xv = Sd.F.to_numpy(float); dp_res = float((xv - Xd @ np.linalg.lstsq(Xd, xv, rcond=None)[0]).std())
    REF, prop, bslope = efeito_referencia(AL, FX)
    SU = pd.concat([tr, te])
    GUARDA_OFERTA = ("l_nrede", "l_nwh", "lf500")
    if seco:
        du = i5.desenho_ultra5(tr, te, V2, "F")
        print(f"CHECAGEM SECA OK item 3 (sem ajuste da medida contra o desfecho). Limiar efetivo do Holm: {LIM:.4f}.")
        print(f"  faixa pela regra: {FX['rot']} (cobertura {FX['cobertura']:.1%}; {FX['n_unidades']} unidades; Growth sem par {FX['sem_par']}); candidatos {FX['candidatos']}")
        print(f"  funil: {F}; no modelo n {len(Sd)}, areas {Sd.metro.nunique()}; maior area {big} ({100 * share_big:.0f}%); pop do preparo x amostra: dif max {dif.max():.4f}, mediana {dif.median():.5f}")
        print("  G* com F (rho 0 / rho 1 / min, G): " + "; ".join(f"{k_} km: {v['Gst0']:.1f}/{v['Gst1']:.1f}/{v['Gst']:.1f} (G {v['G']})" for k_, v in DS.items()))
        print(f"  grades validas: {VALIDAS}; referencia {cl0}; por area G* {D0['Gst_area']:.1f}")
        q = Sd.F
        print(f"  F (lab): p10/p50/p90 = {q.quantile(.1):.3f}/{q.median():.3f}/{q.quantile(.9):.3f}; DP {q.std():.4f}; DP residual (FE+renda+pop) {dp_res:.4f}; "
              f"corr(F, F_comp) {Sd.F.corr(Sd.F_comp):.4f}; cobertura p10 {Sd.cobertura_faixa.quantile(.1):.1%}")
        for rot, cols in (("FE + renda + pop", base_d), ("+ moradores/dom", base_d + ["l_mor"]), ("+ oferta e centralidade", base_d + list(GUARDA_OFERTA))):
            Xq = X_(Sd, cols); xr = xv - Xq @ np.linalg.lstsq(Xq, xv, rcond=None)[0]
            print(f"  R2 de F sobre {rot}: {1 - xr.var() / xv.var():.3f}")
        print(f"  corr(F, .): renda dom {Sd.F.corr(Sd.l_renda_dom):+.2f}; 60+ {Sd.F.corr(Sd.F_60mais):+.2f}; 0-14 {Sd.F.corr(Sd.F_0_14):+.2f}; "
              f"Smart Fit site {Sd.F.corr(Sd.l_nrede):+.2f}; Wellhub {Sd.F.corr(Sd.l_nwh):+.2f}; filiais {Sd.F.corr(Sd.lf500):+.2f}")
        print(f"  EFEITO DE REFERENCIA da composicao: d ln(demanda)/dF = {REF:.3f} -> {pc(REF):+.1f}% por +5 p.p.; {pc(REF, dp_res):+.1f}% por DP residual; "
              f"propensoes {prop}; inclinacoes sobre F {bslope}")
        for nm, al in (("0,05", .05), ("a/6", op.LIMIAR)):
            print(f"  detectavel no lab (80%, {nm}) por +5 p.p.: iid {pc(it2.mde(D0['se_iid'], D0['gl'], al)):+.1f}%; "
                  + "; ".join(f"cluster {k} {pc(it2.mde(DS[k]['se_cl'], max(DS[k]['Gst'] - 1, 1), al)):+.1f}%" for k in VALIDAS)
                  + f" | por DP residual (cluster {cl0[3:]}): {pc(it2.mde(D0['se_cl'], max(D0['Gst'] - 1, 1), al), dp_res):+.1f}%")
        print(f"  razao detectavel (a/6, cluster {cl0[3:]}) / efeito de referencia: {it2.mde(D0['se_cl'], max(D0['Gst'] - 1, 1), op.LIMIAR) / REF:.1f}x")
        print(f"  Ultra: F p50 {SU.F.median():.3f}; turma p50 {AU.F.reindex(pv.index).median():.3f}, DP turma {AU.F.reindex(pv.index).std():.4f}; "
              f"detectavel (80%, 0,05) por +5 p.p.: iid {pc(it2.mde(du['se_iid'], du['gl'], .05)):+.1f}% / cluster {pc(it2.mde(du['se_cl'], max(du['Gst'] - 1, 1), .05)):+.1f}%")
        return
    # ---------------- teste
    if not VALIDAS:
        P, PV_ = dict(pd=1.0, coef=np.nan, nota=f"G* < {it2.G_MIN} em todas as quadrículas: o laboratório não dá p (p = 1)"), {}
    else:
        PV_ = {k: lab3(S, f"cel{k}", rng=rng) for k in VALIDAS}
        kmax = max(PV_, key=lambda k: PV_[k]["p"])
        P = dict(PV_[cl0[3:]] if cl0[3:] in PV_ else PV_[kmax]); P["pd"] = PV_[kmax]["p"]
        P["p_oposto_max"] = max(r["p_oposto"] for r in PV_.values())
        P["nota"] = f"p primário = o maior entre as quadrículas com G* ≥ 10 ({', '.join(VALIDAS)} km; 's' = deslocada), que é o da {kmax} km (§17.3)"
    sem_big = lab3(S[S.metro != big], cl0, rng=rng)
    com_of = lab3(S, cl0, cols_extra=GUARDA_OFERTA, rng=rng)
    por_area = lab3(S, "metro", rng=rng)
    g30 = lab3(S, "cel30", rng=rng)
    rob = lambda r: np.isfinite(P.get("coef", np.nan)) and np.sign(r["coef"]) == np.sign(P["coef"]) and abs(r["coef"]) >= 0.5 * abs(P["coef"])
    pp = P["pd"]
    if not VALIDAS:
        c1 = "não testável (G* < 10); entra no Holm com p = 1"
    elif pp <= LIM:
        c1 = "significativo"
    elif pp <= 0.05:
        c1 = f"não significativo após Holm (os outros 5 itens têm p > 0,05; o item 3 só passaria no 1º posto, com α/6 = {LIM:.4f})"
    else:
        c1 = "não significativo"
    if c1 == "significativo" and not rob(sem_big):
        c1 = "frágil à dependência espacial (não resiste sem a maior área); entra no Holm com p = 1"
    elif c1 == "significativo" and not rob(com_of):
        c1 = "confundido com OFERTA/CENTRALIDADE (não resiste aos controles de Smart Fit, Wellhub e filiais); entra no Holm com p = 1"
    elif c1 == "significativo" and not (por_area["p"] <= 0.05 and g30["p"] <= 0.05):
        c1 = "frágil à dependência espacial (não passa a 0,05 com cluster por área e na grade de 30 km); entra no Holm com p = 1"
    lab_passa = c1 == "significativo"
    L = ["# BLK-UNI-10, item 3 — % da população na faixa etária real dos alunos (protocolo da bateria §7 + §9.9 + §17.3 + §20 + §21, congelado antes de rodar)", "",
         f"Faixa pela regra pré-registrada (idade real dos alunos, Growth, {FX['n_unidades']} unidades com peso igual, sem o teste e a turma): "
         f"**{FX['rot']} anos**, que reúne {FX['cobertura']:.0%} dos alunos. F = população de {FX['rot']} anos / população com faixa, "
         "na área de 10 min de carro (ou círculo), pelos setores do Censo 2022 (células de sigilo recuperadas pelo total do setor).", "",
         f"**Como ler (§21):** F sobe sobretudo onde há menos pessoas com 50 anos ou mais. Um positivo quer dizer \"áreas com estrutura etária "
         f"menos envelhecida têm mais alunos\", e não \"população na faixa dos alunos\". A composição etária, sozinha, prevê só {pc(REF):+.1f}% de "
         f"alunos por +5 p.p. de F ({pc(REF, dp_res):+.1f}% por DP residual), muito abaixo do que o teste enxerga; **um nulo não refuta que a "
         "idade importe**.", "",
         f"## Laboratório Smart Fit (teste primário; {DIRECAO})", "",
         f"- Funil: {F}.",
         f"- No modelo: n = {len(Sd)} em {Sd.metro.nunique()} áreas. Maior área com {100 * share_big:.0f}% do N. F: mediana {Sd.F.median():.1%} "
         f"(p10 {Sd.F.quantile(.1):.1%}, p90 {Sd.F.quantile(.9):.1%}); DP residual {100 * dp_res:.1f} p.p.",
         "- G* (mínimo entre ρ 0 e ρ 1): " + "; ".join(f"{k_} km {v['Gst']:.1f}" for k_, v in DS.items()) + f". {P['nota']}."]
    if np.isfinite(P.get("coef", np.nan)):
        L += [f"- Coeficiente de F: **{P['coef']:+.3f}** → **{pc(P['coef']):+.1f}% de alunos por +5 p.p.** ({pc(P['coef'], dp_res):+.1f}% por DP residual); n = {P['n']}.",
              f"- **p de decisão ({DIRECAO}; wild cluster bootstrap restrito, Webb, B = {it2.B_BOOT}): {pp:.4f}** (limiar efetivo do Holm {LIM:.4f}). Por quadrícula: "
              + "; ".join(f"{k} km p(coef > 0) {r['p']:.4f}, p(coef < 0) {r['p_oposto']:.4f}" for k, r in PV_.items())
              + f". R² LOO com efeito fixo: {P['r2loo0']:.3f} → {P['r2loo1']:.3f}.",
              f"- Guardas (§21): sem a maior área {sem_big['coef']:+.3f} ({'resiste' if rob(sem_big) else 'NÃO resiste'}); com oferta e centralidade "
              f"{com_of['coef']:+.3f} ({'resiste' if rob(com_of) else 'NÃO resiste'}); cluster por área p {por_area['p']:.4f}, grade de 30 km p {g30['p']:.4f}."]
    L += [f"- c1: **{c1}**.", "", f"## Sensibilidades do laboratório (descritivas; p da grade de {cl0[3:]} km, NÃO comparável ao p de decisão)", "",
          "| versão | n | coef. | efeito por +5 p.p. | p (coef > 0) | p (coef < 0) | G* |", "|---|---|---|---|---|---|---|"]

    def sl(rot, r):
        L.append(f"| {rot} | {r['n']} | {r['coef']:+.3f} | {pc(r['coef']):+.1f}% | {r['p']:.4f} | {r['p_oposto']:.4f} | {r['Gst']:.1f} |")
    sl(f"sem a maior área ({big}) — guarda", sem_big)
    sl("controles de oferta e centralidade (Smart Fit pelo site, Wellhub, filiais a ≤ 500 m) — guarda", com_of)
    sl("cluster = área (metrô ou município) — guarda", por_area)
    sl("cluster = quadrícula de 30 km — guarda", g30)
    sl("controle: log(moradores por domicílio)", lab3(S, cl0, cols_extra=("l_mor",), rng=rng))
    sl("só setores completos (sem recuperar células de sigilo)", lab3(S, cl0, xq="F_comp", rng=rng))
    sl("faixa 15–49 (também a leitura por coorte: quem tinha 15–49 em 2022)", lab3(S, cl0, xq="F_15_49", rng=rng))
    sl("faixa 25–59 (a regra lida por nº de grupos)", lab3(S, cl0, xq="F_25_59", rng=rng))
    sl("faixa 20–59", lab3(S, cl0, xq="F_20_59", rng=rng))
    sl("20–49 entre quem tem 15 anos ou mais (interpretativa)", lab3(S, cl0, xq="F_adultos", rng=rng))
    sl("% com 60 anos ou mais (referência, direção esperada negativa)", lab3(S, cl0, xq="F_60mais", rng=rng))
    sl("% com 0 a 14 anos (referência)", lab3(S, cl0, xq="F_0_14", rng=rng))
    sl(f"só áreas com ≥ {COB_MIN_SENS:.0%} da população com faixa ({int((S.cobertura_faixa >= COB_MIN_SENS).sum())})",
       lab3(S[S.cobertura_faixa >= COB_MIN_SENS], cl0, rng=rng))
    for k_ in DS:
        if k_ not in PV_ and f"cel{k_}" not in (cl0, "cel30"):
            sl(f"cluster = quadrícula de {k_[:-1] + ' km deslocada' if k_.endswith('s') else k_ + ' km'} (G* < 10)", lab3(S, f"cel{k_}", rng=rng))
    sl("só isócronas reais (sem círculos; também a leitura de menor erro de medida)", lab3(S[S.geom_tipo == "isocrona"], cl0, rng=rng))
    sl("só dentro das áreas metropolitanas", lab3(S[S.dentro_metro], cl0, rng=rng))
    Sx = S.assign(idade_12_23=((S.idade_m >= 12) & (S.idade_m <= 23)).astype(float))
    sl("controles de idade da unidade (12–23 meses) e franquia", lab3(Sx, cl0, cols_extra=("idade_12_23", "franquia"), rng=rng))
    if np.isfinite(P.get("coef", np.nan)):
        lomo = {m: lab3(S[S.metro != m], cl0, rng=rng, boot=False)["coef"] for m in cnt.index[cnt >= 20]}
        L += ["", "Tirando uma área com ≥ 20 unidades por vez (coeficiente): " + ", ".join(f"sem {m}: {v:+.3f}" for m, v in lomo.items())
              + f". Mesmo sinal em {sum(np.sign(v) == np.sign(P['coef']) for v in lomo.values())} de {len(lomo)}.", ""]
    # ---------------- Ultra
    Ue = op.empilhado(tr, te, V2, "F", "l_fat", rng, cl="cl_metro")
    trq, teq = tr.assign(Q=tr.F), te.assign(Q=te.F)  # it2.c2c3 corta "acima/abaixo da mediana" pela coluna Q
    Mx = it2.c2c3(trq, teq, V2, ["F"], "l_fat", cal["l_fat"], rng)
    c2, c3, c3r = Mx["dl"] >= 0.02, Mx["dt"] >= 0.02, Mx["dt_rec"] >= 0.02
    coerente = np.isfinite(P.get("coef", np.nan)) and np.sign(Mx["coef"]) == np.sign(P["coef"])
    alvo = ("MELHORA A PRECISÃO" if (c2 and c3 and c3r and coerente) else
            ("CANDIDATA (o c3 só passa por nível)" if (c2 and c3 and coerente) else ("CANDIDATA" if (Mx["dl"] >= 0 and coerente) else "NÃO MELHORA")))
    leitura_nulo = f"; exclui efeitos de ~{pc(it2.mde(D0['se_cl'], max(D0['Gst'] - 1, 1), LIM)):.0f}% ou mais por +5 p.p., mas não refuta o efeito que a composição etária prevê ({pc(REF):+.1f}%)"
    if c1 == "significativo":
        v = alvo + " — leitura: áreas com estrutura etária menos envelhecida têm mais alunos"
    elif c1.startswith("frágil") or c1.startswith("confundido"):
        v = c1.split(";")[0].upper()
    elif c1.startswith("não testável"):
        v = "NÃO TESTÁVEL no laboratório (G* < 10; entra no Holm com p = 1)"
    elif c1.startswith("não significativo após Holm"):
        v = f"NÃO DEMONSTRADO após Holm (p {pp:.4f} > {LIM:.4f})" + leitura_nulo
    else:
        v = ("NÃO DEMONSTRADO no laboratório (não vai à Ultra)" + leitura_nulo
             + (" — efeito na direção OPOSTA (descritivo; vale em todas as grades)" if P.get("p_oposto_max", 1) <= 0.05 else ""))
    L += ["## Ultra (57 unidades, pinos corrigidos)", "",
          f"- F: mediana {SU.F.median():.1%} (p25 {SU.F.quantile(.25):.1%}, p75 {SU.F.quantile(.75):.1%}). Sem efeito fixo de área: o coeficiente mistura "
          "diferença entre cidades e regiões (parte absorvida pelas masters), outro estimando que o do laboratório.",
          f"- Efeito de F (empilhado, cluster por metrô; descritivo): {Ue['coef']:+.3f} → {pc(Ue['coef']):+.1f}% de faturamento por +5 p.p.; p (coef > 0) {Ue['p']:.4f}, "
          f"p (coef < 0) {Ue['p_neg']:.4f}; HC3 IC 90% {pc(Ue['lo']):+.1f}% a {pc(Ue['hi']):+.1f}%.",
          f"- c2/c3 (v2 contra v2 + F; {'CONTAM' if lab_passa else 'só relatados, o laboratório não passou'}): coeficiente nas 39 {Mx['coef']:+.3f} "
          f"(IC 90% {Mx['lo']:+.3f} a {Mx['hi']:+.3f}){'' if coerente else ' — sinal diferente do laboratório'}; estúdios {Mx['studios0']:+.3f} → {Mx['studios1']:+.3f}.",
          f"  LOO {100 * Mx['e_l0']:.1f}% → {100 * Mx['e_l1']:.1f}% (queda {100 * Mx['dl']:+.1f} pp; IC 90% {100 * Mx['ic_dl'][0]:+.1f} a {100 * Mx['ic_dl'][1]:+.1f}); "
          f"teste {100 * Mx['e_t0']:.1f}% → {100 * Mx['e_t1']:.1f}% (queda {100 * Mx['dt']:+.1f} pp; IC 90% {100 * Mx['ic_dt'][0]:+.1f} a {100 * Mx['ic_dt'][1]:+.1f}; "
          f"{Mx['k18']} de {Mx['n_te']} melhoram; recentrado {100 * Mx['dt_rec']:+.1f} pp); viés {100 * Mx['vies0']:+.1f}% → {100 * Mx['vies1']:+.1f}%; "
          f"deslocamento {100 * Mx['desloc']:+.1f}%; queda com F acima da mediana {100 * Mx['dt_alto']:+.1f} pp, abaixo {100 * Mx['dt_baixo']:+.1f} pp.", "",
          f"**Veredito do item 3: {v}.**", ""]
    # ---------------- turma 2026 (congela sempre)
    est = pd.read_csv(op.MET, sep=";", encoding="utf-8-sig", index_col=0).metragem_estimada_m2.dropna()
    of = d.tam_metragem_m2.dropna(); m2 = pd.concat([of, est[~est.index.isin(of.index)]])
    cand = Aa.reindex(pv.index).drop(columns=["l_m2"]).join(np.log(m2).rename("l_m2"))
    cand["master_id"] = pv.master_id
    cand = dummies(cand)
    cand["F"] = AU.F.reindex(cand.index)
    me = float(SU.F.mean()); g = Ue["coef"]
    out = pd.DataFrame(index=pv.index)
    out["F"] = cand.F.round(4)
    out["prev_v2dom_cal2026"] = pv.prev_v2dom_cal2026
    out["prev_v2dom_x_I"] = (pv.prev_v2dom_cal2026 * np.exp(g * (cand.F - me))).round(0)
    out["prev_v2dom_mesmo_nivel"] = (pv.prev_v2dom_cal2026 * np.exp(g * (cand.F.mean() - me))).round(0)
    out["coef_lab"] = round(P.get("coef", np.nan), 4)
    okm = cand[V2 + ["F"]].notna().all(axis=1)
    p_c = pd.Series(np.nan, index=cand.index); p_c[okm] = np.exp(X_(cand[okm], V2 + ["F"]) @ Mx["b1"] + cal["l_fat"])
    out["prev_v2_I_39_cal2026"] = p_c.round(0)
    out.to_csv(arq, sep=";", encoding="utf-8-sig")
    h = sha(arq)
    with (out_dir / REG3.name).open("a", encoding="utf-8") as fh:
        fh.write(f"Turma 2026 congelada pelo item 3 em {datetime.now():%Y-%m-%d %H:%M} (faixa {FX['rot']}; gamma F Ultra {g:+.4f}; media F {me:.4f}; "
                 f"lab: coef {P.get('coef', np.nan):+.4f}, p de decisao {pp:.4f}, limiar {LIM:.4f}, grades {VALIDAS}, {DIRECAO}): {h} *{arq.name}\n")
    L += ["## Turma de 2026 congelada", "", f"`{arq.name}`: {len(out)} unidades; γ̂ (Ultra) = {g:+.3f}. SHA-256 `{h}`.",
          "Conferência (§21): junto com o BLK-UNI-12, quando ≥ 10 das 16 tiverem 12 meses de vida e ≥ 3 meses válidos. Métrica: a inclinação "
          "do resíduo da v2 congelada sobre (F − média) dentro da turma, comparada a γ̂ (EP ≈ 0,19 por +5 p.p., detectável de ~+60%: confere "
          "quase só o nível); a `prev_v2dom_x_I` só conta se o erro típico dela vencer o da `prev_v2dom_mesmo_nivel`.", ""]
    res.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
