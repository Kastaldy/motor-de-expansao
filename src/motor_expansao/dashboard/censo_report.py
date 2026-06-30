from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
from fpdf import FPDF
from PIL import Image

from motor_expansao.api.maps_geocoder import build_search_url
from motor_expansao.dashboard.censo_point import METODO_RELATORIO_PONTUAL_CENSITARIO

# Cabecalhos canonicos das 7 paginas do template Ultra (ASCII, sem acento problematico).
# Cada string PRECISA aparecer nos bytes crus do PDF (compressao desativada no writer).
# Ordem das paginas (BLK-CENSO-03-FU5): Concorrentes ANTES de Big Numbers; pagina de
# Score censitario (choropleth) restaurada.
PDF_SECTION_HEADERS = (
    "Relatorio Pontual Censitario",
    "Populacao",
    "Renda",
    "Score censitario",
    "Concorrentes",
    "Big Numbers",
    "Realizacao",
)

# Camadas de mapa (chave canonica -> titulo da pagina de mapa no PDF). Ordem fixa.
# `score` (BLK-CENSO-03-FU5) e o choropleth de score censitario COM legenda; a camada
# `concorrentes` e o mapa SO de pins (basemap + pins Ultra/concorrentes + ponto central),
# SEM choropleth — renderizada na pagina de Concorrentes (`_competitors_page`).
MAP_LAYER_TITLES: tuple[tuple[str, str], ...] = (
    ("densidade", "Populacao - Densidade"),
    ("renda", "Renda per capita"),
    ("score", "Score censitario"),
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

# Atribuicao de tiles (DEC-004) — sempre presente no rodape de cada pagina de mapa/credito.
_ATRIBUICAO_TILES = "(c) OpenStreetMap, (c) CARTO"
_CREDITO_ULTRA = "Relatorio gerado pelo Motor de Expansao - Ultra Academia"

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

# Marca d'agua diagonal de rastreabilidade (BLK-EST-01) — embutida em TODAS as 7 paginas com
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
    "marco",
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


def _draw_map(pdf: _UltraPDF, png_bytes: bytes) -> None:
    """Desenha o PNG do mapa centralizado abaixo da faixa de titulo (area 16:9)."""
    dims = _png_dimensions(png_bytes)
    if dims is None:
        return
    img_w, img_h = dims
    max_w, max_h = 900.0, 442.0
    scale = min(max_w / img_w, max_h / img_h)
    draw_w = img_w * scale
    draw_h = img_h * scale
    x = (_PAGE_W - draw_w) / 2.0
    y = 56.0 + (max_h - draw_h) / 2.0
    try:
        pdf.image(BytesIO(png_bytes), x=x, y=y, w=draw_w, h=draw_h)
    except Exception:
        pass


def _classico_draw_map(pdf: _UltraPDF, png_bytes: bytes) -> None:
    """Desenha o PNG do mapa na area do template CLASSICO (ABAIXO da banda + titulo de secao).

    Diferente de `_draw_map` (calibrado para a banda flush do template recente, que comeca em
    y=56): aqui o topo respeita a banda classica (margem 20 + altura ~58) e o titulo da secao
    logo abaixo (~y114), e o rodape em y~518. Mantem proporcao (sem distorcer) e centraliza.
    """
    dims = _png_dimensions(png_bytes)
    if dims is None:
        return
    img_w, img_h = dims
    top = _CLASSICO_MARGIN + _CLASSICO_BAND_H + 12.0 + 24.0 + 8.0  # banda + gap + titulo + folga (~122)
    bottom = _PAGE_H - 30.0  # acima do rodape (y~518)
    max_w = _PAGE_W - 2.0 * _CLASSICO_MARGIN  # respeita a margem lateral de 20px
    max_h = bottom - top
    scale = min(max_w / img_w, max_h / img_h)
    draw_w = img_w * scale
    draw_h = img_h * scale
    x = (_PAGE_W - draw_w) / 2.0
    y = top + (max_h - draw_h) / 2.0
    try:
        pdf.image(BytesIO(png_bytes), x=x, y=y, w=draw_w, h=draw_h)
    except Exception:
        pass


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
    pdf.multi_cell(block_w, 32, _ascii("Relatorio Pontual Censitario"), align=align)

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
    pdf.cell(block_w, 18, _ascii(f"Raio de analise: {raio}"), align=align)


def _map_page(
    pdf: _UltraPDF,
    png_bytes: bytes | None,
    *,
    title: str,
    assets: dict[str, bytes | None],
    primary: tuple[int, int, int] = ULTRA_TURQUESA,
) -> None:
    """Pagina de mapa: fundo claro, faixa de titulo (tom da pagina), mapa, rodape com atribuicao."""
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, title, rgb=primary)
    if png_bytes:
        _draw_map(pdf, png_bytes)
    else:
        pdf.set_text_color(*_CINZA_TEXTO)
        pdf.set_font("Helvetica", "", 12)
        pdf.set_xy(40, 120)
        pdf.cell(_PAGE_W - 80, 18, _ascii("Mapa indisponivel para esta camada."))
    _draw_footer(pdf, with_attribution=True)


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
    cards = [
        ("Populacao total no raio", _format_number(result.get("pop_total_raio"), 0)),
        ("Renda per capita media", "R$ " + _format_number(result.get("renda_per_capita_media_raio"), 2)),
        ("Score censitario medio", _format_number(result.get("score_setor_medio"), 2)),
        ("Score censitario maximo", _format_number(result.get("score_setor_max"), 2)),
        ("SAM Fitness (alunos)", _format_number(residual.get("sam_fitness_potencial"), 0)),
        ("Residual Fitness (alunos)", _format_number(residual.get("oferta_efetiva_disponivel"), 0)),
        ("Concorrentes no raio", _format_number(result.get("n_concorrentes"), 0)),
        ("Consumo concorrentes (est.)", _format_number(residual.get("oferta_consumida_mercado_estimada"), 0)),
    ]

    # D3=B (BLK-EST-02): cards mais altos/arejados (156) com borda fina e barra acento 6 pt.
    margin_x = 36.0
    top = 70.0
    gap = 16.0
    cols, rows = 4, 2
    card_w = (_PAGE_W - 2 * margin_x - (cols - 1) * gap) / cols
    card_h = 156.0
    # Barras de destaque dos cards seguem o tom da pagina (primaria + acento).
    accents = [primary, secondary]

    for index, (label, value) in enumerate(cards):
        col = index % cols
        row = index // cols
        x = margin_x + col * (card_w + gap)
        y = top + row * (card_h + gap)
        # Cartao branco com barra de destaque e borda fina (D3=B).
        pdf.set_fill_color(*_BRANCO)
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
        pdf.set_text_color(40, 40, 40)
        pdf.set_font("Helvetica", "B", 26)
        pdf.set_xy(x + 14, y + 88)
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
            "Fontes: pop/renda/score = censo (intersecao de setores IBGE 2022 com circulo de 1.5 km, "
            f"metodo {metodo}); SAM Fitness, Residual Fitness (em alunos) e consumo = lookup READ-ONLY "
            "do hex H3 (sem recalculo do M1). 'n/d' = dado ausente para o ponto."
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
    pdf.cell(_PAGE_W - 80, 40, _ascii("Realizacao"), align="C")

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
            "Intersecao de setores censitarios IBGE 2022 com circulo de 1,5 km; "
            "distribuicao intrassetor por area."
        ),
        align="C",
    )

    pdf.set_xy(160, 322)
    pdf.multi_cell(
        _PAGE_W - 320,
        16,
        _ascii(
            "READ-ONLY: este relatorio nao altera score_priorizacao, carteira, plano ou artefatos "
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
    return "Relatorio Pontual Censitario"


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
    subtitulo = f"Relatorio Pontual Censitario - Raio 1,5 km | {_classico_mes_ano(now)}"

    # Zona limpa inferior-direita quando ha fundo de marca; centro quando nao ha.
    base_x = 478.0 if has_bg else 80.0
    pdf.set_text_color(*_BRANCO)
    # Endereco ACIMA (baseline ~y430), subtitulo ABAIXO (baseline ~y455, acima da linha ~y460).
    pdf.set_font("Helvetica", "B", 26)
    pdf.text(base_x, 430.0, _ascii(endereco))
    pdf.set_font("Helvetica", "", 13)
    pdf.text(base_x, 455.0, _ascii(subtitulo))


def _classico_map_page(
    pdf: _UltraPDF,
    png_bytes: bytes | None,
    *,
    banda_texto: str,
    titulo_secao: str,
    assets: dict[str, bytes | None],
    primary: tuple[int, int, int] = ULTRA_TURQUESA,
) -> None:
    """Pagina de mapa classica: fundo claro + banda classica + mapa (reuso) + rodape."""
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _classico_title_band(pdf, banda_texto, titulo_secao, assets, rgb=primary)
    if png_bytes:
        _classico_draw_map(pdf, png_bytes)
    else:
        pdf.set_text_color(*_CINZA_TEXTO)
        pdf.set_font("Helvetica", "", 12)
        pdf.set_xy(40, 160)
        pdf.cell(_PAGE_W - 80, 18, _ascii("Mapa indisponivel para esta camada."))
    _draw_footer(pdf, with_attribution=True)


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
    pdf.cell(_PAGE_W - 80, 40, _ascii("Realizacao"), align="C")

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_xy(40, 172)
    pdf.cell(_PAGE_W - 80, 24, _ascii(_CREDITO_ULTRA), align="C")

    pdf.set_font("Helvetica", "", 12)
    pdf.set_xy(160, 218)
    pdf.multi_cell(
        _PAGE_W - 320,
        16,
        _ascii(
            "Intersecao de setores censitarios IBGE 2022 com circulo de 1,5 km; "
            "distribuicao intrassetor por area."
        ),
        align="C",
    )

    pdf.set_xy(160, 262)
    pdf.multi_cell(
        _PAGE_W - 320,
        16,
        _ascii(
            "READ-ONLY: este relatorio nao altera score_priorizacao, carteira, plano ou artefatos "
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
    pdf.cell(_PAGE_W - 80, 16, _ascii("Link para localizacao do ponto:"), align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_xy(40, 350)
    pdf.cell(_PAGE_W - 80, 16, _ascii(link_label), align="C", link=url)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_xy(40, 380)
    pdf.cell(
        _PAGE_W - 80,
        16,
        _ascii(f"Data de geracao: {_classico_data_extenso(now)}"),
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
    ultra_dir: Path | str | None = None,
    solicitante: str | None = None,
    rotulo: str | None = None,
    now: datetime | None = None,
) -> bytes:
    """Gera o PDF "Apresentacao Classica Ultra" (estetica GeoFusion antiga, motor novo).

    7 paginas na ordem canonica (Capa -> Populacao -> Renda -> Score censitario ->
    Concorrentes -> Big Numbers -> Realizacao), reusando o motor/helpers do template
    recente. Difere do recente na ESTETICA: banda turquesa com margem/cantos arredondados
    e icone Ultra, capa com endereco acima do subtitulo, banda magenta de rodape e
    Realizacao com link clicavel + data por extenso. READ-ONLY sobre o M1.

    `rotulo` e o nome/endereco do ponto (capa + banda + texto do link). `now` e injetavel
    para data determinista em teste. Geracao 100% offline, sem PII. Marca d'agua identica
    ao gerador recente (`solicitante`).
    """
    assets = _load_branding_assets(ultra_dir)
    layers = dict(_normalize_mapas_by_key(mapas))
    banda_texto = _classico_banda_texto(result, rotulo)

    # Tom principal alterna por pagina de conteudo (turquesa <-> magenta).
    p1, _ = _tema_bicolor(1)
    p2, _ = _tema_bicolor(2)
    p3, _ = _tema_bicolor(3)
    p4, s4 = _tema_bicolor(4)
    p5, s5 = _tema_bicolor(5)

    pdf = _UltraPDF()
    _classico_cover_page(pdf, result, assets, rotulo=rotulo, now=now)
    _classico_map_page(
        pdf, layers.get("densidade"), banda_texto=banda_texto,
        titulo_secao="Populacao - Densidade", assets=assets, primary=p1,
    )
    _classico_map_page(
        pdf, layers.get("renda"), banda_texto=banda_texto,
        titulo_secao="Renda per capita", assets=assets, primary=p2,
    )
    _classico_map_page(
        pdf, layers.get("score"), banda_texto=banda_texto,
        titulo_secao="Score censitario", assets=assets, primary=p3,
    )
    _classico_competitors_page(
        pdf, result, layers.get("concorrentes"), assets, banda_texto=banda_texto,
        primary=p4, secondary=s4,
    )
    _big_numbers_page(pdf, result, residual, assets, primary=p5, secondary=s5)
    _classico_banda_magenta_rodape(pdf)
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
    ultra_dir: Path | str | None = None,
    solicitante: str | None = None,
    rotulo: str | None = None,
) -> bytes:
    """Gera o PDF do Relatorio Pontual Censitario com template Ultra (fpdf2, offline).

    Estrutura de 7 paginas (BLK-CENSO-03-FU5): Capa -> Populacao -> Renda ->
    Score censitario -> Concorrentes -> Big Numbers -> Realizacao/Credito.

    `mapas` aceita o dict de camadas combinadas (`{"densidade","renda","score",
    "concorrentes"}`) ou `bytes` (1 mapa legado, retrocompat). A pagina de Score censitario
    usa o choropleth de score (modo de cor + legenda); a de Concorrentes usa o mapa so-pins.
    `residual` carrega os campos do lookup hex (READ-ONLY) para o Big Numbers. `ultra_dir`
    aponta os assets de branding (fallback gracioso para cor solida se ausentes). `solicitante`
    (BLK-EST-01) carimba a marca d'agua diagonal de rastreabilidade em TODAS as 7 paginas:
    None -> so "Ultra Academia"; preenchido -> "Ultra Academia | {solicitante}". Geracao
    100% offline, sem PII.
    """
    assets = _load_branding_assets(ultra_dir)
    layers = dict(_normalize_mapas_by_key(mapas))

    # Tom principal alterna por pagina de conteudo (turquesa <-> magenta).
    p1, _ = _tema_bicolor(1)
    p2, _ = _tema_bicolor(2)
    p3, _ = _tema_bicolor(3)
    p4, s4 = _tema_bicolor(4)
    p5, s5 = _tema_bicolor(5)

    pdf = _UltraPDF()
    _cover_page(pdf, result, assets, rotulo=rotulo)
    _map_page(pdf, layers.get("densidade"), title="Populacao - Densidade", assets=assets, primary=p1)
    _map_page(pdf, layers.get("renda"), title="Renda per capita", assets=assets, primary=p2)
    _map_page(pdf, layers.get("score"), title="Score censitario", assets=assets, primary=p3)
    _competitors_page(pdf, result, layers.get("concorrentes"), assets, primary=p4, secondary=s4)
    _big_numbers_page(pdf, result, residual, assets, primary=p5, secondary=s5)
    _credit_page(pdf, assets)

    # Marca d'agua diagonal POR CIMA do conteudo de cada pagina (BLK-EST-01, D2=todas as 7).
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
    ultra_dir: Path | str | None = None,
    solicitante: str | None = None,
    template: str | None = None,
    rotulo: str | None = None,
) -> RelatorioCensitarioDownloadPayloads:
    prefix = filename_prefix or f"relatorio_pontual_censitario_{_point_name(result)}"
    if template == "classico":
        pdf_bytes = gerar_pdf_relatorio_pontual_classico(
            result, mapas, residual=residual, ultra_dir=ultra_dir,
            solicitante=solicitante, rotulo=rotulo,
        )
    else:
        pdf_bytes = gerar_pdf_relatorio_pontual_censitario(
            result, mapas, residual=residual, ultra_dir=ultra_dir,
            solicitante=solicitante, rotulo=rotulo,
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
    ultra_dir: Path | str | None = None,
    solicitante: str | None = None,
    template: str | None = None,
    rotulo: str | None = None,
) -> RelatorioCensitarioDownloadPayloads:
    """Renderiza botoes Streamlit e retorna os mesmos bytes para testes/reuso."""
    payloads = gerar_payloads_download_relatorio_censitario(
        result,
        mapas,
        filename_prefix=filename_prefix,
        residual=residual,
        ultra_dir=ultra_dir,
        solicitante=solicitante,
        template=template,
        rotulo=rotulo,
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
