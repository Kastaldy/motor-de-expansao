from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
from fpdf import FPDF
from PIL import Image, ImageOps

from motor_expansao.api.maps_geocoder import build_search_url
from motor_expansao.dashboard.censo_point import METODO_RELATORIO_PONTUAL_CENSITARIO

# Cabecalhos canonicos das 6 paginas do template Ultra. Renderizam em latin-1 (core font
# Helvetica do fpdf2), que cobre integralmente os acentos portugueses -- o que e PROIBIDO e
# tipografia fora de latin-1 (travessao/bullet/seta/reticencias/aspas curvas/(c)), que vira
# "?" silenciosamente via _ascii(..., errors="replace").
# Cada string PRECISA aparecer nos bytes crus do PDF (compressao desativada no writer).
# Ordem das paginas (BLK-RELPON-01): os 3 choropleths (Densidade/Renda/Score) foram
# CONSOLIDADOS em um unico slide "Mapas de calor" (tira 1x3 lado a lado), reduzindo o PDF
# de 7 para 5 paginas: Capa -> Mapas de calor -> Concorrentes -> Big Numbers -> Realizacao.
# BLK-RELPON-07: nova pagina "Perfil do Bairro/Distrito" inserida entre Concorrentes e Big
# Numbers, levando o PDF de 5 para 6 paginas: Capa -> Mapas de calor -> Concorrentes ->
# Perfil do Bairro/Distrito -> Big Numbers -> Realizacao.
PDF_SECTION_HEADERS = (
    "Relatório Pontual Censitário",
    "Mapas de calor",
    "Concorrentes",
    "Perfil do Bairro/Distrito",
    "Big Numbers",
    "Realização",
)

# Camadas de mapa (chave canonica -> titulo da pagina de mapa no PDF). Ordem fixa.
# `score` (BLK-CENSO-03-FU5) e o choropleth de score censitario COM legenda; a camada
# `concorrentes` e o mapa SO de pins (basemap + pins Ultra/concorrentes + ponto central),
# SEM choropleth — renderizada na pagina de Concorrentes (`_competitors_page`).
# BLK-RELPON-05 (faixa REVERTIDA para os agregados do raio pelo BLK-RELPON-06/D1): os
# PNGs de densidade/renda/score que chegam aqui ja trazem "assada" a faixa superior com
# o valor do raio de 1.5 km (produzida em
# `censo_map.render_mapas_censitarios_combinados`/`_render_camada`); este modulo recebe
# `mapas: dict[str, bytes]` ja pronto e so embute os bytes (`_mapas_calor_page`/
# `_classico_mapas_calor_page` via `_draw_maps_grid`/`_map_grid_cells`), sem nenhuma
# mudanca de logica. As fontes maiores do BLK-RELPON-06 (D4) tambem vem embutidas nos
# bytes do PNG (UM unico render p/ dashboard/PDF/API) -- nada muda neste modulo.
MAP_LAYER_TITLES: tuple[tuple[str, str], ...] = (
    ("densidade", "População - Densidade"),
    ("renda", "Renda per capita"),
    ("score", "Score censitário"),
    ("renda_domiciliar", "Renda média domiciliar"),
    ("concorrentes", "Concorrentes e Ultra"),
)

CSV_SETOR_COLUMNS = [
    "cod_setor",
    "uf",
    "cod_municipio",
    "nome_municipio",
    "area_setor_m2",
    "area_intersecao_m2",
    "peso_area_setor",
    "pop_total_setor_2022",
    "pop_estimada_intersecao",
    "renda_per_capita_setor_2022_calibrada",
    "densidade_pop_setor_hab_km2",
    "score_setor_2022_calibrado",
    "flag_renda_disponivel",
    "flag_geometria_valida",
    "qualidade_join_uf",
]

# Paleta Ultra (RGB 0..255). Turquesa #00A79D, magenta #C23C8E, branco-gelo #F8F8F8.
ULTRA_TURQUESA = (0, 167, 157)
ULTRA_MAGENTA = (194, 60, 142)
ULTRA_BRANCO_GELO = (248, 248, 248)
_BRANCO = (255, 255, 255)
_CINZA_TEXTO = (60, 60, 60)

# BLK-RELPON-08 (D3/Q4): metas do semaforo de cor dos 8 cards do Big Numbers. Verde quando o
# valor bate a meta; vermelho quando nao bate; neutro quando "n/d" (Q2, indecidivel). Constantes
# nomeadas e auditaveis (nao hardcoded inline dentro de `_big_numbers_page`).
_META_POP_TOTAL_RAIO = 10_000.0
_META_RENDA_PER_CAPITA_MEDIA_RAIO = 1_500.0
# Renda media domiciliar TOTAL (com uplift): alvo ~C1 GeoFusion (fase seguinte, ADITIVO).
_META_RENDA_DOMICILIAR_TOTAL_RAIO = 6_200.0
_META_DOMICILIOS_TOTAL_RAIO = 3_000.0
_META_SCORE_SETOR_MEDIO = 60.0
_META_SAM_FITNESS_POTENCIAL = 2_000.0
_META_RESIDUAL_FITNESS_DISPONIVEL = 2_000.0

# Geometria do grid 4x2 do Big Numbers (8 cards; o card "Score censitario medio" foi removido do
# PDF por pedido de Felipe 2026-07-17 — segue em result/CSV). A pagina e' FIXA 960x540 com
# auto_page_break OFF: as 2 linhas + a nota precisam caber ACIMA do rodape (y=_PAGE_H-22). Constantes ao nivel
# de modulo para o invariante ser testavel (test_censo_report) — nao locais dentro da funcao.
# Invariante garantido: top + rows*card_h + (rows-1)*gap + nota <= _PAGE_H - 22.
_BIG_NUMBERS_TOP = 62.0
_BIG_NUMBERS_GAP = 12.0
_BIG_NUMBERS_CARD_H = 132.0
_BIG_NUMBERS_ROWS = 2
_BIG_NUMBERS_COLS = 4

# Paleta pastel do semaforo (Q3): fundo claro o bastante para preservar contraste com o
# rotulo/valor em cinza-escuro (45,45,45)/(40,40,40) e com a borda fina (225,225,228) ja
# existente do card. Neutro reusa a familia de cinza-claro de `_PERFIL_DIVISOR_RGB` (232,233,237)
# para ficar visualmente distinto do branco puro do card sem meta aplicavel.
_CARD_VERDE_RGB = (205, 236, 217)
_CARD_VERMELHO_RGB = (248, 209, 209)
_CARD_NEUTRO_RGB = (232, 233, 237)

# BLK-RELPON-07 (refino visual "Microarea" GeoFusion): painel vertical do Perfil do
# Bairro/Distrito. Moldura turquesa arredondada + cartao branco + metricas empilhadas
# (icone + rotulo cinza + valor grande azul-marinho). SO estilo/geometria — nao muda os
# 4 blocos, os valores, o metodo de renda nem a contagem de paginas.
_PERFIL_VALOR_RGB = (38, 50, 71)  # azul-marinho escuro dos numeros (como no painel de referencia)
_PERFIL_ROTULO_RGB = (120, 126, 138)  # cinza medio dos rotulos das metricas
_PERFIL_INFO_RGB = (206, 208, 214)  # cinza claro do circulo "i" decorativo
_PERFIL_DIVISOR_RGB = (232, 233, 237)  # linha divisoria fina entre metricas

# Atribuicao de tiles (DEC-004) — sempre presente no rodape de cada pagina de mapa/credito.
_ATRIBUICAO_TILES = "(c) OpenStreetMap, (c) CARTO"
_CREDITO_ULTRA = "Relatório gerado pelo Motor de Expansão - Ultra Academia"

# Nomes default dos assets de branding (gitignored; ficam no host/volume `data/ultra`).
_ASSET_CAPA = "relatorio_capa_bg.png"
_ASSET_CONTEUDO = "relatorio_conteudo_bg.png"
_ASSET_LOGO = "logo_ultra.png"
_ASSET_ICONE = "icone_ultra.png"
_DEFAULT_ULTRA_DIR = Path("data/ultra")

# Dimensoes do slide 16:9 widescreen em pontos (13.333in x 7.5in = 960 x 540 pt).
# Proporcao casa com os fundos do .pptx (capa 1360x763, conteudo 783x437) -> sem distorcao.
_PAGE_W = 960.0
_PAGE_H = 540.0

# Marca d'agua diagonal de rastreabilidade (BLK-EST-01) — embutida em TODAS as paginas com
# compressao OFF: o texto vai em claro no content stream (BT...ET), nao removivel trivialmente
# (sem /Annot separavel). `solicitante=None` -> so "Ultra Academia". ASCII-safe (passa por _ascii).
_WATERMARK_BASE = "Ultra Academia"
_WATERMARK_RGB = (120, 120, 120)
_WATERMARK_RGB_COVER = (255, 255, 255)
_WATERMARK_ALPHA = 0.65
_WATERMARK_ANGLE = 0.0
_WATERMARK_FONT_PT = 10
_WATERMARK_MARGIN = 20.0

# ---------------------------------------------------------------------------
# Variante "Apresentacao Classica Ultra" (BLK-EST-05): estetica GeoFusion antiga
# sobre o motor censitario novo. Funcao publica DEDICADA
# (`gerar_pdf_relatorio_pontual_classico`) — NAO ramifica o gerador recente.
# Cores: REUSAR ULTRA_TURQUESA/ULTRA_MAGENTA (decisao do gate humano Q1).
# ---------------------------------------------------------------------------
_CLASSICO_MARGIN = 20.0
_CLASSICO_CORNER_RADIUS = 16.0
_CLASSICO_BAND_H = 58.0
# Banda magenta de rodape full-width, encostada na borda inferior da pagina
# (offset 0 = flush-baixo; estava 13 pt acima e subia sobre o credito do rodape).
_CLASSICO_MAGENTA_BANDA_H = 13.0
_CLASSICO_MAGENTA_OFFSET = 0.0
# Meses por extenso (ASCII-safe) para a data de geracao e o mes/ano da capa classica.
_MESES_PT = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


@dataclass(frozen=True)
class RelatorioCensitarioDownloadPayloads:
    csv_bytes: bytes
    csv_filename: str
    pdf_bytes: bytes
    pdf_filename: str


def _setores_from_result(result: dict[str, Any] | pd.DataFrame) -> pd.DataFrame:
    if isinstance(result, pd.DataFrame):
        setores = result
    else:
        setores = result.get("setores_intersectados", pd.DataFrame())
    if setores is None or setores.empty:
        return pd.DataFrame(columns=CSV_SETOR_COLUMNS)
    columns = [column for column in CSV_SETOR_COLUMNS if column in setores.columns]
    extra = [column for column in setores.columns if column not in columns and not column.startswith("geometry")]
    return setores.loc[:, columns + extra].copy()


def gerar_csv_setores_censitarios(result: dict[str, Any] | pd.DataFrame) -> bytes:
    """Gera CSV em memoria para a tabela auditavel de setores intersectados.

    INALTERADO neste ciclo (BLK-CENSO-02): contrato do CSV preservado.
    """
    setores = _setores_from_result(result)
    return setores.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")


def _format_number(value: Any, decimals: int = 0, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "n/d"
    number = float(value)
    if decimals <= 0:
        text = f"{number:,.0f}".replace(",", ".")
    else:
        text = f"{number:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text}{suffix}"


def _point_name(result: dict[str, Any]) -> str:
    lat = result.get("lat")
    lng = result.get("lng")
    if lat is None or lng is None:
        return "ponto"
    return f"{float(lat):.5f}_{float(lng):.5f}".replace("-", "m").replace(".", "p")


def _ascii(text: str) -> str:
    """Reduz a latin-1/ASCII seguro para o core font Helvetica do fpdf2."""
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _watermark_text(solicitante: str | None) -> str:
    """Texto da marca d'agua: "Ultra Academia" ou "Ultra Academia | {solicitante}".

    `solicitante` None/vazio -> so a base (default seguro, sem PII). ASCII-safe.
    """
    if solicitante is None or not solicitante.strip():
        return _ascii(_WATERMARK_BASE)
    return _ascii(f"{_WATERMARK_BASE} | {solicitante.strip()}")


# ---------------------------------------------------------------------------
# Assets de branding (offline-safe; fallback gracioso para cor solida)
# ---------------------------------------------------------------------------


def _load_branding_assets(ultra_dir: Path | str | None) -> dict[str, bytes | None]:
    """Carrega assets de branding de ``ultra_dir`` com fallback gracioso.

    Em QUALQUER falha (arquivo ausente, IO, decode) retorna ``None`` para o asset
    — SEM excecao. Garante PDF valido com fundo de cor solida em CI/deploy limpo.
    """
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
            # Valida que e uma imagem decodificavel antes de embutir.
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


# ---------------------------------------------------------------------------
# Writer fpdf2
# ---------------------------------------------------------------------------


class _UltraPDF(FPDF):
    """FPDF com compressao desativada (auditabilidade anti-PII + asserts de texto cru)."""

    def __init__(self) -> None:
        # Slide 16:9 widescreen (960x540 pt). format=(540,960)+orientation=L -> w=960, h=540.
        super().__init__(orientation="L", unit="pt", format=(540, 960))
        # PDF 1.4 para continuidade com os asserts historicos (%PDF-1.4) e leitores antigos.
        self.pdf_version = "1.4"
        self.set_compression(False)
        self.set_auto_page_break(False)
        self.set_margins(0, 0, 0)


def _draw_full_page_background(
    pdf: _UltraPDF,
    image_bytes: bytes | None,
    solid_rgb: tuple[int, int, int],
) -> None:
    """Desenha fundo full-page: imagem se disponivel, senao retangulo de cor solida."""
    if image_bytes is not None:
        try:
            pdf.image(BytesIO(image_bytes), x=0, y=0, w=_PAGE_W, h=_PAGE_H)
            return
        except Exception:
            pass
    pdf.set_fill_color(*solid_rgb)
    pdf.rect(0, 0, _PAGE_W, _PAGE_H, style="F")


def _tema_bicolor(ordinal: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """(primary, secondary) por pagina de CONTEUDO (ordinal >= 1), alternando o tom principal.

    Pedido Vinicius (2026-06-29): as paginas devem alternar entre turquesa e magenta como cor
    principal. Pagina impar -> turquesa primaria / magenta acento; par -> magenta primaria /
    turquesa acento. Aplica-se SO ao chrome decorativo (faixa de titulo + cabecalho/acento
    decorativo principal). Cores SEMANTICAS (Ultra=turquesa, concorrente=magenta nos bullets)
    NAO entram nessa troca. READ-ONLY sobre o M1.
    """
    if ordinal % 2 == 1:
        return ULTRA_TURQUESA, ULTRA_MAGENTA
    return ULTRA_MAGENTA, ULTRA_TURQUESA


def _draw_title_band(pdf: _UltraPDF, title: str, *, rgb: tuple[int, int, int] = ULTRA_TURQUESA) -> None:
    """Faixa de titulo turquesa no topo da pagina de conteudo (largura total 16:9)."""
    # D1=B (BLK-EST-02): banda mais alta (56 pt) e titulo 22 pt p/ hierarquia "executiva".
    band_h = 56.0
    pdf.set_fill_color(*rgb)
    pdf.rect(0, 0, _PAGE_W, band_h, style="F")
    pdf.set_text_color(*_BRANCO)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_xy(36, 16)
    pdf.cell(_PAGE_W - 72, 24, _ascii(title))


def _draw_footer(pdf: _UltraPDF, *, with_attribution: bool = True) -> None:
    """Rodape com credito Ultra e atribuicao de tiles."""
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_xy(36, _PAGE_H - 22)
    text = _CREDITO_ULTRA
    if with_attribution:
        text = f"{text}   |   {_ATRIBUICAO_TILES}"
    pdf.cell(_PAGE_W - 72, 12, _ascii(text))


# ---------------------------------------------------------------------------
# Slide consolidado "Mapas de calor" (BLK-RELPON-01): os 3 choropleths
# (densidade/renda/score) em UMA tira horizontal 1x3, lado a lado, sem
# sobreposicao. Cada PNG e embutido SEPARADAMENTE (nao pre-composto), com
# legenda embutida (D3). Fallback textual por camada ausente (offline-safe).
# ---------------------------------------------------------------------------
# Mensagem literal de fallback por camada de mapa faltante (usada pelas grades 1x3).
_MAPA_INDISPONIVEL = "Mapa indisponível para esta camada."


_MAP_GRID_COLS = 2
_MAP_GRID_ROWS = 2


def _map_grid_cells(
    top: float, bottom: float, margin_x: float, gap: float
) -> list[tuple[float, float, float, float]]:
    """Geometria PURA das 4 celulas do grid 2x2 (x, y, w, h), em ordem row-major. Testavel
    sem gerar PDF; compartilhada pelas variantes recente e classica (variam so top/margem).

    Largura util (`_PAGE_W - 2*margin_x - (cols-1)*gap`) dividida em `cols` colunas iguais;
    altura util (`bottom - top - (rows-1)*gap`) em `rows` linhas iguais.
    """
    cols, rows = _MAP_GRID_COLS, _MAP_GRID_ROWS
    usable_w = _PAGE_W - 2.0 * margin_x - (cols - 1) * gap
    cell_w = usable_w / cols
    usable_h = (bottom - top) - (rows - 1) * gap
    cell_h = usable_h / rows
    cells: list[tuple[float, float, float, float]] = []
    for r in range(rows):
        for c in range(cols):
            x = margin_x + c * (cell_w + gap)
            y = top + r * (cell_h + gap)
            cells.append((x, y, cell_w, cell_h))
    return cells


def _map_grid_cells_packed(
    aspect: float, *, top: float, bottom: float, gap: float
) -> list[tuple[float, float, float, float]]:
    """Celulas 2x2 com a PROPORCAO `aspect` (largura/altura), maximizadas em altura e
    EMPACOTADAS (coladas, so o `gap`) e centralizadas -> mapas maiores/retangulares e sem o
    vao branco (letterbox) entre eles. Geometria pura, testavel sem PDF."""
    cols, rows = _MAP_GRID_COLS, _MAP_GRID_ROWS
    h_avail = bottom - top
    cell_h = (h_avail - (rows - 1) * gap) / rows
    cell_w = cell_h * aspect
    max_total_w = _PAGE_W - 2.0 * 20.0  # margem lateral minima
    if cols * cell_w + (cols - 1) * gap > max_total_w:
        cell_w = (max_total_w - (cols - 1) * gap) / cols
        cell_h = cell_w / aspect
    total_w = cols * cell_w + (cols - 1) * gap
    total_h = rows * cell_h + (rows - 1) * gap
    x0 = (_PAGE_W - total_w) / 2.0
    y0 = top + (h_avail - total_h) / 2.0
    return [
        (x0 + c * (cell_w + gap), y0 + r * (cell_h + gap), cell_w, cell_h)
        for r in range(rows)
        for c in range(cols)
    ]


def _draw_maps_grid(
    pdf: _UltraPDF,
    pngs: list[bytes | None],
    *,
    top: float,
    bottom: float,
    margin_x: float,
    gap: float,
    pack: bool = False,
) -> list[tuple[float, float, float, float]]:
    """Desenha os 4 PNGs [densidade, renda, score, renda_domiciliar] num grid 2x2 sem sobreposicao.

    Cada PNG e escalado para caber na sua celula preservando proporcao (`min(w,h)`) e
    centralizado dentro dela; camada `None` -> texto de fallback centralizado na celula.
    Os PNGs sao embutidos SEPARADAMENTE (nao pre-compostos) para preservar a contagem
    de `/Subtype /Image`. Retorna os bounding boxes efetivamente ocupados por cada mapa
    (imagem desenhada) ou a propria celula quando cai no fallback — usado pelo teste de
    nao-sobreposicao.

    `pack=True` (mapas de calor): as celulas assumem a PROPORCAO do proprio mapa (do 1o PNG
    valido) e sao empacotadas/centralizadas -> mapas maiores, retangulares e SEM o vao branco.
    """
    if pack:
        dims_ref = next((_png_dimensions(p) for p in pngs if p), None)
        aspect = (dims_ref[0] / dims_ref[1]) if dims_ref else (1000.0 / 760.0)
        cells = _map_grid_cells_packed(aspect, top=top, bottom=bottom, gap=gap)
    else:
        cells = _map_grid_cells(top, bottom, margin_x, gap)
    boxes: list[tuple[float, float, float, float]] = []
    for png, (cx, cy, cw, ch) in zip(pngs, cells, strict=False):
        dims = _png_dimensions(png) if png else None
        if png and dims is not None:
            img_w, img_h = dims
            scale = min(cw / img_w, ch / img_h)
            draw_w = img_w * scale
            draw_h = img_h * scale
            x = cx + (cw - draw_w) / 2.0
            y = cy + (ch - draw_h) / 2.0
            try:
                pdf.image(BytesIO(png), x=x, y=y, w=draw_w, h=draw_h)
                boxes.append((x, y, draw_w, draw_h))
                continue
            except Exception:
                pass
        # Fallback: camada ausente ou imagem invalida -> texto centralizado na celula.
        pdf.set_text_color(*_CINZA_TEXTO)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_xy(cx, cy + ch / 2.0 - 8.0)
        pdf.multi_cell(cw, 14, _ascii(_MAPA_INDISPONIVEL), align="C")
        boxes.append((cx, cy, cw, ch))
    return boxes


def _mapas_calor_page(
    pdf: _UltraPDF,
    layers: dict[str, bytes],
    assets: dict[str, bytes | None],
    *,
    primary: tuple[int, int, int] = ULTRA_TURQUESA,
) -> list[tuple[float, float, float, float]]:
    """Slide unico "Mapas de calor" (template recente): faixa de titulo + grid 2x2 + rodape.

    BLK-RELPON-05 (faixa REVERTIDA para o raio pelo BLK-RELPON-06/D1): a faixa
    "<Variavel> no raio: <valor>" de cada mapa ja vem desenhada nos bytes de `layers`
    (ver comentario acima de `MAP_LAYER_TITLES`); nenhuma mudanca de logica necessaria
    nesta funcao. Grid 2x2: [densidade, renda, score, renda_domiciliar].
    """
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, "Mapas de calor", rgb=primary)
    boxes = _draw_maps_grid(
        pdf,
        [
            layers.get("densidade"),
            layers.get("renda"),
            layers.get("score"),
            layers.get("renda_domiciliar"),
        ],
        top=58.0,
        bottom=_PAGE_H - 22.0,
        margin_x=20.0,
        gap=10.0,
        pack=True,
    )
    _draw_footer(pdf, with_attribution=True)
    return boxes


# ---------------------------------------------------------------------------
# Pagina de FOTOS do imovel (BLK-RELVIAB-01): upload do operador, ate 2 fotos
# retangulares lado a lado, dimensoes adaptaveis (fit-within-box preservando
# proporcao). READ-ONLY sobre o M1; saida OPCIONAL (so entra se `fotos` != None).
# Anti-PII: bytes normalizados em memoria, nada persistido.
# ---------------------------------------------------------------------------
_FOTOS_MAX = 2  # MVP: no maximo 2 fotos no PDF.
_FOTO_LADO_MAX = 1600  # downscale: maior lado <= 1600 px (capa o tamanho do PDF).
_FOTO_JPEG_QUALIDADE = 82  # recompressao JPEG.
_FOTOS_PAGE_TITLE = "Imóvel - Fotos"
_SEM_FOTO_VALIDA = "Nenhuma foto valida para exibir."
_FOTO_BORDA_LARANJA = (245, 130, 30)  # laranja Ultra (borda da foto)
_FOTO_BORDA_LARGURA = 5.0  # espessura (pt) da borda ao redor de cada foto
# Cores da borda das fotos, alternadas por foto: laranja Ultra e magenta (ja no PDF).
_FOTO_BORDA_CORES = (_FOTO_BORDA_LARANJA, ULTRA_MAGENTA)


def _normalizar_foto(
    raw: bytes,
    *,
    lado_max: int = _FOTO_LADO_MAX,
    qualidade: int = _FOTO_JPEG_QUALIDADE,
) -> bytes | None:
    """Normaliza uma foto de upload para embutir no PDF (BLK-RELVIAB-01).

    - corrige a orientacao EXIF (foto de celular sai em pe, nao deitada);
    - achata para RGB (descarta alpha/paleta sobre fundo branco);
    - downscale para `lado_max` no maior lado (fotos de celular tem varios MB);
    - recomprime como JPEG `qualidade` para capar o tamanho do PDF.

    Retorna `None` em qualquer falha (formato invalido etc.) -> fallback gracioso.
    Puro/deterministico e sem I/O de disco (so BytesIO em memoria) -> loop-safe.
    """
    try:
        with Image.open(BytesIO(raw)) as src:
            oriented = ImageOps.exif_transpose(src)
            if oriented.mode not in ("RGB", "L"):
                flat = Image.new("RGB", oriented.size, (255, 255, 255))
                flat.paste(oriented.convert("RGB"), mask=oriented.convert("RGBA").split()[-1])
            else:
                flat = oriented.convert("RGB")
            flat.thumbnail((lado_max, lado_max), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            flat.save(buffer, format="JPEG", quality=qualidade, optimize=True)
            return buffer.getvalue()
    except Exception:
        return None


_FOTO_ASPECT = 1.5  # paisagem 3:2 (evita o "quadrado" e reduz o tamanho da foto)
_FOTO_CELL_W_MAX = 390.0  # paisagem, um pouco maior que 345 (pedido Felipe 2026-07-17)


def _fotos_cells(n: int) -> list[tuple[float, float, float, float]]:
    """Geometria PURA das celulas para `n` fotos (1 ou 2): retangulos PAISAGEM 3:2,
    reduzidos (~20% menores) e CENTRALIZADOS na area de conteudo. Testavel sem PDF."""
    cols = max(1, min(n, _FOTOS_MAX))
    gap = 24.0
    area_top, area_bottom, margin_x = 56.0, _PAGE_H - 26.0, 40.0
    max_w = (_PAGE_W - 2.0 * margin_x - (cols - 1) * gap) / cols
    cell_w = min(_FOTO_CELL_W_MAX, max_w)
    cell_h = cell_w / _FOTO_ASPECT
    total_w = cols * cell_w + (cols - 1) * gap
    x0 = (_PAGE_W - total_w) / 2.0
    y0 = area_top + (area_bottom - area_top - cell_h) / 2.0
    return [(x0 + c * (cell_w + gap), y0, cell_w, cell_h) for c in range(cols)]


def _recortar_cover(raw: bytes, ratio_wh: float) -> bytes | None:
    """Center-crop (estilo "cover") da foto para a proporcao `ratio_wh` (largura/altura).

    Padroniza o tamanho: TODAS as fotos passam a ocupar slots IDENTICOS, sem distorcer —
    recorta o excesso do lado mais comprido (em vez de esticar ou deixar borda/letterbox).
    Retorna JPEG ou None em falha. READ-ONLY sobre o M1; so BytesIO em memoria.
    """
    try:
        with Image.open(BytesIO(raw)) as src:
            img = src.convert("RGB")
            w, h = img.size
            atual = w / h
            if atual > ratio_wh:  # muito larga -> corta as laterais
                novo_w = max(1, int(round(h * ratio_wh)))
                x0 = (w - novo_w) // 2
                box = (x0, 0, x0 + novo_w, h)
            else:  # muito alta -> corta topo/base
                novo_h = max(1, int(round(w / ratio_wh)))
                y0 = (h - novo_h) // 2
                box = (0, y0, w, y0 + novo_h)
            recorte = img.crop(box)
            buffer = BytesIO()
            recorte.save(buffer, format="JPEG", quality=_FOTO_JPEG_QUALIDADE, optimize=True)
            return buffer.getvalue()
    except Exception:
        return None


def _fotos_imovel_page(
    pdf: _UltraPDF,
    fotos: list[bytes],
    assets: dict[str, bytes | None],
    *,
    primary: tuple[int, int, int] = ULTRA_TURQUESA,
) -> None:
    """Pagina de fotos do imovel: faixa de titulo + ate 2 fotos com TAMANHO FIXO + rodape.

    Cada foto e normalizada (`_normalizar_foto`) e recortada (`_recortar_cover`) para a
    proporcao da celula, preenchendo-a por inteiro. Assim as fotos ficam com o MESMO tamanho
    (nenhuma diferente da outra), sem distorcer — recorta o excesso em vez de esticar. Cada
    foto ganha uma BORDA (laranja Ultra / magenta, alternadas). Fotos invalidas sao
    descartadas; se nenhuma sobreviver, desenha um aviso gracioso. READ-ONLY M1.
    """
    normalizadas = [n for n in (_normalizar_foto(f) for f in fotos[:_FOTOS_MAX]) if n]

    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, _FOTOS_PAGE_TITLE, rgb=primary)

    if not normalizadas:
        pdf.set_text_color(*_CINZA_TEXTO)
        pdf.set_font("Helvetica", "", 12)
        pdf.set_xy(40, _PAGE_H / 2.0 - 8.0)
        pdf.multi_cell(_PAGE_W - 80, 16, _ascii(_SEM_FOTO_VALIDA), align="C")
        _draw_footer(pdf, with_attribution=False)
        return

    prev_lw = pdf.line_width
    for idx, (png, (cx, cy, cw, ch)) in enumerate(
        zip(normalizadas, _fotos_cells(len(normalizadas)), strict=False)
    ):
        # Recorta para a proporcao da celula e preenche a celula inteira -> tamanho fixo/igual.
        recorte = _recortar_cover(png, cw / ch)
        alvo = recorte if recorte is not None else png
        try:
            pdf.image(BytesIO(alvo), x=cx, y=cy, w=cw, h=ch)
        except Exception:
            pass
        # Borda por cima da foto (laranja Ultra / magenta, alternadas).
        pdf.set_draw_color(*_FOTO_BORDA_CORES[idx % len(_FOTO_BORDA_CORES)])
        pdf.set_line_width(_FOTO_BORDA_LARGURA)
        pdf.rect(cx, cy, cw, ch, style="D")
    pdf.set_line_width(prev_lw)  # restaura p/ nao engrossar bordas das paginas seguintes
    _draw_footer(pdf, with_attribution=False)


# ---------------------------------------------------------------------------
# Pagina de VISTA AEREA (satelite Esri) — porte do BLK-SAT-01 (main). Pagina
# PROPRIA (nao a de fotos do imovel) para nao ocupar as 2 vagas de upload. Saida
# OPCIONAL (so entra se `foto_satelite` != None e a imagem for valida). O PNG e
# gerado pelo chamador via `censo_map.render_foto_satelite_ponto` (fallback gracioso
# -> None sem chave/rede). READ-ONLY sobre o M1; licenca Esri (credito embutido no PNG).
# ---------------------------------------------------------------------------
_SATELITE_PAGE_TITLE = "Imóvel - Vista aérea"


def _foto_satelite_cell_grande() -> tuple[float, float, float, float]:
    """Celula 3:2 CENTRADA ocupando a area de conteudo inteira (altura manda).

    Para quando a vista aerea e a UNICA imagem da pagina (sem upload de fotos do imovel).
    """
    area_top, area_bottom, margin_x = 56.0, _PAGE_H - 26.0, 40.0
    pad_v = 14.0
    h = (area_bottom - area_top) - 2.0 * pad_v
    w = h * _FOTO_ASPECT
    max_w = _PAGE_W - 2.0 * margin_x
    if w > max_w:                      # se estourar a largura, a largura passa a mandar
        w, h = max_w, max_w / _FOTO_ASPECT
    x0 = (_PAGE_W - w) / 2.0
    y0 = area_top + ((area_bottom - area_top) - h) / 2.0
    return x0, y0, w, h


def _foto_satelite_page(
    pdf: _UltraPDF,
    foto: bytes,
    assets: dict[str, bytes | None],
    *,
    primary: tuple[int, int, int] = ULTRA_TURQUESA,
    grande: bool = False,
) -> None:
    """Pagina da VISTA AEREA: faixa de titulo + 1 foto + rodape.

    `grande` dimensiona a foto: False (default) usa a mesma celula de `_fotos_cells(1)`;
    True ocupa a area de conteudo inteira (quando a vista aerea e a unica imagem).
    Foto invalida -> a pagina NAO e criada.
    """
    png = _normalizar_foto(foto)
    if not png:
        return

    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, _SATELITE_PAGE_TITLE, rgb=primary)

    cx, cy, cw, ch = _foto_satelite_cell_grande() if grande else _fotos_cells(1)[0]
    recorte = _recortar_cover(png, cw / ch)
    try:
        pdf.image(BytesIO(recorte if recorte is not None else png), x=cx, y=cy, w=cw, h=ch)
    except Exception:
        pass

    prev_lw = pdf.line_width
    pdf.set_draw_color(*_FOTO_BORDA_LARANJA)
    pdf.set_line_width(_FOTO_BORDA_LARGURA)
    pdf.rect(cx, cy, cw, ch, style="D")
    pdf.set_line_width(prev_lw)
    _draw_footer(pdf, with_attribution=False)


# ---------------------------------------------------------------------------
# Pagina de INFORMACOES do imovel (BLK-RELVIAB-02): dados do imovel em cards +
# observacoes. Saida OPCIONAL (so entra se `info_imovel` != None); campos
# ausentes -> "n/d" gracioso. READ-ONLY sobre o M1; anti-PII (nada persistido).
# ---------------------------------------------------------------------------
_INFO_IMOVEL_PAGE_TITLE = "Imóvel - Informações"
# (chave no dict, rotulo exibido, tipo de formatacao).
_INFO_IMOVEL_CAMPOS: tuple[tuple[str, str, str], ...] = (
    ("metragem_m2", "Metragem (m2)", "num"),
    ("aluguel_pedido", "Aluguel pedido (mês)", "brl"),
    ("valor_venda", "Valor de venda", "brl"),
    ("pe_direito_m", "Pé-direito (m)", "num2"),
    ("vagas", "Vagas", "num"),
    ("tipo_imovel", "Tipo do imóvel", "texto"),
)


def _info_valor(value: Any, kind: str) -> str:
    """Formata um valor de info do imovel; ausente/vazio -> 'n/d'; nao-numerico seguro."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return "n/d"
    try:
        if kind == "brl":
            return "R$ " + _format_number(value, 2)
        if kind == "num":
            return _format_number(value, 0)
        if kind == "num2":
            return _format_number(value, 2)
    except (TypeError, ValueError):
        return str(value)
    return str(value)


def _info_imovel_page(
    pdf: _UltraPDF,
    info_imovel: dict[str, Any],
    assets: dict[str, bytes | None],
    *,
    primary: tuple[int, int, int] = ULTRA_TURQUESA,
    secondary: tuple[int, int, int] = ULTRA_MAGENTA,
) -> None:
    """Pagina de informacoes do imovel: endereco + cards 3x2 + observacoes. READ-ONLY M1."""
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, _INFO_IMOVEL_PAGE_TITLE, rgb=primary)

    endereco = str(info_imovel.get("endereco") or info_imovel.get("rotulo") or "").strip()
    y_cards = 72.0
    if endereco:
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_xy(36, 66)
        pdf.multi_cell(_PAGE_W - 72, 18, _ascii(endereco[:110]))
        y_cards = 100.0

    margin_x, gap, cols = 36.0, 12.0, 3
    card_w = (_PAGE_W - 2 * margin_x - (cols - 1) * gap) / cols
    card_h = 120.0
    accents = [primary, secondary]
    for index, (chave, rotulo, kind) in enumerate(_INFO_IMOVEL_CAMPOS):
        col, row = index % cols, index // cols
        x = margin_x + col * (card_w + gap)
        y = y_cards + row * (card_h + gap)
        pdf.set_fill_color(*_CARD_NEUTRO_RGB)
        pdf.rect(x, y, card_w, card_h, style="F")
        pdf.set_draw_color(225, 225, 228)
        pdf.rect(x, y, card_w, card_h, style="D")
        pdf.set_fill_color(*accents[index % len(accents)])
        pdf.rect(x, y, card_w, 6.0, style="F")
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_xy(x + 14, y + 20)
        pdf.multi_cell(card_w - 28, 14, _ascii(rotulo))
        pdf.set_text_color(40, 40, 40)
        pdf.set_font("Helvetica", "B", 22)
        pdf.set_xy(x + 14, y + 66)
        pdf.multi_cell(card_w - 28, 24, _ascii(_info_valor(info_imovel.get(chave), kind)))

    observacoes = str(info_imovel.get("observacoes") or "").strip()
    if observacoes:
        y_obs = y_cards + 2 * (card_h + gap) + 6
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_xy(margin_x, y_obs)
        pdf.cell(_PAGE_W - 2 * margin_x, 14, _ascii("Observações"))
        pdf.set_text_color(*_CINZA_TEXTO)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_xy(margin_x, y_obs + 16)
        pdf.multi_cell(_PAGE_W - 2 * margin_x, 13, _ascii(observacoes[:600]))
    _draw_footer(pdf, with_attribution=False)


# ---------------------------------------------------------------------------
# Paginas de VIABILIDADE (BLK-RELVIAB-04): slide de NUMEROS (estilo Big Numbers)
# do motor `viabilidade_ponto` + slide de GRAFICOS (PNGs do BLK-RELVIAB-03).
# Saida OPCIONAL (so entra se `viabilidade` != None). READ-ONLY sobre o M1.
# ---------------------------------------------------------------------------
_VIAB_NUMEROS_TITLE = "Viabilidade - Números"
_VIAB_GRAFICOS_TITLE = "Viabilidade - Projeção financeira"


def _viab_brl(value: Any) -> str:
    if value is None or pd.isna(value):
        return "n/d"
    return "R$ " + _format_number(value, 2)


def _viab_pct(frac: Any) -> str:
    if frac is None or pd.isna(frac):
        return "n/d"
    return _format_number(float(frac) * 100.0, 1) + "%"


def _viab_payback(value: Any) -> str:
    if value is None or value == float("inf") or pd.isna(value):
        return "> 60 meses"
    return _format_number(value, 0) + " meses"


def _viab_breakeven(value: Any) -> str:
    if value is None or value == float("inf") or pd.isna(value):
        return "inviável"
    return _format_number(value, 0)


def _viab_faixa(p10: Any, p90: Any) -> str:
    if (p10 is None or pd.isna(p10)) and (p90 is None or pd.isna(p90)):
        return "n/d"
    return f"{_format_number(p10, 0)} - {_format_number(p90, 0)}"


def _viabilidade_page(
    pdf: _UltraPDF,
    viabilidade: dict[str, Any],
    assets: dict[str, bytes | None],
    *,
    primary: tuple[int, int, int] = ULTRA_TURQUESA,
    secondary: tuple[int, int, int] = ULTRA_MAGENTA,
) -> None:
    """Slide de numeros da viabilidade + (se houver) slide dos graficos. READ-ONLY M1.

    `viabilidade` e um dict simples (serializavel) derivado do `ViabilidadePontoResult`:
    alunos_breakeven, aluguel_teto, margem_ebitda_pct (fracao), payback_meses, roic_anual
    (fracao), faturamento_mensal, ebitda_mensal, faixa_p10/p90, flag_viavel,
    flag_fora_envelope e, opcionalmente, `graficos` (lista de ate 4 PNGs do BLK-RELVIAB-03).
    Com `graficos` -> 2 paginas; sem -> 1 pagina.
    """
    # --- Pagina de NUMEROS (grid 4x2 estilo Big Numbers) ---
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, _VIAB_NUMEROS_TITLE, rgb=primary)

    cards = [
        ("Alunos break-even", _viab_breakeven(viabilidade.get("alunos_breakeven"))),
        ("Aluguel-teto (mês)", _viab_brl(viabilidade.get("aluguel_teto"))),
        ("Margem EBITDA", _viab_pct(viabilidade.get("margem_ebitda_pct"))),
        ("Payback", _viab_payback(viabilidade.get("payback_meses"))),
        ("ROIC anual", _viab_pct(viabilidade.get("roic_anual"))),
        ("Faturamento/mês", _viab_brl(viabilidade.get("faturamento_mensal"))),
        ("EBITDA/mês", _viab_brl(viabilidade.get("ebitda_mensal"))),
        (
            "Faixa alunos (p10-p90)",
            _viab_faixa(viabilidade.get("faixa_p10"), viabilidade.get("faixa_p90")),
        ),
    ]
    margin_x, gap, cols = 36.0, 12.0, 4
    card_w = (_PAGE_W - 2 * margin_x - (cols - 1) * gap) / cols
    card_h = 132.0
    top = 72.0
    accents = [primary, secondary]
    for index, (label, value) in enumerate(cards):
        col, row = index % cols, index // cols
        x = margin_x + col * (card_w + gap)
        y = top + row * (card_h + gap)
        pdf.set_fill_color(*_CARD_NEUTRO_RGB)
        pdf.rect(x, y, card_w, card_h, style="F")
        pdf.set_draw_color(225, 225, 228)
        pdf.rect(x, y, card_w, card_h, style="D")
        pdf.set_fill_color(*accents[index % len(accents)])
        pdf.rect(x, y, card_w, 6.0, style="F")
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_xy(x + 14, y + 20)
        pdf.multi_cell(card_w - 28, 14, _ascii(label))
        pdf.set_text_color(40, 40, 40)
        pdf.set_font("Helvetica", "B", 22)
        pdf.set_xy(x + 14, y + 74)
        pdf.multi_cell(card_w - 28, 24, _ascii(value))

    viavel = "Sim" if viabilidade.get("flag_viavel") else "Não"
    envelope = "fora do envelope" if viabilidade.get("flag_fora_envelope") else "dentro do envelope"
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(margin_x, top + 2 * (card_h + gap) + 6)
    pdf.multi_cell(
        _PAGE_W - 2 * margin_x,
        12,
        _ascii(
            f"Viável? {viavel}   |   Metragem {envelope}. A demanda e uma PREMISSA do operador "
            "(nao prevista pela geografia). READ-ONLY sobre o M1."
        ),
    )
    _draw_footer(pdf, with_attribution=False)

    # --- Pagina de GRAFICOS (grid 2x2), so quando ha PNGs ---
    graficos = list(viabilidade.get("graficos") or [])
    if graficos:
        pdf.add_page()
        _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
        _draw_title_band(pdf, _VIAB_GRAFICOS_TITLE, rgb=secondary)
        pngs: list[bytes | None] = (graficos + [None, None, None, None])[:4]
        _draw_maps_grid(
            pdf, pngs, top=60.0, bottom=_PAGE_H - 26.0, margin_x=20.0, gap=12.0
        )
        _draw_footer(pdf, with_attribution=False)


def _draw_watermark(
    pdf: _UltraPDF, text: str, *, rgb: tuple[int, int, int] = _WATERMARK_RGB
) -> None:
    """Desenha a marca d'agua no canto inferior-direito, horizontal e discreta (BLK-EST-01-FU2).

    Posicao: baseline em (_PAGE_W - _WATERMARK_MARGIN - largura_texto, _PAGE_H - _WATERMARK_MARGIN).
    READ-ONLY de estado logico: `local_context` restaura o graphics state (fill_opacity) ao sair.
    Usa `pdf.text` (baseline) — imune a `set_margins`/auto_page_break OFF. Deve ser chamada
    DEPOIS do conteudo da pagina para ficar POR CIMA do fundo/PNG.

    O parametro `rgb` permite cor condicional por pagina: capa (pagina 1) usa `_WATERMARK_RGB_COVER`
    (branco, visivel sobre fundo turquesa); demais paginas usam `_WATERMARK_RGB` (cinza padrao).
    """
    pdf.set_font("Helvetica", "", _WATERMARK_FONT_PT)
    pdf.set_text_color(*rgb)
    w = pdf.get_string_width(text)
    x = _PAGE_W - _WATERMARK_MARGIN - w
    y = _PAGE_H - _WATERMARK_MARGIN
    with pdf.local_context(fill_opacity=_WATERMARK_ALPHA):
        pdf.text(x, y, text)


def _parece_coordenada(texto: str) -> bool:
    """True se o texto for so um par "lat, lng" (entao NAO serve como nome do local)."""
    partes = str(texto or "").replace(" ", "").split(",")
    if len(partes) != 2:
        return False
    try:
        float(partes[0])
        float(partes[1])
        return True
    except ValueError:
        return False


def _cover_page(
    pdf: _UltraPDF,
    result: dict[str, Any],
    assets: dict[str, bytes | None],
    *,
    rotulo: str | None = None,
) -> None:
    """(a) Capa — fundo de marca 16:9 (asset ou turquesa solido) + titulo na zona limpa.

    O asset de capa ja embute o logo "GRUPO ULTRA" e a faixa de marcas; o texto do relatorio
    vai na area turquesa limpa do quadrante inferior-direito para NAO colidir com o branding.
    Sem fundo (deploy/CI limpo) -> turquesa solido e o texto centralizado e legivel mesmo assim.

    `rotulo`: nome do endereco/estabelecimento (vindo do link/endereco resolvido). Quando
    presente e nao for so uma coordenada, vira o subtitulo no lugar de "Coordenada: lat,lng".
    """
    pdf.add_page()
    has_bg = assets.get("capa") is not None
    _draw_full_page_background(pdf, assets.get("capa"), ULTRA_TURQUESA)

    lat = result.get("lat")
    lng = result.get("lng")
    coord = f"{float(lat):.5f}, {float(lng):.5f}" if lat is not None and lng is not None else "coordenada n/d"
    municipio = str(result.get("nome_municipio") or "").strip()
    uf = str(result.get("uf") or "").strip()
    local = f"{municipio}/{uf}".strip("/") if (municipio or uf) else ""
    raio = _format_number(result.get("raio_km"), 1, " km")

    # Com fundo de marca: bloco de texto na zona limpa inferior-direita (x>=470).
    # Sem fundo: bloco centralizado sobre o turquesa solido.
    if has_bg:
        block_x, block_w, align = 478.0, 446.0, "L"
        title_y = 330.0
    else:
        block_x, block_w, align = 40.0, _PAGE_W - 80, "C"
        title_y = 230.0

    pdf.set_text_color(*_BRANCO)
    # D1=B (BLK-EST-02): titulo de capa 30 pt (mais presente).
    pdf.set_font("Helvetica", "B", 30)
    pdf.set_xy(block_x, title_y)
    pdf.multi_cell(block_w, 32, _ascii("Relatório Pontual Censitário"), align=align)

    pdf.set_font("Helvetica", "", 13)
    pdf.set_xy(block_x, title_y + 70)
    nome = str(rotulo or "").strip()
    if nome and not _parece_coordenada(nome):
        # Nome do endereco/estabelecimento (truncado p/ caber na zona limpa da capa).
        subt = nome if len(nome) <= 72 else nome[:69] + "..."
    else:
        subt = f"Coordenada: {coord}"
        if local:
            subt = f"{subt}   |   {local}"
    pdf.cell(block_w, 18, _ascii(subt), align=align)

    pdf.set_xy(block_x, title_y + 92)
    pdf.cell(block_w, 18, _ascii(f"Raio de análise: {raio}"), align=align)


def _cor_por_meta(valor: Any, meta: float) -> tuple[int, int, int]:
    """Cor de fundo do card: verde se valor >= meta, vermelho se < meta, neutro se "n/d".

    BLK-RELPON-08 (D3/Q2): "n/d" (None/NaN) e tratado ANTES da comparacao numerica -- condicao
    indecidivel vira neutro, nunca falsa reprovacao (vermelho) nem falso positivo (verde).
    Funcao pura, testavel isoladamente sem depender do PDF.
    """
    if valor is None or pd.isna(valor):
        return _CARD_NEUTRO_RGB
    return _CARD_VERDE_RGB if float(valor) >= meta else _CARD_VERMELHO_RGB


def _cor_consumo_concorrentes(sam: Any, residual_disponivel: Any) -> tuple[int, int, int]:
    """Cor assimetrica do card "Consumo concorrentes (est.)" -- tambem usada para colorir
    "Concorrentes no raio" (D3: esse card ESPELHA a cor do card acima, sem meta propria).

    Regra (D3): VERMELHO quando o mercado ja esta consumido (SAM Fitness >= meta E Residual
    Fitness < meta); VERDE caso contrario. "n/d" em SAM OU em Residual -> neutro (condicao
    indecidivel, mesmo criterio de `_cor_por_meta`). Funcao pura.
    """
    if sam is None or pd.isna(sam) or residual_disponivel is None or pd.isna(residual_disponivel):
        return _CARD_NEUTRO_RGB
    if (
        float(sam) >= _META_SAM_FITNESS_POTENCIAL
        and float(residual_disponivel) < _META_RESIDUAL_FITNESS_DISPONIVEL
    ):
        return _CARD_VERMELHO_RGB
    return _CARD_VERDE_RGB


def _big_numbers_page(
    pdf: _UltraPDF,
    result: dict[str, Any],
    residual: dict[str, Any] | None,
    assets: dict[str, bytes | None],
    *,
    primary: tuple[int, int, int] = ULTRA_TURQUESA,
    secondary: tuple[int, int, int] = ULTRA_MAGENTA,
) -> None:
    """(e) Big Numbers — grid 4x2 das 8 metricas. READ-ONLY; "n/d" auditavel.

    SAM Fitness e Residual Fitness saem em NUMERO DE ALUNOS (sizing absoluto da camada de
    mercado), nao em score: `sam_fitness_potencial` e `oferta_efetiva_disponivel` do hex H3.
    """
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, "Big Numbers", rgb=primary)

    residual = residual or {}
    sam = residual.get("sam_fitness_potencial")
    oferta_disponivel = residual.get("oferta_efetiva_disponivel")
    cor_consumo = _cor_consumo_concorrentes(sam, oferta_disponivel)

    cards = [
        (
            "População total no raio",
            _format_number(result.get("pop_total_raio"), 0),
            _cor_por_meta(result.get("pop_total_raio"), _META_POP_TOTAL_RAIO),
        ),
        (
            "Renda per capita média",
            "R$ " + _format_number(result.get("renda_per_capita_media_raio"), 2),
            _cor_por_meta(result.get("renda_per_capita_media_raio"), _META_RENDA_PER_CAPITA_MEDIA_RAIO),
        ),
        (
            "Número de domicílios",
            _format_number(result.get("domicilios_total_raio"), 0),
            _cor_por_meta(result.get("domicilios_total_raio"), _META_DOMICILIOS_TOTAL_RAIO),
        ),
        (
            "Renda média domiciliar",
            "R$ " + _format_number(result.get("renda_domiciliar_total_raio"), 2),
            _cor_por_meta(
                result.get("renda_domiciliar_total_raio"), _META_RENDA_DOMICILIAR_TOTAL_RAIO
            ),
        ),
        (
            "SAM Fitness (alunos)",
            _format_number(sam, 0),
            _cor_por_meta(sam, _META_SAM_FITNESS_POTENCIAL),
        ),
        (
            "Residual Fitness (alunos)",
            _format_number(oferta_disponivel, 0),
            _cor_por_meta(oferta_disponivel, _META_RESIDUAL_FITNESS_DISPONIVEL),
        ),
        ("Concorrentes no raio", _format_number(result.get("n_concorrentes"), 0), cor_consumo),
        (
            "Consumo concorrentes (est.)",
            _format_number(residual.get("oferta_consumida_mercado_estimada"), 0),
            cor_consumo,
        ),
    ]

    # 4x2: 8 cards (o "Score censitario medio" foi removido em 2026-07-17 p/ a grade fechar certa).
    # Geometria em constantes de modulo (_BIG_NUMBERS_*) para o invariante "cabe na pagina 960x540"
    # ser testavel; a nota de fonte fica logo abaixo das 2 linhas.
    margin_x = 36.0
    top = _BIG_NUMBERS_TOP
    gap = _BIG_NUMBERS_GAP
    cols, rows = _BIG_NUMBERS_COLS, _BIG_NUMBERS_ROWS
    card_w = (_PAGE_W - 2 * margin_x - (cols - 1) * gap) / cols
    card_h = _BIG_NUMBERS_CARD_H
    # Barras de destaque dos cards seguem o tom da pagina (primaria + acento).
    accents = [primary, secondary]

    for index, (label, value, cor_fundo) in enumerate(cards):
        col = index % cols
        row = index // cols
        x = margin_x + col * (card_w + gap)
        y = top + row * (card_h + gap)
        # Cartao com fundo por meta (semaforo D3) + borda fina + barra de destaque (D3=B).
        pdf.set_fill_color(*cor_fundo)
        pdf.rect(x, y, card_w, card_h, style="F")
        pdf.set_draw_color(225, 225, 228)
        pdf.rect(x, y, card_w, card_h, style="D")
        accent = accents[index % len(accents)]
        pdf.set_fill_color(*accent)
        pdf.rect(x, y, card_w, 6.0, style="F")
        # Rotulo (D2=B: cinza-escuro 45,45,45; acento so na barra do topo).
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_xy(x + 14, y + 20)
        pdf.multi_cell(card_w - 28, 14, _ascii(label))
        # Valor grande (D2=B: cinza-escuro 40,40,40, nao no acento; D3=B: 26 pt).
        # Offset proporcional ao card de 132 pt (era +88 no card de 156) p/ nao encostar na base.
        pdf.set_text_color(40, 40, 40)
        pdf.set_font("Helvetica", "B", 26)
        pdf.set_xy(x + 14, y + 74)
        pdf.multi_cell(card_w - 28, 28, _ascii(value))

    # Nota de fonte auditavel.
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_xy(margin_x, top + rows * (card_h + gap) + 2)
    metodo = str(result.get("metodo", METODO_RELATORIO_PONTUAL_CENSITARIO))
    pdf.multi_cell(
        _PAGE_W - 2 * margin_x,
        11,
        _ascii(
            "Fontes: pop/renda/domicílios/score = censo (interseção de setores IBGE 2022 com círculo de "
            f"1.5 km, método {metodo}); SAM Fitness, Residual Fitness (em alunos) e consumo = lookup "
            "READ-ONLY do hex H3 (sem recálculo do M1). Fundo do card: verde = meta atingida, vermelho = "
            "meta não atingida, cinza = 'n/d' (dado ausente para o ponto)."
        ),
    )
    _draw_footer(pdf, with_attribution=True)


def _point_rows(points: pd.DataFrame, label: str, *, is_ultra: bool) -> list[tuple[str, bool]]:
    """Lista textual de unidades no raio. Usa apenas dados de UNIDADE (sem PII de pessoas).

    D4=B (BLK-EST-02): retorna `(texto, is_ultra)` para colorir o bullet por tipo
    (Ultra=turquesa, concorrente=magenta) sem introduzir PII.
    """
    if points is None or points.empty:
        return [(f"{label}: sem unidades no raio.", is_ultra)]
    name_col = next(
        (column for column in ("rede", "nome_unidade", "nome", "brand") if column in points.columns),
        None,
    )
    rows: list[tuple[str, bool]] = []
    for _, row in points.head(10).iterrows():
        name = str(row.get(name_col, label)) if name_col else label
        dist = _format_number(row.get("dist_km"), 2, " km")
        rows.append((f"{label}: {name} ({dist})", is_ultra))
    return rows


def _safe_len(points: pd.DataFrame | None) -> int:
    """Contagem segura de linhas de um DataFrame de unidades (guarda None/empty)."""
    if points is None:
        return 0
    try:
        return int(len(points))
    except Exception:
        return 0


def _competitors_page(
    pdf: _UltraPDF,
    result: dict[str, Any],
    png_bytes: bytes | None,
    assets: dict[str, bytes | None],
    *,
    primary: tuple[int, int, int] = ULTRA_TURQUESA,
    secondary: tuple[int, int, int] = ULTRA_MAGENTA,
) -> None:
    """(f) Concorrentes — mapa + lista textual das redes no raio (sem PII)."""
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, "Concorrentes", rgb=primary)

    # Mapa de concorrentes a ESQUERDA (16:9: mapa + lista lado a lado).
    if png_bytes:
        dims = _png_dimensions(png_bytes)
        if dims is not None:
            img_w, img_h = dims
            max_w, max_h = 560.0, 430.0
            scale = min(max_w / img_w, max_h / img_h)
            draw_w = img_w * scale
            draw_h = img_h * scale
            x = 36.0 + (max_w - draw_w) / 2.0
            y = 60.0 + (max_h - draw_h) / 2.0
            try:
                pdf.image(BytesIO(png_bytes), x=x, y=y, w=draw_w, h=draw_h)
            except Exception:
                pass

    # Lista de redes a DIREITA.
    list_x = 620.0
    list_w = _PAGE_W - list_x - 36.0
    bullet_w = 12.0
    text_x = list_x + bullet_w

    # D4=B (BLK-EST-02): cabecalho com contagem total quando ha mais de 10 redes no raio.
    concorrentes_df = result.get("concorrentes_raio", pd.DataFrame())
    ultra_df = result.get("ultra_raio", pd.DataFrame())
    total = _safe_len(concorrentes_df) + _safe_len(ultra_df)
    header = "Redes no raio de 1.5 km"
    if total > 10:
        header = f"{header} ({total} no total)"
    pdf.set_text_color(*secondary)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_xy(list_x, 70.0)
    pdf.cell(list_w, 18, _ascii(header))

    pdf.set_font("Helvetica", "", 10)
    y = 100.0
    # D4=B: cada linha leva um bullet colorido por tipo (Ultra=turquesa, concorrente=magenta).
    linhas: list[tuple[str, bool]] = []
    linhas.extend(_point_rows(concorrentes_df, "Concorrente", is_ultra=False))
    linhas.extend(_point_rows(ultra_df, "Ultra", is_ultra=True))
    truncated = total > 10
    for line, is_ultra in linhas:
        if y > _PAGE_H - 40:
            break
        bullet_rgb = ULTRA_TURQUESA if is_ultra else ULTRA_MAGENTA
        pdf.set_fill_color(*bullet_rgb)
        pdf.ellipse(list_x, y + 4, 6, 6, style="F")
        pdf.set_text_color(*_CINZA_TEXTO)
        pdf.set_xy(text_x, y)
        pdf.multi_cell(list_w - bullet_w, 14, _ascii(line))
        y = pdf.get_y() + 4.0

    # D4=B: rodape da lista "... e mais N" quando truncar em 10 linhas.
    if truncated and y <= _PAGE_H - 40:
        pdf.set_text_color(*_CINZA_TEXTO)
        pdf.set_xy(text_x, y)
        pdf.multi_cell(list_w - bullet_w, 14, _ascii(f"... e mais {total - 10}"))

    _draw_footer(pdf, with_attribution=True)


def _perfil_icon(
    pdf: _UltraPDF, kind: str, x: float, y: float, size: float, rgb: tuple[int, int, int]
) -> None:
    """Icone vetorial simples do painel "Microarea": pessoas (pop/densidade), casa
    (domicilios) e cifra (renda), em `rgb`, dentro do bounding box (x, y, size, size).
    """
    pdf.set_fill_color(*rgb)
    pdf.set_draw_color(*rgb)
    if kind in ("pop", "dens"):
        # Duas "pessoas": duas cabecas (circulos) + dois ombros arredondados.
        head_d = size * 0.30
        pdf.ellipse(x + size * 0.14, y + size * 0.08, head_d, head_d, style="F")
        pdf.ellipse(x + size * 0.56, y + size * 0.08, head_d, head_d, style="F")
        pdf.rect(
            x + size * 0.02, y + size * 0.48, size * 0.42, size * 0.44,
            style="F", round_corners=True, corner_radius=size * 0.16,
        )
        pdf.rect(
            x + size * 0.56, y + size * 0.48, size * 0.42, size * 0.44,
            style="F", round_corners=True, corner_radius=size * 0.16,
        )
    elif kind == "dom":
        # Casa: telhado (triangulo) + corpo (retangulo).
        pdf.polygon(
            [
                (x + size * 0.50, y + size * 0.06),
                (x + size * 0.94, y + size * 0.48),
                (x + size * 0.06, y + size * 0.48),
            ],
            style="F",
        )
        pdf.rect(x + size * 0.20, y + size * 0.46, size * 0.60, size * 0.46, style="F")
    else:  # renda -> cifra dentro de um circulo
        pdf.ellipse(x + size * 0.05, y + size * 0.05, size * 0.90, size * 0.90, style="F")
        pdf.set_text_color(*_BRANCO)
        pdf.set_font("Helvetica", "B", max(9, int(size * 0.58)))
        pdf.set_xy(x, y + size * 0.20)
        pdf.cell(size, size * 0.5, "$", align="C")


def _perfil_info_dot(pdf: _UltraPDF, cx: float, cy: float, r: float = 8.5) -> None:
    """Circulo "i" decorativo cinza-claro a direita de cada metrica (fidelidade ao painel)."""
    pdf.set_fill_color(*_PERFIL_INFO_RGB)
    pdf.ellipse(cx - r, cy - r, 2 * r, 2 * r, style="F")
    pdf.set_text_color(*_BRANCO)
    pdf.set_font("Helvetica", "BI", int(r * 1.25))
    pdf.set_xy(cx - r, cy - r * 0.95)
    pdf.cell(2 * r, 2 * r * 0.95, "i", align="C")


def _perfil_metric_rows(perfil: dict[str, Any]) -> list[tuple[str, str, str]]:
    """As 4 metricas do perfil como (kind_icone, rotulo, valor). Rotulos e metodo de renda
    INALTERADOS (D3/D3.5); `_format_number` ja devolve "n/d" para ausente.
    """
    renda_raw = perfil.get("renda_media_domiciliar")
    # "R$" so quando ha valor; sem dado exibe apenas "n/d" (evita "R$ n/d").
    renda_str = (
        "R$ " + _format_number(renda_raw, 2)
        if renda_raw is not None and not pd.isna(renda_raw)
        else "n/d"
    )
    return [
        ("pop", "População", _format_number(perfil.get("populacao_total"), 0)),
        ("dens", "Densidade demográfica", _format_number(perfil.get("densidade_hab_km2"), 0, " hab/km2")),
        ("dom", "Domicílios", _format_number(perfil.get("domicilios_total"), 0)),
        ("renda", "Renda média", renda_str),
    ]


def _draw_perfil_panel(
    pdf: _UltraPDF,
    *,
    x: float,
    y: float,
    w: float,
    h: float,
    disponivel: bool,
    tipo_label: str,
    nome: str,
    local_line: str,
    rows: list[tuple[str, str, str]],
) -> None:
    """Painel vertical estilo "Microarea" (GeoFusion): moldura turquesa arredondada + cartao
    branco + cabecalho (rotulo + nome) + metricas empilhadas (icone + rotulo cinza + valor
    grande azul-marinho + circulo "i"). SO layout — nao altera valores nem a contagem de paginas.
    """
    frame_r = 26.0
    borda = 12.0
    # Moldura turquesa arredondada.
    pdf.set_fill_color(*ULTRA_TURQUESA)
    pdf.set_line_width(0)
    pdf.rect(x, y, w, h, style="F", round_corners=True, corner_radius=frame_r)
    # Cartao branco interno.
    cx0, cy0 = x + borda, y + borda
    cw, ch = w - 2 * borda, h - 2 * borda
    pdf.set_fill_color(*_BRANCO)
    pdf.rect(cx0, cy0, cw, ch, style="F", round_corners=True, corner_radius=frame_r - borda)

    pad = 30.0
    content_x = cx0 + pad
    content_w = cw - 2 * pad
    head_y = cy0 + 24.0

    if disponivel:
        pdf.set_text_color(*_PERFIL_ROTULO_RGB)
        pdf.set_font("Helvetica", "", 12)
        pdf.set_xy(content_x, head_y)
        pdf.cell(content_w, 14, _ascii(tipo_label))
        pdf.set_text_color(*_PERFIL_VALOR_RGB)
        pdf.set_font("Helvetica", "B", 24)
        pdf.set_xy(content_x, head_y + 15)
        pdf.multi_cell(content_w, 26, _ascii(nome))
        y_after = pdf.get_y()
        if local_line:
            pdf.set_text_color(*_PERFIL_ROTULO_RGB)
            pdf.set_font("Helvetica", "", 12)
            pdf.set_xy(content_x, y_after + 2)
            pdf.multi_cell(content_w, 14, _ascii(local_line))
            y_after = pdf.get_y()
    else:
        pdf.set_text_color(*_PERFIL_VALOR_RGB)
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_xy(content_x, head_y)
        pdf.multi_cell(content_w, 24, _ascii("Perfil não disponível"))
        y_after = pdf.get_y()
        pdf.set_text_color(*_PERFIL_ROTULO_RGB)
        pdf.set_font("Helvetica", "", 12)
        pdf.set_xy(content_x, y_after + 2)
        pdf.multi_cell(
            content_w, 14,
            _ascii("Fora da malha de setores ou unidade sem dado suficiente."),
        )
        y_after = pdf.get_y()

    # Divisor sob o cabecalho.
    sep_y = y_after + 14.0
    pdf.set_draw_color(*_PERFIL_DIVISOR_RGB)
    pdf.set_line_width(1.0)
    pdf.line(content_x, sep_y, content_x + content_w, sep_y)

    # Metricas empilhadas, distribuidas no espaco restante do cartao.
    rows_top = sep_y + 6.0
    rows_bottom = cy0 + ch - 18.0
    n = max(1, len(rows))
    row_h = (rows_bottom - rows_top) / n
    for i, (kind, label, value) in enumerate(rows):
        ry = rows_top + i * row_h
        icon_size = min(30.0, row_h * 0.44)
        icon_y = ry + (row_h - icon_size) / 2.0 - 4.0
        _perfil_icon(pdf, kind, content_x, icon_y, icon_size, ULTRA_TURQUESA)
        text_x = content_x + icon_size + 16.0
        text_w = content_w - (icon_size + 16.0) - 26.0
        pdf.set_text_color(*_PERFIL_ROTULO_RGB)
        pdf.set_font("Helvetica", "", 12)
        pdf.set_xy(text_x, ry + row_h * 0.16)
        pdf.cell(text_w, 14, _ascii(label))
        pdf.set_text_color(*_PERFIL_VALOR_RGB)
        pdf.set_font("Helvetica", "B", 26)
        pdf.set_xy(text_x, ry + row_h * 0.16 + 16.0)
        pdf.cell(text_w, 28, _ascii(value))
        _perfil_info_dot(pdf, content_x + content_w - 12.0, ry + row_h / 2.0)
        if i < n - 1:
            pdf.set_draw_color(*_PERFIL_DIVISOR_RGB)
            pdf.set_line_width(1.0)
            pdf.line(content_x, ry + row_h, content_x + content_w, ry + row_h)
    pdf.set_line_width(0)


def _perfil_nota_metodo(pdf: _UltraPDF) -> None:
    """Nota de metodo auditavel do Perfil do Bairro/Distrito (rodape do slide)."""
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_xy(36, _PAGE_H - 40)
    pdf.multi_cell(
        _PAGE_W - 72,
        10,
        _ascii(
            "Agregado sobre todos os setores do bairro/distrito (não o raio de 1,5 km). "
            "Fonte: Censo IBGE 2022; renda média ponderada por domicílios."
        ),
    )


def _perfil_bairro_page(
    pdf: _UltraPDF,
    perfil_bairro: dict[str, Any] | None,
    assets: dict[str, bytes | None],
    *,
    primary: tuple[int, int, int] = ULTRA_TURQUESA,
    secondary: tuple[int, int, int] = ULTRA_MAGENTA,
) -> None:
    """(BLK-RELPON-07) Perfil do Bairro/Distrito — painel vertical estilo "Microarea"
    (GeoFusion) com as 4 metricas agregadas sobre a unidade INTEIRA (nao o raio de 1.5 km).
    SEM mapa; "n/d" gracioso quando o perfil nao esta disponivel (ponto fora da malha de
    setores ou unidade sem dado suficiente).
    """
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, "Perfil do Bairro/Distrito", rgb=primary)

    perfil = perfil_bairro or {}
    flag_disponivel = bool(perfil.get("flag_perfil_disponivel"))
    unidade_tipo = perfil.get("unidade_tipo")
    unidade_nome = str(perfil.get("unidade_nome") or "").strip()
    municipio = str(perfil.get("municipio_nome") or "").strip()
    uf = str(perfil.get("uf") or "").strip()
    tipo_label = "Bairro" if unidade_tipo == "bairro" else "Distrito"
    local_line = f"{municipio}/{uf}".strip("/") if (municipio or uf) else ""

    panel_w = 600.0
    panel_x = (_PAGE_W - panel_w) / 2.0
    _draw_perfil_panel(
        pdf,
        x=panel_x,
        y=70.0,
        w=panel_w,
        h=410.0,
        disponivel=flag_disponivel and bool(unidade_nome),
        tipo_label=tipo_label,
        nome=unidade_nome,
        local_line=local_line,
        rows=_perfil_metric_rows(perfil),
    )

    _perfil_nota_metodo(pdf)
    _draw_footer(pdf, with_attribution=True)


def _credit_page(pdf: _UltraPDF, assets: dict[str, bytes | None]) -> None:
    """(g) Realizacao/Credito — fundo turquesa solido, texto Ultra centralizado. SEM PII.

    Usa turquesa solido (nao a foto da capa) para o texto de credito/metodo ficar legivel no
    formato 16:9; a faixa de marca da capa ja cumpre o papel de branding visual no inicio.
    """
    pdf.add_page()
    pdf.set_fill_color(*ULTRA_TURQUESA)
    pdf.rect(0, 0, _PAGE_W, _PAGE_H, style="F")

    # D1=B (BLK-EST-02): Realizacao 34/18/12 pt.
    pdf.set_text_color(*_BRANCO)
    pdf.set_font("Helvetica", "B", 34)
    pdf.set_xy(40, 180)
    pdf.cell(_PAGE_W - 80, 40, _ascii("Realização"), align="C")

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_xy(40, 232)
    pdf.cell(_PAGE_W - 80, 24, _ascii(_CREDITO_ULTRA), align="C")

    # D5=C: metodo encurtado para 1 frase (ASCII-safe).
    pdf.set_font("Helvetica", "", 12)
    pdf.set_xy(160, 278)
    pdf.multi_cell(
        _PAGE_W - 320,
        16,
        _ascii(
            "Interseção de setores censitários IBGE 2022 com círculo de 1,5 km; "
            "distribuição intrassetor por área."
        ),
        align="C",
    )

    pdf.set_xy(160, 322)
    pdf.multi_cell(
        _PAGE_W - 320,
        16,
        _ascii(
            "READ-ONLY: este relatório não altera score_priorizacao, carteira, plano ou artefatos "
            "oficiais do M1."
        ),
        align="C",
    )

    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(40, _PAGE_H - 40)
    pdf.cell(_PAGE_W - 80, 12, _ascii(f"Fundo de ruas: {_ATRIBUICAO_TILES}."), align="C")


# ---------------------------------------------------------------------------
# Variante "Apresentacao Classica Ultra" (BLK-EST-05) — helpers e gerador.
# READ-ONLY sobre o M1; reusa o motor/helpers do template recente. NAO altera
# nenhuma funcao usada pelo template recente (byte-a-byte preservado).
# ---------------------------------------------------------------------------


def _classico_data_extenso(now: datetime | None = None) -> str:
    """Data por extenso ASCII-safe, ex.: "15 de junho de 2026" (injetavel p/ teste)."""
    moment = now or datetime.now()
    mes = _MESES_PT[moment.month - 1]
    return f"{moment.day} de {mes} de {moment.year}"


def _classico_mes_ano(now: datetime | None = None) -> str:
    """Mes/ano por extenso para o subtitulo da capa, ex.: "Junho de 2026"."""
    moment = now or datetime.now()
    mes = _MESES_PT[moment.month - 1]
    return f"{mes.capitalize()} de {moment.year}"


def _classico_title_band(
    pdf: _UltraPDF,
    texto_banda: str,
    titulo_secao: str,
    assets: dict[str, bytes | None],
    *,
    rgb: tuple[int, int, int] = ULTRA_TURQUESA,
) -> None:
    """Banda turquesa "classica": margem lateral 20px, cantos arredondados r~16, altura ~58.

    Endereco/nome (branco) a esquerda + icone Ultra a direita (fallback gracioso quando
    `assets["icone"]` e None). O titulo da SECAO e desenhado ABAIXO da banda.
    """
    band_w = _PAGE_W - 2 * _CLASSICO_MARGIN
    pdf.set_fill_color(*rgb)
    pdf.set_line_width(0)
    pdf.rect(
        _CLASSICO_MARGIN,
        _CLASSICO_MARGIN,
        band_w,
        _CLASSICO_BAND_H,
        style="F",
        round_corners=True,
        corner_radius=_CLASSICO_CORNER_RADIUS,
    )

    # Icone Ultra a direita, dentro da banda (fallback gracioso se ausente/invalido).
    icone = assets.get("icone")
    icone_w = 0.0
    if icone is not None:
        dims = _png_dimensions(icone)
        if dims is not None:
            iw, ih = dims
            target_h = _CLASSICO_BAND_H - 20.0
            scale = target_h / ih if ih else 1.0
            icone_w = iw * scale
            ix = _PAGE_W - _CLASSICO_MARGIN - 18.0 - icone_w
            iy = _CLASSICO_MARGIN + (_CLASSICO_BAND_H - target_h) / 2.0
            try:
                pdf.image(BytesIO(icone), x=ix, y=iy, w=icone_w, h=target_h)
            except Exception:
                icone_w = 0.0

    # Endereco/nome a esquerda (branco), sem colidir com o icone.
    pdf.set_text_color(*_BRANCO)
    pdf.set_font("Helvetica", "B", 18)
    text_w = band_w - 36.0 - (icone_w + 24.0 if icone_w else 0.0)
    pdf.set_xy(_CLASSICO_MARGIN + 18.0, _CLASSICO_MARGIN + 18.0)
    pdf.cell(text_w, 22, _ascii(texto_banda))

    # Titulo da secao ABAIXO da banda (acompanha o tom da banda, sobre fundo claro).
    pdf.set_text_color(*rgb)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_xy(_CLASSICO_MARGIN, _CLASSICO_MARGIN + _CLASSICO_BAND_H + 12.0)
    pdf.cell(band_w, 24, _ascii(titulo_secao))


def _classico_banda_texto(result: dict[str, Any], rotulo: str | None) -> str:
    """Texto da banda turquesa: endereco/nome quando ha rotulo real, senao a coordenada."""
    nome = str(rotulo or "").strip()
    if nome and not _parece_coordenada(nome):
        return nome if len(nome) <= 80 else nome[:77] + "..."
    lat = result.get("lat")
    lng = result.get("lng")
    if lat is not None and lng is not None:
        return f"Coordenada: {float(lat):.5f}, {float(lng):.5f}"
    return "Relatório Pontual Censitário"


def _classico_cover_page(
    pdf: _UltraPDF,
    result: dict[str, Any],
    assets: dict[str, bytes | None],
    *,
    rotulo: str | None = None,
    now: datetime | None = None,
) -> None:
    """Capa classica: endereco ACIMA do subtitulo, texto por baseline (base ~y455)."""
    pdf.add_page()
    has_bg = assets.get("capa") is not None
    _draw_full_page_background(pdf, assets.get("capa"), ULTRA_TURQUESA)

    lat = result.get("lat")
    lng = result.get("lng")
    coord = f"{float(lat):.5f}, {float(lng):.5f}" if lat is not None and lng is not None else "coordenada n/d"
    nome = str(rotulo or "").strip()
    endereco = nome if (nome and not _parece_coordenada(nome)) else f"Coordenada: {coord}"
    if len(endereco) > 72:
        endereco = endereco[:69] + "..."
    subtitulo = f"Relatório Pontual Censitário - Raio 1,5 km | {_classico_mes_ano(now)}"

    # Zona limpa inferior-direita quando ha fundo de marca; centro quando nao ha.
    base_x = 478.0 if has_bg else 80.0
    pdf.set_text_color(*_BRANCO)
    # Endereco ACIMA (baseline ~y430), subtitulo ABAIXO (baseline ~y455, acima da linha ~y460).
    pdf.set_font("Helvetica", "B", 26)
    pdf.text(base_x, 430.0, _ascii(endereco))
    pdf.set_font("Helvetica", "", 13)
    pdf.text(base_x, 455.0, _ascii(subtitulo))


# Topo da area de conteudo do template CLASSICO (abaixo da banda + titulo de secao ~y122).
_CLASSICO_MAPS_TOP = _CLASSICO_MARGIN + _CLASSICO_BAND_H + 12.0 + 24.0 + 8.0


def _classico_draw_maps_grid(
    pdf: _UltraPDF,
    pngs: list[bytes | None],
) -> list[tuple[float, float, float, float]]:
    """Grid 2x2 dos 4 choropleths na geometria do template CLASSICO (BLK-RELPON-01).

    Mesma logica de `_draw_maps_grid`, mas com o topo respeitando a banda classica + titulo
    de secao (`_CLASSICO_MAPS_TOP` ~122) e a margem lateral classica (20). O header fixo deixa a
    celula 2x2 mais baixa que na variante recente -> a legenda embutida cai para ~8pt (piso legivel
    aceito para caber os 4 mapas; ver test_legenda_corpo_atinge_o_alvo_de_legibilidade_no_pdf).
    """
    return _draw_maps_grid(
        pdf,
        pngs,
        top=_CLASSICO_MAPS_TOP,
        bottom=_PAGE_H - 22.0,
        margin_x=_CLASSICO_MARGIN,
        gap=10.0,
        pack=True,
    )


def _classico_mapas_calor_page(
    pdf: _UltraPDF,
    layers: dict[str, bytes],
    assets: dict[str, bytes | None],
    *,
    banda_texto: str,
    primary: tuple[int, int, int] = ULTRA_TURQUESA,
) -> list[tuple[float, float, float, float]]:
    """Slide unico "Mapas de calor" (template classico): banda classica + grid 2x2 + rodape."""
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _classico_title_band(pdf, banda_texto, "Mapas de calor", assets, rgb=primary)
    boxes = _classico_draw_maps_grid(
        pdf,
        [
            layers.get("densidade"),
            layers.get("renda"),
            layers.get("score"),
            layers.get("renda_domiciliar"),
        ],
    )
    _draw_footer(pdf, with_attribution=True)
    return boxes


def _classico_competitors_page(
    pdf: _UltraPDF,
    result: dict[str, Any],
    png_bytes: bytes | None,
    assets: dict[str, bytes | None],
    *,
    banda_texto: str,
    primary: tuple[int, int, int] = ULTRA_TURQUESA,
    secondary: tuple[int, int, int] = ULTRA_MAGENTA,
) -> None:
    """Concorrentes classica: banda classica + mapa a esquerda + lista a direita (reuso)."""
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _classico_title_band(pdf, banda_texto, "Concorrentes", assets, rgb=primary)

    # Mapa de concorrentes a ESQUERDA (abaixo da banda + titulo de secao).
    if png_bytes:
        dims = _png_dimensions(png_bytes)
        if dims is not None:
            img_w, img_h = dims
            max_w, max_h = 540.0, 380.0
            scale = min(max_w / img_w, max_h / img_h)
            draw_w = img_w * scale
            draw_h = img_h * scale
            x = _CLASSICO_MARGIN + (max_w - draw_w) / 2.0
            y = 130.0 + (max_h - draw_h) / 2.0
            try:
                pdf.image(BytesIO(png_bytes), x=x, y=y, w=draw_w, h=draw_h)
            except Exception:
                pass

    # Lista de redes a DIREITA (mesma logica de `_competitors_page`, reusa _point_rows/_safe_len).
    list_x = 600.0
    list_w = _PAGE_W - list_x - _CLASSICO_MARGIN
    bullet_w = 12.0
    text_x = list_x + bullet_w

    concorrentes_df = result.get("concorrentes_raio", pd.DataFrame())
    ultra_df = result.get("ultra_raio", pd.DataFrame())
    total = _safe_len(concorrentes_df) + _safe_len(ultra_df)
    header = "Redes no raio de 1.5 km"
    if total > 10:
        header = f"{header} ({total} no total)"
    pdf.set_text_color(*secondary)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_xy(list_x, 130.0)
    pdf.cell(list_w, 18, _ascii(header))

    pdf.set_font("Helvetica", "", 10)
    y = 160.0
    linhas: list[tuple[str, bool]] = []
    linhas.extend(_point_rows(concorrentes_df, "Concorrente", is_ultra=False))
    linhas.extend(_point_rows(ultra_df, "Ultra", is_ultra=True))
    truncated = total > 10
    for line, is_ultra in linhas:
        if y > _PAGE_H - 40:
            break
        bullet_rgb = ULTRA_TURQUESA if is_ultra else ULTRA_MAGENTA
        pdf.set_fill_color(*bullet_rgb)
        pdf.ellipse(list_x, y + 4, 6, 6, style="F")
        pdf.set_text_color(*_CINZA_TEXTO)
        pdf.set_xy(text_x, y)
        pdf.multi_cell(list_w - bullet_w, 14, _ascii(line))
        y = pdf.get_y() + 4.0

    if truncated and y <= _PAGE_H - 40:
        pdf.set_text_color(*_CINZA_TEXTO)
        pdf.set_xy(text_x, y)
        pdf.multi_cell(list_w - bullet_w, 14, _ascii(f"... e mais {total - 10}"))

    _draw_footer(pdf, with_attribution=True)


def _classico_perfil_bairro_page(
    pdf: _UltraPDF,
    perfil_bairro: dict[str, Any] | None,
    assets: dict[str, bytes | None],
    *,
    banda_texto: str,
    primary: tuple[int, int, int] = ULTRA_TURQUESA,
    secondary: tuple[int, int, int] = ULTRA_MAGENTA,
) -> None:
    """(BLK-RELPON-07) Perfil do Bairro/Distrito, variante classica: banda classica + 4 cards.

    Mesma logica de conteudo de `_perfil_bairro_page`, com geometria deslocada para abrir
    espaco a banda classica (que ocupa ate ~y=122). SEM mapa; "n/d" gracioso.
    """
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _classico_title_band(pdf, banda_texto, "Perfil do Bairro/Distrito", assets, rgb=primary)

    perfil = perfil_bairro or {}
    flag_disponivel = bool(perfil.get("flag_perfil_disponivel"))
    unidade_tipo = perfil.get("unidade_tipo")
    unidade_nome = str(perfil.get("unidade_nome") or "").strip()
    municipio = str(perfil.get("municipio_nome") or "").strip()
    uf = str(perfil.get("uf") or "").strip()
    tipo_label = "Bairro" if unidade_tipo == "bairro" else "Distrito"
    local_line = f"{municipio}/{uf}".strip("/") if (municipio or uf) else ""

    # Painel "Microarea" abaixo da banda classica (que ocupa ate ~y=122).
    panel_w = 600.0
    panel_x = (_PAGE_W - panel_w) / 2.0
    _draw_perfil_panel(
        pdf,
        x=panel_x,
        y=132.0,
        w=panel_w,
        h=348.0,
        disponivel=flag_disponivel and bool(unidade_nome),
        tipo_label=tipo_label,
        nome=unidade_nome,
        local_line=local_line,
        rows=_perfil_metric_rows(perfil),
    )

    _perfil_nota_metodo(pdf)
    _draw_footer(pdf, with_attribution=True)


def _classico_banda_magenta_rodape(pdf: _UltraPDF) -> None:
    """Banda magenta full-width, flush-baixo, levemente acima da marca d'agua."""
    pdf.set_fill_color(*ULTRA_MAGENTA)
    pdf.set_line_width(0)
    y = _PAGE_H - _CLASSICO_MAGENTA_BANDA_H - _CLASSICO_MAGENTA_OFFSET
    pdf.rect(0.0, y, _PAGE_W, _CLASSICO_MAGENTA_BANDA_H, style="F")


def _classico_credit_page(
    pdf: _UltraPDF,
    result: dict[str, Any],
    assets: dict[str, bytes | None],
    *,
    rotulo: str | None = None,
    now: datetime | None = None,
) -> None:
    """Realizacao classica: corpo do `_credit_page` + link clicavel do ponto + data por extenso.

    SEM logo, SEM cartao de contato (anti-PII). Reusa visual de credito/metodo/READ-ONLY.
    """
    pdf.add_page()
    pdf.set_fill_color(*ULTRA_TURQUESA)
    pdf.rect(0, 0, _PAGE_W, _PAGE_H, style="F")

    pdf.set_text_color(*_BRANCO)
    pdf.set_font("Helvetica", "B", 34)
    pdf.set_xy(40, 120)
    pdf.cell(_PAGE_W - 80, 40, _ascii("Realização"), align="C")

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_xy(40, 172)
    pdf.cell(_PAGE_W - 80, 24, _ascii(_CREDITO_ULTRA), align="C")

    pdf.set_font("Helvetica", "", 12)
    pdf.set_xy(160, 218)
    pdf.multi_cell(
        _PAGE_W - 320,
        16,
        _ascii(
            "Interseção de setores censitários IBGE 2022 com círculo de 1,5 km; "
            "distribuição intrassetor por área."
        ),
        align="C",
    )

    pdf.set_xy(160, 262)
    pdf.multi_cell(
        _PAGE_W - 320,
        16,
        _ascii(
            "READ-ONLY: este relatório não altera score_priorizacao, carteira, plano ou artefatos "
            "oficiais do M1."
        ),
        align="C",
    )

    # Bloco "Link para localizacao do ponto:" + endereco como link clicavel.
    nome = str(rotulo or "").strip()
    if nome and not _parece_coordenada(nome):
        link_query = nome
        link_label = nome if len(nome) <= 80 else nome[:77] + "..."
    else:
        lat = result.get("lat")
        lng = result.get("lng")
        link_query = f"{float(lat):.6f},{float(lng):.6f}" if lat is not None and lng is not None else ""
        link_label = link_query or "n/d"
    url = build_search_url(link_query) if link_query else build_search_url("")

    pdf.set_text_color(*_BRANCO)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(40, 330)
    pdf.cell(_PAGE_W - 80, 16, _ascii("Link para localização do ponto:"), align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_xy(40, 350)
    pdf.cell(_PAGE_W - 80, 16, _ascii(link_label), align="C", link=url)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_xy(40, 380)
    pdf.cell(
        _PAGE_W - 80,
        16,
        _ascii(f"Data de geração: {_classico_data_extenso(now)}"),
        align="C",
    )

    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(40, _PAGE_H - 40)
    pdf.cell(_PAGE_W - 80, 12, _ascii(f"Fundo de ruas: {_ATRIBUICAO_TILES}."), align="C")


def gerar_pdf_relatorio_pontual_classico(
    result: dict[str, Any],
    mapas: dict[str, bytes] | bytes | None = None,
    *,
    residual: dict[str, Any] | None = None,
    perfil_bairro: dict[str, Any] | None = None,
    ultra_dir: Path | str | None = None,
    solicitante: str | None = None,
    rotulo: str | None = None,
    now: datetime | None = None,
    fotos: list[bytes] | None = None,
    info_imovel: dict[str, Any] | None = None,
    viabilidade: dict[str, Any] | None = None,
    foto_satelite: bytes | None = None,
    foto_satelite_grande: bool = False,
) -> bytes:
    """Gera o PDF "Apresentacao Classica Ultra" (estetica GeoFusion antiga, motor novo).

    6 paginas na ordem canonica (Capa -> Mapas de calor -> Concorrentes -> Perfil do
    Bairro/Distrito -> Big Numbers -> Realizacao), reusando o motor/helpers do template
    recente. Os 3 choropleths (Densidade/Renda/Score) foram consolidados em um unico slide
    "Mapas de calor" (tira 1x3 lado a lado) no BLK-RELPON-01; o BLK-RELPON-07 inseriu a
    pagina "Perfil do Bairro/Distrito" entre Concorrentes e Big Numbers (5->6 paginas).
    Difere do recente na ESTETICA: banda turquesa com margem/cantos arredondados e icone
    Ultra, capa com endereco acima do subtitulo, banda magenta de rodape e Realizacao com
    link clicavel + data por extenso. READ-ONLY sobre o M1.

    `rotulo` e o nome/endereco do ponto (capa + banda + texto do link). `perfil_bairro`
    (BLK-RELPON-07) e o dict de `agregar_perfil_bairro_distrito`; `None` (default) produz a
    pagina com "n/d" gracioso. `now` e injetavel para data determinista em teste. Geracao
    100% offline, sem PII. Marca d'agua identica ao gerador recente (`solicitante`).
    """
    assets = _load_branding_assets(ultra_dir)
    layers = dict(_normalize_mapas_by_key(mapas))
    banda_texto = _classico_banda_texto(result, rotulo)

    # Tom principal alterna por pagina de conteudo (turquesa <-> magenta). BLK-RELPON-01 +
    # BLK-RELPON-07: 4 paginas de conteudo (Mapas de calor=1, Concorrentes=2, Perfil do
    # Bairro/Distrito=3, Big Numbers=4).
    p1, _ = _tema_bicolor(1)
    p2, s2 = _tema_bicolor(2)
    p3, s3 = _tema_bicolor(3)
    p4, s4 = _tema_bicolor(4)

    pdf = _UltraPDF()
    _classico_cover_page(pdf, result, assets, rotulo=rotulo, now=now)
    # BLK-SAT-01: vista aerea logo apos a capa (pagina propria, nao disputa as vagas de fotos).
    if foto_satelite:
        _foto_satelite_page(pdf, foto_satelite, assets, primary=p1, grande=foto_satelite_grande)
    if fotos:
        _fotos_imovel_page(pdf, fotos, assets, primary=p1)
    if info_imovel:
        _info_imovel_page(pdf, info_imovel, assets, primary=p2, secondary=s2)
    _classico_mapas_calor_page(pdf, layers, assets, banda_texto=banda_texto, primary=p1)
    _classico_competitors_page(
        pdf, result, layers.get("concorrentes"), assets, banda_texto=banda_texto,
        primary=p2, secondary=s2,
    )
    _classico_perfil_bairro_page(
        pdf, perfil_bairro, assets, banda_texto=banda_texto, primary=p3, secondary=s3,
    )
    _big_numbers_page(pdf, result, residual, assets, primary=p4, secondary=s4)
    _classico_banda_magenta_rodape(pdf)
    if viabilidade:
        _viabilidade_page(pdf, viabilidade, assets, primary=p1, secondary=p2)
    _classico_credit_page(pdf, result, assets, rotulo=rotulo, now=now)

    # Marca d'agua identica ao gerador recente: capa branca, demais cinza.
    wm_text = _watermark_text(solicitante)
    for page_number in range(1, pdf.pages_count + 1):
        pdf.page = page_number
        rgb = _WATERMARK_RGB_COVER if page_number == 1 else _WATERMARK_RGB
        _draw_watermark(pdf, wm_text, rgb=rgb)

    output = pdf.output()
    return bytes(output)


def _normalize_mapas(mapas: dict[str, bytes] | bytes | None) -> list[tuple[str, str, bytes]]:
    """Normaliza a entrada de mapas em lista ordenada (chave, titulo, png_bytes).

    Retrocompat: `bytes` (1 mapa legado) -> 1 pagina "Populacao"; `dict` -> 1 pagina por
    camada canonica presente (densidade/renda/concorrentes), nessa ordem.
    """
    if mapas is None:
        return []
    if isinstance(mapas, (bytes, bytearray)):
        return [("densidade", MAP_LAYER_TITLES[0][1], bytes(mapas))] if mapas else []
    ordered: list[tuple[str, str, bytes]] = []
    for key, title in MAP_LAYER_TITLES:
        png = mapas.get(key)
        if png:
            ordered.append((key, title, png))
    return ordered


def gerar_pdf_relatorio_pontual_censitario(
    result: dict[str, Any],
    mapas: dict[str, bytes] | bytes | None = None,
    *,
    residual: dict[str, Any] | None = None,
    perfil_bairro: dict[str, Any] | None = None,
    ultra_dir: Path | str | None = None,
    solicitante: str | None = None,
    rotulo: str | None = None,
    fotos: list[bytes] | None = None,
    info_imovel: dict[str, Any] | None = None,
    viabilidade: dict[str, Any] | None = None,
    foto_satelite: bytes | None = None,
    foto_satelite_grande: bool = False,
) -> bytes:
    """Gera o PDF do Relatorio Pontual Censitario com template Ultra (fpdf2, offline).

    Estrutura de 6 paginas (BLK-RELPON-01 + BLK-RELPON-07): Capa -> Mapas de calor ->
    Concorrentes -> Perfil do Bairro/Distrito -> Big Numbers -> Realizacao/Credito. Os 3
    choropleths (Densidade/Renda/Score) — antes 1 pagina cada — foram consolidados em UM
    slide "Mapas de calor" (tira 1x3 lado a lado); o BLK-RELPON-07 inseriu a pagina "Perfil
    do Bairro/Distrito" entre Concorrentes e Big Numbers (5->6 paginas).

    `mapas` aceita o dict de camadas combinadas (`{"densidade","renda","score",
    "concorrentes"}`) ou `bytes` (1 mapa legado, retrocompat). O slide "Mapas de calor" embute
    os 3 choropleths (score usa modo de cor + legenda); a pagina de Concorrentes usa o mapa
    so-pins. `residual` carrega os campos do lookup hex (READ-ONLY) para o Big Numbers.
    `perfil_bairro` (BLK-RELPON-07) e o dict de `agregar_perfil_bairro_distrito` (4 cards
    agregados sobre TODO o bairro/distrito, nao o raio); `None` (default) produz a pagina com
    "n/d" gracioso. `ultra_dir` aponta os assets de branding (fallback gracioso para cor
    solida se ausentes). `solicitante` (BLK-EST-01) carimba a marca d'agua diagonal de
    rastreabilidade em TODAS as 6 paginas: None -> so "Ultra Academia"; preenchido ->
    "Ultra Academia | {solicitante}". Geracao 100% offline, sem PII.
    """
    assets = _load_branding_assets(ultra_dir)
    layers = dict(_normalize_mapas_by_key(mapas))

    # Tom principal alterna por pagina de conteudo (turquesa <-> magenta). BLK-RELPON-01 +
    # BLK-RELPON-07: 4 paginas de conteudo (Mapas de calor=1, Concorrentes=2, Perfil do
    # Bairro/Distrito=3, Big Numbers=4).
    p1, _ = _tema_bicolor(1)
    p2, s2 = _tema_bicolor(2)
    p3, s3 = _tema_bicolor(3)
    p4, s4 = _tema_bicolor(4)

    pdf = _UltraPDF()
    _cover_page(pdf, result, assets, rotulo=rotulo)
    # BLK-SAT-01: vista aerea logo apos a capa — o leitor situa o imovel antes de ver
    # qualquer numero. Pagina propria: nao disputa as 2 vagas de `fotos`.
    if foto_satelite:
        _foto_satelite_page(pdf, foto_satelite, assets, primary=p1, grande=foto_satelite_grande)
    if fotos:
        _fotos_imovel_page(pdf, fotos, assets, primary=p1)
    if info_imovel:
        _info_imovel_page(pdf, info_imovel, assets, primary=p2, secondary=s2)
    _mapas_calor_page(pdf, layers, assets, primary=p1)
    _competitors_page(pdf, result, layers.get("concorrentes"), assets, primary=p2, secondary=s2)
    _perfil_bairro_page(pdf, perfil_bairro, assets, primary=p3, secondary=s3)
    _big_numbers_page(pdf, result, residual, assets, primary=p4, secondary=s4)
    if viabilidade:
        _viabilidade_page(pdf, viabilidade, assets, primary=p1, secondary=p2)
    _credit_page(pdf, assets)

    # Marca d'agua diagonal POR CIMA do conteudo de cada pagina (BLK-EST-01, D2=todas as 6).
    # Escrever na pagina `n` via `pdf.page = n` ANEXA ao stream dessa pagina -> sobreposicao.
    wm_text = _watermark_text(solicitante)
    for page_number in range(1, pdf.pages_count + 1):
        pdf.page = page_number
        rgb = _WATERMARK_RGB_COVER if page_number == 1 else _WATERMARK_RGB
        _draw_watermark(pdf, wm_text, rgb=rgb)

    output = pdf.output()
    return bytes(output)


def _normalize_mapas_by_key(mapas: dict[str, bytes] | bytes | None) -> list[tuple[str, bytes]]:
    """Mapa chave-canonica -> png_bytes (preserva retrocompat de bytes unico)."""
    return [(key, png) for key, _title, png in _normalize_mapas(mapas)]


def gerar_payloads_download_relatorio_censitario(
    result: dict[str, Any],
    mapas: dict[str, bytes] | bytes | None = None,
    *,
    filename_prefix: str | None = None,
    residual: dict[str, Any] | None = None,
    perfil_bairro: dict[str, Any] | None = None,
    ultra_dir: Path | str | None = None,
    solicitante: str | None = None,
    template: str | None = None,
    rotulo: str | None = None,
    fotos: list[bytes] | None = None,
    info_imovel: dict[str, Any] | None = None,
    viabilidade: dict[str, Any] | None = None,
) -> RelatorioCensitarioDownloadPayloads:
    prefix = filename_prefix or f"relatorio_pontual_censitario_{_point_name(result)}"
    if template == "classico":
        pdf_bytes = gerar_pdf_relatorio_pontual_classico(
            result, mapas, residual=residual, perfil_bairro=perfil_bairro, ultra_dir=ultra_dir,
            solicitante=solicitante, rotulo=rotulo,
            fotos=fotos, info_imovel=info_imovel, viabilidade=viabilidade,
        )
    else:
        pdf_bytes = gerar_pdf_relatorio_pontual_censitario(
            result, mapas, residual=residual, perfil_bairro=perfil_bairro, ultra_dir=ultra_dir,
            solicitante=solicitante, rotulo=rotulo,
            fotos=fotos, info_imovel=info_imovel, viabilidade=viabilidade,
        )
    return RelatorioCensitarioDownloadPayloads(
        csv_bytes=gerar_csv_setores_censitarios(result),
        csv_filename=f"{prefix}_setores.csv",
        pdf_bytes=pdf_bytes,
        pdf_filename=f"{prefix}.pdf",
    )


def render_downloads_relatorio_censitario(
    st_module: Any,
    result: dict[str, Any],
    mapas: dict[str, bytes] | bytes | None = None,
    *,
    filename_prefix: str | None = None,
    residual: dict[str, Any] | None = None,
    perfil_bairro: dict[str, Any] | None = None,
    ultra_dir: Path | str | None = None,
    solicitante: str | None = None,
    template: str | None = None,
    rotulo: str | None = None,
    fotos: list[bytes] | None = None,
    info_imovel: dict[str, Any] | None = None,
    viabilidade: dict[str, Any] | None = None,
) -> RelatorioCensitarioDownloadPayloads:
    """Renderiza botoes Streamlit e retorna os mesmos bytes para testes/reuso."""
    payloads = gerar_payloads_download_relatorio_censitario(
        result,
        mapas,
        filename_prefix=filename_prefix,
        residual=residual,
        perfil_bairro=perfil_bairro,
        ultra_dir=ultra_dir,
        solicitante=solicitante,
        template=template,
        rotulo=rotulo,
        fotos=fotos,
        info_imovel=info_imovel,
        viabilidade=viabilidade,
    )
    st_module.download_button(
        "Baixar CSV dos setores",
        data=payloads.csv_bytes,
        file_name=payloads.csv_filename,
        mime="text/csv",
    )
    st_module.download_button(
        "Baixar PDF executivo",
        data=payloads.pdf_bytes,
        file_name=payloads.pdf_filename,
        mime="application/pdf",
    )
    return payloads
