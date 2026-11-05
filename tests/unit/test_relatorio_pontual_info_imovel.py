"""Testes do BLK-RELVIAB-02: pagina de INFORMACOES do imovel no PDF.

Cobre o formatador `_info_valor` e a insercao OPCIONAL da pagina de info nos dois
geradores (default None -> PDF inalterado). Usa um `result` minimo + `mapas=None`
(os geradores toleram; a pagina de mapas cai no fallback textual). Sem PII.
"""

from __future__ import annotations

import pytest

from motor_expansao.dashboard.censo_report import (
    _info_valor,
    gerar_pdf_relatorio_pontual_censitario,
    gerar_pdf_relatorio_pontual_classico,
)
from motor_expansao.dashboard.constants import TEXTO_SEM_DADO

_MIN_RESULT = {
    "lat": -23.55,
    "lng": -46.63,
    "nome_municipio": "SAO PAULO",
    "uf": "SP",
    "raio_km": 1.5,
}

_INFO_OK = {
    "endereco": "Rua Teste, 123 - Sao Paulo/SP",
    "metragem_m2": 1500,
    "aluguel_pedido": 20000,
    "valor_venda": 3_500_000,
    "pe_direito_m": 4.2,
    "vagas": 30,
    "tipo_imovel": "Galpão",
    "observacoes": "Esquina com boa visibilidade e fluxo de pedestres.",
}

_TITULO = "Im\xf3vel - Informa\xe7\xf5es".encode("latin-1")


# --------------------------------------------------------------------------- #
# _info_valor                                                                 #
# --------------------------------------------------------------------------- #
def test_info_valor_brl():
    assert _info_valor(20000, "brl") == "R$ 20.000,00"


def test_info_valor_num_e_num2():
    assert _info_valor(1500, "num") == "1.500"
    assert _info_valor(4.2, "num2") == "4,20"


def test_info_valor_com_unidade_depois_do_numero():
    assert _info_valor(1500, "m2") == "1.500 m²"
    assert _info_valor(4.5, "metros") == "4,50 m"
    assert _info_valor(None, "m2") == TEXTO_SEM_DADO


def test_info_valor_texto():
    assert _info_valor("Galpão", "texto") == "Galpão"


def test_info_valor_zero_num_mostra_zero_nao_nd():
    # BLK-RELVIAB-06 (claude-review MEDIA): 0 vagas e valor VALIDO (imovel sem vaga) -> "0".
    assert _info_valor(0, "num") == "0"
    assert _info_valor(0.0, "num2") == "0,00"


def test_info_valor_ausente_ou_vazio_vira_nd():
    assert _info_valor(None, "num") == TEXTO_SEM_DADO
    assert _info_valor("", "texto") == TEXTO_SEM_DADO
    assert _info_valor("   ", "texto") == TEXTO_SEM_DADO


def test_info_valor_nao_numerico_em_campo_num_nao_quebra():
    assert _info_valor("s/ medida", "num") == "s/ medida"


# --------------------------------------------------------------------------- #
# Insercao da pagina (OPCIONAL)                                               #
# --------------------------------------------------------------------------- #
def test_classico_sem_info_mantem_7_paginas():
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(_MIN_RESULT, None)
    # BLK-RELPON-14: o PDF base caiu de 8 para 7 paginas (a "Imagem do Entorno" saiu).
    assert b"/Count 7" in pdf_bytes
    assert _TITULO not in pdf_bytes


def test_classico_com_info_adiciona_pagina_e_titulo():
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(_MIN_RESULT, None, info_imovel=_INFO_OK)
    assert b"/Count 8" in pdf_bytes
    assert _TITULO in pdf_bytes
    assert b"R$ 20.000,00" in pdf_bytes  # valor formatado do aluguel


def test_censitario_com_info_adiciona_pagina():
    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(_MIN_RESULT, None, info_imovel=_INFO_OK)
    assert b"/Count 8" in pdf_bytes
    assert _TITULO in pdf_bytes


def test_info_com_campos_ausentes_usa_nd_sem_quebrar():
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        _MIN_RESULT, None, info_imovel={"metragem_m2": 1200}
    )
    assert b"/Count 8" in pdf_bytes
    # Campos nao informados aparecem por extenso (era a sigla "n/d" ate 2026-07-31).
    assert TEXTO_SEM_DADO.encode("latin-1") in pdf_bytes


def test_fotos_e_info_juntas_somam_duas_paginas():
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (640, 480), (100, 160, 90)).save(buf, format="JPEG")
    foto = buf.getvalue()
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        _MIN_RESULT, None, fotos=[foto, foto], info_imovel=_INFO_OK
    )
    assert b"/Count 9" in pdf_bytes  # capa + fotos + info + 5 conteudo + credito


# --------------------------------------------------------------------------- #
# DEC-080: o card de aluguel de referência no lugar do valor de venda          #
# --------------------------------------------------------------------------- #
def test_card_do_valor_de_venda_deu_lugar_ao_aluguel_de_referencia():
    from motor_expansao.dashboard.censo_report import _INFO_IMOVEL_CAMPOS

    chaves = [chave for chave, _, _ in _INFO_IMOVEL_CAMPOS]
    assert "valor_venda" not in chaves
    assert "aluguel_referencia" in chaves


def test_card_de_aluguel_imprime_o_bloco_ou_nd(monkeypatch):
    from motor_expansao.dashboard import censo_report

    chamadas = []
    original = censo_report._info_card_aluguel_referencia

    def _espiao(pdf, bloco, *args, **kwargs):
        chamadas.append(bloco)
        return original(pdf, bloco, *args, **kwargs)

    monkeypatch.setattr(censo_report, "_info_card_aluguel_referencia", _espiao)
    bloco = {
        "faixa_min": 27600,
        "faixa_max": 43700,
        "rs_m2_p25": 18.4,
        "rs_m2_p75": 29.1,
        "base": "Base: 12 anúncios de comercial em São José dos Campos/SP",
        "mediana": 33800,
        "diferenca_pct": 10,
        "comparacao": "42% acima da mediana · 10% acima da faixa",
    }
    gerar_pdf_relatorio_pontual_classico(
        _MIN_RESULT, None, info_imovel={**_INFO_OK, "aluguel_referencia": bloco}
    )
    gerar_pdf_relatorio_pontual_classico(_MIN_RESULT, None, info_imovel=_INFO_OK)
    assert chamadas == [bloco, None]


def test_card_de_aluguel_com_bloco_malformado_cai_em_nd_sem_quebrar():
    bloco = {"faixa_min": "abc", "diferenca_pct": "5", "comparacao": "x"}
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        _MIN_RESULT, None, info_imovel={**_INFO_OK, "aluguel_referencia": bloco}
    )
    assert _TITULO in pdf_bytes


def test_comparacao_vai_no_card_do_aluguel_pedido(monkeypatch):
    """A comparacao e' do aluguel PEDIDO: sai debaixo do valor dele, nao no card da regiao."""
    from motor_expansao.dashboard import censo_report

    chamadas = []
    monkeypatch.setattr(
        censo_report,
        "_info_card_comparacao_aluguel",
        lambda pdf, bloco, x, y, largura: chamadas.append((bloco, x)),
    )
    bloco = {"faixa_min": 27600, "faixa_max": 43700, "diferenca_pct": 10, "comparacao": "x"}
    gerar_pdf_relatorio_pontual_classico(
        _MIN_RESULT, None, info_imovel={**_INFO_OK, "aluguel_referencia": bloco}
    )
    assert len(chamadas) == 1 and chamadas[0][0] is bloco


@pytest.mark.parametrize(
    ("pct_faixa", "pct_mediana", "cor"),
    [
        (10, 42, "_INFO_ALUGUEL_ACIMA_RGB"),
        (0, 18, "_INFO_ALUGUEL_MEDIANA_RGB"),
        (0, 0, "_INFO_ALUGUEL_DENTRO_RGB"),
        (0, -11, "_INFO_ALUGUEL_DENTRO_RGB"),
        (-9, -26, "_INFO_ALUGUEL_DENTRO_RGB"),
    ],
)
def test_cor_da_comparacao(monkeypatch, pct_faixa, pct_mediana, cor):
    """Vermelho acima da faixa, ambar acima da mediana, verde no resto (Felipe, 05/11/2026)."""
    from motor_expansao.dashboard import censo_report

    cores = []

    class _Pdf:
        def set_text_color(self, *rgb):
            cores.append(rgb)

        def __getattr__(self, _nome):
            return lambda *a, **k: None

    bloco = {"comparacao": "x", "diferenca_pct": pct_faixa, "diferenca_mediana_pct": pct_mediana}
    monkeypatch.setattr(censo_report, "_ajustar_fonte_para_largura", lambda *a, **k: None)
    censo_report._info_card_comparacao_aluguel(_Pdf(), bloco, 0, 0, 200)
    assert cores == [getattr(censo_report, cor)]
