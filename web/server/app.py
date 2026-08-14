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
from collections.abc import Callable, Collection
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
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
import acesso  # noqa: E402  (controle TEMPORARIO de acesso por aba, por Remote-User)
import cobertura_1km  # noqa: E402  (PROTOTIPO — area coberta pelo raio, para desenhar)
import pressao_1km  # noqa: E402  (PROTOTIPO — chave de raio 2 km / 1 km por area)

from motor_expansao.dashboard import (  # noqa: E402
    rede_cadastro,
    rede_coorte,
    rede_diagnostico,
    rede_faturamento_financeiro,
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
# Passo 4 do funil — Crescimento municipal. Camada de CONTEXTO: repassa o que o
# projeto Crescimento Regional TEC ja apura por municipio (CAGED, RAIS, CNPJ da
# Receita). Nao prediz, nao ranqueia oportunidade, nao reconstroi nada.
# Artefato PARALELO e OPCIONAL; NAO e escrito no enriquecido — M1 READ-ONLY.
CONCORRENTES_PATH = STAGING_DIR / "concorrentes_mapeados.parquet"
CRESCIMENTO_PATH = STAGING_DIR / "crescimento_municipal.parquet"
# Taxa de crescimento da area construida POR HEXAGONO (satelite 2016-2023). E o
# que colore o mapa no passo 4: quem decide olha taxa de crescimento, nao emprego
# formal do municipio (que segue no painel, onde ele faz sentido).
CRESCIMENTO_HEX_PATH = STAGING_DIR / "crescimento_hex.parquet"

# O que o piloto realmente consome do artefato municipal. Lido de forma defensiva:
# coluna ausente some do subset em vez de derrubar a rota.
_COLS_CRESCIMENTO = [
    "cod6",
    "cres_chave_nome",
    "cres_tendencia",
    "cres_emp_pct",
    "cres_saldo_empresas",
    "cres_confiab",
    "cres_salario",
    "cres_salario_var",
    "cres_setor",
    "cres_uf_mediana",
    "cres_dims",
    "cres_series",
    "v_frase",
]

CAPACIDADE_CONCORRENTE_PADRAO = 2500.0
OFERTA_DESTAQUE_MIN = 2000.0  # espelha relatorio_municipal (emenda BLK-RELMUN-03)
POP_MIN_ACIONAVEL = 5000  # regua operacional do dashboard (<5k = descartado)

# --- Reguas do funil e das etiquetas -----------------------------------------
# Estavam como literais espalhados dentro de _etiqueta/_etiqueta_muni/montar_funil.
# Subiram para ca' porque o painel de Metodologia (/api/metodologia) publica estes
# MESMOS nomes na tela: com o numero escrito em dois lugares, ajustar um parametro
# fazia a explicacao mentir sem ninguem perceber. Mudou aqui, muda no funil E no texto.
SCORE_CORTE_QUENTE = 70.0  # piso do passo 1 (hexagono "quente")

# --- Reguas do CRITERIO DO IMOVEL ("Serve este imovel?"), so' do modo de ponto ---------
# Decisao do Juan em 2026-08-12: afrouxar os dois cortes que mais reprovavam imovel.
#
# ATE ENTAO estas duas reguas eram AS MESMAS do funil — o score usava
# `SCORE_CORTE_QUENTE` (piso do passo 1) e a concorrencia usava o white space do passo 5
# (zero concorrente). A partir daqui elas DIVERGEM de proposito, e isso tem consequencia
# que precisa estar escrita: um imovel pode passar no criterio da ficha e ficar de fora do
# funil, porque o funil continua exigindo 70 e zero concorrente. Nao e' contradicao — sao
# perguntas diferentes ("este imovel serve?" contra "quais hexagonos entram na fila") —,
# mas quem comparar as duas telas vai notar, e a explicacao tem de existir.
#
# O FUNIL NAO FOI TOCADO. Mexer em `SCORE_CORTE_QUENTE` mudaria o passo 1 do mapa inteiro
# e o texto da metodologia junto; o pedido era sobre a janela de analise de pontos.
CRIT_PONTO_SCORE_MIN = 60.0  # era SCORE_CORTE_QUENTE (70,0)
CRIT_PONTO_CONC_MAX = 3  # era 0 (white space do passo 5)
# SEM USO desde o BLK-MAPA-FAIXAS-01 (regua unica legenda<->etiqueta): as quatro linhas
# abaixo descrevem os cortes de Quente/Forte/Solido e Alta/Media/Baixa POR HEXAGONO,
# vocabularios que `_etiqueta` nao emite mais — hoje ele deriva de FAIXAS_MAPA_* (de 20
# em 20 pontos), e o painel de Metodologia tambem. Ficam aqui, marcadas, porque apagar
# regua e' decisao de quem escreveu o painel; NAO reintroduzir sem DEC/decisao explicita.
FAIXA_SCORE_QUENTE = 90.0  # (orfa) etiqueta Quente
FAIXA_SCORE_FORTE = 80.0  # (orfa) etiqueta Forte; abaixo disso, Solido
FAIXA_RESIDUAL_ALTA_HEX = 6000.0  # (orfa) etiqueta Alta, residual de UM hexagono
FAIXA_RESIDUAL_MEDIA_HEX = 3000.0  # (orfa) etiqueta Media; abaixo, Baixa
# As de UF e as de contagem de hexes SEGUEM VIVAS: `_etiqueta_muni` continua sendo o
# fallback do ranking de municipios quando `faixa_por` nao e' informado.
FAIXA_RESIDUAL_ALTA_UF = 20000.0  # idem, somado por municipio (patamar maior)
FAIXA_RESIDUAL_MEDIA_UF = 8000.0
FAIXA_HEXES_POLO = 30  # etiqueta Polo, em nº de hexes quentes do municipio
FAIXA_HEXES_FORTE = 8  # etiqueta Forte; abaixo, Emergente
CONC_ADENSAR_MAX = 2  # ate' 2 concorrentes estimados = cabe adensar
FILA_MAX = 10  # tamanho maximo da fila do ultimo passo
# Abaixo disto a mediana da UF nao serve de divisor (a razao explode). Ver
# `_etiqueta_crescimento`: no artefato vigente nenhuma UF chega perto, e o piso e defesa.
_CRESC_PISO_MEDIANA = 1.0

app = FastAPI(title="Piloto Web — Motor de Expansao", version="0.1.0")
# Em producao o SPA e a API sao servidos pela MESMA origem (mesmo container atras do
# Caddy), entao CORS e irrelevante ali; estas origens sao so para o dev (Vite :5000).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000", "http://127.0.0.1:5000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Controle TEMPORARIO de acesso por aba (2026-08-13): o Authelia autentica; aqui cada
# rota e' liberada pela aba que a consome, segundo o `Remote-User` que o Caddy repassa.
# Regras, mapa `usuario -> [abas]` e degradacao (fail-open sem o JSON) em `acesso.py`.
# A SPA esconde as abas via /api/me; este middleware e' quem barra de verdade.
@app.middleware("http")
async def _controle_de_acesso_por_aba(request: Request, call_next):  # type: ignore[no-untyped-def]
    detalhe = acesso.motivo_bloqueio(request.url.path, request.headers.get("Remote-User"))
    if detalhe is not None:
        return JSONResponse({"detail": detalhe}, status_code=403)
    return await call_next(request)


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
    # Insumo do modelo de 1 km: junto com `oferta_consumida_ultra_real` reproduz o
    # `oferta_consumida_ultra_estimada` do Bloco 5, necessario para o residual sem
    # concorrente em hexagono SATURADO. Leitura defensiva — se a UF nao materializar a
    # coluna, `pressao_1km` devolve NaN ali em vez de um numero inflado.
    "n_unidades_ultra_2km",
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
    df = _completar_unidades_ultra_2km(df)
    cres = carregar_crescimento()
    if cres is not None:
        df = _juntar_crescimento(df, cres, uf.upper())
    chex = carregar_crescimento_hex()
    if chex is not None:
        df = df.merge(chex, on="hex_id", how="left", validate="m:1")
    return _derivar(df)


#: Insumo do consumo Ultra que o artefato ENRIQUECIDO nao materializa. Vive no parquet de
#: mercado, de onde o proprio artefato deriva.
MERCADO_PARQUET = STAGING_DIR / "hexagonos_mercado_mapeado.parquet"


@functools.lru_cache(maxsize=1)
def _unidades_ultra_2km() -> dict[str, int]:
    """`hex_id -> n_unidades_ultra_2km`, SO' dos hexagonos com pelo menos uma unidade.

    Medido em 2026-08-12: 299 hexagonos dos 1.542.531 do parquet de mercado (0,02%), 0,03 MB.
    Guardar so' os nao-zero e' o que torna este mapa barato -- ler as duas colunas inteiras
    custa 0,7 s e 117 MB residentes, para uma informacao que e' zero em 99,98% da base.
    """
    if not MERCADO_PARQUET.exists():
        return {}
    try:
        bruto = pd.read_parquet(MERCADO_PARQUET, columns=["hex_id", "n_unidades_ultra_2km"])
    except (OSError, ValueError, KeyError) as erro:
        print(f"[mapa] n_unidades_ultra_2km indisponivel ({erro})", file=sys.stderr)
        return {}
    n = pd.to_numeric(bruto["n_unidades_ultra_2km"], errors="coerce").fillna(0)
    com_unidade = bruto.loc[n > 0, "hex_id"].astype(str)
    return dict(zip(com_unidade, n[n > 0].astype(int), strict=True))


def _completar_unidades_ultra_2km(df: pd.DataFrame) -> pd.DataFrame:
    """Repoe `n_unidades_ultra_2km` quando a particao nao a materializa.

    Sem ela, `pressao_1km._consumo_ultra` devolve `None` e TODO hexagono saturado sai da
    leitura como ausente -- 94,6% de SP. O efeito visivel era a rota `/api/cobertura`
    respondendo 500 em 17 das 27 UFs (todas as densas), o que apagava os raios e o mapa de
    calor da pressao concorrencial e deixava so' a recoloracao dos hexagonos.

    O conserto DEFINITIVO e' materializar a coluna no artefato enriquecido; enquanto ele
    nao vier, isto a reconstroi do parquet de mercado, que e' a fonte de onde o proprio
    artefato deriva. `_COLS_DESEJADAS` continua pedindo a coluna: no dia em que a particao
    passar a te-la, este caminho nao roda.
    """
    if "n_unidades_ultra_2km" in df.columns:
        return df
    mapa = _unidades_ultra_2km()
    if not mapa:
        return df
    df["n_unidades_ultra_2km"] = (
        df["hex_id"].astype(str).map(mapa).fillna(0).astype("int32")
    )
    return df


@functools.lru_cache(maxsize=1)
def carregar_crescimento_hex() -> pd.DataFrame | None:
    """Taxa de crescimento da area construida por hexagono. READ-ONLY e OPCIONAL."""
    if not CRESCIMENTO_HEX_PATH.exists():
        return None
    df = pd.read_parquet(CRESCIMENTO_HEX_PATH)
    df["hex_id"] = df["hex_id"].astype(str)
    return df


def _norm_nome(s: pd.Series) -> pd.Series:
    """Normaliza nome de municipio para casamento: sem acento, maiusculo, sem espaco duplo."""
    return (
        s.astype("string")
        .str.normalize("NFKD")
        .str.encode("ascii", "ignore")
        .str.decode("ascii")
        .str.upper()
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )


def _juntar_crescimento(df: pd.DataFrame, cres: pd.DataFrame, uf: str) -> pd.DataFrame:
    """Junta a camada municipal, com FALLBACK por nome.

    O M1 deixa `cod_municipio` 100% NULO em 6 das 12 UFs cobertas (ES, PR, SC, BA,
    PE, CE — cerca de 204 mil hexes). Sem o fallback, metade do territorio coberto
    ficaria sem leitura de crescimento mesmo com o dado existindo. `nome_municipio`
    esta completo em todas as UFs, entao (uf, nome normalizado) recupera o resto.
    """
    cod6 = (
        df["cod_municipio"].astype("string").str[:6]
        if "cod_municipio" in df.columns
        else pd.Series(pd.NA, index=df.index, dtype="string")
    )
    falta = cod6.isna()
    # `cres_chave_nome` e opcional: sem a guarda, um artefato regerado sem ela dava
    # KeyError aqui dentro e derrubava carregar_uf() — ou seja, TODAS as rotas de
    # mapa, nao so o passo 4.
    if falta.any() and "nome_municipio" in df.columns and "cres_chave_nome" in cres.columns:
        mapa = dict(zip(cres["cres_chave_nome"], cres["cod6"], strict=True))
        chave = uf + "|" + _norm_nome(df["nome_municipio"])
        cod6 = cod6.fillna(chave.map(mapa).astype("string"))
    df = df.assign(_cod6=cod6)
    # validate="m:1": se o artefato vier com cod6 repetido, o merge DUPLICA hexes e
    # infla residual, funil e todas as contagens sem erro nenhum. Falhar alto e barato.
    return df.merge(cres, left_on="_cod6", right_on="cod6", how="left", validate="m:1").drop(
        columns=["_cod6", "cod6", "cres_chave_nome"], errors="ignore"
    )


@functools.lru_cache(maxsize=1)
def carregar_crescimento() -> pd.DataFrame | None:
    """Crescimento do municipio. READ-ONLY e OPCIONAL.

    Camada de CONTEXTO: so repassa o que o projeto Crescimento Regional TEC ja
    apura — tendencia do emprego formal (CAGED, ate 2026-06), variacao do emprego
    e saldo de empresas da Receita Federal. Nao ha score novo, nao ha predicao e
    nao ha ranking de oportunidade: isso fica para o projeto de detalhamento.

    Broadcast municipal por construcao: todos os hexes da cidade recebem o mesmo
    valor, porque a pergunta e sobre a CIDADE.

    O artefato tem uma coluna `cres_ramp` (tendencia mapeada para o centro de uma
    faixa de RESIDUAL_SCORE_BANDS) que NAO e' carregada: a camada 4 nao usa a rampa
    de score, colore por classe categorica. Ela fica no parquet, fora de
    `_COLS_CRESCIMENTO`, e nao chega ao payload.
    """
    if not CRESCIMENTO_PATH.exists():
        return None
    # Projecao explicita: o artefato tem 31 colunas e o piloto consome 13. Ler tudo
    # e carregar dim_*/pos_* que ninguem le, em memoria residente por UF cacheada.
    import pyarrow.parquet as pq

    disponiveis = set(pq.read_schema(CRESCIMENTO_PATH).names)
    cols = [c for c in _COLS_CRESCIMENTO if c in disponiveis]
    df = pd.read_parquet(CRESCIMENTO_PATH, columns=cols)
    df["cod6"] = df["cod6"].astype(str).str.zfill(6)
    return df


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

    # PROTOTIPO (chave de raio): anexa o modelo de 1 km por AREA ao lado do de 2 km, sem
    # tocar nenhuma coluna existente. Degrada em silencio se o parquet de concorrentes
    # nao estiver montado — o front nao recebe os campos e a chave nem aparece.
    # Ver web/server/pressao_1km.py.
    if pressao_1km.disponivel(CONCORRENTES_PATH):
        try:
            out = pressao_1km.anexar(out, CONCORRENTES_PATH)
        except Exception:  # pragma: no cover - experimento nao pode derrubar o piloto
            pass

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


# O artefato guarda o identificador sem acento (regra do projeto); a tela mostra
# texto acentuado. Sem o mapa, o tooltip exibia "Estavel" tres linhas acima de
# "Estável" (que vem de cres_hex_classe), no mesmo balao.
_ROTULO_TEND = {"Estavel": "Estável", "Em alta": "Em alta", "Em queda": "Em queda"}
# Mesma regra para a classe do hexagono, que ate o BLK-TRAJ-01 vinha ACENTUADA do
# parquet e era comparada por literal no `colors.ts` — regerar o artefato com
# normalizacao ASCII pintaria o mapa inteiro de cinza, sem erro e sem teste vermelho.
# Agora o bruto e ASCII e a traducao mora aqui; o front passa a casar o ROTULO que a
# API envia, igual ja faz com `FAIXA_LABELS`. `tests/unit/test_paridade_classe_
# crescimento_web.py` trava os dois lados.
_ROTULO_CLASSE = {
    "Em alta": "Em alta",
    "Estavel": "Estável",
    "Sem obra nova": "Sem obra nova",
}


def _texto(v: Any) -> str | None:
    """str JSON-safe. None/NaN/pd.NA/vazio viram None.

    Necessario porque um merge how="left" que nao casa devolve NaN (float) numa
    coluna de texto, e NaN quebra o JSON.parse do cliente.
    """
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    s = str(v).strip()
    return s or None


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
# Cadastro AMPLO das unidades Ultra (169 linhas em 2026-08-07, com `uf`/`cidade`/
# `flag_coord_valida`). O `ULTRA_PERF_PARQUET` acima so tem as 54 unidades da planilha
# GeoFusion e esta congelado desde 2026-06-29; este cadastro cobre a rede atual e serve
# para COMPLETAR as coordenadas da Visao Executiva (ver `_ultra_coord_map`) e para os
# pins do Mapa Territorial (ver `_ultra_pontos_mapa`). READ-ONLY, como todo o resto.
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


@functools.lru_cache(maxsize=1)
def _ultra_pontos_mapa() -> pd.DataFrame:
    """Pontos Ultra dos PINS do mapa: a curada COMPLETADA pelo cadastro amplo.

    Vive separada de `_carregar_ultra_pontos` de propósito, e não por estilo. Aquela
    alimenta o dict `curada` de `_ultra_coord_map`, onde a precedência é entre FONTES:
    unir o cadastro lá faria um acerto do cadastro (que é cego a UF no terceiro
    fallback) ganhar de um acerto da curada — foi exatamente assim que `TAUBATE` foi
    parar na Grande SP. Aqui não há precedência de fonte a preservar, só a união dos
    pontos que existem, então a mistura é segura.

    Antes desta função o mapa desenhava apenas as 54 linhas da planilha GeoFusion,
    congelada em 2026-06-29: a rede aberta depois disso (Duque de Caxias, as Ceilândias,
    Capim Macio…) simplesmente não existia para o Mapa Territorial, mesmo estando no
    cadastro com coordenada válida.

    A curada vence por chave normalizada: onde as duas bases têm a mesma unidade, o
    ponto exibido continua sendo o que o mapa já mostrava.
    """
    cols = ["nome", "lat", "lng"]
    curada = _carregar_ultra_pontos()
    extra = _carregar_ultra_mapeadas()
    if len(extra) and len(curada):
        vistas = {_chave_unidade(n) for n in curada["nome"]}
        extra = extra[~extra["nome"].map(_chave_unidade).isin(vistas)]
    partes = [d[cols] for d in (curada, extra) if len(d)]
    if not partes:
        return pd.DataFrame(columns=cols)
    df = pd.concat(partes, ignore_index=True) if len(partes) > 1 else partes[0]
    df = df.dropna(subset=["lat", "lng"]).drop_duplicates(subset=["lat", "lng"])
    return df[cols].reset_index(drop=True)


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

    ultra = _ultra_pontos_mapa()
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

    O ultimo passo continua com vocabulario de FILA, nao de intensidade: ali a leitura e
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
        if n <= CONC_ADENSAR_MAX:
            # "gray" e nao "blue": azul e' a identidade da camada 1 (potencial
            # censitario) e o chip "Quente"/"Polo" de la'. O mesmo pill azul
            # significando "score altissimo" no passo 1 e "tem 1-2 concorrentes"
            # no passo 3 era leitura dupla de escalas sem relacao.
            return "Adensar", "gray", None
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
    limite: int = FILA_MAX,
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

    RAIO, NAO HEXAGONO: o texto dizia "concorrente dentro do hexagono", e isso nao e'
    o que a coluna mede. `n_concorrentes_est` deriva de `oferta_efetiva_mapeada_2km`
    (`calcular_colunas_mercado`), que soma os concorrentes ate 2 km ponderados por
    distancia — o proprio cabecalho do passo ja exibe "conc. 2 km". Um concorrente a
    1,8 km do centroide conta aqui e nao esta "dentro do hexagono", entao a redacao
    antiga fazia o usuario procurar no lugar errado.
    """
    if n_residual == 0:
        return (
            "Nenhuma região chegou com residual até aqui, então não há pressão "
            "concorrencial a avaliar neste recorte."
        )
    if n_white == 0:
        return (
            f"Dessas {_fmt(n_residual)}, quais estão desguarnecidas? Nenhuma: todas já "
            "têm concorrente mapeado num raio de 2 km. Não há área sem concorrência "
            "neste recorte — por isso a lista abaixo fica vazia. Entrar aqui significa "
            "disputar espaço, protegendo o corredor Ultra."
        )
    verbo = "não tem" if n_white == 1 else "não têm"
    return (
        f"Dessas {_fmt(n_residual)}, quais estão desguarnecidas? {_fmt(n_white)} {verbo} "
        "nenhum concorrente mapeado num raio de 2 km; as demais exigem entrar "
        "protegendo o corredor Ultra contra a concorrência."
    )

def _mun_val(df_muni: pd.DataFrame, col: str) -> Any:
    """Valor municipal (broadcast): basta a 1a linha nao nula."""
    if col not in df_muni.columns or df_muni.empty:
        return None
    s = df_muni[col].dropna()
    return s.iloc[0] if len(s) else None


def _narrativa_crescimento(df_muni: pd.DataFrame, municipio: str) -> str:
    """Passo 4. Como a cidade esta indo.

    So repassa o que o projeto Crescimento Regional TEC ja apura: a tendencia do
    emprego formal (CAGED, defasagem ~3 meses) e o saldo de empresas da Receita.

    O `v_frase` E' uma recomendacao — chega a dizer "vale ficar de olho, nao abrir
    agora" — e chamar tudo isto de "contexto, nao recomendacao" escondia isso. A
    distincao que vale e de NIVEL, nao de natureza: o veredito e' sobre a PRACA
    (esta cidade merece atencao?) e nao escolhe nem ordena PONTO — quem faz isso e' o
    passo 5, pelo residual, sem olhar para o crescimento. Nada aqui promete
    desempenho de unidade.
    """
    tend = _mun_val(df_muni, "cres_tendencia")
    conf = _mun_val(df_muni, "cres_confiab")
    veredito = _mun_val(df_muni, "v_frase")
    # `cres_tendencia` e nula de proposito onde a confiabilidade e muito baixa
    # (2.182 de 5.571 municipios), mas `v_frase` existe em TODOS. Testar a tendencia
    # primeiro escondia o veredito em 39% do pais — inclusive onde o painel mais
    # precisa dele. So cai no "sem leitura" quando as DUAS faltam.
    if tend is None and not veredito:
        motivo = (
            " — o município tem vínculos formais de menos para a medição se sustentar"
            if conf
            else ""
        )
        return (
            f"Sem leitura de crescimento para {municipio}{motivo}. "
            "As áreas sem concorrência seguem valendo."
        )
    emp = _mun_val(df_muni, "cres_emp_pct")
    med = _mun_val(df_muni, "cres_uf_mediana")
    uf = _mun_val(df_muni, "uf")
    setor = _mun_val(df_muni, "cres_setor")
    sal = _mun_val(df_muni, "cres_salario")
    sal_var = _mun_val(df_muni, "cres_salario_var")

    # O VEREDITO vem primeiro: e a leitura de decisao, e o resto e o que a sustenta.
    if veredito:
        detalhe = []
        if setor:
            detalhe.append(f"A abertura de empresas aqui é puxada por {str(setor).lower()}")
        if sal is not None:
            t = f"quem é admitido entra ganhando R$ {_fmt(int(sal))}"
            if sal_var is not None:
                t += f" ({sal_var:+.1f}% no ano)"
            detalhe.append(t)
        cauda = (" " + ", ".join(detalhe) + ".") if detalhe else ""
        aviso = ""
        if conf and str(conf) in ("baixa", "muito_baixa"):
            aviso = " Confiabilidade baixa: poucos vínculos formais no município."
        return f"{veredito}{cauda} CAGED, RAIS, Receita Federal e satélite.{aviso}"

    # Passa pelo MESMO mapa do tooltip. Antes havia um `.replace("estavel", ...)`
    # ad-hoc aqui: dois dialetos para a mesma coluna, e so um deles saberia de um
    # rotulo novo.
    tend_txt = _ROTULO_TEND.get(str(tend), str(tend)).lower()
    partes = [f"O emprego formal em {municipio} está {tend_txt}"]
    if emp is not None:
        partes[0] += f": variou {emp:+.1f}% desde dez/2022"
        # Numero sozinho nao tem escala. A mediana da UF da a referencia em uma linha.
        if med is not None:
            comp = "acima" if emp > med else "abaixo" if emp < med else "na"
            partes[0] += f", {comp} da mediana de {uf or 'estado'} ({med:+.1f}%)"
    partes[0] += "."
    if setor:
        partes.append(f"O que mais puxa a abertura de empresas aqui é {str(setor).lower()}.")
    if sal is not None:
        frase = f"Quem é admitido entra ganhando R$ {_fmt(int(sal))}"
        if sal_var is not None:
            frase += f", {sal_var:+.1f}% em relação ao ano anterior"
        partes.append(frase + ".")
    partes.append("CAGED e Receita Federal, até junho de 2026 — contexto sobre a praça.")
    if conf and str(conf) in ("baixa", "muito_baixa"):
        partes.append("Confiabilidade baixa: poucos vínculos formais no município.")
    return " ".join(partes)


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
        quentes = df_muni[(df_muni[col_censo] >= SCORE_CORTE_QUENTE) & (pop >= POP_MIN_ACIONAVEL)]
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

    # Passo 4 — as areas do passo 3 que TEM leitura de satelite. A cobertura e parcial
    # (41.135 hexes em 12 UFs, so na mancha urbana medida), e o numerao do passo antes
    # contava os hexes medidos do MUNICIPIO INTEIRO enquanto o mapa acendia o white:
    # com 60 medidos e 44 white, a caixa lia "60 de 60" e o mapa acendia 44. Nenhum dos
    # dois conjuntos continha o outro. Toda a convencao do funil e `funil_big` contar
    # exatamente o que `hexes` acende — este era o unico passo que a violava.
    medidos = (
        white[white["cres_hex_classe"].notna()]
        if "cres_hex_classe" in white.columns
        else white.iloc[0:0]
    )

    # Passo 5 — Recomendacao: fila de ate FILA_MAX aberturas priorizada por residual,
    # so com white space. A fila e 100% viavel; encurta sozinha com menos candidatos e
    # fica vazia quando nao ha nenhum (o `if` so protege o df sem a coluna).
    # SEM fallback para o residual disputado (decisao do dono, 2026-08-03, PR #184):
    # nao se reverte isso em silencio na resolucao de um conflito.
    fila = white.nlargest(FILA_MAX, "oferta_efetiva_disponivel") if len(white) else white

    # O tom passado a `_rank_items` e' o tom PADRAO do passo, e hoje ele NAO PINTA
    # em lugar nenhum: `RankItem.tag_cor` (a cor exata da faixa da legenda) tem
    # precedencia no `Chip` do front, e vem preenchido em todos os passos que
    # rotulam por faixa. Ja' tentei trocar estes toms por cores de camada
    # (teal/violet) neste PR: 121 itens saiam com o tom novo e ZERO chegavam ao
    # pixel. Identidade de camada no piloto vive no stepper, no cabecalho do painel
    # e no rotulo do mapa — nao no chip do item.
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
            "mode": "crescimento",
            "titulo": "Como a cidade está indo",
            "narrativa": _narrativa_crescimento(df_muni, municipio),
            # A caixa do funil e "N filtrados de M" em todos os passos. Um percentual
            # ali dentro virava "21 % de emprego formal filtrados de 0 areas", que nao
            # significa nada — e o `or 0` ainda afirmava "0%" quando o dado faltava.
            # Aqui a contagem e o `medidos`: as MESMAS areas que o mapa acende. A
            # variacao % segue na narrativa e no Detalhes, onde tem contexto.
            "funil_big": len(medidos),
            "funil_unit": _unidade(
                len(medidos), "área com medição de satélite", "áreas com medição de satélite"
            ),
            "funil_from": f"{_fmt(len(white))} áreas sem concorrência",
            "metrica": "crescimento",
            # Sem lista propria: o passo 5 ja rankeia os mesmos hexes pela mesma
            # coluna (a lista saia identica, so mudando a etiqueta). A leitura deste
            # passo e municipal e vive na narrativa; o mapa carrega o resto.
            "itens": [],
            "dims": _texto(_mun_val(df_muni, "cres_dims")),
            "series": _texto(_mun_val(df_muni, "cres_series")),
            "hexes": medidos["hex_id"].tolist(),
        },
        {
            "n": 5,
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
        if v >= FAIXA_HEXES_POLO:
            return "Polo", "blue"
        if v >= FAIXA_HEXES_FORTE:
            return "Forte", "green"
        return "Emergente", "gray"
    # residual (soma municipal — patamares maiores que o de 1 hex)
    if v >= FAIXA_RESIDUAL_ALTA_UF:
        return "Alta", "green"
    if v >= FAIXA_RESIDUAL_MEDIA_UF:
        return "Média", "amber"
    return "Baixa", "gray"


def _etiqueta_crescimento(valor: float | None, mediana: float | None) -> tuple[str, str | None]:
    """Chip do ranking do passo 4: POSICAO RELATIVA ao estado, nao nota absoluta.

    O ramo anterior cortava a variacao do emprego em patamares fixos (>=15 "Em alta",
    >=2 "Estável", senao "Em queda") e tinha tres defeitos que se resolvem juntos aqui:

    1. VOCABULARIO COLIDIDO. "Em alta"/"Estável" sao as MESMAS palavras de
       `cres_hex_classe`, que pinta o mapa desta mesma camada — so que o chip mede
       emprego formal (CAGED, municipal) e o mapa mede area construida (satelite, por
       hexagono). Uma cidade podia sair com chip verde "Em alta" e ter todos os
       hexagonos cinza "Sem obra nova". Pior: o chip emitia "Em queda", que nao existe
       em legenda nenhuma.
    2. CHIP CONSTANTE. A lista JA e o top-10 da UF, entao um corte nacional nunca varia
       dentro dela: simulado sobre a distribuicao nacional (p50 +6,4 | p90 +19,4), o
       corte de 15% dava 10 "Em alta" de 10 em UFs de 50, 100, 300 e 645 municipios.
    3. VERMELHO EM CIDADE QUE CRESCEU. "Estável" comecava em +2%, entao +1,0% recebia
       chip vermelho "Em queda" — cerca de 7% dos municipios do pais.

    A regua passa a ser `cres_uf_mediana`, que ja vinha no artefato e ja servia de
    escala na narrativa municipal ("acima da mediana de SP"). Medido no artefato
    vigente: a mediana por UF vai de +2,8% a +12,7% e nunca chega perto de zero, entao
    a razao e estavel. O ramo por pontos percentuais fica so como defesa, para o dia em
    que um recorte novo quebre isso — sem ele, "10x a mediana" elogiaria um municipio
    que cresceu 5% num estado parado.
    """
    if valor is None:
        return "", None
    # Queda de verdade e a unica leitura ABSOLUTA que sobrevive: perder vinculo formal
    # e ruim em qualquer estado. O rotulo nomeia a metrica ("emprego") justamente para
    # nao ser lido como a classe do hexagono.
    if valor < 0:
        return "emprego em queda", "red"
    if mediana is None or mediana < _CRESC_PISO_MEDIANA:
        d = valor - (mediana or 0.0)
        if d >= 10:
            return "muito acima do estado", "green"
        if d >= 2:
            return "acima do estado", "green"
        if d >= -2:
            return "na média do estado", "gray"
        return "abaixo do estado", "amber"
    r = valor / mediana
    if r >= 2:
        return f"{r:.0f}× a mediana do estado", "green"
    if r >= 1.2:
        return "acima da mediana do estado", "green"
    if r >= 0.8:
        return "na mediana do estado", "gray"
    return "abaixo da mediana do estado", "amber"


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
        # `_numf` e nao `_num`: arredondar antes de escolher a faixa faz 79,6 virar 80 e
        # o municipio mudar de faixa na borda, discordando do hexagono no mapa.
        nome, _tom, cor = _faixa_para_chip(_numf(valor), faixas)
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
    if modo == "count":
        serie = g.size()
    elif modo == "crescimento":
        # Metrica MUNICIPAL (broadcast): somar entre hexes daria numero sem sentido.
        serie = g[value_col].max()
    else:
        serie = g[value_col].sum()
    # O `serie > 0` nasceu para matar municipio-fantasma do Categorical no modo
    # `count`. No modo `crescimento` o valor e variacao de emprego e PODE ser
    # negativa (1.035 de 5.567 municipios): o filtro escondia exatamente as cidades
    # que estao indo mal, num passo chamado "Como as cidades estao indo".
    serie = serie.dropna() if modo == "crescimento" else serie[serie > 0]
    serie = serie.sort_values(ascending=False).head(FILA_MAX)
    # Ancora so' dos que entram no painel (evita ordenar a UF inteira).
    ancoras = _hex_representativo(
        df[df["nome_municipio"].isin(list(serie.index))], value_col if modo != "count" else None
    )
    melhor = _melhor_faixa_por_municipio(df, faixa_por) if faixa_por else {}
    # Regua do chip de crescimento. `cres_uf_mediana` e constante na UF inteira (o
    # artefato a calcula por estado), entao uma leitura basta para todo o ranking.
    ref_uf = _numf(_mun_val(df, "cres_uf_mediana")) if modo == "crescimento" else None
    # Detalhe POR MUNICIPIO. Na visao de UF o painel mostrava sempre o mesmo bloco
    # (o do primeiro hex servido, que e o da capital) enquanto a lista rankeava
    # outras cidades — o leitor via numero de Sao Paulo com o nome de Osasco.
    # Montado DEPOIS do head() e so no passo que usa: um groupby sobre os 47 mil
    # hexes de SP custava 543 ms contra 8 ms, em cinco chamadas por requisicao.
    det: dict[str, dict[str, Any]] = {}
    if modo == "crescimento" and {"cres_dims", "cres_series"} & set(df.columns):
        top = df[df["nome_municipio"].isin(list(serie.index))]
        for muni, bloco in top.groupby("nome_municipio", observed=True):
            item: dict[str, Any] = {}
            for col, chave in (("cres_dims", "dims"), ("cres_series", "series")):
                if col in bloco.columns:
                    vals = bloco[col].dropna()
                    if len(vals):
                        item[chave] = str(vals.iloc[0])
            if item:
                det[str(muni)] = item
    itens: list[dict[str, Any]] = []
    for i, (muni, val) in enumerate(serie.items(), 1):
        valor = _num(val)
        if faixa_por:
            etiqueta, cor_item = melhor.get(str(muni), ("", None))
            tom_item = None
        elif modo == "crescimento":
            # Valor CRU na regua, nao o `valor` ja arredondado que vai para a tela.
            etiqueta, tom_item = _etiqueta_crescimento(_numf(val), ref_uf)
            cor_item = None
        else:
            etiqueta, tom_item = _etiqueta_muni(modo, valor, i, fila)
            cor_item = None
        d = det.get(str(muni), {})
        itens.append(
            {
                "rank": i,
                "hex_id": ancoras.get(str(muni), ""),
                "municipio": str(muni),
                "titulo": str(muni),
                "sub": None,
                "dims": d.get("dims"),
                "series": d.get("series"),
                "valor": valor,
                "label": label,
                "tag": etiqueta,
                "tom": tom_item or tom,
                "tag_cor": cor_item,
            }
        )
    return itens


def montar_crescimento_estado(df_uf: pd.DataFrame) -> dict[str, Any] | None:
    """Ranking de crescimento sobre a UF INTEIRA — não sobre o white space.

    POR QUE NÃO É REUSO DO PASSO 4. O passo 4 do funil descreve as cidades que
    SOBREVIVERAM aos passos 1-3: `cres_uf = white[...]` (ver `montar_funil_uf`), e o
    comentário lá diz por escrito que ele "não é o estado inteiro". Ler aquele ranking
    como retrato do estado é o erro fácil: numa UF onde quase tudo tem concorrente, o
    passo 4 lista meia dúzia de cidades e some com o resto.

    Aqui a base é `df_uf` cru. É o único bloco do payload que fala do estado todo, e
    por isso mora FORA da lista de passos — para ninguém confundi-lo com uma camada
    do funil.

    CAGED SÓ CONTRA MARGEM ESTADUAL. `cres_emp_pct` sozinho não diz nada: 8,7% é muito
    ou pouco conforme o estado e o ano. `_rank_municipios(modo="crescimento")` já
    etiqueta cada cidade contra `cres_uf_mediana`, que é constante na UF — e a mediana
    viaja no payload para a tela poder dizer contra o que está comparando.

    READ-ONLY: agrega coluna já servida, não recalcula nada.
    """
    if "cres_emp_pct" not in df_uf.columns:
        return None
    com_medicao = df_uf[df_uf["cres_emp_pct"].notna()]
    if com_medicao.empty:
        return None

    # PISO DE POPULAÇÃO, e declarado. Sem ele o ranking é dominado por município
    # minúsculo: medido em GO, o topo saía "Santa Terezinha de Goiás, 211% — 28x a
    # mediana do estado", que é crescimento percentual sobre uma base de poucas
    # centenas de empregos. O número não é falso, mas ranquear por ele põe ruído no
    # lugar de sinal. O piso é o `POP_MIN_ACIONAVEL` que o funil já usa, e não um
    # corte novo inventado aqui; quantos municípios ele tirou viaja no payload.
    col_pop = "pop_total_setor_2022"
    acionaveis = com_medicao
    n_fora_do_piso = 0
    if col_pop in com_medicao.columns:
        pop_por_muni = com_medicao.groupby("nome_municipio", observed=True)[col_pop].sum()
        grandes = set(pop_por_muni[pop_por_muni >= POP_MIN_ACIONAVEL].index)
        n_fora_do_piso = int(com_medicao["nome_municipio"].nunique() - len(grandes))
        if grandes:
            acionaveis = com_medicao[com_medicao["nome_municipio"].isin(grandes)]

    return {
        "mediana_uf": _num(_mun_val(df_uf, "cres_uf_mediana"), 1),
        # Municípios do estado COM medição de emprego — o denominador honesto do
        # "N de M": sem ele a tela sugeriria cobertura total.
        "n_municipios_com_medicao": int(com_medicao["nome_municipio"].nunique()),
        "n_municipios_uf": int(df_uf["nome_municipio"].nunique()),
        "pop_minima": POP_MIN_ACIONAVEL,
        "n_fora_do_piso": n_fora_do_piso,
        "itens": _rank_municipios(
            acionaveis, "cres_emp_pct", "crescimento", "% emprego", "green"
        ),
    }


def montar_funil_uf(df_uf: pd.DataFrame, uf: str) -> list[dict[str, Any]]:
    """Os 4 passos no nível da UF inteira; o ranking recomenda MUNICÍPIOS."""
    total = len(df_uf)
    n_munis = int(df_uf["nome_municipio"].nunique()) if "nome_municipio" in df_uf.columns else 0

    col = "score_setor_2022_calibrado"
    if col in df_uf.columns:
        pop = df_uf["pop_leitura"] if "pop_leitura" in df_uf.columns else float("nan")
        quentes = df_uf[(df_uf[col] >= SCORE_CORTE_QUENTE) & (pop >= POP_MIN_ACIONAVEL)]
    else:
        quentes = df_uf.iloc[0:0]

    residual = (
        quentes[quentes["oferta_efetiva_disponivel"] >= OFERTA_DESTAQUE_MIN]
        if "oferta_efetiva_disponivel" in quentes.columns
        else quentes.iloc[0:0]
    )
    alunos_res = _num(residual["oferta_efetiva_disponivel"].sum()) if len(residual) else 0
    white = residual[residual["n_concorrentes_est"] == 0] if len(residual) else residual
    # Presenca de VALOR, nao de coluna: o artefato pode existir e o join nao casar
    # (o fallback por nome e o caminho principal em 21 das 27 UFs), e nesse caso a
    # coluna chega cheia de NaN — a prosa afirmava CAGED ao lado de 0 cidades.
    tem_cres = "cres_emp_pct" in white.columns and bool(white["cres_emp_pct"].notna().any())
    # Passo 4 — as areas do passo 3 cujas CIDADES tem leitura de crescimento. O numerao
    # antes contava cidades com emprego >= 15% enquanto o mapa acendia todo o white,
    # inclusive as cidades estaveis e em queda: pelos percentis nacionais o corte cai
    # entre a mediana e o p90, entao tipicamente 80-85% do que estava aceso ficava fora
    # da conta — e o numero podia ser 0 com a camada inteira acesa. Sem contar que
    # contava CIDADES e o `funil_from` dizia AREAS. O passo nao filtra: quem nao tem
    # leitura simplesmente nao e descrito, e segue inteiro para a fila do passo 5.
    cres_uf = white[white["cres_emp_pct"].notna()] if tem_cres else white.iloc[0:0]
    n_cidades_cres = int(cres_uf["nome_municipio"].nunique()) if len(cres_uf) else 0
    n_cidades_white = int(white["nome_municipio"].nunique()) if len(white) else 0
    # Base dos passos 3, 4 e 5: SOMENTE o white space, igual ao funil municipal
    # (decisao do dono, 2026-08-03). Sem hexagono livre a UF inteira sai com esses
    # passos vazios — e isso e o certo: o numerao ja diz 0 e o mapa nao acende nada;
    # ranquear o residual ali fazia o painel prometer municipios que o passo acabara
    # de excluir. O passo 4 (crescimento) le a MESMA base: ele descreve as cidades que
    # chegaram ate aqui, nao o estado inteiro — senao falaria de praca ja descartada.
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
            "mode": "crescimento",
            "titulo": "Como as cidades estão indo",
            # Condicionada a mesma checagem do funil_big e dos itens logo abaixo:
            # sem o artefato, a prosa afirmava CAGED e Receita ao lado de um passo
            # com numero 0 e lista vazia.
            "narrativa": (
                (
                    "Uma leitura sobre a praça, não sobre o ponto: como anda o emprego "
                    "formal de cada cidade, medido pelo CAGED com defasagem de cerca de três "
                    "meses, e quantas empresas a mais do que fechou cada uma abriu segundo a "
                    "Receita Federal. É o dado mais recente da pilha — vai até junho de 2026, "
                    "enquanto o censo é de 2022. Quem escolhe e ordena o ponto é a camada "
                    "seguinte, pelo residual — esta aqui não entra nessa conta."
                )
                if tem_cres
                else (
                    "Sem leitura de crescimento para este estado — o artefato municipal não "
                    "está disponível. As áreas sem concorrência seguem valendo."
                )
            ),
            "funil_big": n_cidades_cres,
            "funil_unit": _unidade(
                n_cidades_cres, "cidade com leitura", "cidades com leitura"
            ),
            "funil_from": f"{_fmt(n_cidades_white)} cidades sem concorrência",
            "metrica": "% emprego",
            "itens": (
                _rank_municipios(cres_uf, "cres_emp_pct", "crescimento", "% emprego", "green")
                if tem_cres
                else []
            ),
            "hexes": (cres_uf["hex_id"].tolist() if len(cres_uf) else []),
        },
        {
            "n": 5,
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
        # PROTOTIPO da chave de raio. `conc1k` = quantas concorrentes ALCANCAM este hex
        # pelo disco de 1 km (e o que colore o mapa no modo novo); `oferta1k` = o residual
        # sob esse modelo. Ausentes quando o parquet de concorrentes nao esta montado —
        # o front so' mostra a chave se os dois vierem.
        "conc1k": (
            int(r.get("n_concorrentes_influencia_1km"))
            if r.get("n_concorrentes_influencia_1km") is not None
            else None
        ),
        "oferta1k": _num(r.get("oferta_efetiva_disponivel_1km")),
        # Alunos que ESTE hexagono perde para as concorrentes sob o rateio por area.
        # E o numero que deixa o split visivel na tela.
        "cons1k": _num(r.get("consumo_concorrentes_1km")),
        "cons2k": _num(r.get("oferta_consumida_mercado_estimada")),
        # Chave para o bloco municipal do passo 4 (`cres_mun` na raiz do payload).
        # Antes os seis campos MUNICIPAIS do crescimento viajavam repetidos em cada
        # hexagono — o mesmo erro que ja tinha sido corrigido para `cres_dims`/
        # `cres_series`, so que com a desculpa de serem "curtos o bastante". Nao eram.
        # Medido em /api/uf: SP 6,58 -> 4,71 MB e RJ 3,62 -> 2,61 MB (-28% nos dois),
        # trocando 15.000 copias por 163 cidades (21 KB). O hex carrega so o nome.
        "mun": _texto(r.get("nome_municipio")),
        # Taxa de crescimento DESTE hexagono — e o que colore o mapa.
        "cres_hex_taxa": _num(r.get("cres_hex_taxa"), 1),
        "cres_hex_classe": _ROTULO_CLASSE.get(str(r.get("cres_hex_classe") or ""))
        or _texto(r.get("cres_hex_classe")),
    }


def _bloco_municipal(vis: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Leitura de crescimento do passo 4, UMA vez por cidade em vez de por hexagono.

    Sao todos broadcast municipal por construcao — `_juntar_crescimento` faz o merge
    com `validate="m:1"`, entao N hexes recebem a MESMA linha. O consumidor tambem e um
    so: o tooltip do `HexMap`, que le pelo nome do municipio (`Hex.mun`).

    `cres_uf_mediana` e ainda mais grosso: e um numero por ESTADO, que viajava repetido
    em todos os 15.000 hexes de /api/uf. Fica aqui junto porque o tooltip mostra os dois
    lado a lado ("variou +8,8% / mediana do estado +6,0%") e separa-los custaria uma
    segunda chave para nada.
    """
    cols = {
        "cres_tendencia",
        "cres_emp_pct",
        "cres_saldo_empresas",
        "cres_salario",
        "cres_setor",
        "cres_uf_mediana",
    }
    if "nome_municipio" not in vis.columns or not (cols & set(vis.columns)):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for muni, bloco in vis.groupby("nome_municipio", observed=True):
        r = bloco.iloc[0]
        item = {
            "tend": _ROTULO_TEND.get(str(r.get("cres_tendencia") or ""))
            or _texto(r.get("cres_tendencia")),
            "emp": _num(r.get("cres_emp_pct"), 1),
            "empresas": _num(r.get("cres_saldo_empresas")),
            "salario": _num(r.get("cres_salario")),
            "setor": _texto(r.get("cres_setor")),
            "uf_mediana": _num(r.get("cres_uf_mediana"), 1),
        }
        # Cidade sem NENHUMA leitura nao entra: o dict e' esparso de proposito, e o
        # tooltip ja sabe lidar com a ausencia (a secao inteira some).
        if any(v is not None for v in item.values()):
            out[str(muni)] = item
    return out


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
    milhares de concorrentes. Os concorrentes aparecem no drill-down do município.

    O protótipo do raio de 1 km chegou a trazer os concorrentes também para a UF, para
    que a chave tivesse bandeirinha visível já no overview. Isso ficou FORA deste PR de
    propósito: reverteria uma decisão de produto da `main` e o teto `COMPETITOR_PIN_LIMIT`
    cortaria em silêncio numa UF grande, mentindo sobre a densidade da concorrência. A
    camada de cobertura em si não depende disso — ela vem de `/api/cobertura/{uf}`."""
    ultra = _ultra_pontos_mapa()
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


# Artefatos que o piloto LE mas que nao viajam com o codigo: `.gitignore` corta
# `data/staging/*` e o `.dockerignore` corta `data/` inteiro da imagem. Em producao eles
# so' chegam pelo bind mount de `docker-compose.prod.yml`. Quando faltam, cada leitor
# devolve None e a tela degrada EM SILENCIO — foi assim que o passo 4 ficou vazio no ar
# enquanto funcionava na maquina de quem gerou o artefato, e nada no sistema dizia isso.
# `scripts/check_artifacts.py` responde a mesma pergunta, mas so' sobre um checkout
# local; era o ambiente PUBLICADO que ninguem conseguia auditar sem entrar no VPS.
def _artefatos_observados() -> list[tuple[str, Path, str]]:
    """Monta a lista NA CHAMADA, lendo os globais de caminho — nunca no import.

    Uma lista de modulo congelaria os `Path` no momento do import, e ai o
    `_point_app_at` dos testes (que faz `monkeypatch.setattr` em `ENRICHED_DIR`,
    `CRESCIMENTO_PATH` e `CRESCIMENTO_HEX_PATH`) nao alcancaria o health: com o app
    apontado para um `tmp_path` vazio, ele responderia sobre o disco REAL de quem roda.
    E' a mesma armadilha que o comentario do `_point_app_at` ja registra para as
    constantes calculadas no import — vale igual aqui.
    """
    return [
        ("enriquecido", ENRICHED_DIR, "hexágonos do mapa — sem ele o piloto não abre"),
        (
            "crescimento_municipal",
            CRESCIMENTO_PATH,
            "passo 4: emprego/empresas por cidade (CAGED, Receita)",
        ),
        (
            "crescimento_hex",
            CRESCIMENTO_HEX_PATH,
            "passo 4: cor do mapa por hexágono (satélite 2016-2023)",
        ),
    ]


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Saude do processo + presenca dos artefatos que a tela depende.

    O healthcheck do container so' olha o status HTTP (`curl -fsS`), entao os campos
    novos sao informativos: nada aqui pode derrubar o container. Por isso o `stat` vive
    num try/except — um mount que sumiu no meio do voo devolve `erro`, nao 500.
    """
    artefatos: dict[str, Any] = {}
    for nome, caminho, para_que in _artefatos_observados():
        item: dict[str, Any] = {"para_que": para_que, "caminho": str(caminho)}
        try:
            existe = caminho.exists()
            item["ok"] = existe
            # Diretorio (enriquecido) nao tem tamanho util; so' arquivo reporta MB.
            if existe and caminho.is_file():
                item["mb"] = round(caminho.stat().st_size / (1024 * 1024), 2)
        except OSError as e:  # mount caiu, permissao, disco — nunca derrubar o health
            item["ok"] = False
            item["erro"] = str(e)
        artefatos[nome] = item

    faltando = sorted(n for n, a in artefatos.items() if not a.get("ok"))
    return {
        "status": "ok",
        "data_dir": str(DATA_DIR),
        "data_ok": artefatos["enriquecido"]["ok"],
        "artefatos": artefatos,
        # Lista pronta para o operador ler sem abrir o dict inteiro.
        "artefatos_faltando": faltando,
    }


@app.get("/api/ufs")
def ufs() -> dict[str, Any]:
    return {"ufs": listar_ufs()}


@app.get("/api/me")
def me(
    remote_user: str | None = Header(default=None, alias="Remote-User"),
) -> dict[str, Any]:
    """Quem sou eu + que abas posso usar (controle temporario, ver `acesso.py`).

    A SPA chama uma vez na abertura e esconde as abas fora da lista; quem chamar a
    API por fora ve o mesmo contrato. O bloqueio de verdade e' do middleware — esta
    rota so' informa.
    """
    usuario = acesso.normalizar_usuario(remote_user)
    return {"usuario": usuario, "abas": sorted(acesso.abas_do_usuario(usuario))}


# ============================================================================
# Metodologia — o "manual" do funil do Mapa
# ============================================================================


def _mil(v: float) -> str:
    """Milhar com ponto, do jeito brasileiro. Existe para o texto NAO precisar de
    `.replace(",", ".")` no fim de uma string concatenada — ali o replace pega junto as
    virgulas da PROSA e vira pontuacao errada ("senao, proxy" -> "senao. proxy")."""
    return f"{v:,.0f}".replace(",", ".")


def _fx(
    etiqueta: str, condicao: str, tom: str, escopo: str = "", cor: str | None = None
) -> dict[str, Any]:
    """Uma faixa de etiqueta. `escopo` vazio = vale nos dois funis.

    `cor` e' o HEX EXATO da faixa, e so' as faixas DERIVADAS DA RAMPA o trazem: ali o
    painel promete a cor que o mapa pinta, e a paleta de 5 `tom` nomeados nao cobre as 5
    cores da rampa 1:1 — "Promissor" saia cinza no manual e amarelo no mapa. Ausente nas
    demais, que nao correspondem a cor de hexagono nenhuma.
    """
    saida: dict[str, Any] = {
        "etiqueta": etiqueta,
        "condicao": condicao,
        "tom": tom,
        "escopo": escopo,
    }
    if cor:
        saida["cor"] = cor
    return saida


def _faixas_da_rampa(
    faixas: list[tuple[int, int, str, str, str]], escopo: str, em_alunos: bool = False
) -> list[dict[str, Any]]:
    """Publica as faixas NOMEADAS que o funil de fato aplica, na ordem da legenda.

    DERIVA de `constants.FAIXAS_MAPA_*` em vez de repetir os cortes: e' a mesma lista
    que o `_etiqueta` usa para rotular o item e que a legenda do mapa desenha. Um painel
    de metodologia que descreve regua diferente da que roda e' pior que painel nenhum —
    o usuario passa a confiar num manual errado. (Ate o BLK-MAPA-FAIXAS-01 este painel
    publicava Quente/Forte/Solido e Alta/Media/Baixa, vocabularios ja extintos.)
    """
    from motor_expansao.dashboard.constants import CAPACIDADE_UNIDADE_ALUNOS

    saida: list[dict[str, Any]] = []
    for de, ate, nome, cor, tom in reversed(faixas):
        if em_alunos:
            piso = _mil(de * CAPACIDADE_UNIDADE_ALUNOS / 100)
            teto = _mil(ate * CAPACIDADE_UNIDADE_ALUNOS / 100)
            condicao = f"≥ {piso} alunos" if ate >= 100 else f"{piso} a {teto} alunos"
        else:
            condicao = f"score ≥ {de}" if ate >= 100 else f"score {de} a {ate}"
        # A cor VIAJA JUNTO: esta lista é a que promete ao operador o que o mapa pinta.
        saida.append(_fx(nome, condicao, tom, escopo, cor))
    return saida


def _faixas_potencial() -> list[dict[str, Any]]:
    """Camada 1. No municipio a etiqueta e' do proprio hexagono; na UF, do MELHOR
    hexagono do municipio (`_melhor_faixa_por_municipio`): mesma regua, base diferente."""
    from motor_expansao.dashboard.constants import FAIXAS_MAPA_POTENCIAL

    return _faixas_da_rampa(FAIXAS_MAPA_POTENCIAL, "municipio") + _faixas_da_rampa(
        FAIXAS_MAPA_POTENCIAL, "uf"
    )


def _faixas_residual() -> list[dict[str, Any]]:
    """Camada 2. A ancora aqui e' fisica — score 100 = uma unidade cheia (2.500 alunos) —
    entao a faixa vai publicada em ALUNOS, exatamente como a legenda do mapa mostra."""
    from motor_expansao.dashboard.constants import FAIXAS_MAPA_DEMANDA

    return _faixas_da_rampa(FAIXAS_MAPA_DEMANDA, "municipio", em_alunos=True) + _faixas_da_rampa(
        FAIXAS_MAPA_DEMANDA, "uf", em_alunos=True
    )


def _faixas_competitivas() -> list[dict[str, Any]]:
    """Camada 3. No municipio a etiqueta e' COMPETITIVA (`_etiqueta`, ramo "conc. 2 km");
    na UF a mesma camada rotula pela faixa de demanda do melhor hexagono. Sao bases
    diferentes, e por isso os dois escopos aparecem lado a lado no painel."""
    from motor_expansao.dashboard.constants import FAIXAS_MAPA_DEMANDA

    # Rotulo E tom sao PERGUNTADOS a `_etiqueta` — a mesma funcao que pinta o chip na
    # tela —, nunca reescritos aqui. Enquanto o tom era copiado a mao, mudar a cor do
    # "Adensar" em `_etiqueta` (blue -> gray, para nao colidir com a camada 1) deixava
    # este painel anunciando a cor antiga. O painel existe justamente para NAO haver
    # uma segunda verdade sobre o funil.
    def faixa(n: int, condicao: str) -> dict[str, Any]:
        rotulo, tom, _ = _etiqueta("conc. 2 km", None, 1, pd.Series({"n_concorrentes_est": n}))
        return _fx(rotulo, condicao, tom or "gray", "municipio")

    return [
        faixa(0, "nenhum concorrente mapeado em 2 km"),
        faixa(CONC_ADENSAR_MAX, f"até {CONC_ADENSAR_MAX} concorrentes estimados"),
        faixa(CONC_ADENSAR_MAX + 1, f"mais de {CONC_ADENSAR_MAX} concorrentes estimados"),
    ] + _faixas_da_rampa(FAIXAS_MAPA_DEMANDA, "uf", em_alunos=True)


def _faixas_crescimento() -> list[dict[str, Any]]:
    """Camada 4 — as etiquetas que o RANKING de fato emite, DERIVADAS do proprio chip.

    Esta funcao publicava as quatro classes de `cres_hex_classe` (Em alta / Estável /
    Sem obra nova / Sem medição), que sao a COR DO MAPA, no slot que o front rotula
    "etiquetas do ranking". So que o chip do ranking sai de `_etiqueta_crescimento`,
    com vocabulario totalmente outro (posicao relativa a mediana da UF). A intersecao
    entre publicado e emitido era VAZIA: o usuario lia "Em alta = area construida
    cresceu mais de 30%" ao lado de um item etiquetado "5x a mediana do estado", e
    concluia que o chip media obra por satelite quando ele mede emprego formal.

    Ironia registrada: foi a correcao do proprio chip que abriu o buraco —
    `_etiqueta_crescimento` trocou o vocabulario JUSTAMENTE para fugir da colisao com
    `cres_hex_classe` (defeito 1 do docstring de la), e o painel ficou publicando o
    vocabulario que o chip abandonou.

    Agora as etiquetas sao PRODUZIDAS chamando `_etiqueta_crescimento` num valor
    representativo de cada ramo. Mudar os cortes do chip muda esta lista junto, sem
    ninguem precisar lembrar — que e' a regra escrita em
    `docs/contrato_api_metodologia.md` ("as faixas sao DERIVADAS, nunca escritas a mao").

    ESCOPO `uf`: so a visao de estado ranqueia municipios nesta camada. No funil
    municipal o passo 4 sai com `"itens": []` — nao ha chip para explicar.
    """
    # (valor, mediana, condicao legivel). Um por ramo ALCANCAVEL de
    # `_etiqueta_crescimento`. A ordem aqui e' a de LEITURA, nao a de avaliacao: a
    # funcao testa o caminho de DEFESA (mediana degenerada) antes do caminho por RAZAO,
    # mas o painel abre pelo que o operador ve todo dia — a mediana de 5,0, acima de
    # `_CRESC_PISO_MEDIANA`, exercita a razao; a defesa (mediana 0,5) fecha a lista.
    #
    # O ramo "abaixo do estado" NAO tem amostra porque e' inalcancavel: ele exige
    # d < -2, e o caminho de defesa so roda com mediana < 1,0 tendo ja filtrado
    # valor < 0, logo d > -1,0 sempre. Registrado no BLK-MAPA-CHIP-01 — remover ou
    # reancorar a regua e' decisao de quem a escreveu, nao deste fix.
    amostras: list[tuple[float, float, str]] = [
        (-1.0, 5.0, "o emprego formal encolheu no período"),
        (12.0, 5.0, "cresce o dobro da mediana do estado, ou mais"),
        (7.0, 5.0, "cresce acima da mediana do estado"),
        (5.0, 5.0, "cresce perto da mediana do estado"),
        (2.0, 5.0, "cresce abaixo da mediana do estado"),
        (11.0, 0.5, "estado parado: cresce 10 p.p. ou mais acima da mediana"),
        (3.0, 0.5, "estado parado: cresce acima da mediana"),
        (1.0, 0.5, "estado parado: cresce na média do estado"),
    ]
    saida: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for valor, mediana, condicao in amostras:
        nome, tom = _etiqueta_crescimento(valor, mediana)
        if not nome:
            continue
        # O ramo do multiplicador varia com o dado ("2x", "5x"...). Publicar o exemplo
        # concreto enganaria; `N×` diz a forma sem prometer um numero.
        rotulo = "N× a mediana do estado" if "× a mediana" in nome else nome
        # Dedup pelo ROTULO, nao pelo `nome`: duas amostras que caiam no ramo do
        # multiplicador ("2×" e "5×") sao nomes diferentes e o MESMO rotulo publicado —
        # dedupar por `nome` publicaria a linha duas vezes.
        if rotulo in vistos:
            continue
        vistos.add(rotulo)
        saida.append(_fx(rotulo, condicao, tom or "gray", "uf"))
    return saida


def _legenda_mapa_crescimento() -> list[dict[str, Any]]:
    """As cores do MAPA na camada 4 (`cres_hex_classe`) — outra coisa que a etiqueta.

    Continua publicada, mas fora do slot de ranking: ela explica por que um hexagono
    esta turquesa, verde ou cinza, e vale nos dois escopos (o mapa pinta nos dois).
    Tres estados, nao uma rampa: aqui nao ha nota, ha direcao. Os cortes saem da
    distribuicao real dos hexes medidos (p50 = +19,2%, p75 = +30,6%), e por isso
    "Estável" nao e' um alarme — e' a maioria.

    DERIVA de `_ROTULO_CLASSE`, a mesma traducao que o payload do mapa usa. Escrita a
    mao, esta lista repetiria num campo novo o defeito de que as `faixas` acabaram de
    sair: um vocabulario copiado que ninguem lembra de atualizar. Assim, trocar uma
    classe la estoura com `KeyError` aqui — falha alta, nao deslize silencioso.
    `Sem medição` nao vem do dict porque nao e' classe do artefato: e' a AUSENCIA dela
    (hexagono fora da mancha urbana medida), e por isso mora so' aqui.
    """
    condicao = {
        "Em alta": "área construída cresceu mais de 30% entre 2016 e 2023",
        "Estável": "área construída cresceu, mas abaixo de 30%",
        "Sem obra nova": "área construída parou de crescer no período",
    }
    tom = {"Em alta": "green", "Estável": "blue", "Sem obra nova": "gray"}
    saida = [_fx(r, condicao[r], tom[r]) for r in _ROTULO_CLASSE.values()]
    saida.append(
        _fx("Sem medição", "fora da mancha urbana medida ou fora das 12 UFs", "gray")
    )
    return saida


def _faixas_m1() -> list[dict[str, Any]]:
    """Camada 5: a etiqueta e' a FAIXA DE OPORTUNIDADE do M1 — a mesma que pinta o
    hexagono nesta camada. NAO e' corte de score: o M1 a define cortando o percentil
    nacional. A ordem da fila continua legivel no 1º/2º/3º do proprio item."""
    from motor_expansao.dashboard.constants import FAIXA_LABELS, FAIXA_ORDEM

    tons = {
        "prioridade_maxima": "green",
        "alta": "green",
        "media": "amber",
        "baixa": "gray",
        "descartado": "gray",
        "inviavel": "gray",
    }
    return [
        _fx(FAIXA_LABELS[bruto], "faixa de oportunidade do M1", tons.get(bruto, "gray"))
        for bruto in FAIXA_ORDEM
    ]


def montar_metodologia() -> dict[str, Any]:
    """As camadas do funil explicadas para quem LE a tela, nao para quem escreveu.

    NAO cravar a quantidade aqui: o funil ja' passou de 4 para 5 camadas (entrou
    "Como a cidade esta indo") e o docstring ficou dizendo 4 por um tempo.

    Espelha o `NotasMetodologicas` da Viabilidade e segue a mesma regra: nenhum numero
    e' escrito a mao — todo corte sai da constante que o proprio funil usa, entao
    ajustar um parametro corrige o funil E este texto de uma vez.

    Cada metrica responde duas perguntas, nesta ordem: COM O QUE foi calculada (`fonte`)
    e COMO (`regra`, em portugues corrido — a formula fica no docs/; aqui o leitor
    precisa entender o raciocinio). `ressalva` existe onde o numero tem limite conhecido:
    esconder isso e' o que faz alguem tratar estimativa como contagem.

    NOTA DE ESTILO: os comentarios deste arquivo sao sem acento por convencao do repo,
    mas TUDO que sai daqui e' texto de usuario e vai acentuado.
    """
    cap = _mil(CAPACIDADE_CONCORRENTE_PADRAO)
    pop = _mil(POP_MIN_ACIONAVEL)
    res = _mil(OFERTA_DESTAQUE_MIN)
    score = f"{SCORE_CORTE_QUENTE:.0f}"

    F_CENSO = "Censo 2022 (IBGE)"
    F_CONC = "Mapeamento de concorrentes"
    F_ULTRA = "Base de unidades Ultra"
    F_CRES = "CAGED, RAIS, Receita Federal e satélite"

    return {
        "intro": (
            "O mapa divide o território em hexágonos de cerca de 5 km² — mais ou menos "
            "o tamanho de um bairro grande. Cada camada do funil recebe apenas o que a "
            "anterior aprovou e aplica mais uma régua. A quarta é a exceção declarada: "
            "ela não corta nada e não entra na ordenação — descreve como a cidade vem se "
            "movendo, para separar 'entrar agora' de 'ficar de olho'. No fim sobra uma "
            "fila de aberturas em que toda posição já passou por todos os filtros."
        ),
        "fontes": [
            {
                "nome": F_CENSO,
                "detalhe": (
                    "Renda, domicílios e população por setor censitário — recortes de "
                    "algumas centenas de domicílios cada. É a base de tudo que o funil "
                    "chama de potencial: nenhuma estimativa de demanda é arbitrada, toda "
                    "ela sai do setor onde o hexágono cai."
                ),
            },
            {
                "nome": F_CONC,
                "detalhe": (
                    "Endereços das academias das redes concorrentes monitoradas, "
                    "geocodificados e contados por raio. É o que permite dizer se uma "
                    "região está disputada ou livre."
                ),
            },
            {
                "nome": F_ULTRA,
                "detalhe": (
                    "As unidades próprias e, quando disponível, o número real de alunos de "
                    "cada uma. Entra como oferta já atendida: o funil desconta a própria "
                    "Ultra para não recomendar canibalizar a rede. Sai da base de "
                    "performance das unidades, atualizada por carga — não é leitura ao vivo: "
                    "uma unidade inaugurada depois da última carga ainda não desconta aqui."
                ),
            },
            {
                "nome": F_CRES,
                "detalhe": (
                    "As quatro leituras de movimento do município: emprego formal e salário "
                    "de admissão (CAGED mensal, apoiado no estoque da RAIS), abertura e "
                    "fechamento de empresas (Receita Federal), renda e população (IBGE) e a "
                    "área construída medida por satélite entre 2016 e 2023. Não entra em "
                    "nenhum corte do funil — é o retrato de para onde a cidade vem andando."
                ),
            },
        ],
        "camadas": [
            {
                "n": 1,
                "titulo": "Potencial socioeconômico",
                "pergunta": "Onde mora gente com renda e perfil para treinar?",
                "corte": f"score ≥ {score} e população ≥ {pop}",
                "metricas": [
                    {
                        "nome": "Score socioeconômico",
                        "coluna": "score_setor_2022_calibrado",
                        "fonte": F_CENSO,
                        "resumo": (
                            "Uma nota de 0 a 100 que responde a uma pergunta só: o perfil de "
                            "quem mora aqui se parece com o de quem assina academia? Quanto "
                            "maior, mais perto a região está do público que a rede converte."
                        ),
                        "regra": (
                            "Dois insumos do setor censitário, com pesos fixos: a renda per "
                            "capita, calibrada e comparada em percentil NACIONAL (peso 0,60), "
                            "e a população do setor, comparada dentro do próprio município "
                            "(peso 0,40). A parte de renda usa a mesma régua para o Brasil "
                            "inteiro — é o que permite comparar regiões de estados diferentes; "
                            "a parte de população é relativa à cidade, para não apagar os "
                            "bairros densos de municípios pequenos. A nota do setor passa para "
                            f"o hexágono que o cobre. Abaixo de {score} o hexágono não entra "
                            "em nenhuma camada seguinte."
                        ),
                    },
                    {
                        "nome": "População da área",
                        "coluna": "pop_leitura",
                        "fonte": F_CENSO,
                        "resumo": (
                            "Quantas pessoas moram no hexágono. Uma região pode ter o perfil "
                            "perfeito e ainda assim não sustentar uma unidade, se houver "
                            "pouca gente."
                        ),
                        "regra": (
                            "Soma dos moradores dos setores censitários que caem dentro do "
                            "hexágono, quando esse hexágono tem cruzamento geográfico de boa "
                            "qualidade com a malha do IBGE. Onde o cruzamento não é bom, o "
                            "número vem de um rateio a partir do total do município — menos "
                            "preciso dentro da cidade, e registrado na própria base para quem "
                            f"quiser auditar. O corte em {pop} habitantes é régua operacional "
                            "do time, não do censo: abaixo disso o mapa já pinta a área em "
                            "cinza e o funil descarta."
                        ),
                    },
                ],
                "faixas": _faixas_potencial(),
            },
            {
                "n": 2,
                "titulo": "Demanda não atendida",
                "pergunta": "Desses, onde ainda sobra gente para atender?",
                "corte": f"residual ≥ {res} alunos",
                "metricas": [
                    {
                        "nome": "Residual de alunos",
                        "coluna": "oferta_efetiva_disponivel",
                        "fonte": f"{F_CENSO} + {F_CONC} + {F_ULTRA}",
                        "resumo": (
                            "Quantos alunos cabem na região que hoje ninguém atende. É o "
                            "tamanho da oportunidade medido em PESSOAS — não em porcentagem, "
                            "não em índice."
                        ),
                        "regra": (
                            "São três passos. Primeiro, estima-se quantos moradores do "
                            "hexágono são público de academia, a partir do perfil do censo. "
                            "Depois, desconta-se quem já é atendido: os alunos dos "
                            "concorrentes da região mais os da própria Ultra. O que sobra é o "
                            "residual. Onde a oferta já supera a demanda o resultado é zero, "
                            "nunca negativo — e o mesmo zero aparece, por motivo diferente, em "
                            "hexágono que não passa no filtro de elegibilidade (faixa de "
                            "oportunidade do M1 e população mínima): ali o potencial nem chega "
                            "a ser calculado, então zero significa 'região não avaliada', e "
                            f"não 'região já atendida'. Segue no funil quem tem {res} ou mais."
                        ),
                        "ressalva": (
                            "É uma estimativa de mercado, não uma lista de pessoas. Serve para "
                            "ordenar regiões entre si e dimensionar a oportunidade — não para "
                            "prever a matrícula de uma unidade específica."
                        ),
                    },
                    {
                        "nome": "Oferta já atendida",
                        "coluna": "oferta_consumida_total_estimada",
                        "fonte": f"{F_CONC} + {F_ULTRA}",
                        "resumo": (
                            "Quantos alunos a região já absorve hoje, somando concorrentes e "
                            "unidades Ultra. É exatamente o que se subtrai do potencial."
                        ),
                        "regra": (
                            "Do lado dos concorrentes, o modelo soma a oferta dentro do raio de "
                            "2 km PONDERADA PELA DISTÂNCIA — academia colada no hexágono pesa "
                            "quase inteira, academia perto do limite dos 2 km pesa pouco — e "
                            f"converte esse peso somado em alunos pela capacidade de {cap} por "
                            "unidade cheia. Por isso três concorrentes na vizinhança quase "
                            f"nunca descontam 3 × {cap} alunos: desconta-se o equivalente ao "
                            "quanto eles de fato alcançam esta área. Do lado da Ultra, quando "
                            "existe o número real de alunos da unidade ele é usado no lugar da "
                            "estimativa; quando não existe, vale a mesma média."
                        ),
                    },
                ],
                "faixas": _faixas_residual(),
            },
            {
                "n": 3,
                "titulo": "Pressão concorrencial",
                "pergunta": "Dessas, quais estão desguarnecidas?",
                "corte": "nenhum concorrente estimado num raio de 2 km",
                "metricas": [
                    {
                        "nome": "Concorrentes em 2 km",
                        "coluna": "n_concorrentes_est",
                        "fonte": F_CONC,
                        "resumo": (
                            "Quantas academias concorrentes existem na vizinhança imediata. "
                            "Zero significa que ninguém disputa esse público hoje — a "
                            "situação mais confortável para abrir."
                        ),
                        "regra": (
                            "O modelo mede a oferta concorrente num raio de 2 km do hexágono e "
                            "converte esse volume em número de unidades, dividindo pela "
                            f"capacidade média de {cap} alunos. Só segue para a última camada "
                            "quem tem zero."
                        ),
                        "ressalva": (
                            "É uma estimativa derivada do volume de oferta, não a contagem de "
                            "endereços na rua. E cobre apenas as redes monitoradas: uma "
                            "academia de bairro sem presença digital pode não estar no "
                            "mapeamento — então zero concorrentes quer dizer nenhum "
                            "concorrente CONHECIDO."
                        ),
                    },
                    {
                        "nome": "Capacidade média por academia",
                        "coluna": "capacidade_default_concorrente_alunos",
                        "fonte": "Premissa do modelo",
                        "resumo": (
                            "Quantos alunos o modelo assume que uma academia concorrente "
                            f"atende: {cap}."
                        ),
                        "regra": (
                            "Um número único para todas as redes, escolhido de forma "
                            "conservadora enquanto não há capacidade real por bandeira. É a "
                            "régua que converte oferta em número de concorrentes: subir esse "
                            "valor faz o modelo enxergar MENOS concorrentes; descer faz "
                            "enxergar mais."
                        ),
                    },
                ],
                "faixas": _faixas_competitivas(),
                "nota": (
                    "Esta camada fala dois idiomas, conforme a tela. No mapa de um município, "
                    "a etiqueta é competitiva (Livre / Adensar / Disputa) e responde 'quantos "
                    "concorrentes há aqui'. Na visão do estado, ela mostra a faixa de demanda "
                    "do melhor hexágono do município, igual à camada anterior. O número ao "
                    "lado da etiqueta é sempre o residual, em alunos."
                ),
            },
            {
                "n": 4,
                "titulo": "Como a cidade está indo",
                "pergunta": "Essa praça está ganhando ou perdendo tração?",
                "corte": "nenhum — camada de contexto, não filtra e não reordena",
                "metricas": [
                    {
                        "nome": "Renda, população, empresas, prédios e emprego",
                        "coluna": "cres_dims",
                        "fonte": F_CRES,
                        "resumo": (
                            "Cinco leituras da mesma pergunta, cada uma com o percentil "
                            "nacional ao lado: variação da renda, da população, densidade de "
                            "empresas por mil habitantes, crescimento da área construída e "
                            "variação do emprego formal. O percentil é o que dá escala — "
                            "+8,8% de emprego não diz nada sozinho; 'top 41% do país' diz."
                        ),
                        "regra": (
                            "Cada dimensão vem da sua própria fonte, na janela mais longa que "
                            "a fonte sustenta, e é comparada com todos os municípios do país. "
                            "As séries do gráfico são publicadas em NÍVEL (estoque), não em "
                            "taxa, para que a curva e o número da dimensão contem a mesma "
                            "história."
                        ),
                        "ressalva": (
                            "A população para em 2021 de propósito: o Censo 2022 quebra a "
                            "série das estimativas intercensitárias e misturar as duas bases "
                            "produziria variações que são artefato de recontagem, não "
                            "crescimento. O emprego tem defasagem de cerca de três meses "
                            "(CAGED) e a área construída vai até 2023, o limite do satélite."
                        ),
                    },
                    {
                        "nome": "Crescimento da área construída do hexágono",
                        "coluna": "cres_hex_classe",
                        "fonte": F_CRES,
                        "resumo": (
                            "É o que colore o mapa nesta camada. Mede, dentro do próprio "
                            "hexágono, quanto a área construída cresceu entre 2016 e 2023 — "
                            "a única das cinco leituras que existe abaixo do município."
                        ),
                        "regra": (
                            "Três estados, não uma nota: acima de 30% é 'Em alta', crescimento "
                            "abaixo disso é 'Estável', variação nula ou negativa é 'Sem obra "
                            "nova'. Os cortes saem da distribuição real dos hexágonos medidos."
                        ),
                        "ressalva": (
                            "'Sem obra nova' não é demolição nem decadência: é obra encerrada "
                            "mais ruído de medição — e, numa metrópole densa e madura, é "
                            "SATURAÇÃO. Boa parte de São Paulo aparece assim justamente por já "
                            "estar construída, o que não a torna um mercado pior; a leitura "
                            "aqui é de movimento, não de qualidade. Onde a cidade já é o centro "
                            "consolidado, quem responde pelo potencial são as camadas 1 e 2. "
                            "A cobertura também é parcial — 41.135 hexágonos em 12 UFs, só onde "
                            "há mancha urbana medida; fora disso a leitura é ausente, não é zero."
                        ),
                    },
                ],
                "faixas": _faixas_crescimento(),
                "legenda_mapa": _legenda_mapa_crescimento(),
                "nota": (
                    "Esta camada NÃO é preditiva: nada aqui foi validado como preditor "
                    "de desempenho de unidade, e ela não entra em nenhum corte do funil. "
                    "Ela responde outra pergunta: o M1 mede a POSIÇÃO do território hoje, e "
                    "esta camada mede a DIREÇÃO em que ele vem andando. Duas praças com o "
                    "mesmo score podem estar em rotas opostas, e é só isso que se afirma "
                    "aqui. O hexágono colorido mostra ONDE a cidade cresceu — não onde abrir: "
                    "para isso existe a camada 5, que é a única que ordena a fila."
                ),
            },
            {
                "n": 5,
                "titulo": "Para onde crescer",
                "pergunta": "Em que ordem abrir?",
                "corte": f"as {FILA_MAX} maiores por residual, entre as aprovadas",
                "metricas": [
                    {
                        "nome": "Fila de aberturas",
                        "coluna": "oferta_efetiva_disponivel",
                        "fonte": "Resultado das três camadas anteriores",
                        "resumo": (
                            f"A ordem sugerida para abrir, com até {FILA_MAX} posições. Toda "
                            "posição já passou pelos três filtros — não há candidato inviável "
                            "na fila."
                        ),
                        "regra": (
                            "Entre as regiões que chegaram sem concorrência, ordena-se pelo "
                            "residual: quem tem mais alunos desatendidos vem primeiro. A fila "
                            "sai EXCLUSIVAMENTE dessas áreas livres — não há recurso a região "
                            "disputada. Por isso ela encurta sozinha em cidade pequena, em vez "
                            "de completar com candidato ruim, e fica VAZIA quando o recorte não "
                            "tem nenhuma área livre: entrar disputando espaço é decisão à "
                            "parte, fora do funil."
                        ),
                    },
                ],
                "faixas": _faixas_m1(),
            },
        ],
        "parametros": [
            {"nome": "Score mínimo para entrar no funil", "valor": score},
            {"nome": "População mínima do hexágono", "valor": f"{pop} habitantes"},
            {"nome": "Residual mínimo", "valor": f"{res} alunos"},
            {"nome": "Capacidade média por academia", "valor": f"{cap} alunos"},
            {"nome": "Raio de concorrência", "valor": "2 km"},
            {"nome": "Tamanho máximo da fila", "valor": str(FILA_MAX)},
        ],
    }


@app.get("/api/metodologia")
def metodologia() -> dict[str, Any]:
    """Manual do funil: o que cada camada mede e com que régua corta."""
    return montar_metodologia()


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


@functools.lru_cache(maxsize=1)
def _ranking_estados() -> list[dict[str, Any]]:
    """Ranking NACIONAL por UF — a pergunta "por qual estado começar?".

    POR QUE NAO EXISTIA. O piloto lê UMA partição `uf=XX` por vez (`carregar_uf`,
    `lru_cache(maxsize=6)`), e nenhuma rota comparava estados. Quem queria escolher a
    UF tinha de abrir uma por uma e comparar de cabeça.

    POR QUE DÁ PARA FAZER AGORA. Parquet é colunar: lendo só 4 colunas das 27
    partições, os 1,54 milhão de hexágonos saem em ~3 s (medido). O `lru_cache` faz
    isso uma vez por processo — o custo some depois da primeira chamada.

    MESMA CASCATA DO FUNIL, aplicada nacionalmente. Nada de critério novo:
    `score_setor_2022_calibrado >= SCORE_CORTE_QUENTE`, população do hexágono
    `>= POP_MIN_ACIONAVEL`, e WHITE SPACE (`oferta_consumida_mercado_estimada` abaixo
    de meia unidade de referência — o mesmo arredondamento que produz
    `n_concorrentes_est == 0`). Ordena por residual em alunos, não por score: o score
    satura em 100 acima de 2.500 alunos e empataria os estados grandes.

    READ-ONLY sobre o M1: agrega colunas já materializadas, não recalcula nada.
    """
    import pyarrow.dataset as ds

    if not ENRICHED_DIR.exists():
        raise HTTPException(500, f"Base nao encontrada em {ENRICHED_DIR}.")

    dset = ds.dataset(str(ENRICHED_DIR), partitioning="hive")
    disp = set(dset.schema.names)
    col_pop = "pop_total_setor_2022" if "pop_total_setor_2022" in disp else "pop_hex_base"
    cols = [
        c
        for c in (
            "uf", "nome_municipio", "oferta_efetiva_disponivel",
            "oferta_consumida_mercado_estimada", "score_setor_2022_calibrado", col_pop,
        )
        if c in disp
    ]
    df = dset.to_table(columns=cols).to_pandas()
    if df.empty:
        return []

    quente = df["score_setor_2022_calibrado"] >= SCORE_CORTE_QUENTE
    povoado = df[col_pop] >= POP_MIN_ACIONAVEL
    # `n_concorrentes_est` e' DERIVADO (round(consumida / 2500)) e nao existe no
    # artefato: reproduzimos o mesmo corte na origem, sem materializar a coluna.
    livre = df["oferta_consumida_mercado_estimada"].fillna(0) < (
        CAPACIDADE_CONCORRENTE_PADRAO / 2.0
    )
    elegivel = df[quente & povoado & livre]

    out: list[dict[str, Any]] = []
    for uf_nome, bloco in df.groupby("uf", observed=True):
        eleg = elegivel[elegivel["uf"] == uf_nome]
        out.append(
            {
                "uf": str(uf_nome),
                # O numero que ORDENA: alunos nao atendidos onde ainda cabe abrir.
                "residual_white_space": _num(eleg["oferta_efetiva_disponivel"].sum()),
                "hexes_elegiveis": int(len(eleg)),
                "municipios_elegiveis": int(eleg["nome_municipio"].nunique())
                if "nome_municipio" in eleg.columns
                else None,
                # Contexto, para o operador ver o tamanho do estado por tras do numero.
                "residual_total": _num(bloco["oferta_efetiva_disponivel"].sum()),
                "hexes_total": int(len(bloco)),
                "pop_total": _num(bloco[col_pop].sum()),
            }
        )

    out.sort(key=lambda r: r["residual_white_space"] or 0, reverse=True)
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out


@app.get("/api/estados")
def estados() -> dict[str, Any]:
    """Por qual estado começar. Cascata do funil, aplicada às 27 UFs."""
    ranking = _ranking_estados()
    return {
        "reguas": {
            "score_minimo": SCORE_CORTE_QUENTE,
            "pop_minima": POP_MIN_ACIONAVEL,
            "capacidade_concorrente": CAPACIDADE_CONCORRENTE_PADRAO,
        },
        "estados": ranking,
    }


@app.get("/api/resolver-ponto")
def resolver_ponto(q: str) -> dict[str, Any]:
    """Texto colado pelo operador -> lat/lng. Cobre o LINK CURTO do celular.

    Por que existe. O front resolve sozinho coordenada e link LONGO (`lib/coord.ts`),
    mas o link que o botão "Compartilhar" do app do Maps gera (`maps.app.goo.gl/...`)
    não tem coordenada nenhuma na URL — é um 30x. Sem esta rota ele seguia como texto
    para o `/api/geocode`, que devolvia `{"found": false}`, e o operador via "não
    encontrei esse endereço" para um link perfeitamente válido.

    Ordem, do mais barato para o mais caro (rede só quando o passo puro falha):
      1. `parse_maps_url` — puro, sem rede;
      2. `expandir_link_curto` — segue o redirect e tenta o parse de novo;
      3. `extrair_endereco_de_place_url` — link de place SEM coordenada: o endereço
         está no próprio path, então geocodifica esse texto;
      4. geocode do texto original.

    Rede aqui é a MESMA exceção já aprovada para a barra de busca (DEC-010): é ação
    do operador, não caminho de carga do app. READ-ONLY; não toca artefato nenhum.
    """
    from motor_expansao.api.coord import (
        CoordenadaInvalidaError,
        parse_maps_url,
        validar_brasil,
    )
    from motor_expansao.api.geo import (
        expandir_link_curto,
        extrair_endereco_de_place_url,
    )

    termo = (q or "").strip()
    if not termo:
        return {"found": False, "motivo": "Cole um link do Google Maps, um endereço ou uma coordenada."}

    def _coord(lat: float, lng: float, via: str) -> dict[str, Any]:
        return {"found": True, "lat": _num(lat, 6), "lng": _num(lng, 6), "via": via}

    # 1. Parse puro: link longo com @lat,lng / !3d!4d, ou "lat,lng" cru.
    try:
        lat, lng = validar_brasil(*parse_maps_url(termo))
        return _coord(lat, lng, "coordenada")
    except CoordenadaInvalidaError as exc:
        # "Fora do Brasil" é DIFERENTE de "não parseei": a coordenada foi lida, e
        # dizer "não reconheci" mandaria o operador procurar erro de digitação.
        if "fora do Brasil" in str(exc):
            return {
                "found": False,
                "motivo": "Essa coordenada está fora do Brasil. Confira se a latitude e a longitude não vieram trocadas.",
            }

    # 2. Link curto: segue o redirect e tenta o parse de novo.
    expandida = expandir_link_curto(termo)
    if expandida != termo:
        try:
            lat, lng = validar_brasil(*parse_maps_url(expandida))
            return _coord(lat, lng, "link-expandido")
        except CoordenadaInvalidaError:
            pass

    # 3. Link de place sem coordenada: o endereço está no path da URL expandida.
    endereco = extrair_endereco_de_place_url(expandida)
    if endereco:
        achado = geocode(endereco)
        if achado.get("found"):
            return {**achado, "via": "endereco-do-link"}

    # 4. Texto livre.
    achado = geocode(termo)
    if achado.get("found"):
        return {**achado, "via": "endereco"}

    return {
        "found": False,
        "motivo": (
            "Não consegui resolver esse link. Abra-o no navegador e cole o endereço "
            "da barra (o que começa com google.com/maps/…), ou cole a coordenada."
        ),
    }


def _criterios_do_ponto(
    censo: dict[str, Any], mercado: dict[str, Any], concorrencia: dict[str, Any]
) -> list[dict[str, Any]]:
    """Cada métrica do IMÓVEL contra a régua do critério do imóvel.

    NÃO cria veredito novo — não há "score de aprovação do imóvel" aqui, o que seria
    definição nova de viabilidade e exigiria DEC. Cada linha é UMA métrica contra UM
    corte, e o operador lê as cinco.

    DUAS DESSAS RÉGUAS DIVERGEM DO FUNIL desde 2026-08-12, por decisão do Juan:
    `CRIT_PONTO_SCORE_MIN` (60, contra 70 do passo 1) e `CRIT_PONTO_CONC_MAX` (3, contra
    o white space do passo 5). As outras três seguem canônicas do `config.py`
    (`POP_MIN_ACIONAVEL`, `OFERTA_DESTAQUE_MIN`, `RENDA_MIN`). Consequência declarada: um
    imóvel pode passar aqui e o hexágono dele não entrar na fila do mapa.

    Avaliado no SERVIDOR de propósito: a régua e a comparação andam juntas. Mandar só
    o número e deixar a tela comparar seria a primeira porta para o front e o backend
    discordarem sobre o que é "aprovado".

    `RENDA_MIN` é renda DOMICILIAR, não per capita (comentário literal em
    `config.py:131`) — comparar contra a per capita reprovaria quase todo ponto.
    """
    from motor_expansao.config import settings

    def crit(
        chave: str, rotulo: str, valor: Any, regua: float, unidade: str, maior_melhor: bool = True
    ) -> dict[str, Any]:
        v = _numf(valor)
        passa = None if v is None else (v >= regua if maior_melhor else v <= regua)
        return {
            "chave": chave,
            "rotulo": rotulo,
            "valor": _num(v, 1) if unidade == "score" else _num(v),
            "regua": _num(regua, 1) if unidade == "score" else _num(regua),
            "unidade": unidade,
            "maior_melhor": maior_melhor,
            "passa": passa,
        }

    itens = [
        crit("populacao", "População no raio", censo.get("populacao"), POP_MIN_ACIONAVEL, "pessoas"),
        crit(
            "renda_domiciliar", "Renda domiciliar",
            censo.get("renda_media_domiciliar"), float(settings.RENDA_MIN), "R$",
        ),
        crit(
            "score", "Potencial socioeconômico",
            censo.get("score_socioeconomico"), CRIT_PONTO_SCORE_MIN, "score",
        ),
    ]
    if mercado.get("disponivel"):
        itens.append(
            crit("residual", "Residual disponível", mercado.get("residual"), OFERTA_DESTAQUE_MIN, "alunos")
        )
    if concorrencia.get("disponivel"):
        # O teto e' `CRIT_PONTO_CONC_MAX`, NAO o white space do passo 5. A fila do funil
        # continua exigindo zero concorrente mapeado; aqui a pergunta e' outra — um imovel
        # com tres concorrentes no raio de 1 km nao esta descartado, esta disputado.
        itens.append(
            crit(
                "concorrentes", "Concorrentes no raio",
                concorrencia.get("n_concorrentes"), CRIT_PONTO_CONC_MAX, "", False,
            )
        )
    return itens


@app.get("/api/ponto")
def ponto(lat: float, lng: float) -> dict[str, Any]:
    """Ficha de UM ponto: censo real no raio de 1,0 km, mais mercado quando houver.

    NÃO carrega a partição da UF. O mapa lê `hexagonos_dashboard_enriquecido/uf=XX`
    inteiro (até 15.000 hexes, >15 s na primeira vez — por isso o `TIMEOUT_LEITURA` de
    90 s no cliente). Um fluxo "cole o link, veja a ficha" que esperasse isso estaria
    morto; aqui se lê só a partição do município e um punhado de hexes.

    DEGRADAÇÃO POR BLOCO, e nunca em silêncio. Cada bloco devolve `disponivel` e, quando
    falso, o `motivo` por extenso. O censo depende só da malha IBGE 2022; concorrência e
    mercado dependem de `data/staging`, que pode não estar montado. Sem isso a tela
    mostraria card em branco e o operador leria como defeito.

    Raio 1,0 km = `RAIO_CENSITARIO_DEFAULT_KM` (DEC-021) — o MESMO do Relatório Pontual,
    para a tela e o PDF contarem a mesma coisa.

    READ-ONLY: nenhum score recalculado, nenhum artefato tocado.
    """
    from motor_expansao.api.coord import CoordenadaInvalidaError, validar_brasil
    from motor_expansao.api.errors import APIError
    from motor_expansao.api.service import (
        _competitors_ultra,
        _hexes_vizinhos_do_ponto,
        _nome_municipio_de,
        _residual_do_ponto,
        _resolver_e_carregar,
    )
    from motor_expansao.api.settings import Settings
    from motor_expansao.dashboard.censo_point import (
        RAIO_CENSITARIO_DEFAULT_KM,
        analisar_ponto_censitario_setores,
    )

    # `_resolver_e_carregar` NÃO valida o bounding box — sem isto, uma coordenada
    # absurda seguiria direto para o ponto-em-polígono.
    try:
        validar_brasil(lat, lng)
    except CoordenadaInvalidaError as exc:
        raise HTTPException(400, str(exc)) from exc

    cfg = Settings(
        censo_geo_dir=CENSO_GEO_DIR,
        ibge_dir=IBGE_DIR,
        ultra_dir=ULTRA_DIR,
        staging_dir=STAGING_DIR,
    )

    try:
        uf, _cod, setores_df = _resolver_e_carregar(lat, lng, cfg)
    except APIError as exc:
        # `APIError` é do contrato da API de produção, que registra um handler próprio
        # (`main.py`). O piloto NÃO registra — aqui ela vazaria como 500 sem código.
        # Propagamos o status ORIGINAL de propósito: 400 é "coordenada fora da malha"
        # (erro do operador) e 404 é "partição do município não materializada" (erro de
        # implantação). O caminho do PDF (app.py, `_gerar_relatorio_pontual_pdf`) achata
        # os dois em 400 e faz o operador ler "não foi possível resolver a coordenada"
        # quando o problema é dado faltando no servidor.
        raise HTTPException(exc.status_code, exc.detail) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Não foi possível resolver a coordenada: {exc}") from exc

    # (None, None) quando `data/staging` não tem os parquets — é o caso previsto, não erro.
    comp_df, ultra_df = _competitors_ultra(cfg)
    tem_concorrentes = comp_df is not None or ultra_df is not None

    res = analisar_ponto_censitario_setores(
        lat, lng, setores_df,
        raio_km=RAIO_CENSITARIO_DEFAULT_KM,
        competitors_df=comp_df,
        ultra_df=ultra_df,
    )

    residual = _residual_do_ponto(lat, lng, cfg)
    tem_mercado = any(v is not None for v in residual.values())

    import h3

    hex_id = h3.latlng_to_cell(lat, lng, 7)  # 7 = H3_RESOLUTION do M1, LIDO

    # Vizinhança para o mini-mapa. k=2 (19 células) e não o k=5 do PDF: aqui é
    # enquadramento de tela, não choropleth de relatório.
    vizinhos: list[dict[str, Any]] = []
    hexes_df = _hexes_vizinhos_do_ponto(lat, lng, cfg, k=2)
    if hexes_df is not None:
        for _, r in hexes_df.iterrows():
            vizinhos.append(
                {
                    "hex_id": _texto(r.get("hex_id")),
                    "residual": _num(r.get("oferta_efetiva_disponivel")),
                    "score_censo": _num(r.get("score_setor_2022_calibrado"), 1),
                }
            )

    from motor_expansao.config import settings as _cfg

    # ---- Detalhe da regiao: os campos que o motor calcula e a ficha resumia ----
    # Existe para o operador AUDITAR de onde cada numero saiu. Definido ANTES dos
    # blocos porque eles o referenciam.
    #
    # `renda_domiciliar_total_raio` fica DE FORA de proposito: apesar do nome, nao e'
    # um total — e' media ponderada de outra grandeza (`censo_point.py:460`). Numero
    # financeiro com rotulo errado vira decisao errada; omitir e' menos pior.
    # Distribuicao BRUTA entre os setores do raio. A media esconde a variacao: na Av.
    # Paulista a renda per capita media e' R$ 5.838, mas os setores vao de R$ 780 a
    # R$ 25.272 — 32x de amplitude dentro de 1 km. Quem escolhe imovel precisa ver isso.
    def _dist(coluna: str, casas: int = 0) -> dict[str, Any] | None:
        setores = res.get("setores_intersectados")
        if setores is None or getattr(setores, "empty", True) or coluna not in setores.columns:
            return None
        valores = pd.to_numeric(setores[coluna], errors="coerce").dropna()
        if valores.empty:
            return None
        return {
            "min": _num(valores.min(), casas),
            "p50": _num(valores.median(), casas),
            "max": _num(valores.max(), casas),
            "n": int(len(valores)),
        }

    detalhe_censo = {
        "n_setores": _num(res.get("n_setores")),
        # Duas AREAS: o circulo inteiro, e o que a malha do IBGE cobre dentro dele.
        "area_circulo_km2": _num(res.get("area_km2"), 2),
        "area_intersectada_km2": _num((res.get("area_intersecao_total_m2") or 0) / 1e6, 2),
        # Duas DENSIDADES, e a diferenca importa na orla: a fixa divide pelo circulo
        # inteiro (inclui agua e vazio); a valida, so' pela area de setor real.
        "densidade_fixa_hab_km2": _num(res.get("densidade_pop_raio_hab_km2")),
        "densidade_valida_hab_km2": _num(res.get("densidade_pop_raio_valida_hab_km2")),
        "score_medio_raio": _num(res.get("score_setor_medio"), 1),
        "score_max_raio": _num(res.get("score_setor_max"), 1),
        # SETOR A SETOR: min / mediana / max do que o raio contem.
        "distribuicao": {
            "renda_per_capita": _dist("renda_per_capita_setor_2022_calibrada"),
            "score": _dist("score_setor_2022_calibrado", 1),
            "populacao": _dist("pop_total_setor_2022"),
            "densidade_hab_km2": _dist("densidade_pop_setor_hab_km2"),
        },
        # O setor que CONTEM o ponto, cru. Pode divergir bastante da media do raio —
        # e' a diferenca entre "a regiao" e "a esquina".
        "setor_do_ponto": {
            "encontrado": bool(res.get("flag_setor_ponto_encontrado")),
            "cod_setor": _texto(res.get("cod_setor_ponto")),
            "renda_per_capita": _num(res.get("renda_per_capita_setor_ponto")),
            "densidade_hab_km2": _num(res.get("densidade_pop_setor_ponto")),
            "score": _num(res.get("score_setor_2022_calibrado_ponto"), 1),
            "bairro": _texto(res.get("nome_bairro_ponto")),
            "distrito": _texto(res.get("nome_distrito_ponto")),
        },
        # Procedencia, nao metodo: de quando e' o dado.
        "data_referencia": _texto(res.get("data_referencia_renda")),
    }

    # Concorrentes por distancia. `concorrentes_raio` e' DataFrame: serializar campo a
    # campo, nunca o objeto cru — ele nao e' JSON e derrubaria a rota.
    lista_conc: list[dict[str, Any]] = []
    _cr = res.get("concorrentes_raio")
    if _cr is not None and getattr(_cr, "empty", True) is False:
        for _, _linha in _cr.sort_values("dist_km").head(30).iterrows():
            lista_conc.append(
                {
                    "rede": _texto(_linha.get("rede")),
                    "dist_km": _num(_linha.get("dist_km"), 2),
                }
            )

    censo_bloco = {
        "disponivel": True,
        "motivo": None,
        "populacao": _num(res.get("pop_total_raio")),
        "domicilios": _num(res.get("domicilios_total_raio")),
        "renda_per_capita": _num(res.get("renda_per_capita_media_raio")),
        "renda_media_domiciliar": _num(res.get("renda_media_domiciliar_raio")),
        # A densidade VÁLIDA divide pela área de setor realmente intersectada, e não
        # por pi*r^2: num ponto com rio/mar no raio, a fixa subestima de propósito.
        "densidade_hab_km2": _num(res.get("densidade_pop_raio_valida_hab_km2")),
        "score_socioeconomico": _num(res.get("score_setor_2022_calibrado_ponto"), 1),
        "n_setores": _num(res.get("n_setores")),
        "detalhe": detalhe_censo,
    }

    conc_bloco = {
        "disponivel": tem_concorrentes,
        "motivo": None if tem_concorrentes else (
            "Sem base de concorrentes montada (data/staging/concorrentes_mapeados.parquet)."
        ),
        "n_concorrentes": _num(res.get("n_concorrentes")) if tem_concorrentes else None,
        "n_ultra": _num(res.get("n_ultra")) if tem_concorrentes else None,
        "lista": lista_conc,
    }

    mercado_bloco = {
        "disponivel": tem_mercado,
        "motivo": None if tem_mercado else (
            "Sem leitura de mercado para este hexágono "
            "(data/staging/hexagonos_mercado_mapeado.parquet ausente)."
        ),
        "sam": _num(residual.get("sam_fitness_potencial")),
        "residual": _num(residual.get("oferta_efetiva_disponivel")),
        "score_residual": _num(residual.get("score_oportunidade_residual"), 1),
    
    }

    return {
        "lat": _num(lat, 6),
        "lng": _num(lng, 6),
        "raio_km": RAIO_CENSITARIO_DEFAULT_KM,
        "hex_id": hex_id,
        "local": {
            # `uf` e o nome do município NÃO estão no dict de `analisar_ponto_...` (são
            # 40 chaves, nenhuma delas é o município): vêm de `_resolver_e_carregar` e
            # da própria partição. Ler `res["municipio_nome"]` daria None em silêncio.
            "uf": uf,
            "municipio": _texto(_nome_municipio_de(setores_df)),
            "bairro": _texto(res.get("unidade_ponto_rotulo")),
            # Identificador cru ("bairro"/"distrito"), NÃO acentuar — o rótulo de
            # exibição é o `bairro` acima.
            "unidade_tipo": _texto(res.get("unidade_ponto_tipo")),
        },
        "censo": censo_bloco,
        "concorrencia": conc_bloco,
        "mercado": mercado_bloco,
        "vizinhos": vizinhos,
        # Reguas do IMOVEL, legiveis por maquina. A `/api/metodologia` traz as mesmas
        # como TEXTO ("5.000 habitantes"), que serve para explicar e nao para comparar.
        "reguas": {
            "pop_minima": POP_MIN_ACIONAVEL,
            # A regua do IMOVEL, nao a do funil. Este bloco e' a versao legivel por
            # maquina do que `criterios` avalia; publicar `SCORE_CORTE_QUENTE` aqui
            # deixaria o MESMO payload dizendo 60 num campo e 70 no outro — foi o que o
            # merge com a main criou, e e' exatamente a divergencia que este bloco existe
            # para eliminar. O funil segue publicando 70 em `/api/estados`, que fala dele.
            "score_minimo": CRIT_PONTO_SCORE_MIN,
            "renda_domiciliar_minima": _num(float(_cfg.RENDA_MIN)),
            "area_min_m2": _num(float(_cfg.AREA_MIN_M2)),
            "area_ideal_min_m2": _num(float(_cfg.AREA_IDEAL_MIN_M2)),
            "area_ideal_max_m2": _num(float(_cfg.AREA_IDEAL_MAX_M2)),
            # Regra de BOLSO, nao modelo: a partir daqui a regiao e disputada. NAO
            # deriva metragem de concorrencia -- isso viola a DEC-009, que fixou o
            # motor como property-first (m2 e ENTRADA do operador, nunca previsto
            # pela geografia).
            #
            # Aponta para `CRIT_PONTO_CONC_MAX` desde 2026-08-12: o teto do criterio
            # passou a ser o mesmo numero em que o texto ja' chamava a regiao de
            # disputada. Sao papeis diferentes — um aprova, o outro nomeia —, mas manter
            # os dois no mesmo valor por construcao evita que divirjam em silencio.
            "conc_regiao_disputada": CRIT_PONTO_CONC_MAX,
        },
        "criterios": _criterios_do_ponto(censo_bloco, mercado_bloco, conc_bloco),
    }


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
        # FORA de `passos` de proposito: e o unico bloco que fala do estado inteiro,
        # e nao uma camada do funil (que sempre descreve o que sobreviveu ao filtro).
        "crescimento_estado": montar_crescimento_estado(df),
        "hexes": hexes,
        "cres_mun": _bloco_municipal(vis),
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
        "cres_mun": _bloco_municipal(vis),
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


@functools.lru_cache(maxsize=32)
def _cobertura_calc(uf: str, municipio: str | None, limite: int) -> str:
    """Geometria da cobertura, em CACHE, serializada como JSON.

    O cache existe porque a chave do raio e' um liga/desliga: sem ele, cada clique
    repetia ~1,5 s de recorte geometrico para devolver exatamente o mesmo resultado —
    era a maior parte dos ~3 s que o operador sentia. Devolve string (imutavel e
    hashavel) para nao entregar o mesmo dict mutavel a varios chamadores.

    `limpar_caches()` varre os globais com `cache_clear`, entao este entra junto.
    """
    df = carregar_uf(uf)
    if municipio:
        sel = df[df["nome_municipio"].str.casefold() == municipio.casefold()]
        if sel.empty:
            raise HTTPException(404, f"Municipio '{municipio}' nao encontrado na UF {uf}.")
        vis = sel.nlargest(4000, "oferta_efetiva_disponivel") if len(sel) > 4000 else sel
    else:
        vis = df.nlargest(limite, "oferta_efetiva_disponivel") if len(df) > limite else df

    # Sombras (adensamento) em TODA visao, inclusive a de estado. Ficaram restritas ao
    # drill-down por uma estimativa de ~1,8 MB "para nada", feita quando a rota morria em
    # 500 nas UFs densas e ninguem conseguia medir o resultado real. Medido em 2026-08-12,
    # com a rota funcionando: SP sai de 1,32 MB / 0,7 s para 2,11 MB / 1,0 s -- +0,79 MB
    # por 2.692 sombras. O outro argumento (disco de 1 km com ~5 px) so' vale no zoom
    # INICIAL: a visao de estado e' navegavel, e quem aproxima passava a nao ter o mapa de
    # calor sem trocar para o drill-down (pedido do Felipe, 2026-08-12).
    #
    # `apenas_dentro` segue preso ao drill-down: la' o recorte e' de EXIBICAO (so' as
    # concorrentes dentro do municipio), e o motor continua contando a vizinha.
    return json.dumps(
        cobertura_1km.cobertura(
            vis,
            CONCORRENTES_PATH,
            com_sombras=True,
            apenas_dentro=bool(municipio),
        )
    )


@app.get("/api/cobertura/{uf}")
def cobertura_uf(uf: str, municipio: str | None = None, limite: int = 15000) -> Response:
    """PROTOTIPO — geometria do raio de 1 km, SOB DEMANDA.

    Vive fora de `/api/uf` e `/api/municipio` de proposito. Calcular a cobertura custa
    ~2,4 s e ~3,9 MB na UF de SP; embutida no payload principal, TODO operador pagava
    isso mesmo sem nunca ligar a chave. Aqui so' paga quem pede.

    O recorte de hexes espelha o das rotas do mapa (mesmo `limite`, mesmo criterio), para
    a geometria bater exatamente com os hexagonos desenhados.
    """
    return Response(
        content=_cobertura_calc(uf, municipio, limite),
        media_type="application/json",
    )


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
# Faturamento oficial (planilha do Financeiro, base dos royalties). Gerado por
# `scripts/ingerir_faturamento_financeiro.py` uma vez por mes. AUSENTE = a aba continua
# funcionando inteira com o faturamento da Growth: nenhuma tela pode cair porque a
# ingestao mensal atrasou.
FATURAMENTO_FINANCEIRO_PARQUET = STAGING_DIR / "faturamento_financeiro.parquet"

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
# 2026-08-03 (e o bloco de 2026-08-07 contra o cadastro de 169 unidades): o alvo existe,
# está livre (nenhuma outra unidade da Growth o reivindica) e a `cidade` do cadastro
# confere. `(chave Growth, UF) -> chave no cadastro`.
#
# O valor é a chave JÁ NORMALIZADA por `_chave_unidade`, que remove acento, caixa e
# sufixo de UF mas PRESERVA os espaços internos: o alvo de "Duque de Caxias" é
# "DUQUE DE CAXIAS", não "DUQUEDECAXIAS" — um valor sem os espaços não casa com nada e
# vira um no-op silencioso.
_EXEC_ALIAS_COORD: dict[tuple[str, str], str] = {
    # Bairro='Boa Vista' no GeoFusion; a homônima "Vitoria da Conquista II" fica no
    # Ibirapuera, e a Growth não tem nenhuma unidade "VITORIA DA CONQUISTA".
    ("BOA VISTA", "BA"): "VITORIA DA CONQUISTA",
    ("PATIO BRASIL", "DF"): "PATIO SHOPPING BRASIL",
    # "Vicente Pires / DF" já é consumida pela unidade "VICENTE PIRES - DF" da Growth;
    # a da "Rua 8" é a segunda do bairro, cadastrada como "Vicente Pires 2".
    ("VICENTE PIRES RUA 8", "DF"): "VICENTE PIRES 2",
    ("CESARIO", "MG"): "CESARIO ALVIM",
    ("FLORIANO", "MG"): "FLORIANO PEIXOTO",
    # Único registro dos 169 que menciona "Sagrada Familia": Rondonópolis, cujo
    # Bairro no GeoFusion é 'Parque Sagrada Família'.
    ("SAGRADA FAMILIA", "MT"): "RONDONOPOLIS",
    # Única unidade de PE nas duas bases; a av. Domingos Ferreira fica no Pina.
    ("DOMINGOS FERREIRA", "PE"): "RECIFE - PINA",
    ("FLOW", "PR"): "CURITIBA FLOW (UBERABA)",
    # Única linha do cadastro no município de Duque de Caxias; a Growth a chama só de
    # "CAXIAS" e `_chave_unidade` não expande prefixo de nome (nem deveria).
    ("CAXIAS", "RJ"): "DUQUE DE CAXIAS",
    ("SAO GONCALO - CENTRO", "RJ"): "SAO GONCALO",
    ("SAO GONCALO SHOPPING", "RJ"): "SHOPPING PARTAGE",
    ("PICARRAS", "SC"): "BALNEARIO PICARRAS",
    ("AMERICANA CENTRO", "SP"): "AMERICANA",
    # CORREÇÃO DE PIN ERRADO, não de pin ausente: sem o alias, "BOQUEIRAO - SP" não
    # casa por (chave, UF), cai no terceiro fallback — que é cego a UF — e herda a
    # coordenada de "Boqueirão / PR", em Curitiba, ~350 km de Santos.
    #
    # Cuidado: há DUAS unidades no bairro Boqueirão no litoral, e o cadastro não usa
    # esse nome em nenhuma das duas — "Praia Grande / SP" (Bairro='Boqueirão', Praia
    # Grande) e "Santos II - SP" (Bairro='Boqueirão', Santos). O alvo é a de SANTOS
    # porque a de Praia Grande já é reivindicada pela própria "PRAIA GRANDE - SP" da
    # Growth, que também está ativa. A geografia confirma: o ponto resolvido fica a
    # 1,1 km do Gonzaga (bairro vizinho na orla de Santos) e a 11 km de Praia Grande.
    # Felipe confirmou em 2026-08-07 que "BOQUEIRAO" no UX é a de Santos.
    ("BOQUEIRAO", "SP"): "SANTOS II",
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
    # A dependência de agregador por RECEITA só passou a existir de fato quando o
    # faturamento veio da planilha: com a Growth ela era 0,00% em toda a base desde
    # maio/2025. Vai para a ficha e para o benchmark de coorte, ao lado da de alunos —
    # as duas discordam em 14,8 p.p. na mediana, e é a de receita que fala de dinheiro.
    "pct_agregador_receita",
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
    # `cancelados` viaja junto do churn porque a tela passa a imprimir os dois: "5,7% (486)".
    # Percentual sozinho esconde o tamanho — 10% de 80 alunos e 10% de 4.000 pedem conversas
    # diferentes, e era o operador que fazia essa conta de cabeça (pedido do Felipe, 2026-08-10).
    "cancelados",
    "conversao_pct",
    "nps",
    "saldo_operacional",
    "pct_agregador_alunos",
    "novos_alunos",
    "em_cobranca_pct",
)

# KPIs do topo da tela. Soma para volume, média ponderada para taxa — somar churn
# de 92 unidades daria um número sem significado nenhum.
_REDE_KPIS_SOMA = (
    "faturamento",
    "ativos",
    "pagantes",
    "agregadores",
    "saldo_operacional",
    # Total de cancelamentos do recorte: o numero absoluto que acompanha o churn.
    "cancelados",
)
_REDE_KPIS_MEDIA = {
    "churn_pct": "pagantes",
    "receita_por_recorrente": "pagantes",
    "nps": "ativos",
    "conversao_pct": "visitas",
}

# Métricas do painel de evolução (12 meses fechados). Mesma divisão dos KPIs — somar uma
# taxa não significa nada — e os MESMOS pesos, para o ponto final da série concordar com o
# KPI do topo quando a competência escolhida está fechada.
_REDE_SERIES_SOMA = (
    "faturamento",
    "ativos",
    "pagantes",
    "agregadores",
    "novos_alunos",
    "saldo_operacional",
)
_REDE_SERIES_MEDIA = dict(_REDE_KPIS_MEDIA)

# Métricas do SSS. `faturamento_agregador` esteve fora daqui enquanto era zero em toda a
# base — a Growth parou de mandar receita de agregador em maio/2025, e a linha só mostraria
# zero contra zero. Com o faturamento vindo da planilha do Financeiro ela volta, e é a linha
# que mais explica a rede: medido em 2026-07 contra 2025-07, na mesma base de 60 unidades, o
# faturamento cresce +4,2% — mas a receita de RECORRENTES cresce só +0,8% e a de AGREGADORES
# +14,7%. Ou seja, o crescimento da mesma loja é quase todo do agregador. Sem esta linha, o
# painel mostrava o +4,2% e deixava a pergunta "de onde ele veio?" sem resposta.
_REDE_SSS_METRICAS = (
    "faturamento",
    "faturamento_sem_agregador",
    "faturamento_agregador",
    "ativos",
    "pagantes",
    "agregadores",
)

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
def _rede_faturamento_financeiro() -> pd.DataFrame:
    """Faturamento oficial da planilha do Financeiro. Vazio se a ingestão não rodou."""
    try:
        return rede_faturamento_financeiro.carregar(FATURAMENTO_FINANCEIRO_PARQUET)
    except (ValueError, OSError) as erro:
        # Parquet corrompido ou com esquema velho não pode derrubar a Visão Executiva: a
        # aba volta a mostrar o faturamento da Growth, que é pior mas está lá.
        print(f"[rede] faturamento do Financeiro ilegível ({erro}) — seguindo só com a Growth",
              file=sys.stderr)
        return pd.DataFrame()


@functools.lru_cache(maxsize=1)
def _rede_fechamento() -> pd.DataFrame:
    """Fechamento mensal de TODA a série, sem corte de dia (a base do histórico).

    O faturamento dos meses FECHADOS vem da planilha do Financeiro quando ela existe (base
    dos royalties); o mês em curso continua na Growth, porque a planilha é mensal e não
    sabe responder por uma janela parcial. Cada linha carrega `origem_faturamento` para a
    tela poder dizer de onde veio o número.
    """
    financeiro = _rede_faturamento_financeiro()
    return rede_metricas.fechamento_mensal(
        _rede_base(), financeiro=financeiro if len(financeiro) else None
    )


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


@functools.lru_cache(maxsize=1)
def _rede_limites() -> tuple[str, str]:
    """Primeira e última data COM DADO da base, em ISO. É o limite do calendário."""
    base = _rede_exigir_base()
    return (
        pd.Timestamp(base["_data"].min()).strftime("%Y-%m-%d"),
        pd.Timestamp(base["_data"].max()).strftime("%Y-%m-%d"),
    )


def _rede_periodo_valido(inicio: str, fim: str) -> tuple[str, str]:
    """Valida e GRAMPEIA o intervalo pedido à cobertura da base.

    Grampear em vez de recusar é deliberado: o operador que arrasta o calendário para
    antes do primeiro dia coletado quer "desde o começo", não um erro. O que é recusado é
    o que não tem leitura possível — data ilegível e fim antes do início.
    """
    try:
        ini = pd.Timestamp(inicio).normalize()
        term = pd.Timestamp(fim).normalize()
    except (TypeError, ValueError) as erro:
        raise HTTPException(400, f"Período inválido: {inicio} a {fim}.") from erro
    if pd.isna(ini) or pd.isna(term):
        raise HTTPException(400, f"Período inválido: {inicio} a {fim}.")
    if ini > term:
        raise HTTPException(400, "O fim do período é anterior ao início.")

    limite_min, limite_max = _rede_limites()
    ini = max(ini, pd.Timestamp(limite_min))
    term = min(term, pd.Timestamp(limite_max))
    if ini > term:
        raise HTTPException(
            404, f"A base cobre de {limite_min} a {limite_max}; o período pedido está fora."
        )
    return (ini.strftime("%Y-%m-%d"), term.strftime("%Y-%m-%d"))


def _rede_periodo_do_mes(mes_sel: str) -> tuple[str, str]:
    """Competência -> intervalo. Um mês em curso termina no último dia COM DADO.

    É o que preserva o comportamento de antes do calendário: escolher `2026-08` no dia 3
    continua mostrando o acumulado de 1 a 03/08, e não um mês inteiro com 28 dias vazios.
    """
    periodo = pd.Period(mes_sel, freq="M")
    inicio = periodo.to_timestamp(how="start")
    fim = periodo.to_timestamp(how="end").normalize()
    _, ultimo_dado = _rede_limites()
    return (inicio.strftime("%Y-%m-%d"), min(fim, pd.Timestamp(ultimo_dado)).strftime("%Y-%m-%d"))


def _rede_periodo_anterior(inicio: pd.Timestamp, fim: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    """O intervalo com que o "vs anterior" das setas compara.

    Três casos, e a regra é a mesma nos três: **preservar a âncora do período**.

    1. Mês calendário INTEIRO compara com o mês anterior inteiro. É a leitura que o time
       já tem e a que o mês fechado sempre usou.
    2. Período ANCORADO NO DIA 1o mas que não fecha o mês (o acumulado do mês em curso,
       que é o padrão da tela) compara com o mesmo intervalo de dias do mês anterior:
       1 a 03/08 contra 1 a 03/07. Sem esta cláusula, o "mesmo tamanho" jogaria 1 a 03/08
       contra 29 a 31/07 — e o faturamento da rede aparecia com **+190,3%** na abertura da
       tela, medido em 2026-08-10. Não é crescimento: a mensalidade é cobrada no começo do
       mês, então os três primeiros dias valem várias vezes os três últimos.
    3. Qualquer outra janela compara com a imediatamente anterior de MESMO TAMANHO:
       15 a 24/07 contra 5 a 14/07 (decisão do Felipe, 2026-08-10). Casar o dia-do-mês
       aqui colocaria 28 dias de um lado e 31 do outro em fevereiro contra março.
    """
    if _eh_mes_inteiro(inicio, fim):
        anterior = pd.Period(inicio, freq="M") - 1
        return (anterior.to_timestamp(how="start"), anterior.to_timestamp(how="end").normalize())

    dias = int((fim - inicio).days) + 1
    if inicio.day == 1 and pd.Period(inicio, freq="M") == pd.Period(fim, freq="M"):
        anterior = pd.Period(inicio, freq="M") - 1
        comeco = anterior.to_timestamp(how="start")
        # O mês anterior pode ser mais curto (03/03 não existe em fevereiro de 28 dias
        # quando se pede o dia 30): o fim é grampeado no último dia dele.
        fim_do_mes = anterior.to_timestamp(how="end").normalize()
        return (comeco, min(comeco + pd.Timedelta(days=dias - 1), fim_do_mes))

    return (inicio - pd.Timedelta(days=dias), fim - pd.Timedelta(days=dias))


def _rede_periodo_ano_anterior(
    inicio: pd.Timestamp, fim: pd.Timestamp
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """O MESMO intervalo, doze meses antes — a base do SSS.

    Mês inteiro vira o mesmo mês do ano passado (e não "o mesmo dia-do-mês"), que é o que
    faz julho de 31 dias comparar com julho de 31 dias. Recorte solto anda 12 meses nas
    duas pontas.
    """
    if _eh_mes_inteiro(inicio, fim):
        base = pd.Period(inicio, freq="M") - 12
        return (base.to_timestamp(how="start"), base.to_timestamp(how="end").normalize())
    return (inicio - pd.DateOffset(months=12), fim - pd.DateOffset(months=12))


def _eh_mes_inteiro(inicio: pd.Timestamp, fim: pd.Timestamp) -> bool:
    """True quando o intervalo é exatamente um mês do calendário, ponta a ponta."""
    periodo = pd.Period(inicio, freq="M")
    return bool(
        inicio.day == 1
        and pd.Period(fim, freq="M") == periodo
        and fim.day == periodo.days_in_month
    )


@functools.lru_cache(maxsize=8)
def _rede_periodo(inicio: str, fim: str) -> dict[str, Any]:
    """Tudo que o intervalo `[inicio, fim]` produz, calculado UMA vez.

    Carteira, ficha, CSV, XLSX e PDF leem daqui. É a resposta ao defeito mais caro deste
    projeto: a mesma unidade com dois números em duas superfícies (o
    `test_carteira_e_ficha_concordam` existe para travar isso).

    O que é do INTERVALO e o que é do MÊS
    -------------------------------------
    Só três coisas seguem o intervalo escolhido: os KPIs/quarteto (`atual`), a comparação
    com o período anterior (`m1`) e o SSS. Série de 12 meses, faixas absolutas de
    faturamento e diagnóstico continuam saindo de MÊS FECHADO, e por motivo, não por
    preguiça: a série é uma linha do tempo mensal, as faixas são limiares de mês inteiro
    (aplicá-las a 3 dias joga a rede toda em "Crítico") e o diagnóstico nunca roda sobre
    competência aberta. A tela diz de que mês cada um desses três vem.
    """
    base = _rede_exigir_base()
    cheio = _rede_fechamento()
    ini, term = pd.Timestamp(inicio).normalize(), pd.Timestamp(fim).normalize()
    if ini > term:
        raise HTTPException(400, "O fim do período é anterior ao início.")

    # As TRÊS janelas recebem a mesma sobreposição, e isso não é zelo: o SSS e o delta
    # contra o período anterior são RAZÕES entre duas pontas. Sobrepor uma só compararia
    # faturamento com agregador contra faturamento sem — que é exatamente o defeito da
    # Growth que este trabalho existe para consertar (Butantã aparecia com SSS de +586%
    # contra os +154% reais, por comparar jul/2026 com agregador contra jul/2025 sem).
    financeiro = _rede_faturamento_financeiro()
    financeiro = financeiro if len(financeiro) else None

    atual_cru = rede_metricas.fechamento_periodo(base, ini, term, financeiro=financeiro)
    if not len(atual_cru):
        raise HTTPException(404, f"Sem dados da rede entre {inicio} e {fim}.")

    ini_ant, fim_ant = _rede_periodo_anterior(ini, term)
    anterior_cru = rede_metricas.fechamento_periodo(base, ini_ant, fim_ant, financeiro=financeiro)

    ini_sss, fim_sss = _rede_periodo_ano_anterior(ini, term)
    ano_anterior = rede_metricas.fechamento_periodo(base, ini_sss, fim_sss, financeiro=financeiro)

    # A receita por recorrente é um NÍVEL — R$ por recorrente NUM MÊS —, e só o mês
    # calendário inteiro pode entregá-la direto. Fora dele, ela sai dos 30 dias que
    # terminam no fim do período, e não do intervalo escolhido, porque o intervalo
    # deforma a razão nas duas direções: 3 dias de receita sobre a base inteira davam
    # R$ 20,28 contra R$ 163,67 reais (o defeito que a janela de 30 dias existe para
    # consertar), e um trimestre sobre a mesma base davam R$ 461,60, que é a soma de três
    # meses fingindo ser um. O resto do quadro continua sendo o do intervalo pedido: quem
    # escolheu três dias quer o faturamento de três dias.
    dias = int((term - ini).days) + 1
    mes_inteiro = _eh_mes_inteiro(ini, term)
    if not mes_inteiro:
        atual_cru = _rede_nivel_de_receita(base, atual_cru, term, financeiro)
        anterior_cru = _rede_nivel_de_receita(base, anterior_cru, fim_ant, financeiro)

    contexto = rede_metricas.contexto_comparativo(atual_cru)
    contexto = rede_coorte.anotar_coortes(contexto)

    referencia = pd.Timestamp(atual_cru["dia_ref"].max())
    competencia = str(pd.Period(term, freq="M"))
    competencia_diagnostico = rede_diagnostico.competencia_base(cheio, competencia)
    diagnosticos = (
        rede_diagnostico.diagnosticar(cheio, competencia_diagnostico)
        if competencia_diagnostico
        else {}
    )

    return {
        "inicio": ini,
        "fim": term,
        "inicio_anterior": ini_ant,
        "fim_anterior": fim_ant,
        "inicio_sss": ini_sss,
        "fim_sss": fim_sss,
        "dias": dias,
        "mes_inteiro": mes_inteiro,
        # `mes` é a competência do FIM do intervalo: é ela que ancora a série de 12 meses,
        # as faixas e o diagnóstico, que continuam mensais.
        "mes": competencia,
        "referencia": referencia,
        # Propriedade da JANELA e da coleta, nunca das unidades. A primeira versão pedia
        # `periodo_completo` de todas elas, e uma única unidade inaugurada no meio de julho
        # bastava para a tela anunciar "julho (mês em curso)" com o mês inteiro na mão.
        "periodo_completo": bool(
            _eh_mes_inteiro(ini, term)
            and referencia >= term - pd.Timedelta(days=rede_metricas.TOLERANCIA_FIM_DE_MES_DIAS)
        ),
        "competencia_diagnostico": competencia_diagnostico,
        "atual": contexto,
        "m1": anterior_cru.set_index("unidade_id"),
        "ano_anterior": ano_anterior,
        "cheio": cheio,
        "diagnosticos": diagnosticos,
        "serie_meses": _rede_serie_meses(cheio, competencia),
    }


def _rede_nivel_de_receita(
    base: pd.DataFrame, quadro: pd.DataFrame, fim: pd.Timestamp,
    financeiro: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Troca `receita_por_recorrente` pela leitura de 30 dias que termina em `fim`.

    Vale para todo intervalo que NÃO seja um mês calendário inteiro. Os demais números do
    quadro seguem sendo os do intervalo escolhido.

    A janela de 30 dias recebe a mesma sobreposição das outras: quando ela calha de cobrir
    um mês civil inteiro — um mês de 30 dias, olhado do último dia — o numerador passa a ser
    o do Financeiro, como em qualquer outra janela fechada. Nos demais casos ela cai fora do
    alcance da planilha, que é mensal, e segue na Growth.
    """
    if not len(quadro):
        return quadro
    janela = rede_metricas.fechamento_periodo(
        base, fim - pd.Timedelta(days=29), fim, financeiro=financeiro
    )
    if not len(janela):
        return quadro
    receita = janela.set_index("unidade_id")["receita_por_recorrente"]
    ajustado = quadro.set_index("unidade_id")
    ajustado["receita_por_recorrente"] = pd.to_numeric(receita, errors="coerce").reindex(
        ajustado.index
    )
    return ajustado.reset_index()


def _rede_mes(mes_sel: str) -> dict[str, Any]:
    """Ponte com quem ainda fala em COMPETÊNCIA: o contrato v1 e a ficha da unidade."""
    inicio, fim = _rede_periodo_do_mes(mes_sel)
    return _rede_periodo(inicio, fim)


def _rede_series(recorte: pd.DataFrame, contexto: dict[str, Any]) -> dict[str, list[float | None]]:
    """Séries de 12 meses FECHADOS do recorte, uma por métrica do painel.

    Mesma regra de agregação dos KPIs do topo, e pelo mesmo motivo: **soma para volume,
    média ponderada para taxa**. Somar o churn de 92 unidades daria um número sem
    significado nenhum, e a média SIMPLES faria a unidade de 200 alunos pesar igual à de
    4.000.

    `None` num mês em que nenhuma unidade do recorte tinha operação — melhor um buraco
    honesto no gráfico do que um zero que parece faturamento nulo.

    `serie_rede` (que o CSV, o XLSX e o PDF já leem) passa a ser exatamente
    `series["faturamento"]`: uma conta só para o mesmo gráfico, que é a regra desta aba
    desde que tela e PDF somavam cada um a sua versão das sparklines.
    """
    meses: list[str] = contexto["serie_meses"]
    chaves = (*_REDE_SERIES_SOMA, *_REDE_SERIES_MEDIA)
    if not meses or not len(recorte):
        return {chave: [None] * len(meses) for chave in chaves}

    cheio = contexto["cheio"]
    do_recorte = cheio[cheio["unidade_id"].isin(set(recorte["unidade_id"]))]
    # Agrupa UMA vez por competência (chave em texto: a coluna é `Period` e o resto do
    # payload trafega mês como string).
    grupos = {str(mes): grupo for mes, grupo in do_recorte.groupby("competencia", observed=True)}

    series: dict[str, list[float | None]] = {}
    for chave in _REDE_SERIES_SOMA:
        series[chave] = [
            _num(pd.to_numeric(grupos[mes][chave], errors="coerce").sum(), _rede_casas(chave))
            if mes in grupos
            else None
            for mes in meses
        ]
    for chave, peso in _REDE_SERIES_MEDIA.items():
        series[chave] = [
            _wavg(grupos[mes][chave], grupos[mes][peso]) if mes in grupos else None for mes in meses
        ]
    return series


def _rede_faturamento_fechado(contexto: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Faturamento do último mês FECHADO por unidade, e a variação contra o mês anterior.

    "Quem puxa e quem segura" não pode sair da competência em curso. No dia 3 de agosto, a
    variação contra os mesmos três dias de julho põe no topo da lista uma unidade que saiu
    de R$ 400 para R$ 26 mil: +6.239% de ruído de janela curta, não de desempenho —
    medido na base de produção em 2026-08-10, com as cinco primeiras colocadas entre
    +178% e +6.239%. É a mesma razão pela qual o diagnóstico e as faixas de faturamento
    rodam sempre sobre mês fechado.

    Quando a competência escolhida JÁ está fechada, este número coincide com o
    `delta_pct` do quarteto — é o mesmo mês contra o mesmo mês anterior.

    A variação só existe para quem operou o mês INTEIRO nos dois meses **e** já tinha ao
    menos um mês completo de operação antes do mês-base. Sem essa segunda condição o
    painel vira uma lista de inaugurações: medido na base de produção, as cinco primeiras
    colocadas de "quem puxa" em julho/2026 (+1.402%, +647%, +617%, +475%, +343%) eram
    todas unidades abertas em JUNHO — Novo Gama abriu no dia 30 e faturou R$ 2,3 mil no
    mês de estreia contra R$ 35 mil no primeiro mês cheio. Isso é rampa de abertura, e
    quem lê a lista quer saber quem MEXEU o ponteiro.
    """
    meses: list[str] = contexto["serie_meses"]
    if not meses:
        return {}
    atual = meses[-1]
    anterior = str(pd.Period(atual, freq="M") - 1)
    cheio = contexto["cheio"]

    def por_unidade(competencia: str) -> pd.DataFrame:
        return cheio[cheio["competencia"] == competencia].set_index("unidade_id")

    agora, antes = por_unidade(atual), por_unidade(anterior)
    fat_agora = pd.to_numeric(agora.get("faturamento"), errors="coerce")
    fat_antes = pd.to_numeric(antes.get("faturamento"), errors="coerce")
    inteiro_agora = agora["operacao_mes_cheio"].fillna(False).astype(bool)
    inteiro_antes = antes["operacao_mes_cheio"].fillna(False).astype(bool)
    # `>= 1` = o mês-base já era, no mínimo, o segundo mês da unidade. Cachamorra abriu
    # no dia 1o de junho, então junho conta como mês inteiro, mas ainda é o mês ZERO dela.
    maduro_antes = pd.to_numeric(antes.get("meses_operacao"), errors="coerce").fillna(0) >= 1

    saida: dict[str, dict[str, Any]] = {}
    for unidade_id in agora.index:
        chave = str(unidade_id)
        valor = _numf(fat_agora.get(unidade_id))
        base = _numf(fat_antes.get(unidade_id))
        comparavel = (
            bool(inteiro_agora.get(unidade_id, False))
            and bool(inteiro_antes.get(unidade_id, False))
            and bool(maduro_antes.get(unidade_id, False))
        )
        saida[chave] = {
            "competencia": atual,
            "faturamento": _num(valor, 2),
            "variacao_pct": (
                _num(100.0 * (valor - base) / base, 1)
                if (comparavel and valor is not None and base)
                else None
            ),
        }
    return saida


def _rede_funil(recorte: pd.DataFrame, conversao_pct: float | None) -> dict[str, Any]:
    """Funil comercial somado do recorte — as MESMAS quatro etapas da ficha da unidade.

    A conversão NÃO é recalculada aqui: vem do KPI, que já a pondera por visitas. Duas
    contas para o mesmo percentual é como a mesma unidade acaba com dois números em duas
    superfícies desta aba.
    """
    def soma(chave: str) -> float | None:
        return _num(pd.to_numeric(recorte[chave], errors="coerce").sum()) if len(recorte) else None

    visitas, convertidos = soma("visitas"), soma("convertidos")
    vendas, novos = soma("vendas"), soma("novos_alunos")
    return {
        "visitas": visitas,
        "convertidos": convertidos,
        "vendas": vendas,
        "novos_alunos": novos,
        "conversao_pct": conversao_pct,
        # NUNCA clampar em 100%: `vendas > convertidos` em 75% das linhas da base.
        # Clampar esconderia um problema de coleta em vez de mostrá-lo.
        "aviso": (
            "Há venda sem visita registrada no período: o funil não fecha."
            if (vendas or 0) > (convertidos or 0)
            else None
        ),
    }


def _rede_faixas(recorte: pd.DataFrame, contexto: dict[str, Any]) -> dict[str, Any]:
    """Quantas unidades do recorte em cada faixa ABSOLUTA de faturamento do time de campo.

    Roda sempre sobre o último mês FECHADO, nunca sobre a competência em curso. As faixas
    (`Crítico <150k … Excelente+ ≥300k`) são limiares de MÊS INTEIRO: aplicá-las ao
    acumulado de três dias jogaria a rede inteira em "Crítico" — o mesmo motivo pelo qual
    o diagnóstico não roda sobre mês aberto.
    """
    competencia = contexto["competencia_diagnostico"]
    if not competencia or not len(recorte):
        return {"competencia": competencia, "faixas": []}

    cheio = contexto["cheio"]
    fechado = cheio[
        (cheio["competencia"] == competencia)
        & cheio["unidade_id"].isin(set(recorte["unidade_id"]))
    ]
    if not len(fechado):
        return {"competencia": competencia, "faixas": []}

    chave_da_linha = fechado["faturamento"].map(lambda v: rede_diagnostico.faixa_faturamento(v)[0])
    faturamento = pd.to_numeric(fechado["faturamento"], errors="coerce")
    faixas: list[dict[str, Any]] = []
    for _teto, chave, rotulo in rede_diagnostico.FAIXAS_FATURAMENTO:
        marca = chave_da_linha == chave
        faixas.append(
            {
                "chave": chave,
                "rotulo": rotulo,
                "n": int(marca.sum()),
                "faturamento": _num(faturamento[marca].sum(), 2),
            }
        )
    # A unidade sem faturamento no mês fechado não some da conta: sem este balde, a soma
    # das faixas não fecharia com o total do recorte e a barra mentiria por omissão.
    sem_dado = int((chave_da_linha == "sem_dado").sum())
    if sem_dado:
        faixas.append({"chave": "sem_dado", "rotulo": "Sem dado", "n": sem_dado, "faturamento": None})
    return {"competencia": competencia, "faixas": faixas}


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


def _rede_sss(
    atual: pd.DataFrame,
    ano_anterior: pd.DataFrame,
    ids: Collection[str] | None = None,
) -> dict[str, Any]:
    """Same Store Sales do RECORTE: o mesmo intervalo, doze meses antes, em BASE COMPARÁVEL.

    A rede abriu 33 unidades em 2025; comparar total contra total mede abertura de loja,
    não desempenho. Entram só as unidades presentes nos DOIS períodos e que operaram o
    período inteiro nos dois — a definição de "mesma loja".

    `ids` é o recorte da tela (consultor, master, UF, maturidade, severidade, busca).
    Sem ele, a conta valia a rede inteira **mesmo com filtro aplicado**: o SSS nascia
    dentro do contexto do mês, que tem cache e nenhuma noção de filtro, então a carteira
    de um consultor com 5 unidades exibia o crescimento das 60 comparáveis da rede.
    Medido em 2026-08-10 na base de produção: MARISE (24 unidades), GUILHERME (5) e a
    rede inteira (92) devolviam os TRÊS o mesmo `+6,2%` sobre `60 unidades`.

    O que o filtro muda é só a CESTA somada. Ranking e "% vs média da rede" continuam
    saindo da rede inteira — mexer num filtro não pode mudar a posição de ninguém.
    """
    agora, antes = _rede_comparaveis(atual), _rede_comparaveis(ano_anterior)
    base_rotulo = _rede_rotulo_periodo(ano_anterior)
    no_recorte = int(agora["unidade_id"].nunique()) if len(agora) else 0
    if ids is not None:
        alvo = set(ids)
        no_recorte = len(alvo)
        agora = agora[agora["unidade_id"].isin(alvo)]
        antes = antes[antes["unidade_id"].isin(alvo)]
    comuns = sorted(set(agora["unidade_id"]) & set(antes["unidade_id"]))
    if not comuns:
        return {
            "disponivel": False,
            "competencia_base": base_rotulo,
            "unidades": 0,
            "unidades_recorte": no_recorte,
            "unidades_fora": no_recorte,
            "serie": {"meses": [], "var_pct": [], "unidades": []},
        }

    agora = agora[agora["unidade_id"].isin(comuns)]
    antes = antes[antes["unidade_id"].isin(comuns)]
    metricas: dict[str, Any] = {}
    for chave in _REDE_SSS_METRICAS:
        casas = _rede_casas(chave)
        # `min_count=1`: coluna INTEIRAMENTE sem dado tem de sair vazia, não como R$ 0. É o
        # caso da receita de agregadores numa janela parcial — a Growth não a envia desde
        # maio/2025, e o `sum` padrão transformava "não sabemos" em "a rede não fatura com
        # Gympass", que é uma afirmação falsa sobre R$ 5,1 milhões por mês.
        atual_valor = _numf(pd.to_numeric(agora[chave], errors="coerce").sum(min_count=1))
        passado = _numf(pd.to_numeric(antes[chave], errors="coerce").sum(min_count=1))
        metricas[chave] = {
            "atual": _num(atual_valor, casas),
            "ano_anterior": _num(passado, casas),
            "var_pct": (
                _num(100.0 * (atual_valor - passado) / passado, 1) if passado else None
            ),
        }
    return {
        "disponivel": True,
        "competencia_base": base_rotulo,
        "unidades": len(comuns),
        # Quantas unidades o recorte tem e quantas ficaram DE FORA da base comparável.
        # É o número que impede a leitura errada: "+6,2%" de 18 unidades não é o
        # crescimento das 24 do consultor — as outras 6 nem existiam há um ano.
        "unidades_recorte": no_recorte,
        "unidades_fora": max(no_recorte - len(comuns), 0),
        "metricas": metricas,
    }


def _rede_sss_por_unidade(
    atual: pd.DataFrame, ano_anterior: pd.DataFrame
) -> dict[str, dict[str, Any]]:
    """SSS de CADA unidade: o mesmo intervalo, um ano antes, unidade a unidade.

    O agregado responde "a carteira cresceu?"; esta lista responde "por causa de quem?".
    A regra de entrada é a mesma do SSS do recorte — operou o período inteiro nos DOIS
    intervalos —, então uma unidade sem base comparável aparece com `var_pct` nulo em vez
    de sumir: quem lê a lista precisa saber que ela existe e por que não entra na conta.
    """
    base_rotulo = _rede_rotulo_periodo(ano_anterior)
    agora = _rede_comparaveis(atual).set_index("unidade_id")
    antes = _rede_comparaveis(ano_anterior).set_index("unidade_id")
    fat_agora = pd.to_numeric(agora.get("faturamento"), errors="coerce")
    fat_antes = pd.to_numeric(antes.get("faturamento"), errors="coerce")

    saida: dict[str, dict[str, Any]] = {}
    for unidade_id in agora.index:
        valor = _numf(fat_agora.get(unidade_id))
        passado = _numf(fat_antes.get(unidade_id))
        saida[str(unidade_id)] = {
            "competencia_base": base_rotulo,
            "faturamento": _num(valor, 2),
            "ano_anterior": _num(passado, 2),
            "var_pct": (
                _num(100.0 * (valor - passado) / passado, 1)
                if (valor is not None and passado)
                else None
            ),
        }
    return saida


def _rede_comparaveis(quadro: pd.DataFrame) -> pd.DataFrame:
    """Só quem operou o período INTEIRO. Unidade em rampa não é "mesma loja"."""
    if not len(quadro):
        return quadro
    return quadro[quadro["operacao_periodo_cheio"].fillna(False).astype(bool)]


def _rede_rotulo_periodo(quadro: pd.DataFrame) -> str:
    """Rótulo do intervalo de um quadro de período: competência quando ele é um mês
    inteiro, `DD/MM/AAAA a DD/MM/AAAA` quando não é.

    A tela imprime este texto como está. Mês inteiro sai como `2025-08` porque a tela
    já sabe traduzir competência em "Ago/2025"; recorte solto sai por extenso, que é o
    único jeito de dizer "de 1 a 10 de agosto" sem mentir por arredondamento.
    """
    if not len(quadro):
        return ""
    inicio = pd.Timestamp(quadro["periodo_inicio"].iloc[0])
    fim = pd.Timestamp(quadro["periodo_fim"].iloc[0])
    if _eh_mes_inteiro(inicio, fim):
        return str(pd.Period(inicio, freq="M"))
    return f"{inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}"


def _rede_sss_serie(
    cheio: pd.DataFrame, meses: list[str], ids: Collection[str]
) -> dict[str, list[Any]]:
    """SSS mês a mês do recorte, alinhado a `serie_meses`.

    Responde à pergunta que o total não responde numa rede que abre loja: *o
    crescimento é da operação ou da expansão?* Cada ponto recalcula a própria base
    comparável — as unidades do recorte que operaram o mês inteiro em `m` E em `m-12`.
    A cesta muda de um ponto para o outro, e é por isso que `unidades` viaja junto:
    sem ela, uma alta de base pequena parece uma alta da rede.
    """
    if not meses or not len(ids):
        return {"meses": [], "var_pct": [], "unidades": []}

    do_recorte = cheio[
        cheio["unidade_id"].isin(set(ids)) & cheio["operacao_mes_cheio"].fillna(False).astype(bool)
    ]
    grupos = {str(mes): grupo for mes, grupo in do_recorte.groupby("competencia", observed=True)}

    variacoes: list[float | None] = []
    tamanhos: list[int] = []
    for mes in meses:
        base = str(pd.Period(mes, freq="M") - 12)
        agora, antes = grupos.get(mes), grupos.get(base)
        if agora is None or antes is None:
            variacoes.append(None)
            tamanhos.append(0)
            continue
        comuns = set(agora["unidade_id"]) & set(antes["unidade_id"])
        if not comuns:
            variacoes.append(None)
            tamanhos.append(0)
            continue
        soma_agora = pd.to_numeric(
            agora.loc[agora["unidade_id"].isin(comuns), "faturamento"], errors="coerce"
        ).sum()
        soma_antes = pd.to_numeric(
            antes.loc[antes["unidade_id"].isin(comuns), "faturamento"], errors="coerce"
        ).sum()
        variacoes.append(
            _num(100.0 * (soma_agora - soma_antes) / soma_antes, 1) if soma_antes else None
        )
        tamanhos.append(len(comuns))
    return {"meses": meses, "var_pct": variacoes, "unidades": tamanhos}


#: Métricas em REAIS. Vão para a tela com centavo desde 2026-08-10: o time de campo
#: confere o faturamento contra o extrato, e um valor arredondado no servidor não se
#: recupera no cliente — `R$ 18.470` e `R$ 18.470,37` são a mesma linha do payload.
_REDE_METRICAS_EM_REAIS: frozenset[str] = frozenset(
    {
        "faturamento",
        "faturamento_sem_agregador",
        "faturamento_agregador",
        "receita_por_recorrente",
    }
)


def _rede_casas(chave: str) -> int:
    """Casas decimais de uma métrica. UMA definição, usada no quarteto E na série.

    Sem isso, o mesmo churn saía 3,3 no KPI e 3,33 no gráfico logo abaixo — divergência
    de arredondamento que parece divergência de cálculo e manda o operador procurar bug
    onde não há.
    """
    if chave in _REDE_METRICAS_EM_REAIS:
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
        "comparavel": bool(linha.get("operacao_periodo_cheio", linha.get("operacao_mes_cheio", True))),
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
        casas = _rede_casas(chave)
        saida[chave] = {
            "atual": _num(atual, casas),
            "m1": _num(anterior, casas),
            "delta_pct": _num(delta, 1),
        }

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


#: O que dizer do faturamento do PERÍODO, conforme a janela alcance ou não a planilha.
#: A planilha é mensal: ela responde por competência coberta INTEIRA e por mais nada.
_NOTA_DO_PERIODO: dict[str, str] = {
    # Sem travessão, aspas curvas ou reticências tipográficas: estas frases vão para o PDF,
    # que roda no core font do fpdf2 (latin-1) e troca por "?" o que não couber. Ver
    # `pdf_base.ascii_seguro` e o teste de tipografia das notas.
    rede_metricas.ORIGEM_FINANCEIRO: (
        "O período selecionado fecha meses inteiros, então o quarteto do topo e o SSS "
        "saem da MESMA fonte da série: os dois números conversam."
    ),
    rede_metricas.ORIGEM_UX: (
        "O período selecionado é PARCIAL e a planilha do Financeiro é mensal: o quarteto "
        "do topo sai da base Growth, que não traz a receita de agregador desde maio/2025 e "
        "fica cerca de 20% abaixo. O degrau contra o último mês fechado é troca de fonte, "
        "não queda de faturamento."
    ),
    rede_metricas.ORIGEM_MISTA: (
        "O período selecionado mistura meses inteiros com pedaços de mês: os inteiros vêm "
        "da planilha do Financeiro e os pedaços da Growth, que fica cerca de 20% abaixo por "
        "não trazer a receita de agregador. Para comparar fonte contra fonte, escolha um "
        "mês fechado."
    ),
}


def _notas_da_fonte(contexto: dict[str, Any], recorte: pd.DataFrame) -> list[str]:
    """De onde vem o faturamento — e o degrau que a troca de fonte cria na série.

    Sem planilha do Financeiro, a nota é a antiga: a Growth não deduz o TEM SAÚDE e por
    isso não bate com o número do time. Com planilha, o faturamento dos meses fechados
    passa a ser exatamente o dos royalties, e o que precisa ser dito é a COSTURA: mês
    fechado vem do Financeiro (~20% acima da Growth, porque a Growth parou de mandar a
    receita de agregador em maio/2025) e o período em curso continua na Growth. Quem não
    souber disso vai ler o degrau como queda de faturamento.
    """
    fonte = _rede_fonte_faturamento(contexto, recorte)
    origens = set(fonte["por_mes"].values())
    if rede_metricas.ORIGEM_FINANCEIRO not in origens:
        return [
            "O faturamento não bate com a planilha do time: lá o TEM SAÚDE é deduzido "
            "(cerca de 0,7%)."
        ]

    notas = [
        "Faturamento dos meses FECHADOS: planilha do Financeiro, a mesma base sobre a qual "
        "os royalties são cobrados (inclui Gympass e Totalpass, já deduzido o TEM SAÚDE)."
    ]
    # A segunda frase muda com a JANELA escolhida, e tem de mudar: dizer "o topo vem da
    # Growth" quando o operador selecionou um mês fechado seria falso, e é justamente a
    # frase que ele lê para decidir se pode confiar no número.
    notas.append(_NOTA_DO_PERIODO[fonte["periodo"]])
    if rede_metricas.ORIGEM_UX in origens:
        meses_ux = sorted(m for m, o in fonte["por_mes"].items() if o != rede_metricas.ORIGEM_FINANCEIRO)
        notas.append(
            f"{len(meses_ux)} mês(es) da série ainda sem cobertura do Financeiro "
            f"({', '.join(meses_ux[:4])}): esses seguem com o faturamento da Growth."
        )
    if fonte["unidades_sem_par"]:
        sem_par = fonte["unidades_sem_par"]
        notas.append(
            f"{len(sem_par)} unidade(s) faturam na planilha do Financeiro e não existem na "
            f"base Growth ({', '.join(sem_par[:4])}): ficam FORA da carteira, porque sem "
            "alunos, churn e NPS entrariam pela metade."
        )
    return notas


def _rede_notas(contexto: dict[str, Any], recorte: pd.DataFrame) -> list[str]:
    """Notas de método. Toda degradação é DITA, nunca silenciosa."""
    notas = [
        "Receita por recorrente = faturamento sem agregador dos últimos 30 dias "
        "dividido pelos recorrentes ativos. NÃO é o TICKET_MEDIO do PowerBI, que vem "
        "da venda individual (tabela que a API Growth não expõe).",
    ]
    notas.extend(_notas_da_fonte(contexto, recorte))
    if contexto["competencia_diagnostico"] and contexto["competencia_diagnostico"] != contexto["mes"]:
        notas.append(
            f"Diagnóstico e alertas calculados sobre {contexto['competencia_diagnostico']}, "
            "o último mês fechado: mês em curso não acende alerta."
        )
    if len(recorte):
        coluna = "operacao_periodo_cheio" if "operacao_periodo_cheio" in recorte else "operacao_mes_cheio"
        novas = int((~recorte[coluna].fillna(True).astype(bool)).sum())
        if novas:
            notas.append(
                f"{novas} unidade(s) inauguradas dentro do período analisado: aparecem na carteira, "
                "mas ficam fora do ranking, da média da rede e do diagnóstico."
            )
        sem_nps = int((~recorte["nps_valido"].fillna(False).astype(bool)).sum())
        if sem_nps:
            notas.append(f"{sem_nps} unidade(s) sem pesquisa de NPS no período.")
    notas.append(
        "Mesma base ano a ano (SSS) acompanha os filtros: entram só as unidades DO "
        "RECORTE que operaram o mês inteiro nos dois períodos. As demais ficam de fora "
        "da comparação, porque abrir loja não é crescer."
    )
    notas.append(
        "Faixas de faturamento saem sempre do último mês FECHADO: são limiares de mês "
        "inteiro, e o acumulado de poucos dias jogaria a rede toda em Crítico."
    )
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
    inicio: str | None = None,
    fim: str | None = None,
    uf: str | None = None,
    master: str | None = None,
    consultor: str | None = None,
    coorte: str | None = None,
    severidade: str | None = None,
    busca: str | None = None,
    ordenar: str = "prioridade",
    direcao: str = "desc",
) -> dict[str, Any]:
    """Payload da carteira. Uma função só, para que tela, CSV, XLSX e PDF nunca divirjam.

    `inicio`/`fim` são o período de análise (ISO, as duas pontas dentro). `mes` continua
    aceito e vira o intervalo daquela competência: é por ele que o contrato v1 da rota
    `/api/executiva/{uf}` e os links antigos seguem funcionando sem saber que existe
    calendário. Sem nenhum dos três, o padrão é a última competência com dado.
    """
    meses = _rede_meses()
    if not meses:
        _rede_exigir_base()
        raise HTTPException(404, "Base de rede sem competências com dado.")

    if inicio and fim:
        periodo_inicio, periodo_fim = _rede_periodo_valido(inicio, fim)
    else:
        periodo_inicio, periodo_fim = _rede_periodo_do_mes(mes if mes in meses else meses[0])
    contexto = _rede_periodo(periodo_inicio, periodo_fim)
    mes_sel = contexto["mes"]

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

    # O mês fechado viaja em cada unidade porque é ele que sustenta "quem puxa e quem
    # segura": a variação da competência em curso, com poucos dias corridos, é ruído.
    fechado = _rede_faturamento_fechado(contexto)
    ultimo_fechado = contexto["serie_meses"][-1] if contexto["serie_meses"] else None
    sss_unidade = _rede_sss_por_unidade(contexto["atual"], contexto["ano_anterior"])
    for unidade in unidades:
        unidade["fechado"] = fechado.get(
            unidade["id"],
            {"competencia": ultimo_fechado, "faturamento": None, "variacao_pct": None},
        )
        unidade["sss"] = sss_unidade.get(unidade["id"])

    com_coordenada = [u for u in unidades if u["lat"] is not None]
    semaforo = {s: 0 for s in rede_diagnostico.SEVERIDADES}
    for unidade in unidades:
        semaforo[unidade["severidade"]] = semaforo.get(unidade["severidade"], 0) + 1

    total_pagantes = float(pd.to_numeric(recorte["pagantes"], errors="coerce").fillna(0).sum())
    total_agregadores = float(pd.to_numeric(recorte["agregadores"], errors="coerce").fillna(0).sum())
    base_split = total_pagantes + total_agregadores
    referencia = pd.Timestamp(contexto["referencia"])

    # Tudo daqui para baixo é do RECORTE, nunca da rede inteira. `ids` sai da carteira já
    # filtrada e é o que faltava ao SSS.
    ids = list(recorte["unidade_id"])
    kpis = _rede_kpis(recorte, contexto["m1"])
    series = _rede_series(recorte, contexto)
    sss = _rede_sss(contexto["atual"], contexto["ano_anterior"], ids)
    sss["serie"] = _rede_sss_serie(contexto["cheio"], contexto["serie_meses"], ids)

    limite_min, limite_max = _rede_limites()
    return {
        "mes": mes_sel,
        "meses": meses[:_REDE_MESES_NO_SELETOR],
        # O intervalo analisado, e o que ele compara. `referencia` e `referencia_m1`
        # seguem no payload porque o CSV, o XLSX e o PDF os imprimem no cabeçalho — agora
        # são as pontas do período, e não mais um dia-do-mês reconstruído.
        "periodo": {
            "inicio": contexto["inicio"].strftime("%Y-%m-%d"),
            "fim": contexto["fim"].strftime("%Y-%m-%d"),
            "dias": contexto["dias"],
            "mes_inteiro": bool(contexto["mes_inteiro"]),
        },
        "periodo_anterior": {
            "inicio": contexto["inicio_anterior"].strftime("%Y-%m-%d"),
            "fim": contexto["fim_anterior"].strftime("%Y-%m-%d"),
        },
        "limites": {"min": limite_min, "max": limite_max},
        "referencia": referencia.strftime("%d/%m/%Y"),
        "referencia_m1": pd.Timestamp(contexto["fim_anterior"]).strftime("%d/%m/%Y"),
        "mes_completo": bool(contexto["periodo_completo"]),
        "competencia_diagnostico": contexto["competencia_diagnostico"],
        "totais": {
            "rede": int(len(contexto["atual"])),
            "no_recorte": len(unidades),
            "com_coordenada": len(com_coordenada),
        },
        "kpis": kpis,
        "split": {
            "recorrentes": _num(total_pagantes),
            "agregadores": _num(total_agregadores),
            "pct_recorrentes": _num(100 * total_pagantes / base_split, 1) if base_split else None,
            "pct_agregadores": _num(100 * total_agregadores / base_split, 1) if base_split else None,
        },
        "semaforo": semaforo,
        "sss": sss,
        "funil": _rede_funil(recorte, (kpis.get("conversao_pct") or {}).get("atual")),
        "faixas": _rede_faixas(recorte, contexto),
        "coortes": rede_coorte.resumo_coortes(recorte),
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
        # A série AGREGADA do recorte vem pronta do servidor. A tela e o PDF liam cada um
        # a sua soma das sparklines — duas contas para o mesmo gráfico, que é justamente
        # como a mesma unidade acaba com dois números em duas superfícies. `serie_rede` é
        # literalmente `series["faturamento"]`: o painel novo não abriu uma segunda conta.
        "serie_rede": series["faturamento"],
        "series": series,
        "unidades": unidades,
        "notas": _rede_notas(contexto, recorte),
        "fonte_faturamento": _rede_fonte_faturamento(contexto, recorte),
    }


def _rede_fonte_faturamento(
    contexto: dict[str, Any], recorte: pd.DataFrame
) -> dict[str, Any]:
    """De onde veio o faturamento de cada camada da aba.

    A costura é real e a tela tem de dizê-la: os meses FECHADOS vêm da planilha do
    Financeiro (base dos royalties, ~20% acima da Growth porque inclui a receita de
    agregador que a Growth parou de mandar em maio/2025), e o período em curso continua na
    Growth, porque a planilha é mensal. Sem o rótulo, o degrau entre o último mês fechado e
    o mês corrente parece queda de faturamento.
    """
    cheio = contexto["cheio"]
    meses: list[str] = contexto["serie_meses"]
    if not len(cheio) or "origem_faturamento" not in cheio.columns:
        return {"por_mes": {}, "periodo": rede_metricas.ORIGEM_UX, "unidades_sem_par": []}

    do_recorte = cheio[cheio["unidade_id"].isin(set(recorte["unidade_id"]))]
    por_mes: dict[str, str] = {}
    for mes in meses:
        origens = set(do_recorte.loc[do_recorte["competencia"] == mes, "origem_faturamento"])
        if origens:
            por_mes[mes] = origens.pop() if len(origens) == 1 else rede_metricas.ORIGEM_MISTA
    return {
        "por_mes": por_mes,
        # O quarteto do topo segue a JANELA escolhida, e a planilha só alcança competência
        # coberta inteira: mês fechado selecionado sai `financeiro`; mês em curso, `ux`.
        "periodo": _origem_dominante(recorte),
        "unidades_sem_par": list(cheio.attrs.get("financeiro_sem_par", [])),
    }


def _origem_dominante(quadro: pd.DataFrame) -> str:
    """Origem única do recorte, ou `misto` quando as unidades não concordam."""
    if not len(quadro) or "origem_faturamento" not in quadro.columns:
        return rede_metricas.ORIGEM_UX
    origens = set(quadro["origem_faturamento"].dropna())
    if not origens:
        return rede_metricas.ORIGEM_UX
    return origens.pop() if len(origens) == 1 else rede_metricas.ORIGEM_MISTA


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
    inicio: str | None = None,
    fim: str | None = None,
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
        mes, inicio, fim, uf, master, consultor, coorte, severidade, busca, ordenar, direcao
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
        # A ficha mostra faturamento em quatro lugares (quarteto, série de 12 meses, rosca e
        # benchmark de coorte) e o PDF dela vai para o franqueado. Sem isto, o rodapé do PDF
        # continuava creditando a Growth por um número que já vem do Financeiro.
        "fonte_faturamento": _rede_fonte_faturamento(contexto, linhas),
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
    inicio: str | None = None,
    fim: str | None = None,
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
        mes, inicio, fim, uf, master, consultor, coorte, severidade, busca, ordenar, direcao
    )
    return _anexo(
        rede_export.carteira_csv(payload),
        _rede_nome_arquivo("carteira_rede_ultra", payload, "csv"),
        "text/csv; charset=utf-8",
    )


@app.get("/api/rede/carteira.xlsx")
def rede_carteira_xlsx(
    mes: str | None = None,
    inicio: str | None = None,
    fim: str | None = None,
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
        mes, inicio, fim, uf, master, consultor, coorte, severidade, busca, ordenar, direcao
    )
    return _anexo(
        rede_export.carteira_xlsx(payload),
        _rede_nome_arquivo("carteira_rede_ultra", payload, "xlsx"),
        XLSX_MEDIA_TYPE,
    )


@app.get("/api/rede/carteira.pdf")
def rede_carteira_pdf(
    mes: str | None = None,
    inicio: str | None = None,
    fim: str | None = None,
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
        mes, inicio, fim, uf, master, consultor, coorte, severidade, busca, ordenar, direcao
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
