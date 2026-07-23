"""Testes do BLK-RELVIAB-02: pagina de INFORMACOES do imovel no PDF.

Cobre o formatador `_info_valor` e a insercao OPCIONAL da pagina de info nos dois
geradores (default None -> PDF inalterado). Usa um `result` minimo + `mapas=None`
(os geradores toleram; a pagina de mapas cai no fallback textual). Sem PII.
"""

from __future__ import annotations

from motor_expansao.dashboard.censo_report import (
    _info_valor,
    gerar_pdf_relatorio_pontual_censitario,
    gerar_pdf_relatorio_pontual_classico,
)

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


def test_info_valor_texto():
    assert _info_valor("Galpão", "texto") == "Galpão"


def test_info_valor_zero_num_mostra_zero_nao_nd():
    # BLK-RELVIAB-06 (claude-review MEDIA): 0 vagas e valor VALIDO (imovel sem vaga) -> "0".
    assert _info_valor(0, "num") == "0"
    assert _info_valor(0.0, "num2") == "0,00"


def test_info_valor_ausente_ou_vazio_vira_nd():
    assert _info_valor(None, "num") == "n/d"
    assert _info_valor("", "texto") == "n/d"
    assert _info_valor("   ", "texto") == "n/d"


def test_info_valor_nao_numerico_em_campo_num_nao_quebra():
    assert _info_valor("s/ medida", "num") == "s/ medida"


# --------------------------------------------------------------------------- #
# Insercao da pagina (OPCIONAL)                                               #
# --------------------------------------------------------------------------- #
def test_classico_sem_info_mantem_6_paginas():
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(_MIN_RESULT, None)
    assert b"/Count 8" in pdf_bytes
    assert _TITULO not in pdf_bytes


def test_classico_com_info_adiciona_pagina_e_titulo():
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(_MIN_RESULT, None, info_imovel=_INFO_OK)
    assert b"/Count 9" in pdf_bytes
    assert _TITULO in pdf_bytes
    assert b"R$ 20.000,00" in pdf_bytes  # valor formatado do aluguel


def test_censitario_com_info_adiciona_pagina():
    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(_MIN_RESULT, None, info_imovel=_INFO_OK)
    assert b"/Count 9" in pdf_bytes
    assert _TITULO in pdf_bytes


def test_info_com_campos_ausentes_usa_nd_sem_quebrar():
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        _MIN_RESULT, None, info_imovel={"metragem_m2": 1200}
    )
    assert b"/Count 9" in pdf_bytes
    assert b"n/d" in pdf_bytes  # campos nao informados aparecem como n/d


def test_fotos_e_info_juntas_somam_duas_paginas():
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (640, 480), (100, 160, 90)).save(buf, format="JPEG")
    foto = buf.getvalue()
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        _MIN_RESULT, None, fotos=[foto, foto], info_imovel=_INFO_OK
    )
    assert b"/Count 10" in pdf_bytes  # capa + fotos + info + 4 conteudo + credito
