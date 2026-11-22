"""O painel de cada master na tela Masters do piloto (DEC-089). Funções puras: o servidor lê os
parquets da ingestão (`masters.ingestao`) e a base do Growth, e chama daqui.

De onde vem cada coisa:

* contratos, inauguradas e assinadas: a planilha de levantamento, ingerida em `data/staging`;
* data de inauguração: a base do Growth (que o motor atualiza todo dia), casada pelo nome da
  unidade e pela UF com a chave do próprio piloto (`chave`, passada por quem chama: é a
  `_chave_unidade` do servidor, que tira o sufixo de UF das três grafias que convivem nas bases).

As regras de status (aprovadas com o prompt da DEC-089):

* **em operação**: inaugurada da planilha com data no Growth até hoje. Sem par no Growth, fica
  em operação marcada "sem data no Growth" e fora da conta do ano;
* **em inauguração**: inaugurada com data FUTURA no Growth, ou assinada na fase "Pré Venda";
* **contratos assinados**: as demais fases do pipeline, por fase.

A meta conta as inauguradas que a planilha atribui ao master (coluna "Meta de abertura") e as que
o contrato manda contar (`conta_tambem`), como o relatório em PDF.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import pandas as pd

from motor_expansao.masters.meta import (
    FASE_PRE_VENDA,
    fase_de_exibicao,
    meses_ate,
    meta_do_ano,
    ordem_da_fase,
)

Chave = Callable[[object], str]

#: Quando a meta é de outro destino que não um master da config ("Holding…" na planilha).
OUTRA_ATRIBUICAO = "outra atribuição"


@dataclass(frozen=True)
class Datas:
    """Datas de inauguração do Growth: por (chave, UF) e, para o desempate, por chave."""

    por_chave_uf: Mapping[tuple[str, str], pd.Timestamp]
    por_chave: Mapping[str, frozenset[pd.Timestamp]]


def indexar_datas(registros: Iterable[tuple[object, object, object]], chave: Chave) -> Datas:
    """(nome, UF, inauguração) do Growth -> `Datas`. Linha sem data não entra."""
    por_uf: dict[tuple[str, str], pd.Timestamp] = {}
    por_chave: dict[str, set[pd.Timestamp]] = {}
    for nome, uf, data in registros:
        if data is None or pd.isna(data):
            continue
        k, d = chave(nome), pd.Timestamp(data).normalize()
        if not k:
            continue
        por_uf.setdefault((k, str(uf or "").strip().upper()), d)
        por_chave.setdefault(k, set()).add(d)
    return Datas(por_uf, {k: frozenset(v) for k, v in por_chave.items()})


def data_da_unidade(nome: object, uf: object, datas: Datas, chave: Chave) -> pd.Timestamp | None:
    """Inauguração no Growth pelo nome + UF; sem o par, vale o nome quando ele dá uma data só
    (Novo Gama está em GO na planilha e em DF no Growth, 17/11)."""
    k = chave(nome)
    d = datas.por_chave_uf.get((k, str(uf or "").strip().upper()))
    if d is not None:
        return d
    unicas = datas.por_chave.get(k, frozenset())
    return next(iter(unicas)) if len(unicas) == 1 else None


def _iso(d: pd.Timestamp | None) -> str | None:
    return d.strftime("%Y-%m-%d") if d is not None else None


def _num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _int(v: Any) -> int | None:
    f = _num(v)
    return int(f) if f is not None else None


def _lista(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, float) and pd.isna(v):
        return []
    return [str(x) for x in list(v)]


def _texto(v: Any) -> str | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    t = str(v).strip()
    return t or None


def painel_do_master(
    master_id: str,
    contratos: pd.DataFrame,
    inauguradas: pd.DataFrame,
    pipeline: pd.DataFrame,
    datas: Datas,
    chave: Chave,
    hoje: pd.Timestamp,
) -> dict[str, Any] | None:
    """O painel de um master; `None` se o id não está nos contratos."""
    hoje = pd.Timestamp(hoje).normalize()
    linha = contratos[contratos["master_id"] == master_id]
    if linha.empty:
        return None
    c = linha.iloc[0]
    nomes = dict(zip(contratos["master_id"], contratos["nome"], strict=True))
    conta_tambem = {chave(u) for u in _lista(c.get("conta_tambem"))}

    # As inauguradas do master: da seção dele, atribuídas à meta dele ou que o contrato manda
    # contar. Uma linha só por unidade (nome + UF).
    meta_col = inauguradas["meta_master_id"]
    sel = inauguradas[
        (inauguradas["master_id"] == master_id)
        | (meta_col == master_id)
        | inauguradas["unidade"].map(chave).isin(conta_tambem)
    ]
    em_operacao: list[dict[str, Any]] = []
    em_inauguracao: list[dict[str, Any]] = []
    vistas: set[tuple[str, str]] = set()
    for r in sel.itertuples(index=False):
        uf = str(r.uf or "").upper()
        if (chave(r.unidade), uf) in vistas:
            continue
        vistas.add((chave(r.unidade), uf))
        conta = r.meta_master_id == master_id or chave(r.unidade) in conta_tambem
        data = data_da_unidade(r.unidade, uf, datas, chave)
        meta_de = None
        if not conta:
            meta_de = nomes.get(r.meta_master_id) if r.meta_master_id else OUTRA_ATRIBUICAO
        operacao = r.operacao_master_id
        item = {
            "unidade": str(r.unidade),
            "uf": uf or None,
            "conta_para_meta": bool(conta),
            # Quem opera, quando não é o próprio master (Bertioga: meta Camargo, operação GEMPRO).
            "operacao_de": nomes.get(operacao) if operacao and operacao != master_id else None,
            "meta_de": meta_de,
        }
        if data is not None and data > hoje:
            em_inauguracao.append({**item, "previsao": _iso(data), "fase": None, "cidade": None})
        else:
            em_operacao.append({**item, "inauguracao": _iso(data), "sem_data": data is None})

    # O pipeline do master: "Pré Venda" já é inauguração; o resto é contrato assinado, por fase.
    pipe = pipeline[pipeline["master_id"] == master_id]
    por_fase: dict[str, list[dict[str, Any]]] = {}
    for r in pipe.itertuples(index=False):
        fase = fase_de_exibicao(r.fase)
        dentro = r.dentro_territorio
        unidade = {
            "unidade": str(r.unidade),
            "cidade": _texto(r.cidade),
            "uf": _texto(r.uf),
            "dentro_territorio": None if dentro is None or pd.isna(dentro) else bool(dentro),
        }
        if fase == FASE_PRE_VENDA:
            em_inauguracao.append(
                {
                    **unidade,
                    "previsao": None,
                    "fase": fase,
                    "conta_para_meta": None,
                    "operacao_de": None,
                    "meta_de": None,
                }
            )
        else:
            por_fase.setdefault(fase, []).append(unidade)
    assinados: list[dict[str, Any]] = [
        {"fase": f, "unidades": sorted(por_fase[f], key=lambda u: str(u["unidade"]))}
        for f in sorted(por_fase, key=ordem_da_fase)
    ]

    # Mais recentes primeiro; as sem data no fim (sort estável: a 2ª ordenação preserva a 1ª).
    em_operacao.sort(key=lambda u: u["inauguracao"] or "", reverse=True)
    em_operacao.sort(key=lambda u: u["sem_data"])
    em_inauguracao.sort(key=lambda u: (u["previsao"] is None, u["previsao"] or "", u["unidade"]))

    # A meta: as que contam e já abriram (as sem data contam no "desde o início", fora do ano).
    contam = [u for u in em_operacao if u["conta_para_meta"]]
    datas_contam = [pd.Timestamp(u["inauguracao"]) for u in contam if u["inauguracao"]]
    por_ano = _int(c.get("meta_por_ano"))
    quantidade = _int(c.get("meta_quantidade"))
    n_ano = sum(1 for d in datas_contam if d.year == hoje.year and d <= hoje)
    prazo_txt = _texto(c.get("meta_prazo"))
    prazo = pd.Timestamp(prazo_txt) if prazo_txt else None
    trimestres = [
        {
            "trimestre": int(t["trimestre"].quarter),
            "novas": int(t["novas"]),
            "acumulado": int(t["acumulado"]),
            "pct": _num(t["pct"]),
            "futuro": bool(t["futuro"]),
            "atual": bool(t["atual"]),
        }
        for t in meta_do_ano(datas_contam, por_ano, hoje)
    ]
    n_assinados = sum(len(f["unidades"]) for f in assinados)
    return {
        "id": master_id,
        # O nome do MASTER (o titular), e o território dele à parte (18/11/2026, Juan: "precisa
        # estar com o nome do master", não o do estado).
        "nome": str(c["nome"]),
        "territorio": _texto(c.get("territorio")),
        "tipo_area": _texto(c.get("tipo_area")),
        "regioes": [
            {"nome": n, "tipo": t}
            for n, t in zip(_lista(c.get("regioes")), _lista(c.get("regioes_tipos")), strict=False)
        ],
        "nota": _texto(c.get("nota")),
        "resumo": {
            "em_operacao": len(em_operacao),
            "em_inauguracao": len(em_inauguracao),
            "assinados": n_assinados,
            "ano": int(hoje.year),
            "abertas_no_ano": n_ano,
        },
        "meta": {
            "ano": int(hoje.year),
            "n_ano": n_ano,
            "por_ano": por_ano,
            "pct_ano": n_ano / por_ano if por_ano else None,
            "trimestres": trimestres,
            "n_contam": len(contam),
            "quantidade": quantidade,
            "pct_contrato": len(contam) / quantidade if quantidade else None,
            "prazo": _iso(prazo),
            "meses_ate_prazo": meses_ate(prazo, hoje) if prazo is not None else None,
            "sem_data": [u["unidade"] for u in contam if u["sem_data"]],
        },
        "em_operacao": em_operacao,
        "em_inauguracao": em_inauguracao,
        "assinados": assinados,
    }


def cards(
    contratos: pd.DataFrame,
    inauguradas: pd.DataFrame,
    pipeline: pd.DataFrame,
    datas: Datas,
    chave: Chave,
    hoje: pd.Timestamp,
) -> list[dict[str, Any]]:
    """Um card por master, na ordem da config: o resumo do painel e a meta em poucas linhas."""
    out: list[dict[str, Any]] = []
    for mid in contratos.sort_values("ordem")["master_id"]:
        p = painel_do_master(str(mid), contratos, inauguradas, pipeline, datas, chave, hoje)
        if p is None:
            continue
        m = p["meta"]
        out.append(
            {
                "id": p["id"],
                "nome": p["nome"],
                "territorio": p["territorio"],
                "tipo_area": p["tipo_area"],
                "regioes": [r["nome"] for r in p["regioes"]],
                "resumo": p["resumo"],
                "meta": {
                    k: m[k]
                    for k in (
                        "ano",
                        "n_ano",
                        "por_ano",
                        "n_contam",
                        "quantidade",
                        "prazo",
                        "meses_ate_prazo",
                    )
                },
            }
        )
    return out
