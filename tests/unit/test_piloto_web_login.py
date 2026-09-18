"""Rotas de entrada e saida (`POST /api/login` e `/api/logout`) — sem tocar banco nenhum.

As rotas sao invocadas DIRETO, como o resto da suite do piloto faz: o CI nao tem Postgres, e
o que precisa ser guardado aqui e' decisao de contrato, nao integracao.

O que mais importa neste arquivo, em ordem:

1. **O 404 com a chave dormente.** E' o estado de producao HOJE. Uma rota de login que
   responde quando o Authelia e' quem autentica seria porta anunciada e sem uso.
2. **O mesmo 401 para login inexistente e senha errada** -- e, junto, que `verificar` roda
   nos DOIS caminhos. A defesa contra oraculo por cronometro mora em `senhas.verificar`
   (ele paga um `ph.hash` descartavel quando o hash e' nulo); um curto-circuito em
   `credencial is None` mataria a defesa em silencio e o teste da MENSAGEM continuaria verde.
3. **Os flags do cookie**, que sao a decisao 2 em forma executavel: `lembrar` muda a
   PERSISTENCIA do cookie, nunca o tempo de vida da sessao.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import acesso  # noqa: E402
import app as pilot  # noqa: E402

from motor_expansao.db import sessoes as db_sessoes  # noqa: E402
from motor_expansao.db.rbac import Identidade  # noqa: E402


class _Requisicao:
    """So' o que o `logout` usa: `.cookies`."""

    def __init__(self, cookies: dict[str, str] | None = None) -> None:
        self.cookies = cookies or {}


def _cookies_da(resposta: Any) -> list[str]:
    return [v.decode("latin-1") for k, v in resposta.raw_headers if k == b"set-cookie"]


def _sessao(id_usuario: int = 7, login: str = "vinicius") -> Any:
    return db_sessoes.SessaoValida(
        identidade=Identidade(
            id_usuario=id_usuario, login=login, perfil="growth", permissoes=frozenset()
        ),
        id_sessao=42,
        ultimo_acesso=None,
    )


@pytest.fixture
def ligado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, "1")


@pytest.fixture(autouse=True)
def _sem_eventos(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
    """Os eventos nunca vao ao banco; ficam registrados para conferencia."""
    from motor_expansao.db import eventos as db_eventos

    vistos: list[tuple[str, int]] = []
    monkeypatch.setattr(db_eventos, "registrar_login", lambda **kw: vistos.append(("login", kw["autor"])))
    monkeypatch.setattr(db_eventos, "registrar_logout", lambda **kw: vistos.append(("logout", kw["autor"])))
    return vistos


def _preparar(
    monkeypatch: pytest.MonkeyPatch,
    *,
    credencial: Any,
    confere: bool,
    verificacoes: list[Any] | None = None,
) -> None:
    from motor_expansao.db import senhas as db_senhas
    from motor_expansao.db import usuarios as db_usuarios

    monkeypatch.setattr(db_usuarios, "credenciais_por_login", lambda _l: credencial)

    def _verificar(senha: str, hash_guardado: str | None) -> bool:
        if verificacoes is not None:
            verificacoes.append(hash_guardado)
        return confere

    monkeypatch.setattr(db_senhas, "verificar", _verificar)
    monkeypatch.setattr(
        db_sessoes, "abrir", lambda **_kw: db_sessoes.SessaoAberta("tok-secreto", 42, None)
    )


def _credencial(deve_trocar: bool = False) -> Any:
    from motor_expansao.db.usuarios import Credencial

    return Credencial(id_usuario=7, deve_trocar=deve_trocar, senha_hash="$argon2id$real")


# --------------------------------------------------------------------------------------
# 1. Dormente: a rota nao existe neste deploy
# --------------------------------------------------------------------------------------


def test_com_a_chave_desligada_o_login_e_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """404, e nao 501 nem 403: anunciar uma porta de login que o sistema nao usa so' convida
    tentativa. E' o estado de producao HOJE, com o Authelia autenticando."""
    monkeypatch.delenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, raising=False)
    with pytest.raises(pilot.HTTPException) as caiu:
        pilot.login(pilot.LoginIn(login="v", senha="x"))
    assert caiu.value.status_code == 404


def test_com_a_chave_desligada_o_logout_e_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, raising=False)
    with pytest.raises(pilot.HTTPException) as caiu:
        pilot.logout(_Requisicao())
    assert caiu.value.status_code == 404


# --------------------------------------------------------------------------------------
# 2. O mesmo 401 — e a defesa contra oraculo por cronometro
# --------------------------------------------------------------------------------------


def test_login_inexistente_e_senha_errada_dao_a_MESMA_resposta(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Distinguir entregaria ao visitante um oraculo de quem trabalha aqui."""
    _preparar(monkeypatch, credencial=None, confere=False)
    with pytest.raises(pilot.HTTPException) as sem_usuario:
        pilot.login(pilot.LoginIn(login="fantasma", senha="x"))

    _preparar(monkeypatch, credencial=_credencial(), confere=False)
    with pytest.raises(pilot.HTTPException) as senha_errada:
        pilot.login(pilot.LoginIn(login="vinicius", senha="errada"))

    assert sem_usuario.value.status_code == senha_errada.value.status_code == 401
    assert sem_usuario.value.detail == senha_errada.value.detail


def test_a_recusa_vira_evento_com_o_id_quando_a_conta_existe(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from motor_expansao.db import eventos as db_eventos

    vistos: list[dict[str, Any]] = []
    monkeypatch.setattr(db_eventos, "registrar_login_recusado", lambda **kw: vistos.append(kw))
    _preparar(monkeypatch, credencial=_credencial(), confere=False)

    with pytest.raises(pilot.HTTPException):
        pilot.login(pilot.LoginIn(login="vinicius", senha="errada"))

    assert vistos == [{"autor": 7, "usuario_conhecido": True}]


def test_a_recusa_de_usuario_inexistente_vira_evento_sem_autor(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from motor_expansao.db import eventos as db_eventos

    vistos: list[dict[str, Any]] = []
    monkeypatch.setattr(db_eventos, "registrar_login_recusado", lambda **kw: vistos.append(kw))
    _preparar(monkeypatch, credencial=None, confere=False)

    with pytest.raises(pilot.HTTPException):
        pilot.login(pilot.LoginIn(login="fantasma", senha="x"))

    assert vistos == [{"autor": None, "usuario_conhecido": False}]


def test_registrar_a_recusa_NAO_muda_a_resposta_ao_visitante(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A asserção central deste bloco.

    O banco passa a distinguir os dois casos — e a RESPOSTA não pode distinguir, senão eu
    teria construído, do lado de fora, exatamente o oráculo que o resto do desenho existe
    para evitar. Status e mensagem idênticos, com o evento gravando coisas diferentes.
    """
    from motor_expansao.db import eventos as db_eventos

    vistos: list[dict[str, Any]] = []
    monkeypatch.setattr(db_eventos, "registrar_login_recusado", lambda **kw: vistos.append(kw))

    _preparar(monkeypatch, credencial=None, confere=False)
    with pytest.raises(pilot.HTTPException) as sem_usuario:
        pilot.login(pilot.LoginIn(login="fantasma", senha="x"))

    _preparar(monkeypatch, credencial=_credencial(), confere=False)
    with pytest.raises(pilot.HTTPException) as senha_errada:
        pilot.login(pilot.LoginIn(login="vinicius", senha="errada"))

    assert sem_usuario.value.status_code == senha_errada.value.status_code
    assert sem_usuario.value.detail == senha_errada.value.detail
    # ...e o banco, esse sim, separou os dois.
    assert [v["usuario_conhecido"] for v in vistos] == [False, True]


def test_falha_ao_gravar_a_recusa_nao_muda_a_resposta(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rastro nunca altera o que o visitante recebe — nem para melhor, nem para pior."""
    from motor_expansao.db import eventos as db_eventos

    monkeypatch.setattr(
        db_eventos,
        "registrar_login_recusado",
        lambda **_kw: (_ for _ in ()).throw(RuntimeError("banco fora")),
    )
    _preparar(monkeypatch, credencial=_credencial(), confere=False)

    with pytest.raises(pilot.HTTPException) as caiu:
        pilot.login(pilot.LoginIn(login="vinicius", senha="errada"))
    assert caiu.value.status_code == 401


def test_a_senha_e_verificada_MESMO_sem_credencial(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A defesa de tempo mora em `senhas.verificar`, que paga um `ph.hash` descartavel
    quando o hash e' nulo. Curto-circuitar em `credencial is None` a mataria em SILENCIO --
    e o teste da mensagem, acima, continuaria verde. Este teste e' o que impede isso.
    """
    verificacoes: list[Any] = []
    _preparar(monkeypatch, credencial=None, confere=False, verificacoes=verificacoes)
    with pytest.raises(pilot.HTTPException):
        pilot.login(pilot.LoginIn(login="fantasma", senha="x"))

    assert verificacoes == [None], "nao verificou a senha quando o login nao existe"


# --------------------------------------------------------------------------------------
# 3. Sucesso: cookie, corpo e evento
# --------------------------------------------------------------------------------------


def test_o_token_vai_no_COOKIE_e_nunca_no_corpo(ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """O corpo da resposta trafega em log de proxy e em ferramenta de rede; o cookie
    `httponly` nao. O token so' existe no cookie."""
    _preparar(monkeypatch, credencial=_credencial(), confere=True)
    resposta = pilot.login(pilot.LoginIn(login="vinicius", senha="certa"))

    assert b"tok-secreto" not in resposta.body, "o token vazou no corpo da resposta"
    assert any("tok-secreto" in c for c in _cookies_da(resposta)), "o token nao foi no cookie"


def test_o_cookie_e_httponly_e_samesite_lax(ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _preparar(monkeypatch, credencial=_credencial(), confere=True)
    cookie = _cookies_da(pilot.login(pilot.LoginIn(login="v", senha="c")))[0].lower()
    assert "httponly" in cookie, "JavaScript conseguiria ler o token"
    assert "samesite=lax" in cookie
    assert "path=/" in cookie


def test_LEMBRAR_muda_a_persistencia_do_cookie_e_nao_a_vida_da_sessao(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Decisao 2, opcao (a) -- FIEL ao Authelia, onde `remember_me` e' igual ao `expiration`.

    COM a caixinha: cookie persistente de 8h, que sobrevive a fechar o navegador.
    SEM: cookie de sessao, que morre com a janela. Nos DOIS casos a sessao no banco dura os
    mesmos 8h -- e e' por isso que `abrir()` nao recebe parametro nenhum de duracao.
    """
    _preparar(monkeypatch, credencial=_credencial(), confere=True)
    com = _cookies_da(pilot.login(pilot.LoginIn(login="v", senha="c", lembrar=True)))[0].lower()
    sem = _cookies_da(pilot.login(pilot.LoginIn(login="v", senha="c", lembrar=False)))[0].lower()

    assert f"max-age={db_sessoes.DURACAO_SESSAO_H * 3600}" in com
    assert "max-age" not in sem, "cookie de sessao nao pode ter validade propria"


def test_o_corpo_diz_a_SPA_se_ela_abre_a_tela_de_troca(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`deve_trocar_senha` vem da MESMA consulta da credencial (D26): buscar depois seria
    uma segunda ida ao banco por um dado que ja' estava na linha."""
    _preparar(monkeypatch, credencial=_credencial(deve_trocar=True), confere=True)
    assert b'"deve_trocar_senha":true' in pilot.login(pilot.LoginIn(login="v", senha="c")).body


def test_o_login_grava_o_evento_com_o_autor_certo(
    ligado: None, monkeypatch: pytest.MonkeyPatch, _sem_eventos: list[tuple[str, int]]
) -> None:
    _preparar(monkeypatch, credencial=_credencial(), confere=True)
    pilot.login(pilot.LoginIn(login="v", senha="c"))
    assert _sem_eventos == [("login", 7)]


def test_falha_ao_gravar_o_evento_NAO_impede_a_entrada(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rastro nunca barra a pessoa: a alternativa e' impedir o trabalho por causa do log."""
    from motor_expansao.db import eventos as db_eventos

    _preparar(monkeypatch, credencial=_credencial(), confere=True)
    monkeypatch.setattr(
        db_eventos, "registrar_login", lambda **_kw: (_ for _ in ()).throw(RuntimeError("x"))
    )
    resposta = pilot.login(pilot.LoginIn(login="v", senha="c"))
    assert any("tok-secreto" in c for c in _cookies_da(resposta))


# --------------------------------------------------------------------------------------
# 4. Logout: revoga no SERVIDOR, e e' idempotente
# --------------------------------------------------------------------------------------


def test_logout_revoga_no_servidor_e_apaga_os_dois_cookies(
    ligado: None, monkeypatch: pytest.MonkeyPatch, _sem_eventos: list[tuple[str, int]]
) -> None:
    """Revogar no servidor e' o ponto inteiro de a D30 ter escolhido tabela: o
    `BotaoSair.tsx` ja' documenta que limpar estado no cliente NAO e' logout."""
    revogados: list[dict[str, Any]] = []
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: _sessao())
    monkeypatch.setattr(db_sessoes, "revogar", lambda **kw: (revogados.append(kw), True)[1])

    resposta = pilot.logout(_Requisicao(cookies={acesso.COOKIE_SESSAO_DEV: "tok"}))

    assert revogados and revogados[0]["token"] == "tok"
    assert _sem_eventos == [("logout", 7)]
    apagados = " ".join(_cookies_da(resposta))
    assert acesso.COOKIE_SESSAO in apagados and acesso.COOKIE_SESSAO_DEV in apagados


def test_logout_sem_sessao_viva_nao_e_erro(ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sair duas vezes, ou sair com a sessao ja' vencida, e' idempotente -- e o cookie e'
    apagado de todo jeito, senao o navegador ficaria com lixo que o portao ja' recusa."""
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: None)
    monkeypatch.setattr(db_sessoes, "revogar", lambda **_kw: pytest.fail("revogou sem sessao"))

    resposta = pilot.logout(_Requisicao(cookies={acesso.COOKIE_SESSAO_DEV: "vencido"}))
    assert resposta.status_code == 200
    assert len(_cookies_da(resposta)) == 2


def test_logout_sem_cookie_nenhum_tambem_responde(ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: pytest.fail("validou sem cookie"))
    assert pilot.logout(_Requisicao()).status_code == 200
