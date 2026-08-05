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
from fastapi import FastAPI, Header, HTTPException, UploadFile
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

# Nucleo semantico da Visao Executiva 2.0 (DEC-023). Importado no topo, e nao de forma
# lazy como o resto do modulo, porque e' consumido por helpers de modulo e nao so' dentro
# de rotas; sao 4 modulos que dependem apenas de pandas (ja carregado). O gerador de
# export (`rede_export`) segue lazy, dentro das rotas: ele puxa fpdf2 e openpyxl.
from motor_expansao.dashboard import (  # noqa: E402
    rede_cadastro,
    rede_coorte,
    rede_diagnostico,
    rede_metricas,
)

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

    Ausente -> `TEXTO_SEM_DADO`, a MESMA string dos PDFs (2026-07-31): a narrativa do piloto
    e o relatorio que sai dela nao podem chamar a mesma coisa por nomes diferentes.
    """
    from motor_expansao.dashboard.constants import TEXTO_SEM_DADO

    n = _num(v, casas)
    if n is None:
        return TEXTO_SEM_DADO
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


def _pct_do_faturamento(valor: Any, faturamento: Any) -> float | None:
    """Fracao de uma linha da DRE sobre o faturamento bruto de steady-state.

    Existe no BACKEND por causa do FIN-VIAB-01: a tela nao divide numero
    financeiro, so renderiza o que o payload traz. `None` (o front omite o %)
    quando o faturamento e zero/ausente, o que evita divisao por zero.
    """
    fat = _num(faturamento, 2)
    v = _num(valor, 2)
    if v is None or not fat:
        return None
    return _num(v / fat, 4)


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
# Cadastro AMPLO das unidades Ultra (150 linhas, com `uf`/`cidade`/`flag_coord_valida`).
# O `ULTRA_PERF_PARQUET` acima so tem as 54 unidades da planilha GeoFusion e esta
# congelado; este cadastro cobre a rede atual e serve para COMPLETAR as coordenadas
# da Visao Executiva (ver `_ultra_coord_map`). READ-ONLY, como todo o resto.
ULTRA_MAPEADAS_PARQUET = STAGING_DIR / "unidades_ultra_mapeadas.parquet"
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


def _unidade(n: int, singular: str, plural: str) -> str:
    """Concorda a unidade do funil com a contagem.

    Os `funil_unit`/`funil_from` eram plural FIXO, entao com 1 item a tela escrevia
    "1 hexágonos de alto potencial" / "em 1 municípios" — defeito apontado pelo Juan
    em 2026-08-03 olhando a visao de UF. Fica logo abaixo do numero grande, entao
    e' das primeiras coisas que o olho pega.
    """
    return singular if n == 1 else plural


def _faixa_para_chip(
    score: float | None, faixas: list[tuple[int, int, str, str, str]]
) -> tuple[str, str | None, str | None]:
    """(nome, tom, cor) da faixa. A COR e' o que o chip usa de fato — o `tom` fica
    como fallback para front antigo que ainda nao leia `tag_cor`.

    Import lazy como o resto do modulo: `app.py` nao carrega o motor na subida.
    """
    from motor_expansao.dashboard.constants import faixa_do_score

    nome, tom = faixa_do_score(score, faixas)
    if not nome:
        return "", None, None
    cor = next((c for _de, _ate, n, c, _t in faixas if n == nome), None)
    return nome, tom or None, cor


def _etiqueta(
    metrica: str, valor: float | None, rank: int, row: pd.Series
) -> tuple[str, str | None, str | None]:
    """Rotulo curto e informativo por item do ranking.

    Repetir o nome da camada em todo item ("CENSITÁRIO" x4) e ruido: a camada ja
    esta no cabecalho do painel. A etiqueta diz algo que muda entre as linhas.

    BLK-MAPA-FAIXAS-01: as camadas 1/2/3 usam as MESMAS faixas da legenda do mapa
    (`constants.FAIXAS_MAPA_*`). Antes cada uma tinha regua propria — score >= 90/80
    aqui contra cortes de 20 em 20 na legenda; alunos >= 6.000/3.000 aqui contra a
    ancora de 2.500 = uma unidade la. Medido em Campinas: 2.400 alunos saiam
    etiquetados "Baixa" e, na legenda ao lado, "Livre" (96% de uma unidade cheia).
    Regua unica elimina a contradicao.

    O passo 4 continua com vocabulario de FILA, nao de intensidade: ali a leitura e
    a ordem de ataque, nao o quanto o hexagono comporta.

    O ramo `"conc. 2 km"` (camada 3) CONTINUA VIVO. Ele parecia codigo morto quando
    este trabalho comecou — nenhuma chamada passava esse label — mas o PR #184
    introduziu `metrica_etiqueta` justamente para reviva-lo, separando "unidade
    exibida sob o numero" de "chave que escolhe o ramo". Removido, a camada 3 do
    funil por MUNICIPIO saia com a etiqueta VAZIA (medido em Campinas). Nao se
    reverte em silencio uma decisao ja mergeada.

    ATENCAO ao homonimo: `Livre` existe nos DOIS vocabularios com sentidos
    diferentes — aqui e' "nenhum concorrente no hexagono", na camada 2 e' "cabe uma
    unidade inteira". A camada 3 pinta pelo residual mas rotula pela concorrencia,
    entao os dois podem aparecer na mesma tela. Se incomodar, e' decisao de texto.
    """
    from motor_expansao.dashboard.constants import (
        CAPACIDADE_UNIDADE_ALUNOS,
        FAIXAS_MAPA_DEMANDA,
        FAIXAS_MAPA_POTENCIAL,
    )

    if metrica == "score":
        # `valor` JA e' o score 0-100 (`score_setor_2022_calibrado`), e vai CRU: o
        # contrato de `faixa_do_score` para score ausente e' ("", ""), ou seja, sem
        # chip. Com o `or 0` que estava aqui, hex sem score caia na primeira faixa e
        # a tela AFIRMAVA "Desfavorável" (chip vermelho) sobre um dado que nao existe.
        return _faixa_para_chip(valor, FAIXAS_MAPA_POTENCIAL)
    if metrica == "conc. 2 km":
        # Leitura COMPETITIVA da camada 3 (PR #184): quantos concorrentes ha no hex.
        n = int(row.get("n_concorrentes_est") or 0)
        if n == 0:
            return "Livre", "green", None
        if n <= 2:
            return "Adensar", "blue", None
        return "Disputa", "red", None
    if metrica == "residual":
        if row.get("_fila"):
            # Passo 4: a etiqueta e' a FAIXA DE OPORTUNIDADE do M1, a mesma que a
            # legenda dessa camada lista e a mesma que pinta o hexagono. Era
            # "Agora/Próximo/Fila" com tom azul fixo, que discordava da legenda ao
            # lado (Juan, 2026-08-03). A posicao na fila NAO se perde: ela ja aparece
            # como "1º/2º/3º" no rank do item e sobre o hexagono no mapa.
            from motor_expansao.dashboard.constants import FAIXA_COLORS_POR_LABEL

            rotulo = _faixa_label(row.get("faixa_oportunidade"))
            if rotulo:
                return rotulo, None, FAIXA_COLORS_POR_LABEL.get(rotulo)
            return "", None, None
        # Aqui `valor` vem em ALUNOS (`oferta_efetiva_disponivel`), nao em score.
        # Converte pela MESMA formula do M1 (100 * alunos / 2.500, saturando em 100)
        # para cair na faixa certa da legenda. Residual ausente NAO vira zero pelo
        # mesmo motivo do ramo de score: "Saturado" e' uma afirmacao, e o dado falta.
        if valor is None:
            return "", None, None
        score = 100.0 * float(valor) / CAPACIDADE_UNIDADE_ALUNOS
        return _faixa_para_chip(score, FAIXAS_MAPA_DEMANDA)
    return "", None, None


def _rank_items(
    df: pd.DataFrame,
    col: str,
    label_metrica: str,
    tom: str,
    casas: int = 0,
    bairros: dict[str, str] | None = None,
    limite: int = 10,
    metrica_etiqueta: str | None = None,
) -> list[dict[str, Any]]:
    """Top-N localidades por uma coluna, no formato do painel de ranking.

    `limite` = 10: mostra ate as 10 melhores. Como o df ja chega FILTRADO pelo
    funil (quentes / residual >= 2000 / white space), todo item e viavel por
    construcao; se houver menos de 10 localidades distintas, a lista encurta
    sozinha (Felipe 2026-07-20: "as 10 melhores, apenas se forem viaveis").

    `label_metrica` e' TEXTO EXIBIDO sob o valor no painel (unidade do numero);
    `metrica_etiqueta`, quando dado, e' a CHAVE que escolhe o ramo do `_etiqueta`.
    Sao coisas diferentes: no passo 3 o valor continua sendo residual (em alunos),
    mas a etiqueta e' a leitura competitiva (Livre / Adensar / Disputa). Enquanto
    os dois andavam juntos no mesmo parametro, o ramo "conc. 2 km" nunca rodava."""
    from motor_expansao.dashboard.constants import TEXTO_SEM_DADO

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
        titulo = local or (r.get("nome_municipio") or TEXTO_SEM_DADO)
        chave = str(titulo).casefold()
        if chave in vistos:
            continue
        vistos.add(chave)
        valor = _num(r.get(col), casas)
        rank = len(itens) + 1
        # A etiqueta sai do valor CRU, nao do arredondado: com `casas=0`, um score
        # 79,6 viraria 80 e o chip diria "Excelente" enquanto o mapa pinta a banda
        # 70-80 e a visao de UF (que usa o valor sem arredondar) diz "Forte". Seria
        # a divergencia de duas reguas que este bloco existe para eliminar, na borda.
        etiqueta, tom_item, cor_item = _etiqueta(
            metrica_etiqueta or label_metrica, _numf(r.get(col)), rank, r
        )
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
                "tag_cor": cor_item,
            }
        )
        if len(itens) == limite:
            break
    return itens


def _narrativa_concorrencia(n_residual: int, n_white: int) -> str:
    """Texto do passo 3, com o caso `n_white == 0` dito por extenso.

    Compartilhada pelos dois niveis (municipio e UF) porque a regra e a mesma: sem
    fallback, `n_white == 0` deixa os passos 3 e 4 SEM itens — e a lista vazia so nao
    parece bug se a narrativa disser que nao ha area sem concorrencia no recorte. Alem
    disso a frase antiga saia agramatical no zero ("0 nao tem nenhum concorrente").
    """
    if n_residual == 0:
        return (
            "Nenhuma região chegou com residual até aqui, então não há pressão "
            "concorrencial a avaliar neste recorte."
        )
    if n_white == 0:
        return (
            f"Dessas {_fmt(n_residual)}, quais estão desguarnecidas? Nenhuma: todas já "
            "têm concorrente dentro do hexágono. Não há área sem concorrência neste "
            "recorte — por isso a lista abaixo fica vazia. Entrar aqui significa "
            "disputar espaço, protegendo o corredor Ultra."
        )
    verbo = "não tem" if n_white == 1 else "não têm"
    return (
        f"Dessas {_fmt(n_residual)}, quais estão desguarnecidas? {_fmt(n_white)} {verbo} "
        "nenhum concorrente no hexágono; as demais exigem entrar protegendo o corredor "
        "Ultra contra a concorrência."
    )


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

    # Passo 3 — Concorrencia: dos residuais, quais estao desguarnecidos. `white` e a
    # base UNICA dos passos 3 e 4 — SEM fallback para o residual (decisao do dono,
    # 2026-08-03: "os top 10 deverao se referir aos hexagonos livres"). O passo 3 ja
    # destacava so o white no mapa (`hexes`) e contava so o white no numerao
    # (`funil_big`); ranquear o residual quando nao havia white enchia o painel de
    # hexagono APAGADO e contradizia o proprio numerao (0). Municipio saturado passa a
    # ter os passos 3 e 4 sem NENHUM item, e a lista vazia e a resposta CORRETA ("nao
    # ha area livre aqui") — o texto do passo (`_narrativa_concorrencia`) diz isso.
    white = residual[residual["n_concorrentes_est"] == 0] if len(residual) else residual

    # Passo 4 — Recomendacao: fila de ate 10 aberturas priorizada por residual, so com
    # white space. A fila e 100% viavel; encurta sozinha com menos de 10 candidatos e
    # fica vazia quando nao ha nenhum (o `if` so protege o df sem a coluna).
    fila = white.nlargest(10, "oferta_efetiva_disponivel") if len(white) else white

    passos = [
        {
            "n": 1,
            "mode": "censitário",
            "titulo": "Potencial socioeconômico",
            "narrativa": (
                f"{municipio} tem {_fmt(total)} hexágonos habitáveis. A primeira pergunta é "
                "onde vive gente com renda e perfil para treinar — o censo 2022 acende "
                f"{_fmt(len(quentes))} hexágonos de alto potencial."
            ),
            "funil_big": len(quentes),
            "funil_unit": _unidade(len(quentes), "hexágono de alto potencial", "hexágonos de alto potencial"),
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
                "Alto potencial não basta: precisa ter espaço. Descontando a oferta já "
                f"instalada, sobram {_fmt(len(residual))} regiões com residual fitness "
                f"real — {_fmt(alunos_residual or 0)} alunos não atendidos."
            ),
            "funil_big": len(residual),
            "funil_unit": _unidade(len(residual), "região com residual", "regiões com residual"),
            "funil_from": f"{_fmt(len(quentes))} hexágonos de alto potencial",
            "metrica": "residual",
            "itens": _rank_items(residual, "oferta_efetiva_disponivel", "residual", "green", bairros=bairros),
            "hexes": residual["hex_id"].tolist(),
        },
        {
            "n": 3,
            "mode": "competitivo",
            "titulo": "Pressão concorrencial",
            "narrativa": _narrativa_concorrencia(len(residual), len(white)),
            "funil_big": len(white),
            "funil_unit": _unidade(len(white), "área sem concorrência", "áreas sem concorrência"),
            "funil_from": f"{_fmt(len(residual))} regiões",
            "metrica": "conc. 2 km",
            "itens": _rank_items(
                white,
                "oferta_efetiva_disponivel",
                "residual",
                "amber",
                bairros=bairros,
                metrica_etiqueta="conc. 2 km",
            ),
            "hexes": white["hex_id"].tolist(),
        },
        {
            "n": 4,
            "mode": "recomendação",
            "titulo": "Para onde crescer",
            "narrativa": (
                f"A síntese das camadas vira ação: uma fila de {_fmt(len(fila))} aberturas "
                "que captura o máximo de residual sem canibalizar a rede atual."
                if len(fila)
                else "A síntese das camadas não gera fila aqui: sem nenhuma área livre de "
                "concorrência, não há abertura a recomendar neste recorte. Avalie outro "
                "município — ou uma entrada disputando espaço, que é decisão à parte."
            ),
            "funil_big": len(fila),
            "funil_unit": _unidade(len(fila), "abertura na fila", "aberturas na fila"),
            "funil_from": f"{_fmt(len(white))} áreas sem concorrência",
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
    modo: str, valor: float | None, rank: int, fila: bool = False
) -> tuple[str, str | None]:
    """Etiqueta curta do item do ranking de MUNICIPIOS.

    Ramifica por `modo` ("count" = contagem de hexes; qualquer outro = soma de
    residual), NAO pelo `label` exibido: o label e' texto de usuario e passou a ser
    acentuado ("hexágonos"), e valor acentuado nao pode virar chave de comparacao.
    """
    v = valor or 0
    if fila:
        return {1: "Agora", 2: "Próximo", 3: "Fila"}.get(rank, "Espera"), None
    if modo == "count":
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


def _hex_representativo(df: pd.DataFrame, value_col: str | None) -> dict[str, str]:
    """Um hex ancora por municipio, para o numero do ranking pousar no mapa.

    Enquanto o item de municipio saia com `hex_id` vazio, o TextLayer do front
    (que pula item sem hex_id) nao desenhava numero NENHUM na visao de estado.
    Criterio explicito e deterministico: o melhor hex do municipio pela coluna que
    esta sendo agregada; no modo de contagem (sem `value_col`) cai para o maior
    score censitario e, na falta dele, populacao/oferta. Desempate por `hex_id`
    para nunca depender da ordem acidental das linhas.
    """
    if "hex_id" not in df.columns or "nome_municipio" not in df.columns or not len(df):
        return {}
    candidatas = [value_col] if value_col else []
    candidatas += ["score_setor_2022_calibrado", "pop_leitura", "oferta_efetiva_disponivel"]
    col = next((c for c in candidatas if c and c in df.columns), None)
    if col is None:
        ordenado = df.sort_values("hex_id")
    else:
        # na_position="last": hex sem a metrica so e ancora se nao houver outro.
        ordenado = df.sort_values([col, "hex_id"], ascending=[False, True], na_position="last")
    serie = ordenado.groupby("nome_municipio", observed=True)["hex_id"].first()
    return {str(muni): str(hid) for muni, hid in serie.items() if pd.notna(hid)}


def _melhor_faixa_por_municipio(
    df: pd.DataFrame, faixa_por: str
) -> dict[str, tuple[str, str | None]]:
    """`nome_municipio` -> (rotulo da faixa, cor) do MELHOR hexagono do municipio.

    "Melhor" = maior score da camada ("potencial"/"demanda") ou faixa M1 mais alta
    ("m1"). READ-ONLY: so le colunas ja materializadas.
    """
    from motor_expansao.dashboard.constants import (
        FAIXA_COLORS_POR_LABEL,
        FAIXA_ORDEM,
        FAIXAS_MAPA_DEMANDA,
        FAIXAS_MAPA_POTENCIAL,
    )

    if "nome_municipio" not in df.columns or not len(df):
        return {}

    if faixa_por == "m1":
        if "faixa_oportunidade" not in df.columns:
            return {}
        # Ordena pela ORDEM CANONICA do M1 (nao alfabetica) e fica com a melhor.
        posicao = {nome: i for i, nome in enumerate(FAIXA_ORDEM)}
        out: dict[str, tuple[str, str | None]] = {}
        for muni, grupo in df.groupby("nome_municipio", observed=True)["faixa_oportunidade"]:
            validas = [v for v in grupo.dropna().astype(str) if v in posicao]
            if not validas:
                continue
            melhor = min(validas, key=lambda v: posicao[v])
            rotulo = _faixa_label(melhor) or ""
            out[str(muni)] = (rotulo, FAIXA_COLORS_POR_LABEL.get(rotulo))
        return out

    col, faixas = (
        ("score_setor_2022_calibrado", FAIXAS_MAPA_POTENCIAL)
        if faixa_por == "potencial"
        else ("score_oportunidade_residual", FAIXAS_MAPA_DEMANDA)
    )
    if col not in df.columns:
        return {}
    maximos = df.groupby("nome_municipio", observed=True)[col].max()
    resultado: dict[str, tuple[str, str | None]] = {}
    for muni, valor in maximos.items():
        nome, _tom, cor = _faixa_para_chip(_num(valor), faixas)
        if nome:
            resultado[str(muni)] = (nome, cor)
    return resultado


def _rank_municipios(
    df: pd.DataFrame,
    value_col: str | None,
    modo: str,
    label: str,
    tom: str,
    fila: bool = False,
    *,
    faixa_por: str | None = None,
) -> list[dict[str, Any]]:
    """Top-10 MUNICÍPIOS por uma métrica agregada. Cada item carrega `municipio`
    para o front fazer o drill-down (clicar -> filtra para o município).

    `faixa_por` (BLK-MAPA-FAIXAS-01) define a etiqueta pelo MELHOR HEXAGONO do
    municipio, na MESMA regua da legenda do mapa: "potencial" e "demanda" usam as
    faixas de score e "m1" usa a faixa de oportunidade. Antes daqui saia vocabulario
    proprio (Polo/Forte/Emergente, Alta/Média/Baixa, Agora/Próximo) que nao existia
    em legenda nenhuma — a visao de UF falava um idioma e a de municipio, outro
    (Juan, 2026-08-03).

    Por que o MELHOR hexagono e nao a soma: as faixas sao definidas por hexagono e
    saturam em uma unidade (2.500 alunos). Aplicar "Livre" a um municipio com 20.000
    alunos residuais afirmaria que ali cabe UMA unidade, quando cabem oito. O melhor
    hex e' comparavel a legenda e responde a pergunta que o ranking faz: "vale a pena
    olhar este municipio?".
    """
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
    # Ancora so' dos 10 que entram no painel (evita ordenar a UF inteira).
    ancoras = _hex_representativo(
        df[df["nome_municipio"].isin(list(serie.index))], value_col if modo != "count" else None
    )
    melhor = _melhor_faixa_por_municipio(df, faixa_por) if faixa_por else {}
    itens: list[dict[str, Any]] = []
    for i, (muni, val) in enumerate(serie.items(), 1):
        valor = _num(val)
        if faixa_por:
            etiqueta, cor_item = melhor.get(str(muni), ("", None))
            tom_item = None
        else:
            etiqueta, tom_item = _etiqueta_muni(modo, valor, i, fila)
            cor_item = None
        itens.append(
            {
                "rank": i,
                "hex_id": ancoras.get(str(muni), ""),
                "municipio": str(muni),
                "titulo": str(muni),
                "sub": None,
                "valor": valor,
                "label": label,
                "tag": etiqueta,
                "tom": tom_item or tom,
                "tag_cor": cor_item,
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
    # Base dos passos 3 e 4: SOMENTE o white space, igual ao funil municipal (decisao
    # do dono, 2026-08-03). Sem hexagono livre a UF inteira sai com os passos 3 e 4
    # vazios — e isso e o certo: o numerao ja diz 0 e o mapa nao acende nada; ranquear
    # o residual ali fazia o painel prometer municipios que o passo acabara de excluir.
    n_reco = (
        int(white.groupby("nome_municipio", observed=True)["oferta_efetiva_disponivel"].sum().gt(0).sum())
        if len(white)
        else 0
    )

    return [
        {
            "n": 1,
            "mode": "censitário",
            "titulo": "Potencial socioeconômico",
            "narrativa": (
                f"{uf} tem {_fmt(total)} hexágonos habitáveis em {_fmt(n_munis)} "
                f"{'município' if n_munis == 1 else 'municípios'}. "
                f"O censo 2022 acende {_fmt(len(quentes))} hexágonos de alto potencial."
            ),
            "funil_big": len(quentes),
            "funil_unit": _unidade(len(quentes), "hexágono de alto potencial", "hexágonos de alto potencial"),
            "funil_from": f"{_fmt(total)} hexágonos",
            "metrica": "score",
            "itens": _rank_municipios(quentes, None, "count", "hexágonos", "blue", faixa_por="potencial"),
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
            "funil_unit": _unidade(len(residual), "região com residual", "regiões com residual"),
            "funil_from": f"{_fmt(len(quentes))} hexágonos de alto potencial",
            "metrica": "residual",
            "itens": _rank_municipios(residual, "oferta_efetiva_disponivel", "sum", "residual", "green", faixa_por="demanda"),
            "hexes": residual["hex_id"].tolist(),
        },
        {
            "n": 3,
            "mode": "competitivo",
            "titulo": "Pressão concorrencial",
            "narrativa": _narrativa_concorrencia(len(residual), len(white)),
            "funil_big": len(white),
            "funil_unit": _unidade(len(white), "área sem concorrência", "áreas sem concorrência"),
            "funil_from": f"{_fmt(len(residual))} regiões",
            "metrica": "conc. 2 km",
            # Fonte `white` vem do #184 (corrige a camada 3 a mostrar so' o que nao
            # tem concorrente); `faixa_por` vem do BLK-MAPA-FAIXAS-01.
            "itens": _rank_municipios(
                white, "oferta_efetiva_disponivel", "sum", "residual", "amber", faixa_por="demanda"
            ),
            "hexes": (white["hex_id"].tolist() if len(white) else []),
        },
        {
            "n": 4,
            "mode": "recomendação",
            "titulo": "Para onde crescer",
            "narrativa": (
                f"A fila de municípios para entrar: {_fmt(n_reco)} onde o residual é maior e a "
                "rede Ultra ainda tem espaço. Clique num município para aprofundar."
                if n_reco
                else "Nenhum município deste estado tem área livre de concorrência com "
                "residual: a fila fica vazia. Amplie o recorte ou avalie uma entrada "
                "disputando espaço, que é decisão à parte."
            ),
            "funil_big": n_reco,
            "funil_unit": _unidade(n_reco, "município na fila", "municípios na fila"),
            "funil_from": f"{_fmt(len(white))} áreas sem concorrência",
            "metrica": "residual",
            "itens": _rank_municipios(
                white,
                "oferta_efetiva_disponivel",
                "sum",
                "residual",
                "blue",
                fila=True,
                # Passo 4 = faixa de oportunidade do M1, igual a legenda desta camada.
                # A ordem da fila continua legivel no rank (1º, 2º, 3º) do proprio item.
                faixa_por="m1",
            ),
            "hexes": (white["hex_id"].tolist() if len(white) else []),
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


def limpar_caches() -> None:
    """Limpa TODOS os `lru_cache` do backend, sem lista para manter.

    A suite reaponta os caminhos de dado por `monkeypatch` e precisa invalidar as cargas
    lazy. Havia uma lista de nomes copiada em cada arquivo de teste, e as três
    envelheceram de forma diferente: os caches novos da Visão Executiva 2.0 entraram só
    numa delas e vazaram entre arquivos — um teste que passava sozinho falhava na suite
    inteira. Varrer os globais elimina a lista paralela de vez.
    """
    for objeto in list(globals().values()):
        if callable(objeto) and hasattr(objeto, "cache_clear"):
            objeto.cache_clear()


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
            # FRACAO do faturamento bruto de steady da linha de RESULTADO APOS IR da
            # cascata. Servido aqui porque a tela nao faz conta financeira
            # (FIN-VIAB-01) — ela so renderiza. `None` quando o faturamento e zero
            # (cenario degenerado): a tela omite o % em vez de exibir infinito.
            # NAO existe campo irmao para o EBITDA: o percentual dele ja e' `margem`
            # (o motor define `margem_ebitda_pct = ebitda / faturamento`) e servir os
            # dois abria a porta para divergirem em silencio se a definicao mudasse.
            "resultado_apos_ir_pct_faturamento": _pct_do_faturamento(
                r.resultado_apos_ir_mensal, r.faturamento_mensal_steady
            ),
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
# Rotas — Visão Executiva (rede Ultra real, camada PARALELA) — WEB-15, DEC-023
#
# Lê `growth_api_historico.parquet` (ingestão diária da Growth API, DEC-013):
# alunos ativos/recorrentes reais, faturamento, churn, split recorrentes ×
# agregadores. READ-ONLY sobre o M1; camada de rede PARALELA (sem PII — o parquet
# é agregado por unidade/data).
#
# O que era `_FAT_MIN_EXEC = 20000.0` (piso de faturamento) saiu daqui na DEC-023:
# era um literal financeiro não nomeado, que `dimensionamento/config.py` proíbe, e
# foi substituído por um gate SEMÂNTICO em `rede_metricas` — unidade inaugurada
# dentro da competência não é comparável. Medido em jul/2026: o gate semântico
# explica 100% dos casos que o piso pegava, sem derrubar academia da carteira.
# A lista de exclusão virou `rede_metricas.EXCLUIDAS_NOME_CRU`, casada por nome
# CRU (a versão por chave normalizada derrubava a academia AGUAS CLARAS junto com
# o studio AGUAS CLARAS - DF).
# ============================================================================

GROWTH_PARQUET = STAGING_DIR / "growth_api_historico.parquet"

# Siglas de UF que aparecem como SUFIXO do nome da unidade, em três grafias que
# convivem nas bases: "Bangú / RJ", "BANGU - RJ" e "Icaraí RJ". O separador é
# OBRIGATÓRIO no padrão — sem ele, "NATAL" viraria "NAT" (o "AL" de Alagoas) e
# "VISCONDE DE RIO CLARO" viraria "…CLA" (o "RO" de Rondônia).
_UFS_BR = (
    "AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO"
)
_UF_SUFIXO_RE = re.compile(rf"(?:\s*[/-]\s*|\s+)(?:{_UFS_BR})$")


def _chave_unidade(valor: object) -> str:
    """Chave de join de unidade, tolerante às grafias que convivem nas bases.

    Estende `growth_api_client.normalizar_unidade` (que só remove o sufixo " - XX")
    para também remover "/ XX" e " XX". Vive AQUI, e não no `growth_api_client`,
    de propósito: aquela função é compartilhada com o catchment e a consolidação do
    M1, e alargar o join lá mudaria pipelines que não são objeto desta correção.
    """
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c)).upper().strip()
    texto = " ".join(texto.split())
    anterior = None
    while anterior != texto:  # "Sao Pedro da Aldeia / RJ" -> "SAO PEDRO DA ALDEIA"
        anterior = texto
        texto = _UF_SUFIXO_RE.sub("", texto).strip()
    return texto


# Unidades cujo nome COMERCIAL na base Growth não bate com o nome no cadastro, e que
# nenhuma normalização resolve. Cada entrada foi conferida contra o cadastro em
# 2026-08-03: o alvo existe, está livre (nenhuma outra unidade da Growth o reivindica)
# e a `cidade` do cadastro confere. `(chave Growth, UF) -> chave no cadastro`.
_EXEC_ALIAS_COORD: dict[tuple[str, str], str] = {
    ("PATIO BRASIL", "DF"): "PATIO SHOPPING BRASIL",
    # "Vicente Pires / DF" já é consumida pela unidade "VICENTE PIRES - DF" da Growth;
    # a da "Rua 8" é a segunda do bairro, cadastrada como "Vicente Pires 2".
    ("VICENTE PIRES RUA 8", "DF"): "VICENTE PIRES 2",
    ("CESARIO", "MG"): "CESARIO ALVIM",
    ("FLORIANO", "MG"): "FLORIANO PEIXOTO",
    # Única unidade de PE nas duas bases; a av. Domingos Ferreira fica no Pina.
    ("DOMINGOS FERREIRA", "PE"): "RECIFE - PINA",
    ("FLOW", "PR"): "CURITIBA FLOW (UBERABA)",
    ("SAO GONCALO - CENTRO", "RJ"): "SAO GONCALO",
    ("SAO GONCALO SHOPPING", "RJ"): "SHOPPING PARTAGE",
    ("PICARRAS", "SC"): "BALNEARIO PICARRAS",
    ("AMERICANA CENTRO", "SP"): "AMERICANA",
    ("VILLA BRANCA", "SP"): "JACAREI",  # Villa Branca é bairro de Jacareí
    ("VISCONDE DE RIO CLARO", "SP"): "RIO CLARO",
}


@functools.lru_cache(maxsize=1)
def _carregar_growth() -> pd.DataFrame:
    if not GROWTH_PARQUET.exists():
        return pd.DataFrame()
    df = pd.read_parquet(GROWTH_PARQUET)
    df["_data"] = pd.to_datetime(df.get("data"), format="%d/%m/%Y", errors="coerce")
    return df


@functools.lru_cache(maxsize=1)
def _carregar_ultra_mapeadas() -> pd.DataFrame:
    """Cadastro amplo das unidades Ultra (READ-ONLY). Vazio se o parquet faltar."""
    cols = ["nome", "uf", "cidade", "lat", "lng"]
    if not ULTRA_MAPEADAS_PARQUET.exists():
        return pd.DataFrame(columns=cols)
    df = pd.read_parquet(
        ULTRA_MAPEADAS_PARQUET,
        columns=["unidade", "uf", "cidade", "lat", "lng", "flag_coord_valida"],
    ).rename(columns={"unidade": "nome"})
    if "flag_coord_valida" in df.columns:
        df = df[df["flag_coord_valida"].fillna(True).astype(bool)]
    df = df.dropna(subset=["lat", "lng"])
    # Ordem estável: o desempate de chaves repetidas abaixo não pode depender da
    # ordem de gravação do parquet.
    return df[cols].sort_values(["uf", "nome"], kind="stable").reset_index(drop=True)


@functools.lru_cache(maxsize=1)
def _ultra_coord_map() -> tuple[
    dict[str, tuple[float, float]],
    dict[tuple[str, str], tuple[float, float]],
    dict[str, tuple[float, float]],
]:
    """Índices de coordenadas das unidades Ultra, um por fonte e por forma de busca.

    Devolve `(curada, cadastro_por_chave_uf, cadastro_por_chave)`. Ficam SEPARADOS
    porque a precedência é entre FONTES, não entre formas de busca: um acerto por
    (chave, UF) no cadastro não pode ganhar de um acerto por chave na curada — foi
    exatamente assim que `TAUBATE` foi parar na Grande SP na primeira versão desta
    correção. Quem aplica a ordem é `_coord_da_unidade`.

    Chaves repetidas dentro de uma mesma fonte: vence a PRIMEIRA na ordem estável.
    """
    curada: dict[str, tuple[float, float]] = {}
    cad_por_chave_uf: dict[tuple[str, str], tuple[float, float]] = {}
    cad_por_chave: dict[str, tuple[float, float]] = {}

    for t in _carregar_ultra_pontos().itertuples(index=False):
        chave = _chave_unidade(t.nome)
        if chave:
            curada.setdefault(chave, (float(t.lat), float(t.lng)))

    for t in _carregar_ultra_mapeadas().itertuples(index=False):
        chave, uf = _chave_unidade(t.nome), str(t.uf).upper().strip()
        if not chave:
            continue
        ponto = (float(t.lat), float(t.lng))
        if uf:
            cad_por_chave_uf.setdefault((chave, uf), ponto)
        cad_por_chave.setdefault(chave, ponto)

    return curada, cad_por_chave_uf, cad_por_chave


def _coord_da_unidade(nome: str, uf: str) -> tuple[float, float] | None:
    """(lat, lng) de uma unidade da base Growth, ou None se não houver cadastro.

    Ordem de busca, da fonte mais confiável para a mais ampla:

      1. `unidades_ultra_performance_hex.parquet` — base curada (54 unidades), a que o
         piloto já usava. Vem primeiro para que nenhuma unidade hoje no mapa mude de
         lugar: onde o cadastro amplo diverge dela (`TAUBATE` está cadastrado com um
         ponto na Grande SP, `SOBRADINHO` com um ponto fora de Sobradinho), a curada
         é a correta e prevalece.
      2. `unidades_ultra_mapeadas.parquet` por (chave, UF) — completa a rede atual.
      3. o mesmo cadastro só por chave — rede de segurança para UF divergente entre as
         bases (ex.: "Novo Gama / GO" atendendo a unidade que a Growth marca como DF).

    Nomes comerciais que nenhuma normalização reconcilia passam antes por
    `_EXEC_ALIAS_COORD`, que redireciona a busca para a chave do cadastro.
    """
    curada, cad_por_chave_uf, cad_por_chave = _ultra_coord_map()
    uf = str(uf).upper().strip()
    chave = _chave_unidade(nome)
    if not chave:
        return None
    # O alias existe justamente porque a chave crua não casa: ele SUBSTITUI a chave.
    chave = _EXEC_ALIAS_COORD.get((chave, uf), chave)
    return (
        curada.get(chave)
        or cad_por_chave_uf.get((chave, uf))
        or cad_por_chave.get(chave)
    )


def _wavg(valores: pd.Series, pesos: pd.Series) -> float | None:
    """Média ponderada JSON-safe; cai na média simples se não houver pesos."""
    v = pd.to_numeric(valores, errors="coerce")
    w = pd.to_numeric(pesos, errors="coerce")
    m = v.notna() & w.notna() & (w > 0)
    if not bool(m.any()):
        vv = v.dropna()
        return _num(vv.mean(), 2) if len(vv) else None
    return _num(float((v[m] * w[m]).sum() / w[m].sum()), 2)


def _numf(v: Any) -> float | None:
    """float JSON-safe SEM arredondar (NaN/inf -> None)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (math.isnan(f) or math.isinf(f)) else f


# ============================================================================
# Rotas — Visão Executiva 2.0: a rede Ultra como carteira acionável (DEC-023)
#
# A v1 desta aba respondia bem a "onde estão as unidades" e mal a "o que fazer
# com elas". Aqui a base Growth vira dois níveis — carteira priorizada e ficha
# da unidade — sobre o núcleo semântico de `motor_expansao.dashboard.rede_*`.
#
# Todo o cálculo mora em `src/`; este arquivo é adaptador. Isso não é estética:
# `web/**` é classe GOVERNANÇA no `loop_guard` (DEC-022) e cada linha aqui custa
# um gate humano, enquanto `src/` é revisável em bloco.
#
# READ-ONLY sobre o M1. A ÚNICA escrita do backend é o cadastro operacional, num
# diretório próprio fora do `MOTOR_DATA_DIR` (§11 do plano, DEC-023).
# ============================================================================

CADASTRO_DIR = Path(os.environ.get("MOTOR_CADASTRO_DIR", str(_REPO_ROOT / "data" / "cadastro")))

# Métricas servidas com o quarteto de contexto (valor, M-1, ranking, % vs média).
# É a leitura que o time de campo já faz na planilha; a ordem é a da carteira.
#
# A CARTEIRA leva um subconjunto e a FICHA leva tudo. Não é economia gratuita: o
# quarteto custa ~110 bytes por métrica por unidade, e as 19 métricas em 92 linhas
# levavam o payload a 277 KB. Com 12, fica em ~190 KB — e a ficha, que é uma unidade
# só, continua com a lista inteira.
_REDE_METRICAS: tuple[str, ...] = (
    "faturamento",
    "ativos",
    "pagantes",
    "agregadores",
    "receita_por_recorrente",
    "churn_pct",
    "conversao_pct",
    "nps",
    "saldo_operacional",
    "novos_alunos",
    "vendas",
    "cancelados",
    "visitas",
    "em_cobranca_pct",
    "pct_agregador_alunos",
    "faturamento_sem_agregador",
    "faturamento_agregador",
    "inadimplente",
    "treino_ativo",
)

#: O que a carteira serve por unidade (as demais só na ficha e no export da ficha).
_REDE_METRICAS_CARTEIRA: tuple[str, ...] = (
    "faturamento",
    "ativos",
    "pagantes",
    "agregadores",
    "receita_por_recorrente",
    "churn_pct",
    "conversao_pct",
    "nps",
    "saldo_operacional",
    "pct_agregador_alunos",
    "novos_alunos",
    "em_cobranca_pct",
)

# KPIs do topo da tela. Soma para volume, média ponderada para taxa — somar churn
# de 92 unidades daria um número sem significado nenhum.
_REDE_KPIS_SOMA = ("faturamento", "ativos", "pagantes", "agregadores", "saldo_operacional")
_REDE_KPIS_MEDIA = {
    "churn_pct": "pagantes",
    "receita_por_recorrente": "pagantes",
    "nps": "ativos",
    "conversao_pct": "visitas",
}

# Meses oferecidos no seletor de competência.
_REDE_MESES_NO_SELETOR = 24
# Meses da série histórica da ficha e da sparkline da carteira.
_REDE_MESES_SERIE = 12
# Teto de segurança do payload da carteira (o cliente não pagina).
_REDE_MAX_UNIDADES = 400


@functools.lru_cache(maxsize=1)
def _rede_base() -> pd.DataFrame:
    """Base Growth preparada: identidade resolvida e não-academias fora."""
    return rede_metricas.carregar_base(GROWTH_PARQUET)


@functools.lru_cache(maxsize=1)
def _rede_fechamento() -> pd.DataFrame:
    """Fechamento mensal de TODA a série, sem corte de dia (a base do histórico)."""
    return rede_metricas.fechamento_mensal(_rede_base())


@functools.lru_cache(maxsize=1)
def _rede_cadastro() -> Any:
    """Cadastro operacional (consultor, master franquia...). Degrada se não montado."""
    return rede_cadastro.ler_cadastro(CADASTRO_DIR)


def _rede_meses() -> list[str]:
    fech = _rede_fechamento()
    return sorted({str(c) for c in fech["competencia"].unique()}, reverse=True) if len(fech) else []


def _rede_exigir_base() -> pd.DataFrame:
    base = _rede_base()
    if not len(base):
        raise HTTPException(
            404, "Base de rede (growth_api_historico.parquet) ausente no servidor."
        )
    return base


@functools.lru_cache(maxsize=4)
def _rede_mes(mes_sel: str) -> dict[str, Any]:
    """Tudo que a competência `mes_sel` produz, calculado UMA vez.

    Carteira, ficha, CSV, XLSX e PDF leem daqui. É a resposta ao defeito mais caro
    deste projeto: a mesma unidade com dois números em duas superfícies (o
    `test_carteira_e_ficha_concordam` existe para travar isso).
    """
    base = _rede_exigir_base()
    cheio = _rede_fechamento()
    periodo = pd.Period(mes_sel, freq="M")
    anterior = str(periodo - 1)

    no_mes = cheio[cheio["competencia"] == mes_sel]
    if not len(no_mes):
        raise HTTPException(404, f"Sem dados da rede na competência {mes_sel}.")
    referencia = pd.Timestamp(no_mes["dia_ref"].max())
    dia_corte = int(referencia.day)

    # Fechado = a coleta chegou ao fim do mês (a tolerância de um dia cobre a ingestão
    # que perde a virada: julho/2026 termina em 30/07 na base de produção).
    fechado = bool(referencia.day >= periodo.days_in_month - rede_metricas.TOLERANCIA_FIM_DE_MES_DIAS)

    if fechado:
        # Mês inteiro: os números da tela são os do PRÓPRIO mês, iguais aos do gráfico
        # histórico. Aplicar a janela de 30 dias aqui faria o KPI divergir do último
        # ponto da série — em fevereiro, a janela puxaria 3 dias de janeiro e a receita
        # por recorrente sairia ~11% acima do fechamento do mês.
        corte = cheio
        atual = cheio[cheio["competencia"] == mes_sel].copy()
        m1 = cheio[cheio["competencia"] == anterior].copy()
    else:
        # Mês em curso: MTD até o dia de referência dos dois lados (comparação justa) e
        # as razões reconstruídas em ~30 dias, senão elas valem só os dias já corridos.
        corte = rede_metricas.fechamento_mensal(base, dia_corte=dia_corte)
        atual = _rede_janela(corte, cheio, mes_sel)
        m1 = _rede_janela(corte, cheio, anterior)

    contexto = rede_metricas.contexto_comparativo(atual)
    contexto = rede_coorte.anotar_coortes(contexto)

    # O diagnóstico NUNCA roda sobre mês aberto: no dia 2, o acumulado de dois dias
    # acenderia queda de faturamento na rede inteira. A tela diz de que mês ele vem.
    competencia_diagnostico = rede_diagnostico.competencia_base(cheio, mes_sel)
    diagnosticos = (
        rede_diagnostico.diagnosticar(cheio, competencia_diagnostico)
        if competencia_diagnostico
        else {}
    )

    return {
        "mes": mes_sel,
        "mes_anterior": anterior,
        "referencia": referencia,
        "dia_corte": dia_corte,
        "mes_completo": fechado,
        "competencia_diagnostico": competencia_diagnostico,
        "atual": contexto,
        "m1": m1.set_index("unidade_id"),
        "cheio": cheio,
        "diagnosticos": diagnosticos,
        "sss": _rede_sss(corte, mes_sel),
        "serie_meses": _rede_serie_meses(cheio, mes_sel),
    }


def _rede_serie_meses(cheio: pd.DataFrame, mes_sel: str) -> list[str]:
    """Competências FECHADAS que alimentam a sparkline e o gráfico da rede.

    Vai no payload porque o cliente NÃO consegue derivá-las: quando a competência
    escolhida está aberta, a série termina no mês anterior, e uma contagem regressiva a
    partir de `mes` no frontend rotulava cada barra com o mês seguinte — o gráfico
    inteiro saía deslocado em um mês.
    """
    fechados = cheio[
        cheio["mes_completo"].fillna(False).astype(bool) & (cheio["competencia"] <= mes_sel)
    ]
    if not len(fechados):
        return []
    meses = sorted({str(c) for c in fechados["competencia"].unique()})
    return meses[-_REDE_MESES_SERIE:]


def _rede_janela(corte: pd.DataFrame, cheio: pd.DataFrame, competencia: str) -> pd.DataFrame:
    """Fechamento da competência com as RAZÕES corrigidas para a janela de 30 dias.

    Cumulativas e snapshots já saem certos do fechamento com corte de dia (o mesmo
    dia-do-mês dos dois lados da comparação). As duas razões abaixo, não: no dia 2
    do mês, `faturamento_sem_agregador / pagantes` vale dois dias de receita sobre
    a base inteira — é o R$ 20,28 que a v1 exibia contra R$ 163,67 reais.

    Reconstrói-se então a janela de ~30 dias sobre a cumulativa que reseta no dia 1.
    Em mês fechado a janela coincide com o próprio mês, e o número não muda.
    """
    linhas = corte[corte["competencia"] == competencia].copy()
    if not len(linhas):
        return linhas
    indexado = linhas.set_index("unidade_id")

    receita = rede_metricas.receita_por_recorrente_30d(corte, cheio, competencia)
    indexado["receita_por_recorrente"] = receita.reindex(indexado.index)

    cancelados = rede_metricas.rolling30(corte, cheio, competencia, "cancelados")
    # Denominador = recorrentes com que a janela COMEÇOU (a base do mês anterior no
    # mesmo dia-do-mês), como o `CHURN_DIA = [CANCELADOS_DIA] / [REC_MES_ANTERIOR]`.
    periodo = pd.Period(competencia, freq="M")
    base_anterior = corte[corte["competencia"] == str(periodo - 1)].set_index("unidade_id")
    pagantes_inicio = pd.to_numeric(base_anterior.get("pagantes"), errors="coerce")
    if pagantes_inicio is None:
        pagantes_inicio = pd.Series(dtype="float64")
    pagantes_inicio = pagantes_inicio.reindex(indexado.index)
    indexado["churn_pct"] = 100.0 * cancelados.reindex(indexado.index) / pagantes_inicio.where(
        pagantes_inicio.ne(0)
    )
    return indexado.reset_index()


def _rede_sss(corte: pd.DataFrame, mes_sel: str) -> dict[str, Any]:
    """Same Store Sales: ano contra ano em BASE COMPARÁVEL.

    A rede abriu 33 unidades em 2025; comparar total contra total mede abertura de
    loja, não desempenho. Entram só as unidades presentes nos DOIS períodos e que
    operaram o mês inteiro nos dois — a definição de "mesma loja".
    """
    ano_anterior = str(pd.Period(mes_sel, freq="M") - 12)
    agora = corte[(corte["competencia"] == mes_sel) & corte["operacao_mes_cheio"]]
    antes = corte[(corte["competencia"] == ano_anterior) & corte["operacao_mes_cheio"]]
    comuns = sorted(set(agora["unidade_id"]) & set(antes["unidade_id"]))
    if not comuns:
        return {"disponivel": False, "competencia_base": ano_anterior, "unidades": 0}

    agora = agora[agora["unidade_id"].isin(comuns)]
    antes = antes[antes["unidade_id"].isin(comuns)]
    metricas: dict[str, Any] = {}
    for chave in ("faturamento", "faturamento_sem_agregador", "agregadores", "ativos", "pagantes"):
        atual = _numf(pd.to_numeric(agora[chave], errors="coerce").sum())
        passado = _numf(pd.to_numeric(antes[chave], errors="coerce").sum())
        metricas[chave] = {
            "atual": _num(atual),
            "ano_anterior": _num(passado),
            "var_pct": _num(100.0 * (atual - passado) / passado, 1) if passado else None,
        }
    return {
        "disponivel": True,
        "competencia_base": ano_anterior,
        "unidades": len(comuns),
        "metricas": metricas,
    }


def _rede_casas(chave: str) -> int:
    """Casas decimais de uma métrica. UMA definição, usada no quarteto E na série.

    Sem isso, o mesmo churn saía 3,3 no KPI e 3,33 no gráfico logo abaixo — divergência
    de arredondamento que parece divergência de cálculo e manda o operador procurar bug
    onde não há.
    """
    if chave == "receita_por_recorrente":
        return 2
    if chave.endswith("_pct") or chave == "nps":
        return 1
    return 0


def _rede_quarteto(linha: pd.Series, m1: pd.Series | None, chave: str) -> dict[str, Any]:
    """`MÊS | M-1 | Ranking N/total | % vs Média Rede` para uma métrica.

    Eles nunca olham um número sozinho: leem "estou 64% abaixo da média da rede e
    sou 79º de 89". Esse trio de contexto É o semáforo deles, e diz mais que um
    chip colorido porque informa o tamanho e a posição do problema.
    """
    casas = _rede_casas(chave)
    atual = _numf(linha.get(chave))
    anterior = _numf(m1.get(chave)) if m1 is not None else None
    rank = _numf(linha.get(f"rank_{chave}"))
    total = _numf(linha.get(f"rank_total_{chave}"))
    delta = (
        100.0 * (atual - anterior) / anterior
        if (atual is not None and anterior not in (None, 0))
        else None
    )
    return {
        "atual": _num(atual, casas),
        "m1": _num(anterior, casas),
        "delta_pct": _num(delta, 1),
        "rank": int(rank) if rank else None,
        "rank_total": int(total) if total else None,
        "vs_media_pct": _num(_numf(linha.get(f"vs_media_{chave}")), 1),
    }


def _rede_serie(cheio: pd.DataFrame, unidade_id: str, ate: str, meses: int) -> pd.DataFrame:
    """Últimas `meses` competências FECHADAS da unidade, em ordem cronológica."""
    serie = cheio[
        (cheio["unidade_id"] == unidade_id)
        & (cheio["competencia"] <= ate)
        & cheio["mes_completo"].fillna(False).astype(bool)
    ]
    return serie.sort_values("competencia", kind="stable").tail(meses)


def _rede_unidade_dict(
    linha: pd.Series,
    m1: pd.DataFrame,
    diagnosticos: dict[str, Any],
    cadastro: Any,
    cheio: pd.DataFrame,
    mes_sel: str,
    *,
    com_serie: bool = True,
    metricas: tuple[str, ...] = _REDE_METRICAS_CARTEIRA,
) -> dict[str, Any]:
    """Uma linha da carteira: identidade, cadastro, quarteto, diagnóstico e sparkline."""
    unidade_id = str(linha["unidade_id"])
    registro = cadastro.de(unidade_id)
    anterior = m1.loc[unidade_id] if unidade_id in m1.index else None
    diagnostico = diagnosticos.get(unidade_id)
    coordenada = _coord_da_unidade(str(linha.get("unidade_cru", "")), str(linha.get("uf", "")))
    inauguracao = linha.get("inauguracao")

    serie: list[float | None] = []
    if com_serie:
        historico = _rede_serie(cheio, unidade_id, mes_sel, _REDE_MESES_SERIE)
        serie = [_num(v) for v in pd.to_numeric(historico["faturamento"], errors="coerce")]

    return {
        "id": unidade_id,
        "nome": str(linha.get("unidade_cru", "")).strip(),
        "uf": str(linha.get("uf", "")),
        "master": str(linha.get("master", "")),
        "cidade": registro.get("cidade") or None,
        "consultor": registro.get("consultor") or None,
        "consultor_2": registro.get("consultor_2") or None,
        "master_franquia": registro.get("master_franquia") or None,
        "franqueado": registro.get("franqueado") or None,
        "coorte": str(linha.get("coorte", rede_coorte.COORTE_INDEFINIDA)),
        "coorte_rotulo": str(linha.get("coorte_rotulo", "")),
        "meses_operacao": _num(_numf(linha.get("meses_operacao"))),
        "inauguracao": (
            pd.Timestamp(inauguracao).strftime("%d/%m/%Y") if pd.notna(inauguracao) else None
        ),
        "lat": _num(coordenada[0], 6) if coordenada else None,
        "lng": _num(coordenada[1], 6) if coordenada else None,
        "comparavel": bool(linha.get("operacao_mes_cheio", True)),
        "severidade": diagnostico.severidade if diagnostico else "sem_base",
        "severidade_rotulo": (
            rede_diagnostico.ROTULO_SEVERIDADE[diagnostico.severidade]
            if diagnostico
            else rede_diagnostico.ROTULO_SEVERIDADE["sem_base"]
        ),
        "prioridade": _num(diagnostico.prioridade, 3) if diagnostico else 0.0,
        "resumo": diagnostico.resumo if diagnostico else "",
        "faixa_faturamento": diagnostico.faixa_faturamento if diagnostico else "sem_dado",
        "faixa_faturamento_rotulo": (
            diagnostico.faixa_faturamento_rotulo if diagnostico else "Sem dado"
        ),
        "alertas": [
            {"codigo": a.codigo, "titulo": a.titulo, "detalhe": a.detalhe, "nivel": a.nivel}
            for a in (diagnostico.alertas if diagnostico else ())
        ],
        "metricas": {c: _rede_quarteto(linha, anterior, c) for c in metricas},
        "sparkline": serie,
    }


def _rede_kpis(unidades: pd.DataFrame, m1: pd.DataFrame) -> dict[str, Any]:
    """KPIs do recorte. `atual` = todos; `m1`/delta na cesta com M-1 (comparável)."""
    if not len(unidades):
        return {c: {"atual": None, "m1": None, "delta_pct": None} for c in _REDE_KPIS_SOMA}
    indexado = unidades.set_index("unidade_id")
    comuns = indexado.index.intersection(m1.index)
    saida: dict[str, Any] = {}

    for chave in _REDE_KPIS_SOMA:
        atual = _numf(pd.to_numeric(indexado[chave], errors="coerce").sum())
        anterior = _numf(pd.to_numeric(m1.loc[comuns, chave], errors="coerce").sum()) if len(comuns) else None
        atual_cesta = _numf(pd.to_numeric(indexado.loc[comuns, chave], errors="coerce").sum()) if len(comuns) else None
        delta = (
            100.0 * (atual_cesta - anterior) / anterior
            if (anterior and atual_cesta is not None)
            else None
        )
        saida[chave] = {"atual": _num(atual), "m1": _num(anterior), "delta_pct": _num(delta, 1)}

    for chave, peso in _REDE_KPIS_MEDIA.items():
        atual = _wavg(indexado[chave], indexado[peso])
        # O delta sai da MESMA cesta dos dois lados. Comparar a média de hoje (com as
        # unidades novas dentro) contra a de M-1 (sem elas) mostrava o NPS da rede
        # despencando num mês de inauguração sem que nada tivesse caído: mudou a cesta,
        # não o desempenho. `atual` segue sendo o número do recorte inteiro.
        anterior = _wavg(m1.loc[comuns, chave], m1.loc[comuns, peso]) if len(comuns) else None
        atual_cesta = _wavg(indexado.loc[comuns, chave], indexado.loc[comuns, peso]) if len(comuns) else None
        delta = (
            100.0 * (atual_cesta - anterior) / anterior
            if (atual_cesta is not None and anterior)
            else None
        )
        saida[chave] = {"atual": _num(atual, 2), "m1": _num(anterior, 2), "delta_pct": _num(delta, 1)}
    return saida


def _rede_notas(contexto: dict[str, Any], recorte: pd.DataFrame) -> list[str]:
    """Notas de método. Toda degradação é DITA, nunca silenciosa."""
    notas = [
        "Receita por recorrente = faturamento sem agregador dos últimos 30 dias "
        "dividido pelos recorrentes ativos. NÃO é o TICKET_MEDIO do PowerBI, que vem "
        "da venda individual (tabela que a API Growth não expõe).",
        "O faturamento não bate com a planilha do time: lá o TEM SAÚDE é deduzido "
        "(cerca de 0,7%).",
    ]
    if contexto["competencia_diagnostico"] and contexto["competencia_diagnostico"] != contexto["mes"]:
        notas.append(
            f"Diagnóstico e alertas calculados sobre {contexto['competencia_diagnostico']}, "
            "o último mês fechado: mês em curso não acende alerta."
        )
    if len(recorte):
        novas = int((~recorte["operacao_mes_cheio"].fillna(True).astype(bool)).sum())
        if novas:
            notas.append(
                f"{novas} unidade(s) inauguradas dentro do período: aparecem na carteira, "
                "mas ficam fora do ranking, da média da rede e do diagnóstico."
            )
        sem_nps = int((~recorte["nps_valido"].fillna(False).astype(bool)).sum())
        if sem_nps:
            notas.append(f"{sem_nps} unidade(s) sem pesquisa de NPS no período.")
    notas.append(
        "Inadimplentes e treino ativo são exibidos sem régua: o denominador ainda não "
        "foi confirmado com a Growth."
    )
    return notas


def _rede_filtrar(contexto: dict[str, Any], filtros: dict[str, str | None]) -> pd.DataFrame:
    """Aplica os filtros da tela. A média da rede e o ranking já foram calculados ANTES.

    A ordem importa: se o ranking fosse calculado depois do filtro, a mesma unidade
    mudaria de posição ao mexer num filtro — é exatamente o defeito do semáforo
    relativo que o HTML do time tem hoje.
    """
    dados = contexto["atual"]
    cadastro = _rede_cadastro()
    diagnosticos = contexto["diagnosticos"]

    if filtros.get("uf"):
        dados = dados[dados["uf"].astype(str).str.upper() == str(filtros["uf"]).upper()]
    if filtros.get("master"):
        dados = dados[dados["master"].astype(str) == filtros["master"]]
    if filtros.get("coorte"):
        dados = dados[dados["coorte"].astype(str) == filtros["coorte"]]
    if filtros.get("consultor"):
        alvo = str(filtros["consultor"])
        ids = {
            uid
            for uid, registro in cadastro.unidades.items()
            if str(registro.get("consultor") or "") == alvo
        }
        dados = dados[dados["unidade_id"].isin(ids)]
    if filtros.get("severidade"):
        alvos = {s.strip() for s in str(filtros["severidade"]).split(",") if s.strip()}
        dados = dados[
            dados["unidade_id"].map(
                lambda uid: (diagnosticos[uid].severidade if uid in diagnosticos else "sem_base")
                in alvos
            )
        ]
    if filtros.get("busca"):
        alvo = _chave_unidade(filtros["busca"])
        if alvo:
            dados = dados[dados["unidade_cru"].map(lambda n: alvo in _chave_unidade(n))]
    return dados


@app.get("/api/rede/filtros")
def rede_filtros(mes: str | None = None) -> dict[str, Any]:
    """Vocabulário dos filtros, réguas vigentes e contadores de qualidade.

    As réguas são SERVIDAS, não repetidas no cliente: é impossível a tela mostrar
    uma régua e o motor aplicar outra.
    """
    _rede_exigir_base()
    meses = _rede_meses()
    if not meses:
        raise HTTPException(404, "Base de rede sem competências com dado.")
    contexto = _rede_mes(mes if mes in meses else meses[0])
    atual = contexto["atual"]
    cadastro = _rede_cadastro()

    com_coordenada = sum(
        1
        for linha in atual.itertuples()
        if _coord_da_unidade(str(linha.unidade_cru), str(linha.uf)) is not None
    )
    return {
        "meses": meses[:_REDE_MESES_NO_SELETOR],
        "mes_padrao": meses[0],
        "ufs": sorted({str(u) for u in atual["uf"].dropna().unique()}),
        "masters": sorted({str(m) for m in atual["master"].dropna().unique() if str(m).strip()}),
        "consultores": rede_cadastro.valores_distintos(cadastro, "consultor"),
        "masters_franquia": rede_cadastro.valores_distintos(cadastro, "master_franquia"),
        "coortes": rede_coorte.resumo_coortes(atual),
        "severidades": [
            {"chave": s, "rotulo": rede_diagnostico.ROTULO_SEVERIDADE[s]}
            for s in rede_diagnostico.SEVERIDADES
        ],
        "metricas": [
            {
                "chave": m.chave,
                "rotulo": m.rotulo,
                "direcao": m.direcao,
                "bom_subindo": m.bom_subindo,
                "formato": m.formato,
            }
            for m in rede_metricas.METRICAS
            if m.chave in _REDE_METRICAS
        ],
        "reguas": rede_diagnostico.REGUAS_VIGENTES,
        "meta_nps": rede_diagnostico.META_NPS,
        "medios_para_alta": rede_diagnostico.MEDIOS_PARA_ALTA,
        "faixas_faturamento": [
            {"ate": None if teto == float("inf") else teto, "chave": chave, "rotulo": rotulo}
            for teto, chave, rotulo in rede_diagnostico.FAIXAS_FATURAMENTO
        ],
        "metricas_a_validar": sorted(rede_diagnostico.metricas_proibidas_em_alerta()),
        "qualidade": {
            "unidades": int(len(atual)),
            "com_coordenada": com_coordenada,
            "com_consultor": sum(
                1
                for uid in atual["unidade_id"]
                if str(cadastro.de(str(uid)).get("consultor") or "").strip()
            ),
            "sem_nps": int((~atual["nps_valido"].fillna(False).astype(bool)).sum()),
        },
        "cadastro": {
            "disponivel": bool(cadastro.disponivel),
            "versao": int(cadastro.versao),
            "campos_editaveis": list(rede_cadastro.CAMPOS_EDITAVEIS),
        },
        "referencia": pd.Timestamp(contexto["referencia"]).strftime("%d/%m/%Y"),
        "fonte": "Growth API",
    }


def _rede_carteira_payload(
    mes: str | None = None,
    uf: str | None = None,
    master: str | None = None,
    consultor: str | None = None,
    coorte: str | None = None,
    severidade: str | None = None,
    busca: str | None = None,
    ordenar: str = "prioridade",
    direcao: str = "desc",
) -> dict[str, Any]:
    """Payload da carteira. Uma função só, para que tela, CSV, XLSX e PDF nunca divirjam."""
    meses = _rede_meses()
    if not meses:
        _rede_exigir_base()
        raise HTTPException(404, "Base de rede sem competências com dado.")
    mes_sel = mes if (mes in meses) else meses[0]
    contexto = _rede_mes(mes_sel)

    recorte = _rede_filtrar(
        contexto,
        {
            "uf": uf,
            "master": master,
            "consultor": consultor,
            "coorte": coorte,
            "severidade": severidade,
            "busca": busca,
        },
    )
    cadastro = _rede_cadastro()
    unidades = [
        _rede_unidade_dict(
            linha,
            contexto["m1"],
            contexto["diagnosticos"],
            cadastro,
            contexto["cheio"],
            mes_sel,
        )
        for _, linha in recorte.iterrows()
    ][:_REDE_MAX_UNIDADES]
    unidades = _rede_ordenar(unidades, ordenar, direcao)

    com_coordenada = [u for u in unidades if u["lat"] is not None]
    semaforo = {s: 0 for s in rede_diagnostico.SEVERIDADES}
    for unidade in unidades:
        semaforo[unidade["severidade"]] = semaforo.get(unidade["severidade"], 0) + 1

    total_pagantes = float(pd.to_numeric(recorte["pagantes"], errors="coerce").fillna(0).sum())
    total_agregadores = float(pd.to_numeric(recorte["agregadores"], errors="coerce").fillna(0).sum())
    base_split = total_pagantes + total_agregadores
    referencia = pd.Timestamp(contexto["referencia"])
    dia_m1 = pd.Period(contexto["mes_anterior"], freq="M")

    return {
        "mes": mes_sel,
        "meses": meses[:_REDE_MESES_NO_SELETOR],
        "referencia": referencia.strftime("%d/%m/%Y"),
        "referencia_m1": (
            f"{min(contexto['dia_corte'], dia_m1.days_in_month):02d}/"
            f"{dia_m1.month:02d}/{dia_m1.year}"
        ),
        "mes_completo": bool(contexto["mes_completo"]),
        "competencia_diagnostico": contexto["competencia_diagnostico"],
        "totais": {
            "rede": int(len(contexto["atual"])),
            "no_recorte": len(unidades),
            "com_coordenada": len(com_coordenada),
        },
        "kpis": _rede_kpis(recorte, contexto["m1"]),
        "split": {
            "recorrentes": _num(total_pagantes),
            "agregadores": _num(total_agregadores),
            "pct_recorrentes": _num(100 * total_pagantes / base_split, 1) if base_split else None,
            "pct_agregadores": _num(100 * total_agregadores / base_split, 1) if base_split else None,
        },
        "semaforo": semaforo,
        "sss": contexto["sss"],
        "centro": {
            "lat": _num(sum(u["lat"] for u in com_coordenada) / len(com_coordenada), 6)
            if com_coordenada
            else None,
            "lng": _num(sum(u["lng"] for u in com_coordenada) / len(com_coordenada), 6)
            if com_coordenada
            else None,
        },
        "bbox": (
            {
                "min_lat": _num(min(u["lat"] for u in com_coordenada), 6),
                "min_lng": _num(min(u["lng"] for u in com_coordenada), 6),
                "max_lat": _num(max(u["lat"] for u in com_coordenada), 6),
                "max_lng": _num(max(u["lng"] for u in com_coordenada), 6),
            }
            if com_coordenada
            else None
        ),
        "ultra_icon": _icone_ultra() if com_coordenada else None,
        "reguas": rede_diagnostico.REGUAS_VIGENTES,
        "meta_nps": rede_diagnostico.META_NPS,
        # Rótulos das barras da sparkline e do gráfico agregado. Alinhados à DIREITA:
        # a série de uma unidade nova é mais curta, e os meses anteriores à inauguração
        # dela simplesmente não existem.
        "serie_meses": contexto["serie_meses"],
        "unidades": unidades,
        "notas": _rede_notas(contexto, recorte),
    }


def _rede_ordenar(
    unidades: list[dict[str, Any]], ordenar: str, direcao: str
) -> list[dict[str, Any]]:
    """Ordena a carteira. Nulos SEMPRE por último, nas duas direções.

    O `?? -Infinity` da v1 só funcionava em `desc`: em `asc`, quem não tinha o
    número subia para o topo da lista de trabalho.
    """
    sinal = 1.0 if direcao == "asc" else -1.0

    def chave(unidade: dict[str, Any]) -> tuple[int, float, str]:
        if ordenar == "prioridade":
            valor = unidade.get("prioridade")
        elif ordenar == "nome":
            valor = None
        else:
            valor = (unidade.get("metricas", {}).get(ordenar) or {}).get("atual")
        nome = str(unidade.get("nome", ""))
        # SEMPRE crescente, com o sinal embutido no número: `reverse=True` inverteria
        # também o desempate por nome, e as mesmas duas unidades empatadas sairiam em
        # ordem diferente na tela e no CSV. O marcador de ausência vem primeiro, então
        # nulo fica no fim nas duas direções — o `?? -Infinity` da v1 só funcionava em
        # `desc`, e em `asc` o dado ausente subia para o topo da lista de trabalho.
        return (1 if valor is None else 0, sinal * float(valor or 0.0), nome)

    if ordenar == "nome":
        return sorted(unidades, key=lambda u: str(u.get("nome", "")), reverse=direcao != "asc")
    return sorted(unidades, key=chave)


@app.get("/api/rede/carteira")
def rede_carteira(
    mes: str | None = None,
    uf: str | None = None,
    master: str | None = None,
    consultor: str | None = None,
    coorte: str | None = None,
    severidade: str | None = None,
    busca: str | None = None,
    ordenar: str = "prioridade",
    direcao: str = "desc",
) -> dict[str, Any]:
    """Nível 1: a carteira da rede, priorizada, com o quarteto de contexto por métrica."""
    return _rede_carteira_payload(
        mes, uf, master, consultor, coorte, severidade, busca, ordenar, direcao
    )


def _rede_ficha_payload(unidade_id: str, mes: str | None = None) -> dict[str, Any]:
    """Payload da ficha. Lê do MESMO `_rede_mes` que a carteira."""
    meses = _rede_meses()
    if not meses:
        _rede_exigir_base()
        raise HTTPException(404, "Base de rede sem competências com dado.")
    mes_sel = mes if (mes in meses) else meses[0]
    contexto = _rede_mes(mes_sel)
    atual = contexto["atual"]

    linhas = atual[atual["unidade_id"] == unidade_id]
    if not len(linhas):
        raise HTTPException(404, f"Unidade {unidade_id} sem dados na competência {mes_sel}.")
    linha = linhas.iloc[0]
    cadastro = _rede_cadastro()
    registro = cadastro.de(unidade_id)

    base_unidade = _rede_unidade_dict(
        linha,
        contexto["m1"],
        contexto["diagnosticos"],
        cadastro,
        contexto["cheio"],
        mes_sel,
        com_serie=False,
        metricas=_REDE_METRICAS,
    )
    diagnostico = contexto["diagnosticos"].get(unidade_id)

    historico = _rede_serie(contexto["cheio"], unidade_id, mes_sel, _REDE_MESES_SERIE)
    # Formato COLUNAR: 0,9 KB contra 2,2 KB do array de objetos, para o mesmo dado.
    serie = {"meses": [str(c) for c in historico["competencia"]]}
    for chave in (
        "faturamento",
        "faturamento_sem_agregador",
        "faturamento_agregador",
        "ativos",
        "pagantes",
        "agregadores",
        "churn_pct",
        "nps",
        "receita_por_recorrente",
        "saldo_operacional",
        "conversao_pct",
    ):
        serie[chave] = [
            _num(v, _rede_casas(chave))
            for v in pd.to_numeric(historico[chave], errors="coerce")
        ]

    diaria = _rede_serie_diaria(unidade_id, mes_sel)
    comparacao = rede_coorte.comparar(atual, unidade_id, list(_REDE_METRICAS))
    coorte_payload = {
        "chave": comparacao.coorte,
        "rotulo": comparacao.coorte_rotulo,
        "degradacao": comparacao.degradacao,
        "base_rotulo": comparacao.base_rotulo,
        "n": comparacao.n,
        "metricas": {
            chave: {
                "unidade": base_unidade["metricas"].get(chave, {}).get("atual"),
                "p25": _num(referencia.p25, 2),
                "p50": _num(referencia.p50, 2),
                "p75": _num(referencia.p75, 2),
                "percentil": _num(comparacao.percentis.get(chave), 0),
            }
            for chave, referencia in comparacao.referencias.items()
        },
    }

    visitas = _numf(linha.get("visitas")) or 0.0
    convertidos = _numf(linha.get("convertidos")) or 0.0
    vendas = _numf(linha.get("vendas")) or 0.0
    return {
        "unidade": {
            **{
                c: base_unidade[c]
                for c in (
                    "id", "nome", "uf", "master", "cidade", "consultor", "consultor_2",
                    "master_franquia", "franqueado", "coorte", "coorte_rotulo",
                    "meses_operacao", "inauguracao", "lat", "lng", "comparavel",
                )
            },
            "dpto": registro.get("dpto") or None,
            "cod_unidade": registro.get("cod_unidade") or None,
            "gold": registro.get("gold"),
            "life_time": registro.get("life_time"),
            "ltv": registro.get("ltv"),
            "wellhub": registro.get("wellhub") or None,
            "totalpass": registro.get("totalpass") or None,
            "modalidades": registro.get("modalidades") or {},
        },
        "mes": mes_sel,
        "meses": meses[:_REDE_MESES_NO_SELETOR],
        "referencia": pd.Timestamp(contexto["referencia"]).strftime("%d/%m/%Y"),
        "competencia_diagnostico": contexto["competencia_diagnostico"],
        "metricas": base_unidade["metricas"],
        "serie": serie,
        "serie_diaria": diaria,
        "funil": {
            "visitas": _num(visitas),
            "convertidos": _num(convertidos),
            "vendas": _num(vendas),
            "novos_alunos": _num(_numf(linha.get("novos_alunos"))),
            "conversao_pct": _num(_numf(linha.get("conversao_pct")), 1),
            # NUNCA clampar em 100%: `vendas > convertidos` em 75% das linhas da base.
            # Clampar esconderia um problema de coleta em vez de mostrá-lo.
            "aviso": (
                "Há venda sem visita registrada no período: o funil não fecha."
                if vendas > convertidos
                else None
            ),
        },
        "coorte": coorte_payload,
        "diagnostico": {
            "competencia": diagnostico.competencia if diagnostico else None,
            "severidade": base_unidade["severidade"],
            "severidade_rotulo": base_unidade["severidade_rotulo"],
            "prioridade": base_unidade["prioridade"],
            "resumo": base_unidade["resumo"],
            "alertas": base_unidade["alertas"],
            "recomendacoes": [
                {"codigo": r.codigo, "titulo": r.titulo, "corpo": r.corpo}
                for r in (diagnostico.recomendacoes if diagnostico else ())
            ],
        },
        "cadastro": {
            "disponivel": bool(cadastro.disponivel),
            "versao": int(cadastro.versao),
            "campos_editaveis": list(rede_cadastro.CAMPOS_EDITAVEIS),
            "valores": {c: registro.get(c) or "" for c in rede_cadastro.CAMPOS_EDITAVEIS},
        },
        "reguas": rede_diagnostico.REGUAS_VIGENTES,
        "meta_nps": rede_diagnostico.META_NPS,
        "notas": _rede_notas(contexto, linhas),
    }


def _rede_serie_diaria(unidade_id: str, mes_sel: str) -> dict[str, Any]:
    """Série DIÁRIA des-acumulada do mês — o bloco de 31 colunas que hoje é colado à mão."""
    base = _rede_base()
    saida: dict[str, Any] = {"datas": []}
    for chave in ("novos_alunos", "vendas", "cancelados"):
        serie = rede_metricas.serie_diaria(base, unidade_id, chave)
        if not len(serie):
            saida[chave] = []
            continue
        no_mes = serie[serie["data"].dt.to_period("M").astype(str) == mes_sel]
        if not saida["datas"]:
            saida["datas"] = [d.strftime("%d/%m") for d in no_mes["data"]]
        saida[chave] = [_num(v) for v in pd.to_numeric(no_mes["valor"], errors="coerce")]
    return saida


# A rota do PDF vem ANTES da rota JSON de propósito. `{unidade_id}` casa qualquer coisa,
# inclusive "botafogo-rj.pdf": declarada depois, a rota do PDF nunca era alcançada — o
# pedido caía na rota JSON, que não achava a unidade e devolvia 404. O PDF da ficha não
# saía para unidade nenhuma. O Starlette resolve por ORDEM DE DECLARAÇÃO, não por
# especificidade.
@app.get("/api/rede/unidade/{unidade_id}.pdf")
def rede_unidade_pdf(unidade_id: str, mes: str | None = None) -> Response:
    from motor_expansao.dashboard import rede_export

    payload = _rede_ficha_payload(unidade_id, mes)
    return _anexo(
        rede_export.ficha_pdf(payload),
        f"ficha_{unidade_id}_{str(payload.get('mes', '')).replace('-', '')}.pdf",
        "application/pdf",
    )


@app.get("/api/rede/unidade/{unidade_id}")
def rede_unidade(unidade_id: str, mes: str | None = None) -> dict[str, Any]:
    """Nível 2: a ficha da unidade — série de 12 meses, funil, coorte e recomendações."""
    return _rede_ficha_payload(unidade_id, mes)


# --- Exports ----------------------------------------------------------------


def _rede_nome_arquivo(prefixo: str, payload: dict[str, Any], extensao: str) -> str:
    return f"{prefixo}_{str(payload.get('mes', '')).replace('-', '')}.{extensao}"


def _anexo(conteudo: bytes, nome: str, media_type: str) -> Response:
    return Response(
        content=conteudo,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@app.get("/api/rede/carteira.csv")
def rede_carteira_csv(
    mes: str | None = None,
    uf: str | None = None,
    master: str | None = None,
    consultor: str | None = None,
    coorte: str | None = None,
    severidade: str | None = None,
    busca: str | None = None,
    ordenar: str = "prioridade",
    direcao: str = "desc",
) -> Response:
    from motor_expansao.dashboard import rede_export

    payload = _rede_carteira_payload(
        mes, uf, master, consultor, coorte, severidade, busca, ordenar, direcao
    )
    return _anexo(
        rede_export.carteira_csv(payload),
        _rede_nome_arquivo("carteira_rede_ultra", payload, "csv"),
        "text/csv; charset=utf-8",
    )


@app.get("/api/rede/carteira.xlsx")
def rede_carteira_xlsx(
    mes: str | None = None,
    uf: str | None = None,
    master: str | None = None,
    consultor: str | None = None,
    coorte: str | None = None,
    severidade: str | None = None,
    busca: str | None = None,
    ordenar: str = "prioridade",
    direcao: str = "desc",
) -> Response:
    from motor_expansao.dashboard import rede_export

    payload = _rede_carteira_payload(
        mes, uf, master, consultor, coorte, severidade, busca, ordenar, direcao
    )
    return _anexo(
        rede_export.carteira_xlsx(payload),
        _rede_nome_arquivo("carteira_rede_ultra", payload, "xlsx"),
        XLSX_MEDIA_TYPE,
    )


@app.get("/api/rede/carteira.pdf")
def rede_carteira_pdf(
    mes: str | None = None,
    uf: str | None = None,
    master: str | None = None,
    consultor: str | None = None,
    coorte: str | None = None,
    severidade: str | None = None,
    busca: str | None = None,
    ordenar: str = "prioridade",
    direcao: str = "desc",
) -> Response:
    from motor_expansao.dashboard import rede_export

    payload = _rede_carteira_payload(
        mes, uf, master, consultor, coorte, severidade, busca, ordenar, direcao
    )
    return _anexo(
        rede_export.carteira_pdf(payload),
        _rede_nome_arquivo("carteira_rede_ultra", payload, "pdf"),
        "application/pdf",
    )


# --- Cadastro (a ÚNICA escrita do backend) ----------------------------------


def _autor(*valores: Any) -> str | None:
    """Primeiro header nao vazio, ou None.

    Aceita ser chamada com a rota INVOCADA DIRETO (como faz a suite do piloto, sem
    TestClient): ali o default do `Header(...)` chega como o proprio objeto `Header`, e
    nao como `None`. Filtrar por `isinstance(str)` cobre os dois caminhos sem inventar um
    autor de mentira no log de auditoria.
    """
    for valor in valores:
        if isinstance(valor, str) and valor.strip():
            return valor.strip()
    return None


class CadastroIn(BaseModel):
    """Edição de cadastro. `versao` implementa a concorrência otimista."""

    versao: int | None = None
    campos: dict[str, str] = Field(default_factory=dict)


@app.put("/api/rede/cadastro/{unidade_id}")
def rede_cadastro_atribuir(
    unidade_id: str,
    body: CadastroIn,
    remote_user: str | None = Header(default=None, alias="Remote-User"),
    remote_email: str | None = Header(default=None, alias="Remote-Email"),
) -> dict[str, Any]:
    """Atribui consultor / master franqueado a uma unidade.

    Única rota de escrita do piloto. Grava num diretório PRÓPRIO, fora do
    `MOTOR_DATA_DIR` — nenhum artefato do M1 fica sob mount de escrita. O autor sai
    do `Remote-User`, que o Caddy já repassa ao piloto atrás do Authelia.
    """
    try:
        cadastro = rede_cadastro.atribuir(
            unidade_id,
            dict(body.campos),
            autor=_autor(remote_user, remote_email),
            versao_cliente=body.versao,
            base=CADASTRO_DIR,
        )
    except rede_cadastro.ConflitoDeVersao as erro:
        raise HTTPException(409, str(erro)) from erro
    except rede_cadastro.CampoNaoEditavel as erro:
        raise HTTPException(422, str(erro)) from erro
    except rede_cadastro.CadastroIndisponivel as erro:
        raise HTTPException(503, str(erro)) from erro
    except PermissionError as erro:
        # O volume existe e e' legivel, mas nao gravavel pelo usuario do container.
        # Sem esta mensagem, o operador ve um 500 opaco e o diretorio parece montado.
        raise HTTPException(
            503,
            "Sem permissão de escrita no volume do cadastro. No servidor, o diretório "
            "precisa pertencer ao usuário do container: "
            "`chown -R 1000:1000 /opt/motor-expansao/cadastro`.",
        ) from erro
    except ValueError as erro:
        raise HTTPException(422, str(erro)) from erro

    _rede_cadastro.cache_clear()
    registro = cadastro.de(unidade_id)
    return {
        "unidade_id": unidade_id,
        "versao": cadastro.versao,
        "valores": {c: registro.get(c) or "" for c in rede_cadastro.CAMPOS_EDITAVEIS},
    }


@app.get("/api/executiva/{uf}")
def executiva(uf: str, mes: str | None = None) -> dict[str, Any]:
    """Contrato v1 da Visão Executiva, servido pelo núcleo novo (BLK-EXEC-02).

    A rota continua registrada e com o MESMO payload de antes — só os números
    mudaram, e mudaram porque estavam errados:

      - o que a v1 chamava de `ticket` era `ticket_medio_pagantes`, uma coluna
        CUMULATIVA no mês lida como se fosse a foto do dia. No dia 2 de junho, SP
        aparecia com R$ 18,41 contra R$ 157,26 reais. Agora é a receita de balcão
        dos últimos ~30 dias por recorrente ativo — e o nome dela, na tela nova, é
        "receita por recorrente", nunca "ticket médio" (o `TICKET_MEDIO` do PowerBI
        é o ticket da VENDA e vem de uma tabela que a API Growth não expõe);
      - o `999` do NPS ("sem pesquisa no período") entrava na média sem filtro;
      - a exclusão casava por chave normalizada e derrubava a academia
        `AGUAS CLARAS` junto com o studio `AGUAS CLARAS - DF`.

    O laço Python por unidade morreu junto: tudo vem de `_rede_mes`, vetorizado.
    """
    uf_sel = uf.upper()
    payload = _rede_carteira_payload(mes=mes, uf=uf_sel)
    if not payload["unidades"]:
        raise HTTPException(404, f"Sem unidades Ultra com dados de rede na UF {uf_sel}.")

    kpis = payload["kpis"]
    unidades = [
        {
            "nome": u["nome"],
            "lat": u["lat"],
            "lng": u["lng"],
            "faturamento": u["metricas"]["faturamento"]["atual"],
            "ativos": u["metricas"]["ativos"]["atual"],
            "pagantes": u["metricas"]["pagantes"]["atual"],
            "agregadores": u["metricas"]["agregadores"]["atual"],
            "churn": u["metricas"]["churn_pct"]["atual"],
            "ticket": u["metricas"]["receita_por_recorrente"]["atual"],
            "nps": u["metricas"]["nps"]["atual"],
            "inauguracao": u["inauguracao"] or "",
        }
        for u in _rede_ordenar(payload["unidades"], "faturamento", "desc")
    ]
    return {
        "uf": uf_sel,
        "mes": payload["mes"],
        "meses": payload["meses"][:12],
        "referencia": payload["referencia"],
        "referencia_m1": payload["referencia_m1"],
        "centro": payload["centro"],
        "ultra_icon": payload["ultra_icon"],
        "totais": {
            "unidades": payload["totais"]["no_recorte"],
            "com_coordenada": payload["totais"]["com_coordenada"],
            "faturamento": kpis["faturamento"],
            "ativos": kpis["ativos"],
            "pagantes": kpis["pagantes"],
            "agregadores": kpis["agregadores"],
            "churn": kpis["churn_pct"],
            "ticket": kpis["receita_por_recorrente"],
            "nps": kpis["nps"],
            "pct_pagantes": payload["split"]["pct_recorrentes"],
            "pct_agregadores": payload["split"]["pct_agregadores"],
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
        carregar_poligono_municipio,
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

    # Codigo do municipio. Os dois consumidores abaixo (divisa e bairros) derivam do
    # MESMO df, entao resolve-se uma vez so'. Mantida a forma do `origin/piloto-web`,
    # que faz `.strip()` — o codigo vem do nome da particao e pode trazer espaco.
    cod_muni = None
    if "cod_municipio" in df_muni.columns and not df_muni["cod_municipio"].dropna().empty:
        cod_muni = str(df_muni["cod_municipio"].dropna().iloc[0]).strip()

    # Divisa REAL do municipio (malha IBGE em IBGE_DIR, ja montada no container do piloto):
    # sem ela os pins vazavam para os municipios vizinhos (SBC saia com Santo Andre/Diadema/SP).
    # `None` -> recorte por hexes res-7; o PDF sai igual, so menos exato na fronteira.
    poligono = carregar_poligono_municipio(IBGE_DIR, body.uf.upper(), cod_muni)

    # Bairros REAIS da pagina de bairros. Sem este kwarg `agregar_municipio` recebe None
    # e a pagina degrada EM SILENCIO para "N hexes - <tese>", ainda imprimindo a nota
    # falsa de "bairros nao mapeados na base IBGE". Streamlit e bot ja passavam.
    bairros = bairros_por_hex(body.uf.upper(), cod_muni) if cod_muni else None

    try:
        result = agregar_municipio(
            df,
            nome_municipio=body.municipio,
            uf=body.uf.upper(),
            competitors_df=comp_df,
            ultra_df=ultra_df,
            bairros_por_hex=bairros,
            df_pre_filtrado=df_muni,
            poligono_municipio=poligono,
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
            poligono_municipio=poligono,
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
    origem_centroide_hex: bool = False,
    fotos: list[UploadFile] | None = None,
) -> Response:
    """Relatorio Pontual Censitario 1,0 km (DEC-021) — fotos, dados do imovel e viabilidade.

    Espelha a montagem da API de producao (`api/service.gerar_pdf_ponto`), mas usa
    o gerador com os kwargs opcionais que o piloto precisa (`fotos`, `info_imovel`,
    `viabilidade`) — aqueles a rota de producao nao expoe.

    `info_imovel` e `viabilidade_json` chegam como JSON serializado porque o corpo
    e multipart (por causa das fotos).

    `origem_centroide_hex` (OPCIONAL, default False) e' o MARCADOR EXPLICITO de que a
    coordenada nao e' um endereco exato e sim o centroide do hexagono: o gerador imprime o
    aviso na capa e na Realizacao. Fica em parametro proprio, e nao anexado ao `rotulo`,
    porque `rotulo` e' texto livre do operador — endereco com parenteses ("Av. Paulista,
    1500 (Shopping Center 3)") seria mutilado por qualquer convencao sobre o texto.
    Esta rota e' consumida SO pelo front deste repo; a API publica
    (`src/motor_expansao/api/`) nao muda.

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
            origem_centroide_hex,
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
    origem_centroide_hex: bool = False,
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
            # DEC-021: mapa e analise voltam a usar O MESMO raio. A divergencia display 1,0 x
            # analise 1,5 durou algumas horas em 2026-07-29 e era, por construcao, um PDF que
            # desenhava um raio e contava outro. Agora o canonico vale 1,0 km e nao ha dois.
            raio_km=RAIO_CENSITARIO_DEFAULT_KM,
            competitors_df=comp_df,
            ultra_df=ultra_df,
            basemap=basemap,
            ultra_logo_dir=ultra_dir,
            street_ceil=215,
            street_gain=1.3,
            street_cap=200,
            # SEM override de alpha: o default do modulo (`_CHOROPLETH_ALPHA`) passa a valer
            # nas TRES superficies (dashboard, API/bot e piloto). Era override em duas delas —
            # 110 na API e 255 aqui — e a divergencia so aparecia comparando PDFs lado a lado.
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
        # Marcador EXPLICITO de origem (parametro proprio, nunca embutido no `rotulo`).
        origem_centroide_hex=origem_centroide_hex,
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
