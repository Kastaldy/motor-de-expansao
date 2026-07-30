from __future__ import annotations

import pandas as pd
import pytest
from pyproj import Transformer
from shapely.geometry import box
from shapely.ops import transform

from motor_expansao.dashboard.censo_point import (
    CRS_ORIGEM_CENSO,
    METODO_RELATORIO_PONTUAL_CENSITARIO,
    RAIO_CENSITARIO_DEFAULT_KM,
    _local_metric_crs,
    agregar_perfil_bairro_distrito,
    analisar_ponto_censitario_setores,
)

LAT_C = -23.55
LNG_C = -46.63

# DEC-021: a geometria dos fixtures DERIVA do raio canonico em vez de fixar 1.500 m. Antes, um
# setor "parcialmente dentro" era `box(1000, -500, 2500, 500)` — numeros escolhidos contra o raio
# de 1,5 km. Com 1,0 km aquela caixa comeca EXATAMENTE na borda do circulo e a intersecao vai a
# zero: o teste passaria a medir "setor fora do raio" achando que mede ponderacao por area.
# Mantendo as PROPORCOES (0,667R a 1,667R, meia-altura R/3), o peso esperado e' identico ao de
# antes e o teste vale para qualquer raio.
_RAIO_M = RAIO_CENSITARIO_DEFAULT_KM * 1000.0


def _setor_parcial():
    """Caixa que ATRAVESSA a borda do circulo — proporcional ao raio vigente."""
    return box(_RAIO_M * (2 / 3), -_RAIO_M / 3, _RAIO_M * (5 / 3), _RAIO_M / 3)


def _circulo_do_raio():
    from shapely.geometry import Point

    return Point(0, 0).buffer(_RAIO_M, quad_segs=64)


def _to_wgs_geometry(local_geom):
    transformer = Transformer.from_crs(_local_metric_crs(LAT_C, LNG_C), CRS_ORIGEM_CENSO, always_xy=True)
    return transform(transformer.transform, local_geom)


def _sector_record(
    cod_setor: str,
    local_geom,
    *,
    pop: float = 1000.0,
    renda: float = 2000.0,
    score: float = 70.0,
    cod_bairro: str | None = None,
    nome_bairro: str | None = None,
    nome_distrito: str | None = None,
    domicilios: float | None = None,
) -> dict[str, object]:
    geom_wgs = _to_wgs_geometry(local_geom)
    minx, miny, maxx, maxy = geom_wgs.bounds
    return {
        "cod_setor": cod_setor,
        "uf": "SP",
        "cod_municipio": "3550308",
        "nome_municipio": "SAO PAULO",
        "area_setor_m2": float(local_geom.area),
        "geometry_wkb": geom_wgs.wkb,
        "bbox_minx": minx,
        "bbox_miny": miny,
        "bbox_maxx": maxx,
        "bbox_maxy": maxy,
        "pop_total_setor_2022": pop,
        "renda_per_capita_setor_2022_calibrada": renda,
        "densidade_pop_setor_hab_km2": pop / (local_geom.area / 1_000_000.0),
        "score_setor_2022_calibrado": score,
        "flag_renda_disponivel": True,
        "flag_geometria_valida": True,
        "qualidade_join_uf": "A",
        # BLK-RELPON-07: identificacao de bairro/distrito (opcional, default None).
        "cod_bairro": cod_bairro,
        "nome_bairro": nome_bairro,
        "nome_distrito": nome_distrito,
        # BLK-RELPON-08: domicilios particulares ocupados do setor (opcional, default None
        # -> coluna toda NaN, exercitando o caso "n/d" por omissao).
        "domicilios_particulares_ocupados_setor_2022": domicilios,
    }


def test_motor_censitario_setor_totalmente_dentro_do_raio():
    setor = box(-100, -100, 100, 100)
    df = pd.DataFrame([_sector_record("355030801000001", setor, pop=500, renda=1800, score=82)])

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, df)

    assert result["metodo"] == METODO_RELATORIO_PONTUAL_CENSITARIO
    assert result["raio_km"] == pytest.approx(RAIO_CENSITARIO_DEFAULT_KM)
    import math

    assert result["area_km2"] == pytest.approx(
        round(math.pi * RAIO_CENSITARIO_DEFAULT_KM**2, 2), rel=0.01
    )
    assert result["n_setores"] == 1
    assert result["pop_total_raio"] == pytest.approx(500)
    assert result["renda_per_capita_media_raio"] == pytest.approx(1800)
    assert result["score_setor_medio"] == pytest.approx(82)
    setores = result["setores_intersectados"]
    assert setores.loc[0, "peso_area_setor"] == pytest.approx(1.0)
    assert setores.loc[0, "area_intersecao_m2"] == pytest.approx(setor.area)
    # BLK-RELPON-06 (D1): densidade sobre area de espaco VALIDO (setor.area, aqui igual a
    # area de intersecao pois o setor esta totalmente dentro do raio).
    assert result["densidade_pop_raio_valida_hab_km2"] == pytest.approx(
        round(500 / (setor.area / 1_000_000.0), 2)
    )
    assert result["densidade_pop_raio_valida_hab_km2"] > result["densidade_pop_raio_hab_km2"]


def test_motor_censitario_domicilios_total_raio_setor_totalmente_dentro_do_raio():
    setor = box(-100, -100, 100, 100)
    df = pd.DataFrame(
        [_sector_record("355030801000001", setor, pop=500, renda=1800, score=82, domicilios=300)]
    )

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, df)

    # Setor totalmente dentro do raio -> peso de area = 1.0.
    assert result["domicilios_total_raio"] == pytest.approx(300)


def test_motor_censitario_domicilios_total_raio_setor_parcial_pondera_por_area():

    setor = _setor_parcial()
    df = pd.DataFrame(
        [_sector_record("355030801000002", setor, pop=1500, renda=2400, score=60, domicilios=1000)]
    )
    expected_intersection_area = setor.intersection(_circulo_do_raio()).area
    expected_weight = expected_intersection_area / setor.area

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, df)

    assert result["domicilios_total_raio"] == pytest.approx(1000 * expected_weight, rel=0.01)


def test_motor_censitario_domicilios_total_raio_nd_quando_coluna_ausente():
    setor = box(-100, -100, 100, 100)
    # Sem passar `domicilios` -> coluna toda NaN -> "n/d" gracioso.
    df = pd.DataFrame([_sector_record("355030801000001", setor, pop=500, renda=1800, score=82)])

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, df)

    assert result["domicilios_total_raio"] is None


def test_motor_censitario_setor_parcialmente_dentro_do_raio():

    setor = _setor_parcial()
    df = pd.DataFrame([_sector_record("355030801000002", setor, pop=1500, renda=2400, score=60)])
    expected_intersection_area = setor.intersection(_circulo_do_raio()).area
    expected_weight = expected_intersection_area / setor.area

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, df)

    assert result["n_setores"] == 1
    assert result["setores_intersectados"].loc[0, "area_intersecao_m2"] == pytest.approx(
        expected_intersection_area,
        rel=0.01,
    )
    assert result["setores_intersectados"].loc[0, "peso_area_setor"] == pytest.approx(
        expected_weight,
        rel=0.01,
    )
    assert result["pop_total_raio"] == pytest.approx(1500 * expected_weight, rel=0.01)
    # BLK-RELPON-06 (D1): densidade sobre area de espaco VALIDO (soma da area de
    # intersecao, aqui menor que o setor inteiro) -- analogo determinístico do caso real
    # de Rio Branco/AC (interseccao < circulo cheio -> densidade nova sobe vs a antiga,
    # que divide por pi*raio^2 fixo).
    assert result["densidade_pop_raio_valida_hab_km2"] == pytest.approx(
        round(
            (1500 * expected_weight) / (expected_intersection_area / 1_000_000.0),
            2,
        ),
        rel=0.01,
    )
    assert result["densidade_pop_raio_valida_hab_km2"] > result["densidade_pop_raio_hab_km2"]


def test_motor_censitario_exclui_setor_fora_do_raio():
    setor = box(3000, 3000, 3500, 3500)
    df = pd.DataFrame([_sector_record("355030801000003", setor)])

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, df)

    assert result["n_setores"] == 0
    assert result["pop_total_raio"] is None
    assert result["setores_intersectados"].empty
    # BLK-RELPON-06 (D1): sem setores intersectados -> sem area valida -> "n/d" (None).
    assert result["densidade_pop_raio_valida_hab_km2"] is None
    # BLK-RELPON-08: sem candidatos -> dict default intacto -> "n/d" (None).
    assert result["domicilios_total_raio"] is None


def test_motor_censitario_entrada_vazia_conta_pontos_por_distancia_real():
    competitors = pd.DataFrame(
        [
            {"nome_unidade": "Concorrente perto", "lat": LAT_C, "lng": LNG_C + 0.004},
            {"nome_unidade": "Concorrente longe", "lat": LAT_C + 0.1, "lng": LNG_C},
        ]
    )
    ultra = pd.DataFrame([{"nome_unidade": "Ultra perto", "lat": LAT_C, "lng": LNG_C}])

    result = analisar_ponto_censitario_setores(
        LAT_C,
        LNG_C,
        pd.DataFrame(),
        competitors_df=competitors,
        ultra_df=ultra,
    )

    assert result["n_setores"] == 0
    assert result["n_concorrentes"] == 1
    assert result["n_ultra"] == 1
    assert result["concorrentes_raio"]["nome_unidade"].tolist() == ["Concorrente perto"]


def test_motor_censitario_nao_muta_dataframe_de_entrada():
    setor = box(-100, -100, 100, 100)
    df = pd.DataFrame([_sector_record("355030801000004", setor)])
    original = df.copy(deep=True)

    analisar_ponto_censitario_setores(LAT_C, LNG_C, df)

    pd.testing.assert_frame_equal(df, original)


# ── BLK-RELPON-05: lookup do setor que CONTEM o ponto ────────────────────────────


def test_lookup_setor_do_ponto_dentro_da_malha():
    # Setor A cobre o ponto (0,0 no CRS metrico local) por completo. Setor B fica fora do
    # ambito de A (nao compartilha fronteira com o ponto) mas ainda DENTRO do raio, com
    # renda/score bem diferentes -- serve para provar que o valor do ponto NAO e reciclagem
    # do agregado ponderado do raio (que combina A+B).
    # DEC-021: as duas caixas derivam do raio. Fixas em 1.000-1.400 m elas valiam para 1,5 km;
    # com 1,0 km o setor B cairia FORA do circulo, o agregado do raio viraria so o A e o teste
    # passaria a comparar 1900 com 1900 — deixando de provar o que se propoe.
    setor_a = box(-_RAIO_M * 0.47, -_RAIO_M * 0.47, _RAIO_M * 0.47, _RAIO_M * 0.47)
    setor_b = box(_RAIO_M * (2 / 3), -_RAIO_M * 0.13, _RAIO_M * 0.93, _RAIO_M * 0.13)
    df = pd.DataFrame(
        [
            _sector_record("355030801000010", setor_a, pop=800, renda=1900, score=55),
            _sector_record("355030801000011", setor_b, pop=1400, renda=4200, score=95),
        ]
    )

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, df)

    assert result["flag_setor_ponto_encontrado"] is True
    assert result["cod_setor_ponto"] == "355030801000010"
    assert result["renda_per_capita_setor_ponto"] == pytest.approx(1900)
    assert result["score_setor_2022_calibrado_ponto"] == pytest.approx(55)
    assert result["densidade_pop_setor_ponto"] == pytest.approx(
        round(800 / (setor_a.area / 1_000_000.0), 2)
    )
    # Difere do agregado ponderado do raio (A+B combinados) -- prova que nao e reciclagem.
    assert result["renda_per_capita_setor_ponto"] != result["renda_per_capita_media_raio"]
    assert result["score_setor_2022_calibrado_ponto"] != result["score_setor_medio"]


def test_lookup_setor_do_ponto_fora_da_malha():
    # Setor que intersecta o raio mas NAO cobre o ponto (0,0): geometria de
    # test_motor_censitario_setor_parcialmente_dentro_do_raio.
    setor = _setor_parcial()
    df = pd.DataFrame([_sector_record("355030801000012", setor)])

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, df)

    assert result["flag_setor_ponto_encontrado"] is False
    assert result["cod_setor_ponto"] is None
    assert result["renda_per_capita_setor_ponto"] is None
    assert result["densidade_pop_setor_ponto"] is None
    assert result["score_setor_2022_calibrado_ponto"] is None
    # BLK-RELPON-07: ponto fora da malha -> identificacao de bairro/distrito tambem "n/d".
    assert result["cod_bairro_ponto"] is None
    assert result["unidade_ponto_tipo"] is None
    assert result["unidade_ponto_rotulo"] is None


def test_lookup_setor_ponto_setor_geometria_invalida_fica_ausente():
    # Setor cobre o ponto mas tem flag_geometria_valida=False -> ja excluido de
    # `candidates` antes do laco de intersecao (linha 196-197): nunca chega a ser
    # avaliado para conter o ponto, caindo em "n/d" por design (mesmo padrao do resto
    # da funcao).
    setor = box(-700, -700, 700, 700)
    record = _sector_record("355030801000013", setor)
    record["flag_geometria_valida"] = False
    df = pd.DataFrame([record])

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, df)

    assert result["n_setores"] == 0
    assert result["flag_setor_ponto_encontrado"] is False
    assert result["cod_setor_ponto"] is None
    assert result["renda_per_capita_setor_ponto"] is None
    assert result["densidade_pop_setor_ponto"] is None
    assert result["score_setor_2022_calibrado_ponto"] is None


def test_lookup_bairro_ponto_quando_setor_tem_bairro():
    # Setor cobre o ponto por completo e tem cod_bairro/nome_bairro preenchidos.
    setor = box(-700, -700, 700, 700)
    df = pd.DataFrame(
        [_sector_record("355030801000020", setor, cod_bairro="0001", nome_bairro="Bairro Teste")]
    )

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, df)

    assert result["unidade_ponto_tipo"] == "bairro"
    assert result["nome_bairro_ponto"] == "Bairro Teste"
    assert result["unidade_ponto_rotulo"] == "Bairro Teste"


def test_lookup_distrito_ponto_fallback_quando_bairro_ausente():
    # nome_bairro ausente (None) mas nome_distrito preenchido -> fallback para distrito.
    setor = box(-700, -700, 700, 700)
    df = pd.DataFrame(
        [_sector_record("355030801000021", setor, nome_bairro=None, nome_distrito="Distrito Teste")]
    )

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, df)

    assert result["unidade_ponto_tipo"] == "distrito"
    assert result["unidade_ponto_rotulo"] == "Distrito Teste"


# ── BLK-RELPON-07: agregar_perfil_bairro_distrito ────────────────────────────────


def _bairro_row(
    cod_setor: str,
    *,
    cod_bairro: str | None = None,
    nome_distrito: str | None = None,
    pop: float | None = None,
    domicilios: float | None = None,
    area_m2: float | None = None,
    renda: float | None = None,
) -> dict[str, object]:
    return {
        "cod_setor": cod_setor,
        "cod_bairro": cod_bairro,
        "nome_distrito": nome_distrito,
        "pop_total_setor_2022": pop,
        "domicilios_particulares_ocupados_setor_2022": domicilios,
        "area_setor_m2": area_m2,
        "renda_responsavel_media_setor_2022": renda,
    }


def test_agregar_perfil_bairro_agrega_todos_setores_do_bairro_por_cod_bairro():
    df = pd.DataFrame(
        [
            _bairro_row(
                "1", cod_bairro="0001", pop=1000, domicilios=100, area_m2=1_000_000, renda=2000
            ),
            _bairro_row(
                "2", cod_bairro="0001", pop=2000, domicilios=200, area_m2=1_000_000, renda=3000
            ),
            _bairro_row(
                "3", cod_bairro="0002", pop=500, domicilios=50, area_m2=500_000, renda=1500
            ),
        ]
    )

    perfil = agregar_perfil_bairro_distrito(df, cod_bairro="0001", nome_bairro="Bairro Teste")

    assert perfil["flag_perfil_disponivel"] is True
    assert perfil["unidade_tipo"] == "bairro"
    assert perfil["n_setores_unidade"] == 2
    assert perfil["populacao_total"] == pytest.approx(3000)
    assert perfil["domicilios_total"] == pytest.approx(300)
    assert perfil["densidade_hab_km2"] == pytest.approx(1500.0)
    assert perfil["renda_media_domiciliar"] == pytest.approx(2666.67, abs=0.01)
    assert perfil["metodo_renda_perfil_bairro"] == "renda_responsavel_media_ponderada_por_domicilios"


def test_agregar_perfil_bairro_fallback_para_distrito_quando_bairro_ausente():
    df = pd.DataFrame(
        [
            _bairro_row(
                "1", cod_bairro=None, nome_distrito="Distrito Teste",
                pop=800, domicilios=80, area_m2=800_000, renda=1800,
            ),
            _bairro_row(
                "2", cod_bairro=None, nome_distrito="Distrito Teste",
                pop=1200, domicilios=120, area_m2=800_000, renda=2200,
            ),
            _bairro_row(
                "3", cod_bairro=None, nome_distrito="Outro Distrito",
                pop=5000, domicilios=500, area_m2=5_000_000, renda=9000,
            ),
        ]
    )

    perfil = agregar_perfil_bairro_distrito(
        df, cod_bairro=None, nome_distrito="Distrito Teste"
    )

    assert perfil["unidade_tipo"] == "distrito"
    assert perfil["unidade_nome"] == "Distrito Teste"
    assert perfil["n_setores_unidade"] == 2
    assert perfil["populacao_total"] == pytest.approx(2000)
    assert perfil["domicilios_total"] == pytest.approx(200)


def test_agregar_perfil_bairro_renda_exclui_setor_com_domicilio_zero_ou_renda_nula():
    df = pd.DataFrame(
        [
            _bairro_row(
                "1", cod_bairro="0001", pop=500, domicilios=100, area_m2=500_000, renda=2000
            ),
            _bairro_row(
                "2", cod_bairro="0001", pop=500, domicilios=0, area_m2=500_000, renda=2500
            ),
            _bairro_row(
                "3", cod_bairro="0001", pop=500, domicilios=150, area_m2=500_000, renda=float("nan")
            ),
        ]
    )

    perfil = agregar_perfil_bairro_distrito(df, cod_bairro="0001", nome_bairro="Bairro Teste")

    # Renda so considera o setor 1 (unico com renda e domicilios validos e > 0).
    assert perfil["renda_media_domiciliar"] == pytest.approx(2000.0)
    # Populacao/domicilios somam os 3 setores (a exclusao e so da renda).
    assert perfil["populacao_total"] == pytest.approx(1500)
    assert perfil["domicilios_total"] == pytest.approx(250)


def test_agregar_perfil_bairro_nd_quando_sem_identificador():
    df = pd.DataFrame(
        [_bairro_row("1", cod_bairro="0001", pop=500, domicilios=100, area_m2=500_000, renda=2000)]
    )

    perfil = agregar_perfil_bairro_distrito(
        df, cod_bairro=None, nome_bairro=None, nome_distrito=None
    )

    assert perfil["flag_perfil_disponivel"] is False
    assert perfil["populacao_total"] is None
    assert perfil["domicilios_total"] is None
    assert perfil["densidade_hab_km2"] is None
    assert perfil["renda_media_domiciliar"] is None


def test_agregar_perfil_bairro_nd_quando_setores_df_vazio():
    perfil = agregar_perfil_bairro_distrito(
        pd.DataFrame(), cod_bairro="0001", nome_bairro="Bairro Teste"
    )

    assert perfil["flag_perfil_disponivel"] is False
    assert perfil["populacao_total"] is None
