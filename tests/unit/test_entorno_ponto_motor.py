"""Reancoragem BLK-WEB-19 (DEC-022): invariantes de `analisar_entorno_ponto`.

Estes cenarios existiam apenas via tests/integration/test_streamlit_app.py
(que sera deletado no corte da DEC-022). Aqui os mesmos invariantes sao
verificados DIRETAMENTE contra a funcao pura do motor compartilhado, sem
streamlit e sem dados em disco: todos os DataFrames sao sinteticos.

Nota: lookup_hex_by_coord, parse_coordinate_input e _validate_brazil_bbox ja
tem cobertura hermetica em tests/unit/test_coord_search.py — nao duplicar aqui.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from motor_expansao.dashboard.data import analisar_entorno_ponto, haversine_km

# Centro de referencia (Sao Paulo) usado em todos os cenarios: os offsets em
# graus de latitude viram distancias conhecidas (~0.01 grau ≈ 1.11 km), o que
# permite controlar quem cai dentro/fora do raio default de 1.6 km.
LAT_C, LNG_C = -23.5, -46.6


# ── haversine_km (nucleo geometrico do raio) ─────────────────────────────────


def test_haversine_zero_para_o_mesmo_ponto():
    """Distancia de um ponto a ele mesmo deve ser 0 — ancora o corte `<= raio`."""
    dist = haversine_km(LAT_C, np.array([LAT_C]), LNG_C, np.array([LNG_C]))
    assert float(dist[0]) == pytest.approx(0.0, abs=1e-6)


def test_haversine_distancia_conhecida_sp_rj():
    """SP (~-23.55,-46.63) a RJ (~-22.90,-43.17) ≈ 360 km: sanidade da formula."""
    dist = haversine_km(-23.55, np.array([-22.90]), -46.63, np.array([-43.17]))
    assert 340 < float(dist[0]) < 380


# ── estrutura vazia e casos de borda de entrada ──────────────────────────────


def test_entorno_sem_dados_retorna_estrutura_vazia():
    """DataFrame vazio nao pode quebrar a analise: retorna dict completo zerado."""
    result = analisar_entorno_ponto(LAT_C, LNG_C, pd.DataFrame())
    assert result["n_hexes"] == 0
    assert result["residual_total"] is None
    assert result["raio_km"] == pytest.approx(1.6)
    assert result["area_km2"] == pytest.approx(3.14159265358979 * 1.6**2, abs=0.01)
    assert result["hexes_entorno"].empty
    assert result["fonte_pop_total_raio"] == "ausente"
    assert result["metodo_renda_raio"] == "ausente"


def test_entorno_hex_df_sem_lat_lng_ainda_conta_pins():
    """Base de hexes sem lat/lng nao inviabiliza a contagem de pins no raio."""
    hex_df = pd.DataFrame([{"hex_id": "h1", "score_priorizacao": 80.0}])
    competitors = pd.DataFrame([{"rede": "smart_fit", "lat": LAT_C, "lng": LNG_C}])
    result = analisar_entorno_ponto(LAT_C, LNG_C, hex_df, competitors_df=competitors)
    assert result["n_hexes"] == 0
    assert result["n_concorrentes"] == 1


def test_entorno_hex_df_none_retorna_estrutura_vazia():
    """hex_df=None (dataset ausente na sessao) segue o mesmo caminho do vazio."""
    result = analisar_entorno_ponto(LAT_C, LNG_C, None)
    assert result["n_hexes"] == 0
    assert result["hexes_entorno"].empty


def test_entorno_raio_sem_vizinhos_zera_agregados():
    """Todos os hexes fora do raio: agregados None e hexes_entorno vazio."""
    df = pd.DataFrame([
        {
            "hex_id": "longe",
            "lat": LAT_C - 0.05,  # ~5.5 km, fora de 1.6 km
            "lng": LNG_C,
            "oferta_efetiva_disponivel": 500.0,
            "score_priorizacao": 90.0,
        }
    ])
    result = analisar_entorno_ponto(LAT_C, LNG_C, df, raio_km=1.6)
    assert result["n_hexes"] == 0
    assert result["hexes_entorno"].empty
    assert result["residual_total"] is None
    assert result["score_m1_medio"] is None
    assert result["pop_total_raio"] is None


def test_entorno_area_reflete_raio_customizado():
    """area_km2 deve acompanhar o raio informado (pi * r^2), nao o default."""
    result = analisar_entorno_ponto(LAT_C, LNG_C, pd.DataFrame(), raio_km=3.0)
    assert result["raio_km"] == pytest.approx(3.0)
    assert result["area_km2"] == pytest.approx(3.14159265358979 * 3.0**2, abs=0.01)


# ── selecao por raio e ordenacao ─────────────────────────────────────────────


def test_entorno_inclui_hex_proximo_e_exclui_distante():
    """So o hex dentro do raio entra nos agregados; o distante nao contamina."""
    df = pd.DataFrame([
        {
            "hex_id": "near", "lat": LAT_C, "lng": LNG_C,
            "score_priorizacao": 80.0, "oferta_efetiva_disponivel": 500.0,
            "score_oportunidade_residual": 40.0,
        },
        {
            "hex_id": "far", "lat": LAT_C - 0.05, "lng": LNG_C,  # ~5.5 km
            "score_priorizacao": 90.0, "oferta_efetiva_disponivel": 200.0,
            "score_oportunidade_residual": 60.0,
        },
    ])
    result = analisar_entorno_ponto(LAT_C, LNG_C, df, raio_km=1.6)
    assert result["n_hexes"] == 1
    assert result["hexes_entorno"].iloc[0]["hex_id"] == "near"
    assert result["residual_total"] == pytest.approx(500.0)
    assert result["score_m1_medio"] == pytest.approx(80.0)
    assert result["score_residual_medio"] == pytest.approx(40.0)


def test_entorno_com_hexes_h3_reais_vizinhos():
    """Malha H3 real (res 8): centro + anel 1 caem no raio, anel 4 fica fora.

    Usa centroides H3 verdadeiros para garantir que a geometria do raio
    funciona com a malha usada em producao, nao apenas com offsets sinteticos.
    """
    import h3

    center = h3.latlng_to_cell(LAT_C, LNG_C, 8)
    dentro = list(h3.grid_disk(center, 1))       # centro + 6 vizinhos (~0.8 km)
    fora = list(h3.grid_ring(center, 4))         # anel a ~3.2 km, fora de 1.6

    def _rows(hex_ids: list[str], residual: float) -> list[dict]:
        rows = []
        for hex_id in hex_ids:
            lat, lng = h3.cell_to_latlng(hex_id)
            rows.append({
                "hex_id": hex_id, "lat": lat, "lng": lng,
                "oferta_efetiva_disponivel": residual,
            })
        return rows

    df = pd.DataFrame(_rows(dentro, 100.0) + _rows(fora, 999.0))
    lat_q, lng_q = h3.cell_to_latlng(center)
    result = analisar_entorno_ponto(lat_q, lng_q, df, raio_km=1.6)

    assert result["n_hexes"] == len(dentro) == 7
    assert set(result["hexes_entorno"]["hex_id"]) == set(dentro)
    # residual soma apenas os 7 hexes do raio (o anel distante nao entra)
    assert result["residual_total"] == pytest.approx(700.0)


def test_entorno_dois_hexes_no_raio_ordenados_por_distancia():
    """hexes_entorno vem ordenado por distancia ascendente, independente da ordem do df."""
    df = pd.DataFrame([
        {
            "hex_id": "b", "lat": LAT_C - 0.01, "lng": LNG_C,  # ~1.11 km
            "score_priorizacao": 75.0, "oferta_efetiva_disponivel": 300.0,
            "score_oportunidade_residual": 30.0,
        },
        {
            "hex_id": "a", "lat": LAT_C, "lng": LNG_C,  # dist 0
            "score_priorizacao": 82.0, "oferta_efetiva_disponivel": 700.0,
            "score_oportunidade_residual": 70.0,
        },
    ])
    result = analisar_entorno_ponto(LAT_C, LNG_C, df, raio_km=1.6)
    assert result["n_hexes"] == 2
    assert result["hexes_entorno"].iloc[0]["hex_id"] == "a"
    assert result["residual_total"] == pytest.approx(1000.0)
    assert result["score_m1_max"] == pytest.approx(82.0)
    assert result["score_m1_medio"] == pytest.approx(78.5)


# ── contagem de pins (concorrentes / ultra / ancoras) ────────────────────────


def test_entorno_conta_concorrentes_ultra_e_ancoras_no_raio():
    """Cada camada de pins conta apenas os pontos dentro do raio."""
    hex_df = pd.DataFrame([
        {"hex_id": "h1", "lat": LAT_C, "lng": LNG_C, "score_priorizacao": 80.0},
    ])
    competitors = pd.DataFrame([
        {"rede": "smart_fit", "lat": LAT_C + 0.005, "lng": LNG_C},  # ~0.55 km, dentro
        {"rede": "bluefit", "lat": LAT_C - 0.1, "lng": LNG_C},      # ~11 km, fora
    ])
    ultra = pd.DataFrame([
        {"nome_unidade": "Ultra A", "lat": LAT_C, "lng": LNG_C + 0.003},  # dentro
        {"nome_unidade": "Ultra B", "lat": LAT_C + 0.08, "lng": LNG_C},   # fora
    ])
    dominio = pd.DataFrame([
        {"hex_id": "d1", "lat": LAT_C + 0.01, "lng": LNG_C},  # ~1.11 km, dentro
        {"hex_id": "d2", "lat": LAT_C + 0.03, "lng": LNG_C},  # ~3.3 km, fora
    ])
    result = analisar_entorno_ponto(
        LAT_C, LNG_C, hex_df, raio_km=1.6,
        competitors_df=competitors, ultra_df=ultra, dominio_df=dominio,
    )
    assert result["n_concorrentes"] == 1
    assert result["n_ultra"] == 1
    assert result["n_ancoras_dominio"] == 1


def test_entorno_pins_sem_lat_lng_ou_none_contam_zero():
    """Camadas de pins ausentes ou sem coordenadas degradam para contagem 0."""
    hex_df = pd.DataFrame([{"hex_id": "h1", "lat": LAT_C, "lng": LNG_C}])
    sem_coords = pd.DataFrame([{"rede": "smart_fit", "cidade": "Sao Paulo"}])
    result = analisar_entorno_ponto(
        LAT_C, LNG_C, hex_df, raio_km=1.6,
        competitors_df=sem_coords, ultra_df=None, dominio_df=pd.DataFrame(),
    )
    assert result["n_concorrentes"] == 0
    assert result["n_ultra"] == 0
    assert result["n_ancoras_dominio"] == 0


# ── populacao: cascata de fontes ─────────────────────────────────────────────


def test_entorno_prefere_populacao_setor_2022():
    """Com todas as fontes presentes, vence pop_total_setor_2022 (fonte oficial)."""
    df = pd.DataFrame([
        {
            "hex_id": "h1", "lat": LAT_C, "lng": LNG_C,
            "pop_total_setor_2022": 1200, "pop_hex_base": 9000,
            "pop_total": 8000, "populacao_proxy": 7000,
            "renda_per_capita_setor_2022_calibrada": 2500,
        },
        {
            "hex_id": "h2", "lat": LAT_C + 0.005, "lng": LNG_C,
            "pop_total_setor_2022": 800, "pop_hex_base": 6000,
            "pop_total": 5000, "populacao_proxy": 4000,
            "renda_per_capita_setor_2022_calibrada": 3500,
        },
    ])
    result = analisar_entorno_ponto(LAT_C, LNG_C, df, raio_km=1.6)
    assert result["pop_total_raio"] == pytest.approx(2000.0)
    assert result["fonte_pop_total_raio"] == "setor_2022"
    assert result["n_hexes_com_pop"] == 2
    hexes = result["hexes_entorno"].set_index("hex_id")
    assert hexes.loc["h1", "pop_total_raio_hex"] == pytest.approx(1200.0)
    assert hexes.loc["h1", "fonte_pop_total_raio_hex"] == "setor_2022"


def test_entorno_fallback_populacao_misto():
    """Cada hex cai numa fonte diferente: soma vale e a origem fica auditavel."""
    df = pd.DataFrame([
        {"hex_id": "h1", "lat": LAT_C, "lng": LNG_C, "pop_hex_base": 1500},
        {"hex_id": "h2", "lat": LAT_C + 0.005, "lng": LNG_C, "pop_total": 2500},
        {"hex_id": "h3", "lat": LAT_C + 0.006, "lng": LNG_C, "populacao_proxy": 3500},
    ])
    result = analisar_entorno_ponto(LAT_C, LNG_C, df, raio_km=1.6)
    assert result["pop_total_raio"] == pytest.approx(7500.0)
    assert result["fonte_pop_total_raio"] == "misto: pop_hex_base, pop_total, populacao_proxy"
    assert result["n_hexes_com_pop"] == 3


# ── renda: ponderacao e fallback ─────────────────────────────────────────────


def test_entorno_calcula_renda_ponderada_por_populacao():
    """Com populacao valida, a renda media do raio e ponderada por populacao."""
    df = pd.DataFrame([
        {
            "hex_id": "h1", "lat": LAT_C, "lng": LNG_C,
            "pop_total_setor_2022": 100,
            "renda_per_capita_setor_2022_calibrada": 1000,
            "renda_per_capita": 9000,
        },
        {
            "hex_id": "h2", "lat": LAT_C + 0.005, "lng": LNG_C,
            "pop_total_setor_2022": 300,
            "renda_per_capita_setor_2022_calibrada": 3000,
            "renda_per_capita": 8000,
        },
    ])
    result = analisar_entorno_ponto(LAT_C, LNG_C, df, raio_km=1.6)
    # (100*1000 + 300*3000) / 400 = 2500 — a coluna calibrada vence a generica
    assert result["renda_per_capita_media_raio"] == pytest.approx(2500.0)
    assert result["metodo_renda_raio"] == "ponderada_populacao"
    assert result["n_hexes_com_renda"] == 2


def test_entorno_usa_media_simples_de_renda_sem_populacao():
    """Sem nenhuma fonte de populacao, degrada para media simples explicita."""
    df = pd.DataFrame([
        {"hex_id": "h1", "lat": LAT_C, "lng": LNG_C, "renda_per_capita": 2000},
        {"hex_id": "h2", "lat": LAT_C + 0.005, "lng": LNG_C, "renda_per_capita": 4000},
    ])
    result = analisar_entorno_ponto(LAT_C, LNG_C, df, raio_km=1.6)
    assert result["pop_total_raio"] is None
    assert result["fonte_pop_total_raio"] == "ausente"
    assert result["renda_per_capita_media_raio"] == pytest.approx(3000.0)
    assert result["metodo_renda_raio"] == "media_simples"


def test_entorno_sem_colunas_pop_renda_sinaliza_ausente():
    """Parquet legado sem pop/renda: valores None e fontes marcadas como ausentes."""
    df = pd.DataFrame([{"hex_id": "h1", "lat": LAT_C, "lng": LNG_C}])
    result = analisar_entorno_ponto(LAT_C, LNG_C, df, raio_km=1.6)
    assert result["pop_total_raio"] is None
    assert result["fonte_pop_total_raio"] == "ausente"
    assert result["renda_per_capita_media_raio"] is None
    assert result["metodo_renda_raio"] == "ausente"


# ── residual, consumo e scores opcionais ─────────────────────────────────────


def test_entorno_sem_colunas_residual_retorna_none():
    """Dataset sem camada residual: n_hexes conta, mas residual/score ficam None."""
    df = pd.DataFrame([
        {"hex_id": "h1", "lat": LAT_C, "lng": LNG_C, "score_priorizacao": 80.0},
    ])
    result = analisar_entorno_ponto(LAT_C, LNG_C, df)
    assert result["n_hexes"] == 1
    assert result["residual_total"] is None
    assert result["score_residual_medio"] is None


def test_entorno_retorna_consumo_quando_colunas_presentes():
    """Colunas de consumo fitness presentes viram totais do raio."""
    df = pd.DataFrame([{
        "hex_id": "h1", "lat": LAT_C, "lng": LNG_C,
        "oferta_efetiva_disponivel": 500.0,
        "oferta_consumida_mercado_estimada": 1200.0,
        "oferta_consumida_ultra_real": 300.0,
    }])
    result = analisar_entorno_ponto(LAT_C, LNG_C, df, raio_km=1.6)
    assert result["consumo_concorrentes_raio"] == pytest.approx(1200.0)
    assert result["consumo_ultra_raio"] == pytest.approx(300.0)


def test_entorno_consumo_none_quando_colunas_ausentes():
    """Sem colunas de consumo, o resultado sinaliza None (nao 0, que enganaria)."""
    df = pd.DataFrame([{
        "hex_id": "h1", "lat": LAT_C, "lng": LNG_C,
        "oferta_efetiva_disponivel": 500.0,
    }])
    result = analisar_entorno_ponto(LAT_C, LNG_C, df, raio_km=1.6)
    assert result["consumo_concorrentes_raio"] is None
    assert result["consumo_ultra_raio"] is None


def test_entorno_consumo_soma_apenas_hexes_no_raio():
    """O hex fora do raio nao contamina os totais de consumo."""
    df = pd.DataFrame([
        {
            "hex_id": "h1", "lat": LAT_C, "lng": LNG_C,
            "oferta_consumida_mercado_estimada": 800.0,
            "oferta_consumida_ultra_real": 200.0,
        },
        {
            "hex_id": "h2", "lat": LAT_C + 0.005, "lng": LNG_C,
            "oferta_consumida_mercado_estimada": 400.0,
            "oferta_consumida_ultra_real": 100.0,
        },
        {
            "hex_id": "h3", "lat": LAT_C - 0.05, "lng": LNG_C,  # fora do raio
            "oferta_consumida_mercado_estimada": 999.0,
            "oferta_consumida_ultra_real": 999.0,
        },
    ])
    result = analisar_entorno_ponto(LAT_C, LNG_C, df, raio_km=1.6)
    assert result["consumo_concorrentes_raio"] == pytest.approx(1200.0)
    assert result["consumo_ultra_raio"] == pytest.approx(300.0)


def test_entorno_agrega_score_hibrido_quando_presente():
    """score_expansao_hibrido presente gera medio/max proprios no resultado."""
    df = pd.DataFrame([
        {"hex_id": "h1", "lat": LAT_C, "lng": LNG_C, "score_expansao_hibrido": 60.0},
        {"hex_id": "h2", "lat": LAT_C + 0.005, "lng": LNG_C, "score_expansao_hibrido": 80.0},
    ])
    result = analisar_entorno_ponto(LAT_C, LNG_C, df, raio_km=1.6)
    assert result["score_hibrido_medio"] == pytest.approx(70.0)
    assert result["score_hibrido_max"] == pytest.approx(80.0)


# ── invariantes de nao-mutacao (protege artefatos oficiais do M1) ────────────


def test_entorno_nao_muta_dataframe_input():
    """A analise e somente leitura: shape, colunas e valores do df intactos."""
    df = pd.DataFrame([{
        "hex_id": "h1", "lat": LAT_C, "lng": LNG_C,
        "score_priorizacao": 80.0, "oferta_efetiva_disponivel": 500.0,
        "score_oportunidade_residual": 40.0,
    }])
    original_cols = list(df.columns)
    original_shape = df.shape
    original_score = float(df.loc[0, "score_priorizacao"])

    analisar_entorno_ponto(LAT_C, LNG_C, df, raio_km=1.6)

    assert list(df.columns) == original_cols
    assert df.shape == original_shape
    assert float(df.loc[0, "score_priorizacao"]) == original_score


def test_score_priorizacao_nao_alterado_pela_analise():
    """score_priorizacao dos dados originais e identico antes e depois da analise."""
    df = pd.DataFrame([
        {"hex_id": "h1", "lat": LAT_C, "lng": LNG_C, "score_priorizacao": 88.5},
        {"hex_id": "h2", "lat": LAT_C - 0.1, "lng": LNG_C, "score_priorizacao": 72.3},
    ])
    scores_antes = df["score_priorizacao"].tolist()

    analisar_entorno_ponto(LAT_C, LNG_C, df, raio_km=1.6)

    assert df["score_priorizacao"].tolist() == scores_antes
