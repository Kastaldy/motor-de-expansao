# -*- coding: utf-8 -*-
"""BLK-UNI-05B — alavancas do operador (protocolo_alavancas.md, congelado antes de rodar).

A: entrada do TotalPass como estudo de evento empilhado (dentro da unidade, ate 2025-12) + conta de substituicao;
   checagem de direcao com as saidas de agregador de 2025-2026.
B: preco Gold, estudios, n. de modalidades e vagas no corte transversal das 39 maduras de 2025 (base M0), regras do UNI-01.
C: confirmacao de B nas 18 unidades de teste do UNI-02 (com e sem Botafogo).
D: receita por aluno de agregador contra a do recorrente (premissa do simulador: 60%).
Rodar com PYTHONPATH=src. So' agregados por unidade; nenhum dado pessoal. `--so-eventos` imprime so' a tabela de
eventos (datas e contagens, sem desfecho) e sai.
"""
import hashlib
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
COL = UNI / "coleta_metragem"


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


ex = mod("ex", UNI / "uni01" / "01_exploracao.py")
u2 = mod("u2", UNI / "uni02" / "01_confirmacao.py")
BASE = ["l_m2", "l_renda", "l_pop"]
FIM_EXPL = "2025-12"
W = 12
MIN_CTRL, MIN_CTRL_SENS = 3, 2
MIN_EV_PLACEBO = 3
FAIXAS_MV = [(6, 8), (9, 11), (12, 17), (18, 23)]
BINS = [(-12, -7, "b_m12"), (-6, -4, "b_m6"), (-3, -2, "b_m3"), (0, 2, "b_p0"), (3, 5, "b_p3"), (6, 8, "b_p6"), (9, 12, "b_p9")]
BINS_TXT = {"b_m12": "−12 a −7", "b_m6": "−6 a −4", "b_m3": "−3 a −2", "b_p0": "0 a 2", "b_p3": "3 a 5", "b_p6": "6 a 8", "b_p9": "9 a 12"}
Y_LOG = {"l_ativos": "total de alunos", "l_pag": "recorrentes (balcão)", "l_fat": "faturamento", "l_ticket": "ticket médio"}
Y_NIV = ["ativos", "pagantes", "agregadores"]
N_BOOT = 2000
SIM_AGR = 0.60
BANDA = (np.log(0.9), np.log(1.1))
ALAV = [("L1", "preco", "preço do plano Gold", 0, 10.0, "por R$ 10"),
        ("L2", "studios", "tem estúdios", +1, 1.0, "ter × não ter"),
        ("L3", "n_mod", "nº de modalidades", +1, 1.0, "+1 modalidade"),
        ("L4", "l_vagas", "vagas de estacionamento", +1, np.log(2), "dobrar as vagas")]
MODS = ["cad_mod_piscina", "cad_mod_studios", "cad_mod_bike", "cad_mod_lutas", "cad_mod_pilates"]
BOTAFOGO = "botafogo-rj"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def pct(v):
    return "–" if v is None or pd.isna(v) else f"{100 * (np.exp(v) - 1):+.1f}%"


def dentro(lo, hi):
    return pd.notna(lo) and pd.notna(hi) and BANDA[0] < lo and hi < BANDA[1]


def exclui0(lo, hi):
    return pd.notna(lo) and pd.notna(hi) and (lo > 0 or hi < 0)


# ---------------------------------------------------------------- parte A: dados e datacao
def tmes(c):
    return c.str[:4].astype(int) * 12 + c.str[5:7].astype(int) - 1


def painel(f):
    """Meses validos (regressao). mvA: placeholder de inauguracao = 999 (24+)."""
    g = f[f.valido].copy()
    g["t"] = tmes(g.competencia)
    g["mvA"] = np.where(g.flag_inauguracao_placeholder.astype(bool), 999.0, g.mv.astype(float))
    g["tp"] = g.alunos_totalpass.fillna(0) > 0
    g["wh"] = g.alunos_gympass.fillna(0) > 0
    g["l_pag"] = np.log(g.pagantes.where(g.pagantes > 0).astype(float))
    for c in Y_NIV:
        g[c] = g[c].astype(float)
    # §3: mes com alunos TotalPass e sem a linha TotalPass no Financeiro nao entra nos desfechos de receita
    g["receita_incompleta"] = (g.alunos_totalpass.fillna(0) > 0) & g.fin_totalpass.isna()
    g.loc[g.receita_incompleta, ["l_fat", "l_ticket"]] = np.nan
    return g.sort_values(["unidade_id", "t"]).reset_index(drop=True)


def todos_meses(f, ate):
    """Todos os meses do Growth (para datar entradas/saidas), nao so' os validos."""
    a = f[f.competencia <= ate].copy()
    a["t"] = tmes(a.competencia)
    a["tp"] = a.alunos_totalpass.fillna(0) > 0
    a["wh"] = a.alunos_gympass.fillna(0) > 0
    return a.sort_values(["unidade_id", "t"])


def trocas_entrada(a, col):
    """Por unidade: (mes da entrada, 1o mes da serie). Entrada: 1o mes com `col` depois de >= 1 mes sem.
    inf = nunca teve; -inf = desde o 1o mes da serie."""
    sw, ini = {}, {}
    for u, h in a.groupby("unidade_id"):
        ini[u] = float(h.t.iloc[0])
        pos = h[h[col]]
        if pos.empty:
            sw[u] = np.inf
        elif (h.t < pos.t.iloc[0]).any():
            sw[u] = float(pos.t.iloc[0])
        else:
            sw[u] = -np.inf
    return pd.Series(sw), pd.Series(ini)


def linhas_controle(g, u, E, sw, ini, col, so_limpos=False):
    """Meses de controle do bloco do evento (u, E), pelo §3."""
    w = g[(g.t >= E - W) & (g.t <= E + W) & (g.mvA >= 6) & (g.unidade_id != u)].copy()
    own = w.unidade_id.map(sw)
    nunca = own == np.inf
    ainda_nao = np.isfinite(own) & (w.t < own)
    ja = pd.Series(False, index=w.index)
    if not so_limpos:
        ja_datado = np.isfinite(own) & (own < E - W)
        ja_inicio = (own == -np.inf) & (w.unidade_id.map(ini) <= E - W - 1)
        cand = w[ja_datado | ja_inicio]
        todo_mes = cand.groupby("unidade_id")[col].all()
        ja = (ja_datado | ja_inicio) & w.unidade_id.map(todo_mes).fillna(False).astype(bool)
    w = w[nunca | ainda_nao | ja]
    ok = w.groupby("unidade_id").t.agg(lambda s: bool((s < E).sum() >= 3 and (s >= E).sum() >= 3))
    ctrl = list(ok[ok].index)
    return w[w.unidade_id.isin(ctrl)], ctrl


def blocos_entrada(f, g, col, ate, so_limpos=False, sem_placeholder_ctrl=False):
    a = todos_meses(f, ate)
    g = g[g.competencia <= ate]
    sw, ini = trocas_entrada(a, col)
    info, blocos = [], []
    for u, E in sw[np.isfinite(sw)].sort_values().items():
        h = g[g.unidade_id == u]
        ha = a[a.unidade_id == u]
        linha_E = ha[ha.t == E].iloc[0]
        mvE = 999.0 if linha_E.flag_inauguracao_placeholder is True or linha_E.flag_inauguracao_placeholder == 1 else float(linha_E.mv)
        tr = h[(h.t >= E - W) & (h.t <= E + W) & (h.mvA >= 6)]
        n_pre, n_pos = int((tr.t < E).sum()), int((tr.t >= E).sum())
        wc, ctrl = linhas_controle(g, u, E, sw, ini, col, so_limpos)
        if sem_placeholder_ctrl:
            ph = set(g.loc[g.flag_inauguracao_placeholder.astype(bool), "unidade_id"])
            wc = wc[~wc.unidade_id.isin(ph)]
            ctrl = [c for c in ctrl if c not in ph]
        fin_ini = ha.loc[ha.fin_totalpass.fillna(0) > 0, "competencia"].min() if col == "tp" else np.nan
        fin_antes = col == "tp" and bool((ha.loc[ha.t <= E - 2, "fin_totalpass"].fillna(0) > 0).any())
        elegivel = mvE >= 6 and n_pre >= 4 and n_pos >= 3 and not fin_antes
        papel = ("principal" if elegivel and len(ctrl) >= MIN_CTRL else
                 "sensibilidade" if elegivel and len(ctrl) >= MIN_CTRL_SENS else
                 "fora (datação: Financeiro antes)" if fin_antes else "fora")
        viz = {f"alunos_rel{k:+d}": float(ha.loc[ha.t == E + k, "alunos_totalpass" if col == "tp" else "alunos_gympass"].sum())
               if (ha.t == E + k).any() else np.nan for k in range(-3, 4)}
        testa_pl = int((tr.t < E - 6).sum()) >= 2 and int(((tr.t >= E - 6) & (tr.t < E)).sum()) >= 2
        info.append(dict(unidade_id=u, competencia=linha_E.competencia, mes_vida=mvE, meses_antes=n_pre, meses_depois=n_pos,
                         n_controles=len(ctrl), controles=", ".join(ctrl), papel=papel, testa_placebo=testa_pl,
                         meses_depois_receita=int(((tr.t >= E) & tr.l_fat.notna()).sum()),
                         primeiro_mes_fin_totalpass=fin_ini, **viz))
        if papel.startswith("fora"):
            continue
        b = pd.concat([tr, wc]).copy()
        b["bloco"], b["E"], b["tratada"], b["papel"] = len(blocos), E, b.unidade_id == u, papel
        b["rel"] = b.t - E
        blocos.append(b)
    B = pd.concat(blocos, ignore_index=True) if blocos else pd.DataFrame()
    return pd.DataFrame(info), preparar(B)


def preparar(B):
    if B.empty:
        return B
    B["depois"] = (B.tratada & (B.rel >= 0)).astype(float)
    for a, b, k in BINS:
        B[k] = (B.tratada & (B.rel >= a) & (B.rel <= b)).astype(float)
    return B


# ---------------------------------------------------------------- parte A: estimador
def demean(M, grupos, tol=1e-9, it=5000):
    M = M.astype(float).copy()
    cnt = [np.bincount(gc).astype(float) for gc in grupos]
    escala = np.maximum(np.abs(M).max(axis=0), 1.0)
    for _ in range(it):
        for gc, n in zip(grupos, cnt):
            for j in range(M.shape[1]):
                M[:, j] -= (np.bincount(gc, weights=M[:, j], minlength=len(n)) / n)[gc]
        gc, n = grupos[0], cnt[0]
        resto = max(np.abs(np.bincount(gc, weights=M[:, j], minlength=len(n)) / n).max() / escala[j] for j in range(M.shape[1]))
        if resto < tol:
            return M, True
    return M, False


def did(B, ys, regs, com_ic=True):
    """Ajusta cada grupo de desfechos com o mesmo padrao de ausencia nas suas proprias linhas (a receita tem menos meses)."""
    if B is None or B.empty:
        return None
    grupos = {}
    for y in ys:
        grupos.setdefault(B[y].notna().to_numpy().tobytes(), []).append(y)
    out = None
    for ys_ in grupos.values():
        r = _did(B, ys_, regs, com_ic)
        if r is None:
            continue
        if out is None:
            out = {k: v for k, v in r.items() if k.startswith("_")}
        out.update({y: r[y] for y in ys_})
    if out is None or not all(y in out for y in ys):
        return None if out is None else {**out, **{y: out.get(y, {reg: dict(beta=np.nan) for reg in regs}) for y in ys}}
    return out


def _did(B, ys, regs, com_ic=True):
    """y = FE unidade x bloco + FE mes x bloco + faixas de maturidade + regs. EP agrupado por unidade (CR1).
    Perda de posto: refaz sem faixas (marcado); se persistir, None."""
    D = B.dropna(subset=ys)
    if D.empty or D.tratada.sum() == 0:
        return None
    g1 = pd.factorize(D.bloco.astype(str) + "|" + D.unidade_id)[0]
    g2 = pd.factorize(D.bloco.astype(str) + "|" + D.t.astype(str))[0]
    fx = np.column_stack([((D.mvA >= a) & (D.mvA <= b)).to_numpy(float) for a, b in FAIXAS_MV])
    R = np.column_stack([D[r].to_numpy(float) for r in regs])
    M, conv = demean(np.column_stack([D[y].to_numpy(float) for y in ys] + [R, fx]), [g1, g2])
    Yd = M[:, :len(ys)]
    Xr, Xf = M[:, len(ys):len(ys) + len(regs)], M[:, len(ys) + len(regs):]
    if np.abs(Xr).max(axis=0).min() < 1e-8:
        return None
    Xf = Xf[:, np.abs(Xf).max(axis=0) > 1e-8]
    Xd, sem_faixas = np.column_stack([Xr, Xf]), False
    if np.linalg.matrix_rank(Xd) < Xd.shape[1]:
        Xd, sem_faixas = Xr, True
        if np.linalg.matrix_rank(Xd) < Xd.shape[1]:
            return None
    XtXi = np.linalg.inv(Xd.T @ Xd)
    cl = pd.factorize(D.unidade_id)[0]
    G, (n, k) = cl.max() + 1, Xd.shape
    kk = k + len(np.unique(g2))
    out = {"_n": n, "_G": int(G), "_trat": int(D[D.tratada].unidade_id.nunique()), "_blocos": int(D.bloco.nunique()),
           "_conv": conv, "_sem_faixas": sem_faixas}
    for i, y in enumerate(ys):
        b = XtXi @ (Xd.T @ Yd[:, i])
        r = {reg: dict(beta=float(b[j])) for j, reg in enumerate(regs)}
        r["_meta"] = dict(n=n, G=int(G), trat=out["_trat"], sem_faixas=sem_faixas)
        if com_ic and G > 1 and n > kk:
            e = Yd[:, i] - Xd @ b
            S = np.zeros((G, k)); np.add.at(S, cl, Xd * e[:, None])
            V = G / (G - 1) * (n - 1) / (n - kk) * XtXi @ (S.T @ S) @ XtXi
            tq = stats.t.ppf(0.95, G - 1)
            for j, reg in enumerate(regs):
                se = np.sqrt(V[j, j])
                r[reg].update(lo=float(b[j] - tq * se), hi=float(b[j] + tq * se), p=float(2 * stats.t.sf(abs(b[j] / se), G - 1)))
        out[y] = r
    return out


def beta(r, y, reg="depois"):
    return np.nan if r is None else r[y][reg]["beta"]


# ---------------------------------------------------------------- parte A
def parte_A(f, g, Dd, a_boot, rho_boot, a_tip):
    ev, B = blocos_entrada(f, g, "tp", FIM_EXPL)
    Bp = B[B.papel == "principal"].copy()
    res = {"eventos": ev}
    res["principal"] = did(Bp, list(Y_LOG), ["depois"])
    res["perfil"] = did(Bp, list(Y_LOG), [k for _, _, k in BINS])
    sens = {"1. com o grupo de SP de 2023-01/02": B,
            "2. só meses com mes_vida ≥ 12": Bp[Bp.mvA >= 12]}
    _, B3 = blocos_entrada(f, g, "tp", FIM_EXPL, so_limpos=True)
    princ = set(ev.loc[ev.papel == "principal", "unidade_id"])
    if not B3.empty:
        t3 = B3.loc[B3.tratada, ["bloco", "unidade_id"]].drop_duplicates()
        B3 = B3[B3.bloco.isin(t3.loc[t3.unidade_id.isin(princ), "bloco"])]
    sens["3. controles só 'nunca' e 'ainda não' (eventos principais com ≥ 2 controles)"] = B3
    _, B4 = blocos_entrada(f, g, "tp", FIM_EXPL, sem_placeholder_ctrl=True)
    sens["4. sem placeholder como controle"] = B4[B4.papel == "principal"] if not B4.empty else B4
    res["sens"] = {k: did(v, list(Y_LOG), ["depois"]) for k, v in sens.items()}
    # placebo: evento falso em E-6, so' meses anteriores ao real
    Bpl = Bp[Bp.t < Bp.E].copy()
    Bpl["depois"] = (Bpl.tratada & (Bpl.rel >= -6)).astype(float)
    res["placebo"] = did(Bpl, list(Y_LOG), ["depois"])
    ev_p = ev[ev.papel == "principal"]
    res["n_testa_placebo"] = int(ev_p.testa_placebo.sum())
    # retirar cada evento; cada evento sozinho
    res["loeo"], res["por_evento"], res["loeo_s"] = {}, {}, {}
    for k in sorted(Bp.bloco.unique()):
        u = Bp.loc[(Bp.bloco == k) & Bp.tratada, "unidade_id"].iloc[0]
        r = did(Bp[Bp.bloco != k], list(Y_LOG) + Y_NIV, ["depois"], com_ic=False)
        res["loeo"][u] = {y: beta(r, y) for y in list(Y_LOG) + Y_NIV}
        ba = res["loeo"][u]["agregadores"]
        res["loeo_s"][u] = -res["loeo"][u]["pagantes"] / ba if pd.notna(ba) and abs(ba) > 1e-9 else np.nan
        r1 = did(Bp[Bp.bloco == k], list(Y_LOG), ["depois"], com_ic=False)
        res["por_evento"][u] = {y: beta(r1, y) for y in Y_LOG} | {"sem_faixas": (r1 or {}).get("_sem_faixas")}
    # nivel e substituicao
    res["nivel"] = did(Bp, Y_NIV, ["depois"])
    bn = {y: beta(res["nivel"], y) for y in Y_NIV}
    s = -bn["pagantes"] / bn["agregadores"]
    # bootstrap estratificado por unidade (tratadas x outras)
    rng = np.random.default_rng(20260929)
    Bp_ = Bp.reset_index(drop=True)
    trat = sorted(Bp_.loc[Bp_.tratada, "unidade_id"].unique())
    outras = sorted(set(Bp_.unidade_id) - set(trat))
    linhas = {u: np.flatnonzero((Bp_.unidade_id == u).to_numpy()) for u in trat + outras}
    boot_s, boot_fat = [], []
    for _ in range(N_BOOT):
        sorteio = list(rng.choice(trat, len(trat))) + list(rng.choice(outras, len(outras)))
        idx = np.concatenate([linhas[u] for u in sorteio])
        rot = np.concatenate([np.full(len(linhas[u]), f"{u}#{j}", dtype=object) for j, u in enumerate(sorteio)])
        Bb = Bp_.iloc[idx].copy(); Bb["unidade_id"] = rot
        r = did(Bb, Y_NIV + ["l_fat"], ["depois"], com_ic=False)
        if r is None:
            boot_s.append(np.nan); boot_fat.append(np.nan); continue
        ba = beta(r, "agregadores")
        boot_s.append(-beta(r, "pagantes") / ba if abs(ba) > 1e-9 else np.nan)
        boot_fat.append(beta(r, "l_fat"))
    boot_s, boot_fat = np.array(boot_s, float), np.array(boot_fat, float)
    res["s"], res["s_ic"] = s, tuple(np.nanquantile(boot_s, [0.05, 0.95]))
    res["n_boot_validas"] = int(np.isfinite(boot_s).sum())
    res["fat_ic_boot"] = tuple(np.nanquantile(boot_fat, [0.05, 0.95]))
    res["bn"] = bn
    mult = lambda s_, a_, rho_: 1 + a_ * (s_ - rho_) / (1 - a_ + a_ * rho_)
    res["m"] = mult(s, a_tip, Dd["razao"])
    mb = mult(boot_s, a_boot[:N_BOOT], rho_boot[:N_BOOT])
    res["m_ic"] = tuple(np.nanquantile(mb, [0.05, 0.95]))
    res["m_s0"], res["m_s1"] = mult(0.0, a_tip, Dd["razao"]), mult(1.0, a_tip, Dd["razao"])
    res["a"], res["rho"] = a_tip, Dd["razao"]
    # leitura (§3)
    rf = res["principal"]["l_fat"]["depois"]
    loeo_ok = all(pd.notna(v["l_fat"]) and np.sign(v["l_fat"]) == np.sign(rf["beta"]) for v in res["loeo"].values())
    pl = res["placebo"]
    pl_estimavel = pl is not None and "lo" in pl["l_fat"]["depois"]
    pl_cobre = pl_estimavel and pl["l_fat"]["depois"]["lo"] <= 0 <= pl["l_fat"]["depois"]["hi"]
    testavel = res["n_testa_placebo"] >= MIN_EV_PLACEBO
    excl = exclui0(rf.get("lo"), rf.get("hi")) and exclui0(*res["fat_ic_boot"])
    if excl and loeo_ok and testavel and pl_cobre:
        leitura = "efeito medido"
    elif excl and loeo_ok and not testavel and (pl_cobre or not pl_estimavel):
        leitura = "efeito provável, sem teste de tendência prévia"
    elif dentro(rf.get("lo"), rf.get("hi")) and dentro(*res["fat_ic_boot"]) and all(
            pd.notna(v["l_fat"]) and BANDA[0] < v["l_fat"] < BANDA[1] for v in res["loeo"].values()):
        leitura = "sem efeito líquido relevante"
    else:
        leitura = "inconclusivo"
    res.update(leitura=leitura, loeo_ok=loeo_ok, pl_estimavel=pl_estimavel, pl_cobre=pl_cobre, testavel=testavel, excl=excl)
    pf = res["perfil"]
    res["pre_cobre"] = None if pf is None else {y: all("lo" in pf[y][k] and pf[y][k]["lo"] <= 0 <= pf[y][k]["hi"]
                                                       for _, _, k in BINS[:3]) for y in Y_LOG}
    # rotulo de m (§7)
    ra = res["nivel"]["agregadores"]["depois"] if res["nivel"] else {}
    s_estavel = all(pd.notna(v) and np.sign(v) == np.sign(s) for v in res["loeo_s"].values())
    res["m_rotulo"] = "medida, não confirmada" if (exclui0(ra.get("lo"), ra.get("hi")) and s_estavel) else "não medida"
    res["s_estavel"] = s_estavel
    return res


def saidas(f, g, col):
    """Confirmacao (§3): saidas de `col` datadas nos meses do Growth."""
    a = todos_meses(f, "9999-99")
    alunos = "alunos_totalpass" if col == "tp" else "alunos_gympass"
    fin = "fin_totalpass" if col == "tp" else "fin_gympass"
    res = []
    for u, h in a.groupby("unidade_id"):
        pos = h[h[col]]
        if pos.empty:
            continue
        ult = pos.t.iloc[-1]
        dep = h[h.t > ult]
        if dep.empty or dep.competencia.iloc[0] < "2025-01":
            continue
        E = float(dep.t.iloc[0])
        ult4 = h[(h.t < E) & (h.t >= E - 4)]
        ult3 = h[(h.t < E) & (h.t >= E - 3)]
        gu = g[g.unidade_id == u]
        tr = gu[(gu.t >= E - W) & (gu.t <= E + W) & (gu.mvA >= 6)]
        linha = dict(unidade_id=u, agregador={"tp": "TotalPass", "wh": "Wellhub"}[col], primeiro_mes_sem=dep.competencia.iloc[0],
                     meses_com_nos_4_anteriores=int(ult4[col].sum()), alunos_media_3_anteriores=float(ult3[alunos].mean()),
                     meses_antes=int((tr.t < E).sum()), meses_depois=int((tr.t >= E).sum()),
                     receita_fin_antes=float(h.loc[(h.t < E) & (h.t >= E - 3), fin].mean()),
                     receita_fin_depois=float(h.loc[h.t >= E + 1, fin].mean()))
        valida = (linha["meses_com_nos_4_anteriores"] >= 3 and linha["alunos_media_3_anteriores"] >= 20
                  and linha["meses_antes"] >= 4 and linha["meses_depois"] >= 3)
        w = g[(g.t >= E - W) & (g.t <= E + W) & (g.mvA >= 6) & (g.unidade_id != u)]
        st = w.groupby("unidade_id")[col].agg(["min", "max"])
        w = w[w.unidade_id.isin(st.index[st["min"] == st["max"]])]
        ok = w.groupby("unidade_id").t.agg(lambda s: bool((s < E).sum() >= 3 and (s >= E).sum() >= 3))
        ctrl = list(ok[ok].index)
        linha.update(n_controles=len(ctrl), analisavel=bool(valida and ctrl))
        if linha["analisavel"]:
            b = pd.concat([tr, w[w.unidade_id.isin(ctrl)]]).copy()
            b["bloco"], b["E"], b["tratada"] = 0, E, b.unidade_id == u
            b["rel"] = b.t - E
            r = did(preparar(b), list(Y_LOG), ["depois"], com_ic=False)
            linha["analisavel"] = r is not None
            for y in Y_LOG:
                linha["efeito_" + y] = beta(r, y)
        res.append(linha)
    return pd.DataFrame(res)


# ---------------------------------------------------------------- parte B / C
def atributos_ext(d):
    A = ex.atributos(d)
    b = lambda c: d[c].map({True: 1.0, False: 0.0}).astype(float)
    A["preco"] = pd.to_numeric(d.cad_preco_gold, errors="coerce")
    A["studios"] = b("cad_mod_studios")
    A["n_mod"] = pd.concat([b(c) for c in MODS], axis=1).sum(axis=1, min_count=len(MODS))
    A["l_vagas"] = np.log1p(pd.to_numeric(d.tam_vagas, errors="coerce"))
    return A


def parte_B(A, Yp, Ya, Yb):
    linhas = []
    for lid, x, nome, sinal, du, txt in ALAV:
        for y in ("l_fat", "l_ativos", "l_ticket"):
            T = dict(id=lid, h=nome, y=y, x=x, sinal=sinal if y == "l_fat" else 0, tipo="log")
            r = ex.ajustar(T, Yp, A)
            conv = {}
            for k, Y_ in (("p", Yp), ("A", Ya), ("B", Yb)):
                D, _, _ = ex.montar(T, Y_, A)
                sd = D[x].std(ddof=0) if len(D) else np.nan
                conv[k] = du / sd if sd and sd > 0 else np.nan
            ra, rb = ex.ajustar(T, Ya, A), ex.ajustar(T, Yb, A)
            r["beta_A"], r["beta_B"] = ra.get("beta", np.nan), rb.get("beta", np.nan)
            classe, falhou = ex.classificar(r, T) if y == "l_fat" else ("", "")
            linhas.append(dict(id=lid, alavanca=nome, x=x, desfecho=y, unidade=txt, n=r.get("n"),
                               efeito_dp=r.get("beta", np.nan), ic_lo_dp=r.get("ic_lo", np.nan), ic_hi_dp=r.get("ic_hi", np.nan),
                               efeito_unid=r.get("beta", np.nan) * conv["p"], ic_lo_unid=r.get("ic_lo", np.nan) * conv["p"],
                               ic_hi_unid=r.get("ic_hi", np.nan) * conv["p"], p=r.get("p", np.nan), dr2_loo=r.get("dr2_loo", np.nan),
                               lomo_ok=r.get("lomo_sinal_ok"), lomo_n=r.get("lomo_n"),
                               efeito_A_unid=r["beta_A"] * conv["A"], efeito_B_unid=r["beta_B"] * conv["B"],
                               classe=classe, falhou=falhou))
    return pd.DataFrame(linhas)


def parte_C(A, Y25, Y26, d):
    est = pd.read_csv(COL / "metragem_estimada.csv", sep=";", encoding="utf-8-sig", index_col=0)
    oficial = d.tam_metragem_m2.dropna()
    sat = est.metragem_estimada_m2.dropna()
    m2_princ = np.log(pd.concat([oficial, sat[~sat.index.isin(oficial.index)]]))
    todos = list(oficial.index) + list(sat.index.difference(oficial.index))
    R = u2.rodar(A, Y25, Y26, d, todos, m2_princ)
    te, cal = R["te"], R["cal"]
    tr = A.join(Y25, how="inner").dropna(subset=["l_fat"] + BASE + ["frac_indep"])
    rng = np.random.default_rng(20260930)
    res, por_unid = [], []
    for lid, x, nome, _, _, _ in ALAV:
        trx = tr[tr[x].notna()]
        linha = dict(id=lid, alavanca=nome, n_treino=len(trx))
        for versao, tx in (("com", te[te[x].notna()]), ("sem", te[te[x].notna() & (te.index != BOTAFOGO)])):
            if len(tx) < 5:
                linha.update({f"n_{versao}": len(tx), f"leitura_{versao}": "sem amostra"})
                continue
            y = tx.l_fat.to_numpy(float)
            p0 = u2.ajusta_prevê(trx, tx, BASE) + cal
            p1 = u2.ajusta_prevê(trx, tx, BASE + [x]) + cal
            e0, e1 = np.abs(np.exp(y - p0) - 1), np.abs(np.exp(y - p1) - 1)
            dif = [np.median(e1[i]) - np.median(e0[i]) for i in (rng.integers(0, len(y), len(y)) for _ in range(N_BOOT))]
            rho0, rho1 = stats.spearmanr(p0, y)[0], stats.spearmanr(p1, y)[0]
            m0, m1 = np.median(e0), np.median(e1)
            linha.update({f"n_{versao}": len(y), f"erro_M0_{versao}": m0, f"erro_mais_{versao}": m1, f"dif_{versao}": m1 - m0,
                          f"dif_lo_{versao}": np.quantile(dif, 0.05), f"dif_hi_{versao}": np.quantile(dif, 0.95),
                          f"rho_M0_{versao}": rho0, f"rho_mais_{versao}": rho1,
                          f"leitura_{versao}": "consistente" if (m1 < m0 and rho1 >= rho0) else "não se repete"})
            if versao == "com":
                for u, a_, b_, v in zip(tx.index, np.exp(y - p0) - 1, np.exp(y - p1) - 1, tx[x]):
                    por_unid.append(dict(id=lid, unidade_id=u, valor=v, erro_M0=a_, erro_M0_mais=b_))
        linha["leitura"] = "consistente" if (linha.get("leitura_com") == "consistente" and linha.get("leitura_sem") == "consistente") else \
            ("sem amostra" if linha.get("leitura_com") == "sem amostra" else "não se repete")
        res.append(linha)
    return pd.DataFrame(res), pd.DataFrame(por_unid), R


# ---------------------------------------------------------------- parte D
def parte_D(f, Yp):
    v = f[f.valido & (f.competencia >= "2025-01") & (f.competencia <= "2025-12") & (f.mv >= 12)].copy()
    wh = np.where(v.fin_gympass.notna(), v.fin_gympass, np.where(v.alunos_gympass.fillna(0) == 0, 0.0, np.nan))
    tp = np.where(v.fin_totalpass.notna(), v.fin_totalpass, np.where(v.alunos_totalpass.fillna(0) == 0, 0.0, np.nan))
    v["rec_wh"], v["rec_tp"] = wh, tp
    n0 = len(v)
    v = v[v.rec_wh.notna() & v.rec_tp.notna() & (v.agregadores > 0) & (v.pagantes > 0)].copy()
    v["rec_agr"] = v.rec_wh + v.rec_tp
    v["r_agr"] = v.rec_agr / v.agregadores
    v["r_rec"] = (v.faturamento - v.rec_agr) / v.pagantes
    v["r_rec_bruto"] = (v.faturamento - v.rec_agr + v.fin_tem_saude.fillna(0)) / v.pagantes
    v["razao"] = v.r_agr / v.r_rec
    wh_ = v[v.alunos_gympass > 0]
    tp_ = v[v.alunos_totalpass > 0]
    out = dict(n_meses=len(v), n_unid=v.unidade_id.nunique(), n_fora=n0 - len(v),
               r_agr=float(v.r_agr.median()), r_rec=float(v.r_rec.median()), r_rec_bruto=float(v.r_rec_bruto.median()),
               razao=float(v.razao.median()), razao_q=tuple(v.razao.quantile([0.25, 0.75])),
               razao_bruta=float((v.r_agr / v.r_rec_bruto).median()),
               razao_unid=float(v.groupby("unidade_id").razao.median().median()),
               razao_wh=float((wh_.rec_wh / wh_.alunos_gympass / wh_.r_rec).median()), n_wh=len(wh_),
               razao_tp=float((tp_.rec_tp / tp_.alunos_totalpass / tp_.r_rec).median()), n_tp=len(tp_),
               tem_saude_pct=float((v.fin_tem_saude.fillna(0) / v.faturamento).median()))
    # bootstraps para m (§3): rho por unidade (mediana dos meses das unidades sorteadas) e a (39 de treino)
    rng = np.random.default_rng(20261001)
    unid = v.unidade_id.unique()
    por_u = {u: v.loc[v.unidade_id == u, "razao"].to_numpy() for u in unid}
    rho_b = np.array([np.median(np.concatenate([por_u[u] for u in rng.choice(unid, len(unid))])) for _ in range(N_BOOT)])
    agr = Yp.agr.dropna().to_numpy()
    a_b = np.array([np.median(rng.choice(agr, len(agr))) for _ in range(N_BOOT)])
    return out, rho_b, a_b


# ---------------------------------------------------------------- relatorio
def main():
    f, d = ex.carregar()
    g = painel(f)
    if "--so-eventos" in sys.argv:
        for nome, kw in (("principal", {}), ("so' limpos", {"so_limpos": True}), ("sem placeholder", {"sem_placeholder_ctrl": True})):
            ev, _ = blocos_entrada(f, g, "tp", FIM_EXPL, **kw)
            cols = ["unidade_id", "competencia", "mes_vida", "meses_antes", "meses_depois", "meses_depois_receita", "n_controles", "papel", "testa_placebo",
                    "primeiro_mes_fin_totalpass"] + [c for c in ev.columns if c.startswith("alunos_rel")]
            print(f"\n== {nome}\n", ev[cols].to_string())
        return
    arqs = [AQUI / "protocolo_alavancas.md", Path(__file__), UNI / "fato_unidade_mes.parquet", UNI / "dim_unidade.parquet",
            UNI / "uni01" / "01_exploracao.py", UNI / "uni02" / "01_confirmacao.py", COL / "metragem_estimada.csv",
            UNI / "uni05" / "comparacao_por_unidade.csv"]
    hashes = {p.name: sha(p) for p in arqs}
    A = atributos_ext(d)
    Y25 = ex.desfechos(f, "2025-01", "2025-12")
    Y26 = ex.desfechos(f, "2026-01", "2026-08")
    tr_idx = A.join(Y25, how="inner").dropna(subset=["l_fat"] + BASE + ["frac_indep"]).index
    Yp = Y25.loc[tr_idx]
    Ya = ex.desfechos_ajustados(f)[0].reindex(tr_idx).dropna(how="all")
    Yb = ex.desfechos(f, "2025-01", "2025-09").reindex(tr_idx).dropna(how="all")
    md = AQUI / "resultado_alavancas.md"
    L = ["# BLK-UNI-05B — alavancas do operador: resultado", "",
         f"Protocolo `protocolo_alavancas.md` (SHA-256 `{hashes['protocolo_alavancas.md'][:16]}…`). Rodado uma vez.", ""]
    flush = lambda: md.write_text("\n".join(L) + "\n", encoding="utf-8")

    # ---- D
    Dd, rho_b, a_b = parte_D(f, Yp)
    L += ["## D — Quanto rende um aluno de agregador (premissa do simulador)", "",
          f"- {Dd['n_meses']} meses de {Dd['n_unid']} unidades maduras em 2025 ({Dd['n_fora']} meses fora: sem alunos de agregador, "
          f"sem recorrentes ou com componente do Financeiro ausente).",
          f"- Receita mensal por aluno de agregador: **R$ {Dd['r_agr']:.0f}**. Por recorrente: **R$ {Dd['r_rec']:.0f}** "
          f"(R$ {Dd['r_rec_bruto']:.0f} sem o desconto do Tem Saúde, que é {100 * Dd['tem_saude_pct']:.1f}% do faturamento na mediana).",
          f"- **ρ = {100 * Dd['razao']:.0f}%** (mediana dos meses; quartis {100 * Dd['razao_q'][0]:.0f}–{100 * Dd['razao_q'][1]:.0f}%; "
          f"mediana por unidade {100 * Dd['razao_unid']:.0f}%; bruto {100 * Dd['razao_bruta']:.0f}%). Wellhub {100 * Dd['razao_wh']:.0f}% "
          f"({Dd['n_wh']} meses), TotalPass {100 * Dd['razao_tp']:.0f}% ({Dd['n_tp']} meses). **O simulador supõe {100 * SIM_AGR:.0f}%.**", ""]
    flush()

    # ---- A
    a_tip = float(Yp.agr.median())
    RA = parte_A(f, g, Dd, a_b, rho_b, a_tip)
    ev = RA["eventos"]
    ev.assign(**{f"efeito_{y}_so_este": ev.unidade_id.map(lambda u, y=y: RA["por_evento"].get(u, {}).get(y, np.nan)) for y in Y_LOG}) \
        .to_csv(AQUI / "eventos_agregador.csv", sep=";", encoding="utf-8-sig", index=False)
    sai = pd.concat([saidas(f, g, "tp"), saidas(f, g, "wh")], ignore_index=True)
    sai.to_csv(AQUI / "saidas_agregador.csv", sep=";", encoding="utf-8-sig", index=False)
    pa = RA["principal"]
    ic = lambda r: f"[{pct(r['lo'])}; {pct(r['hi'])}]" if r and "lo" in r else "–"
    L += ["## A — Aceitar agregador (entrada do TotalPass, dentro da unidade)", "", "### Eventos", "",
          "| unidade | 1º mês com TotalPass | 1º mês com receita TP no Financeiro | mês de vida | meses antes | meses depois | controles | testa o placebo | papel |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in ev.itertuples():
        L.append(f"| {r.unidade_id} | {r.competencia} | {r.primeiro_mes_fin_totalpass} | {'24+ (placeholder)' if r.mes_vida >= 999 else f'{r.mes_vida:.0f}'} | "
                 f"{r.meses_antes} | {r.meses_depois} ({r.meses_depois_receita} com receita) | {r.n_controles} | {'sim' if r.testa_placebo else 'não'} | {r.papel} |")
    n_sp = ev[ev.papel == "sensibilidade"].n_controles
    L += ["", "### Efeito de passar a aceitar o TotalPass", "",
          f"Estimativa principal: {pa['_trat']} unidades tratadas, {pa['_G']} unidades no total, {pa['_n']} meses-unidade"
          f"{' (ajuste sem faixas de maturidade: posto)' if pa['_sem_faixas'] else ''}{'' if pa['_conv'] else ' — ATENÇÃO: a absorção dos efeitos fixos não convergiu'}. "
          f"Nos desfechos de receita (faturamento, ticket): {pa['l_fat'].get('_meta', {}).get('trat', '–')} tratadas, "
          f"{pa['l_fat'].get('_meta', {}).get('n', '–')} meses-unidade (meses sem a linha TotalPass no Financeiro ficam fora).", "",
          "| desfecho | principal | IC 90% (CR1) | placebo (evento 6 meses antes) | IC placebo |", "|---|---|---|---|---|"]
    pl = RA["placebo"]
    for y, nome in Y_LOG.items():
        r = pa[y]["depois"]
        L.append(f"| {nome} | **{pct(r['beta'])}** | {ic(r)} | {pct(beta(pl, y))} | {ic(pl[y]['depois']) if pl else 'não estimável'} |")
    L += ["", f"IC 90% do faturamento por bootstrap de unidades: [{pct(RA['fat_ic_boot'][0])}; {pct(RA['fat_ic_boot'][1])}]. "
          f"Eventos que testam o placebo: {RA['n_testa_placebo']} de {int((ev.papel == 'principal').sum())}.", "",
          "**Sensibilidades** (efeito no faturamento, alunos, recorrentes, ticket; N tratadas):", "",
          "| sensibilidade | tratadas | alunos | recorrentes | faturamento | ticket |", "|---|---|---|---|---|---|"]
    for k, r in RA["sens"].items():
        L.append(f"| {k} | {r['_trat'] if r else 0} | " + " | ".join(f"{pct(beta(r, y))} {ic(r[y]['depois']) if r else ''}" for y in
                                                             ("l_ativos", "l_pag", "l_fat", "l_ticket")) + " |")
    L += ["", f"(Grupo de SP na sensibilidade 1: {len(n_sp)} eventos, com {', '.join(str(x) for x in sorted(set(n_sp)))} controles.)", "",
          "**Retirando cada evento** (efeito principal sem ele):", "", "| evento retirado | alunos | recorrentes | faturamento | ticket | s |",
          "|---|---|---|---|---|---|"]
    for u, v in RA["loeo"].items():
        L.append(f"| {u} | {pct(v['l_ativos'])} | {pct(v['l_pag'])} | {pct(v['l_fat'])} | {pct(v['l_ticket'])} | {RA['loeo_s'][u]:.2f} |")
    L += ["", "**Cada evento sozinho** (descritivo; um só tratado, sem IC):", "", "| evento | alunos | recorrentes | faturamento | ticket |",
          "|---|---|---|---|---|"]
    for u, v in RA["por_evento"].items():
        L.append(f"| {u}{' (sem faixas)' if v.get('sem_faixas') else ''} | {pct(v['l_ativos'])} | {pct(v['l_pag'])} | {pct(v['l_fat'])} | {pct(v['l_ticket'])} |")
    pf = RA["perfil"]
    L += ["", "**Perfil no tempo** (meses em relação à entrada; referência = mês −1; o Financeiro recebe o agregador com atraso, "
          "então os primeiros meses depois subestimam a receita):", "", "| faixa | alunos | recorrentes | faturamento | ticket |", "|---|---|---|---|---|"]
    if pf:
        for _, _, k in BINS:
            L.append(f"| {BINS_TXT[k]} | " + " | ".join(f"{pct(pf[y][k]['beta'])} {ic(pf[y][k])}" for y in Y_LOG) + " |")
        L.append("")
        L.append("Faixas anteriores ao evento com IC cobrindo zero: " + "; ".join(f"{Y_LOG[y]} {'sim' if ok else 'não'}" for y, ok in RA["pre_cobre"].items()) + ".")
    L += ["", f"**Leitura (regra do §3): {RA['leitura']}.**",
          f"- IC CR1 e bootstrap excluem zero: {'sim' if RA['excl'] else 'não'}.",
          f"- Sinal estável ao retirar cada evento: {'sim' if RA['loeo_ok'] else 'não'}.",
          f"- Placebo: {'testável' if RA['testavel'] else 'não testável'} ({RA['n_testa_placebo']} evento(s) o testam); "
          f"{'não estimável' if not RA['pl_estimavel'] else ('cobre zero' if RA['pl_cobre'] else 'NÃO cobre zero')}.", "",
          "### Conta de substituição e \"não aceita agregador\"", "",
          f"- Em nível, por unidade: {RA['bn']['agregadores']:+.0f} alunos de agregador, {RA['bn']['pagantes']:+.0f} recorrentes, "
          f"{RA['bn']['ativos']:+.0f} no total "
          f"(IC agregadores [{res_nivel_lo(RA, 'agregadores'):+.0f}; {res_nivel_hi(RA, 'agregadores'):+.0f}]; "
          f"IC recorrentes [{res_nivel_lo(RA, 'pagantes'):+.0f}; {res_nivel_hi(RA, 'pagantes'):+.0f}]).",
          f"- **s = {RA['s']:.2f}** recorrentes perdidos por aluno de agregador ganho (IC 90% bootstrap [{RA['s_ic'][0]:.2f}; {RA['s_ic'][1]:.2f}], "
          f"{RA['n_boot_validas']} reamostras válidas; sinal estável ao retirar cada evento: {'sim' if RA['s_estavel'] else 'não'}).",
          f"- Com a fatia típica de agregador da rede (a = {100 * RA['a']:.0f}% dos alunos) e ρ = {100 * RA['rho']:.0f}%, uma unidade "
          f"**sem agregador** fatura **{100 * (RA['m'] - 1):+.0f}%** sobre a previsão da praça (faixa bootstrap conjunta "
          f"{100 * (RA['m_ic'][0] - 1):+.0f}% a {100 * (RA['m_ic'][1] - 1):+.0f}%). Referências: sem canibalização (s = 0), "
          f"{100 * (RA['m_s0'] - 1):+.0f}%; com canibalização total (s = 1), {100 * (RA['m_s1'] - 1):+.0f}%.",
          f"- Rótulo de m (§7): **{RA['m_rotulo']}**. É extrapolação: mede-se a entrada de um agregador sobre o Wellhub já aceito."]
    try:
        c5 = pd.read_csv(UNI / "uni05" / "comparacao_por_unidade.csv", sep=";", encoding="utf-8-sig")
        bf = c5[(c5.grupo == "teste") & (c5.unidade_id == BOTAFOGO)].iloc[0]
        L.append(f"- Ilustração (não teste), Botafogo: v2 R$ {bf.fat_V2:,.0f} → com \"sem agregador\" R$ {bf.fat_V2 * RA['m']:,.0f} "
                 f"(real R$ {bf.fat_real:,.0f}).")
    except Exception as e:  # noqa: BLE001
        L.append(f"- Ilustração de Botafogo indisponível: {e}")
    s_at, s_ft = np.sign(beta(pa, "l_ativos")), np.sign(beta(pa, "l_fat"))
    sai_ok = sai[sai.analisavel] if "analisavel" in sai else sai.iloc[0:0]
    consist_A = bool(len(sai_ok) and all(np.sign(r.efeito_l_ativos) == -s_at and np.sign(r.efeito_l_fat) == -s_ft for r in sai_ok.itertuples()))
    L += ["", "### Confirmação de direção: saídas de agregador em 2025–2026", "",
          "| unidade | agregador | 1º mês sem | com agregador nos 4 anteriores | alunos (média 3 anteriores) | receita Fin. antes → depois | analisável | alunos | recorrentes | faturamento | ticket |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sai.itertuples():
        gv = lambda k: pct(getattr(r, k)) if hasattr(r, k) else "–"
        L.append(f"| {r.unidade_id} | {r.agregador} | {r.primeiro_mes_sem} | {r.meses_com_nos_4_anteriores} | {r.alunos_media_3_anteriores:.0f} | "
                 f"R$ {r.receita_fin_antes:,.0f} → R$ {r.receita_fin_depois:,.0f} | {'sim' if r.analisavel else 'não'} | "
                 f"{gv('efeito_l_ativos')} | {gv('efeito_l_pag')} | {gv('efeito_l_fat')} | {gv('efeito_l_ticket')} |")
    L += ["", f"Saídas consistentes (sinal oposto ao da entrada em alunos e faturamento, em todas as analisáveis): "
          f"**{'sim' if consist_A else 'não'}** ({len(sai_ok)} analisável(is)).", ""]
    flush()

    # ---- B
    RB = parte_B(A, Yp, Ya, Yb)
    RB.to_csv(AQUI / "alavancas_corte.csv", sep=";", encoding="utf-8-sig", index=False)
    L += ["## B — Preço, estúdios, modalidades e vagas (39 maduras de 2025, sobre o M0)", "",
          "Preço e vagas já tinham sido olhados contra o erro do modelo (protocolo §2): para eles, esta parte é exploratória.", "",
          "| alavanca | desfecho | N | efeito (unidade de negócio) | IC 90% | ΔR² LOO | estável | sens. A | sens. B | classe | falhou |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in RB.itertuples():
        neg = "**" if r.desfecho == "l_fat" else ""
        L.append(f"| {r.alavanca} ({r.unidade}) | {Y_LOG.get(r.desfecho, r.desfecho)} | {r.n} | {neg}{pct(r.efeito_unid)}{neg} | "
                 f"[{pct(r.ic_lo_unid)}; {pct(r.ic_hi_unid)}] | {r.dr2_loo:+.3f} | {'sim' if r.lomo_ok else 'não'} ({r.lomo_n}) | "
                 f"{pct(r.efeito_A_unid)} | {pct(r.efeito_B_unid)} | {r.classe} | {r.falhou} |")
    L += ["", "Classe só no faturamento (regras do UNI-01; faixa de irrelevância ±10% por desvio-padrão).", ""]
    flush()

    # ---- C
    RC, RCu, R2 = parte_C(A, Y25, Y26, d)
    RCu.assign(nome=RCu.unidade_id.map(d.nome)).to_csv(AQUI / "confirmacao_alavancas.csv", sep=";", encoding="utf-8-sig", index=False)
    L += ["## C — Confirmação nas unidades de teste (2026)", "", f"Ajuste de calendário do UNI-02: {pct(R2['cal'])}.", "",
          "| alavanca | versão | N | erro M0 | erro M0 + alavanca | diferença | IC 90% | ordenação M0 | ordenação M0 + alavanca | leitura |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in RC.to_dict("records"):
        for versao, txt in (("com", "com Botafogo"), ("sem", "sem Botafogo")):
            if r.get(f"leitura_{versao}") == "sem amostra":
                L.append(f"| {r['alavanca']} | {txt} | {r.get(f'n_{versao}')} | – | – | – | – | – | – | sem amostra |")
                continue
            L.append(f"| {r['alavanca']} | {txt} | {r[f'n_{versao}']} | {100 * r[f'erro_M0_{versao}']:.1f}% | {100 * r[f'erro_mais_{versao}']:.1f}% | "
                     f"{100 * r[f'dif_{versao}']:+.1f} p.p. | [{100 * r[f'dif_lo_{versao}']:+.1f}; {100 * r[f'dif_hi_{versao}']:+.1f}] | "
                     f"{r[f'rho_M0_{versao}']:+.2f} | {r[f'rho_mais_{versao}']:+.2f} | {r[f'leitura_{versao}']} |")
    L += ["", "Consistente = consistente com e sem Botafogo.", ""]
    flush()

    # ---- entradas da v2 (§7)
    L += ["## Entradas para a v2 (rótulo pelo §7; a decisão é do Felipe)", "", "| alavanca | rótulo | efeito no faturamento |", "|---|---|---|"]
    rot_A = {"efeito medido": "medida e consistente" if consist_A else "medida, não confirmada",
             "efeito provável, sem teste de tendência prévia": "medida, não confirmada",
             "sem efeito líquido relevante": "sem efeito relevante"}.get(RA["leitura"], "não medida")
    L.append(f"| aceita mais um agregador (TotalPass sobre o Wellhub) | {rot_A} | {pct(beta(pa, 'l_fat'))} {ic(pa['l_fat']['depois'])} |")
    L.append(f"| não aceita agregador (extrapolação pela conta de substituição) | {RA['m_rotulo']} | {100 * (RA['m'] - 1):+.0f}% "
             f"[{100 * (RA['m_ic'][0] - 1):+.0f}%; {100 * (RA['m_ic'][1] - 1):+.0f}%] |")
    for lid, x, nome, _, _, txt in ALAV:
        rb_ = RB[(RB.id == lid) & (RB.desfecho == "l_fat")].iloc[0]
        rc_ = RC[RC.id == lid].iloc[0]
        if rb_.classe == "candidata":
            rot = "medida e consistente" if rc_.leitura == "consistente" else "medida, não confirmada"
        elif rb_.classe == "fraca":
            rot = "medida, não confirmada"
        elif rb_.classe == "descartada":
            rot = "sem efeito relevante" if dentro(rb_.ic_lo_unid, rb_.ic_hi_unid) else "não medida"
        elif rb_.classe == "contraria":
            rot = "sinal oposto ao esperado"
        else:
            rot = "não medida"
        L.append(f"| {nome} ({txt}) | {rot} | {pct(rb_.efeito_unid)} [{pct(rb_.ic_lo_unid)}; {pct(rb_.ic_hi_unid)}] |")
    L += ["", "## Insumos (SHA-256)", ""] + [f"- `{k}`: `{v}`" for k, v in hashes.items()]
    flush()
    print("\n".join(L))


def res_nivel_lo(RA, y):
    r = RA["nivel"][y]["depois"] if RA["nivel"] else {}
    return r.get("lo", np.nan)


def res_nivel_hi(RA, y):
    r = RA["nivel"][y]["depois"] if RA["nivel"] else {}
    return r.get("hi", np.nan)


if __name__ == "__main__":
    main()
