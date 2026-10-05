"""O aviso da viabilidade que o perfil declara para a TELA chega a tela.

`data/perfis/AR/perfil.json` declara `avisos.viabilidade_tributo_provisorio` com
`onde = ["tela", "pdf", "xlsx"]`. O PDF e o XLSX ja' carimbavam (ver
`test_aviso_carimbado_no_perfil.py`); a tela nao tinha leitor nenhum — o perfil
declarava e ninguem obedecia. Na aba de Viabilidade argentina o operador via um
veredito calculado com tributo, custo e CAPEX BRASILEIROS sem a ressalva.

O contrato: `/api/me` serve `aviso_viabilidade` (titulo + texto longo) quando o perfil
da instancia declara o aviso ATIVO e com "tela" em `onde`; e a chave fica AUSENTE
quando nao declara — a resposta brasileira nao muda um byte.

Medido contra os DOIS perfis reais versionados, sem dado local (nenhum parquet).
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

from motor_expansao.perfil import PERFIL_BR_EMBARCADO, Perfil, carregar_perfil

_REPO = Path(__file__).resolve().parents[2]
_SERVIDOR = _REPO / "web" / "server"
if str(_SERVIDOR) not in sys.path:
    sys.path.insert(0, str(_SERVIDOR))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)

_PERFIL_AR_JSON = PERFIL_BR_EMBARCADO.parents[1] / "AR" / "perfil.json"
_CHAVE = "viabilidade_tributo_provisorio"


@pytest.fixture(scope="module")
def br() -> Perfil:
    return carregar_perfil(PERFIL_BR_EMBARCADO)


@pytest.fixture(scope="module")
def ar() -> Perfil:
    return carregar_perfil(_PERFIL_AR_JSON)


def test_o_perfil_ar_declara_o_aviso_para_a_tela(ar: Perfil) -> None:
    """A premissa deste arquivo: se "tela" sair do `onde`, o aviso some da aba em
    silencio — e este teste acusa antes dos de baixo."""
    aviso = ar.avisos[_CHAVE]
    assert aviso.ativo
    assert "tela" in aviso.onde


def test_me_serve_o_aviso_de_viabilidade_na_instancia_ar(
    ar: Perfil, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pilot, "PERFIL", ar)
    resposta = pilot.me(remote_user=None)
    aviso = ar.avisos[_CHAVE]
    assert resposta["aviso_viabilidade"] == {
        "titulo": aviso.titulo,
        "texto": aviso.texto_longo,
    }


def test_me_nao_serve_aviso_na_instancia_br(br: Perfil, monkeypatch: pytest.MonkeyPatch) -> None:
    """No Brasil `avisos` e' `{}`: a chave fica AUSENTE (nao nula) e a resposta de
    `/api/me` segue identica a de antes."""
    monkeypatch.setattr(pilot, "PERFIL", br)
    assert "aviso_viabilidade" not in pilot.me(remote_user=None)


def test_aviso_desligado_ou_fora_da_tela_nao_e_servido(
    ar: Perfil, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O perfil declara, o codigo obedece: `ativo: false` ou "tela" fora do `onde`
    tiram o aviso da aba sem nenhum ramo por pais (DEC-047)."""
    aviso = ar.avisos[_CHAVE]
    for trocado in (
        dataclasses.replace(aviso, ativo=False),
        dataclasses.replace(aviso, onde=frozenset({"pdf", "xlsx"})),
    ):
        perfil = dataclasses.replace(ar, avisos={**ar.avisos, _CHAVE: trocado})
        monkeypatch.setattr(pilot, "PERFIL", perfil)
        assert "aviso_viabilidade" not in pilot.me(remote_user=None)
