"""BLK-DIM-06: testes offline (seed-fixo, sem I/O) do backtest honesto out-of-sample.

Fixtures sinteticas no schema de `base_calibracao_maduras` com as colunas que cada camada
exige. `churn_steady` em PERCENTUAL para exercitar a conversao. O `faturamento` real e gerado
de forma INDEPENDENTE do simulador (proxy realista), nunca por viabilidade() -> anti-circular.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from motor_expansao.dimensionamento.backtest_dim import (
    BacktestResult,
    CamadaBacktest,
    _alunos_maturidade_de_pagantes,
    _churn_para_fracao,
    backtest_camada1,
    backtest_camada34,
    backtest_end_to_end,
    escrever_relatorio,
    executar_backtest_dim,
)


@pytest.fixture
def df_maduras_sintetico() -> pd.DataFrame:
    """8 unidades plausiveis. pop/renda log-espacados; pagantes ~ pop^0.7 + ruido.

    churn_steady em PERCENTUAL (2.0-6.0). ticket_steady, metragem, faturamento reais-plausiveis.
    n=8 garante treino LOO >= 5 (calibrar_aderencia exige N_MIN_CALIBRACAO=5).
    faturamento gerado de forma INDEPENDENTE do simulador (proxy realista), nunca por viabilidade().
    """
    rng = np.random.default_rng(42)
    n = 8
    pop = np.geomspace(8000.0, 90000.0, n)
    renda = rng.permutation(np.geomspace(1500.0, 9000.0, n))
    pagantes = np.exp(-1.0 + 0.7 * np.log(pop) + rng.normal(0, 0.15, n))  # ~250-1200
    churn_pct = rng.uniform(2.0, 6.0, n)  # PERCENTUAL (armadilha)
    ticket = rng.uniform(110.0, 180.0, n)
    metragem = rng.uniform(1200.0, 2200.0, n)
    # faturamento real-proxy: balcao + agr + personal (NAO via simulador) -> evita circularidade
    faturamento = pagantes * ticket * 0.98 + 651 * 82 * 0.98 + 5000 + rng.normal(0, 8000, n)
    return pd.DataFrame(
        {
            "unidade": [f"U{i}" for i in range(n)],
            "uf": ["SP"] * n,
            "pagantes_steady_state": pagantes,
            "pop_captacao": pop,
            "renda_per_capita_captacao": renda,
            "n_setores_captacao": rng.integers(5, 40, n).astype(float),
            "churn_steady": churn_pct,
            "ticket_steady": ticket,
            "metragem": metragem,
            "faturamento": faturamento,
        }
    )


@pytest.fixture
def df_ticket_faltante(df_maduras_sintetico: pd.DataFrame) -> pd.DataFrame:
    """Uma linha com ticket_steady invalido (<=0) para exercitar o fallback."""
    df = df_maduras_sintetico.copy()
    df.loc[0, "ticket_steady"] = 0.0
    return df


def test_backtest_camada1_retorna_metricas(df_maduras_sintetico):
    r = backtest_camada1(df_maduras_sintetico)
    assert isinstance(r, CamadaBacktest)
    assert r.nome == "camada1"
    assert r.n == 8  # todas validas
    assert math.isfinite(r.mape) and r.mape >= 0
    assert math.isfinite(r.mape_baseline)
    assert 0.0 <= r.flag_extrapolacao_pct <= 100.0


def test_backtest_camada34_corrige_churn_percentual(df_maduras_sintetico):
    # churn em PERCENTUAL (2.0-6.0) deve virar fracao na chamada ao simulador.
    r = backtest_camada34(df_maduras_sintetico)
    assert r.nome == "camada34"
    # Se o churn NAO tivesse sido convertido (ex.: 3.8), alunos = pag/(1-3.8) < 0 -> faturamento
    # absurdo/negativo, levando MAPE a explodir. Aqui o MAPE deve ficar finito e razoavel.
    assert math.isfinite(r.mape)
    assert r.mape < 5.0  # MAPE razoavel; churn convertido corretamente
    # E o helper dedicado: 2.0% -> 0.02, 6.0% -> 0.06
    assert _churn_para_fracao(2.0) == pytest.approx(0.02)
    assert _churn_para_fracao(6.0) == pytest.approx(0.06)


def test_backtest_camada34_mape_finito(df_maduras_sintetico):
    r = backtest_camada34(df_maduras_sintetico)
    assert r.nome == "camada34"
    assert math.isfinite(r.mape) and not math.isnan(r.mape)
    assert math.isinf(r.mape) is False
    assert r.aluguel_estimado is True
    assert r.n == 8


def test_backtest_endtoend_retorna_metricas(df_maduras_sintetico):
    r = backtest_end_to_end(df_maduras_sintetico)
    assert r.nome == "end_to_end"
    assert math.isfinite(r.mape)
    assert math.isfinite(r.r2)
    assert r.aluguel_estimado is True


def test_backtest_baseline_comparacao(df_maduras_sintetico):
    # o backtest expoe o MAPE do baseline da media para comparacao honesta
    r = backtest_end_to_end(df_maduras_sintetico)
    assert math.isfinite(r.mape_baseline) and r.mape_baseline >= 0
    # ambos sao MAPEs comparaveis (mesma unidade); o teste so garante que existem e sao finitos
    assert r.mape >= 0 and r.mape_baseline >= 0


def test_flag_extrapolacao_presente(df_maduras_sintetico):
    r1 = backtest_camada1(df_maduras_sintetico)
    rete = backtest_end_to_end(df_maduras_sintetico)
    # camada1 e end_to_end tem flag_extrapolacao_pct numerico em [0,100]
    assert 0.0 <= r1.flag_extrapolacao_pct <= 100.0
    assert 0.0 <= rete.flag_extrapolacao_pct <= 100.0


def test_sem_dado_autogerado(df_maduras_sintetico):
    """O alvo do backtest e SEMPRE o `faturamento` real do df, nunca uma saida do simulador.

    Garante anti-circularidade: se alterarmos o faturamento real, o MAPE muda (logo ele LE o
    campo real, nao recalcula via simulador).
    """
    r_real = backtest_camada34(df_maduras_sintetico)
    df_mut = df_maduras_sintetico.copy()
    df_mut["faturamento"] = df_mut["faturamento"] * 10.0  # altera o ALVO real
    r_mut = backtest_camada34(df_mut)
    assert r_real.mape != pytest.approx(r_mut.mape)  # o alvo real entra na metrica


def test_churn_helper_percentual_e_fracao():
    # Percentual (>1) -> divide por 100
    assert _churn_para_fracao(2.0) == pytest.approx(0.02)
    assert _churn_para_fracao(6.0) == pytest.approx(0.06)
    assert _churn_para_fracao(3.8) == pytest.approx(0.038)
    # Ja em fracao (<=1) -> retorna direto
    assert _churn_para_fracao(0.05) == pytest.approx(0.05)
    assert _churn_para_fracao(1.0) == pytest.approx(1.0)
    # NaN propaga
    assert math.isnan(_churn_para_fracao(float("nan")))


def test_alunos_para_maturidade_inversao():
    # alunos_maturidade = pagantes / (1 - churn_fracao) > pagantes
    am = _alunos_maturidade_de_pagantes(900.0, 0.06)
    assert am == pytest.approx(900.0 / 0.94)
    assert am > 900.0  # nunca negativo/menor
    # churn >= 100% (1 - churn <= 0) -> NaN, nunca negativo
    assert math.isnan(_alunos_maturidade_de_pagantes(900.0, 1.0))
    assert math.isnan(_alunos_maturidade_de_pagantes(900.0, 1.5))


def test_ticket_fallback_contado(df_ticket_faltante):
    r = backtest_camada34(df_ticket_faltante)
    assert r.n_fallback_ticket == 1


def test_escrever_relatorio_cria_arquivo(df_maduras_sintetico, tmp_path):
    res = executar_backtest_dim(df_maduras_sintetico)
    assert isinstance(res, BacktestResult)
    p = tmp_path / "backtest_dim.md"
    escrever_relatorio(res, p)
    assert p.exists() and p.read_text(encoding="utf-8").strip()
