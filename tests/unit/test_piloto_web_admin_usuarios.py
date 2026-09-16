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

from motor_expansao.db import usuarios as db_usuarios  # noqa: E402

ADMIN = "vinicius"


class _Eu:
    id_usuario = 7


@pytest.fixture(autouse=True)
def _sou_admin(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Allowlist do painel liberada — cada teste que quiser o contrário desfaz."""
    monkeypatch.setattr(pilot_app.acesso, "pode_ver_acessos", lambda _u: True)
    yield


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


# --------------------------------------------------------------------------------------
# Escrita
# --------------------------------------------------------------------------------------


def test_corpo_vazio_e_422_e_nao_uma_escrita_a_toa(monkeypatch: pytest.MonkeyPatch) -> None:
    _identidade(monkeypatch, _Eu())
    with pytest.raises(HTTPException) as caiu:
        pilot_app.acessos_usuarios_alterar(9, pilot_app.UsuarioAdminIn(), remote_user=ADMIN)
    assert caiu.value.status_code == 422


def test_perfil_e_status_juntos_viram_duas_chamadas(monkeypatch: pytest.MonkeyPatch) -> None:
    """São duas decisões — 'virou Growth' e 'foi desativado' respondem a perguntas
    diferentes na auditoria e não devem colapsar numa linha só."""
    _identidade(monkeypatch, _Eu())
    chamadas: list[str] = []
    monkeypatch.setattr(
        db_usuarios,
        "alterar_perfil",
        lambda i, p, *, autor: chamadas.append(f"perfil:{i}:{p}:{autor}") or {"mudou": True},
    )
    monkeypatch.setattr(
        db_usuarios,
        "definir_ativo",
        lambda i, a, *, autor: chamadas.append(f"ativo:{i}:{a}:{autor}") or {"mudou": True},
    )
    saida = pilot_app.acessos_usuarios_alterar(
        9, pilot_app.UsuarioAdminIn(perfil="growth", ativo=False), remote_user=ADMIN
    )
    assert chamadas == ["perfil:9:growth:7", "ativo:9:False:7"]
    assert "perfil" in saida and "status" in saida


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

    monkeypatch.setattr(db_usuarios, "alterar_perfil", _falha)
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

    monkeypatch.setattr(db_usuarios, "alterar_perfil", _falha)
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

    monkeypatch.setattr(db_usuarios, "alterar_perfil", _falha)
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
        return {"id_usuario": 42, "login": "ana", "perfil": "expansao",
                "falta_cadastrar_no_authelia": True}

    monkeypatch.setattr(db_usuarios, "criar", _criar)
    saida = pilot_app.acessos_usuarios_criar(_corpo_novo(), remote_user=ADMIN)

    assert visto["autor"] == 7
    assert visto["login"] == "ana"
    assert saida["id_usuario"] == 42
    assert saida["falta_cadastrar_no_authelia"] is True


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


def test_senha_fraca_e_422(monkeypatch: pytest.MonkeyPatch) -> None:
    """A mensagem da política vai para a tela — ela é escrita para a pessoa, não para o log."""
    from motor_expansao.db import senhas

    monkeypatch.setattr(pilot_app, "_minha_identidade", lambda _u: _Eu())

    def _trocar(**_k: Any) -> None:
        raise senhas.SenhaFraca("A senha precisa de pelo menos 12 caracteres.")

    monkeypatch.setattr(db_usuarios, "trocar_a_propria_senha", _trocar)
    with pytest.raises(HTTPException) as caiu:
        pilot_app.me_trocar_senha(
            pilot_app.MinhaSenhaIn(senha_atual="x", nova_senha="curta"), remote_user=ADMIN
        )
    assert caiu.value.status_code == 422
    assert "12 caracteres" in str(caiu.value.detail)


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
