"""Fundacao do banco (`motor_expansao.db`) — Marco A da inclusao do banco no motor.

Estes testes NAO tocam banco nenhum, por decisao de 25/08: nenhum comando SQL parte
daqui, e a verificacao contra dado real e' do Vinicius, no cluster dele. O que se prova
aqui e' o que um dublê alcanca — e que e' justamente o que mais quebra na pratica:

  1. o motor sobe e responde SEM banco (env ausente ou driver ausente);
  2. leitura abre a transacao `READ ONLY`, entao o servidor recusa escrita ali dentro;
  3. escrita carimba `app.id_usuario` na transacao, que e' o insumo das triggers de
     auditoria do D19 — sem ele, revogacao de permissao nasce sem autor;
  4. o diagnostico NUNCA levanta e distingue "nao configurado" de "fora do ar".

O que fica fora do alcance destes testes, e por isso e' verificado do outro lado:
sintaxe aceita pelo servidor, tipos e existencia de coluna.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest

from motor_expansao import db
from motor_expansao.db import postgres as mod

# --------------------------------------------------------------------------------------
# Dublês
# --------------------------------------------------------------------------------------


class FakeCursor:
    def __init__(self, linha: tuple[Any, ...] | None) -> None:
        self._linha = linha

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._linha


class FakeConexao:
    """Registra todo SQL executado e responde por correspondencia de prefixo.

    `falhas` simula o que o PostgreSQL faz quando a extensao ou a tabela nao existem —
    e e' o caso que o savepoint do `_primeiro_valor` precisa isolar, senao a consulta
    seguinte morreria com "current transaction is aborted".
    """

    def __init__(
        self,
        respostas: dict[str, tuple[Any, ...]] | None = None,
        falhas: tuple[str, ...] = (),
    ) -> None:
        self.executados: list[tuple[str, Any]] = []
        self._respostas = respostas or {}
        self._falhas = falhas
        #: psycopg3 usa False por padrao; o dublê espelha para a guarda ser exercitada.
        self.autocommit = False

    def execute(self, sql: str, params: Any = None) -> FakeCursor:
        self.executados.append((sql, params))
        for trecho in self._falhas:
            if trecho in sql:
                raise RuntimeError(f'relation/function "{trecho}" does not exist')
        for chave, linha in self._respostas.items():
            if chave in sql:
                return FakeCursor(linha)
        return FakeCursor(None)

    @contextmanager
    def transaction(self):  # type: ignore[no-untyped-def]
        yield self

    def sql_executado(self) -> list[str]:
        return [sql for sql, _ in self.executados]


class FakePool:
    def __init__(self, con: FakeConexao) -> None:
        self._con = con
        self.aberto = False
        self.fechado = False

    @contextmanager
    def connection(self):  # type: ignore[no-untyped-def]
        yield self._con

    def open(self, wait: bool = False) -> None:
        self.aberto = True

    def close(self) -> None:
        self.fechado = True


def _instalar_driver(monkeypatch: pytest.MonkeyPatch, con: FakeConexao) -> FakePool:
    """Troca o `_driver()` do modulo por uma fabrica que devolve o pool falso."""
    pool = FakePool(con)

    def fabrica(**_kwargs: Any) -> FakePool:
        return pool

    monkeypatch.setattr(mod, "_driver", lambda: fabrica)
    monkeypatch.setenv(mod.ENV_URL, "postgresql://fake/motor")
    return pool


@pytest.fixture(autouse=True)
def _pool_limpo() -> Any:
    """O pool e' estado de MODULO: sem isto, um teste herda o dublê do anterior."""
    db.fechar_pool()
    yield
    db.fechar_pool()


# --------------------------------------------------------------------------------------
# 1) O motor sobe sem banco
# --------------------------------------------------------------------------------------


def test_sem_env_o_banco_e_nao_configurado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(mod.ENV_URL, raising=False)
    assert db.url_configurada() is None
    assert db.configurado() is False
    assert mod.ENV_URL in (db.motivo_indisponivel() or "")


def test_env_vazia_conta_como_ausente(monkeypatch: pytest.MonkeyPatch) -> None:
    """String em branco no `.env` e' erro de operacao comum; nao pode virar tentativa
    de conectar a um host vazio, que so' daria timeout obscuro no boot."""
    monkeypatch.setenv(mod.ENV_URL, "   ")
    assert db.url_configurada() is None
    assert db.configurado() is False


def test_driver_ausente_e_um_estado_de_nao_configurado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quem roda os pipelines do M1 nao instala o extra `db`. Isso nao pode ser erro:
    e' o mesmo estado de 'sem banco', e o diagnostico tem de dizer qual dos dois falta."""
    monkeypatch.setenv(mod.ENV_URL, "postgresql://fake/motor")
    monkeypatch.setattr(mod, "_driver", lambda: None)
    assert db.configurado() is False
    assert "psycopg" in (db.motivo_indisponivel() or "")


def test_conexao_sem_banco_levanta_nao_configurado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(mod.ENV_URL, raising=False)
    with pytest.raises(db.BancoNaoConfigurado):
        with db.conexao():
            pass


def test_saude_sem_banco_nao_levanta_e_explica(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(mod.ENV_URL, raising=False)
    estado = db.saude()
    assert estado["configurado"] is False
    assert estado["conectado"] is False
    assert mod.ENV_URL in estado["erro"]


# --------------------------------------------------------------------------------------
# 2) Leitura e' READ ONLY no servidor
# --------------------------------------------------------------------------------------


def test_leitura_abre_transacao_somente_leitura(monkeypatch: pytest.MonkeyPatch) -> None:
    """A garantia nao e' de convencao: e' o servidor que recusa o INSERT.

    Importa porque o guardrail que hoje prova o read-only do piloto e' um snapshot do
    filesystem — e um INSERT nao aparece em snapshot de arquivo.
    """
    con = FakeConexao()
    _instalar_driver(monkeypatch, con)
    with db.conexao() as c:
        c.execute("SELECT 1")
    assert con.sql_executado()[0] == mod.SQL_SOMENTE_LEITURA


def test_leitura_nao_carimba_autor(monkeypatch: pytest.MonkeyPatch) -> None:
    """`app.id_usuario` e' contrato de ESCRITA. Setar na leitura confundiria a auditoria
    sobre quando houve, de fato, uma acao de alguem."""
    con = FakeConexao()
    _instalar_driver(monkeypatch, con)
    with db.conexao():
        pass
    assert not any("set_config" in sql for sql in con.sql_executado())


# --------------------------------------------------------------------------------------
# 3) Escrita carimba o autor
# --------------------------------------------------------------------------------------


def test_escrita_define_o_autor_como_primeiro_comando(monkeypatch: pytest.MonkeyPatch) -> None:
    con = FakeConexao()
    _instalar_driver(monkeypatch, con)
    with db.transacao(id_usuario=42) as c:
        c.execute("INSERT INTO perfil_permissoes VALUES (1, 2)")

    primeiro_sql, primeiro_param = con.executados[0]
    assert primeiro_sql == mod.SQL_DEFINIR_AUTOR
    assert primeiro_param == ("42",)


def test_autor_vai_por_parametro_e_nao_interpolado() -> None:
    """`SET LOCAL app.id_usuario = <valor>` nao aceita placeholder, o que forcaria
    interpolar a variavel na string — injecao esperando acontecer. Por isso o SQL usa
    `set_config(..., true)`, que aceita bind, e o `true` mantem a variavel LOCAL a
    transacao (morre no commit, nao vaza para a proxima requisicao do pool)."""
    assert "%s" in mod.SQL_DEFINIR_AUTOR
    assert "set_config" in mod.SQL_DEFINIR_AUTOR
    assert mod.SQL_DEFINIR_AUTOR.rstrip().endswith("true)")


def test_acao_de_sistema_passa_autor_nulo(monkeypatch: pytest.MonkeyPatch) -> None:
    """O D19 preve autoria nula ('sem ela, a acao e' registrada com autoria nula').
    O que nao pode existir e' autor nulo por ESQUECIMENTO — dai o parametro obrigatorio."""
    con = FakeConexao()
    _instalar_driver(monkeypatch, con)
    with db.transacao(id_usuario=None):
        pass
    assert con.executados[0][1] == (None,)


def test_escrita_exige_o_parametro_de_autor(monkeypatch: pytest.MonkeyPatch) -> None:
    con = FakeConexao()
    _instalar_driver(monkeypatch, con)
    with pytest.raises(TypeError):
        with db.transacao():  # type: ignore[call-arg]
            pass


@pytest.mark.parametrize("valor", ["", "abc", "-1", "1.5", "9" * 19, "1; DROP TABLE x"])
def test_autor_invalido_falha_cedo(monkeypatch: pytest.MonkeyPatch, valor: str) -> None:
    """Mesmo padrao que a trigger do D19 aplica antes do cast (`^[0-9]{1,18}$`).
    Validar aqui troca 'a trigger descartou em silencio' por um erro legivel."""
    con = FakeConexao()
    _instalar_driver(monkeypatch, con)
    with pytest.raises(ValueError):
        with db.transacao(id_usuario=valor):
            pass


# --------------------------------------------------------------------------------------
# 4) Diagnostico
# --------------------------------------------------------------------------------------


def test_saude_com_banco_no_ar(monkeypatch: pytest.MonkeyPatch) -> None:
    con = FakeConexao(
        respostas={
            "server_version": ("17.2",),
            "postgis_version": ("3.6 USE_GEOS=1",),
            f"FROM {mod.TABELA_MIGRACOES}": ("010",),
        }
    )
    _instalar_driver(monkeypatch, con)

    estado = db.saude()
    assert estado["configurado"] is True
    assert estado["conectado"] is True
    assert estado["servidor"] == "17.2"
    assert estado["postgis"].startswith("3.6")
    assert estado["migracao"] == "010"
    assert estado["erro"] is None


def test_saude_sem_tabela_de_migracao_ainda_conecta(monkeypatch: pytest.MonkeyPatch) -> None:
    """Estado REAL do banco levantado a mao pelo roteiro 001->010: o esquema esta la',
    a tabela de controle de migration ainda nao. Isso nao e' falha de conexao."""
    con = FakeConexao(
        respostas={"server_version": ("17.2",), "postgis_version": ("3.6",)},
        falhas=(mod.TABELA_MIGRACOES,),
    )
    _instalar_driver(monkeypatch, con)

    estado = db.saude()
    assert estado["conectado"] is True
    assert estado["migracao"] is None
    assert estado["erro"] is None


def test_falha_de_uma_consulta_nao_derruba_as_outras(monkeypatch: pytest.MonkeyPatch) -> None:
    """No PostgreSQL, um erro aborta a transacao inteira e tudo depois falha com
    'current transaction is aborted'. Sem o savepoint do `_primeiro_valor`, a falta do
    PostGIS levaria embora tambem a versao de migration — dois sintomas por uma causa."""
    con = FakeConexao(
        respostas={"server_version": ("17.2",), f"FROM {mod.TABELA_MIGRACOES}": ("010",)},
        falhas=("postgis_version",),
    )
    _instalar_driver(monkeypatch, con)

    estado = db.saude()
    assert estado["conectado"] is True
    assert estado["postgis"] is None
    assert estado["migracao"] == "010", "o savepoint nao isolou a consulta que falhou"


def test_saude_com_banco_fora_do_ar_reporta_sem_levantar(monkeypatch: pytest.MonkeyPatch) -> None:
    """Distinguir 'nao configurado' de 'fora do ar' e' o ponto: um e' escolha de
    operacao, o outro e' incidente."""
    monkeypatch.setenv(mod.ENV_URL, "postgresql://fake/motor")

    def fabrica_que_explode(**_kwargs: Any) -> Any:
        raise OSError("connection refused")

    monkeypatch.setattr(mod, "_driver", lambda: fabrica_que_explode)

    estado = db.saude()
    assert estado["configurado"] is True
    assert estado["conectado"] is False
    assert "refused" in estado["erro"]


def test_pool_nao_bloqueia_o_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    """`open(wait=False)`: o pool sobe sem esperar conexao. Com `wait=True`, um banco
    fora do ar penduraria a primeira requisicao ate' o timeout — e, no compose, o
    healthcheck derrubaria o container que ainda servia tudo que nao depende de banco."""
    con = FakeConexao()
    pool = _instalar_driver(monkeypatch, con)
    with db.conexao():
        pass
    assert pool.aberto is True


def test_trocar_a_url_recria_o_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem isto, mudar a env em runtime deixaria conexoes apontando para o banco velho."""
    primeira = FakeConexao()
    pool_antigo = _instalar_driver(monkeypatch, primeira)
    with db.conexao():
        pass

    segunda = FakeConexao()
    _instalar_driver(monkeypatch, segunda)
    monkeypatch.setenv(mod.ENV_URL, "postgresql://outro/motor")
    with db.conexao():
        pass

    assert pool_antigo.fechado is True


# --------------------------------------------------------------------------------------
# 5) Correcoes da revisao de integridade (26/08)
# --------------------------------------------------------------------------------------


def test_excecao_do_chamador_nao_vira_banco_indisponivel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regressao do defeito achado na revisao: com o `yield` DENTRO do `try`, o
    `contextlib` relancava no ponto do yield toda excecao do corpo do `with` do chamador,
    e o `except Exception` a convertia. Um `KeyError` da aplicacao virava
    "banco indisponivel" -- confundindo o alerta e, pior, fazendo o texto de uma excecao
    interna arbitraria viajar dentro de uma classe que convida a virar `detail` de 503.
    """
    con = FakeConexao()
    _instalar_driver(monkeypatch, con)

    with pytest.raises(KeyError):
        with db.conexao():
            raise KeyError("defeito da aplicacao, nao do banco")

    with pytest.raises(KeyError):
        with db.transacao(id_usuario=1):
            raise KeyError("defeito da aplicacao, nao do banco")


def test_escrita_em_autocommit_e_barrada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Em autocommit o `set_config(..., true)` roda na transacao implicita e evapora
    antes do INSERT: nenhum erro, e toda a auditoria seguinte sai com autor nulo. Falha
    MUDA — a pior classe — entao vira excecao explicita."""
    con = FakeConexao()
    con.autocommit = True
    _instalar_driver(monkeypatch, con)

    with pytest.raises(db.AutocommitProibido):
        with db.transacao(id_usuario=1):
            pass


def test_timeout_do_diagnostico_vai_bindado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Era o unico SQL montado por f-string num modulo cuja politica e' nao interpolar.
    Nao era explorav1el (o valor passava por `int()`), mas "nao ha caminho" e' garantia
    mais forte que "nao e' explorav1el hoje"."""
    con = FakeConexao(respostas={"server_version": ("18.4",)})
    _instalar_driver(monkeypatch, con)
    db.saude(timeout_s=1.5)

    timeouts = [(sql, par) for sql, par in con.executados if "statement_timeout" in sql]
    assert timeouts, "o diagnostico deixou de limitar o tempo de consulta"
    sql, parametros = timeouts[0]
    assert "%s" in sql and parametros == ("1500ms",)


def test_erro_nao_vaza_a_string_de_conexao(monkeypatch: pytest.MonkeyPatch) -> None:
    """Uma URL malformada faz o parse do libpq levantar com um fragmento da string de
    conexao dentro, e esse texto ia inteiro para o JSON do diagnostico de admin."""
    url = "postgresql://motor:segredo-muito-secreto@localhost:5432/x"
    monkeypatch.setenv(mod.ENV_URL, url)

    def fabrica_que_explode(**_kwargs: Any) -> Any:
        raise OSError(f"could not parse {url}")

    monkeypatch.setattr(mod, "_driver", lambda: fabrica_que_explode)

    estado = db.saude()
    assert estado["conectado"] is False
    assert "segredo-muito-secreto" not in estado["erro"]
    assert url not in estado["erro"]
    assert "OSError" in estado["erro"], "a classe da excecao ainda deve ajudar a diagnosticar"


def test_diagnostico_responde_se_o_provisionamento_esta_de_pe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 009 afirma que o `SECURITY DEFINER` impede a aplicacao de forjar linha no
    historico — mas isso so' vale se quem conecta NAO for o dono do schema. Sem esta
    resposta, um `MOTOR_DATABASE_URL` apontando para o dono derruba a auditoria inteira
    sem sinal nenhum, que e' o caminho de menor resistencia num deploy apressado."""
    con = FakeConexao(
        respostas={
            "server_version": ("18.4",),
            "current_user": ("app",),
            "has_table_privilege": (False,),
            "FROM pg_trigger": ("A",),
        }
    )
    _instalar_driver(monkeypatch, con)

    prov = db.saude()["provisionamento"]
    assert prov["usuario"] == "app"
    assert prov["pode_escrever_no_historico"] is False, (
        "o papel da aplicacao NAO pode ter INSERT direto no historico (D20)"
    )
    assert prov["trigger_auditoria"] == "A", "'A' = ENABLE ALWAYS, o DDL do D20"


def test_diagnostico_denuncia_conexao_como_dono(monkeypatch: pytest.MonkeyPatch) -> None:
    """O estado perigoso tem de ser LEGIVEL: dono do schema, com INSERT direto no
    historico e trigger em modo normal ('O')."""
    con = FakeConexao(
        respostas={
            "server_version": ("18.4",),
            "current_user": ("postgres",),
            "has_table_privilege": (True,),
            "FROM pg_trigger": ("O",),
        }
    )
    _instalar_driver(monkeypatch, con)

    prov = db.saude()["provisionamento"]
    assert prov["usuario"] == "postgres"
    assert prov["pode_escrever_no_historico"] is True
    assert prov["trigger_auditoria"] == "O"
