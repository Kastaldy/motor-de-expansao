"""
tests/unit/test_score_consolidado.py — Testes do pipeline de score final

Testa:
- Cálculo de score competitivo com/sem concorrentes
- Estimativas de alunos e payback
- Score de abertura e invariantes de ordenação
- Pipeline completo de ranking
"""

import pytest
import pandas as pd

from score_consolidado import (
    calcular_score_competitivo,
    calcular_alunos_estimados,
    calcular_payback_estimado,
    calcular_score_abertura,
    gerar_ranking_oportunidades,
    _normalizar_payback,
)


# ============================================================
#  FIXTURES
# ============================================================

@pytest.fixture
def df_concorrentes_vazio():
    return pd.DataFrame(columns=["nome", "lat", "lng", "tipo"])


@pytest.fixture
def df_concorrentes_com_rede_grande():
    """2 SmartFit próximas ao hexágono central de SP."""
    return pd.DataFrame([
        {"nome": "SmartFit A", "lat": -23.550, "lng": -46.630, "tipo": "rede_grande"},
        {"nome": "SmartFit B", "lat": -23.552, "lng": -46.628, "tipo": "rede_grande"},
    ])


@pytest.fixture
def df_concorrentes_independente():
    """1 academia independente — alvo de aquisição."""
    return pd.DataFrame([
        {"nome": "Academia Local", "lat": -23.551, "lng": -46.631, "tipo": "independente"},
    ])


@pytest.fixture
def hex_sp_centro():
    """hex_id H3 res=8 próximo ao centro de SP."""
    import h3
    return h3.geo_to_h3(-23.550, -46.633, 8)


@pytest.fixture
def df_imoveis_qualificados():
    return pd.DataFrame([
        {
            "area_m2": 900, "lat": -23.55, "lng": -46.63,
            "preco_aluguel": 45_000, "cidade": "São Paulo", "uf": "SP",
            "qualificado": True, "imovel_score": 85.0, "status": "qualificado",
            "titulo": "Galpão Prime SP", "fonte": "zap",
        },
        {
            "area_m2": 1200, "lat": -23.56, "lng": -46.64,
            "preco_aluguel": 60_000, "cidade": "São Paulo", "uf": "SP",
            "qualificado": True, "imovel_score": 78.0, "status": "qualificado",
            "titulo": "Loja Grande Pinheiros", "fonte": "vivareal",
        },
        {
            "area_m2": 200, "lat": -23.57, "lng": -46.65,
            "preco_aluguel": 8_000, "cidade": "São Paulo", "uf": "SP",
            "qualificado": False, "imovel_score": None, "status": "descartado",
            "titulo": "Sala pequena", "fonte": "zap",
        },
    ])


@pytest.fixture
def df_hexagonos_sp():
    import h3
    hex1 = h3.geo_to_h3(-23.55, -46.63, 8)
    hex2 = h3.geo_to_h3(-23.56, -46.64, 8)
    return pd.DataFrame([
        {"hex_id": hex1, "hex_score": 82.0, "renda_media": 7_500, "pop_18_45": 18_000, "n_concorrentes": 1},
        {"hex_id": hex2, "hex_score": 71.0, "renda_media": 5_500, "pop_18_45": 12_000, "n_concorrentes": 0},
    ])


# ============================================================
#  SCORE COMPETITIVO
# ============================================================

class TestScoreCompetitivo:
    def test_sem_concorrentes_retorna_100(self, hex_sp_centro, df_concorrentes_vazio):
        score = calcular_score_competitivo(hex_sp_centro, df_concorrentes_vazio)
        assert score == 100.0

    def test_rede_grande_penaliza_mais(self, hex_sp_centro, df_concorrentes_com_rede_grande, df_concorrentes_independente):
        score_rede = calcular_score_competitivo(hex_sp_centro, df_concorrentes_com_rede_grande)
        score_indep = calcular_score_competitivo(hex_sp_centro, df_concorrentes_independente)
        assert score_rede < score_indep

    def test_score_nunca_negativo(self, hex_sp_centro):
        """Muitos concorrentes — score mínimo é 0."""
        muitos = pd.DataFrame([
            {"nome": f"Academia {i}", "lat": -23.550 + i * 0.001, "lng": -46.630, "tipo": "rede_grande"}
            for i in range(10)
        ])
        score = calcular_score_competitivo(hex_sp_centro, muitos)
        assert score >= 0.0

    def test_score_sempre_entre_0_e_100(self, hex_sp_centro, df_concorrentes_com_rede_grande):
        score = calcular_score_competitivo(hex_sp_centro, df_concorrentes_com_rede_grande)
        assert 0 <= score <= 100

    def test_concorrentes_sem_coordenadas_ignorados(self, hex_sp_centro):
        df = pd.DataFrame([{"nome": "X", "lat": None, "lng": None, "tipo": "rede_grande"}])
        score = calcular_score_competitivo(hex_sp_centro, df)
        assert score == 100.0


# ============================================================
#  ESTIMATIVAS
# ============================================================

class TestEstimativas:
    def test_alunos_maiores_em_hex_melhor(self):
        est_bom  = calcular_alunos_estimados(90, 1000, 90)
        est_ruim = calcular_alunos_estimados(30, 600, 30)
        assert est_bom > est_ruim

    def test_alunos_positivos(self):
        assert calcular_alunos_estimados(50, 800, 50) > 0

    def test_payback_inviavel_retorna_999(self):
        """Aluguel muito alto relativo à receita → payback inviável."""
        payback = calcular_payback_estimado(
            alunos_est=50,
            preco_aluguel=200_000,  # Aluguel absurdo
        )
        assert payback == 999.0

    def test_payback_menor_com_mais_alunos(self):
        p1 = calcular_payback_estimado(800, 30_000)
        p2 = calcular_payback_estimado(200, 30_000)
        assert p1 < p2

    def test_normalizar_payback_0_meses_retorna_100(self):
        assert _normalizar_payback(0) == 100.0

    def test_normalizar_payback_acima_referencia_retorna_0(self):
        assert _normalizar_payback(40, referencia_max=36) == 0.0

    def test_normalizar_payback_metade_referencia(self):
        score = _normalizar_payback(18, referencia_max=36)
        assert score == pytest.approx(50.0, abs=1.0)


# ============================================================
#  SCORE DE ABERTURA
# ============================================================

class TestScoreAbertura:
    def test_score_no_range_0_100(self):
        row = pd.Series({
            "hex_score": 80, "score_competitivo": 70,
            "imovel_score": 85, "alunos_est": 600, "payback_est": 20,
        })
        score = calcular_score_abertura(row)
        assert 0 <= score <= 100

    def test_melhor_perfil_maior_score(self):
        otimo = pd.Series({"hex_score": 95, "score_competitivo": 95, "imovel_score": 95, "alunos_est": 900, "payback_est": 12})
        ruim  = pd.Series({"hex_score": 20, "score_competitivo": 20, "imovel_score": 30, "alunos_est": 150, "payback_est": 30})
        assert calcular_score_abertura(otimo) > calcular_score_abertura(ruim)

    def test_valores_nulos_nao_quebram(self):
        row = pd.Series({"hex_score": None, "score_competitivo": None, "imovel_score": None})
        score = calcular_score_abertura(row)
        assert 0 <= score <= 100


# ============================================================
#  PIPELINE COMPLETO
# ============================================================

class TestRankingOportunidades:
    def test_ranking_retorna_apenas_qualificados(self, df_imoveis_qualificados, df_hexagonos_sp, df_concorrentes_vazio):
        resultado = gerar_ranking_oportunidades(df_imoveis_qualificados, df_hexagonos_sp, df_concorrentes_vazio)
        assert len(resultado) == 2  # Apenas os 2 qualificados
        assert (resultado["status"] == "descartado").sum() == 0

    def test_ranking_ordenado_por_score(self, df_imoveis_qualificados, df_hexagonos_sp, df_concorrentes_vazio):
        resultado = gerar_ranking_oportunidades(df_imoveis_qualificados, df_hexagonos_sp, df_concorrentes_vazio)
        scores = resultado["score_abertura"].values
        assert all(scores[i] >= scores[i+1] for i in range(len(scores)-1))

    def test_ranking_tem_coluna_rank(self, df_imoveis_qualificados, df_hexagonos_sp, df_concorrentes_vazio):
        resultado = gerar_ranking_oportunidades(df_imoveis_qualificados, df_hexagonos_sp, df_concorrentes_vazio)
        assert "rank" in resultado.columns
        assert resultado["rank"].iloc[0] == 1

    def test_ranking_vazio_sem_qualificados(self, df_concorrentes_vazio):
        df_nenhum = pd.DataFrame([
            {"qualificado": False, "status": "descartado", "area_m2": 100,
             "lat": -23.55, "lng": -46.63, "preco_aluguel": 5000}
        ])
        resultado = gerar_ranking_oportunidades(df_nenhum, pd.DataFrame(), df_concorrentes_vazio)
        assert len(resultado) == 0
