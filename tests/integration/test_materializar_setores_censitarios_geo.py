from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import from_wkb
from shapely.geometry import box

from motor_expansao.pipelines.materializar_setores_censitarios_geo import (
    COLUNAS_ARTEFATO,
    CRS_ORIGEM,
    escrever_particoes,
    gerar_relatorio,
    ler_particao_setores,
    montar_base_setorial_uf,
)


def _malha_fake() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "cod_setor": ["355030801000001", "355030801000002", "355030802000001"],
            "uf": ["SP", "SP", "SP"],
            "cod_uf": ["35", "35", "35"],
            "cod_municipio": ["3550308", "3550308", "3550308"],
            "nome_municipio": ["SAO PAULO", "SAO PAULO", "SAO PAULO"],
            # BLK-RELMUN-02: NM_BAIRRO materializado (cobertura heterogenea: 1 setor sem bairro).
            "nome_bairro": ["Bela Vista", "Centro", pd.NA],
            "cod_bairro": ["3550308001", "3550308002", pd.NA],
            "situacao_setor": ["Urbana", "Urbana", "Urbana"],
            "area_setor_km2_ibge": [1.0, 1.0, 1.0],
            "geometry": [
                box(-46.70, -23.60, -46.69, -23.59),
                box(-46.69, -23.60, -46.68, -23.59),
                box(-46.68, -23.60, -46.67, -23.59),
            ],
        },
        crs=CRS_ORIGEM,
    )


# Basico e renda vem EMBARALHADOS (ordem diferente da malha) de proposito: o join agora e' por
# CHAVE `cod_setor`, entao a ordem das linhas nao pode mais importar. A verdade por setor e':
#   A=...801000001 -> pop 900,  renda_resp 3000  (renda_pc 1000)
#   B=...801000002 -> pop 1800, renda_resp 4500  (renda_pc 1500)
#   C=...802000001 -> pop 2700, renda_resp 6000  (renda_pc 2000)
def _basico_fake() -> pd.DataFrame:
    # Ordem [B, C, A] — diferente da malha [A, B, C].
    return pd.DataFrame(
        {
            "cod_setor": ["355030801000002", "355030802000001", "355030801000001"],
            "uf": ["SP", "SP", "SP"],
            "cod_uf": ["35", "35", "35"],
            "cod_municipio": ["3550308", "3550308", "3550308"],
            "area_setor_km2_ibge": [1.0, 1.0, 1.0],
            "pop_total_setor_2022": [1800.0, 2700.0, 900.0],
            "domicilios_particulares_ocupados_setor_2022": [600.0, 900.0, 300.0],
            "avg_moradores_domicilio_setor_2022": [3.0, 3.0, 3.0],
        }
    )


def _renda_fake() -> pd.DataFrame:
    # Ordem [C, A, B] — diferente da malha e do basico.
    return pd.DataFrame(
        {
            "cod_setor": ["355030802000001", "355030801000001", "355030801000002"],
            "uf": ["SP", "SP", "SP"],
            "cod_uf": ["35", "35", "35"],
            "renda_responsavel_media_setor_2022": [6000.0, 3000.0, 4500.0],
            "responsaveis_com_renda_setor_2022": [850.0, 280.0, 570.0],
        }
    )


def _m1_reference_fake() -> pd.DataFrame:
    return pd.DataFrame({"renda_per_capita": [800.0, 1200.0, 1600.0, 2200.0, 3200.0]})


def test_monta_base_setorial_geo_com_schema_crs_e_metricas():
    result = montar_base_setorial_uf(
        _malha_fake(),
        _basico_fake(),
        _renda_fake(),
        uf="SP",
        m1_reference=_m1_reference_fake(),
        data_materializacao="2026-05-22",
    )

    assert list(result.columns) == COLUNAS_ARTEFATO
    assert len(result) == 3
    assert set(result["uf"]) == {"SP"}
    assert set(result["cod_municipio"]) == {"3550308"}
    assert result["crs_origem"].eq(CRS_ORIGEM).all()
    assert result["area_setor_m2"].gt(0).all()
    assert result["densidade_pop_setor_hab_km2"].gt(0).all()
    assert result["flag_geometria_valida"].all()
    assert result["flag_renda_disponivel"].all()
    assert result["flag_score_calibrado_disponivel"].all()
    assert result["score_setor_2022_calibrado"].between(0, 100).all()
    assert from_wkb(result.loc[0, "geometry_wkb"]).is_valid
    # BLK-RELMUN-02: nome_bairro flui ao artefato (com NA preservado no setor sem bairro).
    assert "nome_bairro" in result.columns
    assert list(result["nome_bairro"].fillna("<NA>")) == ["Bela Vista", "Centro", "<NA>"]


def test_join_por_chave_ignora_ordem_e_setor_faltante():
    # Regressao do bug do join posicional: renda SEM o setor B e em ordem [C, A]. O join por CHAVE
    # deve dar a CADA setor a sua propria renda (ordem irrelevante) e deixar B com renda ausente —
    # nunca a renda de um vizinho, como fazia o antigo alinhamento por posicao.
    renda_incompleta = pd.DataFrame(
        {
            "cod_setor": ["355030802000001", "355030801000001"],  # [C, A], sem B
            "uf": ["SP", "SP"],
            "cod_uf": ["35", "35"],
            "renda_responsavel_media_setor_2022": [6000.0, 3000.0],
            "responsaveis_com_renda_setor_2022": [850.0, 280.0],
        }
    )
    result = montar_base_setorial_uf(
        _malha_fake(),
        _basico_fake(),
        renda_incompleta,
        uf="SP",
        m1_reference=_m1_reference_fake(),
    ).set_index("cod_setor")

    a, b, c = "355030801000001", "355030801000002", "355030802000001"
    # Basico (embaralhado) casou por chave: cada setor manteve a SUA populacao.
    assert result.loc[a, "pop_total_setor_2022"] == 900.0
    assert result.loc[b, "pop_total_setor_2022"] == 1800.0
    assert result.loc[c, "pop_total_setor_2022"] == 2700.0
    # Renda casou por chave: A e C com a sua renda; renda_pc = renda_resp / avg_moradores (3).
    assert result.loc[a, "renda_responsavel_media_setor_2022"] == 3000.0
    assert result.loc[c, "renda_responsavel_media_setor_2022"] == 6000.0
    assert result.loc[a, "renda_per_capita_setor_2022"] == 1000.0
    assert result.loc[c, "renda_per_capita_setor_2022"] == 2000.0
    # B nao existe na renda -> ausente (nunca a renda de um vizinho deslocada pela posicao).
    assert pd.isna(result.loc[b, "renda_responsavel_media_setor_2022"])
    assert not bool(result.loc[b, "flag_renda_disponivel"])
    assert bool(result.loc[a, "flag_renda_disponivel"])
    assert bool(result.loc[c, "flag_renda_disponivel"])


def test_escreve_e_le_particao_por_uf_municipio(tmp_path: Path):
    df = montar_base_setorial_uf(
        _malha_fake(),
        _basico_fake(),
        _renda_fake(),
        uf="SP",
        m1_reference=_m1_reference_fake(),
    )
    info = escrever_particoes(df, tmp_path)
    loaded = ler_particao_setores(tmp_path, uf="SP", cod_municipio="3550308")

    assert info == {"arquivos": 1, "linhas": 3}
    assert (tmp_path / "uf=SP" / "cod_municipio=3550308" / "part-000.parquet").exists()
    assert len(loaded) == 3
    assert set(COLUNAS_ARTEFATO).issubset(loaded.columns)


def test_relatorio_descreve_artefato_e_guardrail(tmp_path: Path):
    from motor_expansao.pipelines.materializar_setores_censitarios_geo import UFSummary

    report = gerar_relatorio(
        [
            UFSummary(
                uf="SP",
                municipios=1,
                setores=3,
                arquivos=1,
                tamanho_mb=0.01,
                tempo_s=0.2,
                renda_cobertura_pct=100.0,
                score_cobertura_pct=100.0,
            )
        ],
        tmp_path,
        COLUNAS_ARTEFATO,
    )

    assert "Base censitaria geografica otimizada" in report
    assert "geometry_wkb" in report
    assert "nao altera M1 oficial" in report
