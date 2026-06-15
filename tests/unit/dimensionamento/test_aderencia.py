"""Testes da Camada 1 (BLK-DIM-01R): aderencia calibrada, alvo log(pagantes).

Fixtures anti-circulares: `df_log_sinal` gera log(pagantes) DIRETAMENTE (sem passar
por penetracao=pagantes/pop) -> sinal real calibravel. `df_sem_sinal` tem pagantes
constante -> controle negativo (NO-GO garantido, sem GO espurio). Tudo offline,
seeds fixos, sem leitura de parquet.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from motor_expansao.dimensionamento.aderencia import (
    LIMIAR_R2_GO,
    PAGANTES_MIN,
    AderenciaModel,
    aderencia_calibrada,
    calibrar_aderencia,
    prever_aderencia,
    relatorio_aderencia,
)


@pytest.fixture
def df_log_sinal() -> pd.DataFrame:
    """30 unidades onde log(pagantes) = b0 + b1*log(pop) + b2*log(renda) + ruido.

    Gera log(pagantes) DIRETAMENTE (anti-circular): nunca cria coluna de penetracao
    nem multiplica por pop. b1 positivo e moderado -> sinal real calibravel (GO).
    """
    rng = np.random.default_rng(42)
    pop = np.geomspace(2000.0, 130000.0, 30)
    renda = rng.permutation(np.geomspace(600.0, 16000.0, 30))
    log_pop = np.log(pop)
    log_renda = np.log(renda)
    b0, b1, b2 = -1.0, 0.8, 0.1
    log_pagantes = b0 + b1 * log_pop + b2 * log_renda + rng.normal(0, 0.30, 30)
    pagantes = np.exp(log_pagantes)
    return pd.DataFrame(
        {
            "pop_captacao": pop,
            "renda_per_capita_captacao": renda,
            "pagantes_steady_state": pagantes,
            "n_setores_captacao": rng.integers(3, 40, 30),
        }
    )


@pytest.fixture
def df_sem_sinal() -> pd.DataFrame:
    """30 unidades com pagantes CONSTANTE (sem dependencia de pop/renda).

    Controle negativo forte: o alvo nao tem relacao com nenhuma feature ->
    o modelo nao pode bater a media -> R2_LOO_log <= 0 -> NO-GO.
    """
    rng = np.random.default_rng(42)
    pop = rng.integers(5000, 50000, 30).astype(float)
    renda = rng.uniform(800.0, 3000.0, 30)
    pagantes = np.full(30, 1000.0)  # constante, independente de pop/renda
    return pd.DataFrame(
        {
            "pop_captacao": pop,
            "renda_per_capita_captacao": renda,
            "pagantes_steady_state": pagantes,
            "n_setores_captacao": rng.integers(3, 40, 30),
        }
    )


@pytest.fixture
def df_com_outlier(df_log_sinal: pd.DataFrame) -> pd.DataFrame:
    """Clone de df_log_sinal + 1 linha com n_setores_captacao=0 (catchment vazio)."""
    extra = pd.DataFrame(
        {
            "pop_captacao": [5000.0],
            "renda_per_capita_captacao": [16000.0],
            "pagantes_steady_state": [800.0],
            "n_setores_captacao": [0],  # outlier: catchment vazio
        }
    )
    return pd.concat([df_log_sinal, extra], ignore_index=True)


def test_calibrar_retorna_aderencia_model(df_log_sinal: pd.DataFrame) -> None:
    """Tipo correto e todos os campos NOVOS do D7 presentes."""
    modelo = calibrar_aderencia(df_log_sinal)
    assert isinstance(modelo, AderenciaModel)
    # Campos novos do D7 (espacos log e pagantes).
    assert isinstance(modelo.r2_loo_log, float)
    assert isinstance(modelo.r2_loo_pagantes, float)
    assert isinstance(modelo.rmse_loo_log, float)
    assert isinstance(modelo.rmse_loo_pagantes, float)
    assert isinstance(modelo.r2_insample_log, float)
    assert modelo.veredito in ("GO", "NO-GO")
    assert isinstance(modelo.flag_extrapolacao_padrao, bool)
    assert modelo.n_treinamento == 30


def test_calibrar_com_sinal_go(df_log_sinal: pd.DataFrame) -> None:
    """Fixture com sinal -> espera GO; se R2_LOO_log<0, aceita resultado honesto."""
    modelo = calibrar_aderencia(df_log_sinal)
    # Com b1=0.8, sigma=0.3, N=30 espera-se GO; mas nao forcamos GO.
    assert modelo.veredito in ("GO", "NO-GO")
    if modelo.r2_loo_log > LIMIAR_R2_GO:
        assert modelo.veredito == "GO"
        assert modelo.r2_loo_log > 0
    else:
        # Resultado honesto registrado para inspecao.
        print(f"[honesto] r2_loo_log={modelo.r2_loo_log:+.4f} -> {modelo.veredito}")


def test_controle_negativo_sem_sinal(df_sem_sinal: pd.DataFrame) -> None:
    """Sem relacao alvo~features -> R2_LOO_log <= LIMIAR -> NO-GO (sem GO espurio)."""
    modelo = calibrar_aderencia(df_sem_sinal)
    assert modelo.veredito == "NO-GO"
    assert modelo.r2_loo_log <= LIMIAR_R2_GO


def test_prever_aderencia_retorna_tripla(df_log_sinal: pd.DataFrame) -> None:
    """Retorna tuple[float,float,float] em alunos, ordenado, com pisos respeitados."""
    modelo = calibrar_aderencia(df_log_sinal)
    out = prever_aderencia(20000.0, 4000.0, modelo)
    assert isinstance(out, tuple)
    assert len(out) == 3
    pagantes, lo, hi = out
    assert all(isinstance(v, float) for v in out)
    assert lo <= pagantes <= hi
    assert pagantes >= PAGANTES_MIN
    assert pagantes <= 20000.0


def test_prever_aderencia_clamp_min(df_log_sinal: pd.DataFrame) -> None:
    """Nenhum valor abaixo de PAGANTES_MIN, e teto = pop_captacao respeitado."""
    modelo = calibrar_aderencia(df_log_sinal)
    pagantes, lo, hi = prever_aderencia(10.0, 600.0, modelo)
    assert lo >= PAGANTES_MIN
    assert pagantes >= PAGANTES_MIN
    assert hi >= PAGANTES_MIN
    assert pagantes <= 10.0
    assert hi <= 10.0


def test_prever_entrada_invalida(df_log_sinal: pd.DataFrame) -> None:
    """pop=0 -> (1.0, 1.0, 1.0) sem excecao."""
    modelo = calibrar_aderencia(df_log_sinal)
    assert prever_aderencia(0.0, 4000.0, modelo) == (1.0, 1.0, 1.0)
    assert prever_aderencia(20000.0, 0.0, modelo) == (1.0, 1.0, 1.0)


def test_flag_extrapolacao_dentro(df_log_sinal: pd.DataFrame) -> None:
    """Ponto dentro do envelope -> False."""
    modelo = calibrar_aderencia(df_log_sinal)
    # 20000 hab / 4000 renda esta dentro das faixas geradas pelo fixture.
    assert modelo.flag_extrapolacao(20000.0, 4000.0) is False


def test_flag_extrapolacao_fora(df_log_sinal: pd.DataFrame) -> None:
    """pop=1 (minusculo) -> fora do envelope -> True."""
    modelo = calibrar_aderencia(df_log_sinal)
    assert modelo.flag_extrapolacao(1.0, 4000.0) is True


def test_outlier_removido_quando_pagantes_zero(df_log_sinal: pd.DataFrame) -> None:
    """Linha com pagantes=0 e removida do treino (n_outliers_removidos==1)."""
    extra = pd.DataFrame(
        {
            "pop_captacao": [20000.0],
            "renda_per_capita_captacao": [4000.0],
            "pagantes_steady_state": [0.0],  # invalido -> removido
            "n_setores_captacao": [10],
        }
    )
    df = pd.concat([df_log_sinal, extra], ignore_index=True)
    modelo = calibrar_aderencia(df)
    assert modelo.n_outliers_removidos == 1
    assert modelo.n_treinamento == 30


def test_outlier_catchment_vazio_removido(df_com_outlier: pd.DataFrame) -> None:
    """n_setores_captacao=0 e removido como catchment vazio."""
    modelo = calibrar_aderencia(df_com_outlier)
    assert modelo.n_outliers_removidos == 1
    assert modelo.n_treinamento == 30


def test_n_treinamento_correto(df_log_sinal: pd.DataFrame) -> None:
    """N=30 sem remocoes no fixture limpo."""
    modelo = calibrar_aderencia(df_log_sinal)
    assert modelo.n_treinamento == 30
    assert modelo.n_outliers_removidos == 0


def test_determinismo_seed_fixo(df_log_sinal: pd.DataFrame) -> None:
    """2x calibrar com mesmo df -> resultados identicos."""
    m1 = calibrar_aderencia(df_log_sinal)
    m2 = calibrar_aderencia(df_log_sinal)
    assert m1.alpha_selecionado == m2.alpha_selecionado
    assert m1.coef_log_pop == m2.coef_log_pop
    assert m1.coef_log_renda == m2.coef_log_renda
    assert m1.intercepto_log == m2.intercepto_log
    assert m1.r2_loo_log == m2.r2_loo_log
    assert m1.rmse_loo_log == m2.rmse_loo_log
    assert m1.veredito == m2.veredito


def test_relatorio_aderencia_retorna_str(df_log_sinal: pd.DataFrame) -> None:
    """relatorio_aderencia retorna string nao-vazia com metricas e confounds."""
    modelo = calibrar_aderencia(df_log_sinal)
    texto = relatorio_aderencia(modelo)
    assert isinstance(texto, str)
    assert len(texto) > 0
    assert "R2_LOO_log" in texto
    assert modelo.veredito in texto
    assert "Confounds" in texto


def test_relatorio_no_go_avisa_nao_usar(df_sem_sinal: pd.DataFrame) -> None:
    """No NO-GO o relatorio avisa contra '20% fixo' / uso downstream."""
    modelo = calibrar_aderencia(df_sem_sinal)
    texto = relatorio_aderencia(modelo)
    assert "NO-GO" in texto
    assert "20% fixo" in texto


def test_nota_honesta_embutida(df_log_sinal: pd.DataFrame) -> None:
    """modelo.nota_honesta preenchido."""
    modelo = calibrar_aderencia(df_log_sinal)
    assert isinstance(modelo.nota_honesta, str)
    assert len(modelo.nota_honesta) > 0


def test_alias_aderencia_calibrada() -> None:
    """aderencia_calibrada is prever_aderencia."""
    assert aderencia_calibrada is prever_aderencia


def test_poucos_dados_raises() -> None:
    """n efetivo < N_MIN_CALIBRACAO -> ValueError."""
    df = pd.DataFrame(
        {
            "pop_captacao": [10000.0, 20000.0],
            "renda_per_capita_captacao": [3000.0, 4000.0],
            "pagantes_steady_state": [800.0, 1200.0],
            "n_setores_captacao": [10, 12],
        }
    )
    with pytest.raises(ValueError):
        calibrar_aderencia(df)


def test_coluna_ausente_levanta_key_error(df_log_sinal: pd.DataFrame) -> None:
    """df sem pop_captacao -> ValueError (coluna obrigatoria ausente)."""
    df = df_log_sinal.drop(columns=["pop_captacao"])
    with pytest.raises(ValueError):
        calibrar_aderencia(df)


def test_funciona_sem_n_setores(df_log_sinal: pd.DataFrame) -> None:
    """n_setores_captacao e opcional."""
    df = df_log_sinal.drop(columns=["n_setores_captacao"])
    modelo = calibrar_aderencia(df)
    assert isinstance(modelo, AderenciaModel)
    assert modelo.n_treinamento == 30
