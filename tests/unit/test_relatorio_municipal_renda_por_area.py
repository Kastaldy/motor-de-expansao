"""Renda domiciliar por hexagono no Relatorio Municipal: rateio setor -> hexagono por AREA.

Defeito medido em 2026-10-16 (Sao Roque/SP, 3550605): `carregar_renda_domiciliar_por_hex`
mandava cada setor INTEIRO para o hexagono do centro do seu bbox. Em setor rural grande (7,7 e
13,5 km2, contra ~5,16 km2 de um res-7) o centro cai no vizinho: o hexagono 87a810344ffffff
saia "Não disponível" com quatro setores com renda cobrindo-o, e o vizinho 87a810363ffffff
herdava 100% de um setor do qual cobre so' 5%. A populacao da MESMA linha ja' era rateada por
area -- agora a renda tambem.
"""

from __future__ import annotations

import os
from pathlib import Path

import h3
import pandas as pd
import pytest
from shapely import wkb
from shapely.geometry import Polygon, box

from motor_expansao.dashboard import relatorio_municipal as rm


def _poligono_hex(cell: str) -> Polygon:
    return Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(cell)])


def _setor(cod: str, geom, renda: float, dom: float) -> dict:
    minx, miny, maxx, maxy = geom.bounds
    return {
        "cod_setor": cod,
        "renda_responsavel_media_setor_2022": renda,
        "renda_per_capita_setor_2022": float("nan"),
        "avg_moradores_domicilio_setor_2022": 3.0,
        "domicilios_particulares_ocupados_setor_2022": dom,
        "bbox_minx": minx, "bbox_miny": miny, "bbox_maxx": maxx, "bbox_maxy": maxy,
        "geometry_wkb": wkb.dumps(geom),
    }


@pytest.fixture
def _formula_neutra(monkeypatch):
    """uplift 1 e fator temporal 1: o teste mede o RATEIO, nao a formula."""
    monkeypatch.setattr(
        "motor_expansao.dashboard.constants.uplift_composicao_por_setor", lambda *_a, **_k: 1.0
    )
    monkeypatch.setattr("motor_expansao.dashboard.constants.FATOR_TEMPORAL_RENDA", 1.0)


def _geografia():
    """Hexagono A e um vizinho B; setor `borda` centrado em B que invade A por uma faixa."""
    lat, lng = -23.53, -47.14
    a = h3.latlng_to_cell(lat, lng, 7)
    b = sorted(h3.grid_ring(a, 1))[0]
    pa, pb = _poligono_hex(a), _poligono_hex(b)
    # Quadrado em torno do centro de B, grande o bastante para cruzar para A sem cobri-lo.
    cb = pb.centroid
    borda = box(cb.x - 0.012, cb.y - 0.012, cb.x + 0.012, cb.y + 0.012)
    assert borda.intersects(pa) and not pa.within(borda)
    # Setor pequeno no miolo de A.
    ca = pa.centroid
    dentro = box(ca.x - 0.002, ca.y - 0.002, ca.x + 0.002, ca.y + 0.002)
    assert dentro.within(pa)
    return a, b, pa, pb, borda, dentro


def test_setor_que_so_toca_a_borda_nao_herda_100_por_cento(_formula_neutra):
    a, b, pa, pb, borda, _ = _geografia()
    setores = pd.DataFrame([_setor("BORDA", borda, 5000.0, 100.0)])

    contrib = rm.contribuicoes_renda_por_area(setores, "SP", "3550605")

    frac_a = borda.intersection(pa).area / borda.area
    frac_b = borda.intersection(pb).area / borda.area
    assert 0 < frac_a < 0.5 < frac_b < 1
    # O hexagono A, que o setor so' toca, passa a TER renda (antes saia "Não disponível")...
    assert a in contrib
    # ...com o peso da fracao, nao com o setor inteiro.
    assert contrib[a][1] == pytest.approx(100.0 * frac_a)
    # E o hexagono do centro do bbox (B) deixa de herdar 100% dos domicilios.
    assert contrib[b][1] == pytest.approx(100.0 * frac_b)
    assert contrib[b][1] < 100.0
    # Rateio conserva massa: os domicilios do setor nao somem nem duplicam.
    assert sum(den for _, den in contrib.values()) == pytest.approx(100.0)


def test_renda_do_hex_e_media_ponderada_por_domicilio_x_fracao(_formula_neutra, monkeypatch):
    a, _, pa, _, borda, dentro = _geografia()
    setores = pd.DataFrame([
        _setor("BORDA", borda, 5000.0, 100.0),
        _setor("DENTRO", dentro, 1000.0, 40.0),
    ])
    monkeypatch.setattr(
        "motor_expansao.pipelines.materializar_setores_censitarios_geo.ler_particao_setores",
        lambda **_k: setores,
    )

    mapa = rm.carregar_renda_domiciliar_por_hex("SP", "3550605", "qualquer/caminho", hexes=[a])

    frac = borda.intersection(pa).area / borda.area
    esperado = (5000.0 * 100.0 * frac + 1000.0 * 40.0) / (100.0 * frac + 40.0)
    assert set(mapa) == {a}  # `hexes` restringe a saida
    assert mapa[a] == pytest.approx(esperado)
    # No criterio antigo A receberia so' o setor de dentro (1000): o de borda iria todo para B.
    assert mapa[a] > 1000.0


def test_vizinho_soma_contribuicoes_antes_de_dividir(_formula_neutra, monkeypatch):
    """Hexagono de divisa: as particoes somam numerador e denominador -- nunca media de medias."""
    a, _, _, _, _, dentro = _geografia()
    ca = dentro.centroid
    outro = box(ca.x + 0.003, ca.y - 0.001, ca.x + 0.005, ca.y + 0.001)
    particoes = {
        "3550605": pd.DataFrame([_setor("P", dentro, 1000.0, 10.0)]),
        "3502754": pd.DataFrame([_setor("V", outro, 4000.0, 30.0)]),
    }
    monkeypatch.setattr(
        "motor_expansao.pipelines.materializar_setores_censitarios_geo.ler_particao_setores",
        lambda **k: particoes[k["cod_municipio"]],
    )

    so_proprio = rm.carregar_renda_domiciliar_por_hex("SP", "3550605", "x", hexes=[a])
    com_vizinho = rm.carregar_renda_domiciliar_por_hex(
        "SP", "3550605", "x", hexes=[a], vizinhos=[("SP", "3502754")]
    )
    assert so_proprio[a] == pytest.approx(1000.0)
    assert com_vizinho[a] == pytest.approx((1000.0 * 10 + 4000.0 * 30) / 40)  # 3250, nao 2500


def test_vizinho_ilegivel_nao_derruba_a_renda_do_municipio(_formula_neutra, monkeypatch):
    a, _, _, _, _, dentro = _geografia()

    def _ler(**k):
        if k["cod_municipio"] == "9999999":
            raise OSError("particao corrompida")
        return pd.DataFrame([_setor("P", dentro, 1000.0, 10.0)])

    monkeypatch.setattr(
        "motor_expansao.pipelines.materializar_setores_censitarios_geo.ler_particao_setores", _ler
    )
    mapa = rm.carregar_renda_domiciliar_por_hex(
        "SP", "3550605", "x", hexes=[a], vizinhos=[("SP", "9999999")]
    )
    assert mapa[a] == pytest.approx(1000.0)


def test_particao_sem_geometria_cai_no_bbox_mas_falha_de_leitura_nao(
    _formula_neutra, monkeypatch, tmp_path
):
    """So' a coluna AUSENTE no schema autoriza o criterio antigo; erro de leitura (memoria,
    IO) com a geometria nao pode virar 2a leitura sem ela -- isso devolveria o defeito."""
    a, _, _, _, _, dentro = _geografia()
    # Particao antiga REAL, sem geometry_wkb: o setor vai ao hexagono do centro do bbox.
    linha = _setor("P", dentro, 1000.0, 10.0)
    del linha["geometry_wkb"]
    destino = tmp_path / "uf=SP" / "cod_municipio=3550605"
    destino.mkdir(parents=True)
    pd.DataFrame([linha]).to_parquet(destino / "part-000.parquet", index=False)
    assert rm.carregar_renda_domiciliar_por_hex("SP", "3550605", tmp_path)[a] == pytest.approx(
        1000.0
    )

    # Particao COM geometria cuja leitura falha: nada de cair para a leitura sem ela.
    pd.DataFrame([_setor("P", dentro, 1000.0, 10.0)]).to_parquet(
        destino / "part-000.parquet", index=False
    )
    pedidos: list[list[str]] = []

    def _ler(**k):
        pedidos.append(list(k["columns"]))
        if "geometry_wkb" in k["columns"]:
            raise MemoryError("sem memoria")
        return pd.DataFrame([linha])

    monkeypatch.setattr(
        "motor_expansao.pipelines.materializar_setores_censitarios_geo.ler_particao_setores", _ler
    )
    assert rm.carregar_renda_domiciliar_por_hex("SP", "3550605", tmp_path) == {}
    assert len(pedidos) == 1 and "geometry_wkb" in pedidos[0]


def test_vizinhos_dos_hexes_pela_malha_sem_o_proprio_municipio(monkeypatch, tmp_path):
    """`_municipios_vizinhos_dos_hexes` (o que o service passa como `vizinhos=`): malha
    sintetica com o proprio municipio, um vizinho que o hexagono atravessa e um distante."""
    from shapely.strtree import STRtree

    from motor_expansao.api import service
    from motor_expansao.api.settings import Settings

    a, b, pa, pb, _, _ = _geografia()
    corte = pa.centroid.x  # a divisa corta o hexagono A ao meio
    minx, miny, maxx, maxy = pa.union(pb).bounds
    proprio = box(minx - 1, miny - 1, corte, maxy + 1)
    vizinho = box(corte, miny - 1, maxx + 1, maxy + 1)
    longe = box(minx + 10, miny + 10, minx + 11, miny + 11)
    geoms = [proprio, vizinho, longe]
    malha = service._MalhaMunicipal(
        STRtree(geoms), [("SP", "3550605"), ("sp", "3502754"), ("MG", "3100000")], geoms
    )
    monkeypatch.setattr(service, "_carregar_malha", lambda _d: malha)
    settings = Settings(
        staging_dir=tmp_path, censo_geo_dir=tmp_path, ibge_dir=tmp_path, ultra_dir=tmp_path
    )

    assert service._municipios_vizinhos_dos_hexes([a], "SP", "3550605", settings) == [
        ("sp", "3502754")
    ]
    assert service._municipios_vizinhos_dos_hexes([], "SP", "3550605", settings) == []

    def _sem_malha(_d):
        raise OSError("malha ausente")

    monkeypatch.setattr(service, "_carregar_malha", _sem_malha)
    assert service._municipios_vizinhos_dos_hexes([a], "SP", "3550605", settings) == []


def test_malha_tocados_devolve_municipios_que_os_hexagonos_tocam():
    from shapely.strtree import STRtree

    from motor_expansao.api.service import _MalhaMunicipal

    geoms = [box(0, 0, 1, 1), box(1, 0, 2, 1), box(5, 5, 6, 6)]
    meta = [("SP", "1"), ("SP", "2"), ("MG", "3")]
    malha = _MalhaMunicipal(STRtree(geoms), meta, geoms)
    import numpy as np

    hexes = np.array([box(0.8, 0.2, 1.2, 0.4), box(0.1, 0.1, 0.2, 0.2)], dtype=object)
    assert malha.tocados(hexes) == [("SP", "1"), ("SP", "2")]
    assert malha.tocados(box(5.5, 5.5, 5.6, 5.6)) == [("MG", "3")]


def test_malha_tocados_fora_de_da_o_mesmo_que_tocados_sem_o_proprio():
    """A consulta invertida (candidato da malha contra a arvore dos hexagonos) existe so' pelo
    custo -- Altamira/PA ia de ~10 s a ~1 s. A resposta tem de ser a de `tocados` sem o proprio,
    com a mesma ordem e a comparacao de UF sem caixa."""
    import numpy as np
    from shapely.strtree import STRtree

    from motor_expansao.api.service import _MalhaMunicipal

    geoms = [box(0, 0, 1, 1), box(1, 0, 2, 1), box(0, 1, 2, 2), box(5, 5, 6, 6)]
    meta = [("SP", "1"), ("sp", "2"), ("MG", "3"), ("MG", "4")]
    malha = _MalhaMunicipal(STRtree(geoms), meta, geoms)
    casos = [
        np.array([box(0.8, 0.2, 1.2, 0.4), box(0.1, 0.1, 0.2, 0.2)], dtype=object),
        np.array([box(0.5, 0.5, 1.5, 1.5)], dtype=object),
        np.array([box(0.1, 0.1, 0.2, 0.2)], dtype=object),
        np.array([box(9, 9, 9.1, 9.1)], dtype=object),
    ]
    for hexes in casos:
        for proprio in [("SP", "1"), ("SP", "2"), ("MG", "3")]:
            esperado = [c for c in malha.tocados(hexes) if (c[0].upper(), c[1]) != proprio]
            assert malha.tocados_fora_de(hexes, proprio) == esperado


def test_sem_a_particao_do_proprio_municipio_a_renda_nao_sai_so_da_borda(
    tmp_path, _formula_neutra
):
    """Sem a particao do PROPRIO municipio, so' o vizinho contribuia: a renda saia apenas nos
    hexagonos de borda e o "Onde crescer" media a cidade por eles, sem aviso. Agora a ausencia
    da propria particao devolve `{}` ("Não disponível" em todos), como antes da DEC-072."""
    a, b, _pa, _pb, borda, dentro = _geografia()

    def _gravar(cod: str, linhas: list[dict]) -> None:
        destino = tmp_path / "uf=SP" / f"cod_municipio={cod}"
        destino.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(linhas).to_parquet(destino / "part-000.parquet", index=False)

    _gravar("3502754", [_setor("V", borda, 2000.0, 10.0)])
    sem_proprio = rm.carregar_renda_domiciliar_por_hex(
        "SP", "3550605", tmp_path, hexes=[a, b], vizinhos=[("SP", "3502754")]
    )
    assert sem_proprio == {}

    _gravar("3550605", [_setor("P", dentro, 1000.0, 10.0)])
    com_proprio = rm.carregar_renda_domiciliar_por_hex(
        "SP", "3550605", tmp_path, hexes=[a, b], vizinhos=[("SP", "3502754")]
    )
    assert a in com_proprio  # com a propria particao, o vizinho volta a somar normalmente


# --- regressao com dado real ---------------------------------------------------------------


def _geo_dir() -> Path:
    base = os.environ.get("MOTOR_DATA_DIR")
    candidatos = [Path(base)] if base else []
    candidatos.append(Path(__file__).resolve().parents[2] / "data")
    for raiz in candidatos:
        geo = raiz / "outputs" / "setores_censitarios_2022_geo"
        if (geo / "uf=SP" / "cod_municipio=3550605").is_dir() and (
            geo / "uf=SP" / "cod_municipio=3502754"
        ).is_dir():
            return geo
    pytest.skip("particoes reais de Sao Roque/Aracariguama ausentes (setores_censitarios_2022_geo)")


def test_sao_roque_87a810344_sai_com_renda_por_area(monkeypatch):
    """Numero medido em 2026-10-16 com uplift nacional 1,632 e fator temporal 1,0 (o que a base
    local resolve sem as tabelas de uplift; travado aqui para o teste nao depender delas).
    Por area, com Aracariguama: R$ 4.328,31. So' com Sao Roque: R$ 4.392,77."""
    geo = _geo_dir()
    monkeypatch.setattr(
        "motor_expansao.dashboard.constants.uplift_composicao_por_setor", lambda *_a, **_k: 1.632
    )
    monkeypatch.setattr("motor_expansao.dashboard.constants.FATOR_TEMPORAL_RENDA", 1.0)

    hx = "87a810344ffffff"
    com_vizinho = rm.carregar_renda_domiciliar_por_hex(
        "SP", "3550605", geo, vizinhos=[("SP", "3502754")]
    )
    so_proprio = rm.carregar_renda_domiciliar_por_hex("SP", "3550605", geo)
    assert com_vizinho[hx] == pytest.approx(4328.31, abs=0.5)
    assert so_proprio[hx] == pytest.approx(4392.77, abs=0.5)

    # O vizinho 87a810363ffffff, do centro do bbox do setor 355060505000055 (18 domicilios),
    # herdava os 18 inteiros. Agora recebe 10,85 (60,3% da area do setor) e o 87a810344, 0,96
    # (5,3%); o resto vai a outros cinco hexagonos e a soma fecha nos 18. Valor do hexagono
    # medido em 2026-10-16 com a mesma formula neutralizada acima.
    assert com_vizinho["87a810363ffffff"] == pytest.approx(6448.04, abs=0.5)
    from motor_expansao.pipelines.materializar_setores_censitarios_geo import ler_particao_setores

    sr = ler_particao_setores(
        root=geo, uf="SP", cod_municipio="3550605",
        columns=[*rm._COLUNAS_RENDA_HEX, "geometry_wkb"],
    )
    setor = sr[sr["cod_setor"].astype(str) == "355060505000055"]
    contrib = rm.contribuicoes_renda_por_area(setor, "SP", "3550605")
    assert contrib["87a810363ffffff"][1] == pytest.approx(10.8513, abs=1e-3)
    assert contrib["87a810344ffffff"][1] == pytest.approx(0.9575, abs=1e-3)
    assert sum(den for _, den in contrib.values()) == pytest.approx(18.0)
