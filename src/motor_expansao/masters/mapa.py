"""O mapa do território no painel do master (BLK-MASTERS-04; 18/11/2026, Juan: "deixe uma parte do
relatório nessa aba, o mapa, assim como está na carteira, com a área e a opção de ligar a renda e a
densidade"). Função pura: o servidor lê o mercado e as unidades Ultra e chama daqui.

Os hexágonos do território são os do mapa do relatório em PDF (os povoados de cada região, pela
mesma atribuição `analise.atribuir_regiao`), com as mesmas cores por região. As camadas de renda e
densidade ficam no servidor, com a conta do Mapa do motor (`_renda_domiciliar_hex` e a densidade do
hexágono), para o número da tela do master ser o mesmo do Mapa.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from motor_expansao.masters.analise import atribuir_regiao
from motor_expansao.masters.territorios import Master

#: Cor de cada região, na ordem do contrato (validada para daltonismo com rótulo direto): a do
#: mapa da tela do master e a do mapa do território no PDF (`relatorio_pdf` importa daqui).
CORES_REGIAO = ("#00A79D", "#C23C8E", "#F0941E", "#5B3FA8")
#: Colunas do mercado que o mapa lê (o servidor filtra pelas UFs do master).
COLUNAS_MERCADO_MAPA = ("uf", "nome_municipio", "hex_id", "lat", "lng", "pop_hex_base")


def territorio(mercado: pd.DataFrame, master: Master, ultra: pd.DataFrame | None) -> dict[str, Any]:
    """Regiões (id, nome, cor), hexágonos `[hex_id, índice da região]`, unidades Ultra `[lat, lng,
    nome]` dentro do território e o enquadramento `[oeste, sul, leste, norte]` (None sem hexágono)."""
    regioes = [
        {"id": r.id, "nome": r.nome, "cor": CORES_REGIAO[i % len(CORES_REGIAO)]}
        for i, r in enumerate(master.regioes)
    ]
    vazio: dict[str, Any] = {"regioes": regioes, "hexes": [], "ultra": [], "bbox": None}
    if not master.regioes or mercado.empty:
        return vazio
    m = mercado.assign(regiao_id=atribuir_regiao(mercado, master))
    m = m[m["regiao_id"].notna() & (pd.to_numeric(m["pop_hex_base"], errors="coerce") > 0)]
    if m.empty:
        return vazio
    indice = {r.id: i for i, r in enumerate(master.regioes)}
    hexes = [[str(h), indice[str(r)]] for h, r in zip(m["hex_id"], m["regiao_id"], strict=True)]
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
    bbox = [
        float(m["lng"].min()),
        float(m["lat"].min()),
        float(m["lng"].max()),
        float(m["lat"].max()),
    ]
    return {"regioes": regioes, "hexes": hexes, "ultra": pontos, "bbox": bbox}
