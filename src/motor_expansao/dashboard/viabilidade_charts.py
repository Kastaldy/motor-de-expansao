"""Graficos financeiros de viabilidade em PNG estatico (BLK-RELVIAB-03).

Reproduz, em matplotlib -> PNG (BytesIO), os graficos que a aba de Viabilidade ja
plota em Plotly, para embutir no PDF do Relatorio Pontual (via `pdf.image(BytesIO(...))`).
Backend `Agg` (headless, sem display). Funcoes PURAS: recebem a serie mensal / numeros do
DRE e devolvem `bytes` de um PNG valido — sem I/O de disco, sem estado global, sem
dependencia nova (matplotlib ja e base). READ-ONLY sobre o M1 (nao recalcula score/artefatos).

RENDER PURO (FIN-VIAB-01, 2026-07-24)
-------------------------------------
Este modulo NAO importa `motor_expansao.dimensionamento` e NAO faz aritmetica
financeira. A fonte de tudo e o `viabilidade_payload_v1` que a API devolve — o
MESMO objeto que a tela consome — via `montar_payload_pdf_viabilidade()`:

  - FCF acumulado e a linha de payback: `serie_mensal[].fcf_acumulado` +
    `retorno.payback` (antes o grafico recalculava o cruzamento por conta propria e
    marcava o mes 33 enquanto o card dizia 35);
  - resultado mensal: `serie_mensal[].fcf_mensal`;
  - faturamento x EBITDA: `serie_mensal[].faturamento_mensal` / `.ebitda_mensal`
    (o EBITDA do mes 1 e NEGATIVO por construcao — o custo operacional e integral
    desde o mes 1 enquanto a rampa de alunos ainda esta no comeco, e desde a decisao
    de Felipe de 2026-07-24 a FOLHA tambem e integral desde o mes 1, o que aprofunda
    esse primeiro mes: -R$43.464,47 contra -R$10.139,56 na versao anterior);
  - composicao do custo do mes de steady: `dre.custos_variaveis` / `dre.folha` /
    `dre.custos_fixos` (a folha e custo FIXO, dimensionada pelo faturamento MADURO);
  - taxa de franquia e seu parcelamento: `investimento.taxa_franquia` /
    `investimento.parcelas_franquia` (campo novo; ausente -> a linha nao afirma nada);
  - aluguel-teto impresso: `aluguel_teto.canonico` (= a faixa `teto`, 20% do
    faturamento bruto; a `excecao` de 30% segue impressa no detalhe, nao no card);
  - break-even impresso: `break_even.ebitda`/`break_even.caixa`, em alunos TOTAIS.

As unicas contas aqui sao GEOMETRIA de grafico (empilhamento das barras do
waterfall a partir das proprias linhas do DRE do payload).

A serie mensal legada (`dimensionamento.simulador.gerar_serie_mensal`, adaptador
historico) continua aceita pelos graficos por retrocompatibilidade.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from io import BytesIO
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless: sem display, deterministico.

import matplotlib.pyplot as plt  # noqa: E402  (import apos set do backend, obrigatorio)

# Paleta Ultra (mesmos tons do PDF/dashboard).
_TURQUESA = "#00A79D"
# Tom claro do turquesa: a ANUIDADE no waterfall. Mesma familia da mensalidade
# (as duas sao faturamento bruto) e ainda assim distinguivel como linha propria.
_TURQUESA_CLARO = "#7FD4CE"
_MAGENTA = "#C23C8E"
_CINZA = "#3C3C3C"
_VERDE = "#1AAA55"

_FIG_W = 6.0
_FIG_H = 3.6
_DPI = 100
# Dimensao nominal do PNG (px) = figsize * dpi. tight_layout NAO altera o figsize.
PNG_WIDTH = int(_FIG_W * _DPI)
PNG_HEIGHT = int(_FIG_H * _DPI)


def _fig_to_png(fig: Any) -> bytes:
    """Serializa a figura como PNG (FUNDO TRANSPARENTE) e fecha a figura (sem vazar estado)."""
    buffer = BytesIO()
    fig.tight_layout()
    # transparent=True -> sem retangulo branco atras do grafico (mostra o fundo da pagina).
    fig.savefig(buffer, format="png", dpi=_DPI, transparent=True)
    plt.close(fig)
    return buffer.getvalue()


def _brl(value: float) -> str:
    """R$ com separador de milhar pt-BR (ex.: 193000 -> 'R$ 193.000')."""
    return "R$ " + f"{value:,.0f}".replace(",", ".")


def _pct_fracao(fracao: float) -> str:
    """FRACAO ja pronta do payload -> percentual pt-BR (0.3873 -> '38,7%').

    O x100 e RENDER (mesma regra do `pctFrac` da tela), nao aritmetica financeira:
    a divisao pelo faturamento ja foi feita no motor/backend. Nenhum numero novo
    nasce aqui (FIN-VIAB-01). Sem separador de milhar: percentual nao chega la.
    """
    return f"{fracao * 100:.1f}".replace(".", ",") + "%"


def _finite(value: Any) -> float | None:
    """float finito ou None (NaN/inf/None viram None)."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _coluna(serie: Sequence[dict], *chaves: str) -> list[float]:
    """Coluna da serie pela PRIMEIRA chave presente (aceita o nome novo e o legado).

    Ex.: `_coluna(serie, "fcf_mensal", "fcf")` le a serie canonica do nucleo
    (`fcf_mensal`) e, se ela nao existir, a serie legada do backend (`fcf`).
    """
    saida: list[float] = []
    for ponto in serie:
        valor = 0.0
        for chave in chaves:
            bruto = ponto.get(chave)
            if bruto is not None:
                try:
                    valor = float(bruto)
                except (TypeError, ValueError):
                    valor = 0.0
                break
        saida.append(valor)
    return saida


def _so_operacao(serie: Sequence[dict]) -> list[dict]:
    """Linhas da fase de OPERACAO (M1..M60). Serie sem `fase` (legado) passa inteira."""
    return [linha for linha in serie if str(linha.get("fase", "operacao")) == "operacao"]


def grafico_rampa_alunos(
    serie: Sequence[dict],
    *,
    steady: float | None = None,
    maturacao_mes: int | None = None,
) -> bytes:
    """Rampa de alunos (balcao) ao longo dos meses; steady-state e maturacao como marcos."""
    meses = _coluna(serie, "mes")
    alunos = _coluna(serie, "alunos_balcao")
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), dpi=_DPI)
    ax.plot(meses, alunos, color=_TURQUESA, linewidth=2)
    steady_f = _finite(steady)
    if steady_f is not None:
        ax.axhline(steady_f, color=_MAGENTA, linestyle="--", linewidth=1, label="Steady-state")
        ax.legend(loc="lower right", fontsize=8, frameon=False)
    if maturacao_mes is not None:
        ax.axvline(float(maturacao_mes), color=_CINZA, linestyle=":", linewidth=1)
    ax.set_title("Rampa de alunos (balcao)")
    ax.set_xlabel("Mes")
    ax.set_ylabel("Alunos")
    ax.grid(True, alpha=0.2)
    return _fig_to_png(fig)


def grafico_fco(serie: Sequence[dict], *, mes_positivo: int | None = None) -> bytes:
    """Fluxo de Caixa Operacional mes a mes (NAO acumulado): obras (M-4..M-1) + operacao.

    A serie e a `serie_mensal` do payload: os meses negativos sao a pre-abertura (obras:
    desembolso de capex + aluguel) e os meses >= 1 sao o resultado de caixa do mes
    (`fcf_mensal`). Verde acima de zero, magenta abaixo; marca a transicao obras->operacao e
    o mes em que a operacao passa a se pagar (`mes_caixa_operacional_positivo` do payload).
    Titulos/rotulos em ASCII (excecao de RENDER do PNG)."""
    meses = _coluna(serie, "mes")
    fco = _coluna(serie, "fcf_mensal", "fcf")
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), dpi=_DPI)
    mask_pos = [v >= 0 for v in fco]
    mask_neg = [v < 0 for v in fco]
    ax.fill_between(meses, fco, 0, where=mask_pos, color=_VERDE, alpha=0.30, step=None)
    ax.fill_between(meses, fco, 0, where=mask_neg, color=_MAGENTA, alpha=0.22, step=None)
    ax.plot(meses, fco, color=_CINZA, linewidth=1.8)
    ax.axhline(0.0, color=_CINZA, linewidth=0.8)
    # Transicao obras -> operacao (entre M-1 e M1).
    ax.axvline(0.0, color=_CINZA, linestyle=":", linewidth=1)
    mp = _finite(mes_positivo)
    if mp is not None:
        ax.axvline(
            mp, color=_TURQUESA, linestyle="--", linewidth=1, label=f"Se paga (mes {int(mp)})"
        )
        ax.legend(loc="lower right", fontsize=8, frameon=False)
    ax.set_title("Fluxo de Caixa Operacional")
    ax.set_xlabel("Mes (M-4 a M-1 = obras)")
    ax.set_ylabel("R$ / mes")
    ax.grid(True, alpha=0.2)
    return _fig_to_png(fig)


_MARGEM_EIXO_Y = 0.08


def limites_y_faturamento_ebitda(
    faturamento: Sequence[float], ebitda: Sequence[float]
) -> tuple[float, float] | None:
    """Limites do eixo Y que acomodam a barra MAIS ALTA e o vale MAIS FUNDO, com folga.

    GEOMETRIA de grafico, nao formula financeira: so le os extremos das duas series que
    ja vem do payload. Existe para o enquadramento ser EXPLICITO em vez de depender do
    autoscale: o EBITDA do mes 1 ficou bem mais negativo depois da folha fixa
    (-R$43.464,47 contra -R$10.139,56), e o eixo tem de descer com ele sem cortar a
    linha nem achatar as barras de faturamento.

    O zero entra sempre no intervalo (as barras nascem nele). Serie vazia/nao-finita ou
    span nulo -> None, e o chamador deixa o autoscale do matplotlib decidir.
    """
    valores = [v for v in [*faturamento, *ebitda] if math.isfinite(v)]
    if not valores:
        return None
    piso = min(0.0, min(valores))
    teto = max(0.0, max(valores))
    span = teto - piso
    if span <= 0.0:
        return None
    folga = span * _MARGEM_EIXO_Y
    return piso - folga, teto + folga


def grafico_faturamento_ebitda(serie: Sequence[dict]) -> bytes:
    """Faturamento (barras) e EBITDA (linha) mensais, direto da serie do payload.

    So a fase de OPERACAO entra (a pre-abertura nao tem faturamento). O EBITDA do mes 1
    aparece NEGATIVO: o custo operacional e integral desde a inauguracao enquanto a rampa
    de alunos ainda esta no comeco — e o comportamento correto do modelo, nao um defeito.
    Com a FOLHA FIXA desde o mes 1 (decisao de Felipe, 2026-07-24) esse primeiro mes ficou
    bem mais fundo (-R$43.464,47 contra -R$10.139,56 antes).

    O eixo Y e enquadrado por `limites_y_faturamento_ebitda`, que inclui o vale do EBITDA
    e o topo do faturamento com folga — o mes 1 nao encosta na borda nem sai da area de
    plotagem. A linha do ZERO e desenhada explicitamente para o sinal do EBITDA ser
    legivel: com as barras nascendo em zero e o eixo descendo aos -47 mil, sem ela nao
    havia referencia visual de onde o resultado troca de sinal.
    """
    operacao = _so_operacao(serie)
    meses = _coluna(operacao, "mes")
    faturamento = _coluna(operacao, "faturamento_mensal")
    ebitda = _coluna(operacao, "ebitda_mensal")
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), dpi=_DPI)
    ax.bar(meses, faturamento, color=_TURQUESA, alpha=0.55, label="Faturamento")
    ax.plot(meses, ebitda, color=_MAGENTA, linewidth=2, label="EBITDA")
    # Referencia do zero: o EBITDA dos primeiros meses e negativo e precisa ler como tal.
    ax.axhline(0.0, color=_CINZA, linewidth=0.8)
    limites = limites_y_faturamento_ebitda(faturamento, ebitda)
    if limites is not None:
        ax.set_ylim(*limites)
    ax.set_title("Faturamento e EBITDA mensais")
    ax.set_xlabel("Mes")
    ax.set_ylabel("R$ / mes")
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    ax.grid(True, alpha=0.2)
    return _fig_to_png(fig)


def grafico_fcf_acumulado(serie: Sequence[dict], *, payback_meses: float | None = None) -> bytes:
    """Fluxo de caixa acumulado (`serie_mensal[].fcf_acumulado`) com o marco de payback.

    O marco e o `retorno.payback` do payload — o MESMO numero do card. Nao ha recalculo
    do cruzamento aqui: era exatamente essa segunda implementacao que fazia o grafico
    marcar o mes 33 enquanto o KPI dizia 35. Como o payback do nucleo E o primeiro mes com
    `fcf_acumulado >= 0` da MESMA serie plotada, o marco cai na troca de sinal por
    construcao. Payback ausente/infinito (nunca se paga) -> sem linha, so a curva.
    """
    meses = _coluna(serie, "mes")
    fcf = _coluna(serie, "fcf_acumulado")
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), dpi=_DPI)
    ax.fill_between(meses, fcf, color=_TURQUESA, alpha=0.35)
    ax.plot(meses, fcf, color=_TURQUESA, linewidth=1.8)
    ax.axhline(0.0, color=_CINZA, linewidth=0.8)
    marco = _finite(payback_meses)
    if marco is not None:
        ax.axvline(
            marco, color=_MAGENTA, linestyle="--", linewidth=1,
            label=f"Payback (mes {int(marco)})",
        )
        ax.legend(loc="lower right", fontsize=8, frameon=False)
    ax.set_title("Fluxo de caixa acumulado")
    ax.set_xlabel("Mes")
    ax.set_ylabel("R$ acumulado")
    ax.grid(True, alpha=0.2)
    return _fig_to_png(fig)


def grafico_dre_waterfall(
    *,
    faturamento_bruto: float,
    receita_liquida: float,
    receita_pos_impostos: float,
    ebitda: float,
    receita_anuidade: float | None = None,
    mes_referencia: int | None = None,
    ebitda_pct: float | None = None,
) -> bytes:
    """Waterfall do DRE: Fat. bruto -> Deducoes -> Impostos -> Custos op. -> EBITDA.

    ANUIDADE (FIN-VIAB-01): com `receita_anuidade` > 0 a primeira barra entra PARTIDA em
    duas — "Mensalidades" e "Anuidade" —, empilhadas ate o faturamento bruto. Antes a
    anuidade engordava o faturamento sem nenhuma linha explicando de onde vinha. O total
    e a parcela chegam PRONTOS do payload (`dre.faturamento` / `dre.receita_anuidade`);
    a barra de mensalidades e o complemento entre esses dois numeros servidos — o mesmo
    empilhamento de sempre, GEOMETRIA de grafico, nao uma formula financeira nova.
    Sem anuidade (0/None) o grafico volta a ter a barra unica "Fat. bruto".

    `mes_referencia` e o `premissas.mes_referencia_steady` do payload — o mes de operacao
    a que este DRE se refere. NUNCA recalcular a partir de `maturacao_meses`: era esse
    recalculo que fazia o waterfall apontar um mes e o card ao lado, no MESMO slide,
    apontar outro. None -> titulo generico, sem inventar mes.

    `ebitda_pct` e a FRACAO do faturamento bruto ja pronta (montador CANONICO, payload-v1:
    `dre.margem`; montador DEPRECIADO `montar_payload_viabilidade`:
    `viabilidade.margem_ebitda_pct`, o numero de que aquele deriva) e, quando vem
    preenchida, aparece entre parenteses ao lado do R$ na barra do EBITDA — o PDF dizia so
    o valor absoluto enquanto a tela ja mostrava os dois. Os DOIS montadores a passam:
    enquanto so o canonico passava, o MESMO ponto saia com "(38,7%)" por um caminho e sem
    % pelo outro. Segue OPCIONAL para nao quebrar chamador de fora (e para o grafico
    degradar sem inventar numero). Nao ha divisao aqui (FIN-VIAB-01),
    so formatacao; e nenhuma barra nova entra no grafico por causa dela. So a barra de
    EBITDA ganha percentual porque e' a unica linha de RESULTADO da cascata — o resultado
    apos IR nao tem barra aqui, e por isso nao tem parametro: seria kwarg morto.
    """
    fat = float(faturamento_bruto or 0.0)
    r_liq = float(receita_liquida or 0.0)
    r_pos = float(receita_pos_impostos or 0.0)
    eb = float(ebitda or 0.0)
    anuidade = _finite(receita_anuidade) or 0.0

    # Passos (rotulo, base, topo, cor). Receita/EBITDA sao barras cheias (empilhadas a
    # partir do zero); os 3 do meio sao decrementos.
    passos: list[tuple[str, float, float, str]] = []
    if anuidade > 0.0:
        mensalidades = fat - anuidade
        passos.append(("Mensalidades", 0.0, mensalidades, _TURQUESA))
        passos.append(("Anuidade", mensalidades, fat, _TURQUESA_CLARO))
    else:
        passos.append(("Fat. bruto", 0.0, fat, _TURQUESA))
    passos += [
        ("Deducoes", r_liq, fat, _MAGENTA),
        ("Impostos", r_pos, r_liq, _MAGENTA),
        ("Custos op.", eb, r_pos, _MAGENTA),
        ("EBITDA", 0.0, eb, _VERDE),
    ]

    # % do faturamento POR BARRA: so a linha de RESULTADO da cascata (EBITDA) tem
    # percentual, e so quando o payload manda. A busca e pelo rotulo — uma barra de
    # resultado que um dia entre na cascata entra aqui JUNTO com o parametro dela, nao
    # antes: percentual sem barra correspondente e' codigo que nunca executa.
    pct_por_rotulo: dict[str, float | None] = {"EBITDA": _finite(ebitda_pct)}

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), dpi=_DPI)
    topo_max = max(fat, eb, 1.0)
    for i, (rotulo, base, topo, cor) in enumerate(passos):
        altura = topo - base
        ax.bar(i, altura, bottom=base, color=cor, width=0.6)
        # Valor em R$ acima de cada barra, com o % do faturamento quando existir.
        pct = pct_por_rotulo.get(rotulo)
        texto = _brl(altura) if pct is None else f"{_brl(altura)} ({_pct_fracao(pct)})"
        ax.text(
            i, topo + topo_max * 0.015, texto,
            ha="center", va="bottom", fontsize=7, color=_CINZA,
        )
    ax.set_ylim(top=topo_max * 1.14)  # headroom p/ os rotulos R$
    ax.set_xticks(range(len(passos)))
    ax.set_xticklabels([p[0] for p in passos], rotation=20, fontsize=8, ha="right")
    # Titulo/rotulos em ASCII (excecao de RENDER do PNG).
    mes = _finite(mes_referencia)
    titulo = (
        f"DRE do mes {int(mes)} - regime pleno (R$ / mes)"
        if mes is not None
        else "DRE steady-state (R$ / mes)"
    )
    ax.set_title(titulo)
    if anuidade > 0.0:
        ax.set_xlabel("Anuidade: 1x por ano por aluno de balcao, reconhecida pro-rata mensal")
    ax.set_ylabel("R$ / mes")
    ax.grid(True, axis="y", alpha=0.2)
    return _fig_to_png(fig)


# ---------------------------------------------------------------------------
# RENDER PURO: viabilidade_payload_v1 -> dict do slide do PDF (FIN-VIAB-01)
# ---------------------------------------------------------------------------

PAYLOAD_VERSAO = "viabilidade_payload_v1"


def _secao(payload: Mapping[str, Any], nome: str) -> Mapping[str, Any]:
    """Secao do payload como Mapping (ausente/malformada -> vazia, sem quebrar o PDF)."""
    valor = payload.get(nome)
    return valor if isinstance(valor, Mapping) else {}


def _ler(fonte: Any, *caminho: str) -> Any:
    """Le `fonte[a][b][c]` com tolerancia total (chave/secao ausente -> None)."""
    atual = fonte
    for chave in caminho:
        if not isinstance(atual, Mapping):
            return None
        atual = atual.get(chave)
        if atual is None:
            return None
    return atual


def montar_payload_pdf_viabilidade(
    payload: Mapping[str, Any] | None,
    *,
    incluir_graficos: bool = True,
) -> dict[str, Any] | None:
    """`viabilidade_payload_v1` -> dict que `censo_report._viabilidade_page` imprime.

    ESTA e a unica ponte do PDF de viabilidade. Nao chama o motor, nao recalcula KPI e
    nao aplica formula financeira: cada numero impresso e uma LEITURA do payload que a
    API ja devolveu para a tela, entao PDF e tela nao tem como divergir.

    `payload` None/vazio -> None (o chamador passa `viabilidade=None` e o PDF sai
    exatamente como antes, sem as paginas de viabilidade). Secao ausente -> "n/d" no
    card correspondente, sem quebrar o relatorio.
    """
    if not isinstance(payload, Mapping) or not payload:
        return None

    dre = _secao(payload, "dre")
    investimento = _secao(payload, "investimento")
    retorno = _secao(payload, "retorno")
    break_even = _secao(payload, "break_even")
    teto = _secao(payload, "aluguel_teto")
    faixa = _secao(payload, "faixa_alunos")

    # O retorno impresso e o DESALAVANCADO (decisao do dono do produto); a otica de
    # equity nunca divide card com ele.
    retorno_anual = retorno.get("retorno_anual_desalavancado")

    saida: dict[str, Any] = {
        # --- cards (nomes historicos preservados p/ nao mexer no layout do slide) ---
        "alunos_breakeven": break_even.get("ebitda"),
        "breakeven_unidade": break_even.get("unidade"),
        "breakeven_caixa": break_even.get("caixa"),
        # Aluguel-teto = % do faturamento bruto; o canonico e a faixa `teto` (20%), nao a
        # `excecao` (30%) — o card grande mostra o limite que a operacao defende.
        "aluguel_teto": teto.get("canonico"),
        "aluguel_teto_faixas": {
            "base": teto.get("base"),
            "ideal": teto.get("ideal"),
            "teto": teto.get("teto"),
            "excecao": teto.get("excecao"),
        },
        "margem_ebitda_pct": dre.get("margem"),
        "payback_meses": retorno.get("payback"),
        "retorno_anual": retorno_anual,
        "retorno_otica": retorno.get("otica"),
        "roic_anual": retorno_anual,  # alias historico do card
        "faturamento_mensal": dre.get("faturamento"),
        # Anuidade: a linha de receita que antes so aparecia embutida no faturamento.
        # Tudo LEITURA do payload — o slide imprime, nao decompoe nem recalcula.
        "receita_anuidade": dre.get("receita_anuidade"),
        "anuidade_valor": _ler(payload, "premissas", "anuidade_valor"),
        "anuidade_mes_inicio": _ler(payload, "premissas", "anuidade_mes_inicio"),
        "anuidade_apenas_balcao": _ler(payload, "premissas", "anuidade_apenas_balcao"),
        "anuidade_elegivel_pct": _ler(payload, "premissas", "anuidade_elegivel_pct"),
        # Mes de operacao a que a DRE de steady-state se refere (regime pleno). LIDO do
        # payload — recalcular a partir de `maturacao_meses` foi o que fez o waterfall
        # divergir do card ao lado no mesmo slide.
        "mes_referencia_steady": _ler(payload, "premissas", "mes_referencia_steady"),
        "ebitda_mensal": dre.get("ebitda"),
        # Composicao do custo operacional do mes de steady. A FOLHA e a linha que mudou de
        # natureza (decisao de Felipe, 2026-07-24): deixou de ser percentual da receita DO
        # MES e virou custo FIXO, dimensionado pelo faturamento MADURO e pago integralmente
        # desde o mes 1. O slide precisa dizer isso, senao o leitor supoe que a folha
        # encolhe com a rampa — foi exatamente o defeito reportado. Tudo LEITURA do payload.
        "custos_op": dre.get("custos_op"),
        "custos_variaveis": dre.get("custos_variaveis"),
        "folha": dre.get("folha"),
        "custos_fixos": dre.get("custos_fixos"),
        "folha_pct": _ler(payload, "premissas", "folha_pct"),
        "faixa_p10": faixa.get("p10"),
        "faixa_p90": faixa.get("p90"),
        # --- linhas de detalhe (financiamento e indicadores de comite) ---
        "pmt_mensal": investimento.get("pmt"),
        "juros_totais": investimento.get("juros_totais"),
        "investimento_total": investimento.get("investimento_total"),
        # Taxa de franquia e seu PARCELAMENTO sem juros (4x por decisao de Felipe,
        # 2026-07-24; antes saia inteira do caixa no M-4). `parcelas_franquia` e campo NOVO
        # do payload: ausente -> a linha de investimento nao afirma parcelamento nenhum,
        # em vez de assumir um numero que o backend nao mandou.
        "taxa_franquia": investimento.get("taxa_franquia"),
        "parcelas_franquia": investimento.get("parcelas_franquia"),
        "tir_anual": retorno.get("tir_anual"),
        "vpl": retorno.get("vpl"),
        "acumulado_mes_final": payload.get("acumulado_mes_final"),
        "mes_caixa_operacional_positivo": payload.get("mes_caixa_operacional_positivo"),
        "horizonte_meses": _ler(payload, "premissas", "horizonte_meses"),
        "demanda_premissa": payload.get("demanda_premissa"),
        "ticket_blended": _ler(payload, "premissas", "ticket_blended"),
        "flag_fora_envelope": payload.get("flag_fora_envelope"),
        "flag_zona_morta": payload.get("flag_zona_morta"),
        "motivo_zona_morta": payload.get("motivo_zona_morta"),
    }

    if incluir_graficos:
        saida["graficos"] = _graficos_do_payload(payload, dre, retorno)
    return saida


def _graficos_do_payload(
    payload: Mapping[str, Any], dre: Mapping[str, Any], retorno: Mapping[str, Any]
) -> list[bytes]:
    """Os 4 PNGs do slide, todos lidos da MESMA `serie_mensal` / do MESMO DRE do payload."""
    serie = list(payload.get("serie_mensal") or [])
    graficos: list[bytes] = []
    if serie:
        graficos.append(
            grafico_fco(serie, mes_positivo=payload.get("mes_caixa_operacional_positivo"))
        )
        graficos.append(grafico_faturamento_ebitda(serie))
        graficos.append(grafico_fcf_acumulado(serie, payback_meses=retorno.get("payback")))
    if dre:
        fat = _finite(dre.get("faturamento")) or 0.0
        ebitda = _finite(dre.get("ebitda")) or 0.0
        # Niveis intermediarios do waterfall. Sao GEOMETRIA do grafico (empilhamento das
        # proprias linhas do DRE do payload), nao um DRE paralelo: quando o backend manda
        # `receita_liquida`/`receita_pos_impostos` prontos, sao eles que valem — e hoje
        # ele SEMPRE manda. As subtracoes abaixo so existem para payload legado.
        r_liq = _finite(dre.get("receita_liquida"))
        if r_liq is None:
            r_liq = fat - (_finite(dre.get("deducoes")) or 0.0)
        r_pos = _finite(dre.get("receita_pos_impostos"))
        if r_pos is None:
            r_pos = r_liq - (_finite(dre.get("impostos")) or 0.0)
        graficos.append(
            grafico_dre_waterfall(
                faturamento_bruto=fat,
                receita_liquida=r_liq,
                receita_pos_impostos=r_pos,
                ebitda=ebitda,
                # A anuidade vira barra propria; o mes de referencia e LIDO de
                # `premissas.mes_referencia_steady` (nunca de `maturacao_meses`), o
                # mesmo numero que o card ao lado imprime.
                receita_anuidade=dre.get("receita_anuidade"),
                mes_referencia=_ler(payload, "premissas", "mes_referencia_steady"),
                # % do faturamento da barra de EBITDA, servido pronto: e' `margem` (o
                # motor define `margem_ebitda_pct = ebitda / faturamento`) — nao ha
                # campo `ebitda_pct_faturamento`, servir os dois deixava duas rotas
                # para o mesmo numero, livres para divergir. O percentual do resultado
                # apos IR NAO vem para ca: a cascata termina no EBITDA e nao ha barra
                # onde imprimi-lo (a TELA o consome, do mesmo payload).
                ebitda_pct=dre.get("margem"),
            )
        )
    return graficos


def montar_payload_viabilidade(
    viab_result: Any,
    serie: Sequence[dict] | None = None,
    *,
    incluir_graficos: bool = True,
    maturacao_mes: int | None = None,
    fco_serie: Sequence[dict] | None = None,
    mes_operacao_positiva: int | None = None,
) -> dict[str, Any]:
    """DEPRECATED (FIN-VIAB-01) — ponte engine -> dict do slide (BLK-RELVIAB-05).

    Caminho NOVO e canonico: `montar_payload_pdf_viabilidade(viabilidade_payload_v1)`.
    Esta versao le um objeto do motor e por isso convive com KPIs recalculados fora do
    simulador (foi por aqui que payback e aluguel-teto do PDF divergiram da tela).
    Mantida so para o dashboard Streamlit legado e para a suite historica.

    Le um `ViabilidadePontoResult` (via duck typing — sem import do dataclass) e monta o dict
    que `_viabilidade_page` consome (numeros + `graficos`). Com `serie` (saida de
    `gerar_serie_mensal`) inclui os 3 graficos temporais + o waterfall; sem serie, so o
    waterfall. READ-ONLY sobre o M1 (apenas LE o resultado do motor).
    """
    v = viab_result.viabilidade
    payload: dict[str, Any] = {
        "alunos_breakeven": viab_result.alunos_breakeven,
        "aluguel_teto": viab_result.aluguel_teto_calculado,
        "margem_ebitda_pct": v.margem_ebitda_pct,
        "payback_meses": v.payback_meses,
        "roic_anual": v.roic_anual,
        "faturamento_mensal": v.faturamento_mensal_steady,
        "ebitda_mensal": v.ebitda_mensal,
        "faixa_p10": viab_result.faixa_alunos_p10,
        "faixa_p90": viab_result.faixa_alunos_p90,
        "flag_viavel": v.flag_viavel,
        "flag_fora_envelope": viab_result.flag_fora_envelope,
    }
    if incluir_graficos:
        graficos: list[bytes] = []
        if serie:
            # 1o grafico: Fluxo de Caixa Operacional (substitui a "rampa de alunos" —
            # item Felipe 2026-07-23). Cai no waterfall-only se o backend nao mandar a
            # serie de FCO (retrocompat com chamadores que so passam `serie`).
            if fco_serie:
                graficos.append(
                    grafico_fco(fco_serie, mes_positivo=mes_operacao_positiva)
                )
            graficos.append(grafico_faturamento_ebitda(serie))
            graficos.append(grafico_fcf_acumulado(serie, payback_meses=v.payback_meses))
        graficos.append(
            grafico_dre_waterfall(
                faturamento_bruto=v.faturamento_mensal_steady,
                receita_liquida=v.receita_liquida,
                receita_pos_impostos=v.receita_pos_impostos,
                ebitda=v.ebitda_mensal,
                # MESMO numero que o montador canonico estampa: la o backend serve
                # `dre.margem`, que e' este `margem_ebitda_pct` arredondado. Sem isto o
                # MESMO ponto saia com "(38,7%)" pelo caminho canonico e sem % por este,
                # o depreciado. Ja esta a mao (linha `margem_ebitda_pct` do payload logo
                # acima) — nao ha divisao nova aqui, o modulo nao faz aritmetica financeira.
                ebitda_pct=v.margem_ebitda_pct,
            )
        )
        payload["graficos"] = graficos
    return payload
