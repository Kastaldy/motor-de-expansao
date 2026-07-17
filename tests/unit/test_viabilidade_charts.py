"""Testes do BLK-RELVIAB-03: graficos financeiros de viabilidade em PNG estatico.

Verifica que cada funcao retorna um PNG valido de dimensao esperada, e que o render e
deterministico na dimensao para o mesmo input. Usa a serie real de `gerar_serie_mensal`.
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from motor_expansao.dashboard.viabilidade_charts import (
    PNG_HEIGHT,
    PNG_WIDTH,
    grafico_dre_waterfall,
    grafico_faturamento_ebitda,
    grafico_fcf_acumulado,
    grafico_rampa_alunos,
)
from motor_expansao.dimensionamento.simulador import gerar_serie_mensal


def _serie():
    return gerar_serie_mensal(
        alunos_maturidade=900.0, m2=1500.0, aluguel_mes=20000.0, ticket_medio=137.0
    )


def _assert_png_valido(raw: bytes):
    assert isinstance(raw, bytes) and len(raw) > 0
    with Image.open(BytesIO(raw)) as img:
        assert img.format == "PNG"
        assert img.width == PNG_WIDTH and img.height == PNG_HEIGHT


def test_grafico_rampa_alunos_png_valido():
    _assert_png_valido(grafico_rampa_alunos(_serie(), steady=900.0, maturacao_mes=8))


def test_grafico_faturamento_ebitda_png_valido():
    _assert_png_valido(grafico_faturamento_ebitda(_serie()))


def test_grafico_fcf_acumulado_png_valido():
    _assert_png_valido(grafico_fcf_acumulado(_serie(), payback_meses=24.0))


def test_grafico_fcf_payback_infinito_nao_quebra():
    _assert_png_valido(grafico_fcf_acumulado(_serie(), payback_meses=float("inf")))


def test_grafico_dre_waterfall_png_valido():
    raw = grafico_dre_waterfall(
        faturamento_bruto=193_000.0,
        receita_liquida=180_000.0,
        receita_pos_impostos=155_000.0,
        ebitda=42_000.0,
    )
    _assert_png_valido(raw)


def test_render_deterministico_na_dimensao():
    serie = _serie()
    a = grafico_rampa_alunos(serie, steady=900.0, maturacao_mes=8)
    b = grafico_rampa_alunos(serie, steady=900.0, maturacao_mes=8)
    with Image.open(BytesIO(a)) as ia, Image.open(BytesIO(b)) as ib:
        assert ia.size == ib.size == (PNG_WIDTH, PNG_HEIGHT)


def test_serie_vazia_nao_quebra():
    # Robustez: serie vazia -> ainda gera PNG valido (grafico vazio).
    _assert_png_valido(grafico_faturamento_ebitda([]))
