"""Motor de diagnostico da rede Ultra - BLK-EXEC-03.

Camada PARALELA, READ-ONLY sobre o M1. **Funcao pura**: recebe o fechamento mensal, nao
le disco, nao chama API, nao guarda estado.

Regua absoluta, nao quartil
---------------------------
Cortar por quartil parece neutro e nao e': por construcao, 25% da rede fica sempre no pior
quartil de cada metrica. Medido contra a base real, o corte por quartil acendia algum
alerta em **76 de 89 unidades (85% da rede)** -- uma fila de trabalho com 85% da rede
dentro nao e' fila, e' ruido. O `CLAUDE.md` §2 ja dizia: "quartis sao apoio de ranking
relativo; para decisao executiva, priorizar regua absoluta".

Tres mecanismos empilhados seguram o ruido:

1. **regua absoluta** em vez de quartil;
2. **persistencia** em vez de foto do mes (o saldo operacional exige 3 meses FECHADOS
   seguidos no vermelho, nao um mes ruim);
3. **severidade em dois niveis** -- `alta` com um alerta grave OU dois medios.

Meta nao e' alerta
------------------
`NPS_IDEAL = 60` e' a **meta oficial** da rede (PowerBI) e 38% das unidades estao abaixo
dela: numero certo para uma linha de referencia no grafico, errado para uma fila de visita.
A meta e' EXIBIDA; o alerta dispara em 40.

Texto
-----
Toda string daqui vai para o JSON (UTF-8) **e** para o PDF (`fpdf2`, fonte core Helvetica,
encoding latin-1). Acento portugues renderiza normalmente; o que NAO pode aparecer e'
tipografia fora de latin-1 (travessao, bullet, seta, reticencias unicode, aspas curvas,
sinal de menos U+2212), que o fpdf2 troca por "?" em silencio. Imposto por teste.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import pandas as pd

from motor_expansao.dashboard.rede_metricas import METRICAS_A_VALIDAR

# ---------------------------------------------------------------------------
# Reguas vigentes
#
# UM bloco so, servido em `/api/rede/filtros` e impresso no rodape do PDF: e' impossivel a
# tela mostrar uma regua e o motor aplicar outra. Ao lado de cada limiar, o que ele acende
# na base de jul/2026 (86 unidades comparaveis) -- o numero que justifica o corte.
# Recalibrar aqui, e so aqui.
# ---------------------------------------------------------------------------

#: churn mensal (cancelados / recorrentes do mes ANTERIOR, como o DAX oficial)
REGUA_CHURN_PCT = 8.0  # acende 15 (17%)
REGUA_CHURN_GRAVE_PCT = 12.0
#: conversao visita -> convertido
REGUA_CONVERSAO_PCT = 40.0  # acende 15 (16%)
REGUA_CONVERSAO_GRAVE_PCT = 25.0
#: NPS (a META oficial e' 60; o ALERTA e' bem mais abaixo, de proposito)
REGUA_NPS = 40.0  # acende 19 (21%)
REGUA_NPS_GRAVE = 20.0
META_NPS = 60.0
#: dependencia de agregador, em % dos ALUNOS (nao da receita: por receita o corte de 70%
#: nao acende nenhuma unidade, porque o aluno de agregador paga muito menos)
REGUA_DEPENDENCIA_AGREGADOR_PCT = 70.0  # acende 6 (7%)
REGUA_DEPENDENCIA_AGREGADOR_GRAVE_PCT = 85.0
#: saldo operacional (vendas - cancelados) negativo por N meses FECHADOS consecutivos
MESES_SALDO_NEGATIVO = 3  # acende 12 (14%)
#: queda do faturamento contra a media dos 3 meses fechados anteriores
REGUA_QUEDA_FATURAMENTO_PCT = -10.0  # acende 14 (18%)
REGUA_QUEDA_FATURAMENTO_GRAVE_PCT = -20.0

#: severidade `alta` = 1 alerta grave OU este tanto de alertas medios.
#:
#: E' o parametro que regula o TAMANHO da fila sem mexer em limiar nenhum -- se a fila
#: crescer demais, sobe-se este numero e nenhuma regua de negocio muda. Medido sobre os 5
#: ultimos meses fechados da base de producao (mar a jul/2026), a fatia `alta` fica em:
#:   2 medios -> 22%, 26%, 28%, 23%, 33%   (estoura a banda alvo em julho)
#:   3 medios -> 12%, 17%, 24%, 18%, 24%   (dentro da banda nos cinco meses)
MEDIOS_PARA_ALTA = 3

#: Banda alvo da fatia `alta`. Abaixo do piso a tela nao aponta trabalho nenhum; acima do
#: teto ela vira parede e o time volta para a planilha. O teste-guardiao
#: `test_banda_alvo_da_fila_acionavel` falha o CI quando a regra sai daqui.
BANDA_ALVO_ALTA = (0.05, 0.30)

REGUAS_VIGENTES: dict[str, dict[str, object]] = {
    "churn": {
        "rotulo": "Churn mensal",
        "metrica": "churn_pct",
        "sentido": "acima",
        "limiar": REGUA_CHURN_PCT,
        "limiar_grave": REGUA_CHURN_GRAVE_PCT,
        "unidade": "%",
    },
    "conversao": {
        "rotulo": "Conversao de visitas",
        "metrica": "conversao_pct",
        "sentido": "abaixo",
        "limiar": REGUA_CONVERSAO_PCT,
        "limiar_grave": REGUA_CONVERSAO_GRAVE_PCT,
        "unidade": "%",
    },
    "nps": {
        "rotulo": "NPS",
        "metrica": "nps",
        "sentido": "abaixo",
        "limiar": REGUA_NPS,
        "limiar_grave": REGUA_NPS_GRAVE,
        "unidade": "pontos",
        "meta": META_NPS,
    },
    "agregador": {
        "rotulo": "Dependencia de agregador",
        "metrica": "pct_agregador_alunos",
        "sentido": "acima",
        "limiar": REGUA_DEPENDENCIA_AGREGADOR_PCT,
        "limiar_grave": REGUA_DEPENDENCIA_AGREGADOR_GRAVE_PCT,
        "unidade": "% dos alunos",
    },
    "saldo": {
        "rotulo": "Saldo operacional negativo",
        "metrica": "saldo_operacional",
        "sentido": "persistencia",
        "limiar": 0.0,
        "meses": MESES_SALDO_NEGATIVO,
        "unidade": "alunos",
    },
    "queda_faturamento": {
        "rotulo": "Queda de faturamento",
        "metrica": "faturamento",
        "sentido": "abaixo",
        "limiar": REGUA_QUEDA_FATURAMENTO_PCT,
        "limiar_grave": REGUA_QUEDA_FATURAMENTO_GRAVE_PCT,
        "unidade": "% vs media de 3 meses",
    },
}

# Faixas de faturamento que o time de campo JA usa na planilha diaria. Adotadas como
# estao, de proposito: e' a lingua deles. Ressalva honesta, que vai na nota de metodo da
# tela -- sao faixas absolutas aplicadas igualmente a unidade de bairro e a flagship, sem
# normalizar por porte ou idade; o benchmark por coorte e' o contrapeso.
FAIXAS_FATURAMENTO: tuple[tuple[float, str, str], ...] = (
    (150_000.0, "critico", "Critico"),
    (200_000.0, "regular", "Regular"),
    (250_000.0, "bom", "Bom"),
    (300_000.0, "excelente", "Excelente"),
    (float("inf"), "excelente_mais", "Excelente+"),
)


def faixa_faturamento(valor: object) -> tuple[str, str]:
    """(chave, rotulo) da faixa de faturamento do time de campo."""
    numero = pd.to_numeric(valor, errors="coerce")
    if pd.isna(numero):
        return ("sem_dado", "Sem dado")
    for teto, chave, rotulo in FAIXAS_FATURAMENTO:
        if float(numero) < teto:
            return (chave, rotulo)
    return FAIXAS_FATURAMENTO[-1][1], FAIXAS_FATURAMENTO[-1][2]


# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Alerta:
    codigo: str
    titulo: str
    detalhe: str
    #: 'grave' | 'medio'
    nivel: str
    valor: float | None = None
    limiar: float | None = None


@dataclass(frozen=True)
class Recomendacao:
    codigo: str
    titulo: str
    corpo: str


@dataclass(frozen=True)
class Diagnostico:
    unidade_id: str
    #: competencia FECHADA sobre a qual o diagnostico foi calculado
    competencia: str
    #: 'alta' | 'media' | 'ok' | 'sem_base'
    severidade: str
    prioridade: float
    resumo: str
    faixa_faturamento: str
    faixa_faturamento_rotulo: str
    alertas: tuple[Alerta, ...] = field(default_factory=tuple)
    recomendacoes: tuple[Recomendacao, ...] = field(default_factory=tuple)


SEVERIDADES = ("alta", "media", "ok", "sem_base")

ROTULO_SEVERIDADE = {
    "alta": "Prioridade alta",
    "media": "Atencao",
    "ok": "Sem alerta",
    "sem_base": "Sem base de comparacao",
}


# ---------------------------------------------------------------------------
# Motor
# ---------------------------------------------------------------------------


def competencia_base(fech: pd.DataFrame, competencia: str | None = None) -> str | None:
    """Ultima competencia FECHADA em `fech` que nao passe de `competencia`.

    O diagnostico nunca roda sobre mes aberto: no dia 2 do mes, o acumulado de dois dias
    acenderia queda de faturamento na rede inteira. Quando o operador escolhe o mes
    corrente, a tela mostra o MTD e diz, com todas as letras, de que mes fechado vem o
    diagnostico.
    """
    if not len(fech):
        return None
    fechados = fech[fech["mes_completo"].fillna(False).astype(bool)]
    if competencia:
        fechados = fechados[fechados["competencia"] <= competencia]
    if not len(fechados):
        return None
    return str(fechados["competencia"].max())


def diagnosticar(
    fech: pd.DataFrame,
    competencia: str,
    unidades: Sequence[str] | None = None,
) -> dict[str, Diagnostico]:
    """Diagnostico de cada unidade na competencia FECHADA `competencia`.

    Puro. `fech` e' o fechamento mensal COMPLETO (toda a serie), porque os alertas de
    persistencia e de queda olham para tras.
    """
    if not len(fech):
        return {}
    mes = fech[fech["competencia"] == competencia]
    if unidades is not None:
        mes = mes[mes["unidade_id"].isin(list(unidades))]
    if not len(mes):
        return {}

    historico = _historico_fechado(fech, competencia)
    faturamentos = pd.to_numeric(
        mes.loc[mes["operacao_mes_cheio"].fillna(False).astype(bool), "faturamento"],
        errors="coerce",
    ).dropna()

    saida: dict[str, Diagnostico] = {}
    for linha in mes.to_dict("records"):
        uid = str(linha["unidade_id"])
        chave_faixa, rotulo_faixa = faixa_faturamento(linha.get("faturamento"))
        comparavel = bool(linha.get("operacao_mes_cheio")) and bool(linha.get("mes_completo"))
        if not comparavel:
            saida[uid] = Diagnostico(
                unidade_id=uid,
                competencia=competencia,
                severidade="sem_base",
                prioridade=0.0,
                resumo="Unidade inaugurada dentro do periodo: numeros ainda nao comparaveis.",
                faixa_faturamento=chave_faixa,
                faixa_faturamento_rotulo=rotulo_faixa,
            )
            continue

        alertas = _alertas_da_unidade(linha, historico.get(uid, []))
        severidade = _severidade(alertas)
        porte = _percentil(faturamentos, linha.get("faturamento"))
        saida[uid] = Diagnostico(
            unidade_id=uid,
            competencia=competencia,
            severidade=severidade,
            prioridade=_prioridade(alertas, porte),
            resumo=_resumo(alertas),
            faixa_faturamento=chave_faixa,
            faixa_faturamento_rotulo=rotulo_faixa,
            alertas=alertas,
            recomendacoes=recomendar(alertas),
        )
    return saida


def _historico_fechado(fech: pd.DataFrame, competencia: str) -> dict[str, list[dict]]:
    """Meses FECHADOS ate `competencia`, por unidade, em ordem cronologica."""
    passado = fech[
        fech["mes_completo"].fillna(False).astype(bool)
        & (fech["competencia"] <= competencia)
        & fech["operacao_mes_cheio"].fillna(False).astype(bool)
    ].sort_values(["unidade_id", "competencia"], kind="stable")
    historico: dict[str, list[dict]] = {}
    for registro in passado.to_dict("records"):
        historico.setdefault(str(registro["unidade_id"]), []).append(registro)
    return historico


def _alertas_da_unidade(linha: dict, historico: list[dict]) -> tuple[Alerta, ...]:
    alertas: list[Alerta] = []

    churn = _numero(linha.get("churn_pct"))
    if churn is not None and churn > REGUA_CHURN_PCT:
        alertas.append(
            Alerta(
                "churn",
                "Churn alto",
                f"Churn de {_pct(churn)} no mes, acima da regua de {_pct(REGUA_CHURN_PCT)}.",
                "grave" if churn > REGUA_CHURN_GRAVE_PCT else "medio",
                churn,
                REGUA_CHURN_PCT,
            )
        )

    conversao = _numero(linha.get("conversao_pct"))
    if conversao is not None and conversao < REGUA_CONVERSAO_PCT:
        alertas.append(
            Alerta(
                "conversao",
                "Conversao baixa",
                f"Converte {_pct(conversao)} das visitas, abaixo da regua de "
                f"{_pct(REGUA_CONVERSAO_PCT)}.",
                "grave" if conversao < REGUA_CONVERSAO_GRAVE_PCT else "medio",
                conversao,
                REGUA_CONVERSAO_PCT,
            )
        )

    nps = _numero(linha.get("nps"))
    if nps is not None and nps < REGUA_NPS:
        alertas.append(
            Alerta(
                "nps",
                "NPS baixo",
                f"NPS de {nps:.0f}, abaixo da regua de {REGUA_NPS:.0f} "
                f"(a meta da rede e' {META_NPS:.0f}).",
                "grave" if nps < REGUA_NPS_GRAVE else "medio",
                nps,
                REGUA_NPS,
            )
        )

    dependencia = _numero(linha.get("pct_agregador_alunos"))
    if dependencia is not None and dependencia > REGUA_DEPENDENCIA_AGREGADOR_PCT:
        alertas.append(
            Alerta(
                "agregador",
                "Dependencia de agregador",
                f"{_pct(dependencia)} dos alunos vem de Gympass/Totalpass, acima da regua "
                f"de {_pct(REGUA_DEPENDENCIA_AGREGADOR_PCT)}.",
                "grave" if dependencia > REGUA_DEPENDENCIA_AGREGADOR_GRAVE_PCT else "medio",
                dependencia,
                REGUA_DEPENDENCIA_AGREGADOR_PCT,
            )
        )

    ultimos = historico[-MESES_SALDO_NEGATIVO:]
    saldos = [_numero(m.get("saldo_operacional")) for m in ultimos]
    if len(saldos) == MESES_SALDO_NEGATIVO and all(s is not None and s < 0 for s in saldos):
        total = sum(s for s in saldos if s is not None)
        alertas.append(
            Alerta(
                "saldo",
                "Saldo operacional negativo",
                f"Vendas menos cancelamentos no vermelho ha {MESES_SALDO_NEGATIVO} meses "
                f"seguidos ({total:+.0f} alunos no periodo).",
                "grave",
                total,
                0.0,
            )
        )

    queda = _variacao_vs_media(linha, historico)
    if queda is not None and queda <= REGUA_QUEDA_FATURAMENTO_PCT:
        alertas.append(
            Alerta(
                "queda_faturamento",
                "Queda de faturamento",
                f"Faturamento {_pct(abs(queda))} abaixo da media dos 3 meses anteriores.",
                "grave" if queda <= REGUA_QUEDA_FATURAMENTO_GRAVE_PCT else "medio",
                queda,
                REGUA_QUEDA_FATURAMENTO_PCT,
            )
        )

    return tuple(alertas)


def _variacao_vs_media(linha: dict, historico: list[dict]) -> float | None:
    """Variacao % do faturamento do mes contra a media dos 3 meses fechados anteriores."""
    anteriores = [
        _numero(m.get("faturamento"))
        for m in historico[:-1][-3:]
        if str(m.get("competencia")) != str(linha.get("competencia"))
    ]
    validos = [v for v in anteriores if v is not None and v > 0]
    if len(validos) < 3:
        return None
    atual = _numero(linha.get("faturamento"))
    if atual is None:
        return None
    media = sum(validos) / len(validos)
    return 100.0 * (atual - media) / media


def _severidade(alertas: Sequence[Alerta]) -> str:
    graves = sum(1 for a in alertas if a.nivel == "grave")
    medios = sum(1 for a in alertas if a.nivel == "medio")
    if graves >= 1 or medios >= MEDIOS_PARA_ALTA:
        return "alta"
    if medios >= 1:
        return "media"
    return "ok"


def _prioridade(alertas: Sequence[Alerta], porte: float) -> float:
    """Ordem de trabalho: gravidade primeiro, tamanho da unidade como desempate.

    Duas unidades com o mesmo par de alertas nao valem a mesma visita se uma fatura
    R$ 700 mil e a outra R$ 30 mil. `porte` e' o percentil de faturamento na rede (0..1) e
    so consegue modular a pontuacao entre 50% e 100% -- nunca inverter a ordem de
    gravidade.
    """
    pontos = sum(3.0 if a.nivel == "grave" else 1.0 for a in alertas)
    return round(pontos * (0.5 + 0.5 * porte), 3)


def _resumo(alertas: Sequence[Alerta]) -> str:
    if not alertas:
        return "Nenhum alerta nas reguas vigentes."
    return " ".join(a.detalhe for a in alertas)


# ---------------------------------------------------------------------------
# Recomendacoes
# ---------------------------------------------------------------------------

_RECOMENDACOES: dict[str, tuple[str, str]] = {
    "churn": (
        "Atacar a retencao",
        "Puxar a lista de cancelamentos do mes e separar motivo de saida de motivo de "
        "cobranca. Cancelamento por inadimplencia se resolve na regua de cobranca; "
        "cancelamento por uso se resolve com reativacao e agenda de treino.",
    ),
    "conversao": (
        "Rever o atendimento da visita",
        "A visita ja chegou na unidade: o gargalo esta na abordagem, na oferta ou no "
        "acompanhamento. Conferir o roteiro de visita e o tempo de resposta ao lead.",
    ),
    "nps": (
        "Tratar as pesquisas abertas",
        "Fechar o ciclo com quem respondeu mal antes de rodar nova pesquisa. NPS baixo com "
        "pesquisa nao tratada costuma ser problema de manutencao ou de limpeza.",
    ),
    "agregador": (
        "Reduzir a dependencia de agregador",
        "A base de alunos esta concentrada em Gympass/Totalpass, que pagam menos por aluno "
        "e podem sair em bloco por decisao do parceiro. Trabalhar conversao de agregador "
        "em recorrente com oferta de migracao.",
    ),
    "saldo": (
        "Reverter o saldo operacional",
        "Ha tres meses a unidade cancela mais do que vende. Isso corroi a base mesmo com "
        "faturamento estavel, porque o efeito aparece com atraso. Priorizar meta de vendas "
        "e bloqueio de cancelamento evitavel.",
    ),
    "queda_faturamento": (
        "Investigar a queda",
        "Comparar com o mesmo mes do ano anterior antes de concluir: pode ser sazonal. Se "
        "nao for, olhar mix de plano e inadimplencia no mesmo periodo.",
    ),
}


def recomendar(alertas: Sequence[Alerta]) -> tuple[Recomendacao, ...]:
    """Uma recomendacao por alerta, na ordem em que os alertas acenderam."""
    saida: list[Recomendacao] = []
    vistos: set[str] = set()
    for alerta in alertas:
        if alerta.codigo in vistos or alerta.codigo not in _RECOMENDACOES:
            continue
        vistos.add(alerta.codigo)
        titulo, corpo = _RECOMENDACOES[alerta.codigo]
        saida.append(Recomendacao(alerta.codigo, titulo, corpo))
    return tuple(saida)


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _numero(valor: object) -> float | None:
    numero = pd.to_numeric(valor, errors="coerce")
    if numero is None or pd.isna(numero):
        return None
    return float(numero)


def _pct(valor: float) -> str:
    """Percentual com virgula decimal, como o resto do produto."""
    return f"{valor:.1f}".replace(".", ",") + "%"


def _percentil(valores: pd.Series, valor: object) -> float:
    numero = _numero(valor)
    if numero is None or not len(valores):
        return 0.0
    return float((valores < numero).mean())


def metricas_proibidas_em_alerta() -> frozenset[str]:
    """Metricas cuja definicao nao foi confirmada com a Growth (exibidas, nunca alertam).

    `inadimplente` passa de 100% dos pagantes em ~10% dos fechamentos -- o denominador e'
    desconhecido. Alertar sobre um numero que nao se sabe ler manda o time de campo visitar
    unidade por causa de erro de leitura nossa.
    """
    return METRICAS_A_VALIDAR
