# -*- coding: utf-8 -*-
"""Passos 0-5 do protocolo_manaus_volume.md, v1.1 (emenda §11, depois da revisao adversarial; congelado antes de rodar).
Le atributos_pino.json (01). So' grava nesta pasta. .venv, PYTHONPATH=src."""
import dataclasses
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
POI = UNI.parent / "poi"
ALVO = 3500.0
MIX_PADRAO, MIX_CEN = 0.43, (0.30, 0.55)
PRECO_STUDIO, PCT_STUDIO = 272.0, 0.05


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


u7 = mod("u7", UNI / "uni07" / "01_incerteza.py")
ex, alav, X_ = u7.ex, u7.alav, u7.X_
mc = mod("mc", UNI / "simulacoes" / "manaus_premissas_corrigidas.py")


def renda_dom(d):
    return (pd.to_numeric(d.iso_renda_pc__carro_10, errors="coerce") * pd.to_numeric(d.iso_pop__carro_10, errors="coerce")
            / pd.to_numeric(d.iso_domicilios__carro_10, errors="coerce"))


def fat_mix(al, mix):
    """Faturamento maduro a R$ 167 + plano de estudio (5% da base a R$ 272) com fatia de agregador `mix`."""
    s = 1.0 - mix
    p = dataclasses.replace(mc.premissas(al), share_balcao=s, ticket_cheio=167.0 + (PRECO_STUDIO - 167.0) * PCT_STUDIO / s)
    return p.faturamento(al, com_anuidade=True)


def l_pagantes(f, ini="2025-01", fim="2025-12", mv_min=12, min_meses=3):
    """Mesmo recorte de ex.desfechos, desfecho = media mensal de log(pagantes)."""
    g = f[f.valido & (f.competencia >= ini) & (f.competencia <= fim) & (f.mv >= mv_min) & (f.pagantes > 0)].copy()
    n = g.groupby("unidade_id").size(); g = g[g.unidade_id.isin(n[n >= min_meses].index)]
    return np.log(g.pagantes.astype(float)).groupby(g.unidade_id).mean().rename("l_pag")


def base_treino(f, d):
    A = alav.atributos_ext(d)
    A["l_renda_dom"] = np.log(renda_dom(d))
    mid = pd.read_csv(UNI / "alavancas" / "master_id_cadastro.csv", sep=";", dtype=str)
    A["master_id"] = d.cod_cadastro.map(mid.assign(c=mid.cod_cadastro.str.zfill(2)).set_index("c").master_id).reindex(A.index)
    Y25 = ex.desfechos(f, "2025-01", "2025-12")
    tr = A.join(Y25, how="inner").dropna(subset=["l_fat", "l_ativos", "l_m2", "l_renda", "l_pop", "frac_indep", "studios", "master_id", "l_renda_dom"])
    cont = tr.master_id.value_counts(); proprios = sorted(m for m, n in cont.items() if n >= 4 and m != "M1")
    for m in proprios:
        tr[f"mr_{m}"] = (tr.master_id == m).astype(float)
    tr["mr_outras"] = (~tr.master_id.isin(["M1"] + proprios)).astype(float)
    tr = tr.join(l_pagantes(f))
    return tr, [f"mr_{m}" for m in proprios] + ["mr_outras"]


def main():
    at = json.loads((AQUI / "atributos_pino.json").read_text(encoding="utf-8"))
    c10 = at["carro_10"]
    f, d = ex.carregar()
    tr, DUM = base_treino(f, d)
    assert "mr_M3" in DUM, DUM
    V2 = ["l_m2", "l_renda_dom", "l_pop"] + DUM + ["studios"]
    y = tr.l_ativos.to_numpy(float)
    b, e, h, _ = ex.ols(y, X_(tr, V2))
    b_m2 = float(b[1 + V2.index("l_m2")])
    loo = e / (1 - h); ql, qh = np.quantile(loo, [.1, .9])
    L = ["# Manaus — o volume de ~2.900 alunos: evidências (protocolo v1.1, congelado antes de rodar)", ""]
    sint = {}

    def prev(row, coef=b, cols=V2):
        return float(np.asarray(X_(pd.DataFrame([row]), cols) @ coef).ravel()[0])

    # ---------- Passo 0 / 0b
    trunc = bool(c10["truncada"])
    rd_iso = c10["renda_pc"] * c10["pop"] / c10["domicilios"]
    iso_row = {"l_m2": np.log(2000.0), "l_renda_dom": np.log(rd_iso), "l_pop": np.log(c10["pop"]), "studios": 1.0, **{c: 0.0 for c in DUM}}
    circ_row = {**iso_row, "l_renda_dom": np.log(3511.0), "l_pop": np.log(525_532.0)}
    row_c = circ_row if trunc else iso_row
    MAST = {"M3 (master de RJ/SP)": {"mr_M3": 1.0}, "outras": {"mr_outras": 1.0}, "M1 (referência DF/GO)": {},
            "média da rede": {c: float(tr[c].mean()) for c in DUM}}
    repro = float(np.exp(prev({**circ_row, **MAST["M3 (master de RJ/SP)"]})))
    assert abs(repro - 2884) <= 1.5, f"reproducao do numero congelado falhou: {repro:.1f}"
    L += ["## Passo 0 — número central", "",
          f"Treino: {len(tr)} unidades. Reprodução do número congelado (M3, círculo): {repro:,.0f} ✓.",
          f"Isócrona real (10 min de carro): área {c10['area_km2']:.1f} km², população {c10['pop']:,.0f}, renda per capita R$ {c10['renda_pc']:,.0f}, "
          f"renda domiciliar (proxy da v2) R$ {rd_iso:,.0f}, truncada: {'sim' if trunc else 'não'} → "
          f"{'fica o círculo' if trunc else 'substitui o círculo no central'}.", "",
          "| master | círculo 5 km | isócrona real | faixa 80% (central) |", "|---|---|---|---|"]
    centrais = {}
    for rot, dm in MAST.items():
        pc, pi = prev({**circ_row, **dm}), prev({**iso_row, **dm})
        pcen = pc if trunc else pi
        centrais[rot] = float(np.exp(pcen))
        L.append(f"| {rot} | {np.exp(pc):,.0f} | {np.exp(pi):,.0f} | {np.exp(pcen + ql):,.0f} a {np.exp(pcen + qh):,.0f} |")
    CENTRAL = centrais["M3 (master de RJ/SP)"]
    L += ["", f"**Central direto (M3): {CENTRAL:,.0f} ativos.**", ""]

    # ---------- Passo 0c: balcao
    tp = tr.dropna(subset=["l_pag"])
    bp = np.linalg.lstsq(X_(tp, V2), tp.l_pag.to_numpy(float), rcond=None)[0]
    bal = float(np.exp(prev({**row_c, **MAST["M3 (master de RJ/SP)"]}, bp)))
    bal_media = float(np.exp(prev({**row_c, **MAST["média da rede"]}, bp)))
    agr_m3 = tr.loc[tr.mr_M3 == 1, "agr"].median(); agr_rede = tr.agr.median()
    comp = {m: bal / (1 - m) for m in (MIX_CEN[0], MIX_PADRAO, MIX_CEN[1])}
    L += ["## Passo 0c — central por componentes (balcão ÷ (1 − mix))", "",
          f"v2 em log(balcão), {len(tp)} unidades: coeficiente de M3 {bp[1 + V2.index('mr_M3')]:+.3f} (em ativos: {b[1 + V2.index('mr_M3')]:+.3f}). "
          f"Agregador mediano nas unidades M3: {100 * agr_m3:.0f}% (rede {100 * agr_rede:.0f}%).",
          f"Balcão previsto para Manaus: **{bal:,.0f}** (M3); {bal_media:,.0f} (master média).",
          f"Central por componentes: mix 30% → {comp[0.30]:,.0f}; **mix 43% (padrão 'outros') → {comp[0.43]:,.0f}**; mix 55% → {comp[0.55]:,.0f} ativos.", ""]

    # ---------- Passo 1: ativos ajustados ao porte
    g = f[f.valido & (f.competencia >= "2025-01") & (f.competencia <= "2026-08") & (f.mv >= 12)]
    n = g.groupby("unidade_id").size(); g = g[g.unidade_id.isin(n[n >= 3].index)]
    U = g.groupby("unidade_id")[["ativos", "pagantes", "agregadores"]].mean()
    U["nome"], U["uf"] = d.nome.reindex(U.index), d.uf.reindex(U.index)
    U["renda_dom"] = renda_dom(d).reindex(U.index); U["renda_pc"] = pd.to_numeric(d.iso_renda_pc__carro_10, errors="coerce").reindex(U.index)
    U["m2"] = pd.to_numeric(d.tam_metragem_m2, errors="coerce").reindex(U.index)
    U["ativos_aj"] = U.ativos * (2000.0 / U.m2) ** b_m2
    dif = ((U.ativos - (U.pagantes + U.agregadores)).abs() / U.ativos).median()
    Um = U.dropna(subset=["ativos_aj", "renda_dom"])

    def regra(sub):
        k = int((sub.ativos_aj >= ALVO).sum())
        return ("maior" if k >= 2 else ("teto" if k == 0 else "inconclusivo")), k

    def passo1(col, man):
        c_lo, c_hi = Um[col].quantile(1 / 3), Um[col].quantile(2 / 3)
        lo, hi = Um[Um[col] <= c_lo], Um[Um[col] >= c_hi]
        if man > c_lo:
            return "inconclusivo (Manaus fora do terço inferior)", c_lo, lo, hi, None, None
        (vlo, klo), (vhi, khi) = regra(lo), regra(hi)
        v = "teto geral da rede" if (vlo == "teto" and vhi == "teto") else vlo
        return v, c_lo, lo, hi, (vlo, klo), (vhi, khi)
    v1, c_lo, lo, hi, rlo, rhi = passo1("renda_dom", rd_iso)
    v1pc = passo1("renda_pc", c10["renda_pc"])[0]
    sint["p1"] = v1
    L += ["## Passo 1 — ativos ajustados ao porte (2.000 m²)", "",
          f"Universo: {len(U)} maduras (2025-01 a 2026-08); com metragem oficial e renda: {len(Um)}. Ajuste: ativos × (2.000/m²)^{b_m2:.3f}. "
          f"Pré-checagem |ativos − (balcão + agregador)| / ativos: mediana {100 * dif:.1f}%{' (acima de 5%, declarado)' if dif > .05 else ''}.",
          f"Ativos ajustados no universo: mediana {Um.ativos_aj.median():,.0f}; p75 {Um.ativos_aj.quantile(.75):,.0f}; p90 {Um.ativos_aj.quantile(.9):,.0f}; "
          f"máximo {Um.ativos_aj.max():,.0f}; ≥ {ALVO:,.0f}: {int((Um.ativos_aj >= ALVO).sum())} de {len(Um)}.",
          f"Renda baixa = domiciliar ≤ R$ {c_lo:,.0f} (Manaus R$ {rd_iso:,.0f}), n = {len(lo)}: " + (f"≥ {ALVO:,.0f} ajustado: {rlo[1]} → {rlo[0]}. " if rlo else "") +
          (f"Controle negativo (terço superior, n = {len(hi)}): {rhi[1]} → {rhi[0]}. " if rhi else "") + f"**Veredito: {v1.upper()}.**",
          f"Sensibilidade com renda per capita: {v1pc}.", "",
          "| praça de renda baixa | UF | m² | renda dom. | ativos | ativos ajust. 2.000 m² | balcão | agregador |", "|---|---|---|---|---|---|---|---|"]
    for u, r in lo.sort_values("ativos_aj", ascending=False).iterrows():
        L.append(f"| {r.nome} | {r.uf} | {r.m2:,.0f} | R$ {r.renda_dom:,.0f} | {r.ativos:,.0f} | {r.ativos_aj:,.0f} | {r.pagantes:,.0f} | {r.agregadores:,.0f} |")
    L += ["", "10 maiores em ativos ajustados ao porte (universo todo):", "", "| unidade | UF | m² | renda dom. | ativos | ajust. | balcão | agregador |", "|---|---|---|---|---|---|---|---|"]
    for u, r in Um.sort_values("ativos_aj", ascending=False).head(10).iterrows():
        L.append(f"| {r.nome} | {r.uf} | {r.m2:,.0f} | R$ {r.renda_dom:,.0f} | {r.ativos:,.0f} | {r.ativos_aj:,.0f} | {r.pagantes:,.0f} | {r.agregadores:,.0f} |")
    L += ["", f"Balcão (descritivo): mediana {U.pagantes.median():,.0f}; p90 {U.pagantes.quantile(.9):,.0f}; máximo {U.pagantes.max():,.0f}.", ""]

    # ---------- Passo 2: Smart Fit
    poi = mod("poi", POI / "06_teste_poi.py")
    sf, Xb, _conc, _D, k = poi.amostra_S2()
    k = k.drop_duplicates(["Sigla", "Data_Ref"])
    k25 = k[(k.Data_Ref >= "2025-01-01") & (k.Data_Ref <= "2025-12-31")]
    ym = k25.groupby("Sigla")["Alunos Totais SF"].agg(["median", "count"])
    cols = ["ponto_id", "tipo", "cenario", "metro", "pop", "renda_pc", "domicilios", "truncada"]
    import pyarrow.parquet as pq
    atr = pd.concat([pd.read_parquet(p, columns=[c for c in cols if c in pq.read_schema(p).names])
                     for p in sorted((poi.ISO / "atributos_v2").glob("*.parquet"))])
    assert "truncada" in atr.columns, "atributos_v2 sem coluna truncada: filtro do §11 impossivel"
    atr = atr[atr.tipo.eq("academia") & atr.cenario.eq("carro_10min")].drop_duplicates("ponto_id").set_index("ponto_id")
    S = pd.concat([sf[["sigla", "concorrente_id"]].reset_index(drop=True), Xb[[c for c in ("idade_12_23", "franquia") if c in Xb]].reset_index(drop=True)], axis=1)
    for c in ("metro", "pop", "renda_pc", "domicilios", "truncada"):
        S[c] = S.concorrente_id.map(atr[c]) if c in atr else np.nan
    S["y"] = np.log(S.sigla.map(ym["median"]).astype(float)); S["n25"] = S.sigla.map(ym["count"])
    S["log_renda_dom"] = np.log(S["renda_pc"] * S["pop"] / S["domicilios"]); S["log_pop"] = np.log(S["pop"])
    S = S[S.metro.notna() & np.isfinite(S.y) & (S.n25 >= 6) & np.isfinite(S.log_renda_dom) & np.isfinite(S.log_pop)].reset_index(drop=True)
    S["metro"] = S.metro.astype(int)
    n44_antes = int((S.metro == 44).sum())
    S = S[~S.truncada.fillna(False).astype(bool)].reset_index(drop=True)
    n44 = int((S.metro == 44).sum())
    wU = d.iso_metro.reindex(tr.index).dropna().astype(int).value_counts()
    wU = wU[wU.index.isin(S.metro.unique()) & (wU.index != 44)]
    CTRL = ["log_renda_dom", "log_pop"] + [c for c in ("franquia", "idade_12_23") if c in S and S[c].nunique() > 1]
    metros = sorted(S.metro.unique())

    def r_de(Sx, ctrl):
        M = np.column_stack([(Sx.metro.to_numpy() == m).astype(float) for m in metros] + [Sx[c].to_numpy(float) for c in ctrl])
        if np.linalg.matrix_rank(M) < M.shape[1]:
            return None
        coef = np.linalg.lstsq(M, Sx.y.to_numpy(float), rcond=None)[0]
        ef = dict(zip(metros, coef[:len(metros)]))
        return float(np.exp(ef[44] - sum(ef[m] * w for m, w in wU.items()) / wU.sum()))
    L += ["## Passo 2 — efeito praça pela Smart Fit", "",
          f"Amostra: {len(S)} Smart Fit maduras, com isócrona não truncada e ≥ 6 meses com valor em 2025. Manaus (caixa de ±12 km do pino, metrô 44): "
          f"{n44_antes} antes do filtro de truncamento → **{n44}** depois. Metrôs Ultra cobertos: {len(wU)} ({100 * wU.sum() / len(tr):.0f}% das {len(tr)} de treino).",
          f"Alunos Smart Fit, mediana 2025: Manaus {np.exp(S[S.metro == 44].y.median()) if n44 else float('nan'):,.0f}; "
          f"metrôs das Ultra {np.exp(S[S.metro.isin(wU.index)].y.median()):,.0f}; todas {np.exp(S.y.median()):,.0f}. Controles (ii): {', '.join(CTRL)}.", ""]
    if n44 < 5:
        v2r = "inconclusivo"; L.append(f"Portão (≥ 5 em Manaus): {n44} → **INCONCLUSIVO**.")
    else:
        rng = np.random.default_rng(42); grupos = {m: S.index[S.metro == m].to_numpy() for m in metros}
        res = {}
        for rot, ctrl in (("(i) sem controles", []), ("(ii) com renda domiciliar, população, franquia e idade", CTRL)):
            r0 = r_de(S, ctrl); bs, desc = [], 0
            for _ in range(2000):
                idx = np.concatenate([rng.choice(ix, len(ix), replace=True) for ix in grupos.values()])
                r = r_de(S.loc[idx].reset_index(drop=True), ctrl)
                if r is None:
                    desc += 1
                else:
                    bs.append(r)
            lo_r, hi_r = np.quantile(bs, [.05, .95]); res[rot] = (r0, lo_r, hi_r)
            L.append(f"- {rot}: r = **{r0:.2f}** (IC90 {lo_r:.2f} a {hi_r:.2f}; {len(bs)} reamostras válidas, {desc} descartadas por posto).")
        r0, lo_r, hi_r = res["(ii) com renda domiciliar, população, franquia e idade"]
        med = centrais["média da rede"]
        v2r = "maior" if med * lo_r > CENTRAL else ("menor" if med * hi_r < CENTRAL else "neutro")
        L.append(f"Número alternativo = v2 com master média ({med:,.0f}) × r(ii) = **{med * r0:,.0f} ativos** (IC90 {med * lo_r:,.0f} a {med * hi_r:,.0f}) "
                 f"contra o central {CENTRAL:,.0f} → **{v2r.upper()}**.")
    sint["p2"] = v2r
    L.append("")

    # ---------- Passo 3 (so' cenario)
    whm = 1000 * c10["wh_n_conc_c10"] / c10["pop"]; tpm = 1000 * c10["tp_n_conc_c10"] / c10["pop"]
    whu = (1000 * d.wh_n_conc_c10 / d.iso_pop__carro_10).reindex(U.index).dropna()
    tpu = (1000 * d.tp_n_conc_c10 / d.iso_pop__carro_10).reindex(U.index).dropna()
    mix = 0.30 if whm <= whu.quantile(.25) else (0.55 if whm >= whu.quantile(.75) else 0.43)
    L += ["## Passo 3 — mercado de agregador na praça (só indica o cenário de mix)", "",
          f"Wellhub (musculação, sem Ultra e estúdios) por mil hab. na isócrona de 10 min: Manaus **{whm:.3f}** ({c10['wh_n_conc_c10']} academias); "
          f"rede p25 {whu.quantile(.25):.3f} · mediana {whu.median():.3f} · p75 {whu.quantile(.75):.3f} (percentil de Manaus ≈ {100 * float((whu < whm).mean()):.0f}). "
          f"→ cenário de mix mais plausível: **{100 * mix:.0f}%** → {bal / (1 - mix):,.0f} ativos pelo central por componentes.",
          f"TotalPass (à parte): Manaus {tpm:.3f} ({c10['tp_n_conc_c10']}); rede mediana {tpu.median():.3f}; percentil ≈ {100 * float((tpu < tpm).mean()):.0f}.",
          "Faturamento maduro a R$ 167 + plano de estúdio: " + "; ".join(
              f"{rot} {al:,.0f} ativos, mix {100 * mx:.0f}% → R$ {fat_mix(al, mx) / 1000:,.0f} mil"
              for rot, al, mx in (("central direto", CENTRAL, MIX_PADRAO), ("componentes", comp[MIX_PADRAO], MIX_PADRAO), ("componentes/cenário", bal / (1 - mix), mix))) + ".", ""]

    # ---------- Passo 4
    fi = c10["n_independente_agregador"] / c10["n_academias"] if c10["n_academias"] > 0 else np.nan
    p10, p90 = tr.frac_indep.quantile([.1, .9])
    L += ["## Passo 4 — hipótese do diretor (só sensibilidade)", "",
          f"Fração de independentes: Manaus {fi:.2f} ({c10['n_independente_agregador']:.0f} de {c10['n_academias']:.0f}); treino p10–p90 {p10:.2f}–{p90:.2f}."]
    if not (p10 <= fi <= p90):
        L.append("Fora da faixa do treino → extrapolação; sem número.")
    else:
        T = tr.copy()
        zm, sm, zf, sf_ = T.l_m2.mean(), T.l_m2.std(), T.frac_indep.mean(), T.frac_indep.std()
        T["int"] = ((T.l_m2 - zm) / sm) * ((T.frac_indep - zf) / sf_)
        V4 = V2 + ["frac_indep", "int"]
        b4 = np.linalg.lstsq(X_(T, V4), y, rcond=None)[0]
        row4 = {**row_c, **MAST["M3 (master de RJ/SP)"], "frac_indep": fi, "int": ((np.log(2000.0) - zm) / sm) * ((fi - zf) / sf_)}
        L.append(f"Dentro da faixa. v2 + hipótese do diretor (M3): **{np.exp(prev(row4, b4, V4)):,.0f} ativos** (ao lado do central {CENTRAL:,.0f}; não substitui).")
    L.append("")

    # ---------- Passo 5
    cv = pd.read_csv(UNI / "uni03" / "curva_uni03.csv", sep=";", encoding="utf-8-sig")
    cv = cv[cv.serie == "ativos"].set_index("k").p50
    L += ["## Passo 5 — compromisso depois de abrir", "",
          f"Esperado com o central {CENTRAL:,.0f}: mês 1 ~{CENTRAL * cv[1]:,.0f} (só alerta: cobertura 59%); mês 3 ~{CENTRAL * cv[3]:,.0f}; mês 6 ~{CENTRAL * cv[6]:,.0f}.",
          f"Gatilho do mês 3: revisar para CIMA se fechar com ≥ {1.25 * CENTRAL * cv[3]:,.0f} ativos (projeção ≥ {1.25 * CENTRAL:,.0f}); "
          f"para BAIXO se ≤ {0.81 * CENTRAL * cv[3]:,.0f} (projeção ≤ {0.81 * CENTRAL:,.0f}).", ""]

    # ---------- Sintese (§11)
    p1_teto = sint["p1"] in ("teto", "teto geral da rede")
    if sint["p2"] == "maior" or sint["p1"] == "maior":
        s = "OS DADOS SUSTENTAM NÚMERO MAIOR"
    elif p1_teto and sint["p2"] != "maior":
        s = f"SEM EVIDÊNCIA DE {ALVO:,.0f} AJUSTADO AO PORTE; central = {CENTRAL:,.0f}"
    elif sint["p2"] == "menor":
        s = "OS DADOS APONTAM ABAIXO DO CENTRAL"
    else:
        s = f"MANTÉM O CENTRAL ({CENTRAL:,.0f}) com a faixa e o gatilho do mês 3"
    L += ["## Síntese (regra do §11, fixada antes)", "", f"Passo 1: {sint['p1']}; Passo 2: {sint['p2']}. → **{s}**.", "",
          "Ressalva: nas unidades novas com estúdio, o teto da faixa furou em 4 de 18 (BLK-UNI-08); o risco de subestimar existe e não é previsível antes de abrir.", ""]
    (AQUI / "resultado_manaus_volume_evidencias.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
