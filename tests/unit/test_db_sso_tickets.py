"""Ticket de uso unico do SSO entre hosts (DEC-083) — sem tocar banco nenhum.

O que estes testes guardam:
  1. **O token nunca vai ao banco.** O que viaja no parametro e' o HASH, sempre (igual a sessoes).
  2. **O uso unico e' ATOMICO.** `SQL_CONSUMIR` tem `consumido_em_ticket IS NULL` E
     `expira_em_ticket > now()` no MESMO `UPDATE ... RETURNING` -- e' isso que impede replay.
  3. **O consumo devolve o dono e o pais** do `RETURNING`, para o endpoint abrir a sessao local
     e conferir o host (`pais_destino == PERFIL.pais`).
  4. Emissao grava `pais_destino`, `id_sessao_origem` e o TTL; sem linha no consumo => None.

Mesma infra de fake de `test_db_sessoes.py` (driver falso via `postgres._driver`), copiada aqui
para o teste ser auto-contido.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest

from motor_expansao import db
from motor_expansao.db import postgres, sso_tickets


class FakeCursor:
    def __init__(self, linhas: list[tuple[Any, ...]], rowcount: int) -> None:
        self.linhas = linhas
        self.rowcount = rowcount

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.linhas

    def fetchone(self) -> tuple[Any, ...] | None:
        return self.linhas[0] if self.linhas else None


class FakeConexao:
    def __init__(self, linhas: list[tuple[Any, ...]], rowcount: int = 0) -> None:
        self.linhas = linhas
        self.rowcount = rowcount
        self.executados: list[tuple[str, Any]] = []
        self.autocommit = False

    def execute(self, sql: str, params: Any = None) -> FakeCursor:
        self.executados.append((sql, params))
        return FakeCursor(self.linhas, self.rowcount)

    @contextmanager
    def transaction(self):  # type: ignore[no-untyped-def]
        yield self


class FakePool:
    def __init__(self, con: FakeConexao) -> None:
        self._con = con

    @contextmanager
    def connection(self):  # type: ignore[no-untyped-def]
        yield self._con

    def open(self, wait: bool = False) -> None: ...
    def close(self) -> None: ...


def _instalar(
    monkeypatch: pytest.MonkeyPatch,
    linhas: list[tuple[Any, ...]] | None = None,
    rowcount: int = 0,
) -> FakeConexao:
    con = FakeConexao(linhas or [], rowcount)
    monkeypatch.setattr(postgres, "_driver", lambda: lambda **_k: FakePool(con))
    monkeypatch.setenv(postgres.ENV_URL, "postgresql://fake/motor")
    return con


@pytest.fixture(autouse=True)
def _limpo() -> Any:
    db.fechar_pool()
    yield
    db.fechar_pool()


def _sql_do(con: FakeConexao, fragmento: str) -> tuple[str, Any]:
    for sql, params in con.executados:
        if fragmento in sql:
            return sql, params
    raise AssertionError(
        f"nenhum comando contem {fragmento!r}; executados: "
        + ", ".join(sql.strip().split(chr(10))[0] for sql, _ in con.executados)
    )


# --- emissao -----------------------------------------------------------------------------


def test_emitir_manda_o_HASH_nunca_o_token(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _instalar(monkeypatch, [(99, "2026-11-09T00:00:00Z")])
    emitido = sso_tickets.emitir(id_usuario=7, pais_destino="AR", id_sessao_origem=42)

    _sql, params = _sql_do(con, "INSERT INTO sso_tickets")
    # ordem de SQL_EMITIR: (id_usuario, hash, pais_destino, ttl, id_sessao_origem)
    assert params[0] == 7
    assert params[1] == sso_tickets.hash_do_token(emitido.token)
    assert params[1] != emitido.token, "o TOKEN em claro nao pode ir ao banco, so' o hash"
    assert params[2] == "AR"
    assert params[3] == sso_tickets.TTL_TICKET_S
    assert params[4] == 42
    # RETURNING: id_ticket + expira_em
    assert emitido.id_ticket == 99
    assert emitido.expira_em == "2026-11-09T00:00:00Z"


def test_emitir_sem_sessao_origem_e_opcional(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _instalar(monkeypatch, [(1, "x")])
    sso_tickets.emitir(id_usuario=5, pais_destino="BR")
    _sql, params = _sql_do(con, "INSERT INTO sso_tickets")
    assert params[4] is None  # id_sessao_origem default None (handoff sem rastro de origem)


# --- consumo -----------------------------------------------------------------------------


def test_consumir_e_ATOMICO_uso_unico() -> None:
    # Contrato de string: o UPDATE so' casa linha ainda NAO consumida e NAO expirada, no MESMO
    # comando com RETURNING. Sem isto, dois consumos simultaneos (replay) passariam os dois.
    sql = sso_tickets.SQL_CONSUMIR
    assert "UPDATE sso_tickets" in sql
    assert "consumido_em_ticket IS NULL" in sql
    assert "expira_em_ticket > now()" in sql
    assert "RETURNING id_usuario, pais_destino" in sql


def test_consumir_devolve_dono_e_pais_do_returning(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _instalar(monkeypatch, [(42, "BR")], rowcount=1)
    consumido = sso_tickets.consumir("tok-em-claro")
    assert consumido is not None
    assert consumido.id_usuario == 42
    assert consumido.pais_destino == "BR"
    # manda o HASH do token, nunca o token
    _sql, params = _sql_do(con, "UPDATE sso_tickets")
    assert params[0] == sso_tickets.hash_do_token("tok-em-claro")
    assert params[0] != "tok-em-claro"


def test_consumir_sem_linha_e_None(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ticket inexistente, ja' consumido ou expirado: o UPDATE nao casa linha -> fetchone None.
    _instalar(monkeypatch, [])
    assert sso_tickets.consumir("tok") is None


def test_consumir_token_vazio_nao_toca_banco(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _instalar(monkeypatch, [(1, "BR")])
    assert sso_tickets.consumir("") is None
    assert con.executados == [], "token vazio nao deve abrir transacao nenhuma"


def test_sql_emitir_insere_as_colunas_certas() -> None:
    sql = sso_tickets.SQL_EMITIR
    for coluna in ("id_usuario", "token_hash_ticket", "pais_destino", "expira_em_ticket",
                   "id_sessao_origem"):
        assert coluna in sql
    assert "make_interval(secs => %s)" in sql  # TTL calculado no banco, nao no Python


# --- espiar (le sem consumir, para a pagina de confirmacao da DEC-083) -------------------


def test_espiar_le_sem_consumir(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _instalar(monkeypatch, [("felipe", "BR")])
    esp = sso_tickets.espiar("tok-claro")
    assert esp is not None
    assert esp.login == "felipe"
    assert esp.pais_destino == "BR"
    sql, params = _sql_do(con, "SELECT u.login_usuario")
    assert "UPDATE" not in sql, "espiar LE, nunca consome"
    assert params[0] == sso_tickets.hash_do_token("tok-claro")
    assert params[0] != "tok-claro"


def test_espiar_sem_linha_e_None(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar(monkeypatch, [])
    assert sso_tickets.espiar("tok") is None


def test_espiar_token_vazio_nao_toca_banco(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _instalar(monkeypatch, [("x", "BR")])
    assert sso_tickets.espiar("") is None
    assert con.executados == []
