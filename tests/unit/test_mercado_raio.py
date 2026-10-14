"""Mercado NO RAIO do ponto (DEC-069) -- `dashboard/mercado_raio.py` + `_mercado_do_ponto`.

O que este arquivo trava, com dado SINTETICO (sem parquet real):

(a) CONSERVACAO DE MASSA: unidade no centro de um raio de 1 km contribui capacidade x 1;
    a 2 km contribui 0; a 1 km contribui a fracao da LENTE de dois circulos de 1 km
    (2*acos(1/2) - sqrt(3)/2) / pi ~= 0,3910.
(b) residual = max(SAM - consumo, 0), com as duas parcelas (concorrentes + Ultra).
(c) gate: faixa M1 do hexagono do ponto E pop do raio >= 5.000; reprovado -> SAM 0.
(d) degradacao: sem insumo de concorrentes/Ultra/taxa, o campo sai None -- NUNCA zero.

E tres paridades que impedem a "segunda regua" (DEC-044): o consumo sobre o POLIGONO de um
hexagono reproduz o share do pipeline (`repartir_concorrentes`), o conjunto de faixas
elegiveis e' o mesmo literal do gate do pipeline, e o raio default e' o do censo.
"""

from __future__ import annotations

import math
from pathlib import Path

import h3
import pandas as pd
import pytest
from shapely.geometry import Polygon

from motor_expansao.dashboard import mercado_raio as mr
from motor_expansao.pipelines.calcular_colunas_mercado import (
    CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS,
    POP_MIN_SAM_GATE,
)
from motor_expansao.pipelines.pressao_concorrencial_1km import repartir_concorrentes

LAT, LNG = -23.55, -46.63
CAP = CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS

# Lente de dois circulos de raio 1 com centros a distancia 1, sobre a area do circulo.
LENTE_1KM = (2 * math.acos(0.5) - 0.5 * math.sqrt(3)) / math.pi  # ~0,39100


def _desloca_norte(lat: float, lng: float, metros: float) -> tuple[float, float]:
    """Ponto `metros` ao norte, na MESMA escala local que o modulo usa para projetar."""
    from motor_expansao.pipelines.pressao_concorrencial_1km import _metros_por_grau

    m_lat, _ = _metros_por_grau(lat)
    return lat + metros / m_lat, lng


def _unidades(*pontos: tuple[float, float], cap: float | None = None) -> pd.DataFrame:
    df = pd.DataFrame({"lat": [p[0] for p in pontos], "lng": [p[1] for p in pontos]})
    if cap is not None:
        df[mr.COLUNA_CAPACIDADE] = cap
    return df


def _mercado(**kw):
    base = dict(
        pop_area=20_000.0,
        cadeias=_unidades(),
        ultra=_unidades(),
        taxa=0.2,
        faixa_oportunidade="alta",
    )
    base.update(kw)
    return mr.mercado_na_area(LAT, LNG, **base)


# --------------------------------------------------------------------------- #
# (a) conservacao de massa                                                     #
# --------------------------------------------------------------------------- #
def test_unidade_no_centro_conta_inteira() -> None:
    area = mr.area_local(LAT, LNG)
    r = mr.consumo_na_area(_unidades((LAT, LNG)), area, LAT, LNG)
    assert r["alunos"] == pytest.approx(CAP, rel=1e-6)
    assert r["equivalentes"] == pytest.approx(1.0, rel=1e-6)
    assert r["n_unidades"] == 1


def test_unidade_a_2km_conta_zero() -> None:
    area = mr.area_local(LAT, LNG)
    r = mr.consumo_na_area(_unidades(_desloca_norte(LAT, LNG, 2_000.0)), area, LAT, LNG)
    assert r["alunos"] == pytest.approx(0.0, abs=1e-3)
    # Tangente nao "alcanca": nenhuma unidade entra na contagem.
    assert r["n_unidades"] == 0


def test_unidade_a_1km_conta_a_fracao_da_lente() -> None:
    area = mr.area_local(LAT, LNG)
    r = mr.consumo_na_area(_unidades(_desloca_norte(LAT, LNG, 1_000.0)), area, LAT, LNG)
    assert r["equivalentes"] == pytest.approx(LENTE_1KM, abs=1e-3)
    assert r["alunos"] == pytest.approx(CAP * LENTE_1KM, rel=2e-3)


def test_capacidade_real_por_unidade_vence_o_proxy() -> None:
    """DEC-057: quem tem aluno real consome o proprio numero; NaN cai no proxy de 2.500."""
    area = mr.area_local(LAT, LNG)
    df = _unidades((LAT, LNG), (LAT, LNG))
    df[mr.COLUNA_CAPACIDADE] = [4_000.0, float("nan")]
    r = mr.consumo_na_area(df, area, LAT, LNG)
    assert r["alunos"] == pytest.approx(4_000.0 + CAP, rel=1e-6)
    assert r["n_capacidade_real"] == 1


def test_consumo_no_poligono_do_hexagono_reproduz_o_pipeline() -> None:
    """Paridade com `repartir_concorrentes`: sobre o POLIGONO de um hexagono, a funcao do
    runtime tem de devolver o mesmo consumo que o pipeline grava naquele hexagono. E' a
    prova de que o modelo e' o MESMO (mesmo disco, mesma projecao), nao uma imitacao."""
    pontos = [(LAT + 0.004, LNG - 0.003), (LAT - 0.006, LNG + 0.002), (LAT + 0.001, LNG + 0.009)]
    df = _unidades(*pontos)
    pipeline = repartir_concorrentes(df).set_index("hex_id")["consumo_concorrentes_1km_area"]

    cell = h3.latlng_to_cell(LAT, LNG, 7)
    poly = Polygon([(lo, la) for la, lo in h3.cell_to_boundary(cell)])
    rp = poly.representative_point()
    area = mr.area_local(rp.y, rp.x, geometria=poly)
    r = mr.consumo_na_area(df, area, rp.y, rp.x)
    # A projecao local tem origem diferente (o hexagono aqui, cada unidade la'): o erro
    # medido e' de centesimos de aluno sobre milhares.
    assert r["alunos"] == pytest.approx(float(pipeline.get(cell, 0.0)), abs=1.0)


# --------------------------------------------------------------------------- #
# (b) residual = max(SAM - consumo, 0)                                         #
# --------------------------------------------------------------------------- #
def test_residual_desconta_concorrentes_e_ultra() -> None:
    m = _mercado(
        cadeias=_unidades((LAT, LNG)),  # 2.500 inteiros
        ultra=_unidades((LAT, LNG), cap=1_000.0),  # alunos reais, 1.000 inteiros
    )
    assert m["grao"] == mr.GRAO_RAIO and m["raio_km"] == 1.0
    assert m["sam_fitness_potencial"] == pytest.approx(4_000.0)  # 20.000 x 0,2
    assert m["oferta_consumida_mercado_estimada"] == pytest.approx(CAP, rel=1e-6)
    assert m["oferta_consumida_ultra_estimada"] == pytest.approx(1_000.0, rel=1e-6)
    assert m["oferta_consumida_total_estimada"] == pytest.approx(CAP + 1_000.0, rel=1e-6)
    # A conta fecha com as DUAS parcelas.
    assert m["oferta_efetiva_disponivel"] == pytest.approx(4_000.0 - CAP - 1_000.0, rel=1e-6)
    # Regua ABSOLUTA do pipeline: 100 x residual / 2.500.
    assert m["score_oportunidade_residual"] == pytest.approx(100 * 500.0 / 2_500.0, rel=1e-4)
    assert m["n_ultra_alunos_reais"] == 1


def test_residual_nunca_fica_negativo() -> None:
    m = _mercado(cadeias=_unidades((LAT, LNG), (LAT, LNG)))  # 5.000 contra SAM 4.000
    assert m["oferta_efetiva_disponivel"] == 0.0
    assert m["score_oportunidade_residual"] == 0.0


# --------------------------------------------------------------------------- #
# (c) gate                                                                     #
# --------------------------------------------------------------------------- #
def test_gate_reprova_por_faixa_inelegivel() -> None:
    m = _mercado(faixa_oportunidade="descartar")
    assert m["flag_sam"] is False
    assert m["sam_fitness_potencial"] == 0.0
    assert m["motivo_gate"] == mr.MOTIVO_FAIXA_INELEGIVEL


def test_gate_reprova_por_populacao_do_raio() -> None:
    m = _mercado(pop_area=POP_MIN_SAM_GATE - 1)
    assert m["gate_pop_ok"] is False
    assert m["sam_fitness_potencial"] == 0.0
    assert m["motivo_gate"] == mr.MOTIVO_POP_INSUFICIENTE


def test_gate_passa_no_limite_exato() -> None:
    m = _mercado(pop_area=float(POP_MIN_SAM_GATE))
    assert m["flag_sam"] is True
    assert m["sam_fitness_potencial"] == pytest.approx(POP_MIN_SAM_GATE * 0.2)


def test_hexagono_fora_da_base_reprova_com_motivo_proprio() -> None:
    m = _mercado(faixa_oportunidade=None)
    assert m["flag_sam"] is False
    assert m["motivo_gate"] == mr.MOTIVO_FAIXA_DESCONHECIDA


# --------------------------------------------------------------------------- #
# (d) degradacao: None com motivo, nunca zero                                  #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("faltando", ["cadeias", "ultra"])
def test_sem_insumo_de_oferta_consumo_e_residual_saem_none(faltando: str) -> None:
    m = _mercado(**{faltando: None})
    assert m["oferta_consumida_total_estimada"] is None
    assert m["oferta_efetiva_disponivel"] is None, "ausencia de dado virou residual"
    assert m["score_oportunidade_residual"] is None
    assert m["motivo"], "parcela faltando PRECISA dizer o motivo"
    # O SAM nao depende da oferta e continua de pe'.
    assert m["sam_fitness_potencial"] == pytest.approx(4_000.0)
    assert m["disponivel"] is True


def test_sem_taxa_o_bloco_fica_indisponivel() -> None:
    m = _mercado(taxa=None)
    assert m["sam_fitness_potencial"] is None
    assert m["oferta_efetiva_disponivel"] is None
    assert m["disponivel"] is False
    assert m["motivo"]


def test_sem_populacao_nao_inventa_sam() -> None:
    m = _mercado(pop_area=None)
    assert m["sam_fitness_potencial"] is None
    assert m["flag_sam"] is None


# --------------------------------------------------------------------------- #
# geometria (porta da DEC-070)                                                 #
# --------------------------------------------------------------------------- #
def test_geometria_troca_o_recorte_e_o_grao() -> None:
    """Quadrado de ~1 km de lado: area ~1 km2, grao 'geometria', raio None."""
    d = 0.0045
    quadrado = Polygon([(LNG - d, LAT - d), (LNG + d, LAT - d), (LNG + d, LAT + d), (LNG - d, LAT + d)])
    m = _mercado(geometria=quadrado, cadeias=_unidades((LAT, LNG)))
    assert m["grao"] == mr.GRAO_GEOMETRIA
    assert m["raio_km"] is None
    assert 0.9 < m["area_km2"] < 1.1
    # Disco de 1 km (3,14 km2) centrado no quadrado de ~1 km2: so' ~1/3 dele cai dentro.
    assert 0.25 < m["oferta_equivalente_concorrentes"] < 0.40


# --------------------------------------------------------------------------- #
# Paridades de constante                                                       #
# --------------------------------------------------------------------------- #
def test_faixas_elegiveis_casam_com_o_pipeline() -> None:
    """O gate do pipeline e' um literal inline; este tripwire le o fonte dele."""
    import motor_expansao.pipelines.calcular_colunas_mercado as ccm

    fonte = Path(ccm.__file__).read_text(encoding="utf-8")
    assert '.isin({"baixa", "media", "alta", "prioridade_maxima"})' in fonte
    assert mr.FAIXAS_SAM_ELEGIVEIS == {"baixa", "media", "alta", "prioridade_maxima"}


def test_raio_default_casa_com_o_do_censo() -> None:
    from motor_expansao.dashboard.censo_point import RAIO_CENSITARIO_DEFAULT_KM

    assert mr.RAIO_MERCADO_DEFAULT_KM == RAIO_CENSITARIO_DEFAULT_KM


# --------------------------------------------------------------------------- #
# Ultra: alunos reais por unidade                                              #
# --------------------------------------------------------------------------- #
def test_ultra_casa_performance_por_coordenada_e_por_hexagono() -> None:
    hx = h3.latlng_to_cell(LAT + 0.05, LNG, 7)
    mapeadas = pd.DataFrame({
        "lat": [LAT, LAT + 0.05, LAT - 0.05],
        "lng": [LNG, LNG, LNG],
        "flag_coord_valida": [True, True, True],
        "hex_id_res7": [h3.latlng_to_cell(LAT, LNG, 7), hx, h3.latlng_to_cell(LAT - 0.05, LNG, 7)],
    })
    perf = pd.DataFrame({
        "lat": [LAT, None, LAT + 0.2],
        "lng": [LNG, None, LNG],
        "hex_id_res7": [None, hx, None],
        "alunos_total": [3_000, 1_800, 2_200],
    })
    u = mr.unidades_ultra_com_capacidade(mapeadas, perf)
    caps = u[mr.COLUNA_CAPACIDADE].tolist()
    assert caps[0] == 3_000  # por coordenada
    assert caps[1] == 1_800  # sem coordenada, pelo hexagono (candidato unico)
    assert math.isnan(caps[2])  # sem performance -> proxy no consumo
    # Performance sem unidade mapeada correspondente ENTRA como unidade propria.
    assert len(u) == 4 and caps[3] == 2_200


# --------------------------------------------------------------------------- #
# `_mercado_do_ponto` sobre um staging sintetico                               #
# --------------------------------------------------------------------------- #
def _settings(staging: Path):
    from motor_expansao.api.settings import Settings
    from motor_expansao.perfil import resolver_perfil

    return Settings(
        censo_geo_dir=staging / "geo",
        ibge_dir=staging / "ibge",
        ultra_dir=staging / "ultra",
        staging_dir=staging,
        perfil=resolver_perfil(),
    )


def _staging_sintetico(staging: Path) -> str:
    staging.mkdir(parents=True, exist_ok=True)
    cell = h3.latlng_to_cell(LAT, LNG, 7)
    pd.DataFrame({
        "hex_id": [cell],
        "faixa_oportunidade": ["alta"],
        "taxa_fitness_mercado_calibrada": [0.2],
        "sam_fitness_potencial": [9_999.0],
        "oferta_efetiva_disponivel": [0.0],
        "score_oportunidade_residual": [0.0],
        "oferta_consumida_mercado_estimada": [7_000.0],
        "oferta_consumida_ultra_estimada": [5_000.0],
    }).to_parquet(staging / "hexagonos_mercado_mapeado.parquet", index=False)
    pd.DataFrame({
        "concorrente_id": ["c1"],
        "rede": ["smart_fit"],
        "lat": [LAT],
        "lng": [LNG],
        "status_registro": ["valido"],
    }).to_parquet(staging / mr.ARQ_CONCORRENTES, index=False)
    lat2, lng2 = _desloca_norte(LAT, LNG, 2_000.0)
    pd.DataFrame({
        "lat": [lat2], "lng": [lng2], "flag_coord_valida": [True], "hex_id_res7": [None],
    }).to_parquet(staging / mr.ARQ_ULTRA, index=False)
    return cell


def test_mercado_do_ponto_le_taxa_e_faixa_do_hexagono_e_calcula_no_raio(tmp_path: Path) -> None:
    from motor_expansao.api.service import _mercado_do_ponto

    cell = _staging_sintetico(tmp_path / "staging")
    m = _mercado_do_ponto(LAT, LNG, _settings(tmp_path / "staging"), 20_000.0)

    assert m["hex_id"] == cell
    assert m["sam_fitness_potencial"] == pytest.approx(4_000.0)
    assert m["oferta_consumida_mercado_estimada"] == pytest.approx(CAP, rel=1e-6)
    assert m["oferta_consumida_ultra_estimada"] == pytest.approx(0.0, abs=1e-3)  # Ultra a 2 km
    assert m["oferta_efetiva_disponivel"] == pytest.approx(1_500.0, rel=1e-5)
    # Auditoria do grao antigo viaja junto, sem entrar na conta.
    assert m["hexagono"]["sam"] == 9_999.0
    assert m["hexagono"]["consumo_ultra"] == 5_000.0


def test_mercado_do_ponto_sem_staging_nao_inventa_zero(tmp_path: Path) -> None:
    from motor_expansao.api.service import _mercado_do_ponto

    vazio = tmp_path / "vazio"
    vazio.mkdir()
    m = _mercado_do_ponto(LAT, LNG, _settings(vazio), 20_000.0)
    assert m["disponivel"] is False
    assert m["sam_fitness_potencial"] is None
    assert m["oferta_consumida_mercado_estimada"] is None
    assert m["oferta_efetiva_disponivel"] is None
    assert m["motivo"]
