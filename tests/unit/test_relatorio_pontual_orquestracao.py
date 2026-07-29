"""Testes do BLK-RELVIAB-05: orquestracao do relatorio completo.

Cobre (a) o assembler `montar_payload_viabilidade` (engine -> dict do PDF), (b) o threading
dos params novos pelo dispatcher `gerar_payloads_download_relatorio_censitario`, (c) a
regressao (sem params novos -> /Count 7) e (d) o caminho end-to-end com o motor real
`analisar_viabilidade_ponto`. Sem PII.
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from motor_expansao.dashboard.censo_report import (
    gerar_payloads_download_relatorio_censitario,
)
from motor_expansao.dashboard.viabilidade_charts import montar_payload_viabilidade
from motor_expansao.dimensionamento.simulador import gerar_serie_mensal
from motor_expansao.dimensionamento.viabilidade_ponto import analisar_viabilidade_ponto

_MIN_RESULT = {"lat": -23.55, "lng": -46.63, "nome_municipio": "SAO PAULO", "uf": "SP", "raio_km": 1.5}


def _png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (200, 150), (0, 167, 157)).save(buf, format="PNG")
    return buf.getvalue()


def _viab_result():
    return analisar_viabilidade_ponto(-23.55, -46.63, 1500.0, 20000.0, 800.0)


# --------------------------------------------------------------------------- #
# Assembler engine -> dict                                                    #
# --------------------------------------------------------------------------- #
def test_assembler_monta_chaves_numericas():
    payload = montar_payload_viabilidade(_viab_result(), incluir_graficos=False)
    for chave in (
        "alunos_breakeven",
        "aluguel_teto",
        "margem_ebitda_pct",
        "payback_meses",
        "roic_anual",
        "faturamento_mensal",
        "ebitda_mensal",
        "flag_viavel",
        "flag_fora_envelope",
    ):
        assert chave in payload
    assert "graficos" not in payload  # incluir_graficos=False


def test_assembler_sem_serie_so_waterfall():
    payload = montar_payload_viabilidade(_viab_result())
    assert len(payload["graficos"]) == 1  # so o waterfall


def test_assembler_com_serie_quatro_graficos():
    serie = gerar_serie_mensal(
        alunos_maturidade=800.0, m2=1500.0, aluguel_mes=20000.0, ticket_medio=137.0
    )
    # Item Felipe 2026-07-23: o 1o grafico agora e' o Fluxo de Caixa Operacional (substitui a
    # rampa de alunos). Ele depende da serie de FCO (obras M-4..operacao) que o backend calcula
    # e passa via `fco_serie`; sem ela o assembler cai no waterfall-only (3 graficos).
    fco_serie = [
        {"mes": -4, "fcf": -75000.0},
        {"mes": -3, "fcf": -75000.0},
        {"mes": -2, "fcf": -75000.0},
        {"mes": -1, "fcf": -75000.0},
        {"mes": 1, "fcf": -12000.0},
        {"mes": 2, "fcf": 3000.0},
        {"mes": 6, "fcf": 18000.0},
    ]
    payload = montar_payload_viabilidade(
        _viab_result(), serie, maturacao_mes=8, fco_serie=fco_serie, mes_operacao_positiva=2
    )
    assert len(payload["graficos"]) == 4
    for png in payload["graficos"]:
        assert isinstance(png, bytes) and png[:8] == b"\x89PNG\r\n\x1a\n"


# --------------------------------------------------------------------------- #
# Threading pelo dispatcher                                                   #
# --------------------------------------------------------------------------- #
def test_dispatcher_regressao_sem_params_novos_count_7():
    payloads = gerar_payloads_download_relatorio_censitario(
        _MIN_RESULT, None, template="classico"
    )
    # BLK-RELPON-14: o PDF base caiu de 8 para 7 paginas (a "Imagem do Entorno" saiu).
    assert b"/Count 7" in payloads.pdf_bytes


def test_dispatcher_com_fotos_info_viab_enriquecido():
    payload_viab = {
        "alunos_breakeven": 500,
        "aluguel_teto": 24000.0,
        "margem_ebitda_pct": 0.15,
        "payback_meses": 30.0,
        "roic_anual": 0.2,
        "faturamento_mensal": 140000.0,
        "ebitda_mensal": 21000.0,
        "faixa_p10": 400,
        "faixa_p90": 1000,
        "flag_viavel": True,
        "flag_fora_envelope": False,
        "graficos": [_png(), _png(), _png(), _png()],
    }
    payloads = gerar_payloads_download_relatorio_censitario(
        _MIN_RESULT,
        None,
        template="classico",
        fotos=[_png(), _png()],
        info_imovel={"metragem_m2": 1500},
        viabilidade=payload_viab,
    )
    # capa + fotos + info + 5 conteudo + viab numeros + viab graficos + credito = 11
    assert b"/Count 11" in payloads.pdf_bytes


def test_dispatcher_censitario_tambem_aceita_params():
    payloads = gerar_payloads_download_relatorio_censitario(
        _MIN_RESULT, None, info_imovel={"metragem_m2": 1200}
    )
    assert b"/Count 8" in payloads.pdf_bytes


# --------------------------------------------------------------------------- #
# End-to-end: motor real -> assembler -> PDF                                  #
# --------------------------------------------------------------------------- #
def test_end_to_end_motor_para_pdf():
    serie = gerar_serie_mensal(
        alunos_maturidade=800.0, m2=1500.0, aluguel_mes=20000.0, ticket_medio=137.0
    )
    viabilidade = montar_payload_viabilidade(_viab_result(), serie, maturacao_mes=8)
    payloads = gerar_payloads_download_relatorio_censitario(
        _MIN_RESULT, None, template="classico", viabilidade=viabilidade
    )
    assert b"/Count 9" in payloads.pdf_bytes  # numeros + graficos
    assert len(payloads.pdf_bytes) > 30_000
