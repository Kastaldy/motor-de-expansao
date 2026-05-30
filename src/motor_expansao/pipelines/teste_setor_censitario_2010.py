"""
Experimento paralelo para validar granularidade de setor censitario IBGE 2010.

Objetivos:
- nao altera o pipeline oficial da Fase 1
- reaproveita apenas artefatos ja gerados do M1 para comparacao
- escreve apenas em `data/staging/teste_setor_2010`, `data/outputs/teste_setor_2010`
  e `data/reports/teste_setor_2010.md`
"""

from __future__ import annotations

import argparse
import json
import math
import time
import unicodedata
from collections.abc import Sequence
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import shapely
import structlog
from shapely.geometry import shape
from shapely.strtree import STRtree

from motor_expansao.pipelines.m1.hex_enrichment import (
    _calcular_percentil_nacional,
    calcular_populacao_proxy,
    resumir_distribuicao_score,
)

log = structlog.get_logger()


def _percentil_em_distribuicao_referencia(
    serie: pd.Series, referencia: pd.Series
) -> pd.Series:
    """Percentil de cada valor de `serie` dentro da distribuicao `referencia`.

    Permite ancorar percentis de setor 2010 na distribuicao nacional do M1,
    tornando o score comparavel com o ranking oficial sem recalcular a base nacional.
    """
    serie = pd.to_numeric(serie, errors="coerce")
    ref = pd.to_numeric(referencia, errors="coerce").dropna().sort_values().values
    resultado = pd.Series(float("nan"), index=serie.index, dtype="float64")
    mascara = serie.notna()
    if mascara.any() and len(ref) > 1:
        idx = np.searchsorted(ref, serie.loc[mascara].values, side="right")
        resultado.loc[mascara] = (idx / len(ref)).round(6)
    return resultado


DEFAULT_CIDADES_ALVO = (
    {"cidade": "Sao Paulo", "uf": "SP", "cod_municipio": "3550308"},
    {"cidade": "Goiania", "uf": "GO", "cod_municipio": "5208707"},
    {"cidade": "Campinas", "uf": "SP", "cod_municipio": "3509502"},
)

DEFAULT_BASE_OFICIAL_PATH = Path("data/staging/brasil_estrutural.parquet")
DEFAULT_MUNICIPIOS_ROOT = Path("data/ibge")
DEFAULT_SETORES_ROOT = Path("data/raw/ibge_setor_2010")
DEFAULT_STAGING_DIR = Path("data/staging/teste_setor_2010")
DEFAULT_OUTPUTS_DIR = Path("data/outputs/teste_setor_2010")
DEFAULT_REPORT_PATH = Path("data/reports/teste_setor_2010.md")

SUPPORTED_GEOMETRY_SUFFIXES = {".geojson", ".json", ".parquet"}
SUPPORTED_TABLE_SUFFIXES = {".csv", ".xlsx", ".xls", ".parquet", ".json"}

COD_SETOR_CANDIDATES = (
    "cod_setor",
    "cd_setor",
    "codigo_setor",
    "id_setor",
    "setor",
    "geocodigo",
    "geocod",
    "cd_geocodi",
    "cd_geocodigo",
)
COD_MUNICIPIO_CANDIDATES = (
    "cod_municipio",
    "cd_mun",
    "cd_municipio",
    "codigo_municipio",
    "id_municipio",
    "codarea",
    "geocodigomunicipio",
    "cod_mun",
)
RENDA_CANDIDATES = (
    "renda_media_domiciliar_per_capita",
    "renda_per_capita",
    "renda_media",
    "renda_domiciliar_media",
    "renda",
    "income",
)
POP_TOTAL_CANDIDATES = (
    "pop_total",
    "populacao_total",
    "total_pessoas",
    "total_moradores",
    "populacao",
)
POP_TARGET_CANDIDATES = (
    "pop_18_45",
    "pop_18a45",
    "pop_18_44",
    "pop_target",
    "pop_faixa_target",
    "pop_idade_target",
)


def _slug(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return "".join(ch.lower() for ch in texto if ch.isalnum())


def _normalizar_codigo(valor: object, tamanho: int | None = None) -> str | None:
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return None
    digitos = "".join(ch for ch in str(valor) if ch.isdigit())
    if not digitos:
        return None
    if tamanho is not None and len(digitos) < tamanho:
        digitos = digitos.zfill(tamanho)
    if tamanho is not None and len(digitos) != tamanho:
        return None
    return digitos


def _resolver_coluna_por_candidatos(
    df: pd.DataFrame,
    candidatos: Sequence[str],
    *,
    obrigatoria: bool,
    descricao: str,
) -> str | None:
    colunas_slug = {_slug(coluna): coluna for coluna in df.columns}
    for candidato in candidatos:
        encontrado = colunas_slug.get(_slug(candidato))
        if encontrado:
            return encontrado

    for coluna in df.columns:
        slug = _slug(coluna)
        if any(_slug(candidato) in slug for candidato in candidatos):
            return coluna

    if obrigatoria:
        raise ValueError(f"Nao foi possivel detectar a coluna de {descricao}.")
    return None


def _carregar_tabela(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return pd.DataFrame(payload)
        if isinstance(payload, dict):
            for chave in ("data", "rows", "items", "records"):
                if isinstance(payload.get(chave), list):
                    return pd.DataFrame(payload[chave])
            return pd.DataFrame([payload])
    raise ValueError(f"Formato tabular nao suportado: {path.suffix}")


def _detectar_geometry_parquet(df: pd.DataFrame) -> str:
    candidatos = (
        "geometry",
        "geom",
        "wkt",
        "geometry_wkt",
        "geometry_geojson",
        "geojson",
    )
    coluna = _resolver_coluna_por_candidatos(
        df,
        candidatos,
        obrigatoria=True,
        descricao="geometria de setor",
    )
    assert coluna is not None
    return coluna


def _converter_geometry(valor: object) -> shapely.Geometry | None:
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return None
    if hasattr(valor, "geom_type"):
        return valor
    if isinstance(valor, (bytes, bytearray, memoryview)):
        try:
            return shapely.from_wkb(bytes(valor))
        except Exception:
            return None
    texto = str(valor).strip()
    if not texto:
        return None
    if texto[0] in "{[":
        try:
            return shape(json.loads(texto))
        except Exception:
            return None
    try:
        return shapely.from_wkt(texto)
    except Exception:
        return None


def _carregar_geometrias_setor(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".geojson", ".json"}:
        payload = json.loads(path.read_text(encoding="utf-8"))
        features = payload.get("features", [])
        registros: list[dict] = []
        for feature in features:
            properties = dict(feature.get("properties", {}))
            properties["geometry"] = shape(feature["geometry"])
            registros.append(properties)
        df = pd.DataFrame(registros)
    elif suffix == ".parquet":
        df = pd.read_parquet(path)
        geometry_col = _detectar_geometry_parquet(df)
        df = df.copy()
        df["geometry"] = df[geometry_col].map(_converter_geometry)
    else:
        raise ValueError(
            f"Formato geometrico nao suportado: {path.suffix}. "
            "Use GeoJSON/JSON/Parquet com geometria WKT/WKB/GeoJSON."
        )

    if df.empty:
        raise ValueError(f"Malha de setores veio vazia: {path}")

    cod_setor_col = _resolver_coluna_por_candidatos(
        df,
        COD_SETOR_CANDIDATES,
        obrigatoria=True,
        descricao="codigo de setor na malha",
    )
    assert cod_setor_col is not None

    cod_municipio_col = _resolver_coluna_por_candidatos(
        df,
        COD_MUNICIPIO_CANDIDATES,
        obrigatoria=False,
        descricao="codigo de municipio na malha",
    )

    df = df.copy()
    df["cod_setor"] = df[cod_setor_col].map(lambda valor: _normalizar_codigo(valor))
    if cod_municipio_col:
        df["cod_municipio"] = df[cod_municipio_col].map(lambda valor: _normalizar_codigo(valor, 7))
    else:
        df["cod_municipio"] = df["cod_setor"].str.slice(0, 7)
    df = df[df["cod_setor"].notna() & df["geometry"].notna()].copy()
    df["geometry"] = df["geometry"].map(lambda geom: geom if geom.is_valid else geom.buffer(0))
    if df.empty:
        raise ValueError(f"Nenhum setor valido encontrado em {path}.")
    return df


def _carregar_atributos_setor(path: Path) -> tuple[pd.DataFrame, dict]:
    df = _carregar_tabela(path)
    if df.empty:
        raise ValueError(f"Base tabular de setores veio vazia: {path}")

    cod_setor_col = _resolver_coluna_por_candidatos(
        df,
        COD_SETOR_CANDIDATES,
        obrigatoria=True,
        descricao="codigo de setor nos atributos",
    )
    assert cod_setor_col is not None

    cod_municipio_col = _resolver_coluna_por_candidatos(
        df,
        COD_MUNICIPIO_CANDIDATES,
        obrigatoria=False,
        descricao="codigo de municipio nos atributos",
    )
    renda_col = _resolver_coluna_por_candidatos(
        df,
        RENDA_CANDIDATES,
        obrigatoria=True,
        descricao="renda",
    )
    pop_target_col = _resolver_coluna_por_candidatos(
        df,
        POP_TARGET_CANDIDATES,
        obrigatoria=False,
        descricao="populacao target",
    )
    pop_total_col = _resolver_coluna_por_candidatos(
        df,
        POP_TOTAL_CANDIDATES,
        obrigatoria=False,
        descricao="populacao total",
    )

    if pop_target_col is None and pop_total_col is None:
        raise ValueError("Nao foi possivel detectar populacao target nem populacao total.")

    df = df.copy()
    df["cod_setor"] = df[cod_setor_col].map(lambda valor: _normalizar_codigo(valor))
    if cod_municipio_col:
        df["cod_municipio"] = df[cod_municipio_col].map(lambda valor: _normalizar_codigo(valor, 7))
    else:
        df["cod_municipio"] = df["cod_setor"].str.slice(0, 7)
    df["renda_setor_2010"] = pd.to_numeric(df[renda_col], errors="coerce")
    df["pop_total_setor_2010"] = (
        pd.to_numeric(df[pop_total_col], errors="coerce") if pop_total_col else np.nan
    )
    df["pop_target_setor_2010"] = (
        pd.to_numeric(df[pop_target_col], errors="coerce") if pop_target_col else np.nan
    )
    df["pop_setor_2010"] = df["pop_target_setor_2010"].where(
        df["pop_target_setor_2010"].notna(),
        df["pop_total_setor_2010"],
    )
    df["fonte_renda"] = "ibge_setor_2010"
    df["fonte_pop"] = "ibge_setor_2010"
    df["pop_setor_2010_fallback"] = df["pop_target_setor_2010"].isna() & df["pop_total_setor_2010"].notna()

    colunas_utilizadas = {
        "cod_setor": cod_setor_col,
        "cod_municipio": cod_municipio_col or "derivado_do_cod_setor",
        "renda": renda_col,
        "pop_target": pop_target_col or "nao_encontrada",
        "pop_total": pop_total_col or "nao_encontrada",
    }
    descartadas = [
        coluna
        for coluna in df.columns
        if coluna not in {cod_setor_col, *(f for f in [cod_municipio_col, renda_col, pop_target_col, pop_total_col] if f)}
    ]

    df = (
        df[
            [
                "cod_setor",
                "cod_municipio",
                "renda_setor_2010",
                "pop_total_setor_2010",
                "pop_target_setor_2010",
                "pop_setor_2010",
                "fonte_renda",
                "fonte_pop",
                "pop_setor_2010_fallback",
            ]
        ]
        .dropna(subset=["cod_setor"])
        .drop_duplicates(subset=["cod_setor"])
        .reset_index(drop=True)
    )
    return df, {"colunas_utilizadas": colunas_utilizadas, "colunas_descartadas": descartadas}


def _descobrir_arquivo(root: Path, suffixes: set[str], palavras: Sequence[str]) -> Path:
    candidatos = [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in suffixes
    ]
    if not candidatos:
        raise FileNotFoundError(f"Nenhum arquivo encontrado em {root}")

    palavras_slug = tuple(_slug(palavra) for palavra in palavras)
    pontuados: list[tuple[int, Path]] = []
    for path in candidatos:
        nome = _slug(str(path.relative_to(root)))
        score = sum(1 for palavra in palavras_slug if palavra in nome)
        pontuados.append((score, path))
    pontuados.sort(key=lambda item: (-item[0], len(str(item[1]))))
    melhor_score, melhor_path = pontuados[0]
    if melhor_score == 0:
        raise FileNotFoundError(
            f"Nao foi possivel descobrir automaticamente o arquivo em {root}. "
            "Informe os caminhos explicitamente."
        )
    return melhor_path


def descobrir_insumos_setor_2010(
    *,
    setores_root: Path,
    geometria_path: Path | None = None,
    atributos_path: Path | None = None,
) -> tuple[Path, Path]:
    if geometria_path is None:
        geometria_path = _descobrir_arquivo(
            setores_root,
            SUPPORTED_GEOMETRY_SUFFIXES,
            ("setor", "2010", "malha"),
        )
    if atributos_path is None:
        atributos_path = _descobrir_arquivo(
            setores_root,
            SUPPORTED_TABLE_SUFFIXES,
            ("setor", "2010", "renda"),
        )
    return geometria_path, atributos_path


def _municipios_por_uf(municipios_root: Path, uf: str) -> pd.DataFrame:
    path = municipios_root / f"municipios_{uf.upper()}.geojson"
    if not path.exists():
        raise FileNotFoundError(f"Malha municipal da UF {uf} nao encontrada em {path}.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    registros = []
    for feature in payload.get("features", []):
        properties = feature.get("properties", {})
        codigo = None
        for chave in ("codarea", "id", "CD_MUN", "CD_MUN7", "code"):
            codigo = _normalizar_codigo(properties.get(chave), 7)
            if codigo:
                break
        nome = properties.get("nome") or properties.get("NM_MUN") or properties.get("name") or ""
        if codigo:
            registros.append({"cod_municipio": codigo, "nome_municipio": nome, "uf": uf.upper()})
    if not registros:
        raise ValueError(f"Nenhum municipio reconhecido na malha {path}.")
    df = pd.DataFrame(registros).drop_duplicates(subset=["cod_municipio"])
    df["nome_municipio_slug"] = df["nome_municipio"].map(_slug)
    return df


def resolver_cidades_alvo(
    cidades: Sequence[str] | None,
    *,
    municipios_root: Path = DEFAULT_MUNICIPIOS_ROOT,
) -> list[dict]:
    if not cidades:
        return [dict(item) for item in DEFAULT_CIDADES_ALVO]

    resolvidas: list[dict] = []
    cache_ufs: dict[str, pd.DataFrame] = {}
    for cidade in cidades:
        cidade = cidade.strip()
        codigo = _normalizar_codigo(cidade, 7)
        if codigo and len(codigo) == 7:
            resolvidas.append({"cidade": codigo, "uf": "", "cod_municipio": codigo})
            continue

        if "/" not in cidade:
            raise ValueError(
                f"Cidade invalida: {cidade}. Use o formato 'Nome/UF' ou codigo IBGE de 7 digitos."
            )
        nome, uf = cidade.rsplit("/", 1)
        uf = uf.strip().upper()
        nome_slug = _slug(nome)
        if uf not in cache_ufs:
            cache_ufs[uf] = _municipios_por_uf(municipios_root, uf)
        df_uf = cache_ufs[uf]
        match = df_uf[df_uf["nome_municipio_slug"] == nome_slug]
        if match.empty:
            raise ValueError(f"Municipio nao encontrado na UF {uf}: {cidade}")
        row = match.iloc[0]
        resolvidas.append(
            {
                "cidade": row["nome_municipio"],
                "uf": uf,
                "cod_municipio": row["cod_municipio"],
            }
        )

    return resolvidas


def carregar_base_oficial(path: Path) -> pd.DataFrame:
    colunas = [
        "hex_id",
        "lat",
        "lng",
        "uf",
        "regiao",
        "cod_municipio",
        "nome_municipio",
        "renda_per_capita",
        "pop_total",
        "pop_18_45",
        "populacao_proxy",
        "hex_score_estrutural",
        "score_priorizacao",
        "fonte_renda",
        "fonte_populacao",
    ]
    df = pd.read_parquet(path, columns=colunas)
    df = df.copy()
    df["cod_municipio"] = df["cod_municipio"].map(lambda valor: _normalizar_codigo(valor, 7))
    df["populacao_proxy"] = (
        pd.to_numeric(df["populacao_proxy"], errors="coerce")
        if "populacao_proxy" in df.columns
        else calcular_populacao_proxy(df)
    )
    df["nome_municipio"] = df["nome_municipio"].fillna("").astype(str)
    return df


def filtrar_base_oficial_por_cidades(df: pd.DataFrame, cidades_alvo: Sequence[dict]) -> pd.DataFrame:
    codigos = {item["cod_municipio"] for item in cidades_alvo}
    resultado = df[df["cod_municipio"].isin(codigos)].copy()
    if resultado.empty:
        raise ValueError("Nenhum hexagono encontrado na base oficial para as cidades alvo.")
    cidade_por_codigo = {item["cod_municipio"]: item.get("cidade") or item["cod_municipio"] for item in cidades_alvo}
    resultado["cidade"] = resultado["cod_municipio"].map(cidade_por_codigo).fillna(resultado["cod_municipio"])
    return resultado


def preparar_base_setores_2010(
    *,
    geometria_path: Path,
    atributos_path: Path,
    cidades_alvo: Sequence[dict],
) -> tuple[pd.DataFrame, dict]:
    df_geom = _carregar_geometrias_setor(geometria_path)
    df_attr, schema_info = _carregar_atributos_setor(atributos_path)
    df = df_geom.merge(df_attr, on=["cod_setor", "cod_municipio"], how="inner")
    if df.empty:
        raise ValueError("Join entre geometria e atributos de setor 2010 ficou vazio.")
    codigos = {item["cod_municipio"] for item in cidades_alvo}
    df = df[df["cod_municipio"].isin(codigos)].copy()
    if df.empty:
        raise ValueError("Nenhum setor 2010 encontrado para as cidades alvo.")

    cidade_por_codigo = {item["cod_municipio"]: item.get("cidade") or item["cod_municipio"] for item in cidades_alvo}
    df["cidade"] = df["cod_municipio"].map(cidade_por_codigo).fillna(df["cod_municipio"])
    df["fonte_geometria"] = "ibge_setor_2010"
    df["data_referencia"] = "censo_2010"
    info = {
        "total_setores": int(len(df)),
        "geometria_path": str(geometria_path),
        "atributos_path": str(atributos_path),
        "schema": schema_info,
    }
    return df.reset_index(drop=True), info


def _hex_geometry(hex_id: str) -> shapely.Polygon:
    boundary = h3.cell_to_boundary(hex_id)
    return shapely.Polygon([(lng, lat) for lat, lng in boundary])


def associar_hexagonos_a_setores(
    df_hex: pd.DataFrame,
    df_setores: pd.DataFrame,
) -> pd.DataFrame:
    setores = df_setores.reset_index(drop=True).copy()
    tree = STRtree(setores["geometry"].tolist())

    resultado = df_hex.reset_index(drop=True).copy()
    resultado["geometry_hex"] = resultado["hex_id"].map(_hex_geometry)
    centroides = shapely.centroid(resultado["geometry_hex"].tolist())
    pares = tree.query(centroides, predicate="within")

    idx_setor = np.full(len(resultado), -1, dtype=int)
    metodo = np.full(len(resultado), "sem_match_setor", dtype=object)
    status = np.full(len(resultado), "sem_match_setor", dtype=object)

    if pares.size:
        idx_setor[pares[0]] = pares[1]
        metodo[pares[0]] = "centroide_within"
        status[pares[0]] = "match_setor"

    faltantes = np.where(idx_setor < 0)[0]
    if len(faltantes):
        for idx in faltantes:
            candidatos = tree.query(resultado.at[idx, "geometry_hex"], predicate="intersects")
            if len(candidatos) == 0:
                continue
            hex_geom = resultado.at[idx, "geometry_hex"]
            melhor_idx = None
            melhor_area = -1.0
            for candidato in candidatos:
                area = float(hex_geom.intersection(setores.at[int(candidato), "geometry"]).area)
                if area > melhor_area:
                    melhor_area = area
                    melhor_idx = int(candidato)
            if melhor_idx is not None:
                idx_setor[idx] = melhor_idx
                metodo[idx] = "intersects_maior_area"
                status[idx] = "match_setor"

    colunas_setor = [
        "cod_setor",
        "cod_municipio",
        "cidade",
        "renda_setor_2010",
        "pop_setor_2010",
        "pop_total_setor_2010",
        "pop_target_setor_2010",
        "fonte_renda",
        "fonte_pop",
        "pop_setor_2010_fallback",
    ]
    preenchidos = pd.DataFrame(index=resultado.index, columns=colunas_setor, dtype=object)
    matched = idx_setor >= 0
    if matched.any():
        setores_match = setores.loc[idx_setor[matched], colunas_setor].reset_index(drop=True)
        setores_match.index = resultado.index[matched]
        preenchidos.loc[matched, colunas_setor] = setores_match

    resultado[colunas_setor] = preenchidos[colunas_setor]
    resultado["setor_match_status"] = status
    resultado["setor_match_metodo"] = metodo
    resultado["fonte_renda"] = np.where(
        resultado["setor_match_status"].eq("match_setor"),
        "ibge_setor_2010",
        pd.NA,
    )
    resultado["fonte_pop"] = np.where(
        resultado["setor_match_status"].eq("match_setor"),
        "ibge_setor_2010",
        pd.NA,
    )
    resultado["renda_setor_2010"] = pd.to_numeric(resultado["renda_setor_2010"], errors="coerce")
    resultado["pop_setor_2010"] = pd.to_numeric(resultado["pop_setor_2010"], errors="coerce")
    resultado["pop_total_setor_2010"] = pd.to_numeric(resultado["pop_total_setor_2010"], errors="coerce")
    resultado["pop_target_setor_2010"] = pd.to_numeric(resultado["pop_target_setor_2010"], errors="coerce")
    resultado["pop_setor_2010_fallback"] = resultado["pop_setor_2010_fallback"].map(
        lambda valor: bool(valor) if pd.notna(valor) else False
    )
    return resultado


def calcular_score_setor_2010(
    df_hex_setor: pd.DataFrame,
    base_nacional: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Calcula score censitario 2010.

    Variavel de renda: Basico V005 (rendimento medio do responsavel por domicilio).
    Limitacao documentada: nao e renda per capita domiciliar. Proxy derivado
    `renda_per_capita_setor_2010 = renda_setor_2010 / pop_total_setor_2010`
    e calculado como alternativa mais rigorosa quando pop_total_setor_2010 > 0.

    Percentis: calculados no subconjunto local por padrao.
    Quando `base_nacional` e fornecida, percentis sao ancorados na distribuicao
    nacional de renda_per_capita e populacao_proxy do M1 (comparabilidade nacional).

    Nota de governanca: `hex_score_estrutural` oficial nao e alterado.
    """
    df = df_hex_setor.copy()

    # Proxy de renda per capita: V005 / pop_total (onde disponivel)
    renda_v005 = pd.to_numeric(df.get("renda_setor_2010", pd.Series(dtype=float)), errors="coerce")
    pop_total = pd.to_numeric(df.get("pop_total_setor_2010", pd.Series(dtype=float)), errors="coerce")
    pop_valida = pop_total > 0
    df["renda_per_capita_setor_2010"] = np.where(
        pop_valida & renda_v005.notna(),
        (renda_v005 / pop_total).where(pop_valida),
        np.nan,
    )
    df["variante_renda_setor"] = np.where(
        pop_valida & renda_v005.notna(),
        "renda_per_capita_proxy_v005_por_pop_total",
        "renda_media_responsavel_v005",
    )

    # Percentis: local (padrao) ou ancorados na distribuicao nacional
    if base_nacional is not None and not base_nacional.empty:
        ref_renda = pd.to_numeric(base_nacional.get("renda_per_capita", pd.Series(dtype=float)), errors="coerce")
        ref_pop = pd.to_numeric(base_nacional.get("populacao_proxy", pd.Series(dtype=float)), errors="coerce")
        df["renda_pct_setor_2010"] = _percentil_em_distribuicao_referencia(renda_v005, ref_renda)
        df["pop_pct_setor_2010"] = _percentil_em_distribuicao_referencia(df["pop_setor_2010"], ref_pop)
        df["percentil_escopo"] = "nacional_m1"
    else:
        df["renda_pct_setor_2010"] = _calcular_percentil_nacional(renda_v005)
        df["pop_pct_setor_2010"] = _calcular_percentil_nacional(df["pop_setor_2010"])
        df["percentil_escopo"] = "local_subconjunto"

    mask = df["setor_match_status"].eq("match_setor") & renda_v005.notna() & df["pop_setor_2010"].notna()
    df["hex_score_setor_2010"] = np.nan
    if mask.any():
        df.loc[mask, "hex_score_setor_2010"] = (
            100
            * (
                0.60 * df.loc[mask, "renda_pct_setor_2010"]
                + 0.40 * df.loc[mask, "pop_pct_setor_2010"]
            )
        ).round(2)
    return df


def calcular_score_setor_ancorado(
    df: pd.DataFrame, peso_municipal: float = 0.60
) -> pd.DataFrame:
    """Score censal ancorado na posicao nacional do M1.

    Formula: score_setor_ancorado = peso_municipal * hex_score_estrutural
                                   + (1 - peso_municipal) * hex_score_setor_2010

    Raciocinio: preserva a posicao nacional do hexagono (hex_score_estrutural
    ja foi calculado com percentis nacionais no M1) e adiciona diferenciacao
    intraurbana via score local do setor 2010. Permite comparar hexagonos de
    diferentes cidades sem distorcoes de base local.

    Separacao canonica: nao substitui score_priorizacao oficial do M1.
    """
    df = df.copy()
    score_mun = pd.to_numeric(df.get("hex_score_estrutural", pd.Series(dtype=float)), errors="coerce")
    score_setor = pd.to_numeric(df.get("hex_score_setor_2010", pd.Series(dtype=float)), errors="coerce")
    mask = score_mun.notna() & score_setor.notna()
    df["score_setor_ancorado"] = np.nan
    if mask.any():
        df.loc[mask, "score_setor_ancorado"] = (
            peso_municipal * score_mun.loc[mask] + (1 - peso_municipal) * score_setor.loc[mask]
        ).clip(0, 100).round(2)
    df["score_setor_ancorado_peso_municipal"] = round(peso_municipal, 2)
    return df


def construir_comparativo(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    colunas_base = [
        "cidade",
        "uf",
        "cod_municipio",
        "hex_id",
        "hex_score_estrutural",
        "hex_score_setor_2010",
        "renda_setor_2010",
        "pop_setor_2010",
        "setor_match_status",
        "setor_match_metodo",
    ]
    colunas_extras = [c for c in ("score_setor_ancorado", "percentil_escopo", "variante_renda_setor") if c in df.columns]
    comparativo = df[colunas_base + colunas_extras].copy()
    comparativo["diferenca_score"] = (
        pd.to_numeric(comparativo["hex_score_setor_2010"], errors="coerce")
        - pd.to_numeric(comparativo["hex_score_estrutural"], errors="coerce")
    ).round(2)

    stats = []
    for cidade, grupo in comparativo.groupby("cidade", sort=True):
        score_oficial = pd.to_numeric(grupo["hex_score_estrutural"], errors="coerce")
        score_setor = pd.to_numeric(grupo["hex_score_setor_2010"], errors="coerce")
        cobertura = grupo["setor_match_status"].eq("match_setor")
        stats.append(
            {
                "cidade": cidade,
                "hex_total": int(len(grupo)),
                "hex_com_setor": int(cobertura.sum()),
                "cobertura_pct": round(float(cobertura.mean() * 100), 2),
                "score_oficial_distintos": int(score_oficial.nunique(dropna=True)),
                "score_setor_distintos": int(score_setor.nunique(dropna=True)),
                "score_oficial_std": round(float(score_oficial.std(ddof=0)), 2),
                "score_setor_std": round(float(score_setor.std(ddof=0)), 2) if score_setor.notna().any() else np.nan,
                "score_oficial_p95_p05": round(float(score_oficial.quantile(0.95) - score_oficial.quantile(0.05)), 2),
                "score_setor_p95_p05": (
                    round(float(score_setor.quantile(0.95) - score_setor.quantile(0.05)), 2)
                    if score_setor.notna().any()
                    else np.nan
                ),
            }
        )
    stats_df = pd.DataFrame(stats).sort_values("cidade").reset_index(drop=True)

    top_setor = (
        comparativo[comparativo["hex_score_setor_2010"].notna()]
        .sort_values(["cidade", "hex_score_setor_2010", "hex_score_estrutural", "hex_id"], ascending=[True, False, False, True])
        .groupby("cidade", sort=True, group_keys=False)
        .head(20)
        .reset_index(drop=True)
    )
    top_oficial = (
        comparativo.sort_values(["cidade", "hex_score_estrutural", "hex_id"], ascending=[True, False, True])
        .groupby("cidade", sort=True, group_keys=False)
        .head(20)
        .reset_index(drop=True)
    )
    top_comparativo = (
        top_setor[["cidade", "hex_id", "hex_score_setor_2010", "diferenca_score"]]
        .merge(
            top_oficial[["cidade", "hex_id", "hex_score_estrutural"]],
            on=["cidade", "hex_id"],
            how="outer",
        )
        .sort_values(["cidade", "hex_score_setor_2010", "hex_score_estrutural", "hex_id"], ascending=[True, False, False, True])
        .reset_index(drop=True)
    )
    return comparativo, stats_df, top_setor, top_comparativo


def _markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_sem dados_"
    tabela = df.copy()
    cabecalho = "| " + " | ".join(str(col) for col in tabela.columns) + " |"
    separador = "| " + " | ".join("---" for _ in tabela.columns) + " |"
    linhas = [cabecalho, separador]
    for row in tabela.itertuples(index=False):
        valores = []
        for valor in row:
            if pd.isna(valor):
                valores.append("")
            else:
                valores.append(str(valor))
        linhas.append("| " + " | ".join(valores) + " |")
    return "\n".join(linhas)


def gerar_relatorio_experimento(
    *,
    df_hex: pd.DataFrame,
    comparativo: pd.DataFrame,
    stats_df: pd.DataFrame,
    top_setor: pd.DataFrame,
    top_oficial: pd.DataFrame,
    info_setores: dict,
    cidades_alvo: Sequence[dict],
    tempo_spatial_join_s: float = 0.0,
) -> str:
    cobertura = comparativo["setor_match_status"].eq("match_setor")
    total_hex = int(len(comparativo))
    total_match = int(cobertura.sum())
    cobertura_pct = round(float(cobertura.mean() * 100), 2) if total_hex else 0.0
    cidades_label = ", ".join(f"{item['cidade']}/{item['uf'] or 'NA'}" for item in cidades_alvo)

    ganho_cidades = stats_df[
        stats_df["score_setor_distintos"].fillna(0) > stats_df["score_oficial_distintos"].fillna(0)
    ]["cidade"].tolist()
    plausibilidade = "parcial"
    if len(ganho_cidades) == len(stats_df) and not stats_df.empty:
        plausibilidade = "positiva"
    elif not ganho_cidades:
        plausibilidade = "inconclusiva"

    schema = info_setores["schema"]["colunas_utilizadas"]
    descartadas = info_setores["schema"]["colunas_descartadas"][:15]

    top10_oficial = (
        top_oficial.sort_values(["cidade", "hex_score_estrutural", "hex_id"], ascending=[True, False, True])
        .groupby("cidade", sort=True, group_keys=False)
        .head(10)
        .reset_index(drop=True)
    )
    top10_setor = (
        top_setor.sort_values(["cidade", "hex_score_setor_2010", "hex_id"], ascending=[True, False, True])
        .groupby("cidade", sort=True, group_keys=False)
        .head(10)
        .reset_index(drop=True)
    )

    # Score ancorado: disponivel apenas quando score_setor_ancorado esta no df
    tem_ancorado = "score_setor_ancorado" in df_hex.columns and df_hex["score_setor_ancorado"].notna().any()
    variante_renda = df_hex.get("variante_renda_setor", pd.Series(dtype=str)).mode()
    variante_renda_str = variante_renda.iloc[0] if not variante_renda.empty else "renda_media_responsavel_v005"
    percentil_escopo = df_hex.get("percentil_escopo", pd.Series(dtype=str)).mode()
    percentil_escopo_str = percentil_escopo.iloc[0] if not percentil_escopo.empty else "local_subconjunto"

    # Estimativa de custo computacional
    hex_por_segundo = total_hex / max(tempo_spatial_join_s, 0.01)
    hex_nacional_estimado = 215_000
    t_nacional_s = hex_nacional_estimado / max(hex_por_segundo, 1)
    t_nacional_min = round(t_nacional_s / 60, 1)

    linhas = [
        "# Teste Paralelo - Setor Censitario IBGE 2010",
        "",
        "## Escopo",
        f"- cidades testadas: {cidades_label}",
        "- resolucao H3: 7",
        f"- base oficial preservada: `{DEFAULT_BASE_OFICIAL_PATH}`",
        f"- geometria de setor: `{info_setores['geometria_path']}`",
        f"- atributos censitarios: `{info_setores['atributos_path']}`",
        "",
        "## Metodologia adotada",
        "",
        "### Variavel de renda",
        "- fonte primaria: Basico V005 (rendimento medio nominal mensal do responsavel por domicilio particular permanente)",
        "- limitacao documentada: V005 nao e renda per capita domiciliar; e a renda do chefe, nao dividida pelo numero de moradores",
        "- proxy derivado disponivel: `renda_per_capita_setor_2010 = V005 / pop_total_setor_2010` (calculado quando pop_total > 0)",
        f"- variante em uso neste experimento: `{variante_renda_str}`",
        "- decisao: para producao, definir fonte canonica de renda per capita por setor (ex: tabela Domicilio do Censo 2010, V005 ponderado por V001/V002, ou Censo 2022 quando disponivel por setor)",
        "",
        "### Comparabilidade com ranking nacional",
        f"- percentis calculados no escopo: `{percentil_escopo_str}`",
        "- problema: percentil local nao e diretamente comparavel com percentil nacional do M1",
        "- solucao implementada: `score_setor_ancorado = 0.60 * hex_score_estrutural + 0.40 * hex_score_setor_2010`",
        "  - hex_score_estrutural: ancora o hexagono na posicao nacional do M1 (percentil nacional ja calculado)",
        "  - hex_score_setor_2010: adiciona diferenciacao intraurbana via percentil local do setor 2010",
        "  - resultado: score comparavel entre cidades, com granularidade intraurbana preservada",
        "- alternativa futura: calcular percentis do setor contra distribuicao nacional via `_percentil_em_distribuicao_referencia()` (ja implementada no script)",
        "",
        "## Variaveis 2010 usadas",
        f"- codigo de setor: `{schema['cod_setor']}`",
        f"- codigo de municipio: `{schema['cod_municipio']}`",
        f"- renda: `{schema['renda']}`",
        f"- populacao target: `{schema['pop_target']}`",
        f"- populacao total fallback: `{schema['pop_total']}`",
        f"- colunas descartadas na leitura: {', '.join(f'`{col}`' for col in descartadas) if descartadas else 'nenhuma'}",
        "",
        "## Validacao objetiva",
        f"- hexagonos enriquecidos com setor 2010: {total_match} de {total_hex}",
        f"- cobertura espacial: {cobertura_pct:.2f}%",
        f"- houve ganho de diferenciacao intraurbana? {'sim' if ganho_cidades else 'nao ou inconclusivo'}",
        f"- cidades com aumento de valores distintos no score: {', '.join(ganho_cidades) if ganho_cidades else 'nenhuma'}",
        f"- o topo do ranking ficou mais plausivel? leitura {plausibilidade}",
        f"- custo spatial join (subconjunto {total_hex} hex): {tempo_spatial_join_s:.2f}s",
        "- vale evoluir para modulo oficial futuro? somente se bloqueadores canonicar forem resolvidos (ver secao de limitacoes)",
        "",
        "## Custo computacional estimado",
        f"- spatial join neste experimento: {tempo_spatial_join_s:.2f}s para {total_hex} hexagonos",
        f"- throughput medido: {hex_por_segundo:.0f} hexagonos/segundo",
        f"- hexagonos H3-r7 estimados no Brasil (com populacao): ~{hex_nacional_estimado:,}",
        f"- estimativa de tempo para escala nacional completa: ~{t_nacional_min} minutos (processamento sequencial por UF, sem paralelismo)",
        "- nota: estimativa assume mesma densidade de setores por hex; regioes rurais podem ser mais rapidas por menor numero de setores",
        "- recomendacao: avaliar paralelismo por UF e cache de STRtree antes de producao nacional",
        "",
        "## Metricas por cidade",
        _markdown_table(stats_df),
        "",
        "## Distribuicao de score",
        f"- score oficial atual: {resumir_distribuicao_score(pd.to_numeric(df_hex['hex_score_estrutural'], errors='coerce'))}",
        f"- score setor 2010 (local): {resumir_distribuicao_score(pd.to_numeric(df_hex['hex_score_setor_2010'], errors='coerce'))}",
    ]

    if tem_ancorado:
        linhas += [
            f"- score setor ancorado (60% mun + 40% setor): {resumir_distribuicao_score(pd.to_numeric(df_hex['score_setor_ancorado'], errors='coerce'))}",
        ]

    linhas += [
        "",
        "## Top 10 por cidade - modelo atual",
        _markdown_table(top10_oficial[["cidade", "hex_id", "hex_score_estrutural"]]),
        "",
        "## Top 10 por cidade - modelo censitario",
        _markdown_table(top10_setor[["cidade", "hex_id", "hex_score_setor_2010", "diferenca_score"]]),
    ]

    if tem_ancorado and "score_setor_ancorado" in comparativo.columns:
        top10_ancorado = (
            comparativo[comparativo["score_setor_ancorado"].notna()]
            .sort_values(["cidade", "score_setor_ancorado"], ascending=[True, False])
            .groupby("cidade", sort=True, group_keys=False)
            .head(10)
            .reset_index(drop=True)
        )
        colunas_ancorado = [c for c in ["cidade", "hex_id", "hex_score_estrutural", "score_setor_ancorado", "hex_score_setor_2010"] if c in top10_ancorado.columns]
        linhas += [
            "",
            "## Top 10 por cidade - score ancorado (60% municipal + 40% setor)",
            _markdown_table(top10_ancorado[colunas_ancorado]),
        ]

    linhas += [
        "",
        "## Limitacoes remanescentes",
        "- V005 nao e renda per capita domiciliar; necessario definir fonte canonica de renda por setor para producao",
        "- percentis locais incompativeis com ranking nacional do M1 (mitigado pelo score_setor_ancorado, mas nao eliminado)",
        "- custo computacional em escala nacional nao foi medido empiricamente (apenas estimado)",
        "- cobertura espacial pode cair em regioes com setores muito pequenos ou geometrias problematicas",
        "- fonte censitaria: Censo 2010 (defasagem de ~15 anos em relacao ao periodo de analise)",
        "",
        "## Observacoes",
        "- `hex_score_estrutural` oficial nao foi alterado.",
        "- hex sem setor permaneceram como `sem_match_setor`; nao houve preenchimento silencioso com zero.",
        "- `score_setor_ancorado` e experimental: nao substitui `score_priorizacao` oficial do M1.",
        "- o experimento usa percentis no subconjunto testado por padrao; `_percentil_em_distribuicao_referencia()` esta disponivel para ancoragem nacional futura.",
    ]
    return "\n".join(linhas) + "\n"


def executar_experimento_setor_2010(
    *,
    cidades_alvo: Sequence[dict] | None = None,
    base_oficial_path: Path = DEFAULT_BASE_OFICIAL_PATH,
    setores_root: Path = DEFAULT_SETORES_ROOT,
    geometria_path: Path | None = None,
    atributos_path: Path | None = None,
    staging_dir: Path = DEFAULT_STAGING_DIR,
    outputs_dir: Path = DEFAULT_OUTPUTS_DIR,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> dict:
    cidades_resolvidas = list(cidades_alvo or DEFAULT_CIDADES_ALVO)
    base_oficial = carregar_base_oficial(base_oficial_path)
    df_hex = filtrar_base_oficial_por_cidades(base_oficial, cidades_resolvidas)

    geometria_path, atributos_path = descobrir_insumos_setor_2010(
        setores_root=setores_root,
        geometria_path=geometria_path,
        atributos_path=atributos_path,
    )
    df_setores, info_setores = preparar_base_setores_2010(
        geometria_path=geometria_path,
        atributos_path=atributos_path,
        cidades_alvo=cidades_resolvidas,
    )
    t0_spatial = time.perf_counter()
    df_hex = associar_hexagonos_a_setores(df_hex, df_setores)
    tempo_spatial_join_s = round(time.perf_counter() - t0_spatial, 3)
    df_hex = calcular_score_setor_2010(df_hex, base_nacional=base_oficial)
    df_hex = calcular_score_setor_ancorado(df_hex)
    comparativo, stats_df, top_setor, top_comparativo = construir_comparativo(df_hex)
    top_oficial = (
        comparativo.sort_values(["cidade", "hex_score_estrutural", "hex_id"], ascending=[True, False, True])
        .groupby("cidade", sort=True, group_keys=False)
        .head(20)
        .reset_index(drop=True)
    )
    relatorio = gerar_relatorio_experimento(
        df_hex=df_hex,
        comparativo=comparativo,
        stats_df=stats_df,
        top_setor=top_setor,
        top_oficial=top_oficial,
        info_setores=info_setores,
        cidades_alvo=cidades_resolvidas,
        tempo_spatial_join_s=tempo_spatial_join_s,
    )

    staging_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    hex_path = staging_dir / "hexagonos_teste_setor_2010.parquet"
    comparativo_path = staging_dir / "comparativo_municipal_vs_setor_2010.parquet"
    top_setor_path = outputs_dir / "top_hexagonos_setor_2010.csv"
    top_comparativo_path = outputs_dir / "top_comparativo_por_cidade.csv"

    df_hex.drop(columns=["geometry_hex"], errors="ignore").to_parquet(hex_path, index=False)
    comparativo.to_parquet(comparativo_path, index=False)
    top_setor.to_csv(top_setor_path, index=False, sep=";", encoding="utf-8-sig")
    top_comparativo.to_csv(top_comparativo_path, index=False, sep=";", encoding="utf-8-sig")
    report_path.write_text(relatorio, encoding="utf-8")

    resultado = {
        "hex_path": str(hex_path),
        "comparativo_path": str(comparativo_path),
        "top_setor_path": str(top_setor_path),
        "top_comparativo_path": str(top_comparativo_path),
        "report_path": str(report_path),
        "total_hex": int(len(df_hex)),
        "hex_com_setor": int(df_hex["setor_match_status"].eq("match_setor").sum()),
        "tempo_spatial_join_s": tempo_spatial_join_s,
        "tem_score_ancorado": "score_setor_ancorado" in df_hex.columns,
    }
    log.info("teste_setor_2010_concluido", **resultado)
    return resultado


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Executa experimento paralelo com setor censitario IBGE 2010."
    )
    parser.add_argument(
        "--cidade",
        action="append",
        default=[],
        help="Cidade alvo no formato 'Nome/UF'. Repetir para varias cidades.",
    )
    parser.add_argument(
        "--base-oficial-path",
        default=str(DEFAULT_BASE_OFICIAL_PATH),
        help="Parquet oficial da Fase 1 usado como baseline e fonte dos hexagonos.",
    )
    parser.add_argument(
        "--municipios-root",
        default=str(DEFAULT_MUNICIPIOS_ROOT),
        help="Pasta com as malhas municipais por UF usadas para resolver Nome/UF em codigo IBGE.",
    )
    parser.add_argument(
        "--setores-root",
        default=str(DEFAULT_SETORES_ROOT),
        help="Pasta configuravel onde estao os insumos de setor 2010.",
    )
    parser.add_argument(
        "--setores-geometry-path",
        default="",
        help="Arquivo explicito da malha de setores 2010.",
    )
    parser.add_argument(
        "--setores-attributes-path",
        default="",
        help="Arquivo explicito da tabela de atributos censitarios 2010.",
    )
    parser.add_argument(
        "--staging-dir",
        default=str(DEFAULT_STAGING_DIR),
        help="Pasta de staging isolada do experimento.",
    )
    parser.add_argument(
        "--outputs-dir",
        default=str(DEFAULT_OUTPUTS_DIR),
        help="Pasta de outputs isolada do experimento.",
    )
    parser.add_argument(
        "--report-path",
        default=str(DEFAULT_REPORT_PATH),
        help="Caminho do relatorio Markdown do experimento.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    cidades = resolver_cidades_alvo(
        args.cidade,
        municipios_root=Path(args.municipios_root),
    )
    executar_experimento_setor_2010(
        cidades_alvo=cidades,
        base_oficial_path=Path(args.base_oficial_path),
        setores_root=Path(args.setores_root),
        geometria_path=Path(args.setores_geometry_path) if args.setores_geometry_path else None,
        atributos_path=Path(args.setores_attributes_path) if args.setores_attributes_path else None,
        staging_dir=Path(args.staging_dir),
        outputs_dir=Path(args.outputs_dir),
        report_path=Path(args.report_path),
    )


if __name__ == "__main__":
    main()
