"""Portao de SESSAO do piloto (epic do P19, decisao 1 = D30) — middleware invocado DIRETO.

A garantia mais importante deste arquivo nao e' o 401: e' a LIMPEZA DOS HEADERS DE
IDENTIDADE. Depois do corte do P19 nao ha' mais Caddy fazendo `forward_auth`, logo
`Remote-User` deixa de ser um header que SO' a borda sabe injetar e passa a ser um header
que QUALQUER cliente pode mandar. Sem a limpeza, `curl -H 'Remote-User: felipe'` seria
personificacao completa -- os 19 leitores de `app.py` acreditariam, o RBAC resolveria as
permissoes do Felipe, e a trilha da DEC-027 registraria a acao no nome dele.

E sao DOIS headers, nao um: `_registrar_acesso` faz `remote-user or remote-email`, e o
`_autor` da rota de cadastro tambem aceita o e-mail. Fechar so' o primeiro seria porta
fechada com janela aberta. A primeira versao deste portao filtrava com um GERADOR dentro da
comprehension -- que se esgota no primeiro item e faria o filtro parar de filtrar em
silencio, exatamente aqui. Os dois testes de limpeza existem para que isso nao volte.

ORDEM MEDIDA (`user_middleware` e' de fora para dentro):
    trilha -> portao de sessao -> controle de aba -> rota
E' a unica ordem que entrega as duas propriedades juntas: o 401 e' barrado ANTES do controle
de aba e ainda assim cai DENTRO da trilha, virando linha de auditoria.
"""

from __future__ import annotations

import asyncio
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


class _Url:
    def __init__(self, caminho: str) -> None:
        self.path = caminho


class _Requisicao:
    """Fake com o que o PORTAO usa: `.url.path`, `.cookies` e `.scope["headers"]`.

    Mais rico que o `_Requisicao` de `test_acesso_log.py` de proposito -- aquele nao tem
    `scope` nem `cookies`, porque a trilha nao precisa deles.
    """

    def __init__(
        self,
        caminho: str = "/api/uf/SP",
        cookies: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.url = _Url(caminho)
        self.cookies = cookies or {}
        self.scope: dict[str, Any] = {
            "headers": [
                (chave.lower().encode("latin-1"), valor.encode("latin-1"))
                for chave, valor in (headers or {}).items()
            ]
        }

    def headers_do_scope(self) -> list[tuple[str, str]]:
        """A LISTA CRUA, nunca um dict.

        Um dict colapsa chave duplicada, e foi assim que a primeira versao deste arquivo
        produziu um falso-verde grave: o portao ACRESCENTA a identidade da sessao ao fim da
        lista, entao, com o `Remote-User` forjado ainda presente no inicio, o dict devolvia o
        valor da sessao e o teste passava -- INCLUSIVE com a limpeza de headers removida por
        completo (provado por sabotagem). E em producao o efeito seria o oposto do que o
        teste sugeria: o `Headers.get()` do Starlette devolve a PRIMEIRA ocorrencia, logo o
        forjado venceria. A lista crua e' a unica forma de ver a sobrevivencia.
        """
        return [(n.decode("latin-1"), v.decode("latin-1")) for n, v in self.scope["headers"]]

    def valores_de(self, nome: str) -> list[str]:
        """TODOS os valores daquele header, na ordem. E' aqui que a duplicata aparece."""
        return [v for n, v in self.headers_do_scope() if n == nome.lower()]


class _Resposta:
    status_code = 200
    headers: dict[str, str] = {}


def _rodar(requisicao: _Requisicao) -> tuple[Any, list[_Requisicao]]:
    """Invoca o portao. Devolve (resposta, [requisicoes que chegaram ao `call_next`])."""
    chegou: list[_Requisicao] = []

    async def _proximo(req: _Requisicao) -> _Resposta:
        chegou.append(req)
        return _Resposta()

    resposta = asyncio.run(pilot._portao_de_sessao(requisicao, _proximo))
    return resposta, chegou


def _sessao(login: str = "vinicius", id_usuario: int = 7, id_sessao: int = 42) -> Any:
    return db_sessoes.SessaoValida(
        identidade=Identidade(
            id_usuario=id_usuario, login=login, perfil="growth", permissoes=frozenset()
        ),
        id_sessao=id_sessao,
        ultimo_acesso=None,
    )


@pytest.fixture
def _ligado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, "1")


@pytest.fixture(autouse=True)
def _sem_toque(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, int]]:
    """`tocar` nunca vai ao banco nos testes; registra as chamadas para conferencia."""
    chamadas: list[dict[str, int]] = []
    monkeypatch.setattr(
        db_sessoes,
        "tocar",
        lambda **kw: (chamadas.append(kw), True)[1],
    )
    return chamadas


# --------------------------------------------------------------------------------------
# 1. Dormente — a propriedade que permite esta branch existir
# --------------------------------------------------------------------------------------


def test_desligado_o_portao_nao_toca_em_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem `MOTOR_AUTENTICACAO_PROPRIA`, o Authelia manda e o portao e' transparente.

    Inclui NAO limpar o `Remote-User`: enquanto o Caddy injeta o header atras do Authelia,
    ele e' confiavel e e' a identidade de producao. Limpa-lo aqui derrubaria o login de
    todos no primeiro deploy desta branch.
    """
    monkeypatch.delenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, raising=False)
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: pytest.fail("validou desligado"))

    req = _Requisicao(headers={"Remote-User": "felipe"})
    resposta, chegou = _rodar(req)

    assert resposta.status_code == 200
    assert len(chegou) == 1
    assert req.headers_do_scope() == [("remote-user", "felipe")]


# --------------------------------------------------------------------------------------
# 2. A limpeza dos headers de identidade (a garantia central)
# --------------------------------------------------------------------------------------


def test_com_o_portao_ligado_o_Remote_User_do_CLIENTE_e_descartado(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Personificacao pelo header: sem esta limpeza, `curl -H 'Remote-User: felipe'` bastava."""
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: _sessao(login="vinicius"))

    req = _Requisicao(cookies={acesso.COOKIE_SESSAO_DEV: "t"}, headers={"Remote-User": "felipe"})
    _resposta, chegou = _rodar(req)

    assert len(chegou) == 1
    # A asserção é sobre a LISTA: "felipe" não pode SOBREVIVER em lugar nenhum dela. Olhar
    # um dict aqui deixava este teste passar até com a limpeza removida (ver
    # `headers_do_scope`), porque a injeção da sessão vem depois e o dict só guarda a última.
    assert req.valores_de("remote-user") == ["vinicius"], (
        f"o header do CLIENTE sobreviveu — personificacao: {req.headers_do_scope()}"
    )
    assert "felipe" not in [v for _n, v in req.headers_do_scope()]


def test_o_Remote_Email_TAMBEM_e_descartado(_ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """O SEGUNDO header, e e' por ele que o defeito do gerador passaria.

    `_registrar_acesso` faz `remote-user or remote-email`, e o `_autor` da rota de cadastro
    aceita o e-mail. Filtrar so' o primeiro deixaria um `Remote-Email` forjado virar o autor
    registrado na auditoria.
    """
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: _sessao())

    req = _Requisicao(
        cookies={acesso.COOKIE_SESSAO_DEV: "t"},
        headers={"Remote-User": "felipe", "Remote-Email": "felipe@ultra.com"},
    )
    _rodar(req)

    assert req.valores_de("remote-email") == [], "o e-mail forjado sobreviveu"
    assert "felipe@ultra.com" not in [v for _n, v in req.headers_do_scope()]


def test_a_limpeza_vale_ATE_nas_rotas_publicas(_ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """A limpeza vem ANTES da decisao de rota publica, e e' deliberado: a propria tentativa
    de login nao deve carregar identidade sugerida pelo cliente para a trilha."""
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: pytest.fail("rota publica validou"))

    req = _Requisicao(caminho="/api/login", headers={"Remote-User": "felipe"})
    _resposta, chegou = _rodar(req)

    assert len(chegou) == 1, "rota publica deveria passar sem sessao"
    assert req.headers_do_scope() == [], "o header do cliente sobreviveu numa rota publica"


def test_os_headers_inocentes_sobrevivem(_ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """A limpeza e' CIRURGICA: `Remote-Name`/`Remote-Groups` tem zero leitores (medido), e
    apagar `user-agent` ou `x-forwarded-for` cegaria a trilha da DEC-027."""
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: _sessao())

    req = _Requisicao(
        cookies={acesso.COOKIE_SESSAO_DEV: "t"},
        headers={"Remote-User": "felipe", "User-Agent": "curl/8", "X-Forwarded-For": "8.8.8.8"},
    )
    _rodar(req)

    assert req.valores_de("user-agent") == ["curl/8"]
    assert req.valores_de("x-forwarded-for") == ["8.8.8.8"]
    assert req.valores_de("remote-user") == ["vinicius"], "o forjado sobreviveu"


# --------------------------------------------------------------------------------------
# 3. Quem passa sem sessao, e quem nao passa
# --------------------------------------------------------------------------------------


def test_sem_cookie_a_rota_protegida_devolve_401_e_nao_403(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """401, e a diferenca importa para a SPA: `relatarAcessoNegado()` de `lib/sessao.ts` ja'
    trata 401 como queda de sessao SEM precisar da sonda. 403 cairia na mensagem de
    permissao, que manda a pessoa pedir acesso em vez de entrar de novo."""
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: None)

    resposta, chegou = _rodar(_Requisicao(caminho="/api/uf/SP"))

    assert resposta.status_code == 401
    assert chegou == [], "a requisicao sem sessao chegou a' rota"


@pytest.mark.parametrize("caminho", ["/api/login", "/api/logout", "/api/health"])
def test_as_tres_rotas_publicas_atendem_sem_sessao(
    _ligado: None, monkeypatch: pytest.MonkeyPatch, caminho: str
) -> None:
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: pytest.fail(f"{caminho} validou"))
    _resposta, chegou = _rodar(_Requisicao(caminho=caminho))
    assert len(chegou) == 1


@pytest.mark.parametrize("caminho", ["/", "/index.html", "/assets/app-abc123.js"])
def test_os_estaticos_da_SPA_atendem_sem_sessao(
    _ligado: None, monkeypatch: pytest.MonkeyPatch, caminho: str
) -> None:
    """A SPA e a tela de login moram no MESMO processo e host. Sem isto, o portao negaria o
    HTML que contem o formulario e o unico estado alcancavel seria 401 em tela branca."""
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: pytest.fail("estatico validou"))
    _resposta, chegou = _rodar(_Requisicao(caminho=caminho))
    assert len(chegou) == 1


def test_o_api_me_passa_a_EXIGIR_sessao(_ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Decisao explicita do escopo (§3): `/api/me` e' a PRIMEIRA chamada da SPA e hoje e'
    livre; depois do corte e' ela que responde "quem sou eu" DEPOIS do login."""
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: None)
    resposta, chegou = _rodar(_Requisicao(caminho="/api/me"))
    assert resposta.status_code == 401
    assert chegou == []
    assert "/api/me" not in acesso.ROTAS_PUBLICAS_SEM_SESSAO


# --------------------------------------------------------------------------------------
# 4. Sessao valida: injecao, toque e falha de banco
# --------------------------------------------------------------------------------------


def test_com_sessao_valida_a_identidade_da_SESSAO_e_injetada(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E' o que mantem os 19 leitores do header funcionando sem uma linha de mudanca."""
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: _sessao(login="juancalu"))

    req = _Requisicao(cookies={acesso.COOKIE_SESSAO_DEV: "t"})
    resposta, chegou = _rodar(req)

    assert resposta.status_code == 200
    assert len(chegou) == 1
    assert req.valores_de("remote-user") == ["juancalu"]


def test_o_cookie_com_prefixo___Host__tambem_e_aceito(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Producao usa `__Host-`, que o navegador so' aceita com `Secure`+`Path=/`+sem `Domain`.
    Dev usa o nome simples, porque o prefixo nao vale em http."""
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: _sessao())
    _resposta, chegou = _rodar(_Requisicao(cookies={acesso.COOKIE_SESSAO: "t"}))
    assert len(chegou) == 1


def test_a_inatividade_e_batida_com_os_ids_da_sessao(
    _ligado: None, monkeypatch: pytest.MonkeyPatch, _sem_toque: list[dict[str, int]]
) -> None:
    """A trava de 5 min (decisao 2) vive no `WHERE` do UPDATE, nao aqui -- o portao so'
    chama. O que este teste fixa e' que ele chama com os ids CERTOS."""
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: _sessao(id_usuario=7, id_sessao=42))
    _rodar(_Requisicao(cookies={acesso.COOKIE_SESSAO_DEV: "t"}))
    assert _sem_toque == [{"id_sessao": 42, "id_usuario": 7}]


def test_falha_no_toque_nao_derruba_a_requisicao(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bater o relogio e' rastro, nao transacao: a pessoa nao perde o que pediu por causa
    dele. Mesmo principio do `_registrar_acesso` da DEC-027."""
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: _sessao())
    monkeypatch.setattr(db_sessoes, "tocar", lambda **_kw: (_ for _ in ()).throw(RuntimeError("x")))

    resposta, chegou = _rodar(_Requisicao(cookies={acesso.COOKIE_SESSAO_DEV: "t"}))
    assert resposta.status_code == 200
    assert len(chegou) == 1


def test_banco_fora_do_ar_vira_503_e_nao_500_nem_passagem(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """503 porque e' incidente de infraestrutura, e a mensagem diz para tentar de novo.

    E NAO passagem: um `except` que deixasse seguir transformaria queda de banco em
    "entrada liberada para todos", que e' o pior desfecho possivel deste middleware.
    """
    monkeypatch.setattr(
        db_sessoes, "validar", lambda _t: (_ for _ in ()).throw(RuntimeError("banco fora"))
    )

    resposta, chegou = _rodar(_Requisicao(caminho="/api/uf/SP"))
    assert resposta.status_code == 503
    assert chegou == [], "queda de banco liberou a rota protegida"


# --------------------------------------------------------------------------------------
# 5. O portao esta' registrado, e na posicao certa
# --------------------------------------------------------------------------------------


def test_o_portao_esta_registrado_no_app() -> None:
    """Sem isto, remover o decorator deixaria a suite verde com o portao morto em producao
    -- todos os testes acima chamam a funcao direto. Falso-verde que o
    `test_acesso_log.py` ja' documentou nesta base."""
    dispatches = [getattr(m, "kwargs", {}).get("dispatch") for m in pilot.app.user_middleware]
    assert pilot._portao_de_sessao in dispatches


def test_a_ordem_dos_middlewares_e_a_medida() -> None:
    """`user_middleware` e' de FORA para DENTRO. A ordem tem de ser
    trilha -> portao -> controle de aba, e nenhuma outra:

      * portao DENTRO da trilha  -> o 401 de sessao vira linha de auditoria;
      * portao FORA do controle  -> nao se pergunta "que aba?" a quem nao esta' logado.

    Trocar a ordem de declaracao no arquivo inverte isto em silencio, porque o decorator
    empilha por fora e nada no codigo declara a intencao.
    """
    nomes = [
        getattr(getattr(m, "kwargs", {}).get("dispatch"), "__name__", "")
        for m in pilot.app.user_middleware
    ]
    nomes = [n for n in nomes if n]
    assert nomes == ["_trilha_acesso", "_portao_de_sessao", "_controle_de_acesso_por_aba"], nomes
