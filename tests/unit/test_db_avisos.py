"""Os avisos do sino (DEC-090, migration 028): quem recebe, a lista e o "lido ate'".

Sem Postgres na suite unitaria: um duble responde por PEDACO de SQL, no molde do
`test_db_usuarios.py`, e o teste confere o que o modulo pede ao banco e o que devolve.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import pytest

from motor_expansao.db import avisos as mod


class _Resultado:
    def __init__(self, linhas: list[tuple[Any, ...]]) -> None:
        self.linhas = linhas

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self.linhas)

    def fetchone(self) -> tuple[Any, ...] | None:
        return self.linhas[0] if self.linhas else None


class _Con:
    def __init__(self, respostas: dict[str, list[tuple[Any, ...]]]) -> None:
        self.respostas = respostas
        self.executados: list[tuple[str, Any]] = []

    def execute(self, sql: str, params: Any = None) -> _Resultado:
        self.executados.append((sql, params))
        for pedaco, linhas in self.respostas.items():
            if pedaco in sql:
                return _Resultado(linhas)
        return _Resultado([])


def _instalar(monkeypatch: pytest.MonkeyPatch, respostas: dict[str, list[tuple[Any, ...]]]) -> _Con:
    con = _Con(respostas)

    @contextmanager
    def conexao() -> Any:
        yield con

    @contextmanager
    def transacao(id_usuario: int | None = None) -> Any:
        yield con

    monkeypatch.setattr(mod, "conexao", conexao)
    monkeypatch.setattr(mod, "transacao", transacao)
    return con


def test_os_avisos_sao_os_do_check_da_028() -> None:
    """O identificador de cada aviso e' o mesmo do CHECK `chk_usuario_avisos_tipo`, e cada um sai
    de um evento da trilha."""
    from pathlib import Path

    sql = Path(mod.__file__).with_name("migracoes").joinpath("028-avisos.sql").read_text("utf-8")
    assert "CHECK (aviso IN ('estudo_master', 'imovel_master'))" in sql
    assert set(mod.AVISOS) == {"estudo_master", "imovel_master"}
    assert mod.AVISOS["estudo_master"][1] == "estudo.solicitado"
    assert mod.AVISOS["imovel_master"][1] == "imovel.solicitado"
    assert "'avisos.estudos_masters'" in sql and "('growth', 'avisos.estudos_masters')" in sql


def test_o_growth_recebe_o_estudo_pelo_perfil_e_a_priscila_o_imovel_pela_lista(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """19/11/2026, Juan: o estudo para "o time todo da Growth" (a capacidade do perfil); o imovel
    para a Priscila (marcado para ela na aba Acessos)."""
    _instalar(monkeypatch, {"FROM usuario_avisos": []})
    assert mod.avisos_que_recebe(1, frozenset({"avisos.estudos_masters", "rede.ver"})) == (
        "estudo_master",
    )
    _instalar(monkeypatch, {"FROM usuario_avisos": [("imovel_master",)]})
    assert mod.avisos_que_recebe(2, frozenset({"rede.ver"})) == ("imovel_master",)
    # Os dois, na ordem da tela; e quem nao tem nem um nem outro, nenhum.
    _instalar(monkeypatch, {"FROM usuario_avisos": [("imovel_master",)]})
    assert mod.avisos_que_recebe(3, frozenset({"avisos.estudos_masters"})) == (
        "estudo_master",
        "imovel_master",
    )
    _instalar(monkeypatch, {"FROM usuario_avisos": []})
    assert mod.avisos_que_recebe(4, frozenset({"rede.ver"})) == ()


def test_a_lista_traz_os_eventos_dos_avisos_da_pessoa_e_quantos_ela_nao_viu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quando = datetime(2026, 11, 19, 17, 32, tzinfo=UTC)
    con = _instalar(
        monkeypatch,
        {
            "FROM avisos_lidos": [(40,)],
            "ORDER BY e.id_evento DESC": [
                (
                    42,
                    "estudo.solicitado",
                    {"masters": ["dfgo"], "lugar": "Ceilândia, Brasília/DF", "fora_da_area": False},
                    quando,
                    "Dalmo Dias Ribeiro",
                ),
                (39, "estudo.solicitado", {"masters": ["dfgo"]}, quando, None),
            ],
            "count(*)": [(1,)],
        },
    )
    r = mod.listar(7, ("estudo_master",))
    assert r["nao_lidos"] == 1 and r["ultimo_lido"] == 40
    assert [i["id"] for i in r["itens"]] == [42, 39]
    assert r["itens"][0] == {
        "id": 42,
        "aviso": "estudo_master",
        "quando": quando.isoformat(),
        "quem": "Dalmo Dias Ribeiro",
        "dados": {"masters": ["dfgo"], "lugar": "Ceilândia, Brasília/DF", "fora_da_area": False},
        "lido": False,
    }
    assert r["itens"][1]["lido"] is True and r["itens"][1]["quem"] is None
    # So' os eventos dos avisos que a pessoa recebe.
    listar = next(p for s, p in con.executados if "ORDER BY e.id_evento DESC" in s)
    assert listar == (["estudo.solicitado"], mod.LIMITE_DA_LISTA)


def test_sem_aviso_nenhum_a_lista_vem_vazia_sem_ir_ao_banco(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    con = _instalar(monkeypatch, {})
    assert mod.listar(7, ()) == {"itens": [], "nao_lidos": 0, "ultimo_lido": 0}
    assert con.executados == []


def test_marcar_lidos_so_anda_para_a_frente(monkeypatch: pytest.MonkeyPatch) -> None:
    """`GREATEST` no SQL: duas abas abertas nao fazem o sino voltar a contar o que foi visto."""
    con = _instalar(monkeypatch, {})
    mod.marcar_lidos(7, 42)
    (sql, params) = con.executados[0]
    assert "INSERT INTO avisos_lidos" in sql and "GREATEST" in sql
    assert params == (7, 42)
    mod.marcar_lidos(7, -5)
    assert con.executados[1][1] == (7, 0)
