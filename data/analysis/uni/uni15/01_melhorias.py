# -*- coding: utf-8 -*-
"""BLK-UNI-15 (protocolo_uni15.md v1.1, 06/10): melhorias nos TRES modelos (faturamento F, balcao B, agregador A) + total recombinado.
 T1 regiao no lugar da master (39/18); T2 treino ampliado (~60, dummy de ano); T3 decisao de abrir sem agregador (F e B; conferencia
 interna, duas leituras: sem e com precoces); T4 previsao em dois tempos (abertura meses 1-3 + v2; so' depois de abrir).
Modos (um por vez): --seca | --ensaio | --registrar | --rodar   (.venv, PYTHONPATH=src). Sem Base Consolidada; LOCAL_ so' como SHA."""
import glob
import hashlib
import importlib.util
import sys
import types
import warnings
from datetime import datetime
from pathlib import Path

try:
    import h3  # noqa: F401
except ImportError:
    for _k in [k for k in sys.modules if k == "h3" or k.startswith("h3.")]:
        del sys.modules[_k]
    sys.modules["h3"] = types.ModuleType("h3")

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

warnings.filterwarnings("ignore")
AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
REPO = UNI.parent.parent.parent
PROT = AQUI / "protocolo_uni15.md"
REG_PRE = AQUI / "REGISTRO_PRE.txt"
RES = AQUI / "resultado_uni15.md"
PREV = AQUI / "previsoes_turma_2026_uni15.csv"
REG_POS = AQUI / "REGISTRO_CONGELAMENTO_turma_2026.txt"
OUT = Path(r"C:\Users\Felipe\OneDrive - Grupo Ultra\Área de Trabalho\Análises - Motor de Expansão\Exploratória BLK-UNI\09 - Melhorias nos três modelos")
ENSAIO = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad\uni15_ensaio")
JAN = ("2026-01", "2026-08")
TURMA_B_MADURAS = ["boa-vista-ba", "ceilandia-qnm33-df", "bangu-rj"]
CEGAS = ["belford-roxo-rj", "novo-gama-df", "paulinia-sp", "domingos-ferreira-pe", "bonsucesso-rj"]
TRAVADAS_FORA = ["icarai-rj"]
SEM_AG_MADURAS = ["botafogo-rj", "bangu-rj"]
SEED, NB, ALFA, Z90 = 20261008, 5000, 0.05, 1.6449
NB_REFIT = 2000
MODELOS = ("faturamento", "balcão", "agregador")
TODOS = MODELOS + ("total recombinado",)
VERS = {"masters": "com masters (hoje)", "R1_fora_DFGO": "R1: masters de fora do DF/GO juntas", "R2_SP_outras": "R2: região (DF/GO, SP ou outras)"}
GRUPO = {"mr_M2": "master M2", "mr_M3": "master M3", "mr_outras": "outras masters", "reg_fora": "fora do DF/GO", "reg_SP": "SP", "reg_outros": "outras UFs"}
CAL_NOME = {"faturamento": "l_fat", "balcão": "calB", "agregador": "calA"}
# travas do --rodar (contagens estruturais da --seca de 06/10, sem desfecho)
TRAVA_T2_N = {"faturamento": 60, "balcão": 60, "agregador": 58}
TRAVA_T3_SEM_AG = {"sem_precoces": {"botafogo-rj", "bangu-rj", "flow-pr", "picarras-sc", "bertioga-sp"}}   # --seca de 06/10
TRAVA_T4_N = {"faturamento": 42, "balcão": 47, "agregador": 40}   # --seca de 06/10, com a regra do TotalPass
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 150, "font.size": 9, "axes.grid": True, "grid.alpha": .3})
_SEQ = [0]


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rng_():
    _SEQ[0] += 1
    return np.random.default_rng(SEED + _SEQ[0])


def et(e):
    e = np.asarray(e, float); e = e[np.isfinite(e)]
    return float(np.median(np.abs(np.exp(e) - 1))) if len(e) else np.nan


def pct(x):
    return 100 * (np.exp(x) - 1)


def r2(y, e):
    y, e = np.asarray(y, float), np.asarray(e, float); ok = np.isfinite(y) & np.isfinite(e); y, e = y[ok], e[ok]
    return float(1 - np.sum(e ** 2) / np.sum((y - y.mean()) ** 2)) if len(y) > 2 else np.nan


def dif_boot(a, b, fn=et, nb=NB, nivel=.90):
    """Diferenca fn(a) - fn(b) (pareada), faixa e p = fracao das reamostras com diferenca >= 0."""
    a, b = np.asarray(a, float), np.asarray(b, float); ok = np.isfinite(a) & np.isfinite(b); a, b = a[ok], b[ok]
    rng = rng_(); n = len(a)
    v = np.array([fn(a[ii]) - fn(b[ii]) for ii in (rng.integers(0, n, n) for _ in range(nb))])
    q = (1 - nivel) / 2
    return float(fn(a) - fn(b)), float(np.percentile(v, 100 * q)), float(np.percentile(v, 100 * (1 - q))), float(np.mean(v >= 0)), int(n)


def ols(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


def X_(D, cols):
    return np.column_stack([np.ones(len(D))] + [D[c].to_numpy(float) for c in cols])


def loo(D, cols, y):
    y = np.asarray(y, float); n = len(D); X = X_(D, cols); e = np.empty(n)
    for i in range(n):
        m = np.ones(n, bool); m[i] = False
        e[i] = y[i] - X[i] @ ols(X[m], y[m])
    return e


def lomo(D, cols, y, metro, excluir=None):
    y = np.asarray(y, float); e = np.full(len(D), np.nan); X = X_(D, cols)
    for mm in np.unique(metro):
        if excluir is not None and mm == excluir:
            continue
        s = metro == mm
        e[s] = y[s] - X[s] @ ols(X[~s], y[~s])
    return e


def hc3(D, cols, y):
    """Coeficientes e erro-padrao robusto (HC3)."""
    y = np.asarray(y, float); X = X_(D, cols); XtXi = np.linalg.pinv(X.T @ X); b = XtXi @ X.T @ y; e = y - X @ b
    h = np.einsum("ij,jk,ik->i", X, XtXi, X); w = (e / np.clip(1 - h, 1e-6, None)) ** 2
    V = XtXi @ (X.T * w) @ X @ XtXi
    idx = ["const"] + list(cols)
    return pd.Series(b, index=idx), pd.Series(np.sqrt(np.clip(np.diag(V), 0, None)), index=idx)


def queda_txt(d, onde):
    return f"{onde} piora {d:.1f} ponto(s)" if d > 0 else f"{onde} cai {-d:.1f} ponto(s), menos de 2"


def fac(Bs, idx):
    return Bs["u14"].fac_cadastro(Bs, pd.Index(idx))


def insumos():
    kpi = glob.glob(str(REPO / "data" / "validacao" / "KPIs_Smart_*.xlsx"))
    b = {"protocolo": PROT, "script": Path(__file__), "fato_unidade_mes": UNI / "fato_unidade_mes.parquet", "dim_unidade": UNI / "dim_unidade.parquet",
         "local_demanda_totalpass": UNI / "LOCAL_demanda_totalpass_por_unidade.parquet", "metragem_time": UNI / "coleta_metragem" / "metragem_time_expansao_2026-10-06.csv",
         "metragem_satelite": UNI / "coleta_metragem" / "metragem_estimada_2026-09-29.csv", "curva_uni03": UNI / "uni03" / "curva_uni03.csv",
         "turma_2026": UNI / "previsao_2026" / "previsoes_turma_2026.csv", "turma_2026_v2": UNI / "previsao_2026" / "previsoes_turma_2026_v2_domiciliar.csv",
         "confirmacao_uni02": UNI / "uni02" / "confirmacao_por_unidade.csv", "master_id_cadastro": UNI / "alavancas" / "master_id_cadastro.csv",
         "mod_uni14": UNI / "uni14" / "01_validacao_ampliada.py", "mod_duas_partes": UNI / "uni09" / "01_duas_partes.py",
         "mod_termometro": UNI / "termometro" / "01_termometro.py", "mod_evidencias": UNI / "manaus_volume" / "02_evidencias.py",
         "mod_alavancas": UNI / "alavancas" / "01_alavancas.py", "mod_incerteza": UNI / "uni07" / "01_incerteza.py", "mod_exploracao": UNI / "uni01" / "01_exploracao.py",
         "mod_confirmacao": UNI / "uni02" / "01_confirmacao.py", "mod_comparacao_uni05": UNI / "uni05" / "01_comparacao.py",
         "mod_premissas_manaus": UNI / "simulacoes" / "manaus_premissas_corrigidas.py", "mod_consolidar_metragem": UNI / "coleta_metragem" / "02_consolidar.py",
         "dim_viabilidade": REPO / "src" / "motor_expansao" / "dimensionamento" / "viabilidade_ponto.py",
         "dim_catchment": REPO / "src" / "motor_expansao" / "dimensionamento" / "catchment_batch.py",
         "dim_config": REPO / "src" / "motor_expansao" / "dimensionamento" / "config.py", "dim_simulador": REPO / "src" / "motor_expansao" / "dimensionamento" / "simulador.py"}
    if len(kpi) == 1:
        b["kpis_smart"] = Path(kpi[0])
    return b


# ------------------------------------------------------------------ montagem
def regioes(D, d):
    uf = d.uf.reindex(D.index)
    D["uf"] = uf.to_numpy()
    D["reg_fora"] = (~uf.isin(["DF", "GO"])).astype(float).to_numpy()
    D["reg_SP"] = (uf == "SP").astype(float).to_numpy()
    D["reg_outros"] = (~uf.isin(["DF", "GO", "SP"])).astype(float).to_numpy()
    return D


def specs(Bs):
    V2 = Bs["V2"]; base_ = ["l_m2", "l_renda_dom", "l_pop"]
    return {"masters": V2, "R1_fora_DFGO": base_ + ["reg_fora", "studios"], "R2_SP_outras": base_ + ["reg_SP", "reg_outros", "studios"]}


def alvos(D, fr):
    """y de cada modelo; A normalizado pelo fator de aceite do cadastro (fr)."""
    return {"faturamento": D.Y_tot.to_numpy(float), "balcão": D.Y_B.to_numpy(float),
            "agregador": D.Y_A.to_numpy(float) - np.log(np.where(fr > 0, fr, np.nan))}


def frac_agregador(f, unidades, ini, fim, mv_min=12):
    g = f[f.valido & (f.competencia >= ini) & (f.competencia <= fim) & (f.mv >= mv_min) & f.unidade_id.isin(unidades)]
    return (g.AG > 0).groupby(g.unidade_id).mean()


def montar_bases(Bs):
    u14, u9, d, f = Bs["u14"], Bs["u9"], Bs["d"], Bs["f"]
    tr, te = Bs["tr"].copy(), Bs["te"].copy()
    m2, fonte = u14.metragem(Bs)
    Y26 = u9.partes(f, *JAN)
    tb = u14.montar(Bs, TURMA_B_MADURAS, m2).join(Y26.drop(columns=[c for c in Y26.columns if c in ("l_pag",)]), how="inner")
    assert set(tb.index) == set(TURMA_B_MADURAS), tb.index
    for D, ano in ((tr, 0.0), (te, 1.0), (tb, 1.0)):
        regioes(D, d); D["ano2026"] = ano
    fa = pd.concat([frac_agregador(f, tr.index, "2025-01", "2025-12"), frac_agregador(f, list(te.index) + TURMA_B_MADURAS, *JAN)])
    for D in (tr, te, tb):
        D["sem_agregador"] = (fa.reindex(D.index) < .5).astype(float)
    return tr, te, tb, m2, fonte


# ------------------------------------------------------------------ T1 regiao (39/18)
def fit2p(Bs, D, cols, fr=None):
    """Duas partes sem penalizacao (igual ao u14.ajusta): B e A* por OLS; k = media do total - lse no treino."""
    fr = fac(Bs, D.index) if fr is None else fr
    yB = D.Y_B.to_numpy(float); yA = D.Y_A.to_numpy(float) - np.log(np.where(fr > 0, fr, np.nan))
    X = X_(D, cols); okA = np.isfinite(yA)
    bB, bA = ols(X, yB), ols(X[okA], yA[okA])
    k = float(np.nanmean(D.Y_tot.to_numpy(float) - Bs["u9"].lse(X @ bB, X @ bA, fr)))
    return bB, bA, k


def pred2p(Bs, m, D, cols, fr=None):
    bB, bA, k = m; X = X_(D, cols); fr = fac(Bs, D.index) if fr is None else fr
    return Bs["u9"].lse(X @ bB, X @ bA, fr) + k


def efeito_total(Bs, D, cols):
    """Efeito de cada grupo (contra DF/GO) no total recombinado = media nas unidades de lse(grupo=1) - lse(todos os grupos=0).
    Faixa 90% por reamostragem das unidades com reajuste."""
    grp = [c for c in cols if c.startswith(("mr_", "reg_"))]

    def ef(Dx):
        f_ = fac(Bs, Dx.index); m = fit2p(Bs, Dx, cols, f_)
        Z0 = Dx.copy(); Z0[grp] = 0.0; p0 = pred2p(Bs, m, Z0, cols, f_)
        out = {}
        for c in grp:
            Z1 = Z0.copy(); Z1[c] = 1.0
            out[c] = float(np.mean(pred2p(Bs, m, Z1, cols, f_) - p0))
        return out
    pt = ef(D); rng = rng_(); bs = []
    for _ in range(NB_REFIT):
        Dx = D.iloc[rng.integers(0, len(D), len(D))]
        bs.append({c: np.nan for c in grp} if any(Dx[c].sum() == 0 for c in grp) else ef(Dx))
    B_ = pd.DataFrame(bs)
    return {c: (pt[c], float(np.nanpercentile(B_[c], 5)), float(np.nanpercentile(B_[c], 95)), float(B_[c].isna().mean())) for c in grp}


def t1(Bs, tr, te):
    d = Bs["d"]
    fr, ft = fac(Bs, tr.index), fac(Bs, te.index)
    Ytr = alvos(tr, fr)
    yte = {"faturamento": te.Y_tot.to_numpy(float), "balcão": te.Y_B.to_numpy(float), "agregador": te.Y_A.to_numpy(float)}
    ytr_raw = {"faturamento": tr.Y_tot.to_numpy(float), "balcão": tr.Y_B.to_numpy(float), "agregador": tr.Y_A.to_numpy(float)}
    cal = {"faturamento": Bs["cal"]["l_fat"], "balcão": Bs["calB"], "agregador": Bs["calA"]}
    off = {"faturamento": 0.0, "balcão": 0.0, "agregador": np.log(np.where(ft > 0, ft, np.nan))}
    metro = d.iso_metro.reindex(tr.index).fillna(-1).to_numpy()
    SPC = specs(Bs)
    R, EF = {}, []
    for mod_, y in Ytr.items():
        okm = np.isfinite(y)
        for ver, cols in SPC.items():
            Dm, ym = tr[okm], y[okm]
            el = np.full(len(tr), np.nan); el[okm] = loo(Dm, cols, ym)
            b, se = hc3(Dm, cols, ym)
            ete = yte[mod_] - (X_(te, cols) @ b.to_numpy() + cal[mod_] + off[mod_])
            elm = np.full(len(tr), np.nan); elm[okm] = lomo(Dm, cols, ym, metro[okm])
            R[(mod_, ver)] = dict(y=y, yraw=ytr_raw[mod_], yte=yte[mod_], loo=el, test=ete, lomo=elm, lomo_sb=np.where(metro == 1, np.nan, elm))
            for c in [c for c in cols if c.startswith(("mr_", "reg_"))]:
                EF.append({"modelo": mod_, "versao": ver, "grupo": GRUPO.get(c, c), "efeito_contra_DFGO_pct": pct(b[c]),
                           "faixa90_lo_pct": pct(b[c] - Z90 * se[c]), "faixa90_hi_pct": pct(b[c] + Z90 * se[c]), "n_treino_no_grupo": int(Dm[c].sum()),
                           "como_medido": "coeficiente, faixa robusta (HC3)"})
    SP = {f"2p::{ver}": dict(fam="2p", B=cols, A=cols) for ver, cols in SPC.items()}
    Rt, _, _ = Bs["u14"].avalia(Bs, {"v2": Bs["u14"].specs(Bs)["v2"], **SP}, tr, te, {})
    for ver, cols in SPC.items():
        r = Rt[f"2p::{ver}"]
        R[("total recombinado", ver)] = dict(y=tr.Y_tot.to_numpy(float), yraw=tr.Y_tot.to_numpy(float), yte=te.Y_tot.to_numpy(float), loo=r["loo"],
                                             test=r["test"], lomo=r["lomo"], lomo_sb=np.where(metro == 1, np.nan, r["lomo"]))
        for c, (p_, lo, hi, nan_) in efeito_total(Bs, tr, cols).items():
            EF.append({"modelo": "total recombinado", "versao": ver, "grupo": GRUPO.get(c, c), "efeito_contra_DFGO_pct": pct(p_), "faixa90_lo_pct": pct(lo),
                       "faixa90_hi_pct": pct(hi), "n_treino_no_grupo": int(tr[c].sum()),
                       "como_medido": f"média nas 39 de (total com o grupo − total como DF/GO); faixa por {NB_REFIT} reamostragens com reajuste ({100 * nan_:.0f}% sem o grupo)"})
    linhas = []
    for (mod_, ver), r in R.items():
        b_ = R[(mod_, "masters")]
        L = {"modelo": mod_, "versao": ver, "n_39": int(np.isfinite(r["loo"]).sum()), "n_teste": int(np.isfinite(r["test"]).sum()),
             "R2_39": r2(r["yraw"], r["loo"]), "erro_39_pct": 100 * et(r["loo"]), "R2_teste": r2(r["yte"], r["test"]), "erro_teste_pct": 100 * et(r["test"]),
             "erro_teste_recentrado_pct": 100 * et(r["test"] - np.nanmedian(r["test"])),
             "erro_regiao_nova_sem_brasilia_pct": 100 * et(r["lomo_sb"]), "erro_regiao_nova_todas_pct": 100 * et(r["lomo"])}
        if ver != "masters":
            d1 = dif_boot(r["loo"], b_["loo"]); d2 = dif_boot(r["test"], b_["test"])
            L.update({"dif_39_pontos": 100 * d1[0], "dif_39_faixa90_lo": 100 * d1[1], "dif_39_faixa90_hi": 100 * d1[2], "p_39": d1[3],
                      "dif_teste_pontos": 100 * d2[0], "dif_teste_faixa90_lo": 100 * d2[1], "dif_teste_faixa90_hi": 100 * d2[2],
                      "dif_teste_recentrado_pontos": L["erro_teste_recentrado_pct"] - 100 * et(b_["test"] - np.nanmedian(b_["test"])),
                      "dif_regiao_nova_sem_brasilia_pontos": L["erro_regiao_nova_sem_brasilia_pct"] - 100 * et(b_["lomo_sb"])})
        linhas.append(L)
    T = pd.DataFrame(linhas)
    for mod_ in TODOS:                      # Holm k = 2 por modelo (alfa 0,05 de um lado)
        m = (T.modelo == mod_) & (T.versao != "masters")
        ps = T.loc[m, "p_39"].sort_values(); ok = True
        for i, (ix, p) in enumerate(ps.items()):
            ok = ok and p <= ALFA / (len(ps) - i); T.loc[ix, "holm_ok"] = ok
        for ix in T.index[m]:
            r_ = T.loc[ix]; motivos = []
            if r_.dif_39_pontos > -2:
                motivos.append(queda_txt(r_.dif_39_pontos, "nas 39"))
            elif not bool(r_.holm_ok):
                motivos.append("nas 39 a queda não se distingue do acaso")
            if r_.dif_teste_pontos > -2:
                motivos.append(queda_txt(r_.dif_teste_pontos, "no teste"))
            if r_.dif_teste_recentrado_pontos > -2:
                motivos.append("no teste sem o nível do ano cai menos de 2")
            T.loc[ix, "checagem"] = "passa" if not motivos else "não passa"
            T.loc[ix, "por_que"] = "; ".join(motivos)
            T.loc[ix, "regiao_nova_nao_piora"] = bool(r_.dif_regiao_nova_sem_brasilia_pontos <= 0)
    return T, R, pd.DataFrame(EF)


def quem_muda(Bs, tr, te, DC):
    DUM = Bs["DUM"]
    gm = lambda D: pd.Series(["M1 (= DF/GO)" if (D.loc[u, DUM] == 0).all() else GRUPO.get([c for c in DUM if D.loc[u, c] == 1][0], "?") for u in D.index], index=D.index)
    gr2 = lambda D: D.uf.map(lambda x: "DF/GO" if x in ("DF", "GO") else ("SP" if x == "SP" else "outras UFs"))
    trm, trr = gm(tr), gr2(tr)
    out = []
    for conj, D in (("teste (18)", te), ("cega da turma 2026", DC)):
        dm, dr = gm(D), gr2(D)
        for u in D.index:
            viz_m, viz_r = set(trm.index[trm == dm[u]]), set(trr.index[trr == dr[u]])
            out.append({"unidade": u, "conjunto": conj, "uf": D.loc[u, "uf"], "master": D.loc[u, "master_id"], "grupo_hoje": dm[u],
                        "treino_no_grupo_hoje": len(viz_m), "grupo_R2": dr[u], "treino_no_grupo_R2": len(viz_r),
                        "aprende_com_outras_unidades": "sim" if viz_m != viz_r else "não"})
    return pd.DataFrame(out)


# ------------------------------------------------------------------ T2 treino ampliado
def t2(Bs, tr, te, tb, R_t1, DT, DC):
    d = Bs["d"]
    P = pd.concat([tr, te, tb]); fp = fac(Bs, P.index)
    Yp = alvos(P, fp); Yraw = {"faturamento": P.Y_tot.to_numpy(float), "balcão": P.Y_B.to_numpy(float), "agregador": P.Y_A.to_numpy(float),
                               "total recombinado": P.Y_tot.to_numpy(float)}
    metro = d.iso_metro.reindex(P.index).fillna(-1).to_numpy()
    n39, n18 = len(tr), len(te); i39 = np.arange(len(P)) < n39; i57 = np.arange(len(P)) < n39 + n18
    cal = {"faturamento": Bs["cal"]["l_fat"], "balcão": Bs["calB"], "agregador": Bs["calA"]}
    SPC = specs(Bs); E, FX, ANO, prev, NS = {}, [], [], {}, {}
    DT1 = DT.assign(ano2026=1.0); fdt = fac(Bs, DT.index)
    for ver, cols0 in SPC.items():
        cols = cols0 + ["ano2026"]
        for mod_ in MODELOS:
            y = Yp[mod_]; ok = np.isfinite(y); NS[(mod_, ver)] = int(ok.sum())
            el = np.full(len(P), np.nan); el[ok] = loo(P[ok], cols, y[ok])
            elm = np.full(len(P), np.nan); elm[ok] = lomo(P[ok], cols, y[ok], metro[ok])
            E[(mod_, ver)] = dict(e=el, lomo=elm)
            b, se = hc3(P[ok], cols, y[ok])
            r1 = R_t1[(mod_, ver)]; o1 = np.isfinite(r1["y"]); b39, se39 = hc3(tr[o1], cols0, r1["y"][o1])
            for c in ("l_m2", "l_renda_dom", "l_pop", "studios"):
                FX.append({"modelo": mod_, "versao": ver, "variavel": c, "coef_39": b39[c], "largura_faixa90_39": 2 * Z90 * se39[c],
                           "coef_ampliado": b[c], "largura_faixa90_ampliado": 2 * Z90 * se[c], "razao_largura_ampliado_sobre_39": se[c] / se39[c]})
            ANO.append({"modelo": mod_, "versao": ver, "ajuste_2026_dummy_pct": pct(b["ano2026"]), "faixa90_lo_pct": pct(b["ano2026"] - Z90 * se["ano2026"]),
                        "faixa90_hi_pct": pct(b["ano2026"] + Z90 * se["ano2026"]), "calibracao_calendario_pct": pct(cal[mod_])})
            prev[(mod_, ver)] = pd.Series(X_(DT1, cols) @ b.to_numpy(), index=DT.index)
        yT = P.Y_tot.to_numpy(float); eT = np.full(len(P), np.nan)
        for i in range(len(P)):
            m = np.ones(len(P), bool); m[i] = False
            eT[i] = yT[i] - pred2p(Bs, fit2p(Bs, P[m], cols, fp[m]), P.iloc[[i]], cols, fp[[i]])[0]
        elmT = np.full(len(P), np.nan)
        for mm in np.unique(metro):
            s = metro == mm
            elmT[s] = yT[s] - pred2p(Bs, fit2p(Bs, P[~s], cols, fp[~s]), P[s], cols, fp[s])
        E[("total recombinado", ver)] = dict(e=eT, lomo=elmT); NS[("total recombinado", ver)] = int(np.isfinite(eT).sum())
        mT = fit2p(Bs, P, cols, fp)
        prev[("balcão_sem_k", ver)] = pd.Series(X_(DT1, cols) @ mT[0], index=DT.index)
        prev[("agregador_ambos_sem_k", ver)] = pd.Series(X_(DT1, cols) @ mT[1], index=DT.index)
        prev[("k", ver)] = pd.Series(mT[2], index=DT.index)
        prev[("total recombinado", ver)] = pd.Series(pred2p(Bs, mT, DT1, cols, fdt), index=DT.index)
    linhas, RN = [], []
    rec = lambda e: np.concatenate([e[:n39] - np.nanmedian(e[:n39]), e[n39:] - np.nanmedian(e[n39:])])
    for mod_ in TODOS:
        for ver in SPC:
            r1 = R_t1[(mod_, ver)]
            e39 = np.concatenate([r1["loo"], r1["test"]]); eA = E[(mod_, ver)]["e"][i57]
            dd = dif_boot(eA, e39)
            linhas.append({"modelo": mod_, "versao": ver, "n_treino_ampliado": NS[(mod_, ver)], "n_comparacao": dd[4],
                           "erro_57_treino_39_pct": 100 * et(e39), "erro_57_ampliado_pct": 100 * et(eA),
                           "dif_pontos": 100 * dd[0], "dif_faixa90_lo": 100 * dd[1], "dif_faixa90_hi": 100 * dd[2], "p": dd[3],
                           "dif_recentrado_por_ano_pontos": 100 * (et(rec(eA)) - et(rec(e39))),
                           "erro_39_treino_39_pct": 100 * et(e39[:n39]), "erro_39_ampliado_pct": 100 * et(eA[:n39]),
                           "erro_18_treino_39_pct": 100 * et(e39[n39:]), "erro_18_ampliado_pct": 100 * et(eA[n39:]),
                           "R2_57_treino_39": r2(Yraw[mod_][i57], e39), "R2_57_ampliado": r2(Yraw[mod_][i57], eA)})
            lA = E[(mod_, ver)]["lomo"][i39]; mt39 = metro[i39]
            RN.append({"modelo": mod_, "versao": ver, "regiao_nova_39_treino_39_pct": 100 * et(r1["lomo"]), "regiao_nova_39_ampliado_pct": 100 * et(lA),
                       "regiao_nova_39_sem_brasilia_treino_39_pct": 100 * et(r1["lomo_sb"]),
                       "regiao_nova_39_sem_brasilia_ampliado_pct": 100 * et(np.where(mt39 == 1, np.nan, lA))})
    T = pd.DataFrame(linhas)
    for mod_ in TODOS:                       # Holm k = 3 por modelo
        m = T.modelo == mod_
        ps = T.loc[m, "p"].sort_values(); ok = True
        for i, (ix, p) in enumerate(ps.items()):
            ok = ok and p <= ALFA / (len(ps) - i); T.loc[ix, "holm_ok"] = ok
        for ix in T.index[m]:
            r_ = T.loc[ix]; motivos = []
            if r_.dif_pontos > -2:
                motivos.append(queda_txt(r_.dif_pontos, "nas 57"))
            elif not bool(r_.holm_ok):
                motivos.append("a queda não se distingue do acaso")
            T.loc[ix, "checagem"] = "passa" if not motivos else "não passa"
            T.loc[ix, "por_que"] = "; ".join(motivos)
            T.loc[ix, "aviso_recentrado"] = "o ganho some sem o nível de cada ano" if (not motivos and r_.dif_recentrado_por_ano_pontos > -2) else ""
    # leitura descritiva: Botafogo e Bangu (RJ, M3, sem agregador) e o que as cegas do RJ herdam
    DESC = []
    for mod_, ycol in (("faturamento", "Y_tot"), ("balcão", "Y_B")):
        for ver, cols0 in SPC.items():
            gcols = [c for c in cols0 if c in ("mr_M3", "reg_fora", "reg_outros")]
            var = {"treino 39": (tr, cols0, cal[mod_]), "ampliado": (P, cols0 + ["ano2026"], 0.0),
                   "ampliado sem Botafogo e Bangu": (P.drop(SEM_AG_MADURAS), cols0 + ["ano2026"], 0.0),
                   "ampliado + variável sem agregador": (P, cols0 + ["ano2026", "sem_agregador"], 0.0)}
            for nome, (D, cols, c_) in var.items():
                b = ols(X_(D, cols), D[ycol].to_numpy(float))
                Z = DC.assign(ano2026=1.0, sem_agregador=0.0)
                p_ = X_(Z, cols) @ b + c_
                row = {"modelo": mod_, "versao": ver, "variante": nome}
                for c in gcols:
                    row[f"efeito_{GRUPO.get(c, c).replace(' ', '_')}_pct"] = pct(b[1 + cols.index(c)])
                for u in ("belford-roxo-rj", "bonsucesso-rj"):
                    row[f"prev_{u}_mil_reais"] = float(np.exp(p_[list(DC.index).index(u)]) / 1000) if u in DC.index else np.nan
                DESC.append(row)
    return T, pd.DataFrame(RN), pd.DataFrame(ANO), pd.DataFrame(FX), pd.DataFrame(DESC), prev


# ------------------------------------------------------------------ T3 sem agregador (F e B): conferencia interna
def candidatos(Bs, excluir, m2, fonte):
    f, d, A = Bs["f"], Bs["d"], Bs["A"]
    cv = pd.read_csv(UNI / "uni03" / "curva_uni03.csv", sep=";", encoding="utf-8-sig")
    curva = {s: cv[cv.serie == s].set_index("k").p50 for s in ("faturamento", "pagantes")}
    cf = lambda mv, s: mv.astype(int).map(lambda k: 1.0 if k >= 12 else curva[s].get(k, np.nan)).to_numpy(float)
    g = f[f.valido & (f.competencia >= JAN[0]) & (f.competencia <= JAN[1])]
    us = sorted(set(g[g.mv >= 3].unidade_id) - set(excluir))
    rows, fora = [], []
    for u in us:
        if u in TRAVADAS_FORA:
            fora.append({"unidade": u, "motivo": "travada por nome desde o UNI-14"}); continue
        gu = g[g.unidade_id == u].sort_values("competencia")
        mad, jov, pre = gu[gu.mv >= 12], gu[gu.mv.between(6, 11)], gu[gu.mv >= 3]
        if len(mad) >= 3:
            fora.append({"unidade": u, "motivo": "madura em 2026, fora do treino, do teste e da turma B"}); continue
        if len(jov) >= 3:
            regra, M = "jovem", jov
        elif len(pre) >= 2:
            regra, M = "precoce", pre.tail(3)
        else:
            fora.append({"unidade": u, "motivo": f"só {len(pre)} mês válido com mês de vida ≥ 3 até {JAN[1]}"}); continue
        if (M.BAL <= 0).any():
            fora.append({"unidade": u, "motivo": f"{regra}: mês com balcão ≤ 0 na janela"}); continue
        a = A.loc[u] if u in A.index else None
        falta = [n_ for n_, ok in (("cadastro", a is not None), ("master", a is not None and pd.notna(a.get("master_id"))),
                                    ("renda", a is not None and pd.notna(a.get("l_renda_dom"))), ("população", a is not None and pd.notna(a.get("l_pop"))),
                                    ("estúdio", a is not None and pd.notna(a.get("studios"))), ("metragem", pd.notna(m2.get(u)))) if not ok]
        if falta:
            fora.append({"unidade": u, "motivo": f"{regra}: sem " + ", ".join(falta)}); continue
        lf = np.log(M.faturamento.to_numpy(float))
        rows.append({"unidade_id": u, "regra": regra, "n_meses": len(M), "mv_min": float(M.mv.min()), "mv_max": float(M.mv.max()),
                     "Y_tot": float(np.mean(lf - np.log(cf(M.mv, "faturamento")))), "Y_tot_pag": float(np.mean(lf - np.log(cf(M.mv, "pagantes")))),
                     "Y_B": float(np.mean(np.log(M.BAL.to_numpy(float)) - np.log(cf(M.mv, "pagantes")))),
                     "sem_agregador": float((M.AG > 0).mean() < .5), "fonte_m2": fonte.get(u)})
    return (pd.DataFrame(rows).set_index("unidade_id") if rows else pd.DataFrame()), pd.DataFrame(fora)


def coef_sem(D, cols, ycol):
    if D.sem_agregador.sum() == 0 or D.sem_agregador.sum() == len(D):
        return np.nan
    return float(ols(X_(D, cols), D[ycol].to_numpy(float))[-1])


def t3(Bs, tr, te, tb, m2, fonte, DC):
    u14, d = Bs["u14"], Bs["d"]
    J, fora = candidatos(Bs, list(tr.index) + list(te.index) + list(tb.index) + CEGAS, m2, fonte)
    DJ = u14.montar(Bs, J.index, m2).join(J); regioes(DJ, d)
    DJ["ano2026"] = 1.0; DJ["jovem"] = (DJ.regra == "jovem").astype(float); DJ["precoce"] = (DJ.regra == "precoce").astype(float)
    base = pd.concat([tr, te, tb]).assign(jovem=0.0, precoce=0.0, regra="madura")
    base["Y_tot_pag"] = base.Y_tot; base["fonte_m2"] = fonte.reindex(base.index).to_numpy()
    V2 = Bs["V2"]
    LEIT = {"sem_precoces": pd.concat([base, DJ[DJ.regra == "jovem"]]), "com_precoces": pd.concat([base, DJ])}
    linhas, rob, det, prev = [], [], [], {}
    for lei, P in LEIT.items():
        extra = ["ano2026", "jovem"] + (["precoce"] if lei == "com_precoces" else [])
        cols0 = V2 + extra; cols1 = cols0 + ["sem_agregador"]
        sem = P.sem_agregador.to_numpy() == 1
        for mod_, ycol in (("faturamento", "Y_tot"), ("balcão", "Y_B")):
            y = P[ycol].to_numpy(float)
            e0, e1 = loo(P, cols0, y), loo(P, cols1, y)
            b1 = ols(X_(P, cols1), y); coef = float(b1[-1])
            rng = rng_(); bs = []
            for _ in range(NB_REFIT):
                bs.append(coef_sem(P.iloc[rng.integers(0, len(P), len(P))], cols1, ycol))
            bs = np.asarray(bs, float)
            cai_sem, piora_geral = 100 * (et(e1[sem]) - et(e0[sem])), 100 * (et(e1) - et(e0))
            linhas.append({"leitura": lei, "modelo": mod_, "n_base": len(P), "n_sem_agregador": int(sem.sum()),
                           "unidades_sem_agregador": ", ".join(P.index[sem]), "efeito_sem_agregador_pct": pct(coef),
                           "faixa90_lo_pct": pct(np.nanpercentile(bs, 5)), "faixa90_hi_pct": pct(np.nanpercentile(bs, 95)),
                           "reamostras_sem_nenhuma_pct": 100 * float(np.isnan(bs).mean()),
                           "erro_nelas_sem_variavel_pct": 100 * et(e0[sem]), "erro_nelas_com_variavel_pct": 100 * et(e1[sem]),
                           "erro_geral_sem_variavel_pct": 100 * et(e0), "erro_geral_com_variavel_pct": 100 * et(e1),
                           "R2_sem_variavel": r2(y, e0), "R2_com_variavel": r2(y, e1),
                           "regua_conferencia": "atinge" if (cai_sem <= -10 and piora_geral <= .5) else "não atinge"})
            subs = {"sem RJ": P[P.uf != "RJ"], "só maduras": P[P.regra == "madura"], "só jovens/precoces": P[~(sem & (P.regra == "madura").to_numpy())]}
            if mod_ == "faturamento":
                P2 = P.copy(); m_ = sem & (P.regra != "madura").to_numpy(); P2.loc[m_, "Y_tot"] = P2.loc[m_, "Y_tot_pag"]
                subs["faturamento das novas pela curva de pagantes"] = P2
            for nome, D in subs.items():
                rob.append({"leitura": lei, "modelo": mod_, "recorte": nome, "n_sem_agregador": int(D.sem_agregador.sum()),
                            "efeito_sem_agregador_pct": pct(coef_sem(D, cols1, ycol))})
            tira = {u: coef_sem(P.drop(u), cols1, ycol) for u in P.index[sem]}
            for u, c in tira.items():
                rob.append({"leitura": lei, "modelo": mod_, "recorte": f"sem {u}", "n_sem_agregador": int(sem.sum()) - 1, "efeito_sem_agregador_pct": pct(c)})
            rob.append({"leitura": lei, "modelo": mod_, "recorte": "sinal estável tirando cada uma",
                        "n_sem_agregador": int(sem.sum()), "efeito_sem_agregador_pct": np.nan,
                        "resposta": "sim" if all(np.sign(c) == np.sign(coef) for c in tira.values()) else "não"})
            for u, a_, b_ in zip(P.index[sem], e0[sem], e1[sem]):
                det.append({"leitura": lei, "modelo": mod_, "unidade": u, "regra": P.loc[u, "regra"], "uf": P.loc[u, "uf"], "fonte_metragem": P.loc[u, "fonte_m2"],
                            "erro_sem_variavel_pct": pct(a_), "erro_com_variavel_pct": pct(b_)})
            Z = DC.assign(ano2026=1.0, jovem=0.0, precoce=0.0)
            for s_ in (0, 1):
                prev[(lei, mod_, s_)] = pd.Series(X_(Z.assign(sem_agregador=float(s_)), cols1) @ b1, index=DC.index)
    jov = {lei: list(P.index[P.regra != "madura"]) for lei, P in LEIT.items()}
    return pd.DataFrame(linhas), pd.DataFrame(rob), pd.DataFrame(det), fora, prev, jov


# ------------------------------------------------------------------ T4 dois tempos
def grupos_ano(anos):
    """Ano com menos de 3 unidades se junta ao seguinte (o ultimo, ao anterior)."""
    cnt = anos.value_counts().sort_index(); grupos, atual, n = [], [], 0
    for a, c in cnt.items():
        atual.append(a); n += c
        if n >= 3:
            grupos.append(atual); atual, n = [], 0
    if atual:
        (grupos[-1].extend(atual) if grupos else grupos.append(atual))
    return {a: i for i, g_ in enumerate(grupos) for a in g_}


def t4(Bs, tr, te, R_t1):
    f = Bs["f"]
    g = f[f.valido & f.mes_vida.notna()].copy()
    g["tp_incompleto"] = ((g.passagens_totalpass.fillna(0) > 0) | (g.alunos_totalpass.fillna(0) > 0)) & (g.fin_totalpass.fillna(0) <= 0)
    cols = {"faturamento": "faturamento", "balcão": "BAL", "agregador": "AG"}
    fr39 = fac(Bs, tr.index)
    linhas, det = [], []
    for mod_, c in cols.items():
        r = R_t1[(mod_, "masters")]
        p39 = r["y"] - r["loo"] + (np.log(np.where(fr39 > 0, fr39, np.nan)) if mod_ == "agregador" else 0.0)
        prev_v2 = pd.concat([pd.Series(p39, index=tr.index), pd.Series(r["yte"] - r["test"], index=te.index)])
        gg = g if mod_ == "balcão" else g[~g.tp_incompleto]
        rows = []
        for u in list(tr.index) + list(te.index):
            gu, gall = gg[gg.unidade_id == u], g[g.unidade_id == u]
            ab, ma = gu[gu.mes_vida.between(1, 3) & (gu[c] > 0)], gu[gu.mes_vida.between(12, 18) & (gu[c] > 0)]
            if len(ab) >= 2 and len(ma) >= 3 and np.isfinite(prev_v2.get(u, np.nan)):
                a13 = gall[gall.mes_vida.between(1, 3)]
                rows.append({"unidade_id": u, "l_abertura": float(np.log(ab[c]).mean()), "l_maduro": float(np.log(ma[c]).mean()),
                             "ano_maduro": int(ma.competencia.str[:4].astype(int).median()), "prev_v2": float(prev_v2[u]),
                             "agregador_na_abertura_pct": 100 * float((a13.AG > 0).mean()), "conjunto": "39" if u in tr.index else "teste"})
        D = pd.DataFrame(rows).set_index("unidade_id") if rows else pd.DataFrame()
        if len(D) < 10:
            linhas.append({"modelo": mod_, "n": len(D), "checagem": "unidades insuficientes (mínimo 10)"}); continue
        mp = grupos_ano(D.ano_maduro); D["grupo_ano"] = D.ano_maduro.map(mp)
        dum = []
        for k in sorted(set(mp.values()))[1:]:
            D[f"ano_g{k}"] = (D.grupo_ano == k).astype(float); dum.append(f"ano_g{k}")
        y = D.l_maduro.to_numpy(float)
        e0 = y - D.prev_v2.to_numpy(float)
        e1 = loo(D, ["prev_v2"] + dum, y); e2 = loo(D, ["l_abertura"] + dum, y); e3 = loo(D, ["l_abertura", "prev_v2"] + dum, y)
        dd = dif_boot(e3, e1)
        so_com = (D.agregador_na_abertura_pct >= 50).to_numpy()
        Ds = D[so_com]; ys = Ds.l_maduro.to_numpy(float)
        e1s = loo(Ds, ["prev_v2"] + dum, ys); e3s = loo(Ds, ["l_abertura", "prev_v2"] + dum, ys)
        motivos = []
        if 100 * dd[0] > -2:
            motivos.append(queda_txt(100 * dd[0], "no maduro"))
        elif dd[3] > ALFA:
            motivos.append("a queda não se distingue do acaso")
        linhas.append({"modelo": mod_, "n": len(D), "n_abriu_com_agregador_em_menos_da_metade": int((~so_com).sum()),
                       "anos_do_maduro": ", ".join(f"{a}: {int((D.ano_maduro == a).sum())}" for a in sorted(D.ano_maduro.unique())),
                       "grupos_de_ano": " | ".join("+".join(str(a) for a in sorted(k_ for k_, v in mp.items() if v == gi)) for gi in sorted(set(mp.values()))),
                       "erro_v2_como_esta_pct": 100 * et(e0), "erro_v2_ajustada_pct": 100 * et(e1), "erro_so_abertura_pct": 100 * et(e2),
                       "erro_abertura_mais_v2_pct": 100 * et(e3), "dif_pontos": 100 * dd[0], "dif_faixa90_lo": 100 * dd[1], "dif_faixa90_hi": 100 * dd[2], "p": dd[3],
                       "R2_v2_ajustada": r2(y, e1), "R2_so_abertura": r2(y, e2), "R2_abertura_mais_v2": r2(y, e3),
                       "sem_quem_abriu_sem_agregador_dif_pontos": 100 * (et(e3s) - et(e1s)),
                       "checagem": "passa" if not motivos else "não passa", "por_que": "; ".join(motivos)})
        det.append(D.assign(modelo=mod_, erro_v2_como_esta_pct=pct(e0), erro_v2_ajustada_pct=pct(e1), erro_abertura_mais_v2_pct=pct(e3)))
    return pd.DataFrame(linhas), (pd.concat(det) if det else pd.DataFrame())


# ------------------------------------------------------------------ saidas
def f1(x, nd=1):
    return "—" if x is None or pd.isna(x) else f"{x:.{nd}f}%"


def fp_(x, nd=1):
    return "—" if x is None or pd.isna(x) else f"{x:+.{nd}f}"


def graficos(out, T1, T2, T3, T4):
    out.mkdir(parents=True, exist_ok=True)
    cores = {"masters": "#7f7f7f", "R1_fora_DFGO": "#4c72b0", "R2_SP_outras": "#55a868"}
    fig, axs = plt.subplots(1, 4, figsize=(22, 5.5), sharey=True)
    met = [("erro_39_pct", "39 (cada uma\nprevista sem ela)"), ("erro_teste_pct", "teste"), ("erro_regiao_nova_sem_brasilia_pct", "região nova\n(sem Brasília)")]
    for ax, mod_ in zip(axs, TODOS):
        t = T1[T1.modelo == mod_]; x = np.arange(len(met))
        for k, (ver, c_) in enumerate(cores.items()):
            v = [t[t.versao == ver][m].iloc[0] for m, _ in met]
            ax.bar(x + (k - 1) * .27, v, .27, color=c_, label=VERS[ver])
            for xi, vv in zip(x + (k - 1) * .27, v):
                ax.text(xi, vv + .5, f"{vv:.0f}", ha="center", fontsize=6.5)
        r0 = t[t.versao == "masters"].iloc[0]
        ax.set_xticks(x); ax.set_xticklabels([r for _, r in met]); ax.set_title(f"{mod_}\n(n {r0.n_39} / teste {r0.n_teste}; R² 39 hoje {r0.R2_39:.2f})")
    axs[0].set_ylabel("erro típico (%) — menor = melhor"); axs[0].legend(fontsize=7)
    fig.suptitle("T1 — região no lugar das masters, nos três modelos e no total", y=1.03)
    fig.tight_layout(); fig.savefig(out / "01_regiao_no_lugar_da_master.png", bbox_inches="tight"); plt.close(fig)
    fig, axs = plt.subplots(1, 4, figsize=(22, 5.5), sharey=True)
    for ax, mod_ in zip(axs, TODOS):
        t = T2[T2.modelo == mod_].reset_index(drop=True); x = np.arange(len(t))
        ax.bar(x - .2, t["erro_57_treino_39_pct"], .4, color="#bbbbbb", label="treino de 39")
        ax.bar(x + .2, t["erro_57_ampliado_pct"], .4, color="#4c72b0", label="treino ampliado")
        for i, r_ in t.iterrows():
            ax.text(i - .2, r_["erro_57_treino_39_pct"] + .5, f"{r_['erro_57_treino_39_pct']:.0f}", ha="center", fontsize=7)
            ax.text(i + .2, r_["erro_57_ampliado_pct"] + .5, f"{r_['erro_57_ampliado_pct']:.0f}", ha="center", fontsize=7)
        ax.set_xticks(x); ax.set_xticklabels([VERS[v].split(":")[0] for v in t.versao], fontsize=7)
        ax.set_title(f"{mod_}\n(n comparação {int(t.n_comparacao.iloc[0])}; treino ampliado {int(t.n_treino_ampliado.iloc[0])})")
    axs[0].set_ylabel("erro típico nas mesmas unidades (%)"); axs[0].legend(fontsize=7)
    fig.suptitle("T2 — treino ampliado: erro de cada unidade prevista sem ela, nas mesmas 57 unidades", y=1.03)
    fig.tight_layout(); fig.savefig(out / "02_treino_ampliado.png", bbox_inches="tight"); plt.close(fig)
    fig, axs = plt.subplots(2, 2, figsize=(14, 9))
    for row, lei in enumerate(("sem_precoces", "com_precoces")):
        t = T3[T3.leitura == lei].reset_index(drop=True); x = np.arange(len(t))
        for col, (a, b, rot) in enumerate((("erro_nelas_sem_variavel_pct", "erro_nelas_com_variavel_pct", "erro nas sem agregador"),
                                           ("erro_geral_sem_variavel_pct", "erro_geral_com_variavel_pct", "erro geral"))):
            ax = axs[row, col]
            ax.bar(x - .2, t[a], .4, color="#bbbbbb", label="sem a variável"); ax.bar(x + .2, t[b], .4, color="#c44e52", label="com 'abre sem agregador'")
            ax.set_xticks(x); ax.set_xticklabels(t.modelo); ax.set_ylabel(f"{rot} (%)")
            ax.set_title(f"{'sem' if lei == 'sem_precoces' else 'com'} precoces — {rot} (n = {int(t.n_sem_agregador.iloc[0])} sem agregador, já vistas)")
            ax.legend(fontsize=7)
    fig.suptitle("T3 — conferência interna (não é teste): quem julga são as 5 cegas em 2027", y=1.01)
    fig.tight_layout(); fig.savefig(out / "03_sem_agregador.png", bbox_inches="tight"); plt.close(fig)
    t4 = T4[T4["erro_v2_ajustada_pct"].notna()].reset_index(drop=True) if "erro_v2_ajustada_pct" in T4 else T4.iloc[0:0]
    fig, ax = plt.subplots(figsize=(11, 5)); x = np.arange(len(t4))
    for k, (c, rot, cc) in enumerate((("erro_v2_como_esta_pct", "v2 como está", "#dddddd"), ("erro_v2_ajustada_pct", "v2 ajustada ao maduro (régua)", "#999999"),
                                      ("erro_so_abertura_pct", "só os meses 1–3", "#dd8452"), ("erro_abertura_mais_v2_pct", "meses 1–3 + v2", "#4c72b0"))):
        ax.bar(x + (k - 1.5) * .2, t4[c], .2, color=cc, label=rot)
    ax.set_xticks(x); ax.set_xticklabels([f"{m}\n(n {n})" for m, n in zip(t4.modelo, t4.n)]); ax.legend(fontsize=7); ax.set_ylabel("erro típico do nível maduro (%)")
    ax.set_title("T4 — dois tempos (só depois de abrir). Medido em unidades que abriram COM agregador")
    fig.tight_layout(); fig.savefig(out / "04_dois_tempos.png", bbox_inches="tight"); plt.close(fig)


def escrever(destino, ensaio, T1, EF, QM, T2, RN, ANO, FX, DESC, T3, ROB, T3d, FORA, T4, jov, Bs):
    st = lambda T, m, v, c: T[(T.modelo == m) & (T.versao == v)][c].iloc[0]
    passam = lambda T: [f"{r.modelo} ({VERS[r.versao].split(':')[0]})" for _, r in T.iterrows() if r.get("checagem") == "passa"]
    L = [f"# BLK-UNI-15 — melhorias nos três modelos{' (ENSAIO COM RUÍDO — NÃO INTERPRETAR)' if ensaio else ''}", "",
         f"Protocolo `protocolo_uni15.md` v1.1. Rodado em {datetime.now():%Y-%m-%d %H:%M}.", "",
         "## Como ler", "",
         "- **Três modelos + total:** faturamento (o total direto); balcão (vendas na unidade, sem Tem Saúde); agregador (Wellhub + TotalPass); "
         "total recombinado (balcão + agregador somados, com o ajuste de nível do UNI-09).",
         "- **Erro típico:** quanto a previsão erra numa unidade comum (metade das unidades erra menos que isso). 22% = a unidade típica fatura 22% "
         "a mais ou a menos que o previsto. Menor = melhor.",
         "- **Cada unidade prevista sem ela:** o modelo é refeito sem a unidade e depois prevê ela. É o erro \"fora da amostra\".",
         "- **Diferença (pontos):** erro do novo − erro de hoje. Negativa = o novo erra menos.",
         "- **Faixa provável (90%):** 9 em 10 reamostragens das unidades caem dentro. Se cruza o zero, não dá para separar do acaso. "
         "90% e não 95% porque a pergunta é de um lado só (\"o novo erra menos?\").",
         "- **R²:** quanto da diferença entre unidades o modelo acerta, fora da amostra. 1 = tudo; 0 = igual a chutar a média; negativo = pior que a média.",
         "- **Região nova:** o modelo é refeito sem toda a região metropolitana da unidade (como numa praça onde a rede nunca esteve). "
         "\"Sem Brasília\" tira essa dobra: sem Brasília, o grupo DF/GO fica com 1 unidade e a conta deixa de testar praça nova.",
         "- **Checagem do estudo:** cada teste tem a sua régua, escrita na seção. \"Passa\" não é adoção.", "",
         "## Avisos", "",
         "- Todas as unidades usadas aqui já foram vistas em análises anteriores (UNI-02 a UNI-14). Isto é estimação e conferência; "
         "o juiz de verdade é a turma de 2026, conferida em 2027.",
         "- **Nada é adotado sem o Felipe.**",
         "- O 4º item pedido (preço, estúdio e tier com data) está no BLK-UNI-16: depende da coleta de vendas da Growth, que parou em set/2023 por "
         "limite de chamadas da API e retoma depois.", ""]
    # ---- resposta curta
    s1 = "; ".join(f"{m} R1 {fp_(st(T1, m, 'R1_fora_DFGO', 'dif_39_pontos'))} / R2 {fp_(st(T1, m, 'R2_SP_outras', 'dif_39_pontos'))}" for m in TODOS)
    s2 = "; ".join(f"{m} {fp_(st(T2, m, 'masters', 'dif_pontos'))}" for m in TODOS)
    t3s = T3[T3.leitura == "sem_precoces"]; t3c = T3[T3.leitura == "com_precoces"]
    s3 = lambda t: "; ".join(f"{r.modelo} {r.efeito_sem_agregador_pct:+.0f}% (faixa {r.faixa90_lo_pct:+.0f}% a {r.faixa90_hi_pct:+.0f}%), erro nelas "
                             f"{f1(r.erro_nelas_sem_variavel_pct, 0)} → {f1(r.erro_nelas_com_variavel_pct, 0)}" for _, r in t.iterrows())
    t4ok = T4[T4.get("erro_v2_ajustada_pct", pd.Series(dtype=float)).notna()] if "erro_v2_ajustada_pct" in T4 else T4.iloc[0:0]
    s4 = "; ".join(f"{r.modelo} {f1(r.erro_v2_ajustada_pct, 0)} → {f1(r.erro_abertura_mais_v2_pct, 0)} (n {r.n})" for _, r in t4ok.iterrows())
    L += ["## Resposta curta", "",
          f"- **T1 — região no lugar das masters.** Diferença no erro das 39 (novo − hoje, pontos): {s1}. "
          f"Passam na checagem: {', '.join(passam(T1)) or 'nenhuma'}.",
          f"- **T2 — treino ampliado (~60 unidades).** Diferença nas mesmas 57 (com masters, pontos): {s2}. Passam na checagem: {', '.join(passam(T2)) or 'nenhuma'}.",
          f"- **T3 — abrir sem agregador (conferência, não é teste).** Sem precoces ({int(t3s.n_sem_agregador.iloc[0])} unidades): {s3(t3s)}. "
          f"Com precoces ({int(t3c.n_sem_agregador.iloc[0])} unidades): {s3(t3c)}.",
          f"- **T4 — previsão em dois tempos (só depois de abrir).** Erro do nível maduro, v2 ajustada → meses 1–3 + v2: {s4}. "
          f"Passam na checagem: {', '.join(r.modelo for _, r in T4.iterrows() if r.get('checagem') == 'passa') or 'nenhum'}. "
          "Medido em unidades que abriram COM agregador: não vale ainda para quem abre sem.", ""]
    # ---- T1
    L += ["## T1 — região no lugar das masters (treino 39, teste 18)", "",
          "**O que é:** R1 junta numa só as masters de fora do DF/GO; R2 troca as masters por região (DF/GO, SP ou outras UFs). "
          "Como a master M1 é exatamente o DF/GO, **o teste diz se precisamos de tantas masters, não se região explica melhor que master**.", "",
          "**Régua (passa):** o erro das 39 cai ≥ 2 pontos e a queda se distingue do acaso (Holm, 2 versões por modelo, 5% de um lado), "
          "**e** o erro do teste cai ≥ 2 pontos, com e sem o nível do ano. \"Região nova não piora\" é mostrada, não decide.", "",
          "| modelo | versão | n (39 / teste) | R² 39 | erro 39 | R² teste | erro teste | região nova sem Brasília | diferença nas 39 (faixa 90%) | diferença no teste | checagem | por que |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in T1.iterrows():
        hoje = r.versao == "masters"
        L.append(f"| {r.modelo} | {VERS[r.versao]} | {r.n_39} / {r.n_teste} | {r.R2_39:.2f} | {f1(r.erro_39_pct)} | {r.R2_teste:.2f} | {f1(r.erro_teste_pct)} | "
                 f"{f1(r.erro_regiao_nova_sem_brasilia_pct)} | {'' if hoje else f'{fp_(r.dif_39_pontos)} ({fp_(r.dif_39_faixa90_lo)} a {fp_(r.dif_39_faixa90_hi)})'} | "
                 f"{'' if hoje else fp_(r.dif_teste_pontos)} | {'hoje' if hoje else r.checagem} | {'' if hoje else r.por_que} |")
    L += ["", "R² do agregador: nas 39 é no alvo \"como se aceitasse os dois apps\"; no teste, no valor real (o erro é o mesmo nos dois).", "",
          "**Efeito de cada grupo contra o DF/GO** (faixa 90%; faturamento, balcão e agregador pelo coeficiente com faixa robusta; o total pela média nas 39 com reamostragem):", "",
          "| modelo | versão | grupo | efeito | faixa 90% | unidades do treino no grupo |", "|---|---|---|---|---|---|"]
    for _, r in EF.iterrows():
        L.append(f"| {r.modelo} | {VERS[r.versao].split(':')[0]} | {r.grupo} | {r.efeito_contra_DFGO_pct:+.0f}% | {r.faixa90_lo_pct:+.0f}% a {r.faixa90_hi_pct:+.0f}% | {r.n_treino_no_grupo} |")
    qm = QM[QM.aprende_com_outras_unidades == "sim"]
    L += ["", f"**Quem passa a aprender com outras unidades na R2** ({len(qm)} de {len(QM)} no teste e nas cegas):", "",
          "| unidade | conjunto | UF | master | grupo hoje (treino) | grupo R2 (treino) |", "|---|---|---|---|---|---|"] + [
        f"| {r.unidade} | {r.conjunto} | {r.uf} | {r.master} | {r.grupo_hoje} ({r.treino_no_grupo_hoje}) | {r.grupo_R2} ({r.treino_no_grupo_R2}) |" for _, r in qm.iterrows()]
    L += ["", "**Dá para concluir:** se juntar masters ou trocar por região muda o erro nestas unidades. **Não dá:** que região explica melhor que master "
          "(DF/GO = M1), nem como fica numa praça com master nova.", ""]
    # ---- T2
    L += ["## T2 — treino ampliado (39 + 18 + 3 maduras da turma B, com ajuste de nível de 2026)", "",
          "**Comparação justa:** as mesmas 57 unidades, sempre previstas sem elas. Treino de 39 = cada uma das 39 prevista sem ela + as 18 do teste. "
          "Treino ampliado = cada uma das 57 prevista sem ela, com as outras ~59. O total recombinado é refeito em cada rodada (com o seu ajuste de nível).", "",
          "**Régua (passa):** o erro nas 57 cai ≥ 2 pontos e a queda se distingue do acaso (Holm, 3 versões por modelo, 5% de um lado). "
          "A conta sem o nível de cada ano é leitura: se o ganho sumir nela, o texto avisa.", "",
          "| modelo | versão | n treino | erro 57 (treino 39) | erro 57 (ampliado) | diferença (faixa 90%) | sem o nível do ano | só 39 | só 18 | R² 57 (39 → ampliado) | checagem | por que |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in T2.iterrows():
        L.append(f"| {r.modelo} | {VERS[r.versao].split(':')[0]} | {r.n_treino_ampliado} | {f1(r.erro_57_treino_39_pct)} | {f1(r.erro_57_ampliado_pct)} | "
                 f"{fp_(r.dif_pontos)} ({fp_(r.dif_faixa90_lo)} a {fp_(r.dif_faixa90_hi)}) | {fp_(r.dif_recentrado_por_ano_pontos)} | "
                 f"{f1(r.erro_39_treino_39_pct, 0)} → {f1(r.erro_39_ampliado_pct, 0)} | {f1(r.erro_18_treino_39_pct, 0)} → {f1(r.erro_18_ampliado_pct, 0)} | "
                 f"{r.R2_57_treino_39:.2f} → {r.R2_57_ampliado:.2f} | {r.checagem} | {r.por_que}{(' — ' + r.aviso_recentrado) if r.aviso_recentrado else ''} |")
    L += ["", "**Região nova, nas mesmas 39 unidades** (erro típico; treino 39 → ampliado):", "",
          "| modelo | versão | todas as regiões | sem Brasília |", "|---|---|---|---|"] + [
        f"| {r.modelo} | {VERS[r.versao].split(':')[0]} | {f1(r.regiao_nova_39_treino_39_pct, 0)} → {f1(r.regiao_nova_39_ampliado_pct, 0)} | "
        f"{f1(r.regiao_nova_39_sem_brasilia_treino_39_pct, 0)} → {f1(r.regiao_nova_39_sem_brasilia_ampliado_pct, 0)} |" for _, r in RN.iterrows()]
    L += ["", "**Ajuste de nível de 2026** (coeficiente do treino ampliado × calibração de calendário usada no treino de 39). "
          "Esse ajuste mistura ano, unidades mais novas e a janela jan–ago, não é só \"ano\":", "",
          "| modelo | versão | ajuste no ampliado (faixa 90%) | calibração de calendário |", "|---|---|---|---|"] + [
        f"| {r.modelo} | {VERS[r.versao].split(':')[0]} | {r.ajuste_2026_dummy_pct:+.1f}% ({r.faixa90_lo_pct:+.1f}% a {r.faixa90_hi_pct:+.1f}%) | {r.calibracao_calendario_pct:+.1f}% |"
        for _, r in ANO.iterrows()]
    fx = FX[FX.versao == "masters"]
    L += ["", "**Faixa dos coeficientes principais (com masters; largura da faixa robusta de 90%, em log):**", "",
          "| modelo | variável | treino 39 | ampliado | ampliado ÷ 39 |", "|---|---|---|---|---|"] + [
        f"| {r.modelo} | {r.variavel} | {r.largura_faixa90_39:.2f} | {r.largura_faixa90_ampliado:.2f} | {r.razao_largura_ampliado_sobre_39:.2f} |" for _, r in fx.iterrows()]
    L += ["", "**Leitura descritiva — Botafogo e Bangu** (RJ, master M3, sem agregador) entram no ampliado. O que isso faz com o grupo delas "
          "e com as duas cegas do RJ (previsão em R$ mil/mês, 2026, sem agregador = 0):", "",
          "| modelo | versão | variante | efeito do grupo | Belford Roxo | Bonsucesso |", "|---|---|---|---|---|---|"]
    for _, r in DESC.iterrows():
        ef = "; ".join(f"{k.replace('efeito_', '').replace('_pct', '').replace('_', ' ')} {v:+.0f}%" for k, v in r.items() if k.startswith("efeito_") and pd.notna(v))
        L.append(f"| {r.modelo} | {VERS[r.versao].split(':')[0]} | {r.variante} | {ef} | {r['prev_belford-roxo-rj_mil_reais']:.0f} | {r['prev_bonsucesso-rj_mil_reais']:.0f} |")
    L += ["", "**Dá para concluir:** se mais unidades no treino reduzem o erro nestas mesmas unidades. **Não dá:** separar o efeito de ter mais unidades "
          "do de acertar o nível de 2026, porque o ajuste de 2026 é aprendido com o próprio grupo avaliado.", ""]
    # ---- T3
    L += ["## T3 — abrir sem agregador (faturamento e balcão)", "",
          "**Conferência interna (não é teste): quem julga são as 5 cegas em 2027.** Todas as unidades sem agregador daqui já foram vistas.", "",
          "**O que é:** a variável \"abre sem agregador\" (agregador em menos da metade dos meses) entra no modelo de faturamento e no de balcão. "
          "A base é a ampliada do T2 mais as unidades novas, levadas ao nível maduro pela curva de rampa do UNI-03 (faturamento pela curva de faturamento; "
          "balcão pela de pagantes, porque não há curva de receita de balcão). Duas leituras: sem as precoces (como no plano) e com elas (aviso: dizem pouco "
          "sobre o nível maduro). O total não entra: nas unidades sem agregador o faturamento já é o total, e o modelo de agregador não existe para elas.", "",
          "**Régua de conferência (do plano):** o erro nelas cai ≥ 10 pontos e o erro geral não piora mais que 0,5 ponto. Difere do plano em dois pontos: "
          "o plano lia esse grupo na turma B + turma 2026 e pedia a faixa do efeito; aqui é a base inteira, com a faixa por reamostragem.", "",
          "**Atenção:** os efeitos de faturamento e de balcão não se comparam diretamente: as unidades novas foram levadas ao maduro por curvas diferentes "
          "(a de faturamento carrega a rampa do agregador e tende a inflar as sem agregador).", "",
          "| leitura | modelo | n base | sem agregador | efeito (faixa 90%) | erro nelas (sem → com) | erro geral (sem → com) | R² (sem → com) | régua de conferência |",
          "|---|---|---|---|---|---|---|---|---|"]
    for _, r in T3.iterrows():
        L.append(f"| {r.leitura.replace('_', ' ')} | {r.modelo} | {r.n_base} | {r.n_sem_agregador} | {r.efeito_sem_agregador_pct:+.0f}% ({r.faixa90_lo_pct:+.0f}% a {r.faixa90_hi_pct:+.0f}%) | "
                 f"{f1(r.erro_nelas_sem_variavel_pct, 0)} → {f1(r.erro_nelas_com_variavel_pct, 0)} | {f1(r.erro_geral_sem_variavel_pct, 1)} → {f1(r.erro_geral_com_variavel_pct, 1)} | "
                 f"{r.R2_sem_variavel:.2f} → {r.R2_com_variavel:.2f} | {r.regua_conferencia} |")
    L += ["", "**Cada unidade sem agregador** (erro = real ÷ previsto − 1, cada uma prevista sem ela):", "",
          "| leitura | modelo | unidade | idade | UF | metragem | sem a variável | com a variável |", "|---|---|---|---|---|---|---|---|"] + [
        f"| {r.leitura.replace('_', ' ')} | {r.modelo} | {r.unidade} | {r.regra} | {r.uf} | {r.fonte_metragem} | {r.erro_sem_variavel_pct:+.0f}% | {r.erro_com_variavel_pct:+.0f}% |"
        for _, r in T3d.iterrows()]
    L += ["", "**Robustez do efeito** (a mesma conta em recortes):", "", "| leitura | modelo | recorte | sem agregador (n) | efeito |", "|---|---|---|---|---|"] + [
        f"| {r.leitura.replace('_', ' ')} | {r.modelo} | {r.recorte} | {r.n_sem_agregador} | "
        f"{(r.resposta if isinstance(r.get('resposta'), str) else (f'{r.efeito_sem_agregador_pct:+.0f}%' if pd.notna(r.efeito_sem_agregador_pct) else '—'))} |"
        for _, r in ROB.iterrows()]
    L += ["", "**Paralelo com o UNI-14:** lá a mesma pergunta foi medida sem reajustar o modelo (erro mediano das sem agregador − o das que aceitam os dois apps) "
          "e deu +35% no faturamento (v2) e +115% no total das duas partes. Aqui é o coeficiente de uma variável dentro do modelo, em outra base: os números não "
          "precisam bater, só o sentido.", "",
          f"Unidades novas usadas — sem precoces: {', '.join(jov['sem_precoces']) or 'nenhuma'}; com precoces: {', '.join(jov['com_precoces']) or 'nenhuma'}.", "",
          "**Fora da conta (com o motivo):**", "", "| unidade | motivo |", "|---|---|"] + [f"| {r.unidade} | {r.motivo} |" for _, r in FORA.iterrows()]
    L += ["", "**Dá para ver** o tamanho da diferença nesta base. **Não dá para concluir** que melhora a previsão de unidade nova.", ""]
    # ---- T4
    L += ["## T4 — previsão em dois tempos (só depois de abrir: alerta do mês 3)", "",
          "**Aviso:** medido em unidades que abriram **COM** agregador. Não vale ainda para quem abre sem agregador (as turmas de 2026).", "",
          "**O que é:** prever o nível maduro (média dos meses 12–18 de vida) usando os meses 1–3 junto com a v2. Faturamento e agregador não usam meses "
          "com alunos de TotalPass sem a receita de TotalPass no Financeiro (a linha só existe a partir de out/2023). Em todos entra o ajuste do ano em que "
          "a unidade amadureceu (ano com menos de 3 unidades se junta ao seguinte).", "",
          "**Régua (passa):** \"meses 1–3 + v2\" cai ≥ 2 pontos contra \"v2 ajustada ao maduro\" e a queda se distingue do acaso (5% de um lado; 1 comparação por modelo). "
          "\"v2 como está\" é o erro direto da previsão de aprovação, sem nenhum ajuste (inclui a diferença de ano e de janela).", "",
          "| modelo | n | v2 como está | v2 ajustada (régua) | só meses 1–3 | meses 1–3 + v2 | diferença (faixa 90%) | R² (ajustada → 1–3 + v2) | sem quem abriu sem agregador | checagem |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in T4.iterrows():
        if pd.isna(r.get("erro_v2_ajustada_pct")):
            L.append(f"| {r.modelo} | {r.n} | — | — | — | — | — | — | — | {r.checagem} |"); continue
        L.append(f"| {r.modelo} | {r.n} | {f1(r.erro_v2_como_esta_pct)} | {f1(r.erro_v2_ajustada_pct)} | {f1(r.erro_so_abertura_pct)} | {f1(r.erro_abertura_mais_v2_pct)} | "
                 f"{fp_(r.dif_pontos)} ({fp_(r.dif_faixa90_lo)} a {fp_(r.dif_faixa90_hi)}) | {r.R2_v2_ajustada:.2f} → {r.R2_abertura_mais_v2:.2f} | "
                 f"{fp_(r.sem_quem_abriu_sem_agregador_dif_pontos)} (tira {r.n_abriu_com_agregador_em_menos_da_metade}) | {r.checagem}{(' — ' + r.por_que) if r.por_que else ''} |")
    L += ["", "Anos do maduro: " + " · ".join(f"{r.modelo}: {r.anos_do_maduro} (grupos {r.grupos_de_ano})" for _, r in T4.iterrows() if isinstance(r.get("anos_do_maduro"), str)) + ".",
          "O ajuste de 2026 coincide com as 18 do teste (todas amadurecem em 2026). A previsão da v2 das 39 vem de modelos que viram o desfecho de 2025 "
          "das outras unidades (vazamento pequeno, declarado). O total não entra: a linha de faturamento já é o total observado.", "",
          "**Dá para concluir:** se os meses 1–3 melhoram a leitura do maduro em quem abriu com agregador. **Não dá:** usar isso no alerta do mês 3 de "
          "quem abre sem agregador.", ""]
    destino.write_text("\n".join(L) + "\n", encoding="utf-8")
    return "\n".join(L)


def dicionario():
    return pd.DataFrame([
        ("erro_*_pct", "erro típico (mediana de |real ÷ previsto − 1|), em %"), ("dif_*_pontos", "erro do novo − erro de hoje, em pontos (negativo = novo erra menos)"),
        ("*_faixa90_lo / _hi", "faixa provável de 90% (reamostragem pareada das unidades)"), ("p, p_39", "fração das reamostragens em que o novo NÃO erra menos"),
        ("holm_ok", "a queda se distingue do acaso depois da correção por várias versões (Holm)"), ("R2_*", "R² fora da amostra"),
        ("regiao_nova_*", "erro com toda a região metropolitana da unidade fora do treino"), ("*_recentrado*", "sem o nível de cada ano (tira a mediana do erro de cada ano)"),
        ("masters / R1_fora_DFGO / R2_SP_outras", "versões: com masters (hoje) / masters de fora do DF/GO juntas / região DF/GO, SP ou outras"),
        ("log_*", "previsão em log de R$/mês (exp = R$)"), ("agregador_ambos_sem_k", "agregador \"como se aceitasse os dois apps\", sem o ajuste k nem o fator"),
        ("fator_cadastro", "fator de aceite do cadastro (1 = os dois apps; 1 − s_tp = só Wellhub; s_tp = só TotalPass; 0 = nenhum)"),
        ("k", "ajuste de nível do total recombinado (UNI-09)"), ("total = ", "log(exp(balcao_sem_k) + fator_cadastro × exp(agregador_ambos_sem_k)) + k"),
    ], columns=["coluna", "significado"])


def main():
    modo = [m for m in ("--seca", "--ensaio", "--registrar", "--rodar") if m in sys.argv]
    if len(modo) != 1:
        sys.exit("use exatamente um modo")
    modo = modo[0]
    if modo == "--registrar":
        if REG_PRE.exists():
            sys.exit("RECUSADO: REGISTRO_PRE ja existe")
        txt = [f"REGISTRO PRE-RODADA BLK-UNI-15 (protocolo v1.1) — {datetime.now():%Y-%m-%d %H:%M}"] + [f"{k}: {Path(p).name}  SHA-256 {sha(p)}" for k, p in insumos().items()]
        REG_PRE.write_text("\n".join(txt) + "\n", encoding="utf-8"); print("SHA REGISTRO_PRE:", sha(REG_PRE)); return
    if modo == "--rodar":
        if PREV.exists() or RES.exists() or REG_POS.exists():
            sys.exit("RECUSADO: rodada real ja aconteceu")
        linhas = REG_PRE.read_text(encoding="utf-8").splitlines()
        for k, p in insumos().items():
            reg = next(l_ for l_ in linhas if l_.startswith(f"{k}:")).split("SHA-256 ")[1].strip()
            assert sha(p) == reg, f"{k} mudou depois do REGISTRO_PRE"
    u14 = mod("u14", UNI / "uni14" / "01_validacao_ampliada.py")
    Bs = u14.base(); Bs["u14"] = u14
    tr, te, tb, m2, fonte = montar_bases(Bs)
    TV = pd.read_csv(UNI / "previsao_2026" / "previsoes_turma_2026_v2_domiciliar.csv", sep=";", encoding="utf-8-sig", index_col=0)
    turma_ok = list(TV.index[TV.prev_v2dom_cal2026.notna()])
    DT = u14.montar(Bs, turma_ok, m2); regioes(DT, Bs["d"])
    DC = DT.loc[[u for u in CEGAS if u in DT.index]]
    if modo == "--seca":
        P = pd.concat([tr, te, tb]); fp = fac(Bs, P.index)
        print("T2 n por modelo:", {m: int(np.isfinite(y).sum()) for m, y in alvos(P, fp).items()}, "| sem Y_A:", list(P.index[P.Y_A.isna()]))
        print("fator do cadastro de quem não tem agregador:", {u: float(fp[list(P.index).index(u)]) for u in P.index[P.Y_A.isna()]})
        print("sem agregador (tr/te/tb):", list(P.index[P.sem_agregador == 1]), "| cegas com covariáveis:", list(DC.index))
        print("contagem treino por região:", tr.uf.map(lambda x: "DF/GO" if x in ("DF", "GO") else ("SP" if x == "SP" else "outras")).value_counts().to_dict())
        J, fora = candidatos(Bs, list(tr.index) + list(te.index) + list(tb.index) + CEGAS, m2, fonte)
        print("candidatos T3:\n", J[["regra", "n_meses", "mv_min", "mv_max", "sem_agregador", "fonte_m2"]].to_string())
        print("fora da conta T3:\n", fora.to_string())
        f = Bs["f"]; g = f[f.valido & f.mes_vida.notna()].copy()
        g["tp_inc"] = ((g.passagens_totalpass.fillna(0) > 0) | (g.alunos_totalpass.fillna(0) > 0)) & (g.fin_totalpass.fillna(0) <= 0)
        for mod_, c in (("faturamento", "faturamento"), ("balcão", "BAL"), ("agregador", "AG")):
            gg = g if mod_ == "balcão" else g[~g.tp_inc]
            n = [u for u in list(tr.index) + list(te.index) if (len(gg[(gg.unidade_id == u) & gg.mes_vida.between(1, 3) & (gg[c] > 0)]) >= 2
                                                                and len(gg[(gg.unidade_id == u) & gg.mes_vida.between(12, 18) & (gg[c] > 0)]) >= 3)]
            print(f"T4 {mod_}: n {len(n)}")
        return
    if modo == "--ensaio":
        rz = np.random.default_rng(9)
        for D in (tr, te, tb):
            ya = D.Y_A.notna().to_numpy()
            D["Y_B"] = rz.normal(11.8, .3, len(D)); D["Y_A"] = np.where(ya, D.Y_B - 1.1 + rz.normal(0, .3, len(D)), np.nan)
            D["Y_tot"] = np.log(np.exp(D.Y_B) + np.nan_to_num(np.exp(D.Y_A)))
        f = Bs["f"].copy()
        for c in ("faturamento", "BAL", "AG", "fin_totalpass"):          # ruido puro so' onde ha valor > 0: zeros e ausencias preservados
            v = f[c].to_numpy(float)
            f[c] = np.where(v > 0, 1e5 * np.exp(rz.normal(0, .3, len(f))), v)
        Bs["f"] = f
        dest = outd = ENSAIO; dest.mkdir(parents=True, exist_ok=True)
    else:
        dest, outd = AQUI, OUT
    T1, R_t1, EF = t1(Bs, tr, te)
    QM = quem_muda(Bs, tr, te, DC)
    if modo == "--rodar":
        g = lambda m, v, c: float(T1[(T1.modelo == m) & (T1.versao == v)][c].iloc[0])
        assert abs(g("faturamento", "masters", "erro_39_pct") - 23.5) < .1 and abs(g("faturamento", "masters", "erro_teste_pct") - 22.1) < .1
        assert abs(g("balcão", "masters", "R2_39") - .412) < .002 and abs(g("total recombinado", "masters", "erro_teste_pct") - 22.9) < .1
    T2, RN, ANO, FX, DESC, P2 = t2(Bs, tr, te, tb, R_t1, DT, DC)
    T3, ROB, T3d, FORA, P3, jov = t3(Bs, tr, te, tb, m2, fonte, DC)
    T4, T4d = t4(Bs, tr, te, R_t1)
    print("n:", {"T2": T2.groupby("modelo").n_treino_ampliado.first().to_dict(), "T3": T3.groupby("leitura").n_sem_agregador.first().to_dict(),
                 "T4": dict(zip(T4.modelo, T4.n)), "jovens": jov}, flush=True)
    if modo == "--rodar":
        assert T2[T2.versao == "masters"].set_index("modelo").n_treino_ampliado.reindex(list(TRAVA_T2_N)).to_dict() == TRAVA_T2_N, T2
        assert set(T3[(T3.leitura == "sem_precoces")].unidades_sem_agregador.iloc[0].split(", ")) == TRAVA_T3_SEM_AG["sem_precoces"]
        assert TRAVA_T4_N is not None and dict(zip(T4.modelo, T4.n)) == TRAVA_T4_N, T4
    PT = pd.DataFrame(index=DT.index)
    for (m, v), s in P2.items():
        nome = {"faturamento": "log_fat", "balcão": "log_balcao", "agregador": "log_agregador_ambos_sem_fator", "balcão_sem_k": "log_balcao_sem_k",
                "agregador_ambos_sem_k": "log_agregador_ambos_sem_k", "k": "k", "total recombinado": "log_total"}[m]
        PT[f"{nome}_{v}_T2_ampliado_2026"] = s
    for (lei, m, s_), s in P3.items():
        PT[f"log_{'fat' if m == 'faturamento' else 'balcao'}_T3_{lei}_sem_agregador_{s_}_2026"] = s.reindex(PT.index)
    PT["fator_cadastro"] = fac(Bs, PT.index); PT["s_tp"] = Bs["s_tp"]
    graficos(outd, T1, T2, T3, T4)
    with pd.ExcelWriter(outd / "melhorias_tres_modelos.xlsx") as w:
        pd.DataFrame({"campo": ["O que é", "Como ler", "T1", "T2", "T3", "T4", "Aviso", "Gerado por"], "descrição": [
            "BLK-UNI-15: melhorias pedidas pelo Felipe em 06/10, sempre nos três modelos (faturamento, balcão, agregador) e no total recombinado onde cabe.",
            "Erro típico = quanto a previsão erra numa unidade comum (menor = melhor). Diferença em pontos: negativa = o novo erra menos. Faixa provável de 90%.",
            "Masters de fora do DF/GO juntas (R1) ou região DF/GO, SP ou outras UFs (R2) no lugar das masters. Como M1 = DF/GO, diz se precisamos de tantas masters.",
            "Treino ampliado: 39 + 18 + 3 maduras da turma B, com ajuste de nível de 2026. Comparação nas mesmas 57 unidades, sempre previstas sem elas.",
            "Variável 'abre sem agregador' no faturamento e no balcão. Conferência interna (não é teste): quem julga são as 5 cegas em 2027.",
            "Nível maduro previsto com os meses 1–3 (+ v2): só depois de abrir. Medido em quem abriu COM agregador.",
            "Todas as unidades já foram vistas. Nada adotado sem o Felipe.", "data/analysis/uni/uni15/01_melhorias.py (protocolo v1.1)"]}).to_excel(w, sheet_name="LEIA-ME", index=False)
        pd.DataFrame({"ressalva": [
            "Todas as unidades já foram vistas em análises anteriores: estimação e conferência, não teste cego.",
            "M1 = DF/GO: região e master se confundem no DF/GO.",
            "R² do agregador nas 39 é no alvo 'como se aceitasse os dois apps'; no teste, no valor real.",
            "No T2 o ajuste de 2026 é aprendido com o próprio grupo avaliado e mistura ano, coorte e janela.",
            "No T3 as unidades novas foram levadas ao maduro por curvas de rampa de unidades que abriram com agregador; faturamento e balcão usam curvas diferentes.",
            "No T3, 4 das 5 sem agregador têm metragem aproximada (time ou satélite).",
            "O T4 foi medido em quem abriu com agregador; não vale ainda para quem abre sem.",
            "Faixas de 90% porque as perguntas são de um lado só ('o novo erra menos?')."]}).to_excel(w, sheet_name="RESSALVAS", index=False)
        dicionario().to_excel(w, sheet_name="DICIONARIO", index=False)
        T1.to_excel(w, sheet_name="T1_erros", index=False); EF.to_excel(w, sheet_name="T1_efeito_grupo", index=False); QM.to_excel(w, sheet_name="T1_quem_muda", index=False)
        T2.to_excel(w, sheet_name="T2_erros_57", index=False); RN.to_excel(w, sheet_name="T2_regiao_nova_39", index=False)
        ANO.to_excel(w, sheet_name="T2_ajuste_2026", index=False); FX.to_excel(w, sheet_name="T2_faixas_coef", index=False)
        DESC.to_excel(w, sheet_name="T2_botafogo_bangu", index=False)
        T3.to_excel(w, sheet_name="T3_resumo", index=False); ROB.to_excel(w, sheet_name="T3_robustez", index=False)
        T3d.to_excel(w, sheet_name="T3_por_unidade", index=False); FORA.to_excel(w, sheet_name="T3_fora_da_conta", index=False)
        T4.to_excel(w, sheet_name="T4_resumo", index=False); T4d.to_excel(w, sheet_name="T4_por_unidade")
        PT.to_excel(w, sheet_name="previsoes_turma_2026")
    txt = escrever(dest / RES.name, modo == "--ensaio", T1, EF, QM, T2, RN, ANO, FX, DESC, T3, ROB, T3d, FORA, T4, jov, Bs)
    PT.to_csv(dest / PREV.name, sep=";", encoding="utf-8-sig", float_format="%.6f")
    if modo == "--rodar":
        REG_POS.write_text(f"Turma 2026 (BLK-UNI-15, protocolo v1.1) congelada em {datetime.now():%Y-%m-%d %H:%M}. Escala: log de R$/mês; agregador "
                           f"'ambos_sem' = como se aceitasse os dois apps; total = lse(balcao_sem_k, fator_cadastro x agregador_ambos_sem_k) + k.\n"
                           f"{PREV.name}  SHA-256 {sha(PREV)}\n{RES.name}  SHA-256 {sha(RES)}\nREGISTRO_PRE.txt  SHA-256 {sha(REG_PRE)}\n", encoding="utf-8")
    print(txt if modo == "--rodar" else f"ensaio ok: {dest}")


if __name__ == "__main__":
    main()
