"""Reancoragem da paleta de score do motor compartilhado (DEC-022).

Estes invariantes viviam em tests/integration/test_streamlit_app.py (Bloco 9:
score_band_to_color e padronizacao visual), que sera deletado no corte do
Streamlit. A paleta agora e' travada aqui, direto contra a funcao pura em
motor_expansao.dashboard.utils — o piloto web e os PDFs dependem das MESMAS
cores por faixa, entao qualquer mudanca de banda/cor precisa quebrar um teste.
"""

from __future__ import annotations

import numpy as np

from motor_expansao.dashboard.constants import RESIDUAL_SCORE_BANDS
from motor_expansao.dashboard.utils import (
    _censo_score_to_color,
    hex_to_rgba,
    score_band_to_color,
)

# Cinza neutro reservado a score ausente: hex sem score nao pode "parecer ruim"
# (vermelho) nem "parecer bom" (verde) no mapa.
_CINZA_SEM_SCORE = [120, 120, 140, 70]


def test_score_nan_ou_none_retorna_cinza_neutro():
    # NaN nao e' None: o bug classico de guarda `is not None` deixava NaN passar
    # e estourar na conversao (mesma causa raiz do BLK-FIX de format_int).
    assert score_band_to_color(float("nan")) == _CINZA_SEM_SCORE
    assert score_band_to_color(np.nan) == _CINZA_SEM_SCORE
    assert score_band_to_color(None) == _CINZA_SEM_SCORE


def test_score_nan_ignora_alpha_customizado():
    # O cinza de "sem score" e' fixo por design: um alpha customizado do caller
    # nao deve tornar hexes sem dado mais visiveis do que hexes com dado.
    assert score_band_to_color(float("nan"), alpha=255) == _CINZA_SEM_SCORE


def test_bordas_de_faixa_a_cada_10_pontos():
    # As faixas sao fechadas embaixo e abertas em cima ([10, 20)): 9.99 ainda e'
    # a primeira faixa, 10.0 ja e' a segunda. Se isso mudar, a legenda do mapa
    # deixa de corresponder as cores renderizadas.
    c0 = score_band_to_color(0)
    c9_99 = score_band_to_color(9.99)
    c10 = score_band_to_color(10)
    c49_9 = score_band_to_color(49.9)
    c50 = score_band_to_color(50)
    c89_9 = score_band_to_color(89.9)
    c90 = score_band_to_color(90)
    c100 = score_band_to_color(100)

    assert c0 == c9_99, "0 e 9.99 devem estar na mesma faixa (0-10)"
    assert c0 != c10, "9.99 e 10 devem estar em faixas distintas"
    assert c49_9 != c50, "49.9 e 50 devem estar em faixas distintas"
    assert c89_9 != c90, "89.9 e 90 devem estar em faixas distintas"
    assert c90 == c100, "90 e 100 devem cair na mesma faixa (90-100)"


def test_score_100_nao_estoura_para_faixa_inexistente():
    # 100 // 10 = 10, mas so existem 10 faixas (indices 0-9): o clamp precisa
    # segurar o score maximo dentro da faixa 90-100 em vez de IndexError.
    assert score_band_to_color(100) == score_band_to_color(95)


def test_score_fora_de_faixa_satura_nos_extremos():
    # Scores fora de 0-100 nao existem no contrato do M1, mas dados sujos nao
    # podem derrubar o mapa: acima de 100 satura no verde maximo, negativo
    # satura no vermelho minimo.
    assert score_band_to_color(150) == score_band_to_color(95)
    assert score_band_to_color(-5) == score_band_to_color(0)


def test_escala_ascendente_vermelho_para_verde():
    # Semantica da paleta: score baixo = vermelho (ruim), score alto = verde
    # (bom). Inverter isso mudaria a leitura executiva do mapa inteiro.
    r_baixa, g_baixa, _ = score_band_to_color(5)[:3]
    r_alta, g_alta, _ = score_band_to_color(95)[:3]
    assert g_alta > r_alta, "score alto deve ser mais verde do que vermelho"
    assert r_baixa > g_baixa, "score baixo deve ser mais vermelho do que verde"


def test_retorna_rgba_com_4_componentes_validos():
    # Contrato com o deck.gl (fill_color): lista RGBA com componentes 0-255.
    cor = score_band_to_color(50)
    assert len(cor) == 4
    assert all(0 <= v <= 255 for v in cor)


def test_dez_faixas_todas_com_cores_distintas():
    # A legenda exibe 10 faixas; se duas colapsarem na mesma cor a legenda
    # mente. O ponto medio de cada faixa garante que nao ha empate.
    cores = [tuple(score_band_to_color(faixa * 10 + 5)) for faixa in range(10)]
    assert len(set(cores)) == 10


def test_consistencia_com_residual_score_bands_de_constants():
    # A fonte canonica da paleta e' RESIDUAL_SCORE_BANDS: a cor de cada faixa
    # deve ser exatamente o hex declarado la (convertido com o alpha default).
    # Isso impede a funcao de divergir silenciosamente da constante que os
    # outros consumidores (legenda, piloto web, PDFs) leem.
    assert len(RESIDUAL_SCORE_BANDS) == 10
    for idx, (_, color_hex) in enumerate(RESIDUAL_SCORE_BANDS):
        ponto_medio = idx * 10 + 5
        assert score_band_to_color(ponto_medio) == hex_to_rgba(color_hex, 170)


def test_alpha_customizado_altera_somente_o_canal_alpha():
    # Callers (ex.: camadas com transparencia diferente) podem pedir outro
    # alpha sem que o RGB da faixa mude.
    padrao = score_band_to_color(73)
    opaco = score_band_to_color(73, alpha=255)
    assert opaco[:3] == padrao[:3]
    assert opaco[3] == 255
    assert padrao[3] == 170


def test_censo_score_to_color_delega_para_score_band_to_color():
    # _censo_score_to_color ficou como alias de compatibilidade: se deixar de
    # delegar, consumidores antigos voltam a paleta de 4 faixas do censo.
    assert _censo_score_to_color(60) == score_band_to_color(60)
    assert _censo_score_to_color(float("nan")) == score_band_to_color(float("nan"))
