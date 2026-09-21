"""CONTRATO: a carga de setores do Relatorio Pontual segue a GEOMETRIA, nunca o municipio.

Por que um contrato, e nao mais um teste de unidade: o defeito de 2026-09-17 (mapa e Big
Numbers cortados na divisa de Sao Caetano do Sul com Sao Paulo) nao foi um erro de conta —
foi uma PREMISSA, "o municipio do ponto contem a vizinhanca do ponto", que valia na maioria
dos casos e falhava exatamente onde importa. Premissa assim renasce: basta alguem, meses
depois, reintroduzir um filtro por `cod_municipio` para "economizar leitura", e o sintoma
volta sem nenhum teste vermelho — porque o payload continua plausivel.

Estes testes travam DUAS propriedades, e nenhuma delas e' sobre numeros do relatorio:

1. o universo carregado cobre TODOS os municipios que o frame do mapa alcanca;
2. o alcance e' LIDO de quem desenha o frame — nao esta cravado no lado da selecao.

A (2) e' a que impede o renascimento: se alguem fixar um literal em `service.py`, o mapa
pode crescer e a selecao ficar para tras, e o buraco no choropleth volta em silencio.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest
from shapely.geometry import box

# Tres municipios em faixas verticais coladas, o do meio contendo o ponto. O de LESTE fica
# em OUTRA UF de proposito: divisa de estado e' o mesmo defeito com outro nome.
_LAT, _LNG = -23.60000, -46.57000
_OESTE = box(_LNG - 0.12, _LAT - 0.05, _LNG - 0.003, _LAT + 0.05)
_MEIO = box(_LNG - 0.003, _LAT - 0.05, _LNG + 0.003, _LAT + 0.05)
_LESTE = box(_LNG + 0.003, _LAT - 0.05, _LNG + 0.12, _LAT + 0.05)

_MUNICIPIOS = [
    ("SP", "3500001", _OESTE, _LNG - 0.005),
    ("SP", "3500002", _MEIO, _LNG - 0.001),  # o do PONTO
    ("MG", "3100003", _LESTE, _LNG + 0.004),
]
_COD_DO_PONTO = "3500002"


def _escrever_ambiente(tmp_path):
    """Malha (por UF) + uma particao por municipio, cada uma com 2 setores proprios."""
    from shapely import wkb

    ibge_dir = tmp_path / "ibge"
    censo_dir = tmp_path / "geo"
    ibge_dir.mkdir(parents=True, exist_ok=True)

    por_uf: dict[str, list[dict]] = {}
    for uf, cod, geom, lng_base in _MUNICIPIOS:
        por_uf.setdefault(uf, []).append(
            {
                "type": "Feature",
                "properties": {"codarea": cod},
                "geometry": geom.__geo_interface__,
            }
        )
        linhas = []
        for i in range(2):
            setor = box(lng_base, _LAT - 0.001, lng_base + 0.0008, _LAT + 0.001)
            minx, miny, maxx, maxy = setor.bounds
            linhas.append(
                {
                    "cod_setor": f"{cod}{i:08d}",
                    "uf": uf,
                    "cod_municipio": cod,
                    "nome_municipio": f"Municipio {cod}",
                    "geometry_wkb": wkb.dumps(setor),
                    "bbox_minx": minx,
                    "bbox_miny": miny,
                    "bbox_maxx": maxx,
                    "bbox_maxy": maxy,
                    "pop_total_setor_2022": 500.0,
                }
            )
        destino = censo_dir / f"uf={uf}" / f"cod_municipio={cod}"
        destino.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(linhas).to_parquet(destino / "part-000.parquet", index=False)

    for uf, features in por_uf.items():
        (ibge_dir / f"municipios_{uf}.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8"
        )
    return ibge_dir, censo_dir


@pytest.fixture
def settings(tmp_path):
    from motor_expansao.api import service
    from motor_expansao.api.settings import Settings

    ibge_dir, censo_dir = _escrever_ambiente(tmp_path)
    service._carregar_malha.cache_clear()
    try:
        yield Settings(ibge_dir=ibge_dir, censo_geo_dir=censo_dir)
    finally:
        service._carregar_malha.cache_clear()


def test_o_universo_carregado_cobre_o_frame_inteiro_e_nao_o_municipio(settings) -> None:
    """Propriedade 1: todo municipio alcancado pelo frame entra — inclusive de outra UF."""
    from motor_expansao.api.service import _resolver_e_carregar

    _uf, cod_municipio, setores_df = _resolver_e_carregar(_LAT, _LNG, settings)

    assert cod_municipio == _COD_DO_PONTO, "a identidade do ponto e' do municipio que o CONTEM"
    carregados = {str(v) for v in setores_df["cod_municipio"].unique()}
    assert carregados == {cod for _uf2, cod, _g, _l in _MUNICIPIOS}, (
        "a carga parou em algum limite administrativo: com o frame alcancando os tres "
        "municipios, os tres precisam estar no `setores_df`"
    )


def test_o_alcance_e_LIDO_do_frame_e_nao_cravado_na_selecao(settings, monkeypatch) -> None:
    """Propriedade 2 — a que impede o renascimento do defeito.

    Dobrar o alcance do FRAME tem de mudar o que a selecao pede. Se alguem cravar um numero
    em `service.py`, este teste fica vermelho: o frame cresce e a selecao nao acompanha.
    """
    from motor_expansao.api import service
    from motor_expansao.dashboard import censo_map

    malha = service._carregar_malha(str(settings.ibge_dir))
    pequeno = {chave for chave in service._malha_alcancada(malha, _LAT, _LNG)}

    monkeypatch.setattr(censo_map, "alcance_do_frame_km", lambda *_a, **_k: 0.05)
    encolhido = {chave for chave in service._malha_alcancada(malha, _LAT, _LNG)}

    assert encolhido < pequeno, (
        "encolher o frame tinha de encolher a selecao; como nao encolheu, o alcance esta "
        "cravado no lado da selecao em vez de sair de `censo_map.alcance_do_frame_km`"
    )
    assert encolhido == {("SP", _COD_DO_PONTO)}


def test_o_frame_nunca_e_menor_que_o_circulo_da_analise() -> None:
    """O alcance tem de cobrir pelo menos o raio que a ANALISE usa.

    Selecionar pelo circulo (o caminho "obvio") deixaria os cantos do retangulo sem cor —
    trocaria o corte reto da divisa por quatro buracos. O frame e' o piso, nao o teto.
    """
    from motor_expansao.dashboard.censo_map import (
        RAIO_CENSITARIO_DEFAULT_KM,
        alcance_do_frame_km,
    )

    assert alcance_do_frame_km(RAIO_CENSITARIO_DEFAULT_KM) > RAIO_CENSITARIO_DEFAULT_KM
