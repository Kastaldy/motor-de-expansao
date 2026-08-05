"""Primitivas de PDF 16:9 compartilhadas pelos relatorios Ultra - BLK-EXEC-11.

O `_UltraPDF` era **byte-identico** em `censo_report.py` e `relatorio_municipal.py`. Este
modulo o extrai para que o terceiro gerador (a Visao Executiva) nao vire a terceira copia.

**Os dois legados NAO sao reapontados neste epic**, de proposito: sao geradores em producao
com testes de regressao de bytes, e refatora-los nao entrega nada ao usuario. O que impede a
duplicacao de virar triplicacao e' o teste `test_ultra_pdf_config_identica`, que compara a
configuracao das tres classes.

Armadilha do latin-1: o fpdf2 com core font Helvetica cobre integralmente os acentos
portugueses, mas troca por "?" em SILENCIO qualquer caractere fora de latin-1 -- travessao,
bullet, seta, reticencias unicode, aspas curvas, sinal de menos U+2212. `ascii_seguro`
existe para deixar isso explicito no ponto de uso.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

from fpdf import FPDF

#: Slide 16:9 widescreen, em pontos.
PAGINA_LARGURA = 960.0
PAGINA_ALTURA = 540.0

ULTRA_TURQUESA = (0, 167, 157)
ULTRA_MAGENTA = (194, 60, 142)
BRANCO = (255, 255, 255)
CINZA_TEXTO = (60, 60, 60)
CINZA_CLARO = (238, 238, 238)
CINZA_LINHA = (208, 208, 208)

#: Semaforo do diagnostico. Cores impressas, nao as da tela (fundo branco no PDF).
COR_SEVERIDADE: dict[str, tuple[int, int, int]] = {
    "alta": (198, 40, 40),
    "media": (214, 137, 16),
    "ok": (46, 125, 50),
    "sem_base": (120, 120, 120),
}


class UltraPDF(FPDF):
    """FPDF 16:9 com compressao desativada (auditabilidade + asserts de texto cru)."""

    def __init__(self) -> None:
        # format=(540,960)+orientation=L -> w=960, h=540.
        super().__init__(orientation="L", unit="pt", format=(540, 960))
        # PDF 1.4 para continuidade com os asserts historicos (%PDF-1.4) e leitores antigos.
        self.pdf_version = "1.4"
        self.set_compression(False)
        self.set_auto_page_break(False)
        self.set_margins(0, 0, 0)


def ascii_seguro(texto: object) -> str:
    """Reduz a latin-1 seguro para o core font Helvetica do fpdf2."""
    return str(texto).encode("latin-1", errors="replace").decode("latin-1")


def faixa_de_titulo(
    pdf: UltraPDF,
    titulo: str,
    subtitulo: str = "",
    *,
    rgb: tuple[int, int, int] = ULTRA_TURQUESA,
) -> None:
    """Faixa de titulo no topo da pagina, largura total."""
    altura = 56.0
    pdf.set_fill_color(*rgb)
    pdf.rect(0, 0, PAGINA_LARGURA, altura, style="F")
    pdf.set_text_color(*BRANCO)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_xy(36, 14)
    pdf.cell(PAGINA_LARGURA - 380, 24, ascii_seguro(titulo))
    if subtitulo:
        pdf.set_font("Helvetica", "", 11)
        pdf.set_xy(PAGINA_LARGURA - 360, 22)
        pdf.cell(324, 14, ascii_seguro(subtitulo), align="R")


def rodape(pdf: UltraPDF, texto: str) -> None:
    """Rodape discreto com fonte e metodo -- e' onde a regua vigente e' impressa."""
    pdf.set_text_color(140, 140, 140)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_xy(36, PAGINA_ALTURA - 26)
    pdf.cell(PAGINA_LARGURA - 72, 10, ascii_seguro(texto))


def cartao(
    pdf: UltraPDF,
    x: float,
    y: float,
    largura: float,
    altura: float,
    *,
    rotulo: str,
    valor: str,
    apoio: str = "",
    cor: tuple[int, int, int] = CINZA_TEXTO,
) -> None:
    """Cartao de KPI: rotulo pequeno em cima, numero grande, apoio embaixo."""
    pdf.set_fill_color(*CINZA_CLARO)
    pdf.rect(x, y, largura, altura, style="F")
    pdf.set_text_color(110, 110, 110)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(x + 10, y + 8)
    pdf.cell(largura - 20, 11, ascii_seguro(rotulo))
    pdf.set_text_color(*cor)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_xy(x + 10, y + 22)
    pdf.cell(largura - 20, 22, ascii_seguro(valor))
    if apoio:
        pdf.set_text_color(120, 120, 120)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_xy(x + 10, y + altura - 18)
        pdf.cell(largura - 20, 10, ascii_seguro(apoio))


def linha_de_tabela(
    pdf: UltraPDF,
    x: float,
    y: float,
    colunas: list[tuple[float, str, str]],
    *,
    altura: float = 16.0,
    negrito: bool = False,
    cor: tuple[int, int, int] = CINZA_TEXTO,
    fundo: tuple[int, int, int] | None = None,
) -> None:
    """Uma linha de tabela. `colunas` = (largura, texto, alinhamento)."""
    if fundo is not None:
        largura_total = sum(c[0] for c in colunas)
        pdf.set_fill_color(*fundo)
        pdf.rect(x, y, largura_total, altura, style="F")
    pdf.set_text_color(*cor)
    pdf.set_font("Helvetica", "B" if negrito else "", 8.5)
    cursor = x
    for largura, texto, alinhamento in colunas:
        pdf.set_xy(cursor + 3, y + 3)
        pdf.cell(largura - 6, altura - 6, ascii_seguro(texto), align=alinhamento)
        cursor += largura


# ---------------------------------------------------------------------------
# Graficos
#
# Desenhados com as primitivas do proprio fpdf (rect/line/ellipse), nao com matplotlib:
# sao quatro formas simples, saem VETORIAIS (o PDF e' lido em tela cheia numa reuniao) e o
# gerador continua sem processar imagem dentro de uma rota HTTP.
#
# Regra que vale para todos, a mesma da tela: a base da escala e' ZERO. Comecar no minimo
# da serie faz uma variacao de 2% parecer queda pela metade -- e' o defeito da escala
# congelada da planilha que o time usa hoje.
# ---------------------------------------------------------------------------


def _finitos(valores: Sequence[float | None]) -> list[float]:
    return [float(v) for v in valores if v is not None and math.isfinite(float(v))]


def _milhar(valor: float) -> str:
    """Separador de milhar em pt-BR, sem casas."""
    return f"{valor:,.0f}".replace(",", ".")


def titulo_de_grafico(
    pdf: UltraPDF, x: float, y: float, texto: str, apoio: str = "", largura: float = 340.0
) -> None:
    """Titulo + apoio de um bloco. `largura` LIMITA o texto ao bloco.

    Sem o limite, o `cell` de largura fixa escrevia por cima do bloco vizinho: a frase de
    apoio da composicao da base atravessava a pagina e caia em cima do texto do NPS.
    """
    pdf.set_text_color(90, 90, 90)
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.set_xy(x, y)
    pdf.cell(largura, 11, ascii_seguro(texto))
    if apoio:
        pdf.set_text_color(140, 140, 140)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_xy(x, y + 11)
        # `multi_cell` quebra a linha DENTRO do bloco em vez de transbordar para o lado.
        pdf.multi_cell(largura, 9, ascii_seguro(apoio), align="L")


def barras(
    pdf: UltraPDF,
    x: float,
    y: float,
    largura: float,
    altura: float,
    rotulos: Sequence[str],
    valores: Sequence[float | None],
    *,
    cor: tuple[int, int, int] = ULTRA_TURQUESA,
    formatar: Callable[[float], str] = _milhar,
) -> None:
    """Barras verticais com base em zero, eixo e o maximo anotado."""
    if not rotulos:
        return
    finitos = _finitos(valores)
    maximo = max(finitos) if finitos else 0.0
    passo = largura / max(len(rotulos), 1)
    largura_barra = min(passo * 0.66, 24.0)

    pdf.set_draw_color(*CINZA_LINHA)
    pdf.set_line_width(0.5)
    pdf.line(x, y + altura, x + largura, y + altura)

    for indice, rotulo in enumerate(rotulos):
        valor = valores[indice] if indice < len(valores) else None
        centro = x + passo * indice + passo / 2
        if valor is not None and maximo > 0:
            alto = max(altura * float(valor) / maximo, 0.8)
            ultimo = indice == len(rotulos) - 1
            pdf.set_fill_color(*(cor if ultimo else _clarear(cor, 0.45)))
            pdf.rect(centro - largura_barra / 2, y + altura - alto, largura_barra, alto, style="F")
            # O VALOR vai sobre a barra. Comparar alturas responde "subiu ou caiu"; so o
            # numero responde "quanto" -- e e' o numero que vai para a conversa com o
            # franqueado, que le o PDF sem a tela ao lado.
            pdf.set_text_color(*CINZA_TEXTO)
            pdf.set_font("Helvetica", "B", 6.2)
            pdf.set_xy(centro - passo / 2, y + altura - alto - 9)
            pdf.cell(passo, 8, ascii_seguro(formatar(float(valor))), align="C")
        pdf.set_text_color(150, 150, 150)
        pdf.set_font("Helvetica", "", 6.5)
        pdf.set_xy(centro - passo / 2, y + altura + 3)
        pdf.cell(passo, 8, ascii_seguro(rotulo), align="C")


def linha(
    pdf: UltraPDF,
    x: float,
    y: float,
    largura: float,
    altura: float,
    valores: Sequence[float | None],
    *,
    cor: tuple[int, int, int] = ULTRA_TURQUESA,
    formatar: Callable[[float], str] = _milhar,
    base_zero: bool = True,
) -> None:
    """Polilinha simples, com o minimo e o maximo anotados. Buraco na serie corta a linha."""
    finitos = _finitos(valores)
    if len(finitos) < 2:
        return
    maximo = max(finitos)
    minimo = 0.0 if (base_zero and min(finitos) >= 0) else min(finitos)
    amplitude = (maximo - minimo) or 1.0
    passo = largura / max(len(valores) - 1, 1)

    pdf.set_draw_color(*CINZA_LINHA)
    pdf.set_line_width(0.5)
    pdf.line(x, y + altura, x + largura, y + altura)

    pdf.set_draw_color(*cor)
    pdf.set_line_width(1.4)
    pontos: list[tuple[int, float, float, float]] = []
    anterior: tuple[float, float] | None = None
    for indice, valor in enumerate(valores):
        if valor is None or not math.isfinite(float(valor)):
            anterior = None
            continue
        ponto = (x + passo * indice, y + altura - altura * (float(valor) - minimo) / amplitude)
        pontos.append((indice, ponto[0], ponto[1], float(valor)))
        if anterior is not None:
            pdf.line(anterior[0], anterior[1], ponto[0], ponto[1])
        anterior = ponto
    if anterior is not None:
        pdf.set_fill_color(*cor)
        pdf.ellipse(anterior[0] - 2, anterior[1] - 2, 4, 4, style="F")

    # Valor MES A MES, nao so o minimo e o maximo: sem isso nao ha como ler nenhum ponto
    # do meio da serie num papel -- e no PDF nao existe passar o mouse por cima.
    # Com muitos pontos os rotulos se encavalariam, entao alterna.
    alternar = len(pontos) > 7
    pdf.set_text_color(*CINZA_TEXTO)
    pdf.set_font("Helvetica", "B", 5.8)
    for indice, px, py, valor in pontos:
        if alternar and indice % 2 == 1 and indice != pontos[-1][0]:
            continue
        pdf.set_xy(px - passo / 2, max(py - 9.5, y - 10))
        pdf.cell(max(passo, 22.0), 8, ascii_seguro(formatar(valor)), align="C")


def barras_horizontais(
    pdf: UltraPDF,
    x: float,
    y: float,
    largura: float,
    etapas: Sequence[tuple[str, float | None, tuple[int, int, int]]],
    *,
    altura_linha: float = 15.0,
) -> None:
    """Funil: rotulo a esquerda, barra proporcional ao MAIOR degrau, valor a direita.

    Nao normaliza pelo primeiro degrau de proposito: na base real `vendas > convertidos`
    em 75% das linhas, e forcar o funil a afunilar esconderia um problema de coleta.
    """
    valores = _finitos([v for _, v, _ in etapas])
    maximo = max(valores) if valores else 0.0
    rotulo_largura, valor_largura = 92.0, 52.0
    barra_largura = largura - rotulo_largura - valor_largura

    for indice, (rotulo, valor, cor) in enumerate(etapas):
        topo = y + indice * altura_linha
        pdf.set_text_color(110, 110, 110)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_xy(x, topo + 2)
        pdf.cell(rotulo_largura, 10, ascii_seguro(rotulo))

        pdf.set_fill_color(*CINZA_CLARO)
        pdf.rect(x + rotulo_largura, topo + 3, barra_largura, 8, style="F")
        if valor is not None and maximo > 0:
            pdf.set_fill_color(*cor)
            pdf.rect(x + rotulo_largura, topo + 3, barra_largura * float(valor) / maximo, 8, style="F")

        pdf.set_text_color(*CINZA_TEXTO)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_xy(x + rotulo_largura + barra_largura + 4, topo + 2)
        pdf.cell(valor_largura - 8, 10, "-" if valor is None else _milhar(valor), align="R")


def faixa_de_percentil(
    pdf: UltraPDF,
    x: float,
    y: float,
    largura: float,
    *,
    p25: float | None,
    p50: float | None,
    p75: float | None,
    unidade: float | None,
) -> None:
    """Onde a unidade cai entre os pares: caixa p25-p75, tracinho da mediana, marca dela."""
    pontos = _finitos([p25, p50, p75, unidade])
    if not pontos or unidade is None:
        return
    minimo, maximo = min(0.0, min(pontos)), max(pontos)
    amplitude = (maximo - minimo) or 1.0

    def posicao(valor: float | None) -> float | None:
        return None if valor is None else x + largura * (float(valor) - minimo) / amplitude

    pdf.set_fill_color(*CINZA_CLARO)
    pdf.rect(x, y + 3, largura, 6, style="F")
    esquerda, direita = posicao(p25), posicao(p75)
    if esquerda is not None and direita is not None:
        pdf.set_fill_color(190, 190, 190)
        pdf.rect(esquerda, y + 3, max(direita - esquerda, 0.6), 6, style="F")
    mediana = posicao(p50)
    if mediana is not None:
        pdf.set_fill_color(110, 110, 110)
        pdf.rect(mediana - 0.6, y + 1, 1.2, 10, style="F")
    marca = posicao(unidade)
    if marca is not None:
        pdf.set_fill_color(*ULTRA_TURQUESA)
        pdf.rect(marca - 2, y, 4, 12, style="F")


def barra_de_meta(
    pdf: UltraPDF,
    x: float,
    y: float,
    largura: float,
    *,
    valor: float | None,
    meta: float,
    minimo: float = -100.0,
    maximo: float = 100.0,
) -> None:
    """Regua com a meta marcada. Verde quando bate a meta, turquesa quando nao."""

    def posicao(v: float) -> float:
        return x + largura * min(max((v - minimo) / (maximo - minimo), 0.0), 1.0)

    pdf.set_fill_color(*CINZA_CLARO)
    pdf.rect(x, y, largura, 8, style="F")
    if valor is not None:
        pdf.set_fill_color(*(COR_SEVERIDADE["ok"] if valor >= meta else ULTRA_TURQUESA))
        pdf.rect(x, y, max(posicao(valor) - x, 0.6), 8, style="F")
    pdf.set_fill_color(80, 80, 80)
    pdf.rect(posicao(meta) - 0.6, y - 2, 1.2, 12, style="F")


def barra_empilhada(
    pdf: UltraPDF,
    x: float,
    y: float,
    largura: float,
    altura: float,
    partes: Sequence[tuple[float, tuple[int, int, int]]],
) -> None:
    """Barra segmentada (semaforo da rede, recorrentes x agregadores)."""
    total = sum(max(v, 0.0) for v, _ in partes) or 1.0
    cursor = x
    for valor, cor in partes:
        fatia = largura * max(valor, 0.0) / total
        if fatia <= 0:
            continue
        pdf.set_fill_color(*cor)
        pdf.rect(cursor, y, fatia, altura, style="F")
        cursor += fatia


def _clarear(cor: tuple[int, int, int], fator: float) -> tuple[int, int, int]:
    """Mistura com branco -- distingue os meses anteriores do mes mais recente."""
    return (
        int(cor[0] + (255 - cor[0]) * fator),
        int(cor[1] + (255 - cor[1]) * fator),
        int(cor[2] + (255 - cor[2]) * fator),
    )


def rosca(
    pdf: UltraPDF,
    x: float,
    y: float,
    diametro: float,
    partes: Sequence[tuple[str, float, tuple[int, int, int]]],
    *,
    espessura: float = 16.0,
    centro_valor: str = "",
    centro_rotulo: str = "",
    legenda_abaixo: bool = False,
) -> None:
    """Rosca de duas ou tres fatias, com o numero no miolo e a legenda a direita.

    Desenhada com `solid_arc` (fpdf2) e um circulo branco por cima para abrir o furo --
    e' o caminho que mantem tudo VETORIAL. A fatia responde "muito ou pouco"; so o numero
    responde "quanto", e por isso ele fica no meio.
    """
    total = sum(max(v, 0.0) for _, v, _ in partes)
    raio = diametro / 2
    centro_x, centro_y = x + raio, y + raio

    positivas = [(rotulo, valor, cor) for rotulo, valor, cor in partes if valor > 0]
    if total <= 0:
        pdf.set_fill_color(*CINZA_CLARO)
        pdf.ellipse(x, y, diametro, diametro, style="F")
    elif len(positivas) == 1:
        # Uma fatia so' = circulo inteiro. `solid_arc` de 0 a 360 graus nao fecha a volta
        # e sai como um setor mordido -- foi assim que uma unidade sem nenhum agregador
        # apareceu com a rosca quebrada, mostrando 100% como se fosse ~85%.
        pdf.set_fill_color(*positivas[0][2])
        pdf.ellipse(x, y, diametro, diametro, style="F")
    else:
        angulo = -90.0  # comeca no topo, que e' onde o olho comeca
        for _, valor, cor in positivas:
            fatia = 360.0 * max(valor, 0.0) / total
            pdf.set_fill_color(*cor)
            pdf.set_draw_color(*cor)
            # `a`/`b` do fpdf2 sao o DIAMETRO do bounding box, nao o semi-eixo, e
            # `x`/`y` sao o canto superior esquerdo desse box. Passar o raio desenhava o
            # anel com metade do tamanho e deslocado do furo -- a rosca saia torta.
            pdf.solid_arc(
                x=x,
                y=y,
                a=diametro,
                b=diametro,
                start_angle=angulo,
                end_angle=angulo + fatia,
                style="F",
            )
            angulo += fatia

    # Furo: um circulo da cor do papel por cima do miolo.
    pdf.set_fill_color(*BRANCO)
    furo = diametro - 2 * espessura
    pdf.ellipse(centro_x - furo / 2, centro_y - furo / 2, furo, furo, style="F")

    if centro_valor:
        pdf.set_text_color(*CINZA_TEXTO)
        pdf.set_font("Helvetica", "B", 15)
        pdf.set_xy(centro_x - raio, centro_y - 10)
        pdf.cell(diametro, 14, ascii_seguro(centro_valor), align="C")
    if centro_rotulo:
        pdf.set_text_color(140, 140, 140)
        pdf.set_font("Helvetica", "", 6.5)
        pdf.set_xy(centro_x - raio, centro_y + 4)
        pdf.cell(diametro, 8, ascii_seguro(centro_rotulo), align="C")

    legenda_x = x if legenda_abaixo else x + diametro + 14
    legenda_y = (y + diametro + 8) if legenda_abaixo else (y + 6)
    for rotulo, valor, cor in partes:
        pdf.set_fill_color(*cor)
        pdf.rect(legenda_x, legenda_y + 2, 8, 8, style="F")
        pdf.set_text_color(110, 110, 110)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_xy(legenda_x + 12, legenda_y)
        pdf.cell(78, 11, ascii_seguro(rotulo))
        pdf.set_text_color(*CINZA_TEXTO)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_xy(legenda_x + 92, legenda_y)
        fracao = f" ({100.0 * valor / total:.0f}%)" if total > 0 else ""
        pdf.cell(92, 11, ascii_seguro(_milhar(valor) + fracao))
        legenda_y += 15.0
