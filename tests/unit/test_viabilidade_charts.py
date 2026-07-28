"""Testes do BLK-RELVIAB-03: graficos financeiros de viabilidade em PNG estatico.

Verifica que cada funcao retorna um PNG valido de dimensao esperada, e que o render e
deterministico na dimensao para o mesmo input. Usa a serie real de `gerar_serie_mensal`.

FIN-VIAB-01: cobre tambem o RENDER PURO — `montar_payload_pdf_viabilidade` le o
`viabilidade_payload_v1` e nao recalcula nada (payback do payload, aluguel-teto
canonico, break-even em alunos totais, PMT/juros no relatorio).
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
    grafico_fco,
    grafico_rampa_alunos,
    limites_y_faturamento_ebitda,
    montar_payload_pdf_viabilidade,
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


def _fco_serie():
    """FCO sintetico: 4 meses de obras negativos (M-4..M-1) + operacao ate o plato."""
    obras = [{"mes": m, "fcf": -75_000.0} for m in (-4, -3, -2, -1)]
    op = [{"mes": t, "fcf": float(-8_000 + t * 1_500)} for t in range(1, 25)]
    return obras + op


def test_grafico_fco_png_valido():
    _assert_png_valido(grafico_fco(_fco_serie(), mes_positivo=6))


def test_grafico_fco_sem_marco_nao_quebra():
    _assert_png_valido(grafico_fco(_fco_serie(), mes_positivo=None))


def test_grafico_fco_serie_vazia_nao_quebra():
    _assert_png_valido(grafico_fco([]))


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


# --------------------------------------------------------------------------- #
# FIN-VIAB-01 — render puro do viabilidade_payload_v1                          #
# --------------------------------------------------------------------------- #
def _serie_payload():
    """Recorte minimo da `serie_mensal` do nucleo (M-2..M-1 + 6 meses de operacao)."""
    pre = [
        {
            "mes": m, "mes_contrato": m + 3, "fase": "pre_operacional",
            "faturamento_mensal": 0.0, "ebitda_mensal": -30_000.0,
            "fcf_mensal": -180_000.0, "fcf_acumulado": -180_000.0 * (m + 3),
        }
        for m in (-2, -1)
    ]
    op = []
    acum = -360_000.0
    for t in range(1, 7):
        fcf = -20_000.0 + t * 15_000.0
        acum += fcf
        op.append(
            {
                "mes": t, "mes_contrato": t + 2, "fase": "operacao",
                "faturamento_mensal": 100_000.0 + t * 20_000.0,
                # EBITDA do mes 1 NEGATIVO: custo integral desde a inauguracao (correto).
                "ebitda_mensal": -10_000.0 + t * 12_000.0,
                "fcf_mensal": fcf, "fcf_acumulado": acum,
            }
        )
    return pre + op


def _payload_v1():
    return {
        "versao": "viabilidade_payload_v1",
        "premissas": {"horizonte_meses": 60, "ticket_blended": 120.23},
        "dre": {
            "faturamento": 282_015.62, "deducoes": 1_410.08, "impostos": 18_660.27,
            "custos_op": 152_711.68, "ebitda": 109_233.60, "margem": 0.3873,
        },
        "investimento": {
            "capex_total": 2_000_000.0, "taxa_franquia": 160_000.0,
            "investimento_total": 2_160_000.0, "pmt": 38_348.75,
            "juros_totais": 900_925.18,
        },
        "retorno": {
            "otica": "desalavancada", "retorno_anual_desalavancado": 0.4475,
            "retorno_anual_equity": 0.31, "tir_anual": 0.4221, "vpl": 875_106.66,
            "payback": 29.0,
        },
        "break_even": {"unidade": "alunos_totais", "ebitda": 859.6, "caixa": 1_366.7},
        "aluguel_teto": {
            "base": "faturamento_bruto", "ideal": 42_302.34, "teto": 56_403.12,
            "excecao": 84_604.69, "canonico": 84_604.69, "teto_p10": None,
        },
        "faixa_alunos": {"p10": 1800, "p90": 2600, "n_comparaveis": 12},
        "serie_mensal": _serie_payload(),
        "mes_caixa_operacional_positivo": 6,
        "acumulado_mes_final": 1_636_628.61,
        "flag_fora_envelope": False,
    }


def test_payload_ausente_devolve_none():
    """Fallback gracioso: sem payload nao ha slide de viabilidade (PDF inalterado)."""
    assert montar_payload_pdf_viabilidade(None) is None
    assert montar_payload_pdf_viabilidade({}) is None


def test_render_puro_le_os_kpis_do_payload():
    viab = montar_payload_pdf_viabilidade(_payload_v1(), incluir_graficos=False)
    assert viab is not None
    # aluguel-teto impresso = canonico (30% do faturamento), nao a inversao por margem.
    assert viab["aluguel_teto"] == 84_604.69
    assert viab["aluguel_teto_faixas"]["ideal"] == 42_302.34
    # break-even em alunos TOTAIS, rotulado.
    assert viab["alunos_breakeven"] == 859.6
    assert viab["breakeven_caixa"] == 1_366.7
    assert viab["breakeven_unidade"] == "alunos_totais"
    # payback e retorno vem do MESMO lugar que a tela le.
    assert viab["payback_meses"] == 29.0
    assert viab["retorno_anual"] == 0.4475
    assert viab["retorno_otica"] == "desalavancada"
    # PMT / juros totais deixam de sumir do relatorio.
    assert viab["pmt_mensal"] == 38_348.75
    assert viab["juros_totais"] == 900_925.18
    assert viab["margem_ebitda_pct"] == 0.3873
    assert "graficos" not in viab


def test_render_puro_monta_os_quatro_graficos():
    viab = montar_payload_pdf_viabilidade(_payload_v1())
    assert viab is not None
    assert len(viab["graficos"]) == 4
    for png in viab["graficos"]:
        _assert_png_valido(png)


def test_render_puro_sem_serie_so_waterfall():
    payload = {**_payload_v1(), "serie_mensal": []}
    viab = montar_payload_pdf_viabilidade(payload)
    assert viab is not None
    assert len(viab["graficos"]) == 1


def test_payback_do_grafico_vem_do_payload_nao_do_cruzamento():
    """Regressao do defeito 'payback 33 no grafico x 35 no card'.

    O marco e o `retorno.payback` recebido. Sem payback nao ha linha nenhuma (antes o
    grafico recalculava o cruzamento da serie e marcava um mes proprio).
    """
    serie = _serie_payload()
    sem_marco = grafico_fcf_acumulado(serie, payback_meses=None)
    com_marco = grafico_fcf_acumulado(serie, payback_meses=5.0)
    outro_marco = grafico_fcf_acumulado(serie, payback_meses=2.0)
    _assert_png_valido(sem_marco)
    assert sem_marco != com_marco
    assert com_marco != outro_marco


def test_fco_le_fcf_mensal_da_serie_do_nucleo():
    """O grafico de resultado mensal usa `fcf_mensal` (nome canonico da serie unica)."""
    serie = _serie_payload()
    legado = [{"mes": r["mes"], "fcf": r["fcf_mensal"]} for r in serie]
    assert grafico_fco(serie, mes_positivo=6) == grafico_fco(legado, mes_positivo=6)


def test_pdf_do_payload_mantem_a_contagem_de_paginas():
    """Slide de numeros + slide de graficos = as MESMAS 2 paginas de sempre."""
    from motor_expansao.dashboard.censo_report import gerar_pdf_relatorio_pontual_classico

    viab = montar_payload_pdf_viabilidade(_payload_v1())
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        {"lat": -23.31, "lng": -51.16, "nome_municipio": "LONDRINA", "uf": "PR", "raio_km": 1.5},
        None,
        viabilidade=viab,
    )
    assert b"/Count 9" in pdf_bytes
    assert b"R$ 84.604,69" in pdf_bytes      # aluguel-teto canonico
    assert b"29 meses" in pdf_bytes          # payback do payload
    assert b"R$ 900.925,18" in pdf_bytes     # juros totais (antes sumiam do relatorio)
    assert b"R$ 38.348,75" in pdf_bytes      # PMT
    assert b"860" in pdf_bytes               # break-even EBITDA em alunos totais
    assert b"1.367" in pdf_bytes             # break-even de caixa
    assert b"Break-even" in pdf_bytes        # rotulo da unidade


# --------------------------------------------------------------------------- #
# Anuidade VISIVEL (FIN-VIAB-01): a linha de receita nao pode ficar embutida     #
# --------------------------------------------------------------------------- #
def _payload_com_anuidade():
    """Golden Boulevard Londrina com a anuidade LIGADA (regime pleno no mes 12)."""
    payload = _payload_v1()
    payload["premissas"] = {
        **payload["premissas"],
        "maturacao_meses": 8,
        "anuidade_valor": 99.0,
        "anuidade_mes_inicio": 12,
        "anuidade_apenas_balcao": True,
        "anuidade_elegivel_pct": 0.4759,
        # max(maturacao 8, anuidade_mes_inicio 12) = 12. SERVIDO, nunca recalculado.
        "mes_referencia_steady": 12,
    }
    payload["dre"] = {
        **payload["dre"],
        "faturamento": 288_257.57,
        "receita_anuidade": 6_241.94,
        "deducoes": 1_441.29,
        "receita_liquida": 286_816.28,
        "impostos": 19_073.28,
        "receita_pos_impostos": 267_743.00,
        "custos_op": 154_583.31,
        "ebitda": 113_159.69,
        "margem": 0.3926,
    }
    return payload


def test_waterfall_parte_o_faturamento_quando_ha_anuidade():
    """A anuidade vira BARRA propria; sem ela o grafico volta a barra unica."""
    comum = dict(
        faturamento_bruto=288_257.57,
        receita_liquida=286_816.28,
        receita_pos_impostos=267_743.00,
        ebitda=113_159.69,
    )
    sem = grafico_dre_waterfall(**comum)
    com = grafico_dre_waterfall(**comum, receita_anuidade=6_241.94)
    _assert_png_valido(sem)
    _assert_png_valido(com)
    assert sem != com
    # Anuidade zerada = cenario sem anuidade (nenhuma barra extra inventada).
    assert grafico_dre_waterfall(**comum, receita_anuidade=0.0) == sem


def test_waterfall_rotula_o_mes_de_referencia_do_payload():
    """O mes vem SERVIDO (`premissas.mes_referencia_steady`), nunca de `maturacao_meses`."""
    comum = dict(
        faturamento_bruto=288_257.57,
        receita_liquida=286_816.28,
        receita_pos_impostos=267_743.00,
        ebitda=113_159.69,
        receita_anuidade=6_241.94,
    )
    mes_12 = grafico_dre_waterfall(**comum, mes_referencia=12)
    mes_8 = grafico_dre_waterfall(**comum, mes_referencia=8)
    _assert_png_valido(mes_12)
    assert mes_12 != mes_8
    assert mes_12 != grafico_dre_waterfall(**comum)  # sem mes -> titulo generico


def test_render_puro_expoe_a_anuidade_e_o_mes_de_referencia():
    """O slide recebe a linha de anuidade e o mes do regime pleno, so LENDO o payload."""
    viab = montar_payload_pdf_viabilidade(_payload_com_anuidade(), incluir_graficos=False)
    assert viab is not None
    assert viab["receita_anuidade"] == 6_241.94
    assert viab["anuidade_valor"] == 99.0
    assert viab["anuidade_mes_inicio"] == 12
    assert viab["anuidade_apenas_balcao"] is True
    assert viab["anuidade_elegivel_pct"] == 0.4759
    # Regime pleno = max(maturacao, anuidade_mes_inicio); a ponte NAO recalcula nada:
    # le o campo servido, que difere de `maturacao_meses` (8).
    assert viab["mes_referencia_steady"] == 12
    assert viab["faturamento_mensal"] == 288_257.57


def test_pdf_imprime_a_linha_de_anuidade_sem_mudar_a_contagem_de_paginas():
    """A anuidade aparece por extenso no slide de numeros; o PDF segue com 9 paginas."""
    from motor_expansao.dashboard.censo_report import gerar_pdf_relatorio_pontual_classico

    viab = montar_payload_pdf_viabilidade(_payload_com_anuidade())
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        {"lat": -23.31, "lng": -51.16, "nome_municipio": "LONDRINA", "uf": "PR", "raio_km": 1.5},
        None,
        viabilidade=viab,
    )
    assert b"/Count 9" in pdf_bytes          # contagem/ordem de paginas INALTERADAS
    assert b"R$ 288.257,57" in pdf_bytes      # faturamento bruto do mes 12
    assert b"R$ 6.241,94" in pdf_bytes        # a parcela de ANUIDADE, agora visivel
    assert b"R$ 99,00" in pdf_bytes           # valor cobrado 1x/ano
    assert b"47,6%" in pdf_bytes              # elegibilidade derivada do churn
    assert b"pro-rata mensal" in pdf_bytes
    # "mes" sai acentuado em latin-1 e o fpdf2 escapa os parenteses do literal PDF.
    assert b"Steady-state = m\xeas 12 \\(regime pleno\\)" in pdf_bytes


def test_pdf_sem_anuidade_nao_inventa_a_linha():
    """Cenario com anuidade desligada: nada de 'mensalidades + anuidade' no slide."""
    from motor_expansao.dashboard.censo_report import gerar_pdf_relatorio_pontual_classico

    payload = _payload_com_anuidade()
    payload["premissas"] = {**payload["premissas"], "anuidade_valor": 0.0,
                            "mes_referencia_steady": 8}
    payload["dre"] = {**payload["dre"], "receita_anuidade": 0.0}
    viab = montar_payload_pdf_viabilidade(payload)
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        {"lat": -23.31, "lng": -51.16, "nome_municipio": "LONDRINA", "uf": "PR", "raio_km": 1.5},
        None,
        viabilidade=viab,
    )
    assert b"/Count 9" in pdf_bytes
    assert b"todo de mensalidades" in pdf_bytes
    assert b"Steady-state = m\xeas 8 \\(regime pleno\\)" in pdf_bytes
    assert b"R$ 6.241,94" not in pdf_bytes


# --------------------------------------------------------------------------- #
# FOLHA FIXA DESDE O MES 1 + FRANQUIA PARCELADA (decisoes de Felipe 2026-07-24)  #
# --------------------------------------------------------------------------- #
def _payload_folha_fixa():
    """Golden Boulevard Londrina da 3a rodada: folha FIXA e franquia em 4x."""
    payload = _payload_com_anuidade()
    payload["premissas"] = {
        **payload["premissas"],
        "folha_pct": 0.17,
        "folha_fixa_mes": 49_003.79,
        "folha_base_faturamento_maduro": 288_257.57,
        "folha_fixa_desde_mes_1": True,
    }
    # As tres parcelas FECHAM no custo_op do golden: 37.429,52 (13,05% da liquida)
    # + 49.003,79 (folha fixa) + 68.150,00 (outros fixos 38.150 + aluguel 30.000).
    payload["dre"] = {
        **payload["dre"],
        "custos_op": 154_583.31,
        "custos_variaveis": 37_429.52,
        "folha": 49_003.79,
        "custos_fixos": 68_150.00,
    }
    payload["investimento"] = {
        **payload["investimento"],
        "parcelas_obra": 4,
        "parcelas_franquia": 4,
    }
    return payload


def test_render_puro_expoe_a_folha_fixa_e_o_parcelamento_da_franquia():
    """A ponte LE as duas linhas novas do payload; nao recompoe custo nem cronograma."""
    viab = montar_payload_pdf_viabilidade(_payload_folha_fixa(), incluir_graficos=False)
    assert viab is not None
    assert viab["folha"] == 49_003.79
    assert viab["custos_variaveis"] == 37_429.52
    assert viab["custos_fixos"] == 68_150.00
    assert viab["custos_op"] == 154_583.31
    assert viab["folha_pct"] == 0.17
    assert viab["parcelas_franquia"] == 4
    assert viab["taxa_franquia"] == 160_000.0


def test_pdf_diz_que_a_folha_e_fixa_desde_o_mes_1():
    """O defeito reportado era o leitor supor que a folha escala com a rampa."""
    from motor_expansao.dashboard.censo_report import gerar_pdf_relatorio_pontual_classico

    viab = montar_payload_pdf_viabilidade(_payload_folha_fixa())
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        {"lat": -23.31, "lng": -51.16, "nome_municipio": "LONDRINA", "uf": "PR", "raio_km": 1.5},
        None,
        viabilidade=viab,
    )
    assert b"/Count 9" in pdf_bytes             # contagem/ordem de paginas INALTERADAS
    assert b"R$ 49.003,79" in pdf_bytes          # a folha, agora visivel como linha
    # "mes" sai acentuado em latin-1; o fpdf2 escapa os parenteses do literal PDF.
    assert b"FIXA desde o m\xeas 1" in pdf_bytes
    assert b"dimensionada por 17,0% do faturamento maduro" in pdf_bytes
    assert b"R$ 37.429,52" in pdf_bytes          # custo variavel
    assert b"R$ 68.150,00" in pdf_bytes          # fixos + aluguel


def test_pdf_diz_que_a_taxa_de_franquia_e_parcelada_sem_juros():
    """A franquia deixou de sair inteira no M-4: 4x sem juros, junto da obra."""
    from motor_expansao.dashboard.censo_report import gerar_pdf_relatorio_pontual_classico

    viab = montar_payload_pdf_viabilidade(_payload_folha_fixa())
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        {"lat": -23.31, "lng": -51.16, "nome_municipio": "LONDRINA", "uf": "PR", "raio_km": 1.5},
        None,
        viabilidade=viab,
    )
    assert b"/Count 9" in pdf_bytes
    assert b"parcelada em 4x sem juros" in pdf_bytes
    assert b"R$ 160.000,00 parcelada" in pdf_bytes


def test_pdf_sem_parcelas_franquia_nao_afirma_parcelamento():
    """Degradacao graciosa: sem o campo novo o PDF nao inventa numero de parcelas."""
    from motor_expansao.dashboard.censo_report import gerar_pdf_relatorio_pontual_classico

    payload = _payload_folha_fixa()
    payload["investimento"] = {
        k: v for k, v in payload["investimento"].items() if k != "parcelas_franquia"
    }
    viab = montar_payload_pdf_viabilidade(payload)
    assert viab is not None and viab["parcelas_franquia"] is None
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        {"lat": -23.31, "lng": -51.16, "nome_municipio": "LONDRINA", "uf": "PR", "raio_km": 1.5},
        None,
        viabilidade=viab,
    )
    assert b"/Count 9" in pdf_bytes
    assert b"sem juros" not in pdf_bytes
    assert b"Taxa de franquia" not in pdf_bytes
    # A linha de financiamento continua inteira.
    assert b"investimento total" in pdf_bytes


def test_pdf_sem_folha_no_payload_nao_inventa_a_linha():
    """Payload legado (sem `dre.folha`) sai exatamente como antes."""
    from motor_expansao.dashboard.censo_report import gerar_pdf_relatorio_pontual_classico

    viab = montar_payload_pdf_viabilidade(_payload_v1())
    assert viab is not None and viab["folha"] is None
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        {"lat": -23.31, "lng": -51.16, "nome_municipio": "LONDRINA", "uf": "PR", "raio_km": 1.5},
        None,
        viabilidade=viab,
    )
    assert b"/Count 9" in pdf_bytes
    assert b"FIXA desde o m\xeas 1" not in pdf_bytes


def test_eixo_do_ebitda_acomoda_o_mes_1_mais_negativo():
    """O vale do mes 1 dobrou de profundidade; o eixo tem de descer com ele.

    Regressao do risco apontado no FIN-VIAB-01 (3a rodada): com a folha fixa o EBITDA do
    mes 1 caiu de -R$10.139,56 para -R$43.464,47.
    """
    fat = [36_032.20, 288_257.57]
    lo, hi = limites_y_faturamento_ebitda(fat, [-43_464.47, 113_159.69])
    assert lo < -43_464.47          # o vale cabe, com folga
    assert hi > 288_257.57          # e a barra mais alta nao e cortada
    lo_antigo, _ = limites_y_faturamento_ebitda(fat, [-10_139.56, 113_159.69])
    assert lo < lo_antigo           # o piso desce junto com o vale
    # Sem dado utilizavel nao se inventa limite (autoscale do matplotlib decide).
    assert limites_y_faturamento_ebitda([], []) is None
    assert limites_y_faturamento_ebitda([0.0], [0.0]) is None


def test_grafico_faturamento_ebitda_muda_com_a_profundidade_do_vale():
    """O PNG reflete o mes 1 mais negativo (nao e um render insensivel ao dado)."""
    base = [
        {"mes": t, "fase": "operacao", "faturamento_mensal": 36_032.20 * min(t, 8),
         "ebitda_mensal": 113_159.69 if t >= 8 else -10_139.56}
        for t in range(1, 13)
    ]
    fundo = [{**linha, "ebitda_mensal": -43_464.47 if linha["mes"] < 8 else 113_159.69}
             for linha in base]
    raso = grafico_faturamento_ebitda(base)
    profundo = grafico_faturamento_ebitda(fundo)
    _assert_png_valido(raso)
    _assert_png_valido(profundo)
    assert raso != profundo


def test_pdf_aceita_o_payload_v1_cru():
    """O slide le o proprio `viabilidade_payload_v1` (forma que o backend ja entrega)."""
    from motor_expansao.dashboard.censo_report import gerar_pdf_relatorio_pontual_classico

    payload = dict(_payload_v1())
    payload["graficos"] = []  # sem PNGs -> 1 pagina de numeros
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        {"lat": -23.31, "lng": -51.16, "nome_municipio": "LONDRINA", "uf": "PR", "raio_km": 1.5},
        None,
        viabilidade=payload,
    )
    assert b"/Count 8" in pdf_bytes
    assert b"R$ 84.604,69" in pdf_bytes    # canonico do aluguel-teto, direto da secao v1
    assert b"29 meses" in pdf_bytes        # retorno.payback
    assert b"R$ 900.925,18" in pdf_bytes   # investimento.juros_totais
    assert b"1.367" in pdf_bytes           # break_even.caixa
