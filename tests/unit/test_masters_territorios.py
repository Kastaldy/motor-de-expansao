"""O casamento geográfico dos masters (`masters/territorios.py`): qual região de qual master contém
um município, e qual região o nome de uma unidade do pipeline cita.

Achado médio da revisão automática do #567 ("lógica nova sem teste"): `Regiao.contem`,
`mencionada_em`, `Master.regiao_de`, `regiao_do_pipeline`, `ufs_envolvidas` e
`municipios_sem_match` só eram testadas no #568, que as usa. O erro aqui não quebra nada à vista:
uma unidade cai na região errada (ou em nenhuma) e os números do master mudam em silêncio.
"""

from __future__ import annotations

import pytest

from motor_expansao.masters.territorios import masters_de_dict, municipios_sem_match, normalizar

CONFIG = {
    "masters": [
        {
            "id": "lit",
            "nome_planilha": "Litoral/ABC — TESTE",
            "nome_exibicao": "Litoral/ABC - TESTE",
            "regioes": [
                {
                    "id": "abcd",
                    "nome": "ABCD",
                    "tipo": "exclusividade",
                    "municipios": {"SP": ["Santo André", "São Bernardo do Campo"]},
                },
                {
                    "id": "litoral",
                    "nome": "Litoral",
                    "tipo": "exclusividade",
                    "municipios": {"SP": ["Santos", "Guarujá"]},
                },
            ],
        },
        {
            "id": "go",
            "nome_planilha": "GO — TESTE",
            "regioes": [
                {
                    "id": "go",
                    "nome": "Goiás",
                    "tipo": "exclusividade",
                    "ufs": ["GO"],
                    "excluir": {"GO": ["Formosa"]},
                }
            ],
        },
    ]
}


@pytest.fixture
def masters():
    return masters_de_dict(CONFIG)


def test_normalizar_tira_acento_e_pontuacao():
    assert normalizar("São José dos Campos") == "sao jose dos campos"
    assert normalizar("Ponta da Praia - Canal 7 (Santos)") == "ponta da praia canal 7 santos"
    assert normalizar("Santa Bárbara d'Oeste") == normalizar("Santa Barbara d Oeste")


def test_regiao_por_uf_com_excecao_e_por_lista(masters):
    go, lit = masters["go"], masters["lit"]
    assert go.regiao_de("GO", "Goiânia").id == "go"
    assert go.regiao_de("GO", "Formosa") is None
    assert go.regiao_de("DF", "Brasília") is None
    assert lit.regiao_de("SP", "SANTOS").id == "litoral"
    assert lit.regiao_de("SP", "São Paulo") is None


def test_contem_ignora_caixa_e_acento_da_uf_e_do_municipio(masters):
    go = masters["go"].regioes[0]
    assert go.contem("go", "GOIÂNIA")
    assert not go.contem("go", "formosa")  # a exclusão vale com qualquer grafia
    litoral = masters["lit"].regioes[1]
    assert litoral.contem("sp", "guaruja")
    assert not litoral.contem("RJ", "Santos")  # o município é o da UF certa


def test_pipeline_cita_municipio_entre_parenteses_sem_confundir_santo_andre(masters):
    lit = masters["lit"]
    assert lit.regiao_do_pipeline("Ponta da Praia - Canal 7 (Santos)", "SP").id == "litoral"
    assert lit.regiao_do_pipeline("Planalto SBC (São Bernardo do Campo)", "SP").id == "abcd"
    assert lit.regiao_do_pipeline("Santo André", "SP").id == "abcd"
    assert lit.regiao_do_pipeline("Campinas", "SP") is None


def test_a_citacao_e_de_palavra_inteira_e_respeita_a_uf(masters):
    litoral = masters["lit"].regioes[1]
    assert litoral.mencionada_em("Unidade Santos Centro", "SP")
    assert not litoral.mencionada_em("Unidade Santosville", "SP")  # pedaço de palavra não conta
    assert not litoral.mencionada_em("Unidade Santos", "RJ")  # outro estado
    assert litoral.mencionada_em("Unidade Santos", None)  # sem UF, vale o nome


def test_regiao_de_uf_inteira_aceita_tudo_menos_o_municipio_excluido(masters):
    go = masters["go"].regioes[0]
    assert go.mencionada_em("Setor Bueno", "GO")
    assert not go.mencionada_em("Formosa Centro", "GO")
    assert not go.mencionada_em("Setor Bueno", "DF")


def test_ufs_envolvidas_somam_as_ufs_inteiras_e_as_dos_municipios(masters):
    assert masters["lit"].ufs_envolvidas == frozenset({"SP"})
    assert masters["go"].ufs_envolvidas == frozenset({"GO"})
    juntos = masters_de_dict(
        {
            "masters": [
                {
                    "id": "dfgo",
                    "nome_planilha": "DF/GO — TESTE",
                    "regioes": [
                        {"id": "df", "nome": "DF", "tipo": "exclusividade", "ufs": ["DF"]},
                        {
                            "id": "entorno",
                            "nome": "Entorno",
                            "tipo": "exclusividade",
                            "municipios": {"GO": ["Luziânia"]},
                        },
                    ],
                }
            ]
        }
    )["dfgo"]
    assert juntos.ufs_envolvidas == frozenset({"DF", "GO"})


def test_municipio_da_config_que_nao_existe_na_base_vira_aviso(masters):
    faltando = municipios_sem_match(
        masters["lit"], {"SP": ["Santo André", "São Bernardo do Campo", "Santos"]}
    )
    assert faltando == [("litoral", "SP", "guaruja")]


def test_master_duplicado_na_config_falha():
    with pytest.raises(ValueError):
        masters_de_dict({"masters": [CONFIG["masters"][0], CONFIG["masters"][0]]})
