"""BLK-LTV-03 — Correlacao territorio x retencao/LTV (READ-ONLY, gate de decisao).

Correlaciona bivariadamente (Spearman rho + IC95 bootstrap por par) 7 features
TERRITORIAIS do hexagono da unidade contra 3 alvos de retencao/LTV, sobre
`data/staging/unidade_territorio_retencao.parquet` (88x36; BLK-LTV-02). Emite um
veredito GO/NO-GO MECANICO com os confounds declarados (maturidade nao-controlavel,
N pequeno, selecao de sobreviventes, 32 unidades sem hex_id, colinearidade). Este
bloco NAO cria nenhum score -- e o gate de decisao do epic BLK-LTV: correlacao forte
(GO) libera o BLK-LTV-04 (score M2, com DEC + gate humano proprios); correlacao fraca
(NO-GO, resultado LEGITIMO) encerra o epic em consolidacao de dados.

Metodologia (DEC-008):
  - Spearman rho por par `feature_territorial x alvo`, com IC95 por bootstrap dos
    pares (`np.random.default_rng(SEED)`, determinista; >=1000 reamostras).
  - R2 in-sample BANIDO como desempenho (este bloco e correlacao pura -- nenhum R2).
  - N pequeno (56/44/49): IC obrigatorio; IC cruzando zero e desfecho honesto.
  - Eixo RANKING: alvos `PROB_CANCEL_90D_MEDIA` e `LTV_PROSPECTIVO_12M_MEDIANO`
    no universo N=56 (hex_id notna). Eixo ABSOLUTO: `prob_cancel_90d_media_absoluta`
    (ja NaN fora do subset "Sim"; o drop-por-NaN do par entrega o N efetivo).

GUARDRAILS (DEC-001/DEC-008/DEC-009; CLAUDE.md §5):
  - READ-ONLY sobre o M1: NAO recalcula `score_priorizacao`/`hex_score_estrutural`/
    pesos (renda=0.40/pop=0.60); NAO toca carteira/plano/artefatos oficiais. O
    `score_priorizacao` aqui e apenas uma FEATURE territorial LIDA.
  - DEC-008: Spearman + bootstrap/IC; NO-GO e resultado VALIDO -- NAO forcar GO;
    R2 in-sample BANIDO como desempenho.
  - DEC-009: correlaciona RETENCAO x territorio (pergunta aberta do epic), NAO
    previsao de DEMANDA; PROIBIDO usar qualquer output como preditor geografico de
    magnitude de demanda ou ajuste do `score_priorizacao`.
  - Pacote disjunto `lifetime/`: NAO importa de `pipelines/m1/`, `dashboard/`,
    `censo_*`, `api`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

_logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Constantes
# --------------------------------------------------------------------------- #
N_BOOTSTRAP: int = 1000  # >= 500 exigido; 1000 p/ IC mais estavel em N pequeno
SEED: int = 42  # RNG fixo p/ reprodutibilidade (np.random.default_rng)
LIMIAR_RHO_GO: float = 0.30  # |rho| minimo p/ GO (relevancia material; documentado)
N_MIN_PAR: int = 10  # abaixo disso o par vira "n/d" (variancia/robustez insuficiente)

# As 7 features TERRITORIAIS (lidas de unidade_territorio_retencao.parquet).
FEATURES_TERRITORIAIS: tuple[str, ...] = (
    "renda_per_capita",
    "score_priorizacao",
    "score_expansao_hibrido",
    "score_oportunidade_residual",
    "n_concorrentes_mapeados_1km",
    "densidade_pop_setor_hab_km2",
    "score_setor_2022_calibrado",
)

# Alvos do eixo RANKING (universo N=56, hex_id notna).
ALVOS_RANKING: tuple[str, ...] = (
    "PROB_CANCEL_90D_MEDIA",
    "LTV_PROSPECTIVO_12M_MEDIANO",
)

# Alvo do eixo ABSOLUTO (coluna derivada ja NaN fora do subset "Sim").
ALVO_ABSOLUTO: str = "prob_cancel_90d_media_absoluta"

# Lista EXPLICITA e DETERMINISTICA dos 21 pares a testar:
#   14 do eixo ranking (7 features x 2 alvos) + 7 do eixo absoluto (7 features x 1 alvo).
PARES: tuple[tuple[str, str], ...] = tuple(
    [(feat, alvo) for alvo in ALVOS_RANKING for feat in FEATURES_TERRITORIAIS]
    + [(feat, ALVO_ABSOLUTO) for feat in FEATURES_TERRITORIAIS]
)

# Rotulo literal exigido caso algum R2 fosse reportado (NAO usado: correlacao pura).
_ROTULO_INSAMPLE: str = "apenas auditoria -- NAO usar como desempenho"


# --------------------------------------------------------------------------- #
# Dataclass de resultado por par
# --------------------------------------------------------------------------- #
@dataclass
class ResultadoPar:
    """Resultado da correlacao bivariada de um par `(feature, target)`.

    `rho`/`ci_low`/`ci_high`/`p_value` sao NaN quando `n < N_MIN_PAR` ou nao ha
    variancia em x ou y. `ic_cruza_zero` e True nesses casos degenerados (honesto:
    sem sinal utilizavel).
    """

    feature: str
    target: str
    n: int  # N efetivo (linhas com AMBAS as variaveis nao-NaN)
    rho: float  # Spearman rho (nan se n < N_MIN_PAR ou sem variancia)
    ci_low: float  # percentil 2.5 do bootstrap
    ci_high: float  # percentil 97.5 do bootstrap
    p_value: float  # p de scipy.stats.spearmanr
    eixo: str  # "ranking" (N=56) | "absoluto" (N<=44 derivado)
    ic_cruza_zero: bool  # ci_low <= 0 <= ci_high (ou IC nao-finito)


# --------------------------------------------------------------------------- #
# Loader privado (READ-ONLY)
# --------------------------------------------------------------------------- #
def _carregar_dataset(path: Path) -> pd.DataFrame:
    """Le unidade_territorio_retencao.parquet. READ-ONLY; nunca escreve."""
    return pd.read_parquet(path)


# --------------------------------------------------------------------------- #
# Bootstrap do IC95 do Spearman rho
# --------------------------------------------------------------------------- #
def _bootstrap_spearman_ci(
    x: np.ndarray, y: np.ndarray, *, n_boot: int = N_BOOTSTRAP, seed: int = SEED
) -> tuple[float, float]:
    """IC95 (2.5%, 97.5%) do Spearman rho por bootstrap dos pares (x, y), seed fixo.

    RNG: `np.random.default_rng(seed)` (determinista; NAO o RNG global). Reamostra
    com reposicao os indices, recalcula `spearmanr`; descarta reamostras sem
    variancia (`unique(xb) < 2` ou `unique(yb) < 2`). Teto de tentativas `10 * n_boot`.
    Retorna `(nan, nan)` se `x`/`y` tem < N_MIN_PAR pontos ou nenhuma reamostra valida.

    Determinismo: mesmo `(x, y, seed)` -> mesmo IC (testado explicitamente).
    """
    m = len(x)
    if m < N_MIN_PAR:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    valores: list[float] = []
    tentativas = 0
    teto = 10 * n_boot
    while len(valores) < n_boot and tentativas < teto:
        tentativas += 1
        idx = rng.integers(0, m, size=m)
        xb = x[idx]
        yb = y[idx]
        if np.unique(xb).size < 2 or np.unique(yb).size < 2:
            continue
        rho, _p = spearmanr(xb, yb)
        if np.isfinite(rho):
            valores.append(float(rho))
    if not valores:
        return (float("nan"), float("nan"))
    arr = np.asarray(valores, dtype=float)
    return (float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5)))


# --------------------------------------------------------------------------- #
# Funcao principal publica
# --------------------------------------------------------------------------- #
def analisar_correlacao_territorio_retencao(df: pd.DataFrame) -> list[ResultadoPar]:
    """Correlacao bivariada Spearman + IC95 bootstrap por par de `PARES`.

    Para cada `(feature, target)`: dropa linhas com QUALQUER das duas variaveis NaN,
    calcula Spearman rho + p + IC95 bootstrap sobre o N efetivo, e classifica
    `ic_cruza_zero`. READ-ONLY: nunca muta `df` nem escreve disco. Retorna a lista na
    ordem determinista de `PARES` (NAO ordena por rho, para nao editorializar).
    """
    resultados: list[ResultadoPar] = []
    for feature, target in PARES:
        eixo = "absoluto" if target == ALVO_ABSOLUTO else "ranking"
        if feature not in df.columns or target not in df.columns:
            resultados.append(
                ResultadoPar(
                    feature=feature,
                    target=target,
                    n=0,
                    rho=float("nan"),
                    ci_low=float("nan"),
                    ci_high=float("nan"),
                    p_value=float("nan"),
                    eixo=eixo,
                    ic_cruza_zero=True,
                )
            )
            continue

        x = pd.to_numeric(df[feature], errors="coerce")
        y = pd.to_numeric(df[target], errors="coerce")
        mask = x.notna() & y.notna()
        n = int(mask.sum())
        xm = x[mask]
        ym = y[mask]

        if n < N_MIN_PAR or xm.nunique() < 2 or ym.nunique() < 2:
            resultados.append(
                ResultadoPar(
                    feature=feature,
                    target=target,
                    n=n,
                    rho=float("nan"),
                    ci_low=float("nan"),
                    ci_high=float("nan"),
                    p_value=float("nan"),
                    eixo=eixo,
                    ic_cruza_zero=True,
                )
            )
            continue

        xarr = xm.to_numpy(dtype=float)
        yarr = ym.to_numpy(dtype=float)
        rho, p = spearmanr(xarr, yarr)
        ci_low, ci_high = _bootstrap_spearman_ci(xarr, yarr)
        ic_cruza_zero = not (np.isfinite(ci_low) and np.isfinite(ci_high)) or (
            ci_low <= 0.0 <= ci_high
        )
        resultados.append(
            ResultadoPar(
                feature=feature,
                target=target,
                n=n,
                rho=float(rho),
                ci_low=float(ci_low),
                ci_high=float(ci_high),
                p_value=float(p),
                eixo=eixo,
                ic_cruza_zero=bool(ic_cruza_zero),
            )
        )
    return resultados


# --------------------------------------------------------------------------- #
# Regra de veredito (mecanica; sem editorializar)
# --------------------------------------------------------------------------- #
def _veredito(resultados: list[ResultadoPar]) -> tuple[str, str]:
    """Retorna (veredito, justificativa) MECANICO.

    GO se e somente se EXISTE >=1 par com IC95 sem cruzar zero E `|rho| >= LIMIAR_RHO_GO`
    (0.30). NO-GO em qualquer outro caso. NUNCA levanta excecao (NO-GO e resultado
    VALIDO -- DEC-008).
    """
    aprovados = [
        r
        for r in resultados
        if (not r.ic_cruza_zero)
        and np.isfinite(r.rho)
        and abs(r.rho) >= LIMIAR_RHO_GO
    ]
    if aprovados:
        detalhe = "; ".join(
            f"{r.feature} x {r.target} (rho={r.rho:+.3f}, "
            f"IC95=[{r.ci_low:+.3f}, {r.ci_high:+.3f}], eixo={r.eixo})"
            for r in aprovados
        )
        justificativa = (
            f"GO: {len(aprovados)} par(es) com IC95 sem cruzar zero E |rho| >= "
            f"{LIMIAR_RHO_GO:.2f}: {detalhe}. Habilita (sob DEC + gate humano proprios) "
            "reabrir o BLK-LTV-04 (score M2). NAO cria score neste bloco."
        )
        return "GO", justificativa

    justificativa = (
        f"NO-GO: nenhum par atinge simultaneamente IC95 sem cruzar zero E |rho| >= "
        f"{LIMIAR_RHO_GO:.2f}. Consistente com N pequeno (56/44/49) + confound de "
        "maturidade nao-controlavel. NO-GO e resultado VALIDO (DEC-008): o epic BLK-LTV "
        "encerra em consolidacao de dados (LTV-01/02 como ativo), sem score."
    )
    return "NO-GO", justificativa


# --------------------------------------------------------------------------- #
# Relatorio (funcao pura de string + writer)
# --------------------------------------------------------------------------- #
def _fmt(v: float, nd: int = 3) -> str:
    """Formata float com nd casas; 'n/d' se nao-finito."""
    return f"{v:.{nd}f}" if np.isfinite(v) else "n/d"


def _linha_par(r: ResultadoPar) -> str:
    ic = f"[{_fmt(r.ci_low)}, {_fmt(r.ci_high)}]" if np.isfinite(r.ci_low) else "n/d"
    cruza = "sim" if r.ic_cruza_zero else "NAO"
    return (
        f"| {r.feature} | {r.target} | {r.n} | {_fmt(r.rho)} | {ic} | "
        f"{_fmt(r.p_value, 4)} | {cruza} |"
    )


def _montar_relatorio(
    resultados: list[ResultadoPar], veredito: str, justificativa: str
) -> str:
    """Monta a string markdown do relatorio (funcao PURA; nao toca disco)."""
    ranking = [r for r in resultados if r.eixo == "ranking"]
    absoluto = [r for r in resultados if r.eixo == "absoluto"]

    def _ns(rs: list[ResultadoPar]) -> str:
        vals = sorted({r.n for r in rs})
        return ", ".join(str(v) for v in vals) if vals else "n/d"

    L: list[str] = []
    L.append("# Correlacao territorio x retencao/LTV -- BLK-LTV-03")
    L.append("")
    L.append(
        "READ-ONLY sobre o M1 (DEC-001/DEC-008/DEC-009). NAO recalcula "
        "`score_priorizacao`/`hex_score_estrutural`/pesos (renda=0.40/pop=0.60), "
        "carteira, plano nem artefatos oficiais. `score_priorizacao` e apenas uma "
        "FEATURE territorial LIDA."
    )
    L.append("")
    L.append(
        "Este bloco NAO cria score -- BLK-LTV-04 e CONDICIONAL ao GO, com DEC + gate "
        "humano proprios. NO-GO e resultado LEGITIMO e encerra o epic em consolidacao "
        "de dados (LTV-01/02 como ativo)."
    )
    L.append("")
    L.append(
        f"Metodo: Spearman rho por par + IC95 bootstrap ({N_BOOTSTRAP} reamostras, "
        f"seed={SEED}, np.random.default_rng). R2 in-sample BANIDO como desempenho "
        "(correlacao pura, nenhum R2 calculado). Regra GO/NO-GO abaixo."
    )
    L.append("")
    L.append("## 1. Amostra")
    L.append("")
    L.append(
        "- Universo principal: **N=56** (unidades com `hex_id` notna; 32 das 88 sem "
        "hex_id ficam de fora do eixo ranking)."
    )
    L.append(
        "- Eixo ABSOLUTO usa `prob_cancel_90d_media_absoluta` (ja NaN fora do subset "
        f"USAR_PROB_ABSOLUTA='Sim') -> N efetivo por par: {_ns(absoluto)}."
    )
    L.append(
        f"- Ns efetivos observados no eixo RANKING: {_ns(ranking)} (features de censo "
        "`densidade_pop_setor_hab_km2`/`score_setor_2022_calibrado` caem por NaN "
        "onde nao ha setor censitario)."
    )
    L.append(
        "- 12 unidades sao \"Apenas Ranking\" (calibracao absoluta nao confiavel, so "
        "ordem) -- por isso os dois eixos NAO sao misturados numa mesma tabela."
    )
    L.append("")
    L.append("## 2. Correlacoes por par -- eixo RANKING (N=56 no topo)")
    L.append("")
    L.append("| feature | target | N | rho | IC95 | p | IC cruza 0? |")
    L.append("| --- | --- | ---: | ---: | ---: | ---: | :---: |")
    for r in ranking:
        L.append(_linha_par(r))
    L.append("")
    L.append("## 3. Correlacoes por par -- eixo ABSOLUTO (churn absoluto)")
    L.append("")
    L.append("| feature | target | N | rho | IC95 | p | IC cruza 0? |")
    L.append("| --- | --- | ---: | ---: | ---: | ---: | :---: |")
    for r in absoluto:
        L.append(_linha_par(r))
    L.append("")
    L.append("## 4. Confounds (obrigatorios; declarados, NAO corrigidos)")
    L.append("")
    L.append(
        "1. **Maturidade nao-controlavel**: `unidade_para_motor.parquet` NAO tem data "
        "de abertura (`maturacao_status` 100% `maturacao_indisponivel`; gap G1 da "
        "DEC-001). A retencao/LTV mistura efeito de LOCALIZACAO com TEMPO DE OPERACAO. "
        "Confound estrutural -- declarado, nao silenciado, nem usado para descartar o "
        "resultado."
    )
    L.append(
        "2. **N pequeno (56/44/49)**: IC bootstrap obrigatorio; IC cruzando zero e "
        "desfecho honesto (inconclusivo), NAO evidencia de ausencia de efeito."
    )
    L.append(
        "3. **Selecao de sobreviventes**: as 88 sao unidades OPERANDO; unidades "
        "fechadas nao entram -> pode SUBESTIMAR o efeito do territorio na retencao."
    )
    L.append(
        "4. **32 unidades sem hex_id (36%)**: possivel vies geografico (pior match de "
        "nome) -> o universo N=56 pode nao representar a rede inteira."
    )
    L.append(
        "5. **Colinearidade** entre `renda_per_capita` / `score_priorizacao` / "
        "`score_expansao_hibrido` (o `score_priorizacao` deriva de renda+pop): reportado "
        "BIVARIADO por par; SEM regressao multipla / efeito parcial como desempenho "
        "(DEC-008)."
    )
    L.append("")
    L.append("## 5. Veredito GO/NO-GO (mecanico)")
    L.append("")
    L.append(
        f"Regra: **GO** se e somente se EXISTE >=1 par com IC95 **sem cruzar zero** E "
        f"**|rho| >= {LIMIAR_RHO_GO:.2f}**; **NO-GO** caso contrario. O piso |rho|>=0.30 "
        "exige RELEVANCIA MATERIAL (correlacao ao menos moderada), evitando declarar GO "
        "sobre efeito estatisticamente detectavel porem pequeno demais para sustentar um "
        "score (DEC-008; nao forcar GO). NO-GO e resultado VALIDO."
    )
    L.append("")
    L.append(f"**VEREDITO: {veredito}**")
    L.append("")
    L.append(justificativa)
    L.append("")
    L.append("## 6. Nota de escopo")
    L.append("")
    L.append(
        "PROIBIDO usar qualquer output como preditor geografico de magnitude de demanda "
        "ou ajuste do `score_priorizacao` (DEC-009). Nenhum R2 in-sample reportado como "
        f"desempenho (DEC-008; rotulo reservado: \"{_ROTULO_INSAMPLE}\"). BLK-LTV-04 "
        "(score M2) e bloco separado, condicional ao GO, com DEC propria e gate humano "
        "adicional."
    )
    L.append("")
    return "\n".join(L)


def _escrever_relatorio(texto: str, *, path: Path) -> None:
    """Materializa o relatorio markdown (gitignored). NAO chamada em teste de conteudo."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(texto, encoding="utf-8")
    _logger.info("relatorio BLK-LTV-03 escrito: %s", path)


# --------------------------------------------------------------------------- #
# Orquestrador
# --------------------------------------------------------------------------- #
def run(root: Path | None = None) -> list[ResultadoPar]:
    """Le o parquet, filtra hex_id notna (N=56), roda a analise e grava o relatorio.

    READ-ONLY sobre o M1: le apenas `unidade_territorio_retencao.parquet` e escreve o
    `.md` gitignored. Nenhuma escrita em artefato M1.
    """
    if root is None:
        # src/motor_expansao/lifetime/correlacao_territorio_retencao.py -> parents[3] = raiz
        root = Path(__file__).resolve().parents[3]
    df = _carregar_dataset(root / "data" / "staging" / "unidade_territorio_retencao.parquet")
    df56 = df[df["hex_id"].notna()].copy()  # universo principal N=56
    resultados = analisar_correlacao_territorio_retencao(df56)
    veredito, justificativa = _veredito(resultados)
    texto = _montar_relatorio(resultados, veredito, justificativa)
    _escrever_relatorio(texto, path=root / "data" / "analysis" / "relatorio_correlacao_ltv.md")
    _logger.info("BLK-LTV-03 veredito=%s (%d pares)", veredito, len(resultados))
    return resultados


def main() -> None:
    """Entry point para execucao direta."""
    run()


__all__ = [
    "ResultadoPar",
    "analisar_correlacao_territorio_retencao",
    "_bootstrap_spearman_ci",
    "_veredito",
    "_montar_relatorio",
    "PARES",
    "FEATURES_TERRITORIAIS",
    "ALVOS_RANKING",
    "ALVO_ABSOLUTO",
    "N_BOOTSTRAP",
    "SEED",
    "LIMIAR_RHO_GO",
    "N_MIN_PAR",
    "run",
    "main",
]


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    main()
