"""O produtor do D17 no piloto (`_registrar_relatorio_gerado`) — carimba sempre, grava quando da'.

A politica e' de PRODUTO, decidida em 10/09, e e' contraintuitiva de proposito: o relatorio
nunca falha por causa da trilha. O PDF leva o identificador mesmo com o banco fora, e o custo
disso e' real -- um id carimbado sem linha no banco e' um identificador ORFAO, e quem achar o
arquivo vazado consulta o banco e nao encontra nada.

E' por isso que a falha e' LOGADA COMO ERRO em vez de engolida: sem o log, a unica pista de
que o rastreio nao existe para aquele arquivo seria a ausencia de uma linha que ninguem sabe
procurar. Esse log e' parte do contrato, e nao decoracao -- tem teste proprio aqui.

A funcao nao tinha teste nenhum ate' 16/09, apesar de ser o unico caminho pelo qual as QUATRO
superficies de relatorio produzem evento. Chamada DIRETO, no padrao da suite do piloto
(sem TestClient).
"""

from __future__ import annotations

import logging
import re
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

#: Um id reconhecivel: se o valor devolvido nao for este, alguem cunhou outro pelo caminho.
_ID_CARIMBADO = "11111111-2222-4333-8444-555555555555"


class _Quem:
    """Identidade do RBAC, reduzida ao que o produtor le."""

    def __init__(self, id_usuario: int) -> None:
        self.id_usuario = id_usuario


@pytest.fixture
def gravacoes(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Captura o que chegaria em `registrar_relatorio`, sem banco nenhum."""
    capturadas: list[dict[str, Any]] = []
    monkeypatch.setattr(db_eventos, "novo_report_id", lambda: _ID_CARIMBADO)
    monkeypatch.setattr(
        db_eventos, "registrar_relatorio", lambda **kw: capturadas.append(kw) or kw["report_id"]
    )
    monkeypatch.setattr(rbac, "identidade", lambda _login: _Quem(7))
    return capturadas


# --------------------------------------------------------------------------------------
# Carimba SEMPRE — a trilha nunca derruba o relatorio
# --------------------------------------------------------------------------------------


def test_devolve_o_id_mesmo_quando_a_gravacao_explode(
    monkeypatch: pytest.MonkeyPatch, gravacoes: list[dict[str, Any]]
) -> None:
    """Se o id dependesse do banco, um Postgres fora derrubaria a geracao de relatorio."""

    def _explode(**_kw: Any) -> None:
        raise RuntimeError("banco fora")

    monkeypatch.setattr(db_eventos, "registrar_relatorio", _explode)
    devolvido = pilot_app._registrar_relatorio_gerado("ana", relatorio="pontual", formato="pdf")
    assert devolvido == _ID_CARIMBADO
    assert gravacoes == []


def test_devolve_o_id_mesmo_quando_a_identidade_explode(
    monkeypatch: pytest.MonkeyPatch, gravacoes: list[dict[str, Any]]
) -> None:
    """Banco fora quebra a resolucao de identidade ANTES da gravacao -- e nem isso derruba."""

    def _explode(_login: Any) -> None:
        raise RuntimeError("pool fechado")

    monkeypatch.setattr(rbac, "identidade", _explode)
    assert (
        pilot_app._registrar_relatorio_gerado("ana", relatorio="municipal", formato="pdf")
        == _ID_CARIMBADO
    )
    assert gravacoes == []


def test_o_id_devolvido_e_o_MESMO_que_foi_para_o_evento(gravacoes: list[dict[str, Any]]) -> None:
    """O id vai impresso no arquivo. Se o gravado for outro, o rastreio nao fecha -- e' a
    metade do D17 que o `report_id` existe para cumprir."""
    devolvido = pilot_app._registrar_relatorio_gerado("ana", relatorio="pontual", formato="pdf")
    assert gravacoes[0]["report_id"] == devolvido


def test_deploy_sem_banco_loga_DEBUG_e_nao_ERRO(
    monkeypatch: pytest.MonkeyPatch,
    gravacoes: list[dict[str, Any]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Sem banco CONFIGURADO a ausencia de evento e' esperada, e nao incidente.

    Um traceback por relatorio num deploy sem banco treinaria o operador a ignorar o ERROR do
    teste logo abaixo -- que e' justamente o que denuncia incidente de verdade.

    AS DUAS METADES IMPORTAM. So' exigir "nenhum ERRO" deixaria passar um helper que engolisse
    tudo em silencio, e silencio aqui e' o defeito original que o D17 existe para fechar.
    """
    from motor_expansao.db import BancoNaoConfigurado

    def _sem_banco(**_kw: Any) -> None:
        raise BancoNaoConfigurado("sem MOTOR_DATABASE_URL")

    monkeypatch.setattr(db_eventos, "registrar_relatorio", _sem_banco)
    with caplog.at_level(logging.DEBUG, logger="piloto.d17"):
        devolvido = pilot_app._registrar_relatorio_gerado("ana", relatorio="pontual", formato="pdf")

    assert devolvido == _ID_CARIMBADO, "o relatorio sai igual, com ou sem banco"
    nossos = [r for r in caplog.records if r.name == "piloto.d17"]
    assert [r for r in nossos if r.levelno == logging.DEBUG], "a ausencia passou em silencio"
    assert not [r for r in nossos if r.levelno >= logging.ERROR], "ruido de ERRO sem incidente"


def test_a_falha_vira_LOG_DE_ERRO_com_o_report_id(
    monkeypatch: pytest.MonkeyPatch,
    gravacoes: list[dict[str, Any]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Sem este log, um identificador orfao e' indistinguivel de um rastreio que funciona.

    O operador so' descobriria pela ausencia de uma linha que ele nao sabe que deveria
    procurar -- e o arquivo ja' estaria circulando com um codigo que nao resolve.
    """

    def _explode(**_kw: Any) -> None:
        raise RuntimeError("banco fora")

    monkeypatch.setattr(db_eventos, "registrar_relatorio", _explode)
    with caplog.at_level(logging.ERROR, logger="piloto.d17"):
        pilot_app._registrar_relatorio_gerado("ana", relatorio="comparacao", formato="pdf")

    registros = [r for r in caplog.records if r.name == "piloto.d17"]
    assert registros, "a falha do D17 passou em silencio"
    texto = registros[0].getMessage()
    assert _ID_CARIMBADO in texto, "o log nao diz QUAL arquivo ficou sem rastreio"
    assert "ORFAO" in texto.upper()


# --------------------------------------------------------------------------------------
# O autor, e de onde vem a identidade
# --------------------------------------------------------------------------------------


def test_sem_cadastro_no_banco_o_evento_sai_com_autor_NULO(
    monkeypatch: pytest.MonkeyPatch, gravacoes: list[dict[str, Any]]
) -> None:
    """Meio evento vale mais que nenhum: o D19 preve acao de autoria nula, e um
    `relatorio.gerado` anonimo ainda diz que o arquivo existiu."""
    monkeypatch.setattr(rbac, "identidade", lambda _login: None)
    pilot_app._registrar_relatorio_gerado("fantasma", relatorio="pontual", formato="pdf")

    assert len(gravacoes) == 1, "sem cadastro, o evento deixou de sair"
    assert gravacoes[0]["autor"] is None


def test_com_cadastro_o_autor_e_o_id_do_rbac(gravacoes: list[dict[str, Any]]) -> None:
    pilot_app._registrar_relatorio_gerado("ana", relatorio="pontual", formato="pdf")
    assert gravacoes[0]["autor"] == 7


def test_a_identidade_vem_de_login_da_requisicao_e_nao_do_header_cru(
    monkeypatch: pytest.MonkeyPatch, gravacoes: list[dict[str, Any]]
) -> None:
    """A MESMA resolucao de todo o resto. Ler o header cru aqui reproduziria o defeito que o
    `/api/me` teve ate' 14/09: duas camadas lendo a mesma pessoa de fontes diferentes, e em
    desenvolvimento -- onde nao ha Authelia para injetar o header -- o evento sairia sem autor.
    """
    vistos: list[Any] = []
    monkeypatch.setattr(pilot_app.acesso, "login_da_requisicao", lambda _u: "resolvida.pelo.acesso")
    monkeypatch.setattr(rbac, "identidade", lambda login: vistos.append(login) or _Quem(7))

    pilot_app._registrar_relatorio_gerado(None, relatorio="pontual", formato="pdf")
    assert vistos == ["resolvida.pelo.acesso"]


# --------------------------------------------------------------------------------------
# O que vai no evento
# --------------------------------------------------------------------------------------


def test_relatorio_formato_e_origem_chegam_como_vieram(gravacoes: list[dict[str, Any]]) -> None:
    """A §2.2 poe os quatro relatorios sob o MESMO `tipo`, e `formato` sozinho nao separa
    Pontual de Municipal -- os dois sao PDF. Os dois campos sao necessarios."""
    pilot_app._registrar_relatorio_gerado("ana", relatorio="simulador", formato="xlsx")
    gravado = gravacoes[0]
    assert gravado["relatorio"] == "simulador"
    assert gravado["formato"] == "xlsx"
    assert gravado["origem"] == "web"


def test_o_alvo_e_repassado_quando_existe(gravacoes: list[dict[str, Any]]) -> None:
    """As chaves de alvo sao contrato fechado; quem as recusa e' o `db.eventos`. Aqui o que
    se guarda e' que o produtor nao as ENGOLE pelo caminho."""
    pilot_app._registrar_relatorio_gerado(
        "ana", relatorio="pontual", formato="pdf", alvo={"hex_id": "87a8100efffffff"}
    )
    assert gravacoes[0]["alvo"] == {"hex_id": "87a8100efffffff"}


def test_as_quatro_rotas_usam_os_rotulos_do_contrato() -> None:
    """Os rotulos sao o que distingue as quatro superficies dentro do mesmo `tipo`.

    Um `relatorio="Municipal"` com maiuscula, ou um quinto rotulo inventado, nao quebraria
    nada em tempo de execucao -- so' tornaria o evento inconsultavel pela chave que a §2.2
    declara. Este teste le as CHAMADAS REAIS do `app.py`, e nao uma lista repetida aqui.
    """
    fonte = (_SERVER / "app.py").read_text(encoding="utf-8")
    chamadas = re.findall(
        r'_registrar_relatorio_gerado\([^)]*?relatorio="([^"]+)",\s*formato="([^"]+)"', fonte
    )
    assert len(chamadas) == 4, f"esperava as quatro superficies, achei {chamadas}"
    assert {r for r, _f in chamadas} == {"municipal", "pontual", "simulador", "comparacao"}
    assert {f for _r, f in chamadas} == {"pdf", "xlsx"}


# --------------------------------------------------------------------------------------
# `dossie.baixado` — mesma politica, outro artefato (16/09)
# --------------------------------------------------------------------------------------


@pytest.fixture
def dossies(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Captura o que chegaria em `registrar_dossie_baixado`."""
    capturados: list[dict[str, Any]] = []
    monkeypatch.setattr(db_eventos, "registrar_dossie_baixado", lambda **kw: capturados.append(kw))
    monkeypatch.setattr(rbac, "identidade", lambda _login: _Quem(7))
    return capturados


def test_o_dossie_registra_quem_baixou(dossies: list[dict[str, Any]]) -> None:
    pilot_app._registrar_dossie_baixado("ana", imovel_id="im_3f2a9b")
    assert dossies == [{"autor": 7, "imovel_id": "im_3f2a9b", "origem": "web"}]


def test_deploy_sem_banco_loga_DEBUG_e_nao_ERRO_no_dossie(
    monkeypatch: pytest.MonkeyPatch, dossies: list[dict[str, Any]], caplog: pytest.LogCaptureFixture
) -> None:
    """Mesma politica do relatorio, no artefato em que errar custa mais caro: o dossie e' o
    unico do piloto que carrega contato de corretor.

    Ainda assim, num deploy SEM banco a ausencia de evento e' CONFIGURACAO, nao incidente -- e
    o ERROR fica reservado ao banco que caiu, que e' o teste logo abaixo. O sufixo `_no_dossie`
    no nome nao e' enfeite: ha um teste homonimo para o relatorio neste mesmo modulo, e nomes
    iguais fariam o segundo apagar o primeiro SEM nenhum vermelho.
    """
    from motor_expansao.db import BancoNaoConfigurado

    def _sem_banco(**_kw: Any) -> None:
        raise BancoNaoConfigurado("sem MOTOR_DATABASE_URL")

    monkeypatch.setattr(db_eventos, "registrar_dossie_baixado", _sem_banco)
    with caplog.at_level(logging.DEBUG, logger="piloto.d17"):
        pilot_app._registrar_dossie_baixado("ana", imovel_id="im_3f2a9b")

    nossos = [r for r in caplog.records if r.name == "piloto.d17"]
    assert [r for r in nossos if r.levelno == logging.DEBUG], "a ausencia passou em silencio"
    assert not [r for r in nossos if r.levelno >= logging.ERROR], "ruido de ERRO sem incidente"


def test_a_entrega_do_pdf_nao_depende_da_trilha(
    monkeypatch: pytest.MonkeyPatch, dossies: list[dict[str, Any]], caplog: pytest.LogCaptureFixture
) -> None:
    """O arquivo sai com o banco fora -- e a falha vira log de ERRO, nunca silencio: um
    dossie baixado sem evento e' indistinguivel de um que ninguem baixou."""

    def _explode(**_kw: Any) -> None:
        raise RuntimeError("banco fora")

    monkeypatch.setattr(db_eventos, "registrar_dossie_baixado", _explode)
    with caplog.at_level(logging.ERROR, logger="piloto.d17"):
        pilot_app._registrar_dossie_baixado("ana", imovel_id="im_3f2a9b")

    registros = [r for r in caplog.records if r.name == "piloto.d17"]
    assert registros, "o dossie sem evento passou em silencio"
    assert "im_3f2a9b" in registros[0].getMessage()


def test_sem_cadastro_o_dossie_sai_com_autor_nulo(
    monkeypatch: pytest.MonkeyPatch, dossies: list[dict[str, Any]]
) -> None:
    monkeypatch.setattr(rbac, "identidade", lambda _login: None)
    pilot_app._registrar_dossie_baixado("fantasma", imovel_id="im_3f2a9b")
    assert dossies[0]["autor"] is None


def test_a_rota_do_dossie_so_registra_o_que_ENTREGOU(
    monkeypatch: pytest.MonkeyPatch, dossies: list[dict[str, Any]]
) -> None:
    """Registrar antes do 404 contaria como baixado um dossie que ninguem recebeu."""
    from fastapi import HTTPException

    monkeypatch.setattr(pilot_app, "_dossie_index", dict)
    with pytest.raises(HTTPException) as caiu:
        pilot_app.api_oportunidade_dossie("im_inexistente", remote_user="ana")

    assert caiu.value.status_code == 404
    assert dossies == [], "gravou download de um dossie que nao existe"


def test_o_gesto_da_tela_nao_grava_evento(monkeypatch: pytest.MonkeyPatch) -> None:
    """`abrir-dossie` dispara TAMBEM quando o imovel nao tem dossie (o front manda
    `detalhe: relatorio-pontual`). Gravar la' contaria download que nao houve, e gravar nos
    dois contaria cada um duas vezes -- ver a correcao de 16/09 na §2.4 do contrato.

    O duble REGISTRA a chamada em vez de levantar, e isso nao e' estilo. A primeira versao
    deste teste levantava `AssertionError` -- que e' subclasse de `Exception` e portanto seria
    ENGOLIDA pelo `except Exception` do `_registrar_dossie_baixado`, que existe para a trilha
    nunca derrubar a entrega. Sabotado (o gesto passando a gravar), aquele teste PASSAVA: a
    garantia era falsa. Contar chamadas nao depende de a excecao subir.
    """
    chamadas: list[Any] = []
    monkeypatch.setattr(
        pilot_app, "_registrar_dossie_baixado", lambda *a, **kw: chamadas.append((a, kw))
    )
    monkeypatch.setattr(db_eventos, "registrar_dossie_baixado", lambda **kw: chamadas.append(kw))

    assert pilot_app.api_imobiliaria_evento("abrir-dossie") == {"ok": True}
    assert chamadas == [], "o gesto gravou evento -- o download seria contado duas vezes"
