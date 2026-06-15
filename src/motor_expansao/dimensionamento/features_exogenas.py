"""BLK-DIM-05: features exogenas na aderencia (Camada 1, READ-ONLY sobre M1).

Deriva, por unidade madura, features EXOGENAS do censo 2022 + saturacao de concorrencia
no catchment de 1.5 km, reusando o helper geometrico `analisar_ponto_censitario_setores`
(NAO alterado; raio/metodo de intersecao INTOCADOS) e o loop cache-por-UF de
`catchment_batch`. Compara modelos de aderencia (LOO-CV Ridge multi-feature) com e sem as
features exogenas, contra o baseline pop+renda do BLK-DIM-01R.

aderencia.py (BLK-DIM-01R) e READ-ONLY/congelado: este modulo NAO o importa para calibrar
(a assinatura `calibrar_aderencia(df, limiar_r2)` hardcoda pop+renda). O LOO-CV multi-feature
e reimplementado aqui (espelha a logica honesta: ALPHA_GRID, selecao por menor RMSE_LOO_log,
R2 LOO em dois espacos). READ-ONLY sobre o M1 (DEC-001). Sem PII em disco.

LACUNA CENTRAL (titulo do bloco cita features comportamentais): faixa etaria 18-45, vinculo
formal CLT e % de ocupados estao AUSENTES do Censo 2022 Basico por setor (microdados ~10 GB
fora do escopo loop-safe). Documentado no relatorio como trabalho futuro (BLK-DIM-06).
NO-GO continua sendo resultado cientifico VALIDO (BLK-DIM-01R deu r2_loo_log = -0.0134).
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

logger = logging.getLogger(__name__)

# Reusar os mesmos defaults do BLK-DIM-01R (espelho, NAO importar para nao acoplar).
ALPHA_GRID: tuple[float, ...] = (0.01, 0.1, 1.0, 10.0, 100.0)
LIMIAR_R2_GO: float = 0.05
N_MIN_CALIBRACAO: int = 5
RAIO_FEATURES_KM: float = 1.5  # consistente com o catchment
# Delta material de melhora sobre o baseline (5 p.p.) -- des-circulariza o veredito.
DELTA_MATERIAL: float = 0.05
# Proxy nacional Censo 2022 (CLAUDE.md §2, v0005 = media de moradores). So inspecao.
MEDIA_MORADORES_DOMICILIO: float = 2.8

GEO_BASE_DIR_DEFAULT = Path("data/outputs/setores_censitarios_2022_geo")
STAGING_DIR_DEFAULT = Path("data/staging")

# Feature sets canonicos comparados pelo bloco (nome -> lista de colunas de X ja transformadas).
# As colunas log_* sao derivadas dentro de `comparar_modelos_aderencia`.
FEATURE_SETS: dict[str, tuple[str, ...]] = {
    "baseline_pop_renda": ("log_pop", "log_renda"),
    "A_pop_renda_conc": ("log_pop", "log_renda", "n_conc"),
    "B_pop_renda_conc_dens_rendaresp": (
        "log_pop",
        "log_renda",
        "n_conc",
        "log_densidade",
        "log_renda_resp",
    ),
}

# Mapa coluna-transformada -> coluna bruta do df_features (para limpeza de NaN por set).
_FEATURE_FONTE: dict[str, str] = {
    "log_pop": "pop_captacao",
    "log_renda": "renda_per_capita_captacao",
    "n_conc": "n_concorrentes_raio_1_5km",
    "log_densidade": "densidade_pop_catchment_hab_km2",
    "log_renda_resp": "renda_responsavel_media_catchment",
}


@dataclass
class ResultadoModeloFeatures:
    """Metricas LOO honestas de UM feature_set (espelha o subconjunto util de AderenciaModel)."""

    nome: str
    features: tuple[str, ...]
    alpha_selecionado: float
    r2_loo_log: float  # PRINCIPAL (gate)
    r2_loo_pagantes: float  # auditoria
    rmse_loo_log: float
    rmse_loo_pagantes: float
    r2_insample_log: float  # auditoria, NAO decide gate
    coeficientes: dict[str, float]  # nome_feature -> coef
    intercepto_log: float
    n_treinamento: int
    veredito: str  # "GO" se r2_loo_log > LIMIAR_R2_GO senao "NO-GO"

    @property
    def go(self) -> bool:
        return self.veredito == "GO"


def _haversine_km(
    lat1: float,
    lng1: float,
    lat2: np.ndarray,
    lng2: np.ndarray,
) -> np.ndarray:
    """Haversine vetorizado de um ponto (lat1,lng1) para arrays (lat2,lng2). Km."""
    radius_km = 6371.0
    lat1_r = math.radians(lat1)
    lat2_r = np.radians(lat2)
    dlat = lat2_r - lat1_r
    dlng = np.radians(lng2) - math.radians(lng1)
    a = np.sin(dlat / 2) ** 2 + math.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlng / 2) ** 2
    return radius_km * 2 * np.arctan2(np.sqrt(a), np.sqrt(np.maximum(0.0, 1.0 - a)))


def derivar_n_concorrentes_raio(
    df_unidades: pd.DataFrame,
    df_concorrentes: pd.DataFrame,
    raio_km: float = RAIO_FEATURES_KM,
) -> pd.DataFrame:
    """Batch Haversine: conta concorrentes VALIDOS e NAO-duplicados no raio por unidade.

    Filtra `flag_coord_valida == True & flag_duplicado_rede_coord == False` antes de contar.
    Retorna DataFrame [unidade, n_concorrentes_raio_1_5km]. Unidade sem lat/lng -> NaN.
    Implementacao pura (numpy Haversine vetorizado por unidade); SEM I/O.
    """
    conc = df_concorrentes.copy()
    if "flag_coord_valida" in conc.columns:
        conc = conc.loc[conc["flag_coord_valida"].fillna(False).astype(bool)]
    if "flag_duplicado_rede_coord" in conc.columns:
        conc = conc.loc[~conc["flag_duplicado_rede_coord"].fillna(False).astype(bool)]

    conc_lat = pd.to_numeric(conc.get("lat"), errors="coerce")
    conc_lng = pd.to_numeric(conc.get("lng"), errors="coerce")
    conc_ok = conc_lat.notna() & conc_lng.notna()
    lat_arr = conc_lat[conc_ok].to_numpy(dtype=float)
    lng_arr = conc_lng[conc_ok].to_numpy(dtype=float)

    linhas: list[dict] = []
    for _idx, row in df_unidades.iterrows():
        u_lat = pd.to_numeric(row.get("lat"), errors="coerce")
        u_lng = pd.to_numeric(row.get("lng"), errors="coerce")
        if pd.isna(u_lat) or pd.isna(u_lng):
            n_conc: float = float("nan")
        elif lat_arr.size == 0:
            n_conc = 0.0
        else:
            dist = _haversine_km(float(u_lat), float(u_lng), lat_arr, lng_arr)
            n_conc = float(np.count_nonzero(dist <= raio_km))
        linhas.append(
            {"unidade": row.get("unidade"), "n_concorrentes_raio_1_5km": n_conc}
        )
    return pd.DataFrame(linhas, columns=["unidade", "n_concorrentes_raio_1_5km"])


def derivar_features_censo(
    df_unidades: pd.DataFrame,
    geo_base_dir: Path | str = GEO_BASE_DIR_DEFAULT,
    raio_km: float = RAIO_FEATURES_KM,
    setores_loader=None,
) -> pd.DataFrame:
    """Por unidade, reusa `analisar_ponto_censitario_setores` (cache por UF) e extrai:

      - densidade_pop_catchment_hab_km2  = result["densidade_pop_raio_hab_km2"]
      - renda_responsavel_media_catchment = media ponderada de
        `renda_per_capita_setor_2022_calibrada` por `pop_total_setor_2022` em
        result["setores_intersectados"] (NaN se vazio/sem peso)
      - pop_total_raio (auditoria), n_setores_captacao (auditoria)

    Espelha o loop cache-por-UF de `catchment_batch.calcular_catchment_batch`. NAO altera
    o M1; helper INTOCADO. I/O real -> NAO chamado nos testes unitarios.
    """
    # Import lazy para nao acoplar a importacao do modulo ao dashboard/geo.
    from motor_expansao.dashboard.censo_point import (
        analisar_ponto_censitario_setores,
    )

    if setores_loader is None:
        from motor_expansao.dashboard.data import read_censo_geo_partition

        setores_loader = read_censo_geo_partition

    geo_base_dir = Path(geo_base_dir)
    cache_uf: dict[str, pd.DataFrame] = {}
    linhas: list[dict] = []

    for _idx, row in df_unidades.iterrows():
        unidade = row.get("unidade")
        uf = str(row.get("uf") or "").upper()
        lat = pd.to_numeric(row.get("lat"), errors="coerce")
        lng = pd.to_numeric(row.get("lng"), errors="coerce")

        densidade: float = float("nan")
        renda_resp: float = float("nan")
        pop_total: float = float("nan")
        n_setores = 0

        if not pd.isna(lat) and not pd.isna(lng):
            if uf and uf not in cache_uf:
                try:
                    cache_uf[uf] = setores_loader(geo_base_dir, uf)
                except Exception as exc:  # pragma: no cover - IO defensivo
                    logger.warning("Falha ao carregar setores UF=%s: %s", uf, exc)
                    cache_uf[uf] = pd.DataFrame()
            setores = cache_uf.get(uf, pd.DataFrame())
            if setores is not None and not setores.empty:
                res = analisar_ponto_censitario_setores(
                    float(lat), float(lng), setores, raio_km=raio_km
                )
                dens = res.get("densidade_pop_raio_hab_km2")
                densidade = float(dens) if dens is not None else float("nan")
                pop = res.get("pop_total_raio")
                pop_total = float(pop) if pop is not None else float("nan")
                n_setores = int(res.get("n_setores", 0) or 0)
                renda_resp = _renda_resp_ponderada(res.get("setores_intersectados"))

        linhas.append(
            {
                "unidade": unidade,
                "densidade_pop_catchment_hab_km2": densidade,
                "renda_responsavel_media_catchment": renda_resp,
                "pop_total_raio": pop_total,
                "n_setores_captacao_censo": n_setores,
            }
        )

    return pd.DataFrame(
        linhas,
        columns=[
            "unidade",
            "densidade_pop_catchment_hab_km2",
            "renda_responsavel_media_catchment",
            "pop_total_raio",
            "n_setores_captacao_censo",
        ],
    )


def _renda_resp_ponderada(setores: pd.DataFrame | None) -> float:
    """Media ponderada de renda_per_capita_setor_2022_calibrada por pop_total_setor_2022."""
    if setores is None or setores.empty:
        return float("nan")
    if "renda_per_capita_setor_2022_calibrada" not in setores.columns:
        return float("nan")
    renda = pd.to_numeric(
        setores["renda_per_capita_setor_2022_calibrada"], errors="coerce"
    )
    pesos = pd.to_numeric(
        setores.get("pop_total_setor_2022"), errors="coerce"
    ).clip(lower=0)
    valid = renda.notna() & pesos.notna() & pesos.gt(0)
    if valid.any():
        return float(np.average(renda[valid], weights=pesos[valid]))
    valid_r = renda.notna()
    if valid_r.any():
        return float(renda[valid_r].mean())
    return float("nan")


def montar_df_features(
    df_maduras: pd.DataFrame,
    df_catchment: pd.DataFrame,
    df_concorrentes: pd.DataFrame,
    geo_base_dir: Path | str = GEO_BASE_DIR_DEFAULT,
    raio_km: float = RAIO_FEATURES_KM,
) -> pd.DataFrame:
    """Monta o df de 54 unidades com alvo + features base + features exogenas.

    Passos: merge maduras<-catchment[unidade,lat,lng]; dropna(subset=[lat,lng]) (N efetivo ~53);
    derivar_n_concorrentes_raio + derivar_features_censo; juntar tudo por unidade.
    Colunas de saida (minimo): unidade, uf, pagantes_steady_state, pop_captacao,
    renda_per_capita_captacao, n_concorrentes_raio_1_5km, densidade_pop_catchment_hab_km2,
    renda_responsavel_media_catchment. SEM PII versionada (so staging em memoria).
    """
    base_cols = [
        c
        for c in (
            "unidade",
            "uf",
            "pagantes_steady_state",
            "pop_captacao",
            "renda_per_capita_captacao",
        )
        if c in df_maduras.columns
    ]
    df = df_maduras[base_cols].copy()

    latlng = df_catchment[["unidade", "lat", "lng"]].drop_duplicates("unidade")
    df = df.merge(latlng, on="unidade", how="left")

    lat = pd.to_numeric(df["lat"], errors="coerce")
    lng = pd.to_numeric(df["lng"], errors="coerce")
    df = df.loc[lat.notna() & lng.notna()].reset_index(drop=True)

    df_conc = derivar_n_concorrentes_raio(df, df_concorrentes, raio_km=raio_km)
    df_censo = derivar_features_censo(df, geo_base_dir, raio_km=raio_km)

    df = df.merge(df_conc, on="unidade", how="left")
    df = df.merge(df_censo, on="unidade", how="left")
    return df


def _loo_ridge_multifeature(
    X: np.ndarray,
    y: np.ndarray,
    alpha_grid: tuple[float, ...] = ALPHA_GRID,
) -> dict:
    """LOO-CV Ridge multi-feature, alvo y=log(pagantes). Seleciona alpha por MENOR rmse_loo_log.

    Espelha aderencia._r2_loo_para_alpha + a varredura de calibrar_aderencia, mas para X de
    qualquer largura. Sem scaler (features ja em escala log/contagem comparavel). Pura.
    """
    loo = LeaveOneOut()
    melhor_alpha = float(alpha_grid[0])
    melhor_rmse_loo = math.inf
    melhor_r2_loo = -math.inf
    melhor_y_pred = np.zeros(len(y), dtype=float)

    for alpha in alpha_grid:
        y_pred_loo = np.zeros(len(y), dtype=float)
        for train_idx, test_idx in loo.split(X):
            reg_fold = Ridge(alpha=float(alpha))
            reg_fold.fit(X[train_idx], y[train_idx])
            y_pred_loo[test_idx] = reg_fold.predict(X[test_idx])
        rmse_loo = float(math.sqrt(np.mean((y_pred_loo - y) ** 2)))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        ss_res = float(np.sum((y - y_pred_loo) ** 2))
        r2_loo = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        if rmse_loo < melhor_rmse_loo:
            melhor_rmse_loo = rmse_loo
            melhor_r2_loo = r2_loo
            melhor_alpha = float(alpha)
            melhor_y_pred = y_pred_loo

    # Back-transform para o espaco de pagantes.
    pagantes = np.exp(y)
    pagantes_pred_loo = np.exp(melhor_y_pred)
    ss_tot_pag = float(np.sum((pagantes - pagantes.mean()) ** 2))
    ss_res_pag = float(np.sum((pagantes - pagantes_pred_loo) ** 2))
    r2_loo_pagantes = 1.0 - ss_res_pag / ss_tot_pag if ss_tot_pag > 0 else 0.0
    rmse_loo_pagantes = float(math.sqrt(np.mean((pagantes_pred_loo - pagantes) ** 2)))

    # Modelo final no conjunto completo (coeficientes + r2_insample auditoria).
    reg = Ridge(alpha=melhor_alpha)
    reg.fit(X, y)
    y_pred_insample = reg.predict(X)
    ss_tot_log = float(np.sum((y - y.mean()) ** 2))
    ss_res_insample = float(np.sum((y - y_pred_insample) ** 2))
    r2_insample_log = 1.0 - ss_res_insample / ss_tot_log if ss_tot_log > 0 else 0.0

    return {
        "alpha_selecionado": melhor_alpha,
        "r2_loo_log": float(melhor_r2_loo),
        "rmse_loo_log": float(melhor_rmse_loo),
        "r2_loo_pagantes": float(r2_loo_pagantes),
        "rmse_loo_pagantes": rmse_loo_pagantes,
        "r2_insample_log": float(r2_insample_log),
        "coef": np.asarray(reg.coef_, dtype=float),
        "intercepto_log": float(reg.intercept_),
    }


def _transformar_features(df: pd.DataFrame) -> pd.DataFrame:
    """Deriva as colunas log_*/n_conc das colunas brutas. NAO muta o df de entrada."""
    out = df.copy()
    pop = pd.to_numeric(out.get("pop_captacao"), errors="coerce")
    renda = pd.to_numeric(out.get("renda_per_capita_captacao"), errors="coerce")
    out["log_pop"] = np.where(pop > 0, np.log(pop.where(pop > 0)), np.nan)
    out["log_renda"] = np.where(renda > 0, np.log(renda.where(renda > 0)), np.nan)
    out["n_conc"] = pd.to_numeric(
        out.get("n_concorrentes_raio_1_5km"), errors="coerce"
    )
    dens = pd.to_numeric(
        out.get("densidade_pop_catchment_hab_km2"), errors="coerce"
    )
    out["log_densidade"] = np.log1p(dens.clip(lower=0))
    renda_resp = pd.to_numeric(
        out.get("renda_responsavel_media_catchment"), errors="coerce"
    )
    out["log_renda_resp"] = np.where(
        renda_resp > 0, np.log(renda_resp.where(renda_resp > 0)), np.nan
    )
    return out


def comparar_modelos_aderencia(
    df_features: pd.DataFrame,
    feature_sets: dict[str, tuple[str, ...]] = FEATURE_SETS,
    limiar_r2: float = LIMIAR_R2_GO,
) -> dict[str, ResultadoModeloFeatures]:
    """Para cada feature_set, monta X (deriva log_pop, log_renda, n_conc, log_densidade,
    log_renda_resp das colunas brutas), roda `_loo_ridge_multifeature`, e devolve
    {nome -> ResultadoModeloFeatures}. Limpeza: dropna/<=0 em pagantes/pop/renda (espelha
    aderencia). Linhas com NaN em QUALQUER feature do set sao removidas SO para aquele set.
    Raise ValueError se n efetivo < N_MIN_CALIBRACAO.
    """
    if "pagantes_steady_state" not in df_features.columns:
        raise ValueError("Coluna 'pagantes_steady_state' ausente no df_features.")

    work = _transformar_features(df_features)
    pagantes = pd.to_numeric(work["pagantes_steady_state"], errors="coerce")
    work["_y_log"] = np.where(pagantes > 0, np.log(pagantes.where(pagantes > 0)), np.nan)

    resultados: dict[str, ResultadoModeloFeatures] = {}
    for nome, features in feature_sets.items():
        cols = list(features)
        subset = work[[*cols, "_y_log"]].copy()
        subset = subset.replace([np.inf, -np.inf], np.nan).dropna()
        n = len(subset)
        if n < N_MIN_CALIBRACAO:
            raise ValueError(
                f"Dados insuficientes para o feature_set '{nome}': {n} linhas "
                f"(minimo {N_MIN_CALIBRACAO})."
            )
        X = subset[cols].to_numpy(dtype=float)
        y = subset["_y_log"].to_numpy(dtype=float)
        m = _loo_ridge_multifeature(X, y)
        veredito = "GO" if m["r2_loo_log"] > limiar_r2 else "NO-GO"
        coeficientes = {c: float(v) for c, v in zip(cols, m["coef"], strict=True)}
        resultados[nome] = ResultadoModeloFeatures(
            nome=nome,
            features=tuple(cols),
            alpha_selecionado=m["alpha_selecionado"],
            r2_loo_log=m["r2_loo_log"],
            r2_loo_pagantes=m["r2_loo_pagantes"],
            rmse_loo_log=m["rmse_loo_log"],
            rmse_loo_pagantes=m["rmse_loo_pagantes"],
            r2_insample_log=m["r2_insample_log"],
            coeficientes=coeficientes,
            intercepto_log=m["intercepto_log"],
            n_treinamento=n,
            veredito=veredito,
        )
    return resultados


def _melhora_material(
    resultado: ResultadoModeloFeatures, baseline_r2: float
) -> bool:
    """GO material: r2_loo_log > LIMIAR_R2_GO AND > baseline + DELTA_MATERIAL."""
    return (
        resultado.r2_loo_log > LIMIAR_R2_GO
        and resultado.r2_loo_log > baseline_r2 + DELTA_MATERIAL
    )


def escrever_relatorio_features(
    resultados: dict[str, ResultadoModeloFeatures],
    *,
    path: Path,
    correlacoes: dict[str, float] | None = None,
    n_lacunas_latlng: int = 0,
) -> None:
    """Materializa data/analysis/features_aderencia.md (gitignored). NAO chamado em teste.

    Tabela feature_set x r2_loo_log x r2_loo_pagantes x rmse_loo_log x n x veredito;
    delta vs baseline; secao de confounds (N~53, cobertura OSM, colinearidade, lacuna
    etaria/CLT); veredito consolidado (melhora material?). READ-ONLY sobre o M1.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    baseline = resultados.get("baseline_pop_renda")
    baseline_r2 = baseline.r2_loo_log if baseline is not None else float("nan")

    linhas: list[str] = []
    linhas.append("# Features exogenas na aderencia (Camada 1) -- BLK-DIM-05")
    linhas.append("")
    linhas.append(
        "Alvo = `log(pagantes_steady_state)`. Compara feature_sets via LOO-CV Ridge "
        "multi-feature (selecao de alpha por MENOR rmse_loo_log). READ-ONLY sobre o M1 "
        "(DEC-001); `aderencia.py` congelado (BLK-DIM-01R)."
    )
    linhas.append("")
    linhas.append(
        "Forma funcional: `log(pagantes) = b0 + Σ b_i * x_i`, com "
        "`x ∈ {log(pop), log(renda), n_conc, log1p(densidade), log(renda_resp)}`."
    )
    linhas.append("")
    linhas.append("## Resultados por feature_set")
    linhas.append("")
    linhas.append(
        "| feature_set | n | alpha | r2_loo_log | r2_loo_pagantes | rmse_loo_log | veredito |"
    )
    linhas.append("| --- | ---: | ---: | ---: | ---: | ---: | --- |")
    for nome, r in resultados.items():
        linhas.append(
            f"| {nome} | {r.n_treinamento} | {r.alpha_selecionado:g} | "
            f"{r.r2_loo_log:+.4f} | {r.r2_loo_pagantes:+.4f} | {r.rmse_loo_log:.4f} | {r.veredito} |"
        )
    linhas.append("")
    linhas.append("## Delta vs baseline (materialidade)")
    linhas.append("")
    linhas.append(
        f"Baseline `baseline_pop_renda` r2_loo_log = **{baseline_r2:+.4f}**. "
        f"Melhora MATERIAL exige `r2_loo_log > {LIMIAR_R2_GO}` E "
        f"`> baseline + {DELTA_MATERIAL}` (5 p.p.)."
    )
    linhas.append("")
    linhas.append("| feature_set | Δr2_loo_log vs baseline | melhora material? |")
    linhas.append("| --- | ---: | --- |")
    for nome, r in resultados.items():
        if nome == "baseline_pop_renda":
            continue
        delta = r.r2_loo_log - baseline_r2
        material = "SIM" if _melhora_material(r, baseline_r2) else "nao"
        linhas.append(f"| {nome} | {delta:+.4f} | {material} |")
    linhas.append("")
    if correlacoes:
        linhas.append("## Correlacoes (interpretabilidade)")
        linhas.append("")
        for k, v in correlacoes.items():
            linhas.append(f"- ρ({k}) = {v:+.3f}")
        rr = correlacoes.get("renda_resp_vs_captacao")
        if rr is not None and abs(rr) > 0.85:
            linhas.append("")
            linhas.append(
                "> COLINEARIDADE: `renda_responsavel_media_catchment` x "
                "`renda_per_capita_captacao` com |ρ| > 0.85 -- a feature de renda do "
                "responsavel agrega pouco sinal novo (mantida no modelo B apenas para "
                "auditoria; nao decide o gate)."
            )
        linhas.append("")
    linhas.append("## Confounds e limitacoes")
    linhas.append("")
    linhas.append(
        f"1. **N pequeno (~{baseline.n_treinamento if baseline else 'NA'})**: "
        f"estruturalmente pequeno ({n_lacunas_latlng} unidade(s) sem lat/lng removida(s)); "
        "LOO instavel entre alphas. Herdado do BLK-DIM-01R."
    )
    linhas.append(
        "2. **Cobertura OSM dos concorrentes**: a contagem por raio subestima a "
        "concorrencia em cidades menores (mapeamento incompleto)."
    )
    linhas.append(
        "3. **Colinearidade renda_resp x captacao**: ambas vem da renda censitaria; "
        "a renda do responsavel agrega pouco sinal exogeno (ver correlacoes acima)."
    )
    linhas.append(
        "4. **LACUNA CENTRAL -- features comportamentais ausentes**: faixa etaria 18-45, "
        "vinculo formal CLT e % de ocupados NAO existem no Censo 2022 Basico por setor "
        "(microdados IBGE ~10 GB, fora do escopo loop-safe). O titulo do bloco cita essas "
        "features, mas elas NAO estao nos insumos -> trabalho futuro (BLK-DIM-06)."
    )
    linhas.append(
        "5. **Vies de selecao**: as unidades abertas sao amostra enviesada (Ultra so abriu "
        "onde foi viavel) -> superestima aderencia em regioes similares (herdado do 01R)."
    )
    linhas.append("")
    linhas.append("## Veredito consolidado")
    linhas.append("")
    algum_material = any(
        _melhora_material(r, baseline_r2)
        for nome, r in resultados.items()
        if nome != "baseline_pop_renda"
    )
    if algum_material:
        linhas.append(
            "**GO MATERIAL**: ao menos um feature_set exogeno supera o baseline em mais de "
            f"{DELTA_MATERIAL} de r2_loo_log e fica acima de {LIMIAR_R2_GO}. As features "
            "exogenas adicionam sinal preditivo honesto."
        )
    else:
        linhas.append(
            "**NO-GO honesto**: nenhuma feature exogena melhora MATERIALMENTE o baseline "
            f"pop+renda (regra: r2_loo_log > {LIMIAR_R2_GO} E > baseline + {DELTA_MATERIAL}). "
            "NO-GO e resultado VALIDO e ESPERADO dado N~53 e a ausencia das features "
            "comportamentais reais (faixa etaria/CLT). Consistente com a DEC-001 e o "
            "BLK-DIM-01R (r2_loo_log = -0.0134)."
        )
    linhas.append("")

    path.write_text("\n".join(linhas), encoding="utf-8")


def main() -> None:  # pragma: no cover
    """Caminho REAL (nao testado): le os 3 parquets, monta df_features, compara, escreve relatorio."""
    df_maduras = pd.read_parquet(STAGING_DIR_DEFAULT / "base_calibracao_maduras.parquet")
    df_catchment = pd.read_parquet(
        STAGING_DIR_DEFAULT / "unidades_ultra_catchment.parquet"
    )
    df_conc = pd.read_parquet(STAGING_DIR_DEFAULT / "concorrentes_mapeados.parquet")

    n_total = len(df_maduras)
    df_features = montar_df_features(
        df_maduras, df_catchment, df_conc, GEO_BASE_DIR_DEFAULT
    )
    n_lacunas = n_total - len(df_features)

    resultados = comparar_modelos_aderencia(df_features)

    # Correlacoes para interpretabilidade (sem PII).
    correlacoes: dict[str, float] = {}
    try:
        rr = df_features[
            ["renda_responsavel_media_catchment", "renda_per_capita_captacao"]
        ].apply(pd.to_numeric, errors="coerce")
        correlacoes["renda_resp_vs_captacao"] = float(
            rr.corr().iloc[0, 1]
        )
        cp = df_features[["n_concorrentes_raio_1_5km", "pagantes_steady_state"]].apply(
            pd.to_numeric, errors="coerce"
        )
        correlacoes["n_conc_vs_pagantes"] = float(cp.corr().iloc[0, 1])
        dp = df_features[
            ["densidade_pop_catchment_hab_km2", "pagantes_steady_state"]
        ].apply(pd.to_numeric, errors="coerce")
        correlacoes["densidade_vs_pagantes"] = float(dp.corr().iloc[0, 1])
    except Exception as exc:
        logger.warning("Falha ao computar correlacoes: %s", exc)

    escrever_relatorio_features(
        resultados,
        path=Path("data/analysis/features_aderencia.md"),
        correlacoes=correlacoes,
        n_lacunas_latlng=n_lacunas,
    )
    for nome, r in resultados.items():
        logger.info(
            "feature_set=%s n=%d r2_loo_log=%.4f veredito=%s",
            nome,
            r.n_treinamento,
            r.r2_loo_log,
            r.veredito,
        )


__all__ = [
    "ResultadoModeloFeatures",
    "derivar_n_concorrentes_raio",
    "derivar_features_censo",
    "montar_df_features",
    "comparar_modelos_aderencia",
    "escrever_relatorio_features",
    "FEATURE_SETS",
    "ALPHA_GRID",
    "LIMIAR_R2_GO",
    "RAIO_FEATURES_KM",
]


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    main()
