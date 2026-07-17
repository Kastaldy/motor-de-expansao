"""Testes do BLK-RELVIAB-01: pagina de FOTOS do imovel no PDF do Relatorio Pontual.

Cobre a normalizacao de imagem (`_normalizar_foto`), a geometria pura das celulas
(`_fotos_cells`) e a insercao OPCIONAL da pagina de fotos nos dois geradores. Fixtures
100% sinteticas (fotos geradas por Pillow em memoria, ZERO foto real -> sem PII);
saida do PDF verificada por `/Count` e headers nos bytes crus (compressao OFF).
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd
from PIL import Image
from pyproj import Transformer
from shapely.geometry import box
from shapely.ops import transform

from motor_expansao.dashboard.censo_map import render_mapas_censitarios_combinados
from motor_expansao.dashboard.censo_point import (
    CRS_ORIGEM_CENSO,
    _local_metric_crs,
    analisar_ponto_censitario_setores,
)
from motor_expansao.dashboard.censo_report import (
    _FOTOS_MAX,
    _FOTOS_PAGE_TITLE,
    _fotos_cells,
    _normalizar_foto,
    gerar_pdf_relatorio_pontual_censitario,
    gerar_pdf_relatorio_pontual_classico,
)

LAT_C = -23.55
LNG_C = -46.63


# --------------------------------------------------------------------------- #
# Fixtures sinteticas                                                          #
# --------------------------------------------------------------------------- #
def _fake_foto(w: int = 800, h: int = 600, *, fmt: str = "JPEG", mode: str = "RGB") -> bytes:
    """Foto sintetica (retangular) em memoria — sem PII."""
    color = (120, 180, 90) if mode == "RGB" else (120, 180, 90, 255)
    buffer = BytesIO()
    Image.new(mode, (w, h), color).save(buffer, format=fmt)
    return buffer.getvalue()


def _to_wgs(local_geom):
    transformer = Transformer.from_crs(
        _local_metric_crs(LAT_C, LNG_C), CRS_ORIGEM_CENSO, always_xy=True
    )
    return transform(transformer.transform, local_geom)


def _sector(cod: str, local_geom, *, pop: float, renda: float, score: float) -> dict:
    geom = _to_wgs(local_geom)
    minx, miny, maxx, maxy = geom.bounds
    return {
        "cod_setor": cod,
        "uf": "SP",
        "cod_municipio": "3550308",
        "nome_municipio": "SAO PAULO",
        "area_setor_m2": float(local_geom.area),
        "geometry_wkb": geom.wkb,
        "bbox_minx": minx,
        "bbox_miny": miny,
        "bbox_maxx": maxx,
        "bbox_maxy": maxy,
        "pop_total_setor_2022": pop,
        "renda_per_capita_setor_2022_calibrada": renda,
        "densidade_pop_setor_hab_km2": pop / (local_geom.area / 1_000_000.0),
        "score_setor_2022_calibrado": score,
        "flag_renda_disponivel": True,
        "flag_geometria_valida": True,
        "qualidade_join_uf": "A",
    }


def _sample_result():
    setores = pd.DataFrame(
        [
            _sector("355030801000001", box(-700, -700, 0, 700), pop=800, renda=2100, score=64),
            _sector("355030801000002", box(0, -700, 700, 700), pop=1400, renda=2600, score=86),
        ]
    )
    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, setores)
    mapas = render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores, width=480, height=360, basemap=False
    )
    return result, mapas


# --------------------------------------------------------------------------- #
# _normalizar_foto                                                            #
# --------------------------------------------------------------------------- #
def test_normalizar_foto_retorna_jpeg_valido():
    saida = _normalizar_foto(_fake_foto(800, 600))
    assert saida is not None
    with Image.open(BytesIO(saida)) as img:
        assert img.format == "JPEG"
        assert img.width == 800 and img.height == 600


def test_normalizar_foto_faz_downscale_no_lado_maior():
    saida = _normalizar_foto(_fake_foto(3000, 2000), lado_max=1600)
    assert saida is not None
    with Image.open(BytesIO(saida)) as img:
        assert max(img.width, img.height) == 1600
        assert (img.width, img.height) == (1600, 1067)  # proporcao preservada


def test_normalizar_foto_rgba_achatada_para_rgb():
    saida = _normalizar_foto(_fake_foto(400, 400, fmt="PNG", mode="RGBA"))
    assert saida is not None
    with Image.open(BytesIO(saida)) as img:
        assert img.mode == "RGB"


def test_normalizar_foto_invalida_retorna_none():
    assert _normalizar_foto(b"nao eh imagem") is None
    assert _normalizar_foto(b"") is None


# --------------------------------------------------------------------------- #
# _fotos_cells (geometria pura)                                               #
# --------------------------------------------------------------------------- #
def test_fotos_cells_uma_coluna_ocupa_largura_util():
    cells = _fotos_cells(1)
    assert len(cells) == 1
    x, _y, w, _h = cells[0]
    assert x == 40.0
    assert abs((x + w) - (960.0 - 40.0)) < 1e-6


def test_fotos_cells_duas_colunas_sem_sobreposicao():
    cells = _fotos_cells(2)
    assert len(cells) == 2
    (x0, _y0, w0, _h0), (x1, _y1, _w1, _h1) = cells
    assert x0 + w0 <= x1 + 1e-6  # coluna 0 termina antes de comecar a 1


def test_fotos_cells_limita_ao_max():
    assert len(_fotos_cells(5)) == _FOTOS_MAX


# --------------------------------------------------------------------------- #
# Insercao da pagina nos geradores (OPCIONAL)                                 #
# --------------------------------------------------------------------------- #
def test_classico_sem_fotos_mantem_6_paginas():
    result, mapas = _sample_result()
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(result, mapas)
    assert b"/Count 6" in pdf_bytes


def test_classico_com_2_fotos_adiciona_pagina():
    result, mapas = _sample_result()
    fotos = [_fake_foto(800, 600), _fake_foto(600, 800)]
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(result, mapas, fotos=fotos)
    assert b"/Count 7" in pdf_bytes
    assert _FOTOS_PAGE_TITLE.encode("latin-1") in pdf_bytes


def test_censitario_com_2_fotos_adiciona_pagina():
    result, mapas = _sample_result()
    fotos = [_fake_foto(1024, 768), _fake_foto(768, 1024)]
    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(result, mapas, fotos=fotos)
    assert b"/Count 7" in pdf_bytes


def test_terceira_foto_descartada_no_mvp():
    result, mapas = _sample_result()
    fotos = [_fake_foto(), _fake_foto(), _fake_foto()]  # 3 -> so 2 entram
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(result, mapas, fotos=fotos)
    assert b"/Count 7" in pdf_bytes  # 1 pagina de fotos, nao 2


def test_fotos_invalidas_nao_quebram_geracao():
    result, mapas = _sample_result()
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(result, mapas, fotos=[b"lixo", b""])
    # pagina ainda e adicionada (aviso gracioso), sem excecao.
    assert b"/Count 7" in pdf_bytes
