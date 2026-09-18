"""Toda coluna citada no SQL do motor existe nas migrations. Offline, sem Postgres.

POR QUE ELE EXISTE. O CI nao tem banco (decisao de 25/08), entao nenhuma consulta parte do
desenvolvimento: o `test_migracoes.py` ja' passa o parser real do PostgreSQL em cada
migration, mas **sintaxe valida nao e' coluna existente**. Duas vezes em setembro escrevi
SQL que o parser aceitaria e o banco recusa -- `eventos.id` (a coluna e' `id_evento`) e
`usuarios.email_usuario` (e' `email`) --, e as duas so' apareceram ao rodar contra o banco
real. E' essa distancia que este teste fecha.

COMO. As migrations SAO o esquema: `CREATE TABLE` da' as colunas de nascimento e
`ALTER TABLE ... ADD COLUMN` as que vieram depois (o login na 013, as duas do ciclo da senha
na 016). Com esse mapa em maos, cada instrucao SQL do codigo e' lida pela ARVORE do parser --
nao por texto -- e toda coluna qualificada por tabela ou apelido e' conferida.

O RECORTE E' DELIBERADAMENTE ESTREITO, para o teste nunca virar ruido:

  * tabela DESCONHECIDA nao reprova. `pg_class`, `information_schema`, `geometry_columns` e
    as CTEs do `SQL_CONTAGENS` sao legitimas e nao vivem nas nossas migrations;
  * coluna SEM qualificador so' e' cobrada quando TODAS as tabelas da instrucao sao do
    modelo -- senao um `count(*)` sobre catalogo viraria falso positivo;
  * a clausula de trava e' ignorada. Em `FOR UPDATE OF u`, o parser representa o `u` como
    se fosse uma tabela, usando o APELIDO no `relname`; sem esta excecao, as tres instrucoes
    que travam linha apareceriam com uma tabela fantasma chamada `u`.

O QUE ELE NAO ALCANCA: tipo de coluna, existencia de indice, corpo `plpgsql` e SQL montado
em tempo de execucao. Quem valida isso e' o banco -- e continua sendo.
"""

from __future__ import annotations

import ast as pyast
import re
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[2]
_MIGRACOES = _RAIZ / "src" / "motor_expansao" / "db" / "migracoes"

#: Onde se procura SQL. O pacote `db/` e' a casa dele por guardrail de AST (o `app.py` nao
#: pode ter SQL embutido); `scripts/` entra porque o `rastrear_arquivo.py` consulta `eventos`
#: e `usuarios` por fora da aplicacao -- e foi exatamente ali que um dos dois erros nasceu.
_PASTAS_COM_SQL = (
    _RAIZ / "src" / "motor_expansao" / "db",
    _RAIZ / "scripts",
)

#: Prefixos de tabela que vivem fora das nossas migrations e nao devem ser cobrados.
_FORA_DO_MODELO = ("pg_", "information_schema", "geometry_columns", "spatial_ref_sys")

#: Uma INSTRUCAO, nao uma frase que comeca com palavra-chave. Sem exigir a forma completa,
#: a mensagem de erro `"INSERT em usuarios nao devolveu id"` entraria na varredura e seria
#: reprovada como "sintaxe invalida" -- um texto que nunca foi SQL.
_FORMA_DE_SQL = re.compile(
    r"^\s*(?:SELECT\s|WITH\s|INSERT\s+INTO\s|UPDATE\s+\S+\s+SET\s|DELETE\s+FROM\s)",
    re.IGNORECASE | re.DOTALL,
)

#: Modulos do pacote `db` cujas constantes `SQL_*` sao lidas JA' RESOLVIDAS.
_MODULOS_DE_SQL = ("cli", "eventos", "postgres", "rbac", "usuarios")


def _pglast():
    """O parser real do PostgreSQL, ou `skip` com a razao -- molde do `test_migracoes.py`.

    A DLL nativa (`libpg_query`) e' bloqueada por politica do SO em algumas estacoes, e o
    teste nao pode ficar vermelho por causa disso. Onde ele roda de verdade e' no CI.
    """
    return pytest.importorskip(
        "pglast",
        reason=(
            "pglast indisponivel (nao instalado, ou DLL bloqueada por politica do SO). "
            "O gate roda no CI; localmente, quem valida e' aplicar no banco."
        ),
    )


def _esquema_das_migracoes(pglast) -> dict[str, set[str]]:
    """`tabela -> colunas`, reconstruido do DDL versionado."""
    from pglast import ast as pgast

    esquema: dict[str, set[str]] = {}
    for arquivo in sorted(_MIGRACOES.glob("*.sql")):
        for cru in pglast.parse_sql(arquivo.read_text(encoding="utf-8")):
            no = cru.stmt
            if isinstance(no, pgast.CreateStmt) and no.tableElts:
                esquema.setdefault(no.relation.relname, set()).update(
                    elemento.colname
                    for elemento in no.tableElts
                    if isinstance(elemento, pgast.ColumnDef)
                )
            elif isinstance(no, pgast.AlterTableStmt):
                for comando in no.cmds or ():
                    # Comparado pelo NOME do enum de proposito: `AT_AddColumn` VALE ZERO, e
                    # um `if comando.subtype and ...` curto-circuita em silencio -- as tres
                    # colunas acrescentadas por ALTER sumiriam do mapa, e o teste passaria
                    # a aprovar justamente quem as usa.
                    if getattr(comando.subtype, "name", "") == "AT_AddColumn" and isinstance(
                        comando.def_, pgast.ColumnDef
                    ):
                        esquema.setdefault(no.relation.relname, set()).add(comando.def_.colname)
    return esquema


def _sql_das_constantes() -> list[tuple[str, str]]:
    """As constantes `SQL_*` do pacote `db`, com o valor JA' RESOLVIDO.

    Importar o modulo, em vez de ler o literal do arquivo, e' o que faz a f-string chegar
    inteira: `f"SELECT ... FROM {TABELA_MIGRACOES}"` e' um `JoinedStr` no AST do Python, e o
    pedaco literal dele (`"SELECT ... FROM "`) nao e' instrucao nenhuma -- parseia como SQL
    truncado. Importar nao custa conexao: o pacote so' abre o pool quando alguem consulta.
    """
    import importlib

    achados: list[tuple[str, str]] = []
    for nome in _MODULOS_DE_SQL:
        modulo = importlib.import_module(f"motor_expansao.db.{nome}")
        for chave in sorted(k for k in dir(modulo) if k.startswith("SQL_")):
            valor = getattr(modulo, chave)
            if isinstance(valor, str) and _FORMA_DE_SQL.match(valor):
                achados.append((f"motor_expansao.db.{nome}.{chave}", valor))
    return achados


def _sql_embutido() -> list[tuple[str, str]]:
    """SQL escrito DENTRO de uma funcao, que nunca vira constante -- o caso do rastreio."""
    achados: list[tuple[str, str]] = []
    for pasta in _PASTAS_COM_SQL:
        for arquivo in sorted(pasta.rglob("*.py")):
            if "__pycache__" in arquivo.parts:
                continue
            try:
                arvore = pyast.parse(arquivo.read_text(encoding="utf-8"))
            except SyntaxError:  # pragma: no cover - arquivo quebrado tem teste proprio
                continue
            # Pedaco de f-string nao e' instrucao; quem as resolve e' `_sql_das_constantes`.
            de_fstring = {
                id(parte)
                for no in pyast.walk(arvore)
                if isinstance(no, pyast.JoinedStr)
                for parte in no.values
            }
            for no in pyast.walk(arvore):
                if not isinstance(no, pyast.Constant) or not isinstance(no.value, str):
                    continue
                if id(no) in de_fstring or not _FORMA_DE_SQL.match(no.value):
                    continue
                rotulo = f"{arquivo.relative_to(_RAIZ).as_posix()}:{no.lineno}"
                achados.append((rotulo, no.value.strip()))
    return achados


def _sql_do_codigo() -> list[tuple[str, str]]:
    """As duas fontes, sem repetir a mesma instrucao vinda das duas."""
    vistos: set[str] = set()
    saida: list[tuple[str, str]] = []
    for origem, sql in [*_sql_das_constantes(), *_sql_embutido()]:
        chave = " ".join(sql.split())
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append((origem, sql))
    return saida


def _sem_marcadores(sql: str) -> str:
    """`%s` do psycopg vira `$1`, `$2`... O parser recusa o marcador do driver."""
    contador = 0

    def _trocar(_m: re.Match[str]) -> str:
        nonlocal contador
        contador += 1
        return f"${contador}"

    return re.sub(r"%s", _trocar, sql)


def _referencias(pglast, sql: str) -> tuple[dict[str, str], set[str], list[tuple[str | None, str]]]:
    """`(apelido -> tabela, nomes de CTE, [(qualificador, coluna)])` lidos da arvore."""
    from pglast import ast as pgast
    from pglast.visitors import Visitor

    apelidos: dict[str, str] = {}
    ctes: set[str] = set()
    travadas: set[str] = set()
    colunas: list[tuple[str | None, str]] = []

    class _Coletor(Visitor):
        def visit_RangeVar(self, _ancestrais, no):  # type: ignore[no-untyped-def]
            apelidos.setdefault(no.relname, no.relname)
            if no.alias is not None:
                apelidos[no.alias.aliasname] = no.relname

        def visit_CommonTableExpr(self, _ancestrais, no):  # type: ignore[no-untyped-def]
            ctes.add(no.ctename)

        def visit_LockingClause(self, _ancestrais, no):  # type: ignore[no-untyped-def]
            for travada in no.lockedRels or ():
                travadas.add(travada.relname)

        def visit_ColumnRef(self, _ancestrais, no):  # type: ignore[no-untyped-def]
            partes = [campo.sval for campo in no.fields if isinstance(campo, pgast.String)]
            if partes:
                colunas.append((partes[-2] if len(partes) > 1 else None, partes[-1]))

    for cru in pglast.parse_sql(_sem_marcadores(sql)):
        _Coletor()(cru)

    for nome in travadas | ctes:
        apelidos.pop(nome, None)
    return apelidos, ctes, colunas


# --------------------------------------------------------------------------------------
# As guardas do proprio teste: sem elas, uma varredura vazia passaria como sucesso
# --------------------------------------------------------------------------------------


def test_o_esquema_e_reconstruido_com_as_colunas_de_ALTER() -> None:
    """Se o `ALTER TABLE` sumir do mapa, o teste principal aprova quem usa aquelas colunas.

    As tres sao as que nasceram depois do `CREATE`: o login (013) e o par do ciclo da senha
    (016). Elas existem porque um `ALTER` as acrescentou, e sao exatamente as que um mapa
    montado so' de `CREATE TABLE` perderia.
    """
    pglast = _pglast()
    esquema = _esquema_das_migracoes(pglast)

    assert len(esquema) >= 11, f"poucas tabelas reconstruidas: {sorted(esquema)}"
    for coluna in ("login_usuario", "senha_definida_em_usuario", "deve_trocar_senha_usuario"):
        assert coluna in esquema["usuarios"], f"{coluna} (de ALTER TABLE) faltou no mapa"
    assert "id_evento" in esquema["eventos"]


def test_a_varredura_acha_o_sql_do_codigo() -> None:
    """Guarda contra passar em branco: varredura vazia nao prova nada."""
    achados = _sql_do_codigo()
    assert len(achados) >= 25, f"varredura achou so' {len(achados)} instrucoes"
    origens = {origem for origem, _ in achados}
    assert any(o.startswith("motor_expansao.db.usuarios.SQL_") for o in origens)
    # O script de rastreio consulta o banco por FORA da aplicacao, e foi onde um dos dois
    # erros de coluna nasceu -- se ele sair do recorte, o teste perde o caso que o motivou.
    assert any(o.startswith("scripts/rastrear_arquivo.py") for o in origens), sorted(origens)


# --------------------------------------------------------------------------------------
# O teste
# --------------------------------------------------------------------------------------


def test_toda_coluna_qualificada_existe_na_tabela() -> None:
    """`u.email_usuario` e `e.id` sao sintaxe VALIDA e coluna INEXISTENTE. Aqui reprovam."""
    pglast = _pglast()
    esquema = _esquema_das_migracoes(pglast)

    problemas: list[str] = []
    for origem, sql in _sql_do_codigo():
        try:
            apelidos, _ctes, colunas = _referencias(pglast, sql)
        except Exception as erro:  # noqa: BLE001 - o proprio parser define o tipo
            problemas.append(f"{origem}: nao parseou ({type(erro).__name__}: {erro})")
            continue

        tabelas = set(apelidos.values())
        do_modelo = {t for t in tabelas if t in esquema}
        desconhecidas = {
            t for t in tabelas if t not in esquema and not t.startswith(_FORA_DO_MODELO)
        }

        for qualificador, coluna in colunas:
            if qualificador is not None:
                alvo = apelidos.get(qualificador)
                if alvo in esquema and coluna not in esquema[alvo]:
                    problemas.append(f"{origem}: {qualificador}.{coluna} nao existe em {alvo}")
            elif do_modelo and not desconhecidas and not tabelas - do_modelo:
                # Sem qualificador, so' se TODAS as tabelas sao do modelo -- senao um
                # `count(*)` sobre catalogo viraria falso positivo.
                if not any(coluna in esquema[t] for t in do_modelo):
                    problemas.append(f"{origem}: coluna {coluna} nao existe em {sorted(do_modelo)}")

    assert not problemas, "SQL citando coluna que as migrations nao criam:\n  " + "\n  ".join(
        problemas
    )
