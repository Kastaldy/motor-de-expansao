"""Testes unitários para BLK-LTV-02 — join_territorio_retencao.

Usa EXCLUSIVAMENTE fixtures sintéticas via unittest.mock.patch;
nunca lê arquivos reais.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from motor_expansao.lifetime.join_territorio_retencao import (
    BRIDGE_COLUMNS,
    LIFETIME_COLUMNS,
    OUTPUT_COLUMNS,
    TERRITORIAL_COLUMNS,
    build_unidade_territorio_retencao,
)

# ---------------------------------------------------------------------------
# Helpers para fixtures sintéticas
# ---------------------------------------------------------------------------

_LIFETIME_DEFAULTS: dict = {
    "COD_UNIDADE": "01",
    "UNIDADE": "UNIDADE TESTE",
    "UF": "SP",
    "N_ALUNOS": 1000,
    "TICKET_MEDIO_UNIDADE": 99.9,
    "RECEITA_MENSAL_TOTAL": 99900.0,
    "PROB_CANCEL_90D_MEDIA": 0.15,
    "PROB_CANCEL_90D_P50": 0.12,
    "P_CANCEL_12M_MEDIA": 0.40,
    "P_CANCEL_12M_P50": 0.38,
    "E_MESES_ATIVOS_12M_MEDIANO": 8.5,
    "LTV_PROSPECTIVO_12M_MEDIANO": 850.0,
    "LTV_PROSPECTIVO_12M_MEDIO": 900.0,
    "LTV_PROSPECTIVO_12M_TOTAL": 900000.0,
    "PCT_LTV_FRAGIL": 0.10,
    "PCT_LTV_EM_RISCO": 0.20,
    "PCT_LTV_DURAVEL": 0.40,
    "PCT_LTV_ALTA_DURABILIDADE": 0.30,
    "CONFIABILIDADE_UNIDADE": "Absoluto OK",
    "USAR_PROB_ABSOLUTA": "Sim",
    "USAR_RANKING": "Sim",
}

_BRIDGE_DEFAULTS: dict = {
    "cod_unidade": "01",
    "hex_id": "87a8100d8ffffff",
    "metodo_match": "exato",
    "match_score": 1.0,
}

_MERCADO_DEFAULTS: dict = {
    "hex_id": "87a8100d8ffffff",
    "renda_per_capita": 2500.0,
    "score_priorizacao": 75.0,
    "score_expansao_hibrido": 68.0,
    "n_concorrentes_mapeados_1km": 1,
    "n_concorrentes_mapeados_2km": 3,
    "pop_total_setor_2022": 8000.0,
    "densidade_pop_setor_hab_km2": 4000.0,
    "score_setor_2022_calibrado": 72.0,
    "score_oportunidade_residual": 60.0,
    "oferta_efetiva_disponivel": 3500.0,
    "flag_canibalizacao_ultra_1km": False,
}


def _make_bridge(rows: list[dict]) -> pd.DataFrame:
    """Simula unidade_hex.parquet (colunas: BRIDGE_COLUMNS)."""
    records = [{**_BRIDGE_DEFAULTS, **r} for r in rows]
    return pd.DataFrame(records, columns=BRIDGE_COLUMNS)


def _make_lifetime(rows: list[dict]) -> pd.DataFrame:
    """Simula unidade_para_motor.parquet (colunas: LIFETIME_COLUMNS)."""
    records = [{**_LIFETIME_DEFAULTS, **r} for r in rows]
    return pd.DataFrame(records, columns=LIFETIME_COLUMNS)


def _make_mercado(rows: list[dict]) -> pd.DataFrame:
    """Simula hexagonos_mercado_mapeado.parquet (colunas: TERRITORIAL_COLUMNS)."""
    records = [{**_MERCADO_DEFAULTS, **r} for r in rows]
    return pd.DataFrame(records, columns=TERRITORIAL_COLUMNS)


def _run_build(
    bridge_rows: list[dict],
    lifetime_rows: list[dict],
    mercado_rows: list[dict],
) -> pd.DataFrame:
    """Executa build_unidade_territorio_retencao com DataFrames sintéticos injetados."""
    bridge_df = _make_bridge(bridge_rows)
    lifetime_df = _make_lifetime(lifetime_rows)
    mercado_df = _make_mercado(mercado_rows)

    with (
        patch(
            "motor_expansao.lifetime.join_territorio_retencao._load_bridge",
            return_value=bridge_df,
        ),
        patch(
            "motor_expansao.lifetime.join_territorio_retencao._load_lifetime",
            return_value=lifetime_df,
        ),
        patch(
            "motor_expansao.lifetime.join_territorio_retencao._load_mercado",
            return_value=mercado_df,
        ),
    ):
        return build_unidade_territorio_retencao(
            Path("fake/bridge.parquet"),
            Path("fake/lifetime.parquet"),
            Path("fake/mercado.parquet"),
        )


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


class TestBuildUnidadeTerritorio:
    """Testes de build_unidade_territorio_retencao."""

    def test_preserves_all_88_rows(self):
        """LEFT join não perde linhas: N_TOTAL linhas → N_TOTAL no output."""
        n_total = 5
        bridge_rows = [{"cod_unidade": str(i)} for i in range(n_total)]
        lifetime_rows = [{"COD_UNIDADE": str(i)} for i in range(n_total)]
        # Somente 2 unidades com hex_id correspondente no mercado
        mercado_rows = [{"hex_id": _BRIDGE_DEFAULTS["hex_id"]}]

        result = _run_build(bridge_rows, lifetime_rows, mercado_rows)
        assert len(result) == n_total

    def test_left_join_nan_for_unmatched_hex(self):
        """Unidade sem hex_id → features territoriais = NaN."""
        bridge_rows = [
            {"cod_unidade": "01", "hex_id": None, "metodo_match": "sem_match", "match_score": 0.0},
        ]
        lifetime_rows = [{"COD_UNIDADE": "01"}]
        mercado_rows = []  # nenhum hex no mercado

        result = _run_build(bridge_rows, lifetime_rows, mercado_rows)
        row = result.iloc[0]

        # Features territoriais devem ser NaN
        territorial_features = [c for c in TERRITORIAL_COLUMNS if c != "hex_id"]
        for col in territorial_features:
            assert pd.isna(row[col]), f"Esperado NaN em {col} para unidade sem hex_id"

    def test_join_key_case_normalization(self):
        """cod_unidade lowercase "01" casa com COD_UNIDADE uppercase "01"."""
        bridge_rows = [{"cod_unidade": "01"}]      # lowercase
        lifetime_rows = [{"COD_UNIDADE": "01"}]    # maiúsculas / qualquer case → normalizado
        mercado_rows = [{"hex_id": _BRIDGE_DEFAULTS["hex_id"]}]

        result = _run_build(bridge_rows, lifetime_rows, mercado_rows)
        assert len(result) == 1
        assert result.iloc[0]["UNIDADE"] == _LIFETIME_DEFAULTS["UNIDADE"]

    def test_prob_cancel_absoluta_sim(self):
        """USAR_PROB_ABSOLUTA='Sim' → prob_cancel_90d_media_absoluta == PROB_CANCEL_90D_MEDIA."""
        bridge_rows = [{"cod_unidade": "01"}]
        lifetime_rows = [{"COD_UNIDADE": "01", "USAR_PROB_ABSOLUTA": "Sim", "PROB_CANCEL_90D_MEDIA": 0.15}]
        mercado_rows = [{"hex_id": _BRIDGE_DEFAULTS["hex_id"]}]

        result = _run_build(bridge_rows, lifetime_rows, mercado_rows)
        row = result.iloc[0]
        assert row["prob_cancel_90d_media_absoluta"] == pytest.approx(0.15)

    def test_prob_cancel_absoluta_nao(self):
        """USAR_PROB_ABSOLUTA='Nao' → prob_cancel_90d_media_absoluta é NaN."""
        bridge_rows = [{"cod_unidade": "01"}]
        lifetime_rows = [{"COD_UNIDADE": "01", "USAR_PROB_ABSOLUTA": "Nao", "PROB_CANCEL_90D_MEDIA": 0.15}]
        mercado_rows = [{"hex_id": _BRIDGE_DEFAULTS["hex_id"]}]

        result = _run_build(bridge_rows, lifetime_rows, mercado_rows)
        row = result.iloc[0]
        assert pd.isna(row["prob_cancel_90d_media_absoluta"])

    def test_output_columns_present(self):
        """Todas as colunas de OUTPUT_COLUMNS estão no DataFrame de saída."""
        bridge_rows = [{"cod_unidade": "01"}]
        lifetime_rows = [{"COD_UNIDADE": "01"}]
        mercado_rows = [{"hex_id": _BRIDGE_DEFAULTS["hex_id"]}]

        result = _run_build(bridge_rows, lifetime_rows, mercado_rows)
        assert list(result.columns) == OUTPUT_COLUMNS

    def test_no_extra_m1_imports(self):
        """O módulo não importa de pipelines.m1, dashboard, censo_* ou api."""
        import motor_expansao.lifetime.join_territorio_retencao as mod

        src = inspect.getsource(mod)
        # Verificar que não há instruções de import para módulos proibidos
        # (não checar strings literais no docstring, apenas padrões de import)
        banned_imports = [
            "import motor_expansao.pipelines.m1",
            "from motor_expansao.pipelines.m1",
            "from motor_expansao.dashboard",
            "import motor_expansao.dashboard",
            "from motor_expansao.censo",
            "import motor_expansao.censo",
            "from motor_expansao.api",
            "import motor_expansao.api",
        ]
        for banned in banned_imports:
            assert banned not in src, f"Import proibido detectado: {banned}"

    def test_territorial_features_present_when_hex_matched(self):
        """Unidade com hex_id válido → renda_per_capita não é NaN."""
        bridge_rows = [{"cod_unidade": "01", "hex_id": "87a8100d8ffffff"}]
        lifetime_rows = [{"COD_UNIDADE": "01"}]
        mercado_rows = [{"hex_id": "87a8100d8ffffff", "renda_per_capita": 2500.0}]

        result = _run_build(bridge_rows, lifetime_rows, mercado_rows)
        row = result.iloc[0]
        assert not pd.isna(row["renda_per_capita"])
        assert row["renda_per_capita"] == pytest.approx(2500.0)

    def test_runtime_error_on_join_mismatch(self):
        """COD_UNIDADEs disjuntos → RuntimeError (inner merge < N linhas)."""
        bridge_rows = [
            {"cod_unidade": "01"},
            {"cod_unidade": "02"},
        ]
        # Lifetime só tem "01" → inner merge resulta em 1 linha vs 2 esperadas
        lifetime_rows = [{"COD_UNIDADE": "01"}]
        mercado_rows = []

        with pytest.raises(RuntimeError, match="inner merge"):
            _run_build(bridge_rows, lifetime_rows, mercado_rows)

    def test_output_has_36_columns(self):
        """OUTPUT_COLUMNS deve ter exatamente 36 colunas."""
        assert len(OUTPUT_COLUMNS) == 36

    def test_output_columns_count_in_result(self):
        """DataFrame de saída tem exatamente 36 colunas."""
        bridge_rows = [{"cod_unidade": "01"}]
        lifetime_rows = [{"COD_UNIDADE": "01"}]
        mercado_rows = [{"hex_id": _BRIDGE_DEFAULTS["hex_id"]}]

        result = _run_build(bridge_rows, lifetime_rows, mercado_rows)
        assert result.shape[1] == 36
