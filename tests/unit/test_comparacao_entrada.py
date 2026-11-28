"""Endurecimento da entrada do deck de comparacao (B9 do pentest de 11/2026).

A rota `POST /api/relatorio/comparacao` so' DESENHA (DEC-070/074), com os numeros vindos do
cliente -- isso e' decisao. O que este PR fecha e' a ENTRADA: a imagem (so' PNG, lado limitado,
lendo so' o cabecalho, sem bomba de descompressao) e a coordenada (faixa valida do globo).
Recalcular o ranking no servidor seria outro PR, com emenda da DEC-074.
"""

from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402


def _data_url(img: Image.Image, formato: str) -> str:
    buf = io.BytesIO()
    img.save(buf, formato)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/{formato.lower()};base64,{b64}"


def test_png_pequeno_valido_passa() -> None:
    url = _data_url(Image.new("RGB", (16, 16), "white"), "PNG")
    assert pilot._png_de_data_url(url) is not None


def test_formato_que_nao_e_png_vira_moldura() -> None:
    # Um GIF valido (decodifica, mas nao e' PNG) degrada para a moldura, nao entra no PDF.
    url = _data_url(Image.new("RGB", (16, 16), "white"), "GIF")
    assert pilot._png_de_data_url(url) is None


def test_png_acima_do_lado_maximo_vira_moldura() -> None:
    grande = Image.new("RGB", (pilot._LADO_MAX_IMAGEM_PX + 1, 1), "white")
    assert pilot._png_de_data_url(_data_url(grande, "PNG")) is None


def test_png_no_lado_maximo_passa() -> None:
    no_limite = Image.new("RGB", (pilot._LADO_MAX_IMAGEM_PX, 1), "white")
    assert pilot._png_de_data_url(_data_url(no_limite, "PNG")) is not None


def test_base64_corrompido_ou_vazio_vira_moldura() -> None:
    assert pilot._png_de_data_url("data:image/png;base64,@@@nao-e-base64") is None
    assert pilot._png_de_data_url("") is None
    assert pilot._png_de_data_url(None) is None


def test_coordenada_fora_do_globo_recusada() -> None:
    with pytest.raises(ValidationError):
        pilot.ComparacaoCoordIn(lat=91, lng=0)
    with pytest.raises(ValidationError):
        pilot.ComparacaoCoordIn(lat=0, lng=200)
    with pytest.raises(ValidationError):
        pilot.ComparacaoCoordIn(lat=float("nan"), lng=0)
    # Dentro do globo passa.
    assert pilot.ComparacaoCoordIn(lat=-23.55, lng=-46.63).lat == -23.55
