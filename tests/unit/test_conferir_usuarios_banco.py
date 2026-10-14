"""Testes do conferidor de usuários do corte do banco (`scripts/conferir_usuarios_banco.py`).

O conferidor responde, antes de ligar `MOTOR_DATABASE_URL`, se cada pessoa que entra hoje
(Authelia) existe no banco e vê as mesmas abas que vê pelo `acesso_abas.json`. Os logins aqui
são fictícios — nenhum dado real de usuário entra no repositório.

O teste de DRIFT é o que importa a longo prazo: o script replica o de-para capacidade -> aba do
servidor (ele roda no host da VPS, sem o repo instalado), e uma réplica que desalinha daria
"tudo casa" para uma pessoa que perde aba ao ligar o banco.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from scripts import conferir_usuarios_banco as conf

_SERVER = Path(__file__).resolve().parents[2] / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import acesso  # noqa: E402

_USERS_YML = """\
---
# comentario de topo
users:
  fulano_teste:
    disabled: false
    displayname: "Fulano Teste"
    password: "$argon2id$v=19$m=65536,t=3,p=4$naoeumhashdeverdade"
    email: fulano@example.invalid
    groups: []
  beltrana_teste:
    displayname: "Beltrana Teste"
    password: "$argon2id$v=19$m=65536,t=3,p=4$naoeumhashdeverdade"
    email: beltrana@example.invalid
...
"""

_JSON = {
    "_comentario": "chave de comentario, nao e pessoa",
    "*": ["mapa"],
    "fulano_teste": ["mapa", "oportunidades", "imobiliaria", "viabilidade"],
    "beltrana_teste": ["executiva"],
}

_BANCO_OK = (
    "beltrana_teste|consultoria|t|executiva\n"
    "fulano_teste|expansao|t|imobiliaria,mapa,oportunidades,viabilidade\n"
)


def _rodar(
    tmp_path: Path,
    banco: str,
    *extra: str,
    users: str = _USERS_YML,
    mapa: dict | None = None,
) -> tuple[int, str]:
    yml = tmp_path / "users_database.yml"
    yml.write_text(users, encoding="utf-8")
    js = tmp_path / "acesso_abas.json"
    js.write_text(json.dumps(_JSON if mapa is None else mapa), encoding="utf-8")
    saida = io.StringIO()
    rc = conf.main([str(yml), str(js), *extra], stdin=io.StringIO(banco), stdout=saida)
    return rc, saida.getvalue()


def _linha(saida: str, login: str) -> str:
    return next(linha for linha in saida.splitlines() if linha.startswith(login + " "))


# ---------------------------------------------------------------------------- drift


def test_drift_de_para_capacidade_aba_igual_ao_servidor():
    """A réplica do script tem de ser IGUAL ao `CAPACIDADE_QUE_SUSTENTA_A_ABA` do servidor."""
    assert conf.CAPACIDADE_POR_ABA == acesso.CAPACIDADE_QUE_SUSTENTA_A_ABA


def test_drift_abas_validas_e_sensiveis_iguais_ao_servidor():
    assert frozenset(conf.ABAS) == acesso.ABAS_VALIDAS
    assert conf.ABAS_SENSIVEIS == acesso.ABAS_SENSIVEIS


def test_sql_e_gerado_da_constante():
    sql = conf.sql_da_consulta()
    for aba, capacidade in conf.CAPACIDADE_POR_ABA.items():
        assert f"('{capacidade}','{aba}')" in sql
    assert sql.count("('") == len(conf.CAPACIDADE_POR_ABA)


def test_flag_sql_imprime_a_consulta_e_sai_zero():
    saida = io.StringIO()
    assert conf.main(["--sql"], stdin=io.StringIO(""), stdout=saida) == 0
    assert saida.getvalue().strip() == conf.sql_da_consulta()


# ---------------------------------------------------------------------------- vereditos


def test_tudo_casa_sai_zero(tmp_path):
    rc, saida = _rodar(tmp_path, _BANCO_OK)
    assert rc == 0
    assert _linha(saida, "fulano_teste").endswith("ok")
    assert _linha(saida, "beltrana_teste").endswith("ok")
    assert "pessoas com pendência: 0" in saida


def test_nunca_imprime_hash_nem_email(tmp_path):
    _, saida = _rodar(tmp_path, _BANCO_OK)
    assert "argon2" not in saida
    assert "@" not in saida


def test_falta_no_banco(tmp_path):
    rc, saida = _rodar(tmp_path, "beltrana_teste|consultoria|t|executiva\n")
    assert rc == 1
    assert "FALTA NO BANCO" in _linha(saida, "fulano_teste")


def test_falta_no_authelia(tmp_path):
    rc, saida = _rodar(tmp_path, _BANCO_OK + "sicrano_teste|growth|t|mapa\n")
    assert rc == 1
    assert "falta no Authelia" in _linha(saida, "sicrano_teste")


def test_inativo_que_entra_hoje_e_pendencia(tmp_path):
    banco = _BANCO_OK.replace("beltrana_teste|consultoria|t|", "beltrana_teste|consultoria|f|")
    rc, saida = _rodar(tmp_path, banco)
    assert rc == 1
    linha = _linha(saida, "beltrana_teste")
    assert "(INATIVO)" in linha
    assert "inativo no banco" in linha


def test_inativo_fora_do_authelia_e_coerente(tmp_path):
    rc, saida = _rodar(tmp_path, _BANCO_OK + "sicrano_teste|growth|f|mapa\n")
    assert rc == 0
    assert "coerente" in _linha(saida, "sicrano_teste")


def test_abas_mudam_ganha_e_perde(tmp_path):
    banco = _BANCO_OK.replace(
        "fulano_teste|expansao|t|imobiliaria,mapa,oportunidades,viabilidade",
        "fulano_teste|expansao|t|executiva,mapa,oportunidades,viabilidade",
    )
    rc, saida = _rodar(tmp_path, banco)
    assert rc == 1
    linha = _linha(saida, "fulano_teste")
    assert "ganha executiva" in linha
    assert "PERDE imobiliaria" in linha


def test_aceitar_a_mudanca_exata_vira_aceita(tmp_path):
    banco = _BANCO_OK.replace(
        "beltrana_teste|consultoria|t|executiva", "beltrana_teste|lideres|t|executiva,mapa"
    )
    rc, saida = _rodar(tmp_path, banco, "--aceitar", "beltrana_teste:+mapa")
    assert rc == 0
    assert "(ACEITA)" in _linha(saida, "beltrana_teste")


def test_aceitar_mudanca_diferente_da_real_e_pendencia(tmp_path):
    banco = _BANCO_OK.replace(
        "beltrana_teste|consultoria|t|executiva", "beltrana_teste|lideres|t|executiva,mapa"
    )
    rc, saida = _rodar(tmp_path, banco, "--aceitar", "beltrana_teste:+mapa,+oportunidades")
    assert rc == 1
    linha = _linha(saida, "beltrana_teste")
    assert "ACEITA" not in linha
    assert "--aceitar declarado" in linha


def test_aceitar_sem_mudanca_real_e_pendencia(tmp_path):
    rc, saida = _rodar(tmp_path, _BANCO_OK, "--aceitar", "fulano_teste:+executiva")
    assert rc == 1
    assert "--aceitar declarado" in _linha(saida, "fulano_teste")


def test_aceitar_casa_sem_diferenciar_maiuscula(tmp_path):
    banco = _BANCO_OK.replace(
        "beltrana_teste|consultoria|t|executiva", "beltrana_teste|lideres|t|executiva,mapa"
    )
    rc, _ = _rodar(tmp_path, banco, "--aceitar", "Beltrana_Teste:+mapa")
    assert rc == 0


def test_maiuscula_e_minuscula_casam_entre_as_fontes(tmp_path):
    banco = _BANCO_OK.replace("fulano_teste|", "FULANO_Teste|")
    users = _USERS_YML.replace("  beltrana_teste:", "  Beltrana_TESTE:")
    rc, saida = _rodar(tmp_path, banco, users=users)
    assert rc == 0, saida
    assert "pessoas com pendência: 0" in saida
    # Uma linha por pessoa, não uma por grafia.
    assert sum(1 for linha in saida.splitlines() if linha.casefold().startswith("fulano")) == 1


def test_comentario_e_curinga_nao_sao_pessoas(tmp_path):
    rc, saida = _rodar(tmp_path, _BANCO_OK)
    assert rc == 0
    assert "JSON: 2 |" in saida
    assert not any(linha.startswith(("_comentario", "* ")) for linha in saida.splitlines())


def test_quem_esta_fora_do_json_e_comparado_ao_curinga_sem_aba_sensivel(tmp_path):
    users = _USERS_YML.replace("users:\n", "users:\n  sicrano_teste:\n    disabled: false\n")
    mapa = {**_JSON, "*": ["mapa", "executiva"]}  # o curinga nunca concede a sensível
    rc, saida = _rodar(
        tmp_path, _BANCO_OK + "sicrano_teste|expansao|t|mapa\n", users=users, mapa=mapa
    )
    assert rc == 0, saida
    assert "mapa (*)" in _linha(saida, "sicrano_teste")


def test_aba_desconhecida_no_json_e_descartada(tmp_path):
    mapa = {**_JSON, "beltrana_teste": ["executiva", "aba_que_nao_existe"]}
    rc, _ = _rodar(tmp_path, _BANCO_OK, mapa=mapa)
    assert rc == 0


# ---------------------------------------------------------------------------- erro de uso


@pytest.mark.parametrize(
    "aceitar",
    ["fulano_teste", "fulano_teste:", ":+mapa", "fulano_teste:mapa", "fulano_teste:+aba_x"],
)
def test_aceitar_malformado_sai_dois(tmp_path, aceitar):
    rc, _ = _rodar(tmp_path, _BANCO_OK, "--aceitar", aceitar)
    assert rc == 2


def test_linha_do_banco_fora_do_formato_sai_dois(tmp_path):
    rc, _ = _rodar(tmp_path, "fulano_teste;expansao;t;mapa\n")
    assert rc == 2


def test_json_que_desligaria_o_controle_sai_dois(tmp_path):
    rc, _ = _rodar(tmp_path, _BANCO_OK, mapa={"fulano_teste": "mapa"})
    assert rc == 2


def test_sem_arquivos_sai_dois():
    assert conf.main([], stdin=io.StringIO(""), stdout=io.StringIO()) == 2


def test_authelia_le_so_as_chaves_de_users():
    assert conf.logins_do_authelia(_USERS_YML.splitlines(keepends=True)) == {
        "fulano_teste",
        "beltrana_teste",
    }


def test_authelia_aceita_a_saida_do_grep_do_runbook():
    """O runbook passa só as linhas de login (grep), nunca o arquivo inteiro."""
    filtrado = "users:\n  fulano_teste:\n  beltrana_teste:\n"
    assert conf.logins_do_authelia(filtrado.splitlines(keepends=True)) == {
        "fulano_teste",
        "beltrana_teste",
    }
