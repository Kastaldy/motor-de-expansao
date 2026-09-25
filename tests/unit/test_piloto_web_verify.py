"""`GET /api/verify` — o `forward_auth` do D4 (DEC-067), que substitui o do Authelia.

A garantia central deste arquivo NAO e' o 200: e' que a rota so' aceita o COOKIE. Ela e'
publica por construcao (a borda pergunta a ela antes de existir identidade), e uma rota
publica que aceitasse identidade do cliente seria a porta dos fundos que a trava 1 da
DEC-067 existe para impedir -- `curl -H 'Remote-User: felipe' /api/verify` devolveria 200
com o Felipe dentro, e o Caddy copiaria isso para o backend como veredito da borda.

Ha' uma armadilha MEDIDA que os testes fixam: `_portao_de_sessao` chama
`_sem_headers_de_identidade` ANTES de qualquer decisao, inclusive para rota publica, entao
quando a rota roda os headers de identidade ja' sumiram. Uma versao que lesse header
nasceria quebrada (leria sempre vazio) e insegura (voltaria a confiar no cliente no dia em
que a limpeza mudasse). Por isso ha' teste de COMPORTAMENTO e teste de CODIGO (AST): o de
comportamento passaria mesmo numa implementacao que lesse header, porque o portao o apaga.

Segue o padrao da suite do piloto (`test_piloto_web_acesso.py`): funcoes chamadas DIRETO,
sem TestClient/httpx.
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import acesso  # noqa: E402
import app as pilot  # noqa: E402

from motor_expansao.db import rbac  # noqa: E402
from motor_expansao.db import sessoes as db_sessoes  # noqa: E402
from motor_expansao.db.rbac import Identidade  # noqa: E402

_TEMPLATE_CADDY = _REPO / "deploy" / "caddy" / "piloto-ar.Caddyfile.template"


class _Url:
    def __init__(self, caminho: str) -> None:
        self.path = caminho


class _Requisicao:
    """Fake com o que a rota e o portao usam: `.url.path`, `.cookies`, `.scope["headers"]`."""

    def __init__(
        self,
        caminho: str = "/api/verify",
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

    @property
    def headers(self) -> dict[str, str]:
        """So' existe para PROVAR que a rota nao a usa: qualquer leitura daqui explode.

        Um dict vazio silencioso deixaria uma implementacao que le' header passar verde.
        """
        raise AssertionError(
            "/api/verify leu os headers da requisicao — identidade do CLIENTE (trava 1)"
        )


#: Sentinela para distinguir "não passou nada" de "passou `None`" — e `None` é justamente o
#: valor que interessa nos testes de negação (sessão inexistente).
_SENTINELA = object()


def _sessao(login: str = "vinicius", perfil: str = "growth", id_sessao: int = 42) -> Any:
    return db_sessoes.SessaoValida(
        identidade=Identidade(
            id_usuario=7, login=login, perfil=perfil, permissoes=frozenset()
        ),
        id_sessao=id_sessao,
        ultimo_acesso=None,
    )


class _ValidarEspiao:
    """Dublê de `db_sessoes.validar` que GUARDA o token recebido.

    Existe por um defeito REAL, medido em 25/09/2026: a primeira versão deste arquivo usava
    `lambda _t: _sessao(...)` em todos os dublês -- o token era DESCARTADO. Com isso os 24
    testes passavam mesmo trocando o corpo da rota por um token cravado que não vinha de
    cookie nenhum (sabotagem executada; 24 passed nas três variantes tentadas, inclusive a
    que ignora o `__Host-` em produção -- que significaria "ninguém autentica e o Caddy nega
    o piloto inteiro").

    Nesta casa a suíte verde é o portão de merge (DEC-016), então um teste que não pode ficar
    vermelho não é cobertura: é a aparência dela na frente da rota que guarda a borda.
    Capturar o token é o que amarra o COOKIE ao veredito -- sem isso, nada no arquivo liga
    uma ponta à outra.
    """

    def __init__(self, devolve: Any = _SENTINELA) -> None:
        self._devolve = _sessao() if devolve is _SENTINELA else devolve
        self.tokens: list[str] = []

    def __call__(self, token: str) -> Any:
        self.tokens.append(token)
        return self._devolve

    @property
    def token(self) -> str:
        """O ÚNICO token visto. Levanta se a rota não chamou, ou chamou mais de uma vez."""
        assert len(self.tokens) == 1, f"esperava 1 chamada a validar, houve {len(self.tokens)}"
        return self.tokens[0]


def _espiar(monkeypatch: pytest.MonkeyPatch, devolve: Any = _SENTINELA) -> _ValidarEspiao:
    espiao = _ValidarEspiao(devolve)
    monkeypatch.setattr(db_sessoes, "validar", espiao)
    return espiao


@pytest.fixture
def _ligado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, "1")


@pytest.fixture(autouse=True)
def _tocar_proibido(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, int]]:
    """Registra qualquer toque. A rota NAO deve tocar — ver o teste de inatividade."""
    chamadas: list[dict[str, int]] = []
    monkeypatch.setattr(db_sessoes, "tocar", lambda **kw: (chamadas.append(kw), True)[1])
    return chamadas


# --------------------------------------------------------------------------------------
# 1. O caminho feliz: 200 com os tres headers do contrato
# --------------------------------------------------------------------------------------


def test_sessao_valida_devolve_200_com_os_tres_headers(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O contrato do D4: 200 + `Remote-User`/`Remote-Groups`/`Remote-Email`.

    Os tres EXISTEM sempre, inclusive o vazio: `copy_headers` do Caddy so' sobrescreve o
    que a resposta trouxe, entao header ausente aqui chega ao backend como o CLIENTE
    mandou.
    """
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: _sessao(login="juancalu"))

    resposta = pilot.verify(_Requisicao(cookies={acesso.COOKIE_SESSAO_DEV: "t"}))

    assert resposta.status_code == 200
    for nome in pilot.CABECALHOS_DE_VERIFICACAO:
        assert nome in resposta.headers, f"{nome} faltando na resposta de verificacao"
    assert resposta.headers["Remote-User"] == "juancalu"


def test_o_Remote_Groups_carrega_o_PERFIL_do_rbac_e_nao_as_permissoes(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Grupo e' o que o Authelia servia (`expansao_br`), e o equivalente honesto aqui e' o
    perfil. Publicar as PERMISSOES num header seria uma segunda redacao de
    `REGRAS_POR_CAPACIDADE` num lugar onde ninguem a aplica."""
    monkeypatch.setattr(
        db_sessoes, "validar", lambda _t: _sessao(login="ana", perfil="consultoria")
    )

    resposta = pilot.verify(_Requisicao(cookies={acesso.COOKIE_SESSAO_DEV: "t"}))

    assert resposta.headers["Remote-Groups"] == "consultoria"


def test_o_Remote_Email_sai_vazio_mas_PRESENTE(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Vazio e' decisao (os dois leitores de `remote-email` sao fallback de `remote-user`, e
    o portao apaga o header de toda requisicao). PRESENTE tambem e': omiti-lo faria
    `copy_headers Remote-Email` virar no-op e deixaria passar o valor do cliente."""
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: _sessao())

    resposta = pilot.verify(_Requisicao(cookies={acesso.COOKIE_SESSAO_DEV: "t"}))

    assert resposta.headers["Remote-Email"] == ""


def test_o_cookie_com_prefixo___Host__tambem_e_aceito(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Producao usa `__Host-`; dev usa o nome simples, porque o prefixo nao vale em http.
    A rota aceita os dois, como o portao — uma so' delas aceitando trancaria um dos dois
    ambientes.

    O `espiao.token` e' o que da' DENTE a este teste: sem ele, uma rota que ignorasse o
    `__Host-` e inventasse um token passaria verde -- e em producao isso significa que
    NINGUEM autentica e o Caddy nega o piloto inteiro.
    """
    espiao = _espiar(monkeypatch)
    resposta = pilot.verify(_Requisicao(cookies={acesso.COOKIE_SESSAO: "valor-do-host"}))

    assert resposta.status_code == 200
    assert espiao.token == "valor-do-host", "a rota nao validou o token do cookie __Host-"


def test_o_token_VALIDADO_e_exatamente_o_do_cookie_de_dev(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A outra metade do amarrado, para o nome sem prefixo."""
    espiao = _espiar(monkeypatch)
    pilot.verify(_Requisicao(cookies={acesso.COOKIE_SESSAO_DEV: "valor-de-dev"}))

    assert espiao.token == "valor-de-dev"


def test_cookie_de_OUTRO_nome_nao_vira_token(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fecha a sabotagem que passou: a rota nao pode INVENTAR token nem pescar de qualquer
    cookie. Com um cookie de nome alheio, o que chega a `validar` tem de ser a string vazia
    -- e o veredito, 401."""
    espiao = _espiar(monkeypatch, devolve=None)
    resposta = pilot.verify(_Requisicao(cookies={"sessao_de_outro_app": "nao-me-use"}))

    assert espiao.token == "", f"a rota pescou um token de onde nao devia: {espiao.token!r}"
    assert resposta.status_code == 401


def test_o_veredito_nunca_e_cacheavel(_ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """O corpo e' vazio, mas os HEADERS sao a identidade de uma pessoa: reusar esta resposta
    e' servir a sessao de alguem para outra pessoa."""
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: _sessao())
    concedido = pilot.verify(_Requisicao(cookies={acesso.COOKIE_SESSAO_DEV: "t"}))
    assert concedido.headers["Cache-Control"] == "no-store"

    # A negacao tambem: um 401 cacheado manteria a pessoa fora depois de ela entrar de novo.
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: None)
    negado = pilot.verify(_Requisicao())
    assert negado.headers["Cache-Control"] == "no-store"


def test_login_acentuado_degrada_em_vez_de_derrubar_a_autenticacao(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`login_usuario` vem do banco e nao tem restricao de charset. Header e' latin-1, e uma
    excecao de codificacao aqui vira 500 que o Caddy repassa como NEGACAO — ou seja, um
    login fora de latin-1 trancaria o dono dele para fora do piloto."""
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: _sessao(login="joão✓"))

    resposta = pilot.verify(_Requisicao(cookies={acesso.COOKIE_SESSAO_DEV: "t"}))

    assert resposta.status_code == 200
    assert resposta.headers["Remote-User"] == "joão"


# --------------------------------------------------------------------------------------
# 2. Quem NAO passa
# --------------------------------------------------------------------------------------


def test_sem_cookie_devolve_401(_ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: None)

    resposta = pilot.verify(_Requisicao())

    assert resposta.status_code == 401
    assert "Remote-User" not in resposta.headers, "negacao vazando identidade"


def test_cookie_invalido_devolve_401(_ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Revogada, vencida por teto e vencida por inatividade caem no mesmo `None` do
    `validar` (decisao do modulo de sessao) e portanto no mesmo 401 — distinguir contaria
    ao visitante qual foi."""
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: None)

    resposta = pilot.verify(_Requisicao(cookies={acesso.COOKIE_SESSAO_DEV: "token-que-nao-vale"}))

    assert resposta.status_code == 401


def test_com_a_autenticacao_propria_DESLIGADA_a_rota_nao_existe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """404, e e' fail-CLOSED: o Caddy nega tudo que nao for 2xx, entao apontar o
    `forward_auth` para ca' antes de ligar a env derruba o piloto — que e' o desfecho SEGURO.
    Responder 200 evitaria a queda e deixaria o piloto PUBLICO enquanto ninguem percebesse."""
    monkeypatch.delenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, raising=False)
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: pytest.fail("validou desligado"))

    with pytest.raises(HTTPException) as erro:
        pilot.verify(_Requisicao(cookies={acesso.COOKIE_SESSAO_DEV: "t"}))

    assert erro.value.status_code == 404


def test_o_404_de_desligado_nao_depende_do_throttle_do_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O aviso sai uma vez por processo; a NEGACAO sai toda vez.

    Amarrar as duas faria a segunda chamada em diante responder outra coisa -- e qualquer
    2xx aqui e' o piloto inteiro publico, porque o Caddy so' exige 2xx para liberar.
    """
    monkeypatch.delenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, raising=False)
    monkeypatch.setattr(pilot, "_verify_desligado_logado", False)

    for _ in range(3):
        with pytest.raises(HTTPException) as erro:
            pilot.verify(_Requisicao())
        assert erro.value.status_code == 404


def test_banco_fora_do_ar_vira_503_e_nao_401(_ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """401 AFIRMARIA "sua sessao expirou", o que e' falso: as sessoes estao intactas, so' nao
    da' para le'-las. E a SPA trata 401 como queda de sessao (`relatarAcessoNegado`), entao
    uma piscada de banco viraria logout em massa, mandando a rede para uma tela de login que
    tambem depende do banco. E' a MESMA resposta que o `_portao_de_sessao` ja' da'."""
    monkeypatch.setattr(
        db_sessoes, "validar", lambda _t: (_ for _ in ()).throw(RuntimeError("banco fora"))
    )

    resposta = pilot.verify(_Requisicao(cookies={acesso.COOKIE_SESSAO_DEV: "t"}))

    assert resposta.status_code == 503
    assert "Remote-User" not in resposta.headers


# --------------------------------------------------------------------------------------
# 3. Trava 1 da DEC-067: identidade do CLIENTE nunca entra
# --------------------------------------------------------------------------------------


def test_a_rota_NAO_confia_em_Remote_User_mandado_pelo_cliente(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`curl -H 'Remote-User: felipe'` sem cookie tem de levar 401, nao 200 com o Felipe.

    O fake LEVANTA se alguem ler `request.headers`, entao este teste falha de duas formas
    diferentes conforme o defeito: 200 se a rota acreditasse no header, `AssertionError` se
    ela apenas o lesse.
    """
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: None)

    resposta = pilot.verify(_Requisicao(headers={"Remote-User": "felipe"}))

    assert resposta.status_code == 401


def test_com_cookie_valido_o_header_forjado_nao_muda_a_resposta(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Escalonamento, nao personificacao do zero: quem TEM sessao manda o header de outra
    pessoa junto. O veredito sai do banco, e so' dele."""
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: _sessao(login="vinicius"))

    resposta = pilot.verify(
        _Requisicao(cookies={acesso.COOKIE_SESSAO_DEV: "t"}, headers={"Remote-User": "felipe"})
    )

    assert resposta.headers["Remote-User"] == "vinicius"


def test_o_CODIGO_da_rota_nao_le_header_nenhum() -> None:
    """A prova de comportamento acima NAO basta, e este e' o ponto do arquivo.

    `_portao_de_sessao` apaga `remote-user`/`remote-email` de TODA requisicao antes de
    qualquer decisao, inclusive para rota publica. Logo, uma implementacao que lesse header
    passaria nos testes de comportamento em producao (leria vazio) e so' quebraria no dia em
    que a limpeza mudasse — que e' o pior momento possivel para descobrir. Aqui o teste le' o
    CODIGO.
    """
    arvore = ast.parse(textwrap.dedent(inspect.getsource(pilot.verify)))
    atributos = {no.attr for no in ast.walk(arvore) if isinstance(no, ast.Attribute)}

    assert "headers" not in atributos, "/api/verify le' headers da requisicao (trava 1)"
    assert "cookies" in atributos, "/api/verify deixou de ler o cookie — o que ela valida?"

    fonte = inspect.getsource(pilot.verify)
    corpo = fonte.split('"""', 2)[-1]  # fora do docstring, que CITA os headers de proposito
    assert "Remote-User" in corpo, "a rota parou de emitir Remote-User"


# --------------------------------------------------------------------------------------
# 4. Trava 2 da DEC-067: a identidade de DESENVOLVIMENTO nao entra por aqui
# --------------------------------------------------------------------------------------


def test_a_rota_nunca_cai_na_identidade_de_desenvolvimento(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com as DUAS travas de `rbac._dev_ativo` deliberadamente ABERTAS, ainda e' 401.

    `login_efetivo` existe para quem roda o backend na propria maquina, SEM Caddy; esta rota
    so' e' chamada PORQUE ha' um Caddy na frente. Um fallback aqui faria de um deploy com
    `MOTOR_CADASTRO_DIR` ausente um piloto inteiro autenticado como a env de dev.
    """
    monkeypatch.setenv(rbac.ENV_DEV_USUARIO, "felipe")
    monkeypatch.setenv(rbac.ENV_DEV_IDENTIDADE, "1")  # override: dev ligado, custe o que custar
    monkeypatch.delenv(rbac.ENV_SINAL_PRODUCAO, raising=False)
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: None)
    assert rbac.login_efetivo(None) == "felipe", "o cenario nao reproduz o modo de dev"

    resposta = pilot.verify(_Requisicao())

    assert resposta.status_code == 401
    assert "Remote-User" not in resposta.headers


def test_o_CODIGO_da_rota_nao_chama_a_resolucao_de_identidade_de_dev() -> None:
    """Trava contra a refatoracao bem-intencionada: "unificar com `login_da_requisicao`"
    parece limpeza e e' a abertura da porta dos fundos, porque aquela funcao cai no
    `MOTOR_DEV_USUARIO`."""
    fonte = inspect.getsource(pilot.verify)
    arvore = ast.parse(textwrap.dedent(fonte))
    chamadas = {
        no.func.attr
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
    }

    for proibida in ("login_efetivo", "login_da_requisicao", "identidade"):
        assert proibida not in chamadas, f"/api/verify resolve identidade por {proibida}"


# --------------------------------------------------------------------------------------
# 5. Inatividade: a rota NAO toca
# --------------------------------------------------------------------------------------


def test_a_rota_NAO_toca_a_inatividade_da_sessao(
    _ligado: None, monkeypatch: pytest.MonkeyPatch, _tocar_proibido: list[dict[str, int]]
) -> None:
    """O `forward_auth` roda a cada requisicao protegida, e a MESMA requisicao passa segundos
    depois pelo `_portao_de_sessao`, que ja' valida e ja' toca. Tocar aqui dobraria a
    transacao de ESCRITA num pool de 4 conexoes sem mover o relogio de 30 min um segundo --
    os dois carimbos seriam o mesmo `now()`."""
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: _sessao())

    pilot.verify(_Requisicao(cookies={acesso.COOKIE_SESSAO_DEV: "t"}))

    assert _tocar_proibido == [], "a rota de verificacao escreveu no banco a cada requisicao"


# --------------------------------------------------------------------------------------
# 6. A rota esta' declarada publica — e o portao a deixa passar
# --------------------------------------------------------------------------------------


def test_a_rota_esta_declarada_publica_sem_sessao() -> None:
    """Sem esta declaracao o portao a 401 ANTES de ela rodar, e a borda leria esse 401 como
    "ninguem esta' autenticado" para TODA requisicao do piloto."""
    assert "/api/verify" in acesso.ROTAS_PUBLICAS_SEM_SESSAO
    assert acesso.rota_publica_sem_sessao("/api/verify")


def test_a_rota_esta_declarada_livre_nos_dois_portoes_de_autorizacao() -> None:
    """`ROTAS_LIVRES` e' o que `test_toda_rota_do_app_tem_regra_ou_e_livre_declarada` e o
    gate de PAIS exigem. Um gate de aba aqui transformaria "esta pessoa nao ve a Executiva"
    em "a borda nao autentica ninguem"."""
    assert "/api/verify" in acesso.ROTAS_LIVRES
    assert acesso.abas_necessarias("/api/verify") is None
    assert acesso.superficie_necessaria("/api/verify") is None


def test_a_rota_esta_registrada_no_app() -> None:
    caminhos = {getattr(r, "path", "") for r in pilot.app.routes}
    assert "/api/verify" in caminhos


def test_o_portao_deixa_a_rota_passar_sem_sessao(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prova de ponta a ponta da declaracao acima: o middleware REAL, com o portao ligado e
    sem cookie nenhum, entrega `/api/verify` ao `call_next` em vez de 401."""
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: pytest.fail("o portao validou"))
    chegou: list[Any] = []

    async def _proximo(req: Any) -> Any:
        chegou.append(req)
        return type("R", (), {"status_code": 200, "headers": {}})()

    req = _Requisicao(caminho="/api/verify", headers={"Remote-User": "felipe"})
    asyncio.run(pilot._portao_de_sessao(req, _proximo))

    assert len(chegou) == 1, "o portao barrou a rota que responde por ele"
    assert req.scope["headers"] == [], "o Remote-User do cliente sobreviveu ate' a rota"


# --------------------------------------------------------------------------------------
# 7. A borda: o template do Caddy e o backend nao podem andar separados
# --------------------------------------------------------------------------------------


def _linha_do_template(prefixo: str) -> str:
    texto = _TEMPLATE_CADDY.read_text(encoding="utf-8")
    linhas = [ln.strip() for ln in texto.splitlines() if ln.strip().startswith(prefixo)]
    assert len(linhas) == 1, f"esperava UMA linha `{prefixo}` no template, achei {len(linhas)}"
    return linhas[0]


def test_o_template_do_caddy_aponta_para_a_NOSSA_rota() -> None:
    """O caminho e' o mesmo do Authelia DE PROPOSITO (a borda nao aprende rota nova); o que
    muda e' o alvo do `forward_auth`."""
    texto = _TEMPLATE_CADDY.read_text(encoding="utf-8")
    assert "forward_auth authelia:9091" not in texto, "o template ainda pergunta ao Authelia"
    assert _linha_do_template("uri ") == "uri /api/verify"
    assert "forward_auth @protegido motor_expansao_web_ar:8899 {" in texto


def test_as_excecoes_do_matcher_sao_as_MESMAS_rotas_publicas_do_backend() -> None:
    """Duas redacoes da mesma regra desencontram em SILENCIO (licao da DEC-044).

    Se `ROTAS_PUBLICAS_SEM_SESSAO` ganhar um caminho e o matcher do Caddy nao, a borda
    mandara' ao `forward_auth` uma rota que o backend considera publica -- e ela levara' 401
    antes de chegar. Se acontecer o contrario, a borda abre um buraco que o backend fecha
    sozinho (menos grave, e ainda assim divergencia).
    """
    declaradas = set(_linha_do_template("not path ").removeprefix("not path ").split())
    assert declaradas == set(acesso.ROTAS_PUBLICAS_SEM_SESSAO), (
        "o `not path` do Caddyfile e `ROTAS_PUBLICAS_SEM_SESSAO` divergiram: "
        f"{sorted(declaradas ^ set(acesso.ROTAS_PUBLICAS_SEM_SESSAO))}"
    )


def test_o_copy_headers_lista_exatamente_o_que_a_rota_emite(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`copy_headers` so' SOBRESCREVE o que a resposta de autenticacao trouxe: nome listado
    la' que a rota nao emite chega ao backend como o CLIENTE mandou — o oposto do que a
    diretiva parece prometer. Foi por isso que `Remote-Name` saiu dos dois lados."""
    declarados = tuple(_linha_do_template("copy_headers ").removeprefix("copy_headers ").split())
    assert declarados == pilot.CABECALHOS_DE_VERIFICACAO

    monkeypatch.setattr(db_sessoes, "validar", lambda _t: _sessao())
    resposta = pilot.verify(_Requisicao(cookies={acesso.COOKIE_SESSAO_DEV: "t"}))
    for nome in declarados:
        assert nome in resposta.headers, f"o Caddy copia {nome}, mas a rota nao o emite"
