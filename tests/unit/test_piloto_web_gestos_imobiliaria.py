"""Os gestos da aba imobiliaria: quais sobem para `eventos`, e o que acontece sem alvo.

O `POST /api/imobiliaria/evento/{acao}` tem vocabulario fechado de SETE acoes, e o contrato
(§2.4) manda apenas DOIS deles para `eventos`: marcar e desmarcar visita, que sao decisao de
negocio sobre um imovel. Os outros cinco sao uso de tela e ficam so' na trilha de 90 dias da
DEC-027 -- inclusive `abrir-dossie`, cujo download e' gravado pelo GET do PDF (correcao de
16/09 na §2.4; gravar nos dois contaria o mesmo clique duas vezes).

A regra que este arquivo guarda com mais cuidado e' a do ALVO AUSENTE. No relatorio e no
dossie vale "meio evento vale mais que nenhum". Aqui nao: o valor inteiro do evento e' o
imovel, e um `visita_marcada` sem `imovel_id` cai fora do indice parcial da 014 e nao responde
a pergunta que justifica a sua existencia. Sem alvo, nao se grava -- e a ausencia vira log.

Chama a rota DIRETO, no padrao da suite do piloto (sem TestClient).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot_app  # noqa: E402

from motor_expansao.db import eventos as db_eventos  # noqa: E402
from motor_expansao.db import rbac  # noqa: E402


class _Quem:
    def __init__(self, id_usuario: int) -> None:
        self.id_usuario = id_usuario


@pytest.fixture
def visitas(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Captura o que chegaria em `registrar_visita`, sem banco nenhum."""
    capturadas: list[dict[str, Any]] = []
    monkeypatch.setattr(db_eventos, "registrar_visita", lambda **kw: capturadas.append(kw))
    monkeypatch.setattr(rbac, "identidade", lambda _login: _Quem(7))
    return capturadas


# --------------------------------------------------------------------------------------
# Quais gestos sobem
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("acao", "marcada"), [("marcar-visita", True), ("desmarcar-visita", False)]
)
def test_os_dois_gestos_de_visita_gravam_o_estado_resultante(
    visitas: list[dict[str, Any]], acao: str, marcada: bool
) -> None:
    saida = pilot_app.api_imobiliaria_evento(acao, imovel="im_3f2a9b", remote_user="ana")

    assert saida == {"ok": True}, "a resposta do gesto nao pode mudar"
    assert visitas == [{"autor": 7, "imovel_id": "im_3f2a9b", "marcada": marcada, "origem": "web"}]


@pytest.mark.parametrize(
    "acao", ["abrir-aba", "abrir-imovel", "abrir-dossie", "ver-no-mapa", "filtrar"]
)
def test_os_outros_cinco_gestos_nao_gravam(visitas: list[dict[str, Any]], acao: str) -> None:
    """Uso de tela fica na trilha. `abrir-dossie` esta' aqui de proposito: quem grava o
    download e' o GET do PDF, e gravar nos dois contaria o mesmo clique duas vezes."""
    assert pilot_app.api_imobiliaria_evento(acao, imovel="im_3f2a9b") == {"ok": True}
    assert visitas == []


def test_o_conjunto_que_sobe_e_exatamente_o_do_contrato() -> None:
    assert pilot_app.GESTOS_QUE_VIRAM_EVENTO == {"marcar-visita", "desmarcar-visita"}
    assert pilot_app.GESTOS_QUE_VIRAM_EVENTO <= pilot_app.ACOES_IMOBILIARIA


def test_acao_desconhecida_continua_404_e_nao_grava(visitas: list[dict[str, Any]]) -> None:
    """O 404 do vocabulario e' anterior a tudo -- inclusive ao evento."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as caiu:
        pilot_app.api_imobiliaria_evento("inventada", imovel="im_3f2a9b")
    assert caiu.value.status_code == 404
    assert visitas == []


# --------------------------------------------------------------------------------------
# O alvo
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("imovel", [None, "", "   "])
def test_sem_imovel_nao_grava_evento_nenhum(
    visitas: list[dict[str, Any]], caplog: pytest.LogCaptureFixture, imovel: str | None
) -> None:
    """Sem alvo o evento fica FORA do indice parcial e nao responde nada -- entao nao se grava.

    E a ausencia nao passa calada: vira log, porque um gesto de visita que nao virou evento e'
    uma decisao de negocio que sumiu do banco.
    """
    with caplog.at_level(logging.ERROR, logger="piloto.d17"):
        saida = pilot_app.api_imobiliaria_evento("marcar-visita", imovel=imovel)

    assert saida == {"ok": True}, "o gesto tem de responder ok mesmo sem alvo"
    assert visitas == []
    registros = [r for r in caplog.records if r.name == "piloto.d17"]
    assert registros, "a ausencia passou em silencio"
    # A MENSAGEM importa, e nao so' a existencia do log: sem a guarda, `None.strip()` estoura
    # DENTRO do `try` e o `except` loga outra coisa -- o teste passaria no caso que deveria
    # denunciar. Exigir o texto da guarda fecha essa porta (mesma licao de 16/09).
    assert "sem `imovel`" in registros[0].getMessage()


def test_o_alvo_e_aparado_antes_de_virar_metadado(visitas: list[dict[str, Any]]) -> None:
    pilot_app.api_imobiliaria_evento("marcar-visita", imovel="  im_3f2a9b  ")
    assert visitas[0]["imovel_id"] == "im_3f2a9b"


def test_a_chave_do_front_vira_a_chave_do_contrato(visitas: list[dict[str, Any]]) -> None:
    """A tela manda `imovel` na query; o contrato pede `imovel_id` em `metadados`, que e' uma
    das tres `CHAVES_DE_ALVO`. Errar a traducao e' defeito SILENCIOSO: a escrita passa e o
    evento some das consultas que o indice parcial atende."""
    pilot_app.api_imobiliaria_evento("marcar-visita", imovel="im_3f2a9b")
    assert "imovel_id" in visitas[0]
    assert "imovel" not in visitas[0]
    assert "imovel_id" in db_eventos.CHAVES_DE_ALVO


# --------------------------------------------------------------------------------------
# A trilha nunca derruba o gesto
# --------------------------------------------------------------------------------------


def test_banco_fora_nao_derruba_o_gesto(
    monkeypatch: pytest.MonkeyPatch, visitas: list[dict[str, Any]], caplog: pytest.LogCaptureFixture
) -> None:
    def _explode(**_kw: Any) -> None:
        raise RuntimeError("banco fora")

    monkeypatch.setattr(db_eventos, "registrar_visita", _explode)
    with caplog.at_level(logging.ERROR, logger="piloto.d17"):
        assert pilot_app.api_imobiliaria_evento(
            "marcar-visita", imovel="im_3f2a9b", remote_user="ana"
        ) == {"ok": True}

    registros = [r for r in caplog.records if r.name == "piloto.d17"]
    assert registros, "o gesto sem evento passou em silencio"
    assert "im_3f2a9b" in registros[0].getMessage()


def test_deploy_sem_banco_loga_DEBUG_e_nao_ERRO(
    monkeypatch: pytest.MonkeyPatch, visitas: list[dict[str, Any]], caplog: pytest.LogCaptureFixture
) -> None:
    """Sem banco configurado a visita fica so' na trilha de 90 dias -- desenho, nao incidente.

    A guarda de ALVO AUSENTE (mais acima) segue sendo ERRO de proposito: la' o gesto chegou
    incompleto, que e' defeito; aqui o deploy e' que nao tem banco, que e' configuracao.
    """
    from motor_expansao.db import BancoNaoConfigurado

    def _sem_banco(**_kw: Any) -> None:
        raise BancoNaoConfigurado("sem MOTOR_DATABASE_URL")

    monkeypatch.setattr(db_eventos, "registrar_visita", _sem_banco)
    with caplog.at_level(logging.DEBUG, logger="piloto.d17"):
        assert pilot_app.api_imobiliaria_evento(
            "marcar-visita", imovel="im_3f2a9b", remote_user="ana"
        ) == {"ok": True}

    nossos = [r for r in caplog.records if r.name == "piloto.d17"]
    assert [r for r in nossos if r.levelno == logging.DEBUG], "a ausencia passou em silencio"
    assert not [r for r in nossos if r.levelno >= logging.ERROR], "ruido de ERRO sem incidente"


def test_sem_cadastro_no_banco_a_visita_sai_com_autor_nulo(
    monkeypatch: pytest.MonkeyPatch, visitas: list[dict[str, Any]]
) -> None:
    """Diferente do ALVO, o AUTOR pode faltar: o D19 preve acao de autoria nula, e "este imovel
    entrou na fila de visita" continua sendo informacao sem saber quem o marcou."""
    monkeypatch.setattr(rbac, "identidade", lambda _login: None)
    pilot_app.api_imobiliaria_evento("marcar-visita", imovel="im_3f2a9b")
    assert visitas[0]["autor"] is None
