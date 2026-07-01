"""BLK-LTV-02 — Join territorial: pendurar retenção/LTV no hexágono da unidade.

Une a tabela-ponte geocodificada (unidade_hex.parquet, 88 linhas, BLK-LTV-01) com
as métricas de retenção agregadas do Lifetime (unidade_para_motor.parquet) e as
features territoriais do hexágono (hexagonos_mercado_mapeado.parquet).

Produz data/staging/unidade_territorio_retencao.parquet com exatamente 88 linhas.
As 32 unidades sem hex_id mantêm features territoriais = NaN (não descartadas).

READ-ONLY sobre o M1: ZERO importação de pipelines/m1, censo_*, dashboard, api.

CAVEAT ESTRUTURAL (confound de maturidade):
    unidade_para_motor.parquet não tem data de abertura por unidade
    (maturacao_status = 100% 'maturacao_indisponivel' — DEC-001/DEC-008).
    As métricas de retenção (PROB_CANCEL_90D_*, LTV_PROSPECTIVO_12M_*) refletem
    o snapshot atual de cada unidade, que pode estar em diferentes estágios de
    maturação. Sem controle de maturidade, a comparação territorial de LTV
    confunde efeito de localização com efeito de tempo de operação. Este confound
    é estrutural e deve ser documentado em qualquer análise downstream (BLK-LTV-03+).

USAR_PROB_ABSOLUTA:
    A coluna derivada `prob_cancel_90d_media_absoluta` implementa o gate semântico:
    retorna PROB_CANCEL_90D_MEDIA apenas para as unidades "Sim"; as demais recebem
    NaN, sinalizando que APENAS o ranking é válido para aquelas unidades.
    Haircut volumétrico (aplicado a CHURN_ESPERADO_90D_TOTAL) é responsabilidade
    do BLK-LTV-03.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Colunas territoriais a ler de hexagonos_mercado_mapeado.parquet
TERRITORIAL_COLUMNS: list[str] = [
    "hex_id",
    "renda_per_capita",
    "score_priorizacao",
    "score_expansao_hibrido",
    "n_concorrentes_mapeados_1km",
    "n_concorrentes_mapeados_2km",
    "pop_total_setor_2022",
    "densidade_pop_setor_hab_km2",
    "score_setor_2022_calibrado",
    "score_oportunidade_residual",
    "oferta_efetiva_disponivel",
    "flag_canibalizacao_ultra_1km",
]

# Colunas Lifetime a carregar de unidade_para_motor.parquet
LIFETIME_COLUMNS: list[str] = [
    "COD_UNIDADE",
    "UNIDADE",
    "UF",
    "N_ALUNOS",
    "TICKET_MEDIO_UNIDADE",
    "RECEITA_MENSAL_TOTAL",
    "PROB_CANCEL_90D_MEDIA",
    "PROB_CANCEL_90D_P50",
    "P_CANCEL_12M_MEDIA",
    "P_CANCEL_12M_P50",
    "E_MESES_ATIVOS_12M_MEDIANO",
    "LTV_PROSPECTIVO_12M_MEDIANO",
    "LTV_PROSPECTIVO_12M_MEDIO",
    "LTV_PROSPECTIVO_12M_TOTAL",
    "PCT_LTV_FRAGIL",
    "PCT_LTV_EM_RISCO",
    "PCT_LTV_DURAVEL",
    "PCT_LTV_ALTA_DURABILIDADE",
    "CONFIABILIDADE_UNIDADE",
    "USAR_PROB_ABSOLUTA",
    "USAR_RANKING",
]

# Colunas da ponte (unidade_hex.parquet) a carregar
BRIDGE_COLUMNS: list[str] = [
    "cod_unidade",
    "hex_id",
    "metodo_match",
    "match_score",
]

# Ordem de saída do parquet (36 colunas)
OUTPUT_COLUMNS: list[str] = [
    # Grupo A — Identificação (da ponte)
    "cod_unidade",
    "hex_id",
    "metodo_match",
    "match_score",
    # Grupo B — Identificação e tamanho (do Lifetime)
    "UNIDADE",
    "UF",
    "N_ALUNOS",
    "TICKET_MEDIO_UNIDADE",
    "RECEITA_MENSAL_TOTAL",
    # Grupo C — Retenção 90d
    "PROB_CANCEL_90D_MEDIA",
    "PROB_CANCEL_90D_P50",
    "P_CANCEL_12M_MEDIA",
    "P_CANCEL_12M_P50",
    "E_MESES_ATIVOS_12M_MEDIANO",
    # Grupo D — LTV 12M
    "LTV_PROSPECTIVO_12M_MEDIANO",
    "LTV_PROSPECTIVO_12M_MEDIO",
    "LTV_PROSPECTIVO_12M_TOTAL",
    # Grupo E — Distribuição de durabilidade
    "PCT_LTV_FRAGIL",
    "PCT_LTV_EM_RISCO",
    "PCT_LTV_DURAVEL",
    "PCT_LTV_ALTA_DURABILIDADE",
    # Grupo F — Flags e confiabilidade
    "CONFIABILIDADE_UNIDADE",
    "USAR_PROB_ABSOLUTA",
    "USAR_RANKING",
    # Grupo G — Features territoriais (NaN se sem hex_id)
    "renda_per_capita",
    "score_priorizacao",
    "score_expansao_hibrido",
    "n_concorrentes_mapeados_1km",
    "n_concorrentes_mapeados_2km",
    "pop_total_setor_2022",
    "densidade_pop_setor_hab_km2",
    "score_setor_2022_calibrado",
    "score_oportunidade_residual",
    "oferta_efetiva_disponivel",
    "flag_canibalizacao_ultra_1km",
    # Grupo H — Derivada
    "prob_cancel_90d_media_absoluta",
]


# ---------------------------------------------------------------------------
# Funções privadas de leitura
# ---------------------------------------------------------------------------


def _load_bridge(path: Path) -> pd.DataFrame:
    """Carrega unidade_hex.parquet (ponte BLK-LTV-01).

    Returns:
        DataFrame com BRIDGE_COLUMNS, esperado 88 linhas.
    """
    return pd.read_parquet(path, columns=BRIDGE_COLUMNS)


def _load_lifetime(path: Path) -> pd.DataFrame:
    """Carrega unidade_para_motor.parquet (métricas Lifetime).

    Returns:
        DataFrame com LIFETIME_COLUMNS, esperado 88 linhas.
    """
    return pd.read_parquet(path, columns=LIFETIME_COLUMNS)


def _load_mercado(path: Path, hex_ids: set[str]) -> pd.DataFrame:
    """Carrega subset territorial de hexagonos_mercado_mapeado.parquet.

    Lê apenas TERRITORIAL_COLUMNS e filtra IMEDIATAMENTE para os hex_ids válidos
    para evitar OOM (o parquet tem 1,54 M linhas × 135 colunas).

    Args:
        path: caminho para hexagonos_mercado_mapeado.parquet.
        hex_ids: conjunto de hex_ids válidos a manter (≤ 56 hexes).

    Returns:
        DataFrame com TERRITORIAL_COLUMNS filtrado e deduplicado por hex_id.
    """
    df = pd.read_parquet(path, columns=TERRITORIAL_COLUMNS)
    df = df[df["hex_id"].isin(hex_ids)]
    df = df.drop_duplicates(subset=["hex_id"])
    return df


# ---------------------------------------------------------------------------
# Função pública principal
# ---------------------------------------------------------------------------


def build_unidade_territorio_retencao(
    bridge_path: Path,
    lifetime_path: Path,
    mercado_path: Path,
) -> pd.DataFrame:
    """Constrói a tabela unidade × território × retenção.

    Args:
        bridge_path: caminho para data/staging/unidade_hex.parquet.
        lifetime_path: caminho para data/ultra/unidade_para_motor.parquet.
        mercado_path: caminho para data/staging/hexagonos_mercado_mapeado.parquet.

    Returns:
        DataFrame com OUTPUT_COLUMNS (36 colunas), exatamente 88 linhas.
        As 32 unidades sem hex_id têm features territoriais = NaN.

    Raises:
        RuntimeError: se o inner merge bridge × Lifetime não resultar em 88 linhas.
    """
    # 1. Carregar insumos
    bridge = _load_bridge(bridge_path)    # (88, 4)
    ltv = _load_lifetime(lifetime_path)   # (88, 21)

    # 2. Normalizar chave para o merge (case + whitespace)
    bridge = bridge.copy()
    ltv = ltv.copy()
    bridge["_join_key"] = bridge["cod_unidade"].str.strip().str.upper()
    ltv["_join_key"] = ltv["COD_UNIDADE"].str.strip().str.upper()

    # 3. Merge 1 — Bridge × Lifetime (inner, 88/88 esperado)
    merged = bridge.merge(ltv, on="_join_key", how="inner")
    merged = merged.drop(columns=["_join_key", "COD_UNIDADE"])  # remover auxiliar e col duplicada
    n_merged = len(merged)
    if n_merged != len(bridge):
        raise RuntimeError(
            f"[BLK-LTV-02] Bridge × Lifetime inner merge resultou em {n_merged} linhas "
            f"(esperado {len(bridge)}). Verificar COD_UNIDADE na ponte e no parquet Lifetime."
        )

    # 4. Extrair hex_ids válidos para filtrar o mercado
    valid_hex_ids: set[str] = set(merged["hex_id"].dropna().unique())

    # 5. Carregar subset territorial
    mercado = _load_mercado(mercado_path, valid_hex_ids)

    # 6. Merge 2 — LEFT join por hex_id (preserva as 32 unidades sem hex)
    result = merged.merge(mercado, on="hex_id", how="left")

    # 7. Derivar coluna gate semântico USAR_PROB_ABSOLUTA
    result["prob_cancel_90d_media_absoluta"] = result["PROB_CANCEL_90D_MEDIA"].where(
        result["USAR_PROB_ABSOLUTA"].str.strip().str.lower() == "sim"
    )

    # 8. Selecionar e ordenar colunas de saída
    result = result[OUTPUT_COLUMNS]

    # 9. Log de cobertura
    notna_count = int(result["hex_id"].notna().sum())
    null_count = len(result) - notna_count
    confiabilidade_breakdown = result["CONFIABILIDADE_UNIDADE"].value_counts().to_dict()
    confiabilidade_str = ", ".join(f"{k}={v}" for k, v in confiabilidade_breakdown.items())
    prob_abs_non_null = int(result["prob_cancel_90d_media_absoluta"].notna().sum())
    prob_abs_null = int(result["prob_cancel_90d_media_absoluta"].isna().sum())

    print(f"[BLK-LTV-02] Total linhas: {len(result)} | hex_id notna: {notna_count}/{len(result)}")
    print(f"[BLK-LTV-02] CONFIABILIDADE_UNIDADE: {confiabilidade_str}")
    print(
        f"[BLK-LTV-02] prob_cancel_90d_media_absoluta: "
        f"{prob_abs_non_null} valores / {prob_abs_null} NaN"
    )
    print(
        f"[BLK-LTV-02] CAVEAT: {null_count} unidades sem hex_id têm features territoriais = NaN "
        f"(confound de maturidade também presente; sem data de abertura no parquet Lifetime)"
    )

    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run(root: Path | None = None) -> pd.DataFrame:
    """Executa o join territorial e grava o parquet de saída.

    Args:
        root: raiz do projeto (default: detectado a partir deste arquivo).

    Returns:
        DataFrame com 88 linhas e OUTPUT_COLUMNS.
    """
    if root is None:
        # src/motor_expansao/lifetime/join_territorio_retencao.py → ../../.. = raiz
        root = Path(__file__).resolve().parents[3]

    bridge_path = root / "data" / "staging" / "unidade_hex.parquet"
    lifetime_path = root / "data" / "ultra" / "unidade_para_motor.parquet"
    mercado_path = root / "data" / "staging" / "hexagonos_mercado_mapeado.parquet"
    output_path = root / "data" / "staging" / "unidade_territorio_retencao.parquet"

    result = build_unidade_territorio_retencao(bridge_path, lifetime_path, mercado_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output_path, index=False)
    print(f"[BLK-LTV-02] Parquet gravado: {output_path}")
    return result


def main() -> None:
    """Entry point para execução direta."""
    run()


if __name__ == "__main__":
    main()
