"""Contrato dos parametros canonicos do M1 (CLAUDE.md secao 3) <-> config/core.constants.

Aditivo (review de refatoracao, Fase 0 rank #2). NAO altera codigo-fonte: mecaniza a
invariante "M1 read-only" transformando-a de garantia SOCIAL em teste. Cobre:

  (a) os valores canonicos do bloco de parametros no `config` ativo;
  (b) os pesos oficiais (renda=0.40 / pop=0.60) e os cortes de percentil em `core.constants`;
  (c) o alias re-exportado em `core.constants` alinhado ao `settings` que o origina;
  (d) PARIDADE entre os dois ramos da classe `Settings` duplicada (pydantic + fallback) --
      o ramo inativo tambem precisa carregar os MESMOS defaults canonicos.

Se este teste falhar, um parametro canonico do M1 sofreu drift silencioso -- foi o caso
real de `M1_HEX_LAND_FRACTION_MIN`, ausente da prosa da secao 3 mas 0.05 no codigo.
"""

from __future__ import annotations

import builtins
import importlib
import sys

import pytest

from motor_expansao import config as config_mod
from motor_expansao.core import constants as core_constants

# Valores canonicos do bloco de parametros da secao 3 + os vigentes no codigo mas
# ausentes da prosa (land_fraction, cortes de percentil).
CANONICAL: dict[str, object] = {
    "H3_RESOLUTION": 7,
    "DIST_MIN_ULTRA_KM": 1.0,
    "RENDA_MIN": 4500.0,
    "AREA_MIN_M2": 1200.0,
    "AREA_IDEAL_MIN_M2": 1500.0,
    "AREA_IDEAL_MAX_M2": 2000.0,
    "PE_DIREITO_MIN": 3.5,
    "M1_SCORE_OFICIAL": "score_priorizacao",
    "M1_PRIORIZACAO_TOP_PCT_POR_UF": 0.20,
    "M1_OSM_ENABLED": False,
    "M1_SETOR_CENSITARIO_OBRIGATORIO": False,
    "M1_POP_MINIMA_PROXY": 1,
    # NAO consta na prosa da secao 3 (vem das DEC-002/003); registrado aqui para travar o drift.
    "M1_HEX_LAND_FRACTION_MIN": 0.05,
}

# Chaves re-exportadas por core.constants a partir de settings (constants.py).
_REEXPORTADAS = (
    "H3_RESOLUTION",
    "DIST_MIN_ULTRA_KM",
    "RENDA_MIN",
    "AREA_MIN_M2",
    "AREA_IDEAL_MIN_M2",
    "AREA_IDEAL_MAX_M2",
    "PE_DIREITO_MIN",
    "M1_SCORE_OFICIAL",
    "M1_PRIORIZACAO_TOP_PCT_POR_UF",
    "M1_OSM_ENABLED",
    "M1_SETOR_CENSITARIO_OBRIGATORIO",
    "M1_POP_MINIMA_PROXY",
)


def _fresh_settings(monkeypatch):
    """Instancia `Settings` isolada de qualquer override de ambiente (asserta os DEFAULTS)."""
    for key in CANONICAL:
        monkeypatch.delenv(key, raising=False)
    return config_mod.Settings()


def test_config_ativo_bate_canonico(monkeypatch):
    s = _fresh_settings(monkeypatch)
    for key, expected in CANONICAL.items():
        got = getattr(s, key)
        assert got == expected, f"{key}: config={got!r} != canonico={expected!r}"
        assert type(got) is type(expected), f"{key}: tipo {type(got)} != {type(expected)}"


def test_pesos_oficiais_e_cortes_percentil():
    # Pesos aprovados (DEC-001): renda=0.40, pop=0.60. Devem somar 1.0.
    assert core_constants.PESOS_HEX_SCORE_ESTRUTURAL == {
        "renda_per_capita": 0.40,
        "populacao_proxy": 0.60,
    }
    assert sum(core_constants.PESOS_HEX_SCORE_ESTRUTURAL.values()) == pytest.approx(1.0)
    assert core_constants.PERCENTIL_CORTE_SUPERIOR == 0.75
    assert core_constants.PERCENTIL_CORTE_INFERIOR == 0.25


def test_constants_reexport_alinha_a_sua_origem():
    # core.constants re-exporta valores de `settings`; o alias nao pode divergir da origem.
    for key in _REEXPORTADAS:
        assert getattr(core_constants, key) == getattr(config_mod.settings, key), key


_REAL_IMPORT = builtins.__import__


@pytest.fixture
def _fallback_config():
    """Carrega `config` no ramo FALLBACK (sem pydantic_settings) e restaura no teardown."""
    saved = sys.modules.get("pydantic_settings")

    def _fake_import(name, *args, **kwargs):
        if name == "pydantic_settings" or name.startswith("pydantic_settings."):
            raise ModuleNotFoundError("No module named 'pydantic_settings'")
        return _REAL_IMPORT(name, *args, **kwargs)

    builtins.__import__ = _fake_import
    sys.modules.pop("pydantic_settings", None)
    try:
        yield importlib.reload(importlib.import_module("motor_expansao.config"))
    finally:
        builtins.__import__ = _REAL_IMPORT
        if saved is not None:
            sys.modules["pydantic_settings"] = saved
        else:
            sys.modules.pop("pydantic_settings", None)
        importlib.reload(importlib.import_module("motor_expansao.config"))


def test_settings_dois_ramos_tem_os_mesmos_defaults(_fallback_config, monkeypatch):
    """A `Settings` esta duplicada (pydantic + fallback); os defaults NAO podem divergir."""
    cfg = _fallback_config
    assert cfg.BaseSettings is None  # de fato no ramo fallback
    for key in CANONICAL:
        monkeypatch.delenv(key, raising=False)
    s = cfg.Settings()
    for key, expected in CANONICAL.items():
        got = getattr(s, key)
        assert got == expected, f"[ramo fallback] {key}={got!r} != canonico={expected!r}"
