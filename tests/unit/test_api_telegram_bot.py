"""Testes do bot Telegram (BLK-API-07): acesso -> login -> localizacao -> PDF."""

from __future__ import annotations

import time

import pytest
import requests

from motor_expansao.api import telegram_bot as bot
from motor_expansao.api.settings import Settings

_S = Settings(bot_senha="abre", telegram_token="x")


@pytest.fixture(autouse=True)
def _limpa_sessoes():
    bot._sessoes.clear()
    yield
    bot._sessoes.clear()


def _textos(acoes) -> str:
    return " || ".join(a.get("text", "<pdf>") for a in acoes)


def _auth(cid: int, nome: str = "Tester") -> None:
    """Passa pela senha + login, deixando o chat pronto para usar."""
    bot.processar(cid, "abre", _S)   # senha -> pede login
    bot.processar(cid, nome, _S)     # login -> menu


# --- acesso por senha -------------------------------------------------------


def test_bloqueia_sem_senha():
    assert "senha" in _textos(bot.processar(1, "oi", _S)).lower()


def test_senha_pede_login():
    out = bot.processar(1, "abre", _S)
    assert "chamar" in _textos(out).lower()  # pede o nome/login


def test_senha_errada_continua_bloqueado():
    bot.processar(1, "errada", _S)
    out = bot.processar(1, "-21.9,-46.6", _S)  # ainda nao autorizado
    assert "incorreta" in _textos(out).lower()


def test_login_registra_nome():
    bot.processar(2, "abre", _S)
    out = bot.processar(2, "Joao", _S)
    assert "joao" in _textos(out).lower()      # confirma o nome
    assert "localizacao" in _textos(out).lower()  # ja pede a localizacao
    assert bot._sessao(2)["login"] == "Joao"


# --- comandos (apos login) --------------------------------------------------


def test_relatorio_pede_local():
    _auth(2)
    out = bot.processar(2, "Relatorio", _S)
    assert "localizacao" in _textos(out).lower()


def test_ajuda_difere_do_relatorio():
    _auth(2)
    ajuda = _textos(bot.processar(2, "Ajuda", _S))
    relat = _textos(bot.processar(2, "Relatorio", _S))
    assert "sobre o paulo" in ajuda.lower()
    assert ajuda != relat  # mensagens distintas


# --- localizacao -> PDF -----------------------------------------------------


def test_localizacao_gera_pdf(monkeypatch):
    monkeypatch.setattr(bot, "resolver_local", lambda t, s: (-21.9, -46.6, "Aguas da Prata"))
    monkeypatch.setattr(bot, "consultar_pdf", lambda p, s: b"%PDF-fake")
    _auth(3, "Maria")
    out = bot.processar(3, "-21.9,-46.6", _S)
    texto = _textos(out)
    assert "Aguas da Prata" in texto
    assert "Maria" in texto            # rastreio do solicitante
    assert any("pdf" in a for a in out)


def test_localizacao_nao_resolvida(monkeypatch):
    monkeypatch.setattr(bot, "resolver_local", lambda t, s: None)
    _auth(4)
    out = bot.processar(4, "xpto sem sentido", _S)
    assert "nao consegui localizar" in _textos(out).lower()
    assert not any("pdf" in a for a in out)


def test_localizacao_base_ausente(monkeypatch):
    monkeypatch.setattr(bot, "resolver_local", lambda t, s: (-23.55, -46.63, "Sao Paulo"))
    monkeypatch.setattr(bot, "consultar_pdf", lambda p, s: None)
    monkeypatch.setattr(bot, "_erro_api", lambda p, s: "Materialize a base")
    _auth(5)
    out = bot.processar(5, "-23.55,-46.63", _S)
    assert "materialize" in _textos(out).lower()
    assert not any("pdf" in a for a in out)


# --- laco de long-polling: relatorio duplicado ------------------------------
#
# O bug real: DUAS instancias no mesmo token se derrubam com HTTP 409 e a mesma
# mensagem chega as duas -> a pessoa recebe DOIS relatorios. Antes, o laco so
# imprimia o erro e refazia a volta na hora (busy-loop), sem detectar nada.


class _Parar(BaseException):
    """Encerra o laco infinito do `main()` no fim do roteiro do teste.

    Herda de BaseException de proposito: o `main()` engole `Exception` para nao
    cair por erro de uma mensagem, e isso passaria batido.
    """


def _erro_http(status: int) -> requests.HTTPError:
    resp = requests.Response()
    resp.status_code = status
    return requests.HTTPError(f"HTTP {status}", response=resp)


@pytest.fixture
def _loop(monkeypatch):
    """Prepara `main()` para rodar sem rede/disco e devolve o registro de chamadas."""
    monkeypatch.setattr(bot, "get_settings", lambda: _S)
    monkeypatch.setattr(bot, "_configurar_menu_comandos", lambda token: None)
    monkeypatch.setattr(bot, "_carregar_sessoes", lambda s: None)
    monkeypatch.setattr(bot, "_salvar_sessoes", lambda s: None)
    reg: dict = {"processadas": [], "esperas": []}
    # registra a espera em vez de dormir de verdade (o teste nao pode levar 30s).
    # Patch no modulo `time` (compartilhado), nao em `bot.time` — assim o fixture
    # nao depende de o bot ter o import, e o teste falha na ASSERCAO, nao no setup.
    monkeypatch.setattr(time, "sleep", lambda seg: reg["esperas"].append(seg))
    monkeypatch.setattr(bot, "_enviar", lambda token, chat, acao: None)
    monkeypatch.setattr(
        bot,
        "processar",
        lambda chat, texto, s, notify=None: reg["processadas"].append((chat, texto)) or [],
    )
    return reg


def _roteiro(monkeypatch, respostas: list):
    """Faz `_tg` seguir `respostas` em getUpdates; o resto vira no-op."""
    fila = list(respostas)

    def fake_tg(token, method, **params):
        if method != "getUpdates":
            return {"ok": True}
        if not fila:
            raise _Parar
        item = fila.pop(0)
        if isinstance(item, BaseException):
            raise item
        return {"result": item}

    monkeypatch.setattr(bot, "_tg", fake_tg)


def _update(uid: int, texto: str, chat: int = 7) -> dict:
    return {"update_id": uid, "message": {"chat": {"id": chat}, "text": texto}}


def test_espera_cresce_e_satura():
    assert bot._espera(1) < bot._espera(3) < bot._espera(5)
    assert bot._espera(50) == 30.0  # nao passa de 30s


def test_409_seguidos_abortam_com_mensagem_clara(monkeypatch, _loop):
    _roteiro(monkeypatch, [_erro_http(409)] * bot._MAX_CONFLITOS)
    with pytest.raises(SystemExit) as exc:
        bot.main()
    assert "409" in str(exc.value)
    assert "outra instancia" in str(exc.value).lower()


def test_409_isolado_nao_derruba_o_bot(monkeypatch, _loop):
    """Um 409 logo apos restart e normal — o bot espera e segue."""
    _roteiro(monkeypatch, [_erro_http(409), [_update(1, "-21.9,-46.6")]])
    with pytest.raises(_Parar):
        bot.main()
    assert _loop["processadas"] == [(7, "-21.9,-46.6")]


def test_erro_de_rede_espera_em_vez_de_busy_loop(monkeypatch, _loop):
    _roteiro(monkeypatch, [requests.ConnectionError("rede caiu"), []])
    with pytest.raises(_Parar):
        bot.main()
    assert _loop["esperas"] and _loop["esperas"][0] > 0  # esperou antes de tentar de novo


def test_update_reentregue_nao_gera_segundo_relatorio(monkeypatch, _loop):
    """O MESMO update_id chegando duas vezes deve virar UM relatorio so."""
    upd = _update(42, "Av. Paulista 1000")
    _roteiro(monkeypatch, [[upd], [upd]])
    with pytest.raises(_Parar):
        bot.main()
    assert _loop["processadas"] == [(7, "Av. Paulista 1000")]


def test_updates_distintos_sao_ambos_processados(monkeypatch, _loop):
    """A guarda de duplicado nao pode engolir mensagem nova."""
    _roteiro(monkeypatch, [[_update(1, "primeiro")], [_update(2, "segundo")]])
    with pytest.raises(_Parar):
        bot.main()
    assert _loop["processadas"] == [(7, "primeiro"), (7, "segundo")]
