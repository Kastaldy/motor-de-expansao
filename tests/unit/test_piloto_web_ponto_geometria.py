"""`POST /api/ponto/geometria` -- a ficha de uma AREA DESENHADA (DEC-071, fase 1).

A rota roda de verdade: motor censitario REAL sobre setores sinteticos, mercado REAL sobre
um `data/staging` sintetico. So' a resolucao de municipio vira stub (ela tem teste proprio
de carga por geometria, no fim deste arquivo). O que se trava:

- a area desenhada substitui o raio em censo, concorrentes e mercado, e a ficha DIZ isso
  (`raio_km` nulo, bloco `recorte`, `geometria` para o mapa desenhar);
- o "ponto" da ficha e' o `representative_point` -- dentro da area mesmo num "U";
- o GET `/api/ponto` nao muda: mesmas chaves, mesma chamada de carga;
- entrada invalida vira 400 com mensagem em portugues;
- a carga de vizinhos acompanha a CAIXA do poligono (senao a DEC-065 voltaria por outra
  porta: poligono que atravessa a divisa perderia os setores do vizinho em silencio).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import h3
import pandas as pd
import pytest
from fastapi import HTTPException
from pyproj import Transformer
from shapely.geometry import Point, Polygon, box
from shapely.ops import transform

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402

from motor_expansao.dashboard.censo_point import (  # noqa: E402
    CRS_ORIGEM_CENSO,
    METODO_RELATORIO_PONTUAL_POLIGONO,
    _local_metric_crs,
)

LAT, LNG = -23.55, -46.63


def _wgs(local_geom):
    t = Transformer.from_crs(_local_metric_crs(LAT, LNG), CRS_ORIGEM_CENSO, always_xy=True)
    return transform(t.transform, local_geom)


def _latlng(x: float, y: float) -> tuple[float, float]:
    p = _wgs(Point(x, y))
    return p.y, p.x


def _setores() -> pd.DataFrame:
    """Grade 3 x 3 km de setores de 250 m, 400 habitantes cada."""
    recs = []
    passo, alcance = 250.0, 1537.0
    i = 0
    x = -alcance
    while x < alcance:
        y = -alcance
        while y < alcance:
            i += 1
            local = box(x, y, x + passo, y + passo)
            g = _wgs(local)
            minx, miny, maxx, maxy = g.bounds
            recs.append({
                "cod_setor": f"3550308{i:08d}", "uf": "SP", "cod_municipio": "3550308",
                "nome_municipio": "São Paulo", "area_setor_m2": float(local.area),
                "geometry_wkb": g.wkb, "bbox_minx": minx, "bbox_miny": miny,
                "bbox_maxx": maxx, "bbox_maxy": maxy, "pop_total_setor_2022": 400.0,
                "domicilios_particulares_ocupados_setor_2022": 130.0,
                "renda_per_capita_setor_2022": 2000.0,
                "renda_per_capita_setor_2022_calibrada": 2000.0,
                "avg_moradores_domicilio_setor_2022": 3.0,
                "renda_responsavel_media_setor_2022": 6000.0,
                "score_setor_2022_calibrado": 55.0, "flag_geometria_valida": True,
            })
            y += passo
        x += passo
    return pd.DataFrame(recs)


# Um "U" de 2.000 x 2.000 m com vao central de 600 m de largura e 1.400 m de fundo.
_U_LOCAL = Polygon([(-1000, -1000), (1000, -1000), (1000, 1000), (300, 1000), (300, -400),
                    (-300, -400), (-300, 1000), (-1000, 1000)])


def _geojson(local_geom) -> dict:
    g = _wgs(local_geom)
    return {"type": "Polygon", "coordinates": [[list(c) for c in g.exterior.coords]]}


def _staging(dir_: Path) -> None:
    dir_.mkdir(parents=True, exist_ok=True)
    cells = {h3.latlng_to_cell(*_latlng(x, y), 7) for x in (-800, 0, 800) for y in (-800, 0, 800)}
    pd.DataFrame({
        "hex_id": sorted(cells),
        "faixa_oportunidade": ["prioridade_maxima"] * len(cells),
        "taxa_fitness_mercado_calibrada": [0.2] * len(cells),
        "sam_fitness_potencial": [10_000.0] * len(cells),
        "oferta_efetiva_disponivel": [0.0] * len(cells),
        "score_oportunidade_residual": [0.0] * len(cells),
        "oferta_consumida_mercado_estimada": [0.0] * len(cells),
        "oferta_consumida_ultra_estimada": [0.0] * len(cells),
    }).to_parquet(dir_ / "hexagonos_mercado_mapeado.parquet", index=False)
    dentro = _latlng(-650, 500)
    pd.DataFrame({
        "concorrente_id": ["c1"], "rede": ["smart_fit"], "lat": [dentro[0]], "lng": [dentro[1]],
        "status_registro": ["valido"],
    }).to_parquet(dir_ / "concorrentes_mapeados.parquet", index=False)
    longe = _latlng(5000, 5000)
    pd.DataFrame({
        "lat": [longe[0]], "lng": [longe[1]], "flag_coord_valida": [True],
    }).to_parquet(dir_ / "unidades_ultra_mapeadas.parquet", index=False)


@pytest.fixture
def ambiente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from motor_expansao.api import service as api_service
    from motor_expansao.dashboard import mercado_raio

    setores = _setores()
    chamadas: list[dict] = []

    def _carregar(lat, lng, cfg, **kw):
        chamadas.append(kw)
        return ("SP", "3550308", setores)

    monkeypatch.setattr(api_service, "_resolver_e_carregar", _carregar)
    dentro = _latlng(-650, 500)
    no_vao = _latlng(0, 500)
    comp = pd.DataFrame({
        "rede": ["dentro", "vao"], "classe": ["cadeia", "cadeia"],
        "lat": [dentro[0], no_vao[0]], "lng": [dentro[1], no_vao[1]],
    })
    monkeypatch.setattr(api_service, "_competitors_ultra", lambda cfg: (comp, None))
    staging = tmp_path / "staging"
    _staging(staging)
    monkeypatch.setattr(pilot, "STAGING_DIR", staging)
    mercado_raio.carregar_cadeias_mercado.cache_clear()
    mercado_raio.carregar_ultra_mercado.cache_clear()
    yield chamadas
    mercado_raio.carregar_cadeias_mercado.cache_clear()
    mercado_raio.carregar_ultra_mercado.cache_clear()


def _post(geojson: dict) -> dict:
    return pilot.ponto_geometria(pilot.PontoGeometriaIn(geometria=geojson))


def test_area_desenhada_substitui_o_raio_em_tudo(ambiente) -> None:
    body = _post(_geojson(_U_LOCAL))

    area_u = (2.0 * 2.0) - (0.6 * 1.4)
    assert body["raio_km"] is None
    assert body["recorte"]["tipo"] == "poligono"
    assert body["recorte"]["metodo"] == METODO_RELATORIO_PONTUAL_POLIGONO
    assert body["recorte"]["n_vertices"] == 8
    assert body["recorte"]["area_km2"] == pytest.approx(area_u, rel=0.01)
    anel = body["geometria"][0]
    assert anel[0] == anel[-1] and len(anel) == 9

    # O "ponto" da ficha e' interno ao poligono, mesmo num "U".
    assert _wgs(_U_LOCAL).contains(Point(body["lng"], body["lat"]))

    # Censo: 400 hab por 0,0625 km2 = 6.400 hab/km2 na area inteira do "U".
    assert body["censo"]["populacao"] == pytest.approx(6_400 * area_u, rel=0.02)
    assert body["censo"]["detalhe"]["area_circulo_km2"] == pytest.approx(area_u, rel=0.01)

    # Concorrentes: ponto-em-poligono -- o do "vao" fica de fora, embora a < 1 km.
    assert body["concorrencia"]["n_concorrentes"] == 1
    assert [c["rede"] for c in body["concorrencia"]["lista"]] == ["dentro"]

    # Mercado no MESMO recorte (DEC-070 generalizada).
    m = body["mercado"]
    assert m["grao"] == "geometria" and m["raio_km"] is None
    assert m["area_km2"] == pytest.approx(area_u, rel=0.01)
    assert m["sam"] == pytest.approx(body["censo"]["populacao"] * 0.2, rel=0.01)
    assert m["consumo_total"] == pytest.approx(m["consumo_concorrentes"] + m["consumo_ultra"], abs=1)
    assert m["residual"] == pytest.approx(max(m["sam"] - m["consumo_total"], 0), abs=1)

    # Os rotulos dos criterios dizem o recorte.
    rotulos = {c["chave"]: c["rotulo"] for c in body["criterios"]}
    assert rotulos["populacao"] == "População na área"
    assert rotulos["concorrentes"] == "Concorrentes de rede na área"

    # A carga recebeu o poligono (para alcancar os vizinhos da caixa dele).
    assert ambiente[-1].get("geometria") is not None


def test_nota_da_area_e_a_media_dos_setores_e_nao_a_do_ponto_central(ambiente, monkeypatch) -> None:
    """Na area, "Potencial socioeconomico" e' a nota DA AREA, nao a do setor do ponto central.

    O ponto central (`representative_point`) e' um lugar que ninguem clicou: com a nota do
    setor dele, o mesmo disco de 1 km desenhado a mao dava outra nota que o raio so' porque
    o ponto interno andou alguns metros. Aqui metade da grade vale 30 e metade 80: a nota da
    area tem de ficar ENTRE as duas (a media ponderada), e o raio segue com o setor do ponto.
    """
    from motor_expansao.api import service as api_service

    setores = _setores()
    setores["score_setor_2022_calibrado"] = [30.0 if x < LNG else 80.0 for x in setores["bbox_minx"]]
    monkeypatch.setattr(
        api_service, "_resolver_e_carregar", lambda lat, lng, cfg, **kw: ("SP", "3550308", setores)
    )

    body = _post(_geojson(box(-1000, -500, 1000, 500)))
    nota = body["censo"]["score_socioeconomico"]
    detalhe = body["censo"]["detalhe"]
    assert 30.0 < nota < 80.0
    assert nota == detalhe["score_medio_raio"]
    assert detalhe["setor_do_ponto"]["score"] in (30.0, 80.0)
    assert nota != detalhe["setor_do_ponto"]["score"]
    criterio = {c["chave"]: c for c in body["criterios"]}["score"]
    assert criterio["valor"] == nota

    # O raio NAO muda: la' a nota continua sendo a do setor que contem o ponto escolhido.
    get = pilot.ponto(lat=LAT, lng=LNG)
    assert get["censo"]["score_socioeconomico"] == get["censo"]["detalhe"]["setor_do_ponto"]["score"]


_CHAVES_DO_GET = {
    "lat", "lng", "raio_km", "hex_id", "local", "censo", "concorrencia", "mercado",
    "vizinhos", "reguas", "criterios",
}


def test_get_api_ponto_nao_muda(ambiente) -> None:
    body = pilot.ponto(lat=LAT, lng=LNG)
    assert set(body) == _CHAVES_DO_GET
    assert body["raio_km"] == 1.0
    assert body["mercado"]["grao"] == "raio"
    rotulos = {c["chave"]: c["rotulo"] for c in body["criterios"]}
    assert rotulos["populacao"] == "População no raio"
    assert rotulos["concorrentes"] == "Concorrentes de rede no raio"
    # A carga foi chamada EXATAMENTE como antes: (lat, lng, cfg), sem kwargs.
    assert ambiente[-1] == {}
    # E, pelo raio, o concorrente do "vao" (a < 1 km do centro) conta.
    assert body["concorrencia"]["n_concorrentes"] == 2


def _quadrado(lado_m: float) -> dict:
    return _geojson(box(-lado_m / 2, -lado_m / 2, lado_m / 2, lado_m / 2))


@pytest.mark.parametrize(
    ("geojson", "trecho"),
    [
        ({"type": "Point", "coordinates": [LNG, LAT]}, "polígono GeoJSON"),
        (_geojson(Polygon([(-500, -500), (500, 500), (500, -500), (-500, 500)])), "cruza a si mesmo"),
        (_quadrado(200.0), "o mínimo é 0,1 km²"),
        (_quadrado(15000.0), "o máximo é 200 km²"),
        (
            _geojson(Polygon([
                Point(0, 0).buffer(1000.0).exterior.interpolate(i / 51, normalized=True).coords[0]
                for i in range(51)
            ])),
            "o máximo é 50",
        ),
        (
            {"type": "Polygon", "coordinates": [[[LNG, LAT], [LNG + 0.01, LAT], [LNG, 10.0], [LNG, LAT]]]},
            "Vértice 3 fora da área atendida",
        ),
    ],
)
def test_entrada_invalida_vira_400_em_portugues(ambiente, geojson: dict, trecho: str) -> None:
    with pytest.raises(HTTPException) as exc:
        _post(geojson)
    assert exc.value.status_code == 400
    assert trecho in str(exc.value.detail)


def test_faixa_fina_e_recusada_antes_de_ler_qualquer_particao(ambiente) -> None:
    """Bloqueio 2 da revisao do admin (PR #457): a faixa fina passava no teto de AREA e a
    carga de vizinhos lia as particoes de todos os municipios da caixa dela. A recusa de
    EXTENSAO tem de vir antes de `_resolver_e_carregar` -- a fixture registra cada chamada."""
    faixa = _geojson(box(-250_000, -5, 250_000, 5))  # 10 m x 500 km = 5 km2
    with pytest.raises(HTTPException) as exc:
        _post(faixa)
    assert exc.value.status_code == 400
    assert "de ponta a ponta; o máximo é 40 km" in str(exc.value.detail)
    assert ambiente == [], "nenhuma particao pode ser carregada para uma geometria recusada"


def test_ponto_central_fora_da_malha_diz_que_e_da_area(ambiente, monkeypatch) -> None:
    from motor_expansao.api import service as api_service
    from motor_expansao.api.errors import APIError

    def _fora(*_a, **_k):
        raise APIError(400, "Coordenada fora da malha municipal", "coordenada_invalida")

    monkeypatch.setattr(api_service, "_resolver_e_carregar", _fora)
    with pytest.raises(HTTPException) as exc:
        _post(_quadrado(1000.0))
    assert exc.value.status_code == 400
    assert "ponto central da área desenhada" in exc.value.detail


def test_rota_nova_cai_no_gate_do_api_ponto() -> None:
    import acesso

    assert acesso.abas_necessarias("/api/ponto/geometria") == acesso.abas_necessarias("/api/ponto")
    assert acesso.rota_exige_malha_municipal("/api/ponto/geometria")
    # No modelo por banco (P19), o POST cai na MESMA capacidade do GET.
    assert acesso.capacidade_necessaria("/api/ponto/geometria", "POST") == "ponto.analisar"


# --------------------------------------------------------------------------- #
# Carga de vizinhos pela caixa do poligono                                     #
# --------------------------------------------------------------------------- #
# Tres municipios em faixas: o do PONTO no meio; um vizinho COLADO (o frame ja' o alcanca)
# e um LONGE, a ~3 km do ponto -- fora do frame de ~1,7 km, mas dentro de um poligono que
# se estende para leste.
_PLAT, _PLNG = -23.60000, -46.57000
_MUNS = [
    ("SP", "3500002", box(_PLNG - 0.02, _PLAT - 0.05, _PLNG + 0.003, _PLAT + 0.05), _PLNG - 0.001),
    ("SP", "3500003", box(_PLNG + 0.003, _PLAT - 0.05, _PLNG + 0.025, _PLAT + 0.05), _PLNG + 0.004),
    ("MG", "3100004", box(_PLNG + 0.025, _PLAT - 0.05, _PLNG + 0.08, _PLAT + 0.05), _PLNG + 0.03),
]


@pytest.fixture
def malha_real(tmp_path):
    from shapely import wkb

    from motor_expansao.api import service
    from motor_expansao.api.settings import Settings

    ibge_dir, censo_dir = tmp_path / "ibge", tmp_path / "geo"
    ibge_dir.mkdir()
    por_uf: dict[str, list] = {}
    for uf, cod, geom, lng_base in _MUNS:
        por_uf.setdefault(uf, []).append(
            {"type": "Feature", "properties": {"codarea": cod}, "geometry": geom.__geo_interface__}
        )
        setor = box(lng_base, _PLAT - 0.001, lng_base + 0.0008, _PLAT + 0.001)
        minx, miny, maxx, maxy = setor.bounds
        destino = censo_dir / f"uf={uf}" / f"cod_municipio={cod}"
        destino.mkdir(parents=True)
        pd.DataFrame([{
            "cod_setor": f"{cod}00000001", "uf": uf, "cod_municipio": cod,
            "nome_municipio": f"Municipio {cod}", "geometry_wkb": wkb.dumps(setor),
            "bbox_minx": minx, "bbox_miny": miny, "bbox_maxx": maxx, "bbox_maxy": maxy,
            "pop_total_setor_2022": 500.0,
        }]).to_parquet(destino / "part-000.parquet", index=False)
    for uf, feats in por_uf.items():
        (ibge_dir / f"municipios_{uf}.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8"
        )
    service._carregar_malha.cache_clear()
    try:
        yield Settings(ibge_dir=ibge_dir, censo_geo_dir=censo_dir)
    finally:
        service._carregar_malha.cache_clear()


def test_poligono_que_atravessa_a_divisa_carrega_o_vizinho_da_caixa(malha_real) -> None:
    from motor_expansao.api.service import _resolver_e_carregar

    _uf, cod, so_ponto = _resolver_e_carregar(_PLAT, _PLNG, malha_real)
    assert cod == "3500002"
    assert set(so_ponto["cod_municipio"].astype(str)) == {"3500002", "3500003"}, (
        "premissa do teste: o frame do ponto alcanca o vizinho colado e NAO o de longe"
    )

    poligono = box(_PLNG - 0.004, _PLAT - 0.004, _PLNG + 0.034, _PLAT + 0.004)
    _uf, cod, com_area = _resolver_e_carregar(_PLAT, _PLNG, malha_real, geometria=poligono)
    assert cod == "3500002"
    assert set(com_area["cod_municipio"].astype(str)) == {"3500002", "3500003", "3100004"}
    # O municipio do ponto continua PRIMEIRO (o rotulo do painel e' dele).
    assert str(com_area["cod_municipio"].iloc[0]) == "3500002"


def test_alcance_de_municipios_e_pelo_poligono_e_nao_pela_caixa() -> None:
    """Revisao do admin (service.py): num "L" a caixa cobre municipios que a area nem toca,
    e cada um seria uma particao a mais lida do disco. O alcance passa a ser o poligono
    com a margem de 0,5 km."""
    from shapely import STRtree

    from motor_expansao.api.service import _MalhaMunicipal

    # "L" de 0,1 grau (~11 km) com bracos de 0,01 grau (~1 km), canto em (_PLNG, _PLAT).
    l_area = Polygon([
        (_PLNG, _PLAT), (_PLNG + 0.1, _PLAT), (_PLNG + 0.1, _PLAT + 0.01),
        (_PLNG + 0.01, _PLAT + 0.01), (_PLNG + 0.01, _PLAT + 0.1), (_PLNG, _PLAT + 0.1),
    ])
    no_braco = box(_PLNG + 0.05, _PLAT - 0.02, _PLNG + 0.07, _PLAT + 0.005)
    # A ~0,3 km do braco horizontal (dentro da margem): o setor dele pode atravessar a area.
    na_margem = box(_PLNG + 0.03, _PLAT + 0.0127, _PLNG + 0.04, _PLAT + 0.02)
    # No canto VAZIO do "L": dentro da caixa, a ~4 km de qualquer braco.
    no_vao = box(_PLNG + 0.05, _PLAT + 0.05, _PLNG + 0.09, _PLAT + 0.09)
    geoms = [no_braco, na_margem, no_vao]
    meta = [("SP", "braco"), ("SP", "margem"), ("SP", "vao")]
    malha = _MalhaMunicipal(STRtree(geoms), meta, geoms)

    assert no_vao.intersects(box(*l_area.bounds)), "premissa: a caixa do L cobre o vao"
    assert set(malha.alcancados_na_geometria(l_area)) == {("SP", "braco"), ("SP", "margem")}
