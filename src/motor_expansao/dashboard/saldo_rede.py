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
fato — e quem olha os dois é a mesma pessoa. As exceções são as leituras em que o card segura a
última contagem boa da rede e diz isso, enquanto o Telegram mostra o número cru (decisão do
Vinicius, 05/11/2026; ver `acompanhar_redes`): rede sem coleta nova, rede ausente, salto brusco
ainda não confirmado e execução recusada pela queda difusa do total. A primeira acontece toda
semana (~10,8% das linhas), as outras em semana de coleta quebrada.

QUATRO PROPRIEDADES DO INSUMO, TODAS MEDIDAS EM 2026-09-22, que o código honra:

1. **O universo CRESCE.** 90 redes em 2026-06-29, 107 em 2026-09-20 — **17** entraram depois de
   19/07. Rede ausente na execução de origem é `novo`, nunca `delta = +n`: tratá-la como ganho
   inventaria crescimento de mercado onde houve ampliação de COBERTURA do coletor.
2. **Nem toda execução é domingo.** `2026-07-22` é uma quarta-feira. Por isso a unidade é a
   EXECUÇÃO, e restringir a domingos é opção de quem chama (`so_domingos=True`), não premissa
   embutida.
3. **Defasagem de `data_coleta` é o estado NORMAL de parte das redes** — 154 linhas (10,8%) já
   nascem com data anterior à execução, desde a primeira safra. Logo, data velha **não reprova
   a execução sozinha**: na guarda da DEC-061 (`avaliar_queda_da_execucao`) ela é AGRAVANTE da
   régua percentual e sinal de diagnóstico; a primeira versão deste módulo ia usá-la como
   gatilho, e teria reprovado ~11% de toda semana. No card ela diz outra coisa, sobre UMA rede:
   se a data não avançou, a rede não foi recoletada e fica com a última contagem boa
   (`acompanhar_redes`), sem prender as outras.
4. **`data_coleta` pode vir VAZIA** (12 linhas): é coletor que não devolveu nada, estado diferente
   de "coletado hoje" e diferente de "coletado há meses".

GUARDRAILS: READ-ONLY sobre o M1 — nada aqui toca `score_priorizacao`, pesos, carteira, plano ou
artefato oficial. CSV do projeto: `sep=";"`. O arquivo da VPS chega com CRLF, e isso não é detalhe:
foi o `\\r` no último campo que fez a primeira medição desta análise contar 1.428 de 1.428 linhas
como defasadas, quando são 154.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

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

#: Situação da leitura de UMA rede numa execução (`acompanhar_redes`). `estreia`, `aceita` e
#: `confirmada` mudam o número que o card mostra; `segurada`, `nao_recoletada` e `ausente` seguram
#: a última contagem boa da rede; `removida` tira a rede da contagem.
SITUACOES_LEITURA: tuple[str, ...] = (
    "estreia",
    "aceita",
    "confirmada",
    "segurada",
    "nao_recoletada",
    "ausente",
    "removida",
)

#: Estado da variação de uma rede no card: o vocabulário do Telegram (`STATUS_SALDO_VALIDOS`) mais
#: os estados próprios do card: `confirmada` (salto que se manteve e entrou) e os três em que ele
#: segura a última contagem boa. A tela tem um ramo para cada um
#: (`tests/unit/test_paridade_crescimento_concorrencia_web.py`).
STATUS_VARIACAO_TELA: tuple[str, ...] = (
    *STATUS_SALDO_VALIDOS,
    "confirmada",
    "segurada",
    "nao_recoletada",
    "ausente",
)

#: Sentido do salto brusco de uma rede (`_salto_brusco`).
DIRECOES_SALTO: tuple[str, ...] = ("queda", "subida")

#: Por que uma execução INTEIRA ficou fora do card (`contagem_da_tela`).
MOTIVOS_RECUSA: tuple[str, ...] = ("total", "duplicada")

#: `data_execucao` válida. Linha sem ela é arquivo cortado no meio da cópia ou linha suja.
_DATA_ISO = r"\d{4}-\d{2}-\d{2}"

#: Situações em que a rede foi RECOLETADA nesta execução (a `data_coleta` avançou). Execução sem
#: nenhuma delas não traz contagem nova e não vira a foto da tela (`contagem_da_tela`).
_SITUACOES_COM_COLETA: tuple[str, ...] = ("estreia", "aceita", "confirmada", "segurada")


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
    Linha fora do formato também sai e é contada em `linhas_sem_data`: sem `data_execucao` ISO
    (arquivo cortado no meio da cópia) ou com campos a mais, que derrubaria a leitura inteira.
    """
    ruins: list[list[str]] = []
    out = _ler_e_tipar(caminho, ruins=ruins)
    com_data = out["data_execucao"].astype(str).str.fullmatch(_DATA_ISO).astype(bool)
    n_sem_data = int((~com_data).sum()) + len(ruins)
    out = out[com_data.to_numpy(dtype=bool)]
    repetidas = out.loc[out.duplicated(subset=["data_execucao", "rede"], keep=False), "data_execucao"]
    duplicadas = sorted({str(d) for d in repetidas})
    if duplicadas:
        out = out[~out["data_execucao"].astype(str).isin(duplicadas).to_numpy(dtype=bool)]
    out = out.sort_values(["data_execucao", "rede"], kind="mergesort").reset_index(drop=True)
    return out, {"execucoes_duplicadas": duplicadas, "linhas_sem_data": n_sem_data}


def _ler_e_tipar(caminho: Path, *, ruins: list[list[str]] | None = None) -> pd.DataFrame:
    """CSV do coletor -> frame LONGO tipado, SEM julgar duplicata (cada leitor decide o que fazer).

    Com `ruins`, a linha com campos a mais é pulada e guardada ali, em vez de derrubar o arquivo.
    """
    # `utf-8-sig`, nunca `utf-8` puro: é o padrão de CSV do projeto (CLAUDE.md §2) e o que os
    # módulos irmãos que leem feed de coletor já aplicam (`snapshots.py`, `curadoria_agregadores.py`).
    # Com BOM e `utf-8` puro, o header sai como `﻿data_execucao`, a coluna "não existe" e o
    # erro acusa o CONTRATO — apontando para o lugar errado, longe da causa. Achado da revisão
    # automática no PR #393.
    if ruins is None:
        bruto = pd.read_csv(caminho, sep=";", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    else:
        # O descarte linha a linha só existe no motor `python`; o arquivo tem milhares de linhas,
        # então o custo não pesa.
        bruto = pd.read_csv(
            caminho,
            sep=";",
            dtype=str,
            keep_default_na=False,
            encoding="utf-8-sig",
            engine="python",
            on_bad_lines=ruins.append,
        )
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

    Laudo de DIAGNÓSTICO, sem consumidor no card: a tela julga cada rede em `acompanhar_redes`, e lá
    a rede ausente fica FORA da soma do total (fica uma execução com a última contagem e depois
    sai, com aviso). Aqui ela conta como zero, como na DEC-061.

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
    # Rede presente na referência e AUSENTE na execução conta como ZERO, como na guarda do
    # snapshot (`snapshots.py`, `c_agora.get(rede, 0)`): perder a rede inteira é o caso extremo de
    # coleta parcial. Até 2026-11 ela ficava fora (`sumiu`), e uma execução com metade das redes
    # passava. `novo` segue fora: sem referência, não há queda a medir.
    comparaveis = saldo[saldo["status"].isin(["variou", "estavel", "sumiu"])].copy()
    comparaveis["agora"] = comparaveis["agora"].fillna(0)

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


def _salto_brusco(antes: int, agora: int, tolerancia_pct: float) -> str | None:
    """`"queda"`, `"subida"` ou `None`: a régua por rede da DEC-061, nos DOIS sentidos.

    A DEC-061 só barra queda porque a série dela alimenta sinais de churn. No card, um salto para
    CIMA é o mesmo defeito com o sinal trocado: conserto de paginação, coletor que passa a pegar
    outra região, unidade duplicada. Sem a régua de subida, o número inflado entraria como
    crescimento e a correção dele, na semana seguinte, seria recusada como "coleta incompleta".
    Abaixo de `MIN_UNIDADES_GUARDA_REDE` uma unidade já passa de 30%, então a rede pequena não
    tem salto.
    """
    if antes < MIN_UNIDADES_GUARDA_REDE:
        return None
    if 100.0 * (antes - agora) / antes > tolerancia_pct:
        return "queda"
    if 100.0 * (agora - antes) / antes > tolerancia_pct:
        return "subida"
    return None


def _julgar_leitura(
    aceita: Mapping[str, Any] | None,
    lida: tuple[int, str] | None,
    tolerancia_pct: float,
    data: str,
) -> dict[str, Any]:
    """A situação (`SITUACOES_LEITURA`) da leitura de UMA rede contra a última contagem boa dela."""
    if aceita is None:
        assert lida is not None
        return {"situacao": "estreia", "lido": lida[0], "coleta": lida[1]}
    if lida is None:
        return {"situacao": "removida" if aceita["ausente_desde"] else "ausente", "lido": None, "coleta": None}
    n, coleta = lida
    if coleta and not aceita["coleta"]:
        # A última contagem "boa" era o coletor vazio (sem data): não há base de comparação, e a
        # primeira leitura com dado é cobertura nova, não `+n`.
        return {"situacao": "estreia", "lido": n, "coleta": coleta}
    # `data_coleta` é o dia em que o coletor raspou o site (`date.today()` no GymScraping). Se ela
    # não avançou, a linha repete uma coleta velha: é a safra anterior que o lote devolve à rede
    # que falhou (BLK-COLETA-01), ou o baseline do repositório (o tombo de 13/09). Não é contagem
    # desta semana, e o card não a usa nem para confirmar nada. O piso também conta a coleta que
    # veio numa execução RECUSADA (`coleta_vista`): repeti-la não a transforma em coleta nova.
    piso = max(str(aceita["coleta"]), str(aceita.get("coleta_vista") or ""))
    if not (coleta and coleta > piso):
        return {"situacao": "nao_recoletada", "lido": n, "coleta": coleta}
    direcao = _salto_brusco(int(aceita["valor"]), n, tolerancia_pct)
    if direcao is None:
        return {"situacao": "aceita", "lido": n, "coleta": coleta}
    pendente = aceita["pendente"]
    if (
        pendente is not None
        and pendente["direcao"] == direcao
        and coleta > pendente["coleta"]
        and _salto_brusco(int(pendente["valor"]), n, tolerancia_pct) is None
    ):
        return {"situacao": "confirmada", "lido": n, "coleta": coleta, "direcao": direcao, "desde": pendente["desde"]}
    desde = pendente["desde"] if pendente is not None else data
    return {"situacao": "segurada", "lido": n, "coleta": coleta, "direcao": direcao, "desde": desde}


def _aplicar_leitura(estado: dict[str, dict[str, Any]], rede: str, julgada: Mapping[str, Any], data: str) -> None:
    situacao = julgada["situacao"]
    if situacao in ("estreia", "aceita", "confirmada"):
        estado[rede] = {
            "valor": int(julgada["lido"]),
            "coleta": julgada["coleta"],
            "data": data,
            "pendente": None,
            "ausente_desde": None,
        }
    elif situacao == "segurada":
        estado[rede]["pendente"] = {
            "valor": int(julgada["lido"]),
            "coleta": julgada["coleta"],
            "direcao": julgada["direcao"],
            "desde": julgada["desde"],
        }
        estado[rede]["ausente_desde"] = None
    elif situacao == "nao_recoletada":
        estado[rede]["ausente_desde"] = None
    elif situacao == "ausente":
        estado[rede]["ausente_desde"] = data
    elif situacao == "removida":
        del estado[rede]


def acompanhar_redes(
    historico: pd.DataFrame,
    *,
    tolerancia_rede_pct: float = TOLERANCIA_QUEDA_REDE_PCT,
    tolerancia_total_pct: float = TOLERANCIA_QUEDA_TOTAL_PCT,
) -> list[dict[str, Any]]:
    """O que o card mostra de cada rede depois de CADA execução: uma "foto" por execução.

    O julgamento é POR REDE, contra a última contagem BOA dela, e nunca contra a execução vizinha.
    Contra a vizinha nasce o REBOTE: em 2026-09-13 a Selfit caiu de 231 para 119 pelo crash do
    lote e voltou a 231 em 2026-09-20; contra 13/09, o dia 20 leria +112 unidades que ninguém
    abriu. E é por rede, e não a execução inteira, porque a falha real é de UMA rede ou de um
    punhado delas: julgar a semana inteira prenderia as outras 100 redes por causa de uma rede de
    6 unidades (medido na revisão de 05/11: com as 19 redes reais de 5 a 9 unidades, o card
    inteiro ficaria preso várias semanas por ano).

    Cada leitura recebe uma situação (`SITUACOES_LEITURA`):

    - `estreia`: rede que o coletor passou a contar. Entra (é cobertura, nunca `+n`);
    - `aceita`: coleta nova (`data_coleta` avançou) e sem salto brusco. Entra;
    - `nao_recoletada`: `data_coleta` não avançou. A rede fica na última contagem boa;
    - `segurada`: coleta nova com salto brusco (`_salto_brusco`, a régua da DEC-061 nos dois
      sentidos). A rede fica na última contagem boa;
    - `confirmada`: o salto se MANTEVE numa coleta mais nova que a da segurada (mesmo sentido, e
      sem novo salto contra ela). Entra. Uma reexecução do relatório sem recoletar repete a
      mesma `data_coleta` e não confirma nada;
    - `ausente`: a rede não veio nesta execução. Fica na última contagem boa por UMA execução;
    - `removida`: não veio duas vezes seguidas. Sai da contagem (cobertura).

    A guarda do TOTAL da DEC-061 (queda difusa acima de `tolerancia_total_pct`) segue valendo
    sobre as leituras `aceita`: se ela reprova, a execução INTEIRA fica de fora (`recusada`). A
    seguinte entra se voltar ao patamar (sem queda contra a última contagem boa) ou se, nas mesmas
    redes, repetir a soma da recusada dentro da mesma tolerância (`confirmou_total`). Repetir a
    MESMA coleta não confirma: a data de coleta da recusada vira o piso de cada rede
    (`coleta_vista`), e a rede que a repete (relatório rodado de novo, ou a safra que o passo 2.5
    devolve a quem falhou) fica `nao_recoletada`. A rede ausente fica fora dessa soma.

    `data_coleta` fora do ISO, ou depois da própria execução, conta como vazia: não avança a rede.
    Uma data futura escrita uma vez congelaria a rede para sempre, porque nada passaria dela.
    """
    por_execucao: dict[str, dict[str, tuple[int, str]]] = {}
    for data, rede, n, coleta in zip(
        historico["data_execucao"].astype(str),
        historico["rede"].astype(str),
        historico["unidades"].astype("int64"),
        historico["data_coleta"].astype(str),
        strict=True,
    ):
        dia = coleta[:10] if re.match(_DATA_ISO, coleta) else ""
        por_execucao.setdefault(data, {})[rede] = (int(n), dia if dia <= data else "")

    estado: dict[str, dict[str, Any]] = {}
    # A soma de cada rede na última execução recusada pelo total, para a seguinte confirmar.
    total_pendente: dict[str, int] | None = None
    fotos: list[dict[str, Any]] = []
    for data in sorted(por_execucao):
        lidas = por_execucao[data]
        julgadas = {
            rede: _julgar_leitura(estado.get(rede), lidas.get(rede), tolerancia_rede_pct, data)
            for rede in sorted(set(estado) | set(lidas))
        }
        coleta_nova = any(j["situacao"] in _SITUACOES_COM_COLETA for j in julgadas.values())
        base = {rede: int(j["lido"]) for rede, j in julgadas.items() if j["situacao"] == "aceita"}
        antes = sum(int(estado[rede]["valor"]) for rede in base)
        agora = sum(base.values())
        queda_total = 100.0 * (antes - agora) / antes if antes else 0.0
        reprova = antes >= MIN_UNIDADES_GUARDA_TOTAL and queda_total > tolerancia_total_pct
        confirmou_total = bool(
            reprova and total_pendente is not None and _total_confirma(total_pendente, base, tolerancia_total_pct)
        )
        if reprova and not confirmou_total:
            total_pendente = base
            for rede, julgada in julgadas.items():
                if rede in estado and julgada["situacao"] in _SITUACOES_COM_COLETA:
                    vista = str(estado[rede].get("coleta_vista") or "")
                    estado[rede]["coleta_vista"] = max(vista, str(julgada["coleta"]))
            fotos.append(
                {
                    "execucao": data,
                    "recusada": True,
                    "coleta_nova": coleta_nova,
                    "queda_total_pct": round(queda_total, 2),
                    "confirmou_total": False,
                    "valores": {rede: int(s["valor"]) for rede, s in estado.items()},
                    "redes": {},
                }
            )
            continue
        if antes >= MIN_UNIDADES_GUARDA_TOTAL:
            # Só a execução que a guarda chegou a JULGAR apaga a recusa pendente. A que não trouxe
            # coleta (base vazia) não aprovou nada: a recoleta seguinte ainda confirma contra ela.
            total_pendente = None
        for rede, julgada in julgadas.items():
            _aplicar_leitura(estado, rede, julgada, data)
        fotos.append(
            {
                "execucao": data,
                "recusada": False,
                "coleta_nova": coleta_nova,
                "queda_total_pct": round(queda_total, 2),
                "confirmou_total": confirmou_total,
                "valores": {rede: int(s["valor"]) for rede, s in estado.items()},
                "redes": julgadas,
            }
        )
    return fotos


def _total_confirma(pendente: Mapping[str, int], base: Mapping[str, int], tolerancia_pct: float) -> bool:
    """A queda do total se repetiu? Compara as MESMAS redes da recusada, e só com base que pese.

    Comparar a soma inteira com a da recusada misturaria redes diferentes: as que não foram
    recoletadas mudam de semana para semana.
    """
    comuns = [rede for rede in base if rede in pendente]
    antes = sum(int(pendente[rede]) for rede in comuns)
    if antes < MIN_UNIDADES_GUARDA_TOTAL:
        return False
    return _salto_brusco(antes, sum(int(base[rede]) for rede in comuns), tolerancia_pct) is None


def contagem_da_tela(
    historico: pd.DataFrame,
    *,
    execucoes_duplicadas: Sequence[str] = (),
    linhas_sem_data: int = 0,
    excluir: Iterable[str] = (),
) -> dict[str, Any]:
    """O que o card "Crescimento da concorrência" mostra: a foto da última execução que entrou
    (`acompanhar_redes`) e a variação por rede contra a foto da anterior.

    **A tela e o Telegram discordam onde o card segura a contagem, de propósito** (decisão do
    Vinicius, 05/11/2026): o relatório do coletor compara a execução com a anterior, crua; o card
    compara a contagem boa de cada rede com a contagem boa anterior, e diz o que segurou (rede
    sem coleta nova, ausente, com salto segurado ou confirmado; execução recusada). No resto os
    dois números coincidem, com a mesma semântica de `novo`.

    Execução sem NENHUMA coleta nova (todas as redes repetem a data: o relatório rodado de novo,
    ou um lote em que todos os coletores falharam) não vira a foto da tela. Ela sai em
    `sem_coleta_nova`, e o card segue na anterior em vez de trocar a data e esvaziar a variação.

    `excluir` tira as redes ANTES da guarda: a guarda olha só as redes que a tela mostra. Sem
    isso, um estúdio boutique (que o card não exibe, DEC-056) entraria na conta do total.

    Os avisos saem prontos para a tela: `recusadas` (execuções inteiras de fora, pelo total ou por
    duplicidade), `sem_coleta_nova`, `seguradas` e `confirmadas` (redes com salto brusco),
    `nao_recoletadas`, `ausentes` e `removidas`.
    """
    fora = {str(r).lower() for r in excluir}
    if fora:
        historico = historico[~historico["rede"].astype(str).str.lower().isin(fora).to_numpy(dtype=bool)]
    fotos = acompanhar_redes(historico)
    validas = [i for i, foto in enumerate(fotos) if not foto["recusada"] and foto["coleta_nova"]]
    i_atual = validas[-1] if validas else None
    i_anterior = validas[-2] if len(validas) >= 2 else None
    atual = fotos[i_atual] if i_atual is not None else None
    anterior = fotos[i_anterior] if i_anterior is not None else None
    data = str(atual["execucao"]) if atual else None
    data_anterior = str(anterior["execucao"]) if anterior else None
    piso = data_anterior or ""
    sem_coleta_nova = [
        str(foto["execucao"])
        for foto in fotos
        if not foto["recusada"] and not foto["coleta_nova"] and str(foto["execucao"]) > (data or "")
    ]

    recusadas: list[dict[str, Any]] = [
        {"execucao": str(foto["execucao"]), "motivo": "total", "queda_total_pct": foto["queda_total_pct"]}
        for foto in fotos
        if foto["recusada"] and str(foto["execucao"]) > piso
    ]
    recusadas += [
        {"execucao": str(d), "motivo": "duplicada", "queda_total_pct": None}
        for d in execucoes_duplicadas
        if str(d) > piso
    ]
    recusadas.sort(key=lambda r: str(r["execucao"]))

    unidades: dict[str, int] = dict(atual["valores"]) if atual else {}
    antes_por_rede: dict[str, int] = dict(anterior["valores"]) if anterior else {}
    variacao: dict[str, dict[str, Any]] = {}
    seguradas: list[dict[str, Any]] = []
    confirmadas: list[dict[str, Any]] = []
    nao_recoletadas: list[str] = []
    ausentes: list[str] = []
    removidas: list[str] = []
    for rede, julgada in (atual["redes"].items() if atual else []):
        situacao = julgada["situacao"]
        delta: int | None = None
        if situacao in ("aceita", "confirmada") and rede in antes_por_rede:
            delta = unidades[rede] - antes_por_rede[rede]
            status = "confirmada" if situacao == "confirmada" else ("estavel" if delta == 0 else "variou")
        elif situacao in ("estreia", "aceita", "confirmada"):
            status = "novo"
        elif situacao == "removida":
            status = "sumiu"
        else:
            status = situacao  # segurada, nao_recoletada, ausente
        variacao[rede] = {"delta": delta, "status": status}
        if situacao in ("segurada", "confirmada"):
            salto = {
                "rede": rede,
                "antes": unidades[rede] if situacao == "segurada" else antes_por_rede.get(rede),
                "agora": int(julgada["lido"]),
                "direcao": julgada["direcao"],
                "desde": julgada.get("desde"),
            }
            (seguradas if situacao == "segurada" else confirmadas).append(salto)
        elif situacao == "nao_recoletada":
            nao_recoletadas.append(rede)
        elif situacao == "ausente":
            ausentes.append(rede)
        elif situacao == "removida":
            removidas.append(rede)
    # Rede que saiu numa execução sem coleta nova, entre a foto anterior e a atual: ela não está na
    # foto atual, mas saiu da contagem e a tela precisa dizer.
    if atual is not None and i_anterior is not None and i_atual is not None:
        for foto in fotos[i_anterior + 1 : i_atual]:
            for rede, julgada in foto["redes"].items():
                if julgada["situacao"] == "removida" and rede not in atual["redes"]:
                    variacao[rede] = {"delta": None, "status": "sumiu"}
                    removidas.append(rede)

    def _maior_primeiro(saltos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(saltos, key=lambda s: (-int(s["antes"] or 0), str(s["rede"])))

    return {
        "data": data,
        "data_anterior": data_anterior,
        "execucao_mais_recente": max([str(f["execucao"]) for f in fotos] + [str(d) for d in execucoes_duplicadas], default=None),
        "linhas_sem_data": int(linhas_sem_data),
        "unidades": unidades,
        "variacao": variacao,
        "recusadas": recusadas,
        "sem_coleta_nova": sem_coleta_nova,
        "seguradas": _maior_primeiro(seguradas),
        "confirmadas": _maior_primeiro(confirmadas),
        "nao_recoletadas": sorted(nao_recoletadas),
        "ausentes": sorted(ausentes),
        "removidas": sorted(removidas),
        "total_confirmado": bool(atual and atual["confirmou_total"]),
    }


__all__ = [
    "ARQUIVO_STAGING",
    "CONTRATO_COLUNAS_HISTORICO",
    "DIRECOES_SALTO",
    "MOTIVOS_RECUSA",
    "SITUACOES_LEITURA",
    "STATUS_SALDO_VALIDOS",
    "STATUS_VARIACAO_TELA",
    "ler_historico_contagem",
    "ler_historico_tolerante",
    "execucoes",
    "pivot_contagem",
    "saldo_entre_execucoes",
    "avaliar_queda_da_execucao",
    "acompanhar_redes",
    "contagem_da_tela",
]
