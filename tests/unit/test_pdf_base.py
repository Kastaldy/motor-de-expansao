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
