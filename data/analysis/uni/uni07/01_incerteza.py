# -*- coding: utf-8 -*-
"""BLK-UNI-07 — incerteza do modelo e faixas de seguranca (protocolo_uni07.md, congelado antes de rodar).
Modelo: v2 adotada (M0 + estudios + master real); M0 como referencia. .venv do projeto, PYTHONPATH=src."""
import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from motor_expansao.dimensionamento import config as cfg
from motor_expansao.dimensionamento.simulador import Premissas, simular

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
RAIZ = UNI.parent.parent.parent
BASE = ["l_m2", "l_renda", "l_pop"]


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


ex = mod("ex", UNI / "uni01" / "01_exploracao.py")
alav = mod("alav", UNI / "alavancas" / "01_alavancas.py")
c5 = mod("c5", UNI / "uni05" / "01_comparacao.py")
X_ = lambda D, cols: np.column_stack([np.ones(len(D))] + [D[c].to_numpy(float) for c in cols])
pc = lambda v: f"{100 * (np.exp(v) - 1):+.0f}%"


def binom_ic(k, n):
    lo = stats.beta.ppf(0.05, k, n - k + 1) if k > 0 else 0.0
    hi = stats.beta.ppf(0.95, k + 1, n - k) if k < n else 1.0
    return lo, hi


def sim(fat, estudio):
    """Simulador de producao, premissas-padrao + rampa observada; estudio soma SIM_CUSTO_STUDIO (1 estudio)."""
    al = c5.alunos_de(fat)
    a0 = c5.RAMPA_OBS[0] * al
    p = Premissas(ticket_cheio=float(cfg.SIM_MENSALIDADE_BALCAO), share_balcao=cfg.SIM_SHARE_BALCAO, aluguel_mes=float(cfg.SIM_ALUGUEL_MES),
                  alunos_inicial=float(a0), maturacao_meses=int(c5.RAMPA_OBS[1]),
                  outros_fixos_mes=float(cfg.SIM_OUTROS_FIXOS_MES) + (float(cfg.SIM_CUSTO_STUDIO) if estudio else 0.0))
    r = simular(float(al), p, obra=float(cfg.SIM_CAPEX_DEFAULT))
    pb = r.payback_meses if np.isfinite(r.payback_meses) else c5.HORIZ
    return dict(alunos=al, margem=r.margem_ebitda_pct, payback=min(pb, c5.HORIZ), viavel=bool(r.flag_viavel))


def main():
    arqs = [AQUI / "protocolo_uni07.md", Path(__file__), UNI / "fato_unidade_mes.parquet", UNI / "dim_unidade.parquet",
            UNI / "alavancas" / "master_id_cadastro.csv", UNI / "uni02" / "confirmacao_por_unidade.csv", UNI / "uni05" / "01_comparacao.py",
            UNI / "uni01" / "01_exploracao.py", UNI / "alavancas" / "01_alavancas.py", UNI / "uni02" / "01_confirmacao.py",
            RAIZ / "src" / "motor_expansao" / "dimensionamento" / "config.py", RAIZ / "src" / "motor_expansao" / "dimensionamento" / "simulador.py"]
    hashes = {p.name: sha(p) for p in arqs}
    f, d = ex.carregar()
    A = alav.atributos_ext(d)
    mid = pd.read_csv(UNI / "alavancas" / "master_id_cadastro.csv", sep=";", dtype=str)
    A["master_id"] = d.cod_cadastro.map(mid.assign(c=mid.cod_cadastro.str.zfill(2)).set_index("c").master_id).reindex(A.index)
    Y25, Y26 = ex.desfechos(f, "2025-01", "2025-12"), ex.desfechos(f, "2026-01", "2026-08")
    tr = A.join(Y25, how="inner").dropna(subset=["l_fat"] + BASE + ["frac_indep", "studios", "master_id"])
    t2 = pd.read_csv(UNI / "uni02" / "confirmacao_por_unidade.csv", sep=";", encoding="utf-8-sig", index_col=0)
    te = A.drop(columns=["l_m2"]).join(np.log(t2.m2).rename("l_m2")).join(Y26, how="inner").loc[t2.index]
    assert len(tr) == 39 and len(te) == 18, (len(tr), len(te))
    assert te.master_id.notna().all() and te.studios.notna().all()
    te["fonte_m2"] = t2.fonte_m2; tr["fonte_m2"] = "oficial"
    amb = tr.index.intersection(Y26.index); cal = float(np.median(Y26.loc[amb, "l_fat"] - Y25.loc[amb, "l_fat"]))
    cont = tr.master_id.value_counts(); proprios = sorted(m for m, n in cont.items() if n >= 4 and m != "M1")
    for D in (tr, te):
        for m in proprios:
            D[f"mr_{m}"] = (D.master_id == m).astype(float)
        D["mr_outras"] = (~D.master_id.isin(["M1"] + proprios)).astype(float)
    V2 = BASE + [f"mr_{m}" for m in proprios] + ["mr_outras", "studios"]
    MODS = {"v2 (praça + estúdios + master)": V2, "M0 (só praça)": BASE}

    # ---- erros fora da amostra
    E = {}
    for nome, cols in MODS.items():
        y = tr.l_fat.to_numpy(float)
        b, e, h, _ = ex.ols(y, X_(tr, cols))
        p_tr, p_te = y - e / (1 - h), X_(te, cols) @ b + cal
        D = pd.DataFrame({"grupo": ["treino"] * len(tr) + ["teste"] * len(te), "previsto_log": np.r_[p_tr, p_te],
                          "real_log": np.r_[y, te.l_fat.to_numpy(float)]}, index=list(tr.index) + list(te.index))
        D["residuo"] = D.real_log - D.previsto_log
        E[nome] = D
    m0te = E["M0 (só praça)"].query("grupo == 'teste'").residuo
    san = (np.median(np.abs(np.exp(m0te) - 1)), np.median(np.exp(m0te) - 1))
    ev = E["v2 (praça + estúdios + master)"].copy()
    uf = d.uf.reindex(ev.index)
    ev["uf_grupo"] = np.where(uf == "SP", "SP", np.where(uf.isin(["DF", "GO"]), "DF-GO", "outros"))
    ev["studios"] = pd.concat([tr.studios, te.studios]).reindex(ev.index).values
    ev["fonte_m2"] = pd.concat([tr.fonte_m2, te.fonte_m2]).reindex(ev.index).values
    ev["nome"] = d.nome.reindex(ev.index).values
    ev["previsto_2026_log"] = ev.previsto_log + np.where(ev.grupo == "treino", cal, 0.0)
    ev.to_csv(AQUI / "erros_fora_da_amostra.csv", sep=";", encoding="utf-8-sig")

    L = ["# BLK-UNI-07 — incerteza do modelo e faixas de segurança: resultado", "",
         f"Protocolo `protocolo_uni07.md` (SHA-256 `{hashes['protocolo_uni07.md'][:16]}…`). Rodado uma vez. Calendário 2026: {pc(cal)}.",
         f"Sanidade: 39 de treino, 18 de teste, todas com master; M0 no teste: erro típico {100 * san[0]:.1f}%, viés {100 * san[1]:+.1f}% (UNI-02: 21,5% e +0,7%).",
         f"Premissas do simulador (config.py): ticket R$ {cfg.SIM_MENSALIDADE_BALCAO}, balcão {cfg.SIM_SHARE_BALCAO:.0%}, agregador a {cfg.SIM_TICKET_AGREGADOR_FATOR:.0%}, "
         f"aluguel R$ {cfg.SIM_ALUGUEL_MES:,.0f}, obra R$ {cfg.SIM_CAPEX_DEFAULT:,.0f}, custo do estúdio R$ {cfg.SIM_CUSTO_STUDIO:,.0f}/mês; rampa {c5.RAMPA_OBS}.", "",
         "## 1. Quanto o modelo erra (fora da amostra)", "",
         "| modelo | amostra | N | desvio-padrão do erro (log) | erro típico | viés (mediana) | p10 do erro | p90 do erro |", "|---|---|---|---|---|---|---|---|"]
    for nome, D in E.items():
        for g, h_ in (("treino (LOO)", D[D.grupo == "treino"]), ("teste (fora do tempo)", D[D.grupo == "teste"]), ("juntos", D)):
            r_ = h_.residuo
            L.append(f"| {nome} | {g} | {len(r_)} | {r_.std(ddof=1):.3f} | {100 * np.median(np.abs(np.exp(r_) - 1)):.0f}% | {pc(r_.median())} | "
                     f"{pc(r_.quantile(0.10))} | {pc(r_.quantile(0.90))} |")

    # ---- faixas e cobertura (v2)
    r = ev.residuo.to_numpy(); n = len(r); gte = (ev.grupo == "teste").to_numpy(); nte = int(gte.sum())
    rtr = r[~gte]
    L += ["", "## 2. Faixas e cobertura (v2)", "",
          "| construção | faixa | limites em torno da previsão | cobertura no teste | IC 90% | cobertura total (57) | IC 90% |", "|---|---|---|---|---|---|---|"]
    cob = {}
    for faixa, (ql, qh) in (("80%", (0.10, 0.90)), ("50%", (0.25, 0.75))):
        lo_a, hi_a = np.quantile(rtr, [ql, qh])
        ka = int(((r[gte] >= lo_a) & (r[gte] <= hi_a)).sum())
        dentro = np.array([(r[i] >= np.quantile(np.delete(r, i), ql)) & (r[i] <= np.quantile(np.delete(r, i), qh)) for i in range(n)])
        kb_te, kb = int(dentro[gte].sum()), int(dentro.sum())
        lo_b, hi_b = np.quantile(r, [ql, qh])
        cob[faixa] = dict(A=(ka / nte, lo_a, hi_a), B_te=kb_te / nte, B_tot=(kb / n, lo_b, hi_b))
        ia, ib, it = binom_ic(ka, nte), binom_ic(kb_te, nte), binom_ic(kb, n)
        L.append(f"| (A) só treino — teste limpo | {faixa} | {pc(lo_a)} a {pc(hi_a)} | {100 * ka / nte:.0f}% ({ka}/{nte}) | [{100 * ia[0]:.0f}; {100 * ia[1]:.0f}] | – | – |")
        L.append(f"| (B) conjunta, sem a própria (não é teste limpo) | {faixa} | {pc(lo_b)} a {pc(hi_b)} | {100 * kb_te / nte:.0f}% ({kb_te}/{nte}) | [{100 * ib[0]:.0f}; {100 * ib[1]:.0f}] | "
                 f"{100 * kb / n:.0f}% ({kb}/{n}) | [{100 * it[0]:.0f}; {100 * it[1]:.0f}] |")
    ca, (cbt, lo_b80, hi_b80) = cob["80%"]["A"][0], cob["80%"]["B_tot"]
    if 0.70 <= ca <= 0.90:
        adot, conj, aviso = "A", rtr, ""
    elif 0.70 <= cbt <= 0.90:
        adot, conj, aviso = "B", r, " (aviso: não há teste limpo para a (B))"
    else:
        adot, conj = "B", r
        aviso = f" (aviso: cobertura {'abaixo' if cbt < 0.70 else 'acima'} da prometida)"
    lo80, hi80 = np.quantile(conj, [0.10, 0.90]); med = np.median(conj)
    L += ["", f"**Faixa adotada (regra do §3): ({adot})**, de {pc(lo80)} a {pc(hi80)} em torno da previsão; p50 {pc(med)}{aviso}."]

    # ---- heterogeneidade (regra literal)
    L += ["", "## 3. O erro é igual para todas as unidades? (mediana de |erro|, v2)", "", "| divisão | grupo | N | erro típico |", "|---|---|---|---|"]
    ev["terco_prev"] = pd.qcut(ev.previsto_2026_log, 3, labels=["menor", "médio", "maior"])
    ev["abs_pct"] = np.abs(np.exp(ev.residuo) - 1)
    segmentar = []
    for col, rot, criterio in (("fonte_m2", "metragem", True), ("terco_prev", "faturamento previsto", True), ("uf_grupo", "estado", True),
                               ("studios", "estúdio", True), ("grupo", "treino × teste (fora do tempo; não é critério)", False)):
        g = ev.groupby(col, observed=True).abs_pct.agg(["size", "median"])
        for k, row in g.iterrows():
            L.append(f"| {rot} | {k} | {int(row['size'])} | {100 * row['median']:.0f}% |")
        if criterio and (g["size"] >= 10).all() and g["median"].max() / g["median"].min() >= 1.5:
            segmentar.append(rot)
    L += ["", f"Faixa por grupo (todos os grupos com ≥ 10 e razão ≥ 1,5): {', '.join(segmentar) if segmentar else 'nenhuma divisão dispara — faixa única'}."
          + (" Levado à decisão do Felipe; a §4 usa a faixa única." if segmentar else "")]

    # ---- faixas de seguranca dos indicadores
    rows = []
    tipica = float(np.exp(np.median(ev.previsto_2026_log)))
    alvo = [("unidade típica (mediana das previsões, nível 2026)", None, tipica, None, 0.0)] + \
           [(ev.nome[u], u, float(np.exp(ev.previsto_log[u])), float(np.exp(ev.real_log[u])), float(ev.studios[u])) for u in ev.index[gte]]
    for nome_u, u, fat_p, fat_real, est in alvo:
        cj = conj if u is None or adot == "A" else np.delete(r, ev.index.get_loc(u))  # sem a propria (so' importa na B)
        ql, qm, qh = np.quantile(cj, [0.10, 0.50, 0.90])
        cen = {k: sim(fat_p * np.exp(q), est == 1.0) for k, q in (("p10", ql), ("p50", qm), ("p90", qh))}
        via = np.mean([sim(fat_p * np.exp(e_), est == 1.0)["viavel"] for e_ in cj])
        via_tr = np.mean([sim(fat_p * np.exp(e_), est == 1.0)["viavel"] for e_ in rtr])  # conferencia sem vazamento
        real = sim(fat_real, est == 1.0) if fat_real else None
        rows.append(dict(unidade=nome_u, estudio=est, **{f"{k}_{c}": v for k, s in cen.items() for c, v in
                                                        (("faturamento", fat_p * np.exp({'p10': ql, 'p50': qm, 'p90': qh}[k])), ("alunos", s["alunos"]),
                                                         ("margem", s["margem"]), ("payback", s["payback"]))},
                         chance_viavel=via, chance_viavel_treino=via_tr, faturamento_real=fat_real,
                         payback_real=real["payback"] if real else np.nan, viavel_real=bool(real["viavel"]) if real else np.nan))
    FI = pd.DataFrame(rows)
    FI.to_csv(AQUI / "faixas_indicadores.csv", sep=";", encoding="utf-8-sig", index=False)
    fm = lambda v: f"{v / 1000:,.0f} mil"
    pb = lambda v: ">60" if v >= 61 else f"{v:.0f}"
    L += ["", "## 4. Faixas de segurança dos indicadores (custos-padrão, rampa observada; estúdio com custo de 1 estúdio)", "",
          "| unidade | estúdio | faturamento maduro p10 · p50 · p90 | alunos p10 · p50 · p90 | margem EBITDA p10 · p50 · p90 | payback (meses) p10 · p50 · p90 | chance de ser viável | real no simulador: faturamento / payback |",
          "|---|---|---|---|---|---|---|---|"]
    for _, w in FI.iterrows():
        L.append(f"| {w.unidade} | {'sim' if w.estudio == 1 else 'não'} | {fm(w.p10_faturamento)} · **{fm(w.p50_faturamento)}** · {fm(w.p90_faturamento)} | "
                 f"{w.p10_alunos:,.0f} · {w.p50_alunos:,.0f} · {w.p90_alunos:,.0f} | {100 * w.p10_margem:.0f}% · {100 * w.p50_margem:.0f}% · {100 * w.p90_margem:.0f}% | "
                 f"{pb(w.p10_payback)} · {pb(w.p50_payback)} · {pb(w.p90_payback)} | **{100 * w.chance_viavel:.0f}%** | "
                 + (f"{fm(w.faturamento_real)} / {pb(w.payback_real)}" if pd.notna(w.faturamento_real) else "–") + " |")
    tt = FI.iloc[1:].copy(); vr = tt.viavel_real.astype(bool).astype(float); ch = tt.chance_viavel_treino
    brier, pbar = np.mean((ch - vr) ** 2), vr.mean()
    L += ["", f"**Conferência da chance (sem vazamento: só os 39 erros do treino; 'viável' = seria viável no simulador com o faturamento real e custos-padrão):** "
          f"das {int((ch >= 0.5).sum())} unidades com chance ≥ 50%, {int(((ch >= 0.5) & (vr == 1)).sum())} seriam viáveis; das {int((ch < 0.5).sum())} com chance < 50%, "
          f"{int(((ch < 0.5) & (vr == 1)).sum())}. Brier {brier:.3f} contra {pbar * (1 - pbar):.3f} da taxa-base ({vr.sum():.0f}/{len(vr)} viáveis).", "",
          "## 5. Depois de abrir (referência do UNI-03; outra grandeza)", "",
          f"- Antes de abrir (v2, faixa adotada de 80%): faturamento maduro de {pc(lo80)} a {pc(hi80)} em torno da previsão.",
          "- UNI-03 mede outra coisa: o erro dos **alunos** maduros (meses 11–13) projetados do mês k. No mês 3: −20% a +23% (p10–p90 da exploração), "
          "com cobertura de 77% na confirmação; no mês 6: −13% a +11%, com cobertura de 64% (abaixo do nominal). "
          "Leitura: depois de abrir, os 3 primeiros meses dão uma referência bem mais estreita sobre o volume; a comparação direta com a faixa de faturamento não é exata.",
          "", "## Insumos (SHA-256)", ""] + [f"- `{k}`: `{v}`" for k, v in hashes.items()]
    (AQUI / "resultado_uni07.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
