"""
tests/unit/test_scoring.py — Testes unitários de scores e qualificação

Regras testadas:
- Scores de área, preço, imóvel e hexágono
- Filtros eliminatórios de imóveis
- Invariantes de ordenação (A > B => score_A >= score_B)
- Comportamento com inputs extremos e nulos
"""

import pytest
import pandas as pd

from jobs.pipelines.imovel_qualification import (
    qualificar_imovel,
    processar_lote_imoveis,
    _score_area,
    _score_preco_m2,
    STATUS_QUALIFICADO,
    STATUS_DESCARTADO,
)
from jobs.pipelines.hex_enrichment import (
    calcular_hex_score,
    normalizar_0_100,
)


# ============================================================
#  FIXTURES
# ============================================================

@pytest.fixture
def imovel_valido():
    return {
        "area_m2": 900,
        "lat": -23.55,
        "lng": -46.63,
        "preco_aluguel": 45_000,
        "cidade": "São Paulo",
        "tem_estacionamento": True,
        "tem_fachada": True,
        "dist_ultra_mais_proxima_km": 5.0,
    }


@pytest.fixture
def imovel_minimo():
    """Imóvel que passa com nota mínima aceitável."""
    return {
        "area_m2": 600,
        "lat": -19.92,
        "lng": -43.94,
        "preco_aluguel": 30_000,
        "cidade": "Belo Horizonte",
        "tem_estacionamento": False,
        "tem_fachada": False,
        "dist_ultra_mais_proxima_km": 3.0,
    }


@pytest.fixture
def df_hexagonos():
    return pd.DataFrame({
        "hex_id": ["hex_A", "hex_B", "hex_C"],
        "renda_media": [8_000, 3_000, 1_500],
        "pop_18_45": [15_000, 8_000, 3_000],
        "n_concorrentes": [0, 2, 5],
    })


# ============================================================
#  TESTES DE SCORE DE ÁREA
# ============================================================

class TestScoreArea:
    def test_area_ideal_retorna_100(self):
        assert _score_area(900) == 100.0
        assert _score_area(1200) == 100.0
        assert _score_area(1500) == 100.0

    def test_area_minima_retorna_60(self):
        score = _score_area(600)
        assert score == pytest.approx(60.0, abs=1.0)

    def test_area_grande_penalizada(self):
        assert _score_area(3000) == 60.0

    def test_area_abaixo_minimo_retorna_0(self):
        assert _score_area(400) == 0.0
        assert _score_area(0) == 0.0
        assert _score_area(599) == 0.0

    def test_invariante_maior_area_maior_score_ate_1500(self):
        """Imóveis maiores devem ter score maior (até 1500m²)."""
        scores = [_score_area(a) for a in [600, 700, 800, 900, 1200, 1500]]
        for i in range(len(scores) - 1):
            assert scores[i] <= scores[i + 1], f"Quebra de invariante: score({600 + i*150}) > score({750 + i*150})"


# ============================================================
#  TESTES DE QUALIFICAÇÃO DE IMÓVEL
# ============================================================

class TestQualificacaoImovel:
    def test_imovel_valido_qualificado(self, imovel_valido):
        res = qualificar_imovel(imovel_valido)
        assert res.qualificado is True
        assert res.status == STATUS_QUALIFICADO
        assert res.imovel_score is not None
        assert 0 <= res.imovel_score <= 100

    def test_area_insuficiente_desqualifica(self, imovel_valido):
        imovel_valido["area_m2"] = 400
        res = qualificar_imovel(imovel_valido)
        assert res.qualificado is False
        assert res.status == STATUS_DESCARTADO
        assert "Área" in res.motivo_desqualificacao

    def test_sem_coordenadas_desqualifica(self, imovel_valido):
        imovel_valido["lat"] = None
        res = qualificar_imovel(imovel_valido)
        assert res.qualificado is False
        assert "Coordenadas" in res.motivo_desqualificacao

    def test_coordenada_fora_brasil_desqualifica(self, imovel_valido):
        imovel_valido["lat"] = 40.71   # Nova York
        imovel_valido["lng"] = -74.01
        res = qualificar_imovel(imovel_valido)
        assert res.qualificado is False
        assert "Brasil" in res.motivo_desqualificacao

    def test_sem_preco_desqualifica(self, imovel_valido):
        imovel_valido["preco_aluguel"] = None
        res = qualificar_imovel(imovel_valido)
        assert res.qualificado is False

    def test_canibalizacao_desqualifica(self, imovel_valido):
        imovel_valido["dist_ultra_mais_proxima_km"] = 1.0  # < 2km
        res = qualificar_imovel(imovel_valido)
        assert res.qualificado is False
        assert "Canibalização" in res.motivo_desqualificacao

    def test_score_com_estacionamento_maior(self, imovel_valido):
        """Imóvel com estacionamento deve ter score maior."""
        com = dict(imovel_valido, tem_estacionamento=True)
        sem = dict(imovel_valido, tem_estacionamento=False)
        assert qualificar_imovel(com).imovel_score > qualificar_imovel(sem).imovel_score

    def test_score_retorna_none_quando_desqualificado(self, imovel_valido):
        imovel_valido["area_m2"] = 100
        res = qualificar_imovel(imovel_valido)
        assert res.imovel_score is None

    def test_area_exatamente_no_limite(self, imovel_valido):
        """Área exatamente 600m² deve qualificar."""
        imovel_valido["area_m2"] = 600.0
        res = qualificar_imovel(imovel_valido)
        assert res.qualificado is True


# ============================================================
#  TESTES DE PROCESSAMENTO EM LOTE
# ============================================================

class TestProcessarLote:
    def test_lote_retorna_colunas_esperadas(self):
        df = pd.DataFrame([
            {"area_m2": 900, "lat": -23.55, "lng": -46.63,
             "preco_aluguel": 40_000, "cidade": "São Paulo",
             "dist_ultra_mais_proxima_km": 5.0},
            {"area_m2": 200, "lat": -23.55, "lng": -46.63,
             "preco_aluguel": 10_000, "cidade": "São Paulo",
             "dist_ultra_mais_proxima_km": 5.0},
        ])
        resultado = processar_lote_imoveis(df)
        assert "qualificado" in resultado.columns
        assert "imovel_score" in resultado.columns
        assert "status" in resultado.columns
        assert "motivo_desqualificacao" in resultado.columns

    def test_lote_preserva_linhas_originais(self):
        df = pd.DataFrame([
            {"area_m2": 900, "lat": -23.55, "lng": -46.63,
             "preco_aluguel": 40_000, "cidade": "SP",
             "dist_ultra_mais_proxima_km": 5.0},
        ])
        resultado = processar_lote_imoveis(df)
        assert len(resultado) == len(df)

    def test_lote_vazio_retorna_vazio(self):
        df = pd.DataFrame()
        # Não deve lançar exceção
        resultado = processar_lote_imoveis(df)
        assert len(resultado) == 0


# ============================================================
#  TESTES DE HEX SCORE
# ============================================================

class TestHexScore:
    def test_hex_score_no_range_0_100(self, df_hexagonos):
        resultado = calcular_hex_score(df_hexagonos)
        assert resultado["hex_score"].between(0, 100).all()

    def test_hex_maior_renda_maior_score(self, df_hexagonos):
        resultado = calcular_hex_score(df_hexagonos)
        scores = resultado.sort_values("renda_media", ascending=False)["hex_score"].values
        # Hex com maior renda deve ter score maior que o com menor
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
        """Série constante (sem variância) retorna 50 para todos."""
        serie = pd.Series([42, 42, 42])
        resultado = normalizar_0_100(serie)
        assert (resultado == 50.0).all()
