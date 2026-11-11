"""Mapas do Estudo pontual em JPEG, com a transparência preservada (11/11/2026).

O estudo saía com ~6 MB (99% em PNG de mapa) e, numa conexão lenta, a pessoa recarregava a
página achando que travou. Os PNG grandes viram JPEG; o alfa vai como JPEG cinza no `smask`,
porque o `set_image_filter("DCTDecode")` do fpdf2 o descarta e os cartões translúcidos dos
mapas virariam retângulos brancos.
"""

from __future__ import annotations

import re
from io import BytesIO

from PIL import Image

from motor_expansao.dashboard import censo_report as cr


def _png(modo: str, tamanho: tuple[int, int], alfa: int | None = None) -> bytes:
    img = Image.new(modo, tamanho, (200, 80, 40, alfa) if modo == "RGBA" else (200, 80, 40))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _imagens(pdf: bytes) -> list[bytes]:
    return [m.group(1) for m in re.finditer(rb"<<(.{0,400}?/Subtype /Image.{0,400}?)>>", pdf, re.S)]


def _pdf_com(img: bytes) -> bytes:
    pdf = cr._UltraPDF()
    pdf.add_page()
    pdf.image(BytesIO(img), x=0, y=0, w=640, h=380)
    return bytes(pdf.output())


def test_mapa_translucido_vira_jpeg_e_mantem_a_mascara() -> None:
    saida = _pdf_com(_png("RGBA", (1280, 760), alfa=180))
    dicts = _imagens(saida)
    assert any(b"/SMask" in d for d in dicts), "a transparência do mapa sumiu"
    assert all(b"/DCTDecode" in d for d in dicts), "cor e máscara deviam sair em JPEG"


def test_mapa_opaco_vira_jpeg_sem_mascara() -> None:
    dicts = _imagens(_pdf_com(_png("RGB", (1280, 760))))
    assert len(dicts) == 1 and b"/DCTDecode" in dicts[0] and b"/SMask" not in dicts[0]


def test_imagem_pequena_fica_como_veio() -> None:
    """Ícone, logo e pino não passam pelo JPEG: lá o PNG é nítido e já é leve."""
    dicts = _imagens(_pdf_com(_png("RGBA", (64, 64), alfa=255)))
    assert dicts and all(b"/FlateDecode" in d for d in dicts)


def test_jpeg_de_origem_nao_e_recomprimido() -> None:
    buf = BytesIO()
    Image.new("RGB", (1280, 760), (10, 20, 30)).save(buf, format="JPEG", quality=70)
    assert cr._imagem_em_jpeg(BytesIO(buf.getvalue())) is None


def test_o_mapa_fica_bem_menor() -> None:
    import numpy as np

    ruido = np.random.default_rng(0).integers(0, 255, (760, 1280, 3), dtype=np.uint8)
    img = Image.fromarray(ruido).convert("RGBA")
    img.putalpha(200)
    buf = BytesIO()
    img.save(buf, format="PNG")
    pesado = buf.getvalue()

    class SemConversao(cr._UltraPDF):
        image = cr.FPDF.image

    antes = SemConversao()
    antes.add_page()
    antes.image(BytesIO(pesado), x=0, y=0, w=640, h=380)
    assert len(_pdf_com(pesado)) < 0.5 * len(bytes(antes.output()))
