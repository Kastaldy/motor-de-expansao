from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

DATASET_PATH = Path("data/outputs/hexagonos_brasil_dashboard.parquet")
MAP_SAMPLE_PATH = Path("data/outputs/hexagonos_mapa_sample.parquet")
POWERBI_DIR = Path("powerbi/m1_dashboard_executivo")
EXPORT_DIR = Path("export")
DOC_PATH = Path("docs/powerbi_dashboard_m1.md")

EXPECTED_MODEL_COLUMNS = [
    "UF",
    "nome_municipio",
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

FAIXA_ORDER = [
    "prioridade_maxima",
    "alta",
    "media",
    "baixa",
    "descartado",
    "inviavel",
]

COLORS = {
    "bg": "#F4F6F8",
    "panel": "#FFFFFF",
    "panel_alt": "#E9EEF2",
    "border": "#D5DDE5",
    "text": "#0F172A",
    "muted": "#5B6677",
    "brand": "#153B5C",
    "brand_alt": "#0F6CBD",
    "accent": "#D97706",
    "good": "#1F7A5A",
    "warn": "#C2410C",
    "bad": "#B42318",
    "grid": "#DCE3EA",
}

FAIXA_COLORS = {
    "prioridade_maxima": "#0F6CBD",
    "alta": "#2F855A",
    "media": "#D97706",
    "baixa": "#C2410C",
    "descartado": "#94A3B8",
    "inviavel": "#CBD5E1",
}

UF_LABELS = {
    "AM": "Amazonas",
    "RR": "Roraima",
    "AP": "Amapa",
    "PA": "Para",
    "AC": "Acre",
    "RO": "Rondonia",
    "TO": "Tocantins",
    "MA": "Maranhao",
    "PI": "Piaui",
    "CE": "Ceara",
    "RN": "Rio Grande do Norte",
    "PB": "Paraiba",
    "PE": "Pernambuco",
    "AL": "Alagoas",
    "SE": "Sergipe",
    "BA": "Bahia",
    "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul",
    "GO": "Goias",
    "DF": "Distrito Federal",
    "MG": "Minas Gerais",
    "ES": "Espirito Santo",
    "RJ": "Rio de Janeiro",
    "SP": "Sao Paulo",
    "PR": "Parana",
    "SC": "Santa Catarina",
    "RS": "Rio Grande do Sul",
}


@dataclass
class SchemaValidation:
    source_columns: list[str]
    missing_source_columns: list[str]
    model_mapping: dict[str, str]


def format_int(value: int | float) -> str:
    return f"{int(round(float(value))):,}".replace(",", ".")


def format_pct(value: float) -> str:
    return f"{value:.1f}%"


def format_score(value: float) -> str:
    return f"{value:.2f}"


def safe_name(value: str) -> str:
    text = str(value).strip().lower()
    for source, target in [
        (" ", "_"),
        ("/", "_"),
        ("-", "_"),
        ("(", ""),
        (")", ""),
        (",", ""),
        (".", ""),
    ]:
        text = text.replace(source, target)
    return text


def load_dashboard_dataset(path: Path = DATASET_PATH) -> pd.DataFrame:
    columns = [
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
    return pd.read_parquet(path, columns=columns)


def load_map_sample(path: Path = MAP_SAMPLE_PATH) -> pd.DataFrame:
    columns = ["lat", "lng", "score_priorizacao", "faixa_oportunidade", "rank_brasil"]
    return pd.read_parquet(path, columns=columns)


def validate_schema(df: pd.DataFrame) -> SchemaValidation:
    model_mapping = {
        "UF": "uf",
        "nome_municipio": "cidade",
        "score_priorizacao": "score_priorizacao",
        "hex_score_estrutural": "hex_score_estrutural",
        "ajuste_executivo": "ajuste_executivo",
        "faixa_oportunidade": "faixa_oportunidade",
        "flag_viavel": "flag_viavel",
        "flag_prioridade": "flag_prioridade",
        "rank_brasil": "rank_brasil",
        "rank_uf": "rank_uf",
        "rank_cidade": "rank_cidade",
        "renda_per_capita": "renda_per_capita",
        "populacao_proxy": "populacao_proxy",
    }
    missing_source_columns = [
        source_column
        for source_column in model_mapping.values()
        if source_column not in df.columns
    ]
    return SchemaValidation(
        source_columns=list(df.columns),
        missing_source_columns=missing_source_columns,
        model_mapping=model_mapping,
    )


def build_city_summary(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby(["uf", "cidade"], as_index=False)
        .agg(
            total_hexagonos=("hex_id", "size"),
            oportunidades_viaveis=("flag_viavel", "sum"),
            hexagonos_priorizados=("flag_prioridade", "sum"),
            score_medio=("score_priorizacao", "mean"),
            score_maximo=("score_priorizacao", "max"),
            renda_per_capita=("renda_per_capita", "mean"),
            populacao_proxy=("populacao_proxy", "mean"),
            lat=("lat", "mean"),
            lng=("lng", "mean"),
            melhor_rank_brasil=("rank_brasil", "min"),
            melhor_rank_uf=("rank_uf", "min"),
            melhor_rank_cidade=("rank_cidade", "min"),
        )
        .copy()
    )
    grouped["pct_priorizados"] = np.where(
        grouped["total_hexagonos"] > 0,
        grouped["hexagonos_priorizados"] / grouped["total_hexagonos"] * 100,
        0.0,
    )
    return grouped


def build_uf_summary(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby("uf", as_index=False)
        .agg(
            total_hexagonos=("hex_id", "size"),
            oportunidades_viaveis=("flag_viavel", "sum"),
            hexagonos_priorizados=("flag_prioridade", "sum"),
            score_medio=("score_priorizacao", "mean"),
        )
        .copy()
    )
    grouped["pct_priorizados"] = (
        grouped["hexagonos_priorizados"] / grouped["total_hexagonos"] * 100
    )
    grouped["uf_nome"] = grouped["uf"].map(UF_LABELS).fillna(grouped["uf"])
    return grouped


def build_kpis(
    df: pd.DataFrame,
    city_summary: pd.DataFrame,
    uf_summary: pd.DataFrame,
) -> dict[str, str]:
    total_oportunidades_viaveis = int(df["flag_viavel"].sum())
    total_hexagonos_priorizados = int(df["flag_prioridade"].sum())
    uf_lider = (
        uf_summary.sort_values(
            ["oportunidades_viaveis", "score_medio", "uf"],
            ascending=[False, False, True],
            kind="stable",
        )
        .head(1)
        .iloc[0]
    )
    cidade_lider = (
        city_summary.sort_values(
            ["score_medio", "melhor_rank_brasil", "total_hexagonos", "cidade"],
            ascending=[False, True, False, True],
            kind="stable",
        )
        .head(1)
        .iloc[0]
    )
    return {
        "total_oportunidades_viaveis": format_int(total_oportunidades_viaveis),
        "total_hexagonos_priorizados": format_int(total_hexagonos_priorizados),
        "uf_lider_oportunidades": f"{uf_lider['uf']} ({format_int(uf_lider['oportunidades_viaveis'])})",
        "cidade_lider_score": f"{cidade_lider['cidade']} - {format_score(cidade_lider['score_medio'])}",
    }


def build_score_distribution(df: pd.DataFrame) -> pd.DataFrame:
    bins = np.arange(0, 110, 10)
    counts, edges = np.histogram(df["score_priorizacao"].to_numpy(), bins=bins)
    rows = []
    for idx, count in enumerate(counts):
        rows.append({"faixa": f"{int(edges[idx])}-{int(edges[idx + 1])}", "total": int(count)})
    return pd.DataFrame(rows)


def build_faixa_summary(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby("faixa_oportunidade", observed=False, as_index=False)
        .agg(
            total_hexagonos=("hex_id", "size"),
            oportunidades_viaveis=("flag_viavel", "sum"),
            score_medio=("score_priorizacao", "mean"),
            renda_media=("renda_per_capita", "mean"),
            populacao_media=("populacao_proxy", "mean"),
        )
        .copy()
    )
    grouped["faixa_oportunidade"] = pd.Categorical(
        grouped["faixa_oportunidade"],
        categories=FAIXA_ORDER,
        ordered=True,
    )
    return grouped.sort_values("faixa_oportunidade").reset_index(drop=True)


def build_filter_catalog(df: pd.DataFrame) -> dict[str, list[str]]:
    faixas = [value for value in FAIXA_ORDER if value in set(df["faixa_oportunidade"].astype(str))]
    return {
        "UF": sorted(df["uf"].dropna().astype(str).unique().tolist()),
        "nome_municipio": sorted(df["cidade"].dropna().astype(str).unique().tolist())[:50],
        "faixa_oportunidade": faixas,
    }


def build_business_answers(uf_summary: pd.DataFrame) -> dict[str, list[str]]:
    top_expand = (
        uf_summary.sort_values(
            ["oportunidades_viaveis", "score_medio", "pct_priorizados"],
            ascending=[False, False, False],
            kind="stable",
        )
        .head(5)
    )
    top_priority = (
        uf_summary.sort_values(
            ["score_medio", "oportunidades_viaveis", "pct_priorizados"],
            ascending=[False, False, False],
            kind="stable",
        )
        .head(5)
    )
    avoid = (
        uf_summary.sort_values(
            ["oportunidades_viaveis", "score_medio", "uf"],
            ascending=[True, True, True],
            kind="stable",
        )
        .head(5)
    )
    return {
        "onde_expandir": [
            f"{row.uf}: {format_int(row.oportunidades_viaveis)} oportunidades viaveis, score medio {format_score(row.score_medio)}"
            for row in top_expand.itertuples(index=False)
        ],
        "ufs_priorizar": [
            f"{row.uf}: score medio {format_score(row.score_medio)}, {format_int(row.oportunidades_viaveis)} oportunidades viaveis"
            for row in top_priority.itertuples(index=False)
        ],
        "onde_evitar": [
            f"{row.uf}: {format_int(row.oportunidades_viaveis)} oportunidades viaveis, score medio {format_score(row.score_medio)}"
            for row in avoid.itertuples(index=False)
        ],
    }


def build_measure_catalog() -> list[dict[str, str]]:
    return [
        {
            "name": "Total Oportunidades Viaveis",
            "formula": "CALCULATE(COUNTROWS('M1 Dashboard'), 'M1 Dashboard'[flag_viavel] = TRUE())",
            "purpose": "Card principal da visao executiva.",
        },
        {
            "name": "Total Hexagonos Priorizados",
            "formula": "CALCULATE(COUNTROWS('M1 Dashboard'), 'M1 Dashboard'[flag_prioridade] = TRUE())",
            "purpose": "Card de recorte priorizado oficial do M1.",
        },
        {
            "name": "Score Medio Priorizacao",
            "formula": "AVERAGE('M1 Dashboard'[score_priorizacao])",
            "purpose": "Media oficial para comparativos territoriais e por UF.",
        },
        {
            "name": "Pct Hexagonos Priorizados",
            "formula": "DIVIDE([Total Hexagonos Priorizados], COUNTROWS('M1 Dashboard'))",
            "purpose": "Indicador comparativo de cobertura priorizada por UF.",
        },
        {
            "name": "Renda Per Capita Media",
            "formula": "AVERAGE('M1 Dashboard'[renda_per_capita])",
            "purpose": "Indicador medio da analise territorial.",
        },
        {
            "name": "Populacao Proxy Media",
            "formula": "AVERAGE('M1 Dashboard'[populacao_proxy])",
            "purpose": "Indicador medio da analise territorial.",
        },
        {
            "name": "UF Lider em Oportunidades",
            "formula": "VAR _t = TOPN(1, SUMMARIZE('M1 Dashboard', 'M1 Dashboard'[UF], \"Oportunidades\", [Total Oportunidades Viaveis], \"Score\", [Score Medio Priorizacao]), [Oportunidades], DESC, [Score], DESC, 'M1 Dashboard'[UF], ASC) RETURN CONCATENATEX(_t, 'M1 Dashboard'[UF], \", \")",
            "purpose": "Card textual de lideranca por oportunidades viaveis.",
        },
        {
            "name": "Cidade Lider em Score",
            "formula": "VAR _t = TOPN(1, SUMMARIZE('M1 Dashboard', 'M1 Dashboard'[UF], 'M1 Dashboard'[nome_municipio], \"Score\", [Score Medio Priorizacao], \"MelhorRankBrasil\", MIN('M1 Dashboard'[rank_brasil])), [Score], DESC, [MelhorRankBrasil], ASC, 'M1 Dashboard'[nome_municipio], ASC) RETURN CONCATENATEX(_t, 'M1 Dashboard'[nome_municipio], \", \")",
            "purpose": "Card textual da cidade lider em score medio com desempate por rank Brasil.",
        },
    ]


def build_power_query_m() -> str:
    return "\n".join(
        [
            "let",
            '    Fonte = Parquet.Document(File.Contents(Parametros[M1_DatasetPath]{0}[Valor])),',
            '    #"Tipos Corrigidos" = Table.TransformColumnTypes(Fonte, {{"uf", type text}, {"cidade", type text}, {"score_priorizacao", type number}, {"hex_score_estrutural", type number}, {"ajuste_executivo", type number}, {"faixa_oportunidade", type text}, {"flag_viavel", type logical}, {"flag_prioridade", type logical}, {"rank_brasil", Int64.Type}, {"rank_uf", Int64.Type}, {"rank_cidade", Int64.Type}, {"renda_per_capita", type number}, {"populacao_proxy", type number}, {"lat", type number}, {"lng", type number}}),',
            '    #"Colunas Renomeadas" = Table.RenameColumns(#"Tipos Corrigidos", {{"uf", "UF"}, {"cidade", "nome_municipio"}})',
            "in",
            '    #"Colunas Renomeadas"',
        ]
    )


def build_theme() -> dict[str, object]:
    return {
        "name": "Ultra M1 Executivo",
        "dataColors": [
            COLORS["brand_alt"],
            COLORS["good"],
            COLORS["accent"],
            COLORS["warn"],
            "#4E79A7",
            "#76B7B2",
            "#F28E2B",
            "#E15759",
        ],
        "background": COLORS["bg"],
        "foreground": COLORS["text"],
        "tableAccent": COLORS["brand_alt"],
        "visualStyles": {
            "*": {
                "*": {
                    "title": [
                        {
                            "show": True,
                            "fontFamily": "Segoe UI Semibold",
                            "fontSize": 14,
                            "color": {"solid": {"color": COLORS["text"]}},
                        }
                    ],
                    "background": [
                        {
                            "show": True,
                            "color": {"solid": {"color": COLORS["panel"]}},
                            "transparency": 0,
                        }
                    ],
                    "border": [
                        {
                            "show": True,
                            "color": {"solid": {"color": COLORS["border"]}},
                            "radius": 6,
                        }
                    ],
                }
            }
        },
    }


def build_page_spec() -> list[dict[str, object]]:
    return [
        {
            "pagina": "01_visao_executiva",
            "titulo": "Visao Executiva",
            "visuais": [
                "Cards: total de oportunidades viaveis, total de hexagonos priorizados, UF lider em oportunidades, cidade lider em score",
                "Mapa principal com camada espacial disponivel por centroides",
                "Ranking Top 10 cidades",
                "Ranking Top 10 UFs",
                "Filtros: UF, nome_municipio, faixa_oportunidade",
            ],
        },
        {
            "pagina": "02_analise_territorial",
            "titulo": "Analise Territorial",
            "visuais": [
                "Dispersao: renda_per_capita x populacao_proxy com score_priorizacao em cor/tamanho",
                "Distribuicao de score",
                "Comparativo por faixa_oportunidade",
                "Indicadores medios por filtro aplicado",
            ],
        },
        {
            "pagina": "03_ranking_e_priorizacao",
            "titulo": "Ranking e Priorizacao",
            "visuais": [
                "Tabela executiva com colunas oficiais do M1",
                "Ordenacao padrao por rank_brasil ascendente",
                "Formatacao condicional por score_priorizacao",
            ],
        },
        {
            "pagina": "04_comparacao_por_uf",
            "titulo": "Comparacao por UF",
            "visuais": [
                "Barras: oportunidades viaveis por UF",
                "Barras: score medio por UF",
                "Barras: percentual de hexagonos priorizados por UF",
                "Destaque para top e bottom UFs",
            ],
        },
    ]


def get_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def text_box_size(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
) -> tuple[int, int]:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def draw_panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str | None = None,
) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=18, fill=COLORS["panel"], outline=COLORS["border"], width=2)
    if title:
        draw.text((x0 + 20, y0 + 14), title, font=get_font(22, bold=True), fill=COLORS["text"])


def draw_header(draw: ImageDraw.ImageDraw, title: str, subtitle: str) -> None:
    draw.text((48, 28), title, font=get_font(34, bold=True), fill=COLORS["brand"])
    draw.text((48, 72), subtitle, font=get_font(16), fill=COLORS["muted"])


def draw_card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str,
    value: str,
    note: str,
) -> None:
    draw_panel(draw, box)
    x0, y0, x1, _ = box
    draw.text((x0 + 18, y0 + 18), title, font=get_font(16, bold=True), fill=COLORS["muted"])
    draw.text((x0 + 18, y0 + 56), value, font=get_font(28, bold=True), fill=COLORS["text"])
    draw.text((x0 + 18, y0 + 100), note, font=get_font(14), fill=COLORS["muted"])


def draw_filter_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    draw_panel(draw, box, "Filtros")
    x0, y0, x1, _ = box
    filters = [
        ("UF", "multisselecao"),
        ("nome_municipio", "pesquisa"),
        ("faixa_oportunidade", "lista oficial"),
    ]
    cursor_y = y0 + 46
    for name, detail in filters:
        draw.rounded_rectangle(
            (x0 + 18, cursor_y, x1 - 18, cursor_y + 32),
            radius=10,
            fill=COLORS["panel_alt"],
            outline=COLORS["border"],
        )
        draw.text((x0 + 28, cursor_y + 6), name, font=get_font(13, bold=True), fill=COLORS["text"])
        draw.text((x1 - 170, cursor_y + 7), detail, font=get_font(11), fill=COLORS["muted"])
        cursor_y += 42


def scale_values(values: np.ndarray, *, min_size: float, max_size: float) -> np.ndarray:
    if len(values) == 0:
        return np.array([])
    vmin = float(np.min(values))
    vmax = float(np.max(values))
    if math.isclose(vmin, vmax):
        return np.full(len(values), (min_size + max_size) / 2)
    return min_size + ((values - vmin) / (vmax - vmin)) * (max_size - min_size)


def score_to_color(score: float) -> str:
    if score >= 80:
        return COLORS["brand_alt"]
    if score >= 60:
        return COLORS["good"]
    if score >= 40:
        return COLORS["accent"]
    if score >= 20:
        return COLORS["warn"]
    return COLORS["bad"]


def draw_map_cloud(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    df_map: pd.DataFrame,
) -> None:
    draw_panel(draw, box, "Mapa principal")
    x0, y0, x1, y1 = box
    chart_box = (x0 + 20, y0 + 52, x1 - 20, y1 - 20)
    cx0, cy0, cx1, cy1 = chart_box
    draw.rounded_rectangle(chart_box, radius=14, fill="#F9FBFC", outline=COLORS["border"])

    sample = df_map.copy()
    sampled_frames = []
    for faixa in FAIXA_ORDER:
        faixa_sample = sample.loc[sample["faixa_oportunidade"].astype(str) == faixa]
        if not faixa_sample.empty:
            sampled_frames.append(faixa_sample.sample(n=min(3600, len(faixa_sample)), random_state=42))
    if sampled_frames:
        sample = pd.concat(sampled_frames, ignore_index=True)
    elif len(sample) > 18000:
        sample = sample.sample(n=18000, random_state=42)
    if sample.empty:
        return

    lng_min, lng_max = sample["lng"].min(), sample["lng"].max()
    lat_min, lat_max = sample["lat"].min(), sample["lat"].max()
    width = max(1, cx1 - cx0 - 20)
    height = max(1, cy1 - cy0 - 20)

    for row in sample.itertuples(index=False):
        px = cx0 + 10 + ((row.lng - lng_min) / (lng_max - lng_min)) * width
        py = cy1 - 10 - ((row.lat - lat_min) / (lat_max - lat_min)) * height
        color = FAIXA_COLORS.get(str(row.faixa_oportunidade), COLORS["brand_alt"])
        draw.ellipse((px - 2, py - 2, px + 2, py + 2), fill=color)

    legend_y = cy0 + 14
    legend_x = cx1 - 210
    for faixa in FAIXA_ORDER:
        color = FAIXA_COLORS[faixa]
        draw.ellipse((legend_x, legend_y + 4, legend_x + 10, legend_y + 14), fill=color)
        draw.text((legend_x + 18, legend_y), faixa, font=get_font(13), fill=COLORS["text"])
        legend_y += 22

    draw.text(
        (cx0 + 16, cy1 - 34),
        "Camada espacial disponivel: centroides oficiais de hexagonos do M1",
        font=get_font(13),
        fill=COLORS["muted"],
    )


def draw_horizontal_bars(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    df: pd.DataFrame,
    label_col: str,
    value_col: str,
    title: str,
    *,
    value_fmt,
    color: str,
) -> None:
    draw_panel(draw, box, title)
    x0, y0, x1, y1 = box
    cx0, cy0, cx1, cy1 = x0 + 20, y0 + 56, x1 - 20, y1 - 18
    usable_height = cy1 - cy0
    rows = len(df)
    if rows == 0:
        return
    row_height = usable_height / rows
    max_value = float(df[value_col].max()) if rows else 1.0
    for idx, row in enumerate(df.itertuples(index=False)):
        y = cy0 + idx * row_height
        label = getattr(row, label_col)
        value = float(getattr(row, value_col))
        draw.text((cx0, y + 2), str(label), font=get_font(14, bold=True), fill=COLORS["text"])
        bar_x0 = cx0 + 140
        bar_width = max(1, cx1 - bar_x0 - 90)
        filled = bar_width * (value / max_value if max_value else 0)
        bar_top = int(y + 2)
        bar_bottom = max(bar_top + 12, int(y + row_height - 6))
        bar_left = int(bar_x0)
        bar_right = int(bar_x0 + bar_width)
        fill_right = max(bar_left + 12, int(bar_x0 + filled))
        draw.rounded_rectangle(
            (bar_left, bar_top, bar_right, bar_bottom),
            radius=8,
            fill="#EEF3F7",
            outline=COLORS["border"],
        )
        draw.rounded_rectangle(
            (bar_left, bar_top, fill_right, bar_bottom),
            radius=8,
            fill=color,
        )
        value_text = value_fmt(value)
        text_width, _ = text_box_size(draw, value_text, get_font(13, bold=True))
        draw.text((cx1 - text_width, y + 6), value_text, font=get_font(13, bold=True), fill=COLORS["text"])


def draw_scatter(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    size_col: str,
    color_col: str,
    title: str,
) -> None:
    draw_panel(draw, box, title)
    x0, y0, x1, y1 = box
    cx0, cy0, cx1, cy1 = x0 + 54, y0 + 56, x1 - 28, y1 - 44
    draw.rectangle((cx0, cy0, cx1, cy1), outline=COLORS["grid"], width=1)
    for step in range(1, 5):
        y = cy0 + step * (cy1 - cy0) / 5
        x = cx0 + step * (cx1 - cx0) / 5
        draw.line((cx0, y, cx1, y), fill=COLORS["grid"], width=1)
        draw.line((x, cy0, x, cy1), fill=COLORS["grid"], width=1)
    if df.empty:
        return
    sample = df.sort_values(["score_medio", "total_hexagonos"], ascending=[False, False]).head(300).copy()
    xs = sample[x_col].to_numpy(dtype=float)
    ys = sample[y_col].to_numpy(dtype=float)
    sizes = scale_values(sample[size_col].to_numpy(dtype=float), min_size=4, max_size=18)
    xmin, xmax = float(xs.min()), float(xs.max())
    ymin, ymax = float(ys.min()), float(ys.max())
    for idx, row in enumerate(sample.itertuples(index=False)):
        px = cx0 + ((getattr(row, x_col) - xmin) / (xmax - xmin)) * (cx1 - cx0)
        py = cy1 - ((getattr(row, y_col) - ymin) / (ymax - ymin)) * (cy1 - cy0)
        radius = float(sizes[idx])
        color = score_to_color(float(getattr(row, color_col)))
        draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=color, outline="#FFFFFF")
    draw.text((cx0, cy1 + 12), "renda_per_capita", font=get_font(13, bold=True), fill=COLORS["muted"])
    draw.text((x0 + 18, cy0 - 26), "populacao_proxy", font=get_font(13, bold=True), fill=COLORS["muted"])


def draw_vertical_bars(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    df: pd.DataFrame,
    label_col: str,
    value_col: str,
    title: str,
    *,
    color_map: dict[str, str] | None = None,
    show_value: bool = False,
    value_fmt=None,
) -> None:
    draw_panel(draw, box, title)
    x0, y0, x1, y1 = box
    cx0, cy0, cx1, cy1 = x0 + 20, y0 + 54, x1 - 18, y1 - 26
    draw.line((cx0, cy1, cx1, cy1), fill=COLORS["grid"], width=1)
    rows = len(df)
    if rows == 0:
        return
    bar_width = max(18, (cx1 - cx0) / max(rows * 1.6, 1))
    gap = bar_width * 0.6
    max_value = float(df[value_col].max()) if rows else 1.0
    for idx, row in enumerate(df.itertuples(index=False)):
        label = str(getattr(row, label_col))
        value = float(getattr(row, value_col))
        px0 = cx0 + idx * (bar_width + gap)
        px1 = px0 + bar_width
        py0 = cy1 - ((value / max_value) * (cy1 - cy0 - 18) if max_value else 0)
        color = color_map.get(label, COLORS["brand_alt"]) if color_map else COLORS["brand_alt"]
        draw.rounded_rectangle((px0, py0, px1, cy1), radius=8, fill=color)
        label_width, _ = text_box_size(draw, label, get_font(12))
        draw.text((px0 + (bar_width - label_width) / 2, cy1 + 6), label, font=get_font(12), fill=COLORS["text"])
        if show_value and value_fmt is not None:
            value_text = value_fmt(value)
            vwidth, _ = text_box_size(draw, value_text, get_font(11))
            draw.text((px0 + (bar_width - vwidth) / 2, py0 - 18), value_text, font=get_font(11), fill=COLORS["muted"])


def draw_indicator_block(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    metrics: list[tuple[str, str]],
) -> None:
    draw_panel(draw, box, "Indicadores medios")
    x0, y0, _, _ = box
    cursor_y = y0 + 58
    step = 42 if len(metrics) >= 4 else 66
    for label, value in metrics:
        draw.text((x0 + 18, cursor_y), label, font=get_font(15), fill=COLORS["muted"])
        draw.text((x0 + 18, cursor_y + 16), value, font=get_font(20, bold=True), fill=COLORS["text"])
        cursor_y += step


def draw_table(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    df: pd.DataFrame,
    title: str,
    score_column: str,
) -> None:
    draw_panel(draw, box, title)
    x0, y0, x1, y1 = box
    table_x0, table_y0 = x0 + 18, y0 + 56
    columns = list(df.columns)
    widths = [70, 52, 180, 80, 62, 62, 150, 88, 62, 150]
    header_height = 34
    row_height = 28
    draw.rounded_rectangle(
        (table_x0, table_y0, x1 - 18, table_y0 + header_height),
        radius=8,
        fill=COLORS["brand"],
    )
    cursor_x = table_x0 + 8
    for width, column in zip(widths, columns, strict=False):
        draw.text((cursor_x, table_y0 + 8), column, font=get_font(12, bold=True), fill="#FFFFFF")
        cursor_x += width

    for idx, row in enumerate(df.itertuples(index=False)):
        row_y = table_y0 + header_height + idx * row_height
        if row_y + row_height > y1 - 16:
            break
        fill = "#FBFCFD" if idx % 2 == 0 else "#F1F5F9"
        draw.rectangle((table_x0, row_y, x1 - 18, row_y + row_height), fill=fill)
        cursor_x = table_x0 + 8
        for width, column in zip(widths, columns, strict=False):
            value = getattr(row, column)
            fill_color = COLORS["text"]
            if column == score_column:
                score_fill = score_to_color(float(value))
                draw.rounded_rectangle(
                    (cursor_x - 4, row_y + 3, cursor_x + width - 8, row_y + row_height - 3),
                    radius=6,
                    fill=score_fill,
                )
                fill_color = "#FFFFFF"
            draw.text((cursor_x, row_y + 7), str(value), font=get_font(11), fill=fill_color)
            cursor_x += width


def draw_callout(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str,
    lines: list[str],
    *,
    tone: str,
) -> None:
    fill = {"good": "#E8F4EF", "warn": "#FFF4E8", "bad": "#FDECEC"}[tone]
    accent = {"good": COLORS["good"], "warn": COLORS["accent"], "bad": COLORS["bad"]}[tone]
    draw.rounded_rectangle(box, radius=16, fill=fill, outline=accent, width=2)
    x0, y0, _, _ = box
    draw.text((x0 + 18, y0 + 14), title, font=get_font(16, bold=True), fill=accent)
    cursor_y = y0 + 42
    for line in lines:
        draw.text((x0 + 18, cursor_y), line, font=get_font(13), fill=COLORS["text"])
        cursor_y += 20


def render_visao_executiva(
    df: pd.DataFrame,
    df_map: pd.DataFrame,
    city_summary: pd.DataFrame,
    uf_summary: pd.DataFrame,
    output_path: Path,
) -> None:
    image = Image.new("RGB", (1600, 900), COLORS["bg"])
    draw = ImageDraw.Draw(image)
    draw_header(
        draw,
        "M1 Dashboard Executivo | Visao Executiva",
        "Leitura de ate 30 segundos para onde expandir, o que priorizar e o que evitar com base no dataset oficial validado.",
    )
    kpis = build_kpis(df, city_summary, uf_summary)
    card_y = 114
    card_width = 330
    gap = 20
    titles = [
        ("Total oportunidades viaveis", kpis["total_oportunidades_viaveis"], "Hexagonos com flag_viavel = TRUE"),
        ("Total hexagonos priorizados", kpis["total_hexagonos_priorizados"], "Recorte oficial top 20% por UF"),
        ("UF lider em oportunidades", kpis["uf_lider_oportunidades"], "Maior volume de oportunidades viaveis"),
        ("Cidade lider em score", kpis["cidade_lider_score"], "Score medio com desempate por rank Brasil"),
    ]
    for idx, (title, value, note) in enumerate(titles):
        x0 = 48 + idx * (card_width + gap)
        draw_card(draw, (x0, card_y, x0 + card_width, card_y + 134), title, value, note)

    draw_map_cloud(draw, (48, 270, 1040, 842), df_map)

    top_cities = (
        city_summary.sort_values(
            ["oportunidades_viaveis", "score_medio", "melhor_rank_brasil", "cidade"],
            ascending=[False, False, True, True],
            kind="stable",
        )
        .head(10)[["cidade", "oportunidades_viaveis"]]
        .reset_index(drop=True)
    )
    top_ufs = (
        uf_summary.sort_values(
            ["oportunidades_viaveis", "score_medio", "uf"],
            ascending=[False, False, True],
            kind="stable",
        )
        .head(10)[["uf", "oportunidades_viaveis"]]
        .reset_index(drop=True)
    )
    draw_horizontal_bars(
        draw,
        (1070, 270, 1552, 520),
        top_cities,
        "cidade",
        "oportunidades_viaveis",
        "Ranking Top 10 cidades",
        value_fmt=format_int,
        color=COLORS["brand_alt"],
    )
    draw_horizontal_bars(
        draw,
        (1070, 536, 1552, 726),
        top_ufs,
        "uf",
        "oportunidades_viaveis",
        "Ranking Top 10 UFs",
        value_fmt=format_int,
        color=COLORS["good"],
    )
    draw_filter_panel(draw, (1070, 742, 1552, 842))
    image.save(output_path)


def render_analise_territorial(
    df: pd.DataFrame,
    city_summary: pd.DataFrame,
    output_path: Path,
) -> None:
    image = Image.new("RGB", (1600, 900), COLORS["bg"])
    draw = ImageDraw.Draw(image)
    draw_header(
        draw,
        "M1 Dashboard Executivo | Analise Territorial",
        "Leitura estrutural do territorio com foco em renda, populacao proxy e score oficial de priorizacao.",
    )
    draw_scatter(
        draw,
        (48, 120, 980, 620),
        city_summary,
        "renda_per_capita",
        "populacao_proxy",
        "total_hexagonos",
        "score_medio",
        "Dispersao territorial por municipio",
    )
    score_distribution = build_score_distribution(df)
    draw_vertical_bars(
        draw,
        (1006, 120, 1552, 368),
        score_distribution,
        "faixa",
        "total",
        "Distribuicao de score",
        color_map={row.faixa: COLORS["brand_alt"] for row in score_distribution.itertuples(index=False)},
        show_value=False,
    )
    faixa_summary = build_faixa_summary(df)
    faixa_summary_plot = faixa_summary.assign(
        faixa_oportunidade=faixa_summary["faixa_oportunidade"].astype(str)
    )
    faixa_colors = {
        row.faixa_oportunidade: FAIXA_COLORS[str(row.faixa_oportunidade)]
        for row in faixa_summary_plot.itertuples(index=False)
    }
    draw_vertical_bars(
        draw,
        (1006, 392, 1552, 620),
        faixa_summary_plot,
        "faixa_oportunidade",
        "score_medio",
        "Comparativo por faixa_oportunidade",
        color_map=faixa_colors,
        show_value=True,
        value_fmt=format_score,
    )
    metrics = [
        ("Score medio", format_score(float(df["score_priorizacao"].mean()))),
        ("Renda per capita media", format_score(float(df["renda_per_capita"].mean()))),
        ("Populacao proxy media", format_int(float(df["populacao_proxy"].mean()))),
        ("UFs cobertas", format_int(df["uf"].nunique())),
    ]
    draw_indicator_block(draw, (48, 646, 520, 842), metrics)
    draw_callout(
        draw,
        (544, 646, 1040, 842),
        "Leitura executiva",
        [
            "Quadrante superior direito concentra municipios com maior combinacao",
            "de renda e populacao proxy, reforcando a tese territorial do M1.",
            "Use score_priorizacao como eixo de decisao e hex_score_estrutural",
            "como leitura de base para explicar o territorio.",
        ],
        tone="good",
    )
    top_faixa = faixa_summary_plot.sort_values("score_medio", ascending=False, kind="stable").head(1).iloc[0]
    low_faixa = faixa_summary_plot.sort_values("score_medio", ascending=True, kind="stable").head(1).iloc[0]
    draw_callout(
        draw,
        (1064, 646, 1552, 842),
        "Faixas de leitura",
        [
            f"Melhor faixa: {top_faixa['faixa_oportunidade']} com score medio {format_score(top_faixa['score_medio'])}",
            f"Menor faixa: {low_faixa['faixa_oportunidade']} com score medio {format_score(low_faixa['score_medio'])}",
            "A distribuicao de volume ajuda a calibrar onde ha escala real.",
        ],
        tone="warn",
    )
    image.save(output_path)


def render_ranking_priorizacao(df: pd.DataFrame, output_path: Path) -> None:
    image = Image.new("RGB", (1600, 900), COLORS["bg"])
    draw = ImageDraw.Draw(image)
    draw_header(
        draw,
        "M1 Dashboard Executivo | Ranking e Priorizacao",
        "Tabela executiva para priorizacao nacional, com foco em rank oficial e score_priorizacao.",
    )
    table_df = (
        df.sort_values("rank_brasil", ascending=True, kind="stable")
        .head(20)
        .assign(
            UF=lambda data: data["uf"],
            nome_municipio=lambda data: data["cidade"],
            score_priorizacao=lambda data: data["score_priorizacao"].round(2),
            faixa_oportunidade=lambda data: data["faixa_oportunidade"].astype(str),
        )[
            [
                "rank_brasil",
                "UF",
                "nome_municipio",
                "score_priorizacao",
                "rank_uf",
                "rank_cidade",
                "faixa_oportunidade",
                "flag_prioridade",
                "flag_viavel",
                "hex_id",
            ]
        ]
        .rename(columns={"hex_id": "hex_ref"})
    )
    draw_table(draw, (48, 120, 1552, 710), table_df, "Tabela executiva do ranking oficial", "score_priorizacao")
    draw_callout(
        draw,
        (48, 736, 760, 842),
        "Uso recomendado",
        [
            "Ordene sempre por rank_brasil ascendente para manter a narrativa oficial.",
            "A cor no score destaca a qualidade relativa sem recalcular o contrato do M1.",
            "UF e nome_municipio sao aliases de exibicao sobre uf e cidade do parquet oficial.",
        ],
        tone="good",
    )
    draw_callout(
        draw,
        (786, 736, 1552, 842),
        "Colunas expostas",
        [
            "UF, nome_municipio, score_priorizacao, rank_brasil, rank_uf, rank_cidade,",
            "faixa_oportunidade, flag_prioridade e flag_viavel.",
            "hex_score_estrutural e ajuste_executivo permanecem no modelo para drill adicional.",
        ],
        tone="warn",
    )
    image.save(output_path)


def render_comparacao_uf(uf_summary: pd.DataFrame, output_path: Path) -> None:
    image = Image.new("RGB", (1600, 900), COLORS["bg"])
    draw = ImageDraw.Draw(image)
    draw_header(
        draw,
        "M1 Dashboard Executivo | Comparacao por UF",
        "Comparativo para priorizacao estadual, destacando escala, qualidade media e cobertura priorizada.",
    )
    uf_sorted_opps = uf_summary.sort_values("oportunidades_viaveis", ascending=False, kind="stable")
    uf_sorted_score = uf_summary.sort_values("score_medio", ascending=False, kind="stable")
    uf_sorted_pct = uf_summary.sort_values("pct_priorizados", ascending=False, kind="stable")

    top_bottom_opps = pd.concat([uf_sorted_opps.head(5), uf_sorted_opps.tail(5)]).drop_duplicates("uf")
    top_bottom_score = pd.concat([uf_sorted_score.head(5), uf_sorted_score.tail(5)]).drop_duplicates("uf")
    top_bottom_pct = pd.concat([uf_sorted_pct.head(5), uf_sorted_pct.tail(5)]).drop_duplicates("uf")

    opp_colors = {
        row.uf: (COLORS["brand_alt"] if row.uf in set(uf_sorted_opps.head(5)["uf"]) else COLORS["bad"])
        for row in top_bottom_opps.itertuples(index=False)
    }
    score_colors = {
        row.uf: (COLORS["good"] if row.uf in set(uf_sorted_score.head(5)["uf"]) else COLORS["warn"])
        for row in top_bottom_score.itertuples(index=False)
    }
    pct_colors = {row.uf: COLORS["brand"] for row in top_bottom_pct.itertuples(index=False)}

    draw_vertical_bars(
        draw,
        (48, 120, 540, 520),
        top_bottom_opps[["uf", "oportunidades_viaveis"]].reset_index(drop=True),
        "uf",
        "oportunidades_viaveis",
        "Oportunidades viaveis por UF",
        color_map=opp_colors,
        show_value=True,
        value_fmt=format_int,
    )
    draw_vertical_bars(
        draw,
        (564, 120, 1056, 520),
        top_bottom_score[["uf", "score_medio"]].reset_index(drop=True),
        "uf",
        "score_medio",
        "Score medio por UF",
        color_map=score_colors,
        show_value=True,
        value_fmt=format_score,
    )
    draw_vertical_bars(
        draw,
        (1080, 120, 1552, 520),
        top_bottom_pct[["uf", "pct_priorizados"]].reset_index(drop=True),
        "uf",
        "pct_priorizados",
        "% de hexagonos priorizados",
        color_map=pct_colors,
        show_value=True,
        value_fmt=format_pct,
    )

    answers = build_business_answers(uf_summary)
    draw_callout(draw, (48, 560, 516, 842), "Onde expandir", answers["onde_expandir"], tone="good")
    draw_callout(draw, (540, 560, 1032, 842), "UFs a priorizar", answers["ufs_priorizar"], tone="warn")
    draw_callout(draw, (1056, 560, 1552, 842), "Onde evitar", answers["onde_evitar"], tone="bad")
    image.save(output_path)


def write_powerbi_package(
    schema: SchemaValidation,
    filter_catalog: dict[str, list[str]],
    page_spec: list[dict[str, object]],
    measures: list[dict[str, str]],
) -> None:
    POWERBI_DIR.mkdir(parents=True, exist_ok=True)
    theme_path = POWERBI_DIR / "theme_ultra_m1_executivo.json"
    query_path = POWERBI_DIR / "m1_dashboard_dataset.m"
    dax_path = POWERBI_DIR / "m1_dashboard_measures.dax"
    spec_path = POWERBI_DIR / "m1_dashboard_layout.json"
    model_doc_path = POWERBI_DIR / "m1_dashboard_modelo.md"

    theme_path.write_text(json.dumps(build_theme(), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    query_path.write_text(build_power_query_m() + "\n", encoding="utf-8")

    dax_lines = ["-- Tabela base sugerida: 'M1 Dashboard'", ""]
    for measure in measures:
        dax_lines.append(f"-- {measure['purpose']}")
        dax_lines.append(f"[{measure['name']}] = {measure['formula']}")
        dax_lines.append("")
    dax_path.write_text("\n".join(dax_lines).strip() + "\n", encoding="utf-8")
    spec_path.write_text(json.dumps(page_spec, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    model_lines = [
        "# Modelo Power BI do Dashboard Executivo M1",
        "",
        "## Fonte oficial",
        "",
        f"- Dataset: `{DATASET_PATH.as_posix()}`",
        "- Restricao mantida: nenhum parquet oficial foi alterado.",
        "",
        "## Mapeamento do modelo",
        "",
    ]
    for model_column, source_column in schema.model_mapping.items():
        model_lines.append(f"- `{model_column}` <- `{source_column}`")
    model_lines.extend(["", "## Filtros previstos", ""])
    for filter_name, values in filter_catalog.items():
        preview = ", ".join(values[:8])
        if len(values) > 8:
            preview += ", ..."
        model_lines.append(f"- `{filter_name}`: {preview}")
    model_doc_path.write_text("\n".join(model_lines) + "\n", encoding="utf-8")


def write_short_document(
    df: pd.DataFrame,
    schema: SchemaValidation,
    measures: list[dict[str, str]],
    page_spec: list[dict[str, object]],
) -> None:
    limitations = [
        "O ambiente atual nao possui Power BI Desktop nem ferramenta equivalente para gerar `.pbix` automaticamente.",
        "O dataset oficial nao expoe `UF` e `nome_municipio` com esses aliases; o modelo usa mapeamento de exibicao sobre `uf` e `cidade`.",
        "Os screenshots representam o dashboard executivo final, mas nao substituem a interatividade nativa do Power BI.",
    ]
    lines = [
        "# Dashboard Executivo M1 no Power BI",
        "",
        "## Estrutura final do dashboard",
        "",
    ]
    for page in page_spec:
        lines.append(f"- `{page['titulo']}`: " + "; ".join(page["visuais"]))
    lines.extend(["", "## Medidas criadas", ""])
    for measure in measures:
        lines.append(f"- `{measure['name']}`: `{measure['formula']}`")
    lines.extend(
        [
            "",
            "## Filtros disponiveis",
            "",
            "- `UF`",
            "- `nome_municipio`",
            "- `faixa_oportunidade`",
            "",
            "## Validacao do dataset",
            "",
            f"- Linhas: {format_int(len(df))}",
            f"- Colunas lidas: {len(schema.source_columns)}",
            f"- Colunas obrigatorias ausentes no modelo: {len(schema.missing_source_columns)}",
            "",
            "## Limitacoes encontradas",
            "",
        ]
    )
    for limitation in limitations:
        lines.append(f"- {limitation}")
    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_dashboard_assets() -> dict[str, object]:
    df = load_dashboard_dataset()
    df_map = load_dashboard_dataset()
    schema = validate_schema(df)
    if schema.missing_source_columns:
        raise ValueError(f"Schema invalido para o modelo Power BI: {schema.missing_source_columns}")

    city_summary = build_city_summary(df)
    uf_summary = build_uf_summary(df)
    filter_catalog = build_filter_catalog(df)
    measures = build_measure_catalog()
    page_spec = build_page_spec()

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    render_visao_executiva(df, df_map, city_summary, uf_summary, EXPORT_DIR / "01_visao_executiva.png")
    render_analise_territorial(df, city_summary, EXPORT_DIR / "02_analise_territorial.png")
    render_ranking_priorizacao(df, EXPORT_DIR / "03_ranking_priorizacao.png")
    render_comparacao_uf(uf_summary, EXPORT_DIR / "04_comparacao_por_uf.png")

    write_powerbi_package(schema, filter_catalog, page_spec, measures)
    write_short_document(df, schema, measures, page_spec)

    return {
        "dataset_path": DATASET_PATH.as_posix(),
        "export_dir": EXPORT_DIR.as_posix(),
        "powerbi_dir": POWERBI_DIR.as_posix(),
        "doc_path": DOC_PATH.as_posix(),
        "pages": [page["titulo"] for page in page_spec],
        "measures": [measure["name"] for measure in measures],
    }


def main() -> None:
    artifacts = export_dashboard_assets()
    print("Pacote do dashboard M1 gerado com sucesso.")
    print(f"Dataset: {artifacts['dataset_path']}")
    print(f"Screenshots: {artifacts['export_dir']}")
    print(f"Power BI package: {artifacts['powerbi_dir']}")
    print(f"Documento: {artifacts['doc_path']}")


if __name__ == "__main__":
    main()
