"""Administracao de usuarios (D25) — sem tocar banco nenhum.

O que estes testes guardam nao e' o CRUD: e' a trilha. Uma tela de administracao que muda
acesso e nao registra quem mudou reproduz, em outro lugar, o problema que o D19 resolveu para
`perfil_permissoes`. Por isso o foco esta em: o evento sai, sai na MESMA transacao da mudanca,
sai com o autor certo no lugar certo, e nao sai quando nada mudou.

A confusao mais cara possivel aqui e' trocar as duas pessoas de lugar — `id_usuario` e' QUEM
FEZ e `entidade_id` e' QUEM SOFREU (D24). Invertidos, a auditoria continua parecendo correta e
responde exatamente ao contrario. Tem teste proprio.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest

from motor_expansao import db
from motor_expansao.db import postgres
from motor_expansao.db import usuarios as mod

#: (id, login, nome, email, perfil, ativo, criado, atualizado)
LINHA_LISTA = (7, "vinicius", "Vinícius Cruz", "v@ultra.com", "growth", True, None, None)


class FakeConexao:
    """Dublê que responde por PEDAÇO DE SQL, e não por ordem de chamada.

    Casar por ordem tornaria o teste refém do arranjo interno do módulo — trocar duas
    consultas de lugar quebraria o teste sem quebrar o comportamento. Casar pelo SQL
    exercita a mesma coisa que o banco veria.
    """

    def __init__(self, respostas: dict[str, list[tuple[Any, ...]]]) -> None:
        self.respostas = respostas
        self.executados: list[tuple[str, Any]] = []
        self.autocommit = False
        self._ultimo: list[tuple[Any, ...]] = []

    def execute(self, sql: str, params: Any = None) -> FakeConexao:
        self.executados.append((sql, params))
        self._ultimo = []
        for marca, linhas in self.respostas.items():
            if marca in sql:
                self._ultimo = linhas
                break
        return self

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._ultimo

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._ultimo[0] if self._ultimo else None

    # -- ajudas de leitura para os testes -----------------------------------
    def sql_que_contem(self, trecho: str) -> list[tuple[str, Any]]:
        return [(s, p) for s, p in self.executados if trecho in s]

    @property
    def eventos(self) -> list[Any]:
        return [p for s, p in self.executados if "INSERT INTO eventos" in s]


class FakePool:
    def __init__(self, con: FakeConexao) -> None:
        self._con = con

    @contextmanager
    def connection(self):  # type: ignore[no-untyped-def]
        yield self._con

    def open(self, wait: bool = False) -> None: ...
    def close(self) -> None: ...


def _instalar(
    monkeypatch: pytest.MonkeyPatch, respostas: dict[str, list[tuple[Any, ...]]]
) -> FakeConexao:
    con = FakeConexao(respostas)
    monkeypatch.setattr(postgres, "_driver", lambda: (lambda **_k: FakePool(con)))
    monkeypatch.setenv(postgres.ENV_URL, "postgresql://fake/motor")
    return con


@pytest.fixture(autouse=True)
def _limpo() -> Any:
    db.fechar_pool()
    yield
    db.fechar_pool()


def _con_padrao(monkeypatch: pytest.MonkeyPatch, *, perfil: str, ativo: bool) -> FakeConexao:
    return _instalar(
        monkeypatch,
        {
            "FOR UPDATE OF u": [(9, "alvo", perfil, ativo)],
            "FROM perfis WHERE nome_perfil": [(3,)],
        },
    )


# --------------------------------------------------------------------------------------
# Leitura
# --------------------------------------------------------------------------------------


def test_listar_traz_inativos(monkeypatch: pytest.MonkeyPatch) -> None:
    """Esconder quem foi desativado tornaria a REATIVAÇÃO impossível pela tela."""
    inativo = (8, "quem_saiu", "Quem Saiu", "q@ultra.com", "expansao", False, None, None)
    con = _instalar(monkeypatch, {"FROM usuarios u": [LINHA_LISTA, inativo]})
    lista = mod.listar()
    assert [u.ativo for u in lista] == [True, False]
    assert lista[1].login == "quem_saiu"
    # Leitura entra pelo `conexao()`, que abre a transação READ ONLY.
    assert con.sql_que_contem("READ ONLY")


def test_listar_nao_filtra_por_ativo_no_sql() -> None:
    """A cláusula não pode voltar por 'limpeza': o inativo é o caso de uso da tela."""
    assert "WHERE" not in mod.SQL_LISTAR.upper().split("ORDER BY")[0]


# --------------------------------------------------------------------------------------
# Troca de perfil
# --------------------------------------------------------------------------------------


def test_trocar_perfil_grava_de_para_e_carimba_o_autor(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _con_padrao(monkeypatch, perfil="expansao", ativo=True)
    saida = mod.alterar_perfil(9, "growth", autor=7)

    assert saida == {"id_usuario": 9, "de": "expansao", "para": "growth", "mudou": True}
    # O autor é o PRIMEIRO comando da transação — se a escrita falhar, ele cai no rollback.
    assert con.executados[0][0] == postgres.SQL_DEFINIR_AUTOR
    assert con.executados[0][1] == ("7",)

    (evento,) = con.eventos
    autor, tipo, entidade, alvo, metadados = evento
    assert tipo == mod.EVENTO_PERFIL_ALTERADO
    assert metadados.obj == {"de": "expansao", "para": "growth"}


def test_as_duas_pessoas_do_evento_nao_se_invertem(monkeypatch: pytest.MonkeyPatch) -> None:
    """`id_usuario` é quem FEZ; `entidade_id` é quem SOFREU (D24).

    Invertidos, a trilha continua parecendo correta e responde ao contrário — por isso a
    checagem é explícita e os dois ids do teste são diferentes de propósito.
    """
    con = _con_padrao(monkeypatch, perfil="expansao", ativo=True)
    mod.alterar_perfil(9, "growth", autor=7)

    autor, _tipo, entidade, alvo, _metadados = con.eventos[0]
    assert autor == 7, "o autor virou o alvo"
    assert alvo == 9, "o alvo virou o autor"
    assert entidade == mod.ENTIDADE_USUARIO


def test_trocar_para_o_mesmo_perfil_nao_gera_evento(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nada a fazer é sucesso, mas não é mudança — uma linha `de: growth, para: growth`
    polui a auditoria com ruído que parece sinal."""
    con = _con_padrao(monkeypatch, perfil="growth", ativo=True)
    saida = mod.alterar_perfil(9, "growth", autor=7)
    assert saida["mudou"] is False
    assert con.eventos == []
    assert con.sql_que_contem("UPDATE usuarios SET id_perfil") == []


def test_usuario_que_nao_existe_e_404_nao_criacao(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _instalar(monkeypatch, {"FOR UPDATE OF u": []})
    with pytest.raises(mod.UsuarioDesconhecido):
        mod.alterar_perfil(9, "growth", autor=7)
    assert con.sql_que_contem("UPDATE usuarios") == []


def test_perfil_inexistente_nao_escreve(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _instalar(
        monkeypatch,
        {"FOR UPDATE OF u": [(9, "alvo", "expansao", True)], "FROM perfis WHERE nome_perfil": []},
    )
    with pytest.raises(mod.PerfilDesconhecido):
        mod.alterar_perfil(9, "inventado", autor=7)
    assert con.eventos == []


def test_a_linha_do_alvo_e_travada_antes_de_ler(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem `FOR UPDATE`, dois admins na mesma pessoa produzem dois eventos com o MESMO `de`:
    a trilha diria que o perfil saiu de `expansao` duas vezes."""
    con = _con_padrao(monkeypatch, perfil="expansao", ativo=True)
    mod.alterar_perfil(9, "growth", autor=7)
    assert con.sql_que_contem("FOR UPDATE OF u")


# --------------------------------------------------------------------------------------
# Ativar / desativar
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ativo_antes", "pedido", "tipo"),
    [
        (True, False, mod.EVENTO_DESATIVADO),
        (False, True, mod.EVENTO_REATIVADO),
    ],
)
def test_o_evento_certo_para_cada_sentido(
    monkeypatch: pytest.MonkeyPatch, ativo_antes: bool, pedido: bool, tipo: str
) -> None:
    con = _con_padrao(monkeypatch, perfil="expansao", ativo=ativo_antes)
    saida = mod.definir_ativo(9, pedido, autor=7)
    assert saida["mudou"] is True
    assert con.eventos[0][1] == tipo


def test_desativar_e_soft_nunca_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    """`eventos.id_usuario` é `ON DELETE SET NULL`: um DELETE de verdade orfanaria toda a
    autoria da pessoa de uma vez."""
    con = _con_padrao(monkeypatch, perfil="expansao", ativo=True)
    mod.definir_ativo(9, False, autor=7)
    assert con.sql_que_contem("DELETE") == []
    assert con.sql_que_contem("UPDATE usuarios SET ativo")


def test_sem_mudanca_de_status_nao_gera_evento(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _con_padrao(monkeypatch, perfil="expansao", ativo=True)
    assert mod.definir_ativo(9, True, autor=7)["mudou"] is False
    assert con.eventos == []


# --------------------------------------------------------------------------------------
# A trava de auto-alvo
# --------------------------------------------------------------------------------------


def test_ninguem_muda_o_proprio_perfil(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quem se rebaixa por engano perde a tela que usaria para desfazer."""
    con = _con_padrao(monkeypatch, perfil="growth", ativo=True)
    with pytest.raises(mod.AlvoEhOAutor):
        mod.alterar_perfil(7, "expansao", autor=7)
    assert con.executados == [], "a recusa tem de vir ANTES de abrir transação"


def test_ninguem_se_desativa(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auto-desativação derruba a própria sessão, sem ninguém para reverter."""
    _con_padrao(monkeypatch, perfil="growth", ativo=True)
    with pytest.raises(mod.AlvoEhOAutor):
        mod.definir_ativo(7, False, autor=7)


# --------------------------------------------------------------------------------------
# PII
# --------------------------------------------------------------------------------------


def test_metadados_nao_carregam_pii(monkeypatch: pytest.MonkeyPatch) -> None:
    """Convenções §5: nada de nome, e-mail ou login em `metadados` — o id basta, e quem lê
    `eventos` resolve o nome em `usuarios`."""
    con = _con_padrao(monkeypatch, perfil="expansao", ativo=True)
    mod.alterar_perfil(9, "growth", autor=7)
    metadados = con.eventos[0][4].obj
    achatado = " ".join(str(v) for v in metadados.values()).lower()
    for pii in ("@", "vinícius", "alvo"):
        assert pii not in achatado, f"PII em metadados: {metadados}"


def test_o_vocabulario_de_tipo_e_o_do_contrato() -> None:
    """`tipo` fora do `docs/eventos_contrato.md` §2.7 é defeito, não estilo (D11)."""
    assert mod.EVENTO_PERFIL_ALTERADO == "usuario.perfil_alterado"
    assert mod.EVENTO_DESATIVADO == "usuario.desativado"
    assert mod.EVENTO_REATIVADO == "usuario.reativado"
    assert mod.ENTIDADE_USUARIO == "usuario"
