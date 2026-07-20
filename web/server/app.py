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

import functools
import io
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
from pydantic import BaseModel, Field

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
        # No passo 4 a leitura e a FILA, nao a intensidade.
        if rank <= 4 and row.get("_fila"):
            return {1: "Agora", 2: "Próximo", 3: "Fila", 4: "Espera"}[rank], None
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
) -> list[dict[str, Any]]:
    """Top 4 hexes por uma coluna, no formato do painel de ranking."""
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
        if len(itens) == 4:
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

    # Passo 4 — Recomendacao: fila de aberturas priorizada por residual
    fila = white.nlargest(4, "oferta_efetiva_disponivel") if len(white) else residual.nlargest(4, "oferta_efetiva_disponivel") if len(residual) else residual

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


@app.get("/api/municipios/{uf}")
def municipios(uf: str) -> dict[str, Any]:
    df = carregar_uf(uf)
    g = (
        df.groupby("nome_municipio")
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

    hexes = [
        {
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
            "conc": int(r.get("n_concorrentes_est") or 0),
            "ultra": int(r.get("n_ultra") or 0),
        }
        for _, r in vis.iterrows()
    ]

    for p in passos:
        p["hexes"] = p["hexes"][:400]

    return {
        "uf": uf.upper(),
        "municipio": municipio,
        "n_hex_total": int(len(sel)),
        "n_hex_mapa": len(hexes),
        "centro": {"lat": _num(sel["lat"].mean(), 6), "lng": _num(sel["lng"].mean(), 6)},
        "resumo": {
            "residual_total": _num(sel["oferta_efetiva_disponivel"].sum()),
            # Somar `pop_leitura` DUPLICA: quando o hex nao tem setor censitario,
            # ela cai no fallback municipal, que se repete em todo hex do municipio.
            # A soma so e valida sobre a populacao por setor (real, por hex).
            "pop_total": (
                _num(sel["pop_total_setor_2022"].sum())
                if "pop_total_setor_2022" in sel.columns
                else None
            ),
            "score_m1_medio": _num(sel["score_priorizacao"].mean(), 1),
            "n_concorrentes": int(sel["n_concorrentes_est"].sum()),
            "n_ultra": int(sel["n_ultra"].sum()),
            "espaco_academias": int(
                round(
                    (sel.loc[
                        sel["oferta_efetiva_disponivel"] >= OFERTA_DESTAQUE_MIN,
                        "oferta_efetiva_disponivel",
                    ].sum())
                    / CAPACIDADE_CONCORRENTE_PADRAO
                )
            ),
        },
        "passos": passos,
        "hexes": hexes,
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
    # CAPEX opcional — quando None, o motor usa SIM_CAPEX_DEFAULT (R$ 2,34M).
    capex: float | None = Field(default=None, ge=0)
    capex_financiado_pct: float | None = Field(default=None, ge=0, le=1)
    capex_parcelas_meses: int | None = Field(default=None, gt=0)
    # Carencia de aluguel: meses iniciais sem pagar aluguel (beneficio de rampa;
    # melhora payback/FCF, nao muda margem/breakeven de steady-state).
    carencia_aluguel_meses: int | None = Field(default=None, ge=0, le=60)


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
    # CAPEX flui como kwarg ate o simulador (analisar_viabilidade_ponto repassa
    # **kwargs). So entra quando o operador preenche; senao o default do motor vale.
    if body.capex is not None:
        kwargs["capex"] = body.capex
    if body.capex_financiado_pct is not None:
        kwargs["capex_financiado_pct"] = body.capex_financiado_pct
    # O motor chama o param de "parcelas do financiamento" de `prazo_financiamento_meses`
    # (NAO `capex_parcelas_meses`); `viabilidade()` nao tem **kwargs, entao o nome errado
    # levantaria TypeError. Mapeia aqui.
    if body.capex_parcelas_meses is not None:
        kwargs["prazo_financiamento_meses"] = body.capex_parcelas_meses

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

    # Serie mensal de FCF (60 meses) + carencia de aluguel. Steady-state (margem,
    # breakeven, teto, ROIC) NAO muda com carencia — ela e beneficio de rampa.
    serie, payback = _fcf_serie(body, kwargs)

    dre = _extrair_dre(v)
    # Payback REAL (fonte: serie): ajustado por carencia e extrapolado alem do mes
    # 60 quando o caixa ainda nao virou (o motor limita a 60 -> inf). Mais preciso
    # que o do motor, entao sempre substitui.
    dre["payback"] = payback

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
        "aluguel_teto": _num(res.aluguel_teto_calculado),
        "flag_fora_envelope": bool(res.flag_fora_envelope),
        "flag_zona_morta": res.flag_zona_morta,
        "motivo_zona_morta": res.motivo_zona_morta,
        "split": {
            "balcao": _num(res.alunos_balcao_premissa),
            "agregadores": _num(res.alunos_agregadores_premissa),
        },
        "dre": dre,
        "fcf_serie": serie,
        "carencia_aluguel_meses": body.carencia_aluguel_meses or 0,
        "grade": json.loads(grade.to_json(orient="records")) if grade is not None else [],
    }


def _fcf_serie(
    body: "ViabilidadeIn", kwargs: dict[str, Any]
) -> tuple[list[dict[str, Any]], float | None]:
    """Serie mensal de FCF acumulado (60 meses) com carencia de aluguel opcional.

    Chama a fonte canonica `gerar_serie_mensal` (mesmo motor da viabilidade) e, se
    houver carencia, DEVOLVE o aluguel nos primeiros N meses (a carencia e nao
    pagar aluguel nesse periodo). READ-ONLY: nao altera o motor; so pos-processa a
    serie. Retorna (serie, payback_ajustado_em_meses).
    """
    from motor_expansao.dimensionamento.config import SIM_CAPEX_DEFAULT
    from motor_expansao.dimensionamento.simulador import gerar_serie_mensal
    from motor_expansao.dimensionamento.viabilidade_ponto import (
        SHARE_BALCAO_DEFAULT,
        SIM_MENSALIDADE_BALCAO,
    )

    share = SHARE_BALCAO_DEFAULT
    alunos_balcao = float(body.demanda) * share
    alunos_agregadores = float(body.demanda) * (1.0 - share)
    ticket = body.ticket or SIM_MENSALIDADE_BALCAO

    serie_kwargs: dict[str, Any] = {"alunos_agregadores": alunos_agregadores}
    if body.capex is not None:
        serie_kwargs["capex"] = body.capex
    if body.capex_financiado_pct is not None:
        serie_kwargs["capex_financiado_pct"] = body.capex_financiado_pct
    if body.capex_parcelas_meses is not None:
        serie_kwargs["prazo_financiamento_meses"] = body.capex_parcelas_meses

    try:
        serie = gerar_serie_mensal(
            alunos_balcao, body.m2, body.aluguel, ticket, **serie_kwargs
        )
    except Exception:  # noqa: BLE001 — se a serie falhar, o resto da viabilidade segue
        return [], None

    carencia = int(body.carencia_aluguel_meses or 0)
    capex_efetivo = float(body.capex) if body.capex is not None else float(SIM_CAPEX_DEFAULT)

    out: list[dict[str, Any]] = []
    prev_acum = -capex_efetivo
    acum = -capex_efetivo
    ultimo_mensal = 0.0
    payback: float | None = None
    for row in serie:
        mes = int(row["mes"])
        mensal = float(row["fcf_acumulado"]) - prev_acum
        prev_acum = float(row["fcf_acumulado"])
        if carencia and mes <= carencia:
            mensal += float(body.aluguel)  # carencia: devolve o aluguel do mes
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
# Rotas — Relatorios PDF
# ============================================================================


class RelatorioMunicipalIn(BaseModel):
    uf: str
    municipio: str
    solicitante: str | None = None


@app.post("/api/relatorio/municipal")
def relatorio_municipal(body: RelatorioMunicipalIn) -> Response:
    """Relatorio Municipal (9 paginas). Acionado pelo 4o passo do mapa."""
    from motor_expansao.dashboard.relatorio_municipal import (
        agregar_municipio,
        gerar_payloads_download_relatorio_municipal,
    )

    df = carregar_uf_completo(body.uf)
    try:
        result = agregar_municipio(df, nome_municipio=body.municipio, uf=body.uf.upper())
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Falha ao agregar o municipio: {exc}") from exc

    payloads = gerar_payloads_download_relatorio_municipal(
        result,
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


@app.post("/api/relatorio/pontual")
async def relatorio_pontual(
    lat: float,
    lng: float,
    rotulo: str | None = None,
    solicitante: str | None = None,
    info_imovel: str | None = None,
    viabilidade_json: str | None = None,
    fotos: list[UploadFile] | None = None,
) -> Response:
    """Relatorio Pontual Censitario 1,5 km — com fotos, dados do imovel e viabilidade.

    Espelha a montagem da API de producao (`api/service.gerar_pdf_ponto`), mas usa
    o gerador com os kwargs opcionais que o piloto precisa (`fotos`, `info_imovel`,
    `viabilidade`) — aqueles a rota de producao nao expoe.

    `info_imovel` e `viabilidade_json` chegam como JSON serializado porque o corpo
    e multipart (por causa das fotos).
    """
    from motor_expansao.api.service import (
        _competitors_ultra,
        _nome_municipio_de,
        _residual_do_ponto,
        _resolver_e_carregar,
    )
    from motor_expansao.api.settings import Settings
    from motor_expansao.dashboard import censo_map as _censo_map
    from motor_expansao.dashboard.censo_map import render_mapas_censitarios_combinados

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

    fotos_bytes: list[bytes] = []
    for f in fotos or []:
        conteudo = await f.read()
        if conteudo:
            fotos_bytes.append(conteudo)

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
        viabilidade=json.loads(viabilidade_json) if viabilidade_json else None,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="relatorio_pontual.pdf"'},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8899)
