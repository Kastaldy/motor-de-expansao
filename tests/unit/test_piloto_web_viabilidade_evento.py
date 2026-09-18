"""`viabilidade.calculada`: a rota registra a ANALISE PEDIDA, e nunca cai por causa disso.

O contrato (§2.5) pedia `hex_id` e/ou `imovel_id` em `metadados`, e a correcao de 16/09 tirou
o alvo da especificacao porque ele NAO EXISTE no pedido -- medido nas duas telas que chamam a
rota (o bloco da tela de Ponto e a tela de Viabilidade), que so' tem a coordenada, e no
backend, que usa `lat`/`lng` apenas para escolher a malha do catchment. Derivar o hexagono da
coordenada e' o que a §2.2 recusa; gravar a coordenada e' o que a §4 proibe.

Sobram as PREMISSAS, que sao o conteudo real do ato. E aqui a politica e' o OPOSTO da §2.4, de
proposito: na visita, sem alvo nao se grava, porque o alvo e' o conteudo inteiro; aqui o
conteudo e' a premissa e o ato e' a analise.

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

#: Cenario minimo aceito pelo modelo: coordenada + as tres premissas obrigatorias.
_CENARIO = {"lat": -23.55, "lng": -46.63, "m2": 1500.0, "aluguel": 20000.0, "demanda": 900.0}


class _Quem:
    def __init__(self, id_usuario: int) -> None:
        self.id_usuario = id_usuario


@pytest.fixture
def analises(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Captura o que chegaria em `registrar_viabilidade`, e nao calcula nada de verdade."""
    capturadas: list[dict[str, Any]] = []
    monkeypatch.setattr(db_eventos, "registrar_viabilidade", lambda **kw: capturadas.append(kw))
    monkeypatch.setattr(rbac, "identidade", lambda _login: _Quem(7))
    monkeypatch.setattr(pilot_app, "_payload_viabilidade", lambda _b: {"ok": True})
    return capturadas


def test_a_rota_registra_as_premissas_que_recebeu(analises: list[dict[str, Any]]) -> None:
    corpo = pilot_app.ViabilidadeIn(**_CENARIO)
    saida = pilot_app.viabilidade(corpo, remote_user="ana")

    assert saida == {"ok": True}, "a resposta da rota nao pode mudar"
    assert analises == [
        {"autor": 7, "m2": 1500.0, "aluguel": 20000.0, "demanda": 900.0, "origem": "web"}
    ]


def test_a_coordenada_nao_atravessa_para_o_evento(analises: list[dict[str, Any]]) -> None:
    """§4: `lat`/`lng` ficam fora de `metadados`. A rota TEM a coordenada -- e nao a repassa."""
    pilot_app.viabilidade(pilot_app.ViabilidadeIn(**_CENARIO), remote_user="ana")
    assert "lat" not in analises[0]
    assert "lng" not in analises[0]


def test_registra_DEPOIS_de_o_motor_responder(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gravar antes contaria uma analise que pode nao ter terminado."""
    chamadas: list[str] = []
    monkeypatch.setattr(rbac, "identidade", lambda _login: _Quem(7))
    monkeypatch.setattr(
        pilot_app, "_payload_viabilidade", lambda _b: chamadas.append("motor") or {"ok": True}
    )
    monkeypatch.setattr(
        db_eventos, "registrar_viabilidade", lambda **_kw: chamadas.append("evento")
    )

    pilot_app.viabilidade(pilot_app.ViabilidadeIn(**_CENARIO), remote_user="ana")
    assert chamadas == ["motor", "evento"]


def test_motor_que_explode_nao_grava_evento(monkeypatch: pytest.MonkeyPatch) -> None:
    """Se o calculo falha, nao houve analise -- e nao pode haver evento dizendo que houve."""
    gravou: list[Any] = []

    def _explode(_b: Any) -> None:
        raise RuntimeError("motor caiu")

    monkeypatch.setattr(pilot_app, "_payload_viabilidade", _explode)
    monkeypatch.setattr(db_eventos, "registrar_viabilidade", lambda **kw: gravou.append(kw))
    # A identidade TEM de ser trocada aqui. Sem isso, se alguem inverter a ordem no `app.py` o
    # registro roda primeiro, morre sozinho tentando `rbac.identidade` sem banco, e o `except`
    # do helper engole -- `gravou` fica vazio POR ACIDENTE e o teste passa justamente no caso
    # que deveria denunciar (medido em 16/09: a sabotagem da ordem so' matou um teste, e era
    # este que faltava). Com identidade resolvida, a lista vazia so' pode vir da ordem certa.
    monkeypatch.setattr(rbac, "identidade", lambda _login: _Quem(7))

    with pytest.raises(RuntimeError):
        pilot_app.viabilidade(pilot_app.ViabilidadeIn(**_CENARIO), remote_user="ana")
    assert gravou == []


def test_o_calculo_nao_cai_quando_o_banco_cai(
    monkeypatch: pytest.MonkeyPatch,
    analises: list[dict[str, Any]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A tela recebe o payload mesmo com o banco fora -- e a falha vira log, nunca silencio."""

    def _explode(**_kw: Any) -> None:
        raise RuntimeError("banco fora")

    monkeypatch.setattr(db_eventos, "registrar_viabilidade", _explode)
    with caplog.at_level(logging.ERROR, logger="piloto.d17"):
        saida = pilot_app.viabilidade(pilot_app.ViabilidadeIn(**_CENARIO), remote_user="ana")

    assert saida == {"ok": True}
    assert [r for r in caplog.records if r.name == "piloto.d17"], "a falha passou em silencio"


def test_deploy_sem_banco_loga_DEBUG_e_nao_ERRO(
    monkeypatch: pytest.MonkeyPatch,
    analises: list[dict[str, Any]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A tela mais quente das quatro: sem este ramo, um deploy sem banco escrevia um traceback
    a cada CALCULO de viabilidade. O teste acima cobre o banco que CAIU, que continua ERRO."""
    from motor_expansao.db import BancoNaoConfigurado

    def _sem_banco(**_kw: Any) -> None:
        raise BancoNaoConfigurado("sem MOTOR_DATABASE_URL")

    monkeypatch.setattr(db_eventos, "registrar_viabilidade", _sem_banco)
    with caplog.at_level(logging.DEBUG, logger="piloto.d17"):
        saida = pilot_app.viabilidade(pilot_app.ViabilidadeIn(**_CENARIO), remote_user="ana")

    assert saida == {"ok": True}
    nossos = [r for r in caplog.records if r.name == "piloto.d17"]
    assert [r for r in nossos if r.levelno == logging.DEBUG], "a ausencia passou em silencio"
    assert not [r for r in nossos if r.levelno >= logging.ERROR], "ruido de ERRO sem incidente"


def test_sem_cadastro_no_banco_a_analise_sai_com_autor_nulo(
    monkeypatch: pytest.MonkeyPatch, analises: list[dict[str, Any]]
) -> None:
    """Como no relatorio: o D19 preve acao de autoria nula, e "alguem rodou viabilidade com
    estas premissas" continua sendo informacao."""
    monkeypatch.setattr(rbac, "identidade", lambda _login: None)
    pilot_app.viabilidade(pilot_app.ViabilidadeIn(**_CENARIO), remote_user="fantasma")
    assert analises[0]["autor"] is None


def test_a_identidade_vem_de_login_da_requisicao(
    monkeypatch: pytest.MonkeyPatch, analises: list[dict[str, Any]]
) -> None:
    """A MESMA resolucao de todo o resto -- header, ou identidade de dev no vazio."""
    vistos: list[Any] = []
    monkeypatch.setattr(pilot_app.acesso, "login_da_requisicao", lambda _u: "resolvida")
    monkeypatch.setattr(rbac, "identidade", lambda login: vistos.append(login) or _Quem(7))

    pilot_app.viabilidade(pilot_app.ViabilidadeIn(**_CENARIO), remote_user=None)
    assert vistos == ["resolvida"]
