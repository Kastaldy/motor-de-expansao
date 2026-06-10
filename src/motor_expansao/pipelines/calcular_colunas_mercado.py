"""
Bloco 5 - Calculo das colunas de mercado.

Adiciona colunas de auditoria, TAM, SAM, residual, SOM, sizing absoluto
de fitness e classificacoes executivas ao parquet enriquecido.

Nao altera nenhum artefato oficial do M1.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from motor_expansao.pipelines.pop_corte import (
    derive_confianca_geografica,
    derive_pop_cut_columns,
)

ROOT = Path(__file__).resolve().parents[3]

MERCADO_PATH = ROOT / "data" / "staging" / "hexagonos_mercado_mapeado.parquet"
CENSO_PATH = ROOT / "data" / "staging" / "censo2022_setores_calibrado.parquet"
PERFORMANCE_HEX_PATH = ROOT / "data" / "staging" / "unidades_ultra_performance_hex.parquet"
CONCORRENTES_PATH = ROOT / "data" / "staging" / "concorrentes_mapeados.parquet"
OUT_PATH = ROOT / "data" / "staging" / "hexagonos_mercado_mapeado.parquet"

CENSO_COLS = ["hex_id", "pop_total_setor_2022", "renda_per_capita_setor_2022_calibrada"]
HYBRID_TIEBREAK_MAX_SCORE = 100.001
# Taxa calibrada em runtime a partir de todas as academias mapeadas (concorrentes + Ultra).
# Fallback de 10% quando ha menos de 10 hexes com academia E populacao no dataset de calibracao.
TAXA_FITNESS_MERCADO_FALLBACK = 0.10
TAXA_FITNESS_CALIBRADA = TAXA_FITNESS_MERCADO_FALLBACK  # alias backward-compat; sobrescrito em runtime
CAPACIDADE_MIN_ACADEMIA_ALUNOS = 2_000.0          # lower-bound conservador para calibracao
CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS = 2_500.0   # proxy por unidade para subtracao do residual
SCORE_RESIDUAL_CAPACIDADE_REFERENCIA = CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS
POP_MIN_SAM_GATE = 5_000  # regua operacional de populacao para o gate do SAM (camada paralela de mercado).
                          # Espelha POP_MIN_ACIONAVEL do dashboard; NAO e parametro do M1 oficial (§3).
SOURCE_REQUIRED_COLS = {
    "hex_id",
    "flag_censo_elegivel",
    "populacao_proxy",
    "renda_per_capita",
    "score_priorizacao",
    "faixa_oportunidade",
    "pop_total",
    "flag_hex_hibrido_elegivel",
    "score_expansao_hibrido",
    "flag_viavel",
    "top_municipio",
    "flag_white_space_2km",
    "flag_canibalizacao_ultra_1km",
    "n_concorrentes_mapeados_2km",
    "oferta_efetiva_mapeada_2km",
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


def calibrar_taxa_fitness_mercado(df: pd.DataFrame) -> float:
    """Calcula taxa de penetracao fitness a partir de todas as academias mapeadas no dataset.

    Logica: para cada hex com pelo menos uma academia (concorrente OU Ultra) e populacao
    conhecida, calcula a penetracao minima implicita assumindo CAPACIDADE_MIN_ACADEMIA_ALUNOS
    por unidade. A mediana dessa distribuicao vira a taxa de mercado aplicada ao TAM.

    Requer min. 10 hexes com academia e populacao valida; caso contrario retorna o fallback.
    """
    pop = pd.to_numeric(df["pop_hex_base"], errors="coerce")
    n_conc = pd.to_numeric(
        df["n_concorrentes_mapeados_2km"] if "n_concorrentes_mapeados_2km" in df.columns
        else pd.Series(0, index=df.index),
        errors="coerce",
    ).fillna(0)
    n_ultra = pd.to_numeric(
        df["n_unidades_ultra_2km"] if "n_unidades_ultra_2km" in df.columns
        else pd.Series(0, index=df.index),
        errors="coerce",
    ).fillna(0)
    n_total = n_conc + n_ultra
    mask = n_total.gt(0) & pop.gt(0)

    if int(mask.sum()) < 10:
        return TAXA_FITNESS_MERCADO_FALLBACK

    penetracao = (n_total[mask] * CAPACIDADE_MIN_ACADEMIA_ALUNOS) / pop[mask]
    # Clip: piso de 5% (academias em hexes muito populosos) e teto de 50% (outlier)
    taxa = float(penetracao.clip(lower=0.05, upper=0.50).median())
    return taxa


def validar_entradas(df: pd.DataFrame) -> None:
    faltam = SOURCE_REQUIRED_COLS - set(df.columns)
    assert not faltam, f"Colunas base faltando antes do Bloco 5: {faltam}"


def _safe_div(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce")
    valid_denominator = denominator.where(denominator > 0)
    return numerator / valid_denominator


def anexar_oferta_ultra_real(
    df: pd.DataFrame,
    performance_hex_path: Path = PERFORMANCE_HEX_PATH,
) -> pd.DataFrame:
    """Anexa alunos reais das unidades Ultra quando existe match exato por hex."""
    out = df.drop(
        columns=[
            col
            for col in ["oferta_consumida_ultra_real", "n_unidades_ultra_performance_hex"]
            if col in df.columns
        ]
    ).copy()

    if not performance_hex_path.exists():
        out["oferta_consumida_ultra_real"] = 0.0
        out["n_unidades_ultra_performance_hex"] = 0
        return out

    perf = pd.read_parquet(performance_hex_path)
    required = {"hex_id_res7", "alunos_total"}
    faltam = required - set(perf.columns)
    if faltam:
        raise AssertionError(
            f"Colunas obrigatorias ausentes em {performance_hex_path.name}: {sorted(faltam)}"
        )

    perf = perf[perf["hex_id_res7"].notna()].copy()
    perf["alunos_total_num"] = pd.to_numeric(perf["alunos_total"], errors="coerce")
    perf = perf[perf["alunos_total_num"].notna() & (perf["alunos_total_num"] > 0)]

    agg = (
        perf.groupby("hex_id_res7", as_index=False)
        .agg(
            oferta_consumida_ultra_real=("alunos_total_num", "sum"),
            n_unidades_ultra_performance_hex=("alunos_total_num", "size"),
        )
        .rename(columns={"hex_id_res7": "hex_id"})
    )

    out = out.merge(agg, on="hex_id", how="left", validate="one_to_one")
    out["oferta_consumida_ultra_real"] = (
        pd.to_numeric(out["oferta_consumida_ultra_real"], errors="coerce").fillna(0.0)
    )
    out["n_unidades_ultra_performance_hex"] = (
        pd.to_numeric(out["n_unidades_ultra_performance_hex"], errors="coerce")
        .fillna(0)
        .astype("int64")
    )
    return out


def _contar_redes_mapeadas() -> int:
    """Conta redes unicas validas no snapshot de concorrentes."""
    if not CONCORRENTES_PATH.exists():
        return 0
    comp = pd.read_parquet(CONCORRENTES_PATH, columns=["rede", "status_registro"])
    return int(comp.loc[comp["status_registro"] == "valido", "rede"].nunique())


def calcular(df: pd.DataFrame, n_redes: int | None = None) -> pd.DataFrame:
    """Materializa colunas de mercado sobre o DataFrame ja enriquecido."""
    n = len(df)

    # 5.1 - Auditoria
    df["data_snapshot_mercado"] = str(date.today())
    df["fonte_oferta_principal"] = "csv_big_players_mapeados"
    df["n_redes_mapeadas"] = n_redes if n_redes is not None else _contar_redes_mapeadas()

    # Granularidade da demanda
    mask_hex_censo = (
        df["flag_censo_elegivel"].fillna(False).astype(bool)
        & df["pop_total_setor_2022"].notna()
    )
    df["demanda_granularidade"] = np.where(mask_hex_censo, "hex_censo", "municipio_proxy")
    df["fonte_demanda_principal"] = np.where(mask_hex_censo, "censo_2022_hex", "m1_municipal_proxy")

    # 5.2 - TAM
    pop_censo = pd.to_numeric(df["pop_total_setor_2022"], errors="coerce")
    pop_proxy = pd.to_numeric(df["populacao_proxy"], errors="coerce")

    # Bloco 8: pop_hex_base usa pop_total_setor_2022 sempre que disponivel (>0),
    # independente do gate de densidade do flag_censo_elegivel.
    # Fallback: proxy distribuido por hex do municipio para evitar inflate.
    censo_pop_ok = pop_censo.gt(0)
    if "total_hex_municipio" in df.columns:
        total_hex_mun = pd.to_numeric(df["total_hex_municipio"], errors="coerce")
    else:
        total_hex_mun = pd.Series(1.0, index=df.index)
    total_hex_mun = total_hex_mun.where(total_hex_mun > 0)
    proxy_per_hex = pop_proxy / total_hex_mun
    proxy_pop_ok = ~censo_pop_ok & proxy_per_hex.gt(0)

    df["pop_hex_base"] = np.select(
        [censo_pop_ok, proxy_pop_ok],
        [pop_censo, proxy_per_hex],
        default=np.nan,
    )
    df["fonte_pop_hex_base"] = np.select(
        [censo_pop_ok, proxy_pop_ok],
        ["censo_2022_setor", "m1_municipal_proxy_per_hex"],
        default="sem_populacao_valida",
    )

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
    df["tam_populacao_hex"] = pd.to_numeric(df["pop_hex_base"], errors="coerce")

    # Calibra taxa de penetracao fitness a partir de TODAS as academias mapeadas.
    # Corrige o erro anterior que usava penetracao da Ultra como proxy do mercado total.
    taxa_fitness_mercado = calibrar_taxa_fitness_mercado(df)
    df["taxa_fitness_mercado_calibrada"] = taxa_fitness_mercado
    df["taxa_fitness_calibrada"] = taxa_fitness_mercado  # alias backward-compat

    df["tam_fitness_potencial"] = (
        df["tam_populacao_hex"].clip(lower=0) * taxa_fitness_mercado
    ).where(df["tam_populacao_hex"].notna(), np.nan)

    # 5.4 - SAM
    # Regua de populacao do corte (DEC-006/DEC-007): replica a regua do dashboard via helper
    # compartilhado (setor 2022 quando o hex e granular, fallback pop_total municipal).
    # granular = qualidade_join_uf in {A,B} AND (flag_censo_disponivel OR score_setor_2022_calibrado notna),
    # NAO e flag_censo_elegivel/mask_hex_censo.
    df["confianca_geografica"] = derive_confianca_geografica(df)
    df = derive_pop_cut_columns(df, pop_min=POP_MIN_SAM_GATE)

    flag_canibal = df["flag_canibalizacao_ultra_1km"].fillna(False).astype(bool)
    flag_viavel = df["flag_viavel"].fillna(False).astype(bool)
    flag_top_mun = df["top_municipio"].fillna(False).astype(bool)
    flag_white = df["flag_white_space_2km"].fillna(False).astype(bool)
    flag_hibrid_elig = df["flag_hex_hibrido_elegivel"].fillna(False).astype(bool)

    # Gate DEC-007 (reverte 2 sub-decisoes da DEC-006): apenas faixa M1 elegivel AND
    # populacao_corte_hex >= 5000. flag_viavel e ~canibalizacao SAIRAM do gate (Vinicius 2026-06-10).
    faixa_elegivel = (
        df["faixa_oportunidade"].astype("object")
        .isin({"baixa", "media", "alta", "prioridade_maxima"})
    )
    flag_pop_ok = df["flag_pop_min_5k"].fillna(False).astype(bool)

    df["flag_sam"] = faixa_elegivel & flag_pop_ok
    flag_sam = df["flag_sam"].astype(bool)

    df["sam_indice_operavel"] = np.where(flag_sam, df["tam_indice_demanda"], 0.0)
    df["sam_populacao_base"] = np.where(flag_sam, df["tam_populacao_base"], 0.0)
    # flag_sam_fitness == flag_sam: o piso tam_populacao_hex>0 SAI (redundante com o corte >=5000).
    df["flag_sam_fitness"] = flag_sam
    df["sam_fitness_potencial"] = np.where(
        df["flag_sam_fitness"],
        pd.to_numeric(df["tam_fitness_potencial"], errors="coerce").fillna(0.0),
        0.0,
    )

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

    oferta_mercado_ponderada = (
        pd.to_numeric(df["oferta_efetiva_mapeada_2km"], errors="coerce").fillna(0.0).clip(lower=0)
    )
    df["capacidade_default_concorrente_alunos"] = CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS
    # Concorrentes: oferta espacialmente ponderada (distancia-decaida ate 2km)
    df["oferta_consumida_mercado_estimada"] = (
        oferta_mercado_ponderada * CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS
    )
    if "oferta_consumida_ultra_real" not in df.columns:
        df["oferta_consumida_ultra_real"] = 0.0
    df["oferta_consumida_ultra_real"] = (
        pd.to_numeric(df["oferta_consumida_ultra_real"], errors="coerce").fillna(0.0).clip(lower=0)
    )

    # Ultra: usa alunos reais (hex exato) quando disponiveis; fallback por contagem de
    # unidades vizinhas (2km) para capturar oferta Ultra que ainda nao casou com performance.
    n_ultra_2km = pd.to_numeric(
        df["n_unidades_ultra_2km"] if "n_unidades_ultra_2km" in df.columns
        else pd.Series(0, index=df.index),
        errors="coerce",
    ).fillna(0.0).clip(lower=0)
    ultra_real = pd.to_numeric(df["oferta_consumida_ultra_real"], errors="coerce").fillna(0.0)
    df["oferta_consumida_ultra_estimada"] = np.where(
        ultra_real > 0,
        ultra_real,
        n_ultra_2km * CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS,
    )
    df["oferta_consumida_total_estimada"] = (
        df["oferta_consumida_mercado_estimada"] + df["oferta_consumida_ultra_estimada"]
    )

    # Residual = SAM - toda a oferta existente (concorrentes + Ultra)
    df["oferta_efetiva_disponivel"] = np.maximum(
        pd.to_numeric(df["sam_fitness_potencial"], errors="coerce").fillna(0.0)
        - df["oferta_consumida_total_estimada"],
        0.0,
    )
    # Penetracao total do mercado fitness (todos os players mapeados)
    df["penetracao_fitness_mercado_estimada"] = _safe_div(
        df["oferta_consumida_total_estimada"],
        df["tam_fitness_potencial"],
    ).fillna(0.0)
    df["share_ultra_estimado_hex"] = _safe_div(
        df["oferta_consumida_ultra_real"],
        df["oferta_consumida_ultra_real"] + df["oferta_consumida_mercado_estimada"],
    ).fillna(0.0)
    df["score_oportunidade_residual"] = (
        100.0 * df["oferta_efetiva_disponivel"] / SCORE_RESIDUAL_CAPACIDADE_REFERENCIA
    ).clip(lower=0.0, upper=100.0)

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
    print("\n=== Validacao Bloco 5 ===")

    required = {
        "data_snapshot_mercado", "fonte_demanda_principal", "fonte_oferta_principal",
        "n_redes_mapeadas", "demanda_granularidade",
        "tam_populacao_base", "tam_renda_base", "tam_indice_demanda",
        "tam_indice_demanda_norm", "tam_pop_total_base",
        "pop_hex_base", "fonte_pop_hex_base", "tam_populacao_hex",
        "taxa_fitness_mercado_calibrada", "taxa_fitness_calibrada", "tam_fitness_potencial",
        "populacao_corte_hex", "fonte_populacao_corte", "flag_pop_min_5k",
        "flag_sam", "flag_sam_fitness", "sam_indice_operavel",
        "sam_populacao_base", "sam_fitness_potencial", "sam_granularidade",
        "residual_indice_mapeado", "residual_populacao_mapeada",
        "capacidade_captura_mapeada", "som_indice_mapeado", "som_populacao_mapeada",
        "capacidade_default_concorrente_alunos",
        "oferta_consumida_mercado_estimada", "oferta_consumida_ultra_real",
        "oferta_consumida_ultra_estimada", "oferta_consumida_total_estimada",
        "oferta_efetiva_disponivel",
        "penetracao_fitness_mercado_estimada", "share_ultra_estimado_hex",
        "score_oportunidade_residual",
        "tese_entrada", "prioridade_mercado_mapeado",
    }
    faltam = required - set(df.columns)
    assert not faltam, f"Colunas faltando: {faltam}"
    print("Schema OK")

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
    non_negative_cols = [
        "tam_fitness_potencial",
        "sam_fitness_potencial",
        "oferta_consumida_mercado_estimada",
        "oferta_consumida_ultra_real",
        "oferta_consumida_ultra_estimada",
        "oferta_consumida_total_estimada",
        "oferta_efetiva_disponivel",
        "penetracao_fitness_mercado_estimada",
        "share_ultra_estimado_hex",
        "score_oportunidade_residual",
    ]
    for col in non_negative_cols:
        assert (pd.to_numeric(df[col], errors="coerce").fillna(0.0) >= 0).all(), (
            f"{col} tem valores negativos"
        )
    assert df["share_ultra_estimado_hex"].between(0, 1).all(), (
        "share_ultra_estimado_hex fora de [0, 1]"
    )
    assert df["score_oportunidade_residual"].between(0, 100).all(), (
        "score_oportunidade_residual fora de [0, 100]"
    )
    print("Faixas OK")

    taxa_cal = float(df["taxa_fitness_mercado_calibrada"].iloc[0])
    print(f"\ntaxa_fitness_mercado_calibrada: {taxa_cal:.1%}  "
          f"(fallback={TAXA_FITNESS_MERCADO_FALLBACK:.0%})")
    print(f"tam_indice_demanda: min={df['tam_indice_demanda'].min():.1f}  "
          f"max={df['tam_indice_demanda'].max():.1f}  "
          f"mean={df['tam_indice_demanda'].mean():.1f}")
    print(f"tam_fitness_potencial: min={df['tam_fitness_potencial'].min():.1f}  "
          f"max={df['tam_fitness_potencial'].max():.1f}  "
          f"mean={df['tam_fitness_potencial'].mean():.1f}")
    print(f"flag_sam=True: {df['flag_sam'].sum():,} ({100*df['flag_sam'].mean():.1f}%)")
    print(f"oferta_efetiva_disponivel soma: {df['oferta_efetiva_disponivel'].sum():,.0f}")
    print(f"\ntese_entrada:\n{df['tese_entrada'].value_counts().to_string()}")
    print(f"\nprioridade_mercado_mapeado:\n{df['prioridade_mercado_mapeado'].value_counts().to_string()}")
    print(f"\nsam_granularidade:\n{df['sam_granularidade'].value_counts().to_string()}")
    print(f"\ndemanda_granularidade:\n{df['demanda_granularidade'].value_counts().to_string()}")
    print(f"\nfonte_pop_hex_base:\n{df['fonte_pop_hex_base'].value_counts().to_string()}")

    proxy_mask = df["fonte_pop_hex_base"].eq("m1_municipal_proxy_per_hex")
    if proxy_mask.any():
        sam_proxy = df.loc[proxy_mask, "sam_fitness_potencial"].fillna(0.0)
        pop_base_proxy = pd.to_numeric(df.loc[proxy_mask, "pop_hex_base"], errors="coerce").fillna(0.0)
        taxa_real = float(df["taxa_fitness_mercado_calibrada"].iloc[0])
        max_allowed = pop_base_proxy * taxa_real
        violacoes = int((sam_proxy > max_allowed + 1e-6).sum())
        assert violacoes == 0, f"SAM proxy excede limite (pop_hex_base * taxa): {violacoes} casos"
        print(f"Proxy hexes SAM constraint OK: {int(proxy_mask.sum()):,} hexes validados")

    print("\nValidacao OK")


def main():
    print("Bloco 5 - Calculo das colunas de mercado")
    print("=" * 50)

    print("\n1. Carregando base enriquecida...")
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

    print("\n3. Anexando consumo real Ultra por hex...")
    df = anexar_oferta_ultra_real(df)
    assert len(df) == n_orig, "Join Ultra real alterou cardinalidade"
    print(f"   alunos Ultra reais anexados: {df['oferta_consumida_ultra_real'].sum():,.0f}")

    n_redes = _contar_redes_mapeadas()
    print(f"\n4. Calculando colunas de mercado ({n_redes} redes mapeadas)...")
    df = calcular(df, n_redes=n_redes)
    print(f"   {df.shape[1]} colunas totais")

    validar(df)

    print(f"\n5. Salvando em {OUT_PATH}...")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH, index=False)
    size_mb = OUT_PATH.stat().st_size / 1e6
    print(f"   Salvo: {size_mb:.1f} MB")
    print("\nBloco 5 concluido.")


if __name__ == "__main__":
    main()
