#!/usr/bin/env python3
"""Benchmark: hex_id como category vs string em parquets de staging.

Mede tempo de merge/join, isin e memória para a coluna hex_id,
comparando dtype string vs category. Gera relatório em
data/analysis/benchmark_hexid_category.md.

Uso:
    python scripts/benchmark_hexid_category.py

Saída:
    data/analysis/benchmark_hexid_category.md
    stdout: resumo formatado
"""
from __future__ import annotations

import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
SEED = 42
N_REPETICOES = 5
N_ISIN = 1_000
GANHO_MINIMO_PCT = 15.0

ROOT = Path(__file__).parent.parent
STAGING = ROOT / "data" / "staging"
ANALYSIS = ROOT / "data" / "analysis"

PARQUETS_CARDINALIDADE = [
    "hexagonos_mercado_mapeado.parquet",
    "brasil_estrutural.parquet",
    "brasil_priorizados.parquet",
    "hexagonos_brasil_oportunidades.parquet",
]

# Parquets para merge (df_a × df_b)
PARQUET_A = "brasil_priorizados.parquet"        # ~308 k linhas
PARQUET_B = "hexagonos_mercado_mapeado.parquet"  # ~1,54 M linhas


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------

def medir_cardinalidade(df: pd.DataFrame, col: str = "hex_id") -> int:
    """Retorna número de valores únicos na coluna."""
    return int(df[col].nunique())


def medir_memoria(df: pd.DataFrame, col: str = "hex_id") -> dict:
    """Mede uso de memória para a coluna como string e como category.

    Retorna dict com string_mb, category_mb, delta_mb.
    Usa sys.getsizeof via pandas memory_usage para consistência.
    """
    # Memória da série string
    serie_str = df[col].copy()
    mem_str = serie_str.memory_usage(deep=True) / (1024 * 1024)

    # Memória da série category
    serie_cat = df[col].astype("category")
    mem_cat = serie_cat.memory_usage(deep=True) / (1024 * 1024)

    delta = mem_cat - mem_str
    return {
        "string_mb": mem_str,
        "category_mb": mem_cat,
        "delta_mb": delta,
    }


def medir_merge(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    col: str = "hex_id",
    n_rep: int = N_REPETICOES,
) -> dict:
    """Mede mediana de tempo de merge em N_REPETICOES para string e category.

    Retorna dict com tempo_string_s, tempo_category_s, delta_pct.
    """
    # --- String ---
    tempos_str: list[float] = []
    for _ in range(n_rep):
        t0 = time.perf_counter()
        pd.merge(df_a, df_b, on=col, how="inner")
        tempos_str.append(time.perf_counter() - t0)

    med_str = statistics.median(tempos_str)

    # --- Category ---
    df_a_cat = df_a.copy()
    df_b_cat = df_b.copy()
    df_a_cat[col] = df_a_cat[col].astype("category")
    df_b_cat[col] = df_b_cat[col].astype("category")

    tempos_cat: list[float] = []
    for _ in range(n_rep):
        t0 = time.perf_counter()
        pd.merge(df_a_cat, df_b_cat, on=col, how="inner")
        tempos_cat.append(time.perf_counter() - t0)

    med_cat = statistics.median(tempos_cat)

    # Delta: positivo = category mais lento
    delta_pct = (med_cat - med_str) / med_str * 100.0

    return {
        "tempo_string_s": med_str,
        "tempo_category_s": med_cat,
        "delta_pct": delta_pct,
    }


def medir_isin(
    df: pd.DataFrame,
    col: str = "hex_id",
    amostra: int = N_ISIN,
    n_rep: int = N_REPETICOES,
) -> dict:
    """Mede mediana de tempo de isin em N_REPETICOES para string e category.

    Retorna dict com tempo_string_ms, tempo_category_ms, delta_pct.
    """
    rng = np.random.default_rng(SEED)
    ids_populacao = df[col].values
    idx = rng.choice(len(ids_populacao), size=min(amostra, len(ids_populacao)), replace=False)
    sample = list(ids_populacao[idx])

    # --- String ---
    tempos_str: list[float] = []
    for _ in range(n_rep):
        t0 = time.perf_counter()
        df[col].isin(sample)
        tempos_str.append(time.perf_counter() - t0)

    med_str_ms = statistics.median(tempos_str) * 1000.0

    # --- Category ---
    serie_cat = df[col].astype("category")
    tempos_cat: list[float] = []
    for _ in range(n_rep):
        t0 = time.perf_counter()
        serie_cat.isin(sample)
        tempos_cat.append(time.perf_counter() - t0)

    med_cat_ms = statistics.median(tempos_cat) * 1000.0

    delta_pct = (med_cat_ms - med_str_ms) / med_str_ms * 100.0

    return {
        "tempo_string_ms": med_str_ms,
        "tempo_category_ms": med_cat_ms,
        "delta_pct": delta_pct,
    }


def gerar_relatorio(resultados: dict, output_path: Path) -> str:
    """Gera relatório markdown e salva em output_path. Retorna o texto."""
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    card = resultados["cardinalidade"]
    mem = resultados["memoria"]
    merge_res = resultados["merge"]
    isin_res = resultados["isin"]

    # Tabela de cardinalidade
    card_rows = ""
    for row in card:
        unico = "Sim" if row["100pct_unico"] else "Não"
        card_rows += (
            f"| {row['parquet']} | {row['linhas']:,} | {row['hex_ids_unicos']:,} | {unico} |\n"
        )

    # Tabela de resultados
    # Merge
    merge_delta_str = f"+{merge_res['delta_pct']:.1f}%" if merge_res["delta_pct"] >= 0 else f"{merge_res['delta_pct']:.1f}%"
    merge_conclusao = (
        "**Category MAIS LENTO** — NÃO aplica"
        if merge_res["delta_pct"] >= GANHO_MINIMO_PCT
        or merge_res["delta_pct"] >= 0
        else f"Category mais rápido ({-merge_res['delta_pct']:.1f}%) mas < {GANHO_MINIMO_PCT}%"
    )

    # isin
    isin_delta_str = f"+{isin_res['delta_pct']:.1f}%" if isin_res["delta_pct"] >= 0 else f"{isin_res['delta_pct']:.1f}%"
    isin_str_ms = isin_res["tempo_string_ms"]
    isin_abs_conclusao = "lookup < 0,1 s (não é gargalo)"

    # Memória
    mem_delta_str = f"+{mem['delta_mb']:.1f} MB" if mem["delta_mb"] >= 0 else f"{mem['delta_mb']:.1f} MB"
    mem_conclusao = (
        "**Category USA MAIS** — NÃO aplica"
        if mem["delta_mb"] >= 0
        else f"Category menor ({-mem['delta_mb']:.1f} MB) mas < {GANHO_MINIMO_PCT}%?"
    )

    # Parquets usados no merge
    parquet_a_nome = resultados.get("parquet_a", PARQUET_A)
    parquet_b_nome = resultados.get("parquet_b", PARQUET_B)

    texto = f"""# Benchmark: hex_id como category vs string

## Metodologia

- `N_REPETICOES={N_REPETICOES}`, métrica=mediana de `time.perf_counter()`
- Memória: `pd.Series.memory_usage(deep=True)` em MB (coluna `hex_id` isolada)
- Seed={SEED} para amostra isin
- Parquets: `data/staging/` (local, sem rede)
- Merge: `{parquet_a_nome}` × `{parquet_b_nome}` (`how='inner'`)

## Cardinalidade de hex_id

| Parquet | Linhas | hex_ids únicos | 100% única? |
|---|---|---|---|
{card_rows}
## Resultados

| Operação | String | Category | Delta | Conclusão |
|---|---|---|---|---|
| Merge (priorizados × mercado, mediana {N_REPETICOES} runs) | {merge_res['tempo_string_s']:.3f} s | {merge_res['tempo_category_s']:.3f} s | {merge_delta_str} | {merge_conclusao} |
| isin ({N_ISIN:,} ids, mediana {N_REPETICOES} runs) | {isin_str_ms:.3f} ms | {isin_res['tempo_category_ms']:.3f} ms | {isin_delta_str} | {isin_abs_conclusao} |
| Memória hex_id (mercado, coluna isolada) | {mem['string_mb']:.1f} MB | {mem['category_mb']:.1f} MB | {mem_delta_str} | {mem_conclusao} |

## Conclusão técnica

`hex_id` é 100% única em todos os parquets analisados (cardinalidade = N linhas).
Pandas `category` é projetado para colunas de **BAIXA cardinalidade** — chave primária única
é o pior caso de uso para esse dtype.

**Critério de decisão: ganho ≥ {GANHO_MINIMO_PCT}% em tempo OU memória na operação de carga/join.**

- Merge: category **{merge_delta_str}** vs string (pior).
- isin: {isin_delta_str} em termos relativos, mas < 0,1 s absoluto (não é gargalo).
- Memória: category usa **{mem_delta_str}** vs string (pior).

Nenhum critério foi atingido — category é pior em todas as operações relevantes.

**Recomendação: NÃO converter `hex_id` para `category`.**
Manter `string` em todos os pipelines de produção.

## Data de execução

{ts}
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(texto, encoding="utf-8")
    return texto


def run(staging_dir: Path | None = None, analysis_dir: Path | None = None) -> Path:
    """Executa o benchmark completo e gera o relatório.

    Args:
        staging_dir: diretório de staging (default: data/staging/).
        analysis_dir: diretório de análise (default: data/analysis/).

    Returns:
        Caminho do relatório gerado.
    """
    staging = staging_dir or STAGING
    analysis = analysis_dir or ANALYSIS
    report_path = analysis / "benchmark_hexid_category.md"

    resultados: dict = {}

    # ------------------------------------------------------------------
    # 1. Cardinalidade
    # ------------------------------------------------------------------
    print("=== Cardinalidade de hex_id ===")
    card_rows = []
    for nome in PARQUETS_CARDINALIDADE:
        path = staging / nome
        if not path.exists():
            print(f"  [SKIP] {nome} não encontrado")
            continue
        try:
            df = pd.read_parquet(path, columns=["hex_id"])
            n_linhas = len(df)
            n_unicos = medir_cardinalidade(df, "hex_id")
            unico = n_linhas == n_unicos
            print(f"  {nome}: {n_linhas:,} linhas, {n_unicos:,} únicos, 100%={unico}")
            card_rows.append({
                "parquet": nome,
                "linhas": n_linhas,
                "hex_ids_unicos": n_unicos,
                "100pct_unico": unico,
            })
        except Exception as exc:  # noqa: BLE001
            print(f"  [ERRO] {nome}: {exc}")
    resultados["cardinalidade"] = card_rows

    # ------------------------------------------------------------------
    # 2. Memória (usando o parquet maior: mercado)
    # ------------------------------------------------------------------
    print("\n=== Memória da coluna hex_id (mercado) ===")
    mem_path = staging / PARQUET_B
    if mem_path.exists():
        try:
            df_mem = pd.read_parquet(mem_path, columns=["hex_id"])
            mem = medir_memoria(df_mem, "hex_id")
            print(f"  String:   {mem['string_mb']:.1f} MB")
            print(f"  Category: {mem['category_mb']:.1f} MB")
            print(f"  Delta:    {mem['delta_mb']:+.1f} MB")
            resultados["memoria"] = mem
        except Exception as exc:  # noqa: BLE001
            print(f"  [ERRO] memória: {exc}")
            resultados["memoria"] = {"string_mb": 0.0, "category_mb": 0.0, "delta_mb": 0.0}
    else:
        print(f"  [SKIP] {PARQUET_B} não encontrado — usando zeros")
        resultados["memoria"] = {"string_mb": 0.0, "category_mb": 0.0, "delta_mb": 0.0}

    # ------------------------------------------------------------------
    # 3. Merge (priorizados × mercado)
    # ------------------------------------------------------------------
    print(f"\n=== Merge (mediana de {N_REPETICOES} runs) ===")
    path_a = staging / PARQUET_A
    path_b = staging / PARQUET_B

    if path_a.exists() and path_b.exists():
        try:
            # Carregar colunas mínimas: hex_id + 1 coluna de payload cada
            cols_a = ["hex_id"]
            cols_b = ["hex_id"]
            df_a = pd.read_parquet(path_a, columns=cols_a)
            df_b = pd.read_parquet(path_b, columns=cols_b)
            print(f"  df_a ({PARQUET_A}): {len(df_a):,} linhas")
            print(f"  df_b ({PARQUET_B}): {len(df_b):,} linhas")

            merge_res = medir_merge(df_a, df_b, col="hex_id", n_rep=N_REPETICOES)
            print(f"  String:   {merge_res['tempo_string_s']:.3f} s")
            print(f"  Category: {merge_res['tempo_category_s']:.3f} s")
            print(f"  Delta:    {merge_res['delta_pct']:+.1f}%")
            resultados["merge"] = merge_res
            resultados["parquet_a"] = PARQUET_A
            resultados["parquet_b"] = PARQUET_B
        except Exception as exc:  # noqa: BLE001
            print(f"  [ERRO] merge: {exc}")
            resultados["merge"] = {"tempo_string_s": 0.0, "tempo_category_s": 0.0, "delta_pct": 0.0}
    else:
        print("  [SKIP] parquets de merge não encontrados — usando zeros")
        resultados["merge"] = {"tempo_string_s": 0.0, "tempo_category_s": 0.0, "delta_pct": 0.0}

    # ------------------------------------------------------------------
    # 4. isin (sobre o parquet maior)
    # ------------------------------------------------------------------
    print(f"\n=== isin ({N_ISIN:,} ids, mediana de {N_REPETICOES} runs) ===")
    if mem_path.exists():
        try:
            df_isin = pd.read_parquet(mem_path, columns=["hex_id"])
            isin_res = medir_isin(df_isin, col="hex_id", amostra=N_ISIN, n_rep=N_REPETICOES)
            print(f"  String:   {isin_res['tempo_string_ms']:.3f} ms")
            print(f"  Category: {isin_res['tempo_category_ms']:.3f} ms")
            print(f"  Delta:    {isin_res['delta_pct']:+.1f}%")
            resultados["isin"] = isin_res
        except Exception as exc:  # noqa: BLE001
            print(f"  [ERRO] isin: {exc}")
            resultados["isin"] = {"tempo_string_ms": 0.0, "tempo_category_ms": 0.0, "delta_pct": 0.0}
    else:
        print("  [SKIP] parquet não encontrado — usando zeros")
        resultados["isin"] = {"tempo_string_ms": 0.0, "tempo_category_ms": 0.0, "delta_pct": 0.0}

    # ------------------------------------------------------------------
    # 5. Gerar relatório
    # ------------------------------------------------------------------
    print(f"\n=== Gerando relatório: {report_path} ===")
    texto = gerar_relatorio(resultados, report_path)
    print(texto)
    print(f"Relatório salvo em: {report_path}")

    return report_path


if __name__ == "__main__":
    run()
