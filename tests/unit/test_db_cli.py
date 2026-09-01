"""Ferramenta de linha de comando do banco (`python -m motor_expansao.db`).

Nenhum comando SQL parte daqui — a decisao de 25/08 vale tambem para os testes. O que se
prova sem banco e', justamente, o que decide se a ferramenta e' segura de entregar a quem
executa: de onde ela tira a credencial, o que ela considera pendente, e se ela percebe uma
migration que foi editada depois de aplicada.
"""

from __future__ import annotations

import json
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
