"""Deck de comparacao: 2 a 5 hexagonos (ou pontos) em 6 slides.

POR QUE ESTE MODULO SO' DESENHA. A regra de comparacao — quais dimensoes entram, o que e'
"melhor", quais diferencas sao relevantes e quem lidera — ja' existe em `web/src/lib/`
(`comparacao.ts` e `ranking-comparacao.ts`) e e' o que a TELA mostra. Reimplementa-la aqui
em Python criaria duas fontes da verdade para a mesma pergunta, e elas divergiriam no
primeiro ajuste de limiar: o relatorio afirmaria um vencedor e o piloto, outro, sobre os
mesmos hexagonos. Entao o front manda o ranking JA CALCULADO e este modulo so' o desenha.

O contrato de entrada e' o `RankingComparacao` do TypeScript, em dict. Nada e' derivado
aqui: nem media, nem nota, nem desempate.

SEM SCORE NOVO. O ranking e' CONTAGEM de vitorias por parametro (decisao do Juan,
2026-08-13). Somar parametros numa nota unica seria peso entre camadas do M1, que so' muda
por DEC — e por isso o slide 5 mostra "lidera em N de M" e nomeia QUAIS, em vez de um
numero geral que ninguem aprovou.

ACENTUACAO: texto de usuario vai acentuado (CLAUDE.md secao 2), mas a PONTUACAO fica em
ASCII. O core font Helvetica do fpdf2 escreve latin-1; travessao, bullet, seta e reticencias
caem fora dele e viram "?" em silencio.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

from motor_expansao.dashboard.pdf_base import (
    BRANCO,
    CINZA_CLARO,
    CINZA_LINHA,
    CINZA_TEXTO,
    PAGINA_ALTURA,
    PAGINA_LARGURA,
    ULTRA_MAGENTA,
    ULTRA_TURQUESA,
    UltraPDF,
    ascii_seguro,
    faixa_de_titulo,
    linha_de_tabela,
    rodape,
)

#: Teto de itens no deck. O mesmo `MAX_COMPARADOS` da tela e o mesmo tamanho da paleta de
#: identidade: acima disso duas colunas repetiriam cor e o slide deixaria de distinguir.
MAX_ITENS = 5

#: A paleta de identidade do piloto (`CORES_IDENTIDADE` em `web/src/lib/comparacao.ts`).
#: Repetida aqui como CONSTANTE, e nao importada: sao dois runtimes. O teste
#: `test_relatorio_comparacao.py` trava as duas listas juntas — se a tela mudar de cor e o
#: PDF nao, o relatorio deixa de casar com a tela de onde ele saiu.
CORES_ITEM: tuple[tuple[int, int, int], ...] = (
    (0x4F, 0xA3, 0xF7),
    (0xF2, 0xA7, 0x3B),
    (0x9B, 0x7B, 0xF0),
    (0x2F, 0xBF, 0x9E),
    (0xE8, 0x61, 0x8C),
)

_ASSET_CAPA = "relatorio_capa_bg.png"
_ASSET_CONTEUDO = "relatorio_conteudo_bg.png"

# --- Geometria da CAPA -------------------------------------------------------------------
# A arte da capa NAO e' fundo chapado: tem foto a esquerda, o logo GRUPO ULTRA no meio-direita
# e uma faixa de logos de marcas no rodape, tudo desenhado em BRANCO. Texto branco por cima
# some ou risca o logo — na primeira pagina de um PDF que vai para terceiros.
#
# Estes numeros NAO sao chute: vieram da varredura de pixel do proprio asset registrada em
# `censo_report.py` (2026-08-03). A unica area limpa e larga e' a coluna `x >= 460` entre
# `y = 300` e `y = 450`; abaixo de 461,4 comeca a faixa de logos. Escrevi a primeira versao
# ignorando isso e o titulo saiu atravessado no logo.
_CAPA_X = 478.0
_CAPA_LARGURA = PAGINA_LARGURA - _CAPA_X - 36.0
_CAPA_RODAPE_LOGOS_TOP = 461.4

_MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def cor_do_item(i: int) -> tuple[int, int, int]:
    """Cor de identidade da posicao `i`, ciclando como a tela faz."""
    return CORES_ITEM[i % len(CORES_ITEM)]


def _milhar(v: float) -> str:
    """Inteiro em pt-BR. O separador e' ponto, como no resto dos relatorios."""
    return f"{v:,.0f}".replace(",", ".")


def _valor_com_unidade(valor: float | None, unidade: str) -> str:
    """O numero na unidade da dimensao. Ausente vira '-', nunca zero.

    Zero e' uma AFIRMACAO ("nao ha") e ausencia nao afirma — a mesma regra da ficha do
    piloto, e a razao de o traco existir aqui.
    """
    if valor is None:
        return "-"
    if unidade == "R$":
        return f"R$ {_milhar(valor)}"
    if unidade == "%":
        return f"{valor:.1f}".replace(".", ",") + "%"
    if unidade == "score":
        return f"{valor:.1f}".replace(".", ",")
    return _milhar(valor)


def _assets(ultra_dir: Path | str | None) -> dict[str, bytes | None]:
    """Arte de capa e de conteudo. Ausencia NAO quebra o relatorio: cai no fundo chapado."""
    saida: dict[str, bytes | None] = {"capa": None, "conteudo": None}
    if ultra_dir is None:
        return saida
    base = Path(ultra_dir)
    for chave, nome in (("capa", _ASSET_CAPA), ("conteudo", _ASSET_CONTEUDO)):
        try:
            saida[chave] = (base / nome).read_bytes()
        except Exception:  # noqa: BLE001 - arte ausente e' degradacao prevista
            saida[chave] = None
    return saida


def _fundo(pdf: UltraPDF, arte: bytes | None, *, cor: tuple[int, int, int]) -> None:
    if arte is not None:
        try:
            pdf.image(BytesIO(arte), x=0, y=0, w=PAGINA_LARGURA, h=PAGINA_ALTURA)
            return
        except Exception:  # noqa: BLE001 - arte corrompida cai no chapado
            pass
    pdf.set_fill_color(*cor)
    pdf.rect(0, 0, PAGINA_LARGURA, PAGINA_ALTURA, style="F")


def _data_por_extenso(quando: date) -> str:
    return f"{quando.day} de {_MESES[quando.month - 1]} de {quando.year}"


def _corpo_que_cabe(pdf: UltraPDF, texto: str, largura: float, tentativas: Sequence[float]) -> float:
    """O maior corpo da lista em que `texto` ainda cabe em `largura`.

    `cell` do fpdf2 nao quebra nem avisa: o texto sai pela margem e some. Na capa isso
    apagaria o titulo do relatorio sem erro nenhum.
    """
    limpo = ascii_seguro(texto)
    for corpo in tentativas:
        pdf.set_font("Helvetica", "B", corpo)
        if pdf.get_string_width(limpo) <= largura:
            return corpo
    return tentativas[-1]


def _altura_que_preenche(
    espaco: float, n: int, *, minimo: float, maximo: float, respiro: float = 0.0
) -> float:
    """Altura de linha que OCUPA o slide em vez de amontoar tudo no topo.

    Com 3 itens num layout dimensionado para 5, a primeira versao deixava metade da pagina
    vazia — num deck de reuniao isso le como slide inacabado. A altura cresce ate' o teto
    quando sobra espaco e encolhe ate' o piso quando falta.
    """
    if n <= 0:
        return minimo
    bruta = (espaco - respiro * max(n - 1, 0)) / n
    return max(minimo, min(maximo, bruta))


# ===========================================================================
# Slide 1 - Capa
# ===========================================================================


def _slide_capa(pdf: UltraPDF, dados: Mapping[str, Any], arte: bytes | None, quando: date) -> None:
    pdf.add_page()
    _fundo(pdf, arte, cor=ULTRA_TURQUESA)

    titulo = str(dados.get("titulo") or "Comparação de áreas")
    subtitulo = str(dados.get("subtitulo") or "")
    itens = list(dados.get("itens") or [])[:MAX_ITENS]

    # TUDO na coluna limpa (ver a nota de geometria no topo do modulo). O titulo encolhe
    # ate' caber: a coluna tem 446 pt e "Comparação de hexágonos" nao cabe em 40 pt.
    corpo = _corpo_que_cabe(pdf, titulo, _CAPA_LARGURA, (30.0, 26.0, 23.0, 20.0, 17.0))
    pdf.set_text_color(*BRANCO)
    pdf.set_font("Helvetica", "B", corpo)
    pdf.set_xy(_CAPA_X, 300)
    pdf.cell(_CAPA_LARGURA, corpo + 6, ascii_seguro(titulo))

    if subtitulo:
        # A data entra AQUI, e nao numa linha propria no rodape: abaixo de 461,4 pt comeca
        # a faixa de logos, e a linha de credito riscava o logo da Ultra.
        linha = f"{subtitulo} | {_data_por_extenso(quando)}"
        pdf.set_font("Helvetica", "", 11)
        pdf.set_xy(_CAPA_X, 300 + corpo + 10)
        pdf.cell(_CAPA_LARGURA, 15, ascii_seguro(linha))

    # Os itens comparados JA NA CAPA, cada um na sua cor: quem recebe o PDF sem ter estado
    # na tela precisa saber o que esta' sendo comparado antes de virar a pagina.
    y = 300 + corpo + 34
    passo = 17.0
    # Piso rigido: a lista para antes da faixa de logos, custe o que custar.
    cabem = max(int((_CAPA_RODAPE_LOGOS_TOP - 6 - y) / passo), 0)
    for i, item in enumerate(itens[:cabem]):
        pdf.set_fill_color(*cor_do_item(i))
        pdf.rect(_CAPA_X, y + 3, 8, 8, style="F")
        pdf.set_text_color(*BRANCO)
        pdf.set_font("Helvetica", "", 10.5)
        pdf.set_xy(_CAPA_X + 14, y)
        pdf.cell(_CAPA_LARGURA - 14, 14, ascii_seguro(str(item.get("rotulo") or f"Área {i + 1}")))
        y += passo

    if cabem < len(itens):
        pdf.set_font("Helvetica", "", 9)
        pdf.set_xy(_CAPA_X + 14, y)
        pdf.cell(_CAPA_LARGURA - 14, 12, ascii_seguro(f"e mais {len(itens) - cabem}"))


# ===========================================================================
# Slide 2 - Graficos de comparacao
# ===========================================================================


def _slide_graficos(pdf: UltraPDF, dados: Mapping[str, Any], arte: bytes | None) -> None:
    pdf.add_page()
    _fundo(pdf, arte, cor=BRANCO)
    faixa_de_titulo(pdf, "Comparação por parâmetro", str(dados.get("subtitulo") or ""))

    itens = list(dados.get("itens") or [])[:MAX_ITENS]
    if not itens:
        return
    dimensoes = list(itens[0].get("porDimensao") or [])
    decisivas = set(dados.get("dimensoesDecisivas") or [])

    # LEGENDA no topo. Sem ela as barras só se distinguem pela cor, e o leitor teria de
    # voltar à capa para saber qual é qual — num PDF que circula impresso, isso é o
    # bastante para o slide não ser lido.
    lx = 36.0
    pdf.set_font("Helvetica", "", 9)
    for i, item in enumerate(itens):
        rotulo = ascii_seguro(str(item.get("rotulo") or f"Área {i + 1}"))
        pdf.set_fill_color(*cor_do_item(i))
        pdf.rect(lx, 71, 8, 8, style="F")
        pdf.set_text_color(90, 90, 90)
        pdf.set_xy(lx + 12, 68)
        largura_texto = pdf.get_string_width(rotulo)
        pdf.cell(largura_texto + 4, 14, rotulo)
        lx += 12 + largura_texto + 22

    # GRADE que se ajusta ao numero de parametros, nao ao de itens: sao as barras DENTRO de
    # cada mini-grafico que crescem de 2 para 5. O slide nao muda de forma.
    colunas = 3
    largura_bloco = (PAGINA_LARGURA - 72 - (colunas - 1) * 18) / colunas
    linhas = (len(dimensoes[:6]) + colunas - 1) // colunas
    topo = 96.0
    # Blocos ocupam a altura util: com 5 parametros em 2 linhas, a altura fixa deixava um
    # terco do slide vazio.
    altura_bloco = _altura_que_preenche(474.0 - topo, linhas, minimo=118.0, maximo=176.0, respiro=20.0)

    for indice, dim in enumerate(dimensoes[:6]):
        col, lin = indice % colunas, indice // colunas
        x = 36 + col * (largura_bloco + 18)
        y = topo + lin * (altura_bloco + 20)
        _mini_grafico(pdf, x, y, largura_bloco, altura_bloco, dim, itens, str(dim.get("chave")) in decisivas)

    rodape(
        pdf,
        "Barras na mesma escala do maior valor de cada parâmetro, com base em zero. "
        "Parâmetro que não separou ninguém aparece marcado como sem diferença relevante.",
    )


def _mini_grafico(
    pdf: UltraPDF,
    x: float,
    y: float,
    largura: float,
    altura: float,
    dim: Mapping[str, Any],
    itens: Sequence[Mapping[str, Any]],
    decisiva: bool,
) -> None:
    chave = str(dim.get("chave"))
    unidade = str(dim.get("unidade") or "")

    pdf.set_fill_color(250, 250, 250)
    pdf.rect(x, y, largura, altura, style="F")
    pdf.set_draw_color(*CINZA_LINHA)
    pdf.rect(x, y, largura, altura, style="D")

    pdf.set_text_color(*CINZA_TEXTO)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_xy(x + 10, y + 8)
    rotulo = ascii_seguro(str(dim.get("rotulo") or chave))
    # Largura medida COM A FONTE DO TITULO. Medi-la depois de trocar para o corpo 7,5 da
    # nota dava um deslocamento curto demais, e o "menos é melhor" saiu por cima do titulo.
    largura_rotulo = pdf.get_string_width(rotulo)
    pdf.cell(largura - 20, 12, rotulo)

    # A DIREÇÃO precisa estar escrita. Em "Concorrentes" a barra MAIOR é a pior, e sem o
    # aviso o desenho mente para quem passa o olho. Não vem no payload: sai de quem está em
    # 1o lugar — se o 1o tem o MENOR valor, então menos é melhor. É leitura do dado que já
    # chegou, não regra nova.
    if _menos_e_melhor(dim, itens):
        pdf.set_text_color(150, 150, 150)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_xy(x + 14 + largura_rotulo, y + 9)
        pdf.cell(120, 11, ascii_seguro("menos é melhor"))

    if not decisiva:
        # DECLARA em vez de esconder: parametro que nao separou ninguem continua no slide,
        # com o motivo escrito. Some-lo faria o leitor achar que ele nao foi avaliado.
        pdf.set_text_color(150, 150, 150)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_xy(x + 10, y + 21)
        pdf.cell(largura - 20, 9, "sem diferença relevante")

    valores: list[float | None] = []
    for item in itens:
        casada = _dimensao_do_item(item, chave)
        valores.append(None if casada is None else casada.get("valor"))

    finitos = [v for v in valores if isinstance(v, int | float)]
    teto = max(abs(v) for v in finitos) if finitos else 0.0

    topo = y + 36
    espaco = altura - 46
    passo = espaco / max(len(itens), 1)
    barra_x = x + 10
    barra_largura = largura - 20 - 62

    for i, valor in enumerate(valores):
        linha_y = topo + i * passo
        pdf.set_fill_color(*CINZA_CLARO)
        pdf.rect(barra_x, linha_y + 2, barra_largura, 9, style="F")
        if valor is not None and teto > 0:
            cor = cor_do_item(i) if decisiva else (170, 170, 170)
            pdf.set_fill_color(*cor)
            pdf.rect(barra_x, linha_y + 2, barra_largura * abs(float(valor)) / teto, 9, style="F")
        pdf.set_text_color(*CINZA_TEXTO)
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_xy(barra_x + barra_largura + 4, linha_y)
        pdf.cell(56, 12, ascii_seguro(_valor_com_unidade(valor, unidade)), align="R")


def _menos_e_melhor(dim: Mapping[str, Any], itens: Sequence[Mapping[str, Any]]) -> bool:
    """A dimensao premia o MENOR valor?

    Derivado de quem esta' em 1o lugar, e nao de um campo proprio: o payload ja' traz a
    posicao calculada pela tela, entao perguntar a ela e' mais seguro do que duplicar aqui
    a lista de "quais dimensoes invertem" — duplicata que sairia do lugar na primeira
    dimensao nova.
    """
    chave = str(dim.get("chave"))
    valores: list[tuple[int, float]] = []
    for item in itens:
        casada = _dimensao_do_item(item, chave)
        if casada is None:
            continue
        posicao, valor = casada.get("posicao"), casada.get("valor")
        if posicao is None or not isinstance(valor, int | float):
            continue
        valores.append((int(posicao), float(valor)))
    if len(valores) < 2:
        return False
    primeiro = min(valores, key=lambda p: p[0])[1]
    return primeiro == min(v for _, v in valores) and primeiro != max(v for _, v in valores)


def _dimensao_do_item(item: Mapping[str, Any], chave: str) -> Mapping[str, Any] | None:
    for d in item.get("porDimensao") or []:
        if str(d.get("chave")) == chave:
            return d
    return None


# ===========================================================================
# Slide 3 - Matriz de calor
# ===========================================================================

#: Extremos da matriz. Turquesa = melhor posicao, magenta = pior. NAO e' a rampa de score
#: do produto (verde/vermelho): aqui a cor diz POSICAO RELATIVA entre os comparados, nao
#: qualidade absoluta — reusar a rampa afirmaria "bom/ruim" onde so' ha' "1o/ultimo".
_MATRIZ_MELHOR = ULTRA_TURQUESA
_MATRIZ_PIOR = ULTRA_MAGENTA


def _mistura(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def _slide_matriz(pdf: UltraPDF, dados: Mapping[str, Any], arte: bytes | None) -> None:
    pdf.add_page()
    _fundo(pdf, arte, cor=BRANCO)
    faixa_de_titulo(pdf, "Onde cada área é forte", "posição relativa em cada parâmetro")

    itens = list(dados.get("itens") or [])[:MAX_ITENS]
    if not itens:
        return
    dimensoes = list(itens[0].get("porDimensao") or [])
    n = len(itens)

    rotulo_largura = 168.0
    celula_largura = (PAGINA_LARGURA - 72 - rotulo_largura) / max(len(dimensoes), 1)
    topo = 118.0
    # Ocupa a altura util (ate' a legenda), em vez de deixar dois tercos de slide em branco
    # com 3 itens num layout pensado para 5.
    celula_altura = _altura_que_preenche(430.0 - topo, n, minimo=34.0, maximo=62.0)

    pdf.set_text_color(110, 110, 110)
    pdf.set_font("Helvetica", "", 7.5)
    for j, dim in enumerate(dimensoes):
        x = 36 + rotulo_largura + j * celula_largura
        pdf.set_xy(x + 2, topo - 24)
        pdf.multi_cell(celula_largura - 4, 9, ascii_seguro(str(dim.get("rotulo") or "")), align="C")

    for i, item in enumerate(itens):
        y = topo + i * celula_altura
        pdf.set_fill_color(*cor_do_item(i))
        pdf.rect(36, y + celula_altura / 2 - 5, 9, 9, style="F")
        pdf.set_text_color(*CINZA_TEXTO)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_xy(52, y + celula_altura / 2 - 7)
        pdf.cell(rotulo_largura - 24, 14, ascii_seguro(str(item.get("rotulo") or f"Área {i + 1}")))

        meio = celula_altura / 2
        for j, dim in enumerate(dimensoes):
            casada = _dimensao_do_item(item, str(dim.get("chave")))
            x = 36 + rotulo_largura + j * celula_largura
            # `valor` sai junto de `posicao`: adiante o `continue` garante que a celula
            # existe, mas o mypy nao ve isso atraves do ternario.
            posicao = None if casada is None else casada.get("posicao")
            valor = None if casada is None else casada.get("valor")

            if posicao is None:
                # Sem dado: celula neutra e traco. Pintar do tom "pior" afirmaria derrota
                # onde so' ha' ausencia.
                pdf.set_fill_color(245, 245, 245)
                pdf.rect(x + 1, y + 2, celula_largura - 2, celula_altura - 4, style="F")
                pdf.set_text_color(160, 160, 160)
                pdf.set_font("Helvetica", "", 9)
                pdf.set_xy(x + 1, y + meio - 6)
                pdf.cell(celula_largura - 2, 12, "-", align="C")
                continue

            t = 0.0 if n <= 1 else (float(posicao) - 1.0) / (n - 1)
            pdf.set_fill_color(*_mistura(_MATRIZ_MELHOR, _MATRIZ_PIOR, t))
            pdf.rect(x + 1, y + 2, celula_largura - 2, celula_altura - 4, style="F")
            pdf.set_text_color(*BRANCO)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_xy(x + 1, y + meio - 12)
            # ORDINAL de verdade (º), nao a letra "o": "1o" se le como "um-ó" e nao como
            # primeiro lugar. O º e' latin-1 (0xBA), entao o core font do fpdf2 o escreve.
            pdf.cell(celula_largura - 2, 12, ascii_seguro(f"{int(posicao)}º"), align="C")
            pdf.set_font("Helvetica", "", 7.5)
            pdf.set_xy(x + 1, y + meio + 1)
            pdf.cell(
                celula_largura - 2,
                9,
                ascii_seguro(_valor_com_unidade(valor, str(dim.get("unidade") or ""))),
                align="C",
            )

    legenda_y = topo + n * celula_altura + 22
    pdf.set_text_color(110, 110, 110)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_xy(36, legenda_y)
    pdf.cell(320, 11, "Turquesa = melhor posição no parâmetro | magenta = pior")

    rodape(
        pdf,
        "A cor diz POSIÇÃO entre as áreas comparadas, não qualidade absoluta: o 1o lugar de "
        "um grupo fraco continua sendo o 1o. Onde menos é melhor, a posição já considera isso.",
    )


# ===========================================================================
# Slide 4 - Mapas (um enquadramento por area, lado a lado)
# ===========================================================================


def _proporcao(png: bytes | None) -> float:
    """Altura / largura da captura. `0.75` quando nao da' para medir.

    A MOLDURA se ajusta a IMAGEM, e nao o contrario. Antes a altura da celula era fixa e a
    imagem entrava centralizada dentro dela: sobrava faixa cinza em cima e embaixo de cada
    mapa, sem servir a nada, e o mapa saia menor do que a pagina permitia. Medindo a
    proporcao aqui, a moldura fecha exatamente no mapa e ele cresce ~25% em altura.
    """
    if not png:
        return 0.75
    try:
        from PIL import Image

        with Image.open(BytesIO(png)) as img:
            if img.width > 0 and img.height > 0:
                return img.height / img.width
    except Exception:  # noqa: BLE001 - captura ilegivel cai na proporcao padrao
        pass
    return 0.75


def _slide_mapas(
    pdf: UltraPDF,
    dados: Mapping[str, Any],
    arte: bytes | None,
    mapas: Sequence[bytes | None],
) -> None:
    """Os mapas capturados da tela, um por area, lado a lado.

    As imagens vem do PILOTO (captura do canvas), e nao de um render no servidor: medido em
    2026-08-13, o renderizador do Relatorio Pontual gasta ~7,8 s so' para carregar os
    setores de UMA coordenada e trabalha num raio de 1 km, onde um hexagono de ~5 km2 sai
    praticamente vazio. Capturar garante ainda que o PDF mostre o MESMO enquadramento e as
    MESMAS cores que o operador viu.
    """
    pdf.add_page()
    _fundo(pdf, arte, cor=BRANCO)
    faixa_de_titulo(pdf, "Quem já disputa o aluno ali", "concorrentes e unidades Ultra no entorno")

    itens = list(dados.get("itens") or [])[:MAX_ITENS]
    n = len(itens)
    if not n:
        return

    vao = 14.0
    largura = (PAGINA_LARGURA - 72 - vao * (n - 1)) / n

    # A altura sai da PROPORCAO REAL das capturas, e a mesma para todas: com alturas
    # diferentes lado a lado, a linha de baixo viraria um serrote. Usa a maior proporcao do
    # conjunto para nenhuma imagem precisar ser cortada, e o teto da pagina manda no fim.
    disponivel = 470.0 - 108.0
    proporcao = max((_proporcao(mapas[i] if i < len(mapas) else None) for i in range(n)), default=0.75)
    altura = min(disponivel, largura * proporcao)
    topo = 108.0 + (disponivel - altura) / 2

    for i, item in enumerate(itens):
        x = 36 + i * (largura + vao)
        png = mapas[i] if i < len(mapas) else None

        pdf.set_fill_color(*cor_do_item(i))
        pdf.rect(x, topo - 22, 9, 9, style="F")
        pdf.set_text_color(*CINZA_TEXTO)
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_xy(x + 14, topo - 24)
        pdf.cell(largura - 14, 13, ascii_seguro(str(item.get("rotulo") or f"Área {i + 1}")))

        if png:
            try:
                # A moldura JA' tem a proporcao da captura, entao a imagem preenche a
                # celula inteira sem esticar e sem sobra. `pdf.image(w=, h=)` deformaria se
                # as duas proporcoes divergissem — e deformar mapa, numa peca cujo assunto
                # e' distancia, nao e' detalhe estetico.
                escala = _proporcao(png)
                ch = min(altura, largura * escala)
                cw = ch / escala if escala > 0 else largura
                pdf.image(
                    BytesIO(png),
                    x=x + (largura - cw) / 2,
                    y=topo + (altura - ch) / 2,
                    w=cw,
                    h=ch,
                )
            except Exception:  # noqa: BLE001 - captura corrompida nao derruba o deck
                png = None

        if not png:
            # DECLARA a ausencia em vez de deixar um retangulo vazio: mapa que faltou por
            # captura falha se parece com "nao ha concorrente aqui", que e' o oposto.
            pdf.set_fill_color(246, 246, 246)
            pdf.rect(x, topo, largura, altura, style="F")
            pdf.set_draw_color(*CINZA_LINHA)
            pdf.rect(x, topo, largura, altura, style="D")
            pdf.set_text_color(140, 140, 140)
            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_xy(x + 8, topo + altura / 2 - 12)
            pdf.multi_cell(
                largura - 16,
                11,
                ascii_seguro("Mapa não capturado para esta área."),
                align="C",
            )

        pdf.set_draw_color(*CINZA_LINHA)
        pdf.rect(x, topo, largura, altura, style="D")

    rodape(
        pdf,
        "Imagens capturadas do próprio Mapa Territorial, no enquadramento de cada área - "
        "mesmas camadas e mesmas cores da tela. Pins: concorrentes mapeados e unidades Ultra.",
    )


# ===========================================================================
# Slide 5 - Tabela
# ===========================================================================


def _slide_tabela(pdf: UltraPDF, dados: Mapping[str, Any], arte: bytes | None) -> None:
    pdf.add_page()
    _fundo(pdf, arte, cor=BRANCO)
    faixa_de_titulo(pdf, "Os números", "valores como saíram do motor, sem transformação")

    itens = list(dados.get("itens") or [])[:MAX_ITENS]
    if not itens:
        return
    dimensoes = list(itens[0].get("porDimensao") or [])

    rotulo_largura = 190.0
    coluna = (PAGINA_LARGURA - 72 - rotulo_largura) / max(len(itens), 1)
    y = 96.0

    cabecalho: list[tuple[float, str, str]] = [(rotulo_largura, "Parâmetro", "L")]
    for i, item in enumerate(itens):
        cabecalho.append((coluna, str(item.get("rotulo") or f"Área {i + 1}"), "R"))
    linha_de_tabela(pdf, 36, y, cabecalho, altura=22, negrito=True, fundo=CINZA_CLARO)
    y += 22

    # Linha alta o bastante para a tabela ocupar o slide: 5 parametros em linhas de 26 pt
    # deixavam metade da pagina vazia.
    altura_linha = _altura_que_preenche(452.0 - y, len(dimensoes), minimo=26.0, maximo=48.0)

    for indice, dim in enumerate(dimensoes):
        colunas: list[tuple[float, str, str]] = [(rotulo_largura, str(dim.get("rotulo") or ""), "L")]
        for item in itens:
            casada = _dimensao_do_item(item, str(dim.get("chave")))
            texto = _valor_com_unidade(
                None if casada is None else casada.get("valor"), str(dim.get("unidade") or "")
            )
            # O melhor de cada linha marcado no PROPRIO texto: o PDF e' lido impresso e em
            # preto e branco, onde cor sozinha nao sobrevive.
            if casada is not None and casada.get("melhor"):
                texto = f"{texto}  *"
            colunas.append((coluna, texto, "R"))
        # Faixa alternada, o mesmo trilho da tabela da tela: sem ela o olho perde a linha
        # numa grade larga.
        fundo = (247, 247, 247) if indice % 2 else None
        linha_de_tabela(pdf, 36, y, colunas, altura=altura_linha, fundo=fundo)
        y += altura_linha

    pdf.set_text_color(110, 110, 110)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_xy(36, y + 12)
    pdf.cell(400, 11, "*  melhor valor do parâmetro. Traço = a área não tem esse dado.")

    rodape(
        pdf,
        "Residual em alunos (bruto), não o score: o score de residual satura em 100 acima de "
        "2.500 alunos e empataria as áreas no topo, que é justamente onde estão as candidatas.",
    )


# ===========================================================================
# Slide 5 - Recomendacao e rank
# ===========================================================================


def _slide_recomendacao(pdf: UltraPDF, dados: Mapping[str, Any], arte: bytes | None) -> None:
    pdf.add_page()
    _fundo(pdf, arte, cor=BRANCO)
    faixa_de_titulo(pdf, "Recomendação", "quem lidera, e em quê")

    itens = list(dados.get("itens") or [])[:MAX_ITENS]
    decisivas = list(dados.get("dimensoesDecisivas") or [])
    melhor = dados.get("melhor")

    # RANK POR CONTAGEM DE VITORIAS, nao por nota somada. Ordenar por uma nota unica seria
    # peso entre camadas do M1 (exige DEC); contar em quantos parametros cada area lidera
    # e' leitura direta, e e' a mesma que a tela mostra.
    ordenados = sorted(
        enumerate(itens),
        key=lambda par: (-int(par[1].get("vitorias") or 0), int(par[1].get("derrotas") or 0)),
    )

    # POSICAO COM EMPATE COMPARTILHADO (1, 1, 3, 4), e nao a ordem da lista. O rodape deste
    # slide afirma que empate no topo NAO e' desempatado; imprimir "1º" e "2º" para duas
    # areas que lideram o mesmo numero de parametros faria o desenho contradizer o texto —
    # e a ordem entre elas sairia de um criterio (menos derrotas) que ninguem aprovou como
    # desempate. Medido num deck real de 4 cidades: Sao Paulo e Carapicuiba lideravam 2
    # parametros cada e apareciam como 1º e 2º.
    posicoes: list[int] = []
    for i, (_, item) in enumerate(ordenados):
        v = int(item.get("vitorias") or 0)
        if i and v == int(ordenados[i - 1][1].get("vitorias") or 0):
            posicoes.append(posicoes[-1])
        else:
            posicoes.append(i + 1)

    y = 96.0
    # Reserva o rodape da frase (54 pt) e distribui o resto entre os itens, para o slide
    # nao terminar com metade da pagina em branco.
    altura = _altura_que_preenche(414.0 - y, len(ordenados), minimo=46.0, maximo=84.0, respiro=8.0)
    for ordem, (indice_original, item) in enumerate(ordenados):
        posicao = posicoes[ordem]
        destaque = posicao == 1 and melhor is not None
        pdf.set_fill_color(*(CINZA_CLARO if destaque else (250, 250, 250)))
        pdf.rect(36, y, PAGINA_LARGURA - 72, altura, style="F")
        pdf.set_fill_color(*cor_do_item(indice_original))
        pdf.rect(36, y, 5, altura, style="F")

        # Bloco vertical CENTRADO na faixa: com a altura variável, ancorar no topo deixaria
        # o texto colado na borda de cima nos itens altos.
        centro = y + altura / 2
        pdf.set_text_color(*CINZA_TEXTO)
        pdf.set_font("Helvetica", "B", 15)
        pdf.set_xy(52, centro - 15)
        pdf.cell(40, 18, ascii_seguro(f"{posicao}º"))
        pdf.set_font("Helvetica", "B" if destaque else "", 13)
        pdf.set_xy(92, centro - 14)
        pdf.cell(360, 17, ascii_seguro(str(item.get("rotulo") or "")))

        vitorias = int(item.get("vitorias") or 0)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(110, 110, 110)
        pdf.set_xy(92, centro + 4)
        pdf.cell(
            360,
            13,
            ascii_seguro(f"lidera em {vitorias} de {len(decisivas)} parâmetros que separaram"),
        )

        # QUAIS parametros, e nao so' quantos: "lidera em 3" nao diz se sao os que importam.
        nomes = [
            str(d.get("rotulo") or "")
            for d in item.get("porDimensao") or []
            if d.get("melhor") and str(d.get("chave")) in decisivas
        ]
        if nomes:
            # TETO de 3 nomes. Quem lidera em tudo produzia uma linha que corria ate' a
            # borda da pagina — `cell` nao quebra nem avisa, o texto so' some pela margem.
            visiveis = nomes[:3]
            texto_nomes = ", ".join(visiveis)
            if len(nomes) > len(visiveis):
                texto_nomes += f" e mais {len(nomes) - len(visiveis)}"
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*ULTRA_TURQUESA)
            pdf.set_xy(470, centro - 14)
            pdf.cell(PAGINA_LARGURA - 36 - 470, 13, ascii_seguro(texto_nomes))

        # O ESTUDO, quando o item traz criterios avaliados (analise pontual). Liderar
        # parametros e PASSAR nos criterios sao perguntas diferentes: um ponto pode ganhar
        # a comparacao e mesmo assim reprovar num piso do produto, e o deck nao pode deixar
        # isso implicito. Nao entra viabilidade — ela e' por imovel, com metragem e aluguel
        # digitados (DEC-009), e a comparacao nao os tem.
        reprovados = [
            str(c.get("rotulo") or "")
            for c in item.get("criterios") or []
            if c.get("passa") is False
        ]
        avaliados = [c for c in item.get("criterios") or [] if c.get("passa") is not None]
        if avaliados:
            pdf.set_font("Helvetica", "", 8.5)
            if reprovados:
                pdf.set_text_color(180, 60, 60)
                texto = f"reprova em: {', '.join(reprovados)}"
            else:
                pdf.set_text_color(60, 130, 90)
                texto = f"passa nos {len(avaliados)} critérios avaliados"
            pdf.set_xy(470, centro + 2)
            pdf.cell(PAGINA_LARGURA - 72 - 470 + 30, 12, ascii_seguro(texto))

        y += altura + 8

    frase = str(dados.get("frase") or "")
    if frase:
        pdf.set_fill_color(*CINZA_CLARO)
        pdf.rect(36, y + 6, PAGINA_LARGURA - 72, 54, style="F")
        pdf.set_text_color(*CINZA_TEXTO)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_xy(48, y + 16)
        pdf.multi_cell(PAGINA_LARGURA - 96, 15, ascii_seguro(frase), max_line_height=15)

    # "área" vira "ponto" no deck de pontos: o rodapé é a linha que explica a régua, e
    # explicá-la com a palavra errada é a forma mais fácil de perder a confiança do leitor.
    sujeito = "cada ponto" if dados.get("dePontos") else "cada área"
    rodape(
        pdf,
        f"O rank CONTA em quantos parâmetros {sujeito} lidera; ele não soma os parâmetros numa "
        "nota única. Empate no topo não é desempatado - quando ele ocorre, não há 1º lugar.",
    )


# ===========================================================================
# Slide 6 - Encerramento
# ===========================================================================


def _slide_encerramento(pdf: UltraPDF, dados: Mapping[str, Any], arte: bytes | None, quando: date) -> None:
    pdf.add_page()
    _fundo(pdf, arte, cor=ULTRA_TURQUESA)

    # MESMA coluna limpa da capa. O texto é curto de propósito: a coluna tem 446 pt de
    # largura e para em 461,4 pt de altura, então uma linha longa sairia pela margem sem
    # aviso e um parágrafo alto entraria na faixa de logos.
    pdf.set_text_color(*BRANCO)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_xy(_CAPA_X, 300)
    pdf.cell(_CAPA_LARGURA, 26, ascii_seguro("O que este material decide"))

    # O fechamento muda com o tipo de comparação: num deck de PONTOS, dizer "a área tem
    # 5 km2, use a análise de ponto" seria absurdo — é justamente ela que gerou o deck.
    de_pontos = bool(dados.get("dePontos"))
    linhas = (
        (
            "Decide qual dos pontos leva vantagem em cada",
            "parâmetro do entorno, e o que cada um reprova",
            "nos critérios do estudo.",
            "",
            "NÃO decide viabilidade: metragem e aluguel são",
            "entrada do operador sobre um imóvel concreto",
            "(DEC-009), e ela roda por ponto, não na comparação.",
        )
        if de_pontos
        else (
            "Decide qual das áreas leva vantagem em cada",
            "parâmetro, e quantos parâmetros cada uma lidera.",
            "",
            "NÃO decide viabilidade: metragem e aluguel são",
            "entrada sobre um imóvel concreto, e a área aqui",
            "tem cerca de 5 km2. Para isso, análise de ponto.",
        )
    )
    pdf.set_font("Helvetica", "", 11)
    y = 334.0
    for texto in linhas:
        if y + 16 > _CAPA_RODAPE_LOGOS_TOP:
            break
        pdf.set_xy(_CAPA_X, y)
        pdf.cell(_CAPA_LARGURA, 16, ascii_seguro(texto))
        y += 16

    _ = quando  # a data ja' saiu na capa; repeti-la aqui roubaria linha da coluna limpa


# ===========================================================================
# Entrada
# ===========================================================================


def gerar_pdf_comparacao(
    dados: Mapping[str, Any],
    *,
    mapas: Sequence[bytes | None] | None = None,
    ultra_dir: Path | str | None = None,
    quando: date | None = None,
) -> bytes:
    """Monta o deck de 6 slides a partir do ranking JA CALCULADO pelo front.

    `dados` espelha o `RankingComparacao` do TypeScript, mais `titulo` e `subtitulo`.
    Nenhuma regra de comparacao roda aqui — ver o cabecalho do modulo.
    """
    quando = quando or date.today()
    arte = _assets(ultra_dir)

    pdf = UltraPDF()
    pdf.set_title(ascii_seguro(str(dados.get("titulo") or "Comparação de áreas")))
    pdf.set_author("Motor de Expansão - Ultra Academia")

    _slide_capa(pdf, dados, arte["capa"], quando)
    _slide_graficos(pdf, dados, arte["conteudo"])
    _slide_matriz(pdf, dados, arte["conteudo"])
    # O slide de mapas SO' entra se houver ao menos uma captura. Sem imagem nenhuma ele
    # seria uma pagina de molduras vazias — pior que nao existir.
    if mapas and any(mapas):
        _slide_mapas(pdf, dados, arte["conteudo"], mapas)
    # A TABELA SAIU (pedido do Juan, 2026-08-14): ela repetia os MESMOS numeros que o
    # slide de graficos ja' mostra em barra e que a matriz ja' imprime sob a posicao. Tres
    # slides para os mesmos cinco valores cansa o leitor sem acrescentar leitura. O
    # `_slide_tabela` fica no modulo, sem chamador, so' se voltar a fazer falta.
    _slide_recomendacao(pdf, dados, arte["conteudo"])
    _slide_encerramento(pdf, dados, arte["capa"], quando)

    return bytes(pdf.output())
