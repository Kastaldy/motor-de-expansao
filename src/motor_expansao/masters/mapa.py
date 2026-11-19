"""O mapa do território no painel do master (BLK-MASTERS-04; 18/11/2026, Juan: "deixe uma parte do
relatório nessa aba, o mapa, assim como está na carteira, com a área e a opção de ligar a renda e a
densidade"). Funções puras: o servidor lê o mercado e as unidades Ultra e chama daqui.

O território vai DEMARCADO, não pintado (19/11/2026, Juan: "não precisa deixar a área colorida, só
deixe ela demarcada igual fica no motor"): o contorno de cada região, a união dos hexágonos dela
(todos, e não só os povoados, senão o contorno sairia cheio de buracos); a tela o desenha em
branco. As camadas (renda e densidade, sempre do Censo) ficam no servidor, com os setores do
território inteiro.
"""

from __future__ import annotations

from typing import Any

import h3
import pandas as pd

from motor_expansao.masters.analise import atribuir_regiao
from motor_expansao.masters.territorios import Master

#: Cor de cada região, na ordem do contrato (validada para daltonismo com rótulo direto): a do
#: mapa do território no PDF (`relatorio_pdf` importa daqui); a tela desenha o limite em branco.
CORES_REGIAO = ("#00A79D", "#C23C8E", "#F0941E", "#5B3FA8")
#: Colunas do mercado que o mapa lê (o servidor filtra pelas UFs do master).
COLUNAS_MERCADO_MAPA = (
    "uf",
    "cod_municipio",
    "nome_municipio",
    "hex_id",
    "lat",
    "lng",
    "pop_hex_base",
)
#: Casas decimais das coordenadas do contorno (~1 m): o bastante para o desenho, e o JSON encolhe.
CASAS_CONTORNO = 5


def com_regiao(mercado: pd.DataFrame, master: Master) -> pd.DataFrame:
    """Os hexágonos do mercado que caem no território do master, com o `regiao_id` de cada um."""
    if not master.regioes or mercado.empty:
        return mercado.iloc[0:0].assign(regiao_id=pd.Series(dtype=object))
    m = mercado.assign(regiao_id=atribuir_regiao(mercado, master))
    return m[m["regiao_id"].notna()]


def _poligonos(hex_ids: list[str]) -> list[list[list[list[float]]]]:
    """Os polígonos da união dos hexágonos: `[[anel externo, buracos...], ...]`, cada anel uma
    lista de `[lng, lat]` (o formato do `PathLayer`/`PolygonLayer`)."""
    if not hex_ids:
        return []
    geo = h3.h3shape_to_geo(h3.cells_to_h3shape(hex_ids))
    coords = geo["coordinates"]
    poligonos = [coords] if geo["type"] == "Polygon" else list(coords)
    return [
        [
            [[round(float(x), CASAS_CONTORNO), round(float(y), CASAS_CONTORNO)] for x, y in anel]
            for anel in poligono
        ]
        for poligono in poligonos
    ]


def territorio(mercado: pd.DataFrame, master: Master, ultra: pd.DataFrame | None) -> dict[str, Any]:
    """Regiões (id, nome, cor), o contorno de cada uma, os municípios (para os setores do Censo,
    que vêm por município ao aproximar), as unidades Ultra `[lat, lng, nome]` no território e o
    enquadramento `[oeste, sul, leste, norte]` (None sem hexágono)."""
    regioes = [
        {"id": r.id, "nome": r.nome, "cor": CORES_REGIAO[i % len(CORES_REGIAO)]}
        for i, r in enumerate(master.regioes)
    ]
    vazio: dict[str, Any] = {
        "regioes": regioes,
        "contornos": [],
        "municipios": [],
        "ultra": [],
        "bbox": None,
        "n_hexes": 0,
    }
    m = com_regiao(mercado, master)
    if m.empty:
        return vazio
    indice = {r.id: i for i, r in enumerate(master.regioes)}
    contornos = [
        {"regiao": indice[str(rid)], "poligonos": _poligonos(sorted(map(str, grupo["hex_id"])))}
        for rid, grupo in m.groupby("regiao_id", sort=False)
    ]
    povoados = m[pd.to_numeric(m["pop_hex_base"], errors="coerce") > 0]
    municipios = [
        [
            str(uf),
            str(cod).removesuffix(".0"),
            str(nome),
            [
                float(g["lng"].min()),
                float(g["lat"].min()),
                float(g["lng"].max()),
                float(g["lat"].max()),
            ],
        ]
        for (uf, cod, nome), g in m.dropna(subset=["cod_municipio"]).groupby(
            ["uf", "cod_municipio", "nome_municipio"], sort=True
        )
    ]
    pontos: list[list[Any]] = []
    if ultra is not None and len(ultra) and "hex_id_res7" in ultra.columns:
        dentro = ultra[ultra["hex_id_res7"].isin(set(m["hex_id"]))]
        nomes = (
            dentro["unidade"] if "unidade" in dentro.columns else pd.Series("", index=dentro.index)
        )
        pontos = [
            [round(float(la), 6), round(float(lo), 6), str(n) if pd.notna(n) else ""]
            for la, lo, n in zip(dentro["lat"], dentro["lng"], nomes, strict=True)
        ]
    return {
        "regioes": regioes,
        "contornos": contornos,
        "municipios": municipios,
        "ultra": pontos,
        "bbox": [
            float(m["lng"].min()),
            float(m["lat"].min()),
            float(m["lng"].max()),
            float(m["lat"].max()),
        ],
        "n_hexes": int(len(povoados)),
    }
