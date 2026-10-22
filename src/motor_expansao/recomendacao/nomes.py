"""Nome de cada regiao recomendada: o bairro dominante do hexagono, como no Relatorio Municipal.

Puro dado um DataFrame de setores JA carregado (quem le a particao geo e o chamador). A
atribuicao e a MESMA de `dashboard.relatorio_municipal.bairros_por_hex_de_setores` -- centro do
bbox do setor -> hexagono res-7; soma da `pop_total_setor_2022` por localidade; cascata bairro ->
subdistrito -> distrito ignorando o nivel grosso igual ao nome do municipio; desempate estavel
por nome --, para que a lista da recomendacao e o mapa municipal nunca deem nomes diferentes ao
mesmo hexagono. A diferenca e que aqui sai a lista INTEIRA de bairros, em ordem de populacao: o
2o bairro desempata duas regioes recomendadas com o mesmo nome.

O `relatorio_municipal` NAO e importado (e pesado e CRITICO no guard); a paridade com ele e
travada no teste.

PRE-CONDICAO do chamador (Fase 4): os setores tem de chegar JA passados por
`dashboard.bairro_cnefe.aplicar_bairro_cnefe` (DEC-076, fonte UNICA do bairro), como o
Relatorio Municipal e a API fazem antes de `bairros_por_hex_de_setores`. Este modulo nao pode
importa-lo (`dashboard.*` fica fora do pacote), e com os setores CRUS do IBGE a lista nomearia
o hexagono diferente do mapa municipal. A promessa de "mesmo nome" vale para o MESMO frame de
setores dos dois lados.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd

#: Resolucao H3 da recomendacao (a mesma do M1 e do Relatorio Municipal).
_H3_RES = 7
#: Peso minimo por setor: garante a presenca do bairro mesmo com populacao 0 (desempate).
_PESO_MINIMO = 1e-6


def _safe_float(value: Any) -> float:
    num = pd.to_numeric(value, errors="coerce")
    try:
        return float(num)
    except (TypeError, ValueError):
        return float("nan")


def _localidade_do_setor(row: Mapping[str, Any]) -> str | None:
    """Cascata bairro -> subdistrito -> distrito; ignora nivel grosso == nome do municipio."""
    muni = row.get("nome_municipio")
    muni_norm = str(muni).strip().casefold() if muni is not None and not pd.isna(muni) else ""
    for col in ("nome_bairro", "nome_subdistrito", "nome_distrito"):
        val = row.get(col)
        if val is None or pd.isna(val):
            continue
        nome = str(val).strip()
        if not nome or nome.casefold() == "nan":
            continue
        if col != "nome_bairro" and muni_norm and nome.casefold() == muni_norm:
            continue
        return nome
    return None


def bairros_ordenados_por_hex(setores: pd.DataFrame | None) -> dict[str, list[str]]:
    """`hex_id` res-7 -> bairros do hexagono, do mais populoso ao menos (empate: nome asc).

    O primeiro de cada lista e o bairro dominante -- o mesmo de
    `relatorio_municipal.bairros_por_hex_de_setores` para o mesmo conjunto de setores.
    `setores` ja deve vir com o bairro do CNEFE aplicado (`aplicar_bairro_cnefe`; ver o topo do
    modulo).
    """
    if setores is None or setores.empty or "nome_bairro" not in setores.columns:
        return {}

    import h3

    pop_por_hex_bairro: dict[str, dict[str, float]] = {}
    for row in setores.to_dict("records"):
        nome = _localidade_do_setor(row)
        if not nome:
            continue
        minx = _safe_float(row.get("bbox_minx"))
        miny = _safe_float(row.get("bbox_miny"))
        maxx = _safe_float(row.get("bbox_maxx"))
        maxy = _safe_float(row.get("bbox_maxy"))
        if any(math.isnan(v) for v in (minx, miny, maxx, maxy)):
            continue
        lat_c = (miny + maxy) / 2.0
        lon_c = (minx + maxx) / 2.0
        try:
            hid = str(h3.latlng_to_cell(float(lat_c), float(lon_c), _H3_RES))
        except Exception:  # noqa: BLE001 -- coordenada invalida: setor ignorado, como no municipal
            continue
        peso = _safe_float(row.get("pop_total_setor_2022"))
        if math.isnan(peso) or peso < 0:
            peso = 0.0
        bucket = pop_por_hex_bairro.setdefault(hid, {})
        bucket[nome] = bucket.get(nome, 0.0) + peso + _PESO_MINIMO

    return {
        hid: [nome for nome, _pop in sorted(bucket.items(), key=lambda kv: (-kv[1], kv[0]))]
        for hid, bucket in pop_por_hex_bairro.items()
    }


def rotulos_das_regioes(
    hex_ids_em_ordem: Iterable[str], bairros_ordenados: Mapping[str, list[str]]
) -> dict[str, str]:
    """`hex_id` -> rotulo de exibicao de cada regiao recomendada.

    O rotulo e o bairro dominante. Se duas (ou mais) regioes recomendadas tem o MESMO bairro
    dominante -- vizinhos podem ocupar varias vagas --, cada uma mostra tambem o seu 2o bairro
    ("A / B"), quando ele existe. Hexagono sem bairro fica FORA do dicionario: o chamador mostra
    a regiao do IBGE/municipio.
    """
    ordem: list[str] = []
    for h in hex_ids_em_ordem:
        if h not in ordem:
            ordem.append(h)
    dominante = {h: bairros_ordenados[h][0] for h in ordem if bairros_ordenados.get(h)}
    contagem: dict[str, int] = {}
    for nome in dominante.values():
        contagem[nome] = contagem.get(nome, 0) + 1
    rotulos: dict[str, str] = {}
    for h, nome in dominante.items():
        lista = bairros_ordenados[h]
        if contagem[nome] > 1 and len(lista) > 1:
            rotulos[h] = f"{nome} / {lista[1]}"
        else:
            rotulos[h] = nome
    return rotulos
