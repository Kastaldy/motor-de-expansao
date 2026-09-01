"""Testes do Relatorio Municipal (BLK-RELMUN): fluxo UF->municipio no bot + resolucao.

Herméticos: nao tocam a base de 1,9 GB (o indice de municipios e monkeypatchado) nem a
rede do Telegram/API (consultar_pdf_municipio e monkeypatchado).
"""

from __future__ import annotations

import pytest

from motor_expansao.api import service
from motor_expansao.api import telegram_bot as bot
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
    out = bot.processar(1, "Municipal (bairros)", _S)
    assert "estado" in _textos(out).lower()
    assert bot._sessao(1)["etapa"] == "muni_uf"


def test_uf_valida_pede_municipio():
    _auth(1)
    bot.processar(1, "Municipal (bairros)", _S)
    out = bot.processar(1, "TO", _S)
    assert "municipio" in _textos(out).lower()
    assert bot._sessao(1)["muni_uf"] == "TO"
    assert bot._sessao(1)["etapa"] == "muni_nome"


def test_uf_invalida_mantem_etapa():
    _auth(1)
    bot.processar(1, "Municipal (bairros)", _S)
    out = bot.processar(1, "ZZ", _S)
    assert "invalida" in _textos(out).lower()
    assert bot._sessao(1)["etapa"] == "muni_uf"


def test_municipio_gera_pdf(monkeypatch):
    monkeypatch.setattr(bot, "consultar_pdf_municipio",
                        lambda uf, m, s, st, unidade="bairro": (b"%PDF-fake", None))
    _auth(2, "Maria")
    bot.processar(2, "Municipal (bairros)", _S)
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
        lambda uf, m, s, st, unidade="bairro": (
            None, "Municipio 'x' nao encontrado. Voce quis dizer: Palmas?"
        ),
    )
    _auth(3)
    bot.processar(3, "Municipal (bairros)", _S)
    bot.processar(3, "TO", _S)
    out = bot.processar(3, "x", _S)
    assert "quis dizer" in _textos(out).lower()
    assert not any("pdf" in a for a in out)
    assert bot._sessao(3)["etapa"] == "muni_nome"  # segue pronto p/ nova tentativa


def test_voltar_do_municipio_para_uf():
    _auth(4)
    bot.processar(4, "Municipal (bairros)", _S)
    bot.processar(4, "TO", _S)
    out = bot.processar(4, "⬅️ Voltar", _S)
    assert "estado" in _textos(out).lower()
    assert bot._sessao(4)["etapa"] == "muni_uf"


def test_pontual_ainda_funciona():
    _auth(5)
    out = bot.processar(5, "Relatorio Pontual", _S)
    assert "localizacao" in _textos(out).lower()
    assert bot._sessao(5).get("etapa") is None


# --- Escolha da UNIDADE no menu (Juan, 2026-08-19) ------------------------------------
# O bot passou a oferecer "Municipal (hexagonos)" e "Municipal (bairros)". A unidade e'
# guardada na sessao e precisa chegar INTACTA ate a chamada da API -- se ela se perdesse no
# meio, os dois botoes gerariam o mesmo relatorio e ninguem notaria pelo texto.


def test_menu_oferece_as_tres_opcoes():
    assert bot._KB_MENU == [
        [bot._BTN_PONTUAL],
        [bot._BTN_MUNICIPAL_HEX],
        [bot._BTN_MUNICIPAL_BAIRRO],
        ["Ajuda"],
    ]


@pytest.mark.parametrize(
    ("botao", "esperado"),
    [
        ("Municipal (bairros)", "bairro"),
        ("Municipal (hexagonos)", "hexagono"),
    ],
)
def test_unidade_escolhida_chega_na_api(monkeypatch, botao, esperado):
    recebido = {}

    def _falso(uf, m, s, st, unidade="bairro"):
        recebido["unidade"] = unidade
        return b"%PDF-fake", None

    monkeypatch.setattr(bot, "consultar_pdf_municipio", _falso)
    chat = 900 + hash(botao) % 50
    _auth(chat, "QA")
    bot.processar(chat, botao, _S)
    bot.processar(chat, "TO", _S)
    out = bot.processar(chat, "Palmas", _S)

    assert recebido["unidade"] == esperado
    # O rotulo da mensagem diz ao usuario QUAL relatorio veio.
    texto = _textos(out)
    assert ("hexágonos" if esperado == "hexagono" else "bairros") in texto
    # E o nome do arquivo tambem, para os dois nao se confundirem no Telegram.
    nomes = [a.get("filename", "") for a in out if "pdf" in a]
    assert any(esperado in n for n in nomes), nomes


def test_rotulo_antigo_explica_em_vez_de_escolher(monkeypatch):
    """"Relatorio Municipal" (teclado em cache) NAO pode escolher unidade por conta propria.

    Mapea-lo silenciosamente para bairro seria o mesmo chute que este ciclo veio eliminar --
    e o usuario receberia a outra leitura sem entender por que. Ele responde explicando que a
    opcao virou duas e devolve o teclado novo; nenhuma chamada a API acontece.
    """
    chamou = []
    monkeypatch.setattr(
        bot, "consultar_pdf_municipio",
        lambda *a, **k: (chamou.append(1), (b"%PDF", None))[1],
    )
    _auth(970, "QA")
    out = bot.processar(970, "Relatorio Municipal", _S)

    texto = _textos(out)
    assert "duas leituras" in texto
    assert "Municipal (hexagonos)" in texto and "Municipal (bairros)" in texto
    assert not chamou, "o rotulo antigo nao pode disparar geracao de relatorio"
    assert bot._sessao(970).get("etapa") is None
    # E o teclado volta com as 3 opcoes atuais.
    assert any(a.get("keyboard") == bot._KB_MENU for a in out)


def test_prompt_de_uf_diz_a_unidade_escolhida():
    """Depois do menu, o titulo e' a unica pista de qual relatorio esta sendo montado."""
    _auth(971, "QA")
    out_hex = bot.processar(971, "Municipal (hexagonos)", _S)
    assert "hexágonos" in _textos(out_hex)

    _auth(972, "QA")
    out_bai = bot.processar(972, "Municipal (bairros)", _S)
    assert "bairros" in _textos(out_bai)


def test_voltar_preserva_a_unidade():
    """Voltar da etapa do nome nao pode perder a escolha feita no menu."""
    _auth(973, "QA")
    bot.processar(973, "Municipal (hexagonos)", _S)
    bot.processar(973, "TO", _S)
    out = bot.processar(973, "voltar", _S)

    assert "hexágonos" in _textos(out)
    assert bot._sessao(973)["muni_unidade"] == "hexagono"
