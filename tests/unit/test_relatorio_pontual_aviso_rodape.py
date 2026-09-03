"""Bloco C+ — o aviso do perfil VIAJA nas paginas FINANCEIRAS do PDF (decisao 0.7).

O `aviso_rodape` de `gerar_pdf_relatorio_pontual_classico` e o carimbo do aviso de
provisoriedade declarado no perfil da instancia (na AR,
`avisos.viabilidade_tributo_provisorio.texto_rodape`): tem de aparecer em TODAS as
paginas de resultado financeiro — numeros de viabilidade, graficos e a Conclusao com
parecer financeiro — e em NENHUMA outra. Sem o parametro (o caller brasileiro, cujo
perfil tem `avisos` = `{}`), o PDF nao muda um byte.

A contagem por pagina usa a mesma tecnica dos testes vizinhos: o `_UltraPDF` gera SEM
compressao, entao cada `cell()` vira um literal `(texto) Tj` legivel nos bytes crus —
uma ocorrencia por pagina carimbada. Nao ha extrator de PDF no ambiente (pypdf/pypdfium2
nao estao em [dev]) e este arquivo nao adiciona dependencia nova.

NOTA DE AMBIENTE: `censo_report` importa `h3` transitivamente; nas maquinas Windows em
que o pacote nativo nao carrega (WinError 4551, politica de Controle de Aplicativo) o
arquivo inteiro e SKIPPED — quem o roda de verdade e o CI (Linux), como o resto dos
testes de `censo_report`.
"""

from __future__ import annotations

from io import BytesIO

import pytest

pytest.importorskip(
    "h3",
    reason="censo_report importa h3; sem o binario nativo (WinError 4551) so o CI roda",
)

from PIL import Image  # noqa: E402

from motor_expansao.dashboard.censo_report import (  # noqa: E402
    gerar_pdf_relatorio_pontual_classico,
)

_MIN_RESULT = {"lat": -23.55, "lng": -46.63, "nome_municipio": "SAO PAULO", "uf": "SP", "raio_km": 1.5}

# Payload plano de viabilidade (retrocompat aceita por `_viab_normalizado`) — o mesmo
# formato de `test_relatorio_pontual_viabilidade.py`.
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

# O texto REAL do carimbo argentino vem do perfil e e travado por
# tests/contracts/test_aviso_carimbado_no_perfil.py; aqui basta um marcador ASCII
# inequivoco, que nao colide com nenhum texto fixo do relatorio.
_AVISO = "AVISO DE TESTE: simulacao com tributos provisorios."


def _png(w: int = 300, h: int = 200) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), (0, 167, 157)).save(buf, format="PNG")
    return buf.getvalue()


def _ocorrencias(pdf_bytes: bytes, texto: str) -> int:
    """Quantas paginas carimbam `texto`: 1 `cell()` -> 1 literal `(texto) Tj` por
    pagina, nos bytes crus (compressao OFF no `_UltraPDF`)."""
    return pdf_bytes.decode("latin-1", errors="replace").count(texto)


def test_sem_graficos_o_aviso_sai_nas_2_paginas_financeiras() -> None:
    """`viabilidade` sem `graficos` -> numeros + Conclusao (com parecer financeiro):
    duas paginas financeiras, duas ocorrencias — nem uma a mais (capa, mapas e credito
    NAO levam o carimbo; o aviso fala da conta, nao da geografia)."""
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        _MIN_RESULT, None, viabilidade=_VIAB, aviso_rodape=_AVISO
    )
    assert b"/Count 9" in pdf_bytes  # 7 base + numeros + conclusao: paginacao intacta
    assert _ocorrencias(pdf_bytes, _AVISO) == 2


def test_com_graficos_a_terceira_pagina_financeira_tambem_leva_o_carimbo() -> None:
    viab = dict(_VIAB, graficos=[_png()])
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        _MIN_RESULT, None, viabilidade=viab, aviso_rodape=_AVISO
    )
    assert b"/Count 10" in pdf_bytes  # 7 base + numeros + graficos + conclusao
    assert _ocorrencias(pdf_bytes, _AVISO) == 3


def test_sem_aviso_nenhuma_pagina_e_carimbada() -> None:
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(_MIN_RESULT, None, viabilidade=_VIAB)
    assert _ocorrencias(pdf_bytes, _AVISO) == 0


def test_sem_pagina_financeira_o_aviso_nao_tem_onde_viajar() -> None:
    """Sem payload de `viabilidade` nao existe resultado financeiro no PDF — carimbar
    o aviso em pagina de mapa seria avisar sobre uma conta que o arquivo nao mostra."""
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(_MIN_RESULT, None, aviso_rodape=_AVISO)
    assert b"/Count 7" in pdf_bytes
    assert _ocorrencias(pdf_bytes, _AVISO) == 0


def test_sem_o_parametro_o_pdf_nao_muda_um_byte() -> None:
    """O criterio de aceite do Bloco C+ para o Brasil, ao pe da letra: o caller
    brasileiro passa `None` (perfil com `avisos` = `{}`) e o artefato e IDENTICO ao de
    antes do parametro existir. O relogio do fpdf2 e congelado pelo conftest
    (BLK-FIX-14), entao a comparacao e estavel."""
    de_hoje = gerar_pdf_relatorio_pontual_classico(_MIN_RESULT, None, viabilidade=_VIAB)
    com_none = gerar_pdf_relatorio_pontual_classico(
        _MIN_RESULT, None, viabilidade=_VIAB, aviso_rodape=None
    )
    assert de_hoje == com_none
