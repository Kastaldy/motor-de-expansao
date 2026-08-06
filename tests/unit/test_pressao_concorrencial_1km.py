"""Pressao concorrencial de 1 km repartida por AREA (camada paralela de mercado).

A propriedade que define este modelo e' a CONSERVACAO DE MASSA: cada concorrente vale
exatamente 1 unidade (2.500 alunos), repartida entre os hexagonos que seu disco de 1 km
cobre, na proporcao da area de intersecao. E' isso que o modelo de 2 km do centroide nao
garante — la o mesmo concorrente pinga peso em ~8-12 hexes com soma variavel.

READ-ONLY sobre o M1: nada aqui toca score_priorizacao, pesos, carteira ou artefatos.
"""

from __future__ import annotations

import math

import h3
import pandas as pd
import pytest

from motor_expansao.pipelines.pressao_concorrencial_1km import (
    CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS,
    COLUNAS_1KM_AREA,
    H3_RESOLUTION,
    RAIO_INFLUENCIA_M,
    anexar_pressao_1km_area,
    comparar_modelos,
    oferta_2km_centroide,
    repartir_concorrentes,
    shares_por_hex,
)

# Pontos de teste em zonas urbanas reais (Sao Paulo e Brasilia).
SP = (-23.55, -46.63)
BSB = (-15.77, -47.93)


def _centroide(hex_id: str) -> tuple[float, float]:
    return h3.cell_to_latlng(hex_id)


def _hex_de(lat: float, lng: float) -> str:
    return h3.latlng_to_cell(lat, lng, H3_RESOLUTION)


# ── Conservacao de massa: a propriedade central ───────────────────────────────


@pytest.mark.parametrize(
    "lat,lng",
    [
        SP,
        BSB,
        (-30.03, -51.23),   # Porto Alegre
        (-3.73, -38.52),    # Fortaleza
        (-12.97, -38.50),   # Salvador
    ],
)
def test_shares_somam_um_em_qualquer_ponto(lat, lng):
    shares = shares_por_hex(lat, lng)
    assert math.isclose(sum(shares.values()), 1.0, abs_tol=1e-9)


def test_shares_somam_um_no_centroide_do_hex():
    """Concorrente exatamente no centroide: o disco cabe inteiro num hex so'."""
    hex_id = _hex_de(*SP)
    lat, lng = _centroide(hex_id)
    shares = shares_por_hex(lat, lng)
    assert math.isclose(sum(shares.values()), 1.0, abs_tol=1e-9)
    assert shares[hex_id] == pytest.approx(1.0, abs=1e-9)
    assert len(shares) == 1, "no centroide o disco de 1 km nao deveria vazar para vizinhos"


def test_shares_somam_um_sobre_um_vertice_do_hex():
    """Caso de canto: sobre um vertice o disco se reparte entre 3 hexes e nada se perde."""
    hex_id = _hex_de(*SP)
    lat, lng = h3.cell_to_boundary(hex_id)[0]
    shares = shares_por_hex(lat, lng)
    assert math.isclose(sum(shares.values()), 1.0, abs_tol=1e-9)
    assert len(shares) >= 3


def test_todos_os_shares_sao_positivos_e_menores_ou_iguais_a_um():
    shares = shares_por_hex(*BSB)
    assert all(0.0 < s <= 1.0 for s in shares.values())


# ── O caso que o Felipe descreveu: concorrente entre dois hexagonos ───────────


def test_concorrente_na_fronteira_reparte_entre_os_dois_hexes():
    """Sobre o meio da aresta, o disco se divide de forma praticamente simetrica."""
    hex_id = _hex_de(*SP)
    boundary = h3.cell_to_boundary(hex_id)
    v0, v1 = boundary[0], boundary[1]
    meio_lat = (v0[0] + v1[0]) / 2.0
    meio_lng = (v0[1] + v1[1]) / 2.0

    shares = shares_por_hex(meio_lat, meio_lng)
    assert math.isclose(sum(shares.values()), 1.0, abs_tol=1e-9)

    dois_maiores = sorted(shares.values(), reverse=True)[:2]
    assert len(dois_maiores) == 2
    # Meio da aresta -> praticamente meio a meio entre os dois hexes principais.
    assert dois_maiores[0] == pytest.approx(0.5, abs=0.05)
    assert dois_maiores[1] == pytest.approx(0.5, abs=0.05)
    # Juntos respondem por ~91% do disco: os ~9% restantes caem nos hexes de canto, nas
    # duas pontas da aresta. E' geometria correta, nao perda — a soma acima ja deu 1,0.
    assert sum(dois_maiores) > 0.90


def test_disco_nunca_alcanca_mais_hexes_que_o_razoavel():
    """Disco de 1 km (3,14 km2) em hex de 5,21 km2 -> no maximo 4 hexes com peso relevante."""
    shares = shares_por_hex(*SP)
    relevantes = [s for s in shares.values() if s > 0.01]
    assert 1 <= len(relevantes) <= 4


# ── Geometria e precisao ──────────────────────────────────────────────────────


def test_disco_aproxima_circulo():
    """O buffer poligonal do disco nao pode subestimar a area do circulo em mais de 0,01%."""
    from shapely.geometry import Point

    from motor_expansao.pipelines.pressao_concorrencial_1km import QUAD_SEGS

    disco = Point(0.0, 0.0).buffer(RAIO_INFLUENCIA_M, quad_segs=QUAD_SEGS)
    area_exata = math.pi * RAIO_INFLUENCIA_M**2
    erro_relativo = abs(disco.area - area_exata) / area_exata
    assert erro_relativo < 5e-5


def test_projecao_local_bate_com_aeqd():
    """A equirretangular local reproduz a azimutal equidistante do pyproj no raio usado.

    Confronta os shares da projecao local contra os mesmos shares numa AEQD centrada no
    concorrente (metrica correta por construcao). E' o que autoriza usar a projecao
    barata no lugar de construir um Transformer do pyproj por concorrente.

    Diferenca MEDIDA: ~1,5e-5 de share, ou seja **0,04 aluno** dos 2.500 de um
    concorrente. O residuo vem de a escala de longitude variar com a latitude dentro da
    janela de +-0,03 graus; corrigir isso nao mudaria nenhum numero exibido.
    """
    from pyproj import Transformer
    from shapely.geometry import Point, Polygon

    from motor_expansao.pipelines.pressao_concorrencial_1km import QUAD_SEGS

    lat, lng = SP
    transformer = Transformer.from_crs(
        "EPSG:4326",
        f"+proj=aeqd +lat_0={lat} +lon_0={lng} +datum=WGS84 +units=m",
        always_xy=True,
    )
    # MESMO `quad_segs` do modulo: assim o teste isola o erro da PROJECAO, sem misturar
    # a diferenca de discretizacao do disco.
    disco = Point(0.0, 0.0).buffer(RAIO_INFLUENCIA_M, quad_segs=QUAD_SEGS)

    shares_aeqd: dict[str, float] = {}
    for hex_id in h3.grid_disk(_hex_de(lat, lng), 2):
        boundary = h3.cell_to_boundary(hex_id)
        xs, ys = transformer.transform([p[1] for p in boundary], [p[0] for p in boundary])
        poligono = Polygon(zip(xs, ys, strict=True))
        area = poligono.intersection(disco).area
        if area > 0:
            shares_aeqd[hex_id] = area / disco.area

    shares_local = shares_por_hex(lat, lng)
    assert set(shares_local) == set(shares_aeqd)
    for hex_id, share in shares_local.items():
        assert share == pytest.approx(shares_aeqd[hex_id], abs=5e-5)


# ── Agregacao por hexagono ────────────────────────────────────────────────────


def _concorrentes(*pontos: tuple[float, float]) -> pd.DataFrame:
    return pd.DataFrame({"lat": [p[0] for p in pontos], "lng": [p[1] for p in pontos]})


def test_oferta_total_iguala_o_numero_de_concorrentes():
    """A invariante do modelo: N concorrentes injetam EXATAMENTE N unidades no sistema."""
    pontos = [SP, BSB, (-30.03, -51.23), (-23.56, -46.64)]
    out = repartir_concorrentes(_concorrentes(*pontos))
    assert out["oferta_efetiva_1km_area"].sum() == pytest.approx(len(pontos), abs=1e-9)


def test_consumo_total_iguala_capacidade_vezes_concorrentes():
    pontos = [SP, BSB]
    out = repartir_concorrentes(_concorrentes(*pontos))
    esperado = len(pontos) * CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS
    assert out["consumo_concorrentes_1km_area"].sum() == pytest.approx(esperado, abs=1e-6)


def test_dois_concorrentes_no_mesmo_hex_somam():
    hex_id = _hex_de(*SP)
    lat, lng = _centroide(hex_id)
    out = repartir_concorrentes(_concorrentes((lat, lng), (lat, lng)))
    linha = out.loc[out["hex_id"] == hex_id].iloc[0]
    assert linha["oferta_efetiva_1km_area"] == pytest.approx(2.0, abs=1e-9)
    assert int(linha["n_concorrentes_influencia_1km"]) == 2


def test_concorrente_sem_coordenada_e_ignorado():
    df = pd.DataFrame({"lat": [SP[0], None], "lng": [SP[1], -46.0]})
    out = repartir_concorrentes(df)
    assert out["oferta_efetiva_1km_area"].sum() == pytest.approx(1.0, abs=1e-9)


def test_sem_concorrentes_devolve_frame_vazio_com_schema():
    out = repartir_concorrentes(pd.DataFrame({"lat": [], "lng": []}))
    assert out.empty
    assert "hex_id" in out.columns
    assert "oferta_efetiva_1km_area" in out.columns


# ── Anexacao ao DataFrame de hexagonos ────────────────────────────────────────


def _df_hex(*hex_ids: str) -> pd.DataFrame:
    linhas = []
    for hex_id in hex_ids:
        lat, lng = _centroide(hex_id)
        linhas.append(
            {
                "hex_id": hex_id,
                "lat": lat,
                "lng": lng,
                "score_priorizacao": 80.0,
                "oferta_efetiva_mapeada_2km": 0.7,
                "gap_competitivo_2km": 0.5,
            }
        )
    return pd.DataFrame(linhas)


def test_anexar_preserva_cardinalidade_e_colunas_de_2km():
    hex_alvo = _hex_de(*SP)
    df = _df_hex(hex_alvo, _hex_de(*BSB))
    out = anexar_pressao_1km_area(df, _concorrentes(SP))

    assert len(out) == len(df)
    # As colunas do modelo de 2 km saem intactas (decisao: colunas novas em paralelo).
    assert out["oferta_efetiva_mapeada_2km"].tolist() == [0.7, 0.7]
    assert out["gap_competitivo_2km"].tolist() == [0.5, 0.5]
    assert out["score_priorizacao"].tolist() == [80.0, 80.0]
    for coluna in COLUNAS_1KM_AREA:
        assert coluna in out.columns


def test_hex_sem_concorrente_tem_gap_um_e_pressao_zero():
    hex_longe = _hex_de(*BSB)
    out = anexar_pressao_1km_area(_df_hex(hex_longe), _concorrentes(SP))
    linha = out.iloc[0]
    assert linha["oferta_efetiva_1km_area"] == 0.0
    assert linha["consumo_concorrentes_1km_area"] == 0.0
    assert linha["gap_competitivo_1km_area"] == pytest.approx(1.0)
    assert linha["pressao_concorrencial_score_1km_area"] == pytest.approx(0.0)


def test_anexar_e_idempotente():
    """Rodar duas vezes nao duplica coluna nem muda valor (colunas antigas sao descartadas)."""
    df = _df_hex(_hex_de(*SP))
    uma = anexar_pressao_1km_area(df, _concorrentes(SP))
    duas = anexar_pressao_1km_area(uma, _concorrentes(SP))
    for coluna in COLUNAS_1KM_AREA:
        assert list(duas.columns).count(coluna) == 1
        assert duas[coluna].tolist() == pytest.approx(uma[coluna].tolist())


def test_pressao_cresce_com_a_oferta():
    hex_alvo = _hex_de(*SP)
    lat, lng = _centroide(hex_alvo)
    um = anexar_pressao_1km_area(_df_hex(hex_alvo), _concorrentes((lat, lng)))
    dois = anexar_pressao_1km_area(
        _df_hex(hex_alvo), _concorrentes((lat, lng), (lat, lng))
    )
    assert (
        dois["pressao_concorrencial_score_1km_area"].iloc[0]
        > um["pressao_concorrencial_score_1km_area"].iloc[0]
    )


# ── Comparativo com o modelo atual (2 km do centroide) ────────────────────────


def _pontos_dentro_do_hex(hex_id: str, n: int, seed: int = 42) -> list[tuple[float, float]]:
    """Sorteia `n` pontos uniformes DENTRO do hexagono (rejection sampling na bbox)."""
    import numpy as np

    rng = np.random.default_rng(seed)
    boundary = h3.cell_to_boundary(hex_id)
    lats = [p[0] for p in boundary]
    lngs = [p[1] for p in boundary]
    pontos: list[tuple[float, float]] = []
    while len(pontos) < n:
        la = float(rng.uniform(min(lats), max(lats)))
        ln = float(rng.uniform(min(lngs), max(lngs)))
        if h3.latlng_to_cell(la, ln, H3_RESOLUTION) == hex_id:
            pontos.append((la, ln))
    return pontos


def test_centroide_do_hex_nao_alcanca_os_vizinhos_em_2km():
    """Por que o raio de 2 km espalha MENOS do que a intuicao sugere.

    Em res-7 os centroides vizinhos ficam a ~2.400-2.500 m um do outro — MAIS que os
    2 km do raio. Logo, um concorrente no centroide so' e' visto pelo proprio hex.
    """
    hex_central = _hex_de(*SP)
    centro = _centroide(hex_central)
    distancias = [
        h3.great_circle_distance(centro, _centroide(v), unit="m")
        for v in h3.grid_disk(hex_central, 1)
        if v != hex_central
    ]
    assert min(distancias) > 2_000.0

    df = _df_hex(*h3.grid_disk(hex_central, 2))
    conc = _concorrentes(centro)
    assert int((oferta_2km_centroide(df, conc) > 0).sum()) == 1


def test_modelo_2km_nao_conserva_massa_e_o_de_1km_conserva():
    """A propriedade que separa os dois modelos, medida sobre 60 posicoes no hexagono.

    O modelo de 2 km injeta entre 0,73 e 0,98 unidade por concorrente conforme a
    posicao (media ~0,80): subestima o consumo em ~20% e de forma DESIGUAL. O modelo
    de 1 km por area injeta exatamente 1,00 em qualquer posicao.
    """
    hex_central = _hex_de(*SP)
    df = _df_hex(*h3.grid_disk(hex_central, 3))

    massas_2km: list[float] = []
    for lat, lng in _pontos_dentro_do_hex(hex_central, 60):
        conc = _concorrentes((lat, lng))
        massas_2km.append(float(oferta_2km_centroide(df, conc).sum()))
        # O modelo novo conserva massa em TODA posicao, sem excecao.
        assert sum(shares_por_hex(lat, lng).values()) == pytest.approx(1.0, abs=1e-9)

    assert min(massas_2km) < 0.80 < max(massas_2km), "a massa de 2 km deveria variar"
    assert all(m < 1.0 for m in massas_2km), "2 km subestima o consumo em toda posicao"
    media = sum(massas_2km) / len(massas_2km)
    assert 0.75 < media < 0.85


def test_alcance_do_1km_area_contem_o_do_2km():
    """A descoberta que decide o efeito no residual: ninguem PERDE pressao na troca.

    Se o conjunto de hexes alcancados pelo disco de 1 km contem sempre o alcancado pelo
    raio de 2 km, entao nenhum hexagono passa de "com pressao" para "sem pressao" — logo
    nenhum hexagono GANHA residual com a mudanca. Medido em 120 posicoes: zero violacoes.

    Razao geometrica: o hex res-7 tem ~2,4 km de ponta a ponta, entao um concorrente a
    1-2 km do centroide esta quase sempre a menos de 1 km da BORDA, e seu disco continua
    cobrindo pedaco do hexagono.
    """
    import numpy as np

    rng = np.random.default_rng(7)
    hex_central = _hex_de(*SP)
    anel = list(h3.grid_disk(hex_central, 3))
    df = _df_hex(*anel)

    so_2km_total = 0
    so_1km_total = 0
    amostras = 0
    while amostras < 120:
        alvo = anel[int(rng.integers(0, len(anel)))]
        boundary = h3.cell_to_boundary(alvo)
        lat = float(rng.uniform(min(p[0] for p in boundary), max(p[0] for p in boundary)))
        lng = float(rng.uniform(min(p[1] for p in boundary), max(p[1] for p in boundary)))
        if _hex_de(lat, lng) != alvo:
            continue
        amostras += 1

        alcance_1km = {h for h, s in shares_por_hex(lat, lng).items() if s > 0}
        oferta = oferta_2km_centroide(df, _concorrentes((lat, lng)))
        alcance_2km = set(df.loc[oferta.to_numpy() > 0, "hex_id"])

        so_2km_total += len(alcance_2km - alcance_1km)
        so_1km_total += len(alcance_1km - alcance_2km)

    assert so_2km_total == 0, (
        "algum hex alcancado a 2 km ficou de fora do disco de 1 km -> ele GANHARIA "
        "residual, e a conclusao 'o residual so' cai' deixaria de valer"
    )
    assert so_1km_total > 0, "o modelo novo deveria alcancar hexes que o antigo nao alcanca"


def test_modelo_1km_area_toca_mais_hexes_que_o_de_2km_em_media():
    """Contra-intuitivo e medido: area de intersecao enxerga vizinho que centroide nao."""
    hex_central = _hex_de(*SP)
    df = _df_hex(*h3.grid_disk(hex_central, 3))

    n_1km: list[int] = []
    n_2km: list[int] = []
    for lat, lng in _pontos_dentro_do_hex(hex_central, 60):
        conc = _concorrentes((lat, lng))
        n_1km.append(len(shares_por_hex(lat, lng)))
        n_2km.append(int((oferta_2km_centroide(df, conc) > 0).sum()))

    assert sum(n_1km) / len(n_1km) > sum(n_2km) / len(n_2km)
    assert max(n_1km) <= 4


def test_comparar_modelos_traz_as_duas_bases_e_o_delta():
    df = _df_hex(*h3.grid_disk(_hex_de(*SP), 2))
    out = comparar_modelos(df, _concorrentes(SP))
    for coluna in (
        "hex_id",
        "oferta_efetiva_mapeada_2km",
        "consumo_concorrentes_2km",
        "oferta_efetiva_1km_area",
        "consumo_concorrentes_1km_area",
        "delta_consumo",
    ):
        assert coluna in out.columns
    esperado = out["consumo_concorrentes_1km_area"] - out["consumo_concorrentes_2km"]
    assert out["delta_consumo"].tolist() == pytest.approx(esperado.tolist())
