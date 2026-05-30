"""
jobs/pipelines/hex_enrichment.py — M1 Geográfico / Fase 1

Contrato canônico atual do MVP nacional:
  - métrica oficial: hex_score_estrutural
  - fechamento nacional: estrutural -> priorização -> camada de oportunidade
  - OSM: opcional/futuro, fora do fechamento oficial nacional

Fluxos legados com OSM permanecem no arquivo para uso pontual/local, mas não são a
dependência operacional do pipeline oficial do M1.
"""

import argparse
import math
import time
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import structlog
from geopy.distance import geodesic
from geopy.geocoders import Nominatim

try:
    from api.config import settings
except ModuleNotFoundError:
    from config import settings  # estrutura flat (desenvolvimento)

try:
    from jobs.pipelines.ibge_censo import IBGECenso, carregar_lookup_municipios_ibge
    from jobs.pipelines.poi_enrichment import POIEnricher
except ModuleNotFoundError:
    from ibge_censo import IBGECenso, carregar_lookup_municipios_ibge  # estrutura flat
    from poi_enrichment import POIEnricher

from motor_expansao.core import scoring as _scoring
from motor_expansao.core.constants import (
    CAPITAIS_UF,
    CAPITAL_POR_CODIGO,
    FAIXAS_OPORTUNIDADE,
    OSM_STATUS_NAO_APLICADO,
    PERCENTIL_CORTE_INFERIOR,
    PERCENTIL_CORTE_SUPERIOR,
)
from motor_expansao.core.scoring import (
    _calcular_percentil_nacional,
    _serie_numerica,
    calcular_ajuste_executivo,
    calcular_hex_score,
    calcular_populacao_proxy,
    normalizar_0_100,  # noqa: F401 - re-exportado: tests/wrappers fazem `from hex_enrichment import normalizar_0_100`
    normalizar_serie,  # noqa: F401 - re-exportado: tests/wrappers fazem `from hex_enrichment import normalizar_serie`
    resumir_distribuicao_score,
)

log = structlog.get_logger()


def gerar_hexagonos_cidade(cidade: str, uf: str, raio_km: float = 20.0) -> list[str]:
    geolocator = Nominatim(user_agent="motor_expansao_ultra_academia", timeout=10)
    location = geolocator.geocode(f"{cidade}, {uf}, Brasil")
    time.sleep(1.1)
    if not location:
        log.error("cidade_nao_encontrada", cidade=cidade, uf=uf)
        return []
    lat, lng = location.latitude, location.longitude
    # Resolução 7: cada anel cobre ~1.2km → raio_km / 1.2
    k = max(1, int(raio_km / 1.2))
    hex_centro = h3.latlng_to_cell(lat, lng, settings.H3_RESOLUTION)
    hexagonos = list(h3.grid_disk(hex_centro, k))
    log.info("hexagonos_gerados", cidade=cidade, total=len(hexagonos), resolucao=settings.H3_RESOLUTION)
    return hexagonos


def calcular_hex_score_estrutural(df: pd.DataFrame) -> pd.DataFrame:
    return _scoring.calcular_hex_score_estrutural(df)


def calcular_score_concorrencia(df: pd.DataFrame) -> pd.Series:
    return _scoring.calcular_score_concorrencia(df)


def calcular_hex_score_final(df: pd.DataFrame) -> pd.DataFrame:
    return _scoring.calcular_hex_score_final(df)


def verificar_canibalizacao(hex_id: str, unidades_ultra: list) -> dict:
    lat, lng = h3.cell_to_latlng(hex_id)
    if not unidades_ultra:
        return {"tem_ultra_proxima": False, "dist_ultra_mais_proxima_km": None}
    dists = [geodesic((lat, lng), u).km for u in unidades_ultra]
    dist_min = min(dists)
    return {
        "tem_ultra_proxima": dist_min < settings.DIST_MIN_ULTRA_KM,
        "dist_ultra_mais_proxima_km": round(dist_min, 2),
    }


def enriquecer_hexagono(hex_id: str, uf: str, censo: IBGECenso, poi: POIEnricher) -> dict:
    """Enriquece um hexágono usando dados pré-carregados (sem HTTP por hex)."""
    lat, lng = h3.cell_to_latlng(hex_id)
    ibge = censo.features_para_coordenada(lat, lng, uf)
    return {
        "hex_id":            hex_id,
        "lat":               lat,
        "lng":               lng,
        "renda_per_capita":  ibge.get("renda_per_capita", 0),
        "pop_total":         ibge.get("pop_total", 0),
        "n_domicilios":      ibge.get("n_domicilios", 0),
        "densidade_dom":     ibge.get("densidade_dom", 0),
        "fonte_demografica": ibge.get("fonte", ""),
        "fonte_renda":       ibge.get("fonte_renda", ""),
        "fonte_populacao":   ibge.get("fonte_populacao", ""),
        "nivel_geografico_ibge": ibge.get("nivel_geografico_ibge", ""),
        "fallback_setor_censitario": ibge.get("fallback_setor_censitario", True),
        "motivo_fallback_setor": ibge.get("motivo_fallback_setor", ""),
        "data_referencia_ibge": "censo_2022",
        "n_academias_osm":   poi.contar_academias_proximas(lat, lng),
        "score_vitalidade":  50.0,  # Google Places: fallback neutro sem API key
    }


def rodar_pipeline_hex(cidade: str, uf: str, raio_km: float = 20.0, unidades_ultra: list | None = None) -> pd.DataFrame:
    unidades_ultra = unidades_ultra or []
    log.info("pipeline_hex_iniciado", cidade=cidade, uf=uf, resolucao=settings.H3_RESOLUTION)

    censo = IBGECenso()
    poi   = POIEnricher()

    # ── 1. Gerar hexágonos ─────────────────────────────────────────────────
    hexagonos = gerar_hexagonos_cidade(cidade, uf, raio_km)
    if not hexagonos:
        return pd.DataFrame()

    # ── 2. Resolver município UMA VEZ (sem Nominatim por hexágono) ────────
    cod_municipio = censo.resolver_municipio(cidade, uf)
    if cod_municipio:
        # Pré-aquece o cache SIDRA para o município (1 request)
        censo._sidra_renda_populacao(cod_municipio)
    else:
        # Se resolver falhou, define município vazio para evitar N chamadas Nominatim
        # features_municipio_sidra retornará _features_padrao() diretamente
        censo.set_municipio_padrao("__nenhum__", uf)
        log.warning("ibge_municipio_nao_resolvido", cidade=cidade, uf=uf,
                    msg="Demograficos ficarao com fallback_padrao — sem loop Nominatim")

    # ── 3. UMA query OSM para bbox de toda a cidade ────────────────────────
    lats = [h3.cell_to_latlng(h)[0] for h in hexagonos]
    lngs = [h3.cell_to_latlng(h)[1] for h in hexagonos]
    margem = 0.02  # ~2km
    poi.carregar_academias_cidade(
        lat_min=min(lats) - margem, lat_max=max(lats) + margem,
        lng_min=min(lngs) - margem, lng_max=max(lngs) + margem,
    )

    # ── 4. Enriquecer cada hexágono (sem HTTP — dados pré-carregados) ──────
    registros = []
    for i, hex_id in enumerate(hexagonos):
        if i % 50 == 0:
            log.info("progresso", i=i, total=len(hexagonos))
        dados = enriquecer_hexagono(hex_id, uf, censo, poi)
        dados.update(verificar_canibalizacao(hex_id, unidades_ultra))
        dados["cidade"] = cidade
        dados["uf"] = uf
        registros.append(dados)

    # ── 5. Score e exportação ──────────────────────────────────────────────
    df = calcular_hex_score(pd.DataFrame(registros))
    df = df.sort_values("hex_score", ascending=False).reset_index(drop=True)

    slug = cidade.lower().replace(" ", "_")
    out  = f"data/staging/hexagonos_{slug}_{uf.lower()}.parquet"
    df.to_parquet(out, index=False)
    log.info("pipeline_concluido", cidade=cidade, total=len(df), output=out)
    return df


def _coletar_cidade(cidade: str, uf: str, raio_km: float, unidades_ultra: list) -> pd.DataFrame:
    """
    Coleta e enriquece hexágonos de uma cidade SEM aplicar normalização nem calcular hex_score.
    Usado pelo pipeline batch para consolidação global antes da normalização.
    Retorna DataFrame com dados brutos (renda, pop, n_academias, score_vitalidade).
    """
    log.info("batch_coleta_iniciada", cidade=cidade, uf=uf)
    censo = IBGECenso()
    poi   = POIEnricher()

    hexagonos = gerar_hexagonos_cidade(cidade, uf, raio_km)
    if not hexagonos:
        log.warning("batch_sem_hexagonos", cidade=cidade, uf=uf)
        return pd.DataFrame()

    cod_municipio = censo.resolver_municipio(cidade, uf)
    if cod_municipio:
        censo._sidra_renda_populacao(cod_municipio)
    else:
        censo.set_municipio_padrao("__nenhum__", uf)
        log.warning("ibge_municipio_nao_resolvido", cidade=cidade, uf=uf,
                    msg="Demograficos ficarao com fallback_padrao — sem loop Nominatim")

    lats = [h3.cell_to_latlng(h)[0] for h in hexagonos]
    lngs = [h3.cell_to_latlng(h)[1] for h in hexagonos]
    margem = 0.02
    poi.carregar_academias_cidade(
        lat_min=min(lats) - margem, lat_max=max(lats) + margem,
        lng_min=min(lngs) - margem, lng_max=max(lngs) + margem,
    )

    registros = []
    for i, hex_id in enumerate(hexagonos):
        if i % 100 == 0:
            log.info("batch_progresso", cidade=cidade, i=i, total=len(hexagonos))
        dados = enriquecer_hexagono(hex_id, uf, censo, poi)
        dados.update(verificar_canibalizacao(hex_id, unidades_ultra))
        dados["cidade"] = cidade
        dados["uf"]     = uf
        registros.append(dados)

    df = pd.DataFrame(registros)
    log.info("batch_coleta_concluida", cidade=cidade, hexagonos=len(df))
    return df


def rodar_pipeline_batch(
    cidades: list[tuple[str, str]],
    raio_km: float = 15.0,
    unidades_ultra: list | None = None,
    nome_arquivo: str = "hexagonos_multicidade",
) -> pd.DataFrame:
    """
    Executa o pipeline M1 para múltiplas cidades com normalização global do hex_score.

    Parâmetros:
        cidades: lista de tuplas (cidade, uf), ex: [("Goiania", "GO"), ("Campinas", "SP")]
        raio_km: raio de cobertura por cidade
        unidades_ultra: lista de (lat, lng) de unidades Ultra existentes (anti-canibalização)
        nome_arquivo: prefixo do parquet consolidado em data/staging/

    Retorna:
        DataFrame consolidado com hex_score normalizado globalmente.
        Também salva parquets individuais por cidade (compatibilidade com pipeline atual).
    """
    unidades_ultra = unidades_ultra or []
    log.info("batch_iniciado", cidades=[f"{c}/{u}" for c, u in cidades], raio_km=raio_km)

    # ── 1. Coletar dados brutos de cada cidade (sem score) ─────────────────
    frames = []
    for cidade, uf in cidades:
        import time as _time
        t0 = _time.time()
        df_cidade = _coletar_cidade(cidade, uf, raio_km, unidades_ultra)
        elapsed = _time.time() - t0
        log.info("batch_cidade_ok", cidade=cidade, uf=uf, hexagonos=len(df_cidade), tempo_s=round(elapsed, 1))
        if not df_cidade.empty:
            frames.append(df_cidade)

    if not frames:
        log.error("batch_sem_dados")
        return pd.DataFrame()

    # ── 2. Consolidar ──────────────────────────────────────────────────────
    df_total = pd.concat(frames, ignore_index=True)
    log.info("batch_consolidado", total_hexagonos=len(df_total), cidades=len(frames))

    # ── 3. Normalização GLOBAL e recálculo de hex_score ───────────────────
    df_total = calcular_hex_score(df_total)
    df_total = df_total.sort_values("hex_score", ascending=False).reset_index(drop=True)

    # ── 4. Salvar parquet consolidado ──────────────────────────────────────
    out_consolidado = f"data/staging/{nome_arquivo}.parquet"
    df_total.to_parquet(out_consolidado, index=False)
    log.info("batch_parquet_consolidado_salvo", path=out_consolidado, total=len(df_total))

    # ── 5. Salvar parquets individuais por cidade (retrocompatibilidade) ───
    for cidade, uf in cidades:
        slug = cidade.lower().replace(" ", "_")
        out_cidade = f"data/staging/hexagonos_{slug}_{uf.lower()}.parquet"
        df_cidade = df_total[df_total["cidade"] == cidade].copy()
        if not df_cidade.empty:
            df_cidade.to_parquet(out_cidade, index=False)
            log.info("batch_parquet_cidade_salvo", cidade=cidade, path=out_cidade)

    log.info("batch_concluido", total=len(df_total), cidades=len(frames))
    return df_total


def _listar_particoes_brasil(input_root: Path) -> list[tuple[str, Path]]:
    particoes = []
    for path in sorted(input_root.glob("uf=*/hexagonos.parquet")):
        uf = path.parent.name.split("=", 1)[1]
        particoes.append((uf, path))
    if not particoes:
        raise FileNotFoundError(f"Nenhuma particao nacional encontrada em {input_root}")
    return particoes


def _salvar_particao_uf(df: pd.DataFrame, output_root: Path, uf: str) -> Path:
    target_dir = output_root / f"uf={uf}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "hexagonos.parquet"
    df.to_parquet(target_path, index=False)
    return target_path


def enriquecer_hexagonos_uf_brasil(
    df_hex_uf: pd.DataFrame,
    uf: str,
    censo: IBGECenso,
    poi: POIEnricher,
    refresh_demografia: bool = False,
    refresh_malha: bool = False,
) -> pd.DataFrame:
    log.info("enriquecimento_uf_iniciado", uf=uf, hexagonos=len(df_hex_uf))

    lat_span = float(df_hex_uf["lat"].max() - df_hex_uf["lat"].min())
    lng_span = float(df_hex_uf["lng"].max() - df_hex_uf["lng"].min())
    if len(df_hex_uf) <= 2_000:
        window_step = 0.125
    elif len(df_hex_uf) <= 15_000:
        window_step = 0.25
    elif len(df_hex_uf) <= 80_000:
        window_step = 0.5
    else:
        window_step = 0.75

    df = censo.enriquecer_dataframe_hexagonos(
        df_hex_uf,
        uf=uf,
        refresh_malha=refresh_malha,
        refresh_demografia=refresh_demografia,
    )
    academias = poi.buscar_academias_em_janelas(
        df[["lat", "lng"]],
        lat_step=window_step,
        lng_step=window_step,
        contexto=f"uf_{uf}",
    )
    df["n_academias_osm"] = poi.contar_academias_em_lote(
        df[["lat", "lng"]],
        academias=academias,
    ).astype(int)
    if int(df["n_academias_osm"].sum()) == 0:
        raise RuntimeError(
            f"{uf}: n_academias_osm zerado em toda a UF; coleta OSM tratada como falha bloqueante."
        )

    df["score_vitalidade"] = 50.0
    df["renda_per_capita"] = pd.to_numeric(df["renda_per_capita"], errors="coerce").fillna(0.0)
    df["pop_total"] = pd.to_numeric(df["pop_total"], errors="coerce").fillna(0.0)
    df["n_domicilios"] = pd.to_numeric(df["n_domicilios"], errors="coerce").fillna(0.0)
    df["densidade_dom"] = pd.to_numeric(df["densidade_dom"], errors="coerce").fillna(0.0)
    df["fonte_demografica"] = df["fonte_demografica"].fillna("fallback_padrao")

    log.info(
        "enriquecimento_uf_concluido",
        uf=uf,
        hexagonos=len(df),
        lat_span=round(lat_span, 2),
        lng_span=round(lng_span, 2),
        window_step=window_step,
        academias_osm=len(academias),
        renda_preenchida=int((df["renda_per_capita"] > 0).sum()),
        pop_preenchida=int((df["pop_total"] > 0).sum()),
    )
    return df


def enriquecer_hexagonos_uf_estrutural(
    df_hex_uf: pd.DataFrame,
    uf: str,
    censo: IBGECenso,
    refresh_demografia: bool = False,
    refresh_malha: bool = False,
) -> pd.DataFrame:
    log.info("enriquecimento_uf_estrutural_iniciado", uf=uf, hexagonos=len(df_hex_uf))

    df = censo.enriquecer_dataframe_hexagonos(
        df_hex_uf,
        uf=uf,
        refresh_malha=refresh_malha,
        refresh_demografia=refresh_demografia,
    )
    df["renda_per_capita"] = pd.to_numeric(df["renda_per_capita"], errors="coerce").fillna(0.0)
    df["pop_total"] = pd.to_numeric(df["pop_total"], errors="coerce").fillna(0.0)
    df["n_domicilios"] = pd.to_numeric(df["n_domicilios"], errors="coerce").fillna(0.0)
    df["densidade_dom"] = pd.to_numeric(df["densidade_dom"], errors="coerce").fillna(0.0)
    if "nome_municipio" not in df.columns:
        df["nome_municipio"] = ""
    else:
        df["nome_municipio"] = df["nome_municipio"].fillna("")
    df["fonte_demografica"] = df["fonte_demografica"].fillna("fallback_padrao")
    df["confianca_geografica"] = "municipal"
    df = calcular_hex_score_estrutural(df)

    log.info(
        "enriquecimento_uf_estrutural_concluido",
        uf=uf,
        hexagonos=len(df),
        renda_preenchida=int((df["renda_per_capita"] > 0).sum()),
        pop_proxy_preenchida=int((df["populacao_proxy"] > 0).sum()),
        municipios=df["cod_municipio"].nunique(dropna=True),
    )
    return df


def resumir_validacao_estrutural(df_total: pd.DataFrame) -> dict:
    df = df_total.copy()
    df["populacao_proxy"] = calcular_populacao_proxy(df)
    score_estrutural = pd.to_numeric(df["hex_score_estrutural"], errors="coerce")
    score_priorizacao = pd.to_numeric(df.get("score_priorizacao"), errors="coerce")
    fallback_pct = round(float(df.get("fallback_setor_censitario", pd.Series([True] * len(df))).fillna(True).mean() * 100), 2)
    rastreabilidade_ibge = (
        df.groupby(
            ["nivel_geografico_ibge", "fonte_renda", "fonte_populacao", "motivo_fallback_setor"],
            dropna=False,
            sort=True,
        )
        .size()
        .reset_index(name="hexagonos")
    )
    atribuicao_municipio = (
        df.groupby("metodo_atribuicao_municipio", dropna=False, sort=True)
        .size()
        .reset_index(name="hexagonos")
    ) if "metodo_atribuicao_municipio" in df.columns else pd.DataFrame()
    rows_uf = []
    for uf, grupo in df.groupby("uf", sort=True):
        rows_uf.append(
            {
                "uf": uf,
                "hexagonos": int(len(grupo)),
                "municipios": int(grupo["cod_municipio"].nunique(dropna=True)),
                "renda_preenchida_pct": round(float((grupo["renda_per_capita"] > 0).mean() * 100), 2),
                "pop_proxy_preenchida_pct": round(float((grupo["populacao_proxy"] > 0).mean() * 100), 2),
                "score_estrutural_min": round(float(grupo["hex_score_estrutural"].min()), 2),
                "score_estrutural_max": round(float(grupo["hex_score_estrutural"].max()), 2),
                "score_priorizacao_min": round(float(grupo["score_priorizacao"].min()), 2),
                "score_priorizacao_max": round(float(grupo["score_priorizacao"].max()), 2),
            }
        )

    top20 = (
        df.sort_values("hex_score_estrutural", ascending=False)
        .head(20)[
            [
                "uf",
                "nome_municipio",
                "hex_id",
                "lat",
                "lng",
                "renda_per_capita",
                "populacao_proxy",
                "hex_score_estrutural",
                "ajuste_executivo",
                "score_priorizacao",
            ]
        ]
        .copy()
    )
    return {
        "total_hexagonos": int(len(df)),
        "preenchimento_renda_pct": round(float((df["renda_per_capita"] > 0).mean() * 100), 2),
        "preenchimento_pop_pct": round(float((df["populacao_proxy"] > 0).mean() * 100), 2),
        "fallback_setor_censitario_pct": fallback_pct,
        "distribuicao_score_estrutural": resumir_distribuicao_score(score_estrutural),
        "distribuicao_score_priorizacao": resumir_distribuicao_score(score_priorizacao),
        "rastreabilidade_ibge": rastreabilidade_ibge,
        "atribuicao_municipio": atribuicao_municipio,
        "resumo_uf": pd.DataFrame(rows_uf),
        "top20_brasil": top20,
    }


def _normalizar_codigo_municipio(serie: pd.Series) -> pd.Series:
    return serie.fillna("").astype(str).str.replace(".0", "", regex=False).str.zfill(7)


def _resolver_nomes_municipio(codigos_municipio: pd.Series) -> pd.Series:
    lookup = carregar_lookup_municipios_ibge()
    if lookup.empty:
        return pd.Series([""] * len(codigos_municipio), index=codigos_municipio.index, dtype="string")

    mapping = (
        lookup[["cod_municipio", "nome_municipio"]]
        .drop_duplicates(subset=["cod_municipio"], keep="first")
        .set_index("cod_municipio")["nome_municipio"]
        .astype("string")
    )
    return codigos_municipio.astype("string").map(mapping).fillna("").astype("string")


def _garantir_nomes_municipio(df: pd.DataFrame) -> pd.DataFrame:
    if "cod_municipio" not in df.columns:
        return df

    df = df.copy()
    df["cod_municipio"] = _normalizar_codigo_municipio(df["cod_municipio"])
    nomes_atuais = (
        df["nome_municipio"].fillna("").astype("string").str.strip()
        if "nome_municipio" in df.columns
        else pd.Series([""] * len(df), index=df.index, dtype="string")
    )
    nomes_lookup = _resolver_nomes_municipio(df["cod_municipio"])
    df["nome_municipio"] = nomes_atuais.where(nomes_atuais.ne(""), nomes_lookup).fillna("").astype(str)
    return df


_FAIXAS_SCORE = ["descartado", "baixa", "media", "alta", "prioridade_maxima"]


def _definir_faixa_oportunidade(percentil_score: pd.Series) -> pd.Series:
    faixa = pd.cut(
        percentil_score,
        bins=[-float("inf"), 35, 50, 65, 80, float("inf")],
        labels=_FAIXAS_SCORE,
        right=False,
    )
    return faixa.astype("object").fillna("descartado")


def _combinar_rotulos(
    index: pd.Index,
    regras: list[tuple[pd.Series, str]],
    default: str,
) -> pd.Series:
    resultado = pd.Series([""] * len(index), index=index, dtype="object")
    for mascara, label in regras:
        mascara = mascara.fillna(False)
        if not mascara.any():
            continue
        sem_valor = resultado.eq("")
        idx_novo = mascara & sem_valor
        idx_concat = mascara & ~sem_valor
        if idx_novo.any():
            resultado.loc[idx_novo] = label
        if idx_concat.any():
            resultado.loc[idx_concat] = resultado.loc[idx_concat] + " | " + label
    return resultado.replace("", default)


def preparar_base_oportunidades(
    df_estrutural: pd.DataFrame,
    df_priorizados: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    if df_estrutural.empty:
        vazio = df_estrutural.copy()
        return vazio, {"distribuicao_faixa": pd.DataFrame(), "pct_viavel": 0.0}

    df = _garantir_nomes_municipio(df_estrutural.copy())
    df["cod_municipio"] = _normalizar_codigo_municipio(df["cod_municipio"])

    df_prior = df_priorizados.copy()
    if not df_prior.empty:
        df_prior["cod_municipio"] = _normalizar_codigo_municipio(df_prior["cod_municipio"])
        df_prior["flag_prioridade"] = True
        df = df.merge(
            df_prior[["hex_id", "flag_prioridade"]].drop_duplicates("hex_id"),
            on="hex_id",
            how="left",
        )
        thresholds_uf = (
            df_prior.groupby("uf", sort=True, as_index=False)
            .agg(
                criterio_prioridade=("criterio_prioridade", "first"),
                threshold_prioridade_uf=("threshold_prioridade_uf", "first"),
            )
        )
        df = df.merge(thresholds_uf, on="uf", how="left")
    else:
        df["flag_prioridade"] = False
        df["criterio_prioridade"] = ""
        df["threshold_prioridade_uf"] = np.nan

    df["flag_prioridade"] = df["flag_prioridade"].eq(True)
    df["criterio_prioridade"] = df["criterio_prioridade"].fillna("")
    df["threshold_prioridade_uf"] = pd.to_numeric(df["threshold_prioridade_uf"], errors="coerce")
    df["renda_per_capita"] = _serie_numerica(df, "renda_per_capita")
    df["populacao_proxy"] = _serie_numerica(df, "populacao_proxy")
    if "renda_pct_nacional" in df.columns:
        df["renda_pct_nacional"] = pd.to_numeric(df["renda_pct_nacional"], errors="coerce")
    else:
        df["renda_pct_nacional"] = _calcular_percentil_nacional(df["renda_per_capita"])
    if "pop_pct_nacional" in df.columns:
        df["pop_pct_nacional"] = pd.to_numeric(df["pop_pct_nacional"], errors="coerce")
    else:
        df["pop_pct_nacional"] = _calcular_percentil_nacional(df["populacao_proxy"])
    df["hex_score_estrutural"] = _serie_numerica(df, "hex_score_estrutural")
    if "ajuste_executivo" in df.columns:
        df["ajuste_executivo"] = _serie_numerica(df, "ajuste_executivo")
    else:
        df["ajuste_executivo"] = calcular_ajuste_executivo(df["renda_pct_nacional"], df["pop_pct_nacional"])
    if "score_priorizacao" in df.columns:
        df["score_priorizacao"] = _serie_numerica(df, "score_priorizacao")
    else:
        df["score_priorizacao"] = (
            (df["hex_score_estrutural"] + df["ajuste_executivo"]).clip(lower=0, upper=100)
        ).round(2)
    if "fonte_renda" not in df.columns:
        df["fonte_renda"] = ""
    if "fonte_populacao" not in df.columns:
        df["fonte_populacao"] = ""
    if "nivel_geografico_ibge" not in df.columns:
        df["nivel_geografico_ibge"] = ""
    if "fallback_setor_censitario" not in df.columns:
        df["fallback_setor_censitario"] = True
    if "motivo_fallback_setor" not in df.columns:
        df["motivo_fallback_setor"] = ""
    if "fonte_geometria_ibge" not in df.columns:
        df["fonte_geometria_ibge"] = ""
    if "metodo_atribuicao_municipio" not in df.columns:
        df["metodo_atribuicao_municipio"] = ""
    if "data_referencia_ibge" not in df.columns:
        df["data_referencia_ibge"] = "censo_2022"

    sem_populacao = df.get("hex_sem_populacao", pd.Series(False, index=df.index)).fillna(False).astype(bool)
    score_validos = df["score_priorizacao"].notna() & ~sem_populacao
    df["score_percentil_nacional"] = pd.Series([float("nan")] * len(df), index=df.index, dtype="float64")
    if score_validos.any():
        df.loc[score_validos, "score_percentil_nacional"] = (
            df.loc[score_validos, "score_priorizacao"].rank(method="max", pct=True) * 100
        ).round(2)
    df["faixa_oportunidade"] = _definir_faixa_oportunidade(df["score_percentil_nacional"])
    # Hexágonos sem população (rios, áreas rurais sem dados) recebem status próprio
    df.loc[sem_populacao, "faixa_oportunidade"] = "inviavel"
    df["score_oficial"] = df["score_priorizacao"].round(2)
    df["score_oficial_nome"] = settings.M1_SCORE_OFICIAL
    df["osm_status"] = OSM_STATUS_NAO_APLICADO

    renda_p75 = float(df["renda_per_capita"].quantile(0.75))
    pop_p75 = float(df["populacao_proxy"].quantile(PERCENTIL_CORTE_SUPERIOR))
    pop_p25 = float(df["populacao_proxy"].quantile(PERCENTIL_CORTE_INFERIOR))
    score_p50 = float(df["score_percentil_nacional"].quantile(0.50))

    # IBGE fornece renda per capita; escalamos para estimar renda domiciliar usando RENDA_MIN
    # (renda domiciliar minima) como ancora, sem tocar o score estrutural.
    fator_renda_target = settings.RENDA_MIN / renda_p75 if renda_p75 > 0 else 1.0
    df["renda_target_proxy"] = (df["renda_per_capita"] * fator_renda_target).round(2)

    renda_alta = df["renda_pct_nacional"] >= PERCENTIL_CORTE_SUPERIOR
    pop_alta = df["pop_pct_nacional"] >= PERCENTIL_CORTE_SUPERIOR
    baixa_densidade = df["pop_pct_nacional"] < PERCENTIL_CORTE_INFERIOR
    score_baixo = df["score_percentil_nacional"] < score_p50
    renda_baixa = df["renda_target_proxy"] < settings.RENDA_MIN

    df["motivo_priorizacao"] = np.select(
        [renda_alta & pop_alta, renda_alta, pop_alta],
        ["combinado", "renda_alta", "alta_populacao"],
        default="sem_destaque",
    )
    df["motivo_alerta"] = _combinar_rotulos(
        df.index,
        [
            (renda_baixa, "renda_baixa"),
            (baixa_densidade, "baixa_densidade"),
            (score_baixo, "score_baixo"),
        ],
        default="sem_alerta",
    )
    df["flag_viavel"] = (~renda_baixa) & ~df["faixa_oportunidade"].isin(["descartado", "inviavel"]) & (~sem_populacao)

    df["observacao_estrategica"] = np.select(
        [
            sem_populacao,
            ~df["flag_viavel"],
            renda_alta & baixa_densidade,
            pop_alta & ~renda_alta,
            renda_alta & pop_alta,
        ],
        [
            "Area inviavel (agua/rural sem populacao)",
            "Regiao fora do target ideal",
            "Alta renda, baixa densidade",
            "Alta densidade, renda moderada",
            "Alta renda e alta densidade",
        ],
        default="Potencial estrutural equilibrado",
    )

    municipio_label = df["nome_municipio"].str.strip()
    df["municipio_label"] = municipio_label.where(
        municipio_label.ne(""),
        df["cod_municipio"].map(CAPITAL_POR_CODIGO).fillna(df["cod_municipio"]),
    )

    colunas_ordenacao = [
        "score_priorizacao",
        "hex_score_estrutural",
        "ajuste_executivo",
        "score_percentil_nacional",
        "renda_per_capita",
        "populacao_proxy",
        "uf",
        "cod_municipio",
        "hex_id",
    ]
    ascending = [False, False, False, False, False, False, True, True, True]
    df = df.sort_values(colunas_ordenacao, ascending=ascending, na_position="last").reset_index(drop=True)
    df["rank_brasil"] = np.arange(1, len(df) + 1, dtype=np.int64)
    df["rank_uf"] = df.groupby("uf", sort=False).cumcount().add(1).astype("int64")
    df["rank_cidade"] = df.groupby(["uf", "cod_municipio"], sort=False).cumcount().add(1).astype("int64")

    distribuicao_faixa = (
        df["faixa_oportunidade"]
        .value_counts(dropna=False)
        .reindex(FAIXAS_OPORTUNIDADE, fill_value=0)
        .rename_axis("faixa_oportunidade")
        .reset_index(name="hexagonos")
    )
    distribuicao_faixa["pct_hexagonos"] = (
        distribuicao_faixa["hexagonos"] / len(df) * 100
    ).round(2)

    metadados = {
        "renda_p75": round(renda_p75, 2),
        "pop_p75": round(pop_p75, 2),
        "pop_p25": round(pop_p25, 2),
        "score_percentil_p50": round(score_p50, 2),
        "fator_renda_target": round(fator_renda_target, 4),
        "distribuicao_faixa": distribuicao_faixa,
        "pct_viavel": round(float(df["flag_viavel"].mean() * 100), 2),
    }
    return df, metadados


def resumir_validacao_camada_oportunidade(
    df_oportunidades: pd.DataFrame,
    metadados: dict,
) -> dict:
    base_viavel = df_oportunidades[df_oportunidades["flag_viavel"]].copy()

    top20_brasil = (
        base_viavel.head(20)[
            [
                "rank_brasil",
                "uf",
                "municipio_label",
                "cod_municipio",
                "hex_id",
                "faixa_oportunidade",
                "motivo_priorizacao",
                "observacao_estrategica",
                "score_priorizacao",
                "ajuste_executivo",
                "hex_score_estrutural",
                "score_percentil_nacional",
                "renda_target_proxy",
            ]
        ]
        .copy()
    )
    top5_por_uf = (
        base_viavel.groupby("uf", sort=True, group_keys=False)
        .head(5)[
            [
                "uf",
                "rank_uf",
                "municipio_label",
                "cod_municipio",
                "hex_id",
                "faixa_oportunidade",
                "score_priorizacao",
                "hex_score_estrutural",
                "score_percentil_nacional",
                "flag_viavel",
            ]
        ]
        .copy()
    )
    resumo_uf = (
        df_oportunidades.groupby("uf", sort=True)
        .agg(
            hexagonos=("hex_id", "size"),
            viaveis=("flag_viavel", "sum"),
            score_max=("score_priorizacao", "max"),
            score_mediana=("score_priorizacao", "median"),
            prioridade_maxima=("faixa_oportunidade", lambda s: int((s == "prioridade_maxima").sum())),
        )
        .reset_index()
    )
    if not resumo_uf.empty:
        resumo_uf["pct_viavel"] = (resumo_uf["viaveis"] / resumo_uf["hexagonos"] * 100).round(2)
        resumo_uf["score_max"] = pd.to_numeric(resumo_uf["score_max"], errors="coerce").round(2)
        resumo_uf["score_mediana"] = pd.to_numeric(resumo_uf["score_mediana"], errors="coerce").round(2)

    top20_renda_alta_pct = round(
        float(top20_brasil["motivo_priorizacao"].isin(["renda_alta", "combinado"]).mean() * 100),
        2,
    ) if not top20_brasil.empty else 0.0

    linhas_capitais: list[dict[str, object]] = []
    for uf, meta in CAPITAIS_UF.items():
        capital = df_oportunidades[
            (df_oportunidades["uf"] == uf) & (df_oportunidades["cod_municipio"] == meta["cod_municipio"])
        ]
        if capital.empty:
            linhas_capitais.append(
                {
                    "uf": uf,
                    "capital": meta["capital"],
                    "cod_municipio": meta["cod_municipio"],
                    "melhor_rank_brasil": None,
                    "melhor_rank_uf": None,
                    "faixa_oportunidade": "nao_encontrada",
                    "flag_viavel": False,
                }
            )
            continue

        melhor = capital.nsmallest(1, "rank_brasil").iloc[0]
        linhas_capitais.append(
            {
                "uf": uf,
                "capital": meta["capital"],
                "cod_municipio": meta["cod_municipio"],
                "melhor_rank_brasil": int(melhor["rank_brasil"]),
                "melhor_rank_uf": int(melhor["rank_uf"]),
                "faixa_oportunidade": melhor["faixa_oportunidade"],
                "flag_viavel": bool(melhor["flag_viavel"]),
            }
        )
    sanity_capitais = pd.DataFrame(linhas_capitais).sort_values(["melhor_rank_brasil", "uf"], na_position="last")
    capitais_top10_uf = int((sanity_capitais["melhor_rank_uf"].fillna(999999) <= 10).sum())

    return {
        "distribuicao_faixa": metadados["distribuicao_faixa"],
        "pct_viavel": metadados["pct_viavel"],
        "fallback_setor_censitario_pct": round(
            float(df_oportunidades["fallback_setor_censitario"].fillna(True).mean() * 100),
            2,
        ) if "fallback_setor_censitario" in df_oportunidades.columns else 0.0,
        "top20_brasil": top20_brasil,
        "top5_por_uf": top5_por_uf,
        "resumo_uf": resumo_uf,
        "sanity_renda_topo_pct": top20_renda_alta_pct,
        "sanity_capitais": sanity_capitais,
        "capitais_top10_uf": capitais_top10_uf,
        "renda_p75": metadados["renda_p75"],
        "pop_p75": metadados["pop_p75"],
        "pop_p25": metadados["pop_p25"],
        "fator_renda_target": metadados["fator_renda_target"],
        "distribuicao_score_priorizacao": resumir_distribuicao_score(df_oportunidades["score_priorizacao"]),
    }


def gerar_relatorio_camada_oportunidade(
    validacao: dict,
    output_path: Path,
) -> None:
    linhas = [
        "# Camada de Oportunidade - Fase 1",
        "",
        "## Resumo executivo",
        "",
        f"- percentual de hexagonos viaveis: {validacao['pct_viavel']:.2f}%",
        f"- fallback explicito de setor censitario: {validacao['fallback_setor_censitario_pct']:.2f}%",
        f"- top 20 com renda alta ou combinada: {validacao['sanity_renda_topo_pct']:.2f}%",
        f"- capitais entre top 10 do proprio estado: {validacao['capitais_top10_uf']}/27",
        f"- renda p75 nacional usada na calibragem da proxy executiva: {validacao['renda_p75']:.2f}",
        f"- pop p75 nacional: {validacao['pop_p75']:.2f}",
        f"- pop p25 nacional: {validacao['pop_p25']:.2f}",
        f"- fator de proxy de renda domiciliar: {validacao['fator_renda_target']:.4f}",
        _texto_distribuicao_score("distribuicao do score de priorizacao", validacao["distribuicao_score_priorizacao"]),
        "",
        "## Distribuicao por faixa_oportunidade",
        "",
        _dataframe_para_markdown(validacao["distribuicao_faixa"]),
        "",
        "## Top 20 Brasil",
        "",
        _dataframe_para_markdown(validacao["top20_brasil"]),
        "",
        "## Top 5 por UF",
        "",
        _dataframe_para_markdown(validacao["top5_por_uf"]),
        "",
        "## Sanity check - Capitais",
        "",
        _dataframe_para_markdown(validacao["sanity_capitais"]),
        "",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def rodar_camada_oportunidade_nacional(
    input_estrutural_path: Path | str = "data/staging/brasil_estrutural.parquet",
    input_priorizados_path: Path | str = "data/staging/brasil_priorizados.parquet",
    output_base_path: Path | str = "data/staging/hexagonos_brasil_oportunidades.parquet",
    output_top_brasil_csv: Path | str = "data/outputs/top_hexagonos_brasil.csv",
    output_top_uf_csv: Path | str = "data/outputs/top_hexagonos_por_uf.csv",
    output_dashboard_path: Path | str = "data/staging/hexagonos_brasil_dashboard_base.parquet",
    report_path: Path | str = "data/reports/camada_oportunidade_fase1.md",
) -> tuple[pd.DataFrame, dict]:
    df_estrutural = pd.read_parquet(input_estrutural_path)
    df_priorizados = pd.read_parquet(
        input_priorizados_path,
        columns=[
            "hex_id",
            "uf",
            "cod_municipio",
            "criterio_prioridade",
            "threshold_prioridade_uf",
        ],
    )
    df_oportunidades, metadados = preparar_base_oportunidades(df_estrutural, df_priorizados)

    output_base_path = Path(output_base_path)
    output_base_path.parent.mkdir(parents=True, exist_ok=True)
    df_oportunidades.to_parquet(output_base_path, index=False)

    top_brasil = (
        df_oportunidades[df_oportunidades["flag_viavel"]]
        .head(1000)[
            [
                "rank_brasil",
                "uf",
                "municipio_label",
                "cod_municipio",
                "hex_id",
                "faixa_oportunidade",
                "motivo_priorizacao",
                "motivo_alerta",
                "flag_viavel",
                "observacao_estrategica",
                "score_priorizacao",
                "ajuste_executivo",
                "hex_score_estrutural",
                "score_percentil_nacional",
                "renda_target_proxy",
            ]
        ]
        .copy()
    )
    output_top_brasil_csv = Path(output_top_brasil_csv)
    output_top_brasil_csv.parent.mkdir(parents=True, exist_ok=True)
    top_brasil.to_csv(output_top_brasil_csv, sep=";", encoding="utf-8-sig", index=False)

    top_por_uf = (
        df_oportunidades
        .groupby("uf", sort=True, group_keys=False)
        .head(200)[
            [
                "uf",
                "rank_uf",
                "municipio_label",
                "cod_municipio",
                "hex_id",
                "faixa_oportunidade",
                "motivo_priorizacao",
                "motivo_alerta",
                "flag_viavel",
                "observacao_estrategica",
                "score_priorizacao",
                "ajuste_executivo",
                "hex_score_estrutural",
                "score_percentil_nacional",
                "renda_target_proxy",
            ]
        ]
        .copy()
    )
    output_top_uf_csv = Path(output_top_uf_csv)
    output_top_uf_csv.parent.mkdir(parents=True, exist_ok=True)
    top_por_uf.to_csv(output_top_uf_csv, sep=";", encoding="utf-8-sig", index=False)

    colunas_dashboard = [
        "hex_id",
        "lat",
        "lng",
        "uf",
        "regiao",
        "cod_municipio",
        "municipio_label",
        "renda_per_capita",
        "renda_target_proxy",
        "populacao_proxy",
        "renda_pct_nacional",
        "pop_pct_nacional",
        "hex_score_estrutural",
        "ajuste_executivo",
        "score_priorizacao",
        "score_oficial",
        "score_oficial_nome",
        "score_percentil_nacional",
        "faixa_oportunidade",
        "motivo_priorizacao",
        "motivo_alerta",
        "flag_viavel",
        "observacao_estrategica",
        "flag_prioridade",
        "criterio_prioridade",
        "threshold_prioridade_uf",
        "osm_status",
        "fonte_demografica",
        "fonte_renda",
        "fonte_populacao",
        "nivel_geografico_ibge",
        "fallback_setor_censitario",
        "motivo_fallback_setor",
        "fonte_geometria_ibge",
        "metodo_atribuicao_municipio",
        "data_referencia_ibge",
        "rank_brasil",
        "rank_uf",
        "rank_cidade",
    ]
    dashboard = df_oportunidades[colunas_dashboard].copy()
    output_dashboard_path = Path(output_dashboard_path)
    output_dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard.to_parquet(output_dashboard_path, index=False)

    validacao = resumir_validacao_camada_oportunidade(df_oportunidades, metadados)
    gerar_relatorio_camada_oportunidade(validacao, Path(report_path))

    log.info(
        "camada_oportunidade_nacional_concluida",
        total_hexagonos=len(df_oportunidades),
        pct_viavel=validacao["pct_viavel"],
        output_base=str(output_base_path),
        output_top_brasil=str(output_top_brasil_csv),
        output_top_uf=str(output_top_uf_csv),
        output_dashboard=str(output_dashboard_path),
        report=str(report_path),
    )
    return df_oportunidades, validacao


def selecionar_areas_prioritarias(
    df_estrutural: pd.DataFrame,
    top_pct_por_uf: float = 0.20,
    score_threshold: float | None = None,
) -> tuple[pd.DataFrame, dict]:
    if df_estrutural.empty:
        vazio = pd.DataFrame(columns=["hex_id", "lat", "lng", "uf", "regiao", "hex_score_estrutural", "flag_prioridade"])
        return vazio, {"total_priorizados": 0, "resumo_uf": pd.DataFrame()}

    df_estrutural = _garantir_nomes_municipio(df_estrutural.copy())
    df_estrutural["renda_per_capita"] = _serie_numerica(df_estrutural, "renda_per_capita")
    df_estrutural["populacao_proxy"] = _serie_numerica(df_estrutural, "populacao_proxy")
    df_estrutural["hex_score_estrutural"] = _serie_numerica(df_estrutural, "hex_score_estrutural")
    if "renda_pct_nacional" not in df_estrutural.columns:
        df_estrutural["renda_pct_nacional"] = _calcular_percentil_nacional(df_estrutural["renda_per_capita"])
    if "pop_pct_nacional" not in df_estrutural.columns:
        df_estrutural["pop_pct_nacional"] = _calcular_percentil_nacional(df_estrutural["populacao_proxy"])
    if "ajuste_executivo" not in df_estrutural.columns:
        df_estrutural["ajuste_executivo"] = calcular_ajuste_executivo(
            df_estrutural["renda_pct_nacional"],
            df_estrutural["pop_pct_nacional"],
        )
    if "score_priorizacao" not in df_estrutural.columns:
        df_estrutural["score_priorizacao"] = (
            (df_estrutural["hex_score_estrutural"] + df_estrutural["ajuste_executivo"]).clip(lower=0, upper=100)
        ).round(2)

    frames = []
    for _uf, grupo in df_estrutural.groupby("uf", sort=True):
        df_uf = grupo.sort_values(
            ["score_priorizacao", "hex_score_estrutural", "hex_id"],
            ascending=[False, False, True],
            na_position="last",
        ).copy()
        df_uf["flag_prioridade"] = False

        if score_threshold is not None:
            mascara = df_uf["score_priorizacao"] >= score_threshold
            threshold_uf = float(score_threshold)
            criterio = "threshold_global"
        else:
            n_prioritarios = math.floor(len(df_uf) * top_pct_por_uf)
            idx_prioritarios = df_uf.head(n_prioritarios).index
            mascara = df_uf.index.isin(idx_prioritarios)
            threshold_uf = (
                float(df_uf.loc[idx_prioritarios, "score_priorizacao"].min())
                if n_prioritarios > 0
                else float("nan")
            )
            criterio = f"top_{top_pct_por_uf:.0%}_uf"

        df_uf.loc[mascara, "flag_prioridade"] = True
        df_uf["criterio_prioridade"] = criterio
        df_uf["threshold_prioridade_uf"] = round(threshold_uf, 2)
        frames.append(df_uf)

    df_marcado = pd.concat(frames, ignore_index=True)
    colunas_saida = [
        "hex_id",
        "lat",
        "lng",
        "uf",
        "regiao",
        "cod_municipio",
        "nome_municipio",
        "renda_per_capita",
        "pop_total",
        "populacao_proxy",
        "renda_pct_nacional",
        "pop_pct_nacional",
        "fonte_demografica",
        "hex_score_estrutural",
        "ajuste_executivo",
        "score_priorizacao",
        "flag_prioridade",
        "criterio_prioridade",
        "threshold_prioridade_uf",
    ]
    df_priorizados = df_marcado[df_marcado["flag_prioridade"]].copy()
    df_priorizados = df_priorizados[colunas_saida].reset_index(drop=True)

    resumo_uf = (
        df_priorizados.groupby("uf", sort=True)
        .agg(
            hexagonos_priorizados=("hex_id", "size"),
            municipios_priorizados=("cod_municipio", "nunique"),
            score_min=("score_priorizacao", "min"),
            score_max=("score_priorizacao", "max"),
        )
        .reset_index()
    )
    hexagonos_total_uf = (
        df_estrutural.groupby("uf", sort=True)
        .size()
        .rename("hexagonos_total_uf")
        .reset_index()
    )
    resumo_uf = resumo_uf.merge(hexagonos_total_uf, on="uf", how="left")
    resumo_uf["pct_priorizados"] = (
        resumo_uf["hexagonos_priorizados"] / resumo_uf["hexagonos_total_uf"]
    ).round(6)
    if not resumo_uf.empty:
        resumo_uf["score_min"] = resumo_uf["score_min"].round(2)
        resumo_uf["score_max"] = resumo_uf["score_max"].round(2)

    validacao = {
        "criterio": f"score >= {score_threshold}" if score_threshold is not None else f"top {top_pct_por_uf:.0%} por UF",
        "total_priorizados": int(len(df_priorizados)),
        "pct_volume_priorizado": round(float(len(df_priorizados) / len(df_estrutural) * 100), 2),
        "resumo_uf": resumo_uf,
    }
    return df_priorizados, validacao


def enriquecer_concorrencia_priorizados(
    df_priorizados: pd.DataFrame,
    poi: POIEnricher,
    margem_bbox: float = 0.02,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df_priorizados.empty:
        return df_priorizados.copy(), pd.DataFrame()
    if "cod_municipio" not in df_priorizados.columns:
        raise ValueError("Dataset priorizado sem cod_municipio; a etapa OSM por cidade nao pode ser executada.")

    frames = []
    metricas = []

    grupos = df_priorizados.groupby(["uf", "cod_municipio", "nome_municipio"], sort=True, dropna=False)
    for idx, ((uf, cod_municipio, nome_municipio), grupo) in enumerate(grupos, start=1):
        t0 = time.time()
        contexto = f"cidade_{uf}_{cod_municipio or 'sem_cod'}_{idx}"
        lat_min = float(grupo["lat"].min() - margem_bbox)
        lat_max = float(grupo["lat"].max() + margem_bbox)
        lng_min = float(grupo["lng"].min() - margem_bbox)
        lng_max = float(grupo["lng"].max() + margem_bbox)

        grupo_saida = grupo.copy()
        try:
            academias = poi.buscar_academias_bbox_adaptativo(
                lat_min=lat_min,
                lat_max=lat_max,
                lng_min=lng_min,
                lng_max=lng_max,
                contexto=contexto,
            )
            contagens = poi.contar_academias_em_lote(
                grupo_saida[["lat", "lng"]],
                academias=academias,
            )
            grupo_saida["n_academias_osm"] = pd.Series(contagens, index=grupo_saida.index, dtype="Int64")
            grupo_saida["osm_status"] = "ok"
            grupo_saida["osm_error"] = ""
            academias_total = len(academias)
            status = "ok"
            erro = ""
        except Exception as exc:
            grupo_saida["n_academias_osm"] = pd.Series([pd.NA] * len(grupo_saida), index=grupo_saida.index, dtype="Int64")
            grupo_saida["osm_status"] = "erro"
            grupo_saida["osm_error"] = str(exc)
            academias_total = None
            status = "erro"
            erro = str(exc)
            log.error(
                "osm_priorizados_cidade_falhou",
                uf=uf,
                cod_municipio=cod_municipio,
                nome_municipio=nome_municipio,
                erro=erro,
            )

        frames.append(grupo_saida)
        metricas.append(
            {
                "uf": uf,
                "cod_municipio": cod_municipio,
                "nome_municipio": nome_municipio,
                "hexagonos": int(len(grupo)),
                "academias_osm_total": academias_total,
                "status": status,
                "erro": erro,
                "tempo_s": round(time.time() - t0, 2),
            }
        )

    df_osm = pd.concat(frames, ignore_index=True)
    df_osm["score_concorrencia"] = calcular_score_concorrencia(df_osm)
    return df_osm, pd.DataFrame(metricas)


def resumir_validacao_oportunidades(df_oportunidades: pd.DataFrame, metricas_osm: pd.DataFrame) -> dict:
    df = df_oportunidades.copy()
    df_validos = df[df["hex_score_final"].notna()].copy()
    top20 = (
        df_validos.sort_values("hex_score_final", ascending=False)
        .head(20)[
            [
                "uf",
                "nome_municipio",
                "hex_id",
                "lat",
                "lng",
                "hex_score_estrutural",
                "n_academias_osm",
                "score_concorrencia",
                "hex_score_final",
            ]
        ]
        .copy()
    )
    top5_uf = (
        df_validos.sort_values(["uf", "hex_score_final"], ascending=[True, False])
        .groupby("uf", group_keys=False)
        .head(5)[
            [
                "uf",
                "nome_municipio",
                "hex_id",
                "hex_score_estrutural",
                "n_academias_osm",
                "hex_score_final",
            ]
        ]
        .copy()
    )
    resumo_uf = (
        df.groupby("uf", sort=True)
        .agg(
            priorizados=("hex_id", "size"),
            com_osm=("score_concorrencia", lambda s: int(s.notna().sum())),
            com_erro_osm=("osm_status", lambda s: int((s == "erro").sum())),
            final_max=("hex_score_final", "max"),
        )
        .reset_index()
    )
    if not resumo_uf.empty:
        resumo_uf["final_max"] = pd.to_numeric(resumo_uf["final_max"], errors="coerce").round(2)

    return {
        "total_priorizados": int(len(df)),
        "total_com_osm": int(df["score_concorrencia"].notna().sum()),
        "total_com_erro_osm": int((df["osm_status"] == "erro").sum()) if "osm_status" in df.columns else 0,
        "cidades_processadas": int(metricas_osm["cod_municipio"].nunique()) if not metricas_osm.empty else 0,
        "cidades_com_erro": int((metricas_osm["status"] == "erro").sum()) if not metricas_osm.empty else 0,
        "distribuicao_score_final": resumir_distribuicao_score(df_validos["hex_score_final"]),
        "top20_brasil": top20,
        "top5_por_uf": top5_uf,
        "resumo_uf": resumo_uf,
    }


def resumir_validacao_nacional(df_total: pd.DataFrame) -> dict:
    score = df_total["hex_score"]
    preenchimento_pop = (df_total["pop_total"] > 0).mean() * 100

    anomalias = []
    rows_uf = []
    for uf, grupo in df_total.groupby("uf", sort=True):
        score_std = float(grupo["hex_score"].std(ddof=0)) if len(grupo) else 0.0
        issues = []
        if grupo["hex_score"].nunique(dropna=False) <= 1 or score_std == 0.0:
            issues.append("score_constante")
        if int(grupo["n_academias_osm"].sum()) == 0:
            issues.append("concorrencia_zerada")
        if issues:
            anomalias.append({"uf": uf, "anomalias": ", ".join(issues)})
        rows_uf.append(
            {
                "uf": uf,
                "hexagonos": len(grupo),
                "score_min": round(float(grupo["hex_score"].min()), 2),
                "score_max": round(float(grupo["hex_score"].max()), 2),
                "score_std": round(score_std, 2),
                "academias_osm_total": int(grupo["n_academias_osm"].sum()),
                "anomalias": ", ".join(issues) if issues else "",
            }
        )

    top10 = (
        df_total.sort_values("hex_score", ascending=False)
        .head(10)[["uf", "lat", "lng", "renda_per_capita", "hex_score"]]
        .copy()
    )
    top5_uf = (
        df_total.sort_values(["uf", "hex_score"], ascending=[True, False])
        .groupby("uf", group_keys=False)
        .head(5)[["uf", "lat", "lng", "renda_per_capita", "hex_score"]]
        .copy()
    )

    return {
        "total_hexagonos": int(len(df_total)),
        "preenchimento_renda_pct": round(float((df_total["renda_per_capita"] > 0).mean() * 100), 2),
        "preenchimento_pop_pct": round(float(preenchimento_pop), 2),
        "score_min": round(float(score.min()), 2),
        "score_max": round(float(score.max()), 2),
        "score_media": round(float(score.mean()), 2),
        "score_mediana": round(float(score.median()), 2),
        "score_std": round(float(score.std(ddof=0)), 2),
        "anomalias_uf": anomalias,
        "resumo_uf": pd.DataFrame(rows_uf),
        "top10_brasil": top10,
        "top5_por_uf": top5_uf,
    }


def _formatar_valor_relatorio(valor) -> str:
    if isinstance(valor, float):
        return f"{valor:.5f}" if abs(valor) < 180 else f"{valor:.2f}"
    return str(valor)


def _dataframe_para_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "- Nenhum registro."

    linhas = [
        "| " + " | ".join(df.columns) + " |",
        "| " + " | ".join(["---"] * len(df.columns)) + " |",
    ]
    for row in df.itertuples(index=False, name=None):
        linhas.append("| " + " | ".join(_formatar_valor_relatorio(v) for v in row) + " |")
    return "\n".join(linhas)


def _texto_distribuicao_score(titulo: str, distribuicao: dict) -> str:
    if not distribuicao or distribuicao.get("count", 0) == 0:
        return f"- {titulo}: sem dados."
    return (
        f"- {titulo}: count={distribuicao['count']} | min={distribuicao['min']:.2f} | "
        f"max={distribuicao['max']:.2f} | media={distribuicao['media']:.2f} | "
        f"mediana={distribuicao['mediana']:.2f} | std={distribuicao['std']:.2f} | "
        f"p90={distribuicao['p90']:.2f} | p95={distribuicao['p95']:.2f}"
    )


def gerar_relatorio_mvp_fase1_brasil(
    validacao_estrutural: dict,
    validacao_priorizacao: dict,
    validacao_oportunidades: dict,
    metricas_osm: pd.DataFrame,
    tempos: dict,
    output_path: Path,
) -> None:
    reducao_pct = round(100 - validacao_priorizacao.get("pct_volume_priorizado", 0.0), 2)
    pipeline_estavel = validacao_oportunidades.get("cidades_com_erro", 0) == 0
    resposta_estabilidade = "Sim" if pipeline_estavel else "Parcial"

    linhas = [
        "# MVP Fase 1 Brasil",
        "",
        "## Respostas objetivas",
        "",
        f"- tempo total por etapa: estrutural={tempos.get('estrutural_s', 0):.1f}s | priorizacao={tempos.get('priorizacao_s', 0):.1f}s | osm_priorizados={tempos.get('osm_s', 0):.1f}s | score_final={tempos.get('score_final_s', 0):.1f}s | total={tempos.get('total_s', 0):.1f}s",
        f"- reducao de volume vs abordagem anterior: {reducao_pct:.2f}% menos hexagonos expostos ao OSM ({validacao_estrutural.get('total_hexagonos', 0)} -> {validacao_priorizacao.get('total_priorizados', 0)})",
        _texto_distribuicao_score("distribuicao do score estrutural", validacao_estrutural.get("distribuicao_score_estrutural", {})),
        _texto_distribuicao_score("distribuicao do score final", validacao_oportunidades.get("distribuicao_score_final", {})),
        f"- pipeline agora e estavel e executavel? {resposta_estabilidade}",
        "",
        "## Etapa 1 - Estrutural nacional",
        "",
        f"- total de hexagonos: {validacao_estrutural.get('total_hexagonos', 0)}",
        f"- preenchimento renda: {validacao_estrutural.get('preenchimento_renda_pct', 0):.2f}%",
        f"- preenchimento populacao proxy: {validacao_estrutural.get('preenchimento_pop_pct', 0):.2f}%",
        "",
        _dataframe_para_markdown(validacao_estrutural.get("resumo_uf", pd.DataFrame())),
        "",
        "## Etapa 2 - Priorizacao",
        "",
        f"- criterio de corte: {validacao_priorizacao.get('criterio', '')}",
        f"- hexagonos selecionados: {validacao_priorizacao.get('total_priorizados', 0)}",
        f"- volume priorizado: {validacao_priorizacao.get('pct_volume_priorizado', 0):.2f}% da base estrutural",
        "",
        _dataframe_para_markdown(validacao_priorizacao.get("resumo_uf", pd.DataFrame())),
        "",
        "## Etapa 3 e 4 - OSM incremental e score final",
        "",
        f"- cidades processadas no OSM: {validacao_oportunidades.get('cidades_processadas', 0)}",
        f"- cidades com erro explicito no OSM: {validacao_oportunidades.get('cidades_com_erro', 0)}",
        f"- hexagonos com score final calculado: {validacao_oportunidades.get('total_com_osm', 0)}",
        "",
    ]

    if not metricas_osm.empty:
        linhas.extend(
            [
                _dataframe_para_markdown(metricas_osm),
                "",
            ]
        )
    else:
        linhas.extend(["- Nenhuma cidade priorizada processada no OSM.", ""])

    linhas.extend(
        [
            "## Top 20 estrutural",
            "",
            _dataframe_para_markdown(validacao_estrutural.get("top20_brasil", pd.DataFrame())),
            "",
            "## Top 20 Brasil",
            "",
            _dataframe_para_markdown(validacao_oportunidades.get("top20_brasil", pd.DataFrame())),
            "",
            "## Top 5 por UF",
            "",
            _dataframe_para_markdown(validacao_oportunidades.get("top5_por_uf", pd.DataFrame())),
            "",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def gerar_relatorio_enriquecimento_brasil(
    df_total: pd.DataFrame,
    validacao: dict,
    output_path: Path,
    sucesso_execucao: bool,
) -> None:
    score_consistente = validacao["score_std"] > 0 and not any(
        "score_constante" in item["anomalias"] for item in validacao["anomalias_uf"]
    )
    pronto_ranking = sucesso_execucao and not validacao["anomalias_uf"]

    linhas = [
        "# Enriquecimento H3 Brasil",
        "",
        "## Respostas objetivas",
        "",
        f"- pipeline nacional executou sem erros? {'Sim' if sucesso_execucao else 'Nao'}",
        f"- score esta variando de forma consistente? {'Sim' if score_consistente else 'Nao'}",
        f"- existem anomalias por UF? {'Sim' if validacao['anomalias_uf'] else 'Nao'}",
        f"- dados estao prontos para criacao de ranking nacional? {'Sim' if pronto_ranking else 'Nao'}",
        "",
        "## Validacao geral",
        "",
        f"- total de hexagonos processados: {validacao['total_hexagonos']}",
        f"- preenchimento de renda: {validacao['preenchimento_renda_pct']:.2f}%",
        f"- preenchimento de populacao proxy: {validacao['preenchimento_pop_pct']:.2f}%",
        f"- distribuicao global do hex_score: min={validacao['score_min']:.2f} | max={validacao['score_max']:.2f} | media={validacao['score_media']:.2f} | mediana={validacao['score_mediana']:.2f} | std={validacao['score_std']:.2f}",
        "",
        "## Resumo por UF",
        "",
        _dataframe_para_markdown(validacao["resumo_uf"]),
        "",
        "## Anomalias por UF",
        "",
    ]

    if validacao["anomalias_uf"]:
        linhas.append(_dataframe_para_markdown(pd.DataFrame(validacao["anomalias_uf"])))
    else:
        linhas.append("- Nenhuma anomalia bloqueante identificada.")

    linhas.extend(
        [
            "",
            "## Top 10 Brasil",
            "",
            _dataframe_para_markdown(validacao["top10_brasil"]),
            "",
            "## Top 5 por UF",
            "",
            _dataframe_para_markdown(validacao["top5_por_uf"]),
            "",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def rodar_pipeline_estrutural_brasil(
    input_root: Path | str = "data/staging/brasil",
    output_path: Path | str = "data/staging/brasil_estrutural.parquet",
    tmp_root: Path | str = "data/staging/brasil_estrutural_tmp",
    refresh_demografia: bool = False,
    refresh_malha: bool = False,
) -> tuple[pd.DataFrame, dict]:
    input_root = Path(input_root)
    output_path = Path(output_path)
    tmp_root = Path(tmp_root)

    censo = IBGECenso()
    particoes = _listar_particoes_brasil(input_root)
    paths_tmp = []

    for idx, (uf, path) in enumerate(particoes, start=1):
        t0 = time.time()
        df_hex_uf = pd.read_parquet(path)
        df_estrutural = enriquecer_hexagonos_uf_estrutural(
            df_hex_uf=df_hex_uf,
            uf=uf,
            censo=censo,
            refresh_demografia=refresh_demografia and idx == 1,
            refresh_malha=refresh_malha,
        )
        path_tmp = _salvar_particao_uf(df_estrutural, tmp_root, uf)
        paths_tmp.append(path_tmp)
        log.info("pipeline_estrutural_uf_ok", uf=uf, tempo_s=round(time.time() - t0, 1), path_tmp=str(path_tmp))

    df_total = pd.concat([pd.read_parquet(path) for path in paths_tmp], ignore_index=True)
    df_total = calcular_hex_score_estrutural(df_total)
    df_total = _garantir_nomes_municipio(df_total)
    df_total = df_total.sort_values("hex_score_estrutural", ascending=False).reset_index(drop=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_total.to_parquet(output_path, index=False)
    validacao = resumir_validacao_estrutural(df_total)
    return df_total, validacao


def rodar_pipeline_fase1_brasil(
    input_root: Path | str = "data/staging/brasil",
    output_estrutural_path: Path | str = "data/staging/brasil_estrutural.parquet",
    output_priorizados_path: Path | str = "data/staging/brasil_priorizados.parquet",
    output_oportunidades_path: Path | str = "data/staging/hexagonos_brasil_oportunidades.parquet",
    report_path: Path | str = "data/reports/camada_oportunidade_fase1.md",
    tmp_root: Path | str = "data/staging/brasil_estrutural_tmp",
    refresh_demografia: bool = False,
    refresh_malha: bool = False,
    top_pct_por_uf: float = settings.M1_PRIORIZACAO_TOP_PCT_POR_UF,
    score_threshold: float | None = None,
) -> tuple[pd.DataFrame, dict]:
    started_at = time.time()
    tempos = {}

    t0 = time.time()
    df_estrutural, validacao_estrutural = rodar_pipeline_estrutural_brasil(
        input_root=input_root,
        output_path=output_estrutural_path,
        tmp_root=tmp_root,
        refresh_demografia=refresh_demografia,
        refresh_malha=refresh_malha,
    )
    tempos["estrutural_s"] = round(time.time() - t0, 2)

    t0 = time.time()
    df_priorizados, validacao_priorizacao = selecionar_areas_prioritarias(
        df_estrutural=df_estrutural,
        top_pct_por_uf=top_pct_por_uf,
        score_threshold=score_threshold,
    )
    output_priorizados_path = Path(output_priorizados_path)
    output_priorizados_path.parent.mkdir(parents=True, exist_ok=True)
    df_priorizados.to_parquet(output_priorizados_path, index=False)
    tempos["priorizacao_s"] = round(time.time() - t0, 2)

    t0 = time.time()
    df_oportunidades, validacao_oportunidades = rodar_camada_oportunidade_nacional(
        input_estrutural_path=output_estrutural_path,
        input_priorizados_path=output_priorizados_path,
        output_base_path=output_oportunidades_path,
        report_path=report_path,
    )
    tempos["camada_oportunidade_s"] = round(time.time() - t0, 2)

    t0 = time.time()
    try:
        from motor_expansao.pipelines.m1.fase1_bi_exports import generate_fase1_bi_artifacts
    except ModuleNotFoundError:
        # fallback de import quando rodando fora do pacote (estrutura flat)
        from fase1_bi_exports import (  # type: ignore[no-redef,attr-defined]
            generate_fase1_bi_artifacts,
        )

    artefatos_bi = generate_fase1_bi_artifacts(source_path=output_oportunidades_path)
    tempos["bi_exports_s"] = round(time.time() - t0, 2)
    tempos["total_s"] = round(time.time() - started_at, 2)
    log.info(
        "pipeline_fase1_brasil_concluido",
        total_estrutural=len(df_estrutural),
        total_priorizados=len(df_priorizados),
        total_oportunidades=len(df_oportunidades),
        output_estrutural=str(output_estrutural_path),
        output_priorizados=str(output_priorizados_path),
        output_oportunidades=str(output_oportunidades_path),
        report=str(report_path),
    )
    return df_oportunidades, {
        "estrutural": validacao_estrutural,
        "priorizacao": validacao_priorizacao,
        "oportunidades": validacao_oportunidades,
        "bi_outputs": {chave: len(valor) if isinstance(valor, pd.DataFrame) else valor for chave, valor in artefatos_bi.items()},
        "tempos": tempos,
    }


def rodar_pipeline_brasil(
    input_root: Path | str = "data/staging/brasil",
    output_path: Path | str = "data/staging/hexagonos_brasil_oportunidades.parquet",
    output_part_root: Path | str = "data/staging/brasil_enriquecido",
    report_path: Path | str = "data/reports/camada_oportunidade_fase1.md",
    tmp_root: Path | str = "data/staging/brasil_estrutural_tmp",
    refresh_demografia: bool = False,
    refresh_malha: bool = False,
    top_pct_por_uf: float = settings.M1_PRIORIZACAO_TOP_PCT_POR_UF,
    score_threshold: float | None = None,
) -> tuple[pd.DataFrame, dict]:
    del output_part_root  # legado: mantido apenas para compatibilidade de assinatura
    return rodar_pipeline_fase1_brasil(
        input_root=input_root,
        output_estrutural_path="data/staging/brasil_estrutural.parquet",
        output_priorizados_path="data/staging/brasil_priorizados.parquet",
        output_oportunidades_path=output_path,
        report_path=report_path,
        tmp_root=tmp_root,
        refresh_demografia=refresh_demografia,
        refresh_malha=refresh_malha,
        top_pct_por_uf=top_pct_por_uf,
        score_threshold=score_threshold,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cidade",  help="Cidade única (modo single)")
    parser.add_argument("--uf",      help="UF (modo single)")
    parser.add_argument("--raio",    type=float, default=15.0)
    parser.add_argument("--batch",   action="store_true", help="Modo batch multi-cidade")
    parser.add_argument("--brasil",  action="store_true", help="Modo nacional por UF")
    parser.add_argument("--prioridade-top-pct", type=float, default=settings.M1_PRIORIZACAO_TOP_PCT_POR_UF)
    parser.add_argument("--score-threshold", type=float)
    args = parser.parse_args()

    if args.brasil:
        rodar_pipeline_brasil(
            top_pct_por_uf=args.prioridade_top_pct,
            score_threshold=args.score_threshold,
        )
    elif args.batch:
        CIDADES_BATCH = [
            ("Goiania",          "GO"),
            ("Campinas",         "SP"),
            ("Belo Horizonte",   "MG"),
            ("Curitiba",         "PR"),
        ]
        rodar_pipeline_batch(CIDADES_BATCH, raio_km=args.raio)
    elif args.cidade and args.uf:
        rodar_pipeline_hex(args.cidade, args.uf, args.raio)
    else:
        parser.error("Informe --cidade e --uf para modo single, ou --batch/--brasil.")


if __name__ == "__main__":
    main()
