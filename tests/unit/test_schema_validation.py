from __future__ import annotations

import h3
import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from motor_expansao.dashboard.constants import REQUIRED_COLUMNS
from motor_expansao.dashboard.schemas import (
    _SCORE_NUMERIC_OPTIONAL,
    _SCORE_RANGE_OPTIONAL,
    _SCORE_RANGE_REQUIRED,
    SchemaValidationError,
    validate_dashboard_frame,
)

# Coordenadas reais -> hex_id H3 res 7 validos.
_COORDS = [
    (-23.5505, -46.6333),  # Sao Paulo
    (-22.9068, -43.1729),  # Rio de Janeiro
    (-15.7939, -47.8828),  # Brasilia
]
_HEXES = [h3.latlng_to_cell(lat, lng, 7) for lat, lng in _COORDS]


def _valid_frame() -> pd.DataFrame:
    """Frame minimo valido com TODAS as REQUIRED_COLUMNS e 3 linhas."""
    data: dict[str, object] = {
        "hex_id": list(_HEXES),
        "lat": [c[0] for c in _COORDS],
        "lng": [c[1] for c in _COORDS],
        "uf": ["SP", "RJ", "DF"],
        "cidade": ["Sao Paulo", "Rio de Janeiro", "Brasilia"],
        "regiao": ["Sudeste", "Sudeste", "Centro-Oeste"],
        "score_priorizacao": [80.0, 50.0, 95.0],
        "hex_score_estrutural": [75.0, 48.0, 90.0],
        "ajuste_executivo": [5.0, 2.0, 5.0],
        "faixa_oportunidade": ["alta", "media", "prioridade_maxima"],
        "flag_viavel": [True, True, True],
        "flag_prioridade": [True, False, True],
        "rank_brasil": [1, 100, 2],
        "rank_uf": [1, 10, 1],
        "rank_cidade": [1, 5, 1],
        "renda_per_capita": [6000.0, 5000.0, 7000.0],
        "populacao_proxy": [5000, 4000, 6000],
    }
    df = pd.DataFrame(data)
    # Garante que nenhuma REQUIRED_COLUMN ficou de fora do builder.
    assert set(REQUIRED_COLUMNS) <= set(df.columns)
    return df[REQUIRED_COLUMNS]


def test_caso_feliz_nao_levanta():
    df = _valid_frame()
    validate_dashboard_frame(df, source="ok")  # nao deve levantar


def test_caso_feliz_nao_muta_dataframe():
    df = _valid_frame()
    antes = df.copy(deep=True)
    validate_dashboard_frame(df, source="ok")
    assert_frame_equal(df, antes)  # valores e dtypes identicos


def test_caso_feliz_com_nan_em_score_tolerado():
    df = _valid_frame()
    df.loc[1, "score_priorizacao"] = np.nan  # NaN legitimo num score obrigatorio
    validate_dashboard_frame(df, source="ok")  # NaN nao deve derrubar


def test_score_opcional_presente_com_nan_tolerado():
    df = _valid_frame()
    df["score_oportunidade_residual"] = [70.0, np.nan, 40.0]
    validate_dashboard_frame(df, source="ok")


def test_score_opcional_fora_de_faixa_levanta():
    df = _valid_frame()
    df["score_oportunidade_residual"] = [70.0, 200.0, 40.0]
    with pytest.raises(SchemaValidationError, match="score_oportunidade_residual"):
        validate_dashboard_frame(df, source="enriquecido")


def test_score_expansao_hibrido_acima_de_100_passa():
    # Teto tecnico de desenho: chave lexicografica = M1 (<=100) + micro-desempate <=0.001.
    df = _valid_frame()
    df["score_expansao_hibrido"] = [100.001, 100.0, 99.999]
    validate_dashboard_frame(df, source="enriquecido")  # nao deve levantar


def test_score_expansao_hibrido_nao_conversivel_levanta():
    df = _valid_frame()
    df["score_expansao_hibrido"] = ["x", "y", "z"]
    with pytest.raises(
        SchemaValidationError, match="nao e conversivel a numerico"
    ) as exc:
        validate_dashboard_frame(df, source="enriquecido")
    assert "score_expansao_hibrido" in str(exc.value)


def test_score_expansao_hibrido_com_nan_tolerado():
    df = _valid_frame()
    df["score_expansao_hibrido"] = [100.001, np.nan, 99.5]
    validate_dashboard_frame(df, source="enriquecido")  # NaN tolerado, nao levanta


def test_score_expansao_hibrido_fora_de_required():
    # Sanidade de design: o campo e chave de ordenacao (numerico/sem faixa), nao score [0,100].
    assert "score_expansao_hibrido" in _SCORE_NUMERIC_OPTIONAL
    assert "score_expansao_hibrido" not in _SCORE_RANGE_OPTIONAL
    assert "score_expansao_hibrido" not in _SCORE_RANGE_REQUIRED


def test_coluna_obrigatoria_faltante_levanta():
    df = _valid_frame().drop(columns=["hex_id"])
    with pytest.raises(SchemaValidationError, match="hex_id") as exc:
        validate_dashboard_frame(df, source="arquivo.parquet")
    assert "arquivo.parquet" in str(exc.value)


def test_dtype_errado_em_score_levanta():
    df = _valid_frame()
    df["hex_score_estrutural"] = ["abc", "def", "ghi"]
    with pytest.raises(
        SchemaValidationError, match="nao e conversivel a numerico"
    ) as exc:
        validate_dashboard_frame(df, source="origem")
    assert "hex_score_estrutural" in str(exc.value)
    assert "origem" in str(exc.value)


def test_score_fora_de_faixa_superior_levanta():
    df = _valid_frame()
    df.loc[0, "score_priorizacao"] = 150.0
    with pytest.raises(SchemaValidationError, match=r"faixa \[0,100\]") as exc:
        validate_dashboard_frame(df, source="origem")
    assert "score_priorizacao" in str(exc.value)
    assert "max=150" in str(exc.value)


def test_score_fora_de_faixa_inferior_levanta():
    df = _valid_frame()
    df.loc[2, "score_priorizacao"] = -3.0
    with pytest.raises(SchemaValidationError, match="score_priorizacao") as exc:
        validate_dashboard_frame(df, source="origem")
    assert "min=-3" in str(exc.value)


def test_chave_uf_nula_levanta():
    df = _valid_frame()
    df.loc[1, "uf"] = None
    with pytest.raises(SchemaValidationError, match="'uf'") as exc:
        validate_dashboard_frame(df, source="origem")
    assert "nulo" in str(exc.value)


def test_chave_hex_id_nula_levanta():
    df = _valid_frame()
    df.loc[0, "hex_id"] = None
    with pytest.raises(SchemaValidationError, match="'hex_id'") as exc:
        validate_dashboard_frame(df, source="origem")
    assert "nulo" in str(exc.value)


def test_hex_id_invalido_levanta():
    df = _valid_frame()
    df.loc[1, "hex_id"] = "nao_eh_h3"
    with pytest.raises(SchemaValidationError, match="H3") as exc:
        validate_dashboard_frame(df, source="origem")
    assert "nao_eh_h3" in str(exc.value)


def test_frame_vazio_e_noop():
    validate_dashboard_frame(pd.DataFrame(), source="vazio")  # nao deve levantar


def test_frame_none_e_noop():
    validate_dashboard_frame(None, source="none")  # type: ignore[arg-type]


def test_coerencia_score_required_subconjunto_de_required_columns():
    assert set(_SCORE_RANGE_REQUIRED) <= set(REQUIRED_COLUMNS)


def test_score_opcionais_nao_estao_em_required_columns():
    # Sanidade: opcionais sao realmente opcionais (nao redundantes com REQUIRED).
    assert set(_SCORE_RANGE_OPTIONAL).isdisjoint(set(REQUIRED_COLUMNS))
