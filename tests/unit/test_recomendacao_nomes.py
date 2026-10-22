"""Nome das regioes recomendadas (teste 16 da spec da Fase 2).

Paridade: o 1o bairro de `bairros_ordenados_por_hex` e o bairro dominante de
`relatorio_municipal.bairros_por_hex_de_setores` no MESMO conjunto de setores (o pacote da
recomendacao nao importa o `relatorio_municipal`; a paridade e verificada aqui). E o rotulo:
duas regioes recomendadas com o mesmo nome ganham o 2o bairro ("A / B").
"""

from __future__ import annotations

import h3
import numpy as np
import pandas as pd

from motor_expansao.dashboard.relatorio_municipal import bairros_por_hex_de_setores
from motor_expansao.recomendacao import bairros_ordenados_por_hex, rotulos_das_regioes

_HEX_CENTRO = h3.latlng_to_cell(-23.5505, -46.6333, 7)
# Centro da CELULA: os setores de teste ficam a ~150 m dele, longe da borda do hexagono.
_CENTRO = h3.cell_to_latlng(_HEX_CENTRO)
_HEX_OUTRO = next(c for c in h3.grid_ring(_HEX_CENTRO, 2))


def _setor(lat: float, lng: float, pop: float | None, **nomes: object) -> dict[str, object]:
    d = 0.0005
    return {
        "nome_municipio": "São Paulo",
        "nome_bairro": None,
        "nome_subdistrito": None,
        "nome_distrito": None,
        "bbox_minx": lng - d,
        "bbox_maxx": lng + d,
        "bbox_miny": lat - d,
        "bbox_maxy": lat + d,
        "pop_total_setor_2022": np.nan if pop is None else pop,
        **nomes,
    }


def _setores() -> pd.DataFrame:
    lat, lng = _CENTRO
    outro = h3.cell_to_latlng(_HEX_OUTRO)
    linhas = [
        # hex do centro: Se 300+200, Republica 400 -> Se domina; Bela Vista empata com Liberdade
        _setor(lat, lng, 300.0, nome_bairro="Sé"),
        _setor(lat + 0.001, lng, 200.0, nome_bairro="Sé"),
        _setor(lat, lng + 0.001, 400.0, nome_bairro="República"),
        _setor(lat - 0.001, lng, 50.0, nome_bairro="Liberdade"),
        _setor(lat, lng - 0.001, 50.0, nome_bairro="Bela Vista"),
        # sem bairro: subdistrito igual ao municipio e ignorado, cai no distrito
        _setor(lat + 0.0015, lng + 0.0015, 10.0, nome_subdistrito="São Paulo", nome_distrito="Sé"),
        # populacao nula/negativa vira peso 0 (o bairro existe pelo peso minimo)
        _setor(lat - 0.0015, lng - 0.0015, None, nome_bairro="Cambuci"),
        _setor(lat - 0.0012, lng + 0.0012, -3.0, nome_bairro="Aclimação"),
        # bbox invalida e setor sem nome nenhum: ignorados
        _setor(lat, lng, 999999.0, nome_bairro="Fantasma") | {"bbox_minx": np.nan},
        _setor(lat, lng, 999999.0),
        # outro hexagono, empate exato de populacao -> desempate por nome
        _setor(outro[0], outro[1], 100.0, nome_bairro="Moema"),
        _setor(outro[0] + 0.0005, outro[1], 100.0, nome_bairro="Ibirapuera"),
    ]
    return pd.DataFrame(linhas)


def test_paridade_do_bairro_dominante_com_o_relatorio_municipal() -> None:
    setores = _setores()
    ordenados = bairros_ordenados_por_hex(setores)
    dominante = bairros_por_hex_de_setores(setores)
    assert set(ordenados) == set(dominante)
    assert len(ordenados) >= 2
    for hid, lista in ordenados.items():
        assert lista[0] == dominante[hid]
    assert ordenados[_HEX_CENTRO][:2] == ["Sé", "República"]
    assert "Fantasma" not in ordenados[_HEX_CENTRO]
    assert ordenados[_HEX_OUTRO] == ["Ibirapuera", "Moema"]  # empate exato -> nome asc


def test_paridade_quando_a_cascata_decide_o_dominante() -> None:
    """O setor que DECIDE o hexagono so tem subdistrito == municipio e distrito "Sé": o nome tem
    de ser "Sé" (o municipio "São Paulo" nunca vira nome de regiao), nos dois lados."""
    lat, lng = _CENTRO
    setores = pd.DataFrame(
        [
            _setor(lat, lng, 900.0, nome_subdistrito="São Paulo", nome_distrito="Sé"),
            _setor(lat + 0.001, lng, 400.0, nome_bairro="República"),
            # nivel grosso igual ao municipio em CAIXA diferente tambem e ignorado
            _setor(lat, lng + 0.001, 50.0, nome_subdistrito="SÃO PAULO", nome_distrito="Brás"),
        ]
    )
    ordenados = bairros_ordenados_por_hex(setores)
    assert ordenados[_HEX_CENTRO] == ["Sé", "República", "Brás"]
    assert ordenados[_HEX_CENTRO][0] == bairros_por_hex_de_setores(setores)[_HEX_CENTRO]


def test_paridade_em_casos_vazios() -> None:
    assert bairros_ordenados_por_hex(None) == {} == bairros_por_hex_de_setores(None)
    vazio = _setores().iloc[0:0]
    assert bairros_ordenados_por_hex(vazio) == {} == bairros_por_hex_de_setores(vazio)
    sem_coluna = _setores().drop(columns=["nome_bairro"])
    assert bairros_ordenados_por_hex(sem_coluna) == {} == bairros_por_hex_de_setores(sem_coluna)


def test_nome_repetido_ganha_o_segundo_bairro() -> None:
    bairros = {
        # 3+ bairros: o rotulo leva o 2o (mais populoso depois do dominante), nunca o ultimo
        "h1": ["Pinheiros", "Jardim Paulistano", "Jardim Europa", "Cerqueira César"],
        "h2": ["Pinheiros", "Alto de Pinheiros", "Vila Madalena"],
        "h3": ["Moema"],
        "h4": ["Pinheiros"],  # repetido, mas sem 2o bairro: fica so o nome
        "h5": [],
    }
    rotulos = rotulos_das_regioes(["h1", "h2", "h3", "h4", "h5", "h6"], bairros)
    assert rotulos == {
        "h1": "Pinheiros / Jardim Paulistano",
        "h2": "Pinheiros / Alto de Pinheiros",
        "h3": "Moema",
        "h4": "Pinheiros",
    }


def test_nome_unico_nao_ganha_segundo_bairro() -> None:
    bairros = {"h1": ["Pinheiros", "Jardim Paulistano"], "h2": ["Moema", "Vila Olímpia"]}
    assert rotulos_das_regioes(["h1", "h2"], bairros) == {"h1": "Pinheiros", "h2": "Moema"}
    # so as regioes RECOMENDADAS contam: h2 fora da lista nao gera repeticao
    bairros["h2"] = ["Pinheiros", "X"]
    assert rotulos_das_regioes(["h1"], bairros) == {"h1": "Pinheiros"}
