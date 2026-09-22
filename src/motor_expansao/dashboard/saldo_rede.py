"""Saldo semanal de unidades POR REDE, a partir do histórico de contagem do coletor.

É o número que o Telegram já mostra toda semana ("a Selfit tinha 231, agora tem 231") e que a tela
de movimentação concorrencial não tinha: lá o saldo vinha de um pacote estático, tirado à mão uma
vez. O insumo existe desde 2026-06-29 e é anexado a cada lote de domingo por
`relatorio_crescimento.py` (VPS, `/opt/gymscraping-infra/historico_contagem.csv`).

**A semântica do saldo é a que já existe, não uma nova.** O relatório do coletor compara a execução
corrente com a ANTERIOR (`contagem_anterior.csv`) e chama de `novo` a rede sem contagem prévia.
Este módulo preserva as duas coisas: comparar execuções (não "domingos") e distinguir *novo* de
*delta*. Inventar aqui uma terceira semântica faria a tela e o chat de ops discordarem sobre o mesmo
fato — e quem olha os dois é a mesma pessoa.

QUATRO PROPRIEDADES DO INSUMO, TODAS MEDIDAS EM 2026-09-22, que o código honra:

1. **O universo CRESCE.** 90 redes em 2026-06-29, 107 em 2026-09-20 — **17** entraram depois de
   19/07. Rede ausente na execução de origem é `novo`, nunca `delta = +n`: tratá-la como ganho
   inventaria crescimento de mercado onde houve ampliação de COBERTURA do coletor.
2. **Nem toda execução é domingo.** `2026-07-22` é uma quarta-feira. Por isso a unidade é a
   EXECUÇÃO, e restringir a domingos é opção de quem chama (`so_domingos=True`), não premissa
   embutida.
3. **Defasagem de `data_coleta` é o estado NORMAL de parte das redes** — 154 linhas (10,8%) já
   nascem com data anterior à execução, desde a primeira safra. Logo, data velha **não reprova
   nada sozinha**: ela é AGRAVANTE da régua percentual e sinal de diagnóstico. A primeira versão
   deste módulo ia usá-la como gatilho, e teria reprovado ~11% de toda semana.
4. **`data_coleta` pode vir VAZIA** (12 linhas): é coletor que não devolveu nada, estado diferente
   de "coletado hoje" e diferente de "coletado há meses".

GUARDRAILS: READ-ONLY sobre o M1 — nada aqui toca `score_priorizacao`, pesos, carteira, plano ou
artefato oficial. CSV do projeto: `sep=";"`. O arquivo da VPS chega com CRLF, e isso não é detalhe:
foi o `\\r` no último campo que fez a primeira medição desta análise contar 1.428 de 1.428 linhas
como defasadas, quando são 154.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Tolerâncias REUSADAS do contrato da camada de vulnerabilidade `[DEC-061]`, nunca replicadas: é a
# mesma pergunta ("esta coleta veio quebrada?") sobre o mesmo universo de redes, e duas cópias do
# número divergiriam na primeira revisão de limiar.
from motor_expansao.vulnerabilidade.contrato import (
    MIN_UNIDADES_GUARDA_REDE,
    MIN_UNIDADES_GUARDA_TOTAL,
    TOLERANCIA_QUEDA_REDE_PCT,
    TOLERANCIA_QUEDA_TOTAL_PCT,
)

#: Contrato do histórico como o coletor o escreve (`relatorio_crescimento.py`).
CONTRATO_COLUNAS_HISTORICO: dict[str, str] = {
    "data_execucao": "string",  # ISO; o DIA do lote, não da raspagem
    "rede": "string",
    "unidades": "int64",
    "data_coleta": "string",  # ISO da 1a linha do CSV da rede; "" quando o coletor nao devolveu
}

#: Estados possíveis de uma rede no saldo entre duas execuções.
STATUS_SALDO_VALIDOS: tuple[str, ...] = ("novo", "sumiu", "variou", "estavel")


def ler_historico_contagem(caminho: Path) -> pd.DataFrame:
    """CSV do coletor -> frame LONGO tipado, uma linha por `(data_execucao, rede)`.

    Faz `strip` em todas as colunas de texto por causa do CRLF (ver o topo do módulo). Duplicata de
    `(data_execucao, rede)` LEVANTA: o histórico é append-only e uma execução repetida significa que
    o lote rodou duas vezes no mesmo dia — somar ou escolher uma delas em silêncio produziria saldo
    falso para aquela semana inteira.
    """
    # `utf-8-sig`, nunca `utf-8` puro: é o padrão de CSV do projeto (CLAUDE.md §2) e o que os
    # módulos irmãos que leem feed de coletor já aplicam (`snapshots.py`, `curadoria_agregadores.py`).
    # Com BOM e `utf-8` puro, o header sai como `﻿data_execucao`, a coluna "não existe" e o
    # erro acusa o CONTRATO — apontando para o lugar errado, longe da causa. Achado da revisão
    # automática no PR #393.
    bruto = pd.read_csv(caminho, sep=";", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    faltando = [c for c in CONTRATO_COLUNAS_HISTORICO if c not in bruto.columns]
    if faltando:
        raise ValueError(f"historico de contagem fora do contrato; colunas ausentes: {faltando}")

    out = pd.DataFrame(
        {
            "data_execucao": bruto["data_execucao"].astype(str).str.strip(),
            "rede": bruto["rede"].astype(str).str.strip(),
            "unidades": pd.to_numeric(
                bruto["unidades"].astype(str).str.strip(), errors="coerce"
            ).fillna(0),
            "data_coleta": bruto["data_coleta"].astype(str).str.strip(),
        }
    )
    out["unidades"] = out["unidades"].astype("int64")
    for coluna in ("data_execucao", "rede", "data_coleta"):
        out[coluna] = out[coluna].astype("string")

    dup = int(out.duplicated(subset=["data_execucao", "rede"]).sum())
    if dup:
        raise ValueError(f"historico com (data_execucao, rede) duplicado: {dup} linha(s)")
    return out.sort_values(["data_execucao", "rede"], kind="mergesort").reset_index(drop=True)


def execucoes(historico: pd.DataFrame, *, so_domingos: bool = False) -> list[str]:
    """Datas de execução, em ordem cronológica.

    `so_domingos=True` filtra o que de fato é o lote semanal — existe porque a série tem execuções
    fora da cadência (`2026-07-22` é quarta), e comparar uma delas com um domingo mede um intervalo
    diferente do resto. Não é o default: descartar dado por conveniência de cadência esconderia
    justamente a execução manual que alguém rodou para conferir alguma coisa.
    """
    datas = sorted({str(d) for d in historico["data_execucao"]})
    if not so_domingos:
        return datas
    return [d for d in datas if pd.Timestamp(d).dayofweek == 6]


def pivot_contagem(historico: pd.DataFrame) -> pd.DataFrame:
    """Frame LARGO: uma linha por rede, uma coluna por execução, valores em unidades.

    Célula **nula** (`Int64`) quer dizer "esta rede não estava no universo daquela execução" — e não
    zero. A distinção é o ponto: zero é rede mapeada cujo coletor voltou vazio; nulo é rede que
    ainda não existia na cobertura. Preencher com zero faria as 17 redes que entraram depois de
    julho aparecerem como se tivessem fechado todas as unidades e reaberto.
    """
    largo = historico.pivot(index="rede", columns="data_execucao", values="unidades")
    largo = largo.astype("Int64")
    largo.columns = [str(c) for c in largo.columns]
    largo.columns.name = None
    return largo.sort_index()


def saldo_entre_execucoes(historico: pd.DataFrame, *, de: str, ate: str) -> pd.DataFrame:
    """Saldo por rede entre duas execuções: `rede, antes, agora, delta, status, data_coleta`.

    `status` segue o vocabulário de `STATUS_SALDO_VALIDOS`:

    | status | quando | `delta` |
    |---|---|---|
    | `novo` | a rede não existia na execução `de` | `<NA>` |
    | `sumiu` | existia em `de` e não está em `ate` | `<NA>` |
    | `variou` | existe nas duas e a contagem mudou | assinado |
    | `estavel` | existe nas duas e não mudou | `0` |

    `novo` e `sumiu` têm `delta` NULO de propósito, e não `+n`/`-n`: os dois são mudança de
    COBERTURA do coletor, não movimento de mercado. Somar o `delta` desta coluna responde "quantas
    unidades a mais existem entre as redes comparáveis", que é a pergunta do saldo; incluir os dois
    responderia outra, misturada.
    """
    for rotulo, valor in (("de", de), ("ate", ate)):
        if valor not in set(historico["data_execucao"].astype(str)):
            raise ValueError(f"execucao `{rotulo}`={valor} nao existe no historico")

    antes = historico[historico["data_execucao"].astype(str) == de].set_index("rede")
    agora = historico[historico["data_execucao"].astype(str) == ate].set_index("rede")

    linhas: list[dict[str, object]] = []
    for rede in sorted(set(antes.index) | set(agora.index)):
        tem_antes = rede in antes.index
        tem_agora = rede in agora.index
        n_antes = int(antes.loc[rede, "unidades"]) if tem_antes else None
        n_agora = int(agora.loc[rede, "unidades"]) if tem_agora else None
        coleta = str(agora.loc[rede, "data_coleta"]) if tem_agora else ""

        if not tem_antes:
            status, delta = "novo", None
        elif not tem_agora:
            status, delta = "sumiu", None
        else:
            delta = int(n_agora) - int(n_antes)  # type: ignore[arg-type]
            status = "estavel" if delta == 0 else "variou"

        linhas.append(
            {
                "rede": str(rede),
                "antes": n_antes,
                "agora": n_agora,
                "delta": delta,
                "status": status,
                "data_coleta": coleta,
            }
        )

    out = pd.DataFrame(
        linhas, columns=["rede", "antes", "agora", "delta", "status", "data_coleta"]
    )
    for coluna in ("antes", "agora", "delta"):
        out[coluna] = out[coluna].astype("Int64")
    out["rede"] = out["rede"].astype("string")
    out["status"] = out["status"].astype("string")
    out["data_coleta"] = out["data_coleta"].astype("string")
    return out.reset_index(drop=True)


def avaliar_queda_da_execucao(
    historico: pd.DataFrame,
    *,
    execucao: str,
    referencia: str | None = None,
    tolerancia_rede_pct: float = TOLERANCIA_QUEDA_REDE_PCT,
    tolerancia_total_pct: float = TOLERANCIA_QUEDA_TOTAL_PCT,
) -> dict[str, object]:
    """Esta execução veio de uma coleta COMPLETA? Mesma régua da guarda do snapshot `[DEC-061]`.

    **Por REDE, não no total**, e isso saiu de medição no mesmo incidente: em 2026-09-13 o lote
    morreu no coletor #28 de 90, a Selfit caiu de 231 para 119 (**-48,5%**) e o TOTAL mal se moveu,
    porque as outras 106 redes ficaram com a contagem anterior. Um limiar de total capaz de pegar
    aquele domingo reprovaria também o fechamento real de uma unidade numa rede pequena.

    **`data_coleta` defasada é AGRAVANTE, nunca gatilho.** Medido: 154 das 1.428 linhas (10,8%) já
    nascem com data anterior à execução, desde a primeira safra — usá-la como critério reprovaria
    ~11% de toda semana. Ela entra no laudo como `redes_defasadas`, para quem lê o motivo entender
    *por que* a rede caiu, e é o que separa "o coletor não rodou" de "a rede fechou unidades".

    `referencia=None` usa a execução imediatamente anterior. Execução mais antiga da série não tem
    com o que comparar e **passa**: a guarda mede queda, não tamanho.
    """
    datas = execucoes(historico)
    if execucao not in datas:
        raise ValueError(f"execucao {execucao} nao existe no historico")
    if referencia is None:
        anteriores = [d for d in datas if d < execucao]
        referencia = anteriores[-1] if anteriores else None

    if referencia is None:
        return {
            "aprovado": True,
            "execucao": execucao,
            "referencia": None,
            "motivos": [],
            "redes_que_desabaram": [],
            "redes_defasadas": [],
            "queda_total_pct": None,
        }

    saldo = saldo_entre_execucoes(historico, de=referencia, ate=execucao)
    comparaveis = saldo[saldo["status"].isin(["variou", "estavel"])]

    desabaram: list[dict[str, object]] = []
    for linha in comparaveis.to_dict("records"):
        n_antes = int(linha["antes"])  # type: ignore[arg-type]
        n_agora = int(linha["agora"])  # type: ignore[arg-type]
        if n_antes < MIN_UNIDADES_GUARDA_REDE:
            continue
        perda = 100.0 * (n_antes - n_agora) / n_antes
        if perda > tolerancia_rede_pct:
            desabaram.append(
                {
                    "rede": str(linha["rede"]),
                    "antes": n_antes,
                    "agora": n_agora,
                    "queda_pct": round(perda, 1),
                    # O agravante: coleta MAIS VELHA que a execucao de referencia e' a assinatura
                    # do baseline do repositorio reaparecendo, nao de unidades fechando.
                    "coleta_defasada": bool(
                        str(linha["data_coleta"]) and str(linha["data_coleta"]) < referencia
                    ),
                }
            )

    total_antes = int(comparaveis["antes"].sum()) if len(comparaveis) else 0
    total_agora = int(comparaveis["agora"].sum()) if len(comparaveis) else 0
    queda_total = 100.0 * (total_antes - total_agora) / total_antes if total_antes else 0.0

    defasadas = sorted(
        str(linha["rede"])
        for linha in saldo.to_dict("records")
        if str(linha["data_coleta"]) and str(linha["data_coleta"]) < execucao
    )

    motivos: list[str] = []
    for d in desabaram:
        agravante = " e com coleta DEFASADA (baseline do repositorio?)" if d["coleta_defasada"] else ""
        motivos.append(
            f"rede {d['rede']} caiu {d['antes']} -> {d['agora']} ({d['queda_pct']:.1f}%) "
            f"contra {referencia}{agravante}"
        )
    if total_antes >= MIN_UNIDADES_GUARDA_TOTAL and queda_total > tolerancia_total_pct:
        motivos.append(
            f"total caiu {total_antes} -> {total_agora} ({queda_total:.1f}%) contra {referencia}, "
            f"acima do limite de {tolerancia_total_pct:.0f}%"
        )

    return {
        "aprovado": not motivos,
        "execucao": execucao,
        "referencia": referencia,
        "motivos": motivos,
        "redes_que_desabaram": desabaram,
        "redes_defasadas": defasadas,
        "queda_total_pct": round(queda_total, 2),
    }


__all__ = [
    "CONTRATO_COLUNAS_HISTORICO",
    "STATUS_SALDO_VALIDOS",
    "ler_historico_contagem",
    "execucoes",
    "pivot_contagem",
    "saldo_entre_execucoes",
    "avaliar_queda_da_execucao",
]
