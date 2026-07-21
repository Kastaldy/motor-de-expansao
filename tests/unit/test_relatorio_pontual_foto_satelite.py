"""Testes do BLK-SAT: pagina de VISTA AEREA (satelite Esri) no PDF do Relatorio Pontual.

Cobre a matematica de tile (`_sat_deg2num`), a geometria pura da celula grande
(`_foto_satelite_cell_grande`), o fallback gracioso de rede (`render_foto_satelite_ponto`
-> `None`) e a insercao OPCIONAL da pagina nos dois tamanhos.

ZERO acesso a rede: o download de tile e sempre substituido por monkeypatch. Fixtures
100% sinteticas (Pillow em memoria). Saida do PDF verificada pelo titulo nos bytes crus.
"""

from __future__ import annotations

import math
from io import BytesIO

from PIL import Image

from motor_expansao.dashboard import censo_map
from motor_expansao.dashboard.censo_map import (
    _SAT_RATIO,
    _SAT_ZOOM_MAX,
    _SAT_ZOOM_MIN,
    _sat_deg2num,
    render_foto_satelite_ponto,
)
from motor_expansao.dashboard.censo_report import (
    _FOTO_ASPECT,
    _PAGE_H,
    _PAGE_W,
    _SATELITE_PAGE_TITLE,
    _ascii,
    _foto_satelite_cell_grande,
    _fotos_cells,
    gerar_pdf_relatorio_pontual_classico,
)

LAT_C = -16.6869
LNG_C = -49.2648


def _png_sintetico(w: int = 256, h: int = 256, cor: tuple[int, int, int] = (90, 120, 80)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), cor).save(buf, format="PNG")
    return buf.getvalue()


def _result_minimo() -> dict:
    """`result` enxuto: as paginas censitarias caem no fallback gracioso ('n/d')."""
    return {
        "lat": LAT_C,
        "lng": LNG_C,
        "raio_km": 1.5,
        "n_setores": 0,
        "pop_total_raio": None,
        "renda_per_capita_media_raio": None,
        "densidade_pop_raio_hab_km2": None,
        "score_setor_medio": None,
        "score_setor_max": None,
        "n_concorrentes": 0,
        "n_ultra": 0,
    }


# --------------------------------------------------------------------------- #
# Matematica de tile                                                           #
# --------------------------------------------------------------------------- #


def test_deg2num_bate_com_a_formula_slippy_map():
    """`_sat_deg2num` deve reproduzir a formula padrao XYZ (Web Mercator)."""
    z = 18
    x, y = _sat_deg2num(LAT_C, LNG_C, z)
    n = 2.0**z
    x_esperado = (LNG_C + 180.0) / 360.0 * n
    y_esperado = (
        1.0
        - math.log(math.tan(math.radians(LAT_C)) + 1 / math.cos(math.radians(LAT_C))) / math.pi
    ) / 2.0 * n
    assert x == x_esperado
    assert y == y_esperado


def test_deg2num_devolve_fracao_para_centralizar_o_recorte():
    """A parte decimal e o que centraliza o ponto no mosaico — nao pode ser truncada."""
    x, y = _sat_deg2num(LAT_C, LNG_C, 18)
    assert x != int(x) or y != int(y)


def test_zoom_min_menor_que_max():
    """z18 e o piso (cidade media/grande) e z19 o teto (so capital)."""
    assert _SAT_ZOOM_MIN < _SAT_ZOOM_MAX


def test_ratio_da_foto_igual_ao_da_celula_do_pdf():
    """Se divergirem, `_recortar_cover` corta a lateral e come o credito da Esri."""
    assert _SAT_RATIO == _FOTO_ASPECT


# --------------------------------------------------------------------------- #
# Geometria pura da celula grande                                              #
# --------------------------------------------------------------------------- #


def test_celula_grande_respeita_a_proporcao_da_foto():
    _x, _y, w, h = _foto_satelite_cell_grande()
    assert abs(w / h - _FOTO_ASPECT) < 1e-6


def test_celula_grande_fica_dentro_da_pagina_e_centrada_na_horizontal():
    x, y, w, h = _foto_satelite_cell_grande()
    assert x >= 0 and y >= 0
    assert x + w <= _PAGE_W
    assert y + h <= _PAGE_H
    assert abs((x + w / 2.0) - _PAGE_W / 2.0) < 1e-6


def test_celula_grande_e_maior_que_a_padrao():
    """O tamanho padrao existe p/ acomodar 2 imagens; o grande so entra onde a vista
    aerea e a UNICA imagem da pagina (API/bot e PDF do dashboard)."""
    _gx, _gy, gw, _gh = _foto_satelite_cell_grande()
    _px, _py, pw, _ph = _fotos_cells(1)[0]
    assert gw > pw


# --------------------------------------------------------------------------- #
# Fallback de rede: NUNCA levanta, devolve None                                #
# --------------------------------------------------------------------------- #


def test_render_devolve_none_quando_a_rede_falha(monkeypatch):
    """Rede fora -> `None` -> o PDF sai como hoje, sem a pagina (nao quebra o relatorio)."""

    def _explode(*_args, **_kwargs):
        raise OSError("sem rede")

    monkeypatch.setattr(censo_map, "_sat_melhor_zoom", _explode)
    assert render_foto_satelite_ponto(LAT_C, LNG_C) is None


def test_render_monta_png_com_tiles_mockados(monkeypatch):
    """Caminho feliz, sem rede: devolve PNG na proporcao pedida."""
    monkeypatch.setattr(censo_map, "_sat_melhor_zoom", lambda *a, **k: _SAT_ZOOM_MIN)
    monkeypatch.setattr(
        censo_map,
        "_sat_baixar_tile",
        lambda *a, **k: Image.open(BytesIO(_png_sintetico())).convert("RGBA"),
    )
    png = render_foto_satelite_ponto(LAT_C, LNG_C)
    assert png is not None
    with Image.open(BytesIO(png)) as img:
        assert abs(img.width / img.height - _SAT_RATIO) < 0.02


def test_render_tolera_tile_faltando(monkeypatch):
    """Um tile que falha nao invalida a foto inteira — o resto do mosaico entra."""
    chamadas = {"n": 0}

    def _as_vezes_falha(*_args, **_kwargs):
        chamadas["n"] += 1
        if chamadas["n"] % 3 == 0:
            raise OSError("tile fora do ar")
        return Image.open(BytesIO(_png_sintetico())).convert("RGBA")

    monkeypatch.setattr(censo_map, "_sat_melhor_zoom", lambda *a, **k: _SAT_ZOOM_MIN)
    monkeypatch.setattr(censo_map, "_sat_baixar_tile", _as_vezes_falha)
    assert render_foto_satelite_ponto(LAT_C, LNG_C) is not None


# --------------------------------------------------------------------------- #
# Insercao da pagina no PDF (opcional, nos dois tamanhos)                       #
# --------------------------------------------------------------------------- #


def _tem_pagina_satelite(pdf_bytes: bytes) -> bool:
    return _ascii(_SATELITE_PAGE_TITLE).encode("latin-1") in pdf_bytes


def test_pdf_sem_foto_satelite_nao_ganha_a_pagina():
    """Default `None` -> comportamento identico ao de antes do BLK-SAT."""
    pdf = gerar_pdf_relatorio_pontual_classico(_result_minimo())
    assert not _tem_pagina_satelite(pdf)


def test_pdf_com_foto_satelite_ganha_a_pagina():
    pdf = gerar_pdf_relatorio_pontual_classico(
        _result_minimo(), foto_satelite=_png_sintetico(600, 400)
    )
    assert _tem_pagina_satelite(pdf)


def test_pdf_com_foto_satelite_grande_tambem_ganha_a_pagina():
    pdf = gerar_pdf_relatorio_pontual_classico(
        _result_minimo(), foto_satelite=_png_sintetico(600, 400), foto_satelite_grande=True
    )
    assert _tem_pagina_satelite(pdf)


def test_foto_invalida_nao_cria_a_pagina_nem_levanta():
    """Bytes corrompidos -> `_normalizar_foto` devolve None -> pagina nao entra."""
    pdf = gerar_pdf_relatorio_pontual_classico(
        _result_minimo(), foto_satelite=b"isto nao e uma imagem"
    )
    assert not _tem_pagina_satelite(pdf)


def test_vista_aerea_nao_ocupa_as_vagas_das_fotos_do_imovel():
    """Pagina PROPRIA: com `_FOTOS_MAX=2`, dividir a pagina descartaria 1 foto do usuario."""
    fotos = [_png_sintetico(600, 400, (10, 20, 30)), _png_sintetico(600, 400, (200, 30, 40))]
    com_sat = gerar_pdf_relatorio_pontual_classico(
        _result_minimo(), fotos=fotos, foto_satelite=_png_sintetico(600, 400)
    )
    sem_sat = gerar_pdf_relatorio_pontual_classico(_result_minimo(), fotos=fotos)
    assert _tem_pagina_satelite(com_sat)
    assert not _tem_pagina_satelite(sem_sat)
    assert com_sat.count(b"/Type /Page") == sem_sat.count(b"/Type /Page") + 1
