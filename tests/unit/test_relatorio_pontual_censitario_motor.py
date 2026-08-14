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
from motor_expansao.dashboard.constants import FATOR_TEMPORAL_RENDA

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
    moradores: float = 3.0,
) -> dict[str, object]:
    """`renda` e a renda per capita BRUTA do setor (V06004/moradores).

    Desde 2026-08-13 o fixture tambem emite as duas colunas cruas que a cadeia da renda usa de
    fato — `avg_moradores_domicilio_setor_2022` e `renda_responsavel_media_setor_2022` —, no
    mesmo padrao do fixture de `test_relatorio_pontual_censitario_mapa.py`. Sem elas o motor
    devolvia `None` na renda, e o teste media a ausencia de coluna achando que media a renda.
    """
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
        "renda_per_capita_setor_2022": renda,
        "renda_per_capita_setor_2022_calibrada": renda,
        "avg_moradores_domicilio_setor_2022": moradores,
        "renda_responsavel_media_setor_2022": renda * moradores,
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
    # A renda per capita exibida e a DOMICILIAR per capita (conceito do IBGE): a renda bruta do
    # setor levada a escala do domicilio pelo uplift e atualizada pelo fator temporal. Expressa
    # em termos do que o proprio motor devolve, para nao fixar no teste o valor de um insumo.
    assert result["renda_per_capita_media_raio"] == pytest.approx(
        1800 * result["fator_uplift_composicao"] * FATOR_TEMPORAL_RENDA, rel=1e-3
    )
    # A invariante que o relatorio precisa fechar: domiciliar = per capita x moradores.
    assert result["renda_domiciliar_total_raio"] == pytest.approx(
        result["renda_per_capita_media_raio"] * 3.0, rel=1e-3
    )
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


def test_lookup_setor_do_ponto_dentro_da_malha(monkeypatch):
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
    # Fatores FIXOS: desde a correcao de 2026-08-13 este campo e renda DOMICILIAR per capita
    # (V06004 x uplift x temporal / moradores), entao ele passou a depender do uplift. Sem
    # monkeypatch o esperado viraria funcao do artefato presente na maquina.
    from motor_expansao.dashboard import censo_point

    uplift = 1.6
    monkeypatch.setattr(censo_point, "uplift_composicao_por_setor", lambda *_a, **_k: uplift)
    monkeypatch.setattr(censo_point, "FATOR_TEMPORAL_RENDA", 1.0)

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, df)

    assert result["flag_setor_ponto_encontrado"] is True
    assert result["cod_setor_ponto"] == "355030801000010"
    # `renda` do fixture e a per capita BRUTA; V06004 = renda x moradores. Logo a domiciliar per
    # capita volta a ser `renda x uplift` (os moradores se cancelam) = 1900 x 1,6.
    assert result["renda_per_capita_setor_ponto"] == pytest.approx(1900 * uplift)
    assert result["score_setor_2022_calibrado_ponto"] == pytest.approx(55)
    assert result["densidade_pop_setor_ponto"] == pytest.approx(
        round(800 / (setor_a.area / 1_000_000.0), 2)
    )
    # Difere do agregado ponderado do raio (A+B combinados) -- prova que nao e reciclagem.
    # ATENCAO ao que esta assercao prova HOJE: entre 2026-08-13 e a correcao do setor do ponto
    # ela passava de graca, porque os dois lados estavam em ESCALAS diferentes (o ponto na
    # calibrada, o raio na domiciliar per capita) e qualquer par de numeros seria diferente. Com
    # os dois na mesma escala ela volta a medir o que promete: agregacao, nao descasamento.
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


# ── Dupla contagem do k na renda domiciliar ───────────────────────────────────────────────────
# Regressao de 2026-08-13. `uplift_composicao` e DEFINIDO como
#     uplift = (renda domiciliar per capita do SIDRA x moradores) / V06004 BRUTA
# (pipelines/derivar_uplift_renda_domiciliar.py), ou seja ele JA converte a renda do responsavel
# para a escala domiciliar do IBGE. A renda domiciliar era montada de `calibrada x moradores`;
# como a calibrada e `V06004/moradores x k`, os moradores se cancelavam e sobrava `V06004 x k` —
# o k virava fator EXTRA sobre uma conversao ja feita. Medido em 5.551 municipios: a renda
# domiciliar exibida era 1,2335x a do IBGE, com dispersao ZERO (p05 = p95), isto e +23,35%.
# NAO havia teste nenhum sobre o NIVEL da renda domiciliar — foi por isso que sobreviveu. Este e.


def _setor_com_renda_completa(k: float, resp: float, moradores: float) -> dict[str, object]:
    """Setor com as duas pontas da renda: a V06004 bruta e a calibrada por um `k` visivel."""
    rec = _sector_record(
        "355030801000001", box(-100, -100, 100, 100), pop=900.0, domicilios=300.0
    )
    rec["renda_responsavel_media_setor_2022"] = resp
    rec["avg_moradores_domicilio_setor_2022"] = moradores
    rec["renda_per_capita_setor_2022"] = resp / moradores
    rec["renda_per_capita_setor_2022_calibrada"] = resp / moradores * k
    return rec


def test_renda_domiciliar_nao_leva_o_k_da_calibragem(monkeypatch):
    """O k NAO pode aparecer na renda domiciliar — o uplift ja fez essa conversao.

    O fixture usa k = 2,0, grande e obvio: se ele vazar, o numero DOBRA.
    """
    from motor_expansao.dashboard import censo_point

    k, resp, moradores, uplift = 2.0, 3000.0, 3.0, 1.6
    monkeypatch.setattr(censo_point, "uplift_composicao_por_setor", lambda *_a, **_k: uplift)
    monkeypatch.setattr(censo_point, "FATOR_TEMPORAL_RENDA", 1.0)

    result = analisar_ponto_censitario_setores(
        LAT_C, LNG_C, pd.DataFrame([_setor_com_renda_completa(k, resp, moradores)])
    )

    # Base da renda domiciliar = V06004 BRUTA (o caminho antigo daria resp x k = 6.000).
    assert result["renda_media_domiciliar_raio"] == pytest.approx(resp, abs=0.01)
    # Com uplift: resp x 1,6 = 4.800 (o caminho antigo daria 9.600).
    assert result["renda_domiciliar_total_raio"] == pytest.approx(resp * uplift, abs=0.01)
    assert result["renda_domiciliar_total_raio"] != pytest.approx(resp * k * uplift, abs=0.01)


def test_renda_per_capita_exibida_e_a_domiciliar_per_capita(monkeypatch):
    """A per capita exibida e a renda do DOMICILIO dividida pelos moradores dele.

    Este teste substitui um anterior (de 2026-08-13 pela manha) que travava a per capita na
    coluna CALIBRADA. Aquela premissa caiu quando se mediu o numero: com o k, a per capita
    exibida ficava 19,62% ABAIXO da referencia do IBGE, e so REMOVER o k a levaria a -34,84% —
    porque o k (1,2335) e uma versao parcial do uplift (1,632), nao um fator independente. O
    conceito certo, e o unico que casa com o SIDRA, e a renda domiciliar per capita.

    O k segue intocado onde ele tem funcao: `renda_pct_nacional_calibrado` -> score.
    """
    from motor_expansao.dashboard import censo_point

    k, resp, moradores, uplift = 2.0, 3000.0, 3.0, 1.6
    monkeypatch.setattr(censo_point, "uplift_composicao_por_setor", lambda *_a, **_k: uplift)
    monkeypatch.setattr(censo_point, "FATOR_TEMPORAL_RENDA", 1.0)

    result = analisar_ponto_censitario_setores(
        LAT_C, LNG_C, pd.DataFrame([_setor_com_renda_completa(k, resp, moradores)])
    )

    # resp x uplift / moradores = 3000 x 1,6 / 3 = 1.600. Sem o k em lugar nenhum.
    assert result["renda_per_capita_media_raio"] == pytest.approx(resp * uplift / moradores, abs=0.01)
    assert result["renda_per_capita_media_raio"] != pytest.approx(resp / moradores * k, abs=0.01)
    # E as duas rendas do relatorio fecham entre si.
    assert result["renda_domiciliar_total_raio"] == pytest.approx(
        result["renda_per_capita_media_raio"] * moradores, abs=0.01
    )


def test_renda_domiciliar_cai_na_per_capita_BRUTA_quando_falta_a_v06004(monkeypatch):
    """O fallback tambem nao pode reintroduzir o k pela porta dos fundos."""
    from motor_expansao.dashboard import censo_point

    k, resp, moradores, uplift = 2.0, 3000.0, 3.0, 1.6
    monkeypatch.setattr(censo_point, "uplift_composicao_por_setor", lambda *_a, **_k: uplift)
    monkeypatch.setattr(censo_point, "FATOR_TEMPORAL_RENDA", 1.0)

    rec = _setor_com_renda_completa(k, resp, moradores)
    del rec["renda_responsavel_media_setor_2022"]  # so sobra a per capita (bruta e calibrada)

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, pd.DataFrame([rec]))

    assert result["renda_domiciliar_total_raio"] == pytest.approx(resp * uplift, abs=0.01)


def test_setor_do_ponto_e_raio_na_MESMA_escala(monkeypatch):
    """Com UM setor cobrindo o raio inteiro, o valor do ponto e o do raio tem de ser IGUAIS.

    E a trava do descasamento introduzido em 2026-08-13 e corrigido em seguida: naquele estado
    `renda_per_capita_media_raio` ja era renda domiciliar per capita, mas
    `renda_per_capita_setor_ponto` ainda saia da coluna CALIBRADA. Os dois campos viajam no MESMO
    payload (`setor_do_ponto.renda_per_capita` contra `renda_per_capita_media_raio` em
    `web/server/app.py`), entao o produto exibia duas "renda per capita" em escalas distintas.

    Um unico setor e o cenario que torna a comparacao exata: a media ponderada do raio sobre um
    setor so E aquele setor, entao qualquer diferenca aqui e diferenca de ESCALA — nao de
    agregacao. Voltar a ler a calibrada faz este teste falhar com `k` visivel: 2,0 no fixture.
    """
    from motor_expansao.dashboard import censo_point

    k, resp, moradores, uplift = 2.0, 3000.0, 3.0, 1.6
    monkeypatch.setattr(censo_point, "uplift_composicao_por_setor", lambda *_a, **_k: uplift)
    monkeypatch.setattr(censo_point, "FATOR_TEMPORAL_RENDA", 1.0)

    # Setor unico, grande o bastante para conter o ponto E cobrir todo o raio.
    rec = _setor_com_renda_completa(k, resp, moradores)
    rec["area_setor_m2"] = float(box(-_RAIO_M * 2, -_RAIO_M * 2, _RAIO_M * 2, _RAIO_M * 2).area)
    rec.update(
        _sector_record(
            "355030801000001",
            box(-_RAIO_M * 2, -_RAIO_M * 2, _RAIO_M * 2, _RAIO_M * 2),
            pop=900.0,
            domicilios=300.0,
        )
    )
    rec["renda_responsavel_media_setor_2022"] = resp
    rec["avg_moradores_domicilio_setor_2022"] = moradores
    rec["renda_per_capita_setor_2022"] = resp / moradores
    rec["renda_per_capita_setor_2022_calibrada"] = resp / moradores * k

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, pd.DataFrame([rec]))

    assert result["flag_setor_ponto_encontrado"] is True
    # Mesma escala: um setor so, logo ponto == raio.
    assert result["renda_per_capita_setor_ponto"] == pytest.approx(
        result["renda_per_capita_media_raio"], rel=1e-9
    )
    # E o valor e a domiciliar per capita = V06004 x uplift / moradores, SEM o k.
    esperado = resp * uplift / moradores
    assert result["renda_per_capita_setor_ponto"] == pytest.approx(esperado, rel=1e-6)
    # Prova que o k nao entrou: com a calibrada o numero seria o dobro.
    assert result["renda_per_capita_setor_ponto"] != pytest.approx(esperado * k, rel=1e-6)
    # E a identidade do relatorio fecha tambem no setor do ponto.
    assert result["renda_domiciliar_total_raio"] == pytest.approx(
        result["renda_per_capita_setor_ponto"] * moradores, rel=1e-6
    )


def test_os_tres_campos_de_renda_per_capita_do_payload_na_MESMA_escala(monkeypatch):
    """Os TRES campos irmaos de renda per capita tem de sair na mesma grandeza.

    O Relatorio Pontual expoe renda per capita em tres lugares do MESMO payload
    (`web/server/app.py`):

      1. `renda_per_capita_media_raio`        -> agregado ponderado do raio
      2. `setor_do_ponto.renda_per_capita`    -> o setor que contem o ponto
      3. `detalhe.distribuicao.renda_per_capita` -> min/mediana/max, via `_dist` sobre a
         coluna de `setores_intersectados`

    A correcao de 2026-08-13 pegou os dois primeiros e deixou o terceiro lendo a coluna
    CALIBRADA — ~24% de diferenca dentro do mesmo documento. Foi achado pela revisao
    automatica do PR #237, nao pela suite: nenhum teste olhava a coluna que alimenta o (3).

    Com UM setor cobrindo o raio inteiro, os tres tem de coincidir: a media ponderada de um
    setor so' e' aquele setor, e min = mediana = max. Qualquer divergencia aqui e' de ESCALA.
    """
    from motor_expansao.dashboard import censo_point

    k, resp, moradores, uplift = 2.0, 3000.0, 3.0, 1.6
    monkeypatch.setattr(censo_point, "uplift_composicao_por_setor", lambda *_a, **_k: uplift)
    monkeypatch.setattr(censo_point, "FATOR_TEMPORAL_RENDA", 1.0)

    rec = _sector_record(
        "355030801000001",
        box(-_RAIO_M * 2, -_RAIO_M * 2, _RAIO_M * 2, _RAIO_M * 2),
        pop=900.0,
        domicilios=300.0,
    )
    rec["renda_responsavel_media_setor_2022"] = resp
    rec["avg_moradores_domicilio_setor_2022"] = moradores
    rec["renda_per_capita_setor_2022"] = resp / moradores
    rec["renda_per_capita_setor_2022_calibrada"] = resp / moradores * k

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, pd.DataFrame([rec]))

    esperado = resp * uplift / moradores  # V06004 x uplift / moradores, SEM o k
    setores = result["setores_intersectados"]

    # (3) a coluna que alimenta a distribuicao existe e esta na escala certa
    assert "renda_per_capita_domiciliar_setor" in setores.columns, (
        "sem esta coluna o consumidor cai na CALIBRADA para montar a distribuicao"
    )
    assert float(setores["renda_per_capita_domiciliar_setor"].iloc[0]) == pytest.approx(
        esperado, rel=1e-6
    )
    # (1) e (2) coincidem com ela
    assert result["renda_per_capita_media_raio"] == pytest.approx(esperado, rel=1e-6)
    assert result["renda_per_capita_setor_ponto"] == pytest.approx(esperado, rel=1e-6)
    # E a CALIBRADA continua no frame, crua, para quem precisar dela — mas em OUTRA coluna,
    # com valor diferente. E' o que prova que os tres nao estao lendo a coluna velha.
    assert float(setores["renda_per_capita_setor_2022_calibrada"].iloc[0]) == pytest.approx(
        resp / moradores * k, rel=1e-6
    )
    assert float(setores["renda_per_capita_setor_2022_calibrada"].iloc[0]) != pytest.approx(
        esperado, rel=1e-6
    )
