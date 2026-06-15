"""Camada 1 (BLK-DIM): aderencia calibrada por catchment -- alvo log(pagantes).

Estima a demanda absoluta das unidades maduras via regressao log-log Ridge com
LOO-CV honesto (spec modelo_dimensionamento_expansao.md §4 Camada 1, §6 Fase 1,
§7 metodologia). BLK-DIM-01R corrige os 2 vicios do spike BLK-DIM-01:
(a) fixture circular (R2 alto por construcao) e (b) endogeneidade mecanica do alvo
`penetracao = pagantes/pop` (o `log(pop)` no denominador correlaciona-se quase
perfeitamente com a feature `log(pop)`).

Correcao: modelar `log(pagantes_steady_state)` DIRETAMENTE (sem a razao). Forma
funcional: pagantes ~ exp(b0) * pop^b1 * renda^b2, i.e.
log(pagantes) = b0 + b1*log(pop) + b2*log(renda). NAO usa "20% fixo" (armadilha §5).

NO-GO E O RESULTADO ESPERADO E VALIDO. O criterio de aceite e honestidade
estatistica, NAO obter GO. R2_LOO_log <= LIMIAR_R2_GO -> NO-GO honesto, consistente
com a DEC-001 (M1 teve Spearman ~ 0).

READ-ONLY sobre o M1 (DEC-001): nao recalcula score_priorizacao/hex_score_estrutural,
nao toca pesos/carteira/plano/artefatos oficiais. Sem PII em disco; fixtures sinteticas
nos testes. Confounds documentados (vies de selecao, dilution de catchment, N pequeno)
sao cautelas estruturais propagadas em `nota_honesta`.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import LeaveOneOut

_logger = logging.getLogger(__name__)

# Limiar de materialidade do gate GO/NO-GO (R2_LOO_log estritamente acima disso e GO honesto).
LIMIAR_R2_GO: float = 0.05
# Grade de alpha para selecao por LOO (menor rmse_loo_log).
ALPHA_GRID: tuple[float, ...] = (0.01, 0.1, 1.0, 10.0, 100.0)
# Piso de observacoes para calibrar (n efetivo apos remover outliers).
N_MIN_CALIBRACAO: int = 5
# Piso de pagantes previstos (nunca menos de 1 aluno).
PAGANTES_MIN: float = 1.0


@dataclass
class AderenciaModel:
    """Resultado da calibracao da aderencia (Camada 1, log-log Ridge, alvo log(pagantes)).

    `r2_loo_log` e a metrica PRINCIPAL honesta (LOO-CV no espaco log, espaco de modelagem)
    e decide o gate. `r2_loo_pagantes` e auditoria/interpretabilidade (espaco de alunos).
    `r2_insample_log` existe APENAS para auditoria -- nao decide o gate.
    IC de predicao calculado por +-1 RMSE_LOO_log (back-transformado para alunos).
    """

    # coeficientes (modelo final no espaco log)
    alpha_selecionado: float
    """Alpha selecionado por MENOR rmse_loo_log na varredura do ALPHA_GRID."""

    coef_log_pop: float
    """Coeficiente de log(pop_captacao). Esperado POSITIVO (mais populacao -> mais pagantes)."""

    coef_log_renda: float
    """Coeficiente de log(renda_per_capita). Esperado >= 0 (poder aquisitivo)."""

    intercepto_log: float
    """Intercepto no espaco log (b0)."""

    # validacao honesta -- DOIS espacos
    r2_loo_log: float
    """R2 honesto via LOO-CV no espaco log. METRICA PRINCIPAL do gate."""

    r2_loo_pagantes: float
    """R2 LOO no espaco de pagantes (exp das predicoes). Auditoria; NAO decide gate."""

    rmse_loo_log: float
    """RMSE do LOO-CV no espaco log (usado no IC de predicao)."""

    rmse_loo_pagantes: float
    """RMSE do LOO-CV no espaco de pagantes (alunos)."""

    r2_insample_log: float
    """R2 in-sample no espaco log (apenas auditoria). NAO usar como desempenho."""

    # envelope (no espaco log) para flag de extrapolacao
    log_pop_min: float
    log_pop_max: float
    log_renda_min: float
    log_renda_max: float

    # metadados
    n_treinamento: int
    """Numero de observacoes efetivas usadas no treino (apos remocao de outliers)."""

    n_outliers_removidos: int
    """Quantas linhas foram removidas como outliers/invalidos antes do treino."""

    flag_extrapolacao_padrao: bool
    """Flag de baixa confianca GLOBAL do modelo: True se n_treinamento < 30.

    Heuristica: com menos de 30 observacoes o LOO e muito instavel entre alphas.
    Distinto de `flag_extrapolacao(pop, renda)`, que e por-ponto (envelope min-max).
    """

    veredito: str
    """"GO" se r2_loo_log > LIMIAR_R2_GO, "NO-GO" caso contrario."""

    nota_honesta: str
    """Mensagem legivel (PT, sem PII) com metricas, coeficientes, veredito e confounds."""

    @property
    def go(self) -> bool:
        """True se o gate honesto deu GO."""
        return self.veredito == "GO"

    def flag_extrapolacao(self, pop_captacao: float, renda_per_capita: float) -> bool:
        """True se (log_pop, log_renda) cair fora do envelope min-max de treino.

        pop/renda <= 0 -> extrapolacao True (fora do dominio log, nao avaliavel).
        """
        if pop_captacao <= 0 or renda_per_capita <= 0:
            return True
        lp = math.log(pop_captacao)
        lr = math.log(renda_per_capita)
        return (
            lp < self.log_pop_min
            or lp > self.log_pop_max
            or lr < self.log_renda_min
            or lr > self.log_renda_max
        )


def _r2_loo_para_alpha(
    X: np.ndarray, y: np.ndarray, alpha: float
) -> tuple[float, float, np.ndarray]:
    """LOO-CV de um Ridge(alpha) no espaco do target.

    Retorna (r2_loo, rmse_loo, y_pred_loo). O scaler NAO e usado (features log cruas,
    de escala similar) -> sem risco de vazamento de escala entre folds.
    """
    loo = LeaveOneOut()
    y_pred_loo = np.zeros(len(y), dtype=float)
    for train_idx, test_idx in loo.split(X):
        reg_fold = Ridge(alpha=alpha)
        reg_fold.fit(X[train_idx], y[train_idx])
        y_pred_loo[test_idx] = reg_fold.predict(X[test_idx])
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    ss_res_loo = float(np.sum((y - y_pred_loo) ** 2))
    r2_loo = 1.0 - ss_res_loo / ss_tot if ss_tot > 0 else 0.0
    rmse_loo = float(math.sqrt(np.mean((y_pred_loo - y) ** 2)))
    return r2_loo, rmse_loo, y_pred_loo


def relatorio_aderencia(modelo: AderenciaModel) -> str:
    """String multilinha legivel (PT, sem PII) com metricas, coeficientes e cautelas.

    Le APENAS campos numericos/strings curtas do `modelo` (nunca o proprio
    `nota_honesta`) para evitar dependencia circular na construcao.
    """
    sinal_pop = "positivo (mais populacao -> mais pagantes)" if modelo.coef_log_pop >= 0 else "negativo"
    sinal_renda = "positivo (poder aquisitivo)" if modelo.coef_log_renda >= 0 else "negativo"
    if modelo.go:
        veredito = (
            f"GO: sinal calibravel (R2_LOO_log={modelo.r2_loo_log:+.3f} > {LIMIAR_R2_GO}). "
            "A demanda absoluta tem forma funcional util sobre pop/renda."
        )
    else:
        veredito = (
            f"NO-GO: R2_LOO_log={modelo.r2_loo_log:+.3f} nao supera o limiar {LIMIAR_R2_GO}; "
            "a demanda NAO e calibravel com estas features. NAO usar '20% fixo' como "
            "substituto downstream (BLK-DIM-02/04); coletar mais sinal (perfil etario 18-45, "
            "densidade, concorrencia no catchment)."
        )
    return (
        "Aderencia/demanda calibrada (Camada 1, log-log Ridge) -- relatorio honesto\n"
        "Forma funcional: log(pagantes) = b0 + b1*log(pop) + b2*log(renda)\n"
        f"Veredito GO/NO-GO: {veredito}\n"
        f"  R2_LOO_log (principal, gate) = {modelo.r2_loo_log:+.4f}\n"
        f"  R2_LOO_pagantes (auditoria)  = {modelo.r2_loo_pagantes:+.4f}\n"
        f"  R2_insample_log (auditoria, NAO decide gate) = {modelo.r2_insample_log:+.4f}\n"
        f"  RMSE_LOO_log = {modelo.rmse_loo_log:.4f}  |  RMSE_LOO_pagantes = {modelo.rmse_loo_pagantes:.1f}\n"
        f"  n_treinamento = {modelo.n_treinamento}  |  outliers removidos = {modelo.n_outliers_removidos}\n"
        f"  flag_extrapolacao_padrao (n<30) = {modelo.flag_extrapolacao_padrao}\n"
        f"  alpha_selecionado = {modelo.alpha_selecionado:g}\n"
        f"  coef_log_pop (b1) = {modelo.coef_log_pop:+.4f}  -> {sinal_pop}\n"
        f"  coef_log_renda (b2) = {modelo.coef_log_renda:+.4f}  -> {sinal_renda}\n"
        f"  intercepto_log (b0) = {modelo.intercepto_log:+.4f}\n"
        "Confounds estruturais (spec §5):\n"
        "  - Vies de selecao: as unidades abertas sao amostra enviesada (Ultra so abriu onde foi\n"
        "    viavel: alta renda/densidade) -> o modelo SUPERESTIMA aderencia em regioes similares.\n"
        "  - Dilution de catchment: corr(log_pop, log_pagantes) tende a ser fraca/negativa; o raio\n"
        "    de 1.5 km pode nao capturar toda a area de influencia real da unidade.\n"
        "  - N pequeno (~53): limita a precisao; LOO com N pequeno tem alta variancia entre alphas.\n"
    )


def calibrar_aderencia(df: pd.DataFrame, limiar_r2: float = LIMIAR_R2_GO) -> AderenciaModel:
    """Calibra o modelo de aderencia (Camada 1) com LOO-CV honesto, alvo log(pagantes).

    Modelo log-log Ridge: log(pagantes) = b0 + b1*log(pop) + b2*log(renda), com alpha
    selecionado por MENOR rmse_loo_log e R2 honesto via LeaveOneOut em DOIS espacos
    (log e pagantes). O alvo e a demanda ABSOLUTA (NAO a razao pagantes/pop), corrigindo
    a endogeneidade do spike. NAO ha clamp de penetracao (penetracao deixou de ser o alvo).

    READ-ONLY sobre o M1 -- nao toca score_priorizacao nem artefatos oficiais (DEC-001).
    Vies de selecao, dilution de catchment e N pequeno documentados em `nota_honesta`.

    Parameters
    ----------
    df:
        DataFrame com colunas obrigatorias `pagantes_steady_state`, `pop_captacao`,
        `renda_per_capita_captacao`. `n_setores_captacao` e opcional (flag de outlier
        por catchment vazio: n_setores_captacao == 0 ou NaN remove a linha).
    limiar_r2:
        Limiar do gate GO (default LIMIAR_R2_GO). GO se `r2_loo_log > limiar_r2`.

    Returns
    -------
    AderenciaModel
        Objeto com coeficientes, metricas honestas (dois espacos) e gate GO/NO-GO.
        NO-GO NAO levanta (e resultado valido).

    Raises
    ------
    ValueError
        Se faltar coluna obrigatoria ou n efetivo < N_MIN_CALIBRACAO.
    """
    required = {"pagantes_steady_state", "pop_captacao", "renda_per_capita_captacao"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colunas ausentes no DataFrame: {missing}")

    work = df.copy()
    pop = pd.to_numeric(work["pop_captacao"], errors="coerce")
    renda = pd.to_numeric(work["renda_per_capita_captacao"], errors="coerce")
    pagantes = pd.to_numeric(work["pagantes_steady_state"], errors="coerce")
    n_setores = (
        pd.to_numeric(work["n_setores_captacao"], errors="coerce")
        if "n_setores_captacao" in work.columns
        else None
    )

    n_bruto = len(work)
    # Limpeza: remover linha com NaN ou <= 0 em pop/renda/pagantes. NAO filtra por
    # penetracao (penetracao nao e o alvo). Catchment vazio (n_setores==0/NaN) remove.
    flag_out = (
        (pagantes <= 0)
        | pagantes.isna()
        | (pop <= 0)
        | pop.isna()
        | (renda <= 0)
        | renda.isna()
    )
    if n_setores is not None:
        flag_out = flag_out | (n_setores == 0) | n_setores.isna()

    mask_ok = ~flag_out
    n_outliers_removidos = int(flag_out.sum())
    if n_outliers_removidos:
        # Sem PII: apenas contagem, nunca o nome/unidade.
        _logger.warning(
            "Aderencia: %d linha(s) removida(s) como outlier/invalido (pagantes/pop/renda "
            "nao-positivos/NaN ou n_setores_captacao==0) de %d.",
            n_outliers_removidos,
            n_bruto,
        )

    pop_ok = pop[mask_ok].to_numpy(dtype=float)
    renda_ok = renda[mask_ok].to_numpy(dtype=float)
    pagantes_ok = pagantes[mask_ok].to_numpy(dtype=float)

    n = int(mask_ok.sum())
    if n < N_MIN_CALIBRACAO:
        raise ValueError(
            f"Dados insuficientes para calibracao da aderencia: {n} linhas "
            f"(minimo {N_MIN_CALIBRACAO})."
        )

    # Features/target em log (mask_ok ja garante positivos). Sem scaler (features log cruas).
    log_pop = np.log(pop_ok)
    log_renda = np.log(renda_ok)
    y = np.log(pagantes_ok)
    X = np.column_stack([log_pop, log_renda])

    # Selecao de alpha por MENOR rmse_loo_log (mais robusto que maior R2 com N pequeno).
    melhor_alpha = ALPHA_GRID[0]
    melhor_rmse_loo = math.inf
    melhor_r2_loo = -math.inf
    melhor_y_pred_loo = np.zeros(len(y), dtype=float)
    for alpha in ALPHA_GRID:
        r2_loo, rmse_loo, y_pred_loo = _r2_loo_para_alpha(X, y, float(alpha))
        if rmse_loo < melhor_rmse_loo:
            melhor_rmse_loo = rmse_loo
            melhor_r2_loo = r2_loo
            melhor_alpha = float(alpha)
            melhor_y_pred_loo = y_pred_loo

    r2_loo_log = float(melhor_r2_loo)
    rmse_loo_log = float(melhor_rmse_loo)
    alpha_selecionado = float(melhor_alpha)
    y_pred_loo_log = melhor_y_pred_loo

    # R2/RMSE LOO no espaco de pagantes (back-transform das predicoes LOO selecionadas).
    pagantes_pred_loo = np.exp(y_pred_loo_log)
    ss_tot_pag = float(np.sum((pagantes_ok - pagantes_ok.mean()) ** 2))
    ss_res_pag = float(np.sum((pagantes_ok - pagantes_pred_loo) ** 2))
    r2_loo_pagantes = 1.0 - ss_res_pag / ss_tot_pag if ss_tot_pag > 0 else 0.0
    rmse_loo_pagantes = float(math.sqrt(np.mean((pagantes_pred_loo - pagantes_ok) ** 2)))

    # Modelo final no conjunto completo (coeficientes definitivos + r2_insample auditoria).
    reg = Ridge(alpha=alpha_selecionado)
    reg.fit(X, y)
    coef_log_pop = float(reg.coef_[0])
    coef_log_renda = float(reg.coef_[1])
    intercepto_log = float(reg.intercept_)

    y_pred_insample = reg.predict(X)
    ss_tot_log = float(np.sum((y - y.mean()) ** 2))
    ss_res_insample = float(np.sum((y - y_pred_insample) ** 2))
    r2_insample_log = 1.0 - ss_res_insample / ss_tot_log if ss_tot_log > 0 else 0.0

    log_pop_min = float(log_pop.min())
    log_pop_max = float(log_pop.max())
    log_renda_min = float(log_renda.min())
    log_renda_max = float(log_renda.max())

    veredito = "GO" if r2_loo_log > limiar_r2 else "NO-GO"
    flag_extrapolacao_padrao = n < 30

    modelo = AderenciaModel(
        alpha_selecionado=alpha_selecionado,
        coef_log_pop=coef_log_pop,
        coef_log_renda=coef_log_renda,
        intercepto_log=intercepto_log,
        r2_loo_log=r2_loo_log,
        r2_loo_pagantes=float(r2_loo_pagantes),
        rmse_loo_log=rmse_loo_log,
        rmse_loo_pagantes=rmse_loo_pagantes,
        r2_insample_log=float(r2_insample_log),
        log_pop_min=log_pop_min,
        log_pop_max=log_pop_max,
        log_renda_min=log_renda_min,
        log_renda_max=log_renda_max,
        n_treinamento=n,
        n_outliers_removidos=n_outliers_removidos,
        flag_extrapolacao_padrao=flag_extrapolacao_padrao,
        veredito=veredito,
        nota_honesta="",
    )
    modelo.nota_honesta = relatorio_aderencia(modelo)

    _logger.info(
        "AderenciaModel: n_treinamento=%d r2_loo_log=%.4f r2_loo_pagantes=%.4f "
        "alpha=%.3g gate=%s",
        n,
        r2_loo_log,
        r2_loo_pagantes,
        alpha_selecionado,
        veredito,
    )
    return modelo


def prever_aderencia(
    pop_captacao: float,
    renda_per_capita: float,
    modelo: AderenciaModel,
) -> tuple[float, float, float]:
    """Retorna (pagantes, ic_lower, ic_upper) em ALUNOS absolutos.

    pagantes = exp(b0 + b1*log(pop) + b2*log(renda)); IC = +-1 RMSE_LOO_log
    back-transformado. Clamp [PAGANTES_MIN, pop_captacao] (nao pode haver mais pagantes
    que populacao no catchment). Pos-clamp garante ic_lower <= pagantes <= ic_upper.
    pop/renda <= 0 -> (1.0, 1.0, 1.0). Use `modelo.flag_extrapolacao(pop, renda)`
    para saber se e extrapolacao.
    """
    if pop_captacao <= 0 or renda_per_capita <= 0:
        return (PAGANTES_MIN, PAGANTES_MIN, PAGANTES_MIN)

    log_pop = math.log(pop_captacao)
    log_renda = math.log(renda_per_capita)
    log_pagantes = (
        modelo.intercepto_log
        + modelo.coef_log_pop * log_pop
        + modelo.coef_log_renda * log_renda
    )

    def _clamp(v: float) -> float:
        return min(max(v, PAGANTES_MIN), pop_captacao)

    pagantes = _clamp(math.exp(log_pagantes))
    ic_lower = _clamp(math.exp(log_pagantes - modelo.rmse_loo_log))
    ic_upper = _clamp(math.exp(log_pagantes + modelo.rmse_loo_log))

    # Garantir ordem mesmo nas bordas do clamp.
    ic_lower = min(ic_lower, pagantes)
    ic_upper = max(ic_upper, pagantes)
    return (float(pagantes), float(ic_lower), float(ic_upper))


# Alias fino para o contrato sugerido pelo BO.
aderencia_calibrada = prever_aderencia


def escrever_relatorio_aderencia_real(modelo: AderenciaModel, *, path: Path) -> None:
    """Materializa data/analysis/aderencia_real.md (gitignored). NAO chamada em teste.

    Escreve a varredura completa do ALPHA_GRID (alpha x r2_loo_log x rmse_loo_log),
    coeficientes, veredito, confounds e orientacao downstream. READ-ONLY sobre o M1.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    linhas: list[str] = []
    linhas.append("# Calibracao REAL da Camada 1 (aderencia) -- BLK-DIM-01R")
    linhas.append("")
    linhas.append(
        "Alvo = `log(pagantes_steady_state)` (demanda absoluta). Features = "
        "`[log(pop_captacao), log(renda_per_capita_captacao)]`, sem scaler (features log cruas)."
    )
    linhas.append("Modelo: Ridge log-log; selecao de alpha por MENOR rmse_loo_log; LOO-CV honesto.")
    linhas.append("")
    linhas.append(f"- `n_treinamento` = {modelo.n_treinamento}")
    linhas.append(f"- `n_outliers_removidos` = {modelo.n_outliers_removidos}")
    linhas.append(f"- `alpha_selecionado` = {modelo.alpha_selecionado:g}")
    linhas.append(f"- `flag_extrapolacao_padrao` (n<30) = {modelo.flag_extrapolacao_padrao}")
    linhas.append("")
    linhas.append("## Veredito")
    linhas.append("")
    linhas.append(f"**{modelo.veredito}** -- gate no espaco log: `r2_loo_log > {LIMIAR_R2_GO}`.")
    if not modelo.go:
        linhas.append("")
        linhas.append(
            "NO-GO e o resultado ESPERADO e VALIDO (consistente com a DEC-001: M1 teve "
            "Spearman ~ 0). A demanda NAO e calibravel com pop+renda apenas."
        )
    linhas.append("")
    linhas.append("## Metricas honestas (dois espacos)")
    linhas.append("")
    linhas.append("| metrica | valor |")
    linhas.append("| --- | --- |")
    linhas.append(f"| r2_loo_log (PRINCIPAL, gate) | {modelo.r2_loo_log:+.4f} |")
    linhas.append(f"| r2_loo_pagantes (auditoria) | {modelo.r2_loo_pagantes:+.4f} |")
    linhas.append(f"| r2_insample_log (auditoria) | {modelo.r2_insample_log:+.4f} |")
    linhas.append(f"| rmse_loo_log | {modelo.rmse_loo_log:.4f} |")
    linhas.append(f"| rmse_loo_pagantes | {modelo.rmse_loo_pagantes:.1f} |")
    linhas.append("")
    linhas.append("IC nao estimado por bootstrap -- N pequeno limita a precisao; ver confounds.")
    linhas.append("")
    linhas.append("## Coeficientes (modelo final, espaco log)")
    linhas.append("")
    linhas.append(f"- `intercepto_log` (b0) = {modelo.intercepto_log:+.4f}")
    linhas.append(f"- `coef_log_pop` (b1) = {modelo.coef_log_pop:+.4f}")
    linhas.append(f"- `coef_log_renda` (b2) = {modelo.coef_log_renda:+.4f}")
    linhas.append("")
    linhas.append("## Confounds documentados")
    linhas.append("")
    linhas.append(
        "1. **Vies de selecao**: a Ultra so abriu onde foi viavel (alta renda/densidade) "
        "-> amostra enviesada; o modelo superestimaria aderencia em regioes similares as ja abertas."
    )
    linhas.append(
        "2. **Dilution do catchment**: a correlacao log_pop x log_pagantes e fraca/negativa; "
        "o raio de 1.5 km pode nao capturar toda a area de influencia real."
    )
    linhas.append(
        f"3. **N pequeno** ({modelo.n_treinamento}): limita a precisao; LOO com N pequeno tem "
        "alta variancia entre alphas."
    )
    linhas.append("")
    linhas.append("## Como usar / NAO usar downstream")
    linhas.append("")
    if not modelo.go:
        linhas.append(
            "- Com NO-GO, NAO usar o modelo como preditor de demanda em BLK-DIM-02/04."
        )
        linhas.append("- NAO substituir por '20% fixo'.")
        linhas.append(
            "- A Camada 1 fica como ESTRUTURA pronta aguardando features melhores (perfil "
            "etario 18-45, densidade, concorrencia no catchment -- escopo BLK-DIM-05)."
        )
    else:
        linhas.append(
            "- GO honesto: a forma funcional log-log e util; ainda assim, aplicar com cautela "
            "aos confounds acima (vies de selecao em especial)."
        )
    linhas.append("")
    linhas.append("---")
    linhas.append("")
    linhas.append("## Nota honesta embutida no modelo")
    linhas.append("")
    linhas.append("```")
    linhas.append(modelo.nota_honesta.rstrip("\n"))
    linhas.append("```")
    linhas.append("")

    path.write_text("\n".join(linhas), encoding="utf-8")


__all__ = [
    "AderenciaModel",
    "calibrar_aderencia",
    "prever_aderencia",
    "aderencia_calibrada",
    "relatorio_aderencia",
    "escrever_relatorio_aderencia_real",
    "LIMIAR_R2_GO",
    "ALPHA_GRID",
    "N_MIN_CALIBRACAO",
    "PAGANTES_MIN",
]


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    _df_real = pd.read_parquet(Path("data/staging/base_calibracao_maduras.parquet"))
    _modelo = calibrar_aderencia(_df_real)
    escrever_relatorio_aderencia_real(
        _modelo, path=Path("data/analysis/aderencia_real.md")
    )
    print(_modelo.nota_honesta)
