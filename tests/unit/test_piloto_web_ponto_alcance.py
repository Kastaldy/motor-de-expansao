"""`GET /api/ponto/alcance` -- o ALCANCE do ponto escolhido na ficha (DEC-074).

Raio de 1 km (o estudo de sempre), raio de 2 km e 10 min de carro (isocrona do Valhalla,
SEMPRE mockado aqui: nenhum teste depende do servico real). A rota roda de verdade: motor
censitario REAL sobre setores sinteticos e mercado REAL sobre um `data/staging` sintetico,
no molde de `test_piloto_web_ponto_geometria.py`. O que se trava:

- o `GET /api/ponto` nao muda: mesmas chaves, mesmas chamadas (sem kwarg novo), reguas
  com as constantes cruas;
- `raio_1km` pela rota nova = o MESMO conteudo do GET + o bloco `recorte` (fator 1.0);
- `raio_2km`: fator EXATAMENTE 4.0, "no raio de 2 km", reguas de total x4, gate do SAM
  x4, metodo `_2km` e carga de vizinhos pelo frame do raio de 2 km;
- `carro_10min`: origem = o ponto clicado, contorno GeoJSON, carimbo do calculo, nota da
  area (media dos setores) -- e, sem a env ou com o servico fora, 503 em portugues,
  NUNCA o raio de 1 km em silencio;
- o estudo da unidade Ultra so' no raio de 1 km (400);
- o semaforo das analises de area devolve 503 quando lotado;
- `/api/me` oferece os alcances do deploy e `/api/acessos/saude-artefatos` diz o estado
  do servico de rotas.
"""

from __future__ import annotations

import functools
import json
import math
import sys
import threading
from pathlib import Path

import h3
import pandas as pd
import pytest
from fastapi import HTTPException
from pyproj import Transformer
from shapely.geometry import Point, box, mapping
from shapely.ops import transform

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402

from motor_expansao.dashboard import alcance_ponto  # noqa: E402
from motor_expansao.dashboard.censo_point import (  # noqa: E402
    CRS_ORIGEM_CENSO,
    METODO_RELATORIO_PONTUAL_CENSITARIO,
    METODO_RELATORIO_PONTUAL_ISOCRONA,
    _local_metric_crs,
)
from motor_expansao.dashboard.mercado_raio import POP_MIN_SAM_GATE  # noqa: E402

LAT, LNG = -23.55, -46.63
URL_ROTAS = "http://valhalla.teste:8002"


def _wgs(local_geom):
    t = Transformer.from_crs(_local_metric_crs(LAT, LNG), CRS_ORIGEM_CENSO, always_xy=True)
    return transform(t.transform, local_geom)


def _latlng(x: float, y: float) -> tuple[float, float]:
    p = _wgs(Point(x, y))
    return p.y, p.x


@functools.lru_cache(maxsize=1)
def _setores() -> pd.DataFrame:
    """Grade 6 x 6 km de setores de 500 m, 1.600 habitantes cada: cobre o raio de 2 km
    inteiro (e a isocrona de teste), entao a populacao do recorte e' densidade x area.
    Em cache: montar a grade custa segundos e nenhum teste a altera."""
    recs = []
    passo, alcance = 500.0, 3000.0
    i = 0
    x = -alcance
    while x < alcance:
        y = -alcance
        while y < alcance:
            i += 1
            local = box(x, y, x + passo, y + passo)
            g = _wgs(local)
            minx, miny, maxx, maxy = g.bounds
            recs.append(
                {
                    "cod_setor": f"3550308{i:08d}",
                    "uf": "SP",
                    "cod_municipio": "3550308",
                    "nome_municipio": "São Paulo",
                    "area_setor_m2": float(local.area),
                    "geometry_wkb": g.wkb,
                    "bbox_minx": minx,
                    "bbox_miny": miny,
                    "bbox_maxx": maxx,
                    "bbox_maxy": maxy,
                    "pop_total_setor_2022": 1600.0,
                    "domicilios_particulares_ocupados_setor_2022": 520.0,
                    "renda_per_capita_setor_2022": 2000.0,
                    "renda_per_capita_setor_2022_calibrada": 2000.0,
                    "avg_moradores_domicilio_setor_2022": 3.0,
                    "renda_responsavel_media_setor_2022": 6000.0,
                    # Metade oeste 30, metade leste 80: a nota da AREA (media) cai entre as duas
                    # e a do setor do PONTO e' uma delas -- e' o que distingue as duas regras.
                    "score_setor_2022_calibrado": 30.0 if x < 0 else 80.0,
                    "flag_geometria_valida": True,
                }
            )
            y += passo
        x += passo
    return pd.DataFrame(recs)


def _staging(dir_: Path) -> None:
    dir_.mkdir(parents=True, exist_ok=True)
    cells = {h3.latlng_to_cell(*_latlng(x, y), 7) for x in (-800, 0, 800) for y in (-800, 0, 800)}
    pd.DataFrame(
        {
            "hex_id": sorted(cells),
            "faixa_oportunidade": ["prioridade_maxima"] * len(cells),
            "taxa_fitness_mercado_calibrada": [0.2] * len(cells),
            "sam_fitness_potencial": [10_000.0] * len(cells),
            "oferta_efetiva_disponivel": [0.0] * len(cells),
            "score_oportunidade_residual": [0.0] * len(cells),
            "oferta_consumida_mercado_estimada": [0.0] * len(cells),
            "oferta_consumida_ultra_estimada": [0.0] * len(cells),
        }
    ).to_parquet(dir_ / "hexagonos_mercado_mapeado.parquet", index=False)
    perto = _latlng(500, 0)
    pd.DataFrame(
        {
            "concorrente_id": ["c1"],
            "rede": ["smart_fit"],
            "lat": [perto[0]],
            "lng": [perto[1]],
            "status_registro": ["valido"],
        }
    ).to_parquet(dir_ / "concorrentes_mapeados.parquet", index=False)
    longe = _latlng(9000, 9000)
    pd.DataFrame(
        {
            "lat": [longe[0]],
            "lng": [longe[1]],
            "flag_coord_valida": [True],
        }
    ).to_parquet(dir_ / "unidades_ultra_mapeadas.parquet", index=False)


@pytest.fixture
def ambiente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Carga e concorrentes stub; motor e mercado REAIS. Devolve os kwargs de cada carga."""
    from motor_expansao.api import service as api_service
    from motor_expansao.dashboard import mercado_raio

    setores = _setores()
    chamadas: list[dict] = []

    def _carregar(lat, lng, cfg, **kw):
        chamadas.append(kw)
        return ("SP", "3550308", setores)

    monkeypatch.setattr(api_service, "_resolver_e_carregar", _carregar)
    a_500m = _latlng(500, 0)
    a_1500m = _latlng(1500, 0)
    comp = pd.DataFrame(
        {
            "rede": ["perto", "fora_do_1km"],
            "classe": ["cadeia", "cadeia"],
            "lat": [a_500m[0], a_1500m[0]],
            "lng": [a_500m[1], a_1500m[1]],
        }
    )
    monkeypatch.setattr(api_service, "_competitors_ultra", lambda cfg: (comp, None))
    staging = tmp_path / "staging"
    _staging(staging)
    monkeypatch.setattr(pilot, "STAGING_DIR", staging)
    monkeypatch.delenv(alcance_ponto.ENV_ROTAS, raising=False)
    mercado_raio.carregar_cadeias_mercado.cache_clear()
    mercado_raio.carregar_ultra_mercado.cache_clear()
    alcance_ponto.limpar_cache()
    yield chamadas
    mercado_raio.carregar_cadeias_mercado.cache_clear()
    mercado_raio.carregar_ultra_mercado.cache_clear()
    alcance_ponto.limpar_cache()


# --------------------------------------------------------------------------- #
# Valhalla de mentira                                                          #
# --------------------------------------------------------------------------- #
class _Resp:
    def __init__(self, status: int, corpo) -> None:
        self.status_code = status
        self._corpo = corpo
        self.text = json.dumps(corpo) if not isinstance(corpo, str) else corpo

    def json(self):
        if isinstance(self._corpo, str):
            raise ValueError("nao e' JSON")
        return self._corpo

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


# A "isocrona" de teste: retangulo de 3 x 2 km deslocado para LESTE (de -500 a 2.500 m em
# x): a origem fica dentro, mas o recorte e' assimetrico -- a media dos setores (mais
# leste, nota 80) se afasta da nota do setor do ponto.
_ISO_LOCAL = box(-500, -1000, 2500, 1000)


@pytest.fixture
def valhalla(monkeypatch: pytest.MonkeyPatch):
    """Liga a env e troca `requests.post/get`. Devolve a lista de corpos de POST enviados;
    `estado["post"]` troca a resposta (ou a excecao) do proximo POST."""
    import requests

    monkeypatch.setenv(alcance_ponto.ENV_ROTAS, URL_ROTAS)
    enviados: list[dict] = []
    estado: dict = {
        "post": _Resp(
            200,
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"contour": 10},
                        "geometry": mapping(_wgs(_ISO_LOCAL)),
                    }
                ],
            },
        ),
    }

    def _post(url, json=None, timeout=None):  # noqa: A002 - assinatura do requests
        assert url == f"{URL_ROTAS}/isochrone"
        enviados.append(json)
        r = estado["post"]
        if isinstance(r, BaseException):
            raise r
        return r

    def _get(url, timeout=None):
        assert url == f"{URL_ROTAS}/status"
        return _Resp(200, {"version": "3.9.0"})

    monkeypatch.setattr(requests, "post", _post)
    monkeypatch.setattr(requests, "get", _get)
    alcance_ponto.limpar_cache()
    yield enviados, estado
    alcance_ponto.limpar_cache()


def _alcance(alcance: str, **kw) -> dict:
    return pilot.ponto_alcance(lat=LAT, lng=LNG, alcance=alcance, **kw)


def _dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


# --------------------------------------------------------------------------- #
# Fator 1: o GET e o raio de 1 km nao mudam                                    #
# --------------------------------------------------------------------------- #
_CHAVES_DO_GET = {
    "lat",
    "lng",
    "raio_km",
    "hex_id",
    "local",
    "censo",
    "concorrencia",
    "mercado",
    "vizinhos",
    "reguas",
    "criterios",
    "renda_meta",
}


def test_get_api_ponto_nao_ganha_chave_nem_kwarg(ambiente, monkeypatch) -> None:
    """O GET de sempre: chaves de sempre, reguas CRUAS (mesmo tipo inteiro do perfil) e as
    tres chamadas pesadas sem kwarg novo -- carga, motor e mercado."""
    from motor_expansao.api import service as api_service
    from motor_expansao.dashboard import censo_point

    motor_real = censo_point.analisar_ponto_censitario_setores
    mercado_real = api_service._mercado_do_ponto
    kw_motor: list[dict] = []
    kw_mercado: list[dict] = []

    def _motor(*a, **k):
        kw_motor.append(k)
        return motor_real(*a, **k)

    def _mercado(*a, **k):
        kw_mercado.append(k)
        return mercado_real(*a, **k)

    monkeypatch.setattr(censo_point, "analisar_ponto_censitario_setores", _motor)
    monkeypatch.setattr(api_service, "_mercado_do_ponto", _mercado)

    body = pilot.ponto(lat=LAT, lng=LNG)
    assert set(body) == _CHAVES_DO_GET
    assert body["raio_km"] == 1.0
    from motor_expansao.renda import renda_meta

    assert body["renda_meta"] == renda_meta()  # E0: proveniencia da renda do `censo`
    assert ambiente == [{}]
    assert set(kw_motor[0]) == {"raio_km", "competitors_df", "ultra_df"}
    assert kw_motor[0]["raio_km"] == 1.0
    assert kw_mercado == [{}]
    reguas = body["reguas"]
    assert "fator_regua" not in reguas
    assert reguas["pop_minima"] is pilot.POP_MIN_ACIONAVEL
    assert reguas["conc_regiao_disputada"] is pilot.CRIT_PONTO_CONC_MAX
    assert body["mercado"]["gate"]["pop_minima"] == POP_MIN_SAM_GATE
    assert isinstance(body["mercado"]["gate"]["pop_minima"], int)
    rotulos = {c["chave"]: c["rotulo"] for c in body["criterios"]}
    assert rotulos["populacao"] == "População no raio"
    reg = {c["chave"]: c["regua"] for c in body["criterios"]}
    assert reg["populacao"] == pilot.POP_MIN_ACIONAVEL
    assert reg["concorrentes"] == pilot.CRIT_PONTO_CONC_MAX


def test_raio_1km_pela_rota_nova_e_o_get_mais_o_recorte(ambiente) -> None:
    get = pilot.ponto(lat=LAT, lng=LNG)
    novo = _alcance("raio_1km")
    recorte = novo.pop("recorte")
    # Byte a byte, fora o bloco `recorte`.
    assert _dump(novo) == _dump(get)
    assert recorte["tipo"] == "raio_1km"
    assert recorte["fator_regua"] == 1.0 and type(recorte["fator_regua"]) is float
    assert recorte["metodo"] == METODO_RELATORIO_PONTUAL_CENSITARIO
    assert recorte["area_km2"] == 3.14
    assert recorte["contorno"] is None
    assert recorte["origem"] == {"lat": LAT, "lng": LNG}
    assert recorte["parametros"] is None
    # A carga das DUAS chamadas foi a de sempre.
    assert ambiente == [{}, {}]


def test_raio_1km_pela_rota_nova_aceita_o_estudo_da_unidade(ambiente, monkeypatch) -> None:
    """O modo Ultra vale no raio de 1 km: a rota nova repassa o pedido ao GET de sempre."""
    vistos: list[bool] = []

    def _payload(lat, lng, **kw):
        vistos.append(kw.get("excluir_ultra_proxima", False))
        return {"lat": lat}

    monkeypatch.setattr(pilot, "_payload_ponto", _payload)
    _alcance("raio_1km", excluir_ultra_proxima=True)
    assert vistos == [True]


def test_reguas_de_total_fator_1_devolve_as_constantes_cruas() -> None:
    pop, residual, conc = pilot._reguas_de_total(1.0)
    assert pop is pilot.POP_MIN_ACIONAVEL
    assert residual is pilot.OFERTA_DESTAQUE_MIN
    assert conc is pilot.CRIT_PONTO_CONC_MAX


def test_reguas_de_total_escalam_so_os_totais() -> None:
    pop, residual, conc = pilot._reguas_de_total(4.0)
    assert pop == pilot.POP_MIN_ACIONAVEL * 4
    assert residual == pilot.OFERTA_DESTAQUE_MIN * 4
    assert conc == 12
    # Contagem: arredonda, e nunca abaixo de 1 (teto 0 reprovaria qualquer praca).
    assert pilot._reguas_de_total(0.1)[2] == 1
    assert pilot._reguas_de_total(1.2)[2] == round(3 * 1.2)


# --------------------------------------------------------------------------- #
# Raio de 2 km                                                                 #
# --------------------------------------------------------------------------- #
def test_raio_2km_escala_por_4_e_diz_o_recorte(ambiente) -> None:
    um = pilot.ponto(lat=LAT, lng=LNG)
    body = _alcance("raio_2km")

    assert body["lat"] == LAT and body["lng"] == LNG
    assert body["raio_km"] == 2.0
    recorte = body["recorte"]
    assert recorte["tipo"] == "raio_2km"
    assert recorte["fator_regua"] == 4.0  # EXATO, do raio e nao da area poligonizada
    assert recorte["metodo"] == "setor_censitario_intersecao_area_2km"
    assert recorte["area_km2"] == round(math.pi * 4, 2)
    assert recorte["contorno"] is None  # a tela gera o circulo
    assert recorte["origem"] == {"lat": LAT, "lng": LNG}

    # A populacao do raio de 2 km e' ~4x a do de 1 km (densidade uniforme).
    assert body["censo"]["populacao"] == pytest.approx(4 * um["censo"]["populacao"], rel=0.02)
    # O concorrente a 1,5 km entra no raio de 2 km e nao no de 1 km.
    assert um["concorrencia"]["n_concorrentes"] == 1
    assert body["concorrencia"]["n_concorrentes"] == 2

    # Reguas de TOTAL x4; as de MEDIA intactas.
    reguas = body["reguas"]
    assert reguas["fator_regua"] == 4.0
    assert reguas["pop_minima"] == 4 * pilot.POP_MIN_ACIONAVEL
    assert reguas["conc_regiao_disputada"] == 12
    assert reguas["score_minimo"] == um["reguas"]["score_minimo"]
    assert reguas["renda_domiciliar_minima"] == um["reguas"]["renda_domiciliar_minima"]
    crit = {c["chave"]: c for c in body["criterios"]}
    assert crit["populacao"]["rotulo"] == "População no raio de 2 km"
    assert crit["concorrentes"]["rotulo"] == "Concorrentes de rede no raio de 2 km"
    assert crit["populacao"]["regua"] == 4 * pilot.POP_MIN_ACIONAVEL
    assert crit["residual"]["regua"] == 4 * pilot.OFERTA_DESTAQUE_MIN
    assert crit["concorrentes"]["regua"] == 12
    assert (
        crit["renda_domiciliar"]["regua"]
        == {c["chave"]: c for c in um["criterios"]}["renda_domiciliar"]["regua"]
    )

    # Mercado no MESMO raio, com o gate do SAM escalado pelo MESMO fator.
    m = body["mercado"]
    assert m["grao"] == "raio" and m["raio_km"] == 2.0
    assert m["gate"]["pop_minima"] == 4 * POP_MIN_SAM_GATE

    # Raio: a nota segue sendo a do setor do PONTO.
    assert (
        body["censo"]["score_socioeconomico"] == body["censo"]["detalhe"]["setor_do_ponto"]["score"]
    )

    # Os vizinhos foram carregados pelo frame do raio de 2 km (classe DEC-065).
    assert ambiente[-1] == {"raio_km": 2.0}


def test_raio_2km_recusa_o_estudo_da_unidade_ultra(ambiente) -> None:
    with pytest.raises(HTTPException) as exc:
        _alcance("raio_2km", excluir_ultra_proxima=True)
    assert exc.value.status_code == 400
    assert "só do raio de 1 km" in exc.value.detail
    assert ambiente == []


def test_alcance_desconhecido_e_400_em_portugues(ambiente) -> None:
    with pytest.raises(HTTPException) as exc:
        _alcance("raio_5km")
    assert exc.value.status_code == 400
    assert "Alcance desconhecido" in exc.value.detail
    assert ambiente == []


# --------------------------------------------------------------------------- #
# 10 min de carro                                                              #
# --------------------------------------------------------------------------- #
def test_carro_10min_devolve_a_origem_clicada_sem_arredondar(ambiente, valhalla) -> None:
    # A tela grava a origem do payload e rele o raio de 1 km nela ao voltar: com a origem
    # arredondada a 5 casas (a chave do cache), o ponto andava ate' ~0,5 m.
    lat, lng = LAT - 0.0000034, LNG + 0.0000041
    body = pilot.ponto_alcance(lat=lat, lng=lng, alcance="carro_10min")
    # A MESMA coordenada que o `GET /api/ponto` devolve para este clique (6 casas, ~0,1 m):
    # e' a que a tela rele ao voltar para o raio de 1 km.
    assert (body["lat"], body["lng"]) == (round(lat, 6), round(lng, 6))
    assert body["recorte"]["origem"] == {"lat": round(lat, 6), "lng": round(lng, 6)}
    assert round(lat, 6) != round(lat, 5)  # o caso testado distingue as duas


def test_carro_10min_le_a_isocrona_com_origem_no_ponto_clicado(ambiente, valhalla) -> None:
    enviados, _ = valhalla
    body = _alcance("carro_10min")

    # O pedido ao servico: a origem, carro, 10 min, poligonos.
    assert len(enviados) == 1
    pedido = enviados[0]
    assert pedido["locations"] == [{"lat": LAT, "lon": LNG, "search_cutoff": 300}]
    assert pedido["costing"] == "auto"
    assert pedido["contours"] == [{"time": 10}]
    assert pedido["polygons"] is True

    # A ORIGEM e' o ponto clicado (nao um ponto interno calculado).
    assert body["lat"] == round(LAT, 5) and body["lng"] == round(LNG, 5)
    assert body["raio_km"] is None
    assert "geometria" not in body  # o anel unico do desenho nao cabe MultiPolygon

    recorte = body["recorte"]
    assert recorte["tipo"] == "carro_10min"
    assert recorte["metodo"] == METODO_RELATORIO_PONTUAL_ISOCRONA
    assert recorte["origem"] == {"lat": round(LAT, 5), "lng": round(LNG, 5)}
    assert recorte["contorno"]["type"] in ("Polygon", "MultiPolygon")
    assert recorte["parametros"] == {
        "motor": "valhalla",
        "perfil": "auto",
        "minutos": 10,
        "trafego": False,
        "versao": "3.9.0",
    }
    area = _ISO_LOCAL.area / 1e6  # 6 km2 (a simplificacao nao mexe num retangulo)
    assert recorte["area_km2"] == pytest.approx(area, rel=0.01)
    assert recorte["fator_regua"] == pytest.approx(area / math.pi, rel=0.01)

    fator = recorte["fator_regua"]
    assert body["reguas"]["fator_regua"] == fator
    crit = {c["chave"]: c for c in body["criterios"]}
    assert crit["populacao"]["rotulo"] == "População em 10 min de carro"
    assert crit["populacao"]["regua"] == round(pilot.POP_MIN_ACIONAVEL * fator)

    # Mercado e gate no MESMO poligono e pelo MESMO fator.
    m = body["mercado"]
    assert m["grao"] == "geometria" and m["raio_km"] is None
    assert m["gate"]["pop_minima"] == pytest.approx(POP_MIN_SAM_GATE * fator)

    # Isocrona: nota da AREA (media dos setores), como no desenho -- nao a do ponto.
    detalhe = body["censo"]["detalhe"]
    assert body["censo"]["score_socioeconomico"] == detalhe["score_medio_raio"]
    assert body["censo"]["score_socioeconomico"] != detalhe["setor_do_ponto"]["score"]

    # A carga alcancou os vizinhos pelo poligono.
    assert set(ambiente[-1]) == {"geometria"}


def test_carro_10min_sem_env_e_503_e_nao_cai_para_o_raio(ambiente) -> None:
    with pytest.raises(HTTPException) as exc:
        _alcance("carro_10min")
    assert exc.value.status_code == 503
    assert exc.value.detail == alcance_ponto.MSG_ROTAS_INDISPONIVEIS
    assert "indisponível" in exc.value.detail
    assert ambiente == [], "nenhuma particao lida: o raio de 1 km NAO e' o plano B"


def test_carro_10min_com_servico_lento_e_503(ambiente, valhalla) -> None:
    import requests

    _, estado = valhalla
    estado["post"] = requests.exceptions.ReadTimeout("lento")
    with pytest.raises(HTTPException) as exc:
        _alcance("carro_10min")
    assert exc.value.status_code == 503
    assert exc.value.detail == alcance_ponto.MSG_ROTAS_INDISPONIVEIS
    assert ambiente == []


def test_carro_10min_sem_via_por_perto_e_400(ambiente, valhalla) -> None:
    _, estado = valhalla
    estado["post"] = _Resp(400, {"error": "No suitable edges near location"})
    with pytest.raises(HTTPException) as exc:
        _alcance("carro_10min")
    assert exc.value.status_code == 400
    assert "Use o raio" in exc.value.detail
    assert ambiente == []


def test_carro_10min_recusa_o_estudo_da_unidade_antes_de_chamar_o_servico(
    ambiente, valhalla
) -> None:
    enviados, _ = valhalla
    with pytest.raises(HTTPException) as exc:
        _alcance("carro_10min", excluir_ultra_proxima=True)
    assert exc.value.status_code == 400
    assert enviados == []


def test_coordenada_fora_do_pais_nao_chama_o_servico(ambiente, valhalla) -> None:
    enviados, _ = valhalla
    with pytest.raises(HTTPException) as exc:
        pilot.ponto_alcance(lat=10.0, lng=LNG, alcance="carro_10min")
    assert exc.value.status_code == 400
    assert enviados == []


# --------------------------------------------------------------------------- #
# Area desenhada: fase 2                                                       #
# --------------------------------------------------------------------------- #
def test_area_desenhada_ganha_fator_e_contorno_e_reguas_escaladas(ambiente) -> None:
    lado = 2000.0
    g = _wgs(box(-lado / 2, -lado / 2, lado / 2, lado / 2))
    geojson = {"type": "Polygon", "coordinates": [[list(c) for c in g.exterior.coords]]}
    body = pilot.ponto_geometria(pilot.PontoGeometriaIn(geometria=geojson))

    recorte = body["recorte"]
    assert recorte["tipo"] == "poligono"
    fator = recorte["fator_regua"]
    assert fator == pytest.approx(4.0 / math.pi, rel=0.01)
    assert recorte["contorno"]["type"] == "Polygon"
    assert len(recorte["contorno"]["coordinates"][0]) == 5
    assert body["reguas"]["fator_regua"] == fator
    crit = {c["chave"]: c for c in body["criterios"]}
    assert crit["populacao"]["regua"] == round(pilot.POP_MIN_ACIONAVEL * fator)
    assert crit["populacao"]["rotulo"] == "População na área"
    assert body["mercado"]["gate"]["pop_minima"] == pytest.approx(POP_MIN_SAM_GATE * fator)


# --------------------------------------------------------------------------- #
# Semaforo das analises de area                                                #
# --------------------------------------------------------------------------- #
def test_semaforo_lotado_devolve_503_e_o_raio_de_1km_segue_livre(ambiente, monkeypatch) -> None:
    lotado = threading.BoundedSemaphore(1)
    assert lotado.acquire(blocking=False)
    monkeypatch.setattr(pilot, "_AREA_SEMAFORO", lotado)
    monkeypatch.setattr(pilot, "_AREA_ESPERA_S", 0.01)

    with pytest.raises(HTTPException) as exc:
        _alcance("raio_2km")
    assert exc.value.status_code == 503
    assert exc.value.detail == pilot.MSG_AREA_OCUPADA

    g = _wgs(box(-500, -500, 500, 500))
    geojson = {"type": "Polygon", "coordinates": [[list(c) for c in g.exterior.coords]]}
    with pytest.raises(HTTPException) as exc:
        pilot.ponto_geometria(pilot.PontoGeometriaIn(geometria=geojson))
    assert exc.value.status_code == 503
    assert ambiente == [], "nada carregado com a fila cheia"

    # O estudo de sempre nao disputa a vaga.
    assert _alcance("raio_1km")["raio_km"] == 1.0


def test_semaforo_devolve_a_vaga_mesmo_quando_a_analise_falha(ambiente, monkeypatch) -> None:
    sem = threading.BoundedSemaphore(1)
    monkeypatch.setattr(pilot, "_AREA_SEMAFORO", sem)

    def _explode(*_a, **_k):
        raise HTTPException(400, "falhou")

    monkeypatch.setattr(pilot, "_payload_ponto", _explode)
    with pytest.raises(HTTPException):
        _alcance("raio_2km")
    assert sem.acquire(blocking=False), "a vaga vazou"


def test_teto_de_concorrencia_segue_o_perfil() -> None:
    assert pilot._AREA_CONCORRENCIA_MAX == min(2, pilot._PDF_CONCORRENCIA_MAX)
    assert pilot._AREA_CONCORRENCIA_MAX >= 1


def test_rota_nova_cai_no_gate_do_api_ponto() -> None:
    import acesso

    assert acesso.abas_necessarias("/api/ponto/alcance") == acesso.abas_necessarias("/api/ponto")
    assert acesso.rota_exige_malha_municipal("/api/ponto/alcance")
    assert acesso.capacidade_necessaria("/api/ponto/alcance", "GET") == "ponto.analisar"


# --------------------------------------------------------------------------- #
# /api/me e diagnostico                                                         #
# --------------------------------------------------------------------------- #
def test_me_oferece_os_dois_raios_sem_o_servico_de_rotas(monkeypatch) -> None:
    monkeypatch.delenv(alcance_ponto.ENV_ROTAS, raising=False)
    assert pilot.me(remote_user=None)["alcances"] == ["raio_1km", "raio_2km"]


def test_me_oferece_os_10_min_de_carro_com_a_env(monkeypatch) -> None:
    monkeypatch.setenv(alcance_ponto.ENV_ROTAS, URL_ROTAS)
    assert pilot.me(remote_user=None)["alcances"] == ["raio_1km", "raio_2km", "carro_10min"]


def test_env_vazia_conta_como_ausente(monkeypatch) -> None:
    monkeypatch.setenv(alcance_ponto.ENV_ROTAS, "   ")
    assert "carro_10min" not in pilot.me(remote_user=None)["alcances"]


def test_saude_artefatos_diz_o_estado_do_servico_de_rotas(monkeypatch, valhalla) -> None:
    monkeypatch.setattr(pilot, "_exigir_admin_acessos", lambda u: None)
    monkeypatch.setattr(pilot, "_inventario_artefatos", lambda: {"status": "ok"})
    monkeypatch.setattr(pilot, "_saude_do_banco", lambda: {"configurado": False})
    inv = pilot.acessos_saude_artefatos(remote_user="admin")
    assert inv["rotas"] == {"configurado": True, "responde": True, "versao": "3.9.0"}

    monkeypatch.delenv(alcance_ponto.ENV_ROTAS)
    inv = pilot.acessos_saude_artefatos(remote_user="admin")
    assert inv["rotas"] == {"configurado": False, "responde": None, "versao": None}


def test_health_publico_nao_consulta_o_servico_de_rotas() -> None:
    import inspect

    assert "estado_rotas" not in inspect.getsource(pilot.health)
