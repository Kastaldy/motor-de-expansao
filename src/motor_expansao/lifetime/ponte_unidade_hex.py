"""BLK-LTV-01 — Tabela-ponte unidade_hex.

Geocodifica cada unidade do Lifetime (unidade_para_motor.parquet) contra:
  1. Ultra.csv  (match exato por nome normalizado)
  2. Ultra.csv  (fuzzy, SequenceMatcher, limiar >=FUZZY_THRESHOLD)
  3. unidades_ultra_performance_hex.parquet (fallback perf_hex, exato então fuzzy)

Produz data/staging/unidade_hex.parquet com colunas mínimas:
  cod_unidade, unidade, uf, lat, lng, hex_id, metodo_match, match_score, fonte_geo

READ-ONLY sobre o M1: ZERO importação de pipelines/m1, censo_*, dashboard.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import h3  # type: ignore[import-untyped]
import pandas as pd

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
H3_RESOLUTION: int = 7
FUZZY_THRESHOLD: float = 0.85
_TOKENS_GENERICOS = ["ultra", "academia", "unidade", "fit"]

# Colunas de saída obrigatórias
OUTPUT_COLUMNS = [
    "cod_unidade",
    "unidade",
    "uf",
    "lat",
    "lng",
    "hex_id",
    "metodo_match",
    "match_score",
    "fonte_geo",
]


# ---------------------------------------------------------------------------
# Normalização de nome
# ---------------------------------------------------------------------------

def normalize_name(name: str | None) -> str:
    """Normaliza nome de unidade para comparação.

    Passos:
    - lower + strip
    - remove acentos (NFD → strip Mn)
    - remove sufixo de estado no fim (``/ SP``, ``- SP``)
    - remove tokens genéricos (ultra/academia/unidade/fit)
    - colapsa espaços múltiplos
    """
    try:
        is_na = bool(pd.isna(name))
    except (TypeError, ValueError):
        is_na = False
    if is_na:
        return ""
    if not name:
        return ""
    s = str(name).lower().strip()
    # Remove acentos
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    # Remove estado no final: "/ SP", "- SP", " SP" (2 letras maiúsculas originais)
    s = re.sub(r"\s*/\s*[a-z]{2}$", "", s)
    s = re.sub(r"\s*-\s*[a-z]{2}$", "", s)
    # Remove tokens genéricos
    for tok in _TOKENS_GENERICOS:
        s = re.sub(r"\b" + re.escape(tok) + r"\b", "", s)
    # Colapsa espaços
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _fuzzy_score(a: str, b: str) -> float:
    """SequenceMatcher ratio entre dois strings normalizados."""
    return SequenceMatcher(None, a, b).ratio()


# ---------------------------------------------------------------------------
# Leitura dos insumos
# ---------------------------------------------------------------------------

def _load_ultra_csv(ultra_csv: Path) -> pd.DataFrame:
    """Lê Ultra.csv: sep=';', encoding='latin-1', 1 linha de metadado."""
    df = pd.read_csv(ultra_csv, sep=";", encoding="latin-1", skiprows=1)
    # Converter Latitude/Longitude de vírgula decimal para float
    for col in ("Latitude", "Longitude"):
        if col in df.columns:
            df[col] = (
                df[col].astype(str).str.replace(",", ".", regex=False)
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["_norm"] = df["UNIDADE"].apply(normalize_name)
    return df


def _load_perf_hex(perf_hex: Path) -> pd.DataFrame:
    """Lê unidades_ultra_performance_hex.parquet."""
    df = pd.read_parquet(perf_hex)
    df["_norm"] = df["unidade"].apply(normalize_name)
    return df


def _load_lifetime(lifetime_parquet: Path) -> pd.DataFrame:
    """Lê unidade_para_motor.parquet."""
    df = pd.read_parquet(lifetime_parquet)
    df["_norm"] = df["UNIDADE"].apply(normalize_name)
    return df


# ---------------------------------------------------------------------------
# Lógica de match
# ---------------------------------------------------------------------------

def _best_fuzzy(
    query_norm: str, candidates: list[str], threshold: float = FUZZY_THRESHOLD
) -> tuple[int, float]:
    """Retorna (índice do melhor candidato, score). Índice=-1 se score < threshold."""
    best_idx = -1
    best_score = 0.0
    for idx, cand in enumerate(candidates):
        s = _fuzzy_score(query_norm, cand)
        if s > best_score:
            best_score = s
            best_idx = idx
    if best_score < threshold:
        return -1, best_score
    return best_idx, best_score


def _derive_hex(lat: float, lng: float) -> str | None:
    """Converte lat/lng em hex_id H3 res-7. Retorna None se inválido."""
    try:
        if pd.isna(lat) or pd.isna(lng):
            return None
        return h3.latlng_to_cell(float(lat), float(lng), H3_RESOLUTION)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def build_bridge(
    lifetime_parquet: Path,
    ultra_csv: Path,
    perf_hex: Path,
    fuzzy_threshold: float = FUZZY_THRESHOLD,
) -> pd.DataFrame:
    """Constrói a tabela-ponte unidade_hex.

    Args:
        lifetime_parquet: caminho para unidade_para_motor.parquet
        ultra_csv: caminho para Ultra.csv
        perf_hex: caminho para unidades_ultra_performance_hex.parquet
        fuzzy_threshold: limiar mínimo para aceitar match fuzzy

    Returns:
        DataFrame com colunas OUTPUT_COLUMNS (uma linha por unidade Lifetime).
        Unidades sem match têm hex_id nulo (não silenciadas).
    """
    lt = _load_lifetime(lifetime_parquet)
    ultra = _load_ultra_csv(ultra_csv)
    perf = _load_perf_hex(perf_hex)

    ultra_norms: list[str] = ultra["_norm"].tolist()
    perf_norms: list[str] = perf["_norm"].tolist()

    rows: list[dict] = []

    for _, lrow in lt.iterrows():
        cod = str(lrow["COD_UNIDADE"])
        nome = lrow["UNIDADE"]
        uf = lrow["UF"]
        lt_norm = lrow["_norm"]

        lat: float | None = None
        lng: float | None = None
        hex_id: str | None = None
        metodo: str = "sem_match"
        score: float = 0.0
        fonte: str | None = None

        # Unidades sem nome no Lifetime: não é possível geocodificar por nome
        if not lt_norm:
            rows.append(
                {
                    "cod_unidade": cod,
                    "unidade": nome,
                    "uf": uf,
                    "lat": None,
                    "lng": None,
                    "hex_id": None,
                    "metodo_match": "sem_match",
                    "match_score": 0.0,
                    "fonte_geo": None,
                }
            )
            continue

        # 1. Match exato no Ultra.csv
        exact_mask = ultra["_norm"] == lt_norm
        if exact_mask.any():
            matched = ultra[exact_mask].iloc[0]
            lat = matched["Latitude"]
            lng = matched["Longitude"]
            metodo = "exato"
            score = 1.0
            fonte = "ultra_csv"

        # 2. Fuzzy no Ultra.csv
        if metodo == "sem_match":
            best_idx, best_score = _best_fuzzy(lt_norm, ultra_norms, fuzzy_threshold)
            if best_idx >= 0:
                matched = ultra.iloc[best_idx]
                lat = matched["Latitude"]
                lng = matched["Longitude"]
                metodo = "fuzzy"
                score = best_score
                fonte = "ultra_csv"

        # 3. Fallback perf_hex (exato)
        if metodo == "sem_match":
            exact_mask_perf = perf["_norm"] == lt_norm
            if exact_mask_perf.any():
                matched_p = perf[exact_mask_perf].iloc[0]
                lat = matched_p["lat"]
                lng = matched_p["lng"]
                metodo = "perf_hex"
                score = 1.0
                fonte = "perf_hex"

        # 3b. Fallback perf_hex (fuzzy)
        if metodo == "sem_match":
            best_idx_p, best_score_p = _best_fuzzy(lt_norm, perf_norms, fuzzy_threshold)
            if best_idx_p >= 0:
                matched_p = perf.iloc[best_idx_p]
                lat = matched_p["lat"]
                lng = matched_p["lng"]
                metodo = "perf_hex"
                score = best_score_p
                fonte = "perf_hex"

        # Derivar hex_id a partir de lat/lng
        if lat is not None and lng is not None:
            hex_id = _derive_hex(lat, lng)

        rows.append(
            {
                "cod_unidade": cod,
                "unidade": nome,
                "uf": uf,
                "lat": lat,
                "lng": lng,
                "hex_id": hex_id,
                "metodo_match": metodo,
                "match_score": score,
                "fonte_geo": fonte,
            }
        )

    result = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    return result


# ---------------------------------------------------------------------------
# Relatório de qualidade
# ---------------------------------------------------------------------------

def quality_report(bridge: pd.DataFrame) -> str:
    """Gera relatório de qualidade de match em Markdown."""
    total = len(bridge)
    sem_nome = int((bridge["unidade"].isna() | (bridge["unidade"] == "")).sum())

    by_method = bridge["metodo_match"].value_counts().to_dict()
    geocoded = int(bridge["hex_id"].notna().sum())
    sem_match_total = int(by_method.get("sem_match", 0))

    lines = [
        "# BLK-LTV-01 — Relatório de qualidade de match",
        "",
        "## Totais",
        f"- Total de unidades Lifetime: **{total}**",
        f"- Sem nome (UNIDADE nula → sem match possível): **{sem_nome}**",
        f"- Com nome disponível: **{total - sem_nome}**",
        f"- Geocodificadas (hex_id não-nulo): **{geocoded}**",
        f"- Sem match (hex_id nulo): **{sem_match_total}**",
        "",
        "## Por método de match",
    ]
    for meth, cnt in sorted(by_method.items(), key=lambda x: -x[1]):
        lines.append(f"- `{meth}`: {cnt}")

    lines += ["", "## Por UF"]
    by_uf = (
        bridge.groupby("uf")
        .agg(total=("cod_unidade", "count"), geocoded=("hex_id", "count"))
        .reset_index()
    )
    for _, r in by_uf.iterrows():
        lines.append(f"- {r['uf']}: {int(r['geocoded'])}/{int(r['total'])} geocodificadas")

    lines += ["", "## Por CONFIABILIDADE_UNIDADE"]
    lines.append("_(cobertura das unidades 'Absoluto OK' — as que permitem uso de prob. absoluta)_")
    lines.append("")
    lines.append("_Nota: CONFIABILIDADE_UNIDADE não está nesta tabela-ponte._")
    lines.append("_Cruzar com unidade_para_motor.parquet para detalhe por classe._")

    lines += ["", "## Unidades sem match (verificação humana necessária)"]
    sem_match_df = bridge[bridge["metodo_match"] == "sem_match"][
        ["cod_unidade", "unidade", "uf"]
    ]
    if sem_match_df.empty:
        lines.append("Nenhuma unidade sem match.")
    else:
        lines.append(
            "| cod_unidade | unidade | uf |"
        )
        lines.append("|---|---|---|")
        for _, r in sem_match_df.iterrows():
            lines.append(
                f"| {r['cod_unidade']} | {r['unidade']} | {r['uf']} |"
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(
    root: Path | None = None,
    fuzzy_threshold: float = FUZZY_THRESHOLD,
) -> pd.DataFrame:
    """Executa o pipeline completo e grava os artefatos.

    Args:
        root: raiz do projeto (default: detectado a partir deste arquivo).
        fuzzy_threshold: limiar fuzzy.

    Returns:
        DataFrame da tabela-ponte.
    """
    if root is None:
        # src/motor_expansao/lifetime/ponte_unidade_hex.py → ../../.. = raiz
        root = Path(__file__).resolve().parents[3]

    lifetime_parquet = root / "data" / "ultra" / "unidade_para_motor.parquet"
    ultra_csv = root / "data" / "ultra" / "Ultra.csv"
    perf_hex = root / "data" / "staging" / "unidades_ultra_performance_hex.parquet"
    output_parquet = root / "data" / "staging" / "unidade_hex.parquet"
    report_path = root / "data" / "reports" / "scratch" / "blk_ltv_01_match_quality.md"

    bridge = build_bridge(lifetime_parquet, ultra_csv, perf_hex, fuzzy_threshold)

    # Gravar parquet
    output_parquet.parent.mkdir(parents=True, exist_ok=True)
    bridge.to_parquet(output_parquet, index=False)
    print(f"[BLK-LTV-01] Parquet gravado: {output_parquet}")

    # Gravar relatório
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_text = quality_report(bridge)
    report_path.write_text(report_text, encoding="utf-8")
    print(f"[BLK-LTV-01] Relatório gravado: {report_path}")

    # Resumo no stdout
    total = len(bridge)
    geocoded = int(bridge["hex_id"].notna().sum())
    sem_match = int((bridge["metodo_match"] == "sem_match").sum())
    by_method = bridge["metodo_match"].value_counts().to_dict()
    print(f"[BLK-LTV-01] Cobertura: {geocoded}/{total} geocodificadas | sem_match={sem_match}")
    print(f"[BLK-LTV-01] Por método: {by_method}")

    return bridge


if __name__ == "__main__":
    run()
