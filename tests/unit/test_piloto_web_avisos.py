"""O sino do piloto (DEC-090): as rotas `/api/avisos` e `/api/avisos/lidos` e o lugar do ponto.

A conta de quem recebe e a leitura da trilha tem os testes delas (`test_db_avisos.py`); aqui se
confere a ROTA: so' os avisos de quem pede, o rotulo do master, a falha do banco virando 503 e o
"lido ate'" indo para a pessoa certa. Chama as funcoes de rota direto, no padrao da suite.
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

import acesso  # noqa: E402
import app as pilot  # noqa: E402

from motor_expansao.db import avisos as db_avisos  # noqa: E402
from motor_expansao.db import rbac  # noqa: E402


def _quem(monkeypatch: pytest.MonkeyPatch, permissoes: set[str], marcados: set[str]) -> None:
    """Banco no comando, a identidade e os avisos marcados para ela dublados."""
    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)
    monkeypatch.setattr(
        rbac,
        "identidade",
        lambda _login: rbac.Identidade(
            id_usuario=7,
            login="alguem",
            perfil="growth",
            permissoes=frozenset(permissoes),
            paises=frozenset({"BR"}),
        ),
    )
    monkeypatch.setattr(db_avisos, "avisos_da_pessoa", lambda _id: frozenset(marcados))


def test_o_sino_traz_os_avisos_da_pessoa_com_o_master_por_extenso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quem(monkeypatch, {"avisos.estudos_masters"}, set())
    pedidos: list[tuple[int, tuple[str, ...]]] = []

    def listar(id_usuario: int, avisos: tuple[str, ...]) -> dict[str, Any]:
        pedidos.append((id_usuario, avisos))
        return {
            "itens": [
                {
                    "id": 42,
                    "aviso": "estudo_master",
                    "quando": "2026-11-19T17:32:00+00:00",
                    "quem": "Dalmo Dias Ribeiro",
                    "dados": {"masters": ["dfgo"], "lugar": "Ceilândia, Brasília/DF"},
                    "lido": False,
                }
            ],
            "nao_lidos": 1,
            "ultimo_lido": 40,
        }

    monkeypatch.setattr(db_avisos, "listar", listar)
    monkeypatch.setattr(pilot, "_rotulos_dos_masters", lambda: {"dfgo": "DF/GO"})
    r = pilot.api_avisos(remote_user="alguem")
    assert pedidos == [(7, ("estudo_master",))]
    assert r["avisos"] == ["estudo_master"] and r["nao_lidos"] == 1
    assert r["itens"][0]["masters"] == ["DF/GO"]


def test_quem_nao_recebe_aviso_nenhum_ve_o_sino_vazio_sem_ler_a_trilha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quem(monkeypatch, {"rede.ver"}, set())
    monkeypatch.setattr(db_avisos, "listar", lambda *_a: pytest.fail("leu a trilha"))
    assert pilot.api_avisos(remote_user="alguem") == {
        "avisos": [],
        "itens": [],
        "nao_lidos": 0,
        "ultimo_lido": 0,
    }


def test_sem_banco_no_comando_o_sino_vem_vazio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(acesso, "banco_no_comando", lambda: False)
    assert pilot.api_avisos(remote_user="alguem")["itens"] == []
    assert pilot._avisos_de_quem_pede("alguem") is None


def test_o_banco_falhando_vira_503_no_sino_e_some_do_me(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nas rotas do sino a falha sobe como 503; no `/api/me`, o sino so' some (o `me` responde)."""
    _quem(monkeypatch, {"avisos.estudos_masters"}, set())

    def falha(_id: int) -> frozenset[str]:
        raise RuntimeError("banco ocupado")

    monkeypatch.setattr(db_avisos, "avisos_da_pessoa", falha)
    with pytest.raises(HTTPException) as erro:
        pilot.api_avisos(remote_user="alguem")
    assert erro.value.status_code == 503
    with pytest.raises(HTTPException) as erro:
        pilot.api_avisos_lidos(pilot.AvisosLidosIn(ate=42), remote_user="alguem")
    assert erro.value.status_code == 503
    assert pilot._avisos_de_quem_pede("alguem") is None


def test_abrir_o_sino_marca_lido_ate_o_mais_novo_para_quem_pediu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quem(monkeypatch, set(), {"imovel_master"})
    marcados: list[tuple[int, int]] = []
    monkeypatch.setattr(db_avisos, "marcar_lidos", lambda i, ate: marcados.append((i, ate)))
    assert pilot.api_avisos_lidos(pilot.AvisosLidosIn(ate=42), remote_user="alguem") == {"ok": True}
    assert marcados == [(7, 42)]


def test_as_rotas_do_sino_sao_da_propria_pessoa() -> None:
    """Livres do gate de aba, como o `/api/me`: resolvem quem pede, sem alvo como parametro."""
    assert {"/api/avisos", "/api/avisos/lidos"} <= acesso.ROTAS_LIVRES


# ---------------------------------------------------------------------------------------------
# O lugar do ponto ("da onde"), no aviso do estudo
# ---------------------------------------------------------------------------------------------


class _Malha:
    def __init__(self, resolvido: tuple[str, str] | None) -> None:
        self.resolvido = resolvido

    def resolver(self, _lat: float, _lng: float) -> tuple[str, str] | None:
        return self.resolvido


def _lugar(
    monkeypatch: pytest.MonkeyPatch, resolvido: tuple[str, str] | None, bairro: str | None
) -> str | None:
    import pandas as pd

    from motor_expansao.api import service
    from motor_expansao.pipelines import materializar_setores_censitarios_geo as geo

    monkeypatch.setattr(service, "_carregar_malha", lambda _d: _Malha(resolvido))
    monkeypatch.setattr(
        geo,
        "ler_particao_setores",
        lambda *_a, **_k: pd.DataFrame({"nome_municipio": ["Brasília", "Brasília"]}),
    )
    monkeypatch.setattr(pilot, "_nome_do_hexagono", lambda *_a: bairro)
    return pilot._lugar_do_ponto(-15.82, -48.11)


def test_o_lugar_e_o_bairro_e_o_municipio(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _lugar(monkeypatch, ("DF", "5300108"), "Ceilândia") == "Ceilândia, Brasília/DF"


def test_sem_nome_no_hexagono_o_lugar_e_o_municipio(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _lugar(monkeypatch, ("DF", "5300108"), None) == "Brasília/DF"
    # O bairro que so' repete o municipio tambem nao entra.
    assert _lugar(monkeypatch, ("DF", "5300108"), "Brasília") == "Brasília/DF"


def test_fora_da_malha_ou_com_falha_o_lugar_fica_vazio(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _lugar(monkeypatch, None, "Ceilândia") is None

    def explode(*_a: Any) -> Any:
        raise OSError("particao ilegivel")

    monkeypatch.setattr(pilot, "_nome_do_hexagono", explode)
    from motor_expansao.api import service

    monkeypatch.setattr(service, "_carregar_malha", lambda _d: _Malha(("DF", "5300108")))
    assert pilot._lugar_do_ponto(-15.82, -48.11) is None
