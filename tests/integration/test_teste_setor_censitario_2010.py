import json
from pathlib import Path

import h3
import pandas as pd

from motor_expansao.pipelines.teste_setor_censitario_2010 import (
    executar_experimento_setor_2010,
    resolver_cidades_alvo,
)


def _square(lng: float, lat: float, delta: float = 0.01) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[
            [lng - delta, lat - delta],
            [lng + delta, lat - delta],
            [lng + delta, lat + delta],
            [lng - delta, lat + delta],
            [lng - delta, lat - delta],
        ]],
    }


def test_resolver_cidades_alvo_por_nome_uf(tmp_path: Path):
    municipios_root = tmp_path / "ibge"
    municipios_root.mkdir(parents=True)
    payload = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"id": "3550308", "nome": "Sao Paulo"}, "geometry": _square(-46.63, -23.55, 0.2)},
            {"type": "Feature", "properties": {"id": "3509502", "nome": "Campinas"}, "geometry": _square(-47.06, -22.90, 0.2)},
        ],
    }
    (municipios_root / "municipios_SP.geojson").write_text(json.dumps(payload), encoding="utf-8")

    cidades = resolver_cidades_alvo(["Sao Paulo/SP", "Campinas/SP"], municipios_root=municipios_root)

    assert [cidade["cod_municipio"] for cidade in cidades] == ["3550308", "3509502"]


def test_experimento_setor_2010_gera_outputs_isolados_sem_zero_silencioso(tmp_path: Path):
    setores_root = tmp_path / "setores_2010"
    staging_dir = tmp_path / "staging"
    outputs_dir = tmp_path / "outputs"
    report_path = tmp_path / "reports" / "teste_setor_2010.md"
    setores_root.mkdir(parents=True)

    geometria = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"cod_setor": "355030800000001", "cod_municipio": "3550308"},
                "geometry": _square(-46.63, -23.55),
            },
            {
                "type": "Feature",
                "properties": {"cod_setor": "355030800000002", "cod_municipio": "3550308"},
                "geometry": _square(-46.58, -23.52),
            },
            {
                "type": "Feature",
                "properties": {"cod_setor": "350950200000001", "cod_municipio": "3509502"},
                "geometry": _square(-47.06, -22.90),
            },
        ],
    }
    geometria_path = setores_root / "setores_2010_malha.geojson"
    geometria_path.write_text(json.dumps(geometria), encoding="utf-8")

    atributos = pd.DataFrame(
        [
            {"cod_setor": "355030800000001", "cod_municipio": "3550308", "renda_media": 8000, "pop_total": 1200, "pop_18_45": 700},
            {"cod_setor": "355030800000002", "cod_municipio": "3550308", "renda_media": 2500, "pop_total": 500, "pop_18_45": 150},
            {"cod_setor": "350950200000001", "cod_municipio": "3509502", "renda_media": 5000, "pop_total": 900, "pop_18_45": 450},
        ]
    )
    atributos_path = setores_root / "setores_2010_renda.parquet"
    atributos.to_parquet(atributos_path, index=False)

    base_oficial = pd.DataFrame(
        [
            {
                "hex_id": h3.latlng_to_cell(-23.55, -46.63, 7),
                "lat": -23.55,
                "lng": -46.63,
                "uf": "SP",
                "regiao": "SE",
                "cod_municipio": "3550308",
                "nome_municipio": "Sao Paulo",
                "renda_per_capita": 4000,
                "pop_total": 0,
                "pop_18_45": 1000,
                "populacao_proxy": 1000,
                "hex_score_estrutural": 60.0,
                "score_priorizacao": 62.0,
                "fonte_renda": "oficial",
                "fonte_populacao": "oficial",
            },
            {
                "hex_id": h3.latlng_to_cell(-23.52, -46.58, 7),
                "lat": -23.52,
                "lng": -46.58,
                "uf": "SP",
                "regiao": "SE",
                "cod_municipio": "3550308",
                "nome_municipio": "Sao Paulo",
                "renda_per_capita": 4000,
                "pop_total": 0,
                "pop_18_45": 1000,
                "populacao_proxy": 1000,
                "hex_score_estrutural": 60.0,
                "score_priorizacao": 62.0,
                "fonte_renda": "oficial",
                "fonte_populacao": "oficial",
            },
            {
                "hex_id": h3.latlng_to_cell(-23.70, -46.90, 7),
                "lat": -23.70,
                "lng": -46.90,
                "uf": "SP",
                "regiao": "SE",
                "cod_municipio": "3550308",
                "nome_municipio": "Sao Paulo",
                "renda_per_capita": 4000,
                "pop_total": 0,
                "pop_18_45": 1000,
                "populacao_proxy": 1000,
                "hex_score_estrutural": 60.0,
                "score_priorizacao": 62.0,
                "fonte_renda": "oficial",
                "fonte_populacao": "oficial",
            },
            {
                "hex_id": h3.latlng_to_cell(-22.90, -47.06, 7),
                "lat": -22.90,
                "lng": -47.06,
                "uf": "SP",
                "regiao": "SE",
                "cod_municipio": "3509502",
                "nome_municipio": "Campinas",
                "renda_per_capita": 3500,
                "pop_total": 0,
                "pop_18_45": 800,
                "populacao_proxy": 800,
                "hex_score_estrutural": 50.0,
                "score_priorizacao": 51.0,
                "fonte_renda": "oficial",
                "fonte_populacao": "oficial",
            },
        ]
    )
    base_oficial_path = tmp_path / "brasil_estrutural.parquet"
    base_oficial.to_parquet(base_oficial_path, index=False)

    resultado = executar_experimento_setor_2010(
        cidades_alvo=[
            {"cidade": "Sao Paulo", "uf": "SP", "cod_municipio": "3550308"},
            {"cidade": "Campinas", "uf": "SP", "cod_municipio": "3509502"},
        ],
        base_oficial_path=base_oficial_path,
        setores_root=setores_root,
        geometria_path=geometria_path,
        atributos_path=atributos_path,
        staging_dir=staging_dir,
        outputs_dir=outputs_dir,
        report_path=report_path,
    )

    assert resultado["total_hex"] == 4
    assert resultado["hex_com_setor"] == 3

    hex_df = pd.read_parquet(staging_dir / "hexagonos_teste_setor_2010.parquet")
    comp_df = pd.read_parquet(staging_dir / "comparativo_municipal_vs_setor_2010.parquet")
    report = report_path.read_text(encoding="utf-8")

    sem_match = hex_df.loc[hex_df["setor_match_status"] == "sem_match_setor"].iloc[0]
    assert pd.isna(sem_match["hex_score_setor_2010"])
    assert pd.isna(sem_match["renda_setor_2010"])
    assert "hexagonos enriquecidos com setor 2010: 3 de 4" in report
    assert "hex sem setor permaneceram como `sem_match_setor`" in report

    sao_paulo = comp_df[comp_df["cidade"] == "Sao Paulo"]
    assert sao_paulo["hex_score_estrutural"].nunique() == 1
    assert sao_paulo["hex_score_setor_2010"].nunique(dropna=True) == 2
    assert (outputs_dir / "top_hexagonos_setor_2010.csv").exists()
    assert (outputs_dir / "top_comparativo_por_cidade.csv").exists()
