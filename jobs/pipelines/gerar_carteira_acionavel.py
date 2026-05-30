"""
Gera a carteira acionavel de expansao da Ultra Academia.

Input:  data/outputs/oportunidades_expansao_hibrido.parquet
Output: data/outputs/carteira_expansao_acionavel.parquet
        data/outputs/carteira_expansao_acionavel.csv

Regras:
- Somente municipios com top_municipio=True entram na carteira
- Se o municipio tiver hex granular elegivel (top_hex_intraurbano=True), usar apenas esses hexes
- Se o municipio nao tiver hex granular elegivel, aplicar fallback municipal/M1
- Top 5 hexes por municipio
- Prioridade Alta: rank_municipio_uf <= 5 OU rank_municipio_brasil <= 50
- Prioridade Media: restante dos municipios top
- rank_carteira_brasil e rank_carteira_uf seguem a ordenacao oficial do M1
- motivo_priorizacao gerado como texto curto auditavel

Restricoes:
- NAO altera M1 (score_priorizacao)
- NAO altera pipeline oficial
- NAO recalcula scores
- Usa apenas outputs ja existentes
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT / "data" / "outputs" / "oportunidades_expansao_hibrido.parquet"
MERCADO_PATH = ROOT / "data" / "staging" / "hexagonos_mercado_mapeado.parquet"
OUTPUT_PARQUET = ROOT / "data" / "outputs" / "carteira_expansao_acionavel.parquet"
OUTPUT_CSV = ROOT / "data" / "outputs" / "carteira_expansao_acionavel.csv"

TOP_N_HEX_POR_MUNICIPIO = 5
PRIORIDADE_ALTA_RANK_UF = 5
PRIORIDADE_ALTA_RANK_BRASIL = 50

RESIDUAL_MERCADO_COLS = [
    "pop_hex_base",
    "fonte_pop_hex_base",
    "tam_populacao_hex",
    "tam_fitness_potencial",
    "flag_sam_fitness",
    "sam_fitness_potencial",
    "capacidade_default_concorrente_alunos",
    "oferta_consumida_mercado_estimada",
    "oferta_consumida_ultra_real",
    "n_unidades_ultra_performance_hex",
    "oferta_efetiva_disponivel",
    "penetracao_fitness_mercado_estimada",
    "share_ultra_estimado_hex",
    "score_oportunidade_residual",
    "quartil_oportunidade_residual",
    "prioridade_mercado_mapeado",
    "tese_entrada",
]

LOAD_COLS = [
    "hex_id",
    "uf",
    "cidade",
    "nome_municipio",
    "cod_municipio",
    "score_priorizacao",
    "hex_score_estrutural",
    "score_setor_2022_calibrado",
    "score_expansao_hibrido",
    "densidade_pop_setor_hab_km2",
    "rank_brasil",
    "rank_uf",
    "rank_cidade",
    "rank_municipio_uf",
    "rank_municipio_brasil",
    "rank_hex_intraurbano",
    "rank_hibrido_brasil",
    "rank_hibrido_uf",
    "top_municipio",
    "top_hex_intraurbano",
    "flag_hex_hibrido_elegivel",
    "flag_viavel",
    "flag_prioridade",
    "flag_outlier_espacial",
    "flag_baixa_pop_setor",
    "flag_join_uf_restrito",
    "flag_monitoramento_prioritario",
    "coverage_pct_setor_2022",
    "qualidade_join_uf",
    "faixa_oportunidade",
    "score_priorizacao_municipio",
    "total_hex_municipio",
    "total_hex_censo_elegivel",
    "top_oportunidade_brasil",
    "top_oportunidade_uf",
    "top_oportunidade_municipio",
    "fonte_camada_censitaria",
    "causa_outlier_espacial",
    "criterio_score_expansao_hibrido",
    "camada_modelo_hibrido",
    *RESIDUAL_MERCADO_COLS,
]

NUMERIC_COLUMNS = [
    "score_priorizacao",
    "score_priorizacao_municipio",
    "score_setor_2022_calibrado",
    "score_expansao_hibrido",
    "densidade_pop_setor_hab_km2",
    "rank_brasil",
    "rank_uf",
    "rank_municipio_uf",
    "rank_municipio_brasil",
    "rank_hex_intraurbano",
    "pop_hex_base",
    "tam_populacao_hex",
    "tam_fitness_potencial",
    "sam_fitness_potencial",
    "capacidade_default_concorrente_alunos",
    "oferta_consumida_mercado_estimada",
    "oferta_consumida_ultra_real",
    "n_unidades_ultra_performance_hex",
    "oferta_efetiva_disponivel",
    "penetracao_fitness_mercado_estimada",
    "share_ultra_estimado_hex",
    "score_oportunidade_residual",
]

BOOL_COLUMNS = [
    "top_municipio",
    "top_hex_intraurbano",
    "flag_hex_hibrido_elegivel",
    "flag_outlier_espacial",
    "flag_baixa_pop_setor",
    "flag_join_uf_restrito",
    "flag_sam_fitness",
]


def _safe_int(value: object, default: int = 0) -> int:
    if pd.isna(value):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value: object) -> float | None:
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _adicionar_quartil_residual(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "oferta_efetiva_disponivel" not in out.columns:
        return out

    oferta = pd.to_numeric(out["oferta_efetiva_disponivel"], errors="coerce")
    out["quartil_oportunidade_residual"] = "sem_residual"
    elegivel = oferta.notna() & oferta.gt(0)
    if not elegivel.any():
        return out

    if int(elegivel.sum()) < 4:
        out.loc[elegivel, "quartil_oportunidade_residual"] = "Q4_maior_residual"
        return out

    labels = ["Q1_menor_residual", "Q2", "Q3", "Q4_maior_residual"]
    quartis = pd.qcut(oferta.loc[elegivel].rank(method="first"), q=4, labels=labels)
    out.loc[elegivel, "quartil_oportunidade_residual"] = quartis.astype(str)
    return out


def carregar_colunas_residual_mercado(
    mercado_path: Path = MERCADO_PATH,
) -> pd.DataFrame:
    if not mercado_path.exists():
        return pd.DataFrame()

    available = set(pq.read_schema(mercado_path).names)
    cols = ["hex_id"] + [
        column
        for column in RESIDUAL_MERCADO_COLS
        if column in available and column != "quartil_oportunidade_residual"
    ]
    if len(cols) == 1:
        return pd.DataFrame()

    mercado = pd.read_parquet(mercado_path, columns=cols)
    if mercado["hex_id"].duplicated().any():
        n_dup = int(mercado["hex_id"].duplicated().sum())
        raise AssertionError(f"Mercado residual com hex_id duplicado: {n_dup}")

    return _adicionar_quartil_residual(mercado)


def anexar_colunas_residual_mercado(
    df: pd.DataFrame,
    mercado_path: Path = MERCADO_PATH,
) -> pd.DataFrame:
    mercado = carregar_colunas_residual_mercado(mercado_path)
    if mercado.empty:
        return df.copy()

    merge_cols = [column for column in mercado.columns if column != "hex_id"]
    base = df.drop(columns=[column for column in merge_cols if column in df.columns]).copy()
    merged = base.merge(mercado, on="hex_id", how="left", validate="many_to_one")
    assert len(merged) == len(df), "Join de residual alterou cardinalidade"

    if "score_priorizacao" in df.columns:
        original = pd.to_numeric(df["score_priorizacao"], errors="coerce").reset_index(drop=True)
        atual = pd.to_numeric(merged["score_priorizacao"], errors="coerce").reset_index(drop=True)
        assert original.equals(atual), "score_priorizacao foi alterado ao anexar residual"

    return merged


def _resolve_municipio_keys(df: pd.DataFrame) -> list[str]:
    preferred = ["uf", "cod_municipio"]
    if all(column in df.columns for column in preferred):
        return preferred

    fallback = ["uf", "nome_municipio"]
    if all(column in df.columns for column in fallback):
        return fallback

    raise ValueError("Input sem chaves suficientes para agrupar municipio na carteira.")


def _motivo_priorizacao(row: pd.Series) -> str:
    """Gera texto curto de motivo para uso executivo."""
    parts: list[str] = []

    rank_uf = _safe_int(row.get("rank_municipio_uf", 0))
    rank_br = _safe_int(row.get("rank_municipio_brasil", 0))
    score_m1 = _safe_float(row.get("score_priorizacao_municipio", row.get("score_priorizacao", 0))) or 0.0
    score_censo = _safe_float(row.get("score_setor_2022_calibrado"))
    qualidade = str(row.get("qualidade_join_uf", "A") or "A")
    uf = str(row.get("uf", "") or "")
    modo = str(row.get("modo_selecao_carteira", "") or "")

    if rank_br <= 50:
        parts.append(f"Top {rank_br} nacional")
    if rank_uf <= 5:
        parts.append(f"Top {rank_uf} na {uf}")

    if score_m1 >= 95:
        parts.append("Score M1 maximo")
    elif score_m1 >= 80:
        parts.append(f"Score M1 alto ({score_m1:.0f})")
    else:
        parts.append(f"Score M1 {score_m1:.0f}")

    if score_censo is None:
        if modo == "fallback_municipal_m1":
            parts.append("Fallback municipal/M1")
        else:
            parts.append("Score intraurbano n/d")
    elif score_censo >= 80:
        parts.append(f"Score intraurbano excepcional ({score_censo:.0f})")
    elif score_censo >= 60:
        parts.append(f"Score intraurbano alto ({score_censo:.0f})")
    else:
        parts.append(f"Score intraurbano {score_censo:.0f}")

    if qualidade == "A":
        parts.append("Join A")
    elif qualidade == "B":
        parts.append("Join B (aceitavel)")
    elif qualidade == "C":
        parts.append("Join C (fallback)")

    if bool(row.get("flag_outlier_espacial", False)):
        parts.append("outlier espacial explicado")
    if bool(row.get("flag_baixa_pop_setor", False)):
        parts.append("densidade abaixo do piso")

    return " | ".join(parts)


def _prioridade_abertura(rank_municipio_uf: float, rank_municipio_brasil: float) -> str:
    uf_val = int(rank_municipio_uf) if not math.isnan(float(rank_municipio_uf)) else 9999
    br_val = int(rank_municipio_brasil) if not math.isnan(float(rank_municipio_brasil)) else 9999
    if uf_val <= PRIORIDADE_ALTA_RANK_UF or br_val <= PRIORIDADE_ALTA_RANK_BRASIL:
        return "Alta"
    return "Media"


def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    coerced = df.copy()
    for column in NUMERIC_COLUMNS:
        if column in coerced.columns:
            coerced[column] = pd.to_numeric(coerced[column], errors="coerce")
    for column in BOOL_COLUMNS:
        if column in coerced.columns:
            coerced[column] = coerced[column].fillna(False).astype(bool)
    return coerced


def _selecionar_base_carteira(df: pd.DataFrame) -> pd.DataFrame:
    municipio_keys = _resolve_municipio_keys(df)
    base = _coerce_types(df[df["top_municipio"].eq(True)].copy())  # invariante a `== True`; evita E712
    print(f"[carteira] Apos filtro top_municipio=True: {len(base):,} linhas")

    if base.empty:
        raise ValueError("Nenhuma linha passou em top_municipio=True. Verifique o input.")

    base["_municipio_tem_hex_granular"] = (
        base.groupby(municipio_keys, dropna=False)["top_hex_intraurbano"]
        .transform("any")
        .astype(bool)
    )

    granular = base[
        base["_municipio_tem_hex_granular"] & base["top_hex_intraurbano"]
    ].copy()
    granular["modo_selecao_carteira"] = "granular_censitario"
    if not granular.empty:
        granular = granular.sort_values(
            municipio_keys
            + [
                "rank_hex_intraurbano",
                "score_setor_2022_calibrado",
                "score_expansao_hibrido",
                "rank_brasil",
                "hex_id",
            ],
            ascending=[True, True, True, False, False, True, True],
            kind="stable",
        )

    fallback = base[~base["_municipio_tem_hex_granular"]].copy()
    fallback["modo_selecao_carteira"] = "fallback_municipal_m1"
    if not fallback.empty:
        fallback = fallback.sort_values(
            municipio_keys + ["rank_brasil", "rank_uf", "score_priorizacao", "hex_id"],
            ascending=[True, True, True, True, False, True],
            kind="stable",
        )

    candidatos = pd.concat([granular, fallback], ignore_index=True)
    n_municipios_granular = granular[municipio_keys].drop_duplicates().shape[0]
    n_municipios_fallback = fallback[municipio_keys].drop_duplicates().shape[0]
    print(f"[carteira] Municipios com selecao granular: {n_municipios_granular:,}")
    print(f"[carteira] Municipios em fallback municipal/M1: {n_municipios_fallback:,}")

    carteira = (
        candidatos.groupby(municipio_keys, sort=False, dropna=False)
        .head(TOP_N_HEX_POR_MUNICIPIO)
        .reset_index(drop=True)
    )
    return carteira


def gerar_carteira() -> pd.DataFrame:
    print(f"[carteira] Lendo: {INPUT_PATH}")
    all_cols = pq.read_schema(INPUT_PATH).names
    load_cols = [column for column in LOAD_COLS if column in all_cols]

    df = pd.read_parquet(INPUT_PATH, columns=load_cols)
    print(f"[carteira] Total de linhas no input: {len(df):,}")
    df = anexar_colunas_residual_mercado(df, MERCADO_PATH)
    if "oferta_efetiva_disponivel" in df.columns:
        total_residual = pd.to_numeric(df["oferta_efetiva_disponivel"], errors="coerce").fillna(0.0).sum()
        print(f"[carteira] Oferta residual disponivel no input: {total_residual:,.0f}")

    carteira = _selecionar_base_carteira(df)
    print(f"[carteira] UFs cobertas: {sorted(carteira['uf'].dropna().unique())}")
    if "cod_municipio" in carteira.columns:
        print(f"[carteira] Municipios: {carteira['cod_municipio'].nunique():,}")
    print(f"[carteira] Apos top {TOP_N_HEX_POR_MUNICIPIO} por municipio: {len(carteira):,} linhas")

    carteira["prioridade_abertura"] = carteira.apply(
        lambda row: _prioridade_abertura(
            row.get("rank_municipio_uf", 9999) or 9999,
            row.get("rank_municipio_brasil", 9999) or 9999,
        ),
        axis=1,
    )
    carteira["motivo_priorizacao"] = carteira.apply(_motivo_priorizacao, axis=1)

    carteira = carteira.sort_values(
        [
            "rank_brasil",
            "rank_uf",
            "score_priorizacao",
            "rank_hex_intraurbano",
            "score_setor_2022_calibrado",
            "hex_id",
        ],
        ascending=[True, True, False, True, False, True],
        kind="stable",
    ).reset_index(drop=True)
    carteira["rank_carteira_brasil"] = range(1, len(carteira) + 1)
    carteira["rank_carteira_uf"] = carteira.groupby("uf", sort=False).cumcount() + 1

    n_total = len(carteira)
    n_fora_top_mun = int((carteira["top_municipio"].ne(True)).sum())  # invariante a `!= True`; evita E712
    n_granular_invalido = int(
        (
            (carteira["modo_selecao_carteira"] == "granular_censitario")
            & (carteira["top_hex_intraurbano"].ne(True))  # invariante a `!= True`; evita E712
        ).sum()
    )
    n_dup = int(carteira["hex_id"].duplicated().sum())

    print(f"[carteira] Oportunidades geradas: {n_total:,}")
    print(f"[carteira] Fora do top_municipio:  {n_fora_top_mun} (deve ser 0)")
    print(f"[carteira] Granular invalido:      {n_granular_invalido} (deve ser 0)")
    print(f"[carteira] Hex duplicados:          {n_dup} (deve ser 0)")
    print(
        "[carteira] Modos de selecao: "
        + str(carteira["modo_selecao_carteira"].value_counts(dropna=False).to_dict())
    )

    if n_fora_top_mun > 0 or n_granular_invalido > 0 or n_dup > 0:
        raise AssertionError("Carteira falhou em validacoes de integridade.")

    print(f"[carteira] Prioridade Alta: {(carteira['prioridade_abertura'] == 'Alta').sum():,} linhas")
    print(f"[carteira] Prioridade Media: {(carteira['prioridade_abertura'] == 'Media').sum():,} linhas")
    if "cod_municipio" in carteira.columns:
        print(f"[carteira] Municipios com cobertura: {carteira.groupby('cod_municipio').ngroups:,}")

    return carteira


def salvar_carteira(carteira: pd.DataFrame) -> None:
    OUTPUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)

    carteira.to_parquet(OUTPUT_PARQUET, index=False)
    print(f"[carteira] Salvo em: {OUTPUT_PARQUET}")

    csv_cols_preferencia = [
        "rank_carteira_brasil",
        "rank_carteira_uf",
        "prioridade_abertura",
        "uf",
        "nome_municipio",
        "hex_id",
        "modo_selecao_carteira",
        "score_expansao_hibrido",
        "score_setor_2022_calibrado",
        "densidade_pop_setor_hab_km2",
        "sam_fitness_potencial",
        "oferta_efetiva_disponivel",
        "score_oportunidade_residual",
        "quartil_oportunidade_residual",
        "share_ultra_estimado_hex",
        "oferta_consumida_mercado_estimada",
        "oferta_consumida_ultra_real",
        "score_priorizacao_municipio",
        "rank_municipio_uf",
        "rank_municipio_brasil",
        "rank_hex_intraurbano",
        "motivo_priorizacao",
        "qualidade_join_uf",
        "coverage_pct_setor_2022",
        "flag_outlier_espacial",
        "flag_baixa_pop_setor",
        "flag_join_uf_restrito",
    ]
    csv_cols = [column for column in csv_cols_preferencia if column in carteira.columns]
    remaining = [column for column in carteira.columns if column not in csv_cols]
    carteira[csv_cols + remaining].to_csv(
        OUTPUT_CSV, index=False, sep=";", encoding="utf-8-sig"
    )
    print(f"[carteira] CSV salvo em: {OUTPUT_CSV}")


def main() -> None:
    carteira = gerar_carteira()
    salvar_carteira(carteira)
    print("\n[carteira] Carteira acionavel gerada com sucesso.")


if __name__ == "__main__":
    main()
