from __future__ import annotations

import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
from fpdf import FPDF
from PIL import Image, ImageOps

from motor_expansao.api.maps_geocoder import build_search_url
from motor_expansao.dashboard.censo_point import (
    METODO_RELATORIO_PONTUAL_CENSITARIO,
    RAIO_CENSITARIO_DEFAULT_KM,
)

# Cabecalhos canonicos das 7 paginas do template Ultra. Renderizam em latin-1 (core font
# Helvetica do fpdf2), que cobre integralmente os acentos portugueses -- o que e PROIBIDO e
# tipografia fora de latin-1 (travessao/bullet/seta/reticencias/aspas curvas/(c)), que vira
# "?" silenciosamente via _ascii(..., errors="replace").
# Cada string PRECISA aparecer nos bytes crus do PDF (compressao desativada no writer).
# Historico da ordem das paginas: o BLK-RELPON-01 consolidou os 3 choropleths
# (Densidade/Renda/Score) em UM slide "Mapas de calor"; o BLK-RELPON-07 inseriu "Perfil do
# Bairro/Distrito" entre Concorrentes e Big Numbers; e o grid do slide de mapas passou a 2x2
# com 4 camadas (densidade/renda/score/renda_domiciliar) -> 6 paginas. BLK-RELPON-10: novo
# slide-hero "Socioeconomia e Residual Fitness" ANTES de "Mapas de calor" -> 7 paginas.
# BLK-RELPON-11 (caminho A1, gate Vinicius 2026-07-22) inseriu "Imagem do Entorno" (mapa de
# quadra) entre a Capa e o slide-hero -> 8 paginas; o BLK-RELPON-14 REMOVEU esse slide por
# completo (camada PNG + paginas do PDF + constantes) -> de volta a 7 paginas:
# Capa -> Socioeconomia e Residual Fitness -> Mapas de calor -> Concorrentes ->
# Perfil do Bairro/Distrito -> Big Numbers -> Realizacao.
# As paginas OPCIONAIS nao entram nesta tupla: fotos do imovel, info do imovel e as 2 de
# viabilidade (numeros + graficos) levam o PDF ao teto de 11 paginas (era 12 com o entorno);
# a vista aerea (BLK-SAT, so no caminho API/bot) soma mais uma quando presente.
PDF_SECTION_HEADERS = (
    "Relatório Pontual Censitário",
    "Socioeconomia e Residual Fitness",
    "Mapas de calor",
    "Concorrentes",
    "Perfil do Bairro/Distrito",
    "Big Numbers",
    "Realização",
)

# Camadas de mapa (chave canonica -> titulo da pagina de mapa no PDF). Ordem fixa.
# `score` (BLK-CENSO-03-FU5) e o choropleth de score censitario COM legenda; a camada
# `concorrentes` e o mapa SO de pins (basemap + pins Ultra/concorrentes + ponto central),
# SEM choropleth — renderizada na pagina de Concorrentes (`_classico_competitors_page`).
# BLK-RELPON-05 (faixa REVERTIDA para os agregados do raio pelo BLK-RELPON-06/D1): os
# PNGs de densidade/renda/score que chegam aqui ja trazem "assada" a faixa superior com
# o valor do raio vigente (produzida em
# `censo_map.render_mapas_censitarios_combinados`/`_render_camada`); este modulo recebe
# `mapas: dict[str, bytes]` ja pronto e so embute os bytes (`_classico_mapas_calor_page`
# via `_draw_maps_grid`/`_map_grid_cells`), sem nenhuma
# mudanca de logica. As fontes maiores do BLK-RELPON-06 (D4) tambem vem embutidas nos
# bytes do PNG (UM unico render p/ dashboard/PDF/API) -- nada muda neste modulo.
# BLK-RELPON-10: `socioeconomia` e `residual` sao as 2 camadas do slide-hero. Sem estarem NESTA
# tupla, `_normalize_mapas` as descartaria em SILENCIO (ela so repassa chaves listadas aqui) e o
# slide novo sairia com dois fallbacks textuais. Ficam APOS `renda_domiciliar` de proposito:
# `MAP_LAYER_TITLES[0]` e' o titulo do caminho retrocompativel de `bytes` unico (1 mapa legado ->
# "densidade"), entao `densidade` tem de continuar no indice 0. A ordem desta tupla NAO define a
# ordem das paginas (a composicao usa `layers.get(<chave>)`).
# BLK-RELPON-14: a chave `entorno` (mapa de quadra do BLK-RELPON-11) SAIU junto com o slide
# "Imagem do Entorno"; `_normalize_mapas` volta a descartar essa chave em silencio, que e o
# comportamento desejado agora (a camada tambem deixou de ser produzida em `censo_map`).
MAP_LAYER_TITLES: tuple[tuple[str, str], ...] = (
    ("densidade", "População - Densidade"),
    ("renda", "Renda per capita"),
    ("score", "Score censitário"),
    ("renda_domiciliar", "Renda média domiciliar"),
    ("socioeconomia", "Socioeconomia"),
    ("residual", "Residual Fitness"),
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

# DEC-021: o raio VISIVEL deriva do canonico, nunca mais e' digitado. Este arquivo tinha 6 strings
# "1,5 km" hardcoded e ZERO referencia a `raio_km` — trocar o raio deixaria o motor calculando um
# valor e o PDF estampando outro, errado em SILENCIO para quem le o relatorio. O rodape dos MAPAS
# ja era dinamico desde o BLK-RELPON-10 (`censo_map.py`); aqui nao era.
_RAIO_TXT = f"{RAIO_CENSITARIO_DEFAULT_KM:.1f}".replace(".", ",")  # "1,0"
_RAIO_LABEL = f"{_RAIO_TXT} km"

# BLK-RELPON-08 (D3/Q4): metas do semaforo de cor dos 8 cards do Big Numbers. Verde quando o
# valor bate a meta; vermelho quando nao bate; neutro quando "n/d" (Q2, indecidivel). Constantes
# nomeadas e auditaveis (nao hardcoded inline dentro de `_big_numbers_page`).
# DEC-021 (raio 1,5 -> 1,0 km): as metas de TOTAL sao ABSOLUTAS e foram calibradas para a area
# de 1,5 km. Com 1,0 km a area cai para (1,0/1,5)^2 = 44,4%, logo populacao e domicilios no raio
# caem ~56% por MUDANCA DE ESCALA, sem nada piorar na praca analisada.
#
# DECISAO DE FELIPE (2026-07-30), consultado explicitamente: os cortes FICAM como estao —
# "pode manter o corte de 10k populacao mesmo com a mudanca do Raio e dos dados num geral".
# Consequencia assumida, registrada para nao virar surpresa: o limiar IMPLICITO de densidade
# sobe de ~1.415 para ~3.183 hab/km2 (10.000 / 3,14 km2), ou seja o card fica MAIS DIFICIL de
# ficar verde — passa a exigir mais que o dobro da densidade de antes. E' endurecimento
# deliberado do criterio, nao efeito colateral.
#
# As metas de MEDIA (renda per capita, renda domiciliar, score) sao escala-invariantes e nao
# seriam afetadas de todo jeito. Idem SAM/Residual Fitness, que sao por hexagono H3.
_META_POP_TOTAL_RAIO = 10_000.0
_META_RENDA_PER_CAPITA_MEDIA_RAIO = 1_500.0
# Renda media domiciliar TOTAL (com uplift): verde a partir de 4.000 -- pedido de Felipe
# (2026-07-23, "acima de R$ 4.000 o card NAO deve vir vermelho") e confirmado por Vinicius no
# gate visual do BLK-RELPON-13 (2026-07-24); substitui o alvo anterior de 6.200 (~C1 GeoFusion).
# Alinha com a 1a faixa "verde" das bandas.
_META_RENDA_DOMICILIAR_TOTAL_RAIO = 4_000.0
_META_DOMICILIOS_TOTAL_RAIO = 3_000.0  # mantido junto com a meta de populacao (decisao de Felipe,
# 2026-07-30): manter uma reescalada e a outra nao deixaria o semaforo com duas filosofias.
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
    """(primary, secondary) por pagina de CONTEUDO, alternando o tom principal.

    Pedido Vinicius (2026-06-29): as paginas devem alternar entre turquesa e magenta como cor
    principal. Pagina impar -> turquesa primaria / magenta acento; par -> magenta primaria /
    turquesa acento. Aplica-se SO ao chrome decorativo (faixa de titulo + cabecalho/acento
    decorativo principal). Cores SEMANTICAS (Ultra=turquesa, concorrente=magenta nos bullets)
    NAO entram nessa troca. READ-ONLY sobre o M1.

    BLK-RELPON-10 (DT-4): os ordinais 1..4 sao as 4 paginas de conteudo historicas; paginas
    INSERIDAS ANTES da primeira delas tomam ordinais DECRESCENTES a partir de **0** (o slide-hero
    "Socioeconomia e Residual Fitness" usa `_tema_bicolor(0)` -> magenta). O corpo da funcao NAO
    muda: `0 % 2 == 0` ja devolve (magenta, turquesa), e `p1..p4` ficam EXATAMENTE como estao ->
    ZERO inversao de cor em cascata nas paginas existentes. Uma pagina anterior a essa deve tomar
    o ordinal -1 pela mesma regra de paridade (`-1 % 2 == 1` em Python -> turquesa).

    BLK-RELPON-14: o ordinal -1 ficou LIVRE de novo — era usado so pela pagina "Imagem do
    Entorno", removida neste bloco. Os ordinais em uso hoje sao 0..4 e continuam ABSOLUTOS
    (nao um contador incremental), entao remover/inserir paginas fora dessa faixa nao muda
    a cor de nenhuma das paginas existentes.
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
# Slide consolidado "Mapas de calor" (BLK-RELPON-01, hoje GRID 2x2): as 4 camadas
# censitarias (densidade/renda/score/renda_domiciliar) num unico slide, sem
# sobreposicao. Cada PNG e embutido SEPARADAMENTE (nao pre-composto), com
# legenda embutida (D3). Fallback textual por camada ausente (offline-safe).
# O MESMO grid, com `cols=2, rows=1`, serve o slide-hero "Socioeconomia e Residual
# Fitness" do BLK-RELPON-10 (2 mapas lado a lado).
# ---------------------------------------------------------------------------
# Mensagem literal de fallback por camada de mapa faltante (usada pelas grades de mapas).
_MAPA_INDISPONIVEL = "Mapa indisponível para esta camada."


_MAP_GRID_COLS = 2
_MAP_GRID_ROWS = 2


def _map_grid_cells(
    top: float,
    bottom: float,
    margin_x: float,
    gap: float,
    *,
    cols: int = _MAP_GRID_COLS,
    rows: int = _MAP_GRID_ROWS,
) -> list[tuple[float, float, float, float]]:
    """Geometria PURA das celulas do grid (x, y, w, h), em ordem row-major. Testavel
    sem gerar PDF; compartilhada pelas variantes recente e classica (variam so top/margem).

    Largura util (`_PAGE_W - 2*margin_x - (cols-1)*gap`) dividida em `cols` colunas iguais;
    altura util (`bottom - top - (rows-1)*gap`) em `rows` linhas iguais.

    BLK-RELPON-10: `cols`/`rows` viraram keyword-only COM O DEFAULT NOS VALORES ATUAIS (2x2) ->
    o caminho do slide "Mapas de calor" fica byte-identico; o slide-hero novo pede 2x1.
    """
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
    aspect: float,
    *,
    top: float,
    bottom: float,
    gap: float,
    cols: int = _MAP_GRID_COLS,
    rows: int = _MAP_GRID_ROWS,
    scale: float = 1.0,
) -> list[tuple[float, float, float, float]]:
    """Celulas com a PROPORCAO `aspect` (largura/altura), maximizadas em altura e
    EMPACOTADAS (coladas, so o `gap`) e centralizadas -> mapas maiores/retangulares e sem o
    vao branco (letterbox) entre eles. Geometria pura, testavel sem PDF.

    BLK-RELPON-10: `cols`/`rows` com default nos valores atuais (2x2) -> caminho existente
    inalterado; o slide-hero "Socioeconomia e Residual Fitness" usa 2x1 (2 mapas lado a lado).
    BLK-RELPON-13: `scale` (default 1.0 = geometria IDENTICA) encolhe uniformemente cada celula
    APOS o clamp de largura; como a recentragem usa `total_w`/`total_h`, as celulas menores ficam
    centradas. So o slide-hero passa `scale<1.0` para reduzir um pouco as 2 imagens."""
    h_avail = bottom - top
    cell_h = (h_avail - (rows - 1) * gap) / rows
    cell_w = cell_h * aspect
    max_total_w = _PAGE_W - 2.0 * 20.0  # margem lateral minima
    if cols * cell_w + (cols - 1) * gap > max_total_w:
        cell_w = (max_total_w - (cols - 1) * gap) / cols
        cell_h = cell_w / aspect
    cell_w *= scale
    cell_h *= scale
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
    cols: int = _MAP_GRID_COLS,
    rows: int = _MAP_GRID_ROWS,
    packed_scale: float = 1.0,
) -> list[tuple[float, float, float, float]]:
    """Desenha os PNGs num grid `cols` x `rows` sem sobreposicao (default 2x2:
    [densidade, renda, score, renda_domiciliar]).

    Cada PNG e escalado para caber na sua celula preservando proporcao (`min(w,h)`) e
    centralizado dentro dela; camada `None` -> texto de fallback centralizado na celula.
    Os PNGs sao embutidos SEPARADAMENTE (nao pre-compostos) para preservar a contagem
    de `/Subtype /Image`. Retorna os bounding boxes efetivamente ocupados por cada mapa
    (imagem desenhada) ou a propria celula quando cai no fallback — usado pelo teste de
    nao-sobreposicao.

    `pack=True` (mapas de calor): as celulas assumem a PROPORCAO do proprio mapa (do 1o PNG
    valido) e sao empacotadas/centralizadas -> mapas maiores, retangulares e SEM o vao branco.
    `packed_scale` (BLK-RELPON-13, default 1.0 = geometria IDENTICA; so o ramo `pack=True` o usa)
    encolhe uniformemente as celulas empacotadas — usado so pelo slide-hero.
    """
    if pack:
        dims_ref = next((_png_dimensions(p) for p in pngs if p), None)
        aspect = (dims_ref[0] / dims_ref[1]) if dims_ref else (1000.0 / 760.0)
        cells = _map_grid_cells_packed(
            aspect, top=top, bottom=bottom, gap=gap, cols=cols, rows=rows, scale=packed_scale
        )
    else:
        cells = _map_grid_cells(top, bottom, margin_x, gap, cols=cols, rows=rows)
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


_SOCIOECONOMIA_RESIDUAL_TITULO = "Socioeconomia e Residual Fitness"
# BLK-RELPON-13: fator de escala das 2 imagens do slide-hero (1.0 = tamanho atual). Ponto de
# PARTIDA CALIBRAVEL no gate visual de Vinicius; so as paginas socioeconomia+residual o aplicam.
_HERO_MAP_SCALE = 0.85


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
# BLK-SAT (TESTE): pagina propria da vista aerea, para nao ocupar as 2 vagas de foto.
# Saida OPCIONAL (so entra se `foto_satelite` != None e a imagem for valida). O PNG e' gerado
# pelo CHAMADOR via `censo_map.render_foto_satelite_ponto` (fallback gracioso -> None sem
# chave/rede); licenca Esri, com o credito ja embutido no proprio PNG.
_SATELITE_PAGE_TITLE = "Imóvel - Vista aérea"
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


def _foto_satelite_cell_grande() -> tuple[float, float, float, float]:
    """Celula 3:2 CENTRADA ocupando a area de conteudo inteira (altura manda).

    So para o caminho da API/bot, onde a vista aerea e a UNICA imagem da pagina.
    No dashboard nao se usa: la a celula menor de `_fotos_cells` e o padrao da casa,
    dimensionada para caber ate 2 imagens.
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
    """Pagina da VISTA AEREA (BLK-SAT, TESTE): faixa de titulo + 1 foto + rodape.

    Pagina PROPRIA (nao a de fotos do imovel) para nao ocupar as 2 vagas de upload.

    `grande` dimensiona a foto:
      - False (default, DASHBOARD): mesma celula de `_fotos_cells(1)`. O tamanho menor
        e o padrao da casa — a celula acomoda ate 2 imagens e a pagina de fotos do
        imovel usa a mesma medida, entao as duas ficam consistentes.
      - True (API/BOT): ocupa a area de conteudo inteira. La NAO existe upload de fotos
        (`service.gerar_pdf_ponto` nao recebe `fotos`), entao a vista aerea e a unica
        imagem e a celula reduzida so deixaria branco sobrando.
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
# + slide de GRAFICOS (PNGs de `viabilidade_charts`).
# Saida OPCIONAL (so entra se `viabilidade` != None). READ-ONLY sobre o M1.
#
# RENDER PURO (FIN-VIAB-01, 2026-07-24): este slide so IMPRIME o `viabilidade_payload_v1`
# — o MESMO objeto que a tela consome — direto ou ja achatado por
# `viabilidade_charts.montar_payload_pdf_viabilidade`. Nao ha aqui nenhuma chamada ao motor
# de dimensionamento nem nenhuma conta financeira; era a duplicacao dessas contas que fazia
# o PDF divergir da tela no MESMO cenario (aluguel-teto R$105.813,13 x R$55.535,18,
# payback 33 x 35, acumulado M60 R$2,05 mi x R$1,89 mi). Chave ausente -> "n/d"/linha omitida.
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


def _viab_tem(value: Any) -> bool:
    """True quando o payload trouxe o campo com valor utilizavel (nao None/NaN)."""
    if value is None:
        return False
    try:
        return not bool(pd.isna(value))
    except (TypeError, ValueError):
        return True


def _viab_campo(viabilidade: Mapping[str, Any], plana: str, *caminho: str) -> Any:
    """Le o campo pela chave PLANA e, faltando ela, pelo caminho dentro do payload v1.

    O slide aceita as duas formas do mesmo objeto: o dict plano montado por
    `viabilidade_charts.montar_payload_pdf_viabilidade` e o proprio
    `viabilidade_payload_v1` que a API devolve para a tela (com ou sem as chaves planas
    de compatibilidade por cima). Em nenhum dos casos o PDF calcula: so LE.
    """
    if _viab_tem(viabilidade.get(plana)):
        return viabilidade.get(plana)
    atual: Any = viabilidade
    for chave in caminho:
        if not isinstance(atual, Mapping):
            return None
        atual = atual.get(chave)
        if atual is None:
            return None
    return atual


def _viab_normalizado(viabilidade: Mapping[str, Any]) -> dict[str, Any]:
    """Achata o payload de viabilidade nas chaves que o slide imprime (sem recalcular)."""
    teto = viabilidade.get("aluguel_teto")
    faixas = viabilidade.get("aluguel_teto_faixas")
    if not isinstance(faixas, Mapping):
        faixas = teto if isinstance(teto, Mapping) else {}
    canonico = teto.get("canonico") if isinstance(teto, Mapping) else teto

    dados: dict[str, Any] = {
        "alunos_breakeven": _viab_campo(viabilidade, "alunos_breakeven", "break_even", "ebitda"),
        "breakeven_unidade": _viab_campo(
            viabilidade, "breakeven_unidade", "break_even", "unidade"
        ),
        "breakeven_caixa": _viab_campo(viabilidade, "breakeven_caixa", "break_even", "caixa"),
        "aluguel_teto": canonico,
        "aluguel_teto_faixas": dict(faixas),
        "margem_ebitda_pct": _viab_campo(viabilidade, "margem_ebitda_pct", "dre", "margem"),
        "payback_meses": _viab_campo(viabilidade, "payback_meses", "retorno", "payback"),
        "retorno_anual": _viab_campo(
            viabilidade, "retorno_anual", "retorno", "retorno_anual_desalavancado"
        ),
        "retorno_otica": _viab_campo(viabilidade, "retorno_otica", "retorno", "otica"),
        "roic_anual": viabilidade.get("roic_anual"),
        "faturamento_mensal": _viab_campo(
            viabilidade, "faturamento_mensal", "dre", "faturamento"
        ),
        # Anuidade: parcela do faturamento acima + a regra que a gera. So LEITURA — o
        # slide imprime a linha, nao a decompoe nem a recalcula.
        "receita_anuidade": _viab_campo(viabilidade, "receita_anuidade", "dre", "receita_anuidade"),
        "anuidade_valor": _viab_campo(viabilidade, "anuidade_valor", "premissas", "anuidade_valor"),
        "anuidade_elegivel_pct": _viab_campo(
            viabilidade, "anuidade_elegivel_pct", "premissas", "anuidade_elegivel_pct"
        ),
        "anuidade_mes_inicio": _viab_campo(
            viabilidade, "anuidade_mes_inicio", "premissas", "anuidade_mes_inicio"
        ),
        "anuidade_apenas_balcao": _viab_campo(
            viabilidade, "anuidade_apenas_balcao", "premissas", "anuidade_apenas_balcao"
        ),
        # Mes de operacao a que a DRE de steady-state se refere (regime pleno: alunos
        # maduros E anuidade em cobranca). LIDO do payload — recalcular a partir de
        # `maturacao_meses` foi o que fez o waterfall divergir do card ao lado.
        "mes_referencia_steady": _viab_campo(
            viabilidade, "mes_referencia_steady", "premissas", "mes_referencia_steady"
        ),
        "ebitda_mensal": _viab_campo(viabilidade, "ebitda_mensal", "dre", "ebitda"),
        # Composicao do custo operacional do mes de steady. A folha e a unica destas linhas
        # que mudou de NATUREZA (decisao de Felipe, 2026-07-24): custo FIXO dimensionado
        # pelo faturamento MADURO e pago integralmente desde o mes 1, nao mais percentual
        # da receita do mes. So LEITURA — o slide imprime, nao recompoe o custo.
        "custos_op": _viab_campo(viabilidade, "custos_op", "dre", "custos_op"),
        "custos_variaveis": _viab_campo(viabilidade, "custos_variaveis", "dre", "custos_variaveis"),
        "folha": _viab_campo(viabilidade, "folha", "dre", "folha"),
        "custos_fixos": _viab_campo(viabilidade, "custos_fixos", "dre", "custos_fixos"),
        "folha_pct": _viab_campo(viabilidade, "folha_pct", "premissas", "folha_pct"),
        "faixa_p10": _viab_campo(viabilidade, "faixa_p10", "faixa_alunos", "p10"),
        "faixa_p90": _viab_campo(viabilidade, "faixa_p90", "faixa_alunos", "p90"),
        "pmt_mensal": _viab_campo(viabilidade, "pmt_mensal", "investimento", "pmt"),
        "juros_totais": _viab_campo(viabilidade, "juros_totais", "investimento", "juros_totais"),
        "investimento_total": _viab_campo(
            viabilidade, "investimento_total", "investimento", "investimento_total"
        ),
        # Taxa de franquia + parcelamento sem juros. `parcelas_franquia` e campo NOVO do
        # payload: quando o backend ainda nao o manda, a linha simplesmente nao afirma
        # parcelamento (degradacao graciosa, nunca um numero assumido).
        "taxa_franquia": _viab_campo(viabilidade, "taxa_franquia", "investimento", "taxa_franquia"),
        "parcelas_franquia": _viab_campo(
            viabilidade, "parcelas_franquia", "investimento", "parcelas_franquia"
        ),
        "tir_anual": _viab_campo(viabilidade, "tir_anual", "retorno", "tir_anual"),
        "vpl": _viab_campo(viabilidade, "vpl", "retorno", "vpl"),
        "acumulado_mes_final": viabilidade.get("acumulado_mes_final"),
        "mes_caixa_operacional_positivo": viabilidade.get("mes_caixa_operacional_positivo"),
        "horizonte_meses": _viab_campo(
            viabilidade, "horizonte_meses", "premissas", "horizonte_meses"
        ),
        "flag_fora_envelope": viabilidade.get("flag_fora_envelope"),
        "flag_zona_morta": viabilidade.get("flag_zona_morta"),
        "motivo_zona_morta": viabilidade.get("motivo_zona_morta"),
    }
    # `flag_viavel` e opcional: sem ele o rodape simplesmente nao afirma viabilidade.
    viavel = _viab_campo(viabilidade, "flag_viavel", "dre", "flag_viavel")
    if "flag_viavel" in viabilidade or viavel is not None:
        dados["flag_viavel"] = viavel
    return dados


def _viab_unidade_breakeven(viabilidade: dict[str, Any]) -> str:
    """Rotulo da unidade do break-even, vindo do payload (`break_even.unidade`).

    Sem o campo (payload legado), NAO se assume "alunos totais": o numero antigo variava
    so o balcao e nao era comparavel com a demanda total digitada pelo operador.
    """
    bruto = viabilidade.get("breakeven_unidade")
    if not bruto:
        return ""
    return str(bruto).replace("_", " ").strip()


def _viab_maior_que_zero(value: Any) -> bool:
    """True quando o campo veio no payload E e um numero positivo."""
    if not _viab_tem(value):
        return False
    try:
        return float(value) > 0.0
    except (TypeError, ValueError):
        return False


def _viab_inteiro(value: Any) -> int | None:
    """int do campo do payload, ou None quando ausente/NaN/nao numerico."""
    if not _viab_tem(value):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _viab_linha_receita(viabilidade: dict[str, Any]) -> str | None:
    """Linha que torna VISIVEL a composicao do faturamento e o mes do steady-state.

    A anuidade e uma receita SEPARADA da mensalidade (R$ X uma vez por ano, por aluno de
    balcao que completa N meses) e antes engordava o faturamento sem nenhuma linha
    explicando de onde vinha. Aqui tudo e LEITURA do payload: o faturamento, a parcela de
    anuidade, o valor/ano, a fracao elegivel (derivada do churn) e o mes de referencia do
    regime pleno (`premissas.mes_referencia_steady` — nunca recalculado de `maturacao`).
    """
    mes_ref = viabilidade.get("mes_referencia_steady")
    anuidade = viabilidade.get("receita_anuidade")
    tem_anuidade = _viab_maior_que_zero(anuidade)
    if not tem_anuidade and not _viab_tem(mes_ref):
        return None

    if _viab_tem(mes_ref):
        prefixo = f"Steady-state = mês {_format_number(mes_ref, 0)} (regime pleno)"
    else:
        prefixo = "Steady-state (regime pleno)"
    faturamento = _viab_brl(viabilidade.get("faturamento_mensal"))
    if not tem_anuidade:
        return f"{prefixo}. Faturamento {faturamento}, todo de mensalidades."

    detalhes: list[str] = []
    valor = viabilidade.get("anuidade_valor")
    inicio = viabilidade.get("anuidade_mes_inicio")
    if _viab_tem(valor):
        alvo = "por aluno de balcão" if viabilidade.get("anuidade_apenas_balcao") else "por aluno"
        detalhes.append(f"{_viab_brl(valor)} uma vez por ano {alvo}")
    if _viab_tem(inicio):
        detalhes.append(f"a partir do mês {_format_number(inicio, 0)} de casa")
    eleg = viabilidade.get("anuidade_elegivel_pct")
    if _viab_tem(eleg):
        detalhes.append(f"{_viab_pct(eleg)} chegam lá")
    detalhes.append("reconhecida pro-rata mensal")
    return (
        f"{prefixo}. Faturamento {faturamento} = mensalidades + anuidade "
        f"{_viab_brl(anuidade)} ({', '.join(detalhes)})."
    )


def _viab_linha_custos(viabilidade: dict[str, Any]) -> str | None:
    """Linha que descreve o CUSTO do mes de steady, com a natureza real da folha.

    A folha deixou de ser percentual do faturamento DO MES e virou custo FIXO: e
    dimensionada pelo faturamento MADURO (regime pleno) e paga integralmente desde o mes 1
    (decisao de Felipe, 2026-07-24). Sem dizer isso, o leitor supunha que a folha encolhia
    junto com a rampa — que era exatamente o defeito reportado ("a folha esta escalando
    junto com a unidade"). Consequencia visivel no proprio relatorio: o EBITDA do mes 1
    fica bem mais negativo e o break-even sobe.

    Tudo LEITURA do payload (`dre.custos_variaveis`/`dre.folha`/`dre.custos_fixos` e
    `premissas.folha_pct`). Sem a folha no payload a linha nao existe (payload legado sai
    exatamente como antes).

    A frase e deliberadamente curta: o bloco de detalhe cabe em ~9 linhas RENDERIZADAS
    acima do rodape (auto_page_break OFF), e cada quebra a mais empurra o texto para cima
    do credito Ultra. Ao mexer aqui, REGERAR o PDF e conferir as coordenadas Y.
    """
    folha = viabilidade.get("folha")
    if not _viab_maior_que_zero(folha):
        return None

    pct = viabilidade.get("folha_pct")
    base = (
        f"por {_viab_pct(pct)} do faturamento maduro"
        if _viab_tem(pct)
        else "pelo faturamento maduro"
    )
    linha = f"Folha {_viab_brl(folha)}/mês FIXA desde o mês 1, dimensionada {base}."

    # Composicao do custo do mes de steady (a folha nao se repete: acabou de ser dita).
    partes: list[str] = []
    variaveis = viabilidade.get("custos_variaveis")
    if _viab_tem(variaveis):
        partes.append(f"variáveis {_viab_brl(variaveis)}")
    partes.append("folha")
    fixos = viabilidade.get("custos_fixos")
    if _viab_tem(fixos):
        partes.append(f"fixos e aluguel {_viab_brl(fixos)}")
    if len(partes) == 1:
        return linha
    total = viabilidade.get("custos_op")
    rotulo = (
        f"Custo operacional {_viab_brl(total)}/mês" if _viab_tem(total) else "Custo operacional"
    )
    return f"{linha} {rotulo}: " + " + ".join(partes) + "."


def _viab_linha_investimento(viabilidade: dict[str, Any]) -> str | None:
    """Linha de financiamento/investimento, incluindo o parcelamento da taxa de franquia.

    A taxa de franquia e PARCELADA sem juros (4x por decisao de Felipe, 2026-07-24; antes
    saia inteira do caixa no M-4, junto da 1a parcela da obra). `parcelas_franquia` e campo
    NOVO do payload: quando ele nao vem, a frase do parcelamento simplesmente nao entra —
    o PDF nunca afirma um numero de parcelas que o backend nao mandou.
    """
    pmt = viabilidade.get("pmt_mensal")
    juros = viabilidade.get("juros_totais")
    investimento = viabilidade.get("investimento_total")
    if not any(_viab_tem(v) for v in (pmt, juros, investimento)):
        return None
    texto = (
        f"Financiamento: PMT {_viab_brl(pmt)}/mês  |  juros totais do contrato "
        f"{_viab_brl(juros)}  |  investimento total {_viab_brl(investimento)}."
    )

    n = _viab_inteiro(viabilidade.get("parcelas_franquia"))
    if n is None or n < 1:
        return texto
    taxa = viabilidade.get("taxa_franquia")
    rotulo = f"Taxa de franquia {_viab_brl(taxa)}" if _viab_tem(taxa) else "Taxa de franquia"
    if n <= 1:
        return f"{texto} {rotulo} paga de uma vez, no 1o mês de contrato."
    return f"{texto} {rotulo} parcelada em {n}x sem juros, junto da obra."


def _viab_linhas_detalhe(viabilidade: dict[str, Any]) -> list[str]:
    """Linhas de texto sob os cards. So entra a linha cujo dado veio no payload."""
    linhas: list[str] = []

    # Composicao do faturamento + mes de referencia: primeira linha, logo sob os cards.
    receita = _viab_linha_receita(viabilidade)
    if receita:
        linhas.append(receita)

    # Composicao do custo, com a folha declarada como FIXA desde o mes 1.
    custos = _viab_linha_custos(viabilidade)
    if custos:
        linhas.append(custos)

    unidade = _viab_unidade_breakeven(viabilidade)
    caixa = viabilidade.get("breakeven_caixa")
    if _viab_tem(caixa) or unidade:
        sufixo = f" {unidade}" if unidade else ""
        texto = (
            f"Break-even: {_viab_breakeven(viabilidade.get('alunos_breakeven'))}{sufixo} "
            "para EBITDA zero"
        )
        if _viab_tem(caixa):
            texto += f" e {_viab_breakeven(caixa)}{sufixo} para o caixa (cobre a PMT)"
        linhas.append(texto + ".")

    faixas = viabilidade.get("aluguel_teto_faixas") or {}
    if any(_viab_tem(faixas.get(k)) for k in ("ideal", "teto", "excecao")):
        linhas.append(
            "Aluguel-teto (base: faturamento bruto mensal): ideal "
            f"{_viab_brl(faixas.get('ideal'))}  |  teto {_viab_brl(faixas.get('teto'))}"
            f"  |  exceção {_viab_brl(faixas.get('excecao'))} - o card acima traz o canônico."
        )

    investimento_linha = _viab_linha_investimento(viabilidade)
    if investimento_linha:
        linhas.append(investimento_linha)

    tir = viabilidade.get("tir_anual")
    vpl = viabilidade.get("vpl")
    acumulado = viabilidade.get("acumulado_mes_final")
    mes_positivo = viabilidade.get("mes_caixa_operacional_positivo")
    if any(_viab_tem(v) for v in (tir, vpl, acumulado, mes_positivo)):
        horizonte = viabilidade.get("horizonte_meses")
        rotulo_acum = (
            f"acumulado no mês {_format_number(horizonte, 0)}"
            if _viab_tem(horizonte)
            else "acumulado no fim do horizonte"
        )
        texto = (
            f"TIR {_viab_pct(tir)} a.a.  |  VPL {_viab_brl(vpl)}  |  "
            f"{rotulo_acum} {_viab_brl(acumulado)}"
        )
        if _viab_tem(mes_positivo):
            texto += f"  |  caixa operacional positivo a partir do mês {_format_number(mes_positivo, 0)}"
        linhas.append(texto + ".")

    return linhas


def _viabilidade_page(
    pdf: _UltraPDF,
    viabilidade: dict[str, Any],
    assets: dict[str, bytes | None],
    *,
    primary: tuple[int, int, int] = ULTRA_TURQUESA,
    secondary: tuple[int, int, int] = ULTRA_MAGENTA,
) -> None:
    """Slide de numeros da viabilidade + (se houver) slide dos graficos. READ-ONLY M1.

    `viabilidade` e o `viabilidade_payload_v1` (ou o dict plano equivalente montado por
    `viabilidade_charts.montar_payload_pdf_viabilidade`) mais, opcionalmente, `graficos`
    (lista de ate 4 PNGs). `_viab_normalizado` aceita as duas formas. Com `graficos` ->
    2 paginas; sem -> 1 pagina. O dict LEGADO (so os 8 numeros do BLK-RELVIAB-04)
    continua renderizando: os campos novos que faltarem viram "n/d" e as linhas de
    detalhe correspondentes simplesmente somem.
    """
    dados = _viab_normalizado(viabilidade)

    # --- Pagina de NUMEROS (grid 4x2 estilo Big Numbers) ---
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, _VIAB_NUMEROS_TITLE, rgb=primary)

    unidade_be = _viab_unidade_breakeven(dados)
    rotulo_be = f"Break-even ({unidade_be})" if unidade_be else "Alunos break-even"
    otica = str(dados.get("retorno_otica") or "").strip()
    # VOCABULARIO (4a rodada): "do negocio" no lugar de "desalavancado" — o rotulo
    # tem de dizer O QUE mede (o ativo), nao o jargao de estrutura de capital.
    rotulo_retorno = (
        "Retorno anual do negocio" if otica.startswith("desalav") else "ROIC anual"
    )
    retorno_valor = (
        dados.get("retorno_anual")
        if _viab_tem(dados.get("retorno_anual"))
        else dados.get("roic_anual")
    )

    cards = [
        (rotulo_be, _viab_breakeven(dados.get("alunos_breakeven"))),
        ("Aluguel-teto (mês)", _viab_brl(dados.get("aluguel_teto"))),
        ("Margem EBITDA", _viab_pct(dados.get("margem_ebitda_pct"))),
        ("Payback", _viab_payback(dados.get("payback_meses"))),
        (rotulo_retorno, _viab_pct(retorno_valor)),
        ("Faturamento/mês", _viab_brl(dados.get("faturamento_mensal"))),
        ("EBITDA/mês", _viab_brl(dados.get("ebitda_mensal"))),
        (
            "Faixa alunos (p10-p90)",
            _viab_faixa(dados.get("faixa_p10"), dados.get("faixa_p90")),
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

    envelope = "fora do envelope" if dados.get("flag_fora_envelope") else "dentro do envelope"
    rodape = f"Metragem {envelope}."
    if "flag_viavel" in dados:
        viavel = "Sim" if dados.get("flag_viavel") else "Não"
        rodape = f"Viável? {viavel}   |   " + rodape
    if dados.get("flag_zona_morta"):
        motivo = str(dados.get("motivo_zona_morta") or "").strip()
        rodape += f" Zona morta: {motivo}." if motivo else " Cenário em zona morta."
    rodape += (
        " A demanda é uma PREMISSA do operador (não prevista pela geografia). "
        "READ-ONLY sobre o M1."
    )

    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_font("Helvetica", "", 9)
    y_texto = top + 2 * (card_h + gap) + 6
    for linha in _viab_linhas_detalhe(dados):
        pdf.set_xy(margin_x, y_texto)
        pdf.multi_cell(_PAGE_W - 2 * margin_x, 12, _ascii(linha))
        # Avanca pela altura REAL consumida. Com o passo fixo de 15 pt que havia aqui,
        # uma linha que quebrasse em duas ocupava 24 pt e a linha SEGUINTE era desenhada
        # 3 pt acima do fim dela -> textos sobrepostos e ilegiveis (reportado por Felipe
        # 2026-07-24, depois que a explicacao da anuidade alongou a primeira linha).
        y_texto = pdf.get_y() + 3.0
    pdf.set_xy(margin_x, y_texto + 3.0)
    pdf.multi_cell(_PAGE_W - 2 * margin_x, 12, _ascii(rodape))
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
            f"{_RAIO_LABEL}, método {metodo}); SAM Fitness, Residual Fitness (em alunos) e consumo = lookup "
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


def _redes_no_raio(result: dict[str, Any], *, max_nomes: int = 12) -> tuple[str, str]:
    """(header, texto) compactos das redes no raio p/ a faixa inferior do slide Concorrentes.

    So NOMES de rede (deduplicados), sem PII de pessoas nem enderecos. Ultra entra como
    contagem de unidades (o parquet de Ultra nao traz nome de unidade). Trunca com "(+N)".
    """
    conc = result.get("concorrentes_raio", pd.DataFrame())
    ultra = result.get("ultra_raio", pd.DataFrame())
    total = _safe_len(conc) + _safe_len(ultra)
    header = f"Redes no raio de {_RAIO_LABEL}"
    if total > 10:
        header = f"{header} ({total} no total)"

    def _nomes(df: pd.DataFrame | None) -> list[str]:
        if df is None or df.empty:
            return []
        col = next(
            (c for c in ("rede", "nome_unidade", "nome", "brand") if c in df.columns), None
        )
        if col is None:
            return []
        vistos: set[str] = set()
        out: list[str] = []
        for valor in df[col].astype(str):
            nome = valor.strip()
            if nome and nome.lower() not in vistos:
                vistos.add(nome.lower())
                out.append(nome)
        return out

    nomes = _nomes(conc)
    n_ultra = _safe_len(ultra)
    if not nomes and not n_ultra:
        return header, f"Nenhuma rede mapeada no raio de {_RAIO_LABEL}."
    prefixo = f"Ultra: {n_ultra} unidade(s) no raio.  " if n_ultra else ""
    if not nomes:
        return header, prefixo.strip()
    mostrados = nomes[:max_nomes]
    texto = prefixo + "Concorrentes: " + ", ".join(mostrados)
    if len(nomes) > max_nomes:
        texto += f"  (+{len(nomes) - max_nomes})"
    return header, texto


def _competitors_page(
    pdf: _UltraPDF,
    result: dict[str, Any],
    png_bytes: bytes | None,
    assets: dict[str, bytes | None],
    *,
    primary: tuple[int, int, int] = ULTRA_TURQUESA,
    secondary: tuple[int, int, int] = ULTRA_MAGENTA,
) -> None:
    """(f) Concorrentes — mapa CENTRALIZADO (so-pins, sem titulo/legenda internos) + faixa
    inferior com as redes no raio (sem PII). Pedido de Felipe 2026-07-23: centralizar o mapa,
    remover o titulo interno "Concorrentes e Ultra" (redundante com a barra) e a legenda."""
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, "Concorrentes", rgb=primary)

    # Mapa CENTRALIZADO como elemento principal do slide (o PNG ja vem sem titulo/legenda).
    map_top, map_bottom = 58.0, _PAGE_H - 70.0
    if png_bytes:
        dims = _png_dimensions(png_bytes)
        if dims is not None:
            img_w, img_h = dims
            max_w, max_h = _PAGE_W - 96.0, map_bottom - map_top
            scale = min(max_w / img_w, max_h / img_h)
            draw_w = img_w * scale
            draw_h = img_h * scale
            x = (_PAGE_W - draw_w) / 2.0
            y = map_top + (max_h - draw_h) / 2.0
            try:
                pdf.image(BytesIO(png_bytes), x=x, y=y, w=draw_w, h=draw_h)
            except Exception:
                pass

    # Faixa inferior: redes no raio (compacta, sem PII).
    header, texto = _redes_no_raio(result)
    pdf.set_text_color(*secondary)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(40.0, map_bottom + 2.0)
    pdf.cell(_PAGE_W - 80.0, 15, _ascii(header))
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(40.0, map_bottom + 20.0)
    pdf.multi_cell(_PAGE_W - 80.0, 13, _ascii(texto))

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
            f"Agregado sobre todos os setores do bairro/distrito (não o raio de {_RAIO_LABEL}). "
            "Fonte: Censo IBGE 2022; renda média ponderada por domicílios."
        ),
    )


# ---------------------------------------------------------------------------
# Variante "Apresentacao Classica Ultra" (BLK-EST-05) — helpers e gerador.
# BLK-RELPON-14: apos a UNIFICACAO do gerador, esta e' a UNICA estetica do
# relatorio pontual (ja era o default de producao no dashboard, API e bot); as
# paginas gemeas do template "recente" foram deletadas. READ-ONLY sobre o M1.
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
    subtitulo = f"Relatório Pontual Censitário - Raio {_RAIO_LABEL} | {_classico_mes_ano(now)}"

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
    *,
    cols: int = _MAP_GRID_COLS,
    rows: int = _MAP_GRID_ROWS,
    packed_scale: float = 1.0,
) -> list[tuple[float, float, float, float]]:
    """Grid 2x2 dos 4 choropleths na geometria do template CLASSICO (BLK-RELPON-01).

    Mesma logica de `_draw_maps_grid`, mas com o topo respeitando a banda classica + titulo
    de secao (`_CLASSICO_MAPS_TOP` ~122) e a margem lateral classica (20). O header fixo deixa a
    celula 2x2 mais baixa que na variante recente -> a legenda embutida cai para ~8pt (piso legivel
    aceito para caber os 4 mapas; ver test_legenda_corpo_atinge_o_alvo_de_legibilidade_no_pdf).

    BLK-RELPON-10: `cols`/`rows` keyword-only com default 2x2 (caminho existente inalterado);
    o slide-hero classico passa 2x1.
    BLK-RELPON-13: `packed_scale` (default 1.0 = geometria IDENTICA) repassado ao `_draw_maps_grid`;
    so o slide-hero classico passa `_HERO_MAP_SCALE`.
    """
    return _draw_maps_grid(
        pdf,
        pngs,
        top=_CLASSICO_MAPS_TOP,
        bottom=_PAGE_H - 22.0,
        margin_x=_CLASSICO_MARGIN,
        gap=10.0,
        pack=True,
        cols=cols,
        rows=rows,
        packed_scale=packed_scale,
    )


def _classico_socioeconomia_residual_page(
    pdf: _UltraPDF,
    layers: dict[str, bytes],
    assets: dict[str, bytes | None],
    *,
    banda_texto: str,
    primary: tuple[int, int, int] = ULTRA_MAGENTA,
) -> list[tuple[float, float, float, float]]:
    """(BLK-RELPON-10) Slide-hero "Socioeconomia e Residual Fitness".

    Dois mapas LADO A LADO (grid 2x1) na geometria do template classico (banda com margem +
    titulo de secao), com ESCALAS rotuladas dentro do proprio PNG (produzidos em `censo_map`).
    BLK-RELPON-13: Socioeconomia = `score_setor_2022_calibrado` por hexagono H3 res-7 a 5 km (era
    setor no raio do relatorio); Residual Fitness = `oferta_efetiva_disponivel` (alunos) no mesmo hex/raio;
    as 2 imagens reduzidas por `_HERO_MAP_SCALE` (gate visual). Camada ausente -> fallback
    textual da propria `_draw_maps_grid` (offline-safe). READ-ONLY sobre o M1.
    """
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _classico_title_band(pdf, banda_texto, _SOCIOECONOMIA_RESIDUAL_TITULO, assets, rgb=primary)
    boxes = _classico_draw_maps_grid(
        pdf,
        [layers.get("socioeconomia"), layers.get("residual")],
        cols=2,
        rows=1,
        packed_scale=_HERO_MAP_SCALE,
    )
    _draw_footer(pdf, with_attribution=True)
    return boxes


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
    """Concorrentes classica: banda classica + mapa CENTRALIZADO (so-pins) + faixa inferior
    com as redes no raio. Mesmo pedido de Felipe 2026-07-23 aplicado a variante classica."""
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _classico_title_band(pdf, banda_texto, "Concorrentes", assets, rgb=primary)

    # Mapa CENTRALIZADO (sem titulo/legenda internos), abaixo da banda classica.
    map_top, map_bottom = 128.0, _PAGE_H - 66.0
    if png_bytes:
        dims = _png_dimensions(png_bytes)
        if dims is not None:
            img_w, img_h = dims
            max_w, max_h = _PAGE_W - 2.0 * _CLASSICO_MARGIN, map_bottom - map_top
            scale = min(max_w / img_w, max_h / img_h)
            draw_w = img_w * scale
            draw_h = img_h * scale
            x = (_PAGE_W - draw_w) / 2.0
            y = map_top + (max_h - draw_h) / 2.0
            try:
                pdf.image(BytesIO(png_bytes), x=x, y=y, w=draw_w, h=draw_h)
            except Exception:
                pass

    # Faixa inferior: redes no raio (compacta, sem PII).
    header, texto = _redes_no_raio(result)
    pdf.set_text_color(*secondary)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(_CLASSICO_MARGIN, map_bottom + 2.0)
    pdf.cell(_PAGE_W - 2.0 * _CLASSICO_MARGIN, 15, _ascii(header))
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(_CLASSICO_MARGIN, map_bottom + 20.0)
    pdf.multi_cell(_PAGE_W - 2.0 * _CLASSICO_MARGIN, 13, _ascii(texto))

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
    """(BLK-RELPON-07) Perfil do Bairro/Distrito: banda classica + painel "Microarea".

    As 4 metricas sao agregadas sobre a unidade INTEIRA (nao o raio do relatorio), com a
    geometria deslocada para abrir espaco a banda classica (que ocupa ate ~y=122). SEM mapa;
    "n/d" gracioso quando o perfil nao esta disponivel (ponto fora da malha de setores ou
    unidade sem dado suficiente).
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
    """Realizacao/Credito: fundo turquesa solido + credito/metodo/READ-ONLY + link clicavel
    do ponto + data por extenso.

    SEM logo, SEM cartao de contato (anti-PII). Usa turquesa solido (nao a foto da capa) para
    o texto ficar legivel no formato 16:9; a faixa de marca da capa ja cumpre o branding.
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
            f"Interseção de setores censitários IBGE 2022 com círculo de {_RAIO_LABEL}; "
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

    BLK-RELPON-14: e' a IMPLEMENTACAO UNICA do relatorio pontual — o template "recente" foi
    descontinuado e `gerar_pdf_relatorio_pontual_censitario` virou um wrapper fino sobre esta
    funcao. Estetica classica: banda turquesa com margem/cantos arredondados e icone Ultra,
    capa com endereco acima do subtitulo, banda magenta de rodape e Realizacao com link
    clicavel + data por extenso. READ-ONLY sobre o M1.

    7 paginas na ordem canonica (Capa -> Socioeconomia e Residual Fitness -> Mapas de calor ->
    Concorrentes -> Perfil do Bairro/Distrito -> Big Numbers -> Realizacao). Historico: o
    BLK-RELPON-01 consolidou os choropleths em um unico slide "Mapas de calor"; o BLK-RELPON-07
    inseriu "Perfil do Bairro/Distrito" (5->6 paginas) e o slide de mapas passou a GRID 2x2 com
    4 camadas; o BLK-RELPON-10 inseriu o slide-hero "Socioeconomia e Residual Fitness" ANTES dos
    mapas de calor (6->7 paginas); o BLK-RELPON-11 inseriu "Imagem do Entorno" (7->8 paginas) e o
    BLK-RELPON-14 REMOVEU essa pagina por completo (8->7 paginas).
    As paginas OPCIONAIS `fotos`, `info_imovel` e `viabilidade` (numeros + graficos) somam no
    maximo mais 4 -> teto de 11 paginas (era 12 com o entorno); `foto_satelite` (BLK-SAT, so no
    caminho API/bot) soma mais uma quando presente.

    `rotulo` e o nome/endereco do ponto (capa + banda + texto do link). `perfil_bairro`
    (BLK-RELPON-07) e o dict de `agregar_perfil_bairro_distrito`; `None` (default) produz a
    pagina com "n/d" gracioso. `now` e injetavel para data determinista em teste. `solicitante`
    (BLK-EST-01) carimba a marca d'agua de rastreabilidade em TODAS as paginas: None -> so
    "Ultra Academia"; preenchido -> "Ultra Academia | {solicitante}". Geracao 100% offline, sem PII.
    """
    assets = _load_branding_assets(ultra_dir)
    layers = dict(_normalize_mapas_by_key(mapas))
    banda_texto = _classico_banda_texto(result, rotulo)

    # Tom principal alterna por pagina de conteudo (turquesa <-> magenta). BLK-RELPON-01 +
    # BLK-RELPON-07: 4 paginas de conteudo (Mapas de calor=1, Concorrentes=2, Perfil do
    # Bairro/Distrito=3, Big Numbers=4). BLK-RELPON-10: o slide-hero inserido ANTES delas toma o
    # ordinal 0 (magenta) -> p1..p4 INALTERADOS, sem inversao de cor em cascata.
    # BLK-RELPON-14: a pagina "Imagem do Entorno" saiu e com ela o ordinal -1 (`p_entorno`), que
    # existia SO para ela. Como os ordinais sao ABSOLUTOS (nao um contador incremental de
    # paginas), remover -1 NAO desloca nada: p0..p4 continuam ligados as mesmas paginas e
    # produzem EXATAMENTE as mesmas cores de antes (hero=magenta, mapas=turquesa,
    # concorrentes=magenta, perfil=turquesa, big numbers=magenta). Nenhum ordinal foi ajustado.
    p0, _s0 = _tema_bicolor(0)
    p1, _ = _tema_bicolor(1)
    p2, s2 = _tema_bicolor(2)
    p3, s3 = _tema_bicolor(3)
    p4, s4 = _tema_bicolor(4)

    pdf = _UltraPDF()
    _classico_cover_page(pdf, result, assets, rotulo=rotulo, now=now)
    # Imovel: FOTOS primeiro, DEPOIS a vista aerea (item Felipe 2026-07-23) — cada uma em
    # pagina propria; nao disputam vagas entre si. A intencao do BLK-SAT-01 fica preservada:
    # a vista aerea NAO ocupa nenhuma das 2 vagas de `fotos`, tem pagina propria e continua
    # antes de qualquer numero (Entorno/Socioeconomia/Big Numbers vem todos depois).
    # RECONCILIACAO: ficou de fora a POSICAO da main (vista aerea ANTES de `fotos`, comentada
    # como "BLK-SAT (TESTE)", commit 2af2225 de 2026-07-21). O piloto portou esse mesmo bloco
    # em 3fd1fd5 (2026-07-23) ja com a inversao pedida por Felipe, e e' a decisao mais recente
    # sobre a MESMA pagina; manter as duas posicoes emitiria a vista aerea DUAS vezes, e manter
    # so a da main deixaria o classico divergindo do `gerar_pdf_relatorio_pontual_censitario`
    # (onde a main nao tem satelite nenhum e a ordem do piloto e' a unica existente).
    if fotos:
        _fotos_imovel_page(pdf, fotos, assets, primary=p1)
    if foto_satelite:
        _foto_satelite_page(pdf, foto_satelite, assets, primary=p1, grande=foto_satelite_grande)
    if info_imovel:
        _info_imovel_page(pdf, info_imovel, assets, primary=p2, secondary=s2)
    _classico_socioeconomia_residual_page(
        pdf, layers, assets, banda_texto=banda_texto, primary=p0
    )
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

    # Marca d'agua POR CIMA do conteudo de cada pagina (BLK-EST-01, D2=todas as paginas).
    # Escrever na pagina `n` via `pdf.page = n` ANEXA ao stream dessa pagina -> sobreposicao.
    # Capa em branco (fundo turquesa), demais em cinza.
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
    now: datetime | None = None,
    fotos: list[bytes] | None = None,
    info_imovel: dict[str, Any] | None = None,
    viabilidade: dict[str, Any] | None = None,
    foto_satelite: bytes | None = None,
    foto_satelite_grande: bool = False,
) -> bytes:
    """DEPRECIADA (BLK-RELPON-14): wrapper fino de `gerar_pdf_relatorio_pontual_classico`.

    O template "recente" foi DESCONTINUADO: a estetica CLASSICA venceu a unificacao (ja era o
    default de producao no dashboard, na API e no bot) e passou a ser a implementacao unica.
    Esta funcao existe SO para retrocompatibilidade dos chamadores que ainda a importam pelo
    nome — ela repassa TODOS os kwargs e devolve o PDF classico, emitindo `DeprecationWarning`.
    Prefira chamar `gerar_pdf_relatorio_pontual_classico` diretamente.

    A assinatura e' um SUPERSET da anterior: alem dos kwargs historicos, aceita `now`,
    `foto_satelite` e `foto_satelite_grande`, que so a classica aceitava. Qualquer chamada que
    funcionava antes continua funcionando (os novos parametros tem default inerte).
    """
    warnings.warn(
        "gerar_pdf_relatorio_pontual_censitario esta depreciada (BLK-RELPON-14): o template "
        "recente foi unificado no classico. Use gerar_pdf_relatorio_pontual_classico.",
        DeprecationWarning,
        stacklevel=2,
    )
    return gerar_pdf_relatorio_pontual_classico(
        result,
        mapas,
        residual=residual,
        perfil_bairro=perfil_bairro,
        ultra_dir=ultra_dir,
        solicitante=solicitante,
        rotulo=rotulo,
        now=now,
        fotos=fotos,
        info_imovel=info_imovel,
        viabilidade=viabilidade,
        foto_satelite=foto_satelite,
        foto_satelite_grande=foto_satelite_grande,
    )


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
    foto_satelite: bytes | None = None,
    foto_satelite_grande: bool = False,
) -> RelatorioCensitarioDownloadPayloads:
    """CSV dos setores + PDF do relatorio pontual, prontos para download.

    BLK-RELPON-14: com a unificacao do gerador os DOIS ramos de `template` produzem o MESMO
    PDF (estetica classica). O ramo `else` continua passando pelo simbolo legado
    `gerar_pdf_relatorio_pontual_censitario` (hoje wrapper depreciado) para nao quebrar quem
    faz spy/patch nesse nome; producao ja chama sempre com `template="classico"`.
    """
    prefix = filename_prefix or f"relatorio_pontual_censitario_{_point_name(result)}"
    if template == "classico":
        pdf_bytes = gerar_pdf_relatorio_pontual_classico(
            result, mapas, residual=residual, perfil_bairro=perfil_bairro, ultra_dir=ultra_dir,
            solicitante=solicitante, rotulo=rotulo,
            fotos=fotos, info_imovel=info_imovel, viabilidade=viabilidade,
            foto_satelite=foto_satelite, foto_satelite_grande=foto_satelite_grande,
        )
    else:
        pdf_bytes = gerar_pdf_relatorio_pontual_censitario(
            result, mapas, residual=residual, perfil_bairro=perfil_bairro, ultra_dir=ultra_dir,
            solicitante=solicitante, rotulo=rotulo,
            fotos=fotos, info_imovel=info_imovel, viabilidade=viabilidade,
            foto_satelite=foto_satelite, foto_satelite_grande=foto_satelite_grande,
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
    foto_satelite: bytes | None = None,
    foto_satelite_grande: bool = False,
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
        foto_satelite=foto_satelite,
        foto_satelite_grande=foto_satelite_grande,
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
