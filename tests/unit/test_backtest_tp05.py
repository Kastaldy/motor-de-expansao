"""Testes do re-teste honesto demanda OBSERVADA -> captura (BLK-TP-05).

Usa SEMPRE fixture SINTETICA construida em codigo (NUNCA o parquet/HTML real).
Cobre: GO com sinal forte, NO-GO com ruido puro, IC95 lo<=hi, pct_extrapolacao em [0,100],
R2_insample rotulado, zero-PII, reprodutibilidade com seed fixa, contagem de zeros descartados.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from motor_expansao.demanda_revelada import (
    COLUNAS_PII_PROIBIDAS,
    BacktestTP05Result,
    backtest_demanda_captura,
)
from motor_expansao.demanda_revelada.backtest_tp05 import (
    _ROTULO_INSAMPLE,
    correlacoes_bivariadas,
    preparar_dados,
    relatorio_tp05,
)

N_HEX = 600  # >= 200 -> caminho k=5x5
N_ZEROS = 150  # hexes adicionais com alunos_parceiras == 0


def _fixture_sintetica(*, sinal: bool, seed: int = 7) -> pd.DataFrame:
    """DataFrame sintetico com o contrato de 9 colunas.

    `sinal=True`: alunos_parceiras = funcao monotonica de membros + ruido leve (sinal forte).
    `sinal=False`: alunos_parceiras = ruido puro (sem relacao com as features).
    Inclui N_ZEROS hexes com alunos_parceiras == 0 (zero-inflacao) para testar o descarte.
    """
    rng = np.random.default_rng(seed)
    membros = rng.integers(1, 9000, size=N_HEX).astype(float)
    dist = rng.uniform(150.0, 1_700_000.0, size=N_HEX)
    n_conc = rng.integers(0, 8, size=N_HEX).astype(int)

    if sinal:
        # alunos cresce ~ potencia de membros (relacao log-log forte).
        base = 0.9 * np.log1p(membros) - 0.1 * np.log1p(dist)
        ruido = rng.normal(0.0, 0.25, size=N_HEX)
        alunos = np.maximum(1, np.round(np.expm1(base + ruido)).astype(int))
    else:
        # ruido puro: alunos nao depende de nenhuma feature.
        alunos = rng.integers(1, 5000, size=N_HEX).astype(int)

    df_pos = pd.DataFrame(
        {
            "hex_id": [f"87a{i:012x}" for i in range(N_HEX)],
            "membros": membros.astype("int64"),
            "membros_gt5km_concorrente_lc": rng.integers(0, 100, size=N_HEX).astype("int64"),
            "dist_concorrente_lc_min_m": dist,
            "n_celulas_agregadas": rng.integers(1, 10, size=N_HEX).astype("int64"),
            "n_acad_parceiras": rng.integers(1, 50, size=N_HEX).astype("int64"),
            "alunos_parceiras": alunos.astype("int64"),
            "n_concorrente_lc": n_conc.astype("int64"),
            "versao_contrato": "demanda_revelada_v1",
        }
    )

    # Hexes com alunos_parceiras == 0 (devem ser descartados).
    df_zero = pd.DataFrame(
        {
            "hex_id": [f"87b{i:012x}" for i in range(N_ZEROS)],
            "membros": rng.integers(1, 9000, size=N_ZEROS).astype("int64"),
            "membros_gt5km_concorrente_lc": np.zeros(N_ZEROS, dtype="int64"),
            "dist_concorrente_lc_min_m": rng.uniform(150.0, 1_700_000.0, size=N_ZEROS),
            "n_celulas_agregadas": np.ones(N_ZEROS, dtype="int64"),
            "n_acad_parceiras": np.zeros(N_ZEROS, dtype="int64"),
            "alunos_parceiras": np.zeros(N_ZEROS, dtype="int64"),
            "n_concorrente_lc": rng.integers(0, 8, size=N_ZEROS).astype("int64"),
            "versao_contrato": "demanda_revelada_v1",
        }
    )
    return pd.concat([df_pos, df_zero], ignore_index=True)


def test_go_com_sinal_forte() -> None:
    df = _fixture_sintetica(sinal=True)
    res = backtest_demanda_captura(df)
    assert isinstance(res, BacktestTP05Result)
    assert res.veredito == "GO"
    assert res.go is True
    assert res.r2_oof_log > 0.05
    assert res.ic95_r2_oof[0] > 0.0
    assert res.metodo_validacao == "kfold_5x5"


def test_no_go_com_ruido_puro() -> None:
    df = _fixture_sintetica(sinal=False)
    res = backtest_demanda_captura(df)
    assert res.veredito == "NO-GO"
    assert res.go is False
    # Ruido puro: oof nao supera a media -> R2_oof <= ~0.
    assert res.r2_oof_log <= 0.05


def test_ic95_ordenado() -> None:
    df = _fixture_sintetica(sinal=True)
    res = backtest_demanda_captura(df)
    lo, hi = res.ic95_r2_oof
    assert np.isfinite(lo) and np.isfinite(hi)
    assert lo <= hi


def test_pct_extrapolacao_intervalo() -> None:
    df = _fixture_sintetica(sinal=True)
    res = backtest_demanda_captura(df)
    assert 0.0 <= res.pct_extrapolacao <= 100.0
    # treino == teste (mesmo dump) -> 0% extrapolado.
    assert res.pct_extrapolacao == pytest.approx(0.0)


def test_r2_insample_rotulado_auditoria() -> None:
    df = _fixture_sintetica(sinal=True)
    res = backtest_demanda_captura(df)
    assert isinstance(res.r2_insample, float)
    # O rotulo literal exigido pela DEC-008 aparece na nota e no relatorio.
    assert _ROTULO_INSAMPLE == "apenas auditoria -- NAO usar como desempenho"
    assert _ROTULO_INSAMPLE in res.nota_honesta
    assert _ROTULO_INSAMPLE in relatorio_tp05(res)


def test_zero_pii_em_todas_as_saidas() -> None:
    """Nenhuma coluna PII vaza como NOME (coluna/chave/feature) em qualquer saida.

    A rede anti-PII e por NOME ESTRUTURAL (igual ao `test_zero_pii` da ingestao:
    `set(columns) & COLUNAS_PII_PROIBIDAS`), nao por substring na prosa em PT (rotulos
    curtos como `lat`/`id`/`nome` aparecem dentro de palavras como "plataforma"/"aleatoria").
    """
    df = _fixture_sintetica(sinal=True)
    res = backtest_demanda_captura(df)
    # (a) features/coeficientes expostos nao contem nenhuma coluna proibida.
    assert set(res.coefs.keys()) & COLUNAS_PII_PROIBIDAS == set()
    # (b) chaves de Spearman (features brutas) nao contem coluna proibida.
    assert set(res.spearman.keys()) & COLUNAS_PII_PROIBIDAS == set()
    # (c) chaves do dict de auditoria nao contem coluna proibida.
    assert set(res.auditoria_vazamento.keys()) & COLUNAS_PII_PROIBIDAS == set()
    # (d) o relatorio nao contem PII evidente de identidade (substring forte, nao rotulos curtos).
    rel_baixo = relatorio_tp05(res).lower()
    for forte in ("cpf", "email", "telefone", "employee_id", "company_id", "residencial"):
        assert forte not in rel_baixo, f"PII forte no relatorio: {forte}"


def test_reprodutibilidade_seed_fixa() -> None:
    df = _fixture_sintetica(sinal=True)
    r1 = backtest_demanda_captura(df)
    r2 = backtest_demanda_captura(df)
    assert r1.r2_oof_log == r2.r2_oof_log
    assert r1.ic95_r2_oof == r2.ic95_r2_oof
    assert r1.alpha_selecionado == r2.alpha_selecionado
    assert r1.coefs == r2.coefs
    assert r1.veredito == r2.veredito


def test_n_descartado_zeros_conta_zeros() -> None:
    df = _fixture_sintetica(sinal=True)
    res = backtest_demanda_captura(df)
    assert res.n_descartado_zeros == N_ZEROS
    assert res.n_treinamento == N_HEX
    # range coerente com o subset > 0.
    assert res.range_alunos[0] >= 1.0
    assert res.range_alunos[1] >= res.range_alunos[0]


def test_preparar_dados_e_correlacoes() -> None:
    df = _fixture_sintetica(sinal=True)
    X, y, meta = preparar_dados(df)
    assert X.shape == (N_HEX, 3)
    assert y.shape == (N_HEX,)
    assert meta["n_descartado_zeros"] == N_ZEROS
    corr = correlacoes_bivariadas(df)
    # membros tem sinal forte com o alvo na fixture com sinal.
    rho_membros, _p = corr["membros"]
    assert np.isfinite(rho_membros)
    assert rho_membros > 0.3


def test_erro_sem_positivos() -> None:
    df = _fixture_sintetica(sinal=True)
    df["alunos_parceiras"] = 0
    with pytest.raises(ValueError, match="Nenhum hex"):
        backtest_demanda_captura(df)
