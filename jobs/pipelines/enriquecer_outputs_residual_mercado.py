"""
Bloco 7 - Propagacao de TAM/SAM e oferta residual para outputs.

Enriquece os parquets acionaveis a partir de
data/staging/hexagonos_mercado_mapeado.parquet sem recalcular ou alterar
score_priorizacao, ranks oficiais do M1 ou artefatos oficiais do M1.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from jobs.pipelines.gerar_carteira_acionavel import (  # noqa: E402
    MERCADO_PATH,
    RESIDUAL_MERCADO_COLS,
    carregar_colunas_residual_mercado,
)

HIBRIDO_PATH = ROOT / "data" / "outputs" / "oportunidades_expansao_hibrido.parquet"
CARTEIRA_PATH = ROOT / "data" / "outputs" / "carteira_expansao_acionavel.parquet"
PLANO_PATH = ROOT / "data" / "outputs" / "plano_expansao_curto_prazo.parquet"

OUTPUT_TARGETS = [HIBRIDO_PATH, CARTEIRA_PATH, PLANO_PATH]
REQUIRED_RESIDUAL_COLS = {
    "sam_fitness_potencial",
    "oferta_efetiva_disponivel",
    "score_oportunidade_residual",
    "share_ultra_estimado_hex",
    "oferta_consumida_mercado_estimada",
    "oferta_consumida_ultra_real",
}


def enriquecer_dataframe_com_residual(
    df: pd.DataFrame,
    mercado_residual: pd.DataFrame,
) -> pd.DataFrame:
    if "hex_id" not in df.columns:
        raise AssertionError("Output sem hex_id para join de residual.")
    if "hex_id" not in mercado_residual.columns:
        raise AssertionError("Mercado residual sem hex_id para join.")

    cols_residual = [
        column
        for column in RESIDUAL_MERCADO_COLS
        if column in mercado_residual.columns
    ]
    base = df.drop(columns=[column for column in cols_residual if column in df.columns]).copy()

    score_original = (
        pd.to_numeric(df["score_priorizacao"], errors="coerce").reset_index(drop=True)
        if "score_priorizacao" in df.columns
        else None
    )
    ranks_originais = {
        column: pd.to_numeric(df[column], errors="coerce").reset_index(drop=True)
        for column in ["rank_brasil", "rank_uf", "rank_carteira_brasil", "rank_carteira_uf"]
        if column in df.columns
    }

    enriched = base.merge(
        mercado_residual[["hex_id", *cols_residual]],
        on="hex_id",
        how="left",
        validate="many_to_one",
    )
    assert len(enriched) == len(df), "Join de residual alterou cardinalidade."

    if score_original is not None:
        score_atual = pd.to_numeric(enriched["score_priorizacao"], errors="coerce").reset_index(drop=True)
        assert score_original.equals(score_atual), "score_priorizacao foi alterado."

    for column, original in ranks_originais.items():
        atual = pd.to_numeric(enriched[column], errors="coerce").reset_index(drop=True)
        assert original.equals(atual), f"{column} foi alterado."

    faltam = REQUIRED_RESIDUAL_COLS - set(enriched.columns)
    assert not faltam, f"Colunas residuais faltando apos join: {sorted(faltam)}"
    return enriched


def enriquecer_parquet(
    target_path: Path,
    mercado_residual: pd.DataFrame,
) -> pd.DataFrame:
    if not target_path.exists():
        raise FileNotFoundError(f"Output nao encontrado: {target_path}")

    df = pd.read_parquet(target_path)
    enriched = enriquecer_dataframe_com_residual(df, mercado_residual)
    enriched.to_parquet(target_path, index=False)
    return enriched


def main() -> None:
    print("Bloco 7 - Propagando oferta residual para outputs")
    print("=" * 58)

    mercado_residual = carregar_colunas_residual_mercado(MERCADO_PATH)
    if mercado_residual.empty:
        raise RuntimeError(f"Sem colunas residuais disponiveis em {MERCADO_PATH}")

    faltam = REQUIRED_RESIDUAL_COLS - set(mercado_residual.columns)
    if faltam:
        raise AssertionError(f"Mercado residual incompleto: {sorted(faltam)}")

    for target_path in OUTPUT_TARGETS:
        print(f"\nEnriquecendo: {target_path}")
        enriched = enriquecer_parquet(target_path, mercado_residual)
        cobertura = enriched["oferta_efetiva_disponivel"].notna().mean() * 100.0
        print(
            f"  {len(enriched):,} linhas | "
            f"{enriched.shape[1]} colunas | "
            f"cobertura residual={cobertura:.1f}%"
        )

    print("\nBloco 7 - propagacao concluida.")


if __name__ == "__main__":
    main()
