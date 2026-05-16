"""
Bloco 1 - Normalizacao das unidades Ultra com performance.

Une a planilha de performance GeoFusion/faturamento com o CSV legado de
coordenadas das unidades Ultra. Saida:
data/staging/unidades_ultra_performance.parquet

Nao altera nenhum artefato oficial do M1.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PERFORMANCE_XLSX = ROOT / "data" / "ultra" / "dados_academias.xlsx"
ULTRA_CSV = ROOT / "data" / "ultra" / "Ultra.csv"
OUT_PATH = ROOT / "data" / "staging" / "unidades_ultra_performance.parquet"

H3_RESOLUTION = 7
LAT_MIN, LAT_MAX = -34.0, 6.0
LNG_MIN, LNG_MAX = -75.0, -28.0
FUZZY_MIN_SCORE = 0.86
FUZZY_MIN_MARGIN = 0.05

UF_RE = re.compile(r"^[A-Z]{2}$")
UF_SUFFIX_RE = re.compile(r"(?:/|\s+-\s+|\s+)([A-Z]{2})\s*$")

PERFORMANCE_COLUMN_MAP = {
    "LOCALIZACAO": "localizacao_raw",
    "Populacao": "pop_geofusion_1km",
    "Densidade demografica": "densidade_geofusion_1km_km2",
    "FATURAMENTO": "faturamento",
    "ATIVOS_PAG": "ativos_pag",
    "ALUNOS_GYMPASS": "alunos_gympass",
    "ALUNOS_TOTALPASS": "alunos_totalpass",
    "AGREGADORES": "agregadores",
    "ALUNOS_TOTAL": "alunos_total",
    "Metragem": "metragem",
}

MIN_OUTPUT_COLUMNS = [
    "unidade",
    "uf",
    "cidade",
    "lat",
    "lng",
    "hex_id_res7",
    "pop_geofusion_1km",
    "densidade_geofusion_1km_km2",
    "faturamento",
    "ativos_pag",
    "alunos_gympass",
    "alunos_totalpass",
    "agregadores",
    "alunos_total",
    "ticket_medio_aluno",
    "status_match_coord",
]

# Aliases documentam os poucos casos em que a planilha usa nome comercial/local
# diferente do CSV de coordenadas.
MANUAL_COORD_KEY = {
    ("porto alegre barra sul", "RS"): "porto alegre",
    ("botanic mall", "DF"): "jardim botanico",
    ("cambui campinas", "SP"): "cambui",
    ("cpa", "MT"): "cuiaba",
    ("paranoa parque", "DF"): "paranoa",
    ("jardim botanico", "DF"): "jardim botanico ii",
    ("samambaia", "DF"): "samambaia norte",
    ("valparaiso", "GO"): "valparaiso de goias",
}


def _strip_accents(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    return "".join(
        char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char)
    )


def _clean_text(value: object) -> str:
    return str(value).strip().strip('"') if pd.notna(value) else ""


def _canonical_column(value: object) -> str:
    text = _strip_accents(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _unit_key(value: object) -> str:
    text = _strip_accents(value).lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[/_-]+", " ", text)
    text = re.sub(r"\b[A-Z]{2}\b$", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bjd\b\.?", " jardim ", text)
    text = re.sub(r"\bpoa\b", " porto alegre ", text)
    text = re.sub(r"\bicn\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _remove_uf_suffix(value: object) -> tuple[str, str | None]:
    text = _clean_text(value)
    ascii_upper = _strip_accents(text).upper()
    match = UF_SUFFIX_RE.search(ascii_upper)
    uf = match.group(1) if match else None
    if match:
        text = UF_SUFFIX_RE.sub("", _strip_accents(text))
    return text.strip(), uf


def _parse_perf_location(value: object) -> tuple[str, str | None, str]:
    text = _clean_text(value)
    ascii_text = _strip_accents(text)
    match = re.search(r"\s+-\s+([A-Z]{2})\s*$", ascii_text.upper())
    uf = match.group(1) if match else None
    unidade = re.sub(r"\s+-\s+[A-Z]{2}\s*$", "", ascii_text, flags=re.I).strip()
    return unidade, uf, _unit_key(unidade)


def _coord_in_brazil(value: float, *, axis: str) -> bool:
    if axis == "lat":
        return LAT_MIN <= value <= LAT_MAX
    return LNG_MIN <= value <= LNG_MAX


def _parse_coordinate(value: object, *, axis: str) -> float | None:
    if pd.isna(value):
        return None

    text = str(value).strip().replace(",", ".")
    direct = pd.to_numeric(text, errors="coerce")
    if pd.notna(direct) and _coord_in_brazil(float(direct), axis=axis):
        return float(direct)

    digits = re.sub(r"\D", "", text)
    if not digits:
        return None

    sign = -1 if text.lstrip().startswith("-") else 1
    numeric = int(digits)
    for decimals in range(4, min(len(digits), 10) + 1):
        candidate = sign * numeric / (10**decimals)
        if _coord_in_brazil(candidate, axis=axis):
            return float(candidate)
    return None


def _coord_valida(lat: object, lng: object) -> bool:
    return pd.notna(lat) and pd.notna(lng) and _coord_in_brazil(float(lat), axis="lat") and _coord_in_brazil(float(lng), axis="lng")


def _latlng_to_h3(lat: float, lng: float) -> str:
    import h3

    if hasattr(h3, "latlng_to_cell"):
        return h3.latlng_to_cell(float(lat), float(lng), H3_RESOLUTION)
    return h3.geo_to_h3(float(lat), float(lng), H3_RESOLUTION)


def _safe_div(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce")
    return numerator.where(denominator > 0) / denominator.where(denominator > 0)


def carregar_ultra(path: Path = ULTRA_CSV) -> pd.DataFrame:
    """Le o CSV legado de coordenadas Ultra mantendo colunas usadas por testes antigos."""
    df = pd.read_csv(path, sep=";", skiprows=1, dtype=str, encoding="latin-1")
    df.columns = [_clean_text(column).lower() for column in df.columns]
    df = df.rename(
        columns={
            "unidade": "unidade",
            "estado": "uf_raw",
            "cidade": "cidade",
            "latitude": "lat_raw",
            "longitude": "lng_raw",
        }
    )

    df["unidade"] = df["unidade"].map(_clean_text)
    df["cidade"] = df["cidade"].map(_clean_text)
    parsed = df["unidade"].map(_remove_uf_suffix)
    df["unidade_coord"] = parsed.map(lambda item: item[0])
    df["uf_suffix"] = parsed.map(lambda item: item[1])
    df["uf_raw"] = df["uf_raw"].map(_clean_text).str.upper()
    df["uf"] = df["uf_raw"].where(df["uf_raw"].str.match(r"^[A-Z]{2}$", na=False), df["uf_suffix"])
    df["uf"] = df["uf"].fillna("DESCONHECIDO")
    df["lat"] = df["lat_raw"].map(lambda value: _parse_coordinate(value, axis="lat"))
    df["lng"] = df["lng_raw"].map(lambda value: _parse_coordinate(value, axis="lng"))
    df["flag_coord_valida"] = df.apply(lambda row: _coord_valida(row["lat"], row["lng"]), axis=1)
    df["coord_key"] = df["unidade_coord"].map(_unit_key)
    df["cidade_key"] = df["cidade"].map(_unit_key)
    df["coord_source_index"] = range(len(df))
    return df


def carregar_performance(path: Path = PERFORMANCE_XLSX) -> pd.DataFrame:
    raw = pd.read_excel(path)
    canonical_to_original = {_canonical_column(column): column for column in raw.columns}
    faltam = sorted(set(PERFORMANCE_COLUMN_MAP) - set(canonical_to_original))
    if faltam:
        raise AssertionError(f"Colunas ausentes em dados_academias.xlsx: {faltam}")

    out = pd.DataFrame(index=raw.index)
    for canonical, target in PERFORMANCE_COLUMN_MAP.items():
        out[target] = raw[canonical_to_original[canonical]]

    parsed = out["localizacao_raw"].map(_parse_perf_location)
    out["unidade"] = parsed.map(lambda item: item[0])
    out["uf_perf"] = parsed.map(lambda item: item[1])
    out["perf_key"] = parsed.map(lambda item: item[2])

    numeric_cols = [
        "pop_geofusion_1km",
        "densidade_geofusion_1km_km2",
        "faturamento",
        "ativos_pag",
        "alunos_gympass",
        "alunos_totalpass",
        "agregadores",
        "alunos_total",
        "metragem",
    ]
    for column in numeric_cols:
        out[column] = pd.to_numeric(out[column], errors="coerce")

    out["ticket_medio_aluno"] = _safe_div(out["faturamento"], out["alunos_total"])
    out["performance_source_index"] = range(len(out))
    return out


def _sequence_score(left: str, right: str) -> float:
    score = SequenceMatcher(None, left, right).ratio()
    if left and right and (left in right or right in left):
        score = max(score, 0.92)
    return score


def _pick_by_key(candidates: pd.DataFrame, target_key: str) -> tuple[pd.Series | None, int]:
    matches = candidates[candidates["coord_key"].eq(target_key)]
    if matches.empty:
        return None, 0
    return matches.iloc[-1], len(matches)


def _match_coord(row: pd.Series, coords: pd.DataFrame) -> dict[str, object]:
    candidates = coords[coords["flag_coord_valida"]].copy()
    if pd.notna(row["uf_perf"]):
        candidates = candidates[candidates["uf"].eq(row["uf_perf"])]

    if candidates.empty:
        return {"coord_source_index": pd.NA, "status_match_coord": "sem_coord", "coord_match_score": 0.0, "coord_match_count": 0}

    manual_target = MANUAL_COORD_KEY.get((row["perf_key"], row["uf_perf"]))
    if manual_target:
        picked, count = _pick_by_key(candidates, manual_target)
        if picked is not None:
            status = "casado_alias" if count == 1 else "casado_alias_duplicado"
            return {
                "coord_source_index": picked["coord_source_index"],
                "status_match_coord": status,
                "coord_match_score": 1.0,
                "coord_match_count": count,
            }

    picked, count = _pick_by_key(candidates, row["perf_key"])
    if picked is not None:
        status = "casado_exato" if count == 1 else "casado_exato_duplicado"
        return {
            "coord_source_index": picked["coord_source_index"],
            "status_match_coord": status,
            "coord_match_score": 1.0,
            "coord_match_count": count,
        }

    scored = candidates.assign(
        coord_match_score=candidates["coord_key"].map(lambda key: _sequence_score(row["perf_key"], key))
    ).sort_values("coord_match_score", ascending=False, kind="stable")
    best = scored.iloc[0]
    second_score = float(scored["coord_match_score"].iloc[1]) if len(scored) > 1 else 0.0
    best_score = float(best["coord_match_score"])
    if best_score >= FUZZY_MIN_SCORE and best_score - second_score >= FUZZY_MIN_MARGIN:
        return {
            "coord_source_index": best["coord_source_index"],
            "status_match_coord": "casado_fuzzy",
            "coord_match_score": best_score,
            "coord_match_count": 1,
        }

    return {"coord_source_index": pd.NA, "status_match_coord": "sem_coord", "coord_match_score": best_score, "coord_match_count": 0}


def gerar_base(
    performance_path: Path = PERFORMANCE_XLSX,
    ultra_path: Path = ULTRA_CSV,
) -> pd.DataFrame:
    performance = carregar_performance(performance_path)
    coords = carregar_ultra(ultra_path)
    match = performance.apply(lambda row: _match_coord(row, coords), axis=1, result_type="expand")
    merged = pd.concat([performance, match], axis=1)

    coord_cols = [
        "coord_source_index",
        "unidade_coord",
        "uf",
        "cidade",
        "lat",
        "lng",
        "coord_key",
        "cidade_key",
    ]
    merged = merged.merge(coords[coord_cols], on="coord_source_index", how="left")
    merged["uf"] = merged["uf"].where(merged["uf"].notna(), merged["uf_perf"])
    merged["hex_id_res7"] = [
        _latlng_to_h3(lat, lng) if _coord_valida(lat, lng) else pd.NA
        for lat, lng in zip(merged["lat"], merged["lng"], strict=False)
    ]

    ordered = [
        "unidade",
        "uf",
        "cidade",
        "lat",
        "lng",
        "hex_id_res7",
        "pop_geofusion_1km",
        "densidade_geofusion_1km_km2",
        "faturamento",
        "ativos_pag",
        "alunos_gympass",
        "alunos_totalpass",
        "agregadores",
        "alunos_total",
        "ticket_medio_aluno",
        "status_match_coord",
        "metragem",
        "localizacao_raw",
        "unidade_coord",
        "uf_perf",
        "coord_match_score",
        "coord_match_count",
        "performance_source_index",
        "coord_source_index",
    ]
    return merged[ordered].sort_values("performance_source_index", kind="stable").reset_index(drop=True)


def validar(df: pd.DataFrame) -> None:
    print("\n=== Validacao: unidades_ultra_performance ===")
    print(f"Total de linhas: {len(df)}")
    faltam = set(MIN_OUTPUT_COLUMNS) - set(df.columns)
    assert not faltam, f"Schema incompleto: faltam {sorted(faltam)}"
    print("Schema minimo OK")

    matched = df["status_match_coord"].str.startswith("casado", na=False)
    match_rate = float(matched.mean()) if len(df) else 0.0
    print(f"Unidades com coordenada casada: {int(matched.sum())}/{len(df)} ({match_rate:.1%})")
    assert match_rate >= 0.90, f"Taxa de match baixa: {match_rate:.1%}"

    valid_coord = df["lat"].notna() & df["lng"].notna()
    assert valid_coord.equals(matched), "Status de match e coordenadas estao inconsistentes"
    assert df.loc[valid_coord, "hex_id_res7"].notna().all(), "Coordenada valida sem hex_id_res7"
    assert df.loc[valid_coord, "lat"].between(LAT_MIN, LAT_MAX).all(), "Latitude fora do Brasil"
    assert df.loc[valid_coord, "lng"].between(LNG_MIN, LNG_MAX).all(), "Longitude fora do Brasil"
    print("Coordenadas e H3 OK")

    duplicated_units = df.duplicated(subset=["unidade", "uf"], keep=False)
    assert not duplicated_units.any(), (
        "Duplicidade critica por unidade/UF:\n"
        + df.loc[duplicated_units, ["unidade", "uf", "status_match_coord"]].to_string(index=False)
    )
    print("Sem duplicidade critica por unidade/UF")

    assert df["alunos_total"].notna().all(), "alunos_total nulo"
    assert (df["ticket_medio_aluno"].dropna() >= 0).all(), "ticket_medio_aluno negativo"
    print("Metricas de performance OK")

    if (~matched).any():
        print("\nUnidades sem coordenada casada:")
        print(df.loc[~matched, ["unidade", "uf", "status_match_coord"]].to_string(index=False))
    print("\nStatus de match:")
    print(df["status_match_coord"].value_counts().to_string())
    print("\nValidacao OK")


def main() -> None:
    print("Bloco 1 - Normalizacao das unidades Ultra com performance")
    print("=" * 62)
    df = gerar_base(PERFORMANCE_XLSX, ULTRA_CSV)
    validar(df)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH, index=False)
    print(f"\nSalvo: {OUT_PATH}")
    print("Bloco 1 concluido.")


if __name__ == "__main__":
    main()
