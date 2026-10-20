"""DEC-076 (BLK-BAIRRO-01 fase 2): o nome de bairro vem do CNEFE 2022, com o IBGE de reserva.

O caso que originou o bloco: em Sao Jose dos Campos o `NM_BAIRRO` da malha traz as regioes de
planejamento da prefeitura ("Setor Socioeconômico 14"), e o operador via no mapa de fundo
"Jardim Satélite". O CNEFE da' o bairro dominante de cada setor.

Testes puros: particoes e artefato de mentira em `tmp_path`, sem malha real e sem rede.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest
from shapely.geometry import box

from motor_expansao.dashboard import bairro_cnefe as bc

_UF = "SP"
_COD = "3549904"  # Sao Jose dos Campos
_MUNI = box(-45.95, -23.25, -45.80, -23.15)
_LAT, _LNG = -23.2005, -45.8985  # dentro do setor 0


def _cod_setor(i: int) -> str:
    return f"{_COD}05{i:06d}"


def _escrever_particao(censo_dir) -> None:
    from shapely import wkb

    linhas = []
    for i in range(4):
        geom = box(-45.90 + i * 0.002, -23.201, -45.90 + (i + 1) * 0.002, -23.199)
        minx, miny, maxx, maxy = geom.bounds
        linhas.append(
            {
                "cod_setor": _cod_setor(i),
                "uf": _UF,
                "cod_municipio": _COD,
                "nome_municipio": "São José dos Campos",
                "cod_bairro": "0003549904014",
                "nome_bairro": "Setor Socioeconômico 14",
                "nome_subdistrito": pd.NA,
                "nome_distrito": "São José dos Campos",
                "geometry_wkb": wkb.dumps(geom),
                "bbox_minx": minx,
                "bbox_miny": miny,
                "bbox_maxx": maxx,
                "bbox_maxy": maxy,
                "pop_total_setor_2022": [900.0, 800.0, 50.0, 10.0][i],
                "domicilios_particulares_ocupados_setor_2022": 300.0,
                "renda_responsavel_media_setor_2022": 2500.0,
                "area_setor_km2_ibge": 0.05,
                "renda_per_capita_setor_2022_calibrada": 1500.0,
                "score_setor_2022_calibrado": 40.0,
            }
        )
    destino = censo_dir / f"uf={_UF}" / f"cod_municipio={_COD}"
    destino.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(linhas).to_parquet(destino / "part-000.parquet", index=False)


def _escrever_artefato(raiz, uf: str = _UF) -> None:
    destino = raiz / "staging" / bc.SUBDIR_ARTEFATO / f"uf={uf}"
    destino.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "cod_setor": [_cod_setor(i) for i in range(4)],
            "cod_municipio": [_COD] * 4,
            "uf": [uf] * 4,
            "bairro_cnefe": ["JARDIM SATELITE", "JARDIM SATELITE", "SAO JOSE DOS CAMPOS", "ZONA RURAL"],
            "classe": ["BAIRRO", "BAIRRO", "MUNICIPIO", "RURAL"],
            "participacao": [0.81, 1.0, 0.9, 1.0],
            "n_enderecos": [100, 100, 100, 100],
            "n_domicilios": [90, 90, 90, 90],
        }
    ).to_parquet(destino / "part-000.parquet", index=False)


@pytest.fixture
def ambiente(tmp_path):
    """`<data>/outputs/setores_censitarios_2022_geo` + malha; o artefato o teste decide."""
    from motor_expansao.api import service
    from motor_expansao.api.settings import Settings

    ibge_dir = tmp_path / "ibge"
    ibge_dir.mkdir()
    (ibge_dir / f"municipios_{_UF}.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"codarea": _COD},
                        "geometry": _MUNI.__geo_interface__,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    censo_dir = tmp_path / "outputs" / "setores_censitarios_2022_geo"
    _escrever_particao(censo_dir)
    service._carregar_malha.cache_clear()
    try:
        yield Settings(ibge_dir=ibge_dir, censo_geo_dir=censo_dir), tmp_path
    finally:
        service._carregar_malha.cache_clear()


# --- grafia ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("JARDIM SATELITE", "Jardim Satélite"),
        ("SAO JOSE OPERARIO", "São José Operário"),
        ("VILA DAS INDUSTRIAS", "Vila das Indústrias"),
        ("CENTRO", "Centro"),
        ("JARDIM SAO JOSE II", "Jardim São José II"),
        ("VILA XV DE NOVEMBRO", "Vila XV de Novembro"),
        ("CONJUNTO HABITACIONAL COHAB", "Conjunto Habitacional COHAB"),
        ("VILA E", "Vila E"),  # conectivo no FIM e' letra de loteamento, nao "e"
        ("JARDIM CEU AZUL", "Jardim Céu Azul"),
        ("SANTA BARBARA D'OESTE", "Santa Bárbara D'Oeste"),
        ("  PARQUE   INDUSTRIAL ", "Parque Industrial"),  # sem acento: fora do dicionario
        ("JARDIM ALVORADA", "Jardim Alvorada"),  # Alvorada NAO leva acento
    ],
)
def test_title_case_portugues_com_acento_por_dicionario(bruto: str, esperado: str) -> None:
    assert bc.title_case_portugues(bruto) == esperado


def test_dicionario_de_acentos_e_conservador() -> None:
    """Cada valor so' difere da chave por acento/caixa, e as palavras ambiguas ficam de fora."""
    for chave, grafia in bc._ACENTOS.items():
        assert bc.normalizar_nome(grafia) == chave, chave
        assert grafia != grafia.upper(), chave
        assert chave not in bc._CONECTIVOS
    # verbo "sabia", preposicao "para", conjuncao "se", Franca (cidade) x França (pais)
    for ambigua in ("SABIA", "PARA", "SE", "FRANCA", "ALVORADA", "JARDIM", "VILA"):
        assert ambigua not in bc._ACENTOS


def test_grafia_do_ibge_do_mesmo_municipio_vence() -> None:
    assert bc.formatar_nome_cnefe("JARDIM SATELITE", {"JARDIM SATELITE": "Jd. Satélite"}) == (
        "Jd. Satélite"
    )
    # Sem casamento -> Title Case.
    assert bc.formatar_nome_cnefe("BOSQUE DOS EUCALIPTOS", {"CENTRO": "Centro"}) == (
        "Bosque dos Eucaliptos"
    )


def test_grafia_toda_maiuscula_do_ibge_nao_ensina_acento() -> None:
    setores = pd.DataFrame({"nome_bairro": ["CENTRO", "Vila Ema", "Vila Ema", "VILA EMA"]})
    grafias = bc._grafias_por_municipio(setores, pd.Series(["1"] * 4))
    assert grafias == {"1": {"VILA EMA": "Vila Ema"}}


# --- aplicacao: o artefato e' OPCIONAL ------------------------------------------------------


def test_sem_artefato_devolve_o_MESMO_frame(ambiente) -> None:
    settings, _ = ambiente
    from motor_expansao.dashboard.data import read_censo_geo_partition

    setores = read_censo_geo_partition(settings.censo_geo_dir, _UF, _COD)
    assert bc.aplicar_bairro_cnefe(setores, censo_geo_dir=settings.censo_geo_dir) is setores


def test_artefato_de_OUTRA_uf_tambem_devolve_o_mesmo_frame(ambiente) -> None:
    settings, raiz = ambiente
    _escrever_artefato(raiz, uf="RJ")
    from motor_expansao.dashboard.data import read_censo_geo_partition

    setores = read_censo_geo_partition(settings.censo_geo_dir, _UF, _COD)
    assert bc.aplicar_bairro_cnefe(setores, censo_geo_dir=settings.censo_geo_dir) is setores


def test_regra_de_nome_por_classe(ambiente) -> None:
    settings, raiz = ambiente
    _escrever_artefato(raiz)
    from motor_expansao.dashboard.data import read_censo_geo_partition

    setores = read_censo_geo_partition(settings.censo_geo_dir, _UF, _COD)
    out = bc.aplicar_bairro_cnefe(setores, censo_geo_dir=settings.censo_geo_dir)
    assert out is not setores
    assert list(out["nome_bairro"]) == [
        "Jardim Satélite",            # BAIRRO
        "Jardim Satélite",            # BAIRRO
        "Setor Socioeconômico 14",    # MUNICIPIO -> reserva IBGE
        "Zona rural",                 # RURAL
    ]
    assert list(out["fonte_bairro"]) == ["cnefe", "cnefe", "ibge", "cnefe"]
    # A chave sintetica junta o bairro do CNEFE no municipio; a do IBGE fica intacta na reserva.
    assert out["cod_bairro"].iat[0] == out["cod_bairro"].iat[1] == f"cnefe:{_COD}:JARDIM SATELITE"
    assert out["cod_bairro"].iat[2] == "0003549904014"
    assert set(out["nome_bairro_ibge"]) == {"Setor Socioeconômico 14"}
    # Nao muta a entrada.
    assert set(setores["nome_bairro"]) == {"Setor Socioeconômico 14"}


# --- superficies -----------------------------------------------------------------------------


def _ponto(settings):
    from motor_expansao.api.service import _resolver_e_carregar
    from motor_expansao.dashboard.censo_point import (
        agregar_perfil_bairro_distrito,
        analisar_ponto_censitario_setores,
    )

    uf, cod, setores_df = _resolver_e_carregar(_LAT, _LNG, settings)
    res = analisar_ponto_censitario_setores(_LAT, _LNG, setores_df, raio_km=1.0)
    perfil = agregar_perfil_bairro_distrito(
        setores_df,
        cod_bairro=res.get("cod_bairro_ponto"),
        nome_bairro=res.get("nome_bairro_ponto"),
        nome_distrito=res.get("nome_distrito_ponto"),
        uf=uf,
        cod_municipio=cod,
    )
    return setores_df, res, perfil


def test_ponto_sem_artefato_segue_o_ibge_byte_a_byte(ambiente) -> None:
    settings, _ = ambiente
    from motor_expansao.dashboard.data import read_censo_geo_partition

    setores_df, res, perfil = _ponto(settings)
    pd.testing.assert_frame_equal(
        setores_df, read_censo_geo_partition(settings.censo_geo_dir, _UF, _COD)
    )
    assert res["nome_bairro_ponto"] == "Setor Socioeconômico 14"
    assert perfil["unidade_nome"] == "Setor Socioeconômico 14"
    assert perfil["n_setores_unidade"] == 4


def test_ponto_com_artefato_le_o_bairro_do_cnefe(ambiente) -> None:
    settings, raiz = ambiente
    _escrever_artefato(raiz)

    _setores, res, perfil = _ponto(settings)
    assert res["nome_bairro_ponto"] == "Jardim Satélite"
    assert res["unidade_ponto_rotulo"] == "Jardim Satélite"
    # O perfil do bairro agrega o bairro do CNEFE (2 setores), nao a regiao da prefeitura (4).
    assert perfil["unidade_nome"] == "Jardim Satélite"
    assert perfil["n_setores_unidade"] == 2


def test_hexagono_do_relatorio_municipal_e_da_ficha(ambiente) -> None:
    from motor_expansao.dashboard.relatorio_municipal import (
        _carregar_bairros_por_hex,
        bairros_por_hex_de_setores,
    )

    settings, raiz = ambiente
    antes = _carregar_bairros_por_hex(_UF, _COD, settings.censo_geo_dir)
    assert set(antes.values()) == {"Setor Socioeconômico 14"}

    _escrever_artefato(raiz)
    depois = _carregar_bairros_por_hex(_UF, _COD, settings.censo_geo_dir)
    assert set(depois.values()) == {"Jardim Satélite"}
    assert depois.keys() == antes.keys()
    # A ficha nomeia o hexagono pelos setores do PONTO: a mesma regra da' o mesmo nome.
    from motor_expansao.api.service import _resolver_e_carregar

    _uf, _cod, setores_df = _resolver_e_carregar(_LAT, _LNG, settings)
    assert bairros_por_hex_de_setores(setores_df) == depois


def test_bairros_oficiais_e_nota_da_pagina_6(ambiente) -> None:
    from motor_expansao.dashboard.relatorio_municipal import (
        _nota_fonte_bairro,
        carregar_bairros_geo,
    )

    settings, raiz = ambiente
    sem = carregar_bairros_geo(_UF, _COD, settings.censo_geo_dir)
    assert "fonte_bairro" not in sem
    assert {b["nome"] for b in sem["bairros"]} == {"Setor Socioeconômico 14"}
    assert "CNEFE" not in _nota_fonte_bairro({"bairros_geo": sem})

    _escrever_artefato(raiz)
    com = carregar_bairros_geo(_UF, _COD, settings.censo_geo_dir)
    assert com["fonte_bairro"] == "cnefe"
    assert {b["nome"] for b in com["bairros"]} == {
        "Jardim Satélite", "Setor Socioeconômico 14", "Zona rural",
    }
    assert "CNEFE" in _nota_fonte_bairro({"bairros_geo": com})


def test_artefato_trocado_no_disco_e_relido_sem_restart(ambiente) -> None:
    """O cache e' por (caminho, mtime): a ausencia nunca fica memorizada."""
    settings, raiz = ambiente
    raiz_artefato = bc.diretorio_bairro_cnefe(settings.censo_geo_dir)
    assert bc.ler_bairro_cnefe_uf(raiz_artefato, _UF) is None
    _escrever_artefato(raiz)
    mapa = bc.ler_bairro_cnefe_uf(raiz_artefato, _UF)
    assert mapa is not None
    assert mapa[_cod_setor(0)] == ("JARDIM SATELITE", "BAIRRO")
