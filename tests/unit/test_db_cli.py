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
        # 13 desde a D30: `chk_sessao_expira_apos_criacao`, a guarda contra sessao que
        # nasce vencida -- sem ela a pessoa veria "sessao expirada" logo apos digitar a
        # senha certa, que e' o pior diagnostico possivel.
        "constraints CHECK": 13,
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
        return (self._valor,)

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
    "pg_parameter_acl": False,
    "'eventos', 'INSERT'": True,
    "has_sequence_privilege": True,
    "'usuarios', 'UPDATE'": True,
    "spatial_ref_sys": True,
    "tgenabled": "A",
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
        "pg_parameter_acl",  # SET session_replication_role
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

    def __init__(self, registradas: dict[str, str] | None = None, tem_tabela: bool = True) -> None:
        self.registradas = dict(registradas or {})
        self.tem_tabela = tem_tabela
        self.respostas: dict[str, list[tuple[Any, ...]]] = {}
        self.executados: list[tuple[str, Any]] = []
        self.commits = 0
        self._valor: list[tuple[Any, ...]] = []

    def execute(self, sql: str, params: Any = None) -> _ConMigracoes:
        self.executados.append((sql, params))
        if sql == cli.SQL_TEM_TABELA_DE_CONTROLE:
            self._valor = [(self.tem_tabela,)]
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
