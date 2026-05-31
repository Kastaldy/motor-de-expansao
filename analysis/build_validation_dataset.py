"""Monta o dataset rotulado de validacao (BLK-SCORE-01).

Uma linha por unidade existente (Ultra + Skyfit + Engenharia do Corpo), ligada ao
hex H3 res.7 onde caiu, aos 4 scores do projeto (M1 ``score_priorizacao``,
censitario ``score_setor_2022_calibrado``, residual ``score_oportunidade_residual``,
dominio ``score_dominio_hibrido``) e ao desfecho observado (alunos recorrentes,
sinal Wellhub). Insumo do backtest BLK-SCORE-02.

READ-ONLY sobre o M1: este modulo apenas LE fontes oficiais/staging/validacao e
grava artefatos derivados em ``data/analysis/``. Nao recalcula score nem escreve
em qualquer artefato oficial do M1.

Execucao::

    python -m analysis.build_validation_dataset

Gera:
    data/analysis/dataset_validacao.parquet      (gitignored; pode conter PII interna)
    data/analysis/relatorio_auditoria_rotulo.md  (gitignored; apenas agregados, sem PII)

Decisoes de fonte/chave seguem ``context/handoff.md`` (Planner rev.2, gate humano
2026-05-30): Skyfit usa SOMENTE ``concorrentes/unidades_skyfit.csv`` para coords,
com join por nome em cascata (exato -> fuzzy difflib -> centroide cidade+UF).
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
import unicodedata
import warnings
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

H3_RESOLUTION = 7

# Faixa Brasil para sanidade de coordenada (folgada na fronteira norte).
LAT_MIN, LAT_MAX = -34.0, 6.0
LNG_MIN, LNG_MAX = -74.0, -32.0

REDES = ("ultra", "skyfit", "engcorpo")

# Paths default (relativos a raiz do repo).
REPO_ROOT = Path(__file__).resolve().parents[1]
ULTRA_PARQUET = REPO_ROOT / "data" / "staging" / "unidades_ultra_performance_hex.parquet"
SKYFIT_DESFECHO_XLSX = REPO_ROOT / "data" / "validacao" / "Sky Fit dados.xlsx"
SKYFIT_COORDS_CSV = REPO_ROOT / "concorrentes" / "unidades_skyfit.csv"
ENGCORPO_XLSX = REPO_ROOT / "data" / "validacao" / "academias_engenharia_do_corpo.xlsx"
# Fonte canonica de coordenadas EngCorpo (raiz). A copia em
# ``concorrentes/Unidades/unidades_engenharia_do_corpo.csv`` e byte-identica
# (replica/fallback documentado) e NAO e lida (evita duplicar/ambiguidade).
ENGCORPO_COORDS_CSV = REPO_ROOT / "concorrentes" / "unidades_engenharia_do_corpo.csv"
# Staging: fonte de hex SECUNDARIA/fallback (hex_id_res7 ja resolvido por nome cru).
ENGCORPO_STAGING = REPO_ROOT / "data" / "staging" / "concorrentes_mapeados.parquet"
PRIORIZADOS_PARQUET = REPO_ROOT / "data" / "staging" / "brasil_priorizados.parquet"
MERCADO_PARQUET = REPO_ROOT / "data" / "staging" / "hexagonos_mercado_mapeado.parquet"
DOMINIO_PARQUET = REPO_ROOT / "data" / "outputs" / "plano_expansao_dominio.parquet"

OUT_DIR = REPO_ROOT / "data" / "analysis"
OUT_PARQUET = OUT_DIR / "dataset_validacao.parquet"
OUT_REPORT = OUT_DIR / "relatorio_auditoria_rotulo.md"

DEFAULT_FUZZY_CUTOFF = 0.84

# Colunas do esquema interno comum (ordem canonica do parquet final).
SCHEMA_COLUMNS: tuple[str, ...] = (
    "rede",
    "unidade_id",
    "nome_unidade",
    "lat",
    "lng",
    "hex_id",
    "hex_resolvido",
    "hex_origem",
    "hex_precisao",
    "cod_municipio",
    "nome_municipio",
    "uf",
    "score_priorizacao",
    "score_priorizacao_disponivel",
    "score_setor_2022_calibrado",
    "score_setor_2022_disponivel",
    "score_oportunidade_residual",
    "score_residual_disponivel",
    "score_dominio_hibrido",
    "score_dominio_disponivel",
    "alunos_recorrentes",
    "alunos_origem",
    "alunos_medido",
    "faturamento",
    "metragem_m2",
    "sinal_wellhub",
    "n_parcerias_wellhub",
    "rotulo_casado",
    "rotulo_origem",
    "rotulo_confiabilidade",
    "maturacao_status",
)

MATURACAO_INDISPONIVEL = "maturacao_indisponivel"

# Mapeamento de nome de estado por extenso -> UF (usado se a fonte trouxer extenso).
_ESTADO_PARA_UF = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM",
    "bahia": "BA", "ceara": "CE", "distrito federal": "DF",
    "espirito santo": "ES", "goias": "GO", "maranhao": "MA",
    "mato grosso": "MT", "mato grosso do sul": "MS", "minas gerais": "MG",
    "para": "PA", "paraiba": "PB", "parana": "PR", "pernambuco": "PE",
    "piaui": "PI", "rio de janeiro": "RJ", "rio grande do norte": "RN",
    "rio grande do sul": "RS", "rondonia": "RO", "roraima": "RR",
    "santa catarina": "SC", "sao paulo": "SP", "sergipe": "SE",
    "tocantins": "TO",
}


# --------------------------------------------------------------------------- #
# Helpers de baixo nivel
# --------------------------------------------------------------------------- #
def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )


def normalize_name(s: object) -> str:
    """Normaliza nome para chave de join determinista.

    NFKD -> remove acentos -> casefold -> remove sufixos societarios/genericos
    -> remove pontuacao -> colapsa espacos -> strip.
    """
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    text = _strip_accents(str(s)).casefold()
    # remove pontuacao por espaco
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [t for t in text.split() if t]
    drop = {"ltda", "me", "eireli", "sa", "academia", "unidade", "ec"}
    tokens = [t for t in tokens if t not in drop]
    return " ".join(tokens).strip()


def normalize_name_skyfit(s: object) -> str:
    """Normaliza nome Skyfit, removendo marca e sufixo de UF entre parenteses.

    Trata os dois lados do join: ``NOMENCLATURA UNIDADE`` (desfecho, ex.:
    "SKYFIT ACADEMIA - ILHA DO GOVERNADOR") e ``nome_unidade`` (coords, ex.:
    "Ilha do Governador (RJ)" ou "Aguas Claras - Brasilia (DF)").
    """
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    text = _strip_accents(str(s)).casefold()
    # remove sufixo de UF entre parenteses no fim, ex.: "(rj)"
    text = re.sub(r"\(\s*[a-z]{2}\s*\)\s*$", " ", text)
    # remove tokens de marca/genericos
    text = re.sub(r"sky\s*fit", " ", text)
    text = re.sub(r"\bskyfit\b", " ", text)
    text = re.sub(r"\bacademia\b", " ", text)
    # pontuacao -> espaco
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [t for t in text.split() if t]
    return " ".join(tokens).strip()


def _city_uf_from_coord_name(nome: object) -> tuple[str, str]:
    """Extrai (cidade_norm, uf) de um ``nome_unidade`` de coords Skyfit.

    Padrao tipico: "Bairro - Cidade (UF)" ou "Cidade (UF)". Quando ha um
    separador (hifen ou travessao), a cidade e o ultimo segmento antes do "(UF)".
    """
    if nome is None or (isinstance(nome, float) and pd.isna(nome)):
        return "", ""
    raw = str(nome)
    uf = ""
    m = re.search(r"\(\s*([A-Za-z]{2})\s*\)\s*$", raw)
    if m:
        uf = m.group(1).upper()
        raw = raw[: m.start()]
    # separadores possiveis: travessao, hifen
    parts = re.split(r"[–—\-]", raw)
    cidade = parts[-1] if parts else raw
    return normalize_name(cidade), uf


def normalize_name_engcorpo(s: object) -> str:
    """Normaliza nome EngCorpo, removendo o prefixo de marca ``EC``/``ECB``.

    Trata os dois lados do join: planilha (``EC - VACARIA, RS``,
    ``ECB - DESVIO RIZZO, RS``) vs CSV/staging (``Vacaria, RS``,
    ``Desvio Rizzo - Caxias do Sul, RS``).

    Regra: NFKD/casefold -> remove o PREFIXO inicial ``ec``/``ecb`` (com/sem
    hifen/travessao/dois-pontos e com/sem espaco), ancorado em ``^`` para nunca
    corromper um ``ec`` no meio do nome -> delega ao ``normalize_name`` (que ja
    dropa o token isolado ``ec``, alem de NFKD/pontuacao/sufixos/colapso).
    Deterministico.
    """
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    text = _strip_accents(str(s)).casefold()
    # remove SO o prefixo de marca no inicio (ancora ^): ec/ecb com separador opcional
    text = re.sub(r"^\s*ec[bv]?\s*[-–—:]?\s*", " ", text)
    return normalize_name(text)


def _city_uf_from_engcorpo_name(nome: object) -> tuple[str, str]:
    """Extrai (cidade_norm, uf) de um ``nome_unidade`` EngCorpo.

    Convencao: ``Cidade, UF`` ou ``Prefixo - Cidade, UF`` (virgula antes da UF),
    valendo para a planilha (``EC - VACARIA, RS``) e o CSV/staging
    (``Diamantino - Caxias do Sul, RS``). A UF e o sufixo de 2 letras apos a
    ultima virgula; a cidade e o ultimo segmento apos hifen/travessao. O prefixo
    de marca ``EC``/``ECB`` (planilha) vira token isolado e e dropado por
    ``normalize_name``, entao a cidade normalizada coincide entre os lados.
    """
    if nome is None or (isinstance(nome, float) and pd.isna(nome)):
        return "", ""
    raw = str(nome)
    uf = ""
    m = re.search(r",\s*([A-Za-z]{2})\s*$", raw)
    if m:
        uf = m.group(1).upper()
        raw = raw[: m.start()]
    # separadores possiveis: travessao, hifen -> cidade e o ultimo segmento
    parts = re.split(r"[–—\-]", raw)
    cidade = parts[-1] if parts else raw
    return normalize_name(cidade), uf


def _uf_to_sigla(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if re.fullmatch(r"[A-Za-z]{2}", text):
        return text.upper()
    key = _strip_accents(text).casefold().strip()
    return _ESTADO_PARA_UF.get(key, text.upper()[:2])


def _coord_in_brazil(lat: object, lng: object) -> bool:
    if pd.isna(lat) or pd.isna(lng):
        return False
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (TypeError, ValueError):
        return False
    return LAT_MIN <= lat_f <= LAT_MAX and LNG_MIN <= lng_f <= LNG_MAX


def latlng_to_h3(lat: float, lng: float, resolution: int = H3_RESOLUTION) -> str | None:
    """Espelha o helper canonico ``_latlng_to_h3`` (h3 v4 / fallback v3).

    Degrada para ``None`` se h3 estiver ausente ou a coord for invalida
    (NaN ou fora da faixa Brasil) -> nunca derruba o pipeline.
    """
    if not _coord_in_brazil(lat, lng):
        return None
    try:
        import h3
    except Exception:
        return None
    try:
        if hasattr(h3, "latlng_to_cell"):
            return h3.latlng_to_cell(float(lat), float(lng), resolution)
        return h3.geo_to_h3(float(lat), float(lng), resolution)
    except Exception:
        return None


def _slug(*parts: object) -> str:
    chunks = [normalize_name(p) for p in parts if p is not None and str(p).strip()]
    chunks = [c for c in chunks if c]
    return "__".join(chunks).replace(" ", "-") if chunks else "sem-id"


def _empty_schema_frame() -> pd.DataFrame:
    return pd.DataFrame({col: pd.Series(dtype="object") for col in SCHEMA_COLUMNS})


# --------------------------------------------------------------------------- #
# Leitores por rede (read-only)
# --------------------------------------------------------------------------- #
def load_ultra(path: Path = ULTRA_PARQUET) -> pd.DataFrame:
    """Le o parquet de performance Ultra -> esquema interno parcial.

    Score M1 (``score_priorizacao``) ja vem embutido; demais scores e
    ``cod_municipio``/``nome_municipio`` virao por join por ``hex_id``.
    """
    df = pd.read_parquet(path)
    out = pd.DataFrame()
    out["rede"] = ["ultra"] * len(df)
    out["nome_unidade"] = df.get("unidade")
    out["lat"] = pd.to_numeric(df.get("lat"), errors="coerce")
    out["lng"] = pd.to_numeric(df.get("lng"), errors="coerce")
    out["hex_id"] = df.get("hex_id_res7")
    out["uf"] = df.get("uf")
    # scores embutidos (M1)
    out["score_priorizacao"] = pd.to_numeric(df.get("score_priorizacao"), errors="coerce")
    # desfecho cru
    out["alunos_total"] = pd.to_numeric(df.get("alunos_total"), errors="coerce")
    out["ativos_pag"] = pd.to_numeric(df.get("ativos_pag"), errors="coerce")
    out["alunos_gympass"] = pd.to_numeric(df.get("alunos_gympass"), errors="coerce")
    out["alunos_totalpass"] = pd.to_numeric(df.get("alunos_totalpass"), errors="coerce")
    out["faturamento"] = pd.to_numeric(df.get("faturamento"), errors="coerce")
    out["metragem_m2"] = pd.to_numeric(df.get("metragem"), errors="coerce")

    out["unidade_id"] = [
        f"ultra__{_slug(n)}__{i}" for i, n in enumerate(out["nome_unidade"])
    ]
    return out


def match_skyfit_coords(
    desfecho: pd.DataFrame,
    coords: pd.DataFrame,
    *,
    fuzzy_cutoff: float = DEFAULT_FUZZY_CUTOFF,
) -> pd.DataFrame:
    """Casa desfecho Skyfit x coords por NOME em cascata.

    Tiers: nome_exato -> nome_fuzzy (difflib) -> cidade_centroide (cidade+UF).
    Preenche ``lat``/``lng``/``hex_origem``/``hex_precisao`` (sem alterar o desfecho).
    Determinista (sem dependencia de ordenacao ambigua).
    """
    res = desfecho.copy().reset_index(drop=True)
    res["_nome_norm"] = res["nome_unidade"].map(normalize_name_skyfit)
    res["_uf"] = res["uf"].map(_uf_to_sigla)
    res["_cidade_norm"] = res["cidade"].map(normalize_name)

    cd = coords.copy().reset_index(drop=True)
    cd["_nome_norm"] = cd["nome_unidade"].map(normalize_name_skyfit)
    cidade_uf = cd["nome_unidade"].map(_city_uf_from_coord_name)
    cd["_cidade_norm"] = [c for c, _ in cidade_uf]
    cd["_uf"] = [u for _, u in cidade_uf]
    cd["lat"] = pd.to_numeric(cd["latitude"], errors="coerce")
    cd["lng"] = pd.to_numeric(cd["longitude"], errors="coerce")

    # indices de lookup (primeira ocorrencia ganha; determinista pela ordem do arquivo)
    by_name: dict[str, int] = {}
    for i, nm in enumerate(cd["_nome_norm"]):
        if nm and nm not in by_name:
            by_name[nm] = i
    by_city: dict[tuple[str, str], int] = {}
    for i, (cc, uu) in enumerate(zip(cd["_cidade_norm"], cd["_uf"], strict=False)):
        key = (cc, uu)
        if cc and key not in by_city:
            by_city[key] = i
    coord_name_list = list(by_name.keys())

    lat_out: list[float | None] = []
    lng_out: list[float | None] = []
    origem_out: list[str] = []
    precisao_out: list[str] = []

    for _, row in res.iterrows():
        nm = row["_nome_norm"]
        idx: int | None = None
        origem = "nao_resolvido"
        precisao = "indisponivel"

        # Tier 1: nome exato
        if nm and nm in by_name:
            idx = by_name[nm]
            origem, precisao = "nome_exato", "unidade"
        else:
            # Tier 2: fuzzy deterministico
            if nm:
                cand = difflib.get_close_matches(nm, coord_name_list, n=1, cutoff=fuzzy_cutoff)
                if cand:
                    idx = by_name[cand[0]]
                    origem, precisao = "nome_fuzzy", "unidade"
            # Tier 3: centroide cidade+UF
            if idx is None:
                key = (row["_cidade_norm"], row["_uf"])
                if key in by_city:
                    idx = by_city[key]
                    origem, precisao = "cidade_centroide", "cidade"

        if idx is not None:
            lat_val = cd.at[idx, "lat"]
            lng_val = cd.at[idx, "lng"]
            if _coord_in_brazil(lat_val, lng_val):
                lat_out.append(float(lat_val))
                lng_out.append(float(lng_val))
                origem_out.append(origem)
                precisao_out.append(precisao)
                continue
        lat_out.append(None)
        lng_out.append(None)
        origem_out.append("nao_resolvido")
        precisao_out.append("indisponivel")

    res["lat"] = lat_out
    res["lng"] = lng_out
    res["hex_origem"] = origem_out
    res["hex_precisao"] = precisao_out
    res = res.drop(columns=["_nome_norm", "_uf", "_cidade_norm"])
    return res


def match_engcorpo_coords(
    desfecho: pd.DataFrame,
    coords: pd.DataFrame,
    *,
    fuzzy_cutoff: float = DEFAULT_FUZZY_CUTOFF,
) -> pd.DataFrame:
    """Casa desfecho EngCorpo x coords (CSV) por NOME em cascata determinista.

    Espelha ``match_skyfit_coords``, com normalizacao EngCorpo-especifica
    (``normalize_name_engcorpo`` remove o prefixo ``EC``/``ECB``). Tiers:

    - ``nome_exato``  : nome normalizado bate exatamente -> precisao ``unidade``.
    - ``nome_fuzzy``  : difflib ``get_close_matches`` (cutoff ``fuzzy_cutoff``,
      default ``DEFAULT_FUZZY_CUTOFF=0.84``) COM concordancia OBRIGATORIA
      cidade+UF (rejeita o candidato se cidade OU UF divergirem -> guardrail
      anti-falso-positivo do bloco) -> precisao ``unidade``.
    - ``cidade_centroide`` : cidade+UF batem -> precisao ``cidade``.

    Em todos os tiers a coord e validada por ``_coord_in_brazil`` antes de
    aceitar (protege coords invertidas, ex.: ``CT Areias`` com lat/lng trocados).
    Sem match (ou coord fora da faixa) -> ``nao_resolvido`` / lat/lng None.
    Deterministico: lookups por dict na ordem do arquivo (``keep="first"``),
    sem seed.
    """
    res = desfecho.copy().reset_index(drop=True)
    res["_nome_norm"] = res["nome_unidade"].map(normalize_name_engcorpo)
    cidade_uf_d = res["nome_unidade"].map(_city_uf_from_engcorpo_name)
    res["_cidade_norm"] = [c for c, _ in cidade_uf_d]
    res["_uf"] = [u for _, u in cidade_uf_d]

    cd = coords.copy().reset_index(drop=True)
    cd["_nome_norm"] = cd["nome_unidade"].map(normalize_name_engcorpo)
    cidade_uf_c = cd["nome_unidade"].map(_city_uf_from_engcorpo_name)
    cd["_cidade_norm"] = [c for c, _ in cidade_uf_c]
    cd["_uf"] = [u for _, u in cidade_uf_c]
    cd["lat"] = pd.to_numeric(cd["latitude"], errors="coerce")
    cd["lng"] = pd.to_numeric(cd["longitude"], errors="coerce")

    # indices de lookup (primeira ocorrencia ganha; determinista pela ordem do arquivo)
    by_name: dict[str, int] = {}
    for i, nm in enumerate(cd["_nome_norm"]):
        if nm and nm not in by_name:
            by_name[nm] = i
    by_city: dict[tuple[str, str], int] = {}
    for i, (cc, uu) in enumerate(zip(cd["_cidade_norm"], cd["_uf"], strict=False)):
        key = (cc, uu)
        if cc and key not in by_city:
            by_city[key] = i
    coord_name_list = list(by_name.keys())

    lat_out: list[float | None] = []
    lng_out: list[float | None] = []
    origem_out: list[str] = []
    precisao_out: list[str] = []

    for _, row in res.iterrows():
        nm = row["_nome_norm"]
        idx: int | None = None
        origem = "nao_resolvido"
        precisao = "indisponivel"

        # Tier 1: nome exato
        if nm and nm in by_name:
            idx = by_name[nm]
            origem, precisao = "nome_exato", "unidade"
        else:
            # Tier 2: fuzzy deterministico COM concordancia OBRIGATORIA cidade+UF
            if nm:
                cand = difflib.get_close_matches(nm, coord_name_list, n=1, cutoff=fuzzy_cutoff)
                if cand:
                    cidx = by_name[cand[0]]
                    if (
                        cd.at[cidx, "_cidade_norm"] == row["_cidade_norm"]
                        and cd.at[cidx, "_uf"] == row["_uf"]
                        and row["_cidade_norm"]
                    ):
                        idx = cidx
                        origem, precisao = "nome_fuzzy", "unidade"
            # Tier 3: centroide cidade+UF
            if idx is None:
                key = (row["_cidade_norm"], row["_uf"])
                if key in by_city:
                    idx = by_city[key]
                    origem, precisao = "cidade_centroide", "cidade"

        if idx is not None:
            lat_val = cd.at[idx, "lat"]
            lng_val = cd.at[idx, "lng"]
            if _coord_in_brazil(lat_val, lng_val):
                lat_out.append(float(lat_val))
                lng_out.append(float(lng_val))
                origem_out.append(origem)
                precisao_out.append(precisao)
                continue
        lat_out.append(None)
        lng_out.append(None)
        origem_out.append("nao_resolvido")
        precisao_out.append("indisponivel")

    res["lat"] = lat_out
    res["lng"] = lng_out
    res["hex_origem"] = origem_out
    res["hex_precisao"] = precisao_out
    res = res.drop(columns=["_nome_norm", "_uf", "_cidade_norm"])
    return res


def load_skyfit(
    desfecho_xlsx: Path = SKYFIT_DESFECHO_XLSX,
    coords_csv: Path = SKYFIT_COORDS_CSV,
    *,
    fuzzy_cutoff: float = DEFAULT_FUZZY_CUTOFF,
) -> pd.DataFrame:
    """Le desfecho Skyfit (header=3) + coords (sep=';', utf-8-sig).

    Match por nome em cascata; deriva hex via ``latlng_to_h3``. Esquema interno.
    """
    raw = pd.read_excel(desfecho_xlsx, sheet_name="Sell Out", header=3)
    desf = pd.DataFrame()
    id_sky = raw.get("ID SKY")
    desf["_id_sky_raw"] = id_sky
    desf["nome_unidade"] = raw.get("NOMENCLATURA UNIDADE")
    desf["cidade"] = raw.get("CIDADE")
    desf["uf"] = raw.get("ESTADO")
    desf["alunos_evo"] = pd.to_numeric(raw.get("Alunos EVO"), errors="coerce")
    desf["alunos_gympass"] = pd.to_numeric(raw.get("Alunos Gympass"), errors="coerce")
    desf["alunos_totalpass"] = pd.to_numeric(raw.get("Alunos TotalPass"), errors="coerce")

    coords = pd.read_csv(coords_csv, sep=";", encoding="utf-8-sig")

    matched = match_skyfit_coords(desf, coords, fuzzy_cutoff=fuzzy_cutoff)

    out = pd.DataFrame()
    out["rede"] = ["skyfit"] * len(matched)
    out["nome_unidade"] = matched["nome_unidade"]
    out["lat"] = matched["lat"]
    out["lng"] = matched["lng"]
    out["hex_id"] = None  # derivado em resolve_hex
    out["hex_origem"] = matched["hex_origem"]
    out["hex_precisao"] = matched["hex_precisao"]
    out["uf"] = matched["uf"].map(_uf_to_sigla)
    out["alunos_evo"] = matched["alunos_evo"]
    out["alunos_gympass"] = matched["alunos_gympass"]
    out["alunos_totalpass"] = matched["alunos_totalpass"]

    # unidade_id: usa ID SKY normalizado quando disponivel; fallback slug
    def _norm_id(v: object, fallback: str) -> str:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return f"skyfit__{fallback}"
        s = str(v).strip()
        if s.endswith(".0"):
            s = s[:-2]
        s = s.strip()
        return f"skyfit__{s}" if s else f"skyfit__{fallback}"

    ids: list[str] = []
    seen: dict[str, int] = {}
    for i, v in enumerate(matched["_id_sky_raw"]):
        base = _norm_id(v, _slug(matched.at[i, "nome_unidade"]) or str(i))
        # desambigua duplicatas de ID SKY de forma determinista
        if base in seen:
            seen[base] += 1
            base = f"{base}#{seen[base]}"
        else:
            seen[base] = 0
        ids.append(base)
    out["unidade_id"] = ids
    return out


def join_label_by_name(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    left_key: str = "nome_norm",
    right_key: str = "nome_norm",
    value_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Left join por nome normalizado; cria ``rotulo_casado``.

    Determinista: a primeira ocorrencia do lado direito por chave ganha.
    Nao-casados -> ``value_cols`` nulos + ``rotulo_casado=False`` (nunca quebra).
    """
    value_cols = value_cols or [c for c in right.columns if c != right_key]
    right_dedup = right.drop_duplicates(subset=[right_key], keep="first")
    lookup = right_dedup.set_index(right_key)

    out = left.copy().reset_index(drop=True)
    casado: list[bool] = []
    collected: dict[str, list[object]] = {c: [] for c in value_cols}
    for key in out[left_key]:
        if key and key in lookup.index:
            casado.append(True)
            row = lookup.loc[key]
            for c in value_cols:
                collected[c].append(row[c])
        else:
            casado.append(False)
            for c in value_cols:
                collected[c].append(None)
    for c in value_cols:
        out[c] = collected[c]
    out["rotulo_casado"] = casado
    return out


def load_engcorpo(
    planilha: Path = ENGCORPO_XLSX,
    coords_csv: Path = ENGCORPO_COORDS_CSV,
    staging: Path = ENGCORPO_STAGING,
    *,
    fuzzy_cutoff: float = DEFAULT_FUZZY_CUTOFF,
) -> pd.DataFrame:
    """Le planilha EngCorpo (desfecho) + CSV coords (hex primario) -> esquema interno.

    Hex resolvido em cascata determinista por ``match_engcorpo_coords`` sobre o
    CSV canonico (nome_exato -> nome_fuzzy com cidade+UF -> cidade_centroide).
    Quando o CSV nao resolve, cai para o ``hex_id_res7`` do staging via join por
    nome (``normalize_name_engcorpo``) -> ``hex_staging``. Ordem de prioridade de
    hex: nome_exato/nome_fuzzy/cidade_centroide (CSV) -> hex_staging ->
    nao_resolvido. Nao-casados sao marcados, nunca descartados.
    """
    plan = pd.read_excel(planilha, sheet_name="Academias")
    plan_df = pd.DataFrame()
    plan_df["nome_unidade"] = plan.get("Unidade")
    plan_df["metragem_m2"] = pd.to_numeric(plan.get("Metragem M²"), errors="coerce")
    plan_df["alunos_totais"] = pd.to_numeric(plan.get("Alunos Totais"), errors="coerce")
    plan_df["alunos_gympass"] = pd.to_numeric(plan.get("Total Alunos Gympass"), errors="coerce")

    coords = pd.read_csv(coords_csv, sep=";", encoding="utf-8-sig")
    matched = match_engcorpo_coords(plan_df, coords, fuzzy_cutoff=fuzzy_cutoff)

    # Staging como fallback de hex por nome (so para os nao resolvidos pelo CSV).
    st = pd.read_parquet(staging)
    st = st[(st["rede"] == "engenharia_do_corpo") & (st["status_registro"] == "valido")].copy()
    st["nome_norm"] = st["nome_unidade"].map(normalize_name_engcorpo)
    st_slim = st[["nome_norm", "hex_id_res7"]].copy()
    st_slim = st_slim[st_slim["nome_norm"].astype(bool)]
    staging_hex: dict[str, object] = {}
    for nm, hx in zip(st_slim["nome_norm"], st_slim["hex_id_res7"], strict=False):
        if nm and nm not in staging_hex and hx is not None and str(hx).strip():
            staging_hex[nm] = hx

    out = pd.DataFrame()
    out["rede"] = ["engcorpo"] * len(matched)
    out["nome_unidade"] = matched["nome_unidade"]
    out["lat"] = pd.to_numeric(matched["lat"], errors="coerce")
    out["lng"] = pd.to_numeric(matched["lng"], errors="coerce")
    out["hex_id"] = None  # CSV resolve via lat/lng em resolve_hex
    out["hex_origem"] = matched["hex_origem"]
    out["hex_precisao"] = matched["hex_precisao"]
    out["uf"] = None  # derivado do join de score por hex_id

    # Fallback staging: so quando o CSV nao resolveu.
    hex_ids: list[object] = list(out["hex_id"])
    origens: list[str] = list(out["hex_origem"])
    precisoes: list[str] = list(out["hex_precisao"])
    for i, nome in enumerate(matched["nome_unidade"]):
        if origens[i] == "nao_resolvido":
            nm = normalize_name_engcorpo(nome)
            if nm in staging_hex:
                hex_ids[i] = staging_hex[nm]
                origens[i] = "hex_staging"
                precisoes[i] = "unidade"
    out["hex_id"] = hex_ids
    out["hex_origem"] = origens
    out["hex_precisao"] = precisoes

    out["metragem_m2"] = matched["metragem_m2"]
    out["alunos_totais"] = matched["alunos_totais"]
    out["alunos_gympass"] = matched["alunos_gympass"]
    out["rotulo_casado_staging"] = [o != "nao_resolvido" for o in origens]
    out["unidade_id"] = [f"engcorpo__{_slug(n)}__{i}" for i, n in enumerate(out["nome_unidade"])]
    return out


# --------------------------------------------------------------------------- #
# Resolucao de hex e join de scores
# --------------------------------------------------------------------------- #
def resolve_hex(df: pd.DataFrame, res: int = H3_RESOLUTION) -> pd.DataFrame:
    """Preenche ``hex_id`` (derivando de lat/lng quando ausente) e ``hex_resolvido``.

    Define ``hex_origem``/``hex_precisao`` quando ainda nao definidos (Ultra/EngCorpo).
    """
    out = df.copy().reset_index(drop=True)
    if "hex_id" not in out.columns:
        out["hex_id"] = None
    if "hex_origem" not in out.columns:
        out["hex_origem"] = None
    if "hex_precisao" not in out.columns:
        out["hex_precisao"] = None

    hex_ids: list[str | None] = []
    origens: list[str] = []
    precisoes: list[str] = []
    for _, row in out.iterrows():
        hx = row.get("hex_id")
        origem = row.get("hex_origem")
        precisao = row.get("hex_precisao")
        has_existing = hx is not None and not (isinstance(hx, float) and pd.isna(hx)) and str(hx).strip()
        if has_existing:
            hex_ids.append(str(hx))
            origens.append(origem if isinstance(origem, str) and origem else "hex_staging")
            precisoes.append(precisao if isinstance(precisao, str) and precisao else "unidade")
            continue
        # derivar de lat/lng
        derived = latlng_to_h3(row.get("lat"), row.get("lng"), res)
        if derived:
            hex_ids.append(derived)
            origens.append(origem if isinstance(origem, str) and origem and origem != "nao_resolvido" else "latlng")
            precisoes.append(precisao if isinstance(precisao, str) and precisao and precisao != "indisponivel" else "unidade")
        else:
            hex_ids.append(None)
            origens.append("nao_resolvido")
            precisoes.append("indisponivel")

    out["hex_id"] = hex_ids
    out["hex_origem"] = origens
    out["hex_precisao"] = precisoes
    out["hex_resolvido"] = [h is not None for h in hex_ids]
    return out


def _load_score_source(path: Path, cols: Iterable[str]) -> pd.DataFrame:
    available = pd.read_parquet(path, columns=None).columns
    use = [c for c in cols if c in available]
    df = pd.read_parquet(path, columns=use)
    # cod_municipio sempre string (preserva zeros a esquerda)
    if "cod_municipio" in df.columns:
        df["cod_municipio"] = df["cod_municipio"].astype("string")
    df = df.drop_duplicates(subset=["hex_id"], keep="first")
    return df


def join_scores(
    df: pd.DataFrame,
    *,
    priorizados: pd.DataFrame,
    mercado: pd.DataFrame,
    dominio: pd.DataFrame,
) -> pd.DataFrame:
    """Left join dos 4 scores por ``hex_id``; cria flags ``score_*_disponivel``.

    Ausencia -> nulo + flag False. Nao recalcula score; apenas leitura/join.
    ``cod_municipio``/``nome_municipio``/``uf`` consolidados a partir do mercado
    (com fallback priorizados), sem sobrescrever valores ja presentes.
    """
    out = df.copy().reset_index(drop=True)

    prio = priorizados.drop_duplicates(subset=["hex_id"], keep="first")
    merc = mercado.drop_duplicates(subset=["hex_id"], keep="first")
    dom = dominio.drop_duplicates(subset=["hex_id"], keep="first")

    prio_map_score = prio.set_index("hex_id")["score_priorizacao"] if "score_priorizacao" in prio else pd.Series(dtype="float64")

    def _map(series_holder: pd.DataFrame, col: str) -> dict:
        if col in series_holder.columns:
            return series_holder.set_index("hex_id")[col].to_dict()
        return {}

    merc_setor = _map(merc, "score_setor_2022_calibrado")
    merc_resid = _map(merc, "score_oportunidade_residual")
    dom_score = _map(dom, "score_dominio_hibrido")

    # geo de apoio (mercado primario, priorizados fallback)
    geo_cols = ["cod_municipio", "nome_municipio", "uf"]
    merc_geo = {c: _map(merc, c) for c in geo_cols}
    prio_geo = {c: _map(prio, c) for c in geo_cols}

    # score_priorizacao: preserva embutido (Ultra); preenche concorrentes por hex
    prio_dict = prio_map_score.to_dict()
    sp_vals: list[float | None] = []
    sp_flag: list[bool] = []
    for i, hx in enumerate(out["hex_id"]):
        existing = out.at[i, "score_priorizacao"] if "score_priorizacao" in out.columns else None
        if existing is not None and not (isinstance(existing, float) and pd.isna(existing)):
            sp_vals.append(float(existing))
            sp_flag.append(True)
        elif hx in prio_dict and pd.notna(prio_dict[hx]):
            sp_vals.append(float(prio_dict[hx]))
            sp_flag.append(True)
        else:
            sp_vals.append(None)
            sp_flag.append(False)
    out["score_priorizacao"] = sp_vals
    out["score_priorizacao_disponivel"] = sp_flag

    def _apply(mapping: dict, col: str, flag: str) -> None:
        vals: list[float | None] = []
        flags: list[bool] = []
        for hx in out["hex_id"]:
            v = mapping.get(hx)
            if v is not None and pd.notna(v):
                vals.append(float(v))
                flags.append(True)
            else:
                vals.append(None)
                flags.append(False)
        out[col] = vals
        out[flag] = flags

    _apply(merc_setor, "score_setor_2022_calibrado", "score_setor_2022_disponivel")
    _apply(merc_resid, "score_oportunidade_residual", "score_residual_disponivel")
    _apply(dom_score, "score_dominio_hibrido", "score_dominio_disponivel")

    # geo: preencher cod_municipio/nome_municipio/uf por hex (mercado, fallback prio)
    for col in geo_cols:
        existing_series = out[col] if col in out.columns else pd.Series([None] * len(out))
        vals: list[object] = []
        for hx, ex in zip(out["hex_id"], existing_series, strict=False):
            if ex is not None and not (isinstance(ex, float) and pd.isna(ex)) and str(ex).strip():
                vals.append(ex)
                continue
            v = merc_geo[col].get(hx)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                v = prio_geo[col].get(hx)
            vals.append(v if (v is not None and not (isinstance(v, float) and pd.isna(v))) else None)
        out[col] = vals
    return out


# --------------------------------------------------------------------------- #
# Desfecho canonico / Wellhub / flags
# --------------------------------------------------------------------------- #
def unify_wellhub(df: pd.DataFrame) -> pd.DataFrame:
    """Unifica sinal Wellhub (Gympass + TotalPass) em ``sinal_wellhub``/``n_parcerias_wellhub``.

    Ultra/Skyfit: Gympass e TotalPass; EngCorpo: so Gympass (sem TotalPass).
    Ausencia de ambas as colunas -> NA + n=0.
    """
    out = df.copy().reset_index(drop=True)
    gympass_cols = [c for c in ("alunos_gympass",) if c in out.columns]
    totalpass_cols = [c for c in ("alunos_totalpass",) if c in out.columns]

    g = out[gympass_cols[0]] if gympass_cols else pd.Series([pd.NA] * len(out))
    t = out[totalpass_cols[0]] if totalpass_cols else pd.Series([pd.NA] * len(out))
    g = pd.to_numeric(g, errors="coerce")
    t = pd.to_numeric(t, errors="coerce")

    n_parc: list[int] = []
    sinal: list[object] = []
    for gi, ti in zip(g, t, strict=False):
        has_g = pd.notna(gi) and gi > 0
        has_t = pd.notna(ti) and ti > 0
        n = int(has_g) + int(has_t)
        n_parc.append(n)
        if pd.isna(gi) and pd.isna(ti):
            sinal.append(pd.NA)
        else:
            sinal.append(bool(n > 0))
    out["n_parcerias_wellhub"] = n_parc
    out["sinal_wellhub"] = pd.array(sinal, dtype="boolean")
    return out


def canonical_students(df: pd.DataFrame) -> pd.DataFrame:
    """Cria ``alunos_recorrentes``/``alunos_origem``/``alunos_medido`` por rede."""
    out = df.copy().reset_index(drop=True)
    rec: list[float | None] = []
    origem: list[str] = []
    medido: list[bool] = []
    for _, row in out.iterrows():
        rede = row["rede"]
        if rede == "ultra":
            val = row.get("alunos_total")
            src = "alunos_total"
            if val is None or (isinstance(val, float) and pd.isna(val)):
                val = row.get("ativos_pag")
                src = "ativos_pag"
            rec.append(float(val) if pd.notna(val) else None)
            origem.append(src)
            medido.append(True)
        elif rede == "skyfit":
            val = row.get("alunos_evo")
            rec.append(float(val) if pd.notna(val) else None)
            origem.append("Alunos EVO")
            medido.append(True)
        elif rede == "engcorpo":
            val = row.get("alunos_totais")
            rec.append(float(val) if pd.notna(val) else None)
            origem.append("Alunos Totais")
            medido.append(False)
        else:
            rec.append(None)
            origem.append("desconhecido")
            medido.append(False)
    out["alunos_recorrentes"] = rec
    out["alunos_origem"] = origem
    out["alunos_medido"] = medido
    return out


def add_quality_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona ``rotulo_origem``/``rotulo_confiabilidade``/``maturacao_status`` e ``rotulo_casado``."""
    out = df.copy().reset_index(drop=True)
    out["maturacao_status"] = MATURACAO_INDISPONIVEL
    out["rotulo_origem"] = out["rede"]

    conf: list[str] = []
    for _, row in out.iterrows():
        if bool(row.get("alunos_medido")):
            conf.append("medido")
        elif row["rede"] == "engcorpo":
            conf.append("estimado")
        else:
            conf.append("sinal")
    out["rotulo_confiabilidade"] = conf

    # rotulo_casado: EngCorpo depende do join por nome (staging); demais redes
    # tem desfecho na propria fonte -> casado por definicao.
    if "rotulo_casado" not in out.columns:
        out["rotulo_casado"] = True
    casado: list[bool] = []
    for _, row in out.iterrows():
        if row["rede"] == "engcorpo":
            casado.append(bool(row.get("rotulo_casado_staging", False)))
        else:
            casado.append(True)
    out["rotulo_casado"] = casado
    return out


def _finalize_schema(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in SCHEMA_COLUMNS:
        if col not in out.columns:
            out[col] = None
    # tipos
    out["cod_municipio"] = out["cod_municipio"].astype("string")
    for c in ("lat", "lng", "score_priorizacao", "score_setor_2022_calibrado",
              "score_oportunidade_residual", "score_dominio_hibrido",
              "alunos_recorrentes", "faturamento", "metragem_m2"):
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out["n_parcerias_wellhub"] = pd.to_numeric(out["n_parcerias_wellhub"], errors="coerce").fillna(0).astype(int)
    for c in ("hex_resolvido", "score_priorizacao_disponivel", "score_setor_2022_disponivel",
              "score_residual_disponivel", "score_dominio_disponivel", "alunos_medido",
              "rotulo_casado"):
        out[c] = out[c].astype(bool)
    out["sinal_wellhub"] = out["sinal_wellhub"].astype("boolean")
    return out[list(SCHEMA_COLUMNS)]


# --------------------------------------------------------------------------- #
# Auditoria (apenas agregados, SEM PII)
# --------------------------------------------------------------------------- #
def audit_labels(df: pd.DataFrame, *, entradas_por_rede: dict[str, int] | None = None) -> dict:
    """Computa estatisticas agregadas (sem PII) para o relatorio de auditoria."""
    stats: dict = {"total_linhas": int(len(df)), "por_rede": {}}
    for rede in REDES:
        sub = df[df["rede"] == rede]
        if sub.empty:
            continue
        hex_ok = int(sub["hex_resolvido"].sum())
        n = int(len(sub))
        rede_stats = {
            "n_unidades": n,
            "entrada": int(entradas_por_rede.get(rede, n)) if entradas_por_rede else n,
            "hex_resolvido": hex_ok,
            "hex_resolvido_pct": round(100.0 * hex_ok / n, 1) if n else 0.0,
            "alunos_nulos": int(sub["alunos_recorrentes"].isna().sum()),
            "rotulo_nao_casado": int((~sub["rotulo_casado"]).sum()),
            "score_priorizacao_disp": int(sub["score_priorizacao_disponivel"].sum()),
            "score_setor_disp": int(sub["score_setor_2022_disponivel"].sum()),
            "score_residual_disp": int(sub["score_residual_disponivel"].sum()),
            "score_dominio_disp": int(sub["score_dominio_disponivel"].sum()),
            "hex_origem": sub["hex_origem"].value_counts(dropna=False).to_dict(),
            "hex_precisao": sub["hex_precisao"].value_counts(dropna=False).to_dict(),
        }
        al = pd.to_numeric(sub["alunos_recorrentes"], errors="coerce").dropna()
        if not al.empty:
            rede_stats["alunos_min"] = float(al.min())
            rede_stats["alunos_mediana"] = float(al.median())
            rede_stats["alunos_max"] = float(al.max())
        stats["por_rede"][rede] = rede_stats
    return stats


def render_audit_report(stats: dict) -> str:
    """Gera markdown agregado (sem PII)."""
    lines: list[str] = []
    lines.append("# Relatorio de auditoria de rotulo - dataset de validacao")
    lines.append("")
    lines.append("> BLK-SCORE-01. Apenas agregados (sem PII: nenhum nome de unidade,")
    lines.append("> endereco ou contagem nominal por unidade). Artefato gitignored.")
    lines.append("")
    lines.append(f"Total de linhas no dataset: **{stats['total_linhas']}**")
    lines.append("")
    for rede in REDES:
        rs = stats["por_rede"].get(rede)
        if not rs:
            continue
        lines.append(f"## Rede: {rede}")
        lines.append("")
        lines.append(f"- Unidades de entrada: {rs['entrada']}")
        lines.append(f"- Linhas no dataset: {rs['n_unidades']}")
        diff = rs["n_unidades"] - rs["entrada"]
        lines.append(f"- Diferenca entrada->dataset: {diff} (0 = sem duplicacao)")
        lines.append(f"- Hex resolvido: {rs['hex_resolvido']}/{rs['n_unidades']} ({rs['hex_resolvido_pct']}%)")
        lines.append(f"- Alunos recorrentes nulos: {rs['alunos_nulos']}")
        lines.append(f"- Rotulos nao casados: {rs['rotulo_nao_casado']}")
        lines.append(
            "- Scores disponiveis (priorizacao/setor/residual/dominio): "
            f"{rs['score_priorizacao_disp']}/{rs['score_setor_disp']}/"
            f"{rs['score_residual_disp']}/{rs['score_dominio_disp']}"
        )
        if "alunos_mediana" in rs:
            lines.append(
                f"- Alunos (min/mediana/max): {rs['alunos_min']:.0f} / "
                f"{rs['alunos_mediana']:.0f} / {rs['alunos_max']:.0f}"
            )
        lines.append("- Distribuicao por hex_origem:")
        for k, v in rs["hex_origem"].items():
            lines.append(f"  - {k}: {v}")
        lines.append("- Distribuicao por hex_precisao:")
        for k, v in rs["hex_precisao"].items():
            lines.append(f"  - {k}: {v}")
        lines.append("")
    lines.append("Maturacao: constante `maturacao_indisponivel` (sem data de abertura confiavel).")
    fonte_dom = stats.get("score_dominio_fonte")
    if fonte_dom:
        lines.append("")
        lines.append(f"Fonte score_dominio_hibrido: {fonte_dom}.")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Orquestracao
# --------------------------------------------------------------------------- #
def _prepare_rede(df: pd.DataFrame) -> pd.DataFrame:
    """Pipeline comum por rede ate antes do join de scores."""
    df = resolve_hex(df)
    df = unify_wellhub(df)
    df = canonical_students(df)
    df = add_quality_flags(df)
    return df


def build(
    *,
    ultra: pd.DataFrame | None = None,
    skyfit: pd.DataFrame | None = None,
    engcorpo: pd.DataFrame | None = None,
    priorizados: pd.DataFrame | None = None,
    mercado: pd.DataFrame | None = None,
    dominio: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Orquestra tudo e retorna o dataframe final no esquema canonico.

    Aceita frames ja carregados (para testes com fixtures) ou carrega das fontes
    reais (default em ``main``). READ-ONLY sobre o M1.
    """
    frames: list[pd.DataFrame] = []
    for raw in (ultra, skyfit, engcorpo):
        if raw is not None and len(raw):
            frames.append(_prepare_rede(raw))
    if frames:
        # Alinha as colunas de todas as redes antes do concat para evitar o
        # FutureWarning de pandas sobre colunas vazias/all-NA com dtypes divergentes.
        all_cols: list[str] = []
        for fr in frames:
            for c in fr.columns:
                if c not in all_cols:
                    all_cols.append(c)
        frames = [fr.reindex(columns=all_cols) for fr in frames]
        # Colunas presentes em apenas uma rede ficam all-NA nas demais; o pandas
        # emite FutureWarning sobre os dtypes dessas colunas no concat. O guard
        # abaixo e local e nao altera o resultado (apenas evita o ruido); o
        # esquema final e fixado depois em `_finalize_schema`.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            combined = pd.concat(frames, ignore_index=True, sort=False)
    else:
        combined = _empty_schema_frame()

    prio = priorizados if priorizados is not None else _empty_score_frame(["hex_id", "score_priorizacao", "cod_municipio", "nome_municipio", "uf"])
    merc = mercado if mercado is not None else _empty_score_frame(["hex_id", "score_setor_2022_calibrado", "score_oportunidade_residual", "cod_municipio", "nome_municipio", "uf"])
    dom = dominio if dominio is not None else _empty_score_frame(["hex_id", "score_dominio_hibrido"])

    combined = join_scores(combined, priorizados=prio, mercado=merc, dominio=dom)
    return _finalize_schema(combined)


def _empty_score_frame(cols: list[str]) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in cols})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monta o dataset rotulado de validacao (BLK-SCORE-01).")
    parser.add_argument("--ultra", type=Path, default=ULTRA_PARQUET)
    parser.add_argument("--skyfit-desfecho", type=Path, default=SKYFIT_DESFECHO_XLSX)
    parser.add_argument("--skyfit-coords", type=Path, default=SKYFIT_COORDS_CSV)
    parser.add_argument("--engcorpo", type=Path, default=ENGCORPO_XLSX)
    parser.add_argument("--engcorpo-coords", type=Path, default=ENGCORPO_COORDS_CSV)
    parser.add_argument("--engcorpo-staging", type=Path, default=ENGCORPO_STAGING)
    parser.add_argument("--priorizados", type=Path, default=PRIORIZADOS_PARQUET)
    parser.add_argument("--mercado", type=Path, default=MERCADO_PARQUET)
    parser.add_argument("--dominio", type=Path, default=DOMINIO_PARQUET)
    parser.add_argument("--out-parquet", type=Path, default=OUT_PARQUET)
    parser.add_argument("--out-report", type=Path, default=OUT_REPORT)
    parser.add_argument("--fuzzy-cutoff", type=float, default=DEFAULT_FUZZY_CUTOFF)
    args = parser.parse_args(argv)

    ultra = load_ultra(args.ultra)
    skyfit = load_skyfit(args.skyfit_desfecho, args.skyfit_coords, fuzzy_cutoff=args.fuzzy_cutoff)
    engcorpo = load_engcorpo(
        args.engcorpo, args.engcorpo_coords, args.engcorpo_staging, fuzzy_cutoff=args.fuzzy_cutoff
    )

    entradas = {"ultra": len(ultra), "skyfit": len(skyfit), "engcorpo": len(engcorpo)}

    priorizados = _load_score_source(
        args.priorizados, ["hex_id", "score_priorizacao", "cod_municipio", "nome_municipio", "uf"]
    )
    mercado = _load_score_source(
        args.mercado,
        ["hex_id", "score_setor_2022_calibrado", "score_oportunidade_residual",
         "cod_municipio", "nome_municipio", "uf"],
    )
    # Score de dominio: fonte = `data/outputs/plano_expansao_dominio.parquet`
    # (500 hexes; `hex_id` + `score_dominio_hibrido`). Tratado como OPCIONAL: se o
    # parquet faltar, todas as linhas ficam com score nulo +
    # `score_dominio_disponivel=False` (cobertura parcial esperada pelo plano).
    # NUNCA recalcular o score aqui (read-only sobre o M1).
    if args.dominio.exists():
        dominio = _load_score_source(args.dominio, ["hex_id", "score_dominio_hibrido"])
        dominio_status = f"presente ({len(dominio)} hexes)"
    else:
        dominio = _empty_score_frame(["hex_id", "score_dominio_hibrido"])
        dominio_status = "ausente (score_dominio_disponivel=False em todas as linhas)"

    dataset = build(
        ultra=ultra, skyfit=skyfit, engcorpo=engcorpo,
        priorizados=priorizados, mercado=mercado, dominio=dominio,
    )

    stats = audit_labels(dataset, entradas_por_rede=entradas)
    stats["score_dominio_fonte"] = dominio_status
    report = render_audit_report(stats)

    args.out_parquet.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_parquet(args.out_parquet, index=False)
    args.out_report.write_text(report, encoding="utf-8")

    # stdout: somente agregados (sem PII)
    print(f"[build_validation_dataset] dataset: {len(dataset)} linhas -> {args.out_parquet}")
    print(f"[build_validation_dataset] score_dominio: {dominio_status}")
    for rede in REDES:
        rs = stats["por_rede"].get(rede)
        if rs:
            print(
                f"  {rede}: entrada={rs['entrada']} linhas={rs['n_unidades']} "
                f"hex_ok={rs['hex_resolvido']} ({rs['hex_resolvido_pct']}%) "
                f"alunos_nulos={rs['alunos_nulos']}"
            )
    print(f"[build_validation_dataset] relatorio -> {args.out_report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
