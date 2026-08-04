"""Benchmark por coorte de MATURIDADE da rede Ultra - BLK-EXEC-04.

Camada PARALELA, READ-ONLY sobre o M1. Puro: nao le disco, nao chama API.

Por que maturidade, e nao geografia
-----------------------------------
A **DEC-014** ja decidiu isto: o eixo territorial de retencao deu NO-GO, e a parte
previsivel do desempenho de uma unidade e' o **tempo de operacao**, nao o lugar. Comparar
uma unidade de 4 meses com a media da rede e' comparar rampa com regime; comparar com
pares que abriram na mesma epoca e' a leitura defensavel.

O modulo nao le nenhuma coluna geografica de proposito, e um teste de AST o impoe
(`test_benchmark_nao_usa_geografia`) -- e' a DEC-014 escrita em codigo, para que a
geografia nao volte pela porta dos fundos num refactor futuro.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import pandas as pd

COORTE_INDEFINIDA = "indefinida"


@dataclass(frozen=True)
class Coorte:
    chave: str
    rotulo: str
    #: limites em meses de operacao, inclusivos nas duas pontas
    minimo: int
    maximo: int


# Faixas por semantica operacional (rampa / consolidacao / regime), nao por quantil: um
# corte por quantil mudaria de significado a cada mes em que a rede cresce. Distribuicao
# medida em jul/2026, 92 unidades: 16 / 16 / 23 / 26 / 11.
COORTES: tuple[Coorte, ...] = (
    Coorte("0_5", "0 a 5 meses", 0, 5),
    Coorte("6_11", "6 a 11 meses", 6, 11),
    Coorte("12_23", "12 a 23 meses", 12, 23),
    Coorte("24_47", "2 a 4 anos", 24, 47),
    Coorte("48_mais", "4 anos ou mais", 48, 10**6),
)
COORTES_POR_CHAVE = {c.chave: c for c in COORTES}

ROTULOS_COORTE: dict[str, str] = {c.chave: c.rotulo for c in COORTES}
ROTULOS_COORTE[COORTE_INDEFINIDA] = "Maturidade indefinida"

# Abaixo disto, "o percentil da coorte" e' ruido estatistico e o modulo DEGRADA em vez de
# fingir precisao. Com 5 unidades, o p25 e o p75 sao a 2a e a 4a unidade.
N_MINIMO_PEER = 8


def atribuir_coorte(meses_operacao: object) -> str:
    """Chave da coorte de maturidade, ou `indefinida` se a inauguracao nao for confiavel."""
    numero = pd.to_numeric(meses_operacao, errors="coerce")
    if numero is None or pd.isna(numero):
        return COORTE_INDEFINIDA
    meses = float(numero)
    if meses < 0:
        return COORTE_INDEFINIDA
    for coorte in COORTES:
        if coorte.minimo <= meses <= coorte.maximo:
            return coorte.chave
    return COORTE_INDEFINIDA


def coorte_vizinha(chave: str) -> str | None:
    """Coorte adjacente para onde degradar quando a propria e' pequena demais."""
    ordem = [c.chave for c in COORTES]
    if chave not in ordem:
        return None
    i = ordem.index(chave)
    # Prefere a coorte MAIS MADURA como vizinha: a rampa de uma unidade de 5 meses se
    # parece mais com a de uma de 7 do que com a de uma que ainda nao abriu.
    if i + 1 < len(ordem):
        return ordem[i + 1]
    return ordem[i - 1] if i > 0 else None


#: Fracao da janela que uma unidade precisa ter coletado para servir de referencia.
#: E' RELATIVA ao resto do recorte de proposito -- ver `anotar_coortes`.
COBERTURA_MINIMA_DA_JANELA = 0.8


def anotar_coortes(mes: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta `coorte`, `coorte_rotulo` e `no_peer_set` ao fechamento de um mes.

    `no_peer_set` e' quem pode servir de REFERENCIA para os outros: unidade que operou a
    janela inteira, com maturidade conhecida e com dado suficiente. Uma unidade inaugurada
    no dia 30 continua na carteira (e' academia de verdade e o time precisa ve-la), mas
    nao entra na conta de ninguem.

    "Dado suficiente" e' medido em RELACAO ao recorte, nao contra um numero fixo de dias.
    A razao e' concreta: no dia 3 do mes, TODAS as unidades tem 3 dias de dado, e um piso
    absoluto de 25 dias esvaziaria o peer set inteiro -- a ficha perdia a comparacao por
    coorte justamente na competencia que o time abre todo dia. Com uma janela cortada no
    mesmo dia para todo mundo, comparar parcial com parcial e' honesto; o que nao pode e'
    entrar na conta quem coletou bem menos dias que os pares (unidade que parou de
    reportar no meio do periodo teria um acumulado artificialmente baixo).
    """
    saida = mes.copy()
    if not len(saida):
        saida["coorte"] = pd.Series(dtype="object")
        saida["coorte_rotulo"] = pd.Series(dtype="object")
        saida["no_peer_set"] = pd.Series(dtype="bool")
        return saida
    saida["coorte"] = saida["meses_operacao"].map(atribuir_coorte)
    saida["coorte_rotulo"] = saida["coorte"].map(ROTULOS_COORTE)

    dias = pd.to_numeric(saida.get("dias_com_dado"), errors="coerce")
    if dias is None or dias.isna().all():
        cobertura_ok = pd.Series(True, index=saida.index)
    else:
        cobertura_ok = dias >= COBERTURA_MINIMA_DA_JANELA * float(dias.max())

    saida["no_peer_set"] = (
        cobertura_ok.fillna(False).astype(bool)
        & saida.get("operacao_mes_cheio", pd.Series(True, index=saida.index)).fillna(False).astype(bool)
        & saida["coorte"].ne(COORTE_INDEFINIDA)
    )
    return saida


@dataclass(frozen=True)
class Referencia:
    """Distribuicao de uma metrica no conjunto de pares efetivamente usado."""

    metrica: str
    n: int
    p25: float | None
    p50: float | None
    p75: float | None


@dataclass(frozen=True)
class Benchmark:
    """Comparacao de uma unidade contra seus pares, com a degradacao explicita."""

    unidade_id: str
    coorte: str
    coorte_rotulo: str
    #: 'coorte' | 'coorte_vizinha' | 'rede' | 'sem_dado' - SEMPRE servido ao cliente.
    degradacao: str
    base_rotulo: str
    n: int
    referencias: dict[str, Referencia]
    percentis: dict[str, float | None]


ROTULO_DEGRADACAO = {
    "coorte": "pares da mesma maturidade",
    "coorte_vizinha": "pares da maturidade vizinha (a coorte própria é pequena demais)",
    "rede": "rede toda (sem pares suficientes na maturidade)",
    "sem_dado": "sem base de comparação",
}


def comparar(
    mes_anotado: pd.DataFrame,
    unidade_id: str,
    metricas: Sequence[str],
) -> Benchmark:
    """Compara uma unidade com seus pares, descendo a escada de degradacao.

    Escada: coorte propria (n >= 8) -> coorte vizinha -> rede toda -> sem dado. O degrau
    usado vai no payload E no PDF; e' a licao literal do `fonte_base_calibracao` do piloto,
    onde a degradacao silenciosa mudava o significado dos percentis sem sinal nenhum na
    tela.

    O peer set sai SEMPRE da rede inteira que chega aqui, nunca do recorte filtrado da
    tela: filtrar "master = PR" e comparar contra 2 pares seria ruido -- e reintroduziria
    a geografia que a DEC-014 tirou.
    """
    if not len(mes_anotado) or "unidade_id" not in mes_anotado.columns:
        return Benchmark(unidade_id, COORTE_INDEFINIDA, ROTULOS_COORTE[COORTE_INDEFINIDA],
                         "sem_dado", ROTULO_DEGRADACAO["sem_dado"], 0, {}, {})
    linha = mes_anotado[mes_anotado["unidade_id"] == unidade_id]
    if not len(linha):
        return Benchmark(unidade_id, COORTE_INDEFINIDA, ROTULOS_COORTE[COORTE_INDEFINIDA],
                         "sem_dado", ROTULO_DEGRADACAO["sem_dado"], 0, {}, {})
    coorte = str(linha.iloc[0]["coorte"])

    pares = mes_anotado[mes_anotado["no_peer_set"]]
    degradacao = "sem_dado"
    escolhidos = pares.iloc[0:0]
    for candidata, degrau in _degraus(coorte):
        conjunto = pares if candidata is None else pares[pares["coorte"] == candidata]
        # A propria unidade nao entra na referencia contra a qual ela e' medida.
        conjunto = conjunto[conjunto["unidade_id"] != unidade_id]
        if len(conjunto) >= N_MINIMO_PEER:
            escolhidos, degradacao = conjunto, degrau
            break

    referencias: dict[str, Referencia] = {}
    percentis: dict[str, float | None] = {}
    for metrica in metricas:
        if metrica not in mes_anotado.columns:
            continue
        valores = pd.to_numeric(escolhidos[metrica], errors="coerce").dropna()
        referencias[metrica] = Referencia(
            metrica,
            int(len(valores)),
            _num(valores.quantile(0.25)) if len(valores) else None,
            _num(valores.median()) if len(valores) else None,
            _num(valores.quantile(0.75)) if len(valores) else None,
        )
        proprio = pd.to_numeric(linha.iloc[0].get(metrica), errors="coerce")
        percentis[metrica] = (
            _num(100.0 * float((valores < proprio).mean()))
            if len(valores) and pd.notna(proprio)
            else None
        )

    return Benchmark(
        unidade_id=unidade_id,
        coorte=coorte,
        coorte_rotulo=ROTULOS_COORTE.get(coorte, coorte),
        degradacao=degradacao,
        base_rotulo=ROTULO_DEGRADACAO[degradacao],
        n=int(len(escolhidos)),
        referencias=referencias,
        percentis=percentis,
    )


def _degraus(coorte: str) -> Iterable[tuple[str | None, str]]:
    if coorte != COORTE_INDEFINIDA:
        yield coorte, "coorte"
        vizinha = coorte_vizinha(coorte)
        if vizinha:
            yield vizinha, "coorte_vizinha"
    yield None, "rede"


def resumo_coortes(mes_anotado: pd.DataFrame) -> list[dict[str, object]]:
    """Contagem por coorte para o filtro e o card de distribuicao."""
    if not len(mes_anotado):
        return []
    contagem = mes_anotado["coorte"].value_counts()
    ordem = [c.chave for c in COORTES] + [COORTE_INDEFINIDA]
    return [
        {"chave": chave, "rotulo": ROTULOS_COORTE.get(chave, chave), "n": int(contagem[chave])}
        for chave in ordem
        if chave in contagem.index
    ]


def _num(valor: object) -> float | None:
    """float JSON-safe (NaN/inf/None -> None)."""
    try:
        f = float(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if (f != f or f in (float("inf"), float("-inf"))) else f
