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
