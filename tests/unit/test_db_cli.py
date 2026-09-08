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


def test_o_contrato_conferido_cobre_as_11_tabelas_do_modelo() -> None:
    """A lista de `conferir` e a da §0 da `verificacao.md` tem de ser a MESMA: se
    divergirem, a ferramenta passa a atestar um contrato que o documento nao descreve."""
    assert len(cli.TABELAS_DO_MODELO) == 11
    assert postgres.TABELA_MIGRACOES not in cli.TABELAS_DO_MODELO, (
        "a tabela de controle e' do motor, nao do modelo — some-la mudaria os seis numeros"
    )


def test_endurecimento_esperado_cobre_as_7_funcoes() -> None:
    """Sete funcoes, e as DUAS gravadoras do D19 sao as unicas `SECURITY DEFINER`."""
    assert len(cli.FUNCOES_ESPERADAS) == 7
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
        # 46 desde a D24: os tres indices de expressao sobre `metadados` (o de
        # `idx_usuarios_login_ativo` da D23 levou de 42 a 43). Este numero e o da §0
        # da `verificacao.md` tem de andar JUNTOS — se um ficar para tras, um banco
        # correto passa a acusar DIVERGENTE.
        "indices": 46,
        "constraints CHECK": 12,
        "chaves estrangeiras": 11,
        "triggers": 5,
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
