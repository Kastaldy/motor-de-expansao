"""Ferramenta de linha de comando do banco: estado, aplicacao e conferencia.

    python -m motor_expansao.db estado      # o que ja' foi aplicado, o que falta
    python -m motor_expansao.db aplicar     # aplica as pendentes, em ordem, registrando
    python -m motor_expansao.db registrar   # registra migrations cujo efeito JA' esta no banco
    python -m motor_expansao.db conferir    # o banco bate com o que o motor espera?
    python -m motor_expansao.db privilegios # o papel `app` e' mesmo incapaz do que nao deve

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
# Quantas tabelas o `public` tem que NAO sao de extensao. Serve a uma pergunta so':
# "registradas: 0" significa banco NOVO, ou banco com objetos e sem o registro?
#
# `NOT EXISTS ... deptype = 'e'` nao e' zelo: `CREATE EXTENSION postgis` cria
# `spatial_ref_sys` no `public`, e a 001 e' `CREATE EXTENSION IF NOT EXISTS`, entao
# banco com postgis instalado ANTES das migrations e' estado legitimo. Medido em
# 05/10/2026: `pg_tables` cru devolve 1 nesse banco, e esta consulta devolve 0 --
# contar o cru faria o portao recusar quem nao fez nada de errado.
SQL_TABELAS_FORA_DE_EXTENSAO = (
    "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
    "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') "
    "AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype = 'e')"
)

# Contrato conferido contra o dump do cluster real em 26/08/2026 (§0 da `verificacao.md`).
TABELAS_DO_MODELO = (
    "usuarios",
    "perfis",
    "permissoes",
    "perfil_permissoes",
    "eventos",
    "areas_estudo",
    "contratos",
    "bairros",
    "distritos",
    "municipios",
    "perfil_permissoes_historico",
    "sessoes",
)
NUMEROS_DA_SECAO_ZERO = {
    "indices": 49,  # 35 explicitos + 12 de PK + 2 de UNIQUE (a 018/D30 somou 2 + o dela de PK)
    "constraints CHECK": 14,  # a 018 (D30) e a 019: `ck_usuarios_prazo_exige_troca`
    "chaves estrangeiras": 12,  # a 018 (D30): `sessoes.id_usuario`
    "triggers": 7,  # 5 ate' a 016; a 017 (D29) somou a guarda de coerencia nas duas regioes
    "colunas geometricas": 7,
}
#: `prosecdef` e `proconfig` esperados por funcao, apos a migration 011 (D21) e a 017 (D29).
FUNCOES_ESPERADAS = {
    "registra_perfil_permissoes_historico": (True, "pg_catalog, public, pg_temp"),
    "registra_perfil_permissoes_truncate": (True, "pg_catalog, public, pg_temp"),
    "rotulo_perfil": (False, "pg_catalog, public, pg_temp"),
    "rotulo_permissao": (False, "pg_catalog, public, pg_temp"),
    "set_atualizado_em_usuario": (False, "pg_catalog, pg_temp"),
    "set_atualizado_em_area_estudo": (False, "pg_catalog, pg_temp"),
    "set_atualizado_em_contrato": (False, "pg_catalog, pg_temp"),
    # D29: recusa UPDATE que muda a definicao da regiao sem gravar a forma nova. NAO e'
    # SECURITY DEFINER de proposito -- ela so' levanta excecao, nao escreve nada.
    "exige_geom_coerente": (False, "pg_catalog, pg_temp"),
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
    return hashlib.sha256(
        (MIGRACOES / nome).read_text(encoding="utf-8").encode("utf-8")
    ).hexdigest()


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

    return _conectar_com_diagnostico(psycopg, url)


def _conectar_com_diagnostico(psycopg: Any, url: str) -> Any:
    """Conecta traduzindo a falha em mensagem util.

    Toda entrada do CLI passa por aqui. Ficou como funcao propria porque a primeira
    versao do `privilegios` chamou `psycopg.connect` direto e devolveu traceback de sete
    quadros onde devia haver uma linha -- o mesmo defeito que este bloco ja' consertava
    para o runner, repetido por nao ser reusavel.
    """
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
        raise SystemExit(
            f"ERRO: nao consegui conectar.\n{detalhe}\n\nO que conferir:\n{dicas}"
        ) from None


def _aplicadas(con: Any) -> dict[str, str]:
    """versao -> hash registrado. Vazio se a tabela de controle ainda nao existe."""
    existe = con.execute(SQL_TEM_TABELA_DE_CONTROLE, (postgres.TABELA_MIGRACOES,)).fetchone()[0]
    if not existe:
        return {}
    return {v: h for v, h in con.execute(SQL_JA_APLICADAS).fetchall()}


def _objetos_sem_registro(con: Any) -> int:
    """Tabelas proprias no `public` quando a tabela de controle NAO existe; 0 se existe.

    `_aplicadas` devolve `{}` tanto para banco virgem quanto para banco povoado sem o
    registro, e a tela imprimia "registradas: 0" nos dois -- saida IDENTICA byte a byte,
    medido em 05/10/2026. Esse era o unico portao do unico passo declarado sem volta: o
    `aplicar` aceitava, commitava a 000 e a 001 e morria na 002 com `DuplicateTable`.
    """
    existe = con.execute(SQL_TEM_TABELA_DE_CONTROLE, (postgres.TABELA_MIGRACOES,)).fetchone()[0]
    if existe:
        return 0
    return con.execute(SQL_TABELAS_FORA_DE_EXTENSAO).fetchone()[0]


def _recado_do_banco_povoado(quantas: int) -> str:
    return (
        f"o banco tem {quantas} tabela(s) no schema `public` e NAO tem a tabela de controle\n"
        "  `migracoes_aplicadas`. Entao `registradas: 0` aqui nao quer dizer \"banco novo\":\n"
        "  quer dizer \"o registro nao existe\". Aplicar tudo commitaria as primeiras\n"
        "  migrations e morreria em `DuplicateTable` na primeira que recria objeto.\n"
        "\n"
        "  Se o EFEITO das migrations ja' esta no banco (roteiro aplicado a mao, restore que\n"
        "  perdeu o registro), o caminho e' registrar sem executar:\n"
        "      python -m motor_expansao.db registrar --ate <a ultima que ja' esta de pe>\n"
        "  Se nao esta, o banco nao e' o que voce pensa que e': confira o nome em\n"
        "  MOTOR_DATABASE_URL antes de qualquer coisa."
    )


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
        _sem_registro = _objetos_sem_registro(con)
    pendentes, alteradas = _diagnostico(manifesto, aplicadas)

    print(f"migrations no manifesto: {len(manifesto)}")
    print(f"registradas no banco:    {len(aplicadas)}")
    if _sem_registro:
        print(f"\nATENCAO -- {_recado_do_banco_povoado(_sem_registro)}")
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
        # O portao, ANTES de qualquer DDL. Recusar aqui custa um comando; descobrir
        # depois custa um banco com duas migrations commitadas e o resto fora do
        # registro -- e migration nao tem desfazer.
        _sem_registro = _objetos_sem_registro(con)
        if _sem_registro:
            raise SystemExit(f"ERRO: {_recado_do_banco_povoado(_sem_registro)}")
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
            con.execute(
                SQL_REGISTRAR, (m["versao"], m["arquivo"], _sha256_do_arquivo(m["arquivo"]))
            )
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
        if (
            not _aplicadas(con)
            and not con.execute(
                SQL_TEM_TABELA_DE_CONTROLE, (postgres.TABELA_MIGRACOES,)
            ).fetchone()[0]
        ):
            raise SystemExit(
                f"ERRO: a tabela {postgres.TABELA_MIGRACOES} nao existe. Aplique a 000 "
                "primeiro (ela e' a unica que precisa ir a mao, por criar o registro)."
            )
        for m in alvo:
            con.execute(
                SQL_REGISTRAR, (m["versao"], m["arquivo"], _sha256_do_arquivo(m["arquivo"]))
            )
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
            for nome, secdef, cfg in con.execute(SQL_FUNCOES, (list(FUNCOES_ESPERADAS),)).fetchall()
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
        for _n, _e in sorted((prov.get("triggers_auditoria") or {}).items()):
            print(f"  trigger {_n}: {_e} (esperado 'A' apos o D20)")

        # O estado da trigger ENTRA na conta dos problemas; o `pode_escrever_no_historico`
        # NAO. Os dois sao sinais do D20, mas de naturezas diferentes, e confundi-los era o
        # defeito: ate' 02/10/2026 este comando IMPRIMIA os dois e nao contava nenhum, e
        # entao `CONFERENCIA OK` com codigo 0 saia igual num banco com a auditoria de pe e
        # num banco sem ela. Quem le a ultima linha -- que e' o que se faz -- aprovava os dois.
        #
        # Por que a assimetria e' correta:
        #   `pode_escrever_no_historico` depende de QUEM CONECTA (`has_table_privilege` do
        #   papel atual). Num ensaio local conecta-se como dono, e dono escreve mesmo: ali
        #   `True` e' esperado e nao e' defeito. E' o que o AVISO abaixo explica.
        #
        #   `trigger_auditoria` depende do BANCO, nao de quem conecta. 'A' (ENABLE ALWAYS) e'
        #   o unico pedaco de DDL do D20, e e' o que resiste a `session_replication_role =
        #   replica` -- que deixou de exigir superusuario no PG15, ou seja, esta' ao alcance
        #   de um papel comum. Nao existe cenario em que 'O' seja aceitavel: em TODO ponto em
        #   que o runbook manda rodar este comando (o §8 da VPS e o ensaio do §1), a secao 7
        #   do script de papeis ja' rodou. Logo, reprovar aqui nao reprova ensaio legitimo.
        # TODAS as triggers da tabela auditada, nao so' a primeira. Ate' 05/10/2026 este
        # veredito olhava um nome unico, e um §7 colado pela METADE -- a de TRUNCATE em
        # 'O' -- passava verde aqui E no `privilegios`. Medido.
        _todas = prov.get("triggers_auditoria") or {}
        if not _todas:
            problemas.append(
                "nenhuma trigger de auditoria em `perfil_permissoes`: ou a migration 009 nao "
                "esta aplicada, ou `pg_trigger` nao foi legivel -- sem elas o historico de "
                "permissoes nao existe"
            )
        for _nome, _estado in sorted(_todas.items()):
            if _estado != "A":
                problemas.append(
                    f"trigger `{_nome}` em '{_estado}', nao 'A': o `ENABLE ALWAYS` do D20 nao "
                    f"foi aplicado nela. Rode a secao 7 do `papeis-e-privilegios.md` INTEIRA -- "
                    f"ela tem DUAS linhas `ALTER TABLE`, e colar so' a primeira deixa esta aqui "
                    f"em 'O'. Em 'O' a trigger e' PULADA por uma sessao em "
                    f"`session_replication_role = replica`, que no PG15+ nao exige superusuario "
                    f"-- o historico de permissoes fica contornavel em silencio"
                )

        if prov["pode_escrever_no_historico"]:
            print(
                # Ate' 05/10/2026 esta mensagem dizia "em PRODUCAO significa que o D20
                # nao esta de pe". E' falso: `has_table_privilege` responde por QUEM
                # CONECTOU, o dono sempre tem INSERT na propria tabela, e o §8 do
                # `banco_deploy.md` manda rodar esta verificacao com a credencial de DDL
                # -- isto e', como dono, na VPS. O aviso disparava sempre, inclusive num
                # banco perfeito, e a frase ensinava a ler isso como D20 caido.
                "  AVISO: o papel que CONECTOU aqui tem INSERT direto em\n"
                "  perfil_permissoes_historico. Se voce conectou como dono (e o §8 manda\n"
                "  conectar assim, com a credencial de DDL), isto e' esperado e nao diz nada\n"
                "  sobre o D20. O alarme de verdade e' este mesmo sinal sair VERDADEIRO\n"
                "  conectado como `app`: e' o que o comando `privilegios` mede."
            )

    print()
    if problemas:
        print(f"CONFERENCIA COM {len(problemas)} PROBLEMA(S):")
        for p in problemas:
            print(f"  - {p}")
        return 1
    print("CONFERENCIA OK: o banco tem o que o motor espera.")
    return 0


# ---------------------------------------------------------------------------------------
# `privilegios` — a reposicao do guardrail READ-ONLY (F6.2)
#
# O piloto provava ser read-only de duas formas: AST sobre o `app.py` e snapshot do
# filesystem em runtime. A segunda parou de valer no dia em que ele ganhou banco: um
# `INSERT` nao aparece em snapshot de arquivo. A prova nao FALHOU -- ela deixou de
# cobrir, sem avisar, que e' o pior jeito de uma rede de seguranca sumir.
#
# O que a repoe nao e' outro teste de codigo: e' o PRIVILEGIO. Com o D20 de pe, a escrita
# indevida deixa de ser improvavel e passa a ser impossivel -- o papel nao tem como. Este
# comando e' o que prova isso contra o banco real, do lado de dentro da mesma credencial
# que o piloto usa.
#
# TUDO AQUI E' LEITURA DE CATALOGO (`has_*_privilege`, `pg_class`, `pg_parameter_acl`).
# Nenhuma checagem tenta escrever para ver se falha: isso deixaria lixo, dependeria de
# rollback e, num banco com auditoria append-only, a propria tentativa vira linha.
# ---------------------------------------------------------------------------------------


def _checagens_negativas() -> list[tuple[str, str, str]]:
    """(rotulo, SQL -> bool, por que importa). `True` = o papel PODE = FALHA."""
    return [
        (
            "criar objeto no schema public",
            "SELECT has_schema_privilege(current_user, 'public', 'CREATE')",
            "DDL no papel da aplicacao anula o D20: quem cria tabela cria trigger, e quem "
            "cria trigger na propria tabela desliga a auditoria",
        ),
        (
            "escrever no historico de permissoes",
            "SELECT has_table_privilege(current_user, 'perfil_permissoes_historico', 'INSERT') "
            "OR has_any_column_privilege(current_user, 'perfil_permissoes_historico', 'INSERT')",
            "o D19 promete que a aplicacao nao forja linha de auditoria; com INSERT direto a "
            "promessa e' so' prosa",
        ),
        (
            "apagar sessao",
            "SELECT has_table_privilege(current_user, 'sessoes', 'DELETE')",
            "revogar e' `UPDATE` de `revogada_em_sessao`, NUNCA `DELETE` -- apagar a linha "
            "destruiria a resposta de 'quando esta sessao foi encerrada', e o expurgo de "
            "retencao tambem anonimiza em vez de apagar. `DELETE` aqui significa que o "
            "`papeis-e-privilegios.md` foi afrouxado sem que a decisao acompanhasse",
        ),
        (
            "alterar o historico de permissoes",
            "SELECT has_table_privilege(current_user, 'perfil_permissoes_historico', 'UPDATE') "
            "OR has_any_column_privilege(current_user, 'perfil_permissoes_historico', 'UPDATE')",
            "append-only: reescrever o passado e' pior que apaga-lo, porque nao deixa buraco",
        ),
        (
            "apagar do historico de permissoes",
            "SELECT has_table_privilege(current_user, 'perfil_permissoes_historico', 'DELETE')",
            "mesma razao do UPDATE",
        ),
        (
            "esvaziar perfil_permissoes",
            "SELECT has_table_privilege(current_user, 'perfil_permissoes', 'TRUNCATE')",
            "o TRUNCATE tem trigger propria (D19), mas conceder o privilegio e' convidar o "
            "caminho que ela existe para vigiar",
        ),
        (
            "alterar evento ja' gravado",
            "SELECT has_table_privilege(current_user, 'eventos', 'UPDATE') "
            "OR has_any_column_privilege(current_user, 'eventos', 'UPDATE')",
            "`eventos` e' append-only por contrato (§4) -- e e' onde a tela de administracao "
            "grava quem mudou o acesso de quem",
        ),
        (
            "apagar evento",
            "SELECT has_table_privilege(current_user, 'eventos', 'DELETE')",
            "mesma razao do UPDATE em eventos",
        ),
        (
            "criar tabela temporaria",
            "SELECT has_database_privilege(current_user, current_database(), 'TEMP')",
            "era o caminho da forja que a revisao de 26/08 achou: TEMP TABLE propria + funcao "
            "SECURITY DEFINER da 009 = linha forjada com o privilegio do dono (D21)",
        ),
        (
            "ser dono das tabelas auditadas",
            "SELECT bool_or(c.relowner = (SELECT oid FROM pg_roles WHERE rolname = current_user)) "
            # `relnamespace` e' obrigatorio: sem ele uma tabela homonima noutro
            # schema entra na conta, e `bool_or` devolve `true` dizendo que o papel e'
            # dono da juncao auditada quando a de `public` esta' certa. Medido.
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname IN "
            "('perfil_permissoes', 'perfil_permissoes_historico', 'eventos')",
            "dono desliga a propria trigger com um ALTER TABLE, e nenhum GRANT protege contra isso",
        ),
        (
            "nenhum papel comum recebe SET em session_replication_role",
            # `has_parameter_privilege` do papel CONECTADO, nao `EXISTS` sobre o
            # catalogo: `pg_parameter_acl` e' COMPARTILHADO pelo cluster, e o `EXISTS`
            # acusava concessao feita em outro banco a outro papel -- medido em
            # 06/10/2026, saindo `exit 1` com o diagnostico errado.
            postgres.SQL_PARAMETRO_DA_SESSAO,
            "desde o PG15 esse GRANT existe, e quem o recebe desliga TODAS as triggers da "
            "sessao -- o `ENABLE ALWAYS` da §7 do D20 e' a defesa, este e' o alarme",
        ),
    ]


def _checagens_positivas() -> list[tuple[str, str, str]]:
    """(rotulo, SQL -> bool, por que importa). `False` = o piloto QUEBRA em runtime."""
    return [
        # PRIMEIRA de proposito: sem `USAGE` no schema, o papel nao VE as tabelas, e as
        # dezesseis checagens seguintes degradam para "o objeto nao existe (migration
        # pendente?)" -- diagnostico errado num banco com as migrations todas aplicadas.
        # Quem le o relatorio de cima para baixo encontra a causa antes do sintoma.
        (
            "usar o schema public",
            postgres.SQL_USAGE_NO_SCHEMA,
            "a seccao 2 do D20 concede `USAGE ON SCHEMA public`, e sem ele o privilegio de "
            "TABELA continua no catalogo mas o papel nao enxerga a tabela: a aplicacao morre "
            "com `relation \"usuarios\" does not exist`, que parece migration faltando. Se "
            "esta linha falhar, IGNORE os `PEND` abaixo e rode o `GRANT USAGE` da seccao 2",
        ),
        (
            "gravar evento",
            "SELECT has_table_privilege(current_user, 'eventos', 'INSERT')",
            "sem isto nenhuma acao e' registrada, e o D17 nao fecha",
        ),
        (
            "usar a sequence de eventos",
            "SELECT has_sequence_privilege(current_user, 'eventos_id_evento_seq', 'USAGE')",
            "GRANT INSERT na tabela NAO cobre a sequence do BIGSERIAL -- sem esta, todo "
            "INSERT morre por permissao negada, e so' em runtime",
        ),
        # As TRES abaixo entraram em 05/10/2026. O script de papeis concede USAGE em CINCO
        # sequences e este comando testava DUAS (eventos e sessoes) -- entao faltar qualquer
        # uma das outras tres passava VERDE aqui, verde no `conferir` e verde na conferencia
        # de 12/1/3 (que le `role_table_grants`, onde privilegio de sequence nao mora).
        #
        # A de `usuarios` e' a pior: `SQL_CRIAR` nao passa `id_usuario`, depende do BIGSERIAL.
        # Sem o USAGE nela, NENHUMA pessoa e' criada pela tela de administracao -- e e' esse
        # o passo que entrega o piloto a equipe. Medido num banco de ensaio: revogando so'
        # essa sequence, `privilegios`, `conferir` e a conferencia de linhas passaram todos.
        (
            "usar a sequence de usuarios",
            "SELECT has_sequence_privilege(current_user, 'usuarios_id_usuario_seq', 'USAGE')",
            "sem esta, criar pessoa pela tela morre em runtime: o INSERT do motor nao passa "
            "`id_usuario` e depende do BIGSERIAL. E' a sequence que o passo 9 do repasse usa",
        ),
        (
            "usar a sequence de areas_estudo",
            "SELECT has_sequence_privilege(current_user, "
            "'areas_estudo_id_area_estudo_seq', 'USAGE')",
            "mesma armadilha: `GRANT INSERT` em areas_estudo nao cobre a sequence dela",
        ),
        (
            "usar a sequence de contratos",
            "SELECT has_sequence_privilege(current_user, 'contratos_id_contrato_seq', 'USAGE')",
            "mesma armadilha: `GRANT INSERT` em contratos nao cobre a sequence dela",
        ),
        (
            "atualizar usuarios",
            "SELECT has_table_privilege(current_user, 'usuarios', 'UPDATE')",
            "e' o que a tela de administracao faz: trocar perfil e ativar/desativar",
        ),
        (
            "ler spatial_ref_sys",
            "SELECT has_table_privilege(current_user, 'spatial_ref_sys', 'SELECT')",
            "sem ela o PostGIS quebra ao tocar `geography` -- e o erro aparece longe daqui",
        ),
        # As duas de `sessoes` (D30) entraram em 23/09/2026, e a lacuna que fechavam era
        # SILENCIOSA E GRAVE: este comando existe para provar o D20, e passava VERDE mesmo com
        # a tabela `sessoes` sem `GRANT` nenhum para o `app`.
        #
        # E esse cenario nao e' hipotetico em producao. O `ALTER DEFAULT PRIVILEGES` do
        # `papeis-e-privilegios.md` §6 diz `FOR ROLE postgres`, e vale so' para objetos criados
        # por AQUELE papel -- mas o dono do schema em producao e' `reservas_owner`
        # (`docs/banco_deploy.md`). Logo a `sessoes`, criada pela migration 018, NAO herda
        # privilegio, e o sintoma so' apareceria no dia em que a autenticacao propria fosse
        # ligada: `permission denied for table sessoes`, com todo mundo fora da plataforma.
        # O proprio documento nomeia a armadilha ("as tabelas novas nascem sem GRANT e ninguem
        # percebe"); faltava alguem PERGUNTAR.
        (
            "escrever em sessoes",
            "SELECT has_table_privilege(current_user, 'sessoes', 'INSERT') "
            "AND has_table_privilege(current_user, 'sessoes', 'UPDATE') "
            "AND has_table_privilege(current_user, 'sessoes', 'SELECT')",
            "sem isto o login nao abre sessao e ninguem entra depois do corte do P19",
        ),
        (
            "usar a sequence de sessoes",
            "SELECT has_sequence_privilege(current_user, 'sessoes_id_sessao_seq', 'USAGE')",
            "mesma armadilha da sequence de eventos: `GRANT INSERT` na tabela NAO a cobre, e "
            "o login morre so' em runtime",
        ),
    ]


#: Sentinela de "o objeto que esta checagem pergunta ainda nao existe no banco". Nao e' `False`
#: de proposito: `False` significa "o papel NAO pode", e confundir as duas coisas faria o relatorio
#: acusar privilegio faltando quando o que falta e' a MIGRATION.
AUSENTE = object()


def _valor_unico(con: Any, sql: str) -> Any:
    """Primeira coluna da primeira linha, ou `AUSENTE` se o objeto perguntado nao existe.

    POR QUE A TOLERANCIA, e ela e' estreita de proposito: `has_table_privilege('sessoes', ...)`
    LEVANTA quando a tabela nao existe, em vez de devolver falso. Rodar este comando contra um
    banco que ainda nao recebeu a 018 -- o que e' natural, para ver o estado antes de aplicar --
    derrubava tudo com `UndefinedTable` e um traceback cru, no meio do relatorio. Medido em
    25/09/2026 contra um banco real sem a 018.

    So' `UndefinedTable`/`UndefinedObject` sao absorvidos, e viram uma LINHA PROPRIA no relatorio.
    Qualquer outro erro continua subindo: engolir erro de banco num comando que existe para
    atestar seguranca seria trocar um susto por uma mentira.

    `None` segue significando "a consulta nao devolveu linha", que aqui e' resposta legitima
    (ex.: `bool_or` sobre zero linhas).
    """
    import psycopg

    try:
        linha = con.execute(sql).fetchone()
    except (psycopg.errors.UndefinedTable, psycopg.errors.UndefinedObject):
        # A transacao fica abortada depois do erro; sem o rollback, TODA checagem seguinte
        # falharia com `InFailedSqlTransaction` e o relatorio mentiria sobre o resto.
        con.rollback()
        return AUSENTE
    return None if linha is None else linha[0]


def cmd_privilegios(_args: argparse.Namespace) -> int:
    """O papel do piloto e' mesmo incapaz do que nao deve? Le catalogo, nunca escreve."""
    url = postgres.url_configurada()
    if url is None:
        raise SystemExit(
            f"ERRO: defina {postgres.ENV_URL} com a credencial do PILOTO (papel `app`).\n"
            "  Este comando checa o papel que a aplicacao usa -- conferir com a credencial\n"
            "  de DONO nao prova nada, porque o dono pode tudo."
        )

    import psycopg

    problemas: list[str] = []
    with _conectar_com_diagnostico(psycopg, url) as con:
        quem = _valor_unico(con, postgres.SQL_USUARIO_ATUAL)
        print(f"papel conectado: {quem}\n")

        print("== o que este papel NAO pode ==")
        for rotulo, sql, porque in _checagens_negativas():
            bruto = _valor_unico(con, sql)
            if bruto is AUSENTE:
                # Objeto ausente nao e' privilegio indevido: nao ha' o que o papel possa fazer
                # numa tabela que nao existe. Entra no relatorio para o operador saber, e NAO
                # entra em `problemas`.
                print(f"  --    {rotulo}: o objeto nao existe (migration pendente?)")
                continue
            pode = bool(bruto)
            # Uma checagem negativa pode devolver BOOLEANO ou a LISTA de quem pode. A
            # segunda forma entrou em 07/10/2026, com a pergunta do `session_replication_role`
            # passando a olhar os tres papeis do D20 em vez do conectado: sem o detalhe, o
            # relatorio diria que alguem pode e nao diria quem.
            detalhe = bruto if isinstance(bruto, str) and bruto else ""
            print(f"  {'FALHA' if pode else 'ok   '} {rotulo}"
                  f"{': ' + detalhe if detalhe else ''}")
            if pode:
                print(f"        por que importa: {porque}")
                problemas.append(rotulo + (': ' + detalhe if detalhe else ''))

        print("\n== o que este papel PRECISA poder ==")
        for rotulo, sql, porque in _checagens_positivas():
            bruto = _valor_unico(con, sql)
            if bruto is AUSENTE:
                # AQUI entra em `problemas`, mas com a causa CERTA: o piloto de fato nao vai
                # conseguir o que precisa -- so' que por falta de migration, nao de `GRANT`.
                # Dizer "FALHA" mandaria o operador conferir o provisionamento, que esta' certo.
                print(f"  PEND  {rotulo}: o objeto nao existe -- aplique as migrations antes")
                problemas.append(f"{rotulo} (migration pendente)")
                continue
            pode = bool(bruto)
            print(f"  {'ok   ' if pode else 'FALHA'} {rotulo}")
            if not pode:
                print(f"        por que importa: {porque}")
                problemas.append(rotulo)

        # A DECIMA classe, SEXTA porta: `PUBLIC` em ACL de TABELA.
        #
        # A secao 3 do script faz dois `REVOKE ... FROM PUBLIC` em tabela -- ela trata
        # `PUBLIC`-em-tabela como ameaca que precisa fechar -- e nada conferia se fechou.
        # Medido em 07/10/2026: `GRANT DELETE ON perfil_permissoes_historico TO PUBLIC`
        # deixa as quinze conferencias manuais do pacote IDENTICAS ao estado bom, e o `app`
        # faz `DELETE` de 15 linhas na tabela append-only. As consultas que fecham as
        # outras cinco portas excluiam `PUBLIC` por construcao (`a.grantee <> 0`).
        publico_tab = con.execute(postgres.SQL_ACL_DE_PUBLIC_EM_TABELA).fetchone()[0]
        print(
            f"  {'ok   ' if not publico_tab else 'FALHA'} PUBLIC nao tem privilegio de tabela "
            f"no schema{'' if not publico_tab else ': ' + publico_tab}"
        )
        if publico_tab:
            print(
                "        por que importa: PUBLIC vale para TODO papel, inclusive os tres do\n"
                "        D20 -- e nao aparece na contagem 12/1/3 nem em nenhuma consulta que\n"
                "        filtre por nome, porque PUBLIC nao e' nome nenhum."
            )
            problemas.append("PUBLIC tem privilegio de tabela no schema: " + publico_tab)
        # A PORTA PRINCIPAL, que nunca teve consulta de universo derivado (07/10/2026).
        #
        # Medido: `GRANT SELECT ON perfil_permissoes_historico TO consultor` saia
        # `PRIVILEGIOS OK` exit 0, com a contagem por papel IDENTICA ao estado bom, e o
        # `consultor` lendo as 79 linhas do historico append-only com senha propria.
        #
        # Aqui nomear os tres e' CORRETO, e a diferenca importa: nas perguntas negativas
        # a lista de nomes e' o furo, porque o universo e' aberto; esta pergunta e'
        # POSITIVA sobre o conjunto provisionado -- "quem tem ACL no schema sao exatamente
        # os tres do D20" --, e ai a lista e' a especificacao. Qualquer quarto nome e'
        # achado por definicao. Ela fecha tambem o privilegio de SEQUENCE a quem nao
        # devia, que as duas consultas de sequence (pelo papel conectado) nao veem.
        alheio = con.execute(postgres.SQL_PAPEIS_COM_ACL_NO_SCHEMA).fetchone()[0]
        print(
            f"  {'ok   ' if not alheio else 'FALHA'} so' os papeis do D20 tem ACL no "
            f"schema{'' if not alheio else ': ' + alheio}"
        )
        if alheio:
            print(
                "        por que importa: um GRANT direto a um papel de nome qualquer\n"
                "        nao move a contagem por papel (ela filtra os tres nomes) e nao\n"
                "        e' PUBLIC, entao nenhuma das outras conferencias o ve -- e o\n"
                "        papel entra com senha propria e le o que o D20 existe para\n"
                "        proteger."
            )
            problemas.append("papel alheio tem ACL no schema public: " + alheio)
        # A DECIMA classe, segunda porta: privilegio de COLUNA.
        #
        # Medido: `GRANT UPDATE (id_perfil) ON usuarios TO auditoria` deixa a contagem
        # 12/1/3 intacta, as doze conferencias manuais do pacote identicas ao estado bom,
        # e o `auditoria` troca o perfil de qualquer pessoa. `relacl` nao tem essa
        # concessao -- ela vive em `pg_attribute.attacl`, que ninguem lia.
        #
        # Esta checagem olha OUTROS papeis, nao so' o conectado, como a da setima classe:
        # concessao de coluna a quem nao e' dono nao faz parte do desenho do D20 em
        # nenhuma tabela, entao qualquer linha aqui e' achado.
        colunas = con.execute(postgres.SQL_PRIVILEGIO_DE_COLUNA).fetchone()[0]
        print(
            f"  {'ok   ' if not colunas else 'FALHA'} ninguem tem privilegio de COLUNA no "
            f"schema{'' if not colunas else ': ' + colunas}"
        )
        if colunas:
            print(
                "        por que importa: privilegio de coluna nao entra em `relacl` nem na\n"
                "        contagem 12/1/3 -- e `UPDATE` numa coluna basta para trocar o perfil de\n"
                "        uma pessoa sem passar por `perfil_permissoes`, que e' onde a auditoria olha."
            )
            problemas.append("privilegio de COLUNA concedido no schema: " + colunas)
        # A DECIMA classe (07/10/2026): PERTENCIMENTO nao cria entrada de ACL.
        #
        # Medido: `privilegios` saiu `PRIVILEGIOS OK`, exit 0, com `GRANT pg_write_all_data
        # TO auditoria` (e aí o `auditoria` faz `DELETE` na tabela append-only) e com
        # `GRANT etl TO app` (e aí o `app` faz `TRUNCATE` nas tres de referencia). Nenhuma
        # conferencia via: nem `relacl`, nem `role_table_grants`, nem a lista nominal de
        # `has_table_privilege` -- porque o privilegio nao esta' em ACL nenhuma, esta' na
        # arvore de papeis.
        #
        # A regra e' simples e deriva tudo: o papel que conectou NAO pertence a papel
        # nenhum. Isso fecha os papeis predefinidos que ainda nao existem, e fecha o
        # pertencimento entre os tres do D20, sem lista de nomes perigosos.
        pertence = con.execute(postgres.SQL_PAPEIS_DE_QUEM_CONECTOU).fetchone()[0]
        print(
            f"  {'ok   ' if not pertence else 'FALHA'} nenhum papel comum pertence a papel "
            f"nenhum{'' if not pertence else ': ' + pertence}"
        )
        if pertence:
            print(
                "        por que importa: pertencimento NAO cria entrada de ACL, entao a\n"
                "        contagem 12/1/3, a coluna de privilegios e as checagens nominais acima\n"
                "        ficam TODAS intactas -- e o papel consegue o que o papel-mae consegue.\n"
                "        a checagem olha `pg_auth_members` inteiro, nao so' quem tem ACL no\n"
                "        schema: uma cadeia de dois niveis passava por fora do universo da ACL."
            )
            problemas.append(
                "o papel conectado pertence a outro(s) papel(eis): " + pertence
            )
        # SEQUENCES, nos DOIS sentidos e sem lista (06/10/2026). As cinco checagens
        # nomeadas acima cobrem o sentido `INSERT sem USAGE` para cinco das oito
        # sequences; esta cobre as OITO e tambem o sentido oposto, que nenhum
        # instrumento olhava: `USAGE` numa sequence cuja tabela o papel nao pode
        # inserir e' privilegio excedente -- medido, `GRANT USAGE ON ALL SEQUENCES`
        # passava `conferir`, `privilegios` e a contagem 12/1/3 os tres verdes.
        #
        # A regra deriva de `pg_depend`: o `USAGE` tem de CASAR com o `INSERT` na
        # tabela que possui a sequence. Medido nas oito: casa em todas no estado bom.
        desalinhadas = con.execute(postgres.SQL_SEQUENCES_DESALINHADAS).fetchone()[0]
        print(
            f"  {'ok   ' if not desalinhadas else 'FALHA'} o USAGE de cada sequence casa com o "
            f"INSERT na tabela dela{'' if not desalinhadas else ': ' + desalinhadas}"
        )
        if desalinhadas:
            print(
                "        por que importa: `INSERT` sem `USAGE` mata a escrita em runtime, e\n"
                "        `USAGE` sem `INSERT` e' privilegio que ninguem precisa -- e nenhuma das\n"
                "        duas aparece na contagem 12/1/3, que le `role_table_grants`."
            )
            problemas.append(
                "sequence com USAGE desalinhado do INSERT da tabela: " + desalinhadas
            )
        # A SETIMA classe (06/10/2026): a secao 2 endurece contra PUBLIC, e todo
        # instrumento aqui pergunta pelo papel CONECTADO. Medido: com `CREATE` no schema
        # para o `etl` e `TEMPORARY` no banco para `auditoria` e `etl`, tudo ficava verde
        # e o `etl` criava tabela. Esta pergunta e' pelo UNIVERSO, nao por `current_user`.
        abertos = con.execute(postgres.SQL_PODERES_ABERTOS_NO_SCHEMA).fetchone()[0]
        print(
            f"  {'ok   ' if not abertos else 'FALHA'} ninguem alem do dono cria objeto no "
            f"schema nem tabela temporaria{'' if not abertos else ': ' + abertos}"
        )
        if abertos:
            print(
                "        por que importa: a secao 2 revoga os dois de `PUBLIC`, e revogar de\n"
                "        PUBLIC vale para TODOS os papeis -- inclusive os que nao conectam aqui.\n"
                "        Quem cria objeto no schema instala trigger na propria tabela; quem cria\n"
                "        tabela temporaria tem o caminho da forja do D21. Recole a secao 2."
            )
            problemas.append(
                "poder que a secao 2 revoga de PUBLIC esta aberto: " + abertos
            )

        # A SEXTA classe (06/10/2026): papel comum com poder de cluster. A secao 1 do
        # script endurece os atributos, e nada conferia -- medido, com `etl LOGIN` e
        # `app CREATEDB CREATEROLE` tudo ficava verde. Dono excluido por SER dono, nao por
        # nome: sem isso a consulta acusava o proprio `reservas_owner`.
        #
        # O UNIVERSO deixou de ser `relacl` em 07/10/2026. Medido: `CREATE ROLE intruso
        # LOGIN SUPERUSER` saia `PRIVILEGIOS OK` exit 0 -- a consulta perguntava por
        # `rolsuper` corretamente e nunca via o papel, porque quem ainda nao recebeu GRANT
        # nao esta em `relacl`. Pior: com o universo antigo, `ALTER ROLE quarto SUPERUSER`
        # APAGAVA o achado `quarto (CREATEROLE)` que a consulta ja' tinha produzido, porque
        # o `NOT rolsuper` da outra metade o excluia. Agora o SUPERUSER SOMA:
        # `quarto (SUPERUSER, CREATEROLE)`.
        poderosos = con.execute(postgres.SQL_PAPEIS_COM_PODER_DE_CLUSTER).fetchone()[0]
        print(
            f"  {'ok   ' if not poderosos else 'FALHA'} nenhum papel comum tem poder de "
            f"cluster{'' if not poderosos else ': ' + poderosos}"
        )
        if poderosos:
            print(
                "        por que importa: `CREATEDB`, `CREATEROLE` e `SUPERUSER` anulam o D20 por\n"
                "        fora -- quem cria papel se concede o que quiser, e superusuario ignora\n"
                "        toda ACL e toda trigger. A secao 1 cria os tres SEM nenhum deles."
            )
            problemas.append("papel comum com poder de cluster: " + poderosos)

        # DERIVADA: todo papel com privilegio de tabela/sequence no schema precisa de
        # `USAGE` nele. A checagem positiva acima pergunta so' por `current_user`, e a
        # secao 2 concede o `USAGE` a TRES papeis -- entao o `auditoria` podia perder o
        # dele e tudo ficava verde, inclusive este comando. Medido em 05/10/2026.
        sem_usage = con.execute(postgres.SQL_PAPEIS_SEM_USAGE_NO_SCHEMA).fetchone()[0]
        _sem = [p for p in (sem_usage or "").split(",") if p]
        print(
            f"  {'ok   ' if not _sem else 'FALHA'} todo papel com privilegio no schema tem "
            f"USAGE nele{'' if not _sem else ': ' + ', '.join(_sem) + ' NAO tem'}"
        )
        if _sem:
            print(
                "        por que importa: privilegio de tabela sem `USAGE` no schema e' INERTE --\n"
                "        o catalogo diz que o papel pode, e a consulta falha com\n"
                "        `relation ... does not exist`, que parece migration ausente. A secao 2\n"
                "        concede o USAGE aos TRES papeis; rode o `GRANT USAGE` dela de novo."
            )
            problemas.append(
                "papel com privilegio de tabela e sem USAGE no schema: "
                + ", ".join(_sem)
                + " (o privilegio esta' no catalogo e nao funciona)"
            )

        print("\n== auditoria endurecida (D21) ==")
        # Antes de qualquer consulta derivada: a tabela auditada e' VISIVEL? As tres
        # consultas abaixo derivam do catalogo por `to_regclass`, que devolve NULL em vez
        # de levantar -- mas NULL faria as tres dizerem "nao ha trigger nenhuma", que e'
        # diagnostico errado. Ate' 05/10/2026 elas usavam `::regclass` e ESTOURAVAM com
        # `psycopg.errors.UndefinedTable` e traceback cru; medido com o USAGE do schema
        # revogado. Era defeito meu, contra a disciplina do sentinela AUSENTE.
        visivel = con.execute(
            postgres.SQL_TABELA_AUDITADA_VISIVEL, (postgres.TABELA_AUDITADA,)
        ).fetchone()[0]
        if not visivel:
            print(
                f"  --    {postgres.TABELA_AUDITADA} nao e' visivel para este papel: "
                "ou a migration 009 nao rodou, ou falta `USAGE` no schema `public`"
            )
            print(
                "        as tres checagens do D21 ficam sem objeto. Olhe a linha "
                "`usar o schema public` acima: se ela falhou, a causa e' o USAGE, nao a "
                "migration."
            )
            problemas.append(
                f"{postgres.TABELA_AUDITADA} invisivel: as checagens do D21 nao foram feitas "
                "(veja `usar o schema public`)"
            )
            visivel = False
        # TODAS as triggers nao-internas da tabela auditada, DERIVADAS do catalogo. Ate'
        # 05/10/2026 isto olhava um nome unico (`trg_perfil_permissoes_auditoria`) e a secao 7
        # endurece DUAS -- entao colar so' a primeira das duas linhas `ALTER TABLE` deixava a
        # de TRUNCATE em 'O' e este comando dizia PRIVILEGIOS OK. Medido. E §7 colado pela
        # metade e' exatamente o desfecho da interrupcao que o runbook antecipa.
        linhas = con.execute(
            postgres.SQL_TRIGGERS_AUDITORIA, (postgres.TABELA_AUDITADA,)
        ).fetchall() if visivel else []
        triggers = {linha[0]: linha[1] for linha in linhas}
        if not triggers and visivel:
            print(f"  FALHA nenhuma trigger nao-interna em {postgres.TABELA_AUDITADA}")
            print(
                "        por que importa: sem as triggers da 009 o historico de permissoes nao\n"
                "        existe. Ou a migration nao esta aplicada, ou alguem as removeu."
            )
            problemas.append(f"nenhuma trigger de auditoria em {postgres.TABELA_AUDITADA}")
        for nome, atual in sorted(triggers.items()):
            ok = atual == "A"
            print(f"  {'ok   ' if ok else 'FALHA'} trigger {nome}: {atual!r} (esperado 'A')")
            if not ok:
                print(
                    "        por que importa: fora de 'A', uma sessao em session_replication_role="
                    "replica\n        escreve sem deixar rastro. E' o ALTER TABLE da secao 7 do "
                    "D20 -- e ela tem DUAS linhas."
                )
                problemas.append(f"trigger {nome} fora de ENABLE ALWAYS")

        # A SEGUNDA camada da secao 2, que nenhum instrumento olhava ate' 05/10/2026.
        # Universo derivado das triggers acima (`tgfoid`): as outras funcoes do modelo
        # tem EXECUTE para PUBLIC legitimamente, e cobrar `false` nelas seria falso
        # alarme.
        acl = con.execute(
            postgres.SQL_ACL_FUNCOES_DE_AUDITORIA, (postgres.TABELA_AUDITADA,)
        ).fetchall() if visivel else []
        for nome, publico_executa in acl:
            ok = not publico_executa
            print(
                f"  {'ok   ' if ok else 'FALHA'} funcao {nome}: PUBLIC executa="
                f"{bool(publico_executa)} (esperado False)"
            )
            if not ok:
                print(
                    "        por que importa: e' a segunda das duas camadas contra instalar a\n"
                    "        trigger de auditoria em outra tabela. O `REVOKE EXECUTE` da secao 2\n"
                    "        do D20 nao esta de pe, ou alguem devolveu o GRANT depois."
                )
                problemas.append(f"PUBLIC pode executar {nome}: falta o REVOKE EXECUTE da secao 2")

        # A QUARTA camada: o `ALTER DEFAULT PRIVILEGES` da secao 6. Pergunta DERIVADA --
        # o dono da tabela auditada aparece entre os papeis do `pg_default_acl`? Papel
        # EXTRA nao reprova; o que reprova e' o dono AUSENTE, que e' o no-op do
        # `FOR ROLE postgres`. Medido: no-op puro faz tabela futura nascer invisivel ao
        # `app`, e `conferir`, `privilegios` e a contagem 12/1/3 passavam os tres verdes.
        _dono = con.execute(
            postgres.SQL_DONO_DA_TABELA_AUDITADA, (postgres.TABELA_AUDITADA,)
        ).fetchone()[0] if visivel else None
        _usuario = con.execute(postgres.SQL_USUARIO_ATUAL).fetchone()[0] if visivel else None
        _acl = {
            linha[0]: (linha[1], linha[2], linha[3])
            for linha in (con.execute(postgres.SQL_DEFAULT_ACL_DO_DONO).fetchall() if visivel else [])
        }
        # UMA linha por tipo de objeto. Agregar TABLES e SEQUENCES esconde a lacuna:
        # medido em 05/10/2026, com o grantee errado so' em TABLES e as SEQUENCES
        # intactas, o agregado mostrava o papel certo e o comando passava verde.
        for _tipo, _nome in sorted(postgres.TIPOS_DO_DEFAULT_ACL.items()):
            if _tipo not in _acl:
                if visivel:
                    print(f"  FALHA default privileges de {_nome}: NENHUM")
                    print(
                        "        por que importa: sem esta linha, todo objeto desse tipo criado\n"
                        "        daqui para frente nasce invisivel para a aplicacao. Rode a secao 6."
                    )
                    problemas.append(f"pg_default_acl sem linha de {_nome}: a secao 6 nao rodou")
                continue
            _criam, _recebem, _chega = _acl[_tipo]
            _ok = bool(_dono) and _dono in (_criam or "").split(",") and bool(_chega)
            print(
                f"  {'ok   ' if _ok else 'FALHA'} default privileges de {_nome}: criados por "
                f"{_criam or 'NENHUM'} -> concedidos a {_recebem or 'NENHUM'} "
                f"(esperado: {_dono or '?'} -> {_usuario or '?'}, direto ou por heranca)"
            )
            if not _ok:
                print(
                    "        por que importa: o default privilege tem de ser criado PELO DONO e\n"
                    "        chegar A QUEM CONECTA. Errar qualquer um dos dois faz todo objeto desse\n"
                    "        tipo criado daqui para frente nascer invisivel para a aplicacao, e os\n"
                    "        dois jeitos de errar passam a secao 6 sem um erro na tela:\n"
                    "        `FOR ROLE postgres` (no-op silencioso se o papel existir) e\n"
                    "        `TO <papel errado>`."
                )
                problemas.append(
                    f"pg_default_acl de {_nome} errado: criados por {_criam or 'nada'}, concedidos a "
                    f"{_recebem or 'nada'}, esperado {_dono or '?'} -> {_usuario or '?'}"
                )

    print()
    if problemas:
        print(f"PRIVILEGIOS COM {len(problemas)} PROBLEMA(S):")
        for p in problemas:
            print(f"  - {p}")
        print(
            "\nSe o papel conectado for o DONO do schema, e' esperado que quase tudo falhe --\n"
            "rode de novo com a URL do papel `app`. Se ja' for o `app`, o provisionamento do\n"
            "D20 (sql/papeis-e-privilegios.md) nao esta completo."
        )
        return 1
    print(
        "PRIVILEGIOS OK: o papel do piloto nao consegue o que nao deve, e consegue o que precisa."
    )
    return 0


def cmd_expurgar(args: argparse.Namespace) -> int:
    """Zera a ORIGEM das sessoes alem do prazo de retencao (P15, fechado em 23/09/2026).

    ANONIMIZA, nao apaga: o que tem prazo e' o dado pessoal (`ip_sessao`,
    `user_agent_sessao`), nao o registro da sessao. Zeradas as duas colunas, a linha continua
    respondendo "esta pessoa entrou em tal dia, revogada em tal outro" -- auditoria sem PII.
    Apagar a linha contrariaria o desenho da 018, onde revogar e' `UPDATE` e nunca `DELETE`.

    E' IDEMPOTENTE: rodar duas vezes seguidas nao reescreve nada na segunda, porque o `WHERE`
    exige pelo menos uma das colunas preenchida. Isso torna o `rowcount` honesto -- ele diz
    quanto FOI expurgado agora, e nao quantas linhas sao velhas.

    Roda pelo DONO do schema (a mesma credencial das migrations): e' escrita de manutencao,
    fora do RBAC de usuario, e o papel `app` nao precisa deste poder.
    """
    from . import sessoes

    dias = sessoes.RETENCAO_ORIGEM_DIAS
    with _conectar_para_ddl() as con:
        (pendentes,) = con.execute(sessoes.SQL_CONTAR_ORIGEM_VENCIDA, (dias,)).fetchone()
        print(f"retencao da origem: {dias} dias")
        print(f"sessoes com origem alem do prazo: {pendentes}")
        if args.simular:
            print("(--simular: nada foi escrito)")
            return 0
        if not pendentes:
            print("nada a expurgar")
            return 0
        cursor = con.execute(sessoes.SQL_EXPURGAR_ORIGEM, (dias,))
        quantas = getattr(cursor, "rowcount", 0)
        # COMMIT EXPLICITO, como `cmd_aplicar` e `cmd_registrar`. O `with` do psycopg3 ja'
        # commitaria na saida limpa, mas este era o UNICO comando do CLI que dependia disso --
        # e a inconsistencia e' o problema: uma troca futura de `with` por `connect()/close()`
        # faria o cron imprimir "anonimizadas: N" com ROLLBACK silencioso. Numa politica de
        # retencao, relatar remocao que nao aconteceu e' o pior desfecho possivel.
        con.commit()
        print(f"  anonimizadas: {quantas}")
    return 0


def classificar_para_alinhar(
    linhas: list[tuple[int, str, str | None, str]],
    confere_com_a_inicial,
) -> dict[str, list[tuple[int, str]]]:
    """Separa as linhas de `SQL_ESTADO_DA_SENHA_INICIAL` nas QUATRO classes do alinhamento.

    FUNCAO PROPRIA, e nao um laco dentro do comando, por um motivo de COBERTURA: o CI nao tem
    Postgres (`.github/workflows/ci.yml` roda `pytest -q` e nao sobe servico de banco), e o
    unico teste do `alinhar-senhas` era de integracao -- pulava sem banco. Ou seja, o comando
    que se roda contra o banco de PRODUCAO, no passo que o runbook chama de o unico que nao da'
    para desfazer, chegava a' VPS sem uma linha de verificacao automatica. Extraida, a decisao
    inteira vira testavel sem banco nenhum.

    `confere_com_a_inicial` entra por parametro (e nao `senhas.verificar` direto) para o teste
    poder exercitar as quatro classes sem pagar Argon2 -- que custa ~100 ms por chamada.

    As classes, e por que so' uma e' segura de reescrever:
      `propria_ok`       -> escolheu senha, hash valido. Nada a fazer.
      `propria_quebrada` -> escolheu senha, hash invalido. RELATAR: consertar apagaria a senha
                            que ela escolheu, e isso e' decisao de gente.
      `sem_propria_ok`   -> na inicial, e o hash JA' confere. Nada a fazer -- e' esta classe que
                            torna a contagem honesta e o comando idempotente.
      `sem_propria`      -> na inicial, e o hash NAO confere. E' a unica que se reescreve.
    """
    por_classe: dict[str, list[tuple[int, str]]] = {
        "sem_propria_ok": [],
        "sem_propria": [],
        "propria_quebrada": [],
        "propria_ok": [],
    }
    for id_usuario, login, hash_atual, classe in linhas:
        if classe == "sem_propria" and confere_com_a_inicial(hash_atual):
            classe = "sem_propria_ok"
        por_classe[classe].append((id_usuario, login))
    return por_classe


def cmd_alinhar_senhas(args: argparse.Namespace) -> int:
    """Regrava o hash da senha INICIAL em quem nunca escolheu a propria.

    PARA QUE ISTO EXISTE. O hash de cada pessoa foi gravado no momento da CRIACAO, a partir da
    `MOTOR_SENHA_INICIAL` de entao. Se a env mudou depois, ou se a linha nasceu por SQL a mao,
    a pessoa NAO ENTRA quando o motor passar a autenticar. Enquanto o Authelia autentica isso e'
    inofensivo -- a coluna nao abre porta nenhuma --, e no dia do corte vira gente trancada,
    descoberta uma a uma pelo telefone. Este comando e' o passo de PREPARACAO do corte.

    SO' MEXE EM QUEM NUNCA ESCOLHEU SENHA, e o recorte e' a parte importante. Para essas pessoas
    a senha inicial compartilhada E' a senha delas, entao regravar nao lhes tira nada. Quem
    ESCOLHEU a propria e esta' com hash quebrado e' apenas RELATADO: consertar significaria
    apagar a senha que ela escolheu, e isso e' decisao de gente. O dono do banco, que escolheu a
    senha dele, nunca e' tocado.

    UM SAL POR PESSOA, e nao um hash reaproveitado. `hash_da_senha_inicial()` e' chamada uma vez
    POR LINHA de proposito: com o mesmo hash em todas, duas linhas iguais anunciariam no dump
    exatamente quem ainda esta' na senha compartilhada -- e `deve_trocar_senha_usuario` ja'
    responde isso de forma honesta, para quem tem direito de ver. Custa ~100 ms por pessoa.

    E' IDEMPOTENTE, e isso custa um `verificar` por pessoa: quem nao escolheu senha tem o hash
    CONFERIDO contra a inicial antes de entrar na lista. Sem essa conferencia o comando diria
    "20 seriam alinhadas" tanto num banco quebrado quanto num banco ja' certo, e rodar duas vezes
    nao distinguiria "funcionou" de "nao fez nada".

    NAO GRAVA EVENTO, e a razao e' a mesma do `cmd_expurgar`: roda pelo DONO do schema, fora do
    RBAC de usuario, e nao ha' usuario logado para carimbar como autor (`eventos.id_usuario` tem
    FK). O registro deste ato e' o runbook (`docs/repasse_corte_p19.md`) e a saida deste comando
    -- que por isso NOMEIA cada pessoa tocada, em vez de so' contar.
    """
    from . import senhas, usuarios

    # A env ANTES do banco: sem ela nao ha' o que gravar, e a mensagem de `senha_inicial()`
    # diz exatamente o que fazer. Descobrir isso depois de abrir a conexao so' atrasaria o erro.
    try:
        senhas.senha_inicial()
    except senhas.SenhaInicialNaoConfigurada as erro:
        print(f"ERRO: {erro}")
        return 1
    if not senhas.disponivel():
        print("ERRO: argon2-cffi nao esta instalado neste ambiente (extra `auth`).")
        return 1

    with _conectar_para_ddl() as con:
        linhas = con.execute(
            usuarios.SQL_ESTADO_DA_SENHA_INICIAL, (senhas.PREFIXO_PHC + "%",)
        ).fetchall()

    inicial = senhas.senha_inicial()
    # QUEM NAO ESCOLHEU SENHA AINDA PRECISA SER CONFERIDO, e esse `verificar` e' o que faz a
    # contagem deste comando ser HONESTA. Sem ele, "20 seriam alinhadas" sai igual num banco
    # com 20 hashes quebrados e num com 20 ja' corretos -- e quem roda duas vezes nao
    # distingue "funcionou" de "nao fez nada". Mesma exigencia que o `cmd_expurgar` documenta.
    # A decisao mora em `classificar_para_alinhar`, que tem teste sem banco.
    por_classe = classificar_para_alinhar(
        list(linhas), lambda h: senhas.verificar(inicial, h)
    )

    print(f"usuarios ativos: {len(linhas)}")
    print(f"  ja' escolheram a propria senha, hash ok : {len(por_classe['propria_ok'])}")
    print(f"  na senha inicial e JA' CONFEREM         : {len(por_classe['sem_propria_ok'])}")
    print(f"  na senha inicial e NAO conferem         : {len(por_classe['sem_propria'])}")
    print(f"  escolheram, mas o hash esta' QUEBRADO   : {len(por_classe['propria_quebrada'])}")

    if por_classe["propria_quebrada"]:
        print()
        print("ATENCAO -- estas pessoas NAO entram depois do corte, e este comando NAO as toca:")
        for _id, login in por_classe["propria_quebrada"]:
            print(f"    {login}")
        print("  Elas escolheram uma senha e o hash dela nao e' valido. Consertar significa")
        print("  APAGAR a senha escolhida, entao a decisao e' de quem administra: redefina cada")
        print("  uma pela tela de Acessos (senha temporaria, 2 h) ou combine outra saida.")

    alvos = por_classe["sem_propria"]
    if not alvos:
        print()
        print("nada a alinhar")
        return 0

    if args.simular:
        print()
        print("(--simular: nada foi escrito) seriam alinhadas:")
        for _id, login in alvos:
            print(f"    {login}")
        return 0

    print()
    with _conectar_para_ddl() as con:
        for id_usuario, login in alvos:
            # Uma chamada por linha: sal proprio (ver o docstring).
            con.execute(usuarios.SQL_ALINHAR_SENHA_INICIAL, (senhas.hash_da_senha_inicial(), id_usuario))
            print(f"  alinhada: {login}")
        # COMMIT EXPLICITO, pelo mesmo motivo do `cmd_expurgar`: este e' o unico ponto onde o
        # comando escreve, e depender do `with` faria uma troca futura por `connect()/close()`
        # imprimir "alinhada: <login>" com ROLLBACK silencioso. Relatar credencial gravada que
        # nao foi e' o pior desfecho possivel -- a pessoa descobre no dia do corte.
        con.commit()
    print()
    print(f"ALINHADAS: {len(alvos)}. Elas entram com a MOTOR_SENHA_INICIAL e a tela vai")
    print("convidar cada uma a trocar no primeiro acesso.")
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

    sub.add_parser(
        "privilegios",
        help="o papel `app` e' mesmo incapaz do que nao deve? (usa MOTOR_DATABASE_URL)",
    ).set_defaults(funcao=cmd_privilegios)

    p_expurgar = sub.add_parser(
        "expurgar",
        help="zera ip/user-agent das sessoes alem do prazo de retencao (P15)",
    )
    p_expurgar.add_argument("--simular", action="store_true", help="so' conta; nao escreve nada")
    p_expurgar.set_defaults(funcao=cmd_expurgar)

    p_alinhar = sub.add_parser(
        "alinhar-senhas",
        help="regrava o hash da senha inicial em quem nunca escolheu a propria (preparacao do corte)",
    )
    p_alinhar.add_argument("--simular", action="store_true", help="so' relata; nao escreve nada")
    p_alinhar.set_defaults(funcao=cmd_alinhar_senhas)

    args = parser.parse_args(argv)
    return int(args.funcao(args))


if __name__ == "__main__":
    sys.exit(main())
