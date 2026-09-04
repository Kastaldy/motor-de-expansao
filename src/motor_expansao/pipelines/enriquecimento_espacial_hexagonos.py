"""
Bloco 3 - Enriquecimento espacial por hexagono.

Calcula distancias e contagens entre hexes, concorrentes e unidades Ultra.
Saida: data/staging/hexagonos_mercado_mapeado.parquet (base para o Bloco 4)

Nao altera nenhum artefato oficial do M1.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

ROOT = Path(__file__).resolve().parents[3]

HIBRIDO_PATH = ROOT / "data" / "outputs" / "oportunidades_expansao_hibrido.parquet"
ESTRUTURAL_PATH = ROOT / "data" / "staging" / "brasil_estrutural.parquet"
CONCORRENTES_PATH = ROOT / "data" / "staging" / "concorrentes_mapeados.parquet"
# DEC-048: unidades de REDE vistas pelo agregador. OPCIONAL — ausente, o universo de cadeia
# fica so' com o cadastro e o artefato sai IDENTICO ao de antes.
REDES_AGREGADOR_PATH = ROOT / "data" / "staging" / "vulnerabilidade_ma_redes.parquet"
ULTRA_PATH = ROOT / "data" / "staging" / "unidades_ultra_mapeadas.parquet"
OUT_PATH = ROOT / "data" / "staging" / "hexagonos_mercado_mapeado.parquet"

EARTH_RADIUS_M = 6_371_000.0
RADIUS_1KM_RAD = 1_000.0 / EARTH_RADIUS_M
RADIUS_2KM_RAD = 2_000.0 / EARTH_RADIUS_M
CHUNK_SIZE = 100_000
# DEC-048: unidades de REDE que o agregador lista e o cadastro nao tem. A dedup e' a da
# DEC-034 -- casar a rede ate' 150 m salva concorrente real que a distancia pura apagaria;
# o piso de 50 m recupera endereco igual com slug divergente.
DEDUP_CADEIA_REDE_M = 150.0
DEDUP_CADEIA_COORD_M = 50.0


def _knn_dist_m(
    hex_coords_rad: np.ndarray,
    ref_coords_rad: np.ndarray,
    chunk: int = 200_000,
) -> np.ndarray:
    """Distance (metres) from each hex centroid to the nearest point in ref_coords_rad."""
    tree = BallTree(ref_coords_rad, metric="haversine")
    n = len(hex_coords_rad)
    result = np.empty(n, dtype=np.float64)
    for start in range(0, n, chunk):
        end = min(start + chunk, n)
        dists_rad, _ = tree.query(hex_coords_rad[start:end], k=1)
        result[start:end] = dists_rad[:, 0] * EARTH_RADIUS_M
    return result


def _coords_rad(df: pd.DataFrame) -> np.ndarray:
    """(lat, lng) em radianos, como float64 puro.

    NAO usar `df[["lat","lng"]].values` direto: o artefato do agregador guarda as coordenadas em
    `Float64` NULLABLE (dtype de extensao do pandas), e `.values` sobre DUAS colunas dessas
    devolve um array `object` -- ai `np.radians` levanta
    `loop of ufunc does not support argument 0 of type float`. `pd.to_numeric` NAO resolve:
    ele preserva o dtype de extensao. O `astype("float64")` e' que materializa o array real.
    `concorrentes_mapeados` guarda float64 puro e por isso nunca sofreu disso.
    """
    return np.radians(df[["lat", "lng"]].astype("float64").values)


def unir_cadeias(df_comp: pd.DataFrame, df_redes: pd.DataFrame | None) -> pd.DataFrame:
    """Universo de CADEIA = mapeadas validas + as do agregador que ainda nao estao la'.

    O feed do agregador lista 2.844 unidades de REDE. Medido contra `concorrentes_mapeados`:
    1.673 sao a MESMA academia ja' contada e 1.171 NAO estao no cadastro -- Panobianco (130),
    Selfit (130), SkyFit (96), Bluefit (49) e outras. Elas existem, disputam o mesmo aluno e
    nao pressionavam ninguem: a oferta instalada de cadeia estava **36,8% subestimada**.

    Elas entram no MESMO universo, e nao num termo paralelo, porque sao a mesma coisa: unidade
    de rede, com a mesma capacidade de clube. Fosse um termo separado, `flag_white_space_2km`,
    `gap_competitivo_2km` e a contagem exibida continuariam mentindo -- so' o residual ficaria
    certo. Como a capacidade e' identica, `oferta_consumida_mercado_estimada / 2500` segue
    devolvendo a CONTAGEM correta; nao ha unidade mista aqui.

    Dedup pela regra da DEC-034: `(mesma rede E d <= 150 m) OU (d <= 50 m)`. Casar a rede salva
    concorrente real que a distancia pura apagaria; o piso de 50 m recupera endereco igual com
    slug divergente.

    `df_redes=None` (artefato ausente) devolve so' as mapeadas -- comportamento anterior,
    bit a bit.
    """
    comp_ok = df_comp[df_comp["status_registro"] == "valido"].copy()
    for col in ("lat", "lng"):
        comp_ok[col] = pd.to_numeric(comp_ok[col], errors="coerce")
    comp_ok = comp_ok.dropna(subset=["lat", "lng"]).reset_index(drop=True)
    if df_redes is None or df_redes.empty:
        return comp_ok

    redes = df_redes.copy()
    for col in ("lat", "lng"):
        redes[col] = pd.to_numeric(redes[col], errors="coerce")
    redes = redes.dropna(subset=["lat", "lng"])
    # Segunda checagem de vazio, DEPOIS do dropna: a primeira olha o frame cru. Um feed em que
    # todas as coordenadas sao nulas chega aqui nao-vazio e sai vazio -- e `query_radius` sobre
    # zero linhas LEVANTA no sklearn, derrubando o pipeline inteiro por um insumo degradado.
    if redes.empty:
        return comp_ok
    # Ordem estavel antes da dedup: sem isso, qual duplicata sobrevive dependeria da ordem do
    # arquivo, e a contagem publicada mudaria de uma safra para outra sem ninguem mexer em nada.
    chaves = [c for c in ("chave_snapshot", "nome") if c in redes.columns]
    if chaves:
        redes = redes.sort_values(chaves, kind="stable")
    redes = redes.reset_index(drop=True)

    tree = BallTree(_coords_rad(comp_ok), metric="haversine")
    idxs, dists = tree.query_radius(
        _coords_rad(redes),
        r=DEDUP_CADEIA_REDE_M / EARTH_RADIUS_M,
        return_distance=True,
        sort_results=False,
    )
    rede_comp = comp_ok["rede"].astype(str).to_numpy()
    rede_feed = redes["rede"].astype(str).to_numpy()
    nova = np.ones(len(redes), dtype=bool)
    for i, (ii, dd) in enumerate(zip(idxs, dists, strict=False)):
        if len(ii) == 0:
            continue
        dm = dd * EARTH_RADIUS_M
        if (dm <= DEDUP_CADEIA_COORD_M).any() or (
            (rede_comp[ii] == rede_feed[i]) & (dm <= DEDUP_CADEIA_REDE_M)
        ).any():
            nova[i] = False

    novas = redes.loc[nova].copy()
    novas["status_registro"] = "valido"
    colunas = ["rede", "lat", "lng", "status_registro"]
    unido = pd.concat([comp_ok[colunas], novas[colunas]], ignore_index=True)
    # float64 PURO na saida, e nao `Float64` nullable. O cadastro guarda float64 e o feed do
    # agregador guarda nullable; o `concat` dos dois promove a coluna para nullable, e
    # `calc_comp_metrics` -- que consome este frame -- faz `.values` direto sobre as duas
    # colunas, o que sobre nullable devolve `object` e derruba o `np.radians`.
    # Sanear na FRONTEIRA de saida, e nao no consumidor: quem recebe este frame tem direito
    # de assumir coordenada numerica de verdade. (Encontrado ao rodar o pipeline real: os
    # testes passavam porque exercitavam `unir_cadeias` isolada, sem a funcao a jusante.)
    for col in ("lat", "lng"):
        unido[col] = unido[col].astype("float64")
    return unido.reset_index(drop=True)


def calc_comp_metrics(
    hex_coords_rad: np.ndarray,
    df_comp: pd.DataFrame,
) -> dict:
    comp_valid = df_comp[df_comp["status_registro"] == "valido"].reset_index(drop=True)
    comp_coords_rad = np.radians(comp_valid[["lat", "lng"]].values)

    is_smart = (comp_valid["rede"] == "smart_fit").values
    is_blue = (comp_valid["rede"] == "bluefit").values
    is_pano = (comp_valid["rede"] == "panobianco").values

    n = len(hex_coords_rad)
    tree = BallTree(comp_coords_rad, metric="haversine")

    n_1km = np.zeros(n, dtype=np.int32)
    n_2km = np.zeros(n, dtype=np.int32)
    n_smart = np.zeros(n, dtype=np.int32)
    n_blue = np.zeros(n, dtype=np.int32)
    n_pano = np.zeros(n, dtype=np.int32)
    oferta_1km = np.zeros(n, dtype=np.float64)
    oferta_2km = np.zeros(n, dtype=np.float64)

    n_chunks = (n - 1) // CHUNK_SIZE + 1
    print(f"  Contagens e pesos ({n:,} hexes, {n_chunks} chunks)...")
    for ci, start in enumerate(range(0, n, CHUNK_SIZE)):
        end = min(start + CHUNK_SIZE, n)
        indices, dists_rad = tree.query_radius(
            hex_coords_rad[start:end],
            r=RADIUS_2KM_RAD,
            return_distance=True,
            sort_results=False,
        )
        for i, (idxs, dr) in enumerate(zip(indices, dists_rad, strict=False)):
            if len(idxs) == 0:
                continue
            gi = start + i
            dm = dr * EARTH_RADIUS_M

            n_2km[gi] = len(idxs)
            mask_1 = dm <= 1000.0
            n_1km[gi] = int(mask_1.sum())

            sm = is_smart[idxs]
            bm = is_blue[idxs]
            pm = is_pano[idxs]
            n_smart[gi] = int(sm.sum())
            n_blue[gi] = int(bm.sum())
            n_pano[gi] = int(pm.sum())

            w2 = np.maximum(0.0, 1.0 - dm / 2000.0)
            oferta_2km[gi] = w2.sum()
            if mask_1.any():
                oferta_1km[gi] = np.maximum(0.0, 1.0 - dm[mask_1] / 1000.0).sum()

        if ci % 5 == 0:
            print(f"    chunk {ci + 1}/{n_chunks}")

    # Distancias minimas globais via k=1
    print("  Distancias minimas (k=1)...")
    dist_comp_min = _knn_dist_m(hex_coords_rad, comp_coords_rad)
    dist_smart_min = _knn_dist_m(
        hex_coords_rad,
        np.radians(comp_valid.loc[is_smart, ["lat", "lng"]].values),
    ) if is_smart.any() else np.full(n, np.nan)
    dist_blue_min = _knn_dist_m(
        hex_coords_rad,
        np.radians(comp_valid.loc[is_blue, ["lat", "lng"]].values),
    ) if is_blue.any() else np.full(n, np.nan)
    dist_pano_min = _knn_dist_m(
        hex_coords_rad,
        np.radians(comp_valid.loc[is_pano, ["lat", "lng"]].values),
    ) if is_pano.any() else np.full(n, np.nan)

    # Metricas derivadas (divisao apenas onde denominador > 0)
    mask_has = n_2km > 0
    share_smart = np.zeros(n, dtype=np.float64)
    share_blue  = np.zeros(n, dtype=np.float64)
    share_pano  = np.zeros(n, dtype=np.float64)
    n_2km_f = n_2km[mask_has].astype(np.float64)
    share_smart[mask_has] = n_smart[mask_has] / n_2km_f
    share_blue[mask_has]  = n_blue[mask_has]  / n_2km_f
    share_pano[mask_has]  = n_pano[mask_has]  / n_2km_f

    # Rede dominante com tie-break alfabetico: bluefit < panobianco < smart_fit
    counts_abc = np.column_stack([n_blue, n_pano, n_smart])
    redes_abc = np.array(["bluefit", "panobianco", "smart_fit"])
    rede_dom = np.where(  # type: ignore[call-overload]
        n_2km > 0,
        redes_abc[np.argmax(counts_abc, axis=1)],
        None,
    )

    flag_white = n_2km == 0
    gap_comp = 1.0 / (1.0 + oferta_2km)
    pressao = 100.0 * (1.0 - gap_comp)

    return {
        "n_concorrentes_mapeados_1km": n_1km,
        "n_concorrentes_mapeados_2km": n_2km,
        "n_smart_fit_2km": n_smart,
        "n_bluefit_2km": n_blue,
        "n_panobianco_2km": n_pano,
        "dist_concorrente_mais_proximo_m": dist_comp_min,
        "dist_smart_fit_mais_proximo_m": dist_smart_min,
        "dist_bluefit_mais_proximo_m": dist_blue_min,
        "dist_panobianco_mais_proximo_m": dist_pano_min,
        "oferta_efetiva_mapeada_1km": oferta_1km,
        "oferta_efetiva_mapeada_2km": oferta_2km,
        "share_smart_fit_2km": share_smart,
        "share_bluefit_2km": share_blue,
        "share_panobianco_2km": share_pano,
        "rede_dominante_2km": rede_dom,
        "flag_white_space_2km": flag_white,
        "gap_competitivo_2km": gap_comp,
        "pressao_concorrencial_score_2km": pressao,
    }


def calc_ultra_metrics(
    hex_coords_rad: np.ndarray,
    df_ultra: pd.DataFrame,
) -> dict:
    ultra_valid = df_ultra[df_ultra["flag_coord_valida"]].reset_index(drop=True)
    ultra_coords_rad = np.radians(ultra_valid[["lat", "lng"]].values)

    n = len(hex_coords_rad)
    tree = BallTree(ultra_coords_rad, metric="haversine")

    n_ultra_1km = np.zeros(n, dtype=np.int32)
    n_ultra_2km = np.zeros(n, dtype=np.int32)

    n_chunks = (n - 1) // CHUNK_SIZE + 1
    print(f"  Contagens Ultra ({len(ultra_valid)} unidades, {n_chunks} chunks)...")
    for ci, start in enumerate(range(0, n, CHUNK_SIZE)):
        end = min(start + CHUNK_SIZE, n)
        indices, dists_rad = tree.query_radius(
            hex_coords_rad[start:end],
            r=RADIUS_2KM_RAD,
            return_distance=True,
            sort_results=False,
        )
        for i, (idxs, dr) in enumerate(zip(indices, dists_rad, strict=False)):
            if len(idxs) == 0:
                continue
            gi = start + i
            dm = dr * EARTH_RADIUS_M
            n_ultra_2km[gi] = len(idxs)
            n_ultra_1km[gi] = int((dm <= 1000.0).sum())

        if ci % 5 == 0:
            print(f"    chunk {ci + 1}/{n_chunks}")

    print("  Distancia minima Ultra (k=1)...")
    dist_ultra_min = _knn_dist_m(hex_coords_rad, ultra_coords_rad)

    flag_canibal = dist_ultra_min < 1000.0
    gap_rede = 1.0 / (1.0 + n_ultra_1km.astype(float))

    return {
        "n_unidades_ultra_1km": n_ultra_1km,
        "n_unidades_ultra_2km": n_ultra_2km,
        "dist_ultra_mais_proxima_m": dist_ultra_min,
        "flag_canibalizacao_ultra_1km": flag_canibal,
        "gap_rede_propria_1km": gap_rede,
    }


def validar(df: pd.DataFrame, n_orig: int) -> None:
    print("\n=== Validacao: hexagonos_mercado_mapeado (Bloco 3) ===")

    assert len(df) == n_orig, f"Cardinalidade alterada: {len(df)} != {n_orig}"
    print(f"Linhas: {len(df):,} (preservada OK)")

    required = {
        "n_concorrentes_mapeados_1km", "n_concorrentes_mapeados_2km",
        "n_smart_fit_2km", "n_bluefit_2km", "n_panobianco_2km",
        "dist_concorrente_mais_proximo_m",
        "n_unidades_ultra_1km", "n_unidades_ultra_2km",
        "dist_ultra_mais_proxima_m", "flag_canibalizacao_ultra_1km",
    }
    faltam = required - set(df.columns)
    assert not faltam, f"Colunas faltando: {faltam}"
    print("Schema minimo OK")

    for col in ["n_concorrentes_mapeados_1km", "n_concorrentes_mapeados_2km",
                "n_unidades_ultra_1km", "n_unidades_ultra_2km"]:
        n_nulos = df[col].isna().sum()
        assert n_nulos == 0, f"Nulos inesperados em {col}: {n_nulos}"
    print("Sem nulos em colunas de contagem")

    n_canibal = int(df["flag_canibalizacao_ultra_1km"].sum())
    n_white = int(df["flag_white_space_2km"].sum())
    total = len(df)
    print(f"flag_canibalizacao_ultra_1km=True: {n_canibal:,} ({100*n_canibal/total:.1f}%)")
    print(f"flag_white_space_2km=True:         {n_white:,} ({100*n_white/total:.1f}%)")

    print("\nAmostra manual (3 hexes com concorrentes):")
    sample_cols = [
        "hex_id", "uf", "n_concorrentes_mapeados_2km",
        "dist_concorrente_mais_proximo_m", "rede_dominante_2km",
        "n_unidades_ultra_2km", "dist_ultra_mais_proxima_m",
        "flag_canibalizacao_ultra_1km",
    ]
    com_comp = df[df["n_concorrentes_mapeados_2km"] > 0][sample_cols].head(3)
    if not com_comp.empty:
        print(com_comp.to_string(index=False))

    assert df["dist_concorrente_mais_proximo_m"].isna().sum() == 0, (
        "dist_concorrente_mais_proximo_m tem nulos inesperados"
    )
    assert df["dist_ultra_mais_proxima_m"].isna().sum() == 0, (
        "dist_ultra_mais_proxima_m tem nulos inesperados"
    )
    print("\nValidacao OK")


def main():
    print("Bloco 3 - Enriquecimento espacial por hexagono")
    print("=" * 50)

    print("\n1. Carregando bases...")
    df_hibrido = pd.read_parquet(HIBRIDO_PATH)
    df_est = pd.read_parquet(ESTRUTURAL_PATH, columns=["hex_id", "lat", "lng", "pop_total"])
    df_comp = pd.read_parquet(CONCORRENTES_PATH)
    df_ultra = pd.read_parquet(ULTRA_PATH)
    print(f"   hibrido: {len(df_hibrido):,}")
    print(f"   estrutural (lat/lng/pop_total): {len(df_est):,}")
    print(f"   concorrentes validos: {(df_comp.status_registro == 'valido').sum()}")
    print(f"   ultra validas: {df_ultra.flag_coord_valida.sum()}")

    print("\n2. Montando base com coordenadas...")
    n_orig = len(df_hibrido)
    df_base = df_hibrido.merge(df_est, on="hex_id", how="left", suffixes=("", "_est"))
    assert len(df_base) == n_orig, "Join alterou cardinalidade"
    assert df_base["lat"].isna().sum() == 0, "lat nulo apos join com estrutural"

    hex_coords_rad = np.radians(df_base[["lat", "lng"]].values)
    print(f"   Base: {len(df_base):,} linhas")

    print("\n3. Metricas de concorrentes...")
    # DEC-048: o universo de CADEIA passa a incluir as unidades de rede que o agregador ve'
    # e o cadastro nao tem. O ramo ausente FALA: um artefato com a oferta subestimada em
    # mais de um terco nao pode passar despercebido.
    if REDES_AGREGADOR_PATH.is_file():
        df_redes_wh = pd.read_parquet(REDES_AGREGADOR_PATH)
        cadeias = unir_cadeias(df_comp, df_redes_wh)
        n_base = int((df_comp.status_registro == 'valido').sum())
        print(f"   cadeias: {n_base:,} do cadastro + {len(cadeias) - n_base:,} do agregador = {len(cadeias):,}")
    else:
        print(f"   AUSENTE: {REDES_AGREGADOR_PATH.name} - so' o cadastro; a oferta de cadeia segue subestimada.")
        cadeias = unir_cadeias(df_comp, None)
    comp_metrics = calc_comp_metrics(hex_coords_rad, cadeias)

    print("\n4. Metricas Ultra...")
    ultra_metrics = calc_ultra_metrics(hex_coords_rad, df_ultra)

    print("\n5. Montando DataFrame final...")
    for col, vals in {**comp_metrics, **ultra_metrics}.items():
        df_base[col] = vals

    validar(df_base, n_orig)

    print(f"\n6. Salvando em {OUT_PATH}...")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_base.to_parquet(OUT_PATH, index=False)
    size_mb = OUT_PATH.stat().st_size / 1e6
    print(f"   Salvo: {size_mb:.1f} MB")
    print("\nBloco 3 concluido.")


if __name__ == "__main__":
    main()
