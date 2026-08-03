"""Reancoragem BLK-WEB-19 (DEC-022): `enrich_dashboard_data` sem Streamlit.

A cobertura desta funcao vivia em `tests/integration/test_streamlit_app.py` (via o reexport
`streamlit_app.enrich_dashboard_data`), que sera deletado no corte do Streamlit. Ela NAO e
so do dashboard: `pipelines/m1/fase1_bi_exports.py` usa a MESMA funcao para materializar o
parquet enriquecido particionado (`hexagonos_dashboard_enriquecido/uf=XX`) que o piloto web
le em producao — perder estes invariantes seria perder o contrato do artefato.

Invariantes reancoradas (mesmos cenarios dos testes da UI, contra a funcao pura):
score oficial M1 intocado; coalescencia hibrido > censo (e censo preenchendo lacunas);
join do censo trace trazendo as colunas de rastreabilidade; colunas obrigatorias/derivadas
sempre presentes mesmo sem camadas; dtypes canonicos (Float32/bool/categoricos ordenados);
regua de populacao (pop_cut) e injecao de `pop_total` do parquet estrutural.
"""

from __future__ import annotations

import pandas as pd

from motor_expansao.dashboard.constants import (
    COVERAGE_BUCKET_ORDER,
    FAIXA_ORDEM,
    HYBRID_ELIGIBILITY_ORDER,
    JOIN_QUALITY_ORDER,
)
from motor_expansao.dashboard.data import enrich_dashboard_data


def _base_row(hex_id: str, **overrides) -> dict:
    """Linha minima do dataset oficial M1 (REQUIRED_COLUMNS do dashboard)."""
    row = {
        "hex_id": hex_id,
        "lat": -15.0,
        "lng": -47.0,
        "uf": "DF",
        "cidade": "Brasilia",
        "regiao": "CO",
        "score_priorizacao": 90.0,
        "hex_score_estrutural": 85.0,
        "ajuste_executivo": 5.0,
        "faixa_oportunidade": "alta",
        "flag_viavel": True,
        "flag_prioridade": True,
        "rank_brasil": 1,
        "rank_uf": 1,
        "rank_cidade": 1,
        "renda_per_capita": 6000.0,
        "populacao_proxy": 18000.0,
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# Base oficial preservada + sobreposicao de rastreabilidade (hibrido > censo)
# ---------------------------------------------------------------------------


def test_enrich_preserva_base_oficial_e_sobrepoe_rastreabilidade():
    """O merge das camadas NUNCA reescreve o score oficial M1; na coalescencia o hibrido
    vence o censo (score/coverage), o censo entra apenas onde so ele tem a coluna
    (causa_outlier, metodo_join) e os labels derivados saem consistentes."""
    base_df = pd.DataFrame([_base_row("abc", score_priorizacao=98.0, hex_score_estrutural=95.0)])
    hybrid_df = pd.DataFrame(
        [
            {
                "hex_id": "abc",
                "nome_municipio": "Brasilia",
                "score_setor_2022_calibrado": 87.5,
                "score_expansao_hibrido": 98.000875,
                "top_municipio": True,
                "top_hex_intraurbano": True,
                "flag_censo_elegivel": True,
                "flag_censo_disponivel": True,
                "flag_hex_hibrido_elegivel": True,
                "top_municipio_hibrido": True,
                "rank_municipio_uf": 1,
                "rank_hex_intraurbano": 1,
                "top_oportunidade_municipio": True,
                "coverage_pct_setor_2022": 99.2,
                "qualidade_join_uf": "B",
                "flag_join_uf_restrito": False,
                "flag_baixa_pop_setor": False,
                "flag_outlier_espacial": False,
                "motivo_nao_elegivel_censo": "elegivel",
                "sam_fitness_potencial": 810.0,
                "oferta_consumida_mercado_estimada": 250.0,
                "oferta_consumida_ultra_real": 120.0,
                "oferta_efetiva_disponivel": 560.0,
                "share_ultra_estimado_hex": 0.324,
                "score_oportunidade_residual": 22.4,
                "quartil_oportunidade_residual": "Q4_maior_residual",
            }
        ]
    )
    censo_df = pd.DataFrame(
        [
            {
                "hex_id": "abc",
                "nome_municipio": "Brasilia",
                "score_setor_2022_calibrado": 88.1,
                "coverage_pct_setor_2022": 100.0,
                "qualidade_join_uf": "A",
                "flag_join_uf_restrito": False,
                "flag_baixa_pop_setor": True,
                "flag_outlier_espacial": True,
                "causa_outlier_espacial": "limiar_de_zona",
                "delta_vs_vizinhos": 36.0,
                "metodo_join_setor_2022": "posicional",
                "motivo_fallback_setor_2022": pd.NA,
                "renda_per_capita_setor_2022_calibrada": 7000.0,
            }
        ]
    )

    enriched = enrich_dashboard_data(base_df, hybrid_df, censo_df)

    assert enriched.loc[0, "score_priorizacao"] == 98.0
    assert enriched.loc[0, "score_setor_2022_calibrado"] == 87.5  # hibrido vence 88.1 do censo
    assert enriched.loc[0, "coverage_pct_setor_2022"] == 99.2
    assert bool(enriched.loc[0, "flag_outlier_espacial"]) is False  # hibrido (False) vence
    assert enriched.loc[0, "causa_outlier_espacial"] == "limiar_de_zona"  # so o censo tem
    assert enriched.loc[0, "metodo_join_setor_2022"] == "posicional"
    assert enriched.loc[0, "confianca_geografica"] == "granular"
    assert str(enriched.loc[0, "elegibilidade_hibrida"]) == "Elegivel"
    assert str(enriched.loc[0, "cobertura_censitaria_bucket"]) == "95-99,9%"
    assert str(enriched.loc[0, "qualidade_camada"]) == "B"
    assert float(enriched.loc[0, "oferta_efetiva_disponivel"]) == 560.0
    assert str(enriched.loc[0, "quartil_oportunidade_residual"]) == "Q4_maior_residual"


def test_enrich_censo_preenche_lacuna_que_o_hibrido_nao_tem():
    """Direcao da coalescencia: onde o hibrido veio NaN, o valor do censo trace entra —
    e o que garante score censitario nos hexes que o artefato hibrido ainda nao cobriu."""
    base_df = pd.DataFrame([_base_row("h1"), _base_row("h2", rank_brasil=2)])
    hybrid_df = pd.DataFrame(
        [
            {"hex_id": "h1", "score_setor_2022_calibrado": 80.0, "qualidade_join_uf": "A"},
            {"hex_id": "h2", "score_setor_2022_calibrado": None, "qualidade_join_uf": None},
        ]
    )
    censo_df = pd.DataFrame(
        [
            {"hex_id": "h1", "score_setor_2022_calibrado": 60.0, "qualidade_join_uf": "C"},
            {"hex_id": "h2", "score_setor_2022_calibrado": 65.0, "qualidade_join_uf": "B"},
        ]
    )

    enriched = enrich_dashboard_data(base_df, hybrid_df, censo_df).set_index("hex_id")

    assert float(enriched.loc["h1", "score_setor_2022_calibrado"]) == 80.0  # hibrido mantido
    assert float(enriched.loc["h2", "score_setor_2022_calibrado"]) == 65.0  # censo preencheu
    assert str(enriched.loc["h1", "qualidade_camada"]) == "A"
    assert str(enriched.loc["h2", "qualidade_camada"]) == "B"


def test_enrich_nao_altera_score_oficial_m1():
    """Guardrail do §2 do CLAUDE.md: o enriquecimento e aditivo e READ-ONLY sobre o M1 —
    score_priorizacao e hex_score_estrutural saem byte-identicos ao dataset oficial."""
    base_df = pd.DataFrame(
        [_base_row("h1", score_priorizacao=88.5, hex_score_estrutural=84.0, ajuste_executivo=4.5)]
    )

    enriched = enrich_dashboard_data(base_df)

    assert float(enriched.loc[0, "score_priorizacao"]) == 88.5
    assert float(enriched.loc[0, "hex_score_estrutural"]) == 84.0
    assert float(enriched.loc[0, "score_exibicao"]) == 88.5  # espelho de exibicao


# ---------------------------------------------------------------------------
# Regua de populacao (pop_cut) e injecao do parquet estrutural
# ---------------------------------------------------------------------------


def test_enrich_deriva_colunas_pop_cut():
    """Sem camada censitaria, a regua operacional cai no total municipal (proxy) e as tres
    colunas auditaveis do corte tem de existir no frame materializado."""
    base_df = pd.DataFrame(
        [
            _base_row("h1", populacao_proxy=15_000.0),
            _base_row("h2", populacao_proxy=3_000.0, rank_brasil=2, flag_prioridade=False),
        ]
    )

    enriched = enrich_dashboard_data(base_df).set_index("hex_id")

    for col in ("populacao_corte_hex", "fonte_populacao_corte", "flag_pop_min_5k"):
        assert col in enriched.columns
    assert bool(enriched.loc["h1", "flag_pop_min_5k"]) is True
    assert bool(enriched.loc["h2", "flag_pop_min_5k"]) is False
    assert str(enriched.loc["h1", "fonte_populacao_corte"]) == "total_municipal"
    assert float(enriched.loc["h1", "score_priorizacao"]) == 90.0


def test_enrich_usa_setor_2022_quando_granular():
    """Hex granular (join A/B + sinal de censo) corta pela populacao do SETOR 2022, nao pelo
    proxy municipal — e a preferencia que evita descartar hex denso com proxy defasado."""
    base_df = pd.DataFrame([_base_row("g1", populacao_proxy=5_000.0)])
    hybrid_df = pd.DataFrame(
        [
            {
                "hex_id": "g1",
                "nome_municipio": "Brasilia",
                "qualidade_join_uf": "A",
                "flag_censo_disponivel": True,
                "pop_total_setor_2022": 20_000.0,
                "score_setor_2022_calibrado": 88.0,
                "flag_censo_elegivel": True,
                "flag_hex_hibrido_elegivel": True,
                "coverage_pct_setor_2022": 99.0,
            }
        ]
    )

    enriched = enrich_dashboard_data(base_df, hybrid_df)

    row = enriched.loc[enriched["hex_id"] == "g1"].iloc[0]
    assert row["confianca_geografica"] == "granular"
    assert row["fonte_populacao_corte"] == "setor_2022"
    assert float(row["populacao_corte_hex"]) == 20_000.0
    assert bool(row["flag_pop_min_5k"]) is True


def test_enrich_estrutural_pop_injeta_pop_total_por_hex():
    """O parquet estrutural entra como mapa hex->pop_total (fallback municipal REAL,
    preferido ao proxy 18-45 legado); hex fora do estrutural fica NaN e cai no proxy."""
    base_df = pd.DataFrame(
        [
            _base_row("h1", populacao_proxy=3_000.0),
            _base_row("h2", populacao_proxy=3_000.0, rank_brasil=2, flag_prioridade=False),
        ]
    )
    estrutural = pd.DataFrame([{"hex_id": "h1", "pop_total": 9_500.0}])

    enriched = enrich_dashboard_data(
        base_df, pd.DataFrame(), pd.DataFrame(), estrutural_pop_df=estrutural
    ).set_index("hex_id")

    assert float(enriched.loc["h1", "pop_total"]) == 9_500.0
    assert pd.isna(enriched.loc["h2", "pop_total"])
    # A regua do corte consome o pop_total injetado (>= 5k aprova h1; h2 sem valor reprova).
    assert float(enriched.loc["h1", "populacao_corte_hex"]) == 9_500.0
    assert bool(enriched.loc["h1", "flag_pop_min_5k"]) is True
    assert bool(enriched.loc["h2", "flag_pop_min_5k"]) is False


# ---------------------------------------------------------------------------
# Contrato do artefato materializado: colunas obrigatorias, dtypes e ordenacao
# ---------------------------------------------------------------------------


def test_enrich_sem_camadas_garante_colunas_derivadas_e_defaults():
    """`fase1_bi_exports` chama a funcao mesmo quando os parquets opcionais nao existem
    (frames VAZIOS): todas as colunas derivadas precisam nascer com defaults neutros para
    o schema do artefato particionado nao variar conforme as camadas disponiveis."""
    base_df = pd.DataFrame([_base_row("h1")])

    enriched = enrich_dashboard_data(base_df, pd.DataFrame(), pd.DataFrame())

    for col in (
        "top_municipio",
        "flag_censo_elegivel",
        "flag_censo_disponivel",
        "flag_hex_hibrido_elegivel",
        "flag_outlier_espacial",
        "flag_monitoramento_prioritario",
    ):
        assert bool(enriched.loc[0, col]) is False, col
    assert str(enriched.loc[0, "elegibilidade_hibrida"]) == "Sem camada"
    assert str(enriched.loc[0, "cobertura_censitaria_bucket"]) == "Sem camada"
    assert str(enriched.loc[0, "qualidade_camada"]) == "Sem camada"
    assert enriched.loc[0, "confianca_geografica"] == "municipal"
    # Texto de rastreabilidade ausente vira o placeholder canonico (categorico).
    assert str(enriched.loc[0, "causa_outlier_espacial"]) == "Não informado"
    # Colunas de conveniencia da exibicao sempre presentes.
    assert enriched.loc[0, "UF"] == "DF"
    assert enriched.loc[0, "nome_municipio"] == "Brasilia"  # fallback cidade


def test_enrich_dtypes_canonicos_do_artefato():
    """Os dtypes sao parte do contrato do parquet enriquecido (o reader do piloto le o que
    for gravado): floats em Float32, flags em bool e os eixos de filtro em categoricos
    ORDENADOS com o vocabulario canonico das constantes."""
    base_df = pd.DataFrame([_base_row("h1")])

    enriched = enrich_dashboard_data(base_df, pd.DataFrame(), pd.DataFrame())

    for col in ("score_priorizacao", "renda_per_capita", "populacao_proxy", "rank_brasil"):
        assert str(enriched[col].dtype) == "Float32", col
    for col in ("flag_viavel", "flag_prioridade", "flag_pop_min_5k"):
        assert enriched[col].dtype == bool, col

    faixa = enriched["faixa_oportunidade"]
    assert isinstance(faixa.dtype, pd.CategoricalDtype) and faixa.cat.ordered
    assert list(faixa.cat.categories) == FAIXA_ORDEM + ["Não informado"]
    assert list(enriched["elegibilidade_hibrida"].cat.categories) == HYBRID_ELIGIBILITY_ORDER
    assert list(enriched["cobertura_censitaria_bucket"].cat.categories) == COVERAGE_BUCKET_ORDER
    assert list(enriched["qualidade_camada"].cat.categories) == JOIN_QUALITY_ORDER


def test_enrich_ordena_por_prioridade_do_mapa():
    """A ordenacao (prioridade > viavel > score desc) e aplicada no enrich e materializada
    no parquet — e ela que faz o downsample do mapa manter os top-N sem reordenar na leitura."""
    base_df = pd.DataFrame(
        [
            _base_row("frio", score_priorizacao=99.0, flag_prioridade=False, flag_viavel=False, rank_brasil=3),
            _base_row("quente_menor", score_priorizacao=70.0, rank_brasil=2),
            _base_row("quente_maior", score_priorizacao=80.0, rank_brasil=1),
        ]
    )

    enriched = enrich_dashboard_data(base_df)

    assert enriched["hex_id"].tolist() == ["quente_maior", "quente_menor", "frio"]
