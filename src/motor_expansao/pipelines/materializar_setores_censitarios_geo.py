"""Materializa setores censitarios IBGE 2022 com geometria real.

Camada paralela ao M1 oficial. Este pipeline gera um artefato derivado para o
Relatorio Pontual Censitario 1.5 km e nao altera scores nem outputs oficiais.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import make_valid
from shapely.geometry.base import BaseGeometry

try:
    from motor_expansao.pipelines.calibrar_renda_setor_2022 import (
        ajuste_executivo,
        percentile_in_distribution,
    )
except ModuleNotFoundError:
    from calibrar_renda_setor_2022 import (  # type: ignore[no-redef]
        ajuste_executivo,
        percentile_in_distribution,
    )


RAW_CENSO_DIR = Path("data/raw/CENSO 2022")
BASICO_PATH = (
    RAW_CENSO_DIR
    / "Agregados_por_setores_basico_BR_20250417"
    / "Agregados_por_setores_basico_BR_20250417.csv"
)
RENDA_PATH = (
    RAW_CENSO_DIR
    / "Agregados_por_setores_renda_responsavel_BR_csv"
    / "Agregados_por_setores_renda_responsavel_BR.csv"
)
SHAPEFILE_PATH = RAW_CENSO_DIR / "BR_setores_CD2022" / "BR_setores_CD2022.shp"
# Os CSVs basico/renda/demografia vieram com CD_SETOR corrompido em notacao cientifica (abertos
# no Excel). A renda tem a MESMA contagem/ordem dos demais agregados intactos, entao recuperamos
# o CD_SETOR real enxertando a chave de um arquivo irmao intacto (alfabetizacao). Ja o basico
# (contagem diferente, mas em ordem canonica de CD_SETOR) tem a chave recuperada pela malha
# ordenada por CD_SETOR. Ver docstring de `carregar_renda`/`carregar_basico`.
RENDA_KEY_SIBLING_PATH = (
    RAW_CENSO_DIR
    / "Agregados_por_setores_alfabetizacao_BR"
    / "Agregados_por_setores_alfabetizacao_BR.csv"
)
DEFAULT_OUTPUT_ROOT = Path("data/outputs/setores_censitarios_2022_geo")
DEFAULT_REPORT_PATH = Path("data/reports/relatorio_pontual_censitario_base_geo.md")
DEFAULT_M1_REFERENCE_PATH = Path("data/staging/brasil_estrutural.parquet")
CRS_ORIGEM = "EPSG:4674"
CRS_METRICO_AREA = "EPSG:5880"

UFS_BRASIL = {
    "RO": "11",
    "AC": "12",
    "AM": "13",
    "RR": "14",
    "PA": "15",
    "AP": "16",
    "TO": "17",
    "MA": "21",
    "PI": "22",
    "CE": "23",
    "RN": "24",
    "PB": "25",
    "PE": "26",
    "AL": "27",
    "SE": "28",
    "BA": "29",
    "MG": "31",
    "ES": "32",
    "RJ": "33",
    "SP": "35",
    "PR": "41",
    "SC": "42",
    "RS": "43",
    "MS": "50",
    "MT": "51",
    "GO": "52",
    "DF": "53",
}
UF_POR_CODIGO = {codigo: uf for uf, codigo in UFS_BRASIL.items()}

COLUNAS_ARTEFATO = [
    "cod_setor",
    "uf",
    "cod_uf",
    "cod_municipio",
    "nome_municipio",
    "cod_bairro",
    "nome_bairro",
    "nome_subdistrito",
    "nome_distrito",
    "situacao_setor",
    "area_setor_km2_ibge",
    "area_setor_m2",
    "geometry_wkb",
    "crs_origem",
    "pop_total_setor_2022",
    "domicilios_particulares_ocupados_setor_2022",
    "avg_moradores_domicilio_setor_2022",
    "renda_responsavel_media_setor_2022",
    "renda_per_capita_setor_2022",
    "renda_per_capita_setor_2022_calibrada",
    "densidade_pop_setor_hab_km2",
    "renda_pct_nacional_calibrado",
    "pop_pct_municipal",
    "hex_score_estrutural_calibrado",
    "ajuste_calibrado",
    "score_setor_2022_calibrado",
    "bbox_minx",
    "bbox_miny",
    "bbox_maxx",
    "bbox_maxy",
    "flag_renda_disponivel",
    "flag_geometria_valida",
    "flag_score_calibrado_disponivel",
    "qualidade_join_uf",
    "metodo_renda_setor_2022",
    "metodo_score_setor_2022",
    "data_materializacao",
]


@dataclass(frozen=True)
class UFSummary:
    uf: str
    municipios: int
    setores: int
    arquivos: int
    tamanho_mb: float
    tempo_s: float
    renda_cobertura_pct: float
    score_cobertura_pct: float


def _normalizar_codigo_ibge(value: object, digits: int) -> str | None:
    if value is None or pd.isna(value):
        return None
    raw = str(value).strip()
    if not raw:
        return None
    raw = raw.replace(",", ".")
    try:
        if "E" in raw.upper():
            raw = str(int(Decimal(raw)))
        else:
            raw = raw.split(".")[0]
    except (InvalidOperation, ValueError):
        return None
    return raw.zfill(digits)[-digits:]


def _to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", ".", regex=False), errors="coerce")


# Valores que representam ausencia de bairro no shapefile IBGE (NA, vazio, "nan").
_BAIRRO_NULOS = {"", "nan", "none", "<na>", "null"}


def _normalizar_nome_bairro(value: object) -> object:
    """Limpa o NM_BAIRRO do shapefile: vazio/'nan'/mojibake irrecuperavel -> NA.

    O `.cpg` da malha IBGE 2022 diz UTF-8, mas amostras mostraram mojibake quando o driver
    decodifica como latin-1. A leitura forca `encoding="utf-8"` (ver `carregar_malha_uf`); aqui
    so descartamos sentinelas de ausencia (NA/""/"nan") preservando os acentos UTF-8 validos.
    """
    if value is None or pd.isna(value):
        return pd.NA
    text = str(value).strip()
    if text.casefold() in _BAIRRO_NULOS:
        return pd.NA
    return text


def _read_csv_with_encoding(path: Path, **kwargs) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(path, sep=";", encoding=encoding, dtype=str, low_memory=False, **kwargs)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, sep=";", encoding="latin-1", dtype=str, low_memory=False, **kwargs)


def carregar_basico(
    path: Path = BASICO_PATH,
    chaves_ordenadas: pd.Series | None = None,
) -> pd.DataFrame:
    """Carrega o Agregado basico (pop/moradores/domicilios).

    O CD_SETOR do CSV veio corrompido (notacao cientifica). Como o arquivo esta em ordem
    canonica de CD_SETOR (CD_MUN nao-decrescente) e tem a MESMA contagem da malha, recuperamos
    o CD_SETOR real por posicao a partir de `chaves_ordenadas` (cod_setor da malha ordenado por
    CD_SETOR). A verificacao exige que o municipio embutido no cod_setor recuperado (7 primeiros
    digitos) bata com o CD_MUN intacto do proprio basico.
    """
    usecols = ["CD_UF", "CD_MUN", "AREA_KM2", "v0001", "v0005", "v0007"]
    df = _read_csv_with_encoding(path, usecols=usecols)
    df["cod_uf"] = df["CD_UF"].astype(str).str.zfill(2)
    df["uf"] = df["cod_uf"].map(UF_POR_CODIGO)
    df["cod_municipio"] = df["CD_MUN"].astype(str).str.split(".").str[0].str.zfill(7)

    if chaves_ordenadas is not None:
        if len(chaves_ordenadas) != len(df):
            raise ValueError(
                f"Recuperacao de chave do basico: malha ({len(chaves_ordenadas)}) e "
                f"basico ({len(df)}) precisam ter o mesmo total."
            )
        cod_setor = pd.Series(list(chaves_ordenadas), index=df.index, dtype="object")
        conf = float((cod_setor.str[:7].values == df["cod_municipio"].values).mean())
        if conf < 0.99:
            raise ValueError(
                f"Recuperacao de chave do basico suspeita: so {conf*100:.2f}% dos setores "
                "tem municipio coerente entre chave recuperada e CD_MUN do basico."
            )
        df["cod_setor"] = cod_setor
    df["area_setor_km2_ibge"] = _to_number(df["AREA_KM2"])
    df["pop_total_setor_2022"] = _to_number(df["v0001"]).clip(lower=0)
    df["domicilios_particulares_ocupados_setor_2022"] = _to_number(df["v0007"]).clip(lower=0)
    df["avg_moradores_domicilio_setor_2022"] = _to_number(df["v0005"]).clip(lower=1, upper=15)
    fallback_avg = np.where(
        df["domicilios_particulares_ocupados_setor_2022"] > 0,
        df["pop_total_setor_2022"] / df["domicilios_particulares_ocupados_setor_2022"],
        np.nan,
    )
    df["avg_moradores_domicilio_setor_2022"] = df[
        "avg_moradores_domicilio_setor_2022"
    ].fillna(pd.Series(fallback_avg, index=df.index))
    saida = [
        "uf",
        "cod_uf",
        "cod_municipio",
        "area_setor_km2_ibge",
        "pop_total_setor_2022",
        "domicilios_particulares_ocupados_setor_2022",
        "avg_moradores_domicilio_setor_2022",
    ]
    if "cod_setor" in df.columns:
        saida = ["cod_setor", *saida]
    return df[saida].reset_index(drop=True)


def carregar_renda(
    path: Path = RENDA_PATH,
    chave_sibling_path: Path | None = None,
) -> pd.DataFrame:
    """Carrega o Agregado de renda do responsavel (V06004).

    O CD_SETOR do CSV veio corrompido (notacao cientifica). Recuperamos o CD_SETOR real
    enxertando, por posicao, a chave de um agregado irmao INTACTO (`chave_sibling_path`), que
    tem exatamente a mesma contagem e ordem de setores. A verificacao exige que a UF derivada
    do valor corrompido (cujos primeiros digitos sobrevivem) bata com a UF da chave recuperada.
    """
    # O irmao intacto vive na mesma raiz CENSO do proprio arquivo de renda (nao no RAW_CENSO_DIR
    # do modulo), para funcionar tambem quando os insumos vem de outro diretorio.
    if chave_sibling_path is None:
        chave_sibling_path = (
            path.parent.parent
            / "Agregados_por_setores_alfabetizacao_BR"
            / "Agregados_por_setores_alfabetizacao_BR.csv"
        )

    df = _read_csv_with_encoding(path)
    setor_as_int = (
        df["CD_SETOR"]
        .astype(str)
        .str.replace(",", ".", regex=False)
        .map(lambda value: Decimal(value) if value and value.upper() != "NAN" else None)
    )
    uf_corrompido = setor_as_int.map(
        lambda value: str(int(value // Decimal("1e13"))).zfill(2) if value else None
    )

    sib = _read_csv_with_encoding(chave_sibling_path, usecols=[0]).iloc[:, 0]
    cod_setor = sib.map(lambda value: _normalizar_codigo_ibge(value, 15))
    if len(cod_setor) != len(df):
        raise ValueError(
            f"Recuperacao de chave da renda: irmao intacto ({len(cod_setor)}) e renda "
            f"({len(df)}) precisam ter o mesmo total."
        )
    cod_setor = pd.Series(list(cod_setor), index=df.index, dtype="object")
    conf = float((cod_setor.str[:2].values == uf_corrompido.values).mean())
    if conf < 0.99:
        raise ValueError(
            f"Recuperacao de chave da renda suspeita: so {conf*100:.2f}% das UFs batem "
            "entre valor corrompido e chave recuperada."
        )
    df["cod_setor"] = cod_setor
    df["cod_uf"] = cod_setor.str[:2]
    df["uf"] = df["cod_uf"].map(UF_POR_CODIGO)
    df["renda_responsavel_media_setor_2022"] = _to_number(df["V06004"])
    df["responsaveis_com_renda_setor_2022"] = _to_number(df["V06001"]).clip(lower=0)
    return df[
        [
            "cod_setor",
            "uf",
            "cod_uf",
            "renda_responsavel_media_setor_2022",
            "responsaveis_com_renda_setor_2022",
        ]
    ].reset_index(drop=True)


def _ler_chaves_ordenadas(shp_path: Path = SHAPEFILE_PATH) -> pd.Series:
    """cod_setor de TODA a malha, ordenado por CD_SETOR.

    E' a chave usada para recuperar o CD_SETOR corrompido do Basico, que esta em ordem canonica
    de CD_SETOR e tem a mesma contagem da malha. So os atributos sao lidos (sem geometria).
    """
    try:
        atributos = gpd.read_file(shp_path, columns=["CD_SETOR"], ignore_geometry=True)
    except (TypeError, ValueError):
        atributos = gpd.read_file(shp_path)[["CD_SETOR"]]
    chaves = atributos["CD_SETOR"].map(lambda value: _normalizar_codigo_ibge(value, 15)).dropna()
    return pd.Series(sorted(chaves.tolist()), dtype="object")


def carregar_malha_uf(path: Path, uf: str) -> gpd.GeoDataFrame:
    uf = uf.upper()
    cod_uf = UFS_BRASIL[uf]
    # `encoding="utf-8"` forca o driver (pyogrio/fiona) a respeitar o .cpg UTF-8 da malha IBGE
    # 2022 e preservar os acentos do NM_BAIRRO (sem isso houve mojibake na amostra do Planner).
    gdf = gpd.read_file(path, where=f"CD_UF='{cod_uf}'", encoding="utf-8")
    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_ORIGEM)
    elif gdf.crs.to_string() != CRS_ORIGEM:
        gdf = gdf.to_crs(CRS_ORIGEM)

    cols = [
        "CD_SETOR", "CD_UF", "CD_MUN", "NM_MUN", "CD_BAIRRO", "NM_BAIRRO",
        "NM_SUBDIST", "NM_DIST", "SITUACAO", "AREA_KM2", "geometry",
    ]
    gdf = gdf[[col for col in cols if col in gdf.columns]].copy()
    gdf["cod_setor"] = gdf["CD_SETOR"].map(lambda value: _normalizar_codigo_ibge(value, 15))
    gdf["cod_uf"] = gdf["CD_UF"].astype(str).str.zfill(2)
    gdf["uf"] = gdf["cod_uf"].map(UF_POR_CODIGO)
    gdf["cod_municipio"] = gdf["CD_MUN"].astype(str).str.zfill(7)
    gdf["nome_municipio"] = gdf["NM_MUN"].astype(str)
    # NM_BAIRRO existe no DBF IBGE 2022 mas cobertura e HETEROGENEA (capitais/grandes têm; muitos
    # municipios pequenos e o DF nao têm) -> NA quando ausente. cod_bairro opcional p/ rastreio.
    # NM_SUBDIST/NM_DIST sao niveis mais GROSSOS (distrito/subdistrito) usados como FALLBACK em
    # cascata pelo relatorio (bairro -> subdistrito -> distrito) p/ municipios sem bairro (ex.: SP
    # usa distritos; DF nao tem bairro). Normalizados com o mesmo helper (vazio/"nan"/mojibake->NA).
    if "NM_BAIRRO" in gdf.columns:
        gdf["nome_bairro"] = gdf["NM_BAIRRO"].map(_normalizar_nome_bairro)
    else:
        gdf["nome_bairro"] = pd.NA
    if "CD_BAIRRO" in gdf.columns:
        gdf["cod_bairro"] = gdf["CD_BAIRRO"].map(lambda value: _normalizar_codigo_ibge(value, 13))
    else:
        gdf["cod_bairro"] = pd.NA
    if "NM_SUBDIST" in gdf.columns:
        gdf["nome_subdistrito"] = gdf["NM_SUBDIST"].map(_normalizar_nome_bairro)
    else:
        gdf["nome_subdistrito"] = pd.NA
    if "NM_DIST" in gdf.columns:
        gdf["nome_distrito"] = gdf["NM_DIST"].map(_normalizar_nome_bairro)
    else:
        gdf["nome_distrito"] = pd.NA
    gdf["situacao_setor"] = gdf.get("SITUACAO", pd.Series(pd.NA, index=gdf.index))
    gdf["area_setor_km2_ibge"] = _to_number(gdf.get("AREA_KM2", pd.Series(np.nan, index=gdf.index)))
    return gdf.reset_index(drop=True)


def _corrigir_geometria(geom: BaseGeometry | None) -> BaseGeometry | None:
    if geom is None or geom.is_empty:
        return None
    if geom.is_valid:
        return geom
    fixed = make_valid(geom)
    if fixed is None or fixed.is_empty:
        return None
    return fixed


def _calcular_scores_setoriais(df: pd.DataFrame, m1_reference: pd.DataFrame | None) -> pd.DataFrame:
    result = df.copy()
    valid_renda = result["renda_per_capita_setor_2022"].notna()

    if m1_reference is not None and "renda_per_capita" in m1_reference.columns:
        ref_renda = pd.to_numeric(m1_reference["renda_per_capita"], errors="coerce").dropna().to_numpy()
    else:
        ref_renda = np.array([], dtype=float)

    if len(ref_renda) > 0 and valid_renda.any():
        setor_median = float(result.loc[valid_renda, "renda_per_capita_setor_2022"].median())
        k_global = float(np.median(ref_renda) / setor_median) if setor_median > 0 else 1.0
        result["renda_per_capita_setor_2022_calibrada"] = (
            result["renda_per_capita_setor_2022"] * k_global
        )
        renda_cal = result.loc[valid_renda, "renda_per_capita_setor_2022_calibrada"].to_numpy()
        result.loc[valid_renda, "renda_pct_nacional_calibrado"] = percentile_in_distribution(
            renda_cal,
            ref_renda,
        )
        metodo_renda = f"v06004_div_v0005_multiplicativo_global_k={k_global:.4f}"
    else:
        result["renda_per_capita_setor_2022_calibrada"] = result["renda_per_capita_setor_2022"]
        if valid_renda.any():
            result.loc[valid_renda, "renda_pct_nacional_calibrado"] = (
                result.loc[valid_renda, "renda_per_capita_setor_2022_calibrada"].rank(pct=True)
            )
        metodo_renda = "v06004_div_v0005_sem_referencia_m1"

    result["pop_pct_municipal"] = (
        result.groupby("cod_municipio")["pop_total_setor_2022"]
        .rank(pct=True, method="average")
        .astype(float)
    )
    score_mask = result["renda_pct_nacional_calibrado"].notna() & result["pop_pct_municipal"].notna()
    result["hex_score_estrutural_calibrado"] = np.nan
    result["ajuste_calibrado"] = np.nan
    result["score_setor_2022_calibrado"] = np.nan
    if score_mask.any():
        renda_pct = result.loc[score_mask, "renda_pct_nacional_calibrado"].to_numpy(dtype=float)
        pop_pct = result.loc[score_mask, "pop_pct_municipal"].to_numpy(dtype=float)
        hex_score = 100.0 * (0.60 * renda_pct + 0.40 * pop_pct)
        ajuste = ajuste_executivo(renda_pct, pop_pct)
        result.loc[score_mask, "hex_score_estrutural_calibrado"] = hex_score
        result.loc[score_mask, "ajuste_calibrado"] = ajuste
        result.loc[score_mask, "score_setor_2022_calibrado"] = np.clip(
            hex_score + ajuste,
            0.0,
            100.0,
        )

    result["flag_score_calibrado_disponivel"] = result["score_setor_2022_calibrado"].notna()
    result["metodo_renda_setor_2022"] = metodo_renda
    result["metodo_score_setor_2022"] = (
        "score_setorial_paralelo_0p60_renda_pct_m1_0p40_pop_pct_municipal"
    )
    return result


def montar_base_setorial_uf(
    gdf_malha: gpd.GeoDataFrame,
    basico_uf: pd.DataFrame,
    renda_uf: pd.DataFrame,
    *,
    uf: str,
    m1_reference: pd.DataFrame | None = None,
    data_materializacao: str | None = None,
) -> gpd.GeoDataFrame:
    if "cod_setor" not in gdf_malha.columns:
        raise ValueError(f"UF {uf}: malha sem coluna cod_setor para join por chave.")
    if "cod_setor" not in basico_uf.columns or "cod_setor" not in renda_uf.columns:
        raise ValueError(
            f"UF {uf}: basico/renda precisam ter cod_setor recuperado para join por chave "
            "(nao use mais join posicional)."
        )

    result = gdf_malha.copy()
    # `carregar_malha_uf` ja produz `nome_bairro`/`cod_bairro` (IBGE NM_BAIRRO/CD_BAIRRO); para
    # qualquer outro caller (ex.: malha sintetica em teste) garante a presenca das colunas como NA
    # antes da selecao final de `COLUNAS_ARTEFATO`. READ-ONLY sobre o M1.
    for opt_col in ("nome_bairro", "cod_bairro", "nome_subdistrito", "nome_distrito"):
        if opt_col not in result.columns:
            result[opt_col] = pd.NA
    # Join por CHAVE cod_setor (o antigo join posicional era invalido: basico e renda tem
    # contagens diferentes e ordens distintas da malha). A malha e' o ancoramento (left join);
    # `area_setor_km2_ibge` vem da malha, nao do basico.
    basic_cols = [
        "pop_total_setor_2022",
        "domicilios_particulares_ocupados_setor_2022",
        "avg_moradores_domicilio_setor_2022",
    ]
    result = result.merge(
        basico_uf[["cod_setor", *basic_cols]].drop_duplicates("cod_setor"),
        on="cod_setor",
        how="left",
    )
    result = result.merge(
        renda_uf[["cod_setor", "renda_responsavel_media_setor_2022"]].drop_duplicates("cod_setor"),
        on="cod_setor",
        how="left",
    )
    result["renda_per_capita_setor_2022"] = np.where(
        result["avg_moradores_domicilio_setor_2022"] > 0,
        result["renda_responsavel_media_setor_2022"]
        / result["avg_moradores_domicilio_setor_2022"],
        np.nan,
    )

    result["geometry"] = result.geometry.map(_corrigir_geometria)
    result = result[result.geometry.notna()].copy()
    result["flag_geometria_valida"] = result.geometry.is_valid & ~result.geometry.is_empty

    bounds = result.bounds
    result["bbox_minx"] = bounds["minx"]
    result["bbox_miny"] = bounds["miny"]
    result["bbox_maxx"] = bounds["maxx"]
    result["bbox_maxy"] = bounds["maxy"]

    metric = result.to_crs(CRS_METRICO_AREA)
    result["area_setor_m2"] = metric.geometry.area
    result["densidade_pop_setor_hab_km2"] = np.where(
        result["area_setor_m2"] > 0,
        result["pop_total_setor_2022"] / (result["area_setor_m2"] / 1_000_000.0),
        np.nan,
    )
    result["flag_renda_disponivel"] = result["renda_per_capita_setor_2022"].notna()
    # Qualidade = taxa REAL de setores da malha que casaram com a renda por chave (antes era uma
    # comparacao de contagens, que nada dizia sobre o acerto do join).
    taxa_match = float(result["flag_renda_disponivel"].mean()) if len(result) else 0.0
    result["qualidade_join_uf"] = "A" if taxa_match >= 0.95 else ("B" if taxa_match >= 0.90 else "C")

    geometries = result.geometry.copy()
    result = _calcular_scores_setoriais(pd.DataFrame(result.drop(columns="geometry")), m1_reference)
    result = gpd.GeoDataFrame(result, geometry=geometries, crs=CRS_ORIGEM)
    result["geometry_wkb"] = result.geometry.to_wkb()
    result["crs_origem"] = CRS_ORIGEM
    result["data_materializacao"] = data_materializacao or date.today().isoformat()
    return result[COLUNAS_ARTEFATO].reset_index(drop=True)


def escrever_particoes(df: pd.DataFrame, output_root: Path) -> dict[str, int]:
    output_root.mkdir(parents=True, exist_ok=True)
    files = 0
    rows = 0
    for (uf, cod_municipio), part in df.groupby(["uf", "cod_municipio"], dropna=False):
        part_dir = output_root / f"uf={uf}" / f"cod_municipio={cod_municipio}"
        part_dir.mkdir(parents=True, exist_ok=True)
        part_path = part_dir / "part-000.parquet"
        part.to_parquet(part_path, index=False)
        files += 1
        rows += len(part)
    return {"arquivos": files, "linhas": rows}


def ler_particao_setores(
    root: Path = DEFAULT_OUTPUT_ROOT,
    *,
    uf: str,
    cod_municipio: str | None = None,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    uf = uf.upper()
    base = root / f"uf={uf}"
    if cod_municipio:
        paths = sorted((base / f"cod_municipio={cod_municipio}").glob("*.parquet"))
    else:
        paths = sorted(base.glob("cod_municipio=*/*.parquet"))
    if not paths:
        return pd.DataFrame(columns=columns or COLUNAS_ARTEFATO)
    return pd.concat([pd.read_parquet(path, columns=columns) for path in paths], ignore_index=True)


def _dir_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = sum(p.stat().st_size for p in path.rglob("*.parquet"))
    return round(total / 1024 / 1024, 2)


def gerar_relatorio(summaries: list[UFSummary], output_root: Path, schema: list[str]) -> str:
    total_setores = sum(s.setores for s in summaries)
    total_files = sum(s.arquivos for s in summaries)
    total_size = round(sum(s.tamanho_mb for s in summaries), 2)
    lines = [
        "# Relatorio - Base censitaria geografica otimizada",
        "",
        f"> Gerado em {date.today().isoformat()} para o ciclo Relatorio Pontual Censitario 1.5 km.",
        "",
        "## Resumo",
        "",
        f"- Artefato: `{output_root.as_posix()}`",
        "- Formato: Parquet com `geometry_wkb`, particionado por `uf` e `cod_municipio`.",
        f"- Setores materializados: {total_setores:,}".replace(",", "."),
        f"- Arquivos parquet: {total_files:,}".replace(",", "."),
        f"- Tamanho total: {total_size:.2f} MB",
        "- Guardrail: artefato derivado; nao altera M1 oficial, carteira ou plano.",
        "",
        "## Performance por UF",
        "",
        "| UF | Municipios | Setores | Arquivos | Tamanho MB | Tempo s | Renda % | Score % |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for s in summaries:
        lines.append(
            f"| {s.uf} | {s.municipios} | {s.setores} | {s.arquivos} | "
            f"{s.tamanho_mb:.2f} | {s.tempo_s:.2f} | {s.renda_cobertura_pct:.2f} | "
            f"{s.score_cobertura_pct:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Schema",
            "",
            ", ".join(f"`{col}`" for col in schema),
            "",
            "## Observacoes",
            "",
            "- A geometria permanece no CRS original `EPSG:4674`; areas sao calculadas em `EPSG:5880`.",
            "- A renda setorial usa `V06004 / v0005` e calibracao multiplicativa global quando a referencia M1 esta disponivel.",
            "- O score setorial e paralelo e operacional; nao substitui `score_priorizacao`.",
            "- O CSV de renda possui menos linhas que a malha/Basico. O join e' feito por CHAVE "
            "`cod_setor` (nao posicional) e `qualidade_join_uf` registra a taxa real de match. A "
            "chave e' recuperada: na renda, enxertando o `CD_SETOR` de um agregado irmao intacto "
            "(alfabetizacao); no basico, pela malha ordenada por `CD_SETOR`.",
        ]
    )
    return "\n".join(lines) + "\n"


def materializar_base_geo(
    *,
    ufs: list[str] | None = None,
    municipios: list[str] | None = None,
    basico_path: Path = BASICO_PATH,
    renda_path: Path = RENDA_PATH,
    shp_path: Path = SHAPEFILE_PATH,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    report_path: Path = DEFAULT_REPORT_PATH,
    m1_reference_path: Path = DEFAULT_M1_REFERENCE_PATH,
    max_municipios_por_uf: int | None = None,
) -> dict:
    for path in (basico_path, renda_path, shp_path):
        if not path.exists():
            raise FileNotFoundError(f"Insumo nao encontrado: {path}")

    ufs = [uf.upper() for uf in (ufs or sorted(UFS_BRASIL))]
    invalid = sorted(set(ufs) - set(UFS_BRASIL))
    if invalid:
        raise ValueError(f"UFs invalidas: {invalid}")

    chaves_ordenadas = _ler_chaves_ordenadas(shp_path)
    basico = carregar_basico(basico_path, chaves_ordenadas=chaves_ordenadas)
    renda = carregar_renda(renda_path)
    m1_reference = (
        pd.read_parquet(m1_reference_path, columns=["renda_per_capita"])
        if m1_reference_path.exists()
        else None
    )

    summaries: list[UFSummary] = []
    municipios_set = {m.strip() for m in municipios or []}
    for uf in ufs:
        t0 = time.perf_counter()
        gdf_malha = carregar_malha_uf(shp_path, uf)
        basico_uf = basico[basico["uf"] == uf].reset_index(drop=True)
        renda_uf = renda[renda["uf"] == uf].reset_index(drop=True)

        # Basta filtrar a MALHA: basico/renda entram por join de chave (cod_setor), entao apenas
        # os setores da malha filtrada sobrevivem ao left join. Fatiar basico/renda por posicao
        # (como antes) misturava setores de municipios diferentes.
        if municipios_set:
            gdf_malha = gdf_malha[
                gdf_malha["cod_municipio"].isin(municipios_set)
            ].reset_index(drop=True)
        elif max_municipios_por_uf:
            selected = sorted(gdf_malha["cod_municipio"].dropna().unique())[:max_municipios_por_uf]
            gdf_malha = gdf_malha[gdf_malha["cod_municipio"].isin(selected)].reset_index(drop=True)

        df_uf = montar_base_setorial_uf(
            gdf_malha,
            basico_uf,
            renda_uf,
            uf=uf,
            m1_reference=m1_reference,
        )
        write_info = escrever_particoes(df_uf, output_root)
        uf_root = output_root / f"uf={uf}"
        tempo_s = time.perf_counter() - t0
        summaries.append(
            UFSummary(
                uf=uf,
                municipios=int(df_uf["cod_municipio"].nunique()),
                setores=len(df_uf),
                arquivos=write_info["arquivos"],
                tamanho_mb=_dir_size_mb(uf_root),
                tempo_s=round(tempo_s, 2),
                renda_cobertura_pct=round(float(df_uf["flag_renda_disponivel"].mean() * 100), 2),
                score_cobertura_pct=round(
                    float(df_uf["flag_score_calibrado_disponivel"].mean() * 100),
                    2,
                ),
            )
        )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(gerar_relatorio(summaries, output_root, COLUNAS_ARTEFATO), encoding="utf-8")
    metadata = {
        "data_execucao": date.today().isoformat(),
        "output_root": str(output_root),
        "report_path": str(report_path),
        "ufs": [s.__dict__ for s in summaries],
        "schema": COLUNAS_ARTEFATO,
    }
    (output_root / "_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materializa setores censitarios 2022 com geometria WKB por UF/municipio."
    )
    parser.add_argument("--uf", action="append", default=[], help="UF a processar. Repetir para varias.")
    parser.add_argument("--municipio", action="append", default=[], help="Codigo IBGE de municipio.")
    parser.add_argument("--max-municipios-por-uf", type=int, default=None)
    parser.add_argument("--basico-path", default=str(BASICO_PATH))
    parser.add_argument("--renda-path", default=str(RENDA_PATH))
    parser.add_argument("--shp-path", default=str(SHAPEFILE_PATH))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--m1-reference-path", default=str(DEFAULT_M1_REFERENCE_PATH))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    metadata = materializar_base_geo(
        ufs=args.uf or None,
        municipios=args.municipio or None,
        basico_path=Path(args.basico_path),
        renda_path=Path(args.renda_path),
        shp_path=Path(args.shp_path),
        output_root=Path(args.output_root),
        report_path=Path(args.report_path),
        m1_reference_path=Path(args.m1_reference_path),
        max_municipios_por_uf=args.max_municipios_por_uf,
    )
    total = sum(item["setores"] for item in metadata["ufs"])
    print(f"Base geo materializada: {total} setores em {metadata['output_root']}")


if __name__ == "__main__":
    main()
