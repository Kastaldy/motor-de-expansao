"""Blinda o ramo FALLBACK de `Settings` (sem `pydantic_settings`).

Reproduz o estado exato do CI (instala so `.[dev]`, sem o extra `api`, logo
`pydantic_settings` ausente) e prova que `Settings()` instancia, `CORES` resolve
e o override por env continua funcionando — exatamente o caso que quebrava a
collection do CI (`AttributeError: property 'CORES' ... has no setter`).
"""

from __future__ import annotations

import builtins
import importlib
import os
import sys

import pytest

_REAL_IMPORT = builtins.__import__


def _load_config_fallback():
    """Recarrega `motor_expansao.config` forcando `pydantic_settings` ausente.

    Retorna o modulo recarregado no ramo fallback. O chamador e responsavel por
    restaurar `sys.modules`/`builtins.__import__` (feito no fixture de teardown).
    """

    def _fake_import(name, *args, **kwargs):
        if name == "pydantic_settings" or name.startswith("pydantic_settings."):
            raise ModuleNotFoundError("No module named 'pydantic_settings'")
        return _REAL_IMPORT(name, *args, **kwargs)

    builtins.__import__ = _fake_import
    sys.modules.pop("pydantic_settings", None)
    cfg = importlib.import_module("motor_expansao.config")
    return importlib.reload(cfg)


@pytest.fixture
def config_fallback():
    """Carrega o config no ramo fallback e restaura o estado real no teardown."""
    saved_pydantic_settings = sys.modules.get("pydantic_settings")
    env_no_setup = dict(os.environ)
    try:
        yield _load_config_fallback()
    finally:
        # Restaura o import real e recarrega o config no ramo normal para nao
        # contaminar o restante da suite.
        builtins.__import__ = _REAL_IMPORT
        if saved_pydantic_settings is not None:
            sys.modules["pydantic_settings"] = saved_pydantic_settings
        else:
            sys.modules.pop("pydantic_settings", None)
        # O reload de teardown TEM de rodar com o ambiente que existia no setup.
        # `monkeypatch` e finalizado DEPOIS deste bloco (finalizacao LIFO: quem
        # entra primeiro na assinatura do teste sai por ultimo), entao o
        # `monkeypatch.setenv("H3_RESOLUTION", "9")` de `test_fallback_env_override`
        # ainda estava valendo aqui e o `settings` GLOBAL do processo ficava com
        # H3_RESOLUTION=9 para o resto da sessao. Efeito observado:
        # `tests/contracts/test_parametros_canonicos.py::
        #  test_constants_reexport_alinha_a_sua_origem` quebrava com `assert 7 == 9`
        # sempre que este arquivo rodasse ANTES dele (repro:
        # `pytest tests/unit/test_config_fallback.py tests/contracts/test_parametros_canonicos.py`).
        # Na ordem alfabetica da suite completa contracts vem primeiro, entao o
        # defeito ficava escondido; com pytest-randomly ou xdist, virava flake.
        os.environ.clear()
        os.environ.update(env_no_setup)
        importlib.reload(importlib.import_module("motor_expansao.config"))


def test_fallback_settings_instancia_e_cores_resolve(config_fallback):
    cfg = config_fallback
    # Estamos de fato no ramo fallback (pydantic_settings ausente).
    assert cfg.BaseSettings is None
    s = cfg.Settings()
    # CORES permanece @property intacta e resolve as 9 cores.
    assert s.CORES["purple"] == "#6B21A8"
    assert len(s.CORES) == 9


def test_fallback_env_override(config_fallback, monkeypatch):
    monkeypatch.setenv("H3_RESOLUTION", "9")
    cfg = config_fallback
    s = cfg.Settings()
    assert s.H3_RESOLUTION == 9
    assert isinstance(s.H3_RESOLUTION, int)
