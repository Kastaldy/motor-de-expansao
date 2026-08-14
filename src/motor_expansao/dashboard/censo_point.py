from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
import pandas as pd
from pyproj import CRS, Transformer
from shapely import from_wkb, make_valid
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

from motor_expansao.dashboard.constants import (
    DATA_REFERENCIA_RENDA,
    FATOR_TEMPORAL_RENDA,
    uplift_composicao_por_setor,
    uplift_extrapolado,
    uplift_renda_domiciliar,
)

CRS_ORIGEM_CENSO = "EPSG:4674"
# DEC-021 (2026-07-29, AUTORIZADA por Felipe): o raio do Relatorio Pontual Censitario passa de
# 1,5 km para 1,0 km — analise E rotulos, nao so o enquadramento do mapa.
#
# Viavel sem reprocessar nada: a intersecao setor x circulo e calculada EM RUNTIME a partir deste
# valor (`buffer(raio_km * 1000)` + `intersection` setor a setor, mais abaixo neste arquivo), e o
# artefato M1 geo e RADIUS-AGNOSTIC — nenhuma das 38 colunas de `COLUNAS_ARTEFATO` depende de
# raio. Os 468.099 setores / 1,17 GB ficam intocados.
#
# O rotulo do metodo acompanha o valor: mante-lo como `..._1p5km` faria o proprio artefato mentir
# sobre si mesmo, e ele vaza para o JSON da API, para o schema publico e para o texto do PDF.
# E' MUDANCA DE CONTRATO: quem comparava a string literal precisa atualizar (ver DEC-021).
METODO_RELATORIO_PONTUAL_CENSITARIO = "setor_censitario_intersecao_area_1km"
RAIO_CENSITARIO_DEFAULT_KM = 1.0
# BLK-RELPON-07: renda media domiciliar do bairro/distrito ponderada por domicilios
# (Metodo A, D3.5), com exclusao simetrica de setor com renda ou domicilios nulos/<=0.
METODO_RENDA_PERFIL_BAIRRO = "renda_responsavel_media_ponderada_por_domicilios"


def _haversine_km(
    lat1: float,
    lat2: np.ndarray | float,
    lng1: float,
    lng2: np.ndarray | float,
) -> np.ndarray:
    radius_km = 6371.0
    lat1_r = np.radians(lat1)
    lat2_r = np.radians(lat2)
    dlat = lat2_r - lat1_r
    dlng = np.radians(lng2) - np.radians(lng1)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlng / 2) ** 2
    return radius_km * 2 * np.arctan2(np.sqrt(a), np.sqrt(np.maximum(0.0, 1.0 - a)))


def _local_metric_crs(lat: float, lng: float) -> CRS:
    return CRS.from_proj4(
        f"+proj=aeqd +lat_0={lat} +lon_0={lng} +datum=WGS84 +units=m +no_defs"
    )


def _transformer(source: CRS | str, target: CRS | str) -> Transformer:
    return Transformer.from_crs(source, target, always_xy=True)


def _project_geometry(geom: BaseGeometry, transformer: Transformer) -> BaseGeometry:
    return transform(transformer.transform, geom)


def _decode_geometry(value: object) -> BaseGeometry | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, BaseGeometry):
        geom = value
    else:
        geom = from_wkb(value)
    if geom is None or geom.is_empty:
        return None
    if not geom.is_valid:
        geom = make_valid(geom)
    if geom is None or geom.is_empty:
        return None
    return geom


def _numeric(df: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")


def _weighted_average(values: pd.Series, weights: pd.Series) -> float | None:
    valid = values.notna() & weights.notna() & weights.gt(0)
    if valid.any():
        return round(float(np.average(values[valid], weights=weights[valid])), 2)
    valid_values = values.notna()
    if valid_values.any():
        return round(float(values[valid_values].mean()), 2)
    return None


def _empty_setores_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "cod_setor",
            "uf",
            "cod_municipio",
            "nome_municipio",
            "area_setor_m2",
            "area_intersecao_m2",
            "peso_area_setor",
            "pop_total_setor_2022",
            "pop_estimada_intersecao",
            "renda_per_capita_setor_2022_calibrada",
            # Per capita DOMICILIAR por setor — a MESMA grandeza dos agregados do raio e
            # do setor do ponto. Sem ela no frame, o consumidor so tem a CALIBRADA para
            # montar min/mediana/max, e a distribuicao sai numa escala diferente da dos
            # campos irmaos do mesmo payload.
            "renda_per_capita_domiciliar_setor",
            "densidade_pop_setor_hab_km2",
            "score_setor_2022_calibrado",
            "flag_renda_disponivel",
            "flag_geometria_valida",
            "qualidade_join_uf",
        ]
    )


def _points_in_radius(
    lat: float,
    lng: float,
    points_df: pd.DataFrame | None,
    raio_km: float,
) -> pd.DataFrame:
    if points_df is None or points_df.empty or "lat" not in points_df.columns or "lng" not in points_df.columns:
        return pd.DataFrame()
    valid = points_df[["lat", "lng"]].apply(pd.to_numeric, errors="coerce").notna().all(axis=1)
    if not valid.any():
        return pd.DataFrame(columns=list(points_df.columns) + ["dist_km"])
    pts = points_df.loc[valid].copy()
    dists = _haversine_km(
        lat,
        pts["lat"].to_numpy(dtype=float),
        lng,
        pts["lng"].to_numpy(dtype=float),
    )
    pts["dist_km"] = np.round(dists, 4)
    return pts.loc[pts["dist_km"] <= raio_km].sort_values("dist_km", kind="stable").reset_index(drop=True)


def _bbox_prefilter(
    setores_df: pd.DataFrame,
    circle_wgs84: BaseGeometry,
) -> pd.DataFrame:
    bbox_cols = {"bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy"}
    if not bbox_cols.issubset(set(setores_df.columns)):
        return setores_df
    minx, miny, maxx, maxy = circle_wgs84.bounds
    mask = (
        _numeric(setores_df, "bbox_maxx").ge(minx)
        & _numeric(setores_df, "bbox_minx").le(maxx)
        & _numeric(setores_df, "bbox_maxy").ge(miny)
        & _numeric(setores_df, "bbox_miny").le(maxy)
    )
    return setores_df.loc[mask]


def _available_columns(preferred: Iterable[str], df: pd.DataFrame) -> list[str]:
    return [column for column in preferred if column in df.columns]


def analisar_ponto_censitario_setores(
    lat: float,
    lng: float,
    setores_df: pd.DataFrame,
    raio_km: float = RAIO_CENSITARIO_DEFAULT_KM,
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
) -> dict:
    """Analisa um ponto por intersecao real entre setores censitarios e circulo.

    A entrada esperada e uma base setorial ja recortada/carregada com `geometry_wkb`
    em EPSG:4674. A funcao e pura: nao muta os DataFrames recebidos e nao recalcula
    nenhum artefato oficial do M1.

    BLK-RELPON-05: alem dos agregados ponderados do raio de 1.0 km, o `result` expoe
    5 campos com o valor BRUTO do setor que CONTEM o ponto pesquisado (`covers()` no
    CRS metrico local, tie-break por maior `peso_area_setor`): `cod_setor_ponto`,
    `renda_per_capita_setor_ponto`, `densidade_pop_setor_ponto`,
    `score_setor_2022_calibrado_ponto` e `flag_setor_ponto_encontrado`. Reaproveita a
    geometria ja decodificada/projetada no laco de intersecao (sem novo `_decode_geometry`
    nem novo transformer). Quando o ponto cai fora de qualquer setor da malha (agua/orla,
    setor com geometria invalida, etc.), os 5 campos ficam `None`/`False`, sem excecao.

    BLK-RELPON-06 (D1, reverte o D3 do BLK-RELPON-05 quanto a fonte da FAIXA do mapa):
    `densidade_pop_raio_valida_hab_km2` = `pop_total_raio / (area_intersecao_total_m2 /
    1e6)`, ou seja, populacao do raio dividida pela area de espaco VALIDO (soma das areas
    de intersecao dos setores IBGE com o circulo -- o IBGE nao cobre agua/vazio). Difere de
    `densidade_pop_raio_hab_km2`, que divide por `pi*raio_km**2` FIXO (inclui agua/vazio
    dentro do circulo, subestimando a densidade em pontos com rio/mar no raio). Guarda de
    divisao por zero: fica `None` ("n/d" no display) quando nao ha setores intersectados
    (o bloco inteiro e pulado) ou quando `area_intersecao_total_m2` e 0/None. Os 5 campos
    `*_setor_ponto` acima PERMANECEM no `result` para CSV/auditoria; so deixam de alimentar
    a faixa superior do mapa (`censo_map.py`).

    BLK-RELPON-07: alem dos campos acima, `result` expoe 5 campos de IDENTIFICACAO do
    bairro/distrito que CONTEM o ponto: `cod_bairro_ponto`, `nome_bairro_ponto`,
    `nome_distrito_ponto`, `unidade_ponto_tipo` (`"bairro"`/`"distrito"`/`None`, identificador
    cru, NAO acentuar) e `unidade_ponto_rotulo` (nome de exibicao ja com o fallback bairro ->
    distrito resolvido). Sao leitura direta das colunas `cod_bairro`/`nome_bairro`/
    `nome_distrito` do MESMO setor que contem o ponto (reaproveita o lookup do
    BLK-RELPON-05, sem nova geometria/CRS). A AGREGACAO dos 4 blocos (populacao, densidade,
    domicilios, renda media) sobre TODOS os setores dessa unidade e responsabilidade do
    helper `agregar_perfil_bairro_distrito` (abaixo), nao desta funcao. Ponto fora de
    qualquer setor da malha -> os 5 campos ficam `None`, sem excecao.
    """
    area_km2 = math.pi * raio_km**2
    concorrentes_raio = _points_in_radius(lat, lng, competitors_df, raio_km)
    ultra_raio = _points_in_radius(lat, lng, ultra_df, raio_km)
    result: dict = {
        "lat": lat,
        "lng": lng,
        "raio_km": raio_km,
        "area_km2": round(area_km2, 2),
        "metodo": METODO_RELATORIO_PONTUAL_CENSITARIO,
        "n_setores": 0,
        "area_intersecao_total_m2": 0.0,
        "pop_total_raio": None,
        "domicilios_total_raio": None,
        "renda_per_capita_media_raio": None,
        "metodo_renda_raio": "ausente",
        # Renda media domiciliar no raio (fase seguinte): renda do responsavel x uplift x fator
        # temporal, ponderada por DOMICILIOS. ADITIVO — nao substitui a renda per capita acima.
        "renda_media_domiciliar_raio": None,
        "renda_domiciliar_total_raio": None,
        "metodo_renda_domiciliar_raio": "ausente",
        "uf_renda_uplift": None,
        "cod_municipio_renda_uplift": None,
        "fator_uplift_renda_domiciliar": None,
        "fator_uplift_composicao": None,
        "fator_uplift_composicao_municipio": None,
        # Fracao dos DOMICILIOS do raio cujo uplift foi extrapolado para fora da faixa de
        # calibracao do municipio (o pipeline marca como "leitura cautelosa"). Ate 2026-08-13
        # essa flag existia no artefato e morria na carga — 20,3% dos setores do pais chegavam
        # ao relatorio sem ressalva nenhuma. Campo ADITIVO: nao muda nenhum numero de renda.
        "fracao_uplift_extrapolado_raio": None,
        "fator_temporal_renda": FATOR_TEMPORAL_RENDA,
        "data_referencia_renda": DATA_REFERENCIA_RENDA,
        "densidade_pop_raio_hab_km2": None,
        # BLK-RELPON-06 (D1): densidade sobre area de espaco VALIDO (exclui agua/vazio) --
        # ver docstring abaixo. Difere de `densidade_pop_raio_hab_km2` (divide por pi*raio^2
        # fixo, incluindo agua/vazio dentro do circulo).
        "densidade_pop_raio_valida_hab_km2": None,
        "score_setor_medio": None,
        "score_setor_max": None,
        "n_concorrentes": len(concorrentes_raio),
        "n_ultra": len(ultra_raio),
        "concorrentes_raio": concorrentes_raio,
        "ultra_raio": ultra_raio,
        "setores_intersectados": _empty_setores_frame(),
        # BLK-RELPON-05: valor BRUTO do setor que CONTEM o ponto (nao o agregado do raio).
        "cod_setor_ponto": None,
        "renda_per_capita_setor_ponto": None,
        "densidade_pop_setor_ponto": None,
        "score_setor_2022_calibrado_ponto": None,
        "flag_setor_ponto_encontrado": False,
        # BLK-RELPON-07: identificacao do bairro/distrito que CONTEM o ponto.
        "cod_bairro_ponto": None,
        "nome_bairro_ponto": None,
        "nome_distrito_ponto": None,
        "unidade_ponto_tipo": None,       # "bairro" | "distrito" | None (identificador cru, NAO acentuar)
        "unidade_ponto_rotulo": None,     # nome de exibicao ja com fallback resolvido
    }

    if setores_df is None or setores_df.empty:
        return result
    if "geometry_wkb" not in setores_df.columns and "geometry" not in setores_df.columns:
        return result

    metric_crs = _local_metric_crs(lat, lng)
    to_metric = _transformer(CRS_ORIGEM_CENSO, metric_crs)
    to_wgs84 = _transformer(metric_crs, CRS_ORIGEM_CENSO)
    center_metric = Point(0, 0)
    circle_metric = center_metric.buffer(raio_km * 1000.0, quad_segs=64)
    circle_wgs84 = _project_geometry(circle_metric, to_wgs84)

    candidates = _bbox_prefilter(setores_df, circle_wgs84)
    if "flag_geometria_valida" in candidates.columns:
        candidates = candidates.loc[candidates["flag_geometria_valida"].fillna(False).astype(bool)]
    if candidates.empty:
        return result

    geometry_col = "geometry_wkb" if "geometry_wkb" in candidates.columns else "geometry"
    records: list[dict[str, object]] = []
    for _idx, row in candidates.iterrows():
        geom_wgs84 = _decode_geometry(row[geometry_col])
        if geom_wgs84 is None:
            continue
        geom_metric = _project_geometry(geom_wgs84, to_metric)
        if geom_metric.is_empty:
            continue
        intersection = geom_metric.intersection(circle_metric)
        if intersection.is_empty:
            continue
        area_intersecao_m2 = float(intersection.area)
        if area_intersecao_m2 <= 0:
            continue
        # O peso tem de comparar duas areas na MESMA projecao. O numerador (`intersection.area`)
        # sai da AEQD local, centrada no ponto pesquisado e praticamente exata num raio de 1 km.
        # Ate 2026-08-13 o denominador vinha de `area_setor_m2` do artefato, calculada em
        # EPSG:5880 (Policonica do Brasil), que NAO e equivalente em area: a distorcao cresce com
        # a distancia ao meridiano central de -54. Medido, a razao AEQD/artefato e sistematica —
        # Recife 0,9481, Fortaleza 0,9648, Sao Paulo 0,9931, Porto Alegre 0,9991 —, entao um setor
        # INTEIRAMENTE dentro do raio recebia peso 0,948 no Recife em vez de 1,0, e o `min(1, ...)`
        # nao corrigia nada porque a razao e sistematicamente menor que 1. Isso subestimava
        # populacao e domicilios do raio em ate 5,2%, direto nos Big Numbers de meta ABSOLUTA.
        area_setor_metrica = float(geom_metric.area)
        peso_area = max(0.0, min(1.0, area_intersecao_m2 / area_setor_metrica))
        # `area_setor_m2` do artefato segue valendo para EXIBICAO (e a area oficial do setor,
        # comparavel entre setores do pais); ela so nao serve de denominador do peso local.
        area_setor_m2 = pd.to_numeric(row.get("area_setor_m2", np.nan), errors="coerce")
        if pd.isna(area_setor_m2) or float(area_setor_m2) <= 0:
            area_setor_m2 = area_setor_metrica
        record = row.to_dict()
        record["area_setor_m2"] = float(area_setor_m2)
        record["area_intersecao_m2"] = area_intersecao_m2
        record["peso_area_setor"] = peso_area
        # BLK-RELPON-05: `covers()` (inclusivo de fronteira) sobre a mesma geometria
        # metrica ja projetada acima -- sem recalcular malha nem raio.
        record["contains_ponto"] = bool(geom_metric.covers(center_metric))
        records.append(record)

    if not records:
        return result

    intersectados = pd.DataFrame(records).reset_index(drop=True)
    pop_setor = _numeric(intersectados, "pop_total_setor_2022").clip(lower=0)
    intersectados["pop_estimada_intersecao"] = pop_setor * intersectados["peso_area_setor"]

    # BLK-RELPON-08: mesmo padrao de peso de area de pop_total_raio, mas para domicilios
    # particulares ocupados. NAO persistido como coluna em `intersectados`/`setores_intersectados`
    # (fora do schema de `_empty_setores_frame()`); so o agregado do raio (`domicilios_total_raio`)
    # e exposto no result.
    dom_setor = _numeric(intersectados, "domicilios_particulares_ocupados_setor_2022").clip(lower=0)
    dom_weights = dom_setor * intersectados["peso_area_setor"]

    renda = _numeric(intersectados, "renda_per_capita_setor_2022_calibrada")
    if renda.isna().all() and "renda_per_capita_setor_2022" in intersectados.columns:
        renda = _numeric(intersectados, "renda_per_capita_setor_2022")
        intersectados["renda_per_capita_setor_2022_calibrada"] = renda

    score = _numeric(intersectados, "score_setor_2022_calibrado")
    area_weights = _numeric(intersectados, "area_intersecao_m2").clip(lower=0)
    pop_weights = _numeric(intersectados, "pop_estimada_intersecao").clip(lower=0)
    renda_weight = pop_weights.where(pop_weights.gt(0), area_weights)
    score_weight = pop_weights.where(pop_weights.gt(0), area_weights)

    # ── Renda media domiciliar por setor (fase seguinte) ──────────────────────────────────────
    # A base e a renda do responsavel BRUTA (V06004), NUNCA a calibrada.
    #
    # Por que (corrigido em 2026-08-13): `uplift_composicao` foi DEFINIDO como
    #     uplift = (renda domiciliar per capita do SIDRA x moradores) / V06004_bruta
    # (ver `pipelines/derivar_uplift_renda_domiciliar.py`), ou seja ele JA leva a V06004 para a
    # escala domiciliar do IBGE. Ate esta data a base vinha de `calibrada x moradores`; como a
    # calibrada e `V06004 / moradores x k`, a ida-e-volta cancelava os moradores e sobrava
    # `V06004 x k` — o `k` virava um fator EXTRA em cima de uma conversao ja feita.
    # Medido em 5.551 municipios: a renda domiciliar exibida era exatamente 1,2335x a do IBGE,
    # com dispersao ZERO (p05 = p95 = 1,2335), isto e +23,35%. Ironia que confirma o diagnostico:
    # k x uplift = 1,2335 x 1,632 = 2,013, quase o 2,02 da GeoFusion que este mesmo pipeline
    # rejeita por escrito como circular.
    # O `k` continua existindo e continua correto no seu papel: alinhar a renda a regua de
    # percentil do M1 (`renda_pct_nacional_calibrado` -> score). Ele nunca foi fator de escala
    # de renda exibida.
    moradores = _numeric(intersectados, "avg_moradores_domicilio_setor_2022")
    if "renda_responsavel_media_setor_2022" in intersectados.columns:
        renda_domiciliar = _numeric(intersectados, "renda_responsavel_media_setor_2022")
    else:
        renda_domiciliar = pd.Series(np.nan, index=intersectados.index, dtype="float64")
    # Fallback sem a V06004: reconstroi pela per capita BRUTA (V06004/moradores), nunca pela
    # calibrada — usar a calibrada aqui reintroduziria o k pela porta dos fundos.
    if renda_domiciliar.isna().any() and "renda_per_capita_setor_2022" in intersectados.columns:
        _bruta = _numeric(intersectados, "renda_per_capita_setor_2022") * moradores
        renda_domiciliar = renda_domiciliar.where(renda_domiciliar.notna(), _bruta)
    # UF/municipio do ponto (moda) para a cascata do uplift.
    uf_ponto = None
    if "uf" in intersectados.columns:
        _ufs = intersectados["uf"].dropna()
        if not _ufs.empty:
            uf_ponto = str(_ufs.mode().iloc[0])
    municipio_ponto = None
    if "cod_municipio" in intersectados.columns:
        _muns = intersectados["cod_municipio"].dropna()
        if not _muns.empty:
            municipio_ponto = str(_muns.mode().iloc[0])
    # uplift responsavel->domicilio POR SETOR (parentesco); cascata setor->municipio->UF->nacional.
    fator_composicao_setor = pd.Series(
        [
            uplift_composicao_por_setor(cod, uf_ponto, municipio_ponto)
            for cod in intersectados.get("cod_setor", pd.Series(index=intersectados.index))
        ],
        index=intersectados.index,
        dtype="float64",
    )
    renda_domiciliar_total = renda_domiciliar * fator_composicao_setor * FATOR_TEMPORAL_RENDA
    # Renda PER CAPITA exibida = renda do domicilio dividida pelos moradores dele. E o mesmo
    # conceito que o IBGE publica (SIDRA t.10295 v.13431, "rendimento nominal medio mensal
    # domiciliar per capita") e que o M1 carrega em `renda_per_capita` — por isso e ele que se
    # compara com referencia externa e com corte absoluto.
    #
    # Ate 2026-08-13 exibia-se a coluna CALIBRADA (V06004/moradores x k). Aquilo nao era renda
    # per capita de ninguem: era a renda do RESPONSAVEL diluida por todos os moradores, escalada
    # por um k que e uma versao parcial do uplift (k = 1,2335 contra uplift 1,632). Medido, dava
    # 19,62% ABAIXO do IBGE. Note que so REMOVER o k pioraria para -34,84%: o defeito nao era o k
    # estar la, era ele estar no lugar do uplift.
    # Com esta troca, as duas rendas do relatorio passam a fechar entre si:
    #     renda domiciliar = renda per capita x moradores
    renda_per_capita_domiciliar = renda_domiciliar_total / moradores.where(moradores > 0)
    # Ressalva de leitura (ADITIVA): quanto do raio depende de uplift extrapolado.
    extrapolado_setor = pd.Series(
        [
            uplift_extrapolado(cod)
            for cod in intersectados.get("cod_setor", pd.Series(index=intersectados.index))
        ],
        index=intersectados.index,
        dtype="boolean",
    ).fillna(False)
    fator_composicao = uplift_renda_domiciliar(uf_ponto, municipio_ponto)
    # Renda domiciliar do raio: ponderada por DOMICILIOS (fallback pop/area quando ausentes).
    renda_domiciliar_weight = dom_weights.where(dom_weights.gt(0), renda_weight)

    # Injetada ANTES do corte de `display_cols`: `renda_per_capita_domiciliar` foi calculada
    # acima e e o que os dois agregados ja usam. Deixar de expo-la aqui foi o que manteve
    # `detalhe.distribuicao.renda_per_capita` (web/server/app.py) na escala antiga,
    # ~24% distante dos dois campos irmaos do MESMO payload.
    intersectados["renda_per_capita_domiciliar_setor"] = renda_per_capita_domiciliar

    display_cols = _available_columns(_empty_setores_frame().columns, intersectados)
    result["setores_intersectados"] = intersectados[display_cols].copy()
    result["n_setores"] = len(intersectados)
    result["area_intersecao_total_m2"] = round(float(area_weights.sum()), 2)

    # BLK-RELPON-05: lookup do setor que CONTEM o ponto (usa `intersectados` completa,
    # antes do corte de `display_cols`, pois `contains_ponto` nao esta em
    # `_empty_setores_frame()`). Tie-break por maior `peso_area_setor` (mais
    # "solidamente" dentro) quando mais de um setor "cobre" o ponto por ruido de
    # ponto flutuante na reprojecao.
    contains_mask = (
        intersectados.get("contains_ponto", pd.Series(False, index=intersectados.index))
        .fillna(False)
        .astype(bool)
    )
    ponto_candidatos = intersectados.loc[contains_mask]
    if not ponto_candidatos.empty:
        ponto_row = ponto_candidatos.sort_values("peso_area_setor", ascending=False).iloc[0]
        result["flag_setor_ponto_encontrado"] = True
        cod_setor_val = ponto_row.get("cod_setor")
        result["cod_setor_ponto"] = None if pd.isna(cod_setor_val) else str(cod_setor_val)
        # MESMA grandeza do agregado do raio: renda DOMICILIAR per capita (V06004 x uplift do
        # setor x fator temporal / moradores). Lido de `renda_per_capita_domiciliar` pelo rotulo
        # do indice — `intersectados` tem RangeIndex unico (`reset_index(drop=True)`), entao a
        # busca devolve escalar. Reaproveitar a Serie em vez de recalcular e' o que garante que o
        # setor do ponto e o raio nunca divirjam: um recalculo aqui abriria espaco para as duas
        # expressoes andarem separadas no proximo diff.
        #
        # Ate esta correcao o campo saia da coluna CALIBRADA — a mesma que o resto deste arquivo
        # deixou de usar. Como so o raio tinha sido corrigido, o payload passava a carregar DUAS
        # "renda per capita" em escalas ~24% distintas (`setor_do_ponto.renda_per_capita` em
        # `web/server/app.py` contra `renda_per_capita_media_raio`), justamente o sintoma que
        # esta mudanca promete curar. Antes dela as duas concordavam — ambas erradas, mas
        # coerentes —, entao corrigir so metade era uma regressao de coerencia.
        #
        # Sem fallback proprio: `renda_per_capita_domiciliar` ja carrega a cascata (V06004, e na
        # falta dela a per capita BRUTA x moradores). NaN aqui significa setor sem renda, e o
        # certo e devolver None — igual ao que o raio faz.
        renda_ponto = pd.to_numeric(
            renda_per_capita_domiciliar.get(ponto_row.name, np.nan), errors="coerce"
        )
        result["renda_per_capita_setor_ponto"] = (
            None if pd.isna(renda_ponto) else round(float(renda_ponto), 2)
        )
        densidade_ponto = pd.to_numeric(
            ponto_row.get("densidade_pop_setor_hab_km2"), errors="coerce"
        )
        result["densidade_pop_setor_ponto"] = (
            None if pd.isna(densidade_ponto) else round(float(densidade_ponto), 2)
        )
        score_ponto = pd.to_numeric(ponto_row.get("score_setor_2022_calibrado"), errors="coerce")
        result["score_setor_2022_calibrado_ponto"] = (
            None if pd.isna(score_ponto) else round(float(score_ponto), 2)
        )
        # BLK-RELPON-07: identificacao do bairro/distrito que CONTEM o ponto (D1: bairro
        # tem prioridade sobre distrito). So leitura de colunas ja carregadas em `setores_df`
        # -- `ponto_row.get(...)` retorna `None` com seguranca se a coluna nao existir.
        cod_bairro_val = ponto_row.get("cod_bairro")
        result["cod_bairro_ponto"] = None if pd.isna(cod_bairro_val) else str(cod_bairro_val)
        nome_bairro_val = ponto_row.get("nome_bairro")
        nome_bairro_ponto = None if pd.isna(nome_bairro_val) else str(nome_bairro_val).strip() or None
        result["nome_bairro_ponto"] = nome_bairro_ponto
        nome_distrito_val = ponto_row.get("nome_distrito")
        nome_distrito_ponto = None if pd.isna(nome_distrito_val) else str(nome_distrito_val).strip() or None
        result["nome_distrito_ponto"] = nome_distrito_ponto
        if nome_bairro_ponto:
            result["unidade_ponto_tipo"] = "bairro"
            result["unidade_ponto_rotulo"] = nome_bairro_ponto
        elif nome_distrito_ponto:
            result["unidade_ponto_tipo"] = "distrito"
            result["unidade_ponto_rotulo"] = nome_distrito_ponto

    if pop_weights.notna().any():
        pop_total = float(pop_weights.fillna(0).sum())
        result["pop_total_raio"] = round(pop_total, 2)
        result["densidade_pop_raio_hab_km2"] = round(pop_total / area_km2, 2)
        # BLK-RELPON-06 (D1): denominador = area de INTERSECAO VALIDA (soma das areas dos
        # setores IBGE intersectados ao circulo), nao pi*raio^2 fixo -- exclui agua/vazio
        # (o IBGE nao cobre agua). Guarda de divisao por zero: "n/d" (None) quando nao ha
        # area valida (sem setores intersectados ou area_intersecao_total_m2 <= 0).
        area_valida_m2 = result["area_intersecao_total_m2"]
        if area_valida_m2 and area_valida_m2 > 0:
            result["densidade_pop_raio_valida_hab_km2"] = round(
                pop_total / (area_valida_m2 / 1_000_000.0), 2
            )

    if dom_weights.notna().any():
        result["domicilios_total_raio"] = round(float(dom_weights.fillna(0).sum()), 2)

    result["renda_per_capita_media_raio"] = _weighted_average(
        renda_per_capita_domiciliar, renda_weight
    )
    if result["renda_per_capita_media_raio"] is not None:
        result["metodo_renda_raio"] = (
            "domiciliar_per_capita_ponderada_populacao"
            if pop_weights.gt(0).any()
            else "domiciliar_per_capita_ponderada_area"
        )

    # ── Agregacao da renda media domiciliar no raio (ADITIVO) ─────────────────────────────────
    result["renda_media_domiciliar_raio"] = _weighted_average(
        renda_domiciliar, renda_domiciliar_weight
    )
    if result["renda_media_domiciliar_raio"] is not None:
        result["metodo_renda_domiciliar_raio"] = (
            "ponderada_domicilios_estimados"
            if dom_weights.gt(0).any()
            else "ponderada_populacao_ou_area"
        )
    result["renda_domiciliar_total_raio"] = _weighted_average(
        renda_domiciliar_total, renda_domiciliar_weight
    )
    _peso_extrap = renda_domiciliar_weight.fillna(0).clip(lower=0)
    if float(_peso_extrap.sum()) > 0:
        result["fracao_uplift_extrapolado_raio"] = round(
            float(_peso_extrap[extrapolado_setor].sum() / _peso_extrap.sum()), 4
        )
    # Uplift EFETIVO do raio: media dos setores ponderada por domicilios (nao o escalar municipal).
    # Sem _weighted_average aqui: ele arredonda a 2 casas, e um fator truncado nao reproduziria a
    # renda aplicada por setor.
    _peso_uplift = renda_domiciliar_weight.where(
        fator_composicao_setor.notna() & renda_domiciliar_weight.gt(0)
    )
    if _peso_uplift.notna().any() and float(_peso_uplift.fillna(0).sum()) > 0:
        uplift_efetivo = float(
            np.average(
                fator_composicao_setor[_peso_uplift.notna()],
                weights=_peso_uplift[_peso_uplift.notna()],
            )
        )
    elif fator_composicao_setor.notna().any():
        uplift_efetivo = float(fator_composicao_setor.mean())
    else:
        uplift_efetivo = fator_composicao
    result["uf_renda_uplift"] = uf_ponto
    result["cod_municipio_renda_uplift"] = municipio_ponto
    result["fator_uplift_renda_domiciliar"] = round(uplift_efetivo * FATOR_TEMPORAL_RENDA, 4)
    result["fator_uplift_composicao"] = round(uplift_efetivo, 4)
    result["fator_uplift_composicao_municipio"] = round(fator_composicao, 4)

    result["score_setor_medio"] = _weighted_average(score, score_weight)
    if score.notna().any():
        result["score_setor_max"] = round(float(score.max()), 2)

    return result


def _perfil_bairro_default(
    *, nome_municipio: str | None, uf: str | None
) -> dict[str, object]:
    return {
        "unidade_tipo": None,
        "unidade_nome": None,
        "n_setores_unidade": 0,
        "populacao_total": None,
        "domicilios_total": None,
        "area_total_m2": None,
        "densidade_hab_km2": None,
        "renda_media_domiciliar": None,
        "metodo_renda_perfil_bairro": METODO_RENDA_PERFIL_BAIRRO,
        "flag_perfil_disponivel": False,
        "municipio_nome": nome_municipio,
        "uf": uf,
    }


def agregar_perfil_bairro_distrito(
    setores_df: pd.DataFrame,
    *,
    cod_bairro: str | None = None,
    nome_bairro: str | None = None,
    nome_distrito: str | None = None,
    nome_municipio: str | None = None,
    uf: str | None = None,
) -> dict[str, object]:
    """Agrega populacao/domicilios/densidade/renda sobre TODOS os setores de um bairro/distrito.

    BLK-RELPON-07 (slide "Perfil do Bairro/Distrito", entre Concorrentes e Big Numbers no
    PDF do Relatorio Pontual Censitario):

    - D1 (prioridade de unidade): resolve por `cod_bairro` quando disponivel; senao cai para
      `nome_distrito` (fallback). `nome_subdistrito` NUNCA e usado como unidade (descartado).
    - D2 (escopo): agrega TODOS os setores da unidade administrativa que contem o ponto --
      NAO o raio de 1.0 km do relatorio (essa e a diferenca fundamental para os outros
      agregados do modulo, que sao sempre "no raio").
    - D3.5 (formula da renda media, fechada pelo Planner): `renda_media_domiciliar` e a media
      de `renda_responsavel_media_setor_2022` PONDERADA por
      `domicilios_particulares_ocupados_setor_2022` (Metodo A, leitura GeoFusion "Renda
      Media" -- distinta da renda per capita usada em outras 2 paginas do PDF). Exclusao
      SIMETRICA: um setor so entra no numerador E no denominador se renda E domicilios forem
      nao-nulos E domicilios > 0; setor que falha qualquer condicao fica fora dos DOIS lados
      da fracao (nunca vira zero disfarcado). Sem nenhum setor valido -> `None` ("n/d").

    Funcao pura: nao muta `setores_df`, nao recalcula geometria/raio/M1. Em qualquer cenario
    sem dado suficiente (DataFrame vazio/`None`, identificador ausente, colunas ausentes,
    unidade sem setores) retorna o dict-default com `flag_perfil_disponivel=False`, sem
    excecao -- mesmo padrao gracioso do resto do modulo.
    """
    default = _perfil_bairro_default(nome_municipio=nome_municipio, uf=uf)
    if setores_df is None or setores_df.empty:
        return default

    tipo: str | None = None
    mask: pd.Series | None = None
    nome_unidade: str | None = None

    cod_bairro_str = str(cod_bairro).strip() if cod_bairro is not None else ""
    if cod_bairro_str and cod_bairro_str.lower() != "nan" and "cod_bairro" in setores_df.columns:
        tipo = "bairro"
        mask = setores_df["cod_bairro"].astype(str).str.strip() == cod_bairro_str
        nome_bairro_str = str(nome_bairro).strip() if nome_bairro is not None else ""
        nome_unidade = nome_bairro_str or cod_bairro_str
    else:
        nome_distrito_str = str(nome_distrito).strip() if nome_distrito is not None else ""
        if (
            nome_distrito_str
            and nome_distrito_str.lower() != "nan"
            and "nome_distrito" in setores_df.columns
        ):
            tipo = "distrito"
            mask = setores_df["nome_distrito"].astype(str).str.strip() == nome_distrito_str
            nome_unidade = nome_distrito_str

    if tipo is None or mask is None:
        return default

    subset = setores_df.loc[mask]
    if subset.empty:
        return default

    result = dict(default)
    result["unidade_tipo"] = tipo
    result["unidade_nome"] = nome_unidade
    result["n_setores_unidade"] = int(len(subset))

    pop = _numeric(subset, "pop_total_setor_2022")
    dom = _numeric(subset, "domicilios_particulares_ocupados_setor_2022")
    area = _numeric(subset, "area_setor_m2")
    renda = _numeric(subset, "renda_responsavel_media_setor_2022")

    populacao_total: float | None = None
    if pop.notna().any():
        populacao_total = round(float(pop[pop.notna()].sum()), 2)
    result["populacao_total"] = populacao_total

    domicilios_total: float | None = None
    if dom.notna().any():
        domicilios_total = round(float(dom[dom.notna()].sum()), 2)
    result["domicilios_total"] = domicilios_total

    area_total_m2: float | None = None
    if area.notna().any():
        area_total_m2 = round(float(area[area.notna()].sum()), 2)
    result["area_total_m2"] = area_total_m2

    if populacao_total is not None and area_total_m2 is not None and area_total_m2 > 0:
        result["densidade_hab_km2"] = round(populacao_total / (area_total_m2 / 1_000_000.0), 2)

    # D3.5: exclusao SIMETRICA -- so entra se renda E domicilios nao-nulos E domicilios > 0.
    renda_mask = renda.notna() & dom.notna() & dom.gt(0)
    if renda_mask.any():
        result["renda_media_domiciliar"] = round(
            float(np.average(renda[renda_mask], weights=dom[renda_mask])), 2
        )

    result["flag_perfil_disponivel"] = True
    return result
