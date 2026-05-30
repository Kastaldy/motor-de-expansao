"""
Testes unitarios — Expansao de Dominio (Blocos 2 e 3)
"""
from __future__ import annotations

import math

import h3
import pandas as pd
import pytest

from motor_expansao.pipelines.gerar_plano_expansao_dominio import (
    PESO_CENSO_DOMINIO,
    PESO_RESIDUAL_DOMINIO,
    SAIDA_CSV,
    SAIDA_PARQUET,
    SCHEMA_DOMINIO_OBRIGATORIO,
    _haversine_m,
    calcular_metricas_cluster,
    calcular_score_dominio_hibrido,
    classificar_tese_dominio,
    construir_clusters,
    filtrar_candidatos,
    gerar_plano_dominio,
    selecionar_ancoras_greedy,
    validate_dominio_schema,
)

# ── IDs H3 res7 reais usados nos testes ──────────────────────────────────────
# SP centro e seus vizinhos diretos
_SP_CENTER = h3.latlng_to_cell(-23.5505, -46.6333, 7)
_SP_NEIGHBORS = sorted(set(h3.grid_disk(_SP_CENTER, 1)) - {_SP_CENTER})
_SP_N1 = _SP_NEIGHBORS[0]
_SP_N2 = _SP_NEIGHBORS[1]
# Hex 2 passos do centro (~2.4 km) — garante dist > 1.5 km
_SP_RING2 = sorted(set(h3.grid_disk(_SP_CENTER, 2)) - set(h3.grid_disk(_SP_CENTER, 1)))[0]
# Hex em outro municipio (Rio de Janeiro)
_RJ_HEX = h3.latlng_to_cell(-22.9068, -43.1729, 7)

# Coordenadas lat/lng dos hexes usados nos testes de distancia
_SP_CENTER_LATLNG = h3.cell_to_latlng(_SP_CENTER)
_SP_N1_LATLNG = h3.cell_to_latlng(_SP_N1)
_SP_RING2_LATLNG = h3.cell_to_latlng(_SP_RING2)


def _row(
    hex_id=_SP_CENTER,
    uf="SP",
    cod_municipio="3550308",
    nome_municipio="Sao Paulo",
    lat=-23.5505,
    lng=-46.6333,
    flag_sam_fitness=True,
    oferta_efetiva_disponivel=1000.0,
    score_oportunidade_residual=50.0,
    flag_canibalizacao_ultra_1km=False,
    dist_ultra_mais_proxima_m=3000.0,
    sam_fitness_potencial=2000.0,
    pressao_concorrencial_score_2km=30.0,
    flag_white_space_2km=True,
    n_concorrentes_mapeados_2km=0,
    **kwargs,
) -> dict:
    base = dict(
        hex_id=hex_id,
        uf=uf,
        cod_municipio=cod_municipio,
        nome_municipio=nome_municipio,
        lat=lat,
        lng=lng,
        flag_sam_fitness=flag_sam_fitness,
        oferta_efetiva_disponivel=oferta_efetiva_disponivel,
        score_oportunidade_residual=score_oportunidade_residual,
        flag_canibalizacao_ultra_1km=flag_canibalizacao_ultra_1km,
        dist_ultra_mais_proxima_m=dist_ultra_mais_proxima_m,
        sam_fitness_potencial=sam_fitness_potencial,
        pressao_concorrencial_score_2km=pressao_concorrencial_score_2km,
        flag_white_space_2km=flag_white_space_2km,
        n_concorrentes_mapeados_2km=n_concorrentes_mapeados_2km,
    )
    base.update(kwargs)
    return base


def _df(*rows) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


# =============================================================================
# calcular_score_dominio_hibrido
# =============================================================================

class TestCalcularScoreDominioHibrido:
    def _df_ambos(self, censo=70.0, residual=50.0) -> pd.DataFrame:
        return pd.DataFrame([_row(
            score_oportunidade_residual=residual,
            score_setor_2022_calibrado=censo,
        )])

    def _df_sem_censo(self, residual=50.0) -> pd.DataFrame:
        return pd.DataFrame([_row(score_oportunidade_residual=residual)])

    def test_colunas_rastreabilidade_presentes(self):
        result = calcular_score_dominio_hibrido(self._df_ambos())
        for col in [
            "score_dominio_hibrido", "peso_censitario_dominio", "peso_residual_dominio",
            "flag_dominio_por_censo", "flag_dominio_por_residual", "motivo_dominio",
        ]:
            assert col in result.columns, f"coluna ausente: {col}"

    def test_formula_ambos_componentes(self):
        result = calcular_score_dominio_hibrido(self._df_ambos(censo=80.0, residual=60.0))
        esperado = round(PESO_CENSO_DOMINIO * 80.0 + PESO_RESIDUAL_DOMINIO * 60.0, 2)
        assert float(result["score_dominio_hibrido"].iloc[0]) == pytest.approx(esperado)

    def test_motivo_ambos_componentes(self):
        result = calcular_score_dominio_hibrido(self._df_ambos())
        assert result["motivo_dominio"].iloc[0] == "censitario+residual"

    def test_pesos_ambos_componentes(self):
        result = calcular_score_dominio_hibrido(self._df_ambos())
        assert float(result["peso_censitario_dominio"].iloc[0]) == pytest.approx(PESO_CENSO_DOMINIO)
        assert float(result["peso_residual_dominio"].iloc[0]) == pytest.approx(PESO_RESIDUAL_DOMINIO)

    def test_fallback_so_residual_sem_coluna_censo(self):
        result = calcular_score_dominio_hibrido(self._df_sem_censo(residual=45.0))
        assert float(result["score_dominio_hibrido"].iloc[0]) == pytest.approx(45.0)
        assert result["motivo_dominio"].iloc[0] == "so_residual"
        assert float(result["peso_residual_dominio"].iloc[0]) == pytest.approx(1.0)
        assert float(result["peso_censitario_dominio"].iloc[0]) == pytest.approx(0.0)

    def test_clipping_nao_ultrapassa_100(self):
        result = calcular_score_dominio_hibrido(self._df_ambos(censo=100.0, residual=100.0))
        assert float(result["score_dominio_hibrido"].iloc[0]) <= 100.0

    def test_clipping_nao_negativo(self):
        result = calcular_score_dominio_hibrido(self._df_ambos(censo=0.0, residual=0.0))
        assert float(result["score_dominio_hibrido"].iloc[0]) >= 0.0

    def test_nao_altera_score_priorizacao(self):
        df = pd.DataFrame([_row(score_oportunidade_residual=50.0, score_priorizacao=88.0)])
        result = calcular_score_dominio_hibrido(df)
        assert float(result["score_priorizacao"].iloc[0]) == pytest.approx(88.0)

    def test_flag_dominio_por_censo_verdadeiro_quando_censo_presente(self):
        result = calcular_score_dominio_hibrido(self._df_ambos())
        assert bool(result["flag_dominio_por_censo"].iloc[0]) is True

    def test_flag_dominio_por_censo_falso_sem_coluna_censo(self):
        result = calcular_score_dominio_hibrido(self._df_sem_censo())
        assert bool(result["flag_dominio_por_censo"].iloc[0]) is False

    def test_nao_muta_dataframe_original(self):
        df = self._df_ambos()
        cols_antes = set(df.columns)
        calcular_score_dominio_hibrido(df)
        assert set(df.columns) == cols_antes


# =============================================================================
# filtrar_candidatos
# =============================================================================

class TestFiltrarCandidatos:
    def test_hex_valido_passa(self):
        df = _df(_row())
        result = filtrar_candidatos(df)
        assert len(result) == 1

    def test_canibalizacao_bloqueia(self):
        df = _df(_row(flag_canibalizacao_ultra_1km=True))
        result = filtrar_candidatos(df)
        assert len(result) == 0

    def test_sam_falso_bloqueia(self):
        df = _df(_row(flag_sam_fitness=False))
        result = filtrar_candidatos(df)
        assert len(result) == 0

    def test_oferta_zero_bloqueia(self):
        df = _df(_row(oferta_efetiva_disponivel=0.0))
        result = filtrar_candidatos(df)
        assert len(result) == 0

    def test_oferta_negativa_bloqueia(self):
        df = _df(_row(oferta_efetiva_disponivel=-100.0))
        result = filtrar_candidatos(df)
        assert len(result) == 0

    def test_score_abaixo_do_minimo_bloqueia(self):
        df = _df(_row(score_oportunidade_residual=10.0))
        result = filtrar_candidatos(df)
        assert len(result) == 0

    def test_score_exatamente_no_minimo_passa(self):
        df = _df(_row(score_oportunidade_residual=20.0))
        result = filtrar_candidatos(df)
        assert len(result) == 1

    def test_coordenada_nula_bloqueia(self):
        df = _df(_row(lat=None, lng=None))
        result = filtrar_candidatos(df)
        assert len(result) == 0

    def test_coordenada_invalida_bloqueia(self):
        df = _df(_row(lat=200.0, lng=400.0))
        result = filtrar_candidatos(df)
        assert len(result) == 0

    def test_min_score_customizavel(self):
        df = _df(_row(score_oportunidade_residual=35.0))
        assert len(filtrar_candidatos(df, min_score=30.0)) == 1
        assert len(filtrar_candidatos(df, min_score=40.0)) == 0

    def test_nao_altera_score_priorizacao_quando_presente(self):
        df = _df(_row(score_priorizacao=88.0, hex_score_estrutural=82.0))
        result = filtrar_candidatos(df)
        assert float(result.loc[0, "score_priorizacao"]) == 88.0
        assert float(result.loc[0, "hex_score_estrutural"]) == 82.0


# =============================================================================
# construir_clusters
# =============================================================================

class TestConstruirClusters:
    def test_dois_adjacentes_mesmo_municipio_formam_um_cluster(self):
        df = _df(
            _row(hex_id=_SP_CENTER),
            _row(hex_id=_SP_N1),
        )
        result = construir_clusters(filtrar_candidatos(df))
        assert result["cluster_id"].nunique() == 1

    def test_dois_nao_adjacentes_mesmo_municipio_formam_dois_clusters(self):
        # Usa um hex distante em SP (RJ nao e adjacente a SP)
        # Para garantir nao-adjacencia, escolhe hex de municipio distinto
        # mas com mesmo cod_municipio simulado — verifica pelo proprio ID
        h_far = h3.latlng_to_cell(-23.6505, -46.7333, 7)
        df = _df(
            _row(hex_id=_SP_CENTER),
            _row(hex_id=h_far),
        )
        candidates = filtrar_candidatos(df)
        result = construir_clusters(candidates)
        # Se sao adjacentes, 1 cluster; se nao, 2
        expected = 1 if h3.are_neighbor_cells(_SP_CENTER, h_far) else 2
        assert result["cluster_id"].nunique() == expected

    def test_municipios_diferentes_nao_agrupam(self):
        df = _df(
            _row(hex_id=_SP_CENTER, cod_municipio="3550308"),
            _row(hex_id=_RJ_HEX, cod_municipio="3304557", uf="RJ",
                 lat=-22.9068, lng=-43.1729),
        )
        result = construir_clusters(filtrar_candidatos(df))
        assert result["cluster_id"].nunique() == 2

    def test_tres_adjacentes_formam_um_cluster(self):
        df = _df(
            _row(hex_id=_SP_CENTER),
            _row(hex_id=_SP_N1),
            _row(hex_id=_SP_N2),
        )
        result = construir_clusters(filtrar_candidatos(df))
        assert result["cluster_id"].nunique() == 1

    def test_cluster_id_formato_correto(self):
        df = _df(_row(hex_id=_SP_CENTER, cod_municipio="3550308"))
        result = construir_clusters(filtrar_candidatos(df))
        assert result.loc[0, "cluster_id"].startswith("3550308_")

    def test_dataframe_vazio_retorna_vazio_sem_erro(self):
        df = pd.DataFrame(columns=_df(_row()).columns)
        result = construir_clusters(df)
        assert result.empty
        assert "cluster_id" in result.columns


# =============================================================================
# calcular_metricas_cluster
# =============================================================================

class TestCalcularMetricasCluster:
    def _base_df(self) -> pd.DataFrame:
        df = _df(
            _row(hex_id=_SP_CENTER, oferta_efetiva_disponivel=1000.0,
                 score_oportunidade_residual=60.0, sam_fitness_potencial=2000.0,
                 pressao_concorrencial_score_2km=30.0, dist_ultra_mais_proxima_m=3000.0),
            _row(hex_id=_SP_N1, oferta_efetiva_disponivel=500.0,
                 score_oportunidade_residual=40.0, sam_fitness_potencial=1000.0,
                 pressao_concorrencial_score_2km=10.0, dist_ultra_mais_proxima_m=2000.0),
        )
        df = construir_clusters(filtrar_candidatos(df))
        return df

    def test_n_hex_cluster_correto(self):
        df = calcular_metricas_cluster(self._base_df())
        assert (df["n_hex_cluster"] == 2).all()

    def test_residual_total_correto(self):
        df = calcular_metricas_cluster(self._base_df())
        assert df["residual_total_cluster"].iloc[0] == pytest.approx(1500.0)

    def test_score_residual_max_correto(self):
        df = calcular_metricas_cluster(self._base_df())
        assert df["score_residual_max"].iloc[0] == pytest.approx(60.0)

    def test_score_residual_medio_correto(self):
        df = calcular_metricas_cluster(self._base_df())
        assert df["score_residual_medio"].iloc[0] == pytest.approx(50.0)

    def test_sam_total_correto(self):
        df = calcular_metricas_cluster(self._base_df())
        assert df["sam_total_cluster"].iloc[0] == pytest.approx(3000.0)

    def test_pressao_media_correta(self):
        df = calcular_metricas_cluster(self._base_df())
        assert df["pressao_concorrencial_media"].iloc[0] == pytest.approx(20.0)

    def test_dist_ultra_min_correta(self):
        df = calcular_metricas_cluster(self._base_df())
        assert df["dist_ultra_min_cluster"].iloc[0] == pytest.approx(2000.0)

    def test_dataframe_vazio_nao_lanca_excecao(self):
        df = pd.DataFrame(columns=_df(_row()).columns)
        result = calcular_metricas_cluster(df)
        assert result.empty


# =============================================================================
# _haversine_m
# =============================================================================

class TestHaversineM:
    def test_mesmo_ponto_retorna_zero(self):
        assert _haversine_m(-23.5505, -46.6333, -23.5505, -46.6333) == pytest.approx(0.0)

    def test_distancia_positiva(self):
        d = _haversine_m(*_SP_CENTER_LATLNG, *_SP_N1_LATLNG)
        assert d > 0

    def test_simetria(self):
        d1 = _haversine_m(*_SP_CENTER_LATLNG, *_SP_N1_LATLNG)
        d2 = _haversine_m(*_SP_N1_LATLNG, *_SP_CENTER_LATLNG)
        assert d1 == pytest.approx(d2)

    def test_hexes_adjacentes_res7_menos_de_3km(self):
        # H3 res7: distancia entre centros adjacentes ~2.5 km
        d = _haversine_m(*_SP_CENTER_LATLNG, *_SP_N1_LATLNG)
        assert d < 3000.0

    def test_hex_ring2_mais_de_1500m(self):
        d = _haversine_m(*_SP_CENTER_LATLNG, *_SP_RING2_LATLNG)
        assert d > 1500.0


# =============================================================================
# classificar_tese_dominio
# =============================================================================

class TestClassificarTese:
    def test_white_space_score_alto(self):
        assert classificar_tese_dominio(1, 80.0, 0, 5000.0, True) == "dominar_white_space"

    def test_white_space_score_baixo_nao_classifica_como_ws(self):
        tese = classificar_tese_dominio(1, 30.0, 0, 5000.0, True)
        assert tese != "dominar_white_space"

    def test_proteger_corredor_1km_a_2km(self):
        assert classificar_tese_dominio(1, 60.0, 0, 1500.0, False) == "proteger_corredor_ultra"

    def test_proteger_corredor_precede_white_space(self):
        assert classificar_tese_dominio(1, 80.0, 0, 1200.0, True) == "proteger_corredor_ultra"

    def test_abrir_com_disputa_ordem1_com_concorrentes(self):
        assert classificar_tese_dominio(1, 40.0, 3, 5000.0, False) == "abrir_com_disputa"

    def test_adensar_cluster_ordem2(self):
        assert classificar_tese_dominio(2, 40.0, 0, 5000.0, False) == "adensar_cluster"

    def test_monitorar_sem_triggers(self):
        assert classificar_tese_dominio(1, 30.0, 0, 5000.0, False) == "monitorar"

    def test_dist_ultra_exatamente_1km_protege(self):
        assert classificar_tese_dominio(1, 60.0, 0, 1000.0, False) == "proteger_corredor_ultra"

    def test_dist_ultra_exatamente_2km_nao_protege(self):
        tese = classificar_tese_dominio(1, 80.0, 0, 2000.0, True)
        assert tese != "proteger_corredor_ultra"


# =============================================================================
# selecionar_ancoras_greedy
# =============================================================================

def _cidade_df(*rows) -> pd.DataFrame:
    """Constroi DataFrame de candidatos ja filtrados para testes do greedy."""
    base = _df(*rows)
    return filtrar_candidatos(construir_clusters(base))


class TestSelecionarAncorasGreedy:
    def _candidato_centro(self, **kw):
        lat, lng = _SP_CENTER_LATLNG
        return _row(hex_id=_SP_CENTER, lat=lat, lng=lng, **kw)

    def _candidato_ring2(self, **kw):
        lat, lng = _SP_RING2_LATLNG
        return _row(hex_id=_SP_RING2, lat=lat, lng=lng, **kw)

    def _candidato_n1(self, **kw):
        lat, lng = _SP_N1_LATLNG
        return _row(hex_id=_SP_N1, lat=lat, lng=lng, **kw)

    def test_df_vazio_retorna_vazio(self):
        df = pd.DataFrame(columns=_df(self._candidato_centro()).columns)
        result = selecionar_ancoras_greedy(df)
        assert result.empty

    def test_candidato_unico_retorna_uma_ancora(self):
        df = _cidade_df(self._candidato_centro())
        result = selecionar_ancoras_greedy(df, max_ancoras=5, dist_min_km=1.5)
        assert len(result) == 1

    def test_ordem_expansao_começa_em_1(self):
        df = _cidade_df(self._candidato_centro())
        result = selecionar_ancoras_greedy(df, max_ancoras=1)
        assert result["ordem_expansao_cidade"].iloc[0] == 1

    def test_duas_ancoras_proximas_retorna_apenas_uma(self):
        # H3 res7: adjacentes ~2.5 km; dist_min=3km bloqueia a segunda
        lat_n1, lng_n1 = _SP_N1_LATLNG
        df = _cidade_df(
            self._candidato_centro(),
            _row(hex_id=_SP_N1, lat=lat_n1, lng=lng_n1),
        )
        result = selecionar_ancoras_greedy(df, max_ancoras=5, dist_min_km=3.0)
        assert len(result) == 1

    def test_duas_ancoras_distantes_retorna_duas(self):
        # ring2 esta >1.5km do center → ambas podem ser selecionadas
        df = _cidade_df(self._candidato_centro(), self._candidato_ring2())
        result = selecionar_ancoras_greedy(df, max_ancoras=5, dist_min_km=1.5)
        assert len(result) == 2

    def test_max_ancoras_limita_selecao(self):
        df = _cidade_df(self._candidato_centro(), self._candidato_ring2())
        result = selecionar_ancoras_greedy(df, max_ancoras=1, dist_min_km=0.0)
        assert len(result) == 1

    def test_dist_ancora_proxima_nan_na_primeira(self):
        df = _cidade_df(self._candidato_centro())
        result = selecionar_ancoras_greedy(df, max_ancoras=1)
        assert math.isnan(result["dist_nova_ancora_mais_proxima_m"].iloc[0])

    def test_dist_ancora_proxima_positiva_na_segunda(self):
        df = _cidade_df(self._candidato_centro(), self._candidato_ring2())
        result = selecionar_ancoras_greedy(df, max_ancoras=5, dist_min_km=1.5)
        assert result["dist_nova_ancora_mais_proxima_m"].iloc[1] > 0

    def test_colunas_auditoria_presentes(self):
        df = _cidade_df(self._candidato_centro())
        result = selecionar_ancoras_greedy(df)
        for col in [
            "ordem_expansao_cidade",
            "residual_incremental_capturado",
            "residual_cluster_pos_acao",
            "dist_nova_ancora_mais_proxima_m",
            "tese_dominio",
        ]:
            assert col in result.columns, f"coluna ausente: {col}"

    def test_residual_incremental_positivo(self):
        df = _cidade_df(self._candidato_centro())
        result = selecionar_ancoras_greedy(df)
        assert result["residual_incremental_capturado"].iloc[0] > 0

    def test_residual_pos_acao_menor_que_inicial(self):
        df = _cidade_df(self._candidato_centro())
        residual_inicial = df["oferta_efetiva_disponivel"].sum()
        result = selecionar_ancoras_greedy(df)
        assert result["residual_cluster_pos_acao"].iloc[0] < residual_inicial

    def test_tese_dominio_valor_valido(self):
        teses_validas = {
            "dominar_white_space", "abrir_com_disputa", "proteger_corredor_ultra",
            "adensar_cluster", "monitorar", "bloqueado_canibalizacao",
        }
        df = _cidade_df(self._candidato_centro(), self._candidato_ring2())
        result = selecionar_ancoras_greedy(df, max_ancoras=5, dist_min_km=1.5)
        assert set(result["tese_dominio"].unique()) <= teses_validas

    def test_desempate_por_score_residual(self):
        # Dois candidatos distantes com residual igual mas scores diferentes
        # → deve selecionar o de maior score primeiro
        df = _cidade_df(
            self._candidato_centro(oferta_efetiva_disponivel=100.0, score_oportunidade_residual=80.0),
            self._candidato_ring2(oferta_efetiva_disponivel=100.0, score_oportunidade_residual=40.0),
        )
        result = selecionar_ancoras_greedy(df, max_ancoras=1, dist_min_km=0.0)
        assert result.iloc[0]["score_oportunidade_residual"] == pytest.approx(80.0)


# =============================================================================
# gerar_plano_dominio
# =============================================================================

class TestGerarPlanoDominio:
    def test_df_vazio_retorna_vazio(self):
        df = pd.DataFrame(columns=_df(_row()).columns)
        cands = filtrar_candidatos(construir_clusters(df))
        result = gerar_plano_dominio(cands)
        assert result.empty

    def test_duas_cidades_retorna_ancora_por_cidade(self):
        lat_sp, lng_sp = _SP_CENTER_LATLNG
        lat_rj, lng_rj = h3.cell_to_latlng(_RJ_HEX)
        df = _df(
            _row(hex_id=_SP_CENTER, cod_municipio="3550308", uf="SP", lat=lat_sp, lng=lng_sp),
            _row(hex_id=_RJ_HEX, cod_municipio="3304557", uf="RJ", lat=lat_rj, lng=lng_rj),
        )
        cands = filtrar_candidatos(construir_clusters(df))
        result = gerar_plano_dominio(cands, max_ancoras=5, dist_min_km=1.5)
        assert result["cod_municipio"].nunique() == 2

    def test_hex_id_sem_duplicatas(self):
        lat_c, lng_c = _SP_CENTER_LATLNG
        lat_r, lng_r = _SP_RING2_LATLNG
        df = _df(
            _row(hex_id=_SP_CENTER, lat=lat_c, lng=lng_c),
            _row(hex_id=_SP_RING2, lat=lat_r, lng=lng_r),
        )
        cands = filtrar_candidatos(construir_clusters(df))
        result = gerar_plano_dominio(cands, max_ancoras=5, dist_min_km=1.5)
        assert not result["hex_id"].duplicated().any()

    def test_todos_bloqueados_por_ultra_retorna_vazio(self):
        lat_c, lng_c = _SP_CENTER_LATLNG
        lat_r, lng_r = _SP_RING2_LATLNG
        df = _df(
            _row(hex_id=_SP_CENTER, lat=lat_c, lng=lng_c, flag_canibalizacao_ultra_1km=True),
            _row(hex_id=_SP_RING2, lat=lat_r, lng=lng_r, flag_canibalizacao_ultra_1km=True),
        )
        cands = filtrar_candidatos(construir_clusters(df))
        result = gerar_plano_dominio(cands)
        assert result.empty

    def test_multiplos_clusters_seleciona_ancoras_de_cada(self):
        # _SP_CENTER e _SP_RING2 estao a 2 hops de distancia — nao sao adjacentes
        lat_c, lng_c = _SP_CENTER_LATLNG
        lat_r, lng_r = _SP_RING2_LATLNG
        df = _df(
            _row(hex_id=_SP_CENTER, lat=lat_c, lng=lng_c),
            _row(hex_id=_SP_RING2, lat=lat_r, lng=lng_r),
        )
        cands = filtrar_candidatos(construir_clusters(df))
        if cands["cluster_id"].nunique() < 2:
            pytest.skip("hexes ficaram adjacentes neste ambiente H3")
        result = gerar_plano_dominio(cands, max_ancoras=10, dist_min_km=0.0)
        assert len(result) == 2

    def test_limite_ancoras_por_cidade_respeitado(self):
        lat_c, lng_c = _SP_CENTER_LATLNG
        lat_r, lng_r = _SP_RING2_LATLNG
        lat_n1, lng_n1 = _SP_N1_LATLNG
        df = _df(
            _row(hex_id=_SP_CENTER, lat=lat_c, lng=lng_c),
            _row(hex_id=_SP_RING2, lat=lat_r, lng=lng_r),
            _row(hex_id=_SP_N1, lat=lat_n1, lng=lng_n1),
        )
        cands = filtrar_candidatos(construir_clusters(df))
        result = gerar_plano_dominio(cands, max_ancoras=2, dist_min_km=0.0)
        for _, grp in result.groupby("cod_municipio"):
            assert len(grp) <= 2


# =============================================================================
# validate_dominio_schema
# =============================================================================

def _plano_minimo() -> pd.DataFrame:
    """DataFrame com todas as colunas obrigatórias do schema de domínio."""
    row = {col: None for col in SCHEMA_DOMINIO_OBRIGATORIO}
    row["hex_id"] = "abc"
    return pd.DataFrame([row])


class TestValidateDominioSchema:
    def test_schema_valido_nao_levanta_excecao(self):
        validate_dominio_schema(_plano_minimo())

    def test_schema_faltando_coluna_levanta_assertion(self):
        df = _plano_minimo().drop(columns=["cluster_id"])
        with pytest.raises(AssertionError, match="colunas ausentes"):
            validate_dominio_schema(df)

    def test_schema_obrigatorio_alinhado_com_constants(self):
        from motor_expansao.dashboard.constants import DOMINIO_SCHEMA_MINIMO
        assert SCHEMA_DOMINIO_OBRIGATORIO == DOMINIO_SCHEMA_MINIMO


# =============================================================================
# Guardrail: pipeline nao escreve em paths M1
# =============================================================================

class TestArtefatosM1:
    def test_saida_parquet_nao_e_artefato_m1(self):
        m1_paths = {
            SAIDA_PARQUET.parent / "carteira_expansao_acionavel.parquet",
            SAIDA_PARQUET.parent / "plano_expansao_curto_prazo.parquet",
        }
        assert SAIDA_PARQUET not in m1_paths

    def test_saida_csv_nao_sobrescreve_m1(self):
        assert "carteira" not in SAIDA_CSV.name
        assert "curto_prazo" not in SAIDA_CSV.name
