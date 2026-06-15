"""BLK-DIM-06: backtest honesto out-of-sample do motor de dimensionamento.

Roda o motor (Camada 1 aderencia + Camada 3+4 simulador DRE) "as cegas" sobre os 54 maduros
REAIS e mede MAPE/RMSE/R2 out-of-sample por camada e end-to-end. O alvo e SEMPRE o dado real
(faturamento, pagantes_steady_state) -- nunca uma saida do proprio simulador (corrige o
in-sample disfarcado do spike). NO-GO / erro alto sao resultados VALIDOS e esperados
(Camada 1 deu r2_loo_log=-0.0134 no BLK-DIM-01R).

READ-ONLY sobre o M1 (DEC-001/DEC-008). `aderencia.py` e `simulador.py` congelados (so
importados). Sem PII em disco; fixtures sinteticas nos testes; relatorio gitignored.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from motor_expansao.dimensionamento.aderencia import (
    calibrar_aderencia,
    prever_aderencia,
)
from motor_expansao.dimensionamento.config import (
    SIM_ALUGUEL_MES,
    SIM_MENSALIDADE_BALCAO,
    SIM_PERSONAL_MES_RECEITA,
)
from motor_expansao.dimensionamento.simulador import viabilidade

_logger = logging.getLogger(__name__)

# Colunas obrigatorias por camada
COLS_CAMADA1 = ("pagantes_steady_state", "pop_captacao", "renda_per_capita_captacao")
COLS_CAMADA34 = (
    "pagantes_steady_state",
    "metragem",
    "ticket_steady",
    "churn_steady",
    "faturamento",
)
N_MIN_BACKTEST = 5  # piso de unidades validas por camada


# ---------- helpers numericos puros ----------


def _mape(real: np.ndarray, pred: np.ndarray) -> float:
    """MAPE = mean(|pred-real|/|real|) sobre real!=0 e ambos finitos. NaN se vazio."""
    real = np.asarray(real, dtype=float)
    pred = np.asarray(pred, dtype=float)
    valid = np.isfinite(real) & np.isfinite(pred) & (real != 0.0)
    if not valid.any():
        return float("nan")
    return float(np.mean(np.abs(pred[valid] - real[valid]) / np.abs(real[valid])))


def _rmse(real: np.ndarray, pred: np.ndarray) -> float:
    """RMSE; NaN se vazio."""
    real = np.asarray(real, dtype=float)
    pred = np.asarray(pred, dtype=float)
    valid = np.isfinite(real) & np.isfinite(pred)
    if not valid.any():
        return float("nan")
    return float(math.sqrt(np.mean((pred[valid] - real[valid]) ** 2)))


def _r2(real: np.ndarray, pred: np.ndarray) -> float:
    """R2 = 1 - SS_res/SS_tot (vs media de `real`). 0.0 se SS_tot==0; NaN se vazio."""
    real = np.asarray(real, dtype=float)
    pred = np.asarray(pred, dtype=float)
    valid = np.isfinite(real) & np.isfinite(pred)
    if not valid.any():
        return float("nan")
    r = real[valid]
    p = pred[valid]
    ss_tot = float(np.sum((r - r.mean()) ** 2))
    ss_res = float(np.sum((r - p) ** 2))
    if ss_tot == 0.0:
        return 0.0
    return 1.0 - ss_res / ss_tot


def _churn_para_fracao(churn_steady: float) -> float:
    """Converte churn em PERCENTUAL (2.0-6.0) para FRACAO (0.02-0.06). >1 -> /100."""
    c = float(churn_steady)
    if not math.isfinite(c):
        return float("nan")
    return c / 100.0 if c > 1.0 else c


def _alunos_maturidade_de_pagantes(pagantes: float, churn_fracao: float) -> float:
    """alunos_maturidade = pagantes / (1 - churn_fracao). NaN se (1-churn)<=0."""
    denom = 1.0 - float(churn_fracao)
    if not math.isfinite(denom) or denom <= 0.0:
        return float("nan")
    return float(pagantes) / denom


def _ticket_efetivo(ticket_steady: float) -> tuple[float, bool]:
    """(ticket, usou_fallback). ticket_steady<=0/NaN -> (SIM_MENSALIDADE_BALCAO, True)."""
    t = float(ticket_steady) if ticket_steady is not None else float("nan")
    if not math.isfinite(t) or t <= 0.0:
        return (float(SIM_MENSALIDADE_BALCAO), True)
    return (t, False)


# ---------- nucleo LOO da Camada 1 (reusa funcoes congeladas) ----------


def _prever_loo_alunos(
    df_maduras: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, list[bool]]:
    """LOO sobre a Camada 1. Para cada fold: calibrar_aderencia nos N-1, prever_aderencia no ponto.

    Retorna (pagantes_real, pagantes_pred_loo, flags_extrapolacao) ALINHADOS as linhas validas
    (pop/renda/pagantes finitos e >0). Reusa as funcoes congeladas; NAO as altera.
    `flags_extrapolacao[i]` = modelo_do_fold_i.flag_extrapolacao(pop_i, renda_i).
    """
    faltando = set(COLS_CAMADA1) - set(df_maduras.columns)
    if faltando:
        raise ValueError(f"Colunas ausentes para Camada 1: {faltando}")

    pop = pd.to_numeric(df_maduras["pop_captacao"], errors="coerce")
    renda = pd.to_numeric(df_maduras["renda_per_capita_captacao"], errors="coerce")
    pagantes = pd.to_numeric(df_maduras["pagantes_steady_state"], errors="coerce")
    mask = (
        pop.notna()
        & (pop > 0)
        & renda.notna()
        & (renda > 0)
        & pagantes.notna()
        & (pagantes > 0)
    )
    df_valido = df_maduras.loc[mask].reset_index(drop=True)
    n = len(df_valido)
    if n < N_MIN_BACKTEST:
        raise ValueError(
            f"Dados insuficientes para LOO da Camada 1: {n} linhas validas "
            f"(minimo {N_MIN_BACKTEST}); LOO exige treino >= 5, logo n >= 6 efetivo."
        )

    pop_v = pd.to_numeric(df_valido["pop_captacao"], errors="coerce").to_numpy(float)
    renda_v = pd.to_numeric(
        df_valido["renda_per_capita_captacao"], errors="coerce"
    ).to_numpy(float)
    pagantes_real = pd.to_numeric(
        df_valido["pagantes_steady_state"], errors="coerce"
    ).to_numpy(float)

    pagantes_pred = np.full(n, np.nan, dtype=float)
    flags: list[bool] = []
    for i in range(n):
        df_treino = df_valido.drop(index=i)
        modelo = calibrar_aderencia(df_treino)
        pred_i, _, _ = prever_aderencia(float(pop_v[i]), float(renda_v[i]), modelo)
        pagantes_pred[i] = pred_i
        flags.append(bool(modelo.flag_extrapolacao(float(pop_v[i]), float(renda_v[i]))))

    return pagantes_real, pagantes_pred, flags


# ---------- dataclass de metricas (uma por camada) ----------


@dataclass
class CamadaBacktest:
    """Metricas out-of-sample de uma camada do backtest."""

    nome: str  # "camada1" | "camada34" | "end_to_end"
    n: int  # unidades validas usadas
    mape: float
    rmse: float
    r2: float  # vs media (honesto)
    mape_baseline: float  # MAPE da previsao ingenua da media
    flag_extrapolacao_pct: float  # % de unidades fora do envelope (NaN p/ camada34 isolada)
    aluguel_estimado: bool  # True se usou SIM_ALUGUEL_MES (camada34/end_to_end)
    n_fallback_ticket: int  # quantas linhas usaram ticket fallback
    nota: str  # legivel, sem PII, reflete o erro MEDIDO


@dataclass
class BacktestResult:
    """Resultado consolidado do backtest (3 camadas)."""

    camada1: CamadaBacktest
    camada34: CamadaBacktest
    end_to_end: CamadaBacktest
    n_unidades_entrada: int  # linhas do df de entrada
    aluguel_default: float  # SIM_ALUGUEL_MES usado
    nota_consolidada: str  # sintese honesta das 3 camadas


# ---------- funcoes de backtest por camada ----------


def backtest_camada1(df_maduras: pd.DataFrame) -> CamadaBacktest:
    """LOO da Camada 1 (aderencia) no espaco de ALUNOS.

    Usa _prever_loo_alunos; metricas pagantes_pred_loo vs pagantes_real; baseline = media LOO
    de pagantes (media dos N-1 por fold). flag_extrapolacao_pct = % de pontos fora do envelope.
    """
    faltando = set(COLS_CAMADA1) - set(df_maduras.columns)
    if faltando:
        raise ValueError(f"Colunas ausentes para Camada 1: {faltando}")

    real, pred, flags = _prever_loo_alunos(df_maduras)
    n = len(real)

    mape = _mape(real, pred)
    rmse = _rmse(real, pred)
    r2 = _r2(real, pred)

    # Baseline LOO: previsao do ponto i = media dos N-1 restantes.
    total = float(np.sum(real))
    baseline_pred = (total - real) / (n - 1)
    mape_baseline = _mape(real, baseline_pred)

    flag_pct = 100.0 * (sum(flags) / n) if n else float("nan")

    nota = (
        f"Camada 1 (aderencia, LOO) | n={n} | MAPE={mape:.1%} | RMSE={rmse:.1f} alunos | "
        f"R2(vs media)={r2:+.3f} | MAPE_baseline={mape_baseline:.1%} | "
        f"extrapolacao={flag_pct:.0f}%. NO-GO esperado (BLK-DIM-01R r2_loo_log=-0.0134): "
        "a demanda absoluta nao e calibravel so com pop+renda; o erro alto e o resultado "
        "honesto, nao defeito."
    )
    return CamadaBacktest(
        nome="camada1",
        n=n,
        mape=mape,
        rmse=rmse,
        r2=r2,
        mape_baseline=mape_baseline,
        flag_extrapolacao_pct=flag_pct,
        aluguel_estimado=False,
        n_fallback_ticket=0,
        nota=nota,
    )


def backtest_camada34(
    df_maduras: pd.DataFrame,
    *,
    aluguel_default: float = SIM_ALUGUEL_MES,
) -> CamadaBacktest:
    """Camada 3+4 (DRE) dado ALUNOS REAIS. Sem LOO (deterministico).

    Para cada unidade: churn_fracao=_churn_para_fracao(churn_steady);
    alunos_maturidade=_alunos_maturidade_de_pagantes(pagantes_steady_state, churn_fracao);
    ticket,fb=_ticket_efetivo(ticket_steady);
    res=viabilidade(alunos_maturidade, metragem, aluguel_default, ticket, churn=churn_fracao,
                    alunos_agregadores=0.0).
    Compara res.faturamento_mensal_steady vs faturamento real. baseline = media global do
    faturamento real. flag_extrapolacao_pct=NaN (sem modelo calibrado). aluguel_estimado=True.
    """
    faltando = set(COLS_CAMADA34) - set(df_maduras.columns)
    if faltando:
        raise ValueError(f"Colunas ausentes para Camada 3+4: {faltando}")

    pagantes = pd.to_numeric(df_maduras["pagantes_steady_state"], errors="coerce")
    metragem = pd.to_numeric(df_maduras["metragem"], errors="coerce")
    ticket_col = pd.to_numeric(df_maduras["ticket_steady"], errors="coerce")
    churn_col = pd.to_numeric(df_maduras["churn_steady"], errors="coerce")
    faturamento_real = pd.to_numeric(df_maduras["faturamento"], errors="coerce")

    real_list: list[float] = []
    pred_list: list[float] = []
    n_fallback = 0

    for i in range(len(df_maduras)):
        pag_i = pagantes.iloc[i]
        m2_i = metragem.iloc[i]
        fat_real_i = faturamento_real.iloc[i]
        if not (
            np.isfinite(pag_i)
            and pag_i > 0
            and np.isfinite(m2_i)
            and m2_i > 0
            and np.isfinite(fat_real_i)
        ):
            continue

        churn_fracao = _churn_para_fracao(float(churn_col.iloc[i]))
        if not math.isfinite(churn_fracao):
            continue
        alunos = _alunos_maturidade_de_pagantes(float(pag_i), churn_fracao)
        if not math.isfinite(alunos) or alunos <= 0:
            continue
        ticket, fb = _ticket_efetivo(float(ticket_col.iloc[i]))
        if fb:
            n_fallback += 1

        res = viabilidade(
            alunos,
            float(m2_i),
            aluguel_default,
            ticket,
            churn=churn_fracao,
            alunos_agregadores=0.0,
            personal_mes=SIM_PERSONAL_MES_RECEITA,
        )
        real_list.append(float(fat_real_i))
        pred_list.append(float(res.faturamento_mensal_steady))

    real = np.asarray(real_list, dtype=float)
    pred = np.asarray(pred_list, dtype=float)
    n = len(real)

    mape = _mape(real, pred)
    rmse = _rmse(real, pred)
    r2 = _r2(real, pred)
    # Baseline global: previsao = media do faturamento real (constante).
    baseline_pred = (
        np.full(n, float(np.mean(real))) if n else np.asarray([], dtype=float)
    )
    mape_baseline = _mape(real, baseline_pred)

    nota = (
        f"Camada 3+4 (DRE, alunos reais) | n={n} | MAPE={mape:.1%} | RMSE=R${rmse:,.0f} | "
        f"R2(vs media)={r2:+.3f} | MAPE_baseline={mape_baseline:.1%}. Confound: agregadores "
        "zerados -> faturamento previsto SUBESTIMA o real (balcao + personal apenas); aluguel "
        f"fixo SIM_ALUGUEL_MES=R${aluguel_default:,.0f} (nao afeta faturamento bruto). "
        f"ticket fallback em {n_fallback} linha(s)."
    )
    return CamadaBacktest(
        nome="camada34",
        n=n,
        mape=mape,
        rmse=rmse,
        r2=r2,
        mape_baseline=mape_baseline,
        flag_extrapolacao_pct=float("nan"),
        aluguel_estimado=True,
        n_fallback_ticket=n_fallback,
        nota=nota,
    )


def backtest_end_to_end(
    df_maduras: pd.DataFrame,
    *,
    aluguel_default: float = SIM_ALUGUEL_MES,
) -> CamadaBacktest:
    """LOO Camada 1 -> Camada 3+4. Mede o erro TOTAL quando a demanda NAO e conhecida.

    Reusa _prever_loo_alunos para obter pagantes_pred_loo por unidade; converte em
    alunos_maturidade via churn real da unidade; alimenta viabilidade() com metragem/ticket reais
    e aluguel_default; faturamento previsto vs faturamento real. baseline = media LOO do
    faturamento real. flag_extrapolacao_pct herda de _prever_loo_alunos.
    """
    faltando = (set(COLS_CAMADA1) | set(COLS_CAMADA34)) - set(df_maduras.columns)
    if faltando:
        raise ValueError(f"Colunas ausentes para end-to-end: {faltando}")

    # Reproduz a mascara de validade da Camada 1 para alinhar as demais colunas.
    pop = pd.to_numeric(df_maduras["pop_captacao"], errors="coerce")
    renda = pd.to_numeric(df_maduras["renda_per_capita_captacao"], errors="coerce")
    pagantes = pd.to_numeric(df_maduras["pagantes_steady_state"], errors="coerce")
    mask = (
        pop.notna()
        & (pop > 0)
        & renda.notna()
        & (renda > 0)
        & pagantes.notna()
        & (pagantes > 0)
    )
    df_valido = df_maduras.loc[mask].reset_index(drop=True)

    _real_alunos, pagantes_pred_loo, flags = _prever_loo_alunos(df_maduras)

    metragem = pd.to_numeric(df_valido["metragem"], errors="coerce")
    ticket_col = pd.to_numeric(df_valido["ticket_steady"], errors="coerce")
    churn_col = pd.to_numeric(df_valido["churn_steady"], errors="coerce")
    faturamento_real = pd.to_numeric(df_valido["faturamento"], errors="coerce")

    real_list: list[float] = []
    pred_list: list[float] = []
    flags_usadas: list[bool] = []
    n_fallback = 0

    for i in range(len(df_valido)):
        pag_pred_i = pagantes_pred_loo[i]
        m2_i = metragem.iloc[i]
        fat_real_i = faturamento_real.iloc[i]
        if not (
            np.isfinite(pag_pred_i)
            and pag_pred_i > 0
            and np.isfinite(m2_i)
            and m2_i > 0
            and np.isfinite(fat_real_i)
        ):
            continue
        churn_fracao = _churn_para_fracao(float(churn_col.iloc[i]))
        if not math.isfinite(churn_fracao):
            continue
        alunos = _alunos_maturidade_de_pagantes(float(pag_pred_i), churn_fracao)
        if not math.isfinite(alunos) or alunos <= 0:
            continue
        ticket, fb = _ticket_efetivo(float(ticket_col.iloc[i]))
        if fb:
            n_fallback += 1

        res = viabilidade(
            alunos,
            float(m2_i),
            aluguel_default,
            ticket,
            churn=churn_fracao,
            alunos_agregadores=0.0,
            personal_mes=SIM_PERSONAL_MES_RECEITA,
        )
        real_list.append(float(fat_real_i))
        pred_list.append(float(res.faturamento_mensal_steady))
        flags_usadas.append(flags[i])

    real = np.asarray(real_list, dtype=float)
    pred = np.asarray(pred_list, dtype=float)
    n = len(real)

    mape = _mape(real, pred)
    rmse = _rmse(real, pred)
    r2 = _r2(real, pred)
    # Baseline LOO: previsao do ponto i = media dos N-1 do faturamento real.
    if n > 1:
        total = float(np.sum(real))
        baseline_pred = (total - real) / (n - 1)
    else:
        baseline_pred = np.asarray([], dtype=float)
    mape_baseline = _mape(real, baseline_pred)

    flag_pct = (
        100.0 * (sum(flags_usadas) / len(flags_usadas)) if flags_usadas else float("nan")
    )

    nota = (
        f"End-to-end (Camada 1 LOO -> Camada 3+4) | n={n} | MAPE={mape:.1%} | "
        f"RMSE=R${rmse:,.0f} | R2(vs media)={r2:+.3f} | MAPE_baseline={mape_baseline:.1%} | "
        f"extrapolacao={flag_pct:.0f}%. Mede o erro TOTAL quando a demanda NAO e conhecida; "
        "o NO-GO da Camada 1 propaga -> erro alto esperado. Confounds: agregadores zerados "
        f"(subestima faturamento), aluguel fixo R${aluguel_default:,.0f}, ticket fallback em "
        f"{n_fallback} linha(s)."
    )
    return CamadaBacktest(
        nome="end_to_end",
        n=n,
        mape=mape,
        rmse=rmse,
        r2=r2,
        mape_baseline=mape_baseline,
        flag_extrapolacao_pct=flag_pct,
        aluguel_estimado=True,
        n_fallback_ticket=n_fallback,
        nota=nota,
    )


# ---------- orquestrador + relatorio ----------


def executar_backtest_dim(
    df_maduras: pd.DataFrame,
    *,
    output_path: Path | str | None = None,
    aluguel_default: float = SIM_ALUGUEL_MES,
) -> BacktestResult:
    """Roda as 3 camadas e consolida. Se output_path != None, chama escrever_relatorio.

    NAO le parquet (recebe df pronto). N por camada deve ser ~igual (54 ou proximo).
    """
    c1 = backtest_camada1(df_maduras)
    c34 = backtest_camada34(df_maduras, aluguel_default=aluguel_default)
    ete = backtest_end_to_end(df_maduras, aluguel_default=aluguel_default)

    nota_consolidada = (
        "Backtest honesto out-of-sample (BLK-DIM-06). Alvo = dado REAL (pagantes/faturamento), "
        "nunca saida do proprio simulador. "
        f"Camada 1 LOO: MAPE={c1.mape:.1%} (vs baseline media {c1.mape_baseline:.1%}, "
        f"R2={c1.r2:+.3f}). "
        f"Camada 3+4 (alunos reais): MAPE={c34.mape:.1%} (vs baseline {c34.mape_baseline:.1%}, "
        f"R2={c34.r2:+.3f}). "
        f"End-to-end: MAPE={ete.mape:.1%} (vs baseline {ete.mape_baseline:.1%}, "
        f"R2={ete.r2:+.3f}). "
        "Leitura: MAPE do modelo > MAPE do baseline => o motor e pior que o chute ingenuo da "
        "media; NO-GO da Camada 1 (BLK-DIM-01R) propaga ao end-to-end. Erro alto e o resultado "
        "MEDIDO e esperado, nao defeito. Confounds: aluguel default, agregadores zerados, N=54 "
        "pequeno (LOO instavel). READ-ONLY sobre o M1 (DEC-001/DEC-008)."
    )

    result = BacktestResult(
        camada1=c1,
        camada34=c34,
        end_to_end=ete,
        n_unidades_entrada=int(len(df_maduras)),
        aluguel_default=float(aluguel_default),
        nota_consolidada=nota_consolidada,
    )

    if output_path is not None:
        escrever_relatorio(result, output_path)

    return result


def escrever_relatorio(result: BacktestResult, path: Path | str) -> None:
    """Materializa data/analysis/backtest_dim.md (gitignored). NAO chamada em teste unitario.

    Tabela por camada (MAPE/RMSE/R2/N/%extrapolacao/MAPE_baseline), secao de confounds
    (aluguel SIM_ALUGUEL_MES default; agregadores=0; N=54; NO-GO Camada 1), nota honesta
    consolidada. READ-ONLY sobre o M1.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    def _f(v: float, pct: bool = False) -> str:
        if not math.isfinite(v):
            return "n/d"
        return f"{v:.1%}" if pct else f"{v:.4g}"

    linhas: list[str] = []
    linhas.append("# Backtest honesto out-of-sample do motor de dimensionamento -- BLK-DIM-06")
    linhas.append("")
    linhas.append(
        "Backtest out-of-sample que roda o motor (Camada 1 aderencia + Camada 3+4 simulador "
        "DRE) sobre os maduros REAIS. O alvo e SEMPRE o dado real (`pagantes_steady_state`, "
        "`faturamento`), nunca uma saida do proprio simulador -- corrige o in-sample disfarcado "
        "do spike. READ-ONLY sobre o M1 (DEC-001/DEC-008); `aderencia.py` e `simulador.py` "
        "congelados."
    )
    linhas.append("")
    linhas.append(f"N de unidades na entrada: **{result.n_unidades_entrada}**.")
    linhas.append("")
    linhas.append("## Metricas por camada")
    linhas.append("")
    linhas.append(
        "| camada | N | MAPE | RMSE | R2 (vs media) | MAPE_baseline | % extrapolacao |"
    )
    linhas.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for c in (result.camada1, result.camada34, result.end_to_end):
        ext = _f(c.flag_extrapolacao_pct, pct=False)
        ext = f"{ext}%" if ext != "n/d" else "n/d"
        linhas.append(
            f"| {c.nome} | {c.n} | {_f(c.mape, pct=True)} | {_f(c.rmse)} | "
            f"{_f(c.r2)} | {_f(c.mape_baseline, pct=True)} | {ext} |"
        )
    linhas.append("")
    linhas.append(
        "Nota: o N por camada deve ser ~igual (54 ou proximo). Camada 3+4 nao tem "
        "% extrapolacao (sem modelo calibrado)."
    )
    linhas.append("")
    linhas.append("## Leitura honesta (modelo vs baseline da media)")
    linhas.append("")
    linhas.append(
        "Regra: **se MAPE do modelo > MAPE do baseline -> o motor e pior que o chute ingenuo "
        "da media**. O `R2 (vs media)` ja e a mesma comparacao em outra unidade (R2 < 0 = pior "
        "que a media). NO-GO / erro alto sao resultados VALIDOS e esperados."
    )
    linhas.append("")
    linhas.append("## Confounds documentados")
    linhas.append("")
    linhas.append(
        f"1. **Aluguel nao disponivel por unidade** -> `SIM_ALUGUEL_MES`="
        f"R${result.aluguel_default:,.0f} default (`aluguel_estimado=True`). So afeta "
        "EBITDA/payback, NAO o faturamento bruto -- a metrica central (faturamento) nao e "
        "contaminada."
    )
    linhas.append(
        "2. **Agregadores zerados** no backtest (`alunos_agregadores=0`): "
        "`pagantes_steady_state` e BALCAO. O faturamento previsto SUBESTIMA o real (que inclui "
        "agregadores + personal). Personal mantido no default real (R$5.000)."
    )
    linhas.append(
        f"3. **N pequeno** ({result.n_unidades_entrada}): LOO instavel; intervalo amplo."
    )
    linhas.append(
        "4. **Camada 1 NO-GO** (`r2_loo_log=-0.0134` no BLK-DIM-01R): o erro end-to-end alto e "
        "ESPERADO -- a demanda nao e calibravel so com pop+renda; o erro propaga."
    )
    linhas.append(
        f"5. **Ticket fallback** (`SIM_MENSALIDADE_BALCAO`={SIM_MENSALIDADE_BALCAO}) em "
        f"camada34={result.camada34.n_fallback_ticket} / "
        f"end_to_end={result.end_to_end.n_fallback_ticket} linha(s)."
    )
    linhas.append("")
    linhas.append("## Notas por camada")
    linhas.append("")
    for c in (result.camada1, result.camada34, result.end_to_end):
        linhas.append(f"- **{c.nome}**: {c.nota}")
    linhas.append("")
    linhas.append("## Nota consolidada")
    linhas.append("")
    linhas.append(result.nota_consolidada)
    linhas.append("")

    path.write_text("\n".join(linhas), encoding="utf-8")


__all__ = [
    "CamadaBacktest",
    "BacktestResult",
    "backtest_camada1",
    "backtest_camada34",
    "backtest_end_to_end",
    "executar_backtest_dim",
    "escrever_relatorio",
    "COLS_CAMADA1",
    "COLS_CAMADA34",
    "N_MIN_BACKTEST",
]


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    _df = pd.read_parquet(Path("data/staging/base_calibracao_maduras.parquet"))
    _res = executar_backtest_dim(
        _df, output_path=Path("data/analysis/backtest_dim.md")
    )
    print(_res.nota_consolidada)
