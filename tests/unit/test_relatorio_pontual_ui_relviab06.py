"""Testes do BLK-RELVIAB-06: wiring da geracao do relatorio completo na aba Viabilidade.

Nao dirige os widgets do Streamlit (isso e verificacao visual); testa a LOGICA que o botao
"Gerar relatorio" dispara: montagem dos insumos censitarios (com fallback gracioso) + o
caminho engine -> payload -> PDF completo. Sem PII (fotos sinteticas).
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd
from PIL import Image

from motor_expansao.dashboard.censo_report import gerar_payloads_download_relatorio_censitario
from motor_expansao.dashboard.pages import _montar_insumos_censo_pdf
from motor_expansao.dashboard.viabilidade_charts import montar_payload_viabilidade
from motor_expansao.dimensionamento.simulador import gerar_serie_mensal
from motor_expansao.dimensionamento.viabilidade_ponto import analisar_viabilidade_ponto

LAT, LNG = -23.55, -46.63


def _png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (320, 220), (0, 167, 157)).save(buf, format="PNG")
    return buf.getvalue()


def test_insumos_censo_fallback_sem_loader():
    """Sem loader setorial -> mapas None, perfil None, residual n/d; result minimo com o ponto."""
    df = pd.DataFrame({"hex_id": ["semmatch"]})
    ins = _montar_insumos_censo_pdf(
        LAT, LNG, df,
        competitors_df=None, ultra_df=None,
        censo_geo_loader=None, censo_geo_dir=None,
    )
    assert ins["mapas"] is None
    assert ins["perfil_bairro"] is None
    assert ins["result"]["lat"] == LAT and ins["result"]["lng"] == LNG
    assert all(v is None for v in ins["residual"].values())


def test_wiring_do_botao_gera_pdf_completo():
    """Reproduz a sequencia do botao 'Gerar relatorio (PDF)' e valida o PDF completo."""
    df = pd.DataFrame({"hex_id": ["semmatch"]})
    vr = analisar_viabilidade_ponto(LAT, LNG, 1500.0, 20000.0, 800.0)
    serie = gerar_serie_mensal(
        alunos_maturidade=float(vr.alunos_balcao_premissa),
        m2=1500.0, aluguel_mes=20000.0, ticket_medio=137.0,
    )
    viab = montar_payload_viabilidade(vr, serie, maturacao_mes=8)
    ins = _montar_insumos_censo_pdf(
        LAT, LNG, df,
        competitors_df=None, ultra_df=None,
        censo_geo_loader=None, censo_geo_dir=None,
    )
    payloads = gerar_payloads_download_relatorio_censitario(
        ins["result"], ins["mapas"],
        residual=ins["residual"], perfil_bairro=ins["perfil_bairro"],
        template="classico", rotulo="Rua Teste, 1",
        fotos=[_png(), _png()],
        info_imovel={"metragem_m2": 1500, "aluguel_pedido": 20000, "endereco": "Rua Teste, 1"},
        viabilidade=viab,
    )
    # capa + fotos + info + 4 conteudo + viab numeros + viab graficos + credito = 10
    assert b"/Count 10" in payloads.pdf_bytes
    assert payloads.pdf_bytes.startswith(b"%PDF")
    assert len(payloads.pdf_bytes) > 30_000  # PNGs reais embutidos
