"""Testes do bot Telegram (BLK-API-07): acesso -> login -> localizacao -> PDF."""

from __future__ import annotations

import pytest

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
