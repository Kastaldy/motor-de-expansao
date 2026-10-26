"""Contrato das rotas de administração de usuários (D25).

O módulo de dados (`test_db_usuarios.py`) guarda a trilha: que o evento sai, na mesma
transação, com as duas pessoas nos lugares certos. Aqui o que se guarda é o **portão** e a
**tradução de erro** — as duas coisas que só existem na camada de rota:

  * o gate duplo. Estas rotas vivem sob `/api/acessos/`, então passam pela allowlist de env
    do painel (404 que não anuncia existência) E pela capacidade do banco. Se a allowlist
    parar de valer aqui, o painel inteiro perde a defesa que a emenda da DEC-027 lhe deu.
  * quem está na allowlist mas não tem linha em `usuarios` não pode escrever: sem
    `id_usuario` não há autor para carimbar, e escrita sem autor é exatamente o que o D19
    existe para impedir. Isso é 409, não 500 opaco.

Chama as funções de rota DIRETO (sem TestClient), no padrão de `test_piloto_web_api.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot_app  # noqa: E402

from motor_expansao.db import sessoes as db_sessoes  # noqa: E402
from motor_expansao.db import usuarios as db_usuarios  # noqa: E402

ADMIN = "vinicius"


class _Eu:
    id_usuario = 7


@pytest.fixture(autouse=True)
def _sou_admin(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Allowlist do painel liberada — cada teste que quiser o contrário desfaz."""
    monkeypatch.setattr(pilot_app.acesso, "pode_ver_acessos", lambda _u: True)
    yield


@pytest.fixture(autouse=True)
def _login_proprio_desligado_por_padrao(monkeypatch: pytest.MonkeyPatch) -> Any:
    """O estado de PRODUCAO ate' o corte do P19 -- e o default de todos os testes daqui.

    Sem isto, um `MOTOR_AUTENTICACAO_PROPRIA` exportado na maquina de quem roda a suite mudaria
    o resultado de metade dela. Quem precisa da chave LIGADA pede a fixture `login_proprio`.
    """
    monkeypatch.delenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, raising=False)
    yield


@pytest.fixture
def login_proprio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Liga a chave: os tres gestos de senha so' existem com ela (decisao do dono, 24/10/2026)."""
    monkeypatch.setenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, "1")


def _identidade(monkeypatch: pytest.MonkeyPatch, eu: Any) -> None:
    monkeypatch.setattr(pilot_app, "_identidade_do_admin", lambda _u: eu)


# --------------------------------------------------------------------------------------
# O portão
# --------------------------------------------------------------------------------------


def test_fora_da_allowlist_a_rota_nao_existe(monkeypatch: pytest.MonkeyPatch) -> None:
    """404, e não 403: o painel não anuncia a própria existência (emenda da DEC-027)."""
    monkeypatch.setattr(pilot_app.acesso, "pode_ver_acessos", lambda _u: False)
    with pytest.raises(HTTPException) as caiu:
        pilot_app.acessos_usuarios_listar(remote_user="qualquer")
    assert caiu.value.status_code == 404

    with pytest.raises(HTTPException) as caiu2:
        pilot_app.acessos_usuarios_alterar(
            9, pilot_app.UsuarioAdminIn(perfil="growth"), remote_user="qualquer"
        )
    assert caiu2.value.status_code == 404


def test_o_gate_e_checado_antes_de_tocar_o_banco(monkeypatch: pytest.MonkeyPatch) -> None:
    """Negado não consulta nada — senão a rota vaza estado do banco pelo tempo de resposta."""
    monkeypatch.setattr(pilot_app.acesso, "pode_ver_acessos", lambda _u: False)

    def _explode() -> None:
        raise AssertionError("o banco foi consultado antes do gate")

    monkeypatch.setattr(db_usuarios, "listar", _explode)
    with pytest.raises(HTTPException):
        pilot_app.acessos_usuarios_listar(remote_user="qualquer")


# --------------------------------------------------------------------------------------
# Leitura
# --------------------------------------------------------------------------------------


def test_listagem_devolve_usuarios_perfis_e_quem_sou_eu(monkeypatch: pytest.MonkeyPatch) -> None:
    _identidade(monkeypatch, _Eu())
    monkeypatch.setattr(
        db_usuarios,
        "listar",
        lambda: [
            db_usuarios.UsuarioAdmin(7, "vinicius", "Vinícius", "v@u.com", "growth", True),
            db_usuarios.UsuarioAdmin(9, "saiu", "Saiu", "s@u.com", "expansao", False),
        ],
    )
    monkeypatch.setattr(
        db_usuarios, "perfis", lambda: [{"perfil": "growth", "descricao": "…", "capacidades": 15}]
    )
    saida = pilot_app.acessos_usuarios_listar(remote_user=ADMIN)

    assert saida["eu"] == 7
    assert [u["login"] for u in saida["usuarios"]] == ["vinicius", "saiu"]
    # O inativo vem junto: escondê-lo tornaria a reativação impossível pela tela.
    assert saida["usuarios"][1]["ativo"] is False
    assert saida["perfis"][0]["capacidades"] == 15


@pytest.mark.parametrize(("valor", "esperado"), [(None, False), ("1", True), ("", False)])
def test_a_listagem_diz_se_o_login_proprio_esta_ligado(
    monkeypatch: pytest.MonkeyPatch, valor: str | None, esperado: bool
) -> None:
    """A tela esconde "Redefinir senha" e "Exigir troca" e escolhe os recados por este campo.

    Um booleano DE VERDADE nos dois estados, e nao "ausente quando desligado": a tela trata a
    ausencia como desligado (o conservador), mas o backend deste repo sempre diz qual e' -- e a
    leitura e' a mesma de `sessoes.ligada`, sem segunda redacao da regra da env.
    """
    if valor is None:
        monkeypatch.delenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, raising=False)
    else:
        monkeypatch.setenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, valor)
    _identidade(monkeypatch, _Eu())
    monkeypatch.setattr(db_usuarios, "listar", lambda: [])
    monkeypatch.setattr(db_usuarios, "perfis", lambda: [])

    saida = pilot_app.acessos_usuarios_listar(remote_user=ADMIN)
    assert saida["login_proprio"] is esperado
    assert saida["login_proprio"] is db_sessoes.ligada()


# --------------------------------------------------------------------------------------
# Escrita
# --------------------------------------------------------------------------------------


def test_corpo_vazio_e_422_e_nao_uma_escrita_a_toa(monkeypatch: pytest.MonkeyPatch) -> None:
    _identidade(monkeypatch, _Eu())
    with pytest.raises(HTTPException) as caiu:
        pilot_app.acessos_usuarios_alterar(9, pilot_app.UsuarioAdminIn(), remote_user=ADMIN)
    assert caiu.value.status_code == 422


def test_perfil_e_status_juntos_vao_numa_unidade_de_trabalho_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uma chamada, uma transacao (#463, follow-up B).

    Ate' 24/10/2026 a rota fazia DUAS chamadas -- `alterar_perfil` e `definir_ativo`, cada uma
    com a sua transacao --, e a falha da segunda deixava a primeira gravada sob um 503 que nao
    dizia isso. Os dois EVENTOS continuam separados ("virou Growth" e "foi desativado"
    respondem a perguntas diferentes na auditoria) -- isso e' guardado em `test_db_usuarios.py`.
    Aqui se guarda que a rota entrega os dois campos JUNTOS a uma unica unidade de trabalho.
    """
    _identidade(monkeypatch, _Eu())
    chamadas: list[dict[str, Any]] = []

    def _alterar_acesso(
        i: int, *, autor: int, perfil: Any = None, ativo: Any = None
    ) -> dict[str, Any]:
        chamadas.append({"alvo": i, "autor": autor, "perfil": perfil, "ativo": ativo})
        return {"id_usuario": i, "perfil": {"mudou": True}, "status": {"mudou": True}}

    def _proibido(*_a: Any, **_k: Any) -> None:
        raise AssertionError("a rota voltou a abrir uma transacao por campo")

    monkeypatch.setattr(db_usuarios, "alterar_acesso", _alterar_acesso)
    monkeypatch.setattr(db_usuarios, "alterar_perfil", _proibido)
    monkeypatch.setattr(db_usuarios, "definir_ativo", _proibido)
    saida = pilot_app.acessos_usuarios_alterar(
        9, pilot_app.UsuarioAdminIn(perfil="growth", ativo=False), remote_user=ADMIN
    )
    assert chamadas == [{"alvo": 9, "autor": 7, "perfil": "growth", "ativo": False}]
    assert "perfil" in saida and "status" in saida


@pytest.mark.parametrize(
    ("corpo", "esperado"),
    [({"perfil": "growth"}, ("growth", None)), ({"ativo": True}, (None, True))],
)
def test_um_campo_so_tambem_passa_pela_mesma_unidade_de_trabalho(
    monkeypatch: pytest.MonkeyPatch, corpo: dict[str, Any], esperado: tuple[Any, Any]
) -> None:
    """Um caminho so' na rota: o campo que nao veio chega como `None`, e nao como "nao mexer"
    inventado na rota -- quem decide o que aplicar e' `alterar_acesso`."""
    _identidade(monkeypatch, _Eu())
    vistos: list[tuple[Any, Any]] = []
    monkeypatch.setattr(
        db_usuarios,
        "alterar_acesso",
        lambda i, *, autor, perfil=None, ativo=None: vistos.append((perfil, ativo))
        or {"id_usuario": i},
    )
    pilot_app.acessos_usuarios_alterar(9, pilot_app.UsuarioAdminIn(**corpo), remote_user=ADMIN)
    assert vistos == [esperado]


@pytest.mark.parametrize(
    ("erro", "status"),
    [
        (db_usuarios.UsuarioDesconhecido("não existe"), 404),
        (db_usuarios.PerfilDesconhecido("perfil inventado"), 422),
        (db_usuarios.AlvoEhOAutor("você não"), 403),
    ],
)
def test_cada_recusa_do_dominio_tem_seu_status(
    monkeypatch: pytest.MonkeyPatch, erro: Exception, status: int
) -> None:
    _identidade(monkeypatch, _Eu())

    def _falha(*_a: Any, **_k: Any) -> None:
        raise erro

    monkeypatch.setattr(db_usuarios, "alterar_acesso", _falha)
    with pytest.raises(HTTPException) as caiu:
        pilot_app.acessos_usuarios_alterar(
            9, pilot_app.UsuarioAdminIn(perfil="x"), remote_user=ADMIN
        )
    assert caiu.value.status_code == status


def test_banco_fora_do_ar_e_503(monkeypatch: pytest.MonkeyPatch) -> None:
    from motor_expansao.db import BancoIndisponivel

    _identidade(monkeypatch, _Eu())

    def _falha(*_a: Any, **_k: Any) -> None:
        raise BancoIndisponivel("sem rota para o host")

    monkeypatch.setattr(db_usuarios, "alterar_acesso", _falha)
    with pytest.raises(HTTPException) as caiu:
        pilot_app.acessos_usuarios_alterar(
            9, pilot_app.UsuarioAdminIn(perfil="x"), remote_user=ADMIN
        )
    assert caiu.value.status_code == 503


def test_deploy_sem_banco_e_503_e_nao_500(monkeypatch: pytest.MonkeyPatch) -> None:
    """IRMAO do teste acima, e a diferenca entre os dois e' a razao deste ramo existir.

    `BancoIndisponivel` e `BancoNaoConfigurado` sao irmaos -- nenhum herda do outro --, entao o
    ramo do primeiro NAO pegava o segundo: a excecao chegava ao `raise erro` do fim de
    `_erro_de_usuarios` e virava 500 CRU. E deploy sem banco nao e' caso de borda: e' o estado
    PADRAO do compose (`MOTOR_DATABASE_URL: ${MOTOR_DATABASE_URL:-}`), entao o card
    "Administracao de usuarios" mostrava um 500 em toda instalacao que ainda nao ligou o banco.
    """
    from motor_expansao.db import BancoNaoConfigurado

    _identidade(monkeypatch, _Eu())

    def _falha(*_a: Any, **_k: Any) -> None:
        raise BancoNaoConfigurado("sem MOTOR_DATABASE_URL")

    monkeypatch.setattr(db_usuarios, "alterar_acesso", _falha)
    with pytest.raises(HTTPException) as caiu:
        pilot_app.acessos_usuarios_alterar(
            9, pilot_app.UsuarioAdminIn(perfil="x"), remote_user=ADMIN
        )
    assert caiu.value.status_code == 503
    # A MENSAGEM tambem, e nao so' o status: o 503 sozinho nao diz ao operador o que fazer, e a
    # tela so' tem o que mostrar se o texto disser qual e' a falta.
    assert "banco" in str(caiu.value.detail).lower()


# --------------------------------------------------------------------------------------
# O autor
# --------------------------------------------------------------------------------------


def test_na_allowlist_mas_sem_cadastro_no_banco_nao_escreve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Os dois cadastros divergiram. Sem `id_usuario` não há autor, e escrita sem autor é
    exatamente o que o D19 existe para impedir — 409, não um 500 opaco."""
    from motor_expansao.db import rbac

    monkeypatch.setattr(rbac, "identidade", lambda _u: None)
    with pytest.raises(HTTPException) as caiu:
        pilot_app.acessos_usuarios_alterar(
            9, pilot_app.UsuarioAdminIn(perfil="growth"), remote_user=ADMIN
        )
    assert caiu.value.status_code == 409


def test_banco_fora_do_ar_na_identidade_e_503(monkeypatch: pytest.MonkeyPatch) -> None:
    from motor_expansao.db import BancoIndisponivel, rbac

    def _falha(_u: Any) -> None:
        raise BancoIndisponivel("pool fechado")

    monkeypatch.setattr(rbac, "identidade", _falha)
    with pytest.raises(HTTPException) as caiu:
        pilot_app.acessos_usuarios_listar(remote_user=ADMIN)
    assert caiu.value.status_code == 503


# --------------------------------------------------------------------------------------
# Criação (D26)
# --------------------------------------------------------------------------------------


def _corpo_novo(**troca: Any) -> Any:
    campos: dict[str, Any] = {
        "login": "ana",
        "nome": "Ana Ribeiro",
        "email": "ana@ultraacademia.com.br",
        "perfil": "expansao",
    }
    campos.update(troca)
    return pilot_app.UsuarioNovoIn(**campos)


def test_fora_da_allowlist_a_criacao_nao_existe(monkeypatch: pytest.MonkeyPatch) -> None:
    """404, e não 403 — a rota de criação segue a mesma regra das outras duas."""
    monkeypatch.setattr(pilot_app.acesso, "pode_ver_acessos", lambda _u: False)
    with pytest.raises(HTTPException) as caiu:
        pilot_app.acessos_usuarios_criar(_corpo_novo(), remote_user="qualquer")
    assert caiu.value.status_code == 404


def test_o_gate_da_criacao_e_checado_antes_de_tocar_o_banco(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negado não cria, não consulta e não hasheia — o Argon2 custa 64 MB por chamada."""
    monkeypatch.setattr(pilot_app.acesso, "pode_ver_acessos", lambda _u: False)

    def _explode(**_k: Any) -> None:
        raise AssertionError("o banco foi tocado antes do gate")

    monkeypatch.setattr(db_usuarios, "criar", _explode)
    with pytest.raises(HTTPException) as caiu:
        pilot_app.acessos_usuarios_criar(_corpo_novo(), remote_user="qualquer")
    assert caiu.value.status_code == 404


def test_a_criacao_passa_o_autor_e_devolve_o_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """O autor vem da identidade de quem pediu, nunca do corpo da requisição."""
    _identidade(monkeypatch, _Eu())
    visto: dict[str, Any] = {}

    def _criar(**kwargs: Any) -> dict[str, Any]:
        visto.update(kwargs)
        return {
            "id_usuario": 42,
            "login": "ana",
            "perfil": "expansao",
            "falta_cadastrar_no_authelia": True,
        }

    monkeypatch.setattr(db_usuarios, "criar", _criar)
    saida = pilot_app.acessos_usuarios_criar(_corpo_novo(), remote_user=ADMIN)

    assert visto["autor"] == 7
    assert visto["login"] == "ana"
    assert saida["id_usuario"] == 42
    assert saida["falta_cadastrar_no_authelia"] is True


@pytest.mark.parametrize("ligada", [False, True])
def test_a_criacao_diz_a_chave_e_o_authelia_segue_pendente_nos_dois_estados(
    monkeypatch: pytest.MonkeyPatch, ligada: bool
) -> None:
    """O recado depois de criar depende da chave, e a resposta tem de dizer qual e'.

    `falta_cadastrar_no_authelia` fica `True` nos DOIS estados, por razoes diferentes:
    desligada, sem a entrada no `users_database.yml` a pessoa nao entra; ligada, durante a
    janela de observacao do corte, a entrada no Authelia e' o que mantem o rollback possivel.
    O que muda e' o recado -- e quem o escolhe e' `login_proprio`.
    """
    if ligada:
        monkeypatch.setenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, "1")
    _identidade(monkeypatch, _Eu())
    monkeypatch.setattr(
        db_usuarios,
        "criar",
        lambda **_k: {
            "id_usuario": 42,
            "login": "ana",
            "perfil": "expansao",
            "falta_cadastrar_no_authelia": True,
        },
    )
    saida = pilot_app.acessos_usuarios_criar(_corpo_novo(), remote_user=ADMIN)
    assert saida["login_proprio"] is ligada
    assert saida["falta_cadastrar_no_authelia"] is True
    assert saida["id_usuario"] == 42


def test_o_corpo_da_criacao_nao_aceita_senha() -> None:
    """Sem campo de senha, de propósito: o admin não deve conhecer a senha de outra pessoa.

    Se um campo `senha` aparecer aqui, qualquer ação daquela conta fica contestável — o oposto
    do que o D17 existe para sustentar. Pydantic ignora extra por padrão, então o que se guarda
    é que o modelo NÃO declara o campo.
    """
    assert "senha" not in pilot_app.UsuarioNovoIn.model_fields
    assert set(pilot_app.UsuarioNovoIn.model_fields) == {"login", "nome", "email", "perfil"}


@pytest.mark.parametrize("faltando", ["login", "nome", "email", "perfil"])
def test_criacao_com_campo_faltando_nao_monta(faltando: str) -> None:
    """Os quatro são obrigatórios — ao contrário dos dois de alteração, opcionais de propósito."""
    from pydantic import ValidationError

    campos = {"login": "ana", "nome": "Ana", "email": "a@u.com", "perfil": "expansao"}
    del campos[faltando]
    with pytest.raises(ValidationError):
        pilot_app.UsuarioNovoIn(**campos)


@pytest.mark.parametrize(
    ("erro", "status"),
    [
        ("PerfilDesconhecido", 422),
        ("LoginEmUso", 409),
        ("EmailEmUso", 409),
    ],
)
def test_cada_recusa_da_criacao_tem_seu_status(
    monkeypatch: pytest.MonkeyPatch, erro: str, status: int
) -> None:
    """409 para conflito de estado, 422 para corpo que o banco não aceita. Nunca 500."""
    _identidade(monkeypatch, _Eu())
    classe = getattr(db_usuarios, erro)

    def _criar(**_k: Any) -> None:
        raise classe("não")

    monkeypatch.setattr(db_usuarios, "criar", _criar)
    with pytest.raises(HTTPException) as caiu:
        pilot_app.acessos_usuarios_criar(_corpo_novo(), remote_user=ADMIN)
    assert caiu.value.status_code == status


def test_senha_inicial_nao_configurada_e_503_e_nao_500(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falta de configuração do deploy, no molde do banco indisponível.

    A mensagem tem de dizer o que o OPERADOR precisa fazer — quem está na tela não tem como
    consertar o `.env`.
    """
    from motor_expansao.db import senhas

    _identidade(monkeypatch, _Eu())

    def _criar(**_k: Any) -> None:
        raise senhas.SenhaInicialNaoConfigurada("MOTOR_SENHA_INICIAL não está definida.")

    monkeypatch.setattr(db_usuarios, "criar", _criar)
    with pytest.raises(HTTPException) as caiu:
        pilot_app.acessos_usuarios_criar(_corpo_novo(), remote_user=ADMIN)
    assert caiu.value.status_code == 503
    assert "MOTOR_SENHA_INICIAL" in str(caiu.value.detail)


def test_extra_auth_ausente_e_503(monkeypatch: pytest.MonkeyPatch) -> None:
    """`argon2-cffi` faltando é 503, como driver de banco faltando — não é erro de quem clicou."""
    from motor_expansao.db import senhas

    _identidade(monkeypatch, _Eu())

    def _criar(**_k: Any) -> None:
        raise senhas.HashIndisponivel("argon2-cffi nao esta instalado")

    monkeypatch.setattr(db_usuarios, "criar", _criar)
    with pytest.raises(HTTPException) as caiu:
        pilot_app.acessos_usuarios_criar(_corpo_novo(), remote_user=ADMIN)
    assert caiu.value.status_code == 503


# --------------------------------------------------------------------------------------
# Senha própria (D26)
# --------------------------------------------------------------------------------------


@pytest.mark.usefixtures("login_proprio")
def test_trocar_a_propria_senha_nao_exige_a_allowlist_do_painel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trocar a própria senha não é ato de administração, e não pode depender da allowlist.

    Se dependesse, só quem administra o painel poderia definir senha — e a preparação do P19
    exigiria promover todo mundo a Growth para depois rebaixar.
    """
    monkeypatch.setattr(pilot_app.acesso, "pode_ver_acessos", lambda _u: False)
    monkeypatch.setattr(pilot_app, "_minha_identidade", lambda _u: _Eu())
    monkeypatch.setattr(
        db_usuarios, "trocar_a_propria_senha", lambda **_k: {"id_usuario": 7, "primeira_vez": True}
    )
    saida = pilot_app.me_trocar_senha(
        pilot_app.MinhaSenhaIn(senha_atual="a-inicial", nova_senha="uma frase bem longa"),
        remote_user="qualquer",
    )
    assert saida["primeira_vez"] is True


@pytest.mark.usefixtures("login_proprio")
def test_a_rota_de_senha_nao_aceita_alvo(monkeypatch: pytest.MonkeyPatch) -> None:
    """O alvo não é parâmetro em lugar nenhum do caminho — nem no path, nem no corpo.

    É o que torna a ausência de gate inofensiva: não existe forma de chamar isto para outra
    pessoa, nem passando id, nem passando login.
    """
    assert set(pilot_app.MinhaSenhaIn.model_fields) == {"senha_atual", "nova_senha"}

    visto: dict[str, Any] = {}
    monkeypatch.setattr(pilot_app, "_minha_identidade", lambda _u: _Eu())
    monkeypatch.setattr(
        db_usuarios,
        "trocar_a_propria_senha",
        lambda **k: visto.update(k) or {"id_usuario": 7, "primeira_vez": False},
    )
    pilot_app.me_trocar_senha(
        pilot_app.MinhaSenhaIn(senha_atual="x", nova_senha="uma frase bem longa"),
        remote_user=ADMIN,
    )
    assert set(visto) == {"autor", "senha_atual", "nova_senha"}
    assert visto["autor"] == 7


def test_a_rota_de_senha_esta_fora_do_prefixo_de_acessos() -> None:
    """Sob `/api/acessos/` ela levaria 404 seco de quem não administra o painel.

    E o mapa de capacidade não tem regra para `/api/me`, então a rota é livre para quem tem
    identidade — exatamente o público certo.
    """
    from motor_expansao.db import rbac  # noqa: F401  (garante que o pacote carrega)

    caminhos = [r.path for r in pilot_app.app.routes if getattr(r, "path", "").endswith("/senha")]
    assert "/api/me/senha" in caminhos
    assert not any(c.startswith("/api/acessos/") for c in caminhos)
    assert pilot_app.acesso.capacidade_necessaria("/api/me/senha", "PATCH") is None
    # `bloqueio_acessos` devolve falsy para "não bloqueado". O lado do bloqueio tem cobertura
    # própria em `test_fora_da_allowlist_a_rota_nao_existe` — aqui a fixture autouse já liberou
    # a allowlist, então afirmar o contrário neste teste brigaria com ela.
    assert not pilot_app.acesso.bloqueio_acessos("/api/me/senha", "ninguem")


@pytest.mark.parametrize(
    ("erro", "status"),
    [("SenhaAtualIncorreta", 403), ("UsuarioDesconhecido", 404)],
)
@pytest.mark.usefixtures("login_proprio")
def test_cada_recusa_da_troca_tem_seu_status(
    monkeypatch: pytest.MonkeyPatch, erro: str, status: int
) -> None:
    monkeypatch.setattr(pilot_app, "_minha_identidade", lambda _u: _Eu())
    classe = getattr(db_usuarios, erro)

    def _trocar(**_k: Any) -> None:
        raise classe("não")

    monkeypatch.setattr(db_usuarios, "trocar_a_propria_senha", _trocar)
    with pytest.raises(HTTPException) as caiu:
        pilot_app.me_trocar_senha(
            pilot_app.MinhaSenhaIn(senha_atual="x", nova_senha="uma frase bem longa"),
            remote_user=ADMIN,
        )
    assert caiu.value.status_code == status


@pytest.mark.usefixtures("login_proprio")
def test_senha_fraca_e_422(monkeypatch: pytest.MonkeyPatch) -> None:
    """A mensagem da política vai para a tela — ela é escrita para a pessoa, não para o log."""
    from motor_expansao.db import senhas

    monkeypatch.setattr(pilot_app, "_minha_identidade", lambda _u: _Eu())

    # A mensagem sai da POLITICA DE VERDADE, e nao de um literal: ate' 25/09/2026 este dublê
    # dizia "pelo menos 12 caracteres" cravado. O dono baixou o piso para 8 e este teste
    # continuou VERDE ensinando o numero errado -- dublê que inventa a propria mensagem nao
    # mede nada e ainda vira documentacao falsa do que a pessoa vai ler.
    piso = senhas.MINIMO_DE_CARACTERES
    curta = "a" * (piso - 1)
    with pytest.raises(senhas.SenhaFraca) as reprovada:
        senhas.validar(curta)
    mensagem_real = str(reprovada.value)

    def _trocar(**_k: Any) -> None:
        raise senhas.SenhaFraca(mensagem_real)

    monkeypatch.setattr(db_usuarios, "trocar_a_propria_senha", _trocar)
    with pytest.raises(HTTPException) as caiu:
        pilot_app.me_trocar_senha(
            pilot_app.MinhaSenhaIn(senha_atual="x", nova_senha=curta), remote_user=ADMIN
        )
    assert caiu.value.status_code == 422
    assert f"{piso} caracteres" in str(caiu.value.detail)


@pytest.mark.usefixtures("login_proprio")
def test_sem_cadastro_no_banco_a_mensagem_nao_fala_da_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Aqui 409 significa "você não tem cadastro", não "a allowlist divergiu".

    Reaproveitar a mensagem do painel mandaria a pessoa procurar uma allowlist em que ela nunca
    esteve — por isso `_minha_identidade` existe separada de `_identidade_do_admin`.
    """
    from motor_expansao.db import rbac

    monkeypatch.setattr(rbac, "identidade", lambda _u: None)
    with pytest.raises(HTTPException) as caiu:
        pilot_app.me_trocar_senha(
            pilot_app.MinhaSenhaIn(senha_atual="x", nova_senha="uma frase bem longa"),
            remote_user="ninguem",
        )
    assert caiu.value.status_code == 409
    assert "allowlist" not in str(caiu.value.detail).lower()


# --------------------------------------------------------------------------------------
# A senha DE OUTRA PESSOA (15/09)
# --------------------------------------------------------------------------------------

_ROTAS_DE_SENHA_ALHEIA = (
    ("acessos_usuarios_redefinir_senha", "redefinir_senha"),
    ("acessos_usuarios_exigir_troca", "exigir_troca"),
)


@pytest.mark.parametrize(("rota", "_funcao"), _ROTAS_DE_SENHA_ALHEIA)
def test_fora_da_allowlist_as_rotas_de_senha_alheia_nao_existem(
    monkeypatch: pytest.MonkeyPatch, rota: str, _funcao: str
) -> None:
    """Sob `/api/acessos/`: 404 que nao anuncia existencia, antes de resolver identidade."""
    monkeypatch.setattr(pilot_app.acesso, "pode_ver_acessos", lambda _u: False)

    def _nao_deveria(_u: Any) -> None:
        raise AssertionError("resolveu identidade fora da allowlist")

    monkeypatch.setattr(pilot_app, "_identidade_do_admin", _nao_deveria)
    with pytest.raises(HTTPException) as caiu:
        getattr(pilot_app, rota)(9, remote_user="qualquer")
    assert caiu.value.status_code == 404


@pytest.mark.parametrize(("rota", "funcao"), _ROTAS_DE_SENHA_ALHEIA)
@pytest.mark.usefixtures("login_proprio")
def test_as_rotas_de_senha_alheia_passam_o_alvo_e_o_autor(
    monkeypatch: pytest.MonkeyPatch, rota: str, funcao: str
) -> None:
    _identidade(monkeypatch, _Eu())
    visto: dict[str, Any] = {}
    monkeypatch.setattr(
        db_usuarios,
        funcao,
        lambda i, *, autor: visto.update(alvo=i, autor=autor) or {"id_usuario": i},
    )
    getattr(pilot_app, rota)(9, remote_user=ADMIN)
    assert visto == {"alvo": 9, "autor": 7}


@pytest.mark.parametrize(("rota", "funcao"), _ROTAS_DE_SENHA_ALHEIA)
@pytest.mark.parametrize(("erro", "status"), [("UsuarioDesconhecido", 404), ("AlvoEhOAutor", 403)])
@pytest.mark.usefixtures("login_proprio")
def test_cada_recusa_da_senha_alheia_tem_seu_status(
    monkeypatch: pytest.MonkeyPatch, rota: str, funcao: str, erro: str, status: int
) -> None:
    _identidade(monkeypatch, _Eu())
    classe = getattr(db_usuarios, erro)

    def _falha(*_a: Any, **_k: Any) -> None:
        raise classe("não")

    monkeypatch.setattr(db_usuarios, funcao, _falha)
    with pytest.raises(HTTPException) as caiu:
        getattr(pilot_app, rota)(9, remote_user=ADMIN)
    assert caiu.value.status_code == status


@pytest.mark.usefixtures("login_proprio")
def test_redefinir_sem_senha_inicial_e_503_com_o_recado_do_operador(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from motor_expansao.db import senhas

    _identidade(monkeypatch, _Eu())

    def _falha(*_a: Any, **_k: Any) -> None:
        raise senhas.SenhaInicialNaoConfigurada("MOTOR_SENHA_INICIAL não está definida.")

    monkeypatch.setattr(db_usuarios, "redefinir_senha", _falha)
    with pytest.raises(HTTPException) as caiu:
        pilot_app.acessos_usuarios_redefinir_senha(9, remote_user=ADMIN)
    assert caiu.value.status_code == 503
    assert "MOTOR_SENHA_INICIAL" in str(caiu.value.detail)


# --------------------------------------------------------------------------------------
# Login proprio DESLIGADO: os tres gestos de senha recusam (decisao do dono, 24/10/2026)
# --------------------------------------------------------------------------------------
# Com `MOTOR_AUTENTICACAO_PROPRIA` desligada quem confere a senha e' o Authelia. A troca da
# propria senha pedia a INICIAL do banco -- sorteada em producao, ninguem a conhece -- e
# recusava todo mundo; a temporaria de 2 h que o admin repassava nao abria nada.

_GESTOS_DE_SENHA = [
    pytest.param(
        lambda: pilot_app.me_trocar_senha(
            pilot_app.MinhaSenhaIn(senha_atual="x", nova_senha="uma frase bem longa"),
            remote_user=ADMIN,
        ),
        "LOGIN_PROPRIO_DESLIGADO_TROCA",
        id="trocar-a-propria",
    ),
    pytest.param(
        lambda: pilot_app.acessos_usuarios_redefinir_senha(9, remote_user=ADMIN),
        "LOGIN_PROPRIO_DESLIGADO_ADMIN",
        id="redefinir-senha",
    ),
    pytest.param(
        lambda: pilot_app.acessos_usuarios_exigir_troca(9, remote_user=ADMIN),
        "LOGIN_PROPRIO_DESLIGADO_ADMIN",
        id="exigir-troca",
    ),
]


@pytest.mark.parametrize(("chamar", "constante"), _GESTOS_DE_SENHA)
def test_com_o_login_proprio_desligado_os_gestos_de_senha_recusam_sem_tocar_o_banco(
    monkeypatch: pytest.MonkeyPatch, chamar: Any, constante: str
) -> None:
    """404, o status do `/api/login` com a chave desligada -- e ANTES de qualquer ida ao banco.

    Recusar por configuracao nao precisa de identidade: os dubles abaixo explodem se a rota
    tentar resolver quem pediu ou escrever alguma coisa.
    """

    def _explode(*_a: Any, **_k: Any) -> None:
        raise AssertionError("a rota foi ao banco com o login proprio desligado")

    for nome in ("_identidade_do_admin", "_minha_identidade", "_derrubar_sessoes"):
        monkeypatch.setattr(pilot_app, nome, _explode)
    for nome in ("trocar_a_propria_senha", "redefinir_senha", "exigir_troca"):
        monkeypatch.setattr(db_usuarios, nome, _explode)

    with pytest.raises(HTTPException) as caiu:
        chamar()
    assert caiu.value.status_code == 404
    assert caiu.value.detail == getattr(pilot_app, constante)


def test_a_recusa_segue_o_STATUS_do_login_mas_fala_portugues() -> None:
    """O padrao e' o do `/api/login` com a chave desligada -- o mesmo 404 --, mas o texto nao e'
    o "Not Found" de la': aqui quem le' e' gente, numa tela aberta antes de a chave mudar."""
    with pytest.raises(HTTPException) as no_login:
        pilot_app.login(pilot_app.LoginIn(login="ana", senha="x"), request=None)  # type: ignore[arg-type]
    for texto in (pilot_app.LOGIN_PROPRIO_DESLIGADO_TROCA, pilot_app.LOGIN_PROPRIO_DESLIGADO_ADMIN):
        assert no_login.value.status_code == 404
        assert texto != no_login.value.detail
        assert "login próprio" in texto, "a recusa tem de dizer o que esta' desligado"
        assert "Authelia" in texto, "a recusa tem de dizer por onde se entra hoje"


@pytest.mark.parametrize("rota", ["acessos_usuarios_redefinir_senha", "acessos_usuarios_exigir_troca"])
def test_fora_da_allowlist_a_recusa_continua_o_not_found_cru(
    monkeypatch: pytest.MonkeyPatch, rota: str
) -> None:
    """A allowlist vem ANTES da chave. Ao contrario, o texto proprio da recusa anunciaria a rota
    a quem nao administra o painel -- e o "Not Found" cru e' o que a esconde (emenda da DEC-027)."""
    monkeypatch.setattr(pilot_app.acesso, "pode_ver_acessos", lambda _u: False)
    with pytest.raises(HTTPException) as caiu:
        getattr(pilot_app, rota)(9, remote_user="qualquer")
    assert caiu.value.status_code == 404
    assert caiu.value.detail == "Not Found"


@pytest.mark.usefixtures("login_proprio")
@pytest.mark.parametrize(("chamar", "_constante"), _GESTOS_DE_SENHA)
def test_com_o_login_proprio_ligado_os_gestos_chegam_ao_banco(
    monkeypatch: pytest.MonkeyPatch, chamar: Any, _constante: str
) -> None:
    """A outra metade: com a chave ligada, nenhum dos tres para na recusa de configuracao."""
    monkeypatch.setattr(pilot_app, "_identidade_do_admin", lambda _u: _Eu())
    monkeypatch.setattr(pilot_app, "_minha_identidade", lambda _u: _Eu())
    monkeypatch.setattr(pilot_app, "_derrubar_sessoes", lambda *_a, **_k: None)
    chegou: list[str] = []
    for nome in ("trocar_a_propria_senha", "redefinir_senha", "exigir_troca"):
        monkeypatch.setattr(
            db_usuarios,
            nome,
            lambda *_a, _n=nome, **_k: chegou.append(_n) or {"id_usuario": 9, "mudou": True},
        )
    chamar()
    assert len(chegou) == 1


@pytest.mark.parametrize("gesto", ["redefinir-senha", "exigir-troca"])
def test_as_rotas_de_senha_alheia_nao_recebem_corpo_e_exigem_gerir(gesto: str) -> None:
    """Sem corpo: o admin nao escolhe nem conhece a senha de ninguem. E a capacidade e' a de
    GERIR, nao a de ver o painel -- a regra de `POST` em `/api/acessos/usuarios` casa por prefixo."""
    import inspect

    molde = f"/api/acessos/usuarios/{{id_usuario}}/{gesto}"
    registradas = {r.path: r for r in pilot_app.app.routes if getattr(r, "path", "") == molde}
    assert molde in registradas, f"rota {molde} nao registrada"
    rota = registradas[molde]
    assert rota.methods == {"POST"}
    assert set(inspect.signature(rota.endpoint).parameters) == {"id_usuario", "remote_user"}

    concreto = f"/api/acessos/usuarios/9/{gesto}"
    capacidade = pilot_app.acesso.capacidade_necessaria
    assert capacidade(concreto, "POST") == "acesso.usuario_gerir"
    assert capacidade(concreto, "GET") == "acesso.painel_ver"


# --------------------------------------------------------------------------------------
# A senha TEMPORARIA (D31, 18/09) — o que a rota devolve, e o que ela nao pode deixar escapar
# --------------------------------------------------------------------------------------


@pytest.mark.usefixtures("login_proprio")
def test_a_rota_devolve_a_senha_para_o_admin_repassar(monkeypatch: pytest.MonkeyPatch) -> None:
    """A senha sai no CORPO, e e' a unica vez que um segredo faz isso aqui.

    O token de sessao vai no cookie justamente para nao sair no corpo (ha' teste proprio). A
    diferenca e' o destinatario: aqui quem le' e' uma PESSOA, que vai ditar por telefone. Sem
    isto a rota redefiniria a senha e ninguem saberia qual e' -- conta perdida.
    """
    import json

    _identidade(monkeypatch, _Eu())
    monkeypatch.setattr(
        db_usuarios,
        "redefinir_senha",
        lambda *_a, **_k: {
            "id_usuario": 9,
            "tinha_senha_propria": True,
            "senha_temporaria": "kvth-9rqm-2xbf",
            "validade_horas": 2,
        },
    )
    monkeypatch.setattr(pilot_app, "_derrubar_sessoes", lambda *_a, **_k: None)

    resposta = pilot_app.acessos_usuarios_redefinir_senha(9, remote_user=ADMIN)
    corpo = json.loads(bytes(resposta.body))
    assert corpo["senha_temporaria"] == "kvth-9rqm-2xbf"
    assert corpo["validade_horas"] == 2


@pytest.mark.usefixtures("login_proprio")
def test_a_resposta_com_a_senha_NAO_pode_ser_cacheada(monkeypatch: pytest.MonkeyPatch) -> None:
    """`no-store`, e nao `no-cache`: o corpo carrega uma senha VIVA.

    Sem o cabecalho ela fica no cache do navegador e em qualquer intermediario do caminho --
    lugares que ninguem vai lembrar de limpar quando a senha for trocada.
    """
    _identidade(monkeypatch, _Eu())
    monkeypatch.setattr(
        db_usuarios,
        "redefinir_senha",
        lambda *_a, **_k: {"id_usuario": 9, "senha_temporaria": "kvth-9rqm-2xbf"},
    )
    monkeypatch.setattr(pilot_app, "_derrubar_sessoes", lambda *_a, **_k: None)

    resposta = pilot_app.acessos_usuarios_redefinir_senha(9, remote_user=ADMIN)
    assert resposta.headers.get("cache-control") == "no-store"


@pytest.mark.usefixtures("login_proprio")
def test_a_senha_nova_nao_vai_para_o_LOG(monkeypatch: pytest.MonkeyPatch, caplog: Any) -> None:
    """O log da trilha e' lido por operador e vive 90 dias. Senha viva ali seria vazamento
    com prazo maior que o da propria senha."""
    import logging

    _identidade(monkeypatch, _Eu())
    monkeypatch.setattr(
        db_usuarios,
        "redefinir_senha",
        lambda *_a, **_k: {"id_usuario": 9, "senha_temporaria": "kvth-9rqm-2xbf"},
    )
    with caplog.at_level(logging.DEBUG):
        pilot_app.acessos_usuarios_redefinir_senha(9, remote_user=ADMIN)
    assert "kvth-9rqm-2xbf" not in caplog.text


# --------------------------------------------------------------------------------------
# Deploy SEM banco: 503 honesto nas SEIS rotas, e não 500 cru (BLK-SAUDE-02)
# --------------------------------------------------------------------------------------
# Medido em produção em 29/09/2026 pela trilha da DEC-027: `GET /api/acessos/usuarios`
# respondeu 500 em **139 de 139 chamadas**, zero sucessos desde 18/09, para os três nomes
# da allowlist. O traceback colhido ao vivo:
#
#   app.py acessos_usuarios_listar -> _identidade_do_admin -> db/rbac.py identidade
#     -> db/postgres.py conexao -> BancoNaoConfigurado: MOTOR_DATABASE_URL nao definida
#
# `BancoNaoConfigurado` e `BancoIndisponivel` são IRMÃS (as duas herdam direto de
# `RuntimeError`), e as duas funções de identidade capturavam só a segunda.
#
# A LACUNA DE TESTE QUE PERMITIU ISSO, e que estes casos fecham: o tradutor
# `_erro_de_usuarios` JÁ tinha o ramo de `BancoNaoConfigurado`, coberto por
# `test_deploy_sem_banco_e_503_e_nao_500` — mas aquele teste usa o helper `_identidade`,
# que substitui `_identidade_do_admin` INTEIRA por uma lambda, então o corpo real nunca
# rodava. O único caso que exercitava o corpo real
# (`test_banco_fora_do_ar_na_identidade_e_503`) cobria apenas a irmã `BancoIndisponivel`.
# Duas redes, e o peixe passou entre as duas.
#
# Por isso aqui NADA é stubado além de `rbac.identidade`: é o corpo de verdade que precisa
# de prova.


def _rbac_sem_banco(monkeypatch: pytest.MonkeyPatch) -> None:
    """`rbac.identidade` levanta o que um deploy sem `MOTOR_DATABASE_URL` levanta."""
    from motor_expansao.db import BancoNaoConfigurado, rbac

    def _falha(_u: Any) -> None:
        raise BancoNaoConfigurado("MOTOR_DATABASE_URL nao definida")

    monkeypatch.setattr(rbac, "identidade", _falha)


#: As CINCO rotas que passam por `_identidade_do_admin`. Uma causa, seis rotas — e cinco
#: delas nunca apareceram na trilha porque a listagem quebra ANTES de a tela desenhar os
#: botões que as disparariam. Parametrizar é o que prova que o conserto único cobre todas.
_ROTAS_DO_ADMIN = [
    pytest.param(lambda: pilot_app.acessos_usuarios_listar(remote_user=ADMIN), id="listar"),
    pytest.param(
        # Corpo VÁLIDO de propósito: esta rota valida o payload ANTES de resolver
        # identidade, então `UsuarioAdminIn()` vazio pararia num 422 sem nunca chegar ao
        # `_identidade_do_admin` — o teste passaria a medir a validação, não o conserto.
        lambda: pilot_app.acessos_usuarios_alterar(
            9, pilot_app.UsuarioAdminIn(perfil="expansao"), remote_user=ADMIN
        ),
        id="alterar",
    ),
    pytest.param(
        lambda: pilot_app.acessos_usuarios_criar(_corpo_novo(), remote_user=ADMIN), id="criar"
    ),
    pytest.param(
        lambda: pilot_app.acessos_usuarios_redefinir_senha(9, remote_user=ADMIN),
        id="redefinir-senha",
    ),
    pytest.param(
        lambda: pilot_app.acessos_usuarios_exigir_troca(9, remote_user=ADMIN),
        id="exigir-troca",
    ),
]


@pytest.mark.parametrize("chamar", _ROTAS_DO_ADMIN)
@pytest.mark.usefixtures("login_proprio")
def test_deploy_sem_banco_na_identidade_do_admin_e_503_e_nao_500(
    chamar: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """As cinco rotas de administração, com o corpo REAL de `_identidade_do_admin`."""
    _rbac_sem_banco(monkeypatch)
    with pytest.raises(HTTPException) as caiu:
        chamar()
    assert caiu.value.status_code == 503, "voltou a ser 500 cru num deploy sem banco"
    # A mensagem também, e não só o status: 503 sozinho não diz ao operador o que fazer.
    assert "banco" in str(caiu.value.detail).lower()


@pytest.mark.usefixtures("login_proprio")
def test_deploy_sem_banco_na_troca_da_propria_senha_e_503_e_nao_500(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sexta rota, que passa por `_minha_identidade` e não por `_identidade_do_admin`."""
    _rbac_sem_banco(monkeypatch)
    with pytest.raises(HTTPException) as caiu:
        pilot_app.me_trocar_senha(
            pilot_app.MinhaSenhaIn(senha_atual="a-inicial", nova_senha="uma frase bem longa"),
            remote_user="qualquer",
        )
    assert caiu.value.status_code == 503
    assert "banco" in str(caiu.value.detail).lower()


@pytest.mark.usefixtures("login_proprio")
def test_as_duas_mensagens_de_sem_banco_sao_DIFERENTES(monkeypatch: pytest.MonkeyPatch) -> None:
    """E é por isso que `_minha_identidade` existe separada de `_identidade_do_admin`.

    O docstring de `_minha_identidade` declara a razão: no painel, a falta significa "a
    allowlist e o banco divergiram", problema do operador; em `/api/me/senha` significa
    outra conversa. Mandar o recado do painel a quem tentou trocar a PRÓPRIA senha manda a
    pessoa procurar uma tela que ela pode nem ter permissão de abrir.

    Sem esta guarda, "simplificar" as duas funções numa só passaria verde — os dois testes
    acima só exigem 503 e a palavra "banco".
    """
    _rbac_sem_banco(monkeypatch)

    with pytest.raises(HTTPException) as no_painel:
        pilot_app.acessos_usuarios_listar(remote_user=ADMIN)
    with pytest.raises(HTTPException) as na_senha:
        pilot_app.me_trocar_senha(
            pilot_app.MinhaSenhaIn(senha_atual="a-inicial", nova_senha="uma frase bem longa"),
            remote_user="qualquer",
        )

    do_painel = str(no_painel.value.detail)
    da_senha = str(na_senha.value.detail)
    assert do_painel != da_senha, "as duas mensagens colapsaram numa só"
    assert "usuários" in do_painel.lower(), "o recado do painel perdeu o assunto dele"
    assert "senha" in da_senha.lower(), "o recado da troca de senha perdeu o assunto dele"


def test_banco_AUSENTE_e_banco_FORA_DO_AR_nao_dizem_a_mesma_coisa(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """Irmãs, e a distinção é operacional, não estética.

    `BancoNaoConfigurado` é ESCOLHA declarada (§4 do CLAUDE.md: banco vazio devolve o piloto
    ao comportamento pré-banco) — não há nada para consertar, é o estado esperado deste
    deploy. `BancoIndisponivel` é INCIDENTE: o banco existe e não respondeu, e alguém tem de
    ir olhar. Colapsar as duas num `except (A, B)` com mensagem única faria o operador
    procurar um incidente que não existe — ou ignorar um que existe.
    """
    from motor_expansao.db import BancoIndisponivel, BancoNaoConfigurado, rbac

    def _levantar(exc: Exception) -> Any:
        def _f(_u: Any) -> None:
            raise exc

        return _f

    monkeypatch.setattr(rbac, "identidade", _levantar(BancoNaoConfigurado("sem URL")))
    with pytest.raises(HTTPException) as ausente:
        pilot_app.acessos_usuarios_listar(remote_user=ADMIN)

    monkeypatch.setattr(rbac, "identidade", _levantar(BancoIndisponivel("pool fechado")))
    with pytest.raises(HTTPException) as fora:
        pilot_app.acessos_usuarios_listar(remote_user=ADMIN)

    assert ausente.value.status_code == fora.value.status_code == 503

    # Compara o SENTIDO, não o texto interpolado. Comparar `str(detail)` seria guarda cega:
    # as duas frases embutem a mensagem da exceção (`sem URL` x `pool fechado`), então
    # bastaria a exceção ter texto diferente para elas "diferirem" mesmo com a MESMA
    # redação. Foi assim que a primeira versão deste teste deixou passar uma sabotagem que
    # trocava o ramo do ausente pela frase do incidente.
    msg_ausente = str(ausente.value.detail).lower()
    msg_fora = str(fora.value.detail).lower()
    assert "sem banco configurado" in msg_ausente, (
        "o ausente parou de dizer que é CONFIGURAÇÃO e o operador vai caçar um incidente"
    )
    assert "sem banco configurado" not in msg_fora, (
        "o incidente passou a se anunciar como escolha de operação, e ninguém vai olhar"
    )
