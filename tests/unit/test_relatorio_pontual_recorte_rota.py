"""O Estudo do RECORTE: `alcance`/`geometria` em `POST /api/relatorio/pontual` (DEC-074).

Fase 2 da DEC-071: o botao "Estudo" (PDF so' demografico) passa a valer para a area
desenhada, o raio de 2 km e os 10 min de carro. ESPIOES em cada colaborador pesado (carga,
motor, mapas, mercado, gerador): o que se trava e' o que a rota ENTREGA a cada um -- o
desenho dos textos e das metas no PDF e' do `censo_report` e tem teste proprio. Travas:

- sem os campos, nenhuma chamada ganha kwarg novo (o PDF de sempre);
- o recorte so' existe no Estudo; com os dois campos, sem `so_estudo` ou com o estudo da
  unidade Ultra na AREA DESENHADA -> 400 em portugues, ANTES de registrar o relatorio;
- o estudo da unidade Ultra vale no raio de 2 km e nos 5/10 min de carro e o mercado do PDF
  e' medido NO recorte, sem a unidade (emenda do item 6 da DEC-074, 2026-10-21);
- o servidor RECALCULA o recorte: a isocrona sai do servico de rotas (mockado), o desenho
  passa pelo validador da ficha -- e o PDF roda na origem/ponto interno dele;
- servico de rotas fora -> 503, nunca o raio de 1 km em silencio;
- os campos sao do CORPO multipart (Form), nao da query;
- o deck de comparacao aceita o recorte por item e o repassa ao gerador.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import math
import sys
from pathlib import Path

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

from motor_expansao.dashboard import alcance_ponto, censo_report  # noqa: E402
from motor_expansao.dashboard.censo_point import (  # noqa: E402
    CRS_ORIGEM_CENSO,
    GEOMETRIA_TIPO_ISOCRONA_CARRO_10MIN,
    GEOMETRIA_TIPO_POLIGONO,
    _local_metric_crs,
)

_LAT, _LNG = -23.55, -46.63
_URL_ROTAS = "http://valhalla.teste:8002"

_MERCADO = {
    "grao": "raio",
    "sam_fitness_potencial": 3_000.0,
    "oferta_consumida_mercado_estimada": 1_200.0,
    "oferta_consumida_ultra_estimada": 300.0,
    "oferta_consumida_total_estimada": 1_500.0,
    "oferta_efetiva_disponivel": 1_500.0,
    "score_oportunidade_residual": 60.0,
}


def _wgs(local_geom):
    t = Transformer.from_crs(_local_metric_crs(_LAT, _LNG), CRS_ORIGEM_CENSO, always_xy=True)
    return transform(t.transform, local_geom)


def _point_app_at(monkeypatch: pytest.MonkeyPatch, data_dir: Path) -> None:
    outputs = data_dir / "outputs"
    monkeypatch.setattr(pilot, "DATA_DIR", data_dir)
    monkeypatch.setattr(pilot, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(pilot, "STAGING_DIR", data_dir / "staging")
    monkeypatch.setattr(pilot, "IBGE_DIR", data_dir / "ibge")
    monkeypatch.setattr(pilot, "ULTRA_DIR", data_dir / "ultra")
    monkeypatch.setattr(pilot, "CENSO_GEO_DIR", outputs / "setores_censitarios_2022_geo")


def _resultado_do_motor(lat, lng, raio_km=1.0, geometria_wgs84=None, geometria_tipo=None):
    """O dict que o motor REAL devolve nas chaves que a rota le: no raio de 1 km sem
    `fator_regua`/`area_km2_exata`; fora dele, com as duas (contrato do motor, DEC-074)."""
    out = {"lat": lat, "lng": lng, "nome_municipio": "SAO PAULO", "uf": "SP"}
    if geometria_wgs84 is not None:
        area = 6.0
        out.update(
            {
                "raio_km": None,
                "geometria_tipo": geometria_tipo or "poligono",
                "area_km2": round(area, 2),
                "area_km2_exata": area,
                "fator_regua": area / math.pi,
            }
        )
    else:
        out["raio_km"] = raio_km
        if raio_km != 1.0:
            out.update({"area_km2_exata": math.pi * raio_km**2, "fator_regua": raio_km**2})
    return out


@pytest.fixture
def espioes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Todo colaborador pesado vira espiao. Devolve {nome: [(args, kwargs), ...]}."""
    (tmp_path / "outputs" / "setores_censitarios_2022_geo").mkdir(parents=True)
    _point_app_at(monkeypatch, tmp_path)

    from motor_expansao.api import service as api_service
    from motor_expansao.dashboard import censo_map, censo_point, censo_report

    visto: dict[str, list] = {
        k: [] for k in ("carga", "motor", "mapas", "mercado", "gerador", "registro")
    }
    setores = pd.DataFrame({"cod_setor": ["355030801000001"], "nome_municipio": ["SAO PAULO"]})

    def _carga(lat, lng, cfg, **kw):
        visto["carga"].append(((lat, lng), kw))
        return ("SP", "3550308", setores)

    def _motor(lat, lng, df, **kw):
        visto["motor"].append(((lat, lng), kw))
        return _resultado_do_motor(
            lat,
            lng,
            **{k: kw[k] for k in ("raio_km", "geometria_wgs84", "geometria_tipo") if k in kw},
        )

    def _mapas(lat, lng, df, **kw):
        visto["mapas"].append(((lat, lng), kw))
        return None

    def _mercado(lat, lng, cfg, pop, **kw):
        visto["mercado"].append(((lat, lng), kw))
        return dict(_MERCADO)

    def _gerar(result, mapas, **kw):
        visto["gerador"].append(((result,), kw))
        return b"%PDF-1.4 stub"

    def _registrar(*a, **k):
        visto["registro"].append(k)
        return "rid-teste"

    monkeypatch.setattr(api_service, "_resolver_e_carregar", _carga)
    monkeypatch.setattr(api_service, "_competitors_ultra", lambda cfg: (None, None))
    monkeypatch.setattr(api_service, "_nome_municipio_de", lambda df: "SAO PAULO")
    monkeypatch.setattr(api_service, "_mercado_do_ponto", _mercado)
    monkeypatch.setattr(censo_point, "analisar_ponto_censitario_setores", _motor)
    monkeypatch.setattr(censo_point, "agregar_perfil_bairro_distrito", lambda *a, **k: None)
    monkeypatch.setattr(censo_map, "render_mapas_censitarios_combinados", _mapas)
    monkeypatch.setattr(censo_map, "render_foto_satelite_ponto", lambda *a, **k: None)
    monkeypatch.setattr(censo_map, "_BASEMAP_CACHE_DIR", censo_map._BASEMAP_CACHE_DIR)
    monkeypatch.setattr(censo_report, "gerar_pdf_relatorio_pontual_classico", _gerar)
    monkeypatch.setattr(pilot, "_praca_para_pdf", lambda *a, **k: None)
    monkeypatch.setattr(pilot, "_registrar_relatorio_gerado", _registrar)
    monkeypatch.delenv(alcance_ponto.ENV_ROTAS, raising=False)
    alcance_ponto.limpar_cache()
    yield visto
    alcance_ponto.limpar_cache()


class _Resp:
    def __init__(self, status: int, corpo) -> None:
        self.status_code = status
        self._corpo = corpo
        self.text = json.dumps(corpo)

    def json(self):
        return self._corpo

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


_ISO_LOCAL = box(-500, -1000, 2500, 1000)


@pytest.fixture
def valhalla(monkeypatch: pytest.MonkeyPatch) -> list:
    import requests

    monkeypatch.setenv(alcance_ponto.ENV_ROTAS, _URL_ROTAS)
    enviados: list = []

    def _post(url, json=None, timeout=None):  # noqa: A002 - assinatura do requests
        enviados.append(json)
        return _Resp(
            200,
            {
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "geometry": mapping(_wgs(_ISO_LOCAL))}],
            },
        )

    monkeypatch.setattr(requests, "post", _post)
    monkeypatch.setattr(requests, "get", lambda url, timeout=None: _Resp(200, {"version": "3.9.0"}))
    alcance_ponto.limpar_cache()
    return enviados


def _rota(**kwargs):
    return asyncio.run(pilot.relatorio_pontual(lat=_LAT, lng=_LNG, **kwargs))


def _kw(visto: dict, nome: str) -> dict:
    assert visto[nome], f"{nome} nao foi chamado"
    return visto[nome][-1][1]


def _desenho_geojson() -> str:
    g = _wgs(box(-1000, -1000, 1000, 1000))
    return json.dumps({"type": "Polygon", "coordinates": [[list(c) for c in g.exterior.coords]]})


# --------------------------------------------------------------------------- #
# Sem recorte: nada muda                                                       #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("extra", [{}, {"alcance": "raio_1km"}])
def test_sem_recorte_nenhuma_chamada_ganha_kwarg(espioes, extra) -> None:
    """Sem os campos (ou pedindo o proprio raio de 1 km) o PDF e' o de sempre: nenhum
    colaborador recebe kwarg da DEC-074."""
    _rota(so_estudo=True, **extra)
    assert _kw(espioes, "carga") == {}
    assert _kw(espioes, "motor")["raio_km"] == 1.0
    assert not {"geometria_wgs84", "geometria_tipo"} & set(_kw(espioes, "motor"))
    assert not {"result", "geometria_wgs84", "geometria_tipo"} & set(_kw(espioes, "mapas"))
    assert _kw(espioes, "mapas")["raio_km"] == 1.0
    assert _kw(espioes, "mercado") == {}
    assert "recorte" not in _kw(espioes, "gerador")


def test_raio_1km_explicito_nao_exige_o_estudo(espioes) -> None:
    _rota(alcance="raio_1km")
    assert "recorte" not in _kw(espioes, "gerador")
    assert _kw(espioes, "gerador")["conclusao_so_estudo"] is False


# --------------------------------------------------------------------------- #
# Raio de 2 km                                                                 #
# --------------------------------------------------------------------------- #
def test_estudo_do_raio_de_2km(espioes) -> None:
    _rota(so_estudo=True, alcance="raio_2km")

    assert _kw(espioes, "carga") == {"raio_km": 2.0}
    motor = _kw(espioes, "motor")
    assert motor["raio_km"] == 2.0 and "geometria_wgs84" not in motor
    mapas = _kw(espioes, "mapas")
    assert mapas["raio_km"] == 2.0
    # O `result` do PDF vai aos mapas: sem segunda intersecao e sem outro recorte.
    assert mapas["result"] is espioes["gerador"][-1][0][0]
    assert "geometria_wgs84" not in mapas
    assert _kw(espioes, "mercado") == {"raio_km": 2.0, "fator_regua": 4.0}

    gerador = _kw(espioes, "gerador")
    assert gerador["conclusao_so_estudo"] is True
    assert gerador["recorte"] == {
        "tipo": "raio_2km",
        "rotulo_curto": "Raio 2,0 km",
        "rotulo_longo": "raio de 2,0 km",
        "fator_regua": 4.0,
        "area_km2": math.pi * 4,
    }
    # O PDF roda na ORIGEM pedida.
    assert espioes["motor"][-1][0] == (_LAT, _LNG)


# --------------------------------------------------------------------------- #
# 10 min de carro                                                              #
# --------------------------------------------------------------------------- #
def test_estudo_dos_10_min_de_carro(espioes, valhalla) -> None:
    _rota(so_estudo=True, alcance="carro_10min")

    assert len(valhalla) == 1
    origem = (round(_LAT, 5), round(_LNG, 5))
    assert espioes["motor"][-1][0] == origem
    assert espioes["carga"][-1][0] == origem
    motor = _kw(espioes, "motor")
    assert motor["geometria_tipo"] == GEOMETRIA_TIPO_ISOCRONA_CARRO_10MIN
    geom = motor["geometria_wgs84"]
    assert geom.covers(Point(origem[1], origem[0]))
    assert _kw(espioes, "carga")["geometria"] is geom
    # O PDF desenha o mapa: a carga de vizinhos cobre o QUADRO dele, nao so' o contorno.
    assert _kw(espioes, "carga")["com_mapa"] is True
    mapas = _kw(espioes, "mapas")
    assert mapas["geometria_wgs84"] is geom
    assert mapas["geometria_tipo"] == GEOMETRIA_TIPO_ISOCRONA_CARRO_10MIN
    assert "result" in mapas
    mercado = _kw(espioes, "mercado")
    assert mercado["geometria"] is geom
    assert mercado["fator_regua"] == pytest.approx(6.0 / math.pi)

    recorte = _kw(espioes, "gerador")["recorte"]
    assert recorte["tipo"] == "carro_10min"
    assert recorte["rotulo_curto"] == "10 min de carro (sem trânsito)"
    assert recorte["rotulo_longo"].startswith("isócrona de 10 min de carro")
    # A rota nao inventa rotulo: o dict e' o de `censo_report.recorte_pdf`, a fonte unica.
    assert recorte == censo_report.recorte_pdf(
        "carro_10min",
        fator_regua=recorte["fator_regua"],
        area_km2=recorte["area_km2"],
        versao_rotas="3.9.0",
    )
    # O carimbo da malha viaria chega ao PDF, nao so' ao JSON da tela.
    assert recorte["versao_rotas"] == "3.9.0"
    assert recorte["fator_regua"] == pytest.approx(6.0 / math.pi)
    # Texto do PDF: so' latin-1 (fpdf2 core font).
    for campo in ("rotulo_curto", "rotulo_longo"):
        recorte[campo].encode("latin-1")


def test_estudo_dos_10_min_sem_servico_e_503_antes_de_registrar(espioes) -> None:
    with pytest.raises(HTTPException) as exc:
        _rota(so_estudo=True, alcance="carro_10min")
    assert exc.value.status_code == 503
    assert exc.value.detail == alcance_ponto.MSG_ROTAS_INDISPONIVEIS
    assert espioes["registro"] == [] and espioes["gerador"] == []


# --------------------------------------------------------------------------- #
# Area desenhada                                                               #
# --------------------------------------------------------------------------- #
def test_estudo_da_area_desenhada(espioes) -> None:
    # O cliente manda um lat/lng QUALQUER: o PDF roda no ponto interno do desenho validado.
    asyncio.run(
        pilot.relatorio_pontual(
            lat=0.0,
            lng=0.0,
            so_estudo=True,
            geometria=_desenho_geojson(),
        )
    )
    (lat, lng), motor = espioes["motor"][-1]
    assert motor["geometria_tipo"] == GEOMETRIA_TIPO_POLIGONO
    assert motor["geometria_wgs84"].contains(Point(lng, lat))
    assert abs(lat - _LAT) < 0.01 and abs(lng - _LNG) < 0.01
    recorte = _kw(espioes, "gerador")["recorte"]
    assert recorte["tipo"] == "poligono"
    assert recorte["rotulo_curto"] == "Área desenhada (6,00 km2)"
    assert recorte["rotulo_longo"] == "área desenhada de 6,00 km2"
    recorte["rotulo_curto"].encode("latin-1")


@pytest.mark.parametrize(
    ("geometria", "trecho"),
    [
        ("{nao e json", "GeoJSON legível"),
        (json.dumps({"type": "Point", "coordinates": [_LNG, _LAT]}), "polígono GeoJSON"),
    ],
)
def test_area_desenhada_invalida_e_400(espioes, geometria, trecho) -> None:
    with pytest.raises(HTTPException) as exc:
        _rota(so_estudo=True, geometria=geometria)
    assert exc.value.status_code == 400
    assert trecho in exc.value.detail
    assert espioes["registro"] == [] and espioes["carga"] == []


# --------------------------------------------------------------------------- #
# Recusas                                                                      #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("kwargs", "trecho"),
    [
        ({"alcance": "raio_2km"}, "use o Estudo"),
        ({"geometria": "{}"}, "use o Estudo"),
        ({"so_estudo": True, "alcance": "raio_2km", "geometria": "{}"}, "não os dois"),
        ({"so_estudo": True, "geometria": "{}", "excluir_ultra_proxima": True}, "área desenhada"),
        ({"alcance": "raio_2km", "excluir_ultra_proxima": True}, "use o Estudo"),
        ({"so_estudo": True, "alcance": "raio_9km"}, "Alcance desconhecido"),
    ],
)
def test_recusas_sao_400_em_portugues_antes_de_registrar(espioes, kwargs, trecho) -> None:
    with pytest.raises(HTTPException) as exc:
        _rota(**kwargs)
    assert exc.value.status_code == 400
    assert trecho in exc.value.detail
    assert espioes["registro"] == [], "relatorio recusado nao entra na trilha"
    assert espioes["carga"] == []


# --------------------------------------------------------------------------- #
# Estudo da unidade Ultra no recorte (emenda do item 6 da DEC-074)               #
# --------------------------------------------------------------------------- #
@pytest.fixture
def unidade_valida(monkeypatch: pytest.MonkeyPatch) -> list:
    """A validacao antecipada da unidade (cadastro em disco) vira espia: a regra dela e' a
    do `mercado_na_area`, com teste proprio; aqui so' importa ONDE ela roda."""
    vistos: list = []
    monkeypatch.setattr(pilot, "_validar_estudo_da_unidade", lambda lat, lng: vistos.append((lat, lng)))
    return vistos


def test_estudo_da_unidade_no_raio_de_2km_mede_o_mercado_no_2km(espioes, unidade_valida) -> None:
    """O defeito que a emenda fecha: com ramos exclusivos, o flag mandava o mercado para o
    raio de 1 km e o PDF diria "raio de 2 km" medindo o 1 km. Agora o MESMO recorte e o
    modo chegam JUNTOS ao mercado."""
    _rota(so_estudo=True, alcance="raio_2km", excluir_ultra_proxima=True)
    assert _kw(espioes, "mercado") == {
        "raio_km": 2.0,
        "fator_regua": 4.0,
        "excluir_ultra_proxima": True,
    }
    assert _kw(espioes, "motor")["raio_km"] == 2.0
    assert _kw(espioes, "gerador")["recorte"]["tipo"] == "raio_2km"
    # A tolerancia de 150 m e' conferida na ORIGEM pedida, antes do registro.
    assert unidade_valida == [(_LAT, _LNG)]
    assert len(espioes["registro"]) == 1


@pytest.mark.parametrize("alcance", ["carro_5min", "carro_10min"])
def test_estudo_da_unidade_na_isocrona_mede_o_mercado_na_isocrona(
    espioes, valhalla, unidade_valida, alcance
) -> None:
    _rota(so_estudo=True, alcance=alcance, excluir_ultra_proxima=True)
    mercado = _kw(espioes, "mercado")
    assert mercado["excluir_ultra_proxima"] is True
    assert "raio_km" not in mercado
    assert mercado["geometria"].equals(_kw(espioes, "motor")["geometria_wgs84"])
    assert mercado["fator_regua"] > 1.0
    assert _kw(espioes, "gerador")["recorte"]["tipo"] == alcance


def test_estudo_da_unidade_no_raio_de_1km_segue_igual(espioes, unidade_valida) -> None:
    """Sem recorte, o mercado do estudo da unidade recebe SO' o flag, como antes."""
    _rota(so_estudo=True, excluir_ultra_proxima=True)
    assert _kw(espioes, "mercado") == {"excluir_ultra_proxima": True}


def test_os_campos_sao_form_e_nao_query() -> None:
    """Os dois campos moram no CORPO multipart: o poligono nao cabe numa URL (HTTP 431)."""
    params = inspect.signature(pilot.relatorio_pontual).parameters
    for nome in ("alcance", "geometria"):
        # Default `None` de verdade: chamada Python direta (testes) nao recebe um FieldInfo.
        assert params[nome].default is None
    rota = next(r for r in pilot.app.routes if getattr(r, "path", "") == "/api/relatorio/pontual")
    corpo = {p.name for p in rota.dependant.body_params}
    query = {p.name for p in rota.dependant.query_params}
    assert {"alcance", "geometria"} <= corpo
    assert not {"alcance", "geometria"} & query


# --------------------------------------------------------------------------- #
# Deck de comparacao                                                           #
# --------------------------------------------------------------------------- #
def test_comparacao_aceita_o_recorte_por_item_e_repassa(monkeypatch) -> None:
    from motor_expansao.dashboard import relatorio_comparacao

    visto: dict = {}

    def _gerar(dados, **kw):
        visto["dados"] = dados
        return b"%PDF-1.4 stub"

    monkeypatch.setattr(relatorio_comparacao, "gerar_pdf_comparacao", _gerar)
    corpo = pilot.ComparacaoIn(
        itens=[
            {
                "rotulo": "A",
                "recorte": {
                    "tipo": "raio_2km",
                    "rotulo": "Raio de 2 km",
                    "area_km2": 12.57,
                    "fator_regua": 4.0,
                },
            },
            {"rotulo": "B"},
        ]
    )
    pilot._gerar_comparacao_pdf(corpo.model_dump())
    itens = visto["dados"]["itens"]
    assert itens[0]["recorte"] == {
        "tipo": "raio_2km",
        "rotulo": "Raio de 2 km",
        "area_km2": 12.57,
        "fator_regua": 4.0,
    }
    assert itens[0]["rotulo"] == "A"  # o resto do item (extra) segue passando
    assert itens[1].get("recorte") is None


@pytest.mark.parametrize(
    "recorte",
    [
        {"tipo": "raio_5km"},
        {"tipo": "raio_2km", "fator_regua": 0},
        {"tipo": "raio_2km", "area_km2": float("inf")},
        {"tipo": "poligono", "rotulo": "x" * 121},
    ],
)
def test_comparacao_recusa_recorte_malformado(recorte) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        pilot.ComparacaoIn(itens=[{"rotulo": "A", "recorte": recorte}])


# --------------------------------------------------------------------------- #
# Ponta a ponta com o gerador REAL                                             #
# --------------------------------------------------------------------------- #
def test_pdf_real_do_estudo_do_raio_de_2km_nomeia_o_recorte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O dict que a rota monta e' aceito pelo gerador de VERDADE, e o PDF diz o recorte e a
    escala das metas -- trava a COSTURA rota -> gerador (os textos tem teste proprio)."""
    pytest.importorskip("h3", reason="censo_report importa h3", exc_type=ImportError)
    from motor_expansao.api import service as api_service
    from motor_expansao.dashboard import censo_map, censo_point

    (tmp_path / "outputs" / "setores_censitarios_2022_geo").mkdir(parents=True)
    _point_app_at(monkeypatch, tmp_path)
    setores = pd.DataFrame({"cod_setor": ["1"], "nome_municipio": ["SAO PAULO"]})
    monkeypatch.setattr(
        api_service, "_resolver_e_carregar", lambda lat, lng, cfg, **kw: ("SP", "1", setores)
    )
    monkeypatch.setattr(api_service, "_competitors_ultra", lambda cfg: (None, None))
    monkeypatch.setattr(api_service, "_nome_municipio_de", lambda df: "SAO PAULO")
    monkeypatch.setattr(
        api_service, "_mercado_do_ponto", lambda lat, lng, cfg, pop, **k: dict(_MERCADO)
    )
    monkeypatch.setattr(
        censo_point,
        "analisar_ponto_censitario_setores",
        lambda lat, lng, df, **kw: _resultado_do_motor(lat, lng, raio_km=kw["raio_km"]),
    )
    monkeypatch.setattr(censo_point, "agregar_perfil_bairro_distrito", lambda *a, **k: None)
    monkeypatch.setattr(censo_map, "render_mapas_censitarios_combinados", lambda *a, **k: None)
    monkeypatch.setattr(censo_map, "render_foto_satelite_ponto", lambda *a, **k: None)
    monkeypatch.setattr(censo_map, "_BASEMAP_CACHE_DIR", censo_map._BASEMAP_CACHE_DIR)
    monkeypatch.setattr(pilot, "_praca_para_pdf", lambda *a, **k: None)
    monkeypatch.setattr(pilot, "_registrar_relatorio_gerado", lambda *a, **k: "rid")

    texto = _rota(so_estudo=True, alcance="raio_2km").body.decode("latin-1", errors="replace")
    assert texto.startswith("%PDF")
    assert "Raio 2,0 km" in texto
    assert "x4,0" in texto  # a nota da escala das metas de total


# --------------------------------------------------------------------------- #
# 5 min de carro (DEC-074, Emenda 1)                                           #
# --------------------------------------------------------------------------- #
def test_estudo_dos_5_min_de_carro(espioes, valhalla) -> None:
    from motor_expansao.dashboard.censo_point import GEOMETRIA_TIPO_ISOCRONA_CARRO_5MIN

    _rota(so_estudo=True, alcance="carro_5min")
    assert [p["contours"] for p in valhalla] == [[{"time": 5}]]
    assert _kw(espioes, "motor")["geometria_tipo"] == GEOMETRIA_TIPO_ISOCRONA_CARRO_5MIN
    assert _kw(espioes, "mapas")["geometria_tipo"] == GEOMETRIA_TIPO_ISOCRONA_CARRO_5MIN
    recorte = _kw(espioes, "gerador")["recorte"]
    assert recorte["tipo"] == "carro_5min"
    assert recorte["rotulo_curto"] == "5 min de carro (sem trânsito)"
    assert recorte["rotulo_longo"].startswith("isócrona de 5 min de carro sem trânsito")
    assert recorte == censo_report.recorte_pdf(
        "carro_5min",
        fator_regua=recorte["fator_regua"],
        area_km2=recorte["area_km2"],
        versao_rotas="3.9.0",
    )


def test_comparacao_aceita_o_recorte_de_5_min() -> None:
    corpo = pilot.ComparacaoIn(
        itens=[{"rotulo": "A", "recorte": {"tipo": "carro_5min", "area_km2": 3.2}}]
    )
    assert corpo.itens[0].recorte is not None
    assert corpo.itens[0].recorte.tipo == "carro_5min"


def test_comparacao_recusa_tempo_de_carro_fora_da_tabela() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        pilot.ComparacaoIn(itens=[{"rotulo": "A", "recorte": {"tipo": "carro_7min"}}])
