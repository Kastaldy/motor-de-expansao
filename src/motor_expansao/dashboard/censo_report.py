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
from motor_expansao.core.constants import (
    AREA_IDEAL_MAX_M2,
    AREA_IDEAL_MIN_M2,
    AREA_MIN_M2,
)
from motor_expansao.dashboard.censo_point import (
    METODO_RELATORIO_PONTUAL_CENSITARIO,
    RAIO_CENSITARIO_DEFAULT_KM,
)
from motor_expansao.dashboard.constants import TEXTO_SEM_DADO

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
# "Conclusão" tambem NAO entra: ela e' condicional (`viabilidade` ou `conclusao_so_estudo`),
# e po-la aqui faria esta tupla prometer um header que a maioria dos PDFs nao tem.
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
    # Escala FINAL exibida (V06004 x uplift setorial x fator temporal / moradores) — a mesma
    # do PDF e do payload. Sem ela o CSV so trazia a CALIBRADA (~35-40% abaixo da distribuicao
    # que o PDF do MESMO relatorio mostra), sem nenhuma coluna para reconciliar. A calibrada
    # continua no CSV: e' o insumo do score, nao a renda de leitura.
    "renda_per_capita_domiciliar_setor",
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
# valor bate a meta; vermelho quando nao bate; neutro quando sem dado (Q2, indecidivel). Constantes
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
# Ambar do estado INTERMEDIARIO ("Aprovado com ressalvas") da pagina de Conclusao. Os 8 cards
# do Big Numbers nao usam esta cor -- o semaforo de la e binario (bate/nao bate a meta) mais o
# neutro do indecidivel. Mesma familia pastel das 3 acima: fundo claro o bastante para o rotulo
# em (45,45,45) e o valor em (40,40,40) manterem contraste, e distinguivel do verde e do
# vermelho tambem em impressao P&B (luminancia intermediaria).
_CARD_AMBAR_RGB = (250, 233, 195)

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

# Aviso da pagina de Realizacao (pedido do Felipe, 2026-08-19). Substitui a fala tecnica de
# READ-ONLY/score/plano — jargao interno que nao dizia nada a quem RECEBE o estudo. O que o
# leitor precisa saber e' que o retrato tem data: as bases mudam com o tempo.
_AVISO_DADOS_DINAMICOS = (
    "Este estudo retrata as bases de dados disponíveis na data de geração. Os dados são "
    "dinâmicos e podem ser alterados com o tempo; para decisão, utilize sempre a versão "
    "mais recente do relatório."
)

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

# Marca d'agua de CONFIDENCIALIDADE (pedido do Felipe, 2026-08-19): "ARQUIVO CONFIDENCIAL"
# diagonal, grande e translucida em TODAS as paginas — quem recebe o estudo entende a
# seriedade do arquivo sem perder a leitura (alpha baixo de proposito). Mesmo racional da
# marca de rastreabilidade acima: embutida em claro no content stream, por cima do conteudo.
_CONFIDENCIAL_TEXT = "ARQUIVO CONFIDENCIAL"
_CONFIDENCIAL_FONT_PT = 52
_CONFIDENCIAL_ALPHA = 0.10
# Na capa o fundo e' turquesa/foto (mais escuro que as paginas de conteudo): o branco a 0,10
# sumiria — sobe um degrau, ainda discreto.
_CONFIDENCIAL_ALPHA_CAPA = 0.16
# Diagonal do slide 16:9: atan(540/960) = 29,36 graus (anti-horario, convencao do fpdf2).
_CONFIDENCIAL_ANGLE = 29.36

# ---------------------------------------------------------------------------
# Variante "Apresentacao Classica Ultra" (BLK-EST-05): estetica GeoFusion antiga
# sobre o motor censitario novo. Funcao publica DEDICADA
# (`gerar_pdf_relatorio_pontual_classico`) — NAO ramifica o gerador recente.
# Cores: REUSAR ULTRA_TURQUESA/ULTRA_MAGENTA (decisao do gate humano Q1).
# ---------------------------------------------------------------------------
_CLASSICO_MARGIN = 20.0
_CLASSICO_CORNER_RADIUS = 16.0
_CLASSICO_BAND_H = 58.0
# --- Geometria da CAPA classica (pagina 960x540 pt) --------------------------------------
# A arte `relatorio_capa_bg.png` (1360x763 px) NAO e' um fundo chapado: ela tem uma FAIXA DE
# RODAPE com os logos das marcas (Ultra, Spider Kick, The Flame) desenhados em BRANCO. Texto
# branco dali para baixo fica ilegivel E risca o logo — na pagina 1 de um PDF que vai para
# terceiros. Numeros abaixo MEDIDOS por varredura de pixel do proprio asset (2026-08-03):
#   * linha divisoria branca do rodape: px y=652 de 763 -> pt y=461,4 (99% de pixel branco);
#   * logos do rodape ocupam pt x~140-270 (Ultra), ~400-560 (Spider Kick), ~700-810 (Flame);
#   * a coluna x>=460 pt entre y=300 e y=450 pt e' turquesa CHAPADO: 0,000 de pixel
#     nao-turquesa. E' a unica area limpa larga da capa (o resto e' foto, logo ou rodape).
# Todo texto da capa mora nessa coluna e ACIMA de `_CAPA_RODAPE_LOGOS_TOP`.
_CAPA_RODAPE_LOGOS_TOP = 461.4
_CAPA_BASE_X_COM_ARTE = 478.0
_CAPA_BASE_X_SEM_ARTE = 80.0
_CAPA_AVISO_Y = 402.0
_CAPA_ENDERECO_Y = 430.0
_CAPA_SUBTITULO_Y = 455.0
_CAPA_AVISO_FONT_PT = 10.0
_CAPA_ENDERECO_FONT_PT = 26.0
# Piso de encolhimento do endereco: abaixo disso ele briga com o subtitulo (13 pt) e o corte
# por largura passa a ser preferivel a uma linha minuscula.
_CAPA_ENDERECO_FONT_MIN_PT = 15.0
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
        return TEXTO_SEM_DADO
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


def _ajustar_fonte_para_largura(
    pdf: FPDF,
    texto: str,
    largura: float,
    *,
    familia: str = "Helvetica",
    estilo: str = "B",
    tamanho: float = 26.0,
    minimo: float = 11.0,
) -> float:
    """Fixa a maior fonte <= `tamanho` em que `texto` cabe em UMA linha de `largura` pt.

    Necessario desde que "n/d" virou `TEXTO_SEM_DADO` (2026-07-31): a string por extenso nao
    cabe nos 185 pt uteis do card de Big Numbers a 26 pt, e o `multi_cell` a quebraria em duas
    linhas que vazariam a base do card de 132 pt. Encolher em passos de 1 pt e' preferivel a
    quebrar -- o card continua com uma linha so, alinhada com os vizinhos. Tambem protege
    valores numericos longos (ex.: renda com centavos em municipio grande), que ate aqui
    dependiam de caber por sorte. Devolve o corpo aplicado (a fonte fica ATIVA no `pdf`).
    """
    corpo = float(tamanho)
    pdf.set_font(familia, estilo, corpo)
    while corpo > minimo and pdf.get_string_width(texto) > largura:
        corpo -= 1.0
        pdf.set_font(familia, estilo, corpo)
    return corpo


def _truncar_por_largura(
    pdf: FPDF, texto: str, largura: float, *, reticencias: str = "..."
) -> str:
    """Corta `texto` pela largura RENDERIZADA na fonte ATIVA do `pdf`, nao por nº de chars.

    Helvetica e' proporcional: 37 caracteres podem medir 480 pt ("Galpao Comercial Avenida
    Brasil, 4500" a 26 pt bold) ou 200 pt, conforme as letras. Cortar por CONTAGEM (o que a
    capa fazia: >72 chars -> 69 + "...") nao protege borda nenhuma — o rotulo e' texto livre
    do operador e vazava para fora da pagina muito antes de chegar a 72 caracteres.

    Devolve o texto intacto quando ja cabe (rotulo curto = comportamento historico, sem
    reticencias); senao encurta ate que `texto + reticencias` caiba em `largura`.
    """
    if pdf.get_string_width(texto) <= largura:
        return texto
    corte = texto.rstrip()
    while corte and pdf.get_string_width(corte + reticencias) > largura:
        corte = corte[:-1].rstrip()
    return corte + reticencias


def _nome_exibicao(usuario: str) -> str:
    """Nome de EXIBICAO do usuario: "felipe_castaldi" -> "Felipe Castaldi".

    Camada de exibicao apenas (regra de identificadores, CLAUDE.md §2): o valor bruto do
    usuario segue intacto em trilha/log/payload — aqui muda so' como ele aparece no PDF,
    para o nome sair consistente em qualquer pagina que o exiba.
    """
    partes = [p for p in str(usuario).replace("_", " ").split() if p]
    if not partes:
        return str(usuario).strip()
    return " ".join(p[:1].upper() + p[1:] for p in partes)


def _watermark_text(solicitante: str | None) -> str:
    """Texto da marca d'agua: "Ultra Academia" ou "Ultra Academia | {solicitante}".

    `solicitante` None/vazio -> so a base (default seguro, sem PII). ASCII-safe.
    """
    if solicitante is None or not solicitante.strip():
        return _ascii(_WATERMARK_BASE)
    return _ascii(f"{_WATERMARK_BASE} | {_nome_exibicao(solicitante)}")


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
# ausentes -> `TEXTO_SEM_DADO` gracioso. READ-ONLY sobre o M1; anti-PII (nada persistido).
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
        return TEXTO_SEM_DADO
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
_VIAB_NUMEROS_TITLE = "Projeção de Viabilidade - Números"
_VIAB_GRAFICOS_TITLE = "Viabilidade - Projeção financeira"


def _viab_brl(value: Any) -> str:
    if value is None or pd.isna(value):
        return TEXTO_SEM_DADO
    return "R$ " + _format_number(value, 2)


def _viab_pct(frac: Any) -> str:
    if frac is None or pd.isna(frac):
        return TEXTO_SEM_DADO
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
        return TEXTO_SEM_DADO
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
        # Reguas do veredito, servidas pelo proprio payload (`premissas.*`). A pagina de
        # Conclusao precisa saber se `flag_viavel=False` falhou em UM criterio ou nos DOIS,
        # e le os limites daqui em vez de importar `dimensionamento.config` -- e' a mesma
        # fronteira de RENDER PURO do FIN-VIAB-01 (o slide LE o payload, nao recalcula nem
        # crava constante propria que sairia de sincronia com a fonte unica).
        "margem_viavel_min": _viab_campo(
            viabilidade, "margem_viavel_min", "premissas", "margem_viavel_min"
        ),
        "payback_viavel_max": _viab_campo(
            viabilidade, "payback_viavel_max", "premissas", "payback_viavel_max"
        ),
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
        # Mesmo encolhimento do grid de Big Numbers: aqui tambem cai `TEXTO_SEM_DADO`
        # (via _viab_brl/_viab_pct/_viab_faixa) num card de largura fixa.
        valor_txt = _ascii(value)
        _ajustar_fonte_para_largura(pdf, valor_txt, card_w - 28, tamanho=22.0)
        pdf.set_xy(x + 14, y + 74)
        pdf.multi_cell(card_w - 28, 24, valor_txt)

    envelope = "fora do envelope" if dados.get("flag_fora_envelope") else "dentro do envelope"
    rodape = f"Metragem {envelope}."
    if "flag_viavel" in dados:
        viavel = "Sim" if dados.get("flag_viavel") else "Não"
        rodape = f"Viável? {viavel}   |   " + rodape
    if dados.get("flag_zona_morta"):
        motivo = str(dados.get("motivo_zona_morta") or "").strip()
        rodape += f" Zona morta: {motivo}." if motivo else " Cenário em zona morta."
    # Sem o "READ-ONLY sobre o M1" que fechava esta frase: jargao interno de governanca,
    # que nao diz nada a quem RECEBE o estudo (limpeza de 2026-08-19; o guardrail em si
    # continua valendo — e' regra de codigo, nao de rodape).
    rodape += " A demanda é uma PREMISSA do operador (não prevista pela geografia)."

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


# ---------------------------------------------------------------------------
# Pagina de CONCLUSAO: DOIS pareceres tri-estado do ponto + observacoes.
#
# Ate aqui o relatorio nao tinha veredito por ponto. O que existia era:
#   * o semaforo por METRICA dos 8 Big Numbers (`_cor_por_meta`, BLK-RELPON-08);
#   * o veredito BINARIO de viabilidade financeira (`dre.flag_viavel`);
#   * o parecer tri-estado de `rede_diagnostico`, mas apontado para unidade MADURA.
# A pagina nasceu (2026-08-06) compondo os tres num status UNICO por ponto candidato.
# Desde a DEC-030 (pedido de Vinicius, 2026-08-14) esse status unico NAO existe mais:
# a pagina carimba DOIS selos independentes, um por EIXO, e nada os agrega.
#
# Por que separar: os dois eixos respondem perguntas diferentes e falham por motivos
# que nao se compensam. Uma praca que nao sustenta a operacao nao vira aceitavel
# porque o imovel e' barato, e um imovel fora do envelope nao vira aceitavel porque a
# praca e' boa. O status unico ESCONDIA esse conflito: colapsava os dois no pior dos
# lados e o leitor tinha de reconstruir, pela lista de observacoes, de onde veio a
# reprovacao. Com dois selos o conflito fica VISIVEL -- verde de um lado, vermelho do
# outro, na mesma pagina -- e a decisao de o que fazer com ele volta para quem le.
#
# A gramatica de cada eixo continua sendo a de `rede_diagnostico` ("1 grave OU N
# medios"): um gate ELIMINATORIO reprova o EIXO sozinho; os demais apontamentos apenas
# rebaixam aquele eixo para "Aprovado com ressalvas".
#
# REGUA (cortes aprovados por Vinicius em 2026-08-06; particao em eixos na DEC-030):
#   EIXO DEMOGRAFICO -- a praca (o que os Big Numbers medem). Sempre avaliado.
#     E4  cenario em zona morta (`flag_zona_morta`)                    -> Reprovado
#     E5  N metas censitarias vermelhas ao mesmo tempo (so-estudo)     -> Reprovado
#     R4  meta de Big Number nao atingida                              -> Ressalvas
#     R7  mercado ja consumido pela oferta instalada                   -> Ressalvas
#     --  nenhum setor censitario no raio (censo indisponivel)         -> Ressalvas
#   EIXO FINANCEIRO -- o imovel e o retorno (Informacoes do Imovel + Viabilidade).
#     E1  margem abaixo da regua E payback acima da regua (os DOIS)    -> Reprovado
#     E2  aluguel pedido acima da 3a faixa de aluguel-teto (excecao)   -> Reprovado
#     E3  metragem < AREA_MIN_M2  (pe-direito SAIU: Vinicius, 2026-08-07)  -> Reprovado
#     R1  falha em UM dos dois criterios de retorno                    -> Ressalvas
#     R2  aluguel acima da 2a faixa (teto) e dentro da excecao         -> Ressalvas
#     R3  metragem fora de AREA_IDEAL_MIN_M2..AREA_IDEAL_MAX_M2        -> Ressalvas
#     R5  metragem fora do envelope da base de calibracao              -> Ressalvas
#     R6  campo essencial do imovel nao informado                      -> Ressalvas
#   Eixo sem nenhum dos dois -> Aprovado.
#
# E4 (zona morta) mora no eixo DEMOGRAFICO embora chegue pelo payload de viabilidade:
# o flag e' levantado por `pop<5000` / `renda<1600` na captacao (ver
# `_CONCLUSAO_MOTIVO_ZONA_MORTA`), que e' juizo sobre a PRACA, nao sobre o imovel nem
# sobre o retorno. Por isso ele sobrevive no modo so-estudo, onde o eixo financeiro
# inteiro nao existe. Consequencia declarada e aceita: o gate le `dados_viab`, entao um
# ponto sem payload de viabilidade nunca dispara E4 -- ausencia de dado, nao aprovacao.
#
# "Mercado consumido" nasceu ELIMINATORIO na proposta e virou RESSALVA por decisao
# de Vinicius (2026-08-06): saturacao e' leitura de disputa, nao sentenca -- um ponto
# com residual curto mas economia sadia continua negociavel.
#
# INDECIDIVEL NUNCA REPROVA. Dado ausente segue a regra ja estabelecida em
# `_cor_por_meta` (BLK-RELPON-08 D3/Q2): condicao indecidivel vira neutra, jamais
# falsa reprovacao. Todo gate eliminatorio so dispara com o dado em maos -- por isso
# as comparacoes sao sempre `valor is not None and ...`, nunca truthiness.
#
# SEM FATURAMENTO, COM ALUGUEL-TETO (pedido de Vinicius, 2026-08-06, ajustado no mesmo
# dia). A pagina NAO imprime faturamento, EBITDA, investimento, VPL nem TIR, e as
# observacoes de retorno seguem QUALITATIVAS -- nem margem nem payback saem em numero.
# O aluguel-teto ESTA impresso, em card proprio, por decisao explicita depois de a
# implicacao ser levantada e aceita: o teto e' 20% do faturamento bruto, entao quem
# conhecer a regra reconstroi o faturamento dividindo por 0,20. O que o card mostra e'
# a faixa `teto` (a 2a, canonica), NUNCA a `excecao` -- esta ultima segue apenas como
# REGUA do eliminatorio E2. Os demais numeros da pagina sao FISICOS (metragem,
# pe-direito), de CUSTO DO IMOVEL (aluguel pedido, informado pelo operador) ou
# CENSITARIOS (populacao, domicilios, renda, SAM/residual em alunos).
#
# READ-ONLY sobre o M1: nao recalcula score, carteira, plano nem artefatos oficiais.
# ---------------------------------------------------------------------------
_CONCLUSAO_PAGE_TITLE = "Conclusão"

# Status BRUTOS: identificadores comparados em codigo/teste -- SEM acento, por regra.
# A acentuacao vive so na camada de LABEL (`_CONCLUSAO_SELO_TEXTOS`, mais abaixo), que e'
# a UNICA forma de exibicao do status desde que o selo substituiu o card de largura total.
CONCLUSAO_APROVADO = "aprovado"
CONCLUSAO_RESSALVAS = "com_ressalvas"
CONCLUSAO_REPROVADO = "reprovado"

# Eixos do parecer (DEC-030). Tambem identificadores BRUTOS, sem acento: sao chave de
# dicionario de texto/cor e comparados em teste. A acentuacao vive em
# `_CONCLUSAO_SELO_LEGENDAS`, camada de exibicao.
CONCLUSAO_EIXO_DEMOGRAFICO = "demografico"
CONCLUSAO_EIXO_FINANCEIRO = "financeiro"

_CONCLUSAO_CORES = {
    CONCLUSAO_APROVADO: _CARD_VERDE_RGB,
    CONCLUSAO_RESSALVAS: _CARD_AMBAR_RGB,
    CONCLUSAO_REPROVADO: _CARD_VERMELHO_RGB,
}

# Campos do imovel que ALIMENTAM gate. `valor_venda`, `vagas` e `tipo_imovel` ficam de
# fora de proposito: nao entram em nenhuma regra, e exigi-los faria todo relatorio sem
# preco de venda (a maioria) nascer "com ressalvas" por um dado que nao muda o parecer.
# `pe_direito_m` saiu daqui junto com o gate (Vinicius, 2026-08-07) -- cobrar um campo
# que nao decide mais nada so geraria ressalva sem consequencia.
_CONCLUSAO_CAMPOS_ESSENCIAIS = (
    ("metragem_m2", "Metragem"),
    ("aluguel_pedido", "Aluguel pedido"),
)

# E5 (BLK-CONC-ESTUDO, corte de Juan em 2026-08-11): N metas censitarias vermelhas AO MESMO
# TEMPO valem um eliminatorio -- a mesma gramatica "1 grave OU N medios" que a pagina ja
# herdou de `rede_diagnostico`. Antes deste bloco NENHUM criterio da praca reprovava, e o
# parecer do caminho API/bot (que nao tem imovel nem financeiro) parava sempre em
# "com ressalvas".
#
# Por que 4 e nao 3: medido em 40 pontos reais de SP sorteados entre hexes povoados, o corte
# 3 reprovaria 65% deles e "Reprovado" viraria a resposta padrao do bot; 4 reprova 60% da
# MESMA amostra, que puxa para cidade pequena (as metas sao ABSOLUTAS e calibradas para o
# raio de 1,0 km urbano). Numeros no gate; mexer aqui pede remedir.
#
# Vale nos DOIS modos desde a emenda da DEC-030 (Vinicius, 2026-08-14). Nasceu preso ao
# so-estudo, e a divergencia declarada entao -- mesmo ponto "Reprovado" no bot e "Aprovado
# com ressalvas" no piloto -- deixou de ser aceitavel quando o selo demografico ganhou vida
# propria: a leitura da PRACA passou a ser um carimbo visivel, e ela nao pode depender de
# por qual porta o relatorio saiu. O corte NAO foi remedido nem alterado; so o escopo mudou.
_CONCLUSAO_METAS_ELIMINATORIO_MIN = 4
# Total avaliado por `_conclusao_metas_vermelhas` (pop, renda pc, domicilios, renda
# domiciliar, SAM, Residual). So compoe o TEXTO ("4 das 6"); travado em teste contra a
# funcao real, para nao virar prosa desatualizada se uma meta entrar ou sair.
_CONCLUSAO_METAS_AVALIADAS = 6

# `motivo_zona_morta` chega como token bruto do motor ("pop<5000"). Traduzir aqui mantem
# o valor cru intacto e ainda assim legivel; token novo cai no fallback e sai como veio.
_CONCLUSAO_MOTIVO_ZONA_MORTA = {
    "pop<5000": "população de captação abaixo de 5.000",
    "renda<1600": "renda per capita de captação abaixo de R$ 1.600",
    "catchment_indisponivel": "captação indisponível",
}

# Texto de confirmacao por EIXO (DEC-030): cada selo tem o seu, porque cada um afirma
# ter avaliado coisas diferentes. O texto unico anterior citava envelope do imovel E metas
# censitarias E criterios de retorno na mesma frase -- sob dois selos ele seria falso nos
# dois lados, afirmando de cada eixo o que so o outro olhou.
_CONCLUSAO_APROVADO_TEXTO_DEMOGRAFICO = (
    "Nenhuma restrição encontrada na praça: o ponto atende às metas censitárias do raio "
    "e à leitura de mercado do hexágono."
)
_CONCLUSAO_APROVADO_TEXTO_FINANCEIRO = (
    "Nenhuma restrição encontrada no imóvel nem no retorno: o ponto atende ao envelope "
    "do imóvel e aos critérios de retorno da Ultra."
)
_CONCLUSAO_NOTA = (
    # "e pé-direito" saiu junto com o gate (Vinicius, 2026-08-07): a nota descreve a
    # REGUA aplicada, e citar um criterio que nao decide mais nada seria mentir sobre ela.
    "Parecer automático das réguas da Ultra, em dois eixos independentes. DEMOGRÁFICO: "
    f"metas censitárias do raio de {_RAIO_LABEL} e leitura de mercado do hexágono, com "
    # O gate E5 passou a valer aqui (emenda da DEC-030): sem esta frase o parecer
    # reprovaria a praca sem que a pagina dissesse por qual regra.
    f"reprovação quando {_CONCLUSAO_METAS_ELIMINATORIO_MIN} das "
    f"{_CONCLUSAO_METAS_AVALIADAS} metas falham ao mesmo tempo. FINANCEIRO: envelope do "
    "imóvel (metragem), aluguel-teto e critérios de retorno do cenário simulado. Cada eixo "
    "tem selo próprio e NÃO há veredito único: um item eliminatório reprova o eixo sozinho; "
    "os demais rebaixam aquele eixo para 'Aprovado com ressalvas'. Dado ausente nunca "
    "reprova, apenas deixa o item sem avaliar."
)
# Variantes do modo SO-ESTUDO (BLK-CONC-ESTUDO). Reusar as strings acima seria AFIRMAR que
# o envelope do imovel e os criterios de retorno foram avaliados -- exatamente os que este
# modo nao avalia. O texto de aprovacao e a nota tem de descrever a regua que rodou.
_CONCLUSAO_APROVADO_TEXTO_ESTUDO = (
    "Nenhuma restrição encontrada na base do estudo: o ponto atende às metas censitárias "
    "do raio e à leitura de mercado do hexágono."
)
_CONCLUSAO_NOTA_ESTUDO = (
    "Parecer automático das réguas do ESTUDO: metas censitárias do raio de "
    f"{_RAIO_LABEL} e leitura de mercado do hexágono. NÃO avalia o imóvel (metragem, "
    # Travessao (U+2014) NAO existe em latin-1 e sairia como "?" silencioso no PDF (fonte
    # core do fpdf2) -- regra de acentuacao do CLAUDE.md, travada pelo teste de regressao.
    "aluguel) nem o retorno do cenário - esses critérios exigem a análise financeira e "
    "ficam fora deste parecer, que por isso traz só o selo demográfico. Reprova quando "
    f"{_CONCLUSAO_METAS_ELIMINATORIO_MIN} das {_CONCLUSAO_METAS_AVALIADAS} metas falham ao "
    "mesmo tempo; as demais observações rebaixam para 'Aprovado com ressalvas'. Dado "
    "ausente nunca reprova, apenas deixa o item sem avaliar."
)
# Piso da area de observacoes: a pagina e FIXA (auto_page_break OFF), entao texto que nao
# cabe NAO vaza para a pagina seguinte -- ele some por baixo do rodape, em silencio.
_CONCLUSAO_OBS_LIMITE_Y = _PAGE_H - 74.0
_CONCLUSAO_NOTA_Y = _PAGE_H - 62.0

# Area de conteudo entre a banda de titulo e a nota metodologica. As duas colunas sao
# centralizadas VERTICALMENTE nela (pedido de Vinicius, 2026-08-07); antes tudo nascia
# colado no topo e sobrava um vazio grande embaixo em quase todo relatorio.
_CONCLUSAO_AREA_TOPO = 66.0
_CONCLUSAO_AREA_BASE = _CONCLUSAO_OBS_LIMITE_Y

# Cada observacao vira um CARD, com o mesmo peso visual dos cards de valor (pedido de
# Vinicius, 2026-08-07: em bullet de texto solto elas ficavam discretas demais e davam a
# impressao de que so o valor tinha decidido o parecer). Barra de acento no topo, como
# nos cards de aluguel, mas aqui a cor e' SEMANTICA -- diz a severidade do apontamento.
_CONCLUSAO_OBS_LINHA_H = 13.0
# Padding e gap ENXUTOS de proposito: com 8/8 a coluna comportava 6 cards, e o parecer de
# um ponto ruim tipico tem 10 apontamentos -- 4 caiam no "(+N nao exibido(s))" justamente
# onde a leitura mais importa. Com 5/6 cabem 8, sem apertar o texto de forma perceptivel.
_CONCLUSAO_OBS_PAD_Y = 5.0
_CONCLUSAO_OBS_PAD_X = 16.0
_CONCLUSAO_OBS_GAP = 6.0
_CONCLUSAO_OBS_ACENTO_H = 4.0
_CONCLUSAO_OBS_TITULO_H = 16.0
_CONCLUSAO_OBS_TITULO_GAP = 8.0
_CONCLUSAO_ALUGUEL_OBS_GAP = 22.0
# Respiro EXTRA antes do titulo do 2o bloco de observacoes (DEC-030). Com so o
# `_CONCLUSAO_OBS_GAP` (6) o titulo do bloco financeiro colava no ultimo card do
# demografico e os dois blocos liam como uma lista so. 14 pt fica entre as duas reguas que
# a pagina ja usa: 6 entre cards irmaos e 22 entre blocos de natureza diferente.
_CONCLUSAO_BLOCO_GAP = 14.0
# Titulo de cada bloco de observacoes. Amarram os cards ao selo que os gerou: sem eles o
# leitor ve dois carimbos e uma lista unica, sem saber qual apontamento pesou em qual.
# Camada de EXIBICAO -- acentuada, como manda a regra; a chave e' o eixo bruto.
_CONCLUSAO_BLOCO_TITULOS = {
    CONCLUSAO_EIXO_DEMOGRAFICO: "Praça (demográfico)",
    CONCLUSAO_EIXO_FINANCEIRO: "Imóvel e retorno (financeiro)",
}
# Altura reservada para a linha "(+N apontamento(s) nao exibido(s))". Sem reservar, o
# loop enchia a coluna ate o limite e o aviso saia POR CIMA do ultimo card.
_CONCLUSAO_OBS_AVISO_H = 16.0

# Severidade da observacao -> (fundo, acento). Identificadores BRUTOS, sem acento.
# Hierarquia deliberada: o que REPROVA leva fundo tingido e salta; a ressalva fica no
# cinza neutro dos demais cards, com a cor so na barra -- com 8+ apontamentos, tingir
# todos deixaria a pagina inteira vermelha e nada saltaria.
_CONCLUSAO_OBS_CORES = {
    "eliminatorio": (_CARD_VERMELHO_RGB, (198, 57, 57)),
    "ressalva": (_CARD_NEUTRO_RGB, (198, 146, 44)),
    "confirmacao": (_CARD_VERDE_RGB, (26, 170, 85)),
}
# Cor SOLIDA do selo por estado (traco e texto). Os `_CARD_*_RGB` sao pasteis de FUNDO e
# nao teriam contraste como linha de 2 pt nem como tipografia; estas sao as mesmas
# familias em versao cheia. Verde e ambar espelham a semantica de `--pos`/`--warn` do
# carimbo da tela; o vermelho e' o terceiro estado, que la nao existe.
_CONCLUSAO_SELO_RGB = {
    "aprovado": (26, 170, 85),
    "com_ressalvas": (198, 146, 44),
    "reprovado": (198, 57, 57),
}
# (rotulo principal, linha de apoio) POR EIXO (DEC-030). O rotulo principal e' o mesmo nos
# dois -- e o status, e status nao muda de nome conforme o eixo. Quem diferencia e' a linha
# de apoio, que diz a CONSEQUENCIA daquele eixo: o financeiro conserva os textos de
# 2026-08-07, que espelham "APROVADO / PARA COMITÊ" da tela (`ViabilityCharts.Veredito`);
# o demografico estreia os seus, que falam da praca e nao prometem rito nenhum.
_CONCLUSAO_SELO_TEXTOS = {
    CONCLUSAO_EIXO_DEMOGRAFICO: {
        "aprovado": ("APROVADO", "PRAÇA SUSTENTA"),
        "com_ressalvas": ("COM RESSALVAS", "PRAÇA COM RISCO"),
        "reprovado": ("REPROVADO", "PRAÇA NÃO SUSTENTA"),
    },
    CONCLUSAO_EIXO_FINANCEIRO: {
        "aprovado": ("APROVADO", "PARA COMITÊ"),
        "com_ressalvas": ("COM RESSALVAS", "REQUER REVISÃO"),
        "reprovado": ("REPROVADO", "FORA DA RÉGUA"),
    },
}
# Legenda no topo do selo: sem ela os dois carimbos sao indistinguiveis. Camada de
# EXIBICAO (acentuada); a chave e' o eixo bruto.
_CONCLUSAO_SELO_LEGENDAS = {
    CONCLUSAO_EIXO_DEMOGRAFICO: "DEMOGRÁFICO",
    CONCLUSAO_EIXO_FINANCEIRO: "FINANCEIRO",
}
# O pedido de Juan (2026-08-12) de esconder "PARA COMITÊ" no modo so-estudo virou
# ESTRUTURAL na DEC-030 e por isso deixou de existir como excecao: o rito de comite
# pertence ao eixo FINANCEIRO, e o so-estudo nao desenha esse selo. O parecer do bot nao
# tem mais como prometer um rito que nao tem base para disparar -- por construcao, nao por
# um `frozenset` de excecao. `test_selo_aprovado_so_estudo_sem_mencao_a_comite` segue
# guardando o invariante.

# Geometria de 2 COLUNAS (reestruturacao pedida por Vinicius, 2026-08-07): cards de
# aluguel + observacoes a ESQUERDA, selos a DIREITA. A largura da coluna esquerda
# sai por subtracao para a soma fechar sempre na pagina, mesmo se a do selo mudar.
_CONCLUSAO_MARGEM_X = 36.0
# 240 -> 210 na DEC-030: o que a coluna direita perde em largura, a esquerda ganha (622 ->
# 652), e ela e' que precisa -- passou a comportar DOIS titulos de bloco alem dos cards.
_CONCLUSAO_COL_DIR_W = 210.0
_CONCLUSAO_COL_GAP = 26.0
_CONCLUSAO_COL_DIR_X = _PAGE_W - _CONCLUSAO_MARGEM_X - _CONCLUSAO_COL_DIR_W
_CONCLUSAO_COL_ESQ_W = _CONCLUSAO_COL_DIR_X - _CONCLUSAO_MARGEM_X - _CONCLUSAO_COL_GAP
# 210 x 176 ~ 1,19:1 -- quase quadrado, como o carimbo da tela (era 240 x 196 ~ 1,22:1 com
# um selo so). Nao e' 1:1 exato porque o rotulo mais longo ("COM RESSALVAS") precisa da
# largura para nao encolher demais.
#
# A altura caiu de 196 para 176 porque agora sao DOIS: a area util da coluna e' de apenas
# `_CONCLUSAO_AREA_BASE - _CONCLUSAO_AREA_TOPO` = 400 pt, e `2 x 196 + gap` estoura isso
# em 8 a 16 pt. Como `auto_page_break` esta OFF, o excedente NAO vazaria para a pagina
# seguinte: sairia por baixo do rodape, em silencio (mesma armadilha que
# `_CONCLUSAO_OBS_LIMITE_Y` documenta para as observacoes). `2 x 176 + 20` = 372 deixa
# 28 pt de folga -- 14 de cada lado, o suficiente para os selos nao encostarem na banda de
# titulo nem na nota metodologica. Travado por `test_os_dois_selos_cabem_na_area_util`.
_CONCLUSAO_SELO_H = 176.0
_CONCLUSAO_SELO_GAP = 20.0
# Cantos arredondados do selo (pedido de Vinicius, 2026-08-07). Fica um pouco menor que
# `_CLASSICO_CORNER_RADIUS` (16) porque a borda aqui tem 2 pt e o mesmo raio da banda
# clássica deixaria o traco visivelmente achatado nas quinas. Os CARDS seguem retos, como
# todos os outros do relatorio -- o arredondamento marca o selo como elemento a parte.
# ABSOLUTO de proposito: raio e borda nao escalam com a altura, senao o selo menor pareceria
# um card arredondado em vez do mesmo carimbo em outro tamanho.
_CONCLUSAO_SELO_RAIO = 13.0
# Geometria INTERNA do selo, em fracao da altura (DEC-030). Antes eram absolutos (48 pt de
# simbolo, celulas de 22/14, corpo 17/9,5), calibrados para a altura unica de 196.
#
# Duas coisas mudaram aqui, e elas sao de naturezas DIFERENTES -- o comentario original
# afirmava que as duas eram inocuas e a revisao adversarial mostrou que so a primeira e':
#
#   (a) TAMANHOS viraram fracao e REPRODUZEM o desenho de 2026-08-07 em `altura = 196`:
#       48/196 = 0,245, 22/196 = 0,112, 14/196 = 0,0714. Isso e' parametrizacao pura --
#       sem ela, o simbolo de 48 pt fixo num selo de 176 fica desproporcional em relacao
#       aos rotulos, que encolheram junto com a altura.
#
#   (b) POSICOES foram REANCORADAS, e isso MUDA o desenho mesmo em 196: o simbolo desce
#       0,30 -> 0,335, o rotulo 0,55 -> 0,60, o apoio 0,74 -> 0,78 (em 196: 6,9 / 9,8 /
#       7,8 pt mais baixos). Nao foi de carona: a LEGENDA e' um elemento novo no topo, que
#       o desenho de 2026-08-07 nao tinha. Com as posicoes antigas em 176, o simbolo comeca
#       em 28,8 pt e a legenda (celula de 12) ocuparia 12,3..24,3 -- 4,5 pt de respiro, ela
#       colada no simbolo. Descendo o conjunto, o respiro vai a 13,1 pt e a area morta no
#       pe cai de 33,2 para 26,2 pt. Ou seja: o reancoramento EQUILIBRA o selo de tres
#       niveis para um de quatro; ele nao pode "reproduzir exatamente" um desenho que tinha
#       um elemento a menos.
#
# (Para o registro, porque a justificativa anterior citava um numero errado: com a
# geometria antiga em 176 o simbolo NAO termina a ~5 pt do rotulo. O gap real seria de
# 18,85 pt no pior caso -- o "!" do estado intermediario, que e' o simbolo que mais desce
# -- e 28,16 pt no check. O problema era a legenda, nunca a colisao simbolo/rotulo.)
#
# As oito fracoes estao travadas em `test_geometria_interna_do_selo` -- as de TAMANHO
# contra os absolutos de 2026-08-07, as de POSICAO contra os valores desta decisao.
_CONCLUSAO_SELO_LEGENDA_Y = 0.070
# A legenda e' a UNICA parte do selo que nao escala: 9 pt ja e' a menor tipografia da
# pagina, e encolhe-la junto com a altura a tornaria ilegivel antes de qualquer outra coisa.
_CONCLUSAO_SELO_LEGENDA_CORPO = 9.0
_CONCLUSAO_SELO_LEGENDA_H = 12.0
_CONCLUSAO_SELO_SIMBOLO_TAM = 0.245
_CONCLUSAO_SELO_SIMBOLO_Y = 0.335
_CONCLUSAO_SELO_PRINCIPAL_Y = 0.60
_CONCLUSAO_SELO_PRINCIPAL_H = 0.112
_CONCLUSAO_SELO_SECUNDARIO_Y = 0.78
_CONCLUSAO_SELO_SECUNDARIO_H = 0.0714
# Corpos de texto na altura de referencia; escalam por `altura / _CONCLUSAO_SELO_H_REF`.
_CONCLUSAO_SELO_H_REF = 196.0
_CONCLUSAO_SELO_PRINCIPAL_CORPO = 17.0
_CONCLUSAO_SELO_SECUNDARIO_CORPO = 9.5
# Os dois cards de aluguel vivem na coluna ESQUERDA, lado a lado, acima das observacoes
# (pedido de Vinicius, 2026-08-07). O gap e' HORIZONTAL desde entao.
_CONCLUSAO_ALUGUEL_H = 72.0
_CONCLUSAO_ALUGUEL_GAP = 12.0


@dataclass(frozen=True)
class _ConclusaoEixo:
    """Parecer de UM eixo: status bruto + observacoes ja redigidas, na ordem de leitura."""

    status: str
    eliminatorios: tuple[str, ...]
    ressalvas: tuple[str, ...]


def _conclusao_eixo(eliminatorios: list[str], ressalvas: list[str]) -> _ConclusaoEixo:
    """Fecha um eixo aplicando a gramatica "1 grave OU N medios" -- so aqui, uma vez."""
    if eliminatorios:
        status = CONCLUSAO_REPROVADO
    elif ressalvas:
        status = CONCLUSAO_RESSALVAS
    else:
        status = CONCLUSAO_APROVADO
    return _ConclusaoEixo(
        status=status, eliminatorios=tuple(eliminatorios), ressalvas=tuple(ressalvas)
    )


@dataclass(frozen=True)
class _ConclusaoPonto:
    """Parecer do ponto: DOIS eixos independentes, sem status agregado (DEC-030).

    Nao existe `status` do ponto de proposito. Um agregado (pior-dos-dois) sobreviveria
    aqui sem nenhum consumidor de render -- a pagina carimba um selo por eixo -- e seria
    lido como "o veredito", que e' exatamente a leitura que a DEC-030 aboliu. Quem precisa
    de um juizo unico tem de dizer, no ponto de uso, qual eixo esta perguntando.

    `financeiro` e' `None` no modo so-estudo: o eixo nao foi reprovado nem aprovado, ele
    nao existe naquele parecer (ver `_avaliar_conclusao`). `None` e' o unico valor que diz
    isso; um `_ConclusaoEixo` vazio sairia "Aprovado" e afirmaria o que ninguem avaliou.
    """

    demografico: _ConclusaoEixo
    financeiro: _ConclusaoEixo | None

    @property
    def eliminatorios(self) -> tuple[str, ...]:
        """Todos os eliminatorios, demografico antes de financeiro (ordem de leitura).

        Conveniencia de LEITURA sobre a lista de observacoes, que sempre foi uma coisa so
        e continua sendo -- a DEC-030 partiu o VEREDITO, nao os apontamentos. A pagina
        renderiza por bloco (`_conclusao_blocos`), nao por estas propriedades.
        """
        fin = self.financeiro.eliminatorios if self.financeiro else ()
        return self.demografico.eliminatorios + fin

    @property
    def ressalvas(self) -> tuple[str, ...]:
        fin = self.financeiro.ressalvas if self.financeiro else ()
        return self.demografico.ressalvas + fin


def _conclusao_valor(value: Any) -> float | None:
    """float FINITO utilizavel, ou None quando ausente/NaN/infinito/nao numerico.

    Infinito vira None de proposito: nenhum gate deve comparar contra `inf` por acidente.
    O unico campo em que `inf` carrega significado e o payback, tratado a parte em
    `_conclusao_retorno` (la `inf`/None quer dizer "nao paga no horizonte", nao "sem dado").
    """
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        numero = float(value)
    except (TypeError, ValueError):
        return None
    if numero != numero or numero in (float("inf"), float("-inf")):
        return None
    return numero


def _conclusao_flag(value: Any) -> bool:
    """True SO quando o flag veio e e' verdadeiro. Ausente/NaN -> False.

    Truthiness crua contrariava o invariante escrito no cabecalho desta secao: `NaN` e'
    truthy em Python, entao um flag corrompido reprovava o ponto por zona morta. O
    payload do browser manda `null`, mas um cliente que serialize com `allow_nan=True`
    injeta `NaN` -- e indecidivel nao pode reprovar.
    """
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    return bool(value)


def _conclusao_faixas_aluguel(dados: Mapping[str, Any]) -> tuple[float | None, float | None]:
    """(teto, excecao) resolvidos UMA vez, para o gate e o card lerem o MESMO par.

    O payload chega em duas formas: `aluguel_teto_faixas` (dict das 3 faixas) ou
    `aluguel_teto` ja achatado no canonico. Resolver isso em dois lugares diferentes
    deixava o gate MUDO enquanto o card ao lado pintava vermelho na mesma pagina -- a
    mesma classe de divergencia que o FIN-VIAB-01 combateu entre o PDF e a tela.
    """
    faixas = dados.get("aluguel_teto_faixas")
    faixas = faixas if isinstance(faixas, Mapping) else {}
    teto = _conclusao_valor(faixas.get("teto"))
    if teto is None:
        teto = _conclusao_valor(dados.get("aluguel_teto"))
    return teto, _conclusao_valor(faixas.get("excecao"))


def _conclusao_motivo_zona_morta(bruto: str) -> str:
    """Traduz o motivo TOKEN A TOKEN.

    `viabilidade_ponto` junta os motivos com "; " quando populacao E renda estao abaixo
    do piso -- ou seja, o caso MAIS grave era o unico que nunca traduzia, e saia
    "pop<5000; renda<1600" cru no PDF. Token desconhecido cai no fallback e sai como veio.
    """
    partes = [parte.strip() for parte in bruto.split(";") if parte.strip()]
    return "; ".join(_CONCLUSAO_MOTIVO_ZONA_MORTA.get(parte, parte) for parte in partes)


def _conclusao_metas_vermelhas(
    result: Mapping[str, Any], residual: Mapping[str, Any]
) -> tuple[tuple[str, str, str], ...]:
    """(rotulo, valor formatado, meta formatada) dos cards com meta NAO atingida.

    Reusa `_cor_por_meta` e as mesmas constantes `_META_*` que colorem o Big Numbers, em
    vez de reimplementar a comparacao: mexer numa meta muda o card E a conclusao juntos,
    sem drift entre a pagina que mostra o numero e a que da o parecer.
    """
    def _brl(valor: Any) -> str:
        return "R$ " + _format_number(valor, 2)

    def _int(valor: Any) -> str:
        return _format_number(valor, 0)

    avaliados: tuple[tuple[str, Any, float, Any], ...] = (
        ("População total no raio", result.get("pop_total_raio"), _META_POP_TOTAL_RAIO, _int),
        (
            "Renda per capita média",
            result.get("renda_per_capita_media_raio"),
            _META_RENDA_PER_CAPITA_MEDIA_RAIO,
            _brl,
        ),
        (
            "Número de domicílios",
            result.get("domicilios_total_raio"),
            _META_DOMICILIOS_TOTAL_RAIO,
            _int,
        ),
        (
            "Renda média domiciliar",
            result.get("renda_domiciliar_total_raio"),
            _META_RENDA_DOMICILIAR_TOTAL_RAIO,
            _brl,
        ),
        (
            "SAM Fitness",
            residual.get("sam_fitness_potencial"),
            _META_SAM_FITNESS_POTENCIAL,
            _int,
        ),
        (
            "Residual Fitness",
            residual.get("oferta_efetiva_disponivel"),
            _META_RESIDUAL_FITNESS_DISPONIVEL,
            _int,
        ),
    )
    return tuple(
        (rotulo, formata(valor), formata(meta))
        for rotulo, valor, meta, formata in avaliados
        if _cor_por_meta(valor, meta) == _CARD_VERMELHO_RGB
    )


def _conclusao_retorno(dados: Mapping[str, Any]) -> tuple[bool, bool, bool]:
    """(falha_margem, falha_payback, decidivel) da regua de retorno do cenario.

    As reguas vem do PROPRIO payload (`margem_viavel_min` / `payback_viavel_max`, servidas
    pelo backend a partir de `dimensionamento/config.py`). Sem elas -- payload legado --
    sobra o veredito pronto `flag_viavel`, que basta para RESSALVA e nunca para reprovar:
    sem os limites nao ha como saber se o cenario falhou em um criterio ou nos dois, e
    reprovar por inferencia violaria o principio de que indecidivel nao reprova.

    `payback` None ou infinito significa "nao paga dentro do horizonte" -- e' exatamente o
    que `_viab_payback` ja imprime como "> 60 meses" na pagina anterior --, portanto FALHA
    conhecida, nao dado ausente.
    """
    margem = _conclusao_valor(dados.get("margem_ebitda_pct"))
    margem_min = _conclusao_valor(dados.get("margem_viavel_min"))
    payback_max = _conclusao_valor(dados.get("payback_viavel_max"))
    if margem_min is None or payback_max is None or margem is None:
        return False, False, False
    payback = _conclusao_valor(dados.get("payback_meses"))
    return margem < margem_min, (payback is None or payback > payback_max), True


def _conclusao_eixo_financeiro(
    info: Mapping[str, Any], dados_viab: Mapping[str, Any]
) -> _ConclusaoEixo:
    """Eixo FINANCEIRO: os gates que dependem do IMOVEL e do cenario de retorno.

    Sao exatamente os criterios que o modo SO-ESTUDO (BLK-CONC-ESTUDO) desliga, porque
    nenhum deles tem insumo no caminho API/bot -- que nunca envia `viabilidade` nem
    `info_imovel`. Desde a DEC-030 essa mesma fronteira e' a do SELO financeiro: o modo
    so-estudo deixou de ser "meia regua" e passou a ser "um selo dos dois".

    A ZONA MORTA saiu daqui para o eixo demografico (DEC-030): o flag chega pelo payload de
    viabilidade, mas o que ele afirma -- `pop<5000` / `renda<1600` na captacao -- e' juizo
    sobre a praca. Manter os itens nesta ordem preserva a ordem de leitura de 2026-08-07.
    """
    eliminatorios: list[str] = []
    ressalvas: list[str] = []

    # --- Retorno do cenario (E1 / R1) ---
    falha_margem, falha_payback, decidivel = _conclusao_retorno(dados_viab)
    if decidivel and falha_margem and falha_payback:
        eliminatorios.append(
            "Retorno fora da régua da Ultra nos dois critérios ao mesmo tempo: margem "
            "operacional e prazo de retorno do investimento."
        )
    elif decidivel and falha_margem:
        ressalvas.append("Margem operacional abaixo do mínimo da régua da Ultra.")
    elif decidivel and falha_payback:
        ressalvas.append("Prazo de retorno do investimento acima do limite da régua da Ultra.")
    elif dados_viab.get("flag_viavel") is False:
        ressalvas.append("Cenário fora da régua de viabilidade da Ultra.")

    # --- Envelope fisico do imovel (E3 / R3) ---
    # Primeira aplicacao real de AREA_MIN_M2/AREA_IDEAL_*: eram canonicos declarados em
    # config.py e travados em teste de contrato, mas nao comparados com nada em lugar
    # nenhum. `PE_DIREITO_MIN` continua FORA daqui: o pe-direito foi retirado da regua a
    # pedido de Vinicius (2026-08-07) e volta a ser so um campo digitado e impresso na
    # pagina de informacoes do imovel.
    metragem = _conclusao_valor(info.get("metragem_m2"))
    if metragem is not None:
        if metragem < AREA_MIN_M2:
            eliminatorios.append(
                f"Metragem de {_format_number(metragem, 0)} m2 abaixo do mínimo de "
                f"{_format_number(AREA_MIN_M2, 0)} m2."
            )
        elif not AREA_IDEAL_MIN_M2 <= metragem <= AREA_IDEAL_MAX_M2:
            ressalvas.append(
                f"Metragem de {_format_number(metragem, 0)} m2 fora da faixa ideal de "
                f"{_format_number(AREA_IDEAL_MIN_M2, 0)} a "
                f"{_format_number(AREA_IDEAL_MAX_M2, 0)} m2."
            )
    # --- Aluguel pedido x faixas de aluguel-teto (E2 / R2) ---
    # MESMO par que o card imprime (`_conclusao_faixas_aluguel`): resolver separado fazia
    # o gate ficar mudo com o card vermelho ao lado, na mesma pagina.
    aluguel = _conclusao_valor(info.get("aluguel_pedido"))
    teto, excecao = _conclusao_faixas_aluguel(dados_viab)
    if aluguel is not None and excecao is not None and aluguel > excecao:
        eliminatorios.append(
            "Aluguel pedido acima do máximo admitido para este ponto: inviabiliza a "
            "operação no valor atual."
        )
    elif aluguel is not None and teto is not None and aluguel > teto:
        ressalvas.append(
            "Aluguel pedido acima do teto recomendado para este ponto: exige renegociação."
        )

    # --- Extrapolacao da base de calibracao (R5) ---
    if _conclusao_flag(dados_viab.get("flag_fora_envelope")):
        ressalvas.append(
            "Metragem fora do envelope da base de calibração: projeção com incerteza maior."
        )

    # --- Campos essenciais nao informados (R6) ---
    # Fecham a lista, como sempre fecharam. Ate a DEC-030 moravam em `_avaliar_conclusao`
    # justamente para nao subir na ordem de leitura; agora que o eixo financeiro e' um
    # bloco proprio, o fim do bloco E o mesmo lugar -- e o `if not somente_estudo` que os
    # protegia virou desnecessario: neste modo a funcao inteira nao roda.
    for chave, rotulo in _CONCLUSAO_CAMPOS_ESSENCIAIS:
        if _conclusao_valor(info.get(chave)) is None:
            ressalvas.append(
                f"{rotulo} não informado: o critério correspondente não pôde ser avaliado."
            )

    return _conclusao_eixo(eliminatorios, ressalvas)


def _avaliar_conclusao(
    result: Mapping[str, Any] | None,
    residual: Mapping[str, Any] | None,
    info_imovel: Mapping[str, Any] | None,
    dados_viab: Mapping[str, Any],
    *,
    somente_estudo: bool = False,
) -> _ConclusaoPonto:
    """Aplica a regua e devolve o parecer. FUNCAO PURA: sem I/O, sem motor, sem estado.

    `dados_viab` e o dict ja achatado por `_viab_normalizado` -- a conclusao LE os mesmos
    numeros que a pagina de Viabilidade imprime, nunca recalcula nenhum deles.

    `somente_estudo=True` (BLK-CONC-ESTUDO) avalia SO a base do estudo: o eixo DEMOGRAFICO.
    O eixo financeiro (`_conclusao_eixo_financeiro`) fica de fora INTEIRO -- nao "sem
    dado", e sim fora da regua --, porque no caminho API/bot ele nunca teve insumo e sairia
    todo como "nao informado", enchendo o parecer de ressalvas que nao dizem nada sobre o
    ponto. Desde a DEC-030 isso tem consequencia VISUAL direta: `financeiro is None` e a
    pagina desenha um selo so. O que RESTA e' a praca: metas censitarias, mercado do
    hexagono, zona morta e a ressalva de censo indisponivel -- mais o gate E5, que reprova
    quando as metas falham EM BLOCO (ver `_CONCLUSAO_METAS_ELIMINATORIO_MIN`).
    """
    result = result or {}
    residual = residual or {}
    info = info_imovel or {}
    eliminatorios: list[str] = []
    ressalvas: list[str] = []

    # --- Zona morta (E4) ---
    # Primeiro item do eixo demografico: e' o unico gate da praca que REPROVA fora do
    # so-estudo, entao encabecar a lista o poe no topo da coluna de observacoes. Le
    # `dados_viab` porque e' de la que o motor manda o flag -- ver o cabecalho da secao
    # sobre por que isso nao o torna financeiro.
    if _conclusao_flag(dados_viab.get("flag_zona_morta")):
        bruto = str(dados_viab.get("motivo_zona_morta") or "").strip()
        motivo = _conclusao_motivo_zona_morta(bruto)
        eliminatorios.append(
            f"Ponto em zona morta para a operação ({motivo})."
            if motivo
            else "Ponto em zona morta para a operação."
        )

    # --- Censo indisponivel para o ponto ---
    # As 4 metricas censitarias ausentes AO MESMO TEMPO significam que nenhum setor caiu
    # no raio (ponto no mar, particao geo do municipio ausente, borda da malha). Sem esta
    # ressalva o parecer saia "Aprovado" AFIRMANDO que o ponto "atende as metas
    # censitarias do raio" que nunca chegou a avaliar -- o reverso do invariante de
    # indecidivel: nao reprova por falta de dado, mas tambem nao pode APROVAR por ela.
    if all(
        _conclusao_valor(result.get(chave)) is None
        for chave in (
            "pop_total_raio",
            "renda_per_capita_media_raio",
            "domicilios_total_raio",
            "renda_domiciliar_total_raio",
        )
    ):
        ressalvas.append(
            "Metas censitárias não avaliadas: nenhum setor censitário no raio do ponto."
        )

    # --- Mercado e metas censitarias (R7 / R4) ---
    sam = residual.get("sam_fitness_potencial")
    disponivel = residual.get("oferta_efetiva_disponivel")
    mercado_consumido = _cor_consumo_concorrentes(sam, disponivel) == _CARD_VERMELHO_RGB
    if mercado_consumido:
        ressalvas.append(
            "Mercado já consumido pela oferta instalada: residual de "
            f"{_format_number(disponivel, 0)} contra potencial de {_format_number(sam, 0)} alunos."
        )

    # --- E5: metas censitarias falhando EM BLOCO (BLK-CONC-ESTUDO) ---
    # Vale nos DOIS modos desde a emenda da DEC-030 (Vinicius, 2026-08-14). Nasceu preso ao
    # so-estudo (escopo fechado por Juan em 2026-08-12: "a mudanca e' do PDF do bot, e so
    # dele"), e a divergencia que isso criava era conhecida e aceita -- mas ficava DILUIDA
    # num veredito unico. Com o selo demografico proprio ela virou um carimbo de cor
    # diferente entre dois documentos do MESMO ponto, e a separacao existe justamente para
    # a leitura da praca ser a mesma em qualquer lugar. Custo medido antes de estender:
    # nenhum dos 5 pontos do golden do Recife falha mais de 1 meta, contra corte 4 -- a
    # calibracao de Vinicius nao se move (travado por `test_e5_nao_desloca_o_golden_do_recife`).
    #
    # Conta sobre a lista CRUA, nao sobre a exibida: a linha do Residual e' suprimida logo
    # abaixo quando o mercado consumido ja a disse com mais contexto, e descontar isso do
    # gate faria o mesmo ponto reprovar ou nao conforme uma decisao de TEXTO.
    metas_vermelhas = _conclusao_metas_vermelhas(result, residual)
    if len(metas_vermelhas) >= _CONCLUSAO_METAS_ELIMINATORIO_MIN:
        eliminatorios.append(
            f"{len(metas_vermelhas)} das {_CONCLUSAO_METAS_AVALIADAS} metas censitárias do raio "
            "não atingidas ao mesmo tempo: a praça não sustenta a operação."
        )
    for rotulo, valor_txt, meta_txt in metas_vermelhas:
        # A meta do Residual ja foi dita, com mais contexto, na linha de mercado consumido
        # logo acima -- repeti-la seria afirmar a mesma coisa duas vezes no mesmo parecer.
        if mercado_consumido and rotulo == "Residual Fitness":
            continue
        ressalvas.append(f"Meta não atingida em {rotulo}: {valor_txt} para meta de {meta_txt}.")

    return _ConclusaoPonto(
        demografico=_conclusao_eixo(eliminatorios, ressalvas),
        financeiro=None if somente_estudo else _conclusao_eixo_financeiro(info, dados_viab),
    )


def _cor_aluguel_pedido(aluguel: Any, teto: Any, excecao: Any) -> tuple[int, int, int]:
    """Semaforo do card "Aluguel pedido": verde ate o teto, ambar na excecao, vermelho acima.

    Espelha a classificacao que a tela ja faz em `ViabilityScreen` (`tetoCls`), com uma
    simplificacao deliberada: la sao 4 estados (`ideal` tem verde proprio), aqui o `ideal`
    e o `teto` compartilham o verde, porque a pagina nao imprime a faixa `ideal` e um
    quarto tom sem rotulo que o explique so confundiria. Sem dado -> neutro, nunca
    reprovacao visual (mesma regra de `_cor_por_meta`). Funcao pura.
    """
    valor = _conclusao_valor(aluguel)
    limite_teto = _conclusao_valor(teto)
    limite_excecao = _conclusao_valor(excecao)
    if valor is None or limite_teto is None:
        return _CARD_NEUTRO_RGB
    if valor <= limite_teto:
        return _CARD_VERDE_RGB
    if limite_excecao is not None and valor <= limite_excecao:
        return _CARD_AMBAR_RGB
    return _CARD_VERMELHO_RGB


def _conclusao_simbolo(
    pdf: _UltraPDF, status: str, cx: float, cy: float, tam: float, rgb: tuple[int, int, int]
) -> None:
    """Desenha o simbolo do selo em VETOR (linhas/retangulos), nao como glifo de fonte.

    O selo da tela usa "✓" e "✕" (`ViabilityCharts.Veredito`), e os dois estao FORA do
    latin-1 -- no core font Helvetica do fpdf2 sairiam como "?" em silencio, que e'
    exatamente a armadilha que a regra de acentuacao do projeto descreve. Em vetor os
    tres estados ainda ganham o mesmo peso otico, o que misturar desenho com um "!"
    tipografico nao daria. Funcao de RENDER pura.
    """
    prev_lw = pdf.line_width
    espessura = max(2.5, tam * 0.13)
    pdf.set_draw_color(*rgb)
    pdf.set_fill_color(*rgb)
    pdf.set_line_width(espessura)
    meio = tam / 2
    if status == CONCLUSAO_APROVADO:
        # Check: desce ate o vertice baixo e sobe mais alto do lado direito.
        pdf.line(cx - meio, cy + tam * 0.04, cx - meio * 0.30, cy + meio * 0.66)
        pdf.line(cx - meio * 0.30, cy + meio * 0.66, cx + meio, cy - meio * 0.60)
    elif status == CONCLUSAO_REPROVADO:
        pdf.line(cx - meio * 0.68, cy - meio * 0.68, cx + meio * 0.68, cy + meio * 0.68)
        pdf.line(cx + meio * 0.68, cy - meio * 0.68, cx - meio * 0.68, cy + meio * 0.68)
    else:
        # Exclamacao: haste + ponto, preenchidos (nao ha traco "!" desenhavel a linha).
        # A haste e' ~1,8x a espessura das linhas dos outros dois simbolos DE PROPOSITO:
        # o "!" so ocupa uma faixa vertical estreita, entao com a mesma espessura ele
        # pesava menos que o check e o X e o selo intermediario parecia mais fraco.
        haste_w = espessura * 1.8
        pdf.rect(cx - haste_w / 2, cy - meio * 0.92, haste_w, tam * 0.60, style="F")
        pdf.rect(cx - haste_w / 2, cy + meio * 0.58, haste_w, haste_w, style="F")
    pdf.set_line_width(prev_lw)


def _conclusao_selo(
    pdf: _UltraPDF,
    eixo: str,
    status: str,
    x: float,
    y: float,
    largura: float,
    altura: float,
) -> None:
    """Selo de UM eixo: legenda em cima, simbolo no meio, rotulo embaixo, cor pelo estado.

    Mesma anatomia do carimbo de veredito da tela de Viabilidade (`Veredito`, escolha de
    Felipe em 2026-07-31: "bater o olho e ja ter o veredito"), portada para o PDF e
    estendida de 2 para 3 estados. Fundo no pastel que o resto do relatorio ja usa
    (`_CARD_*_RGB`); borda de 2 pt e simbolo/texto na cor SOLIDA correspondente, que
    existe so aqui -- os pasteis nao teriam contraste como traco.

    A LEGENDA no topo (DEC-030) e' o unico acrescimo a essa anatomia: com dois carimbos na
    mesma coluna, sem ela o leitor ve dois selos identicos em forma e nao sabe qual eixo
    cada um julga. Tudo abaixo dela escala com `altura`, para o mesmo desenho servir ao
    selo de 176 pt (dois eixos) e ao de qualquer outra altura. As fracoes de TAMANHO
    reproduzem o desenho de 2026-08-07 em `_CONCLUSAO_SELO_H_REF`; as de POSICAO nao, e nem
    poderiam -- elas foram reancoradas justamente para abrir o topo para a legenda. Ver o
    bloco de constantes para os numeros e a razao.
    """
    rgb = _CONCLUSAO_SELO_RGB[status]
    principal, secundario = _CONCLUSAO_SELO_TEXTOS[eixo][status]
    escala = altura / _CONCLUSAO_SELO_H_REF
    prev_lw = pdf.line_width

    pdf.set_fill_color(*_CONCLUSAO_CORES[status])
    pdf.rect(
        x, y, largura, altura,
        style="F", round_corners=True, corner_radius=_CONCLUSAO_SELO_RAIO,
    )
    pdf.set_draw_color(*rgb)
    pdf.set_line_width(2.0)
    pdf.rect(
        x, y, largura, altura,
        style="D", round_corners=True, corner_radius=_CONCLUSAO_SELO_RAIO,
    )
    pdf.set_line_width(prev_lw)

    pdf.set_text_color(*rgb)
    pdf.set_font("Helvetica", "B", _CONCLUSAO_SELO_LEGENDA_CORPO)
    pdf.set_xy(x, y + altura * _CONCLUSAO_SELO_LEGENDA_Y)
    pdf.cell(largura, _CONCLUSAO_SELO_LEGENDA_H, _ascii(_CONCLUSAO_SELO_LEGENDAS[eixo]), align="C")

    _conclusao_simbolo(
        pdf,
        status,
        x + largura / 2,
        y + altura * _CONCLUSAO_SELO_SIMBOLO_Y,
        altura * _CONCLUSAO_SELO_SIMBOLO_TAM,
        rgb,
    )
    # O rotulo principal encolhe se preciso: "COM RESSALVAS" e' bem mais largo que
    # "APROVADO" e nao pode vazar a borda do selo.
    pdf.set_xy(x, y + altura * _CONCLUSAO_SELO_PRINCIPAL_Y)
    _ajustar_fonte_para_largura(
        pdf, _ascii(principal), largura - 16, tamanho=_CONCLUSAO_SELO_PRINCIPAL_CORPO * escala
    )
    pdf.cell(largura, altura * _CONCLUSAO_SELO_PRINCIPAL_H, _ascii(principal), align="C")
    pdf.set_font("Helvetica", "B", _CONCLUSAO_SELO_SECUNDARIO_CORPO * escala)
    pdf.set_xy(x, y + altura * _CONCLUSAO_SELO_SECUNDARIO_Y)
    pdf.cell(largura, altura * _CONCLUSAO_SELO_SECUNDARIO_H, _ascii(secundario), align="C")


def _conclusao_cards_aluguel(
    pdf: _UltraPDF,
    dados: Mapping[str, Any],
    info_imovel: Mapping[str, Any] | None,
    x: float,
    y: float,
    largura: float,
    accent: tuple[int, int, int],
) -> None:
    """Aluguel-teto (referencia) e aluguel pedido (com semaforo), LADO A LADO.

    Moram na coluna ESQUERDA, acima das observacoes (pedido de Vinicius, 2026-08-07):
    a direita fica so com o selo. `largura` e' a da coluna inteira e os dois cards a
    dividem com `_CONCLUSAO_ALUGUEL_GAP` entre eles.

    O teto impresso e' o CANONICO (`aluguel_teto`, a faixa de 20%), o mesmo numero que o
    card da pagina de Viabilidade ja mostra -- nao a `excecao`, que fica so como regua do
    eliminatorio E2. Sem payload de teto ou sem aluguel informado, o card cai em "n/d"
    gracioso em vez de sumir, para a ausencia do dado ficar visivel no parecer.
    """
    info = info_imovel or {}
    # MESMO par que os gates E2/R2 usam -- ver `_conclusao_faixas_aluguel`.
    teto, excecao = _conclusao_faixas_aluguel(dados)
    aluguel = info.get("aluguel_pedido")

    cards = (
        ("Aluguel-teto (mês)", _viab_brl(teto), _CARD_NEUTRO_RGB),
        (
            "Aluguel pedido (mês)",
            _viab_brl(aluguel),
            _cor_aluguel_pedido(aluguel, teto, excecao),
        ),
    )
    card_h = _CONCLUSAO_ALUGUEL_H
    card_w = (largura - _CONCLUSAO_ALUGUEL_GAP) / 2
    for index, (rotulo, valor, cor) in enumerate(cards):
        esquerda = x + index * (card_w + _CONCLUSAO_ALUGUEL_GAP)
        pdf.set_fill_color(*cor)
        pdf.rect(esquerda, y, card_w, card_h, style="F")
        pdf.set_draw_color(225, 225, 228)
        pdf.rect(esquerda, y, card_w, card_h, style="D")
        pdf.set_fill_color(*accent)
        pdf.rect(esquerda, y, card_w, 5.0, style="F")
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_xy(esquerda + 14, y + 13)
        pdf.cell(card_w - 28, 13, _ascii(rotulo))
        pdf.set_text_color(40, 40, 40)
        valor_txt = _ascii(valor)
        _ajustar_fonte_para_largura(pdf, valor_txt, card_w - 28, tamanho=19.0)
        pdf.set_xy(esquerda + 14, y + 34)
        pdf.cell(card_w - 28, 22, valor_txt)


def _conclusao_itens(eixo: _ConclusaoEixo, confirmacao: str) -> tuple[tuple[str, str], ...]:
    """(texto, severidade) de UM eixo, na ordem de leitura: eliminatorios antes de ressalvas.

    Sem nenhum apontamento sobra o card de confirmacao, e ele e' do CHAMADOR: cada eixo
    afirma ter avaliado coisas diferentes, e um texto unico mentiria dos dois lados.
    """
    itens = [(texto, "eliminatorio") for texto in eixo.eliminatorios]
    itens += [(texto, "ressalva") for texto in eixo.ressalvas]
    return tuple(itens) or ((confirmacao, "confirmacao"),)


def _conclusao_blocos(
    parecer: _ConclusaoPonto, *, somente_estudo: bool = False
) -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    """(eixo, itens) na ordem de leitura da coluna: praca antes de imovel e retorno.

    A ordem espelha a dos SELOS na coluna direita -- demografico em cima -- para que a
    coluna esquerda seja lida de par com eles. No modo so-estudo sai um bloco so, porque
    o eixo financeiro nao existe naquele parecer (`financeiro is None`).
    """
    demografico = (
        _CONCLUSAO_APROVADO_TEXTO_ESTUDO if somente_estudo
        else _CONCLUSAO_APROVADO_TEXTO_DEMOGRAFICO
    )
    blocos = [
        (CONCLUSAO_EIXO_DEMOGRAFICO, _conclusao_itens(parecer.demografico, demografico))
    ]
    if parecer.financeiro is not None:
        blocos.append(
            (
                CONCLUSAO_EIXO_FINANCEIRO,
                _conclusao_itens(parecer.financeiro, _CONCLUSAO_APROVADO_TEXTO_FINANCEIRO),
            )
        )
    return tuple(blocos)


def _conclusao_altura_obs(pdf: _UltraPDF, texto: str, largura: float) -> float:
    """Altura do card de UMA observacao, medida sem desenhar nada.

    `dry_run` do `multi_cell` devolve as linhas que o texto ocuparia na largura dada; sem
    isso nao daria para centralizar o bloco verticalmente, porque a altura so seria
    conhecida DEPOIS de desenhar. Exige a fonte ja aplicada pelo chamador.
    """
    largura_texto = largura - 2 * _CONCLUSAO_OBS_PAD_X
    saida = pdf.multi_cell(
        largura_texto, _CONCLUSAO_OBS_LINHA_H, _ascii(texto), dry_run=True, output="LINES"
    )
    # O retorno de `multi_cell` e' uma UNIAO que depende de `output` (bool, float, lista
    # de linhas ou tuplas delas), e o mypy nao estreita isso pelo valor do argumento. A
    # checagem explicita satisfaz o type checker E degrada para 1 linha caso a assinatura
    # do fpdf2 mude -- um card de altura minima e' preferivel a um TypeError no relatorio.
    n = len(saida) if isinstance(saida, (list, tuple)) else 1
    return (
        _CONCLUSAO_OBS_ACENTO_H
        + max(1, n) * _CONCLUSAO_OBS_LINHA_H
        + 2 * _CONCLUSAO_OBS_PAD_Y
    )


@dataclass(frozen=True)
class _ConclusaoElemento:
    """Um card de observacao mais o titulo de bloco que porventura o abre.

    Modelar o titulo como PARTE do primeiro card do bloco (DEC-030) e' o que mantem
    `_conclusao_quantos_cabem` / `_conclusao_plano_observacoes` intactas: elas seguem vendo
    uma sequencia de alturas com gap uniforme, sem saber que ha dois blocos. O efeito
    colateral e' desejavel -- titulo e primeiro card cabem juntos ou nenhum dos dois cabe,
    entao nunca sobra um titulo orfao no pe da coluna anunciando um bloco vazio.
    """

    texto: str
    severidade: str
    titulo: str
    titulo_offset: float
    altura_card: float

    @property
    def altura_titulo(self) -> float:
        if not self.titulo:
            return 0.0
        return self.titulo_offset + _CONCLUSAO_OBS_TITULO_H + _CONCLUSAO_OBS_TITULO_GAP

    @property
    def altura(self) -> float:
        return self.altura_titulo + self.altura_card


def _conclusao_elementos(
    pdf: _UltraPDF,
    blocos: tuple[tuple[str, tuple[tuple[str, str], ...]], ...],
    largura: float,
) -> tuple[_ConclusaoElemento, ...]:
    """Achata os blocos numa sequencia de elementos com altura ja medida."""
    pdf.set_font("Helvetica", "", 10)
    elementos: list[_ConclusaoElemento] = []
    for indice, (eixo, itens) in enumerate(blocos):
        for posicao, (texto, severidade) in enumerate(itens):
            abre_bloco = posicao == 0
            elementos.append(
                _ConclusaoElemento(
                    texto=texto,
                    severidade=severidade,
                    titulo=_CONCLUSAO_BLOCO_TITULOS[eixo] if abre_bloco else "",
                    # O 1o bloco nasce logo abaixo dos cards de aluguel, que ja trazem o
                    # seu proprio respiro (`_CONCLUSAO_ALUGUEL_OBS_GAP`).
                    titulo_offset=_CONCLUSAO_BLOCO_GAP if abre_bloco and indice else 0.0,
                    altura_card=_conclusao_altura_obs(pdf, texto, largura),
                )
            )
    return tuple(elementos)


def _conclusao_altura_bloco(elementos: tuple[_ConclusaoElemento, ...]) -> float:
    """Altura do conteudo inteiro de observacoes: titulos, cards e gaps entre eles."""
    return sum(elemento.altura for elemento in elementos) + _CONCLUSAO_OBS_GAP * max(
        0, len(elementos) - 1
    )


def _conclusao_quantos_cabem(alturas: tuple[float, ...], y: float, limite: float) -> int:
    """Quantos cards, na ordem, cabem entre `y` e `limite`. Puro, sem tocar no PDF."""
    topo = y
    cabem = 0
    for altura in alturas:
        if topo + altura > limite:
            break
        topo += altura + _CONCLUSAO_OBS_GAP
        cabem += 1
    return cabem


def _conclusao_plano_observacoes(alturas: tuple[float, ...], y: float) -> tuple[int, float]:
    """(quantos cards desenhar, y onde a linha de aviso entra). Funcao pura.

    Quando nem todos cabem, a conta e' REFEITA com a altura do aviso ja reservada. Sem
    isso o loop enchia a coluna ate o limite e a linha "(+N nao exibido(s))" era escrita
    POR CIMA do ultimo card -- os dois textos sobrepostos e ilegiveis.
    """
    cabem = _conclusao_quantos_cabem(alturas, y, _CONCLUSAO_AREA_BASE)
    if cabem < len(alturas):
        # Desconta o aviso E o gap: `_conclusao_quantos_cabem` garante que o ultimo CARD
        # termina dentro do limite, mas o aviso comeca um gap depois disso. Sem descontar
        # os dois, o aviso ainda estourava a area por ate `_CONCLUSAO_OBS_GAP` pt.
        cabem = _conclusao_quantos_cabem(
            alturas,
            y,
            _CONCLUSAO_AREA_BASE - _CONCLUSAO_OBS_AVISO_H - _CONCLUSAO_OBS_GAP,
        )
    return cabem, y + sum(alturas[:cabem]) + _CONCLUSAO_OBS_GAP * cabem


def _conclusao_plano_elementos(
    elementos: tuple[_ConclusaoElemento, ...], y: float
) -> tuple[tuple[int, ...], float]:
    """(indices a desenhar, y do aviso) repartindo o espaco ENTRE os blocos, por rodadas.

    DEFEITO QUE ISTO CORRIGE (visto na revisao visual da DEC-030): preenchendo a coluna na
    ordem, um ponto ruim em tudo enchia-a inteira com o bloco demografico e o bloco
    financeiro nao entrava -- nem o titulo. O selo financeiro ficava carimbado REPROVADO ao
    lado de uma coluna que nao trazia UMA linha sobre o financeiro. E' exatamente o
    "reprova, mas nunca em silencio" que a pagina promete desde 2026-08-06, quebrado pela
    unica via que a lista unica nao tinha: a truncagem.

    Por rodadas, cada bloco entra com o seu primeiro elemento antes de qualquer bloco pegar
    o segundo -- e como o primeiro elemento de um bloco e' o que carrega o titulo, e como a
    ordem dentro do bloco poe os eliminatorios na frente, o que cada selo tem de mais grave
    aparece antes de qualquer ressalva do outro. Um bloco que nao caiba mais e' pulado sem
    travar os demais (`continue`), entao um bloco de cards altos nao bloqueia um bloco de
    card curto que ainda caberia.

    Funcao PURA: recebe alturas ja medidas, nao toca no PDF.
    """
    alturas = tuple(elemento.altura for elemento in elementos)
    cabem, y_aviso = _conclusao_plano_observacoes(alturas, y)
    if cabem >= len(elementos):
        return tuple(range(len(elementos))), y_aviso

    # Trunca: a partir daqui o aviso e' certo, entao o limite ja desconta a linha dele --
    # mesma reserva (e mesma razao) de `_conclusao_plano_observacoes`.
    limite = _CONCLUSAO_AREA_BASE - _CONCLUSAO_OBS_AVISO_H - _CONCLUSAO_OBS_GAP
    filas: list[list[int]] = []
    for indice, elemento in enumerate(elementos):
        if elemento.titulo or not filas:
            filas.append([])
        filas[-1].append(indice)

    escolhidos: list[int] = []
    fim = y
    coube_alguma = True
    while coube_alguma:
        coube_alguma = False
        for fila in filas:
            if not fila:
                continue
            candidato = fila[0]
            proximo = fim + alturas[candidato] + (_CONCLUSAO_OBS_GAP if escolhidos else 0.0)
            if proximo > limite:
                continue
            fim = proximo
            escolhidos.append(fila.pop(0))
            coube_alguma = True
    return tuple(sorted(escolhidos)), fim + _CONCLUSAO_OBS_GAP


def _conclusao_card_observacao(
    pdf: _UltraPDF, texto: str, severidade: str, x: float, y: float, largura: float, altura: float
) -> None:
    """Um card de observacao: fundo + borda fina + barra de acento no topo + texto."""
    fundo, acento = _CONCLUSAO_OBS_CORES[severidade]
    pdf.set_fill_color(*fundo)
    pdf.rect(x, y, largura, altura, style="F")
    pdf.set_draw_color(225, 225, 228)
    pdf.rect(x, y, largura, altura, style="D")
    pdf.set_fill_color(*acento)
    pdf.rect(x, y, largura, _CONCLUSAO_OBS_ACENTO_H, style="F")
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(
        x + _CONCLUSAO_OBS_PAD_X, y + _CONCLUSAO_OBS_ACENTO_H + _CONCLUSAO_OBS_PAD_Y
    )
    pdf.multi_cell(largura - 2 * _CONCLUSAO_OBS_PAD_X, _CONCLUSAO_OBS_LINHA_H, _ascii(texto))


def _conclusao_page(
    pdf: _UltraPDF,
    result: dict[str, Any],
    residual: dict[str, Any] | None,
    info_imovel: dict[str, Any] | None,
    viabilidade: dict[str, Any] | None,
    assets: dict[str, bytes | None],
    *,
    primary: tuple[int, int, int] = ULTRA_TURQUESA,
    secondary: tuple[int, int, int] = ULTRA_MAGENTA,
    somente_estudo: bool = False,
) -> None:
    """Pagina de parecer do ponto, em 2 COLUNAS: conteudo a esquerda, selos a direita.

    Estrutura pedida por Vinicius (2026-08-07), com DOIS selos desde a DEC-030. A direita
    ficam so eles, empilhados -- demografico em cima, financeiro embaixo --, cada um com a
    anatomia do carimbo de veredito da tela de Viabilidade (quadrado de cantos
    arredondados, simbolo em cima, rotulo embaixo, cor pelo estado). A esquerda ficam os
    dois cards de aluguel e, abaixo deles, as observacoes agrupadas nos MESMOS dois blocos
    e na mesma ordem -- cada apontamento em CARD proprio, com o peso visual dos cards de
    valor. As duas colunas sao centralizadas VERTICALMENTE na area de conteudo, cada uma no
    seu proprio eixo. READ-ONLY sobre o M1.

    `somente_estudo=True` (BLK-CONC-ESTUDO) e' o modo do caminho API/bot: `viabilidade`
    pode vir `None`, os dois cards de aluguel SOMEM (sao numeros financeiros, e sem payload
    imprimiriam "n/d" duas vezes), o selo FINANCEIRO nao e' desenhado -- o eixo nao existe
    naquele parecer -- e o demografico volta a ocupar a coluna sozinho, centrado. A nota
    metodologica troca junto -- ver `_CONCLUSAO_NOTA_ESTUDO`.
    """
    dados = _viab_normalizado(viabilidade) if viabilidade else {}
    parecer = _avaliar_conclusao(
        result, residual, info_imovel, dados, somente_estudo=somente_estudo
    )

    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, _CONCLUSAO_PAGE_TITLE, rgb=primary)

    margem = _CONCLUSAO_MARGEM_X
    largura_esq = _CONCLUSAO_COL_ESQ_W
    area_h = _CONCLUSAO_AREA_BASE - _CONCLUSAO_AREA_TOPO

    # --- Coluna DIREITA: os selos dos eixos avaliados, centrados na vertical ---
    selos: list[tuple[str, str]] = [(CONCLUSAO_EIXO_DEMOGRAFICO, parecer.demografico.status)]
    if parecer.financeiro is not None:
        selos.append((CONCLUSAO_EIXO_FINANCEIRO, parecer.financeiro.status))
    bloco_selos_h = len(selos) * _CONCLUSAO_SELO_H + _CONCLUSAO_SELO_GAP * (len(selos) - 1)
    y_selo = _CONCLUSAO_AREA_TOPO + max(0.0, (area_h - bloco_selos_h) / 2)
    for eixo, status in selos:
        _conclusao_selo(
            pdf,
            eixo,
            status,
            _CONCLUSAO_COL_DIR_X,
            y_selo,
            _CONCLUSAO_COL_DIR_W,
            _CONCLUSAO_SELO_H,
        )
        y_selo += _CONCLUSAO_SELO_H + _CONCLUSAO_SELO_GAP

    # --- Coluna ESQUERDA: cards de aluguel + cards de observacao, centrados na vertical ---
    blocos = _conclusao_blocos(parecer, somente_estudo=somente_estudo)
    elementos = _conclusao_elementos(pdf, blocos, largura_esq)
    # No modo so-estudo os cards de aluguel nao existem -- e a altura deles NAO pode entrar
    # na conta, senao o bloco de observacoes nasce 94 pt abaixo do centro da area.
    altura_aluguel = 0.0 if somente_estudo else _CONCLUSAO_ALUGUEL_H + _CONCLUSAO_ALUGUEL_OBS_GAP
    conteudo_h = altura_aluguel + _conclusao_altura_bloco(elementos)
    # `max(0, ...)`: conteudo mais alto que a area comeca no TOPO em vez de subir acima da
    # banda de titulo -- e a guarda de altura mais abaixo corta o excedente com aviso.
    y = _CONCLUSAO_AREA_TOPO + max(0.0, (area_h - conteudo_h) / 2)

    if not somente_estudo:
        _conclusao_cards_aluguel(pdf, dados, info_imovel, margem, y, largura_esq, secondary)
    y += altura_aluguel

    desenhar, y_aviso = _conclusao_plano_elementos(elementos, y)
    for indice in desenhar:
        elemento = elementos[indice]
        if elemento.titulo:
            y += elemento.titulo_offset
            pdf.set_text_color(45, 45, 45)
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_xy(margem, y)
            pdf.cell(largura_esq, _CONCLUSAO_OBS_TITULO_H, _ascii(elemento.titulo))
            y += _CONCLUSAO_OBS_TITULO_H + _CONCLUSAO_OBS_TITULO_GAP
        _conclusao_card_observacao(
            pdf, elemento.texto, elemento.severidade, margem, y, largura_esq, elemento.altura_card
        )
        y += elemento.altura_card + _CONCLUSAO_OBS_GAP
    restantes = len(elementos) - len(desenhar)
    if restantes > 0:
        # Truncar em SILENCIO faria a pagina parecer completa quando nao esta.
        pdf.set_text_color(*_CINZA_TEXTO)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_xy(margem, y_aviso)
        pdf.cell(
            largura_esq,
            12,
            _ascii(f"(+{restantes} apontamento(s) não exibido(s) por falta de espaço.)"),
        )

    # A nota metodologica volta a ocupar a largura TOTAL: ela fala da pagina inteira, nao
    # da coluna de observacoes, e presa aos 652 pt da esquerda ganharia varias linhas.
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_xy(margem, _CONCLUSAO_NOTA_Y)
    pdf.multi_cell(
        _PAGE_W - 2 * margem,
        11,
        _ascii(_CONCLUSAO_NOTA_ESTUDO if somente_estudo else _CONCLUSAO_NOTA),
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


def _draw_confidencial(
    pdf: _UltraPDF,
    *,
    rgb: tuple[int, int, int] = _WATERMARK_RGB,
    alpha: float = _CONFIDENCIAL_ALPHA,
) -> None:
    """Marca d'agua diagonal "ARQUIVO CONFIDENCIAL", centrada na pagina.

    Translucida de proposito: marca a seriedade do arquivo sem roubar a leitura do
    conteudo. Mesma mecanica da `_draw_watermark` (chamada DEPOIS do conteudo, fica por
    cima; `local_context` restaura o graphics state ao sair); a rotacao gira em torno do
    centro da pagina, na diagonal do slide 16:9.
    """
    pdf.set_font("Helvetica", "B", _CONFIDENCIAL_FONT_PT)
    pdf.set_text_color(*rgb)
    w = pdf.get_string_width(_CONFIDENCIAL_TEXT)
    # Baseline ~1/3 do corpo abaixo do pivo: centro OTICO do texto no centro da pagina.
    y = _PAGE_H / 2 + _CONFIDENCIAL_FONT_PT * 0.35
    with pdf.local_context(fill_opacity=alpha):
        with pdf.rotation(_CONFIDENCIAL_ANGLE, _PAGE_W / 2, _PAGE_H / 2):
            pdf.text((_PAGE_W - w) / 2, y, _CONFIDENCIAL_TEXT)


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


# Aviso de ORIGEM do estudo, impresso quando o chamador passa `origem_centroide_hex=True`
# (hoje: o piloto web, quando o ponto veio do clique num hexagono e nao ha endereco — a
# coordenada e' o centroide do hex res-7, a ate ~1,5 km do imovel que o operador imagina).
# Quem le o PDF precisa saber que o raio foi tracado dali; nao ha aviso equivalente na tela.
#
# String FIXA de proposito: e' texto de PRODUTO, controlado aqui, nao texto do usuario. A
# versao anterior deste aviso viajava anexada ao proprio `rotulo` entre parenteses e era
# reextraida por heuristica no gerador — o que mutilava rotulo legitimo com parenteses
# ("Av. Paulista, 1500 (Shopping Center 3)"). O marcador agora e' um parametro explicito.
#
# Latin-1 puro (fpdf2 core font): acentos portugueses OK, sem travessao/reticencias/bullet.
_AVISO_ORIGEM_CENTROIDE_HEX = (
    "Estudo a partir do centroide do hexágono - não de um endereço exato."
)


def _cor_por_meta(valor: Any, meta: float) -> tuple[int, int, int]:
    """Cor de fundo do card: verde se valor >= meta, vermelho se < meta, neutro quando sem dado.

    BLK-RELPON-08 (D3/Q2): sem dado (None/NaN) e tratado ANTES da comparacao numerica -- condicao
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
    Fitness < meta); VERDE caso contrario. Sem dado em SAM OU em Residual -> neutro (condicao
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
    """(e) Big Numbers — grid 4x2 das 8 metricas. READ-ONLY; sem dado auditavel.

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
        # A fonte encolhe quando o texto nao cabe em uma linha (`TEXTO_SEM_DADO`, valores
        # longos) -- sem isso o multi_cell quebraria em 2 linhas e vazaria a base do card.
        pdf.set_text_color(40, 40, 40)
        valor_txt = _ascii(value)
        _ajustar_fonte_para_largura(pdf, valor_txt, card_w - 28)
        pdf.set_xy(x + 14, y + 74)
        pdf.multi_cell(card_w - 28, 28, valor_txt)

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
            f"{_RAIO_LABEL}, método {metodo}); SAM Fitness, Residual Fitness (em alunos) e consumo = leitura "
            "direta do hexágono H3. Fundo do card: verde = meta atingida, vermelho = "
            f"meta não atingida, cinza = '{TEXTO_SEM_DADO}' (dado ausente para o ponto)."
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
    INALTERADOS (D3/D3.5); `_format_number` ja devolve `TEXTO_SEM_DADO` para ausente.
    """
    renda_raw = perfil.get("renda_media_domiciliar")
    # "R$" so quando ha valor; sem dado exibe so o texto (evita "R$ Nao disponivel").
    renda_str = (
        "R$ " + _format_number(renda_raw, 2)
        if renda_raw is not None and not pd.isna(renda_raw)
        else TEXTO_SEM_DADO
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
    """Texto da banda turquesa: endereco/nome quando ha rotulo real, senao a coordenada.

    O `rotulo` chega INTEIRO e sai inteiro (so' truncado em 80 chars por largura da banda):
    ele e' texto livre do operador e nada dele e' reinterpretado aqui. O aviso de origem
    (`origem_centroide_hex`) e' um parametro separado e NAO entra na banda — ele sai em
    linha propria na capa e na Realizacao.
    """
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
    origem_centroide_hex: bool = False,
) -> None:
    """Capa classica: texto por baseline, todo na coluna limpa da arte (x>=460, y 300-450).

    Empilhamento de cima para baixo: aviso de origem (condicional, y=402) -> endereco (y=430)
    -> subtitulo (y=455). Nada desce abaixo de `_CAPA_RODAPE_LOGOS_TOP` (y=461,4), onde comeca
    a faixa de logos BRANCOS da arte, nem passa da margem direita da pagina.
    """
    pdf.add_page()
    has_bg = assets.get("capa") is not None
    _draw_full_page_background(pdf, assets.get("capa"), ULTRA_TURQUESA)

    lat = result.get("lat")
    lng = result.get("lng")
    coord = (
        f"{float(lat):.5f}, {float(lng):.5f}"
        if lat is not None and lng is not None
        else f"coordenada {TEXTO_SEM_DADO.lower()}"
    )
    nome = str(rotulo or "").strip()
    endereco = _ascii(nome if (nome and not _parece_coordenada(nome)) else f"Coordenada: {coord}")
    subtitulo = f"Relatório Pontual Censitário - Raio {_RAIO_LABEL} | {_classico_mes_ano(now)}"

    # Zona limpa inferior-direita quando ha fundo de marca; centro quando nao ha.
    base_x = _CAPA_BASE_X_COM_ARTE if has_bg else _CAPA_BASE_X_SEM_ARTE
    largura_util = _PAGE_W - base_x - _CLASSICO_MARGIN
    pdf.set_text_color(*_BRANCO)

    # Aviso de ORIGEM (string FIXA do modulo) em LINHA PROPRIA, na MESMA coluna do endereco e
    # ACIMA dele. Ficava a x=20 / baseline y=518, ou seja DENTRO da faixa de rodape da arte
    # (comeca em y=461,4) e por cima do logo BRANCO da Ultra (x~140-270) — texto branco sobre
    # logo branco: ilegivel e riscando a marca. Aqui a caixa e' turquesa chapado medido.
    # Largura: 314,1 pt a 10 pt contra 462 pt uteis (base_x=478 ate a margem direita) -> 147,9
    # pt de folga em UMA linha; a string e' texto de produto, fixa, entao a folga nao varia.
    if origem_centroide_hex:
        pdf.set_font("Helvetica", "", _CAPA_AVISO_FONT_PT)
        pdf.text(base_x, _CAPA_AVISO_Y, _ascii(_AVISO_ORIGEM_CENTROIDE_HEX))

    # Endereco ACIMA (baseline y=430), subtitulo ABAIXO (baseline y=455, acima da linha y=461,4).
    # O endereco e' TEXTO LIVRE do operador e precisa caber nos `largura_util` pt ate a margem
    # direita: primeiro encolhe a fonte (26 -> 15 pt), e so' se ainda nao couber corta pela
    # largura REAL. "Galpao Comercial Avenida Brasil, 4500" mede 481,2 pt a 26 pt (vazava a
    # borda) e passa a sair inteiro a 24 pt; rotulo que ja cabia continua a 26 pt e sem corte.
    _ajustar_fonte_para_largura(
        pdf,
        endereco,
        largura_util,
        tamanho=_CAPA_ENDERECO_FONT_PT,
        minimo=_CAPA_ENDERECO_FONT_MIN_PT,
    )
    pdf.text(base_x, _CAPA_ENDERECO_Y, _truncar_por_largura(pdf, endereco, largura_util))
    pdf.set_font("Helvetica", "", 13)
    pdf.text(base_x, _CAPA_SUBTITULO_Y, _ascii(subtitulo))


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
    `TEXTO_SEM_DADO` gracioso quando o perfil nao esta disponivel (ponto fora da malha de setores ou
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
    origem_centroide_hex: bool = False,
) -> None:
    """Realizacao/Credito: fundo turquesa solido + credito/metodo + aviso de dados
    dinamicos (`_AVISO_DADOS_DINAMICOS`) + link clicavel do ponto + data por extenso.

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
        _ascii(_AVISO_DADOS_DINAMICOS),
        align="C",
    )

    # Bloco "Link para localizacao do ponto:" + endereco como link clicavel. A query e' o
    # `rotulo` INTEIRO, como o operador digitou — o aviso de origem e' parametro proprio e
    # nunca entrou aqui (dentro da busca do Google Maps so atrapalharia o resultado).
    nome = str(rotulo or "").strip()
    if nome and not _parece_coordenada(nome):
        link_query = nome
        link_label = nome if len(nome) <= 80 else nome[:77] + "..."
    else:
        lat = result.get("lat")
        lng = result.get("lng")
        link_query = f"{float(lat):.6f},{float(lng):.6f}" if lat is not None and lng is not None else ""
        link_label = link_query or TEXTO_SEM_DADO
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

    # Segunda (e ultima) aparicao do aviso de origem, em linha propria e centrada. Repetido
    # de proposito: capa e Realizacao sao as duas paginas que quem recebe o PDF olha inteiro,
    # e o aviso nao pode depender de uma unica linha. Largura medida: ~293 pt a 10 pt na
    # celula de 880 pt — uma linha, sem risco de estouro (string fixa do modulo).
    if origem_centroide_hex:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_xy(40, 408)
        pdf.cell(_PAGE_W - 80, 14, _ascii(_AVISO_ORIGEM_CENTROIDE_HEX), align="C")

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
    origem_centroide_hex: bool = False,
    conclusao_so_estudo: bool = False,
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

    `conclusao_so_estudo=True` (BLK-CONC-ESTUDO) faz a pagina de Conclusao sair TAMBEM sem
    `viabilidade`, em modo so-estudo -- e o que o caminho API/bot pede. Default `False`
    preserva o comportamento historico: sem o payload, sem pagina.

    `rotulo` e o nome/endereco do ponto (capa + banda + texto do link) — TEXTO LIVRE de quem
    chama, impresso e usado na busca do link SEM reinterpretacao (parenteses, virgulas e
    numeros no fim continuam parte do endereco). `origem_centroide_hex=True` acrescenta, em
    linha propria na CAPA e na REALIZACAO, o aviso fixo de que o estudo saiu do centroide do
    hexagono e nao de um endereco exato; default `False` = nenhuma linha nova (comportamento
    historico intacto para bot e API). O aviso NAO entra na banda das paginas de
    conteudo (largura fixa) nem na query do link. `perfil_bairro`
    (BLK-RELPON-07) e o dict de `agregar_perfil_bairro_distrito`; `None` (default) produz a
    pagina com `TEXTO_SEM_DADO` gracioso. `now` e injetavel para data determinista em teste. `solicitante`
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
    # Ordinal 5: o primeiro LIVRE (0..4 em uso) e a pagina de Conclusao. Como os ordinais
    # sao ABSOLUTOS -- nao um contador incremental de paginas --, tomar o 5 nao desloca a
    # cor de nenhuma pagina existente. 5 e' impar -> turquesa primaria / magenta acento.
    p5, s5 = _tema_bicolor(5)

    pdf = _UltraPDF()
    _classico_cover_page(
        pdf, result, assets, rotulo=rotulo, now=now, origem_centroide_hex=origem_centroide_hex
    )
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
    # CONCLUSAO: fecha o relatorio com o parecer do ponto, logo antes do credito.
    #
    # COM `viabilidade` -> parecer completo, como desde 2026-08-06.
    # SEM `viabilidade` -> so entra se o chamador PEDIR (`conclusao_so_estudo=True`), e ai
    # roda em modo so-estudo. Hoje quem pede e' `api/service.py` (caminho API/bot), que
    # nunca teve o payload e por isso nunca via a pagina.
    #
    # O flag existe para CONFINAR o BLK-CONC-ESTUDO ao caminho da API (escopo fechado por
    # Juan em 2026-08-12). Sem ele, o piloto web -- que chama esta funcao com
    # `viabilidade=None` quando o operador nao preencheu o formulario (`web/server/app.py`)
    # -- ganharia a pagina junto, fora do escopo pedido. Default `False` = comportamento
    # historico intacto para todo chamador que nao se manifeste.
    if viabilidade or conclusao_so_estudo:
        _conclusao_page(
            pdf,
            result,
            residual,
            info_imovel,
            viabilidade,
            assets,
            primary=p5,
            secondary=s5,
            somente_estudo=not viabilidade,
        )
    _classico_credit_page(
        pdf, result, assets, rotulo=rotulo, now=now, origem_centroide_hex=origem_centroide_hex
    )

    # Marca d'agua POR CIMA do conteudo de cada pagina (BLK-EST-01, D2=todas as paginas).
    # Escrever na pagina `n` via `pdf.page = n` ANEXA ao stream dessa pagina -> sobreposicao.
    # Capa em branco (fundo turquesa), demais em cinza.
    wm_text = _watermark_text(solicitante)
    for page_number in range(1, pdf.pages_count + 1):
        pdf.page = page_number
        rgb = _WATERMARK_RGB_COVER if page_number == 1 else _WATERMARK_RGB
        alpha = _CONFIDENCIAL_ALPHA_CAPA if page_number == 1 else _CONFIDENCIAL_ALPHA
        _draw_confidencial(pdf, rgb=rgb, alpha=alpha)
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
    origem_centroide_hex: bool = False,
    conclusao_so_estudo: bool = False,
) -> bytes:
    """DEPRECIADA (BLK-RELPON-14): wrapper fino de `gerar_pdf_relatorio_pontual_classico`.

    O template "recente" foi DESCONTINUADO: a estetica CLASSICA venceu a unificacao (ja era o
    default de producao no dashboard, na API e no bot) e passou a ser a implementacao unica.
    Esta funcao existe SO para retrocompatibilidade dos chamadores que ainda a importam pelo
    nome — ela repassa TODOS os kwargs e devolve o PDF classico, emitindo `DeprecationWarning`.
    Prefira chamar `gerar_pdf_relatorio_pontual_classico` diretamente.

    A assinatura e' um SUPERSET da anterior: alem dos kwargs historicos, aceita `now`,
    `foto_satelite`, `foto_satelite_grande`, `origem_centroide_hex` e `conclusao_so_estudo`,
    que so a classica aceitava. Qualquer chamada que funcionava antes continua funcionando
    (os novos parametros tem default inerte).
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
        origem_centroide_hex=origem_centroide_hex,
        conclusao_so_estudo=conclusao_so_estudo,
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
