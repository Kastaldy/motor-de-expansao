"""Ferramenta de linha de comando do banco (`python -m motor_expansao.db`).

Nenhum comando SQL parte daqui — a decisao de 25/08 vale tambem para os testes. O que se
prova sem banco e', justamente, o que decide se a ferramenta e' segura de entregar a quem
executa: de onde ela tira a credencial, o que ela considera pendente, e se ela percebe uma
migration que foi editada depois de aplicada.
"""

from __future__ import annotations

import argparse
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from motor_expansao.db import cli, postgres


def test_credencial_de_ddl_prefere_a_de_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aplicar migration e' DDL, e o D20 tira DDL do papel `app` para que a aplicacao nao
    possa desligar a propria trigger de auditoria. Se o runner usasse a mesma URL do
    piloto, o D20 seria anulado em silencio -- e a auditoria da 009 deixaria de proteger."""
    monkeypatch.setenv(postgres.ENV_URL, "postgresql://app:x@localhost/banco")
    monkeypatch.setenv(cli.ENV_URL_ADMIN, "postgresql://postgres:y@localhost/banco")
    assert cli._url_de_ddl() == "postgresql://postgres:y@localhost/banco"


def test_sem_url_de_admin_cai_para_a_do_piloto(monkeypatch: pytest.MonkeyPatch) -> None:
    """No banco de teste local os dois papeis sao a mesma pessoa, e exigir duas envs so'
    para isso atrapalharia. O `conferir` e' quem denuncia quando isso vale em PRODUCAO."""
    monkeypatch.setenv(postgres.ENV_URL, "postgresql://postgres:x@localhost/teste")
    monkeypatch.delenv(cli.ENV_URL_ADMIN, raising=False)
    assert cli._url_de_ddl() == "postgresql://postgres:x@localhost/teste"


def test_sem_credencial_nenhuma_falha_com_instrucao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(postgres.ENV_URL, raising=False)
    monkeypatch.delenv(cli.ENV_URL_ADMIN, raising=False)
    with pytest.raises(SystemExit) as erro:
        cli._conectar_para_ddl()
    assert cli.ENV_URL_ADMIN in str(erro.value)


def test_pendentes_sao_as_que_o_banco_nao_registrou() -> None:
    manifesto = cli._manifesto()
    versoes = [m["versao"] for m in manifesto]
    # nada registrado -> tudo pendente
    pendentes, alteradas = cli._diagnostico(manifesto, {})
    assert [m["versao"] for m in pendentes] == versoes
    assert alteradas == []


def test_registro_com_hash_correto_nao_acusa_alteracao() -> None:
    manifesto = cli._manifesto()
    registradas = {m["versao"]: cli._sha256_do_arquivo(m["arquivo"]) for m in manifesto}
    pendentes, alteradas = cli._diagnostico(manifesto, registradas)
    assert pendentes == []
    assert alteradas == []


def test_migration_editada_depois_de_aplicada_e_denunciada() -> None:
    """O defeito que a `convencoes.md` §7 proibe por prosa: editar migration ja' aplicada
    deixa o banco num estado que NENHUM arquivo descreve. Aqui ele vira sinal."""
    manifesto = cli._manifesto()
    registradas = {m["versao"]: cli._sha256_do_arquivo(m["arquivo"]) for m in manifesto}
    registradas["007"] = "0" * 64  # como se o arquivo tivesse mudado desde a aplicacao

    pendentes, alteradas = cli._diagnostico(manifesto, registradas)
    assert pendentes == []
    assert [m["versao"] for m in alteradas] == ["007"]


def test_hash_ignora_fim_de_linha(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CRLF numa estacao Windows nao pode fazer a mesma migration parecer alterada — o
    defeito viveria so' na maquina de quem revisa, e passaria no CI Linux."""
    pasta = tmp_path / "migracoes"
    pasta.mkdir()
    (pasta / "x.sql").write_bytes(b"BEGIN;\r\nSELECT 1;\r\nCOMMIT;\r\n")
    monkeypatch.setattr(cli, "MIGRACOES", pasta)
    com_crlf = cli._sha256_do_arquivo("x.sql")

    (pasta / "x.sql").write_bytes(b"BEGIN;\nSELECT 1;\nCOMMIT;\n")
    assert cli._sha256_do_arquivo("x.sql") == com_crlf


def test_o_contrato_conferido_cobre_as_12_tabelas_do_modelo() -> None:
    """A lista de `conferir` e a da §0 da `verificacao.md` tem de ser a MESMA: se
    divergirem, a ferramenta passa a atestar um contrato que o documento nao descreve.

    Eram ONZE ate' a D30, que somou `sessoes` (migration 018). O nome deste teste carrega o
    numero pelo mesmo motivo que o do `..._as_8_funcoes` logo abaixo: numero no nome que
    deixou de ser o numero e' a deriva doc-contra-codigo que esta suite existe para pegar.

    ESTE ARQUIVO E' O QUARTO LUGAR onde os numeros da §0 vivem -- os outros tres sao a
    propria `verificacao.md`, o `NUMEROS_DA_SECAO_ZERO` do `cli.py` e o `test_migracoes.py`.
    A nota da 018 dizia "tres lugares" ate' esta assercao ficar vermelha com `12 == 11`, e
    foi corrigida la'.
    """
    assert len(cli.TABELAS_DO_MODELO) == 12
    assert postgres.TABELA_MIGRACOES not in cli.TABELAS_DO_MODELO, (
        "a tabela de controle e' do motor, nao do modelo — some-la mudaria os seis numeros"
    )


def test_endurecimento_esperado_cobre_as_8_funcoes() -> None:
    """Oito funcoes, e as DUAS gravadoras do D19 seguem as unicas `SECURITY DEFINER`.

    Eram sete ate' a D29, que somou `exige_geom_coerente` (migration 017). O nome deste teste
    carrega o numero de proposito: um teste batizado com um numero que deixou de ser o numero e'
    a mesma deriva doc-contra-codigo que a suite existe para pegar.

    A segunda asserçao passa a valer DE GRAÇA para a funcao nova: ela NAO e' `SECURITY DEFINER`
    -- so' levanta excecao, nao escreve nada --, e se alguem a promover a definer sem pensar,
    este teste acusa.
    """
    assert len(cli.FUNCOES_ESPERADAS) == 8
    definers = [nome for nome, (secdef, _) in cli.FUNCOES_ESPERADAS.items() if secdef]
    assert sorted(definers) == [
        "registra_perfil_permissoes_historico",
        "registra_perfil_permissoes_truncate",
    ]
    # As tres de `atualizado_em` nao tocam o schema `public`: so' `now()`.
    for nome, (_, caminho) in cli.FUNCOES_ESPERADAS.items():
        if nome.startswith("set_atualizado_em"):
            assert caminho == "pg_catalog, pg_temp"


def test_manifesto_do_pacote_e_o_mesmo_que_a_cli_le() -> None:
    """A CLI resolve o manifesto por caminho relativo ao PACOTE, nao ao repositorio: e'
    assim que ela funciona dentro da imagem, onde nao ha checkout."""
    do_pacote = json.loads(cli.MANIFESTO.read_text(encoding="utf-8"))["migracoes"]
    assert [m["versao"] for m in do_pacote] == [m["versao"] for m in cli._manifesto()]
    assert cli.MIGRACOES.parent.name == "db"


def test_sql_de_registro_e_idempotente() -> None:
    """Rodar `registrar` duas vezes por engano nao pode custar nada."""
    assert "ON CONFLICT" in cli.SQL_REGISTRAR
    assert "DO NOTHING" in cli.SQL_REGISTRAR


def test_contagens_conferem_com_os_seis_numeros_da_secao_zero() -> None:
    esperado: dict[str, Any] = dict(cli.NUMEROS_DA_SECAO_ZERO)
    assert esperado == {
        # 49 desde a D30, que criou `sessoes` (migration 018) e somou tres: o de PK, o
        # UNIQUE de `token_hash_sessao` (a consulta quente) e o da FK `id_usuario`. Era 46
        # desde a D24 (os tres indices de expressao sobre `metadados`; o de
        # `idx_usuarios_login_ativo` da D23 levou de 42 a 43). Este numero e o da §0
        # da `verificacao.md` tem de andar JUNTOS — se um ficar para tras, um banco
        # correto passa a acusar DIVERGENTE.
        "indices": 49,
        # 14 desde a 019: `ck_usuarios_prazo_exige_troca`, que impede senha PROPRIA com prazo
        # de validade -- o estado que faria a pessoa ser barrada com a senha certa. Era 13 desde
        # a D30 (`chk_sessao_expira_apos_criacao`, a guarda contra sessao que nasce vencida --
        # sem ela a pessoa veria "sessao expirada" logo apos digitar a senha certa, que e' o pior
        # diagnostico possivel). Desde 18/09/2026 este numero tambem e' conferido contra as
        # MIGRATIONS, e nao so' contra um banco vivo, por `test_migracoes.py` -- ate' entao nada
        # o cobria no CI, que nao tem Postgres.
        "constraints CHECK": 14,
        # 12 desde a D30: `sessoes.id_usuario`, a UNICA FK do modelo com ON DELETE CASCADE
        # (sessao nao e' registro a preservar, e sessao orfa decidindo acesso e' o que nao
        # se quer). Toda FK ganha indice, e e' por isso que os indices somaram 3 e nao 2.
        "chaves estrangeiras": 12,
        # 7 desde a D29: a guarda de coerencia (migration 017) poe uma trigger em
        # `areas_estudo` e outra em `contratos`. Mesma regra do numero acima -- este e o da
        # §0 da `verificacao.md` andam JUNTOS, senao um banco correto acusa DIVERGENTE.
        "triggers": 7,
        "colunas geometricas": 7,
    }


# --------------------------------------------------------------------------------------
# `privilegios` — a reposição do guardrail READ-ONLY (F6.2)
# --------------------------------------------------------------------------------------


class _ConPrivilegios:
    """Dublê que responde por trecho de SQL. `respostas` mapeia marca -> valor."""

    def __init__(self, respostas: dict[str, Any], padrao: Any = False) -> None:
        self.respostas = respostas
        self.padrao = padrao
        self.executados: list[str] = []
        self._valor: Any = None

    def execute(self, sql: str, params: Any = None) -> _ConPrivilegios:
        self.executados.append(sql)
        self._valor = self.padrao
        # Igualdade EXATA antes de conter: `current_user` aparece em quase toda consulta de
        # privilégio, então casar por trecho fazia a chave do usuário sequestrar todas elas.
        if sql in self.respostas:
            self._valor = self.respostas[sql]
            return self
        for marca, valor in self.respostas.items():
            if marca in sql:
                self._valor = valor
                break
        return self

    def fetchone(self) -> tuple[Any, ...]:
        # Resposta ja' em tupla volta COMO ESTA': e' o caso da consulta de duas colunas
        # (`SQL_DEFAULT_ACL_DO_DONO` devolve `(dono, papeis)`). Embalar de novo daria uma
        # tupla de um elemento e o desempacotamento do chamador estouraria.
        if isinstance(self._valor, tuple):
            return self._valor
        return (self._valor,)

    def fetchall(self) -> list[tuple[Any, ...]]:
        """Para a consulta das triggers, que devolve N linhas de (nome, estado).

        Se a resposta registrada ja' for uma lista de tuplas, devolve como esta' -- e' o
        caso em que o teste quer controlar as duas triggers da secao 7, inclusive o estado
        de §7 colado pela METADE. Senao, embala o valor unico, para os dubles antigos nao
        precisarem saber desta consulta.
        """
        if isinstance(self._valor, list):
            return self._valor
        return [("trg_perfil_permissoes_auditoria", self._valor)]

    def __enter__(self) -> _ConPrivilegios:
        return self

    def __exit__(self, *_a: Any) -> None:
        return None


def _rodar_privilegios(
    monkeypatch: pytest.MonkeyPatch, respostas: dict[str, Any]
) -> tuple[int, _ConPrivilegios]:
    con = _ConPrivilegios(respostas)
    falso = types.SimpleNamespace(connect=lambda _url: con)
    monkeypatch.setitem(sys.modules, "psycopg", falso)
    monkeypatch.setenv(postgres.ENV_URL, "postgresql://fake/motor")
    codigo = cli.cmd_privilegios(argparse.Namespace())
    return codigo, con


#: Um cluster provisionado como o D20 manda: nega tudo do lado negativo, concede o positivo.
_D20_DE_PE: dict[str, Any] = {
    postgres.SQL_USUARIO_ATUAL: "app",
    "has_schema_privilege": False,
    # Os marcadores citam TABELA + PRIVILÉGIO porque `perfil_permissoes_historico` sozinho
    # também aparece na consulta de dono (`pg_class`) — casar por ele fazia aquela chave
    # nunca ser consultada, e o teste do dono passava sem testar nada.
    "'perfil_permissoes_historico', 'INSERT'": False,
    "'perfil_permissoes_historico', 'UPDATE'": False,
    "'perfil_permissoes_historico', 'DELETE'": False,
    "'perfil_permissoes', 'TRUNCATE'": False,
    "'eventos', 'UPDATE'": False,
    "'eventos', 'DELETE'": False,
    "has_database_privilege": False,
    "pg_class": False,
    "'eventos', 'INSERT'": True,
    "has_sequence_privilege": True,
    "'usuarios', 'UPDATE'": True,
    "spatial_ref_sys": True,
    # `sessoes` (D30), acrescentada em 23/09/2026. Um cluster "provisionado como o D20 manda"
    # passou a incluir a escrita na sessao -- e o `DELETE` NEGADO, porque revogar e' `UPDATE`
    # de `revogada_em_sessao` e o expurgo de retencao anonimiza em vez de apagar.
    "'sessoes', 'INSERT'": True,
    "'sessoes', 'UPDATE'": True,
    "'sessoes', 'SELECT'": True,
    "'sessoes', 'DELETE'": False,
    "tgenabled": "A",
    # A ACL das funcoes de auditoria (secao 2 do D20), acrescentada em 05/10/2026: era a
    # TERCEIRA camada que o script endurecia e nenhum instrumento conferia. `False` aqui
    # e' o estado bom -- `PUBLIC` NAO executa.
    postgres.SQL_ACL_FUNCOES_DE_AUDITORIA: [
        ("registra_perfil_permissoes_historico", False),
        ("registra_perfil_permissoes_truncate", False),
    ],
    # A QUARTA camada (secao 6), acrescentada em 05/10/2026. UMA LINHA POR TIPO de
    # objeto: `(tipo, quem_cria, quem_recebe, chega_a_quem_conecta)`. Agregar os dois
    # tipos escondia a lacuna -- medido: grantee errado so' em TABLES passava verde.
    postgres.SQL_DONO_DA_TABELA_AUDITADA: "reservas_owner",
    postgres.SQL_DEFAULT_ACL_DO_DONO: [
        ("S", "reservas_owner", "app", True),
        ("r", "reservas_owner", "app", True),
    ],
    #: Papeis com privilegio de tabela no schema e SEM `USAGE` nele. Vazio = estado bom.
    postgres.SQL_PAPEIS_SEM_USAGE_NO_SCHEMA: "",
    #: A SEXTA classe (06/10/2026): papel com privilegio no schema E poder de cluster.
    #: Vazio = estado bom.
    postgres.SQL_PAPEIS_COM_PODER_DE_CLUSTER: "",
    #: A SETIMA classe (06/10/2026): o que a secao 2 revoga de PUBLIC, aberto para alguem
    #: que nao e' o dono. Vazio = estado bom.
    postgres.SQL_PODERES_ABERTOS_NO_SCHEMA: "",
    # O QUINTO furo (05/10/2026): `USAGE` no schema. Sem ele o papel nao VE a tabela, e
    # as dezesseis checagens seguintes degradam acusando migration ausente.
    postgres.SQL_USAGE_NO_SCHEMA: True,
    #: A tabela auditada e' visivel. Nota: este SQL e' textualmente IGUAL ao
    #: `cli.SQL_TEM_TABELA_DE_CONTROLE` -- a mesma pergunta, parametro diferente --, e o
    #: duble casa por texto, nao por parametro. Inocuo aqui: `cmd_privilegios` nao usa o
    #: outro.
    postgres.SQL_TABELA_AUDITADA_VISIVEL: True,
    #: A pergunta sobre o parametro da sessao e' `has_parameter_privilege` do papel
    #: CONECTADO, nao `EXISTS` sobre `pg_parameter_acl` -- que e' catalogo do CLUSTER e
    #: acusava concessao feita em outro banco, a outro papel (medido em 06/10/2026,
    #: saindo `exit 1` com o diagnostico errado). `False` e' o estado bom.
    postgres.SQL_PARAMETRO_DA_SESSAO: "",
    #: Sequences cujo `USAGE` nao casa com o `INSERT` na tabela que as possui, nos DOIS
    #: sentidos e com universo derivado de `pg_depend`. Vazio = estado bom (medido nas
    #: oito do banco de ensaio: casa em todas).
    postgres.SQL_SEQUENCES_DESALINHADAS: "",
    #: A DECIMA classe (07/10/2026), duas portas. Vazio e' o estado bom nas duas.
    #: Pertencimento nao cria entrada de ACL; privilegio de coluna nao entra em `relacl`.
    #: Medido: `privilegios` saia `OK` em cinco estados ruins antes destas checagens.
    postgres.SQL_PAPEIS_DE_QUEM_CONECTOU: "",
    postgres.SQL_PRIVILEGIO_DE_COLUNA: "",
    #: A SEXTA porta da decima classe (07/10/2026): `PUBLIC` em ACL de tabela.
    postgres.SQL_ACL_DE_PUBLIC_EM_TABELA: "",
    postgres.SQL_PAPEIS_COM_ACL_NO_SCHEMA: "",
    postgres.SQL_PARAMETRO_FIXADO_POR_BANCO_OU_PAPEL: "",
    postgres.SQL_GRANTEE_A_MAIS_NO_DEFAULT_ACL: "",
    postgres.SQL_RLS_LIGADO_NO_SCHEMA: "",
    postgres.SQL_FUNCAO_SECURITY_DEFINER_ALHEIA: "",
    postgres.SQL_O_QUE_O_D20_NAO_CRIA: "",
    postgres.SQL_FUNCAO_COM_DONO_ALHEIO: "",
}


def test_provisionamento_completo_passa(monkeypatch: pytest.MonkeyPatch) -> None:
    codigo, _ = _rodar_privilegios(monkeypatch, dict(_D20_DE_PE))
    assert codigo == 0


def test_nada_e_escrito_no_banco(monkeypatch: pytest.MonkeyPatch) -> None:
    """A checagem lê CATÁLOGO. Tentar escrever para ver se falha deixaria lixo, dependeria de
    rollback e, numa tabela append-only, a própria tentativa viraria linha."""
    _, con = _rodar_privilegios(monkeypatch, dict(_D20_DE_PE))
    for sql in con.executados:
        # O VERBO, e não o texto solto: `'TRUNCATE'` aparece como NOME DE PRIVILÉGIO dentro
        # de `has_table_privilege(...)`, que é leitura pura. Foi o falso positivo da 1ª versão.
        verbo = sql.strip().split(None, 1)[0].upper()
        assert verbo == "SELECT", f"a checagem tentou escrever: {sql!r}"


@pytest.mark.parametrize(
    "marca",
    [
        "has_schema_privilege",  # DDL no papel da aplicação
        "'perfil_permissoes_historico', 'INSERT'",  # forjar auditoria
        "has_database_privilege",  # TEMP TABLE: o caminho da forja do D21
        "pg_class",  # dono desliga a própria trigger
        # O SQL INTEIRO, nao o nome do catalogo: a pergunta e'
        # `has_parameter_privilege` do papel conectado desde 06/10/2026, e deixar a
        # marca antiga aqui fazia este caso nao casar com consulta nenhuma -- o teste
        # passaria a cobrar `exit 1` de um estado que ele nao sabotou.
        postgres.SQL_PARAMETRO_DA_SESSAO,  # SET session_replication_role
    ],
)
def test_cada_poder_indevido_reprova(monkeypatch: pytest.MonkeyPatch, marca: str) -> None:
    respostas = dict(_D20_DE_PE)
    respostas[marca] = True
    codigo, _ = _rodar_privilegios(monkeypatch, respostas)
    assert codigo == 1, f"{marca} concedido e a checagem passou"


def test_falta_da_sequence_reprova(monkeypatch: pytest.MonkeyPatch) -> None:
    """`GRANT INSERT` na tabela NÃO cobre a sequence do `BIGSERIAL` — e sem ela todo INSERT
    morre por permissão negada, só em runtime."""
    respostas = dict(_D20_DE_PE)
    respostas["has_sequence_privilege"] = False
    codigo, _ = _rodar_privilegios(monkeypatch, respostas)
    assert codigo == 1


def test_sequence_com_usage_desalinhado_reprova(monkeypatch: pytest.MonkeyPatch) -> None:
    """O sentido que NENHUM instrumento olhava: `USAGE` numa sequence cuja tabela o papel
    nao pode inserir e' privilegio excedente.

    Medido em 06/10/2026 no banco de ensaio: um `GRANT USAGE ON ALL SEQUENCES IN SCHEMA
    public TO app` deixava as cinco checagens nomeadas verdes, `conferir` verde e a
    contagem 12/1/3 verde -- e dava ao `app` o `USAGE` das tres sequences das tabelas de
    permissao, as que ele nao pode escrever. Com a regra derivada: `exit 1`, nomeando as
    tres.
    """
    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_SEQUENCES_DESALINHADAS] = (
        "perfis_id_perfil_seq (USAGE sem INSERT em perfis)"
    )
    codigo, _ = _rodar_privilegios(monkeypatch, respostas)
    assert codigo == 1


def test_sequence_orfa_com_usage_reprova(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sequence SEM tabela dona e com `USAGE` e' privilegio excedente, e a 1a versao desta
    regra NAO a via: o `JOIN pg_depend` era interno, entao a orfa desaparecia do resultado
    e a consulta certificava o banco como alinhado.

    Medido em 06/10/2026 no cluster de ensaio: com uma `seq_sem_dona` segurando `USAGE`
    para o `app`, a versao com `JOIN` interno devolvia **oito linhas, zero desalinhadas** --
    e, pior, a regra de leitura que acompanha a consulta ("esperado: oito linhas") CONFIRMAVA
    o estado ruim, porque oito era o numero esperado. A consulta por nome, que esta regra
    deveria substituir, via nove e acusava. Agora o `JOIN` e' `LEFT` e `deptype IN ('a','i')`,
    o que tambem passa a ver coluna `IDENTITY` (medido: ela gera `deptype = 'i'`).
    """
    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_SEQUENCES_DESALINHADAS] = (
        "seq_sem_dona (USAGE numa sequence SEM TABELA DONA)"
    )
    codigo, _ = _rodar_privilegios(monkeypatch, respostas)
    assert codigo == 1


def test_a_regra_das_sequences_nao_depende_de_join_interno(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Crava a FORMA da consulta, nao so' o comportamento: `LEFT JOIN` e os dois `deptype`.

    Sem isto, um refactor bem-intencionado volta ao `JOIN` interno (que le mais bonito) e
    a orfa desaparece de novo, em silencio -- que foi exatamente como o defeito nasceu.
    """
    sql = postgres.SQL_SEQUENCES_DESALINHADAS
    assert "LEFT JOIN pg_depend" in sql, "a orfa precisa sobreviver ao join"
    assert "LEFT JOIN pg_class t" in sql, "a tabela dona ausente precisa virar NULL"
    assert "deptype IN ('a', 'i')" in sql, "coluna IDENTITY gera deptype 'i', nao 'a'"
    assert "SEM TABELA DONA" in sql, "a orfa precisa se nomear no diagnostico"


def test_parametro_da_sessao_pergunta_pelo_papel_conectado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`pg_parameter_acl` e' catalogo COMPARTILHADO do cluster (`relisshared = true`,
    medido), entao `EXISTS (...)` sobre ele acusa concessao feita em OUTRO banco, a OUTRO
    papel. Reproduzido ao vivo em 06/10/2026: um `GRANT SET ON PARAMETER
    session_replication_role TO auditoria` em `outro_banco_ensaio` fazia este comando sair
    `exit 1` com o diagnostico errado, enquanto `has_parameter_privilege('app', ...)` era
    `false`. Este teste crava a pergunta certa: nenhuma consulta le o catalogo.
    """
    _, con = _rodar_privilegios(monkeypatch, dict(_D20_DE_PE))
    assert any(
        "has_parameter_privilege" in sql for sql in con.executados
    ), "ninguem perguntou se o papel conectado pode trocar o parametro"
    assert not [
        sql for sql in con.executados if "pg_parameter_acl" in sql
    ], "a checagem voltou a ler o catalogo COMPARTILHADO do cluster"


def test_dono_da_tabela_auditada_filtra_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem `relnamespace`, uma tabela homonima noutro schema entra na conta e o `bool_or`
    devolve `true` -- "o papel e' dono da juncao auditada" -- com a de `public` certa."""
    _, con = _rodar_privilegios(monkeypatch, dict(_D20_DE_PE))
    dono = [sql for sql in con.executados if "'perfil_permissoes_historico', 'eventos'" in sql]
    assert dono, "a consulta de dono das tabelas auditadas desapareceu"
    for sql in dono:
        assert "relnamespace" in sql and "nspname" in sql, (
            f"a consulta de dono voltou a aceitar tabela de qualquer schema: {sql!r}"
        )


def test_parametro_da_sessao_olha_todo_papel_comum(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A pergunta e' por TODO papel comum, nao pelos tres nomes nem pelo conectado.

    Historico desta checagem, em tres dias: `EXISTS` sobre `pg_parameter_acl` (falso alarme,
    porque o catalogo e' compartilhado pelo cluster) -> `has_parameter_privilege(current_user)`
    (ponto cego) -> os tres papeis. Medido no meio do caminho: com a concessao feita a
    `auditoria` em OUTRO banco do cluster, a pergunta pelo `app` saia `f` e no banco do
    piloto `SET ROLE auditoria; SET session_replication_role = replica` FUNCIONAVA.
    """
    sql = postgres.SQL_PARAMETRO_DA_SESSAO
    # O universo deixou de ser a lista de tres nomes em 07/10/2026: tres rodadas de ensaio
    # seguidas acharam privilegio entrando por um papel FORA da lista, invisivel a toda
    # consulta que pergunta pelos tres. Agora o universo e' derivado, e o teste crava isso.
    assert "'app', 'auditoria', 'etl'" not in sql, (
        "voltar a' lista de tres nomes deixa um quarto papel invisivel"
    )
    # E o `NOT rolsuper` SAIU no mesmo dia, horas depois, porque eu o tinha posto aqui com
    # a justificativa "superusuario pode tudo por definicao" -- que e' verdade e nao vem ao
    # caso: o que esta consulta faz e' ENUMERAR quem pode desligar as triggers, e um
    # superusuario novo e' exatamente quem o operador precisa ver nessa lista. Medido:
    # `CREATE ROLE intruso LOGIN SUPERUSER` -> `PRIVILEGIOS OK`, exit 0, com o `intruso`
    # lendo 79 linhas de `perfil_permissoes_historico`.
    assert "NOT rolsuper" not in sql, (
        "o `NOT rolsuper` esconde o pior caso desta linha: um superusuario novo"
    )
    assert "datdba" in sql, (
        "quem sai e' o DONO do banco, que e' superusuario por desenho -- e sai por SER dono"
    )
    assert "current_user" not in sql, "perguntar so' pelo conectado deixa os demais cegos"
    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_PARAMETRO_DA_SESSAO] = "auditoria"
    codigo, _ = _rodar_privilegios(monkeypatch, respostas)
    assert codigo == 1
    assert "auditoria" in capsys.readouterr().out, (
        "o relatorio tem de dizer QUEM pode, nao so' que alguem pode"
    )


def test_pertencimento_a_papel_reprova(monkeypatch: pytest.MonkeyPatch) -> None:
    """A DECIMA classe: o privilegio chega por uma porta que o instrumento nao olhava.

    Pertencimento NAO cria entrada de ACL, entao `relacl`, `role_table_grants` e a lista
    nominal de `has_table_privilege` ficam todas intactas. Medido em 07/10/2026, com
    `privilegios` saindo `PRIVILEGIOS OK` e exit 0:

      GRANT pg_write_all_data TO auditoria  -> `auditoria` faz DELETE no append-only
      GRANT etl TO app                      -> `app` faz TRUNCATE nas tres de referencia

    O universo da regra sao os papeis que tem privilegio no schema (derivado de `relacl`)
    mais o conectado -- olhar so' o conectado deixava passar o primeiro caso.
    """
    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_PAPEIS_DE_QUEM_CONECTOU] = "auditoria -> pg_write_all_data"
    codigo, _ = _rodar_privilegios(monkeypatch, respostas)
    assert codigo == 1


def test_public_em_tabela_reprova(monkeypatch: pytest.MonkeyPatch) -> None:
    """A SEXTA porta: `PUBLIC` vale para todo papel e nao e' nome nenhum.

    A secao 3 do script faz dois `REVOKE ... FROM PUBLIC` em tabela -- ela trata
    `PUBLIC`-em-tabela como ameaca -- e nada conferia se fechou. Medido em 07/10/2026:
    `GRANT DELETE ON perfil_permissoes_historico TO PUBLIC` deixa as QUINZE conferencias
    manuais do pacote byte a byte identicas ao estado bom, e o `app` faz `DELETE` de 15
    linhas na tabela append-only. As consultas que fecham as outras cinco portas excluiam
    `PUBLIC` por construcao, com `a.grantee <> 0`.
    """
    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_ACL_DE_PUBLIC_EM_TABELA] = "perfil_permissoes_historico (DELETE)"
    codigo, _ = _rodar_privilegios(monkeypatch, respostas)
    assert codigo == 1


def test_as_consultas_de_acl_nao_excluem_public(monkeypatch: pytest.MonkeyPatch) -> None:
    """Crava a FORMA: `PUBLIC` (grantee 0) nao pode ser filtrado fora das duas consultas
    que existem para ver privilegio de quem nao e' o dono.

    `a.grantee <> 0` le como "ignore o pseudo-papel", e e' o oposto do que se quer: ele e'
    o grantee que alcanca TODOS os papeis de uma vez. Medido: com o filtro, a consulta de
    coluna devolvia zero linha para `GRANT UPDATE (id_perfil) ... TO PUBLIC`; sem ele,
    devolve `- | usuarios.id_perfil | UPDATE`.
    """
    assert "a.grantee <> 0" not in postgres.SQL_PRIVILEGIO_DE_COLUNA, (
        "a consulta de coluna voltou a excluir PUBLIC"
    )
    assert "a.grantee = 0" in postgres.SQL_ACL_DE_PUBLIC_EM_TABELA, (
        "a consulta de ACL de tabela tem de perguntar EXATAMENTE por PUBLIC"
    )


def test_arvore_de_papeis_nao_tem_universo_de_privilegio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    r"""A arvore se responde sobre `pg_auth_members` inteiro -- nenhum universo, nenhuma lista.

    Esta checagem teve tres formas, e as duas primeiras aprovaram estados ruins medidos:

      1a  olhava so' o papel conectado     ->  `GRANT pg_write_all_data TO auditoria` passava
      2a  duas direcoes, universo de ACL   ->  a cadeia de DOIS niveis passava

    A 2a trocou a lista de tres nomes por um universo derivado de `relacl`, e isso parecia
    fechar a familia inteira. Nao fecha: um universo derivado da ACL ainda e' ESTREITO.
    Medido em 07/10/2026:

        GRANT pg_read_all_data TO relatorios;  GRANT relatorios TO consultor;

        o motor  ->  "ok    a arvore de papeis esta plana, nas duas direcoes"
                     PRIVILEGIOS OK, exit 0
        e o `consultor`, com senha propria:
                 ->  SELECT count(*) FROM perfil_permissoes_historico  ->  47

    `relatorios` tira o poder de um papel INTERNO, entao nao aparece em `relacl` nem como
    `m.member` nem como `m.roleid` -- as duas metades olhavam o mesmo universo estreito e a
    cadeia passava por fora das duas.

    O `\du` tambem nao mostra nada disso: no PG 16+ o pertencimento saiu para o `\drg`.

    Teste de FORMA, e com uma asserção NEGATIVA: o defeito da 2a forma era justamente ter
    `aclexplode` aqui, e nenhum estado de um cluster novo o revela.
    """
    sql = postgres.SQL_PAPEIS_DE_QUEM_CONECTOU

    assert "pg_auth_members" in sql, "a arvore se le em `pg_auth_members`"
    assert "aclexplode" not in sql, (
        "a arvore NAO se filtra por quem tem ACL: a cadeia de dois niveis passa por fora"
    )
    assert "'app'" not in sql and "'auditoria'" not in sql, "...nem por lista de nomes"
    # A 4a forma, no fim do mesmo dia. Eu tinha escrito aqui que "papel interno ou
    # superusuario como MEMBRO nao acrescenta achado", e a rodada 31 mediu o contrario:
    #
    #     GRANT auditoria TO pg_monitor   ->  (0 linha), com a armadilha ARMADA e muda
    #     e no dia em que alguem recebe pg_monitor -- gesto rotineiro de monitoracao --
    #     a linha que aparece e' `consultor -> pg_monitor`, que se le como inofensiva
    #     e nao nomeia `auditoria` em lugar nenhum
    #
    # Saem so' as arestas NATIVAS do PostgreSQL, as duas pontas internas. Medido: no estado
    # bom isso da zero linha igual, porque toda aresta nativa e' pg_ -> pg_.
    assert "NOT mem.rolsuper" not in sql, (
        "`GRANT auditoria TO pg_monitor` fica mudo se o membro for filtrado"
    )
    assert "NOT (mem.rolname LIKE" in sql and "AND mae.rolname LIKE" in sql, (
        "o filtro e' a ARESTA nativa (as duas pontas internas), nao a ponta do membro"
    )
    assert "mae.rolsuper" not in sql, (
        "...e a MAE fica livre: `pg_write_all_data` como mae e' o caso da 1a forma"
    )
    assert "inherit_option" in sql, (
        "`WITH SET TRUE, INHERIT FALSE` alcanca por `SET ROLE`; o diagnostico tem de dizer qual e'"
    )

    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_PAPEIS_DE_QUEM_CONECTOU] = (
        "consultor -> relatorios, relatorios -> pg_read_all_data"
    )
    codigo, _ = _rodar_privilegios(monkeypatch, respostas)
    assert codigo == 1, "a cadeia de dois niveis tem de REPROVAR"


def test_aplicar_explica_a_janela_em_vez_de_estourar() -> None:
    """A janela entre aplicar e registrar, achada na r33 -- teste de FORMA.

    20 das 21 migrations trazem `BEGIN`/`COMMIT` no proprio arquivo (medido), e a sequencia
    do laco e' `execute(sql)` -> `INSERT` no registro -> `commit()`. Logo o `execute` JA'
    COMMITOU a migration quando o registro ainda nao foi gravado: morrer nessa fresta deixa
    a migration APLICADA e NAO REGISTRADA.

    Medido deterministicamente (sem depender de timing, porque o estado se reproduz
    apagando o registro sem desfazer o DDL):

        `estado`   ->  registradas: 6 / pendentes: 006..020 / exit 0, SEM aviso
        a errata   ->  le esse estado como "e' retomada, SIGA"
        `aplicar`  ->  psycopg.errors.DuplicateTable, traceback cru, exit 1

    Fechar a janela exigiria gravar o registro DENTRO da transacao da migration, o que o
    `COMMIT` dela impede. Entao o conserto e' reconhecer o estado e dizer a cura.

    Pelo SQLSTATE e nao pela classe do driver: `psycopg` e' importado dentro de `_conectar`,
    e `except psycopg.errors...` no laco estourava com `NameError` em RUNTIME -- o
    `import motor_expansao.db.cli` passava. Terceira vez nesta sessao que um nome de outro
    escopo passou pelo import e morreu na execucao.
    """
    import inspect
    import re as _re

    bruto = inspect.getsource(cli.cmd_aplicar)
    # SEM os comentarios. A 1a versao deste teste olhava `inspect.getsource` cru e passou
    # por uma sabotagem que deixou a tupla com UM sqlstate -- porque os outros cinco
    # seguiam no comentario logo acima dela. Verificacao que casa com a DESCRICAO da coisa
    # em vez da coisa e' exatamente o defeito que o resto deste arquivo existe para cacar.
    corpo = _re.sub(r"#[^\n]*", "", bruto)

    assert "sqlstate" in corpo, (
        "capturar pela classe do driver estoura com NameError: `psycopg` nao esta' no "
        "escopo deste modulo"
    )
    # a TUPLA do `except`, e nao o corpo inteiro
    # `.*?` e nao `[^)]*?`: o `getattr(erro, "sqlstate", "")` traz um `)` ANTES do
    # `not in`, e a classe negada parava ali -- o teste nao achava a tupla no estado BOM.
    m = _re.search(r"sqlstate.*?not in \(([^)]*)\)", corpo, _re.S)
    assert m, "nao achei a tupla de SQLSTATE do `except`"
    tupla = m.group(1)
    for codigo in ("42P07", "42P06", "42710", "42701"):
        assert codigo in tupla, (
            f"faltou o SQLSTATE de duplicacao {codigo} na TUPLA "
            f"(achei: {' '.join(tupla.split())})"
        )
    # O `raise` tem de estar NO RAMO DO IF, e nao em qualquer lugar do corpo: `"raise" in
    # corpo` passava com o ramo trocado por `pass`, porque ha' outro `raise` na funcao.
    # Substring num corpo grande e' asserção fraca -- terceira iteracao deste teste.
    assert _re.search(r"not in \([^)]*\):\s*raise", corpo, _re.S), (
        "erro de OUTRA natureza tem de continuar estourando -- o `raise` sai do ramo do if"
    )
    assert "registrar --ate" in corpo, "a mensagem tem de dizer a cura, com o comando"
    assert "to_regclass" in corpo, (
        "...e como CONFIRMAR antes de aplicar a cura: `t` e' este caso, `f` e' outro"
    )


def test_funcao_com_dono_alheio_reprova(monkeypatch: pytest.MonkeyPatch) -> None:
    """A QUINTA porta, que o pacote nomeava desde o inicio e ninguem cobria.

    Medido em 08/10/2026, passando as duas funcoes de auditoria do D20 para o `app`:

        conferir                              ->  CONFERENCIA OK,  exit 0
        privilegios                           ->  PRIVILEGIOS OK,  exit 0
        as 22 conferencias manuais do pacote  ->  NENHUMA diferenca

    e entao, como `app` (transacao revertida):

        DROP FUNCTION registra_perfil_permissoes_historico() CASCADE;
          NOTA: removendo em cascata gatilho trg_perfil_permissoes_auditoria
        DROP FUNCTION registra_perfil_permissoes_truncate() CASCADE;
          NOTA: removendo em cascata gatilho trg_perfil_permissoes_auditoria_truncate
        triggers restantes: 0
        INSERT + DELETE em perfil_permissoes  ->  ZERO linha de auditoria

    O papel da aplicacao vira dono do mecanismo que existe para vigia-lo. A posse nao
    aparece em ACL nenhuma, entao nenhuma conferencia de privilegio a ve -- e o `prosecdef`,
    que o `conferir` olha, e' a OUTRA metade da mesma porta.

    DERIVADA, e nao pelas duas do D20: a pergunta e' "alguma funcao deste schema tem dono que
    nao e' o dono do banco?". Medida em quatro estados -- 0 no bom, 2 com as duas no `app`, 1
    com uma so' e 1 com uma funcao qualquer (`rotulo_perfil`) passada ao `etl`.
    """
    sql = postgres.SQL_FUNCAO_COM_DONO_ALHEIO

    assert "proowner" in sql, "a posse se le em `proowner`, e nao em ACL"
    assert "datdba" in sql, "o esperado e' o dono do BANCO, derivado, nao um nome"
    assert "registra_perfil_permissoes" not in sql, (
        "nomear as duas do D20 deixaria passar qualquer funcao nova com dono alheio"
    )
    assert "prosecdef" not in sql, (
        "`prosecdef` e' a outra metade da porta, e tem consulta propria"
    )

    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_FUNCAO_COM_DONO_ALHEIO] = (
        "registra_perfil_permissoes_historico (dono app)"
    )
    codigo, _ = _rodar_privilegios(monkeypatch, respostas)
    assert codigo == 1, "funcao do schema com dono alheio tem de REPROVAR"


def test_o_que_o_d20_nao_cria_reprova(monkeypatch: pytest.MonkeyPatch) -> None:
    r"""O recorte `public` que TODAS as outras conferencias partilham. O pior da familia.

    Medido em 07/10/2026:

        CREATE SCHEMA integra;
        CREATE EXTENSION postgres_fdw SCHEMA integra;
        CREATE SERVER volta ... dbname 'banco_de_reservas';     -- de volta a ESTE banco
        CREATE USER MAPPING FOR app SERVER volta
          OPTIONS (user 'reservas_owner', password ...);          -- com a identidade do DONO
        CREATE FOREIGN TABLE integra.hist (...) SERVER volta
          OPTIONS (schema_name 'public', table_name 'perfil_permissoes_historico');
        GRANT SELECT, DELETE ON integra.hist TO app;

        o `app` lendo a tabela direto  ->  ERRO: permissao negada   (como o D20 quer)
        o `app` pelo FDW               ->  77
        o `app` APAGANDO pelo FDW      ->  DELETE 77
        no banco real                 ->  0 linhas restantes

        conferir     ->  CONFERENCIA OK, exit 0
        privilegios  ->  PRIVILEGIOS OK, exit 0
        as DOZE consultas do pacote  ->  todas no estado bom

    A promessa central do D19/D20 -- "a aplicacao nao consegue apagar o proprio rastro" --
    quebrada por inteiro, com tudo verde e sem que nenhuma ACL do `public` mudasse. A causa
    nao e' falta de uma consulta: e' o `n.nspname = 'public'` que todas elas tem. O pacote
    ja' declarava "a quarta porta e' o schema" e nao tinha conferencia para ela.

    Uma varredura em vez de cinco consultas, provada em seis estados: o FDW inteiro, um
    `EVENT TRIGGER` de DDL, um schema novo VAZIO (o caso mais discreto -- nenhuma outra
    conferencia o ve), uma view noutro schema com GRANT ao `app`, e uma extensao alheia no
    PROPRIO `public`. Zero linha no estado bom.

    `pg_user_mapping` fica de fora de proposito: medido, o `app` nao o le (`permissao
    negada`) e este comando roda como `app`. Nao custa cobertura -- mapeamento nao existe
    sem servidor, e o servidor aparece.
    """
    sql = postgres.SQL_O_QUE_O_D20_NAO_CRIA

    assert "pg_namespace" in sql, "schema alheio e' o caminho mais discreto"
    assert "pg_extension" in sql, "a extensao traz a maquinaria (postgres_fdw, dblink)"
    assert "pg_foreign_server" in sql, "o servidor e' o no' obrigatorio do FDW"
    assert "pg_foreign_table" in sql, "...e a tabela externa e' por onde o dado passa"
    assert "pg_event_trigger" in sql, "DDL de terceiro, que atravessa o pg_dump"
    assert "pg_user_mapping" not in sql, (
        "o `app` nao le `pg_user_mapping`; o servidor cobre o caso e ele LE o servidor"
    )
    # O recorte invertido: esta consulta existe para olhar FORA do `public`.
    assert "NOT IN ('public', 'information_schema')" in sql, (
        "a pergunta e' o COMPLEMENTO do `public`, nao o `public`"
    )
    assert "'plpgsql', 'postgis', 'citext'" in sql, (
        "as tres extensoes do D20 sao a especificacao; qualquer outra e' achado"
    )
    assert "datdba" in sql, "o dono do banco nao e' intruso no proprio banco"

    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_O_QUE_O_D20_NAO_CRIA] = (
        "schema alheio: integra (dono reservas_owner); servidor externo: volta; "
        "privilegio fora do public: app em integra.hist (DELETE)"
    )
    codigo, _ = _rodar_privilegios(monkeypatch, respostas)
    assert codigo == 1, "objeto fora do que o D20 cria tem de REPROVAR"


def test_parametro_fixado_por_banco_ou_papel_reprova(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A outra porta do `session_replication_role`, achada na r32.

    Todo o instrumento conferia quem PODE trocar o parametro -- o `GRANT SET ON PARAMETER`,
    que vive em `pg_parameter_acl`. Medido em 07/10/2026 a porta que ninguem olhava:

        ALTER DATABASE banco_de_reservas SET session_replication_role = 'replica';

        o `app`, em sessao nova   ->  SHOW session_replication_role = replica
        o `app` tentando voltar   ->  ERRO: permissao negada  (o estado e' pegajoso)
        as DEZ conferencias       ->  todas identicas ao estado bom
        pg_db_role_setting        ->  {session_replication_role=replica}

    Ninguem precisa de privilegio: quem fixa e' o DONO do banco, num gesto que parece
    configuracao. E as triggers de auditoria em `ENABLE ALWAYS` continuam disparando, o que
    torna o estado ainda mais convincente -- o que para sao as do modo padrao.

    A consulta nao nomeia parametro DE PROPOSITO: `row_security = off` desliga RLS e
    `search_path` muda a resolucao de nomes. Medido tambem com `ALTER ROLE app SET
    row_security = off`, que a mesma consulta pega.
    """
    sql = postgres.SQL_PARAMETRO_FIXADO_POR_BANCO_OU_PAPEL
    assert "pg_db_role_setting" in sql, "o estado vive neste catalogo, nao em pg_parameter_acl"
    assert "pg_parameter_acl" not in sql, "...que e' a OUTRA porta, com consulta propria"
    assert "session_replication_role" not in sql, (
        "a lista de parametros perigosos nao fecha: qualquer um fixado e' para LER"
    )
    assert "LEFT JOIN pg_database" in sql and "LEFT JOIN pg_roles" in sql, (
        "setdatabase e setrole sao NULOS quando a fixacao e' global -- JOIN interno perderia"
    )

    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_PARAMETRO_FIXADO_POR_BANCO_OU_PAPEL] = (
        "banco_de_reservas/(todo papel): {session_replication_role=replica}"
    )
    codigo, _ = _rodar_privilegios(monkeypatch, respostas)
    assert codigo == 1, "parametro fixado tem de REPROVAR"


def test_grantee_a_mais_no_default_acl_reprova(monkeypatch: pytest.MonkeyPatch) -> None:
    """O privilegio que age no FUTURO, achado na r32.

    A checagem de `pg_default_acl` que existia olha se o `app` RECEBE. Medido o que ela nao
    olhava:

        ALTER DEFAULT PRIVILEGES FOR ROLE reservas_owner IN SCHEMA public
          GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON TABLES TO auditoria;

        no instante do repasse  ->  as DEZ conferencias identicas ao estado bom
        a PROXIMA tabela        ->  {..., auditoria=arwdD/reservas_owner}
        o `auditoria` nela      ->  TRUNCATE TABLE

    E' o eixo do TEMPO, e por isso nenhuma conferencia de ACL do presente pode ve-lo: no
    momento do repasse o objeto que vai carregar o privilegio ainda nao existe. O `GRANT` da
    secao 3 e' retrato do presente; o default ACL age na proxima migration.

    `'app'` aqui e' a ESPECIFICACAO, como em `SQL_PAPEIS_COM_ACL_NO_SCHEMA`: o D20 concede
    default ACL ao `app` e a mais ninguem.
    """
    sql = postgres.SQL_GRANTEE_A_MAIS_NO_DEFAULT_ACL
    assert "pg_default_acl" in sql
    assert "a.grantee <> d.defaclrole" in sql, "quem concede aparece na propria ACL"
    assert "'app'" in sql, "a lista de um nome e' a especificacao: so' o `app` recebe"
    assert "defaclobjtype::text" in sql, (
        "`defaclobjtype` e' do tipo \"char\": sem o cast, `text || \"char\"` estoura com "
        "AmbiguousFunction em RUNTIME -- nenhum compile pega, e foi medido"
    )

    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_GRANTEE_A_MAIS_NO_DEFAULT_ACL] = "auditoria em r (TRUNCATE)"
    codigo, _ = _rodar_privilegios(monkeypatch, respostas)
    assert codigo == 1, "grantee a mais no default ACL tem de REPROVAR"


def test_rls_ligado_reprova(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cegueira por SILENCIO, achada na r32.

    O D20 nao usa row-level security. Medido:

        ALTER TABLE perfil_permissoes_historico ENABLE ROW LEVEL SECURITY;

        o `auditoria` passa a ver  ->  0 linhas (eram 81)
        has_table_privilege(...)   ->  t, CONTINUA t
        o dono ve                  ->  81
        as DEZ conferencias        ->  todas identicas ao estado bom

    RLS sem politica nenhuma nega tudo, e nega SEM ERRO -- o `SELECT` devolve zero linha. O
    papel que existe para ler a auditoria, e a tela que ele serve, passam a mostrar um
    historico vazio; e auditoria cega e auditoria limpa se leem igual. Nenhuma conferencia
    de ACL pode ver isso, porque a ACL nao muda.

    A contagem de politicas entra no diagnostico porque RLS ligado com ZERO politica e'
    justamente o caso que nega tudo.
    """
    sql = postgres.SQL_RLS_LIGADO_NO_SCHEMA
    assert "relrowsecurity" in sql, "o estado vive aqui, e nao na ACL"
    assert "relforcerowsecurity" in sql, "o FORCADO atinge ate' o dono"
    assert "pg_policy" in sql, "zero politica com RLS ligado e' o caso que nega tudo"

    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_RLS_LIGADO_NO_SCHEMA] = (
        "perfil_permissoes_historico (rls, 0 politica(s))"
    )
    codigo, _ = _rodar_privilegios(monkeypatch, respostas)
    assert codigo == 1, "RLS ligado tem de REPROVAR"


def test_funcao_security_definer_alheia_reprova(monkeypatch: pytest.MonkeyPatch) -> None:
    """A lista FIXA de nomes que cegava o audit de funcoes, achada na r32.

    O `conferir` checa `prosecdef` e `proconfig`, e checa BEM -- medido, degradando uma
    funcao esperada (`ALTER FUNCTION rotulo_perfil(bigint) SECURITY DEFINER; RESET
    search_path`) ele reprova e nomeia. Mas filtra `proname = ANY(FUNCOES_ESPERADAS)`, uma
    lista de oito nomes, e funcao NOVA nao entra no universo. Medido:

        CREATE FUNCTION total_do_historico() RETURNS bigint LANGUAGE sql
          SECURITY DEFINER AS $$ SELECT count(*) FROM perfil_permissoes_historico $$;

        o `app` lendo a tabela direto  ->  ERRO: permissao negada  (como o D20 quer)
        o `app` pela funcao            ->  81
        as DEZ conferencias            ->  todas identicas ao estado bom

    `SECURITY DEFINER` carrega o privilegio do DONO e nao deixa entrada de ACL em lugar
    nenhum: e' um buraco na parede, nao uma porta -- e por isso toda conferencia de ACL
    continua dizendo, corretamente, que o `app` nao alcanca a tabela.

    As duas funcoes do D20 saem por nome porque elas SAO a especificacao.
    """
    sql = postgres.SQL_FUNCAO_SECURITY_DEFINER_ALHEIA
    assert "prosecdef" in sql
    assert "proconfig" in sql, "sem `search_path` fixado e' pior ainda -- vai no diagnostico"
    assert "FUNCOES_ESPERADAS" not in sql, (
        "a lista de oito nomes e' justamente o universo que cegava"
    )
    assert "registra_perfil_permissoes_historico" in sql, (
        "as DUAS do D20 saem por nome: elas sao a especificacao"
    )

    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_FUNCAO_SECURITY_DEFINER_ALHEIA] = (
        "total_do_historico (dono reservas_owner, SEM search_path)"
    )
    codigo, _ = _rodar_privilegios(monkeypatch, respostas)
    assert codigo == 1, "funcao SECURITY DEFINER alheia tem de REPROVAR"


def test_papel_alheio_com_acl_no_schema_reprova(monkeypatch: pytest.MonkeyPatch) -> None:
    """A porta PRINCIPAL -- ACL de tabela -- nunca teve consulta de universo derivado.

    Achado na rodada 31 e medido por mim antes de consertar:

        CREATE ROLE consultor LOGIN PASSWORD '...';
        GRANT SELECT ON perfil_permissoes_historico TO consultor;

        `privilegios`                        ->  PRIVILEGIOS OK, exit 0
        a contagem por papel do pacote       ->  app|24, auditoria|1, etl|9  (identica)
        a consulta de PUBLIC em tabela       ->  spatial_ref_sys  (identica)
        e o `consultor`, com senha propria   ->  79 linhas do historico append-only

    Havia uma consulta para os TRES nomes (a contagem) e uma para `PUBLIC`, e NADA entre as
    duas. Esta fecha o meio, e fecha de lambuja o privilegio de SEQUENCE a quem nao devia:
    medido, `GRANT USAGE, UPDATE ON ALL SEQUENCES ... TO consultor` aparece aqui, e as duas
    consultas de sequence -- que perguntam pelo papel CONECTADO -- nao o veem.

    Aqui nomear os tres e' CORRETO, e a distincao vale ser dita porque esta sessao passou
    quatro rodadas desmontando listas de nomes: nas perguntas NEGATIVAS ("ninguem deve ter
    X") a lista e' o furo, porque o universo e' aberto. Esta pergunta e' POSITIVA sobre o
    conjunto provisionado -- "quem tem ACL no schema sao exatamente os tres do D20" --, e
    ai a lista e' a ESPECIFICACAO, nao um atalho.
    """
    sql = postgres.SQL_PAPEIS_COM_ACL_NO_SCHEMA
    assert "aclexplode" in sql, "a pergunta e' sobre ACL, e se le em `relacl`"
    assert "a.grantee <> 0" in sql, "PUBLIC tem consulta propria; esta e' dos papeis NOMEAVEIS"
    assert "datdba" in sql, "o dono do banco nao e' papel alheio"
    assert "'app', 'auditoria', 'etl'" in sql, (
        "aqui a lista E' a especificacao: o esperado e' exatamente estes tres"
    )

    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_PAPEIS_COM_ACL_NO_SCHEMA] = "consultor"
    codigo, _ = _rodar_privilegios(monkeypatch, respostas)
    assert codigo == 1, "papel alheio com ACL no schema tem de REPROVAR"


def test_poder_de_cluster_soma_o_superuser_em_vez_de_apagar() -> None:
    """O pior estado possivel APAGAVA um achado que a consulta ja' tinha produzido.

    Medido na rodada 31, no MESMO papel, em dois gestos:

        CREATE ROLE quarto LOGIN ... CREATEROLE  ->  acusa `quarto (CREATEROLE)`
        ALTER ROLE quarto SUPERUSER              ->  (0 linha)

    O `NOT rolsuper` que eu mesmo tinha posto no filtro fazia o `SUPERUSER` -- o poder que
    ignora toda ACL e toda trigger -- silenciar a linha. E `CREATE ROLE intruso LOGIN
    SUPERUSER` nunca aparecia, porque o universo vinha de `relacl` e um papel recem-criado
    nao tem ACL em tabela nenhuma.

    Duas coisas tem de valer ao mesmo tempo, e as duas sao de FORMA porque nenhum estado
    sozinho as revela: o universo vem de `pg_roles`, e o `SUPERUSER` e' um dos poderes
    perguntados -- somado aos outros por `concat_ws`, nao escolhido por `CASE ... WHEN`
    em cadeia, que imprimiria so' o primeiro.
    """
    sql = postgres.SQL_PAPEIS_COM_PODER_DE_CLUSTER

    assert "FROM pg_roles" in sql, (
        "o universo e' `pg_roles`: quem nao recebeu GRANT nao esta em `relacl`"
    )
    assert "aclexplode" not in sql, "...e nao a ACL, que e' estreita por construcao"
    assert "NOT rolsuper" not in sql and "NOT r.rolsuper" not in sql, (
        "o `NOT rolsuper` faz o pior estado APAGAR o achado"
    )
    assert "'SUPERUSER'" in sql, "SUPERUSER e' um dos cinco poderes, nao uma exclusao"
    assert "concat_ws" in sql, (
        "os poderes SOMAM: um `CASE WHEN ... THEN ... WHEN` em cadeia imprime so' o 1o"
    )
    assert "datdba" in sql, "o dono do banco e' superusuario por desenho e sai por SER dono"
    for col in ("rolcreatedb", "rolcreaterole", "rolreplication", "rolbypassrls"):
        assert col in sql, f"faltou a coluna de poder {col}"


def test_privilegio_de_coluna_reprova(monkeypatch: pytest.MonkeyPatch) -> None:
    """A segunda porta da decima classe: `GRANT UPDATE (coluna)` nao entra em `relacl`.

    Medido: com `GRANT UPDATE (id_perfil) ON usuarios TO auditoria`, a contagem 12/1/3 nao
    se move, as doze conferencias manuais do pacote saem identicas ao estado bom, e o papel
    que existe para LER troca o perfil de qualquer pessoa -- sem tocar em
    `perfil_permissoes`, que e' onde a trigger de auditoria olha.
    """
    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_PRIVILEGIO_DE_COLUNA] = "auditoria em usuarios.id_perfil (UPDATE)"
    codigo, _ = _rodar_privilegios(monkeypatch, respostas)
    assert codigo == 1


def test_poder_de_cluster_cobre_as_cinco_colunas(monkeypatch: pytest.MonkeyPatch) -> None:
    r"""`rolreplication` e `rolbypassrls` ficaram fora da 1a versao desta consulta.

    Medido: com `ALTER ROLE app REPLICATION` e `ALTER ROLE auditoria BYPASSRLS`, a consulta
    devolvia exatamente o esperado -- enquanto o `\du` IMPRIME os dois. Com as cinco, a
    lista fecha por construcao: as outras colunas booleanas de `pg_authid` (`rolinherit`,
    `rolcanlogin`) nao concedem poder.
    """
    sql = postgres.SQL_PAPEIS_COM_PODER_DE_CLUSTER
    for coluna in ("rolsuper", "rolcreatedb", "rolcreaterole", "rolreplication", "rolbypassrls"):
        assert coluna in sql, f"{coluna} fora da consulta de poder de cluster"


def test_negativas_de_tabela_somam_o_privilegio_de_coluna(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`has_table_privilege` nao ve `GRANT UPDATE (coluna)`; `has_any_column_privilege` ve.

    Vale so' para os privilegios que TEM granularidade de coluna (`SELECT`, `INSERT`,
    `UPDATE`, `REFERENCES`): com `DELETE` ou `TRUNCATE` a funcao recusa com `tipo de
    privilegio desconhecido`, medido -- e la' nao existe o furo.
    """
    _, con = _rodar_privilegios(monkeypatch, dict(_D20_DE_PE))
    por_coluna = [s for s in con.executados if "has_any_column_privilege" in s]
    assert len(por_coluna) >= 3, "as negativas de INSERT/UPDATE precisam somar a coluna"
    for sql in por_coluna:
        assert "'DELETE'" not in sql and "'TRUNCATE'" not in sql, (
            f"has_any_column_privilege nao aceita DELETE nem TRUNCATE: {sql!r}"
        )


def test_trigger_fora_de_always_reprova(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fora de `A`, uma sessão em `replica` escreve sem deixar rastro."""
    respostas = dict(_D20_DE_PE)
    respostas["tgenabled"] = "O"
    codigo, _ = _rodar_privilegios(monkeypatch, respostas)
    assert codigo == 1


def test_sem_url_do_piloto_recusa(monkeypatch: pytest.MonkeyPatch) -> None:
    """Checar com a credencial de DONO não prova nada — o dono pode tudo."""
    monkeypatch.delenv(postgres.ENV_URL, raising=False)
    with pytest.raises(SystemExit) as caiu:
        cli.cmd_privilegios(argparse.Namespace())
    assert postgres.ENV_URL in str(caiu.value)


def test_falha_de_conexao_no_privilegios_vira_mensagem(monkeypatch: pytest.MonkeyPatch) -> None:
    """Traceback de sete quadros esconde a linha que importa. A primeira versão do
    `privilegios` chamava `psycopg.connect` direto e fazia exatamente isso — o mesmo
    defeito que o runner já tinha consertado, repetido por o conserto não ser reusável."""

    class _Erro(Exception):
        pass

    def _falha(_url: str) -> None:
        raise _Erro("FATAL: autenticacao do tipo senha falhou para o usuario 'app'")

    falso = types.SimpleNamespace(connect=_falha, OperationalError=_Erro)
    monkeypatch.setitem(sys.modules, "psycopg", falso)
    monkeypatch.setenv(postgres.ENV_URL, "postgresql://app:x@localhost/banco")

    with pytest.raises(SystemExit) as caiu:
        cli.cmd_privilegios(argparse.Namespace())
    texto = str(caiu.value)
    assert "nao consegui conectar" in texto
    assert "PGPASSWORD" in texto, "a dica do caractere especial na URL precisa aparecer"


# --------------------------------------------------------------------------------------
# `estado`, `aplicar`, `registrar` e `conferir` — a ORQUESTRACAO (16/09)
#
# Ate' aqui o arquivo provava a DECISAO (de onde vem a credencial, o que conta como
# pendente, como a alteracao e' denunciada) e exercitava um unico comando, o `privilegios`.
# O que faltava era o corpo dos outros quatro -- e entre eles esta' o `aplicar`, que executa
# DDL. Era o comando mais perigoso do conjunto e o menos coberto.
#
# Continua sem banco: o duble responde por IGUALDADE com as constantes de SQL do modulo, e
# o que se afirma e' o par (o que foi executado, o que foi commitado).
# --------------------------------------------------------------------------------------


class _ConMigracoes:
    """Duble da conexao de DDL: responde as consultas de controle e REGISTRA o que rodou.

    O `_ConPrivilegios` acima nao serve: ele devolve um escalar por consulta e nao tem
    `fetchall` nem `commit` -- e e' justamente o par (executou, commitou) que decide se o
    `aplicar` respeita uma transacao POR MIGRATION.
    """

    def __init__(
        self,
        registradas: dict[str, str] | None = None,
        tem_tabela: bool = True,
        tabelas_proprias: int = 0,
    ) -> None:
        self.registradas = dict(registradas or {})
        self.tem_tabela = tem_tabela
        #: Tabelas do `public` fora de extensao. So' importa quando `tem_tabela` e' False:
        #: e' o par (sem registro, com objetos) que o portao do `aplicar` tem de recusar.
        self.tabelas_proprias = tabelas_proprias
        self.respostas: dict[str, list[tuple[Any, ...]]] = {}
        self.executados: list[tuple[str, Any]] = []
        self.commits = 0
        self._valor: list[tuple[Any, ...]] = []

    def execute(self, sql: str, params: Any = None) -> _ConMigracoes:
        self.executados.append((sql, params))
        if sql == cli.SQL_TEM_TABELA_DE_CONTROLE:
            self._valor = [(self.tem_tabela,)]
        elif sql == cli.SQL_TABELAS_FORA_DE_EXTENSAO:
            self._valor = [(self.tabelas_proprias,)]
        elif sql == cli.SQL_JA_APLICADAS:
            self._valor = [(v, h) for v, h in self.registradas.items()]
        else:
            self._valor = self.respostas.get(sql, [])
        return self

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._valor[0] if self._valor else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._valor)

    def commit(self) -> None:
        self.commits += 1

    def __enter__(self) -> _ConMigracoes:
        return self

    def __exit__(self, *_a: Any) -> None:
        return None

    # -- leitura para os testes ---------------------------------------------
    @property
    def corpos_de_migration(self) -> list[str]:
        """O SQL que NAO e' consulta de controle: o conteudo dos arquivos `.sql`."""
        conhecidos = {
            cli.SQL_JA_APLICADAS,
            cli.SQL_TEM_TABELA_DE_CONTROLE,
            cli.SQL_TABELAS_FORA_DE_EXTENSAO,
            cli.SQL_REGISTRAR,
            cli.SQL_EXTENSOES,
            cli.SQL_CONTAGENS,
            cli.SQL_FUNCOES,
        }
        return [sql for sql, _p in self.executados if sql not in conhecidos]

    @property
    def registros(self) -> list[Any]:
        return [params for sql, params in self.executados if sql == cli.SQL_REGISTRAR]


def _rodar(monkeypatch: pytest.MonkeyPatch, con: _ConMigracoes, funcao: Any, args: Any) -> int:
    """Troca o modulo `psycopg` inteiro, no molde do `_rodar_privilegios`."""
    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=lambda _url: con))
    monkeypatch.setenv(postgres.ENV_URL, "postgresql://fake/motor")
    return int(funcao(args))


def _tudo_registrado() -> dict[str, str]:
    """Manifesto inteiro, com o hash CERTO de cada arquivo -- nada pendente, nada alterado."""
    return {m["versao"]: cli._sha256_do_arquivo(m["arquivo"]) for m in cli._manifesto()}


# --- aplicar ---------------------------------------------------------------------------


def test_simular_nao_executa_nem_commita_nada(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A flag existe para o operador VER o que aconteceria. Se ela executasse, seria a pior
    das regressoes possiveis nesta ferramenta -- e nada no codigo a impedia de virar no-op."""
    con = _ConMigracoes()
    codigo = _rodar(monkeypatch, con, cli.cmd_aplicar, argparse.Namespace(simular=True))

    assert codigo == 0
    assert con.corpos_de_migration == [], "simular executou migration"
    assert con.registros == [], "simular registrou migration"
    assert con.commits == 0
    assert "--simular" in capsys.readouterr().out


def test_aplicar_faz_uma_transacao_por_migration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Uma por migration, e nao uma para o lote: se a setima falhar, as seis anteriores
    ficam aplicadas E registradas, e reexecutar retoma de onde parou."""
    manifesto = cli._manifesto()
    con = _ConMigracoes()
    codigo = _rodar(monkeypatch, con, cli.cmd_aplicar, argparse.Namespace(simular=False))

    assert codigo == 0
    assert con.commits == len(manifesto), "commit por lote, nao por migration"
    assert len(con.corpos_de_migration) == len(manifesto)
    assert len(con.registros) == len(manifesto)


def test_aplicar_recusa_banco_com_objetos_e_sem_tabela_de_controle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O portao que faltava, e que custou a medicao de 05/10/2026.

    `_aplicadas` devolve `{}` tanto no banco virgem quanto no banco povoado sem o
    registro, e o `estado` imprimia "registradas: 0" nos dois -- saida identica byte a
    byte. Seguir aquele verde commitava a 000 e a 001 e morria na 002 com
    `DuplicateTable`, num passo que o runbook declara sem desfazer. Recusar antes custa
    um comando.
    """
    con = _ConMigracoes(tem_tabela=False, tabelas_proprias=12)
    with pytest.raises(SystemExit) as caiu:
        _rodar(monkeypatch, con, cli.cmd_aplicar, argparse.Namespace(simular=False))

    assert "migracoes_aplicadas" in str(caiu.value)
    assert "registrar --ate" in str(caiu.value), "recusar sem dizer o caminho de volta"
    assert con.corpos_de_migration == [], "recusou DEPOIS de executar DDL"
    assert con.commits == 0


def test_aplicar_segue_no_banco_virgem_mesmo_com_extensao_instalada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O outro lado do portao: ele nao pode recusar quem nao fez nada de errado.

    `CREATE EXTENSION postgis` cria `spatial_ref_sys` no `public` e a 001 e' `IF NOT
    EXISTS`, entao banco com a extensao ja' instalada e' estado legitimo. A consulta do
    portao exclui objeto de extensao justamente por isso -- medido em 05/10/2026: ali o
    `pg_tables` cru devolve 1 e a consulta devolve 0.
    """
    con = _ConMigracoes(tem_tabela=False, tabelas_proprias=0)
    codigo = _rodar(monkeypatch, con, cli.cmd_aplicar, argparse.Namespace(simular=False))

    assert codigo == 0
    assert len(con.corpos_de_migration) == len(cli._manifesto())


def test_aplicar_registra_o_hash_do_arquivo_que_aplicou(monkeypatch: pytest.MonkeyPatch) -> None:
    """Registrar outro hash faria o proprio comando acusar "alterada" na proxima corrida."""
    con = _ConMigracoes()
    _rodar(monkeypatch, con, cli.cmd_aplicar, argparse.Namespace(simular=False))

    esperado = [
        (m["versao"], m["arquivo"], cli._sha256_do_arquivo(m["arquivo"])) for m in cli._manifesto()
    ]
    assert con.registros == esperado


def test_nada_pendente_nao_escreve_nada(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    con = _ConMigracoes(registradas=_tudo_registrado())
    codigo = _rodar(monkeypatch, con, cli.cmd_aplicar, argparse.Namespace(simular=False))

    assert codigo == 0
    assert con.commits == 0
    assert con.registros == []
    assert "nada a aplicar" in capsys.readouterr().out


def test_aplicar_denuncia_migration_alterada_antes_de_aplicar(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Editar migration ja' aplicada deixa o banco num estado que nenhum arquivo descreve.
    O aviso tem de sair ANTES, senao o operador so' descobre depois de escrever."""
    registradas = _tudo_registrado()
    alvo = cli._manifesto()[1]["versao"]
    registradas[alvo] = "0" * 64

    con = _ConMigracoes(registradas=registradas)
    _rodar(monkeypatch, con, cli.cmd_aplicar, argparse.Namespace(simular=True))

    saida = capsys.readouterr().out
    assert "ATENCAO" in saida
    assert alvo in saida


# --- registrar -------------------------------------------------------------------------


def test_registrar_recusa_sem_a_tabela_de_controle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem a 000 nao ha onde registrar. Recusar com instrucao, nunca gravar no vazio."""
    con = _ConMigracoes(tem_tabela=False)
    with pytest.raises(SystemExit) as caiu:
        _rodar(monkeypatch, con, cli.cmd_registrar, argparse.Namespace(ate="016"))

    assert postgres.TABELA_MIGRACOES in str(caiu.value)
    assert con.registros == []
    assert con.commits == 0


def test_registrar_nunca_executa_corpo_de_migration(monkeypatch: pytest.MonkeyPatch) -> None:
    """E' o ponto INTEIRO do comando: o efeito ja' esta' no banco, so' falta o registro.
    Executar aqui reaplicaria DDL sobre um esquema que ja' o tem."""
    con = _ConMigracoes()
    codigo = _rodar(monkeypatch, con, cli.cmd_registrar, argparse.Namespace(ate="016"))

    assert codigo == 0
    assert con.corpos_de_migration == []
    assert con.commits == 1, "registrar e' UMA unidade de trabalho"


def test_registrar_ate_para_na_versao_pedida(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _ConMigracoes()
    _rodar(monkeypatch, con, cli.cmd_registrar, argparse.Namespace(ate="003"))

    versoes = [params[0] for params in con.registros]
    assert versoes == ["000", "001", "002", "003"]


def test_registrar_sem_alvo_nenhum_falha_com_instrucao(monkeypatch: pytest.MonkeyPatch) -> None:
    """`--ate 00` nao alcanca nem a 000 (comparacao de TEXTO: "000" > "00")."""
    con = _ConMigracoes()
    with pytest.raises(SystemExit) as caiu:
        _rodar(monkeypatch, con, cli.cmd_registrar, argparse.Namespace(ate="00"))
    assert "nenhuma migration" in str(caiu.value)
    assert con.executados == [], "recusou depois de abrir conexao"


# --- conferir e estado -----------------------------------------------------------------


def _con_conferencia(**trocas: Any) -> _ConMigracoes:
    """Um cluster que bate com o contrato, salvo o que o teste trocar."""
    contagens = {"tabelas": len(cli.TABELAS_DO_MODELO), **cli.NUMEROS_DA_SECAO_ZERO, **trocas}
    con = _ConMigracoes(registradas=_tudo_registrado())
    con.respostas = {
        cli.SQL_EXTENSOES: [("postgis",), ("citext",)],
        cli.SQL_CONTAGENS: list(contagens.items()),
        cli.SQL_FUNCOES: [
            (nome, secdef, [f"search_path={caminho}"])
            for nome, (secdef, caminho) in cli.FUNCOES_ESPERADAS.items()
        ],
    }
    return con


def _sem_provisionamento(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        postgres,
        "_provisionamento",
        lambda _con: {
            "usuario": "app",
            "pode_escrever_no_historico": False,
            "trigger_auditoria": "A",
            "triggers_auditoria": {
                "trg_perfil_permissoes_auditoria": "A",
                "trg_perfil_permissoes_auditoria_truncate": "A",
            },
        },
    )


def test_conferir_devolve_zero_quando_o_banco_bate(monkeypatch: pytest.MonkeyPatch) -> None:
    _sem_provisionamento(monkeypatch)
    con = _con_conferencia()
    assert _rodar(monkeypatch, con, cli.cmd_conferir, argparse.Namespace()) == 0


def test_conferir_devolve_um_quando_um_numero_diverge(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Um indice a menos e' exatamente o sintoma de migration nao aplicada -- e o codigo de
    saida e' o que um cron ou um runbook consegue ler."""
    _sem_provisionamento(monkeypatch)
    con = _con_conferencia(indices=cli.NUMEROS_DA_SECAO_ZERO["indices"] - 1)
    codigo = _rodar(monkeypatch, con, cli.cmd_conferir, argparse.Namespace())

    assert codigo == 1
    assert "DIVERGE" in capsys.readouterr().out


def test_conferir_REPROVA_quando_a_trigger_do_D20_nao_esta_endurecida(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`tgenabled = 'O'` e' um banco em que o historico de permissoes e' contornavel.

    Ate' 02/10/2026 este comando IMPRIMIA o estado da trigger e nao o contava: `CONFERENCIA
    OK` com codigo 0 saia igual com 'O' e com 'A'. Medido na fonte e reproduzido num Postgres
    18 real por um agente sem contexto seguindo o runbook.

    E 'O' nao tem desculpa de ambiente, ao contrario do `pode_escrever_no_historico`: aquele
    depende de QUEM CONECTA (dono escreve mesmo, e num ensaio local isso e' esperado); este
    depende do BANCO. Em todo ponto em que o runbook roda `conferir`, a secao 7 do script de
    papeis ja' rodou -- entao reprovar aqui nao reprova ensaio legitimo.
    """
    monkeypatch.setattr(
        postgres,
        "_provisionamento",
        lambda _con: {
            "usuario": "app",
            "pode_escrever_no_historico": False,
            "trigger_auditoria": "O",
            "triggers_auditoria": {
                "trg_perfil_permissoes_auditoria": "O",
                "trg_perfil_permissoes_auditoria_truncate": "O",
            },
        },
    )
    codigo = _rodar(monkeypatch, _con_conferencia(), cli.cmd_conferir, argparse.Namespace())
    saida = capsys.readouterr().out

    assert codigo == 1, "trigger em 'O' tem de REPROVAR, nao sair com 0"
    assert "ENABLE ALWAYS" in saida, "a mensagem tem de dizer O QUE fazer"
    assert "DUAS linhas" in saida, "...e que a secao 7 tem DUAS linhas ALTER TABLE"
    assert "secao 7" in saida, "...e ONDE: a secao 7 do script de papeis"
    assert "session_replication_role" in saida, "...e POR QUE: e' por ali que a trigger e' pulada"


def test_conferir_REPROVA_quando_a_trigger_do_D20_esta_ausente(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Trigger ilegivel ou inexistente nao e' silencio: a 009 nao esta' de pe."""
    monkeypatch.setattr(
        postgres,
        "_provisionamento",
        lambda _con: {
            "usuario": "app",
            "pode_escrever_no_historico": False,
            "trigger_auditoria": None,
            "triggers_auditoria": {},
        },
    )
    codigo = _rodar(monkeypatch, _con_conferencia(), cli.cmd_conferir, argparse.Namespace())

    assert codigo == 1
    assert "nenhuma trigger de auditoria" in capsys.readouterr().out


def test_conferir_NAO_reprova_o_dono_escrevendo_no_historico(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A assimetria, travada: `pode_escrever_no_historico` NAO entra nos problemas.

    Num ensaio local conecta-se como DONO, e dono tem `INSERT` direto no historico. Isso e'
    propriedade de quem conecta, nao do banco, e reprovar ali reprovaria ensaio legitimo --
    que era a objecao obvia ao conserto da trigger. O comando avisa e segue.
    """
    monkeypatch.setattr(
        postgres,
        "_provisionamento",
        lambda _con: {
            "usuario": "reservas_owner",
            "pode_escrever_no_historico": True,
            "trigger_auditoria": "A",
            "triggers_auditoria": {
                "trg_perfil_permissoes_auditoria": "A",
                "trg_perfil_permissoes_auditoria_truncate": "A",
            },
        },
    )
    codigo = _rodar(monkeypatch, _con_conferencia(), cli.cmd_conferir, argparse.Namespace())
    saida = capsys.readouterr().out

    assert codigo == 0, "dono escrevendo no historico e' esperado em ensaio: AVISO, nao problema"
    assert "AVISO" in saida


def test_privilegios_REPROVA_com_a_secao_7_colada_pela_METADE(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A secao 7 tem DUAS linhas `ALTER TABLE ... ENABLE ALWAYS TRIGGER`.

    Ate' 05/10/2026 os dois instrumentos olhavam UM nome (`trg_perfil_permissoes_auditoria`),
    entao colar so' a primeira linha deixava a de TRUNCATE em 'O' e `privilegios` dizia
    PRIVILEGIOS OK, exit 0. Medido num banco real. E §7 pela metade nao e' hipotese: e' o
    desfecho da interrupcao que a secao "Se o passo 5 for interrompido" do repasse antecipa --
    ela chega a contar "2 ALTER TABLE ... ENABLE ALWAYS TRIGGER".

    A consulta DERIVA as triggers do catalogo em vez de nomea-las, entao uma terceira trigger
    na tabela auditada tambem passa a ser exigida em 'A' sem ninguem lembrar de mexer aqui.
    """
    # Parte do cluster PROVISIONADO e estraga so' a trigger: assim o unico problema que
    # sobra e' o que o teste quer medir. Antes partia de um dicionario minimo, e o
    # `exit 1` vinha de dezenas de checagens falhando por falta de resposta registrada.
    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_TRIGGERS_AUDITORIA] = [
        ("trg_perfil_permissoes_auditoria", "A"),
        ("trg_perfil_permissoes_auditoria_truncate", "O"),
    ]
    codigo, _con = _rodar_privilegios(monkeypatch, respostas)
    saida = capsys.readouterr().out

    assert codigo == 1, "uma das duas triggers fora de 'A' tem de REPROVAR"
    assert "trg_perfil_permissoes_auditoria_truncate" in saida, "a mensagem tem de NOMEAR qual"
    assert "DUAS linhas" in saida, "...e lembrar que a secao 7 tem duas"


def test_privilegios_REPROVA_sem_trigger_nenhuma(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tabela auditada sem trigger nao-interna: a 009 nao esta' de pe."""
    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_TRIGGERS_AUDITORIA] = []
    codigo, _con = _rodar_privilegios(monkeypatch, respostas)
    assert codigo == 1


def test_privilegios_REPROVA_funcao_de_auditoria_executavel_por_PUBLIC(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """O TERCEIRO furo de instrumento, achado em 05/10/2026.

    A secao 2 do script de papeis fecha o `EXECUTE` das duas funcoes de auditoria a
    `PUBLIC`, e nenhum instrumento olhava essa camada: `has_function_privilege` nao
    aparecia uma vez no modulo. Medido num banco de verdade -- com o `EXECUTE` devolvido,
    `conferir` dizia OK, a contagem 12/1/3 ficava intacta e o `privilegios` passava.

    Reprova NOMEANDO o objeto: devolver o privilegio a UMA das duas nao pode acusar as
    duas.
    """
    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_ACL_FUNCOES_DE_AUDITORIA] = [
        ("registra_perfil_permissoes_historico", False),
        ("registra_perfil_permissoes_truncate", True),
    ]
    codigo, _con = _rodar_privilegios(monkeypatch, respostas)
    saida = capsys.readouterr().out

    assert codigo == 1, "PUBLIC executando a funcao de auditoria tem de REPROVAR"
    assert "FALHA funcao registra_perfil_permissoes_truncate" in saida, "tem de NOMEAR qual"
    assert "ok    funcao registra_perfil_permissoes_historico" in saida, (
        "a outra esta' certa e nao pode ser acusada"
    )
    assert "REVOKE EXECUTE" in saida, "...e dizer qual comando conserta"


def test_privilegios_REPROVA_sem_usage_no_schema(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """O QUINTO furo, achado em 05/10/2026 -- e o unico que REPROVAVA pela causa ERRADA.

    A secao 2 do D20 concede `USAGE ON SCHEMA public` e nenhum instrumento perguntava se
    o papel tem. Sem `USAGE`, o privilegio de TABELA continua no catalogo
    (`has_table_privilege` nao considera schema), entao `conferir` fica verde e a
    contagem 12/1/3 fica intacta -- mas o papel nao enxerga a tabela e a aplicacao morre
    com `relation "usuarios" does not exist`.

    Medido num banco de verdade: dezesseis checagens degradavam para "o objeto nao
    existe (migration pendente?)" num banco onde `estado` diz 21 de 21 registradas. O
    operador era mandado de volta ao §5, que responde que esta' tudo certo.
    """
    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_USAGE_NO_SCHEMA] = False
    codigo, _con = _rodar_privilegios(monkeypatch, respostas)
    saida = capsys.readouterr().out

    assert codigo == 1, "sem USAGE no schema tem de REPROVAR"
    assert "FALHA usar o schema public" in saida
    assert "does not exist" in saida, "tem de nomear o sintoma que o operador vai ver"
    assert saida.index("usar o schema public") < saida.index("gravar evento"), (
        "a causa tem de vir ANTES dos sintomas: quem le de cima para baixo encontra o "
        "USAGE antes dos `PEND` que ele provoca"
    )


def test_privilegios_degrada_sem_estourar_com_a_tabela_auditada_invisivel(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """As tres consultas derivadas nao podem levantar -- era defeito MEU, medido.

    Ate' 05/10/2026 elas usavam `%s::regclass`, que levanta `UndefinedTable` quando a
    relacao nao e' visivel. Com o `USAGE` do schema revogado, `privilegios` morria com
    traceback cru de psycopg -- exatamente o que o comentario de
    `_conectar_com_diagnostico` chama de inaceitavel numa ferramenta de operador, e
    contra a disciplina do sentinela AUSENTE que o modulo inteiro segue. `to_regclass`
    devolve NULL em vez de levantar.

    E o recado tem de nomear as DUAS causas possiveis: migration ausente OU falta de
    USAGE. Chutar uma e' o que fazia o relatorio mandar o operador ao lugar errado.
    """
    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_TABELA_AUDITADA_VISIVEL] = False
    codigo, _con = _rodar_privilegios(monkeypatch, respostas)
    saida = capsys.readouterr().out

    assert codigo == 1
    assert "nao e' visivel para este papel" in saida
    assert "migration 009 nao rodou" in saida, "primeira causa"
    assert "`USAGE` no schema" in saida, "segunda causa -- chutar uma so' foi o defeito"
    assert "FALHA trigger" not in saida, "sem objeto, nao se afirma nada sobre as triggers"
    assert "FALHA funcao" not in saida
    assert "FALHA default privileges" not in saida


def test_privilegios_REPROVA_default_privilege_concedido_ao_papel_ERRADO(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Defeito do conserto da R14, achado na R16: a consulta lia QUEM CRIA e nao QUEM RECEBE.

    A secao 6 pode ser colada com o `FOR ROLE` certo e o grantee errado
    (`... TO auditoria` em vez de `TO app`). Medido num banco de verdade: as duas linhas
    aparecem com `defaclrole = reservas_owner`, a instrucao do §6 ("olhe o PAPEL, nao a
    contagem") aprova, e a tabela futura nasce com `has_table_privilege('app', ...) =
    false`. `defaclacl` e' a coluna que carrega a concessao, e a instrucao parava uma
    coluna antes dela.
    """
    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_DEFAULT_ACL_DO_DONO] = [
        ("S", "reservas_owner", "app", True),
        ("r", "reservas_owner", "auditoria", False),
    ]
    codigo, _con = _rodar_privilegios(monkeypatch, respostas)
    saida = capsys.readouterr().out

    assert codigo == 1, "grantee errado tem de REPROVAR"
    assert "FALHA default privileges de TABLES" in saida, "tem de dizer QUAL tipo"
    assert "ok    default privileges de SEQUENCES" in saida, (
        "o outro tipo esta' certo e nao pode ser acusado -- e agregar os dois escondia "
        "exatamente este estado"
    )


def test_privilegios_REPROVA_default_privilege_criado_pelo_papel_ERRADO(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """O outro jeito de errar a secao 6: `FOR ROLE postgres` num cluster onde ele existe.

    Nao da erro na tela e grava duas linhas INUTEIS -- quem cria objeto ali e' o dono.
    """
    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_DEFAULT_ACL_DO_DONO] = [
        ("S", "postgres", "app", True),
        ("r", "postgres", "app", True),
    ]
    codigo, _con = _rodar_privilegios(monkeypatch, respostas)
    saida = capsys.readouterr().out

    assert codigo == 1
    assert "criados por postgres" in saida
    assert "reservas_owner" in saida, "tem de dizer quem DEVIA ter criado"


def test_privilegios_ACEITA_default_privilege_com_papel_extra(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Criterio 7: papel EXTRA, ao lado do certo, e' estado legitimo e nao pode reprovar.

    Um cluster pode ter default ACL de mais de um dono por motivo legitimo. A pergunta e'
    "o dono esta' la' e a concessao chega a quem conecta?", nao "so' o dono esta' la'".
    """
    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_DEFAULT_ACL_DO_DONO] = [
        ("S", "postgres,reservas_owner", "app", True),
        ("r", "postgres,reservas_owner", "app,etl", True),
    ]
    codigo, _con = _rodar_privilegios(monkeypatch, respostas)

    assert codigo == 0, "papel extra, criando E recebendo, e' estado legitimo"
    assert "ok    default privileges de TABLES" in capsys.readouterr().out


def test_privilegios_REPROVA_sem_a_linha_de_um_dos_tipos(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A secao 6 tem DUAS linhas (`ON TABLES` e `ON SEQUENCES`). Colar uma so' reprova."""
    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_DEFAULT_ACL_DO_DONO] = [("r", "reservas_owner", "app", True)]
    codigo, _con = _rodar_privilegios(monkeypatch, respostas)
    saida = capsys.readouterr().out

    assert codigo == 1
    assert "FALHA default privileges de SEQUENCES: NENHUM" in saida


def test_privilegios_REPROVA_poder_que_a_secao_2_revoga_de_PUBLIC(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A SETIMA classe, achada na R18 -- e a mais estrutural das sete.

    A secao 2 do script faz `REVOKE CREATE ON SCHEMA public FROM PUBLIC` e
    `REVOKE TEMPORARY ON DATABASE ... FROM PUBLIC`. Revogar de `PUBLIC` vale para TODOS os
    papeis, inclusive os que nao conectam por aqui. Mas todo instrumento pergunta pelo
    papel CONECTADO: este comando usa `current_user` e os seis testes negativos do script
    cravam `'app'`.

    Medido num banco de verdade: com `CREATE` no schema para o `etl` e `TEMPORARY` no banco
    para `auditoria` e `etl`, o `conferir` sai 0, a contagem 12/1/3 fica intacta, os seis
    negativos dao seis `false`, as seis consultas manuais do pacote dao o esperado -- e o
    `etl` CRIA TABELA no schema.

    A consulta pergunta pelo UNIVERSO (papeis com privilegio + o proprio `public`, menos o
    dono), e de tabela subsume o buraco do `TEMPORARY` que o dump nao carrega: antes so' o
    `privilegios` o pegava, e so' para o `app`.
    """
    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_PODERES_ABERTOS_NO_SCHEMA] = (
        "auditoria (TEMPORARY no banco), etl (CREATE no schema)"
    )
    codigo, _con = _rodar_privilegios(monkeypatch, respostas)
    saida = capsys.readouterr().out

    assert codigo == 1, "poder aberto a quem nao e' o dono tem de REPROVAR"
    assert "etl (CREATE no schema)" in saida, "tem de NOMEAR o papel e o poder"
    assert "auditoria (TEMPORARY no banco)" in saida, "...todos, nao so' o primeiro"
    assert "revogar de" in saida, "...e dizer por que revogar de PUBLIC alcanca os tres"


def test_poderes_abertos_EXCLUI_o_dono_do_banco_por_construcao() -> None:
    """O dono do banco tem os DOIS poderes legitimamente, e acusa-lo e' falso alarme.

    Medido em 07/10/2026, num banco criado com `OWNER dono_comum` onde o dono NAO e'
    superusuario:

        has_schema_privilege('dono_comum', 'public', 'CREATE')   ->  t
        has_database_privilege('dono_comum', <banco>, 'TEMPORARY') -> t
        pg_has_role('dono_comum', 'pg_database_owner', 'USAGE')  ->  t

    Ele herda `pg_database_owner`, que POSSUI o `public`. No cluster de ensaio o dono e'
    superusuario e sai pelo `relowner`, entao o furo nao aparecia -- mas na VPS o dono do
    banco pode ser papel comum, e ai a consulta reprovaria o estado BOM. A exclusao e' por
    SER dono (`datdba`), nao por nome: um `rolname = 'reservas_owner'` seria a mesma lista
    nomeada que esta sessao passou tres rodadas desmontando.

    Teste de FORMA de proposito: o defeito nao aparece em nenhum estado do ensaio.
    """
    sql = postgres.SQL_PODERES_ABERTOS_NO_SCHEMA

    assert "datdba" in sql, "o dono do banco tem de sair do universo, e sair por SER dono"
    assert "current_database()" in sql, "...do banco CORRENTE, nao de um nome fixo"
    assert "reservas_owner" not in sql, "...e nunca por nome"


def test_privilegios_REPROVA_papel_com_poder_de_cluster(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A SEXTA classe de furo, achada na R17: os ATRIBUTOS que a secao 1 endurece.

    A secao 1 cria os tres papeis sem `CREATEDB`, `CREATEROLE` nem `SUPERUSER`, e o `etl`
    com `NOLOGIN`. Nenhum instrumento olhava isso. Medido num banco de verdade: com
    `ALTER ROLE etl LOGIN` e `ALTER ROLE app CREATEDB CREATEROLE`, `conferir` sai 0 e a
    contagem 12/1/3 fica intacta -- e `CREATEROLE` anula o D20 por fora, porque quem cria
    papel se concede o que quiser.

    A checagem DERIVA e exclui o dono por SER dono, nao por nome: sem isso ela acusava o
    proprio `reservas_owner`, que e' superusuario e aparece em `relacl` com concessoes
    explicitas. Falso alarme medido antes de entregar.
    """
    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_PAPEIS_COM_PODER_DE_CLUSTER] = "app (CREATEROLE)"
    codigo, _con = _rodar_privilegios(monkeypatch, respostas)
    saida = capsys.readouterr().out

    assert codigo == 1, "papel com poder de cluster tem de REPROVAR"
    assert "app (CREATEROLE)" in saida, "tem de NOMEAR o papel e o poder"
    assert "anulam o D20 por" in saida, "...e dizer por que isso derruba o provisionamento"


def test_privilegios_REPROVA_papel_com_privilegio_e_sem_usage_no_schema(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """O SEXTO furo, achado na R16: o `USAGE` e' concedido a TRES papeis e conferido a UM.

    A checagem positiva que entrou na R15 pergunta por `current_user` (o `app`), e a
    consulta que o pacote prescrevia perguntava so' pelo `app` tambem. Medido num banco
    de verdade: revogando o `USAGE` apenas do `auditoria`, ele mantem `SELECT` em
    `perfil_permissoes_historico` no catalogo, a consulta real falha com
    `relation ... does not exist`, e TODAS as conferencias ficam verdes. O papel existe
    para uma coisa so' -- ler aquele historico -- e e' ela que quebra.

    O conserto DERIVA o universo: todo papel com privilegio de tabela ou sequence no
    schema precisa de `USAGE` nele, senao o privilegio e' inerte. Papel novo entra
    sozinho, porque nao ha lista.
    """
    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_PAPEIS_SEM_USAGE_NO_SCHEMA] = "auditoria"
    codigo, _con = _rodar_privilegios(monkeypatch, respostas)
    saida = capsys.readouterr().out

    assert codigo == 1, "papel com privilegio inerte tem de REPROVAR"
    assert "auditoria NAO tem" in saida, "tem de NOMEAR o papel"
    assert "INERTE" in saida, "...e dizer por que o privilegio no catalogo nao vale nada"
    assert "ok    usar o schema public" in saida, (
        "a checagem do `current_user` continua passando -- e e' justamente por isso que "
        "ela sozinha nao bastava"
    )



def test_privilegios_deriva_as_funcoes_de_auditoria_do_catalogo(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A consulta sai das PROPRIAS triggers (`tgfoid`), nao de uma lista nem de um `LIKE`.

    Por que importa: as OUTRAS funcoes do modelo tem `EXECUTE` para `PUBLIC` por padrao e
    de forma legitima -- medi seis assim no banco de ensaio --, entao cobrar `False` em
    todas daria falso alarme em seis objetos. Derivando, uma terceira trigger na tabela
    auditada traz a funcao dela para a conta sem ninguem lembrar de mexer aqui.
    """
    respostas = dict(_D20_DE_PE)
    respostas[postgres.SQL_ACL_FUNCOES_DE_AUDITORIA] = [
        ("registra_perfil_permissoes_historico", False),
        ("registra_perfil_permissoes_truncate", False),
        ("registra_terceira_coisa", True),
    ]
    codigo, _con = _rodar_privilegios(monkeypatch, respostas)
    saida = capsys.readouterr().out

    assert codigo == 1, "funcao nova na tabela auditada entra na conta sozinha"
    assert "registra_terceira_coisa" in saida


def test_conferir_nao_escreve_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le CATALOGO, nunca dado -- e nunca escreve."""
    _sem_provisionamento(monkeypatch)
    con = _con_conferencia()
    _rodar(monkeypatch, con, cli.cmd_conferir, argparse.Namespace())

    assert con.registros == []
    assert con.commits == 0
    assert not any("INSERT" in sql.upper() or "UPDATE" in sql.upper() for sql, _ in con.executados)


def test_estado_so_le(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    con = _ConMigracoes(registradas=_tudo_registrado())
    codigo = _rodar(monkeypatch, con, cli.cmd_estado, argparse.Namespace())

    assert codigo == 0
    assert con.commits == 0
    assert con.corpos_de_migration == []
    assert "migrations no manifesto" in capsys.readouterr().out


# --------------------------------------------------------------------------------------
# `expurgar` — a retencao da origem das sessoes (P15, prazo fechado em 23/09/2026)
# --------------------------------------------------------------------------------------


class _ConExpurgo(_ConMigracoes):
    """Reusa o dublê de migrations: ele tem `commit` contado, que e' o que importa aqui."""

    def __init__(self, pendentes: int) -> None:
        super().__init__()
        self.pendentes = pendentes
        self.rowcount = 0

    def execute(self, sql: str, params: Any = None) -> Any:
        from motor_expansao.db import sessoes

        self.executados.append((sql, params))
        if sql == sessoes.SQL_CONTAR_ORIGEM_VENCIDA:
            self._valor = [(self.pendentes,)]
            self.rowcount = 0
        elif sql == sessoes.SQL_EXPURGAR_ORIGEM:
            self._valor = []
            self.rowcount = self.pendentes
        else:  # pragma: no cover - nao deve haver outra consulta
            self._valor = []
        return self


def _rodar_expurgo(
    monkeypatch: pytest.MonkeyPatch, pendentes: int, *, simular: bool = False
) -> tuple[int, _ConExpurgo]:
    con = _ConExpurgo(pendentes)
    monkeypatch.setattr(cli, "_conectar_para_ddl", lambda: con)
    argv = ["expurgar", "--simular"] if simular else ["expurgar"]
    return cli.main(argv), con


def test_expurgar_ESCREVE_e_commita(monkeypatch: pytest.MonkeyPatch) -> None:
    """O commit e' EXPLICITO, como em `aplicar` e `registrar`.

    Ate' 23/09/2026 este era o unico comando do CLI que dependia do `with` do psycopg para
    commitar. Funcionava -- mas uma troca futura por `connect()/close()` faria o cron imprimir
    "anonimizadas: N" com ROLLBACK silencioso. Numa politica de retencao, relatar remocao que
    nao aconteceu e' o pior desfecho possivel, porque ninguem vai conferir.
    """
    from motor_expansao.db import sessoes

    codigo, con = _rodar_expurgo(monkeypatch, pendentes=7)
    assert codigo == 0
    assert any(sql == sessoes.SQL_EXPURGAR_ORIGEM for sql, _p in con.executados)
    assert con.commits == 1, "o expurgo escreveu sem commitar"


def test_expurgar_manda_o_prazo_DECIDIDO(monkeypatch: pytest.MonkeyPatch) -> None:
    """90 dias, da constante -- nao um numero digitado no comando."""
    from motor_expansao.db import sessoes

    _codigo, con = _rodar_expurgo(monkeypatch, pendentes=3)
    for sql, params in con.executados:
        if sql in (sessoes.SQL_EXPURGAR_ORIGEM, sessoes.SQL_CONTAR_ORIGEM_VENCIDA):
            assert params == (sessoes.RETENCAO_ORIGEM_DIAS,)


def test_expurgar_SIMULAR_nao_escreve_nem_commita(monkeypatch: pytest.MonkeyPatch) -> None:
    """E' o smoke que a instalacao do cron manda rodar primeiro. Um modo seco que escreve
    nao e' seco -- e aqui o que ele escreveria seria a REMOCAO de dado."""
    from motor_expansao.db import sessoes

    codigo, con = _rodar_expurgo(monkeypatch, pendentes=5, simular=True)
    assert codigo == 0
    assert not any(sql == sessoes.SQL_EXPURGAR_ORIGEM for sql, _p in con.executados)
    assert con.commits == 0


def test_expurgar_sem_nada_vencido_nao_escreve(monkeypatch: pytest.MonkeyPatch) -> None:
    """Idempotencia vista de fora: rodado todo dia, na maioria deles nao ha' o que fazer, e
    nesses o comando nao pode tocar no banco."""
    from motor_expansao.db import sessoes

    codigo, con = _rodar_expurgo(monkeypatch, pendentes=0)
    assert codigo == 0
    assert not any(sql == sessoes.SQL_EXPURGAR_ORIGEM for sql, _p in con.executados)
    assert con.commits == 0


def test_privilegios_COBRE_sessoes() -> None:
    """A checagem de `sessoes` tem de EXISTIR, e nao so' passar quando existe.

    Sem esta assercao, apagar as duas checagens positivas deixaria a suite inteira verde --
    e o `db privilegios`, que existe para provar o D20, voltaria a passar no exato cenario em
    que o login morre: `sessoes` sem `GRANT` para o papel `app`.

    E esse cenario NAO e' hipotetico em producao. O `ALTER DEFAULT PRIVILEGES` do
    `papeis-e-privilegios.md` §6 diz `FOR ROLE postgres`, e so' alcanca objetos criados por
    AQUELE papel -- mas o dono do schema em producao e' `reservas_owner`. A `sessoes`, criada
    pela migration 018, nao herda nada, e o sintoma so' apareceria no dia da virada da chave.
    O documento ja' nomeava a armadilha ("as tabelas novas nascem sem GRANT e ninguem
    percebe"); o que faltava era alguem PERGUNTAR, e e' isto aqui.
    """
    positivas = " | ".join(sql for _rot, sql, _por in cli._checagens_positivas())
    assert "'sessoes', 'INSERT'" in positivas
    assert "'sessoes', 'UPDATE'" in positivas
    assert "'sessoes', 'SELECT'" in positivas
    assert "sessoes_id_sessao_seq" in positivas, (
        "a sequence da sessao: `GRANT INSERT` na tabela NAO a cobre, e o login morre so' em "
        "runtime -- mesma armadilha da sequence de eventos"
    )

    assert "usuarios_id_usuario_seq" in positivas, (
        "a sequence de `usuarios`: sem o USAGE nela NENHUMA pessoa e' criada pela tela, porque "
        "o `SQL_CRIAR` nao passa `id_usuario` e depende do BIGSERIAL. Ate' 05/10/2026 este "
        "comando testava SO' as sequences de `eventos` e `sessoes`, e faltar esta passava verde "
        "aqui, no `conferir` e na conferencia de 12/1/3 -- medido num banco de ensaio"
    )
    assert "areas_estudo_id_area_estudo_seq" in positivas
    assert "contratos_id_contrato_seq" in positivas

    _seqs = [s for s in positivas.split(" | ") if "has_sequence_privilege" in s]
    assert len(_seqs) == 5, (
        f"o script de papeis concede USAGE em CINCO sequences e este comando testa "
        f"{len(_seqs)}. Se o script mudar, mude os dois juntos -- a divergencia entre eles e' "
        f"exatamente o buraco que ficou aberto ate' 05/10/2026"
    )

    negativas = " | ".join(sql for _rot, sql, _por in cli._checagens_negativas())
    assert "'sessoes', 'DELETE'" in negativas, (
        "revogar e' UPDATE e o expurgo anonimiza; `DELETE` em `sessoes` significa que o "
        "provisionamento foi afrouxado sem a decisao acompanhar"
    )


def test_privilegios_NAO_estoura_com_objeto_ausente(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rodar contra um banco que ainda nao recebeu a 018 tem de RELATAR, nao explodir.

    `has_table_privilege('sessoes', ...)` LEVANTA quando a tabela nao existe, em vez de devolver
    falso. Ate' 25/09/2026 isso derrubava o comando inteiro com `UndefinedTable` e um traceback
    cru no meio do relatorio -- medido contra um banco real sem a 018.

    E o cenario e' NATURAL: conferir o estado ANTES de aplicar e' a primeira coisa que o operador
    faz. Um traceback ali manda investigar o provisionamento, que esta' certo.

    ESTE TESTE NASCEU DE UM ERRO DE JULGAMENTO: tres verificadores independentes classificaram
    este risco como refutado; rodar contra o banco real mostrou que era verdadeiro. Voto de
    maioria nao substitui execucao.
    """
    import psycopg

    class _ConAusente(_ConPrivilegios):
        def __init__(self) -> None:
            super().__init__(dict(_D20_DE_PE))
            self.rollbacks = 0

        def execute(self, sql: str, params: Any = None) -> Any:
            if "sessoes" in sql:
                raise psycopg.errors.UndefinedTable('relação "sessoes" não existe')
            return super().execute(sql, params)

        def rollback(self) -> None:
            self.rollbacks += 1

    con = _ConAusente()
    monkeypatch.setattr(cli, "_conectar_com_diagnostico", lambda _p, _u: con)
    monkeypatch.setenv(postgres.ENV_URL, "postgresql://app@localhost/x")

    codigo = cli.main(["privilegios"])

    assert codigo == 1, "objeto ausente e' problema a relatar, nao sucesso"
    assert con.rollbacks >= 1, (
        "sem `rollback` a transacao fica abortada e TODA checagem seguinte falha com "
        "`InFailedSqlTransaction` -- o relatorio mentiria sobre o resto"
    )


def test_o_sentinela_de_ausente_nao_e_False() -> None:
    """`AUSENTE` e `False` respondem perguntas diferentes, e confundi-las inverte o diagnostico.

    `False` = o papel NAO PODE (o `GRANT` falta). `AUSENTE` = o objeto nao existe (a MIGRATION
    falta). Se o sentinela fosse falsy-e-indistinguivel, o relatorio acusaria privilegio faltando
    e mandaria o operador mexer no provisionamento, que esta' correto.
    """
    assert cli.AUSENTE is not False
    assert cli.AUSENTE is not None


# --------------------------------------------------------------------------------------
# `alinhar-senhas`: a classificacao, SEM banco (25/09/2026)
# --------------------------------------------------------------------------------------
#
# O CI nao tem Postgres, e o unico teste do comando era de integracao -- pulava sem banco.
# Ou seja, o comando que se roda contra o banco de PRODUCAO, no passo que o runbook chama de
# "o unico que nao da' para desfazer depois", chegava a' VPS sem verificacao automatica.
# A decisao foi extraida para `classificar_para_alinhar` e e' o que estes testes cobrem.

#: `(id, login, hash, classe-vinda-do-SQL)` — a forma de `SQL_ESTADO_DA_SENHA_INICIAL`.
_CONFERE = "$argon2id$hash-da-inicial"


def _confere_com_a_inicial(h: str | None) -> bool:
    return h == _CONFERE


def test_classificar_poe_cada_linha_na_classe_certa() -> None:
    por_classe = cli.classificar_para_alinhar(
        [
            (1, "dono", "$argon2id$propria-do-dono", "propria_ok"),
            (2, "ana", "hash_de_teste_1", "propria_quebrada"),
            (3, "bruno", _CONFERE, "sem_propria"),
            (4, "carla", "hash_de_teste_2", "sem_propria"),
        ],
        _confere_com_a_inicial,
    )
    assert [login for _i, login in por_classe["propria_ok"]] == ["dono"]
    assert [login for _i, login in por_classe["propria_quebrada"]] == ["ana"]
    assert [login for _i, login in por_classe["sem_propria_ok"]] == ["bruno"]
    assert [login for _i, login in por_classe["sem_propria"]] == ["carla"]


def test_quem_escolheu_a_propria_senha_NUNCA_entra_na_lista_de_reescrita() -> None:
    """A propriedade de seguranca do comando, e ela inclui o DONO do banco.

    Um comando que "alinha todo mundo" derrubaria a senha de quem a escolheu -- no passo de
    PREPARACAO do corte, e sem ninguem pedir. Nem `propria_ok` nem `propria_quebrada` podem
    aparecer em `sem_propria`, que e' a unica classe que o comando reescreve.
    """
    por_classe = cli.classificar_para_alinhar(
        [
            (1, "dono", "$argon2id$propria-do-dono", "propria_ok"),
            (2, "ana", None, "propria_quebrada"),
            (3, "bruno", "$argon2id$de-OUTRA-senha", "propria_ok"),
        ],
        _confere_com_a_inicial,
    )
    assert por_classe["sem_propria"] == [], (
        "alguem que escolheu a propria senha entrou na lista de reescrita"
    )


def test_hash_que_CONFERE_sai_da_lista_e_e_isso_que_torna_o_comando_idempotente() -> None:
    """Rodar duas vezes nao reescreve, e o numero diz o que FALTA.

    Sem esta separacao a saida diria "N seriam alinhadas" tanto num banco quebrado quanto num
    ja' certo -- e quem rodasse o comando duas vezes nao distinguiria "funcionou" de "nao fez
    nada". E' a mesma exigencia que o `cmd_expurgar` documenta para o proprio contador.
    """
    linhas = [(i, f"p{i}", _CONFERE, "sem_propria") for i in range(1, 4)]
    por_classe = cli.classificar_para_alinhar(linhas, _confere_com_a_inicial)
    assert len(por_classe["sem_propria_ok"]) == 3
    assert por_classe["sem_propria"] == []


def test_hash_NULO_de_quem_nunca_escolheu_entra_para_reescrita() -> None:
    """`senha_hash` nulo nao e' "confere": e' pessoa que nao entra."""
    por_classe = cli.classificar_para_alinhar(
        [(1, "sem-hash", None, "sem_propria")], _confere_com_a_inicial
    )
    assert [login for _i, login in por_classe["sem_propria"]] == ["sem-hash"]


def test_lista_vazia_nao_explode_e_devolve_as_quatro_classes() -> None:
    """Banco recem-criado, sem usuario nenhum -- o caso da VPS antes do passo 0.a."""
    por_classe = cli.classificar_para_alinhar([], _confere_com_a_inicial)
    assert set(por_classe) == {"sem_propria_ok", "sem_propria", "propria_quebrada", "propria_ok"}
    assert all(v == [] for v in por_classe.values())
