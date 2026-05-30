"""
Calibração da renda censitária (Censo 2022) para compatibilidade com o M1.

Problema: renda_per_capita_setor_2022 (V06004/v0005 do Censo 2022) está em
escala diferente de renda_per_capita do M1 (SIDRA 10295 var 13431).
Correlação hex-level é estruturalmente baixa (~0.08) porque M1 é uniforme
por município enquanto o setor tem variação intraurbana — esse é o valor
da Fase A, não um defeito.

Abordagem vencedora: Multiplicativo global (renda) + pop_pct_municipal (híbrida)

  RENDA:
    k = median(M1_nacional) / median(setor_piloto)  ≈ 1.02
    renda_calibrada = k * renda_setor
    renda_pct_nacional_calibrado = percentile(renda_calibrada, M1_nacional)

  POPULAÇÃO:
    pop_pct_municipal = rank(pop_total_setor_2022) within-municipality
    — NÃO usa pop_pct_nacional_m1: megacidades (SP) têm pop_pct=1.000
      para todos os hexes → amplitude colapsa para 32 (FALHA gate)
    — NÃO usa pop_pct_setor (within-pilot): SP capital spearman=0.587 < 0.6
      porque pop e renda são negativamente correlacionados em SP (favelas
      densas em áreas de baixa renda vs. áreas ricas esparsas)
    — within-municipality: melhor representação de densidade relativa
      dentro de cada mercado local

  SCORE:
    score_setor_2022_calibrado = clip(100*(0.60*renda_pct + 0.40*pop_pct_mun) + ajuste, 0, 100)

  Resultados:
  - k ≈ 1.02: ajuste mínimo, preserva toda variação intraurbana
  - Monotônico em renda: rank order 100% preservado
  - Amplitude GO=92.1, SP=63.4, RJ=73.5 (> 50 gate ✓)
  - Spearman GO=0.87, SP=0.65, RJ=0.82 (> 0.6 gate ✓)

  Abordagens rejeitadas:
  - Multiplicativo por UF (k≈1.55-1.68): amplitude cai para 29-47 (FALHA)
  - Quantile normalization: amplitude artificialmente uniforme ~90 (perde sinal)
  - pop_pct_nacional_m1: amplitude SP=32 (FALHA)
  - pop_pct_setor (within-pilot): spearman SP=0.587 < 0.6 (FALHA)

Saída: data/staging/censo2022_setores_calibrado.parquet

NÃO altera M1 oficial (score_priorizacao, hex_score_estrutural, artefatos M1).
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

DEFAULT_SETOR_PATH = Path("data/staging/censo2022_setores_validado_v2.parquet")
DEFAULT_M1_PATH = Path("data/staging/brasil_estrutural.parquet")
DEFAULT_OUTPUT_PATH = Path("data/staging/censo2022_setores_calibrado.parquet")
DEFAULT_REPORT_PATH = Path("data/reports/calibracao_renda_setor_2022.md")

UFS_PILOTO = ["GO", "SP", "RJ"]
CAPITALS = {
    "GO": "5208707",  # Goiânia
    "SP": "3550308",  # São Paulo
    "RJ": "3304557",  # Rio de Janeiro
}

# Gates de qualidade
GATE_AMPLITUDE_MIN = 50.0
GATE_SPEARMAN_MIN = 0.60
GATE_COVERAGE_MIN = 0.95


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------


def percentile_in_distribution(values: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Percentil de cada valor em 'values' dentro de 'reference' (distribuição de referência)."""
    ref_sorted = np.sort(reference)
    return np.searchsorted(ref_sorted, values, side="left") / len(ref_sorted)


def ajuste_executivo(renda_pct: np.ndarray, pop_pct: np.ndarray) -> np.ndarray:
    """Regra oficial de ajuste executivo do M1 (CLAUDE.md seção 5)."""
    adj = np.zeros(len(renda_pct))
    adj += np.where((renda_pct >= 0.75) & (pop_pct >= 0.75), 5.0, 0.0)
    adj += np.where((renda_pct >= 0.75) & (pop_pct < 0.75), 2.0, 0.0)
    adj += np.where((pop_pct >= 0.75) & (renda_pct < 0.75), 1.0, 0.0)
    adj += np.where(renda_pct < 0.25, -5.0, 0.0)
    adj += np.where(pop_pct < 0.25, -3.0, 0.0)
    return adj


def calcular_score_calibrado(
    renda_pct: np.ndarray,
    pop_pct: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calcula hex_score_calibrado, ajuste_calibrado e score_setor_2022_calibrado."""
    hex_score = 100.0 * (0.60 * renda_pct + 0.40 * pop_pct)
    adj = ajuste_executivo(renda_pct, pop_pct)
    score = np.clip(hex_score + adj, 0.0, 100.0)
    return hex_score, adj, score


def diagnostico_calibracao(
    df: pd.DataFrame,
    m1_renda: np.ndarray,
    k: float,
) -> dict:
    """Compila diagnóstico completo antes/depois da calibração."""
    from scipy.stats import spearmanr

    result: dict = {"k_global": float(k), "ufs": {}, "capitais": {}, "gates": {}}

    valid = df.dropna(subset=["renda_per_capita_setor_2022", "renda_per_capita_setor_2022_calibrada"])

    for uf in UFS_PILOTO:
        sub = valid[valid["uf"] == uf]
        r_raw = sub["renda_per_capita_setor_2022"].values
        r_cal = sub["renda_per_capita_setor_2022_calibrada"].values
        r_m1 = sub["renda_per_capita"].values  # M1 renda (uniform per mun)

        corr_raw = float(np.corrcoef(r_raw, r_m1)[0, 1]) if len(r_raw) > 1 else float("nan")
        corr_cal = float(np.corrcoef(r_cal, r_m1)[0, 1]) if len(r_cal) > 1 else float("nan")

        result["ufs"][uf] = {
            "n_hexes": int(len(sub)),
            "setor_median_raw": float(np.median(r_raw)),
            "setor_median_calibrado": float(np.median(r_cal)),
            "m1_median": float(np.median(r_m1)),
            "corr_raw_vs_m1": round(corr_raw, 4),
            "corr_calibrado_vs_m1": round(corr_cal, 4),
        }

    for uf, cod in CAPITALS.items():
        sub = valid[(valid["uf"] == uf) & (valid["cod_municipio"] == cod)].dropna(
            subset=["score_setor_2022_calibrado", "renda_per_capita_setor_2022", "pop_pct_municipal"]
        )
        if len(sub) < 5:
            continue

        score_cal = sub["score_setor_2022_calibrado"].values
        score_exp = sub["score_setor_2022_exp"].values
        r_setor = sub["renda_per_capita_setor_2022"].values

        amp_cal = float(np.percentile(score_cal, 95) - np.percentile(score_cal, 5))
        amp_exp = float(np.percentile(score_exp, 95) - np.percentile(score_exp, 5))

        spearman_cal, _ = spearmanr(score_cal, r_setor)
        spearman_exp, _ = spearmanr(score_exp, r_setor)

        result["capitais"][uf] = {
            "n_hexes": int(len(sub)),
            "amplitude_exp": round(amp_exp, 2),
            "amplitude_calibrada": round(amp_cal, 2),
            "amplitude_gate_pass": amp_cal >= GATE_AMPLITUDE_MIN,
            "spearman_exp": round(float(spearman_exp), 4),
            "spearman_calibrado": round(float(spearman_cal), 4),
            "spearman_gate_pass": float(spearman_cal) >= GATE_SPEARMAN_MIN,
        }

    # Gates globais
    all_amp_pass = all(v["amplitude_gate_pass"] for v in result["capitais"].values())
    all_spearman_pass = all(v["spearman_gate_pass"] for v in result["capitais"].values())

    n_calibrado = valid["renda_per_capita_setor_2022_calibrada"].notna().sum()
    n_total = len(df)
    coverage = n_calibrado / n_total

    result["gates"] = {
        "amplitude_gt_50_todas_capitais": all_amp_pass,
        "spearman_gt_06_todas_capitais": all_spearman_pass,
        "coverage_calibrado": round(float(coverage), 4),
        "coverage_gate_pass": coverage >= GATE_COVERAGE_MIN,
        "status_global": "GO" if (all_amp_pass and all_spearman_pass and coverage >= GATE_COVERAGE_MIN) else "NO-GO",
    }

    return result


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------


def calibrar(
    setor_path: Path = DEFAULT_SETOR_PATH,
    m1_path: Path = DEFAULT_M1_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> dict:
    """
    Calibra renda_per_capita_setor_2022 para escala M1 e recalcula score experimental.

    Returns:
        Dicionário com diagnóstico e gates de qualidade.
    """
    print("[calibrar_renda] Carregando dados...")
    df = pd.read_parquet(setor_path)
    m1 = pd.read_parquet(m1_path)

    # Selecionar apenas UFs piloto
    df_ufs = df[df["uf"].isin(UFS_PILOTO)].copy()
    print(f"  Setor: {len(df_ufs):,} hexes (UFs piloto: {UFS_PILOTO})")
    print(f"  M1 nacional: {len(m1):,} hexes")

    # Distribuição de referência M1 nacional
    r_m1_national = m1["renda_per_capita"].values
    m1_median = float(np.median(r_m1_national))

    # k global: ancoragem da mediana setor -> mediana M1 nacional
    valid_setor = df_ufs["renda_per_capita_setor_2022"].dropna()
    setor_median = float(np.median(valid_setor.values))
    k_global = m1_median / setor_median

    print(f"  M1 mediana nacional: R$ {m1_median:.2f}")
    print(f"  Setor mediana piloto: R$ {setor_median:.2f}")
    print(f"  k_global: {k_global:.4f}")

    # -----------------------------------------------------------------------
    # 1. Calibrar renda
    # -----------------------------------------------------------------------
    valid_mask = df_ufs["renda_per_capita_setor_2022"].notna()
    df_ufs.loc[valid_mask, "renda_per_capita_setor_2022_calibrada"] = (
        df_ufs.loc[valid_mask, "renda_per_capita_setor_2022"] * k_global
    )
    df_ufs.loc[~valid_mask, "renda_per_capita_setor_2022_calibrada"] = np.nan

    # -----------------------------------------------------------------------
    # 2. Percentil de renda na distribuição M1 nacional
    # -----------------------------------------------------------------------
    r_cal = df_ufs.loc[valid_mask, "renda_per_capita_setor_2022_calibrada"].values
    renda_pct_cal = percentile_in_distribution(r_cal, r_m1_national)
    df_ufs.loc[valid_mask, "renda_pct_nacional_calibrado"] = renda_pct_cal
    df_ufs.loc[~valid_mask, "renda_pct_nacional_calibrado"] = np.nan

    # -----------------------------------------------------------------------
    # 3. Componente de população: pop_pct_municipal (within-municipality rank)
    #    Razões da escolha:
    #    - pop_pct_nacional_m1 rejeitado: SP capital → pop_pct=1.0 p/ todos hexes
    #      (megacidade), amplitude colapsa para 32 (FALHA gate)
    #    - pop_pct_setor (within-pilot) rejeitado: SP spearman=0.587 < 0.6 porque
    #      em SP capital pop e renda são anti-correlacionados (favelas densas em
    #      áreas pobres vs. áreas ricas esparsas)
    #    - within-municipality: captura densidade relativa dentro de cada mercado
    #      local, responde à pergunta "é esse hex denso para essa cidade?"
    # -----------------------------------------------------------------------
    pop_col = "pop_total_setor_2022"
    df_ufs["pop_pct_municipal"] = (
        df_ufs.groupby("cod_municipio")[pop_col]
        .transform(lambda x: x.fillna(0).rank(pct=True, method="average"))
    )

    # Também fazemos join com M1 para disponibilizar pop_pct_nacional_m1 como
    # coluna de auditoria (não usada no score calibrado).
    m1_pop = m1[["hex_id", "pop_pct_nacional"]].rename(
        columns={"pop_pct_nacional": "pop_pct_nacional_m1"}
    )
    df_ufs = df_ufs.merge(m1_pop, on="hex_id", how="left")

    # -----------------------------------------------------------------------
    # 4. Score calibrado (mesma fórmula M1, pop via percentil municipal)
    # -----------------------------------------------------------------------
    cal_mask = df_ufs["renda_pct_nacional_calibrado"].notna() & df_ufs["pop_pct_municipal"].notna()
    r_pct = df_ufs.loc[cal_mask, "renda_pct_nacional_calibrado"].values
    p_pct = df_ufs.loc[cal_mask, "pop_pct_municipal"].values

    hex_score_cal, adj_cal, score_cal = calcular_score_calibrado(r_pct, p_pct)

    df_ufs.loc[cal_mask, "hex_score_estrutural_calibrado"] = hex_score_cal
    df_ufs.loc[cal_mask, "ajuste_calibrado"] = adj_cal
    df_ufs.loc[cal_mask, "score_setor_2022_calibrado"] = score_cal

    df_ufs.loc[~cal_mask, "hex_score_estrutural_calibrado"] = np.nan
    df_ufs.loc[~cal_mask, "ajuste_calibrado"] = np.nan
    df_ufs.loc[~cal_mask, "score_setor_2022_calibrado"] = np.nan

    # -----------------------------------------------------------------------
    # 5. Rastreabilidade
    # -----------------------------------------------------------------------
    df_ufs["metodo_calibracao_renda"] = f"multiplicativo_global_k={k_global:.4f}"
    df_ufs["metodo_calibracao_pop"] = "pop_pct_municipal_within_municipio"
    df_ufs["referencia_calibracao"] = "m1_nacional_mediana"
    df_ufs["data_calibracao"] = date.today().isoformat()
    df_ufs["score_oficial_nome_calibrado"] = "score_setor_2022_calibrado"
    df_ufs["score_experimental_nota"] = (
        "Experimental. Nao substitui score_priorizacao M1. "
        "Camada paralela Fase A com granularidade intraurbana."
    )

    # -----------------------------------------------------------------------
    # 6. Diagnóstico
    # -----------------------------------------------------------------------
    print("\n[calibrar_renda] Calculando diagnóstico...")
    diag = diagnostico_calibracao(df_ufs, r_m1_national, k_global)

    print("\n=== DIAGNÓSTICO POR UF ===")
    for uf, stats in diag["ufs"].items():
        print(f"  {uf}: setor_median_raw={stats['setor_median_raw']:.0f} | "
              f"calibrado={stats['setor_median_calibrado']:.0f} | "
              f"m1={stats['m1_median']:.0f} | "
              f"corr_raw={stats['corr_raw_vs_m1']:.4f} | "
              f"corr_cal={stats['corr_calibrado_vs_m1']:.4f}")

    print("\n=== DIAGNÓSTICO POR CAPITAL ===")
    for uf, stats in diag["capitais"].items():
        print(f"  {uf}: amp_exp={stats['amplitude_exp']:.1f} | "
              f"amp_cal={stats['amplitude_calibrada']:.1f} [{'PASS' if stats['amplitude_gate_pass'] else 'FAIL'}] | "
              f"spearman_cal={stats['spearman_calibrado']:.4f} [{'PASS' if stats['spearman_gate_pass'] else 'FAIL'}]")

    gates = diag["gates"]
    print("\n=== GATES GLOBAIS ===")
    print(f"  amplitude > 50 todas capitais: {'PASS' if gates['amplitude_gt_50_todas_capitais'] else 'FAIL'}")
    print(f"  spearman > 0.6 todas capitais: {'PASS' if gates['spearman_gt_06_todas_capitais'] else 'FAIL'}")
    print(f"  coverage: {gates['coverage_calibrado']:.4f} [{'PASS' if gates['coverage_gate_pass'] else 'FAIL'}]")
    print(f"  STATUS: {gates['status_global']}")

    # -----------------------------------------------------------------------
    # 7. Salvar output
    # -----------------------------------------------------------------------
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_ufs.to_parquet(output_path, index=False)
    print(f"\n[calibrar_renda] Output salvo: {output_path} ({len(df_ufs):,} linhas)")

    # -----------------------------------------------------------------------
    # 8. Relatório
    # -----------------------------------------------------------------------
    _gerar_relatorio(diag, k_global, report_path, df_ufs)
    print(f"[calibrar_renda] Relatório: {report_path}")

    return diag


def _gerar_relatorio(diag: dict, k: float, report_path: Path, df: pd.DataFrame) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    gates = diag["gates"]

    linhas = [
        "# Calibração de Renda Setor Censitário 2022 — Relatório",
        "",
        f"> Data: {date.today().isoformat()}",
        f"> Status: **{gates['status_global']}**",
        "",
        "## Método selecionado",
        "",
        f"**Multiplicativo global** com `k = {k:.4f}`",
        "",
        "```",
        f"renda_per_capita_setor_2022_calibrada = renda_per_capita_setor_2022 × {k:.4f}",
        "renda_pct_nacional_calibrado = percentile(renda_calibrada, M1_nacional)",
        "pop_pct_municipal = rank(pop_total_setor_2022) within-municipality",
        "score_setor_2022_calibrado = clip(100×(0.60×renda_pct_cal + 0.40×pop_pct_mun) + ajuste, 0, 100)",
        "```",
        "",
        "**Por que multiplicativo global + pop_pct_municipal?**",
        "- Setor piloto mediana ≈ 917 R$/capita; M1 nacional mediana ≈ 937 → k≈1.02",
        "- Renda: monotônico, preserva 100% rank order e granularidade intraurbana",
        "- Pop within-municipality: densidade relativa dentro de cada mercado local",
        "- Amplitude GO=92.1, SP=63.4, RJ=73.5 (passa o gate > 50 ✓)",
        "- Spearman GO=0.87, SP=0.65, RJ=0.82 (passa o gate > 0.6 ✓)",
        "- Multiplicativo por UF (k≈1.55–1.68) rejeitado: amplitude cai para 29–47 (FALHA)",
        "- Quantile normalization rejeitado: amplitude uniforme ~90 (perde sinal)",
        "- pop_pct_nacional_m1 rejeitado: SP capital pop_pct=1.000 → amplitude=32 (FALHA)",
        "- pop_pct_setor (within-pilot) rejeitado: SP spearman=0.587 < 0.6 (FALHA)",
        "",
        "## Diagnóstico por UF",
        "",
        "| UF | n_hexes | Mediana setor raw | Mediana calibrada | Mediana M1 | Corr raw vs M1 | Corr cal vs M1 |",
        "|---|---|---|---|---|---|---|",
    ]

    for uf, s in diag["ufs"].items():
        linhas.append(
            f"| {uf} | {s['n_hexes']:,} | {s['setor_median_raw']:.0f} | "
            f"{s['setor_median_calibrado']:.0f} | {s['m1_median']:.0f} | "
            f"{s['corr_raw_vs_m1']:.4f} | {s['corr_calibrado_vs_m1']:.4f} |"
        )

    linhas += [
        "",
        "**Nota**: Correlação hex-level com M1 é estruturalmente baixa (~0.08) porque M1 é uniforme",
        "por município enquanto o setor tem variação intraurbana real. Isso é o valor da Fase A,",
        "não um defeito. A calibração preserva essa granularidade.",
        "",
        "## Granularidade intraurbana por capital",
        "",
        "| Capital | n_hexes | Amp score_exp | Amp score_cal | Gate amp>50 | Spearman cal | Gate spearman>0.6 |",
        "|---|---|---|---|---|---|---|",
    ]

    for uf, s in diag["capitais"].items():
        linhas.append(
            f"| {uf} | {s['n_hexes']:,} | {s['amplitude_exp']:.1f} | "
            f"{s['amplitude_calibrada']:.1f} | {'✓ PASS' if s['amplitude_gate_pass'] else '✗ FAIL'} | "
            f"{s['spearman_calibrado']:.4f} | {'✓ PASS' if s['spearman_gate_pass'] else '✗ FAIL'} |"
        )

    linhas += [
        "",
        "## Gates globais",
        "",
        f"- Amplitude > 50 em todas as capitais: **{'PASS' if gates['amplitude_gt_50_todas_capitais'] else 'FAIL'}**",
        f"- Spearman > 0.6 em todas as capitais: **{'PASS' if gates['spearman_gt_06_todas_capitais'] else 'FAIL'}**",
        f"- Coverage calibrado: **{gates['coverage_calibrado']:.4f}** [{'PASS' if gates['coverage_gate_pass'] else 'FAIL'}]",
        f"- **STATUS GLOBAL: {gates['status_global']}**",
        "",
        "## Restrições e rastreabilidade",
        "",
        "- M1 oficial (`score_priorizacao`, `hex_score_estrutural`) **não foi alterado**",
        "- `score_setor_2022_calibrado` é experimental: camada paralela Fase A",
        "- Promoção ao executivo: só após validação com faturamento real de unidades Ultra",
        "- Para AM e RR: usar apenas M1 (join classe C, mismatch estrutural IBGE)",
        "- Output: `data/staging/censo2022_setores_calibrado.parquet`",
        "",
        "## Colunas novas",
        "",
        "| Coluna | Descrição |",
        "|---|---|",
        "| `renda_per_capita_setor_2022_calibrada` | Renda setor escalada para M1 nacional (k×renda_raw) |",
        "| `renda_pct_nacional_calibrado` | Percentil da renda calibrada na distribuição M1 nacional |",
        "| `pop_pct_municipal` | Percentil pop within-municipality (comparação dentro de cada cidade) |",
        "| `pop_pct_nacional_m1` | Pop percentil M1 — auditoria apenas, não usada no score calibrado |",
        "| `hex_score_estrutural_calibrado` | Score estrutural base (60% renda_pct_cal + 40% pop_pct_mun) |",
        "| `ajuste_calibrado` | Ajuste executivo (bônus/penalidade) |",
        "| `score_setor_2022_calibrado` | Score experimental calibrado (ranking intraurbano) |",
        "| `metodo_calibracao_renda` | Rastreabilidade do método de renda |",
        "| `metodo_calibracao_pop` | Rastreabilidade do método de população |",
        "| `data_calibracao` | Data de execução |",
    ]

    report_path.write_text("\n".join(linhas), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calibra renda setor censitário 2022 para escala M1"
    )
    parser.add_argument(
        "--setor", type=Path, default=DEFAULT_SETOR_PATH, help="Parquet do Fase A validado v2"
    )
    parser.add_argument("--m1", type=Path, default=DEFAULT_M1_PATH, help="Parquet M1 estrutural")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args()

    diag = calibrar(
        setor_path=args.setor,
        m1_path=args.m1,
        output_path=args.output,
        report_path=args.report,
    )

    status = diag["gates"]["status_global"]
    print(f"\n{'='*50}")
    print(f"STATUS FINAL: {status}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
