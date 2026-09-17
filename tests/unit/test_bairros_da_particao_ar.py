"""Os barrios argentinos chegam ao Relatorio Municipal.

A particao `setores_censitarios_2022_geo` que `exportar_piloto_ar.escrever_setores_geo` grava
tinha o barrio em `nome_distrito`, mas nao as colunas que os DOIS leitores de bairro do
relatorio exigem (`nome_bairro`, `nome_subdistrito`, `bbox_*`, `area_setor_km2_ibge`). A
leitura falhava e o fallback devolvia vazio em silencio: na Comuna 1 (CABA), com 352 radios
em 8 barrios, a Comparacao das Regioes saia "Nao disponivel" em toda linha e a pagina Bairros
Oficiais dizia que o municipio "nao tem bairro nem distrito mapeado" (Juan, 2026-09-17).

O teste e' de CONTRATO entre os dois lados da costura: o exportador escreve num diretorio
temporario e os leitores do relatorio leem exatamente o que ele escreveu.
"""

from __future__ import annotations

import json

import h3
import pandas as pd
import pytest
from shapely.geometry import box

from motor_expansao.dashboard.relatorio_municipal import (
    _carregar_bairros_por_hex,
    carregar_bairros_geo,
)
from motor_expansao.pipelines import exportar_piloto_ar as exp

_COLUNAS_DOS_LEITORES = (
    "nome_bairro",
    "nome_subdistrito",
    "bbox_minx",
    "bbox_miny",
    "bbox_maxx",
    "bbox_maxy",
    "area_setor_km2_ibge",
)

# Dois radios lado a lado em Retiro e San Telmo (CABA), ~1 km x ~1 km cada.
_RADIOS = {
    "020070101": box(-58.380, -34.595, -58.370, -34.585),
    "020070202": box(-58.375, -34.625, -58.365, -34.615),
}
_LOCALIDADES = {"Retiro": (-58.375, -34.590), "San Telmo": (-58.370, -34.620)}


@pytest.fixture
def particao_ar(tmp_path, monkeypatch):
    dados = tmp_path / "dados"
    (dados / "censo_indec").mkdir(parents=True)
    (dados / "malha_admin").mkdir(parents=True)
    pd.DataFrame(
        {
            "COD_2022": list(_RADIOS),
            "PROV": ["02", "02"],
            "DEPTO": ["007", "007"],
            "POB_TOT_P": [1200, 800],
            "VIV_TOT_P": [500, 400],
            "geometry": [g.wkb for g in _RADIOS.values()],
        }
    ).to_parquet(dados / "censo_indec" / "radios-2022.parquet", index=False)
    (dados / "malha_admin" / "localidades.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"nombre": nome},
                        "geometry": {"type": "Point", "coordinates": list(xy)},
                    }
                    for nome, xy in _LOCALIDADES.items()
                ],
            }
        ),
        encoding="utf-8",
    )
    saida = tmp_path / "saida"
    monkeypatch.setattr(exp, "CAMINHOS", exp.Caminhos(dados, saida))
    hx = pd.DataFrame(columns=["h3_id", "renda_estimada_usd", "pop_total"])
    exp.escrever_setores_geo(saida, {"02007": ("CA", "Comuna 1")}, hx)
    return saida / "outputs" / "setores_censitarios_2022_geo"


def test_particao_ar_tem_as_colunas_que_os_leitores_de_bairro_exigem(particao_ar):
    df = pd.read_parquet(particao_ar / "uf=CA" / "cod_municipio=02007" / "part-000.parquet")

    faltando = [c for c in _COLUNAS_DOS_LEITORES if c not in df.columns]
    assert faltando == []
    linha = df.set_index("cod_setor").loc["020070101"]
    assert (linha["bbox_minx"], linha["bbox_miny"], linha["bbox_maxx"], linha["bbox_maxy"]) == (
        pytest.approx(-58.380), pytest.approx(-34.595), pytest.approx(-58.370), pytest.approx(-34.585)
    )
    assert linha["area_setor_km2_ibge"] == pytest.approx(linha["area_setor_m2"] / 1e6)
    # O INDEC nao publica bairro nem subdistrito: as colunas existem e vem VAZIAS, e a
    # cascata do relatorio cai no `nome_distrito`, que e' onde mora o barrio.
    assert df["nome_bairro"].isna().all()
    assert df["nome_subdistrito"].isna().all()
    assert sorted(df["nome_distrito"]) == ["Retiro", "San Telmo"]


def test_rotulo_por_hexagono_le_os_barrios_da_particao_ar(particao_ar):
    mapa = _carregar_bairros_por_hex("CA", "02007", particao_ar)

    esperado = {
        h3.latlng_to_cell(-34.590, -58.375, 7): "Retiro",
        h3.latlng_to_cell(-34.620, -58.370, 7): "San Telmo",
    }
    assert mapa == esperado


def test_bairros_oficiais_desenham_os_barrios_da_particao_ar(particao_ar):
    geo = carregar_bairros_geo("CA", "02007", particao_ar)

    nomes = sorted(b["nome"] for b in geo["bairros"] if not b.get("sobra"))
    assert nomes == ["Retiro", "San Telmo"]
    assert geo["cobertura"] == pytest.approx(1.0)
