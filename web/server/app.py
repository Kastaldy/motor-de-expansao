"""Backend do piloto web — Motor de Expansao Ultra Academia.

Serve as duas telas do piloto (Mapa Territorial + Viabilidade do ponto) e os
relatorios em PDF, embrulhando as funcoes PURAS que ja existem no repo.

GUARDRAILS (nao negociaveis):
  - READ-ONLY sobre o M1: nenhuma escrita em artefato oficial, nenhum recalculo
    de `score_priorizacao`/pesos/`hex_score_estrutural`. So leitura de parquet.
  - A demanda da Viabilidade e PREMISSA EXPLICITA do operador (DEC-009); nunca
    derivada de lat/lng.
  - Nao toca `src/motor_expansao/api/` (API de producao). Este processo e do
    piloto e roda separado, na porta 8899.

Os dados vivem no checkout da `main` (os parquets sao gitignored e nao existem
no worktree). Aponte com a env var MOTOR_DATA_DIR; ha um default para o caminho
local do Felipe.

Subir:
    uvicorn app:app --port 8899 --reload
"""

from __future__ import annotations

import asyncio
import base64
import functools
import hashlib
import inspect
import json
import math
import os
import re
import sys
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

# Quantos Relatorios Pontuais podem ser gerados AO MESMO TEMPO. O gerador e pesado
# (interseccao de setores, tiles de basemap/satelite, matplotlib, fpdf) e roda no
# threadpool; sem teto, N pedidos simultaneos disputariam as 4 CPUs da VPS e inflariam
# a memoria. 3 deixa folga para o event loop e para os demais apps do host.
_PDF_CONCORRENCIA_MAX = 3
_PDF_SEMAFORO = asyncio.Semaphore(_PDF_CONCORRENCIA_MAX)

# --- Localizacao do repo e dos dados ---------------------------------------
# O backend do piloto vive em <repo>/web/server; o codigo do motor em <repo>/src.
_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parents[2]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_DEFAULT_DATA = Path(
    r"C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\data"
)
DATA_DIR = Path(os.environ.get("MOTOR_DATA_DIR", str(_DEFAULT_DATA)))
OUTPUTS_DIR = DATA_DIR / "outputs"
STAGING_DIR = DATA_DIR / "staging"
IBGE_DIR = DATA_DIR / "ibge"
ULTRA_DIR = DATA_DIR / "ultra"
CENSO_GEO_DIR = OUTPUTS_DIR / "setores_censitarios_2022_geo"
ENRICHED_DIR = OUTPUTS_DIR / "hexagonos_dashboard_enriquecido"

CAPACIDADE_CONCORRENTE_PADRAO = 2500.0
OFERTA_DESTAQUE_MIN = 2000.0  # espelha relatorio_municipal (emenda BLK-RELMUN-03)
POP_MIN_ACIONAVEL = 5000  # regua operacional do dashboard (<5k = descartado)

app = FastAPI(title="Piloto Web — Motor de Expansao", version="0.1.0")
# Em producao o SPA e a API sao servidos pela MESMA origem (mesmo container atras do
# Caddy), entao CORS e irrelevante ali; estas origens sao so para o dev (Vite :5000).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000", "http://127.0.0.1:5000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Carga de dados (lazy, cacheada por UF)
# ============================================================================

# Colunas que o mapa e o funil consomem. Lidas de forma defensiva: o parquet tem
# 82 colunas e nem toda UF materializa todas.
_COLS_DESEJADAS = [
    "hex_id",
    "lat",
    "lng",
    "nome_municipio",
    "cidade",
    "cod_municipio",
    "score_priorizacao",
    "score_setor_2022_calibrado",
    "score_expansao_hibrido",
    "score_oportunidade_residual",
    "oferta_efetiva_disponivel",
    "oferta_consumida_mercado_estimada",
    "oferta_consumida_ultra_real",
    "capacidade_default_concorrente_alunos",
    "sam_fitness_potencial",
    "populacao_corte_hex",
    "pop_total",
    "pop_total_setor_2022",
    "renda_per_capita",
    "renda_per_capita_setor_2022_calibrada",
    "densidade_pop_setor_hab_km2",
    "faixa_oportunidade",
    "n_unidades_ultra_performance_hex",
]


def _uf_partition(uf: str) -> Path:
    return ENRICHED_DIR / f"uf={uf.upper()}"


@functools.lru_cache(maxsize=6)
def carregar_uf(uf: str) -> pd.DataFrame:
    """Le a particao de uma UF do artefato enriquecido. READ-ONLY."""
    part = _uf_partition(uf)
    if not part.exists():
        raise HTTPException(404, f"Particao da UF {uf} nao encontrada em {part}")

    arquivos = sorted(part.glob("*.parquet"))
    if not arquivos:
        raise HTTPException(404, f"Nenhum parquet em {part}")

    import pyarrow.parquet as pq

    disponiveis = set(pq.read_schema(arquivos[0]).names)
    cols = [c for c in _COLS_DESEJADAS if c in disponiveis]
    df = pd.read_parquet(part, columns=cols)
    df["uf"] = uf.upper()
    return _derivar(df)


@functools.lru_cache(maxsize=2)
def carregar_uf_completo(uf: str) -> pd.DataFrame:
    """Particao da UF com TODAS as colunas (82), sem projecao.

    O mapa vive bem com o subset de `_COLS_DESEJADAS`, mas `agregar_municipio`
    (Relatorio Municipal) consome dezenas de colunas do enriquecido; com o subset
    ele quebra em `'numpy.float64' object has no attribute 'dropna'`, porque
    colunas ausentes viram escalar no meio da agregacao. READ-ONLY.
    """
    part = _uf_partition(uf)
    if not part.exists():
        raise HTTPException(404, f"Particao da UF {uf} nao encontrada em {part}")
    return pd.read_parquet(part)


def _derivar(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona colunas derivadas de leitura. Nao altera nada do M1."""
    out = df.copy()

    if "nome_municipio" not in out.columns and "cidade" in out.columns:
        out["nome_municipio"] = out["cidade"]

    # Contagem estimada de concorrentes: o enriquecido nao traz a contagem, so a
    # oferta consumida. Divide-se pela capacidade default (2.500 alunos/unidade).
    cap = (
        out["capacidade_default_concorrente_alunos"]
        if "capacidade_default_concorrente_alunos" in out.columns
        else CAPACIDADE_CONCORRENTE_PADRAO
    )
    consumo = out.get("oferta_consumida_mercado_estimada")
    if consumo is not None:
        divisor = pd.to_numeric(cap, errors="coerce")
        divisor = divisor.replace(0, float("nan")) if hasattr(divisor, "replace") else divisor
        n = pd.to_numeric(consumo, errors="coerce") / divisor
        n = n.replace([float("inf"), float("-inf")], float("nan"))
        out["n_concorrentes_est"] = n.fillna(0).round().astype("int64")
    else:
        out["n_concorrentes_est"] = 0

    ultra = out.get("n_unidades_ultra_performance_hex")
    out["n_ultra"] = (
        pd.to_numeric(ultra, errors="coerce").fillna(0).astype("int64")
        if ultra is not None
        else 0
    )

    # Populacao de leitura, com a mesma precedencia do dashboard.
    for origem in ("populacao_corte_hex", "pop_total_setor_2022", "pop_total"):
        if origem in out.columns:
            out["pop_leitura"] = pd.to_numeric(out[origem], errors="coerce")
            break
    else:
        out["pop_leitura"] = float("nan")

    for origem in ("renda_per_capita_setor_2022_calibrada", "renda_per_capita"):
        if origem in out.columns:
            out["renda_leitura"] = pd.to_numeric(out[origem], errors="coerce")
            break
    else:
        out["renda_leitura"] = float("nan")

    return out


@functools.lru_cache(maxsize=1)
def listar_ufs() -> list[str]:
    if not ENRICHED_DIR.exists():
        raise HTTPException(
            500,
            f"Base nao encontrada em {ENRICHED_DIR}. "
            "Defina MOTOR_DATA_DIR apontando para o data/ do checkout da main.",
        )
    ufs = sorted(
        p.name.split("=", 1)[1] for p in ENRICHED_DIR.glob("uf=*") if p.is_dir()
    )
    return ufs


def _fmt(v: Any, casas: int = 0) -> str:
    """Formata numero no padrao pt-BR (milhar com ponto, decimal com virgula).

    Existe porque a narrativa mistura numero e texto: um `.replace(",", ".")`
    global comia as virgulas das FRASES, nao so as dos numeros.
    """
    n = _num(v, casas)
    if n is None:
        return "n/d"
    return f"{n:,.{casas}f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _num(v: Any, casas: int = 0) -> float | None:
    """Converte para float JSON-safe (NaN/inf viram None)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, casas) if casas else round(f)


# ============================================================================
# Renda media domiciliar + rotulo de faixa (enriquecimento do tooltip)
#
# Espelha o tooltip do dashboard Streamlit (`_renda_media_domiciliar_series` e
# `_compute_faixa_label` em dashboard/components.py). READ-ONLY sobre o M1: so
# leitura/exibicao, nenhum recalculo de score.
# ============================================================================


def _init_renda_domiciliar_paths() -> float:
    """Reaponta os artefatos de renda domiciliar para o DATA_DIR absoluto e le o
    FATOR_TEMPORAL_RENDA real.

    No motor, `UPLIFT_COMPOSICAO_PATH`/`FATOR_TEMPORAL_RENDA_PATH` sao RELATIVOS
    ao CWD ("data/staging/..."). Como o uvicorn do piloto sobe de web/server, eles
    nao resolvem e o uplift/moradores/temporal cairiam no fallback NACIONAL
    (~1.632 / ~2.79 / 1.0) — mesma pegadinha do `_BASEMAP_CACHE_DIR`. Reaponta para
    o checkout absoluto ANTES da 1a leitura (as caches sao lazy) e devolve o fator.
    """
    from motor_expansao.dashboard import constants as _const

    _const.UPLIFT_COMPOSICAO_PATH = STAGING_DIR / "uplift_renda_domiciliar_municipio.parquet"
    _const.UPLIFT_COMPOSICAO_SETOR_PATH = STAGING_DIR / "uplift_composicao_setor.parquet"
    _const.FATOR_TEMPORAL_RENDA_PATH = STAGING_DIR / "fator_temporal_renda.json"
    _const._uplift_cache = None
    _const._uplift_uf_cache = None
    _const._moradores_cache = None
    _const._moradores_uf_cache = None
    fator, _ref = _const._carregar_fator_temporal()
    return fator


@functools.lru_cache(maxsize=1)
def _fator_temporal_renda() -> float:
    return _init_renda_domiciliar_paths()


def _fator_domiciliar(uf: str | None, cod_municipio: str | None) -> float | None:
    """Fator renda per capita -> renda media domiciliar do municipio.

    = moradores_por_domicilio x uplift_renda_domiciliar x FATOR_TEMPORAL_RENDA
    (todos MUNICIPAIS, como no tooltip do Streamlit — um hex res-7 cobre varios
    setores, entao o uplift setorial nao se aplica ao hex). Um hex do piloto
    pertence a UM municipio, entao o fator e um escalar por chamada.
    """
    fator_temporal = _fator_temporal_renda()  # tambem reaponta os paths (1x)
    from motor_expansao.dashboard.constants import (
        moradores_por_domicilio,
        uplift_renda_domiciliar,
    )

    try:
        return (
            moradores_por_domicilio(uf, cod_municipio)
            * uplift_renda_domiciliar(uf, cod_municipio)
            * fator_temporal
        )
    except Exception:  # noqa: BLE001 — enriquecimento opcional, degrada gracioso
        return None


def _renda_domiciliar_hex(r: pd.Series, fator: float | None) -> float | None:
    """Renda media domiciliar do hex = renda per capita x fator municipal.

    NaN (tooltip em branco) quando falta renda OU cod_municipio — fiel ao contrato
    do Streamlit, que nao exibe estimativa de nivel UF para hex sem municipio.
    """
    if fator is None:
        return None
    cod = r.get("cod_municipio")
    if cod is None or pd.isna(cod):
        return None
    return _num(r.get("renda_leitura", float("nan")) * fator)


@functools.lru_cache(maxsize=1)
def _faixa_labels() -> dict[str, str]:
    from motor_expansao.dashboard.constants import FAIXA_LABELS

    return dict(FAIXA_LABELS)


def _faixa_label(v: Any) -> str | None:
    """Rotulo de exibicao da faixa de oportunidade M1 (ex.: 'alta' -> 'Alta')."""
    try:
        if v is None or pd.isna(v):
            return None
    except (TypeError, ValueError):
        return None
    return _faixa_labels().get(str(v), str(v))


# ============================================================================
# Pins de concorrentes e Ultra — bandeiras com logo QUADRADO (WEB-13)
#
# Felipe (2026-07-20): o concorrente vira apenas a bandeira com a logo em formato
# QUADRADO, enxuta. Fallback local = quadrado da cor da marca + sigla (as logos
# PNG das redes sao gitignored; so `logo_ultra.png` existe no checkout). Camada
# VISUAL de apoio (CLAUDE.md §2): nao altera score/ranking/carteira/artefatos.
# ============================================================================

COMPETITOR_PIN_LIMIT = 6000  # espelha constants.COMPETITOR_PIN_LIMIT
CONCORRENTES_PARQUET = STAGING_DIR / "concorrentes_mapeados.parquet"
ULTRA_PERF_PARQUET = STAGING_DIR / "unidades_ultra_performance_hex.parquet"
# Diretorio das logos PNG das redes (`logo_<rede>.png`). Canonico do motor =
# <repo>/concorrentes (normalizar_concorrentes.CONCORRENTES_DIR); override por env.
# As logos sao gitignored -> fallback gracioso (quadrado cor+sigla) quando ausentes.
COMPETITORS_LOGO_DIR = Path(
    os.environ.get("MOTOR_COMPETITORS_LOGO_DIR", str(_REPO_ROOT / "concorrentes"))
)


@app.on_event("startup")
def _preload_pins_logos() -> None:
    """Popula competitors._ICON_CACHE uma vez no boot: SEM isto os pins dos PDFs
    (Relatorio Municipal + Pontual) caem no fallback de sigla e as logos das redes NAO
    aparecem. Idempotente e gracioso (arquivo ausente -> so nao cacheia). READ-ONLY M1."""
    try:
        from motor_expansao.dashboard.competitors import preload_logos

        preload_logos(
            COMPETITORS_LOGO_DIR,
            ultra_dir=ULTRA_DIR if ULTRA_DIR.is_dir() else None,
        )
    except Exception:  # noqa: BLE001
        pass


def _clean(v: Any) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    return str(v).strip()


def _svg_data_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def _quadrado_logo(logo_path: Path | None, bg: str) -> str | None:
    """Quadrado branco arredondado com a logo PNG encaixada. None se o PNG faltar."""
    if logo_path is None or not logo_path.exists():
        return None
    try:
        png = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    except Exception:  # noqa: BLE001
        return None
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        'width="128" height="128" viewBox="0 0 128 128">'
        f'<rect x="4" y="4" width="120" height="120" rx="26" fill="#FFFFFF" stroke="{bg}" stroke-width="7"/>'
        f'<image href="data:image/png;base64,{png}" x="18" y="18" width="92" height="92" '
        'preserveAspectRatio="xMidYMid meet"/></svg>'
    )
    return _svg_data_uri(svg)


def _quadrado_sigla(short: str, bg: str, fg: str) -> str:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">'
        f'<rect x="4" y="4" width="120" height="120" rx="26" fill="{bg}" stroke="#FFFFFF" stroke-width="7"/>'
        f'<text x="64" y="83" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" '
        f'font-size="46" font-weight="800" fill="{fg}">{_clean(short)[:3] or "C"}</text></svg>'
    )
    return _svg_data_uri(svg)


# BLK-RELPON-14: 64 era folgado com as 39 redes antigas — e as 68 novas nem tinham entrada em
# COMPETITOR_LOGO_FILES, entao `_quadrado_logo(None, ...)` curto-circuitava sem custo. Agora as 107
# tem `logo_<slug>.png`, e cada MISS custa Path.exists() + read_bytes() + base64 do PNG. Com 107
# redes possiveis contra 64 entradas o LRU entrava em thrash entre municipios.
@functools.lru_cache(maxsize=128)
def _icone_rede(rede: str) -> str:
    from motor_expansao.dashboard.competitors import (
        COMPETITOR_BRANDS,
        COMPETITOR_LOGO_FILES,
    )

    brand = COMPETITOR_BRANDS.get(
        rede, {"short": (rede[:3].upper() or "C"), "bg": "#64748B", "fg": "#FFFFFF"}
    )
    logo_file = COMPETITOR_LOGO_FILES.get(rede)
    logo_path = COMPETITORS_LOGO_DIR / logo_file if logo_file else None
    return _quadrado_logo(logo_path, str(brand["bg"])) or _quadrado_sigla(
        str(brand["short"]), str(brand["bg"]), str(brand["fg"])
    )


@functools.lru_cache(maxsize=1)
def _icone_ultra() -> str:
    from motor_expansao.dashboard.competitors import ULTRA_BRAND, ULTRA_LOGO_FILE

    return _quadrado_logo(ULTRA_DIR / ULTRA_LOGO_FILE, str(ULTRA_BRAND["bg"])) or _quadrado_sigla(
        str(ULTRA_BRAND["short"]), str(ULTRA_BRAND["bg"]), str(ULTRA_BRAND["fg"])
    )


@functools.lru_cache(maxsize=1)
def _carregar_concorrentes() -> pd.DataFrame:
    """Pontos individuais de concorrentes (READ-ONLY). Vazio se o parquet faltar."""
    cols = ["rede", "nome_unidade", "lat", "lng", "hex_id_res7"]
    if not CONCORRENTES_PARQUET.exists():
        return pd.DataFrame(columns=cols)
    df = pd.read_parquet(
        CONCORRENTES_PARQUET,
        columns=[*cols, "flag_coord_valida"],
    )
    if "flag_coord_valida" in df.columns:
        df = df[df["flag_coord_valida"].fillna(True).astype(bool)]
    df = df.dropna(subset=["lat", "lng"])
    return df[cols].reset_index(drop=True)


@functools.lru_cache(maxsize=1)
def _carregar_ultra_pontos() -> pd.DataFrame:
    """Pontos reais das unidades Ultra (READ-ONLY). Vazio se o parquet faltar."""
    if not ULTRA_PERF_PARQUET.exists():
        return pd.DataFrame(columns=["nome", "lat", "lng"])
    df = pd.read_parquet(ULTRA_PERF_PARQUET, columns=["unidade", "lat", "lng"]).rename(
        columns={"unidade": "nome"}
    )
    df = df.dropna(subset=["lat", "lng"]).drop_duplicates(subset=["lat", "lng"])
    return df[["nome", "lat", "lng"]].reset_index(drop=True)


def _montar_pins(sel: pd.DataFrame) -> dict[str, Any]:
    """Pins de concorrentes (por hex do municipio) + Ultra (por bbox) + icones quadrados."""
    from motor_expansao.dashboard.competitors import COMPETITOR_BRANDS

    hex_ids = set(sel["hex_id"].astype(str))
    lat_min, lat_max = float(sel["lat"].min()), float(sel["lat"].max())
    lng_min, lng_max = float(sel["lng"].min()), float(sel["lng"].max())

    conc = _carregar_concorrentes()
    if len(conc):
        no_muni = conc[conc["hex_id_res7"].astype(str).isin(hex_ids)]
        if no_muni.empty:  # base antiga sem hex casavel -> cai no bbox
            no_muni = conc[conc["lat"].between(lat_min, lat_max) & conc["lng"].between(lng_min, lng_max)]
        conc = no_muni.head(COMPETITOR_PIN_LIMIT)

    ultra = _carregar_ultra_pontos()
    if len(ultra):
        ultra = ultra[ultra["lat"].between(lat_min, lat_max) & ultra["lng"].between(lng_min, lng_max)]

    redes = sorted(conc["rede"].dropna().astype(str).unique()) if len(conc) else []
    icones = {r: _icone_rede(r) for r in redes}
    if len(ultra):
        icones["__ultra__"] = _icone_ultra()

    def _label(r: str) -> str:
        return str(COMPETITOR_BRANDS.get(r, {}).get("label", r))

    return {
        "concorrentes": [
            {
                "lat": _num(t.lat, 6),
                "lng": _num(t.lng, 6),
                "rede": str(t.rede),
                "label": _label(str(t.rede)),
                "nome": _clean(t.nome_unidade),
            }
            for t in conc.itertuples(index=False)
        ]
        if len(conc)
        else [],
        "ultra": [
            {"lat": _num(t.lat, 6), "lng": _num(t.lng, 6), "nome": _clean(t.nome)}
            for t in ultra.itertuples(index=False)
        ]
        if len(ultra)
        else [],
        "icones": icones,
    }


# ============================================================================
# Funil narrativo — os 4 passos do mapa, calculados sobre dado real
# ============================================================================


@functools.lru_cache(maxsize=32)
def bairros_por_hex(uf: str, cod_municipio: str) -> dict[str, str]:
    """Mapa hex_id -> bairro/distrito dominante (IBGE), para nomear o ranking.

    Sem isso, todo item do ranking repetiria o nome do municipio ("Brasília",
    "Brasília", …) — o que mata a leitura. Reusa o helper do Relatorio Municipal;
    fallback gracioso para {} se a particao geo nao existir.
    """
    if not CENSO_GEO_DIR.exists():
        return {}
    try:
        from motor_expansao.dashboard.relatorio_municipal import (
            _carregar_bairros_por_hex,
        )

        return _carregar_bairros_por_hex(uf, cod_municipio, CENSO_GEO_DIR) or {}
    except Exception:  # noqa: BLE001 — enriquecimento opcional
        return {}


def _etiqueta(
    metrica: str, valor: float | None, rank: int, row: pd.Series
) -> tuple[str, str | None]:
    """Rotulo curto e informativo por item do ranking.

    Repetir o nome da camada em todo item ("CENSITÁRIO" x4) e ruido: a camada ja
    esta no cabecalho do painel. A etiqueta diz algo que muda entre as linhas.
    """
    v = valor or 0
    if metrica == "score":
        if v >= 90:
            return "Quente", "blue"
        if v >= 80:
            return "Forte", "green"
        return "Sólido", "gray"
    if metrica == "conc. 2 km":
        n = int(row.get("n_concorrentes_est") or 0)
        if n == 0:
            return "White space", "green"
        if n <= 2:
            return "Adensar", "blue"
        return "Disputa", "red"
    if metrica == "residual":
        # No passo 4 a leitura e a FILA, nao a intensidade. Os 3 primeiros ganham
        # rotulo de urgencia; do 4o ao 10o e "Espera" (a fila vai ate 10).
        if row.get("_fila"):
            return {1: "Agora", 2: "Próximo", 3: "Fila"}.get(rank, "Espera"), None
        if v >= 6000:
            return "Alta", "green"
        if v >= 3000:
            return "Média", "amber"
        return "Baixa", "gray"
    return "", None


def _rank_items(
    df: pd.DataFrame,
    col: str,
    label_metrica: str,
    tom: str,
    casas: int = 0,
    bairros: dict[str, str] | None = None,
    limite: int = 10,
) -> list[dict[str, Any]]:
    """Top-N localidades por uma coluna, no formato do painel de ranking.

    `limite` = 10: mostra ate as 10 melhores. Como o df ja chega FILTRADO pelo
    funil (quentes / residual >= 2000 / white space), todo item e viavel por
    construcao; se houver menos de 10 localidades distintas, a lista encurta
    sozinha (Felipe 2026-07-20: "as 10 melhores, apenas se forem viaveis")."""
    if col not in df.columns:
        return []
    bairros = bairros or {}

    # Um item por LOCALIDADE, nao por hexagono: sem isso o ranking repete
    # "Ceilândia" quatro vezes (hexes vizinhos do mesmo bairro) e nao informa nada.
    # Fica o melhor hex de cada bairro, que e o candidato a ponto.
    # Desempate por populacao: no passo 1 muitos hexes empatam em score 100, e sem
    # criterio secundario o topo do ranking vira ordem alfabetica acidental.
    chaves = [col] + [c for c in ("pop_leitura", "oferta_efetiva_disponivel") if c in df.columns]
    ordenado = df.dropna(subset=[col]).sort_values(chaves, ascending=False)
    itens: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for _, r in ordenado.iterrows():
        hid = str(r.get("hex_id"))
        local = bairros.get(hid)
        titulo = local or (r.get("nome_municipio") or "n/d")
        chave = str(titulo).casefold()
        if chave in vistos:
            continue
        vistos.add(chave)
        valor = _num(r.get(col), casas)
        rank = len(itens) + 1
        etiqueta, tom_item = _etiqueta(label_metrica, valor, rank, r)
        itens.append(
            {
                "rank": rank,
                "hex_id": hid,
                "titulo": titulo,
                "sub": (r.get("nome_municipio") if local else f"hex {hid[:9]}…"),
                "valor": valor,
                "label": label_metrica,
                "tag": etiqueta,
                "tom": tom_item or tom,
            }
        )
        if len(itens) == limite:
            break
    return itens


def montar_funil(
    df_muni: pd.DataFrame, municipio: str, bairros: dict[str, str] | None = None
) -> list[dict[str, Any]]:
    """Os 4 passos, com contagens REAIS do municipio.

    A narrativa e a mesma do template de referencia, mas os numeros saem do dado
    — nao sao mock. Cada passo declara de onde veio (funil) e o que sobrou.
    """
    total = len(df_muni)

    # Passo 1 — Potencial socioeconomico (censo). Corte de <5k habitantes: a
    # regiao precisa de gente suficiente para sustentar a unidade (mesma regua
    # POP_MIN_ACIONAVEL do mapa, que ja pinta <5k em cinza). O corte propaga por
    # todo o funil (residual/concorrencia/recomendacao derivam de `quentes`).
    col_censo = "score_setor_2022_calibrado"
    if col_censo in df_muni.columns:
        pop = df_muni["pop_leitura"] if "pop_leitura" in df_muni.columns else float("nan")
        quentes = df_muni[(df_muni[col_censo] >= 70) & (pop >= POP_MIN_ACIONAVEL)]
    else:
        quentes = df_muni.iloc[0:0]

    # Passo 2 — Residual: quentes que ainda tem espaco de oferta
    residual = (
        quentes[quentes["oferta_efetiva_disponivel"] >= OFERTA_DESTAQUE_MIN]
        if "oferta_efetiva_disponivel" in quentes.columns
        else quentes.iloc[0:0]
    )
    alunos_residual = _num(residual["oferta_efetiva_disponivel"].sum()) if len(residual) else 0

    # Passo 3 — Concorrencia: dos residuais, quais estao desguarnecidos
    white = residual[residual["n_concorrentes_est"] == 0] if len(residual) else residual

    # Passo 4 — Recomendacao: fila de ate 10 aberturas priorizada por residual.
    # So entra quem passou o funil (white space, senao residual >= 2000): a fila e
    # 100% viavel; encurta sozinha quando ha menos de 10 candidatos.
    fila = (
        white.nlargest(10, "oferta_efetiva_disponivel")
        if len(white)
        else residual.nlargest(10, "oferta_efetiva_disponivel")
        if len(residual)
        else residual
    )

    passos = [
        {
            "n": 1,
            "mode": "censitário",
            "titulo": "Potencial socioeconômico",
            "narrativa": (
                f"{municipio} tem {_fmt(total)} hexágonos habitáveis. A primeira pergunta é "
                "onde vive gente com renda e perfil para treinar — o censo 2022 acende "
                f"{_fmt(len(quentes))} setores quentes."
            ),
            "funil_big": len(quentes),
            "funil_unit": "setores quentes",
            "funil_from": f"{_fmt(total)} hexágonos",
            "metrica": "score",
            "itens": _rank_items(quentes, col_censo, "score", "blue", bairros=bairros),
            "hexes": quentes["hex_id"].tolist(),
        },
        {
            "n": 2,
            "mode": "residual fitness",
            "titulo": "Demanda não atendida",
            "narrativa": (
                "Setor quente não basta: precisa ter espaço. Descontando a oferta já "
                f"instalada, sobram {_fmt(len(residual))} regiões com residual fitness "
                f"real — {_fmt(alunos_residual or 0)} alunos não atendidos."
            ),
            "funil_big": len(residual),
            "funil_unit": "regiões com residual",
            "funil_from": f"{_fmt(len(quentes))} setores quentes",
            "metrica": "residual",
            "itens": _rank_items(residual, "oferta_efetiva_disponivel", "residual", "green", bairros=bairros),
            "hexes": residual["hex_id"].tolist(),
        },
        {
            "n": 3,
            "mode": "competitivo",
            "titulo": "Pressão concorrencial",
            "narrativa": (
                f"Dessas {_fmt(len(residual))}, quais estão desguarnecidas? "
                f"{_fmt(len(white))} são white space puro; as demais exigem entrar "
                "protegendo o corredor Ultra contra a concorrência."
            ),
            "funil_big": len(white),
            "funil_unit": "white spaces livres",
            "funil_from": f"{_fmt(len(residual))} regiões",
            "metrica": "conc. 2 km",
            "itens": _rank_items(residual, "oferta_efetiva_disponivel", "residual", "amber", bairros=bairros),
            "hexes": white["hex_id"].tolist(),
        },
        {
            "n": 4,
            "mode": "recomendação",
            "titulo": "Para onde crescer",
            "narrativa": (
                f"A síntese das camadas vira ação: uma fila de {_fmt(len(fila))} aberturas "
                "que captura o máximo de residual sem canibalizar a rede atual."
            ),
            "funil_big": len(fila),
            "funil_unit": "aberturas na fila",
            "funil_from": f"{_fmt(len(white))} white spaces",
            "metrica": "residual",
            "itens": _rank_items(
                fila.assign(_fila=True),
                "oferta_efetiva_disponivel",
                "residual",
                "blue",
                bairros=bairros,
            ),
            "hexes": fila["hex_id"].tolist(),
        },
    ]
    return passos


# ============================================================================
# Funil por UF (visão de entrada) — recomenda MUNICÍPIOS, não hexes (WEB-12)
# ============================================================================


def _etiqueta_muni(
    label: str, valor: float | None, rank: int, fila: bool = False
) -> tuple[str, str | None]:
    v = valor or 0
    if fila:
        return {1: "Agora", 2: "Próximo", 3: "Fila"}.get(rank, "Espera"), None
    if label == "setores":
        if v >= 30:
            return "Polo", "blue"
        if v >= 8:
            return "Forte", "green"
        return "Emergente", "gray"
    # residual (soma municipal — patamares maiores que o de 1 hex)
    if v >= 20000:
        return "Alta", "green"
    if v >= 8000:
        return "Média", "amber"
    return "Baixa", "gray"


def _rank_municipios(
    df: pd.DataFrame,
    value_col: str | None,
    modo: str,
    label: str,
    tom: str,
    fila: bool = False,
) -> list[dict[str, Any]]:
    """Top-10 MUNICÍPIOS por uma métrica agregada. Cada item carrega `municipio`
    para o front fazer o drill-down (clicar -> filtra para o município)."""
    if not len(df) or "nome_municipio" not in df.columns:
        return []
    # observed=True: nome_municipio e Categorical com o dicionario NACIONAL de
    # municipios (parquet dict-encoded); sem isto o groupby cria 1 grupo por
    # categoria — inclusive municipios de OUTRAS UFs, com 0 hexes. Aqui o
    # serie[serie > 0] abaixo ja filtrava esses fantasmas, mas observed=True evita
    # gerar ~4,6k grupos vazios (e silencia o FutureWarning do pandas).
    g = df.groupby("nome_municipio", observed=True)
    serie = g.size() if modo == "count" else g[value_col].sum()
    serie = serie[serie > 0].sort_values(ascending=False).head(10)
    itens: list[dict[str, Any]] = []
    for i, (muni, val) in enumerate(serie.items(), 1):
        valor = _num(val)
        etiqueta, tom_item = _etiqueta_muni(label, valor, i, fila)
        itens.append(
            {
                "rank": i,
                "hex_id": "",
                "municipio": str(muni),
                "titulo": str(muni),
                "sub": None,
                "valor": valor,
                "label": label,
                "tag": etiqueta,
                "tom": tom_item or tom,
            }
        )
    return itens


def montar_funil_uf(df_uf: pd.DataFrame, uf: str) -> list[dict[str, Any]]:
    """Os 4 passos no nível da UF inteira; o ranking recomenda MUNICÍPIOS."""
    total = len(df_uf)
    n_munis = int(df_uf["nome_municipio"].nunique()) if "nome_municipio" in df_uf.columns else 0

    col = "score_setor_2022_calibrado"
    if col in df_uf.columns:
        pop = df_uf["pop_leitura"] if "pop_leitura" in df_uf.columns else float("nan")
        quentes = df_uf[(df_uf[col] >= 70) & (pop >= POP_MIN_ACIONAVEL)]
    else:
        quentes = df_uf.iloc[0:0]

    residual = (
        quentes[quentes["oferta_efetiva_disponivel"] >= OFERTA_DESTAQUE_MIN]
        if "oferta_efetiva_disponivel" in quentes.columns
        else quentes.iloc[0:0]
    )
    alunos_res = _num(residual["oferta_efetiva_disponivel"].sum()) if len(residual) else 0
    white = residual[residual["n_concorrentes_est"] == 0] if len(residual) else residual
    base_fila = white if len(white) else residual
    n_reco = (
        int(base_fila.groupby("nome_municipio", observed=True)["oferta_efetiva_disponivel"].sum().gt(0).sum())
        if len(base_fila)
        else 0
    )

    return [
        {
            "n": 1,
            "mode": "censitário",
            "titulo": "Potencial socioeconômico",
            "narrativa": (
                f"{uf} tem {_fmt(total)} hexágonos habitáveis em {_fmt(n_munis)} municípios. "
                f"O censo 2022 acende {_fmt(len(quentes))} setores quentes."
            ),
            "funil_big": len(quentes),
            "funil_unit": "setores quentes",
            "funil_from": f"{_fmt(total)} hexágonos",
            "metrica": "score",
            "itens": _rank_municipios(quentes, None, "count", "setores", "blue"),
            "hexes": quentes["hex_id"].tolist(),
        },
        {
            "n": 2,
            "mode": "residual fitness",
            "titulo": "Demanda não atendida",
            "narrativa": (
                f"Descontando a oferta já instalada, sobram {_fmt(len(residual))} regiões com "
                f"residual real — {_fmt(alunos_res or 0)} alunos não atendidos."
            ),
            "funil_big": len(residual),
            "funil_unit": "regiões com residual",
            "funil_from": f"{_fmt(len(quentes))} setores quentes",
            "metrica": "residual",
            "itens": _rank_municipios(residual, "oferta_efetiva_disponivel", "sum", "residual", "green"),
            "hexes": residual["hex_id"].tolist(),
        },
        {
            "n": 3,
            "mode": "competitivo",
            "titulo": "Pressão concorrencial",
            "narrativa": (
                f"Dessas regiões, {_fmt(len(white))} são white space puro — sem concorrente "
                "no hexágono; as demais exigem entrar protegendo o corredor Ultra."
            ),
            "funil_big": len(white),
            "funil_unit": "white spaces livres",
            "funil_from": f"{_fmt(len(residual))} regiões",
            "metrica": "conc. 2 km",
            "itens": _rank_municipios(base_fila, "oferta_efetiva_disponivel", "sum", "residual", "amber"),
            "hexes": (white["hex_id"].tolist() if len(white) else []),
        },
        {
            "n": 4,
            "mode": "recomendação",
            "titulo": "Para onde crescer",
            "narrativa": (
                f"A fila de municípios para entrar: {_fmt(n_reco)} onde o residual é maior e a "
                "rede Ultra ainda tem espaço. Clique num município para aprofundar."
            ),
            "funil_big": n_reco,
            "funil_unit": "municípios na fila",
            "funil_from": f"{_fmt(len(white))} white spaces",
            "metrica": "residual",
            "itens": _rank_municipios(
                base_fila, "oferta_efetiva_disponivel", "sum", "residual", "blue", fila=True
            ),
            "hexes": base_fila["hex_id"].tolist(),
        },
    ]


def _hex_dict(r: pd.Series, fator_dom: float | None) -> dict[str, Any]:
    """Serializa um hex para o mapa (compartilhado entre as rotas UF e município)."""
    return {
        "id": r["hex_id"],
        "lat": _num(r["lat"], 6),
        "lng": _num(r["lng"], 6),
        "m1": _num(r.get("score_priorizacao"), 1),
        "censo": _num(r.get("score_setor_2022_calibrado"), 1),
        "hib": _num(r.get("score_expansao_hibrido"), 1),
        "res": _num(r.get("score_oportunidade_residual"), 1),
        "oferta": _num(r.get("oferta_efetiva_disponivel")),
        "sam": _num(r.get("sam_fitness_potencial")),
        "pop": _num(r.get("pop_leitura")),
        "renda": _num(r.get("renda_leitura")),
        "renda_dom": _renda_domiciliar_hex(r, fator_dom),
        "faixa": _faixa_label(r.get("faixa_oportunidade")),
        "conc": int(r.get("n_concorrentes_est") or 0),
        "ultra": int(r.get("n_ultra") or 0),
    }


def _resumo(df: pd.DataFrame) -> dict[str, Any]:
    """KPIs de topo (residual, população, score médio, concorrentes, espaço)."""
    return {
        "residual_total": _num(df["oferta_efetiva_disponivel"].sum()),
        "pop_total": (
            _num(df["pop_total_setor_2022"].sum())
            if "pop_total_setor_2022" in df.columns
            else None
        ),
        "score_m1_medio": _num(df["score_priorizacao"].mean(), 1),
        "n_concorrentes": int(df["n_concorrentes_est"].sum()),
        "n_ultra": int(df["n_ultra"].sum()),
        "espaco_academias": int(
            round(
                df.loc[
                    df["oferta_efetiva_disponivel"] >= OFERTA_DESTAQUE_MIN,
                    "oferta_efetiva_disponivel",
                ].sum()
                / CAPACIDADE_CONCORRENTE_PADRAO
            )
        ),
    }


def _pins_ultra_bbox(df: pd.DataFrame) -> dict[str, Any]:
    """Só os pins Ultra (a rede própria) no bbox — overview da UF sem poluir com
    milhares de concorrentes. Os concorrentes aparecem no drill-down do município."""
    ultra = _carregar_ultra_pontos()
    if len(ultra):
        lat_min, lat_max = float(df["lat"].min()), float(df["lat"].max())
        lng_min, lng_max = float(df["lng"].min()), float(df["lng"].max())
        ultra = ultra[ultra["lat"].between(lat_min, lat_max) & ultra["lng"].between(lng_min, lng_max)]
    return {
        "concorrentes": [],
        "ultra": [
            {"lat": _num(t.lat, 6), "lng": _num(t.lng, 6), "nome": _clean(t.nome)}
            for t in ultra.itertuples(index=False)
        ]
        if len(ultra)
        else [],
        "icones": {"__ultra__": _icone_ultra()} if len(ultra) else {},
    }


# ============================================================================
# Rotas — catalogo
# ============================================================================


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "data_dir": str(DATA_DIR),
        "data_ok": ENRICHED_DIR.exists(),
    }


@app.get("/api/ufs")
def ufs() -> dict[str, Any]:
    return {"ufs": listar_ufs()}


# --- Geocoding de endereço (Nominatim, DEC-010: cache + timeout + fallback) ---
GEOCODE_CACHE_DIR = DATA_DIR / "cache" / "geocode"
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_GEOCODE_UA = "MotorExpansaoUltra-Piloto/1.0 (contato: felipe.silva@ultraacademia.com.br)"


@app.get("/api/geocode")
def geocode(q: str) -> dict[str, Any]:
    """Resolve um ENDEREÇO livre -> lat/lng (Nominatim, restrito ao Brasil).

    DEC-010: cache em disco por hash da consulta, timeout curto, fallback gracioso
    ({"found": false}) quando a rede/serviço falha. Não persiste PII; a consulta é
    uma localização (endereço de imóvel), não dado pessoal de aluno.
    """
    termo = (q or "").strip()
    if len(termo) < 3:
        return {"found": False}

    chave = hashlib.sha1(termo.lower().encode("utf-8")).hexdigest()[:16]
    cache = GEOCODE_CACHE_DIR / f"{chave}.json"
    if cache.exists():
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — cache corrompido: refaz
            pass

    import requests

    try:
        resp = requests.get(
            _NOMINATIM_URL,
            params={"q": termo, "format": "json", "limit": 1, "countrycodes": "br"},
            headers={"User-Agent": _GEOCODE_UA},
            timeout=10,
        )
        arr = resp.json() if resp.ok else []
    except Exception:  # noqa: BLE001 — rede/timeout -> fallback gracioso
        arr = []

    if not arr:
        return {"found": False}

    top = arr[0]
    try:
        out = {
            "found": True,
            "lat": _num(float(top["lat"]), 6),
            "lng": _num(float(top["lon"]), 6),
            "nome": str(top.get("display_name", ""))[:140],
        }
    except (KeyError, TypeError, ValueError):
        return {"found": False}

    try:  # cacheia só sucessos
        GEOCODE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return out


@app.get("/api/municipios/{uf}")
def municipios(uf: str) -> dict[str, Any]:
    df = carregar_uf(uf)
    # observed=True e OBRIGATORIO: nome_municipio e Categorical com o dicionario
    # NACIONAL (parquet dict-encoded). Sem isto, o groupby default (observed=False)
    # gera 1 grupo por CATEGORIA — os ~4,6k municipios de outras UFs (0 hexes na
    # particao) vazavam para a lista, poluindo o seletor com municipios fantasma.
    g = (
        df.groupby("nome_municipio", observed=True)
        .agg(
            n_hex=("hex_id", "size"),
            residual=("oferta_efetiva_disponivel", "sum"),
            score=("score_priorizacao", "mean"),
        )
        .reset_index()
        .sort_values("residual", ascending=False)
    )
    return {
        "uf": uf.upper(),
        "municipios": [
            {
                "nome": r["nome_municipio"],
                "n_hex": int(r["n_hex"]),
                "residual": _num(r["residual"]),
                "score": _num(r["score"], 1),
            }
            for _, r in g.iterrows()
        ],
    }


@app.get("/api/uf/{uf}")
def uf_view(uf: str, limite: int = 15000) -> dict[str, Any]:
    """Visão de UF inteira: funil narrativo por UF + ranking de MUNICÍPIOS.

    Porta de entrada do app — o operador escolhe um estado e vê a leitura
    territorial de toda a UF; o painel recomenda municípios (clique -> drill-down).
    READ-ONLY sobre o M1.
    """
    df = carregar_uf(uf)
    passos = montar_funil_uf(df, uf.upper())

    citados = {h for p in passos for h in p["hexes"][:200]}
    if len(df) > limite:
        base = df.nlargest(limite, "oferta_efetiva_disponivel")
        extras = df[df["hex_id"].isin(citados - set(base["hex_id"]))]
        vis = pd.concat([base, extras]).drop_duplicates(subset="hex_id")
    else:
        vis = df

    # Fator domiciliar por município (poucos únicos) para a renda do tooltip.
    fatores: dict[str, float | None] = {}
    if "cod_municipio" in vis.columns:
        for cod in vis["cod_municipio"].dropna().astype(str).unique():
            fatores[cod] = _fator_domiciliar(uf.upper(), cod)

    hexes = [_hex_dict(r, fatores.get(str(r.get("cod_municipio")))) for _, r in vis.iterrows()]
    for p in passos:
        p["hexes"] = p["hexes"][:400]

    return {
        "nivel": "uf",
        "uf": uf.upper(),
        "municipio": None,
        "n_hex_total": int(len(df)),
        "n_hex_mapa": len(hexes),
        "centro": {"lat": _num(df["lat"].mean(), 6), "lng": _num(df["lng"].mean(), 6)},
        "resumo": _resumo(df),
        "passos": passos,
        "hexes": hexes,
        "pins": _pins_ultra_bbox(df),
    }


@app.get("/api/municipio/{uf}/{municipio}")
def municipio(uf: str, municipio: str, limite: int = 4000) -> dict[str, Any]:
    """Hexes + funil narrativo de 4 passos, tudo sobre dado real."""
    df = carregar_uf(uf)
    sel = df[df["nome_municipio"].str.casefold() == municipio.casefold()]
    if sel.empty:
        sugestoes = (
            df["nome_municipio"].dropna().unique().tolist()[:8]
            if "nome_municipio" in df.columns
            else []
        )
        raise HTTPException(
            404,
            f"Municipio '{municipio}' nao encontrado na UF {uf}. Voce quis dizer: {sugestoes}",
        )

    cod = sel["cod_municipio"].dropna().astype(str).iloc[0] if "cod_municipio" in sel.columns and sel["cod_municipio"].notna().any() else None
    bairros = bairros_por_hex(uf.upper(), cod) if cod else {}
    passos = montar_funil(sel, municipio, bairros)

    # O mapa recebe no maximo `limite` hexes, priorizando os de maior residual —
    # os hexes citados no funil entram sempre.
    citados = {h for p in passos for h in p["hexes"][:200]}
    if len(sel) > limite:
        base = sel.nlargest(limite, "oferta_efetiva_disponivel")
        extras = sel[sel["hex_id"].isin(citados - set(base["hex_id"]))]
        vis = pd.concat([base, extras]).drop_duplicates(subset="hex_id")
    else:
        vis = sel

    # Fator municipal renda per capita -> renda media domiciliar (escalar por
    # municipio, como no tooltip do Streamlit). Calculado 1x aqui.
    fator_dom = _fator_domiciliar(uf.upper(), cod)

    hexes = [_hex_dict(r, fator_dom) for _, r in vis.iterrows()]

    for p in passos:
        p["hexes"] = p["hexes"][:400]

    return {
        "nivel": "municipio",
        "uf": uf.upper(),
        "municipio": municipio,
        "n_hex_total": int(len(sel)),
        "n_hex_mapa": len(hexes),
        "centro": {"lat": _num(sel["lat"].mean(), 6), "lng": _num(sel["lng"].mean(), 6)},
        "resumo": _resumo(sel),
        "passos": passos,
        "hexes": hexes,
        "pins": _montar_pins(sel),
    }


# ============================================================================
# Rotas — Viabilidade
# ============================================================================


class ViabilidadeIn(BaseModel):
    lat: float
    lng: float
    m2: float = Field(gt=0)
    aluguel: float = Field(ge=0)
    demanda: float = Field(gt=0, description="PREMISSA do operador — nunca prevista")
    ticket: float | None = None
    formato: str | None = None
    # Numero de studios extras (0..3): cada studio soma SIM_CUSTO_STUDIO (R$6.000/mes de
    # fopag) aos custos fixos. FIN-VIAB-01: ate aqui o campo era aceito e DESCARTADO —
    # o studio elevava o ticket no front e nao custava nada no DRE (receita fantasma).
    n_studios: int | None = Field(default=None, ge=0, le=3)
    # --- Investimento: Obra (CAPEX, equity) x Equipamentos (OPEX, financiado) ---
    # Obra: desembolso do franqueado (equity), parcelado sem juros (parcelas_obra,
    # default 4). E a base do ROIC e do fluxo acumulado (payback parte de -Obra).
    obra: float | None = Field(default=None, ge=0)
    parcelas_obra: int | None = Field(default=None, gt=0, le=12)
    # Taxa de franquia PARCELADA sem juros (decisao de Felipe, 2026-07-24; default 4).
    # Antes saia INTEIRA do caixa no M-4. As parcelas caem nos meses de CONTRATO 1..N
    # (M-4..M-1 com N=4), junto da obra. E SO timing de caixa: melhora TIR/VPL e nao
    # toca EBITDA, margem nem break-even. Mesma validacao de `parcelas_obra`.
    parcelas_franquia: int | None = Field(default=None, gt=0, le=12)
    # Equipamentos: financiado (prazo 36-60m + juros a.m.); a PMT entra ABAIXO do
    # EBITDA (nao e desembolso a vista) -> dilui no tempo e melhora o payback.
    equipamentos: float | None = Field(default=None, ge=0)
    prazo_equipamentos: int | None = Field(default=None, ge=1, le=60)
    juros_equipamentos_am: float | None = Field(default=None, ge=0, le=1)
    # --- LEGADO (compat): CAPEX unico + fracao/valor financiado ---
    # Preservados para nao quebrar chamadas antigas; usados so como fallback quando
    # obra/equipamentos nao vem preenchidos (ver _investimento()).
    capex: float | None = Field(default=None, ge=0)
    capex_financiado_pct: float | None = Field(default=None, ge=0, le=1)
    capex_financiado_valor: float | None = Field(default=None, ge=0)
    juros_financiamento_am: float | None = Field(default=None, ge=0, le=1)
    capex_parcelas_meses: int | None = Field(default=None, gt=0)
    # Margem EBITDA-alvo (fracao). LEGADO: nao dirige mais o aluguel-teto (agora por
    # clusters % do faturamento); segue so alimentando `alunos_para_margem_alvo`.
    # None usa o default do motor (0.10).
    margem_alvo: float | None = Field(default=None, ge=0, le=1)
    # Carencia de aluguel: meses iniciais sem pagar aluguel (beneficio de rampa;
    # melhora payback/FCF, nao muda margem/breakeven de steady-state).
    carencia_aluguel_meses: int | None = Field(default=None, ge=0, le=60)
    # Meses de rampa de maturacao (Simulador E13; default do motor = 8). Controlavel
    # pelo operador; afeta a serie e o payback, nao a margem/breakeven de steady-state.
    rampa_meses: int | None = Field(default=None, ge=1, le=36)

    # --- Premissas explicitas (FIN-VIAB-01) ---------------------------------
    # Todas OPCIONAIS: None = default do config.py (fonte unica). Estavam escondidas
    # como literal no meio do codigo; agora o operador ve e pode sobrescrever.
    # Taxa de franquia: 160.000 por decisao de Felipe (a planilha diz 140.000), agora
    # EDITAVEL em vez de constante invisivel.
    taxa_franquia: float | None = Field(default=None, ge=0)
    deducoes_pct: float | None = Field(default=None, ge=0, le=1)
    reajuste_ticket_aa: float | None = Field(default=None, ge=0, le=1)
    reajuste_aluguel_aa: float | None = Field(default=None, ge=0, le=1)
    reajuste_custos_aa: float | None = Field(default=None, ge=0, le=1)
    # TAXA MINIMA DO NEGOCIO (a.a., fracao) — a UNICA taxa configuravel do modelo.
    # Default do config: 25% a.a. A taxa minima do SOCIO NAO entra aqui: ela e
    # DERIVADA dentro de `simular()` a partir desta, do custo da divida e da
    # alavancagem. Nao existe campo onde alguem possa digitar uma taxa de socio
    # abaixo do que o banco cobra — a incoerencia ficou impossivel por construcao.
    taxa_minima_negocio_aa: float | None = Field(default=None, ge=0, le=1)
    # ALIAS DEPRECIADO (1 versao) de `taxa_minima_negocio_aa`. Existe so para nao
    # quebrar consumidor que ainda manda o nome antigo; `taxa_minima_negocio_aa`
    # tem precedencia quando os dois vem preenchidos.
    taxa_desconto_aa: float | None = Field(default=None, ge=0, le=1)
    custo_pre_operacional_mes: float | None = Field(default=None, ge=0)
    valor_residual_mes_60: float | None = Field(default=None, ge=0)
    capex_renovacao: float | None = Field(default=None, ge=0)


@app.get("/api/faixa-alunos")
def faixa_alunos(m2: float, formato: str | None = None) -> dict[str, Any]:
    """Faixa de alunos (p10/p50/p90) da curva tamanho->densidade para uma metragem.

    Depende SO de `m2` (e da base de comparaveis), nao da demanda — por isso o
    front usa o p50 daqui para semear a "demanda assumida" antes de calcular a
    viabilidade. GUARDRAIL: nao e previsao de demanda; e a faixa plausivel de
    ocupacao por tamanho (DEC-009).
    """
    from motor_expansao.dimensionamento.viabilidade_ponto import (
        faixa_alunos_por_densidade,
    )

    base, _fonte = _base_calibracao()
    if base is None:
        return {"p10": None, "p50": None, "p90": None, "n_comparaveis": 0}

    r = faixa_alunos_por_densidade(m2, base, formato=formato)
    return {
        "p10": _num(r.get("faixa_alunos_p10")),
        "p50": _num(r.get("faixa_alunos_p50")),
        "p90": _num(r.get("faixa_alunos_p90")),
        "n_comparaveis": r.get("n_comparaveis", 0),
    }


def _investimento(body: ViabilidadeIn) -> dict[str, Any]:
    """Kwargs de investimento de `simular()` — o desmembramento REAL do desembolso.

    - OBRA: equity do franqueado, parcelada SEM juros ao longo de `parcelas_obra`
      (default 4, os meses M-4..M-1 de pre-abertura).
    - EQUIPAMENTOS: financiados (`prazo_equipamentos` meses a `juros_equipamentos_am`);
      a PMT (Price) sai do caixa mes a mes e a parcela de juros vai a DRE.
    - TAXA DE FRANQUIA: PARCELADA sem juros em `parcelas_franquia` (default 4), nos
      meses de contrato 1..N (M-4..M-1), junto da obra — antes saia inteira no M-4.
      Valor default do config (R$160 mil), sobrescrivivel pelo operador.

    Legado (`capex` + `capex_financiado_valor`/`_pct` + `juros_financiamento_am` +
    `capex_parcelas_meses`): a fracao financiada vira EQUIPAMENTOS, o resto vira OBRA.
    """
    from motor_expansao.dimensionamento.config import (
        SIM_CAPEX_DEFAULT,
        SIM_PARCELAS_FRANQUIA_DEFAULT,
        SIM_PARCELAS_OBRA_DEFAULT,
        SIM_TAXA_FRANQUIA,
    )

    obra = float(body.obra) if body.obra is not None else None
    equip = float(body.equipamentos) if body.equipamentos is not None else None
    if obra is None and equip is None:
        capex_total = float(body.capex) if body.capex is not None else float(SIM_CAPEX_DEFAULT)
        if body.capex_financiado_valor:
            equip = min(float(body.capex_financiado_valor), capex_total)
        elif body.capex_financiado_pct:
            equip = capex_total * float(body.capex_financiado_pct)
        else:
            equip = 0.0
        obra = capex_total - equip
    obra = float(obra or 0.0)
    equip = float(equip or 0.0)

    juros = body.juros_equipamentos_am
    if juros is None:
        juros = body.juros_financiamento_am
    franquia = SIM_TAXA_FRANQUIA if body.taxa_franquia is None else float(body.taxa_franquia)
    return {
        "obra": obra,
        "parcelas_obra": int(body.parcelas_obra or SIM_PARCELAS_OBRA_DEFAULT),
        "equipamentos": equip,
        # Sem prazo declarado, mantem o default historico de 36 meses; equipamento
        # zerado -> prazo 0 (o nucleo trata como nao-financiado).
        "prazo_equipamentos": (
            int(body.prazo_equipamentos or body.capex_parcelas_meses or 36) if equip > 0 else 0
        ),
        "juros_equipamentos_am": float(juros or 0.0),
        "taxa_franquia": float(franquia),
        "parcelas_franquia": int(body.parcelas_franquia or SIM_PARCELAS_FRANQUIA_DEFAULT),
    }


def _premissas_do_body(body: ViabilidadeIn):  # -> simulador.Premissas
    """Traduz o corpo da requisicao em `Premissas` — a fonte unica de coeficientes.

    Tudo que o operador NAO informa fica com o default do `config.py`. Nenhum
    coeficiente financeiro nasce aqui.

    `n_studios` deixa de ser receita fantasma: cada studio soma SIM_CUSTO_STUDIO
    (R$6.000/mes de fopag) em `outros_fixos_mes`. Antes o campo era aceito e
    DESCARTADO — o studio elevava o ticket no front e nao custava nada no DRE.
    """
    from motor_expansao.dimensionamento.config import (
        SIM_CUSTO_STUDIO,
        SIM_MENSALIDADE_BALCAO,
        SIM_OUTROS_FIXOS_MES,
    )
    from motor_expansao.dimensionamento.simulador import Premissas

    n_studios = int(body.n_studios or 0)
    opcionais: dict[str, Any] = {
        "devolucoes_pct": body.deducoes_pct,
        "reajuste_ticket_aa": body.reajuste_ticket_aa,
        "reajuste_aluguel_aa": body.reajuste_aluguel_aa,
        "reajuste_custos_aa": body.reajuste_custos_aa,
        # `taxa_desconto_aa` e o nome ANTIGO do mesmo campo (alias depreciado por 1
        # versao); o novo tem precedencia. Do lado do motor existe UM campo so:
        # `taxa_minima_negocio_aa`. A taxa minima do SOCIO nao e configuravel — sai
        # derivada de Ke = Ku + (Ku - Kd) * D/E dentro de `simular()`.
        "taxa_minima_negocio_aa": (
            body.taxa_minima_negocio_aa
            if body.taxa_minima_negocio_aa is not None
            else body.taxa_desconto_aa
        ),
        "custo_pre_operacional_mes": body.custo_pre_operacional_mes,
        "valor_residual_mes_60": body.valor_residual_mes_60,
        "capex_renovacao": body.capex_renovacao,
        "maturacao_meses": body.rampa_meses,
        "carencia_aluguel_meses": body.carencia_aluguel_meses,
    }
    return Premissas(
        ticket_cheio=float(body.ticket or SIM_MENSALIDADE_BALCAO),
        aluguel_mes=float(body.aluguel),
        outros_fixos_mes=float(SIM_OUTROS_FIXOS_MES) + n_studios * float(SIM_CUSTO_STUDIO),
        **{k: v for k, v in opcionais.items() if v is not None},
    )


# Campos da linha da serie que NAO sao numero (nao passam pelo arredondamento).
_SERIE_NAO_NUMERICOS = ("mes", "mes_contrato", "fase")


def _linha_serie(linha: dict[str, Any]) -> dict[str, Any]:
    """Uma linha da serie do nucleo, JSON-safe (NaN/inf -> None). NAO recalcula nada."""
    out: dict[str, Any] = {
        "mes": int(linha["mes"]),
        "mes_contrato": int(linha["mes_contrato"]),
        "fase": str(linha["fase"]),
    }
    for chave, valor in linha.items():
        if chave not in _SERIE_NAO_NUMERICOS:
            out[chave] = _num(valor, 2)
    return out


def _grade_json(grade: pd.DataFrame | None) -> list[dict[str, Any]]:
    """Grade de sensibilidade em JSON-safe. `payback` pode vir `inf` (nunca se paga):
    `json.dumps(..., allow_nan=False)` do Starlette quebraria com Infinity."""
    if grade is None or not len(grade):
        return []
    return [
        {
            "alunos": _num(t.alunos),
            "aluguel": _num(t.aluguel, 2),
            "fator_aluguel": _num(t.fator_aluguel, 2),
            "margem_liq": _num(t.margem_liq, 4),
            "viavel": bool(t.viavel),
            "payback": _num(t.payback, 1),
        }
        for t in grade.itertuples(index=False)
    ]


VIABILIDADE_PAYLOAD_VERSAO = "viabilidade_payload_v1"


def _payload_viabilidade(body: ViabilidadeIn) -> dict[str, Any]:
    """Monta o `viabilidade_payload_v1` a partir de UMA rodada do nucleo.

    CONTRATO (FIN-VIAB-01): este dict e a UNICA saida financeira do backend — a tela
    e o PDF consomem o MESMO objeto, sem recalcular. Antes existiam cinco series
    mensais e nove KPIs com implementacao dupla aqui dentro (payback do card 35 x 33
    do grafico, aluguel-teto R$55,5 mil x R$105,8 mil).

    Convencao de unidades: TODA taxa/percentual vai como FRACAO (margem 0,3873 =
    38,73%; retorno 0,4475; TIR 0,4221). Dinheiro em reais, alunos em alunos TOTAIS.
    Nenhum valor nao-finito sai daqui (payback infinito / TIR inexistente -> null).
    """
    from motor_expansao.dimensionamento.config import (
        SIM_MARGEM_VIAVEL_MIN,
        SIM_PAYBACK_VIAVEL_MAX,
    )
    from motor_expansao.dimensionamento.viabilidade_ponto import (
        analisar_viabilidade_ponto,
    )

    premissas = _premissas_do_body(body)
    inv = _investimento(body)
    base, fonte_base = _base_calibracao()

    res = analisar_viabilidade_ponto(
        lat=body.lat,
        lng=body.lng,
        m2=body.m2,
        aluguel_pedido=body.aluguel,
        demanda_premissa=body.demanda,
        premissas=premissas,
        base_calibracao_df=base,
        formato=body.formato,
        **inv,
    )
    r = res.viabilidade
    serie = [_linha_serie(linha) for linha in r.serie_mensal]
    # 1o mes em que o aluguel de fato entra no caixa (LEITURA da serie — a carencia
    # conta a partir do M-4, entao o operador precisa ver o mes resultante).
    mes_inicio_aluguel = next((linha["mes"] for linha in serie if (linha["aluguel"] or 0) > 0), None)
    teto = res.aluguel_teto_faixas
    # Linha da serie a que a DRE de steady-state se refere (regime pleno). O motor ja
    # publica `deducoes` e `impostos` como COLUNAS dessa linha; ler daqui elimina as
    # duas ultimas subtracoes que montavam degrau de DRE dentro do backend.
    linha_steady = next(
        (linha for linha in serie if linha["mes"] == int(r.mes_referencia_steady)), {}
    )

    return {
        "versao": VIABILIDADE_PAYLOAD_VERSAO,
        "premissas": {
            "ticket_cheio": _num(premissas.ticket_cheio, 2),
            "ticket_agregador": _num(premissas.ticket_agregador, 2),
            "ticket_blended": _num(premissas.ticket_blended, 2),
            "ticket_agregador_fator": _num(premissas.ticket_agregador_fator, 4),
            "share_balcao": _num(premissas.share_balcao, 4),
            "folha_pct": _num(premissas.folha_pct, 4),
            # FOLHA FIXA DESDE O MES 1 (decisao de Felipe, 2026-07-24). `folha_pct`
            # nao e mais um percentual da receita DO MES: ele DIMENSIONA a folha pelo
            # faturamento MADURO (regime pleno, a precos do ano 1) e o valor resultante
            # e pago integralmente desde o mes 1 — a equipe existe antes dos alunos.
            # Consequencia: a folha e CUSTO FIXO (saiu de `fator_receita_para_ebitda`) e
            # os meses de rampa ficam mais pesados. Os tres campos abaixo vem do proprio
            # motor (`Premissas.folha_fixa_mes` / `.faturamento_maduro`); a tela LE, nao
            # multiplica percentual por faturamento.
            "folha_fixa_mes": _num(premissas.folha_fixa_mes(float(body.demanda)), 2),
            "folha_base_faturamento_maduro": _num(
                premissas.faturamento_maduro(float(body.demanda)), 2
            ),
            "folha_fixa_desde_mes_1": True,
            "folha_regime": "fixa_desde_mes_1_dimensionada_pelo_faturamento_maduro",
            "deducoes_pct": _num(premissas.devolucoes_pct, 4),
            "impostos_receita_pct": _num(premissas.impostos_receita_pct, 4),
            "custo_variavel_pct": _num(premissas.custo_variavel_pct, 4),
            "reajuste_ticket_aa": _num(premissas.reajuste_ticket_aa, 4),
            "reajuste_aluguel_aa": _num(premissas.reajuste_aluguel_aa, 4),
            "reajuste_custos_aa": _num(premissas.reajuste_custos_aa, 4),
            # TAXA MINIMA DO NEGOCIO (a.a.): a unica taxa configuravel. A do SOCIO nao
            # aparece aqui de proposito — ela e DERIVADA e viaja no bloco `retorno`
            # (`socio.taxa_minima_aa`), junto do custo da divida e da alavancagem que a
            # produzem. Expor as duas como premissa editavel era o que permitia digitar
            # uma taxa de socio menor que a do credor.
            "taxa_minima_negocio_aa": _num(premissas.taxa_minima_negocio_aa, 4),
            # ALIAS DEPRECIADO (1 versao) do campo acima — nome antigo, mesmo numero.
            "taxa_desconto_aa": _num(premissas.taxa_minima_negocio_aa, 4),
            # Reguas do veredito (`dre.flag_viavel`), servidas para a tela e o PDF
            # rotularem o criterio sem cravar o numero. Sao CONSTANTES da fonte unica
            # (`dimensionamento/config.py`), nao contas feitas aqui.
            "margem_viavel_min": _num(SIM_MARGEM_VIAVEL_MIN, 4),
            "payback_viavel_max": int(SIM_PAYBACK_VIAVEL_MAX),
            "carencia_aluguel_meses": int(premissas.carencia_aluguel_meses),
            "mes_inicio_aluguel": mes_inicio_aluguel,
            "custo_pre_operacional_mes": _num(premissas.custo_pre_operacional_mes, 2),
            "maturacao_meses": int(premissas.maturacao_meses),
            "horizonte_meses": int(premissas.horizonte_meses),
            # Anuidade (Simulador J10/J12): R$ por aluno de BALCAO que completa
            # `anuidade_mes_inicio` meses, cobrada 1x/ano e reconhecida pro-rata.
            # A elegibilidade sai do proprio churn ((1-churn)^12) — nem todo aluno
            # chega a 12 meses. Exposta aqui para o operador ver a linha, e nao um
            # faturamento maior sem causa visivel.
            "anuidade_valor": _num(premissas.anuidade_valor, 2),
            "anuidade_mes_inicio": int(premissas.anuidade_mes_inicio),
            "anuidade_apenas_balcao": bool(premissas.anuidade_apenas_balcao),
            "anuidade_elegivel_pct": _num(premissas.anuidade_elegivel_efetivo, 4),
            # Mes de operacao a que a DRE de steady-state se refere (regime pleno:
            # alunos maduros E anuidade ja em cobranca). LEIA daqui — nao recalcule.
            "mes_referencia_steady": int(r.mes_referencia_steady),
            "valor_residual_mes_60": _num(premissas.valor_residual_mes_60, 2),
            "capex_renovacao": _num(premissas.capex_renovacao, 2),
            "fonte_base_calibracao": fonte_base,
        },
        "dre": {
            "faturamento": _num(r.faturamento_mensal_steady, 2),
            # Parcela de anuidade dentro do faturamento acima (0 antes do mes de inicio).
            "receita_anuidade": _num(r.receita_anuidade_mensal, 2),
            # LEITURA da coluna `deducoes` da linha de steady (nao a subtracao
            # faturamento - receita_liquida): o degrau ja existe pronto no motor.
            "deducoes": linha_steady.get("deducoes"),
            # Niveis intermediarios servidos PRONTOS: sem eles o gerador de graficos
            # reconstruia os dois degraus do waterfall por subtracao — era a ultima
            # formula financeira viva fora do simulador.py.
            "receita_liquida": _num(r.receita_liquida, 2),
            "receita_pos_impostos": _num(r.receita_pos_impostos, 2),
            # Idem: coluna `impostos` da MESMA linha, nao receita_liquida - pos_impostos.
            "impostos": linha_steady.get("impostos"),
            "custos_op": _num(r.custos_op_mensal, 2),
            "custos_variaveis": _num(r.custos_variaveis_mensal, 2),
            "folha": _num(r.folha_mensal, 2),
            "custos_fixos": _num(r.custos_fixos_mensal, 2),
            "ebitda": _num(r.ebitda_mensal, 2),
            "margem": _num(r.margem_ebitda_pct, 4),
            "ir_csll": _num(r.ir_csll_mensal, 2),
            "despesa_financeira": _num(r.despesa_financeira_mensal, 2),
            "resultado_apos_ir": _num(r.resultado_apos_ir_mensal, 2),
            "flag_viavel": bool(r.flag_viavel),
        },
        "investimento": {
            "obra": _num(inv["obra"], 2),
            "equipamentos": _num(inv["equipamentos"], 2),
            "capex_total": _num(r.capex_total, 2),
            "taxa_franquia": _num(r.taxa_franquia, 2),
            "investimento_total": _num(r.investimento_total, 2),
            "pmt": _num(r.pmt_mensal, 2),
            "juros_totais": _num(r.juros_totais, 2),
            "prazo_equipamentos": int(inv["prazo_equipamentos"]),
            "juros_equipamentos_am": _num(inv["juros_equipamentos_am"], 6),
            "parcelas_obra": int(inv["parcelas_obra"]),
            # Franquia PARCELADA sem juros: N parcelas iguais nos meses de contrato
            # 1..N (M-4..M-1 com N=4), junto da obra. A divisao abaixo e RENDER do
            # cronograma de desembolso (valor / n de parcelas sem juros), nao uma
            # formula financeira nova — nenhum coeficiente entra nela.
            "parcelas_franquia": int(inv["parcelas_franquia"]),
            "franquia_parcela": _num(
                inv["taxa_franquia"] / inv["parcelas_franquia"]
                if inv["taxa_franquia"] > 0 and inv["parcelas_franquia"] > 0
                else 0.0,
                2,
            ),
            # APORTE INICIAL (obra + taxa de franquia) = o dinheiro que o CONTRATO pede
            # do socio, e o denominador do retorno dele. VOCABULARIO: nao se chama mais
            # "equity aportado"; e "aporte inicial". A soma e dos DOIS campos que ja
            # estao neste mesmo bloco (nao ha coeficiente nem formula financeira aqui) e
            # reproduz literalmente o denominador que o nucleo usa em `simular()`.
            "aporte_inicial": _num(inv["obra"] + inv["taxa_franquia"], 2),
            # CHEQUE TOTAL: o pior ponto do caixa acumulado — quanto o investidor precisa
            # TER disponivel, nao quanto o contrato pede. No caso de referencia sao
            # R$1,14 mi no mes 5 contra R$760 mil de aporte (1,50x). E o numero que
            # decide se o negocio e FINANCIAVEL e nao existia em lugar nenhum do produto.
            # Vem PRONTO do nucleo (`cheque_total` / `mes_cheque_total`).
            "cheque_total": _num(r.cheque_total, 2),
            "mes_cheque_total": int(r.mes_cheque_total),
        },
        "retorno": {
            # ------------------------------------------------------------------
            # DUAS OTICAS, SEPARADAS E ROTULADAS — nunca no mesmo numero.
            #   `negocio` (FCFF): sem financiamento, CAPEX inteiro desembolsado. Mede o
            #       ATIVO. Descontado a taxa minima do NEGOCIO (premissa).
            #   `socio`   (FCFE): PMT inteira sai do caixa e so obra+franquia entram como
            #       aporte. Mede a ESTRUTURA. Descontado a taxa minima do SOCIO, que e
            #       DERIVADA (Ke = Ku + (Ku - Kd) * D/E) — o socio e subordinado ao
            #       banco, entao a taxa dele nao pode ser menor que a do credor.
            # Sem escudo fiscal no Lucro Presumido, WACC = taxa minima do negocio: a
            # divida so cria valor por ARBITRAGEM (tomar a 23,87% para um ativo que
            # rende 25%), nunca por beneficio tributario.
            # Rotulos de usuario: "do negocio" (era "desalavancado") e "do socio".
            # ------------------------------------------------------------------
            "negocio": {
                "tir_anual": _num(r.tir_negocio_anual, 4),
                "vpl": _num(r.vpl_negocio, 2),
                "taxa_minima_aa": _num(r.taxa_minima_negocio_aa, 4),
                "retorno_anual": _num(r.retorno_anual_desalavancado, 4),
            },
            "socio": {
                "tir_anual": _num(r.tir_socio_anual, 4),
                "vpl": _num(r.vpl_socio, 2),
                "taxa_minima_aa": _num(r.taxa_minima_socio_aa, 4),
                "retorno_anual": _num(r.retorno_anual_equity, 4),
            },
            "custo_divida_aa": _num(r.custo_divida_aa, 4),
            "alavancagem_divida_sobre_aporte": _num(r.alavancagem_divida_sobre_aporte, 4),
            # VPL da divida descontado a taxa minima do NEGOCIO = a ARBITRAGEM. Vem do
            # nucleo quando ele o publica; `null` enquanto nao publicar — este backend
            # NAO calcula formula financeira para preencher o campo.
            "vpl_divida_arbitragem": _num(getattr(r, "vpl_divida_arbitragem", None), 2),
            # GUARDA 1: se a divida custa mais que a taxa minima do negocio, a
            # alavancagem DESTROI valor em vez de criar (sem escudo fiscal nao ha o que
            # compensar). Aviso visivel na tela.
            "alerta_divida_acima_da_taxa_negocio": bool(
                r.alerta_divida_acima_da_taxa_negocio
            ),
            # GUARDA 2 (diagnostico, NAO tolerancia): VPL do socio @taxa do socio menos
            # VPL do negocio @taxa do negocio. Os dois NAO coincidem de proposito — a
            # taxa do socio usa a alavancagem INICIAL enquanto o saldo devedor cai a
            # zero ao longo do contrato. -R$36.073,94 no caso de referencia.
            "vpl_identidade_residuo": _num(r.vpl_identidade_residuo, 2),
            # --- CHAVES PLANAS: ALIAS HISTORICOS (o PDF e o XLSX leem delas) ---------
            # `tir_anual` e `vpl` sao o par do SOCIO (e o que o nucleo mantem como alias
            # em `ViabilidadeResult`). `retorno_anual_desalavancado` e o retorno DO
            # NEGOCIO e `retorno_anual_equity` o DO SOCIO — os nomes ficam pelo contrato
            # antigo; os rotulos de usuario sao "do negocio" e "do socio".
            "otica": "desalavancada",  # LEGADO: `censo_report` escolhe o rotulo do card
            # por `otica.startswith("desalav")`; mudar o VALOR aqui trocaria o card do
            # PDF para "ROIC anual". O rotulo novo e responsabilidade do consumidor.
            "retorno_anual_desalavancado": _num(r.retorno_anual_desalavancado, 4),
            "retorno_anual_equity": _num(r.retorno_anual_equity, 4),
            "tir_anual": _num(r.tir_anual, 4),
            "vpl": _num(r.vpl, 2),
            "payback": _num(r.payback_meses, 1),
        },
        "break_even": {
            "unidade": "alunos_totais",
            "ebitda": _num(res.alunos_breakeven, 1),
            "caixa": _num(res.alunos_breakeven_caixa, 1),
        },
        "aluguel_teto": {
            "base": "faturamento_bruto",
            "ideal": _num(teto.get("ideal"), 2),
            "teto": _num(teto.get("teto"), 2),
            "excecao": _num(teto.get("excecao"), 2),
            "canonico": _num(res.aluguel_teto_calculado, 2),
            # Teto sobre o p10 da faixa (nao circular). null sem base de comparaveis.
            "teto_p10": _num(res.aluguel_teto_p10, 2),
        },
        "faixa_alunos": {
            "p10": _num(res.faixa_alunos_p10),
            "p50": _num(res.faixa_alunos_p50),
            "p90": _num(res.faixa_alunos_p90),
            "n_comparaveis": res.n_comparaveis,
        },
        "serie_mensal": serie,
        "mes_caixa_operacional_positivo": r.mes_caixa_operacional_positivo,
        "acumulado_mes_final": _num(r.acumulado_mes_final, 2),
        "demanda_premissa": _num(res.demanda_premissa, 1),
        "demanda_fonte": res.demanda_fonte,
        "split": {
            "balcao": _num(res.alunos_balcao_premissa, 1),
            "agregadores": _num(res.alunos_agregadores_premissa, 1),
        },
        "flag_zona_morta": res.flag_zona_morta,
        "motivo_zona_morta": res.motivo_zona_morta,
        "flag_fora_envelope": bool(res.flag_fora_envelope),
        "grade": _grade_json(res.grade_sensibilidade),
        # Sugestao de ajuste quando o payback estoura (LEITURA da serie; nao e KPI).
        "melhoria_payback": _melhoria_payback(
            serie, _num(r.payback_meses, 1), float(body.aluguel), float(r.investimento_total)
        ),
    }


@app.post("/api/viabilidade")
def viabilidade(body: ViabilidadeIn) -> dict[str, Any]:
    """Viabilidade do ponto — devolve o `viabilidade_payload_v1` (contrato unico).

    GUARDRAIL: a demanda e PREMISSA EXPLICITA do operador (DEC-009), nunca derivada
    de lat/lng. READ-ONLY sobre o M1.
    """
    return _payload_viabilidade(body)


def _melhoria_payback(
    serie: list[dict[str, Any]],
    payback: float | None,
    aluguel: float,
    capex_efetivo: float,
    alvo_meses: int = 36,
    gatilho_meses: int = 40,
) -> dict[str, Any] | None:
    """Quando o payback estoura (> gatilho), estima quanto cortar de CAPEX OU de aluguel
    para o payback cair para ~alvo_meses. Estimativa de 1a ordem LIDA da serie do nucleo
    (`fcf_acumulado` no mes-alvo): o CAPEX desloca a curva 1:1; cada R$1/mes a menos de
    aluguel soma ~alvo_meses ao caixa no mes-alvo. NAO e KPI e nao recalcula o motor —
    e uma sugestao de ajuste. None quando nao ha o que sugerir.

    payback None (nunca vira dentro do horizonte) e o PIOR caso -> tambem gera sugestao."""
    if payback is not None and payback <= gatilho_meses:
        return None
    row = next((r for r in serie if r.get("mes") == alvo_meses), None)
    if row is None or row.get("fcf_acumulado") is None or float(row["fcf_acumulado"]) >= 0:
        return None
    deficit = -float(row["fcf_acumulado"])  # caixa que ainda falta no mes-alvo
    reduzir_capex = (
        float(round(deficit)) if (capex_efetivo > 0 and deficit < capex_efetivo) else None
    )
    red_aluguel = deficit / alvo_meses
    reduzir_aluguel = float(round(red_aluguel)) if (aluguel > 0 and red_aluguel < aluguel) else None
    return {
        "alvo_meses": alvo_meses,
        "reduzir_capex": reduzir_capex,
        "reduzir_aluguel": reduzir_aluguel,
    }


# Bases da curva tamanho->densidade, em ordem de preferencia: (arquivo, rotulo da fonte).
# O rotulo VAI NO PAYLOAD (`premissas.fonte_base_calibracao`) porque a degradacao era
# SILENCIOSA: caindo no fallback (ou sem base nenhuma), a faixa p10/p50/p90 mudava de
# significado sem nenhum sinal na tela nem no PDF.
_BASES_CALIBRACAO = (
    ("base_calibracao_maduras.parquet", "base_calibracao_maduras.parquet (oficial)"),
    ("unidades_ultra_performance_hex.parquet", "unidades_ultra_performance_hex.parquet (fallback)"),
)
FONTE_BASE_INDISPONIVEL = "indisponivel (faixa de alunos nao calculada)"


@functools.lru_cache(maxsize=1)
def _base_calibracao() -> tuple[pd.DataFrame | None, str]:
    """Base de comparaveis da curva tamanho->densidade + QUAL arquivo a alimentou.

    A curva exige a coluna `alunos_por_m2`. `base_calibracao_multirede` NAO a tem
    (traz `alunos_reais` + `metragem` crus), entao entregar aquele parquet faz a
    faixa voltar vazia com n_comparaveis=0 — foi o bug da primeira versao.
    Prioriza as bases que ja trazem a coluna e valida antes de devolver.
    """
    for nome, rotulo in _BASES_CALIBRACAO:
        caminho = STAGING_DIR / nome
        if not caminho.exists():
            continue
        try:
            df = pd.read_parquet(caminho)
        except Exception:  # noqa: BLE001 — base opcional, degrada gracioso
            continue
        if "alunos_por_m2" in df.columns and len(df):
            return df, rotulo
    return None, FONTE_BASE_INDISPONIVEL


# ============================================================================
# Rotas — Visão Executiva por estado (rede Ultra real, camada PARALELA) — WEB-15
#
# Agrega `growth_api_historico.parquet` (ingestão semanal da Growth API, DEC-013)
# por UF: alunos ativos/pagantes reais, faturamento, churn, split pagantes ×
# agregadores. READ-ONLY sobre o M1; camada de rede PARALELA (sem PII — o parquet
# é agregado por unidade/data).
# ============================================================================

GROWTH_PARQUET = STAGING_DIR / "growth_api_historico.parquet"
# Piso de faturamento (30d) para uma unidade contar como academia OPERANTE. Entradas
# administrativas/de teste na base têm faturamento irrisório (R$ 1-5 mil) e churn
# impossível (>100%) — "dado sujo" que polui ranking e totais. Academia real >> isto.
_FAT_MIN_EXEC = 20000.0
# Unidades a EXCLUIR da Visão Executiva (pedido de Felipe 2026-07-20): fora da rede
# comparável. Casadas por nome normalizado (sem acento, sem sufixo " - UF").
_EXEC_EXCLUIR = {"NATAL", "BATEL", "BACACHERI", "AGUAS CLARAS"}


@functools.lru_cache(maxsize=1)
def _carregar_growth() -> pd.DataFrame:
    if not GROWTH_PARQUET.exists():
        return pd.DataFrame()
    df = pd.read_parquet(GROWTH_PARQUET)
    df["_data"] = pd.to_datetime(df.get("data"), format="%d/%m/%Y", errors="coerce")
    return df


@functools.lru_cache(maxsize=1)
def _ultra_coord_map() -> dict[str, tuple[float, float]]:
    """unidade normalizada -> (lat, lng) das unidades Ultra (para os pins)."""
    from motor_expansao.dimensionamento.growth_api_client import normalizar_unidade

    ultra = _carregar_ultra_pontos()
    mapa: dict[str, tuple[float, float]] = {}
    for t in ultra.itertuples(index=False):
        chave = normalizar_unidade(t.nome)
        if chave:
            mapa[chave] = (float(t.lat), float(t.lng))
    return mapa


def _wavg(valores: pd.Series, pesos: pd.Series) -> float | None:
    """Média ponderada JSON-safe; cai na média simples se não houver pesos."""
    v = pd.to_numeric(valores, errors="coerce")
    w = pd.to_numeric(pesos, errors="coerce")
    m = v.notna() & w.notna() & (w > 0)
    if not bool(m.any()):
        vv = v.dropna()
        return _num(vv.mean(), 2) if len(vv) else None
    return _num(float((v[m] * w[m]).sum() / w[m].sum()), 2)


def _prev_month(ano: int, mes: int) -> tuple[int, int]:
    return (ano - 1, 12) if mes == 1 else (ano, mes - 1)


def _numf(v: Any) -> float | None:
    """float JSON-safe SEM arredondar (NaN/inf -> None)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (math.isnan(f) or math.isinf(f)) else f


@app.get("/api/executiva/{uf}")
def executiva(uf: str, mes: str | None = None) -> dict[str, Any]:
    """Rede Ultra por estado, com o ETL correto da base Growth.

    Peculiaridades tratadas (Felipe 2026-07-20): a base é DIÁRIA e `faturamento`,
    `churn` e `cancelados` ACUMULAM no mês (MTD) e resetam no dia 1. Logo:
      - acumulados (faturamento) -> valor MTD no dia de referência; M-1 = MESMO
        DIA-DO-MÊS do mês anterior (12/06 vs 12/05), comparação justa;
      - snapshots (ativos/pagantes/agregadores/ticket/NPS) -> valor no mesmo dia;
      - churn -> ROLLING 30 dias (reconstruído do cumulativo mensal), não o MTD
        parcial que subestima;
      - unidades sem dado no mês de referência (paradas) ficam FORA.
    Todos os cards trazem `atual`, `m1` e `delta_pct`. READ-ONLY sobre o M1.
    """
    df = _carregar_growth()
    if not len(df):
        raise HTTPException(404, "Base de rede (growth_api_historico.parquet) ausente no servidor.")
    sel = df[df["uf"].astype(str).str.upper() == uf.upper()].copy()
    if not len(sel):
        raise HTTPException(404, f"Sem unidades Ultra com dados de rede na UF {uf.upper()}.")

    # Período (competência) analisável: o operador escolhe o mês no topo — evita
    # ficar preso ao mês corrente parcial. Default = mês mais recente com dado.
    meses = sorted({str(p) for p in sel["_data"].dt.to_period("M").dropna().unique()}, reverse=True)
    mes_sel = mes if (mes in meses) else (meses[0] if meses else None)
    if mes_sel is None:
        raise HTTPException(404, f"Sem competências com dado na UF {uf.upper()}.")
    ry, rm = int(mes_sel[:4]), int(mes_sel[5:7])
    # dia de referência = último dia COM DADO no mês escolhido (mês passado -> fim do
    # mês; mês corrente -> último dia coletado).
    ref = sel.loc[(sel["_data"].dt.year == ry) & (sel["_data"].dt.month == rm), "_data"].max()
    dom = int(ref.day)
    py, pm = _prev_month(ry, rm)

    from motor_expansao.dimensionamento.growth_api_client import normalizar_unidade

    coords = _ultra_coord_map()

    def mtd(g: pd.DataFrame, ano: int, mes: int) -> pd.Series | None:
        """Última linha do mês (ano,mes) com dia <= dom (valor MTD nesse dia)."""
        m = g[(g["_data"].dt.year == ano) & (g["_data"].dt.month == mes) & (g["_data"].dt.day <= dom)]
        return m.iloc[-1] if len(m) else None

    def mes_cheio(g: pd.DataFrame, ano: int, mes: int) -> pd.Series | None:
        m = g[(g["_data"].dt.year == ano) & (g["_data"].dt.month == mes)]
        return m.iloc[-1] if len(m) else None

    def rolling30(g: pd.DataFrame, ano: int, mes: int, colr: str) -> float | None:
        """Soma dos ~30 dias que terminam no dia `dom` de (ano,mes) para uma coluna
        CUMULATIVA mensal (faturamento, cancelados): MTD do mês + (mês anterior
        COMPLETO − MTD do mês anterior até `dom`). Reconstrói a janela de 30 dias
        sobre o cumulativo que reseta no dia 1. Ex.: faturamento de 12/06 = jun(1..12)
        + mai(13..31) ≈ um mês cheio (não os 12 dias parciais)."""
        atual = mtd(g, ano, mes)
        if atual is None:
            return None
        v = _numf(atual.get(colr))
        if v is None:
            return None
        pa, pmo = _prev_month(ano, mes)
        cheio, ate_dom = mes_cheio(g, pa, pmo), mtd(g, pa, pmo)
        extra = 0.0
        if cheio is not None and ate_dom is not None:
            fv, sv = _numf(cheio.get(colr)), _numf(ate_dom.get(colr))
            if fv is not None and sv is not None:
                extra = max(0.0, fv - sv)
        return v + extra

    def churn30(g: pd.DataFrame, ano: int, mes: int) -> float | None:
        """Churn dos ~30 dias (cancelados rolling 30d / base de pagantes), em %."""
        canc = rolling30(g, ano, mes, "cancelados")
        atual = mtd(g, ano, mes)
        pag = _numf(atual.get("pagantes")) if atual is not None else None
        if canc is None or not pag:
            return None
        return 100.0 * canc / pag

    def agr(row: pd.Series | None) -> float | None:
        if row is None:
            return None
        return (_numf(row.get("alunos_gympass")) or 0.0) + (_numf(row.get("alunos_totalpass")) or 0.0)

    def val(row: pd.Series | None, c: str) -> float | None:
        return _numf(row.get(c)) if row is not None else None

    rows: list[dict[str, Any]] = []
    for nome_u, g in sel.groupby("unidade", observed=True):
        nome = _clean(nome_u)
        if normalizar_unidade(nome) in _EXEC_EXCLUIR:
            continue  # unidade excluída da rede comparável (pedido de Felipe)
        g = g.sort_values("_data")
        cur = mtd(g, ry, rm)
        if cur is None:
            continue  # unidade sem dado no mês de referência (parada) -> fora
        # Faturamento EXIBIDO = MTD (acumulado no mês até o dia de referência): o
        # "faturamento até o dia disponível" que o Felipe pediu. O rolling30 (mês
        # cheio reconstruído com a cauda do mês anterior) inflava o mês PARCIAL
        # ~2x (SP jun 2,20x) e passa a servir SÓ como proxy de "unidade operante"
        # no gate abaixo, para o piso de R$20k não derrubar unidade real no mês
        # parcial (poucos dias de MTD ainda ficariam sob o piso).
        fat_cur = _numf(cur.get("faturamento"))
        fat_gate = rolling30(g, ry, rm, "faturamento")
        churn_cur = churn30(g, ry, rm)
        # Dado sujo: entradas administrativas/de teste (faturamento irrisório ou
        # churn impossível >100%) poluem ranking e totais -> fora.
        if fat_gate is None or fat_gate < _FAT_MIN_EXEC or (churn_cur is not None and churn_cur > 100.0):
            continue
        m1 = mtd(g, py, pm)
        c = coords.get(normalizar_unidade(nome))
        rows.append(
            {
                "nome": nome,
                "lat": c[0] if c else None,
                "lng": c[1] if c else None,
                "inauguracao": _clean(cur.get("inauguracao")),
                # faturamento = MTD (acumulado no mês até o dia de referência); M-1 =
                # MTD do mês anterior até o MESMO dia-do-mês (mtd() já limita a day<=dom)
                "fat_cur": fat_cur,
                "fat_m1": _numf(m1.get("faturamento")) if m1 is not None else None,
                "ativos_cur": val(cur, "ativos_total"),
                "ativos_m1": val(m1, "ativos_total"),
                "pag_cur": val(cur, "pagantes"),
                "pag_m1": val(m1, "pagantes"),
                "agr_cur": agr(cur),
                "agr_m1": agr(m1),
                "ticket_cur": val(cur, "ticket_medio_pagantes"),
                "ticket_m1": val(m1, "ticket_medio_pagantes"),
                "nps_cur": val(cur, "NPS"),
                "nps_m1": val(m1, "NPS"),
                "churn_cur": churn_cur,
                "churn_m1": churn30(g, py, pm),
            }
        )

    if not rows:
        raise HTTPException(404, f"Sem unidades com dados no mês de referência na UF {uf.upper()}.")

    U = pd.DataFrame(rows)
    for c in (
        "fat_cur fat_m1 ativos_cur ativos_m1 pag_cur pag_m1 agr_cur agr_m1 "
        "ticket_cur ticket_m1 nps_cur nps_m1 churn_cur churn_m1 lat lng"
    ).split():
        U[c] = pd.to_numeric(U[c], errors="coerce")

    def soma_metric(cur_c: str, m1_c: str) -> dict[str, Any]:
        """Total (soma). `atual` = todos; `m1`/delta na cesta com M-1 (comparável)."""
        both = U[U[cur_c].notna() & U[m1_c].notna()]
        m1_sum = float(both[m1_c].sum()) if len(both) else None
        cur_both = float(both[cur_c].sum()) if len(both) else None
        delta = (100.0 * (cur_both - m1_sum) / m1_sum) if (m1_sum and cur_both is not None) else None
        return {"atual": _num(U[cur_c].sum()), "m1": _num(m1_sum), "delta_pct": _num(delta, 1)}

    def media_metric(cur_c: str, m1_c: str, w_cur: str, w_m1: str) -> dict[str, Any]:
        atual, m1v = _wavg(U[cur_c], U[w_cur]), _wavg(U[m1_c], U[w_m1])
        delta = (100.0 * (atual - m1v) / m1v) if (atual is not None and m1v) else None
        return {"atual": _num(atual, 2), "m1": _num(m1v, 2), "delta_pct": _num(delta, 1)}

    tot_pag = float(U["pag_cur"].fillna(0).sum())
    tot_agr = float(U["agr_cur"].fillna(0).sum())
    base_split = tot_pag + tot_agr
    com_coord = U[U["lat"].notna()]

    unidades = [
        {
            "nome": r["nome"],
            "lat": _num(r["lat"], 6),
            "lng": _num(r["lng"], 6),
            "faturamento": _num(r["fat_cur"]),
            "ativos": _num(r["ativos_cur"]),
            "pagantes": _num(r["pag_cur"]),
            "agregadores": _num(r["agr_cur"]),
            "churn": _num(r["churn_cur"], 2),
            "ticket": _num(r["ticket_cur"], 2),
            "nps": _num(r["nps_cur"], 1),
            "inauguracao": r["inauguracao"],
        }
        for _, r in U.sort_values("fat_cur", ascending=False).iterrows()
    ]

    return {
        "uf": uf.upper(),
        "mes": mes_sel,
        "meses": meses[:12],
        "referencia": ref.strftime("%d/%m/%Y"),
        # clampa o dia ao último do mês anterior (M-1 de 31/05 é 30/04, não 31/04)
        "referencia_m1": (
            f"{min(dom, pd.Period(freq='M', year=py, month=pm).days_in_month):02d}/{pm:02d}/{py}"
        ),
        "centro": {
            "lat": _num(com_coord["lat"].mean(), 6) if len(com_coord) else None,
            "lng": _num(com_coord["lng"].mean(), 6) if len(com_coord) else None,
        },
        # Bandeira quadrada da Ultra (mesmo tile do Mapa Territorial) para plantar no
        # centro de cada bolha de faturamento no mapa da rede.
        "ultra_icon": _icone_ultra() if len(com_coord) else None,
        "totais": {
            "unidades": int(len(U)),
            "com_coordenada": int(len(com_coord)),
            "faturamento": soma_metric("fat_cur", "fat_m1"),
            "ativos": soma_metric("ativos_cur", "ativos_m1"),
            "pagantes": soma_metric("pag_cur", "pag_m1"),
            "agregadores": soma_metric("agr_cur", "agr_m1"),
            "churn": media_metric("churn_cur", "churn_m1", "pag_cur", "pag_m1"),
            "ticket": media_metric("ticket_cur", "ticket_m1", "pag_cur", "pag_m1"),
            "nps": media_metric("nps_cur", "nps_m1", "ativos_cur", "ativos_m1"),
            "pct_pagantes": _num(100 * tot_pag / base_split, 1) if base_split > 0 else None,
            "pct_agregadores": _num(100 * tot_agr / base_split, 1) if base_split > 0 else None,
        },
        "unidades": unidades,
    }


# ============================================================================
# Rotas — Relatorios PDF
# ============================================================================


class RelatorioMunicipalIn(BaseModel):
    uf: str
    municipio: str
    solicitante: str | None = None


@app.post("/api/relatorio/municipal")
def relatorio_municipal(body: RelatorioMunicipalIn) -> Response:
    """Relatorio Municipal (9 paginas). Acionado pelo 4o passo do mapa.

    Renderiza as 5 camadas de mapa (`render_mapas_municipio`) e AS PASSA ao gerador —
    sem isso o PDF saia sem nenhum mapa (o gerador cai em "Mapa indisponivel" em toda
    pagina), que era o defeito reportado ("relatorio nao gera"). Espelha o
    /api/relatorio/pontual: reaponta o cache de tiles (RELATIVO ao CWD do uvicorn em
    web/server) e degrada gracioso online -> offline -> sem mapas.
    """
    from motor_expansao.api.service import _competitors_ultra
    from motor_expansao.api.settings import Settings
    from motor_expansao.dashboard import relatorio_municipal as _relmun
    from motor_expansao.dashboard.relatorio_municipal import (
        _municipio_mask,
        agregar_municipio,
        gerar_payloads_download_relatorio_municipal,
        render_mapas_municipio,
    )

    df = carregar_uf_completo(body.uf)
    df_muni = df.loc[_municipio_mask(df, body.municipio)].copy()
    if df_muni.empty:
        raise HTTPException(
            404, f"Nenhum hexagono encontrado para '{body.municipio}' em {body.uf.upper()}."
        )

    cfg = Settings(
        censo_geo_dir=CENSO_GEO_DIR,
        ibge_dir=IBGE_DIR,
        ultra_dir=ULTRA_DIR,
        staging_dir=STAGING_DIR,
    )
    comp_df, ultra_df = _competitors_ultra(cfg)

    try:
        result = agregar_municipio(
            df,
            nome_municipio=body.municipio,
            uf=body.uf.upper(),
            competitors_df=comp_df,
            ultra_df=ultra_df,
            df_pre_filtrado=df_muni,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Falha ao agregar o municipio: {exc}") from exc

    # `_BASEMAP_CACHE_DIR` do modulo e RELATIVO ao CWD (uvicorn sobe de web/server).
    # Reaponta para o cache absoluto do checkout (mesmo motivo do /relatorio/pontual).
    _relmun._BASEMAP_CACHE_DIR = DATA_DIR / "cache" / "basemap_tiles"

    def _mapas(basemap: bool) -> dict[str, bytes]:
        return render_mapas_municipio(
            df_muni,
            result,
            competitors_df=comp_df,
            ultra_df=ultra_df,
            basemap=basemap,
        )

    # Ruas online -> offline (choropleth sem tiles) -> sem mapas. O PDF nunca falha
    # por causa do basemap; na pior hipotese sai como antes (sem mapas).
    try:
        mapas: dict[str, bytes] | None = _mapas(True)
    except Exception:  # noqa: BLE001
        try:
            mapas = _mapas(False)
        except Exception:  # noqa: BLE001
            mapas = None

    payloads = gerar_payloads_download_relatorio_municipal(
        result,
        mapas,
        ultra_dir=ULTRA_DIR if ULTRA_DIR.exists() else None,
        solicitante=body.solicitante,
    )
    return Response(
        content=payloads.pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{payloads.pdf_filename}"'
        },
    )


def _viabilidade_pdf_payload(body: ViabilidadeIn) -> dict[str, Any] | None:
    """Payload do slide de viabilidade do PDF — o MESMO `viabilidade_payload_v1` da tela.

    FIN-VIAB-01: o PDF NAO re-roda o motor nem realinha KPI nenhum. Antes esta funcao
    chamava o motor de novo e depois sobrescrevia payback/ROIC "para bater com a tela";
    era exatamente essa segunda passagem que fazia o mesmo cenario sair com payback
    35 x 33 e aluguel-teto R$55,5 mil x R$105,8 mil.

    O achatamento v1 -> chaves planas do slide (e os 4 PNGs) vem de
    `viabilidade_charts.montar_payload_pdf_viabilidade`, a ponte UNICA do PDF. Havia aqui
    uma segunda copia desse mapeamento e ela ja tinha regredido em dois pontos: a chave
    plana `aluguel_teto` (float) sobrescrevia a secao v1 homonima (dict) e sumia com a
    linha "ideal | teto | excecao"; e o waterfall reencontrava a linha de steady na serie
    por `maturacao_meses` em vez de ler o `dre` do payload, entao grafico e card do MESMO
    slide podiam sair de meses diferentes.

    Devolve o payload v1 + as chaves PLANAS que o slide legado consome + `graficos`.
    `None` em qualquer falha -> o PDF cai no payload so-numeros (`viabilidade_json`).
    """
    from motor_expansao.dashboard.viabilidade_charts import montar_payload_pdf_viabilidade

    try:
        payload = _payload_viabilidade(body)
    except Exception:  # noqa: BLE001 — o PDF nunca cai por causa da viabilidade
        return None

    saida: dict[str, Any] = dict(payload)
    try:
        saida.update(montar_payload_pdf_viabilidade(payload) or {})
    except Exception:  # noqa: BLE001 — sem graficos o slide sai so com os numeros
        saida.update(montar_payload_pdf_viabilidade(payload, incluir_graficos=False) or {})
    # `flag_viavel` nao faz parte do contrato v1 fechado; o slide le do `dre` quando existe.
    saida["flag_viavel"] = payload["dre"].get("flag_viavel")
    return saida


# Raio de EXIBICAO dos mapas de calor e do mapa de Concorrentes (pedido Felipe 2026-07-29).
# Constante de RENDER: NAO entra em `config.py` nem no §3 do CLAUDE.md e NAO toca o motor
# censitario (`RAIO_CENSITARIO_DEFAULT_KM` = 1,5 segue governando quais setores entram na conta).
# Enquadrar 1 km em vez de 1,5 km aumenta o zoom em ~1,5x e e' o que torna rua e entorno legiveis.
RAIO_MAPAS_DISPLAY_KM = 1.0


def _residual_hexes_do_ponto(lat: float, lng: float, staging_dir: Path):
    """Disco de hexes (grid_disk k=5, res 7) ao redor do ponto para o slide-hero
    "Socioeconomia e Residual Fitness": `oferta_efetiva_disponivel` (Residual) E
    `score_setor_2022_calibrado` (Socioeconomia, BLK-RELPON-13).

    DEFEITO CORRIGIDO (achado por Felipe em 2026-07-29): esta funcao lia SO
    `oferta_efetiva_disponivel`. Como `_render_camada_residual_hex` devolve lista vazia quando
    a `value_col` pedida nao esta no DataFrame, a chave `socioeconomia` simplesmente NAO existia
    no dict de mapas e o PDF do piloto saia com o painel de Socioeconomia em fallback textual —
    so o Residual aparecia. Nao havia erro: a ausencia da chave e' um caminho legitimo (ponto sem
    hex desenhavel), entao falhava em silencio. Mesma defesa da API (`api/service.py`): a coluna
    entra SE existir no schema, para nao quebrar em parquet antigo.

    Filtro direto no parquet de mercado (~91 linhas), espelhando `_residual_do_ponto`. `None`
    se o parquet faltar ou falhar -> as camadas de hexagono caem no fallback textual
    (offline-safe). READ-ONLY sobre o M1 (so leitura de parquet)."""
    mercado = staging_dir / "hexagonos_mercado_mapeado.parquet"
    if not mercado.is_file():
        return None
    try:
        import h3
        import pyarrow.compute as pc
        import pyarrow.dataset as ds

        centro = h3.latlng_to_cell(float(lat), float(lng), 7)
        cells = list(h3.grid_disk(centro, 5))
        if not cells:
            return None
        conjunto = ds.dataset(mercado)
        colunas = ["hex_id", "oferta_efetiva_disponivel"]
        # BLK-RELPON-13: o painel de Socioeconomia le `score_setor_2022_calibrado` do MESMO
        # disco de hexes. So pede se o schema tiver — parquet antigo continua servindo o Residual.
        if "score_setor_2022_calibrado" in conjunto.schema.names:
            colunas.append("score_setor_2022_calibrado")
        tbl = conjunto.to_table(filter=pc.field("hex_id").isin(cells), columns=colunas)
        if not tbl.num_rows:
            return None
        return tbl.to_pandas()
    except Exception:  # noqa: BLE001
        return None


@app.post("/api/relatorio/pontual")
async def relatorio_pontual(
    lat: float,
    lng: float,
    rotulo: str | None = None,
    solicitante: str | None = None,
    info_imovel: str | None = None,
    viabilidade_json: str | None = None,
    viabilidade_inputs_json: str | None = None,
    fotos: list[UploadFile] | None = None,
) -> Response:
    """Relatorio Pontual Censitario 1,5 km — com fotos, dados do imovel e viabilidade.

    Espelha a montagem da API de producao (`api/service.gerar_pdf_ponto`), mas usa
    o gerador com os kwargs opcionais que o piloto precisa (`fotos`, `info_imovel`,
    `viabilidade`) — aqueles a rota de producao nao expoe.

    `info_imovel` e `viabilidade_json` chegam como JSON serializado porque o corpo
    e multipart (por causa das fotos).

    Esta funcao so faz a parte ASSINCRONA (ler os uploads) e delega o resto ao
    threadpool — ver `_gerar_relatorio_pontual_pdf`.
    """
    # Unico I/O assincrono da rota: o corpo multipart.
    fotos_bytes: list[bytes] = []
    for f in fotos or []:
        conteudo = await f.read()
        if conteudo:
            fotos_bytes.append(conteudo)

    # O resto do trabalho e 100% SINCRONO e pesado (10-30 s). Rodando direto dentro do
    # `async def`, ele BLOQUEAVA o event loop do unico worker do uvicorn: enquanto um PDF
    # era gerado, TODAS as outras requisicoes ficavam presas na fila — inclusive as de
    # outros usuarios e o proprio /api/health (medido em producao em 2026-07-24: 3
    # relatorios simultaneos serializaram em 12/21/31 s e um /api/health levou 29 s).
    # Era isso que aparecia como "o relatorio carrega para sempre" na aba Viabilidade.
    # No threadpool o event loop segue livre e os pedidos rodam de fato em paralelo.
    async with _PDF_SEMAFORO:
        return await run_in_threadpool(
            _gerar_relatorio_pontual_pdf,
            lat,
            lng,
            rotulo,
            solicitante,
            info_imovel,
            viabilidade_json,
            viabilidade_inputs_json,
            fotos_bytes,
        )


def _gerar_relatorio_pontual_pdf(
    lat: float,
    lng: float,
    rotulo: str | None,
    solicitante: str | None,
    info_imovel: str | None,
    viabilidade_json: str | None,
    viabilidade_inputs_json: str | None,
    fotos_bytes: list[bytes],
) -> Response:
    """Corpo SINCRONO do Relatorio Pontual — roda no threadpool, nunca no event loop.

    Recebe as fotos ja lidas em bytes (o `await` ficou na rota). Deliberadamente `def`,
    nao `async def`: e o que mantem o servidor respondendo durante a geracao.
    """
    from motor_expansao.api.service import (
        _competitors_ultra,
        _nome_municipio_de,
        _residual_do_ponto,
        _resolver_e_carregar,
    )
    from motor_expansao.api.settings import Settings
    from motor_expansao.dashboard import censo_map as _censo_map
    from motor_expansao.dashboard.censo_map import (
        render_foto_satelite_ponto,
        render_mapas_censitarios_combinados,
    )

    # `_BASEMAP_CACHE_DIR` no modulo e RELATIVO ao CWD ("data/cache/basemap_tiles").
    # Como o uvicorn do piloto sobe de web/server, os tiles caiam em
    # web/server/data/ — 350 arquivos de cache dentro do codigo-fonte. Reaponta
    # para o cache absoluto do checkout, que ja existe e ja e gitignored.
    _censo_map._BASEMAP_CACHE_DIR = DATA_DIR / "cache" / "basemap_tiles"
    from motor_expansao.dashboard.censo_point import (
        RAIO_CENSITARIO_DEFAULT_KM,
        agregar_perfil_bairro_distrito,
        analisar_ponto_censitario_setores,
    )
    from motor_expansao.dashboard.censo_report import (
        gerar_pdf_relatorio_pontual_classico,
    )

    if not CENSO_GEO_DIR.exists():
        raise HTTPException(
            404,
            "Base geo dos setores censitarios ausente — o Relatorio Pontual precisa "
            f"de {CENSO_GEO_DIR}",
        )

    cfg = Settings(
        censo_geo_dir=CENSO_GEO_DIR,
        ibge_dir=IBGE_DIR,
        ultra_dir=ULTRA_DIR,
        staging_dir=STAGING_DIR,
    )

    try:
        uf, _cod, setores_df = _resolver_e_carregar(lat, lng, cfg)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Nao foi possivel resolver a coordenada: {exc}") from exc

    comp_df, ultra_df = _competitors_ultra(cfg)
    result = analisar_ponto_censitario_setores(
        lat,
        lng,
        setores_df,
        raio_km=RAIO_CENSITARIO_DEFAULT_KM,
        competitors_df=comp_df,
        ultra_df=ultra_df,
    )

    perfil_bairro = agregar_perfil_bairro_distrito(
        setores_df,
        cod_bairro=result.get("cod_bairro_ponto"),
        nome_bairro=result.get("nome_bairro_ponto"),
        nome_distrito=result.get("nome_distrito_ponto"),
        nome_municipio=_nome_municipio_de(setores_df),
        uf=uf,
    )

    ultra_dir = ULTRA_DIR if ULTRA_DIR.is_dir() else None
    # Disco de hexes p/ o choropleth Residual Fitness do slide-hero (grid_disk k=5).
    # None -> a camada residual cai no fallback textual (nao derruba o PDF).
    hexes_residual = _residual_hexes_do_ponto(lat, lng, STAGING_DIR)

    def _mapas(basemap: bool):
        return render_mapas_censitarios_combinados(
            lat,
            lng,
            setores_df,
            # RENDER, nao analise (pedido Felipe 2026-07-29): os mapas de calor e o de
            # Concorrentes enquadram 1 km em vez de 1,5 km -> mais zoom, rua e entorno legiveis.
            # A ANALISE segue em `RAIO_CENSITARIO_DEFAULT_KM` (1,5 km) na chamada de
            # `analisar_ponto_censitario_setores` acima: os Big Numbers do PDF NAO mudam.
            # Consequencia a olhar no gate visual: o rodape do mapa passa a dizer "Raio 1,0 km"
            # (descreve o circulo desenhado) enquanto os numeros do relatorio continuam sendo os
            # de 1,5 km. Alinhar os dois exige mexer no raio de ANALISE — parametro canonico do
            # §3, com DEC e gate humano proprios.
            raio_km=RAIO_MAPAS_DISPLAY_KM,
            competitors_df=comp_df,
            ultra_df=ultra_df,
            basemap=basemap,
            ultra_logo_dir=ultra_dir,
            street_ceil=215,
            street_gain=1.3,
            street_cap=200,
            # Cor CHEIA, fiel a legenda (pedido Felipe 2026-07-29). O `110` existia para as ruas
            # do basemap aparecerem POR BAIXO da cor; desde o BLK-BASEMAP-06 a malha viaria e
            # desenhada POR CIMA, pelo overlay do tileserver, entao o motivo do alpha baixo
            # deixou de existir. A legenda sempre pintou RGB solido ignorando este alpha (ver
            # `_CHOROPLETH_ALPHA` em censo_map.py) — era por isso que mapa e legenda nao batiam.
            choropleth_alpha=255,
            hexes_df=hexes_residual,
        )

    # Ruas online -> offline -> sem mapas. O PDF nunca falha por causa do basemap.
    try:
        mapas = _mapas(True)
    except Exception:  # noqa: BLE001
        try:
            mapas = _mapas(False)
        except Exception:  # noqa: BLE001
            mapas = None

    try:
        residual = _residual_do_ponto(lat, lng, cfg)
    except Exception:  # noqa: BLE001
        residual = None

    # BLK-SAT-01: vista aerea (satelite Esri) da capa do PDF. A chave vem de env
    # API_ARCGIS_API_KEY (passthrough no compose); sem chave/rede -> None -> pagina
    # OMITIDA e o resto do PDF sai igual. Nenhum caminho novo derruba a geracao.
    try:
        foto_satelite = render_foto_satelite_ponto(lat, lng)
    except Exception:  # noqa: BLE001
        foto_satelite = None

    # Viabilidade no PDF: com os INPUTS (viabilidade_inputs_json) re-roda o motor p/ incluir
    # os GRAFICOS (rampa/faturamento/FCF/DRE waterfall); sem eles (ou em falha) cai nos numeros
    # crus do viabilidade_json (retrocompat). Nenhum caminho novo derruba a geracao.
    viab_pdf: dict[str, Any] | None = None
    if viabilidade_inputs_json:
        try:
            viab_pdf = _viabilidade_pdf_payload(
                ViabilidadeIn(**json.loads(viabilidade_inputs_json))
            )
        except Exception:  # noqa: BLE001
            viab_pdf = None
    if viab_pdf is None and viabilidade_json:
        viab_pdf = json.loads(viabilidade_json)

    # BLK-RELPON-14: o gerador unico e' a estetica CLASSICA. `gerar_pdf_relatorio_pontual_censitario`
    # virou wrapper depreciado dela; chamamos a classica direto para nao emitir
    # DeprecationWarning a cada PDF do piloto. Os ARGUMENTOS sao os mesmos e a assinatura da
    # classica e' superset da antiga — nenhum kwarg daqui ficou de fora.
    #
    # ATENCAO PARA O GATE VISUAL: os BYTES do PDF MUDAM. Antes esta rota saia pelo template
    # "recente"; agora sai pela estetica CLASSICA (capa com endereco acima do subtitulo, banda
    # turquesa com margem e icone, banda magenta no rodape, Realizacao com link clicavel e data
    # por extenso) e sem o slide "Imagem do Entorno" (8 -> 7 paginas de base). E o efeito
    # PRETENDIDO da unificacao, nao colateral — mas e' perceptivel para quem usa o piloto.
    pdf = gerar_pdf_relatorio_pontual_classico(
        result,
        mapas,
        residual=residual,
        perfil_bairro=perfil_bairro,
        ultra_dir=ultra_dir,
        solicitante=solicitante,
        rotulo=rotulo,
        fotos=fotos_bytes[:2] or None,
        info_imovel=json.loads(info_imovel) if info_imovel else None,
        viabilidade=viab_pdf,
        foto_satelite=foto_satelite,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="relatorio_pontual.pdf"'},
    )


# ============================================================================
# Simulador financeiro completo em XLSX (formulas vivas)
#
# Pedido do dono do produto (Felipe, 2026-07-24): abrir a planilha na frente do
# investidor e defender os numeros — DRE, folha de pagamento e fluxo de caixa com
# possibilidade de EDICAO MANUAL. Por isso a planilha sai com FORMULAS, nao com
# valores estaticos: mudar a demanda, o aluguel ou um salario dentro do Excel
# recalcula os 60 meses ali mesmo, sem voltar ao sistema.
#
# Esta rota nao contem calculo financeiro nenhum: reusa `_premissas_do_body` e
# `_investimento` (os MESMOS do /api/viabilidade) e delega a montagem ao motor.
# ============================================================================

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _slug_arquivo(texto: str | None, default: str = "cenario") -> str:
    """Slug ASCII (sem acento) para NOME DE ARQUIVO.

    Excecao explicita do §2 do CLAUDE.md: texto de usuario leva acento, nome de
    arquivo NAO — acento em `Content-Disposition` sai mojibake no download.
    """
    base = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower()
    return base[:60] or default


def _gerador_simulador_xlsx() -> Callable[..., bytes]:
    """Resolve o gerador do XLSX no motor (import lazy, como o resto do backend).

    Isolado em uma funcao por dois motivos: o import pesa (openpyxl) e nao deve
    custar no boot do piloto, e o teste troca o gerador aqui para nao pagar a
    montagem real da planilha.
    """
    try:
        from motor_expansao.dimensionamento.simulador_xlsx import gerar_simulador_xlsx
    except ImportError as exc:  # modulo do motor ausente neste checkout
        # Texto de USUARIO (chega ao box de erro da tela) -> acentuado, §2 do CLAUDE.md.
        raise HTTPException(
            503,
            "O gerador da planilha não está disponível neste servidor "
            f"(motor_expansao.dimensionamento.simulador_xlsx): {exc}",
        ) from exc
    return gerar_simulador_xlsx


def _kwargs_aceitos(fn: Callable[..., Any], **candidatos: Any) -> dict[str, Any]:
    """Mantem so os kwargs OPCIONAIS que a assinatura do gerador de fato aceita.

    Os extras (rotulo/m2) sao enfeite de cabecalho da planilha, nao contrato: um
    nome diferente do outro lado viraria `TypeError` em runtime — HTTP 500 no lugar
    do arquivo. Os argumentos ESSENCIAIS (demanda/premissas/investimento) vao
    posicionais e nao passam por aqui: se aqueles nao casarem, tem de estourar.
    """
    params = inspect.signature(fn).parameters
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return candidatos
    return {k: v for k, v in candidatos.items() if k in params}


@app.post("/api/simulador/xlsx")
async def simulador_xlsx(body: ViabilidadeIn, rotulo: str | None = None) -> Response:
    """Simulador financeiro completo em XLSX, com formulas vivas.

    Mesmo corpo do /api/viabilidade (`ViabilidadeIn`); `rotulo` (query) so nomeia o
    arquivo. A montagem e SINCRONA e pesada (openpyxl escrevendo 60 meses de DRE,
    folha e fluxo de caixa), entao roda no threadpool — igual ao PDF Pontual. Sem
    isso ela bloquearia o event loop do unico worker do uvicorn e todo o resto do
    piloto ficaria preso na fila durante a geracao.

    GUARDRAILS: nada e escrito em disco (BytesIO dentro do gerador) e a demanda
    segue sendo PREMISSA do operador (DEC-009), nunca derivada de lat/lng.
    """
    return await run_in_threadpool(_gerar_simulador_xlsx_response, body, rotulo)


def _gerar_simulador_xlsx_response(body: ViabilidadeIn, rotulo: str | None) -> Response:
    """Corpo SINCRONO da rota do XLSX — roda no threadpool, nunca no event loop.

    Deliberadamente `def`, nao `async def`: e o que mantem o servidor respondendo
    durante a geracao.
    """
    gerar = _gerador_simulador_xlsx()
    premissas = _premissas_do_body(body)
    inv = _investimento(body)
    extras = _kwargs_aceitos(gerar, rotulo=rotulo, m2=float(body.m2))

    conteudo = gerar(float(body.demanda), premissas, inv, **extras)

    nome = f"simulador_viabilidade_{_slug_arquivo(rotulo)}.xlsx"
    return Response(
        content=conteudo,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


# ============================================================================
# SPA estatico (build do Vite) — producao
# ============================================================================
# Em producao UM container serve o frontend (dist/) E a API na mesma porta; o
# Caddy so faz reverse_proxy (espelha dashboard->streamlit). O mount na raiz vem
# por ULTIMO (todas as rotas /api ja foram registradas acima) com html=True p/ o
# SPA. So monta se o dist/ existir (em dev o Vite serve o front na :5000 e faz
# proxy /api para ca, entao o dist/ nem existe). Caminho configuravel via WEB_DIST_DIR.
_DIST_DIR = Path(os.environ.get("WEB_DIST_DIR", str(_REPO_ROOT / "web" / "dist")))
if _DIST_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST_DIR), html=True), name="spa")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8899)
