"""BLK-TP-07: Huff/gravitacional de captura de concorrentes vs demanda OBSERVADA.

Reabre a Camada 2 da epic BLK-DIM (share gravitacional / captura), mas com a topologia
CORRETA para a Demanda Revelada: o share e do **hexagono candidato** (centroide do hex),
validado OUT-OF-FOLD contra a demanda paga OBSERVADA (`membros`, casada por `hex_id`) em
~16 mil hexes, sob a disciplina DEC-008 (k-fold repetido vs baseline da media; IC95 bootstrap
seed-fixa; R2 in-sample BANIDO do veredito; beta selecionado out-of-fold; flag de extrapolacao).

Emite veredito honesto GO/NO-GO em `data/analysis/huff_captura.md` (gitignored). READ-ONLY sobre
o M1: NAO recalcula `score_priorizacao`/`hex_score_estrutural`/pesos nem toca carteira/plano/
artefatos oficiais. NAO altera a formula do `score_oportunidade_residual` nem regenera nenhum
parquet de staging (isso e o BLK-TP-09, follow-up com DEC + gate proprio).

Decisoes de modelagem (gate humano APROVADO por Felipe Silva em 2026-07-03 -- "aprovar"; as 6
recomendacoes D1..D6 do Planner ficam como recomendadas):
  - D1: atratividade UNITARIA (1.0) por concorrente no modelo PRINCIPAL; capacidade-por-rede
    (anti-PII, `capacidade_clube_validacao.py`) so como SENSIBILIDADE rotulada, FORA do veredito.
  - D2: share do CENTROIDE do hex (`h3.cell_to_latlng(hex_id)`), 1-para-1 com o alvo agregado.
  - D3: grade beta `BETA_GRID=(0.5,1.0,1.5,2.0,3.0)` (importada de huff.py), beta escolhido por
    MENOR RMSE out-of-fold do modelo `log1p(membros) ~ log1p(share_beta)`. Selecao OUT-OF-FOLD.
  - D4: SEM Ultra no denominador do share PRINCIPAL + variante de SENSIBILIDADE "com
    canibalizacao Ultra" rotulada (via `dist_ultra_mais_proxima_m`/`n_unidades_ultra_1km`,
    READ-ONLY), reportada FORA do gate.
  - D5: `membros` (log1p) e o ALVO UNICO do veredito; `alunos_parceiras`/`n_acad_parceiras`
    entram SO como cross-check bivariado (Spearman ANTES do modelo), com caveat de circularidade.
  - D6: baseline da MEDIA (ancora do R2, embutido no k-fold) + baseline GEOMETRICO
    (`log1p(n_concorrentes_no_raio) ~ membros`, contagem-no-raio SEM beta), reportado ao lado --
    se o Huff nao supera a mera contagem no raio, a geometria de distancia NAO agrega.

GUARDRAILS (DEC-001/DEC-008/DEC-009/DEC-012; CLAUDE.md §5):
  - READ-ONLY sobre o M1: nenhuma escrita em score/pesos/carteira/plano/artefatos oficiais.
  - DEC-008: LOO/k-fold vs baseline SEMPRE; R2 in-sample so campo de auditoria rotulado (nunca no
    veredito); IC95 seed=42; beta out-of-fold; flag de extrapolacao; NO-GO e resultado VALIDO.
  - DEC-009: `membros`/`alunos_parceiras` sao ALVO/cross-check OBSERVADO, NUNCA preditor
    geografico de magnitude. A funcao-nucleo `share_huff` (importada de huff.py) e PURA e
    GEOMETRICA -- NUNCA recebe o alvo (vazamento estruturalmente impossivel).
  - DEC-012: pacote `demanda_revelada/` DISJUNTO -- este modulo NUNCA importa de `pipelines/m1/`,
    `censo_*`, `dashboard/` (inclui `analisar_entorno_ponto`!), `api` nem `config.py` raiz. Sem PII
    (zero coluna de COLUNAS_PII_PROIBIDAS em qualquer frame/saida/relatorio); centroide via
    `h3.cell_to_latlng(hex_id)` (NAO le `lat`/`lng`, que sao PII proibidas); `nome_unidade` nunca
    lido; fonte real (NAO_ABRA/) nunca tocada; `data/validacao/*.xlsx` so via a fronteira
    `capacidade_clube_validacao.py` (sensibilidade D1); testes so com fixture sintetica.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import h3
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

# Harness de validacao honesta (Ridge k-fold, IC, alpha por RMSE oof).
from motor_expansao.dimensionamento.aderencia import LIMIAR_R2_GO
from motor_expansao.dimensionamento.backtest_dim import _r2, _rmse

# Nucleo PURO e geometrico do Huff (share nunca recebe o alvo) + constantes de distancia/janela.
from motor_expansao.dimensionamento.huff import (
    BETA_GRID,
    DIST_BASE_KM,
    JANELA_CATCHMENT_KM,
    _carregar_concorrentes,
    _haversine_vec,
    share_huff,
)

# Reuso do harness testado da camada irma (k-fold repetido oof, IC bootstrap, selecao de alpha).
from .calibracao_residual import (
    N_BOOTSTRAP,
    N_PISO_LOO,
    SEED,
    _ic_bootstrap_r2,
    _ic_bootstrap_rho,
    _metodo_validacao,
    _rho_oof,
    _selecionar_alpha_e_oof,
)

# Rede de seguranca anti-PII (mesma lista do contrato da camada).
from .contrato import COLUNAS_PII_PROIBIDAS

_logger = logging.getLogger(__name__)

# Universo de hexes do Motor (DEC-003; usado so para a % de cobertura do join, nao e M1).
_UNIVERSO_MOTOR: int = 1_542_531

# Limiar de suporte do rho_oof (Spearman out-of-fold) para o GO "monotonico".
LIMIAR_RHO_SUPORTE: float = 0.30

# Piso minimo de observacoes para tentar modelar (abaixo disso o oof e degenerado).
N_MIN_MODELO: int = 3

# Rotulo literal exigido para o R2 in-sample (testado por substring -- NAO alterar o texto).
_ROTULO_INSAMPLE = "apenas auditoria -- NAO usar como desempenho"

# Nomes de feature (rotulos, nao PII). O preditor e o SHARE geometrico; a demanda e ALVO.
FEATURE_PRINCIPAL: str = "log1p_share_huff"
FEATURE_BASELINE_GEOMETRICO: str = "log1p_n_conc_no_raio"


# --------------------------------------------------------------------------- #
# Resultado
# --------------------------------------------------------------------------- #
@dataclass
class HuffCapturaResult:
    """Resultado da validacao honesta share Huff (por hex) -> demanda OBSERVADA (`membros`).

    `r2_oof_log` e a metrica-ANCORA (out-of-fold, espaco log, vs media => vs baseline). O veredito
    tambem exige que o Huff supere o baseline GEOMETRICO (contagem-no-raio sem beta) -- senao a
    distancia nao agrega. `rho_oof` e o suporte monotonico. `r2_insample` existe SO para auditoria.
    Sem PII: campos numericos/agregados apenas.
    """

    beta_selecionado: float
    """Beta escolhido por MENOR RMSE medio out-of-fold na varredura do BETA_GRID (D3)."""

    alpha_selecionado: float
    """Alpha do Ridge selecionado por MENOR RMSE out-of-fold (dado o beta selecionado)."""

    coef_share: float
    """Coeficiente do modelo final (log1p(share_huff)), espaco log."""

    intercepto: float
    """Intercepto do modelo final (espaco log)."""

    r2_oof_log: float
    """R2 out-of-fold no espaco log. METRICA-ANCORA do gate (vs media => vs baseline)."""

    rmse_oof_log: float
    """RMSE out-of-fold do modelo Huff (espaco log)."""

    rmse_oof_baseline_log: float
    """RMSE out-of-fold do baseline da media (espaco log)."""

    ic95_r2_oof: tuple[float, float]
    """IC95 (2,5%; 97,5%) do R2_oof_log por bootstrap dos pares (y, y_pred_oof)."""

    rho_oof: float
    """Spearman out-of-fold (predicoes oof concatenadas vs alvo). Metrica de SUPORTE do gate."""

    ic95_rho_oof: tuple[float, float]
    """IC95 (2,5%; 97,5%) do rho_oof por bootstrap dos pares (y, y_pred_oof)."""

    r2_oof_baseline_geometrico: float
    """R2 out-of-fold do baseline GEOMETRICO log1p(n_conc_no_raio) ~ membros (D6b). Ao lado."""

    ic95_r2_oof_baseline_geometrico: tuple[float, float]
    """IC95 do R2_oof do baseline geometrico (auditoria; NAO no veredito)."""

    r2_insample: float
    """R2 in-sample (espaco log). APENAS auditoria -- NAO usar como desempenho (DEC-008)."""

    n_treinamento: int
    """N de hexes usados no modelo (feature/alvo finitos)."""

    n_join: int
    """N do join inner demanda x share por hex_id (antes da limpeza de invalidos)."""

    pct_cobertura_universo: float
    """% do universo de hexes do Motor coberto pelo join (~1%)."""

    n_descartado_invalidos: int
    """N de hexes descartados por NaN/inf em feature/alvo."""

    range_membros: tuple[float, float]
    """(min, max) de `membros` no subset modelado."""

    spearman_bruta: dict[str, tuple[float, float]]
    """Spearman bivariada (share/contagem/dist/cross-check oferta) vs membros, ANTES do modelo."""

    pct_extrapolacao: float
    """% de pontos cuja feature cai fora do envelope min-max de treino (0-100)."""

    flag_extrapolacao_padrao_global: bool
    """True se n_treinamento < N_PISO_LOO (modelo globalmente instavel; degradou p/ LOO)."""

    metodo_validacao: str
    """"kfold_5x5" | "kfold_10x5" | "loo" -- caminho de validacao efetivo."""

    concentracao_uf: dict[str, float]
    """Top-3 UF (% do join) -- caveat de vies metropolitano."""

    rmse_oof_por_beta: dict[float, float]
    """RMSE out-of-fold por beta da grade (auditoria da selecao de beta D3)."""

    sensibilidade_capacidade: dict[str, float] = field(default_factory=dict)
    """Sensibilidade D1b: R2_oof do Huff com atratividade = capacidade mediana por rede. FORA do gate."""

    sensibilidade_ultra: dict[str, float] = field(default_factory=dict)
    """Sensibilidade D4c: R2_oof do Huff com proximidade Ultra como covariavel. FORA do gate."""

    veredito: str = ""
    """"GO" se (ancora R2 + supera baseline geometrico) OU (suporte rho); "NO-GO" caso contrario."""

    tipo_go: str = field(default="")
    """"ancora_r2" | "suporte_rho" | "" -- qual condicao disparou o GO (vazio se NO-GO)."""

    nota_honesta: str = field(default="")
    """Mensagem legivel (PT, sem PII) com metricas, veredito e os confounds obrigatorios."""

    @property
    def go(self) -> bool:
        """True se o gate honesto deu GO."""
        return self.veredito == "GO"


# --------------------------------------------------------------------------- #
# Geometria do centroide do hex (anti-PII: nunca le lat/lng do parquet)
# --------------------------------------------------------------------------- #
def _centroide_hex(hex_id: str) -> tuple[float, float]:
    """Centroide (lat, lng) de um hex H3 via `h3.cell_to_latlng`. `(nan, nan)` se invalido.

    Anti-PII (DEC-012): a geometria vem do PROPRIO `hex_id` (chave de join), NUNCA da coluna
    `lat`/`lng` (que sao COLUNAS_PII_PROIBIDAS).
    """
    try:
        lat, lng = h3.cell_to_latlng(str(hex_id))
        return float(lat), float(lng)
    except (ValueError, TypeError, KeyError):  # hex invalido -> descartado a jusante
        return (float("nan"), float("nan"))


# --------------------------------------------------------------------------- #
# Nucleo por hex: share (PURO, sem alvo) + contagem no raio (baseline geometrico)
# --------------------------------------------------------------------------- #
def share_hex(
    hex_id: str,
    conc_lat: np.ndarray,
    conc_lng: np.ndarray,
    beta: float,
    *,
    janela_km: float = JANELA_CATCHMENT_KM,
    atr_concorrente: float = 1.0,
) -> float:
    """Share gravitacional de Huff do CENTROIDE do hex vs concorrentes na janela. PURO.

    Calcula distancias do centroide do hex aos concorrentes dentro de `janela_km` (via
    `_haversine_vec`, importado) e delega a `share_huff` (importado, PURO). Sem concorrentes na
    janela -> share = 1.0 (monopolio local). Retorna float em [0, 1].

    ANTI-VAZAMENTO (DEC-009): NAO recebe nem usa `membros` (o alvo). O share depende SO da
    geometria (centroide + coords dos concorrentes) e de `beta`/`atr_concorrente` -- o vazamento
    do alvo no previsor e estruturalmente impossivel.
    """
    lat_h, lng_h = _centroide_hex(hex_id)
    if not (np.isfinite(lat_h) and np.isfinite(lng_h)):
        return float("nan")
    dist = _haversine_vec(lat_h, lng_h, conc_lat, conc_lng)
    dist = dist[np.isfinite(dist) & (dist <= janela_km)]
    return share_huff(DIST_BASE_KM, dist, beta, atr_concorrente=atr_concorrente)


def n_conc_no_raio_hex(
    hex_id: str,
    conc_lat: np.ndarray,
    conc_lng: np.ndarray,
    *,
    raio_km: float = DIST_BASE_KM,
) -> float:
    """Numero de concorrentes dentro de `raio_km` do centroide do hex (baseline SEM beta, D6b).

    Baseline GEOMETRICO: mede o poder de mera CONTAGEM de concorrentes no raio, sem decaimento por
    distancia. Se o Huff (com beta) nao supera este baseline, a geometria de distancia nao agrega.
    """
    lat_h, lng_h = _centroide_hex(hex_id)
    if not (np.isfinite(lat_h) and np.isfinite(lng_h)):
        return float("nan")
    d = _haversine_vec(lat_h, lng_h, conc_lat, conc_lng)
    return float(np.sum(np.isfinite(d) & (d <= raio_km)))


def calcular_share_por_hex(
    hexes: list[str],
    conc_lat: np.ndarray,
    conc_lng: np.ndarray,
    beta: float,
    *,
    atr_concorrente: float = 1.0,
) -> np.ndarray:
    """Vetor de shares Huff (1 por hex) para um dado beta. Cada share e PURO (sem alvo)."""
    return np.array(
        [share_hex(h, conc_lat, conc_lng, beta, atr_concorrente=atr_concorrente) for h in hexes],
        dtype=float,
    )


def calcular_n_conc_por_hex(
    hexes: list[str],
    conc_lat: np.ndarray,
    conc_lng: np.ndarray,
    *,
    raio_km: float = DIST_BASE_KM,
) -> np.ndarray:
    """Vetor de contagens de concorrentes no raio (baseline geometrico D6b), 1 por hex."""
    return np.array(
        [n_conc_no_raio_hex(h, conc_lat, conc_lng, raio_km=raio_km) for h in hexes],
        dtype=float,
    )


# --------------------------------------------------------------------------- #
# Correlacoes bivariadas (ANTES do modelo)
# --------------------------------------------------------------------------- #
def correlacoes_bivariadas(df: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """Spearman de cada preditor/covariavel bruta vs `membros` (ANTES do modelo).

    Reporta o alinhamento monotonico ANTES do modelo. `share_huff`/`n_conc_no_raio` sao os
    preditores geometricos; `n_concorrente_lc`/`dist_concorrente_lc_min_m` sao covariaveis do dump;
    `alunos_parceiras`/`n_acad_parceiras` sao OFERTA instalada (cross-check com caveat de
    circularidade rho +0,94, NUNCA alvo/feature do gate). Retorna dict feature -> (rho, p).
    """
    cols = (
        "share_huff",
        "n_conc_no_raio",
        "n_concorrente_lc",
        "dist_concorrente_lc_min_m",
        "alunos_parceiras",
        "n_acad_parceiras",
    )
    alvo = pd.to_numeric(df.get("membros"), errors="coerce")
    mask = alvo.notna()
    out: dict[str, tuple[float, float]] = {}
    y = alvo[mask].to_numpy(dtype=float)
    for c in cols:
        if c not in df.columns:
            out[c] = (float("nan"), float("nan"))
            continue
        x = pd.to_numeric(df[c], errors="coerce")[mask].to_numpy(dtype=float)
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 3 or np.unique(x[ok]).size < 2:
            out[c] = (float("nan"), float("nan"))
            continue
        rho, p = spearmanr(x[ok], y[ok])
        out[c] = (float(rho), float(p))
    return out


# --------------------------------------------------------------------------- #
# Preparacao dos dados
# --------------------------------------------------------------------------- #
def _preparar_xy(
    df: pd.DataFrame, feature_col: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """(X, y, membros, n_descartado) do modelo log1p(membros) ~ log1p(feature_col).

    Alvo `y = log1p(membros)`; feature `X = [log1p(feature_col)]`. Limpa NaN/inf.
    """
    membros = pd.to_numeric(df.get("membros"), errors="coerce").to_numpy(dtype=float)
    feat = pd.to_numeric(df.get(feature_col), errors="coerce").to_numpy(dtype=float)
    X = np.log1p(np.clip(feat, 0.0, None)).reshape(-1, 1)
    y = np.log1p(np.clip(membros, 0.0, None))
    finito = np.isfinite(X).all(axis=1) & np.isfinite(y)
    n_descartado = int((~finito).sum())
    return X[finito], y[finito], membros[finito], n_descartado


def _concentracao_uf(df: pd.DataFrame, *, top: int = 3) -> dict[str, float]:
    """Top-N UF por % do join (caveat de vies). {} se `uf` ausente."""
    if "uf" not in df.columns or df.empty:
        return {}
    vc = (df["uf"].value_counts(normalize=True) * 100.0).round(1)
    return {str(k): float(v) for k, v in vc.head(top).items()}


def _pct_extrapolacao(X: np.ndarray) -> float:
    """% de pontos fora do envelope min-max da feature de treino (contrato honesto)."""
    if X.size == 0:
        return float("nan")
    mn = X.min(axis=0)
    mx = X.max(axis=0)
    fora = ((X < mn) | (X > mx)).any(axis=1)
    return float(100.0 * fora.sum() / len(X))


# --------------------------------------------------------------------------- #
# Selecao de beta out-of-fold (D3) + validacao honesta de UM modelo
# --------------------------------------------------------------------------- #
def _validar_modelo_oof(
    X: np.ndarray, y: np.ndarray, *, metodo: str
) -> tuple[float, np.ndarray, np.ndarray, float, float]:
    """Seleciona alpha por menor RMSE oof e devolve o oof do melhor.

    Delega a `_selecionar_alpha_e_oof` (harness testado). Retorna
    (alpha, y_pred_oof, y_pred_baseline_oof, r2_oof_log, rmse_oof_log).
    """
    return _selecionar_alpha_e_oof(X, y, metodo=metodo)


def _selecionar_beta_oof(
    df: pd.DataFrame,
    hexes: list[str],
    conc_lat: np.ndarray,
    conc_lng: np.ndarray,
    *,
    beta_grid: tuple[float, ...] = BETA_GRID,
    atr_concorrente: float = 1.0,
) -> tuple[float, dict[float, float], pd.DataFrame]:
    """Varre `beta_grid`, recomputa o share por beta, roda o oof, escolhe beta por menor RMSE_oof.

    ANTI-VAZAMENTO: o share e SEMPRE puro (nunca recebe o alvo); a escolha de beta e por desempenho
    OUT-OF-FOLD (nao in-sample). Retorna (beta_selecionado, rmse_oof_por_beta, df_com_share_do_beta).
    """
    melhor_beta = float(beta_grid[0])
    melhor_rmse = float("inf")
    rmse_por_beta: dict[float, float] = {}
    df_melhor = df

    for beta in beta_grid:
        b = float(beta)
        share = calcular_share_por_hex(hexes, conc_lat, conc_lng, b, atr_concorrente=atr_concorrente)
        df_b = df.assign(share_huff=share)
        X, y, _membros, _nd = _preparar_xy(df_b, "share_huff")
        n = int(len(y))
        if n < N_MIN_MODELO:
            rmse_por_beta[b] = float("nan")
            continue
        metodo = _metodo_validacao(n)
        _alpha, _pred, _base, _r2v, rmse_v = _validar_modelo_oof(X, y, metodo=metodo)
        rmse_por_beta[b] = float(rmse_v)
        if np.isfinite(rmse_v) and rmse_v < melhor_rmse:
            melhor_rmse = float(rmse_v)
            melhor_beta = b
            df_melhor = df_b

    return melhor_beta, rmse_por_beta, df_melhor


# --------------------------------------------------------------------------- #
# Sensibilidades rotuladas (FORA do veredito)
# --------------------------------------------------------------------------- #
def _r2_oof_de_feature(df: pd.DataFrame, feature_col: str) -> tuple[float, tuple[float, float]]:
    """R2_oof + IC95 do modelo log1p(membros) ~ log1p(feature_col). Auxiliar de sensibilidade."""
    X, y, _membros, _nd = _preparar_xy(df, feature_col)
    n = int(len(y))
    if n < N_MIN_MODELO:
        return (float("nan"), (float("nan"), float("nan")))
    metodo = _metodo_validacao(n)
    _alpha, y_pred_oof, _base, r2_oof, _rmse_oof = _validar_modelo_oof(X, y, metodo=metodo)
    rng = np.random.default_rng(SEED)
    ic = _ic_bootstrap_r2(y, y_pred_oof, rng)
    return (float(r2_oof), (float(ic[0]), float(ic[1])))


def _sensibilidade_capacidade(
    df_share: pd.DataFrame,
    hexes: list[str],
    conc_lat: np.ndarray,
    conc_lng: np.ndarray,
    beta: float,
    *,
    dir_validacao: Path | None,
) -> dict[str, float]:
    """Sensibilidade D1b: R2_oof do Huff com atratividade = capacidade mediana por rede (anti-PII).

    NAO entra no veredito (rotulada). Usa a capacidade MEDIANA GLOBAL (das redes lidas em
    `data/validacao/`) como atratividade uniforme dos concorrentes -- uma escala constante do share,
    entao mede se um share "por capacidade" (mesmo que grosseiro por rede) desloca o R2_oof. Se as
    bases nao existirem, retorna {} (nada e forcado). Fronteira anti-PII: so um float sai.
    """
    try:
        from .capacidade_clube_validacao import (
            DIR_VALIDACAO_DEFAULT,
            FALLBACK_CAPACIDADE,
            ler_capacidade_clube_por_rede,
        )

        base_dir = dir_validacao if dir_validacao is not None else DIR_VALIDACAO_DEFAULT
        cap = ler_capacidade_clube_por_rede(base_dir)
        # Escala uniforme: mediana das capacidades reais lidas (fallback 2.500 se nada lido).
        atr = float(np.median(list(cap.values()))) if cap else float(FALLBACK_CAPACIDADE)
    except Exception as exc:  # pragma: no cover - base ausente cai fora do gate
        _logger.info("sensibilidade_capacidade indisponivel: %s", exc)
        return {}

    share = calcular_share_por_hex(hexes, conc_lat, conc_lng, beta, atr_concorrente=atr)
    df_cap = df_share.assign(share_huff=share)
    r2_cap, ic_cap = _r2_oof_de_feature(df_cap, "share_huff")
    return {
        "atratividade_uniforme": atr,
        "r2_oof_log": r2_cap,
        "ic95_inf": ic_cap[0],
        "ic95_sup": ic_cap[1],
    }


def _sensibilidade_ultra(df_share: pd.DataFrame) -> dict[str, float]:
    """Sensibilidade D4c: R2_oof do baseline geometrico + proximidade Ultra como covariavel.

    NAO entra no veredito. Usa `n_unidades_ultra_1km`/`dist_ultra_mais_proxima_m` (READ-ONLY, do
    mercado) so como covariaveis de um modelo bivariado com o share, para medir se a proximidade da
    rede Ultra desloca o sinal. Retorna {} se as colunas ultra nao estiverem no frame.
    """
    tem_ultra = any(
        c in df_share.columns for c in ("n_unidades_ultra_1km", "dist_ultra_mais_proxima_m")
    )
    if not tem_ultra or "share_huff" not in df_share.columns:
        return {}
    membros = pd.to_numeric(df_share.get("membros"), errors="coerce").to_numpy(dtype=float)
    y = np.log1p(np.clip(membros, 0.0, None))
    cols_feat = [
        c
        for c in ("share_huff", "n_unidades_ultra_1km", "dist_ultra_mais_proxima_m")
        if c in df_share.columns
    ]
    mats = []
    for c in cols_feat:
        v = pd.to_numeric(df_share[c], errors="coerce").to_numpy(dtype=float)
        mats.append(np.log1p(np.clip(v, 0.0, None)) if c != "share_huff" else np.log1p(np.clip(v, 0.0, None)))
    X = np.column_stack(mats)
    finito = np.isfinite(X).all(axis=1) & np.isfinite(y)
    X, y = X[finito], y[finito]
    n = int(len(y))
    if n < N_MIN_MODELO:
        return {}
    metodo = _metodo_validacao(n)
    _alpha, y_pred_oof, _base, r2_oof, _rmse = _validar_modelo_oof(X, y, metodo=metodo)
    rng = np.random.default_rng(SEED)
    ic = _ic_bootstrap_r2(y, y_pred_oof, rng)
    return {
        "r2_oof_log_com_ultra": float(r2_oof),
        "ic95_inf": float(ic[0]),
        "ic95_sup": float(ic[1]),
        "n_features": float(len(cols_feat)),
    }


# --------------------------------------------------------------------------- #
# Orquestrador de calibracao
# --------------------------------------------------------------------------- #
def calibrar_huff_captura(
    df_join: pd.DataFrame,
    conc_lat: np.ndarray,
    conc_lng: np.ndarray,
    *,
    limiar_r2: float = LIMIAR_R2_GO,
    limiar_rho: float = LIMIAR_RHO_SUPORTE,
    beta_grid: tuple[float, ...] = BETA_GRID,
    dir_validacao: Path | None = None,
    incluir_sensibilidades: bool = True,
) -> HuffCapturaResult:
    """Valida (out-of-fold) o share Huff por hex -> demanda OBSERVADA (`membros`).

    `df_join` deve conter `hex_id`, `membros` (+ opcional `uf`, covariaveis de cross-check, colunas
    ultra). O share e recomputado por beta a partir do CENTROIDE de cada `hex_id` contra
    `(conc_lat, conc_lng)` -- NUNCA usa o alvo. Beta escolhido por menor RMSE_oof (D3); alpha por
    menor RMSE_oof; R2_oof e a ancora e deve superar o baseline geometrico (D6b); rho_oof e o
    suporte. NO-GO NAO levanta (resultado VALIDO, DEC-008).

    READ-ONLY sobre o M1 (DEC-001/009); pacote disjunto (DEC-012); sem PII. `share_huff` PURO.

    Raises
    ------
    ValueError
        Se `df_join` nao tiver `hex_id`/`membros` ou nao restar nenhum hex valido.
    """
    if "hex_id" not in df_join.columns or "membros" not in df_join.columns:
        raise ValueError("`df_join` precisa de `hex_id` e `membros`.")

    n_join = int(len(df_join))
    hexes = df_join["hex_id"].astype(str).tolist()

    # Baseline geometrico D6b: contagem de concorrentes no raio (sem beta), por hex.
    n_conc = calcular_n_conc_por_hex(hexes, conc_lat, conc_lng)
    df_base = df_join.assign(n_conc_no_raio=n_conc)

    # D3: selecao de beta out-of-fold (share sempre puro).
    beta_sel, rmse_por_beta, df_share = _selecionar_beta_oof(
        df_base, hexes, conc_lat, conc_lng, beta_grid=beta_grid
    )

    # Correlacoes bivariadas ANTES do modelo (share do beta selecionado).
    spearman = correlacoes_bivariadas(df_share)

    # Modelo PRINCIPAL: log1p(membros) ~ log1p(share_huff) do beta selecionado.
    X, y, membros_ok, n_descartado = _preparar_xy(df_share, "share_huff")
    n = int(len(y))
    if n == 0:
        raise ValueError("Nenhum hex valido apos a limpeza -- nada a modelar.")

    flag_extrapolacao_padrao_global = n < N_PISO_LOO
    metodo = _metodo_validacao(n)
    alpha, y_pred_oof, y_pred_base_oof, r2_oof_log, rmse_oof_log = _validar_modelo_oof(
        X, y, metodo=metodo
    )
    rmse_oof_baseline_log = _rmse(y, y_pred_base_oof)

    # IC95 do R2_oof e do rho_oof por bootstrap dos pares (seed 42; determinista).
    rng_r2 = np.random.default_rng(SEED)
    ic95_r2 = _ic_bootstrap_r2(y, y_pred_oof, rng_r2)
    rng_rho = np.random.default_rng(SEED)
    ic95_rho = _ic_bootstrap_rho(y, y_pred_oof, rng_rho)
    rho_oof = _rho_oof(y, y_pred_oof)

    # Modelo final no conjunto completo (coeficiente + R2 in-sample AUDITORIA).
    from sklearn.linear_model import Ridge

    reg = Ridge(alpha=alpha)
    reg.fit(X, y)
    coef_share = float(reg.coef_[0])
    intercepto = float(reg.intercept_)
    r2_insample = _r2(y, reg.predict(X))

    pct_extra = _pct_extrapolacao(X)

    # Baseline GEOMETRICO D6b: log1p(n_conc_no_raio) ~ membros (mesma validacao k-fold), AO LADO.
    r2_base_geo, ic95_base_geo = _r2_oof_de_feature(df_share, "n_conc_no_raio")

    # Sensibilidades rotuladas (FORA do gate).
    sens_cap: dict[str, float] = {}
    sens_ultra: dict[str, float] = {}
    if incluir_sensibilidades:
        sens_cap = _sensibilidade_capacidade(
            df_share, hexes, conc_lat, conc_lng, beta_sel, dir_validacao=dir_validacao
        )
        sens_ultra = _sensibilidade_ultra(df_share)

    range_membros = (
        (float(np.min(membros_ok)), float(np.max(membros_ok)))
        if membros_ok.size
        else (float("nan"), float("nan"))
    )

    # Veredito: ancora R2 (E supera baseline geometrico) OU suporte rho.
    supera_baseline_geo = not np.isfinite(r2_base_geo) or (r2_oof_log > r2_base_geo)
    go_ancora = (
        np.isfinite(r2_oof_log)
        and r2_oof_log > limiar_r2
        and np.isfinite(ic95_r2[0])
        and ic95_r2[0] > 0.0
        and supera_baseline_geo
    )
    go_suporte = (
        np.isfinite(rho_oof)
        and rho_oof >= limiar_rho
        and np.isfinite(ic95_rho[0])
        and ic95_rho[0] > 0.0
    )
    if go_ancora:
        veredito, tipo_go = "GO", "ancora_r2"
    elif go_suporte:
        veredito, tipo_go = "GO", "suporte_rho"
    else:
        veredito, tipo_go = "NO-GO", ""

    result = HuffCapturaResult(
        beta_selecionado=float(beta_sel),
        alpha_selecionado=float(alpha),
        coef_share=coef_share,
        intercepto=intercepto,
        r2_oof_log=float(r2_oof_log),
        rmse_oof_log=float(rmse_oof_log),
        rmse_oof_baseline_log=float(rmse_oof_baseline_log),
        ic95_r2_oof=(float(ic95_r2[0]), float(ic95_r2[1])),
        rho_oof=float(rho_oof),
        ic95_rho_oof=(float(ic95_rho[0]), float(ic95_rho[1])),
        r2_oof_baseline_geometrico=float(r2_base_geo),
        ic95_r2_oof_baseline_geometrico=(float(ic95_base_geo[0]), float(ic95_base_geo[1])),
        r2_insample=float(r2_insample),
        n_treinamento=n,
        n_join=n_join,
        pct_cobertura_universo=float(100.0 * n_join / _UNIVERSO_MOTOR),
        n_descartado_invalidos=n_descartado,
        range_membros=range_membros,
        spearman_bruta=spearman,
        pct_extrapolacao=float(pct_extra),
        flag_extrapolacao_padrao_global=flag_extrapolacao_padrao_global,
        metodo_validacao=metodo,
        concentracao_uf=_concentracao_uf(df_share),
        rmse_oof_por_beta=rmse_por_beta,
        sensibilidade_capacidade=sens_cap,
        sensibilidade_ultra=sens_ultra,
        veredito=veredito,
        tipo_go=tipo_go,
    )
    result.nota_honesta = _nota_honesta(result)

    _logger.info(
        "HuffCaptura: n=%d metodo=%s beta=%.2f alpha=%.3g r2_oof_log=%.4f ic95=(%.4f,%.4f) "
        "rho_oof=%.4f base_geo=%.4f gate=%s(%s)",
        n,
        metodo,
        beta_sel,
        alpha,
        r2_oof_log,
        ic95_r2[0],
        ic95_r2[1],
        rho_oof,
        r2_base_geo,
        veredito,
        tipo_go or "n/a",
    )
    return result


# --------------------------------------------------------------------------- #
# Nota honesta + relatorio
# --------------------------------------------------------------------------- #
def _nota_honesta(r: HuffCapturaResult) -> str:
    """Mensagem legivel (PT, sem PII) com metricas, veredito e os confounds obrigatorios."""
    if r.go and r.tipo_go == "ancora_r2":
        cab = (
            f"GO (ancora R2): R2_oof_log={r.r2_oof_log:+.4f} > {LIMIAR_R2_GO} E IC95_inferior="
            f"{r.ic95_r2_oof[0]:+.4f} > 0 E supera o baseline geometrico "
            f"(R2_base_geo={r.r2_oof_baseline_geometrico:+.4f}). O share Huff (com beta/distancia) "
            "prevê a demanda OBSERVADA fora da amostra e a geometria de distancia AGREGA sobre a "
            "mera contagem no raio, RESTRITO ao recorte metropolitano do join (~1%). Integrar a "
            "captura ao residual/carteira e FOLLOW-UP com gate (BLK-TP-09), NAO este bloco."
        )
    elif r.go and r.tipo_go == "suporte_rho":
        cab = (
            f"GO (suporte rho): alinhamento monotonico sem ganho de erro out-of-fold. "
            f"rho_oof={r.rho_oof:+.4f} >= {LIMIAR_RHO_SUPORTE} E IC95_inferior="
            f"{r.ic95_rho_oof[0]:+.4f} > 0, mas a ANCORA R2_oof_log={r.r2_oof_log:+.4f} nao superou "
            f"{LIMIAR_R2_GO}/IC ou nao bateu o baseline geometrico "
            f"(R2_base_geo={r.r2_oof_baseline_geometrico:+.4f}). O share ORDENA a demanda, mas nao "
            "reduz o erro vs a media out-of-fold. Integracao = FOLLOW-UP com gate (BLK-TP-09)."
        )
    else:
        cab = (
            f"NO-GO honesto: R2_oof_log={r.r2_oof_log:+.4f} (limiar {LIMIAR_R2_GO}), IC95="
            f"[{r.ic95_r2_oof[0]:+.4f}, {r.ic95_r2_oof[1]:+.4f}]; "
            f"baseline geometrico R2={r.r2_oof_baseline_geometrico:+.4f}; "
            f"rho_oof={r.rho_oof:+.4f} (limiar {LIMIAR_RHO_SUPORTE}), IC95="
            f"[{r.ic95_rho_oof[0]:+.4f}, {r.ic95_rho_oof[1]:+.4f}]. "
            "O share Huff nao supera o baseline da media de forma materialmente confiavel "
            "out-of-fold nem alcanca alinhamento monotonico com IC valido (ou nao bate a mera "
            "contagem no raio -> a distancia nao agrega). NO-GO e resultado VALIDO (DEC-008)."
        )
    top_uf = ", ".join(f"{k} {v:.1f}%" for k, v in r.concentracao_uf.items()) or "n/d"
    betas = ", ".join(
        f"b={b:g}:{('n/d' if not np.isfinite(v) else f'{v:.4f}')}"
        for b, v in r.rmse_oof_por_beta.items()
    )
    linhas_sens = []
    if r.sensibilidade_capacidade:
        sc = r.sensibilidade_capacidade
        linhas_sens.append(
            f"  Sensibilidade D1b (capacidade/rede, FORA do gate): atratividade uniforme="
            f"{sc.get('atratividade_uniforme', float('nan')):.0f}; R2_oof_log="
            f"{sc.get('r2_oof_log', float('nan')):+.4f} IC95="
            f"[{sc.get('ic95_inf', float('nan')):+.4f}, {sc.get('ic95_sup', float('nan')):+.4f}]"
        )
    if r.sensibilidade_ultra:
        su = r.sensibilidade_ultra
        linhas_sens.append(
            f"  Sensibilidade D4c (proximidade Ultra covariavel, FORA do gate): R2_oof_log="
            f"{su.get('r2_oof_log_com_ultra', float('nan')):+.4f} IC95="
            f"[{su.get('ic95_inf', float('nan')):+.4f}, {su.get('ic95_sup', float('nan')):+.4f}]"
        )
    bloco_sens = ("\n" + "\n".join(linhas_sens)) if linhas_sens else ""
    return (
        "Validacao honesta share Huff (por hex) -> demanda OBSERVADA "
        "(BLK-TP-07, k-fold repetido vs baseline)\n"
        "Alvo: log1p(membros) (demanda paga OBSERVADA); preditor: log1p(share_huff) (PURO, sem "
        "alvo).\n"
        f"Veredito GO/NO-GO: {cab}\n"
        f"  beta_selecionado (out-of-fold, menor RMSE_oof) = {r.beta_selecionado:g} | "
        f"RMSE_oof por beta = [{betas}]\n"
        f"  R2_oof_log (ancora, gate) = {r.r2_oof_log:+.4f} | IC95 = "
        f"[{r.ic95_r2_oof[0]:+.4f}, {r.ic95_r2_oof[1]:+.4f}]\n"
        f"  rho_oof (suporte) = {r.rho_oof:+.4f} | IC95 = "
        f"[{r.ic95_rho_oof[0]:+.4f}, {r.ic95_rho_oof[1]:+.4f}]\n"
        f"  R2_oof baseline GEOMETRICO log1p(n_conc_no_raio) (D6b, AO LADO) = "
        f"{r.r2_oof_baseline_geometrico:+.4f} | IC95 = "
        f"[{r.ic95_r2_oof_baseline_geometrico[0]:+.4f}, "
        f"{r.ic95_r2_oof_baseline_geometrico[1]:+.4f}]\n"
        f"  R2_insample = {r.r2_insample:+.4f} ({_ROTULO_INSAMPLE})\n"
        f"  RMSE_oof_log = {r.rmse_oof_log:.4f} (baseline media {r.rmse_oof_baseline_log:.4f})\n"
        f"  n_join = {r.n_join} | n_treinamento = {r.n_treinamento} | "
        f"invalidos={r.n_descartado_invalidos} | cobertura ~{r.pct_cobertura_universo:.2f}% do "
        f"universo | range membros = [{r.range_membros[0]:.0f}, {r.range_membros[1]:.0f}]\n"
        f"  metodo_validacao = {r.metodo_validacao} | alpha = {r.alpha_selecionado:g} | "
        f"pct_extrapolacao = {r.pct_extrapolacao:.1f}% | flag_global = "
        f"{r.flag_extrapolacao_padrao_global} | top-3 UF = {top_uf}"
        f"{bloco_sens}\n"
        "Confounds obrigatorios (read-only, nao corrigidos):\n"
        "  1. Cobertura ~1% do universo de hexes do Motor (16.575 de ~1,54 M; DEC-012) -> camada "
        "de refino sobre metropoles, NAO validacao nacional.\n"
        "  2. Vies metropolitano do Sudeste (top-3 UF do join concentram a amostra) -> nao "
        "representativa do Brasil.\n"
        "  3. Ruido de coords ~1 km na fonte -> o centroide res-7 (~5,16 km2) e proxy de ordem de "
        "grandeza; o ruido de coord domina qualquer refino sub-hex e atenua o sinal.\n"
        "  4. Atratividade UNITARIA por concorrente (D1): o share ignora porte -> sensibilidade "
        "por capacidade/rede reportada SEPARADA (FORA do gate).\n"
        "  5. Circularidade `alunos_parceiras`<->`n_acad_parceiras` (rho ~+0,94): so cross-check "
        "bivariado, NUNCA alvo/feature do gate.\n"
        "  6. Vies de selecao da plataforma -> `membros` so existe onde ha adesao ao beneficio "
        "corporativo (selecao nao aleatoria); documentado, nao corrigido.\n"
        "  7. Baseline geometrico D6b (contagem-no-raio sem beta): se o Huff nao o supera, a "
        "GEOMETRIA de distancia (beta) nao agrega sobre a mera contagem.\n"
        "  8. DEC-009: `membros` e ALVO OBSERVADO; PROIBIDO usar como preditor geografico de "
        "magnitude ou ajuste do score. Este bloco VALIDA, nao INTEGRA (integracao = BLK-TP-09).\n"
    )


def _f(v: float, nd: int = 4) -> str:
    return f"{v:.{nd}f}" if isinstance(v, (int, float)) and np.isfinite(float(v)) else "n/d"


def relatorio_huff_captura(result: HuffCapturaResult) -> str:
    """String markdown legivel (PT, sem PII) com N, Spearman, metricas honestas, veredito, confounds."""
    L: list[str] = []
    L.append("# Captura Huff/gravitacional vs demanda revelada -- BLK-TP-07")
    L.append("")
    L.append(
        "READ-ONLY sobre o M1 (DEC-001/DEC-008/DEC-009). Pacote disjunto (DEC-012). Sem PII "
        "(so contagens/metricas agregadas; centroide derivado do PROPRIO `hex_id` via H3, nunca "
        "de coordenada residencial). A demanda (`membros`) e ALVO OBSERVADO; o share Huff (PURO, "
        "sem alvo) e o "
        "PREDITOR. Este bloco VALIDA -- NAO integra a captura ao residual/carteira/plano nem "
        "regenera parquet (isso e o BLK-TP-09, com DEC + gate)."
    )
    L.append("")
    L.append(
        "Gate humano APROVADO por Felipe Silva em 2026-07-03 (\"aprovar\"): D1 atratividade "
        "unitaria (capacidade por rede so sensibilidade); D2 centroide do hex; D3 grade beta por "
        "RMSE_oof; D4 sem Ultra no principal (+ sensibilidade); D5 `membros` log1p alvo unico; "
        "D6 baseline media + baseline geometrico ao lado. R2 in-sample BANIDO do veredito."
    )
    L.append("")

    L.append("## 1. Amostra + cobertura/vies")
    L.append("")
    L.append(f"- N do join inner (demanda x share por hex_id): **{result.n_join}**")
    L.append(f"- N usado no modelo (feature/alvo finitos): **{result.n_treinamento}**")
    L.append(f"- N descartado por NaN/inf: {result.n_descartado_invalidos}")
    L.append(
        f"- Cobertura do universo do Motor (~1,54 M hexes): **~{result.pct_cobertura_universo:.2f}%** "
        "-> camada de refino sobre metropoles, NAO validacao nacional."
    )
    top_uf = ", ".join(f"{k} {v:.1f}%" for k, v in result.concentracao_uf.items()) or "n/d"
    L.append(f"- Concentracao (top-3 UF do join): {top_uf} -> vies metropolitano do Sudeste.")
    L.append(
        f"- Range de `membros` no subset: "
        f"[{result.range_membros[0]:.0f}, {result.range_membros[1]:.0f}]"
    )
    L.append(f"- Metodo de validacao: `{result.metodo_validacao}`")
    L.append("")

    L.append("## 2. Selecao de beta out-of-fold (D3)")
    L.append("")
    L.append(f"- **beta_selecionado = {result.beta_selecionado:g}** (menor RMSE_oof da grade).")
    L.append("")
    L.append("| beta | RMSE_oof_log |")
    L.append("| ---: | ---: |")
    for b, v in result.rmse_oof_por_beta.items():
        L.append(f"| {b:g} | {_f(v)} |")
    L.append("")
    L.append(
        "O share NUNCA recebe o alvo (nucleo `share_huff` puro); a escolha de beta e por desempenho "
        "OUT-OF-FOLD (nao in-sample)."
    )
    L.append("")

    L.append("## 3. Correlacoes bivariadas (Spearman, ANTES do modelo)")
    L.append("")
    L.append("| feature bruta (vs membros) | rho | p |")
    L.append("| --- | ---: | ---: |")
    for feat, (rho, p) in result.spearman_bruta.items():
        L.append(f"| {feat} | {_f(rho, 3)} | {_f(p, 4)} |")
    L.append("")
    L.append(
        "Nota: `alunos_parceiras`/`n_acad_parceiras` sao OFERTA instalada (rho ~+0,94 entre si, "
        "circular) -> SO cross-check, NUNCA alvo/feature do gate."
    )
    L.append("")

    L.append("## 4. Metricas honestas (k-fold repetido out-of-fold)")
    L.append("")
    L.append("| metrica | valor |")
    L.append("| --- | ---: |")
    L.append(f"| R2_oof_log (ANCORA, gate) | {_f(result.r2_oof_log)} |")
    L.append(
        f"| IC95 R2_oof (bootstrap {N_BOOTSTRAP}, seed {SEED}) | "
        f"[{_f(result.ic95_r2_oof[0])}, {_f(result.ic95_r2_oof[1])}] |"
    )
    L.append(f"| rho_oof (SUPORTE, Spearman oof) | {_f(result.rho_oof)} |")
    L.append(
        f"| IC95 rho_oof (bootstrap {N_BOOTSTRAP}, seed {SEED}) | "
        f"[{_f(result.ic95_rho_oof[0])}, {_f(result.ic95_rho_oof[1])}] |"
    )
    L.append(
        f"| R2_oof baseline GEOMETRICO (D6b, AO LADO) | {_f(result.r2_oof_baseline_geometrico)} "
        f"IC95 [{_f(result.ic95_r2_oof_baseline_geometrico[0])}, "
        f"{_f(result.ic95_r2_oof_baseline_geometrico[1])}] |"
    )
    L.append(f"| R2_insample ({_ROTULO_INSAMPLE}) | {_f(result.r2_insample)} |")
    L.append(f"| RMSE_oof_log (modelo Huff) | {_f(result.rmse_oof_log)} |")
    L.append(f"| RMSE_oof_log (baseline media) | {_f(result.rmse_oof_baseline_log)} |")
    L.append(f"| alpha selecionado | {result.alpha_selecionado:g} |")
    L.append(f"| pct_extrapolacao (envelope min-max) | {_f(result.pct_extrapolacao, 1)}% |")
    L.append(
        f"| flag_extrapolacao_padrao_global (n<{N_PISO_LOO}) | "
        f"{result.flag_extrapolacao_padrao_global} |"
    )
    L.append("")
    L.append("Coeficiente do modelo final (espaco log):")
    L.append("")
    L.append("| feature | coef |")
    L.append("| --- | ---: |")
    L.append(f"| {FEATURE_PRINCIPAL} | {result.coef_share:+.4f} |")
    L.append(f"| (intercepto) | {result.intercepto:+.4f} |")
    L.append("")

    L.append("## 5. Sensibilidades rotuladas (FORA do veredito)")
    L.append("")
    if result.sensibilidade_capacidade:
        sc = result.sensibilidade_capacidade
        L.append(
            f"- **D1b capacidade/rede** (atratividade uniforme = {sc.get('atratividade_uniforme', float('nan')):.0f}): "
            f"R2_oof_log = {_f(sc.get('r2_oof_log', float('nan')))} "
            f"IC95 [{_f(sc.get('ic95_inf', float('nan')))}, {_f(sc.get('ic95_sup', float('nan')))}]."
        )
    else:
        L.append("- **D1b capacidade/rede**: base `data/validacao/` ausente -> nao computada.")
    if result.sensibilidade_ultra:
        su = result.sensibilidade_ultra
        L.append(
            f"- **D4c proximidade Ultra** (covariavel): R2_oof_log = "
            f"{_f(su.get('r2_oof_log_com_ultra', float('nan')))} "
            f"IC95 [{_f(su.get('ic95_inf', float('nan')))}, {_f(su.get('ic95_sup', float('nan')))}]."
        )
    else:
        L.append("- **D4c proximidade Ultra**: colunas ultra ausentes no join -> nao computada.")
    L.append("")
    L.append(
        "As sensibilidades NAO decidem o gate (D1/D4). Medem se atratividade por capacidade ou a "
        "proximidade da rede Ultra deslocam o sinal -- reportadas para transparencia."
    )
    L.append("")

    L.append("## 6. Veredito")
    L.append("")
    L.append(
        f"**{result.veredito}**"
        + (f" ({result.tipo_go})" if result.tipo_go else "")
        + f" -- GO se (`R2_oof_log > {LIMIAR_R2_GO}` E `IC95_inf(R2) > 0` E supera o baseline "
        f"geometrico) OU (`rho_oof >= {LIMIAR_RHO_SUPORTE}` E `IC95_inf(rho) > 0`). "
        "R2 e a ANCORA; rho e o SUPORTE. NO-GO e resultado VALIDO (DEC-008)."
    )
    L.append("")

    L.append("## 7. Limitacoes / confounds")
    L.append("")
    L.append("```")
    L.append(result.nota_honesta.rstrip("\n"))
    L.append("```")
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# Rede de seguranca anti-PII no relatorio
# --------------------------------------------------------------------------- #
def _assert_sem_pii_no_relatorio(texto: str) -> None:
    """Falha se qualquer coluna de COLUNAS_PII_PROIBIDAS aparecer como token isolado no texto.

    Word-boundary para nao casar substring de palavras PT legitimas (ex.: "id" em "medida").
    """
    import re

    baixo = texto.lower()
    presentes = {
        c for c in COLUNAS_PII_PROIBIDAS if re.search(rf"\b{re.escape(c.lower())}\b", baixo)
    }
    if presentes:  # pragma: no cover - rede de seguranca
        raise AssertionError(f"PII vazou no relatorio BLK-TP-07: {presentes}")


def escrever_relatorio(result: HuffCapturaResult, *, path: Path) -> None:
    """Materializa o relatorio markdown (gitignored, sem PII). NAO chamada em teste."""
    path = Path(path)
    texto = relatorio_huff_captura(result)
    _assert_sem_pii_no_relatorio(texto)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(texto, encoding="utf-8")
    _logger.info("relatorio BLK-TP-07 escrito: %s", path)


# --------------------------------------------------------------------------- #
# Orquestrador real (caminho de disco -- NAO chamado em teste)
# --------------------------------------------------------------------------- #
def _preparar_join_real(
    dem_df: pd.DataFrame, mkt_df: pd.DataFrame | None
) -> pd.DataFrame:
    """Monta o frame de join: demanda (agregada) + `uf`/colunas ultra do mercado (READ-ONLY).

    So colunas AGREGADAS (nunca PII). Da demanda: `hex_id`, `membros`, `alunos_parceiras`,
    `n_acad_parceiras`, `n_concorrente_lc`, `dist_concorrente_lc_min_m`. Do mercado (opcional):
    `uf`, `n_unidades_ultra_1km`, `dist_ultra_mais_proxima_m` (para concentracao/sensibilidade D4c).
    """
    cols_dem = [
        c
        for c in (
            "hex_id",
            "membros",
            "alunos_parceiras",
            "n_acad_parceiras",
            "n_concorrente_lc",
            "dist_concorrente_lc_min_m",
        )
        if c in dem_df.columns
    ]
    df = dem_df[cols_dem].copy()
    if mkt_df is not None:
        cols_mkt = [
            c
            for c in (
                "hex_id",
                "uf",
                "n_unidades_ultra_1km",
                "dist_ultra_mais_proxima_m",
            )
            if c in mkt_df.columns
        ]
        if "hex_id" in cols_mkt:
            df = df.merge(mkt_df[cols_mkt], on="hex_id", how="left")
    return df


def executar(
    dem_path: Path | str = Path("data/staging/demanda_revelada_h3.parquet"),
    conc_path: Path | str = Path("data/staging/concorrentes_mapeados.parquet"),
    mkt_path: Path | str = Path("data/staging/hexagonos_mercado_mapeado.parquet"),
    out_path: Path | str = Path("data/analysis/huff_captura.md"),
) -> HuffCapturaResult:
    """Le demanda + concorrentes (+ mercado p/ uf/ultra), calcula share por hex, valida, materializa.

    READ-ONLY sobre o M1: NAO escreve em nenhum artefato oficial; so materializa o relatorio
    markdown gitignored. `nome_unidade` nunca lido; centroide via `hex_id`.
    """
    dem = pd.read_parquet(dem_path)
    conc_lat, conc_lng = _carregar_concorrentes(Path(conc_path))
    mkt = None
    mkt_p = Path(mkt_path)
    if mkt_p.exists():
        try:
            mkt = pd.read_parquet(
                mkt_p,
                columns=["hex_id", "uf", "n_unidades_ultra_1km", "dist_ultra_mais_proxima_m"],
            )
        except Exception as exc:  # pragma: no cover - mercado sem essas colunas
            _logger.info("mercado sem colunas uf/ultra (%s); segue sem elas", exc)
            mkt = None
    df_join = _preparar_join_real(dem, mkt)
    result = calibrar_huff_captura(df_join, conc_lat, conc_lng)
    escrever_relatorio(result, path=Path(out_path))
    return result


__all__ = [
    "HuffCapturaResult",
    "share_hex",
    "n_conc_no_raio_hex",
    "calcular_share_por_hex",
    "calcular_n_conc_por_hex",
    "correlacoes_bivariadas",
    "calibrar_huff_captura",
    "relatorio_huff_captura",
    "escrever_relatorio",
    "executar",
    "LIMIAR_RHO_SUPORTE",
    "FEATURE_PRINCIPAL",
    "N_BOOTSTRAP",
]


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    _res = executar()
    print(_res.nota_honesta)
    print("veredito:", _res.veredito, _res.tipo_go)
