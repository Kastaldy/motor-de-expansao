"""Coordenada do centro sob cada foto do deck de comparacao.

O operador escolhe o "melhor" hexagono no PDF e precisa VOLTAR a ele no mapa: a linha
`Centro: lat, lng` sai no formato que a barra de busca aceita colado (`web/src/lib/coord.ts`).
O pareamento e' pelo `indice` do item, como o da foto — `itens` chega RANQUEADO e as
`coordenadas` chegam na ordem de COLAGEM.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError
from pypdf import PdfReader

from motor_expansao.dashboard.relatorio_comparacao import gerar_pdf_comparacao

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot_app  # noqa: E402  (backend do piloto; web/server no sys.path acima)


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (300, 300), (200, 200, 200)).save(buf, "PNG")
    return buf.getvalue()


# Ranqueado: a area de indice 1 ("Jatai") vem PRIMEIRO, a de indice 0 ("Posse") depois.
_DADOS = {
    "titulo": "Comparação de hexágonos",
    "itens": [
        {"rotulo": "Jatai", "indice": 1, "porDimensao": []},
        {"rotulo": "Posse", "indice": 0, "porDimensao": []},
    ],
}
# Ordem de COLAGEM: posicao 0 = Posse, posicao 1 = Jatai.
_POSSE = {"lat": -14.0937123, "lng": -46.3698456}
_JATAI = {"lat": -17.8812345, "lng": -51.7145678}


def _texto_dos_mapas(dados: dict) -> str:
    pdf = gerar_pdf_comparacao(dados, mapas=[_png(), _png()])
    for pagina in PdfReader(io.BytesIO(pdf)).pages:
        texto = pagina.extract_text()
        if "disputa o aluno" in texto:
            return texto
    raise AssertionError("slide de mapas ausente")


def test_coordenada_sai_sob_a_foto_da_area_certa() -> None:
    texto = _texto_dos_mapas({**_DADOS, "coordenadas": [_POSSE, _JATAI]})
    jatai = texto.index("Jatai")
    centro_jatai = texto.index("Centro: -17.88123, -51.71457")
    posse = texto.index("Posse")
    centro_posse = texto.index("Centro: -14.09371, -46.36985")
    # Cada coordenada vem logo depois do nome DELA, apesar da ordem trocada.
    assert jatai < centro_jatai < posse < centro_posse


def test_sem_coordenadas_nao_imprime_linha() -> None:
    # O deck de pontos nao manda `coordenadas`: o slide dele fica como era.
    assert "Centro:" not in _texto_dos_mapas(dict(_DADOS))


def test_coordenada_ausente_so_tira_a_linha_daquela_area() -> None:
    texto = _texto_dos_mapas({**_DADOS, "coordenadas": [None, _JATAI]})
    assert texto.count("Centro:") == 1
    assert "Centro: -17.88123, -51.71457" in texto


def test_schema_recusa_coordenada_nao_numerica() -> None:
    with pytest.raises(ValidationError):
        pilot_app.ComparacaoIn(itens=[{"porDimensao": []}], coordenadas=[{"lat": "x", "lng": 1.0}])


def test_schema_recusa_coordenadas_acima_do_teto() -> None:
    coordenadas = [_POSSE] * (pilot_app._COMPARACAO_ITENS_MAX + 1)
    with pytest.raises(ValidationError):
        pilot_app.ComparacaoIn(itens=[{"porDimensao": []}], coordenadas=coordenadas)


def test_schema_aceita_coordenada_nula_e_preserva_no_dump() -> None:
    corpo = pilot_app.ComparacaoIn(itens=[{"porDimensao": []}], coordenadas=[None, _JATAI])
    assert corpo.model_dump()["coordenadas"] == [None, _JATAI]
