"""Testes do BLK-RELVIAB-04: pagina(s) de VIABILIDADE no PDF (numeros + graficos).

Sem `graficos` -> 1 pagina (numeros); com `graficos` -> 2 paginas (numeros + grade). Default
None -> PDF inalterado. Usa `result` minimo + `mapas=None`. Um teste integra os PNGs reais
do BLK-RELVIAB-03. Sem PII.
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from motor_expansao.dashboard.censo_report import (
    _viab_breakeven,
    _viab_brl,
    _viab_faixa,
    _viab_normalizado,
    _viab_payback,
    _viab_pct,
    gerar_pdf_relatorio_pontual_censitario,
    gerar_pdf_relatorio_pontual_classico,
)
from motor_expansao.dashboard.constants import TEXTO_SEM_DADO

_MIN_RESULT = {"lat": -23.55, "lng": -46.63, "nome_municipio": "SAO PAULO", "uf": "SP", "raio_km": 1.5}

_VIAB = {
    "alunos_breakeven": 520,
    "aluguel_teto": 24500.0,
    "margem_ebitda_pct": 0.18,
    "payback_meses": 26.0,
    "roic_anual": 0.22,
    "faturamento_mensal": 150_000.0,
    "ebitda_mensal": 27_000.0,
    "faixa_p10": 400,
    "faixa_p90": 1000,
    "flag_viavel": True,
    "flag_fora_envelope": False,
}

_TIT_NUM = "Proje\xe7\xe3o de Viabilidade - N\xfameros".encode("latin-1")
_TIT_GRAF = "Viabilidade - Proje\xe7\xe3o financeira".encode("latin-1")


def _png(w: int = 300, h: int = 200) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), (0, 167, 157)).save(buf, format="PNG")
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# Formatadores                                                                #
# --------------------------------------------------------------------------- #
def test_viab_brl():
    assert _viab_brl(24500.0) == "R$ 24.500,00"
    assert _viab_brl(None) == TEXTO_SEM_DADO


def test_viab_pct():
    assert _viab_pct(0.18) == "18,0%"
    assert _viab_pct(None) == TEXTO_SEM_DADO


def test_viab_payback():
    assert _viab_payback(26.0) == "26 meses"
    assert _viab_payback(float("inf")) == "> 60 meses"
    assert _viab_payback(None) == "> 60 meses"


def test_viab_breakeven():
    assert _viab_breakeven(520) == "520"
    assert _viab_breakeven(float("inf")) == "inviável"
    assert _viab_breakeven(None) == "inviável"


def test_viab_faixa():
    assert _viab_faixa(400, 1000) == "400 - 1.000"
    assert _viab_faixa(None, None) == TEXTO_SEM_DADO


# --------------------------------------------------------------------------- #
# Insercao das paginas (OPCIONAL)                                             #
# --------------------------------------------------------------------------- #
def test_sem_viabilidade_mantem_7_paginas():
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(_MIN_RESULT, None)
    # BLK-RELPON-14: o PDF base caiu de 8 para 7 paginas (a "Imagem do Entorno" saiu).
    assert b"/Count 7" in pdf_bytes
    assert _TIT_NUM not in pdf_bytes


def test_viabilidade_sem_graficos_1_pagina():
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(_MIN_RESULT, None, viabilidade=_VIAB)
    # 7 base + numeros + CONCLUSAO: `viabilidade` passou a trazer 2 paginas, nao 1 -- a
    # de Conclusao entra sob a MESMA condicao (sem payload nao ha regua para avaliar).
    assert b"/Count 9" in pdf_bytes
    assert _TIT_NUM in pdf_bytes
    assert _TIT_GRAF not in pdf_bytes
    assert b"R$ 24.500,00" in pdf_bytes  # aluguel-teto formatado


def test_viabilidade_com_graficos_2_paginas():
    viab = {**_VIAB, "graficos": [_png(), _png(), _png(), _png()]}
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(_MIN_RESULT, None, viabilidade=viab)
    assert b"/Count 10" in pdf_bytes  # 7 base + numeros + graficos + conclusao
    assert _TIT_NUM in pdf_bytes
    assert _TIT_GRAF in pdf_bytes


def test_censitario_com_viabilidade_e_graficos():
    viab = {**_VIAB, "graficos": [_png(), _png()]}
    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(_MIN_RESULT, None, viabilidade=viab)
    # numeros + graficos + conclusao (2 pngs preenchem, resto fallback)
    assert b"/Count 10" in pdf_bytes


def test_relatorio_completo_soma_todas_as_paginas():
    """Fotos(1) + info(1) + viab numeros(1) + viab graficos(1) + conclusao(1) = 7 + 5 = 12."""
    viab = {**_VIAB, "graficos": [_png(), _png(), _png(), _png()]}
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        _MIN_RESULT,
        None,
        fotos=[_png(640, 480), _png(480, 640)],
        info_imovel={"metragem_m2": 1500, "endereco": "Rua Teste, 1"},
        viabilidade=viab,
    )
    assert b"/Count 12" in pdf_bytes


def test_integra_graficos_reais_do_relviab_03():
    from motor_expansao.dashboard.viabilidade_charts import (
        grafico_dre_waterfall,
        grafico_faturamento_ebitda,
        grafico_fcf_acumulado,
        grafico_rampa_alunos,
    )
    from motor_expansao.dimensionamento.simulador import gerar_serie_mensal

    serie = gerar_serie_mensal(
        alunos_maturidade=900.0, m2=1500.0, aluguel_mes=20000.0, ticket_medio=137.0
    )
    graficos = [
        grafico_rampa_alunos(serie, steady=900.0, maturacao_mes=8),
        grafico_faturamento_ebitda(serie),
        grafico_fcf_acumulado(serie, payback_meses=24.0),
        grafico_dre_waterfall(
            faturamento_bruto=193_000.0,
            receita_liquida=180_000.0,
            receita_pos_impostos=155_000.0,
            ebitda=42_000.0,
        ),
    ]
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        _MIN_RESULT, None, viabilidade={**_VIAB, "graficos": graficos}
    )
    assert b"/Count 10" in pdf_bytes  # + conclusao
    assert len(pdf_bytes) > 30_000  # 4 PNGs reais embutidos


# --------------------------------------------------------------------------- #
# Card "Capex total" no lugar de "Retorno anual do negocio" (pedido de 2026-09-23)  #
# --------------------------------------------------------------------------- #
_INVESTIMENTO = {
    "obra": 1_200_000.0,
    "equipamentos": 800_000.0,
    "taxa_franquia": 160_000.0,
    "investimento_total": 2_160_000.0,
}


def test_card_capex_total_substitui_retorno_anual():
    viab = {
        "dre": {"faturamento": 150_000.0, "margem": 0.18},
        "retorno": {"otica": "desalavancada", "retorno_anual_desalavancado": 0.4475, "payback": 26.0},
        "investimento": dict(_INVESTIMENTO),
    }
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(_MIN_RESULT, None, viabilidade=viab)
    assert _TIT_NUM in pdf_bytes
    assert b"Capex total" in pdf_bytes
    assert b"R$ 2.160.000,00" in pdf_bytes
    assert b"Retorno anual do negocio" not in pdf_bytes
    assert b"ROIC anual" not in pdf_bytes
    # continua com 8 cards: o de capex ocupa a posicao do retorno, nada e' acrescentado
    for rotulo in (b"Margem EBITDA", b"Payback", b"Faturamento/m", b"EBITDA/m", b"Faixa alunos"):
        assert rotulo in pdf_bytes
    assert b"44,8%" not in pdf_bytes  # o retorno nao sobrevive em outro card


def test_capex_total_e_obra_mais_equipamentos_mais_franquia():
    # LEITURA do payload: o total e' o que o simulador entregou...
    dados = _viab_normalizado({"investimento": dict(_INVESTIMENTO)})
    assert dados["capex_total"] == 2_160_000.0
    # ...e, quando o payload nao traz o total, o PDF soma as tres partes
    sem_total = {k: v for k, v in _INVESTIMENTO.items() if k != "investimento_total"}
    assert _viab_normalizado({"investimento": sem_total})["capex_total"] == 2_160_000.0
    # dict plano (montar_payload_pdf_viabilidade) tambem
    assert _viab_normalizado({"obra": 1.0, "equipamentos": 2.0, "taxa_franquia": 3.0})["capex_total"] == 6.0
    # parte faltando: nao inventa zero -- "n/d"
    assert _viab_normalizado({"investimento": {"obra": 1.0, "equipamentos": 2.0}})["capex_total"] is None
    assert _viab_normalizado({})["capex_total"] is None
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(_MIN_RESULT, None, viabilidade=_VIAB)
    assert b"Capex total" in pdf_bytes and TEXTO_SEM_DADO.encode("latin-1") in pdf_bytes
