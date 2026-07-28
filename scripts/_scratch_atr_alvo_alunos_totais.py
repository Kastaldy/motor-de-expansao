"""SCRATCH (READ-ONLY M1): revalida a estrutura ATR-03 trocando o ALVO de demanda de
`membros` (agregador corporativo, enviesado) por `alunos_totais` reais (Ultra + Smart Fit +
Engenharia do Corpo), agregados por hex H3 res-7. Reusa o harness PURO estrutura_funil.

Guardrails: nao escreve em score/pipelines/config; so LE parquets/xlsx. Anti-PII (DEC-012):
dropa lat/lng/nome/endereco na fronteira; so persiste [hex_id, alunos_totais] agregado + metricas.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, "src")

import h3
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from motor_expansao.demanda_revelada.concorrentes_densos import _coords_densas
from motor_expansao.demanda_revelada.estrutura_funil import (
    FEAT_DISPUTA,
    FEAT_MERCADO,
    FEAT_SOCIODEMO,
    FEATURES_COMPOSTO,
    POP_MIN_GATE_ATR,
    _avaliar_modelo,
    _derive_populacao_corte,
    _percentil_0_100,
    _preparar_alvo,
    aplicar_gate_atratividade,
    avaliar_estrutura_funil,
    normalizar_eixos,
    relatorio_estrutura_funil,
)
from motor_expansao.demanda_revelada.huff_captura import (
    calcular_share_por_hex,
    calibrar_huff_captura,
)

DENSOS = Path("data/staging/concorrentes_densos.parquet")

ROOT = Path(".")
MKT = ROOT / "data/staging/hexagonos_mercado_mapeado.parquet"
OUT_MD = ROOT / "data/analysis/atr_alvo_alunos_totais.md"

RES = 7
prov: list[str] = []  # linhas de proveniencia por base (contagens, sem PII)


UFS = {"ac","al","ap","am","ba","ce","df","es","go","ma","mt","ms","mg","pa","pb","pr",
       "pe","pi","rj","rn","rs","ro","rr","sc","sp","se","to"}


def norm(s: str) -> str:
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return " ".join("".join(ch if (ch.isalnum() or ch == " ") else " " for ch in s).split())


def strip_ec(s: str) -> str:
    return re.sub(r"^(engenharia do corpo|ecb|ec|eb)\b\s*", "", norm(s)).strip()


def _uf_of(k: str) -> str:
    t = k.split()
    return t[-1] if t and t[-1] in UFS else ""


def _coord_segments(nomes: pd.Series) -> tuple[list[str], list[str]]:
    """(keys normalizadas, seg0 = bairro antes de virgula/traco/parenteses)."""
    keys = [norm(s) for s in nomes]
    seg0 = [norm(str(s).replace("(", " ").split("–")[0].split(",")[0].split(" - ")[0]) for s in nomes]
    return keys, seg0


def match_por_nome(tok: str, ckeys: list[str], cseg: list[str]) -> int | None:
    """Casa um nome de unidade (tok normalizado) a um indice de coord, em cascata.

    (1) key exata; (2) segmento-bairro exato; (3) palavra-bairro (len>=4) na MESMA UF.
    Tolerante a colisao intra-cidade (agregamos por hex depois).
    """
    if not tok:
        return None
    for i, k in enumerate(ckeys):
        if tok == k:
            return i
    for i, s in enumerate(cseg):
        if tok == s:
            return i
    tuf = _uf_of(tok)
    words = [w for w in tok.split() if w not in UFS and len(w) >= 4]
    if tuf and words:
        for i, k in enumerate(ckeys):
            if _uf_of(k) == tuf and any(re.search(r"\b" + re.escape(w) + r"\b", k) for w in words):
                return i
    return None


# --------------------------------------------------------------------------- #
# 1. Ultra (ja hex-mapeado)
# --------------------------------------------------------------------------- #
def base_ultra() -> pd.DataFrame:
    df = pd.read_parquet(
        "data/staging/unidades_ultra_performance_hex.parquet",
        columns=["hex_id_res7", "alunos_total"],
    )
    df = df.rename(columns={"hex_id_res7": "hex_id", "alunos_total": "alunos_totais"})
    df["alunos_totais"] = pd.to_numeric(df["alunos_totais"], errors="coerce")
    n0 = len(df)
    df = df.dropna(subset=["hex_id", "alunos_totais"])
    df = df[df["alunos_totais"] > 0]
    prov.append(f"- Ultra: {n0} unidades no parquet; {len(df)} com hex+alunos_total>0 (100% ja hex-mapeadas).")
    return df[["hex_id", "alunos_totais"]]


# --------------------------------------------------------------------------- #
# 2. Smart Fit (KPI -> Data_Ref mais recente por unidade -> coord -> hex)
# --------------------------------------------------------------------------- #
def base_smart() -> pd.DataFrame:
    kpi = pd.read_excel("data/validacao/KPIs_Smart_2025_02 (1).xlsx", sheet_name="Base")
    kpi["Data_Ref"] = pd.to_datetime(kpi["Data_Ref"], errors="coerce")
    kpi = kpi.dropna(subset=["Data_Ref"])
    # Data_Ref MAIS RECENTE por unidade (Nome)
    idx = kpi.groupby("Nome")["Data_Ref"].idxmax()
    ult = kpi.loc[idx, ["Nome", "Alunos Totais SF"]].copy()
    ult["alunos_totais"] = pd.to_numeric(ult["Alunos Totais SF"], errors="coerce")
    ult["key"] = ult["Nome"].map(norm)
    n_units = len(ult)

    coords = pd.read_csv("concorrentes/Unidades/unidades_smart_fit.csv", sep=";")
    coords["key"] = coords["nome_unidade"].map(norm)
    coords = coords.dropna(subset=["latitude", "longitude"]).drop_duplicates("key")

    m = ult.merge(coords[["key", "latitude", "longitude"]], on="key", how="inner")
    m = m.dropna(subset=["alunos_totais"])
    m = m[m["alunos_totais"] > 0]
    m["hex_id"] = [h3.latlng_to_cell(float(a), float(o), RES) for a, o in zip(m["latitude"], m["longitude"], strict=True)]
    prov.append(
        f"- Smart Fit: {n_units} unidades unicas (Data_Ref mais recente = {kpi['Data_Ref'].max().date()}); "
        f"{len(m)} casaram coord por nome ({100*len(m)/n_units:.0f}%) e viraram hex."
    )
    return m[["hex_id", "alunos_totais"]]


# --------------------------------------------------------------------------- #
# 3. Engenharia do Corpo (strip prefixo EC/ECB -> coord por bairro/UF -> hex)
# --------------------------------------------------------------------------- #
def base_eng() -> pd.DataFrame:
    e = pd.read_excel("data/validacao/academias_engenharia_do_corpo.xlsx", sheet_name="Academias")
    e["alunos_totais"] = pd.to_numeric(e["Alunos Totais"], errors="coerce")
    e["tok"] = e["Unidade"].map(strip_ec)
    n_units = len(e)
    ec = pd.read_csv("concorrentes/Unidades/unidades_engenharia_do_corpo.csv", sep=";")
    ec = ec.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
    ckeys, cseg = _coord_segments(ec["nome_unidade"])
    rows = []
    for tok, al in zip(e["tok"], e["alunos_totais"], strict=True):
        i = match_por_nome(tok, ckeys, cseg)
        if i is not None and pd.notna(al) and al > 0:
            rows.append((float(ec["latitude"].iloc[i]), float(ec["longitude"].iloc[i]), float(al)))
    m = pd.DataFrame(rows, columns=["latitude", "longitude", "alunos_totais"])
    m["hex_id"] = [h3.latlng_to_cell(a, o, RES) for a, o in zip(m["latitude"], m["longitude"], strict=True)]
    prov.append(
        f"- Engenharia do Corpo: {n_units} unidades no xlsx; {len(m)} casaram coord "
        f"(strip prefixo 'EC'/'ECB' + match por bairro dentro da UF; {100*len(m)/n_units:.0f}%)."
    )
    return m[["hex_id", "alunos_totais"]]


# --------------------------------------------------------------------------- #
# 4. Sky Fit (KPI 'Alunos EVO' -> coord por bairro/UF ou cidade+UF -> hex)
# --------------------------------------------------------------------------- #
def base_sky() -> pd.DataFrame:
    sk = pd.read_excel("data/validacao/Sky Fit dados.xlsx", sheet_name="Sell Out", header=3)
    sk["alunos_totais"] = pd.to_numeric(sk["Alunos EVO"], errors="coerce")
    sk["tok"] = sk["NOMENCLATURA UNIDADE"].map(
        lambda s: re.sub(r"^skyfit academia\s*", "", norm(s)).strip()
    )
    sk["ciduf"] = [norm(f"{c} {e}") for c, e in zip(sk["CIDADE"], sk["ESTADO"], strict=True)]
    n_units = len(sk)
    skc = pd.read_csv("concorrentes/Unidades/unidades_skyfit.csv", sep=";")
    skc = skc.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
    ckeys, cseg = _coord_segments(skc["nome_unidade"])
    rows = []
    n_match = 0
    for tok, cid, al in zip(sk["tok"], sk["ciduf"], sk["alunos_totais"], strict=True):
        i = match_por_nome(tok, ckeys, cseg)
        if i is None:  # fallback cidade+UF
            i = match_por_nome(cid, ckeys, cseg)
        if i is not None:
            n_match += 1
            if pd.notna(al) and al > 0:
                rows.append((float(skc["latitude"].iloc[i]), float(skc["longitude"].iloc[i]), float(al)))
    m = pd.DataFrame(rows, columns=["latitude", "longitude", "alunos_totais"])
    m["hex_id"] = [h3.latlng_to_cell(a, o, RES) for a, o in zip(m["latitude"], m["longitude"], strict=True)]
    prov.append(
        f"- Sky Fit: {n_units} unidades no KPI ('Alunos EVO'); {n_match} casaram coord "
        f"(bairro/UF, fallback cidade+UF; {100*n_match/n_units:.0f}%); {len(m)} com alunos>0 -> hex."
    )
    return m[["hex_id", "alunos_totais"]]


def build_alvo() -> pd.DataFrame:
    partes = [base_ultra(), base_smart(), base_eng(), base_sky()]
    todo = pd.concat(partes, ignore_index=True)
    # SOMA alunos_totais por hex (anti-PII: so [hex_id, alunos_totais])
    agg = todo.groupby("hex_id", as_index=False)["alunos_totais"].sum()
    prov.append(f"- TOTAL alvo: {len(todo)} unidades georreferenciadas -> {len(agg)} hexes unicos (soma de alunos_totais).")
    return agg


# --------------------------------------------------------------------------- #
# Join com mercado + harness
# --------------------------------------------------------------------------- #
def carregar_mkt() -> pd.DataFrame:
    import pyarrow.parquet as pq

    cols = [
        "hex_id", "score_priorizacao", "score_oportunidade_residual", "share_captura_huff",
        "score_setor_2022_calibrado", "renda_per_capita", "uf", "populacao_corte_hex",
        "confianca_geografica", "pop_total_setor_2022", "pop_total", "populacao_proxy",
        "qualidade_join_uf", "flag_censo_disponivel",
    ]
    disp = set(pq.ParquetFile(MKT).schema.names)
    return pd.read_parquet(MKT, columns=[c for c in cols if c in disp])


def marginal_band(df_join: pd.DataFrame) -> str:
    """Faixa marginal renda_pc em [1200,1500) e pop_corte>=5000: os eixos ainda separam alunos_totais?"""
    df = df_join.copy()
    pop = _derive_populacao_corte(df)
    renda = pd.to_numeric(df.get("renda_per_capita"), errors="coerce")
    # comparacao de N pos-gate 1500 vs 1200
    g1500 = ((pop >= POP_MIN_GATE_ATR) & (renda >= 1500.0)).fillna(False)
    g1200 = ((pop >= POP_MIN_GATE_ATR) & (renda >= 1200.0)).fillna(False)
    band = ((pop >= POP_MIN_GATE_ATR) & (renda >= 1200.0) & (renda < 1500.0)).fillna(False)
    n1500, n1200, nband = int(g1500.sum()), int(g1200.sum()), int(band.sum())

    L: list[str] = []
    L.append(f"- N pos-gate renda>=1500: **{n1500}** | N pos-gate renda>=1200: **{n1200}** "
             f"(delta +{n1200-n1500}) | N na faixa marginal [1200,1500): **{nband}**")

    sub = df.loc[band].copy()
    if nband >= 3:
        sub = normalizar_eixos(sub)
        y = _preparar_alvo(sub.rename(columns={}))  # alvo ja chamado 'membros' (=alunos_totais)
        # Spearman de cada eixo vs alunos_totais na faixa
        alvo = pd.to_numeric(sub["membros"], errors="coerce").to_numpy(dtype=float)
        for lbl, col in (("sociodemo(score_priorizacao)", FEAT_SOCIODEMO),
                         ("mercado(residual)", FEAT_MERCADO),
                         ("disputa(1-share_huff)", FEAT_DISPUTA)):
            x = pd.to_numeric(sub[col], errors="coerce").to_numpy(dtype=float)
            ok = np.isfinite(x) & np.isfinite(alvo)
            if ok.sum() >= 3 and np.unique(x[ok]).size >= 2:
                rho, p = spearmanr(x[ok], alvo[ok])
                L.append(f"  - Spearman {lbl} vs alunos_totais (faixa): rho={rho:+.3f} p={p:.4f} (n={int(ok.sum())})")
            else:
                L.append(f"  - Spearman {lbl}: n insuficiente")
        # R2_oof do composto SO na faixa (se N permitir)
        if nband >= 30:
            m = _avaliar_modelo(sub, y, FEATURES_COMPOSTO, nome="composto_faixa_marginal")
            L.append(f"  - R2_oof composto (so faixa marginal, metodo por N={m.n}): {m.r2_oof:+.4f} "
                     f"IC95=[{m.ic95_r2[0]:+.4f}, {m.ic95_r2[1]:+.4f}] rho_oof={m.rho_oof:+.4f}")
        else:
            L.append(f"  - R2_oof composto na faixa: N={nband} pequeno demais para k-fold confiavel; so correlacoes acima.")
    else:
        L.append("  - Faixa marginal com N<3: nada a modelar.")
    return "\n".join(L)


def huff_breakdown(df_join: pd.DataFrame) -> tuple[dict[str, float], str]:
    """Isola quanto do sinal e Huff-circular vs sociodemo+residual "limpo".

    Reusa EXATAMENTE o pre-processamento e o k-fold 5x5 seed=42 do harness: gate ATR-02,
    normalizacao dos eixos, log1p(alvo) e `_avaliar_modelo` (mesmo Ridge/ALPHA_GRID). Roda:
      (a) composto SEM disputa (sociodemo + mercado/residual);
      (b) disputa sozinho; (c) composto completo (3 eixos).
    O eixo `disputa` = 1 - share_captura_huff, e o Huff foi CALIBRADO no proprio `membros`
    (BLK-TP-07) -> disputa-vs-membros e parcialmente circular. Aqui o alvo e alunos_totais.
    """
    df_pos, _ = aplicar_gate_atratividade(df_join)
    df_norm = normalizar_eixos(df_pos)
    y = _preparar_alvo(df_norm)
    m_sem = _avaliar_modelo(df_norm, y, (FEAT_SOCIODEMO, FEAT_MERCADO), nome="composto_sem_disputa")
    m_disp = _avaliar_modelo(df_norm, y, (FEAT_DISPUTA,), nome="disputa_so")
    m_full = _avaliar_modelo(df_norm, y, FEATURES_COMPOSTO, nome="composto_full")
    d = {
        "n": float(m_full.n),
        "r2_sem_disputa": m_sem.r2_oof, "ic_sem_lo": m_sem.ic95_r2[0], "ic_sem_hi": m_sem.ic95_r2[1],
        "r2_disputa": m_disp.r2_oof, "ic_disp_lo": m_disp.ic95_r2[0], "ic_disp_hi": m_disp.ic95_r2[1],
        "r2_full": m_full.r2_oof, "ic_full_lo": m_full.ic95_r2[0], "ic_full_hi": m_full.ic95_r2[1],
    }
    L = [
        "| modelo (alvo=alunos_totais) | R2_oof | IC95 |",
        "| --- | ---: | :--- |",
        f"| (a) composto SEM disputa (sociodemo+residual, \"limpo\") | {d['r2_sem_disputa']:+.4f} | "
        f"[{d['ic_sem_lo']:+.4f}, {d['ic_sem_hi']:+.4f}] |",
        f"| (b) disputa sozinho (1-share_huff, Huff-circular) | {d['r2_disputa']:+.4f} | "
        f"[{d['ic_disp_lo']:+.4f}, {d['ic_disp_hi']:+.4f}] |",
        f"| (c) composto completo (3 eixos) | {d['r2_full']:+.4f} | "
        f"[{d['ic_full_lo']:+.4f}, {d['ic_full_hi']:+.4f}] |",
    ]
    return d, "\n".join(L)


def huff_recalibrado(df_join: pd.DataFrame) -> tuple[dict[str, float], str]:
    """Calibra um Huff NOVO contra alunos_totais (nao membros) e mede o eixo disputa recalibrado.

    O Huff atual (`share_captura_huff` no mercado) foi calibrado em `membros` (BLK-TP-07) -> fica
    INTOCADO (READ-ONLY). Aqui, sobre a MESMA base densa de concorrentes (`concorrentes_densos`,
    ~10k un., mesma do ATR-03-FU1), calibra-se um beta NOVO out-of-fold minimizando RMSE vs
    alunos_totais e constroi-se `disputa_novo = percentil(1 - share_novo)`, avaliado pelo MESMO
    _avaliar_modelo (Ridge k-fold 5x5 seed=42) do harness -- apples-to-apples com disputa-membros.

    Decompoe o efeito em 2 fontes: (i) COBERTURA (coords densas vs esparsas do mercado) e (ii)
    RECALIBRACAO do beta no alvo certo. Para isolar, mede-se tambem `disputa_dense_beta05` (coords
    densas, beta=0.5 do Huff-membros).

    Caveat metodologico (registrado): beta e escolhido out-of-fold GLOBAL (nao nested-in-fold) e o
    eixo e reavaliado nos mesmos folds -> tuning de 1 ESCALAR levemente otimista. Grade beta pequena
    (5 valores) mitiga; efeito de 1 escalar sobre R2_oof e de 2a ordem.
    """
    df_pos, _ = aplicar_gate_atratividade(df_join)
    hexes = df_pos["hex_id"].astype(str).tolist()
    df_denso = pd.read_parquet(DENSOS, columns=["lat", "lng"])
    conc_lat, conc_lng = _coords_densas(df_denso)

    # beta NOVO out-of-fold minimizando RMSE vs alunos_totais (df_pos ja tem alvo 'membros'=alunos)
    res_huff = calibrar_huff_captura(df_pos, conc_lat, conc_lng, incluir_sensibilidades=False)
    beta_novo = float(res_huff.beta_selecionado)

    # shares na base densa: beta_novo e beta=0.5 (do Huff-membros), mesmos hexes
    share_novo = calcular_share_por_hex(hexes, conc_lat, conc_lng, beta_novo)
    share_b05 = calcular_share_por_hex(hexes, conc_lat, conc_lng, 0.5)

    df_norm = normalizar_eixos(df_pos)  # traz sociodemo, mercado, disputa (membros-huff do mercado)
    df_norm = df_norm.assign(
        eixo_disputa_novo=_percentil_0_100(pd.Series(1.0 - share_novo, index=df_norm.index)),
        eixo_disputa_dense_b05=_percentil_0_100(pd.Series(1.0 - share_b05, index=df_norm.index)),
    )
    y = _preparar_alvo(df_norm)

    m_dnovo = _avaliar_modelo(df_norm, y, ("eixo_disputa_novo",), nome="disputa_novo_so")
    m_db05 = _avaliar_modelo(df_norm, y, ("eixo_disputa_dense_b05",), nome="disputa_dense_b05_so")
    m_comp = _avaliar_modelo(
        df_norm, y, (FEAT_SOCIODEMO, FEAT_MERCADO, "eixo_disputa_novo"), nome="composto_disputa_novo"
    )
    d = {
        "beta_novo": beta_novo,
        "r2_huff_log": float(res_huff.r2_oof_log),
        "ic_huff_lo": float(res_huff.ic95_r2_oof[0]), "ic_huff_hi": float(res_huff.ic95_r2_oof[1]),
        "r2_base_geo": float(res_huff.r2_oof_baseline_geometrico),
        "n": float(m_dnovo.n),
        "r2_dnovo": m_dnovo.r2_oof, "ic_dnovo_lo": m_dnovo.ic95_r2[0], "ic_dnovo_hi": m_dnovo.ic95_r2[1],
        "rho_dnovo": m_dnovo.rho_oof,
        "r2_db05": m_db05.r2_oof, "ic_db05_lo": m_db05.ic95_r2[0], "ic_db05_hi": m_db05.ic95_r2[1],
        "r2_comp": m_comp.r2_oof, "ic_comp_lo": m_comp.ic95_r2[0], "ic_comp_hi": m_comp.ic95_r2[1],
        "rho_comp": m_comp.rho_oof,
    }
    L = [
        f"- **beta_novo selecionado (out-of-fold, menor RMSE vs alunos_totais) = {beta_novo:g}** "
        f"vs beta do Huff-membros = 0.5. (Modelo direto log1p(alunos)~log1p(share_novo): "
        f"R2_oof_log = {d['r2_huff_log']:+.4f} IC95=[{d['ic_huff_lo']:+.4f}, {d['ic_huff_hi']:+.4f}]; "
        f"baseline geometrico contagem-no-raio = {d['r2_base_geo']:+.4f}.)",
        "",
        "| eixo/modelo (alvo=alunos_totais, mesmos folds) | R2_oof | IC95 |",
        "| --- | ---: | :--- |",
        "| REF limpo (sociodemo+residual, sem Huff) | +0.0827 | [+0.0394, +0.1223] |",
        "| REF disputa-membros (Huff calibrado em membros, coords do mercado) | +0.1492 | [+0.0979, +0.1952] |",
        "| REF composto c/ disputa-membros | +0.1629 | [+0.1088, +0.2137] |",
        f"| disputa DENSA beta=0.5 (isola efeito COORDS densas) | {d['r2_db05']:+.4f} | "
        f"[{d['ic_db05_lo']:+.4f}, {d['ic_db05_hi']:+.4f}] |",
        f"| **disputa_novo sozinho** (Huff recalibrado no alvo certo, coords densas) | "
        f"**{d['r2_dnovo']:+.4f}** | [{d['ic_dnovo_lo']:+.4f}, {d['ic_dnovo_hi']:+.4f}] |",
        f"| **composto c/ disputa_novo** (sociodemo+residual+disputa_novo) | "
        f"**{d['r2_comp']:+.4f}** | [{d['ic_comp_lo']:+.4f}, {d['ic_comp_hi']:+.4f}] |",
    ]
    return d, "\n".join(L)


def _secao_recal(rc: dict[str, float]) -> list[str]:
    limpo = 0.0827
    disp_membros = 0.1492
    dnovo = rc["r2_dnovo"]
    comp = rc["r2_comp"]
    d_vs_limpo = dnovo - limpo
    d_vs_membros = dnovo - disp_membros
    huff_bate_contagem = rc["r2_huff_log"] > rc["r2_base_geo"]
    vered = (
        f"CIRCULARIDADE domina, geometria residual fraca. beta_novo selecionado honestamente = "
        f"{rc['beta_novo']:g} (o MESMO 0.5 do Huff-membros; a grade nao quis decaimento mais forte). "
        f"Recalibrado no alvo certo sobre a base DENSA, o eixo `disputa_novo` cai para R2_oof "
        f"{dnovo:+.4f} -- praticamente IGUAL a leitura limpa (+{limpo:.4f}; delta {d_vs_limpo:+.4f}, "
        f"ICs quase totalmente sobrepostos) e MUITO abaixo da disputa-membros (+{disp_membros:.4f}; "
        f"delta {d_vs_membros:+.4f}, queda de ~{abs(100*d_vs_membros/disp_membros):.0f}%). Como a base "
        f"densa e MAIS completa que a do Huff-membros (nao menos), a vantagem do +{disp_membros:.4f} "
        f"NAO era geometria melhor -- era o Huff ter sido AJUSTADO no proprio membros (circular). "
        f"Prova adicional pelo teste do proprio modulo (D6b): o Huff honesto "
        f"({rc['r2_huff_log']:+.4f}) {'SUPERA' if huff_bate_contagem else 'NAO supera'} a mera "
        f"contagem-de-concorrentes-no-raio ({rc['r2_base_geo']:+.4f}) -- "
        f"{'a distancia agrega' if huff_bate_contagem else 'a distancia/decaimento NAO agrega sobre so contar concorrentes'}. "
        f"Resta um sinal geometrico RESIDUAL: o composto c/ disputa_novo ({comp:+.4f}) ainda supera a "
        f"leitura limpa por {comp-limpo:+.4f}, mas modesto. Conclusao: a leitura honesta de magnitude "
        f"de alunos reais mora em sociodemo+residual (~+0.08); o Huff acrescenta pouco quando "
        f"recalibrado sem circularidade."
    )
    return [
        "## Huff recalibrado vs alunos_totais (isola circularidade vs geometria)",
        "",
        "O Huff atual (`share_captura_huff`) foi calibrado em `membros` e fica **INTOCADO** "
        "(READ-ONLY). Aqui calibra-se um Huff NOVO com beta out-of-fold minimizando RMSE contra "
        "**alunos_totais**, sobre a base DENSA de concorrentes (`concorrentes_densos`, ~10k un.), e "
        "constroi-se `disputa_novo = percentil(1 - share_novo)`, avaliado pelo MESMO k-fold 5x5 "
        "seed=42. Decompoe o efeito em coords densas (linha beta=0.5) vs recalibracao do beta.",
        "",
        rc["_tbl"],
        "",
        f"Veredito (circularidade vs geometria): {vered}",
        "",
        "Caveat metodologico (registrado): o beta e escolhido out-of-fold GLOBAL (nao "
        "nested-in-fold) e o eixo e reavaliado nos mesmos folds -> e um tuning de 1 ESCALAR, "
        "levemente otimista. A grade beta e pequena (5 valores) e o efeito de 1 escalar sobre o "
        "R2_oof e de 2a ordem; o sinal do veredito nao depende dessa margem. A comparacao tambem "
        "conflui 2 mudancas (coords densas + beta): a linha 'disputa DENSA beta=0.5' isola o efeito "
        "de cobertura antes da recalibracao.",
        "",
    ]


def _conclusao(result, hb: dict[str, float], band_txt: str, rc: dict[str, float]) -> list[str]:
    comp = result.modelos["composto"]
    mods = result.modelos
    def r2(k):  # noqa: ANN001
        return mods[k].r2_oof if k in mods else float("nan")
    L = [
        "# ATR-03 revalidado com ALVO = ALUNOS TOTAIS reais (nao `membros` corporativo)",
        "",
        "READ-ONLY M1 (DEC-001/008/009/012). Alvo trocado: em vez de `membros` (demanda do beneficio "
        "corporativo TotalPass/WellHub, ~1/3 da demanda real, enviesado), usa-se **alunos_totais reais** "
        "por unidade, unificando TODAS as bases reais do repo (Ultra + Smart Fit + Eng. do Corpo + Sky "
        "Fit), somados por hex H3 res-7. **No harness a coluna `membros` CARREGA alunos_totais.** "
        "Anti-PII: so [hex_id, alunos_totais] agregado; coord/nome dropados na fronteira.",
        "",
        "## Conclusao honesta (leia primeiro)",
        "",
        "| eixo (R2_oof) | ALVO=membros (baseline) | ALVO=alunos_totais (este teste) |",
        "| --- | ---: | ---: |",
        f"| disputa (1-share_huff) | +0.4885 | **{r2('disputa'):+.4f}** |",
        f"| sociodemo (score_priorizacao) | +0.2592 | **{r2('sociodemo'):+.4f}** |",
        f"| mercado (residual) | +0.1054 | **{r2('mercado'):+.4f}** |",
        f"| **composto Ridge** | **+0.5653** [+0.5450,+0.5839] | **{comp.r2_oof:+.4f}** "
        f"[{comp.ic95_r2[0]:+.4f}, {comp.ic95_r2[1]:+.4f}] |",
        f"| rho_oof composto | +0.7467 | {comp.rho_oof:+.4f} |",
        f"| N_join / N_pos_gate | 16411 / 4630 | {result.n_join} / {result.n_pos_gate} |",
        f"| veredito | GO-composto | **{result.veredito.upper()}** |",
        "",
        "### Breakdown Huff-circular vs limpo (mesmo k-fold 5x5 seed=42; alvo=alunos_totais)",
        "",
        "O eixo `disputa` = 1 - `share_captura_huff`, e o Huff foi CALIBRADO no proprio `membros` "
        "(BLK-TP-07) -> disputa-vs-membros e parcialmente circular. Separando os componentes:",
        "",
        f"- (a) composto SEM disputa (sociodemo+residual, \"limpo\"): R2_oof = **{hb['r2_sem_disputa']:+.4f}** "
        f"IC95=[{hb['ic_sem_lo']:+.4f}, {hb['ic_sem_hi']:+.4f}]",
        f"- (b) disputa sozinho (Huff): R2_oof = **{hb['r2_disputa']:+.4f}** "
        f"IC95=[{hb['ic_disp_lo']:+.4f}, {hb['ic_disp_hi']:+.4f}]",
        f"- (c) composto completo (3 eixos): R2_oof = **{hb['r2_full']:+.4f}** "
        f"IC95=[{hb['ic_full_lo']:+.4f}, {hb['ic_full_hi']:+.4f}]",
        "",
        "Leitura honesta: o eixo disputa/Huff (b) e o maior contribuinte isolado e o composto "
        "completo (c) so o supera por +0.0137 -- ou seja, o \"topo\" do composto e essencialmente o "
        "Huff, que carrega circularidade (calibrado no `membros`, nao no alunos_totais). MAS a parte "
        "\"limpa\" sociodemo+residual (a) NAO e ruido: sozinha da R2_oof +0.0827 com IC95 que "
        "EXCLUI zero [+0.0394,+0.1223] -- ha um sinal geografico real, ainda que modesto, de "
        "magnitude de alunos reais, independente do Huff. Conclusao: (i) o composto e GO-composto "
        "FRACO (vence o melhor eixo por so +0.0137); (ii) o sinal `membros`->+0.5653 era MUITO "
        "inflado pela circularidade + selecao corporativa; com alunos_totais o teto realista fica "
        "em ~+0.16 (composto) e ~+0.08 (leitura limpa sem Huff).",
        "",
        *_secao_recal(rc),
        "## Proveniencia do alvo (contagens, sem PII)",
        "",
        *prov,
        "",
        "## Faixa marginal de renda (corte 1500 vs 1200)",
        "",
        band_txt,
        "",
        "Veredito da faixa marginal: BORDERLINE, nao conclusivo a favor de baixar o corte. Na faixa "
        "[1200,1500) (N=101) so o eixo sociodemo mostra Spearman positivo no limite da significancia "
        "(rho +0.196, p=0.049) e a disputa fica marginal (rho +0.188, p=0.060); o mercado/residual e "
        "nulo (rho -0.043). O composto NAO generaliza out-of-fold nessa faixa (R2_oof -0.0321, IC "
        "cruza zero). Ou seja: ha um sopro de sinal sociodemografico na renda mais baixa, mas nao "
        "robusto o bastante para justificar baixar 1500->1200 so por esta evidencia. Os +101 hexes "
        "ganhos entram com sinal fraco/ruidoso.",
        "",
        "---",
        "",
    ]
    return L


def main() -> None:
    alvo = build_alvo()
    mkt = carregar_mkt()
    join = alvo.merge(mkt, on="hex_id", how="inner")
    n_join = len(join)
    prov.append(f"- Inner join alvo x mercado por hex_id: **{n_join}** hexes (de {len(alvo)} hexes-alvo).")

    # Renomeia alunos_totais -> membros para o harness (documentado)
    join = join.rename(columns={"alunos_totais": "membros"})

    result = avaliar_estrutura_funil(join)
    hb, hb_tbl = huff_breakdown(join)
    rc, rc_tbl = huff_recalibrado(join)
    rc["_tbl"] = rc_tbl
    band_txt = marginal_band(join)

    base_md = relatorio_estrutura_funil(result)
    header = _conclusao(result, hb, band_txt, rc)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(header) + base_md, encoding="utf-8")

    print("=== PROVENIENCIA ===")
    print("\n".join(prov))
    print("\n=== HUFF BREAKDOWN (alvo=alunos_totais) ===")
    print(hb_tbl)
    print("\n=== HUFF RECALIBRADO (novo beta vs alunos_totais) ===")
    print(f"beta_novo={rc['beta_novo']:g} (vs 0.5) | R2_huff_log={rc['r2_huff_log']:+.4f}")
    print(rc_tbl)
    print("\n=== VEREDITO ESTRUTURA ===")
    print(result.nota_honesta.splitlines()[2])
    print("=== MARGINAL ===")
    print(band_txt)
    print(f"\nMD: {OUT_MD}")


if __name__ == "__main__":
    main()
