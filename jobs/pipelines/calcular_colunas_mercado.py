"""
Bloco 4 - Calculo das colunas de mercado.

Adiciona colunas de auditoria, TAM, SAM, residual, SOM e classificacoes
executivas ao parquet enriquecido do Bloco 3.

Nao altera nenhum artefato oficial do M1.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MERCADO_PATH = ROOT / "data" / "staging" / "hexagonos_mercado_mapeado.parquet"
CENSO_PATH = ROOT / "data" / "staging" / "censo2022_setores_calibrado.parquet"
OUT_PATH = ROOT / "data" / "staging" / "hexagonos_mercado_mapeado.parquet"

CENSO_COLS = ["hex_id", "pop_total_setor_2022", "renda_per_capita_setor_2022_calibrada"]
HYBRID_TIEBREAK_MAX_SCORE = 100.001
SOURCE_REQUIRED_COLS = {
    "hex_id",
    "flag_censo_elegivel",
    "populacao_proxy",
    "renda_per_capita",
    "score_priorizacao",
    "flag_hex_hibrido_elegivel",
    "score_expansao_hibrido",
    "flag_viavel",
    "top_municipio",
    "flag_white_space_2km",
    "flag_canibalizacao_ultra_1km",
    "gap_competitivo_2km",
    "pressao_concorrencial_score_2km",
}


def anexar_colunas_censo(df: pd.DataFrame) -> pd.DataFrame:
    """Atualiza as colunas censitarias necessarias sem criar duplicatas.

    O input do Bloco 3 ja herda a camada censitaria completa do hibrido
    (core + expandida + nacional). A leitura do parquet core aqui deve apenas
    preencher lacunas legadas, sem apagar dados censitarios ja materializados.
    """
    legacy_cols = {
        f"{col}_{suffix}"
        for col in CENSO_COLS[1:]
        for suffix in ("x", "y")
    }
    cols_para_remover = [col for col in sorted(legacy_cols) if col in df.columns]
    if cols_para_remover:
        df = df.drop(columns=cols_para_remover)

    censo = pd.read_parquet(CENSO_PATH, columns=CENSO_COLS)
    if censo["hex_id"].duplicated().any():
        n_dup = int(censo["hex_id"].duplicated().sum())
        raise AssertionError(f"censo2022_setores_calibrado com hex_id duplicado: {n_dup}")

    censo = censo.rename(columns={col: f"{col}_core" for col in CENSO_COLS[1:]})
    merged = df.merge(censo, on="hex_id", how="left")
    for col in CENSO_COLS[1:]:
        core_col = f"{col}_core"
        if col in merged.columns:
            merged[col] = merged[col].where(merged[col].notna(), merged[core_col])
        else:
            merged[col] = merged[core_col]
    return merged.drop(columns=[f"{col}_core" for col in CENSO_COLS[1:]])


def validar_entradas(df: pd.DataFrame) -> None:
    faltam = SOURCE_REQUIRED_COLS - set(df.columns)
    assert not faltam, f"Colunas base faltando antes do Bloco 4: {faltam}"


def calcular(df: pd.DataFrame) -> pd.DataFrame:
    """Materializa colunas de mercado sobre o DataFrame ja enriquecido."""
    n = len(df)

    # 5.1 - Auditoria
    df["data_snapshot_mercado"] = str(date.today())
    df["fonte_oferta_principal"] = "csv_big_players_mapeados"
    df["n_redes_mapeadas"] = 3

    # Granularidade da demanda
    mask_hex_censo = (
        df["flag_censo_elegivel"].fillna(False).astype(bool)
        & df["pop_total_setor_2022"].notna()
    )
    df["demanda_granularidade"] = np.where(mask_hex_censo, "hex_censo", "municipio_proxy")
    df["fonte_demanda_principal"] = np.where(mask_hex_censo, "censo_2022_hex", "m1_municipal_proxy")

    # 5.2 - TAM
    df["tam_populacao_base"] = np.where(
        mask_hex_censo, df["pop_total_setor_2022"], df["populacao_proxy"]
    )

    renda_censo_ok = mask_hex_censo & df["renda_per_capita_setor_2022_calibrada"].notna()
    df["tam_renda_base"] = np.where(
        renda_censo_ok,
        df["renda_per_capita_setor_2022_calibrada"],
        df["renda_per_capita"],
    )

    mask_hibrido = (
        df["flag_hex_hibrido_elegivel"].fillna(False).astype(bool)
        & df["score_expansao_hibrido"].notna()
    )
    df["tam_indice_demanda"] = np.where(
        mask_hibrido, df["score_expansao_hibrido"], df["score_priorizacao"]
    )
    df["tam_indice_demanda_norm"] = df["tam_indice_demanda"] / 100.0

    # Alterado em 2026-05-15: removida trava 18-45; população total via populacao_proxy.
    df["tam_pop_total_base"] = df["populacao_proxy"]

    # 5.4 - SAM
    flag_canibal = df["flag_canibalizacao_ultra_1km"].fillna(False).astype(bool)
    flag_viavel = df["flag_viavel"].fillna(False).astype(bool)
    flag_top_mun = df["top_municipio"].fillna(False).astype(bool)
    flag_white = df["flag_white_space_2km"].fillna(False).astype(bool)
    flag_hibrid_elig = df["flag_hex_hibrido_elegivel"].fillna(False).astype(bool)

    df["flag_sam"] = flag_viavel & flag_top_mun & ~flag_canibal
    flag_sam = df["flag_sam"].astype(bool)

    df["sam_indice_operavel"] = np.where(flag_sam, df["tam_indice_demanda"], 0.0)
    df["sam_populacao_base"] = np.where(flag_sam, df["tam_populacao_base"], 0.0)

    # Contrato literal: flag_hex_hibrido_elegivel tem precedencia
    df["sam_granularidade"] = np.select(
        [flag_hibrid_elig, flag_sam, flag_canibal],
        ["hex_censo", "municipio_priorizado", "bloqueado_rede_ultra"],
        default="fora_escopo_atual",
    )

    # 5.6 - Residual e SOM
    df["residual_indice_mapeado"] = df["tam_indice_demanda"] * df["gap_competitivo_2km"]
    df["residual_populacao_mapeada"] = np.where(
        mask_hex_censo,
        df["tam_populacao_base"] * df["gap_competitivo_2km"],
        np.nan,
    )
    df["capacidade_captura_mapeada"] = (df["sam_indice_operavel"] / 100.0) * df["gap_competitivo_2km"]
    df["som_indice_mapeado"] = 100.0 * df["capacidade_captura_mapeada"]
    df["som_populacao_mapeada"] = np.where(
        mask_hex_censo,
        df["sam_populacao_base"] * df["gap_competitivo_2km"],
        np.nan,
    )

    # 5.7 - Classificacoes executivas
    df["tese_entrada"] = np.select(
        [
            flag_canibal,
            flag_sam & flag_white,
            flag_sam & ~flag_white,
            flag_viavel & ~flag_top_mun,
        ],
        ["proteger_rede_atual", "abrir_agora", "abrir_com_disputa", "monitorar"],
        default="descartar",
    )

    som = df["som_indice_mapeado"].fillna(0.0)
    df["prioridade_mercado_mapeado"] = np.select(
        [som >= 75, som >= 50, som > 0],
        ["alta", "media", "baixa"],
        default="nula",
    )

    assert len(df) == n, "Cardinalidade alterada"
    return df


def validar(df: pd.DataFrame) -> None:
    print("\n=== Validacao Bloco 4 ===")

    required = {
        "data_snapshot_mercado", "fonte_demanda_principal", "fonte_oferta_principal",
        "n_redes_mapeadas", "demanda_granularidade",
        "tam_populacao_base", "tam_renda_base", "tam_indice_demanda",
        "tam_indice_demanda_norm", "tam_pop_total_base",
        "flag_sam", "sam_indice_operavel", "sam_populacao_base", "sam_granularidade",
        "residual_indice_mapeado", "residual_populacao_mapeada",
        "capacidade_captura_mapeada", "som_indice_mapeado", "som_populacao_mapeada",
        "tese_entrada", "prioridade_mercado_mapeado",
    }
    faltam = required - set(df.columns)
    assert not faltam, f"Colunas faltando: {faltam}"
    print("Schema OK")

    n_violacao = int(
        (df["flag_sam"] & df["flag_canibalizacao_ultra_1km"].fillna(False)).sum()
    )
    assert n_violacao == 0, f"flag_sam=True com canibalizacao: {n_violacao} casos"
    print("Regra canibalizacao OK")

    for col in ["tam_indice_demanda", "flag_sam", "tese_entrada", "prioridade_mercado_mapeado"]:
        n_nulos = df[col].isna().sum()
        assert n_nulos == 0, f"Nulos inesperados em {col}: {n_nulos}"
    print("Sem nulos em colunas criticas OK")

    td = df["tam_indice_demanda"].fillna(0.0)
    assert (td >= 0).all() and (td <= HYBRID_TIEBREAK_MAX_SCORE).all(), (
        f"tam_indice_demanda fora de [0, {HYBRID_TIEBREAK_MAX_SCORE}]"
    )
    som_vals = df["som_indice_mapeado"].fillna(0.0)
    assert (som_vals >= 0).all() and (som_vals <= HYBRID_TIEBREAK_MAX_SCORE).all(), (
        f"som_indice_mapeado fora de [0, {HYBRID_TIEBREAK_MAX_SCORE}]"
    )
    print("Faixas OK")

    print(f"\ntam_indice_demanda: min={df['tam_indice_demanda'].min():.1f}  "
          f"max={df['tam_indice_demanda'].max():.1f}  "
          f"mean={df['tam_indice_demanda'].mean():.1f}")
    print(f"flag_sam=True: {df['flag_sam'].sum():,} ({100*df['flag_sam'].mean():.1f}%)")
    print(f"\ntese_entrada:\n{df['tese_entrada'].value_counts().to_string()}")
    print(f"\nprioridade_mercado_mapeado:\n{df['prioridade_mercado_mapeado'].value_counts().to_string()}")
    print(f"\nsam_granularidade:\n{df['sam_granularidade'].value_counts().to_string()}")
    print(f"\ndemanda_granularidade:\n{df['demanda_granularidade'].value_counts().to_string()}")
    print("\nValidacao OK")


def main():
    print("Bloco 4 - Calculo das colunas de mercado")
    print("=" * 50)

    print("\n1. Carregando base enriquecida (Bloco 3)...")
    df = pd.read_parquet(MERCADO_PATH)
    n_orig = len(df)
    print(f"   {n_orig:,} linhas, {df.shape[1]} colunas")
    validar_entradas(df)

    print("\n2. Juntando colunas censitarias necessarias...")
    df = anexar_colunas_censo(df)
    assert len(df) == n_orig, "Join alterou cardinalidade"
    print(f"   censo: {pd.read_parquet(CENSO_PATH, columns=['hex_id']).shape[0]:,} hexes com dados")
    n_com_censo = int(df["pop_total_setor_2022"].notna().sum())
    print(f"   {n_com_censo:,} hexes com pop_total_setor_2022 apos join")

    print("\n3. Calculando colunas de mercado...")
    df = calcular(df)
    print(f"   {df.shape[1]} colunas totais")

    validar(df)

    print(f"\n4. Salvando em {OUT_PATH}...")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH, index=False)
    size_mb = OUT_PATH.stat().st_size / 1e6
    print(f"   Salvo: {size_mb:.1f} MB")
    print("\nBloco 4 concluido.")


if __name__ == "__main__":
    main()
