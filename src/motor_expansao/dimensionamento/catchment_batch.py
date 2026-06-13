"""Catchment censitario por unidade (camada de Dimensionamento, BLK-DIM).

Para cada unidade Ultra, cruza um circulo de raio `RAIO_CATCHMENT_KM` (D3=1.5 km)
com os setores censitarios reais via o helper geometrico
`analisar_ponto_censitario_setores` (NAO alterado; raio/metodo de intersecao
INTOCADOS). Extrai `pop_captacao`/`renda_per_capita_captacao` por unidade.

READ-ONLY sobre o M1; nao recalcula score nem toca artefatos oficiais.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from motor_expansao.dashboard.censo_point import analisar_ponto_censitario_setores
from motor_expansao.dashboard.data import read_censo_geo_partition
from motor_expansao.dimensionamento import config
from motor_expansao.dimensionamento.growth_api_client import normalizar_unidade

logger = logging.getLogger(__name__)

GEO_BASE_DIR_DEFAULT = Path("data/outputs/setores_censitarios_2022_geo")

# Colunas de saida do catchment.
CATCHMENT_COLUNAS = (
    "unidade",
    "unidade_norm",
    "uf",
    "lat",
    "lng",
    "pop_captacao",
    "renda_per_capita_captacao",
    "n_setores_captacao",
    "raio_km",
)


def calcular_catchment_unidade(
    lat: object,
    lng: object,
    setores_df: pd.DataFrame | None,
    raio_km: float = config.RAIO_CATCHMENT_KM,
) -> dict:
    """Catchment de 1 ponto. Trata lat/lng NULL -> NaN (entra em `lacunas`).

    Reusa `analisar_ponto_censitario_setores` (helper geometrico, NAO alterado).
    """
    lat_num = pd.to_numeric(lat, errors="coerce")
    lng_num = pd.to_numeric(lng, errors="coerce")
    base: dict = {
        "pop_captacao": float("nan"),
        "renda_per_capita_captacao": float("nan"),
        "n_setores_captacao": 0,
        "raio_km": float(raio_km),
    }
    if pd.isna(lat_num) or pd.isna(lng_num):
        return base
    if setores_df is None or setores_df.empty:
        return base
    res = analisar_ponto_censitario_setores(
        float(lat_num), float(lng_num), setores_df, raio_km=raio_km
    )
    pop = res.get("pop_total_raio")
    renda = res.get("renda_per_capita_media_raio")
    return {
        "pop_captacao": float(pop) if pop is not None else float("nan"),
        "renda_per_capita_captacao": float(renda) if renda is not None else float("nan"),
        "n_setores_captacao": int(res.get("n_setores", 0) or 0),
        "raio_km": float(raio_km),
    }


def calcular_catchment_batch(
    perf_df: pd.DataFrame,
    geo_base_dir: Path | str = GEO_BASE_DIR_DEFAULT,
    raio_km: float = config.RAIO_CATCHMENT_KM,
    setores_loader=read_censo_geo_partition,
) -> pd.DataFrame:
    """Itera as unidades do performance parquet e calcula o catchment.

    Carrega setores por UF (com cache em memoria para nao reler) via
    `setores_loader(geo_base_dir, uf)` (default `read_censo_geo_partition`).
    """
    geo_base_dir = Path(geo_base_dir)
    cache_uf: dict[str, pd.DataFrame] = {}
    linhas: list[dict] = []

    try:
        from tqdm import tqdm

        iterador = tqdm(perf_df.iterrows(), total=len(perf_df), desc="catchment")
    except Exception:  # pragma: no cover - tqdm sempre na base
        iterador = perf_df.iterrows()

    for _idx, row in iterador:
        unidade = row.get("unidade")
        uf = str(row.get("uf") or "").upper()
        lat = row.get("lat")
        lng = row.get("lng")
        if uf and uf not in cache_uf:
            try:
                cache_uf[uf] = setores_loader(geo_base_dir, uf)
            except Exception as exc:  # pragma: no cover - IO defensivo
                logger.warning("Falha ao carregar setores UF=%s: %s", uf, exc)
                cache_uf[uf] = pd.DataFrame()
        setores = cache_uf.get(uf, pd.DataFrame())
        catch = calcular_catchment_unidade(lat, lng, setores, raio_km=raio_km)
        linhas.append(
            {
                "unidade": unidade,
                "unidade_norm": normalizar_unidade(unidade),
                "uf": uf,
                "lat": pd.to_numeric(lat, errors="coerce"),
                "lng": pd.to_numeric(lng, errors="coerce"),
                **catch,
            }
        )

    df = pd.DataFrame(linhas)
    if df.empty:
        return pd.DataFrame(columns=list(CATCHMENT_COLUNAS))
    return df[list(CATCHMENT_COLUNAS)].reset_index(drop=True)
