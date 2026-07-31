"""Relatorio Municipal (BLK-RELMUN-01) — PDF de 9 paginas por municipio selecionado.

Modulo NOVO e disjunto. COEXISTE com o Relatorio Pontual Censitario (raio 1,5 km),
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
"""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fpdf import FPDF
from PIL import Image, ImageChops, ImageDraw, ImageFont

from motor_expansao.dashboard.censo_map import (
    _BASEMAP_TILES_URL_ENV,
    _fetch_labels,
)
from motor_expansao.dashboard.censo_map import (
    _atribuicao_tiles as _censo_atribuicao_tiles,
)
from motor_expansao.dashboard.competitors import _render_square_logo_tile
from motor_expansao.dashboard.constants import TEXTO_SEM_DADO
from motor_expansao.dashboard.utils import score_band_to_color

# ---------------------------------------------------------------------------
# Constantes de DISPLAY do relatorio (DEC-011 parte 2). Locais a este modulo;
# NAO mexem em flag_sam/DEC-006/DEC-007 (pipeline de mercado) nem no M1.
# BLK-RELMUN-03 (DEC-011 emenda): criterio de destaque passou a ser SO Residual Fitness (>=2000).
# ---------------------------------------------------------------------------
OFERTA_DESTAQUE_MIN = 2000.0
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
VERSAO_CONTRATO_MUNICIPAL = "BLK-RELMUN-01 | contrato v1 | score M1 INALTERADO"
METODO_RELATORIO_MUNICIPAL = "agregacao_municipal_h3_res7"

# Cabecalhos canonicos das 9 paginas. Renderizam em latin-1 (core font Helvetica do fpdf2),
# que cobre integralmente os acentos portugueses -- o que e PROIBIDO e tipografia fora de
# latin-1 (travessao/bullet/seta/reticencias/aspas curvas/(c)), que vira "?" silenciosamente
# via _ascii(..., errors="replace"). Cada string aparece nos bytes crus do PDF (compressao OFF).
PDF_SECTION_HEADERS = (
    "Potencial de Entrada de Novas Unidades",
    "Visão Geral do Município",
    "Resumo da Região",
    "Score Censitário",
    "Residual Fitness",
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

# Camada Resumo (alpha 200): destacado por procedencia + neutro (nao-destacado).
_HEX_DESTAQUE_RGBA = (*_COR_APROVADO_PROPRIO, 200)
_HEX_DESTAQUE_MUNICIPAL_RGBA = (*_COR_APROVADO_MUNICIPAL, 200)
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
_HEX_APROVADO_MUNICIPAL_RGBA = (*_COR_APROVADO_MUNICIPAL, 210)
_HEX_REPROVADO_RGBA = (*_COR_REPROVADO, 170)
_COBERTURA_LEGENDA = (
    ("Aprovado (dado próprio)", _COR_APROVADO_PROPRIO),
    ("Aprovado (fallback municipal)", _COR_APROVADO_MUNICIPAL),
    ("Reprovado", _COR_REPROVADO),
)
# Camada Resumo: legenda so das 2 categorias de aprovado (o neutro e contexto).
_RESUMO_LEGENDA = (
    ("Aprovado (dado próprio)", _COR_APROVADO_PROPRIO),
    ("Aprovado (fallback municipal)", _COR_APROVADO_MUNICIPAL),
)

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
_CREDITO_ULTRA = "Relatório gerado pelo Motor de Expansão - Ultra Academia"

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


def _prettify_rede(rede: str) -> str:
    """Nome legivel da rede: override conhecido ou title-case trocando '_' por espaco."""
    key = str(rede or "").strip()
    if not key:
        return "Concorrente"
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
    oferta = pd.to_numeric(df_muni.get("oferta_efetiva_disponivel"), errors="coerce")
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




def _carregar_bairros_por_hex(
    uf: str | None,
    cod_municipio: str | None,
    censo_geo_dir: Path | None,
) -> dict[str, str]:
    """A2.3: le a particao geo do municipio e mapeia `hex_id` res-7 -> localidade dominante.

    READ-ONLY e OFFLINE: usa `ler_particao_setores` (parquet local) para obter, por setor, o
    nome da localidade em CASCATA `nome_bairro` -> `nome_subdistrito` -> `nome_distrito` (decisao
    de produto 2026-06-24: bairros reais onde existem; lacunas usam o nivel mais grosso, ex.: SP
    usa distritos, DF idem), ignorando subdistrito/distrito que seja so o nome do municipio
    (redundante). Deriva o centroide do setor (do bbox), mapeia a `hex_id` res-7 via h3 (import
    lazy) e resolve a localidade DOMINANTE por hex (mais populosa vence). Fallback gracioso: sem
    `censo_geo_dir`/particao/coluna -> `{}` (Pagina 6 simplificada).
    """
    if censo_geo_dir is None or not uf or not cod_municipio:
        return {}
    _bbox_pop = ["bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy", "pop_total_setor_2022"]
    try:
        from motor_expansao.pipelines.materializar_setores_censitarios_geo import (
            ler_particao_setores,
        )

        # Tenta a cascata completa (bairro/subdistrito/distrito + nome_municipio p/ o guard); se a
        # particao for de um schema antigo sem essas colunas, cai para so `nome_bairro`.
        try:
            setores = ler_particao_setores(
                root=Path(censo_geo_dir), uf=str(uf), cod_municipio=str(cod_municipio),
                columns=["nome_bairro", "nome_subdistrito", "nome_distrito", "nome_municipio",
                         *_bbox_pop],
            )
        except Exception:
            setores = ler_particao_setores(
                root=Path(censo_geo_dir), uf=str(uf), cod_municipio=str(cod_municipio),
                columns=["nome_bairro", *_bbox_pop],
            )
    except Exception:
        return {}
    if setores is None or setores.empty or "nome_bairro" not in setores.columns:
        return {}

    import h3

    def _localidade(row: pd.Series) -> str | None:
        """Cascata bairro -> subdistrito -> distrito; ignora niveis grossos == nome do municipio."""
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

    # Para cada hex, soma a populacao por localidade; a mais populosa vence (dominante).
    pop_por_hex_bairro: dict[str, dict[str, float]] = {}
    for _, row in setores.iterrows():
        nome = _localidade(row)
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
            redes = conc_muni["rede"].astype(str)
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

    # FU1: penetracao MUNICIPAL significativa = consumo / (consumo + residual) * 100.
    # consumo_total = sum(oferta_consumida_mercado_estimada); residual_total = mercado_disponivel.
    consumo_serie = pd.to_numeric(
        df_muni.get("oferta_consumida_mercado_estimada"), errors="coerce"
    ).dropna()
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
        "bairros_por_zona": bairros_por_zona,
        "n_bairros_total": sum(int(z.get("n_bairros", 0)) for z in bairros_por_zona),
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


# Extensao MINIMA do viewport de foco (em metros 3857). Evita super-ampliar quando o foco
# e um unico/poucos hexes (~1,2 km de aresta no res-7): garante ao menos ~6 km de lado.
_FOCUS_MIN_SPAN_M = 6000.0
# Padding fracional aplicado ao bbox de foco (AJUSTE 1): margem de ~16% em cada eixo.
_FOCUS_PAD_FRAC = 0.16


def _focus_bounds_mercator(
    df_muni: pd.DataFrame,
    *,
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
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

    destaque = _hex_destacado_mask(df_muni)
    rel = df_muni.loc[destaque]
    if rel.empty:
        score = pd.to_numeric(df_muni.get("score_setor_2022_calibrado"), errors="coerce")
        oferta = pd.to_numeric(df_muni.get("oferta_efetiva_disponivel"), errors="coerce")
        pop = pd.to_numeric(df_muni.get("pop_total_setor_2022"), errors="coerce")
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
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)

    # Extensao MINIMA (evita super-ampliar com 1 hex isolado).
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    span_x = max(maxx - minx, _FOCUS_MIN_SPAN_M)
    span_y = max(maxy - miny, _FOCUS_MIN_SPAN_M)
    minx, maxx = cx - span_x / 2.0, cx + span_x / 2.0
    miny, maxy = cy - span_y / 2.0, cy + span_y / 2.0

    # Padding fracional.
    pad_x = span_x * _FOCUS_PAD_FRAC
    pad_y = span_y * _FOCUS_PAD_FRAC
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
) -> bytes:
    """Renderiza um PNG do municipio. `camada` define o esquema de cor dos hexes:

    - "resumo": destacados em verde (rotulo = oferta_efetiva_disponivel), demais cinza.
    - "score": choropleth por `score_setor_2022_calibrado` (D5).
    - "residual": choropleth por `score_oportunidade_residual`.
    - "dominio": hexes coloridos por zona (1/2/3) das zonas do `dominio_df` (fallback amarelo).
    - "cobertura": municipio INTEIRO; aprovados (destacados) em verde, reprovados em cinza.
      Usa o municipio inteiro (passe `focus_bounds=None`); sem rotulos de valor e sem pins.

    `basemap=True` busca tiles online (DEC-011) com fallback offline. Em CI/teste default
    `basemap=False`.

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
    zona_labels: list[tuple[int, int, str, tuple[int, int, int]]] = []
    for poly, pos in geometrias:
        pixels = [(int(round(px)), int(round(py))) for px, py in (project(x, y) for x, y in poly)]
        if len(pixels) < 3:
            continue
        if camada == "cobertura":
            if destaque_mask[pos]:
                color = _HEX_APROVADO_RGBA if fonte_propria[pos] else _HEX_APROVADO_MUNICIPAL_RGBA
            else:
                color = _HEX_REPROVADO_RGBA
            odraw.polygon(pixels, fill=color, outline=(255, 255, 255, 90))
        elif camada == "resumo":
            if destaque_mask[pos]:
                color = _HEX_DESTAQUE_RGBA if fonte_propria[pos] else _HEX_DESTAQUE_MUNICIPAL_RGBA
            else:
                color = _HEX_NEUTRO_RGBA
            odraw.polygon(pixels, fill=color, outline=(255, 255, 255, 90))
            if destaque_mask[pos] and not math.isnan(oferta_hex[pos]):
                cx = int(sum(p[0] for p in pixels) / len(pixels))
                cy = int(sum(p[1] for p in pixels) / len(pixels))
                label_pins.append((cx, cy, _format_number(oferta_hex[pos], 0)))
        elif camada == "score":
            color = _score_faixa_color(score_hex[pos])
            odraw.polygon(pixels, fill=color, outline=(255, 255, 255, 70))
        elif camada == "residual":
            color = _score_faixa_color(residual_hex[pos])
            odraw.polygon(pixels, fill=color, outline=(255, 255, 255, 70))
        elif camada == "dominio":
            hid = hex_id_list[pos] if pos < len(hex_id_list) else ""
            zona = hex_zona_geo.get(hid)
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

    # FU1: numero da estrategia (1/2/3) sobre cada hex de zona (camada dominio). Mesmo realce
    # magenta dos valores (decisao de Vinicius no gate: aplicar nos dois, por consistencia
    # entre as paginas Resumo e Dominio).
    zona_font = _font(15)
    for cx, cy, num, _zc in zona_labels:
        w = _text_width(rdraw, num, zona_font)
        rdraw.ellipse([cx - 11, cy - 11, cx + 11, cy + 11], fill=_ROTULO_PLACA_RGBA)
        _draw_text(rdraw, (cx - w // 2, cy - 9), num, font=zona_font, fill=_ROTULO_INK)

    _compor_no_map_box(rotulos_overlay)

    # Legenda no canto superior direito: cobertura mostra as 3 categorias (aprovado proprio /
    # aprovado fallback municipal / reprovado); resumo mostra so as 2 de aprovado (realce de
    # procedencia do dado - pedido de Vinicius 2026-06-24).
    legenda = _COBERTURA_LEGENDA if camada == "cobertura" else (
        _RESUMO_LEGENDA if camada == "resumo" else None
    )
    if legenda is not None:
        leg_font = _font(11)
        box_w = 248
        box_h = 18 * len(legenda) + 14
        lx = right - box_w - 14
        ly = top + 14
        draw.rounded_rectangle([lx, ly, lx + box_w, ly + box_h], radius=6,
                               fill=(255, 255, 255, 235), outline=(120, 120, 120))
        yy = ly + 9
        for rotulo, col in legenda:
            draw.rectangle([lx + 12, yy + 2, lx + 28, yy + 14], fill=col, outline=(120, 120, 120))
            _draw_text(draw, (lx + 36, yy), rotulo, font=leg_font, fill=_CINZA_TEXTO)
            yy += 18

    # Rodape com atribuicao quando ha basemap.
    footer = (
        f"Agregação H3 res 7 - EPSG:3857 - {_atribuicao_tiles()}"
        if drew_basemap
        else "Agregação H3 res 7 - fundo de ruas offline"
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

            # BLK-RELPON-09: logo QUADRADA (sem balao/mascara circular), ancorada pelo
            # CENTRO do quadrado no ponto (S2b) -- o marcador nao tem ponta.
            size = _PIN_LOGO_PX
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
    height: int = 704,
    poligono_municipio: Any | None = None,
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
    mapas = {
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
            focus_bounds=focus_bounds,
        )
        for camada in ("resumo", "score", "residual", "dominio")
    }

    # Camada "cobertura": municipio INTEIRO (focus_bounds=None), sem pins (leitura limpa).
    mapas["cobertura"] = _render_mapa_municipio(
        df_muni,
        camada="cobertura",
        municipio_result=municipio_result,
        competitors_df=None,
        ultra_df=None,
        basemap=basemap,
        width=width,
        height=height,
        focus_bounds=None,
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


def _draw_footer(pdf: _UltraPDF, *, versao: str | None = None, with_attribution: bool = True) -> None:
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_xy(36, _PAGE_H - 22)
    text = _CREDITO_ULTRA
    if with_attribution:
        text = f"{text}   |   {_atribuicao_tiles()}"
    if versao:
        text = f"{text}   |   {versao}"
    pdf.cell(_PAGE_W - 72, 12, _ascii(text))


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


def _watermark_text(solicitante: str | None) -> str:
    if solicitante is None or not solicitante.strip():
        return _ascii(_WATERMARK_BASE)
    return _ascii(f"{_WATERMARK_BASE} | {solicitante.strip()}")


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


def _draw_note(pdf: _UltraPDF, x: float, y: float, w: float, text: str) -> None:
    """Nota curta em cinza pequeno (legenda de calculo), sem poluir."""
    pdf.set_text_color(120, 120, 120)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_xy(x, y)
    pdf.multi_cell(w, 11, _ascii(text))


def _info_panel(pdf: _UltraPDF, x: float, y: float, w: float, titulo: str,
                linhas: list[tuple[str, str]], *, accent: tuple[int, int, int] = ULTRA_TURQUESA,
                border_rgb: tuple[int, int, int] | None = None) -> float:
    """Painel lateral "rotulo | valor". Retorna o y final.

    `border_rgb` (AJUSTE 1) define o contorno colorido do bloco; default = `accent`.
    """
    row_h = 26.0
    panel_h = 36.0 + len(linhas) * row_h + 12.0
    _rounded_panel(pdf, x, y, w, panel_h, border_rgb=border_rgb if border_rgb is not None else accent)
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
    pdf.multi_cell(
        block_w, 18,
        _ascii("Mapeamento competitivo por região - Ultra e espaço disponível para novas academias"),
        align=align,
    )
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
    _draw_framed_map(pdf, mapa, max_w=540.0, max_h=380.0, x_anchor=34.0, y_anchor=100.0,
                     border_rgb=primary)

    n_aprov = int(result.get("n_aprovados", 0) or 0)
    n_muni = int(result.get("n_hex_municipio", 0) or 0)
    n_reprov = int(result.get("n_reprovados", 0) or 0)

    px = 610.0
    pw = _PAGE_W - px - 36.0
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

    _draw_note(
        pdf, 34.0, 490.0, 540.0,
        f"As páginas seguintes consideram apenas as {_format_number(n_aprov, 0)} regiões aprovadas "
        f"(Residual Fitness >= {_format_number(OFERTA_DESTAQUE_MIN, 0)} alunos).",
    )
    _draw_footer(pdf, versao=result.get("versao_contrato"))


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
        [
            ("Unidades Ultra", _format_number(result.get("n_ultra"), 0)),
            ("Unidades Concorrentes", _format_number(result.get("n_concorrentes"), 0)),
            ("Espaço para academias", _format_number(result.get("espaco_para_academias"), 0)),
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
    pdf.multi_cell(pw - 24, 13, _ascii("Soma dos hexágonos destacados / 2.500"))
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
        f"Hexágono considerado quando Residual Fitness >= {_format_number(OFERTA_DESTAQUE_MIN, 0)} (alunos).",
    )
    _draw_footer(pdf, versao=result.get("versao_contrato"))


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
    panel_h = 34.0 + len(SCORE_FAIXAS_TEMPLATE) * 28.0 + 42.0
    py0 = _centered_y(panel_h)
    _rounded_panel(pdf, px, py0, pw, panel_h, border_rgb=secondary)
    pdf.set_text_color(*secondary)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(px + 14, py0 + 16)
    pdf.cell(pw - 28, 16, _ascii("Potencial socioeconômico"))
    yy = py0 + 44.0
    for label, _lo, hi in SCORE_FAIXAS_TEMPLATE:
        rgba = score_band_to_color(min(hi - 1.0, 95.0), alpha=255)
        pdf.set_fill_color(int(rgba[0]), int(rgba[1]), int(rgba[2]))
        pdf.rect(px + 14, yy, 20, 16, style="F", round_corners=True, corner_radius=3)
        pdf.set_text_color(45, 45, 45)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_xy(px + 42, yy)
        pdf.cell(pw - 42, 16, _ascii(label))
        yy += 28
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(px + 14, yy + 6)
    pdf.multi_cell(pw - 28, 12, _ascii(
        f"Score médio {_format_number(result.get('score_censo_medio'), 1)} | "
        f"máx {_format_number(result.get('score_censo_max'), 1)}"
    ))
    # FU1: nota curta explicando as faixas do score (D5).
    _draw_note(
        pdf, px, py0 + panel_h + 10, pw,
        "Score censitário H3 res 7 (IBGE 2022): faixas Alto>=70 / Médio-alto 50-70 / "
        "Médio 30-50 / Baixo <30.",
    )
    pdf.set_xy(36, _PAGE_H - 36)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.cell(_PAGE_W - 72, 12, _ascii("Fonte: IBGE Censo 2022 - Agregação H3 resolução 7"))
    _draw_footer(pdf, versao=result.get("versao_contrato"))


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
    panel_h = 230.0
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
    pdf.cell(pw - 28, 16, _ascii("alunos elegíveis sem academia"))
    yy = py0 + 116
    for rotulo, valor in (
        ("Hab. totais", _format_number(result.get("pop_total_municipio"), 0)),
        ("Renda per capita", "R$ " + _format_number(result.get("renda_per_capita_media"), 2)),
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
        "Residual = pop. elegível - alunos já atendidos (camada de mercado).",
    )
    _draw_footer(pdf, versao=result.get("versao_contrato"))


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
            pdf.cell(pw - 52, 16, _ascii(f"{rotulo}  ({zona.get('n_hex')} hexes)"))
            yy += 20
            pdf.set_text_color(45, 45, 45)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_xy(px + 38, yy)
            pdf.multi_cell(pw - 52, 13, _ascii(str(zona.get("descricao", ""))))
            yy = pdf.get_y() + 14
    pdf.set_xy(36, _PAGE_H - 36)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.cell(_PAGE_W - 72, 12, _ascii("Motor de Expansão Ultra - IBGE + OSM"))
    _draw_footer(pdf, versao=result.get("versao_contrato"))


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
            _ascii("Bairros (IBGE 2022) agrupados pelas zonas de domínio do município."),
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
                "Fonte: IBGE Censo 2022 (bairro do setor; sem bairro, usa subdistrito/distrito). "
                "Cobertura heterogênea entre municípios; zonas por distância ao centroide "
                "(display, não altera o M1).",
            )
        else:
            _draw_note(
                pdf, 36, yy + 2, _PAGE_W - 72,
                "Bairros não mapeados na base IBGE 2022 para este município; exibição por zona "
                "geométrica (display); não altera dominio_df nem o M1.",
            )
    pdf.set_xy(36, _PAGE_H - 36)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_CINZA_TEXTO)
    pdf.cell(_PAGE_W - 72, 12, _ascii("Motor de Expansão Ultra - IBGE + OSM"))
    _draw_footer(pdf, versao=result.get("versao_contrato"))


def _sintese_page(pdf: _UltraPDF, result: dict[str, Any], assets: dict[str, bytes | None], *,
                  primary: tuple[int, int, int] = ULTRA_TURQUESA) -> None:
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, "Síntese - Diagnóstico & Recomendação", rgb=primary)
    cards = [
        (
            ULTRA_MAGENTA,
            _format_number(result.get("penetracao_fitness_pct"), 1, "% de penetração"),
            "Mercado com Oportunidade: penetração fitness atual baixa, grande espaço para crescimento.",
        ),
        (
            ULTRA_TURQUESA,
            f"{_format_number(result.get('residual_total_alunos'), 0)} alunos",
            "Residual Significativo: elegíveis sem academia regular, concentrados nas bordas/periferia.",
        ),
        (
            ULTRA_LARANJA,
            f"{_format_number(result.get('n_zonas_geo'), 0)} zonas de atuação",
            _texto_zonas_sintese(result.get("zonas_geo")),
        ),
    ]
    margin_x = 36.0
    gap = 18.0
    card_w = (_PAGE_W - 2 * margin_x - 2 * gap) / 3.0
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
    _draw_footer(pdf, versao=result.get("versao_contrato"))


def _espaco_academias_page(pdf: _UltraPDF, result: dict[str, Any], assets: dict[str, bytes | None], *,
                           primary: tuple[int, int, int] = ULTRA_TURQUESA) -> None:
    """Pagina 8 — big numbers + breakdown de concorrentes por rede (D8) + carimbo de versao."""
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, "Espaço e academias", rgb=primary)
    big = [
        (ULTRA_TURQUESA, _format_number(result.get("n_ultra"), 0), "Unidades Ultra mapeadas"),
        (ULTRA_MAGENTA, _format_number(result.get("n_concorrentes"), 0), "Unidades concorrentes mapeadas"),
        (ULTRA_LARANJA, _format_number(result.get("espaco_para_academias"), 0), "Espaço total p/ novas academias"),
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
            "Método: contagem de pins dentro do território (H3 res 7) - "
            "Espaço = soma dos hexágonos destacados / 2.500. "
            f"Versão: {result.get('versao_contrato')}"
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
    """Gera o PDF do Relatorio Municipal (9 paginas, 16:9, fpdf2, offline-safe).

    `mapas` = dict `{"resumo","score","residual","dominio"}` (camadas PNG); ausente -> paginas
    com "Mapa indisponivel". `ultra_dir` aponta os assets de branding (fallback gracioso para
    cor solida). `solicitante` carimba a marca d'agua em todas as 9 paginas (anti-PII). `versao`
    sobrescreve o carimbo de versao do rodape. READ-ONLY sobre o M1.
    """
    assets = _load_branding_assets(ultra_dir)
    mapas = mapas or {}
    if versao:
        municipio_result = {**municipio_result, "versao_contrato": versao}

    # Tom principal alterna por pagina de conteudo (turquesa <-> magenta).
    p1, s1 = _tema_bicolor(1)
    p2, s2 = _tema_bicolor(2)
    p3, s3 = _tema_bicolor(3)
    p4, s4 = _tema_bicolor(4)
    p5, s5 = _tema_bicolor(5)
    p6, _ = _tema_bicolor(6)
    p7, _ = _tema_bicolor(7)
    p8, _ = _tema_bicolor(8)

    pdf = _UltraPDF()
    _cover_page(pdf, municipio_result, assets)
    _cobertura_page(pdf, municipio_result, mapas.get("cobertura"), assets, primary=p1, secondary=s1)
    _resumo_page(pdf, municipio_result, mapas.get("resumo"), assets, primary=p2, secondary=s2)
    _score_page(pdf, municipio_result, mapas.get("score"), assets, primary=p3, secondary=s3)
    _residual_page(pdf, municipio_result, mapas.get("residual"), assets, primary=p4, secondary=s4)
    _dominio_page(pdf, municipio_result, mapas.get("dominio"), assets, primary=p5, secondary=s5)
    _bairros_page(pdf, municipio_result, assets, primary=p6)
    _sintese_page(pdf, municipio_result, assets, primary=p7)
    _espaco_academias_page(pdf, municipio_result, assets, primary=p8)

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
