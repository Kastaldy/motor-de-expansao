"""Backtest LOO do motor de viabilidade vs as 54 unidades Ultra reais (BLK-VIAB-04).

Roda `analisar_viabilidade_ponto` em modo COORDLESS (`setores_df=None`,
`lat=lng=0.0`) sobre cada unidade Ultra madura, usando m2 e alunos reais como
entradas, com base de calibracao LEAVE-ONE-OUT (as 54 unidades MENOS a avaliada).
Mede o erro da curva tamanho->densidade (`faixa_alunos_p50` predito vs
`alunos_total` real) + aluguel-teto/break-even, e gera relatorio com MAE/vies e
casos de erro material.

GUARDRAILS:
    - LOO obrigatorio: para cada unidade i, a base de calibracao NUNCA inclui i.
      Isso e o que garante honestidade da medicao (DEC-008: so MEDIR, nao ajustar).
    - DEC-009: `demanda_premissa = alunos_total` REAL da unidade (premissa
      explicita). NUNCA prevista pela geografia (lat/lng NAO entram na demanda).
    - Modo COORDLESS: `setores_df=None` -> sem catchment, sem rede, sem fetch HTTP.
    - READ-ONLY sobre o M1: nao recalcula `score_priorizacao`, `hex_score_estrutural`,
      pesos, carteira, plano nem artefatos oficiais (DEC-001/DEC-008).
    - `viabilidade_ponto.py` / `simulador.py` / `config.py` INTOCADOS (so importados).
    - Saida = SO relatorio `.md` gitignored; nenhum parquet, nenhuma PII persistida.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from motor_expansao.dimensionamento.config import PII_COLUNAS_PROIBIDAS, SIM_ALUGUEL_MES
from motor_expansao.dimensionamento.viabilidade_ponto import (
    FAIXA_M2_TOLERANCIA,
    N_MIN_COMPARAVEIS,
    analisar_viabilidade_ponto,
)

# ---------------------------------------------------------------------------
# Constantes publicas
# ---------------------------------------------------------------------------

VERSAO_CONTRATO: str = "viabilidade_backtest_v1"

COLS_OBRIGATORIAS: tuple[str, ...] = (
    "unidade",
    "metragem",
    "alunos_total",
    "ticket_medio_aluno",
)

# Placeholders ecoados (modo coordless; o catchment nao usa lat/lng quando
# setores_df=None). NAO sao persistidos como coluna de saida.
LAT_COORDLESS: float = 0.0
LNG_COORDLESS: float = 0.0

MARGEM_ALVO_DEFAULT: float = 0.10

# Limiar de erro material (CA-5): se MAPE p50 > 40% -> registrar recalibracao.
MAE_MATERIAL_PCT: float = 0.40

# Ordem fixa das colunas do DataFrame de backtest (uma linha por unidade).
COLUNAS_SAIDA: list[str] = [
    "unidade",
    "metragem",
    "alunos_real",
    "ticket_real",
    "alunos_por_m2_real",
    "faixa_alunos_p10_predito",
    "faixa_alunos_p50_predito",
    "faixa_alunos_p90_predito",
    "alunos_por_m2_predito_p50",
    "n_comparaveis",
    "alunos_breakeven_predito",
    "alunos_para_margem_predito",
    "aluguel_teto_predito",
    "flag_viavel",
    "faixa_contem_real",
    "erro_abs_p50",
    "erro_rel_p50",
    "erro_breakeven",
    "flag_extrapolacao",
    "demanda_fonte",
    "versao_contrato",
]


# ---------------------------------------------------------------------------
# Helpers numericos puros (semantica identica a backtest_dim.py; sem sklearn)
# ---------------------------------------------------------------------------


def _mape(real: np.ndarray, pred: np.ndarray) -> float:
    """MAPE = mean(|pred-real|/|real|) sobre real!=0 e finitos; nan se vazio."""
    real = np.asarray(real, dtype=float)
    pred = np.asarray(pred, dtype=float)
    mask = np.isfinite(real) & np.isfinite(pred) & (real != 0)
    if not mask.any():
        return float("nan")
    return float(np.mean(np.abs(pred[mask] - real[mask]) / np.abs(real[mask])))


def _rmse(real: np.ndarray, pred: np.ndarray) -> float:
    """RMSE = sqrt(mean((pred-real)^2)) sobre finitos; nan se vazio."""
    real = np.asarray(real, dtype=float)
    pred = np.asarray(pred, dtype=float)
    mask = np.isfinite(real) & np.isfinite(pred)
    if not mask.any():
        return float("nan")
    return float(np.sqrt(np.mean((pred[mask] - real[mask]) ** 2)))


def _r2(real: np.ndarray, pred: np.ndarray) -> float:
    """R2 = 1 - SS_res/SS_tot (vs media de real); 0.0 se SS_tot==0; nan se vazio."""
    real = np.asarray(real, dtype=float)
    pred = np.asarray(pred, dtype=float)
    mask = np.isfinite(real) & np.isfinite(pred)
    if not mask.any():
        return float("nan")
    r = real[mask]
    p = pred[mask]
    ss_tot = float(np.sum((r - np.mean(r)) ** 2))
    if ss_tot == 0.0:
        return 0.0
    ss_res = float(np.sum((r - p) ** 2))
    return 1.0 - ss_res / ss_tot


# ---------------------------------------------------------------------------
# Funcoes publicas
# ---------------------------------------------------------------------------


def carregar_ultra(parquet_path: Path | str) -> pd.DataFrame:
    """Le o parquet Ultra e devolve a base limpa (indice RESETADO para o LOO).

    Retorna DataFrame com colunas minimas
    ['unidade','metragem','alunos_total','ticket_medio_aluno','alunos_por_m2'].
    NAO propaga lat/lng nem outras colunas do parquet original (anti-PII/geo).

    O reset do indice e CRITICO: o LOO usa o indice posicional para `drop`.
    """
    df = pd.read_parquet(Path(parquet_path))

    faltando = [c for c in COLS_OBRIGATORIAS if c not in df.columns]
    if faltando:
        raise ValueError(f"colunas obrigatorias ausentes: {faltando}")

    metragem = pd.to_numeric(df["metragem"], errors="coerce").astype(float)
    alunos = pd.to_numeric(df["alunos_total"], errors="coerce").astype(float)
    ticket = pd.to_numeric(df["ticket_medio_aluno"], errors="coerce").astype(float)

    if "alunos_por_m2" in df.columns:
        apm = pd.to_numeric(df["alunos_por_m2"], errors="coerce").astype(float)
    else:
        with np.errstate(divide="ignore", invalid="ignore"):
            apm = alunos / metragem

    out = pd.DataFrame(
        {
            "unidade": df["unidade"].astype(str),
            "metragem": metragem,
            "alunos_total": alunos,
            "ticket_medio_aluno": ticket,
            "alunos_por_m2": apm,
        }
    )
    mask = (
        np.isfinite(out["metragem"])
        & (out["metragem"] > 0)
        & np.isfinite(out["alunos_total"])
        & (out["alunos_total"] > 0)
        & np.isfinite(out["alunos_por_m2"])
        & (out["alunos_por_m2"] > 0)
        & np.isfinite(out["ticket_medio_aluno"])
        & (out["ticket_medio_aluno"] > 0)
    )
    out = out[mask].reset_index(drop=True)
    if out.empty:
        raise ValueError("base Ultra vazia apos limpeza")
    return out


def calcular_loo_base(df_ultra: pd.DataFrame, idx: int) -> pd.DataFrame:
    """Base de calibracao LEAVE-ONE-OUT: todas as unidades MENOS `idx`.

    Reseta o indice apos o drop (o LOO posicional depende disso). A base
    conserva `alunos_por_m2` e `metragem` (exigidos pela curva de densidade).
    """
    if idx not in df_ultra.index:
        raise KeyError(f"idx {idx} ausente no DataFrame Ultra")
    return df_ultra.drop(index=idx).reset_index(drop=True)


def rodar_unidade_loo(
    row: pd.Series,
    df_ultra: pd.DataFrame,
    idx: int,
    *,
    aluguel_ref: float = SIM_ALUGUEL_MES,
    margem_alvo: float = MARGEM_ALVO_DEFAULT,
) -> dict:
    """Roda o motor (coordless, LOO) para 1 unidade e monta o dict de saida."""
    base_loo = calcular_loo_base(df_ultra, idx)

    m2 = float(row["metragem"])
    alunos_real = float(row["alunos_total"])
    ticket = float(row["ticket_medio_aluno"])
    apm_real = float(row["alunos_por_m2"])

    res = analisar_viabilidade_ponto(
        lat=LAT_COORDLESS,
        lng=LNG_COORDLESS,
        m2=m2,
        aluguel_pedido=float(aluguel_ref),
        demanda_premissa=alunos_real,  # DEC-009: premissa = alunos_total REAL
        ticket_medio=ticket,
        margem_alvo=margem_alvo,
        base_calibracao_df=base_loo,  # LOO: NUNCA inclui a propria unidade
        setores_df=None,  # COORDLESS explicito
    )

    p10 = res.faixa_alunos_p10
    p50 = res.faixa_alunos_p50
    p90 = res.faixa_alunos_p90

    faixa_contem_real = (
        p10 is not None
        and p90 is not None
        and float(p10) <= alunos_real <= float(p90)
    )

    p50_f = float(p50) if p50 is not None else float("nan")
    erro_abs_p50 = p50_f - alunos_real  # +=motor superestima; -=subestima
    erro_rel_p50 = erro_abs_p50 / alunos_real if alunos_real > 0 else float("nan")

    breakeven = float(res.alunos_breakeven)
    erro_breakeven = alunos_real - breakeven  # +=folga sobre o break-even

    apm_pred_p50 = p50_f / m2 if m2 > 0 else float("nan")

    # flag_extrapolacao: a janela estreita (+/-20%) da base LOO teve < N_MIN
    # comparaveis -> o motor alargou. `n_comparaveis` do motor e da janela FINAL
    # (ja alargada), entao recomputamos a contagem da janela estreita (leitura
    # pura sobre base_loo; NAO altera o motor).
    metr_loo = pd.to_numeric(base_loo["metragem"], errors="coerce")
    apm_loo = pd.to_numeric(base_loo["alunos_por_m2"], errors="coerce")
    lo = m2 * (1.0 - FAIXA_M2_TOLERANCIA)
    hi = m2 * (1.0 + FAIXA_M2_TOLERANCIA)
    n_estreita = int(
        (
            metr_loo.between(lo, hi)
            & np.isfinite(apm_loo)
            & (apm_loo > 0)
        ).sum()
    )
    flag_extrapolacao = bool(n_estreita < N_MIN_COMPARAVEIS)

    return {
        "unidade": str(row["unidade"]),
        "metragem": m2,
        "alunos_real": alunos_real,
        "ticket_real": ticket,
        "alunos_por_m2_real": apm_real,
        "faixa_alunos_p10_predito": None if p10 is None else float(p10),
        "faixa_alunos_p50_predito": None if p50 is None else float(p50),
        "faixa_alunos_p90_predito": None if p90 is None else float(p90),
        "alunos_por_m2_predito_p50": apm_pred_p50,
        "n_comparaveis": res.n_comparaveis,
        "alunos_breakeven_predito": breakeven,
        "alunos_para_margem_predito": float(res.alunos_para_margem_alvo),
        "aluguel_teto_predito": float(res.aluguel_teto_calculado),
        "flag_viavel": bool(res.viabilidade.flag_viavel),
        "faixa_contem_real": bool(faixa_contem_real),
        "erro_abs_p50": erro_abs_p50,
        "erro_rel_p50": erro_rel_p50,
        "erro_breakeven": erro_breakeven,
        "flag_extrapolacao": flag_extrapolacao,
        "demanda_fonte": str(res.demanda_fonte),
        "versao_contrato": VERSAO_CONTRATO,
    }


def rodar_backtest(
    df_ultra: pd.DataFrame,
    *,
    aluguel_ref: float = SIM_ALUGUEL_MES,
    margem_alvo: float = MARGEM_ALVO_DEFAULT,
) -> pd.DataFrame:
    """Roda o LOO para cada unidade e devolve o DataFrame ranqueado por |erro|.

    Recebe `df_ultra` ja carregado (permite teste sem IO). Ranking por
    |erro_abs_p50| DESC (piores erros no topo do relatorio).
    """
    linhas: list[dict] = []
    for idx, row in df_ultra.iterrows():
        linhas.append(
            rodar_unidade_loo(
                row,
                df_ultra,
                int(idx),
                aluguel_ref=aluguel_ref,
                margem_alvo=margem_alvo,
            )
        )

    df = pd.DataFrame(linhas, columns=COLUNAS_SAIDA)

    # Guard anti-PII de saida (case-insensitive). `unidade` NAO e PII proibida.
    proibidas = {c.lower() for c in PII_COLUNAS_PROIBIDAS}
    vazadas = [c for c in df.columns if c.lower() in proibidas]
    if vazadas:
        raise ValueError(f"colunas PII proibidas na saida: {vazadas}")

    df = df.sort_values(
        "erro_abs_p50", key=lambda s: s.abs(), ascending=False, na_position="last"
    ).reset_index(drop=True)
    return df


def calcular_metricas_agregadas(df: pd.DataFrame) -> dict:
    """Agrega MAE, MAPE, RMSE, vies, R2, cobertura do intervalo e contagens."""
    real = df["alunos_real"].to_numpy(dtype=float)
    pred = df["faixa_alunos_p50_predito"].to_numpy(dtype=float)

    mask = np.isfinite(real) & np.isfinite(pred)
    mae = float(np.mean(np.abs(pred[mask] - real[mask]))) if mask.any() else float("nan")
    vies = float(np.mean(pred[mask] - real[mask])) if mask.any() else float("nan")

    return {
        "n": int(len(df)),
        "mae": mae,
        "mape": _mape(real, pred),
        "vies": vies,
        "rmse": _rmse(real, pred),
        "r2": _r2(real, pred),
        "cobertura_intervalo": (
            float(df["faixa_contem_real"].mean()) if len(df) else float("nan")
        ),
        "pct_viavel": float(df["flag_viavel"].mean()) if len(df) else float("nan"),
        "n_faixa_correta": int(df["faixa_contem_real"].sum()) if len(df) else 0,
        "pct_faixa_correta": (
            float(df["faixa_contem_real"].mean()) if len(df) else float("nan")
        ),
        "n_extrapolacao": int(df["flag_extrapolacao"].sum()) if len(df) else 0,
        "versao_contrato": VERSAO_CONTRATO,
    }


def _fmt(v: float, casas: int = 2) -> str:
    """Formata float tolerando NaN."""
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "n/d"
    return f"{v:,.{casas}f}"


def _gerar_relatorio_md(df: pd.DataFrame, metricas: dict) -> str:
    """Gera o relatorio markdown do backtest."""
    mape = metricas.get("mape", float("nan"))
    linhas = [
        "# Backtest do motor de viabilidade vs 54 unidades Ultra reais — BLK-VIAB-04",
        "",
        f"Data de geração: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"Versão do contrato: `{VERSAO_CONTRATO}` · "
        "Modo: coordless (setores_df=None) · "
        "Demanda: premissa explícita = alunos_total real (DEC-009) · "
        "Calibração: LEAVE-ONE-OUT.",
        "",
        "## Métricas agregadas",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| N unidades | {metricas['n']} |",
        f"| **MAE** (alunos, p50 vs real) | {_fmt(metricas['mae'])} |",
        f"| MAPE (p50 vs real) | {_fmt(mape * 100.0, 1)}% |",
        f"| **Viés** (mean(pred-real); +=superestima) | {_fmt(metricas['vies'])} |",
        f"| RMSE | {_fmt(metricas['rmse'])} |",
        f"| R2 (p50 vs real) | {_fmt(metricas['r2'], 3)} |",
        f"| Cobertura do intervalo [p10,p90] | {_fmt(metricas['cobertura_intervalo'] * 100.0, 1)}% |",
        f"| N faixa correta (real in [p10,p90]) | {metricas['n_faixa_correta']} |",
        f"| % viável (cenário aluguel-ref) | {_fmt(metricas['pct_viavel'] * 100.0, 1)}% |",
        f"| N extrapolação (janela estreita <{N_MIN_COMPARAVEIS}) | {metricas['n_extrapolacao']} |",
        "",
        "## Leitura material (CA-5)",
        "",
    ]

    if np.isfinite(mape) and mape > MAE_MATERIAL_PCT:
        linhas.append(
            f"NECESSIDADE DE RECALIBRAÇÃO: MAPE P50 = {mape * 100.0:.1f}% > 40% — "
            "O MOTOR ERRA DE FORMA MATERIAL E SISTEMÁTICA; A RECALIBRAÇÃO DEVE SER "
            "BLOCO PRÓPRIO (DEC-008: ESTE BLOCO SÓ MEDE)."
        )
    else:
        linhas.append("Erro dentro do limiar material (MAPE p50 <= 40%).")

    linhas += [
        "",
        "## Por unidade (ordenado por |erro_abs_p50| DESC)",
        "",
        "| Unidade | m² | Alunos real | p10 | p50 | p90 | Erro abs p50 | "
        "Erro rel p50 | Contém real | N comp. | Extrap | Aluguel-teto | Viável |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    for _, r in df.iterrows():
        contem = "SIM" if bool(r["faixa_contem_real"]) else "-"
        extrap = "ATENÇÃO" if bool(r["flag_extrapolacao"]) else "-"
        viavel = "SIM" if bool(r["flag_viavel"]) else "-"
        erro_rel = r["erro_rel_p50"]
        erro_rel_s = _fmt(erro_rel * 100.0, 1) + "%" if np.isfinite(erro_rel) else "n/d"
        linhas.append(
            f"| {r['unidade']} | {_fmt(r['metragem'], 0)} | "
            f"{_fmt(r['alunos_real'], 0)} | {_fmt(r['faixa_alunos_p10_predito'], 0)} | "
            f"{_fmt(r['faixa_alunos_p50_predito'], 0)} | "
            f"{_fmt(r['faixa_alunos_p90_predito'], 0)} | {_fmt(r['erro_abs_p50'], 0)} | "
            f"{erro_rel_s} | {contem} | {r['n_comparaveis']} | {extrap} | "
            f"{_fmt(r['aluguel_teto_predito'], 0)} | {viavel} |"
        )

    # Casos extremos por metragem (menor e maior m²).
    linhas += ["", "## Casos extremos (menor e maior m²)", ""]
    if len(df):
        menor = df.loc[df["metragem"].idxmin()]
        maior = df.loc[df["metragem"].idxmax()]
        for tag, r in (("Menor m²", menor), ("Maior m²", maior)):
            ex = "SIM" if bool(r["flag_extrapolacao"]) else "não"
            linhas.append(
                f"- **{tag}:** {r['unidade']} ({_fmt(r['metragem'], 0)} m²) — "
                f"alunos real {_fmt(r['alunos_real'], 0)}, p50 predito "
                f"{_fmt(r['faixa_alunos_p50_predito'], 0)}, extrapolação: {ex}."
            )

    linhas += [
        "",
        "## Caveats",
        "",
        "- **Aluguel real AUSENTE:** o eixo `aluguel_teto_predito` é análise de "
        "capacidade interna (quanto a unidade suportaria dada a demanda real), NÃO "
        "validação contra o aluguel de mercado — este dado não existe na base.",
        "- **N=54 pequeno** e **LOO instável nos extremos** (janela ±20% cai abaixo "
        f"de {N_MIN_COMPARAVEIS} comparáveis → o motor alarga para ±50% ou usa a base "
        "inteira; casos marcados como extrapolação).",
        "- **READ-ONLY M1:** nenhum score, peso, carteira, plano ou artefato oficial "
        "do M1 foi tocado (DEC-001/DEC-008). `viabilidade_ponto.py` INTOCADO.",
        "- **DEC-009:** a demanda entrou SÓ como premissa explícita (`alunos_total` "
        "real de cada unidade); NUNCA prevista pela geografia (modo coordless, "
        "`setores_df=None`, lat=lng=0.0).",
    ]

    return "\n".join(linhas)


def materializar(
    df_backtest: pd.DataFrame,
    metricas: dict,
    analysis_dir: Path | str,
) -> Path:
    """Escreve o relatorio `.md` (gitignored). NAO persiste parquet."""
    analysis_dir = Path(analysis_dir)
    analysis_dir.mkdir(parents=True, exist_ok=True)
    md_path = analysis_dir / "viabilidade_backtest_ultra.md"
    md_path.write_text(_gerar_relatorio_md(df_backtest, metricas), encoding="utf-8")
    return md_path


def run(
    ultra_path: Path | str | None = None,
    analysis_dir: Path | str | None = None,
) -> Path:
    """Pipeline completo: carrega Ultra, roda o LOO e materializa o relatorio."""
    repo = Path(__file__).resolve().parents[3]
    if ultra_path is None:
        ultra_path = repo / "data" / "staging" / "unidades_ultra_performance_hex.parquet"
    if analysis_dir is None:
        analysis_dir = repo / "data" / "analysis"

    df_ultra = carregar_ultra(ultra_path)
    df_bt = rodar_backtest(df_ultra)
    met = calcular_metricas_agregadas(df_bt)
    return materializar(df_bt, met, analysis_dir)


__all__ = [
    "carregar_ultra",
    "calcular_loo_base",
    "rodar_unidade_loo",
    "rodar_backtest",
    "calcular_metricas_agregadas",
    "materializar",
    "run",
    "VERSAO_CONTRATO",
    "COLS_OBRIGATORIAS",
    "COLUNAS_SAIDA",
    "MAE_MATERIAL_PCT",
    "LAT_COORDLESS",
    "LNG_COORDLESS",
]


if __name__ == "__main__":
    _md = run()
    print(f"Relatorio: {_md}")

    _repo = Path(__file__).resolve().parents[3]
    _df_ultra = carregar_ultra(
        _repo / "data" / "staging" / "unidades_ultra_performance_hex.parquet"
    )
    _df_bt = rodar_backtest(_df_ultra)
    _met = calcular_metricas_agregadas(_df_bt)
    print(f"\nN unidades: {_met['n']}")
    print(f"MAE (p50 vs real): {_met['mae']:.2f} alunos")
    print(f"MAPE: {_met['mape'] * 100.0:.1f}%")
    print(f"Vies (pred-real): {_met['vies']:+.2f} alunos")
    print(f"R2: {_met['r2']:.3f}")
    print(f"Cobertura [p10,p90]: {_met['cobertura_intervalo'] * 100.0:.1f}%")
    print(f"N faixa correta: {_met['n_faixa_correta']} / {_met['n']}")
    print(f"N extrapolacao: {_met['n_extrapolacao']}")
    print("\nTop-3 piores erros (|erro_abs_p50|):")
    _cols = ["unidade", "metragem", "alunos_real", "faixa_alunos_p50_predito", "erro_abs_p50"]
    print(_df_bt[_cols].head(3).to_string(index=False))
