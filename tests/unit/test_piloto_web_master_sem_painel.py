"""O master SEM o próprio painel, temporariamente (emenda 3 da DEC-089, 23/11/2026).

Juan: "os masters não podem visualizar essas abas novas (vai ser temporariamente)". Com
`acesso.MASTER_VE_O_PROPRIO_PAINEL` desligado, o master com login próprio volta a ver só a
Executiva recortada, como antes da 027: sem a aba Masters, sem a trilha "Meu território" do Início
e recusado nas rotas de `/api/masters`. A capacidade `masters.ver_proprio` continua no banco, e
Growth e Líderes não mudam (nem a trilha de teste do Growth, `masters.inicio_testar`).

O comportamento com o painel LIGADO, para quando ele voltar, segue em `test_piloto_web_masters.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

_SERVER = Path(__file__).resolve().parents[2] / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import acesso  # noqa: E402
import app as pilot  # noqa: E402

from tests.unit.test_piloto_web_masters import _identidade, _login  # noqa: E402

#: O master da 025 + 027, como o banco o devolve depois das duas migrations.
MASTER = {"rede.ver_propria", "masters.ver_proprio"}


def test_o_painel_do_master_esta_desligado_de_proposito() -> None:
    """Religar é uma decisão: trocar esta constante para `True` (e este teste junto)."""
    assert acesso.MASTER_VE_O_PROPRIO_PAINEL is False


def test_o_master_ve_so_a_executiva(monkeypatch: pytest.MonkeyPatch) -> None:
    _identidade(monkeypatch, MASTER)
    assert acesso.abas_do_usuario_por_banco("alguem") == frozenset({"executiva"})


@pytest.mark.parametrize(
    ("metodo", "caminho"),
    [
        ("GET", "/api/masters"),
        ("GET", "/api/masters/rjsp"),
        ("POST", "/api/masters/solicitar-imovel"),
        ("POST", "/api/masters/estudo"),
    ],
)
def test_o_gate_recusa_o_master_na_tela_masters_e_nos_pedidos(
    monkeypatch: pytest.MonkeyPatch, metodo: str, caminho: str
) -> None:
    _identidade(monkeypatch, MASTER)
    assert acesso.motivo_bloqueio_por_banco(caminho, metodo, "alguem") is not None


def test_a_rota_tambem_recusa_o_master(monkeypatch: pytest.MonkeyPatch) -> None:
    """Além do gate, o recorte da rota (`_masters_do_pedido`) obedece à mesma chave."""
    _login(monkeypatch, "Master Um", MASTER)
    with pytest.raises(HTTPException) as erro:
        pilot._masters_do_pedido("alguem")
    assert erro.value.status_code == 403


def test_o_inicio_do_master_nao_ganha_a_trilha(monkeypatch: pytest.MonkeyPatch) -> None:
    _login(monkeypatch, "Master Um", MASTER)
    r = pilot.me(remote_user="alguem")
    assert set(r["abas"]) == {"executiva"}
    # Sem a aba Masters, o `/api/me` nem manda as chaves da trilha: o Início é o de sempre.
    assert not r.get("masters_proprio") and not r.get("trilha_do_master")
    assert acesso.ve_so_o_proprio_master("alguem") is False
    assert acesso.ve_a_trilha_do_master("alguem") is False


def test_so_o_login_de_teste_tem_o_painel_com_a_chave_desligada() -> None:
    """23/11/2026 (Felipe): o login de teste de master (id 24 na produção) testa o aviso de
    imóvel antes de os masters ganharem o painel. Só ele; tirar é `frozenset()`."""
    assert acesso.IDS_COM_O_PAINEL_DO_MASTER == frozenset({24})


def test_o_login_de_teste_ganha_o_painel_inteiro(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com o id dele na lista, o master de teste tem tudo o que a chave ligada daria: a aba, o
    gate nas leituras e nos dois POST do Início, a rota e a trilha "Meu território"."""
    # `_identidade` devolve o id 1: ele faz o papel do login de teste aqui.
    monkeypatch.setattr(acesso, "IDS_COM_O_PAINEL_DO_MASTER", frozenset({1}))
    _login(monkeypatch, "Master Um", MASTER)
    assert acesso.abas_do_usuario_por_banco("alguem") == frozenset({"executiva", "masters"})
    for metodo, caminho in (
        ("GET", "/api/masters"),
        ("GET", "/api/masters/rjsp"),
        ("POST", "/api/masters/solicitar-imovel"),
        ("POST", "/api/masters/estudo"),
    ):
        assert acesso.motivo_bloqueio_por_banco(caminho, metodo, "alguem") is None, caminho
    assert acesso.ve_so_o_proprio_master("alguem") is True
    assert acesso.ve_a_trilha_do_master("alguem") is True


def test_o_login_de_teste_nao_abre_o_painel_de_outro_master(monkeypatch: pytest.MonkeyPatch) -> None:
    """A lista libera o painel, não o recorte: outro id segue recusado, e o recorte da rota
    continua pelo nome (`_masters_do_pedido` devolve um conjunto, nunca `None` = todos)."""
    monkeypatch.setattr(acesso, "IDS_COM_O_PAINEL_DO_MASTER", frozenset({2}))
    _identidade(monkeypatch, MASTER)  # id 1, fora da lista
    assert acesso.abas_do_usuario_por_banco("alguem") == frozenset({"executiva"})
    assert acesso.motivo_bloqueio_por_banco("/api/masters", "GET", "alguem") is not None
    assert acesso.painel_do_master_ligado(None) is False


def test_growth_e_lideres_nao_mudam(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quem vê todos os masters segue com a aba e, no Growth, com a trilha de teste do Início."""
    _login(monkeypatch, "Fulano", {"masters.ver", "rede.ver", "masters.inicio_testar"})
    r = pilot.me(remote_user="alguem")
    assert {"executiva", "masters"} <= set(r["abas"])
    assert r["trilha_do_master"] is True
    assert acesso.motivo_bloqueio_por_banco("/api/masters", "GET", "alguem") is None
    assert pilot._masters_do_pedido("alguem") is None  # vê todos
