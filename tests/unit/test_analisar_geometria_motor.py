"""Motor censitario com POLIGONO desenhado -- "Analisar geometria", fase 1 (DEC-070).

O poligono e' um parametro OPCIONAL e ADITIVO de `analisar_ponto_censitario_setores`. Este
arquivo trava as duas metades da promessa:

- SEM geometria, nada muda: mesmas chaves, metodo `_1km`, raio 1,0 e area pi;
- COM geometria, a MESMA intersecao setor a setor roda no poligono: um poligono que
  aproxima o circulo de 1 km reproduz o raio; um quadrado da' o peso de area certo;
  concorrentes sao ponto-em-poligono (um concavo NAO conta quem esta no "vao");
- a validacao (`geometria_desenhada`) recusa o que a analise nao sabe ler, com mensagem
  em portugues.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest
from pyproj import Transformer
from shapely.geometry import Point, Polygon, box
from shapely.ops import transform

from motor_expansao.dashboard.censo_point import (
    CRS_ORIGEM_CENSO,
    GEOMETRIA_TIPO_POLIGONO,
    METODO_RELATORIO_PONTUAL_CENSITARIO,
    METODO_RELATORIO_PONTUAL_POLIGONO,
    _local_metric_crs,
    analisar_ponto_censitario_setores,
)
from motor_expansao.dashboard.geometria_desenhada import (
    AREA_MAX_KM2,
    AREA_MIN_KM2,
    MAX_VERTICES,
    GeometriaDesenhadaInvalida,
    validar_geometria_desenhada,
)

LAT_C = -23.55
LNG_C = -46.63


def _para_wgs(local_geom):
    """Geometria em metros (AEQD centrada em LAT_C/LNG_C) -> graus (x=lng)."""
    t = Transformer.from_crs(_local_metric_crs(LAT_C, LNG_C), CRS_ORIGEM_CENSO, always_xy=True)
    return transform(t.transform, local_geom)


def _ponto_wgs(x: float, y: float) -> tuple[float, float]:
    """(lat, lng) de um ponto em metros no plano local."""
    p = _para_wgs(Point(x, y))
    return p.y, p.x


def _setor(cod: str, local_geom, *, pop: float = 1000.0, renda: float = 2000.0,
           dom: float = 300.0) -> dict[str, object]:
    g = _para_wgs(local_geom)
    minx, miny, maxx, maxy = g.bounds
    return {
        "cod_setor": cod,
        "uf": "SP",
        "cod_municipio": "3550308",
        "nome_municipio": "SAO PAULO",
        "area_setor_m2": float(local_geom.area),
        "geometry_wkb": g.wkb,
        "bbox_minx": minx, "bbox_miny": miny, "bbox_maxx": maxx, "bbox_maxy": maxy,
        "pop_total_setor_2022": pop,
        "domicilios_particulares_ocupados_setor_2022": dom,
        "renda_per_capita_setor_2022": renda,
        "renda_per_capita_setor_2022_calibrada": renda,
        "avg_moradores_domicilio_setor_2022": 3.0,
        "renda_responsavel_media_setor_2022": renda * 3.0,
        "densidade_pop_setor_hab_km2": pop / (local_geom.area / 1e6),
        "score_setor_2022_calibrado": 60.0,
        "flag_renda_disponivel": True,
        "flag_geometria_valida": True,
        "qualidade_join_uf": "A",
    }


def _malha_de_setores(passo: float = 250.0, alcance: float = 1537.0) -> pd.DataFrame:
    """Grade de setores quadrados cobrindo +-alcance m, populacao e renda variando.

    `alcance` NAO e' multiplo do raio de proposito: com a grade alinhada em 1.000 m, quatro
    setores ficam TANGENTES ao circulo (intersecao de area ~1e-6 m2) e entram ou nao
    conforme o arredondamento da reprojecao -- o teste mediria ruido de ponto flutuante.
    """
    recs = []
    i = 0
    x = -alcance
    while x < alcance:
        y = -alcance
        while y < alcance:
            i += 1
            recs.append(
                _setor(f"S{i:04d}", box(x, y, x + passo, y + passo),
                       pop=500.0 + (i % 7) * 100.0, renda=1500.0 + (i % 5) * 400.0,
                       dom=150.0 + (i % 3) * 40.0)
            )
            y += passo
        x += passo
    return pd.DataFrame(recs)


# --------------------------------------------------------------------------- #
# Sem geometria, nada muda                                                    #
# --------------------------------------------------------------------------- #
_CHAVES_DO_RAIO = {
    "lat", "lng", "raio_km", "area_km2", "metodo", "n_setores", "area_intersecao_total_m2",
    "pop_total_raio", "domicilios_total_raio", "renda_per_capita_media_raio",
    "metodo_renda_raio", "renda_media_domiciliar_raio", "renda_domiciliar_total_raio",
    "metodo_renda_domiciliar_raio", "uf_renda_uplift", "cod_municipio_renda_uplift",
    "fator_uplift_renda_domiciliar", "fator_uplift_composicao",
    "fator_uplift_composicao_municipio", "fracao_uplift_extrapolado_raio",
    "fator_temporal_renda", "data_referencia_renda", "densidade_pop_raio_hab_km2",
    "densidade_pop_raio_valida_hab_km2", "score_setor_medio", "score_setor_max",
    "n_concorrentes", "n_concorrentes_cadeia", "n_academias_total", "n_ultra",
    "concorrentes_raio", "ultra_raio", "setores_intersectados", "cod_setor_ponto",
    "renda_per_capita_setor_ponto", "densidade_pop_setor_ponto",
    "score_setor_2022_calibrado_ponto", "flag_setor_ponto_encontrado", "cod_bairro_ponto",
    "nome_bairro_ponto", "nome_distrito_ponto", "unidade_ponto_tipo", "unidade_ponto_rotulo",
}


def _escalares(res: dict) -> dict:
    return {k: v for k, v in res.items() if not isinstance(v, pd.DataFrame)}


def test_sem_geometria_o_dict_do_raio_nao_muda() -> None:
    setores = _malha_de_setores()
    res = analisar_ponto_censitario_setores(LAT_C, LNG_C, setores)
    # Mesmas chaves de antes da DEC-070 -- nenhuma a mais (nem `geometria_tipo`).
    assert set(res) == _CHAVES_DO_RAIO
    assert res["metodo"] == METODO_RELATORIO_PONTUAL_CENSITARIO
    assert res["raio_km"] == 1.0
    assert res["area_km2"] == round(math.pi, 2)
    # Passar `geometria_wgs84=None` explicito e' o MESMO caminho, valor a valor.
    explicito = analisar_ponto_censitario_setores(LAT_C, LNG_C, setores, geometria_wgs84=None)
    assert _escalares(explicito) == _escalares(res)
    pd.testing.assert_frame_equal(
        explicito["setores_intersectados"], res["setores_intersectados"]
    )


# --------------------------------------------------------------------------- #
# Com geometria                                                               #
# --------------------------------------------------------------------------- #
def test_poligono_que_aproxima_o_circulo_reproduz_o_raio() -> None:
    setores = _malha_de_setores()
    raio = analisar_ponto_censitario_setores(LAT_C, LNG_C, setores)
    # O circulo de 1 km com 64 segmentos por quadrante (256 vertices), levado a graus.
    circulo = _para_wgs(Point(0, 0).buffer(1000.0, quad_segs=64))
    poli = analisar_ponto_censitario_setores(LAT_C, LNG_C, setores, geometria_wgs84=circulo)

    assert poli["metodo"] == METODO_RELATORIO_PONTUAL_POLIGONO
    assert poli["geometria_tipo"] == GEOMETRIA_TIPO_POLIGONO
    assert poli["raio_km"] is None
    assert poli["area_km2"] == pytest.approx(math.pi, rel=1e-3)
    assert poli["n_setores"] == raio["n_setores"]
    for chave in ("pop_total_raio", "domicilios_total_raio", "renda_per_capita_media_raio",
                  "renda_domiciliar_total_raio", "area_intersecao_total_m2"):
        assert poli[chave] == pytest.approx(raio[chave], rel=0.01), chave
    # O setor do ponto e' o mesmo: o (lat, lng) e' o centro dos dois recortes.
    assert poli["cod_setor_ponto"] == raio["cod_setor_ponto"]


def test_quadrado_da_o_peso_de_area_certo() -> None:
    # Tres setores de 1.000 habitantes: A inteiro dentro, B metade dentro, C fora.
    setores = pd.DataFrame([
        _setor("A", box(-400, -400, 0, 400), pop=1000.0),       # 0,32 km2, dentro
        _setor("B", box(300, -400, 700, 400), pop=1000.0),      # metade (300..500) dentro
        _setor("C", box(2000, 2000, 2400, 2400), pop=1000.0),   # fora
    ])
    quadrado = _para_wgs(box(-500, -500, 500, 500))  # 1,0 km2
    lat, lng = _ponto_wgs(-200, 0)
    res = analisar_ponto_censitario_setores(lat, lng, setores, geometria_wgs84=quadrado)

    assert res["area_km2"] == pytest.approx(1.0, rel=0.01)
    assert res["n_setores"] == 2
    pesos = dict(zip(res["setores_intersectados"]["cod_setor"],
                     res["setores_intersectados"]["peso_area_setor"], strict=True))
    assert pesos["A"] == pytest.approx(1.0, abs=0.01)
    assert pesos["B"] == pytest.approx(0.5, abs=0.01)
    assert res["pop_total_raio"] == pytest.approx(1500.0, rel=0.01)
    # Densidade pela area do POLIGONO, nao por pi*r2.
    assert res["densidade_pop_raio_hab_km2"] == pytest.approx(1500.0, rel=0.02)
    assert res["cod_setor_ponto"] == "A"


def test_concorrentes_sao_ponto_em_poligono_num_concavo() -> None:
    # Um "U" de 1.200 x 1.200 m com vao central de 400 m de largura e 800 m de fundo.
    u_local = Polygon([(-600, -600), (600, -600), (600, 600), (200, 600), (200, -200),
                       (-200, -200), (-200, 600), (-600, 600)])
    u = _para_wgs(u_local)
    ref = u.representative_point()
    dentro = _ponto_wgs(-400, 300)       # no braco esquerdo
    no_vao = _ponto_wgs(0, 300)          # dentro da CAIXA, fora do poligono
    longe = _ponto_wgs(3000, 3000)
    comp = pd.DataFrame({
        "rede": ["dentro", "vao", "longe"],
        "lat": [dentro[0], no_vao[0], longe[0]],
        "lng": [dentro[1], no_vao[1], longe[1]],
    })
    ultra = pd.DataFrame({"lat": [no_vao[0]], "lng": [no_vao[1]]})
    res = analisar_ponto_censitario_setores(
        ref.y, ref.x, pd.DataFrame(), competitors_df=comp, ultra_df=ultra, geometria_wgs84=u,
    )
    assert list(res["concorrentes_raio"]["rede"]) == ["dentro"]
    assert res["n_concorrentes"] == 1
    assert res["n_ultra"] == 0
    # `dist_km` continua sendo ao ponto de referencia, para ordenar a lista.
    assert "dist_km" in res["concorrentes_raio"].columns
    # O "vao" esta a menos de 1 km do ponto: pelo raio ele contaria. Pelo poligono, nao.
    raio = analisar_ponto_censitario_setores(
        ref.y, ref.x, pd.DataFrame(), competitors_df=comp, ultra_df=ultra,
    )
    assert "vao" in set(raio["concorrentes_raio"]["rede"])


# --------------------------------------------------------------------------- #
# Validacao                                                                    #
# --------------------------------------------------------------------------- #
def _geojson(local_geom) -> dict:
    g = _para_wgs(local_geom)
    return {"type": "Polygon", "coordinates": [[list(c) for c in g.exterior.coords]]}


def test_valida_e_devolve_o_ponto_interno_e_a_area() -> None:
    u_local = Polygon([(-600, -600), (600, -600), (600, 600), (200, 600), (200, -200),
                       (-200, -200), (-200, 600), (-600, 600)])
    d = validar_geometria_desenhada(_geojson(u_local))
    assert d.n_vertices == 8
    assert d.area_km2 == pytest.approx((1.2 * 1.2) - (0.4 * 0.8), rel=0.01)
    # O ponto de referencia esta DENTRO, mesmo num concavo (o centroide do "U" cairia
    # perto do vao).
    assert d.poligono.contains(Point(d.lng, d.lat))
    anel = d.coordenadas[0]
    assert anel[0] == anel[-1] and len(anel) == 9


def test_anel_aberto_e_vertice_repetido_sao_normalizados() -> None:
    g = _para_wgs(box(-500, -500, 500, 500))
    coords = [list(c) for c in g.exterior.coords][:-1]  # sem o fechamento
    coords.insert(1, list(coords[0]))                    # clique duplo no 1o vertice
    d = validar_geometria_desenhada({"type": "Polygon", "coordinates": [coords]})
    assert d.n_vertices == 4


@pytest.mark.parametrize(
    ("entrada", "trecho"),
    [
        ({"type": "Point", "coordinates": [LNG_C, LAT_C]}, "polígono GeoJSON"),
        ({"type": "Polygon", "coordinates": []}, "sem coordenadas"),
        (
            {"type": "Polygon", "coordinates": [
                [[0, 0], [1, 0], [1, 1], [0, 0]], [[0.2, 0.2], [0.3, 0.2], [0.3, 0.3], [0.2, 0.2]],
            ]},
            "buracos",
        ),
        ({"type": "Polygon", "coordinates": [[[LNG_C, LAT_C], [LNG_C + 0.01, LAT_C]]]}, "pelo menos 3"),
        ({"type": "Polygon", "coordinates": [[[LNG_C, LAT_C], ["x", LAT_C], [LNG_C, LAT_C + 0.01]]]},
         "Coordenada inválida"),
    ],
)
def test_entradas_malformadas(entrada, trecho: str) -> None:
    with pytest.raises(GeometriaDesenhadaInvalida, match=trecho):
        validar_geometria_desenhada(entrada)


def test_autointersecao_e_recusada() -> None:
    oito = Polygon([(-500, -500), (500, 500), (500, -500), (-500, 500)])
    with pytest.raises(GeometriaDesenhadaInvalida, match="cruza a si mesmo"):
        validar_geometria_desenhada(_geojson(oito))


def test_vertices_alinhados_sao_recusados() -> None:
    reta = {"type": "Polygon", "coordinates": [[[LNG_C, LAT_C], [LNG_C + 0.01, LAT_C],
                                                 [LNG_C + 0.02, LAT_C], [LNG_C, LAT_C]]]}
    with pytest.raises(GeometriaDesenhadaInvalida, match="alinhados"):
        validar_geometria_desenhada(reta)


def test_area_fora_dos_limites() -> None:
    lado_min = math.sqrt(AREA_MIN_KM2 * 0.5) * 1000.0  # metade do piso
    with pytest.raises(GeometriaDesenhadaInvalida, match="o mínimo é 0,1 km²"):
        validar_geometria_desenhada(_geojson(box(0, 0, lado_min, lado_min)))
    lado_max = math.sqrt(AREA_MAX_KM2 * 1.2) * 1000.0
    with pytest.raises(GeometriaDesenhadaInvalida, match="o máximo é 25 km²"):
        validar_geometria_desenhada(_geojson(box(0, 0, lado_max, lado_max)))
    # Dentro dos limites passa.
    assert validar_geometria_desenhada(_geojson(box(0, 0, 1000, 1000))).area_km2 == pytest.approx(1.0, rel=0.01)


def test_vertices_demais() -> None:
    n = MAX_VERTICES + 1
    circulo = Point(0, 0).buffer(1000.0, quad_segs=64)
    pontos = [circulo.exterior.interpolate(i / n, normalized=True) for i in range(n)]
    with pytest.raises(GeometriaDesenhadaInvalida, match=f"o máximo é {MAX_VERTICES}"):
        validar_geometria_desenhada(_geojson(Polygon([(p.x, p.y) for p in pontos])))


def test_vertice_fora_do_pais_usa_a_regua_do_chamador() -> None:
    def _so_sul(lat: float, lng: float) -> None:
        if lat > -23.549:
            raise ValueError("fora do Brasil")

    with pytest.raises(GeometriaDesenhadaInvalida, match="Vértice .* fora do Brasil"):
        validar_geometria_desenhada(_geojson(box(-500, -500, 500, 500)), validar_coordenada=_so_sul)
