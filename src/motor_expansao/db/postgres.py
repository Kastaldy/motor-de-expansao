"""Pool, transacoes e diagnostico do PostgreSQL. Interface publica no `__init__` do pacote.

Por que psycopg3 SINCRONO e sem ORM
-----------------------------------
O backend do piloto e' sincrono (as rotas sao `def`, nao `async def`), entao um pool
sincrono encaixa sem reescrever rota nenhuma; o caminho async arrastaria uma refatoracao
que nada neste trabalho exige. E sem ORM porque o esquema do `banco-de-reservas` e' SQL
escrito a mao, com triggers `SECURITY DEFINER`, indices parciais e checagem condicional de
JSONB -- coisas que um ORM nao expressa e que ja' foram validadas em cluster real.

Por que o driver e' importado com tolerancia
--------------------------------------------
O motor tem de subir sem banco. "Sem banco" inclui "sem o extra `db` instalado": quem
roda os pipelines do M1 nao precisa do psycopg. Um `import` no topo sem protecao faria o
`app.py` inteiro falhar no boot por falta de uma dependencia que aquele caminho nao usa.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from typing import Any

_LOG = logging.getLogger("motor.db")

#: Env que LIGA o banco. Ausente ou vazia = banco nao configurado, e nenhuma conexao
#: e' tentada. Prefixo `MOTOR_` para acompanhar `MOTOR_DATA_DIR`/`MOTOR_CADASTRO_DIR`
#: (e para nao colidir com o `DATABASE_URL` morto do `config.py`, que a limpeza remove).
ENV_URL = "MOTOR_DATABASE_URL"

#: Tetos do pool. Pequenos de proposito: o piloto roda num unico worker de uvicorn e a
#: VPS ja' divide RAM entre `web` (8 GB) e `api` (6 GB).
POOL_MIN = 1
POOL_MAX = 4

#: Segundos para o pool entregar uma conexao antes de desistir. Curto: uma rota que
#: espera 30s por conexao ja' perdeu o usuario -- melhor falhar e deixar o erro aparecer.
TIMEOUT_POOL_S = 5.0

#: Segundos para o `saude()` desistir. Ele responde ao diagnostico de admin, que o
#: operador abre justamente quando desconfia do banco: nao pode pendurar a requisicao.
TIMEOUT_SAUDE_S = 2.0

#: Tabela de controle das migrations, criada pela `000`. O `saude()` apenas TENTA le-la
#: e degrada em silencio quando ela nao existe -- que e' o estado de um banco levantado a
#: mao pelo roteiro 001->010 do `banco-de-reservas`, antes de a 000 rodar.
#:
#: `migracoes_aplicadas`, e nao `migracoes`: o diretorio dos arquivos `.sql` ja' se chama
#: `migracoes/`, e o nome tambem e' mais fiel -- a tabela guarda quais foram APLICADAS,
#: quando e com que hash, nao as migrations em si.
TABELA_MIGRACOES = "migracoes_aplicadas"

#: Tabela cuja auditoria o D19 protege. O `saude()` pergunta o privilegio EFETIVO sobre
#: ela para responder "o provisionamento do D20 esta de pe?" -- ver `_provisionamento`.
TABELA_HISTORICO = "perfil_permissoes_historico"
TRIGGER_AUDITORIA = "trg_perfil_permissoes_auditoria"
#: A tabela que a 009 audita. As triggers do §7 vivem aqui, e e' por `tgrelid` que a
#: consulta as acha -- sem isso, homonima em outra tabela casaria.
TABELA_AUDITADA = "perfil_permissoes"

#: O `id_usuario` vai para o banco como TEXTO e e' validado la' pelo mesmo padrao
#: (`^[0-9]{1,18}$`, D19) antes do cast. Repetimos a validacao aqui para falhar cedo,
#: com erro legivel, em vez de gravar lixo que a trigger vai descartar em silencio.
_PADRAO_ID_USUARIO = re.compile(r"^[0-9]{1,18}$")

# --- SQL, em constantes nomeadas -------------------------------------------------------
# Todo SQL do motor fica LOCALIZAVEL, nunca interpolado no meio da logica: quem executa
# contra o banco real e' o Vinicius, e ele precisa ter o que revisar num lugar so'. E' a
# mesma razao pela qual o gate de sintaxe offline (pglast) consegue alcancar tudo.

SQL_PING = "SELECT 1"
SQL_VERSAO_POSTGIS = "SELECT postgis_version()"
SQL_VERSAO_SERVIDOR = "SHOW server_version"
SQL_SOMENTE_LEITURA = "SET TRANSACTION READ ONLY"
# `set_config(..., true)` e NAO `SET LOCAL app.id_usuario = %s`: o `SET` nao aceita
# parametro bindado, o que forcaria interpolar o valor na string -- e uma variavel de
# sessao interpolada e' injecao esperando acontecer. O terceiro argumento `true` e' o que
# torna a variavel LOCAL a transacao, morrendo no commit junto com ela.
SQL_DEFINIR_AUTOR = "SELECT set_config('app.id_usuario', %s, true)"
# Mesma forma para o timeout: era o UNICO SQL montado por f-string neste modulo, o que
# contrariava a politica declarada logo acima. Nao era injetavel (o valor passava por
# `int()`), mas "nao e' exploravel hoje" e' garantia mais fraca que "nao ha caminho".
SQL_DEFINIR_TIMEOUT = "SELECT set_config('statement_timeout', %s, true)"
SQL_VERSAO_MIGRACAO = (
    f"SELECT versao_migracao FROM {TABELA_MIGRACOES} ORDER BY versao_migracao DESC LIMIT 1"
)
# Diagnostico do provisionamento (D20). Sem estas tres respostas, um `MOTOR_DATABASE_URL`
# apontando para o DONO do schema -- o caminho de menor resistencia num deploy apressado --
# derruba a auditoria inteira sem sinal nenhum: dono desliga a propria trigger.
SQL_USUARIO_ATUAL = "SELECT current_user"
SQL_PODE_ESCREVER_HISTORICO = "SELECT has_table_privilege(%s, 'INSERT')"
# Filtra por TABELA tambem: `tgname` nao e' unico no banco, e uma trigger homonima em
# outra tabela casaria. Mantido por compatibilidade do campo `trigger_auditoria` do health.
SQL_ESTADO_TRIGGER = (
    "SELECT tgenabled FROM pg_trigger WHERE tgname = %s AND tgrelid = %s::regclass"
)
# A secao 7 do script de papeis endurece DUAS triggers em `perfil_permissoes`
# (`..._auditoria` e `..._auditoria_truncate`), e ate' 05/10/2026 este modulo olhava
# so' a primeira -- entao um §7 colado pela METADE deixava a de TRUNCATE em 'O' e
# `conferir` e `privilegios` passavam os dois verdes. E §7 colado pela metade e'
# justamente o desfecho da interrupcao que o runbook antecipa.
#
# Esta consulta DERIVA a lista em vez de nomear: se uma terceira trigger entrar na
# tabela auditada, ela aparece aqui sozinha, sem precisar lembrar de mexer no motor.
SQL_TRIGGERS_AUDITORIA = (
    "SELECT tgname, tgenabled FROM pg_trigger "
    "WHERE tgrelid = to_regclass(%s) AND NOT tgisinternal ORDER BY tgname"
)
# A secao 2 do script de papeis fecha o `EXECUTE` das funcoes de auditoria a `PUBLIC`, e
# ate' 05/10/2026 NENHUM instrumento olhava essa camada: `has_function_privilege` nao
# aparecia uma vez em todo o modulo. Com o `EXECUTE` devolvido a `PUBLIC`, `conferir`
# dizia OK e a contagem 12/1/3 ficava intacta. Terceiro furo da mesma familia.
#
# O universo sai das PROPRIAS triggers (`tgfoid`), nao de uma lista nem de um `LIKE`. E
# isso nao e' elegancia: as OUTRAS funcoes do modelo tem `EXECUTE` para `PUBLIC` por
# padrao e de forma legitima -- medi seis assim --, entao exigir `false` em todas daria
# falso alarme em seis objetos. O escopo certo e' "as funcoes atras das triggers da
# tabela auditada", e so' o catalogo sabe quais sao.
SQL_ACL_FUNCOES_DE_AUDITORIA = (
    "SELECT p.proname, has_function_privilege('public', p.oid, 'EXECUTE') "
    "FROM pg_trigger tg JOIN pg_proc p ON p.oid = tg.tgfoid "
    "WHERE tg.tgrelid = to_regclass(%s) AND NOT tg.tgisinternal ORDER BY p.proname"
)
# A QUARTA camada que o script endurece e nenhum instrumento olhava: o
# `ALTER DEFAULT PRIVILEGES` da secao 6. E' a de maior alcance das quatro -- o no-op
# silencioso do `FOR ROLE postgres` faz TODA TABELA FUTURA nascer invisivel para o
# `app`, e os tres comandos passavam verdes. Medido em 05/10/2026: com so' as linhas de
# `postgres` no `pg_default_acl`, uma tabela criada depois devolve
# `has_table_privilege('app', ..., 'SELECT') = false`.
#
# A pergunta e' DERIVADA: o dono da tabela auditada -- quem de fato vai criar objeto
# aqui -- aparece entre os papeis do `pg_default_acl`? E' permissiva de proposito: papel
# EXTRA nao reprova (um cluster pode ter default ACL de mais de um dono por motivo
# legitimo); o que reprova e' o dono estar AUSENTE, que e' exatamente o no-op.
# O QUINTO furo, achado em 05/10/2026: a seccao 2 concede `USAGE ON SCHEMA public` e
# NENHUM instrumento perguntava se o papel tem. `has_schema_privilege` aparecia uma vez
# so', para `CREATE`, que e' checagem NEGATIVA. Sem `USAGE` o privilegio de TABELA
# continua no catalogo -- `has_table_privilege` nao considera schema --, entao `conferir`
# fica verde, a contagem 12/1/3 fica intacta, e a aplicacao morre com
# `relation "usuarios" does not exist`, que aponta para migration ausente.
#
# Tem de ser a PRIMEIRA checagem positiva: sem USAGE, dezesseis das outras degradam para
# "o objeto nao existe (migration pendente?)" num banco com 21 de 21 migrations
# registradas, e o operador e' mandado de volta ao §5, que responde que esta' tudo certo.
SQL_USAGE_NO_SCHEMA = "SELECT has_schema_privilege(current_user, 'public', 'USAGE')"
#: A tabela auditada e' VISIVEL para este papel? `to_regclass` devolve NULL em vez de
#: levantar, e NULL aqui significa "ou a migration nao rodou, ou falta USAGE no schema" --
#: duas causas, e o relatorio tem de nomear as duas em vez de chutar uma.
SQL_TABELA_AUDITADA_VISIVEL = "SELECT to_regclass(%s) IS NOT NULL"
# Devolve (dono da tabela auditada, quem CRIA, quem RECEBE). As tres colunas, porque
# as duas primeiras sozinhas aprovam um estado ruim: ate' 05/10/2026 esta consulta lia so'
# `defaclrole` -- QUEM CRIA -- e um `ALTER DEFAULT PRIVILEGES` com o `FOR ROLE` certo e o
# grantee errado (`TO auditoria` em vez de `TO app`) passava verde, com a tabela futura
# nascendo invisivel ao `app`. `defaclacl` e' a coluna que carrega a concessao, e
# `aclexplode` a abre em papeis.
#: Quem cria objeto no schema: o dono da tabela auditada. Separado da consulta do
#: `pg_default_acl` porque aquela agora devolve UMA LINHA POR TIPO de objeto.
SQL_DONO_DA_TABELA_AUDITADA = (
    "SELECT c.relowner::regrole::text FROM pg_class c WHERE c.oid = to_regclass(%s)"
)
SQL_DEFAULT_ACL_DO_DONO = (
    "SELECT d.defaclobjtype, "
    "string_agg(DISTINCT d.defaclrole::regrole::text, ','), "
    "coalesce(string_agg(DISTINCT a.grantee::regrole::text, ','), ''), "
    # Responde se o papel CONECTADO recebe, direta ou por HERANCA. Comparar `current_user`
    # com o nome do grantee deu falso alarme medido -- papel membro do `app` recebe o
    # privilegio e seria reprovado. Nota: para SUPERUSUARIO isto e' sempre verdadeiro, o
    # que esta' certo (superusuario tem tudo) e e' por isso que este comando pede para ser
    # rodado com a credencial do `app`, nao com a do dono.
    "coalesce(bool_or(pg_has_role(a.grantee, 'USAGE')), false) "
    "FROM pg_default_acl d JOIN pg_namespace n ON n.oid = d.defaclnamespace "
    "LEFT JOIN LATERAL aclexplode(d.defaclacl) a ON true "
    "WHERE n.nspname = 'public' GROUP BY d.defaclobjtype ORDER BY d.defaclobjtype"
)
#: Os tipos de objeto que a secao 6 cobre: `r` = TABLES, `S` = SEQUENCES. UMA linha por
#: tipo, porque agregar os dois ESCONDE a lacuna -- medido: com o grantee errado so' em
#: TABLES e as SEQUENCES intactas, o agregado continuava mostrando o papel certo e passava.
TIPOS_DO_DEFAULT_ACL = {"r": "TABLES", "S": "SEQUENCES"}
# Papel que tem privilegio de TABELA ou SEQUENCE no schema `public` e NAO tem `USAGE`
# nele: o privilegio existe no catalogo e e' inerte, porque o papel nao ve o objeto.
#
# DERIVADA de proposito. A secao 2 concede `USAGE` a TRES papeis (`app, auditoria, etl`),
# e tanto a checagem que entrou na R15 quanto a consulta que o pacote prescreve
# perguntavam por UM. Medido em 05/10/2026: revogando so' do `auditoria`, ele mantem
# `SELECT` em `perfil_permissoes_historico` no catalogo, a consulta real falha com
# `relation "perfil_permissoes_historico" does not exist`, e as oito conferencias do
# pacote ficam TODAS verdes. O papel existe para uma coisa so' -- ler aquele historico --
# e e' exatamente ela que quebra.
#
# O dono do schema nao aparece aqui: tem `USAGE` implicito (medido). Papel novo entra
# sozinho, sem ninguem lembrar de mexer nesta lista -- porque nao ha lista.
# A SEXTA classe, achada em 06/10/2026: a secao 1 do script endurece ATRIBUTOS de papel
# (`CREATE ROLE etl NOLOGIN`, e nenhum dos tres com `CREATEDB`, `CREATEROLE` ou
# `SUPERUSER`) e nenhum instrumento olhava isso. Medido: com `ALTER ROLE etl LOGIN` e
# `ALTER ROLE app CREATEDB CREATEROLE`, `conferir` sai 0 e a contagem 12/1/3 fica intacta.
#
# DERIVADA, e com o dono excluido por SER DONO -- nao por nome. Sem essa exclusao a
# consulta acusaria o proprio `reservas_owner`, que e' superusuario e aparece em `relacl`
# com concessoes explicitas: falso alarme medido antes de entregar.
#
# Nao cobre o `NOLOGIN` do `etl`: qual dos tres nao deve logar e' decisao de desenho, nao
# se deriva do catalogo. Essa metade fica como consulta manual, declarada no pacote.
# A SETIMA classe (06/10/2026). A secao 2 do script faz
# `REVOKE CREATE ON SCHEMA public FROM PUBLIC` e `REVOKE TEMPORARY ON DATABASE ... FROM
# PUBLIC` -- endurece contra PUBLIC, isto e', a favor de `auditoria` e `etl` tambem. Mas
# todo instrumento pergunta pelo papel CONECTADO: o `privilegios` usa `current_user` e os
# seis testes negativos do script cravam `'app'`. Medido: com `CREATE` no schema para o
# `etl` e `TEMPORARY` no banco para `auditoria` e `etl`, tudo fica verde e o `etl` cria
# tabela.
#
# Universo DERIVADO: os papeis que tem privilegio no schema, mais o proprio `public`, menos
# o dono (que tem os dois por construcao). As duas perguntas juntas, porque sao as duas que
# a secao 2 fecha -- e porque a de `TEMPORARY` subsume o buraco que o dump nao carrega.
# Sequences cujo `USAGE` NAO casa com o `INSERT` na tabela que as possui -- nos dois
# sentidos. Deriva o universo de `pg_depend` (`deptype = 'a'`, a sequence pertence a
# coluna), entao as oito do schema entram sozinhas e uma nova entra sem ninguem lembrar.
#
# Os dois sentidos importam, e nenhum instrumento olhava o segundo:
#   INSERT sem USAGE -> o `INSERT` morre em runtime (era 2 de 5 cobertas);
#   USAGE sem INSERT -> privilegio excedente (medido: `GRANT USAGE ON ALL SEQUENCES`
#                       passava `conferir`, `privilegios` e a contagem 12/1/3 verdes).
SQL_SEQUENCES_DESALINHADAS = (
    "SELECT coalesce(string_agg(s.rotulo, ', ' ORDER BY s.relname), '') FROM ("
    "SELECT s.relname, CASE WHEN t.oid IS NULL THEN s.relname || "
    "' (USAGE numa sequence SEM TABELA DONA)' WHEN s.usa THEN s.relname || "
    "' (USAGE sem INSERT em ' || t.relname || ')' ELSE s.relname || "
    "' (INSERT sem USAGE em ' || t.relname || ')' END AS rotulo "
    "FROM (SELECT c.oid, c.relname, "
    "has_sequence_privilege(current_user, c.oid, 'USAGE') AS usa "
    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
    "WHERE c.relkind = 'S' AND n.nspname = 'public') s "
    "LEFT JOIN pg_depend d ON d.objid = s.oid AND d.deptype IN ('a', 'i') "
    "LEFT JOIN pg_class t ON t.oid = d.refobjid "
    "WHERE t.oid IS NULL AND s.usa "
    "OR t.oid IS NOT NULL AND s.usa <> has_table_privilege(current_user, t.oid, 'INSERT')"
    ") s"
)
#: O parametro que desliga todas as triggers da sessao: a pergunta e' se QUEM CONECTOU
#: pode. `pg_parameter_acl` e' catalogo do CLUSTER (`relisshared = true`, medido), e um
#: `EXISTS` sobre ele acusa concessao feita em outro banco, a outro papel.
#: Quem pode trocar `session_replication_role` -- e a pergunta e' pelos TRES papeis que o
#: D20 cria, nao so' pelo conectado. Devolve os nomes que podem; vazio e' o estado bom.
#:
#: Por que mudou em 07/10/2026: a 1a versao perguntava `current_user`, o que consertou o
#: falso alarme do catalogo compartilhado e abriu um ponto cego. Medido: com `GRANT SET ON
#: PARAMETER session_replication_role TO auditoria` feito em OUTRO banco do cluster, a
#: pergunta pelo `app` saia `f` -- e no banco do piloto `SET ROLE auditoria; SET
#: session_replication_role = replica` FUNCIONAVA. O universo sao os papeis do D20, que e'
#: o mesmo recorte da setima classe.
#: Quem pode trocar `session_replication_role`. O universo e' DERIVADO: todo papel que
#: nao e' do sistema e nao e' superusuario. Vazio e' o estado bom.
#:
#: Por que deixou de ser a lista de tres nomes, em 07/10/2026: tres rodadas de ensaio
#: seguidas acharam variantes do mesmo defeito -- privilegio que entra por um papel fora
#: da lista e' invisivel a toda conferencia que pergunta pelos tres. Medido: um quarto
#: papel com `GRANT SET ON PARAMETER` ficava invisivel a esta consulta, e a unica leitura
#: que o via era o `EXISTS` sobre `pg_parameter_acl` -- que erra para o outro lado, porque
#: o catalogo e' compartilhado pelo cluster. Superusuario fica fora porque pode tudo por
#: definicao, e o `rolname NOT LIKE 'pg\_%'` exclui os papeis predefinidos do proprio PG.
SQL_PARAMETRO_DA_SESSAO = (
    # O `NOT rolsuper` saiu em 07/10/2026: superusuario PODE trocar
    # `session_replication_role`, entao exclui-lo e' esconder o pior caso desta linha. Quem
    # sai e' o DONO do banco, por `datdba` -- ele e' superusuario por desenho aqui.
    "SELECT coalesce(string_agg(rolname, ', ' ORDER BY rolname), '') FROM pg_roles "
    r"WHERE rolname NOT LIKE 'pg\_%' "
    "AND oid <> (SELECT datdba FROM pg_database WHERE datname = current_database()) "
    "AND has_parameter_privilege(rolname, 'session_replication_role', 'SET')"
)
SQL_PODERES_ABERTOS_NO_SCHEMA = (
    "SELECT coalesce(string_agg(DISTINCT papel || ' (' || poder || ')', ', '), '') FROM ("
    "SELECT p.papel, x.poder FROM ("
    "SELECT DISTINCT a.grantee::regrole::text AS papel FROM pg_class c "
    "JOIN pg_namespace n ON n.oid = c.relnamespace "
    "CROSS JOIN LATERAL aclexplode(c.relacl) a "
    "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'S') "
    "AND a.grantee <> 0 AND a.grantee <> c.relowner "
    "AND a.grantee <> (SELECT datdba FROM pg_database "
    "WHERE datname = current_database()) "
    "UNION SELECT 'public'"
    ") p CROSS JOIN LATERAL (VALUES "
    "('CREATE no schema', has_schema_privilege(p.papel, 'public', 'CREATE')), "
    "('TEMPORARY no banco', has_database_privilege(p.papel, current_database(), 'TEMPORARY'))"
    ") x(poder, tem) WHERE x.tem"
    ") y"
)
# As CINCO colunas de poder de `pg_authid`, nao tres: `rolreplication` e `rolbypassrls`
# ficaram de fora da 1a versao e, medido em 07/10/2026, a consulta devolvia o esperado com
# `app REPLICATION` e `auditoria BYPASSRLS` -- enquanto o `\du` IMPRIME os dois. As outras
# colunas booleanas (`rolinherit`, `rolcanlogin`) nao concedem poder.
#
# E o UNIVERSO passou de `relacl` para `pg_roles` em 07/10/2026, pela terceira vez que a
# mesma licao apareceu nesta familia. Medido: `CREATE ROLE intruso LOGIN SUPERUSER` saia
# `PRIVILEGIOS OK`, exit 0, e o `intruso` lia 79 linhas de `perfil_permissoes_historico`.
# A consulta PERGUNTAVA por `rolsuper` corretamente -- e nunca via o papel, porque um
# papel recem-criado nao tem ACL em tabela nenhuma e por isso nao entrava no universo.
# Universo derivado da ACL e' estreito: quem ainda nao recebeu GRANT fica fora dele.
#
# O DONO do banco sai por `datdba`, nao por nome: no cenario deste pacote ele e' o
# superusuario de bootstrap e e' superusuario POR DESENHO. Qualquer OUTRO superusuario e'
# achado -- inclusive um `postgres` de administracao, que o operador confirma e segue.
SQL_PAPEIS_COM_PODER_DE_CLUSTER = (
    "SELECT coalesce(string_agg(r.rolname || ' (' || "
    "concat_ws(', ', CASE WHEN r.rolsuper THEN 'SUPERUSER' END, "
    "CASE WHEN r.rolcreaterole THEN 'CREATEROLE' END, "
    "CASE WHEN r.rolcreatedb THEN 'CREATEDB' END, "
    "CASE WHEN r.rolreplication THEN 'REPLICATION' END, "
    "CASE WHEN r.rolbypassrls THEN 'BYPASSRLS' END) || ')', "
    "', ' ORDER BY r.rolname), '') FROM pg_roles r "
    r"WHERE r.rolname NOT LIKE 'pg\_%' "
    "AND r.oid <> (SELECT datdba FROM pg_database "
    "WHERE datname = current_database()) "
    "AND (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole "
    "OR r.rolreplication OR r.rolbypassrls)"
)
#: A que papeis o papel CONECTADO pertence. Vazio e' o estado bom -- medido: no banco
#: provisionado como o D20 manda, `app` nao e' membro de ninguem.
#:
#: Por que existe (07/10/2026): pertencimento NAO cria entrada de ACL, entao nenhuma
#: conferencia que leia `relacl`, `role_table_grants` ou `has_table_privilege` sobre a
#: lista nominal o ve. Medido, com `privilegios` saindo OK nos dois casos:
#:   GRANT pg_write_all_data TO auditoria  -> `auditoria` faz DELETE na tabela append-only
#:   GRANT etl TO app                      -> `app` faz TRUNCATE nas tres de referencia
#: Esta consulta fecha os dois de uma vez, e fecha tambem os papeis predefinidos que
#: ainda nao existem: o universo e' "qualquer papel", nao uma lista de nomes perigosos.
#: Privilegio de COLUNA concedido a quem nao e' o dono, em qualquer tabela do schema.
#: Vazio e' o estado bom -- medido: o provisionamento do D20 nao concede coluna nenhuma.
#:
#: Por que existe (07/10/2026): `GRANT UPDATE (id_perfil) ON usuarios TO auditoria` nao
#: aparece em `relacl` nem em `information_schema.role_table_grants` -- so' em
#: `pg_attribute.attacl` / `role_column_grants`, que nenhum instrumento lia. Medido: a
#: contagem 12/1/3 nao se move, as doze conferencias manuais do pacote saem identicas ao
#: estado bom, e o `auditoria` -- o papel que existe para LER -- troca o perfil de
#: qualquer pessoa. E' o caminho que derrota o RBAC sem tocar em `perfil_permissoes`,
#: que e' onde toda a instrumentacao olhava.
SQL_PRIVILEGIO_DE_COLUNA = (
    "SELECT coalesce(string_agg(DISTINCT x.papel || ' em ' || x.obj || ' (' || x.priv || ')', "
    "', '), '') FROM ("
    "SELECT a.grantee::regrole::text AS papel, "
    "c.relname || '.' || att.attname AS obj, a.privilege_type AS priv "
    "FROM pg_attribute att "
    "JOIN pg_class c ON c.oid = att.attrelid "
    "JOIN pg_namespace n ON n.oid = c.relnamespace "
    "CROSS JOIN LATERAL aclexplode(att.attacl) a "
    # `PUBLIC` ENTRA. O filtro `a.grantee <> 0` o excluia, e `PUBLIC` e' o pior grantee
    # possivel: `GRANT UPDATE (id_perfil) ON usuarios TO PUBLIC` nao aparecia aqui, e a
    # contagem por nome (12/1/3) tambem nao o ve, porque ele nao e' nenhum dos tres nomes.
    # Medido em 07/10/2026: com esse GRANT, esta consulta devolvia ZERO linha; sem o
    # filtro, devolve `- | usuarios.id_perfil | UPDATE` (o `-` e' o PUBLIC).
    "WHERE n.nspname = 'public' AND att.attacl IS NOT NULL "
    "AND a.grantee <> c.relowner"
    ") x"
)
#: ACL de TABELA concedida a `PUBLIC` no schema. Vazio e' o estado bom -- a secao 3 do
#: script faz dois `REVOKE ... FROM PUBLIC` em tabela, isto e', trata `PUBLIC`-em-tabela
#: como ameaca que ela precisa fechar, e nada conferia se fechou.
#:
#: Medido em 07/10/2026: `GRANT DELETE ON perfil_permissoes_historico TO PUBLIC` deixa as
#: quinze conferencias manuais do pacote byte a byte identicas ao estado bom, e o `app`
#: faz `DELETE` na tabela append-only. O `privilegios` pega por outro caminho -- as
#: perguntas negativas usam `has_table_privilege(current_user, ...)`, que CONSIDERA o
#: privilegio herdado de `PUBLIC` --, mas so' para as tabelas que ele nomeia; esta ve
#: qualquer tabela do schema.
SQL_ACL_DE_PUBLIC_EM_TABELA = (
    "SELECT coalesce(string_agg(DISTINCT c.relname || ' (' || a.privilege_type || ')', "
    "', ' ORDER BY c.relname || ' (' || a.privilege_type || ')'), '') "
    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
    "CROSS JOIN LATERAL aclexplode(c.relacl) a "
    # O `relkind IN ('r','p')` saiu em 07/10/2026: medido, uma VIEW do historico criada no
    # PROPRIO `public` e concedida a `PUBLIC` passava por tudo --
    # `has_table_privilege('app', <tabela>, 'SELECT')` em `f` e na VIEW em `t`, com as 79
    # linhas legiveis. O filtro estava ali para nao gritar com
    # `geometry_columns`/`geography_columns`, que sao views do PostGIS -- e isso se resolve
    # por NOME, que e' o que os tres objetos conhecidos fazem agora.
    "WHERE n.nspname = 'public' AND a.grantee = 0 "
    "AND c.relname NOT IN ('spatial_ref_sys', 'geometry_columns', 'geography_columns')"
)
#: A QUINTA porta: a POSSE de funcao. O pacote a nomeava desde o inicio e ninguem cobria.
#:
#: Medido em 08/10/2026, passando as duas funcoes de auditoria do D20 para o `app`:
#:
#:     conferir                  ->  CONFERENCIA OK,  exit 0
#:     privilegios               ->  PRIVILEGIOS OK,  exit 0
#:     as 22 conferencias manuais do pacote  ->  NENHUMA diferenca
#:
#: e entao, como `app`:
#:
#:     DROP FUNCTION registra_perfil_permissoes_historico() CASCADE;
#:       NOTA: removendo em cascata gatilho trg_perfil_permissoes_auditoria
#:     DROP FUNCTION registra_perfil_permissoes_truncate() CASCADE;
#:       NOTA: removendo em cascata gatilho trg_perfil_permissoes_auditoria_truncate
#:     triggers restantes: 0
#:     INSERT + DELETE em perfil_permissoes  ->  ZERO linha de auditoria
#:
#: Dono de funcao pode `DROP ... CASCADE` (que leva a trigger junto) e
#: `ALTER ... SECURITY INVOKER`. O `conferir` pega o segundo -- ele olha `prosecdef` --, e o
#: primeiro ninguem pegava: a posse nao aparece em ACL nenhuma.
#:
#: DERIVADA, e nao pelas duas do D20: a pergunta e' "alguma funcao deste schema tem dono que
#: nao e' o dono do banco?". Medida em quatro estados -- 0 no bom, 2 com as duas no `app`, 1
#: com uma so' (o caso mais discreto) e 1 com uma funcao qualquer passada ao `etl`.
SQL_FUNCAO_COM_DONO_ALHEIO = (
    "SELECT coalesce(string_agg(p.proname || ' (dono ' || "
    "p.proowner::regrole::text || ')', ', ' ORDER BY p.proname), '') "
    "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
    "WHERE n.nspname = 'public' "
    "AND p.proowner <> (SELECT datdba FROM pg_database "
    "WHERE datname = current_database())"
)
#: O que existe neste banco ALEM do que o D20 cria -- o recorte `public` que todas as
#: outras conferencias partilham, e que deixava o `app` apagar o historico inteiro.
#:
#: Medido em 07/10/2026, e e' o achado mais grave desta familia: com uma foreign table num
#: schema novo apontando de volta para o proprio banco, sob um user mapping do `app` para o
#: DONO, o `app` fez `DELETE 77` em `perfil_permissoes_historico` -- as 77 linhas, zero
#: restantes -- enquanto `conferir` saia OK, `privilegios` saia OK e as DOZE consultas do
#: pacote ficavam todas no estado bom. A promessa central do D19/D20 quebrada com tudo
#: verde, e sem que nenhuma ACL do `public` tenha mudado.
#:
#: Nao e' falta de uma consulta: e' o `n.nspname = 'public'` que todas as outras tem. Esta
#: pergunta o complemento -- "o que existe aqui que o D20 nao cria?" -- numa varredura so'.
#: Provada em seis estados: o FDW inteiro, um `EVENT TRIGGER` de DDL, um schema novo VAZIO
#: (o caso mais discreto, que nenhuma outra ve), uma view noutro schema com GRANT ao `app`,
#: e uma extensao alheia instalada no PROPRIO `public`.
#:
#: `pg_user_mapping` fica fora: medido, o `app` nao o le (`permissao negada`), e este
#: comando roda como `app`. Nao custa cobertura, porque mapeamento nao existe sem servidor
#: e o servidor aparece. As tres extensoes nomeadas sao a especificacao do D20.
SQL_O_QUE_O_D20_NAO_CRIA = (
    "SELECT coalesce(string_agg(achado, '; ' ORDER BY achado), '') FROM ("
    "SELECT 'schema alheio: ' || n.nspname || ' (dono ' "
    "|| n.nspowner::regrole::text || ')' AS achado "
    "FROM pg_namespace n "
    r"WHERE n.nspname NOT LIKE 'pg\_%' "
    "AND n.nspname NOT IN ('public', 'information_schema') "
    "UNION ALL "
    "SELECT 'extensao alheia: ' || e.extname || ' em ' || n.nspname "
    "FROM pg_extension e JOIN pg_namespace n ON n.oid = e.extnamespace "
    "WHERE e.extname NOT IN ('plpgsql', 'postgis', 'citext') "
    "UNION ALL "
    "SELECT 'servidor externo: ' || s.srvname FROM pg_foreign_server s "
    "UNION ALL "
    "SELECT 'tabela externa: ' || n.nspname || '.' || c.relname "
    "FROM pg_foreign_table f JOIN pg_class c ON c.oid = f.ftrelid "
    "JOIN pg_namespace n ON n.oid = c.relnamespace "
    "UNION ALL "
    "SELECT 'event trigger: ' || e.evtname || ' em ' || e.evtevent "
    "|| ' (dono ' || e.evtowner::regrole::text || ')' FROM pg_event_trigger e "
    "UNION ALL "
    "SELECT 'privilegio fora do public: ' || a.grantee::regrole::text || ' em ' "
    "|| n.nspname || '.' || c.relname || ' (' || a.privilege_type || ')' "
    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
    "CROSS JOIN LATERAL aclexplode(c.relacl) a "
    r"WHERE n.nspname NOT LIKE 'pg\_%' "
    "AND n.nspname NOT IN ('public', 'information_schema') "
    "AND a.grantee <> c.relowner "
    "AND a.grantee <> (SELECT datdba FROM pg_database "
    "WHERE datname = current_database())"
    ") x"
)
#: O parametro FIXADO por banco ou por papel -- a porta que `pg_parameter_acl` nao ve.
#:
#: Todo o instrumento conferia quem PODE trocar `session_replication_role` (o GRANT SET ON
#: PARAMETER, que vive em `pg_parameter_acl`). Medido em 07/10/2026, a outra porta:
#:
#:     ALTER DATABASE banco_de_reservas SET session_replication_role = 'replica';
#:
#:     o `app` NASCE em replica em toda sessao nova
#:     SET session_replication_role = origin  ->  ERRO: permissao negada  (pegajoso)
#:     as dez conferencias                   ->  TODAS identicas ao estado bom
#:
#: Ninguem precisa de privilegio para isso: quem fixa e' o dono do banco, num gesto que
#: parece configuracao. As triggers em modo padrao param de disparar, e as de auditoria em
#: `ENABLE ALWAYS` continuam -- o que torna o estado ainda mais convincente.
#:
#: A consulta nao nomeia parametro nenhum DE PROPOSITO: `row_security = off` desliga RLS,
#: `search_path` redireciona a resolucao de nomes, e a lista de parametros perigosos nao
#: fecha. Qualquer linha aqui e' para o operador LER.
SQL_PARAMETRO_FIXADO_POR_BANCO_OU_PAPEL = (
    "SELECT coalesce(string_agg("
    "coalesce(d.datname, '(todo o cluster)') || '/' || "
    "coalesce(r.rolname, '(todo papel)') || ': ' || s.setconfig::text, ', '), '') "
    "FROM pg_db_role_setting s "
    "LEFT JOIN pg_database d ON d.oid = s.setdatabase "
    "LEFT JOIN pg_roles r ON r.oid = s.setrole"
)
#: Grantee A MAIS no default ACL do dono -- o privilegio que age no FUTURO.
#:
#: A conferencia que existia olhava se o `app` RECEBE (e se `defaclrole` e' o dono). Medido
#: em 07/10/2026 o que ela nao olhava:
#:
#:     ALTER DEFAULT PRIVILEGES FOR ROLE reservas_owner IN SCHEMA public
#:       GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON TABLES TO auditoria;
#:
#:     no instante do repasse  ->  as dez conferencias identicas ao estado bom
#:     e a PROXIMA tabela      ->  {..., auditoria=arwdD/reservas_owner}
#:     o `auditoria` nela      ->  TRUNCATE TABLE
#:
#: E' o eixo do TEMPO: o GRANT da secao 3 e' retrato do presente, e o default ACL age na
#: proxima tabela que o dono criar -- isto e', na proxima migration. Nenhuma conferencia de
#: ACL no momento do repasse pode ver isso, porque o objeto ainda nao existe.
#:
#: Aqui `'app'` e' a ESPECIFICACAO, como na `SQL_PAPEIS_COM_ACL_NO_SCHEMA`: a pergunta e'
#: positiva sobre o conjunto provisionado -- o D20 concede default ACL ao `app` e a mais
#: ninguem --, e qualquer outro grantee e' achado. `PUBLIC` aparece como `-`.
SQL_GRANTEE_A_MAIS_NO_DEFAULT_ACL = (
    "SELECT coalesce(string_agg(DISTINCT "
    "coalesce(nullif(a.grantee::regrole::text, '-'), 'PUBLIC') || ' em ' || "
    # `defaclobjtype` e' do tipo `"char"`, e `text || "char"` nao tem operador unico --
    # `AmbiguousFunction` em runtime, que nenhum compile pega. Cast explicito.
    "d.defaclobjtype::text || ' (' || a.privilege_type || ')', ', '), '') "
    "FROM pg_default_acl d "
    "CROSS JOIN LATERAL aclexplode(d.defaclacl) a "
    "JOIN pg_namespace n ON n.oid = d.defaclnamespace "
    "WHERE n.nspname = 'public' AND a.grantee <> d.defaclrole "
    "AND a.grantee::regrole::text <> 'app'"
)
#: RLS ligado numa tabela do schema -- a cegueira por SILENCIO.
#:
#: O D20 nao usa row-level security. Medido em 07/10/2026:
#:
#:     ALTER TABLE perfil_permissoes_historico ENABLE ROW LEVEL SECURITY;
#:
#:     o `auditoria` passa a ver   ->  0 linhas (eram 81)
#:     has_table_privilege(...)    ->  t  (CONTINUA t)
#:     o dono ve                   ->  81
#:     as dez conferencias         ->  TODAS identicas ao estado bom
#:
#: RLS sem politica nenhuma nega tudo, e nega SEM ERRO: o `SELECT` devolve zero linha. O
#: papel que existe para ler a auditoria -- e a tela que ele serve -- passa a mostrar um
#: historico vazio, e o operador nao tem como distinguir "nada aconteceu" de "estou cego".
#: A contagem de politicas vai no diagnostico porque zero politica com RLS ligado e' o caso
#: que nega tudo.
SQL_RLS_LIGADO_NO_SCHEMA = (
    "SELECT coalesce(string_agg(c.relname || ' (" "rls" "' || "
    "CASE WHEN c.relforcerowsecurity THEN ' FORCADO' ELSE '' END || ', ' || "
    "(SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid)::text || "
    "' politica(s))', ', ' ORDER BY c.relname), '') "
    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
    "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') "
    "AND (c.relrowsecurity OR c.relforcerowsecurity)"
)
#: Funcao `SECURITY DEFINER` que nao e' uma das duas do D20 -- a lista fixa que cegava.
#:
#: O `conferir` checa `prosecdef` e `proconfig`, e checa BEM -- medido, degradando uma
#: funcao esperada ele reprova. Mas ele filtra `proname = ANY(FUNCOES_ESPERADAS)`, uma
#: lista de oito nomes, e funcao NOVA nao entra no universo. Medido em 07/10/2026:
#:
#:     CREATE FUNCTION total_do_historico() RETURNS bigint LANGUAGE sql SECURITY DEFINER
#:       AS $$ SELECT count(*) FROM perfil_permissoes_historico $$;
#:
#:     o `app` lendo a tabela direto  ->  ERRO: permissao negada  (como o D20 quer)
#:     o `app` pela funcao            ->  81
#:     as dez conferencias            ->  TODAS identicas ao estado bom
#:
#: `SECURITY DEFINER` carrega o privilegio do DONO e nao deixa entrada de ACL em lugar
#: nenhum -- e' um buraco na parede, nao uma porta. As duas funcoes do D20 saem por nome
#: porque elas SAO a especificacao; o `search_path` vai no diagnostico porque uma
#: `SECURITY DEFINER` sem `search_path` fixado e' pior ainda.
SQL_FUNCAO_SECURITY_DEFINER_ALHEIA = (
    "SELECT coalesce(string_agg(p.proname || ' (dono ' || "
    "p.proowner::regrole::text || ', ' || "
    "coalesce(p.proconfig::text, 'SEM search_path') || ')', "
    "', ' ORDER BY p.proname), '') "
    "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
    "WHERE n.nspname = 'public' AND p.prosecdef "
    "AND p.proname NOT IN ('registra_perfil_permissoes_historico', "
    "'registra_perfil_permissoes_truncate')"
)
#: Os papeis que TEM ACL no schema -- a porta principal, que nunca teve consulta de
#: universo derivado. Medido em 07/10/2026:
#:
#:     GRANT SELECT ON perfil_permissoes_historico TO consultor
#:       -> `PRIVILEGIOS OK` exit 0, a contagem por papel IDENTICA ao estado bom,
#:          e o `consultor`, com senha propria, lendo as 79 linhas do historico
#:
#: Aqui a lista de tres nomes e' CORRETA, e a diferenca importa: nas perguntas negativas
#: ("ninguem deve ter X") nomear tres e' o furo, porque o universo e' aberto. Esta pergunta
#: e' POSITIVA sobre o conjunto provisionado -- "os papeis com ACL no schema sao exatamente
#: os tres que o D20 cria" --, e ai a lista e' a ESPECIFICACAO. Um quarto nome e' achado
#: por definicao, seja ele qual for.
#:
#: Ela tambem fecha o privilegio de SEQUENCE a quem nao devia: medido,
#: `GRANT USAGE, UPDATE ON ALL SEQUENCES ... TO consultor` aparece aqui, e as duas
#: consultas de sequence (que perguntam pelo papel conectado) nao o veem.
SQL_PAPEIS_COM_ACL_NO_SCHEMA = (
    "SELECT coalesce(string_agg(DISTINCT a.grantee::regrole::text, ', '), '') "
    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
    "CROSS JOIN LATERAL aclexplode(c.relacl) a "
    "WHERE n.nspname = 'public' AND a.grantee <> 0 AND a.grantee <> c.relowner "
    "AND a.grantee <> (SELECT datdba FROM pg_database "
    "WHERE datname = current_database()) "
    "AND a.grantee::regrole::text NOT IN ('app', 'auditoria', 'etl')"
)

# A arvore de papeis: NENHUM universo de privilegio, nem lista de nomes.
#
# Esta consulta teve tres formas. A 1a olhava so' o papel conectado, e deixava passar
# `GRANT pg_write_all_data TO auditoria`. A 2a (r29) acrescentou a direcao inversa e
# derivou os dois universos de `relacl` -- o que parecia fechar a familia, porque troca
# lista de nomes por universo derivado. NAO fecha: um universo derivado da ACL ainda e'
# um universo ESTREITO. Medido em 07/10/2026, cadeia de DOIS niveis:
#
#     GRANT pg_read_all_data TO relatorios;  GRANT relatorios TO consultor;
#     -> "ok  a arvore de papeis esta plana, nas duas direcoes", PRIVILEGIOS OK, exit 0
#     -> e o `consultor`, com senha propria: 47 linhas de `perfil_permissoes_historico`
#
# `relatorios` tira o poder de um papel INTERNO, entao nao aparece em `relacl` -- nem como
# `m.member` nem como `m.roleid`. As duas metades olhavam o mesmo universo estreito.
#
# A pergunta "a arvore esta plana?" nao precisa de universo de privilegio: ela se responde
# sobre `pg_auth_members` inteiro. O unico filtro legitimo e' no MEMBRO -- papel interno ou
# superusuario como membro nao acrescenta achado. A MAE fica LIVRE, de proposito:
# `pg_write_all_data` como mae e' justamente o caso da 1a forma.
SQL_PAPEIS_DE_QUEM_CONECTOU = (
    "SELECT coalesce(string_agg("
    "mem.rolname || ' -> ' || mae.rolname || "
    "CASE WHEN m.inherit_option THEN '' ELSE ' (so com SET ROLE)' END, "
    "', ' ORDER BY mem.rolname, mae.rolname), '') "
    "FROM pg_auth_members m "
    "JOIN pg_roles mem ON mem.oid = m.member "
    "JOIN pg_roles mae ON mae.oid = m.roleid "
    # 4a forma, 07/10/2026: o filtro do MEMBRO (`NOT LIKE 'pg\_%' AND NOT rolsuper`) dizia
    # que "papel interno como membro nao acrescenta achado", e isso foi medido FALSO:
    # `GRANT auditoria TO pg_monitor` saia `(0 linha)`, e no dia em que alguem recebe
    # `pg_monitor` -- gesto rotineiro de monitoracao -- a linha que aparece e'
    # `consultor -> pg_monitor`, que se le como inofensiva e nao nomeia `auditoria`.
    # Saem so' as arestas NATIVAS do PostgreSQL (membro `pg_` E mae `pg_`): medido, no
    # estado bom as duas formas dao zero linha, porque as nativas sao todas pg_->pg_.
    r"WHERE NOT (mem.rolname LIKE 'pg\_%' AND mae.rolname LIKE 'pg\_%') "
    "AND mem.oid <> (SELECT datdba FROM pg_database WHERE datname = current_database())"
)
SQL_PAPEIS_SEM_USAGE_NO_SCHEMA = (
    "SELECT coalesce(string_agg(DISTINCT papel, ','), '') FROM ("
    "SELECT a.grantee::regrole::text AS papel "
    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
    "CROSS JOIN LATERAL aclexplode(c.relacl) a "
    "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'S') AND a.grantee <> 0"
    ") x WHERE NOT has_schema_privilege(papel, 'public', 'USAGE')"
)

# --- Estado do modulo ------------------------------------------------------------------

_TRAVA = threading.Lock()
_pool: Any = None
_pool_da_url: str | None = None


class BancoNaoConfigurado(RuntimeError):
    """Nao ha `MOTOR_DATABASE_URL` (ou falta o driver): o motor roda sem banco."""


class BancoIndisponivel(RuntimeError):
    """Configurado, mas a conexao falhou. Distinto de nao-configurado de proposito:
    um e' escolha de operacao, o outro e' incidente -- e o diagnostico os separa."""


class AutocommitProibido(RuntimeError):
    """Escrita numa conexao em autocommit: o carimbo de autor evaporaria em silencio."""


def _driver() -> Any:
    """`ConnectionPool` do psycopg_pool, ou `None` se o extra `db` nao esta instalado."""
    try:
        from psycopg_pool import ConnectionPool
    except ImportError:
        return None
    return ConnectionPool


def url_configurada() -> str | None:
    """A URL de conexao, ou `None`. Valor vazio/em branco conta como ausente."""
    bruto = os.environ.get(ENV_URL, "")
    return bruto.strip() or None


def _sem_segredo(texto: str) -> str:
    """Remove a URL de conexao e a senha dela de uma mensagem de erro.

    O libpq nao costuma citar a senha, mas uma URL malformada faz o proprio parse
    levantar com um fragmento da string de conexao dentro -- e esse texto ia inteiro
    para o JSON do diagnostico. Mascarar aqui e' mais barato que auditar cada driver.
    """
    url = url_configurada()
    if not url:
        return texto
    texto = texto.replace(url, "<" + ENV_URL + ">")
    # A senha e' o trecho entre o primeiro dois-pontos depois do esquema e o arroba; ela
    # some isolada tambem, para o caso de a mensagem citar so' um pedaco da URL.
    achado = re.search(r"://[^:/@\s]+:([^@\s]+)@", url)
    if achado and achado.group(1):
        texto = texto.replace(achado.group(1), "<senha>")
    return texto


def _falha(erro: Exception) -> BancoIndisponivel:
    """Normaliza falha de driver/rede, preservando a CLASSE e escondendo segredo."""
    return BancoIndisponivel(f"{type(erro).__name__}: {_sem_segredo(str(erro))}")


def motivo_indisponivel() -> str | None:
    """`None` = da' para tentar conectar. String = por que nao da', em uma linha."""
    if url_configurada() is None:
        return f"{ENV_URL} nao definida"
    if _driver() is None:
        return (
            "driver psycopg nao instalado -- "
            'python -m pip install "psycopg[binary,pool]>=3.2,<4" -c constraints.txt'
        )
    return None


def configurado() -> bool:
    """Se ha URL E driver. NAO diz que o banco responde -- para isso, `saude()`."""
    return motivo_indisponivel() is None


def _obter_pool() -> Any:
    """Pool aberto, criado sob demanda. Levanta `BancoNaoConfigurado` se nao da'.

    `open=False` + `open(wait=False)`: sem isso o construtor tentaria conectar e
    BLOQUEARIA o boot quando o banco estivesse fora -- justo o que este modulo existe
    para evitar. Com `wait=False` o pool sobe vazio e reconecta sozinho em segundo
    plano, entao o motor se recupera quando o banco volta, sem restart.
    """
    global _pool, _pool_da_url

    motivo = motivo_indisponivel()
    if motivo is not None:
        raise BancoNaoConfigurado(motivo)

    url = url_configurada()
    with _TRAVA:
        # URL trocada (teste, ou reconfiguracao) invalida o pool antigo: sem esta
        # checagem, mudar a env em runtime deixaria conexoes apontando para o banco velho.
        if _pool is not None and _pool_da_url == url:
            return _pool
        if _pool is not None:
            _fechar_sem_trava()

        classe = _driver()
        _pool = classe(
            conninfo=url,
            min_size=POOL_MIN,
            max_size=POOL_MAX,
            timeout=TIMEOUT_POOL_S,
            open=False,
            name="motor-db",
        )
        _pool_da_url = url
        _pool.open(wait=False)
        _LOG.info("pool do banco criado (min=%d max=%d)", POOL_MIN, POOL_MAX)
        return _pool


def _pool_ou_falha() -> Any:
    """`_obter_pool()` com a falha de CRIACAO ja' normalizada.

    Falha ao construir o pool (URL malformada, host inalcancavel) e' banco indisponivel,
    e precisa chegar ao chamador com a classe da excecao original preservada e sem
    segredo. Fica numa funcao propria para que `conexao()`/`transacao()` possam
    chama-la ANTES do `try` que envolve o `yield` -- que e' o que impede excecao do
    chamador de ser convertida.
    """
    try:
        return _obter_pool()
    except BancoNaoConfigurado:
        raise
    except Exception as erro:  # noqa: BLE001 - falha de driver/rede ao abrir o pool
        raise _falha(erro) from erro


def _fechar_sem_trava() -> None:
    global _pool, _pool_da_url
    if _pool is not None:
        try:
            _pool.close()
        except Exception:  # noqa: BLE001 - fechar pool nunca deve derrubar quem chamou
            _LOG.warning("falha ao fechar o pool do banco", exc_info=True)
    _pool = None
    _pool_da_url = None


def fechar_pool() -> None:
    """Encerra o pool. Para o shutdown do app e para isolar testes entre si."""
    with _TRAVA:
        _fechar_sem_trava()


@contextmanager
def conexao() -> Iterator[Any]:
    """Conexao de LEITURA. A transacao e' aberta `READ ONLY`.

    Nao e' documentacao nem convencao: o servidor recusa escrita em tabela permanente e
    DDL dentro dela, e a recusa vale inclusive para funcao `SECURITY DEFINER` chamada de
    dentro -- o modo e' checado no executor, nao pelo papel efetivo.

    LIMITE, para nao prometer mais do que entrega: a garantia e' da TRANSACAO, nao da
    conexao. Um `con.commit()` no meio do bloco encerra esta transacao, e a proxima
    nasce read-write. O que fecha isso de vez e' um papel de leitura dedicado com
    `default_transaction_read_only = on` (D20), nao este comando. Tambem passam, por
    desenho do Postgres: escrita em tabela temporaria ja' existente, `nextval()` e
    `LISTEN`/`NOTIFY`.

    Isso importa porque o guardrail que hoje prova o read-only do piloto
    (`test_leituras_nao_mutam_artefatos`, por snapshot do filesystem) e' CEGO a um
    INSERT -- e ficaria cego sem substituto ate' os papeis do D20 existirem.
    """
    pool = _pool_ou_falha()
    # O `yield` fica FORA de qualquer `except Exception`. Com ele dentro, o
    # `contextlib` relanca no ponto do yield toda excecao do corpo do `with` do
    # chamador -- e um `KeyError` da aplicacao virava `BancoIndisponivel`, com o texto
    # de uma excecao interna arbitraria viajando dentro de uma classe cuja semantica
    # convida a renderizar como `detail` de um 503.
    with ExitStack() as pilha:
        try:
            con = pilha.enter_context(pool.connection())
            con.execute(SQL_SOMENTE_LEITURA)
        except Exception as erro:  # noqa: BLE001 - so' o SETUP e' traduzido
            raise _falha(erro) from erro
        yield con


@contextmanager
def transacao(*, id_usuario: int | str | None) -> Iterator[Any]:
    """Conexao de ESCRITA, com o autor carimbado na transacao.

    `id_usuario` e' obrigatorio como PARAMETRO e pode ser `None` como VALOR: acao de
    sistema existe e o D19 a preve ("sem ela, a acao e' registrada com autoria nula").
    O que nao pode existir e' escrita cujo autor ficou nulo por esquecimento -- por isso
    o parametro e' nomeado e sem default.

    CUIDADO ao usar: um `con.commit()` no meio do bloco encerra a transacao e leva a
    variavel junto (ela e' local a transacao, de proposito). As escritas seguintes do
    MESMO bloco sairiam auditadas com `registrado_por` nulo, sem erro nenhum. Uma
    unidade de trabalho por bloco.
    """
    autor = _normalizar_autor(id_usuario)
    pool = _pool_ou_falha()
    with ExitStack() as pilha:
        try:
            con = pilha.enter_context(pool.connection())
            # Autocommit faria o `set_config(..., true)` rodar na propria transacao
            # implicita e evaporar antes do INSERT: nenhuma excecao, e toda linha de
            # auditoria a partir dali com autor nulo. Falha MUDA, e por isso barrada.
            if getattr(con, "autocommit", False):
                raise AutocommitProibido(
                    "conexao em autocommit: o carimbo de app.id_usuario nao sobreviveria "
                    "ate' a escrita, e a auditoria sairia sem autor"
                )
            # Primeiro comando da transacao: se a escrita seguinte falhar, o autor cai
            # junto no rollback -- variavel local a transacao nao sobrevive ao aborto.
            con.execute(SQL_DEFINIR_AUTOR, (autor,))
        except AutocommitProibido:
            raise
        except Exception as erro:  # noqa: BLE001 - so' o SETUP e' traduzido
            raise _falha(erro) from erro
        yield con


def _normalizar_autor(id_usuario: int | str | None) -> str | None:
    """`None` (sistema) ou digitos. Qualquer outra coisa e' erro de programacao aqui."""
    if id_usuario is None:
        return None
    texto = str(id_usuario).strip()
    if not _PADRAO_ID_USUARIO.match(texto):
        raise ValueError(
            f"id_usuario invalido para app.id_usuario: {id_usuario!r} "
            "(esperado inteiro positivo de ate 18 digitos, ou None para acao de sistema)"
        )
    return texto


def saude(timeout_s: float = TIMEOUT_SAUDE_S) -> dict[str, Any]:
    """Diagnostico para a rota de ADMIN. NUNCA levanta -- o health e' sinal, nao rota.

    Separa tres estados que dao no mesmo para o usuario e sao muito diferentes para
    quem opera: nao configurado (escolha), configurado e fora (incidente), configurado
    e no ar (normal). `migracao` fica `None` enquanto a tabela de controle nao existir,
    que e' o estado de um banco levantado a mao pelo roteiro 001->010.

    NAO vai para o `/api/health`: aquela rota e' livre e foi emudecida de proposito
    (pentest Onda B #8). E o healthcheck do container tambem nao olha o banco -- o
    piloto serve sem ele, e amarrar os dois faria o Docker reiniciar o `web` a cada
    piscada do Postgres, derrubando o que ainda funcionava.
    """
    estado: dict[str, Any] = {
        "configurado": False,
        "conectado": False,
        "postgis": None,
        "servidor": None,
        "migracao": None,
        "provisionamento": None,
        "erro": None,
    }

    motivo = motivo_indisponivel()
    if motivo is not None:
        estado["erro"] = motivo
        return estado

    estado["configurado"] = True
    try:
        with conexao() as con:
            con.execute(SQL_DEFINIR_TIMEOUT, (f"{int(timeout_s * 1000)}ms",))
            con.execute(SQL_PING)
            estado["conectado"] = True
            estado["servidor"] = _primeiro_valor(con, SQL_VERSAO_SERVIDOR)
            # PostGIS pode nao estar habilitado (migration 001 nao rodou): e' informacao,
            # nao falha -- o banco responde, e e' isso que `conectado` afirma.
            estado["postgis"] = _primeiro_valor(con, SQL_VERSAO_POSTGIS, tolerar_erro=True)
            estado["migracao"] = _primeiro_valor(con, SQL_VERSAO_MIGRACAO, tolerar_erro=True)
            estado["provisionamento"] = _provisionamento(con)
    except Exception as erro:  # noqa: BLE001 - health nunca derruba a requisicao
        estado["erro"] = _sem_segredo(str(erro))
    return estado


def _provisionamento(con: Any) -> dict[str, Any]:
    """O D20 esta de pe? Responde com FATO, nao com suposicao.

    A 009 afirma que o `SECURITY DEFINER` impede a aplicacao de forjar linha no
    historico -- mas isso so' vale se quem conecta NAO for o dono do schema. Sendo dono,
    a aplicacao teria `INSERT` direto no historico e poderia `ALTER TABLE ... DISABLE
    TRIGGER` na propria auditoria. Nada no motor detectava esse estado, e ele e' o
    caminho de menor resistencia num deploy apressado.

    `tgenabled`: 'O' = habilitada no modo normal (o padrao) e 'A' = ENABLE ALWAYS, que e'
    o unico pedaco de DDL do D20 e o que resiste a `session_replication_role = replica`
    -- que deixou de exigir superusuario no PostgreSQL 15.
    """
    dados: dict[str, Any] = {
        "usuario": _primeiro_valor(con, SQL_USUARIO_ATUAL, tolerar_erro=True),
        "pode_escrever_no_historico": None,
        "trigger_auditoria": None,
    }
    dados["pode_escrever_no_historico"] = _primeiro_valor(
        con, SQL_PODE_ESCREVER_HISTORICO, (TABELA_HISTORICO,), tolerar_erro=True
    )
    dados["trigger_auditoria"] = _primeiro_valor(
        con, SQL_ESTADO_TRIGGER, (TRIGGER_AUDITORIA, TABELA_AUDITADA), tolerar_erro=True
    )
    # Campo NOVO, aditivo: o antigo fica como estava para nao mudar a forma do health.
    dados["triggers_auditoria"] = _todas_as_linhas(
        con, SQL_TRIGGERS_AUDITORIA, (TABELA_AUDITADA,), tolerar_erro=True
    )
    return dados


def _todas_as_linhas(
    con: Any,
    sql: str,
    parametros: tuple[Any, ...] | None = None,
    *,
    tolerar_erro: bool = False,
) -> dict[str, Any]:
    """Pares (chave, valor) de uma consulta de duas colunas, ou `{}`.

    Mesmo cuidado de SAVEPOINT do `_primeiro_valor`: tabela ausente nao pode abortar a
    transacao e levar as consultas seguintes do health com ela.
    """
    def _ler() -> dict[str, Any]:
        cursor = con.execute(sql, parametros) if parametros else con.execute(sql)
        return {linha[0]: linha[1] for linha in cursor.fetchall()}

    if not tolerar_erro:
        return _ler()
    try:
        with con.transaction():
            return _ler()
    except Exception:  # noqa: BLE001 - ausencia de tabela e' informacao, nao erro
        return {}


def _primeiro_valor(
    con: Any,
    sql: str,
    parametros: tuple[Any, ...] | None = None,
    *,
    tolerar_erro: bool = False,
) -> Any:
    """Primeira coluna da primeira linha, ou `None`.

    Com `tolerar_erro`, a consulta roda em SAVEPOINT: sem ele, uma tabela ausente
    aborta a transacao inteira no PostgreSQL e as consultas SEGUINTES falhariam com
    "current transaction is aborted" -- o health perderia o `migracao` E o `postgis`
    por causa de um so' deles faltar.
    """
    if not tolerar_erro:
        linha = con.execute(sql, parametros).fetchone() if parametros else con.execute(sql).fetchone()
        return linha[0] if linha else None
    try:
        with con.transaction():
            cursor = con.execute(sql, parametros) if parametros else con.execute(sql)
            linha = cursor.fetchone()
            return linha[0] if linha else None
    except Exception:  # noqa: BLE001 - ausencia de extensao/tabela e' informacao
        return None
