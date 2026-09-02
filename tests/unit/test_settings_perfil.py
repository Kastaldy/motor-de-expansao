"""Bloco A / commit A2 — o campo `perfil` em `Settings`, e as duas propriedades dele.

O campo entra com default `None` por uma razao operacional, nao por indecisao: e o que
permite converter os **4 sitios** que constroem `Settings` no `web/server/app.py`
(`:4522`, `:5224`, `:7739`, `:8008`) **um por commit**, cada um verde sozinho. Sem o
default, `pydantic-settings` levantaria nos quatro ao mesmo tempo.

Spec: `docs/spec_bloco_a_perfil.md` §3.4.
"""

from __future__ import annotations

import pytest

from motor_expansao.api.settings import Settings
from motor_expansao.perfil import PERFIL_BR_EMBARCADO, Perfil, carregar_perfil


@pytest.fixture(scope="module")
def perfil() -> Perfil:
    return carregar_perfil(PERFIL_BR_EMBARCADO)


def test_default_e_none() -> None:
    """`None` = "quem construiu nao passou". O consumidor cai em `resolver_perfil()`."""
    assert Settings().perfil is None


def test_perfil_passado_chega_intacto(perfil: Perfil) -> None:
    """**Identidade**, nao so igualdade. `pydantic` sabe construir validador para
    dataclass e poderia RECONSTRUIR o objeto; se fizesse isso, o `lru_cache` de
    `resolver_perfil()` deixaria de garantir uma instancia por processo e cada
    `Settings(...)` carregaria uma copia. Este teste trava a passagem por referencia."""
    assert Settings(perfil=perfil).perfil is perfil


def test_perfil_nao_vem_de_variavel_de_ambiente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**Regressao de um defeito real.** A spec §3.4 afirmava que um campo de dataclass
    nao e preenchivel por env. E FALSO: medido em 2026-09-02, `pydantic-settings` le
    `API_PERFIL` como JSON e monta o objeto. Sem o validador `_perfil_so_por_objeto`,
    uma env sobrescreveria bbox e regua de uma instancia em producao, contornando o
    arquivo montado no volume — o oposto da DEC-047."""
    completo = PERFIL_BR_EMBARCADO.read_text(encoding="utf-8")
    monkeypatch.setenv("API_PERFIL", completo)
    with pytest.raises(ValueError, match="resolver_perfil"):
        Settings()


@pytest.mark.parametrize("valor", ['{"pais": "AR"}', {"pais": "AR"}, "BR", 42])
def test_perfil_recusa_qualquer_coisa_que_nao_seja_o_objeto(valor: object) -> None:
    """Aceitar um dict criaria um SEGUNDO caminho de construcao, que nao passa pela
    validacao fail-closed do loader — um perfil sem `superficies`, por exemplo."""
    with pytest.raises(ValueError, match="resolver_perfil"):
        Settings(perfil=valor)


def test_os_diretorios_de_dados_seguem_intactos() -> None:
    """A2 acrescenta UM campo. Se o import do `perfil` tivesse efeito colateral sobre
    os defaults de diretorio, os 4 sitios de `Settings` quebrariam longe da causa."""
    s = Settings()
    assert s.censo_geo_dir.name == "setores_censitarios_2022_geo"
    assert s.ibge_dir.name == "ibge"
    assert s.ultra_dir.name == "ultra"
    assert s.staging_dir.name == "staging"
