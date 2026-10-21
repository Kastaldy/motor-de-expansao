"""E1 do plano de correcao da renda: as telas que serviam renda CRUA passam pela cadeia canonica.

Cada teste trava UMA superficie da frente (b) contra a formula do modulo `motor_expansao.renda`
(com o fator VIGENTE, qualquer que seja ele) e contra o numero cru de antes:

  - perfil do bairro do PDF Pontual: na MESMA escala do card "Renda media domiciliar";
  - campo `renda_media_domiciliar_raio` da API: a domiciliar canonica (o nome fica verdadeiro);
  - `renda_per_capita` da rede (Executiva): a per capita do tooltip, ponderada no disco;
  - `renda_pc` de Oportunidades: a per capita do tooltip do hexagono do imovel;
  - painel "Renda per capita" do Relatorio Municipal: a SIDRA com o fator, pelo modulo;
  - rotulo da camada de calor de setor = a grandeza que o servidor manda.

O mapa de calor (payload) e o `/api/hexagonos` estao em `test_piloto_web_endpoints.py`, junto
das fixtures das rotas. A varredura (R6) esta em `tests/contracts/test_renda_ponto_unico.py`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import pytest
from pyproj import Transformer
from shapely.geometry import box
from shapely.ops import transform

from motor_expansao import renda
from motor_expansao.dashboard.censo_point import (
    CRS_ORIGEM_CENSO,
    _local_metric_crs,
    agregar_perfil_bairro_distrito,
    analisar_ponto_censitario_setores,
)
from motor_expansao.renda import hex as renda_hex
from tests.unit.renda_fixtures import apontar_staging_renda, fixar_fatores, fixar_uplift_setor

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402

LAT_C, LNG_C = -23.55, -46.63


def _setor(cod: str, local_geom, *, v06004: float, moradores: float, dom: float) -> dict:
    para_wgs = Transformer.from_crs(
        _local_metric_crs(LAT_C, LNG_C), CRS_ORIGEM_CENSO, always_xy=True
    )
    geom = transform(para_wgs.transform, local_geom)
    minx, miny, maxx, maxy = geom.bounds
    return {
        "cod_setor": cod,
        "uf": "SP",
        "cod_municipio": "3550308",
        "nome_municipio": "SAO PAULO",
        "cod_bairro": "0001",
        "nome_bairro": "Bairro Teste",
        "area_setor_m2": float(local_geom.area),
        "geometry_wkb": geom.wkb,
        "bbox_minx": minx,
        "bbox_miny": miny,
        "bbox_maxx": maxx,
        "bbox_maxy": maxy,
        "pop_total_setor_2022": dom * moradores,
        "domicilios_particulares_ocupados_setor_2022": dom,
        "renda_responsavel_media_setor_2022": v06004,
        "avg_moradores_domicilio_setor_2022": moradores,
        "renda_per_capita_setor_2022": v06004 / moradores,
        "renda_per_capita_setor_2022_calibrada": v06004 / moradores * 1.2335,
        "score_setor_2022_calibrado": 50.0,
        "densidade_pop_setor_hab_km2": 10000.0,
    }


# ---------------------------------------------------------------------------
# Perfil do bairro: mesma escala do card
# ---------------------------------------------------------------------------


def test_perfil_do_bairro_sai_na_mesma_escala_do_card_do_raio(monkeypatch, tmp_path) -> None:
    """Um setor so, inteiro dentro do raio: bairro e raio sao o MESMO conjunto, entao o perfil
    (antes a V06004 bruta, ~0,53x) tem de dar o mesmo numero do card."""
    fixar_uplift_setor(monkeypatch, 1.6)
    fixar_fatores(monkeypatch, tmp_path, per_capita=1.2, domiciliar=1.1)
    df = pd.DataFrame(
        [_setor("1", box(-200, -200, 200, 200), v06004=3000.0, moradores=3.0, dom=300.0)]
    )

    card = analisar_ponto_censitario_setores(LAT_C, LNG_C, df, raio_km=1.0)
    perfil = agregar_perfil_bairro_distrito(
        df, cod_bairro="0001", nome_bairro="Bairro Teste", uf="SP", cod_municipio="3550308"
    )

    assert card["renda_domiciliar_total_raio"] == pytest.approx(3000.0 * 1.6 * 1.1, abs=0.01)
    assert perfil["renda_media_domiciliar"] == pytest.approx(
        card["renda_domiciliar_total_raio"], abs=0.01
    )
    assert perfil["renda_media_domiciliar"] != pytest.approx(3000.0, abs=1)  # a V06004 crua


def test_perfil_do_bairro_reconstroi_a_v06004_pela_per_capita_bruta(monkeypatch, tmp_path) -> None:
    """Setor sem V06004: reconstruida por per capita BRUTA x moradores (nunca a calibrada)."""
    fixar_uplift_setor(monkeypatch, 1.0)
    fixar_fatores(monkeypatch, tmp_path, per_capita=1.0)
    linha = _setor("1", box(-200, -200, 200, 200), v06004=3000.0, moradores=3.0, dom=300.0)
    linha["renda_responsavel_media_setor_2022"] = None
    perfil = agregar_perfil_bairro_distrito(
        pd.DataFrame([linha]), cod_bairro="0001", uf="SP", cod_municipio="3550308"
    )
    assert perfil["renda_media_domiciliar"] == pytest.approx(3000.0, abs=0.01)


# ---------------------------------------------------------------------------
# API: renda_media_domiciliar_raio
# ---------------------------------------------------------------------------


def test_campo_renda_media_domiciliar_raio_da_api_e_a_domiciliar_canonica(
    monkeypatch, tmp_path
) -> None:
    from motor_expansao.api import service
    from motor_expansao.api.schemas import AnalisarResponseJSON

    fixar_uplift_setor(monkeypatch, 1.6)
    fixar_fatores(monkeypatch, tmp_path, per_capita=1.2)
    df = pd.DataFrame(
        [_setor("1", box(-200, -200, 200, 200), v06004=3000.0, moradores=3.0, dom=300.0)]
    )
    monkeypatch.setattr(service, "_resolver_e_carregar", lambda *_a, **_k: ("SP", "3550308", df))
    monkeypatch.setattr(service, "_competitors_ultra", lambda *_a, **_k: (None, None))
    monkeypatch.setattr(service, "fontes_oferta_presentes", lambda *_a, **_k: ())

    out = service.analisar_ponto(LAT_C, LNG_C, None, settings=None)  # type: ignore[arg-type]

    assert out["renda_media_domiciliar_raio"] == pytest.approx(3000.0 * 1.6 * 1.2, abs=0.01)
    assert out["renda_media_domiciliar_raio"] == out["renda_domiciliar_total_raio"]
    # O contrato do campo (nome e tipo) nao muda: o schema publico continua aceitando.
    modelo = AnalisarResponseJSON.model_validate(out)
    assert modelo.renda_media_domiciliar_raio == pytest.approx(5760.0, abs=0.01)


# ---------------------------------------------------------------------------
# Rede (Executiva): renda_per_capita do disco
# ---------------------------------------------------------------------------


def _bloco_rede() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"hex_id": "h0", "uf": "SP", "cod_municipio": 3550308.0, "pop_total_setor_2022": 9000.0,
             "renda_per_capita_setor_2022_calibrada": 2000.0, "renda_per_capita": 1800.0},
            {"hex_id": "h1", "uf": "SP", "cod_municipio": 3550308.0, "pop_total_setor_2022": 1000.0,
             "renda_per_capita_setor_2022_calibrada": 1000.0, "renda_per_capita": 1800.0},
        ]
    ).set_index("hex_id")


def test_renda_per_capita_da_rede_e_a_do_tooltip_ponderada_no_disco(monkeypatch) -> None:
    apontar_staging_renda(monkeypatch, None)
    pilot.limpar_caches()
    bloco = _bloco_rede()
    pesos = {"h0": 1.0, "h1": 0.5}

    valor = pilot._rede_renda_per_capita(bloco, pesos)

    k = pilot._k_calibracao_renda()
    pc = {
        h: renda_hex.renda_per_capita_hex(c / k, "SP", "3550308")
        for h, c in (("h0", 2000.0), ("h1", 1000.0))
    }
    esperado = (pc["h0"] * 9000.0 + pc["h1"] * 500.0) / 9500.0
    assert valor == pytest.approx(round(esperado), abs=1)
    s_crua = (2000.0 * 9000.0 + 1000.0 * 500.0) / 9500.0
    assert valor != pytest.approx(s_crua, rel=0.02)


def test_rede_inteligencia_nao_monta_mais_renda_do_disco() -> None:
    """A per capita e a domiciliar do disco saem do app (cadeia canonica), nunca da calibrada."""
    import rede_inteligencia as ri

    fatos = ri._praca_do_disco("u1", _bloco_rede(), {"u1": ["h0", "h1"]})
    assert "renda_per_capita" not in fatos


# ---------------------------------------------------------------------------
# Oportunidades: renda_pc
# ---------------------------------------------------------------------------


def _imovel(imovel_id: str, hex_id: str) -> dict[str, object]:
    return {
        "imovel_id": imovel_id,
        "titulo": imovel_id,
        "uf": "SP",
        "municipio": "Sao Paulo",
        "area_relevante_m2": 1500.0,
        "preco_aluguel": 30000.0,
        "hex_id": hex_id,
        "m1_residual_fitness": 50.0,
        "m1_residual_total": 1000.0,
        "censo_renda_per_capita_hex": 2600.0,
        "m1_renda_per_capita": 2500.0,
        "status": "ativo",
        "latitude": -23.5,
        "longitude": -46.6,
    }


def test_renda_pc_de_oportunidades_e_a_per_capita_do_tooltip(monkeypatch, tmp_path) -> None:
    apontar_staging_renda(monkeypatch, None)
    enriquecido = tmp_path / "enriquecido"
    (enriquecido / "uf=SP").mkdir(parents=True)
    pd.DataFrame(
        [{"hex_id": "87na0000000ffff", "cod_municipio": "3550308",
          "renda_per_capita_setor_2022_calibrada": 3000.0, "renda_per_capita": 2500.0}]
    ).to_parquet(enriquecido / "uf=SP" / "part-0.parquet")
    caminho = tmp_path / "viaveis.parquet"
    pd.DataFrame(
        [_imovel("na_base", "87na0000000ffff"), _imovel("fora", "87fora000000ffff")]
    ).to_parquet(caminho)
    monkeypatch.setattr(pilot, "ENRICHED_DIR", enriquecido)
    monkeypatch.setattr(pilot, "STAGING_DIR", tmp_path / "staging")
    monkeypatch.setattr(pilot, "OPORTUNIDADES_PATH", caminho)
    monkeypatch.setattr(pilot, "_OPORTUNIDADES_CACHE", None)
    monkeypatch.setattr(pilot, "DOSSIES_DIR", tmp_path / "sem-dossies")
    pilot.limpar_caches()
    try:
        itens = {i["id"]: i for i in pilot.api_oportunidades(limite=10)["itens"]}
    finally:
        pilot._OPORTUNIDADES_CACHE = None

    k = pilot._k_calibracao_renda()
    # Hexagono na base: a MESMA conta do tooltip, sobre a linha da base (3.000, nao 2.600).
    na_base = renda_hex.renda_per_capita_hex(3000.0 / k, "SP", "3550308")
    assert itens["na_base"]["renda_pc"] == pytest.approx(round(na_base), abs=1)
    # Fora da base: o valor do coletor passa pelo MESMO modulo (cascata da UF), nunca cru.
    fora = renda_hex.renda_per_capita_hex(2600.0 / k, "SP", None)
    assert itens["fora"]["renda_pc"] == pytest.approx(round(fora), abs=1)
    for item in itens.values():
        assert item["renda_pc"] not in (2600.0, 2500.0)


# ---------------------------------------------------------------------------
# Relatorio Municipal: painel "Renda per capita"
# ---------------------------------------------------------------------------


def test_painel_per_capita_do_relatorio_municipal_aplica_o_fator(monkeypatch) -> None:
    from motor_expansao.dashboard.relatorio_municipal import agregar_municipio

    apontar_staging_renda(monkeypatch, None)
    df = pd.DataFrame(
        [
            {"hex_id": f"87a8100c{i}ffffff", "lat": -23.55, "lng": -46.63,
             "nome_municipio": "SAO PAULO", "uf": "SP", "cod_municipio": "3550308",
             "pop_total_setor_2022": 1000.0 * (i + 1), "renda_per_capita": 3000.0,
             "oferta_efetiva_disponivel": 100.0}
            for i in range(3)
        ]
    )
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")

    # SIDRA ja e per capita: base = SIDRA / uplift; per capita = base x uplift x moradores x
    # F_pc / moradores -- na pratica, SIDRA x F_pc (com o arredondamento de exibicao do hex).
    uplift = renda.uplift_municipio("SP", "3550308")
    esperado = renda_hex.renda_per_capita_hex(3000.0 / uplift, "SP", "3550308")
    assert res["renda_per_capita_media"] == pytest.approx(esperado)
    assert res["renda_per_capita_media"] == pytest.approx(
        3000.0 * renda.fator("SP", "per_capita"), rel=1e-3
    )


# ---------------------------------------------------------------------------
# Rotulo da camada de calor = grandeza servida
# ---------------------------------------------------------------------------


def _ler(rel: str) -> str:
    return (_REPO / rel).read_text(encoding="utf-8")


def test_rotulo_da_camada_de_calor_e_a_grandeza_servida() -> None:
    """O servidor manda `renda_domiciliar`; o tipo, o mapa, a legenda e a faixa dizem o mesmo."""
    app_py = _ler("web/server/app.py")
    corpo = app_py[app_py.index("def _setores_heatmap_features") :]
    corpo = corpo[: corpo.index("\n@app.get")]
    assert '"renda_domiciliar":' in corpo
    assert '"renda":' not in corpo

    tipos = _ler("web/src/lib/types.ts")
    bloco = tipos[tipos.index("export interface SetorHeatmap") :]
    bloco = bloco[: bloco.index("}")]
    assert re.search(r"\brenda_domiciliar: number \| null", bloco)
    assert not re.search(r"\brenda: number", bloco)

    assert "rendaSetorToColor(d.renda_domiciliar)" in _ler("web/src/components/HexMap.tsx")

    calor = _ler("web/src/lib/camadas-calor.ts")
    assert "RENDA_DOMICILIAR_SETOR_BANDS" in calor
    assert "'Renda domiciliar'" in calor and "'por domicílio/mês'" in calor
    assert "per capita" not in calor.split("export function legendaDoCalor")[1]

    mapa = _ler("web/src/screens/MapScreen.tsx")
    chave = mapa[mapa.index("id: 'calor-renda'") :][:200]
    assert "titulo: 'Renda domiciliar'" in chave
