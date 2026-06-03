"""
Base nacional H3 do Brasil (resolucao 7) pronta para enriquecimento da Fase 1.

Fluxo:
1. Baixa ou reutiliza a malha oficial do IBGE por UF.
2. Gera os candidatos H3 de cada UF por containment OVERLAP (BLK-FIX-06-B): inclui
   as celulas que SOBREPOEM o poligono da UF, nao so as de centro dentro. Sem isso,
   a orla de centroide-no-mar nunca era candidata e o filtro de fracao-de-terra do
   BLK-FIX-06 nao a alcancava (a orla povoada continuava recortada).
3. Criterio HIBRIDO (BLK-FIX-06 / DEC-002, limiar aprovado 0.20): mantem hexagonos
   cujo CENTROIDE esta dentro do Brasil (fast path) OU, para os de centroide fora,
   cujo poligono sobrepoe terra em fracao de area >= settings.M1_HEX_LAND_FRACTION_MIN
   (recupera costeiros povoados, ex.: orla de Mongagua/SP `87a810998ffffff`,
   Praia Grande/SP `87a810c02ffffff`). Hexes em mar aberto (fracao < limiar) continuam
   descartados. Substitui o antigo filtro de centroide puro, que recortava o litoral.
4. Salva parquet particionado por UF em data/staging/brasil/uf=XX/hexagonos.parquet.
5. Gera relatorio curto de execucao em data/reports/base_h3_brasil.md.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

import h3
import pandas as pd
import requests
import shapely
from shapely.geometry import Polygon, shape

from motor_expansao.config import settings

IBGE_MALHAS_UF_URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
    "?formato=application/vnd.geo+json&intrarregiao=UF&qualidade=maxima"
)
IBGE_MALHA_BRASIL_URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
    "?formato=application/vnd.geo+json&qualidade=maxima"
)

UF_POR_CODAREA = {
    "11": "RO",
    "12": "AC",
    "13": "AM",
    "14": "RR",
    "15": "PA",
    "16": "AP",
    "17": "TO",
    "21": "MA",
    "22": "PI",
    "23": "CE",
    "24": "RN",
    "25": "PB",
    "26": "PE",
    "27": "AL",
    "28": "SE",
    "29": "BA",
    "31": "MG",
    "32": "ES",
    "33": "RJ",
    "35": "SP",
    "41": "PR",
    "42": "SC",
    "43": "RS",
    "50": "MS",
    "51": "MT",
    "52": "GO",
    "53": "DF",
}

REGIAO_POR_UF = {
    "AC": "N",
    "AL": "NE",
    "AM": "N",
    "AP": "N",
    "BA": "NE",
    "CE": "NE",
    "DF": "CO",
    "ES": "SE",
    "GO": "CO",
    "MA": "NE",
    "MG": "SE",
    "MS": "CO",
    "MT": "CO",
    "PA": "N",
    "PB": "NE",
    "PE": "NE",
    "PI": "NE",
    "PR": "S",
    "RJ": "SE",
    "RN": "NE",
    "RO": "N",
    "RR": "N",
    "RS": "S",
    "SC": "S",
    "SE": "NE",
    "SP": "SE",
    "TO": "N",
}

COLUNAS_SAIDA = ["hex_id", "lat", "lng", "uf", "regiao"]


@dataclass
class UFMetrica:
    uf: str
    regiao: str
    candidatos: int
    validos: int
    removidos: int
    recuperados_costeiros: int
    tempo_s: float
    null_hex_id: int
    null_lat: int
    null_lng: int
    null_uf: int


def _chunks(values: list[str], chunk_size: int) -> Iterator[list[str]]:
    for start in range(0, len(values), chunk_size):
        yield values[start : start + chunk_size]


def _hex_polygon(hex_id: str) -> Polygon:
    return Polygon((lng, lat) for lat, lng in h3.cell_to_boundary(hex_id))


def _download_geojson(url: str, cache_path: Path, timeout: int = 120) -> dict:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return payload


def carregar_geojson(url: str, cache_path: Path, refresh: bool = False) -> dict:
    if cache_path.exists() and not refresh:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    return _download_geojson(url=url, cache_path=cache_path)


def normalizar_features_uf(payload: dict) -> list[dict]:
    features = payload.get("features", [])
    if len(features) != 27:
        raise ValueError(f"Malha IBGE invalida: esperado 27 features, recebido {len(features)}")

    normalizadas = []
    for feature in features:
        codarea = feature["properties"]["codarea"]
        uf = UF_POR_CODAREA.get(codarea)
        if not uf:
            raise ValueError(f"UF desconhecida para codarea={codarea}")
        normalizadas.append(
            {
                "uf": uf,
                "regiao": REGIAO_POR_UF[uf],
                "geometry": feature["geometry"],
            }
        )
    return sorted(normalizadas, key=lambda item: item["uf"])


def construir_geometria_brasil(payload_brasil: dict):
    features = payload_brasil.get("features", [])
    if len(features) != 1:
        raise ValueError(f"Malha do Brasil invalida: esperado 1 feature, recebido {len(features)}")
    return shape(features[0]["geometry"])


def _gerar_candidatos_uf(geometry: dict, resolucao: int) -> list[str]:
    """Candidatos H3 da UF por containment OVERLAP (BLK-FIX-06-B).

    `h3.geo_to_cells` (polyfill por CENTRO) so produz hexes cujo centroide cai
    dentro do poligono de terra da UF; hexes da orla com centroide no mar NUNCA
    eram candidatos, entao o filtro de fracao-de-terra do BLK-FIX-06 nunca os
    avaliava (orla povoada ficava de fora). `overlap` inclui as celulas que
    SOBREPOEM o poligono (borda costeira); o filtro de fracao-de-terra depois
    mantem so as que tem >= M1_HEX_LAND_FRACTION_MIN de terra. O interior nao
    muda (overlap e superconjunto de center). Fallback robusto a versao do h3:
    centro + anel de borda (grid_disk k=1), que tambem inclui a orla adjacente.
    """
    shape_uf = h3.geo_to_h3shape(geometry)
    try:
        cells = h3.h3shape_to_cells_experimental(shape_uf, resolucao, "overlap")
    except (AttributeError, TypeError, ValueError):
        center = list(h3.geo_to_cells(geometry, resolucao))
        candidatos = set(center)
        for cell in center:
            candidatos.update(h3.grid_disk(cell, 1))
        cells = candidatos
    # Dedup: overlap sobre UF multipolygon (continente + ilhas) pode repetir celulas.
    return list(dict.fromkeys(cells))


def _fracao_terra_hex(hex_id: str, land_geom) -> float:
    """Fracao da area do poligono do hex que sobrepoe `land_geom` (terra).

    `land_geom` e o poligono de terra de referencia — na recuperacao costeira do
    BLK-FIX-06-B passamos o poligono da PROPRIA UF (atribuicao correta na borda
    litoranea entre estados), nao o Brasil inteiro.

    Razao de areas em graus (CRS WGS84/EPSG:4674, consistente com a malha IBGE).
    Para celulas H3 res 7 (pequenas e adjacentes) a razao e aproximadamente
    invariante a projecao; evita reprojetar centenas de milhares de poligonos.
    """
    hex_poly = _hex_polygon(hex_id)
    area_hex = hex_poly.area
    if area_hex <= 0:
        return 0.0
    inter = land_geom.intersection(hex_poly)
    return float(inter.area / area_hex)


def gerar_hexagonos_validos_uf(
    feature_uf: dict,
    brasil_geom,
    resolucao: int,
    chunk_size: int = 50_000,
    land_fraction_min: float | None = None,
    coletar_fracao_terra: bool = False,
) -> tuple[list[str], int, int, list[tuple[str, float]]]:
    """Gera os hexagonos validos de uma UF pelo criterio HIBRIDO (BLK-FIX-06 / 06-B).

    Candidatos por containment OVERLAP (`_gerar_candidatos_uf`), entao classifica
    cada hex pelo seu CENTROIDE para atribuir a UF correta (sem duplicar entre UFs):

    1. FAST PATH: centroide dentro DESTA UF -> mantido (pertence a ela).
    2. Centroide em terra do Brasil mas fora desta UF -> IGNORADO aqui (pertence a UF
       vizinha, que o reivindica pelo proprio centro). Evita duplicata entre UFs.
    3. Centroide NO MAR -> recuperacao costeira: constroi o poligono do hex e calcula a
       fracao de area sobre terra (Brasil); MANTEM se fracao >= land_fraction_min. Hexes
       de mar na fronteira entre duas UFs costeiras podem ser recuperados por ambas; o
       dedup nacional em `executar_base_h3_brasil` garante hex unico por base.

    A interseccao poligono x poligono so e calculada para os hexes de centroide no mar.

    Retorna `(validos, removidos, recuperados_costeiros, fracao_terra_vec)`:
      - `removidos`: hexes de centroide no mar com fracao < limiar (mar aberto).
      - `recuperados_costeiros`: hexes de centroide no mar mantidos pela fracao de terra.
      - `fracao_terra_vec`: quando `coletar_fracao_terra=True`, lista de
        `(hex_id, fracao_terra)` dos hexes de centroide no mar que sobrepoem terra
        (fracao > 0), para re-filtragem barata por limiar. Vazia caso contrario.
    """
    if land_fraction_min is None:
        land_fraction_min = settings.M1_HEX_LAND_FRACTION_MIN
    # BLK-FIX-06-B: candidatos por OVERLAP (nao por centro) para a orla de
    # centroide-no-mar entrar na avaliacao de fracao-de-terra.
    candidatos = _gerar_candidatos_uf(feature_uf["geometry"], resolucao)
    uf_geom = shape(feature_uf["geometry"])

    validos: list[str] = []
    removidos = 0
    recuperados_costeiros = 0
    fracao_terra_vec: list[tuple[str, float]] = []
    for chunk in _chunks(candidatos, chunk_size):
        lats_lngs = [h3.cell_to_latlng(hex_id) for hex_id in chunk]
        chunk_centroids = shapely.points(
            [lng for lat, lng in lats_lngs],
            [lat for lat, lng in lats_lngs],
        )
        in_uf = shapely.intersects(uf_geom, chunk_centroids)
        in_brasil = shapely.intersects(brasil_geom, chunk_centroids)
        for hex_id, c_uf, c_br in zip(chunk, in_uf, in_brasil, strict=True):
            if c_uf:
                validos.append(hex_id)  # fast path: pertence a esta UF
                continue
            if c_br:
                continue  # centroide em UF vizinha -> evita duplicata entre UFs
            # Centroide no mar: recuperacao costeira (fracao sobre terra do Brasil).
            fracao_terra = _fracao_terra_hex(hex_id, brasil_geom)
            if coletar_fracao_terra and fracao_terra > 0.0:
                fracao_terra_vec.append((hex_id, fracao_terra))
            if fracao_terra >= land_fraction_min:
                validos.append(hex_id)
                recuperados_costeiros += 1
            else:
                removidos += 1
    return validos, removidos, recuperados_costeiros, fracao_terra_vec


def montar_dataframe_hexagonos(hex_ids: list[str], uf: str, regiao: str) -> pd.DataFrame:
    registros = []
    for hex_id in hex_ids:
        lat, lng = h3.cell_to_latlng(hex_id)
        registros.append(
            {
                "hex_id": hex_id,
                "lat": lat,
                "lng": lng,
                "uf": uf,
                "regiao": regiao,
            }
        )

    df = pd.DataFrame(registros, columns=COLUNAS_SAIDA)
    if not df.empty:
        df = df.sort_values("hex_id").reset_index(drop=True)
    return df


def validar_dataframe_hexagonos(df: pd.DataFrame) -> dict[str, int]:
    return {
        "null_hex_id": int(df["hex_id"].isna().sum()),
        "null_lat": int(df["lat"].isna().sum()),
        "null_lng": int(df["lng"].isna().sum()),
        "null_uf": int(df["uf"].isna().sum()),
    }


def salvar_particao_uf(df: pd.DataFrame, output_root: Path, uf: str) -> Path:
    target_dir = output_root / f"uf={uf}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "hexagonos.parquet"
    df.to_parquet(target_path, index=False)
    return target_path


def gerar_relatorio(
    metricas: list[UFMetrica],
    output_path: Path,
    resolucao: int,
    tempo_execucao_s: float,
    problemas: list[str],
    cache_path_uf: Path,
    cache_path_brasil: Path,
) -> None:
    total_hexagonos = sum(item.validos for item in metricas)
    linhas = [
        "# Base H3 Brasil",
        "",
        f"- Data de execucao: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Resolucao H3: {resolucao}",
        f"- Total de hexagonos: {total_hexagonos}",
        f"- Tempo de execucao: {tempo_execucao_s:.1f}s",
        f"- Fonte malha UFs IBGE: {IBGE_MALHAS_UF_URL}",
        f"- Cache malha UFs: {cache_path_uf}",
        f"- Fonte malha Brasil IBGE: {IBGE_MALHA_BRASIL_URL}",
        f"- Cache malha Brasil: {cache_path_brasil}",
        "",
        "## Distribuicao por UF",
        "",
        "| UF | Regiao | Hexagonos | Removidos | Recuperados costeiros | Tempo (s) |",
        "|----|--------|-----------|-----------|-----------------------|-----------|",
    ]

    for item in metricas:
        linhas.append(
            f"| {item.uf} | {item.regiao} | {item.validos} | {item.removidos} "
            f"| {item.recuperados_costeiros} | {item.tempo_s:.1f} |"
        )

    linhas.extend(
        [
            "",
            "## Problemas encontrados",
            "",
        ]
    )

    if problemas:
        linhas.extend(f"- {problema}" for problema in problemas)
    else:
        linhas.append("- Nenhum problema bloqueante.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def executar_base_h3_brasil(
    resolucao: int = settings.H3_RESOLUTION,
    cache_path_uf: Path | None = None,
    cache_path_brasil: Path | None = None,
    output_root: Path | None = None,
    report_path: Path | None = None,
    refresh_malha: bool = False,
) -> dict:
    cache_path_uf = cache_path_uf or Path("data/raw/ibge/malha_uf_brasil.geojson")
    cache_path_brasil = cache_path_brasil or Path("data/raw/ibge/malha_brasil.geojson")
    output_root = output_root or Path("data/staging/brasil")
    report_path = report_path or Path("data/reports/base_h3_brasil.md")

    started_at = time.time()
    payload_uf = carregar_geojson(
        url=IBGE_MALHAS_UF_URL,
        cache_path=cache_path_uf,
        refresh=refresh_malha,
    )
    payload_brasil = carregar_geojson(
        url=IBGE_MALHA_BRASIL_URL,
        cache_path=cache_path_brasil,
        refresh=refresh_malha,
    )
    features_uf = normalizar_features_uf(payload_uf)
    brasil_geom = construir_geometria_brasil(payload_brasil)

    metricas: list[UFMetrica] = []
    problemas: list[str] = []
    hexes_vistos: set[str] = set()
    total_duplicados_dedup = 0

    for feature_uf in features_uf:
        uf_started_at = time.time()
        hex_ids_validos, removidos, recuperados_costeiros, _ = gerar_hexagonos_validos_uf(
            feature_uf=feature_uf,
            brasil_geom=brasil_geom,
            resolucao=resolucao,
        )
        df_uf = montar_dataframe_hexagonos(
            hex_ids=hex_ids_validos,
            uf=feature_uf["uf"],
            regiao=feature_uf["regiao"],
        )
        # BLK-FIX-06-B: dedup. Um hex pode repetir DENTRO da UF (overlap sobre
        # multipolygon) ou ser recuperado por >1 UF costeira (mar em fronteira). Garante
        # hex unico por base; em duplicata entre UFs, fica na 1a processada (alfabetica).
        if not df_uf.empty:
            antes = len(df_uf)
            if hexes_vistos:
                df_uf = df_uf[~df_uf["hex_id"].isin(hexes_vistos)]
            df_uf = df_uf.drop_duplicates("hex_id").reset_index(drop=True)
            total_duplicados_dedup += antes - len(df_uf)
        hexes_vistos.update(df_uf["hex_id"].tolist())
        validacao = validar_dataframe_hexagonos(df_uf)
        salvar_particao_uf(df=df_uf, output_root=output_root, uf=feature_uf["uf"])

        metrica = UFMetrica(
            uf=feature_uf["uf"],
            regiao=feature_uf["regiao"],
            candidatos=len(hex_ids_validos) + removidos,
            validos=len(df_uf),
            removidos=removidos,
            recuperados_costeiros=recuperados_costeiros,
            tempo_s=round(time.time() - uf_started_at, 2),
            **validacao,
        )
        metricas.append(metrica)

        if any(validacao.values()):
            problemas.append(f"{feature_uf['uf']}: nulls detectados apos geracao {validacao}.")

    total_hexagonos = sum(item.validos for item in metricas)
    total_removidos = sum(item.removidos for item in metricas)
    total_recuperados_costeiros = sum(item.recuperados_costeiros for item in metricas)
    total_nulls = {
        "hex_id": sum(item.null_hex_id for item in metricas),
        "lat": sum(item.null_lat for item in metricas),
        "lng": sum(item.null_lng for item in metricas),
        "uf": sum(item.null_uf for item in metricas),
    }

    if total_nulls != {"hex_id": 0, "lat": 0, "lng": 0, "uf": 0}:
        raise ValueError(f"Base H3 invalida: nulls criticos detectados {total_nulls}")

    if total_removidos:
        ufs_com_remocao = sum(1 for item in metricas if item.removidos > 0)
        problemas.insert(
            0,
            (
                f"{total_removidos} hexagonos sem centroide no Brasil removidos "
                f"(centroide em mar/fronteira, fracao de terra < "
                f"{settings.M1_HEX_LAND_FRACTION_MIN}) em {ufs_com_remocao} UFs."
            ),
        )

    if total_recuperados_costeiros:
        ufs_com_recuperacao = sum(1 for item in metricas if item.recuperados_costeiros > 0)
        problemas.insert(
            0,
            (
                f"{total_recuperados_costeiros} hexagonos costeiros recuperados "
                f"(centroide fora mas fracao de terra >= "
                f"{settings.M1_HEX_LAND_FRACTION_MIN}) em {ufs_com_recuperacao} UFs."
            ),
        )

    if total_duplicados_dedup:
        problemas.insert(
            0,
            (
                f"{total_duplicados_dedup} hexagonos de mar duplicados entre UFs costeiras "
                "removidos pelo dedup nacional (cada hex fica na 1a UF processada)."
            ),
        )

    gerar_relatorio(
        metricas=metricas,
        output_path=report_path,
        resolucao=resolucao,
        tempo_execucao_s=time.time() - started_at,
        problemas=problemas,
        cache_path_uf=cache_path_uf,
        cache_path_brasil=cache_path_brasil,
    )

    return {
        "total_hexagonos": total_hexagonos,
        "total_removidos": total_removidos,
        "total_recuperados_costeiros": total_recuperados_costeiros,
        "land_fraction_min": settings.M1_HEX_LAND_FRACTION_MIN,
        "tempo_execucao_s": round(time.time() - started_at, 2),
        "metricas": [asdict(item) for item in metricas],
        "report_path": str(report_path),
        "output_root": str(output_root),
        "cache_path_uf": str(cache_path_uf),
        "cache_path_brasil": str(cache_path_brasil),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera a base nacional H3 do Brasil.")
    parser.add_argument("--resolucao", type=int, default=settings.H3_RESOLUTION)
    parser.add_argument("--refresh-malha", action="store_true")
    args = parser.parse_args()

    resultado = executar_base_h3_brasil(
        resolucao=args.resolucao,
        refresh_malha=args.refresh_malha,
    )
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
