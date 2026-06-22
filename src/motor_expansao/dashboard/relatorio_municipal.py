"""Relatorio Municipal (BLK-RELMUN-01) — PDF de 8 paginas por municipio selecionado.

Modulo NOVO e disjunto. COEXISTE com o Relatorio Pontual Censitario (raio 1,5 km),
que fica BYTE-A-BYTE INTOCADO (este modulo NAO importa nenhum helper `_`-prefixado de
`censo_report.py`/`censo_map.py`; os helpers de layout/desenho sao reimplementados aqui
para isolamento total). READ-ONLY sobre o M1: nao recalcula `score_priorizacao`,
`hex_score_estrutural`, pesos, carteira, plano, plano de dominio nem artefatos oficiais.

Decisoes do gate humano (Vinicius, 2026-06-22 — DEC-011):
- D1: hex DESTACADO ("amarelo") <=> `sam_fitness_potencial >= 3000` E
  `oferta_efetiva_disponivel >= 2000`. Rotulo sobre o hex = `oferta_efetiva_disponivel`.
  "Espaco para academias" = round( sum(oferta_efetiva_disponivel destacados) / 2500 ).
- D2: zonas via `dominio_df` agrupado por `cluster_id` (fallback gracioso).
- D3: mapas COM TILES ONLINE (contextily/EPSG:3857, cache `data/cache/basemap_tiles/`,
  import lazy, fallback offline gracioso -> canvas claro; `basemap=False` em CI/teste).
- D4: Mercado/Residual = sum(oferta_efetiva_disponivel) do municipio (alunos).
- D5: faixas Score Censitario: Alto >=70 / Medio-alto 50-70 / Medio 30-50 / Baixo <30.
- D6: contagem de pins Ultra/concorrentes por filtro geografico H3 res-7.
- D7: redacao zonas: 1 Ancora central / 2 Flancos laterais / 3 Cerco.
- D8: Pagina 8 so com redes mapeadas + carimbo de versao no rodape.
- D9: Pagina 6 (bairros) SIMPLIFICADA por zona/cluster + nota (sem NM_BAIRRO).
"""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

from motor_expansao.dashboard.competitors import _render_pin_tile
from motor_expansao.dashboard.utils import score_band_to_color

# ---------------------------------------------------------------------------
# Constantes de DISPLAY do relatorio (DEC-011 parte 2). Locais a este modulo;
# NAO mexem em flag_sam/DEC-006/DEC-007 (pipeline de mercado) nem no M1.
# ---------------------------------------------------------------------------
SAM_DESTAQUE_MIN = 3000.0
OFERTA_DESTAQUE_MIN = 2000.0
CAPACIDADE_UNIDADE = 2500.0
H3_RES = 7

# Carimbo de versao do contrato deste relatorio (D8 / espirito DEC-005 item 6).
VERSAO_CONTRATO_MUNICIPAL = "BLK-RELMUN-01 | contrato v1 | score M1 INALTERADO"
METODO_RELATORIO_MUNICIPAL = "agregacao_municipal_h3_res7"

# Cabecalhos canonicos das 8 paginas (ASCII; cada string aparece nos bytes crus do PDF,
# pois a compressao do stream esta desativada).
PDF_SECTION_HEADERS = (
    "Potencial de Entrada de Novas Unidades",
    "Resumo da Regiao",
    "Score Censitario",
    "Residual Fitness",
    "Expansao de Dominio",
    "Bairros por Zona",
    "Sintese",
    "Espaco e academias",
)

# Paleta Ultra (RGB 0..255). Espelha censo_report (cores canonicas), reimplementado local.
ULTRA_TURQUESA = (0, 167, 157)
ULTRA_MAGENTA = (194, 60, 142)
ULTRA_LARANJA = (240, 148, 30)
ULTRA_BRANCO_GELO = (248, 248, 248)
_BRANCO = (255, 255, 255)
_CINZA_TEXTO = (60, 60, 60)
_NAVY_CAPA = (30, 28, 58)

# Cor do hexagono destacado ("amarelo") e do nao-destacado (cinza), na camada Resumo.
_HEX_DESTAQUE_RGBA = (255, 210, 28, 200)
_HEX_NEUTRO_RGBA = (176, 182, 196, 110)
_CIRCLE_INK = (31, 41, 55)

_ATRIBUICAO_TILES = "(c) OpenStreetMap, (c) CARTO"
_CREDITO_ULTRA = "Relatorio gerado pelo Motor de Expansao - Ultra Academia"

_ASSET_CAPA = "relatorio_capa_bg.png"
_ASSET_CONTEUDO = "relatorio_conteudo_bg.png"
_ASSET_LOGO = "logo_ultra.png"
_ASSET_ICONE = "icone_ultra.png"
_DEFAULT_ULTRA_DIR = Path("data/ultra")

# Slide 16:9 widescreen em pontos (13.333in x 7.5in = 960 x 540 pt).
_PAGE_W = 960.0
_PAGE_H = 540.0

# Marca d'agua de rastreabilidade (anti-PII; embutida em todas as 8 paginas, stream OFF).
_WATERMARK_BASE = "Ultra Academia"
_WATERMARK_RGB = (120, 120, 120)
_WATERMARK_RGB_COVER = (255, 255, 255)
_WATERMARK_ALPHA = 0.65
_WATERMARK_FONT_PT = 10
_WATERMARK_MARGIN = 20.0

# Cap de desenho de hexes (performance, R5): municipios grandes nao devem estourar o tempo.
_HEX_DRAW_CAP = 8000

# Cache de tiles (DEC-004/DEC-011). Nunca versionado (data/cache/ no .gitignore).
_BASEMAP_CACHE_DIR = Path("data/cache/basemap_tiles")
_BASEMAP_PROVIDER_ATTR = "Voyager"
CRS_WEB_MERCATOR = "EPSG:3857"
CRS_WGS84 = "EPSG:4326"

# Faixas do Score Censitario do template (D5): Alto >=70 / Medio-alto 50-70 / Medio 30-50 /
# Baixo <30. Cor representativa via RESIDUAL_SCORE_BANDS (centro da banda de score).
SCORE_FAIXAS_TEMPLATE: tuple[tuple[str, float, float], ...] = (
    ("Alto potencial", 70.0, 100.0),
    ("Medio-alto", 50.0, 70.0),
    ("Medio", 30.0, 50.0),
    ("Baixo potencial", 0.0, 30.0),
)


@dataclass(frozen=True)
class RelatorioMunicipalDownloadPayloads:
    pdf_bytes: bytes
    pdf_filename: str


# ===========================================================================
# Helpers de texto/formatacao
# ===========================================================================


def _ascii(text: str) -> str:
    """Reduz a latin-1/ASCII seguro para o core font Helvetica do fpdf2."""
    return str(text).encode("latin-1", errors="replace").decode("latin-1")


def _slug(text: str) -> str:
    norm = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")
    out = "".join(ch.lower() if ch.isalnum() else "_" for ch in norm)
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_") or "municipio"


def _format_number(value: Any, decimals: int = 0, suffix: str = "") -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)) or pd.isna(value):
        return "n/d"
    number = float(value)
    if decimals <= 0:
        text = f"{number:,.0f}".replace(",", ".")
    else:
        text = f"{number:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text}{suffix}"


def _safe_float(value: Any) -> float:
    num = pd.to_numeric(value, errors="coerce")
    try:
        f = float(num)
    except (TypeError, ValueError):
        return float("nan")
    return f


# ===========================================================================
# Agregacao do municipio (READ-ONLY; unico ponto que toca dados)
# ===========================================================================


def _municipio_mask(df: pd.DataFrame, nome_municipio: str) -> pd.Series:
    """Mascara de linhas do municipio: tenta `nome_municipio`, fallback `cidade`."""
    alvo = str(nome_municipio).strip().casefold()
    mask = pd.Series(False, index=df.index)
    for col in ("nome_municipio", "cidade"):
        if col in df.columns:
            mask = mask | (df[col].astype(str).str.strip().str.casefold() == alvo)
    return mask


def _hex_destacado_mask(df_muni: pd.DataFrame) -> pd.Series:
    """D1: destacado <=> sam_fitness_potencial>=3000 E oferta_efetiva_disponivel>=2000."""
    if df_muni.empty:
        return pd.Series(False, index=df_muni.index)
    sam = pd.to_numeric(df_muni.get("sam_fitness_potencial"), errors="coerce")
    oferta = pd.to_numeric(df_muni.get("oferta_efetiva_disponivel"), errors="coerce")
    return (sam >= SAM_DESTAQUE_MIN) & (oferta >= OFERTA_DESTAQUE_MIN)


def _zonas_do_municipio(
    dominio_df: pd.DataFrame | None, nome_municipio: str
) -> list[dict[str, Any]]:
    """D2/D7: zonas a partir de `dominio_df` agrupado por `cluster_id` do municipio.

    Ordena os clusters por residual desc e numera Zona 1..N (cap em 3 para casar com a
    redacao do template, D7). Fallback gracioso: `dominio_df` None/vazio/sem o municipio
    -> lista vazia (Paginas 5-6 entram em modo simplificado, sem excecao).
    """
    if dominio_df is None or dominio_df.empty:
        return []
    if "cluster_id" not in dominio_df.columns or "nome_municipio" not in dominio_df.columns:
        return []
    alvo = str(nome_municipio).strip().casefold()
    sub = dominio_df[dominio_df["nome_municipio"].astype(str).str.strip().str.casefold() == alvo]
    if sub.empty:
        return []

    rotulos = ("Ancora central", "Flancos laterais", "Cerco")
    zonas: list[dict[str, Any]] = []
    for cluster_id, grupo in sub.groupby("cluster_id", dropna=True):
        residual = _safe_float(grupo.get("residual_total_cluster", pd.Series(dtype=float)).max())
        if math.isnan(residual):
            residual = _safe_float(
                pd.to_numeric(grupo.get("oferta_efetiva_disponivel"), errors="coerce").sum()
            )
        tese = ""
        if "tese_dominio" in grupo.columns and not grupo["tese_dominio"].dropna().empty:
            tese = str(grupo["tese_dominio"].dropna().mode().iloc[0])
        zonas.append(
            {
                "cluster_id": str(cluster_id),
                "n_hex": int(len(grupo)),
                "residual_cluster": 0.0 if math.isnan(residual) else float(residual),
                "tese_dominio": tese,
            }
        )

    zonas.sort(key=lambda z: z["residual_cluster"], reverse=True)
    zonas = zonas[:3]
    for idx, zona in enumerate(zonas):
        zona["zona_n"] = idx + 1
        zona["rotulo"] = rotulos[idx] if idx < len(rotulos) else f"Zona {idx + 1}"
    return zonas


def _pins_no_municipio(
    df_muni: pd.DataFrame,
    competitors_df: pd.DataFrame | None,
    ultra_df: pd.DataFrame | None,
) -> tuple[int, int, dict[str, int]]:
    """D6: conta pins Ultra/concorrentes cujo hex H3 res-7 cai nos hexes do municipio.

    Reusa `hex_id_res7` quando presente; senao deriva via h3. Anti-PII: usa so `rede`.
    Retorna (n_ultra, n_concorrentes, {rede: contagem}).
    """
    hexes_muni: set[str] = set()
    if "hex_id" in df_muni.columns:
        hexes_muni = {str(h) for h in df_muni["hex_id"].dropna().astype(str)}
    if not hexes_muni:
        return 0, 0, {}

    def _hexes_of(frame: pd.DataFrame | None) -> pd.Series | None:
        if frame is None or frame.empty:
            return None
        if "hex_id_res7" in frame.columns:
            return frame["hex_id_res7"].astype(str)
        if {"lat", "lng"}.issubset(frame.columns):
            import h3

            out: list[str] = []
            for _, row in frame.iterrows():
                la = _safe_float(row.get("lat"))
                lo = _safe_float(row.get("lng"))
                if math.isnan(la) or math.isnan(lo):
                    out.append("")
                    continue
                out.append(str(h3.latlng_to_cell(float(la), float(lo), H3_RES)))
            return pd.Series(out, index=frame.index)
        return None

    n_ultra = 0
    ultra_hexes = _hexes_of(ultra_df)
    if ultra_hexes is not None:
        n_ultra = int(ultra_hexes.isin(hexes_muni).sum())

    n_conc = 0
    por_rede: dict[str, int] = {}
    conc_hexes = _hexes_of(competitors_df)
    if conc_hexes is not None and competitors_df is not None:
        in_muni = conc_hexes.isin(hexes_muni)
        n_conc = int(in_muni.sum())
        if "rede" in competitors_df.columns:
            redes = competitors_df.loc[in_muni, "rede"].astype(str)
            por_rede = {
                str(rede): int(cnt) for rede, cnt in redes.value_counts().items()
            }
    return n_ultra, n_conc, por_rede


def agregar_municipio(
    df: pd.DataFrame,
    *,
    nome_municipio: str,
    uf: str | None = None,
    dominio_df: pd.DataFrame | None = None,
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Agrega o dicionario canonico de metricas do municipio. READ-ONLY (so le colunas).

    Filtra `df` por `nome_municipio` (fallback `cidade`) e computa as metricas das 8 paginas
    conforme as decisoes do gate (D1/D4/D5/D6). NUNCA recalcula score ou artefatos do M1.
    """
    mask = _municipio_mask(df, nome_municipio)
    df_muni = df.loc[mask].copy()

    uf_value = str(uf).strip().upper() if uf else ""
    if not uf_value and "uf" in df_muni.columns and not df_muni["uf"].dropna().empty:
        uf_value = str(df_muni["uf"].dropna().iloc[0]).strip().upper()

    n_hex_total = int(len(df_muni))

    destaque_mask = _hex_destacado_mask(df_muni)
    oferta = pd.to_numeric(df_muni.get("oferta_efetiva_disponivel"), errors="coerce")
    oferta_destacados = oferta[destaque_mask].dropna()
    soma_oferta_amarelos = float(oferta_destacados.sum()) if not oferta_destacados.empty else 0.0
    n_hex_amarelos = int(destaque_mask.sum())
    espaco_para_academias = int(round(soma_oferta_amarelos / CAPACIDADE_UNIDADE)) if CAPACIDADE_UNIDADE else 0
    # Ate 5 maiores parcelas para a caixa "Como calculamos".
    parcelas = [float(v) for v in oferta_destacados.sort_values(ascending=False).head(5).tolist()]

    score_col = pd.to_numeric(df_muni.get("score_setor_2022_calibrado"), errors="coerce").dropna()
    score_censo_medio = float(score_col.mean()) if not score_col.empty else float("nan")
    score_censo_max = float(score_col.max()) if not score_col.empty else float("nan")

    mercado_disponivel = float(oferta.dropna().sum()) if not oferta.dropna().empty else 0.0

    pop_serie = pd.to_numeric(df_muni.get("pop_total_setor_2022"), errors="coerce")
    if pop_serie.dropna().empty:
        pop_serie = pd.to_numeric(df_muni.get("pop_total"), errors="coerce")
    pop_total_municipio = float(pop_serie.dropna().sum()) if not pop_serie.dropna().empty else float("nan")

    renda = pd.to_numeric(df_muni.get("renda_per_capita"), errors="coerce")
    pesos = pd.to_numeric(df_muni.get("pop_total_setor_2022"), errors="coerce")
    valid = renda.notna() & pesos.notna() & (pesos > 0)
    if valid.any():
        renda_per_capita_media = float((renda[valid] * pesos[valid]).sum() / pesos[valid].sum())
    elif renda.dropna().any():
        renda_per_capita_media = float(renda.dropna().mean())
    else:
        renda_per_capita_media = float("nan")

    penetr = pd.to_numeric(df_muni.get("penetracao_fitness_mercado_estimada"), errors="coerce").dropna()
    penetracao_fitness_media = float(penetr.mean()) if not penetr.empty else float("nan")

    zonas = _zonas_do_municipio(dominio_df, nome_municipio)
    n_ultra, n_concorrentes, concorrentes_por_rede = _pins_no_municipio(
        df_muni, competitors_df, ultra_df
    )

    return {
        "nome_municipio": str(nome_municipio).strip(),
        "uf": uf_value,
        "n_hex_total": n_hex_total,
        "n_hex_amarelos": n_hex_amarelos,
        "soma_oferta_amarelos": soma_oferta_amarelos,
        "espaco_para_academias": espaco_para_academias,
        "parcelas_amarelos": parcelas,
        "score_censo_medio": score_censo_medio,
        "score_censo_max": score_censo_max,
        "mercado_disponivel_pessoas": mercado_disponivel,
        "residual_total_alunos": mercado_disponivel,
        "pop_total_municipio": pop_total_municipio,
        "renda_per_capita_media": renda_per_capita_media,
        "penetracao_fitness_media": penetracao_fitness_media,
        "n_zonas": len(zonas),
        "zonas": zonas,
        "n_ultra": n_ultra,
        "n_concorrentes": n_concorrentes,
        "concorrentes_por_rede": concorrentes_por_rede,
        "versao_contrato": VERSAO_CONTRATO_MUNICIPAL,
        "metodo": METODO_RELATORIO_MUNICIPAL,
    }


# ===========================================================================
# Mapas do municipio (Pillow + tiles online via contextily; D3)
# ===========================================================================


def _score_faixa_color(value: float, alpha: int = 200) -> tuple[int, int, int, int]:
    rgba = score_band_to_color(value, alpha=alpha)
    return (int(rgba[0]), int(rgba[1]), int(rgba[2]), int(rgba[3]))


def _font(size: int = 12) -> ImageFont.ImageFont:
    from typing import cast

    try:
        return cast(ImageFont.ImageFont, ImageFont.truetype("arial.ttf", size))
    except OSError:
        return cast(ImageFont.ImageFont, ImageFont.load_default())


def _lonlat_to_mercator(lon: float, lat: float) -> tuple[float, float]:
    """WGS84 lon/lat -> EPSG:3857 (sem dependencia de pyproj para o caminho do municipio)."""
    r = 6378137.0
    x = math.radians(lon) * r
    lat = max(min(lat, 85.05112878), -85.05112878)
    y = r * math.log(math.tan(math.pi / 4.0 + math.radians(lat) / 2.0))
    return x, y


def _hex_boundary_mercator(hex_id: str) -> list[tuple[float, float]]:
    import h3

    boundary = h3.cell_to_boundary(hex_id)  # [(lat, lng), ...]
    return [_lonlat_to_mercator(lng, lat) for lat, lng in boundary]


def _fetch_basemap_municipio(
    bounds_3857: tuple[float, float, float, float], width: int
) -> tuple[object, tuple[float, float, float, float]] | None:
    """Tiles de basemap claro via contextily (DEC-011). Import LAZY; None em qualquer falha.

    Sem o extra [basemap] ou sem internet -> None -> chamador cai no canvas claro offline.
    Cache local em data/cache/basemap_tiles/.
    """
    try:
        import contextily as ctx  # lazy: so existe com o extra [basemap]
    except ImportError:
        return None
    try:
        _BASEMAP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            ctx.set_cache_dir(str(_BASEMAP_CACHE_DIR))
        except Exception:
            pass
        minx, miny, maxx, maxy = bounds_3857
        earth = 2.0 * math.pi * 6378137.0
        span = max(maxx - minx, 1.0)
        zoom = 19
        for z in range(0, 20):
            res = earth / (256.0 * (2**z))
            if span / res >= width:
                zoom = max(0, min(z, 19))
                break
        source = getattr(ctx.providers.CartoDB, _BASEMAP_PROVIDER_ATTR)
        img, extent = ctx.bounds2img(minx, miny, maxx, maxy, zoom=zoom, source=source, ll=False)
        return img, extent
    except Exception:
        return None


def _render_mapa_municipio(
    df_muni: pd.DataFrame,
    *,
    camada: str,
    municipio_result: dict[str, Any],
    zonas: list[dict[str, Any]] | None = None,
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
    width: int = 1000,
    height: int = 620,
    basemap: bool = False,
) -> bytes:
    """Renderiza um PNG do municipio. `camada` define o esquema de cor dos hexes:

    - "resumo": destacados em amarelo (rotulo = oferta_efetiva_disponivel), demais cinza.
    - "score": choropleth por `score_setor_2022_calibrado` (D5).
    - "residual": choropleth por `score_oportunidade_residual`.
    - "dominio": hexes coloridos por zona (1/2/3) das zonas do `dominio_df` (fallback amarelo).

    `basemap=True` busca tiles online (DEC-011) com fallback offline. Em CI/teste default
    `basemap=False`. READ-ONLY sobre o M1.
    """
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image, "RGBA")
    titulo = {
        "resumo": "Resumo da regiao",
        "score": "Score censitario",
        "residual": "Residual fitness",
        "dominio": "Expansao de dominio",
    }.get(camada, camada)
    _draw_text(draw, (24, 18), titulo, font=_font(20))

    map_box = (20, 60, width - 20, height - 40)
    left, top, right, bottom = map_box

    rows = df_muni.copy()
    if "hex_id" not in rows.columns or rows.empty:
        draw.rounded_rectangle(map_box, radius=6, fill=(245, 245, 245), outline=(120, 120, 120))
        _draw_text(draw, (left + 16, (top + bottom) // 2), "Mapa indisponivel para este municipio.", font=_font(13))
        out = BytesIO()
        image.save(out, format="PNG", optimize=True)
        return out.getvalue()

    # Cap de desenho de hexes (performance).
    if len(rows) > _HEX_DRAW_CAP:
        sort_col = "oferta_efetiva_disponivel" if "oferta_efetiva_disponivel" in rows.columns else None
        if sort_col is None and "score_setor_2022_calibrado" in rows.columns:
            sort_col = "score_setor_2022_calibrado"
        if sort_col is not None:
            rows = rows.sort_values(sort_col, ascending=False).head(_HEX_DRAW_CAP)
        else:
            rows = rows.head(_HEX_DRAW_CAP)

    # Geometria dos hexes em 3857 + bbox.
    geometrias: list[tuple[list[tuple[float, float]], int]] = []
    minx = miny = math.inf
    maxx = maxy = -math.inf
    for pos, (_, row) in enumerate(rows.iterrows()):
        try:
            poly = _hex_boundary_mercator(str(row["hex_id"]))
        except Exception:
            continue
        if not poly:
            continue
        geometrias.append((poly, pos))
        for x, y in poly:
            minx, maxx = min(minx, x), max(maxx, x)
            miny, maxy = min(miny, y), max(maxy, y)

    if not geometrias or not math.isfinite(minx):
        draw.rounded_rectangle(map_box, radius=6, fill=(245, 245, 245), outline=(120, 120, 120))
        _draw_text(draw, (left + 16, (top + bottom) // 2), "Mapa indisponivel para este municipio.", font=_font(13))
        out = BytesIO()
        image.save(out, format="PNG", optimize=True)
        return out.getvalue()

    # Margem de 6% na bbox.
    pad_x = (maxx - minx) * 0.06 + 1.0
    pad_y = (maxy - miny) * 0.06 + 1.0
    minx, maxx = minx - pad_x, maxx + pad_x
    miny, maxy = miny - pad_y, maxy + pad_y
    span_x = max(maxx - minx, 1.0)
    span_y = max(maxy - miny, 1.0)
    inner_w = right - left - 16
    inner_h = bottom - top - 16
    scale = min(inner_w / span_x, inner_h / span_y)
    offset_x = left + 8 + (inner_w - span_x * scale) / 2
    offset_y = top + 8 + (inner_h - span_y * scale) / 2

    def project(x: float, y: float) -> tuple[float, float]:
        px = offset_x + (x - minx) * scale
        py = offset_y + (maxy - y) * scale
        return px, py

    # Fundo: basemap online (DEC-011) ou canvas claro offline.
    drew_basemap = False
    if basemap:
        tiles = _fetch_basemap_municipio((minx, miny, maxx, maxy), width)
        if tiles is not None:
            try:
                img_array, extent = tiles
                bm = Image.fromarray(np.asarray(img_array)).convert("RGB")
                ex_minx, ex_maxx, ex_miny, ex_maxy = extent
                tx0, ty0 = project(ex_minx, ex_maxy)
                tx1, ty1 = project(ex_maxx, ex_miny)
                box_w = max(1, int(round(tx1 - tx0)))
                box_h = max(1, int(round(ty1 - ty0)))
                bm = bm.resize((box_w, box_h), Image.Resampling.LANCZOS)
                canvas = Image.new("RGB", (width, height), (245, 245, 245))
                canvas.paste(bm, (int(round(tx0)), int(round(ty0))))
                patch = canvas.crop((left, top, right, bottom))
                image.paste(patch, (left, top))
                draw.rounded_rectangle(map_box, radius=6, outline=(120, 120, 120))
                drew_basemap = True
            except Exception:
                drew_basemap = False
    if not drew_basemap:
        draw.rounded_rectangle(map_box, radius=6, fill=(245, 245, 245), outline=(120, 120, 120))

    # Pre-computa flags/valores por camada.
    destaque_mask = _hex_destacado_mask(rows).to_numpy()
    oferta_hex = pd.to_numeric(rows.get("oferta_efetiva_disponivel"), errors="coerce").to_numpy()
    score_hex = pd.to_numeric(rows.get("score_setor_2022_calibrado"), errors="coerce").to_numpy()
    residual_hex = pd.to_numeric(rows.get("score_oportunidade_residual"), errors="coerce").to_numpy()

    label_pins: list[tuple[int, int, str]] = []
    for poly, pos in geometrias:
        pixels = [(int(round(px)), int(round(py))) for px, py in (project(x, y) for x, y in poly)]
        if len(pixels) < 3:
            continue
        if camada == "resumo":
            color = _HEX_DESTAQUE_RGBA if destaque_mask[pos] else _HEX_NEUTRO_RGBA
            draw.polygon(pixels, fill=color, outline=(255, 255, 255, 90))
            if destaque_mask[pos] and not math.isnan(oferta_hex[pos]):
                cx = int(sum(p[0] for p in pixels) / len(pixels))
                cy = int(sum(p[1] for p in pixels) / len(pixels))
                label_pins.append((cx, cy, _format_number(oferta_hex[pos], 0)))
        elif camada == "score":
            color = _score_faixa_color(score_hex[pos])
            draw.polygon(pixels, fill=color, outline=(255, 255, 255, 70))
        elif camada == "residual":
            color = _score_faixa_color(residual_hex[pos])
            draw.polygon(pixels, fill=color, outline=(255, 255, 255, 70))
        elif camada == "dominio":
            color = _HEX_DESTAQUE_RGBA if destaque_mask[pos] else _HEX_NEUTRO_RGBA
            draw.polygon(pixels, fill=color, outline=(255, 255, 255, 90))

    # Rotulos de oferta sobre hexes amarelos (camada resumo).
    label_font = _font(11)
    for cx, cy, txt in label_pins:
        w = _text_width(draw, txt, label_font)
        draw.rectangle([cx - w // 2 - 2, cy - 8, cx + w // 2 + 2, cy + 8], fill=(255, 255, 255, 200))
        _draw_text(draw, (cx - w // 2, cy - 7), txt, font=label_font, fill=_CIRCLE_INK)

    # Pins de Ultra/concorrentes (geograficos; dentro da bbox).
    _draw_pins(draw, image, competitors_df, project, "", minx, maxx, miny, maxy)
    _draw_pins(draw, image, ultra_df, project, "__ultra__", minx, maxx, miny, maxy)

    # Rodape com atribuicao quando ha basemap.
    footer = (
        f"Agregacao H3 res 7 - EPSG:3857 - {_ATRIBUICAO_TILES}"
        if drew_basemap
        else "Agregacao H3 res 7 - fundo de ruas offline"
    )
    _draw_text(draw, (24, height - 28), footer, font=_font(11), fill=(71, 85, 105))

    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _draw_pins(
    draw: ImageDraw.ImageDraw,
    image: Image.Image,
    frame: pd.DataFrame | None,
    project: Any,
    forced_key: str,
    minx: float,
    maxx: float,
    miny: float,
    maxy: float,
) -> None:
    if frame is None or frame.empty or not {"lat", "lng"}.issubset(frame.columns):
        return
    for _, row in frame.iterrows():
        la = _safe_float(row.get("lat"))
        lo = _safe_float(row.get("lng"))
        if math.isnan(la) or math.isnan(lo):
            continue
        x, y = _lonlat_to_mercator(float(lo), float(la))
        if not (minx <= x <= maxx and miny <= y <= maxy):
            continue
        px, py = project(x, y)
        if forced_key:
            key = forced_key
        else:
            rede = row.get("rede")
            key = str(rede) if rede is not None and not pd.isna(rede) and str(rede).strip() else ""
        try:
            from typing import cast

            tile = cast(Image.Image, _render_pin_tile(key))
            size = 34
            tile = tile.resize((size, size), Image.Resampling.LANCZOS)
            image.paste(tile, (int(px) - size // 2, int(py) - size), tile)
        except Exception:
            draw.ellipse([px - 4, py - 4, px + 4, py + 4], fill=ULTRA_MAGENTA if not forced_key else ULTRA_TURQUESA)


def _draw_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    fill: tuple[int, int, int] = (31, 41, 55),
    font: ImageFont.ImageFont | None = None,
) -> None:
    draw.text(xy, text, fill=fill, font=font or _font())


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return int(bbox[2] - bbox[0])


def render_mapas_municipio(
    df_muni: pd.DataFrame,
    municipio_result: dict[str, Any],
    *,
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
    basemap: bool = False,
    width: int = 1000,
    height: int = 620,
) -> dict[str, bytes]:
    """Gera as 4 camadas de mapa do relatorio (resumo/score/residual/dominio)."""
    zonas = municipio_result.get("zonas", [])
    return {
        camada: _render_mapa_municipio(
            df_muni,
            camada=camada,
            municipio_result=municipio_result,
            zonas=zonas,
            competitors_df=competitors_df,
            ultra_df=ultra_df,
            basemap=basemap,
            width=width,
            height=height,
        )
        for camada in ("resumo", "score", "residual", "dominio")
    }


# ===========================================================================
# Assets de branding (offline-safe)
# ===========================================================================


def _load_branding_assets(ultra_dir: Path | str | None) -> dict[str, bytes | None]:
    base = Path(ultra_dir) if ultra_dir is not None else _DEFAULT_ULTRA_DIR
    assets: dict[str, bytes | None] = {"capa": None, "conteudo": None, "logo": None, "icone": None}
    for key, filename in (
        ("capa", _ASSET_CAPA),
        ("conteudo", _ASSET_CONTEUDO),
        ("logo", _ASSET_LOGO),
        ("icone", _ASSET_ICONE),
    ):
        path = base / filename
        try:
            raw = path.read_bytes()
            Image.open(BytesIO(raw)).verify()
            assets[key] = raw
        except Exception:
            assets[key] = None
    return assets


def _png_dimensions(raw: bytes) -> tuple[int, int] | None:
    try:
        with Image.open(BytesIO(raw)) as image:
            return image.width, image.height
    except Exception:
        return None


# ===========================================================================
# Writer fpdf2 (helpers de layout reimplementados localmente — isolamento total)
# ===========================================================================


class _UltraPDF(FPDF):
    """FPDF com compressao desativada (auditabilidade anti-PII + asserts de texto cru)."""

    def __init__(self) -> None:
        super().__init__(orientation="L", unit="pt", format=(540, 960))
        self.pdf_version = "1.4"
        self.set_compression(False)
        self.set_auto_page_break(False)
        self.set_margins(0, 0, 0)


def _draw_full_page_background(
    pdf: _UltraPDF, image_bytes: bytes | None, solid_rgb: tuple[int, int, int]
) -> None:
    if image_bytes is not None:
        try:
            pdf.image(BytesIO(image_bytes), x=0, y=0, w=_PAGE_W, h=_PAGE_H)
            return
        except Exception:
            pass
    pdf.set_fill_color(*solid_rgb)
    pdf.rect(0, 0, _PAGE_W, _PAGE_H, style="F")


def _draw_title_band(pdf: _UltraPDF, title: str, *, rgb: tuple[int, int, int] = ULTRA_TURQUESA) -> None:
    band_h = 56.0
    pdf.set_fill_color(*rgb)
    pdf.rect(0, 0, _PAGE_W, band_h, style="F")
    pdf.set_text_color(*_BRANCO)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_xy(36, 16)
    pdf.cell(_PAGE_W - 72, 24, _ascii(title))


def _draw_footer(pdf: _UltraPDF, *, versao: str | None = None, with_attribution: bool = True) -> None:
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_xy(36, _PAGE_H - 22)
    text = _CREDITO_ULTRA
    if with_attribution:
        text = f"{text}   |   {_ATRIBUICAO_TILES}"
    if versao:
        text = f"{text}   |   {versao}"
    pdf.cell(_PAGE_W - 72, 12, _ascii(text))


def _draw_map(pdf: _UltraPDF, png_bytes: bytes | None, *, max_w: float = 600.0, max_h: float = 430.0,
              x_anchor: float = 36.0, y_anchor: float = 70.0) -> None:
    if not png_bytes:
        pdf.set_text_color(*_CINZA_TEXTO)
        pdf.set_font("Helvetica", "", 12)
        pdf.set_xy(x_anchor, y_anchor + 40)
        pdf.cell(max_w, 18, _ascii("Mapa indisponivel para esta camada."))
        return
    dims = _png_dimensions(png_bytes)
    if dims is None:
        return
    img_w, img_h = dims
    scale = min(max_w / img_w, max_h / img_h)
    draw_w = img_w * scale
    draw_h = img_h * scale
    x = x_anchor + (max_w - draw_w) / 2.0
    y = y_anchor + (max_h - draw_h) / 2.0
    try:
        pdf.image(BytesIO(png_bytes), x=x, y=y, w=draw_w, h=draw_h)
    except Exception:
        pass


def _draw_watermark(pdf: _UltraPDF, text: str, *, rgb: tuple[int, int, int] = _WATERMARK_RGB) -> None:
    pdf.set_font("Helvetica", "", _WATERMARK_FONT_PT)
    pdf.set_text_color(*rgb)
    w = pdf.get_string_width(text)
    x = _PAGE_W - _WATERMARK_MARGIN - w
    y = _PAGE_H - _WATERMARK_MARGIN
    with pdf.local_context(fill_opacity=_WATERMARK_ALPHA):
        pdf.text(x, y, text)


def _watermark_text(solicitante: str | None) -> str:
    if solicitante is None or not solicitante.strip():
        return _ascii(_WATERMARK_BASE)
    return _ascii(f"{_WATERMARK_BASE} | {solicitante.strip()}")


def _local_label(result: dict[str, Any]) -> str:
    municipio = str(result.get("nome_municipio") or "").strip()
    uf = str(result.get("uf") or "").strip()
    return f"{municipio} - {uf}".strip(" -") if (municipio or uf) else "Municipio"


# ===========================================================================
# Paginas do PDF (8)
# ===========================================================================


def _info_panel(pdf: _UltraPDF, x: float, y: float, w: float, titulo: str,
                linhas: list[tuple[str, str]], *, accent: tuple[int, int, int] = ULTRA_TURQUESA) -> float:
    """Painel lateral "rotulo | valor". Retorna o y final."""
    pdf.set_fill_color(*_BRANCO)
    pdf.set_draw_color(225, 225, 228)
    row_h = 26.0
    panel_h = 36.0 + len(linhas) * row_h + 12.0
    pdf.rect(x, y, w, panel_h, style="DF")
    pdf.set_fill_color(*accent)
    pdf.rect(x, y, w, 6.0, style="F")
    pdf.set_text_color(*accent)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(x + 14, y + 16)
    pdf.cell(w - 28, 16, _ascii(titulo))
    pdf.set_font("Helvetica", "", 12)
    yy = y + 42
    for rotulo, valor in linhas:
        pdf.set_text_color(45, 45, 45)
        pdf.set_xy(x + 14, yy)
        pdf.cell((w - 28) * 0.62, 16, _ascii(rotulo))
        pdf.set_text_color(40, 40, 40)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_xy(x + 14 + (w - 28) * 0.62, yy)
        pdf.cell((w - 28) * 0.38, 16, _ascii(valor), align="R")
        pdf.set_font("Helvetica", "", 12)
        yy += row_h
    return y + panel_h


def _cover_page(pdf: _UltraPDF, result: dict[str, Any], assets: dict[str, bytes | None]) -> None:
    pdf.add_page()
    has_bg = assets.get("capa") is not None
    _draw_full_page_background(pdf, assets.get("capa"), _NAVY_CAPA)
    if has_bg:
        block_x, block_w, align = 478.0, 446.0, "L"
        title_y = 300.0
    else:
        block_x, block_w, align = 60.0, _PAGE_W - 120, "C"
        title_y = 190.0
    pdf.set_text_color(*_BRANCO)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(block_x, title_y - 34)
    pdf.cell(block_w, 16, _ascii("ANALISE DE EXPANSAO"), align=align)
    # Titulo em UMA linha (cell, nao multi_cell) p/ a string canonica aparecer contigua nos
    # bytes crus do PDF (compressao OFF). Fonte ajustada ao bloco; quebra visual em duas
    # linhas via subtitulo curto abaixo, mantendo a hierarquia do template.
    pdf.set_font("Helvetica", "B", 24 if has_bg else 30)
    pdf.set_xy(block_x, title_y)
    pdf.cell(block_w, 36, _ascii("Potencial de Entrada de Novas Unidades"), align=align)
    pdf.set_font("Helvetica", "", 13)
    pdf.set_xy(block_x, title_y + 96)
    pdf.multi_cell(
        block_w, 18,
        _ascii("Mapeamento competitivo por regiao - Ultra e espaco disponivel para novas academias"),
        align=align,
    )
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_xy(block_x, title_y + 142)
    pdf.cell(block_w, 20, _ascii(_local_label(result)), align=align)


def _resumo_page(pdf: _UltraPDF, result: dict[str, Any], mapa: bytes | None,
                 assets: dict[str, bytes | None]) -> None:
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, f"Resumo da Regiao - {_local_label(result)}")
    _draw_map(pdf, mapa, max_w=560.0, max_h=400.0, x_anchor=24.0, y_anchor=70.0)

    px = 610.0
    pw = _PAGE_W - px - 36.0
    y_end = _info_panel(
        pdf, px, 70.0, pw, "RESUMO DA REGIAO",
        [
            ("Unidades Ultra", _format_number(result.get("n_ultra"), 0)),
            ("Unidades Concorrentes", _format_number(result.get("n_concorrentes"), 0)),
            ("Espaco para academias", _format_number(result.get("espaco_para_academias"), 0)),
        ],
    )
    # Box "Como calculamos o espaco".
    pdf.set_fill_color(*_BRANCO)
    pdf.set_draw_color(225, 225, 228)
    pdf.rect(px, y_end + 12, pw, 110.0, style="DF")
    pdf.set_text_color(*ULTRA_MAGENTA)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(px + 12, y_end + 22)
    pdf.cell(pw - 24, 14, _ascii("Como calculamos o espaco"))
    pdf.set_text_color(45, 45, 45)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(px + 12, y_end + 42)
    pdf.multi_cell(pw - 24, 13, _ascii("Soma dos hexagonos amarelos / 2.500"))
    parcelas = result.get("parcelas_amarelos") or []
    soma = result.get("soma_oferta_amarelos", 0.0)
    if parcelas:
        expr = " + ".join(_format_number(p, 0) for p in parcelas)
        if len(parcelas) < int(result.get("n_hex_amarelos", 0)):
            expr += " + ..."
        pdf.set_xy(px + 12, y_end + 60)
        pdf.multi_cell(pw - 24, 13, _ascii(f"{expr} = {_format_number(soma, 0)}"))
    pdf.set_xy(px + 12, y_end + 88)
    pdf.cell(pw - 24, 14, _ascii(f"/ 2.500 -> {_format_number(result.get('espaco_para_academias'), 0)}"))
    _draw_footer(pdf, versao=result.get("versao_contrato"))


def _score_page(pdf: _UltraPDF, result: dict[str, Any], mapa: bytes | None,
                assets: dict[str, bytes | None]) -> None:
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, "Score Censitario")
    _draw_map(pdf, mapa, max_w=600.0, max_h=400.0, x_anchor=24.0, y_anchor=70.0)
    # Legenda 4 faixas (D5) com cor representativa via RESIDUAL_SCORE_BANDS.
    px = 650.0
    pw = _PAGE_W - px - 36.0
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(px, 80.0)
    pdf.cell(pw, 16, _ascii("Potencial socioeconomico"))
    yy = 110.0
    for label, _lo, hi in SCORE_FAIXAS_TEMPLATE:
        rgba = score_band_to_color(min(hi - 1.0, 95.0), alpha=255)
        pdf.set_fill_color(int(rgba[0]), int(rgba[1]), int(rgba[2]))
        pdf.rect(px, yy, 20, 16, style="F")
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_xy(px + 28, yy)
        pdf.cell(pw - 28, 16, _ascii(label))
        yy += 28
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(px, yy + 12)
    pdf.multi_cell(pw, 12, _ascii(
        f"Score medio {_format_number(result.get('score_censo_medio'), 1)} | "
        f"max {_format_number(result.get('score_censo_max'), 1)}"
    ))
    pdf.set_xy(36, _PAGE_H - 36)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(_PAGE_W - 72, 12, _ascii("Fonte: IBGE Censo 2022 - Agregacao H3 resolucao 7"))
    _draw_footer(pdf, versao=result.get("versao_contrato"))


def _residual_page(pdf: _UltraPDF, result: dict[str, Any], mapa: bytes | None,
                   assets: dict[str, bytes | None]) -> None:
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, "Residual Fitness")
    _draw_map(pdf, mapa, max_w=560.0, max_h=400.0, x_anchor=24.0, y_anchor=70.0)
    px = 610.0
    pw = _PAGE_W - px - 36.0
    pdf.set_fill_color(*_BRANCO)
    pdf.set_draw_color(225, 225, 228)
    pdf.rect(px, 70.0, pw, 230.0, style="DF")
    pdf.set_fill_color(*ULTRA_MAGENTA)
    pdf.rect(px, 70.0, pw, 6.0, style="F")
    pdf.set_text_color(*ULTRA_MAGENTA)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(px + 14, 86.0)
    pdf.cell(pw - 28, 16, _ascii("MERCADO DISPONIVEL"))
    pdf.set_text_color(*ULTRA_MAGENTA)
    pdf.set_font("Helvetica", "B", 34)
    pdf.set_xy(px + 14, 116.0)
    pdf.cell(pw - 28, 36, _ascii(f"{_format_number(result.get('mercado_disponivel_pessoas'), 0)}"))
    pdf.set_text_color(45, 45, 45)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_xy(px + 14, 158.0)
    pdf.cell(pw - 28, 16, _ascii("alunos elegiveis sem academia"))
    yy = 186.0
    for rotulo, valor in (
        ("Hab. totais", _format_number(result.get("pop_total_municipio"), 0)),
        ("Renda per capita", "R$ " + _format_number(result.get("renda_per_capita_media"), 2)),
        ("Penetracao fitness", _format_number(result.get("penetracao_fitness_media"), 1, "%")),
    ):
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "", 12)
        pdf.set_xy(px + 14, yy)
        pdf.cell((pw - 28) * 0.6, 16, _ascii(rotulo))
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_xy(px + 14 + (pw - 28) * 0.6, yy)
        pdf.cell((pw - 28) * 0.4, 16, _ascii(valor), align="R")
        yy += 24
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_xy(px + 14, yy + 6)
    pdf.multi_cell(pw - 28, 11, _ascii("Pop. elegivel - alunos com academia cadastrada (camada residual)."))
    _draw_footer(pdf, versao=result.get("versao_contrato"))


_ZONA_TEXTOS = {
    "Ancora central": "Hexagonos centrais / posicionamento principal.",
    "Flancos laterais": "Captura dos hexagonos residuais e consolidacao.",
    "Cerco": "Bairros de alta renda / hexagonos mais afastados.",
}


def _dominio_page(pdf: _UltraPDF, result: dict[str, Any], mapa: bytes | None,
                  assets: dict[str, bytes | None]) -> None:
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, "Expansao de Dominio")
    _draw_map(pdf, mapa, max_w=560.0, max_h=400.0, x_anchor=24.0, y_anchor=70.0)
    px = 610.0
    pw = _PAGE_W - px - 36.0
    pdf.set_text_color(*ULTRA_TURQUESA)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_xy(px, 76.0)
    pdf.cell(pw, 18, _ascii("ESTRATEGIA"))
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(px, 96.0)
    pdf.multi_cell(pw, 13, _ascii("Sugestao de posicionamento para cercar e dominar a regiao."))

    zonas = result.get("zonas") or []
    yy = 128.0
    if not zonas:
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_xy(px, yy)
        pdf.multi_cell(pw, 14, _ascii(
            "Zonas de dominio nao disponiveis para este municipio. "
            "Rode gerar_plano_expansao_dominio.py para habilitar."
        ))
    else:
        # D7: ordem 1 Ancora central / 2 Flancos laterais / 3 Cerco.
        for zona in zonas:
            rotulo = str(zona.get("rotulo", f"Zona {zona.get('zona_n', '')}"))
            pdf.set_text_color(*ULTRA_MAGENTA)
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_xy(px, yy)
            pdf.cell(pw, 16, _ascii(f"{zona.get('zona_n')} {rotulo}"))
            yy += 18
            pdf.set_text_color(45, 45, 45)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_xy(px, yy)
            texto = _ZONA_TEXTOS.get(rotulo, "Movimento de dominio da zona.")
            pdf.multi_cell(pw, 13, _ascii(f"{texto} ({zona.get('n_hex')} hexes)"))
            yy = pdf.get_y() + 8
    pdf.set_xy(36, _PAGE_H - 36)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.cell(_PAGE_W - 72, 12, _ascii("Motor de Expansao Ultra - IBGE + OSM"))
    _draw_footer(pdf, versao=result.get("versao_contrato"))


def _bairros_page(pdf: _UltraPDF, result: dict[str, Any], assets: dict[str, bytes | None]) -> None:
    """D9: Pagina 6 SIMPLIFICADA (por zona/cluster + nota; sem NM_BAIRRO)."""
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, "Bairros por Zona")
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_xy(36, 70.0)
    pdf.multi_cell(
        _PAGE_W - 72, 14,
        _ascii(
            "Bairros indisponiveis na base atual; listagem por zona/hexes de dominio. "
            "A malha geo IBGE 2022 materializada nao inclui NM_BAIRRO."
        ),
    )
    zonas = result.get("zonas") or []
    yy = 120.0
    if not zonas:
        pdf.set_xy(36, yy)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(45, 45, 45)
        pdf.multi_cell(_PAGE_W - 72, 14, _ascii("Sem zonas de dominio disponiveis para este municipio."))
    else:
        for zona in zonas:
            rotulo = str(zona.get("rotulo", f"Zona {zona.get('zona_n', '')}"))
            pdf.set_text_color(*ULTRA_TURQUESA)
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_xy(36, yy)
            pdf.cell(_PAGE_W - 72, 16, _ascii(f"Zona {zona.get('zona_n')} - {rotulo}"))
            yy += 20
            pdf.set_text_color(45, 45, 45)
            pdf.set_font("Helvetica", "", 11)
            pdf.set_xy(52, yy)
            tese = str(zona.get("tese_dominio") or "n/d")
            pdf.multi_cell(
                _PAGE_W - 104, 14,
                _ascii(f"Cluster {zona.get('cluster_id')} - {zona.get('n_hex')} hexes - tese: {tese}"),
            )
            yy = pdf.get_y() + 10
    pdf.set_xy(36, _PAGE_H - 36)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.cell(_PAGE_W - 72, 12, _ascii("Motor de Expansao Ultra - IBGE + OSM"))
    _draw_footer(pdf, versao=result.get("versao_contrato"))


def _sintese_page(pdf: _UltraPDF, result: dict[str, Any], assets: dict[str, bytes | None]) -> None:
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, "Sintese - Diagnostico & Recomendacao")
    cards = [
        (
            ULTRA_MAGENTA,
            _format_number(result.get("penetracao_fitness_media"), 1, "% de penetracao"),
            "Mercado com Oportunidade: penetracao fitness atual baixa, grande espaco para crescimento.",
        ),
        (
            ULTRA_TURQUESA,
            f"{_format_number(result.get('residual_total_alunos'), 0)} alunos",
            "Residual Significativo: elegiveis sem academia regular, concentrados nas bordas/periferia.",
        ),
        (
            ULTRA_LARANJA,
            f"{_format_number(result.get('n_zonas'), 0)} zonas de atuacao",
            "Movimento Recomendado: posicionamento periferico, cercar o nucleo pelos flancos antes da concorrencia.",
        ),
    ]
    margin_x = 36.0
    gap = 18.0
    card_w = (_PAGE_W - 2 * margin_x - 2 * gap) / 3.0
    card_h = 340.0
    top = 90.0
    for idx, (accent, valor, texto) in enumerate(cards):
        x = margin_x + idx * (card_w + gap)
        pdf.set_fill_color(*_BRANCO)
        pdf.set_draw_color(225, 225, 228)
        pdf.rect(x, top, card_w, card_h, style="DF")
        pdf.set_fill_color(*accent)
        pdf.rect(x, top, card_w, 8.0, style="F")
        pdf.set_text_color(*accent)
        pdf.set_font("Helvetica", "B", 22)
        pdf.set_xy(x + 16, top + 40)
        pdf.multi_cell(card_w - 32, 26, _ascii(valor))
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "", 12)
        pdf.set_xy(x + 16, top + 130)
        pdf.multi_cell(card_w - 32, 16, _ascii(texto))
    pdf.set_xy(36, _PAGE_H - 36)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.cell(_PAGE_W - 72, 12, _ascii("Estrategia e Growth - Ultra Academia - Motor de Expansao - 2026"))
    _draw_footer(pdf, versao=result.get("versao_contrato"))


def _espaco_academias_page(pdf: _UltraPDF, result: dict[str, Any], assets: dict[str, bytes | None]) -> None:
    """Pagina 8 — big numbers + breakdown de concorrentes por rede (D8) + carimbo de versao."""
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, "Espaco e academias")
    big = [
        (ULTRA_TURQUESA, _format_number(result.get("n_ultra"), 0), "Unidades Ultra mapeadas"),
        (ULTRA_MAGENTA, _format_number(result.get("n_concorrentes"), 0), "Unidades concorrentes mapeadas"),
        (ULTRA_LARANJA, _format_number(result.get("espaco_para_academias"), 0), "Espaco total p/ novas academias"),
    ]
    margin_x = 36.0
    gap = 18.0
    card_w = (_PAGE_W - 2 * margin_x - 2 * gap) / 3.0
    top = 80.0
    for idx, (accent, valor, label) in enumerate(big):
        x = margin_x + idx * (card_w + gap)
        pdf.set_fill_color(*_BRANCO)
        pdf.set_draw_color(225, 225, 228)
        pdf.rect(x, top, card_w, 150.0, style="DF")
        pdf.set_fill_color(*accent)
        pdf.rect(x, top, card_w, 6.0, style="F")
        pdf.set_text_color(*accent)
        pdf.set_font("Helvetica", "B", 40)
        pdf.set_xy(x + 16, top + 38)
        pdf.cell(card_w - 32, 44, _ascii(valor))
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_xy(x + 16, top + 104)
        pdf.multi_cell(card_w - 32, 14, _ascii(label))

    # Breakdown de concorrentes por rede (D8: so redes realmente mapeadas).
    por_rede = result.get("concorrentes_por_rede") or {}
    pdf.set_text_color(*ULTRA_MAGENTA)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_xy(margin_x, 250.0)
    pdf.cell(_PAGE_W - 72, 16, _ascii("Concorrentes por rede"))
    yy = 276.0
    if not por_rede:
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_xy(margin_x, yy)
        pdf.cell(_PAGE_W - 72, 14, _ascii("Nenhuma rede concorrente mapeada no municipio."))
    else:
        col_w = (_PAGE_W - 2 * margin_x) / 3.0
        for idx, (rede, cnt) in enumerate(sorted(por_rede.items(), key=lambda kv: kv[1], reverse=True)):
            col = idx % 3
            x = margin_x + col * col_w
            if col == 0 and idx > 0:
                yy += 22
            if yy > _PAGE_H - 70:
                break
            pdf.set_fill_color(*ULTRA_MAGENTA)
            pdf.ellipse(x, yy + 3, 8, 8, style="F")
            pdf.set_text_color(45, 45, 45)
            pdf.set_font("Helvetica", "", 11)
            pdf.set_xy(x + 14, yy)
            pdf.cell(col_w - 18, 14, _ascii(f"{cnt} {rede}"))

    pdf.set_xy(36, _PAGE_H - 48)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.multi_cell(
        _PAGE_W - 72, 11,
        _ascii(
            "Metodo: contagem de pins dentro do territorio (H3 res 7) - "
            "Espaco = soma dos hexagonos amarelos / 2.500. "
            f"Versao: {result.get('versao_contrato')}"
        ),
    )


def gerar_pdf_relatorio_municipal(
    municipio_result: dict[str, Any],
    mapas: dict[str, bytes] | None = None,
    *,
    ultra_dir: Path | str | None = None,
    solicitante: str | None = None,
    versao: str | None = None,
) -> bytes:
    """Gera o PDF do Relatorio Municipal (8 paginas, 16:9, fpdf2, offline-safe).

    `mapas` = dict `{"resumo","score","residual","dominio"}` (camadas PNG); ausente -> paginas
    com "Mapa indisponivel". `ultra_dir` aponta os assets de branding (fallback gracioso para
    cor solida). `solicitante` carimba a marca d'agua em todas as 8 paginas (anti-PII). `versao`
    sobrescreve o carimbo de versao do rodape. READ-ONLY sobre o M1.
    """
    assets = _load_branding_assets(ultra_dir)
    mapas = mapas or {}
    if versao:
        municipio_result = {**municipio_result, "versao_contrato": versao}

    pdf = _UltraPDF()
    _cover_page(pdf, municipio_result, assets)
    _resumo_page(pdf, municipio_result, mapas.get("resumo"), assets)
    _score_page(pdf, municipio_result, mapas.get("score"), assets)
    _residual_page(pdf, municipio_result, mapas.get("residual"), assets)
    _dominio_page(pdf, municipio_result, mapas.get("dominio"), assets)
    _bairros_page(pdf, municipio_result, assets)
    _sintese_page(pdf, municipio_result, assets)
    _espaco_academias_page(pdf, municipio_result, assets)

    wm_text = _watermark_text(solicitante)
    for page_number in range(1, pdf.pages_count + 1):
        pdf.page = page_number
        rgb = _WATERMARK_RGB_COVER if page_number == 1 else _WATERMARK_RGB
        _draw_watermark(pdf, wm_text, rgb=rgb)

    return bytes(pdf.output())


def gerar_payloads_download_relatorio_municipal(
    municipio_result: dict[str, Any],
    mapas: dict[str, bytes] | None = None,
    *,
    filename_prefix: str | None = None,
    ultra_dir: Path | str | None = None,
    solicitante: str | None = None,
    versao: str | None = None,
) -> RelatorioMunicipalDownloadPayloads:
    uf = _slug(municipio_result.get("uf", ""))
    muni = _slug(municipio_result.get("nome_municipio", "municipio"))
    prefix = filename_prefix or f"relatorio_municipal_{uf}_{muni}".strip("_")
    pdf_bytes = gerar_pdf_relatorio_municipal(
        municipio_result, mapas, ultra_dir=ultra_dir, solicitante=solicitante, versao=versao
    )
    return RelatorioMunicipalDownloadPayloads(
        pdf_bytes=pdf_bytes,
        pdf_filename=f"{prefix}.pdf",
    )


def render_download_relatorio_municipal(
    st_module: Any,
    municipio_result: dict[str, Any],
    mapas: dict[str, bytes] | None = None,
    *,
    filename_prefix: str | None = None,
    ultra_dir: Path | str | None = None,
    solicitante: str | None = None,
    versao: str | None = None,
) -> RelatorioMunicipalDownloadPayloads:
    """Renderiza o botao de download Streamlit e retorna os mesmos bytes (testavel)."""
    payloads = gerar_payloads_download_relatorio_municipal(
        municipio_result, mapas, filename_prefix=filename_prefix,
        ultra_dir=ultra_dir, solicitante=solicitante, versao=versao,
    )
    st_module.download_button(
        "Baixar PDF do Relatorio Municipal",
        data=payloads.pdf_bytes,
        file_name=payloads.pdf_filename,
        mime="application/pdf",
    )
    return payloads
