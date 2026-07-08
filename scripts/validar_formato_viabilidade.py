"""Validacao out-of-fold do filtro por formato na curva tamanho->densidade (BLK-VIAB-07).

DEC-008 honrada: k-fold 5x5 (seed=42) vs baseline da media; R2 in-sample BANIDO;
IC95 por bootstrap; NO-GO e resultado valido. DEC-009: alvo = alunos REAIS.
READ-ONLY sobre o M1. Sem rede, sem escrita em artefato M1.

Uso:
    python scripts/validar_formato_viabilidade.py
Saida:
    data/analysis/relatorio_formato_densidade.md (gitignored)
    + veredito GO/NO-GO no stdout (exit 0 sempre; o veredito e conteudo, nao status).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from motor_expansao.dimensionamento.viabilidade_ponto import (
    FORMATO_LOW_COST_MASSA,
    FORMATO_POR_MARCA,
    faixa_alunos_por_densidade,
)

ROOT = Path(__file__).resolve().parents[1]
BASE_PARQUET = ROOT / "data" / "staging" / "base_calibracao_multirede.parquet"
RELATORIO = ROOT / "data" / "analysis" / "relatorio_formato_densidade.md"

SEED = 42
N_REPS = 5
N_FOLDS = 5
N_BOOT = 2000
GANHO_MIN_PP = 1.0  # ganho minimo de MAPE (p.p.) para GO


def carregar_base() -> pd.DataFrame:
    """Le a base multirede, deriva formato + alunos_por_m2, mantem linhas uteis."""
    df = pd.read_parquet(BASE_PARQUET)
    df = df.copy()
    df["formato"] = df["marca"].astype("string").map(FORMATO_POR_MARCA)
    df["metragem"] = pd.to_numeric(df["metragem"], errors="coerce")
    df["alunos_reais"] = pd.to_numeric(df["alunos_reais"], errors="coerce")
    mask = (
        df["metragem"].notna()
        & (df["metragem"] > 0)
        & df["alunos_reais"].notna()
        & (df["alunos_reais"] > 0)
    )
    df = df[mask].copy()
    df["alunos_por_m2"] = df["alunos_reais"] / df["metragem"]
    return df.reset_index(drop=True)


def _kfold_indices(n: int, n_folds: int, rng: np.random.Generator) -> list[np.ndarray]:
    idx = np.arange(n)
    rng.shuffle(idx)
    return list(np.array_split(idx, n_folds))


def erros_oof(
    df_alvo: pd.DataFrame,
    base_comparaveis: pd.DataFrame,
    *,
    formato: str | None,
) -> np.ndarray:
    """MAPE por unidade de teste, out-of-fold, sobre df_alvo.

    O treino de cada fold e (base_comparaveis) MENOS as linhas do fold de teste
    (removidas por indice de df_alvo). Predicao = p50 da faixa * m2_teste.
    """
    rng = np.random.default_rng(SEED)
    n = len(df_alvo)
    erros: list[float] = []
    for _rep in range(N_REPS):
        folds = _kfold_indices(n, N_FOLDS, rng)
        for fold in folds:
            teste = df_alvo.iloc[fold]
            # treino = base_comparaveis sem as unidades de teste (por 'unidade')
            unidades_teste = set(teste["unidade"])
            treino = base_comparaveis[~base_comparaveis["unidade"].isin(unidades_teste)]
            for _, row in teste.iterrows():
                out = faixa_alunos_por_densidade(
                    float(row["metragem"]), treino, formato=formato
                )
                p50 = out["faixa_alunos_p50"]
                if p50 is None:
                    continue
                real = float(row["alunos_reais"])
                erros.append(abs(p50 - real) / real)
    return np.asarray(erros, dtype=float)


def erros_baseline_media(df_alvo: pd.DataFrame, base: pd.DataFrame) -> np.ndarray:
    """Baseline: prediz a MEDIA de alunos_reais do treino (por fold), oof."""
    rng = np.random.default_rng(SEED)
    n = len(df_alvo)
    erros: list[float] = []
    for _rep in range(N_REPS):
        folds = _kfold_indices(n, N_FOLDS, rng)
        for fold in folds:
            teste = df_alvo.iloc[fold]
            unidades_teste = set(teste["unidade"])
            treino = base[~base["unidade"].isin(unidades_teste)]
            pred = float(treino["alunos_reais"].mean())
            for _, row in teste.iterrows():
                real = float(row["alunos_reais"])
                erros.append(abs(pred - real) / real)
    return np.asarray(erros, dtype=float)


def ic95_mape(erros: np.ndarray, rng: np.random.Generator) -> tuple[float, float, float]:
    """MAPE (%) + IC95 bootstrap (percentil 2.5/97.5)."""
    mape = float(np.mean(erros) * 100.0)
    boot = np.array(
        [np.mean(rng.choice(erros, size=len(erros), replace=True)) for _ in range(N_BOOT)]
    ) * 100.0
    return mape, float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))


def ic95_delta(erros_sem: np.ndarray, erros_com: np.ndarray) -> tuple[float, float, float]:
    """Delta = MAPE_sem - MAPE_com (positivo = filtro melhora). IC95 pareado por fold-unit.

    Como erros_sem/erros_com sao pareados por unidade (mesma ordem de iteracao),
    reamostramos os PARES para o IC do ganho.
    """
    rng = np.random.default_rng(SEED)
    n = min(len(erros_sem), erros_com.shape[0])
    a = erros_sem[:n]
    b = erros_com[:n]
    delta = float((np.mean(a) - np.mean(b)) * 100.0)
    boot = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, n, size=n)
        boot.append((np.mean(a[idx]) - np.mean(b[idx])) * 100.0)
    boot_arr = np.asarray(boot)
    return delta, float(np.percentile(boot_arr, 2.5)), float(np.percentile(boot_arr, 97.5))


def main() -> None:
    df = carregar_base()
    # Alvo de validacao = unidades Ultra (formato low_cost_massa homogeneo).
    df_ultra = df[df["formato"] == FORMATO_LOW_COST_MASSA].reset_index(drop=True)
    # Base de comparaveis MISTA (Ultra + EngCorpo): so aqui o filtro de formato importa.
    base_mista = df.reset_index(drop=True)

    rng = np.random.default_rng(SEED)

    err_base = erros_baseline_media(df_ultra, base_mista)
    err_sem = erros_oof(df_ultra, base_mista, formato=None)
    err_com = erros_oof(df_ultra, base_mista, formato=FORMATO_LOW_COST_MASSA)

    mape_base, base_lo, base_hi = ic95_mape(err_base, rng)
    mape_sem, sem_lo, sem_hi = ic95_mape(err_sem, rng)
    mape_com, com_lo, com_hi = ic95_mape(err_com, rng)
    delta, d_lo, d_hi = ic95_delta(err_sem, err_com)

    ganho_suficiente = delta >= GANHO_MIN_PP
    ic_nao_cruza = d_lo > 0.0
    bate_baseline = mape_com < mape_base
    veredito = "GO" if (ganho_suficiente and ic_nao_cruza and bate_baseline) else "NO-GO"

    RELATORIO.parent.mkdir(parents=True, exist_ok=True)
    linhas = [
        "# Relatorio — Curva de densidade por formato (BLK-VIAB-07)",
        "",
        "Validacao out-of-fold (DEC-008): k-fold 5x5, seed=42, IC95 bootstrap.",
        "Alvo (DEC-009): `alunos_reais`. Base de comparaveis: Ultra + Engenharia do Corpo (mista).",
        f"Unidades de teste: Ultra (N={len(df_ultra)}). R2 in-sample BANIDO.",
        "",
        "## MAPE out-of-fold",
        "",
        "| Cenario | MAPE (%) | IC95 |",
        "|---|---|---|",
        f"| (a) baseline media | {mape_base:.2f} | [{base_lo:.2f}, {base_hi:.2f}] |",
        f"| (b) sem filtro de formato | {mape_sem:.2f} | [{sem_lo:.2f}, {sem_hi:.2f}] |",
        f"| (c) formato=low_cost_massa | {mape_com:.2f} | [{com_lo:.2f}, {com_hi:.2f}] |",
        "",
        "## Ganho do filtro (b - c)",
        "",
        f"- Delta MAPE = **{delta:.2f} p.p.** (positivo = filtro melhora)",
        f"- IC95 do delta = [{d_lo:.2f}, {d_hi:.2f}]",
        f"- Ganho >= {GANHO_MIN_PP:.1f} p.p.? {ganho_suficiente}",
        f"- IC nao cruza zero? {ic_nao_cruza}",
        f"- Bate baseline da media? {bate_baseline}",
        "",
        f"## Veredito: **{veredito}**",
        "",
        "GO => expor `formato` em `analisar_viabilidade_ponto` e documentar.",
        "NO-GO => nao expor (utility interna); resultado honesto (DEC-008).",
    ]
    RELATORIO.write_text("\n".join(linhas) + "\n", encoding="utf-8")

    print(f"[BLK-VIAB-07] veredito={veredito} "
          f"MAPE sem={mape_sem:.2f}% com={mape_com:.2f}% delta={delta:.2f}pp "
          f"IC_delta=[{d_lo:.2f},{d_hi:.2f}] baseline={mape_base:.2f}%")
    print(f"Relatorio: {RELATORIO}")


if __name__ == "__main__":
    main()
