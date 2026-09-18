"""PNGs das paginas da PRACA nos Relatorios Municipal e Pontual (ver `relatorio_praca.py`).

Desenhos em EPSG:3857 sobre o mesmo fundo de ruas das demais camadas (`_fetch_basemap`, com o
fallback offline de sempre -- sem rede, canvas claro, e o PDF sai igual):

- `render_calor_cidade` (municipal): hexagonos do municipio coloridos por quantil da cidade;
- `render_pressao_cidade` (municipal): um disco translucido por academia do municipio;
- `render_pressao_raios` (pontual): os discos no entorno do ponto -- onde se sobrepoem, a cor se
  soma e escurece;
- `render_onde_crescer` (municipal): a cidade em cinza e os hexagonos escolhidos numerados.

Texto dentro do PNG em ASCII (excecao de RENDER do CLAUDE.md §2: a fonte do PNG nao tem glifo
acentuado). So' exibicao: nada aqui recalcula score nem grava artefato.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from io import BytesIO

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

from motor_expansao.dashboard.censo_map import (
    CRS_WEB_MERCATOR,
    _atribuicao_tiles,
    _draw_center_pin,
    _draw_scale_bar,
    _draw_text,
    _fetch_basemap,
    _font,
    _paste_logo_pin,
    _text_width,
)
from motor_expansao.dashboard.censo_point import CRS_ORIGEM_CENSO, _transformer
from motor_expansao.dashboard.constants import DENSIDADE_POP_BANDS, RENDA_MEDIA_DOMICILIAR_BANDS
from motor_expansao.dashboard.relatorio_praca import distancia_m, quebras_por_quantil
from motor_expansao.pipelines.pressao_concorrencial_1km import RAIO_INFLUENCIA_M

_W = 1400
_H = 1000
_MAP_TOP = 96
_LEGEND_W = 360
_MARGEM = 24
_TINTA = (31, 41, 55)
_TINTA_SUAVE = (71, 85, 105)
_SEM_DADO = (210, 214, 222, 150)

# Paletas das faixas do slide "Mapas de calor" (constants, perfil do pais): as imagens da cidade
# falam a mesma lingua de cor da grade 2x2. Os CORTES continuam sendo os quintis da cidade.
PALETA_RENDA = [tuple(b[2][:3]) for b in RENDA_MEDIA_DOMICILIAR_BANDS]
PALETA_DENSIDADE = [tuple(b[2][:3]) for b in DENSIDADE_POP_BANDS]
_ALPHA_CALOR = 185

# Discos da pressao: cadeia em magenta, independente em ambar, Ultra em turquesa.
_COR_CADEIA = (194, 60, 142)
_COR_INDEPENDENTE = (217, 119, 6)
_COR_ULTRA = (0, 167, 157)
_ALPHA_DISCO = 38
_ALPHA_BORDA = 150

# Verde, e nao o turquesa da marca: no mapa da cidade o escolhido tem de saltar do cinza e nao
# se confundir com a unidade Ultra da pagina de pressao.
_COR_TOP = (22, 163, 74)
_COR_TOP_BORDA = (20, 83, 45)
_COR_CIDADE = (148, 163, 184, 70)

_JANELA_PRESSAO_M = 2_600.0

#: Margem do quadro de "Onde crescer" em torno dos hexagonos escolhidos (fracao do proprio span).
#: 0,6 deixa cerca de um hexagono de folga de cada lado quando os 5 estao juntos.
_MARGEM_ONDE_CRESCER = 0.6


def _png(image: Image.Image) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


class _Quadro:
    """Projecao lat/lng -> pixel dentro da caixa do mapa, preservando proporcao."""

    def __init__(self, bounds_3857: tuple[float, float, float, float], width: int, height: int) -> None:
        self.left = _MARGEM
        self.top = _MAP_TOP
        self.right = width - _LEGEND_W
        self.bottom = height - 56
        minx, miny, maxx, maxy = bounds_3857
        inner_w = self.right - self.left
        inner_h = self.bottom - self.top
        # Expande a bbox para a proporcao da caixa: sem isso o fundo de ruas nao cobre a caixa.
        span_x = max(maxx - minx, 1.0)
        span_y = max(maxy - miny, 1.0)
        if span_x / span_y < inner_w / inner_h:
            extra = (span_y * inner_w / inner_h - span_x) / 2.0
            minx, maxx = minx - extra, maxx + extra
        else:
            extra = (span_x * inner_h / inner_w - span_y) / 2.0
            miny, maxy = miny - extra, maxy + extra
        self.bounds = (minx, miny, maxx, maxy)
        self.scale = inner_w / (maxx - minx)
        self._to_3857 = _transformer(CRS_ORIGEM_CENSO, CRS_WEB_MERCATOR)

    @property
    def caixa(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.right, self.bottom)

    def xy(self, x: float, y: float) -> tuple[float, float]:
        minx, _miny, _maxx, maxy = self.bounds
        return self.left + (x - minx) * self.scale, self.top + (maxy - y) * self.scale

    def lnglat(self, lng: float, lat: float) -> tuple[float, float]:
        x, y = self._to_3857.transform(float(lng), float(lat))
        return self.xy(x, y)

    def metros_em_px(self, metros: float, lat: float) -> float:
        # Em 3857 a escala cresce com 1/cos(lat): um metro no chao ocupa mais unidades do mapa.
        return metros / max(math.cos(math.radians(lat)), 0.01) * self.scale


def _bounds_de_pontos(lats: Sequence[float], lngs: Sequence[float], margem: float = 0.04) -> tuple[float, float, float, float]:
    to_3857 = _transformer(CRS_ORIGEM_CENSO, CRS_WEB_MERCATOR)
    xs, ys = to_3857.transform(np.asarray(lngs, dtype="float64"), np.asarray(lats, dtype="float64"))
    minx, maxx = float(np.nanmin(xs)), float(np.nanmax(xs))
    miny, maxy = float(np.nanmin(ys)), float(np.nanmax(ys))
    # Piso de 1.500 m: com 1 ou 2 hexagonos quase no mesmo ponto o span tende a zero e o mapa
    # sairia num zoom de rua, sem contexto nenhum.
    dx = max((maxx - minx) * margem, 1_500.0) + 200.0
    dy = max((maxy - miny) * margem, 1_500.0) + 200.0
    return (minx - dx, miny - dy, maxx + dx, maxy + dy)


def _base(quadro: _Quadro, titulo: str, subtitulo: str | None, *, basemap: bool) -> tuple[Image.Image, ImageDraw.ImageDraw, bool]:
    image = Image.new("RGBA", (_W, _H), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image, "RGBA")
    _draw_text(draw, (_MARGEM, 18), titulo, font=_font(40))
    if subtitulo:
        _draw_text(draw, (_MARGEM, 62), subtitulo, font=_font(24), fill=_TINTA_SUAVE)
    left, top, right, bottom = quadro.caixa
    desenhou = False
    tiles = _fetch_basemap(quadro.bounds, right - left, zoom_bump=-1) if basemap else None
    if tiles is not None:
        try:
            arr, (ex_minx, ex_maxx, ex_miny, ex_maxy) = tiles
            bm = Image.fromarray(np.asarray(arr)).convert("RGB")
            x0, y0 = quadro.xy(ex_minx, ex_maxy)
            x1, y1 = quadro.xy(ex_maxx, ex_miny)
            bm = bm.resize((max(1, int(round(x1 - x0))), max(1, int(round(y1 - y0)))), Image.Resampling.LANCZOS)
            tela = Image.new("RGB", (_W, _H), (245, 245, 245))
            tela.paste(bm, (int(round(x0)), int(round(y0))))
            image.paste(tela.crop((left, top, right, bottom)), (left, top))
            desenhou = True
        except Exception:
            desenhou = False
    if not desenhou:
        draw.rectangle(quadro.caixa, fill=(245, 245, 245))
    return image, draw, desenhou


def _fechar(image: Image.Image, draw: ImageDraw.ImageDraw, quadro: _Quadro, desenhou: bool) -> bytes:
    draw.rectangle(quadro.caixa, outline=_TINTA_SUAVE, width=2)
    _draw_scale_bar(draw, quadro.caixa, 1.0 / quadro.scale)
    rodape = f"EPSG:3857 - {_atribuicao_tiles() if desenhou else 'fundo de ruas offline'}"
    _draw_text(draw, (_MARGEM, _H - 40), rodape, font=_font(20), fill=_TINTA_SUAVE)
    return _png(image.convert("RGB"))


def _poligono_hex(hex_id: str) -> list[tuple[float, float]] | None:
    try:
        import h3

        return [(float(lat), float(lng)) for lat, lng in h3.cell_to_boundary(str(hex_id))]
    except Exception:
        return None


def _desenhar_hex(draw: ImageDraw.ImageDraw, quadro: _Quadro, hex_id: str, fill: tuple[int, ...], outline: tuple[int, ...] | None = None, width: int = 1) -> tuple[float, float] | None:
    borda = _poligono_hex(hex_id)
    if not borda:
        return None
    pts = [quadro.lnglat(lng, lat) for lat, lng in borda]
    draw.polygon(pts, fill=fill)
    if outline is not None:
        draw.line(pts + [pts[0]], fill=outline, width=width)
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def _legenda(draw: ImageDraw.ImageDraw, titulo: str, itens: Sequence[tuple[str, tuple[int, ...]]], *, y: int = _MAP_TOP) -> int:
    x = _W - _LEGEND_W + 24
    _draw_text(draw, (x, y), titulo, font=_font(26))
    yy = y + 44
    for rotulo, cor in itens:
        draw.rounded_rectangle([x, yy, x + 46, yy + 32], radius=5, fill=cor[:3], outline=(148, 163, 184))
        _draw_text(draw, (x + 58, yy + 4), rotulo, font=_font(22))
        yy += 44
    return yy


def _centroides(hexes: pd.DataFrame) -> tuple[list[float], list[float]]:
    import h3

    lats: list[float] = []
    lngs: list[float] = []
    for h in hexes["hex_id"].astype(str):
        try:
            la, lo = h3.cell_to_latlng(h)
        except Exception:
            continue
        lats.append(float(la))
        lngs.append(float(lo))
    return lats, lngs


def _com_ponto(lats: list[float], lngs: list[float], lat: float | None, lng: float | None) -> tuple[list[float], list[float]]:
    if lat is None or lng is None:
        return lats, lngs
    return lats + [lat], lngs + [lng]


def _pin_do_ponto(draw: ImageDraw.ImageDraw, quadro: _Quadro, lat: float | None, lng: float | None, scale: float) -> None:
    if lat is None or lng is None:
        return
    cx, cy = quadro.lnglat(lng, lat)
    _draw_center_pin(draw, int(round(cx)), int(round(cy)), scale=scale)


def render_calor_cidade(
    hexes: pd.DataFrame | None,
    value_col: str,
    *,
    lat: float | None = None,
    lng: float | None = None,
    titulo: str,
    legenda_titulo: str,
    formatar: Callable[[float], str],
    paleta: Sequence[tuple[int, int, int]],
    subtitulo: str | None = None,
    basemap: bool = True,
) -> bytes | None:
    """Mapa de calor do municipio por hexagono, com faixas por quantil da propria cidade.

    `None` quando nao ha hexagono com valor -- a pagina cai no fallback textual da grade.
    """
    if hexes is None or hexes.empty or value_col not in hexes.columns or "hex_id" not in hexes.columns:
        return None
    valores = pd.to_numeric(hexes[value_col], errors="coerce")
    limites = quebras_por_quantil(valores, n_classes=len(paleta))
    if not limites:
        return None
    lats, lngs = _centroides(hexes)
    if not lats:
        return None
    quadro = _Quadro(_bounds_de_pontos(*_com_ponto(lats, lngs, lat, lng)), _W, _H)
    image, draw, desenhou = _base(quadro, titulo, subtitulo, basemap=basemap)

    # A paleta encolhe junto quando o quantil colapsa (cidade pequena): as cores de ponta ficam.
    idx_cor = np.linspace(0, len(paleta) - 1, len(limites)).round().astype(int)
    cores = [(*paleta[i], _ALPHA_CALOR) for i in idx_cor]

    def cor(v: float) -> tuple[int, ...]:
        if pd.isna(v) or v <= 0:
            return _SEM_DADO
        for limite, c in zip(limites, cores, strict=True):
            if v <= limite:
                return c
        return cores[-1]

    for h, v in zip(hexes["hex_id"].astype(str), valores, strict=True):
        _desenhar_hex(draw, quadro, h, cor(float(v)) if not pd.isna(v) else _SEM_DADO)

    _pin_do_ponto(draw, quadro, lat, lng, 1.3)

    itens: list[tuple[str, tuple[int, ...]]] = []
    anterior = 0.0
    for i, (limite, c) in enumerate(zip(limites, cores, strict=True)):
        # A ultima faixa vai ate' o MAXIMO da cidade, que costuma ser um hexagono atipico: escrever
        # o maximo na legenda poe um numero de outlier no lugar de destaque. "acima de" basta.
        ultima = i == len(limites) - 1 and i > 0
        # Faixa DEGENERADA: com os cortes proximos, os dois extremos formatam igual e a linha
        # sairia "0,2 a 0,2" (Manaus, densidade: a floresta domina os quintis). Ela se funde com a
        # proxima -- `anterior` nao avanca, entao o intervalo seguinte comeca do mesmo piso.
        if not ultima and formatar(anterior) == formatar(limite):
            continue
        rotulo = f"acima de {formatar(anterior)}" if ultima else f"{formatar(anterior)} a {formatar(limite)}"
        if itens and itens[-1][0] == rotulo:
            anterior = limite
            continue
        itens.append((rotulo, c))
        anterior = limite
    itens.append(("Sem dado", _SEM_DADO))
    yy = _legenda(draw, legenda_titulo, itens)
    _draw_text(draw, (_W - _LEGEND_W + 24, yy + 8), "Faixas: quintis da cidade", font=_font(20), fill=_TINTA_SUAVE)
    return _fechar(image, draw, quadro, desenhou)


def render_pressao_raios(
    lat: float,
    lng: float,
    concorrentes: pd.DataFrame | None,
    ultra: pd.DataFrame | None,
    *,
    raio_m: float = RAIO_INFLUENCIA_M,
    basemap: bool = True,
) -> bytes:
    """Um disco de `raio_m` por academia no entorno; a sobreposicao escurece por soma de alpha."""
    janela = _JANELA_PRESSAO_M
    grau_lat = 111_195.0
    d_lat = janela / grau_lat
    d_lng = janela / (grau_lat * max(math.cos(math.radians(lat)), 0.01))
    quadro = _Quadro(
        _bounds_de_pontos([lat - d_lat, lat + d_lat], [lng - d_lng, lng + d_lng], margem=0.0), _W, _H
    )
    raio_txt = f"{raio_m / 1000:.1f}".replace(".", ",")
    image, draw, desenhou = _base(
        quadro, "Pressao concorrencial", f"Area de influencia de {raio_txt} km por academia", basemap=basemap
    )

    alcance = raio_m + janela * 1.5

    def _perto(df: pd.DataFrame | None) -> pd.DataFrame | None:
        sub = _com_coordenada(df)
        if sub is None:
            return None
        return sub.loc[distancia_m(lat, lng, sub["lat"], sub["lng"]) <= alcance]

    draw = _discos_sobre(image, quadro, _perto(concorrentes), _perto(ultra), raio_m=raio_m, lat_ref=lat)

    cx, cy = quadro.lnglat(lng, lat)
    r_ponto = quadro.metros_em_px(raio_m, lat)
    draw.ellipse([cx - r_ponto, cy - r_ponto, cx + r_ponto, cy + r_ponto], outline=(0, 88, 220, 235), width=4)
    _draw_center_pin(draw, int(round(cx)), int(round(cy)), scale=1.4)

    yy = _legenda_discos(draw)
    x = _W - _LEGEND_W + 24
    draw.ellipse([x, yy + 84, x + 40, yy + 124], outline=(0, 88, 220, 235), width=4)
    _draw_text(draw, (x + 58, yy + 90), f"Raio de {raio_txt} km do ponto", font=_font(22))
    return _fechar(image, draw, quadro, desenhou)


#: Acima disto o mapa da cidade troca as logos por um ponto: numa capital com centenas de
#: academias as logos se empilham e escondem os proprios discos que a pagina quer mostrar.
LOGOS_MAX_CIDADE = 120


def render_pressao_cidade(
    hexes_cidade: pd.DataFrame | None,
    concorrentes: pd.DataFrame | None,
    ultra: pd.DataFrame | None,
    *,
    raio_m: float = RAIO_INFLUENCIA_M,
    basemap: bool = True,
) -> bytes | None:
    """Os discos de `raio_m` de TODAS as academias do municipio, sobre a cidade inteira.

    `concorrentes`/`ultra` chegam ja' recortados ao municipio. `None` sem hexagono para enquadrar.
    """
    if hexes_cidade is None or hexes_cidade.empty or "hex_id" not in hexes_cidade.columns:
        return None
    lats, lngs = _centroides(hexes_cidade)
    if not lats:
        return None
    quadro = _Quadro(_bounds_de_pontos(lats, lngs), _W, _H)
    raio_txt = f"{raio_m / 1000:.1f}".replace(".", ",")
    image, draw, desenhou = _base(
        quadro, "Pressao concorrencial", f"Area de influencia de {raio_txt} km por academia, cidade inteira",
        basemap=basemap,
    )
    conc = _com_coordenada(concorrentes)
    ult = _com_coordenada(ultra)
    n = (0 if conc is None else len(conc)) + (0 if ult is None else len(ult))
    draw = _discos_sobre(
        image, quadro, conc, ult, raio_m=raio_m, lat_ref=float(np.nanmean(lats)), logos=n <= LOGOS_MAX_CIDADE,
    )
    _legenda_discos(draw)
    return _fechar(image, draw, quadro, desenhou)


def _com_coordenada(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None or df.empty or not {"lat", "lng"}.issubset(df.columns):
        return None
    la = pd.to_numeric(df["lat"], errors="coerce")
    lo = pd.to_numeric(df["lng"], errors="coerce")
    sub = df.loc[la.notna() & lo.notna()]
    return None if sub.empty else sub


def _rede(row: pd.Series) -> str:
    rede = row.get("rede")
    sem_rede = rede is None or rede is pd.NA or (isinstance(rede, float) and math.isnan(rede)) or not str(rede).strip()
    return "" if sem_rede else str(rede)


def _discos_sobre(
    image: Image.Image,
    quadro: _Quadro,
    concorrentes: pd.DataFrame | None,
    ultra: pd.DataFrame | None,
    *,
    raio_m: float,
    lat_ref: float,
    logos: bool = True,
) -> ImageDraw.ImageDraw:
    """Pinta os discos (e as logos) sobre `image` e devolve um `draw` novo da imagem composta."""
    # Discos numa camada propria, recortada a caixa do mapa: disco de academia fora do quadro
    # nao pode pintar a legenda.
    camada = Image.new("RGBA", (_W, _H), (0, 0, 0, 0))
    dc = ImageDraw.Draw(camada, "RGBA")
    r_px = quadro.metros_em_px(raio_m, lat_ref)
    # Logos coladas DEPOIS do recorte dos discos, na ordem: independente, rede, Ultra (a bandeira
    # fica por cima na sobreposicao, como no slide Concorrentes).
    marcas: list[tuple[int, float, float, str, tuple[int, int, int]]] = []

    def _pintar(df: pd.DataFrame | None, cor_de: Callable[[pd.Series], tuple[int, int, int]], chave_de: Callable[[pd.Series], str]) -> None:
        if df is None:
            return
        for _, row in df.iterrows():
            px, py = quadro.lnglat(float(row["lng"]), float(row["lat"]))
            c = cor_de(row)
            dc.ellipse([px - r_px, py - r_px, px + r_px, py + r_px], fill=(*c, _ALPHA_DISCO), outline=(*c, _ALPHA_BORDA), width=2)
            chave = chave_de(row)
            marcas.append((2 if chave == "__ultra__" else 1 if chave else 0, px, py, chave, c))

    _pintar(concorrentes, lambda row: _COR_CADEIA if _rede(row) else _COR_INDEPENDENTE, _rede)
    _pintar(ultra, lambda _row: _COR_ULTRA, lambda _row: "__ultra__")

    mascara = Image.new("L", (_W, _H), 0)
    ImageDraw.Draw(mascara).rectangle(quadro.caixa, fill=255)
    recorte = Image.new("RGBA", (_W, _H), (0, 0, 0, 0))
    recorte.paste(camada, (0, 0), mascara)
    image.alpha_composite(recorte)
    draw = ImageDraw.Draw(image, "RGBA")
    left, top, right, bottom = quadro.caixa
    for _ordem, px, py, chave, cor in sorted(marcas, key=lambda t: t[0]):
        if not (left <= px <= right and top <= py <= bottom):
            continue
        if logos:
            _paste_logo_pin(image, int(round(px)), int(round(py)), chave)
        else:
            draw.ellipse([px - 4, py - 4, px + 4, py + 4], fill=(*cor, 255), outline=(255, 255, 255, 255))
    return ImageDraw.Draw(image, "RGBA")


def _legenda_discos(draw: ImageDraw.ImageDraw) -> int:
    yy = _legenda(
        draw,
        "Legenda",
        [
            ("Rede concorrente", (*_COR_CADEIA, 255)),
            ("Academia independente", (*_COR_INDEPENDENTE, 255)),
            ("Unidade Ultra", (*_COR_ULTRA, 255)),
        ],
    )
    _draw_text(draw, (_W - _LEGEND_W + 24, yy + 8), "Cor mais forte =", font=_font(22), fill=_TINTA_SUAVE)
    _draw_text(draw, (_W - _LEGEND_W + 24, yy + 36), "mais raios sobrepostos", font=_font(22), fill=_TINTA_SUAVE)
    return yy


def _quadro_da_cidade(hexes: pd.DataFrame, lat: float | None, lng: float | None) -> _Quadro | None:
    """Enquadramento do mapa de onde crescer: todos os hexagonos da cidade (mais o ponto, se houver)."""
    lats, lngs = _centroides(hexes)
    if not lats:
        return None
    return _Quadro(_bounds_de_pontos(*_com_ponto(lats, lngs, lat, lng)), _W, _H)


def quadro_onde_crescer(
    top: pd.DataFrame,
    hexes_cidade: pd.DataFrame | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> _Quadro | None:
    """Enquadramento do mapa de "Onde crescer": os hexagonos ESCOLHIDOS, com margem.

    Zoom na melhor area (2026-09-17, pedido do Juan): antes o quadro era o municipio inteiro e em
    capital os 5 escolhidos viravam 5 pontinhos verdes. Sem escolhidos desenhaveis, cai no
    enquadramento da cidade.
    """
    lats, lngs = _centroides(top) if top is not None and len(top) else ([], [])
    if lats:
        return _Quadro(
            _bounds_de_pontos(*_com_ponto(lats, lngs, lat, lng), margem=_MARGEM_ONDE_CRESCER), _W, _H
        )
    base = hexes_cidade if hexes_cidade is not None and not hexes_cidade.empty else top
    return _quadro_da_cidade(base, lat, lng) if base is not None and len(base) else None


def render_onde_crescer(
    hexes_cidade: pd.DataFrame | None,
    top: pd.DataFrame,
    *,
    lat: float | None = None,
    lng: float | None = None,
    basemap: bool = True,
) -> bytes | None:
    """A cidade em cinza e os hexagonos escolhidos em destaque, numerados na ordem da lista."""
    if top is None or top.empty or "hex_id" not in top.columns:
        return None
    quadro = quadro_onde_crescer(top, hexes_cidade, lat, lng)
    if quadro is None:
        return None
    image, draw, desenhou = _base(quadro, "Onde crescer", "Top 5 hexagonos da cidade", basemap=basemap)

    if hexes_cidade is not None and not hexes_cidade.empty:
        # Camada propria + alpha_composite: desenhar RGBA direto na imagem RGBA grava o alpha em
        # vez de misturar, e a cidade saia cinza opaco, com cara de area sem dado.
        camada = Image.new("RGBA", (_W, _H), (0, 0, 0, 0))
        dc = ImageDraw.Draw(camada, "RGBA")
        for h in hexes_cidade["hex_id"].astype(str):
            _desenhar_hex(dc, quadro, h, _COR_CIDADE)
        image.alpha_composite(camada)
        draw = ImageDraw.Draw(image, "RGBA")

    # Na escala de uma capital cada hexagono tem ~30 px: a borda grossa alarga a mancha verde e o
    # selo vai para CIMA do hexagono -- no centro ele cobria o hexagono inteiro (pagina toda cinza).
    selos: list[tuple[int, float, float, float]] = []
    for _, row in top.iterrows():
        c = _desenhar_hex(draw, quadro, str(row["hex_id"]), (*_COR_TOP, 255), outline=(*_COR_TOP, 255), width=8)
        if c is None:
            continue
        borda = _poligono_hex(str(row["hex_id"])) or []
        topo = min((quadro.lnglat(g, t)[1] for t, g in borda), default=c[1])
        selos.append((int(row.get("posicao", len(selos) + 1)), c[0], c[1], topo))

    _pin_do_ponto(draw, quadro, lat, lng, 1.3)

    fonte = _font(20)
    r = 14
    for pos, px, _py, topo in selos:
        sy = topo - 4 - r
        draw.line([(px, topo), (px, sy)], fill=(*_COR_TOP_BORDA, 255), width=3)
        draw.ellipse([px - r, sy - r, px + r, sy + r], fill=(*_COR_TOP_BORDA, 255), outline=(255, 255, 255, 255), width=2)
        txt = str(pos)
        _draw_text(draw, (int(px - _text_width(draw, txt, fonte) / 2), int(sy - 12)), txt, font=fonte, fill=(255, 255, 255))

    _legenda(
        draw,
        "Legenda",
        [("Hexagono escolhido", (*_COR_TOP, 255)), ("Demais da cidade", _COR_CIDADE)],
    )
    return _fechar(image, draw, quadro, desenhou)
