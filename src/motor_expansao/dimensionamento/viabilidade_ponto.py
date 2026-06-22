"""Motor property-first de viabilidade do imovel (BLK-DIM-11).

Dado um imovel real (`lat,lng` + `m2` + `aluguel pedido` + `demanda_premissa`),
devolve: contexto do entorno (catchment), faixa de alunos por densidade (curva
tamanho->densidade, NAO geografica), flag de zona morta, viabilidade financeira no
cenario pedido (margem/payback/ROIC), aluguel-teto, break-even e grade de
sensibilidade demanda x aluguel.

GUARDRAIL CENTRAL (4 NO-GOs):
    - A demanda NUNCA e derivada de lat/lng. `demanda_premissa` e entrada EXPLICITA
      do operador; `demanda_fonte` e sempre "premissa_explicita".
    - `lat/lng` so alimentam o catchment (contexto pop/renda) e a flag de zona morta.
    - A faixa de alunos por densidade depende SO de `m2` + base de comparaveis — nao de geo.
    - Sem I/O de parquet interno: todos os DataFrames sao injetados pelo chamador.

READ-ONLY sobre o M1: nao recalcula `score_priorizacao`, `hex_score_estrutural`,
pesos, carteira, plano nem artefatos oficiais (DEC-001/DEC-008). Funcao pura, sem UI.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from motor_expansao.dimensionamento.catchment_batch import calcular_catchment_unidade
from motor_expansao.dimensionamento.config import RAIO_CATCHMENT_KM, SIM_MENSALIDADE_BALCAO
from motor_expansao.dimensionamento.simulador import (
    ViabilidadeResult,
    aluguel_teto,
    alunos_minimos_viaveis,
    viabilidade,
)

# --- Thresholds de zona morta (exogenos; NAO preveem alunos) -----------------
POP_ZONA_MORTA_MIN: float = 5_000.0       # alinhado com POP_MIN_ACIONAVEL do dashboard
RENDA_ZONA_MORTA_MIN: float = 1_600.0     # renda per capita minima do entorno

# --- Faixa de comparaveis por densidade (curva tamanho->densidade) -----------
FAIXA_M2_TOLERANCIA: float = 0.20         # +/-20% do m2 do imovel
FAIXA_M2_TOLERANCIA_ALARGADA: float = 0.50  # +/-50% se N < N_MIN_COMPARAVEIS na janela estreita
N_MIN_COMPARAVEIS: int = 3                # minimo de comparaveis para nao alargar

# --- Grade de sensibilidade (defaults) ---------------------------------------
ALUNOS_RANGE_DEFAULT: tuple[float, ...] = (200.0, 400.0, 600.0, 800.0, 1000.0, 1200.0)
ALUGUEL_RANGE_FATOR: tuple[float, ...] = (0.6, 0.8, 1.0, 1.2, 1.5)  # x aluguel_pedido

# --- Guardrail explicito -----------------------------------------------------
DEMANDA_FONTE_PREMISSA: str = "premissa_explicita"

# --- Composicao balcao/agregadores (estudo §5; Ultra ~69% balcao / ~31% agregadores) ---
# A demanda_premissa representa alunos TOTAIS; o split alimenta o DRE com 2 tickets
# (balcao a ticket cheio + agregadores ~60% do ticket). NAO altera o simulador (DRE).
SHARE_BALCAO_DEFAULT: float = 0.69


@dataclass
class ViabilidadePontoResult:
    """Resultado consolidado do motor de viabilidade property-first (BLK-DIM-11).

    GUARDRAIL: `demanda_premissa` e entrada do operador; NUNCA derivada de lat/lng.
    `demanda_fonte` e sempre "premissa_explicita".
    """

    # --- Contexto do imovel (inputs ecoados) ---
    lat: float
    lng: float
    m2: float
    aluguel_pedido: float
    demanda_premissa: float

    # --- Faixa de alunos por densidade (None se base_calibracao_df ausente) ---
    faixa_alunos_p10: float | None
    faixa_alunos_p50: float | None
    faixa_alunos_p90: float | None
    n_comparaveis: int | None

    # --- Flag de zona morta (None se setores_df ausente -> catchment nao rodado) ---
    flag_zona_morta: bool | None
    motivo_zona_morta: str | None

    # --- Contexto do entorno (catchment; None se setores_df ausente) ---
    pop_captacao: float | None
    renda_per_capita_captacao: float | None

    # --- Viabilidade no cenario pedido (demanda = premissa explicita) ---
    viabilidade: ViabilidadeResult
    aluguel_teto_calculado: float
    alunos_breakeven: float

    # --- Grade de sensibilidade ---
    grade_sensibilidade: pd.DataFrame

    # --- Split da premissa (auditabilidade; derivados de demanda_premissa * share) ---
    alunos_balcao_premissa: float = 0.0
    alunos_agregadores_premissa: float = 0.0

    # --- Break-even com margem_alvo explícita (NAO break-even real) ---
    alunos_para_margem_alvo: float = 0.0

    # --- Guardrail: demanda NUNCA derivada de geo ---
    demanda_fonte: str = DEMANDA_FONTE_PREMISSA


def faixa_alunos_por_densidade(
    m2: float,
    base_calibracao_df: pd.DataFrame,
    *,
    tolerancia: float = FAIXA_M2_TOLERANCIA,
    tolerancia_alargada: float = FAIXA_M2_TOLERANCIA_ALARGADA,
    n_min: int = N_MIN_COMPARAVEIS,
) -> dict:
    """Faixa de alunos plausivel derivada da curva tamanho->densidade (NAO geografica).

    Usa `alunos_por_m2` dos comparaveis Ultra numa janela de m2 em torno do imovel.
    Retorna percentis (p10/p50/p90) de `alunos_por_m2` x m2 -> faixa de ALUNOS.

    GUARDRAIL: nao recebe lat/lng. A faixa depende SO de `m2` + base de comparaveis.

    Janela:
      1. +/-`tolerancia` (20%) do m2 do imovel.
      2. Se N < `n_min`: alarga para +/-`tolerancia_alargada` (50%).
      3. Se ainda N < `n_min`: usa a base inteira valida.

    Retorna dict:
      {"faixa_alunos_p10": float, "faixa_alunos_p50": float, "faixa_alunos_p90": float,
       "n_comparaveis": int}
    ou, se a base nao tiver as colunas exigidas ou ficar vazia apos limpeza:
      {"faixa_alunos_p10": None, ..., "n_comparaveis": 0}
    """
    vazio = {
        "faixa_alunos_p10": None,
        "faixa_alunos_p50": None,
        "faixa_alunos_p90": None,
        "n_comparaveis": 0,
    }
    if base_calibracao_df is None or len(base_calibracao_df) == 0:
        return vazio
    if "alunos_por_m2" not in base_calibracao_df.columns:
        return vazio

    df = base_calibracao_df.copy()
    df["__apm"] = pd.to_numeric(df["alunos_por_m2"], errors="coerce")
    df = df[np.isfinite(df["__apm"]) & (df["__apm"] > 0)]
    if df.empty:
        return vazio

    tem_metragem = "metragem" in df.columns
    if tem_metragem:
        df["__metr"] = pd.to_numeric(df["metragem"], errors="coerce")

    def _janela(tol: float) -> pd.DataFrame:
        if not tem_metragem:
            return df
        lo = m2 * (1.0 - tol)
        hi = m2 * (1.0 + tol)
        return df[df["__metr"].between(lo, hi)]

    sub = _janela(tolerancia)
    if len(sub) < n_min:
        sub = _janela(tolerancia_alargada)
    if len(sub) < n_min:
        sub = df

    if sub.empty:
        return vazio

    apm_sub = sub["__apm"].to_numpy(dtype=float)
    p10, p50, p90 = (float(v) for v in np.percentile(apm_sub, [10, 50, 90]))
    return {
        "faixa_alunos_p10": float(p10 * m2),
        "faixa_alunos_p50": float(p50 * m2),
        "faixa_alunos_p90": float(p90 * m2),
        "n_comparaveis": int(len(sub)),
    }


def flag_zona_morta(
    catchment_result: dict | None,
    *,
    pop_min: float = POP_ZONA_MORTA_MIN,
    renda_min: float = RENDA_ZONA_MORTA_MIN,
) -> dict:
    """Sinaliza risco de contexto (zona morta) a partir do catchment — NAO preve alunos.

    Le `pop_captacao` e `renda_per_capita_captacao` do dict de catchment.
    Dispara True se pop < pop_min OU renda < renda_min.

    Retorna {"flag_zona_morta": Optional[bool], "motivo_zona_morta": Optional[str]}.
    Se catchment_result is None (sem setores) ou pop/renda forem NaN -> retorna
    {"flag_zona_morta": None, "motivo_zona_morta": "catchment_indisponivel"}.

    GUARDRAIL: esta funcao NAO preve demanda — so compara pop/renda do entorno com
    thresholds exogenos. A flag e de exclusao de contexto, nao estimativa de alunos.
    """
    indisponivel = {"flag_zona_morta": None, "motivo_zona_morta": "catchment_indisponivel"}
    if catchment_result is None:
        return indisponivel

    pop_raw = catchment_result.get("pop_captacao")
    renda_raw = catchment_result.get("renda_per_capita_captacao")
    pop = float(pop_raw) if pop_raw is not None and np.isfinite(pop_raw) else None
    renda = float(renda_raw) if renda_raw is not None and np.isfinite(renda_raw) else None
    if pop is None and renda is None:
        return indisponivel

    motivos: list[str] = []
    if pop is not None and pop < pop_min:
        motivos.append(f"pop<{int(pop_min)}")
    if renda is not None and renda < renda_min:
        motivos.append(f"renda<{int(renda_min)}")

    flag = bool(motivos)
    motivo = "; ".join(motivos) if motivos else "ok"
    return {"flag_zona_morta": flag, "motivo_zona_morta": motivo}


def grade_sensibilidade(
    m2: float,
    aluguel_ref: float,
    demanda_premissa: float,
    *,
    ticket_medio: float = SIM_MENSALIDADE_BALCAO,
    n_alunos_range: tuple[float, ...] = ALUNOS_RANGE_DEFAULT,
    n_aluguel_range: tuple[float, ...] = ALUGUEL_RANGE_FATOR,
    margem_alvo: float = 0.10,
    share_balcao: float = SHARE_BALCAO_DEFAULT,
    **kwargs: object,
) -> pd.DataFrame:
    """Varredura cartesiana alunos x aluguel -> viabilidade() por par.

    `n_alunos_range` e uma grade ABSOLUTA de alunos TOTAIS (nao inclui
    `demanda_premissa` automaticamente; o orquestrador a usa como referencia
    separada). Cada celula aplica o split interno via `share_balcao`:
    balcao = alunos*share_balcao + agregadores = alunos*(1-share_balcao).
    `n_aluguel_range` sao FATORES multiplicados por `aluguel_ref`.

    `margem_alvo` fica na assinatura por simetria; nao gera coluna dependente aqui.
    `demanda_premissa` e referencia (nao entra na varredura — a grade varre
    `n_alunos_range`); mantido na assinatura por simetria com o orquestrador.

    Retorna DataFrame com colunas:
      ['alunos', 'aluguel', 'fator_aluguel', 'margem_liq', 'viavel', 'payback'].
    Shape = (len(n_alunos_range) * len(n_aluguel_range), 6). `margem_liq` e a
    margem EBITDA do DRE (`margem_ebitda_pct`).
    """
    _ = (demanda_premissa, margem_alvo)  # referencia explicita; nao varridos
    linhas: list[dict] = []
    for alunos in n_alunos_range:
        balcao_cel = float(alunos) * share_balcao
        agr_cel = float(alunos) * (1.0 - share_balcao)
        for fator in n_aluguel_range:
            aluguel = float(aluguel_ref) * float(fator)
            r = viabilidade(
                balcao_cel, m2, aluguel, ticket_medio,
                alunos_agregadores=agr_cel, **kwargs,  # type: ignore[arg-type]
            )
            linhas.append(
                {
                    "alunos": float(alunos),
                    "aluguel": aluguel,
                    "fator_aluguel": float(fator),
                    "margem_liq": r.margem_ebitda_pct,
                    "viavel": r.flag_viavel,
                    "payback": r.payback_meses,
                }
            )
    return pd.DataFrame(
        linhas,
        columns=["alunos", "aluguel", "fator_aluguel", "margem_liq", "viavel", "payback"],
    )


def analisar_viabilidade_ponto(
    lat: float,
    lng: float,
    m2: float,
    aluguel_pedido: float,
    demanda_premissa: float,
    *,
    ticket_medio: float = SIM_MENSALIDADE_BALCAO,
    margem_alvo: float = 0.10,
    share_balcao: float = SHARE_BALCAO_DEFAULT,
    raio_km: float = RAIO_CATCHMENT_KM,
    base_calibracao_df: pd.DataFrame | None = None,
    setores_df: pd.DataFrame | None = None,
    alunos_range: tuple[float, ...] = ALUNOS_RANGE_DEFAULT,
    aluguel_range_fator: tuple[float, ...] = ALUGUEL_RANGE_FATOR,
    **kwargs: object,
) -> ViabilidadePontoResult:
    """Orquestrador property-first.

    GUARDRAIL: `demanda_premissa` e entrada do operador; NUNCA derivada de lat/lng.
    lat/lng entram SO no catchment (contexto pop/renda) e na flag de zona morta.

    Modos degradados:
      - setores_df is None  -> catchment NAO roda; flag_zona_morta=None,
        pop_captacao/renda_per_capita_captacao=None.
      - base_calibracao_df is None -> faixa_alunos_p10/p50/p90=None, n_comparaveis=None.
    """
    # 1. Catchment (contexto) — so roda se setores_df foi injetado.
    catch: dict | None
    pop: float | None
    renda: float | None
    if setores_df is None:
        catch = None
        pop = None
        renda = None
    else:
        catch = calcular_catchment_unidade(lat, lng, setores_df, raio_km=raio_km)
        pop = float(catch["pop_captacao"])
        renda = float(catch["renda_per_capita_captacao"])

    # 2. Flag de zona morta.
    zm = flag_zona_morta(catch, pop_min=POP_ZONA_MORTA_MIN, renda_min=RENDA_ZONA_MORTA_MIN)

    # 3. Faixa de alunos por densidade (curva tamanho->densidade; NAO geografica).
    if base_calibracao_df is None:
        faixa: dict = {
            "faixa_alunos_p10": None,
            "faixa_alunos_p50": None,
            "faixa_alunos_p90": None,
            "n_comparaveis": None,
        }
    else:
        faixa = faixa_alunos_por_densidade(m2, base_calibracao_df)

    # 3b. Split da premissa em balcao + agregadores (composicao; estudo §5).
    # A demanda_premissa e SEMPRE alunos TOTAIS; o DRE roda com 2 tickets.
    alunos_balcao = float(demanda_premissa) * share_balcao
    alunos_agregadores = float(demanda_premissa) * (1.0 - share_balcao)

    # 4. Viabilidade no cenario pedido (demanda = premissa explicita).
    viab = viabilidade(
        alunos_balcao, m2, aluguel_pedido, ticket_medio,
        alunos_agregadores=alunos_agregadores, **kwargs,  # type: ignore[arg-type]
    )

    # 5. Aluguel-teto e break-even.
    teto = aluguel_teto(
        alunos_balcao, m2, ticket_medio, margem_alvo=margem_alvo,
        alunos_agregadores=alunos_agregadores, **kwargs,  # type: ignore[arg-type]
    )
    # Break-even REAL: margem EBITDA = 0% (definicao canonica; DEC-009)
    breakeven = alunos_minimos_viaveis(
        m2, aluguel_pedido, ticket_medio, margem_alvo=0.0,
        alunos_agregadores=alunos_agregadores, **kwargs,  # type: ignore[arg-type]
    )
    # Alunos para a margem-alvo (informativo; sempre >= breakeven)
    alunos_margem_alvo = alunos_minimos_viaveis(
        m2, aluguel_pedido, ticket_medio, margem_alvo=margem_alvo,
        alunos_agregadores=alunos_agregadores, **kwargs,  # type: ignore[arg-type]
    )

    # 6. Grade de sensibilidade.
    grade = grade_sensibilidade(
        m2,
        aluguel_pedido,
        demanda_premissa,
        ticket_medio=ticket_medio,
        n_alunos_range=alunos_range,
        n_aluguel_range=aluguel_range_fator,
        margem_alvo=margem_alvo,
        share_balcao=share_balcao,
        **kwargs,
    )

    # 7. Montar resultado.
    return ViabilidadePontoResult(
        lat=float(lat),
        lng=float(lng),
        m2=float(m2),
        aluguel_pedido=float(aluguel_pedido),
        demanda_premissa=float(demanda_premissa),
        faixa_alunos_p10=faixa["faixa_alunos_p10"],
        faixa_alunos_p50=faixa["faixa_alunos_p50"],
        faixa_alunos_p90=faixa["faixa_alunos_p90"],
        n_comparaveis=faixa["n_comparaveis"],
        flag_zona_morta=zm["flag_zona_morta"],
        motivo_zona_morta=zm["motivo_zona_morta"],
        pop_captacao=None if catch is None else pop,
        renda_per_capita_captacao=None if catch is None else renda,
        viabilidade=viab,
        aluguel_teto_calculado=float(teto),
        alunos_breakeven=float(breakeven),
        grade_sensibilidade=grade,
        alunos_balcao_premissa=float(alunos_balcao),
        alunos_agregadores_premissa=float(alunos_agregadores),
        alunos_para_margem_alvo=float(alunos_margem_alvo),
        demanda_fonte=DEMANDA_FONTE_PREMISSA,
    )


__all__ = [
    "ViabilidadePontoResult",
    "analisar_viabilidade_ponto",
    "faixa_alunos_por_densidade",
    "flag_zona_morta",
    "grade_sensibilidade",
    "POP_ZONA_MORTA_MIN",
    "RENDA_ZONA_MORTA_MIN",
    "FAIXA_M2_TOLERANCIA",
    "FAIXA_M2_TOLERANCIA_ALARGADA",
    "N_MIN_COMPARAVEIS",
    "ALUNOS_RANGE_DEFAULT",
    "ALUGUEL_RANGE_FATOR",
    "DEMANDA_FONTE_PREMISSA",
    "SHARE_BALCAO_DEFAULT",
]
