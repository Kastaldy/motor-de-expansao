import json
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import pytest

import streamlit_app
from motor_expansao.dashboard.components import (
    _DISCARDED_FILL,
    _NAN_SCORE_FILL,
    _apply_pop_cut_colors,
    _hybrid_compact_tooltip,
    _shared_map_tooltip,
)
from motor_expansao.dashboard.constants import (
    COLOR_MODE_IDS,
    COLOR_MODES,
    COMPETITOR_CLUSTER_LIMIT,
    COMPETITOR_CLUSTER_RES,
    COMPETITOR_CLUSTER_TOP_REDES,
    COMPETITOR_PIN_LIMIT,
    DOMINIO_SCHEMA_MINIMO,
    HYBRID_LOAD_COLS,
    OVERLAY_IDS,
    REQUIRED_COLUMNS,
    color_mode_available,
    overlay_available,
)

# Celulas H3 res-7 reais (a validacao de schema do load rejeita hex_id nao-H3).
_HEX_SP1 = h3.latlng_to_cell(-23.55, -46.63, 7)
_HEX_SP2 = h3.latlng_to_cell(-22.90, -47.06, 7)  # Campinas
_HEX_RJ1 = h3.latlng_to_cell(-22.91, -43.17, 7)


def _write_dashboard_parquet(root: Path, rows: list[dict[str, object]]) -> Path:
    path = root / "hexagonos_brasil_dashboard.parquet"
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path


@pytest.fixture
def local_tmp_dir():
    root = Path("fixtures") / "_tmp_codex_tests_streamlit"
    root.mkdir(parents=True, exist_ok=True)
    yield root


def test_load_data_prepara_aliases_e_score_oficial(local_tmp_dir, monkeypatch):
    path = _write_dashboard_parquet(
        local_tmp_dir,
        [
            {
                "hex_id": _HEX_SP1,
                "lat": -23.55,
                "lng": -46.63,
                "uf": "SP",
                "cidade": "Sao Paulo",
                "regiao": "SE",
                "score_priorizacao": 81.0,
                "hex_score_estrutural": 77.0,
                "ajuste_executivo": 4.0,
                "faixa_oportunidade": "alta",
                "flag_viavel": True,
                "flag_prioridade": True,
                "rank_brasil": 1,
                "rank_uf": 1,
                "rank_cidade": 1,
                "renda_per_capita": 5200.0,
                "populacao_proxy": 16000.0,
            }
        ],
    )
    monkeypatch.setattr(streamlit_app, "DATASET_PATH", path)
    streamlit_app.load_data.clear()

    df = streamlit_app.load_data()

    assert df.loc[0, "score_exibicao"] == 81.0
    assert df.loc[0, "UF"] == "SP"
    assert df.loc[0, "nome_municipio"] == "Sao Paulo"
    assert str(df.loc[0, "faixa_oportunidade"]) == "alta"


def test_load_data_falha_sem_colunas_obrigatorias(local_tmp_dir, monkeypatch):
    path = _write_dashboard_parquet(
        local_tmp_dir,
        [
            {
                "hex_id": "a",
                "lat": -23.55,
                "lng": -46.63,
                "uf": "SP",
            }
        ],
    )
    monkeypatch.setattr(streamlit_app, "DATASET_PATH", path)
    streamlit_app.load_data.clear()

    with pytest.raises(ValueError, match="colunas obrigatorias"):
        streamlit_app.load_data()


def test_apply_global_filters_respeita_uf_cidade_e_faixa():
    df = pd.DataFrame(
        [
            {"uf": "SP", "cidade": "Sao Paulo", "faixa_oportunidade": "alta"},
            {"uf": "SP", "cidade": "Campinas", "faixa_oportunidade": "media"},
            {"uf": "RJ", "cidade": "Rio de Janeiro", "faixa_oportunidade": "alta"},
        ]
    )

    filtered = streamlit_app.apply_global_filters(
        df,
        selected_ufs=["SP"],
        selected_cities=["Campinas"],
        selected_faixas=["media"],
    )

    assert len(filtered) == 1
    assert filtered.iloc[0]["cidade"] == "Campinas"


def test_apply_global_filters_respeita_campos_hibridos():
    df = pd.DataFrame(
        [
            {
                "uf": "DF",
                "nome_municipio": "Brasilia",
                "faixa_oportunidade": "alta",
                "elegibilidade_hibrida": "Elegivel",
                "cobertura_censitaria_bucket": "95-99,9%",
                "qualidade_camada": "A",
                "top_municipio": True,
                "top_hex_intraurbano": False,
            },
            {
                "uf": "SP",
                "nome_municipio": "Sao Paulo",
                "faixa_oportunidade": "alta",
                "elegibilidade_hibrida": "Nao elegivel",
                "cobertura_censitaria_bucket": "<85%",
                "qualidade_camada": "C",
                "top_municipio": True,
                "top_hex_intraurbano": True,
            },
        ]
    )

    filtered = streamlit_app.apply_global_filters(
        df,
        selected_ufs=[],
        selected_cities=[],
        selected_faixas=["alta"],
        selected_hybrid_eligibility=["Elegivel"],
        selected_coverage_buckets=["95-99,9%"],
        selected_join_quality=["A"],
        only_top_municipio=True,
        only_top_hex_intraurbano=False,
    )

    assert len(filtered) == 1
    assert filtered.iloc[0]["nome_municipio"] == "Brasilia"


def test_build_kpis_aplica_desempate_oficial_para_uf_e_cidade():
    df = pd.DataFrame(
        [
            {"flag_viavel": True, "flag_prioridade": True},
            {"flag_viavel": True, "flag_prioridade": False},
            {"flag_viavel": False, "flag_prioridade": True},
        ]
    )
    city_summary = pd.DataFrame(
        [
            {"uf": "RJ", "cidade": "Niteroi", "score_medio": 90.0, "melhor_rank_brasil": 3},
            {"uf": "SP", "cidade": "Campinas", "score_medio": 90.0, "melhor_rank_brasil": 1},
        ]
    )
    uf_summary = pd.DataFrame(
        [
            {"uf": "RJ", "oportunidades_viaveis": 2, "score_medio": 80.0},
            {"uf": "SP", "oportunidades_viaveis": 2, "score_medio": 82.0},
        ]
    )

    kpis = streamlit_app.build_kpis(df, city_summary, uf_summary)

    assert kpis["total_oportunidades_viaveis"] == "2"
    assert kpis["total_hexagonos_priorizados"] == "2"
    assert kpis["uf_lider_oportunidades"] == "SP"
    assert kpis["cidade_lider_score"] == "Campinas / SP"


def test_build_hybrid_kpis_conta_municipios_unicos():
    hdf = pd.DataFrame(
        [
            {
                "uf": "DF",
                "nome_municipio": "Brasilia",
                "top_municipio_hibrido": True,
                "flag_censo_disponivel": True,
                "flag_hex_hibrido_elegivel": True,
                "flag_monitoramento_prioritario": True,
                "flag_prioridade": True,
            },
            {
                "uf": "DF",
                "nome_municipio": "Brasilia",
                "top_municipio_hibrido": True,
                "flag_censo_disponivel": True,
                "flag_hex_hibrido_elegivel": True,
                "flag_monitoramento_prioritario": False,
                "flag_prioridade": False,
            },
            {
                "uf": "GO",
                "nome_municipio": "Goiania",
                "top_municipio_hibrido": False,
                "flag_censo_disponivel": True,
                "flag_hex_hibrido_elegivel": False,
                "flag_monitoramento_prioritario": True,
                "flag_prioridade": True,
            },
        ]
    )

    kpis = streamlit_app.build_hybrid_kpis(hdf)

    assert kpis["municipios_elegiveis"] == "1"
    assert kpis["hexes_elegiveis"] == "2"
    assert kpis["municipios_cobertos"] == "2"
    assert kpis["registros_monitoramento"] == "2"
    assert kpis["comparativo_m1_hibrido"] == "2 -> 2"


def test_enrich_dashboard_data_preserva_base_oficial_e_sobrepoe_rastreabilidade():
    base_df = pd.DataFrame(
        [
            {
                "hex_id": "abc",
                "lat": -15.0,
                "lng": -47.0,
                "uf": "DF",
                "cidade": "Brasilia",
                "regiao": "CO",
                "score_priorizacao": 98.0,
                "hex_score_estrutural": 95.0,
                "ajuste_executivo": 3.0,
                "faixa_oportunidade": "alta",
                "flag_viavel": True,
                "flag_prioridade": True,
                "rank_brasil": 1,
                "rank_uf": 1,
                "rank_cidade": 1,
                "renda_per_capita": 6500.0,
                "populacao_proxy": 18000.0,
            }
        ]
    )
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

    enriched = streamlit_app.enrich_dashboard_data(base_df, hybrid_df, censo_df)

    assert enriched.loc[0, "score_priorizacao"] == 98.0
    assert enriched.loc[0, "score_setor_2022_calibrado"] == 87.5
    assert enriched.loc[0, "coverage_pct_setor_2022"] == 99.2
    assert bool(enriched.loc[0, "flag_outlier_espacial"]) is False
    assert enriched.loc[0, "causa_outlier_espacial"] == "limiar_de_zona"
    assert enriched.loc[0, "metodo_join_setor_2022"] == "posicional"
    assert enriched.loc[0, "confianca_geografica"] == "granular"
    assert str(enriched.loc[0, "elegibilidade_hibrida"]) == "Elegivel"
    assert str(enriched.loc[0, "cobertura_censitaria_bucket"]) == "95-99,9%"
    assert str(enriched.loc[0, "qualidade_camada"]) == "B"
    assert float(enriched.loc[0, "oferta_efetiva_disponivel"]) == 560.0
    assert str(enriched.loc[0, "quartil_oportunidade_residual"]) == "Q4_maior_residual"


def test_build_map_scope_caption_reflete_todos_os_hexes_da_uf():
    caption = streamlit_app.build_map_scope_caption(1234, selected_ufs=["SP"])

    assert "todos os hexagonos validos da UF selecionada" in caption
    assert "100 melhores" not in caption
    assert "1.234" in caption
    # BLK-UI-02 (#3a): ramo nao-capped orienta filtrar por municipio para densidade total.
    assert "municipio" in caption


def test_map_tooltips_tem_css_de_tamanho():
    # BLK-UI-03 (D2): meio-termo entre o 11px do BLK-UI-02 e o default deck.gl;
    # ambos os tooltips compartilham fontSize/padding/maxWidth/lineHeight no style.
    for tooltip in (_shared_map_tooltip(), _hybrid_compact_tooltip()):
        style = tooltip["style"]
        assert style["fontSize"] == "13px"
        assert style["padding"] == "8px 10px"
        assert style["maxWidth"] == "300px"
        assert style["lineHeight"] == "1.35"


def test_censo_score_to_color_delega_para_score_band_to_color():
    # _censo_score_to_color agora delega para score_band_to_color (10-band)
    # score=60 → faixa 60-70 → #96D250 → [150, 210, 80, 170]
    assert streamlit_app._censo_score_to_color(60) == streamlit_app.score_band_to_color(60)


def test_faixa_alta_usa_amarelo_no_mapa_e_na_legenda():
    assert streamlit_app.FAIXA_COLORS["alta"] == "#F59E0B"
    assert streamlit_app.hex_to_rgba(streamlit_app.FAIXA_COLORS["alta"], 140) == [245, 158, 11, 140]


def test_load_competitors_ignora_skyfit(tmp_path):
    (tmp_path / "unidades_smart_fit.csv").write_text(
        "nome_unidade;latitude;longitude;data_coleta\n"
        "Augusta;-23.5572558791;-46.6591845018;2026-04-22\n",
        encoding="utf-8",
    )
    (tmp_path / "SkyFit_unidades_geocodificado.csv").write_text(
        "NOMENCLATURA UNIDADE;CIDADE;ESTADO;latitude;longitude;geocoding_status\n"
        "SKYFIT TAQUARA;RIO DE JANEIRO;RJ;-22.9236315;-43.3750906;OK\n",
        encoding="utf-8-sig",
    )
    competitors = streamlit_app.load_competitor_points(tmp_path)
    assert "skyfit" not in set(competitors["rede"])
    assert "smart_fit" in set(competitors["rede"])


def test_load_competitors_carrega_multiplas_planilhas(tmp_path):
    (tmp_path / "unidades_smart_fit.csv").write_text(
        "nome_unidade;latitude;longitude;data_coleta\n"
        "Augusta;-23.5572558791;-46.6591845018;2026-04-22\n",
        encoding="utf-8",
    )
    (tmp_path / "unidades_bluefit.csv").write_text(
        "nome_unidade;latitude;longitude;data_coleta\n"
        "Blue Rio;-22.90;-43.20;2026-04-22\n",
        encoding="utf-8",
    )
    (tmp_path / "unidades_26fit.csv").write_text(
        "nome_unidade;latitude;longitude;data_coleta\n"
        "Alegrete;-29.781996;-55.793823;2026-04-29\n",
        encoding="utf-8",
    )
    competitors = streamlit_app.load_competitor_points(tmp_path)
    assert set(competitors["rede"]) == {"smart_fit", "bluefit", "26fit"}
    assert len(competitors) == 3


def test_build_map_figure_mostra_todos_os_hexes_validos_da_uf_sem_cap_editorial():
    df = pd.DataFrame(
        [
            {
                "hex_id": "sp_granular_1",
                "lat": -23.55,
                "lng": -46.63,
                "cidade": "Sao Paulo",
                "nome_municipio": "Sao Paulo",
                "uf": "SP",
                "faixa_oportunidade": "alta",
                "score_priorizacao": 98.0,
                "hex_score_estrutural": 92.0,
                "flag_viavel": True,
                "flag_prioridade": True,
                "score_setor_2022_calibrado": 88.0,
                "coverage_pct_setor_2022": 97.0,
                "qualidade_join_uf": "A",
                "flag_censo_disponivel": True,
            },
            {
                "hex_id": "sp_granular_1",
                "lat": -23.55,
                "lng": -46.63,
                "cidade": "Sao Paulo",
                "nome_municipio": "Sao Paulo",
                "uf": "SP",
                "faixa_oportunidade": "alta",
                "score_priorizacao": 98.0,
                "hex_score_estrutural": 92.0,
                "flag_viavel": True,
                "flag_prioridade": True,
                "score_setor_2022_calibrado": 88.0,
                "coverage_pct_setor_2022": 97.0,
                "qualidade_join_uf": "A",
                "flag_censo_disponivel": True,
            },
            {
                "hex_id": "sp_granular_2",
                "lat": -23.56,
                "lng": -46.62,
                "cidade": "Sao Paulo",
                "nome_municipio": "Sao Paulo",
                "uf": "SP",
                "faixa_oportunidade": "alta",
                "score_priorizacao": 97.0,
                "hex_score_estrutural": 91.0,
                "flag_viavel": True,
                "flag_prioridade": True,
                "score_setor_2022_calibrado": 86.0,
                "coverage_pct_setor_2022": 96.0,
                "qualidade_join_uf": "A",
                "flag_censo_disponivel": True,
            },
            {
                "hex_id": "sp_granular_3",
                "lat": -23.57,
                "lng": -46.61,
                "cidade": "Sao Paulo",
                "nome_municipio": "Sao Paulo",
                "uf": "SP",
                "faixa_oportunidade": "media",
                "score_priorizacao": 96.0,
                "hex_score_estrutural": 89.0,
                "flag_viavel": True,
                "flag_prioridade": False,
                "score_setor_2022_calibrado": 82.0,
                "coverage_pct_setor_2022": 94.0,
                "qualidade_join_uf": "B",
                "flag_censo_disponivel": True,
            },
            {
                "hex_id": "sp_sem_censo",
                "lat": -23.58,
                "lng": -46.60,
                "cidade": "Sao Paulo",
                "nome_municipio": "Sao Paulo",
                "uf": "SP",
                "faixa_oportunidade": "media",
                "score_priorizacao": 95.0,
                "hex_score_estrutural": 87.0,
                "flag_viavel": True,
                "flag_prioridade": False,
                "score_setor_2022_calibrado": pd.NA,
                "coverage_pct_setor_2022": pd.NA,
                "qualidade_join_uf": "A",
                "flag_censo_disponivel": False,
            },
            {
                "hex_id": "ce_municipal",
                "lat": -3.73,
                "lng": -38.52,
                "cidade": "Fortaleza",
                "nome_municipio": "Fortaleza",
                "uf": "CE",
                "faixa_oportunidade": "alta",
                "score_priorizacao": 99.0,
                "hex_score_estrutural": 93.0,
                "flag_viavel": True,
                "flag_prioridade": True,
                "score_setor_2022_calibrado": pd.NA,
                "coverage_pct_setor_2022": pd.NA,
                "qualidade_join_uf": "C",
                "flag_censo_disponivel": False,
            },
        ]
    )

    deck, points = streamlit_app.build_map_figure(
        df,
        selected_ufs=["SP"],
        selected_cities=[],
    )

    assert deck is not None
    # BLK-FIX-06-C-FU: o hex SP sem censo (sp_sem_censo) NAO e mais descartado — o mapa
    # executivo M1 mostra TODOS os hexes validos da UF (orla/margens incluidas). Antes
    # eram 3 (so os granulares com censo); agora 4 (com o sem-censo, rotulado municipal).
    assert points == 4
    rendered = pd.DataFrame(deck.layers[0].data)
    assert set(rendered["hex_id"]) == {
        "sp_granular_1",
        "sp_granular_2",
        "sp_granular_3",
        "sp_sem_censo",
    }
    assert rendered["hex_id"].nunique() == len(rendered)
    # confianca_geografica é insumo intermediário (decide line_color/recorte granular),
    # mas NÃO é serializada ao payload do layer (fix MessageSizeError, BLK-FIX-02).
    assert "confianca_geografica" not in rendered.columns


def test_build_map_figure_adiciona_pins_de_concorrentes_no_recorte():
    df = pd.DataFrame(
        [
            {
                "hex_id": "sp_granular",
                "lat": -23.55,
                "lng": -46.63,
                "cidade": "Sao Paulo",
                "nome_municipio": "Sao Paulo",
                "uf": "SP",
                "faixa_oportunidade": "alta",
                "score_priorizacao": 98.0,
                "hex_score_estrutural": 92.0,
                "flag_viavel": True,
                "flag_prioridade": True,
                "score_setor_2022_calibrado": 88.0,
                "coverage_pct_setor_2022": 97.0,
                "qualidade_join_uf": "A",
                "flag_censo_disponivel": True,
            }
        ]
    )
    competitors = pd.DataFrame(
        [
            {
                "rede": "smart_fit",
                "rede_label": "Smart Fit",
                "nome_unidade": "Smart Paulista",
                "lat": -23.551,
                "lng": -46.631,
                "cidade": "",
                "uf": "",
                "arquivo_origem": "unidades_smart_fit.csv",
            },
            {
                "rede": "bluefit",
                "rede_label": "Bluefit",
                "nome_unidade": "Blue Rio",
                "lat": -22.90,
                "lng": -43.20,
                "cidade": "",
                "uf": "",
                "arquivo_origem": "unidades_bluefit.csv",
            },
        ]
    )

    deck, points = streamlit_app.build_map_figure(
        df,
        selected_ufs=["SP"],
        selected_cities=[],
        competitors_df=competitors,
    )

    assert deck is not None
    assert points == 1
    assert len(deck.layers) == 2
    rendered_hex = pd.DataFrame(deck.layers[0].data)
    competitor_layer = deck.layers[1]
    rendered_competitors = pd.DataFrame(competitor_layer.data)
    assert "tooltip_title" in rendered_hex.columns
    # BLK-FIX-07: o logo agora vem do atlas (icon_atlas/icon_mapping em nivel de
    # layer) e cada linha leva so a chave da rede em get_icon (sem icon_data por
    # linha). O recorte (apenas Smart Paulista no bbox de SP) e preservado.
    assert "icon_data" not in rendered_competitors.columns
    assert rendered_competitors["tooltip_title"].tolist() == ["Smart Fit: Smart Paulista"]
    # get_icon aponta para a coluna 'rede' (acessor pydeck -> '@@=rede')
    assert str(competitor_layer.get_icon) in ("rede", "@@=rede")
    assert "smart_fit" in competitor_layer.icon_mapping
    # iconAtlas serializado e literal (NAO vira expressao '@@='): trava do pitfall
    serialized_atlas = json.loads(deck.to_json())["layers"][1]["iconAtlas"]
    assert serialized_atlas.startswith("data:image/png;base64,")
    assert not serialized_atlas.startswith("@@=")


# ── BLK-FIX-07: camada de pins escalavel (atlas + payload enxuto + cap duro) ─────

_ICON_PAYLOAD_COLS_COMP = {
    "rede",
    "lng",
    "lat",
    "icon_size",
    "tooltip_title",
    "tooltip_line_1",
    "tooltip_line_2",
    "tooltip_line_3",
    "tooltip_line_4",
    "tooltip_line_5",
}


def _make_synthetic_competitors(n: int) -> pd.DataFrame:
    """n concorrentes sinteticos no bbox de SP, varias redes, coords validas."""
    redes = ["smart_fit", "bluefit", "panobianco", "selfit", "bodytech"]
    rng = np.random.default_rng(7)
    return pd.DataFrame(
        {
            "rede": [redes[i % len(redes)] for i in range(n)],
            "rede_label": [redes[i % len(redes)].title() for i in range(n)],
            "nome_unidade": [f"Unidade {i}" for i in range(n)],
            "lat": rng.uniform(-23.70, -23.40, n),
            "lng": rng.uniform(-46.80, -46.40, n),
            "cidade": ["Sao Paulo"] * n,
            "uf": ["SP"] * n,
            "arquivo_origem": ["sintetico.csv"] * n,
        }
    )


def _sp_reference() -> pd.DataFrame:
    return pd.DataFrame({"lat": [-23.70, -23.40], "lng": [-46.80, -46.40]})


def test_atlas_icon_layer_payload_enxuto_40k_concorrentes():
    """40k concorrentes sinteticos: cap duro aplicado, payload enxuto (sem icon_data
    por linha nem tooltip_line_6..14) e bytes sob LIMIT_BYTES. Medicao deterministica.

    Margem: payload medido ~2.07 MB (6.000 linhas enxutas com tooltips), vs ~7 MB
    para as MESMAS 6.000 linhas no modelo antigo (icon_data por linha) e ~47 MB para
    40k sem cap. LIMIT_BYTES=3_000_000 deixa ~0.9 MB de folga sobre o medido.
    """
    from motor_expansao.dashboard.components import _build_competitor_icon_layer

    LIMIT_BYTES = 3_000_000
    comp = _make_synthetic_competitors(40_000)
    layer, full = _build_competitor_icon_layer(comp, _sp_reference())

    payload = pd.DataFrame(layer.data)
    # cap duro aplicado
    assert len(payload) <= COMPETITOR_PIN_LIMIT
    assert len(payload) == COMPETITOR_PIN_LIMIT  # 40k >> cap
    # payload enxuto: conjunto exato de colunas, sem icon_data nem campos vazios
    assert set(payload.columns) == _ICON_PAYLOAD_COLS_COMP
    assert "icon_data" not in payload.columns
    assert not any(c in payload.columns for c in (f"tooltip_line_{i}" for i in range(6, 15)))
    # bytes sob o limite (com folga documentada)
    payload_bytes = len(json.dumps(payload.to_dict("records")))
    assert payload_bytes < LIMIT_BYTES, f"payload_bytes={payload_bytes}"
    # logo via atlas: literal (sem '@@='), mapping cobre as redes presentes
    serialized = json.loads(
        __import__("pydeck").Deck(layers=[layer]).to_json()
    )["layers"][0]["iconAtlas"]
    assert serialized.startswith("data:image/png;base64,")
    assert not serialized.startswith("@@=")
    for rede in payload["rede"].unique():
        assert rede in layer.icon_mapping


def test_pins_sp_like_1381_sem_regressao():
    """SP-like (1.381 < cap): nao corta, payload enxuto leve e tooltips com os
    MESMOS textos de hoje (Tipo/Rede/Cidade-UF/Coordenadas/Fonte)."""
    from motor_expansao.dashboard.components import _build_competitor_icon_layer

    n = 1381
    comp = _make_synthetic_competitors(n)
    # linha conhecida e deterministica para conferir os textos do tooltip
    comp.loc[0, "rede"] = "smart_fit"
    comp.loc[0, "rede_label"] = "Smart Fit"
    comp.loc[0, "nome_unidade"] = "Smart Conhecida"
    comp.loc[0, "cidade"] = "Sao Paulo"
    comp.loc[0, "uf"] = "SP"
    comp.loc[0, "lat"] = -23.55000
    comp.loc[0, "lng"] = -46.63000
    comp.loc[0, "arquivo_origem"] = "unidades_smart_fit.csv"

    layer, full = _build_competitor_icon_layer(comp, _sp_reference())
    payload = pd.DataFrame(layer.data)
    assert len(payload) == n  # 1.381 < cap, sem corte
    payload_bytes = len(json.dumps(payload.to_dict("records")))
    assert payload_bytes < 600_000, f"payload_bytes={payload_bytes}"

    row = payload.loc[payload["tooltip_title"] == "Smart Fit: Smart Conhecida"].iloc[0]
    assert row["tooltip_line_1"] == "Tipo: Concorrente mapeado"
    assert row["tooltip_line_2"] == "Rede: Smart Fit"
    assert row["tooltip_line_3"] == "Cidade/UF: Sao Paulo / SP"
    assert row["tooltip_line_4"] == "Coordenadas: -23.55000, -46.63000"
    assert row["tooltip_line_5"] == "Fonte: unidades_smart_fit.csv"
    # logo via atlas
    assert "smart_fit" in layer.icon_mapping


def test_icon_atlas_nao_vira_expressao_pydeck():
    """Trava de regressao do pitfall pydeck: iconAtlas serializado deve ser literal
    (data:image/png;base64,...) e NUNCA comecar com '@@=' (acessor invalido)."""
    import pydeck as pdk

    from motor_expansao.dashboard.components import (
        _build_competitor_icon_layer,
        _build_ultra_icon_layer,
    )

    comp = _make_synthetic_competitors(50)
    comp_layer, _ = _build_competitor_icon_layer(comp, _sp_reference())
    ultra = pd.DataFrame(
        {
            "nome_unidade": ["U1", "U2"],
            "lat": [-23.55, -23.56],
            "lng": [-46.63, -46.64],
            "cidade": ["Sao Paulo", "Sao Paulo"],
            "uf": ["SP", "SP"],
            "arquivo_origem": ["Ultra.csv", "Ultra.csv"],
        }
    )
    ultra_layer = _build_ultra_icon_layer(ultra, _sp_reference())

    for layer in (comp_layer, ultra_layer):
        serialized = json.loads(pdk.Deck(layers=[layer]).to_json())["layers"][0]["iconAtlas"]
        assert serialized.startswith("data:image/png;base64,")
        assert not serialized.startswith("@@=")


def test_pins_amostrados_caption():
    """count_pins_in_scope/pins_amostrados_caption: frase so quando > cap; None senao."""
    from motor_expansao.dashboard.components import (
        count_pins_in_scope,
        pins_amostrados_caption,
    )

    ref = _sp_reference()
    comp_small = _make_synthetic_competitors(100)
    n_comp, n_ultra = count_pins_in_scope(comp_small, None, ref)
    assert n_comp == 100
    assert n_ultra == 0
    assert pins_amostrados_caption(n_comp, n_ultra) is None

    comp_big = _make_synthetic_competitors(40_000)
    n_comp_big, _ = count_pins_in_scope(comp_big, None, ref)
    assert n_comp_big == 40_000
    caption = pins_amostrados_caption(n_comp_big, 0)
    assert caption is not None
    assert "nao afeta score" in caption
    assert str(COMPETITOR_PIN_LIMIT).startswith("6")


# ── BLK-FIX-07-B: clustering server-side por recorte ────────────────────────────


def test_competitor_cluster_layer_uf_inteira_agrega_sem_cortar():
    """40k concorrentes -> bolhas de densidade (ScatterplotLayer): conserva o total
    (sem corte quando celulas ocupadas <= LIMIT), respeita o cap de bolhas e mantem
    o payload do cluster bem abaixo de 3MB (muito menor que pins individuais)."""
    from motor_expansao.dashboard.components import _build_competitor_cluster_layer

    comp = _make_synthetic_competitors(40_000)
    layer, frame = _build_competitor_cluster_layer(comp, _sp_reference())

    assert layer is not None
    assert str(layer.type) == "ScatterplotLayer"
    # agrega sem cortar: total preservado (celulas ocupadas << LIMIT no bbox de SP)
    assert int(frame["total"].sum()) == 40_000
    assert len(frame) <= COMPETITOR_CLUSTER_LIMIT
    # payload enxuto: muito abaixo do limite de 3MB
    payload_bytes = len(json.dumps(pd.DataFrame(layer.data).to_dict("records")))
    assert payload_bytes < 3_000_000, f"payload_bytes={payload_bytes}"


def test_build_map_figure_cluster_false_mantem_iconlayer():
    """cluster_competitors=False (Fase A) preserva a IconLayer com logo via atlas,
    mesmo num recorte que o gate consideraria amplo."""
    import h3

    hex_id = h3.latlng_to_cell(-23.55, -46.63, 7)
    df = pd.DataFrame([_hex_row(hex_id, -23.55, -46.63)])
    competitors = _make_synthetic_competitors(50)
    deck, _ = streamlit_app.build_map_figure(
        df,
        selected_ufs=["SP"],
        selected_cities=["Sao Paulo"],
        competitors_df=competitors,
        cluster_competitors=False,
    )
    assert deck is not None
    competitor_layer = deck.layers[1]
    assert str(competitor_layer.type) == "IconLayer"
    assert str(competitor_layer.get_icon) in ("rede", "@@=rede")
    assert competitor_layer.icon_mapping
    serialized_atlas = json.loads(deck.to_json())["layers"][1]["iconAtlas"]
    assert serialized_atlas.startswith("data:image/png;base64,")
    assert competitor_layer.pickable


def test_competitor_cluster_mode_gate():
    """Gate puro/idempotente: Brasil e UF inteira agregam; municipio/faixa/>1 UF nao."""
    from motor_expansao.dashboard.components import competitor_cluster_mode

    assert competitor_cluster_mode([], [], []) is True
    assert competitor_cluster_mode(["SP"], [], []) is True
    assert competitor_cluster_mode(["SP"], ["Sao Paulo"], []) is False
    assert competitor_cluster_mode(["SP"], [], ["alta"]) is False
    assert competitor_cluster_mode(["SP", "RJ"], [], []) is False
    # idempotente em repeticao (pureza)
    assert competitor_cluster_mode(["SP"], [], []) is True
    assert competitor_cluster_mode(["SP"], ["Sao Paulo"], []) is False


def test_competitor_cluster_tooltip_counts():
    """Coords escolhidas para cair na MESMA celula res-4: uma linha de cluster com
    total correto e breakdown por rede com as contagens certas."""
    from motor_expansao.dashboard.components import _build_competitor_cluster_layer

    # 3 Smart Fit + 2 Bluefit, todas proximas (mesma celula res-4 no centro de SP)
    coords = [
        (-23.550, -46.633),
        (-23.551, -46.634),
        (-23.552, -46.635),
        (-23.553, -46.636),
        (-23.554, -46.637),
    ]
    cells = {h3.latlng_to_cell(la, ln, COMPETITOR_CLUSTER_RES) for la, ln in coords}
    assert len(cells) == 1, "sanity: coords devem cair na mesma celula res-4"

    comp = pd.DataFrame(
        {
            "rede": ["smart_fit", "smart_fit", "smart_fit", "bluefit", "bluefit"],
            "rede_label": ["Smart Fit", "Smart Fit", "Smart Fit", "Bluefit", "Bluefit"],
            "nome_unidade": [f"U{i}" for i in range(5)],
            "lat": [la for la, _ in coords],
            "lng": [ln for _, ln in coords],
            "cidade": ["Sao Paulo"] * 5,
            "uf": ["SP"] * 5,
            "arquivo_origem": ["sintetico.csv"] * 5,
        }
    )
    layer, frame = _build_competitor_cluster_layer(comp, _sp_reference())
    assert layer is not None
    assert len(frame) == 1
    row = frame.iloc[0]
    assert int(row["total"]) == 5
    assert row["tooltip_title"] == "Cluster: 5 concorrentes"
    assert row["tooltip_line_2"] == "Total: 5"
    breakdown = row["tooltip_line_3"]
    assert "Smart Fit: 3" in breakdown
    assert "Bluefit: 2" in breakdown
    # 2 redes <= TOP_REDES -> sem sufixo "+N redes"
    assert COMPETITOR_CLUSTER_TOP_REDES >= 2
    assert "redes" not in breakdown


def test_build_unified_map_figure_cluster_gate():
    """Dispatcher aplica o gate: UF inteira -> ScatterplotLayer; com municipio ->
    IconLayer. A contagem de camadas (deck.layers) e identica nos dois modos."""
    import h3

    hex_id = h3.latlng_to_cell(-23.55, -46.63, 7)
    df = pd.DataFrame([_hex_row(hex_id, -23.55, -46.63)])
    competitors = _make_synthetic_competitors(50)

    deck_uf, _ = streamlit_app.build_unified_map_figure(
        df,
        color_mode="m1",
        selected_ufs=["SP"],
        selected_cities=[],
        selected_faixas=[],
        competitors_df=competitors,
    )
    deck_city, _ = streamlit_app.build_unified_map_figure(
        df,
        color_mode="m1",
        selected_ufs=["SP"],
        selected_cities=["Sao Paulo"],
        selected_faixas=[],
        competitors_df=competitors,
    )
    assert deck_uf is not None and deck_city is not None
    assert str(deck_uf.layers[1].type) == "ScatterplotLayer"
    assert str(deck_city.layers[1].type) == "IconLayer"
    # contagem de camadas inalterada entre os dois modos
    assert len(deck_uf.layers) == len(deck_city.layers)


def test_build_map_figure_usa_geometria_granular_em_uf_ab_e_fallback_municipal_em_uf_c():
    df = pd.DataFrame(
        [
            {
                "hex_id": "sp_granular",
                "lat": -23.55,
                "lng": -46.63,
                "cidade": "Sao Paulo",
                "nome_municipio": "Sao Paulo",
                "uf": "SP",
                "faixa_oportunidade": "alta",
                "score_priorizacao": 98.0,
                "hex_score_estrutural": 92.0,
                "flag_viavel": True,
                "flag_prioridade": True,
                "score_setor_2022_calibrado": 88.0,
                "coverage_pct_setor_2022": 97.0,
                "qualidade_join_uf": "B",
                "flag_censo_disponivel": True,
            },
            {
                "hex_id": "sp_sem_censo",
                "lat": -23.57,
                "lng": -46.61,
                "cidade": "Sao Paulo",
                "nome_municipio": "Sao Paulo",
                "uf": "SP",
                "faixa_oportunidade": "media",
                "score_priorizacao": 91.0,
                "hex_score_estrutural": 86.0,
                "flag_viavel": True,
                "flag_prioridade": False,
                "score_setor_2022_calibrado": pd.NA,
                "coverage_pct_setor_2022": pd.NA,
                "qualidade_join_uf": "B",
                "flag_censo_disponivel": False,
            },
            {
                "hex_id": "ce_municipal",
                "lat": -3.73,
                "lng": -38.52,
                "cidade": "Fortaleza",
                "nome_municipio": "Fortaleza",
                "uf": "CE",
                "faixa_oportunidade": "alta",
                "score_priorizacao": 84.0,
                "hex_score_estrutural": 79.0,
                "flag_viavel": True,
                "flag_prioridade": True,
                "score_setor_2022_calibrado": pd.NA,
                "coverage_pct_setor_2022": pd.NA,
                "qualidade_join_uf": "C",
                "flag_censo_disponivel": False,
            },
        ]
    )

    deck, points = streamlit_app.build_map_figure(
        df,
        selected_ufs=["SP", "CE"],
        selected_cities=[],
    )

    assert deck is not None
    # BLK-FIX-06-C-FU: o hex SP sem censo (sp_sem_censo) numa UF granular agora RENDERIZA
    # (antes era descartado) e recebe o rotulo "municipal" (borda ambar), exatamente como
    # a orla costeira. SP granular com censo segue "granular".
    assert points == 3
    rendered = pd.DataFrame(deck.layers[0].data).set_index("hex_id")
    assert set(rendered.index) == {"sp_granular", "sp_sem_censo", "ce_municipal"}
    # confianca_geografica é insumo intermediário (decide a line_color granular vs municipal)
    # e NÃO é serializada ao payload do layer (fix MessageSizeError, BLK-FIX-02). Validamos
    # a consequência visível: o hex granular (SP, qual B + censo) usa a borda granular; o
    # municipal (CE, qual C) e o SP sem censo (orla) usam a borda âmbar canônica municipal.
    assert "confianca_geografica" not in rendered.columns
    assert rendered.loc["ce_municipal", "line_color"] == [245, 158, 11, 220]
    assert rendered.loc["sp_sem_censo", "line_color"] == [245, 158, 11, 220]
    assert rendered.loc["sp_granular", "line_color"] != rendered.loc["ce_municipal", "line_color"]


def test_build_map_figure_m1_renderiza_orla_sem_censo_em_uf_granular():
    # Regressao BLK-FIX-06-C-FU: a orla costeira (sem setor censitario) num UF granular (SP)
    # deve aparecer no mapa executivo M1, colorida pelo score_priorizacao real (NAO descartada,
    # NAO pintada de cinza pois tem pop>=5k). Reproduz Mongagua (87a810998ffffff, score 78).
    from motor_expansao.dashboard.components import _DISCARDED_FILL
    from motor_expansao.dashboard.utils import score_band_to_color

    df = pd.DataFrame(
        [
            {  # ancora granular com censo: garante que SP entra em granular_ufs
                "hex_id": "sp_centro_granular",
                "lat": -23.55,
                "lng": -46.63,
                "cidade": "Sao Paulo",
                "nome_municipio": "Sao Paulo",
                "uf": "SP",
                "faixa_oportunidade": "alta",
                "score_priorizacao": 95.0,
                "hex_score_estrutural": 90.0,
                "flag_viavel": True,
                "flag_prioridade": True,
                "score_setor_2022_calibrado": 88.0,
                "coverage_pct_setor_2022": 97.0,
                "qualidade_join_uf": "A",
                "flag_censo_disponivel": True,
                "flag_pop_min_5k": True,
                "populacao_corte_hex": 12000.0,
            },
            {  # orla sem censo, score alto, pop>=5k -> deve renderizar COLORIDA pelo score
                "hex_id": "87a810998ffffff",
                "lat": -24.09,
                "lng": -46.62,
                "cidade": "Mongagua",
                "nome_municipio": "Mongagua",
                "uf": "SP",
                "faixa_oportunidade": "alta",
                "score_priorizacao": 78.0,
                "hex_score_estrutural": 70.0,
                "flag_viavel": True,
                "flag_prioridade": True,
                "score_setor_2022_calibrado": pd.NA,
                "coverage_pct_setor_2022": pd.NA,
                "qualidade_join_uf": "A",
                "flag_censo_disponivel": False,
                "flag_pop_min_5k": True,
                "populacao_corte_hex": 8000.0,
            },
        ]
    )

    deck, points = streamlit_app.build_map_figure(df, selected_ufs=["SP"], selected_cities=[])

    assert deck is not None
    assert points == 2
    rendered = pd.DataFrame(deck.layers[0].data).set_index("hex_id")
    # a orla NAO e mais descartada do mapa executivo M1
    assert "87a810998ffffff" in rendered.index
    # colorida pelo score real (78), NAO o cinza de descarte (_DISCARDED_FILL tem pop>=5k aqui)
    assert list(rendered.loc["87a810998ffffff", "fill_color"]) == list(score_band_to_color(78.0))
    assert list(rendered.loc["87a810998ffffff", "fill_color"]) != list(_DISCARDED_FILL)
    # borda municipal (sem censo) ambar canonica
    assert rendered.loc["87a810998ffffff", "line_color"] == [245, 158, 11, 220]


def test_sort_carteira_by_m1_preserva_ranking_oficial_antes_do_hibrido():
    carteira = pd.DataFrame(
        [
            {
                "hex_id": "hex_b",
                "rank_brasil": 2,
                "rank_uf": 2,
                "score_priorizacao": 99.0,
                "rank_hex_intraurbano": 3,
                "score_setor_2022_calibrado": 92.0,
                "score_expansao_hibrido": 105.0,
            },
            {
                "hex_id": "hex_a",
                "rank_brasil": 1,
                "rank_uf": 1,
                "score_priorizacao": 88.0,
                "rank_hex_intraurbano": 1,
                "score_setor_2022_calibrado": 70.0,
                "score_expansao_hibrido": 80.0,
            },
        ]
    )

    sorted_df = streamlit_app._sort_carteira_by_m1(carteira)

    assert sorted_df["hex_id"].tolist() == ["hex_a", "hex_b"]


def test_tabelas_hibridas_expoem_flags_de_rastreabilidade():
    hdf = pd.DataFrame(
        [
            {
                "uf": "RJ",
                "nome_municipio": "Rio de Janeiro",
                "hex_id": "hex1",
                "score_setor_2022_calibrado": 91.0,
                "score_priorizacao": 97.0,
                "score_expansao_hibrido": 97.00091,
                "rank_hex_intraurbano": 1,
                "rank_hibrido_brasil": 3,
                "rank_hibrido_uf": 1,
                "top_hex_intraurbano": True,
                "top_oportunidade_municipio": True,
                "qualidade_join_uf": "B",
                "coverage_pct_setor_2022": 90.0,
                "flag_join_uf_restrito": False,
                "flag_baixa_pop_setor": True,
                "flag_outlier_espacial": True,
                "causa_outlier_espacial": "setor_baixa_pop_area_nobre",
                "motivo_nao_elegivel_censo": "elegivel",
                "top_municipio": True,
                "top_municipio_hibrido": True,
                "flag_censo_disponivel": True,
                "flag_monitoramento_prioritario": True,
                "flag_hex_hibrido_elegivel": True,
                "rank_municipio_uf": 1,
                "rank_municipio_brasil": 10,
            }
        ]
    )

    top_hexes = streamlit_app.build_hybrid_top_hexes_table(hdf)
    municipios = streamlit_app.build_hybrid_municipios_table(hdf)
    portfolio = streamlit_app.build_hybrid_portfolio_table(hdf)

    assert "Dens. < 5k" in top_hexes.columns
    assert "Causa Outlier" in top_hexes.columns
    assert top_hexes.loc[0, "Outlier Espacial"] == "Sim"
    assert "Melhor Hex Outlier" in municipios.columns
    assert municipios.loc[0, "Melhor Hex Dens. < 5k"] == "Sim"
    assert "Outlier" in portfolio.columns
    assert portfolio.loc[0, "Dens. < 5k"] == "Sim"


def test_enrich_dashboard_data_deriva_colunas_pop_cut():
    base_df = pd.DataFrame(
        [
            {
                "hex_id": "h1",
                "lat": -23.55,
                "lng": -46.63,
                "uf": "SP",
                "cidade": "Sao Paulo",
                "regiao": "SE",
                "score_priorizacao": 80.0,
                "hex_score_estrutural": 75.0,
                "ajuste_executivo": 5.0,
                "faixa_oportunidade": "alta",
                "flag_viavel": True,
                "flag_prioridade": True,
                "rank_brasil": 1,
                "rank_uf": 1,
                "rank_cidade": 1,
                "renda_per_capita": 5000.0,
                "populacao_proxy": 15_000.0,
            },
            {
                "hex_id": "h2",
                "lat": -23.56,
                "lng": -46.64,
                "uf": "SP",
                "cidade": "Sao Paulo",
                "regiao": "SE",
                "score_priorizacao": 70.0,
                "hex_score_estrutural": 65.0,
                "ajuste_executivo": 5.0,
                "faixa_oportunidade": "media",
                "flag_viavel": False,
                "flag_prioridade": False,
                "rank_brasil": 2,
                "rank_uf": 2,
                "rank_cidade": 2,
                "renda_per_capita": 4000.0,
                "populacao_proxy": 3_000.0,
            },
        ]
    )

    enriched = streamlit_app.enrich_dashboard_data(base_df)

    assert "populacao_corte_hex" in enriched.columns
    assert "fonte_populacao_corte" in enriched.columns
    assert "flag_pop_min_5k" in enriched.columns
    assert bool(enriched.loc[enriched["hex_id"] == "h1", "flag_pop_min_5k"].values[0]) is True
    assert bool(enriched.loc[enriched["hex_id"] == "h2", "flag_pop_min_5k"].values[0]) is False
    assert enriched.loc[enriched["hex_id"] == "h1", "score_priorizacao"].values[0] == 80.0


def test_enrich_dashboard_data_usa_setor_2022_quando_granular():
    base_df = pd.DataFrame(
        [
            {
                "hex_id": "g1",
                "lat": -15.0,
                "lng": -47.0,
                "uf": "DF",
                "cidade": "Brasilia",
                "regiao": "CO",
                "score_priorizacao": 95.0,
                "hex_score_estrutural": 90.0,
                "ajuste_executivo": 5.0,
                "faixa_oportunidade": "prioridade_maxima",
                "flag_viavel": True,
                "flag_prioridade": True,
                "rank_brasil": 1,
                "rank_uf": 1,
                "rank_cidade": 1,
                "renda_per_capita": 7000.0,
                "populacao_proxy": 5_000.0,
            }
        ]
    )
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
                "top_municipio": True,
                "top_municipio_hibrido": True,
                "top_hex_intraurbano": True,
                "rank_hex_intraurbano": 1,
                "rank_municipio_uf": 1,
                "coverage_pct_setor_2022": 99.0,
                "flag_join_uf_restrito": False,
                "flag_baixa_pop_setor": False,
                "flag_outlier_espacial": False,
                "motivo_nao_elegivel_censo": "elegivel",
                "top_oportunidade_municipio": True,
            }
        ]
    )

    enriched = streamlit_app.enrich_dashboard_data(base_df, hybrid_df)

    row = enriched.loc[enriched["hex_id"] == "g1"].iloc[0]
    assert row["fonte_populacao_corte"] == "setor_2022"
    assert float(row["populacao_corte_hex"]) == 20_000.0
    assert bool(row["flag_pop_min_5k"]) is True


def test_parse_coordinate_input_via_streamlit_app():
    assert streamlit_app.parse_coordinate_input("-23.55,-46.63") == pytest.approx((-23.55, -46.63))
    assert streamlit_app.parse_coordinate_input("-23,55; -46,63") == pytest.approx((-23.55, -46.63))
    assert streamlit_app.parse_coordinate_input("invalido") is None
    assert streamlit_app.parse_coordinate_input("20.0,-50.0") is None  # fora do Brasil


def test_lookup_hex_by_coord_encontra_hex_na_base():
    import h3
    lat, lng = -23.55, -46.63
    hex_id = h3.latlng_to_cell(lat, lng, 7)
    df = pd.DataFrame([{
        "hex_id": hex_id,
        "lat": lat,
        "lng": lng,
        "uf": "SP",
        "cidade": "Sao Paulo",
        "score_priorizacao": 80.0,
        "rank_brasil": 100,
    }])
    result = streamlit_app.lookup_hex_by_coord(lat, lng, df)
    assert result is not None
    assert result["hex_id"] == hex_id
    assert result["_not_found"] is False


def test_build_map_figure_centraliza_no_search_pin_e_adiciona_layer():
    import h3
    lat, lng = -23.55, -46.63
    hex_id = h3.latlng_to_cell(lat, lng, 7)
    df = pd.DataFrame([{
        "hex_id": hex_id,
        "lat": lat,
        "lng": lng,
        "cidade": "Sao Paulo",
        "nome_municipio": "Sao Paulo",
        "uf": "SP",
        "faixa_oportunidade": "alta",
        "score_priorizacao": 80.0,
        "hex_score_estrutural": 75.0,
        "flag_viavel": True,
        "flag_prioridade": True,
        "score_setor_2022_calibrado": pd.NA,
        "coverage_pct_setor_2022": pd.NA,
        "qualidade_join_uf": "C",
        "flag_censo_disponivel": False,
    }])

    deck, points = streamlit_app.build_map_figure(
        df,
        selected_ufs=["SP"],
        selected_cities=[],
        search_pin=(-15.77, -47.93),
    )

    assert deck is not None
    assert len(deck.layers) == 2  # hex layer + pin layer
    view = deck.initial_view_state
    assert view.latitude == pytest.approx(-15.77)
    assert view.longitude == pytest.approx(-47.93)
    assert view.zoom == pytest.approx(10.0)


def _hex_row(hex_id: str, lat: float, lng: float, **kwargs) -> dict:
    base = {
        "hex_id": hex_id,
        "lat": lat,
        "lng": lng,
        "cidade": "Sao Paulo",
        "nome_municipio": "Sao Paulo",
        "uf": "SP",
        "faixa_oportunidade": "alta",
        "score_priorizacao": 80.0,
        "hex_score_estrutural": 75.0,
        "flag_viavel": True,
        "flag_prioridade": True,
        "score_setor_2022_calibrado": 85.0,
        "coverage_pct_setor_2022": 97.0,
        "qualidade_join_uf": "A",
        "flag_censo_disponivel": True,
        "populacao_proxy": 12_000,
        "renda_per_capita": 3_500,
        "pop_total_setor_2022": 12_345,
        "renda_per_capita_setor_2022_calibrada": 6_789,
        "flag_pop_min_5k": True,
        "sam_fitness_potencial": 540.0,
        "oferta_consumida_mercado_estimada": 200.0,
        "oferta_consumida_ultra_real": 25.0,
        "oferta_efetiva_disponivel": 300.0,
        "share_ultra_estimado_hex": 0.111,
        "score_oportunidade_residual": 12.0,
        "quartil_oportunidade_residual": "Q3",
    }
    base.update(kwargs)
    return base


def test_build_map_figure_pinta_hex_descartado_por_pop_com_cor_neutra():
    import h3
    lat_ok, lng_ok = -23.55, -46.63
    lat_bad, lng_bad = -23.65, -46.50  # coords diferentes o suficiente para hex distinto
    hex_ok = h3.latlng_to_cell(lat_ok, lng_ok, 7)
    hex_bad = h3.latlng_to_cell(lat_bad, lng_bad, 7)
    assert hex_ok != hex_bad, "sanity: coords devem mapear para hexes distintos"

    df = pd.DataFrame([
        _hex_row(hex_ok, lat_ok, lng_ok, flag_pop_min_5k=True),
        _hex_row(hex_bad, lat_bad, lng_bad, flag_pop_min_5k=False),
    ])

    deck, points = streamlit_app.build_map_figure(df, selected_ufs=["SP"], selected_cities=[])

    assert deck is not None
    assert points == 2
    rendered = pd.DataFrame(deck.layers[0].data).set_index("hex_id")
    # hex descartado deve ter a NOVA cor de "descartado <5k" (visivel, alpha >= 140)
    assert rendered.loc[hex_bad, "fill_color"] == _DISCARDED_FILL
    assert _DISCARDED_FILL[3] >= 140
    assert _DISCARDED_FILL != [120, 120, 140, 70]
    # hex nao descartado nao deve ter a cor de descartado
    assert rendered.loc[hex_ok, "fill_color"] != _DISCARDED_FILL
    # tooltip do descartado deve mencionar descarte
    assert "Descartado" in rendered.loc[hex_bad, "tooltip_title"]
    # tooltip do nao descartado nao deve mencionar descarte
    assert "Descartado" not in rendered.loc[hex_ok, "tooltip_title"]


def test_build_map_figure_orla_baixa_pop_renderiza_visivel():
    """BLK-FIX-06-C: hex de orla (pop <5k) com score_priorizacao valido deve aparecer
    no layer M1 com cor VISIVEL (alpha >= 140), nao o cinza alpha-70 antigo."""
    import h3
    lat, lng = -23.99, -46.41  # orla litoral SP (Mongagua/Praia Grande)
    hex_orla = h3.latlng_to_cell(lat, lng, 7)
    df = pd.DataFrame([
        _hex_row(hex_orla, lat, lng, flag_pop_min_5k=False, score_priorizacao=72.0),
    ])

    deck, points = streamlit_app.build_map_figure(df, selected_ufs=["SP"], selected_cities=[])

    assert deck is not None
    assert points == 1
    rendered = pd.DataFrame(deck.layers[0].data).set_index("hex_id")
    # (a) hex de orla presente no layer (nao descartado do dataset)
    assert hex_orla in rendered.index
    fill = rendered.loc[hex_orla, "fill_color"]
    # (b) cor visivel: alpha >= 140 e != cinza alpha-70 antigo
    assert fill[3] >= 140
    assert fill != [120, 120, 140, 70]


def test_build_hybrid_map_figure_renderiza_hex_sem_setor_censitario():
    """BLK-FIX-06-C: hex sem setor censitario (score_* NaN) com geometria valida deve
    aparecer no layer Hibrido com _NAN_SCORE_FILL (cor de fallback visivel)."""
    import h3
    lat, lng = -23.99, -46.41
    hex_orla = h3.latlng_to_cell(lat, lng, 7)
    hdf = pd.DataFrame([{
        "hex_id": hex_orla,
        "lat": lat,
        "lng": lng,
        "uf": "SP",
        "nome_municipio": "Mongagua",
        "score_setor_2022_calibrado": pd.NA,
        "score_priorizacao": 70.0,
        "score_expansao_hibrido": pd.NA,
        "densidade_pop_setor_hab_km2": pd.NA,
        "qualidade_join_uf": "C",
        "flag_join_uf_restrito": False,
        "flag_baixa_pop_setor": pd.NA,
        "flag_outlier_espacial": False,
        "causa_outlier_espacial": pd.NA,
        "coverage_pct_setor_2022": pd.NA,
        "motivo_nao_elegivel_censo": pd.NA,
        "elegibilidade_hibrida": "-",
        "rank_hex_intraurbano": pd.NA,
        "top_hex_intraurbano": pd.NA,
        "top_oportunidade_municipio": pd.NA,
        "populacao_proxy": 2_416,
        "renda_per_capita": 4_000,
        "pop_total_setor_2022": pd.NA,
        "renda_per_capita_setor_2022_calibrada": pd.NA,
        "flag_pop_min_5k": True,  # isola o caso NaN-de-score do corte de 5k
        "oferta_efetiva_disponivel": pd.NA,
        "score_oportunidade_residual": pd.NA,
        "quartil_oportunidade_residual": pd.NA,
    }])

    deck, n = streamlit_app.build_hybrid_map_figure(
        hdf,
        selected_ufs=["SP"],
        selected_cities=[],
    )

    assert deck is not None
    assert n >= 1
    rendered = pd.DataFrame(deck.layers[0].data).set_index("hex_id")
    # (a) hex presente no layer (nao mais descartado por NaN de setor)
    assert hex_orla in rendered.index
    # (b) cor de fallback de score NaN, visivel
    assert rendered.loc[hex_orla, "fill_color"] == _NAN_SCORE_FILL
    assert _NAN_SCORE_FILL[3] >= 140


def test_build_residual_heatmap_figure_renderiza_hex_sem_score_residual():
    """BLK-FIX-06-C: hex sem score_oportunidade_residual (NaN) com geometria valida deve
    aparecer no layer Residual com _NAN_SCORE_FILL (cor de fallback visivel)."""
    import h3
    lat, lng = -23.99, -46.41
    hex_orla = h3.latlng_to_cell(lat, lng, 7)
    hdf = pd.DataFrame([{
        "hex_id": hex_orla,
        "lat": lat,
        "lng": lng,
        "uf": "SP",
        "nome_municipio": "Mongagua",
        "score_setor_2022_calibrado": pd.NA,
        "score_priorizacao": 70.0,
        "score_expansao_hibrido": pd.NA,
        "densidade_pop_setor_hab_km2": pd.NA,
        "qualidade_join_uf": "C",
        "flag_join_uf_restrito": False,
        "coverage_pct_setor_2022": pd.NA,
        "elegibilidade_hibrida": "-",
        "populacao_proxy": 2_416,
        "renda_per_capita": 4_000,
        "pop_total_setor_2022": pd.NA,
        "flag_pop_min_5k": True,  # isola o caso NaN-de-score do corte de 5k
        "oferta_efetiva_disponivel": pd.NA,
        "score_oportunidade_residual": pd.NA,
        "quartil_oportunidade_residual": pd.NA,
    }])

    deck, n = streamlit_app.build_residual_heatmap_figure(
        hdf,
        selected_ufs=["SP"],
        selected_cities=[],
    )

    assert deck is not None
    assert n >= 1
    rendered = pd.DataFrame(deck.layers[0].data).set_index("hex_id")
    # (a) hex presente no layer (nao mais descartado por NaN de setor)
    assert hex_orla in rendered.index
    # (b) cor de fallback de score NaN, visivel
    assert rendered.loc[hex_orla, "fill_color"] == _NAN_SCORE_FILL
    assert _NAN_SCORE_FILL[3] >= 140


def test_apply_pop_cut_colors_usa_alpha_visivel():
    """BLK-FIX-06-C: _apply_pop_cut_colors deve pintar hex descartado (<5k) com
    _DISCARDED_FILL de alpha visivel (>= 140), nao o cinza alpha-70 antigo."""
    df = pd.DataFrame({
        "flag_pop_min_5k": [False],
        "fill_color": [[10, 20, 30, 200]],
        "line_color": [[1, 2, 3, 200]],
    })

    out = _apply_pop_cut_colors(df)

    assert out.loc[0, "fill_color"] == _DISCARDED_FILL
    assert _DISCARDED_FILL[3] >= 140
    assert _DISCARDED_FILL != [120, 120, 140, 70]


_DECK_LAYER_KEEP_SET = {
    "hex_id",
    "fill_color",
    "line_color",
    "tooltip_title",
    *[f"tooltip_line_{i}" for i in range(1, 15)],
}


def test_build_map_figure_payload_do_layer_so_tem_colunas_de_render_e_tooltip():
    """O payload serializado ao H3HexagonLayer (M1) deve conter SOMENTE colunas de
    render/tooltip — auxiliares e colunas-fonte nao podem vazar (fix MessageSizeError)."""
    import h3
    lat, lng = -23.55, -46.63
    hex_id = h3.latlng_to_cell(lat, lng, 7)
    df = pd.DataFrame([_hex_row(hex_id, lat, lng)])

    deck, points = streamlit_app.build_map_figure(df, selected_ufs=["SP"], selected_cities=[])

    assert deck is not None
    assert points == 1
    rendered = pd.DataFrame(deck.layers[0].data)
    # subconjunto do keep-set
    assert set(rendered.columns) <= _DECK_LAYER_KEEP_SET
    # auxiliares AUSENTES
    for aux in (
        "score_priorizacao_fmt",
        "confianca_geografica",
        "tooltip_residual_1",
        "faixa_label",
        "renda_per_capita",
    ):
        assert aux not in rendered.columns
    # render PRESENTES
    assert {"hex_id", "fill_color", "line_color", "tooltip_title"} <= set(rendered.columns)
    # tooltip preservado
    assert isinstance(rendered.loc[0, "tooltip_title"], str)
    assert rendered.loc[0, "tooltip_title"] != ""


def test_build_hybrid_map_figure_payload_do_layer_enxuto():
    """O payload serializado ao H3HexagonLayer (hibrido) deve conter SOMENTE colunas de
    render/tooltip — auxiliares e colunas-fonte nao podem vazar (fix MessageSizeError)."""
    import h3

    def hybrid_row(hex_id: str, lat: float, lng: float) -> dict:
        return {
            "hex_id": hex_id,
            "lat": lat,
            "lng": lng,
            "uf": "SP",
            "nome_municipio": "Sao Paulo",
            "score_setor_2022_calibrado": 88.0,
            "score_priorizacao": 80.0,
            "score_expansao_hibrido": 93.0,
            "densidade_pop_setor_hab_km2": 8_500,
            "qualidade_join_uf": "A",
            "flag_join_uf_restrito": False,
            "flag_baixa_pop_setor": False,
            "flag_outlier_espacial": False,
            "causa_outlier_espacial": pd.NA,
            "coverage_pct_setor_2022": 96.0,
            "motivo_nao_elegivel_censo": pd.NA,
            "elegibilidade_hibrida": "Elegivel",
            "rank_hex_intraurbano": 1,
            "top_hex_intraurbano": True,
            "top_oportunidade_municipio": True,
            "populacao_proxy": 20_000,
            "renda_per_capita": 4_200,
            "pop_total_setor_2022": 21_000,
            "renda_per_capita_setor_2022_calibrada": 4_500,
            "flag_pop_min_5k": True,
            "sam_fitness_potencial": 1000.0,
            "oferta_consumida_mercado_estimada": 350.0,
            "oferta_consumida_ultra_real": 150.0,
            "oferta_efetiva_disponivel": 650.0,
            "share_ultra_estimado_hex": 0.3,
            "score_oportunidade_residual": 26.0,
            "quartil_oportunidade_residual": "Q4_maior_residual",
        }

    hex_sp = h3.latlng_to_cell(-23.55, -46.63, 7)
    hdf = pd.DataFrame([hybrid_row(hex_sp, -23.55, -46.63)])

    deck, n = streamlit_app.build_hybrid_map_figure(
        hdf,
        selected_ufs=["SP"],
        selected_cities=[],
    )

    assert deck is not None
    assert n == 1
    rendered = pd.DataFrame(deck.layers[0].data)
    assert set(rendered.columns) <= _DECK_LAYER_KEEP_SET
    for aux in (
        "score_censo_fmt",
        "densidade_pop_setor_hab_km2",
        "tooltip_residual_2",
        "score_expansao_hibrido",
        "renda_per_capita",
    ):
        assert aux not in rendered.columns
    assert {"hex_id", "fill_color", "line_color", "tooltip_title"} <= set(rendered.columns)
    assert isinstance(rendered.loc[0, "tooltip_title"], str)
    assert rendered.loc[0, "tooltip_title"] != ""


def test_build_residual_heatmap_figure_payload_do_layer_enxuto():
    """O payload serializado ao H3HexagonLayer (residual) deve conter SOMENTE colunas de
    render/tooltip — colunas-fonte (ex.: score_oportunidade_residual) nao podem vazar."""
    import h3

    def residual_row(hex_id: str, lat: float, lng: float, score_residual: float) -> dict:
        return {
            "hex_id": hex_id,
            "lat": lat,
            "lng": lng,
            "uf": "SP",
            "nome_municipio": "Sao Paulo",
            "score_setor_2022_calibrado": 75.0,
            "score_priorizacao": 80.0,
            "score_expansao_hibrido": 82.0,
            "densidade_pop_setor_hab_km2": 9_000,
            "qualidade_join_uf": "A",
            "coverage_pct_setor_2022": 97.0,
            "elegibilidade_hibrida": "Elegivel",
            "populacao_proxy": 30_000,
            "renda_per_capita": 5_000,
            "pop_total_setor_2022": 25_000,
            "flag_pop_min_5k": True,
            "oferta_efetiva_disponivel": 800.0,
            "score_oportunidade_residual": score_residual,
            "quartil_oportunidade_residual": "Q4_maior_residual",
        }

    hex1 = h3.latlng_to_cell(-23.55, -46.63, 7)
    hdf = pd.DataFrame([residual_row(hex1, -23.55, -46.63, 85.0)])

    deck, n = streamlit_app.build_residual_heatmap_figure(
        hdf,
        selected_ufs=[],
        selected_cities=[],
    )

    assert deck is not None
    assert n == 1
    rendered = pd.DataFrame(deck.layers[0].data)
    assert set(rendered.columns) <= _DECK_LAYER_KEEP_SET
    for aux in (
        "score_oportunidade_residual",
        "densidade_pop_setor_hab_km2",
        "tooltip_residual_1",
        "renda_per_capita",
    ):
        assert aux not in rendered.columns
    assert {"hex_id", "fill_color", "line_color", "tooltip_title"} <= set(rendered.columns)
    assert isinstance(rendered.loc[0, "tooltip_title"], str)
    assert rendered.loc[0, "tooltip_title"] != ""


def test_build_map_figure_adiciona_layer_de_destaque_do_hex_pesquisado():
    import h3
    lat, lng = -23.55, -46.63
    hex_id = h3.latlng_to_cell(lat, lng, 7)
    lat_bsb, lng_bsb = -15.77, -47.93
    hex_brasilia = h3.latlng_to_cell(lat_bsb, lng_bsb, 7)
    df = pd.DataFrame([
        _hex_row(hex_id, lat, lng),
        _hex_row(
            hex_brasilia,
            lat_bsb,
            lng_bsb,
            cidade="Brasilia",
            nome_municipio="Brasilia",
            uf="DF",
            score_priorizacao=91.0,
            hex_score_estrutural=89.0,
            populacao_proxy=20_000,
            renda_per_capita=4_200,
            pop_total_setor_2022=21_000,
            renda_per_capita_setor_2022_calibrada=4_500,
        ),
    ])

    # sem search_hex_id: apenas 1 layer (sem competidores)
    deck_sem, _ = streamlit_app.build_map_figure(df, selected_ufs=["SP"], selected_cities=[])
    assert deck_sem is not None
    assert len(deck_sem.layers) == 1

    # com search_hex_id: 2 layers (hex + destaque)
    deck_com, _ = streamlit_app.build_map_figure(
        df, selected_ufs=["SP"], selected_cities=[], search_hex_id=hex_id
    )
    assert deck_com is not None
    assert len(deck_com.layers) == 2
    highlight_data = pd.DataFrame(deck_com.layers[-1].data)
    assert hex_id in highlight_data["hex_id"].values
    highlight = highlight_data.iloc[0]
    assert highlight["tooltip_title"] == "Sao Paulo / SP"
    assert highlight["tooltip_line_3"] == "Score M1: 80.00"
    assert highlight["tooltip_line_10"] == "Habitantes: 12.345"
    assert highlight["tooltip_line_11"] == "Renda per capita: R$ 6.789"
    assert highlight["tooltip_line_12"] == "Residual fitness: 300 | Score residual: 12.00 | Q3"
    assert highlight["tooltip_line_13"] == "SAM fitness: 540 | Consumo concorrentes: 200"
    assert highlight["tooltip_line_14"] == "Consumo Ultra: 25 | Share Ultra: 11.1%"


def test_build_map_figure_destaque_hex_aparece_mesmo_fora_dos_filtros():
    """Hex pesquisado deve ser destacado mesmo se estiver fora do recorte filtrado."""
    import h3
    lat, lng = -23.55, -46.63
    hex_id = h3.latlng_to_cell(lat, lng, 7)
    lat_bsb, lng_bsb = -15.77, -47.93
    hex_brasilia = h3.latlng_to_cell(lat_bsb, lng_bsb, 7)
    df = pd.DataFrame([
        _hex_row(hex_id, lat, lng),
        _hex_row(
            hex_brasilia,
            lat_bsb,
            lng_bsb,
            cidade="Brasilia",
            nome_municipio="Brasilia",
            uf="DF",
            score_priorizacao=91.0,
            hex_score_estrutural=89.0,
            populacao_proxy=20_000,
            renda_per_capita=4_200,
            pop_total_setor_2022=21_000,
            renda_per_capita_setor_2022_calibrada=4_500,
        ),
    ])
    deck, _ = streamlit_app.build_map_figure(
        df, selected_ufs=["SP"], selected_cities=[], search_hex_id=hex_brasilia
    )
    assert deck is not None
    # deve ter o hex layer (SP) + destaque (Brasilia fora do filtro)
    assert len(deck.layers) == 2
    highlight_data = pd.DataFrame(deck.layers[-1].data)
    assert hex_brasilia in highlight_data["hex_id"].values
    highlight = highlight_data.iloc[0]
    assert highlight["tooltip_title"] == "Brasilia / DF"
    assert highlight["tooltip_line_3"] == "Score M1: 91.00"
    assert highlight["tooltip_line_10"] == "Habitantes: 21.000"


def test_build_hybrid_map_figure_destaque_hex_usa_tooltip_completo():
    import h3

    def hybrid_row(hex_id: str, lat: float, lng: float, uf: str, cidade: str, score_m1: float) -> dict:
        return {
            "hex_id": hex_id,
            "lat": lat,
            "lng": lng,
            "uf": uf,
            "nome_municipio": cidade,
            "score_setor_2022_calibrado": 88.0,
            "score_priorizacao": score_m1,
            "score_expansao_hibrido": 93.0,
            "densidade_pop_setor_hab_km2": 8_500,
            "qualidade_join_uf": "A",
            "flag_join_uf_restrito": False,
            "flag_baixa_pop_setor": False,
            "flag_outlier_espacial": False,
            "causa_outlier_espacial": pd.NA,
            "coverage_pct_setor_2022": 96.0,
            "motivo_nao_elegivel_censo": pd.NA,
            "elegibilidade_hibrida": "Elegivel",
            "rank_hex_intraurbano": 1,
            "top_hex_intraurbano": True,
            "top_oportunidade_municipio": True,
            "populacao_proxy": 20_000,
            "renda_per_capita": 4_200,
            "pop_total_setor_2022": 21_000,
            "renda_per_capita_setor_2022_calibrada": 4_500,
            "flag_pop_min_5k": True,
            "sam_fitness_potencial": 1000.0,
            "oferta_consumida_mercado_estimada": 350.0,
            "oferta_consumida_ultra_real": 150.0,
            "oferta_efetiva_disponivel": 650.0,
            "share_ultra_estimado_hex": 0.3,
            "score_oportunidade_residual": 26.0,
            "quartil_oportunidade_residual": "Q4_maior_residual",
        }

    hex_sp = h3.latlng_to_cell(-23.55, -46.63, 7)
    hex_brasilia = h3.latlng_to_cell(-15.77, -47.93, 7)
    hdf = pd.DataFrame([
        hybrid_row(hex_sp, -23.55, -46.63, "SP", "Sao Paulo", 80.0),
        hybrid_row(hex_brasilia, -15.77, -47.93, "DF", "Brasilia", 91.0),
    ])

    deck, _ = streamlit_app.build_hybrid_map_figure(
        hdf,
        selected_ufs=["SP"],
        selected_cities=[],
        search_hex_id=hex_brasilia,
    )

    assert deck is not None
    assert len(deck.layers) == 2
    highlight = pd.DataFrame(deck.layers[-1].data).iloc[0]
    assert highlight["tooltip_title"] == "Brasilia / DF"
    assert highlight["tooltip_line_1"] == "Score Censitario 2022: 88.00"
    assert highlight["tooltip_line_2"] == "Score M1: 91.00"
    assert highlight["tooltip_line_3"] == "Score Hibrido: 93.00"
    # Quando _HYBRID_TOOLTIP_SHOW_DETAIL=False (compacto): linhas 5-8 sao Habitantes/Renda/Residual.
    # Para restaurar os campos de detalhe (Rank, Top, Elegibilidade, Qualidade, Outlier, Motivo),
    # setar _HYBRID_TOOLTIP_SHOW_DETAIL=True em components.py e ajustar as assertions abaixo
    # para tooltip_line_11/12/13/14.
    assert highlight["tooltip_line_5"] == "Habitantes: 21.000"
    assert highlight["tooltip_line_6"] == "Renda per capita: R$ 4.500"
    assert highlight["tooltip_line_7"] == "Residual fitness: 650 | Score residual: 26.00 | Q4_maior_residual"
    assert highlight["tooltip_line_8"] == "SAM fitness: 1.000 | Consumo concorrentes: 350 | Consumo Ultra: 150 | Share Ultra: 30.0%"


def test_residual_score_to_color_faixas():
    assert streamlit_app._residual_score_to_color(0) == [148, 18, 18, 190]
    assert streamlit_app._residual_score_to_color(5) == [148, 18, 18, 190]
    assert streamlit_app._residual_score_to_color(95) == [10, 130, 38, 170]
    assert streamlit_app._residual_score_to_color(100) == [10, 130, 38, 170]
    assert streamlit_app._residual_score_to_color(None) == [120, 120, 140, 70]


def test_build_residual_heatmap_figure_retorna_deck_com_hexes():
    import h3

    def residual_row(hex_id: str, lat: float, lng: float, score_residual: float) -> dict:
        return {
            "hex_id": hex_id,
            "lat": lat,
            "lng": lng,
            "uf": "SP",
            "nome_municipio": "Sao Paulo",
            "score_setor_2022_calibrado": 75.0,
            "score_priorizacao": 80.0,
            "score_expansao_hibrido": 82.0,
            "densidade_pop_setor_hab_km2": 9_000,
            "qualidade_join_uf": "A",
            "flag_join_uf_restrito": False,
            "flag_baixa_pop_setor": False,
            "flag_outlier_espacial": False,
            "coverage_pct_setor_2022": 97.0,
            "elegibilidade_hibrida": "Elegivel",
            "rank_hex_intraurbano": 1,
            "top_hex_intraurbano": True,
            "top_oportunidade_municipio": True,
            "populacao_proxy": 30_000,
            "renda_per_capita": 5_000,
            "pop_total_setor_2022": 25_000,
            "flag_pop_min_5k": True,
            "oferta_efetiva_disponivel": 800.0,
            "score_oportunidade_residual": score_residual,
            "quartil_oportunidade_residual": "Q4_maior_residual",
        }

    hex1 = h3.latlng_to_cell(-23.55, -46.63, 7)
    hex2 = h3.latlng_to_cell(-23.56, -46.64, 7)
    hdf = pd.DataFrame([
        residual_row(hex1, -23.55, -46.63, 85.0),
        residual_row(hex2, -23.56, -46.64, 15.0),
    ])

    deck, n_points = streamlit_app.build_residual_heatmap_figure(
        hdf,
        selected_ufs=[],
        selected_cities=[],
    )

    assert deck is not None
    assert n_points == 2
    map_layer_data = pd.DataFrame(deck.layers[0].data)
    # score_oportunidade_residual é insumo (gera fill_color) mas NÃO é serializada ao
    # payload do layer (fix MessageSizeError, BLK-FIX-02). Validamos a cor resultante:
    # a linha 0 (residual=85) recebe a cor da faixa alta; a linha 1 (residual=15), a baixa.
    assert "score_oportunidade_residual" not in map_layer_data.columns
    fill_high = map_layer_data.iloc[0]["fill_color"]
    fill_low = map_layer_data.iloc[1]["fill_color"]
    assert fill_high == streamlit_app.score_band_to_color(85.0)
    assert fill_low == streamlit_app.score_band_to_color(15.0)
    assert fill_high != fill_low


def test_build_residual_heatmap_figure_sem_score_retorna_none():
    hdf = pd.DataFrame([{"hex_id": "a", "lat": -23.5, "lng": -46.6, "uf": "SP"}])
    deck, n = streamlit_app.build_residual_heatmap_figure(
        hdf, selected_ufs=[], selected_cities=[]
    )
    assert deck is None
    assert n == 0


def test_load_plano_dominio_retorna_vazio_quando_ausente(monkeypatch):
    monkeypatch.setattr(streamlit_app, "PLANO_DOMINIO_PATH", Path("_nao_existe_dominio.parquet"))
    streamlit_app.load_plano_dominio.clear()
    df = streamlit_app.load_plano_dominio()
    assert df.empty


def test_render_expansao_dominio_exibe_warning_sem_dados():
    """render_expansao_dominio nao deve lancar excecao com DataFrame vazio."""
    import unittest.mock as mock

    with mock.patch("streamlit.warning") as warn_mock:
        streamlit_app.render_expansao_dominio(pd.DataFrame())
    warn_mock.assert_called_once()
    msg = warn_mock.call_args[0][0]
    assert "Expansao de Dominio" in msg or "plano" in msg.lower()


def _dominio_row(hex_id: str, uf: str, cidade: str, ordem: int, tese: str) -> dict:
    return {
        "hex_id": hex_id,
        "uf": uf,
        "cod_municipio": f"cod_{cidade[:3]}",
        "nome_municipio": cidade,
        "lat": -23.55,
        "lng": -46.63,
        "cluster_id": f"cluster_{cidade[:3]}_001",
        "score_oportunidade_residual": 65.0,
        "oferta_efetiva_disponivel": 500.0,
        "sam_fitness_potencial": 1200.0,
        "residual_incremental_capturado": 300.0 - ordem * 10,
        "residual_cluster_pos_acao": 200.0,
        "dist_ultra_mais_proxima_m": 1800.0,
        "n_concorrentes_mapeados_2km": 1,
        "tese_dominio": tese,
        "ordem_expansao_cidade": ordem,
        "rank_dominio_brasil": ordem,
        "rank_dominio_uf": ordem,
        "rank_dominio_cidade": ordem,
    }


def _mock_columns(n_or_list, **kw):
    import unittest.mock as mock
    n = n_or_list if isinstance(n_or_list, int) else len(n_or_list)
    return [mock.MagicMock() for _ in range(n)]


def test_render_expansao_dominio_exibe_tabela_com_dados():
    """Com dados validos, render_expansao_dominio deve exibir dataframe sem excecao."""
    import unittest.mock as mock

    plano = pd.DataFrame([
        _dominio_row("hex_a", "SP", "Sao Paulo", 1, "dominar_white_space"),
        _dominio_row("hex_b", "SP", "Sao Paulo", 2, "adensar_cluster"),
        _dominio_row("hex_c", "RJ", "Rio de Janeiro", 1, "abrir_com_disputa"),
    ])

    rendered_frames = []

    with (
        mock.patch("streamlit.dataframe", side_effect=lambda df, **kw: rendered_frames.append(df)),
        mock.patch("streamlit.markdown"),
        mock.patch("streamlit.caption"),
        mock.patch("streamlit.columns", side_effect=_mock_columns),
        mock.patch("streamlit.multiselect", side_effect=lambda label, options, **kw: options),
        mock.patch("streamlit.info"),
    ):
        streamlit_app.render_expansao_dominio(plano, selected_ufs=["SP", "RJ"])

    assert len(rendered_frames) >= 1
    tbl = rendered_frames[0]
    assert "Hex Ancora" in tbl.columns or "hex_id" in tbl.columns or "Tese" in tbl.columns


def test_render_expansao_dominio_filtro_por_tese():
    """Filtro por tese deve reduzir as linhas exibidas."""
    import unittest.mock as mock

    plano = pd.DataFrame([
        _dominio_row("hex_a", "SP", "Sao Paulo", 1, "dominar_white_space"),
        _dominio_row("hex_b", "SP", "Sao Paulo", 2, "adensar_cluster"),
        _dominio_row("hex_c", "SP", "Sao Paulo", 3, "monitorar"),
    ])

    rendered_frames = []

    def fake_multiselect(label, options, **kw):
        if label == "Tese de dominio":
            return ["dominar_white_space"]
        return options

    with (
        mock.patch("streamlit.dataframe", side_effect=lambda df, **kw: rendered_frames.append(df)),
        mock.patch("streamlit.markdown"),
        mock.patch("streamlit.caption"),
        mock.patch("streamlit.columns", side_effect=_mock_columns),
        mock.patch("streamlit.multiselect", side_effect=fake_multiselect),
        mock.patch("streamlit.info"),
    ):
        streamlit_app.render_expansao_dominio(plano)

    assert len(rendered_frames) >= 1
    tbl = rendered_frames[0]
    assert len(tbl) == 1


def test_build_dominio_map_figure_retorna_deck_com_ancoras():
    """build_dominio_map_figure deve retornar deck com layer de hexes e contar ancoras."""
    import h3

    # Usar coordenadas de cidades diferentes para garantir hexes distintos em res7
    hex_sp = h3.latlng_to_cell(-23.55, -46.63, 7)
    hex_rj = h3.latlng_to_cell(-22.90, -43.17, 7)
    assert hex_sp != hex_rj, "sanity: SP e RJ devem ter hexes distintos"

    plano = pd.DataFrame([
        {
            "hex_id": hex_sp, "uf": "SP", "nome_municipio": "Sao Paulo",
            "lat": -23.55, "lng": -46.63, "cluster_id": "cluster_SP_001",
            "ordem_expansao_cidade": 1, "tese_dominio": "dominar_white_space",
            "score_oportunidade_residual": 75.0, "residual_incremental_capturado": 400.0,
            "dist_ultra_mais_proxima_m": 1800.0, "n_concorrentes_mapeados_2km": 0,
            "rank_dominio_brasil": 1,
        },
        {
            "hex_id": hex_rj, "uf": "RJ", "nome_municipio": "Rio de Janeiro",
            "lat": -22.90, "lng": -43.17, "cluster_id": "cluster_RJ_001",
            "ordem_expansao_cidade": 1, "tese_dominio": "adensar_cluster",
            "score_oportunidade_residual": 60.0, "residual_incremental_capturado": 280.0,
            "dist_ultra_mais_proxima_m": 2100.0, "n_concorrentes_mapeados_2km": 1,
            "rank_dominio_brasil": 2,
        },
    ])

    deck, n = streamlit_app.build_dominio_map_figure(plano)

    assert deck is not None
    assert n == 2
    layer_data = pd.DataFrame(deck.layers[0].data)
    assert set(layer_data["hex_id"]) == {hex_sp, hex_rj}
    # ordem 1 em ambos: fill_color igual (mesmo gradiente)
    row_sp = layer_data.loc[layer_data["hex_id"] == hex_sp].iloc[0]
    assert "Abertura #1" in row_sp["tooltip_line_1"]
    assert "dominar_white_space" in row_sp["tooltip_line_2"]
    # borda distingue tese: SP=verde, RJ=purple
    row_rj = layer_data.loc[layer_data["hex_id"] == hex_rj].iloc[0]
    assert row_sp["line_color"] != row_rj["line_color"]


def test_build_dominio_map_figure_retorna_none_sem_dados():
    """build_dominio_map_figure deve retornar (None, 0) com DataFrame vazio ou sem colunas minimas."""
    deck, n = streamlit_app.build_dominio_map_figure(pd.DataFrame())
    assert deck is None
    assert n == 0

    deck2, n2 = streamlit_app.build_dominio_map_figure(
        pd.DataFrame([{"uf": "SP", "nome_municipio": "Sao Paulo"}])
    )
    assert deck2 is None
    assert n2 == 0


# ── Testes de configuracao de camadas (Bloco 2) ───────────────────────────────

def test_color_mode_ids_sem_duplicatas():
    assert len(COLOR_MODE_IDS) == len(set(COLOR_MODE_IDS))


def test_overlay_ids_sem_duplicatas():
    assert len(OVERLAY_IDS) == len(set(OVERLAY_IDS))


def test_color_mode_required_cols_existem_em_schemas_conhecidos():
    known = set(REQUIRED_COLUMNS) | set(HYBRID_LOAD_COLS) | set(DOMINIO_SCHEMA_MINIMO)
    for mode_id, cfg in COLOR_MODES.items():
        for col in cfg["required_cols"]:
            assert col in known, f"Coluna '{col}' no modo '{mode_id}' nao encontrada nos schemas conhecidos"


def test_color_mode_available_fallback_gracioso():
    df_m1 = pd.DataFrame(columns=["faixa_oportunidade", "score_priorizacao"])
    assert color_mode_available(df_m1, "m1") is True
    assert color_mode_available(df_m1, "hibrido") is False
    assert color_mode_available(df_m1, "modo_inexistente") is False


def test_overlay_available_fallback_gracioso():
    df = pd.DataFrame(columns=["lat", "lng", "rede"])
    assert overlay_available(df, "concorrentes") is True
    assert overlay_available(df, "ultra") is True
    assert overlay_available(df, "descartados_5k") is False
    assert overlay_available(df, "overlay_inexistente") is False


# ── Testes do Bloco 3: build_unified_map_figure ───────────────────────────────

def _hybrid_row_unified(hex_id: str, lat: float, lng: float, **kwargs) -> dict:
    base = {
        "hex_id": hex_id,
        "lat": lat,
        "lng": lng,
        "uf": "SP",
        "nome_municipio": "Sao Paulo",
        "score_setor_2022_calibrado": 75.0,
        "score_priorizacao": 80.0,
        "score_expansao_hibrido": 82.0,
        "densidade_pop_setor_hab_km2": 9_000,
        "qualidade_join_uf": "A",
        "flag_join_uf_restrito": False,
        "flag_baixa_pop_setor": False,
        "flag_outlier_espacial": False,
        "causa_outlier_espacial": pd.NA,
        "coverage_pct_setor_2022": 95.0,
        "motivo_nao_elegivel_censo": pd.NA,
        "elegibilidade_hibrida": "Elegivel",
        "rank_hex_intraurbano": 1,
        "top_hex_intraurbano": True,
        "top_oportunidade_municipio": True,
        "populacao_proxy": 12_000,
        "renda_per_capita": 3_500,
        "pop_total_setor_2022": 12_345,
        "renda_per_capita_setor_2022_calibrada": 6_789,
        "flag_pop_min_5k": True,
        "score_oportunidade_residual": 55.0,
        "oferta_efetiva_disponivel": 400.0,
        "quartil_oportunidade_residual": "Q3",
    }
    base.update(kwargs)
    return base


def test_build_unified_map_figure_modo_m1_retorna_deck():
    import h3
    hex_id = h3.latlng_to_cell(-23.55, -46.63, 7)
    df = pd.DataFrame([_hex_row(hex_id, -23.55, -46.63)])
    deck, n = streamlit_app.build_unified_map_figure(
        df, color_mode="m1", selected_ufs=["SP"], selected_cities=[]
    )
    assert deck is not None
    assert n == 1
    rendered = pd.DataFrame(deck.layers[0].data)
    assert "hex_id" in rendered.columns


def test_build_unified_map_figure_modo_residual_usa_score_residual():
    import h3
    hex1 = h3.latlng_to_cell(-23.55, -46.63, 7)
    hex2 = h3.latlng_to_cell(-23.65, -46.50, 7)
    assert hex1 != hex2
    df = pd.DataFrame([
        _hybrid_row_unified(hex1, -23.55, -46.63, score_oportunidade_residual=85.0),
        _hybrid_row_unified(hex2, -23.65, -46.50, score_oportunidade_residual=15.0),
    ])
    deck, n = streamlit_app.build_unified_map_figure(
        df, color_mode="residual", selected_ufs=[], selected_cities=[]
    )
    assert deck is not None
    assert n == 2
    rendered = pd.DataFrame(deck.layers[0].data).set_index("hex_id")
    # scores opostos devem gerar cores opostas
    assert rendered.loc[hex1, "fill_color"] != rendered.loc[hex2, "fill_color"]


def test_build_unified_map_figure_overlay_concorrentes_desligado():
    import h3
    hex_id = h3.latlng_to_cell(-23.55, -46.63, 7)
    df = pd.DataFrame([_hex_row(hex_id, -23.55, -46.63)])
    competitors = pd.DataFrame([{
        "rede": "smart_fit",
        "rede_label": "Smart Fit",
        "nome_unidade": "Smart Paulista",
        "lat": -23.551,
        "lng": -46.631,
        "cidade": "",
        "uf": "",
        "arquivo_origem": "unidades_smart_fit.csv",
    }])
    deck_com, _ = streamlit_app.build_unified_map_figure(
        df, color_mode="m1", enabled_overlays=["concorrentes"],
        selected_ufs=["SP"], selected_cities=[], competitors_df=competitors,
    )
    assert deck_com is not None
    assert len(deck_com.layers) == 2

    deck_sem, _ = streamlit_app.build_unified_map_figure(
        df, color_mode="m1", enabled_overlays=[],
        selected_ufs=["SP"], selected_cities=[], competitors_df=competitors,
    )
    assert deck_sem is not None
    assert len(deck_sem.layers) == 1


def test_build_unified_map_figure_overlay_hex_pesquisado_ligado_vs_desligado():
    # BLK-FIX-11 OVERLAY 1: hex_pesquisado liga/desliga o pin + hex destacado.
    hex_id = h3.latlng_to_cell(-23.55, -46.63, 7)
    df = pd.DataFrame([_hex_row(hex_id, -23.55, -46.63)])
    search_pin = (-23.55, -46.63)
    search_hex_id = hex_id

    deck_on, _ = streamlit_app.build_unified_map_figure(
        df, color_mode="m1",
        enabled_overlays=["hex_pesquisado"],
        selected_ufs=["SP"], selected_cities=[],
        search_pin=search_pin, search_hex_id=search_hex_id,
    )
    assert deck_on is not None
    # hex_layer + search_pin_layer + search_hex_layer
    assert len(deck_on.layers) == 3

    deck_off, _ = streamlit_app.build_unified_map_figure(
        df, color_mode="m1",
        enabled_overlays=[],
        selected_ufs=["SP"], selected_cities=[],
        search_pin=search_pin, search_hex_id=search_hex_id,
    )
    assert deck_off is not None
    # so o hex_layer; pin e hex destacado suprimidos
    assert len(deck_off.layers) == 1


def test_build_unified_map_figure_overlay_descartados_5k_ligado_vs_desligado():
    # BLK-FIX-11 OVERLAY 2: descartados_5k alterna o cinza _DISCARDED_FILL + label.
    lat_ok, lng_ok = -23.55, -46.63
    lat_bad, lng_bad = -23.65, -46.50
    hex_ok = h3.latlng_to_cell(lat_ok, lng_ok, 7)
    hex_bad = h3.latlng_to_cell(lat_bad, lng_bad, 7)
    assert hex_ok != hex_bad

    df = pd.DataFrame([
        _hex_row(hex_ok, lat_ok, lng_ok, flag_pop_min_5k=True),
        _hex_row(hex_bad, lat_bad, lng_bad, flag_pop_min_5k=False),
    ])

    deck_on, _ = streamlit_app.build_unified_map_figure(
        df, color_mode="m1",
        enabled_overlays=["descartados_5k"],
        selected_ufs=["SP"], selected_cities=[],
    )
    assert deck_on is not None
    rendered_on = pd.DataFrame(deck_on.layers[0].data).set_index("hex_id")
    assert rendered_on.loc[hex_bad, "fill_color"] == _DISCARDED_FILL
    assert "Descartado" in rendered_on.loc[hex_bad, "tooltip_title"]

    deck_off, _ = streamlit_app.build_unified_map_figure(
        df, color_mode="m1",
        enabled_overlays=[],
        selected_ufs=["SP"], selected_cities=[],
    )
    assert deck_off is not None
    rendered_off = pd.DataFrame(deck_off.layers[0].data).set_index("hex_id")
    assert rendered_off.loc[hex_bad, "fill_color"] != _DISCARDED_FILL
    assert "Descartado" not in rendered_off.loc[hex_bad, "tooltip_title"]


def test_build_unified_map_figure_overlay_ancoras_dominio_ligado_vs_desligado():
    # BLK-FIX-11 OVERLAY 3: ancoras_dominio injeta/remove a camada ambar; no-op
    # silencioso quando dominio_df e None ou vazio.
    hex_id = h3.latlng_to_cell(-23.55, -46.63, 7)
    hex_dom = h3.latlng_to_cell(-23.56, -46.64, 7)
    df = pd.DataFrame([_hex_row(hex_id, -23.55, -46.63)])
    dominio_df = pd.DataFrame([{
        "hex_id": hex_dom,
        "lat": -23.56,
        "lng": -46.64,
        "uf": "SP",
        "nome_municipio": "Sao Paulo",
    }])

    deck_on, _ = streamlit_app.build_unified_map_figure(
        df, color_mode="m1",
        enabled_overlays=["ancoras_dominio"],
        selected_ufs=["SP"], selected_cities=[],
        dominio_df=dominio_df,
    )
    assert deck_on is not None
    assert len(deck_on.layers) == 2  # hex_layer + ancoras_layer

    deck_off, _ = streamlit_app.build_unified_map_figure(
        df, color_mode="m1",
        enabled_overlays=[],
        selected_ufs=["SP"], selected_cities=[],
        dominio_df=dominio_df,
    )
    assert deck_off is not None
    assert len(deck_off.layers) == 1

    # No-op silencioso quando dominio_df e None
    deck_none, _ = streamlit_app.build_unified_map_figure(
        df, color_mode="m1",
        enabled_overlays=["ancoras_dominio"],
        selected_ufs=["SP"], selected_cities=[],
        dominio_df=None,
    )
    assert deck_none is not None
    assert len(deck_none.layers) == 1

    # No-op silencioso quando dominio_df e vazio
    deck_empty, _ = streamlit_app.build_unified_map_figure(
        df, color_mode="m1",
        enabled_overlays=["ancoras_dominio"],
        selected_ufs=["SP"], selected_cities=[],
        dominio_df=pd.DataFrame(),
    )
    assert deck_empty is not None
    assert len(deck_empty.layers) == 1


def test_build_unified_map_figure_modo_dominio_fallback_sem_dados():
    deck, n = streamlit_app.build_unified_map_figure(
        pd.DataFrame(), color_mode="dominio",
        selected_ufs=[], selected_cities=[],
        dominio_df=pd.DataFrame(),
    )
    assert deck is None
    assert n == 0


def test_build_unified_map_figure_censitario_vs_hibrido_cor_diferente():
    """Modo censitario dropa residual: hex com censo alto deve ter cor diferente de modo hibrido."""
    import h3
    hex1 = h3.latlng_to_cell(-23.55, -46.63, 7)
    hex2 = h3.latlng_to_cell(-23.65, -46.50, 7)
    assert hex1 != hex2
    # censo alto / residual baixo para hex1; censo baixo / residual alto para hex2
    df = pd.DataFrame([
        _hybrid_row_unified(hex1, -23.55, -46.63, score_setor_2022_calibrado=90.0, score_oportunidade_residual=10.0),
        _hybrid_row_unified(hex2, -23.65, -46.50, score_setor_2022_calibrado=10.0, score_oportunidade_residual=90.0),
    ])
    deck_censo, n_censo = streamlit_app.build_unified_map_figure(
        df, color_mode="censitario", selected_ufs=[], selected_cities=[]
    )
    deck_hibrido, n_hibrido = streamlit_app.build_unified_map_figure(
        df, color_mode="hibrido", selected_ufs=[], selected_cities=[]
    )
    assert deck_censo is not None and n_censo == 2
    assert deck_hibrido is not None and n_hibrido == 2
    rendered_censo = pd.DataFrame(deck_censo.layers[0].data).set_index("hex_id")
    rendered_hibrido = pd.DataFrame(deck_hibrido.layers[0].data).set_index("hex_id")
    # No modo censitario hex1 (censo=90) deve ser verde; hex2 (censo=10) deve ser vermelho
    # No modo hibrido hex2 (residual=90) deve ser verde; hex1 (residual=10) deve ser vermelho
    color_hex1_censo = rendered_censo.loc[hex1, "fill_color"]
    color_hex1_hibrido = rendered_hibrido.loc[hex1, "fill_color"]
    # hex1 deve ser melhor no modo censitario do que no hibrido
    assert color_hex1_censo != color_hex1_hibrido


# ── Testes do Bloco 4: render_mapa_territorial ────────────────────────────────

def test_render_mapa_territorial_e_exportado():
    assert hasattr(streamlit_app, "render_mapa_territorial")
    assert callable(streamlit_app.render_mapa_territorial)


def test_render_mapa_territorial_modo_m1_renderiza_mapa():
    import unittest.mock as mock

    import h3

    hex_id = h3.latlng_to_cell(-23.55, -46.63, 7)
    df = pd.DataFrame([_hex_row(hex_id, -23.55, -46.63)])

    fragment_calls = []

    with (
        mock.patch("streamlit.selectbox", return_value="m1"),
        mock.patch("streamlit.multiselect", return_value=["concorrentes", "ultra", "hex_pesquisado", "descartados_5k"]),
        mock.patch("streamlit.columns", side_effect=_mock_columns),
        mock.patch("streamlit.markdown"),
        mock.patch("streamlit.caption"),
        mock.patch("streamlit.info"),
        mock.patch("streamlit.warning"),
        mock.patch(
            "motor_expansao.dashboard.pages.render_mapa_pydeck_fragment",
            side_effect=lambda deck, n_points, selected_ufs, multihex_ids: fragment_calls.append(deck),
        ),
    ):
        streamlit_app.render_mapa_territorial(df, selected_ufs=["SP"], selected_cities=[])

    assert len(fragment_calls) == 1
    assert fragment_calls[0] is not None


def test_render_mapa_territorial_modo_indisponivel_exibe_aviso():
    import unittest.mock as mock

    df = pd.DataFrame([{
        "hex_id": "h1", "lat": -23.5, "lng": -46.6,
        "faixa_oportunidade": "alta", "score_priorizacao": 80.0,
    }])

    warnings_captured = []

    with (
        mock.patch("streamlit.selectbox", return_value="hibrido"),
        mock.patch("streamlit.multiselect", return_value=[]),
        mock.patch("streamlit.columns", side_effect=_mock_columns),
        mock.patch("streamlit.markdown"),
        mock.patch("streamlit.caption"),
        mock.patch("streamlit.warning", side_effect=lambda msg, **kw: warnings_captured.append(msg)),
    ):
        streamlit_app.render_mapa_territorial(df, selected_ufs=["SP"], selected_cities=[])

    assert len(warnings_captured) >= 1
    assert any("Hibrido" in w or "disponivel" in w for w in warnings_captured)


def test_render_mapa_territorial_dominio_sem_dados_exibe_info():
    import unittest.mock as mock

    import h3

    hex_id = h3.latlng_to_cell(-23.55, -46.63, 7)
    df = pd.DataFrame([_hex_row(hex_id, -23.55, -46.63)])

    infos_captured = []

    with (
        mock.patch("streamlit.selectbox", return_value="dominio"),
        mock.patch("streamlit.multiselect", return_value=[]),
        mock.patch("streamlit.columns", side_effect=_mock_columns),
        mock.patch("streamlit.markdown"),
        mock.patch("streamlit.caption"),
        mock.patch("streamlit.info", side_effect=lambda msg, **kw: infos_captured.append(msg)),
        mock.patch("streamlit.warning"),
    ):
        streamlit_app.render_mapa_territorial(
            df, selected_ufs=["SP"], selected_cities=[], dominio_df=pd.DataFrame()
        )

    assert len(infos_captured) >= 1


def test_render_mapa_territorial_sem_dados_no_mapa_exibe_info():
    """Quando build_unified_map_figure retorna None, deve mostrar info em vez de erro.

    BLK-FIX-06-C: o scope dos builders relaxou para exigir só geometria valida (nao
    mais setor censitario), entao o caso "sem dados no mapa" passa a ser geometria
    ausente (lat/lng NaN), e nao score NaN — score NaN agora RENDERIZA (orla)."""
    import unittest.mock as mock

    df = pd.DataFrame([_hybrid_row_unified(
        "h1", float("nan"), float("nan"),
        score_setor_2022_calibrado=pd.NA,
        score_oportunidade_residual=pd.NA,
    )])

    infos_captured = []

    with (
        mock.patch("streamlit.selectbox", return_value="residual"),
        mock.patch("streamlit.multiselect", return_value=[]),
        mock.patch("streamlit.columns", side_effect=_mock_columns),
        mock.patch("streamlit.markdown"),
        mock.patch("streamlit.caption"),
        mock.patch("streamlit.info", side_effect=lambda msg, **kw: infos_captured.append(msg)),
        mock.patch("streamlit.warning"),
    ):
        streamlit_app.render_mapa_territorial(df, selected_ufs=["SP"], selected_cities=[])

    assert len(infos_captured) >= 1


# ── Testes do Bloco 5: enxugar abas ──────────────────────────────────────────

def test_render_carteira_e_plano_e_exportado():
    """render_carteira_e_plano deve estar disponivel via streamlit_app."""
    assert hasattr(streamlit_app, "render_carteira_e_plano")
    assert callable(streamlit_app.render_carteira_e_plano)


def test_render_mapa_territorial_com_city_summary_renderiza_expanders():
    """Passando city_summary, render_mapa_territorial deve criar expanders abaixo do mapa."""
    import unittest.mock as mock

    import h3

    hex_id = h3.latlng_to_cell(-23.55, -46.63, 7)
    df = pd.DataFrame([_hex_row(hex_id, -23.55, -46.63)])
    city_summary = pd.DataFrame([{
        "uf": "SP", "cidade": "Sao Paulo", "score_medio": 80.0, "melhor_rank_brasil": 1,
        "oportunidades_viaveis": 3, "renda_per_capita": 5000.0, "populacao_proxy": 15000.0,
    }])
    uf_summary = pd.DataFrame([{
        "uf": "SP", "oportunidades_viaveis": 3, "score_medio": 80.0,
        "renda_per_capita": 5000.0, "populacao_proxy": 15000.0,
    }])

    expanders_created = []

    def fake_expander(label, **kw):
        expanders_created.append(label)
        return mock.MagicMock()

    with (
        mock.patch("streamlit.selectbox", return_value="m1"),
        mock.patch("streamlit.multiselect", return_value=[]),
        mock.patch("streamlit.columns", side_effect=_mock_columns),
        mock.patch("streamlit.markdown"),
        mock.patch("streamlit.caption"),
        mock.patch("streamlit.info"),
        mock.patch("streamlit.warning"),
        mock.patch("streamlit.pydeck_chart"),
        mock.patch("streamlit.plotly_chart"),
        mock.patch("streamlit.dataframe"),
        mock.patch("streamlit.metric"),
        mock.patch("streamlit.tabs", side_effect=_mock_columns),
        mock.patch("streamlit.checkbox", return_value=False),
        mock.patch("streamlit.expander", side_effect=fake_expander),
        # isola conteudo interno dos expanders para manter o teste focado
        mock.patch("motor_expansao.dashboard.pages.render_analise_territorial"),
        mock.patch("motor_expansao.dashboard.pages.render_ranking_priorizacao"),
    ):
        streamlit_app.render_mapa_territorial(
            df,
            selected_ufs=["SP"],
            selected_cities=[],
            city_summary=city_summary,
            uf_summary=uf_summary,
        )

    assert any("Analise" in e for e in expanders_created), f"Expanders criados: {expanders_created}"
    assert any("Ranking" in e for e in expanders_created), f"Expanders criados: {expanders_created}"


# ── Testes do Bloco 6: hardening de cache, invariante de score e limite de pontos ──

def test_loaders_com_cache_tem_metodo_clear():
    """Todos os loaders de dados criticos devem usar cache do Streamlit (expoe .clear)."""
    loaders = [
        streamlit_app.load_data,
        streamlit_app.load_hybrid_data,
        streamlit_app.load_estrutural_pop,
        streamlit_app.build_dashboard_dataset,
        streamlit_app.load_competitors,
        streamlit_app.load_ultra,
        streamlit_app.load_carteira,
        streamlit_app.load_plano,
        streamlit_app.load_plano_dominio,
    ]
    for fn in loaders:
        assert hasattr(fn, "clear"), f"Loader sem cache: {fn.__name__}"


def test_score_priorizacao_invariante_enrich_e_carteira():
    """score_priorizacao nao deve ser alterado pelo enrich nem pelo load_carteira."""
    base_df = pd.DataFrame([{
        "hex_id": "h1",
        "lat": -23.55, "lng": -46.63,
        "uf": "SP", "cidade": "Sao Paulo", "regiao": "SE",
        "score_priorizacao": 88.5,
        "hex_score_estrutural": 84.0,
        "ajuste_executivo": 4.5,
        "faixa_oportunidade": "alta",
        "flag_viavel": True, "flag_prioridade": True,
        "rank_brasil": 1, "rank_uf": 1, "rank_cidade": 1,
        "renda_per_capita": 6000.0, "populacao_proxy": 20_000.0,
    }])
    enriched = streamlit_app.enrich_dashboard_data(base_df)
    assert float(enriched.loc[0, "score_priorizacao"]) == 88.5
    assert float(enriched.loc[0, "hex_score_estrutural"]) == 84.0


def test_map_point_limit_respeitado_no_mapa_hibrido():
    """build_hybrid_map_figure: recorte que satura MAP_POINT_LIMIT cai no cap
    reduzido (MAP_POINT_LIMIT_LARGE) — mitigacao OOM client-side em UF grande."""
    from motor_expansao.dashboard.constants import MAP_POINT_LIMIT, MAP_POINT_LIMIT_LARGE

    df = _hybrid_rows(MAP_POINT_LIMIT + 100)
    assert df["hex_id"].nunique() > MAP_POINT_LIMIT
    deck, n = streamlit_app.build_hybrid_map_figure(df, selected_ufs=[], selected_cities=[])
    assert deck is not None
    # Recorte satura o cap global -> cap efetivo reduzido (18k), nao 35k.
    assert n == MAP_POINT_LIMIT_LARGE
    assert n <= MAP_POINT_LIMIT


def test_downsample_map_index_respeita_cap_dedup_e_ordem():
    """O helper deve ordenar pela chave, deduplicar opcionalmente e respeitar o cap."""
    from motor_expansao.dashboard.components import _downsample_map_index

    key = pd.DataFrame(
        {
            "hex_id": ["a", "a", "b", "c", "d"],
            "score": [10.0, 10.0, 50.0, 30.0, 20.0],
        }
    )
    idx_sem_dedup = _downsample_map_index(key, sort_columns=["score"], ascending=[False], limit=3)
    assert key.loc[idx_sem_dedup, "hex_id"].tolist() == ["b", "c", "d"]

    idx_dedup = _downsample_map_index(
        key, sort_columns=["score"], ascending=[False], limit=10, dedup_column="hex_id"
    )
    assert key.loc[idx_dedup, "hex_id"].tolist() == ["b", "c", "d", "a"]


def test_build_map_figure_downsample_mantem_exatamente_o_top_por_prioridade():
    """O downsample antes do cap deve manter exatamente os top-N hexes por
    prioridade. Para recorte que satura MAP_POINT_LIMIT, N = cap efetivo reduzido
    (MAP_POINT_LIMIT_LARGE) — intencao original (top-N por prioridade) preservada."""
    from motor_expansao.dashboard.constants import (
        MAP_POINT_LIMIT,
        MAP_POINT_LIMIT_LARGE,
        MAP_SORT_ASCENDING,
        MAP_SORT_COLUMNS,
    )

    extra = 40
    total = MAP_POINT_LIMIT + extra
    rows = [
        _hex_row(
            f"sp_{i:06d}",
            -23.55 + i * 0.0005,
            -46.63 + i * 0.0005,
            # score decrescente: as primeiras linhas tem maior prioridade
            score_priorizacao=float(total - i),
        )
        for i in range(total)
    ]
    df = pd.DataFrame(rows)
    assert df["hex_id"].nunique() == total
    # recorte satura MAP_POINT_LIMIT -> cap efetivo reduzido (18k)
    assert total > MAP_POINT_LIMIT

    deck, n = streamlit_app.build_map_figure(df, selected_ufs=["SP"], selected_cities=[])
    assert deck is not None
    assert n == MAP_POINT_LIMIT_LARGE

    rendered = set(pd.DataFrame(deck.layers[0].data)["hex_id"])
    sort_cols = [c for c in MAP_SORT_COLUMNS if c in df.columns]
    asc = [MAP_SORT_ASCENDING[MAP_SORT_COLUMNS.index(c)] for c in sort_cols]
    expected_top = set(
        df.sort_values(sort_cols, ascending=asc, kind="stable")
        .head(MAP_POINT_LIMIT_LARGE)["hex_id"]
    )
    assert rendered == expected_top


def _hybrid_rows(n: int, *, score: float = 75.0) -> pd.DataFrame:
    """DataFrame sintetico de n hexes validos para os builders hibrido/residual.

    Espalha os pontos numa grade ampla (~0.05 graus de passo) para garantir n
    hexes res-7 DISTINTOS — offsets pequenos colapsam multiplos pontos no mesmo hex.
    """
    import h3

    rows = []
    base_lat, base_lng = -23.55, -46.63
    side = int(n**0.5) + 1
    for i in range(n):
        lat = base_lat + (i // side) * 0.05
        lng = base_lng + (i % side) * 0.05
        hex_id = h3.latlng_to_cell(lat, lng, 7)
        rows.append({
            "hex_id": hex_id,
            "lat": lat, "lng": lng,
            "uf": "SP", "nome_municipio": "Sao Paulo",
            "score_setor_2022_calibrado": score,
            "score_priorizacao": 80.0,
            "score_expansao_hibrido": 82.0,
            "densidade_pop_setor_hab_km2": 9_000,
            "qualidade_join_uf": "A",
            "flag_join_uf_restrito": False,
            "flag_baixa_pop_setor": False,
            "flag_outlier_espacial": False,
            "causa_outlier_espacial": pd.NA,
            "coverage_pct_setor_2022": 95.0,
            "motivo_nao_elegivel_censo": pd.NA,
            "elegibilidade_hibrida": "Elegivel",
            "rank_hex_intraurbano": i + 1,
            "top_hex_intraurbano": True,
            "top_oportunidade_municipio": True,
            "populacao_proxy": 12_000,
            "renda_per_capita": 3_500,
            "pop_total_setor_2022": 12_345,
            "renda_per_capita_setor_2022_calibrada": 6_789,
            "flag_pop_min_5k": True,
            "score_oportunidade_residual": 55.0,
            "oferta_efetiva_disponivel": 400.0,
            "quartil_oportunidade_residual": "Q3",
        })
    return pd.DataFrame(rows).drop_duplicates(subset=["hex_id"])


def test_cap_reduzido_para_uf_grande_no_mapa_m1():
    """BLK-FIX-03: recorte M1 que satura MAP_POINT_LIMIT cai no cap reduzido."""
    from motor_expansao.dashboard.constants import MAP_POINT_LIMIT, MAP_POINT_LIMIT_LARGE

    total = MAP_POINT_LIMIT + 100
    rows = [
        _hex_row(f"sp_{i:06d}", -23.55 + i * 0.0005, -46.63 + i * 0.0005, score_priorizacao=float(total - i))
        for i in range(total)
    ]
    df = pd.DataFrame(rows)
    assert df["hex_id"].nunique() > MAP_POINT_LIMIT

    deck, n = streamlit_app.build_map_figure(df, selected_ufs=["SP"], selected_cities=[])
    assert deck is not None
    assert n <= MAP_POINT_LIMIT_LARGE
    assert n == MAP_POINT_LIMIT_LARGE
    assert len(pd.DataFrame(deck.layers[0].data)) <= MAP_POINT_LIMIT_LARGE


def test_cap_reduzido_para_uf_grande_no_mapa_hibrido_e_residual():
    """BLK-FIX-03: cap reduzido tambem nos builders hibrido e residual."""
    from motor_expansao.dashboard.constants import MAP_POINT_LIMIT, MAP_POINT_LIMIT_LARGE

    df = _hybrid_rows(MAP_POINT_LIMIT + 100)
    assert df["hex_id"].nunique() > MAP_POINT_LIMIT

    deck_h, n_h = streamlit_app.build_hybrid_map_figure(df, selected_ufs=[], selected_cities=[])
    assert deck_h is not None
    assert n_h == MAP_POINT_LIMIT_LARGE
    assert len(pd.DataFrame(deck_h.layers[0].data)) <= MAP_POINT_LIMIT_LARGE

    deck_r, n_r = streamlit_app.build_residual_heatmap_figure(df, selected_ufs=[], selected_cities=[])
    assert deck_r is not None
    assert n_r == MAP_POINT_LIMIT_LARGE
    assert len(pd.DataFrame(deck_r.layers[0].data)) <= MAP_POINT_LIMIT_LARGE


def test_uf_pequena_nao_regride_cap_cheio():
    """BLK-FIX-03 nao-regressao: recorte entre MAP_POINT_LIMIT_LARGE e
    MAP_POINT_LIMIT renderiza TODOS os hexes (cap cheio, sem corte novo)."""
    from motor_expansao.dashboard.constants import MAP_POINT_LIMIT, MAP_POINT_LIMIT_LARGE

    total = 20_000
    assert MAP_POINT_LIMIT_LARGE < total < MAP_POINT_LIMIT
    rows = [
        _hex_row(f"sp_{i:06d}", -23.55 + i * 0.0005, -46.63 + i * 0.0005, score_priorizacao=float(total - i))
        for i in range(total)
    ]
    df = pd.DataFrame(rows)
    assert df["hex_id"].nunique() == total

    deck, n = streamlit_app.build_map_figure(df, selected_ufs=["SP"], selected_cities=[])
    assert deck is not None
    # cap cheio aplicado: sem corte novo, todos os hexes renderizam
    assert n == total


def test_cap_reduzido_simplifica_layer_sem_mudar_cor():
    """BLK-FIX-03: em UF grande o H3HexagonLayer simplifica (auto_highlight/stroked
    False) MAS a cor de fill continua vindo de score_band_to_color (cor inalterada)."""
    from motor_expansao.dashboard.constants import MAP_POINT_LIMIT

    score = 73.0
    total = MAP_POINT_LIMIT + 100
    rows = [
        _hex_row(
            f"sp_{i:06d}", -23.55 + i * 0.0005, -46.63 + i * 0.0005,
            score_priorizacao=score, flag_pop_min_5k=True,
        )
        for i in range(total)
    ]
    df = pd.DataFrame(rows)

    deck, n = streamlit_app.build_map_figure(df, selected_ufs=["SP"], selected_cities=[])
    assert deck is not None
    hex_layer = deck.layers[0]
    assert hex_layer.auto_highlight is False
    assert hex_layer.stroked is False
    # cor NAO mudou: fill continua vindo de score_band_to_color
    expected_color = streamlit_app.score_band_to_color(score)
    layer_df = pd.DataFrame(hex_layer.data)
    first_fill = layer_df["fill_color"].iloc[0]
    assert list(first_fill) == list(expected_color)


def test_caption_capped_reflete_cap_efetivo():
    """BLK-FIX-03: o caption capped exibe o cap efetivo (18k em UF grande, 35k caso contrario)."""
    from motor_expansao.dashboard.constants import MAP_POINT_LIMIT, MAP_POINT_LIMIT_LARGE
    from motor_expansao.dashboard.utils import format_int

    cap_large = streamlit_app.build_map_scope_caption(
        MAP_POINT_LIMIT_LARGE, selected_ufs=["SP"], capped=True, effective_cap=MAP_POINT_LIMIT_LARGE
    )
    assert format_int(MAP_POINT_LIMIT_LARGE) in cap_large

    cap_full = streamlit_app.build_map_scope_caption(
        MAP_POINT_LIMIT, selected_ufs=["SP"], capped=True, effective_cap=MAP_POINT_LIMIT
    )
    assert format_int(MAP_POINT_LIMIT) in cap_full


def _map_row(hex_id: str, lat: float, lng: float) -> dict:
    return {
        "hex_id": hex_id, "lat": lat, "lng": lng, "cidade": "X", "nome_municipio": "X",
        "uf": "SP", "faixa_oportunidade": "alta", "score_priorizacao": 80.0,
        "hex_score_estrutural": 75.0, "flag_viavel": True, "flag_prioridade": True,
        "score_setor_2022_calibrado": 85.0, "coverage_pct_setor_2022": 97.0,
        "qualidade_join_uf": "A", "flag_censo_disponivel": True, "populacao_proxy": 12_000,
        "renda_per_capita": 3_500, "pop_total_setor_2022": 12_345,
        "renda_per_capita_setor_2022_calibrada": 6_789, "flag_pop_min_5k": True,
        "sam_fitness_potencial": 540.0, "oferta_consumida_mercado_estimada": 200.0,
        "oferta_consumida_ultra_real": 25.0, "oferta_efetiva_disponivel": 300.0,
        "share_ultra_estimado_hex": 0.111, "score_oportunidade_residual": 12.0,
        "quartil_oportunidade_residual": "Q3",
    }


def test_caption_nao_amostrado_em_recorte_18k_a_35k(monkeypatch):
    """FU1: recorte na janela (LARGE, FULL] nao sofre corte -> _ultra_capped is False.

    A heuristica antiga (n_points >= MAP_POINT_LIMIT_LARGE) marcava "amostrado"
    nessa janela mesmo sem corte. Usa limites pequenos equivalentes (janela 10<n<=30)
    para um caso leve e deterministico; o corte real e len(key) > effective_limit.
    """
    from motor_expansao.dashboard import components

    monkeypatch.setattr(components, "MAP_POINT_LIMIT_LARGE", 10)
    monkeypatch.setattr(components, "MAP_POINT_LIMIT", 30)

    center = h3.latlng_to_cell(-23.55, -46.63, 7)
    cells = list(h3.grid_disk(center, 2))  # 19 hexes distintos, dentro de (10, 30]
    assert 10 < len(cells) <= 30
    df = pd.DataFrame([_map_row(c, *h3.cell_to_latlng(c)) for c in cells])

    deck, n = streamlit_app.build_map_figure(df, selected_ufs=["SP"], selected_cities=[])

    assert deck is not None
    assert n == len(cells)  # nenhum hex cortado
    assert deck._ultra_capped is False
    assert deck._ultra_effective_cap == 30


def test_caption_amostrado_quando_satura_cap():
    """FU1: recorte > MAP_POINT_LIMIT (35k) satura o cap -> _ultra_capped True, cap 18k."""
    from motor_expansao.dashboard.constants import MAP_POINT_LIMIT, MAP_POINT_LIMIT_LARGE

    center = h3.latlng_to_cell(-23.55, -46.63, 7)
    cells = list(h3.grid_disk(center, 110))  # ~36.6k hexes reais distintos
    assert len(cells) > MAP_POINT_LIMIT
    df = pd.DataFrame([_map_row(c, *h3.cell_to_latlng(c)) for c in cells])

    deck, n = streamlit_app.build_map_figure(df, selected_ufs=["SP"], selected_cities=[])

    assert deck is not None
    assert deck._ultra_capped is True
    assert deck._ultra_effective_cap == MAP_POINT_LIMIT_LARGE == 18000
    assert n == MAP_POINT_LIMIT_LARGE


def test_build_ultra_presence_map_retorna_none_sem_dados():
    deck, n = streamlit_app.build_ultra_presence_map(
        None, selected_ufs=[], selected_cities=[]
    )
    assert deck is None
    assert n == 0

    deck, n = streamlit_app.build_ultra_presence_map(
        pd.DataFrame(), selected_ufs=[], selected_cities=[]
    )
    assert deck is None
    assert n == 0


def test_build_ultra_presence_map_nao_usa_h3hexagonlayer():
    ultra_df = pd.DataFrame([
        {"lat": -23.55, "lng": -46.63, "nome_unidade": "Ultra SP Centro", "cidade": "Sao Paulo", "uf": "SP"},
        {"lat": -15.77, "lng": -47.93, "nome_unidade": "Ultra BSB", "cidade": "Brasilia", "uf": "DF"},
    ])
    deck, n = streamlit_app.build_ultra_presence_map(
        ultra_df, selected_ufs=[], selected_cities=[]
    )
    assert deck is not None
    assert n == 2
    layer_types = [type(layer).__name__ for layer in deck.layers]
    assert "H3HexagonLayer" not in str(deck.to_json())
    assert any("IconLayer" in t or "icon" in str(layer.type).lower() for layer, t in zip(deck.layers, layer_types, strict=False))


def test_build_ultra_presence_map_filtra_por_uf():
    ultra_df = pd.DataFrame([
        {"lat": -23.55, "lng": -46.63, "nome_unidade": "Ultra SP", "cidade": "Sao Paulo", "uf": "SP"},
        {"lat": -15.77, "lng": -47.93, "nome_unidade": "Ultra DF", "cidade": "Brasilia", "uf": "DF"},
    ])
    deck, n = streamlit_app.build_ultra_presence_map(
        ultra_df, selected_ufs=["SP"], selected_cities=[]
    )
    assert deck is not None
    assert n == 1
    icon_data = pd.DataFrame(deck.layers[0].data)
    assert all(icon_data["tooltip_title"].str.contains("Ultra SP"))


def test_build_ultra_presence_map_estado_vazio_sem_uf_match():
    ultra_df = pd.DataFrame([
        {"lat": -23.55, "lng": -46.63, "nome_unidade": "Ultra SP", "cidade": "Sao Paulo", "uf": "SP"},
    ])
    deck, n = streamlit_app.build_ultra_presence_map(
        ultra_df, selected_ufs=["RJ"], selected_cities=[]
    )
    assert deck is None
    assert n == 0


def test_build_ultra_network_kpis_retorna_chaves_esperadas():
    df = pd.DataFrame([{"score_priorizacao": 70.0, "uf": "SP", "cidade": "Campinas"}])
    ultra_df = pd.DataFrame([
        {"lat": -22.9, "lng": -47.06, "nome_unidade": "Ultra Campinas", "cidade": "Campinas", "uf": "SP"},
    ])
    carteira_df = pd.DataFrame([
        {
            "uf": "SP",
            "nome_municipio": "Campinas",
            "oferta_efetiva_disponivel": 1000.0,
            "score_oportunidade_residual": 65.0,
            "n_unidades_ultra_performance_hex": 0,
        }
    ])
    result = streamlit_app.build_ultra_network_kpis(
        df,
        ultra_df,
        carteira_df,
        None,
        selected_ufs=["SP"],
        selected_cities=["Campinas"],
    )
    assert set(result.keys()) == {"ultra_units", "cidades_com_ultra", "residual_total", "opps_sem_ultra", "ancoras_dominio", "score_medio_m1"}
    assert result["ultra_units"] == "1"
    assert result["residual_total"] == "1.000"
    assert result["opps_sem_ultra"] == "1"
    assert result["ancoras_dominio"] == "-"


def test_build_residual_by_uf_figure_retorna_none_sem_dados():
    assert streamlit_app.build_residual_by_uf_figure(None) is None
    assert streamlit_app.build_residual_by_uf_figure(pd.DataFrame()) is None


def test_build_residual_score_dist_figure_retorna_none_sem_coluna():
    df_sem_col = pd.DataFrame([{"uf": "SP", "score_priorizacao": 70.0}])
    assert streamlit_app.build_residual_score_dist_figure(df_sem_col) is None
    assert streamlit_app.build_residual_score_dist_figure(None) is None


def test_build_top_cities_residual_figure_retorna_figura_com_dados():
    cart = pd.DataFrame([
        {"nome_municipio": "Campinas", "uf": "SP", "oferta_efetiva_disponivel": 2000.0, "n_unidades_ultra_performance_hex": 0},
        {"nome_municipio": "Goiania", "uf": "GO", "oferta_efetiva_disponivel": 1500.0, "n_unidades_ultra_performance_hex": 0},
        {"nome_municipio": "Curitiba", "uf": "PR", "oferta_efetiva_disponivel": 1200.0, "n_unidades_ultra_performance_hex": 0},
        {"nome_municipio": "Fortaleza", "uf": "CE", "oferta_efetiva_disponivel": 900.0, "n_unidades_ultra_performance_hex": 0},
        {"nome_municipio": "Manaus", "uf": "AM", "oferta_efetiva_disponivel": 800.0, "n_unidades_ultra_performance_hex": 0},
    ])
    fig = streamlit_app.build_top_cities_residual_figure(cart)
    assert fig is not None
    assert streamlit_app.build_top_cities_residual_figure(None) is None


# ── Testes do Bloco 4: haversine_km e analisar_entorno_ponto ──────────────────

def test_haversine_km_zero_para_mesmo_ponto():
    import numpy as np
    lat, lng = -23.5, -46.6
    dist = streamlit_app.haversine_km(lat, np.array([lat]), lng, np.array([lng]))
    assert float(dist[0]) == pytest.approx(0.0, abs=1e-6)


def test_haversine_km_distancia_conhecida():
    """SP (~-23.55, -46.63) a RJ (~-22.90, -43.17) ≈ 360 km."""
    import numpy as np
    dist = streamlit_app.haversine_km(-23.55, np.array([-22.90]), -46.63, np.array([-43.17]))
    assert 340 < float(dist[0]) < 380


def test_analisar_entorno_ponto_retorna_vazio_sem_dados():
    result = streamlit_app.analisar_entorno_ponto(-23.5, -46.6, pd.DataFrame())
    assert result["n_hexes"] == 0
    assert result["residual_total"] is None
    assert result["raio_km"] == pytest.approx(1.6)
    assert result["area_km2"] == pytest.approx(3.14159265358979 * 1.6 ** 2, abs=0.01)
    assert result["hexes_entorno"].empty


def test_analisar_entorno_ponto_inclui_hex_proximo_e_exclui_distante():
    # centro: -23.5, -46.6
    # hex_near: mesmo ponto → dist ≈ 0 km (dentro de 1.6 km)
    # hex_far:  offset 0.05° lat ≈ 5.5 km (fora)
    lat_c, lng_c = -23.5, -46.6
    df = pd.DataFrame([
        {
            "hex_id": "near", "lat": lat_c, "lng": lng_c,
            "score_priorizacao": 80.0, "oferta_efetiva_disponivel": 500.0,
            "score_oportunidade_residual": 40.0,
        },
        {
            "hex_id": "far", "lat": lat_c - 0.05, "lng": lng_c,
            "score_priorizacao": 90.0, "oferta_efetiva_disponivel": 200.0,
            "score_oportunidade_residual": 60.0,
        },
    ])
    result = streamlit_app.analisar_entorno_ponto(lat_c, lng_c, df, raio_km=1.6)
    assert result["n_hexes"] == 1
    assert result["hexes_entorno"].iloc[0]["hex_id"] == "near"
    assert result["residual_total"] == pytest.approx(500.0)
    assert result["score_m1_medio"] == pytest.approx(80.0)
    assert result["score_residual_medio"] == pytest.approx(40.0)


def test_analisar_entorno_ponto_dois_hexes_no_raio_ordenados_por_distancia():
    lat_c, lng_c = -23.5, -46.6
    # hex_a: muito proximo; hex_b: um pouco mais longe (mas dentro)
    df = pd.DataFrame([
        {
            "hex_id": "b", "lat": lat_c - 0.01, "lng": lng_c,
            "score_priorizacao": 75.0, "oferta_efetiva_disponivel": 300.0,
            "score_oportunidade_residual": 30.0,
        },
        {
            "hex_id": "a", "lat": lat_c, "lng": lng_c,
            "score_priorizacao": 82.0, "oferta_efetiva_disponivel": 700.0,
            "score_oportunidade_residual": 70.0,
        },
    ])
    result = streamlit_app.analisar_entorno_ponto(lat_c, lng_c, df, raio_km=1.6)
    assert result["n_hexes"] == 2
    # ordenado por distancia ascendente → hex_a (dist=0) antes de hex_b
    assert result["hexes_entorno"].iloc[0]["hex_id"] == "a"
    assert result["residual_total"] == pytest.approx(1000.0)
    assert result["score_m1_max"] == pytest.approx(82.0)
    assert result["score_m1_medio"] == pytest.approx(78.5)


def test_analisar_entorno_ponto_conta_concorrentes_e_ultra():
    lat_c, lng_c = -23.5, -46.6
    hex_df = pd.DataFrame([
        {"hex_id": "h1", "lat": lat_c, "lng": lng_c, "score_priorizacao": 80.0},
    ])
    competitors = pd.DataFrame([
        {"rede": "smart_fit", "lat": lat_c + 0.005, "lng": lng_c},   # ~0.55 km → dentro
        {"rede": "bluefit", "lat": lat_c - 0.1, "lng": lng_c},       # ~11 km → fora
    ])
    ultra = pd.DataFrame([
        {"nome_unidade": "Ultra A", "lat": lat_c, "lng": lng_c + 0.003},  # ~0.28 km → dentro
        {"nome_unidade": "Ultra B", "lat": lat_c + 0.08, "lng": lng_c},  # ~8.9 km → fora
    ])
    dominio = pd.DataFrame([
        {"hex_id": "d1", "lat": lat_c + 0.01, "lng": lng_c},   # ~1.11 km → dentro
        {"hex_id": "d2", "lat": lat_c + 0.03, "lng": lng_c},   # ~3.3 km → fora
    ])
    result = streamlit_app.analisar_entorno_ponto(
        lat_c, lng_c, hex_df, raio_km=1.6,
        competitors_df=competitors,
        ultra_df=ultra,
        dominio_df=dominio,
    )
    assert result["n_concorrentes"] == 1
    assert result["n_ultra"] == 1
    assert result["n_ancoras_dominio"] == 1


def test_analisar_entorno_ponto_sem_colunas_residual_retorna_none():
    lat_c, lng_c = -23.5, -46.6
    df = pd.DataFrame([
        {"hex_id": "h1", "lat": lat_c, "lng": lng_c, "score_priorizacao": 80.0},
    ])
    result = streamlit_app.analisar_entorno_ponto(lat_c, lng_c, df)
    assert result["n_hexes"] == 1
    assert result["residual_total"] is None
    assert result["score_residual_medio"] is None


def test_analisar_entorno_ponto_exportado_via_streamlit_app():
    assert hasattr(streamlit_app, "analisar_entorno_ponto")
    assert callable(streamlit_app.analisar_entorno_ponto)
    assert hasattr(streamlit_app, "haversine_km")
    assert callable(streamlit_app.haversine_km)


# ── Testes do Bloco 5: UI de Analise Pontual ─────────────────────────────────

def test_build_analise_pontual_map_retorna_deck_com_camadas():
    """build_analise_pontual_map deve retornar Deck com layer de hexes + circulo + ponto."""
    import h3
    lat, lng = -23.55, -46.63
    hex_id = h3.latlng_to_cell(lat, lng, 7)
    hexes = pd.DataFrame([{"hex_id": hex_id}])

    deck = streamlit_app.build_analise_pontual_map(lat, lng, 1.6, hexes)

    assert deck is not None
    # hex layer + circulo + ponto central
    assert len(deck.layers) == 3
    assert deck.initial_view_state.latitude == pytest.approx(lat)
    assert deck.initial_view_state.longitude == pytest.approx(lng)
    assert deck.initial_view_state.zoom == pytest.approx(12.0)


def test_build_analise_pontual_map_sem_hexes_retorna_deck_com_2_camadas():
    """Sem hexes no raio, deve retornar apenas camadas de circulo e ponto central."""
    deck = streamlit_app.build_analise_pontual_map(-15.77, -47.93, 1.6, pd.DataFrame())

    assert deck is not None
    # sem hex layer: apenas circulo + ponto
    assert len(deck.layers) == 2


def test_build_analise_pontual_map_inclui_pins_no_raio():
    lat, lng = -23.55, -46.63
    competitors = pd.DataFrame([
        {
            "rede": "smart_fit",
            "rede_label": "Smart Fit",
            "nome_unidade": "Smart Paulista",
            "lat": -23.551,
            "lng": -46.631,
            "cidade": "Sao Paulo",
            "uf": "SP",
            "arquivo_origem": "unidades_smart_fit.csv",
        },
        {
            "rede": "bluefit",
            "rede_label": "Bluefit",
            "nome_unidade": "Blue Rio",
            "lat": -22.90,
            "lng": -43.20,
            "cidade": "Rio de Janeiro",
            "uf": "RJ",
            "arquivo_origem": "unidades_bluefit.csv",
        },
    ])
    ultra = pd.DataFrame([
        {
            "nome_unidade": "Ultra Paulista",
            "lat": -23.552,
            "lng": -46.632,
            "cidade": "Sao Paulo",
            "uf": "SP",
            "arquivo_origem": "Ultra.csv",
        },
        {
            "nome_unidade": "Ultra Rio",
            "lat": -22.90,
            "lng": -43.20,
            "cidade": "Rio de Janeiro",
            "uf": "RJ",
            "arquivo_origem": "Ultra.csv",
        },
    ])

    deck = streamlit_app.build_analise_pontual_map(
        lat,
        lng,
        1.6,
        pd.DataFrame(),
        competitors_df=competitors,
        ultra_df=ultra,
    )

    assert deck is not None
    assert len(deck.layers) == 4
    icon_layers = [layer for layer in deck.layers if str(layer.type) == "IconLayer"]
    assert len(icon_layers) == 2
    competitor_data = pd.DataFrame(icon_layers[0].data)
    ultra_data = pd.DataFrame(icon_layers[1].data)
    # BLK-FIX-07: payload enxuto nao carrega nome_unidade cru; o nome vai no
    # tooltip_title. O recorte por raio (so os pins de SP) e preservado.
    assert competitor_data["tooltip_title"].tolist() == ["Smart Fit: Smart Paulista"]
    assert ultra_data["tooltip_title"].tolist() == ["Ultra Academia: Ultra Paulista"]


def test_build_analise_pontual_map_nao_inclui_pins_fora_do_raio():
    competitors = pd.DataFrame([
        {
            "rede": "smart_fit",
            "rede_label": "Smart Fit",
            "nome_unidade": "Smart Rio",
            "lat": -22.90,
            "lng": -43.20,
            "cidade": "Rio de Janeiro",
            "uf": "RJ",
            "arquivo_origem": "unidades_smart_fit.csv",
        }
    ])
    ultra = pd.DataFrame([
        {
            "nome_unidade": "Ultra Rio",
            "lat": -22.90,
            "lng": -43.20,
            "cidade": "Rio de Janeiro",
            "uf": "RJ",
            "arquivo_origem": "Ultra.csv",
        }
    ])

    deck = streamlit_app.build_analise_pontual_map(
        -23.55,
        -46.63,
        1.6,
        pd.DataFrame(),
        competitors_df=competitors,
        ultra_df=ultra,
    )

    assert deck is not None
    assert len(deck.layers) == 2
    assert all(str(layer.type) != "IconLayer" for layer in deck.layers)


def test_render_analise_pontual_sem_coordenada_exibe_info():
    """render_analise_pontual sem search_pin deve mostrar info de instrucao."""
    import unittest.mock as mock

    df = pd.DataFrame([{"hex_id": "h1", "lat": -23.55, "lng": -46.63, "score_priorizacao": 80.0}])

    with mock.patch("streamlit.info") as info_mock, mock.patch("streamlit.caption"):
        streamlit_app.render_analise_pontual(None, df)

    info_mock.assert_called_once()
    msg = info_mock.call_args[0][0]
    assert "coordenada" in msg.lower() or "sidebar" in msg.lower()


def test_render_analise_pontual_com_coordenada_exibe_kpis():
    """render_analise_pontual com search_pin deve chamar st.metric para os KPIs."""
    import unittest.mock as mock

    lat, lng = -23.55, -46.63
    df = pd.DataFrame([{
        "hex_id": "h1",
        "lat": lat,
        "lng": lng,
        "score_priorizacao": 80.0,
        "oferta_efetiva_disponivel": 500.0,
        "score_oportunidade_residual": 42.0,
    }])

    metric_calls = []

    def fake_columns(n_or_list, **kw):
        n = n_or_list if isinstance(n_or_list, int) else len(n_or_list)
        cols = []
        for _ in range(n):
            m = mock.MagicMock()
            m.metric = mock.MagicMock(side_effect=lambda label, value, **kw: metric_calls.append(label))
            cols.append(m)
        return cols

    with (
        mock.patch("streamlit.columns", side_effect=fake_columns),
        mock.patch("streamlit.caption"),
        mock.patch("streamlit.markdown"),
        mock.patch("streamlit.info"),
        mock.patch("streamlit.pydeck_chart"),
        mock.patch("streamlit.dataframe"),
    ):
        streamlit_app.render_analise_pontual((lat, lng), df)

    labels = [c.lower() for c in metric_calls]
    assert any("hex" in label for label in labels)
    assert any("residual" in label or "score" in label for label in labels)


def test_render_analise_pontual_exportado_via_streamlit_app():
    assert hasattr(streamlit_app, "render_analise_pontual")
    assert callable(streamlit_app.render_analise_pontual)


# ── Testes do Bloco 6: captura de coordenada por clique no mapa ───────────────

class _MockSelection:
    def __init__(self, objects: dict):
        self.objects = objects


class _MockMapEvent:
    def __init__(self, objects: dict):
        self.selection = _MockSelection(objects)


def test_extract_click_coord_resolve_centroide_do_hex_id_da_selecao():
    """Branch A: o payload do H3HexagonLayer traz hex_id; resolve o centroide via h3."""
    hex_id = h3.latlng_to_cell(-23.55, -46.63, 7)
    centroide = h3.cell_to_latlng(hex_id)
    event = _MockMapEvent({"hex_layer": [{"hex_id": hex_id, "score_priorizacao": 80.0}]})
    result = streamlit_app._extract_click_coord_from_selection(event)
    assert result == pytest.approx(centroide)


def test_extract_click_coord_retorna_none_sem_selecao():
    event = _MockMapEvent({})
    assert streamlit_app._extract_click_coord_from_selection(event) is None


def test_extract_click_coord_resolve_centroide_quando_payload_so_tem_hex_id():
    """Payload sem lat/lng (caso real do _deck_layer_frame): resolve centroide do hex_id."""
    hex_id = h3.latlng_to_cell(-15.79, -47.88, 7)
    centroide = h3.cell_to_latlng(hex_id)
    event = _MockMapEvent({"hex_layer": [{"hex_id": hex_id, "score_priorizacao": 80.0}]})
    result = streamlit_app._extract_click_coord_from_selection(event)
    assert result == pytest.approx(centroide)


def test_extract_click_coord_hex_id_invalido_retorna_none():
    """hex_id que nao e um indice H3 valido -> None (sem excecao)."""
    event = _MockMapEvent({"hex_layer": [{"hex_id": "nao_e_hex", "score_priorizacao": 80.0}]})
    assert streamlit_app._extract_click_coord_from_selection(event) is None


def test_extract_click_coord_retorna_none_para_none():
    assert streamlit_app._extract_click_coord_from_selection(None) is None


def test_extract_click_coord_e_robusto_contra_mock_object():
    """MagicMock (retorno padrao nos testes que mokam pydeck_chart) nao deve causar excecao."""
    import unittest.mock as mock
    mock_event = mock.MagicMock()
    # MagicMock.selection.objects nao e dict -> deve retornar None sem excecao
    result = streamlit_app._extract_click_coord_from_selection(mock_event)
    assert result is None


def test_extract_click_coord_exportado_via_streamlit_app():
    assert hasattr(streamlit_app, "_extract_click_coord_from_selection")
    assert callable(streamlit_app._extract_click_coord_from_selection)


def test_hex_id_to_centroid_hex_invalido_retorna_none():
    assert streamlit_app._hex_id_to_centroid("nao_e_hex") is None


def test_hex_id_to_centroid_idempotente_com_lookup():
    """O centroide resolvido reconverte para o MESMO hex via lookup_hex_by_coord (res 7)."""
    hex_id = h3.latlng_to_cell(-23.55, -46.63, 7)
    centroide = streamlit_app._hex_id_to_centroid(hex_id)
    assert centroide is not None
    lat, lng = centroide
    df = pd.DataFrame({"hex_id": [hex_id], "lat": [lat], "lng": [lng]})
    found = streamlit_app.lookup_hex_by_coord(lat, lng, df)
    assert found is not None
    assert found["hex_id"] == hex_id
    assert found["_not_found"] is False


def test_render_analise_pontual_vazio_menciona_clique_e_sidebar():
    """Estado vazio deve mencionar clique no mapa E campo de coordenada."""
    import unittest.mock as mock

    df = pd.DataFrame([{"hex_id": "h1", "lat": -23.55, "lng": -46.63, "score_priorizacao": 80.0}])

    with mock.patch("streamlit.info") as info_mock, mock.patch("streamlit.caption"):
        streamlit_app.render_analise_pontual(None, df)

    msg = info_mock.call_args[0][0].lower()
    assert "clique" in msg or "mapa" in msg
    assert "coordenada" in msg or "sidebar" in msg


# ── Testes do Bloco 7: hardening final ───────────────────────────────────────

def test_render_visao_executiva_nao_chama_builders_com_hexagonos():
    """render_visao_executiva nao deve chamar build_map_figure nem build_hybrid_map_figure."""
    import unittest.mock as mock

    df = pd.DataFrame([{
        "hex_id": "h1", "lat": -23.55, "lng": -46.63,
        "uf": "SP", "cidade": "Sao Paulo", "regiao": "SE",
        "score_priorizacao": 80.0, "hex_score_estrutural": 75.0, "ajuste_executivo": 5.0,
        "faixa_oportunidade": "alta", "flag_viavel": True, "flag_prioridade": True,
        "rank_brasil": 1, "rank_uf": 1, "rank_cidade": 1,
        "renda_per_capita": 5000.0, "populacao_proxy": 15_000.0,
    }])
    city_summary = pd.DataFrame([{
        "uf": "SP", "cidade": "Sao Paulo", "score_medio": 80.0, "melhor_rank_brasil": 1,
        "oportunidades_viaveis": 3, "renda_per_capita": 5000.0, "populacao_proxy": 15_000.0,
    }])
    uf_summary = pd.DataFrame([{
        "uf": "SP", "oportunidades_viaveis": 3, "score_medio": 80.0,
        "renda_per_capita": 5000.0, "populacao_proxy": 15_000.0,
    }])

    _fake_kpis = {"total_oportunidades_viaveis": "3", "total_hexagonos_priorizados": "1",
                  "uf_lider_oportunidades": "SP", "cidade_lider_score": "Sao Paulo"}
    _fake_answers = {"expandir": "SP", "priorizar": "SP", "evitar": "-",
                     "ufs_priorizar": "SP", "ufs_evitar": "-"}

    with (
        mock.patch("motor_expansao.dashboard.pages.build_map_figure") as map_mock,
        mock.patch("motor_expansao.dashboard.pages.build_hybrid_map_figure") as hybrid_mock,
        mock.patch("motor_expansao.dashboard.pages.build_kpis", return_value=_fake_kpis),
        mock.patch("motor_expansao.dashboard.pages.build_business_answers", return_value=_fake_answers),
        mock.patch("motor_expansao.dashboard.pages.build_ultra_network_kpis",
                   return_value={"ultra_units": "1", "cidades_com_ultra": "1", "score_medio_m1": "80",
                                 "residual_total": "1.000", "opps_sem_ultra": "1", "ancoras_dominio": "-"}),
        mock.patch("motor_expansao.dashboard.pages.render_answer_card"),
        mock.patch("streamlit.columns", side_effect=_mock_columns),
        mock.patch("streamlit.markdown"),
        mock.patch("streamlit.caption"),
        mock.patch("streamlit.metric"),
        mock.patch("streamlit.info"),
        mock.patch("streamlit.pydeck_chart"),
        mock.patch("streamlit.plotly_chart"),
    ):
        streamlit_app.render_visao_executiva(
            df, city_summary, uf_summary,
            selected_ufs=[], selected_cities=[],
        )

    map_mock.assert_not_called()
    hybrid_mock.assert_not_called()


def test_analisar_entorno_ponto_nao_muta_dataframe_input():
    """analisar_entorno_ponto nao deve modificar o DataFrame de entrada."""
    lat_c, lng_c = -23.5, -46.6
    df = pd.DataFrame([{
        "hex_id": "h1", "lat": lat_c, "lng": lng_c,
        "score_priorizacao": 80.0, "oferta_efetiva_disponivel": 500.0,
        "score_oportunidade_residual": 40.0,
    }])
    original_cols = list(df.columns)
    original_shape = df.shape
    original_score = float(df.loc[0, "score_priorizacao"])

    streamlit_app.analisar_entorno_ponto(lat_c, lng_c, df, raio_km=1.6)

    assert list(df.columns) == original_cols
    assert df.shape == original_shape
    assert float(df.loc[0, "score_priorizacao"]) == original_score


def test_score_priorizacao_nao_alterado_por_analise_pontual():
    """score_priorizacao nos dados originais deve ser identico antes e apos analise_entorno_ponto."""
    lat_c, lng_c = -23.5, -46.6
    df = pd.DataFrame([
        {"hex_id": "h1", "lat": lat_c, "lng": lng_c, "score_priorizacao": 88.5},
        {"hex_id": "h2", "lat": lat_c - 0.1, "lng": lng_c, "score_priorizacao": 72.3},
    ])
    scores_antes = df["score_priorizacao"].tolist()

    streamlit_app.analisar_entorno_ponto(lat_c, lng_c, df, raio_km=1.6)

    assert df["score_priorizacao"].tolist() == scores_antes


# ── Testes do Bloco 9: score_band_to_color e padronizacao visual ──────────────

# Testes do Bloco 10: populacao e renda na Analise Pontual

def test_analisar_entorno_ponto_prefere_populacao_setor_2022():
    lat_c, lng_c = -23.5, -46.6
    df = pd.DataFrame([
        {
            "hex_id": "h1",
            "lat": lat_c,
            "lng": lng_c,
            "pop_total_setor_2022": 1200,
            "pop_hex_base": 9000,
            "pop_total": 8000,
            "populacao_proxy": 7000,
            "renda_per_capita_setor_2022_calibrada": 2500,
        },
        {
            "hex_id": "h2",
            "lat": lat_c + 0.005,
            "lng": lng_c,
            "pop_total_setor_2022": 800,
            "pop_hex_base": 6000,
            "pop_total": 5000,
            "populacao_proxy": 4000,
            "renda_per_capita_setor_2022_calibrada": 3500,
        },
    ])

    result = streamlit_app.analisar_entorno_ponto(lat_c, lng_c, df, raio_km=1.6)

    assert result["pop_total_raio"] == pytest.approx(2000.0)
    assert result["fonte_pop_total_raio"] == "setor_2022"
    assert result["n_hexes_com_pop"] == 2
    hexes = result["hexes_entorno"].set_index("hex_id")
    assert hexes.loc["h1", "pop_total_raio_hex"] == pytest.approx(1200.0)
    assert hexes.loc["h1", "fonte_pop_total_raio_hex"] == "setor_2022"


def test_analisar_entorno_ponto_fallback_populacao_misto():
    lat_c, lng_c = -23.5, -46.6
    df = pd.DataFrame([
        {"hex_id": "h1", "lat": lat_c, "lng": lng_c, "pop_hex_base": 1500},
        {"hex_id": "h2", "lat": lat_c + 0.005, "lng": lng_c, "pop_total": 2500},
        {"hex_id": "h3", "lat": lat_c + 0.006, "lng": lng_c, "populacao_proxy": 3500},
    ])

    result = streamlit_app.analisar_entorno_ponto(lat_c, lng_c, df, raio_km=1.6)

    assert result["pop_total_raio"] == pytest.approx(7500.0)
    assert result["fonte_pop_total_raio"] == "misto: pop_hex_base, pop_total, populacao_proxy"
    assert result["n_hexes_com_pop"] == 3


def test_analisar_entorno_ponto_calcula_renda_ponderada_por_populacao():
    lat_c, lng_c = -23.5, -46.6
    df = pd.DataFrame([
        {
            "hex_id": "h1",
            "lat": lat_c,
            "lng": lng_c,
            "pop_total_setor_2022": 100,
            "renda_per_capita_setor_2022_calibrada": 1000,
            "renda_per_capita": 9000,
        },
        {
            "hex_id": "h2",
            "lat": lat_c + 0.005,
            "lng": lng_c,
            "pop_total_setor_2022": 300,
            "renda_per_capita_setor_2022_calibrada": 3000,
            "renda_per_capita": 8000,
        },
    ])

    result = streamlit_app.analisar_entorno_ponto(lat_c, lng_c, df, raio_km=1.6)

    assert result["renda_per_capita_media_raio"] == pytest.approx(2500.0)
    assert result["metodo_renda_raio"] == "ponderada_populacao"
    assert result["n_hexes_com_renda"] == 2


def test_analisar_entorno_ponto_usa_media_simples_de_renda_sem_populacao():
    lat_c, lng_c = -23.5, -46.6
    df = pd.DataFrame([
        {"hex_id": "h1", "lat": lat_c, "lng": lng_c, "renda_per_capita": 2000},
        {"hex_id": "h2", "lat": lat_c + 0.005, "lng": lng_c, "renda_per_capita": 4000},
    ])

    result = streamlit_app.analisar_entorno_ponto(lat_c, lng_c, df, raio_km=1.6)

    assert result["pop_total_raio"] is None
    assert result["fonte_pop_total_raio"] == "ausente"
    assert result["renda_per_capita_media_raio"] == pytest.approx(3000.0)
    assert result["metodo_renda_raio"] == "media_simples"


def test_analisar_entorno_ponto_sem_colunas_pop_renda_sinaliza_ausente():
    lat_c, lng_c = -23.5, -46.6
    df = pd.DataFrame([{"hex_id": "h1", "lat": lat_c, "lng": lng_c}])

    result = streamlit_app.analisar_entorno_ponto(lat_c, lng_c, df, raio_km=1.6)

    assert result["pop_total_raio"] is None
    assert result["fonte_pop_total_raio"] == "ausente"
    assert result["renda_per_capita_media_raio"] is None
    assert result["metodo_renda_raio"] == "ausente"


# Testes do Bloco 9: score_band_to_color e padronizacao visual

def test_score_band_to_color_nan_retorna_cinza():
    assert streamlit_app.score_band_to_color(float("nan")) == [120, 120, 140, 70]
    assert streamlit_app.score_band_to_color(None) == [120, 120, 140, 70]


def test_score_band_to_color_bordas_de_faixa():
    c0 = streamlit_app.score_band_to_color(0)
    c9_99 = streamlit_app.score_band_to_color(9.99)
    c10 = streamlit_app.score_band_to_color(10)
    c49_9 = streamlit_app.score_band_to_color(49.9)
    c50 = streamlit_app.score_band_to_color(50)
    c89_9 = streamlit_app.score_band_to_color(89.9)
    c90 = streamlit_app.score_band_to_color(90)
    c100 = streamlit_app.score_band_to_color(100)

    assert c0 == c9_99, "0 e 9.99 devem estar na mesma faixa (0-10)"
    assert c0 != c10, "9.99 e 10 devem estar em faixas distintas"
    assert c49_9 != c50, "49.9 e 50 devem estar em faixas distintas"
    assert c89_9 != c90, "89.9 e 90 devem estar em faixas distintas"
    assert c90 == c100, "90 e 100 devem cair na mesma faixa (90-100)"


def test_score_band_to_color_escala_ascendente():
    """Scores mais altos devem ter cores mais 'verdes' (componente verde maior que vermelho)."""
    cor_baixa = streamlit_app.score_band_to_color(5)
    cor_alta = streamlit_app.score_band_to_color(95)
    r_baixa, g_baixa, b_baixa = cor_baixa[:3]
    r_alta, g_alta, b_alta = cor_alta[:3]
    assert g_alta > r_alta, "score alto deve ser mais verde do que vermelho"
    assert r_baixa > g_baixa, "score baixo deve ser mais vermelho do que verde"


def test_score_band_to_color_retorna_4_elementos():
    cor = streamlit_app.score_band_to_color(50)
    assert len(cor) == 4
    assert all(0 <= v <= 255 for v in cor)


def test_build_unified_map_modo_m1_usa_score_priorizacao_para_cor():
    """No modo M1 dois hexes com scores bem distintos devem ter cores diferentes."""
    import h3
    hex1 = h3.latlng_to_cell(-23.55, -46.63, 7)
    hex2 = h3.latlng_to_cell(-23.65, -46.50, 7)
    assert hex1 != hex2

    def _row(hex_id, lat, lng, score):
        return {
            "hex_id": hex_id, "lat": lat, "lng": lng,
            "uf": "SP", "cidade": "Sao Paulo", "regiao": "SE",
            "score_priorizacao": score, "hex_score_estrutural": score - 2,
            "ajuste_executivo": 2.0, "faixa_oportunidade": "alta",
            "flag_viavel": True, "flag_prioridade": True,
            "rank_brasil": 1, "rank_uf": 1, "rank_cidade": 1,
            "renda_per_capita": 5000.0, "populacao_proxy": 15_000.0,
        }

    df = pd.DataFrame([_row(hex1, -23.55, -46.63, 5.0), _row(hex2, -23.65, -46.50, 95.0)])
    deck, n = streamlit_app.build_unified_map_figure(df, color_mode="m1", selected_ufs=["SP"], selected_cities=[])
    assert deck is not None and n == 2
    rendered = pd.DataFrame(deck.layers[0].data).set_index("hex_id")
    assert rendered.loc[hex1, "fill_color"] != rendered.loc[hex2, "fill_color"]


def test_build_unified_map_hibrido_usa_score_expansao_hibrido_nao_residual():
    """Modo hibrido deve colorir por score_expansao_hibrido, nao score_oportunidade_residual."""
    import h3
    hex1 = h3.latlng_to_cell(-23.55, -46.63, 7)
    hex2 = h3.latlng_to_cell(-23.65, -46.50, 7)
    assert hex1 != hex2
    # hex1: hibrido alto / residual baixo; hex2: hibrido baixo / residual alto
    df = pd.DataFrame([
        _hybrid_row_unified(hex1, -23.55, -46.63, score_expansao_hibrido=90.0, score_oportunidade_residual=10.0),
        _hybrid_row_unified(hex2, -23.65, -46.50, score_expansao_hibrido=10.0, score_oportunidade_residual=90.0),
    ])
    deck, n = streamlit_app.build_unified_map_figure(df, color_mode="hibrido", selected_ufs=[], selected_cities=[])
    assert deck is not None and n == 2
    rendered = pd.DataFrame(deck.layers[0].data).set_index("hex_id")
    c_hex1 = rendered.loc[hex1, "fill_color"]
    c_hex2 = rendered.loc[hex2, "fill_color"]
    # hex1 tem hibrido=90 (verde) e hex2 tem hibrido=10 (vermelho): devem ter cores diferentes
    assert c_hex1 != c_hex2
    # Em modo residual a ordem seria invertida: hex2 (residual=90) seria verde
    deck_res, _ = streamlit_app.build_unified_map_figure(df, color_mode="residual", selected_ufs=[], selected_cities=[])
    rendered_res = pd.DataFrame(deck_res.layers[0].data).set_index("hex_id")
    # No modo residual hex2 (residual=90) deve ser verde; no modo hibrido hex1 (hibrido=90) e verde
    assert rendered_res.loc[hex1, "fill_color"] != c_hex1


def test_render_score_bands_legend_exportada():
    assert hasattr(streamlit_app, "render_score_bands_legend")
    assert callable(streamlit_app.render_score_bands_legend)


def test_score_band_to_color_exportado():
    assert hasattr(streamlit_app, "score_band_to_color")
    assert callable(streamlit_app.score_band_to_color)


# ── Testes do Bloco 12: decisao tecnica clique exato ─────────────────────────

def test_extract_click_coord_retorna_centroide_do_hex_nao_coord_livre():
    """_extract_click_coord retorna o centroide do hex selecionado, nao coordenada exata do clique.

    Comportamento documentado: pydeck on_select passa dados do objeto de camada; para o
    H3HexagonLayer o payload traz hex_id (o frame enxuto nao serializa lat/lng), e o
    centroide e reconstruido via h3.cell_to_latlng. Fallback para coordenada exata:
    campo lat,lng na barra lateral.
    """
    hex_id = h3.latlng_to_cell(-23.5505, -46.6333, 7)
    centroide = h3.cell_to_latlng(hex_id)
    event = _MockMapEvent({"main_unified_map": [{"hex_id": hex_id, "score_priorizacao": 80.0}]})
    result = streamlit_app._extract_click_coord_from_selection(event)
    assert result is not None
    assert result == pytest.approx(centroide)


def test_extract_click_coord_espaco_vazio_nao_dispara_evento():
    """Clique em espaco vazio do mapa pydeck nao retorna coordenada (sem objeto de camada)."""
    event = _MockMapEvent({})
    assert streamlit_app._extract_click_coord_from_selection(event) is None


def test_decisao_clique_documentada_em_analise_pontual_entorno():
    """docs/analise_pontual_entorno.md deve conter a decisao tecnica do Bloco 12."""
    doc = (
        Path("docs") / "analise_pontual_entorno.md"
    )
    assert doc.exists(), "docs/analise_pontual_entorno.md deve existir"
    texto = doc.read_text(encoding="utf-8").lower()
    assert "pydeck" in texto, "decisao deve mencionar pydeck"
    assert "streamlit-folium" in texto, "decisao deve mencionar streamlit-folium como opcao avaliada"
    assert "descartada" in texto or "adotada" in texto, "decisao deve registrar resultado da avaliacao"


def test_render_analise_pontual_estado_vazio_menciona_fallback_sidebar():
    """Estado vazio da Analise Pontual deve orientar uso do campo lat,lng na sidebar."""
    import unittest.mock as mock

    df = pd.DataFrame([{"hex_id": "h1", "lat": -23.55, "lng": -46.63, "score_priorizacao": 80.0}])

    with mock.patch("streamlit.info") as info_mock, mock.patch("streamlit.caption") as cap_mock:
        streamlit_app.render_analise_pontual(None, df)

    all_text = " ".join(
        str(c[0][0]) for c in (list(info_mock.call_args_list) + list(cap_mock.call_args_list))
        if c[0]
    ).lower()
    assert "sidebar" in all_text or "barra lateral" in all_text or "lat" in all_text


# ── Bloco 16: UI Cenario Multi-Hex ───────────────────────────────────────────

def test_build_multihex_selection_layer_retorna_layer():
    """_build_multihex_selection_layer deve retornar um pdk.Layer H3HexagonLayer."""
    import pydeck as pdk
    layer = streamlit_app._build_multihex_selection_layer(["hex1", "hex2"])
    assert isinstance(layer, pdk.Layer)
    assert layer.type == "H3HexagonLayer"


def test_build_multihex_selection_layer_lista_vazia():
    """Layer com lista vazia nao deve lancar excecao."""
    import pydeck as pdk
    layer = streamlit_app._build_multihex_selection_layer([])
    assert isinstance(layer, pdk.Layer)


def test_render_multihex_controls_estado_vazio():
    """_render_multihex_controls com cenario vazio e sem hex ativo deve renderizar sem erro."""
    import unittest.mock as mock

    with mock.patch("streamlit.markdown"), \
         mock.patch("streamlit.columns", return_value=[mock.MagicMock(), mock.MagicMock(), mock.MagicMock()]), \
         mock.patch("streamlit.caption"), \
         mock.patch("streamlit.button", return_value=False), \
         mock.patch("streamlit.expander") as exp_mock, \
         mock.patch("streamlit.session_state", {}):
        exp_mock.return_value.__enter__ = lambda s: s
        exp_mock.return_value.__exit__ = mock.MagicMock(return_value=False)
        streamlit_app._render_multihex_controls(None, [])


def test_render_multihex_kpis_sem_hexes_validos():
    """_render_multihex_kpis com hex_ids ausentes no df deve exibir info."""
    import unittest.mock as mock

    df = pd.DataFrame([{
        "hex_id": "h1",
        "populacao_proxy": 10_000.0,
        "score_priorizacao": 80.0,
        "renda_per_capita": 5_000.0,
    }])
    with mock.patch("streamlit.info") as info_mock, \
         mock.patch("streamlit.markdown"), \
         mock.patch("streamlit.columns", return_value=[mock.MagicMock(), mock.MagicMock(), mock.MagicMock()]), \
         mock.patch("streamlit.metric"), \
         mock.patch("streamlit.caption"), \
         mock.patch("streamlit.dataframe"):
        streamlit_app._render_multihex_kpis(df, ["hex_inexistente"])

    assert info_mock.called


def test_render_multihex_kpis_com_hexes_validos():
    """_render_multihex_kpis com hexes presentes deve exibir metricas sem erro."""
    import unittest.mock as mock

    df = pd.DataFrame([
        {"hex_id": "h1", "populacao_proxy": 10_000.0, "score_priorizacao": 80.0, "renda_per_capita": 5_000.0},
        {"hex_id": "h2", "populacao_proxy": 5_000.0, "score_priorizacao": 60.0, "renda_per_capita": 4_000.0},
    ])
    with mock.patch("streamlit.markdown"), \
         mock.patch("streamlit.columns", return_value=[mock.MagicMock(), mock.MagicMock(), mock.MagicMock()]), \
         mock.patch("streamlit.metric") as metric_mock, \
         mock.patch("streamlit.caption"), \
         mock.patch("streamlit.dataframe"):
        streamlit_app._render_multihex_kpis(df, ["h1", "h2"])

    assert metric_mock.called


def test_render_multihex_kpis_exportado_via_streamlit_app():
    """_render_multihex_kpis deve estar acessivel via streamlit_app."""
    assert hasattr(streamlit_app, "_render_multihex_kpis")
    assert callable(streamlit_app._render_multihex_kpis)


def test_render_multihex_controls_exportado_via_streamlit_app():
    """_render_multihex_controls deve estar acessivel via streamlit_app."""
    assert hasattr(streamlit_app, "_render_multihex_controls")
    assert callable(streamlit_app._render_multihex_controls)


# ── Testes do Bloco 16.1: Integrar Multi-Hex ao Mapa da Analise Pontual ──────

def test_build_multihex_analysis_map_retorna_deck_com_layer():
    """build_multihex_analysis_map com hex_ids deve retornar Deck com layer H3."""
    import h3
    import pydeck as pdk
    lat, lng = -23.55, -46.63
    hex_id = h3.latlng_to_cell(lat, lng, 7)
    deck = streamlit_app.build_multihex_analysis_map([hex_id])
    assert deck is not None
    assert isinstance(deck, pdk.Deck)
    assert len(deck.layers) >= 1


def test_build_multihex_analysis_map_lista_vazia_retorna_none():
    """build_multihex_analysis_map com lista vazia deve retornar None."""
    assert streamlit_app.build_multihex_analysis_map([]) is None


def test_build_multihex_analysis_map_com_coordenada_adiciona_raio():
    """Com lat/lng, deve adicionar camadas de raio e ponto alem do layer de hexes."""
    import h3
    lat, lng = -23.55, -46.63
    hex_id = h3.latlng_to_cell(lat, lng, 7)
    deck_sem_coord = streamlit_app.build_multihex_analysis_map([hex_id])
    deck_com_coord = streamlit_app.build_multihex_analysis_map([hex_id], lat=lat, lng=lng)
    assert deck_com_coord is not None
    assert len(deck_com_coord.layers) > len(deck_sem_coord.layers)


def test_render_analise_pontual_com_multihex_exibe_mapa_e_kpis():
    """render_analise_pontual com multihex_ids deve chamar pydeck_chart e markdown de cabecalho."""
    import unittest.mock as mock

    import h3

    lat, lng = -23.55, -46.63
    hex_id = h3.latlng_to_cell(lat, lng, 7)
    df = pd.DataFrame([{
        "hex_id": hex_id,
        "populacao_proxy": 10_000.0,
        "score_priorizacao": 75.0,
        "renda_per_capita": 5_000.0,
        "oferta_efetiva_disponivel": 2_000.0,
        "lat": lat,
        "lng": lng,
    }])

    markdowns = []
    def _cols(n, *a, **kw):
        return [mock.MagicMock() for _ in range(n if isinstance(n, int) else len(n))]

    with mock.patch("streamlit.markdown", side_effect=lambda msg, **kw: markdowns.append(str(msg))), \
         mock.patch("streamlit.caption"), \
         mock.patch("streamlit.columns", side_effect=_cols), \
         mock.patch("streamlit.pydeck_chart") as pydeck_mock, \
         mock.patch("streamlit.dataframe"):
        streamlit_app.render_analise_pontual(None, df, multihex_ids=[hex_id])

    # mapa renderizado
    assert pydeck_mock.called
    # cabecalho menciona multi-hex ou n de hexes
    all_md = " ".join(markdowns).lower()
    assert "hex" in all_md or "cenario" in all_md


def test_render_analise_pontual_multihex_sem_hexes_validos_exibe_info():
    """Com multihex_ids inexistentes no df, deve exibir info."""
    import unittest.mock as mock

    df = pd.DataFrame([{"hex_id": "h1", "populacao_proxy": 1000.0, "score_priorizacao": 50.0}])
    with mock.patch("streamlit.info") as info_mock, \
         mock.patch("streamlit.caption"), \
         mock.patch("streamlit.markdown"):
        streamlit_app.render_analise_pontual(None, df, multihex_ids=["hex_inexistente"])

    assert info_mock.called


def test_render_analise_pontual_multihex_com_coordenada_ativa_mostra_referencia():
    """Com multihex_ids e search_pin, caption deve mencionar coordenada de referencia."""
    import unittest.mock as mock

    import h3

    lat, lng = -23.55, -46.63
    hex_id = h3.latlng_to_cell(lat, lng, 7)
    df = pd.DataFrame([{
        "hex_id": hex_id,
        "populacao_proxy": 5_000.0,
        "score_priorizacao": 60.0,
        "renda_per_capita": 4_000.0,
    }])

    captions = []
    def _cols(n, *a, **kw):
        return [mock.MagicMock() for _ in range(n if isinstance(n, int) else len(n))]

    with mock.patch("streamlit.caption", side_effect=lambda msg, **kw: captions.append(str(msg))), \
         mock.patch("streamlit.markdown"), \
         mock.patch("streamlit.metric"), \
         mock.patch("streamlit.columns", side_effect=_cols), \
         mock.patch("streamlit.pydeck_chart"), \
         mock.patch("streamlit.dataframe"):
        streamlit_app.render_analise_pontual((lat, lng), df, multihex_ids=[hex_id])

    all_text = " ".join(captions).lower()
    assert str(round(lat, 5)) in all_text or "referenc" in all_text or "raio" in all_text


def test_render_analise_pontual_sem_multihex_preserva_comportamento_atual():
    """Sem multihex_ids, render_analise_pontual sem search_pin deve exibir info de instrucao."""
    import unittest.mock as mock

    df = pd.DataFrame([{"hex_id": "h1", "lat": -23.55, "lng": -46.63, "score_priorizacao": 80.0}])
    with mock.patch("streamlit.info") as info_mock, mock.patch("streamlit.caption"):
        streamlit_app.render_analise_pontual(None, df)

    info_mock.assert_called_once()


def test_build_multihex_analysis_map_exportado_via_streamlit_app():
    """build_multihex_analysis_map deve estar acessivel via streamlit_app."""
    assert hasattr(streamlit_app, "build_multihex_analysis_map")
    assert callable(streamlit_app.build_multihex_analysis_map)


# ── Bloco 16.2: Facilitar Copia e Inclusao de hex_id ─────────────────────────

def test_parse_hex_ids_from_text_separadores_variados():
    """parse_hex_ids_from_text deve aceitar linha, virgula, ponto-e-virgula e espaco."""
    from motor_expansao.dashboard.data import parse_hex_ids_from_text

    assert parse_hex_ids_from_text("87abc\n87xyz") == ["87abc", "87xyz"]
    assert parse_hex_ids_from_text("87abc,87xyz") == ["87abc", "87xyz"]
    assert parse_hex_ids_from_text("87abc;87xyz") == ["87abc", "87xyz"]
    assert parse_hex_ids_from_text("87abc 87xyz") == ["87abc", "87xyz"]
    result = parse_hex_ids_from_text("87abc\n87xyz, 87def;87ghi 87jkl")
    assert result == ["87abc", "87xyz", "87def", "87ghi", "87jkl"]


def test_parse_hex_ids_from_text_texto_vazio():
    """parse_hex_ids_from_text deve retornar lista vazia para texto vazio ou espacos."""
    from motor_expansao.dashboard.data import parse_hex_ids_from_text

    assert parse_hex_ids_from_text("") == []
    assert parse_hex_ids_from_text("   ") == []
    assert parse_hex_ids_from_text("\n\n") == []


def test_parse_hex_ids_from_text_duplicados_count():
    """Logica de duplicados via parse_hex_ids_from_text deve detectar entradas repetidas."""
    from motor_expansao.dashboard.data import parse_hex_ids_from_text

    existing = {"hex_a", "hex_b"}
    parsed = parse_hex_ids_from_text("hex_b\nhex_c\nhex_b")
    new_ids = [h for h in parsed if h not in existing]
    dupes = len(parsed) - len(new_ids)
    assert new_ids == ["hex_c"]
    assert dupes == 2


def test_parse_hex_ids_from_text_exportado_via_streamlit_app():
    """parse_hex_ids_from_text deve estar acessivel via streamlit_app."""
    assert hasattr(streamlit_app, "parse_hex_ids_from_text")
    assert callable(streamlit_app.parse_hex_ids_from_text)


def test_render_multihex_controls_exibe_hex_id_ativo_via_code():
    """_render_multihex_controls com hex ativo deve chamar st.code com o hex_id."""
    import unittest.mock as mock

    code_calls = []

    def _cols(spec, **kw):
        n = spec if isinstance(spec, int) else len(spec)
        return [mock.MagicMock() for _ in range(n)]

    with mock.patch("streamlit.markdown"), \
         mock.patch("streamlit.button", return_value=False), \
         mock.patch("streamlit.caption"), \
         mock.patch("streamlit.code", side_effect=lambda v, **kw: code_calls.append(v)), \
         mock.patch("streamlit.columns", side_effect=_cols), \
         mock.patch("streamlit.expander") as exp_mock, \
         mock.patch("streamlit.text_area", return_value=""):
        exp_mock.return_value.__enter__ = lambda s: s
        exp_mock.return_value.__exit__ = mock.MagicMock(return_value=False)
        streamlit_app._render_multihex_controls("87abc123def456", [])

    assert "87abc123def456" in code_calls


def test_render_multihex_paste_com_newlines_aceito():
    """parse_hex_ids_from_text deve aceitar lista com quebras de linha (simulando colar)."""
    from motor_expansao.dashboard.data import parse_hex_ids_from_text

    raw = "87hex_a\n87hex_b\n87hex_c"
    result = parse_hex_ids_from_text(raw)
    assert len(result) == 3
    assert result == ["87hex_a", "87hex_b", "87hex_c"]


def test_render_analise_pontual_single_point_exibe_hex_id():
    """render_analise_pontual no modo single-point deve chamar st.code com o hex_id do ponto."""
    import unittest.mock as mock

    import h3

    lat, lng = -23.55, -46.63
    hex_id = h3.latlng_to_cell(lat, lng, 7)
    df = pd.DataFrame([{
        "hex_id": hex_id, "lat": lat, "lng": lng,
        "uf": "SP", "cidade": "Sao Paulo", "nome_municipio": "Sao Paulo",
        "score_priorizacao": 75.0, "renda_per_capita": 4000.0,
        "populacao_proxy": 10000.0, "rank_brasil": 100,
    }])

    code_calls = []

    def _cols(spec, **kw):
        n = spec if isinstance(spec, int) else len(spec)
        return [mock.MagicMock() for _ in range(n)]

    with mock.patch("streamlit.code", side_effect=lambda v, **kw: code_calls.append(v)), \
         mock.patch("streamlit.caption"), \
         mock.patch("streamlit.markdown"), \
         mock.patch("streamlit.columns", side_effect=_cols), \
         mock.patch("streamlit.metric"), \
         mock.patch("streamlit.button", return_value=False), \
         mock.patch("streamlit.pydeck_chart"), \
         mock.patch("streamlit.dataframe"), \
         mock.patch("streamlit.info"):
        streamlit_app.render_analise_pontual((lat, lng), df)

    assert any(hex_id in str(c) for c in code_calls)


def test_render_analise_pontual_single_point_botao_adicionar_ao_cenario():
    """render_analise_pontual no modo single-point deve chamar st.button para adicionar ao cenario."""
    import unittest.mock as mock

    import h3

    lat, lng = -23.55, -46.63
    hex_id = h3.latlng_to_cell(lat, lng, 7)
    df = pd.DataFrame([{
        "hex_id": hex_id, "lat": lat, "lng": lng,
        "uf": "SP", "cidade": "Sao Paulo", "nome_municipio": "Sao Paulo",
        "score_priorizacao": 75.0, "renda_per_capita": 4000.0,
        "populacao_proxy": 10000.0, "rank_brasil": 100,
    }])

    button_labels = []

    def _cols(spec, **kw):
        n = spec if isinstance(spec, int) else len(spec)
        return [mock.MagicMock() for _ in range(n)]

    with mock.patch("streamlit.code"), \
         mock.patch("streamlit.caption"), \
         mock.patch("streamlit.markdown"), \
         mock.patch("streamlit.columns", side_effect=_cols), \
         mock.patch("streamlit.metric"), \
         mock.patch("streamlit.button", side_effect=lambda label, **kw: button_labels.append(label) or False), \
         mock.patch("streamlit.pydeck_chart"), \
         mock.patch("streamlit.dataframe"), \
         mock.patch("streamlit.info"):
        streamlit_app.render_analise_pontual((lat, lng), df)

    assert any("cenario" in str(lbl).lower() or "adicionar" in str(lbl).lower() for lbl in button_labels)


# ── Testes do Bloco 18: consumo fitness nos detalhes ─────────────────────────

def test_analisar_entorno_ponto_retorna_consumo_quando_colunas_presentes():
    lat_c, lng_c = -23.5, -46.6
    df = pd.DataFrame([{
        "hex_id": "h1", "lat": lat_c, "lng": lng_c,
        "oferta_efetiva_disponivel": 500.0,
        "oferta_consumida_mercado_estimada": 1200.0,
        "oferta_consumida_ultra_real": 300.0,
    }])
    result = streamlit_app.analisar_entorno_ponto(lat_c, lng_c, df, raio_km=1.6)
    assert result["consumo_concorrentes_raio"] == pytest.approx(1200.0)
    assert result["consumo_ultra_raio"] == pytest.approx(300.0)


def test_analisar_entorno_ponto_consumo_none_quando_colunas_ausentes():
    lat_c, lng_c = -23.5, -46.6
    df = pd.DataFrame([{
        "hex_id": "h1", "lat": lat_c, "lng": lng_c,
        "oferta_efetiva_disponivel": 500.0,
    }])
    result = streamlit_app.analisar_entorno_ponto(lat_c, lng_c, df, raio_km=1.6)
    assert result["consumo_concorrentes_raio"] is None
    assert result["consumo_ultra_raio"] is None


def test_analisar_entorno_ponto_consumo_soma_hexes_no_raio():
    lat_c, lng_c = -23.5, -46.6
    df = pd.DataFrame([
        {
            "hex_id": "h1", "lat": lat_c, "lng": lng_c,
            "oferta_consumida_mercado_estimada": 800.0,
            "oferta_consumida_ultra_real": 200.0,
        },
        {
            "hex_id": "h2", "lat": lat_c + 0.005, "lng": lng_c,
            "oferta_consumida_mercado_estimada": 400.0,
            "oferta_consumida_ultra_real": 100.0,
        },
        # hex fora do raio
        {
            "hex_id": "h3", "lat": lat_c - 0.05, "lng": lng_c,
            "oferta_consumida_mercado_estimada": 999.0,
            "oferta_consumida_ultra_real": 999.0,
        },
    ])
    result = streamlit_app.analisar_entorno_ponto(lat_c, lng_c, df, raio_km=1.6)
    assert result["consumo_concorrentes_raio"] == pytest.approx(1200.0)
    assert result["consumo_ultra_raio"] == pytest.approx(300.0)


def test_render_expansao_dominio_exibe_consumo_quando_colunas_presentes(tmp_path, monkeypatch):
    from unittest import mock
    plano = pd.DataFrame([{
        "rank_dominio_brasil": 1,
        "rank_dominio_uf": 1,
        "uf": "SP",
        "nome_municipio": "Sao Paulo",
        "cluster_id": "c1",
        "hex_id": "h_anc",
        "lat": -23.55,
        "lng": -46.63,
        "ordem_expansao_cidade": 1,
        "score_oportunidade_residual": 70.0,
        "residual_incremental_capturado": 1500.0,
        "oferta_efetiva_disponivel": 2000.0,
        "oferta_consumida_mercado_estimada": 3000.0,
        "oferta_consumida_ultra_real": 500.0,
        "tese_dominio": "ancora_isolada",
        "rank_dominio_cidade": 1,
    }])

    rendered_dfs = []

    def _cols(spec, **kw):
        n = spec if isinstance(spec, int) else len(spec)
        return [mock.MagicMock() for _ in range(n)]

    with mock.patch("streamlit.markdown"), \
         mock.patch("streamlit.caption"), \
         mock.patch("streamlit.columns", side_effect=_cols), \
         mock.patch("streamlit.metric"), \
         mock.patch("streamlit.multiselect", return_value=[]), \
         mock.patch("streamlit.info"), \
         mock.patch("streamlit.pydeck_chart"), \
         mock.patch("streamlit.dataframe", side_effect=lambda df, **kw: rendered_dfs.append(df)):
        streamlit_app.render_expansao_dominio(plano)

    assert rendered_dfs, "dataframe nao renderizado"
    tbl = rendered_dfs[0]
    assert "Consumo Conc. (est.)" in tbl.columns
    assert "Consumo Ultra (real)" in tbl.columns
    assert tbl["Consumo Conc. (est.)"].iloc[0] == "3.000"
    assert tbl["Consumo Ultra (real)"].iloc[0] == "500"


# ── Testes do Bloco 4: carga lazy por UF ──

def _build_lazy_partitions(base_dir: Path) -> Path:
    """Materializa um dataset enriquecido particionado sintetico (SP, RJ)."""
    from motor_expansao.pipelines.m1.fase1_bi_exports import write_enriched_dashboard_partitioned

    rows = [
        (_HEX_SP1, "SP", "Sao Paulo", 1),
        (_HEX_SP2, "SP", "Campinas", 2),
        (_HEX_RJ1, "RJ", "Rio de Janeiro", 3),
    ]
    records = [
        {
            "hex_id": hex_id, "lat": -23.5 - i, "lng": -46.6 - i,
            "uf": uf, "cidade": cidade, "regiao": "SE",
            "score_priorizacao": 90.0 - i, "hex_score_estrutural": 86.0 - i,
            "ajuste_executivo": 4.0, "faixa_oportunidade": "alta",
            "flag_viavel": True, "flag_prioridade": True,
            "rank_brasil": rank, "rank_uf": 1, "rank_cidade": 1,
            "renda_per_capita": 5200.0, "populacao_proxy": 16000.0,
        }
        for i, (hex_id, uf, cidade, rank) in enumerate(rows)
    ]
    base = streamlit_app._prepare_dataframe(pd.DataFrame(records)[REQUIRED_COLUMNS])
    enriched = streamlit_app.enrich_dashboard_data(base, pd.DataFrame(), pd.DataFrame())
    out = base_dir / "enriquecido_lazy"
    write_enriched_dashboard_partitioned(enriched, base_dir=out)
    return out


def test_list_partitioned_ufs_lista_e_vazio(tmp_path):
    out = _build_lazy_partitions(tmp_path)
    assert streamlit_app.list_partitioned_ufs(out) == ["RJ", "SP"]
    assert streamlit_app.list_partitioned_ufs(tmp_path / "nao_existe") == []


def test_read_enriched_uf_partition_le_apenas_uf(tmp_path):
    out = _build_lazy_partitions(tmp_path)
    sp = streamlit_app.read_enriched_uf_partition(out, "SP")
    assert not sp.empty
    assert set(sp["uf"].astype(str).unique()) == {"SP"}
    assert len(sp) == 2
    assert "UF" in sp.columns and "score_exibicao" in sp.columns
    # particao inexistente -> frame vazio (sem erro)
    assert streamlit_app.read_enriched_uf_partition(out, "MG").empty


def test_load_uf_catalog_usa_particoes(tmp_path, monkeypatch):
    out = _build_lazy_partitions(tmp_path)
    monkeypatch.setattr(streamlit_app, "ENRIQUECIDO_DIR", out)
    streamlit_app.load_uf_catalog.clear()
    assert streamlit_app.load_uf_catalog() == ["RJ", "SP"]


def test_load_uf_catalog_fallback_parquet_oficial(local_tmp_dir, monkeypatch):
    path = _write_dashboard_parquet(
        local_tmp_dir,
        [
            {"hex_id": "a", "lat": -23.55, "lng": -46.63, "uf": "SP", "cidade": "Sao Paulo",
             "regiao": "SE", "score_priorizacao": 80.0, "hex_score_estrutural": 76.0,
             "ajuste_executivo": 4.0, "faixa_oportunidade": "alta", "flag_viavel": True,
             "flag_prioridade": True, "rank_brasil": 1, "rank_uf": 1, "rank_cidade": 1,
             "renda_per_capita": 5200.0, "populacao_proxy": 16000.0},
            {"hex_id": "b", "lat": -22.91, "lng": -43.17, "uf": "RJ", "cidade": "Rio de Janeiro",
             "regiao": "SE", "score_priorizacao": 70.0, "hex_score_estrutural": 66.0,
             "ajuste_executivo": 4.0, "faixa_oportunidade": "alta", "flag_viavel": True,
             "flag_prioridade": True, "rank_brasil": 2, "rank_uf": 1, "rank_cidade": 1,
             "renda_per_capita": 4800.0, "populacao_proxy": 12000.0},
        ],
    )
    monkeypatch.setattr(streamlit_app, "ENRIQUECIDO_DIR", local_tmp_dir / "sem_particoes")
    monkeypatch.setattr(streamlit_app, "DATASET_PATH", path)
    streamlit_app.load_uf_catalog.clear()
    assert streamlit_app.load_uf_catalog() == ["RJ", "SP"]


def test_load_uf_slice_le_so_a_particao(tmp_path, monkeypatch):
    out = _build_lazy_partitions(tmp_path)
    monkeypatch.setattr(streamlit_app, "ENRIQUECIDO_DIR", out)
    streamlit_app.load_uf_slice.clear()
    sp = streamlit_app.load_uf_slice("SP")
    assert set(sp["uf"].astype(str).unique()) == {"SP"}
    assert len(sp) == 2


# ── Performance Bloco 5: render lazy das abas ────────────────────────────────

def test_render_tab_selector_e_exportado():
    assert hasattr(streamlit_app, "render_tab_selector")
    assert callable(streamlit_app.render_tab_selector)
    assert streamlit_app.DASHBOARD_TAB_LABELS == [
        "Visao Executiva",
        "Mapa Territorial",
        "Expansao de Dominio",
        "Carteira e Plano",
    ]


def test_render_tab_selector_retorna_aba_ativa():
    """O seletor devolve a aba escolhida no segmented_control."""
    import unittest.mock as mock

    with (
        mock.patch("streamlit.segmented_control", return_value="Mapa Territorial"),
        mock.patch("streamlit.session_state", {}),
    ):
        result = streamlit_app.render_tab_selector()

    assert result == "Mapa Territorial"


def test_render_tab_selector_fallback_quando_desmarcado():
    """Quando segmented_control devolve None (desmarcado), mantem a ultima aba ou o default."""
    import unittest.mock as mock

    # Sem ultima aba registrada -> cai para o primeiro label.
    with (
        mock.patch("streamlit.segmented_control", return_value=None),
        mock.patch("streamlit.session_state", {}),
    ):
        result = streamlit_app.render_tab_selector()
    assert result == "Visao Executiva"

    # Com ultima aba registrada -> preserva a aba previa.
    with (
        mock.patch("streamlit.segmented_control", return_value=None),
        mock.patch("streamlit.session_state", {"dashboard_active_tab_last": "Carteira e Plano"}),
    ):
        result = streamlit_app.render_tab_selector()
    assert result == "Carteira e Plano"


def test_main_renderiza_apenas_a_aba_ativa(tmp_path, monkeypatch):
    """main() deve chamar somente o render_* da aba ativa, nao das outras tres."""
    import contextlib
    import unittest.mock as mock

    out = _build_lazy_partitions(tmp_path)
    monkeypatch.setattr(streamlit_app, "ENRIQUECIDO_DIR", out)
    streamlit_app.load_uf_catalog.clear()
    streamlit_app.load_uf_slice.clear()

    empty = pd.DataFrame()
    # ExitStack em vez de `with (m1, ..., m21):` — 21 context managers num unico `with`
    # estouram o limite de 20 blocos aninhados do compilador no Python 3.11 (CI), embora
    # compile no 3.12+ (local). enter_context preserva ordem/comportamento.
    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch("streamlit.session_state", {}))
        stack.enter_context(mock.patch.object(streamlit_app, "inject_styles"))
        stack.enter_context(mock.patch.object(streamlit_app, "render_header"))
        stack.enter_context(mock.patch.object(streamlit_app, "render_uf_selectbox", return_value="SP"))
        stack.enter_context(mock.patch.object(streamlit_app, "render_sidebar_filters",
                            return_value=([], [], [], [], [], [], False, False)))
        stack.enter_context(mock.patch.object(streamlit_app, "render_coord_search_sidebar", return_value=None))
        stack.enter_context(mock.patch.object(streamlit_app, "render_tab_selector", return_value="Expansao de Dominio"))
        stack.enter_context(mock.patch.object(streamlit_app, "load_carteira", return_value=empty))
        stack.enter_context(mock.patch.object(streamlit_app, "load_plano", return_value=empty))
        stack.enter_context(mock.patch.object(streamlit_app, "load_plano_dominio", return_value=empty))
        stack.enter_context(mock.patch.object(streamlit_app, "load_competitors", return_value=empty))
        stack.enter_context(mock.patch.object(streamlit_app, "load_ultra", return_value=empty))
        visao_mock = stack.enter_context(mock.patch.object(streamlit_app, "render_visao_executiva"))
        mapa_mock = stack.enter_context(mock.patch.object(streamlit_app, "render_mapa_territorial"))
        dominio_mock = stack.enter_context(mock.patch.object(streamlit_app, "render_expansao_dominio"))
        carteira_mock = stack.enter_context(mock.patch.object(streamlit_app, "render_carteira_e_plano"))
        city_mock = stack.enter_context(mock.patch.object(streamlit_app, "build_city_summary"))
        stack.enter_context(mock.patch("streamlit.caption"))
        stack.enter_context(mock.patch("streamlit.markdown"))
        stack.enter_context(mock.patch("streamlit.info"))
        stack.enter_context(mock.patch("streamlit.spinner"))
        streamlit_app.main()

    assert dominio_mock.called
    assert not visao_mock.called
    assert not mapa_mock.called
    assert not carteira_mock.called
    # summaries so sao computados para abas que os consomem (Visao/Mapa), nao para Dominio
    assert not city_mock.called


def test_render_relatorio_pontual_censitario_sem_coordenada_exibe_info():
    import unittest.mock as mock

    with mock.patch("streamlit.info") as info_mock, mock.patch("streamlit.caption"):
        streamlit_app.render_relatorio_pontual_censitario(
            None,
            pd.DataFrame(),
            censo_geo_loader=lambda uf, cod: pd.DataFrame(),
        )

    info_mock.assert_called_once()
    assert "coordenada" in info_mock.call_args[0][0].lower()


def test_render_relatorio_pontual_censitario_sem_base_setorial_exibe_warning():
    import unittest.mock as mock

    import h3

    lat, lng = -15.7939, -47.8828
    df = pd.DataFrame([{
        "hex_id": h3.latlng_to_cell(lat, lng, 7),
        "lat": lat,
        "lng": lng,
        "uf": "DF",
        "cidade": "Brasilia",
        "nome_municipio": "BRASILIA",
        "cod_municipio": "5300108",
    }])

    with (
        mock.patch("streamlit.warning") as warning_mock,
        mock.patch("streamlit.caption"),
    ):
        streamlit_app.render_relatorio_pontual_censitario(
            (lat, lng),
            df,
            censo_geo_loader=lambda uf, cod: pd.DataFrame(),
        )

    assert "base setorial" in warning_mock.call_args[0][0].lower()
    assert "5300108" in warning_mock.call_args[0][0]


def test_render_relatorio_pontual_censitario_com_coordenada_gera_mapa_e_downloads():
    import unittest.mock as mock

    import h3

    lat, lng = -15.7939, -47.8828
    df = pd.DataFrame([{
        "hex_id": h3.latlng_to_cell(lat, lng, 7),
        "lat": lat,
        "lng": lng,
        "uf": "DF",
        "cidade": "Brasilia",
        "nome_municipio": "BRASILIA",
        "cod_municipio": "5300108",
    }])
    setores_df = pd.DataFrame([{"cod_setor": "530010805000001", "geometry_wkb": b"fake"}])
    result = {
        "lat": lat,
        "lng": lng,
        "raio_km": 1.5,
        "metodo": "setor_censitario_intersecao_area_1p5km",
        "n_setores": 1,
        "pop_total_raio": 1234.0,
        "renda_per_capita_media_raio": 2100.0,
        "densidade_pop_raio_hab_km2": 175.0,
        "score_setor_medio": 77.0,
        "score_setor_max": 88.0,
        "n_concorrentes": 2,
        "n_ultra": 1,
        "setores_intersectados": pd.DataFrame([{
            "cod_setor": "530010805000001",
            "nome_municipio": "BRASILIA",
            "area_intersecao_m2": 1000.0,
            "peso_area_setor": 0.5,
            "pop_estimada_intersecao": 1234.0,
            "renda_per_capita_setor_2022_calibrada": 2100.0,
            "score_setor_2022_calibrado": 77.0,
            "qualidade_join_uf": "A",
        }]),
    }

    mapas_stub = {"densidade": b"PNG", "renda": b"PNG", "score": b"PNG", "concorrentes": b"PNG"}
    with (
        mock.patch("motor_expansao.dashboard.pages.analisar_ponto_censitario_setores", return_value=result) as analyze_mock,
        mock.patch("motor_expansao.dashboard.pages.render_mapas_censitarios_combinados", return_value=mapas_stub) as map_mock,
        mock.patch("motor_expansao.dashboard.pages.render_downloads_relatorio_censitario") as download_mock,
        mock.patch("streamlit.columns", side_effect=_mock_columns),
        mock.patch("streamlit.markdown"),
        mock.patch("streamlit.caption"),
        mock.patch("streamlit.image") as image_mock,
        mock.patch("streamlit.dataframe"),
    ):
        streamlit_app.render_relatorio_pontual_censitario(
            (lat, lng),
            df,
            censo_geo_loader=lambda uf, cod: setores_df,
        )

    analyze_mock.assert_called_once()
    map_mock.assert_called_once()
    download_mock.assert_called_once()
    # 4 camadas combinadas exibidas juntas (densidade/renda/score/concorrentes; sem dropdown).
    assert image_mock.call_count == 4


def test_load_censo_geo_setores_le_particao_por_municipio(tmp_path, monkeypatch):
    base = tmp_path / "setores_censitarios_2022_geo"
    part = base / "uf=DF" / "cod_municipio=5300108"
    part.mkdir(parents=True)
    pd.DataFrame([{
        "cod_setor": "530010805000001",
        "geometry_wkb": b"fake",
        "pop_total_setor_2022": 100.0,
    }]).to_parquet(part / "part-000.parquet", index=False)

    monkeypatch.setattr(streamlit_app, "CENSO_GEO_DIR", base)
    streamlit_app.load_censo_geo_setores.clear()
    streamlit_app.load_censo_geo_municipios.clear()

    municipios = streamlit_app.load_censo_geo_municipios("DF")
    setores = streamlit_app.load_censo_geo_setores("DF", "5300108")

    assert municipios == ["5300108"]
    assert len(setores) == 1
    assert setores.loc[0, "uf"] == "DF"
    assert setores.loc[0, "cod_municipio"] == "5300108"


# ── BLK-FIX-05: tema escuro travado independente do SO ──────────────────────────


def test_config_theme_dark():
    """`.streamlit/config.toml` deve travar o tema escuro com cores espelhando COLORS
    (guarda anti-drift: se COLORS mudar, este teste falha e exige sincronizar o toml)."""
    import tomllib

    from motor_expansao.dashboard.constants import COLORS

    config_path = Path(__file__).resolve().parents[2] / ".streamlit" / "config.toml"
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))

    assert "theme" in config
    theme = config["theme"]
    assert theme["base"] == "dark"
    assert theme["backgroundColor"] == COLORS["bg"]
    assert theme["textColor"] == COLORS["text"]
    assert theme["primaryColor"] == COLORS["brand_alt"]
    assert theme["secondaryBackgroundColor"] == COLORS["panel_solid"]


def test_inject_styles_cobre_componentes_baseweb():
    """O CSS injetado por inject_styles deve cobrir o seletor de abas real
    (segmented_control), o popover/menu do dropdown (portal fora do container) e o
    texto/estado do select — caso contrario o tema escuro vaza quando o SO e claro."""
    import unittest.mock as mock

    captured: list[str] = []
    with mock.patch("streamlit.markdown", side_effect=lambda body, **kw: captured.append(body)):
        streamlit_app.inject_styles()

    assert captured, "inject_styles deveria injetar ao menos um bloco de markdown"
    css = "".join(captured)
    assert "stSegmentedControl" in css
    assert 'data-baseweb="popover"' in css
    assert 'data-baseweb="select"' in css
    assert ('aria-checked="true"' in css) or ('aria-selected="true"' in css)
    assert "#19B7FF" in css  # aba ativa ciano sólido (BLK-UI-04)
    assert "stBaseButton-segmented_controlActive" in css  # seletor real Streamlit 1.58 (BLK-UI-05)
    assert "stBaseButton-segmented_control" in css  # seletor inativo real Streamlit 1.58 (BLK-UI-05)
    # BLK-UI-06: gap no flex-pai real e margin zero nos botões
    assert 'data-baseweb="button-group"' in css  # flex-pai real do seletor
    assert "gap: 8px" in css  # gap horizontal efetivo (pode ser em qualquer seletor)
    assert "margin: 0 !important" in css  # zera o margin-right: -1px do baseweb


# ── BLK-MAP-01: filtro individual de redes ───────────────────────────────────

def _make_competitors_two_redes() -> pd.DataFrame:
    """Fixture auxiliar: dois concorrentes em SP, uma smart_fit e uma bluefit."""
    return pd.DataFrame([
        {
            "rede": "smart_fit",
            "rede_label": "Smart Fit",
            "nome_unidade": "Smart Paulista",
            "lat": -23.551,
            "lng": -46.631,
            "cidade": "Sao Paulo",
            "uf": "SP",
            "arquivo_origem": "unidades_smart_fit.csv",
        },
        {
            "rede": "bluefit",
            "rede_label": "Bluefit",
            "nome_unidade": "Blue SP",
            "lat": -23.552,
            "lng": -46.632,
            "cidade": "Sao Paulo",
            "uf": "SP",
            "arquivo_origem": "unidades_bluefit.csv",
        },
    ])


def test_filtro_rede_uma_rede_so_ela_renderiza():
    """BLK-MAP-01 Cenario A: filtrar para uma rede => somente ela aparece na camada de pins."""
    import h3

    hex_id = h3.latlng_to_cell(-23.55, -46.63, 7)
    df = pd.DataFrame([_hex_row(hex_id, -23.55, -46.63)])
    competitors = _make_competitors_two_redes()

    # Simula o filtro aplicado por pages.py (D1=A/D2=A): apenas smart_fit selecionada
    competitors_filtrado = competitors[competitors["rede"].isin(["smart_fit"])]

    deck, _n = streamlit_app.build_unified_map_figure(
        df,
        color_mode="m1",
        enabled_overlays=["concorrentes"],
        selected_ufs=["SP"],
        selected_cities=["Sao Paulo"],
        competitors_df=competitors_filtrado,
    )

    assert deck is not None
    # hex_layer + icon_layer (pins de smart_fit)
    assert len(deck.layers) == 2
    rendered_competitors = pd.DataFrame(deck.layers[1].data)
    assert set(rendered_competitors["rede"].unique()) == {"smart_fit"}
    assert "bluefit" not in rendered_competitors["rede"].values


def test_filtro_rede_vazio_esconde_concorrentes():
    """BLK-MAP-01 Cenario B: seleção vazia => D2=A => competitors_df=None => zero camadas de pins."""
    import h3

    hex_id = h3.latlng_to_cell(-23.55, -46.63, 7)
    df = pd.DataFrame([_hex_row(hex_id, -23.55, -46.63)])

    # D2=A: seleção vazia => pages.py passa competitors_df=None ao builder
    deck, _n = streamlit_app.build_unified_map_figure(
        df,
        color_mode="m1",
        enabled_overlays=["concorrentes"],
        selected_ufs=["SP"],
        selected_cities=["Sao Paulo"],
        competitors_df=None,
    )

    assert deck is not None
    # Apenas o hex_layer; sem camada de pins de concorrentes
    assert len(deck.layers) == 1


def test_filtro_rede_todas_comportamento_atual():
    """BLK-MAP-01 Cenario C: todas as redes selecionadas => retrocompatibilidade com comportamento anterior."""
    import h3

    hex_id = h3.latlng_to_cell(-23.55, -46.63, 7)
    df = pd.DataFrame([_hex_row(hex_id, -23.55, -46.63)])
    competitors = _make_competitors_two_redes()

    # Sem filtro aplicado (todas as redes)
    deck, _n = streamlit_app.build_unified_map_figure(
        df,
        color_mode="m1",
        enabled_overlays=["concorrentes"],
        selected_ufs=["SP"],
        selected_cities=["Sao Paulo"],
        competitors_df=competitors,
    )

    assert deck is not None
    # hex_layer + icon_layer (ambas as redes)
    assert len(deck.layers) == 2
    rendered_competitors = pd.DataFrame(deck.layers[1].data)
    redes_renderizadas = set(rendered_competitors["rede"].unique())
    # Ambas as redes presentes no bbox de SP devem aparecer
    assert "smart_fit" in redes_renderizadas
    assert "bluefit" in redes_renderizadas
