"""Testes da renda media domiciliar por HEX no tooltip do PILOTO WEB (web/server/app.py).

Substitui os testes de `dashboard.components._renda_media_domiciliar_series` — modulo
DELETADO no corte do Streamlit (DEC-022). A implementacao de PRODUCAO agora e a do
backend do piloto: `_derivar` (precedencia da renda de leitura), `_fator_domiciliar`
(moradores x uplift x fator temporal, todos MUNICIPAIS) e `_renda_domiciliar_hex`
(renda de leitura x fator; vazio quando falta renda OU cod_municipio).

READ-ONLY sobre o M1 e HERMETICO: os artefatos de staging (tabela municipal de
uplift/moradores + fator temporal) sao SINTETICOS em tmp_path — nenhum `data/` em
disco. Invariantes preservados do teste antigo: formula (renda_pc x moradores_muni x
uplift_muni x fator_temporal), fallback calibrada -> renda_per_capita (por COLUNA no
piloto; ver nota no teste), cod_municipio ausente/NaN -> vazio (sem estimativa de
nivel UF) e cascata municipio -> mediana UF -> nacional dos fatores. No piloto o
"NaN" do tooltip e servido como None (payload JSON-safe via `_num`).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pytest import approx

from motor_expansao.dashboard import constants as _const

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)

# ---------------------------------------------------------------------------
# Artefatos SINTETICOS de staging + isolamento do modulo constants.
#
# `_fator_temporal_renda()` (lru_cache) chama `_init_renda_domiciliar_paths()`, que
# MUTA `constants.UPLIFT_*_PATH`/`FATOR_TEMPORAL_RENDA_PATH` para `pilot.STAGING_DIR`
# e zera as caches lazy. Os fixtures reapontam STAGING_DIR para tmp_path, registram os
# atributos de `constants` no monkeypatch (restauracao pos-teste) e limpam a lru_cache
# antes E depois — nenhum estado vaza entre testes nem para outros arquivos.
# ---------------------------------------------------------------------------

FATOR_TEMPORAL = 1.25  # sintetico, dentro da faixa plausivel [1.0, 2.0] do artefato

# Fatores municipais resultantes (moradores x uplift x FATOR_TEMPORAL):
#   3550308: 3.2 x 1.5 x 1.25 = 6.0   | 3509502: 2.5 x 1.2 x 1.25 = 3.75
#   3304557: 2.0 x 1.8 x 1.25 = 4.5
_TABELA_MUNICIPIOS = pd.DataFrame(
    {
        "uf": ["SP", "SP", "RJ"],
        "cod_municipio": ["3550308", "3509502", "3304557"],
        "uplift_composicao_final": [1.5, 1.2, 1.8],
        "uplift_confiavel": [True, True, True],
        "moradores_por_domicilio_municipio": [3.2, 2.5, 2.0],
    }
)


def _apontar_staging(monkeypatch: pytest.MonkeyPatch, staging: Path) -> None:
    monkeypatch.setattr(pilot, "STAGING_DIR", staging)
    # Registra os originais: `_init_renda_domiciliar_paths` muta o MODULO constants.
    for attr in (
        "UPLIFT_COMPOSICAO_PATH",
        "UPLIFT_COMPOSICAO_SETOR_PATH",
        "FATOR_TEMPORAL_RENDA_PATH",
    ):
        monkeypatch.setattr(_const, attr, getattr(_const, attr))
    for cache in ("_uplift_cache", "_uplift_uf_cache", "_moradores_cache", "_moradores_uf_cache"):
        monkeypatch.setattr(_const, cache, None)
    pilot._fator_temporal_renda.cache_clear()


@pytest.fixture
def staging_sintetico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Staging com a tabela municipal sintetica + fator temporal 1.25."""
    staging = tmp_path / "staging"
    staging.mkdir()
    _TABELA_MUNICIPIOS.to_parquet(staging / "uplift_renda_domiciliar_municipio.parquet")
    (staging / "fator_temporal_renda.json").write_text(
        json.dumps({"fator_temporal_renda": FATOR_TEMPORAL, "competencia_atual_fim": "202606"}),
        encoding="utf-8",
    )
    _apontar_staging(monkeypatch, staging)
    yield staging
    pilot._fator_temporal_renda.cache_clear()


@pytest.fixture
def staging_vazio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Staging VAZIO (o cenario do CI): tudo cai nos fallbacks nacionais."""
    staging = tmp_path / "staging"
    staging.mkdir()
    _apontar_staging(monkeypatch, staging)
    yield staging
    pilot._fator_temporal_renda.cache_clear()


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "hex_id": ["a", "b", "c"],
            "uf": ["SP", "SP", "RJ"],
            "cod_municipio": ["3550308", "3509502", "3304557"],
            "renda_per_capita_setor_2022_calibrada": [1500.0, 2000.0, np.nan],
            "renda_per_capita": [1400.0, 1900.0, 1700.0],
        }
    )


def _serie_renda_dom(df: pd.DataFrame) -> pd.Series:
    """Renda media domiciliar por linha, pelo MESMO fluxo do endpoint `uf_view`:
    `_derivar` (renda_leitura) -> fator municipal via `_fator_domiciliar` ->
    `_renda_domiciliar_hex` por linha. dtype=object preserva os None do payload."""
    derivado = pilot._derivar(df)
    valores: dict[object, object] = {}
    for idx, linha in derivado.iterrows():
        cod = linha.get("cod_municipio")
        cod_str = None if cod is None or pd.isna(cod) else str(cod)
        fator = pilot._fator_domiciliar(linha.get("uf"), cod_str)
        valores[idx] = pilot._renda_domiciliar_hex(linha, fator)
    return pd.Series(valores, dtype=object)


# ===========================================================================
# Formula e variacao municipal
# ===========================================================================


def test_formula_usa_moradores_e_uplift_municipais(staging_sintetico: Path) -> None:
    assert pilot._fator_domiciliar("SP", "3550308") == approx(6.0)
    assert pilot._fator_domiciliar("SP", "3509502") == approx(3.75)
    r = _serie_renda_dom(_frame())
    assert r.loc[0] == 9000  # 1500 x 6.0 (renda calibrada x fator municipal)
    assert r.loc[1] == 7500  # 2000 x 3.75


def test_varia_por_municipio(staging_sintetico: Path) -> None:
    """Mesma renda per capita, municipios distintos -> fatores distintos -> rendas
    distintas. Com a tabela sintetica os fatores diferem POR CONSTRUCAO (o teste
    antigo, sobre a tabela real, so podia afirmar isso condicionalmente)."""
    df = pd.DataFrame(
        {
            "hex_id": ["a", "b"],
            "uf": ["SP", "SP"],
            "cod_municipio": ["3550308", "3509502"],
            "renda_per_capita_setor_2022_calibrada": [1000.0, 1000.0],
        }
    )
    r = _serie_renda_dom(df)
    assert r.loc[0] == 6000  # 1000 x 6.0
    assert r.loc[1] == 3750  # 1000 x 3.75
    assert r.loc[0] != r.loc[1]


# ===========================================================================
# Fallback de renda (calibrada -> renda_per_capita)
# ===========================================================================


def test_fallback_para_renda_per_capita_quando_coluna_calibrada_ausente(
    staging_sintetico: Path,
) -> None:
    df = _frame().drop(columns=["renda_per_capita_setor_2022_calibrada"])
    r = _serie_renda_dom(df)
    assert r.loc[0] == 8400  # 1400 x 6.0
    assert r.loc[2] == 7650  # 1700 x 4.5 (RJ/3304557)


def test_calibrada_nan_por_linha_vira_none_sem_fallback_por_linha(
    staging_sintetico: Path,
) -> None:
    """CONTRATO DO PILOTO (difere do Streamlit aposentado): a precedencia
    calibrada -> renda_per_capita e por COLUNA (`_derivar` escolhe UMA origem para a
    `renda_leitura`), nao por linha. Linha com calibrada NaN -> tooltip vazio (None),
    e NAO o `renda_per_capita` daquela linha."""
    derivado = pilot._derivar(_frame())
    assert np.isnan(derivado.loc[2, "renda_leitura"])  # nao caiu para 1700
    r = _serie_renda_dom(_frame())
    assert r.loc[2] is None


def test_sem_nenhuma_renda_retorna_none(staging_sintetico: Path) -> None:
    df = _frame().drop(columns=["renda_per_capita_setor_2022_calibrada", "renda_per_capita"])
    r = _serie_renda_dom(df)
    assert all(v is None for v in r)


# ===========================================================================
# Sem municipio resolvido -> None (nunca estimativa de nivel UF)
# ===========================================================================


def test_sem_cod_municipio_retorna_none(staging_sintetico: Path) -> None:
    df = _frame().drop(columns=["cod_municipio"])
    r = _serie_renda_dom(df)
    assert all(v is None for v in r)


def test_cod_municipio_nan_por_linha_retorna_none(staging_sintetico: Path) -> None:
    """Hex sem municipio resolvido (cod_municipio NaN, uf presente) -> None, e NAO uma
    estimativa de nivel UF — mesmo com um fator municipal valido em maos."""
    df = pd.DataFrame(
        {
            "hex_id": ["a", "b"],
            "uf": ["SP", "SP"],
            "cod_municipio": ["3550308", np.nan],
            "renda_per_capita_setor_2022_calibrada": [1500.0, 900.0],
        }
    )
    r = _serie_renda_dom(df)
    assert r.loc[0] == 9000  # municipio resolvido
    assert r.loc[1] is None  # cod_municipio NaN -> tooltip vazio (nao fallback UF)
    # O guardrail vive na PROPRIA funcao: nem um fator valido destrava a linha sem cod.
    linha_sem_cod = pilot._derivar(df).loc[1]
    assert pilot._renda_domiciliar_hex(linha_sem_cod, 6.0) is None


# ===========================================================================
# Cascata dos fatores (municipio -> mediana UF -> nacional) e indice
# ===========================================================================


def test_fallback_municipio_ausente_usa_mediana_da_uf_e_depois_nacional(
    staging_sintetico: Path,
) -> None:
    # Municipio fora da tabela -> medianas da UF: moradores med(3.2, 2.5) = 2.85 e
    # uplift med(1.5, 1.2) = 1.35 (so linhas `uplift_confiavel`).
    assert pilot._fator_domiciliar("SP", "3599999") == approx(2.85 * 1.35 * FATOR_TEMPORAL)
    # UF fora da tabela -> constantes nacionais (2.79 x 1.632).
    esperado = (
        _const.MORADORES_DOMICILIO_NACIONAL * _const.UPLIFT_COMPOSICAO_NACIONAL * FATOR_TEMPORAL
    )
    assert pilot._fator_domiciliar("ZZ", "9999999") == approx(esperado)


def test_sem_artefatos_cai_no_nacional_com_fator_temporal_1(staging_vazio: Path) -> None:
    """Staging vazio (CI): fatores NACIONAIS e fator temporal 1.0 — degradacao
    graciosa que mantem o tooltip vivo sem os parquets."""
    assert pilot._fator_temporal_renda() == approx(1.0)
    esperado = _const.MORADORES_DOMICILIO_NACIONAL * _const.UPLIFT_COMPOSICAO_NACIONAL
    assert pilot._fator_domiciliar("SP", "3550308") == approx(esperado)
    r = _serie_renda_dom(_frame())
    assert r.loc[0] == round(1500.0 * esperado)


def test_preserva_indice_nao_sequencial(staging_sintetico: Path) -> None:
    df = _frame()
    df.index = [10, 20, 30]
    derivado = pilot._derivar(df)
    assert list(derivado.index) == [10, 20, 30]
    r = _serie_renda_dom(df)
    assert list(r.index) == [10, 20, 30]
    # A linha do rotulo 10 casa com o SEU municipio — sem mistura posicional.
    assert r.loc[10] == 9000
