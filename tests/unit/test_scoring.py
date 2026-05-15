import pandas as pd
import pytest

from hex_enrichment import calcular_hex_score, normalizar_0_100
from motor_expansao.core.scoring import (
    _calcular_percentil_nacional,
    calcular_ajuste_executivo,
    calcular_hex_score_estrutural as calcular_hex_score_estrutural_core,
)


@pytest.fixture
def df_hexagonos():
    return pd.DataFrame(
        {
            "hex_id": ["hex_A", "hex_B", "hex_C"],
            "renda_per_capita": [8_000, 3_000, 1_500],
            "pop_total": [15_000, 8_000, 3_000],
            "n_academias_osm": [0, 2, 5],
            "score_vitalidade": [50.0, 50.0, 50.0],
        }
    )


class TestHexScore:
    def test_hex_score_no_range_0_100(self, df_hexagonos):
        resultado = calcular_hex_score(df_hexagonos)
        assert resultado["hex_score"].between(0, 100).all()

    def test_hex_maior_renda_maior_score(self, df_hexagonos):
        resultado = calcular_hex_score(df_hexagonos)
        scores = resultado.sort_values("renda_per_capita", ascending=False)["hex_score"].values
        assert scores[0] >= scores[-1]

    def test_hex_score_presente_para_todos(self, df_hexagonos):
        resultado = calcular_hex_score(df_hexagonos)
        assert resultado["hex_score"].notna().all()

    def test_normalizar_0_100_range(self):
        serie = pd.Series([10, 20, 30, 40, 50])
        normalizada = normalizar_0_100(serie)
        assert normalizada.min() == pytest.approx(0.0)
        assert normalizada.max() == pytest.approx(100.0)

    def test_normalizar_serie_constante_retorna_50(self):
        serie = pd.Series([42, 42, 42])
        resultado = normalizar_0_100(serie)
        assert (resultado == 50.0).all()


class TestM1CoreScoring:
    def test_percentil_nacional_ignora_nulos_e_preserva_indice(self):
        serie = pd.Series([10.0, None, 30.0, 20.0], index=["a", "b", "c", "d"])

        resultado = _calcular_percentil_nacional(serie)

        assert resultado.loc["a"] == 0.0
        assert pd.isna(resultado.loc["b"])
        assert resultado.loc["c"] == 1.0
        assert resultado.loc["d"] == 0.5

    def test_ajuste_executivo_aplica_bonus_e_penalidades(self):
        renda_pct = pd.Series([0.90, 0.90, 0.50, 0.10])
        pop_pct = pd.Series([0.90, 0.50, 0.90, 0.10])

        resultado = calcular_ajuste_executivo(renda_pct, pop_pct)

        assert resultado.tolist() == [5.0, 2.0, 1.0, -8.0]

    def test_score_estrutural_core_calcula_percentis_pesos_e_clip(self):
        df = pd.DataFrame(
            [
                {"hex_id": "top", "renda_per_capita": 6000.0, "pop_total": 600.0},
                {"hex_id": "mid", "renda_per_capita": 3000.0, "pop_total": 300.0},
                {"hex_id": "zero", "renda_per_capita": 6000.0, "pop_total": 0.0},
            ]
        )

        resultado = calcular_hex_score_estrutural_core(df).set_index("hex_id")

        assert resultado.loc["top", "renda_pct_nacional"] == 1.0
        assert resultado.loc["top", "pop_pct_nacional"] == 1.0
        assert resultado.loc["top", "hex_score_estrutural"] == 100.0
        assert resultado.loc["top", "ajuste_executivo"] == 5.0
        assert resultado.loc["top", "score_priorizacao"] == 100.0

        assert resultado.loc["mid", "renda_pct_nacional"] == 0.0
        assert resultado.loc["mid", "pop_pct_nacional"] == 0.0
        assert resultado.loc["mid", "hex_score_estrutural"] == 0.0
        assert resultado.loc["mid", "ajuste_executivo"] == -8.0
        assert resultado.loc["mid", "score_priorizacao"] == 0.0

        assert bool(resultado.loc["zero", "hex_sem_populacao"]) is True
        assert pd.isna(resultado.loc["zero", "renda_pct_nacional"])
        assert resultado.loc["zero", "hex_score_estrutural"] == 0.0
