"""
Teste minimo - Bloco 5: piloto de mercado por hexagono.
"""

from pathlib import Path

import pandas as pd
import pytest

from jobs.pipelines import calcular_colunas_mercado as mercado_module
from jobs.pipelines.calcular_colunas_mercado import HYBRID_TIEBREAK_MAX_SCORE, calcular
from jobs.pipelines.normalizar_unidades_ultra import carregar_ultra

ROOT = Path(__file__).resolve().parents[2]
MERCADO_PATH = ROOT / "data" / "staging" / "hexagonos_mercado_mapeado.parquet"
HIBRIDO_PATH = ROOT / "data" / "outputs" / "oportunidades_expansao_hibrido.parquet"
ULTRA_RAW_PATH = ROOT / "data" / "ultra" / "Ultra.csv"

CSV_REQUIRED_COLS = {"nome_unidade", "latitude", "longitude", "data_coleta"}
CSV_SOURCES = {
    ROOT / "concorrentes" / "unidades_smart_fit.csv": 1000,
    ROOT / "concorrentes" / "unidades_bluefit.csv": 226,
    ROOT / "concorrentes" / "unidades_panobianco.csv": 458,
}

MERCADO_REQUIRED_COLS = {
    "data_snapshot_mercado",
    "fonte_demanda_principal",
    "fonte_oferta_principal",
    "n_redes_mapeadas",
    "demanda_granularidade",
    "tam_populacao_base",
    "tam_renda_base",
    "tam_indice_demanda",
    "tam_indice_demanda_norm",
    "tam_pop_total_base",
    "gap_competitivo_2km",
    "pressao_concorrencial_score_2km",
    "flag_canibalizacao_ultra_1km",
    "flag_sam",
    "sam_indice_operavel",
    "sam_populacao_base",
    "sam_granularidade",
    "residual_indice_mapeado",
    "residual_populacao_mapeada",
    "capacidade_captura_mapeada",
    "som_indice_mapeado",
    "som_populacao_mapeada",
    "tese_entrada",
    "prioridade_mercado_mapeado",
}
MERCADO_GUARDRAIL_COLS = sorted(MERCADO_REQUIRED_COLS)

M1_ARTIFACTS = {
    ROOT / "data" / "staging" / "brasil_estrutural.parquet": {
        "score_priorizacao",
        "hex_score_estrutural",
    },
    ROOT / "data" / "staging" / "brasil_priorizados.parquet": {
        "score_priorizacao",
        "hex_score_estrutural",
    },
    ROOT / "data" / "staging" / "hexagonos_brasil_oportunidades.parquet": {
        "score_priorizacao",
        "score_oficial",
        "score_oficial_nome",
        "hex_score_estrutural",
        "osm_status",
    },
    ROOT / "data" / "outputs" / "hexagonos_brasil_dashboard.parquet": {
        "score_priorizacao",
        "score_oficial",
        "score_oficial_nome",
        "hex_score_estrutural",
        "osm_status",
    },
    ROOT / "data" / "outputs" / "hexagonos_mapa_sample.parquet": {
        "score_priorizacao",
        "score_oficial",
        "score_oficial_nome",
        "hex_score_estrutural",
        "osm_status",
    },
}


@pytest.fixture(scope="module")
def mercado_guardrails_df():
    assert MERCADO_PATH.exists(), f"Parquet nao encontrado: {MERCADO_PATH}"
    return pd.read_parquet(MERCADO_PATH, columns=MERCADO_GUARDRAIL_COLS)


@pytest.fixture(scope="module")
def mercado_score_df():
    assert MERCADO_PATH.exists(), f"Parquet nao encontrado: {MERCADO_PATH}"
    return pd.read_parquet(MERCADO_PATH, columns=["hex_id", "score_priorizacao", "score_oficial"])


@pytest.fixture(scope="module")
def hibrido_score_df():
    assert HIBRIDO_PATH.exists(), f"Parquet nao encontrado: {HIBRIDO_PATH}"
    return pd.read_parquet(HIBRIDO_PATH, columns=["hex_id", "score_priorizacao"])


@pytest.mark.parametrize(("csv_path", "expected_rows"), CSV_SOURCES.items())
def test_csvs_concorrentes_legiveis(csv_path: Path, expected_rows: int):
    assert csv_path.exists(), f"CSV nao encontrado: {csv_path}"
    df = pd.read_csv(csv_path, sep=";", dtype=str)
    assert CSV_REQUIRED_COLS <= set(df.columns)
    assert len(df) == expected_rows


def test_ultra_loader_lida_com_metadado_e_encoding_legacy():
    assert ULTRA_RAW_PATH.exists(), f"CSV nao encontrado: {ULTRA_RAW_PATH}"
    df = carregar_ultra(ULTRA_RAW_PATH)

    assert len(df) == 150
    assert {"unidade", "uf", "cidade", "lat_raw", "lng_raw", "lat", "lng"} <= set(df.columns)
    assert df["lat"].notna().all()
    assert df["lng"].notna().all()

    al_rows = df[df["unidade"].str.contains(r"/\s*AL\s*$", regex=True, na=False)]
    assert not al_rows.empty, "Linha AL nao encontrada no CSV bruto"
    assert set(al_rows["uf"].unique()) == {"AL"}


def test_calcular_bloqueia_sam_quando_ha_canibalizacao():
    df = pd.DataFrame(
        {
            "hex_id": ["h1", "h2"],
            "flag_censo_elegivel": [True, False],
            "pop_total_setor_2022": [1000.0, None],
            "renda_per_capita_setor_2022_calibrada": [2500.0, None],
            "populacao_proxy": [900.0, 800.0],
            "renda_per_capita": [2000.0, 1800.0],
            "score_priorizacao": [80.0, 70.0],
            "flag_hex_hibrido_elegivel": [True, False],
            "score_expansao_hibrido": [99.5, None],
            "flag_viavel": [True, True],
            "top_municipio": [True, True],
            "flag_white_space_2km": [True, False],
            "flag_canibalizacao_ultra_1km": [True, False],
            "gap_competitivo_2km": [1.0, 0.5],
            "pressao_concorrencial_score_2km": [0.0, 50.0],
        }
    )

    result = calcular(df.copy())

    bloqueado = result.loc[result["hex_id"] == "h1"].iloc[0]
    assert bool(bloqueado["flag_sam"]) is False
    assert bloqueado["sam_indice_operavel"] == pytest.approx(0.0)
    assert bloqueado["sam_populacao_base"] == pytest.approx(0.0)
    assert bloqueado["tese_entrada"] == "proteger_rede_atual"
    assert bloqueado["prioridade_mercado_mapeado"] == "nula"

    operavel = result.loc[result["hex_id"] == "h2"].iloc[0]
    assert bool(operavel["flag_sam"]) is True
    assert operavel["sam_granularidade"] == "municipio_priorizado"
    assert operavel["sam_indice_operavel"] == pytest.approx(70.0)
    assert operavel["tese_entrada"] == "abrir_com_disputa"


def test_anexar_colunas_censo_preserva_camada_censitaria_do_hibrido(tmp_path, monkeypatch):
    censo_path = tmp_path / "censo_core.parquet"
    pd.DataFrame(
        {
            "hex_id": ["h1", "h2"],
            "pop_total_setor_2022": [100.0, 200.0],
            "renda_per_capita_setor_2022_calibrada": [1000.0, 2000.0],
        }
    ).to_parquet(censo_path, index=False)
    monkeypatch.setattr(mercado_module, "CENSO_PATH", censo_path)

    base = pd.DataFrame(
        {
            "hex_id": ["h1", "h2", "h3"],
            "pop_total_setor_2022": [1000.0, None, 3000.0],
            "renda_per_capita_setor_2022_calibrada": [1100.0, None, 3300.0],
        }
    )

    result = mercado_module.anexar_colunas_censo(base)

    assert result.loc[result["hex_id"] == "h1", "pop_total_setor_2022"].iloc[0] == pytest.approx(1000.0)
    assert result.loc[result["hex_id"] == "h2", "pop_total_setor_2022"].iloc[0] == pytest.approx(200.0)
    assert result.loc[result["hex_id"] == "h3", "pop_total_setor_2022"].iloc[0] == pytest.approx(3000.0)


def test_parquet_final_tem_schema_minimo(mercado_guardrails_df: pd.DataFrame):
    assert MERCADO_REQUIRED_COLS <= set(mercado_guardrails_df.columns)


def test_parquet_final_respeita_guardrails_do_piloto(mercado_guardrails_df: pd.DataFrame):
    assert int(
        (mercado_guardrails_df["flag_sam"] & mercado_guardrails_df["flag_canibalizacao_ultra_1km"]).sum()
    ) == 0
    assert set(mercado_guardrails_df["fonte_oferta_principal"].dropna().unique()) == {
        "csv_big_players_mapeados"
    }
    assert set(mercado_guardrails_df["n_redes_mapeadas"].dropna().unique()) == {3}
    assert set(mercado_guardrails_df["demanda_granularidade"].dropna().unique()) <= {
        "hex_censo",
        "municipio_proxy",
    }
    assert set(mercado_guardrails_df["sam_granularidade"].dropna().unique()) <= {
        "hex_censo",
        "municipio_priorizado",
        "bloqueado_rede_ultra",
        "fora_escopo_atual",
    }
    assert mercado_guardrails_df["tam_indice_demanda"].between(
        0, HYBRID_TIEBREAK_MAX_SCORE
    ).all()
    assert mercado_guardrails_df["som_indice_mapeado"].between(
        0, HYBRID_TIEBREAK_MAX_SCORE
    ).all()


def test_piloto_preserva_score_oficial_do_mercado_e_cobertura_hibrida(
    mercado_score_df: pd.DataFrame,
    hibrido_score_df: pd.DataFrame,
):
    joined = mercado_score_df.merge(
        hibrido_score_df,
        on="hex_id",
        how="inner",
        suffixes=("_mercado", "_hibrido"),
    )

    assert len(joined) == len(hibrido_score_df) == len(mercado_score_df)
    assert (mercado_score_df["score_oficial"] == mercado_score_df["score_priorizacao"]).all()
    assert joined["score_priorizacao_mercado"].between(0, 100).all()
    assert joined["score_priorizacao_hibrido"].between(0, 100).all()


@pytest.mark.parametrize(("artifact_path", "required_cols"), M1_ARTIFACTS.items())
def test_artefatos_oficiais_m1_mantem_invariantes(
    artifact_path: Path,
    required_cols: set[str],
):
    assert artifact_path.exists(), f"Artefato oficial ausente: {artifact_path}"
    df = pd.read_parquet(artifact_path, columns=sorted(required_cols))
    assert required_cols <= set(df.columns)

    if {"score_oficial", "score_priorizacao"} <= required_cols:
        assert (df["score_oficial"] == df["score_priorizacao"]).all()
    if "score_oficial_nome" in required_cols:
        assert set(df["score_oficial_nome"].dropna().unique()) == {"score_priorizacao"}
    if "osm_status" in required_cols:
        assert set(df["osm_status"].dropna().unique()) == {"nao_aplicado_mvp_nacional"}
