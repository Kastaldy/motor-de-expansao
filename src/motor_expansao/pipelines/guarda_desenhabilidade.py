"""Guarda de desenhabilidade da publicacao do mercado (DEC-059, com margem desde 2026-11-05).

A validacao do regen semanal (`scripts/cron/run_regen_mercado.sh`) compara os concorrentes
DESENHAVEIS do rascunho com os do publicado. Ate' 2026-11-05 a regra era "nao pode cair NENHUM":
em 2026-11-01 a coleta trouxe 4.734 contra 4.736 (rotacao normal de semana: 1 academia saiu do
site, 10 vieram sem coordenada, 8 entraram) e o mercado inteiro deixou de ser publicado. Pior, a
regra TRAVA: comparando sempre com o publicado congelado, toda semana abaixo daquele numero
reprova.

A regua passa a ser a da DEC-061 (guarda de coleta parcial do snapshot, mesmo feed): o colapso
POR REDE e' a assinatura de coleta quebrada, e o total e' rede de seguranca para a queda difusa.
Em 2026-09-13 o lote morreu no meio e o total caiu so' 2,6% (4.589 -> 4.470), mas a Selfit
caiu 48% -- e e' isso que reprova. As constantes sao as MESMAS do snapshot
(`vulnerabilidade.contrato`), copiadas e nao importadas para a camada de mercado nao puxar o
pacote de vulnerabilidade inteiro; um teste trava a igualdade, para as duas guardas do mesmo feed
nao divergirem em silencio.
"""

from __future__ import annotations

import pandas as pd

TOLERANCIA_QUEDA_REDE_PCT = 30.0
TOLERANCIA_QUEDA_TOTAL_PCT = 10.0
MIN_UNIDADES_GUARDA_REDE = 5
MIN_UNIDADES_GUARDA_TOTAL = 50


def desenhaveis(df: pd.DataFrame) -> pd.DataFrame:
    """Concorrentes DESENHAVEIS: status valido E coordenada presente.

    As duas condicoes deveriam ser a mesma coisa (`status_registro` DERIVA da validade da
    coordenada em `normalizar_concorrentes`), e e' justamente por isso que a coordenada e'
    checada de novo: a guarda de 2026-08-30 falhou por confiar numa propriedade que
    "obviamente" valia.
    """
    ok = df["status_registro"].astype(str) == "valido"
    ok &= pd.to_numeric(df["lat"], errors="coerce").notna()
    ok &= pd.to_numeric(df["lng"], errors="coerce").notna()
    return df.loc[ok]


def quedas_de_desenhaveis(
    publicado: pd.DataFrame,
    rascunho: pd.DataFrame,
    *,
    tolerancia_rede_pct: float = TOLERANCIA_QUEDA_REDE_PCT,
    tolerancia_total_pct: float = TOLERANCIA_QUEDA_TOTAL_PCT,
    min_unidades_rede: int = MIN_UNIDADES_GUARDA_REDE,
    min_unidades_total: int = MIN_UNIDADES_GUARDA_TOTAL,
) -> list[str]:
    """Motivos para REPROVAR a publicacao; lista vazia = aprova.

    Recebe os dois frames ja' filtrados por `desenhaveis`. Reprova se:
    - uma rede com pelo menos `min_unidades_rede` pins publicados cair mais de
      `tolerancia_rede_pct` (abaixo do piso, uma academia a menos ja' passa de 30%);
    - o total, sobre base de pelo menos `min_unidades_total`, cair mais de `tolerancia_total_pct`.

    Rede que SOME inteira entra pela regra por rede (queda de 100%).
    """
    motivos: list[str] = []
    antes = publicado["rede"].astype(str).value_counts()
    agora = rascunho["rede"].astype(str).value_counts()
    for rede, qtd_antes in antes.items():
        qtd_antes = int(qtd_antes)
        if qtd_antes < min_unidades_rede:
            continue
        qtd_agora = int(agora.get(rede, 0))
        perda = 100.0 * (qtd_antes - qtd_agora) / qtd_antes
        if perda > tolerancia_rede_pct:
            motivos.append(
                f"concorrentes DESENHAVEIS da rede {rede} cairam {qtd_antes:,} -> {qtd_agora:,} "
                f"({perda:.1f}%, limite {tolerancia_rede_pct:.0f}%) -- coleta parcial? pins sumiriam do mapa"
            )

    n_antes, n_agora = len(publicado), len(rascunho)
    if n_antes >= min_unidades_total:
        queda_total = 100.0 * (n_antes - n_agora) / n_antes
        if queda_total > tolerancia_total_pct:
            motivos.append(
                f"concorrentes DESENHAVEIS cairam no total {n_antes:,} -> {n_agora:,} "
                f"({queda_total:.1f}%, limite {tolerancia_total_pct:.0f}%) -- coleta parcial? pins sumiriam do mapa"
            )
    return motivos
