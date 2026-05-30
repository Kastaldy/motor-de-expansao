"""
Bloco 2 - Penetracao Ultra por hexagono.

Une a base auditavel de performance das unidades Ultra com a camada de
hexagonos de mercado e calcula penetracao, receita por habitante e densidade
operacional da unidade. Saida:
data/staging/unidades_ultra_performance_hex.parquet

Nao altera nenhum artefato oficial do M1.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[3]

UNIDADES_PATH = ROOT / "data" / "staging" / "unidades_ultra_performance.parquet"
HEXAGONOS_PATH = ROOT / "data" / "staging" / "hexagonos_mercado_mapeado.parquet"
OUT_PATH = ROOT / "data" / "staging" / "unidades_ultra_performance_hex.parquet"

HEX_REQUIRED_COLS = {
    "hex_id",
    "flag_censo_elegivel",
    "pop_total_setor_2022",
    "populacao_proxy",
}

HEX_OPTIONAL_COLS = [
    "uf",
    "cidade",
    "lat",
    "lng",
    "renda_per_capita",
    "renda_per_capita_setor_2022_calibrada",
    "densidade_pop_setor_hab_km2",
    "score_priorizacao",
    "score_oficial",
    "rank_brasil",
    "rank_uf",
    "rank_cidade",
    "flag_hex_hibrido_elegivel",
    "score_expansao_hibrido",
    "n_concorrentes_mapeados_1km",
    "n_concorrentes_mapeados_2km",
    "dist_concorrente_mais_proximo_m",
    "flag_white_space_2km",
    "flag_canibalizacao_ultra_1km",
    "dist_ultra_mais_proxima_m",
]

HEX_RENAME = {
    "uf": "uf_hex",
    "cidade": "cidade_hex",
    "lat": "lat_hex_centroide",
    "lng": "lng_hex_centroide",
}

MIN_OUTPUT_COLUMNS = {
    "unidade",
    "uf",
    "cidade",
    "lat",
    "lng",
    "hex_id_res7",
    "hex_id",
    "pop_hex_base",
    "fonte_pop_hex_base",
    "penetracao_ultra_alunos_total",
    "penetracao_ultra_pagantes",
    "receita_por_habitante_hex",
    "ticket_medio_aluno",
    "alunos_por_m2",
    "rank_penetracao_ultra_alunos_total",
    "rank_penetracao_ultra_pagantes",
    "rank_receita_por_habitante_hex",
}

POP_SOURCE_VALUES = {
    "censo_2022_hex",
    "m1_municipal_proxy",
    "hex_nao_encontrado",
    "sem_hex_id_res7",
    "sem_populacao_valida",
}


def _safe_div(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce")
    valid_denominator = denominator.where(denominator > 0)
    return numerator / valid_denominator


def _rank_desc(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").rank(ascending=False, method="min").astype("Int64")


def _bool_series(value: object, index: pd.Index) -> pd.Series:
    if isinstance(value, pd.Series):
        series = value.reindex(index)
    else:
        series = pd.Series(value, index=index)
    return series.map(lambda item: bool(item) if pd.notna(item) else False).astype(bool)


def _read_parquet_columns(path: Path, required: set[str], optional: list[str]) -> pd.DataFrame:
    available = set(pq.read_schema(path).names)
    missing = required - available
    if missing:
        raise AssertionError(f"Colunas obrigatorias ausentes em {path.name}: {sorted(missing)}")
    columns = sorted(required | (available & set(optional)))
    return pd.read_parquet(path, columns=columns)


def carregar_hexagonos(path: Path = HEXAGONOS_PATH) -> pd.DataFrame:
    hexagonos = _read_parquet_columns(path, HEX_REQUIRED_COLS, HEX_OPTIONAL_COLS)
    if hexagonos["hex_id"].duplicated().any():
        n_dup = int(hexagonos["hex_id"].duplicated().sum())
        raise AssertionError(f"Base de hexagonos com hex_id duplicado: {n_dup}")
    return hexagonos.rename(columns=HEX_RENAME)


def anexar_hexagonos(unidades: pd.DataFrame, hexagonos: pd.DataFrame) -> pd.DataFrame:
    return unidades.merge(
        hexagonos,
        left_on="hex_id_res7",
        right_on="hex_id",
        how="left",
        validate="many_to_one",
    )


def calcular_metricas(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    pop_censo = pd.to_numeric(out.get("pop_total_setor_2022"), errors="coerce")
    pop_proxy = pd.to_numeric(out.get("populacao_proxy"), errors="coerce")
    flag_censo = _bool_series(out.get("flag_censo_elegivel", False), out.index)

    censo_ok = flag_censo & pop_censo.notna() & (pop_censo > 0)
    proxy_ok = pop_proxy.notna() & (pop_proxy > 0)
    sem_hex_id = out["hex_id_res7"].isna()
    sem_match_hex = out["hex_id_res7"].notna() & out["hex_id"].isna()

    out["pop_hex_base"] = np.select(
        [censo_ok, proxy_ok],
        [pop_censo, pop_proxy],
        default=np.nan,
    )
    out["fonte_pop_hex_base"] = np.select(
        [censo_ok, proxy_ok, sem_hex_id, sem_match_hex],
        ["censo_2022_hex", "m1_municipal_proxy", "sem_hex_id_res7", "hex_nao_encontrado"],
        default="sem_populacao_valida",
    )

    if "ticket_medio_aluno" not in out.columns:
        out["ticket_medio_aluno"] = np.nan
    ticket_calculado = _safe_div(out["faturamento"], out["alunos_total"])
    out["ticket_medio_aluno"] = pd.to_numeric(out["ticket_medio_aluno"], errors="coerce")
    out["ticket_medio_aluno"] = out["ticket_medio_aluno"].where(
        out["ticket_medio_aluno"].notna(), ticket_calculado
    )

    out["penetracao_ultra_alunos_total"] = _safe_div(out["alunos_total"], out["pop_hex_base"])
    out["penetracao_ultra_pagantes"] = _safe_div(out["ativos_pag"], out["pop_hex_base"])
    out["receita_por_habitante_hex"] = _safe_div(out["faturamento"], out["pop_hex_base"])

    if "metragem" in out.columns:
        out["alunos_por_m2"] = _safe_div(out["alunos_total"], out["metragem"])
    else:
        out["alunos_por_m2"] = np.nan

    out["rank_penetracao_ultra_alunos_total"] = _rank_desc(out["penetracao_ultra_alunos_total"])
    out["rank_penetracao_ultra_pagantes"] = _rank_desc(out["penetracao_ultra_pagantes"])
    out["rank_receita_por_habitante_hex"] = _rank_desc(out["receita_por_habitante_hex"])
    return out


def gerar_base(
    unidades_path: Path = UNIDADES_PATH,
    hexagonos_path: Path = HEXAGONOS_PATH,
) -> pd.DataFrame:
    unidades = pd.read_parquet(unidades_path)
    hexagonos = carregar_hexagonos(hexagonos_path)
    merged = anexar_hexagonos(unidades, hexagonos)
    return calcular_metricas(merged).sort_values("performance_source_index", kind="stable").reset_index(drop=True)


def validar(df: pd.DataFrame) -> None:
    print("\n=== Validacao: unidades_ultra_performance_hex ===")
    print(f"Total de linhas: {len(df)}")

    faltam = MIN_OUTPUT_COLUMNS - set(df.columns)
    assert not faltam, f"Schema incompleto: faltam {sorted(faltam)}"
    print("Schema minimo OK")

    if "performance_source_index" in df.columns:
        assert not df["performance_source_index"].duplicated().any(), (
            "Duplicidade em performance_source_index apos join"
        )
    print("Cardinalidade de unidades preservada OK")

    fontes = set(df["fonte_pop_hex_base"].dropna().unique())
    assert fontes <= POP_SOURCE_VALUES, f"Fontes inesperadas: {fontes - POP_SOURCE_VALUES}"

    censo = df["fonte_pop_hex_base"].eq("censo_2022_hex")
    if censo.any():
        assert _bool_series(df.loc[censo, "flag_censo_elegivel"], df.loc[censo].index).all()
        assert np.allclose(
            df.loc[censo, "pop_hex_base"],
            df.loc[censo, "pop_total_setor_2022"],
            equal_nan=False,
        )

    proxy = df["fonte_pop_hex_base"].eq("m1_municipal_proxy")
    if proxy.any():
        assert np.allclose(
            df.loc[proxy, "pop_hex_base"],
            df.loc[proxy, "populacao_proxy"],
            equal_nan=False,
        )
    print("Fontes de populacao OK")

    sem_pop = df["pop_hex_base"].isna() | (pd.to_numeric(df["pop_hex_base"], errors="coerce") <= 0)
    metric_cols = [
        "penetracao_ultra_alunos_total",
        "penetracao_ultra_pagantes",
        "receita_por_habitante_hex",
    ]
    assert df.loc[sem_pop, metric_cols].isna().all().all(), (
        "Metricas de penetracao calculadas sem populacao valida"
    )
    assert (df.loc[~sem_pop, metric_cols].fillna(0) >= 0).all().all(), (
        "Metricas de penetracao negativas"
    )
    assert (df["alunos_por_m2"].dropna() >= 0).all(), "alunos_por_m2 negativo"
    print("Divisoes e metricas OK")

    ranked = df["rank_penetracao_ultra_alunos_total"].dropna()
    assert not ranked.empty, "Ranking de penetracao vazio"
    assert int(ranked.min()) == 1, "Ranking de penetracao sem primeira posicao"
    print("Ranking de penetracao OK")

    print("\nFontes de populacao:")
    print(df["fonte_pop_hex_base"].value_counts(dropna=False).to_string())
    print("\nTop 5 por penetracao alunos totais:")
    cols = ["unidade", "uf", "pop_hex_base", "alunos_total", "penetracao_ultra_alunos_total"]
    print(df.sort_values("penetracao_ultra_alunos_total", ascending=False)[cols].head(5).to_string(index=False))
    print("\nValidacao OK")


def main() -> None:
    print("Bloco 2 - Penetracao Ultra por hexagono")
    print("=" * 50)

    df = gerar_base(UNIDADES_PATH, HEXAGONOS_PATH)
    validar(df)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH, index=False)
    print(f"\nSalvo: {OUT_PATH}")
    print("Bloco 2 concluido.")


if __name__ == "__main__":
    main()
