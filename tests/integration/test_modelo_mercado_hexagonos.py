"""
Teste minimo - Bloco 5: piloto de mercado por hexagono.
"""

from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.pipelines import calcular_colunas_mercado as mercado_module
from motor_expansao.pipelines.calcular_colunas_mercado import (
    CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS,
    HYBRID_TIEBREAK_MAX_SCORE,
    TAXA_FITNESS_CALIBRADA,
    anexar_oferta_ultra_real,
    calcular,
)
from motor_expansao.pipelines.normalizar_unidades_ultra import carregar_ultra

ROOT = Path(__file__).resolve().parents[2]
MERCADO_PATH = ROOT / "data" / "staging" / "hexagonos_mercado_mapeado.parquet"
HIBRIDO_PATH = ROOT / "data" / "outputs" / "oportunidades_expansao_hibrido.parquet"
ULTRA_RAW_PATH = ROOT / "data" / "ultra" / "Ultra.csv"

CSV_REQUIRED_COLS = {"nome_unidade", "latitude", "longitude", "data_coleta"}
# Pisos de sanidade por CSV (não contagens exatas): dado real gitignored é frágil a regenerações
# legítimas do pipeline de mapeamento; piso conservador detecta CSV vazio/truncado sem rebote a
# cada refresh de dados sem ser uma regressão de código.
CSV_SOURCES = {
    ROOT / "concorrentes" / "unidades_smart_fit.csv": 100,
    ROOT / "concorrentes" / "unidades_bluefit.csv": 100,
    ROOT / "concorrentes" / "unidades_panobianco.csv": 100,
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
    "pop_hex_base",
    "fonte_pop_hex_base",
    "tam_populacao_hex",
    "taxa_fitness_calibrada",
    "taxa_fitness_mercado_calibrada",
    "tam_fitness_potencial",
    "gap_competitivo_2km",
    "pressao_concorrencial_score_2km",
    "flag_canibalizacao_ultra_1km",
    "populacao_corte_hex",
    "fonte_populacao_corte",
    "flag_pop_min_5k",
    "flag_sam",
    "flag_sam_fitness",
    "sam_indice_operavel",
    "sam_populacao_base",
    "sam_fitness_potencial",
    "sam_granularidade",
    "residual_indice_mapeado",
    "residual_populacao_mapeada",
    "capacidade_captura_mapeada",
    "som_indice_mapeado",
    "som_populacao_mapeada",
    "capacidade_default_concorrente_alunos",
    "oferta_consumida_mercado_estimada",
    "oferta_consumida_ultra_real",
    "oferta_consumida_ultra_estimada",
    "oferta_consumida_total_estimada",
    "oferta_efetiva_disponivel",
    "penetracao_fitness_mercado_estimada",
    "share_ultra_estimado_hex",
    "score_oportunidade_residual",
    "tese_entrada",
    "prioridade_mercado_mapeado",
}
MERCADO_GUARDRAIL_COLS = sorted(MERCADO_REQUIRED_COLS)

# Colunas materializadas a partir do BLK-SAM-01 (DEC-006). O parquet real so as contem
# apos a regeneracao operacional pos-merge (passo separado do fechamento de testes); ate la,
# o guardrail de schema sobre o parquet existente as trata como pendencia conhecida.
MERCADO_COLS_PENDENTES_REGEN = {
    "populacao_corte_hex",
    "fonte_populacao_corte",
    "flag_pop_min_5k",
}

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
    if not MERCADO_PATH.exists():
        pytest.skip(f"Parquet de mercado real ausente: {MERCADO_PATH}")
    import pyarrow.parquet as pq

    available = set(pq.read_schema(MERCADO_PATH).names)
    cols = [c for c in MERCADO_GUARDRAIL_COLS if c in available]
    return pd.read_parquet(MERCADO_PATH, columns=cols)


@pytest.fixture(scope="module")
def mercado_score_df():
    if not MERCADO_PATH.exists():
        pytest.skip(f"Parquet de mercado real ausente: {MERCADO_PATH}")
    return pd.read_parquet(MERCADO_PATH, columns=["hex_id", "score_priorizacao", "score_oficial"])


@pytest.fixture(scope="module")
def hibrido_score_df():
    if not HIBRIDO_PATH.exists():
        pytest.skip(f"Parquet hibrido real ausente: {HIBRIDO_PATH}")
    return pd.read_parquet(HIBRIDO_PATH, columns=["hex_id", "score_priorizacao"])


@pytest.mark.parametrize(("csv_path", "min_rows"), CSV_SOURCES.items())
def test_csvs_concorrentes_legiveis(csv_path: Path, min_rows: int):
    if not csv_path.exists():
        pytest.skip(f"CSV concorrente real ausente: {csv_path}")
    df = pd.read_csv(csv_path, sep=";", dtype=str)
    assert CSV_REQUIRED_COLS <= set(df.columns)
    # Piso de sanidade: detecta CSV vazio/truncado sem rebote a cada refresh legítimo de dados.
    assert len(df) >= min_rows, f"{csv_path.name}: esperado >= {min_rows} linhas, encontrado {len(df)}"


def test_ultra_loader_lida_com_metadado_e_encoding_legacy():
    if not ULTRA_RAW_PATH.exists():
        pytest.skip(f"data/ultra/Ultra.csv ausente: {ULTRA_RAW_PATH}")
    df = carregar_ultra(ULTRA_RAW_PATH)

    assert len(df) == 150
    assert {"unidade", "uf", "cidade", "lat_raw", "lng_raw", "lat", "lng"} <= set(df.columns)
    assert df["lat"].notna().all()
    assert df["lng"].notna().all()

    al_rows = df[df["unidade"].str.contains(r"/\s*AL\s*$", regex=True, na=False)]
    assert not al_rows.empty, "Linha AL nao encontrada no CSV bruto"
    assert set(al_rows["uf"].unique()) == {"AL"}


def test_canibalizacao_nao_bloqueia_mais_o_sam():
    """DEC-007: canibalizacao deixou de bloquear o SAM. h1 (canibal=True, faixa
    prioridade_maxima, pop_corte=10000) agora entra no SAM. Labels de protecao/
    granularidade permanecem coerentes (tese=proteger_rede_atual; granularidade
    =hex_censo pela precedencia hibrida)."""
    df = pd.DataFrame(
        {
            "hex_id": ["h1", "h2"],
            "flag_censo_elegivel": [True, False],
            "pop_total_setor_2022": [1000.0, None],
            "renda_per_capita_setor_2022_calibrada": [2500.0, None],
            "populacao_proxy": [900.0, 800.0],
            "pop_total": [10_000.0, 10_000.0],
            "faixa_oportunidade": ["prioridade_maxima", "alta"],
            "renda_per_capita": [2000.0, 1800.0],
            "score_priorizacao": [80.0, 70.0],
            "flag_hex_hibrido_elegivel": [True, False],
            "score_expansao_hibrido": [99.5, None],
            "flag_viavel": [True, True],
            "top_municipio": [True, True],
            "flag_white_space_2km": [True, False],
            "flag_canibalizacao_ultra_1km": [True, False],
            "n_concorrentes_mapeados_2km": [0, 1],
            "oferta_efetiva_mapeada_2km": [0.0, 0.5],
            "gap_competitivo_2km": [1.0, 0.5],
            "pressao_concorrencial_score_2km": [0.0, 50.0],
        }
    )

    result = calcular(df.copy())

    canibal = result.loc[result["hex_id"] == "h1"].iloc[0]
    # Antes da DEC-007 este hex era bloqueado por ~canibal; agora entra no SAM.
    assert bool(canibal["flag_sam"]) is True
    # tam_indice_demanda = score_expansao_hibrido (mask_hibrido=True, 99.5 notna).
    assert canibal["sam_indice_operavel"] == pytest.approx(99.5)
    assert bool(canibal["flag_sam_fitness"]) is True
    assert canibal["sam_fitness_potencial"] > 0
    # flag_canibal continua sendo o 1o criterio de tese_entrada.
    assert canibal["tese_entrada"] == "proteger_rede_atual"
    # flag_hex_hibrido_elegivel tem precedencia em sam_granularidade (np.select).
    assert canibal["sam_granularidade"] == "hex_censo"

    operavel = result.loc[result["hex_id"] == "h2"].iloc[0]
    assert bool(operavel["flag_sam"]) is True
    assert operavel["sam_granularidade"] == "municipio_priorizado"
    assert operavel["sam_indice_operavel"] == pytest.approx(70.0)
    assert operavel["tam_fitness_potencial"] == pytest.approx(800.0 * TAXA_FITNESS_CALIBRADA)
    assert operavel["oferta_consumida_mercado_estimada"] == pytest.approx(
        0.5 * CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS
    )
    assert operavel["tese_entrada"] == "abrir_com_disputa"


def test_calcular_tam_sam_residual_absoluto_exemplo_manual():
    df = pd.DataFrame(
        {
            "hex_id": ["h10k"],
            "flag_censo_elegivel": [True],
            "pop_total_setor_2022": [10_000.0],
            "renda_per_capita_setor_2022_calibrada": [2_500.0],
            "populacao_proxy": [99_999.0],
            "pop_total": [120_000.0],
            "faixa_oportunidade": ["prioridade_maxima"],
            "qualidade_join_uf": ["A"],
            "flag_censo_disponivel": [True],
            "renda_per_capita": [2_000.0],
            "score_priorizacao": [80.0],
            "flag_hex_hibrido_elegivel": [True],
            "score_expansao_hibrido": [90.0],
            "flag_viavel": [True],
            "top_municipio": [True],
            "flag_white_space_2km": [False],
            "flag_canibalizacao_ultra_1km": [False],
            "n_concorrentes_mapeados_2km": [1],
            "oferta_efetiva_mapeada_2km": [0.1],
            "gap_competitivo_2km": [1.0 / 1.1],
            "pressao_concorrencial_score_2km": [100.0 * (1.0 - 1.0 / 1.1)],
        }
    )

    result = calcular(df).iloc[0]

    potencial = 10_000.0 * TAXA_FITNESS_CALIBRADA
    consumo = 0.1 * CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS
    residual = potencial - consumo

    assert result["pop_hex_base"] == pytest.approx(10_000.0)
    assert result["tam_populacao_hex"] == pytest.approx(10_000.0)
    assert result["tam_fitness_potencial"] == pytest.approx(potencial)
    assert result["sam_fitness_potencial"] == pytest.approx(potencial)
    assert result["oferta_consumida_mercado_estimada"] == pytest.approx(consumo)
    assert result["oferta_efetiva_disponivel"] == pytest.approx(residual)
    assert result["score_oportunidade_residual"] == pytest.approx(
        100.0 * residual / CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS
    )


def test_anexar_oferta_ultra_real_soma_alunos_por_hex(tmp_path):
    perf_path = tmp_path / "unidades_ultra_performance_hex.parquet"
    pd.DataFrame(
        {
            "hex_id_res7": ["h1", "h1", "h3", None],
            "alunos_total": [1000, 500, 300, 999],
        }
    ).to_parquet(perf_path, index=False)

    base = pd.DataFrame({"hex_id": ["h1", "h2"]})
    result = anexar_oferta_ultra_real(base, perf_path)

    assert result.loc[result["hex_id"].eq("h1"), "oferta_consumida_ultra_real"].iat[0] == pytest.approx(1500.0)
    assert result.loc[result["hex_id"].eq("h1"), "n_unidades_ultra_performance_hex"].iat[0] == 2
    assert result.loc[result["hex_id"].eq("h2"), "oferta_consumida_ultra_real"].iat[0] == pytest.approx(0.0)


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


def test_bloco8_pop_hex_base_usa_censo_independente_de_flag_censo_elegivel():
    """Bloco 8: pop_total_setor_2022 > 0 define pop_hex_base mesmo quando flag_censo_elegivel=False."""
    base = {
        "flag_censo_elegivel": [False, False, True, False],
        "pop_total_setor_2022": [5000.0, None, 8000.0, None],
        "renda_per_capita_setor_2022_calibrada": [2000.0, None, 3000.0, None],
        "populacao_proxy": [200_000.0, 150_000.0, 99_000.0, 0.0],
        "pop_total": [200_000.0, 150_000.0, 99_000.0, 0.0],
        "faixa_oportunidade": ["alta", "alta", "alta", "alta"],
        "renda_per_capita": [1800.0, 1600.0, 2800.0, 1200.0],
        "score_priorizacao": [75.0, 70.0, 80.0, 60.0],
        "flag_hex_hibrido_elegivel": [False, False, False, False],
        "score_expansao_hibrido": [None, None, None, None],
        "flag_viavel": [True, True, True, True],
        "top_municipio": [True, True, True, True],
        "flag_white_space_2km": [True, True, True, True],
        "flag_canibalizacao_ultra_1km": [False, False, False, False],
        "n_concorrentes_mapeados_2km": [0, 0, 0, 0],
        "oferta_efetiva_mapeada_2km": [0.0, 0.0, 0.0, 0.0],
        "gap_competitivo_2km": [1.0, 1.0, 1.0, 1.0],
        "pressao_concorrencial_score_2km": [0.0, 0.0, 0.0, 0.0],
        "total_hex_municipio": [50, 50, 40, 30],
        "hex_id": ["h_a", "h_b", "h_c", "h_d"],
    }
    df = pd.DataFrame(base)
    result = calcular(df.copy())

    row_a = result.loc[result["hex_id"] == "h_a"].iloc[0]
    assert row_a["pop_hex_base"] == pytest.approx(5000.0), "h_a deve usar censo (pop_total_setor_2022)"
    assert row_a["fonte_pop_hex_base"] == "censo_2022_setor"
    assert row_a["tam_fitness_potencial"] == pytest.approx(5000.0 * TAXA_FITNESS_CALIBRADA)

    row_b = result.loc[result["hex_id"] == "h_b"].iloc[0]
    assert row_b["pop_hex_base"] == pytest.approx(150_000.0 / 50), "h_b deve usar proxy/total_hex_municipio"
    assert row_b["fonte_pop_hex_base"] == "m1_municipal_proxy_per_hex"
    assert row_b["tam_fitness_potencial"] == pytest.approx((150_000.0 / 50) * TAXA_FITNESS_CALIBRADA)

    row_c = result.loc[result["hex_id"] == "h_c"].iloc[0]
    assert row_c["pop_hex_base"] == pytest.approx(8000.0), "h_c usa censo (flag_censo_elegivel=True e pop > 0)"
    assert row_c["fonte_pop_hex_base"] == "censo_2022_setor"

    row_d = result.loc[result["hex_id"] == "h_d"].iloc[0]
    assert row_d["fonte_pop_hex_base"] == "sem_populacao_valida", "h_d: sem censo, proxy=0 → sem_populacao_valida"


def _gate_fixture_row(**overrides) -> pd.DataFrame:
    """Constroi 1 hex com defaults seguros para exercitar o gate do SAM (DEC-006)."""
    base = {
        "hex_id": ["hx"],
        "flag_censo_elegivel": [False],
        "pop_total_setor_2022": [None],
        "renda_per_capita_setor_2022_calibrada": [None],
        "populacao_proxy": [8_000.0],
        "pop_total": [8_000.0],
        "faixa_oportunidade": ["alta"],
        "renda_per_capita": [2_000.0],
        "score_priorizacao": [70.0],
        "flag_hex_hibrido_elegivel": [False],
        "score_expansao_hibrido": [None],
        "flag_viavel": [True],
        "top_municipio": [False],
        "flag_white_space_2km": [False],
        "flag_canibalizacao_ultra_1km": [False],
        "n_concorrentes_mapeados_2km": [0],
        "oferta_efetiva_mapeada_2km": [0.0],
        "gap_competitivo_2km": [1.0],
        "pressao_concorrencial_score_2km": [0.0],
    }
    base.update({k: [v] for k, v in overrides.items()})
    return pd.DataFrame(base)


def test_sam_zera_quando_pop_corte_granular_abaixo_de_5000():
    """DEC-006 repro 87a91b18dffffff: hex granular com setor 2022 < 5000 zera o SAM,
    mesmo com pop_total municipal alto (corte usa SETOR 2022 quando granular)."""
    df = _gate_fixture_row(
        flag_censo_elegivel=False,
        pop_total_setor_2022=35.4,
        pop_total=27_272.0,
        populacao_proxy=27_272.0,
        faixa_oportunidade="prioridade_maxima",
        flag_viavel=True,
        flag_canibalizacao_ultra_1km=False,
        qualidade_join_uf="A",
        flag_censo_disponivel=True,
        score_setor_2022_calibrado=42.0,
    )

    result = calcular(df).iloc[0]

    assert result["confianca_geografica"] == "granular"
    assert result["populacao_corte_hex"] == pytest.approx(35.4)
    assert result["fonte_populacao_corte"] == "setor_2022"
    assert bool(result["flag_pop_min_5k"]) is False
    assert bool(result["flag_sam"]) is False
    assert result["sam_fitness_potencial"] == pytest.approx(0.0)


def test_sam_calcula_para_faixa_elegivel_pop_corte_acima_5000_fora_top_municipio():
    """DEC-006: hex fora do top_municipio antigo (=False) passa a calcular SAM quando
    faixa M1 elegivel e populacao_corte_hex >= 5000 (expansao controlada alem do top-20%)."""
    df = _gate_fixture_row(
        top_municipio=False,
        faixa_oportunidade="alta",
        flag_viavel=True,
        flag_canibalizacao_ultra_1km=False,
        pop_total=8_000.0,
        populacao_proxy=8_000.0,
    )

    result = calcular(df).iloc[0]

    assert result["confianca_geografica"] == "municipal"
    assert result["fonte_populacao_corte"] == "total_municipal"
    assert result["populacao_corte_hex"] == pytest.approx(8_000.0)
    assert bool(result["flag_pop_min_5k"]) is True
    assert bool(result["flag_sam"]) is True
    assert result["sam_fitness_potencial"] > 0


@pytest.mark.parametrize(
    ("overrides", "esperado_sam"),
    [
        ({}, True),  # tudo ok
        ({"faixa_oportunidade": "descartado"}, False),  # faixa nao elegivel
        ({"pop_total": 4_999.0, "populacao_proxy": 4_999.0}, False),  # pop_corte < 5000
        ({"flag_canibalizacao_ultra_1km": True}, True),  # canibal NAO bloqueia mais (DEC-007)
        ({"flag_viavel": False}, True),  # nao-viavel M1 NAO bloqueia mais (DEC-007)
    ],
)
def test_flag_sam_e_conjuncao_dos_dois_criterios(overrides, esperado_sam):
    """DEC-007: flag_sam e a conjuncao de faixa M1 elegivel & flag_pop_min_5k(>=5000).
    flag_viavel e ~canibalizacao SAIRAM do gate; falhar em faixa ou pop zera o SAM."""
    df = _gate_fixture_row(**overrides)
    result = calcular(df).iloc[0]
    assert bool(result["flag_sam"]) is esperado_sam


def test_dropar_flag_viavel_admite_hex_no_sam():
    """DEC-007 repro flag_viavel: antes do BLK-SAM-02 (gate DEC-006) este hex reprovava
    SO por flag_viavel=False; com a DEC-007 ele entra no SAM (faixa alta + pop_corte>=5000)."""
    df = _gate_fixture_row(
        flag_viavel=False,
        faixa_oportunidade="alta",
        flag_canibalizacao_ultra_1km=False,
        pop_total=8_000.0,
        populacao_proxy=8_000.0,
        renda_per_capita=100.0,  # renda < RENDA_MIN reprovaria flag_viavel no M1
    )

    result = calcular(df).iloc[0]

    assert bool(result["flag_sam"]) is True
    assert result["sam_fitness_potencial"] > 0


def test_dropar_canibal_admite_hex_no_sam():
    """DEC-007 repro ~canibal: antes reprovava SO por ~canibal; a DEC-007 inclui areas
    Ultra<1km no SAM. Labels coerentes: tese=proteger_rede_atual (canibal 1o criterio),
    sam_granularidade=municipio_priorizado (flag_sam vence flag_canibal na precedencia)."""
    df = _gate_fixture_row(
        flag_canibalizacao_ultra_1km=True,
        flag_viavel=True,
        faixa_oportunidade="alta",
        pop_total=8_000.0,
        populacao_proxy=8_000.0,
    )

    result = calcular(df).iloc[0]

    assert bool(result["flag_sam"]) is True
    assert result["sam_fitness_potencial"] > 0
    assert result["tese_entrada"] == "proteger_rede_atual"
    assert result["sam_granularidade"] == "municipio_priorizado"


def test_parquet_final_tem_schema_minimo(mercado_guardrails_df: pd.DataFrame):
    # As colunas estaveis (pre-BLK-SAM-01) devem existir no parquet real.
    cols = set(mercado_guardrails_df.columns)
    assert (MERCADO_REQUIRED_COLS - MERCADO_COLS_PENDENTES_REGEN) <= cols
    # As 3 colunas de corte (DEC-006) so aparecem apos a regeneracao operacional pos-merge.
    if not MERCADO_COLS_PENDENTES_REGEN <= cols:
        pytest.skip(
            "parquet de mercado ainda nao regenerado pos-BLK-SAM-01 "
            "(populacao_corte_hex/fonte_populacao_corte/flag_pop_min_5k pendentes)"
        )


def test_parquet_final_respeita_guardrails_do_piloto(mercado_guardrails_df: pd.DataFrame):
    # DEC-007: o invariante (flag_sam & canibalizacao)==0 deixou de valer (SAM agora
    # coexiste com canibalizacao). Demais guardrails do piloto permanecem.
    assert set(mercado_guardrails_df["fonte_oferta_principal"].dropna().unique()) == {
        "csv_big_players_mapeados"
    }
    assert (mercado_guardrails_df["n_redes_mapeadas"].dropna() >= 3).all()
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
    if not artifact_path.exists():
        pytest.skip(f"artefato M1 real ausente: {artifact_path}")
    df = pd.read_parquet(artifact_path, columns=sorted(required_cols))
    assert required_cols <= set(df.columns)

    if {"score_oficial", "score_priorizacao"} <= required_cols:
        assert (df["score_oficial"] == df["score_priorizacao"]).all()
    if "score_oficial_nome" in required_cols:
        assert set(df["score_oficial_nome"].dropna().unique()) == {"score_priorizacao"}
    if "osm_status" in required_cols:
        assert set(df["osm_status"].dropna().unique()) == {"nao_aplicado_mvp_nacional"}
