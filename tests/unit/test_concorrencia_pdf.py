"""PDF da janela da unidade no mapa: a unidade, a região e o que cada concorrente oferece.

O PDF repete o que a ficha em janela mostra (`FichaUnidadeNoMapa.tsx`) e tem de preservar os
mesmos três estados das comodidades: base ausente, academia não coletada e item declarado.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from motor_expansao.dashboard import rede_export
from tests.unit.rede_fixtures import payload_ficha_sintetico
from tests.unit.test_pdf_base import _SEMPRE_ACENTUADAS, _texto_cru_do_pdf

SERVER = Path(__file__).resolve().parents[2] / "web" / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))


def _canal(fonte: str, itens: dict[str, bool], lista: list[str], atividades: list[str]) -> dict[str, object]:
    return {
        "fonte": fonte,
        "nome": "Academia",
        "itens": {chave: (True if valor else None) for chave, valor in itens.items()},
        "lista": lista,
        "atividades": atividades,
        "data_coleta": "2026-09-29",
    }


def _concorrente(nome: str, **campos: object) -> dict[str, object]:
    return {
        "lat": -22.95,
        "lng": -43.18,
        "nome": nome,
        "rede": "bluefit",
        "classe": "cadeia",
        "distancia_m": 320.0,
        "comodidades": None,
        "agregadores": {"wellhub": None, "totalpass": None},
        **campos,
    }


def _inteligencia(concorrentes: list[dict[str, object]]) -> dict[str, object]:
    return {
        "agregadores": {"wellhub": 150, "totalpass": 90},
        "mapa": {"raio_m": 2000, "concorrentes": concorrentes},
    }


def _ficha() -> dict[str, object]:
    ficha = payload_ficha_sintetico()
    ficha["metricas"] = {
        **ficha["metricas"],  # type: ignore[dict-item]
        "ativos": {"atual": 1_400.0},
        "pagantes": {"atual": 1_100.0},
        "agregadores": {"atual": 300.0},
    }
    return ficha


PONTO = {
    "raio_km": 1.0,
    "censo": {
        "disponivel": True,
        "renda_media_domiciliar": 8_500.0,
        "renda_per_capita": 3_200.0,
        "densidade_hab_km2": 14_000.0,
        "populacao": 43_000.0,
    },
}


def test_pdf_traz_a_unidade_a_regiao_e_o_que_cada_concorrente_oferece() -> None:
    completo = _concorrente(
        "Bluefit Botafogo",
        agregadores={"wellhub": {"plano": "Silver", "preco": 149.99, "casado_por": "ponto"}, "totalpass": None},
        comodidades={
            "recorrente": _canal("site", {"musculacao": True, "luta": True}, ["Lutas", "Ar-condicionado"], []),
            "agregador": _canal("wellhub", {"chuveiro": True}, ["Chuveiro"], ["Muay Thai", "Yoga", "muay thai", " "]),
        },
    )
    pdf = rede_export.concorrencia_pdf(_ficha(), _inteligencia([completo]), PONTO)
    assert pdf.startswith(b"%PDF-1.4")
    cru = _texto_cru_do_pdf(pdf)
    for esperado in (
        "botafogo",
        "bluefit botafogo",
        "320 m",
        "wellhub: silver",
        "149,99",
        "no site da rede",
        r"no agregador \(wellhub\)",  # o PDF escapa os parênteses no texto cru
        "chuveiro",
        "lutas",
        "modalidades: muay thai, yoga",
        "43.000",  # população do raio
    ):
        assert esperado in cru, esperado
    # pedido do Juan (05/10): o PDF não leva dado de aluno da unidade
    for proibido in ("alunos", "pagantes", "1.400", "1.100", "via wellhub", "via totalpass"):
        assert proibido not in cru, proibido


def test_pdf_distingue_base_ausente_de_academia_nao_coletada() -> None:
    sem_base = _concorrente("Academia Sem Base", comodidades=None)
    nao_coletada = _concorrente("Academia Fora da Coleta", comodidades={"recorrente": None, "agregador": None})

    cru = _texto_cru_do_pdf(rede_export.concorrencia_pdf(_ficha(), _inteligencia([sem_base]), None))
    assert "comodidades indispon" in cru and "o coletadas" not in cru

    cru = _texto_cru_do_pdf(rede_export.concorrencia_pdf(_ficha(), _inteligencia([nao_coletada]), None))
    assert "comodidades n\xe3o coletadas" in cru
    assert "sem plano de wellhub ou totalpass identificado" in cru
    # sem o censo do ponto a página não inventa número: diz que não leu
    assert "censo do entorno indispon" in cru


def test_pdf_sem_mapa_e_sem_concorrente_nao_quebra() -> None:
    sem_mapa = rede_export.concorrencia_pdf(_ficha(), {"mapa": None}, None)
    assert "sem coordenada" in _texto_cru_do_pdf(sem_mapa)
    vazio = rede_export.concorrencia_pdf(_ficha(), _inteligencia([]), PONTO)
    assert "nenhuma academia mapeada" in _texto_cru_do_pdf(vazio)


def test_pdf_pagina_quando_a_praca_e_densa_e_nao_perde_concorrente() -> None:
    muitos = [
        _concorrente(
            f"Academia Numero {i:02d}",
            comodidades={
                "recorrente": None,
                "agregador": _canal("totalpass", {"musculacao": True}, ["Musculação"], ["Funcional"] * 12),
            },
        )
        for i in range(40)
    ]
    pdf = rede_export.concorrencia_pdf(_ficha(), _inteligencia(muitos), PONTO)
    cru = _texto_cru_do_pdf(pdf)
    assert all(f"academia numero {i:02d}" in cru for i in range(40))
    assert len(re.findall(rb"/Type /Page\b", pdf)) > 2


def test_pdf_nao_imprime_interrogacao_nem_texto_sem_acento() -> None:
    # travessão e seta estão fora de latin-1: o texto da FONTE não pode virar "?" calado
    esquisito = _concorrente(
        "Studio Corpo — Unidade → Sul",
        comodidades={
            "recorrente": None,
            "agregador": _canal("wellhub", {"vestiario": True}, ["Vesti\xe1rio"], ["Dan\xe7a – ritmos"]),
        },
    )
    cru = _texto_cru_do_pdf(rede_export.concorrencia_pdf(_ficha(), _inteligencia([esquisito]), PONTO))
    assert "studio corpo - unidade -> sul" in cru
    assert "dan\xe7a - ritmos" in cru
    ofensas = sorted(set(re.findall(r"\b(?:" + "|".join(_SEMPRE_ACENTUADAS) + r")\b", cru)))
    assert not ofensas, f"PDF imprime texto sem acento (CLAUDE.md \xa72): {ofensas}"


def test_pdf_segue_o_guia_de_marca_titulos_em_caixa_alta_e_sem_preto() -> None:
    """Guia de marca: título e subtítulo em CAIXA ALTA, teal dominante, nunca preto puro."""
    pdf = rede_export.concorrencia_pdf(_ficha(), _inteligencia([_concorrente("Bluefit Botafogo")]), PONTO)
    cru = pdf.decode("latin-1", errors="replace")
    assert "(BOTAFOGO)" in cru and "CONCORRENTES - 1 A 2 KM" in cru
    assert r"REGIÃO \(RAIO DE 1,0 KM\)" in cru
    # cor de texto e de preenchimento em preto puro ("0 g" / "0 0 0 rg") não aparece
    assert not re.search(r"(?m)^(0 g|0 0 0 rg|0\.000 g|0\.000 0\.000 0\.000 rg)$", cru)


def test_pdf_abre_com_o_raio_da_unidade_antes_da_lista_e_sem_numero_nos_marcadores() -> None:
    perto = _concorrente("Academia Perto", lat=-22.951, lng=-43.180, distancia_m=110.0)
    longe = _concorrente("Academia Longe", lat=-22.962, lng=-43.190, distancia_m=1_680.0, classe="independente", rede=None)
    intel = _inteligencia([perto, longe])
    intel["mapa"].update({"lat": -22.950, "lng": -43.180, "ultra": [{"lat": -22.94, "lng": -43.17}]})  # type: ignore[union-attr]
    pdf = rede_export.concorrencia_pdf(_ficha(), intel, PONTO)
    cru = _texto_cru_do_pdf(pdf)
    paginas = cru.split("/type /page\n")
    # o raio e a legenda vêm ANTES da lista: estão na página 1, e a lista na 2
    assert "(ultra)" in cru and "(2 km)" in cru and "(1,0 km)" in cru
    assert cru.index("unidade deste relat") < cru.index("(academia perto)") < cru.index("(academia longe)")
    # pedido do Juan (05/10): o desenho não leva numeração, nem a lista
    assert " 6.00 tf" not in cru and "1. academia" not in cru  # o corpo 6 era só o do número
    assert len(re.findall(rb"/Type /Page\b", pdf)) == 2, len(paginas)


def test_pdf_sem_coordenada_diz_que_nao_ha_raio_para_desenhar() -> None:
    cru = _texto_cru_do_pdf(rede_export.concorrencia_pdf(_ficha(), _inteligencia([_concorrente("Sem Ponto")]), None))
    assert "n\xe3o h\xe1 raio para desenhar" in cru and "(sem ponto)" in cru


def test_icones_do_pdf_cobrem_os_itens_da_coleta() -> None:
    """Item sem figura sairia só em texto, calado: os traços têm de cobrir a lista da coleta."""
    from motor_expansao.dashboard import comodidades_concorrentes as cc

    assert set(rede_export._TRACOS_DOS_ITENS) == set(cc.ITENS)
    for item in cc.ITENS:
        svg = rede_export._svg_do_item(item)
        assert svg and svg.startswith(b"<svg") and b"#00A79D" in svg  # teal da marca


def test_pdf_desenha_uma_figura_por_item_oferecido() -> None:
    def figuras(itens: dict[str, bool]) -> int:
        conc = _concorrente(
            "Academia", comodidades={"recorrente": None, "agregador": _canal("wellhub", itens, [], [])}
        )
        pdf = rede_export.concorrencia_pdf(_ficha(), _inteligencia([conc]), PONTO)
        return pdf.count(b" cm")  # cada figura entra com a própria matriz de posição

    # mais itens declarados = mais desenho no arquivo; nenhum item = nenhuma figura a mais
    assert figuras({"musculacao": True, "luta": True, "chuveiro": True}) > figuras({"musculacao": True})
    assert figuras({"musculacao": True}) > figuras({})


def test_pdf_marca_a_unidade_com_a_logo_da_ultra_quando_ela_existe() -> None:
    from PIL import Image

    intel = _inteligencia([_concorrente("Academia Perto", lat=-22.951, lng=-43.18)])
    intel["mapa"].update({"lat": -22.95, "lng": -43.18})  # type: ignore[union-attr]
    sem = rede_export.concorrencia_pdf(_ficha(), intel, PONTO)
    com = rede_export.concorrencia_pdf(_ficha(), intel, PONTO, None, Image.new("RGBA", (40, 40), (0, 169, 158, 255)))
    assert com.count(b"/Subtype /Image") > sem.count(b"/Subtype /Image")
    # logo ilegível não derruba o relatório: a unidade volta a ser o ponto desenhado
    quebrada = rede_export.concorrencia_pdf(_ficha(), intel, PONTO, None, "nao-existe.png")
    assert quebrada.startswith(b"%PDF-1.4") and b"(ULTRA)" in quebrada


def _independente(nome: str, wellhub: bool, totalpass: bool) -> dict[str, object]:
    bloco = {"plano": "Basic", "preco": 69.99, "casado_por": "ponto"}
    return _concorrente(
        nome,
        lat=-22.951,
        lng=-43.18,
        classe="independente",
        rede=None,
        agregadores={"wellhub": bloco if wellhub else None, "totalpass": bloco if totalpass else None},
    )


def test_independente_recebe_a_logo_do_agregador_e_so_o_totalpass_quando_so_ele() -> None:
    """Pedido do Juan (14/10): a independente rosa sai com a logo, não com o quadro vazio.
    Regra da DEC-066: TotalPass só quando ele é o único; o resto, Wellhub."""
    artes = {"wellhub": "wh", "totalpass": "tp"}
    assert rede_export._logo_do_concorrente(_independente("A", True, False), None, artes) == "wh"
    assert rede_export._logo_do_concorrente(_independente("B", True, True), None, artes) == "wh"
    assert rede_export._logo_do_concorrente(_independente("C", False, True), None, artes) == "tp"
    assert rede_export._logo_do_concorrente(_independente("D", False, False), None, artes) == "wh"
    # a rede continua com a logo dela, nunca a do agregador
    assert rede_export._logo_do_concorrente(_concorrente("Bluefit"), {"bluefit": "bf"}, artes) == "bf"
    assert rede_export._logo_do_concorrente(_concorrente("Bluefit"), None, artes) is None


def test_pdf_embute_a_logo_do_agregador_nas_independentes() -> None:
    from PIL import Image

    intel = _inteligencia([_independente("Koka Academia", True, True), _independente("Biodelta", False, True)])
    intel["mapa"].update({"lat": -22.95, "lng": -43.18})  # type: ignore[union-attr]
    artes = {
        "wellhub": Image.new("RGBA", (40, 40), (240, 78, 110, 255)),
        "totalpass": Image.new("RGBA", (40, 40), (39, 208, 125, 255)),
    }
    sem = rede_export.concorrencia_pdf(_ficha(), intel, PONTO)
    com = rede_export.concorrencia_pdf(_ficha(), intel, PONTO, None, None, artes)
    # as duas artes entram (o fpdf embute cada imagem uma vez só, por mais pinos que a usem)
    assert com.count(b"/Subtype /Image") == sem.count(b"/Subtype /Image") + 2
    assert "(logo do wellhub; do totalpass se s" in _texto_cru_do_pdf(com)


def test_pdf_desenha_o_raio_sobre_o_fundo_de_ruas_e_sem_ele_volta_ao_esquema() -> None:
    """O mapa vinha em branco (14/10): sem tile nenhum, só o esquema cinza."""
    from PIL import Image

    intel = _inteligencia([_concorrente("Academia Perto", lat=-22.951, lng=-43.18)])
    intel["mapa"].update({"lat": -22.95, "lng": -43.18})  # type: ignore[union-attr]
    fundo = (Image.new("RGB", (300, 300), (230, 225, 210)), "(c) OpenStreetMap")
    sem = rede_export.concorrencia_pdf(_ficha(), intel, PONTO)
    com = rede_export.concorrencia_pdf(_ficha(), intel, PONTO, fundo=fundo)
    assert com.count(b"/Subtype /Image") == sem.count(b"/Subtype /Image") + 1
    assert "openstreetmap" in _texto_cru_do_pdf(com) and "openstreetmap" not in _texto_cru_do_pdf(sem)
    # fundo ilegível não derruba o relatório nem imprime crédito de tile que não entrou
    quebrado = rede_export.concorrencia_pdf(_ficha(), intel, PONTO, fundo=("nao-existe.png", "Credito Fantasma"))
    assert quebrado.startswith(b"%PDF-1.4") and "credito fantasma" not in _texto_cru_do_pdf(quebrado)


def test_fundo_de_ruas_recorta_o_quadro_do_raio_e_falha_em_none(monkeypatch: pytest.MonkeyPatch) -> None:
    import math

    import numpy as np

    from motor_expansao.dashboard import censo_map

    lat, lng = -23.5735, -46.6270  # Aclimação
    pedidos: list[tuple[float, float, float, float]] = []
    tamanhos: list[int] = []

    def falso_fetch(caixa: tuple[float, float, float, float], largura: int, **_: object) -> object:
        pedidos.append(caixa)
        tamanhos.append(largura)
        minx, miny, maxx, maxy = caixa
        folga = (maxx - minx) / 2  # o tile vem maior que o pedido, como o contextily devolve
        return np.zeros((n, n, 4), dtype=np.uint8), (minx - folga, maxx + folga, miny - folga, maxy + folga)

    from PIL import Image

    monkeypatch.setattr(censo_map, "_fetch_basemap", falso_fetch)
    n = 400
    jpeg, credito = rede_export.fundo_de_ruas({"lat": lat, "lng": lng, "raio_m": 2000})  # type: ignore[misc]
    # o pedido cobre o raio (2 km) mais a folga do quadro, em metros de Web Mercator
    minx, _, maxx, _ = pedidos[0]
    metade_chao = (maxx - minx) / 2 * math.cos(math.radians(lat))
    assert metade_chao == pytest.approx(2000 * 210 / 194, rel=1e-6)
    assert Image.open(jpeg).format == "JPEG" and Image.open(jpeg).size == (200, 200)  # o miolo, sem a folga
    assert tamanhos == [rede_export._PIXELS_DO_FUNDO]
    # mosaico maior que o pedido é reduzido: era isso que fazia o PDF passar de 25 MB
    n = 6000
    jpeg, _ = rede_export.fundo_de_ruas({"lat": lat, "lng": lng, "raio_m": 2000})  # type: ignore[misc]
    assert Image.open(jpeg).size == (rede_export._PIXELS_DO_FUNDO, rede_export._PIXELS_DO_FUNDO)
    assert credito in (censo_map._ATRIBUICAO_TILES, censo_map._ATRIBUICAO_TILES_SELFHOST)

    monkeypatch.setattr(censo_map, "_fetch_basemap", lambda *a, **k: None)
    assert rede_export.fundo_de_ruas({"lat": lat, "lng": lng, "raio_m": 2000}) is None
    assert rede_export.fundo_de_ruas({"raio_m": 2000}) is None  # sem coordenada, nem vai à rede


def test_fundo_de_ruas_que_passa_do_teto_volta_ao_esquema_sem_esperar(monkeypatch: pytest.MonkeyPatch) -> None:
    """O contextily baixa tile sem timeout: tileserver mudo penduraria o PDF (review do Felipe, #452)."""
    import threading
    import time

    from motor_expansao.dashboard import censo_map

    solta = threading.Event()

    def tileserver_mudo(*_: object, **__: object) -> object:
        solta.wait(10)  # "não responde"; o teste solta no fim para não deixar thread viva
        return None

    monkeypatch.setattr(censo_map, "_fetch_basemap", tileserver_mudo)
    monkeypatch.setattr(rede_export, "_TETO_DO_FUNDO_S", 0.2)
    inicio = time.monotonic()
    try:
        assert rede_export.fundo_de_ruas({"lat": -23.57, "lng": -46.63, "raio_m": 2000}) is None
        assert time.monotonic() - inicio < 2.0  # devolve no teto, não quando a busca termina
    finally:
        solta.set()


def test_rota_do_pdf_existe_e_fica_atras_da_aba_executiva() -> None:
    import acesso
    import app as pilot

    rota = "/api/rede/unidade/{unidade_id}/concorrencia.pdf"
    assert rota in {r.path for r in pilot.app.routes}
    assert any(
        rota.startswith(prefixo) and abas == frozenset({"executiva"})
        for prefixo, abas in acesso.REGRAS_DE_ACESSO
    )


def test_rota_do_pdf_devolve_404_para_unidade_desconhecida(rede) -> None:  # noqa: F811
    import app as pilot
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as erro:
        pilot.rede_unidade_concorrencia_pdf("nao-existe")
    assert erro.value.status_code == 404


from tests.unit.test_piloto_web_rede import rede  # noqa: E402,F401  (fixture)
