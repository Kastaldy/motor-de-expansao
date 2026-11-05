"""Relatorio Municipal (BLK-RELMUN-01) — PDF de 9 paginas por municipio selecionado.

Modulo NOVO e disjunto. COEXISTE com o Relatorio Pontual Censitario (raio 1,0 km),
que fica BYTE-A-BYTE INTOCADO (este modulo NAO importa nenhum helper `_`-prefixado de
`censo_report.py`/`censo_map.py`; os helpers de layout/desenho sao reimplementados aqui
para isolamento total). READ-ONLY sobre o M1: nao recalcula `score_priorizacao`,
`hex_score_estrutural`, pesos, carteira, plano, plano de dominio nem artefatos oficiais.

Decisoes do gate humano (Vinicius, 2026-06-22 — DEC-011):
- D1 (emenda BLK-RELMUN-03, 2026-07-02): hex DESTACADO ("amarelo") <=>
  `oferta_efetiva_disponivel >= 2000` (Residual Fitness; termo de SAM removido).
  Rotulo sobre o hex = `oferta_efetiva_disponivel`.
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

BLK-RELMUN-02 (resolve D9): a Pagina 6 lista bairros REAIS (IBGE 2022 `NM_BAIRRO`) agrupados
pelas 3 zonas geometricas quando `bairros_por_hex` e resolvido (via `_carregar_bairros_por_hex`,
leitura OFFLINE da particao geo do municipio); fallback gracioso por zona geometrica quando o
municipio nao tem bairro mapeado (cobertura IBGE heterogenea). READ-ONLY sobre o M1.

DEC-076: o nome do bairro passa a vir do CNEFE 2022 (bairro dominante por setor), com o
`NM_BAIRRO` da malha como RESERVA. Os dois leitores de setores daqui (`_carregar_bairros_por_hex`
e `carregar_bairros_geo`) passam por `bairro_cnefe.aplicar_bairro_cnefe` antes da cascata, entao
a Pagina 6 (bairros por zona), os rotulos dos hexes destacados e os "Bairros oficiais" agrupam
pelo MESMO bairro. Sem o artefato, tudo e' o de antes.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from fpdf import FPDF
from PIL import Image, ImageChops, ImageDraw, ImageFont

from motor_expansao.dashboard.bairro_cnefe import (
    FONTE_CNEFE,
    aplicar_bairro_cnefe,
    bairro_cnefe_disponivel,
)
from motor_expansao.dashboard.censo_map import (
    _BASEMAP_TILES_URL_ENV,
    _fetch_labels,
)
from motor_expansao.dashboard.censo_map import (
    _atribuicao_tiles as _censo_atribuicao_tiles,
)
from motor_expansao.dashboard.competitors import (
    PIN_INDEPENDENTE_PX,
    ROTULO_AGREGADOR,
    _render_square_logo_tile,
    chave_agregador_da_fonte,
)
from motor_expansao.dashboard.constants import TEXTO_SEM_DADO
from motor_expansao.dashboard.utils import score_band_to_color
from motor_expansao.perfil import resolver_perfil
from motor_expansao.renda import hex as _renda_hex

from . import pdf_base

if TYPE_CHECKING:
    from motor_expansao.dashboard.relatorio_praca import PracaDaCidade

# ---------------------------------------------------------------------------
# Constantes de DISPLAY do relatorio (DEC-011 parte 2). Locais a este modulo;
# NAO mexem em flag_sam/DEC-006/DEC-007 (pipeline de mercado) nem no M1.
# BLK-RELMUN-03 (DEC-011 emenda): criterio de destaque passou a ser SO Residual Fitness (>=2000).
# ---------------------------------------------------------------------------
# SEGUNDA copia (a primeira e `web/server/app.py`) — e a que faz deste arquivo o
# TERCEIRO CRITICO do Bloco A, que nenhum documento listava antes da spec §8.1.
OFERTA_DESTAQUE_MIN = resolver_perfil().reguas.oferta_destaque_min
CAPACIDADE_UNIDADE = 2500.0
H3_RES = 7

# BLK-RELPON-09 (S2a): lado (px do PNG-fonte) do marcador de concorrente/Ultra nos mapas
# municipais. 26 px preserva a razao 34/40 = 0,85 que o Municipal ja tinha frente ao
# Pontual: mesmo canvas de 1000 px, porem cobrindo um MUNICIPIO inteiro -> muito mais
# pins e maior risco de colisao. Logo util: ~14 px (balao) -> ~22 px (quadrado).
_PIN_LOGO_PX = 26
# Rasterizacao (px) da logo embutida no PDF da pagina "Concorrentes por rede": desenhada
# a 14 pt, 64 px cobre ~300 dpi sem inchar o PDF (o crop antigo do balao era 54x54).
_REDE_LOGO_RASTER_PX = 64

# Carimbo de versao do contrato deste relatorio (D8 / espirito DEC-005 item 6).
# Carimbo do rodape (DEC-005 decisao 6: versao no PDF para REPRODUTIBILIDADE). Sobe para v2
# porque a estrutura mudou de verdade: 9 -> 12 paginas, unidade de leitura escolhivel
# (bairro/hexagono) e renda da tabela virou domiciliar. Manter "v1" faria dois PDFs com o mesmo
# carimbo e conteudos incomparaveis -- que e' exatamente o que o carimbo existe para evitar.
# v3 (2026-10-22): paginas novas e removidas na reforma dos slides e, no Brasil, a resposta unica
# de "onde expandir" (DEC-077) no lugar dos aprovados -- de novo estrutura e conteudo diferentes.
VERSAO_CONTRATO_MUNICIPAL = "BLK-RELMUN | contrato v3 | score M1 INALTERADO"
METODO_RELATORIO_MUNICIPAL = "agregacao_municipal_h3_res7"

#: Chave do resultado que liga a RESPOSTA UNICA de "onde expandir" (DEC-077) no PDF. O preparo
#: (`api.service.montar_pdf_municipio`) a liga quando o pais tem regua de recomendacao (Brasil);
#: sem ela -- Argentina, ou quem chama o PDF direto -- o relatorio segue como antes da DEC-077.
#: Ligada: "Onde crescer" = Mata Virgem + Premium do modulo unico; Visao Geral e Resumo sem o
#: verde de aprovado nem a tabela de bairros aprovados; sem Expansao de Dominio, Bairros por Zona
#: e o card de zonas da Sintese (voltam com os dados do gestor); Espaco so' como leitura.
CHAVE_RESPOSTA_UNICA = "resposta_unica"


def _resposta_unica(result: dict[str, Any] | None) -> bool:
    return bool((result or {}).get(CHAVE_RESPOSTA_UNICA))


def _rotulo_espaco_leitura() -> str:
    """Rotulo do Espaco para academias na resposta unica (DEC-077): leitura de capacidade, sem
    sugerir onde abrir (pedido do Felipe, 2026-10-21)."""
    return ("capacidade não atendida nas regiões com residual a partir de "
            f"{_format_number(OFERTA_DESTAQUE_MIN, 0)} alunos")

# Cabecalhos canonicos das 11 paginas fixas, iguais nas duas unidades (desde 2026-10-20 com "Como
# chegamos ao Espaco para academias"). Fora daqui: uma pagina por parte dos Bairros Oficiais em
# municipio grande e as 4 da praca. No Brasil (DEC-077) Expansao de Dominio, Bairros por Zona e,
# desde 2026-10-22, a Visao Geral nao saem: 8 fixas, 12 com a praca. Renderizam em latin-1 (core
# font Helvetica do fpdf2),
# que cobre integralmente os acentos portugueses -- o que e PROIBIDO e tipografia fora de
# latin-1 (travessao/bullet/seta/reticencias/aspas curvas/(c)), que vira "?" silenciosamente
# via _ascii(..., errors="replace"). Cada string aparece nos bytes crus do PDF (compressao OFF).
PDF_SECTION_HEADERS = (
    "Potencial de Entrada de Novas Unidades",
    "Bairros Oficiais",
    "Score Censitário",
    "Residual Fitness",
    "Visão Geral do Município",
    "Resumo da Região",
    "Como chegamos ao Espaço para academias",
    "Expansão de Domínio",
    "Bairros por Zona",
    "Síntese",
    "Espaço e academias",
)

# Paleta Ultra (RGB 0..255). Espelha censo_report (cores canonicas), reimplementado local.
ULTRA_TURQUESA = (0, 167, 157)
ULTRA_MAGENTA = (194, 60, 142)
ULTRA_LARANJA = (240, 148, 30)
ULTRA_BRANCO_GELO = (248, 248, 248)
_BRANCO = (255, 255, 255)
_CINZA_TEXTO = (60, 60, 60)
_NAVY_CAPA = (30, 28, 58)

# Cores dos hexagonos APROVADOS por PROCEDENCIA do dado de populacao (realce; pedido de
# Vinicius 2026-06-24; cor otimista verde por Vinicius 2026-07-08, BLK-RELMUN-05): dado
# PROPRIO do hex (setor censitario 2022, `fonte_populacao_corte == "setor_2022"`) = verde
# forte; aprovado via FALLBACK MUNICIPAL (`total_municipal`/`ausente`) = amarelo-ambar
# (tom mais amarelado p/ distinguir do dado proprio; Vinicius 2026-07-10, BLK-RELMUN-05-FU1).
# Reprovado/neutro = cinza. Camada de DISPLAY; nao toca M1.
_COR_APROVADO_PROPRIO = (20, 170, 80)
_COR_APROVADO_MUNICIPAL = (215, 200, 60)
_COR_REPROVADO = (150, 156, 170)

# Camada Resumo (alpha 200): destacado + neutro (nao-destacado). Desde 2026-10-21 o aprovado por
# fallback municipal tambem sai verde: sem legenda (Juan), o amarelo nao teria explicacao.
_HEX_DESTAQUE_RGBA = (*_COR_APROVADO_PROPRIO, 200)
_HEX_NEUTRO_RGBA = (176, 182, 196, 110)
_CIRCLE_INK = (31, 41, 55)

# BLK-RELPON-09-FU1: realce dos rotulos sobre os hexagonos (valor de Residual Fitness na
# camada "resumo" e numero de zona na camada "dominio"). Decisao de PRODUTO de Vinicius no
# gate visual de 2026-07-21, escolhida sobre 4 alternativas (branco opaco, grafite, turquesa):
# a placa MAGENTA e a unica cor que nao colide com nada no mapa -- os hexagonos sao verdes/
# cinza, o basemap e claro e os marcadores de rede sao pretos/azuis/amarelos. Reusa o
# `ULTRA_MAGENTA` do proprio modulo (mesma tinta das bandas/frames do relatorio), em vez de
# introduzir um magenta quase-igual. Parametrizado -> reajustar e mudanca de 1 linha.
_ROTULO_PLACA_RGBA = (*ULTRA_MAGENTA, 240)
_ROTULO_INK = (255, 255, 255)

# Slide "Visao Geral do Municipio" (FU1): hexagonos do MUNICIPIO em 3 categorias.
# Aprovado dado proprio (verde forte) / Aprovado fallback municipal (verde medio) / Reprovado (cinza).
# Camada de DISPLAY; nao toca M1.
_HEX_APROVADO_RGBA = (*_COR_APROVADO_PROPRIO, 210)
_HEX_REPROVADO_RGBA = (*_COR_REPROVADO, 170)
#: Regiao com espaco no mapa "Como chegamos ao Espaco" na resposta unica (DEC-077, Brasil): laranja
#: escuro (o tom do "Espaco para academias"), com o mesmo contraste do verde para o numero branco.
#: O verde de antes era o do aprovado e quase o da Mata Virgem no "Onde crescer".
_HEX_ESPACO_RGBA = (180, 90, 10, 245)
#: Circulo do numero de academias por regiao nessa pagina: grafite, que nao se confunde com as ruas
#: brancas nem com os nomes pretos do fundo de ruas, e destaca no laranja e no verde.
_ESPACO_NUMERO_RGB = (40, 40, 48)

# Slide "Bairros oficiais" (BLK-RELMUN-06): LIMITE TERRITORIAL real de cada bairro, obtido
# dissolvendo os setores censitarios (IBGE 2022, `geometry_wkb`) pela MESMA cascata de
# localidade ja usada em `_carregar_bairros_por_hex`. Camada de DISPLAY: geometria de bairro
# NAO entra em score, carteira, plano nem em qualquer artefato do M1.
#
# A paleta espelha o material de referencia do time de Expansao (estudo GeoFusion): contorno de
# bairro em VERMELHO sobre basemap claro, divisa do MUNICIPIO em preto, miolo quase transparente
# (o arruamento do basemap tem de continuar legivel por baixo - e o que da a nocao de onde o
# bairro fica). Sem preenchimento opaco de proposito.
_BAIRRO_CONTORNO = (226, 0, 26)
_BAIRRO_CONTORNO_RGBA = (*_BAIRRO_CONTORNO, 235)
_BAIRRO_FILL_RGBA = (255, 255, 255, 26)
_BAIRRO_DESTAQUE_FILL_RGBA = (*_COR_APROVADO_PROPRIO, 70)
_MUNICIPIO_CONTORNO_RGBA = (17, 17, 17, 235)
_BAIRRO_ROTULO_INK = (31, 41, 55)
# A area SEM bairro na base ("<municipio> (demais setores)") sai com contorno CINZA, nunca no
# vermelho de bairro: em municipio com cobertura ruim ela e a cidade inteira, e pinta-la como
# divisa faria o mapa afirmar um limite que o IBGE nao da. Cinza = "aqui nao ha bairro mapeado".
_SOBRA_CONTORNO_RGBA = (120, 128, 140, 190)
# SEM preenchimento desde 2026-10-22 (Juan, SJC): a sobra e' quase sempre mata, parque ou zona
# rural, e o fundo de ruas (OpenMapTiles) mostra isso -- o cinza tapava o verde que explica o
# vazio. Reverte o alpha 90 de 2026-08-19 (Tangara da Serra/MT, "uma area em branco", quando o
# alpha 30 sumia no basemap claro). O que segue declarando o estado e' o CONTORNO cinza e o
# rodape ("sem cor, contorno cinza: sem bairro na base").
_SOBRA_FILL_RGBA = (120, 128, 140, 0)

# Tabela de comparacao das regioes (BLK-RELMUN-07): quantas linhas cabem numa pagina 16:9 sem
# encolher a fonte a ponto de nao se ler em projecao. O material de referencia do time usa 15
# ("as 15 melhores ranqueados"); mantemos o mesmo teto para a leitura ficar familiar.
_TABELA_HEXES_LIMITE = 15

# Unidade de leitura do relatorio, escolhida por QUEM PEDE (Juan, 2026-08-19: o bot passa a
# oferecer "Municipal (hexagonos)" e "Municipal (bairros)" como opcoes separadas).
# - "bairro"   -> tematicos por bairro + as paginas Bairros Oficiais e Nucleo Urbano.
# - "hexagono" -> tematicos por hexagono e SEM as paginas de bairro (o relatorio classico).
# A escolha e' explicita de proposito: cada unidade responde melhor a uma pergunta, e antes
# disso o codigo decidia sozinho -- o que surpreendia quem esperava a outra.
UNIDADE_BAIRRO = "bairro"
UNIDADE_HEXAGONO = "hexagono"

# Recorte do NUCLEO URBANO (BLK-RELMUN-11). Municipio de fronteira agricola tem a cidade em
# ~2% do territorio (Sinop/MT, Tangara da Serra/MT): enquadrar o municipio inteiro faz os
# bairros virarem um ponto. Estas constantes definem o "onde a cidade esta de fato".
#
# Criterio = DENSIDADE, nao populacao bruta: um distrito rural extenso pode ter muita gente
# somada e ainda assim nao ser cidade. Ordena por hab/km2 desc e acumula ate cobrir
# `_URBANO_POP_ALVO` da populacao; o bbox desses bairros e' o nucleo.
_URBANO_POP_ALVO = 0.85
# Piso de densidade, como FRACAO da densidade do bairro mais denso. Sem ele o alvo de 85%
# acima e' uma armadilha: quando o nucleo urbano sozinho nao alcanca a meta, o laco continua
# somando bairros cada vez mais esparsos ate o recorte voltar a ser o municipio inteiro --
# exatamente o que esta pagina existe para evitar. Com o piso, a area rural fica de fora
# mesmo que a meta nao seja atingida.
_URBANO_DENS_MIN_FRAC = 0.10
# Extensao MINIMA do recorte (m). Sem isto, municipio de nucleo minusculo geraria um zoom
# absurdo, com o basemap ilegivel.
_URBANO_SPAN_MIN_M = 4000.0
_URBANO_PAD_FRAC = 0.10

# Abaixo desta fracao de setores COM localidade, a pagina para de vender a contagem de bairros
# como se fosse o municipio mapeado e passa a avisar que a malha vem incompleta. Palmas/TO e o
# caso-limite que motivou o corte: 2 distritos rurais mapeados e 717 de 733 setores sem nada --
# um "2 bairros" seco daria a entender que a cidade tem dois bairros.
_BAIRRO_COBERTURA_MIN = 0.5

# Simplificacao das divisas antes do desenho, em GRAUS (a particao geo vem em EPSG:4674).
# 3e-5 graus ~ 3 m: imperceptivel no PNG de 1000 px e corta ~90% dos vertices, que e o que
# mantem a pagina leve em municipio grande (Sao Paulo tem 27.301 setores).
_BAIRRO_SIMPLIFY_GRAUS = 3e-5
# Area minima (fracao da maior parte do bairro) para uma ilha entrar no desenho: descarta
# slivers de topologia do dissolve sem apagar bairro descontinuo de verdade.
_BAIRRO_PARTE_MIN_FRAC = 0.02

# Atribuicao do rodape. UMA constante para os dois modos (fallback Voyager e self-host), porque
# nos dois o CARTO e' de fato consumido.
#
# HISTORICO, para nao regredir: o BLK-BASEMAP-02 criou um `_ATRIBUICAO_TILES_SELFHOST =
# "(c) OpenStreetMap"` resolvido em runtime, com o raciocinio correto na epoca — no self-host o
# fundo vem do tileserver proprio e este relatorio, ao contrario do Pontual, nao tinha overlay de
# rotulos, entao creditar CARTO seria credito falso. O efeito COLATERAL era o mapa municipal
# perder os NOMES DE RUA: o estilo `ultra-maptiler` tem as geometrias de via (`transportation`)
# mas nao a camada `transportation_name`, enquanto o Voyager trazia os nomes embutidos no raster.
# O BLK-BASEMAP-03 fecha isso reusando o `_fetch_labels` do Pontual aqui tambem -> o CARTO volta
# a ser consumido nos DOIS modos e o credito duplo volta a ser o unico honesto.
_ATRIBUICAO_TILES = "(c) OpenStreetMap, (c) CARTO"

_ASSET_CAPA = "relatorio_capa_bg.png"
_ASSET_CONTEUDO = "relatorio_conteudo_bg.png"
_ASSET_LOGO = "logo_ultra.png"
_ASSET_ICONE = "icone_ultra.png"
_DEFAULT_ULTRA_DIR = Path("data/ultra")

# Slide 16:9 widescreen em pontos (13.333in x 7.5in = 960 x 540 pt).
_PAGE_W = 960.0
_PAGE_H = 540.0

# Marca d'agua de rastreabilidade (anti-PII; embutida em todas as 9 paginas, stream OFF).
_WATERMARK_BASE = "Ultra Academia"
_WATERMARK_RGB = (120, 120, 120)
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
    ("Médio-alto", 50.0, 70.0),
    ("Médio", 30.0, 50.0),
    ("Baixo potencial", 0.0, 30.0),
)

# Cores das 3 zonas geometricas de dominio (FU1; camada de DISPLAY, NAO altera dominio_df/M1).
_ZONA_CORES_PDF = (ULTRA_TURQUESA, ULTRA_MAGENTA, ULTRA_LARANJA)
_ZONA_CORES_RGBA = (
    (0, 167, 157, 205),    # 1 Ancora central — turquesa
    (194, 60, 142, 205),   # 2 Flancos laterais — magenta
    (240, 148, 30, 205),   # 3 Cerco — laranja
)
_ZONA_GEO_ROTULOS = ("Âncora central", "Flancos laterais", "Cerco")
_ZONA_GEO_DESC = (
    "Adensar o núcleo central da região.",
    "Capturar residuais nas laterais.",
    "Ocupar as bordas antes da concorrência.",
)

# Prettify de nomes de rede para a Pagina 8 (Slide 8). Overrides conhecidos + fallback
# generico (title-case trocando "_" por espaco). Camada de display; nao toca a base.
_REDE_NOME_OVERRIDES = {
    "allp_fit": "Allp Fit",
    "bio_ritmo": "Bio Ritmo",
    "smart_fit": "Smart Fit",
    "bluefit": "BlueFit",
    "bodytech": "Bodytech",
    "cia_athletica": "Cia Athletica",
    "tonus_gym": "Tonus Gym",
    "vidya_studio": "Vidya Studio",
    "aera_pilates": "Aera Pilates",
    "race_bootcamp": "Race Bootcamp",
    "phd_sports": "PHD Sports",
    "selfit": "Selfit",
    "panobianco": "Panobianco",
    "velocity": "Velocity",
    "skyfit": "SkyFit",
    "redfit": "RedFit",
}


def _chave_rede(rede: Any) -> str:
    """Chave da rede do pin; "" quando a linha nao tem rede (academia independente)."""
    if rede is None or pd.isna(rede):
        return ""
    return str(rede).strip()


def _prettify_rede(rede: str) -> str:
    """Nome legivel da rede: override conhecido ou title-case trocando '_' por espaco."""
    key = str(rede or "").strip()
    if not key:
        return "Concorrente"
    if key in ROTULO_AGREGADOR:
        # `[DEC-066]` Era o literal "Independentes (Wellhub)" cravado aqui. Com o TotalPass no
        # entregavel, o slide 8 escreveria o nome do app ERRADO para as academias que so'
        # existem nele.
        return ROTULO_AGREGADOR[key]
    low = key.casefold()
    if low in _REDE_NOME_OVERRIDES:
        return _REDE_NOME_OVERRIDES[low]
    return low.replace("_", " ").title()


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
    """Numero formatado pt-BR; ausente/NaN -> `TEXTO_SEM_DADO` (por extenso desde 2026-07-31).

    Os valores que caem em celula de fonte grande deste relatorio (Residual do municipio,
    contagem de hexes, contagem de pins) sao somas/contagens e NUNCA sao NaN; os que podem ser
    NaN (renda media, score medio, populacao) so aparecem em tabela de rotulo+valor, onde a
    string longa cabe. Por isso aqui nao ha o encolhimento de fonte do Relatorio Pontual.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)) or pd.isna(value):
        return TEXTO_SEM_DADO
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


def academias_por_hex(df_muni: pd.DataFrame) -> dict[str, int]:
    """Quantas academias de `CAPACIDADE_UNIDADE` alunos cabem em cada hexagono APROVADO.

    Residual / 2.500 por hexagono, arredondado pelos MAIORES RESTOS: cada um fica com a parte
    inteira e as academias que sobram vao para as maiores fracoes. Assim os numeros do mapa somam
    exatamente o "Espaco para academias" do Resumo (arredondar um a um dava 536 em Sao Paulo,
    contra 545). Hexagono que fica com 0 nao entra. So' display; a formula e' a da DEC-011.
    """
    if df_muni is None or df_muni.empty or "hex_id" not in df_muni.columns:
        return {}
    destaque = _hex_destacado_mask(df_muni)
    oferta = _coluna_numerica(df_muni, "oferta_efetiva_disponivel")
    cotas: dict[str, float] = {}
    for h, o, d in zip(df_muni["hex_id"], oferta, destaque, strict=True):
        if d and not math.isnan(float(o)):
            cotas[str(h)] = cotas.get(str(h), 0.0) + float(o) / CAPACIDADE_UNIDADE
    if not cotas:
        return {}
    alvo = int(round(sum(cotas.values())))
    inteiros = {h: int(math.floor(v)) for h, v in cotas.items()}
    sobra = alvo - sum(inteiros.values())
    for h in sorted(cotas, key=lambda k: (-(cotas[k] - inteiros[k]), k))[: max(sobra, 0)]:
        inteiros[h] += 1
    return {h: n for h, n in inteiros.items() if n > 0}


def _municipio_mask(df: pd.DataFrame, nome_municipio: str) -> pd.Series:
    """Mascara de linhas do municipio: tenta `nome_municipio`, fallback `cidade`."""
    alvo = str(nome_municipio).strip().casefold()
    mask = pd.Series(False, index=df.index)
    for col in ("nome_municipio", "cidade"):
        if col in df.columns:
            mask = mask | (df[col].astype(str).str.strip().str.casefold() == alvo)
    return mask


def _hex_destacado_mask(df_muni: pd.DataFrame) -> pd.Series:
    """D1 (emenda BLK-RELMUN-03): destacado <=> oferta_efetiva_disponivel>=2000 (Residual Fitness; termo de SAM removido)."""
    if df_muni.empty:
        return pd.Series(False, index=df_muni.index)
    oferta = _coluna_numerica(df_muni, "oferta_efetiva_disponivel")
    return oferta >= OFERTA_DESTAQUE_MIN


def _fonte_propria_mask(df_muni: pd.DataFrame) -> pd.Series:
    """True quando o hex usa DADO PROPRIO (setor censitario 2022) na regua de populacao do
    corte (`fonte_populacao_corte == "setor_2022"`); False = aprovado via FALLBACK MUNICIPAL
    (`total_municipal`/`ausente`). Sem a coluna (ex.: df sintetico de teste), assume dado
    proprio -> preserva o realce historico de cor unica (sem regressao)."""
    if df_muni.empty or "fonte_populacao_corte" not in df_muni.columns:
        return pd.Series(True, index=df_muni.index)
    return df_muni["fonte_populacao_corte"].astype(str).eq("setor_2022")


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

    rotulos = ("Âncora central", "Flancos laterais", "Cerco")
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



def _localidade_do_setor(row: pd.Series) -> str | None:
    """Cascata bairro -> subdistrito -> distrito; ignora niveis grossos == nome do municipio.

    Extraida de dentro de `_carregar_bairros_por_hex` (comportamento IDENTICO) para virar a
    UNICA definicao de "localidade do setor" do modulo: a Pagina de Bairros por Zona (rotulo
    por hex) e a de Bairros oficiais (limite territorial) tem de concordar sobre o que e um
    bairro, senao o mapa desenha uma divisao e a lista ao lado nomeia outra.
    """
    muni = row.get("nome_municipio")
    muni_norm = str(muni).strip().casefold() if muni is not None and not pd.isna(muni) else ""
    for col in ("nome_bairro", "nome_subdistrito", "nome_distrito"):
        val = row.get(col)
        if val is None or pd.isna(val):
            continue
        nome = str(val).strip()
        if not nome or nome.casefold() == "nan":
            continue
        if col != "nome_bairro" and muni_norm and nome.casefold() == muni_norm:
            continue
        return nome
    return None


def _carregar_bairros_por_hex(
    uf: str | None,
    cod_municipio: str | None,
    censo_geo_dir: Path | None,
    staging_dir: Path | str | None = None,
) -> dict[str, str]:
    """A2.3: le a particao geo do municipio e mapeia `hex_id` res-7 -> localidade dominante.

    READ-ONLY e OFFLINE: usa `ler_particao_setores` (parquet local) para obter, por setor, o
    nome da localidade em CASCATA `nome_bairro` -> `nome_subdistrito` -> `nome_distrito` (decisao
    de produto 2026-06-24: bairros reais onde existem; lacunas usam o nivel mais grosso, ex.: SP
    usa distritos, DF idem), ignorando subdistrito/distrito que seja so o nome do municipio
    (redundante). Deriva o centroide do setor (do bbox), mapeia a `hex_id` res-7 via h3 (import
    lazy) e resolve a localidade DOMINANTE por hex (mais populosa vence). Fallback gracioso: sem
    `censo_geo_dir`/particao/coluna -> `{}` (Pagina 6 simplificada).

    `staging_dir` (DEC-076): a configuracao de staging do processo, onde mora o artefato do
    CNEFE; `None` cai no fallback derivado de `censo_geo_dir` (ver `bairro_cnefe`).
    """
    return bairros_por_hex_de_setores(
        carregar_setores_com_bairro(uf, cod_municipio, censo_geo_dir, staging_dir=staging_dir)
    )


def carregar_setores_com_bairro(
    uf: str | None,
    cod_municipio: str | None,
    censo_geo_dir: Path | None,
    staging_dir: Path | str | None = None,
) -> pd.DataFrame | None:
    """Setores do municipio com o bairro JA' resolvido pelo CNEFE (DEC-076) -- o miolo de
    `_carregar_bairros_por_hex`, sem a reducao por hexagono.

    Quem nomeia o hexagono pelo bairro de mais moradores parte DESTE frame: o mapa municipal
    (`bairros_por_hex_de_setores`) e os nomes da recomendacao unica
    (`recomendacao.bairros_ordenados_por_hex`, DEC-077), para o mesmo hexagono nunca ganhar dois
    nomes. `None` sem particao/colunas.
    """
    if censo_geo_dir is None or not uf or not cod_municipio:
        return None
    _bbox_pop = ["bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy", "pop_total_setor_2022"]
    # Tenta a cascata completa (bairro/subdistrito/distrito + nome_municipio p/ o guard); se a
    # particao for de um schema antigo sem essas colunas, cai para so `nome_bairro`.
    tentativas = [
        ["nome_bairro", "nome_subdistrito", "nome_distrito", "nome_municipio", *_bbox_pop],
        ["nome_bairro", *_bbox_pop],
    ]
    # DEC-076: com o artefato do CNEFE para a UF, le tambem `cod_setor` (a chave dele). Sem o
    # artefato a leitura e' a de sempre, coluna a coluna. Particao SEM `cod_setor` (schema
    # antigo) cai nas leituras de antes: o bairro segue o do IBGE, nunca some.
    if bairro_cnefe_disponivel(censo_geo_dir, uf, staging_dir=staging_dir):
        tentativas = [[*cols, "cod_setor"] for cols in tentativas] + tentativas
    setores = _ler_setores_em_tentativas(censo_geo_dir, uf, cod_municipio, tentativas)
    if setores is None:
        return None
    return aplicar_bairro_cnefe(setores, censo_geo_dir=censo_geo_dir, uf=uf, staging_dir=staging_dir)


def _ler_setores_em_tentativas(
    censo_geo_dir: Path | str,
    uf: str,
    cod_municipio: str,
    tentativas: list[list[str]],
) -> pd.DataFrame | None:
    """Le a particao com a PRIMEIRA lista de colunas que o schema aceitar; `None` se nenhuma."""
    try:
        from motor_expansao.pipelines.materializar_setores_censitarios_geo import (
            ler_particao_setores,
        )
    except Exception:
        return None
    for colunas in tentativas:
        try:
            return ler_particao_setores(
                root=Path(censo_geo_dir), uf=str(uf), cod_municipio=str(cod_municipio),
                columns=colunas,
            )
        except Exception:
            continue
    return None


def bairros_por_hex_de_setores(setores: pd.DataFrame | None) -> dict[str, str]:
    """`hex_id` res-7 -> localidade dominante, a partir de setores JA' em memoria.

    O miolo de `_carregar_bairros_por_hex`, sem a leitura da particao: quem ja' tem os setores
    carregados (a ficha de ponto, que leu a particao para o raio) nomeia o hexagono sem reler
    o disco. A regra e' a MESMA, entao o mesmo conjunto de setores da' o mesmo nome. O recorte
    e' de quem chama: passar so' os setores de um municipio reproduz o mapa daquele municipio.
    """
    if setores is None or setores.empty or "nome_bairro" not in setores.columns:
        return {}

    import h3

    # Para cada hex, soma a populacao por localidade; a mais populosa vence (dominante).
    pop_por_hex_bairro: dict[str, dict[str, float]] = {}
    for _, row in setores.iterrows():
        nome = _localidade_do_setor(row)
        if not nome:
            continue
        minx = _safe_float(row.get("bbox_minx"))
        miny = _safe_float(row.get("bbox_miny"))
        maxx = _safe_float(row.get("bbox_maxx"))
        maxy = _safe_float(row.get("bbox_maxy"))
        if any(math.isnan(v) for v in (minx, miny, maxx, maxy)):
            continue
        lat_c = (miny + maxy) / 2.0
        lon_c = (minx + maxx) / 2.0
        try:
            hid = str(h3.latlng_to_cell(float(lat_c), float(lon_c), H3_RES))
        except Exception:
            continue
        peso = _safe_float(row.get("pop_total_setor_2022"))
        if math.isnan(peso) or peso < 0:
            peso = 0.0
        # Garante presenca do bairro mesmo com pop 0 (peso minimo de desempate).
        bucket = pop_por_hex_bairro.setdefault(hid, {})
        bucket[nome] = bucket.get(nome, 0.0) + peso + 1e-6

    bairros_por_hex: dict[str, str] = {}
    for hid, bucket in pop_por_hex_bairro.items():
        # Bairro dominante: maior pop; desempate estavel por nome.
        nome_dom = max(sorted(bucket), key=lambda n: bucket[n])
        bairros_por_hex[hid] = nome_dom
    return bairros_por_hex


def tem_bairro_real(bairros_geo: dict[str, Any] | None) -> bool:
    """Ha ao menos UM bairro de verdade (fora a sobra "<municipio> (demais setores)")?

    NAO basta a lista ser nao-vazia: municipio sem nenhuma localidade no IBGE (Apodi/RN)
    produz uma lista com SO a sobra, e desenhar "por bairro" nesse caso pinta um poligono
    unico do municipio inteiro -- pior que o mapa de hexagono que substituiu (perde toda a
    variacao intramunicipal) e ainda faz o rodape afirmar uma agregacao inexistente.
    """
    return any(not b.get("sobra") for b in ((bairros_geo or {}).get("bairros") or []))


def bairros_aprovados(bairros_geo: dict[str, Any] | None) -> list[str] | None:
    """Nomes dos bairros aprovados (maioria da populacao em hexagono aprovado), em ordem alfabetica.

    `None` quando nao da para dizer -- sem bairro real ou sem as metricas de mercado de
    `aplicar_metricas_hex_nos_bairros` -- e a Visao Geral volta aos paineis de contagem. A sobra
    "(demais setores)" nunca entra: e' area sem bairro, nao bairro.
    """
    if not tem_bairro_real(bairros_geo) or not (bairros_geo or {}).get("metricas_mercado"):
        return None
    nomes = {
        str(b["nome"])
        for b in (bairros_geo or {}).get("bairros") or []
        if b.get("destacado") and not b.get("sobra")
    }
    # Ordem sem acento ("Agua Rasa" antes de "Alto de Pinheiros"), como o leitor procura.
    return sorted(
        nomes,
        key=lambda n: unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().casefold(),
    )


def _partes_desenhaveis(geom: Any) -> list[Any]:
    """Poligonos de `geom` que valem desenho, do maior para o menor, sem slivers do dissolve.

    Uniao de setores vizinhos costuma deixar farpas de area ~0 nas bordas compartilhadas; elas
    nao mudam o desenho e so pesam. Mantem partes com area >= `_BAIRRO_PARTE_MIN_FRAC` da maior
    (bairro descontinuo de verdade sobrevive; farpa some).

    So devolve POLIGONO: `unary_union` de setores que se tocam apenas por borda pode render uma
    GeometryCollection com LineString/Point dentro, e quem consome aqui le `.exterior` -- sem este
    filtro a pagina inteira morreria num AttributeError por causa de uma farpa de topologia.
    """
    if geom is None or geom.is_empty:
        return []
    partes = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    partes = [
        p for p in partes
        if p is not None and not p.is_empty and p.geom_type == "Polygon" and p.area > 0
    ]
    if not partes:
        return []
    partes.sort(key=lambda p: p.area, reverse=True)
    corte = partes[0].area * _BAIRRO_PARTE_MIN_FRAC
    return [p for p in partes if p.area >= corte]


def carregar_bairros_geo(
    uf: str | None,
    cod_municipio: str | None,
    censo_geo_dir: Path | str | None,
    staging_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Limite territorial de cada bairro do municipio, em EPSG:3857, pronto para desenho.

    Dissolve os setores censitarios da particao geo (IBGE 2022, `geometry_wkb` em EPSG:4674)
    pela cascata de `_localidade_do_setor`. Setor SEM localidade nenhuma entra num agregado
    "<municipio> (demais setores)" -- o mesmo tratamento do material de referencia do time de
    Expansao, que nomeia assim a area rural/nao-loteada que sobra fora dos bairros.

    Devolve, por bairro: nome, aneis do contorno projetados em 3857, ponto de rotulo, populacao,
    area e renda per capita (media ponderada por populacao). READ-ONLY e OFFLINE.

    Fallback gracioso em QUALQUER falha (sem particao, schema antigo, shapely ausente, geometria
    corrompida) -> `{"bairros": [], ...}`; a pagina cai no aviso e o relatorio sai inteiro.
    """
    vazio: dict[str, Any] = {
        "bairros": [], "contorno": [], "n_bairros": 0, "n_setores": 0, "sem_localidade": 0,
        "cobertura": 0.0,
    }
    if censo_geo_dir is None or not uf or not cod_municipio:
        return vazio
    try:
        from shapely import wkb as shapely_wkb
        from shapely.ops import unary_union
    except Exception:
        return vazio

    medidas = [
        "geometry_wkb",
        "pop_total_setor_2022",
        "area_setor_km2_ibge",
        "renda_per_capita_setor_2022_calibrada",
        "score_setor_2022_calibrado",
        # bbox: centroide do setor -> hexagono res-7 (ponte para repartir metrica de mercado).
        "bbox_minx",
        "bbox_miny",
        "bbox_maxx",
        "bbox_maxy",
    ]
    # Schema antigo (sem a cascata): so `nome_bairro` ja permite desenhar.
    tentativas = [
        ["nome_bairro", "nome_subdistrito", "nome_distrito", "nome_municipio", *medidas],
        ["nome_bairro", *medidas],
    ]
    # DEC-076: a chave do artefato do CNEFE, so' quando ele existe para a UF. Particao SEM
    # `cod_setor` cai nas leituras de antes (bairro do IBGE), em vez de sumir.
    if bairro_cnefe_disponivel(censo_geo_dir, uf, staging_dir=staging_dir):
        tentativas = [[*cols, "cod_setor"] for cols in tentativas] + tentativas
    setores = _ler_setores_em_tentativas(censo_geo_dir, str(uf), str(cod_municipio), tentativas)
    if setores is None or setores.empty or "geometry_wkb" not in setores.columns:
        return vazio
    # DEC-076: o bairro do CNEFE substitui o do IBGE onde existe; o limite desenhado passa a ser
    # o do bairro do CNEFE (dissolvido pelos setores), o mesmo que nomeia a Pagina 6.
    setores_cnefe = aplicar_bairro_cnefe(
        setores, censo_geo_dir=censo_geo_dir, uf=uf, staging_dir=staging_dir
    )
    usou_cnefe = setores_cnefe is not setores
    setores = setores_cnefe

    nome_muni = ""
    if "nome_municipio" in setores.columns:
        nomes = setores["nome_municipio"].dropna()
        if not nomes.empty:
            nome_muni = str(nomes.iloc[0]).strip()
    rotulo_sobra = f"{nome_muni} (demais setores)" if nome_muni else "Demais setores"

    # Ponte hexagono -> bairro (BLK-RELMUN-10). O setor e' a unidade mais fina que temos e cai
    # inteiro dentro de UM hexagono (pelo centroide) e de UM bairro, entao ele serve de moeda de
    # troca: a populacao do setor diz que fracao de cada hexagono pertence a cada bairro.
    import h3 as _h3

    pop_por_hex: dict[str, float] = {}
    pop_por_bairro_hex: dict[str, dict[str, float]] = {}

    # Agrupa geometria + medidas por localidade numa passada.
    grupos: dict[str, dict[str, Any]] = {}
    sem_localidade = 0
    for _, row in setores.iterrows():
        bruto = row.get("geometry_wkb")
        if bruto is None:
            continue
        try:
            geom = shapely_wkb.loads(bytes(bruto))
        except Exception:
            continue
        if geom is None or geom.is_empty:
            continue
        nome = _localidade_do_setor(row)
        if not nome:
            sem_localidade += 1
            nome = rotulo_sobra
        pop = _safe_float(row.get("pop_total_setor_2022"))
        pop = 0.0 if math.isnan(pop) or pop < 0 else pop
        area = _safe_float(row.get("area_setor_km2_ibge"))
        area = 0.0 if math.isnan(area) or area < 0 else area
        renda = _safe_float(row.get("renda_per_capita_setor_2022_calibrada"))
        score = _safe_float(row.get("score_setor_2022_calibrado"))

        alvo = grupos.setdefault(
            nome,
            {
                "geoms": [], "pop": 0.0, "area": 0.0,
                "renda_num": 0.0, "renda_peso": 0.0,
                "score_num": 0.0, "score_peso": 0.0,
            },
        )
        alvo["geoms"].append(geom)
        alvo["pop"] += pop
        alvo["area"] += area
        if not math.isnan(renda) and pop > 0:
            alvo["renda_num"] += renda * pop
            alvo["renda_peso"] += pop
        # Score do bairro = media dos setores PONDERADA POR POPULACAO, nao media simples: um
        # setor de 12 moradores nao pode pesar o mesmo que um de 3.000 na cor do bairro.
        if not math.isnan(score) and pop > 0:
            alvo["score_num"] += score * pop
            alvo["score_peso"] += pop

        # Peso deste setor no par (hexagono, bairro), para repartir metrica de mercado depois.
        if pop > 0:
            minx_h = _safe_float(row.get("bbox_minx"))
            miny_h = _safe_float(row.get("bbox_miny"))
            maxx_h = _safe_float(row.get("bbox_maxx"))
            maxy_h = _safe_float(row.get("bbox_maxy"))
            if not any(math.isnan(v) for v in (minx_h, miny_h, maxx_h, maxy_h)):
                try:
                    hid = str(
                        _h3.latlng_to_cell(
                            float((miny_h + maxy_h) / 2.0), float((minx_h + maxx_h) / 2.0), H3_RES
                        )
                    )
                except Exception:
                    hid = ""
                if hid:
                    pop_por_hex[hid] = pop_por_hex.get(hid, 0.0) + pop
                    balde = pop_por_bairro_hex.setdefault(nome, {})
                    balde[hid] = balde.get(hid, 0.0) + pop

    bairros: list[dict[str, Any]] = []
    dissolvidos: list[Any] = []
    for nome, dados in grupos.items():
        try:
            unido = unary_union(dados["geoms"])
            if _BAIRRO_SIMPLIFY_GRAUS > 0:
                unido = unido.simplify(_BAIRRO_SIMPLIFY_GRAUS, preserve_topology=True)
        except Exception:
            continue
        dissolvidos.append(unido)
        partes = _partes_desenhaveis(unido)
        if not partes:
            continue
        # So o anel EXTERNO de cada parte: o PIL desenha poligono sem furo, e ilha interna de
        # bairro e rara o bastante para nao justificar composicao por mascara aqui.
        aneis = [
            [_lonlat_to_mercator(float(lon), float(lat)) for lon, lat in p.exterior.coords]
            for p in partes
        ]
        try:
            ponto = partes[0].representative_point()
            rotulo_xy = _lonlat_to_mercator(float(ponto.x), float(ponto.y))
        except Exception:
            continue
        peso = dados["renda_peso"]
        peso_score = dados["score_peso"]
        area = dados["area"]
        bairros.append(
            {
                "nome": nome,
                "aneis": aneis,
                "rotulo_xy": rotulo_xy,
                "pop": dados["pop"],
                "area_km2": area,
                "densidade": (dados["pop"] / area) if area > 0 else float("nan"),
                "renda_pc": (dados["renda_num"] / peso) if peso > 0 else float("nan"),
                "score": (dados["score_num"] / peso_score) if peso_score > 0 else float("nan"),
                # `hex_id -> fracao do hexagono que pertence a este bairro` (por populacao).
                # As fracoes de um mesmo hexagono somam 1 entre os bairros que o dividem, entao
                # repartir uma metrica EXTENSIVA (alunos) por elas preserva o total do municipio.
                "pesos_hex": {
                    hid: (p / pop_por_hex[hid])
                    for hid, p in (pop_por_bairro_hex.get(nome) or {}).items()
                    if pop_por_hex.get(hid, 0.0) > 0
                },
                "sobra": nome == rotulo_sobra,
            }
        )

    # Divisa do MUNICIPIO = uniao dos proprios setores desenhados (nao a malha IBGE): assim o
    # contorno preto fecha exatamente sobre os bairros vermelhos, sem fresta de reprojecao.
    contorno: list[list[tuple[float, float]]] = []
    try:
        borda = unary_union(dissolvidos)
        contorno = [
            [_lonlat_to_mercator(float(lon), float(lat)) for lon, lat in p.exterior.coords]
            for p in _partes_desenhaveis(borda)
        ]
    except Exception:
        contorno = []

    bairros.sort(key=lambda b: (-float(b["pop"]), str(b["nome"])))
    n_setores = int(len(setores))
    return {
        "bairros": bairros,
        "contorno": contorno,
        # A sobra "(demais setores)" e area, nao bairro: nao entra na contagem exibida.
        "n_bairros": sum(1 for b in bairros if not b["sobra"]),
        "n_setores": n_setores,
        "sem_localidade": sem_localidade,
        # Fracao de setores COM bairro/distrito: e o que diz se a contagem acima representa o
        # municipio ou so um pedaco dele. Quem exibe tem de olhar isto antes do numero.
        "cobertura": ((n_setores - sem_localidade) / n_setores) if n_setores else 0.0,
        # DEC-076: a chave so' entra quando o CNEFE nomeou algum setor (sem o artefato, o dict
        # e' o de antes). E' o que a Pagina 6 le para citar a fonte certa.
        **({"fonte_bairro": FONTE_CNEFE} if usou_cnefe else {}),
    }


def aplicar_metricas_hex_nos_bairros(
    bairros_geo: dict[str, Any],
    df_muni: pd.DataFrame,
    *,
    hex_zona_geo: dict[str, int] | None = None,
    renda_domiciliar_por_hex: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Traz as metricas de MERCADO do hexagono para o bairro (BLK-RELMUN-10). MUTA `bairros_geo`.

    Isto e' REPARTICAO, nao agregacao, e a diferenca importa: o hexagono res-7 (5,16 km2) e' MAIOR
    que 86% dos bairros de Novo Hamburgo, entao o valor do bairro e' ESTIMADO a partir do valor do
    hexagono que o contem -- ao contrario do score censitario, que sobe do setor e e' exato. Cada
    pagina que usa isto declara o metodo.

    Regra por tipo de grandeza, que nao pode ser a mesma para todas:

    - EXTENSIVA (`oferta_efetiva_disponivel`, em alunos): RATEADA pelos pesos populacionais
      (`pesos_hex`). Como as fracoes de um hexagono somam 1, a soma do municipio se preserva.
    - INTENSIVA (`score_oportunidade_residual`, um score 0-100): MEDIA PONDERADA pelos mesmos
      pesos. Ratear um score seria erro de dimensao -- dois bairros num hexagono de score 80 nao
      ficam com 40 cada.
    - CATEGORICA (zona de dominio, aprovado/reprovado): vence a categoria com MAIOR peso
      populacional no bairro.
    - `renda_domiciliar_por_hex` (2026-10-20, legenda do Score): a renda domiciliar do hexagono
      (a do card do mapa) vira `renda_dom` do bairro, intensiva -> media pelos mesmos pesos.

    Fallback gracioso: sem `pesos_hex`/sem colunas -> campos ausentes; o render cai no cinza de
    "sem dado". READ-ONLY sobre o M1.
    """
    bairros = list(bairros_geo.get("bairros") or [])
    if not bairros or df_muni is None or df_muni.empty or "hex_id" not in df_muni.columns:
        return bairros_geo

    destaque = _hex_destacado_mask(df_muni).to_numpy()
    hex_ids = [str(h) for h in df_muni["hex_id"].tolist()]
    oferta = _coluna_numerica(df_muni, "oferta_efetiva_disponivel").to_numpy()
    residual = _coluna_numerica(df_muni, "score_oportunidade_residual").to_numpy()

    por_hex: dict[str, dict[str, Any]] = {}
    for i, hid in enumerate(hex_ids):
        por_hex[hid] = {
            "oferta": float(oferta[i]) if i < len(oferta) else float("nan"),
            "residual": float(residual[i]) if i < len(residual) else float("nan"),
            "destacado": bool(destaque[i]) if i < len(destaque) else False,
        }
    zonas = dict(hex_zona_geo or {})
    dom = {str(k): _safe_float(v) for k, v in (renda_domiciliar_por_hex or {}).items()}

    for bairro in bairros:
        pesos: dict[str, float] = dict(bairro.get("pesos_hex") or {})
        oferta_total = 0.0
        res_num = res_peso = 0.0
        dom_num = dom_peso = 0.0
        peso_destacado = peso_total = 0.0
        peso_por_zona: dict[int, float] = {}
        for hid, frac in pesos.items():
            dados_hex = por_hex.get(hid)
            if dados_hex is None or frac <= 0:
                continue
            peso_total += frac
            if not math.isnan(dados_hex["oferta"]):
                oferta_total += dados_hex["oferta"] * frac
            if not math.isnan(dados_hex["residual"]):
                res_num += dados_hex["residual"] * frac
                res_peso += frac
            if dados_hex["destacado"]:
                peso_destacado += frac
            renda_hex = dom.get(hid, float("nan"))
            if not math.isnan(renda_hex):
                dom_num += renda_hex * frac
                dom_peso += frac
            zona = zonas.get(hid)
            if zona is not None:
                peso_por_zona[int(zona)] = peso_por_zona.get(int(zona), 0.0) + frac

        bairro["oferta_alunos"] = oferta_total if peso_total > 0 else float("nan")
        bairro["score_residual"] = (res_num / res_peso) if res_peso > 0 else float("nan")
        bairro["renda_dom"] = (dom_num / dom_peso) if dom_peso > 0 else float("nan")
        # "Aprovado" quando a MAIORIA da populacao do bairro cai em hexagono aprovado -- um
        # bairro que so encosta na borda de um hexagono aprovado nao herda o carimbo.
        bairro["destacado"] = bool(peso_total > 0 and peso_destacado > peso_total / 2.0)
        bairro["zona"] = max(peso_por_zona, key=lambda z: peso_por_zona[z]) if peso_por_zona else None

    bairros_geo["metricas_mercado"] = True
    return bairros_geo


def _bairros_por_zona(
    hex_zona_geo: dict[str, int],
    bairros_por_hex: dict[str, str] | None,
) -> list[dict[str, Any]]:
    """Agrupa bairros distintos por zona (0/1/2), ordenados por frequencia desc. PURO/offline.

    `hex_zona_geo`: mapa hex_id -> 0|1|2 (mesma zonificacao da Pagina 5). `bairros_por_hex`:
    hex_id -> bairro dominante. Retorna lista alinhada as zonas presentes (1..3), com a lista
    de bairros e o total. Fallback gracioso: sem fonte de bairro -> listas vazias por zona.
    """
    if not hex_zona_geo:
        return []
    freq: dict[int, dict[str, int]] = {0: {}, 1: {}, 2: {}}
    if bairros_por_hex:
        for hid, zona in hex_zona_geo.items():
            if zona not in freq:
                continue
            bairro = bairros_por_hex.get(str(hid))
            if not bairro:
                continue
            freq[zona][bairro] = freq[zona].get(bairro, 0) + 1

    zonas: list[dict[str, Any]] = []
    zonas_presentes = sorted({z for z in hex_zona_geo.values() if z in (0, 1, 2)})
    for zona in zonas_presentes:
        contagem = freq[zona]
        # Ordena por frequencia desc, desempate estavel por nome.
        ordenados = sorted(contagem, key=lambda n: (-contagem[n], n))
        zonas.append(
            {
                "zona_n": zona + 1,
                "rotulo": _ZONA_GEO_ROTULOS[zona],
                "bairros": ordenados,
                "n_bairros": len(ordenados),
            }
        )
    return zonas


def _coluna_numerica(df: pd.DataFrame, nome: str) -> pd.Series:
    """Serie numerica da coluna, ou NaN ALINHADO ao indice quando a coluna nao existe.

    `pd.to_numeric(df.get("ausente"), errors="coerce")` devolve um ESCALAR `nan`, nao uma Series
    -- e qualquer `.dropna()`/`.nunique()` a jusante estoura `AttributeError`. Este helper existe
    para o caminho de coluna ausente ser tao valido quanto o de coluna presente.
    """
    if nome not in df.columns:
        return pd.Series(float("nan"), index=df.index, dtype="float64")
    return pd.to_numeric(df[nome], errors="coerce")


def _renda(valor: Any, decimais: int = 0) -> str:
    """`R$ 5.210` (BR) / `USD 5.210` (AR) quando ha numero; so o "n/d" quando nao ha.

    O rotulo e' `moeda.simbolo_renda()` do perfil, nunca `moeda.simbolo` cru: a renda AR chega
    em USD enquanto o simbolo do pais e' o "$" do peso (BLK-INTL-10).

    Colar o simbolo em cima do texto de ausencia produzia "R$ Nao disponivel", que lê como se o
    valor fosse a string -- visto na tabela de Sinop/MT.
    """
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return TEXTO_SEM_DADO
    return f"{resolver_perfil().moeda.simbolo_renda()} " + _format_number(valor, decimais)


def _instituto_censo() -> str:
    """Sigla do instituto do censo, lida do perfil: "Censo 2022 (IBGE)" -> "IBGE",
    "Censo 2022 (INDEC)" -> "INDEC". Sem parenteses, o nome inteiro (BLK-INTL-10)."""
    nome = resolver_perfil().fontes.censo.nome
    achado = re.search(r"\(([^)]+)\)", nome)
    return achado.group(1).strip() if achado else nome


def _renda_pc_canonica(df_muni: pd.DataFrame, coluna: str) -> pd.Series:
    """Renda domiciliar per capita canonica de cada hex, lida SO de `coluna` (E1).

    A conta e do modulo da renda (`renda.hex.renda_per_capita_por_linha`, a mesma cadeia do
    card): a coluna de origem e convertida (k desfeito na calibrada, uplift desfeito na SIDRA)
    e recebe uplift, moradores e o fator per capita do municipio. Coluna ausente -> tudo NaN.
    """
    if df_muni is None or df_muni.empty or coluna not in df_muni.columns:
        return pd.Series(np.nan, index=getattr(df_muni, "index", None), dtype="float64")
    return _renda_hex.renda_per_capita_por_linha(df_muni, precedencia=(coluna,))


def _tabela_hexes(
    df_muni: pd.DataFrame,
    bairros_por_hex: dict[str, str] | None = None,
    *,
    renda_domiciliar_por_hex: dict[str, float] | None = None,
    limite: int = _TABELA_HEXES_LIMITE,
) -> dict[str, Any]:
    """Ranking das regioes (hexes res-7) do municipio para a tabela de comparacao.

    Ordena por `oferta_efetiva_disponivel` (Residual Fitness) desc -- a MESMA metrica que decide
    o destaque no mapa (D1) e que a pagina de Residual reporta; ranquear por outra coisa faria a
    tabela contradizer o mapa ao lado. Empate desfeito pelo `hex_id` (estavel entre execucoes).

    O `bairro dominante` de cada hex vem de `_carregar_bairros_por_hex` e serve de PONTE: e o que
    deixa o leitor amarrar "hexágono 87a90e88..." a um nome que ele reconhece.

    Devolve `{"linhas": [...], "n_total": N, "n_exibidas": M}` -- `n_total` para a pagina poder
    declarar quantas regioes ficaram de fora do corte, em vez de truncar em silencio.
    READ-ONLY: so le colunas, nao recalcula nada do M1.
    """
    if df_muni is None or df_muni.empty or "hex_id" not in df_muni.columns:
        return {"linhas": [], "n_total": 0, "n_exibidas": 0}

    destaque = _hex_destacado_mask(df_muni)

    # Renda: preferir a CENSITARIA calibrada do setor. `renda_per_capita` e' insumo do M1 e em
    # boa parte dos municipios vem replicada do valor MUNICIPAL -- em Novo Hamburgo/RS ela tem 1
    # valor unico para os 48 hexes, enquanto a censitaria tem 47. Numa tabela cuja unica funcao
    # e' COMPARAR regioes, uma coluna constante nao e so inutil: sugere que os bairros tem a
    # mesma renda. Fallback para `renda_per_capita` onde a censitaria nao existir.
    # RENDA DOMICILIAR e' a leitura pedida (Juan, 2026-08-19): e' o numero com que se conversa
    # sobre praca -- "domicilio de R$ 4.500" diz algo, "per capita de R$ 1.500" nao diz. Vem de
    # `motor_expansao.renda.hex.renda_domiciliar_por_hex` (desde 2026-10-16 a MESMA formula do card do REP, sobre
    # a coluna do hexagono). Cai para per capita so quando o mapa chega vazio.
    # Os dois fallbacks (per capita, sem o mapa domiciliar) passam pelo MESMO modulo do card
    # desde a E1 (`renda_per_capita_por_linha`): antes exibiam a coluna CRUA -- a calibrada na
    # escala do score (com k, sem uplift nem fator) ou a SIDRA municipal sem fator.
    mapa_dom = dict(renda_domiciliar_por_hex or {})
    if mapa_dom:
        renda = df_muni["hex_id"].astype(str).map(mapa_dom).astype("float64")
        fonte_renda = "domiciliar"
    else:
        renda = _renda_pc_canonica(df_muni, "renda_per_capita_setor_2022_calibrada")
        fonte_renda = "censo"
    if renda.dropna().empty:
        renda = _renda_pc_canonica(df_muni, "renda_per_capita")
        fonte_renda = "m1"

    pop = _coluna_numerica(df_muni, "populacao_corte_hex")
    if pop.dropna().empty:
        pop = _coluna_numerica(df_muni, "pop_total_setor_2022")

    dados = pd.DataFrame(
        {
            "hex_id": df_muni["hex_id"].astype(str),
            "pop": pop,
            "renda": renda,
            "densidade": _coluna_numerica(df_muni, "densidade_pop_setor_hab_km2"),
            "score": _coluna_numerica(df_muni, "score_setor_2022_calibrado"),
            "residual": _coluna_numerica(df_muni, "oferta_efetiva_disponivel"),
            "destacado": destaque.to_numpy(),
        }
    )
    dados = dados.sort_values(
        ["residual", "hex_id"], ascending=[False, True], na_position="last"
    )

    mapa_bairro = bairros_por_hex or {}

    def _num(valor: Any) -> float | None:
        """NaN vira None: `nan != nan` faria duas chamadas identicas de `agregar_municipio`
        compararem como diferentes (invariante travado em teste), e NaN nao e' JSON valido --
        este dict trafega pela API. `_format_number(None)` ja imprime "n/d".
        `pd.isna` e nao so `isnan`: o enriquecido e' `Float32` nulavel e o buraco chega como
        `pd.NA`, que `float()` recusa.
        """
        if pd.isna(valor):
            return None
        v = float(valor)
        return None if math.isnan(v) else v

    linhas: list[dict[str, Any]] = []
    for _, row in dados.head(max(0, int(limite))).iterrows():
        hid = str(row["hex_id"])
        linhas.append(
            {
                "hex_id": hid,
                "bairro": mapa_bairro.get(hid) or TEXTO_SEM_DADO,
                "pop": _num(row["pop"]),
                "renda": _num(row["renda"]),
                "densidade": _num(row["densidade"]),
                "score": _num(row["score"]),
                "residual": _num(row["residual"]),
                "destacado": bool(row["destacado"]),
            }
        )
    return {
        "linhas": linhas,
        "n_total": int(len(dados)),
        "n_exibidas": len(linhas),
        "fonte_renda": fonte_renda,
        # Renda constante entre as regioes exibidas: a pagina precisa DIZER isso, senao a coluna
        # repetida passa por erro de calculo (ou pior, por bairros de renda identica).
        "renda_constante": bool(dados["renda"].dropna().nunique() <= 1),
    }


def _zonas_geometricas(df_muni: pd.DataFrame) -> dict[str, Any]:
    """FU1 (estende D2 SO para o display do mapa, READ-ONLY M1): classifica os hexes
    RELEVANTES do municipio em 3 zonas geometricas por DISTANCIA ao centroide.

    Esta zonificacao e CAMADA DE DISPLAY: NAO altera `dominio_df`, `flag_sam`, score nem
    qualquer artefato do M1 — apenas colore o mapa da Pagina 5 e alimenta o painel/Pagina 6.

    Hexes relevantes = SOMENTE os hexes DESTACADOS/aprovados (`_hex_destacado_mask`:
    oferta_efetiva_disponivel>=2000; termo de SAM removido em BLK-RELMUN-03). Decisao do produto
    (Vinicius, 2026-06-24): so quem foi APROVADO recebe estrategia de expansao — sem fallback
    para todos os hexes do municipio (antes, com <3 aprovados, a estrategia se espalhava por
    todo o municipio). Particiona por tercis de distancia ao centroide: terco central = zona 1
    (Ancora), intermediario = zona 2 (Flancos), externo = zona 3 (Cerco); com 1 aprovado ->
    1 zona (Ancora). Retorna `{"hex_zona": {hex_id: 0|1|2}, "zonas": [ {...}, ... ]}`.
    Fallback gracioso: sem hexes aprovados/sem `hex_id` -> `{"hex_zona": {}, "zonas": []}`.
    """
    vazio: dict[str, Any] = {"hex_zona": {}, "zonas": []}
    if df_muni.empty or "hex_id" not in df_muni.columns:
        return vazio

    destaque = _hex_destacado_mask(df_muni)
    rel = df_muni.loc[destaque]
    rel = rel[rel["hex_id"].notna()]
    if rel.empty:
        return vazio

    import h3

    centros: list[tuple[str, float, float]] = []
    vistos: set[str] = set()
    for hid in rel["hex_id"].astype(str):
        if hid in vistos:
            continue
        try:
            la, lo = h3.cell_to_latlng(hid)
        except Exception:
            continue
        vistos.add(hid)
        centros.append((hid, float(la), float(lo)))
    if not centros:
        return vazio

    lat_c = sum(c[1] for c in centros) / len(centros)
    lon_c = sum(c[2] for c in centros) / len(centros)
    dists = [(hid, math.hypot(la - lat_c, lo - lon_c)) for hid, la, lo in centros]
    dists.sort(key=lambda t: t[1])

    n = len(dists)
    # Tercis por POSICAO (distribuicao equilibrada mesmo com poucos hexes).
    hex_zona: dict[str, int] = {}
    counts = [0, 0, 0]
    for idx, (hid, _d) in enumerate(dists):
        zona = min(2, (idx * 3) // n)
        hex_zona[hid] = zona
        counts[zona] += 1

    zonas: list[dict[str, Any]] = []
    for z in range(3):
        if counts[z] == 0:
            continue
        zonas.append(
            {
                "zona_n": z + 1,
                "rotulo": _ZONA_GEO_ROTULOS[z],
                "descricao": _ZONA_GEO_DESC[z],
                "n_hex": counts[z],
                "cor_rgb": _ZONA_CORES_PDF[z],
            }
        )
    return {"hex_zona": hex_zona, "zonas": zonas}


# ---------------------------------------------------------------------------
# Recorte territorial dos pins (BLK-RELMUN-05)
# ---------------------------------------------------------------------------
# Os pins de concorrentes/Ultra vazavam para fora do municipio por DOIS caminhos distintos:
#
#   (a) o MAPA desenhava todo pin dentro da bbox da imagem -- que cobre o municipio MAIS o
#       padding do enquadramento --, sem filtro territorial nenhum. Por isso o relatorio de
#       Sao Bernardo do Campo saia com unidades de Santo Andre, Diadema e Sao Paulo;
#   (b) a CONTAGEM filtrava pelo conjunto de hexes H3 res-7 do municipio. Um hex res-7 tem
#       ~5 km2 e cruza divisa, entao a faixa de fronteira entrava na conta.
#
# `filtrar_pins_do_municipio` centraliza o recorte e passa a ser aplicado ANTES de contar E
# ANTES de desenhar. Dois niveis de precisao, com degradacao graciosa:
#
#   - com `poligono` (malha municipal IBGE, `data/ibge/municipios_<UF>.geojson`): teste
#     ponto-em-poligono -- a divisa e a real, resolve (a) e (b);
#   - sem `poligono` (app que nao monta `data/ibge`): cai no conjunto de hexes res-7, que
#     resolve (a) e mantem o comportamento historico de (b).
#
# READ-ONLY sobre o M1: so filtra linhas de um parquet ja pronto, nao recalcula metrica alguma.


def _hexes_do_municipio(df_muni: pd.DataFrame) -> set[str]:
    """Conjunto de `hex_id` (res-7) do municipio; vazio quando a coluna nao existe."""
    if "hex_id" not in df_muni.columns:
        return set()
    return {str(h) for h in df_muni["hex_id"].dropna().astype(str)}


def _hexes_res7_do_frame(frame: pd.DataFrame) -> pd.Series | None:
    """`hex_id_res7` do frame de pins; deriva de lat/lng via h3 quando a coluna nao existe."""
    if "hex_id_res7" in frame.columns:
        return frame["hex_id_res7"].astype(str)
    if not {"lat", "lng"}.issubset(frame.columns):
        return None
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


def _mask_dentro_do_poligono(frame: pd.DataFrame, poligono: Any) -> pd.Series | None:
    """Mascara ponto-em-poligono para `frame` (colunas `lat`/`lng`). `None` se indisponivel.

    Pre-filtra pela bbox do poligono (comparacao numerica vetorizada, barata) e so entao roda
    o teste exato de geometria nos sobreviventes -- a base de concorrentes e NACIONAL e o
    municipio e uma fracao minuscula dela, entao a bbox derruba quase tudo antes do shapely.
    Usa `covers` (nao `contains`) para nao descartar unidade exatamente sobre a divisa.
    """
    try:
        from shapely.geometry import Point
    except Exception:  # shapely ausente -> chamador cai no filtro por hex
        return None
    try:
        minx, miny, maxx, maxy = poligono.bounds
    except Exception:
        return None
    lat = pd.to_numeric(frame["lat"], errors="coerce")
    lng = pd.to_numeric(frame["lng"], errors="coerce")
    candidatos = (
        lat.notna() & lng.notna() & lng.between(minx, maxx) & lat.between(miny, maxy)
    )
    mask = pd.Series(False, index=frame.index)
    for idx in frame.index[candidatos]:
        try:
            if poligono.covers(Point(float(lng.at[idx]), float(lat.at[idx]))):
                mask.at[idx] = True
        except Exception:  # geometria estranha numa linha nao pode derrubar o relatorio
            continue
    return mask


def filtrar_pins_do_municipio(
    frame: pd.DataFrame | None,
    *,
    hexes_muni: set[str],
    poligono: Any | None = None,
) -> pd.DataFrame | None:
    """Recorta um frame de pins (concorrentes/Ultra) ao territorio do municipio.

    `poligono` = geometria da malha IBGE (via `carregar_poligono_municipio`); quando dado,
    manda. Sem ele, filtra pelo conjunto `hexes_muni` de hexes res-7. Sem NENHUMA referencia
    territorial (`hexes_muni` vazio) devolve frame VAZIO -- e o que a contagem ja fazia
    (`return 0, 0, {}`), e o contrario seria desenhar a base nacional inteira no mapa.
    """
    if frame is None or frame.empty:
        return frame
    if poligono is not None and {"lat", "lng"}.issubset(frame.columns):
        mask = _mask_dentro_do_poligono(frame, poligono)
        if mask is not None:
            return frame.loc[mask]
    if not hexes_muni:
        return frame.iloc[0:0]
    hexes = _hexes_res7_do_frame(frame)
    if hexes is None:  # sem hex e sem lat/lng: nada a filtrar por
        return frame.iloc[0:0]
    return frame.loc[hexes.isin(hexes_muni)]


@lru_cache(maxsize=8)
def _indice_malha_uf(ibge_dir_str: str, uf: str) -> dict[str, Any]:
    """`cod_municipio` -> geometria, lido de `municipios_<UF>.geojson` (cacheado por processo).

    Mesma fonte e mesmas chaves de propriedade que `api.service._carregar_malha`, mas indexado
    por codigo em vez de espacialmente: aqui ja sabemos QUAL municipio queremos.
    """
    import json

    from shapely.geometry import shape

    path = Path(ibge_dir_str) / f"municipios_{uf}.geojson"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, Any] = {}
    for feat in data.get("features", []) or []:
        props = feat.get("properties") or {}
        cod = str(
            props.get("codarea") or props.get("CD_MUN") or props.get("cod_municipio") or ""
        ).strip()
        geom = feat.get("geometry")
        if not cod or not geom:
            continue
        try:
            out[cod] = shape(geom)
        except Exception:  # geometria malformada -> municipio fica sem poligono
            continue
    return out


def carregar_poligono_municipio(
    ibge_dir: Path | str | None,
    uf: str | None,
    cod_municipio: str | None,
) -> Any | None:
    """Geometria do municipio na malha IBGE, ou `None` (fallback gracioso p/ filtro por hex).

    `None` e o caminho esperado em app que nao monta `data/ibge` (o Streamlit, hoje) ou quando
    a linha do parquet nao tem `cod_municipio`. Nunca levanta: o relatorio sai de qualquer jeito.
    """
    if not ibge_dir or not uf or not cod_municipio:
        return None
    cod = str(cod_municipio).strip()
    if not cod:
        return None
    try:
        return _indice_malha_uf(str(ibge_dir), str(uf).strip().upper()).get(cod)
    except Exception:
        return None


def _pins_no_municipio(
    df_muni: pd.DataFrame,
    competitors_df: pd.DataFrame | None,
    ultra_df: pd.DataFrame | None,
    *,
    poligono: Any | None = None,
) -> tuple[int, int, dict[str, int]]:
    """D6: conta pins Ultra/concorrentes DENTRO do municipio. Anti-PII: usa so `rede`.

    Recorte por `filtrar_pins_do_municipio` (poligono IBGE quando disponivel; senao hexes
    res-7). Retorna (n_ultra, n_concorrentes, {rede: contagem}).
    """
    hexes_muni = _hexes_do_municipio(df_muni)
    if not hexes_muni and poligono is None:
        return 0, 0, {}

    ultra_muni = filtrar_pins_do_municipio(
        ultra_df, hexes_muni=hexes_muni, poligono=poligono
    )
    conc_muni = filtrar_pins_do_municipio(
        competitors_df, hexes_muni=hexes_muni, poligono=poligono
    )

    n_ultra = 0 if ultra_muni is None else int(len(ultra_muni))

    n_conc = 0
    por_rede: dict[str, int] = {}
    if conc_muni is not None:
        n_conc = int(len(conc_muni))
        if "rede" in conc_muni.columns:
            # Independente (rede vazia, DEC-046) conta no balde do agregador; `astype(str)`
            # direto abria um balde "<NA>" com a placa cinza "C" no slide 8.
            #
            # `[DEC-066]` O balde sai do APP que revelou a academia, e nao mais de uma constante:
            # sem `fonte` (artefato anterior a esta DEC) cai no WellHub e o agrupamento fica
            # IDENTICO ao de antes.
            fontes = (
                conc_muni["fonte"]
                if "fonte" in conc_muni.columns
                else pd.Series([None] * len(conc_muni), index=conc_muni.index)
            )
            # `[DEC-066 / fatia 2]` O balde tambem se desdobra: academia nos dois apps conta num
            # balde PROPRIO, senao ela seria somada sob o nome de um app so'.
            declaradas = (
                conc_muni["fontes_da_academia"]
                if "fontes_da_academia" in conc_muni.columns
                else pd.Series([None] * len(conc_muni), index=conc_muni.index)
            )
            redes = pd.Series(
                [
                    _chave_rede(r) or chave_agregador_da_fonte(f, d)
                    for r, f, d in zip(
                        conc_muni["rede"], fontes, declaradas, strict=False
                    )
                ],
                index=conc_muni.index,
                dtype="object",
            )
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
    bairros_por_hex: dict[str, str] | None = None,
    bairros_geo: dict[str, Any] | None = None,
    renda_domiciliar_por_hex: dict[str, float] | None = None,
    df_pre_filtrado: pd.DataFrame | None = None,
    poligono_municipio: Any | None = None,
) -> dict[str, Any]:
    """Agrega o dicionario canonico de metricas do municipio. READ-ONLY (so le colunas).

    Filtra `df` por `nome_municipio` (fallback `cidade`) e computa as metricas das 9 paginas
    conforme as decisoes do gate (D1/D4/D5/D6). NUNCA recalcula score ou artefatos do M1.

    `bairros_por_hex` (BLK-RELMUN-02, A2): mapa OPCIONAL `hex_id -> bairro dominante` (fonte
    IBGE `NM_BAIRRO` da particao geo, via `_carregar_bairros_por_hex`). `None` (default) =
    comportamento IDENTICO ao anterior (Pagina 6 simplificada por zona geometrica). Quando dado,
    popula `result["bairros_por_zona"]` com os bairros REAIS agrupados pelas 3 zonas geometricas.

    `bairros_geo` (BLK-RELMUN-06): saida de `carregar_bairros_geo` (limite territorial de cada
    bairro em EPSG:3857). OPCIONAL: `None` (default) mantem o comportamento anterior e a pagina
    "Bairros Oficiais" sai com o aviso de bairro nao mapeado. So trafega ate o render; nenhuma
    metrica do relatorio deriva dela.

    `df_pre_filtrado` (Fix 2 BLK-PERF-01a): DataFrame ja filtrado para o municipio (evita
    full-scan de 1,5 M hexes). Quando fornecido, substitui a filtragem interna por `_municipio_mask`.
    `df` continua obrigatorio na assinatura para compatibilidade, mas nao e usado para filtragem
    quando `df_pre_filtrado` esta presente.

    `poligono_municipio` (BLK-RELMUN-05): geometria da malha IBGE (via
    `carregar_poligono_municipio`) para recortar os pins pela divisa REAL. `None` (default)
    mantem o recorte por hexes res-7. Ver o bloco "Recorte territorial dos pins" acima.
    """
    if df_pre_filtrado is not None:
        df_muni = df_pre_filtrado.copy()
    else:
        mask = _municipio_mask(df, nome_municipio)
        df_muni = df.loc[mask].copy()

    uf_value = str(uf).strip().upper() if uf else ""
    if not uf_value and "uf" in df_muni.columns and not df_muni["uf"].dropna().empty:
        uf_value = str(df_muni["uf"].dropna().iloc[0]).strip().upper()

    n_hex_total = int(len(df_muni))

    destaque_mask = _hex_destacado_mask(df_muni)
    oferta = _coluna_numerica(df_muni, "oferta_efetiva_disponivel")
    oferta_destacados = oferta[destaque_mask].dropna()
    soma_oferta_amarelos = float(oferta_destacados.sum()) if not oferta_destacados.empty else 0.0
    n_hex_amarelos = int(destaque_mask.sum())
    espaco_para_academias = int(round(soma_oferta_amarelos / CAPACIDADE_UNIDADE)) if CAPACIDADE_UNIDADE else 0
    # Ate 5 maiores parcelas para a caixa "Como calculamos".
    parcelas = [float(v) for v in oferta_destacados.sort_values(ascending=False).head(5).tolist()]

    score_col = _coluna_numerica(df_muni, "score_setor_2022_calibrado").dropna()
    score_censo_medio = float(score_col.mean()) if not score_col.empty else float("nan")
    score_censo_max = float(score_col.max()) if not score_col.empty else float("nan")

    mercado_disponivel = float(oferta.dropna().sum()) if not oferta.dropna().empty else 0.0

    pop_serie = _coluna_numerica(df_muni, "pop_total_setor_2022")
    if pop_serie.dropna().empty:
        pop_serie = _coluna_numerica(df_muni, "pop_total")
    pop_total_municipio = float(pop_serie.dropna().sum()) if not pop_serie.dropna().empty else float("nan")

    # Painel "Renda per capita": a SIDRA municipal (`renda_per_capita`, o insumo do M1, o MESMO
    # valor em todo hex do municipio) convertida pela cadeia canonica do card (E1) -- uplift e
    # moradores municipais e o fator per capita. Ate a E1 saia crua, sem fator: ~F abaixo da
    # per capita do Relatorio Pontual por construcao. A coluna do M1 fica intocada.
    renda = _renda_pc_canonica(df_muni, "renda_per_capita")
    pesos = _coluna_numerica(df_muni, "pop_total_setor_2022")
    valid = renda.notna() & pesos.notna() & (pesos > 0)
    if valid.any():
        renda_per_capita_media = float((renda[valid] * pesos[valid]).sum() / pesos[valid].sum())
    elif renda.dropna().any():
        renda_per_capita_media = float(renda.dropna().mean())
    else:
        renda_per_capita_media = float("nan")

    penetr = _coluna_numerica(df_muni, "penetracao_fitness_mercado_estimada").dropna()
    penetracao_fitness_media = float(penetr.mean()) if not penetr.empty else float("nan")

    # FU1: penetracao MUNICIPAL significativa = consumo / (consumo + residual) * 100.
    # consumo_total = sum(oferta_consumida_mercado_estimada); residual_total = mercado_disponivel.
    consumo_serie = _coluna_numerica(df_muni, "oferta_consumida_mercado_estimada").dropna()
    consumo_total = float(consumo_serie.sum()) if not consumo_serie.empty else 0.0
    residual_total = mercado_disponivel
    denom = consumo_total + residual_total
    penetracao_fitness_pct = (100.0 * consumo_total / denom) if denom > 0 else float("nan")

    zonas = _zonas_do_municipio(dominio_df, nome_municipio)
    zonas_geo = _zonas_geometricas(df_muni)
    # A2: bairros REAIS por zona quando `bairros_por_hex` foi resolvido (particao geo IBGE).
    # Fallback gracioso: None/{} -> listas vazias (Pagina 6 cai nas zonas geometricas + tese).
    bairros_por_zona = _bairros_por_zona(zonas_geo.get("hex_zona", {}), bairros_por_hex)
    n_ultra, n_concorrentes, concorrentes_por_rede = _pins_no_municipio(
        df_muni, competitors_df, ultra_df, poligono=poligono_municipio
    )

    return {
        "nome_municipio": str(nome_municipio).strip(),
        "uf": uf_value,
        "n_hex_total": n_hex_total,
        "n_hex_municipio": n_hex_total,
        "n_aprovados": n_hex_amarelos,
        "n_reprovados": max(0, n_hex_total - n_hex_amarelos),
        "n_hex_amarelos": n_hex_amarelos,
        "soma_oferta_amarelos": soma_oferta_amarelos,
        "espaco_para_academias": espaco_para_academias,
        "academias_por_hex": academias_por_hex(df_muni),
        "parcelas_amarelos": parcelas,
        "score_censo_medio": score_censo_medio,
        "score_censo_max": score_censo_max,
        "mercado_disponivel_pessoas": mercado_disponivel,
        "residual_total_alunos": mercado_disponivel,
        "pop_total_municipio": pop_total_municipio,
        "renda_per_capita_media": renda_per_capita_media,
        "penetracao_fitness_media": penetracao_fitness_media,
        "penetracao_fitness_pct": penetracao_fitness_pct,
        "consumo_total_alunos": consumo_total,
        "n_zonas": len(zonas),
        "zonas": zonas,
        "zonas_geo": zonas_geo.get("zonas", []),
        "hex_zona_geo": zonas_geo.get("hex_zona", {}),
        "n_zonas_geo": len(zonas_geo.get("zonas", [])),
        # Mapa cru hex -> bairro dominante: os renderizadores rotulam o hexagono com ele
        # (BLK-RELMUN-08), para o leitor saber QUAL bairro cada regiao do mapa e'.
        "bairros_por_hex": dict(bairros_por_hex or {}),
        "bairros_por_zona": bairros_por_zona,
        "n_bairros_total": sum(int(z.get("n_bairros", 0)) for z in bairros_por_zona),
        "bairros_geo": bairros_geo or {},
        # A renda domiciliar por hexagono segue ate' o render: a legenda do Score a usa por bairro.
        "renda_domiciliar_por_hex": dict(renda_domiciliar_por_hex or {}),
        "tabela_hexes": _tabela_hexes(
            df_muni, bairros_por_hex, renda_domiciliar_por_hex=renda_domiciliar_por_hex
        ),
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
    # Mesma regra do `censo_map._font` (BLK-RELPON-06): fonte EMBUTIDA do Pillow, que escala.
    # `arial.ttf` so existe no Windows; na imagem de producao o fallback `load_default()` SEM
    # size desenhava todo texto de mapa num bitmap fixo de ~10 px (rotulo de 8 px saia grande).
    from typing import cast

    return cast(ImageFont.ImageFont, ImageFont.load_default(size=size))


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


# Extensao MINIMA do viewport de foco (em metros 3857). Evita super-ampliar quando o foco
# e um unico/poucos hexes (~1,2 km de aresta no res-7): garante ao menos ~6 km de lado.
# 6.000 -> 5.000 m e 0,16 -> 0,08 de margem em 2026-09-17: o pedido do Juan de "um leve zoom"
# nos mapas que continuam mostrando a cidade toda.
_FOCUS_MIN_SPAN_M = 5000.0
# Padding fracional aplicado ao bbox de foco (AJUSTE 1): margem de ~16% em cada eixo.
_FOCUS_PAD_FRAC = 0.08
# O Resumo fecha nos MESMOS hexagonos do Dominio (os escolhidos), com margem folgada: enquadrar
# todos os aprovados devolvia a cidade inteira, porque em Sao Paulo eles vao de norte a sul.
# Com 0,55 o quadro mostra a melhor area e o bastante em volta para situar (Juan, 2026-09-17).
_FOCUS_PAD_FRAC_RESUMO = 0.55
# A Visao Geral fecha nos aprovados com margem quase nula (Juan, 2026-10-20: "o zoom encaixar
# no maximo da margem possivel, mostrando ainda os aprovados, sem perder nenhum"). 2% so' para
# o contorno do aprovado da borda nao encostar na moldura.
_FOCUS_PAD_FRAC_COBERTURA = 0.02


def _bounds_bairros_aprovados(
    bairros_geo: dict[str, Any] | None, *, pad_frac: float = _FOCUS_PAD_FRAC_COBERTURA
) -> tuple[float, float, float, float] | None:
    """bbox EPSG:3857 dos contornos dos bairros aprovados (`destacado`), com margem minima.

    `None` sem bairro aprovado -- o chamador mantem o recorte que ja usava.
    """
    xs: list[float] = []
    ys: list[float] = []
    for bairro in (bairros_geo or {}).get("bairros") or []:
        if not bairro.get("destacado") or bairro.get("sobra"):
            continue
        for anel in bairro.get("aneis") or []:
            for x, y in anel:
                xs.append(float(x))
                ys.append(float(y))
    if not xs:
        return None
    return _com_margem(min(xs), min(ys), max(xs), max(ys), pad_frac=pad_frac)


def _focus_bounds_mercator(
    df_muni: pd.DataFrame,
    *,
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
    hexes_foco: set[str] | None = None,
    pad_frac: float = _FOCUS_PAD_FRAC,
) -> tuple[float, float, float, float] | None:
    """AJUSTE 1 (FU1): bbox de FOCO em EPSG:3857 das regioes RELEVANTES do municipio.

    Conjunto de foco = centroides dos hexes "relevantes" (DESTACADOS quando existirem; senao
    hexes com `score_setor_2022_calibrado` notna OU `oferta_efetiva_disponivel`>0 OU
    `pop_total_setor_2022`>0) UNIAO com as posicoes dos pins (Ultra + concorrentes) que caem
    no municipio. Resultado JA com padding e extensao MINIMA. Fallback: foco vazio -> None
    (o chamador cai no bbox de TODOS os hexes, comportamento anterior). READ-ONLY sobre o M1.
    """
    if df_muni.empty or "hex_id" not in df_muni.columns:
        return None

    if hexes_foco:
        # Zoom na MELHOR area (2026-09-17): o quadro fecha nos hexagonos escolhidos. Pins ficam
        # fora do calculo -- eles enquadravam a cidade inteira e desfaziam o zoom.
        rel = df_muni.loc[df_muni["hex_id"].astype(str).isin(hexes_foco)]
        if not rel.empty:
            xs_f: list[float] = []
            ys_f: list[float] = []
            for hid in rel["hex_id"].astype(str):
                try:
                    poly = _hex_boundary_mercator(hid)
                except Exception:
                    continue
                for x, y in poly:
                    xs_f.append(x)
                    ys_f.append(y)
            if xs_f:
                return _com_margem(min(xs_f), min(ys_f), max(xs_f), max(ys_f), pad_frac=pad_frac)

    destaque = _hex_destacado_mask(df_muni)
    rel = df_muni.loc[destaque]
    if rel.empty:
        score = _coluna_numerica(df_muni, "score_setor_2022_calibrado")
        oferta = _coluna_numerica(df_muni, "oferta_efetiva_disponivel")
        pop = _coluna_numerica(df_muni, "pop_total_setor_2022")
        relevante = score.notna() | (oferta.fillna(0.0) > 0) | (pop.fillna(0.0) > 0)
        rel = df_muni.loc[relevante]
    rel = rel[rel["hex_id"].notna()]

    xs: list[float] = []
    ys: list[float] = []
    for hid in rel["hex_id"].astype(str):
        try:
            poly = _hex_boundary_mercator(hid)
        except Exception:
            continue
        for x, y in poly:
            xs.append(x)
            ys.append(y)

    # Pins (Ultra + concorrentes) cujo hex H3 res-7 cai no municipio.
    hexes_muni: set[str] = set()
    if "hex_id" in df_muni.columns:
        hexes_muni = {str(h) for h in df_muni["hex_id"].dropna().astype(str)}
    for frame in (competitors_df, ultra_df):
        if frame is None or frame.empty or not {"lat", "lng"}.issubset(frame.columns):
            continue
        import h3

        for _, row in frame.iterrows():
            la = _safe_float(row.get("lat"))
            lo = _safe_float(row.get("lng"))
            if math.isnan(la) or math.isnan(lo):
                continue
            try:
                if str(h3.latlng_to_cell(float(la), float(lo), H3_RES)) not in hexes_muni:
                    continue
            except Exception:
                continue
            mx, my = _lonlat_to_mercator(float(lo), float(la))
            xs.append(mx)
            ys.append(my)

    if not xs or not ys:
        return None
    return _com_margem(min(xs), min(ys), max(xs), max(ys), pad_frac=pad_frac)


def _com_margem(
    minx: float, miny: float, maxx: float, maxy: float, *, pad_frac: float = _FOCUS_PAD_FRAC
) -> tuple[float, float, float, float]:
    """Aplica extensao MINIMA (evita super-ampliar com 1 hex isolado) e o padding fracional."""
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    span_x = max(maxx - minx, _FOCUS_MIN_SPAN_M)
    span_y = max(maxy - miny, _FOCUS_MIN_SPAN_M)
    minx, maxx = cx - span_x / 2.0, cx + span_x / 2.0
    miny, maxy = cy - span_y / 2.0, cy + span_y / 2.0
    pad_x = span_x * pad_frac
    pad_y = span_y * pad_frac
    return (minx - pad_x, miny - pad_y, maxx + pad_x, maxy + pad_y)


def _basemap_source(ctx: object) -> object:
    """Fonte de tiles: self-host (`API_BASEMAP_TILES_URL`) quando configurado, Voyager senao.

    Reusa a MESMA env var do Relatorio Pontual de proposito — os dois relatorios saem da mesma
    caixa e apontar para tileservers diferentes so criaria divergencia visual entre eles. O
    `contextily` aceita template de URL cru como `source`, entao a env entra direto.
    """
    import os

    url = os.environ.get(_BASEMAP_TILES_URL_ENV)
    if url:
        return url
    return getattr(ctx.providers.CartoDB, _BASEMAP_PROVIDER_ATTR)  # type: ignore[attr-defined]


def _atribuicao_tiles() -> str:
    """Credito do rodape, coerente com as fontes REALMENTE usadas.

    BLK-BASEMAP-06: chegou o dia que o docstring anterior antecipava — "se um dia a fonte de
    rotulos virar o proprio tileserver (ai o credito passa a ser so OSM)". Os rotulos passaram a
    vir do estilo `ultra-labels` do tileserver proprio, entao no modo self-host nenhum tile do
    CARTO e' consumido nem no fundo nem no texto.

    DELEGA para `censo_map._atribuicao_tiles()` de proposito: os dois relatorios saem da mesma
    caixa (emenda BLK-BASEMAP-02 a DEC-011) e manter duas copias da regra so criaria divergencia
    de rodape entre eles — foi exatamente o que aconteceu entre o BASEMAP-02 e o BASEMAP-03.
    """
    return _censo_atribuicao_tiles()


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
        source = _basemap_source(ctx)
        # Retry: a 1a busca (rede fria) pode dar timeout e deixar so essa camada offline (ex.:
        # Resumo, a 1a das 4 de foco) enquanto as demais ja pegam o cache. Tenta ate 3x antes de
        # cair no fallback offline (que segue valido se a rede realmente faltar).
        for attempt in range(3):
            try:
                img, extent = ctx.bounds2img(minx, miny, maxx, maxy, zoom=zoom, source=source, ll=False)
                return img, extent
            except Exception:
                if attempt == 2:
                    return None
        return None
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
    height: int = 704,
    basemap: bool = False,
    focus_bounds: tuple[float, float, float, float] | None = None,
    hexes_rotulados: set[str] | None = None,
    hexes_top: set[str] | None = None,
    nota_pins: str | None = None,
    rotular_valores: bool = True,
    rotulos_out: list[tuple[float, float, str]] | None = None,
) -> bytes:
    """Renderiza um PNG do municipio. `camada` define o esquema de cor dos hexes:

    `rotulos_out` (camada "espaco"): em vez de rasterizar os numeros no PNG, devolve
    `(x_px, y_px, texto)` de cada um nessa lista, para a pagina escrever como TEXTO do PDF --
    rasterizado e reduzido para caber no quadro, o numero saia pixelado (Juan, 2026-10-20).

    - "resumo": destacados em verde (rotulo = oferta_efetiva_disponivel), demais cinza.
    - "score": choropleth por `score_setor_2022_calibrado` (D5).
    - "residual": choropleth por `score_oportunidade_residual`.
    - "dominio": hexes coloridos por zona (1/2/3) das zonas do `dominio_df` (fallback amarelo).
    - "cobertura": municipio INTEIRO; aprovados (destacados) em verde, reprovados em cinza.
      Usa o municipio inteiro (passe `focus_bounds=None`); sem rotulos de valor e sem pins.

    `basemap=True` busca tiles online (DEC-011) com fallback offline. Em CI/teste default
    `basemap=False`.

    `rotular_valores=False` (2026-09-17, pedido do Juan) tira o numero do Residual de cima dos
    hexagonos da camada "resumo". `hexes_top` limita a cor e o numero de zona da camada "dominio"
    aos 10 melhores hexagonos. `hexes_rotulados` nao e' mais lido: o nome do bairro saiu dos
    hexagonos em 2026-10-20 (o parametro fica para quem ainda o passa). `nota_pins` e' a frase que
    o rodape do mapa acrescenta para declarar
    qual recorte de academias esta desenhado.

    `focus_bounds` (AJUSTE 1, FU1) e o bbox de VIEWPORT em EPSG:3857 (regioes relevantes do
    municipio + pins, com padding/extensao minima); quando dado, a CAMERA enquadra esse
    recorte (mesmo bbox nas 4 camadas, p/ ficarem comparaveis) em vez do municipio inteiro.
    TODOS os hexes seguem sendo desenhados; os que caem fora do viewport so ficam fora do
    quadro. `None` -> bbox de todos os hexes (comportamento anterior). READ-ONLY sobre o M1.
    """
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image, "RGBA")
    titulo = {
        "resumo": "Resumo da região",
        "score": "Score censitário",
        "residual": "Residual fitness",
        "dominio": "Expansão de domínio",
        "cobertura": "Visão geral do município",
        "espaco": "Quantas academias cabem em cada região",
    }.get(camada, camada)
    _draw_text(draw, (24, 18), titulo, font=_font(20))

    map_box = (20, 60, width - 20, height - 40)
    left, top, right, bottom = map_box

    rows = df_muni.copy()
    if "hex_id" not in rows.columns or rows.empty:
        draw.rounded_rectangle(map_box, radius=6, fill=(245, 245, 245), outline=(120, 120, 120))
        _draw_text(draw, (left + 16, (top + bottom) // 2), "Mapa indisponível para este município.", font=_font(13))
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
        _draw_text(draw, (left + 16, (top + bottom) // 2), "Mapa indisponível para este município.", font=_font(13))
        out = BytesIO()
        image.save(out, format="PNG", optimize=True)
        return out.getvalue()

    # AJUSTE 1 (FU1): se ha viewport de FOCO, a camera enquadra esse recorte (ja com
    # padding/extensao minima). Senao, bbox de TODOS os hexes + margem de 6% (anterior).
    if focus_bounds is not None:
        minx, miny, maxx, maxy = focus_bounds
    else:
        pad_x = (maxx - minx) * 0.06 + 1.0
        pad_y = (maxy - miny) * 0.06 + 1.0
        minx, maxx = minx - pad_x, maxx + pad_x
        miny, maxy = miny - pad_y, maxy + pad_y
    span_x = max(maxx - minx, 1.0)
    span_y = max(maxy - miny, 1.0)
    inner_w = right - left - 16
    inner_h = bottom - top - 16
    # Casa o aspect dos bounds ao do map_box (overscan simetrico do eixo curto) ANTES de buscar/
    # projetar os tiles, para o basemap preencher TODO o map_box sem deixar faixa cinza de
    # letterbox no interior do contorno. So amplia a EXTENSAO (nao a escala por eixo): a
    # geografia/hexes seguem sem distorcao, so ganham margem de basemap no eixo curto.
    target_aspect = inner_w / inner_h if inner_h > 0 else 1.0
    if span_x / span_y < target_aspect:
        new_span_x = span_y * target_aspect
        cx = (minx + maxx) / 2.0
        minx, maxx = cx - new_span_x / 2.0, cx + new_span_x / 2.0
        span_x = new_span_x
    else:
        new_span_y = span_x / target_aspect
        cy = (miny + maxy) / 2.0
        miny, maxy = cy - new_span_y / 2.0, cy + new_span_y / 2.0
        span_y = new_span_y
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
    fonte_propria = _fonte_propria_mask(rows).to_numpy()
    oferta_hex = pd.to_numeric(rows.get("oferta_efetiva_disponivel"), errors="coerce").to_numpy()
    score_hex = pd.to_numeric(rows.get("score_setor_2022_calibrado"), errors="coerce").to_numpy()
    residual_hex = pd.to_numeric(rows.get("score_oportunidade_residual"), errors="coerce").to_numpy()

    # FU1: zonas geometricas de dominio (camada "dominio"): hex_id -> 0|1|2.
    hex_id_arr = rows.get("hex_id")
    hex_id_list = [str(h) for h in hex_id_arr.tolist()] if hex_id_arr is not None else []
    hex_zona_geo: dict[str, int] = dict(municipio_result.get("hex_zona_geo") or {})

    # AJUSTE 1 (FU1): com viewport de FOCO, hexes fora do recorte projetam para fora do
    # `map_box` e poderiam invadir o titulo/rodape. Desenhamos hexes e rotulos numa OVERLAY
    # RGBA e compomos SO o recorte de `map_box` -> nada vaza para fora do quadro do mapa.
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay, "RGBA")

    label_pins: list[tuple[int, int, str]] = []
    # Camada "espaco" (2026-10-20): o numero de academias que cabem no hexagono aprovado.
    espaco_labels: list[tuple[int, int, str]] = []
    academias = dict(municipio_result.get("academias_por_hex") or {})
    zona_labels: list[tuple[int, int, str, tuple[int, int, int]]] = []
    # Sem nome de bairro sobre o hexagono desde 2026-10-20 (Juan): os slides de bairro do inicio
    # (Visao Geral e Bairros Oficiais) ja' dizem onde cada bairro fica; o nome aqui so' cobria o
    # dado. O BLK-RELMUN-08 tinha posto o bairro dominante nos hexagonos destacados.
    # Resposta unica (DEC-077, Brasil): nao ha "aprovado" -- Visao Geral e Resumo saem neutros.
    resposta_unica = _resposta_unica(municipio_result)
    for poly, pos in geometrias:
        pixels = [(int(round(px)), int(round(py))) for px, py in (project(x, y) for x, y in poly)]
        if len(pixels) < 3:
            continue
        if camada == "cobertura":
            # Aprovado via fallback municipal sai no cinza do reprovado (Juan, 2026-10-20): a
            # Visao Geral mostra so' onde ha dado proprio aprovado.
            if resposta_unica:
                color = _HEX_NEUTRO_RGBA
            elif destaque_mask[pos] and fonte_propria[pos]:
                color = _HEX_APROVADO_RGBA
            else:
                color = _HEX_REPROVADO_RGBA
            odraw.polygon(pixels, fill=color, outline=(255, 255, 255, 90))
        elif camada == "resumo":
            # Os nao aprovados sao desenhados: eles sao o CONTEXTO do quadro. O pedido de
            # 2026-09-17 era que o ZOOM priorizasse os hexagonos verdes quando houvesse cinza nas
            # pontas -- quem faz isso e' o `focus_bounds` (hexagonos escolhidos), nao este desenho.
            # Apagar o cinza foi leitura errada e durou um dia (Juan, 2026-09-18).
            if destaque_mask[pos] and not resposta_unica:
                color = _HEX_DESTAQUE_RGBA
            else:
                color = _HEX_NEUTRO_RGBA
            odraw.polygon(pixels, fill=color, outline=(255, 255, 255, 90))
            # O Residual de cada hexagono destacado SAIU do mapa em 2026-09-17, a pedido do Juan:
            # em Sao Paulo eram 154 plaquinhas e o mapa virava um tapete de numeros. Os valores
            # seguem na tabela "Comparacao das Regioes" e o total, no box "Como calculamos o
            # espaco". `rotular_valores=True` reproduz o mapa de antes (o default o mantem para
            # quem chama esta funcao direto).
            if (rotular_valores and destaque_mask[pos] and not resposta_unica
                    and not math.isnan(oferta_hex[pos])):
                cx = int(sum(p[0] for p in pixels) / len(pixels))
                cy = int(sum(p[1] for p in pixels) / len(pixels))
                label_pins.append((cx, cy, _format_number(oferta_hex[pos], 0)))
        elif camada == "espaco":
            # Todo aprovado em verde -- no Brasil, laranja (`_HEX_ESPACO_RGBA`) --; o fallback
            # municipal tambem conta no espaco, o resto cinza. O numero e' o ponto da pagina: no
            # Resumo cada verde parecia "uma vaga".
            cor_espaco = _HEX_ESPACO_RGBA if resposta_unica else (20, 130, 65, 245)
            color = cor_espaco if destaque_mask[pos] else _HEX_REPROVADO_RGBA
            odraw.polygon(pixels, fill=color, outline=(255, 255, 255, 160))
            n_acad = academias.get(hex_id_list[pos] if pos < len(hex_id_list) else "")
            if n_acad:
                cx = int(sum(p[0] for p in pixels) / len(pixels))
                cy = int(sum(p[1] for p in pixels) / len(pixels))
                espaco_labels.append((cx, cy, str(n_acad)))
        elif camada == "score":
            color = _score_faixa_color(score_hex[pos])
            odraw.polygon(pixels, fill=color, outline=(255, 255, 255, 70))
        elif camada == "residual":
            color = _score_faixa_color(residual_hex[pos])
            odraw.polygon(pixels, fill=color, outline=(255, 255, 255, 70))
        elif camada == "dominio":
            hid = hex_id_list[pos] if pos < len(hex_id_list) else ""
            zona = hex_zona_geo.get(hid)
            # Com `hexes_top` (2026-09-17, pedido do Juan), so' os 10 melhores levam cor e numero
            # de zona: numerar os 154 aprovados de Sao Paulo enchia o mapa de circulos magenta.
            if hexes_top is not None and hid not in hexes_top:
                zona = None
            if zona is not None:
                color = _ZONA_CORES_RGBA[zona]
                odraw.polygon(pixels, fill=color, outline=(255, 255, 255, 110))
                cx = int(sum(p[0] for p in pixels) / len(pixels))
                cy = int(sum(p[1] for p in pixels) / len(pixels))
                zona_labels.append((cx, cy, str(zona + 1), _ZONA_CORES_PDF[zona]))
            else:
                odraw.polygon(pixels, fill=_HEX_NEUTRO_RGBA, outline=(255, 255, 255, 90))

    # Compoe a overlay SO dentro do `map_box` (confinamento do recorte de foco).
    clip = Image.new("L", (width, height), 0)
    ImageDraw.Draw(clip).rounded_rectangle(map_box, radius=6, fill=255)

    def _compor_no_map_box(camada: Image.Image) -> None:
        masked = Image.composite(camada, Image.new("RGBA", (width, height), (0, 0, 0, 0)),
                                 ImageChops.multiply(camada.split()[3], clip))
        image.paste(masked, (0, 0), masked)

    _compor_no_map_box(overlay)

    # BLK-BASEMAP-03: NOMES DE RUA por cima dos hexes. O estilo self-host `ultra-maptiler` tem as
    # geometrias de via mas nao a camada `transportation_name`, entao sem este overlay o mapa sai
    # com as ruas desenhadas e SEM nome — regressao contra o Voyager, que trazia os nomes
    # embutidos no raster. Mesma fonte e mesmo contrato do Pontual (`_fetch_labels`, BLK-RELPON-07,
    # com cache em disco pela emenda a DEC-004), reprojetada pelo EXTENT DOS TILES (nao pelo bbox,
    # senao os nomes saem deslocados) e recortada no `map_box` como as demais camadas.
    #
    # Ordem: DEPOIS dos hexes (o nome tem de ler sobre a cor) e ANTES dos pins e dos rotulos de
    # valor, que seguem por cima — a mesma prioridade que o gate visual do FU1 fixou.
    # `drew_basemap` como guarda: sem fundo de ruas nao ha o que rotular, e a condicao de rede e'
    # a mesma. Best-effort: qualquer falha deixa o mapa exatamente como estava.
    if drew_basemap:
        # `zoom_bump=0`: rotulos no MESMO zoom do frame. Com o bump padrao (+1) o mosaico sai
        # 2x mais denso que o mapa e o texto encolhe pela metade no resize — a mesma armadilha
        # que deixou os nomes sub-pixel no Relatorio Pontual (BLK-BASEMAP-06).
        rotulos_rua = _fetch_labels((minx, miny, maxx, maxy), width, zoom_bump=0)
        if rotulos_rua is not None:
            try:
                rua_img, rua_extent = rotulos_rua
                ex_minx, ex_maxx, ex_miny, ex_maxy = rua_extent
                rx0, ry0 = project(ex_minx, ex_maxy)
                rx1, ry1 = project(ex_maxx, ex_miny)
                rua = rua_img.resize(
                    (max(1, int(round(rx1 - rx0))), max(1, int(round(ry1 - ry0)))),
                    Image.Resampling.LANCZOS,
                )
                camada_rua = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                camada_rua.paste(rua, (int(round(rx0)), int(round(ry0))))
                _compor_no_map_box(camada_rua)
            except Exception:
                pass  # nome de rua e' aditivo: falha aqui nao pode derrubar a pagina

    # Pins de Ultra/concorrentes (geograficos; dentro da bbox).
    _draw_pins(draw, image, competitors_df, project, "", minx, maxx, miny, maxy)
    _draw_pins(draw, image, ultra_df, project, "__ultra__", minx, maxx, miny, maxy)

    # BLK-RELPON-09-FU1 (gate visual de Vinicius, 2026-07-21): os rotulos de valor sao
    # desenhados numa overlay PROPRIA, composta DEPOIS dos pins, para que o marcador quadrado
    # nao cubra o numero de Residual Fitness do hexagono -- que e o dado principal da pagina.
    # Antes do FU1 a ordem era hexes+rotulos -> pins, e o pin vencia o numero. Mesmo `clip` do
    # `map_box`, entao o confinamento do recorte de foco (AJUSTE 1/FU1) segue valendo.
    rotulos_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    rdraw = ImageDraw.Draw(rotulos_overlay, "RGBA")

    # Rotulos de oferta sobre hexes destacados (camada resumo). Decisao do produto (Vinicius,
    # 2026-06-24): exibir o Residual em TODOS os hexes aprovados (sem cap), com fonte menor
    # para mitigar a sobreposicao quando ha muitos destacados no quadro.
    label_font = _font(8)
    for cx, cy, txt in label_pins:
        w = _text_width(rdraw, txt, label_font)
        rdraw.rectangle(
            [cx - w // 2 - 2, cy - 8, cx + w // 2 + 2, cy + 8], fill=_ROTULO_PLACA_RGBA
        )
        _draw_text(rdraw, (cx - w // 2, cy - 7), txt, font=label_font, fill=_ROTULO_INK)

    # Numero em branco direto sobre o verde do hexagono: um circulo do tamanho do hexagono
    # escondia a cor, e a cor e' metade da leitura (aprovado x nao aprovado).
    espaco_font = _font(12)
    for cx, cy, txt in espaco_labels:
        if rotulos_out is not None:
            # So' os que caem no quadro: o resto ficaria por cima da moldura na pagina.
            if left <= cx <= right and top <= cy <= bottom:
                rotulos_out.append((float(cx), float(cy), txt))
            continue
        w = _text_width(rdraw, txt, espaco_font)
        _draw_text(rdraw, (cx - w // 2, cy - 8), txt, font=espaco_font, fill=(255, 255, 255))

    # FU1: numero da estrategia (1/2/3) sobre cada hex de zona (camada dominio). Mesmo realce
    # magenta dos valores (decisao de Vinicius no gate: aplicar nos dois, por consistencia
    # entre as paginas Resumo e Dominio).
    zona_font = _font(15)
    for cx, cy, num, _zc in zona_labels:
        w = _text_width(rdraw, num, zona_font)
        rdraw.ellipse([cx - 11, cy - 11, cx + 11, cy + 11], fill=_ROTULO_PLACA_RGBA)
        _draw_text(rdraw, (cx - w // 2, cy - 9), num, font=zona_font, fill=_ROTULO_INK)

    _compor_no_map_box(rotulos_overlay)

    # Sem legenda em nenhuma camada desta funcao: a cobertura perdeu a sua em 2026-10-20 e o
    # Resumo (aprovado proprio x fallback municipal) em 2026-10-21, a pedido do Juan.

    # Rodape com atribuicao quando ha basemap.
    footer = (
        f"Agregação H3 res 7 - EPSG:3857 - {_atribuicao_tiles()}"
        if drew_basemap
        else "Agregação H3 res 7 - fundo de ruas offline"
    )
    _rodape_do_mapa(draw, footer, nota_pins, height=height, largura_max=width - 48)

    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def bounds_nucleo_urbano(bairros_geo: dict[str, Any] | None) -> tuple[float, float, float, float] | None:
    """bbox (EPSG:3857) da parte URBANA do municipio, ou None se nao der para distinguir.

    Ordena os bairros por DENSIDADE (hab/km2) desc e acumula ate cobrir `_URBANO_POP_ALVO` da
    populacao OU a densidade cair abaixo de `_URBANO_DENS_MIN_FRAC` da maior; o bbox dos
    escolhidos e' o nucleo. Densidade e' o discriminante certo aqui -- por populacao bruta um
    distrito rural grande entraria e o recorte voltaria a ser o municipio inteiro.

    As DUAS condicoes de parada importam: so a meta de populacao nao basta, porque quando o
    nucleo urbano nao a alcanca sozinho o laco segue somando bairros esparsos ate engolir a
    area rural (medido em teste com nucleo de 40k e distrito rural de 12k a 200 km).

    A sobra ("demais setores") fica FORA do calculo: ela e' tipicamente a area rural sem nome,
    e inclui-la puxaria o recorte de volta para o territorio todo. Ela continua sendo DESENHADA
    no recorte -- so nao vota em onde ele fica.

    `None` quando nao ha bairro com area/populacao utilizavel (o chamador cai no mapa cheio).
    """
    bairros = [
        b for b in ((bairros_geo or {}).get("bairros") or [])
        if not b.get("sobra") and b.get("aneis")
    ]
    if not bairros:
        return None
    pop_total = sum(max(0.0, _safe_float(b.get("pop"))) for b in bairros)
    if pop_total <= 0:
        return None

    def _dens(b: dict[str, Any]) -> float:
        d = _safe_float(b.get("densidade"))
        return -1.0 if math.isnan(d) else d

    ordenados = sorted(bairros, key=_dens, reverse=True)
    piso = max(0.0, _dens(ordenados[0])) * _URBANO_DENS_MIN_FRAC
    # O mais denso entra SEMPRE (ancora do recorte); os seguintes so enquanto forem densos o
    # bastante E a meta de populacao nao tiver sido atingida.
    escolhidos: list[dict[str, Any]] = [ordenados[0]]
    acumulado = max(0.0, _safe_float(ordenados[0].get("pop")))
    for b in ordenados[1:]:
        if acumulado >= pop_total * _URBANO_POP_ALVO or _dens(b) < piso:
            break
        escolhidos.append(b)
        acumulado += max(0.0, _safe_float(b.get("pop")))
    aneis = [anel for b in escolhidos for anel in b["aneis"]]
    if not aneis:
        return None

    minx = min(x for anel in aneis for x, _ in anel)
    maxx = max(x for anel in aneis for x, _ in anel)
    miny = min(y for anel in aneis for _, y in anel)
    maxy = max(y for anel in aneis for _, y in anel)

    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    span_x = max(maxx - minx, _URBANO_SPAN_MIN_M)
    span_y = max(maxy - miny, _URBANO_SPAN_MIN_M)
    pad_x, pad_y = span_x * _URBANO_PAD_FRAC, span_y * _URBANO_PAD_FRAC
    return (
        cx - span_x / 2.0 - pad_x, cy - span_y / 2.0 - pad_y,
        cx + span_x / 2.0 + pad_x, cy + span_y / 2.0 + pad_y,
    )


# Bairros Oficiais em VARIAS paginas (Juan, 2026-10-20: "separa em alguns slides esse mapa"). Em
# Sao Paulo (96 bairros) o mapa unico cabia 29 nomes e a placa cruzava a divisa; com numero no
# lugar do nome e o municipio repartido, cada bairro tem numero proprio dentro do seu limite e o
# indice ao lado diz o nome. Uma parte = uma pagina com zoom so' naquela regiao.
_BAIRROS_POR_PARTE = 25
# Com o CNEFE (DEC-076) o municipio tem centenas de bairros (Sao Jose dos Campos: 331 contra as 35
# regioes do IBGE) e numerar todos dava 40 paginas. Desde 2026-10-21 (Juan) so' os mais populosos
# ganham numero e indice; os demais seguem no mapa, em cinza, sem numero.
_BAIRROS_NUMERADOS_MAX = 40
# Mesma regra na tabela BAIRROS APROVADOS da Visao Geral: os mais populosos, em ordem
# alfabetica, e "+ N outros" com o total no titulo.
_BAIRROS_APROVADOS_LISTADOS_MAX = 60
# Distancia minima (px, no quadro do mapa de 1000 x 704) entre dois numeros da mesma parte; abaixo
# disso os circulos se encostam e a parte e' dividida de novo.
_BAIRRO_NUMERO_DMIN_PX = 36.0
# Parte com ate tantos bairros nao ganha pagina: e' zona rural extensa, longe da cidade, grande o
# bastante para o numero caber no mapa geral (Parelheiros/Marsilac em SP).
_BAIRROS_PARTE_MIN = 3
_PARTE_CORES: tuple[tuple[int, int, int], ...] = (
    ULTRA_TURQUESA, ULTRA_MAGENTA, ULTRA_LARANJA, (70, 110, 200), (120, 170, 60),
    (150, 90, 190), (210, 80, 70), (60, 150, 190),
)
_BAIRRO_APAGADO_FILL_RGBA = (232, 234, 238, 255)
_BAIRRO_APAGADO_TRACO_RGBA = (175, 180, 190, 255)
_BAIRRO_NUMERO_RGBA = (*ULTRA_MAGENTA, 245)


def _ponto_interno_bairro(bairro: dict[str, Any]) -> tuple[float, float]:
    """Ponto bem DENTRO do bairro (polo de inacessibilidade da maior parte), em EPSG:3857.

    O `rotulo_xy` e' o centro geometrico, que em bairro em forma de "C" cai fora dele ou colado na
    divisa -- o numero ficaria parecendo de outro bairro.
    """
    from shapely.geometry import Polygon
    from shapely.ops import polylabel

    try:
        partes = [Polygon(a).buffer(0) for a in bairro.get("aneis") or [] if len(a) >= 3]
        maior = max((g for g in partes if not g.is_empty), key=lambda g: g.area)
        if maior.geom_type != "Polygon":
            maior = max(maior.geoms, key=lambda g: g.area)
        c = polylabel(maior, tolerance=max(maior.length / 400.0, 1.0))
        return float(c.x), float(c.y)
    except Exception:
        x, y = bairro["rotulo_xy"]
        return float(x), float(y)


def _bbox_bairros(
    bairros: list[dict[str, Any]], *, pad_frac: float = 0.0
) -> tuple[float, float, float, float]:
    xs = [float(x) for b in bairros for a in b["aneis"] for x, _ in a]
    ys = [float(y) for b in bairros for a in b["aneis"] for _, y in a]
    px = (max(xs) - min(xs)) * pad_frac
    py = (max(ys) - min(ys)) * pad_frac
    return (min(xs) - px, min(ys) - py, max(xs) + px, max(ys) + py)


def dividir_bairros_em_partes(
    bairros_geo: dict[str, Any] | None,
    *,
    max_por_parte: int = _BAIRROS_POR_PARTE,
    dmin_px: float = _BAIRRO_NUMERO_DMIN_PX,
    quadro_px: tuple[float, float] = (944.0, 588.0),
    max_numerados: int | None = _BAIRROS_NUMERADOS_MAX,
) -> dict[str, Any] | None:
    """Reparte os bairros do municipio em partes de leitura e numera todos. PURA e deterministica.

    Corte recursivo pela mediana do eixo mais longo ate cada parte ter no maximo `max_por_parte`
    bairros e nenhum par de numeros a menos de `dmin_px` no zoom da propria parte. Um VAZIO maior
    que 30% do eixo (zona rural longe da cidade) vira corte antes de tudo, senao o zoom da parte
    enquadraria o vazio. Partes de ate `_BAIRROS_PARTE_MIN` bairros viram `avulsos`: numerados no
    mapa geral, sem pagina propria. A numeracao segue a leitura (de cima para baixo, da esquerda
    para a direita), parte a parte, e termina nos avulsos.

    So' os `max_numerados` bairros mais populosos entram (desempate pelo nome); os outros vao em
    `fora`, sem numero. `None` numera todos.

    `parte_de` diz a parte (indice em `partes`) de TODO bairro real, numerado ou nao: o de `fora`
    vai para a parte do bairro numerado mais proximo. O mapa pinta o municipio inteiro nas cores
    das partes -- com so' os numerados coloridos, o cinza cobria 84% de Sao Jose dos Campos e
    metade da populacao (Juan, 2026-10-22). Avulso nao tem parte e fica fora de `parte_de`.

    Devolve `{"partes": [[nome]], "avulsos": [nome], "numero": {nome: n}, "ponto": {nome: (x, y)},
    "fora": [nome], "parte_de": {nome: k}, "n_total": int}` ou `None` sem bairro real. A sobra
    "(demais setores)" nunca e' numerada nem entra em parte.
    """
    if not tem_bairro_real(bairros_geo):
        return None
    todos_bairros = [b for b in (bairros_geo or {}).get("bairros") or [] if not b.get("sobra")]
    bairros = todos_bairros
    if max_numerados is not None and len(bairros) > max_numerados:
        bairros = sorted(bairros, key=lambda b: (-_safe_float(b.get("pop")), str(b["nome"])))[:max_numerados]
    dentro = {str(b["nome"]) for b in bairros}
    fora = sorted(str(b["nome"]) for b in todos_bairros if str(b["nome"]) not in dentro)
    por_nome = {str(b["nome"]): b for b in bairros}
    ponto = {nome: _ponto_interno_bairro(b) for nome, b in por_nome.items()}

    def colide(nomes: list[str]) -> bool:
        minx, miny, maxx, maxy = _bbox_bairros([por_nome[n] for n in nomes])
        escala = min(quadro_px[0] / max(maxx - minx, 1.0), quadro_px[1] / max(maxy - miny, 1.0))
        pts = [(ponto[n][0] * escala, ponto[n][1] * escala) for n in nomes]
        return any(
            (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 < dmin_px ** 2
            for i, a in enumerate(pts) for b in pts[i + 1:]
        )

    def dividir(nomes: list[str]) -> list[list[str]]:
        if len(nomes) <= 1:
            return [nomes]
        xs = [ponto[n][0] for n in nomes]
        ys = [ponto[n][1] for n in nomes]
        eixo = 0 if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else 1
        nomes = sorted(nomes, key=lambda n: (ponto[n][eixo], n))
        vals = [ponto[n][eixo] for n in nomes]
        span = (vals[-1] - vals[0]) or 1.0
        if len(nomes) > _BAIRROS_PARTE_MIN:
            gaps = [vals[k + 1] - vals[k] for k in range(len(vals) - 1)]
            gap, corte = max((g, k + 1) for k, g in enumerate(gaps))
            positivos = sorted(g for g in gaps if g > 0)
            tipico = positivos[len(positivos) // 2] if positivos else 0.0
            # Vazio = grande no eixo E muito maior que o espacamento tipico: numa malha regular
            # cada vao entre colunas passa de 30% do eixo, e so' a 1a condicao picaria a cidade.
            if gap > 0.3 * span and gap > 3.0 * tipico:
                return dividir(nomes[:corte]) + dividir(nomes[corte:])
        if len(nomes) <= max_por_parte and (len(nomes) <= _BAIRROS_PARTE_MIN or not colide(nomes)):
            return [nomes]
        meio = len(nomes) // 2
        return dividir(nomes[:meio]) + dividir(nomes[meio:])

    todas = dividir(list(por_nome))
    if len(todas) == 1:
        partes, avulsos = todas, []
    else:
        partes = [p for p in todas if len(p) > _BAIRROS_PARTE_MIN]
        avulsos = [n for p in todas if len(p) <= _BAIRROS_PARTE_MIN for n in p]
        if not partes:  # so' parte pequena: melhor uma pagina com todos do que nenhuma
            partes, avulsos = [[n for p in todas for n in p]], []

    ys_todos = [ponto[n][1] for n in por_nome]
    faixa_cidade = max((max(ys_todos) - min(ys_todos)) / 6.0, 1.0)

    def centro(p: list[str]) -> tuple[float, float]:
        return (sum(ponto[n][0] for n in p) / len(p), sum(ponto[n][1] for n in p) / len(p))

    partes.sort(key=lambda p: (-round(centro(p)[1] / faixa_cidade), centro(p)[0]))
    numero: dict[str, int] = {}

    def em_leitura(nomes: list[str]) -> list[str]:
        ys = [ponto[n][1] for n in nomes]
        faixa = max((max(ys) - min(ys)) / 12.0, 1.0)
        return sorted(nomes, key=lambda n: (-round(ponto[n][1] / faixa), ponto[n][0], n))

    for p in partes:
        for n in em_leitura(p):
            numero[n] = len(numero) + 1
    avulsos = em_leitura(avulsos) if avulsos else []
    for n in avulsos:
        numero[n] = len(numero) + 1
    partes = [sorted(p, key=lambda n: numero[n]) for p in partes]
    parte_de = {n: k for k, p in enumerate(partes) for n in p}
    if parte_de and fora:
        # Centro do bairro (`rotulo_xy`) contra o ponto interno dos numerados: basta para escolher
        # a parte, e o `polylabel` dos centenas de bairros de fora sairia caro. Empate pelo numero.
        refs = sorted(parte_de, key=lambda n: numero[n])
        for b in todos_bairros:
            nome = str(b["nome"])
            if nome not in fora:
                continue
            xy = b.get("rotulo_xy")
            if xy is None:
                pts = [p for a in b.get("aneis") or [] for p in a]
                if not pts:
                    continue
                xy = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
            bx, by = float(xy[0]), float(xy[1])
            perto = min(refs, key=lambda n: ((ponto[n][0] - bx) ** 2 + (ponto[n][1] - by) ** 2, numero[n]))
            parte_de[nome] = parte_de[perto]
    return {"partes": partes, "avulsos": avulsos, "numero": numero, "ponto": ponto,
            "fora": fora, "parte_de": parte_de, "n_total": len(todos_bairros)}


def _render_mapa_bairros(
    bairros_geo: dict[str, Any],
    *,
    titulo: str = "Bairros oficiais",
    destaque: set[str] | None = None,
    metrica: str | None = None,
    bounds: tuple[float, float, float, float] | None = None,
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
    width: int = 1000,
    height: int = 704,
    basemap: bool = False,
    nota_pins: str | None = None,
    numeros: dict[str, int] | None = None,
    pontos: dict[str, tuple[float, float]] | None = None,
    apagados: set[str] | None = None,
    cor_por_bairro: dict[str, tuple[int, int, int]] | None = None,
    marcadores: list[tuple[float, float, str, tuple[int, int, int]]] | None = None,
    localizar: set[str] | None = None,
    sem_aprovado: bool = False,
    cor_clara: set[str] | None = None,
    so_contorno: bool = False,
) -> bytes:
    """PNG dos bairros (BLK-RELMUN-06), no formato do material de Expansao. Dois modos:

    `sem_aprovado` (resposta unica, DEC-077): nas metricas "resumo"/"cobertura" nenhum bairro sai
    no verde de aprovado -- a lista de onde expandir e' so' a do "Onde crescer".

    - `metrica=None` (default): LIMITE TERRITORIAL -- divisa de cada bairro em vermelho sobre o
      basemap claro, divisa do municipio em preto, nome em placa branca.
    - `metrica="score"` (BLK-RELMUN-09): CHOROPLETH -- cada bairro pintado pela sua faixa de
      score, com a MESMA regua `score_band_to_color` das camadas de hexagono (regra visual
      canonica do §5): a cor precisa significar a mesma coisa nos dois mapas do relatorio.

    O choropleth por bairro so vale para metrica CENSITARIA, e a razao e' geometrica: o bairro e'
    agregacao EXATA de setores (~21 setores por bairro em Novo Hamburgo), enquanto o hexagono
    res-7 (5,16 km2) e' MAIOR que 86% dos bairros de la. Trazer metrica de hexagono para o bairro
    seria repartir, nao agregar -- por isso Residual/mercado seguem em hexagono.

    `bounds` (EPSG:3857) enquadra um recorte explicito -- usado pela pagina do NUCLEO URBANO
    (`bounds_nucleo_urbano`), onde o municipio inteiro faria a cidade virar um ponto.

    `destaque` (nomes) pinta um subconjunto em verde -- e o que separa "Bairros oficiais"
    (destaque vazio) de "Melhores bairros" sem duplicar renderizador.

    Bairros Oficiais em partes (2026-10-20): `numeros` troca o nome em placa por um NUMERO em
    circulo no `pontos[nome]` (o indice com os nomes vai na pagina); `apagados` sai em cinza (os
    bairros das outras partes, so' para situar); `cor_por_bairro` pinta cada bairro na cor da sua
    parte (`cor_clara`: os sem numero, num tom mais claro); `so_contorno` troca a cor cheia por
    contorno forte na cor da parte, sem preenchimento (paginas das partes: o limite do bairro e' o
    que se le ali); `marcadores` sao circulos grandes (numero da parte); `localizar` desenha no
    canto um mini-mapa do municipio com esses bairros realcados.

    Mesma camera, mesma projecao e mesmo `map_box` de `_render_mapa_municipio`, de proposito: as
    paginas tem de parecer o mesmo mapa. `basemap=False` (default de CI/teste) cai no canvas
    claro offline. READ-ONLY sobre o M1: geometria de bairro e display, nao entra em score.
    """
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image, "RGBA")
    _draw_text(draw, (24, 18), titulo, font=_font(20))

    map_box = (20, 60, width - 20, height - 40)
    left, top, right, bottom = map_box

    bairros = list(bairros_geo.get("bairros") or [])
    contorno = list(bairros_geo.get("contorno") or [])
    aneis_todos = [anel for b in bairros for anel in b["aneis"]]
    if not aneis_todos:
        draw.rounded_rectangle(map_box, radius=6, fill=(245, 245, 245), outline=(120, 120, 120))
        _draw_text(
            draw, (left + 16, (top + bottom) // 2),
            f"Bairros não mapeados na base {_instituto_censo()} 2022 para este município.", font=_font(13),
        )
        out = BytesIO()
        image.save(out, format="PNG", optimize=True)
        return out.getvalue()

    if bounds is not None:
        # Recorte EXPLICITO (nucleo urbano): ja vem com padding proprio. Todos os bairros
        # seguem sendo desenhados; os de fora apenas caem fora do quadro -- e o `clip` do
        # `map_box` impede que invadam titulo e rodape.
        minx, miny, maxx, maxy = bounds
    else:
        minx = min(x for anel in aneis_todos for x, _ in anel)
        maxx = max(x for anel in aneis_todos for x, _ in anel)
        miny = min(y for anel in aneis_todos for _, y in anel)
        maxy = max(y for anel in aneis_todos for _, y in anel)
        pad_x = (maxx - minx) * 0.06 + 1.0
        pad_y = (maxy - miny) * 0.06 + 1.0
        minx, maxx = minx - pad_x, maxx + pad_x
        miny, maxy = miny - pad_y, maxy + pad_y

    span_x = max(maxx - minx, 1.0)
    span_y = max(maxy - miny, 1.0)
    inner_w = right - left - 16
    inner_h = bottom - top - 16
    # Overscan do eixo curto ANTES de buscar tiles (mesma razao de `_render_mapa_municipio`:
    # sem isso sobra faixa cinza de letterbox dentro do quadro).
    target_aspect = inner_w / inner_h if inner_h > 0 else 1.0
    if span_x / span_y < target_aspect:
        novo = span_y * target_aspect
        cx = (minx + maxx) / 2.0
        minx, maxx = cx - novo / 2.0, cx + novo / 2.0
        span_x = novo
    else:
        novo = span_x / target_aspect
        cy = (miny + maxy) / 2.0
        miny, maxy = cy - novo / 2.0, cy + novo / 2.0
        span_y = novo
    scale = min(inner_w / span_x, inner_h / span_y)
    offset_x = left + 8 + (inner_w - span_x * scale) / 2
    offset_y = top + 8 + (inner_h - span_y * scale) / 2

    def project(x: float, y: float) -> tuple[float, float]:
        return offset_x + (x - minx) * scale, offset_y + (maxy - y) * scale

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
                bm = bm.resize(
                    (max(1, int(round(tx1 - tx0))), max(1, int(round(ty1 - ty0)))),
                    Image.Resampling.LANCZOS,
                )
                canvas = Image.new("RGB", (width, height), (245, 245, 245))
                canvas.paste(bm, (int(round(tx0)), int(round(ty0))))
                image.paste(canvas.crop((left, top, right, bottom)), (left, top))
                draw.rounded_rectangle(map_box, radius=6, outline=(120, 120, 120))
                drew_basemap = True
            except Exception:
                drew_basemap = False
    if not drew_basemap:
        draw.rounded_rectangle(map_box, radius=6, fill=(245, 245, 245), outline=(120, 120, 120))

    clip = Image.new("L", (width, height), 0)
    ImageDraw.Draw(clip).rounded_rectangle(map_box, radius=6, fill=255)

    def _compor_no_map_box(camada: Image.Image) -> None:
        masked = Image.composite(
            camada, Image.new("RGBA", (width, height), (0, 0, 0, 0)),
            ImageChops.multiply(camada.split()[3], clip),
        )
        image.paste(masked, (0, 0), masked)

    def _compor_cor_cheia(camada: Image.Image) -> None:
        # Alpha aplicado UMA vez: `_compor_no_map_box` escurece a cor pelo alpha e ainda a usa
        # como mascara, e a cor das partes saia bege no lugar do laranja (SJC, 2026-10-22).
        image.paste(camada.convert("RGB"), (0, 0), ImageChops.multiply(camada.split()[3], clip))

    def _pixels(anel: list[tuple[float, float]]) -> list[tuple[int, int]]:
        return [(int(round(px)), int(round(py))) for px, py in (project(x, y) for x, y in anel)]

    # Divisas numa overlay: hex/bairro fora do quadro nao pode invadir titulo nem rodape.
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay, "RGBA")
    # Preenchimento das partes dos Bairros Oficiais (`cor_por_bairro`) numa camada propria, com a
    # composicao de `_compor_cor_cheia`, entre o fundo (sobra e cinzas) e as divisas -- que vao
    # para a sua camada so' nesse caso, para os outros mapas sairem como antes.
    camada_partes = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(camada_partes, "RGBA")
    camada_linhas = Image.new("RGBA", (width, height), (0, 0, 0, 0)) if cor_por_bairro else overlay
    ldraw = ImageDraw.Draw(camada_linhas, "RGBA") if cor_por_bairro else odraw
    alvos = {str(n) for n in (destaque or set())}
    choropleth = metrica in _BAIRRO_METRICAS

    def _cor_do_bairro(bairro: dict[str, Any]) -> tuple[int, int, int, int]:
        """Cor do bairro na metrica pedida, com CINZA para 'sem dado' em todas elas.

        Cinza nunca pode virar a faixa mais baixa: "nao medido" e "medido e ruim" sao afirmacoes
        diferentes, e no mapa a segunda tira o bairro da lista de candidatos por engano.
        """
        if metrica == "score":
            v = _safe_float(bairro.get("score"))
            return _HEX_NEUTRO_RGBA if math.isnan(v) else _score_faixa_color(v, alpha=205)
        if metrica == "residual":
            v = _safe_float(bairro.get("score_residual"))
            return _HEX_NEUTRO_RGBA if math.isnan(v) else _score_faixa_color(v, alpha=205)
        if metrica in ("resumo", "cobertura"):
            if sem_aprovado:
                # Resposta unica (DEC-077): o mapa so' situa os bairros -- o cinza escuro do
                # "reprovado" virava uma mancha so' na cidade inteira (SJC, 2026-10-22).
                return _HEX_NEUTRO_RGBA
            # Mesmas cores/semantica das camadas de hexagono (aprovado x reprovado).
            if bairro.get("destacado"):
                return _HEX_APROVADO_RGBA
            v = _safe_float(bairro.get("oferta_alunos"))
            return _HEX_NEUTRO_RGBA if math.isnan(v) else _HEX_REPROVADO_RGBA
        if metrica == "dominio":
            zona = bairro.get("zona")
            return _ZONA_CORES_RGBA[int(zona)] if zona is not None else _HEX_NEUTRO_RGBA
        return _BAIRRO_FILL_RGBA

    # Desenha a SOBRA primeiro: ela costuma envolver os bairros, e por baixo nao come a divisa.
    def _contorno_forte(b: dict[str, Any]) -> bool:
        nome = str(b["nome"])
        return bool(cor_por_bairro) and nome in (cor_por_bairro or {}) and nome not in (cor_clara or set())

    # O contorno FORTE das partes vai por ultimo: a divisa que um bairro divide com o vizinho e'
    # desenhada duas vezes, e a cinza (ou a fina) do vizinho nao pode cobrir a da parte.
    for bairro in sorted(bairros, key=lambda b: (not b.get("sobra"), _contorno_forte(b))):
        sobra = bool(bairro.get("sobra"))
        realce = str(bairro["nome"]) in alvos
        da_parte = False
        if sobra:
            fill, traco, espessura = _SOBRA_FILL_RGBA, _SOBRA_CONTORNO_RGBA, 2
        elif choropleth:
            fill = _cor_do_bairro(bairro)
            # Contorno branco fino: na cor cheia, o vermelho brigaria com a paleta tematica.
            traco, espessura = (255, 255, 255, 190), 1
        elif apagados and str(bairro["nome"]) in apagados:
            fill, traco, espessura = _BAIRRO_APAGADO_FILL_RGBA, _BAIRRO_APAGADO_TRACO_RGBA, 1
        elif cor_por_bairro and str(bairro["nome"]) in cor_por_bairro:
            # Cor CHEIA da parte, com divisa branca fina entre os bairros: com alpha 70 e divisa na
            # propria cor as partes sumiam no fundo de ruas (SJC, 2026-10-22). `cor_clara` = bairro
            # da parte sem numero, num tom mais claro da mesma cor.
            cor = cor_por_bairro[str(bairro["nome"])]
            da_parte = True
            clara = bool(cor_clara) and str(bairro["nome"]) in (cor_clara or set())
            if so_contorno:
                # Paginas das partes (Juan, 2026-10-22): o bairro LIMITADO, nao pintado -- o
                # preenchimento fazia a pagina parecer mais um mapa tematico do motor e escondia
                # a divisa. Contorno forte na cor da parte; mais fino no bairro sem numero.
                fill = (*cor, 0)
                traco, espessura = ((*cor, 210), 2) if clara else ((*cor, 255), 4)
            elif clara:
                fill, traco, espessura = (*cor, 95), (*cor, 200), 1
            else:
                fill, traco, espessura = (*cor, 185), (255, 255, 255, 210), 1
        else:
            fill = _BAIRRO_DESTAQUE_FILL_RGBA if realce else _BAIRRO_FILL_RGBA
            traco, espessura = _BAIRRO_CONTORNO_RGBA, 2
        for anel in bairro["aneis"]:
            pixels = _pixels(anel)
            if len(pixels) < 3:
                continue
            if fill[3]:  # a sobra nao tem preenchimento: o fundo de ruas fica a vista
                (pdraw if da_parte else odraw).polygon(pixels, fill=fill)
            # Contorno em `line` (nao `polygon(outline=)`) porque so `line` aceita espessura.
            ldraw.line([*pixels, pixels[0]], fill=traco, width=espessura, joint="curve")
    for anel in contorno:
        pixels = _pixels(anel)
        if len(pixels) < 3:
            continue
        ldraw.line([*pixels, pixels[0]], fill=_MUNICIPIO_CONTORNO_RGBA, width=3, joint="curve")
    _compor_no_map_box(overlay)
    if cor_por_bairro:
        _compor_cor_cheia(camada_partes)
        _compor_no_map_box(camada_linhas)

    # Pins de Ultra/concorrentes: a pagina de Resumo perde o sentido sem eles ("espaco para
    # academias" e' leitura de quem JA esta la). Mesmo helper das camadas de hexagono, para o
    # marcador ser identico entre os mapas.
    _draw_pins(draw, image, competitors_df, project, "", minx, maxx, miny, maxy)
    _draw_pins(draw, image, ultra_df, project, "__ultra__", minx, maxx, miny, maxy)

    # Nenhum nome de bairro em placa desde 2026-10-20 (Juan): a Visao Geral e os Bairros Oficiais
    # ja' dizem onde cada bairro fica, e nos tematicos a placa so' cobria a cor. O que sobra e' o
    # NUMERO dos Bairros Oficiais (`numeros`), cujo nome esta' no indice da pagina.
    rotulos = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    rdraw = ImageDraw.Draw(rotulos, "RGBA")
    if numeros is not None:
        fonte_num = _font(13)
        for nome, n in numeros.items():
            xy = (pontos or {}).get(nome)
            if xy is None:
                continue
            px, py = project(*xy)
            if not (left <= px <= right and top <= py <= bottom):
                continue
            texto = str(n)
            tw = _text_width(rdraw, texto, fonte_num)
            r = max(11, tw // 2 + 5)
            rdraw.ellipse([px - r, py - r, px + r, py + r], fill=_BAIRRO_NUMERO_RGBA,
                          outline=(255, 255, 255, 255), width=2)
            _draw_text(rdraw, (int(round(px - tw / 2)), int(round(py - 8))), texto, font=fonte_num,
                       fill=(255, 255, 255))
        fonte_parte = _font(24)
        for mx, my, texto, cor in marcadores or []:
            px, py = project(mx, my)
            tw = _text_width(rdraw, texto, fonte_parte)
            r = max(22, tw // 2 + 10)
            rdraw.ellipse([px - r, py - r, px + r, py + r], fill=(*cor, 255),
                          outline=(255, 255, 255, 255), width=3)
            _draw_text(rdraw, (int(round(px - tw / 2)), int(round(py - 15))), texto, font=fonte_parte,
                       fill=(255, 255, 255))
    _compor_no_map_box(rotulos)

    if localizar:
        # Mini-mapa no canto: onde esta' esta parte no municipio.
        mw, mh = 170, 150
        x1, y1 = right - 10, top + 10
        x0 = x1 - mw
        mini = [b for b in bairros if not b.get("sobra")]
        bminx, bminy, bmaxx, bmaxy = _bbox_bairros(mini, pad_frac=0.04)
        esc = min((mw - 12) / max(bmaxx - bminx, 1.0), (mh - 12) / max(bmaxy - bminy, 1.0))
        ox = x0 + (mw - (bmaxx - bminx) * esc) / 2
        oy = y1 + (mh - (bmaxy - bminy) * esc) / 2

        def mproj(x: float, y: float) -> tuple[int, int]:
            return int(round(ox + (x - bminx) * esc)), int(round(oy + (bmaxy - y) * esc))

        draw.rectangle([x0, y1, x1, y1 + mh], fill=(255, 255, 255), outline=(150, 150, 150), width=2)
        cor_loc = next(iter(cor_por_bairro.values())) if cor_por_bairro else ULTRA_MAGENTA
        for b in mini:
            fill = (*cor_loc, 230) if str(b["nome"]) in localizar else (225, 227, 232, 255)
            for anel in b["aneis"]:
                pix = [mproj(x, y) for x, y in anel]
                if len(pix) >= 3:
                    draw.polygon(pix, fill=fill)
        for anel in contorno:
            pix = [mproj(x, y) for x, y in anel]
            if len(pix) >= 3:
                draw.line([*pix, pix[0]], fill=(17, 17, 17, 255), width=2)

    # Resposta unica (DEC-077): Visao Geral e Resumo nao medem "aprovacao" -- o rodape so' diz de
    # onde vem o bairro.
    sem_metrica = sem_aprovado and metrica in ("resumo", "cobertura")
    fonte_txt = (
        "Setores censitários {instituto} 2022 dissolvidos por bairro"
        if sem_metrica
        else _BAIRRO_METRICA_RODAPE.get(
            str(metrica), "Setores censitários {instituto} 2022 dissolvidos por bairro"
        )
    ).format(instituto=_instituto_censo())
    if _BAIRRO_METRICAS.get(str(metrica)) == "rateada" and not sem_metrica:
        # Nunca deixar uma estimativa passar por medicao: o hexagono e' MAIOR que a maioria dos
        # bairros, entao este numero desceu do hexagono, nao subiu do setor.
        fonte_txt += " (estimativa: hexágono rateado no bairro)"
    if any(b.get("sobra") for b in bairros):
        fonte_txt += " - sem cor, contorno cinza: sem bairro na base"
    if apagados:
        fonte_txt += " - em cinza, bairros das outras partes"
    rodape = (
        f"{fonte_txt} - EPSG:3857 - {_atribuicao_tiles()}"
        if drew_basemap
        else f"{fonte_txt} - fundo de ruas offline"
    )
    _rodape_do_mapa(draw, rodape, nota_pins, height=height, largura_max=width - 48)

    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _rodape_do_mapa(
    draw: ImageDraw.ImageDraw, texto: str, nota: str | None, *, height: int, largura_max: int
) -> None:
    """Rodape do PNG: a credito/procedencia na 1a linha e a nota das academias na 2a.

    Em duas linhas porque numa so' a nota estourava a largura do PNG e saia cortada no meio do
    nome da ultima rede (Sao Paulo, 2026-09-17). Nota que ainda nao caiba e' truncada com "...".
    """
    _draw_text(draw, (24, height - 40), texto, font=_font(11), fill=(71, 85, 105))
    if not nota:
        return
    fonte = _font(11)
    while nota and _text_width(draw, nota, fonte) > largura_max:
        nota = nota[:-1]
    _draw_text(draw, (24, height - 24), nota, font=fonte, fill=(71, 85, 105))


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
        size = _PIN_LOGO_PX
        if forced_key:
            key = forced_key
        else:
            key = _chave_rede(row.get("rede"))
            if not key:
                # DEC-046: linha sem `rede` e' academia INDEPENDENTE -> marcador do agregador,
                # menor que a bandeira de cadeia (mesmo ramo do `censo_map`, Pontual).
                # `[DEC-066]` A MARCA sai do app que a revelou: rosa no WellHub, verde no
                # TotalPass. MESMA funcao que o Pontual chama -- uma redacao da regra.
                key, size = (
                    chave_agregador_da_fonte(row.get("fonte"), row.get("fontes_da_academia")),
                    PIN_INDEPENDENTE_PX,
                )
        try:
            from typing import cast

            # BLK-RELPON-09: logo QUADRADA (sem balao/mascara circular), ancorada pelo
            # CENTRO do quadrado no ponto (S2b) -- o marcador nao tem ponta.
            tile = cast(Image.Image, _render_square_logo_tile(key, size))
            image.paste(tile, (int(px) - size // 2, int(py) - size // 2), tile)
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
    draw.text(xy, _texto_render(text), fill=fill, font=font or _font())


def _texto_render(text: str) -> str:
    """Excecao de RENDER (CLAUDE.md §2): texto de PNG sai sem acento. A fonte embutida do
    Pillow (12.3, a da imagem de producao) nao tem glifo acentuado e desenha um quadrado."""
    norm = unicodedata.normalize("NFKD", str(text))
    return "".join(ch for ch in norm if not unicodedata.combining(ch))


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), _texto_render(text), font=font)
    return int(bbox[2] - bbox[0])


#: Quantas redes concorrentes os mapas tematicos desenham. Em 2026-09-17 o Juan levou este numero
#: a ZERO: com as 5 maiores redes o mapa de Sao Paulo ainda saia com 370 pins (so' a Smart Fit tem
#: 171), e Resumo/Dominio existem para responder ONDE HA ESPACO. A concorrencia tem duas paginas
#: proprias (Pressao concorrencial e Espaco e academias) e os totais no painel ao lado.
#: `principais_redes` fica, e voltar a desenhar as N maiores e' mudar esta constante.
TOP_REDES_NO_MAPA = 0


def principais_redes(competitors_df: pd.DataFrame | None, n: int = TOP_REDES_NO_MAPA) -> list[str]:
    """As `n` redes com mais unidades no municipio, em ordem total (mais unidades, depois nome)."""
    if n <= 0 or competitors_df is None or competitors_df.empty or "rede" not in competitors_df.columns:
        return []
    rede = competitors_df["rede"].astype("string").str.strip()
    contagem = rede[rede.notna() & (rede != "")].value_counts()
    ordenado = sorted(((str(k), int(v)) for k, v in contagem.items()), key=lambda kv: (-kv[1], kv[0]))
    return [nome for nome, _ in ordenado[:n]]


def _so_as_principais(competitors_df: pd.DataFrame | None, redes: list[str]) -> pd.DataFrame | None:
    """Recorta os pins as `redes` dadas; independente (sem rede) fica fora do mapa tematico.

    Sem rede nenhuma para recortar (`redes` vazia, ex.: municipio so' com independentes) devolve
    o frame inteiro -- ai' nao ha o que poluir.
    """
    if competitors_df is None or competitors_df.empty or not redes or "rede" not in competitors_df.columns:
        return competitors_df
    return competitors_df.loc[competitors_df["rede"].astype("string").str.strip().isin(redes)]


def render_mapas_municipio(
    df_muni: pd.DataFrame,
    municipio_result: dict[str, Any],
    *,
    unidade: str = UNIDADE_BAIRRO,
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
    basemap: bool = False,
    width: int = 1000,
    height: int = 704,
    poligono_municipio: Any | None = None,
    hexes_rotulados: set[str] | None = None,
    hexes_top: set[str] | None = None,
) -> dict[str, bytes]:
    """Gera as camadas de mapa do relatorio (cobertura/resumo/score/residual/dominio).

    AJUSTE 1 (FU1): computa UM viewport de FOCO (regioes relevantes + pins) e o reutiliza nas
    camadas de FOCO (resumo/score/residual/dominio), para ficarem comparaveis/alinhadas e o
    miolo povoado preencher o quadro. Fallback gracioso: foco vazio -> `None` -> bbox de todos
    os hexes (comportamento anterior).

    FU1 (slide novo): a camada "cobertura" mostra o municipio INTEIRO (sem foco) com aprovados
    (destacados, verde) e reprovados (cinza), sem pins.

    BLK-RELMUN-05: os frames de pins sao RECORTADOS ao municipio aqui, uma vez, antes de
    qualquer render -- `_draw_pins` so filtrava pela bbox da imagem e por isso desenhava
    concorrentes dos municipios vizinhos. Recortar na entrada tambem conserta o viewport de
    foco, que passa a enquadrar so o que e do municipio.
    """
    zonas = municipio_result.get("zonas", [])
    # Resposta unica (DEC-077, Brasil): sem o mapa de Dominio (a pagina sai ate' chegarem os
    # dados do gestor) e sem foco nos aprovados/escolhidos na Visao Geral e no Resumo.
    resposta_unica = _resposta_unica(municipio_result)
    hexes_muni = _hexes_do_municipio(df_muni)
    competitors_df = filtrar_pins_do_municipio(
        competitors_df, hexes_muni=hexes_muni, poligono=poligono_municipio
    )
    ultra_df = filtrar_pins_do_municipio(
        ultra_df, hexes_muni=hexes_muni, poligono=poligono_municipio
    )
    focus_bounds = _focus_bounds_mercator(
        df_muni, competitors_df=competitors_df, ultra_df=ultra_df
    )
    # Resumo e Dominio fecham o quadro nos hexagonos escolhidos (zoom na melhor area); os demais
    # seguem com o foco de sempre, agora com menos margem em volta.
    foco_top = _focus_bounds_mercator(df_muni, hexes_foco=hexes_top) if hexes_top else None
    # Resumo: os escolhidos com margem folgada, SEM os pins no calculo (uma unidade Ultra num
    # hexagono afastado esticava o quadro). Sem `hexes_top`, cai nos aprovados.
    foco_resumo = (
        _focus_bounds_mercator(df_muni, hexes_foco=hexes_top, pad_frac=_FOCUS_PAD_FRAC_RESUMO)
        if hexes_top
        else _focus_bounds_mercator(df_muni, pad_frac=_FOCUS_PAD_FRAC_RESUMO)
    ) or focus_bounds
    if resposta_unica:
        # Sem escolhidos: o Resumo enquadra como Score e Residual (Juan, 2026-10-22).
        foco_resumo = focus_bounds
    # Mapas tematicos: so' a Ultra e as maiores redes. A contagem cheia (inclusive independentes)
    # segue nos numeros das paginas e na Pressao concorrencial, que e' onde a oferta e' o assunto.
    redes_principais = principais_redes(competitors_df)
    comp_principais = _so_as_principais(competitors_df, redes_principais) if redes_principais else None
    n_conc = 0 if competitors_df is None else len(competitors_df)
    nota_pins: str | None
    if redes_principais:
        nota_pins = (
            f"no mapa, Ultra e as {len(redes_principais)} maiores redes "
            f"({', '.join(_prettify_rede(r) for r in redes_principais)})"
        )
    else:
        # Declara a ausencia: mapa sem concorrente nenhum desenhado parece cidade sem concorrencia.
        nota_pins = (
            f"no mapa, só as unidades Ultra; as {_format_number(n_conc, 0)} concorrentes estão em "
            "Pressão concorrencial e Espaço e academias"
            if n_conc
            else None
        )
    # Score e residual SEM pins (Juan, 2026-09-17): em capital as logos cobriam os hexagonos --
    # Sao Paulo tem 491 academias. Mesma regra que a versao por bairro ja seguia; quem esta
    # instalado aparece em Resumo, Dominio, Pressao concorrencial e Espaco e academias.
    pins_por_camada = {"resumo": True, "score": False, "residual": False, "dominio": True}
    if resposta_unica:
        del pins_por_camada["dominio"]
    mapas = {
        camada: _render_mapa_municipio(
            df_muni,
            camada=camada,
            municipio_result=municipio_result,
            zonas=zonas,
            competitors_df=comp_principais if pins else None,
            ultra_df=ultra_df if pins else None,
            basemap=basemap,
            width=width,
            height=height,
            focus_bounds=(
                foco_resumo
                if camada == "resumo"
                else (foco_top or focus_bounds) if camada == "dominio" else focus_bounds
            ),
            hexes_rotulados=hexes_rotulados,
            hexes_top=hexes_top if camada == "dominio" else None,
            nota_pins=nota_pins if pins else None,
            rotular_valores=False,
        )
        for camada, pins in pins_por_camada.items()
    }

    # Camada "cobertura", sem pins (leitura limpa). O quadro fecha nos hexagonos APROVADOS em
    # verde (Juan, 2026-10-20): zoom maximo sem cortar nenhum. O aprovado por fallback municipal
    # sai cinza no mapa, entao nao entra no enquadramento. Sem verde, o municipio inteiro.
    # No Brasil (resposta unica) a pagina da Visao Geral saiu (Juan, 2026-10-22): o mapa nao e'
    # desenhado -- seria um fundo de ruas baixado a toa.
    if not resposta_unica:
        verdes = (
            df_muni.loc[_hex_destacado_mask(df_muni) & _fonte_propria_mask(df_muni), "hex_id"]
            if "hex_id" in df_muni.columns else pd.Series(dtype=object)
        )
        mapas["cobertura"] = _render_mapa_municipio(
            df_muni,
            camada="cobertura",
            municipio_result=municipio_result,
            competitors_df=None,
            ultra_df=None,
            basemap=basemap,
            width=width,
            height=height,
            focus_bounds=(
                _focus_bounds_mercator(
                    df_muni, hexes_foco={str(h) for h in verdes.dropna()},
                    pad_frac=_FOCUS_PAD_FRAC_COBERTURA,
                )
                if not verdes.dropna().empty else None
            ),
            hexes_rotulados=hexes_rotulados,
        )

    # Camada "espaco" (2026-10-20): por HEXAGONO de proposito, nos dois modos -- e' o grao em que
    # o espaco e' calculado; repartir por bairro perdia 19 academias em Sao Paulo (hexagono de
    # borda) e punha numero em bairro cinza.
    aprovados = (
        df_muni.loc[_hex_destacado_mask(df_muni), "hex_id"]
        if "hex_id" in df_muni.columns else pd.Series(dtype=object)
    )
    # Os numeros saem como texto do PDF (nitidos), nao no PNG: a pagina os le daqui.
    rotulos_espaco: list[tuple[float, float, str]] = []
    municipio_result["espaco_rotulos"] = {"tamanho_px": (width, height), "pontos": rotulos_espaco}
    mapas["espaco"] = _render_mapa_municipio(
        df_muni,
        camada="espaco",
        municipio_result=municipio_result,
        basemap=basemap,
        width=width,
        height=height,
        rotulos_out=rotulos_espaco,
        focus_bounds=(
            _focus_bounds_mercator(
                df_muni, hexes_foco={str(h) for h in aprovados.dropna()}, pad_frac=_FOCUS_PAD_FRAC_COBERTURA,
            )
            if not aprovados.dropna().empty else None
        ),
    )

    # Camada "bairros" (BLK-RELMUN-06): divisa territorial real, municipio INTEIRO. Nao usa
    # `focus_bounds` (que enquadra hexes relevantes) de proposito -- o slide serve para situar o
    # municipio todo, inclusive a parte rural que fica fora do recorte de oportunidade.
    bairros_geo = municipio_result.get("bairros_geo") or {}
    # Desde 2026-10-20 os bairros saem NUMERADOS e, quando nao cabem num quadro so', repartidos:
    # "bairros" vira a visao geral das partes e cada parte ganha "bairros_parte_<k>" (zoom so'
    # nela). A pagina refaz a mesma divisao (`dividir_bairros_em_partes` e' pura) para o indice.
    divisao = dividir_bairros_em_partes(bairros_geo)
    if divisao is None:
        mapas["bairros"] = _render_mapa_bairros(
            bairros_geo, basemap=basemap, width=width, height=height,
        )
    elif len(divisao["partes"]) == 1 and not divisao["avulsos"]:
        mapas["bairros"] = _render_mapa_bairros(
            bairros_geo, basemap=basemap, width=width, height=height,
            numeros=divisao["numero"], pontos=divisao["ponto"], apagados=set(divisao["fora"]),
        )
    else:
        # O municipio INTEIRO nas cores das partes (2026-10-22, Juan): cada bairro sem numero vai
        # na cor da parte mais proxima (`parte_de`). Antes so' os numerados tinham cor e o resto
        # saia em cinza -- em Sao Jose dos Campos, 84% da area e metade da populacao.
        cor_de = {
            nome: _PARTE_CORES[k % len(_PARTE_CORES)] for nome, k in divisao["parte_de"].items()
        }
        marcadores = []
        for k, parte in enumerate(divisao["partes"]):
            xs = [divisao["ponto"][n][0] for n in parte]
            ys = [divisao["ponto"][n][1] for n in parte]
            marcadores.append((sum(xs) / len(xs), sum(ys) / len(ys), str(k + 1),
                               _PARTE_CORES[k % len(_PARTE_CORES)]))
        mapas["bairros"] = _render_mapa_bairros(
            bairros_geo, basemap=basemap, width=width, height=height,
            numeros={n: divisao["numero"][n] for n in divisao["avulsos"]}, pontos=divisao["ponto"],
            cor_por_bairro=cor_de, marcadores=marcadores,
            apagados=set(divisao["fora"]) - set(divisao["parte_de"]),
            # Os numerados na cor cheia e os demais no tom claro: a zona rural (em SJC, Sao
            # Francisco Xavier sozinho tem 357 km2) nao pode pesar mais que a cidade no slide.
            cor_clara=set(divisao["fora"]),
        )
        por_nome = {str(b["nome"]): b for b in bairros_geo["bairros"] if not b.get("sobra")}
        for k, parte in enumerate(divisao["partes"]):
            # A parte inteira (numerados + os sem numero que caem nela) em cor; o zoom segue so'
            # nos numerados, para a zona rural da parte nao afastar o quadro.
            nomes = {n for n, kk in divisao["parte_de"].items() if kk == k}
            minx, miny, maxx, maxy = _bbox_bairros([por_nome[n] for n in parte], pad_frac=0.06)
            mapas[f"bairros_parte_{k + 1}"] = _render_mapa_bairros(
                bairros_geo, titulo=f"Bairros oficiais - parte {k + 1}",
                bounds=(minx, miny, maxx, maxy), basemap=basemap, width=width, height=height,
                numeros={n: divisao["numero"][n] for n in parte}, pontos=divisao["ponto"],
                apagados=set(por_nome) - nomes,
                cor_por_bairro={n: _PARTE_CORES[k % len(_PARTE_CORES)] for n in nomes},
                cor_clara=nomes - set(parte),
                localizar=nomes,
                so_contorno=True,
            )
    # Metricas de mercado no bairro ANTES do corte por unidade: a tabela de bairros aprovados da
    # Visao Geral (`bairros_aprovados`) le o `destacado` do bairro tambem no modo hexagono.
    if tem_bairro_real(bairros_geo):
        aplicar_metricas_hex_nos_bairros(
            bairros_geo, df_muni, hex_zona_geo=municipio_result.get("hex_zona_geo") or {},
            renda_domiciliar_por_hex=municipio_result.get("renda_domiciliar_por_hex"),
        )
    if unidade == UNIDADE_HEXAGONO:
        # Modo hexagono: so a divisa dos bairros (pagina Bairros Oficiais, igual no motor e no
        # bot); sem nucleo urbano, e os choropleths acima seguem por hexagono.
        return mapas

    # O recorte do nucleo urbano (BLK-RELMUN-11) segue enquadrando os tematicos por bairro; a
    # pagina propria dele ("Bairros - Nucleo Urbano") saiu em 2026-10-20 (Juan): repetia o mapa
    # de score da pagina seguinte.
    bounds_urbano = bounds_nucleo_urbano(bairros_geo)

    # BLK-RELMUN-09/10: TODAS as camadas tematicas passam a ser desenhadas POR BAIRRO.
    #
    # A procedencia difere e esta declarada no rodape de cada mapa: `score` SOBE do setor
    # (agregacao exata), enquanto residual/resumo/cobertura/dominio DESCEM do hexagono
    # (reparticao por populacao) -- o hexagono res-7 e' maior que 86% dos bairros de Novo
    # Hamburgo, entao esses quatro sao estimativa, nao medicao. Decisao do usuario (2026-08-14)
    # apos a alternativa conservadora ter sido apresentada e reconsiderada.
    #
    # Fallback: SO municipio sem bairro real na base mantem os choropleths de hexagono.
    #
    # O corte por COBERTURA (<50% voltava ao hexagono, caso Campinas) foi REVERTIDO em
    # 2026-08-19 a pedido de Juan, depois de ver Sinop/MT: "so vistas de bairros sem
    # hexagonos". O que protege a leitura em cobertura baixa passou a ser o RECORTE URBANO
    # abaixo, nao a troca de unidade -- e a pagina de Bairros Oficiais segue declarando a
    # cobertura real. Consequencia aceita: em Campinas/SP (31%, distritos so na periferia) o
    # miolo urbano aparece sem cor, com contorno cinza, "sem bairro na base" dentro do recorte.
    if tem_bairro_real(bairros_geo):
        for camada, titulo, com_pins in (
            ("score", "Score censitário por bairro", False),
            ("residual", "Residual fitness por bairro", False),
            ("resumo", "Resumo da região por bairro", True),
            # "cobertura" e' a visao geral limpa (sem pins), como na versao de hexagono.
            ("cobertura", "Visão geral do município por bairro", False),
            ("dominio", "Expansão de domínio por bairro", True),
        ):
            if resposta_unica and camada in ("dominio", "cobertura"):
                # Brasil: as paginas de Dominio e da Visao Geral nao saem.
                continue
            mapas[camada] = _render_mapa_bairros(
                bairros_geo,
                titulo=titulo,
                metrica=camada,
                sem_aprovado=resposta_unica,
                # Mesmo recorte urbano da pagina 4. Sem ele, um distrito rural extenso domina
                # o quadro e espreme a cidade a ponto de nao dar para ler onde ha espaco --
                # Juan viu isso na Expansao de Dominio de Tangara da Serra/MT. E' o analogo do
                # `focus_bounds` que as camadas de HEXAGONO ja usavam; era a paridade que
                # faltava. A pagina 3 (municipio inteiro) segue sem recorte, de proposito.
                # A Visao Geral fecha nos bairros APROVADOS (Juan, 2026-10-20): zoom maximo sem
                # cortar nenhum verde. Sem aprovado, o recorte urbano de sempre.
                bounds=(
                    _bounds_bairros_aprovados(bairros_geo) or bounds_urbano
                    if camada == "cobertura" and not resposta_unica else bounds_urbano
                ),
                competitors_df=comp_principais if com_pins else None,
                ultra_df=ultra_df if com_pins else None,
                nota_pins=nota_pins if com_pins else None,
                basemap=basemap,
                width=width,
                height=height,
            )
    return mapas


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


def _fit_contain(
    img_w: float, img_h: float, max_w: float, max_h: float,
    *, x_anchor: float = 0.0, y_anchor: float = 0.0,
) -> tuple[float, float, float, float]:
    """Encaixe CONTAIN (scale=min) de uma imagem `img_w x img_h` no retangulo `max_w x max_h`,
    centralizado a partir de (x_anchor, y_anchor). Funcao PURA (sem I/O de PDF), extraida de
    `_draw_map` byte-a-byte para tornar a ausencia de letterbox testavel deterministicamente.

    Retorna `(draw_w, draw_h, x, y)`. Quando o aspect da imagem casa o do retangulo, a sobra em
    ambos os eixos tende a zero (sem barra cinza). READ-ONLY sobre o M1 (so geometria de render).
    """
    scale = min(max_w / img_w, max_h / img_h)
    draw_w = img_w * scale
    draw_h = img_h * scale
    x = x_anchor + (max_w - draw_w) / 2.0
    y = y_anchor + (max_h - draw_h) / 2.0
    return draw_w, draw_h, x, y


def _draw_map(pdf: _UltraPDF, png_bytes: bytes | None, *, max_w: float = 540.0, max_h: float = 380.0,
              x_anchor: float = 36.0, y_anchor: float = 70.0) -> None:
    if not png_bytes:
        pdf.set_text_color(*_CINZA_TEXTO)
        pdf.set_font("Helvetica", "", 12)
        pdf.set_xy(x_anchor, y_anchor + 40)
        pdf.cell(max_w, 18, _ascii("Mapa indisponível para esta camada."))
        return
    dims = _png_dimensions(png_bytes)
    if dims is None:
        return
    img_w, img_h = dims
    draw_w, draw_h, x, y = _fit_contain(
        img_w, img_h, max_w, max_h, x_anchor=x_anchor, y_anchor=y_anchor
    )
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


def _watermark_text(solicitante: str | None, report_id: str | None = None) -> str:
    """Delega ao texto COMPARTILHADO de `pdf_base` (10/09, D17).

    So' o TEXTO -- o `_draw_watermark` acima fica como esta', porque ele e' o desenho e
    mexer nele mexeria nos bytes de um gerador em producao com teste de regressao.

    Duas coisas mudam de comportamento, e as duas sao consertos: o `report_id` passa a
    caber, e o solicitante passa por `nome_exibicao` -- antes era `strip()` cru, entao
    "felipe_castaldi" saia com o underscore no PDF enquanto o Pontual ja' escrevia
    "Felipe Castaldi" para a MESMA pessoa.
    """
    return pdf_base.texto_da_marca(solicitante, report_id)


def _local_label(result: dict[str, Any]) -> str:
    municipio = str(result.get("nome_municipio") or "").strip()
    uf = str(result.get("uf") or "").strip()
    return f"{municipio} - {uf}".strip(" -") if (municipio or uf) else "Município"


# ===========================================================================
# Paginas do PDF (8)
# ===========================================================================


# Ciclo canonico de cores das molduras (FU1, AJUSTE 1): cada bloco de uma pagina recebe
# uma cor distinta do contorno, ciclando turquesa -> magenta -> laranja.
_FRAME_CICLO = (ULTRA_TURQUESA, ULTRA_MAGENTA, ULTRA_LARANJA)


def _ciclo_cor(idx: int) -> tuple[int, int, int]:
    """Cor da moldura do bloco `idx` da pagina, ciclando turquesa -> magenta -> laranja."""
    return _FRAME_CICLO[idx % len(_FRAME_CICLO)]


def _tema_bicolor(ordinal: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """(primary, secondary) por pagina de CONTEUDO (ordinal >= 1), alternando o tom principal.

    Pedido Vinicius (2026-06-29): as paginas alternam entre turquesa e magenta como cor
    principal. Pagina impar -> turquesa primaria / magenta acento; par -> magenta primaria /
    turquesa acento. Aplica-se SO ao chrome decorativo da pagina (faixa de titulo, moldura do
    mapa e painel/cabecalho decorativo principal). Cores SEMANTICAS (zonas, faixas de score,
    Ultra=turquesa / concorrente=magenta, laranja como 3o tom dos cards) NAO entram na troca.
    READ-ONLY sobre o M1.
    """
    if ordinal % 2 == 1:
        return ULTRA_TURQUESA, ULTRA_MAGENTA
    return ULTRA_MAGENTA, ULTRA_TURQUESA


def _rounded_panel(
    pdf: _UltraPDF,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    radius: float = 12.0,
    fill: tuple[int, int, int] | None = _BRANCO,
    border_rgb: tuple[int, int, int] = ULTRA_TURQUESA,
    border_w: float = 1.1,
) -> None:
    """Moldura Ultra Clean: retangulo de cantos arredondados com CONTORNO COLORIDO inteiro
    (AJUSTE 1, FU1). A cor da borda (`border_rgb`) e uma das 3 cores principais e VARIA entre
    os blocos da mesma pagina (ciclo via `_ciclo_cor`). Corpo branco/gelo por dentro.

    Sem barra/acento tricolor: a propria borda inteira leva a cor do bloco.
    """
    if fill is not None:
        pdf.set_fill_color(*fill)
        pdf.rect(x, y, w, h, style="F", round_corners=True, corner_radius=radius)
    prev_line_w = pdf.line_width
    pdf.set_line_width(border_w)
    pdf.set_draw_color(*border_rgb)
    pdf.rect(x, y, w, h, style="D", round_corners=True, corner_radius=radius)
    pdf.set_line_width(prev_line_w)


# Area de conteudo abaixo da faixa de titulo (band_h=56) ate acima do rodape.
_CONTENT_TOP = 70.0
_CONTENT_BOTTOM = 512.0


def _centered_y(block_h: float, *, top: float = _CONTENT_TOP, bottom: float = _CONTENT_BOTTOM) -> float:
    """Y inicial p/ centralizar verticalmente um bloco de altura `block_h` na area de conteudo."""
    y = top + ((bottom - top) - block_h) / 2.0
    return max(top, y)


def _draw_framed_map(
    pdf: _UltraPDF, png_bytes: bytes | None, *, max_w: float, max_h: float,
    x_anchor: float, y_anchor: float,
    border_rgb: tuple[int, int, int] = ULTRA_TURQUESA,
) -> None:
    """Mapa com moldura Ultra Clean (cantos arredondados + contorno colorido) ao redor."""
    pad = 10.0
    _rounded_panel(
        pdf, x_anchor - pad, y_anchor - pad, max_w + 2 * pad, max_h + 2 * pad,
        border_rgb=border_rgb,
    )
    _draw_map(pdf, png_bytes, max_w=max_w, max_h=max_h, x_anchor=x_anchor, y_anchor=y_anchor)


def _draw_rede_logo(pdf: _UltraPDF, rede: str, x: float, y: float, size: float = 14.0) -> bool:
    """Slide 8: desenha a logo QUADRADA da rede (`competitors._render_square_logo_tile`) em (x,y).

    BLK-RELPON-09: era `_render_pin_tile(...).crop((37,20,91,74))` -- recorte acoplado a
    geometria do balao. Agora a logo ja vem quadrada; sem borda/sombra (a pagina do PDF e
    branca, keyline e sombra ficariam sujeira). `size` continua em PONTOS do PDF (14 pt),
    inalterado; `_REDE_LOGO_RASTER_PX` e so a resolucao do raster embutido.
    Fallback gracioso: sem tile/erro -> retorna False (o chamador mantem so o bullet/nome).
    """
    try:
        from typing import cast

        tile = cast(
            Image.Image,
            _render_square_logo_tile(str(rede), _REDE_LOGO_RASTER_PX, border=False, shadow=False),
        )
        buf = BytesIO()
        tile.convert("RGBA").save(buf, format="PNG")
        buf.seek(0)
        pdf.image(buf, x=x, y=y, w=size, h=size)
        return True
    except Exception:
        return False


_NOTA_LINHA_H = 11.0


def _draw_note(pdf: _UltraPDF, x: float, y: float, w: float, text: str) -> None:
    """Nota curta em cinza pequeno (legenda de calculo), sem poluir."""
    pdf.set_text_color(120, 120, 120)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_xy(x, y)
    pdf.multi_cell(w, _NOTA_LINHA_H, _ascii(text))


def _altura_note(pdf: _UltraPDF, w: float, text: str) -> float:
    """Altura (pt) que `_draw_note` ocuparia, medida pelo `dry_run` do fpdf2 na MESMA fonte."""
    pdf.set_font("Helvetica", "", 8)
    linhas = pdf.multi_cell(w, _NOTA_LINHA_H, _ascii(text), dry_run=True, output="LINES")
    assert isinstance(linhas, list)  # output="LINES" devolve a lista de linhas
    return len(linhas) * _NOTA_LINHA_H


def _encurtar(pdf: _UltraPDF, texto: str, largura: float) -> str:
    """Trunca `texto` com reticencias ate caber em `largura` pt na fonte ATUAL do `pdf`.

    Mede com `get_string_width` em vez de contar caracteres: "MMM" e "iii" tem a mesma
    contagem e larguras muito diferentes, e um corte por contagem erra nos dois sentidos
    (trunca cedo demais ou deixa transbordar).
    """
    texto = _ascii(texto)
    reticencias = "..."
    if largura <= 0:
        # Largura degenerada: devolver o texto inteiro seria o oposto do pedido.
        return reticencias
    if pdf.get_string_width(texto) <= largura:
        return texto
    disponivel = largura - pdf.get_string_width(reticencias)
    if disponivel <= 0:
        return reticencias
    corte = texto
    while corte and pdf.get_string_width(corte) > disponivel:
        corte = corte[:-1]
    return (corte.rstrip() + reticencias) if corte else reticencias


def _info_panel(pdf: _UltraPDF, x: float, y: float, w: float, titulo: str,
                linhas: list[tuple[str, str]], *, accent: tuple[int, int, int] = ULTRA_TURQUESA,
                border_rgb: tuple[int, int, int] | None = None,
                subtitulos: dict[str, str] | None = None) -> float:
    """Painel lateral "rotulo | valor". Retorna o y final.

    `subtitulos` (rotulo -> texto) poe uma linha miuda embaixo do rotulo, e a linha ganha altura.

    `border_rgb` (AJUSTE 1) define o contorno colorido do bloco; default = `accent`.
    """
    row_h = 26.0
    sub = dict(subtitulos or {})
    extra_h = 12.0
    panel_h = 36.0 + len(linhas) * row_h + extra_h * sum(1 for r, _v in linhas if r in sub) + 12.0
    _rounded_panel(pdf, x, y, w, panel_h, border_rgb=border_rgb if border_rgb is not None else accent)
    pdf.set_text_color(*accent)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(x + 14, y + 16)
    pdf.cell(w - 28, 16, _ascii(titulo))
    pdf.set_font("Helvetica", "", 12)
    yy = y + 42
    rotulo_w = (w - 28) * 0.62
    for rotulo, valor in linhas:
        pdf.set_text_color(45, 45, 45)
        pdf.set_xy(x + 14, yy)
        # `cell` NAO corta texto largo demais: ele transborda por cima da coluna do valor.
        # Visto em Goiania/GO, onde a localidade do IBGE e' uma U.T.P. de nome longo
        # ("U.T.P. Parque das Laranjeiras e Jardim da Luz") e o numero saiu grudado nela.
        pdf.cell(rotulo_w, 16, _ascii(_encurtar(pdf, rotulo, rotulo_w - 6)))
        pdf.set_text_color(40, 40, 40)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_xy(x + 14 + (w - 28) * 0.62, yy)
        pdf.cell((w - 28) * 0.38, 16, _ascii(valor), align="R")
        pdf.set_font("Helvetica", "", 12)
        if rotulo in sub:
            pdf.set_text_color(*_CINZA_TEXTO)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_xy(x + 14, yy + 16)
            pdf.cell(w - 28, 11, _ascii(sub[rotulo]))
            pdf.set_font("Helvetica", "", 12)
            yy += extra_h
        yy += row_h
    return y + panel_h


def _cover_page(pdf: _UltraPDF, result: dict[str, Any], assets: dict[str, bytes | None]) -> None:
    pdf.add_page()
    has_bg = assets.get("capa") is not None
    _draw_full_page_background(pdf, assets.get("capa"), _NAVY_CAPA)
    if has_bg:
        block_x, block_w, align = 478.0, 446.0, "L"
        # Subtitulo/rotulo permanecem nas posicoes absolutas de antes (NAO mexer):
        subtitle_y = 396.0  # antigo title_y(300)+96
        label_y = 442.0     # antigo title_y(300)+142
        # FU1: eyebrow + titulo descem para o centro vertical da faixa ENTRE a logo
        # (terco superior/medio) e o subtitulo, sem sobrepor a logo.
        eyebrow_y, title_y = 330.0, 356.0
    else:
        block_x, block_w, align = 60.0, _PAGE_W - 120, "C"
        subtitle_y, label_y = 286.0, 332.0
        eyebrow_y, title_y = 190.0, 216.0
    pdf.set_text_color(*_BRANCO)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(block_x, eyebrow_y)
    pdf.cell(block_w, 16, _ascii("ANÁLISE DE EXPANSÃO"), align=align)
    # Titulo em UMA linha (cell, nao multi_cell) p/ a string canonica aparecer contigua nos
    # bytes crus do PDF (compressao OFF). Fonte ajustada ao bloco; quebra visual em duas
    # linhas via subtitulo curto abaixo, mantendo a hierarquia do template.
    pdf.set_font("Helvetica", "B", 24 if has_bg else 30)
    pdf.set_xy(block_x, title_y)
    pdf.cell(block_w, 36, _ascii("Potencial de Entrada de Novas Unidades"), align=align)
    pdf.set_font("Helvetica", "", 13)
    pdf.set_xy(block_x, subtitle_y)
    # No Brasil (DEC-077) o Espaco e' leitura de capacidade, nao vaga para novas academias (item 4
    # do Felipe): a capa diz o mesmo que as paginas.
    subtitulo = ("Mapeamento competitivo por região - Ultra, concorrência e capacidade não atendida"
                 if _resposta_unica(result)
                 else "Mapeamento competitivo por região - Ultra e espaço disponível para novas academias")
    pdf.multi_cell(block_w, 18, _ascii(subtitulo), align=align)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_xy(block_x, label_y)
    pdf.cell(block_w, 20, _ascii(_local_label(result)), align=align)


def _cobertura_page(pdf: _UltraPDF, result: dict[str, Any], mapa: bytes | None,
                    assets: dict[str, bytes | None], *,
                    primary: tuple[int, int, int] = ULTRA_TURQUESA,
                    secondary: tuple[int, int, int] = ULTRA_MAGENTA) -> None:
    """Slide novo (FU1), logo apos a capa: visao geral do municipio inteiro com aprovados/
    reprovados/fora-do-municipio + bloco "REGIOES CONSIDERADAS" (quantas entram nas paginas
    seguintes e quantas ficaram de fora). READ-ONLY sobre o M1."""
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, f"Visão Geral do Município - {_local_label(result)}", rgb=primary)
    if _resposta_unica(result):
        # DEC-077 (Brasil): sem aprovados, sem a tabela e sem contagem -- so' o municipio, no
        # centro (Juan, 2026-10-22: "mapa da cidade sem verde e sem tabela").
        _draw_framed_map(pdf, mapa, max_w=540.0, max_h=380.0, x_anchor=(_PAGE_W - 540.0) / 2.0,
                         y_anchor=100.0, border_rgb=primary)
        return
    _draw_framed_map(pdf, mapa, max_w=540.0, max_h=380.0, x_anchor=34.0, y_anchor=100.0,
                     border_rgb=primary)

    n_aprov = int(result.get("n_aprovados", 0) or 0)
    n_muni = int(result.get("n_hex_municipio", 0) or 0)
    n_reprov = int(result.get("n_reprovados", 0) or 0)

    px = 610.0
    pw = _PAGE_W - px - 36.0
    nota = (
        f"As páginas seguintes consideram apenas as {_format_number(n_aprov, 0)} regiões aprovadas "
        f"(Residual Fitness >= {_format_number(OFERTA_DESTAQUE_MIN, 0)} alunos)."
    )
    # Com bairro na base, a coluna da direita e' a LISTA dos bairros aprovados (Juan, 2026-10-20):
    # o mapa perdeu os nomes e a legenda, e a tabela diz quais sao os verdes. Sem bairro, os
    # paineis de contagem de antes.
    aprovados = bairros_aprovados(result.get("bairros_geo"))
    if aprovados is not None:
        pop = {str(b["nome"]): _safe_float(b.get("pop"))
               for b in (result.get("bairros_geo") or {}).get("bairros") or []}
        # Mesma altura da moldura do mapa (y_anchor 100 - pad 10, 380 + 2 * pad).
        _tabela_bairros_aprovados(pdf, aprovados, px, 90.0, pw, 400.0, cor=secondary, pop=pop)
        _draw_note(pdf, 34.0, 490.0, 540.0, nota)
        return

    head_h = 100.0
    panel_h = 36.0 + 3 * 26.0 + 12.0
    bloco_h = head_h + 12.0 + panel_h
    py0 = _centered_y(bloco_h)

    # Headline: o NUMERO de regioes consideradas casa com a cor do CONTORNO do bloco (acento).
    cor_bloco = secondary
    _rounded_panel(pdf, px, py0, pw, head_h, border_rgb=cor_bloco)
    pdf.set_text_color(*cor_bloco)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(px + 14, py0 + 12)
    pdf.cell(pw - 28, 14, _ascii("REGIÕES CONSIDERADAS"))
    pdf.set_text_color(*cor_bloco)
    pdf.set_font("Helvetica", "B", 40)
    pdf.set_xy(px + 14, py0 + 32)
    pdf.cell(pw - 28, 44, _ascii(_format_number(n_aprov, 0)))
    pdf.set_text_color(45, 45, 45)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_xy(px + 14, py0 + 80)
    pdf.cell(pw - 28, 14, _ascii("regiões consideradas nas páginas seguintes"))

    # Detalhamento: total no municipio, aprovados, reprovados (fora do recorte).
    _info_panel(
        pdf, px, py0 + head_h + 12, pw, "DETALHAMENTO",
        [
            ("Hexágonos no município", _format_number(n_muni, 0)),
            ("Aprovados (considerados)", _format_number(n_aprov, 0)),
            ("Reprovados (fora do recorte)", _format_number(n_reprov, 0)),
        ],
        accent=ULTRA_LARANJA, border_rgb=_ciclo_cor(2),
    )

    _draw_note(pdf, 34.0, 490.0, 540.0, nota)


def _tabela_bairros_aprovados(pdf: _UltraPDF, nomes: list[str], x: float, y: float, w: float,
                              h: float, *, cor: tuple[int, int, int],
                              pop: dict[str, float] | None = None) -> None:
    """Painel "BAIRROS APROVADOS" com os nomes em colunas, de cima para baixo.

    Colunas e fonte se ajustam a quantidade; o que ainda nao couber vira "+ N outros" na ultima
    linha -- nunca some em silencio. Com o CNEFE (DEC-076) sao centenas (Sao Jose dos Campos: 168),
    entao desde 2026-10-21 entram so' os `_BAIRROS_APROVADOS_LISTADOS_MAX` mais populosos (por
    `pop`), ainda em ordem alfabetica, e o titulo segue com o total.
    """
    total = len(nomes)
    cortado = pop is not None and total > _BAIRROS_APROVADOS_LISTADOS_MAX
    if cortado:
        pesos = pop or {}
        maiores = set(sorted(nomes, key=lambda n: (-pesos.get(n, 0.0), n))[:_BAIRROS_APROVADOS_LISTADOS_MAX])
        nomes = [*[n for n in nomes if n in maiores], f"+ {total - len(maiores)} outros"]
    _rounded_panel(pdf, x, y, w, h, border_rgb=cor)
    pdf.set_text_color(*cor)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(x + 14, y + 12)
    pdf.cell(w - 28, 14, _ascii(f"BAIRROS APROVADOS ({_format_number(total, 0)})"))
    if cortado:
        pdf.set_text_color(*_CINZA_TEXTO)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_xy(x + 14, y + 26)
        pdf.cell(w - 28, 10, _ascii(f"os {len(nomes) - 1} mais populosos"))
    topo = y + 36.0
    util_h = h - (topo - y) - 12.0
    if not nomes:
        pdf.set_text_color(*_CINZA_TEXTO)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_xy(x + 14, topo)
        pdf.multi_cell(w - 28, 14, _ascii("Nenhum bairro tem a maioria da população em região aprovada."))
        return
    # Ate' os 60 (+ "outros") em DUAS colunas: os nomes do CNEFE sao longos ("Conjunto Residencial
    # ...") e em tres colunas saiam cortados (2026-10-21).
    n_col = 1 if len(nomes) <= 18 else (2 if len(nomes) <= _BAIRROS_APROVADOS_LISTADOS_MAX + 1 else 3)
    linhas = math.ceil(len(nomes) / n_col)
    linha_h = max(9.0, min(18.0, util_h / linhas))
    # `+ 1e-6`: com linha_h = util_h / linhas exato, o `//` em float dava uma linha a menos e
    # cortava o ultimo nome que cabia.
    linhas_que_cabem = int(util_h / linha_h + 1e-6)
    cabem = linhas_que_cabem * n_col
    if len(nomes) > cabem:
        nomes = [*nomes[: cabem - 1], f"+ {total - cabem + 1} outros"]
        linhas = linhas_que_cabem
    else:
        linhas = math.ceil(len(nomes) / n_col)
    col_w = (w - 28) / n_col
    pdf.set_text_color(45, 45, 45)
    pdf.set_font("Helvetica", "", max(7.0, min(11.0, linha_h * 0.62)))
    for i, nome in enumerate(nomes):
        col, lin = divmod(i, linhas)
        pdf.set_xy(x + 14 + col * col_w, topo + lin * linha_h)
        pdf.cell(col_w - 4, linha_h, _ascii(_encurtar(pdf, nome, col_w - 6)))


def _resumo_page(pdf: _UltraPDF, result: dict[str, Any], mapa: bytes | None,
                 assets: dict[str, bytes | None], *,
                 primary: tuple[int, int, int] = ULTRA_TURQUESA,
                 secondary: tuple[int, int, int] = ULTRA_MAGENTA) -> None:
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, f"Resumo da Região - {_local_label(result)}", rgb=primary)
    # Moldura do mapa acompanha o tom principal da pagina.
    _draw_framed_map(pdf, mapa, max_w=540.0, max_h=380.0, x_anchor=34.0, y_anchor=100.0,
                     border_rgb=primary)

    px = 610.0
    pw = _PAGE_W - px - 36.0
    # FU1: centraliza verticalmente o bloco (painel + box "Como calculamos").
    panel_h = 36.0 + 3 * 26.0 + 12.0
    box_h = 110.0
    bloco_h = panel_h + 12.0 + box_h
    py0 = _centered_y(bloco_h)
    y_end = _info_panel(
        pdf, px, py0, pw, "RESUMO DA REGIÃO",
        # Ordem de leitura pedida por Juan (2026-10-20): o espaco e' a resposta, concorrentes e
        # Ultra sao o contexto dela.
        [
            ("Espaço para academias", _format_number(result.get("espaco_para_academias"), 0)),
            ("Unidades Concorrentes", _format_number(result.get("n_concorrentes"), 0)),
            ("Unidades Ultra", _format_number(result.get("n_ultra"), 0)),
        ],
        accent=secondary, border_rgb=secondary,
    )
    # Box "Como calculamos o espaco" (3o bloco: contorno laranja).
    _rounded_panel(pdf, px, y_end + 12, pw, box_h, border_rgb=_ciclo_cor(2))
    pdf.set_text_color(*ULTRA_LARANJA)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(px + 12, y_end + 22)
    pdf.cell(pw - 24, 14, _ascii("Como calculamos o espaço"))
    pdf.set_text_color(45, 45, 45)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(px + 12, y_end + 42)
    resposta_unica = _resposta_unica(result)
    pdf.multi_cell(pw - 24, 13, _ascii(
        f"Residual das regiões com {_format_number(OFERTA_DESTAQUE_MIN, 0)} ou mais / 2.500"
        if resposta_unica else "Soma dos hexágonos destacados / 2.500"
    ))
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
    # AJUSTE 2 (BLK-RELMUN-03): legenda BREVE do criterio de inclusao do hexagono (limiar real
    # do _hex_destacado_mask: OFERTA_DESTAQUE_MIN — SO Residual Fitness, termo de SAM removido).
    _draw_note(
        pdf, 34.0, 490.0, 540.0,
        # DEC-077 (Brasil): o espaco e' leitura de capacidade; a lista de onde expandir e' so' a
        # do "Onde crescer".
        f"Espaço para academias = {_rotulo_espaco_leitura()}. Leitura de capacidade do município."
        if resposta_unica else
        f"Hexágono considerado quando Residual Fitness >= {_format_number(OFERTA_DESTAQUE_MIN, 0)} (alunos).",
    )


def _espaco_explicado_page(pdf: _UltraPDF, result: dict[str, Any], mapa: bytes | None,
                           assets: dict[str, bytes | None], *,
                           primary: tuple[int, int, int] = ULTRA_TURQUESA) -> None:
    """Pagina "Como chegamos ao Espaco para academias", logo depois do Resumo (Juan, 2026-10-20).

    No mapa do Resumo cada verde parecia UM espaco. Aqui cada hexagono aprovado mostra QUANTAS
    academias de 2.500 alunos cabem nele (`academias_por_hex`), e os numeros somam o total do
    Resumo. O pedido foi a visualizacao, nao texto: ao lado, so' o total e onde cabem mais.
    """
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, f"Como chegamos ao Espaço para academias - {_local_label(result)}", rgb=primary)
    _draw_framed_map(pdf, mapa, max_w=540.0, max_h=380.0, x_anchor=34.0, y_anchor=100.0,
                     border_rgb=primary)
    # Numeros como TEXTO do PDF sobre o mapa, na mesma conta de encaixe de `_draw_map`: nitidos em
    # qualquer zoom, ao contrario do numero rasterizado no PNG.
    rot = result.get("espaco_rotulos") or {}
    dims = _png_dimensions(mapa) if mapa else None
    if dims and rot.get("pontos"):
        draw_w, draw_h, mx, my = _fit_contain(dims[0], dims[1], 540.0, 380.0, x_anchor=34.0, y_anchor=100.0)
        k = draw_w / dims[0]
        # Numero num circulo escuro com borda branca (Juan, 2026-10-22): branco de 7 pt direto no
        # hexagono sumia sob as ruas brancas e os nomes do fundo de ruas, que vem por cima dos
        # hexagonos. O circulo e' menor que o hexagono, entao a cor da regiao segue a vista.
        pdf.set_font("Helvetica", "B", 9)
        espessura = pdf.line_width
        pdf.set_line_width(0.9)
        for cx, cy, txt in rot["pontos"]:
            d = max(13.0, pdf.get_string_width(_ascii(txt)) + 6.0)
            x, y = mx + cx * k, my + cy * k
            pdf.set_fill_color(*_ESPACO_NUMERO_RGB)
            pdf.set_draw_color(*_BRANCO)
            pdf.ellipse(x - d / 2.0, y - d / 2.0, d, d, style="FD")
            pdf.set_text_color(*_BRANCO)
            pdf.set_xy(x - d / 2.0, y - 4.5)
            pdf.cell(d, 9.0, _ascii(txt), align="C")
        pdf.set_line_width(espessura)

    espaco = result.get("espaco_para_academias")
    n_aprov = int(result.get("n_aprovados", 0) or 0)
    px = 610.0
    pw = _PAGE_W - px - 36.0
    head_h = 150.0
    y0 = 90.0
    _rounded_panel(pdf, px, y0, pw, head_h, border_rgb=ULTRA_LARANJA)
    pdf.set_text_color(*ULTRA_LARANJA)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(px + 14, y0 + 12)
    pdf.cell(pw - 28, 14, _ascii("ESPAÇO PARA ACADEMIAS"))
    pdf.set_font("Helvetica", "B", 40)
    pdf.set_xy(px + 14, y0 + 30)
    pdf.cell(pw - 28, 44, _ascii(_format_number(espaco, 0)))
    pdf.set_text_color(45, 45, 45)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_xy(px + 14, y0 + 78)
    # DEC-077 (Brasil): sem "aprovadas" -- a pagina fica (Juan com o Felipe, 2026-10-22), com o
    # espaco lido como capacidade nao atendida.
    regioes = (
        f"regiões com residual a partir de {_format_number(OFERTA_DESTAQUE_MIN, 0)} alunos "
        "(capacidade não atendida)"
        if _resposta_unica(result) else "regiões aprovadas"
    )
    pdf.multi_cell(pw - 28, 14, _ascii(
        f"academias de {_format_number(CAPACIDADE_UNIDADE, 0)} alunos cabem nas "
        f"{_format_number(n_aprov, 0)} {regioes}. Cada número no mapa é quantas cabem "
        "naquela região."
    ))

    _draw_note(
        pdf, 34.0, 490.0, 540.0,
        f"Número = Residual Fitness da região ÷ {_format_number(CAPACIDADE_UNIDADE, 0)}, arredondado "
        f"para os números somarem {_format_number(espaco, 0)}. Região = hexágono de ~5 km².",
    )
    if _resposta_unica(result):
        # DEC-077 (Brasil): o mapa segue com QUANTAS academias cabem em cada regiao (item 4 do
        # Felipe), mas sem o painel "ONDE CABEM MAIS" -- regioes NOMEADAS em ordem de residual
        # seriam uma segunda lista de onde expandir ao lado do Top 10 (em SJC abria com Campo dos
        # Alemaes, que a regua deixa de fora por renda).
        return
    # Onde cabem mais: os hexagonos com mais academias, pelo bairro dominante.
    academias = dict(result.get("academias_por_hex") or {})
    bairro_de = dict(result.get("bairros_por_hex") or {})
    top = sorted(academias.items(), key=lambda t: (-t[1], t[0]))[:6]
    y = y0 + head_h + 12.0
    _rounded_panel(pdf, px, y, pw, 32.0 + 20.0 * max(len(top), 1) + 10.0, border_rgb=primary)
    pdf.set_text_color(*primary)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(px + 14, y + 12)
    pdf.cell(pw - 28, 14, _ascii("ONDE CABEM MAIS"))
    yy = y + 34.0
    for hid, n in top:
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_xy(px + 14, yy)
        pdf.cell(pw - 80, 14, _ascii(_encurtar(pdf, str(bairro_de.get(hid) or "Região sem bairro"), pw - 90)))
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_xy(px + pw - 70, yy)
        pdf.cell(56, 14, _ascii(f"{n} academia{'s' if n != 1 else ''}"), align="R")
        yy += 20.0


def renda_por_faixa_de_score(
    bairros_geo: dict[str, Any] | None,
) -> dict[str, dict[str, Any]] | None:
    """Renda per capita e DENSIDADE observadas dos bairros de cada faixa de score.

    `{rotulo: {"renda": (p25, p75), "densidade": (p25, p75), "n": n}}`, do 1o ao 3o quartil dos
    bairros da faixa, para um bairro fora da curva nao esticar o intervalo. O score junta renda
    (60%) e populacao do HEXAGONO (40%, area fixa de ~5 km2) numa regua absoluta (DEC-040), entao
    o par que acompanha o score e' renda + densidade -- a populacao do bairro nao, porque bairro
    grande tem muita gente sem ser denso (em SP a faixa "Medio" tinha os bairros mais populosos).
    Nenhuma faixa tem renda ou densidade fixa: e' o que os bairros DESTA cidade nela tem.
    `None` sem bairro real.
    """
    if not tem_bairro_real(bairros_geo):
        return None
    reais = [b for b in (bairros_geo or {}).get("bairros") or [] if not b.get("sobra")]
    # Renda DOMICILIAR (Juan, 2026-10-20) -- a mesma do card do mapa, trazida do hexagono. Sem ela
    # (base sem fator temporal, ou bairros sem metricas de mercado), a per capita do Censo.
    usa_dom = any(not math.isnan(_safe_float(b.get("renda_dom"))) for b in reais)
    campo = "renda_dom" if usa_dom else "renda_pc"
    trios = [
        (_safe_float(b.get("score")), _safe_float(b.get(campo)), _safe_float(b.get("densidade")))
        for b in reais
    ]
    trios = [t for t in trios if not math.isnan(t[0]) and not math.isnan(t[1])]
    if not trios:
        return None

    def quartis(valores: list[float]) -> tuple[float, float]:
        v = sorted(valores)
        return v[len(v) // 4], v[(3 * len(v)) // 4]

    saida: dict[str, dict[str, Any]] = {}
    for rotulo, lo, hi in SCORE_FAIXAS_TEMPLATE:
        dentro = [t for t in trios if lo <= t[0] < hi or (hi >= 100.0 and t[0] >= lo)]
        if not dentro:
            continue
        dens = [t[2] for t in dentro if not math.isnan(t[2])]
        saida[rotulo] = {
            "renda": quartis([t[1] for t in dentro]),
            "densidade": quartis(dens) if dens else None,
            "n": len(dentro),
            "renda_tipo": "domiciliar" if usa_dom else "per capita",
        }
    return saida


def _densidade_redonda(valor: float) -> str:
    """Densidade em hab./km2 arredondada a centena (7.852 -> "7.900")."""
    return _format_number(round(valor / 100.0) * 100.0 if valor >= 1_000 else round(valor), 0)


def _reais_redondos(valor: float) -> str:
    """Renda arredondada a dezena, na moeda de renda do perfil (R$ no BR, USD na AR)."""
    return _renda(round(valor / 10.0) * 10.0, 0)


def _score_page(pdf: _UltraPDF, result: dict[str, Any], mapa: bytes | None,
                assets: dict[str, bytes | None], *,
                primary: tuple[int, int, int] = ULTRA_TURQUESA,
                secondary: tuple[int, int, int] = ULTRA_MAGENTA) -> None:
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, "Score Censitário", rgb=primary)
    # Moldura do mapa = tom principal; painel de legenda = acento. Faixas de score INALTERADAS.
    # BLK-RELPON-03: max_w padronizado 560->540 (aspect 1,4211) p/ eliminar letterbox no PNG 1000x704.
    _draw_framed_map(pdf, mapa, max_w=540.0, max_h=380.0, x_anchor=34.0, y_anchor=100.0,
                     border_rgb=primary)
    # Legenda 4 faixas (D5) com cor representativa via RESIDUAL_SCORE_BANDS, em painel centrado.
    px = 626.0
    pw = _PAGE_W - px - 36.0
    renda_faixa = renda_por_faixa_de_score(result.get("bairros_geo"))
    passo = 40.0 if renda_faixa else 28.0
    panel_h = 34.0 + len(SCORE_FAIXAS_TEMPLATE) * passo + 42.0 + (14.0 if renda_faixa else 0.0)
    # Quadro "O que e' o score" ACIMA da legenda e em letra maior (Juan, 2026-10-20): so' com as
    # faixas em R$ o leitor concluia que o score e' renda.
    explica_h = 72.0
    topo = _centered_y(explica_h + 10.0 + panel_h)
    _rounded_panel(pdf, px, topo, pw, explica_h, border_rgb=ULTRA_LARANJA)
    pdf.set_text_color(*ULTRA_LARANJA)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(px + 12, topo + 10)
    pdf.cell(pw - 24, 14, _ascii("O que é o score censitário"))
    pdf.set_text_color(45, 45, 45)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(px + 12, topo + 28)
    # Versao curta pedida por Juan: "e' uma relacao entre populacao e renda". Pesos e ancoras
    # (DEC-040) ficam no codigo e na DEC, nao no slide.
    pdf.multi_cell(pw - 24, 12.5, _ascii(
        "Nota de 0 a 100 que relaciona renda e população: onde mora mais gente com mais renda, "
        "maior o score (60% renda, 40% população)."
    ))
    py0 = topo + explica_h + 10.0
    _rounded_panel(pdf, px, py0, pw, panel_h, border_rgb=secondary)
    pdf.set_text_color(*secondary)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(px + 14, py0 + 16)
    pdf.cell(pw - 28, 16, _ascii("Potencial socioeconômico"))
    yy = py0 + 44.0
    if renda_faixa:
        # O que sao os dois numeros de cada faixa, uma vez so', em vez de uma nota embaixo.
        tipo = next(iter(renda_faixa.values()))["renda_tipo"]
        pdf.set_text_color(*_CINZA_TEXTO)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_xy(px + 42, yy - 8)
        pdf.cell(pw - 56, 10, _ascii(f"renda {tipo} média / densidade dos bairros"), align="R")
        yy += 14.0
    for label, _lo, hi in SCORE_FAIXAS_TEMPLATE:
        rgba = score_band_to_color(min(hi - 1.0, 95.0), alpha=255)
        pdf.set_fill_color(int(rgba[0]), int(rgba[1]), int(rgba[2]))
        pdf.rect(px + 14, yy, 20, 16, style="F", round_corners=True, corner_radius=3)
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_xy(px + 42, yy)
        pdf.cell(pw - 42, 16, _ascii(label))
        # A faixa numerica ao lado do nome (Juan, 2026-10-20): "Medio" sozinho nao diz onde
        # comeca e termina. Com bairro na base, o numero e' a RENDA per capita que os bairros
        # desta cidade naquela faixa tem; o score da faixa desce para a linha de baixo.
        faixa = f"{_format_number(_lo, 0)} a {_format_number(hi, 0)}" if _lo > 0 else f"abaixo de {_format_number(hi, 0)}"
        if hi >= 100.0:
            faixa = f"{_format_number(_lo, 0)} ou mais"
        if renda_faixa is not None:
            obs = renda_faixa.get(label)

            def _intervalo(par: tuple[float, float] | None, fmt) -> str:
                if par is None:
                    return "sem bairro"
                a, b = fmt(par[0]), fmt(par[1])
                return a if a == b else f"{a} a {b}"

            renda_txt = _intervalo(obs["renda"] if obs else None, _reais_redondos)
            pop_txt = (
                _intervalo(obs["densidade"], _densidade_redonda) + " hab./km²"
                if obs and obs["densidade"] else ""
            )
            n_b = obs["n"] if obs else 0
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_xy(px + 42, yy)
            pdf.cell(pw - 56, 16, _ascii(renda_txt), align="R")
            pdf.set_text_color(*_CINZA_TEXTO)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_xy(px + 42, yy + 17)
            pdf.cell(pw - 56, 11, _ascii(
                f"score {faixa} - {_format_number(n_b, 0)} bairro{'s' if n_b != 1 else ''}"
            ))
            if pop_txt:
                pdf.set_text_color(45, 45, 45)
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_xy(px + 42, yy + 17)
                pdf.cell(pw - 56, 11, _ascii(pop_txt), align="R")
        else:
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_xy(px + 42, yy)
            pdf.cell(pw - 56, 16, _ascii(faixa), align="R")
        yy += passo
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(px + 14, yy + 6)
    pdf.multi_cell(pw - 28, 12, _ascii(
        f"Score médio {_format_number(result.get('score_censo_medio'), 1)} | "
        f"máx {_format_number(result.get('score_censo_max'), 1)}"
    ))
    # BLK-RELMUN-09: quando o mapa sai por BAIRRO, o rodape tem de dizer isso -- o leitor precisa
    # saber em que unidade esta olhando. (A nota das faixas saiu em 2026-10-20: elas estao na
    # legenda e o quadro de cima explica o score.)
    por_bairro = tem_bairro_real(result.get("bairros_geo"))
    instituto = _instituto_censo()
    pdf.set_xy(36, _PAGE_H - 36)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_CINZA_TEXTO)
    rodape_fonte = (
        f"Fonte: {instituto} Censo 2022 - setores agregados por bairro (média ponderada por população)"
        if por_bairro
        else f"Fonte: {instituto} Censo 2022 - Agregação H3 resolução 7"
    )
    pdf.cell(_PAGE_W - 72, 12, _ascii(rodape_fonte))


def _residual_page(pdf: _UltraPDF, result: dict[str, Any], mapa: bytes | None,
                   assets: dict[str, bytes | None], *,
                   primary: tuple[int, int, int] = ULTRA_TURQUESA,
                   secondary: tuple[int, int, int] = ULTRA_MAGENTA) -> None:
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, "Residual Fitness", rgb=primary)
    # Moldura do mapa = tom principal; painel MERCADO = acento.
    _draw_framed_map(pdf, mapa, max_w=540.0, max_h=380.0, x_anchor=34.0, y_anchor=100.0,
                     border_rgb=primary)
    px = 610.0
    pw = _PAGE_W - px - 36.0
    panel_h = 254.0
    py0 = _centered_y(panel_h)
    _rounded_panel(pdf, px, py0, pw, panel_h, border_rgb=secondary)
    pdf.set_text_color(*secondary)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(px + 14, py0 + 16)
    pdf.cell(pw - 28, 16, _ascii("MERCADO DISPONÍVEL"))
    pdf.set_text_color(*secondary)
    pdf.set_font("Helvetica", "B", 34)
    pdf.set_xy(px + 14, py0 + 46)
    pdf.cell(pw - 28, 36, _ascii(f"{_format_number(result.get('mercado_disponivel_pessoas'), 0)}"))
    pdf.set_text_color(45, 45, 45)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_xy(px + 14, py0 + 88)
    pdf.cell(pw - 28, 16, _ascii("alunos sem academia no município inteiro"))
    yy = py0 + 116
    for rotulo, valor in (
        # O total e' do MUNICIPIO INTEIRO; a parte das regioes aprovadas e' a que entra no
        # "Espaco para academias" (Juan perguntou se eram os dados da cidade toda, 2026-10-20).
        (
            # DEC-077 (Brasil): sem "aprovadas"; e' o residual das regioes de 2.000 ou mais.
            f"Em regiões com {_format_number(OFERTA_DESTAQUE_MIN, 0)} ou mais"
            if _resposta_unica(result) else "Nas regiões aprovadas",
            _format_number(result.get("soma_oferta_amarelos"), 0),
        ),
        ("Hab. totais", _format_number(result.get("pop_total_municipio"), 0)),
        ("Renda per capita", _renda(result.get("renda_per_capita_media"), 2)),
        ("Penetração fitness", _format_number(result.get("penetracao_fitness_pct"), 1, "%")),
    ):
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "", 12)
        pdf.set_xy(px + 14, yy)
        pdf.cell((pw - 28) * 0.6, 16, _ascii(rotulo))
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_xy(px + 14 + (pw - 28) * 0.6, yy)
        pdf.cell((pw - 28) * 0.4, 16, _ascii(valor), align="R")
        yy += 24
    # FU1: nota curta explicando o residual.
    _draw_note(
        pdf, px, py0 + panel_h + 10, pw,
        "Residual = pop. elegível - alunos já atendidos (camada de mercado), somado em todos os "
        "hexágonos do município; os totais abaixo também são da cidade inteira.",
    )


_ZONA_TEXTOS = {
    "Âncora central": "Hexágonos centrais / posicionamento principal.",
    "Flancos laterais": "Captura dos hexágonos residuais e consolidação.",
    "Cerco": "Bairros de alta renda / hexágonos mais afastados.",
}


def _texto_zonas_sintese(zonas_geo: list[dict[str, Any]] | None) -> str:
    """Compoe o texto do card 3 (Movimento Recomendado) da Sintese a partir dos tipos de
    zona geometrica PRESENTES em result["zonas_geo"] (SO LEITURA; nao recalcula zonas).
    Ordem canonica de checagem: Cerco > Flancos laterais > Ancora central > fallback vazio
    (a zonificacao so produz PREFIXOS contiguos comecando em Ancora — ver _zonas_geometricas
    linhas 506-513 — checar por pertencimento de rotulo, nao por indice, e defensivo a
    mudancas futuras no algoritmo)."""
    rotulos = {str(z.get("rotulo", "")) for z in (zonas_geo or [])}
    if "Cerco" in rotulos:
        return (
            "Movimento Recomendado: posicionamento periférico, cercar o núcleo pelos "
            "flancos antes da concorrência."
        )
    if "Flancos laterais" in rotulos:
        return (
            "Movimento Recomendado: adensar o núcleo central e avançar pelos flancos, "
            "capturando os residuais laterais."
        )
    if "Âncora central" in rotulos:
        return (
            "Movimento Recomendado: adensar o núcleo central, concentrando a expansão "
            "na região de maior aprovação."
        )
    return (
        "Movimento Recomendado: hexágonos aprovados insuficientes para zonas de atuação "
        "neste município."
    )


def _dominio_page(pdf: _UltraPDF, result: dict[str, Any], mapa: bytes | None,
                  assets: dict[str, bytes | None], *,
                  primary: tuple[int, int, int] = ULTRA_TURQUESA,
                  secondary: tuple[int, int, int] = ULTRA_MAGENTA) -> None:
    """Pagina 5 — 3 estrategias de dominio.

    FU1: a zonificacao das 3 estrategias e GEOMETRICA (tercis de distancia ao centroide;
    `zonas_geo`/`hex_zona_geo` em `agregar_municipio` via `_zonas_geometricas`). E camada de
    DISPLAY: NAO altera `dominio_df`, `flag_sam`, score nem qualquer artefato do M1.
    """
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, "Expansão de Domínio", rgb=primary)
    # Moldura do mapa = tom principal; painel ESTRATEGIA = acento. Cores de ZONA inalteradas.
    _draw_framed_map(pdf, mapa, max_w=540.0, max_h=380.0, x_anchor=34.0, y_anchor=100.0,
                     border_rgb=primary)
    px = 610.0
    pw = _PAGE_W - px - 36.0

    zonas_geo = result.get("zonas_geo") or []
    # Painel ESTRATEGIA centrado verticalmente.
    panel_h = 60.0 + max(1, len(zonas_geo)) * 64.0
    py0 = _centered_y(panel_h)
    _rounded_panel(pdf, px, py0, pw, panel_h, border_rgb=secondary)
    pdf.set_text_color(*secondary)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_xy(px + 14, py0 + 16)
    pdf.cell(pw - 28, 18, _ascii("ESTRATÉGIA"))
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(px + 14, py0 + 36)
    pdf.multi_cell(pw - 28, 12, _ascii("Cercar e dominar a região por zonas geométricas."))

    yy = py0 + 60.0
    if not zonas_geo:
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_xy(px + 14, yy)
        pdf.multi_cell(pw - 28, 14, _ascii(
            "Hexes relevantes insuficientes para zonas neste município."
        ))
    else:
        # D7: ordem 1 Ancora central / 2 Flancos laterais / 3 Cerco — cada zona com sua cor.
        for zona in zonas_geo:
            zn = int(zona.get("zona_n", 0))
            cor = zona.get("cor_rgb", ULTRA_MAGENTA)
            rotulo = str(zona.get("rotulo", f"Zona {zn}"))
            # Bullet numerado colorido por estrategia.
            pdf.set_fill_color(*cor)
            pdf.ellipse(px + 14, yy + 1, 16, 16, style="F")
            pdf.set_text_color(*_BRANCO)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_xy(px + 14, yy + 2)
            pdf.cell(16, 14, _ascii(str(zn)), align="C")
            pdf.set_text_color(*cor)
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_xy(px + 38, yy)
            # BLK-RELMUN-10: quando o mapa ao lado sai por BAIRRO, contar hexes no painel deixa
            # a pagina incoerente consigo mesma -- o leitor conta bairros no mapa e le "hexes"
            # na legenda. A zona continua definida em hexagono; muda so a unidade EXIBIDA.
            n_bairros_zona = sum(
                1 for b in (result.get("bairros_geo") or {}).get("bairros") or []
                if not b.get("sobra") and b.get("zona") == zn - 1
            )
            unidade = (
                f"{n_bairros_zona} bairros" if n_bairros_zona
                else f"{zona.get('n_hex')} hexes"
            )
            pdf.cell(pw - 52, 16, _ascii(f"{rotulo}  ({unidade})"))
            yy += 20
            pdf.set_text_color(45, 45, 45)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_xy(px + 38, yy)
            pdf.multi_cell(pw - 52, 13, _ascii(str(zona.get("descricao", ""))))
            yy = pdf.get_y() + 14
    pdf.set_xy(36, _PAGE_H - 36)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.cell(_PAGE_W - 72, 12, _ascii(f"Motor de Expansão Ultra - {_instituto_censo()} + OSM"))


# Colunas da tabela de comparacao: (rotulo, largura pt, alinhamento). Somam 878 dos 888 pt
# uteis (960 - 2*36 de margem); a folga evita que arredondamento de fonte empurre a ultima
# coluna para fora da pagina.
# Sem as colunas "Hexágono" (id H3) e "Score" desde 2026-10-20, a pedido de Juan: o id nao diz
# nada a quem le e o score tem pagina propria. Os dois seguem em `tabela_hexes` (dado), so' nao
# sao impressos; a largura que sobrou foi para o nome do bairro.
_TABELA_COLUNAS: tuple[tuple[str, float, str], ...] = (
    ("#", 28.0, "C"),
    ("Bairro dominante", 330.0, "L"),
    ("População", 120.0, "R"),
    ("Renda domiciliar", 150.0, "R"),
    ("Densidade", 120.0, "R"),
    ("Residual", 130.0, "R"),
)
_TABELA_ZEBRA = (243, 245, 248)

# Metricas que o mapa de bairro sabe pintar como choropleth, e a procedencia de cada uma.
# "exata" = sobe do SETOR (agregacao); "rateada" = desce do HEXAGONO (reparticao, estimativa).
# A pagina usa isto para declarar o metodo em vez de deixar as duas passarem por iguais.
_BAIRRO_METRICAS: dict[str, str] = {
    "score": "exata",
    "residual": "rateada",
    "resumo": "rateada",
    "cobertura": "rateada",
    "dominio": "rateada",
}
_BAIRRO_METRICA_RODAPE: dict[str, str] = {
    "score": "Score do bairro = média dos setores {instituto} 2022 ponderada por população",
    "residual": "Residual do bairro = média dos hexágonos, ponderada pela população dos setores",
    "resumo": "Aprovação do bairro = maioria da população em hexágono aprovado",
    "cobertura": "Aprovação do bairro = maioria da população em hexágono aprovado",
    "dominio": "Zona do bairro = zona do hexágono com maior população do bairro",
}


def _tabela_hexes_page(pdf: _UltraPDF, result: dict[str, Any], assets: dict[str, bytes | None], *,
                       primary: tuple[int, int, int] = ULTRA_TURQUESA) -> None:
    """Pagina "Comparação das Regiões" (BLK-RELMUN-07): tabela ranqueada dos hexes do municipio.

    Equivale a tabela de abertura do material de referencia do time de Expansao, trocando bairro
    por HEXAGONO -- que e a unidade em que este relatorio decide. Ordenada por Residual Fitness,
    a mesma metrica do destaque no mapa; a coluna de bairro amarra cada hex a um nome conhecido.

    Fallback gracioso: municipio sem hexes/sem a tabela -> aviso, sem excecao.
    """
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, f"Comparação das Regiões - {_local_label(result)}", rgb=primary)

    tabela = result.get("tabela_hexes") or {}
    linhas = list(tabela.get("linhas") or [])
    n_total = int(tabela.get("n_total", len(linhas)) or 0)

    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_xy(36, 70.0)
    if linhas:
        # Declara o corte SEMPRE: "as 15 melhores" so e' informacao util junto do total.
        resumo = (
            f"As {len(linhas)} melhores das {n_total} regiões do município, ranqueadas por "
            f"Residual Fitness (alunos sem academia)."
            if len(linhas) < n_total
            else f"As {n_total} regiões do município, ranqueadas por Residual Fitness "
                 f"(alunos sem academia)."
        )
        pdf.multi_cell(_PAGE_W - 72, 14, _ascii(resumo))
    else:
        pdf.multi_cell(_PAGE_W - 72, 14, _ascii("Sem regiões mapeadas para este município."))
        return

    x0, y = 36.0, 100.0
    head_h, row_h = 24.0, 22.0

    # Cabecalho.
    pdf.set_fill_color(*primary)
    pdf.rect(x0, y, sum(w for _r, w, _a in _TABELA_COLUNAS), head_h, style="F")
    pdf.set_text_color(*_BRANCO)
    pdf.set_font("Helvetica", "B", 9)
    x = x0
    for rotulo, w, align in _TABELA_COLUNAS:
        pdf.set_xy(x + 6, y + 6)
        pdf.cell(w - 12, 12, _ascii(rotulo), align=align)
        x += w
    y += head_h

    largura_total = sum(w for _r, w, _a in _TABELA_COLUNAS)
    for i, linha in enumerate(linhas, start=1):
        if i % 2 == 0:
            pdf.set_fill_color(*_TABELA_ZEBRA)
            pdf.rect(x0, y, largura_total, row_h, style="F")

        bairro = str(linha["bairro"])
        if len(bairro) > 48:  # a coluna e' fixa; truncar aqui evita invadir a proxima
            bairro = bairro[:45] + "..."
        valores = (
            (str(i), _CINZA_TEXTO, "", 9),
            (bairro, (40, 40, 40), "", 9),
            (_format_number(linha["pop"], 0), (40, 40, 40), "", 9),
            (_renda(linha["renda"]), (40, 40, 40), "", 9),
            (_format_number(linha["densidade"], 0), (40, 40, 40), "", 9),
            # Residual em VERDE quando a regiao passa no criterio de destaque (D1) -- mesma
            # semantica de cor do mapa, para tabela e mapa nao contarem historias diferentes.
            (
                _format_number(linha["residual"], 0),
                _COR_APROVADO_PROPRIO if linha["destacado"] else (120, 128, 140),
                "B",
                9,
            ),
        )
        x = x0
        # strict: se `valores` e `_TABELA_COLUNAS` divergirem numa edicao futura, e' melhor
        # estourar aqui do que a tabela sair com uma coluna a menos, calada.
        for (texto, cor, estilo, tamanho), (_rot, w, align) in zip(
            valores, _TABELA_COLUNAS, strict=True
        ):
            pdf.set_text_color(*cor)
            pdf.set_font("Helvetica", estilo, tamanho)
            pdf.set_xy(x + 6, y + 6)
            pdf.cell(w - 12, 11, _ascii(texto), align=align)
            x += w
        y += row_h

    fonte = tabela.get("fonte_renda")
    if fonte == "domiciliar":
        nota_renda = (
            "Renda domiciliar = renda do hexágono (Censo 2022, setores repartidos por área) x "
            "moradores e uplift de composição do município x atualização monetária - o MESMO "
            "número do card do hexágono no mapa."
        )
    elif fonte == "censo":
        nota_renda = (
            "Renda = per capita do hexágono (a domiciliar exigiria a partição de "
            "setores, indisponível para este município)."
        )
    else:
        nota_renda = "Renda = per capita municipal; sem renda censitária por hexágono."
    if tabela.get("renda_constante"):
        nota_renda += " Neste município ela é a MESMA em todas as regiões (não diferencia)."

    _draw_note(
        pdf, x0, y + 8, largura_total,
        f"Residual Fitness em VERDE = região aprovada (>= {_format_number(OFERTA_DESTAQUE_MIN, 0)} "
        f"alunos), a mesma regra que destaca o hexágono no mapa. {nota_renda} População e "
        f"densidade do Censo {_instituto_censo()} 2022; bairro dominante = bairro mais populoso do hexágono. "
        "Camada de display, não altera o M1.",
    )


def _indice_bairros(pdf: _UltraPDF, x: float, y: float, w: float, h: float, titulo: str,
                    itens: list[tuple[int, str]], *, cor: tuple[int, int, int],
                    subtitulo: str | None = None, subtitulo_rgb: tuple[int, int, int] | None = None) -> None:
    """Painel "numero  nome" em colunas, de cima para baixo -- o indice do mapa numerado."""
    _rounded_panel(pdf, x, y, w, h, border_rgb=cor)
    pdf.set_text_color(*cor)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(x + 14, y + 12)
    pdf.cell(w - 28, 14, _ascii(titulo))
    topo = y + 34.0
    if subtitulo:
        pdf.set_text_color(*(subtitulo_rgb or _CINZA_TEXTO))
        pdf.set_font("Helvetica", "", 9)
        pdf.set_xy(x + 14, topo - 4)
        pdf.cell(w - 28, 12, _ascii(subtitulo))
        topo += 12.0
    util_h = y + h - 12.0 - topo
    n_col = 1 if len(itens) <= 22 else (2 if len(itens) <= 50 else 3)
    linhas = max(1, math.ceil(len(itens) / n_col))
    linha_h = max(8.0, min(16.0, util_h / linhas))
    col_w = (w - 28) / n_col
    fonte = max(6.5, min(10.0, linha_h * 0.66))
    for i, (n, nome) in enumerate(itens):
        col, lin = divmod(i, linhas)
        xx = x + 14 + col * col_w
        yy = topo + lin * linha_h
        pdf.set_text_color(*ULTRA_MAGENTA)
        pdf.set_font("Helvetica", "B", fonte)
        pdf.set_xy(xx, yy)
        pdf.cell(22, linha_h, _ascii(str(n)))
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "", fonte)
        pdf.set_xy(xx + 22, yy)
        pdf.cell(col_w - 26, linha_h, _ascii(_encurtar(pdf, nome, col_w - 28)))


def _bairros_mapa_page(pdf: _UltraPDF, result: dict[str, Any], mapa: bytes | None,
                       assets: dict[str, bytes | None], *,
                       primary: tuple[int, int, int] = ULTRA_TURQUESA,
                       secondary: tuple[int, int, int] = ULTRA_MAGENTA,
                       mapas_partes: dict[str, bytes] | None = None) -> None:
    """Pagina "Bairros Oficiais" (BLK-RELMUN-06): divisa territorial real, bairros NUMERADOS.

    Da ao leitor a mesma ancora geografica do material de referencia do time de Expansao: ANTES
    de discutir hexagono, mostrar em que bairro cada coisa cai. Fallback gracioso: municipio sem
    bairro na base IBGE -> mapa com o aviso e painel de contagem zerada, sem excecao.

    Desde 2026-10-20 (Juan): o nome saiu do mapa para um indice ao lado, e o municipio que nao
    cabe num quadro (`dividir_bairros_em_partes`) vira uma visao geral das partes + uma pagina
    por parte, com zoom so' nela. `mapas_partes` traz os PNGs `bairros_parte_<k>`.
    """
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, f"Bairros Oficiais - {_local_label(result)}", rgb=primary)
    _draw_framed_map(pdf, mapa, max_w=540.0, max_h=380.0, x_anchor=34.0, y_anchor=100.0,
                     border_rgb=primary)

    geo = result.get("bairros_geo") or {}
    bairros = [b for b in (geo.get("bairros") or []) if not b.get("sobra")]
    n_bairros = int(geo.get("n_bairros", len(bairros)) or 0)
    cobertura = float(geo.get("cobertura", 1.0) or 0.0)
    # Cobertura ruim = a contagem NAO representa o municipio (ex.: Palmas/TO, 2 distritos rurais
    # para 733 setores). O numero continua exibido, mas com a ressalva colada nele.
    parcial = bool(bairros) and cobertura < _BAIRRO_COBERTURA_MIN

    px = 610.0
    pw = _PAGE_W - px - 36.0
    divisao = dividir_bairros_em_partes(geo)
    if divisao is not None:
        _bairros_numerados(pdf, result, divisao, assets, px=px, pw=pw, parcial=parcial,
                           cobertura=cobertura, primary=primary, secondary=secondary,
                           mapas_partes=mapas_partes or {})
        return
    head_h = 100.0
    topo = bairros[:5]
    panel_h = 36.0 + max(len(topo), 1) * 26.0 + 12.0
    py0 = _centered_y(head_h + 12.0 + panel_h)

    _rounded_panel(pdf, px, py0, pw, head_h, border_rgb=secondary)
    pdf.set_text_color(*secondary)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(px + 14, py0 + 12)
    pdf.cell(pw - 28, 14, _ascii("BAIRROS IDENTIFICADOS"))
    pdf.set_font("Helvetica", "B", 40)
    pdf.set_xy(px + 14, py0 + 32)
    pdf.cell(pw - 28, 44, _ascii(_format_number(n_bairros, 0)))
    pdf.set_text_color(45, 45, 45)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_xy(px + 14, py0 + 80)
    if parcial:
        pdf.set_text_color(*ULTRA_LARANJA)
        pdf.cell(
            pw - 28, 14,
            _ascii(f"cobrem só {cobertura * 100:.0f}% dos setores do município"),
        )
    else:
        pdf.cell(pw - 28, 14, _ascii("bairros com limite territorial mapeado"))

    linhas = (
        [(str(b["nome"]), _format_number(b["pop"], 0)) for b in topo]
        if topo
        else [("Sem bairro mapeado", TEXTO_SEM_DADO)]
    )
    _info_panel(
        pdf, px, py0 + head_h + 12, pw, "MAIS POPULOSOS (hab.)",
        linhas, accent=ULTRA_LARANJA, border_rgb=_ciclo_cor(2),
    )

    if parcial:
        nota = (
            f"A base {_instituto_censo()} 2022 só nomeia bairro/distrito em {cobertura * 100:.0f}% dos setores "
            "deste município - a área sem cor (contorno cinza) não tem divisa oficial. Para desenhar o "
            "restante seria preciso a malha de bairros da prefeitura. Camada de display, não "
            "altera o M1."
        )
    elif bairros:
        nota = (
            f"Limite de cada bairro = setores censitários do {_instituto_censo()} 2022 dissolvidos por bairro "
            "(sem bairro, usa subdistrito/distrito). Cobertura heterogênea entre municípios. "
            "População do Censo 2022; camada de display, não altera o M1."
        )
    else:
        nota = (
            f"Este município não tem bairro nem distrito mapeado na base {_instituto_censo()} 2022 - o limite "
            "territorial exigiria a malha de bairros da prefeitura."
            # No Brasil (DEC-077) as paginas por zona sairam: a frase apontaria para paginas que
            # o PDF nao tem.
            + ("" if _resposta_unica(result)
               else " As páginas seguintes usam as zonas geométricas por distância ao centroide.")
        )
    _draw_note(pdf, 34.0, 490.0, 540.0, nota)


def _nota_bairros_oficiais(parcial: bool, cobertura: float, *, cnefe: bool = False) -> str:
    if cnefe and not parcial:
        # DEC-076: nome e limite vem do bairro do CNEFE (o mais frequente no setor).
        return (
            f"Limite de cada bairro = setores censitários do {_instituto_censo()} 2022 dissolvidos pelo "
            "bairro do Cadastro de Endereços (CNEFE), o mais frequente em cada setor; sem bairro no "
            "CNEFE, usa bairro/subdistrito/distrito da malha. População do Censo 2022; camada de "
            "display, não altera o M1."
        )
    if parcial:
        return (
            f"A base {_instituto_censo()} 2022 só nomeia bairro/distrito em {cobertura * 100:.0f}% dos setores "
            "deste município - a área sem cor (contorno cinza) não tem divisa oficial. Para desenhar o "
            "restante seria preciso a malha de bairros da prefeitura. Camada de display, não "
            "altera o M1."
        )
    return (
        f"Limite de cada bairro = setores censitários do {_instituto_censo()} 2022 dissolvidos por bairro "
        "(sem bairro, usa subdistrito/distrito). Cobertura heterogênea entre municípios. "
        "População do Censo 2022; camada de display, não altera o M1."
    )


def _bairros_numerados(pdf: _UltraPDF, result: dict[str, Any], divisao: dict[str, Any],
                       assets: dict[str, bytes | None], *, px: float, pw: float, parcial: bool,
                       cobertura: float, primary: tuple[int, int, int],
                       secondary: tuple[int, int, int], mapas_partes: dict[str, bytes]) -> None:
    """Lado direito da pagina Bairros Oficiais (o mapa ja' foi desenhado) + as paginas das partes."""
    numero = divisao["numero"]
    partes = divisao["partes"]
    avulsos = divisao["avulsos"]
    n_total = int(divisao.get("n_total", len(numero)))
    aviso = f"cobrem só {cobertura * 100:.0f}% dos setores do município" if parcial else None
    nota = _nota_bairros_oficiais(
        parcial, cobertura, cnefe=(result.get("bairros_geo") or {}).get("fonte_bairro") == FONTE_CNEFE,
    )
    # Paginas das partes: bairro so' com CONTORNO na cor da parte (o limite e' o que se le ali).
    nota_parte = (
        "Cada bairro desta parte com o contorno na cor dela"
        + (" - grosso nos numerados, fino nos demais" if divisao.get("fora") else "")
        + "; em cinza, os das outras partes; o mini-mapa mostra onde esta parte fica no município. "
        + (f"Numerados os {len(numero)} bairros mais populosos dos {_format_number(n_total, 0)}. "
           if divisao.get("fora") else "")
        + nota
    )
    if divisao.get("fora"):
        nota = (f"Numerados os {len(numero)} bairros mais populosos dos {_format_number(n_total, 0)}; "
                "os demais ficam no tom mais claro da parte mais próxima, sem número. " + nota)
    # Bairros por parte, numerados ou nao (`parte_de`): e' o que o mapa pinta em cada cor.
    n_na_parte = [sum(1 for kk in (divisao.get("parte_de") or {}).values() if kk == k)
                  for k in range(len(partes))]
    if len(partes) == 1 and not avulsos:
        titulo = (f"BAIRROS ({len(numero)} mais populosos de {_format_number(n_total, 0)})"
                  if divisao.get("fora") else f"BAIRROS ({len(numero)})")
        _indice_bairros(pdf, px, 90.0, pw, 400.0, titulo,
                        [(numero[n], n) for n in partes[0]], cor=secondary,
                        subtitulo=aviso, subtitulo_rgb=ULTRA_LARANJA)
        _draw_note(pdf, 34.0, 490.0, 540.0, nota)
        return

    # Visao geral: as partes, cada uma com a faixa de numeros e tres bairros de exemplo.
    _rounded_panel(pdf, px, 90.0, pw, 400.0, border_rgb=secondary)
    pdf.set_text_color(*secondary)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(px + 14, 102.0)
    pdf.cell(pw - 28, 14, _ascii(
        f"PARTES DO MUNICÍPIO ({len(numero)} de {_format_number(n_total, 0)} bairros)"
        if divisao.get("fora") else f"PARTES DO MUNICÍPIO ({len(numero)} bairros)"
    ))
    y = 124.0
    if aviso:
        pdf.set_text_color(*ULTRA_LARANJA)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_xy(px + 14, y - 4)
        pdf.cell(pw - 28, 12, _ascii(aviso))
        y += 10.0
    por_nome = {str(b["nome"]): b for b in (result.get("bairros_geo") or {}).get("bairros") or []}
    passo = min(44.0, (330.0 - (14.0 * len(avulsos) + 20.0 if avulsos else 0.0)) / max(len(partes), 1))
    for k, parte in enumerate(partes):
        cor = _PARTE_CORES[k % len(_PARTE_CORES)]
        pdf.set_fill_color(*cor)
        pdf.ellipse(px + 14, y + 1, 16, 16, style="F")
        pdf.set_text_color(*_BRANCO)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_xy(px + 14, y + 3)
        pdf.cell(16, 12, _ascii(str(k + 1)), align="C")
        nums = [numero[n] for n in parte]
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_xy(px + 36, y + 2)
        total = (f" de {_format_number(n_na_parte[k], 0)}" if divisao.get("fora") and n_na_parte[k] > len(parte)
                 else "")
        pdf.cell(pw - 50, 12, _ascii(
            f"Parte {k + 1} - {len(parte)}{total} bairros (nº {min(nums)} a {max(nums)})"
        ))
        maiores = sorted(parte, key=lambda n: -_safe_float((por_nome.get(n) or {}).get("pop")))[:3]
        pdf.set_text_color(*_CINZA_TEXTO)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_xy(px + 36, y + 15)
        pdf.cell(pw - 50, 10, _ascii(_encurtar(pdf, "ex.: " + ", ".join(maiores), pw - 52)))
        y += passo
    if avulsos:
        y += 6.0
        pdf.set_text_color(*primary)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_xy(px + 14, y)
        pdf.cell(pw - 28, 12, _ascii("NUMERADOS NO MAPA AO LADO"))
        y += 16.0
        for n in avulsos:
            pdf.set_text_color(*ULTRA_MAGENTA)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_xy(px + 14, y)
            pdf.cell(22, 12, _ascii(str(numero[n])))
            pdf.set_text_color(45, 45, 45)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_xy(px + 36, y)
            pdf.cell(pw - 50, 12, _ascii(_encurtar(pdf, n, pw - 52)))
            y += 14.0
    _draw_note(pdf, 34.0, 490.0, 540.0,
               f"O município foi dividido em {len(partes)} partes para os números caberem; cada parte "
               "tem uma página a seguir, com zoom e a lista dos seus bairros. " + nota)

    for k, parte in enumerate(partes):
        cor = _PARTE_CORES[k % len(_PARTE_CORES)]
        pdf.add_page()
        _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
        _draw_title_band(pdf, f"Bairros Oficiais - {_local_label(result)} - Parte {k + 1} de {len(partes)}",
                         rgb=primary)
        _draw_framed_map(pdf, mapas_partes.get(f"bairros_parte_{k + 1}"), max_w=540.0, max_h=380.0,
                         x_anchor=34.0, y_anchor=100.0, border_rgb=primary)
        _indice_bairros(pdf, px, 90.0, pw, 400.0, f"BAIRROS DA PARTE {k + 1} ({len(parte)})",
                        [(numero[n], n) for n in parte], cor=cor)
        _draw_note(pdf, 34.0, 490.0, 540.0, nota_parte)


def _nota_fonte_bairro(result: dict[str, Any]) -> str:
    """Primeira frase da nota de fonte da Pagina 6: diz de ONDE veio o nome do bairro (DEC-076)."""
    instituto = _instituto_censo()
    if (result.get("bairros_geo") or {}).get("fonte_bairro") == FONTE_CNEFE:
        return (
            f"Fonte: bairro do Cadastro de Endereços (CNEFE) do {instituto} Censo 2022, o mais "
            "frequente em cada setor; sem bairro no CNEFE, usa bairro/subdistrito/distrito da "
            "malha de setores. "
        )
    return f"Fonte: {instituto} Censo 2022 (bairro do setor; sem bairro, usa subdistrito/distrito). "


def _bairros_page(pdf: _UltraPDF, result: dict[str, Any], assets: dict[str, bytes | None], *,
                  primary: tuple[int, int, int] = ULTRA_TURQUESA) -> None:
    """Pagina 6 — Bairros por Zona (BLK-RELMUN-02 / resolve D9).

    Quando ha bairros REAIS resolvidos (`result["bairros_por_zona"]`, fonte IBGE `NM_BAIRRO`
    da particao geo), lista TODOS os bairros distintos agrupados pelas 3 zonas geometricas
    (sem cap; multi_cell quebra em linhas). Fallback gracioso (municipio sem
    bairro mapeado — DF, pequenos): cai nas zonas geometricas + tese, SEM excecao e sem a nota
    de "indisponivel" como texto principal. READ-ONLY sobre o M1; display-only.
    """
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, "Bairros por Zona", rgb=primary)

    bairros_por_zona = result.get("bairros_por_zona") or []
    tem_bairros = any(z.get("bairros") for z in bairros_por_zona)
    zonas_geo = result.get("zonas_geo") or []
    desc_por_zona = {int(z.get("zona_n", 0)): str(z.get("descricao", "")) for z in zonas_geo}
    nhex_por_zona = {int(z.get("zona_n", 0)): z.get("n_hex") for z in zonas_geo}

    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_xy(36, 70.0)
    if tem_bairros:
        pdf.multi_cell(
            _PAGE_W - 72, 14,
            _ascii(f"Bairros ({_instituto_censo()} 2022) agrupados pelas zonas de domínio do município."),
        )
    else:
        pdf.multi_cell(
            _PAGE_W - 72, 14,
            _ascii("Zonas de domínio do município por distância ao centroide."),
        )

    yy = 116.0
    if not zonas_geo:
        pdf.set_xy(36, yy)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(45, 45, 45)
        pdf.multi_cell(_PAGE_W - 72, 14, _ascii("Sem zonas geométricas disponíveis para este município."))
    else:
        for zona in zonas_geo:
            zn = int(zona.get("zona_n", 0))
            cor = zona.get("cor_rgb", ULTRA_TURQUESA)
            rotulo = str(zona.get("rotulo", f"Zona {zn}"))
            pdf.set_fill_color(*cor)
            pdf.ellipse(36, yy + 2, 12, 12, style="F")
            pdf.set_text_color(*cor)
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_xy(56, yy)
            pdf.cell(_PAGE_W - 92, 16, _ascii(f"Zona {zn} - {rotulo}"))
            yy += 20

            # Bairros REAIS desta zona (quando houver) ou linha de hexes/tese (fallback).
            bairros = next(
                (z.get("bairros") or [] for z in bairros_por_zona if int(z.get("zona_n", 0)) == zn),
                [],
            )
            pdf.set_text_color(45, 45, 45)
            pdf.set_xy(56, yy)
            if bairros:
                # Lista TODOS os bairros da zona (sem cap). Fonte/entrelinha compactas para que
                # ate municipios densos (Rio ~100 bairros) caibam na pagina sem auto_page_break
                # (off) cortar texto; multi_cell quebra em linhas e yy acompanha a altura real.
                pdf.set_font("Helvetica", "", 9)
                texto = ", ".join(bairros)
                pdf.multi_cell(_PAGE_W - 112, 11, _ascii(texto))
                yy = pdf.get_y() + 8
            else:
                pdf.set_font("Helvetica", "", 11)
                pdf.multi_cell(
                    _PAGE_W - 112, 14,
                    _ascii(f"{nhex_por_zona.get(zn)} hexes - {desc_por_zona.get(zn, '')}"),
                )
                yy = pdf.get_y() + 12
        if tem_bairros:
            _draw_note(
                pdf, 36, yy + 2, _PAGE_W - 72,
                _nota_fonte_bairro(result) + "Cobertura heterogênea entre municípios; zonas por distância ao centroide "
                "(display, não altera o M1).",
            )
        else:
            _draw_note(
                pdf, 36, yy + 2, _PAGE_W - 72,
                f"Bairros não mapeados na base {_instituto_censo()} 2022 para este município; exibição por zona "
                "geométrica (display); não altera dominio_df nem o M1.",
            )
    pdf.set_xy(36, _PAGE_H - 36)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.cell(_PAGE_W - 72, 12, _ascii(f"Motor de Expansão Ultra - {_instituto_censo()} + OSM"))


# ── Paginas da PRACA (`relatorio_praca.PracaDaCidade`): mapas de calor, pressao, crescimento e
# onde crescer. Condicionais (so' com `praca=`), por isso fora de `PDF_SECTION_HEADERS`. Texto
# pelo `texto_pdf` antes do `_ascii`: parte dele vem pronto da camada de crescimento, com travessao.

_PRACA_MAPA_W = 430.0
_PRACA_MAPA_H = _PRACA_MAPA_W * 1000.0 / 1400.0  # proporcao dos PNGs de `relatorio_praca_mapas`


def _praca_texto(texto: Any) -> str:
    from motor_expansao.dashboard.relatorio_praca import texto_pdf

    return _ascii(texto_pdf(texto))


def _praca_pct(valor: float | None) -> str:
    return TEXTO_SEM_DADO if valor is None else _format_number(valor, 0, "%")


def _praca_calor_page(pdf: _UltraPDF, result: dict[str, Any], praca: Any,
                      assets: dict[str, bytes | None], *,
                      primary: tuple[int, int, int], secondary: tuple[int, int, int]) -> None:
    from motor_expansao.dashboard.relatorio_praca import (
        TEXTO_POP_MUNICIPAL,
        TITULO_MAPAS_CALOR_CIDADE,
    )

    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, TITULO_MAPAS_CALOR_CIDADE, rgb=primary)
    y = 96.0
    # Sem o mapa de densidade (base que so' tem a populacao do municipio), a renda ocupa o slide
    # inteiro em vez de dividir a pagina com uma moldura vazia.
    tem_densidade = "calor_cidade_densidade" in praca.mapas
    largura = _PRACA_MAPA_W if tem_densidade else _PRACA_MAPA_W * 1.4
    altura = largura * 1000.0 / 1400.0
    legenda = (
        f"{praca.n_hexagonos_cidade} hexágonos de {praca.municipio}. Renda média domiciliar "
        + ("e densidade (habitantes por km² do hexágono), " if tem_densidade else "")
        + "com as cores do slide Mapas de calor e as faixas pelos quintis da própria cidade: "
        "o mapa compara bairros da mesma praça, não cidades."
    )
    if praca.renda_municipal:
        legenda += " Nesta base a renda é a do município inteiro, então o mapa de renda sai de uma cor só."
    if praca.populacao_municipal:
        legenda += " " + TEXTO_POP_MUNICIPAL
    texto_nota = _praca_texto(legenda)
    largura_nota = _PAGE_W - 72.0
    # A nota tem de caber ACIMA do rodape: `auto_page_break` e OFF, e sem o mapa de densidade o mapa largo (602 x 430) empurrava a nota para y = 550,
    # fora da pagina de 540. O mapa encolhe na altura (o fit-contain preserva a proporcao).
    limite_nota = _PAGE_H - 22.0 - 4.0 - _altura_note(pdf, largura_nota, texto_nota)
    altura = min(altura, limite_nota - 24.0 - y)
    chaves = [("calor_cidade_renda_domiciliar", primary)]
    if tem_densidade:
        chaves.append(("calor_cidade_densidade", secondary))
    for idx, (chave, cor) in enumerate(chaves):
        _draw_framed_map(
            pdf, praca.mapas.get(chave), max_w=largura, max_h=altura,
            x_anchor=36.0 + idx * (largura + 28.0), y_anchor=y, border_rgb=cor,
        )
    _draw_note(pdf, 36.0, y + altura + 24.0, largura_nota, texto_nota)


def _praca_pressao_page(pdf: _UltraPDF, result: dict[str, Any], praca: Any,
                        assets: dict[str, bytes | None], *,
                        primary: tuple[int, int, int], secondary: tuple[int, int, int]) -> None:
    from motor_expansao.dashboard.relatorio_praca import TITULO_PRESSAO_CONCORRENCIAL

    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, TITULO_PRESSAO_CONCORRENCIAL, rgb=primary)
    _draw_framed_map(pdf, praca.mapas.get("pressao_cidade"), max_w=540.0, max_h=386.0,
                     x_anchor=34.0, y_anchor=90.0, border_rgb=primary)

    p = praca.pressao
    raio_txt = f"{p.raio_m / 1000:.1f}".replace(".", ",")
    px = 610.0
    pw = _PAGE_W - px - 36.0
    linhas = [
        ("Concorrentes", _format_number(p.n_concorrentes, 0)),
        ("das quais independentes", _format_number(p.n_independentes, 0)),
        ("Unidades Ultra", _format_number(p.n_ultra, 0)),
        # Sem "hexagonos sob algum raio / com 3+ raios / maximo de raios" desde 2026-10-20 (Juan):
        # numeros de metodo, nao de leitura. Seguem em `praca.pressao` para quem precisar.
    ]
    y = _info_panel(pdf, px, 76.0, pw, f"Raios de {raio_txt} km", linhas, accent=secondary)

    if p.redes:
        y += 14.0
        pdf.set_text_color(*secondary)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_xy(px, y)
        pdf.cell(pw, 14, _ascii("Redes com mais unidades"))
        y += 20.0
        for rede, n in p.redes[:5]:
            tem_logo = _draw_rede_logo(pdf, rede, px, y)
            pdf.set_text_color(45, 45, 45)
            pdf.set_font("Helvetica", "", 11)
            pdf.set_xy(px + (20.0 if tem_logo else 0.0), y + 1)
            pdf.cell(pw - 60, 13, _ascii(_encurtar(pdf, _prettify_rede(rede), pw - 80)))
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_xy(px + pw - 40, y + 1)
            pdf.cell(40, 13, _ascii(_format_number(n, 0)), align="R")
            y += 18.0
    _draw_note(
        pdf, px, max(y + 8.0, _PAGE_H - 76.0), pw,
        f"Cada círculo é a área de influência de {raio_txt} km que o motor usa para descontar a "
        "concorrência do residual. Onde os círculos se sobrepõem a cor escurece: mais academias "
        "disputando o mesmo público. Conta o centro de cada hexágono.",
    )


def _praca_crescimento_page(pdf: _UltraPDF, result: dict[str, Any], praca: Any,
                            assets: dict[str, bytes | None], *,
                            primary: tuple[int, int, int], secondary: tuple[int, int, int]) -> None:
    from motor_expansao.dashboard.relatorio_praca import (
        ROTULO_POUCOS_EMPREGOS,
        TITULO_COMO_A_CIDADE_ESTA_INDO,
    )

    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, TITULO_COMO_A_CIDADE_ESTA_INDO, rgb=primary)
    c = praca.crescimento
    x = 36.0
    w = _PAGE_W - 72.0
    # Sem frase (no Brasil o veredito "E' praca para entrar" saiu pela DEC-077) a caixa fica so'
    # com o nome da cidade, e os paineis sobem.
    frase_h = 96.0 if str(c.frase or "").strip() else 44.0
    _rounded_panel(pdf, x, 76.0, w, frase_h, border_rgb=secondary)
    pdf.set_text_color(*secondary)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(x + 16, 90.0)
    pdf.cell(w - 32, 16, _ascii(_local_label(result)))
    pdf.set_text_color(45, 45, 45)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_xy(x + 16, 112.0)
    pdf.multi_cell(w - 32, 16, _praca_texto(c.frase))

    if c.linhas:
        metade = (len(c.linhas) + 1) // 2
        col_w = (w - 20.0) / 2.0
        for idx, bloco in enumerate((c.linhas[:metade], c.linhas[metade:])):
            if bloco:
                _info_panel(
                    pdf, x + idx * (col_w + 20.0), 76.0 + frase_h + 18.0, col_w,
                    "Emprego e empresas" if idx == 0 else "Salário e setor",
                    [(_praca_texto(r), _praca_texto(v)) for r, v in bloco],
                    accent=primary if idx == 0 else secondary,
                    subtitulos={_praca_texto(k): _praca_texto(v) for k, v in c.subtitulos.items()},
                )
    # O que cada numero e' (Juan, 2026-10-20 e 2026-10-21). O aviso de poucos empregos formais
    # so' e' explicado quando a linha existe (cidade com menos de 20 mil vinculos).
    fragil = any(r == _praca_texto(ROTULO_POUCOS_EMPREGOS) or r == ROTULO_POUCOS_EMPREGOS for r, _ in c.linhas)
    _draw_note(
        pdf, x, _PAGE_H - 92.0, w,
        "Saldo de empresas = empresas abertas menos empresas fechadas (baixadas) na Receita Federal no "
        "período. Salário de contratação = salário médio de quem foi contratado com carteira "
        "nos últimos 12 meses (CAGED); a variação compara com os 12 meses anteriores. "
        + ("Poucos empregos formais (menos de 20 mil) = poucas contratações já mexem muito na tendência "
           "e na variação do emprego; leia esses dois números com cautela. " if fragil else "")
        + "Mediana = valor do meio entre os municípios do estado. Fontes: CAGED, RAIS e Receita "
        "Federal (atualização trimestral). Contexto sobre a praça: não é previsão de desempenho de unidade.",
    )


#: Cores das duas tabelas de "Onde crescer". O azul e' o `_COR_TOP_SOCIO` do mapa; o verde e' mais
#: escuro que o `_COR_TOP` (22, 163, 74) do mapa para o texto branco do cabecalho ler (contraste
#: 4,9:1 contra 3,3:1) -- e' o verde da tabela da Argentina.
_COR_LISTA_1 = (20, 130, 65)
_COR_LISTA_2 = (37, 99, 235)

#: Motivo que so' o PDF usa, fora do vocabulario do modulo: a recomendacao recusou a base da cidade
#: (coluna faltando, hexagono repetido) e o "Onde crescer" sai indisponivel, nunca com a lista de
#: outra regua (DEC-077). Quem o grava e' `api.service._praca_da_cidade`.
MOTIVO_BASE_RECUSADA = "base_recusada"
_ROTULO_MOTIVO_DO_PDF = {
    MOTIVO_BASE_RECUSADA: "Recomendação indisponível: a base desta cidade não passou na checagem",
}


#: Fonte do nome da regiao quando ele vai em duas linhas na tabela de "Onde crescer".
_FONTE_REGIAO_2_LINHAS = 7.5


def _linhas_da_regiao(pdf: _UltraPDF, nome: str, largura: float) -> list[str]:
    """O nome da regiao em UMA linha (fonte da tabela) ou em DUAS (fonte menor), sem perder o 2o
    bairro do desempate "A / B" (DEC-077 item 10).

    Cortar pelo fim apagava justamente o que separa duas regioes do mesmo bairro dominante:
    "Parque Residencial Aquarius / Jardim Aquarius" e "... / Jardim Apolo" saiam iguais, e em Passo
    Fundo os dois "Regiao do Bairro Centro ... / Regiao do Bairro <X>" tambem. Quando nao cabe, o
    dominante vai na 1a linha e "/ B" na 2a; sem barra, quebra por palavra. Cada linha ainda e'
    encurtada se passar da largura.
    """
    texto = _ascii(nome)
    if pdf.get_string_width(texto) <= largura:
        return [texto]
    tamanho = pdf.font_size_pt
    pdf.set_font_size(_FONTE_REGIAO_2_LINHAS)
    try:
        if " / " in texto:
            dominante, segundo = texto.split(" / ", 1)
            return [_encurtar(pdf, dominante, largura), _encurtar(pdf, f"/ {segundo}", largura)]
        palavras = texto.split()
        primeira = ""
        for i, palavra in enumerate(palavras):
            candidata = f"{primeira} {palavra}".strip()
            if primeira and pdf.get_string_width(candidata) > largura:
                return [_encurtar(pdf, primeira, largura), _encurtar(pdf, " ".join(palavras[i:]), largura)]
            primeira = candidata
        return [_encurtar(pdf, texto, largura)]
    finally:
        pdf.set_font_size(tamanho)


def _onde_crescer_recomendacao(pdf: _UltraPDF, rec: Any, rotulos: dict[str, str],
                               x: float, w: float) -> None:
    """As duas tabelas da recomendacao unica (DEC-077, Brasil), no lugar das listas por coluna.

    Mata Virgem em ordem de residual e Premium em ordem de populacao, `vagas_por_segmento` vagas
    cada, como o modulo devolve -- nada e' reordenado aqui. Vaga sem candidato sai sinalizada com
    o motivo do modulo; segmento indisponivel (sem o carimbo k da malha, ou base recusada) vira uma
    linha so' com o motivo, sem numero. Nome = `rotulos_das_regioes` (o bairro com mais moradores);
    sem bairro, o municipio, e a nota diz isso. Numeros e criterios da nota saem da regua
    (`rec.regra`); a frase do mapa, das vagas preenchidas.
    """
    from motor_expansao.recomendacao import ROTULO_MOTIVO, ROTULO_SEGMENTO, ItemRecomendado

    colunas = (("#", 18.0), ("Região", 116.0), ("Residual (alunos)", 66.0),
               ("População", 66.0), ("Renda domiciliar", 78.0))
    escala = w / sum(c[1] for c in colunas)
    larguras = [c[1] * escala for c in colunas]
    renda_municipal = False
    sem_bairro = False

    def _motivo(motivo: str) -> str:
        return ROTULO_MOTIVO.get(motivo) or _ROTULO_MOTIVO_DO_PDF.get(motivo, motivo)

    def _linha(y: float, i: int, valores: tuple[str | list[str], ...] | None, texto: str | None = None,
               numero: str | None = None) -> float:
        pdf.set_fill_color(*((255, 255, 255) if i % 2 == 0 else (240, 242, 245)))
        pdf.set_text_color(45, 45, 45)
        if valores is not None:
            xx = x
            for valor, lw in zip(valores, larguras, strict=True):
                pdf.set_xy(xx, y)
                if isinstance(valor, list) and len(valor) > 1:
                    # Nome em duas linhas (`_linhas_da_regiao`), na mesma altura de linha.
                    pdf.cell(lw, 20, "", fill=True)
                    tamanho = pdf.font_size_pt
                    pdf.set_font_size(_FONTE_REGIAO_2_LINHAS)
                    for k, parte in enumerate(valor):
                        pdf.set_xy(xx, y + 2.0 + 8.0 * k)
                        pdf.cell(lw, 8, _ascii(parte), align="C")
                    pdf.set_font_size(tamanho)
                else:
                    pdf.cell(lw, 20, _ascii(valor[0] if isinstance(valor, list) else valor),
                             align="C", fill=True)
                xx += lw
        else:
            # Vaga vazia: posicao + o motivo numa celula so', para nao parecer regiao sem dado. O
            # segmento indisponivel vem sem numero (`numero=""`): o motivo vale para a lista toda.
            pdf.set_xy(x, y)
            pdf.cell(larguras[0], 20, _ascii(str(i + 1) if numero is None else numero), align="C", fill=True)
            resto = w - larguras[0]
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_xy(x + larguras[0], y)
            pdf.cell(resto, 20, _ascii(_encurtar(pdf, texto or "", resto - 6)), align="L", fill=True)
            pdf.set_font("Helvetica", "", 9)
        return y + 20.0

    def _tabela(y: float, seg: Any, titulo: str, cor: tuple[int, int, int]) -> float:
        nonlocal renda_municipal, sem_bairro
        pdf.set_text_color(*cor)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_xy(x, y)
        pdf.cell(w, 14, _ascii(titulo))
        y += 18.0
        pdf.set_fill_color(*cor)
        pdf.set_text_color(*_BRANCO)
        pdf.set_font("Helvetica", "B", 8)
        pdf.rect(x, y, w, 26.0, style="F")
        xx = x
        for (rotulo, _), lw in zip(colunas, larguras, strict=True):
            uma_linha = pdf.get_string_width(_ascii(rotulo)) <= lw - 4
            pdf.set_xy(xx, y + (7.0 if uma_linha else 1.0))
            pdf.multi_cell(lw, 12, _ascii(rotulo), align="C", new_x="RIGHT", new_y="TOP")
            xx += lw
        y += 28.0
        pdf.set_font("Helvetica", "", 9)
        if seg.status == "indisponivel":
            motivo = seg.vagas[0].motivo if seg.vagas else "renda_indisponivel"
            return _linha(y, 0, None, _motivo(motivo), numero="")
        for i, vaga in enumerate(seg.vagas):
            if isinstance(vaga, ItemRecomendado):
                nome = rotulos.get(vaga.hex_id)
                if not nome:
                    sem_bairro = True
                    nome = vaga.nome_municipio or rec.recorte.nome or TEXTO_SEM_DADO
                renda = _renda(vaga.renda_domiciliar)
                if vaga.renda_municipal:
                    renda_municipal = True
                    renda += "*"
                y = _linha(y, i, (
                    str(vaga.posicao),
                    _linhas_da_regiao(pdf, str(nome), larguras[1] - 4),
                    _format_number(vaga.residual, 0),
                    _format_number(vaga.populacao, 0),
                    renda,
                ))
            else:
                y = _linha(y, i, None, f"Vaga vazia: {_motivo(vaga.motivo)}")
        return y

    y = _tabela(80.0, rec.mata_virgem, f"{ROTULO_SEGMENTO['mata_virgem']} (ordem: residual)", _COR_LISTA_1)
    y = _tabela(y + 14.0, rec.premium, f"{ROTULO_SEGMENTO['premium']} (ordem: população)", _COR_LISTA_2)
    mv, pr = rec.regra.mata_virgem, rec.regra.premium

    def _piso(populacao_min: float | None) -> str:
        return f" e {_format_number(populacao_min, 0)} habitantes ou mais" if populacao_min is not None else ""

    # O mapa so' tem a cor do segmento que ganhou regiao; sem nenhuma, a cidade sai em cinza.
    cores = [f"{cor} = {ROTULO_SEGMENTO[s]}" for s, cor in (("mata_virgem", "verde"), ("premium", "azul"))
             if any(isinstance(v, ItemRecomendado) for v in getattr(rec, s).vagas)]
    if cores:
        mapa = f"No mapa, {' e '.join(cores)}, numerados como nas tabelas. "
    elif "indisponivel" in (rec.mata_virgem.status, rec.premium.status):
        mapa = ""
    else:
        mapa = "No mapa, a cidade em cinza: nenhuma região atende à régua. "
    _draw_note(
        pdf, x, y + 10.0, w,
        f"Mata Virgem = renda domiciliar a partir de {_renda(mv.renda_domiciliar_min)} e "
        f"{'residual medido' if mv.exige_residual_medido else 'residual'} a partir de "
        f"{_format_number(mv.residual_min, 0)} alunos{_piso(mv.populacao_min)}, em ordem de residual. "
        f"Premium = região que não é Mata Virgem, com score censitário a partir de "
        f"{_format_number(pr.score_min, 0)}{_piso(pr.populacao_min)}"
        f"{' e residual medido' if pr.exige_residual_medido else ''}, em ordem de população. Região = "
        "hexágono de ~5 km², com o nome do bairro de mais moradores"
        + (" (sem bairro mapeado, o do município)" if sem_bairro else "")
        + f". Vaga vazia = nenhuma outra região da cidade atende à régua. {mapa}"
        f"Régua {rec.regra.versao} ({rec.regra.dec})."
        + (" * Renda do município: a região não tem renda por setor." if renda_municipal else ""),
    )


def _praca_onde_crescer_page(pdf: _UltraPDF, result: dict[str, Any], praca: Any,
                             assets: dict[str, bytes | None], *,
                             primary: tuple[int, int, int], secondary: tuple[int, int, int]) -> None:
    """"Onde crescer" com DUAS tabelas (Juan, 2026-10-20): top 5 por residual e top 5 por score
    socioeconomico, cada uma pelo valor absoluto. O mapa marca as duas listas em cores proprias.
    Substitui a lista unica pelo indice de praca e a pagina "Comparacao das Regioes".

    No Brasil (`praca.recomendacao`, DEC-077) as duas tabelas sao a recomendacao unica -- Mata
    Virgem e Premium do modulo `motor_expansao.recomendacao` --, com o mesmo layout e o mesmo mapa
    de duas cores; muda so' de onde vem a lista (Felipe, 2026-10-21)."""
    from motor_expansao.dashboard.relatorio_praca import TITULO_ONDE_CRESCER

    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, TITULO_ONDE_CRESCER, rgb=primary)
    _draw_framed_map(pdf, praca.mapas.get("onde_crescer"), max_w=_PRACA_MAPA_W, max_h=_PRACA_MAPA_H,
                     x_anchor=34.0, y_anchor=96.0, border_rgb=primary)

    bairros = result.get("bairros_por_hex") or {}
    x = 34.0 + _PRACA_MAPA_W + 30.0
    w = _PAGE_W - x - 36.0
    rec = getattr(praca, "recomendacao", None)
    if rec is not None:
        _onde_crescer_recomendacao(pdf, rec, dict(getattr(praca, "rotulos_recomendacao", None) or {}), x, w)
        return
    # Densidade no lugar do score (Juan, 2026-10-20): o score ja' ordena a 2a lista e, em Sao
    # Paulo, satura em 100 -- a coluna repetia "100,0". A densidade mostra a "gente" do score.
    colunas = (("#", 18.0), ("Bairro", 110.0), ("Residual (alunos)", 70.0),
               ("Densidade (hab/km2)", 70.0), ("Renda domiciliar", 76.0))
    escala = w / sum(c[1] for c in colunas)
    larguras = [c[1] * escala for c in colunas]

    def _tabela(y: float, titulo: str, df: Any, cor: tuple[int, int, int]) -> float:
        pdf.set_text_color(*cor)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_xy(x, y)
        pdf.cell(w, 14, _ascii(titulo))
        y += 18.0
        pdf.set_fill_color(*cor)
        pdf.set_text_color(*_BRANCO)
        pdf.set_font("Helvetica", "B", 8)
        pdf.rect(x, y, w, 26.0, style="F")
        xx = x
        for (rotulo, _), lw in zip(colunas, larguras, strict=True):
            uma_linha = pdf.get_string_width(_ascii(rotulo)) <= lw - 4
            pdf.set_xy(xx, y + (7.0 if uma_linha else 1.0))
            pdf.multi_cell(lw, 12, _ascii(rotulo), align="C", new_x="RIGHT", new_y="TOP")
            xx += lw
        y += 28.0
        pdf.set_font("Helvetica", "", 9)
        linhas = [] if df is None or getattr(df, "empty", True) else df.to_dict("records")
        for i, row in enumerate(linhas):
            pdf.set_fill_color(*((255, 255, 255) if i % 2 == 0 else (240, 242, 245)))
            pdf.set_text_color(45, 45, 45)
            bairro = bairros.get(str(row.get("hex_id"))) or TEXTO_SEM_DADO
            valores = (
                str(row.get("posicao", i + 1)),
                _encurtar(pdf, str(bairro), larguras[1] - 4),
                _format_number(row.get("oferta_efetiva_disponivel"), 0),
                _format_number(row.get("densidade_hab_km2"), 0),
                _renda(row.get("renda_domiciliar")),
            )
            xx = x
            for valor, lw in zip(valores, larguras, strict=True):
                pdf.set_xy(xx, y)
                pdf.cell(lw, 20, _ascii(valor), align="C", fill=True)
                xx += lw
            y += 20.0
        if not linhas:
            pdf.set_text_color(45, 45, 45)
            pdf.set_xy(x, y + 2)
            pdf.cell(w, 16, _ascii("Sem dado para esta lista."))
            y += 20.0
        return y

    y = _tabela(80.0, "Maior residual (alunos sem academia)", getattr(praca, "top_residual", None), (20, 130, 65))
    y = _tabela(y + 14.0, "Maior socioeconômico (score)", getattr(praca, "top_socio", None), (37, 99, 235))
    _draw_note(
        pdf, x, y + 10.0, w,
        "Cada lista são as 5 regiões (hexágonos de ~5 km²) com o maior valor absoluto daquele "
        "indicador na cidade. Residual = alunos sem academia na região; socioeconômico = maior "
        "score censitário (renda e população); empatadas no teto de 100, vem antes a de renda e "
        "população maiores. Densidade = moradores por km². No mapa, verde = maior residual e azul "
        "= maior socioeconômico, numerados como nas tabelas; o que está nas duas listas sai "
        "cortado ao meio, com a posição em cada uma.",
    )


# Regua da Sintese: tercos (p33 / mediana / p67) entre os 313 municipios BR com 100 mil+
# habitantes (penetracao = consumido / (consumido + residual); residual por mil habitantes),
# medidos com `scripts/medir_regua_sintese.py` na base que este PDF le em PRODUCAO
# (`outputs/hexagonos_dashboard_enriquecido`, 27 UFs, regenerada em 2026-10-25; emenda de
# 2026-10-29 da DEC-011). As cidades pequenas ficam fora da regua: a maioria nao tem academia
# mapeada e a mediana do pais inteiro e' 0%. Antes da regua os dois cards diziam sempre
# "penetracao baixa" e "residual significativo", qualquer que fosse o numero. Leitura de
# COMPARACAO, nao previsao de desempenho.
#
# A primeira regua (10,5 / 15,8 / 22,8 e 138 / 151 / 169) saiu de uma base local de 2026-10-20,
# sem script, e na producao punha 247 das 313 cidades em "Mercado maduro" e 293 em "Residual
# abaixo da maioria". Remedir com o script, nunca editar a mao, quando uma DEC mudar consumo,
# residual ou capacidade: de 21/10 a 25/10 a variacao foi de 0,1 p.p.
_SINTESE_PENETRACAO_TERCOS = (33.0, 42.3, 49.8)
_SINTESE_RESIDUAL_MIL_TERCOS = (78.0, 90.0, 104.0)


def _texto_penetracao_sintese(pen: Any) -> str:
    v = _safe_float(pen)
    p33, med, p67 = _SINTESE_PENETRACAO_TERCOS
    ref = f"(mediana das cidades com 100 mil+ hab.: {_format_number(med, 1)}%)"
    if math.isnan(v):
        return "Penetração sem dado: não há oferta mapeada suficiente para medir."
    if v <= 0:
        return "Mercado sem academias mapeadas: quase todo o público ainda está fora."
    if v < p33:
        return f"Mercado com espaço: penetração abaixo da maioria das cidades grandes {ref}."
    if v <= p67:
        return f"Mercado em desenvolvimento: penetração na faixa típica das cidades grandes {ref}."
    return (f"Mercado maduro: penetração acima da maioria das cidades grandes {ref}; crescer "
            "aqui é disputar quem já treina.")


def _texto_residual_sintese(result: dict[str, Any]) -> tuple[str, str]:
    residual = _safe_float(result.get("residual_total_alunos"))
    pop = _safe_float(result.get("pop_total_municipio"))
    aprov = _safe_float(result.get("soma_oferta_amarelos"))
    por_mil = 1000.0 * residual / pop if pop and pop > 0 and not math.isnan(residual) else float("nan")
    p33, med, p67 = _SINTESE_RESIDUAL_MIL_TERCOS
    valor = f"{_format_number(residual, 0)} alunos"
    if math.isnan(por_mil):
        return valor, "Residual: alunos sem academia regular na cidade."
    # Mesmas palavras do card de penetracao (2026-10-21): a regua e' a dos tercos das cidades
    # grandes, com a mediana citada -- "abaixo da media" contradizia o numero do lado.
    if por_mil < p33:
        nivel = "Residual abaixo da maioria das cidades grandes"
    elif por_mil <= p67:
        nivel = "Residual na faixa típica das cidades grandes"
    else:
        nivel = "Residual acima da maioria das cidades grandes"
    texto = (f"{nivel}: {_format_number(por_mil, 0)} alunos sem academia por mil habitantes "
             f"(mediana das cidades grandes: {_format_number(med, 0)}).")
    if residual > 0 and not math.isnan(aprov):
        # DEC-077 (Brasil): sem "aprovadas" -- a parte do residual nas regioes de 2.000 ou mais.
        onde = (
            f"nas regiões com residual a partir de {_format_number(OFERTA_DESTAQUE_MIN, 0)} alunos"
            if _resposta_unica(result) else "nas regiões aprovadas"
        )
        texto += f" {_format_number(100.0 * aprov / residual, 0)}% dele está {onde}."
    return valor, texto


def _sintese_page(pdf: _UltraPDF, result: dict[str, Any], assets: dict[str, bytes | None], *,
                  primary: tuple[int, int, int] = ULTRA_TURQUESA) -> None:
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    # DEC-077 (Brasil): a recomendacao e' so' o Top 10 do "Onde crescer"; a Sintese e' diagnostico.
    _draw_title_band(pdf, "Síntese - Diagnóstico" if _resposta_unica(result)
                     else "Síntese - Diagnóstico & Recomendação", rgb=primary)
    residual_valor, residual_texto = _texto_residual_sintese(result)
    cards = [
        (
            ULTRA_MAGENTA,
            _format_number(result.get("penetracao_fitness_pct"), 1, "% de penetração"),
            _texto_penetracao_sintese(result.get("penetracao_fitness_pct")),
        ),
        (
            ULTRA_TURQUESA,
            residual_valor,
            residual_texto,
        ),
        (
            ULTRA_LARANJA,
            f"{_format_number(result.get('n_zonas_geo'), 0)} zonas de atuação",
            _texto_zonas_sintese(result.get("zonas_geo")),
        ),
    ]
    if _resposta_unica(result):
        # DEC-077 (Brasil): o card de zonas sai ate' chegarem os dados do gestor (Felipe,
        # 2026-10-21), junto com Expansao de Dominio e Bairros por Zona.
        cards = cards[:2]
    margin_x = 36.0
    gap = 18.0
    card_w = (_PAGE_W - 2 * margin_x - (len(cards) - 1) * gap) / len(cards)
    # FU1: cards mais baixos e CENTRALIZADOS verticalmente (evita excesso de espaco vazio).
    card_h = 210.0
    top = _centered_y(card_h)
    for idx, (_accent, valor, texto) in enumerate(cards):
        x = margin_x + idx * (card_w + gap)
        # AJUSTE 1: um contorno por card, ciclo turquesa -> magenta -> laranja.
        # AJUSTE 3 (FU1): a cor do NUMERO em destaque casa EXATAMENTE com a moldura do
        # card (mesma sequencia `_ciclo_cor`): card 1 turquesa / 2 magenta / 3 laranja.
        cor_card = _ciclo_cor(idx)
        _rounded_panel(pdf, x, top, card_w, card_h, border_rgb=cor_card)
        pdf.set_text_color(*cor_card)
        pdf.set_font("Helvetica", "B", 22)
        pdf.set_xy(x + 16, top + 30)
        pdf.multi_cell(card_w - 32, 26, _ascii(valor))
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "", 12)
        pdf.set_xy(x + 16, top + 104)
        pdf.multi_cell(card_w - 32, 16, _ascii(texto))
    pdf.set_xy(36, _PAGE_H - 36)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.cell(_PAGE_W - 72, 12, _ascii("Estratégia e Growth - Ultra Academia - Motor de Expansão - 2026"))


def _espaco_academias_page(pdf: _UltraPDF, result: dict[str, Any], assets: dict[str, bytes | None], *,
                           primary: tuple[int, int, int] = ULTRA_TURQUESA) -> None:
    """Pagina 8 — big numbers + breakdown de concorrentes por rede (D8) + carimbo de versao."""
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, "Espaço e academias", rgb=primary)
    # DEC-077 (Brasil): o espaco so' como leitura, com o rotulo do Felipe (2026-10-21).
    resposta_unica = _resposta_unica(result)
    rotulo_espaco = (
        f"Espaço para academias: {_rotulo_espaco_leitura()}"
        if resposta_unica else "Espaço total p/ novas academias"
    )
    big = [
        (ULTRA_TURQUESA, _format_number(result.get("n_ultra"), 0), "Unidades Ultra mapeadas"),
        (ULTRA_MAGENTA, _format_number(result.get("n_concorrentes"), 0), "Unidades concorrentes mapeadas"),
        (ULTRA_LARANJA, _format_number(result.get("espaco_para_academias"), 0), rotulo_espaco),
    ]
    margin_x = 36.0
    gap = 18.0
    card_w = (_PAGE_W - 2 * margin_x - 2 * gap) / 3.0
    top = 80.0
    for idx, (accent, valor, label) in enumerate(big):
        x = margin_x + idx * (card_w + gap)
        # AJUSTE 1: um contorno por big number, ciclo turquesa -> magenta -> laranja.
        _rounded_panel(pdf, x, top, card_w, 150.0, border_rgb=_ciclo_cor(idx))
        pdf.set_text_color(*accent)
        pdf.set_font("Helvetica", "B", 40)
        pdf.set_xy(x + 16, top + 38)
        pdf.cell(card_w - 32, 44, _ascii(valor))
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_xy(x + 16, top + 104)
        pdf.multi_cell(card_w - 32, 14, _ascii(label))

    # Breakdown de concorrentes por rede (D8: so redes realmente mapeadas).
    # AJUSTE 1: bloco de breakdown na cor SEGUINTE do ciclo (idx 3 -> turquesa).
    breakdown_border = _ciclo_cor(3)
    bd_x, bd_y = margin_x, 246.0
    bd_w, bd_h = _PAGE_W - 2 * margin_x, _PAGE_H - 70.0 - bd_y
    _rounded_panel(pdf, bd_x, bd_y, bd_w, bd_h, border_rgb=breakdown_border)
    por_rede = result.get("concorrentes_por_rede") or {}
    pdf.set_text_color(*breakdown_border)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_xy(margin_x + 14, bd_y + 10)
    pdf.cell(bd_w - 28, 16, _ascii("Concorrentes por rede"))
    yy = bd_y + 36.0
    if not por_rede:
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_xy(margin_x + 14, yy)
        pdf.cell(bd_w - 28, 14, _ascii("Nenhuma rede concorrente mapeada no município."))
    else:
        col_w = (bd_w - 28) / 3.0
        for idx, (rede, cnt) in enumerate(sorted(por_rede.items(), key=lambda kv: kv[1], reverse=True)):
            col = idx % 3
            x = margin_x + 14 + col * col_w
            if col == 0 and idx > 0:
                yy += 24
            if yy > bd_y + bd_h - 22:
                break
            # Slide 8: logo da rede (fallback bullet) + nome prettificado + contagem.
            drew_logo = _draw_rede_logo(pdf, rede, x, yy, size=14.0)
            if not drew_logo:
                pdf.set_fill_color(*ULTRA_MAGENTA)
                pdf.ellipse(x + 3, yy + 4, 8, 8, style="F")
            pdf.set_text_color(45, 45, 45)
            pdf.set_font("Helvetica", "", 11)
            pdf.set_xy(x + 20, yy)
            pdf.cell(col_w - 24, 14, _ascii(f"{cnt} {_prettify_rede(str(rede))}"))

    pdf.set_xy(36, _PAGE_H - 48)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.multi_cell(
        _PAGE_W - 72, 11,
        _ascii(
            "Método: contagem de pins dentro do território (H3 res 7) - Espaço = "
            + (f"residual das regiões com {_format_number(OFERTA_DESTAQUE_MIN, 0)} ou mais alunos / 2.500."
               if resposta_unica else "soma dos hexágonos destacados / 2.500.")
        ),
    )


def gerar_pdf_relatorio_municipal(
    municipio_result: dict[str, Any],
    mapas: dict[str, bytes] | None = None,
    *,
    ultra_dir: Path | str | None = None,
    solicitante: str | None = None,
    report_id: str | None = None,
    versao: str | None = None,
    unidade: str = UNIDADE_BAIRRO,
    praca: PracaDaCidade | None = None,
) -> bytes:
    """Gera o PDF do Relatorio Municipal.

    `unidade` decide a leitura dos mapas (bairro ou hexagono), nao o numero de paginas: 11 nas
    duas (as de `PDF_SECTION_HEADERS`), mais uma por parte dos Bairros Oficiais em municipio
    grande. No Brasil (`resposta_unica`, DEC-077) Expansao de Dominio, Bairros por Zona e a
    Visao Geral do Municipio nao saem: 8.

    `mapas` = dict `{"cobertura","bairros","resumo","score","residual","dominio"}` (camadas PNG);
    ausente -> paginas com "Mapa indisponivel". `ultra_dir` aponta os assets de branding (fallback
    gracioso para cor solida). `solicitante` carimba a marca d'agua em todas as paginas
    (anti-PII). `versao` sobrescreve o carimbo de versao do rodape. READ-ONLY sobre o M1.

    `praca` (pedido do Felipe, 2026-09-10) acrescenta QUATRO paginas: "Mapas de calor da cidade",
    "Pressao concorrencial" e "Como a cidade esta indo" (depois de Residual Fitness) e "Onde
    crescer" (antes da Sintese). `None` = PDF identico ao de antes do parametro.
    """
    assets = _load_branding_assets(ultra_dir)
    mapas = mapas or {}
    if versao:
        municipio_result = {**municipio_result, "versao_contrato": versao}

    # Tom principal alterna por pagina de conteudo (turquesa <-> magenta).
    p1, s1 = _tema_bicolor(1)
    p2, s2 = _tema_bicolor(2)
    p3, s3 = _tema_bicolor(3)
    p4, _ = _tema_bicolor(4)
    p5, s5 = _tema_bicolor(5)
    p6, s6 = _tema_bicolor(6)
    p7, s7 = _tema_bicolor(7)
    p8, s8 = _tema_bicolor(8)
    p9, _ = _tema_bicolor(9)
    p10, _ = _tema_bicolor(10)
    p11, _ = _tema_bicolor(11)

    pdf = _UltraPDF()
    # Carimbo de versao (DEC-005 decisao 6) no `/Info`, nao mais no rodape das paginas: o
    # rodape saiu do PDF a pedido de Juan (2026-10-20) e a reprodutibilidade continua -- o
    # carimbo segue no arquivo, so' deixou de ser impresso.
    keywords = [str(municipio_result.get("versao_contrato") or VERSAO_CONTRATO_MUNICIPAL)]
    if report_id:
        # SEGUNDA camada do carimbo (D17): o `/Info` sobrevive a RECORTE de pagina e a
        # extracao de texto; a marca-d'agua sobrevive a screenshot e a reimpressao.
        pdf.set_subject(f"report_id {report_id}")
        keywords.insert(0, f"report_id={report_id}")
    pdf.set_keywords(" | ".join(keywords))
    _cover_page(pdf, municipio_result, assets)
    # Ordem de leitura pedida por Juan (2026-10-20): APRESENTA o municipio (bairros oficiais),
    # mostra os MAPAS do territorio (score, residual, calor, pressao e como a
    # cidade esta' indo), so' entao a OPORTUNIDADE (bairros aprovados, resumo e a conta do
    # espaco), a ESTRATEGIA (dominio, bairros por zona, onde crescer), a tabela e a sintese.
    # As cores seguem o ordinal de `_tema_bicolor` de cada pagina, nao a posicao: mudar a ordem
    # nao troca a cor de nenhuma pagina. Ordinais 12..15 = paginas da praca.
    _bairros_mapa_page(
        pdf, municipio_result, mapas.get("bairros"), assets, primary=p2, secondary=s2,
        mapas_partes={k: v for k, v in mapas.items() if k.startswith("bairros_parte_")},
    )
    _score_page(pdf, municipio_result, mapas.get("score"), assets, primary=p6, secondary=s6)
    _residual_page(pdf, municipio_result, mapas.get("residual"), assets, primary=p7, secondary=s7)
    if praca is not None:
        p12, s12 = _tema_bicolor(12)
        _praca_calor_page(pdf, municipio_result, praca, assets, primary=p12, secondary=s12)
        p13, s13 = _tema_bicolor(13)
        _praca_pressao_page(pdf, municipio_result, praca, assets, primary=p13, secondary=s13)
        p15, s15 = _tema_bicolor(15)
        _praca_crescimento_page(pdf, municipio_result, praca, assets, primary=p15, secondary=s15)
    if not _resposta_unica(municipio_result):
        # Brasil (Juan, 2026-10-22): a Visao Geral saiu. Com a resposta unica ela ficou neutra --
        # sem o verde de aprovado e sem a tabela -- e repetia o mapa do Resumo. A Argentina, sem
        # regua, segue com ela (a tabela BAIRROS APROVADOS mora nela).
        _cobertura_page(pdf, municipio_result, mapas.get("cobertura"), assets, primary=p1, secondary=s1)
    _resumo_page(pdf, municipio_result, mapas.get("resumo"), assets, primary=p5, secondary=s5)
    _espaco_explicado_page(pdf, municipio_result, mapas.get("espaco"), assets, primary=s5)
    if not _resposta_unica(municipio_result):
        # DEC-077 (Brasil): Expansao de Dominio e Bairros por Zona ficam fora ate' chegarem os
        # dados do gestor (Felipe, 2026-10-21); eram outras listas de "onde expandir". A
        # Argentina, sem regua de recomendacao, segue com as duas.
        _dominio_page(pdf, municipio_result, mapas.get("dominio"), assets, primary=p8, secondary=s8)
        _bairros_page(pdf, municipio_result, assets, primary=p9)
    if praca is not None:
        p14, s14 = _tema_bicolor(14)
        _praca_onde_crescer_page(pdf, municipio_result, praca, assets, primary=p14, secondary=s14)
    # "Comparacao das Regioes" saiu em 2026-10-20 (Juan): as duas tabelas de "Onde crescer" a
    # substituem. `tabela_hexes` segue no resultado (dado), so' nao e' impressa.
    _sintese_page(pdf, municipio_result, assets, primary=p10)
    _espaco_academias_page(pdf, municipio_result, assets, primary=p11)

    # Capa SEM marca-d'agua (Juan, 2026-10-20): a pagina 1 e' a que vai para apresentacao. O
    # carimbo segue nas paginas de conteudo e no `/Info`.
    wm_text = _watermark_text(solicitante, report_id)
    for page_number in range(2, pdf.pages_count + 1):
        pdf.page = page_number
        _draw_watermark(pdf, wm_text, rgb=_WATERMARK_RGB)

    return bytes(pdf.output())


def gerar_payloads_download_relatorio_municipal(
    municipio_result: dict[str, Any],
    mapas: dict[str, bytes] | None = None,
    *,
    filename_prefix: str | None = None,
    ultra_dir: Path | str | None = None,
    solicitante: str | None = None,
    report_id: str | None = None,
    versao: str | None = None,
    unidade: str = UNIDADE_BAIRRO,
    praca: PracaDaCidade | None = None,
) -> RelatorioMunicipalDownloadPayloads:
    uf = _slug(municipio_result.get("uf", ""))
    muni = _slug(municipio_result.get("nome_municipio", "municipio"))
    prefix = filename_prefix or f"relatorio_municipal_{uf}_{muni}".strip("_")
    pdf_bytes = gerar_pdf_relatorio_municipal(
        municipio_result, mapas, ultra_dir=ultra_dir, solicitante=solicitante, versao=versao,
        unidade=unidade, report_id=report_id, praca=praca,
    )
    return RelatorioMunicipalDownloadPayloads(
        pdf_bytes=pdf_bytes,
        pdf_filename=f"{prefix}.pdf",
    )
