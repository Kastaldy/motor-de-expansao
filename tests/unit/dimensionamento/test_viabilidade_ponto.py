"""Testes do motor property-first de viabilidade do imovel — BLK-DIM-11.

Fixtures sinteticas em memoria; ZERO leitura de parquet real. Catchment desligado
(setores_df=None) na maioria dos testes do orquestrador para determinismo. A flag de
zona morta e testada diretamente com dicts de catchment sinteticos.
"""

from __future__ import annotations

import math

import pandas as pd

from motor_expansao.dimensionamento.simulador import ViabilidadeResult
from motor_expansao.dimensionamento.viabilidade_ponto import (
    ViabilidadePontoResult,
    analisar_viabilidade_ponto,
    faixa_alunos_por_densidade,
    flag_zona_morta,
    grade_sensibilidade,
)


def _base_comparaveis() -> pd.DataFrame:
    """6 unidades sinteticas; alunos_por_m2 ~0.35..0.70; metragem 900..2100."""
    return pd.DataFrame(
        {
            "unidade": [f"U{i}" for i in range(6)],
            "metragem": [900.0, 1200.0, 1400.0, 1500.0, 1800.0, 2100.0],
            "alunos_por_m2": [0.70, 0.60, 0.55, 0.50, 0.45, 0.35],
        }
    )


def test_faixa_alunos_por_densidade_normal() -> None:
    """Janela estreita +/-20% de 1500 pega >=3 comparaveis; p10<=p50<=p90>0."""
    out = faixa_alunos_por_densidade(1500.0, _base_comparaveis())
    assert out["n_comparaveis"] is not None and out["n_comparaveis"] >= 3
    assert out["faixa_alunos_p10"] is not None
    assert out["faixa_alunos_p50"] is not None
    assert out["faixa_alunos_p90"] is not None
    assert out["faixa_alunos_p10"] <= out["faixa_alunos_p50"] <= out["faixa_alunos_p90"]
    assert out["faixa_alunos_p50"] > 0
    assert math.isfinite(out["faixa_alunos_p50"])


def test_faixa_alunos_alarga_janela() -> None:
    """+/-20% pega so 1 comparavel; o modulo alarga para +/-50% e atinge >=3."""
    base = pd.DataFrame(
        {
            "metragem": [1000.0, 1480.0, 1490.0, 1495.0],
            "alunos_por_m2": [0.50, 0.48, 0.52, 0.49],
        }
    )
    out = faixa_alunos_por_densidade(1000.0, base)
    assert out["n_comparaveis"] is not None and out["n_comparaveis"] >= 3
    assert out["faixa_alunos_p50"] is not None


def test_flag_zona_morta_true() -> None:
    """pop abaixo do minimo dispara a flag e registra o motivo."""
    out = flag_zona_morta({"pop_captacao": 1000.0, "renda_per_capita_captacao": 5000.0})
    assert out["flag_zona_morta"] is True
    assert "pop<5000" in out["motivo_zona_morta"]


def test_flag_zona_morta_false() -> None:
    """pop e renda saudaveis -> flag False, motivo 'ok'."""
    out = flag_zona_morta({"pop_captacao": 50000.0, "renda_per_capita_captacao": 6000.0})
    assert out["flag_zona_morta"] is False
    assert out["motivo_zona_morta"] == "ok"


def test_grade_sensibilidade_shape() -> None:
    """Grade default = 6 alunos x 5 fatores = 30 linhas, colunas e dtype esperados."""
    g = grade_sensibilidade(1500.0, 20000.0, 938.0)
    assert g.shape[0] == 6 * 5 == 30
    assert {"alunos", "aluguel", "fator_aluguel", "margem_liq", "viavel", "payback"} <= set(
        g.columns
    )
    assert g["viavel"].dtype == bool


def test_analisar_viabilidade_ponto_completo() -> None:
    """Orquestrador retorna todos os campos; catchment desligado -> flags geo None."""
    r = analisar_viabilidade_ponto(
        -23.9,
        -46.3,
        1500.0,
        20000.0,
        938.0,
        base_calibracao_df=_base_comparaveis(),
        setores_df=None,
    )
    assert isinstance(r, ViabilidadePontoResult)
    assert isinstance(r.viabilidade, ViabilidadeResult)
    assert r.faixa_alunos_p50 is not None
    assert r.n_comparaveis is not None
    assert r.flag_zona_morta is None
    assert r.pop_captacao is None
    assert r.aluguel_teto_calculado >= 0
    assert math.isfinite(r.aluguel_teto_calculado)
    assert isinstance(r.grade_sensibilidade, pd.DataFrame)
    assert not r.grade_sensibilidade.empty
    assert r.demanda_premissa == 938.0


def test_demanda_fonte_sempre_premissa_explicita() -> None:
    """GUARDRAIL: demanda_fonte e sempre 'premissa_explicita'."""
    r = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 938.0, base_calibracao_df=_base_comparaveis()
    )
    assert r.demanda_fonte == "premissa_explicita"


def test_sem_staging_real() -> None:
    """Modos degradados sem nenhum parquet: faixa None, flag geo None."""
    r = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 938.0, base_calibracao_df=None, setores_df=None
    )
    assert isinstance(r, ViabilidadePontoResult)
    assert r.faixa_alunos_p50 is None
    assert r.flag_zona_morta is None


def test_faixa_usa_curva_densidade_nao_geo() -> None:
    """GUARDRAIL anti-geografico: lat/lng diferentes nao mudam faixa, demanda nem margem."""
    base = _base_comparaveis()
    r1 = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 938.0, base_calibracao_df=base, setores_df=None
    )
    r2 = analisar_viabilidade_ponto(
        +1.0, -60.0, 1500.0, 20000.0, 938.0, base_calibracao_df=base, setores_df=None
    )
    assert r1.faixa_alunos_p10 == r2.faixa_alunos_p10
    assert r1.faixa_alunos_p50 == r2.faixa_alunos_p50
    assert r1.faixa_alunos_p90 == r2.faixa_alunos_p90
    assert r1.n_comparaveis == r2.n_comparaveis
    assert r1.demanda_premissa == r2.demanda_premissa
    assert r1.viabilidade.margem_ebitda_pct == r2.viabilidade.margem_ebitda_pct


def test_grade_sensibilidade_margem_decresce_com_aluguel() -> None:
    """Para um mesmo nivel de alunos, fator de aluguel maior reduz a margem_liq."""
    g = grade_sensibilidade(1500.0, 20000.0, 938.0)
    linha = g[g["alunos"] == 800.0].sort_values("fator_aluguel")
    margens = linha["margem_liq"].to_numpy()
    assert (margens[:-1] >= margens[1:]).all()
