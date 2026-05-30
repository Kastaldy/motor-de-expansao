from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from dashboard.constants import (
    BOOL_COLUMNS,
    COVERAGE_BUCKET_ORDER,
    FAIXA_ORDEM,
    FLOAT_COLUMNS,
    HYBRID_ELIGIBILITY_ORDER,
    JOIN_QUALITY_ORDER,
    MAP_SORT_ASCENDING,
    MAP_SORT_COLUMNS,
    OPTIONAL_DATASET_COLUMNS,
    POP_MIN_ACIONAVEL,
    RESIDUAL_MERCADO_COLS,
    TEXT_COLUMNS,
)


def _read_parquet_subset(path: Path, columns: list[str]) -> pd.DataFrame:
    available_columns = pq.read_schema(path).names
    missing = [column for column in columns if column not in available_columns]
    if missing:
        raise ValueError(
            "O dataset oficial nao contem todas as colunas obrigatorias do dashboard: "
            + ", ".join(missing)
        )
    optional_columns = [
        column for column in OPTIONAL_DATASET_COLUMNS
        if column in available_columns and column not in columns
    ]
    return pd.read_parquet(path, columns=columns + optional_columns)


def _read_optional_parquet_subset(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    available_columns = pq.read_schema(path).names
    cols = [column for column in columns if column in available_columns]
    if not cols:
        return pd.DataFrame()
    return pd.read_parquet(path, columns=cols)


def list_partitioned_ufs(base_dir: Path) -> list[str]:
    """Lista as UFs do dataset enriquecido particionado (`uf=XX`).

    Catalogo leve para a sidebar: inspeciona apenas os diretorios de particao,
    sem carregar dados. Retorna lista vazia quando o dataset nao existe.
    """
    base = Path(base_dir)
    if not base.is_dir():
        return []
    ufs = [
        child.name.split("=", 1)[1]
        for child in base.iterdir()
        if child.is_dir() and child.name.startswith("uf=")
    ]
    return sorted(uf for uf in ufs if uf)


def read_enriched_uf_partition(base_dir: Path, uf: str) -> pd.DataFrame:
    """Le apenas a particao `uf=XX` do dataset enriquecido (Bloco 3).

    Restaura tipos/categoricos via `_prepare_dataframe` para igualar o frame que
    `enrich_dashboard_data` produziria em runtime. Retorna DataFrame vazio quando
    o dataset ou a particao nao existem. Nao recalcula score nem altera artefatos.
    """
    base = Path(base_dir)
    if not base.is_dir():
        return pd.DataFrame()
    dataset = ds.dataset(str(base), format="parquet", partitioning="hive")
    frame = dataset.to_table(filter=ds.field("uf") == str(uf)).to_pandas()
    if frame.empty:
        return frame
    return _prepare_dataframe(frame)


def resolve_cod_municipio_from_geo_dir(
    base_dir: Path,
    uf: str,
    nome_municipio: str,
) -> str | None:
    """Resolve cod_municipio pelo nome do municipio varrendo o artefato geo censitario.

    Le apenas uma linha e a coluna `nome_municipio` de cada particao para
    identificar o codigo sem carregar dados completos. Retorna None se nao
    encontrar correspondencia exata (case-insensitive).
    """
    uf_dir = Path(base_dir) / f"uf={str(uf).upper()}"
    if not uf_dir.is_dir():
        return None
    nome_norm = str(nome_municipio).strip().upper()
    if not nome_norm:
        return None
    for child in sorted(uf_dir.iterdir()):
        if not child.is_dir() or not child.name.startswith("cod_municipio="):
            continue
        cod = child.name.split("=", 1)[1]
        try:
            sample = pd.read_parquet(child, columns=["nome_municipio"]).head(1)
            if not sample.empty and str(sample.iloc[0]["nome_municipio"]).strip().upper() == nome_norm:
                return cod
        except Exception:
            pass
    return None


def list_censo_geo_municipios(base_dir: Path, uf: str) -> list[str]:
    """Lista municipios materializados no artefato geo censitario de uma UF."""
    uf_dir = Path(base_dir) / f"uf={str(uf).upper()}"
    if not uf_dir.is_dir():
        return []
    municipios = [
        child.name.split("=", 1)[1]
        for child in uf_dir.iterdir()
        if child.is_dir() and child.name.startswith("cod_municipio=")
    ]
    return sorted(m for m in municipios if m)


def read_censo_geo_partition(
    base_dir: Path,
    uf: str,
    cod_municipio: str | None = None,
) -> pd.DataFrame:
    """Le setores censitarios geograficos por UF e, quando possivel, municipio.

    O artefato e derivado e particionado como
    `setores_censitarios_2022_geo/uf=XX/cod_municipio=NNNNNNN`. Este helper nao
    recalcula score nem toca nos artefatos oficiais do M1; apenas carrega o
    recorte necessario ao relatorio pontual censitario.
    """
    base = Path(base_dir)
    uf_value = str(uf).upper()
    if not base.is_dir():
        return pd.DataFrame()

    if cod_municipio:
        cod_value = str(cod_municipio)
        part_dir = base / f"uf={uf_value}" / f"cod_municipio={cod_value}"
        if part_dir.is_dir():
            frame = pd.read_parquet(part_dir)
            if "uf" not in frame.columns:
                frame["uf"] = uf_value
            if "cod_municipio" not in frame.columns:
                frame["cod_municipio"] = cod_value
            return frame.reset_index(drop=True)
        return pd.DataFrame()

    uf_dir = base / f"uf={uf_value}"
    if not uf_dir.is_dir():
        return pd.DataFrame()

    dataset = ds.dataset(str(base), format="parquet", partitioning="hive")
    filter_expr = ds.field("uf") == uf_value
    return dataset.to_table(filter=filter_expr).to_pandas().reset_index(drop=True)


def _normalized_join_quality(df: pd.DataFrame) -> pd.Series:
    if "qualidade_join_uf" not in df.columns:
        return pd.Series("", index=df.index, dtype="object")
    return (
        df["qualidade_join_uf"]
        .astype(object)
        .where(df["qualidade_join_uf"].notna(), "")
        .astype(str)
        .str.upper()
    )


def _has_censo_signal(df: pd.DataFrame) -> pd.Series:
    signal = pd.Series(False, index=df.index)
    if "flag_censo_disponivel" in df.columns:
        signal |= df["flag_censo_disponivel"].fillna(False).astype(bool)
    if "score_setor_2022_calibrado" in df.columns:
        signal |= df["score_setor_2022_calibrado"].notna()
    return signal


def _derive_confianca_geografica(df: pd.DataFrame) -> pd.Series:
    if "confianca_geografica" in df.columns:
        base = (
            df["confianca_geografica"]
            .astype(object)
            .where(df["confianca_geografica"].notna(), "municipal")
            .astype(str)
            .str.lower()
        )
        base = base.where(base.isin(["granular", "municipal"]), "municipal")
    else:
        base = pd.Series("municipal", index=df.index, dtype="object")

    granular_mask = _normalized_join_quality(df).isin(["A", "B"]) & _has_censo_signal(df)
    return pd.Series(
        np.where(granular_mask, "granular", base),
        index=df.index,
        dtype="object",
    )


def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()
    for column in FLOAT_COLUMNS:
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce").astype("Float32")

    for column in BOOL_COLUMNS:
        if column in prepared.columns:
            prepared[column] = prepared[column].astype("boolean").fillna(False).astype(bool)

    for column in TEXT_COLUMNS:
        if column in prepared.columns:
            prepared[column] = (
                prepared[column]
                .astype(object)
                .where(prepared[column].notna(), "Nao informado")
                .astype("category")
            )

    if "faixa_oportunidade" in prepared.columns:
        prepared["faixa_oportunidade"] = (
            prepared["faixa_oportunidade"]
            .astype(object)
            .where(prepared["faixa_oportunidade"].notna(), "Nao informado")
        )
        prepared["faixa_oportunidade"] = pd.Categorical(
            prepared["faixa_oportunidade"],
            categories=FAIXA_ORDEM + ["Nao informado"],
            ordered=True,
        )

    if "elegibilidade_hibrida" in prepared.columns:
        prepared["elegibilidade_hibrida"] = pd.Categorical(
            prepared["elegibilidade_hibrida"].fillna("Sem camada"),
            categories=HYBRID_ELIGIBILITY_ORDER,
            ordered=True,
        )

    if "cobertura_censitaria_bucket" in prepared.columns:
        prepared["cobertura_censitaria_bucket"] = pd.Categorical(
            prepared["cobertura_censitaria_bucket"].fillna("Sem camada"),
            categories=COVERAGE_BUCKET_ORDER,
            ordered=True,
        )

    if "qualidade_camada" in prepared.columns:
        prepared["qualidade_camada"] = pd.Categorical(
            prepared["qualidade_camada"].fillna("Sem camada"),
            categories=JOIN_QUALITY_ORDER,
            ordered=True,
        )

    prepared = prepared.sort_values(
        MAP_SORT_COLUMNS,
        ascending=MAP_SORT_ASCENDING,
        kind="stable",
    ).reset_index(drop=True)
    prepared["UF"] = prepared["uf"]
    if "nome_municipio" in prepared.columns:
        prepared["nome_municipio"] = prepared["nome_municipio"].fillna(prepared["cidade"])
    else:
        prepared["nome_municipio"] = prepared["cidade"]
    prepared["score_exibicao"] = prepared["score_priorizacao"]
    return prepared


def _prepare_censo_trace(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    prepared = df.copy()
    if "classe_join_uf" in prepared.columns and "qualidade_join_uf" not in prepared.columns:
        prepared = prepared.rename(columns={"classe_join_uf": "qualidade_join_uf"})

    for column in [
        "score_setor_2022_calibrado",
        "densidade_pop_setor_hab_km2",
        "coverage_pct_setor_2022",
        "delta_vs_vizinhos",
        "renda_per_capita_setor_2022_calibrada",
    ]:
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce").astype("Float32")

    for column in ["flag_join_uf_restrito", "flag_baixa_pop_setor", "flag_outlier_espacial"]:
        if column in prepared.columns:
            prepared[column] = prepared[column].fillna(False).astype(bool)

    return prepared


def _coalesce_columns(df: pd.DataFrame, base_column: str, overlay_column: str) -> pd.DataFrame:
    if overlay_column not in df.columns:
        return df
    if base_column in df.columns:
        df[base_column] = df[base_column].where(df[base_column].notna(), df[overlay_column])
    else:
        df[base_column] = df[overlay_column]
    return df.drop(columns=[overlay_column])


def _derive_hybrid_labels(df: pd.DataFrame) -> pd.DataFrame:
    derived = df.copy()
    available = derived["flag_censo_disponivel"].fillna(False) | derived["score_setor_2022_calibrado"].notna()
    eligible = derived["flag_censo_elegivel"].fillna(False)
    derived["elegibilidade_hibrida"] = np.where(
        eligible,
        "Elegivel",
        np.where(available, "Nao elegivel", "Sem camada"),
    )

    coverage = pd.to_numeric(derived["coverage_pct_setor_2022"], errors="coerce")
    derived["cobertura_censitaria_bucket"] = np.select(
        [
            coverage.ge(99.95).fillna(False).to_numpy(),
            coverage.ge(95.0).fillna(False).to_numpy(),
            coverage.ge(85.0).fillna(False).to_numpy(),
            coverage.notna().to_numpy(),
        ],
        ["100%", "95-99,9%", "85-94,9%", "<85%"],
        default="Sem camada",
    )

    quality = (
        derived["qualidade_join_uf"]
        .astype(object)
        .where(derived["qualidade_join_uf"].notna(), "")
        .astype(str)
        .str.upper()
    )
    derived["qualidade_camada"] = np.where(
        quality.isin(["A", "B", "C"]),
        quality,
        "Sem camada",
    )
    return derived


def enrich_dashboard_data(
    base_df: pd.DataFrame,
    hybrid_df: pd.DataFrame | None = None,
    censo_df: pd.DataFrame | None = None,
    estrutural_pop_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    enriched = base_df.copy()
    hybrid_df = hybrid_df if hybrid_df is not None else pd.DataFrame()
    censo_df = censo_df if censo_df is not None else pd.DataFrame()

    # Injeta pop_total do parquet estrutural quando disponivel para manter
    # fallback municipal explicito e resiliente a parquets legados.
    if estrutural_pop_df is not None and not estrutural_pop_df.empty:
        if "pop_total" in estrutural_pop_df.columns and "hex_id" in estrutural_pop_df.columns:
            pop_map = estrutural_pop_df.set_index("hex_id")["pop_total"]
            enriched["pop_total"] = enriched["hex_id"].map(pop_map)

    hybrid_extra_cols = [
        "hex_id",
        "nome_municipio",
        "confianca_geografica",
        "score_setor_2022_calibrado",
        "score_expansao_hibrido",
        "densidade_pop_setor_hab_km2",
        "top_municipio",
        "top_hex_intraurbano",
        "flag_censo_elegivel",
        "flag_censo_disponivel",
        "flag_hex_hibrido_elegivel",
        "top_municipio_hibrido",
        "municipio_censo_disponivel",
        "rank_municipio_uf",
        "rank_municipio_brasil",
        "rank_hex_intraurbano",
        "rank_hibrido_brasil",
        "rank_hibrido_uf",
        "top_oportunidade_municipio",
        "top_oportunidade_brasil",
        "top_oportunidade_uf",
        "qualidade_join_uf",
        "flag_join_uf_restrito",
        "flag_baixa_pop_setor",
        "flag_outlier_espacial",
        "coverage_pct_setor_2022",
        "motivo_nao_elegivel_censo",
        "status_espacial_uf",
        "fonte_camada_censitaria",
        "flag_monitoramento_prioritario",
        "criterio_score_expansao_hibrido",
        "camada_modelo_hibrido",
        "pop_total_setor_2022",
        *RESIDUAL_MERCADO_COLS,
    ]
    if not hybrid_df.empty:
        hybrid_subset = hybrid_df[[column for column in hybrid_extra_cols if column in hybrid_df.columns]]
        enriched = enriched.merge(hybrid_subset, on="hex_id", how="left")

    censo_extra_cols = [
        "hex_id",
        "cod_municipio",
        "nome_municipio",
        "confianca_geografica",
        "score_setor_2022_calibrado",
        "densidade_pop_setor_hab_km2",
        "coverage_pct_setor_2022",
        "qualidade_join_uf",
        "flag_join_uf_restrito",
        "flag_baixa_pop_setor",
        "flag_outlier_espacial",
        "causa_outlier_espacial",
        "delta_vs_vizinhos",
        "metodo_join_setor_2022",
        "motivo_fallback_setor_2022",
        "renda_per_capita_setor_2022_calibrada",
        "pop_total_setor_2022",
    ]
    if not censo_df.empty:
        censo_subset = censo_df[[column for column in censo_extra_cols if column in censo_df.columns]]
        enriched = enriched.merge(censo_subset, on="hex_id", how="left", suffixes=("", "_censo"))

        for column in [
            "nome_municipio",
            "score_setor_2022_calibrado",
            "densidade_pop_setor_hab_km2",
            "coverage_pct_setor_2022",
            "qualidade_join_uf",
            "flag_join_uf_restrito",
            "flag_baixa_pop_setor",
            "flag_outlier_espacial",
        ]:
            censo_column = f"{column}_censo"
            enriched = _coalesce_columns(enriched, column, censo_column)

    for column in [
        "top_municipio",
        "top_hex_intraurbano",
        "flag_censo_elegivel",
        "flag_censo_disponivel",
        "flag_hex_hibrido_elegivel",
        "top_municipio_hibrido",
        "municipio_censo_disponivel",
        "flag_join_uf_restrito",
        "flag_baixa_pop_setor",
        "flag_outlier_espacial",
        "flag_monitoramento_prioritario",
        "top_oportunidade_municipio",
        "top_oportunidade_brasil",
        "top_oportunidade_uf",
    ]:
        if column not in enriched.columns:
            enriched[column] = False

    for column in [
        "qualidade_join_uf",
        "motivo_nao_elegivel_censo",
        "status_espacial_uf",
        "fonte_camada_censitaria",
        "criterio_score_expansao_hibrido",
        "camada_modelo_hibrido",
        "causa_outlier_espacial",
        "metodo_join_setor_2022",
        "motivo_fallback_setor_2022",
        "score_setor_2022_calibrado",
        "coverage_pct_setor_2022",
    ]:
        if column not in enriched.columns:
            enriched[column] = pd.NA

    if "nome_municipio" not in enriched.columns:
        enriched["nome_municipio"] = enriched["cidade"]

    enriched["nome_municipio"] = (
        enriched["nome_municipio"]
        .fillna(enriched["cidade"])
        .replace({"": pd.NA})
        .fillna(enriched["cidade"])
    )
    enriched["confianca_geografica"] = _derive_confianca_geografica(enriched)
    enriched = _derive_hybrid_labels(enriched)
    enriched = derive_pop_cut_columns(enriched)
    return _prepare_dataframe(enriched)


def apply_global_filters(
    df: pd.DataFrame,
    *,
    selected_ufs: list[str],
    selected_cities: list[str],
    selected_faixas: list[str],
    selected_hybrid_eligibility: list[str] | None = None,
    selected_coverage_buckets: list[str] | None = None,
    selected_join_quality: list[str] | None = None,
    only_top_municipio: bool = False,
    only_top_hex_intraurbano: bool = False,
) -> pd.DataFrame:
    selected_hybrid_eligibility = selected_hybrid_eligibility or []
    selected_coverage_buckets = selected_coverage_buckets or []
    selected_join_quality = selected_join_quality or []
    mask = pd.Series(True, index=df.index)
    if selected_ufs:
        mask &= df["uf"].isin(selected_ufs)
    if selected_cities:
        city_col = "nome_municipio" if "nome_municipio" in df.columns else "cidade"
        mask &= df[city_col].isin(selected_cities)
    if selected_faixas:
        mask &= df["faixa_oportunidade"].isin(selected_faixas)
    if selected_hybrid_eligibility and "elegibilidade_hibrida" in df.columns:
        mask &= df["elegibilidade_hibrida"].isin(selected_hybrid_eligibility)
    if selected_coverage_buckets and "cobertura_censitaria_bucket" in df.columns:
        mask &= df["cobertura_censitaria_bucket"].isin(selected_coverage_buckets)
    if selected_join_quality and "qualidade_camada" in df.columns:
        mask &= df["qualidade_camada"].isin(selected_join_quality)
    if only_top_municipio and "top_municipio" in df.columns:
        mask &= df["top_municipio"].eq(True)  # invariante a `== True`; evita E712 preservando semantica pandas/NaN
    if only_top_hex_intraurbano and "top_hex_intraurbano" in df.columns:
        mask &= df["top_hex_intraurbano"].eq(True)  # invariante a `== True`; evita E712 preservando semantica pandas/NaN
    return df.loc[mask]


def build_city_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "uf",
                "cidade",
                "total_hexagonos",
                "oportunidades_viaveis",
                "hexagonos_priorizados",
                "score_medio",
                "renda_per_capita",
                "populacao_proxy",
                "melhor_rank_brasil",
                "pct_priorizados",
            ]
        )

    grouped = (
        df.groupby(["uf", "cidade"], as_index=False, observed=True)
        .agg(
            total_hexagonos=("hex_id", "size"),
            oportunidades_viaveis=("flag_viavel", "sum"),
            hexagonos_priorizados=("flag_prioridade", "sum"),
            score_medio=("score_priorizacao", "mean"),
            renda_per_capita=("renda_per_capita", "mean"),
            populacao_proxy=("populacao_proxy", "mean"),
            melhor_rank_brasil=("rank_brasil", "min"),
        )
        .copy()
    )
    grouped["pct_priorizados"] = (
        grouped["hexagonos_priorizados"] / grouped["total_hexagonos"] * 100
    ).fillna(0.0)
    return grouped


def derive_pop_cut_columns(df: pd.DataFrame, pop_min: int = POP_MIN_ACIONAVEL) -> pd.DataFrame:
    """Deriva colunas auditaveis para a regua operacional de populacao minima.

    - populacao_corte_hex: valor usado no corte (setor 2022 preferencial, fallback total municipal)
    - fonte_populacao_corte: origem do valor ("setor_2022", "total_municipal" ou "ausente")
    - flag_pop_min_5k: True quando populacao_corte_hex >= pop_min
    Nao altera score_priorizacao nem artefatos oficiais do M1.
    """
    result = df.copy()
    is_granular = (
        result["confianca_geografica"].eq("granular")
        if "confianca_geografica" in result.columns
        else pd.Series(False, index=result.index)
    )
    has_setor = "pop_total_setor_2022" in result.columns
    # Preferir pop_total (total real) sobre populacao_proxy legado (proxy 18-45 antigo).
    has_pop_total = "pop_total" in result.columns
    has_proxy = "populacao_proxy" in result.columns

    pop_municipal = (
        result["pop_total"] if has_pop_total else
        result["populacao_proxy"] if has_proxy else
        pd.Series(pd.NA, index=result.index, dtype="Float64")
    )
    pop_municipal_notna = (
        result["pop_total"].notna() if has_pop_total else
        result["populacao_proxy"].notna() if has_proxy else
        pd.Series(False, index=result.index)
    )

    if has_setor:
        use_setor = is_granular & result["pop_total_setor_2022"].notna()
        pop_val = result["pop_total_setor_2022"].where(use_setor, pop_municipal)
        fonte = np.where(
            use_setor,
            "setor_2022",
            np.where(pop_municipal_notna, "total_municipal", "ausente"),
        )
    else:
        pop_val = pop_municipal
        fonte = np.where(pop_municipal_notna, "total_municipal", "ausente")

    result["populacao_corte_hex"] = pd.to_numeric(pop_val, errors="coerce")
    result["fonte_populacao_corte"] = fonte
    result["flag_pop_min_5k"] = result["populacao_corte_hex"].ge(pop_min).fillna(False)
    return result


def build_pop_cut_lookup(enriched_df: pd.DataFrame) -> pd.DataFrame:
    """Extrai lookup leve {hex_id -> colunas de corte} para enriquecer carteira/plano."""
    cols = [c for c in ["hex_id", "populacao_corte_hex", "fonte_populacao_corte", "flag_pop_min_5k"] if c in enriched_df.columns]
    if "hex_id" not in cols:
        return pd.DataFrame()
    return enriched_df[cols].drop_duplicates(subset=["hex_id"]).copy()


def build_uf_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "uf",
                "total_hexagonos",
                "oportunidades_viaveis",
                "hexagonos_priorizados",
                "score_medio",
                "pct_priorizados",
            ]
        )

    grouped = (
        df.groupby("uf", as_index=False, observed=True)
        .agg(
            total_hexagonos=("hex_id", "size"),
            oportunidades_viaveis=("flag_viavel", "sum"),
            hexagonos_priorizados=("flag_prioridade", "sum"),
            score_medio=("score_priorizacao", "mean"),
        )
        .copy()
    )
    grouped["pct_priorizados"] = (
        grouped["hexagonos_priorizados"] / grouped["total_hexagonos"] * 100
    ).fillna(0.0)
    return grouped


# ── Coordinate search ────────────────────────────────────────────────────────

_BRAZIL_LAT_MIN = -33.75
_BRAZIL_LAT_MAX = 5.27
_BRAZIL_LNG_MIN = -73.99
_BRAZIL_LNG_MAX = -28.65


def _validate_brazil_bbox(lat: float, lng: float) -> tuple[float, float] | None:
    if _BRAZIL_LAT_MIN <= lat <= _BRAZIL_LAT_MAX and _BRAZIL_LNG_MIN <= lng <= _BRAZIL_LNG_MAX:
        return lat, lng
    return None


def parse_coordinate_input(text: str) -> tuple[float, float] | None:
    """Parse a coordinate string in common formats and validate for Brazil.

    Accepted formats:
    - ``-23.55,-46.63``  (dot decimal, comma separator)
    - ``-23,55; -46,63`` (BR comma decimal, semicolon separator)
    - ``-23.55 -46.63``  (space separator)
    - ``-23,55 -46,63``  (BR comma decimal, space separator)

    Returns ``(lat, lng)`` or ``None`` if invalid or outside Brazil bounding box.
    """
    if not text or not text.strip():
        return None
    text = text.strip()

    # Semicolon separator (handles BR comma-as-decimal)
    m = re.match(r'^([+-]?\d+[.,]\d+)\s*;\s*([+-]?\d+[.,]\d+)$', text)
    if m:
        try:
            lat = float(m.group(1).replace(',', '.'))
            lng = float(m.group(2).replace(',', '.'))
            return _validate_brazil_bbox(lat, lng)
        except ValueError:
            pass

    # Dot decimal with comma separator: -23.55,-46.63
    m = re.match(r'^([+-]?\d+\.\d+)\s*,\s*([+-]?\d+\.\d+)$', text)
    if m:
        try:
            lat, lng = float(m.group(1)), float(m.group(2))
            return _validate_brazil_bbox(lat, lng)
        except ValueError:
            pass

    # Space separator (dot or comma decimal)
    parts = text.split()
    if len(parts) == 2:
        try:
            lat = float(parts[0].replace(',', '.'))
            lng = float(parts[1].replace(',', '.'))
            return _validate_brazil_bbox(lat, lng)
        except ValueError:
            pass

    # Comma separator where second token starts with minus: -23,55,-46,63
    m = re.match(r'^([+-]?\d+(?:[.,]\d+)?)\s*,\s*(-\d+(?:[.,]\d+)?)$', text)
    if m:
        try:
            lat = float(m.group(1).replace(',', '.'))
            lng = float(m.group(2).replace(',', '.'))
            return _validate_brazil_bbox(lat, lng)
        except ValueError:
            pass

    return None


_RAIO_DEFAULT_KM: float = 1.6
_AREA_RAIO_KM2: float = round(3.14159265358979 * _RAIO_DEFAULT_KM**2, 2)
_POP_RAIO_COLUMNS: tuple[tuple[str, str], ...] = (
    ("pop_total_setor_2022", "setor_2022"),
    ("pop_hex_base", "pop_hex_base"),
    ("pop_total", "pop_total"),
    ("populacao_proxy", "populacao_proxy"),
)
_RENDA_RAIO_COLUMNS: tuple[tuple[str, str], ...] = (
    ("renda_per_capita_setor_2022_calibrada", "setor_2022_calibrado"),
    ("renda_per_capita", "renda_per_capita"),
)


def haversine_km(
    lat1: float,
    lat2: np.ndarray | float,
    lng1: float,
    lng2: np.ndarray | float,
) -> np.ndarray:
    """Vectorized haversine distance (km) from scalar (lat1, lng1) to array (lat2, lng2)."""
    R = 6371.0
    lat1_r = np.radians(lat1)
    lat2_r = np.radians(lat2)
    dlat = lat2_r - lat1_r
    dlng = np.radians(lng2) - np.radians(lng1)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlng / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(np.maximum(0.0, 1.0 - a)))


def _coalesce_numeric_with_source(
    df: pd.DataFrame,
    candidates: tuple[tuple[str, str], ...],
) -> tuple[pd.Series, pd.Series]:
    values = pd.Series(np.nan, index=df.index, dtype="float64")
    sources = pd.Series("ausente", index=df.index, dtype="object")
    for column, source in candidates:
        if column not in df.columns:
            continue
        numeric = pd.to_numeric(df[column], errors="coerce")
        use_value = values.isna() & numeric.notna()
        values = values.where(~use_value, numeric)
        sources = sources.where(~use_value, source)
    return values, sources


def _summarize_sources(sources: pd.Series) -> str:
    valid_sources = [str(source) for source in sources.dropna().unique().tolist() if str(source) != "ausente"]
    if not valid_sources:
        return "ausente"
    if len(valid_sources) == 1:
        return valid_sources[0]
    return "misto: " + ", ".join(valid_sources)


def analisar_entorno_ponto(
    lat: float,
    lng: float,
    hex_df: pd.DataFrame,
    raio_km: float = _RAIO_DEFAULT_KM,
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
    dominio_df: pd.DataFrame | None = None,
) -> dict:
    """Aggregate hex/candidate metrics within raio_km of (lat, lng).

    Uses haversine distance from hex centroid to the query point. Results are
    approximate: without fine street/sector geometries, precision reflects
    centroid proximity only. Does not recalculate or alter score_priorizacao,
    hex_score_estrutural, carteira, plano or any official M1 artifact.
    """
    area_km2 = round(3.14159265358979 * raio_km**2, 2)
    result: dict = {
        "lat": lat,
        "lng": lng,
        "raio_km": raio_km,
        "area_km2": area_km2,
        "n_hexes": 0,
        "residual_total": None,
        "score_residual_medio": None,
        "score_residual_max": None,
        "score_m1_medio": None,
        "score_m1_max": None,
        "score_hibrido_medio": None,
        "score_hibrido_max": None,
        "pop_total_raio": None,
        "fonte_pop_total_raio": "ausente",
        "renda_per_capita_media_raio": None,
        "metodo_renda_raio": "ausente",
        "n_hexes_com_pop": 0,
        "n_hexes_com_renda": 0,
        "n_concorrentes": 0,
        "n_ultra": 0,
        "n_ancoras_dominio": 0,
        "consumo_concorrentes_raio": None,
        "consumo_ultra_raio": None,
        "hexes_entorno": pd.DataFrame(),
    }

    def _count_in_radius(df_pts: pd.DataFrame | None) -> int:
        if df_pts is None or df_pts.empty:
            return 0
        if "lat" not in df_pts.columns or "lng" not in df_pts.columns:
            return 0
        dists = haversine_km(lat, df_pts["lat"].to_numpy(dtype=float), lng, df_pts["lng"].to_numpy(dtype=float))
        return int((dists <= raio_km).sum())

    if hex_df is None or hex_df.empty or "lat" not in hex_df.columns or "lng" not in hex_df.columns:
        result["n_concorrentes"] = _count_in_radius(competitors_df)
        result["n_ultra"] = _count_in_radius(ultra_df)
        result["n_ancoras_dominio"] = _count_in_radius(dominio_df)
        return result

    dists = haversine_km(lat, hex_df["lat"].to_numpy(dtype=float), lng, hex_df["lng"].to_numpy(dtype=float))
    mask = dists <= raio_km
    nearby = hex_df.loc[mask].copy()
    nearby["dist_km"] = np.round(dists[mask], 4)

    result["n_hexes"] = len(nearby)

    if not nearby.empty:
        pop_values, pop_sources = _coalesce_numeric_with_source(nearby, _POP_RAIO_COLUMNS)
        renda_values, renda_sources = _coalesce_numeric_with_source(nearby, _RENDA_RAIO_COLUMNS)
        nearby["pop_total_raio_hex"] = pop_values
        nearby["fonte_pop_total_raio_hex"] = pop_sources
        nearby["renda_per_capita_raio_hex"] = renda_values
        nearby["fonte_renda_per_capita_raio_hex"] = renda_sources

        valid_pop = pop_values.notna()
        valid_renda = renda_values.notna()
        result["n_hexes_com_pop"] = int(valid_pop.sum())
        result["n_hexes_com_renda"] = int(valid_renda.sum())
        if valid_pop.any():
            result["pop_total_raio"] = float(pop_values[valid_pop].sum())
            result["fonte_pop_total_raio"] = _summarize_sources(pop_sources[valid_pop])

        weighted_mask = valid_renda & pop_values.gt(0).fillna(False)
        if weighted_mask.any():
            weights = pop_values[weighted_mask]
            result["renda_per_capita_media_raio"] = round(
                float(np.average(renda_values[weighted_mask], weights=weights)),
                2,
            )
            result["metodo_renda_raio"] = "ponderada_populacao"
        elif valid_renda.any():
            result["renda_per_capita_media_raio"] = round(float(renda_values[valid_renda].mean()), 2)
            result["metodo_renda_raio"] = "media_simples"

        if "oferta_efetiva_disponivel" in nearby.columns:
            result["residual_total"] = float(pd.to_numeric(nearby["oferta_efetiva_disponivel"], errors="coerce").sum())
        if "oferta_consumida_mercado_estimada" in nearby.columns:
            s = pd.to_numeric(nearby["oferta_consumida_mercado_estimada"], errors="coerce").dropna()
            if not s.empty:
                result["consumo_concorrentes_raio"] = float(s.sum())
        if "oferta_consumida_ultra_real" in nearby.columns:
            s = pd.to_numeric(nearby["oferta_consumida_ultra_real"], errors="coerce").dropna()
            if not s.empty:
                result["consumo_ultra_raio"] = float(s.sum())

        for col, key_med, key_max in [
            ("score_oportunidade_residual", "score_residual_medio", "score_residual_max"),
            ("score_priorizacao", "score_m1_medio", "score_m1_max"),
            ("score_expansao_hibrido", "score_hibrido_medio", "score_hibrido_max"),
        ]:
            if col in nearby.columns:
                s = pd.to_numeric(nearby[col], errors="coerce").dropna()
                if not s.empty:
                    result[key_med] = round(float(s.mean()), 2)
                    result[key_max] = round(float(s.max()), 2)

        sort_cols = ["dist_km"]
        sort_asc = [True]
        if "score_oportunidade_residual" in nearby.columns:
            sort_cols.append("score_oportunidade_residual")
            sort_asc.append(False)
        nearby = nearby.sort_values(sort_cols, ascending=sort_asc, kind="stable").reset_index(drop=True)
        result["hexes_entorno"] = nearby

    result["n_concorrentes"] = _count_in_radius(competitors_df)
    result["n_ultra"] = _count_in_radius(ultra_df)
    result["n_ancoras_dominio"] = _count_in_radius(dominio_df)
    return result


# ── Multi-hex scenario aggregator ──────────────────────────────────────────

_POP_MULTIHEX_COLUMNS: tuple[tuple[str, str], ...] = (
    ("pop_total_setor_2022", "setor_2022"),
    ("populacao_proxy", "populacao_proxy"),
)


def agregar_cenario_multihex(
    df: pd.DataFrame,
    hex_ids: list[str],
) -> dict:
    """Agrega KPIs de uma lista de hex_ids para cenario multi-hex.

    Funcao pura — nao muta df. Fallback de populacao: pop_total_setor_2022 > populacao_proxy.
    Retorna dict com metricas agregadas e 'hexes_selecionados' (DataFrame dos hexes filtrados).
    hex_ids ausentes no df sao registrados em 'hex_ids_ausentes'.
    """
    result: dict = {
        "qtd_hexes": 0,
        "hex_ids_existentes": [],
        "hex_ids_ausentes": [],
        "pop_total": None,
        "renda_per_capita_media": None,
        "metodo_renda": "ausente",
        "residual_total": None,
        "sam_fitness_total": None,
        "consumo_concorrentes_total": None,
        "consumo_ultra_total": None,
        "consumo_total_instalado": None,
        "n_concorrentes_total": None,
        "n_unidades_ultra": None,
        "presenca_ultra": False,
        "score_m1_medio": None,
        "score_m1_max": None,
        "score_censo_medio": None,
        "score_censo_max": None,
        "score_residual_medio": None,
        "score_residual_max": None,
        "score_hibrido_medio": None,
        "score_hibrido_max": None,
        "score_dominio_hibrido_medio": None,
        "score_dominio_hibrido_max": None,
        "hexes_selecionados": pd.DataFrame(),
    }

    if not hex_ids or df is None or df.empty:
        return result

    mask = df["hex_id"].isin(hex_ids)
    selecionados = df.loc[mask].copy()

    presentes = set(selecionados["hex_id"].tolist())
    result["hex_ids_existentes"] = [h for h in hex_ids if h in presentes]
    result["hex_ids_ausentes"] = [h for h in hex_ids if h not in presentes]
    result["qtd_hexes"] = len(selecionados)

    if selecionados.empty:
        return result

    # --- Populacao ---
    pop_values, _ = _coalesce_numeric_with_source(selecionados, _POP_MULTIHEX_COLUMNS)
    valid_pop = pop_values.notna()
    if valid_pop.any():
        result["pop_total"] = float(pop_values[valid_pop].sum())

    # --- Renda media ponderada por populacao ---
    renda_values, _ = _coalesce_numeric_with_source(selecionados, _RENDA_RAIO_COLUMNS)
    valid_renda = renda_values.notna()
    weighted_mask = valid_renda & pop_values.gt(0).fillna(False)
    if weighted_mask.any():
        result["renda_per_capita_media"] = round(
            float(np.average(renda_values[weighted_mask], weights=pop_values[weighted_mask])), 2
        )
        result["metodo_renda"] = "ponderada_populacao"
    elif valid_renda.any():
        result["renda_per_capita_media"] = round(float(renda_values[valid_renda].mean()), 2)
        result["metodo_renda"] = "media_simples"

    # --- Fitness e residual ---
    def _soma(col: str) -> float | None:
        if col not in selecionados.columns:
            return None
        s = pd.to_numeric(selecionados[col], errors="coerce").dropna()
        return float(s.sum()) if not s.empty else None

    result["residual_total"] = _soma("oferta_efetiva_disponivel")
    result["sam_fitness_total"] = _soma("sam_fitness_potencial")
    result["consumo_concorrentes_total"] = _soma("oferta_consumida_mercado_estimada")
    result["consumo_ultra_total"] = _soma("oferta_consumida_ultra_real")

    c = result["consumo_concorrentes_total"]
    u = result["consumo_ultra_total"]
    if c is not None or u is not None:
        result["consumo_total_instalado"] = (c or 0.0) + (u or 0.0)

    result["n_concorrentes_total"] = _soma("n_concorrentes_hex")
    n_ultra = _soma("n_unidades_ultra_performance_hex")
    result["n_unidades_ultra"] = n_ultra
    result["presenca_ultra"] = n_ultra is not None and n_ultra > 0

    # --- Scores (media ponderada por populacao e maximo) ---
    def _score_stats(col: str) -> tuple[float | None, float | None]:
        if col not in selecionados.columns:
            return None, None
        s = pd.to_numeric(selecionados[col], errors="coerce")
        valid = s.notna()
        if not valid.any():
            return None, None
        s_v = s[valid]
        w = pop_values[valid].fillna(0)
        med = (
            round(float(np.average(s_v, weights=w)), 2)
            if w.sum() > 0
            else round(float(s_v.mean()), 2)
        )
        return med, round(float(s_v.max()), 2)

    result["score_m1_medio"], result["score_m1_max"] = _score_stats("score_priorizacao")
    result["score_censo_medio"], result["score_censo_max"] = _score_stats("score_setor_2022_calibrado")
    result["score_residual_medio"], result["score_residual_max"] = _score_stats("score_oportunidade_residual")
    result["score_hibrido_medio"], result["score_hibrido_max"] = _score_stats("score_expansao_hibrido")

    # Dominio hibrido: clip(0.60 * censo + 0.40 * residual, 0, 100) com fallback por componente
    censo_s = (
        pd.to_numeric(selecionados["score_setor_2022_calibrado"], errors="coerce")
        if "score_setor_2022_calibrado" in selecionados.columns
        else pd.Series(np.nan, index=selecionados.index)
    )
    residual_s = (
        pd.to_numeric(selecionados["score_oportunidade_residual"], errors="coerce")
        if "score_oportunidade_residual" in selecionados.columns
        else pd.Series(np.nan, index=selecionados.index)
    )
    both = censo_s.notna() & residual_s.notna()
    only_c = censo_s.notna() & residual_s.isna()
    only_r = censo_s.isna() & residual_s.notna()
    dominio_s = pd.Series(np.nan, index=selecionados.index, dtype="float64")
    if both.any():
        dominio_s[both] = (0.60 * censo_s[both] + 0.40 * residual_s[both]).clip(0, 100)
    if only_c.any():
        dominio_s[only_c] = censo_s[only_c].clip(0, 100)
    if only_r.any():
        dominio_s[only_r] = residual_s[only_r].clip(0, 100)
    valid_d = dominio_s.notna()
    if valid_d.any():
        d_v = dominio_s[valid_d]
        w_d = pop_values[valid_d].fillna(0)
        med_d = (
            round(float(np.average(d_v, weights=w_d)), 2)
            if w_d.sum() > 0
            else round(float(d_v.mean()), 2)
        )
        result["score_dominio_hibrido_medio"] = med_d
        result["score_dominio_hibrido_max"] = round(float(d_v.max()), 2)

    result["hexes_selecionados"] = selecionados.reset_index(drop=True)
    return result


def parse_hex_ids_from_text(text: str) -> list[str]:
    """Parse hex_ids from text, accepting newline, comma, semicolon or space as separators."""
    if not text or not text.strip():
        return []
    tokens = re.split(r'[\s,;]+', text.strip())
    return [t for t in tokens if t]


def lookup_hex_by_coord(
    lat: float,
    lng: float,
    df: pd.DataFrame,
    h3_res: int = 7,
) -> dict | None:
    """Convert ``lat/lng`` to H3 ``hex_id`` at ``h3_res`` and look up in ``df``.

    Returns a dict with the matching row (plus ``_searched_lat``, ``_searched_lng``,
    ``_not_found=False``). If the hex is not in ``df``, returns the dict with
    ``_not_found=True``. Returns ``None`` only on H3 conversion failure.
    """
    try:
        import h3 as h3lib
        hex_id = h3lib.latlng_to_cell(lat, lng, h3_res)
    except Exception:
        return None
    matches = df.loc[df["hex_id"] == hex_id]
    meta = {"_searched_lat": lat, "_searched_lng": lng}
    if matches.empty:
        return {"hex_id": hex_id, "_not_found": True, **meta}
    row = matches.iloc[0].to_dict()
    row.update({**meta, "_not_found": False})
    return row
