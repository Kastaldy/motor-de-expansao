"""Travas de seguranca do bot Telegram (BLK-SEC-05).

Cobrem o lockout anti-brute-force da senha, a comparacao em tempo constante e a
ausencia de PII (nome/chat_id cru) nos logs operacionais.
"""

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


# ── lockout anti-brute-force ────────────────────────────────────────────────
def test_lockout_apos_muitas_tentativas() -> None:
    cid = 100
    bot.processar(cid, "x", _S)  # 1a msg = saudacao (nao conta)
    for _ in range(bot._SENHA_MAX_TENTATIVAS - 1):
        out = bot.processar(cid, "errada", _S)
        assert "incorreta" in _textos(out).lower()
    # A tentativa que atinge o teto -> bloqueio.
    out = bot.processar(cid, "errada", _S)
    assert "muitas tentativas" in _textos(out).lower()
    assert bot._sessao(cid).get("bloqueado_ate", 0) > 0


def test_bloqueado_recusa_ate_a_senha_certa() -> None:
    cid = 101
    bot.processar(cid, "x", _S)
    for _ in range(bot._SENHA_MAX_TENTATIVAS):
        bot.processar(cid, "errada", _S)
    # Bloqueado: mesmo a senha CORRETA nao autoriza enquanto durar o lockout.
    out = bot.processar(cid, "abre", _S)
    assert "aguarde" in _textos(out).lower()
    assert not bot._sessao(cid).get("autorizado")


def test_senha_certa_reseta_contador() -> None:
    cid = 102
    bot.processar(cid, "x", _S)     # saudacao
    bot.processar(cid, "errada", _S)  # tentativa 1
    bot.processar(cid, "errada", _S)  # tentativa 2
    out = bot.processar(cid, "abre", _S)  # correta antes do teto -> autoriza
    assert "chamar" in _textos(out).lower()
    assert bot._sessao(cid)["autorizado"] is True
    assert bot._sessao(cid).get("tentativas", 0) == 0


def test_senha_errada_de_mesmo_tamanho_nao_autoriza() -> None:
    cid = 103
    bot.processar(cid, "x", _S)
    out = bot.processar(cid, "abrx", _S)  # mesmo tamanho, valor diferente
    assert not bot._sessao(cid).get("autorizado")
    assert "incorreta" in _textos(out).lower()


# ── referencia opaca de chat ────────────────────────────────────────────────
def test_chat_ref_e_opaca_e_estavel() -> None:
    ref = bot._chat_ref(987654321, "token-do-bot")
    assert ref.startswith("#") and len(ref) == 9
    assert "987654321" not in ref
    assert ref == bot._chat_ref(987654321, "token-do-bot")  # deterministico c/ a mesma chave
    assert ref != bot._chat_ref(987654322, "token-do-bot")  # sensivel ao id


def test_chat_ref_hmac_depende_da_chave_e_nao_e_sha256_nu() -> None:
    import hashlib

    # Chaves diferentes -> refs diferentes (nao reversivel sem o token do bot).
    assert bot._chat_ref(987654321, "chave-A") != bot._chat_ref(987654321, "chave-B")
    # E difere do sha256 NU (prova que a chave entra no digest, fechando o brute-force).
    nu = "#" + hashlib.sha256(b"987654321").hexdigest()[:8]
    assert bot._chat_ref(987654321, "token-do-bot") != nu


# ── log sem PII ─────────────────────────────────────────────────────────────
def test_log_estudo_nao_vaza_pii(monkeypatch, capsys) -> None:
    monkeypatch.setattr(bot, "resolver_local", lambda t, s: (-21.9, -46.6, "Aguas da Prata"))
    monkeypatch.setattr(bot, "consultar_pdf", lambda p, s: b"%PDF-fake")
    cid = 555123
    bot.processar(cid, "abre", _S)
    bot.processar(cid, "NomeSecretoDoUsuario", _S)  # login
    capsys.readouterr()  # descarta o que veio ate aqui
    bot.processar(cid, "-21.9,-46.6", _S)
    saida = capsys.readouterr().out
    assert "[ESTUDO]" in saida
    assert "chat=#" in saida
    # O log NAO pode conter o nome do usuario nem o chat_id cru.
    assert "NomeSecretoDoUsuario" not in saida
    assert str(cid) not in saida


# ── Pentest Onda B #13: escape de Markdown nos valores dinamicos ─────────────
def test_escape_md_escapa_so_os_metacaracteres_legados() -> None:
    bt = chr(96)  # backtick
    assert bot._escape_md("a_b*c[d]" + bt + "e") == r"a\_b\*c\[d]" + "\\" + bt + "e"
    # NAO escapa . ! ( ) - : no Markdown LEGADO isso imprimiria o backslash na tela.
    assert bot._escape_md("R. Dr. Joao (SP)!") == "R. Dr. Joao (SP)!"
    # preserva acento e emoji
    assert bot._escape_md("São Paulo 🎯") == "São Paulo 🎯"


def test_login_com_markdown_e_escapado() -> None:
    """Um login `[x](http://evil)` nao pode virar hyperlink na saudacao do bot."""
    cid = 700
    bot.processar(cid, "abre", _S)  # autoriza -> pede login
    out = bot.processar(cid, "[x](http://evil.example)", _S)  # login com injecao
    texto = _textos(out)
    # O colchete de abertura foi escapado -> o Telegram nao monta o link.
    assert r"\[x]" in texto
    # E o bold `*...*` NAO envolve um link funcional (o `*` nao e' seguido de `[`).
    assert "*[x](" not in texto


def test_nome_resolvido_e_login_escapados_no_relatorio(monkeypatch) -> None:
    """Nome vindo do geocoder e login entram escapados na legenda do PDF pontual."""
    monkeypatch.setattr(bot, "resolver_local", lambda t, s: (-23.5, -46.6, "Bar *do Ze*"))
    monkeypatch.setattr(bot, "consultar_pdf", lambda p, s: b"%PDF-fake")
    cid = 701
    bot.processar(cid, "abre", _S)
    bot.processar(cid, "chef_boss", _S)  # login com underscore
    out = bot.processar(cid, "-23.5,-46.6", _S)
    texto = _textos(out)
    assert r"Bar \*do Ze\*" in texto  # asteriscos do nome escapados
    assert r"chef\_boss" in texto  # underscore do login escapado
