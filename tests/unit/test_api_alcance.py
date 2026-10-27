"""O alcance do ponto na API publica: `alcance` em `POST /api/v1/analisar` (DEC-074, Emenda 3).

Ate' aqui o campo nao existia no contrato e o Pydantic o descartava sem avisar: medido em
producao em 27/10/2026, `"alcance": "carro_10min"` devolvia 200 com o estudo de 1 km
(`raio_km` 1.0, metodo `..._1km`, mesma populacao e mesmos setores da chamada sem o campo).
Quem pediu 10 min de carro recebia o raio de 1 km achando que era outro estudo.

Travas deste arquivo:

- o campo existe, com os quatro alcances do motor e nenhum outro (fora da lista -> 422);
- o recorte so' existe no PDF Estudo (decisao 3 da DEC-074): com JSON, `viabilidade` ou
  `info_imovel` -> 400 em portugues, antes de gerar qualquer coisa;
- servico de rotas fora -> 503, recorte inviavel -> 400; nunca o raio de 1 km em silencio;
- sem o campo (ou com `raio_1km`), nenhuma chamada ganha kwarg novo: o PDF de sempre;
- a API entrega a carga, ao motor, aos mapas, ao mercado e ao gerador o MESMO recorte que o
  botao Estudo do piloto entrega. O mapeamento recorte -> kwargs vive nos dois lugares; e'
  este teste, e nao um comentario, que impede os dois de divergirem.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Literal, get_args, get_origin

import pandas as pd
import pytest
from pyproj import Transformer
from shapely.geometry import box, mapping
from shapely.ops import transform

pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from motor_expansao.api import service as api_service  # noqa: E402
from motor_expansao.api.errors import APIError  # noqa: E402
from motor_expansao.api.main import create_app  # noqa: E402
from motor_expansao.api.routes import analisar as rota_analisar  # noqa: E402
from motor_expansao.api.schemas import AnalisarRequest  # noqa: E402
from motor_expansao.api.settings import Settings  # noqa: E402
from motor_expansao.dashboard import alcance_ponto  # noqa: E402
from motor_expansao.dashboard.censo_point import (  # noqa: E402
    CRS_ORIGEM_CENSO,
    GEOMETRIA_TIPO_ISOCRONA_CARRO_10MIN,
    _local_metric_crs,
)

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

_LAT, _LNG = -23.55, -46.63
_URL_ROTAS = "http://valhalla.teste:8002"
AUTH = {"Authorization": "Bearer dev-token"}
_CENARIO = {"m2": 1500, "aluguel": 30000, "demanda": 1600}

_MERCADO = {
    "grao": "raio",
    "sam_fitness_potencial": 3_000.0,
    "oferta_consumida_mercado_estimada": 1_200.0,
    "oferta_consumida_ultra_estimada": 300.0,
    "oferta_consumida_total_estimada": 1_500.0,
    "oferta_efetiva_disponivel": 1_500.0,
    "score_oportunidade_residual": 60.0,
}


# --------------------------------------------------------------------------- #
# Contrato                                                                     #
# --------------------------------------------------------------------------- #
def test_alcance_do_contrato_e_o_do_motor() -> None:
    """Os valores aceitos sao exatamente os alcances do motor, na mesma ordem."""
    anotacao = AnalisarRequest.model_fields["alcance"].annotation
    literal = next(a for a in get_args(anotacao) if get_origin(a) is Literal)
    assert get_args(literal) == alcance_ponto.ALCANCES
    assert AnalisarRequest.model_fields["alcance"].default is None


# --------------------------------------------------------------------------- #
# Rota: o que entra e o que e' recusado antes de gerar                         #
# --------------------------------------------------------------------------- #
@pytest.fixture
def rota(monkeypatch: pytest.MonkeyPatch) -> dict:
    """A rota com o gerador e o estudo JSON trocados por espioes."""
    visto: dict[str, list] = {"pdf": [], "json": []}

    def _pdf(lat, lng, consumidor, settings, **kw):
        visto["pdf"].append(((lat, lng), kw))
        return b"%PDF-1.4 stub"

    def _json(lat, lng, consumidor, settings):
        visto["json"].append((lat, lng))
        return {}

    monkeypatch.setattr(rota_analisar, "gerar_pdf_ponto", _pdf)
    monkeypatch.setattr(rota_analisar, "analisar_ponto", _json)
    visto["client"] = TestClient(create_app())
    return visto


def _post(rota: dict, **corpo):
    return rota["client"].post(
        "/api/v1/analisar", json={"lat": _LAT, "lng": _LNG, **corpo}, headers=AUTH
    )


@pytest.mark.parametrize("alcance", ["raio_2km", "carro_5min", "carro_10min"])
def test_alcance_chega_ao_gerador_do_pdf(rota, alcance) -> None:
    resp = _post(rota, formato="pdf", alcance=alcance)
    assert resp.status_code == 200, resp.text
    assert rota["pdf"][-1][1]["alcance"] == alcance


def test_alcance_com_viabilidade_e_400_sem_gerar(rota) -> None:
    resp = _post(rota, formato="pdf", alcance="carro_10min", viabilidade=_CENARIO)
    assert resp.status_code == 400, resp.text
    assert resp.json() == {
        "detail": api_service.MSG_ALCANCE_SO_NO_ESTUDO,
        "codigo": "alcance_so_no_estudo",
    }
    assert rota["pdf"] == []


def test_alcance_com_info_imovel_e_400_sem_gerar(rota) -> None:
    """`info_imovel` carrega aluguel e valor de venda: e' dado do relatorio completo."""
    resp = _post(rota, formato="pdf", alcance="raio_2km", info_imovel={"vagas": 10})
    assert resp.status_code == 400, resp.text
    assert resp.json()["codigo"] == "alcance_so_no_estudo"
    assert rota["pdf"] == []


def test_alcance_no_json_e_400_sem_calcular(rota) -> None:
    """O JSON segue no raio de 1 km; aceitar o campo ali repetiria o defeito."""
    resp = _post(rota, alcance="carro_10min")
    assert resp.status_code == 400, resp.text
    assert resp.json() == {
        "detail": api_service.MSG_ALCANCE_SO_NO_PDF,
        "codigo": "alcance_so_no_pdf",
    }
    assert rota["json"] == [] and rota["pdf"] == []


def test_alcance_fora_da_lista_e_422(rota) -> None:
    resp = _post(rota, formato="pdf", alcance="carro_7min")
    assert resp.status_code == 422, resp.text
    assert rota["pdf"] == []


@pytest.mark.parametrize(
    "corpo",
    [
        {},
        {"alcance": "raio_1km"},
        {"alcance": "raio_1km", "viabilidade": _CENARIO, "info_imovel": {"vagas": 10}},
    ],
)
def test_sem_recorte_o_pedido_de_sempre_passa(rota, corpo) -> None:
    """Sem alcance, ou pedindo o proprio raio de 1 km, nada e' recusado."""
    resp = _post(rota, formato="pdf", **corpo)
    assert resp.status_code == 200, resp.text
    assert len(rota["pdf"]) == 1


# --------------------------------------------------------------------------- #
# Servico: espioes nos colaboradores pesados, nos dois geradores               #
# --------------------------------------------------------------------------- #
def _resultado_do_motor(lat, lng, raio_km=1.0, geometria_wgs84=None, geometria_tipo=None):
    """As chaves do `result` real que as rotas leem (contrato do motor, DEC-074)."""
    out = {"lat": lat, "lng": lng, "nome_municipio": "SAO PAULO", "uf": "SP"}
    if geometria_wgs84 is not None:
        area = 6.0
        out.update(
            {
                "raio_km": None,
                "geometria_tipo": geometria_tipo,
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
    """Carga, motor, mapas, mercado e gerador viram espioes. {nome: [(args, kwargs)]}."""
    from motor_expansao.dashboard import censo_map, censo_point, censo_report

    visto: dict[str, list] = {k: [] for k in ("carga", "motor", "mapas", "mercado", "gerador")}
    setores = pd.DataFrame({"cod_setor": ["355030801000001"], "nome_municipio": ["SAO PAULO"]})

    def _carga(lat, lng, cfg, **kw):
        visto["carga"].append(((lat, lng), kw))
        return ("SP", "3550308", setores)

    def _motor(lat, lng, df, **kw):
        visto["motor"].append(((lat, lng), kw))
        chaves = ("raio_km", "geometria_wgs84", "geometria_tipo")
        return _resultado_do_motor(lat, lng, **{k: kw[k] for k in chaves if k in kw})

    def _mapas(lat, lng, df, **kw):
        visto["mapas"].append(((lat, lng), kw))
        return None

    def _mercado(lat, lng, cfg, pop, **kw):
        visto["mercado"].append(((lat, lng), kw))
        return dict(_MERCADO)

    def _gerar(result, mapas, **kw):
        visto["gerador"].append(((result,), kw))
        return b"%PDF-1.4 stub"

    monkeypatch.setattr(api_service, "_resolver_e_carregar", _carga)
    monkeypatch.setattr(api_service, "_competitors_ultra", lambda cfg: (None, None))
    monkeypatch.setattr(api_service, "_nome_municipio_de", lambda df: "SAO PAULO")
    monkeypatch.setattr(api_service, "_mercado_do_ponto", _mercado)
    monkeypatch.setattr(api_service, "_hexes_vizinhos_do_ponto", lambda *a, **k: None)
    monkeypatch.setattr(api_service, "_reuse_contextily_session", lambda: None)
    monkeypatch.setattr(censo_point, "analisar_ponto_censitario_setores", _motor)
    monkeypatch.setattr(censo_point, "agregar_perfil_bairro_distrito", lambda *a, **k: None)
    monkeypatch.setattr(censo_map, "render_mapas_censitarios_combinados", _mapas)
    monkeypatch.setattr(censo_map, "render_foto_satelite_ponto", lambda *a, **k: None)
    monkeypatch.setattr(censo_map, "_BASEMAP_CACHE_DIR", censo_map._BASEMAP_CACHE_DIR)
    monkeypatch.setattr(censo_report, "gerar_pdf_relatorio_pontual_classico", _gerar)
    monkeypatch.delenv(alcance_ponto.ENV_ROTAS, raising=False)
    alcance_ponto.limpar_cache()
    visto["settings"] = Settings(
        censo_geo_dir=tmp_path / "geo",
        ibge_dir=tmp_path / "ibge",
        ultra_dir=tmp_path / "ultra",
        staging_dir=tmp_path / "staging",
    )
    visto["tmp"] = tmp_path
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


def _wgs(local_geom):
    t = Transformer.from_crs(_local_metric_crs(_LAT, _LNG), CRS_ORIGEM_CENSO, always_xy=True)
    return transform(t.transform, local_geom)


@pytest.fixture
def valhalla(monkeypatch: pytest.MonkeyPatch) -> list:
    """O servico de rotas respondendo uma isocrona fixa em volta do ponto."""
    import requests

    monkeypatch.setenv(alcance_ponto.ENV_ROTAS, _URL_ROTAS)
    enviados: list = []
    iso = _wgs(box(-500, -1000, 2500, 1000))

    def _post(url, json=None, timeout=None):  # noqa: A002 - assinatura do requests
        enviados.append(json)
        return _Resp(
            200,
            {
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "geometry": mapping(iso)}],
            },
        )

    monkeypatch.setattr(requests, "post", _post)
    monkeypatch.setattr(requests, "get", lambda url, timeout=None: _Resp(200, {"version": "3.9.0"}))
    alcance_ponto.limpar_cache()
    return enviados


def _pdf_da_api(espioes: dict, **kw) -> bytes:
    return api_service.gerar_pdf_ponto(_LAT, _LNG, "teste", espioes["settings"], **kw)


def _kw(visto: dict, nome: str) -> dict:
    assert visto[nome], f"{nome} nao foi chamado"
    return visto[nome][-1][1]


@pytest.mark.parametrize("extra", [{}, {"alcance": None}, {"alcance": "raio_1km"}])
def test_api_sem_recorte_nenhuma_chamada_ganha_kwarg(espioes, extra) -> None:
    _pdf_da_api(espioes, **extra)
    assert _kw(espioes, "carga") == {}
    motor = _kw(espioes, "motor")
    assert motor["raio_km"] == 1.0
    assert not {"geometria_wgs84", "geometria_tipo"} & set(motor)
    assert not {"result", "geometria_wgs84", "geometria_tipo"} & set(_kw(espioes, "mapas"))
    assert _kw(espioes, "mapas")["raio_km"] == 1.0
    assert _kw(espioes, "mercado") == {}
    assert "recorte" not in _kw(espioes, "gerador")


def test_api_dos_10_min_sem_servico_e_503_antes_de_carregar(espioes) -> None:
    with pytest.raises(APIError) as exc:
        _pdf_da_api(espioes, alcance="carro_10min")
    assert exc.value.status_code == 503
    assert exc.value.codigo == "rotas_indisponiveis"
    assert exc.value.detail == alcance_ponto.MSG_ROTAS_INDISPONIVEIS
    assert espioes["carga"] == [] and espioes["gerador"] == []


def test_api_recorte_inviavel_e_400_antes_de_carregar(espioes, monkeypatch) -> None:
    motivo = alcance_ponto.MSG_SEM_VIA.format(minutos=5)

    def _sem_via(lat, lng, minutos=10):
        raise alcance_ponto.AlcanceInvalido(motivo)

    monkeypatch.setattr(alcance_ponto, "isocrona_carro", _sem_via)
    with pytest.raises(APIError) as exc:
        _pdf_da_api(espioes, alcance="carro_5min")
    assert exc.value.status_code == 400
    assert exc.value.codigo == "alcance_invalido"
    assert exc.value.detail == motivo
    assert espioes["carga"] == [] and espioes["gerador"] == []


# Os kwargs que o recorte acrescenta a cada colaborador (web/server/app.py,
# `_gerar_relatorio_pontual_pdf`). O resto das chamadas difere de proposito entre as duas
# superficies (logos e hexes do residual na API, praca e fotos no piloto).
_CHAVES_DO_RECORTE = {
    "carga": ("raio_km", "geometria", "com_mapa"),
    "motor": ("raio_km", "geometria_wgs84", "geometria_tipo"),
    "mapas": ("raio_km", "geometria_wgs84", "geometria_tipo"),
    "mercado": ("raio_km", "geometria", "fator_regua"),
    "gerador": ("recorte", "conclusao_so_estudo"),
}


def _o_que_o_recorte_entrega(visto: dict) -> dict:
    out: dict = {}
    for nome, chaves in _CHAVES_DO_RECORTE.items():
        args, kw = visto[nome][-1]
        out[nome] = {k: kw[k] for k in chaves if k in kw}
        if nome != "gerador":
            out[f"{nome}:origem"] = args
    # Os mapas desenham o `result` que o PDF imprime: sem segunda intersecao.
    out["mapas:result"] = visto["mapas"][-1][1].get("result") is visto["gerador"][-1][0][0]
    return out


def _limpar(visto: dict) -> None:
    for nome in _CHAVES_DO_RECORTE:
        visto[nome].clear()


@pytest.mark.parametrize("alcance", ["raio_2km", "carro_10min"])
def test_api_e_piloto_entregam_o_mesmo_recorte(espioes, valhalla, monkeypatch, alcance) -> None:
    import app as pilot

    tmp = espioes["tmp"]
    (tmp / "outputs" / "setores_censitarios_2022_geo").mkdir(parents=True)
    monkeypatch.setattr(pilot, "DATA_DIR", tmp)
    monkeypatch.setattr(pilot, "OUTPUTS_DIR", tmp / "outputs")
    monkeypatch.setattr(pilot, "STAGING_DIR", tmp / "staging")
    monkeypatch.setattr(pilot, "IBGE_DIR", tmp / "ibge")
    monkeypatch.setattr(pilot, "ULTRA_DIR", tmp / "ultra")
    monkeypatch.setattr(pilot, "CENSO_GEO_DIR", tmp / "outputs" / "setores_censitarios_2022_geo")
    monkeypatch.setattr(pilot, "_praca_para_pdf", lambda *a, **k: None)

    recorte = pilot._resolver_recorte_do_pdf(_LAT, _LNG, alcance, None, True, False)
    pilot._gerar_relatorio_pontual_pdf(
        recorte.lat,
        recorte.lng,
        None,
        None,
        None,
        None,
        None,
        [],
        so_estudo=True,
        recorte=recorte,
    )
    do_piloto = _o_que_o_recorte_entrega(espioes)

    _limpar(espioes)
    _pdf_da_api(espioes, alcance=alcance)
    da_api = _o_que_o_recorte_entrega(espioes)

    assert da_api == do_piloto
    # E o que se compara nao e' vazio: o recorte de fato chegou ao gerador.
    assert da_api["gerador"]["recorte"]["tipo"] == alcance
    assert da_api["gerador"]["conclusao_so_estudo"] is True
    if alcance == "carro_10min":
        assert da_api["motor"]["geometria_tipo"] == GEOMETRIA_TIPO_ISOCRONA_CARRO_10MIN
        assert da_api["gerador"]["recorte"]["versao_rotas"] == "3.9.0"
        # A isocrona saiu do cache: o piloto e a API nao pagaram duas chamadas.
        assert len(valhalla) == 1
