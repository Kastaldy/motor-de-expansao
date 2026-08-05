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
