"""Primitivas de PDF compartilhadas (BLK-EXEC-11).

O `_UltraPDF` era byte-identico em `censo_report.py` e `relatorio_municipal.py`. O
`pdf_base.py` existe para que o terceiro gerador (a Visao Executiva) nao vire a terceira
copia -- e os dois legados NAO foram reapontados de proposito: sao geradores em producao
com testes de regressao de bytes, e refatora-los nao entrega nada ao usuario.

O teste abaixo e' o que impede a duplicacao de virar triplicacao em silencio: se alguem
mexer na configuracao de um dos tres, o CI aponta qual dos tres saiu da linha.
"""

from __future__ import annotations

import inspect

import pytest

from motor_expansao.dashboard import pdf_base
from motor_expansao.dashboard.censo_report import _UltraPDF as PdfCenso
from motor_expansao.dashboard.relatorio_municipal import _UltraPDF as PdfMunicipal


def _configuracao(classe: type) -> dict[str, object]:
    """Estado observavel de um PDF recem-construido, sem depender do corpo do `__init__`."""
    pdf = classe()
    return {
        "pdf_version": pdf.pdf_version,
        "compressao": bool(getattr(pdf, "compress", False)),
        "quebra_automatica": bool(getattr(pdf, "auto_page_break", False)),
        "largura": round(float(pdf.w), 2),
        "altura": round(float(pdf.h), 2),
        "margens": (
            round(float(pdf.l_margin), 2),
            round(float(pdf.t_margin), 2),
            round(float(pdf.r_margin), 2),
        ),
    }


@pytest.mark.parametrize("legado", [PdfCenso, PdfMunicipal], ids=["censo", "municipal"])
def test_ultra_pdf_config_identica(legado: type) -> None:
    """As tres classes tem de descrever o MESMO slide 16:9, sem compressao."""
    assert _configuracao(pdf_base.UltraPDF) == _configuracao(legado)


def test_pagina_e_16_por_9_em_pontos() -> None:
    pdf = pdf_base.UltraPDF()
    assert (round(pdf.w), round(pdf.h)) == (
        round(pdf_base.PAGINA_LARGURA),
        round(pdf_base.PAGINA_ALTURA),
    )
    assert pdf.w / pdf.h == pytest.approx(16 / 9, rel=0.01)


def test_ascii_seguro_preserva_acento_e_neutraliza_tipografia() -> None:
    """Acento portugues cabe em latin-1; o que vira "?" e' a tipografia fora dela.

    E' a distincao que o `CLAUDE.md` §2 faz e que este projeto quase perdeu: escrever
    "nao" e "mes" na tela nunca foi exigencia do PDF.
    """
    assert pdf_base.ascii_seguro("Conversão de visitas") == "Conversão de visitas"
    assert pdf_base.ascii_seguro("Atenção à cobrança") == "Atenção à cobrança"
    for fora_de_latin1 in ("—", "•", "→", "…", "≥", "−", "“aspas”"):
        assert "?" in pdf_base.ascii_seguro(fora_de_latin1)


def test_primitivas_desenham_sem_estourar() -> None:
    """Fumaca: cada helper roda numa pagina real e o PDF sai valido."""
    pdf = pdf_base.UltraPDF()
    pdf.add_page()
    pdf_base.faixa_de_titulo(pdf, "Rede Ultra", "Competência 2026-07")
    pdf_base.cartao(pdf, 36, 90, 180, 70, rotulo="Faturamento", valor="R$ 18,6 mi", apoio="rede")
    pdf_base.linha_de_tabela(
        pdf,
        36,
        180,
        [(200.0, "Unidade", "L"), (100.0, "1.234", "R")],
        negrito=True,
        fundo=pdf_base.CINZA_CLARO,
    )
    pdf_base.rodape(pdf, "Fonte: Growth API")
    saida = bytes(pdf.output())
    assert saida.startswith(b"%PDF-1.4")
    assert b"Rede Ultra" in saida, "compressao desligada = texto cru auditavel"


def test_cor_por_severidade_cobre_todos_os_niveis() -> None:
    from motor_expansao.dashboard.rede_diagnostico import SEVERIDADES

    assert set(pdf_base.COR_SEVERIDADE) == set(SEVERIDADES)


def test_nenhum_gerador_legado_foi_reapontado() -> None:
    """Escopo declarado da DEC-023: os dois legados continuam com a classe DELES.

    Reapontar `censo_report` e `relatorio_municipal` para `pdf_base` neste epic seria
    risco alto (testes de regressao de bytes em producao) sem entregar nada ao usuario.
    Quando alguem fizer isso, este teste cai junto -- de propósito, para forçar a
    decisão a ser consciente.
    """
    for modulo in ("censo_report", "relatorio_municipal"):
        fonte = inspect.getsource(
            __import__(f"motor_expansao.dashboard.{modulo}", fromlist=[modulo])
        )
        assert "class _UltraPDF(FPDF)" in fonte, f"{modulo} deixou de definir a propria classe"


# ---------------------------------------------------------------------------
# Guard de acentuacao NO PDF
# ---------------------------------------------------------------------------

#: Palavras que em portugues SEMPRE levam acento. Mesma lista de
#: `test_rede_diagnostico.py`, sem as ambiguas ("sao" aparece em nome cru de unidade,
#: que e' dado e nao texto).
_SEMPRE_ACENTUADAS = (
    "nao", "mes", "regua", "reguas", "periodo", "periodos", "conversao", "dependencia",
    "diagnostico", "numero", "numeros", "critico", "inadimplencia", "retencao", "decisao",
    "manutencao", "migracao", "reativacao", "estavel", "evitavel", "saida", "cobranca",
    "tres", "corroi", "comparavel", "comparaveis", "atencao", "comparacao", "competencia",
    "rodape", "media", "ja", "esta", "ha", "so", "composicao", "posicao", "relatorio",
    "analise", "grafico", "graficos", "metrica", "metricas", "referencia", "usuario",
)


def _texto_cru_do_pdf(pdf: bytes) -> str:
    """Texto do PDF em minusculas. Funciona porque o `UltraPDF` desliga a compressao."""
    return pdf.decode("latin-1", errors="replace").lower()


def test_pdf_nao_imprime_texto_sem_acento() -> None:
    """Guard que o teste do "?" NAO cobre -- e' por isso que ele existe.

    Escrever "competencia" em vez de "competência" nao produz caractere fora de latin-1;
    o PDF sai limpo, o `assert b"?" not in pdf` passa, e o defeito chega ao usuario. O
    unico lugar onde ele aparece e' o texto CRU do arquivo gerado.
    """
    import re

    from motor_expansao.dashboard import rede_export
    from tests.unit.rede_fixtures import payload_carteira_sintetico, payload_ficha_sintetico

    padrao = re.compile(r"\b(?:" + "|".join(_SEMPRE_ACENTUADAS) + r")\b")
    for nome, gerar, payload in (
        ("carteira", rede_export.carteira_pdf, payload_carteira_sintetico()),
        ("ficha", rede_export.ficha_pdf, payload_ficha_sintetico()),
    ):
        cru = _texto_cru_do_pdf(gerar(payload))
        ofensas = sorted(set(padrao.findall(cru)))
        assert not ofensas, f"PDF da {nome} imprime texto sem acento (CLAUDE.md §2): {ofensas}"


# ---------------------------------------------------------------------------
# Graficos: o que os renders mostraram e nenhum teste pegava
# ---------------------------------------------------------------------------


def _pdf_de_uma_pagina(desenhar) -> str:
    """Texto cru de um PDF de uma pagina.

    Os parenteses delimitam string no PDF e saem ESCAPADOS (`\(100%\)`); tira-se a
    barra para que a asercao possa procurar o texto como ele e' lido.
    """
    pdf = pdf_base.UltraPDF()
    pdf.add_page()
    desenhar(pdf)
    cru = bytes(pdf.output()).decode("latin-1", errors="replace")
    return cru.replace("\(", "(").replace("\)", ")")


def test_barras_imprimem_o_valor_de_cada_mes() -> None:
    """Comparar alturas responde "subiu ou caiu"; só o número responde "quanto"."""
    cru = _pdf_de_uma_pagina(
        lambda pdf: pdf_base.barras(
            pdf, 36, 100, 400, 120, ["jan", "fev", "mar"], [100.0, 250.0, 175.0]
        )
    )
    for esperado in ("100", "250", "175"):
        assert esperado in cru, f"o valor {esperado} não foi impresso sobre a barra"


def test_linha_imprime_valor_mes_a_mes_e_nao_so_os_extremos() -> None:
    """Antes saíam só o mínimo e o máximo, e no papel não há como passar o mouse."""
    valores = [10.0, 20.0, 30.0, 40.0]
    cru = _pdf_de_uma_pagina(
        lambda pdf: pdf_base.linha(pdf, 36, 100, 400, 80, valores)
    )
    impressos = [v for v in ("10", "20", "30", "40") if v in cru]
    assert len(impressos) >= 3, f"esperava o valor de quase todos os pontos, saíram {impressos}"


def test_rosca_de_fatia_unica_desenha_o_anel_inteiro() -> None:
    """`solid_arc` de 0 a 360 graus não fecha a volta e sai como um setor mordido.

    Aconteceu de verdade: uma unidade sem nenhum agregador aparecia com 100% desenhado
    como se fosse ~85%. Uma fatia só passa a ser um círculo.
    """
    def desenhar(pdf: pdf_base.UltraPDF) -> None:
        pdf_base.rosca(
            pdf,
            40,
            40,
            80,
            [("Recorrentes", 3870.0, pdf_base.ULTRA_TURQUESA), ("Agregadores", 0.0, pdf_base.ULTRA_MAGENTA)],
            centro_valor="0%",
        )

    cru = _pdf_de_uma_pagina(desenhar)
    assert "(100%)" in cru and "(0%)" in cru
    assert "3.870" in cru


def test_rosca_com_duas_fatias_soma_cem_por_cento() -> None:
    def desenhar(pdf: pdf_base.UltraPDF) -> None:
        pdf_base.rosca(
            pdf,
            40,
            40,
            80,
            [("Recorrentes", 906.0, pdf_base.ULTRA_TURQUESA), ("Agregadores", 713.0, pdf_base.ULTRA_MAGENTA)],
            centro_valor="44%",
            legenda_abaixo=True,
        )

    cru = _pdf_de_uma_pagina(desenhar)
    assert "(56%)" in cru and "(44%)" in cru
    assert "44%" in cru


def test_rosca_sem_dado_nao_divide_por_zero() -> None:
    cru = _pdf_de_uma_pagina(
        lambda pdf: pdf_base.rosca(
            pdf, 40, 40, 80, [("A", 0.0, pdf_base.ULTRA_TURQUESA), ("B", 0.0, pdf_base.ULTRA_MAGENTA)]
        )
    )
    assert "%PDF" in cru[:10] or cru.startswith("%PDF")


def test_titulo_de_grafico_respeita_a_largura_do_bloco() -> None:
    """Sem o limite, o texto de apoio de um bloco escrevia por cima do bloco vizinho."""
    import inspect

    assinatura = inspect.signature(pdf_base.titulo_de_grafico)
    assert "largura" in assinatura.parameters
    assert assinatura.parameters["largura"].default == 340.0
