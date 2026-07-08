"""Faixa de demanda-premissa por tier de metragem (BLK-VIAB-02).

Combina comparaveis reais (Ultra + Eng Corpo) em 5 tiers de metragem e calcula
p10/p50/p90 de alunos por tier. Materializa em staging e gera relatorio de qualidade.

GUARDRAIL DEC-009:
    - Alvo = alunos REAIS observados (Ultra: alunos_total; Eng Corpo: Alunos Totais).
    - PROIBIDO usar membros/agregadores corporativos ou qualquer preditor geografico
      (lat, lng, hex_id) como alvo de demanda.

READ-ONLY sobre o M1: nao recalcula score_priorizacao, hex_score_estrutural, pesos,
carteira, plano nem artefatos oficiais (DEC-001/DEC-008/DEC-009).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constantes publicas
# ---------------------------------------------------------------------------

VERSAO_CONTRATO: str = "demanda_premissa_v1"
N_EXTRAPOLACAO_MIN: int = 5  # N < 5 -> flag_extrapolacao = True

TIERS: list[dict[str, Any]] = [
    {"tier_label": "<1000", "metragem_min": 0.0, "metragem_max": 999.9},
    {"tier_label": "1000-1499", "metragem_min": 1000.0, "metragem_max": 1499.9},
    {"tier_label": "1500-1999", "metragem_min": 1500.0, "metragem_max": 1999.9},
    {"tier_label": "2000-2999", "metragem_min": 2000.0, "metragem_max": 2999.9},
    {"tier_label": ">=3000", "metragem_min": 3000.0, "metragem_max": float("inf")},
]

# ---------------------------------------------------------------------------
# Funcoes privadas
# ---------------------------------------------------------------------------


def _assign_tier(metragem: float) -> str:
    """Retorna o tier_label correspondente para uma metragem dada."""
    if metragem < 1000.0:
        return "<1000"
    elif metragem < 1500.0:
        return "1000-1499"
    elif metragem < 2000.0:
        return "1500-1999"
    elif metragem < 3000.0:
        return "2000-2999"
    else:
        return ">=3000"


# ---------------------------------------------------------------------------
# Funcoes publicas
# ---------------------------------------------------------------------------


def carregar_ultra(path: Path | str) -> pd.DataFrame:
    """Carrega comparaveis da Ultra a partir do parquet de performance.

    Args:
        path: Caminho para `unidades_ultra_performance_hex.parquet`.

    Returns:
        DataFrame com colunas ['metragem', 'alunos'] (float), linhas validas (>0, sem NaN).
        Nenhuma coluna de PII (nome, lat, lng, hex_id) e propagada.
    """
    df = pd.read_parquet(Path(path))
    df = df[["metragem", "alunos_total"]].copy()
    df = df.rename(columns={"alunos_total": "alunos"})
    df = df.astype({"metragem": float, "alunos": float})
    df = df.dropna(subset=["metragem", "alunos"])
    df = df[(df["metragem"] > 0) & (df["alunos"] > 0)]
    return df[["metragem", "alunos"]].reset_index(drop=True)


def carregar_eng_corpo(path: Path | str) -> pd.DataFrame:
    """Carrega comparaveis da Engenharia do Corpo a partir do xlsx de validacao.

    Args:
        path: Caminho para `academias_engenharia_do_corpo.xlsx`.

    Returns:
        DataFrame com colunas ['metragem', 'alunos'] (float), linhas validas (>0, sem NaN).
        Nenhuma coluna de PII (nome, endereco) e propagada.
    """
    df = pd.read_excel(Path(path), engine="openpyxl")
    df = df[["Metragem M²", "Alunos Totais"]].copy()
    df = df.rename(columns={"Metragem M²": "metragem", "Alunos Totais": "alunos"})
    df = df.astype({"metragem": float, "alunos": float})
    df = df.dropna(subset=["metragem", "alunos"])
    df = df[(df["metragem"] > 0) & (df["alunos"] > 0)]
    return df[["metragem", "alunos"]].reset_index(drop=True)


def combinar_bases(ultra_df: pd.DataFrame, eng_df: pd.DataFrame) -> pd.DataFrame:
    """Combina os DataFrames de Ultra e Eng Corpo em uma base unica.

    Args:
        ultra_df: DataFrame com colunas ['metragem', 'alunos'].
        eng_df: DataFrame com colunas ['metragem', 'alunos'].

    Returns:
        DataFrame concatenado com colunas ['metragem', 'alunos'], sem NaN e valores <= 0.
    """
    for name, df in [("ultra_df", ultra_df), ("eng_df", eng_df)]:
        missing = [c for c in ["metragem", "alunos"] if c not in df.columns]
        if missing:
            raise ValueError(f"{name} nao tem colunas: {missing}")

    combined = pd.concat(
        [ultra_df[["metragem", "alunos"]], eng_df[["metragem", "alunos"]]],
        ignore_index=True,
    )
    combined = combined.dropna(subset=["metragem", "alunos"])
    combined = combined[(combined["metragem"] > 0) & (combined["alunos"] > 0)]
    return combined[["metragem", "alunos"]].reset_index(drop=True)


def calcular_tiers(
    df: pd.DataFrame,
    *,
    n_extrapolacao_min: int = N_EXTRAPOLACAO_MIN,
) -> pd.DataFrame:
    """Calcula p10/p50/p90 de alunos por tier de metragem.

    Args:
        df: DataFrame com colunas ['metragem', 'alunos'].
        n_extrapolacao_min: Limiar de N abaixo do qual flag_extrapolacao=True.

    Returns:
        DataFrame com 5 linhas (uma por tier) e colunas:
        ['tier_label', 'metragem_min', 'metragem_max', 'n', 'p10', 'p50', 'p90',
         'flag_extrapolacao', 'versao_contrato']
    """
    missing = [c for c in ["metragem", "alunos"] if c not in df.columns]
    if missing:
        raise ValueError(f"df nao tem colunas: {missing}")

    df_work = df[["metragem", "alunos"]].copy()
    df_work["tier_label"] = df_work["metragem"].map(_assign_tier)

    rows = []
    for tier in TIERS:
        label = tier["tier_label"]
        sub = df_work[df_work["tier_label"] == label]
        n = len(sub)
        if n == 0:
            p10, p50, p90 = float("nan"), float("nan"), float("nan")
        else:
            arr = sub["alunos"].to_numpy(dtype=float)
            p10, p50, p90 = np.percentile(arr, [10, 50, 90])
        rows.append(
            {
                "tier_label": label,
                "metragem_min": float(tier["metragem_min"]),
                "metragem_max": float(tier["metragem_max"]),
                "n": int(n),
                "p10": float(p10),
                "p50": float(p50),
                "p90": float(p90),
                "flag_extrapolacao": bool(n < n_extrapolacao_min),
                "versao_contrato": VERSAO_CONTRATO,
            }
        )

    result = pd.DataFrame(rows)
    result = result.astype(
        {
            "tier_label": str,
            "metragem_min": "float64",
            "metragem_max": "float64",
            "n": "int64",
            "p10": "float64",
            "p50": "float64",
            "p90": "float64",
            "flag_extrapolacao": bool,
            "versao_contrato": str,
        }
    )
    return result


def materializar(
    df_tiers: pd.DataFrame,
    staging_dir: Path | str,
    analysis_dir: Path | str,
) -> tuple[Path, Path]:
    """Persiste o DataFrame de tiers em parquet e gera relatorio de qualidade em markdown.

    Args:
        df_tiers: DataFrame de 5 linhas retornado por calcular_tiers.
        staging_dir: Diretorio de staging (ex.: data/staging/).
        analysis_dir: Diretorio de analise (ex.: data/analysis/).

    Returns:
        Tupla (parquet_path, md_path).
    """
    staging_dir = Path(staging_dir)
    analysis_dir = Path(analysis_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = staging_dir / "demanda_premissa_por_tier.parquet"
    df_tiers.to_parquet(parquet_path, index=False)

    # Gera relatorio de qualidade
    md_lines = [
        "# Relatorio de Qualidade - Faixa de Demanda-Premissa por Tier (BLK-VIAB-02)",
        "",
        f"Data de geracao: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"Versao do contrato: `{VERSAO_CONTRATO}`",
        "",
        "## Tabela de tiers",
        "",
        "| Tier (m²) | N | p10 (alunos) | p50 (alunos) | p90 (alunos) | flag_extrapolacao |",
        "|---|---|---|---|---|---|",
    ]

    for _, row in df_tiers.iterrows():
        p10_str = f"{row['p10']:.0f}" if not np.isnan(row["p10"]) else "n/a"
        p50_str = f"{row['p50']:.0f}" if not np.isnan(row["p50"]) else "n/a"
        p90_str = f"{row['p90']:.0f}" if not np.isnan(row["p90"]) else "n/a"
        flag_str = "True" if row["flag_extrapolacao"] else "False"
        md_lines.append(
            f"| {row['tier_label']} | {row['n']} | {p10_str} | {p50_str} | {p90_str} | {flag_str} |"
        )

    md_lines += [
        "",
        "## Caveats e Alertas",
        "",
        "**ALERTA - Tier >= 3.000 m²: N=2 (flag_extrapolacao=True).**"
        " Os percentis neste tier sao instaveis (baseados em apenas 2 academias Eng Corpo)."
        " Usar com cautela; o VIAB-03 deve exibir aviso explicito quando o candidato cair neste tier.",
        "",
        "**ALERTA - Discrepancia com o backlog:** o backlog BLK-VIAB-02 citava"
        " \"~1.100 academias REAIS\". A inspecao real das fontes disponiveis revelou"
        " **N=112 unidades** (Ultra 54 + Eng Corpo 58). Smart Fit e Sky Fit nao possuem"
        " coluna de metragem em nenhuma fonte disponivel (apenas alunos totais).",
        "",
        "**Nota - Eng Corpo inclui academias acima de 3.500 m²:**"
        " porte muito diferente da Ultra (max. ~2.800 m²)."
        " As observacoes do tier >= 3.000 m² sao integralmente Eng Corpo."
        " O modulo nao filtra por rede (usa os dados como comparaveis de capacidade),"
        " mas o consumidor deve ter ciencia desse contexto.",
        "",
        "**Fontes:** Ultra = `data/staging/unidades_ultra_performance_hex.parquet`"
        " (coluna `alunos_total`);"
        " Eng Corpo = `data/validacao/academias_engenharia_do_corpo.xlsx`"
        " (coluna `Alunos Totais`)."
        " Alvo = alunos REAIS (DEC-009)."
        " PROIBIDO usar `membros`/agregadores corporativos ou qualquer preditor geografico como alvo.",
    ]

    md_path = analysis_dir / "demanda_premissa_qualidade.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    return parquet_path, md_path


def run(
    ultra_path: Path | str,
    eng_path: Path | str,
    staging_dir: Path | str,
    analysis_dir: Path | str,
) -> tuple[Path, Path]:
    """Pipeline completo: carrega, combina, calcula tiers e materializa.

    Args:
        ultra_path: Caminho para `unidades_ultra_performance_hex.parquet`.
        eng_path: Caminho para `academias_engenharia_do_corpo.xlsx`.
        staging_dir: Diretorio de staging.
        analysis_dir: Diretorio de analise.

    Returns:
        Tupla (parquet_path, md_path) dos artefatos gerados.
    """
    ultra_df = carregar_ultra(ultra_path)
    eng_df = carregar_eng_corpo(eng_path)
    combined = combinar_bases(ultra_df, eng_df)
    df_tiers = calcular_tiers(combined)
    return materializar(df_tiers, staging_dir, analysis_dir)


__all__ = [
    "carregar_ultra",
    "carregar_eng_corpo",
    "combinar_bases",
    "calcular_tiers",
    "materializar",
    "run",
    "VERSAO_CONTRATO",
    "TIERS",
    "N_EXTRAPOLACAO_MIN",
]


if __name__ == "__main__":
    from pathlib import Path as _Path

    _repo = _Path(__file__).resolve().parents[3]
    _ultra = _repo / "data" / "staging" / "unidades_ultra_performance_hex.parquet"
    _eng = _repo / "data" / "validacao" / "academias_engenharia_do_corpo.xlsx"
    _staging = _repo / "data" / "staging"
    _analysis = _repo / "data" / "analysis"

    _parquet, _md = run(_ultra, _eng, _staging, _analysis)
    print(f"Parquet: {_parquet}")
    print(f"Relatorio: {_md}")

    _df = pd.read_parquet(_parquet)
    print("\nTiers gerados:")
    print(_df.to_string(index=False))
