"""Batch de viabilidade sobre candidatos limpos, em modo coordless (BLK-VIAB-03).

Roda `analisar_viabilidade_ponto` (modo COORDLESS, `setores_df=None`) sobre os
candidatos limpos do BLK-VIAB-01, mapeando cada imovel ao tier de demanda-premissa
do BLK-VIAB-02 (p10/p50/p90) pela metragem, e materializa um parquet + relatorio
`.md` ranqueado por margem de seguranca.

GUARDRAIL DEC-009:
    - A demanda entra SO como PREMISSA EXPLICITA (faixa p10/p50/p90 do tier de
      metragem), NUNCA prevista por lat/lng. `demanda_fonte` = "premissa_explicita".
    - Modo COORDLESS: `setores_df=None` -> sem catchment, sem rede, sem fetch HTTP.
      lat/lng dos candidatos sao NaN e NAO influenciam a demanda.

READ-ONLY sobre o M1: nao recalcula score_priorizacao, hex_score_estrutural, pesos,
carteira, plano nem artefatos oficiais (DEC-001/DEC-008/DEC-009).
`viabilidade_ponto.py` INTOCADO (reusado sem modificar).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from motor_expansao.dimensionamento.demanda_premissa import _assign_tier
from motor_expansao.dimensionamento.viabilidade_ponto import (
    analisar_viabilidade_ponto,
)

# ---------------------------------------------------------------------------
# Constantes publicas
# ---------------------------------------------------------------------------

VERSAO_CONTRATO: str = "viabilidade_candidatos_v1"

# Placeholders ecoados (modo coordless; o catchment nao usa lat/lng quando
# setores_df=None). NAO sao persistidos como coluna de saida.
LAT_COORDLESS: float = 0.0
LNG_COORDLESS: float = 0.0

# Colunas geo/PII que NUNCA entram no parquet de saida.
COLUNAS_GEO_EXCLUIR: list[str] = [
    "LATITUDE",
    "LONGITUDE",
    "LOGRADOURO",
    "CEP",
    "BAIRRO",
    "NÚMERO",
    "COMPLEMENTO",
]

# Ordem fixa das colunas do parquet de saida.
COLUNAS_SAIDA: list[str] = [
    "ID",
    "NOME",
    "ÁREA",
    "ALUGUEL",
    "CIDADE",
    "ESTADO",
    "tier_label",
    "flag_extrapolacao",
    "demanda_p10",
    "demanda_p50",
    "demanda_p90",
    "aluguel_teto_p10",
    "aluguel_teto_p50",
    "aluguel_teto_p90",
    "margem_seguranca",
    "flag_robusto",
    "flag_no_go",
    "alunos_breakeven",
    "alunos_para_margem_alvo",
    "faixa_alunos_p10",
    "faixa_alunos_p50",
    "faixa_alunos_p90",
    "margem_ebitda_pct_p50",
    "payback_meses_p50",
    "flag_viavel_p50",
    "demanda_fonte",
    "grade_sensibilidade_json",
    "versao_contrato",
]


# ---------------------------------------------------------------------------
# Funcoes publicas
# ---------------------------------------------------------------------------


def carregar_base_calibracao(ultra_parquet_path: Path | str) -> pd.DataFrame:
    """Deriva a base de comparaveis (curva tamanho->densidade) do parquet Ultra.

    Retorna DataFrame com colunas ['metragem', 'alunos_por_m2'] (float), limpo:
    sem NaN, metragem>0 e alunos_por_m2>0. Nenhuma PII/geo propagada.

    Se `alunos_por_m2` nao existir mas existirem `metragem`+`alunos_total`, deriva
    `alunos_por_m2 = alunos_total / metragem` (guard defensivo; na base real a
    coluna ja existe).
    """
    df = pd.read_parquet(Path(ultra_parquet_path))

    if "alunos_por_m2" in df.columns:
        metragem = pd.to_numeric(df["metragem"], errors="coerce").astype(float)
        apm = pd.to_numeric(df["alunos_por_m2"], errors="coerce").astype(float)
    elif "metragem" in df.columns and "alunos_total" in df.columns:
        metragem = pd.to_numeric(df["metragem"], errors="coerce").astype(float)
        alunos = pd.to_numeric(df["alunos_total"], errors="coerce").astype(float)
        # Evita divisao por zero: onde metragem<=0, o resultado vira inf/NaN e cai
        # no filtro np.isfinite abaixo.
        with np.errstate(divide="ignore", invalid="ignore"):
            apm = alunos / metragem
    else:
        raise ValueError(
            "base de calibracao precisa de 'alunos_por_m2' ou "
            "('metragem' e 'alunos_total')"
        )

    out = pd.DataFrame({"metragem": metragem, "alunos_por_m2": apm})
    mask = (
        np.isfinite(out["metragem"])
        & np.isfinite(out["alunos_por_m2"])
        & (out["metragem"] > 0)
        & (out["alunos_por_m2"] > 0)
    )
    out = out[mask].dropna().reset_index(drop=True)
    if out.empty:
        raise ValueError("base de calibracao vazia após limpeza")
    return out[["metragem", "alunos_por_m2"]]


def assign_tier_e_faixa(
    m2: float, df_tiers: pd.DataFrame
) -> tuple[str, float, float, float, bool]:
    """Mapeia m2 -> (tier_label, p10, p50, p90, flag_extrapolacao).

    Usa `_assign_tier(m2)` (fonte unica dos limites de tier, BLK-VIAB-02) para o
    rotulo e faz lookup da linha correspondente em df_tiers.

    Levanta ValueError se o tier resultante nao existir em df_tiers.
    """
    label = _assign_tier(float(m2))
    row = df_tiers[df_tiers["tier_label"] == label]
    if row.empty:
        raise ValueError(f"tier '{label}' ausente em df_tiers")
    first = row.iloc[0]
    p10 = float(first["p10"])
    p50 = float(first["p50"])
    p90 = float(first["p90"])
    flag_extrap = bool(first["flag_extrapolacao"])
    return label, p10, p50, p90, flag_extrap


def rodar_candidato(
    row: pd.Series,
    base_calib_df: pd.DataFrame,
    df_tiers: pd.DataFrame,
) -> dict:
    """Roda o motor de viabilidade (coordless) para 1 candidato e monta o dict de saida.

    Chama `analisar_viabilidade_ponto` 3x (demanda p10/p50/p90) para obter o
    aluguel-teto em cada cenario. A grade de sensibilidade e as metricas de
    viabilidade sao lidas do cenario central (p50).
    """
    m2 = float(row["ÁREA"])
    aluguel = float(row["ALUGUEL"])
    tier_label, p10, p50, p90, flag_extrap = assign_tier_e_faixa(m2, df_tiers)

    def _analisar(demanda: float):  # type: ignore[no-untyped-def]
        return analisar_viabilidade_ponto(
            lat=LAT_COORDLESS,
            lng=LNG_COORDLESS,
            m2=m2,
            aluguel_pedido=aluguel,
            demanda_premissa=demanda,
            base_calibracao_df=base_calib_df,
            setores_df=None,  # COORDLESS explicito
        )

    res_p10 = _analisar(p10)
    res = _analisar(p50)  # cenario central (fonte da grade e das metricas)
    res_p90 = _analisar(p90)

    teto_p10 = float(res_p10.aluguel_teto_calculado)
    teto_p50 = float(res.aluguel_teto_calculado)
    teto_p90 = float(res_p90.aluguel_teto_calculado)

    margem_seguranca = teto_p50 - aluguel
    flag_robusto = bool(aluguel < teto_p10)  # passa ate no pior cenario (p10)
    flag_no_go = bool(aluguel > teto_p50)  # inviavel no cenario central

    grade_json = res.grade_sensibilidade.to_json(orient="records")

    return {
        "ID": row["ID"],
        "NOME": row["NOME"],
        "ÁREA": m2,
        "ALUGUEL": aluguel,
        "CIDADE": row["CIDADE"],
        "ESTADO": row["ESTADO"],
        "tier_label": tier_label,
        "flag_extrapolacao": bool(flag_extrap),
        "demanda_p10": float(p10),
        "demanda_p50": float(p50),
        "demanda_p90": float(p90),
        "aluguel_teto_p10": teto_p10,
        "aluguel_teto_p50": teto_p50,
        "aluguel_teto_p90": teto_p90,
        "margem_seguranca": float(margem_seguranca),
        "flag_robusto": flag_robusto,
        "flag_no_go": flag_no_go,
        "alunos_breakeven": float(res.alunos_breakeven),
        "alunos_para_margem_alvo": float(res.alunos_para_margem_alvo),
        "faixa_alunos_p10": (
            None if res.faixa_alunos_p10 is None else float(res.faixa_alunos_p10)
        ),
        "faixa_alunos_p50": (
            None if res.faixa_alunos_p50 is None else float(res.faixa_alunos_p50)
        ),
        "faixa_alunos_p90": (
            None if res.faixa_alunos_p90 is None else float(res.faixa_alunos_p90)
        ),
        "margem_ebitda_pct_p50": float(res.viabilidade.margem_ebitda_pct),
        "payback_meses_p50": float(res.viabilidade.payback_meses),
        "flag_viavel_p50": bool(res.viabilidade.flag_viavel),
        "demanda_fonte": str(res.demanda_fonte),
        "grade_sensibilidade_json": grade_json,
        "versao_contrato": VERSAO_CONTRATO,
    }


def rodar_batch(
    candidatos_path: Path | str,
    tiers_path: Path | str,
    ultra_path: Path | str,
) -> pd.DataFrame:
    """Le os 3 parquets, roda cada candidato e devolve o DataFrame ranqueado.

    Ranking por `margem_seguranca` DESC.
    """
    candidatos = pd.read_parquet(Path(candidatos_path))
    df_tiers = pd.read_parquet(Path(tiers_path))
    base_calib_df = carregar_base_calibracao(ultra_path)

    linhas: list[dict] = []
    for _, row in candidatos.iterrows():
        linhas.append(rodar_candidato(row, base_calib_df, df_tiers))

    df = pd.DataFrame(linhas, columns=COLUNAS_SAIDA)
    df = df.sort_values("margem_seguranca", ascending=False).reset_index(drop=True)
    return df


def materializar(
    df_resultado: pd.DataFrame,
    staging_dir: Path | str,
    analysis_dir: Path | str,
) -> tuple[Path, Path]:
    """Persiste o DataFrame ranqueado em parquet e gera o relatorio `.md`.

    Retorna (parquet_path, md_path).
    """
    staging_dir = Path(staging_dir)
    analysis_dir = Path(analysis_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = staging_dir / "viabilidade_candidatos.parquet"
    df_resultado.to_parquet(parquet_path, index=False)

    md_path = analysis_dir / "viabilidade_candidatos.md"
    md_path.write_text(_gerar_relatorio_md(df_resultado), encoding="utf-8")

    return parquet_path, md_path


def _gerar_relatorio_md(df: pd.DataFrame) -> str:
    """Gera o relatorio markdown ranqueado por margem de seguranca."""
    n_total = len(df)
    n_robusto = int(df["flag_robusto"].sum()) if n_total else 0
    n_no_go = int(df["flag_no_go"].sum()) if n_total else 0
    n_extrap = int(df["flag_extrapolacao"].sum()) if n_total else 0

    linhas = [
        "# Relatório de Viabilidade dos Candidatos (BLK-VIAB-03)",
        "",
        f"Data de geração: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"Versão do contrato: `{VERSAO_CONTRATO}` · "
        "Demanda: premissa explícita (DEC-009) · "
        "Modo: coordless (setores_df=None)",
        "",
        "## Resumo",
        "",
        f"- Total de candidatos: {n_total}",
        f"- ROBUSTO (aluguel < teto p10): {n_robusto}",
        f"- NO-GO (aluguel > teto p50): {n_no_go}",
        f"- Com flag de extrapolação (tier instável): {n_extrap}",
        "",
        "## Ranking por margem de segurança (DESC)",
        "",
        "| Rank | ID | NOME | ÁREA (m²) | ALUGUEL (R$) | Tier | "
        "Teto p50 (R$) | Margem seg. (R$) | Break-even (alunos) | "
        "Robusto | NO-GO | Extrap |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    for rank, (_, r) in enumerate(df.iterrows(), start=1):
        robusto = "SIM" if bool(r["flag_robusto"]) else "-"
        no_go = "NO-GO" if bool(r["flag_no_go"]) else "-"
        extrap = "ATENÇÃO" if bool(r["flag_extrapolacao"]) else "-"
        linhas.append(
            f"| {rank} | {r['ID']} | {r['NOME']} | {r['ÁREA']:,.0f} | "
            f"{r['ALUGUEL']:,.0f} | {r['tier_label']} | "
            f"{r['aluguel_teto_p50']:,.0f} | {r['margem_seguranca']:,.0f} | "
            f"{r['alunos_breakeven']:.0f} | {robusto} | {no_go} | {extrap} |"
        )

    linhas += ["", "## Caveats", ""]

    extrapolados = df[df["flag_extrapolacao"]]
    if len(extrapolados):
        nomes = ", ".join(str(x) for x in extrapolados["NOME"].tolist())
        linhas.append(
            "- **Extrapolação de tier:** os candidatos a seguir caem em um tier com "
            f"N pequeno (percentis instáveis) - {nomes}. O p50/p90 do tier deve ser "
            "usado com cautela."
        )
    else:
        linhas.append("- Nenhum candidato em tier extrapolado.")

    linhas += [
        "- **Nota metodológica:** ranking = aluguel_teto(demanda=p50) - "
        "aluguel_pedido; flag_robusto = aluguel < teto(p10); "
        "flag_no_go = aluguel > teto(p50). "
        "Defaults do motor: ticket R$137, margem-alvo 10%, share balcão 69%.",
        "- **Nota DEC-009:** a demanda entra SÓ como premissa explícita por tier de "
        "metragem; NUNCA prevista por lat/lng. Modo coordless puro "
        "(setores_df=None, sem catchment/rede).",
        "- **READ-ONLY M1:** nenhum score, peso, carteira, plano ou artefato oficial "
        "do M1 foi tocado (DEC-001/DEC-008).",
    ]

    return "\n".join(linhas)


def run(
    candidatos_path: Path | str,
    tiers_path: Path | str,
    ultra_path: Path | str,
    staging_dir: Path | str,
    analysis_dir: Path | str,
) -> tuple[Path, Path]:
    """Pipeline completo: roda o batch e materializa parquet + relatorio."""
    df = rodar_batch(candidatos_path, tiers_path, ultra_path)
    return materializar(df, staging_dir, analysis_dir)


__all__ = [
    "carregar_base_calibracao",
    "assign_tier_e_faixa",
    "rodar_candidato",
    "rodar_batch",
    "materializar",
    "run",
    "VERSAO_CONTRATO",
    "LAT_COORDLESS",
    "LNG_COORDLESS",
    "COLUNAS_GEO_EXCLUIR",
    "COLUNAS_SAIDA",
]


if __name__ == "__main__":
    _repo = Path(__file__).resolve().parents[3]
    _candidatos = _repo / "data" / "staging" / "imoveis_candidatos_limpos.parquet"
    _tiers = _repo / "data" / "staging" / "demanda_premissa_por_tier.parquet"
    _ultra = _repo / "data" / "staging" / "unidades_ultra_performance_hex.parquet"
    _staging = _repo / "data" / "staging"
    _analysis = _repo / "data" / "analysis"

    _parquet, _md = run(_candidatos, _tiers, _ultra, _staging, _analysis)
    print(f"Parquet: {_parquet}")
    print(f"Relatorio: {_md}")

    _df = pd.read_parquet(_parquet)
    print(f"\nN candidatos: {len(_df)}")
    print("\nTop-3 por margem de seguranca:")
    _cols = ["ID", "NOME", "ÁREA", "ALUGUEL", "tier_label", "margem_seguranca"]
    print(_df[_cols].head(3).to_string(index=False))
    print(f"\ndemanda_fonte unico: {_df['demanda_fonte'].unique().tolist()}")
