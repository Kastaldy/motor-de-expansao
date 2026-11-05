"""Saldo semanal de unidades POR REDE, a partir do histórico de contagem do coletor.

É o número que o Telegram já mostra toda semana ("a Selfit tinha 231, agora tem 231"). Até 2026-11
a tela de movimentação concorrencial não o lia: as unidades do card "Crescimento da concorrência"
vinham de um pacote estático, tirado à mão uma vez, e ficaram paradas em 06/09. Desde então o card
lê `contagem_da_tela`. O insumo existe desde 2026-06-29 e é anexado a cada lote de domingo por
`relatorio_crescimento.py` (VPS, `/opt/gymscraping-infra/historico_contagem.csv`); o passo 2.1 do
mesmo lote o copia para o staging do motor (`ARQUIVO_STAGING`).

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

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

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

#: Nome do histórico no staging do motor. O passo 2.1 do lote de domingo (`run_weekly_90.sh`) o copia
#: de `/opt/gymscraping-infra/historico_contagem.csv` logo depois de o relatório anexar a semana.
ARQUIVO_STAGING = "historico_contagem.csv"

#: Os três jeitos de uma execução entrar na série que a tela lê (ver `avaliar_serie`).
COMO_ACEITA: tuple[str, ...] = ("primeira", "aprovada", "confirmada")

#: `data_execucao` válida. Linha sem ela é arquivo cortado no meio da cópia ou linha suja.
_DATA_ISO = r"\d{4}-\d{2}-\d{2}"


def ler_historico_contagem(caminho: Path) -> pd.DataFrame:
    """CSV do coletor -> frame LONGO tipado, uma linha por `(data_execucao, rede)`.

    Faz `strip` em todas as colunas de texto por causa do CRLF (ver o topo do módulo). Duplicata de
    `(data_execucao, rede)` LEVANTA: o histórico é append-only e uma execução repetida significa que
    o lote rodou duas vezes no mesmo dia — somar ou escolher uma delas em silêncio produziria saldo
    falso para aquela semana inteira. Quem precisa MOSTRAR a contagem lê por
    `ler_historico_tolerante`.
    """
    out = _ler_e_tipar(caminho)
    dup = int(out.duplicated(subset=["data_execucao", "rede"]).sum())
    if dup:
        raise ValueError(f"historico com (data_execucao, rede) duplicado: {dup} linha(s)")
    return out.sort_values(["data_execucao", "rede"], kind="mergesort").reset_index(drop=True)


def ler_historico_tolerante(caminho: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """A leitura de quem MOSTRA a contagem: um dia ruim sai da série, o arquivo não cai inteiro.

    `ler_historico_contagem` levanta em `(data_execucao, rede)` repetido, e com razão. Para a TELA,
    porém, levantar devolveria o card inteiro ao pacote de setembro por causa de um único domingo.
    Aqui a execução repetida sai INTEIRA (todas as redes daquele dia; nunca uma das cópias
    escolhida) e volta nomeada em `execucoes_duplicadas`, para a tela dizer que ela ficou de fora.
    Linha sem `data_execucao` ISO também sai, e é contada em `linhas_sem_data`.
    """
    out = _ler_e_tipar(caminho)
    com_data = out["data_execucao"].astype(str).str.fullmatch(_DATA_ISO).astype(bool)
    n_sem_data = int((~com_data).sum())
    out = out[com_data.to_numpy(dtype=bool)]
    repetidas = out.loc[out.duplicated(subset=["data_execucao", "rede"], keep=False), "data_execucao"]
    duplicadas = sorted({str(d) for d in repetidas})
    if duplicadas:
        out = out[~out["data_execucao"].astype(str).isin(duplicadas).to_numpy(dtype=bool)]
    out = out.sort_values(["data_execucao", "rede"], kind="mergesort").reset_index(drop=True)
    return out, {"execucoes_duplicadas": duplicadas, "linhas_sem_data": n_sem_data}


def _ler_e_tipar(caminho: Path) -> pd.DataFrame:
    """CSV do coletor -> frame LONGO tipado, SEM julgar duplicata (cada leitor decide o que fazer)."""
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
    return out


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
            "queda_total_reprovou": False,
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
    total_reprovou = total_antes >= MIN_UNIDADES_GUARDA_TOTAL and queda_total > tolerancia_total_pct
    if total_reprovou:
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
        # O total reprovou POR SI (e não só pelas redes): a tela diz "o total caiu", não "a rede X".
        "queda_total_reprovou": bool(total_reprovou),
    }


def avaliar_serie(
    historico: pd.DataFrame,
    *,
    tolerancia_rede_pct: float = TOLERANCIA_QUEDA_REDE_PCT,
    tolerancia_total_pct: float = TOLERANCIA_QUEDA_TOTAL_PCT,
) -> list[dict[str, object]]:
    """Laudo de CADA execução, em ordem, julgada contra a última ACEITA — nunca só contra a vizinha.

    Comparar com a imediatamente anterior (o default de `avaliar_queda_da_execucao`) produz o
    REBOTE: em 2026-09-13 a Selfit caiu de 231 para 119 pelo crash do lote, e em 2026-09-20 voltou
    a 231. Contra 13/09, o dia 20 leria +112 unidades que ninguém abriu; contra a última aceita
    (06/09), lê 0, que é o fato.

    Uma execução é aceita de três jeitos (`como`, vocabulário de `COMO_ACEITA`):

    - `primeira`: a mais antiga da série. Não tem com o que comparar, e a guarda mede queda, não
      tamanho;
    - `aprovada`: passa na guarda contra a última aceita;
    - `confirmada`: reprovada contra a última aceita, mas COERENTE com a execução imediatamente
      anterior (passa na guarda contra ela), que também tinha sido reprovada. É a queda que se repetiu em duas contagens seguidas, e aí
      ela deixa de ser coleta quebrada para virar fato. Sem essa saída a régua CONGELARIA a série:
      uma rede de 6 unidades que fecha 2 (-33%) seria reprovada contra a mesma contagem velha em
      toda semana seguinte, para sempre.

    O preço da confirmação fica declarado: duas coletas quebradas IGUAIS, em domingos seguidos,
    passam na segunda. Desde o BLK-COLETA-01 o coletor que falha volta à safra anterior, e não ao
    baseline do repositório, então o tombo de 13/09 não se repete desse jeito; e a tela nomeia toda
    queda que aceitou por confirmação. Recusada fica com `como = "recusada"`.
    """
    laudos: list[dict[str, object]] = []
    referencia: str | None = None
    for data in execucoes(historico):
        if referencia is None:
            laudo: dict[str, object] = {
                "execucao": data,
                "aceita": True,
                "como": "primeira",
                "referencia": None,
                "motivos": [],
                "redes_que_desabaram": [],
                "queda_total_pct": None,
                "queda_total_reprovou": False,
            }
        else:
            contra_ultima = avaliar_queda_da_execucao(
                historico,
                execucao=data,
                referencia=referencia,
                tolerancia_rede_pct=tolerancia_rede_pct,
                tolerancia_total_pct=tolerancia_total_pct,
            )
            como = "aprovada" if contra_ultima["aprovado"] else "recusada"
            if como == "recusada" and laudos and not laudos[-1]["aceita"]:
                contra_vizinha = avaliar_queda_da_execucao(
                    historico,
                    execucao=data,
                    referencia=str(laudos[-1]["execucao"]),
                    tolerancia_rede_pct=tolerancia_rede_pct,
                    tolerancia_total_pct=tolerancia_total_pct,
                )
                if contra_vizinha["aprovado"]:
                    como = "confirmada"
            laudo = {
                "execucao": data,
                "aceita": como != "recusada",
                "como": como,
                "referencia": referencia,
                "motivos": contra_ultima["motivos"],
                "redes_que_desabaram": contra_ultima["redes_que_desabaram"],
                "queda_total_pct": contra_ultima["queda_total_pct"],
                "queda_total_reprovou": contra_ultima["queda_total_reprovou"],
            }
        laudos.append(laudo)
        if laudo["aceita"]:
            referencia = data
    return laudos


def _quedas(laudo: Mapping[str, object] | None) -> list[dict[str, object]]:
    """As redes que caíram num laudo, só com o que a tela escreve (quem, de quanto, para quanto)."""
    if not laudo:
        return []
    desabaram = cast(list[dict[str, Any]], laudo.get("redes_que_desabaram") or [])
    return [
        {
            "rede": str(d["rede"]),
            "antes": int(d["antes"]),
            "agora": int(d["agora"]),
            "coleta_defasada": bool(d["coleta_defasada"]),
        }
        for d in desabaram
    ]


def contagem_da_tela(
    historico: pd.DataFrame,
    *,
    execucoes_duplicadas: Sequence[str] = (),
    excluir: Iterable[str] = (),
) -> dict[str, object]:
    """O que o card "Crescimento da concorrência" mostra: a última contagem ACEITA (`avaliar_serie`)
    e a variação por rede contra a aceita anterior (`saldo_entre_execucoes`, mesma semântica do
    Telegram: `novo` e `sumiu` são cobertura do coletor, nunca `+n`/`-n`).

    `excluir` tira as redes ANTES da guarda, não só da exibição: a guarda olha as redes que a tela
    mostra. Sem isso, o tombo de um estúdio boutique (que o card não exibe, DEC-056) seguraria a
    contagem de todas as outras redes numa semana velha.

    `recusadas` lista o que ficou de fora DEPOIS da aceita anterior. As que caem entre as duas
    aceitas explicam por que a variação cobre mais de uma semana; as que vêm depois da última aceita
    explicam por que o card não está na execução mais recente. Cada uma traz as redes que caíram,
    para a tela dizer quem e quanto. `execucoes_duplicadas` vêm de `ler_historico_tolerante` e entram
    nessa lista com `motivo = "duplicada"`.
    """
    fora = {str(r).lower() for r in excluir}
    if fora:
        historico = historico[~historico["rede"].astype(str).str.lower().isin(fora).to_numpy(dtype=bool)]
    laudos = avaliar_serie(historico)
    aceitas = [laudo for laudo in laudos if laudo["aceita"]]
    datas = [str(laudo["execucao"]) for laudo in laudos] + [str(d) for d in execucoes_duplicadas]
    atual = aceitas[-1] if aceitas else None
    anterior = aceitas[-2] if len(aceitas) >= 2 else None
    data = str(atual["execucao"]) if atual else None
    data_anterior = str(anterior["execucao"]) if anterior else None
    piso = data_anterior or ""

    recusadas: list[dict[str, object]] = [
        {
            "execucao": str(laudo["execucao"]),
            "motivo": "queda",
            "redes": _quedas(laudo),
            "queda_total_pct": laudo["queda_total_pct"] if laudo["queda_total_reprovou"] else None,
        }
        for laudo in laudos
        if not laudo["aceita"] and str(laudo["execucao"]) > piso
    ]
    recusadas += [
        {"execucao": str(d), "motivo": "duplicada", "redes": [], "queda_total_pct": None}
        for d in execucoes_duplicadas
        if str(d) > piso
    ]
    recusadas.sort(key=lambda r: str(r["execucao"]))

    unidades: dict[str, int] = {}
    variacao: dict[str, dict[str, object]] = {}
    if data is not None:
        foto = historico[historico["data_execucao"].astype(str) == data]
        unidades = {str(r): int(n) for r, n in zip(foto["rede"], foto["unidades"], strict=True)}
        if data_anterior is not None:
            saldo = saldo_entre_execucoes(historico, de=data_anterior, ate=data)
            variacao = {
                str(linha["rede"]): {
                    "delta": None if pd.isna(linha["delta"]) else int(linha["delta"]),
                    "status": str(linha["status"]),
                }
                for linha in saldo.to_dict("records")
            }
    confirmada = bool(atual is not None and atual["como"] == "confirmada")
    return {
        "data": data,
        "data_anterior": data_anterior,
        "execucao_mais_recente": max(datas) if datas else None,
        "unidades": unidades,
        "variacao": variacao,
        "confirmada": confirmada,
        "quedas_confirmadas": _quedas(atual) if confirmada else [],
        "queda_total_confirmada_pct": (
            atual["queda_total_pct"] if confirmada and atual is not None and atual["queda_total_reprovou"] else None
        ),
        "recusadas": recusadas,
    }


__all__ = [
    "ARQUIVO_STAGING",
    "COMO_ACEITA",
    "CONTRATO_COLUNAS_HISTORICO",
    "STATUS_SALDO_VALIDOS",
    "ler_historico_contagem",
    "ler_historico_tolerante",
    "execucoes",
    "pivot_contagem",
    "saldo_entre_execucoes",
    "avaliar_queda_da_execucao",
    "avaliar_serie",
    "contagem_da_tela",
]
