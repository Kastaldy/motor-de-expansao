"""Identidade e permissao a partir do banco (F3.3) — sem tocar banco nenhum.

O que estes testes guardam e' a fronteira de autorizacao: quem e' negado, quem e' aceito, e
sob que condicoes a identidade de DESENVOLVIMENTO vale. Esta ultima e' a mais perigosa do
conjunto — um modo que deixa alguem "ser qualquer usuario" e' porta dos fundos se vazar para
producao, entao ela tem teste proprio para cada trava.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest

from motor_expansao import db
from motor_expansao.db import postgres, rbac


class FakeConexao:
    def __init__(self, linhas: list[tuple[Any, ...]]) -> None:
        self.linhas = linhas
        self.executados: list[tuple[str, Any]] = []
        self.autocommit = False

    def execute(self, sql: str, params: Any = None) -> FakeConexao:
        self.executados.append((sql, params))
        return self

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.linhas

    def fetchone(self) -> tuple[Any, ...] | None:
        return self.linhas[0] if self.linhas else None

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


def _instalar(monkeypatch: pytest.MonkeyPatch, linhas: list[tuple[Any, ...]]) -> FakeConexao:
    con = FakeConexao(linhas)
    monkeypatch.setattr(postgres, "_driver", lambda: (lambda **_k: FakePool(con)))
    monkeypatch.setenv(postgres.ENV_URL, "postgresql://fake/motor")
    return con


@pytest.fixture(autouse=True)
def _limpo(monkeypatch: pytest.MonkeyPatch) -> Any:
    db.fechar_pool()
    # Sem sinal de producao e sem env de dev: cada teste declara o que precisa.
    monkeypatch.delenv(rbac.ENV_SINAL_PRODUCAO, raising=False)
    monkeypatch.delenv(rbac.ENV_DEV_USUARIO, raising=False)
    monkeypatch.delenv(rbac.ENV_DEV_IDENTIDADE, raising=False)
    yield
    db.fechar_pool()


# --------------------------------------------------------------------------------------
# Resolucao de identidade
# --------------------------------------------------------------------------------------


def test_usuario_conhecido_traz_id_perfil_e_permissoes(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar(
        monkeypatch,
        [
            (7, "lideres", "territorio.explorar"),
            (7, "lideres", "rede.ver"),
            (7, "lideres", "rede.cadastro_editar"),
        ],
    )
    quem = rbac.identidade("william_urso")
    assert quem is not None
    assert quem.id_usuario == 7
    assert quem.login == "william_urso"
    assert quem.perfil == "lideres"
    assert quem.pode("rede.ver")
    assert not quem.pode("acesso.painel_ver")


def test_usuario_desconhecido_e_negado_e_nao_e_criado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deny-by-default, como o `acesso_abas.json`: quem nao esta no mapa nao tem nada. Criar
    a pessoa aqui transformaria "autenticado no Authelia" em "autorizado no piloto"."""
    con = _instalar(monkeypatch, [])
    assert rbac.identidade("ninguem") is None
    assert not any("INSERT" in sql.upper() for sql, _ in con.executados)


def test_a_consulta_filtra_por_ativo(monkeypatch: pytest.MonkeyPatch) -> None:
    """O indice unico e' parcial (`WHERE ativo`), entao um login PODE existir numa linha
    inativa. Sem o filtro, alguem desativado voltaria a ser resolvido."""
    con = _instalar(monkeypatch, [(1, "expansao", "ponto.analisar")])
    rbac.identidade("alguem")
    sql, params = con.executados[-1]
    assert "u.ativo" in sql
    assert params == ("alguem",)


def test_perfil_sem_permissao_existe_mas_nao_pode_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    """LEFT JOIN devolve `chave` NULL. Existir-e-nao-poder e' diferente de nao existir, e o
    chamador precisa distinguir os dois para dar a mensagem certa."""
    _instalar(monkeypatch, [(9, "novato", None)])
    quem = rbac.identidade("novato")
    assert quem is not None
    assert quem.permissoes == frozenset()


def test_sem_login_nenhum_nao_consulta_o_banco(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _instalar(monkeypatch, [])
    assert rbac.identidade(None) is None
    assert con.executados == [], "consultou o banco sem ter quem procurar"


# --------------------------------------------------------------------------------------
# A identidade de desenvolvimento — a parte perigosa
# --------------------------------------------------------------------------------------


def test_em_dev_a_env_preenche_a_falta_do_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem Caddy nem Authelia na maquina, nao ha `Remote-User` — e sem isto o dev nao
    consegue exercitar autorizacao NENHUMA, que e' como o piloto esta hoje (fail-open)."""
    monkeypatch.setenv(rbac.ENV_DEV_USUARIO, "vinicius")
    assert rbac.login_efetivo(None) == "vinicius"


def test_o_header_real_sempre_vence_a_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """A env preenche o VAZIO; ela nunca sobrescreve quem o Authelia disse que e'. Inverter
    esta ordem seria permitir trocar de identidade por variavel de ambiente."""
    monkeypatch.setenv(rbac.ENV_DEV_USUARIO, "vinicius")
    assert rbac.login_efetivo("felipe") == "felipe"


def test_em_producao_a_env_de_dev_e_ignorada(monkeypatch: pytest.MonkeyPatch) -> None:
    """A trava que importa. `MOTOR_CADASTRO_DIR` so' existe no compose de producao — o mesmo
    sinal que o `acesso.py` ja' usa para o fail-closed, para nao haver dois conceitos de
    "estou em producao" que possam divergir."""
    monkeypatch.setenv(rbac.ENV_DEV_USUARIO, "quem_eu_quiser")
    monkeypatch.setenv(rbac.ENV_SINAL_PRODUCAO, "/app/cadastro")
    assert rbac.login_efetivo(None) is None


def test_override_explicito_desliga_a_identidade_de_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(rbac.ENV_DEV_USUARIO, "vinicius")
    monkeypatch.setenv(rbac.ENV_DEV_IDENTIDADE, "0")
    assert rbac.login_efetivo(None) is None


def test_override_explicito_liga_mesmo_com_sinal_de_producao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Escape hatch deliberado, para depurar um container. E' explicito e nomeado — o risco
    de alguem liga-lo por acidente e' menor que o de nao haver como investigar em campo."""
    monkeypatch.setenv(rbac.ENV_DEV_USUARIO, "vinicius")
    monkeypatch.setenv(rbac.ENV_SINAL_PRODUCAO, "/app/cadastro")
    monkeypatch.setenv(rbac.ENV_DEV_IDENTIDADE, "1")
    assert rbac.login_efetivo(None) == "vinicius"


def test_env_de_dev_vazia_nao_vira_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(rbac.ENV_DEV_USUARIO, "   ")
    assert rbac.login_efetivo(None) is None


# --------------------------------------------------------------------------------------
# Falha do banco
# --------------------------------------------------------------------------------------


def test_banco_fora_do_ar_levanta_em_vez_de_negar(monkeypatch: pytest.MonkeyPatch) -> None:
    """Negar em silencio faria "banco caiu" virar "voce nao tem acesso" para o usuario, e
    apagaria o incidente. A politica de falha (fail-closed nas sensiveis, fail-open em dev)
    e' do chamador, onde ela ja' vive."""
    monkeypatch.setenv(postgres.ENV_URL, "postgresql://fake/motor")

    def explode(**_kwargs: Any) -> Any:
        raise OSError("connection refused")

    monkeypatch.setattr(postgres, "_driver", lambda: explode)
    with pytest.raises(db.BancoIndisponivel):
        rbac.identidade("felipe")


def test_banco_nao_configurado_levanta_o_erro_proprio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Distinto de "fora do ar": um e' escolha de operacao, o outro e' incidente."""
    monkeypatch.delenv(postgres.ENV_URL, raising=False)
    with pytest.raises(db.BancoNaoConfigurado):
        rbac.identidade("felipe")


def test_a_leitura_de_identidade_e_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolver quem e' a pessoa nao escreve nada — e a transacao READ ONLY faz o servidor
    garantir isso, nao a boa intencao de quem escreveu a consulta."""
    con = _instalar(monkeypatch, [(1, "expansao", "ponto.analisar")])
    rbac.identidade("alguem")
    assert con.executados[0][0] == postgres.SQL_SOMENTE_LEITURA
