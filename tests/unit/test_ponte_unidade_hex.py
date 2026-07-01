"""Testes unitários para BLK-LTV-01 — ponte_unidade_hex.

Usa EXCLUSIVAMENTE fixtures sintéticas; nunca lê arquivos reais.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from motor_expansao.lifetime.ponte_unidade_hex import (
    FUZZY_THRESHOLD,
    H3_RESOLUTION,
    OUTPUT_COLUMNS,
    _derive_hex,
    _fuzzy_score,
    build_bridge,
    normalize_name,
    quality_report,
)

# ---------------------------------------------------------------------------
# Helpers para fixtures sintéticas
# ---------------------------------------------------------------------------

def _make_lifetime(rows: list[dict]) -> pd.DataFrame:
    """Cria DataFrame sintético no formato de unidade_para_motor.parquet."""
    defaults = {"COD_UNIDADE": "99", "UNIDADE": None, "UF": None}
    records = [{**defaults, **r} for r in rows]
    return pd.DataFrame(records)


def _make_ultra_csv(rows: list[dict]) -> pd.DataFrame:
    """Cria DataFrame sintético no formato de Ultra.csv (com Latitude/Longitude já float)."""
    defaults = {"UNIDADE": "", "ESTADO": "", "CIDADE": "", "Latitude": -15.0, "Longitude": -47.0}
    records = [{**defaults, **r} for r in rows]
    if records:
        df = pd.DataFrame(records)
    else:
        df = pd.DataFrame(columns=list(defaults.keys()))
    # _load_ultra_csv converte vírgula → float mas nos testes passamos float direto
    # Simular o comportamento adicionando _norm
    from motor_expansao.lifetime.ponte_unidade_hex import normalize_name
    df["_norm"] = df["UNIDADE"].apply(normalize_name)
    return df


def _make_perf(rows: list[dict]) -> pd.DataFrame:
    """Cria DataFrame sintético no formato de unidades_ultra_performance_hex.parquet."""
    defaults = {"unidade": "", "uf": "", "cidade": "", "lat": -15.0, "lng": -47.0, "hex_id": None}
    records = [{**defaults, **r} for r in rows]
    if records:
        df = pd.DataFrame(records)
    else:
        # DataFrame vazio mas com as colunas esperadas
        df = pd.DataFrame(columns=list(defaults.keys()))
    from motor_expansao.lifetime.ponte_unidade_hex import normalize_name
    df["_norm"] = df["unidade"].apply(normalize_name)
    return df


# ---------------------------------------------------------------------------
# Testes de normalize_name
# ---------------------------------------------------------------------------

class TestNormalizeName:
    def test_lower_and_strip(self):
        assert normalize_name("  ASA NORTE  ") == "asa norte"

    def test_remove_accents(self):
        assert normalize_name("JOÃO") == "joao"
        assert normalize_name("Brasilândia") == "brasilandia"
        assert normalize_name("Ceilandía") == "ceilandia"

    def test_remove_state_suffix_slash(self):
        assert normalize_name("ASA NORTE / DF") == "asa norte"
        assert normalize_name("Taubate / SP") == "taubate"

    def test_remove_state_suffix_dash(self):
        assert normalize_name("SORRISO - MT") == "sorriso"
        assert normalize_name("CAMPO LARGO - PR") == "campo largo"

    def test_remove_generic_tokens(self):
        # "ultra" é token genérico, "fitness" não está na lista — permanece
        assert normalize_name("Ultra Academia") == ""  # ambos genéricos → vazio
        assert normalize_name("Academia Centro") == "centro"  # 'academia' removido
        assert normalize_name("Ultra Fit Unidade") == ""  # ultra+fit+unidade removidos

    def test_collapse_whitespace(self):
        assert normalize_name("JARDIM   BOTANICO") == "jardim botanico"

    def test_none_returns_empty(self):
        assert normalize_name(None) == ""

    def test_nan_returns_empty(self):
        import pandas as pd
        assert normalize_name(pd.NA) == ""  # type: ignore[arg-type]

    def test_preserves_non_generic_words(self):
        assert normalize_name("JARDIM BOTANICO") == "jardim botanico"
        assert normalize_name("VILA MARIANA / SP") == "vila mariana"


# ---------------------------------------------------------------------------
# Testes de _fuzzy_score
# ---------------------------------------------------------------------------

class TestFuzzyScore:
    def test_identical_strings(self):
        assert _fuzzy_score("asa norte", "asa norte") == pytest.approx(1.0)

    def test_completely_different(self):
        assert _fuzzy_score("asa norte", "xyz") < 0.5

    def test_close_strings(self):
        score = _fuzzy_score("jardim botanico", "jardim botanico ii")
        assert score > 0.85

    def test_partial_overlap(self):
        score = _fuzzy_score("botafogo", "botafogo rj")
        assert score > 0.80


# ---------------------------------------------------------------------------
# Testes de _derive_hex
# ---------------------------------------------------------------------------

class TestDeriveHex:
    def test_valid_coords(self):
        # Brasília (lat aprox. -15.77, lng aprox. -47.89)
        hex_id = _derive_hex(-15.769997, -47.891550)
        assert hex_id is not None
        assert len(hex_id) == 15  # H3 res-7 cell tem 15 caracteres

    def test_none_lat(self):
        assert _derive_hex(None, -47.0) is None  # type: ignore[arg-type]

    def test_none_lng(self):
        assert _derive_hex(-15.0, None) is None  # type: ignore[arg-type]

    def test_resolution_7(self):
        import h3
        hex_id = _derive_hex(-15.769997, -47.891550)
        assert hex_id is not None
        assert h3.get_resolution(hex_id) == H3_RESOLUTION


# ---------------------------------------------------------------------------
# Testes de build_bridge com mocks
# ---------------------------------------------------------------------------

class TestBuildBridge:
    """Testa o pipeline de match sem tocar arquivos reais."""

    def _run(
        self,
        lifetime_rows: list[dict],
        ultra_rows: list[dict],
        perf_rows: list[dict],
        fuzzy_threshold: float = FUZZY_THRESHOLD,
    ) -> pd.DataFrame:
        """Executa build_bridge com DataFrames sintéticos injetados via mock."""
        lt_df = _make_lifetime(lifetime_rows)
        ultra_df = _make_ultra_csv(ultra_rows)
        perf_df = _make_perf(perf_rows)

        # Normalizar antes de injetar (simulate _load_*)
        from motor_expansao.lifetime.ponte_unidade_hex import normalize_name
        lt_df["_norm"] = lt_df["UNIDADE"].apply(normalize_name)

        with (
            patch(
                "motor_expansao.lifetime.ponte_unidade_hex._load_lifetime",
                return_value=lt_df,
            ),
            patch(
                "motor_expansao.lifetime.ponte_unidade_hex._load_ultra_csv",
                return_value=ultra_df,
            ),
            patch(
                "motor_expansao.lifetime.ponte_unidade_hex._load_perf_hex",
                return_value=perf_df,
            ),
        ):
            return build_bridge(
                Path("fake/lifetime.parquet"),
                Path("fake/Ultra.csv"),
                Path("fake/perf.parquet"),
                fuzzy_threshold=fuzzy_threshold,
            )

    def test_output_columns(self):
        result = self._run(
            [{"COD_UNIDADE": "10", "UNIDADE": "ASA NORTE", "UF": "DF"}],
            [{"UNIDADE": "Asa Norte / DF", "Latitude": -15.77, "Longitude": -47.89}],
            [],
        )
        assert list(result.columns) == OUTPUT_COLUMNS

    def test_exact_match(self):
        result = self._run(
            [{"COD_UNIDADE": "10", "UNIDADE": "ASA NORTE", "UF": "DF"}],
            [{"UNIDADE": "Asa Norte / DF", "Latitude": -15.77, "Longitude": -47.89}],
            [],
        )
        row = result.iloc[0]
        assert row["metodo_match"] == "exato"
        assert row["match_score"] == pytest.approx(1.0)
        assert row["fonte_geo"] == "ultra_csv"
        assert row["hex_id"] is not None
        assert row["lat"] == pytest.approx(-15.77)
        assert row["lng"] == pytest.approx(-47.89)

    def test_fuzzy_match(self):
        """'jardim botanico' deve casar fuzzy com 'jardim botanico ii'."""
        result = self._run(
            [{"COD_UNIDADE": "10", "UNIDADE": "JARDIM BOTANICO", "UF": "DF"}],
            # Exato não existe; fuzzy deve casar
            [{"UNIDADE": "Jardim Botanico II / DF", "Latitude": -15.8, "Longitude": -47.9}],
            [],
            fuzzy_threshold=0.85,
        )
        row = result.iloc[0]
        assert row["metodo_match"] == "fuzzy"
        assert row["match_score"] >= 0.85
        assert row["fonte_geo"] == "ultra_csv"
        assert row["hex_id"] is not None

    def test_perf_hex_fallback_exact(self):
        """Unidade não presente no Ultra.csv deve ser resolvida pelo perf_hex."""
        result = self._run(
            [{"COD_UNIDADE": "21", "UNIDADE": "CAMPO LIMPO", "UF": "SP"}],
            [],  # Ultra.csv vazio
            [{"unidade": "CAMPO LIMPO", "lat": -23.60, "lng": -46.76}],
        )
        row = result.iloc[0]
        assert row["metodo_match"] == "perf_hex"
        assert row["match_score"] == pytest.approx(1.0)
        assert row["fonte_geo"] == "perf_hex"
        assert row["hex_id"] is not None

    def test_sem_match_survives_with_null_hex(self):
        """Unidade que não casa em nenhuma fonte deve sobreviver com hex_id nulo."""
        result = self._run(
            [{"COD_UNIDADE": "99", "UNIDADE": "UNIDADE FANTASMA XYZ", "UF": "ZZ"}],
            [{"UNIDADE": "Completamente diferente / SP", "Latitude": -23.0, "Longitude": -46.0}],
            [],
        )
        row = result.iloc[0]
        assert row["metodo_match"] == "sem_match"
        assert row["hex_id"] is None
        assert row["lat"] is None

    def test_sem_nome_survives(self):
        """Unidade sem nome (None) deve sobreviver com hex_id nulo e metodo sem_match."""
        result = self._run(
            [{"COD_UNIDADE": "01", "UNIDADE": None, "UF": None}],
            [{"UNIDADE": "Qualquer / SP", "Latitude": -23.0, "Longitude": -46.0}],
            [],
        )
        row = result.iloc[0]
        assert row["metodo_match"] == "sem_match"
        assert row["hex_id"] is None

    def test_multiple_units_all_present(self):
        """Teste com múltiplas unidades: todas devem aparecer na saída."""
        result = self._run(
            [
                {"COD_UNIDADE": "10", "UNIDADE": "ASA NORTE", "UF": "DF"},
                {"COD_UNIDADE": "11", "UNIDADE": "LAGO SUL", "UF": "DF"},
                {"COD_UNIDADE": "99", "UNIDADE": None, "UF": None},
            ],
            [
                {"UNIDADE": "Asa Norte / DF", "Latitude": -15.77, "Longitude": -47.89},
                {"UNIDADE": "Lago Sul / DF", "Latitude": -15.84, "Longitude": -47.92},
            ],
            [],
        )
        assert len(result) == 3
        assert set(result["metodo_match"].unique()) <= {"exato", "sem_match"}

    def test_fuzzy_below_threshold_is_sem_match(self):
        """Score abaixo do limiar não deve resultar em match."""
        result = self._run(
            [{"COD_UNIDADE": "99", "UNIDADE": "ABC DEF GHI", "UF": "SP"}],
            [{"UNIDADE": "XYZ QRS TUV / SP", "Latitude": -23.0, "Longitude": -46.0}],
            [],
            fuzzy_threshold=0.85,
        )
        row = result.iloc[0]
        assert row["metodo_match"] == "sem_match"
        assert row["hex_id"] is None

    def test_hex_id_is_h3_res7(self):
        """hex_id derivado deve ser H3 resolução 7."""
        import h3 as h3lib
        result = self._run(
            [{"COD_UNIDADE": "10", "UNIDADE": "ASA NORTE", "UF": "DF"}],
            [{"UNIDADE": "Asa Norte / DF", "Latitude": -15.769997, "Longitude": -47.891550}],
            [],
        )
        row = result.iloc[0]
        assert row["hex_id"] is not None
        assert h3lib.get_resolution(row["hex_id"]) == 7


# ---------------------------------------------------------------------------
# Teste do relatório de qualidade
# ---------------------------------------------------------------------------

class TestQualityReport:
    def test_report_contains_totals(self):
        bridge = pd.DataFrame(
            {
                "cod_unidade": ["01", "02", "03"],
                "unidade": ["A", "B", None],
                "uf": ["SP", "DF", None],
                "lat": [-23.0, -15.0, None],
                "lng": [-46.0, -47.0, None],
                "hex_id": ["abc123", None, None],
                "metodo_match": ["exato", "sem_match", "sem_match"],
                "match_score": [1.0, 0.0, 0.0],
                "fonte_geo": ["ultra_csv", None, None],
            }
        )
        report = quality_report(bridge)
        assert "BLK-LTV-01" in report
        assert "3" in report  # total
        assert "exato" in report
        assert "sem_match" in report

    def test_sem_match_list_in_report(self):
        bridge = pd.DataFrame(
            {
                "cod_unidade": ["01"],
                "unidade": ["UNIDADE FANTASMA"],
                "uf": ["ZZ"],
                "lat": [None],
                "lng": [None],
                "hex_id": [None],
                "metodo_match": ["sem_match"],
                "match_score": [0.0],
                "fonte_geo": [None],
            }
        )
        report = quality_report(bridge)
        assert "UNIDADE FANTASMA" in report
        assert "01" in report
