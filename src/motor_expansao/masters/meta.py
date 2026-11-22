"""A meta de aberturas dos masters e as fases do pipeline (uma fonte só, lida pelo painel do piloto
e pelo relatório)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd

#: Fase do pipeline que já é inauguração (venda de planos antes de abrir): entra em "em
#: inauguração" no painel, e não em "contratos assinados" (DEC-089).
FASE_PRE_VENDA = "Pré Venda"

#: Fases do pipeline, da mais perto de abrir à mais longe; as que não estão aqui vêm depois, em
#: ordem alfabética, e "sem status" por último.
ORDEM_FASES: tuple[str, ...] = (
    FASE_PRE_VENDA,
    "Obras",
    "Projeto",
    "Minuta",
    "Negociação",
    "Buscando Imóvel",
)
FASE_SEM_STATUS = "sem status"

#: Grafias da planilha que viram outra coisa na tela.
_FASE_EXIBICAO: dict[str, str] = {"sem status II": FASE_SEM_STATUS}


def fase_de_exibicao(fase: Any) -> str:
    """A fase como a tela mostra: vazia ou "sem status II" vira "sem status"."""
    if fase is None or (isinstance(fase, float) and pd.isna(fase)) or not str(fase).strip():
        return FASE_SEM_STATUS
    texto = str(fase).strip()
    return _FASE_EXIBICAO.get(texto, texto)


def ordem_da_fase(fase: str) -> tuple[int, str]:
    """Chave de ordenação: as de `ORDEM_FASES` primeiro, na ordem dela; "sem status" por último."""
    if fase in ORDEM_FASES:
        return (ORDEM_FASES.index(fase), fase)
    if fase == FASE_SEM_STATUS:
        return (len(ORDEM_FASES) + 1, fase)
    return (len(ORDEM_FASES), fase)


def meta_do_ano(
    inauguracoes: Iterable[pd.Timestamp], por_ano: int | None, hoje: pd.Timestamp
) -> list[dict[str, Any]]:
    """A meta é anual (17/11, Juan: "a meta é a cada ano, 4 trimestres"): os 4 trimestres do ano
    de `hoje`, com quantas das que contam abriram no ano até o fim de cada um e o % da meta do ano.

    O % só sobe nos trimestres com abertura e zera no ano seguinte. Trimestre que ainda não
    começou vem com `futuro`; sem `por_ano`, o % fica vazio.
    """
    hoje = pd.Timestamp(hoje)
    atual = hoje.to_period("Q")
    no_ano = [pd.Timestamp(x) for x in inauguracoes if pd.Timestamp(x).year == hoje.year]
    tri = [x.to_period("Q") for x in no_ano if x <= hoje]
    linhas: list[dict[str, Any]] = []
    acumulado = 0
    for q in range(1, 5):
        p = pd.Period(year=hoje.year, quarter=q, freq="Q")
        novas = sum(1 for x in tri if x == p)
        acumulado += novas
        linhas.append(
            {
                "trimestre": p,
                "novas": novas,
                "acumulado": acumulado,
                "pct": acumulado / por_ano if por_ano else float("nan"),
                "futuro": p > atual,
                # O trimestre em que o relatório é gerado: ainda em andamento.
                "atual": p == atual,
            }
        )
    return linhas


def meses_ate(prazo: pd.Timestamp, hoje: pd.Timestamp) -> int:
    """Meses inteiros de `hoje` até o prazo (0 quando já venceu)."""
    return max(0, (prazo.year - hoje.year) * 12 + prazo.month - hoje.month)
