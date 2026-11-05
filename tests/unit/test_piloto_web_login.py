"""Rotas de entrada e saida (`POST /api/login` e `/api/logout`) — sem tocar banco nenhum.

As rotas sao invocadas DIRETO, como o resto da suite do piloto faz: a suite unitaria nao tem Postgres, e
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
from types import SimpleNamespace
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
    # DEC-081: `Identidade` passou a exigir `paises`. Login/logout sao rotas PUBLICAS (sem gate
    # de pais), mas a construcao precisa do campo -- uso o pais DESTE processo (BR em teste).
    return db_sessoes.SessaoValida(
        identidade=Identidade(
            id_usuario=id_usuario,
            login=login,
            perfil="growth",
            permissoes=frozenset(),
            paises=frozenset({pilot.PERFIL.pais}),
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
    monkeypatch.setattr(
        db_eventos, "registrar_login", lambda **kw: vistos.append(("login", kw["autor"]))
    )
    monkeypatch.setattr(
        db_eventos, "registrar_logout", lambda **kw: vistos.append(("logout", kw["autor"]))
    )
    return vistos


@pytest.fixture(autouse=True)
def _reset_rate_limit_login() -> None:
    """O rate-limit por IP de /api/login (`rate_limit_login`) guarda estado de MODULO; zera
    entre testes, senao ~20 chamadas na mesma chave (origem 'desconhecido' no teste) fariam
    os ultimos casos receberem 429 no lugar do 401/200/503 esperado."""
    import rate_limit_login

    rate_limit_login._resetar_para_teste()
    yield
    rate_limit_login._resetar_para_teste()


class _RequisicaoDeLogin:
    """O que a rota de login usa do `Request`: cabecalhos e o peer TCP.

    Existe desde a 020, que passou a gravar DE ONDE a sessao veio. O default e' uma
    requisicao SEM `X-Forwarded-For` e sem peer -- ou seja, origem desconhecida, que e'
    estado legitimo e o caminho mais comum em teste.
    """

    def __init__(
        self, *, xff: str | None = None, agente: str | None = None, peer: str | None = None
    ) -> None:
        cabecalhos = {}
        if xff is not None:
            cabecalhos["x-forwarded-for"] = xff
        if agente is not None:
            cabecalhos["user-agent"] = agente
        self.headers = cabecalhos
        self.client = type("Peer", (), {"host": peer})() if peer else None
        # O handler de login carimba `request.state.login_na_trilha` no sucesso (BLK-BANCO-12);
        # o `.state` precisa existir e aceitar atribuicao, como no `Request` real.
        self.state = SimpleNamespace()


def _req(**kw: Any) -> Any:
    return _RequisicaoDeLogin(**kw)


def _preparar(
    monkeypatch: pytest.MonkeyPatch,
    *,
    credencial: Any,
    confere: bool,
    verificacoes: list[Any] | None = None,
) -> None:
    from motor_expansao.db import eventos as db_eventos
    from motor_expansao.db import senhas as db_senhas
    from motor_expansao.db import usuarios as db_usuarios

    monkeypatch.setattr(db_usuarios, "credenciais_por_login", lambda _l: credencial)
    # A trava de tentativas consulta o banco a cada login de conta existente; aqui ela sai
    # do caminho com contador ZERADO. Quem prova a trava sao os testes proprios dela.
    monkeypatch.setattr(db_eventos, "contar_recusas_recentes", lambda **_kw: 0)

    def _verificar(senha: str, hash_guardado: str | None) -> bool:
        if verificacoes is not None:
            verificacoes.append(hash_guardado)
        return confere

    monkeypatch.setattr(db_senhas, "verificar", _verificar)
    monkeypatch.setattr(
        db_sessoes, "abrir", lambda **_kw: db_sessoes.SessaoAberta("tok-secreto", 42, None)
    )


def _credencial(
    deve_trocar: bool = False, *, expira_em: Any = None, redefinida_em: Any = None
) -> Any:
    from motor_expansao.db.usuarios import Credencial

    return Credencial(
        id_usuario=7,
        deve_trocar=deve_trocar,
        senha_hash="$argon2id$real",
        expira_em=expira_em,
        redefinida_em=redefinida_em,
    )


def _daqui(minutos: int) -> Any:
    from datetime import UTC, datetime, timedelta

    return datetime.now(UTC) + timedelta(minutes=minutos)


# --------------------------------------------------------------------------------------
# 1. Dormente: a rota nao existe neste deploy
# --------------------------------------------------------------------------------------


def test_com_a_chave_desligada_o_login_e_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """404, e nao 501 nem 403: anunciar uma porta de login que o sistema nao usa so' convida
    tentativa. E' o estado de producao HOJE, com o Authelia autenticando."""
    monkeypatch.delenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, raising=False)
    with pytest.raises(pilot.HTTPException) as caiu:
        pilot.login(pilot.LoginIn(login="v", senha="x"), _req())
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
        pilot.login(pilot.LoginIn(login="fantasma", senha="x"), _req())

    _preparar(monkeypatch, credencial=_credencial(), confere=False)
    with pytest.raises(pilot.HTTPException) as senha_errada:
        pilot.login(pilot.LoginIn(login="vinicius", senha="errada"), _req())

    assert sem_usuario.value.status_code == senha_errada.value.status_code == 401
    assert sem_usuario.value.detail == senha_errada.value.detail


def _travar(monkeypatch: pytest.MonkeyPatch, recusas: int, *, confere: bool = False) -> list[str]:
    """Instala o contador e devolve a lista de chamadas caras que foram feitas.

    `confere=True` significa SENHA CERTA, e e' o que da poder aos testes da tranca: com
    senha errada o 401 sai por qualquer caminho, entao um teste que so' olhasse o codigo de
    status ficaria verde mesmo com a trava arrancada -- foi assim que duas assercoes minhas
    passaram vazias ate' a sabotagem de 18/09/2026 mostrar. Com a senha CERTA, so' a tranca
    pode negar.
    """
    from motor_expansao.db import eventos as db_eventos
    from motor_expansao.db import senhas as db_senhas

    caras: list[str] = []
    monkeypatch.setattr(db_eventos, "contar_recusas_recentes", lambda **_kw: recusas)
    # O autouse `_sem_eventos` cobre login/logout, nao a recusa: sem isto o caminho NAO
    # barrado iria ao banco de verdade.
    monkeypatch.setattr(db_eventos, "registrar_login_recusado", lambda **_kw: None)
    monkeypatch.setattr(
        db_senhas, "verificar", lambda *_a, **_k: (caras.append("argon2"), confere)[1]
    )
    monkeypatch.setattr(
        db_sessoes, "abrir", lambda **_kw: db_sessoes.SessaoAberta("tok-secreto", 42, None)
    )
    return caras


def test_na_quinta_recusa_a_conta_e_barrada(ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cinco e' o limite decidido em 18/09/2026: com cinco na janela, a sexta nao passa.

    A senha aqui esta' CERTA: sem a trava este login ENTRARIA, entao o 401 so' pode vir dela.
    """
    from motor_expansao.db import usuarios as db_usuarios

    monkeypatch.setattr(db_usuarios, "credenciais_por_login", lambda _l: _credencial())
    _travar(monkeypatch, recusas=5, confere=True)

    with pytest.raises(pilot.HTTPException) as caiu:
        pilot.login(pilot.LoginIn(login="vinicius", senha="a-senha-certa"), _req())
    assert caiu.value.status_code == 401


def test_com_quatro_recusas_ainda_passa(ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """A trava é no QUINTO, não no quarto — o limite é `>=`, e este teste fixa o lado de cá."""
    from motor_expansao.db import usuarios as db_usuarios

    monkeypatch.setattr(db_usuarios, "credenciais_por_login", lambda _l: _credencial())
    caras = _travar(monkeypatch, recusas=4)

    with pytest.raises(pilot.HTTPException):
        pilot.login(pilot.LoginIn(login="vinicius", senha="errada"), _req())
    assert caras == ["argon2"], "com 4 recusas a senha ainda deve ser verificada"


def test_excesso_de_tentativas_do_mesmo_IP_recebe_429(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rate-limit por IP (solidificacao #1): estourado o teto, /api/login devolve 429 ANTES
    do Argon2 -- sem rodar `verificar`. A chave e' o ULTIMO elemento do X-Forwarded-For (o
    que a borda anexa), entao variar o PREFIXO (o que o cliente dita) nao evade o teto."""
    import rate_limit_login

    from motor_expansao.db import usuarios as db_usuarios

    monkeypatch.setattr(rate_limit_login, "MAX_TENTATIVAS", 2)
    monkeypatch.setattr(db_usuarios, "credenciais_por_login", lambda _l: None)
    caras = _travar(monkeypatch, recusas=0, confere=False)

    corpo = pilot.LoginIn(login="x", senha="y")
    # As 2 primeiras passam (401), com PREFIXO de XFF diferente mas o MESMO ultimo elemento
    for i in range(2):
        with pytest.raises(pilot.HTTPException) as e:
            pilot.login(corpo, _req(xff=f"{i}.{i}.{i}.{i}, 203.0.113.5"))
        assert e.value.status_code == 401
    # A 3a estoura -> 429, e o Argon2 NAO roda nela
    with pytest.raises(pilot.HTTPException) as barrada:
        pilot.login(corpo, _req(xff="7.7.7.7, 203.0.113.5"))
    assert barrada.value.status_code == 429
    assert caras == ["argon2", "argon2"], "o Argon2 so roda nas 2 que passaram, nunca na barrada"


def test_a_conta_barrada_NAO_paga_o_argon2(ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Negar cedo é metade da defesa: uma rajada não pode queimar CPU a cada tentativa."""
    from motor_expansao.db import usuarios as db_usuarios

    monkeypatch.setattr(db_usuarios, "credenciais_por_login", lambda _l: _credencial())
    caras = _travar(monkeypatch, recusas=9)

    with pytest.raises(pilot.HTTPException):
        pilot.login(pilot.LoginIn(login="vinicius", senha="qualquer"), _req())
    assert caras == [], "verificou a senha de uma conta já barrada"


def test_tentativa_BARRADA_nao_vira_evento(ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """A asserção que impede a trava de virar arma.

    Se a tentativa barrada contasse, um atacante manteria a conta da vítima trancada para
    sempre com uma requisição a cada janela — o contador nunca drenaria e o bloqueio, que é
    temporário por desenho, viraria permanente. Não registrando, a janela sempre esvazia.
    """
    from motor_expansao.db import eventos as db_eventos
    from motor_expansao.db import usuarios as db_usuarios

    vistos: list[dict[str, Any]] = []
    monkeypatch.setattr(db_usuarios, "credenciais_por_login", lambda _l: _credencial())
    # O coletor entra DEPOIS do `_travar`, que tambem instala um dublê desta função: na
    # ordem inversa o no-op dele apagava a captura e a asserção ficava verde sozinha.
    _travar(monkeypatch, recusas=5, confere=True)
    monkeypatch.setattr(db_eventos, "registrar_login_recusado", lambda **kw: vistos.append(kw))

    with pytest.raises(pilot.HTTPException):
        pilot.login(pilot.LoginIn(login="vinicius", senha="a-senha-certa"), _req())
    assert vistos == [], "a tentativa barrada virou evento e prolongaria a própria trava"


def test_usuario_INEXISTENTE_nao_e_barrado_pela_trava(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Limitação declarada, não esquecimento.

    Sem `id_usuario` não há o que contar, e o IP — que resolveria — não está em `eventos`
    por causa do P15. Varredura de nomes inexistentes segue sem trava no banco; o que ela
    deixa é a linha de autoria nula e o registro da trilha, que tem o IP em arquivo.
    """
    from motor_expansao.db import eventos as db_eventos
    from motor_expansao.db import usuarios as db_usuarios

    contagens: list[Any] = []
    monkeypatch.setattr(db_usuarios, "credenciais_por_login", lambda _l: None)
    monkeypatch.setattr(
        db_eventos, "contar_recusas_recentes", lambda **kw: (contagens.append(kw), 99)[1]
    )
    monkeypatch.setattr(db_eventos, "registrar_login_recusado", lambda **_kw: None)
    from motor_expansao.db import senhas as db_senhas

    monkeypatch.setattr(db_senhas, "verificar", lambda *_a, **_k: False)

    with pytest.raises(pilot.HTTPException):
        pilot.login(pilot.LoginIn(login="fantasma", senha="x"), _req())
    assert contagens == [], "tentou contar recusas de quem não tem cadastro"


def test_a_conta_barrada_devolve_a_MESMA_mensagem(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dizer "conta bloqueada" avisaria a quem varre nomes que acertou um."""
    from motor_expansao.db import eventos as db_eventos
    from motor_expansao.db import usuarios as db_usuarios

    monkeypatch.setattr(db_usuarios, "credenciais_por_login", lambda _l: _credencial())
    _travar(monkeypatch, recusas=5, confere=True)
    with pytest.raises(pilot.HTTPException) as barrada:
        pilot.login(pilot.LoginIn(login="vinicius", senha="a-senha-certa"), _req())

    _preparar(monkeypatch, credencial=None, confere=False)
    monkeypatch.setattr(db_eventos, "registrar_login_recusado", lambda **_kw: None)
    with pytest.raises(pilot.HTTPException) as comum:
        pilot.login(pilot.LoginIn(login="fantasma", senha="x"), _req())

    assert barrada.value.status_code == comum.value.status_code
    assert barrada.value.detail == comum.value.detail


def test_a_recusa_vira_evento_com_o_id_quando_a_conta_existe(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from motor_expansao.db import eventos as db_eventos

    vistos: list[dict[str, Any]] = []
    monkeypatch.setattr(db_eventos, "registrar_login_recusado", lambda **kw: vistos.append(kw))
    _preparar(monkeypatch, credencial=_credencial(), confere=False)

    with pytest.raises(pilot.HTTPException):
        pilot.login(pilot.LoginIn(login="vinicius", senha="errada"), _req())

    assert vistos == [{"autor": 7, "usuario_conhecido": True}]


def test_a_recusa_de_usuario_inexistente_vira_evento_sem_autor(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from motor_expansao.db import eventos as db_eventos

    vistos: list[dict[str, Any]] = []
    monkeypatch.setattr(db_eventos, "registrar_login_recusado", lambda **kw: vistos.append(kw))
    _preparar(monkeypatch, credencial=None, confere=False)

    with pytest.raises(pilot.HTTPException):
        pilot.login(pilot.LoginIn(login="fantasma", senha="x"), _req())

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
        pilot.login(pilot.LoginIn(login="fantasma", senha="x"), _req())

    _preparar(monkeypatch, credencial=_credencial(), confere=False)
    with pytest.raises(pilot.HTTPException) as senha_errada:
        pilot.login(pilot.LoginIn(login="vinicius", senha="errada"), _req())

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
        pilot.login(pilot.LoginIn(login="vinicius", senha="errada"), _req())
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
        pilot.login(pilot.LoginIn(login="fantasma", senha="x"), _req())

    assert verificacoes == [None], "nao verificou a senha quando o login nao existe"


# --------------------------------------------------------------------------------------
# 3. Sucesso: cookie, corpo e evento
# --------------------------------------------------------------------------------------


def test_o_token_vai_no_COOKIE_e_nunca_no_corpo(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O corpo da resposta trafega em log de proxy e em ferramenta de rede; o cookie
    `httponly` nao. O token so' existe no cookie."""
    _preparar(monkeypatch, credencial=_credencial(), confere=True)
    resposta = pilot.login(pilot.LoginIn(login="vinicius", senha="certa"), _req())

    assert b"tok-secreto" not in resposta.body, "o token vazou no corpo da resposta"
    assert any("tok-secreto" in c for c in _cookies_da(resposta)), "o token nao foi no cookie"


def test_o_cookie_e_httponly_e_samesite_lax(ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _preparar(monkeypatch, credencial=_credencial(), confere=True)
    cookie = _cookies_da(pilot.login(pilot.LoginIn(login="v", senha="c"), _req()))[0].lower()
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
    com = _cookies_da(pilot.login(pilot.LoginIn(login="v", senha="c", lembrar=True), _req()))[
        0
    ].lower()
    sem = _cookies_da(pilot.login(pilot.LoginIn(login="v", senha="c", lembrar=False), _req()))[
        0
    ].lower()

    assert f"max-age={db_sessoes.DURACAO_SESSAO_H * 3600}" in com
    assert "max-age" not in sem, "cookie de sessao nao pode ter validade propria"


def test_o_corpo_diz_a_SPA_se_ela_abre_a_tela_de_troca(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`deve_trocar_senha` vem da MESMA consulta da credencial (D26): buscar depois seria
    uma segunda ida ao banco por um dado que ja' estava na linha."""
    _preparar(monkeypatch, credencial=_credencial(deve_trocar=True), confere=True)
    assert (
        b'"deve_trocar_senha":true' in pilot.login(pilot.LoginIn(login="v", senha="c"), _req()).body
    )


def test_o_login_grava_o_evento_com_o_autor_certo(
    ligado: None, monkeypatch: pytest.MonkeyPatch, _sem_eventos: list[tuple[str, int]]
) -> None:
    _preparar(monkeypatch, credencial=_credencial(), confere=True)
    pilot.login(pilot.LoginIn(login="v", senha="c"), _req())
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
    resposta = pilot.login(pilot.LoginIn(login="v", senha="c"), _req())
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


def test_logout_sem_cookie_nenhum_tambem_responde(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: pytest.fail("validou sem cookie"))
    assert pilot.logout(_Requisicao()).status_code == 200


# --------------------------------------------------------------------------------------
# A senha TEMPORARIA vence (D31, 18/09)
# --------------------------------------------------------------------------------------


def test_senha_temporaria_VENCIDA_nao_entra(ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """O prazo e' o que impede uma redefinicao esquecida de virar porta aberta indefinida.

    A senha esta' CERTA aqui (`confere=True`): sem a checagem de prazo, este login entraria.
    """
    _preparar(monkeypatch, credencial=_credencial(expira_em=_daqui(-1)), confere=True)
    with pytest.raises(pilot.HTTPException) as caiu:
        pilot.login(pilot.LoginIn(login="vinicius", senha="a-temporaria"), _req())
    assert caiu.value.status_code == 401


def test_senha_temporaria_VENCIDA_responde_o_MESMO_que_senha_errada(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dizer "sua senha temporaria venceu" confirma que ela existiu -- e, para quem varre nomes,
    que a conta e' real. O visitante ve' o mesmo 401 de sempre."""
    from motor_expansao.db import eventos as db_eventos

    monkeypatch.setattr(db_eventos, "registrar_login_recusado", lambda **_kw: None)

    _preparar(monkeypatch, credencial=_credencial(expira_em=_daqui(-1)), confere=True)
    with pytest.raises(pilot.HTTPException) as vencida:
        pilot.login(pilot.LoginIn(login="vinicius", senha="a-temporaria"), _req())

    _preparar(monkeypatch, credencial=_credencial(), confere=False)
    with pytest.raises(pilot.HTTPException) as errada:
        pilot.login(pilot.LoginIn(login="vinicius", senha="qualquer"), _req())

    assert vencida.value.status_code == errada.value.status_code
    assert vencida.value.detail == errada.value.detail


def test_senha_temporaria_DENTRO_do_prazo_entra(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A outra metade: o prazo nao pode barrar quem esta' dentro dele."""
    _preparar(monkeypatch, credencial=_credencial(expira_em=_daqui(30)), confere=True)
    resposta = pilot.login(pilot.LoginIn(login="vinicius", senha="a-temporaria"), _req())
    assert resposta.status_code == 200


def test_senha_SEM_prazo_segue_entrando(ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """`expira_em = None` e' o estado de toda senha que a pessoa escolheu -- a maioria dos
    logins. Uma comparacao malfeita com `None` transformaria isto em 401 para todo mundo."""
    _preparar(monkeypatch, credencial=_credencial(expira_em=None), confere=True)
    assert pilot.login(pilot.LoginIn(login="vinicius", senha="a-minha"), _req()).status_code == 200


def test_o_prazo_e_conferido_DEPOIS_do_argon2(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O oposto da trava de tentativas, e de proposito.

    A trava nega ANTES do Argon2 para poupar CPU numa rajada. O prazo e' estado RARO: conferi-lo
    antes faria a resposta voltar mais rapido para quem digitou a temporaria certa depois do
    vencimento -- e essa diferenca de tempo denuncia que a senha existiu.
    """
    verificacoes: list[Any] = []
    _preparar(
        monkeypatch,
        credencial=_credencial(expira_em=_daqui(-1)),
        confere=True,
        verificacoes=verificacoes,
    )
    with pytest.raises(pilot.HTTPException):
        pilot.login(pilot.LoginIn(login="vinicius", senha="a-temporaria"), _req())
    assert verificacoes == ["$argon2id$real"], "a senha vencida nao pagou o Argon2"


def test_a_trava_recebe_o_piso_da_REDEFINICAO(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O caso tipico do pedido de ajuda: errou cinco vezes e SO' ENTAO ligou para o admin.

    Sem repassar este piso, a pessoa recebe a senha nova e continua barrada por ate' 15 minutos,
    lendo a mesma mensagem de senha errada -- sem nada que ligue uma coisa a outra.
    """
    from motor_expansao.db import eventos as db_eventos

    vistos: list[dict[str, Any]] = []
    marco = _daqui(-3)
    # O espiao entra DEPOIS do `_preparar`, que tambem instala um dublê desta funcao. Na ordem
    # inversa o dublê dele apagaria a captura e `vistos` ficaria vazio -- foi o que aconteceu na
    # primeira tentativa, e e' a segunda vez nesta suite que a ordem morde.
    _preparar(monkeypatch, credencial=_credencial(redefinida_em=marco), confere=True)
    monkeypatch.setattr(
        db_eventos, "contar_recusas_recentes", lambda **kw: (vistos.append(kw), 0)[1]
    )
    pilot.login(pilot.LoginIn(login="vinicius", senha="a-temporaria"), _req())

    assert vistos and vistos[0]["redefinida_em"] == marco


# --------------------------------------------------------------------------------------
# De onde a sessao veio (020) — e por que o IP nao e' forjavel
# --------------------------------------------------------------------------------------


def _capturar_origem(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    vistos: list[dict[str, Any]] = []
    monkeypatch.setattr(
        db_sessoes,
        "abrir",
        lambda **kw: (vistos.append(kw), db_sessoes.SessaoAberta("tok", 42, None))[1],
    )
    return vistos


def test_a_sessao_guarda_o_ip_e_o_agente(ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """A pergunta do `BLK-SEC-03-FU2`: esta sessao e' da pessoa ou de quem roubou o cookie?"""
    _preparar(monkeypatch, credencial=_credencial(), confere=True)
    vistos = _capturar_origem(monkeypatch)

    pilot.login(
        pilot.LoginIn(login="vinicius", senha="certa"),
        _req(xff="198.51.100.7", agente="Mozilla/5.0 (Teste)", peer="10.0.0.1"),
    )
    assert vistos[0]["ip"] == "198.51.100.7"
    assert vistos[0]["user_agent"] == "Mozilla/5.0 (Teste)"


def test_o_IP_GRAVADO_NAO_E_FORJAVEL(ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """A garantia que sustenta a coluna inteira.

    O Caddy ANEXA o peer real ao FIM do `X-Forwarded-For`; tudo a' esquerda vem do cliente.
    Usar o PRIMEIRO token foi vulnerabilidade real no motor -- pentest de 19/08/2026, em que
    `X-Forwarded-For: 8.8.8.8` fazia a acao constar de um IP arbitrario na aba Acessos.
    Se a sessao gravasse `[0]`, a coluna nova nasceria com a mesma falha JA' CORRIGIDA em
    outro lugar do mesmo arquivo -- que e' a forma mais cara de repetir um erro.
    """
    _preparar(monkeypatch, credencial=_credencial(), confere=True)
    vistos = _capturar_origem(monkeypatch)

    pilot.login(
        pilot.LoginIn(login="vinicius", senha="certa"),
        # O cliente MENTE no primeiro token; o Caddy anexa o verdadeiro no fim.
        _req(xff="8.8.8.8, 203.0.113.50", peer="10.0.0.1"),
    )
    assert vistos[0]["ip"] == "203.0.113.50", "gravou o token FORJADO pelo cliente"
    assert vistos[0]["ip"] != "8.8.8.8"


def test_sem_proxy_na_frente_cai_no_peer_TCP(ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Alcancar o backend SEM passar pelo Caddy nao pode virar IP inventado.

    Sem `X-Forwarded-For`, o unico valor confiavel e' o peer da conexao, que nao e' forjavel.
    """
    _preparar(monkeypatch, credencial=_credencial(), confere=True)
    vistos = _capturar_origem(monkeypatch)

    pilot.login(pilot.LoginIn(login="vinicius", senha="certa"), _req(peer="10.0.0.1"))
    assert vistos[0]["ip"] == "10.0.0.1"


def test_origem_ausente_nao_derruba_o_login(ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sessao sem origem conhecida e' estado legitimo. Trocar o principal (entrar) pelo
    acessorio (saber de onde) seria inversao de prioridade."""
    _preparar(monkeypatch, credencial=_credencial(), confere=True)
    vistos = _capturar_origem(monkeypatch)

    resposta = pilot.login(pilot.LoginIn(login="vinicius", senha="certa"), _req())
    assert resposta.status_code == 200
    assert vistos[0]["ip"] is None
    assert vistos[0]["user_agent"] is None


# ---------------------------------------------------------------------------
# BLK-BANCO-12: o /api/login bem-sucedido nao consta como "desconhecido" na trilha (DEC-027)
# ---------------------------------------------------------------------------


class _Headers:
    """So' o `.get` que o middleware usa."""

    def __init__(self, d: dict[str, str]) -> None:
        self._d = d

    def get(self, chave: str, default: Any = None) -> Any:
        return self._d.get(chave, default)


def _req_trilha(caminho: str, *, state: Any, headers: dict[str, str] | None = None) -> Any:
    return SimpleNamespace(
        url=SimpleNamespace(path=caminho, query=""),
        headers=_Headers(headers or {}),
        client=SimpleNamespace(host="203.0.113.7"),
        state=state,
        method="POST",
    )


def test_trilha_do_login_bem_sucedido_registra_o_login_nao_desconhecido(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O handler de login carimba `request.state.login_na_trilha` no sucesso; o middleware a usa.

    Sem isto, o POST /api/login (pre-autenticacao, sem Remote-User) caia no `or "desconhecido"`
    do montar_evento, e a trilha da DEC-027 nunca dizia QUEM entrou.
    """
    capturados: list[dict[str, Any]] = []
    monkeypatch.setattr(pilot.acesso_log, "registrar", lambda ev: capturados.append(ev))
    st = SimpleNamespace(login_na_trilha="ana.ribeiro")
    pilot._registrar_acesso(_req_trilha("/api/login", state=st), status=200, inicio=0.0, tamanho=None)
    assert len(capturados) == 1
    assert capturados[0]["usuario"] == "ana.ribeiro"


def test_trilha_do_login_le_o_carimbo_do_state_apos_o_call_next(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ponte no middleware REAL `_trilha_acesso`: o que o endpoint carimba em `request.state`
    DURANTE o `call_next` tem de ser lido DEPOIS dele. Os testes vizinhos chamam
    `_registrar_acesso` com o state ja' pronto; este exercita o middleware INTEIRO e trava a
    ORDEM -- se alguem ler o state ANTES do `call_next`, ou passar outro request a
    `_registrar_acesso`, a trilha volta a "desconhecido" no login em silencio (familia
    DEC-038/045/054). `login_da_requisicao` vira header cru de proposito: ponte quebrada cai
    em "desconhecido", nao na identidade de dev, que mascararia a regressao.

    Sem `TestClient`/`httpx`/`FastAPI`: o `starlette.testclient` exige `httpx2`, ausente no CI,
    e importa-lo no topo quebrava a COLETA do arquivo inteiro. Chamar o middleware como coroutine
    exercita o mesmo caminho (`call_next` -> `_registrar_acesso`) sem subir um servidor ASGI.
    """
    import asyncio

    capturados: list[dict[str, Any]] = []
    monkeypatch.setattr(pilot.acesso_log, "registrar", lambda ev: capturados.append(ev))
    monkeypatch.setattr(pilot.acesso, "login_da_requisicao", lambda h: h)

    req = _req_trilha("/api/login", state=SimpleNamespace())

    async def _endpoint_que_carimba(_r: Any) -> Any:
        # o endpoint de login real faz exatamente isto, so' no sucesso, no MESMO request:
        req.state.login_na_trilha = "ana.ribeiro"
        return SimpleNamespace(status_code=200, headers=_Headers({}))

    asyncio.run(pilot._trilha_acesso(req, _endpoint_que_carimba))

    assert len(capturados) == 1
    assert capturados[0]["usuario"] == "ana.ribeiro"


def test_trilha_login_recusado_segue_desconhecido(monkeypatch: pytest.MonkeyPatch) -> None:
    """Recusa/inexistente NAO carimba `login_na_trilha` (o raise vem antes) e sem Remote-User
    a trilha grava "desconhecido" -- o certo: o visitante nao e' uma identidade confirmada."""
    capturados: list[dict[str, Any]] = []
    monkeypatch.setattr(pilot.acesso_log, "registrar", lambda ev: capturados.append(ev))
    monkeypatch.setattr(pilot.acesso, "login_da_requisicao", lambda _u: None)
    pilot._registrar_acesso(
        _req_trilha("/api/login", state=SimpleNamespace()), status=401, inicio=0.0, tamanho=None
    )
    assert len(capturados) == 1
    assert capturados[0]["usuario"] == "desconhecido"


def test_trilha_requisicao_normal_usa_o_remote_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """Requisicao gateada (com Remote-User) e' INTOCADA: sem `login_na_trilha`, usa o header."""
    capturados: list[dict[str, Any]] = []
    monkeypatch.setattr(pilot.acesso_log, "registrar", lambda ev: capturados.append(ev))
    monkeypatch.setattr(pilot.acesso, "login_da_requisicao", lambda u: u)
    pilot._registrar_acesso(
        _req_trilha("/api/acessos/usuarios", state=SimpleNamespace(), headers={"remote-user": "vinicius"}),
        status=200,
        inicio=0.0,
        tamanho=None,
    )
    assert len(capturados) == 1
    assert capturados[0]["usuario"] == "vinicius"


# --------------------------------------------------------------------------------------
# BLK-BANCO-07: semaforo do Argon2id -- uma rajada de logins nao esgota memoria/threadpool
# --------------------------------------------------------------------------------------
# Medido: cada verificacao custa 64 MiB; ~32 concorrentes estouram o `mem_limit` de 2 GiB do
# web (OOM) e saturam o threadpool. O semaforo NAO-BLOQUEANTE recusa o excedente com 503 SEM
# pagar o Argon2, e libera o slot nos dois caminhos (sucesso e recusa).


def _todos_os_slots_do_login_livres() -> bool:
    """True se os LOGIN_MAX_CONCORRENTES slots do semaforo estao livres (nada vazou)."""
    pegos = [pilot._SEM_LOGIN.acquire(blocking=False) for _ in range(pilot.LOGIN_MAX_CONCORRENTES)]
    for p in pegos:
        if p:
            pilot._SEM_LOGIN.release()
    return all(pegos)


def test_login_sob_carga_recusa_503_sem_rodar_o_argon2(
    ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Semaforo CHEIO: o login recusa com 503 de IMEDIATO, sem pagar a verificacao de 64 MiB --
    e' o que impede a rajada de esgotar memoria e threadpool. A senha esta' CERTA de proposito:
    sem o semaforo este login ENTRARIA, entao o 503 so' pode vir da protecao de carga."""
    verificacoes: list[Any] = []
    _preparar(monkeypatch, credencial=_credencial(), confere=True, verificacoes=verificacoes)
    pegos = [pilot._SEM_LOGIN.acquire(blocking=False) for _ in range(pilot.LOGIN_MAX_CONCORRENTES)]
    try:
        assert all(pegos), "nao esgotou o semaforo no setup do teste"
        with pytest.raises(pilot.HTTPException) as caiu:
            pilot.login(pilot.LoginIn(login="vinicius", senha="a-senha-certa"), _req())
        assert caiu.value.status_code == 503
        assert verificacoes == [], "o Argon2 rodou mesmo com o semaforo cheio"
    finally:
        for p in pegos:
            if p:
                pilot._SEM_LOGIN.release()


def test_login_bem_sucedido_libera_o_slot(ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """O slot volta apos o login (sucesso): nao vaza capacidade a cada entrada."""
    _preparar(monkeypatch, credencial=_credencial(), confere=True)
    resposta = pilot.login(pilot.LoginIn(login="vinicius", senha="a-senha-certa"), _req())
    assert resposta.status_code == 200
    assert _todos_os_slots_do_login_livres(), "o semaforo nao foi liberado apos o sucesso"


def test_login_recusado_tambem_libera_o_slot(ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Senha errada tambem solta o slot (o `finally` cobre os dois caminhos) -- senao uma rajada
    de senhas erradas drenaria o semaforo e travaria os logins legitimos seguintes."""
    _preparar(monkeypatch, credencial=_credencial(), confere=False)
    with pytest.raises(pilot.HTTPException) as caiu:
        pilot.login(pilot.LoginIn(login="vinicius", senha="errada"), _req())
    assert caiu.value.status_code == 401
    assert _todos_os_slots_do_login_livres(), "o semaforo nao foi liberado apos a recusa"
