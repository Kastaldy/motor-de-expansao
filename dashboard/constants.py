from __future__ import annotations

REQUIRED_COLUMNS = [
    "hex_id",
    "lat",
    "lng",
    "uf",
    "cidade",
    "regiao",
    "score_priorizacao",
    "hex_score_estrutural",
    "ajuste_executivo",
    "faixa_oportunidade",
    "flag_viavel",
    "flag_prioridade",
    "rank_brasil",
    "rank_uf",
    "rank_cidade",
    "renda_per_capita",
    "populacao_proxy",
]
OPTIONAL_DATASET_COLUMNS = ["confianca_geografica"]

RESIDUAL_MERCADO_COLS = [
    "pop_hex_base",
    "fonte_pop_hex_base",
    "tam_populacao_hex",
    "tam_fitness_potencial",
    "flag_sam_fitness",
    "sam_fitness_potencial",
    "capacidade_default_concorrente_alunos",
    "oferta_consumida_mercado_estimada",
    "oferta_consumida_ultra_real",
    "n_unidades_ultra_performance_hex",
    "oferta_efetiva_disponivel",
    "penetracao_fitness_mercado_estimada",
    "share_ultra_estimado_hex",
    "score_oportunidade_residual",
    "quartil_oportunidade_residual",
    "prioridade_mercado_mapeado",
    "tese_entrada",
]

HYBRID_LOAD_COLS = [
    "hex_id", "uf", "cidade", "nome_municipio",
    "score_priorizacao", "hex_score_estrutural", "faixa_oportunidade",
    "flag_viavel", "flag_prioridade", "rank_brasil", "rank_uf",
    "score_setor_2022_calibrado", "score_expansao_hibrido", "densidade_pop_setor_hab_km2",
    "top_municipio", "top_hex_intraurbano",
    "flag_censo_elegivel", "flag_censo_disponivel",
    "flag_hex_hibrido_elegivel", "top_municipio_hibrido", "municipio_censo_disponivel",
    "rank_municipio_uf", "rank_municipio_brasil", "rank_hex_intraurbano",
    "rank_hibrido_brasil", "rank_hibrido_uf",
    "top_oportunidade_municipio", "top_oportunidade_brasil", "top_oportunidade_uf",
    "qualidade_join_uf", "flag_join_uf_restrito", "flag_baixa_pop_setor",
    "flag_outlier_espacial", "coverage_pct_setor_2022",
    "motivo_nao_elegivel_censo", "status_espacial_uf", "fonte_camada_censitaria",
    "flag_monitoramento_prioritario", "criterio_score_expansao_hibrido",
    "camada_modelo_hibrido",
    "populacao_proxy", "renda_per_capita", "pop_total_setor_2022",
    "renda_per_capita_setor_2022_calibrada",
    *RESIDUAL_MERCADO_COLS,
]

CENSO_TRACE_LOAD_COLS = [
    "hex_id",
    "uf",
    "cod_municipio",
    "nome_municipio",
    "pop_total_setor_2022",
    "score_setor_2022_calibrado",
    "densidade_pop_setor_hab_km2",
    "coverage_pct_setor_2022",
    "qualidade_join_uf",
    "flag_join_uf_restrito",
    "flag_baixa_pop_setor",
    "flag_outlier_espacial",
    "causa_outlier_espacial",
    "delta_vs_vizinhos",
    "metodo_join_setor_2022",
    "motivo_fallback_setor_2022",
    "renda_per_capita_setor_2022_calibrada",
]

CENSO_UFS = ["DF", "GO", "MG", "RJ", "RS", "SP"]
HYBRID_ELIGIBILITY_ORDER = ["Elegivel", "Nao elegivel", "Sem camada"]
COVERAGE_BUCKET_ORDER = ["100%", "95-99,9%", "85-94,9%", "<85%", "Sem camada"]
JOIN_QUALITY_ORDER = ["A", "B", "C", "Sem camada"]

FAIXA_ORDEM = [
    "prioridade_maxima",
    "alta",
    "media",
    "baixa",
    "descartado",
    "inviavel",
]
MAP_POINT_LIMIT = 35000
TABLE_ROW_LIMIT = 1000
POP_MIN_ACIONAVEL = 5_000
BRASIL_CENTER = {"lat": -14.235, "lon": -51.9253}
FLOAT_COLUMNS = [
    "lat",
    "lng",
    "score_priorizacao",
    "hex_score_estrutural",
    "ajuste_executivo",
    "rank_brasil",
    "rank_uf",
    "rank_cidade",
    "renda_per_capita",
    "populacao_proxy",
    "score_setor_2022_calibrado",
    "score_expansao_hibrido",
    "densidade_pop_setor_hab_km2",
    "coverage_pct_setor_2022",
    "rank_municipio_uf",
    "rank_municipio_brasil",
    "rank_hex_intraurbano",
    "rank_hibrido_brasil",
    "rank_hibrido_uf",
    "delta_vs_vizinhos",
    "populacao_corte_hex",
    "pop_hex_base",
    "tam_populacao_hex",
    "tam_fitness_potencial",
    "sam_fitness_potencial",
    "capacidade_default_concorrente_alunos",
    "oferta_consumida_mercado_estimada",
    "oferta_consumida_ultra_real",
    "n_unidades_ultra_performance_hex",
    "oferta_efetiva_disponivel",
    "penetracao_fitness_mercado_estimada",
    "share_ultra_estimado_hex",
    "score_oportunidade_residual",
]
BOOL_COLUMNS = [
    "flag_viavel",
    "flag_prioridade",
    "top_municipio",
    "top_hex_intraurbano",
    "flag_censo_elegivel",
    "flag_censo_disponivel",
    "flag_hex_hibrido_elegivel",
    "top_municipio_hibrido",
    "municipio_censo_disponivel",
    "flag_join_uf_restrito",
    "flag_baixa_pop_setor",
    "flag_outlier_espacial",
    "flag_monitoramento_prioritario",
    "top_oportunidade_municipio",
    "top_oportunidade_brasil",
    "top_oportunidade_uf",
    "flag_pop_min_5k",
    "flag_sam_fitness",
]
TEXT_COLUMNS = [
    "uf",
    "cidade",
    "regiao",
    "nome_municipio",
    "confianca_geografica",
    "qualidade_join_uf",
    "motivo_nao_elegivel_censo",
    "status_espacial_uf",
    "fonte_camada_censitaria",
    "criterio_score_expansao_hibrido",
    "camada_modelo_hibrido",
    "causa_outlier_espacial",
    "metodo_join_setor_2022",
    "motivo_fallback_setor_2022",
    "fonte_populacao_corte",
    "fonte_pop_hex_base",
    "quartil_oportunidade_residual",
    "prioridade_mercado_mapeado",
    "tese_entrada",
]
MAP_SORT_COLUMNS = ["flag_prioridade", "flag_viavel", "score_priorizacao", "rank_brasil"]
MAP_SORT_ASCENDING = [False, False, False, True]
COLORS = {
    "bg": "#0A0C18",
    "bg_alt": "#12162A",
    "panel": "rgba(17, 24, 39, 0.88)",
    "panel_solid": "#12172A",
    "panel_soft": "#18203A",
    "border": "rgba(120, 137, 210, 0.24)",
    "text": "#F3F7FF",
    "muted": "#A7B3D1",
    "brand": "#3E2A78",
    "brand_alt": "#19B7FF",
    "accent": "#FF4D8D",
    "accent_alt": "#7C5CFF",
    "good": "#22C55E",
    "bad": "#FF5A6B",
    "warning": "#F59E0B",
    "map_line": "#C8D3EA",
}
FAIXA_COLORS = {
    "prioridade_maxima": "#14C850",
    "alta": "#F59E0B",
    "media": "#DC3232",
    "baixa": "#B41E1E",
    "descartado": "#78788C",
    "inviavel": "#2E3040",
}
CENSO_SCORE_COLORS = {
    "0-25": [180, 30, 30, 140],
    "25-50": [220, 50, 50, 140],
    "50-75": [245, 158, 11, 140],
    "75-100": [20, 200, 80, 140],
}
RESIDUAL_SCORE_BANDS: list[tuple[str, str]] = [
    ("0-10",   "#941212"),
    ("10-20",  "#B92323"),
    ("20-30",  "#DC4141"),
    ("30-40",  "#DC6914"),
    ("40-50",  "#F0941E"),
    ("50-60",  "#EEC828"),
    ("60-70",  "#96D250"),
    ("70-80",  "#50C33C"),
    ("80-90",  "#19A832"),
    ("90-100", "#0A8226"),
]

# Expansao de Dominio — constantes canonicas
DOMINIO_SCHEMA_MINIMO: frozenset[str] = frozenset({
    "hex_id", "uf", "cod_municipio", "nome_municipio", "lat", "lng",
    "cluster_id", "tese_dominio",
    "ordem_expansao_cidade", "residual_incremental_capturado",
    "residual_cluster_pos_acao", "dist_nova_ancora_mais_proxima_m",
    "rank_dominio_brasil", "rank_dominio_uf", "rank_dominio_cidade",
    "score_dominio_hibrido", "motivo_dominio",
})
DOMINIO_TESES_VALIDAS: frozenset[str] = frozenset({
    "dominar_white_space", "abrir_com_disputa", "proteger_corredor_ultra",
    "adensar_cluster", "monitorar", "bloqueado_canibalizacao",
})

# ── Mapa Territorial Unificado — camadas ──────────────────────────────────────

COLOR_MODES: dict[str, dict] = {
    "m1": {
        "label": "M1",
        "parquet": "hexagonos_brasil_dashboard.parquet",
        "required_cols": ["faixa_oportunidade", "score_priorizacao"],
        "optional_cols": [],
    },
    "hibrido": {
        "label": "Hibrido",
        "parquet": "oportunidades_expansao_hibrido.parquet",
        "required_cols": ["score_expansao_hibrido"],
        "optional_cols": ["score_setor_2022_calibrado"],
    },
    "censitario": {
        "label": "Censitario",
        "parquet": "oportunidades_expansao_hibrido.parquet",
        "required_cols": ["score_setor_2022_calibrado"],
        "optional_cols": [],
    },
    "residual": {
        "label": "Residual Fitness",
        "parquet": "oportunidades_expansao_hibrido.parquet",
        "required_cols": ["score_oportunidade_residual"],
        "optional_cols": ["oferta_efetiva_disponivel"],
    },
    "dominio": {
        "label": "Expansao de Dominio",
        "parquet": "plano_expansao_dominio.parquet",
        "required_cols": ["ordem_expansao_cidade", "tese_dominio"],
        "optional_cols": ["residual_incremental_capturado"],
    },
}
COLOR_MODE_DEFAULT = "m1"
COLOR_MODE_IDS: list[str] = list(COLOR_MODES)

OVERLAYS: dict[str, dict] = {
    "concorrentes": {
        "label": "Concorrentes",
        "default": True,
        "required_cols": ["lat", "lng", "rede"],
        "absent_behavior": "hide_silently",
    },
    "ultra": {
        "label": "Ultra",
        "default": True,
        "required_cols": ["lat", "lng"],
        "absent_behavior": "hide_silently",
    },
    "ancoras_dominio": {
        "label": "Ancoras Dominio",
        "default": False,
        "required_cols": ["lat", "lng", "hex_id"],
        "absent_behavior": "hide_silently",
    },
    "hex_pesquisado": {
        "label": "Hex pesquisado",
        "default": True,
        "required_cols": [],
        "absent_behavior": "hide_when_no_search",
    },
    "descartados_5k": {
        "label": "Descartados <5k hab",
        "default": True,
        "required_cols": ["flag_pop_min_5k"],
        "absent_behavior": "show_neutral",
    },
}
OVERLAY_IDS: list[str] = list(OVERLAYS)


def color_mode_available(df, mode_id: str) -> bool:
    """Retorna True se todas as colunas obrigatorias do modo existirem no DataFrame."""
    cfg = COLOR_MODES.get(mode_id)
    if cfg is None:
        return False
    return all(c in df.columns for c in cfg["required_cols"])


def overlay_available(df, overlay_id: str) -> bool:
    """Retorna True se todas as colunas obrigatorias do overlay existirem no DataFrame."""
    cfg = OVERLAYS.get(overlay_id)
    if cfg is None:
        return False
    return all(c in df.columns for c in cfg["required_cols"])
