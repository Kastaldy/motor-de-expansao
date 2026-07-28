from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageEnhance, ImageFont
from pyproj import Transformer
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.geometry.base import BaseGeometry

from motor_expansao.dashboard.censo_point import (
    CRS_ORIGEM_CENSO,
    RAIO_CENSITARIO_DEFAULT_KM,
    _bbox_prefilter,
    _decode_geometry,
    _local_metric_crs,
    _project_geometry,
    _transformer,
    analisar_ponto_censitario_setores,
)
from motor_expansao.dashboard.competitors import _render_square_logo_tile
from motor_expansao.dashboard.constants import (
    DENSIDADE_POP_BANDS,
    FATOR_TEMPORAL_RENDA,
    OFERTA_DISPONIVEL_ALUNOS_BANDS,
    RENDA_MEDIA_DOMICILIAR_BANDS,
    RENDA_PER_CAPITA_BANDS,
    uplift_composicao_por_setor,
)
from motor_expansao.dashboard.utils import score_band_to_color

# Cache local de tiles do basemap (DEC-004). Nunca versionado (.gitignore: data/cache/).
# Cada ponto cobre ~3 km de lado -> poucos tiles; dedup por-tile do contextily.
_BASEMAP_CACHE_DIR = Path("data/cache/basemap_tiles")

# Estilo do fundo de ruas: CartoDB **Voyager** COM labels (base CLARA estilo GeoFusion) —
# trocado da Dark Matter pelo gate BLK-CENSO-03 (Felipe, 2026-06-08) para o mapa de calor nao
# ficar escuro. No Voyager as ruas sao linhas ESCURAS finas e os nomes escuros sobre fundo
# claro — nitidos nativamente, sem nenhum realce/edge artificial. O choropleth translucido por
# cima fornece a cor; para a cor nao apagar o arruamento, recolocamos POR CIMA os PROPRIOS
# pixels ESCUROS do tile (ruas+nomes nativos — NAO e edge-detection; ver _STREET_*).
# O provedor e resolvido lazy em _fetch_basemap (ctx.providers.CartoDB.<_BASEMAP_PROVIDER_ATTR>).
# Continua sendo o FALLBACK quando o self-host abaixo nao esta configurado.
_BASEMAP_PROVIDER_ATTR = "Voyager"

# BLK-BASEMAP-02 — basemap SELF-HOST (emenda a DEC-004). Com `API_BASEMAP_TILES_URL` definida, o
# fundo de ruas vem do tileserver OpenMapTiles proprio (stack em `openmaptiles-infra/`) em vez do
# CartoDB. Em producao a API e o Streamlit alcancam o container direto pela rede `app_net`:
#   API_BASEMAP_TILES_URL=http://motor_expansao_tileserver:8080/styles/ultra-maptiler/{z}/{x}/{y}@2x.png
# INTERNO de proposito, NAO a rota publica `/tiles/`: aquela esta atras do Authelia e um fetch
# server-side nao tem cookie de sessao -> 302 p/ o login, `_fetch_basemap` engole a excecao e o
# PDF sairia SEM ruas, em silencio. Sem a env var o comportamento e' byte-identico ao anterior
# (Voyager), que e' o que CI, teste e dev local exercitam. Nao e' parametro de score: e' RENDER.
_BASEMAP_TILES_URL_ENV = "API_BASEMAP_TILES_URL"

# Atribuicao exigida pela licenca CARTO/OSM (DEC-004); aparece no rodape do PNG quando ha tile.
# INALTERADA nos dois modos: no self-host o dado e' OpenStreetMap (schema OpenMapTiles) e os
# ROTULOS continuam vindo do CARTO (`_LABELS_TILE_URL`, BLK-RELPON-07) -> os dois creditos seguem
# devidos. Desde o BLK-BASEMAP-03 o Relatorio Municipal usa o MESMO overlay, entao o credito
# duplo vale igual la (ver `relatorio_municipal._ATRIBUICAO_TILES`).
_ATRIBUICAO_TILES = "(c) OpenStreetMap, (c) CARTO"
_BASEMAP_CONTRAST = 1.15
# Zoom extra dos tiles (alem do minimo p/ cobrir a bbox) -> ruas mais nitidas/detalhadas.
_BASEMAP_ZOOM_BUMP = 1

# Overlay de ROTULOS (nomes de rua/bairro) POR CIMA do choropleth. Sem isso os nomes ficam
# SOTERRADOS sob a cor e nao da p/ identificar QUAL area tem o numero melhor/pior — a dor que o
# realce `_STREET_*` (so linhas de rua, sem texto) nao resolve. Solucao = ordem de camadas: o heat
# entra por baixo e um tileset SO-ROTULOS (transparente) e composto por cima. Fonte atual = CartoDB
# Voyager Only-Labels (keyless; MESMA familia/licenca do basemap Voyager -> atribuicao inalterada).
# Quando o OpenMapTiles self-host subir, trocar por um endpoint de rotulos do proprio tileserver.
_LABELS_TILE_URL = "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}@2x.png"
_LABELS_SUBDOMAINS = ("a", "b", "c")
# Rotulos num zoom ACIMA do basemap -> nomes maiores e legiveis sobre a cor (o zoom base ja e
# minimo-p/-cobrir + _BASEMAP_ZOOM_BUMP; aqui somamos mais 1).
_LABELS_ZOOM_BUMP = 1
# Cache local dos tiles de rotulo (emenda BLK-BASEMAP-03 a DEC-004, mitigacao (a) — a MESMA
# faz ao basemap). O `_fetch_basemap` herda o cache de graca do `ctx.set_cache_dir()`; aqui o
# fetch e' `urllib` cru, entao o cache precisa ser explicito. Diretorio SEPARADO do
# `_BASEMAP_CACHE_DIR` porque o conteudo e' outro: PNG RGBA nosso, indexado por (z,x,y), e nao o
# cache interno do contextily/requests-cache.
_LABELS_CACHE_DIR = Path("data/cache/label_tiles")
# Timeout POR TILE. Era 20 s, mas o mosaico do frame canonico do Pontual (raio 1,5 km, canvas
# 1000x760) tem 624 tiles em 8 workers: contra um CDN que faz BLACKHOLE (nao recusa, so' nao
# responde) o pior caso era 624/8 x 20 s ~= 26 min segurando a geracao do PDF. Com 8 s cai para
# ~10 min. Ainda longo — o teto de verdade e' um orcamento de tempo do mosaico inteiro, anotado
# como follow-up no BLK-BASEMAP-04 junto com o desperdicio do @2x.
_LABELS_TIMEOUT_S = 8

# Circunferencia da Terra em Web Mercator (EPSG:3857). Uma constante so, usada pelo calculo de
# zoom e pela grade de tiles do overlay — antes o mesmo literal aparecia nos dois lugares.
_EARTH_M = 2.0 * np.pi * 6378137.0

# Cores dos elementos desenhados DENTRO do mapa claro (precisam contrastar com fundo claro):
# circulo do raio (AZUL, pedido de Vini 2026-06-17) e barra de escala/labels em tinta ESCURA.
# _CIRCLE_RGBA: azul vivido, visivel sobre o fundo claro do basemap.
_CIRCLE_RGBA = (0, 102, 255, 235)
_DARK_MAP_INK = (31, 41, 55)

# Ruas/nomes do Voyager sao pixels ESCUROS sobre fundo claro. Para o choropleth nao apagar
# o arruamento, recolocamos POR CIMA do heat os PROPRIOS pixels escuros do basemap (ruas+nomes
# nativos do tile — NAO e edge-detection): luminancia < `_STREET_CEIL` vira opacidade (ganho
# `_STREET_GAIN`, teto `_STREET_CAP`). Resultado = ruas escuras nitidas sobre a cor, estilo
# GeoFusion. RENDER apenas (READ-ONLY M1).
_STREET_CEIL = 160
_STREET_GAIN = 2.2
_STREET_CAP = 210

# Margem do frame do mapa em torno do circulo de 1.5 km. O choropleth (display) cobre TODO
# o frame (setores recortados a este RETANGULO com a proporcao da area de mapa), nao so o
# circulo — estilo GeoFusion, sem letterbox. A analise (KPIs) segue circular/INTOCADA; e so RENDER.
_MAP_FRAME_MARGIN = 0.08

# BLK-RELPON-09 (S2a): lado do marcador de concorrente/Ultra em PIXELS do PNG-fonte.
# Era um balao de 40 px cuja logo util media ~17 px; agora o quadrado INTEIRO e logo
# (~26 px uteis). Ancora = CENTRO do quadrado (S2b). RENDER apenas (READ-ONLY M1).
_PIN_LOGO_PX = 30

# Web Mercator (CRS nativo dos tiles). A composicao do mapa novo acontece em 3857;
# o motor (intersecao setor x circulo 1.5 km) segue intocado em aeqd local (censo_point).
CRS_WEB_MERCATOR = "EPSG:3857"

MAPA_CENSITARIO_METRICAS = {
    "pop_estimada_intersecao": "Pop. estimada",
    "renda_per_capita_setor_2022_calibrada": "Renda per capita",
    "score_setor_2022_calibrado": "Score censitario",
    "peso_area_setor": "Peso de area",
}

# Chaves canonicas das camadas combinadas (BLK-CENSO-03-FU5): `score` e o choropleth de
# score censitario COM legenda; `renda_domiciliar` e o choropleth de renda media domiciliar
# (renda_pc x moradores x uplift SETORIAL x fator temporal); `concorrentes` e o mapa SO de pins.
# BLK-RELPON-10: `socioeconomia` e o MESMO choropleth de score censitario do `score` (mesmo
# insumo/legenda), so com titulo/raio rotulados p/ o slide-hero "Socioeconomia e Residual
# Fitness" (S1=A do gate: o score PERMANECE tambem no grid 2x2); `residual` e o choropleth de
# `oferta_efetiva_disponivel` por HEXAGONO H3 res-7 num raio de EXIBICAO de 5 km — chave
# CONDICIONAL, so presente quando `hexes_df` foi passado e ha hex desenhavel.
# BLK-RELPON-11: `entorno` e o mapa de QUADRA (so basemap Voyager + ponto central, sem
# choropleth, sem pins e sem circulo de raio) num raio de EXIBICAO de ~0,14 km. Ao contrario de
# `residual`, e INCONDICIONAL: depende so de `lat`/`lng` e cai no canvas claro offline quando
# nao ha tile, entao a chave existe SEMPRE.
CAMADAS_CENSITARIAS = (
    "densidade",
    "renda",
    "score",
    "renda_domiciliar",
    "socioeconomia",
    "residual",
    "concorrentes",
    "entorno",
)

# BLK-RELPON-10: raio de EXIBICAO do mapa de Residual Fitness por hexagono. NAO e' parametro de
# motor — nao entra em `config.py` nem no §3 do CLAUDE.md, e nao toca
# `setor_censitario_intersecao_area_1p5km`/`RAIO_CENSITARIO_DEFAULT_KM` (o motor censitario segue
# em 1,5 km, INTOCADO). Motivo do raio maior: no circulo de 1,5 km cabem so 3 a 5 hexes res-7 ->
# mosaico chapado, nao mapa de calor. READ-ONLY sobre o M1.
RAIO_RESIDUAL_DISPLAY_KM = 5.0
# Raio `k` do disco H3 (res-7) de hexes candidatos ao redor do hex central. O disco cobre no PIOR
# eixo (direcao da aresta) ~(2k+1)*apotema = (2k+1)*1,057 km; a meia-diagonal do frame de 5 km no
# caller mais largo (1280x760 -> aspect ~1,573) e ~10,07 km. k=4 daria so 9,51 km -> CANTOS VAZIOS;
# k=5 da 11,63 km e cobre com folga (91 hexes, custo irrelevante). Nao reduzir "para economizar":
# os hexes excedentes sao descartados de graca pelo clip ao frame.
_RESIDUAL_GRID_DISK_K = 5

# BLK-RELPON-11: raio de EXIBICAO do mapa de quadra "Imagem do Entorno". Constante de RENDER
# (fora de `config.py` / §3 do CLAUDE.md), como `RAIO_RESIDUAL_DISPLAY_KM`. O lado MENOR do frame
# sai em 2 * raio * 1000 * (1 + _MAP_FRAME_MARGIN) = 2 * 140 * 1,08 = 302,4 m -> dentro da janela
# util de 250-400 m medida na pesquisa de alternativas (alvo ~300 m); o lado menor e INVARIANTE em
# relacao ao canvas, entao a resolucao efetiva (~1,82 px por metro de solo) e a mesma a 1000x760 e
# a 1280x760. O motor censitario (`setor_censitario_intersecao_area_1p5km`,
# `RAIO_CENSITARIO_DEFAULT_KM`=1,5) fica INTOCADO — este raio e' so de EXIBICAO.
RAIO_ENTORNO_DISPLAY_KM = 0.14

# Textos da camada `entorno` (PNG). ASCII PURO: excecao de RENDER ao §2 do CLAUDE.md — o font
# embutido do Pillow usado no PNG nao tem glifo acentuado. Nenhuma string promete satelite,
# imagem aerea ou POI comercial: o Voyager entrega morfologia urbana (ruas/quadras/nomes).
_ENTORNO_TITULO_PNG = "Entorno - mapa de quadra"
_ENTORNO_VALOR_LINHA = "Ruas e quadras do entorno"
_ENTORNO_LEGENDA_TITULO = "Entorno imediato do ponto"
# Prefixo do rodape NO LUGAR de "Raio X km": nesta escala nao ha raio de ANALISE, e o formato
# automatico sairia "Raio 0,1 km" (enganoso vs o motor censitario de 1,5 km).
_ENTORNO_ROTULO_ESCALA = "Escala de quadra"

_SECTOR_PALETTE = [
    (232, 242, 255, 225),
    (176, 211, 245, 225),
    (111, 166, 214, 225),
    (247, 196, 97, 225),
    (214, 93, 74, 225),
]

# Alpha do choropleth (heat) sobre o basemap CLARO Voyager. Mais opaco que no fundo escuro para
# a cor de faixa ser legivel sobre o claro; as ruas escuras do Voyager sao RECOLOCADAS por cima
# depois (_STREET_*), entao o arruamento nao se perde. A legenda usa RGB solido (ignora este
# alpha), entao as faixas seguem nitidas na legenda.
_CHOROPLETH_ALPHA = 140

# Cor de fill para setor sem dado na faixa nova (cinza translucido).
_FILL_SEM_DADO = (218, 222, 229, _CHOROPLETH_ALPHA)

# BLK-RELPON-06 (D4): tamanhos de fonte do mapa. Valem para dashboard, PDF e API (UM render
# so -- nao ha parametro `escala` por caminho, ver D4 da DEC). Ancorados no pior caso do PDF:
# o PNG de 1000px entra numa celula de ~298,67pt na tira 1x3 do slide "Mapas de calor"
# (`_map_grid_cells`: usable_w=896/3) -> ratio ~0,2987 -> a legenda-corpo (32px) sai a
# ~9,6pt, acima do alvo de 9-10pt de legibilidade no PDF.
_FS_TITULO = 44
_FS_VALOR_RAIO = 38
_FS_LEGENDA_TITULO = 34
_FS_LEGENDA_CORPO = 32
# Subtitulo da legenda ("Renda per capita (R$/pessoa)" etc.): fonte MENOR que o titulo --
# o subtitulo mais longo transbordava do canvas a `_FS_LEGENDA_TITULO` (34px -> ~448px,
# > budget de ~320px da coluna, `_LEGEND_COL_W - 10`). Texto secundario, como o rodape.
_FS_LEGENDA_SUBTITULO = 22
# Legenda de pins ("Ponto central"/"Pins: Ultra e concorrentes"): fonte MENOR que o corpo
# das faixas -- a essas duas linhas cabe em `_LEGEND_COL_W`, mas a frase e mais longa que
# o rotulo de faixa mais longo e transbordava do canvas a `_FS_LEGENDA_CORPO` (32px ->
# ~362px, > budget de ~252px da coluna). Texto secundario/anotacao, como rodape/escala.
_FS_LEGENDA_CAPTION = 20
_FS_BODY = 26  # mensagem "Sem setores intersectados no raio"
_FS_FOOTER = 22  # rodape (atribuicao CARTO)
_FS_ESCALA = 24  # label da barra de escala

# Coluna da legenda: alargada de 252 -> 330px porque o rotulo mais longo das faixas
# ("R$ 2.001-3.500", 14 chars) ocupa ~246px a 32px de fonte (ver teste de legibilidade).
_LEGEND_COL_W = 330
_MAP_TOP = 132  # era 92: abre espaco para titulo (44px) + linha de dado (38px)
_VALOR_Y = 78  # era 51: 22 (topo do titulo) + 44 (titulo) + 12 de respiro


def _with_choropleth_alpha(rgba: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Aplica o alpha canonico do choropleth (mantem RGB da faixa)."""
    return (int(rgba[0]), int(rgba[1]), int(rgba[2]), _CHOROPLETH_ALPHA)


def _map_box(width: int, height: int) -> tuple[int, int, int, int]:
    """Retangulo (left, top, right, bottom) da area de mapa dentro da figura.

    BLK-RELPON-06 (D4): `_MAP_TOP` abre espaco para o titulo+linha-de-dado maiores; o `-33`
    preserva o mesmo respiro (~33px) entre a borda direita do mapa e a coluna da legenda que
    existia antes (`(width-252) - (width-285) = 33`), agora com `_LEGEND_COL_W` mais larga.
    """
    return (28, _MAP_TOP, width - (_LEGEND_COL_W + 33), height - 54)


def _map_inner_dims(width: int, height: int) -> tuple[float, float]:
    """Dimensoes uteis (inner_w, inner_h) onde o frame e desenhado (sem o padding de 12px)."""
    left, top, right, bottom = _map_box(width, height)
    return (float(right - left - 24), float(bottom - top - 24))


def _frame_box_metric(raio_km: float, width: int, height: int) -> Polygon:
    """Frame do mapa (retangulo no CRS metrico local, centrado em 0,0), como poligono.

    RETANGULO com a proporcao da area de mapa (nao quadrado), para o choropleth preencher a
    figura inteira sem letterbox. O lado MENOR = raio*(1+`_MAP_FRAME_MARGIN`) — o circulo do raio
    cabe e fica redondo, pois x/y compartilham o mesmo `scale` no render. Os poligonos (setores ou
    hexes) sao recortados a este retangulo, nao ao circulo. Geometria PURA (testavel isolada);
    extraida do corpo de `render_mapas_censitarios_combinados` no BLK-RELPON-10 SEM mudanca de
    calculo. RENDER apenas — a analise (KPIs) segue circular e INTOCADA.
    """
    base_half = raio_km * 1000.0 * (1.0 + _MAP_FRAME_MARGIN)
    inner_w, inner_h = _map_inner_dims(width, height)
    aspect = inner_w / inner_h if inner_h > 0 else 1.0
    if aspect >= 1.0:
        frame_half_x, frame_half_y = base_half * aspect, base_half
    else:
        frame_half_x, frame_half_y = base_half, base_half / aspect
    return box(-frame_half_x, -frame_half_y, frame_half_x, frame_half_y)


def _font(size: int = 12) -> ImageFont.ImageFont:
    # BLK-RELPON-06 (D3): fonte TrueType EMBUTIDA do Pillow (>=10.1), via load_default(size=).
    # Deliberadamente NAO usa TTF do sistema: `arial.ttf` so existe no Windows e a imagem de
    # producao (python:3.11-slim) nao tem fonte alguma -> o fallback load_default() SEM size
    # caia num bitmap FIXO ~10px que IGNORAVA o tamanho pedido, quebrando o texto do mapa no
    # PDF *e* no dashboard (title_font(20) e title_font(60) renderizavam IGUAL em producao).
    # Com load_default(size=N) a fonte escala de fato -> o PNG/PDF fica IDENTICO em Windows
    # e na VPS (auditavel). truetype()/arial.ttf NAO devem ser reintroduzidos.
    # truetype() devolve FreeTypeFont (nao subclasse de ImageFont nos stubs Pillow);
    # cast preserva runtime e mantem a assinatura aceita por _draw_text/_text_width.
    return cast(ImageFont.ImageFont, ImageFont.load_default(size=size))


def _iter_polygons(geom: BaseGeometry) -> Iterable[Polygon]:
    if isinstance(geom, Polygon):
        yield geom
    elif isinstance(geom, MultiPolygon):
        yield from geom.geoms
    elif hasattr(geom, "geoms"):
        for item in geom.geoms:
            yield from _iter_polygons(item)


def _metric_values(df: pd.DataFrame, metric_column: str) -> pd.Series:
    if metric_column not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    return pd.to_numeric(df[metric_column], errors="coerce")


def _color_for_value(value: float, breaks: list[float]) -> tuple[int, int, int, int]:
    if pd.isna(value):
        return (218, 222, 229, 210)
    if not breaks:
        return _SECTOR_PALETTE[2]
    idx = int(np.searchsorted(breaks, float(value), side="right"))
    idx = max(0, min(idx, len(_SECTOR_PALETTE) - 1))
    return _SECTOR_PALETTE[idx]


def _build_breaks(values: pd.Series) -> list[float]:
    valid = values.dropna()
    if valid.empty or valid.nunique() <= 1:
        return []
    quantiles = valid.quantile([0.2, 0.4, 0.6, 0.8]).to_numpy(dtype=float)
    return sorted({round(float(value), 6) for value in quantiles})


# ── Cores por faixa absoluta fixa (substitui o quartil no caminho novo) ──────────


def _color_for_bands(
    value: float,
    bands: list[tuple[float, str, tuple[int, int, int, int]]],
) -> tuple[int, int, int, int]:
    if pd.isna(value):
        return _FILL_SEM_DADO
    val = float(value)
    for upper, _label, color in bands:
        if val <= upper:
            return color
    return bands[-1][2]


def _color_for_densidade(value: float) -> tuple[int, int, int, int]:
    return _with_choropleth_alpha(_color_for_bands(value, DENSIDADE_POP_BANDS))


def _color_for_renda(value: float) -> tuple[int, int, int, int]:
    return _with_choropleth_alpha(_color_for_bands(value, RENDA_PER_CAPITA_BANDS))


def _color_for_score(value: float) -> tuple[int, int, int, int]:
    rgba = score_band_to_color(value, alpha=_CHOROPLETH_ALPHA)
    return (int(rgba[0]), int(rgba[1]), int(rgba[2]), int(rgba[3]))


def _format_value(value: float) -> str:
    if pd.isna(value):
        return "-"
    abs_value = abs(float(value))
    if abs_value >= 1000:
        return f"{value:,.0f}".replace(",", ".")
    if abs_value >= 10:
        return f"{value:.1f}"
    return f"{value:.2f}"


def _metric_label(metric_column: str) -> str:
    return MAPA_CENSITARIO_METRICAS.get(metric_column, metric_column)


# ── Faixa superior "<variavel> no raio" por camada (BLK-RELPON-05, faixa REVERTIDA p/ o
# raio pelo BLK-RELPON-06/D1) ──────────────────────────────────────────────────────────
# Formata o valor AGREGADO do raio de 1.5 km (densidade sobre area valida, renda e score
# medios ponderados) -- NAO mais o valor bruto do setor que contem o ponto (BLK-RELPON-05
# original). "n/d" para None/NaN (sem setores intersectados). Texto so com pontuacao ASCII
# por consistencia com o restante do relatorio.


def _format_valor_ponto_renda(value: float | None) -> str:
    """Renda per capita media do raio: moeda, separador de milhar '.', sem centavos."""
    if value is None or pd.isna(value):
        return "n/d"
    return f"R$ {float(value):,.0f}".replace(",", ".")


def _format_valor_ponto_densidade(value: float | None) -> str:
    """Densidade populacional do raio (sobre area valida): inteiro, unidade ASCII 'hab/km2'."""
    if value is None or pd.isna(value):
        return "n/d"
    return f"{float(value):,.0f}".replace(",", ".") + " hab/km2"


def _format_valor_ponto_score(value: float | None) -> str:
    """Score censitario medio do raio: inteiro 0-100."""
    if value is None or pd.isna(value):
        return "n/d"
    return f"{float(value):.0f}"


def _format_valor_residual(value: float | None) -> str:
    """Residual fitness disponivel (alunos): inteiro com separador de milhar '.'; "n/d" se ausente."""
    if value is None or pd.isna(value):
        return "n/d"
    return f"{float(value):,.0f}".replace(",", ".")


def _legenda_valor_ponto(rotulo: str, texto: str) -> str:
    """Monta o texto da faixa superior do mapa: "<Rotulo> no raio: <texto>" (BLK-RELPON-06/D1)."""
    return f"{rotulo} no raio: {texto}"


def _legenda_valor_hex(rotulo: str, texto: str) -> str:
    """Faixa superior da camada de HEXAGONO: "<Rotulo> no hexagono: <texto>" (BLK-RELPON-10).

    Irmao de `_legenda_valor_ponto`, com rotulo de ESCALA diferente: o valor exibido e' o do hex
    central (o MESMO ja mostrado nos Big Numbers via `lookup_hex_by_coord`), NAO a soma do disco —
    somar seria agregado NOVO (analise), e este bloco e' 100% exibicao. ASCII puro ("hexagono"
    sem acento): o font do PNG nao tem glifo acentuado.
    """
    return f"{rotulo} no hexagono: {texto}"


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
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return int(right - left)


def _polygon_to_pixels(
    polygon: Polygon,
    project: Callable[[float, float], tuple[float, float]],
) -> list[tuple[int, int]]:
    coords = [project(x, y) for x, y in polygon.exterior.coords]
    return [(int(round(x)), int(round(y))) for x, y in coords]


def _draw_scale_bar(
    draw: ImageDraw.ImageDraw,
    map_box: tuple[int, int, int, int],
    meters_per_px: float,
) -> None:
    left, _, _, bottom = map_box
    candidates = [1000, 750, 500, 250, 100]
    scale_m = next((value for value in candidates if value / meters_per_px <= 140), 100)
    px_len = max(20, int(round(scale_m / meters_per_px)))
    x0 = left + 18
    y0 = bottom - 28
    # Barra de escala em tinta ESCURA (dentro do mapa claro Voyager).
    # D8=B (BLK-EST-02): linha mais grossa (width 5) e box branco semi-translucido atras do
    # label, para legibilidade sobre qualquer cor do choropleth.
    draw.line([(x0, y0), (x0 + px_len, y0)], fill=_DARK_MAP_INK, width=5)
    draw.line([(x0, y0 - 5), (x0, y0 + 5)], fill=_DARK_MAP_INK, width=2)
    draw.line([(x0 + px_len, y0 - 5), (x0 + px_len, y0 + 5)], fill=_DARK_MAP_INK, width=2)
    label = f"{scale_m // 1000} km" if scale_m >= 1000 else f"{scale_m} m"
    # BLK-RELPON-06 (D4): box branco atras do label acompanha a fonte maior (_FS_ESCALA).
    draw.rectangle([x0 - 2, y0 + 5, x0 + px_len, y0 + 34], fill=(255, 255, 255, 180))
    _draw_text(draw, (x0, y0 + 8), label, font=_font(_FS_ESCALA), fill=_DARK_MAP_INK)


def _paste_logo_pin(
    image: Image.Image,
    px: int,
    py: int,
    key: str,
    *,
    size: int = _PIN_LOGO_PX,
) -> None:
    """Cola a LOGO QUADRADA (`competitors._render_square_logo_tile`) no mapa.

    BLK-RELPON-09: saiu o balao teardrop com a logo mascarada em circulo; entra a
    propria logo num quadrado de `size` px, com borda branca e sombra leve. Ancora o
    CENTRO do quadrado no ponto (px, py) -- o marcador nao tem ponta, e ancorar a base
    deslocaria a leitura ~15 px (~88 m no frame de 1,5 km). O ponto exato da analise
    segue marcado pelo pin vermelho central (`_draw_center_pin`, INALTERADO). Reusa a
    mascara alpha do tile RGBA. Logo real quando ha PNG no _ICON_CACHE; sigla no fallback.
    """
    tile = cast(Image.Image, _render_square_logo_tile(key, size))
    image.paste(tile, (int(px) - size // 2, int(py) - size // 2), tile)


def _draw_legend_camada(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    titulo: str,
    entries: list[tuple[str, tuple[int, int, int, int]]],
    *,
    mostrar_legenda_pins: bool = True,
) -> None:
    """Legenda por camada: faixas fixas (label + amostra de cor) + pins de referencia.

    BLK-RELPON-06 (D4): fontes/layout ampliados (`_FS_LEGENDA_TITULO`/`_FS_LEGENDA_CORPO`,
    linhas/swatch maiores) para o texto ficar legivel no PDF (celula ~299pt na tira 1x3).

    BLK-RELPON-10-FU1 (gate de Vinicius, 2026-07-22): `mostrar_legenda_pins=False` omite a
    linha "Pins: Ultra e concorrentes" -- usado SO pela camada `residual`, que deixou de
    desenhar pins (a 5 km a densidade de logos cobria o choropleth). O default `True` mantem
    as 5 camadas pre-existentes byte-a-byte identicas, INCLUSIVE quando o raio nao tem nenhum
    concorrente: a legenda NAO pode reagir ao `pins` estar vazio, senao a byte-identidade
    provada pelo QA quebraria nesse cenario. "Ponto central" permanece nas duas: o pin do
    centro continua sendo desenhado no mapa.
    """
    title_font = _font(_FS_LEGENDA_TITULO)
    body_font = _font(_FS_LEGENDA_CORPO)
    caption_font = _font(_FS_LEGENDA_CAPTION)
    subtitle_font = _font(_FS_LEGENDA_SUBTITULO)
    _draw_text(draw, (x, y), "Legenda", font=title_font)
    # Subtitulo com fonte dedicada MENOR que o corpo (ver `_FS_LEGENDA_SUBTITULO`): o mais
    # longo ("Renda per capita (R$/pessoa)") transbordaria do canvas a `_FS_LEGENDA_CORPO`.
    _draw_text(draw, (x, y + 44), titulo, font=subtitle_font)

    base_y = y + 96
    row_h = 48
    for idx, (label, color) in enumerate(entries):
        yy = base_y + idx * row_h
        # D7=C subset seguro (BLK-EST-02): amostras arredondadas (radius 5).
        draw.rounded_rectangle(
            [x, yy, x + 56, yy + 38], radius=5, fill=color[:3], outline=(148, 163, 184)
        )
        _draw_text(draw, (x + 68, yy + 6), label, font=body_font)

    # D7=C subset seguro: linha separadora fina antes do bloco de pins.
    sep_y = base_y + len(entries) * row_h + 8
    draw.line([(x, sep_y), (x + 210, sep_y)], fill=(210, 214, 222), width=1)

    yy = base_y + len(entries) * row_h + 24
    _draw_center_pin(draw, x + 12, yy + 20, scale=0.8)
    # Fonte MENOR (`_FS_LEGENDA_CAPTION`) que o corpo das faixas: a frase "Pins: Ultra e
    # concorrentes" e mais longa que o rotulo de faixa mais longo e transbordaria do
    # canvas a `_FS_LEGENDA_CORPO` (ver constante acima).
    _draw_text(draw, (x + 68, yy), "Ponto central", font=caption_font)
    if mostrar_legenda_pins:
        _draw_text(draw, (x + 68, yy + 30), "Pins: Ultra e concorrentes", font=caption_font)


def _draw_center_pin(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    *,
    scale: float = 1.0,
) -> None:
    """Pin VERMELHO de mapa com a PONTA ancorada no ponto central (cx, cy)."""
    red = (220, 38, 38)
    white = (255, 255, 255)
    r = max(4, int(round(9 * scale)))
    head_cy = cy - int(round(22 * scale))
    # corpo: triangulo da base da cabeca ate a ponta no ponto
    draw.polygon([(cx, cy), (cx - r, head_cy), (cx + r, head_cy)], fill=red)
    # cabeca do pin
    draw.ellipse([cx - r, head_cy - r, cx + r, head_cy + r], fill=red, outline=white, width=2)
    # furo central branco
    hole = max(2, int(round(3 * scale)))
    draw.ellipse([cx - hole, head_cy - hole, cx + hole, head_cy + hole], fill=white)


def _decode_intersections(
    lat: float,
    lng: float,
    setores_df: pd.DataFrame,
    raio_km: float,
    clip_box_metric: BaseGeometry,
) -> tuple[list[dict[str, object]], BaseGeometry]:
    """Decodifica os setores que cobrem o FRAME do mapa (quadrado em torno do circulo),
    recortados ao `clip_box_metric` — NAO ao circulo — p/ o choropleth cobrir o frame todo
    (estilo GeoFusion). Os valores (densidade/renda/score) vem da PROPRIA linha do setor em
    `setores_df`, entao setores fora do circulo tambem saem coloridos. Display-only; a analise
    (KPIs por `analisar_ponto_censitario_setores`) segue circular e INTOCADA.
    """
    metric_crs = _local_metric_crs(lat, lng)
    to_metric = _transformer(CRS_ORIGEM_CENSO, metric_crs)
    to_wgs84 = _transformer(metric_crs, CRS_ORIGEM_CENSO)
    circle_metric = Point(0, 0).buffer(raio_km * 1000.0, quad_segs=96)
    clip_wgs84 = _project_geometry(clip_box_metric, to_wgs84)

    if setores_df is None or setores_df.empty:
        return [], circle_metric

    geometry_col = "geometry_wkb" if "geometry_wkb" in setores_df.columns else "geometry"
    if geometry_col not in setores_df.columns:
        return [], circle_metric

    candidates = _bbox_prefilter(setores_df, clip_wgs84)
    records: list[dict[str, object]] = []
    for _, row in candidates.iterrows():
        geom_wgs84 = _decode_geometry(row[geometry_col])
        if geom_wgs84 is None:
            continue
        clipped = _project_geometry(geom_wgs84, to_metric).intersection(clip_box_metric)
        if clipped.is_empty:
            continue
        records.append(
            {
                "cod_setor": str(row.get("cod_setor", "")),
                "geometry_metric": clipped,
                "densidade_pop_setor_hab_km2": row.get("densidade_pop_setor_hab_km2"),
                "renda_per_capita_setor_2022_calibrada": row.get("renda_per_capita_setor_2022_calibrada"),
                "renda_per_capita_setor_2022": row.get("renda_per_capita_setor_2022"),
                "score_setor_2022_calibrado": row.get("score_setor_2022_calibrado"),
                # Insumos da renda media domiciliar por setor (uplift SETORIAL, formula do #124).
                "avg_moradores_domicilio_setor_2022": row.get("avg_moradores_domicilio_setor_2022"),
                "renda_responsavel_media_setor_2022": row.get("renda_responsavel_media_setor_2022"),
                "uf": row.get("uf"),
                "cod_municipio": row.get("cod_municipio"),
            }
        )
    return records, circle_metric


def _to_mercator(geom: BaseGeometry, lat: float, lng: float) -> BaseGeometry:
    """Reprojeta uma geometria do aeqd local (CRS do motor) -> EPSG:3857, SO para render."""
    to_3857 = _transformer(_local_metric_crs(lat, lng), CRS_WEB_MERCATOR)
    return _project_geometry(geom, to_3857)


def _point_to_mercator(x_local: float, y_local: float, lat: float, lng: float) -> tuple[float, float]:
    to_3857 = _transformer(_local_metric_crs(lat, lng), CRS_WEB_MERCATOR)
    return to_3857.transform(x_local, y_local)


def _project_points(
    points_df: pd.DataFrame,
    lat: float,
    lng: float,
) -> list[tuple[float, float, str]]:
    """Reprojeta pontos (lat/lng) -> aeqd local. Devolve (x, y, key) para o pin.

    `key` e a rede (concorrente) ou "__ultra__"; resolvido a partir da coluna `rede`.
    """
    if points_df is None or points_df.empty or not {"lat", "lng"}.issubset(points_df.columns):
        return []
    to_metric = _transformer(CRS_ORIGEM_CENSO, _local_metric_crs(lat, lng))
    coords: list[tuple[float, float, str]] = []
    for _, row in points_df.iterrows():
        point_lat = pd.to_numeric(row.get("lat"), errors="coerce")
        point_lng = pd.to_numeric(row.get("lng"), errors="coerce")
        if pd.isna(point_lat) or pd.isna(point_lng):
            continue
        x, y = to_metric.transform(float(point_lng), float(point_lat))
        rede = row.get("rede")
        key = str(rede) if rede is not None and not pd.isna(rede) and str(rede).strip() else ""
        coords.append((x, y, key))
    return coords


def _zoom_for_bounds(minx: float, maxx: float, target_px: int) -> int:
    """Escolhe o menor zoom cujo grid de tiles (256 px) cubra a bbox 3857 com >= target_px.

    A resolucao 3857 no zoom z e (2*pi*R)/(256*2^z) m/px; queremos span/res >= target_px.
    """
    span_m = max(maxx - minx, 1.0)
    for zoom in range(0, 20):
        res = _EARTH_M / (256.0 * (2**zoom))
        if span_m / res >= target_px:
            return max(0, min(zoom, 19))
    return 19


def _basemap_source(ctx: object) -> object:
    """Fonte de tiles do fundo de ruas: self-host quando configurado, CartoDB Voyager senao.

    O `contextily` aceita tanto um provider do `xyzservices` quanto um TEMPLATE de URL cru com
    `{z}/{x}/{y}` — e por isso a env var pode entrar direto como `source`, sem provider novo.

    Sem `API_BASEMAP_TILES_URL` devolve exatamente o que devolvia antes (`ctx.providers.CartoDB.
    Voyager`), entao CI/teste/dev local seguem no caminho conhecido e o fallback offline da
    DEC-004 (sem rede -> None -> canvas claro) vale IGUAL nos dois modos.

    Nota de zoom: o `brazil.mbtiles` e' z0-14, mas o relatorio pede ate z19. Nao e' problema —
    o tileserver-gl RASTERIZA o vetor no zoom pedido (overzoom de vetor, geometria continua
    nitida), ao contrario de um raster overzoomado, que borra.
    """
    import os

    url = os.environ.get(_BASEMAP_TILES_URL_ENV)
    if url:
        return url
    return getattr(ctx.providers.CartoDB, _BASEMAP_PROVIDER_ATTR)  # type: ignore[attr-defined]


def _fetch_basemap(
    bounds_3857: tuple[float, float, float, float],
    width: int,
    *,
    zoom_bump: int | None = None,
) -> tuple[object, tuple[float, float, float, float]] | None:
    """Busca tiles de basemap claro (CartoDB Voyager No-Labels) via contextily.

    Import LAZY sob try/except: se o extra `[basemap]` nao estiver instalado OU o fetch
    falhar (sem internet/timeout), devolve None e o chamador cai no fallback offline.
    Aplica realce de contraste `_BASEMAP_CONTRAST` p/ as ruas aparecerem sob o choropleth.
    Cache local em data/cache/basemap_tiles/. Retorna (img_array, extent_3857) ou None.

    BLK-RELPON-11: `zoom_bump` sobrescreve o `_BASEMAP_ZOOM_BUMP` GLOBAL apenas nesta chamada
    (`None` = usa a constante, que continua `1` e serve os frames de 1,5 km e 5 km). Honestidade
    sobre o que ele faz HOJE no frame de quadra: e' um NO-OP, porque ha DOIS clampes em 19
    (`_zoom_for_bounds` ja devolve no maximo 19 e o `min(19, ...)` abaixo repete o teto) -> tanto
    `bump=1` quanto `bump=0` resolvem z19 nesse bbox — por isso o valor que a camada de quadra
    passa NAO e' `0`, e sim `-1`: no gate visual de 2026-07-22 Vinicius escolheu **z18**, porque
    o render tem ~1,82 px/m contra 3,65 px/m do tile z19, reduz o tile ~2x e joga o rotulo de rua
    para 3,0-3,3 pt (variante recente) / 2,6-2,9 pt (CLASSICA) no PDF; em z18 os mesmos rotulos
    dobram, com campo de visao identico. Ver `_render_camada_entorno`.
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
        bump = _BASEMAP_ZOOM_BUMP if zoom_bump is None else int(zoom_bump)
        # `max(0, ...)` e' guarda barata contra bump negativo em bbox continental; nao altera
        # nada hoje (com o bump global o resultado e' sempre >= 1).
        zoom = max(0, min(19, _zoom_for_bounds(minx, maxx, width) + bump))
        source = _basemap_source(ctx)
        img, extent = ctx.bounds2img(minx, miny, maxx, maxy, zoom=zoom, source=source, ll=False)
        if _BASEMAP_CONTRAST != 1.0:
            base = Image.fromarray(np.asarray(img)).convert("RGB")
            base = ImageEnhance.Contrast(base).enhance(_BASEMAP_CONTRAST)
            arr = np.asarray(base)
            alpha = np.full((arr.shape[0], arr.shape[1], 1), 255, dtype=np.uint8)
            img = np.concatenate([arr, alpha], axis=2)
        return img, extent
    except Exception:
        return None


def _labels_grid(
    bounds_3857: tuple[float, float, float, float], width: int
) -> tuple[int, int, int, int, int, float]:
    """Zoom + faixa de tiles `(zoom, tx0, tx1, ty0, ty1, tile_m)` que cobre `bounds_3857`.

    Extraido de `_fetch_labels` (emenda BLK-BASEMAP-03 a DEC-004) p/ ser testado SEM rede: e' a
    unica aritmetica nao trivial do overlay e antes so era exercitada por monkeypatch da funcao
    inteira, ou seja, nunca. Convencao XYZ: `x` cresce para LESTE a partir de -180 e `y` cresce
    para o SUL a partir do topo — por isso `ty0` sai de `maxy` e `ty1` de `miny` (invertidos em
    relacao a `x`). O teto de zoom 19 e' o mesmo do `_fetch_basemap`.
    """
    minx, miny, maxx, maxy = bounds_3857
    zoom = min(19, _zoom_for_bounds(minx, maxx, width) + _BASEMAP_ZOOM_BUMP + _LABELS_ZOOM_BUMP)
    tile_m = _EARTH_M / (2**zoom)  # tamanho do tile em metros (3857)
    tx0 = int((minx + _EARTH_M / 2) / tile_m)
    tx1 = int((maxx + _EARTH_M / 2) / tile_m)
    ty0 = int((_EARTH_M / 2 - maxy) / tile_m)
    ty1 = int((_EARTH_M / 2 - miny) / tile_m)
    return zoom, tx0, tx1, ty0, ty1, tile_m


def _labels_extent(
    tx0: int, tx1: int, ty0: int, ty1: int, tile_m: float
) -> tuple[float, float, float, float]:
    """Extent 3857 do mosaico como `(minx, maxx, miny, maxy)` — convencao do `ctx.bounds2img`.

    E' o extent dos TILES INTEIROS, sempre >= o bbox pedido (a grade e' discreta): quem compoe
    reprojeta por este extent, nao pelo bbox, senao os nomes saem deslocados.
    """
    return (
        tx0 * tile_m - _EARTH_M / 2,
        (tx1 + 1) * tile_m - _EARTH_M / 2,
        _EARTH_M / 2 - (ty1 + 1) * tile_m,
        _EARTH_M / 2 - ty0 * tile_m,
    )


def _labels_tile(zoom: int, tx: int, ty: int) -> Image.Image:
    """Um tile de rotulo, servido do DISCO quando ja baixado (DEC-004, mitigacao (a)).

    E' o cache que a mitigacao (a) da DEC-004 exige do basemap e que o overlay nao tinha: sem
    ele cada PDF rebaixava o mosaico inteiro do CARTO. O `_fetch_basemap` ganha isso de graca
    via `ctx.set_cache_dir()`; como aqui o fetch e' `urllib` cru, o cache e' explicito.

    Escrita por arquivo temporario + `replace()` (atomico) de proposito: sao 8 threads aqui e
    ate 3 relatorios concorrentes no piloto, entao um leitor poderia abrir um PNG truncado.
    Falha de ESCRITA e' engolida — cache e' otimizacao e nao pode derrubar o render; falha de
    REDE sobe e o chamador trata o tile como faltando (o mosaico segue sem aquele pedaco).
    """
    import os
    import urllib.request

    destino = _LABELS_CACHE_DIR / f"{zoom}_{tx}_{ty}.png"
    if destino.is_file():
        try:
            with Image.open(destino) as cached:
                return cached.convert("RGBA")
        except Exception:
            pass  # cache corrompido/truncado -> rebaixa como se nao existisse

    url = _LABELS_TILE_URL.format(s=_LABELS_SUBDOMAINS[(tx + ty) % 3], z=zoom, x=tx, y=ty)
    req = urllib.request.Request(url, headers={"User-Agent": "motor-expansao/censo-labels"})
    with urllib.request.urlopen(req, timeout=_LABELS_TIMEOUT_S) as resp:  # noqa: S310 (URL https)
        raw = resp.read()
    tile = Image.open(BytesIO(raw)).convert("RGBA")
    try:
        _LABELS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        parcial = destino.with_name(f"{destino.name}.{os.getpid()}.tmp")
        parcial.write_bytes(raw)
        parcial.replace(destino)
    except Exception:
        pass
    return tile


def _fetch_labels(
    bounds_3857: tuple[float, float, float, float],
    width: int,
) -> tuple[Image.Image, tuple[float, float, float, float]] | None:
    """Mosaico SO-de-rotulos (PNG transparente) p/ compor os nomes POR CIMA do choropleth.

    Espelha o contrato de `_fetch_basemap` (retorna imagem + extent 3857, topo = norte), mas a
    imagem e RGBA transparente (so texto/halo) e vem de `_LABELS_TILE_URL`. Rede + best-effort:
    QUALQUER falha (sem internet, timeout, tile faltando) -> None, e o mapa segue SEM nomes,
    identico ao comportamento anterior (degradacao graciosa, igual ao basemap offline).

    Consumido pelos DOIS relatorios: Pontual (`_render_camada`) e Municipal (BLK-BASEMAP-03) —
    este ultimo porque o estilo self-host `ultra-maptiler` nao tem `transportation_name` e sem o
    overlay o mapa municipal sairia com as ruas desenhadas e SEM nome. Tile a tile o fetch passa
    por `_labels_tile`, que cacheia em disco (emenda BLK-BASEMAP-03 a DEC-004, mitigacao (a)); a
    grade e o extent saem de `_labels_grid`/`_labels_extent`, testaveis sem rede.

    NENHUM tile entrou -> `None`, nao um canvas transparente. Ate o BLK-BASEMAP-03 o
    `except Exception: continue` por tile engolia TUDO e a funcao devolvia mosaico vazio +
    extent mesmo com 100% dos tiles falhando: o docstring prometia `None`, o codigo entregava
    outra coisa e o chamador compunha uma camada inteiramente transparente achando que tinha
    rotulos. Mesmo criterio que a DEC-018 fixou para a foto de satelite ("conta os tiles que
    entraram e devolve None se for zero").
    """
    import concurrent.futures as cf

    try:
        zoom, tx0, tx1, ty0, ty1, tile_m = _labels_grid(bounds_3857, width)
        px = 512  # tiles @2x

        canvas = Image.new("RGBA", ((tx1 - tx0 + 1) * px, (ty1 - ty0 + 1) * px), (0, 0, 0, 0))
        coords = [(tx, ty) for ty in range(ty0, ty1 + 1) for tx in range(tx0, tx1 + 1)]
        entraram = 0
        with cf.ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                (tx, ty): executor.submit(_labels_tile, zoom, tx, ty) for tx, ty in coords
            }
            for (tx, ty), future in futures.items():
                try:
                    tile = future.result()
                    if tile.size != (px, px):
                        tile = tile.resize((px, px), Image.Resampling.LANCZOS)
                    canvas.alpha_composite(tile, ((tx - tx0) * px, (ty - ty0) * px))
                    entraram += 1
                except Exception:
                    continue  # rotulo faltando nao e problema (base ja desenhada)
        if not entraram:
            return None  # rede toda fora -> contrato de None, nao mosaico transparente
        return canvas, _labels_extent(tx0, tx1, ty0, ty1, tile_m)
    except Exception:
        return None


def _render_camada(
    *,
    titulo: str,
    legenda_titulo: str,
    legenda_entries: list[tuple[str, tuple[int, int, int, int]]],
    color_fn: Callable[[float], tuple[int, int, int, int]],
    source_values: pd.Series,
    sector_records_3857: list[tuple[BaseGeometry, int]],
    circle_3857: BaseGeometry | None,
    center_3857: tuple[float, float],
    pins: list[tuple[float, float, str]],
    ultra_pins: list[tuple[float, float, str]],
    basemap: tuple[object, tuple[float, float, float, float]] | None,
    bounds: tuple[float, float, float, float],
    lat: float,
    lng: float,
    raio_km: float,
    n_setores: int,
    width: int,
    height: int,
    pins_only: bool = False,
    street_ceil: int | None = None,
    street_gain: float | None = None,
    street_cap: int | None = None,
    valor_ponto: str | None = None,
    rotulo_escala: str | None = None,
    mostrar_legenda_pins: bool = True,
    labels: tuple[Image.Image, tuple[float, float, float, float]] | None = None,
) -> bytes:
    """Desenha UMA camada (mesmos bbox/projecao/basemap/pins; varia fill + legenda).

    Quando `pins_only=True` (camada Concorrentes): pula o choropleth de faixas E o overlay
    de ruas de pixel; mantem basemap + circulo + ponto central + pins de concorrentes/Ultra +
    escala + footer + legenda so de pins. BLK-CENSO-03.

    BLK-RELPON-11 (2 parametros DEFAULT-PRESERVING — com os defaults, as 7 camadas anteriores
    saem byte-a-byte identicas):
    - `circle_3857=None` omite o circulo do raio. Usado SO pela camada `entorno`, cujo frame
      de ~300 m nao tem raio de ANALISE nenhum (um circulo ali seria lido como se a analise
      censitaria fosse de 140 m, contradizendo o motor de 1,5 km).
    - `rotulo_escala` substitui o prefixo "Raio X km" do rodape. `None` mantem o formato atual.

    `valor_ponto` (BLK-RELPON-05, faixa REVERTIDA p/ os agregados do raio pelo
    BLK-RELPON-06/D1): texto opcional da faixa superior ("<Variavel> no raio: <valor>"),
    desenhado numa 2a linha entre o titulo e o `map_box`. Default `None` preserva o render
    IDENTICO desta funcao para qualquer chamador que nao passe o parametro.

    BLK-RELPON-06 (D4): fontes ampliadas na BASE (`_FS_*`) -- vale para dashboard, PDF e
    API com UM UNICO render (sem parametro de escala por-caminho).
    """
    # Base RGBA TRANSPARENTE-branco: as margens (fora do map_box) ficam transparentes -> no
    # PDF o fundo da pagina aparece (sem retangulo branco). O choropleth/pins sao clipados ao
    # map_box (sobre basemap/fill OPACO), entao as cores nao mudam; e, achatado sobre branco
    # (convert("RGB")), fica identico ao RGB antigo -> compat com os testes de cor das faixas.
    image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image, "RGBA")
    title_font = _font(_FS_TITULO)
    body_font = _font(_FS_BODY)
    small_font = _font(_FS_FOOTER)

    _draw_text(draw, (28, 22), titulo, font=title_font)
    if valor_ponto is not None:
        # BLK-RELPON-06 (D4): `_VALOR_Y`/`_FS_VALOR_RAIO`/`_MAP_TOP` tem que fechar:
        # _VALOR_Y (78) + _FS_VALOR_RAIO (38) + 16 de respiro = _MAP_TOP (132). Mudar um
        # tamanho no gate visual exige recalcular os outros dois junto.
        _draw_text(draw, (28, _VALOR_Y), valor_ponto, font=_font(_FS_VALOR_RAIO), fill=_DARK_MAP_INK)

    map_box = _map_box(width, height)
    legend_x = width - _LEGEND_COL_W
    left, top, right, bottom = map_box

    minx, miny, maxx, maxy = bounds
    span_x = max(maxx - minx, 1.0)
    span_y = max(maxy - miny, 1.0)
    inner_w = right - left - 24
    inner_h = bottom - top - 24
    scale = min(inner_w / span_x, inner_h / span_y)
    offset_x = left + 12 + (inner_w - span_x * scale) / 2
    offset_y = top + 12 + (inner_h - span_y * scale) / 2

    def project(x: float, y: float) -> tuple[float, float]:
        px = offset_x + (x - minx) * scale
        py = offset_y + (maxy - y) * scale
        return px, py

    # Fundo: basemap Voyager (3857) quando disponivel; senao canvas claro (fallback offline).
    # As ruas/nomes vem NATIVOS do tile (linhas escuras finas sobre fundo claro) — sem realce
    # artificial: base clara estilo GeoFusion.
    drew_basemap = False
    basemap_patch: Image.Image | None = None  # ruas/nomes claros p/ recolocar por cima da cor
    if basemap is not None:
        try:
            img_array, extent = basemap
            bm = Image.fromarray(np.asarray(img_array)).convert("RGB")
            ex_minx, ex_maxx, ex_miny, ex_maxy = extent
            # mapeia o extent dos tiles (3857) para pixels e cola
            tx0, ty0 = project(ex_minx, ex_maxy)  # canto superior-esquerdo
            tx1, ty1 = project(ex_maxx, ex_miny)  # canto inferior-direito
            box_w = max(1, int(round(tx1 - tx0)))
            box_h = max(1, int(round(ty1 - ty0)))
            bm = bm.resize((box_w, box_h), Image.Resampling.LANCZOS)
            crop = Image.new("RGB", (width, height), (245, 245, 245))
            crop.paste(bm, (int(round(tx0)), int(round(ty0))))
            # recorta a area do map_box e cola so ela (mantem moldura)
            patch = crop.crop((left, top, right, bottom))
            image.paste(patch, (left, top))
            draw.rounded_rectangle(map_box, radius=6, outline=(71, 85, 105))
            basemap_patch = patch
            drew_basemap = True
        except Exception:
            drew_basemap = False
            basemap_patch = None
    if not drew_basemap:
        # Fallback offline: canvas claro (sem ruas), coerente com o tema claro do mapa.
        draw.rounded_rectangle(map_box, radius=6, fill=(245, 245, 245), outline=(71, 85, 105))

    # choropleth por faixa fixa (alpha translucido -> ruas ESCURAS do basemap claro aparecem por
    # cima depois). SEM borda nos setores: transicao suave entre faixas (estilo GeoFusion).
    # Pulado quando pins_only=True (camada Concorrentes = so basemap + pins).
    if not pins_only:
        for geom_3857, idx in sector_records_3857:
            color = color_fn(source_values.iloc[idx])
            for polygon in _iter_polygons(geom_3857):
                points = _polygon_to_pixels(polygon, project)
                if len(points) >= 3:
                    draw.polygon(points, fill=color)
                    for interior in polygon.interiors:
                        hole = [
                            (int(round(px)), int(round(py)))
                            for px, py in (project(a, b) for a, b in interior.coords)
                        ]
                        if len(hole) >= 3:
                            draw.polygon(hole, fill=(200, 200, 200, 80))

    # Ruas/nomes do Voyager (pixels ESCUROS) recolocados POR CIMA da cor, com os PROPRIOS
    # pixels do tile (nao edge-detection): luminancia baixa -> opacidade -> arruamento nitido
    # sobre o choropleth, estilo GeoFusion. Antes do circulo/pins/escala (que ficam no topo).
    # Pulado quando pins_only=True (sem choropleth -> nao precisa recolocar ruas). RENDER apenas.
    if basemap_patch is not None and not pins_only:
        ceil = _STREET_CEIL if street_ceil is None else street_ceil
        gain = _STREET_GAIN if street_gain is None else street_gain
        cap = _STREET_CAP if street_cap is None else street_cap
        lum = basemap_patch.convert("L")
        street_mask = lum.point(
            lambda v: 0 if v >= ceil else min(cap, int((ceil - v) * gain))
        )
        region = image.crop((left, top, right, bottom))
        region.paste(basemap_patch, (0, 0), street_mask)
        image.paste(region, (left, top))

    # Rotulos (NOMES de rua/bairro) POR CIMA do choropleth -> da p/ identificar a area. O realce
    # `_STREET_*` acima recupera so as LINHAS de rua; aqui entram os TEXTOS, crus, de um tileset
    # so-rotulos transparente (buscado 1x em `render_mapas_censitarios_combinados`). Alinhado ao
    # extent dos tiles como o basemap (project()), recortado ao `map_box`. Pulado em pins_only
    # (mapa so-pins mantem os rotulos nativos do basemap, sem choropleth por cima). RENDER apenas.
    if labels is not None and not pins_only:
        labels_img, (lb_minx, lb_maxx, lb_miny, lb_maxy) = labels
        lx0, ly0 = project(lb_minx, lb_maxy)  # canto sup-esq do mosaico de rotulos
        lx1, ly1 = project(lb_maxx, lb_miny)  # canto inf-dir
        lw, lh = max(1, int(round(lx1 - lx0))), max(1, int(round(ly1 - ly0)))
        placed = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        placed.paste(labels_img.resize((lw, lh), Image.Resampling.LANCZOS),
                     (int(round(lx0)), int(round(ly0))))
        patch = placed.crop((left, top, right, bottom))
        region = image.crop((left, top, right, bottom))
        region.alpha_composite(patch)
        image.paste(region, (left, top))

    # Circulo do raio: OPCIONAL desde o BLK-RELPON-11 (a camada `entorno`, mapa de quadra, nao
    # tem raio). O overlay de rotulos acima entra ANTES dele de proposito -- o circulo e' desenho
    # do motor, nao do basemap, e nao pode ser coberto por rotulo de rua.
    if circle_3857 is not None:
        circle_points = [
            (int(round(px)), int(round(py)))
            for px, py in (project(x, y) for x, y in circle_3857.exterior.coords)
        ]
        if len(circle_points) >= 3:
            # Circulo do raio em AZUL (pedido de Vini 2026-06-17), visivel sobre o fundo claro.
            draw.line(circle_points + [circle_points[0]], fill=_CIRCLE_RGBA, width=3)

    cx, cy = project(*center_3857)
    _draw_center_pin(draw, int(round(cx)), int(round(cy)))

    for x_local, y_local, key in pins:
        mx, my = _point_to_mercator(x_local, y_local, lat, lng)
        px, py = project(mx, my)
        _paste_logo_pin(image, int(round(px)), int(round(py)), key or "")
    for x_local, y_local, _key in ultra_pins:
        mx, my = _point_to_mercator(x_local, y_local, lat, lng)
        px, py = project(mx, my)
        _paste_logo_pin(image, int(round(px)), int(round(py)), "__ultra__")

    if not sector_records_3857 and not pins_only:
        message = "Sem setores intersectados no raio"
        msg_w = _text_width(draw, message, body_font)
        _draw_text(
            draw,
            (int((left + right - msg_w) / 2), int((top + bottom) / 2)),
            message,
            font=body_font,
            fill=_DARK_MAP_INK,
        )

    meters_per_px = 1 / scale
    _draw_scale_bar(draw, map_box, meters_per_px)
    _draw_legend_camada(
        draw, legend_x, 96, legenda_titulo, legenda_entries,
        mostrar_legenda_pins=mostrar_legenda_pins,
    )

    # D8=B (BLK-EST-02): rodape enxuto. Atribuicao CARTO (exigida pela licenca DEC-004)
    # permanece quando ha basemap; some no fallback offline (sem tile, sem atribuicao).
    # BLK-RELPON-10 (DT-5): o raio deixa de ser hardcode e deriva de `raio_km` (parametro que ja
    # existia e nao era usado no corpo) -> com raio_km=1.5 a string sai IDENTICA ("Raio 1,5 km")
    # e as 4 camadas censitarias ficam byte-a-byte iguais; a camada de residual sai "Raio 5,0 km".
    # BLK-RELPON-11: `rotulo_escala` (default None) troca SO o prefixo do rodape -- com None a
    # string sai EXATAMENTE como antes; a camada `entorno` passa "Escala de quadra" porque
    # "Raio 0,1 km" (o que `:.1f` produziria a 0,14 km) seria ativamente enganoso.
    raio_txt = f"{float(raio_km):.1f}".replace(".", ",")
    prefixo = f"Raio {raio_txt} km" if rotulo_escala is None else rotulo_escala
    if drew_basemap:
        footer = f"{prefixo} - EPSG:3857 - {_ATRIBUICAO_TILES}"
    else:
        footer = f"{prefixo} - EPSG:3857 - fundo de ruas offline"
    _draw_text(draw, (28, height - 34), footer, font=small_font, fill=(71, 85, 105))

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _bands_legend_entries(
    bands: list[tuple[float, str, tuple[int, int, int, int]]],
) -> list[tuple[str, tuple[int, int, int, int]]]:
    return [(label, color) for _upper, label, color in bands]


def _score_legend_entries() -> list[tuple[str, tuple[int, int, int, int]]]:
    entries: list[tuple[str, tuple[int, int, int, int]]] = []
    for band in range(0, 100, 20):
        rgba = score_band_to_color(float(band) + 5.0, alpha=150)
        entries.append((f"{band}-{band + 20}", (int(rgba[0]), int(rgba[1]), int(rgba[2]), int(rgba[3]))))
    return entries


# ── BLK-RELPON-10: camada de Residual Fitness por HEXAGONO H3 (raio de EXIBICAO 5 km) ──────
# READ-ONLY sobre o M1: `oferta_efetiva_disponivel` e' apenas LIDA do dataframe recebido; nada
# aqui recalcula score/flag/carteira/plano nem escreve artefato. O motor censitario (raio 1,5 km,
# `setor_censitario_intersecao_area_1p5km`) fica INTOCADO — esta camada e' um recorte visual
# paralelo, com escala PROPRIA e rotulada como tal.


def _hex_polygons_3857(
    lat: float,
    lng: float,
    hexes_df: pd.DataFrame | None,
    frame_3857: BaseGeometry,
    to_3857: Transformer,
    *,
    value_col: str = "oferta_efetiva_disponivel",
) -> tuple[list[tuple[BaseGeometry, int]], pd.Series]:
    """Poligonos dos hexes H3 res-7 do disco em torno do ponto, recortados ao frame (EPSG:3857).

    Cadeia: `h3.latlng_to_cell(lat,lng,7)` -> `h3.grid_disk(centro, _RESIDUAL_GRID_DISK_K)` ->
    filtro por `hex_id` no `hexes_df` -> `h3.cell_to_boundary` -> projecao -> clip ao frame.
    O `7` e' `H3_RESOLUTION` do M1, apenas LIDO. Import de `h3` LAZY (mesmo padrao de `data.py`).

    Devolve `(records, values)` no formato que `_render_camada` consome: `records` = lista de
    `(geometria_3857, idx)` e `values` = Serie posicional com o valor de `value_col`
    (default `oferta_efetiva_disponivel`; a socioeconomia passa `score_setor_2022_calibrado`)
    (`idx` indexa `values.iloc[]`). Lista vazia quando nao ha hex utilizavel — inclusive quando
    `value_col` nao esta no `hexes_df` (a socioeconomia SEM a coluna cai no fallback textual).

    Nota de projecao: `h3.cell_to_boundary` emite WGS84 e usamos `CRS_ORIGEM_CENSO`
    (EPSG:4674/SIRGAS 2000) como origem — igual ao que `_project_points` ja faz com lat/lng de
    concorrentes. A diferenca 4674<->4326 e' sub-metrica, irrelevante num frame de ~17 km, e
    preserva UMA unica convencao "lat/lng -> 3857" no modulo.
    """
    empty: tuple[list[tuple[BaseGeometry, int]], pd.Series] = ([], pd.Series(dtype="float64"))
    if hexes_df is None or hexes_df.empty or "hex_id" not in hexes_df.columns:
        return empty
    if value_col not in hexes_df.columns:
        return empty
    try:
        import h3  # lazy: nunca no topo deste modulo
    except ImportError:
        return empty
    try:
        centro = h3.latlng_to_cell(float(lat), float(lng), 7)  # 7 = H3_RESOLUTION (M1), LIDO
        celulas = set(h3.grid_disk(centro, _RESIDUAL_GRID_DISK_K))
    except Exception:
        return empty
    if not celulas:
        return empty

    sub = hexes_df.loc[hexes_df["hex_id"].astype(str).isin(celulas)]
    if sub.empty:
        return empty

    records: list[tuple[BaseGeometry, int]] = []
    values: list[float] = []
    for _, row in sub.iterrows():
        try:
            boundary = h3.cell_to_boundary(str(row["hex_id"]))
        except Exception:
            continue
        try:
            coords = [to_3857.transform(float(pt_lng), float(pt_lat)) for pt_lat, pt_lng in boundary]
            if len(coords) < 3:
                continue
            clipped = Polygon(coords).intersection(frame_3857)
        except Exception:
            continue
        if clipped.is_empty:
            continue
        records.append((clipped, len(values)))
        values.append(float(pd.to_numeric(row.get(value_col), errors="coerce")))

    if not records:
        return empty
    return records, pd.Series(values, dtype="float64")


def _residual_hex_central(
    lat: float,
    lng: float,
    hexes_df: pd.DataFrame | None,
    *,
    value_col: str = "oferta_efetiva_disponivel",
) -> float | None:
    """Valor de `value_col` do hex H3 res-7 que CONTEM o ponto — o MESMO valor exibido nos
    Big Numbers (mesma chave `hex_id`, mesma resolucao 7 de `lookup_hex_by_coord`). Deliberadamente
    NAO soma o disco: somar seria um agregado NOVO (analise), e este bloco e' so exibicao. Default
    `oferta_efetiva_disponivel` (residual); a socioeconomia passa `score_setor_2022_calibrado`.
    `None` quando a coluna/linha nao existe ou o valor e' NaN -> a faixa mostra "n/d".
    """
    if hexes_df is None or hexes_df.empty:
        return None
    if not {"hex_id", value_col}.issubset(hexes_df.columns):
        return None
    try:
        import h3  # lazy

        cell = h3.latlng_to_cell(float(lat), float(lng), 7)  # 7 = H3_RESOLUTION (M1), LIDO
    except Exception:
        return None
    linha = hexes_df.loc[hexes_df["hex_id"].astype(str) == str(cell)]
    if linha.empty:
        return None
    valor = pd.to_numeric(linha[value_col].iloc[0], errors="coerce")
    if pd.isna(valor):
        return None
    return float(valor)


def _render_camada_residual_hex(
    lat: float,
    lng: float,
    hexes_df: pd.DataFrame | None,
    *,
    basemap: bool,
    width: int,
    height: int,
    street_ceil: int | None = None,
    street_gain: float | None = None,
    street_cap: int | None = None,
    choropleth_alpha: int | None = None,
    value_col: str = "oferta_efetiva_disponivel",
    titulo: str = "Residual Fitness - raio 5 km",
    legenda_titulo: str = "Residual disponivel (alunos)",
    legenda_entries: list[tuple[str, tuple[int, int, int, int]]] | None = None,
    color_fn: Callable[[float], tuple[int, int, int, int]] | None = None,
    valor_central_rotulo: str = "Residual",
    valor_central_fmt: Callable[[float | None], str] = _format_valor_residual,
) -> bytes | None:
    """Choropleth de `value_col` por hexagono H3 no raio de EXIBICAO de 5 km.

    Monta o PROPRIO frame/circulo/basemap (bounds diferentes das camadas de 1,5 km) e delega o
    desenho a `_render_camada`, cujo `sector_records_3857` ja e' generico (poligonos 3857 coloridos
    por `color_fn`) — nao precisa saber que sao hexes. Pins de concorrentes/Ultra sao filtrados
    pelo bbox do frame de 5 km (NAO reusa `result["concorrentes_raio"]`, que e' do recorte de
    1,5 km e daria a impressao falsa de que so existem aqueles). Devolve `None` quando nao ha hex
    desenhavel -> a chave `residual` some do dict e o slide cai no fallback textual do PDF.

    Generalizado no BLK-RELPON-13 (DEFAULT-PRESERVING): TODOS os parametros keyword-only novos
    (`value_col`/`titulo`/`legenda_titulo`/`legenda_entries`/`color_fn`/`valor_central_*`) tem
    default que reproduz o Residual Fitness byte-a-byte. A socioeconomia do slide-hero reusa este
    caminho passando `value_col="score_setor_2022_calibrado"` + titulo/legenda/`color_fn` do score
    — mesmo frame/basemap/clip de 5 km, sem duplicar a logica.
    """
    # Saida rapida: sem dataframe de hexes nao ha camada (nem transformer, nem fetch de tiles).
    if hexes_df is None or hexes_df.empty:
        return None

    frame_metric = _frame_box_metric(RAIO_RESIDUAL_DISPLAY_KM, width, height)
    circle_metric = Point(0, 0).buffer(RAIO_RESIDUAL_DISPLAY_KM * 1000.0, quad_segs=96)

    metric_crs = _local_metric_crs(lat, lng)
    to_3857_local = _transformer(metric_crs, CRS_WEB_MERCATOR)
    # (o transformer para WGS84 saiu no BLK-RELPON-10-FU1: so servia ao recorte de pins.)
    # Transformer lat/lng -> 3857 criado UMA vez e reusado por todos os hexes (`_transformer`
    # NAO e' cacheado; recria-lo por hex custaria caro). Espelha o `_to_3857` compartilhado da
    # orquestradora (Fix 1 BLK-PERF-01a).
    to_3857_wgs = _transformer(CRS_ORIGEM_CENSO, CRS_WEB_MERCATOR)

    frame_3857 = _project_geometry(frame_metric, to_3857_local)
    circle_3857 = _project_geometry(circle_metric, to_3857_local)
    center_3857 = to_3857_local.transform(0.0, 0.0)

    hex_records, hex_values = _hex_polygons_3857(
        lat, lng, hexes_df, frame_3857, to_3857_wgs, value_col=value_col
    )
    if not hex_records:
        return None

    # BLK-RELPON-10-FU1: esta camada NAO desenha pins (ver comentario na chamada de
    # `_render_camada` abaixo), entao o recorte de pontos por bbox do frame foi removido
    # junto com os parametros `competitors_df`/`ultra_df`.
    basemap_tiles = _fetch_basemap(frame_3857.bounds, width) if basemap else None

    eff_alpha = _CHOROPLETH_ALPHA if choropleth_alpha is None else int(choropleth_alpha)
    sem_dado = (_FILL_SEM_DADO[0], _FILL_SEM_DADO[1], _FILL_SEM_DADO[2], eff_alpha)

    def _residual_fn(value: float) -> tuple[int, int, int, int]:
        if pd.isna(value):
            return sem_dado
        r, g, b, _a = _color_for_bands(value, OFERTA_DISPONIVEL_ALUNOS_BANDS)
        return (int(r), int(g), int(b), eff_alpha)

    # DEFAULT-PRESERVING: sem override (`None`), legenda/cor sao as do Residual Fitness -> byte
    # a byte identico ao de hoje. A socioeconomia passa as suas (score) e nao toca este caminho.
    _legenda_entries_eff = (
        legenda_entries
        if legenda_entries is not None
        else _bands_legend_entries(OFERTA_DISPONIVEL_ALUNOS_BANDS)
    )
    _color_fn_eff = color_fn if color_fn is not None else _residual_fn

    return _render_camada(
        titulo=titulo,
        legenda_titulo=legenda_titulo,
        legenda_entries=_legenda_entries_eff,
        color_fn=_color_fn_eff,
        source_values=hex_values,
        sector_records_3857=hex_records,
        circle_3857=circle_3857,
        center_3857=center_3857,
        # BLK-RELPON-10-FU1 (gate de Vinicius, 2026-07-22): SEM pins nesta camada. A area a
        # 5 km e ~11x a de 1,5 km (r^2), entao a densidade de logos cobria o choropleth --
        # medido na amostra da Av. Paulista, onde os marcadores tapavam quase todos os
        # hexagonos. Quem esta instalado ja e mostrado na pagina "Concorrentes"; este mapa
        # existe para responder ONDE HA ESPACO, e a cor e o dado dele.
        pins=[],
        ultra_pins=[],
        mostrar_legenda_pins=False,
        basemap=basemap_tiles,
        bounds=frame_3857.bounds,
        lat=lat,
        lng=lng,
        raio_km=RAIO_RESIDUAL_DISPLAY_KM,
        n_setores=len(hex_records),
        width=width,
        height=height,
        street_ceil=street_ceil,
        street_gain=street_gain,
        street_cap=street_cap,
        valor_ponto=_legenda_valor_hex(
            valor_central_rotulo,
            valor_central_fmt(
                _residual_hex_central(lat, lng, hexes_df, value_col=value_col)
            ),
        ),
    )


# ── BLK-RELPON-11: camada "Imagem do Entorno" — mapa de QUADRA (raio de EXIBICAO ~0,14 km) ──
# Caminho A1 do gate de Vinicius (2026-07-22): mesmo provedor CartoDB Voyager das DEC-004/011,
# SEM DEC nova e SEM provedor novo. Nao ha dado tematico nesta camada: e' so o basemap de ruas
# + o ponto central, para o leitor ver a morfologia fisica (quadras, vias, nomes de rua) em que
# o ponto esta inserido. READ-ONLY sobre o M1; o motor censitario (1,5 km) fica INTOCADO.


def _render_camada_entorno(
    lat: float,
    lng: float,
    *,
    basemap: bool,
    width: int,
    height: int,
) -> bytes:
    """Mapa de quadra do entorno imediato do ponto (so basemap + ponto central).

    Monta o PROPRIO frame (raio de EXIBICAO `RAIO_ENTORNO_DISPLAY_KM`, lado curto ~302 m) e
    delega o desenho a `_render_camada` com `pins_only=True` — que pula o choropleth, o overlay
    de ruas (desnecessario: sem cor por cima, as ruas do Voyager ja sao nativas) e a mensagem
    "Sem setores intersectados no raio".

    Decisoes de produto (Planner, 2026-07-22):
    - **SEM pins de concorrentes/Ultra**: a ~1,82 px por metro de solo, um pin de
      `_PIN_LOGO_PX`=30 px cobre ~16,5 m de solo — uma edificacao inteira; apagaria o objeto da
      pagina. Mesmo argumento (e mesmo gatekeeper) do BLK-RELPON-10-FU1. "Quem esta instalado"
      e' papel da pagina Concorrentes. O pin central vermelho CONTINUA: e' o sujeito da pagina.
    - **SEM circulo de raio** (`circle_3857=None`) e rodape "Escala de quadra" (D4): nao ha raio
      de ANALISE nesta escala. A referencia de distancia continua na barra de escala.

    Devolve SEMPRE `bytes` (nunca `None`): sem tile/rede/contextily o proprio `_fetch_basemap`
    devolve `None` e `_render_camada` cai no canvas claro — por isso a chave e' INCONDICIONAL.
    """
    frame_metric = _frame_box_metric(RAIO_ENTORNO_DISPLAY_KM, width, height)
    to_3857_local = _transformer(_local_metric_crs(lat, lng), CRS_WEB_MERCATOR)
    frame_3857 = _project_geometry(frame_metric, to_3857_local)
    center_3857 = to_3857_local.transform(0.0, 0.0)

    # `zoom_bump=-1` -> z18 (GATE VISUAL de Vinicius, 2026-07-22). O frame resolveria z19 pelos
    # dois clampes em 19, mas o render tem ~1,82 px/m contra 3,65 px/m do tile z19: o tile e'
    # reduzido ~2x e o rotulo de rua sai a 3,0-3,3 pt (variante recente) / 2,6-2,9 pt (CLASSICA,
    # que e' a que o dashboard e o bot entregam) — numero de porta ilegivel, que era justamente
    # o que motivava o z19. Em z18 os mesmos rotulos dobram (6,0-6,6 / 5,2-5,7 pt) com campo de
    # visao IDENTICO. E' o mesmo mecanismo que matou o z20 na pesquisa; aqui ele ja morde no z19.
    basemap_tiles = _fetch_basemap(frame_3857.bounds, width, zoom_bump=-1) if basemap else None

    return _render_camada(
        titulo=_ENTORNO_TITULO_PNG,
        legenda_titulo=_ENTORNO_LEGENDA_TITULO,
        legenda_entries=[],  # sem faixas de choropleth (camada so-basemap)
        color_fn=_color_for_score,  # irrelevante quando pins_only=True
        source_values=pd.Series(dtype="float64"),  # idem
        sector_records_3857=[],
        circle_3857=None,
        center_3857=center_3857,
        pins=[],
        ultra_pins=[],
        mostrar_legenda_pins=False,
        basemap=basemap_tiles,
        bounds=frame_3857.bounds,
        lat=lat,
        lng=lng,
        raio_km=RAIO_ENTORNO_DISPLAY_KM,
        n_setores=0,
        width=width,
        height=height,
        pins_only=True,
        valor_ponto=_ENTORNO_VALOR_LINHA,
        rotulo_escala=_ENTORNO_ROTULO_ESCALA,
    )


def render_mapas_censitarios_combinados(
    lat: float,
    lng: float,
    setores_df: pd.DataFrame,
    *,
    raio_km: float = RAIO_CENSITARIO_DEFAULT_KM,
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
    width: int = 1000,
    height: int = 760,
    basemap: bool = True,
    logos_dir: Path | None = None,
    ultra_logo_dir: Path | None = None,
    street_ceil: int | None = None,
    street_gain: float | None = None,
    street_cap: int | None = None,
    choropleth_alpha: int | None = None,
    hexes_df: pd.DataFrame | None = None,
    labels_overlay: bool = True,
) -> dict[str, bytes]:
    """Gera as camadas do Relatorio Pontual Censitario numa unica chamada.

    Retorna `{"densidade": png, "renda": png, "score": png, "renda_domiciliar": png,
    "concorrentes": png, "entorno": png}` e, CONDICIONALMENTE, `"socioeconomia"` e `"residual"`
    (ambas dependem de `hexes_df` desenhavel — ver abaixo).
    `renda_domiciliar` e o choropleth de renda media domiciliar (renda_pc x moradores x uplift
    SETORIAL x fator temporal); `concorrentes` e o mapa SO de pins (basemap + pins, sem
    choropleth). As camadas de choropleth de SETOR e a de pins compartilham basemap, bbox,
    projecao (EPSG:3857) e pins; variam so o fill dos setores + a legenda/titulo.

    BLK-RELPON-10 (slide-hero "Socioeconomia e Residual Fitness"),
    revisto no BLK-RELPON-13 (gate visual de Vinicius, 2026-07-23):
    - `socioeconomia` e o choropleth de `score_setor_2022_calibrado` por HEXAGONO H3 res-7 num
      raio de EXIBICAO de 5 km (disco `grid_disk` k=5), com a MESMA metrica/paleta do `score`
      do grid 2x2 — o que a distingue e' a geometria/escala (hex a 5 km, nao setor a 1,5 km).
      Reusa o caminho de `_render_camada_residual_hex` (mesmo frame/basemap/clip do residual).
      CONDICIONAL como o `residual`: so entra no dict quando `hexes_df` traz `hex_id` +
      `score_setor_2022_calibrado` e ha >= 1 hex desenhavel; senao a chave e' AUSENTE e o PDF
      cai no fallback textual. O `score` PERMANECE no grid 2x2 (S1=A do gate de Vinicius).
    - `residual` e o choropleth de `oferta_efetiva_disponivel` (ALUNOS) por hexagono H3 res-7 num
      raio de EXIBICAO de 5 km (`RAIO_RESIDUAL_DISPLAY_KM`), com escala PROPRIA rotulada no titulo
      e no rodape do PNG. So entra no dict quando `hexes_df` foi passado E ha >= 1 hex desenhavel;
      caso contrario a chave e' AUSENTE e o PDF cai no fallback textual (offline-safe).
      `hexes_df` precisa ter `hex_id` + `oferta_efetiva_disponivel` — no dashboard e' o proprio
      `df` da UF ja em escopo. *Limitacao conhecida e aceita:* como o `df` e' a fatia da UF
      carregada (CLAUDE.md §4), um ponto na divisa de UF tera o disco truncado; o efeito e'
      gracioso (hexes ausentes ficam sem cor, nao levantam excecao).
    READ-ONLY sobre o M1: `oferta_efetiva_disponivel` e `score_setor_2022_calibrado` sao apenas
    LIDOS; nenhum score/flag/artefato e' recalculado ou escrito.

    BLK-RELPON-11 (pagina "Imagem do Entorno"):
    - `entorno` e o mapa de QUADRA do entorno imediato: so o basemap CartoDB Voyager + o ponto
      central, num raio de EXIBICAO de `RAIO_ENTORNO_DISPLAY_KM` (~0,14 km -> lado curto ~302 m
      do frame), com `zoom_bump=-1` (z18 — gate visual, ver `_render_camada_entorno`), SEM pins
      e SEM circulo de raio. Ao contrario de `residual`,
      a chave e' INCONDICIONAL: depende so de `lat`/`lng` e cai no canvas claro quando nao ha
      tile (`basemap=False`, sem rede ou sem o extra `[basemap]`).

    READ-ONLY sobre o M1: o motor (`analisar_ponto_censitario_setores`,
    `setor_censitario_intersecao_area_1p5km`, raio 1.5 km) e INTOCADO; toda a mudanca e
    de RENDER. `basemap=False` forca o caminho offline (canvas branco sem ruas) — default
    seguro em CI/teste. `import contextily` e lazy: sem o extra `[basemap]` cai no offline.

    Ajuste fino do arruamento (todos `None` = constantes do modulo, render IDENTICO ao
    dashboard; so a API os sobrescreve): `street_ceil`/`street_gain`/`street_cap` controlam
    o resgate das ruas sobre o choropleth (luminancia abaixo de `street_ceil` -> opacidade);
    subir o `ceil` recupera as vias residenciais CINZA-CLARAS do Voyager (lum ~200) que com o
    teto baixo (160) sumiam sob a cor. `choropleth_alpha` e a opacidade do preenchimento das
    faixas — menor = ruas aparecem mais. A legenda usa RGB solido, entao nao muda com o alpha.

    BLK-RELPON-07: `labels_overlay` (default True) compoe os NOMES de rua/bairro POR CIMA do
    choropleth (tileset so-rotulos, buscado 1x por `_fetch_labels` e compartilhado pelas 4 camadas
    de choropleth). Enquanto o `_STREET_*` recupera so as LINHAS de rua, este overlay traz os
    TEXTOS -> da p/ identificar a area. Best-effort: sem basemap/rede o overlay some (mapa sem
    nomes, identico ao anterior). A camada so-pins (concorrentes) nao recebe overlay.

    BLK-RELPON-05: os 3 choropleths (densidade/renda/score) recebem uma faixa superior,
    computada a partir do PROPRIO `result` interno desta funcao (mesma chamada de
    `analisar_ponto_censitario_setores` que ja existia antes desta mudanca) -- nenhum
    caller em `pages.py` precisa mudar para o recurso aparecer, tanto no PNG interativo do
    dashboard quanto no PDF (que embute os mesmos PNGs). A camada `concorrentes` NAO
    recebe a faixa (fica byte-a-byte igual): e um mapa so-pins, sem variavel continua por
    setor. BLK-RELPON-06 (D1) REVERTEU a fonte da faixa: era o valor BRUTO do setor que
    CONTEM o ponto, agora sao os agregados do RAIO de 1.5 km (densidade sobre area valida,
    renda e score medios ponderados) -- rotulo "no raio". Os 5 campos `*_setor_ponto`
    continuam no `result` para CSV/auditoria.
    """
    if logos_dir is not None:
        from motor_expansao.dashboard.competitors import preload_logos

        preload_logos(logos_dir, ultra_dir=ultra_logo_dir)

    result = analisar_ponto_censitario_setores(
        lat,
        lng,
        setores_df,
        raio_km=raio_km,
        competitors_df=competitors_df,
        ultra_df=ultra_df,
    )
    # Frame do mapa: RETANGULO com a proporcao da area de mapa (nao mais quadrado), para o
    # choropleth preencher a figura inteira sem letterbox (ver `_frame_box_metric`).
    frame_box_metric = _frame_box_metric(raio_km, width, height)
    sector_records, circle_metric = _decode_intersections(
        lat,
        lng,
        setores_df,
        raio_km,
        frame_box_metric,
    )

    # Transformer compartilhado: criado UMA vez para todos os setores e geometrias
    # do mesmo render (mesmo lat/lng -> mesmo CRS aeqd local -> mesmo 3857). Fix 1 BLK-PERF-01a.
    _crs_local = _local_metric_crs(lat, lng)
    _to_3857 = _transformer(_crs_local, CRS_WEB_MERCATOR)

    # Reprojeta setores + circulo + centro + frame do aeqd local -> 3857 (SO para render).
    circle_3857 = _project_geometry(circle_metric, _to_3857)
    center_3857 = _to_3857.transform(0.0, 0.0)
    frame_3857 = _project_geometry(frame_box_metric, _to_3857)

    sector_records_3857: list[tuple[BaseGeometry, int]] = []
    densidade_vals: list[float] = []
    renda_vals: list[float] = []
    score_vals: list[float] = []
    renda_domiciliar_vals: list[float] = []
    for idx, record in enumerate(sector_records):
        geom = record.get("geometry_metric")
        if not isinstance(geom, BaseGeometry) or geom.is_empty:
            densidade_vals.append(float("nan"))
            renda_vals.append(float("nan"))
            score_vals.append(float("nan"))
            renda_domiciliar_vals.append(float("nan"))
            continue
        sector_records_3857.append((_project_geometry(geom, _to_3857), idx))
        densidade_vals.append(
            float(pd.to_numeric(record.get("densidade_pop_setor_hab_km2"), errors="coerce"))
        )
        renda_calibrada = pd.to_numeric(
            record.get("renda_per_capita_setor_2022_calibrada"), errors="coerce"
        )
        renda_raw = renda_calibrada
        if pd.isna(renda_raw):
            renda_raw = pd.to_numeric(record.get("renda_per_capita_setor_2022"), errors="coerce")
        renda_vals.append(float(renda_raw))
        score_vals.append(
            float(pd.to_numeric(record.get("score_setor_2022_calibrado"), errors="coerce"))
        )
        # Renda media domiciliar por setor (formula setorial do #124, censo_point.py:328-352):
        # renda_pc(CALIBRADA) x moradores x uplift_SETORIAL(cod_setor) x fator_temporal, com fallback
        # POR SETOR para renda_responsavel_media_setor_2022 quando calibrada x moradores e' NaN
        # (`.where(notna, _resp)` do #124). Usa a CALIBRADA (nao a bruta do renda_per_capita), para o
        # setor entrar na cor com o MESMO valor com que entra no agregado `renda_domiciliar_total_raio`.
        moradores = pd.to_numeric(
            record.get("avg_moradores_domicilio_setor_2022"), errors="coerce"
        )
        renda_domiciliar = renda_calibrada * moradores
        if pd.isna(renda_domiciliar):
            renda_domiciliar = pd.to_numeric(
                record.get("renda_responsavel_media_setor_2022"), errors="coerce"
            )
        uf_val = record.get("uf")
        mun_val = record.get("cod_municipio")
        uplift_setor = uplift_composicao_por_setor(
            str(record.get("cod_setor") or ""),
            str(uf_val) if pd.notna(uf_val) else None,
            str(mun_val) if pd.notna(mun_val) else None,
        )
        renda_domiciliar_vals.append(
            float(renda_domiciliar * uplift_setor * float(FATOR_TEMPORAL_RENDA))
        )

    densidade_series = pd.Series(densidade_vals, dtype="float64")
    renda_series = pd.Series(renda_vals, dtype="float64")
    score_series = pd.Series(score_vals, dtype="float64")
    renda_domiciliar_series = pd.Series(renda_domiciliar_vals, dtype="float64")

    # bbox do mapa = o FRAME (quadrado em 3857). Os setores ja foram recortados a ele, entao
    # preenchem o frame todo (corners inclusos), sem sobra de margem nem spill na legenda.
    bounds_t = frame_3857.bounds

    basemap_tiles = None
    labels_tiles = None
    if basemap:
        basemap_tiles = _fetch_basemap(bounds_t, width)
        # rotulos buscados UMA vez (compartilhados pelas 4 camadas de choropleth); so quando ha
        # basemap (mesma condicao de rede) e o overlay esta ligado. best-effort -> None nao quebra.
        if basemap_tiles is not None and labels_overlay:
            labels_tiles = _fetch_labels(bounds_t, width)

    pins = _project_points(result["concorrentes_raio"], lat, lng)
    ultra_pins = _project_points(result["ultra_raio"], lat, lng)
    n_setores = result["n_setores"]

    # Alpha efetivo do choropleth: None -> constante do modulo (identico ao dashboard). As
    # color_fn locais reproduzem `_color_for_densidade/renda/score` exatamente quando
    # eff_alpha == _CHOROPLETH_ALPHA; so a API passa um alpha menor p/ as ruas aparecerem.
    eff_alpha = _CHOROPLETH_ALPHA if choropleth_alpha is None else int(choropleth_alpha)
    sem_dado = (_FILL_SEM_DADO[0], _FILL_SEM_DADO[1], _FILL_SEM_DADO[2], eff_alpha)

    def _dens_fn(value: float) -> tuple[int, int, int, int]:
        if pd.isna(value):
            return sem_dado
        r, g, b, _a = _color_for_bands(value, DENSIDADE_POP_BANDS)
        return (int(r), int(g), int(b), eff_alpha)

    def _renda_fn(value: float) -> tuple[int, int, int, int]:
        if pd.isna(value):
            return sem_dado
        r, g, b, _a = _color_for_bands(value, RENDA_PER_CAPITA_BANDS)
        return (int(r), int(g), int(b), eff_alpha)

    def _renda_dom_fn(value: float) -> tuple[int, int, int, int]:
        if pd.isna(value):
            return sem_dado
        r, g, b, _a = _color_for_bands(value, RENDA_MEDIA_DOMICILIAR_BANDS)
        return (int(r), int(g), int(b), eff_alpha)

    def _score_fn(value: float) -> tuple[int, int, int, int]:
        rgba = score_band_to_color(value, alpha=eff_alpha)
        return (int(rgba[0]), int(rgba[1]), int(rgba[2]), int(rgba[3]))

    common = dict(
        sector_records_3857=sector_records_3857,
        circle_3857=circle_3857,
        center_3857=center_3857,
        pins=pins,
        ultra_pins=ultra_pins,
        basemap=basemap_tiles,
        labels=labels_tiles,
        bounds=bounds_t,
        lat=lat,
        lng=lng,
        raio_km=raio_km,
        n_setores=n_setores,
        width=width,
        height=height,
        street_ceil=street_ceil,
        street_gain=street_gain,
        street_cap=street_cap,
    )

    # BLK-RELPON-06 (D1): faixa superior por camada, com os agregados do RAIO de 1.5 km
    # (ja expostos por `result`, computados no proprio `analisar_ponto_censitario_setores`
    # acima) -- REVERTE a fonte do BLK-RELPON-05, que usava o valor BRUTO do setor que
    # CONTEM o ponto. "n/d" quando nao ha setores intersectados (sem area valida).
    valor_raio_densidade = _legenda_valor_ponto(
        "Densidade", _format_valor_ponto_densidade(result.get("densidade_pop_raio_valida_hab_km2"))
    )
    valor_raio_renda = _legenda_valor_ponto(
        "Renda", _format_valor_ponto_renda(result.get("renda_per_capita_media_raio"))
    )
    valor_raio_score = _legenda_valor_ponto(
        "Score", _format_valor_ponto_score(result.get("score_setor_medio"))
    )
    # Faixa da renda domiciliar: usa o agregado do raio COM uplift+temporal (mesma escala das
    # bandas), NAO o pre-uplift `renda_media_domiciliar_raio` (cairia sempre na faixa mais baixa).
    valor_raio_renda_dom = _legenda_valor_ponto(
        "Renda dom.", _format_valor_ponto_renda(result.get("renda_domiciliar_total_raio"))
    )

    densidade_png = _render_camada(
        titulo="Densidade populacional",
        legenda_titulo="Densidade (hab/km2)",
        legenda_entries=_bands_legend_entries(DENSIDADE_POP_BANDS),
        color_fn=_dens_fn,
        source_values=densidade_series,
        valor_ponto=valor_raio_densidade,
        **common,
    )
    renda_png = _render_camada(
        titulo="Renda per capita",
        legenda_titulo="Renda per capita (R$/pessoa)",
        legenda_entries=_bands_legend_entries(RENDA_PER_CAPITA_BANDS),
        color_fn=_renda_fn,
        source_values=renda_series,
        valor_ponto=valor_raio_renda,
        **common,
    )
    # Camada Score censitario: choropleth COM legenda (modo de cor ativo) — restaurada no
    # BLK-CENSO-03-FU5 (Felipe, 2026-06-08). Distinta da camada Concorrentes (so-pins).
    score_png = _render_camada(
        titulo="Score censitario",
        legenda_titulo="Score censitario (0-100)",
        legenda_entries=_score_legend_entries(),
        color_fn=_score_fn,
        source_values=score_series,
        valor_ponto=valor_raio_score,
        **common,
    )
    renda_domiciliar_png = _render_camada(
        titulo="Renda media domiciliar",
        legenda_titulo="Renda domiciliar (R$/domicilio)",
        legenda_entries=_bands_legend_entries(RENDA_MEDIA_DOMICILIAR_BANDS),
        color_fn=_renda_dom_fn,
        source_values=renda_domiciliar_series,
        valor_ponto=valor_raio_renda_dom,
        **common,
    )
    concorrentes_png = _render_camada(
        titulo="Concorrentes e Ultra",
        legenda_titulo="Pins: Ultra e concorrentes",
        legenda_entries=[],  # sem faixas de choropleth (camada so-pins)
        color_fn=_color_for_score,  # irrelevante quando pins_only=True
        source_values=score_series,  # irrelevante quando pins_only=True
        pins_only=True,
        **common,
    )
    # BLK-RELPON-11: camada `entorno` (mapa de quadra, raio de EXIBICAO ~0,14 km). Tem frame,
    # bbox e zoom PROPRIOS -> nao entra no `common`. INCONDICIONAL: devolve sempre bytes (canvas
    # claro no fallback offline), por isso vai dentro do dict literal abaixo.
    entorno_png = _render_camada_entorno(
        lat,
        lng,
        basemap=basemap,
        width=width,
        height=height,
    )

    mapas: dict[str, bytes] = {
        "densidade": densidade_png,
        "renda": renda_png,
        "score": score_png,
        "renda_domiciliar": renda_domiciliar_png,
        "concorrentes": concorrentes_png,
        "entorno": entorno_png,
    }

    # BLK-RELPON-13: camada `socioeconomia` do slide-hero = `score_setor_2022_calibrado` por
    # HEXAGONO H3 res-7 no raio de EXIBICAO de 5 km (disco `grid_disk` k=5), MESMA metrica/paleta
    # do `score` do grid 2x2 — o que muda e' a geometria/escala (hex a 5 km, nao setor a 1,5 km).
    # Reusa `_render_camada_residual_hex` (mesmo frame/basemap/clip do residual), so trocando o
    # dado/titulo/legenda/cor. CONDICIONAL como o `residual`: sem `hexes_df`, sem a coluna
    # `score_setor_2022_calibrado` ou sem hex desenhavel -> chave AUSENTE, fallback textual do PDF.
    socioeconomia_png = _render_camada_residual_hex(
        lat,
        lng,
        hexes_df,
        basemap=basemap,
        width=width,
        height=height,
        street_ceil=street_ceil,
        street_gain=street_gain,
        street_cap=street_cap,
        choropleth_alpha=choropleth_alpha,
        value_col="score_setor_2022_calibrado",
        titulo="Socioeconomia - raio 5 km",  # ASCII (excecao de RENDER, CLAUDE.md §2)
        legenda_titulo="Score censitario (0-100)",
        legenda_entries=_score_legend_entries(),
        color_fn=_score_fn,
        valor_central_rotulo="Score",
        valor_central_fmt=_format_valor_ponto_score,
    )
    if socioeconomia_png is not None:
        mapas["socioeconomia"] = socioeconomia_png

    # Camada `residual` (raio de EXIBICAO de 5 km, hexagonos H3): CONDICIONAL. Sem `hexes_df` ou
    # sem hex desenhavel a chave nao entra -> o slide cai no fallback textual do `_draw_maps_grid`.
    residual_png = _render_camada_residual_hex(
        lat,
        lng,
        hexes_df,
        basemap=basemap,
        width=width,
        height=height,
        street_ceil=street_ceil,
        street_gain=street_gain,
        street_cap=street_cap,
        choropleth_alpha=choropleth_alpha,
    )
    if residual_png is not None:
        mapas["residual"] = residual_png
    return mapas


def render_mapa_censitario_estatico_png(
    lat: float,
    lng: float,
    setores_df: pd.DataFrame,
    *,
    raio_km: float = RAIO_CENSITARIO_DEFAULT_KM,
    metric_column: str = "pop_estimada_intersecao",
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
    width: int = 1000,
    height: int = 760,
    basemap: bool = False,
) -> bytes:
    """LEGADO: wrapper fino sobre `render_mapas_censitarios_combinados`.

    Mantido para imports externos durante a migracao. Devolve UMA das camadas combinadas,
    mapeando o antigo `metric_column` para a chave canonica mais proxima (renda->"renda",
    score->"score", demais->"densidade"). `basemap=False` por padrao (offline) p/
    nao depender de internet em chamadas legadas. Prefira a orquestradora combinada.
    """
    mapas = render_mapas_censitarios_combinados(
        lat,
        lng,
        setores_df,
        raio_km=raio_km,
        competitors_df=competitors_df,
        ultra_df=ultra_df,
        width=width,
        height=height,
        basemap=basemap,
    )
    if metric_column == "renda_per_capita_setor_2022_calibrada":
        return mapas["renda"]
    if metric_column == "score_setor_2022_calibrado":
        return mapas["score"]
    return mapas["densidade"]


# ===========================================================================
# TESTE (ainda NAO definitivo) — FOTO DE SATELITE do ponto.
#
# Fonte: Esri World Imagery + Reference/World_Transportation (rotulos) — a MESMA
# composicao do "World Imagery Hybrid" da Esri e do sat-overlay do
# openmaptiles-infra. Aditivo: nenhuma funcao existente foi tocada.
#
# Zoom: tenta z19 e cai p/ z18 conforme a disponibilidade REAL no ponto (a Esri
# devolve placeholder de ~2,5 KB onde nao ha imagem). Medido em 22 pontos do
# Brasil: z17 existe em todo lugar, z18 em cidade media/grande, z19 so em capital.
#
# LICENCA (REGULARIZADA — DEC-018): a imagem vem do ArcGIS Location Platform
# (`ibasemaps-api.arcgis.com`), autenticada por CHAVE. A API passa a chave via
# `settings.arcgis_api_key` (env `API_ARCGIS_API_KEY`); o dashboard cai no fallback
# de env `_sat_api_key()`. A chave precisa do privilegio `premium:user:basemaps`
# (faixa gratuita de 2M tiles/mes) e NUNCA e commitada. SEM chave, a pagina de
# satelite e simplesmente OMITIDA (render devolve None) -- nunca se cai no endpoint
# anonimo `server.arcgisonline.com`, cujo uso os termos da Esri consideram irregular.
# A imagem e SEMPRE externa (nao se self-hospeda) e o credito da Esri e obrigatorio
# -- por isso `_SAT_ATRIBUICAO` e desenhado no canto da foto.
# ===========================================================================

# Env var com a chave do ArcGIS Location Platform (fallback p/ chamadas sem settings,
# ex.: dashboard). Na API a chave vem de `settings.arcgis_api_key`, passada explicita.
_SAT_API_KEY_ENV = "API_ARCGIS_API_KEY"
_SAT_TILE_URL = (
    "https://ibasemaps-api.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
_SAT_ROTULOS_URL = (
    "https://ibasemaps-api.arcgis.com/arcgis/rest/services/Reference/World_Transportation"
    "/MapServer/tile/{z}/{y}/{x}"
)
_SAT_ATRIBUICAO = "Esri, Vantor, Earthstar Geographics"
# Faixa da sonda de zoom. O piso era 18 e isso FURAVA em area sem cobertura fina: a Esri
# devolve 404 em z18/z19 (ex.: -10.1880,-48.3247, interior do TO, onde so ha imagem de z17
# para baixo), a sonda nao achava nada e caia no piso 18 -> todos os tiles 404 -> saia uma
# PAGINA PRETA no PDF. Agora desce ate 16 e, se nem ai houver imagem, a pagina e OMITIDA.
_SAT_ZOOM_MIN, _SAT_ZOOM_MAX = 16, 19
_SAT_PLACEHOLDER_MAX_BYTES = 3000
# Zoom baixo cobre os mesmos 400 m com MENOS pixels (z17 ~365 px, z16 ~180 px) e a celula do
# PDF tem ~1100 px. Ampliamos ate esta largura ANTES de desenhar pin e credito, para os dois
# sairem nitidos sobre o fundo ampliado (o credito da Esri e exigido pela licenca).
_SAT_LARGURA_ALVO = 1100
_SAT_COBERTURA_M = 400          # largura do enquadramento no chao
# Proporcao = a MESMA da celula de foto do PDF (`_FOTO_ASPECT`, paisagem 3:2). Se gerar
# em outra proporcao, `_recortar_cover` corta as laterais p/ encaixar na celula -- e o
# corte come o credito da Esri no canto, que a licenca exige visivel. Medido no teste:
# em 1,667 o PDF cortou 141 px e a atribuicao saiu pela metade.
_SAT_RATIO = 3.0 / 2.0
_SAT_RAIO_CANTO_PCT = 0.025
_SAT_TILE_PX = 256
_SAT_UA = {"User-Agent": "motor_expansao_ultra_academia_bot"}


def _sat_deg2num(lat: float, lng: float, z: int) -> tuple[float, float]:
    """lat/lng -> coordenada de tile FRACIONARIA (a parte decimal centraliza o recorte)."""
    n = 2.0**z
    x = (lng + 180.0) / 360.0 * n
    y = (
        1.0 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi
    ) / 2.0 * n
    return x, y


def _sat_api_key() -> str | None:
    """Fallback: chave do ArcGIS Location Platform lida de env (`API_ARCGIS_API_KEY`).

    Usado por chamadores SEM `settings` (ex.: dashboard). A API passa a chave
    explicitamente via `render_foto_satelite_ponto(..., api_key=settings.arcgis_api_key)`.
    """
    import os

    return os.environ.get(_SAT_API_KEY_ENV) or None


def _sat_url(base: str, z: int, x: int, y: int, token: str) -> str:
    """URL do tile ja autenticada com o token do ArcGIS Location Platform (`?token=`)."""
    from urllib.parse import quote

    return f"{base.format(z=z, x=x, y=y)}?token={quote(token, safe='')}"


def _sat_baixar_tile(url: str, z: int, x: int, y: int, timeout: float, token: str) -> Image.Image:
    import urllib.request

    req = urllib.request.Request(_sat_url(url, z, x, y, token), headers=_SAT_UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return Image.open(BytesIO(resp.read())).convert("RGBA")


def _sat_melhor_zoom(lat: float, lng: float, timeout: float, token: str) -> int | None:
    """Maior zoom com imagem REAL neste ponto (1 tile de sonda, nao o mosaico todo).

    Desce de `_SAT_ZOOM_MAX` ate `_SAT_ZOOM_MIN` ate achar cobertura. Devolve `None`
    quando NENHUM zoom tem imagem real -- a Esri responde 404 (ou um placeholder de
    ~2,5 KB) fora da area coberta. Antes esta funcao devolvia o piso nesse caso, o que
    fazia o mosaico buscar tiles inexistentes e render uma pagina PRETA.
    """
    import urllib.request

    for z in range(_SAT_ZOOM_MAX, _SAT_ZOOM_MIN - 1, -1):
        fx, fy = _sat_deg2num(lat, lng, z)
        try:
            req = urllib.request.Request(
                _sat_url(_SAT_TILE_URL, z, int(fx), int(fy), token), headers=_SAT_UA
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if len(resp.read()) > _SAT_PLACEHOLDER_MAX_BYTES:
                    return z
        except Exception:
            continue
    return None


def _sat_desenhar_pin(img: Image.Image, escala: float) -> None:
    """Pin vermelho com a PONTA no centro — mesma geometria de `_draw_center_pin`."""
    cx, cy = img.width // 2, img.height // 2
    vermelho = (218, 32, 32)
    r = max(6, int(round(9 * escala)))
    topo = cy - int(round(24 * escala))

    camada = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    sr = int(r * 1.2)
    d.ellipse([cx - sr, cy - int(sr * 0.34), cx + sr, cy + int(sr * 0.34)], fill=(0, 0, 0, 115))
    # gota: o pescoco sai TANGENTE a cabeca, senao circulo+triangulo viram um borrao
    bx, by = r * 0.72, topo + r * 0.70
    d.polygon([(cx, cy), (cx - bx, by), (cx + bx, by)], fill=vermelho)
    d.ellipse([cx - r, topo - r, cx + r, topo + r], fill=vermelho)
    furo = max(3, int(round(r * 0.38)))
    d.ellipse([cx - furo, topo - furo, cx + furo, topo + furo], fill=(255, 255, 255))
    img.paste(Image.alpha_composite(img.convert("RGBA"), camada).convert("RGB"), (0, 0))


def render_foto_satelite_ponto(
    lat: float,
    lng: float,
    *,
    api_key: str | None = None,
    cobertura_m: int = _SAT_COBERTURA_M,
    zoom: int | None = None,
    rotulos: bool = True,
    timeout: float = 20.0,
) -> bytes | None:
    """PNG da foto de satelite do ponto, com pin no centro. `None` se a rede falhar
    OU se nao houver chave do ArcGIS Location Platform.

    `api_key`: chave do ArcGIS Location Platform. A API passa `settings.arcgis_api_key`;
    se omitido, cai no fallback de env `_sat_api_key()` (ex.: dashboard).

    Devolver `None` (em vez de levantar) e proposital: o chamador segue gerando o
    relatorio sem a pagina de foto, igual ao fallback offline do `_fetch_basemap`.
    Sem chave, a pagina e omitida — nunca se busca tile no endpoint anonimo (licenca).
    """
    try:
        token = api_key or _sat_api_key()
        if not token:
            return None
        z = zoom if zoom is not None else _sat_melhor_zoom(lat, lng, timeout, token)
        if z is None:
            return None  # sem cobertura de imagem em nenhum zoom -> pagina omitida
        m_px = 156543.03392 * math.cos(math.radians(lat)) / (2**z)
        larg = int(round(cobertura_m / m_px))
        alt = int(round(larg / _SAT_RATIO))

        fx, fy = _sat_deg2num(lat, lng, z)
        x0, y0 = fx * _SAT_TILE_PX - larg / 2, fy * _SAT_TILE_PX - alt / 2
        tx0, ty0 = math.floor(x0 / _SAT_TILE_PX), math.floor(y0 / _SAT_TILE_PX)
        tx1 = math.floor((x0 + larg) / _SAT_TILE_PX)
        ty1 = math.floor((y0 + alt) / _SAT_TILE_PX)
        coords = [(tx, ty) for ty in range(ty0, ty1 + 1) for tx in range(tx0, tx1 + 1)]

        tam = ((tx1 - tx0 + 1) * _SAT_TILE_PX, (ty1 - ty0 + 1) * _SAT_TILE_PX)
        canvas = Image.new("RGBA", tam, (20, 24, 34, 255))
        urls = [_SAT_TILE_URL] + ([_SAT_ROTULOS_URL] if rotulos else [])
        tiles_foto_ok = 0                          # quantos tiles da FOTO entraram
        with ThreadPoolExecutor(max_workers=8) as ex:
            for url in urls:                       # ordem importa: foto, depois rotulo
                futs = {
                    (tx, ty): ex.submit(_sat_baixar_tile, url, z, tx, ty, timeout, token)
                    for tx, ty in coords
                }
                for (tx, ty), fut in futs.items():
                    try:
                        canvas.alpha_composite(
                            fut.result(),
                            ((tx - tx0) * _SAT_TILE_PX, (ty - ty0) * _SAT_TILE_PX),
                        )
                        if url == _SAT_TILE_URL:
                            tiles_foto_ok += 1
                    except Exception:
                        continue                   # tile faltando nao invalida a foto
        # NENHUM tile de foto entrou -> so restaria o canvas de fundo. Devolver isso
        # gerava uma pagina PRETA no PDF; o certo e omitir a pagina (mesmo contrato do
        # fallback de rede). Um tile faltando aqui e ali continua tolerado (acima).
        if tiles_foto_ok == 0:
            return None
        ox, oy = int(round(x0 - tx0 * _SAT_TILE_PX)), int(round(y0 - ty0 * _SAT_TILE_PX))
        img = canvas.crop((ox, oy, ox + larg, oy + alt)).convert("RGB")

        # Em zoom baixo os mesmos 400 m rendem poucos pixels; amplia ANTES do pin e do
        # credito, para os dois ficarem nitidos sobre o fundo ampliado.
        if img.width < _SAT_LARGURA_ALVO:
            img = img.resize(
                (_SAT_LARGURA_ALVO, int(round(_SAT_LARGURA_ALVO / _SAT_RATIO))),
                Image.Resampling.LANCZOS,
            )
            larg = img.width                       # pin e canto arredondado seguem o tamanho final

        _sat_desenhar_pin(img, escala=larg / 520)

        # credito da Esri: exigido pela licenca. Texto com sombra, sem caixa.
        d = ImageDraw.Draw(img, "RGBA")
        f = _font(max(11, int(14 * (img.width / 1100))))
        bb = d.textbbox((0, 0), _SAT_ATRIBUICAO, font=f)
        # nome proprio: `tx`/`ty` acima sao coordenadas INTEIRAS de tile no laco do
        # mosaico; reusar os nomes aqui (float) quebra o mypy.
        cred_x = img.width - (bb[2] - bb[0]) - 10
        cred_y = img.height - (bb[3] - bb[1]) - 10
        for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            d.text((cred_x + dx, cred_y + dy), _SAT_ATRIBUICAO, font=f, fill=(0, 0, 0, 150))
        d.text((cred_x, cred_y), _SAT_ATRIBUICAO, font=f, fill=(255, 255, 255, 225))

        raio = int(round(larg * _SAT_RAIO_CANTO_PCT))
        if raio > 0:
            mask = Image.new("L", img.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                [0, 0, img.width - 1, img.height - 1], raio, fill=255
            )
            arredondado = Image.new("RGBA", img.size, (255, 255, 255, 0))
            arredondado.paste(img, (0, 0), mask)
            img = arredondado

        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None
