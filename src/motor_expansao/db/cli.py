"""Ferramenta de linha de comando do banco: estado, aplicacao e conferencia.

    python -m motor_expansao.db estado      # o que ja' foi aplicado, o que falta
    python -m motor_expansao.db aplicar     # aplica as pendentes, em ordem, registrando
    python -m motor_expansao.db registrar   # registra migrations cujo efeito JA' esta no banco
    python -m motor_expansao.db conferir    # o banco bate com o que o motor espera?

Quem executa e' o operador
--------------------------
Por decisao de 25/08/2026, nenhum comando SQL parte do desenvolvimento: o banco e' provisionado,
migrado e carregado pelo Vinicius. Este modulo e' a ferramenta que ele usa -- nao um caminho pelo
qual o motor aplica migration sozinho. Nada aqui roda no boot do piloto, nem em requisicao.

Por que a URL do runner NAO e' a do piloto
------------------------------------------
Aplicar migration e' DDL, e o D20 tira DDL do papel `app` justamente para que a aplicacao nao possa
desligar a propria trigger de auditoria. Logo, o runner precisa de uma credencial de DONO do schema,
que o piloto nao tem e nao deve ter. Por isso ele le `MOTOR_DATABASE_URL_ADMIN` PRIMEIRO, e so' cai
para `MOTOR_DATABASE_URL` quando aquela nao existe -- o que e' o caso do banco de teste local, onde
os dois papeis sao a mesma pessoa. Usar a mesma URL em producao anularia o D20 em silencio, e o
`conferir` acusa isso.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import postgres

MIGRACOES = Path(__file__).resolve().parent / "migracoes"
MANIFESTO = MIGRACOES / "manifesto.json"

#: Credencial de DDL. Ver a nota do topo -- o piloto nunca deve usar esta.
ENV_URL_ADMIN = "MOTOR_DATABASE_URL_ADMIN"

SQL_JA_APLICADAS = f"SELECT versao_migracao, hash_migracao FROM {postgres.TABELA_MIGRACOES}"
SQL_REGISTRAR = (
    f"INSERT INTO {postgres.TABELA_MIGRACOES} "
    "(versao_migracao, arquivo_migracao, hash_migracao) VALUES (%s, %s, %s) "
    "ON CONFLICT (versao_migracao) DO NOTHING"
)
SQL_TEM_TABELA_DE_CONTROLE = "SELECT to_regclass(%s) IS NOT NULL"

# Contrato conferido contra o dump do cluster real em 26/08/2026 (§0 da `verificacao.md`).
TABELAS_DO_MODELO = (
    "usuarios", "perfis", "permissoes", "perfil_permissoes", "eventos",
    "areas_estudo", "contratos", "bairros", "distritos", "municipios",
    "perfil_permissoes_historico",
)
NUMEROS_DA_SECAO_ZERO = {
    "indices": 46,   # 33 explicitos + 11 de PK + 2 de UNIQUE (D24 somou os 3 de metadados)
    "constraints CHECK": 12,
    "chaves estrangeiras": 11,
    "triggers": 5,
    "colunas geometricas": 7,
}
#: `prosecdef` e `proconfig` esperados por funcao, apos a migration 011 (D21).
FUNCOES_ESPERADAS = {
    "registra_perfil_permissoes_historico": (True, "pg_catalog, public, pg_temp"),
    "registra_perfil_permissoes_truncate": (True, "pg_catalog, public, pg_temp"),
    "rotulo_perfil": (False, "pg_catalog, public, pg_temp"),
    "rotulo_permissao": (False, "pg_catalog, public, pg_temp"),
    "set_atualizado_em_usuario": (False, "pg_catalog, pg_temp"),
    "set_atualizado_em_area_estudo": (False, "pg_catalog, pg_temp"),
    "set_atualizado_em_contrato": (False, "pg_catalog, pg_temp"),
}

SQL_CONTAGENS = """
WITH modelo(tabela) AS (SELECT unnest(%s::text[]))
SELECT 'tabelas', count(*) FROM pg_tables
  WHERE schemaname = 'public' AND tablename IN (SELECT tabela FROM modelo)
UNION ALL SELECT 'indices', count(*) FROM pg_indexes
  WHERE schemaname = 'public' AND tablename IN (SELECT tabela FROM modelo)
UNION ALL SELECT 'constraints CHECK', count(*) FROM pg_constraint c
  JOIN pg_class t ON t.oid = c.conrelid
  WHERE c.contype = 'c' AND t.relnamespace = 'public'::regnamespace
    AND t.relname IN (SELECT tabela FROM modelo)
UNION ALL SELECT 'chaves estrangeiras', count(*) FROM pg_constraint c
  JOIN pg_class t ON t.oid = c.conrelid
  WHERE c.contype = 'f' AND t.relnamespace = 'public'::regnamespace
    AND t.relname IN (SELECT tabela FROM modelo)
UNION ALL SELECT 'triggers', count(*) FROM pg_trigger tg
  JOIN pg_class t ON t.oid = tg.tgrelid
  WHERE NOT tg.tgisinternal AND t.relname IN (SELECT tabela FROM modelo)
UNION ALL SELECT 'colunas geometricas', count(*) FROM geometry_columns
  WHERE f_table_schema = 'public' AND f_table_name IN (SELECT tabela FROM modelo)
"""
SQL_FUNCOES = """
SELECT p.proname, p.prosecdef, p.proconfig
FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public' AND p.proname = ANY(%s)
"""
SQL_EXTENSOES = "SELECT extname FROM pg_extension WHERE extname = ANY(%s)"


def _url_de_ddl() -> str | None:
    admin = os.environ.get(ENV_URL_ADMIN, "").strip()
    return admin or postgres.url_configurada()


def _manifesto() -> list[dict[str, Any]]:
    if not MANIFESTO.exists():
        raise SystemExit(f"ERRO: manifesto ausente em {MANIFESTO}")
    return json.loads(MANIFESTO.read_text(encoding="utf-8"))["migracoes"]


def _sha256_do_arquivo(nome: str) -> str:
    # `read_text` normaliza fim de linha: o hash tem de ser o mesmo em Windows e Linux,
    # senao a mesma migration pareceria alterada so' por causa do checkout.
    return hashlib.sha256((MIGRACOES / nome).read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def _conectar_para_ddl() -> Any:
    """Conexao com a credencial de DDL, fora do pool read-only do piloto."""
    url = _url_de_ddl()
    if url is None:
        raise SystemExit(
            f"ERRO: defina {ENV_URL_ADMIN} (ou {postgres.ENV_URL}) com a credencial do "
            "DONO do schema -- aplicar migration e' DDL, e o papel `app` do D20 nao a tem."
        )
    try:
        import psycopg
    except ImportError:
        raise SystemExit(
            "ERRO: driver psycopg ausente.\n"
            "  Instale SO' o driver, respeitando o lockfile:\n"
            '    python -m pip install "psycopg[binary,pool]>=3.2,<4" -c constraints.txt\n'
            "  (`pip install -e '.[db]'` tambem resolve, mas NAO use a partir de um worktree: "
            "ele repontaria o pacote instalado e afetaria o checkout principal.)"
        ) from None

    try:
        return psycopg.connect(url)
    except psycopg.OperationalError as erro:
        # Erro ESPERADO numa ferramenta de operador (senha errada, banco inexistente,
        # servidor fora). Traceback aqui nao ajuda ninguem: esconde a linha que importa
        # no meio de sete quadros de pilha. A mensagem do servidor e' preservada, ja' sem
        # a string de conexao -- `_sem_segredo` tira a URL e a senha se elas aparecerem.
        detalhe = postgres._sem_segredo(str(erro).strip())  # noqa: SLF001 - mesma casa
        dicas = (
            "  - senha errada? se ela tem @ : / # ou %, a URL quebra. Tire a senha da URL\n"
            "    e passe por PGPASSWORD, que o libpq le sozinho:\n"
            '      $env:PGPASSWORD = "..."   (PowerShell)\n'
            '      MOTOR_DATABASE_URL="postgresql://postgres@localhost:5432/<banco>"\n'
            "  - o banco existe? CREATE DATABASE <nome> ENCODING 'UTF8';\n"
            "  - o servidor esta no ar e ouvindo na porta 5432?"
        )
        raise SystemExit(f"ERRO: nao consegui conectar.\n{detalhe}\n\nO que conferir:\n{dicas}") from None


def _aplicadas(con: Any) -> dict[str, str]:
    """versao -> hash registrado. Vazio se a tabela de controle ainda nao existe."""
    existe = con.execute(SQL_TEM_TABELA_DE_CONTROLE, (postgres.TABELA_MIGRACOES,)).fetchone()[0]
    if not existe:
        return {}
    return {v: h for v, h in con.execute(SQL_JA_APLICADAS).fetchall()}


def _diagnostico(manifesto: list[dict[str, Any]], aplicadas: dict[str, str]) -> tuple[list, list]:
    """(pendentes, alteradas). `alteradas` e' o defeito que a convencao §7 proibe."""
    pendentes = [m for m in manifesto if m["versao"] not in aplicadas]
    alteradas = [
        m
        for m in manifesto
        if m["versao"] in aplicadas and aplicadas[m["versao"]] != _sha256_do_arquivo(m["arquivo"])
    ]
    return pendentes, alteradas


def _avisar_alteradas(alteradas: list[dict[str, Any]]) -> None:
    if not alteradas:
        return
    print("\nATENCAO -- migrations JA APLICADAS cujo arquivo mudou desde entao:")
    for m in alteradas:
        print(f"  {m['versao']}  {m['arquivo']}")
    print(
        "  A `convencoes.md` §7 proibe editar migration ja' aplicada: o banco esta num estado\n"
        "  que nenhum arquivo descreve. Corrija com uma migration NOVA, nao editando estas."
    )


def cmd_estado(_args: argparse.Namespace) -> int:
    manifesto = _manifesto()
    with _conectar_para_ddl() as con:
        aplicadas = _aplicadas(con)
    pendentes, alteradas = _diagnostico(manifesto, aplicadas)

    print(f"migrations no manifesto: {len(manifesto)}")
    print(f"registradas no banco:    {len(aplicadas)}")
    for m in manifesto:
        marca = "ok " if m["versao"] in aplicadas else "-- "
        print(f"  {marca}{m['versao']}  {m['arquivo']}")
    if pendentes:
        print(f"\npendentes: {', '.join(m['versao'] for m in pendentes)}")
    _avisar_alteradas(alteradas)
    return 0


def cmd_aplicar(args: argparse.Namespace) -> int:
    manifesto = _manifesto()
    with _conectar_para_ddl() as con:
        pendentes, alteradas = _diagnostico(manifesto, _aplicadas(con))
        _avisar_alteradas(alteradas)
        if not pendentes:
            print("nada a aplicar.")
            return 0

        print("a aplicar: " + ", ".join(m["versao"] for m in pendentes))
        if args.simular:
            print("(--simular: nada foi executado)")
            return 0

        for m in pendentes:
            sql = (MIGRACOES / m["arquivo"]).read_text(encoding="utf-8")
            # Uma transacao POR MIGRATION, e nao uma para o lote: se a 007 falhar, a 006
            # continua aplicada e registrada, e reexecutar retoma de onde parou. As
            # proprias migrations ja' trazem BEGIN/COMMIT; o psycopg respeita.
            con.execute(sql)
            con.execute(SQL_REGISTRAR, (m["versao"], m["arquivo"], _sha256_do_arquivo(m["arquivo"])))
            con.commit()
            print(f"  aplicada {m['versao']}  {m['arquivo']}")
    return 0


def cmd_registrar(args: argparse.Namespace) -> int:
    """Registra migrations cujo EFEITO ja' esta no banco, sem reexecuta-las.

    E' o caso do cluster que rodou 001->010 a mao, pelo roteiro do `banco-de-reservas`,
    antes de a tabela de controle existir. Nao aplica nada: so' preenche o registro.
    """
    manifesto = _manifesto()
    ate = args.ate
    alvo = [m for m in manifesto if m["versao"] <= ate]
    if not alvo:
        raise SystemExit(f"ERRO: nenhuma migration ate' a versao {ate!r}")

    with _conectar_para_ddl() as con:
        if not _aplicadas(con) and not con.execute(
            SQL_TEM_TABELA_DE_CONTROLE, (postgres.TABELA_MIGRACOES,)
        ).fetchone()[0]:
            raise SystemExit(
                f"ERRO: a tabela {postgres.TABELA_MIGRACOES} nao existe. Aplique a 000 "
                "primeiro (ela e' a unica que precisa ir a mao, por criar o registro)."
            )
        for m in alvo:
            con.execute(SQL_REGISTRAR, (m["versao"], m["arquivo"], _sha256_do_arquivo(m["arquivo"])))
        con.commit()
    print(f"registradas como aplicadas (sem executar): {', '.join(m['versao'] for m in alvo)}")
    return 0


def cmd_conferir(_args: argparse.Namespace) -> int:
    """O banco tem o que o motor espera encontrar? Le CATALOGO, nunca dado."""
    problemas: list[str] = []
    with _conectar_para_ddl() as con:
        print("== extensoes ==")
        achadas = {e for (e,) in con.execute(SQL_EXTENSOES, (["postgis", "citext"],)).fetchall()}
        for nome in ("postgis", "citext"):
            ok = nome in achadas
            print(f"  {'ok ' if ok else 'FALTA'} {nome}")
            if not ok:
                problemas.append(f"extensao {nome} ausente")

        print("\n== os seis numeros da secao 0 ==")
        contagens = dict(con.execute(SQL_CONTAGENS, (list(TABELAS_DO_MODELO),)).fetchall())
        esperado_tabelas = len(TABELAS_DO_MODELO)
        for item, esperado in [("tabelas", esperado_tabelas), *NUMEROS_DA_SECAO_ZERO.items()]:
            achado = contagens.get(item)
            ok = achado == esperado
            print(f"  {'ok ' if ok else 'DIVERGE'} {item}: {achado} (esperado {esperado})")
            if not ok:
                problemas.append(f"{item}: {achado} != {esperado}")

        print("\n== funcoes e endurecimento (D19/D21) ==")
        encontradas = {
            nome: (secdef, cfg)
            for nome, secdef, cfg in con.execute(
                SQL_FUNCOES, (list(FUNCOES_ESPERADAS),)
            ).fetchall()
        }
        for nome, (secdef_esp, caminho_esp) in FUNCOES_ESPERADAS.items():
            atual = encontradas.get(nome)
            if atual is None:
                print(f"  FALTA {nome}")
                problemas.append(f"funcao {nome} ausente")
                continue
            secdef, cfg = atual
            caminho = (cfg or [""])[0].removeprefix("search_path=")
            ok = secdef == secdef_esp and caminho == caminho_esp
            print(
                f"  {'ok ' if ok else 'DIVERGE'} {nome}: "
                f"security_definer={secdef} search_path={caminho or '(nenhum)'}"
            )
            if not ok:
                problemas.append(f"funcao {nome} sem o endurecimento esperado")

        print("\n== migrations registradas ==")
        aplicadas = _aplicadas(con)
        manifesto = _manifesto()
        pendentes, alteradas = _diagnostico(manifesto, aplicadas)
        print(f"  {len(aplicadas)} de {len(manifesto)} registradas")
        if pendentes:
            faltando = ", ".join(m["versao"] for m in pendentes)
            print(f"  PENDENTES {faltando}")
            problemas.append(f"migrations nao registradas: {faltando}")
            print(
                "  Se o efeito delas JA esta no banco (roteiro aplicado a mao), use:\n"
                f"    python -m motor_expansao.db registrar --ate {manifesto[-1]['versao']}"
            )
        _avisar_alteradas(alteradas)

        print("\n== provisionamento (D20) ==")
        prov = postgres._provisionamento(con)  # noqa: SLF001 - mesma casa, sem API publica ainda
        print(f"  usuario conectado: {prov['usuario']}")
        print(f"  pode escrever direto no historico: {prov['pode_escrever_no_historico']}")
        print(f"  trigger de auditoria: {prov['trigger_auditoria']} (esperado 'A' apos o D20)")
        if prov["pode_escrever_no_historico"]:
            print(
                "  AVISO: este papel tem INSERT direto em perfil_permissoes_historico. Num\n"
                "  cluster de teste isso e' esperado (voce conecta como dono); em PRODUCAO\n"
                "  significa que o D20 nao esta de pe e a auditoria da 009 nao protege nada."
            )

    print()
    if problemas:
        print(f"CONFERENCIA COM {len(problemas)} PROBLEMA(S):")
        for p in problemas:
            print(f"  - {p}")
        return 1
    print("CONFERENCIA OK: o banco tem o que o motor espera.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m motor_expansao.db", description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("estado", help="o que ja' foi aplicado e o que falta").set_defaults(
        funcao=cmd_estado
    )
    p_aplicar = sub.add_parser("aplicar", help="aplica as migrations pendentes, em ordem")
    p_aplicar.add_argument("--simular", action="store_true", help="mostra o que faria, sem aplicar")
    p_aplicar.set_defaults(funcao=cmd_aplicar)

    p_registrar = sub.add_parser(
        "registrar", help="registra migrations cujo efeito ja' esta no banco (sem executar)"
    )
    p_registrar.add_argument("--ate", required=True, help="ultima versao a registrar, ex.: 011")
    p_registrar.set_defaults(funcao=cmd_registrar)

    sub.add_parser("conferir", help="o banco bate com o que o motor espera?").set_defaults(
        funcao=cmd_conferir
    )

    args = parser.parse_args(argv)
    return int(args.funcao(args))


if __name__ == "__main__":
    sys.exit(main())
