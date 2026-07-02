"""BLK-TP-03: Vazio competitivo do concorrente low-cost (H3 res-7, READ-ONLY sobre o M1).

Identifica hexes com demanda paga relevante a >5 km do concorrente low-cost de referencia
E sem unidade dele no hex — "vazio competitivo" — e materializa o artefato reproduzivel
`data/staging/vazios_competitivos_lc.parquet`.

GUARDRAILS (DEC-001/DEC-009/DEC-012; CLAUDE.md §5):
  - READ-ONLY sobre o M1: NAO recalcula `score_priorizacao`/`hex_score_estrutural`/pesos
    (renda=0.40/pop=0.60); NAO toca carteira/plano/artefatos oficiais. `score_priorizacao` e
    `oferta_efetiva_disponivel` sao LIDOS do join de enriquecimento.
  - DEC-009: a demanda e insumo OBSERVADO. `membros`/`membros_gt5km_concorrente_lc` aqui sao
    criterio de filtro de vazio competitivo (analise read-only), NUNCA preditor geografico de
    magnitude para ajustar o score.
  - DEC-012: pacote `demanda_revelada/` DISJUNTO — este modulo NUNCA importa de `pipelines/m1/`,
    `censo_*`, `dashboard/` nem `config.py` raiz; sem PII (zero coluna de COLUNAS_PII_PROIBIDAS
    em qualquer frame/saida); fonte real (NAO_ABRA/) nunca tocada; testes so com fixture sintetica.
    Colunas de localizacao = `hex_lat`/`hex_lng` (centroide do hex derivado de h3, NAO `lat`/`lng`
    que constam em COLUNAS_PII_PROIBIDAS).

Uso:
  python -m motor_expansao.demanda_revelada.vazios_competitivos  # gera o parquet sobre dados reais
"""

from __future__ import annotations

import logging
from pathlib import Path

import h3
import numpy as np
import pandas as pd

from .contrato import COLUNAS_PII_PROIBIDAS

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes de modulo
# ---------------------------------------------------------------------------

LIMIAR_MEMBROS_GT5KM: int = 200
"""Threshold inclusivo (>=) de membros_gt5km_concorrente_lc para classificar como vazio.

Calibrado sobre o sweep do parquet real (16.575 hexes, BLK-TP-03/Planner):
  limiar=200 -> 229 hexes (reproduz ~231 do prototipo; percentil >99 da base).
Parametrizavel: o operador pode afrouxar/apertar sem editar a formula.
"""

DIST_LC_MIN_M: float = 5_000.0
"""Distancia minima (metros, estrita) ao concorrente low-cost para contar como vazio.

A condicao e `dist_concorrente_lc_min_m > DIST_LC_MIN_M` (estrita, nao >=).
NaN em dist_concorrente_lc_min_m = "muito longe" -> INCLUIDO (Decisao 1 do Planner).
"""

VERSAO_CONTRATO_VAZIOS: str = "vazios_competitivos_v1"
"""Carimbo de versao gravado em todas as linhas do artefato (reprodutibilidade)."""

CONTRATO_COLUNAS_VAZIOS: dict[str, str] = {
    "hex_id": "string",                          # H3 res-7 (chave)
    "membros": "int64",                          # demanda paga total no hex (contexto)
    "membros_gt5km_concorrente_lc": "int64",     # demanda a >5km do LC (sinal do vazio)
    "dist_concorrente_lc_min_m": "float64",      # dist. minima ao LC no hex (m)
    "n_concorrente_lc": "int64",                 # unidades LC no hex (=0 por construcao)
    "flag_vazio_competitivo": "bool",            # True em todas as linhas (autoexplicativo)
    "hex_lat": "float64",                        # centroide do hex (NAO 'lat' — ver DEC-012)
    "hex_lng": "float64",                        # centroide do hex (NAO 'lng' — ver DEC-012)
    "uf": "string",                              # enriquecimento READ-ONLY
    "nome_municipio": "string",                  # enriquecimento READ-ONLY
    "score_priorizacao": "float64",              # LIDO do M1 (READ-ONLY; ranquear vazios)
    "oferta_efetiva_disponivel": "float64",      # LIDO do mercado/residual (contexto)
    "versao_contrato": "string",                 # carimbo de versao
}
"""Schema do artefato `data/staging/vazios_competitivos_lc.parquet`.

Ordem deterministica; frame sempre ordenado por `hex_id`.
`hex_lat`/`hex_lng` sao centroides de HEX H3 (nao residencias) — nomes distintos de
`lat`/`lng`/`latitude`/`longitude` que constam em COLUNAS_PII_PROIBIDAS (DEC-012).
"""

# Paths default (relativos ao diretorio raiz do projeto)
FONTE_DEMANDA_DEFAULT = Path("data/staging/demanda_revelada_h3.parquet")
FONTE_ENRIQUECIMENTO_DEFAULT = Path("data/staging/hexagonos_mercado_mapeado.parquet")
DESTINO_DEFAULT = Path("data/staging/vazios_competitivos_lc.parquet")


# ---------------------------------------------------------------------------
# Funcoes puras
# ---------------------------------------------------------------------------

def flag_vazio_competitivo(
    df: pd.DataFrame,
    *,
    limiar_membros_gt5km: int = LIMIAR_MEMBROS_GT5KM,
) -> pd.Series[bool]:
    """Classifica cada hex como vazio competitivo do concorrente low-cost.

    Aplica 3 condicoes sobre o contrato de demanda_revelada_v1:
      1. `n_concorrente_lc == 0` — sem unidade do concorrente LC no hex.
      2. `dist_concorrente_lc_min_m > DIST_LC_MIN_M` OU dist NaN (Decisao 1: NaN = muito longe).
      3. `membros_gt5km_concorrente_lc >= limiar_membros_gt5km` — demanda expressiva a >5 km.

    Coercao numerica defensiva (pd.to_numeric errors='coerce') em todas as colunas numericas.
    Retorna serie booleana alinhada ao indice de `df`.

    Parameters
    ----------
    df:
        DataFrame com pelo menos as colunas `n_concorrente_lc`, `dist_concorrente_lc_min_m`,
        `membros_gt5km_concorrente_lc`. Consumido READ-ONLY (nao modifica o frame de entrada).
    limiar_membros_gt5km:
        Limiar inclusivo (>=) para `membros_gt5km_concorrente_lc`. Default = LIMIAR_MEMBROS_GT5KM.

    Returns
    -------
    pd.Series[bool]
        Serie booleana com mesmo indice de `df`. True = vazio competitivo.
    """
    n_conc = pd.to_numeric(df.get("n_concorrente_lc", pd.Series(np.nan, index=df.index)), errors="coerce")
    dist = pd.to_numeric(df.get("dist_concorrente_lc_min_m", pd.Series(np.nan, index=df.index)), errors="coerce")
    membros_gt = pd.to_numeric(df.get("membros_gt5km_concorrente_lc", pd.Series(np.nan, index=df.index)), errors="coerce")

    # Condicao 1: sem unidade LC no hex
    cond_sem_lc = n_conc == 0

    # Condicao 2: dist > 5km OU dist eh NaN (NaN = muito longe, Decisao 1 do Planner)
    # Materializa coluna auxiliar auditavel dist_ge_5km para rastreabilidade.
    dist_ge_5km: pd.Series[bool] = dist.isna() | (dist > DIST_LC_MIN_M)

    # Condicao 3: demanda expressiva a >5km (limiar inclusivo >=)
    cond_demanda = membros_gt >= limiar_membros_gt5km

    return cond_sem_lc & dist_ge_5km & cond_demanda


def enriquecer_vazios(
    vazios: pd.DataFrame,
    enriquecimento: pd.DataFrame,
) -> pd.DataFrame:
    """Enriquece o frame de vazios com colunas de localizacao/contexto via join por `hex_id`.

    JOIN READ-ONLY (left): traz SÓ `uf`, `nome_municipio`, `score_priorizacao`,
    `oferta_efetiva_disponivel` do frame de enriquecimento (`hexagonos_mercado_mapeado.parquet`).
    Colunas ausentes no enriquecimento sao preenchidas com pd.NA sem falhar.

    `hex_lat`/`hex_lng` sao derivados de `h3.cell_to_latlng(hex_id)` (deterministico, independe
    do enriquecimento — evita depender de `lat`/`lng` que constam em COLUNAS_PII_PROIBIDAS).

    Parameters
    ----------
    vazios:
        Frame filtrado de hexes com flag_vazio_competitivo == True.
    enriquecimento:
        Frame com colunas de contexto (ex.: hexagonos_mercado_mapeado.parquet). Consumido READ-ONLY.

    Returns
    -------
    pd.DataFrame
        Frame enriquecido com `hex_lat`, `hex_lng` e as 4 colunas de enriquecimento.
    """
    # Derivar centroide do hex via h3 (deterministico; evita colisao com COLUNAS_PII_PROIBIDAS)
    hex_ids = vazios["hex_id"].astype(str)

    def _cell_to_lat(hid: str) -> float:
        try:
            return float(h3.cell_to_latlng(hid)[0])
        except Exception:
            return float("nan")

    def _cell_to_lng(hid: str) -> float:
        try:
            return float(h3.cell_to_latlng(hid)[1])
        except Exception:
            return float("nan")

    vazios = vazios.copy()
    vazios["hex_lat"] = hex_ids.map(_cell_to_lat)
    vazios["hex_lng"] = hex_ids.map(_cell_to_lng)

    # Colunas de enriquecimento a trazer (READ-ONLY; guard por coluna ausente)
    _COLUNAS_ENRICH = ["uf", "nome_municipio", "score_priorizacao", "oferta_efetiva_disponivel"]

    if len(enriquecimento) == 0:
        for col in _COLUNAS_ENRICH:
            vazios[col] = pd.NA
        return vazios

    enrich_sub = enriquecimento[
        ["hex_id"] + [c for c in _COLUNAS_ENRICH if c in enriquecimento.columns]
    ].copy()

    merged = vazios.merge(enrich_sub, on="hex_id", how="left")

    # Preencher colunas ausentes no enriquecimento com NA
    for col in _COLUNAS_ENRICH:
        if col not in merged.columns:
            merged[col] = pd.NA

    return merged


# ---------------------------------------------------------------------------
# Guard anti-PII
# ---------------------------------------------------------------------------

def _assert_sem_pii_vazios(df: pd.DataFrame) -> None:
    """Falha se qualquer coluna de COLUNAS_PII_PROIBIDAS aparecer no frame.

    Rede de seguranca automatizada (DEC-012). Chamada antes de gravar o artefato.
    Raises AssertionError se houver colisao.
    """
    colisao = set(df.columns) & COLUNAS_PII_PROIBIDAS
    if colisao:
        raise AssertionError(
            f"PII detectada no artefato de vazios competitivos: {sorted(colisao)}. "
            "Use 'hex_lat'/'hex_lng' em vez de 'lat'/'lng' (DEC-012)."
        )


# ---------------------------------------------------------------------------
# Orquestrador
# ---------------------------------------------------------------------------

def gerar_vazios_competitivos(
    fonte: Path = FONTE_DEMANDA_DEFAULT,
    enriquecimento: Path = FONTE_ENRIQUECIMENTO_DEFAULT,
    destino: Path = DESTINO_DEFAULT,
    *,
    limiar_membros_gt5km: int = LIMIAR_MEMBROS_GT5KM,
    escrever: bool = True,
) -> pd.DataFrame:
    """Gera o artefato `vazios_competitivos_lc.parquet` de forma reproduzivel.

    Fluxo:
      1. Le `demanda_revelada_h3.parquet` (fonte).
      2. Aplica `flag_vazio_competitivo` (3 condicoes).
      3. Filtra hexes True.
      4. Enriquece com `hexagonos_mercado_mapeado.parquet` (join left por hex_id).
      5. Coerce ao CONTRATO_COLUNAS_VAZIOS (dtypes + ordem).
      6. Ordena por `hex_id` (determinismo).
      7. Verifica anti-PII.
      8. Grava parquet se `escrever=True`.

    READ-ONLY sobre o M1: nao toca score_priorizacao/pesos/artefatos oficiais (DEC-001).
    Anti-PII por construcao (DEC-012): sem lat/lng/employee_id/etc. no artefato.

    Parameters
    ----------
    fonte:
        Path para `demanda_revelada_h3.parquet`. Default = FONTE_DEMANDA_DEFAULT.
    enriquecimento:
        Path para `hexagonos_mercado_mapeado.parquet`. Default = FONTE_ENRIQUECIMENTO_DEFAULT.
    destino:
        Path do artefato de saida. Default = DESTINO_DEFAULT.
    limiar_membros_gt5km:
        Limiar inclusivo (>=). Default = LIMIAR_MEMBROS_GT5KM (200).
    escrever:
        Se True (default), grava o parquet em `destino`.

    Returns
    -------
    pd.DataFrame
        Frame com as colunas de CONTRATO_COLUNAS_VAZIOS, ordenado por `hex_id`.
    """
    _logger.info("BLK-TP-03: lendo demanda revelada de %s", fonte)
    df_demanda = pd.read_parquet(Path(fonte))

    _logger.info("BLK-TP-03: aplicando flag_vazio_competitivo (limiar=%d)", limiar_membros_gt5km)
    mask = flag_vazio_competitivo(df_demanda, limiar_membros_gt5km=limiar_membros_gt5km)
    n_total = int(len(df_demanda))
    n_vazios = int(mask.sum())
    _logger.info("BLK-TP-03: %d/%d hexes classificados como vazio competitivo", n_vazios, n_total)

    df_vazios = df_demanda[mask].copy()
    # Garantir flag_vazio_competitivo como coluna (auditavel; True por construcao do filtro)
    df_vazios["flag_vazio_competitivo"] = True

    # Carregar enriquecimento (tolerante a ausencia de arquivo)
    path_enrich = Path(enriquecimento)
    if path_enrich.exists():
        _logger.info("BLK-TP-03: carregando enriquecimento de %s", path_enrich)
        df_enrich = pd.read_parquet(path_enrich)
    else:
        _logger.warning("BLK-TP-03: enriquecimento nao encontrado em %s — preenchendo com NA", path_enrich)
        df_enrich = pd.DataFrame(columns=["hex_id"])

    df_enriquecido = enriquecer_vazios(df_vazios, df_enrich)

    # Adicionar versao_contrato
    df_enriquecido["versao_contrato"] = VERSAO_CONTRATO_VAZIOS

    # Coercao ao contrato (dtypes + ordem)
    df_final = _coagir_ao_contrato(df_enriquecido)

    # Ordenar por hex_id (determinismo)
    df_final = df_final.sort_values("hex_id").reset_index(drop=True)

    # Guard anti-PII
    _assert_sem_pii_vazios(df_final)

    if escrever:
        destino_path = Path(destino)
        destino_path.parent.mkdir(parents=True, exist_ok=True)
        df_final.to_parquet(destino_path, index=False)
        _logger.info("BLK-TP-03: artefato gravado em %s (%d hexes)", destino_path, len(df_final))

    return df_final


def _coagir_ao_contrato(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce o frame ao CONTRATO_COLUNAS_VAZIOS (dtypes + ordem).

    Colunas ausentes sao adicionadas com NA. Colunas extras sao descartadas.
    """
    out: dict[str, pd.Series] = {}  # type: ignore[type-arg]
    for col, dtype in CONTRATO_COLUNAS_VAZIOS.items():
        if col in df.columns:
            serie = df[col]
            try:
                if dtype == "bool":
                    out[col] = serie.astype(bool)
                elif dtype == "string":
                    out[col] = serie.astype("string")
                elif dtype == "int64":
                    out[col] = pd.to_numeric(serie, errors="coerce").astype("Int64")
                elif dtype == "float64":
                    out[col] = pd.to_numeric(serie, errors="coerce").astype(float)
                else:
                    out[col] = serie
            except Exception:
                out[col] = serie
        else:
            # Coluna ausente: preencher com NA no dtype correto
            n = len(df)
            if dtype == "bool":
                out[col] = pd.Series([pd.NA] * n, dtype="boolean")
            elif dtype == "string":
                out[col] = pd.Series([pd.NA] * n, dtype="string")
            elif dtype == "int64":
                out[col] = pd.Series([pd.NA] * n, dtype="Int64")
            else:
                out[col] = pd.Series([float("nan")] * n, dtype=float)

    return pd.DataFrame(out)


__all__ = [
    "flag_vazio_competitivo",
    "enriquecer_vazios",
    "gerar_vazios_competitivos",
    "LIMIAR_MEMBROS_GT5KM",
    "DIST_LC_MIN_M",
    "VERSAO_CONTRATO_VAZIOS",
    "CONTRATO_COLUNAS_VAZIOS",
    "FONTE_DEMANDA_DEFAULT",
    "FONTE_ENRIQUECIMENTO_DEFAULT",
    "DESTINO_DEFAULT",
]


if __name__ == "__main__":  # pragma: no cover
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)
    _df_final = gerar_vazios_competitivos()
    print(f"Vazios competitivos gerados: {len(_df_final)} hexes")
    print(f"Colunas: {list(_df_final.columns)}")
    print(_df_final[["hex_id", "membros_gt5km_concorrente_lc", "uf", "nome_municipio", "score_priorizacao"]].head(10).to_string())
