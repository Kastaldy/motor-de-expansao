"""Motor de risco property-first (BLK-DIM-14).

Funcoes PURAS de classificacao de risco para o motor de viabilidade de imovel.
READ-ONLY sobre o M1: nao recalcula score_priorizacao, pesos, carteira nem
artefatos oficiais (DEC-001/DEC-008/DEC-009).

GUARDRAIL CENTRAL (anti-geografico):
    Nenhuma funcao deste modulo recebe lat/lng. O P(viavel) depende
    SOMENTE da metragem do imovel + base de comparaveis - nao de geo.

RANKING DORMENTE:
    `ranking_oportunidades` existe mas RANKING_ATIVO=False e a funcao
    nao e chamada por nenhum render do dashboard. Servira para a fase
    futura de busca imobiliaria web (epic separada, nao loop-safe).

Sem I/O de parquet: todos os DataFrames sao injetados pelo chamador.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# --- Janela de m2 (espelha viabilidade_ponto; paridade garantida em test_risco.T17) ---
FAIXA_M2_TOLERANCIA: float = 0.20          # +/-20% do m2 do imovel
FAIXA_M2_TOLERANCIA_ALARGADA: float = 0.50  # +/-50% se N < N_MIN_COMPARAVEIS
N_MIN_COMPARAVEIS: int = 3                  # minimo de comparaveis para nao alargar

# --- Cutoffs de classe de risco (estudo secao 7) ---
CUTOFF_GO: float = 0.70       # P >= 0.70 -> GO
CUTOFF_ATENCAO: float = 0.40  # P >= 0.40 -> ATENCAO; P < 0.40 -> NAO

# --- Feature flag: ranking DORMENTE (sem render) ---
RANKING_ATIVO: bool = False

# --- Coluna de formato/marca na base de calibracao ---
COL_FORMATO_CANDIDATAS: tuple[str, ...] = ("marca", "formato")


def p_viavel(
    m2: float,
    break_even: float,
    base_calibracao_df: pd.DataFrame | None,
    formato: str | None = None,
    *,
    tolerancia: float = FAIXA_M2_TOLERANCIA,
    tolerancia_alargada: float = FAIXA_M2_TOLERANCIA_ALARGADA,
    n_min: int = N_MIN_COMPARAVEIS,
) -> float | None:
    """Probabilidade honesta de viabilidade: fracao dos comparaveis que superam o break-even.

    GUARDRAIL anti-geografico: NAO recebe lat/lng. O P(viavel) depende SO de `m2` +
    `base_calibracao_df` (base de comparaveis com `alunos_por_m2`).

    Parametros
    ----------
    m2 : float
        Metragem do imovel em m2.
    break_even : float
        Alunos minimos para viabilidade (de `alunos_minimos_viaveis` ou `alunos_breakeven`).
        `float("inf")` -> retorna 0.0 (nenhum comparavel supera infinity).
    base_calibracao_df : pd.DataFrame | None
        Base de comparaveis com pelo menos `alunos_por_m2` e, opcionalmente, `metragem` e
        coluna de formato (`marca` ou `formato`). DataFrame injetado pelo chamador (sem I/O).
    formato : str | None
        Valor da coluna de formato a filtrar (ex.: `"ultra"`, `"engenharia_do_corpo"`).
        A coluna e resolvida em ordem de `COL_FORMATO_CANDIDATAS` (`marca`, entao `formato`).
        Se a coluna nao existir ou N < n_min apos filtro -> usa a base inteira (silencioso).
        Comparacao case-insensitive com strip.
    tolerancia : float
        Janela estreita de m2 (+-tolerancia). Default 0.20 (espelha viabilidade_ponto).
    tolerancia_alargada : float
        Janela alargada de m2 (+-tolerancia_alargada). Default 0.50.
    n_min : int
        Minimo de comparaveis para nao alargar a janela. Default 3.

    Retorna
    -------
    float | None
        Fracao em [0.0, 1.0] dos comparaveis cujo `alunos_por_m2 * m2 > break_even`.
        `None` se base ausente/vazia/sem coluna obrigatoria ou janela final vazia.
        `0.0` se `break_even=inf` (correto: nenhum comparavel supera infinity).
    """
    # 1. Base ausente ou vazia
    if base_calibracao_df is None or len(base_calibracao_df) == 0:
        return None

    # 2. Coluna obrigatoria
    if "alunos_por_m2" not in base_calibracao_df.columns:
        return None

    # 3. Limpeza de alunos_por_m2
    df = base_calibracao_df.copy()
    df["__apm"] = pd.to_numeric(df["alunos_por_m2"], errors="coerce")
    df = df[np.isfinite(df["__apm"]) & (df["__apm"] > 0)].copy()
    if df.empty:
        return None

    # 4. Filtro de formato (ANTES do m2)
    if formato is not None:
        col_fmt: str | None = None
        for candidata in COL_FORMATO_CANDIDATAS:
            if candidata in df.columns:
                col_fmt = candidata
                break
        if col_fmt is not None:
            formato_norm = str(formato).strip().casefold()
            df_fmt = df[df[col_fmt].astype(str).str.strip().str.casefold() == formato_norm]
            if len(df_fmt) >= n_min:
                df = df_fmt
            # senao: fallback silencioso para df inteiro

    # 5. Janela de m2
    tem_metragem = "metragem" in df.columns
    if tem_metragem:
        df = df.copy()
        df["__metr"] = pd.to_numeric(df["metragem"], errors="coerce")

    def _janela(tol: float) -> pd.DataFrame:
        if not tem_metragem:
            return df
        lo, hi = m2 * (1.0 - tol), m2 * (1.0 + tol)
        return df[df["__metr"].between(lo, hi)]

    sub = _janela(tolerancia)
    if len(sub) < n_min:
        sub = _janela(tolerancia_alargada)
    if len(sub) < n_min:
        sub = df

    if sub.empty:
        return None

    # 6-7. Fracao dos comparaveis que superam o break-even (comparacao ESTRITA >)
    apm_arr = sub["__apm"].to_numpy(dtype=float)
    return float((apm_arr * m2 > break_even).mean())


def classe_risco(p: float | None) -> str:
    """Classifica o P(viavel) em GO / ATENCAO / NAO / INDISPONIVEL.

    Cutoffs:
      GO           : P >= 0.70
      ATENCAO      : 0.40 <= P < 0.70
      NAO          : P < 0.40
      INDISPONIVEL : p is None (base de comparaveis ausente)
    """
    if p is None:
        return "INDISPONIVEL"
    if p >= CUTOFF_GO:
        return "GO"
    if p >= CUTOFF_ATENCAO:
        return "ATENCAO"
    return "NAO"


def ranking_oportunidades(lista_imoveis: list[dict]) -> list[dict]:
    """Ordena imoveis por P(viavel) DESC; desempate por break_even ASC. DORMENTE.

    RANKING_ATIVO=False: esta funcao existe mas NAO e chamada por nenhum render do
    dashboard. Servira para a fase futura de busca imobiliaria web (epic separada).

    Parametros
    ----------
    lista_imoveis : list[dict]
        Lista de dicts com pelo menos `{"p_viavel": float|None, "break_even": float}`.
        Campo `id` opcional. A lista original NAO e mutada (usa sorted()).

    Retorna
    -------
    list[dict]
        Lista ordenada: p_viavel DESC (None vai para o fim), break_even ASC desempate.
    """

    def _key(im: dict) -> tuple[bool, float, float]:
        pv = im.get("p_viavel")
        none_flag = pv is None
        pv_desc = -(pv or 0.0)  # None ja fica no fim pela flag; 0.0 e o pior dos nao-None
        be_asc = float(im.get("break_even", float("inf")))
        return (none_flag, pv_desc, be_asc)

    return sorted(lista_imoveis, key=_key)


__all__ = [
    "p_viavel",
    "classe_risco",
    "ranking_oportunidades",
    "RANKING_ATIVO",
    "CUTOFF_GO",
    "CUTOFF_ATENCAO",
    "FAIXA_M2_TOLERANCIA",
    "FAIXA_M2_TOLERANCIA_ALARGADA",
    "N_MIN_COMPARAVEIS",
    "COL_FORMATO_CANDIDATAS",
]
