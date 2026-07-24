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
import json
import math
import os
import sys
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


@functools.lru_cache(maxsize=64)
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
    # Numero de studios extras (0..3): cada studio adiciona R$6.000/mes de folha.
    n_studios: int | None = Field(default=None, ge=0, le=3)
    # --- Investimento: Obra (CAPEX, equity) x Equipamentos (OPEX, financiado) ---
    # Obra: desembolso do franqueado (equity), parcelado sem juros (parcelas_obra,
    # default 4). E a base do ROIC e do fluxo acumulado (payback parte de -Obra).
    obra: float | None = Field(default=None, ge=0)
    parcelas_obra: int | None = Field(default=None, gt=0, le=12)
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
    # Meses de rampa de maturacao do balcao (Simulador E13; default do motor = 8).
    # Controlavel pelo operador na sidebar; afeta a serie de FCF e o payback (rampa
    # mais longa = caixa mais lento), nao a margem/breakeven de steady-state.
    rampa_meses: int | None = Field(default=None, ge=1, le=36)


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

    base = _base_calibracao()
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
    """Investimento do franqueado (NUCLEO — a vista, sem financiamento).

    Obra + Equipamentos somam o CAPEX total; somado a taxa de franquia (R$160k) da o
    INVESTIMENTO TOTAL, base do ROIC (desalavancado) e do payback — igual a planilha
    (Simulador!N21 = lucro/(R9+R10)). Financiamento/alavancagem como camada separada
    fica para o 2o passo (por isso, no nucleo, nao ha PMT afetando DRE/payback/ROIC).
    """
    from motor_expansao.dimensionamento.config import SIM_CAPEX_DEFAULT, SIM_TAXA_FRANQUIA

    if body.obra is not None or body.equipamentos is not None:
        capex_total = float(body.obra or 0.0) + float(body.equipamentos or 0.0)
    elif body.capex is not None:
        capex_total = float(body.capex)
    else:
        capex_total = float(SIM_CAPEX_DEFAULT)
    franquia = float(SIM_TAXA_FRANQUIA)
    return {
        "capex_total": capex_total,
        "franquia": franquia,
        "investimento_total": capex_total + franquia,
    }


def _clusters_aluguel_teto(faturamento: float | None) -> dict[str, float | None] | None:
    """Aluguel-teto por clusters sobre o faturamento bruto steady (planilha oficial):
    Ideal 15% · Teto 20% · Excecao 30%. Substitui a inversao por margem EBITDA."""
    from motor_expansao.dimensionamento.config import (
        SIM_ALUGUEL_TETO_EXCECAO,
        SIM_ALUGUEL_TETO_IDEAL,
        SIM_ALUGUEL_TETO_TETO,
    )

    if faturamento is None or faturamento <= 0:
        return None
    return {
        "ideal": _num(faturamento * SIM_ALUGUEL_TETO_IDEAL, 2),
        "teto": _num(faturamento * SIM_ALUGUEL_TETO_TETO, 2),
        "excecao": _num(faturamento * SIM_ALUGUEL_TETO_EXCECAO, 2),
    }


@app.post("/api/viabilidade")
def viabilidade(body: ViabilidadeIn) -> dict[str, Any]:
    from motor_expansao.dimensionamento.viabilidade_ponto import (
        analisar_viabilidade_ponto,
    )

    kwargs: dict[str, Any] = {}
    if body.ticket:
        kwargs["ticket_medio"] = body.ticket
    if body.formato:
        kwargs["formato"] = body.formato
    # Margem EBITDA-alvo do operador -> define o aluguel-teto e os alunos-para-alvo
    # (analisar_viabilidade_ponto tem `margem_alvo` como param nomeado; liga direto).
    if body.margem_alvo is not None:
        kwargs["margem_alvo"] = body.margem_alvo
    # Investimento (NUCLEO — a vista): Obra + Equipamentos = CAPEX total; o motor recebe
    # SO o capex (sem financiamento/PMT — camada separada fica p/ o 2o passo). O efeito
    # dos studios ja veio embutido no ticket (frontend), nao como custo aqui.
    inv = _investimento(body)
    kwargs["capex"] = inv["capex_total"]
    # Rampa de maturacao (Simulador E13). Flui como kwarg ate gerar_serie_mensal
    # via analisar_viabilidade_ponto(**kwargs); afeta FCF/payback, nao a margem.
    if body.rampa_meses is not None:
        kwargs["maturacao_meses"] = body.rampa_meses

    base = _base_calibracao()
    if base is not None:
        kwargs["base_calibracao_df"] = base

    res = analisar_viabilidade_ponto(
        lat=body.lat,
        lng=body.lng,
        m2=body.m2,
        aluguel_pedido=body.aluguel,
        demanda_premissa=body.demanda,
        **kwargs,
    )

    v = res.viabilidade

    # Serie mensal de FCF acumulado (payback, 60 meses, parte de -Obra) + carencia de
    # aluguel. Steady-state (margem, breakeven, teto, ROIC) NAO muda com carencia.
    serie, payback = _fcf_serie(body, inv)

    dre = _extrair_dre(v)
    # Payback REAL (fonte: serie): ajustado por carencia e extrapolado alem do mes
    # 60 quando o caixa ainda nao virou (o motor limita a 60 -> inf). Mais preciso
    # que o do motor, entao sempre substitui.
    dre["payback"] = payback
    # ROIC DESALAVANCADO = lucro liquido anual / investimento total (capex + franquia),
    # igual a planilha (Simulador!N21 = lucro/(R9+R10)). NAO desconta PMT (financiamento
    # e camada separada, 2o passo). Usa o lucro steady x12 (retorno de maturidade).
    investimento = float(inv["investimento_total"])
    lucro_liq = getattr(v, "lucro_liquido_mensal", None)
    dre["roic"] = (
        _num((float(lucro_liq) * 12.0) / investimento, 4)
        if (lucro_liq is not None and investimento > 0)
        else None
    )

    # Aluguel-teto por clusters (% do faturamento bruto steady): Ideal/Teto/Excecao.
    aluguel_teto_clusters = _clusters_aluguel_teto(
        getattr(v, "faturamento_mensal_steady", None)
    )

    # Resultado operacional mês a mês (não acumulado): quando a operação passa a se
    # pagar sozinha por mês e estabiliza no positivo (mes_operacao_positiva).
    fco_serie, mes_operacao_positiva = _fco_serie(body, inv)

    # Sugestoes de melhoria quando o payback estoura: quanto cortar do investimento OU
    # do aluguel para trazer o payback para a faixa ideal (o capex desloca o acumulado 1:1).
    melhoria = _melhoria_payback(serie, payback, float(body.aluguel), investimento)

    grade = res.grade_sensibilidade
    return {
        "demanda_premissa": res.demanda_premissa,
        "demanda_fonte": res.demanda_fonte,
        "faixa_alunos": {
            "p10": _num(res.faixa_alunos_p10),
            "p50": _num(res.faixa_alunos_p50),
            "p90": _num(res.faixa_alunos_p90),
            "n_comparaveis": res.n_comparaveis,
        },
        "alunos_breakeven": _num(res.alunos_breakeven),
        "alunos_para_margem_alvo": _num(res.alunos_para_margem_alvo),
        "aluguel_teto": aluguel_teto_clusters,
        "flag_fora_envelope": bool(res.flag_fora_envelope),
        "flag_zona_morta": res.flag_zona_morta,
        "motivo_zona_morta": res.motivo_zona_morta,
        "split": {
            "balcao": _num(res.alunos_balcao_premissa),
            "agregadores": _num(res.alunos_agregadores_premissa),
        },
        "dre": dre,
        "fcf_serie": serie,
        "fco_serie": fco_serie,
        "mes_operacao_positiva": mes_operacao_positiva,
        "carencia_aluguel_meses": body.carencia_aluguel_meses or 0,
        "melhoria_payback": melhoria,
        "grade": json.loads(grade.to_json(orient="records")) if grade is not None else [],
    }


def _melhoria_payback(
    serie: list[dict[str, Any]],
    payback: float | None,
    aluguel: float,
    capex_efetivo: float,
    alvo_meses: int = 36,
    gatilho_meses: int = 40,
) -> dict[str, Any] | None:
    """Quando o payback estoura (> gatilho), estima quanto cortar de CAPEX OU de aluguel
    para o payback cair para ~alvo_meses. Estimativa de 1a ordem a partir da serie de FCF:
    o CAPEX desloca a curva 1:1; cada R$1/mes a menos de aluguel soma ~alvo_meses ao caixa
    no mes-alvo. Retorna None quando nao ha o que sugerir (payback ok ou serie ausente).

    payback None (nunca vira dentro de 60 meses) e o PIOR caso -> tambem gera sugestao."""
    if payback is not None and payback <= gatilho_meses:
        return None
    row = next((r for r in serie if r.get("mes") == alvo_meses), None)
    if row is None or row.get("fcf") is None or float(row["fcf"]) >= 0:
        return None
    deficit = -float(row["fcf"])  # caixa que ainda falta no mes-alvo
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


def _serie_motor(body: ViabilidadeIn, inv: dict[str, Any]) -> list[dict[str, Any]]:
    """Serie mensal BRUTA do motor (60 meses; campos com `fcf_acumulado`).

    Fonte unica usada pelas duas curvas (payback e operacional). Recebe o capex TOTAL
    (Obra+Equip) e a fracao financiada (Equip/total) do `inv` -> o motor parte de -Obra.
    Retorna [] em caso de falha (degrada gracioso).
    """
    from motor_expansao.dimensionamento.simulador import gerar_serie_mensal
    from motor_expansao.dimensionamento.viabilidade_ponto import (
        SHARE_BALCAO_DEFAULT,
        SIM_MENSALIDADE_BALCAO,
    )

    share = SHARE_BALCAO_DEFAULT
    alunos_balcao = float(body.demanda) * share
    alunos_agregadores = float(body.demanda) * (1.0 - share)
    ticket = body.ticket or SIM_MENSALIDADE_BALCAO

    serie_kwargs: dict[str, Any] = {
        "alunos_agregadores": alunos_agregadores,
        "capex": inv["capex_total"],
    }
    if body.rampa_meses is not None:
        serie_kwargs["maturacao_meses"] = body.rampa_meses

    try:
        return gerar_serie_mensal(alunos_balcao, body.m2, body.aluguel, ticket, **serie_kwargs)
    except Exception:  # noqa: BLE001 — se a serie falhar, o resto da viabilidade segue
        return []


# Meses de pré-abertura/obras antes da inauguração (M-4..M-1). O CAPEX é desembolsado
# nesse período e a carência de aluguel conta A PARTIR DE M-4 (mês de contrato 1 = M-4).
_MESES_OBRA = 4


def _fcf_serie(
    body: ViabilidadeIn, inv: dict[str, Any]
) -> tuple[list[dict[str, Any]], float | None]:
    """Serie de FCF acumulado (payback): 60 meses, partindo de -(capex + franquia).

    NUCLEO a vista: o acumulado parte do INVESTIMENTO total (capex + taxa de franquia)
    e soma o caixa operacional mes a mes (sem PMT — financiamento e camada separada).
    Se houver carencia, DEVOLVE o aluguel nos primeiros N meses. READ-ONLY.
    Retorna (serie, payback_ajustado_em_meses).
    """
    serie = _serie_motor(body, inv)
    if not serie:
        return [], None

    carencia = int(body.carencia_aluguel_meses or 0)
    capex_total = float(inv["capex_total"])
    investimento = float(inv["investimento_total"])

    out: list[dict[str, Any]] = []
    prev_motor = -capex_total  # acumulado do motor ANTES do mes 1 (a vista, sem PMT)
    acum = -investimento  # payback parte do investimento total (capex + franquia)
    ultimo_mensal = 0.0
    payback: float | None = None
    for row in serie:
        mes = int(row["mes"])
        mensal = float(row["fcf_acumulado"]) - prev_motor
        prev_motor = float(row["fcf_acumulado"])
        if carencia and (mes + _MESES_OBRA) <= carencia:
            mensal += float(body.aluguel)  # carencia (contada de M-4): devolve o aluguel
        acum += mensal
        ultimo_mensal = mensal
        if payback is None and acum >= 0:
            payback = float(mes)
        out.append({"mes": mes, "fcf": _num(acum)})

    # Nao virou dentro dos 60 meses: extrapola pelo FCF mensal de steady-state
    # (mes 60 ja e pos-maturacao e pos-carencia). Mostra o payback REAL em vez de
    # "inf"/"nao atinge". So faz sentido se o caixa mensal ja e positivo.
    if payback is None and ultimo_mensal > 0:
        payback = float(round(60 + (-acum) / ultimo_mensal))

    return out, payback


def _plano_pagamento(body: ViabilidadeIn, inv: dict[str, Any]) -> dict[str, Any]:
    """Desmembra o investimento em OBRA (equity, parcelada SEM juros) e EQUIPAMENTOS
    (FINANCIADOS, PMT com juros — sistema Price) para o fluxo de caixa mês a mês.

    - Obra: `obra` pago em `parcelas_obra` parcelas iguais (default 4), sem juros.
    - Equipamentos: `equipamentos` financiado em `prazo_equipamentos` meses a
      `juros_equipamentos_am` (fracao a.m.) -> PMT constante. Juros 0 -> parcela simples.
    Legado (so `capex`/`capex_financiado_*`): split por valor/percentual; senao tudo em obra.
    Retorna as parcelas mensais e os prazos, para `_fco_serie` compor o caixa."""
    capex_total = float(inv["capex_total"])
    obra = float(body.obra) if body.obra is not None else None
    equip = float(body.equipamentos) if body.equipamentos is not None else None
    if obra is None and equip is None:
        if body.capex_financiado_valor:
            equip = min(float(body.capex_financiado_valor), capex_total)
            obra = capex_total - equip
        elif body.capex_financiado_pct:
            equip = capex_total * float(body.capex_financiado_pct)
            obra = capex_total - equip
        else:
            obra, equip = capex_total, 0.0
    obra = float(obra or 0.0)
    equip = float(equip or 0.0)

    parcelas_obra = int(body.parcelas_obra or _MESES_OBRA)
    prazo_equip = int(body.prazo_equipamentos or body.capex_parcelas_meses or 36)
    juros = body.juros_equipamentos_am
    if juros is None:
        juros = body.juros_financiamento_am
    juros = float(juros or 0.0)

    obra_parcela = obra / parcelas_obra if parcelas_obra > 0 else 0.0
    if equip > 0 and prazo_equip > 0:
        if juros > 0:
            fator = (1.0 + juros) ** prazo_equip
            equip_pmt = equip * juros * fator / (fator - 1.0)
        else:
            equip_pmt = equip / prazo_equip
    else:
        equip_pmt = 0.0
    return {
        "obra": obra,
        "equipamentos": equip,
        "obra_parcela": obra_parcela,
        "parcelas_obra": max(parcelas_obra, 0),
        "equip_pmt": equip_pmt,
        "prazo_equip": max(prazo_equip, 0),
        "juros": juros,
    }


def _fco_serie(
    body: ViabilidadeIn, inv: dict[str, Any]
) -> tuple[list[dict[str, Any]], int | None]:
    """Fluxo de caixa OPERACIONAL + FINANCEIRO mês a mês (NÃO acumulado), a partir das OBRAS.

    Compõe, mês a mês: (a) caixa OPERACIONAL (EBITDA − IR/CSLL, já com aluguel), (b) a
    PARCELA da OBRA (equity, sem juros, ao longo de `parcelas_obra`), (c) a PMT dos
    EQUIPAMENTOS FINANCIADOS (com juros, ao longo de `prazo_equipamentos`) e (d) o aluguel
    da pré-abertura. Por isso REAGE a obra/equipamentos/parcelas/juros (antes o gráfico era
    idêntico em qualquer cenário de financiamento). O motor roda A VISTA (sem PMT); a
    alavancagem é composta AQUI, então o caixa operacional puro sai do delta do motor.

    Linha do tempo: M-4..M-1 = obras (parcela da obra + aluguel salvo carência), depois a
    operação (mês 1..60). Carência de aluguel conta A PARTIR de M-4 (mês de contrato 1 = M-4).
    Retorna (serie, mes_operacao_positiva) — 1o mês de OPERAÇÃO (>=1) com resultado >= 0 que
    assim permanece (None se nunca vira)."""
    serie = _serie_motor(body, inv)
    if not serie:
        return [], None

    aluguel = float(body.aluguel)
    carencia = int(body.carencia_aluguel_meses or 0)
    capex_total = float(inv["capex_total"])
    plano = _plano_pagamento(body, inv)
    obra_parcela = float(plano["obra_parcela"])
    parcelas_obra = int(plano["parcelas_obra"])
    equip_pmt = float(plano["equip_pmt"])
    prazo_equip = int(plano["prazo_equip"])

    out: list[dict[str, Any]] = []
    # Pré-abertura (M-4..M-1, mês de contrato 1..4): parcela da obra (enquanto durar) +
    # aluguel (fora da carência). Equipamentos financiados NÃO desembolsam aqui (a PMT
    # corre na operação).
    for i in range(_MESES_OBRA):
        contrato_mes = i + 1  # 1..4 -> M-4..M-1
        display_mes = i - _MESES_OBRA  # -4..-1
        val = 0.0
        if contrato_mes <= parcelas_obra:
            val -= obra_parcela
        if contrato_mes > carencia:
            val -= aluguel
        out.append({"mes": display_mes, "fcf": _num(val)})

    # Operação: caixa operacional (delta do motor — EBITDA − IR, com aluguel; o capex
    # cancela no delta) MENOS a parcela da obra que passa da abertura e a PMT dos
    # equipamentos. Carência devolve o aluguel enquanto vigente (contada de M-4).
    prev_acum = -capex_total
    for row in serie:
        mes = int(row["mes"])
        contrato_mes = mes + _MESES_OBRA  # 5..64
        mensal = float(row["fcf_acumulado"]) - prev_acum
        prev_acum = float(row["fcf_acumulado"])
        if carencia and contrato_mes <= carencia:
            mensal += aluguel  # carência ainda vigente neste mês de operação
        if contrato_mes <= parcelas_obra:
            mensal -= obra_parcela  # parcelas de obra que passam da abertura
        if mes <= prazo_equip:
            mensal -= equip_pmt  # PMT do equipamento financiado (juros a.m.)
        out.append({"mes": mes, "fcf": _num(mensal)})

    # Break-even operacional: 1o mês de OPERAÇÃO (mes >= 1) com resultado >= 0 e que
    # assim permanece (ignora as obras, sempre negativas).
    positiva: int | None = None
    operacao = [p for p in out if p["mes"] >= 1]
    for i, p in enumerate(operacao):
        val = p["fcf"]
        if val is not None and val >= 0 and all((q["fcf"] or 0.0) >= 0 for q in operacao[i:]):
            positiva = int(p["mes"])
            break

    return out, positiva


def _extrair_dre(v: Any) -> dict[str, Any]:
    """Monta a cascata do DRE a partir do ViabilidadeResult.

    O dataclass expoe NIVEIS acumulados (faturamento -> receita liquida ->
    receita pos-impostos -> EBITDA), nao as parcelas. A cascata precisa das
    PARCELAS, entao cada degrau e a diferenca entre dois niveis consecutivos.

    Atencao: `margem_ebitda_pct` e FRACAO (-0.3457), nao percentual; e
    `payback_meses` vem `inf` quando nunca paga, e inf nao sobrevive ao JSON.
    """

    def campo(nome: str) -> float | None:
        return _num(getattr(v, nome, None), 2)

    faturamento = campo("faturamento_mensal_steady")
    liquida = campo("receita_liquida")
    pos_imp = campo("receita_pos_impostos")
    ebitda = campo("ebitda_mensal")

    def delta(a: float | None, b: float | None) -> float | None:
        return None if a is None or b is None else round(a - b, 2)

    margem_frac = getattr(v, "margem_ebitda_pct", None)

    return {
        "faturamento": faturamento,
        "deducoes": delta(faturamento, liquida),
        "impostos": delta(liquida, pos_imp),
        "custos": delta(pos_imp, ebitda),
        "ebitda": ebitda,
        "margem": None if margem_frac is None else _num(float(margem_frac) * 100, 2),
        "payback": _num(getattr(v, "payback_meses", None), 1),
        "roic": _num(getattr(v, "roic_anual", None), 4),
        "lucro_liquido": campo("lucro_liquido_mensal"),
        "flag_viavel": bool(getattr(v, "flag_viavel", False)),
    }


@functools.lru_cache(maxsize=1)
def _base_calibracao() -> pd.DataFrame | None:
    """Base de comparaveis da curva tamanho->densidade.

    A curva exige a coluna `alunos_por_m2`. `base_calibracao_multirede` NAO a tem
    (traz `alunos_reais` + `metragem` crus), entao entregar aquele parquet faz a
    faixa voltar vazia com n_comparaveis=0 — foi o bug da primeira versao.
    Prioriza as bases que ja trazem a coluna e valida antes de devolver.
    """
    for nome in (
        "base_calibracao_maduras.parquet",
        "unidades_ultra_performance_hex.parquet",
    ):
        caminho = STAGING_DIR / nome
        if not caminho.exists():
            continue
        try:
            df = pd.read_parquet(caminho)
        except Exception:  # noqa: BLE001 — base opcional, degrada gracioso
            continue
        if "alunos_por_m2" in df.columns and len(df):
            return df
    return None


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
    """Re-roda o motor de viabilidade e monta o payload do slide do PDF COM os graficos
    (rampa de alunos, faturamento/EBITDA, FCF acumulado, DRE waterfall). `None` em qualquer
    falha -> o PDF cai no payload so-numeros (viabilidade_json). Alinha payback/roic aos
    MESMOS valores da tela (a rota /api/viabilidade sobrescreve os do motor). READ-ONLY M1."""
    try:
        from motor_expansao.dashboard.viabilidade_charts import montar_payload_viabilidade
        from motor_expansao.dimensionamento.viabilidade_ponto import (
            analisar_viabilidade_ponto,
        )

        kwargs: dict[str, Any] = {}
        if body.ticket:
            kwargs["ticket_medio"] = body.ticket
        if body.formato:
            kwargs["formato"] = body.formato
        if body.margem_alvo is not None:
            kwargs["margem_alvo"] = body.margem_alvo
        inv = _investimento(body)
        kwargs["capex"] = inv["capex_total"]
        if body.rampa_meses is not None:
            kwargs["maturacao_meses"] = body.rampa_meses
        base = _base_calibracao()
        if base is not None:
            kwargs["base_calibracao_df"] = base

        res = analisar_viabilidade_ponto(
            lat=body.lat,
            lng=body.lng,
            m2=body.m2,
            aluguel_pedido=body.aluguel,
            demanda_premissa=body.demanda,
            **kwargs,
        )
        serie = _serie_motor(body, inv)
        # Fluxo de Caixa Operacional (M-4..operação) para o gráfico do slide — substitui
        # a antiga "rampa de alunos" e reage a aluguel/capex (item Felipe 2026-07-23).
        fco_serie, mes_operacao_positiva = _fco_serie(body, inv)
        payload = montar_payload_viabilidade(
            res,
            serie,
            maturacao_mes=body.rampa_meses,
            fco_serie=fco_serie,
            mes_operacao_positiva=mes_operacao_positiva,
        )

        # Alinha payback/roic aos valores da TELA (a rota /api/viabilidade sobrescreve os do
        # motor: payback pela serie de FCF, roic desalavancado) -> numeros do PDF batem.
        _serie_fcf, payback = _fcf_serie(body, inv)
        payload["payback_meses"] = payback
        investimento = float(inv["investimento_total"])
        lucro_liq = getattr(res.viabilidade, "lucro_liquido_mensal", None)
        payload["roic_anual"] = (
            _num((float(lucro_liq) * 12.0) / investimento, 4)
            if (lucro_liq is not None and investimento > 0)
            else None
        )
        return payload
    except Exception:  # noqa: BLE001
        return None


def _residual_hexes_do_ponto(lat: float, lng: float, staging_dir: Path):
    """Disco de hexes (grid_disk k=5, res 7) ao redor do ponto com `oferta_efetiva_disponivel`,
    para o choropleth de Residual Fitness do slide-hero "Socioeconomia e Residual Fitness".

    Filtro direto no parquet de mercado (~91 linhas), espelhando `_residual_do_ponto`. `None`
    se o parquet faltar ou falhar -> a camada residual cai no fallback textual (offline-safe).
    READ-ONLY sobre o M1 (so leitura de parquet)."""
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
        tbl = ds.dataset(mercado).to_table(
            filter=pc.field("hex_id").isin(cells),
            columns=["hex_id", "oferta_efetiva_disponivel"],
        )
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
        gerar_pdf_relatorio_pontual_censitario,
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
            raio_km=RAIO_CENSITARIO_DEFAULT_KM,
            competitors_df=comp_df,
            ultra_df=ultra_df,
            basemap=basemap,
            ultra_logo_dir=ultra_dir,
            street_ceil=215,
            street_gain=1.3,
            street_cap=200,
            choropleth_alpha=110,
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

    pdf = gerar_pdf_relatorio_pontual_censitario(
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
