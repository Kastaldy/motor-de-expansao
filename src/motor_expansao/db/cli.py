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

# Contrato conferido contra o dump do cluster real em 26/08/2026 (§0 da `verificacao.md`).
TABELAS_DO_MODELO = (
    "usuarios", "perfis", "permissoes", "perfil_permissoes", "eventos",
    "areas_estudo", "contratos", "bairros", "distritos", "municipios",
    "perfil_permissoes_historico", "sessoes",
)
NUMEROS_DA_SECAO_ZERO = {
    "indices": 49,   # 35 explicitos + 12 de PK + 2 de UNIQUE (a 018/D30 somou 2 + o dela de PK)
    "constraints CHECK": 14,    # a 018 (D30) e a 019: `ck_usuarios_prazo_exige_troca`
    "chaves estrangeiras": 12,  # a 018 (D30): `sessoes.id_usuario`
    "triggers": 7,   # 5 ate' a 016; a 017 (D29) somou a guarda de coerencia nas duas regioes
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
            "SELECT has_table_privilege(current_user, 'perfil_permissoes_historico', 'INSERT')",
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
            "SELECT has_table_privilege(current_user, 'perfil_permissoes_historico', 'UPDATE')",
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
            "SELECT has_table_privilege(current_user, 'eventos', 'UPDATE')",
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
            "FROM pg_class c WHERE c.relname IN "
            "('perfil_permissoes', 'perfil_permissoes_historico', 'eventos')",
            "dono desliga a propria trigger com um ALTER TABLE, e nenhum GRANT protege contra isso",
        ),
        (
            "receber SET em session_replication_role",
            "SELECT EXISTS (SELECT 1 FROM pg_parameter_acl "
            "WHERE parname = 'session_replication_role')",
            "desde o PG15 esse GRANT existe, e quem o recebe desliga TODAS as triggers da "
            "sessao -- o `ENABLE ALWAYS` da §7 do D20 e' a defesa, este e' o alarme",
        ),
    ]


def _checagens_positivas() -> list[tuple[str, str, str]]:
    """(rotulo, SQL -> bool, por que importa). `False` = o piloto QUEBRA em runtime."""
    return [
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


def _valor_unico(con: Any, sql: str) -> Any:
    """Primeira coluna da primeira linha. `None` quando a consulta nao devolve nada --
    o que aqui e' resposta legitima (ex.: `bool_or` sobre zero linhas)."""
    linha = con.execute(sql).fetchone()
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
            pode = bool(_valor_unico(con, sql))
            print(f"  {'FALHA' if pode else 'ok   '} {rotulo}")
            if pode:
                print(f"        por que importa: {porque}")
                problemas.append(rotulo)

        print("\n== o que este papel PRECISA poder ==")
        for rotulo, sql, porque in _checagens_positivas():
            pode = bool(_valor_unico(con, sql))
            print(f"  {'ok   ' if pode else 'FALHA'} {rotulo}")
            if not pode:
                print(f"        por que importa: {porque}")
                problemas.append(rotulo)

        print("\n== auditoria endurecida (D21) ==")
        estado = con.execute(postgres.SQL_ESTADO_TRIGGER, ("trg_perfil_permissoes_auditoria",))
        linha = estado.fetchone()
        atual = linha[0] if linha else None
        ok = atual == "A"
        print(f"  {'ok   ' if ok else 'FALHA'} trigger de auditoria: {atual!r} (esperado 'A')")
        if not ok:
            print(
                "        por que importa: fora de 'A', uma sessao em session_replication_role="
                "replica\n        escreve sem deixar rastro. E' o ALTER TABLE da secao 7 do D20."
            )
            problemas.append("trigger de auditoria fora de ENABLE ALWAYS")

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
    print("PRIVILEGIOS OK: o papel do piloto nao consegue o que nao deve, e consegue o que precisa.")
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
    p_expurgar.add_argument(
        "--simular", action="store_true", help="so' conta; nao escreve nada"
    )
    p_expurgar.set_defaults(funcao=cmd_expurgar)

    args = parser.parse_args(argv)
    return int(args.funcao(args))


if __name__ == "__main__":
    sys.exit(main())
