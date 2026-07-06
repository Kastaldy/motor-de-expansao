"""Testes do Relatorio Municipal (BLK-RELMUN): fluxo UF->municipio no bot + resolucao.

Herméticos: nao tocam a base de 1,9 GB (o indice de municipios e monkeypatchado) nem a
rede do Telegram/API (consultar_pdf_municipio e monkeypatchado).
"""

from __future__ import annotations

import pytest

from motor_expansao.api import service, telegram_bot as bot
from motor_expansao.api.settings import Settings

_S = Settings(bot_senha="abre", telegram_token="x")

# Indice falso: uf -> {nome_normalizado -> {nome, cod}}.
_IDX_FAKE = {
    "TO": {
        "palmas": {"nome": "Palmas", "cod": "1721000"},
        "paraiso do tocantins": {"nome": "Paraíso do Tocantins", "cod": "1716109"},
        "porto nacional": {"nome": "Porto Nacional", "cod": "1718204"},
    },
    "SP": {"sao paulo": {"nome": "São Paulo", "cod": "3550308"}},
}


@pytest.fixture(autouse=True)
def _limpa_sessoes():
    bot._sessoes.clear()
    yield
    bot._sessoes.clear()


@pytest.fixture
def _idx(monkeypatch):
    monkeypatch.setattr(service, "_indice_municipios", lambda _p: _IDX_FAKE)


def _textos(acoes) -> str:
    return " || ".join(a.get("text", "<pdf>") for a in acoes)


def _auth(cid: int, nome: str = "Tester") -> None:
    bot.processar(cid, "abre", _S)
    bot.processar(cid, nome, _S)


# --- resolucao de municipio (service, sem base) -----------------------------


def test_norm_remove_acento_e_caso():
    assert service._norm("São Paulo") == "sao paulo"
    assert service._norm("  PALMÁS ") == "palmas"


def test_resolver_exato_e_sem_acento(_idx):
    assert service.resolver_municipio("TO", "palmas", _S) == ("Palmas", ["Palmas"])
    assert service.resolver_municipio("TO", "Palmás", _S)[0] == "Palmas"


def test_resolver_ambiguo_devolve_sugestoes(_idx):
    # "pa" casa Palmas E Paraíso -> ambiguo -> nao resolve, sugere.
    nome, cands = service.resolver_municipio("TO", "pa", _S)
    assert nome is None
    assert "Palmas" in cands and "Paraíso do Tocantins" in cands


def test_resolver_substring_unica_resolve(_idx):
    # "por" so casa Porto Nacional -> resolve (tolerante a nome parcial).
    assert service.resolver_municipio("TO", "por", _S) == ("Porto Nacional", ["Porto Nacional"])


def test_resolver_nao_encontrado(_idx):
    assert service.resolver_municipio("TO", "xyzzy", _S) == (None, [])


def test_listar_ufs_e_municipios(_idx):
    assert service.listar_ufs(_S) == ["SP", "TO"]
    assert "Palmas" in service.listar_municipios("TO", _S)


# --- fluxo do bot: menu -> UF -> municipio -> PDF ---------------------------


def test_municipal_pede_uf():
    _auth(1)
    out = bot.processar(1, "Relatorio Municipal", _S)
    assert "estado" in _textos(out).lower()
    assert bot._sessao(1)["etapa"] == "muni_uf"


def test_uf_valida_pede_municipio():
    _auth(1)
    bot.processar(1, "Relatorio Municipal", _S)
    out = bot.processar(1, "TO", _S)
    assert "municipio" in _textos(out).lower()
    assert bot._sessao(1)["muni_uf"] == "TO"
    assert bot._sessao(1)["etapa"] == "muni_nome"


def test_uf_invalida_mantem_etapa():
    _auth(1)
    bot.processar(1, "Relatorio Municipal", _S)
    out = bot.processar(1, "ZZ", _S)
    assert "invalida" in _textos(out).lower()
    assert bot._sessao(1)["etapa"] == "muni_uf"


def test_municipio_gera_pdf(monkeypatch):
    monkeypatch.setattr(bot, "consultar_pdf_municipio", lambda uf, m, s, st: (b"%PDF-fake", None))
    _auth(2, "Maria")
    bot.processar(2, "Relatorio Municipal", _S)
    bot.processar(2, "TO", _S)
    out = bot.processar(2, "Palmas", _S)
    texto = _textos(out)
    assert "Palmas" in texto and "TO" in texto
    assert "Maria" in texto
    assert any("pdf" in a for a in out)
    assert bot._sessao(2)["etapa"] is None  # volta ao menu


def test_municipio_erro_mostra_mensagem(monkeypatch):
    monkeypatch.setattr(
        bot, "consultar_pdf_municipio",
        lambda uf, m, s, st: (None, "Municipio 'x' nao encontrado. Voce quis dizer: Palmas?"),
    )
    _auth(3)
    bot.processar(3, "Relatorio Municipal", _S)
    bot.processar(3, "TO", _S)
    out = bot.processar(3, "x", _S)
    assert "quis dizer" in _textos(out).lower()
    assert not any("pdf" in a for a in out)
    assert bot._sessao(3)["etapa"] == "muni_nome"  # segue pronto p/ nova tentativa


def test_voltar_do_municipio_para_uf():
    _auth(4)
    bot.processar(4, "Relatorio Municipal", _S)
    bot.processar(4, "TO", _S)
    out = bot.processar(4, "⬅️ Voltar", _S)
    assert "estado" in _textos(out).lower()
    assert bot._sessao(4)["etapa"] == "muni_uf"


def test_pontual_ainda_funciona():
    _auth(5)
    out = bot.processar(5, "Relatorio Pontual", _S)
    assert "localizacao" in _textos(out).lower()
    assert bot._sessao(5).get("etapa") is None
