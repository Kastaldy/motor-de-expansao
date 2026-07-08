"""BLK-ATR-03-FU1: re-rodar a estrutura (matriz vs composto) do ATR-03 sobre o Huff DENSO.

Refaz o teste de ESTRUTURA de leitura da atratividade (BLK-ATR-03, `estrutura_funil.py`)
substituindo SO o eixo `share_captura_huff` pelo share recomputado GEOMETRICAMENTE sobre a base
DENSA de concorrentes (`concorrentes_densos.parquet`, base BLK-ATR-01: TotalPass + WellHub +
Unidades + base atual, ~10 mil pares), reusando as funcoes PURAS ja existentes (harness k-fold 5x5
seed=42 / IC95 de `estrutura_funil.avaliar_estrutura_funil`; share puro de
`huff_captura.calcular_share_por_hex`; beta out-of-fold de `huff_captura.calibrar_huff_captura`).
Emite o veredito honesto matriz vs composto em `data/analysis/estrutura_funil_densa.md`
(gitignored). NO-GO/matriz e resultado VALIDO (DEC-008).

GUARDRAILS (DEC-001/DEC-008/DEC-009/DEC-012; CLAUDE.md §5):
  - READ-ONLY sobre o M1: nenhuma escrita em score/pesos/carteira/plano/artefatos oficiais; a base
    densa e apenas LIDA (`concorrentes_densos.parquet` nunca sobrescrito).
  - DEC-008: k-fold repetido vs baseline da media (harness reusado); R2 in-sample so auditoria
    rotulada (nunca no veredito); IC95 seed=42; beta out-of-fold; NO-GO/matriz e VALIDO.
  - DEC-009: `membros` e ALVO OBSERVADO; NUNCA preditor. O share denso vem de
    `calcular_share_por_hex` (PURO, geometrico) -- o vazamento do alvo e estruturalmente impossivel.
  - DEC-012: pacote `demanda_revelada/` DISJUNTO -- este modulo NUNCA importa de `pipelines/`,
    `pipelines/m1/`, `censo_*`, `dashboard/`, `api` nem `config.py` raiz; sem PII (so contagens/
    metricas agregadas); fonte real (`NAO_ABRA/`) nunca tocada; testes so com fixture sintetica.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .concorrentes_densos import (
    DEMANDA_DEFAULT,
    MERCADO_DEFAULT,
    _coords_densas,
)
from .estrutura_funil import (
    EstruturaFunilResult,
    avaliar_estrutura_funil,
    escrever_relatorio,
    relatorio_estrutura_funil,
)
from .huff_captura import (
    BETA_GRID,
    calcular_share_por_hex,
    calibrar_huff_captura,
)

__all__ = [
    "substituir_share_denso",
    "avaliar_estrutura_densa",
    "executar",
    "RELATORIO_ESTRUTURA_DENSA_DEFAULT",
    "DENSO_DEFAULT",
    "BETA_GRID",
    "relatorio_estrutura_funil",
]

RELATORIO_ESTRUTURA_DENSA_DEFAULT = Path("data/analysis/estrutura_funil_densa.md")
DENSO_DEFAULT = Path("data/staging/concorrentes_densos.parquet")
_logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Recomputacao do share denso (PURA, sem I/O, sem alvo)
# --------------------------------------------------------------------------- #
def substituir_share_denso(
    df_join: pd.DataFrame,
    conc_lat: np.ndarray,
    conc_lng: np.ndarray,
    beta: float,
) -> pd.DataFrame:
    """Recomputa `share_captura_huff` por hex sobre a base densa e SUBSTITUI a coluna no frame.

    - `df_join` deve ter `hex_id`. Recomputa o share de CADA hex via `calcular_share_por_hex`
      (PURO, sem alvo) contra `(conc_lat, conc_lng)` e o `beta` dado.
    - Retorna uma CÓPIA do frame com a coluna `share_captura_huff` DENSA (substitui a antiga se
      existir). NÃO toca `membros` (o alvo, DEC-009). NÃO altera nenhuma outra coluna.

    Raises
    ------
    ValueError
        Se `df_join` nao tiver `hex_id`.
    """
    if "hex_id" not in df_join.columns:
        raise ValueError("`df_join` precisa de `hex_id` para recomputar o share denso.")
    out = df_join.copy()
    hexes = out["hex_id"].astype(str).tolist()
    share = calcular_share_por_hex(hexes, conc_lat, conc_lng, beta)
    out["share_captura_huff"] = share
    return out


# --------------------------------------------------------------------------- #
# Avaliacao com o share denso (PURA -- recebe frames prontos, sem I/O)
# --------------------------------------------------------------------------- #
def avaliar_estrutura_densa(
    df_join: pd.DataFrame,
    df_denso: pd.DataFrame,
) -> tuple[EstruturaFunilResult, float]:
    """Seleciona beta OOF sobre a base densa, substitui o eixo disputa e roda o harness ATR-03.

    1. Extrai `(conc_lat, conc_lng)` via `_coords_densas(df_denso)`.
    2. Seleciona beta OUT-OF-FOLD via `calibrar_huff_captura(df_join_min, conc_lat, conc_lng)`
       (menor RMSE_oof sobre a base densa; `calibrar` exige so `hex_id` + `membros`; sem
       sensibilidades caras). Usa `result_huff.beta_selecionado` (recomputado, nunca hardcoded).
    3. Substitui o share via `substituir_share_denso(df_join, conc_lat, conc_lng, beta)`.
    4. Chama `avaliar_estrutura_funil(df_join_denso)` (harness PURO -- aplica o gate ATR-02, os
       modelos oof e o veredito honesto matriz vs composto).

    Retorna `(EstruturaFunilResult, beta_selecionado)`. READ-ONLY sobre o M1; share PURO (DEC-009).
    """
    conc_lat, conc_lng = _coords_densas(df_denso)

    # Selecao de beta OOF: `calibrar_huff_captura` so precisa de `hex_id` + `membros`.
    df_min = df_join[["hex_id", "membros"]].copy()
    result_huff = calibrar_huff_captura(
        df_min, conc_lat, conc_lng, incluir_sensibilidades=False
    )
    beta = float(result_huff.beta_selecionado)

    df_denso_join = substituir_share_denso(df_join, conc_lat, conc_lng, beta)
    result = avaliar_estrutura_funil(df_denso_join)
    return result, beta


# --------------------------------------------------------------------------- #
# Caminho de disco (NAO chamado em teste)
# --------------------------------------------------------------------------- #
def executar(
    dem_path: Path | str = DEMANDA_DEFAULT,
    mkt_path: Path | str = MERCADO_DEFAULT,
    denso_path: Path | str = DENSO_DEFAULT,
    out_path: Path | str = RELATORIO_ESTRUTURA_DENSA_DEFAULT,
) -> EstruturaFunilResult:  # pragma: no cover - caminho de disco, nao chamado em teste
    """Carrega o join demanda x mercado + a base densa, avalia com o share denso e grava o .md.

    Operacao CARA (share denso sobre ~10 mil concorrentes x ~16 mil hexes na selecao de beta) e
    gitignored. READ-ONLY sobre o M1: `escrever_relatorio` ja tem a rede anti-PII embutida.
    """
    from .estrutura_funil import _carregar_join

    df_join = _carregar_join(Path(dem_path), Path(mkt_path))
    df_denso = pd.read_parquet(Path(denso_path))
    result, beta = avaliar_estrutura_densa(df_join, df_denso)
    escrever_relatorio(result, path=Path(out_path))
    _logger.info(
        "BLK-ATR-03-FU1: beta_denso=%.2f veredito=%s r2_composto=%.4f",
        beta,
        result.veredito,
        result.modelos["composto"].r2_oof,
    )
    return result


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    _res = executar()
    print(_res.nota_honesta)
