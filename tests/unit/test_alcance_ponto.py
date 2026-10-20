"""Alcance do ponto (DEC-074) -- `dashboard/alcance_ponto.py` e as portas do motor.

O que este arquivo trava, sem nenhum servico real (o Valhalla e' SEMPRE mockado em
`requests.post`/`requests.get`):

(a) o FATOR da regua: raio de 1 km -> exatamente 1.0, raio de 2 km -> exatamente 4.0, e
    da area exata (nunca da arredondada) no recorte poligonal;
(b) o motor censitario: raio != 1 ganha metodo `_{r}km` e as chaves da regua; a isocrona
    ganha metodo proprio; o raio de 1 km sem geometria NAO ganha chave nenhuma;
(c) a isocrona: MultiPolygon com buraco aceito, origem fora une um disco, teto de area e
    de diagonal recusam com `AlcanceInvalido`, e qualquer falha do servico (env vazia,
    timeout, 5xx) vira `RotasIndisponiveis` -- NUNCA um raio de 1 km em silencio;
(d) a carga de setores alcanca os vizinhos do raio pedido (classe DEC-065).
"""

from __future__ import annotations

import math
import subprocess
import sys

import pandas as pd
import pytest
import requests
from pyproj import Transformer
from shapely.geometry import MultiPolygon, Point, Polygon, box, mapping
from shapely.ops import transform

from motor_expansao.dashboard import alcance_ponto as ap
from motor_expansao.dashboard.censo_point import (
    CRS_ORIGEM_CENSO,
    GEOMETRIA_TIPO_ISOCRONA_CARRO_10MIN,
    METODO_RELATORIO_PONTUAL_CENSITARIO,
    METODO_RELATORIO_PONTUAL_ISOCRONA,
    RAIO_CENSITARIO_DEFAULT_KM,
    _local_metric_crs,
    analisar_ponto_censitario_setores,
    metodo_do_raio,
)

LAT, LNG = -23.55, -46.63
URL = "http://valhalla.teste:8002"


def _para_wgs(geom_m):
    """Metros (AEQD centrada em LAT/LNG) -> graus (x=lng)."""
    t = Transformer.from_crs(_local_metric_crs(LAT, LNG), CRS_ORIGEM_CENSO, always_xy=True)
    return transform(t.transform, geom_m)


# --------------------------------------------------------------------------- #
# Fakes do servico de rotas                                                    #
# --------------------------------------------------------------------------- #
class _Resp:
    def __init__(self, status: int = 200, corpo=None, texto: str = "") -> None:
        self.status_code = status
        self._corpo = corpo
        self.text = texto

    def json(self):
        if isinstance(self._corpo, Exception):
            raise self._corpo
        return self._corpo

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def _feature_collection(*geoms_m) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"contour": 10}, "geometry": mapping(_para_wgs(g))}
            for g in geoms_m
        ],
    }


@pytest.fixture
def rotas(monkeypatch):
    """Liga a env e registra as chamadas. `rotas.isocrona` define o que o POST devolve."""
    ap.limpar_cache()
    monkeypatch.setenv(ap.ENV_ROTAS, URL + "/")

    class _Estado:
        posts: list = []
        gets: list = []
        isocrona: object = _Resp(200, _feature_collection(Point(0, 0).buffer(3000)))
        status: object = _Resp(200, {"version": "3.9.0", "tileset_last_modified": 1_760_000_000})

    estado = _Estado()
    estado.posts = []
    estado.gets = []

    def _post(url, json=None, timeout=None, **_kw):
        estado.posts.append({"url": url, "json": json, "timeout": timeout})
        if isinstance(estado.isocrona, Exception):
            raise estado.isocrona
        return estado.isocrona

    def _get(url, timeout=None, **_kw):
        estado.gets.append({"url": url, "timeout": timeout})
        if isinstance(estado.status, Exception):
            raise estado.status
        return estado.status

    monkeypatch.setattr(requests, "post", _post)
    monkeypatch.setattr(requests, "get", _get)
    yield estado
    ap.limpar_cache()


# --------------------------------------------------------------------------- #
# (a) fator da regua                                                           #
# --------------------------------------------------------------------------- #
def test_fator_do_raio_e_exato() -> None:
    # Igualdade EXATA, nao approx: 0,9999 moveria a meta de 10.000 habitantes.
    assert ap.fator_regua_do_raio(1.0) == 1.0
    assert ap.fator_regua_do_raio(2.0) == 4.0
    assert ap.fator_regua_do_raio(ap.RAIO_DO_ALCANCE[ap.ALCANCE_RAIO_2KM]) == 4.0


def test_fator_da_area_e_area_sobre_pi() -> None:
    assert ap.fator_regua_da_area(math.pi) == 1.0
    assert ap.fator_regua_da_area(38.2) == pytest.approx(38.2 / math.pi)
    # A area ARREDONDADA do dict (3,14) nao da' 1 -- e' por isso que o fator nao a usa.
    assert ap.fator_regua_da_area(3.14) != 1.0


@pytest.mark.parametrize("ruim", [0, -1, float("nan"), float("inf"), None, "x"])
def test_fator_recusa_entrada_invalida(ruim) -> None:
    with pytest.raises(ValueError):
        ap.fator_regua_do_raio(ruim)
    with pytest.raises(ValueError):
        ap.fator_regua_da_area(ruim)


def test_vocabulario_e_paridades() -> None:
    from motor_expansao.dashboard import geometria_desenhada as gd

    assert ap.ALCANCES == ("raio_1km", "raio_2km", "carro_10min")
    assert ap.RAIO_DO_ALCANCE == {"raio_1km": 1.0, "raio_2km": 2.0}
    assert ap.MINUTOS_ISOCRONA == 10
    # Literais repetidos para o modulo seguir leve: a igualdade e' o tripwire.
    assert ap.AREA_MAX_KM2 == gd.AREA_MAX_KM2
    assert ap.DIAGONAL_MAX_KM == gd.DIAGONAL_MAX_KM
    assert ap.RAIO_REFERENCIA_KM == RAIO_CENSITARIO_DEFAULT_KM


def test_modulo_e_leve_no_import() -> None:
    """Sem pyproj, requests nem `censo_point` no import: so' quem calcula isocrona paga."""
    codigo = (
        "import sys, motor_expansao.dashboard.alcance_ponto\n"
        "pesados = [m for m in ('pyproj', 'requests', 'motor_expansao.dashboard.censo_point')"
        " if m in sys.modules]\n"
        "print(','.join(pesados))\n"
    )
    saida = subprocess.run(
        [sys.executable, "-c", codigo],
        capture_output=True,
        text=True,
        check=True,
        stdin=subprocess.DEVNULL,
    ).stdout.strip()
    assert saida == ""


def test_rotas_configuradas_le_a_env(monkeypatch) -> None:
    monkeypatch.delenv(ap.ENV_ROTAS, raising=False)
    assert ap.rotas_configuradas() is False
    monkeypatch.setenv(ap.ENV_ROTAS, "   ")
    assert ap.rotas_configuradas() is False
    monkeypatch.setenv(ap.ENV_ROTAS, URL + "/")
    assert ap.rotas_configuradas() is True
    assert ap.url_rotas() == URL


# --------------------------------------------------------------------------- #
# (b) motor censitario                                                         #
# --------------------------------------------------------------------------- #
def _setor(cod: str, geom_m, pop: float = 1000.0) -> dict:
    g = _para_wgs(geom_m)
    minx, miny, maxx, maxy = g.bounds
    return {
        "cod_setor": cod,
        "uf": "SP",
        "cod_municipio": "3550308",
        "geometry_wkb": g.wkb,
        "bbox_minx": minx,
        "bbox_miny": miny,
        "bbox_maxx": maxx,
        "bbox_maxy": maxy,
        "area_setor_m2": float(geom_m.area),
        "pop_total_setor_2022": pop,
        "domicilios_particulares_ocupados_setor_2022": 300.0,
        "renda_per_capita_setor_2022_calibrada": 2000.0,
        "score_setor_2022_calibrado": 60.0,
        "flag_geometria_valida": True,
    }


def _malha() -> pd.DataFrame:
    # Um setor grande cobrindo o raio de 2 km inteiro e um anel externo.
    return pd.DataFrame([_setor("CENTRO", box(-2500, -2500, 2500, 2500), pop=25_000.0)])


def test_metodo_do_raio() -> None:
    assert metodo_do_raio(1.0) == METODO_RELATORIO_PONTUAL_CENSITARIO
    assert metodo_do_raio(1) == METODO_RELATORIO_PONTUAL_CENSITARIO
    assert metodo_do_raio(2.0) == "setor_censitario_intersecao_area_2km"
    assert metodo_do_raio(1.5) == "setor_censitario_intersecao_area_1p5km"


def test_raio_de_2km_tem_metodo_proprio_e_fator_quatro() -> None:
    res = analisar_ponto_censitario_setores(LAT, LNG, _malha(), raio_km=2.0)
    assert res["metodo"] == "setor_censitario_intersecao_area_2km"
    assert res["raio_km"] == 2.0
    assert res["fator_regua"] == 4.0  # exato
    assert res["area_km2_exata"] == math.pi * 4.0
    assert res["area_km2"] == round(math.pi * 4.0, 2)
    assert "geometria_tipo" not in res  # raio nao e' geometria
    # Setor de 25 km2 com 25.000 hab: o disco de 4*pi km2 leva ~12.566.
    assert res["pop_total_raio"] == pytest.approx(25_000.0 * 4 * math.pi / 25.0, rel=0.01)


def test_raio_de_1km_sem_geometria_nao_ganha_chave() -> None:
    res = analisar_ponto_censitario_setores(LAT, LNG, _malha())
    assert "fator_regua" not in res
    assert "area_km2_exata" not in res
    assert res["metodo"] == METODO_RELATORIO_PONTUAL_CENSITARIO
    explicito = analisar_ponto_censitario_setores(LAT, LNG, _malha(), raio_km=1.0)
    assert set(explicito) == set(res)


def test_isocrona_no_motor_tem_metodo_proprio_e_fator_da_area() -> None:
    estrela = Polygon(
        [
            (0, 1800),
            (500, 300),
            (2000, 0),
            (500, -300),
            (0, -1800),
            (-500, -300),
            (-2000, 0),
            (-500, 300),
        ]
    )
    res = analisar_ponto_censitario_setores(
        LAT,
        LNG,
        _malha(),
        geometria_wgs84=_para_wgs(estrela),
        geometria_tipo=GEOMETRIA_TIPO_ISOCRONA_CARRO_10MIN,
    )
    assert res["metodo"] == METODO_RELATORIO_PONTUAL_ISOCRONA
    assert res["geometria_tipo"] == "isocrona_carro_10min"
    assert res["raio_km"] is None
    assert res["area_km2_exata"] == pytest.approx(estrela.area / 1e6, rel=1e-4)
    assert res["fator_regua"] == pytest.approx(res["area_km2_exata"] / math.pi, rel=1e-12)


def test_geometria_tipo_invalido_ou_sem_geometria_recusa() -> None:
    quadrado = _para_wgs(box(-500, -500, 500, 500))
    with pytest.raises(ValueError):
        analisar_ponto_censitario_setores(
            LAT, LNG, _malha(), geometria_wgs84=quadrado, geometria_tipo="raio_2km"
        )
    with pytest.raises(ValueError):
        analisar_ponto_censitario_setores(LAT, LNG, _malha(), geometria_tipo="poligono")


# --------------------------------------------------------------------------- #
# (c) isocrona                                                                 #
# --------------------------------------------------------------------------- #
def test_isocrona_monta_o_pedido_e_carimba(rotas) -> None:
    iso = ap.isocrona_carro(LAT, LNG)
    assert len(rotas.posts) == 1
    chamada = rotas.posts[0]
    assert chamada["url"] == URL + "/isochrone"
    assert chamada["timeout"] == (2, 15)
    assert chamada["json"] == {
        # `search_cutoff`: sem ele o Valhalla procura a via a ate' 35 km do clique.
        "locations": [{"lat": LAT, "lon": LNG, "search_cutoff": 300}],
        "costing": "auto",
        "contours": [{"time": 10}],
        "polygons": True,
        "denoise": 0.5,
        "generalize": 25,
    }
    assert iso.lat == LAT and iso.lng == LNG
    assert iso.geometria.covers(Point(LNG, LAT))
    assert iso.area_km2 == pytest.approx(math.pi * 9.0, rel=0.01)
    assert iso.fator_regua == pytest.approx(iso.area_km2 / math.pi)
    p = iso.parametros
    assert p == {
        "motor": "valhalla",
        "perfil": "auto",
        "minutos": 10,
        "trafego": False,
        "versao": "2025-10-09T08:53:20+00:00",
    }
    # Copia nova a cada leitura: o objeto mora num cache compartilhado.
    p["versao"] = "mexido"
    assert iso.parametros["versao"] != "mexido"


def test_multipolygon_com_buraco_e_aceito(rotas) -> None:
    com_buraco = Polygon(
        Point(0, 0).buffer(2500).exterior.coords,
        [Point(1200, 0).buffer(400).exterior.coords],
    )
    ilha = Point(5000, 5000).buffer(600)
    rotas.isocrona = _Resp(200, _feature_collection(MultiPolygon([com_buraco, ilha])))
    iso = ap.isocrona_carro(LAT, LNG)
    assert iso.geometria.geom_type == "MultiPolygon"
    assert sum(len(g.interiors) for g in iso.geometria.geoms) == 1
    assert iso.geometria.covers(Point(LNG, LAT))

    geo = ap.contorno_geojson(iso.geometria)
    assert geo["type"] == "MultiPolygon"
    assert len(geo["coordinates"]) == 2
    assert sum(len(p) for p in geo["coordinates"]) == 3  # 2 exteriores + 1 buraco
    x, y = geo["coordinates"][0][0][0]
    assert x == round(x, 6) and y == round(y, 6)
    assert -47 < x < -46 and -24 < y < -23  # (lng, lat)


def test_isocrona_entra_no_motor(rotas) -> None:
    rotas.isocrona = _Resp(200, _feature_collection(Point(0, 0).buffer(1500)))
    iso = ap.isocrona_carro(LAT, LNG)
    res = analisar_ponto_censitario_setores(
        iso.lat,
        iso.lng,
        _malha(),
        geometria_wgs84=iso.geometria,
        geometria_tipo=GEOMETRIA_TIPO_ISOCRONA_CARRO_10MIN,
    )
    # A area do motor e a da isocrona saem da MESMA projecao local: o fator bate.
    assert res["fator_regua"] == pytest.approx(iso.fator_regua, rel=1e-9)
    assert res["flag_setor_ponto_encontrado"] is True


def test_origem_fora_une_um_disco_em_volta_dela(rotas) -> None:
    # Contorno que comeca a 40 m da origem (o clique caiu no meio de uma quadra).
    rotas.isocrona = _Resp(200, _feature_collection(box(40, -1500, 3000, 1500)))
    iso = ap.isocrona_carro(LAT, LNG)
    assert iso.geometria.covers(Point(LNG, LAT))
    assert iso.area_km2 > 2.96 * 3.0  # o contorno original continua inteiro


def test_origem_a_200m_liga_o_clique_ao_contorno_numa_area_so(rotas) -> None:
    # Clique no meio de um lote grande, a 200 m da area alcancada: ainda "a partir do
    # ponto", e o recorte e' UMA area (faixa ate' o contorno), nao um disco solto ao lado.
    rotas.isocrona = _Resp(200, _feature_collection(box(200, -1500, 3200, 1500)))
    iso = ap.isocrona_carro(LAT, LNG)
    assert iso.geometria.covers(Point(LNG, LAT))
    assert iso.geometria.geom_type == "Polygon"


def test_origem_longe_da_area_alcancada_recusa_com_400(rotas) -> None:
    # Clique no meio de um lago: o Valhalla parte de uma via a 2 km. Unir um disco em volta
    # do clique daria "10 min a partir do ponto" sobre uma area que nao parte dele.
    rotas.isocrona = _Resp(200, _feature_collection(box(2000, -1500, 5000, 1500)))
    with pytest.raises(ap.AlcanceInvalido, match="300 m de qualquer rua") as exc:
        ap.isocrona_carro(LAT, LNG)
    assert "Use o raio" in str(exc.value)


def test_area_acima_do_teto_recusa(rotas) -> None:
    rotas.isocrona = _Resp(200, _feature_collection(Point(0, 0).buffer(8200)))  # ~211 km2
    with pytest.raises(ap.AlcanceInvalido, match="200 km²"):
        ap.isocrona_carro(LAT, LNG)


def test_diagonal_acima_do_teto_recusa(rotas) -> None:
    # Corredor de 45 km x 1 km = 45 km2: cabe na area, passa da diagonal de 40 km.
    rotas.isocrona = _Resp(200, _feature_collection(box(-22_500, -500, 22_500, 500)))
    with pytest.raises(ap.AlcanceInvalido, match="40 km"):
        ap.isocrona_carro(LAT, LNG)


def test_compacidade_nao_se_aplica(rotas) -> None:
    """Estrela fina ao longo de duas avenidas (compacidade << 0,02 do desenho a mao)."""
    cruz = box(-12_000, -40, 12_000, 40).union(box(-40, -12_000, 40, 12_000))
    assert 4 * math.pi * cruz.area / cruz.length**2 < 0.02
    rotas.isocrona = _Resp(200, _feature_collection(cruz))
    iso = ap.isocrona_carro(LAT, LNG)
    assert iso.area_km2 == pytest.approx(cruz.area / 1e6, rel=0.05)


def test_contorno_detalhado_e_simplificado_ate_o_teto(rotas) -> None:
    detalhado = Point(0, 0).buffer(3000, quad_segs=3000)  # ~12.000 vertices
    rotas.isocrona = _Resp(200, _feature_collection(detalhado))
    iso = ap.isocrona_carro(LAT, LNG)
    assert iso.n_vertices <= ap.MAX_VERTICES_ISOCRONA
    assert iso.area_km2 == pytest.approx(math.pi * 9.0, rel=0.01)


def test_env_vazia_e_indisponivel(monkeypatch) -> None:
    monkeypatch.delenv(ap.ENV_ROTAS, raising=False)
    chamou = []
    monkeypatch.setattr(requests, "post", lambda *a, **k: chamou.append(1))
    with pytest.raises(ap.RotasIndisponiveis) as exc:
        ap.isocrona_carro(LAT, LNG)
    assert str(exc.value) == ap.MSG_ROTAS_INDISPONIVEIS
    assert "indisponível" in str(exc.value)
    assert chamou == []


@pytest.mark.parametrize("status", [401, 403, 404, 405, 429])
def test_4xx_que_nao_e_400_e_configuracao_e_nao_o_ponto(rotas, status) -> None:
    # URL errada (404/405), proxy (401/403) ou limite (429): o servico nao avaliou o ponto.
    # Responder "nenhuma rua por perto" esconderia um `MOTOR_ROTAS_URL` errado.
    rotas.isocrona = _Resp(status, texto="Not Found")
    with pytest.raises(ap.RotasIndisponiveis) as exc:
        ap.isocrona_carro(LAT, LNG)
    assert str(exc.value) == ap.MSG_ROTAS_INDISPONIVEIS


@pytest.mark.parametrize(
    "falha",
    [
        requests.exceptions.ConnectTimeout("lento"),
        requests.exceptions.ReadTimeout("lento"),
        requests.exceptions.ConnectionError("fora"),
        _Resp(500, texto="erro interno"),
        _Resp(503, texto="ocupado"),
        _Resp(200, ValueError("nao e' json")),
        _Resp(200, {"sem": "features"}),
    ],
)
def test_falha_do_servico_e_indisponivel_nunca_raio(rotas, falha) -> None:
    rotas.isocrona = falha
    with pytest.raises(ap.RotasIndisponiveis) as exc:
        ap.isocrona_carro(LAT, LNG)
    assert str(exc.value) == ap.MSG_ROTAS_INDISPONIVEIS


@pytest.mark.parametrize(
    "resposta",
    [
        _Resp(400, {"error_code": 171}, texto="No suitable edges near location"),
        _Resp(200, {"type": "FeatureCollection", "features": []}),
    ],
)
def test_sem_via_por_perto_e_alcance_invalido(rotas, resposta) -> None:
    rotas.isocrona = resposta
    with pytest.raises(ap.AlcanceInvalido, match="Use o raio"):
        ap.isocrona_carro(LAT, LNG)


def test_cache_por_ponto_arredondado_e_falha_nao_memoizada(rotas) -> None:
    a = ap.isocrona_carro(LAT, LNG)
    b = ap.isocrona_carro(LAT + 1e-7, LNG - 1e-7)  # mesmo ponto a 5 casas
    assert a.geometria is b.geometria  # o MESMO contorno, do cache
    assert len(rotas.posts) == 1

    ap.limpar_cache()
    rotas.isocrona = requests.exceptions.ConnectionError("fora")
    with pytest.raises(ap.RotasIndisponiveis):
        ap.isocrona_carro(LAT, LNG)
    rotas.isocrona = _Resp(200, _feature_collection(Point(0, 0).buffer(2000)))
    assert ap.isocrona_carro(LAT, LNG).area_km2 == pytest.approx(math.pi * 4, rel=0.01)


def test_origem_devolvida_e_a_do_clique_e_nao_a_arredondada(rotas) -> None:
    # A tela grava a origem do payload e, ao voltar ao raio de 1 km, rele o ponto nela:
    # devolver a coordenada arredondada movia o ponto ate' ~0,5 m.
    lat, lng = LAT - 0.0000034, LNG + 0.0000041
    iso = ap.isocrona_carro(lat, lng)
    assert (iso.lat, iso.lng) == (lat, lng)
    assert rotas.posts[0]["json"]["locations"][0]["lat"] == round(lat, 5)  # a conta, arredondada
    assert iso.geometria.covers(Point(lng, lat))


def test_falha_do_status_fica_lembrada_e_nao_e_reconsultada_a_cada_clique(rotas) -> None:
    rotas.status = requests.exceptions.ReadTimeout("pendurado")
    assert ap.versao_rotas() is None
    assert ap.versao_rotas() is None
    ap.isocrona_carro(LAT, LNG)
    assert len(rotas.gets) == 1  # so' a primeira paga o timeout
    assert ap.TIMEOUT_STATUS_S[1] <= 2  # e a leitura e' curta: o carimbo e' opcional
    ap.limpar_cache()
    rotas.status = _Resp(200, {"version": "3.9.0"})
    assert ap.versao_rotas() == "3.9.0"


def test_status_fora_nao_derruba_a_isocrona(rotas) -> None:
    rotas.status = requests.exceptions.ConnectionError("fora")
    iso = ap.isocrona_carro(LAT, LNG)
    assert iso.parametros["versao"] is None
    assert ap.estado_rotas() == {"configurado": True, "responde": False, "versao": None}


def test_estado_rotas(rotas, monkeypatch) -> None:
    assert ap.estado_rotas() == {
        "configurado": True,
        "responde": True,
        "versao": "2025-10-09T08:53:20+00:00",
    }
    assert rotas.gets[0]["url"] == URL + "/status"
    monkeypatch.delenv(ap.ENV_ROTAS)
    assert ap.estado_rotas() == {"configurado": False, "responde": None, "versao": None}


def test_contorno_de_poligono_simples() -> None:
    geo = ap.contorno_geojson(box(-46.6, -23.6, -46.5, -23.5))
    assert geo["type"] == "Polygon"
    assert len(geo["coordinates"]) == 1
    with pytest.raises(ValueError):
        ap.contorno_geojson(Point(0, 0))


# --------------------------------------------------------------------------- #
# (d) carga de setores alcanca os vizinhos do raio pedido                      #
# --------------------------------------------------------------------------- #
class _MalhaFake:
    def __init__(self) -> None:
        self.alcances: list[float] = []

    def resolver(self, lat, lng):
        return ("SP", "3500002")

    def alcancados(self, lat, lng, alcance_km):
        self.alcances.append(alcance_km)
        vizinho = [("SP", "3500003")] if alcance_km > 2.0 else []
        return [("SP", "3500002"), *vizinho]


def test_malha_alcancada_usa_o_frame_do_raio_pedido() -> None:
    from motor_expansao.api import service
    from motor_expansao.dashboard.censo_map import alcance_do_frame_km

    malha = _MalhaFake()
    um = service._malha_alcancada(malha, LAT, LNG)
    dois = service._malha_alcancada(malha, LAT, LNG, raio_km=2.0)
    assert malha.alcances == [alcance_do_frame_km(1.0), alcance_do_frame_km(2.0)]
    assert malha.alcances[1] > 2.0
    assert ("SP", "3500003") in dois and ("SP", "3500003") not in um


def test_mapa_da_isocrona_alongada_carrega_o_vizinho_da_faixa_lateral_do_quadro() -> None:
    """O quadro do mapa do recorte e' esticado para a proporcao da figura (~1,7:1). Numa
    isocrona alongada no sentido norte-sul (15 x 8 km) ele vai bem alem do contorno nas
    laterais: o vizinho que so' toca essa faixa tem de ser carregado quando ha' MAPA, ou o
    choropleth do PDF sai com buraco. Sem mapa (a ficha), continua so' o poligono."""
    from shapely import STRtree

    from motor_expansao.api import service
    from motor_expansao.api.service import _MalhaMunicipal
    from motor_expansao.dashboard.censo_map import quadro_do_mapa_da_geometria

    isocrona = _para_wgs(box(-4_000, -7_500, 4_000, 7_500))
    quadro = quadro_do_mapa_da_geometria(LAT, LNG, isocrona)
    # Faixa lateral: a leste do contorno + margem de 0,5 km, mas dentro do quadro.
    lateral = _para_wgs(box(6_000, -2_000, 9_000, 2_000))
    assert not lateral.intersects(isocrona.buffer(0.01)), "premissa: fora do contorno+margem"
    assert lateral.intersects(quadro), "premissa: dentro do quadro do mapa"

    proprio = _para_wgs(box(-20_000, -20_000, 5_000, 20_000))
    geoms = [proprio, lateral]
    malha = _MalhaMunicipal(STRtree(geoms), [("SP", "ponto"), ("SP", "lateral")], geoms)

    sem_mapa = service._malha_alcancada(malha, LAT, LNG, geometria=isocrona)
    com_mapa = service._malha_alcancada(malha, LAT, LNG, geometria=isocrona, com_mapa=True)
    assert ("SP", "lateral") not in sem_mapa
    assert ("SP", "lateral") in com_mapa
    assert com_mapa[0] == ("SP", "ponto")  # o municipio do ponto segue primeiro


def test_quadro_do_mapa_e_o_mesmo_que_o_render_usa() -> None:
    """Fonte unica: o quadro em graus volta, projetado, ao `_frame_box_da_geometria`."""
    from motor_expansao.dashboard import censo_map

    contorno = box(-4_000, -7_500, 4_000, 7_500)
    quadro = censo_map.quadro_do_mapa_da_geometria(LAT, LNG, _para_wgs(contorno))
    esperado = censo_map._frame_box_da_geometria(
        contorno, censo_map.MAPA_WIDTH_PADRAO, censo_map.MAPA_HEIGHT_PADRAO
    )
    t = Transformer.from_crs(CRS_ORIGEM_CENSO, _local_metric_crs(LAT, LNG), always_xy=True)
    de_volta = transform(t.transform, quadro)
    assert de_volta.bounds == pytest.approx(esperado.bounds, abs=1.0)
    # E e' de fato mais largo que o contorno: e' a faixa que a carga perdia.
    assert esperado.bounds[2] > contorno.bounds[2] + 4_000


def test_resolver_e_carregar_repassa_o_raio_so_quando_vem(monkeypatch, tmp_path) -> None:
    from motor_expansao.api import service
    from motor_expansao.api.settings import Settings
    from motor_expansao.dashboard import data as dash_data

    chamadas: list[dict] = []

    def _alcancada(malha, lat, lng, **kw):
        chamadas.append(kw)
        return [("SP", "3500002"), ("SP", "3500003")] if kw.get("raio_km") else []

    lidos: list[str] = []

    def _ler(_dir, uf, cod):
        lidos.append(cod)
        return pd.DataFrame({"cod_municipio": [cod], "cod_setor": [f"{cod}01"]})

    monkeypatch.setattr(service, "_carregar_malha", lambda _s: _MalhaFake())
    monkeypatch.setattr(service, "_malha_alcancada", _alcancada)
    monkeypatch.setattr(dash_data, "read_censo_geo_partition", _ler)
    settings = Settings(ibge_dir=tmp_path, censo_geo_dir=tmp_path)

    _uf, _cod, so_ponto = service._resolver_e_carregar(LAT, LNG, settings)
    assert chamadas[-1] == {}  # sem kwarg: a chamada de sempre
    assert list(so_ponto["cod_municipio"]) == ["3500002"]

    _uf, _cod, com_raio = service._resolver_e_carregar(LAT, LNG, settings, raio_km=2.0)
    assert chamadas[-1] == {"raio_km": 2.0}
    assert list(com_raio["cod_municipio"]) == ["3500002", "3500003"]
