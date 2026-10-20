"""Estudo por recorte no PDF do Relatorio Pontual (DEC-074, fase 2 da DEC-071).

O PDF do raio de 1 km e' o contrato de sempre (bot/API, Viabilidade, botao Estudo do ponto):
sem `recorte` ele tem de sair IDENTICO. Com `recorte` (raio de 2 km, 10 min de carro, area
desenhada) os textos nomeiam o recorte, as 4 metas de TOTAL saem escaladas pelo
`fator_regua` -- UM objeto para o card do Big Numbers e o parecer da Conclusao -- e as
paginas presas ao ponto dizem isso. Tudo em latin-1 (fonte core do fpdf2).
"""

from __future__ import annotations

import math
import re
from dataclasses import replace
from datetime import datetime
from io import BytesIO

import pandas as pd
import pytest
from PIL import Image
from pyproj import Transformer
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.ops import transform

import motor_expansao.dashboard.censo_map as censo_map
import motor_expansao.dashboard.censo_report as cr
from motor_expansao.dashboard.censo_point import (
    CRS_ORIGEM_CENSO,
    GEOMETRIA_TIPO_ISOCRONA_CARRO_10MIN,
    _local_metric_crs,
    analisar_ponto_censitario_setores,
)
from motor_expansao.dashboard.relatorio_comparacao import (
    gerar_pdf_comparacao,
    rotulo_do_recorte,
    rotulos_dos_recortes,
)
from motor_expansao.dashboard.relatorio_praca import (
    PracaDoPonto,
    crescimento_do_hexagono,
    pressao_sobre_ponto,
    resumir_crescimento,
)

LAT, LNG = -23.48516183001325, -46.61770984110429  # Santana/SP
NOW = datetime(2026, 10, 19, 12, 0, 0)

_RESULT = {
    "lat": LAT,
    "lng": LNG,
    "raio_km": 1.0,
    "metodo": "setor_censitario_intersecao_area_1km",
    "pop_total_raio": 20_000.0,
    "renda_per_capita_media_raio": 2_000.0,
    "domicilios_total_raio": 7_000.0,
    "renda_domiciliar_total_raio": 5_000.0,
    "n_concorrentes": 3,
    "n_ultra": 1,
    "ultra_raio": [{"dist_km": 0.8}],
}
_RESIDUAL = {
    "sam_fitness_potencial": 3_000.0,
    "oferta_efetiva_disponivel": 1_500.0,
    "oferta_consumida_mercado_estimada": 1_200.0,
    "oferta_consumida_ultra_estimada": 300.0,
}


def _png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (400, 300), (0, 167, 157)).save(buf, format="PNG")
    return buf.getvalue()


def _praca() -> PracaDoPonto:
    return PracaDoPonto(
        municipio="São Paulo",
        uf="SP",
        pressao=pressao_sobre_ponto(LAT, LNG, None, None),
        crescimento=resumir_crescimento(
            {"cres_tendencia": "Em alta", "v_frase": "Cidade em alta."}
        ),
        crescimento_hex=crescimento_do_hexagono(
            {"cres_hex_taxa": 12.0, "cres_hex_classe": "Em alta"}
        ),
        mapas={"pressao_raios": _png()},
    )


def _pdf(recorte=None, **kw) -> bytes:
    if recorte is not None:
        kw["recorte"] = recorte
    return cr.gerar_pdf_relatorio_pontual_classico(
        _RESULT,
        None,
        residual=_RESIDUAL,
        rotulo="Santana, São Paulo",
        now=NOW,
        conclusao_so_estudo=True,
        **kw,
    )


def _sem_data(pdf: bytes) -> bytes:
    """O PDF sem o carimbo de criacao (unico campo que muda entre duas geracoes)."""
    return re.sub(rb"/CreationDate \(D:[^)]*\)", b"", pdf)


def _texto(pdf: bytes) -> str:
    """Texto cru do PDF (a classe desliga a compressao), com os parenteses desescapados."""
    return pdf.decode("latin-1").replace("\\(", "(").replace("\\)", ")")


def _iso_recorte() -> dict:
    return cr.recorte_pdf("carro_10min", fator_regua=24.5, area_km2=24.5 * math.pi)


# --------------------------------------------------------------------------- #
# Sem recorte: o PDF de sempre                                                #
# --------------------------------------------------------------------------- #
def test_sem_recorte_e_com_raio_1km_explicito_saem_identicos():
    # A rota nova manda `recorte_pdf("raio_1km", ...)`; o bot/API nao manda nada. Os dois
    # tem de ser o MESMO arquivo, byte a byte (fora a data de criacao).
    um_km = cr.recorte_pdf("raio_1km", fator_regua=1.0, area_km2=math.pi)
    assert cr._contexto_recorte(um_km) is cr._RECORTE_PADRAO
    praca = _praca()
    assert _sem_data(_pdf(praca=praca, foto_satelite=_png())) == _sem_data(
        _pdf(um_km, praca=praca, foto_satelite=_png())
    )


def test_sem_recorte_os_textos_sao_os_de_antes():
    texto = _texto(_pdf(praca=_praca(), foto_satelite=_png()))
    for trecho in (
        "Relatório Pontual Censitário - Raio 1,0 km",
        "Redes no raio de 1,0 km",
        "População total no raio",
        "Academias no raio (todas)",
        "círculo de 1,0 km",
        "não o raio de 1,0 km",
    ):
        assert trecho.encode("latin-1").decode("latin-1") in texto, trecho
    # Nada do recorte vaza para o estudo de sempre.
    assert "Em volta do ponto de origem" not in texto
    assert "Metas de totais escaladas" not in texto


def test_sem_recorte_as_paginas_recebem_os_argumentos_de_sempre(monkeypatch):
    """Nenhuma pagina recebe `contexto` no PDF do raio de 1 km: as chamadas nao mudam."""
    chamadas: dict[str, dict] = {}
    for nome in (
        "_classico_cover_page",
        "_classico_socioeconomia_residual_page",
        "_classico_competitors_page",
        "_classico_perfil_bairro_page",
        "_big_numbers_page",
        "_conclusao_page",
        "_classico_credit_page",
        "_praca_pressao_page",
        "_praca_cidade_page",
        "_foto_satelite_page",
    ):
        original = getattr(cr, nome)

        def _espiao(*a, _nome=nome, _orig=original, **kw):
            chamadas[_nome] = kw
            return _orig(*a, **kw)

        monkeypatch.setattr(cr, nome, _espiao)
    _pdf(praca=_praca(), foto_satelite=_png())
    assert len(chamadas) == 10
    assert all("contexto" not in kw for kw in chamadas.values()), chamadas

    chamadas.clear()
    _pdf(_iso_recorte(), praca=_praca(), foto_satelite=_png())
    assert all(kw.get("contexto") is not None for kw in chamadas.values()), chamadas


def test_textos_da_conclusao_no_raio_de_1km_sao_as_constantes():
    assert cr._textos_conclusao(cr._RECORTE_PADRAO) == (
        cr._CONCLUSAO_APROVADO_TEXTO_DEMOGRAFICO,
        cr._CONCLUSAO_APROVADO_TEXTO_ESTUDO,
        cr._CONCLUSAO_NOTA,
        cr._CONCLUSAO_NOTA_ESTUDO,
    )
    assert cr._RECORTE_PADRAO.metas is cr._METAS
    assert cr._RECORTE_PADRAO.nota_regua is None


# --------------------------------------------------------------------------- #
# Metas escaladas                                                             #
# --------------------------------------------------------------------------- #
def test_raio_2km_escala_so_as_4_metas_de_total_por_4():
    ctx = cr._contexto_recorte(cr.recorte_pdf("raio_2km", fator_regua=4.0, area_km2=4 * math.pi))
    m, base = ctx.metas, cr._METAS
    assert m.pop_total_raio == 4 * base.pop_total_raio == 40_000
    assert m.domicilios_total_raio == 4 * base.domicilios_total_raio == 12_000
    assert m.sam_fitness_potencial == 4 * base.sam_fitness_potencial == 8_000
    assert m.residual_fitness_disponivel == 4 * base.residual_fitness_disponivel == 8_000
    # Medias nao escalam.
    assert m.renda_per_capita_media_raio == base.renda_per_capita_media_raio
    assert m.renda_domiciliar_total_raio == base.renda_domiciliar_total_raio
    assert m.score_setor_medio == base.score_setor_medio
    # As constantes de modulo (funil, contratos) NAO mudam.
    assert cr._META_POP_TOTAL_RAIO == 10_000.0


def test_metas_multiplicam_o_valor_do_perfil_e_nao_um_literal(monkeypatch):
    # Um perfil com outra regua (ex.: AR): a escala tem de partir DELE.
    outro = replace(cr._METAS, pop_total_raio=7_000.0, sam_fitness_potencial=1_000.0)
    monkeypatch.setattr(cr, "_METAS", outro)
    ctx = cr._contexto_recorte(cr.recorte_pdf("raio_2km", fator_regua=4.0))
    assert ctx.metas.pop_total_raio == 28_000.0
    assert ctx.metas.sam_fitness_potencial == 4_000.0


def test_card_e_parecer_leem_a_mesma_regua_escalada():
    ctx = cr._contexto_recorte(cr.recorte_pdf("raio_2km", fator_regua=4.0))
    # 20.000 habitantes: verde no raio de 1 km (meta 10.000), vermelho no de 2 km (40.000).
    assert cr._cor_por_meta(20_000, cr._METAS.pop_total_raio) == cr._CARD_VERDE_RGB
    assert cr._cor_por_meta(20_000, ctx.metas.pop_total_raio) == cr._CARD_VERMELHO_RGB
    vermelhas = dict(
        (r, m)
        for r, _v, m in cr._conclusao_metas_vermelhas(
            _RESULT, _RESIDUAL, metas=ctx.metas, onde=ctx.onde
        )
    )
    assert vermelhas["População total no raio"] == "40.000"
    assert "População total no raio" not in dict(
        (r, m) for r, _v, m in cr._conclusao_metas_vermelhas(_RESULT, _RESIDUAL)
    )
    # Mercado: SAM 3.000 >= 2.000 e residual 1.500 < 2.000 -> consumido no raio de 1 km; com
    # a regua x4 o SAM nao bate a meta e o card nao fica vermelho.
    assert cr._cor_consumo_concorrentes(3_000, 1_500) == cr._CARD_VERMELHO_RGB
    assert cr._cor_consumo_concorrentes(3_000, 1_500, metas=ctx.metas) == cr._CARD_VERDE_RGB
    parecer = cr._avaliar_conclusao(_RESULT, _RESIDUAL, None, {}, somente_estudo=True, contexto=ctx)
    textos = " ".join(parecer.demografico.ressalvas + parecer.demografico.eliminatorios)
    assert "Meta não atingida em População total no raio: 20.000 para meta de 40.000." in textos
    assert "Mercado já consumido" not in textos


def test_pdf_com_recorte_mostra_a_nota_da_escala_em_latin1():
    texto = _texto(_pdf(cr.recorte_pdf("raio_2km", fator_regua=4.0, area_km2=4 * math.pi)))
    assert "Metas de totais escaladas x4,0 pela área do recorte" in texto
    assert "(12,57 km2 / 3,14 km2 do raio de 1 km)." in texto


def test_isocrona_carimba_a_malha_viaria_no_pdf():
    # Sem o carimbo, dois PDFs dos 10 min de carro do mesmo ponto -- antes e depois de
    # reconstruir os tiles -- sairiam indistinguiveis.
    rec = cr.recorte_pdf(
        "carro_10min",
        fator_regua=24.5,
        area_km2=24.5 * math.pi,
        versao_rotas="2026-10-01T03:00:00+00:00",
    )
    assert rec["versao_rotas"] == "2026-10-01T03:00:00+00:00"
    ctx = cr._contexto_recorte(rec)
    assert ctx.descricao_censo.endswith("(76,97 km2; malha viária de 01/10/2026)")
    ctx.descricao_censo.encode("latin-1")
    assert "01/10/2026" in _texto(_pdf(rec))
    # Sem data nos tiles, a versao do servico.
    assert cr._texto_da_malha_viaria("3.9.0") == "Valhalla 3.9.0"
    assert cr._texto_da_malha_viaria(None) is None
    # Sem carimbo, o dict e o texto de antes (sem a chave nova).
    assert "versao_rotas" not in _iso_recorte()
    assert cr._contexto_recorte(_iso_recorte()).descricao_censo.endswith("(76,97 km2)")


def test_recorte_invalido_levanta():
    with pytest.raises(ValueError, match="tipo de recorte"):
        cr._contexto_recorte({"tipo": "raio_3km", "fator_regua": 9.0})
    with pytest.raises(ValueError, match="fator_regua"):
        cr._contexto_recorte({"tipo": "raio_2km", "fator_regua": 0.0})
    with pytest.raises(ValueError, match="fator_regua"):
        cr._contexto_recorte({"tipo": "poligono", "fator_regua": float("nan")})


# --------------------------------------------------------------------------- #
# Rotulos do recorte em todas as paginas                                      #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("recorte", "trechos"),
    [
        (
            cr.recorte_pdf("raio_2km", fator_regua=4.0, area_km2=4 * math.pi),
            (
                "Relatório Pontual Censitário - Raio 2,0 km",
                "Redes no raio de 2,0 km",
                "círculo de 2,0 km",
                "não o raio de 2,0 km",
            ),
        ),
        (
            cr.recorte_pdf("carro_10min", fator_regua=24.5, area_km2=24.5 * math.pi),
            (
                "Relatório Pontual Censitário - 10 min de carro (sem trânsito)",
                "Redes em 10 min de carro, sem trânsito",
                "não a isócrona de 10 min de carro",
                "1 unidade Ultra dentro da isócrona do estudo",
            ),
        ),
        (
            cr.recorte_pdf("poligono", fator_regua=3.2, area_km2=3.2 * math.pi),
            (
                "Relatório Pontual Censitário - Área desenhada (10,05 km2)",
                "Redes na área desenhada",
                "área desenhada de 10,05 km2",
                "não a área desenhada",
            ),
        ),
    ],
)
def test_recorte_nomeado_nas_paginas(recorte, trechos):
    texto = _texto(_pdf(recorte, praca=_praca(), foto_satelite=_png()))
    for trecho in trechos:
        assert trecho in texto, trecho
    # Capa, Concorrentes, Big Numbers, Conclusao e Realizacao ja' foram cobertos acima; as
    # paginas presas ao ponto (hero, vista aerea, pressao, perfil, cidade) avisam -- 5 vezes.
    assert texto.count("Em volta do ponto de origem") == 5
    assert "Relatório Pontual Censitário - Raio 1,0 km" not in texto


def test_big_numbers_rotula_o_recorte_nos_cards():
    texto = _texto(_pdf(_iso_recorte()))
    assert "População total em 10 min de carro" in texto
    assert "método setor_censitario_intersecao_area_1km" in texto  # o metodo vem do result


def test_textos_do_recorte_cabem_em_latin1(monkeypatch):
    """Toda string que passa pelo `_ascii` num PDF de recorte e' latin-1 pura: nada vira '?'."""
    vistas: list[str] = []
    original = cr._ascii

    def _audita(texto: str) -> str:
        vistas.append(texto)
        return original(texto)

    monkeypatch.setattr(cr, "_ascii", _audita)
    for recorte in (
        _iso_recorte(),
        cr.recorte_pdf("poligono", fator_regua=3.2, area_km2=10.05),
        cr.recorte_pdf("raio_2km", fator_regua=4.0),
    ):
        _pdf(recorte, praca=_praca(), foto_satelite=_png())
    assert vistas
    for texto in vistas:
        texto.encode("latin-1")  # levanta UnicodeEncodeError se houver pi, travessao...


# --------------------------------------------------------------------------- #
# Mapas (censo_map)                                                           #
# --------------------------------------------------------------------------- #
def _para_wgs(geom):
    t = Transformer.from_crs(_local_metric_crs(LAT, LNG), CRS_ORIGEM_CENSO, always_xy=True)
    return transform(t.transform, geom)


def _setores(meia: float = 4000.0, passo: float = 1000.0) -> pd.DataFrame:
    linhas = []
    for i, x in enumerate(range(int(-meia), int(meia), int(passo))):
        for j, y in enumerate(range(int(-meia), int(meia), int(passo))):
            local = box(x, y, x + passo, y + passo)
            g = _para_wgs(local)
            mx, my, mxx, mxy = g.bounds
            linhas.append(
                {
                    "cod_setor": f"3550308{i:03d}{j:03d}",
                    "uf": "SP",
                    "cod_municipio": "3550308",
                    "area_setor_m2": float(local.area),
                    "geometry_wkb": g.wkb,
                    "bbox_minx": mx,
                    "bbox_miny": my,
                    "bbox_maxx": mxx,
                    "bbox_maxy": mxy,
                    "pop_total_setor_2022": 1000.0,
                    "renda_per_capita_setor_2022_calibrada": 2000.0,
                    "avg_moradores_domicilio_setor_2022": 3.0,
                    "renda_responsavel_media_setor_2022": 6000.0,
                    "densidade_pop_setor_hab_km2": 1000.0,
                    "score_setor_2022_calibrado": 60.0,
                    "flag_renda_disponivel": True,
                    "flag_geometria_valida": True,
                    "qualidade_join_uf": "A",
                }
            )
    return pd.DataFrame(linhas)


def _isocrona():
    """MultiPolygon com buraco: o formato que o Valhalla devolve e `.exterior` nao aceita."""
    principal = Polygon(
        [(-2500, -1500), (2500, -1800), (2800, 2000), (-2200, 2400)],
        holes=[[(500, 500), (900, 500), (900, 900), (500, 900)]],
    )
    ilha = Point(3300, -3000).buffer(400)
    return _para_wgs(MultiPolygon([principal, ilha]))


def test_frame_da_geometria_cobre_o_contorno_e_o_ponto_na_proporcao_do_mapa():
    contorno = MultiPolygon([box(1000, 1000, 6000, 3000), box(7000, -500, 7500, 0)])
    frame = censo_map._frame_box_da_geometria(contorno, 1280, 760)
    assert frame.contains(contorno)
    assert frame.contains(Point(0, 0))
    minx, miny, maxx, maxy = frame.bounds
    inner_w, inner_h = censo_map._map_inner_dims(1280, 760)
    assert (maxx - minx) / (maxy - miny) == pytest.approx(inner_w / inner_h)


def test_onde_do_recorte():
    assert censo_map.onde_do_recorte(1.0, None) == "no raio"  # o texto de sempre
    assert censo_map.onde_do_recorte(2.0, None) == "no raio de 2 km"
    assert censo_map.onde_do_recorte(1.5, None) == "no raio de 1,5 km"
    assert (
        censo_map.onde_do_recorte(None, GEOMETRIA_TIPO_ISOCRONA_CARRO_10MIN) == "em 10 min de carro"
    )
    assert censo_map.onde_do_recorte(None, "poligono") == "na area"  # ASCII: excecao de RENDER
    assert censo_map._legenda_valor_ponto("Renda", "R$ 1") == "Renda no raio: R$ 1"


def _espiar_camadas(monkeypatch) -> list[dict]:
    chamadas: list[dict] = []
    original = censo_map._render_camada

    def _espiao(**kw):
        chamadas.append(kw)
        return original(**kw)

    monkeypatch.setattr(censo_map, "_render_camada", _espiao)
    return chamadas


def test_mapa_sem_kwargs_novos_chama_o_motor_e_as_camadas_como_antes(monkeypatch):
    setores = _setores()
    motor: list[dict] = []
    original_motor = censo_map.analisar_ponto_censitario_setores

    def _motor(*a, **kw):
        motor.append(kw)
        return original_motor(*a, **kw)

    monkeypatch.setattr(censo_map, "analisar_ponto_censitario_setores", _motor)
    camadas = _espiar_camadas(monkeypatch)
    censo_map.render_mapas_censitarios_combinados(LAT, LNG, setores, basemap=False)
    assert set(motor[0]) == {"raio_km", "competitors_df", "ultra_df"}
    for kw in camadas:
        assert "onde" not in kw and "rodape_recorte" not in kw
        assert kw["raio_km"] == 1.0
        assert kw.get("valor_ponto") is None or " no raio: " in kw["valor_ponto"]


def test_mapa_do_raio_de_2km_diz_qual_raio(monkeypatch):
    camadas = _espiar_camadas(monkeypatch)
    censo_map.render_mapas_censitarios_combinados(LAT, LNG, _setores(), raio_km=2.0, basemap=False)
    densidade = camadas[0]
    assert densidade["raio_km"] == 2.0  # rodape "Raio 2,0 km"
    assert densidade["valor_ponto"].startswith("Densidade no raio de 2 km: ")
    assert densidade["onde"] == "no raio de 2 km"


def test_mapa_da_isocrona_reaproveita_o_result_e_desenha_o_contorno(monkeypatch):
    setores = _setores()
    iso = _isocrona()
    result = analisar_ponto_censitario_setores(
        LAT, LNG, setores, geometria_wgs84=iso, geometria_tipo=GEOMETRIA_TIPO_ISOCRONA_CARRO_10MIN
    )

    def _nao_chame(*_a, **_kw):
        raise AssertionError("o mapa refez a intersecao em vez de usar o result")

    monkeypatch.setattr(censo_map, "analisar_ponto_censitario_setores", _nao_chame)
    camadas = _espiar_camadas(monkeypatch)
    mapas = censo_map.render_mapas_censitarios_combinados(
        LAT,
        LNG,
        setores,
        basemap=False,
        geometria_wgs84=iso,
        geometria_tipo=GEOMETRIA_TIPO_ISOCRONA_CARRO_10MIN,
        result=result,
    )
    densidade = camadas[0]
    assert densidade["raio_km"] is None  # sem "Raio 1,0 km" no rodape
    assert densidade["rodape_recorte"] == "Isocrona 10 min de carro (sem transito)"
    assert densidade["valor_ponto"].startswith("Densidade em 10 min de carro: ")
    # O contorno desenhado e' a ISOCRONA (MultiPolygon, com a ilha), nao um circulo.
    assert isinstance(densidade["circle_3857"], MultiPolygon)
    assert len(densidade["circle_3857"].geoms) == 2
    # O azul do contorno esta' no PNG.
    img = Image.open(BytesIO(mapas["densidade"])).convert("RGB")
    azul = censo_map._CIRCLE_RGBA[:3]
    assert any(cor == azul for _n, cor in img.getcolors(maxcolors=1_000_000))


def test_mapa_da_area_desenhada_usa_poligono_por_default(monkeypatch):
    camadas = _espiar_camadas(monkeypatch)
    area = _para_wgs(box(-1500, -1000, 1800, 1200))
    censo_map.render_mapas_censitarios_combinados(
        LAT, LNG, _setores(), basemap=False, geometria_wgs84=area
    )
    assert camadas[0]["rodape_recorte"] == "Area desenhada"
    assert camadas[0]["valor_ponto"].startswith("Densidade na area: ")


def test_mapa_rotulo_de_geometria_sem_geometria_levanta():
    with pytest.raises(ValueError, match="geometria_tipo sem geometria"):
        censo_map.render_mapas_censitarios_combinados(
            LAT, LNG, _setores(), basemap=False, geometria_tipo="poligono"
        )


# --------------------------------------------------------------------------- #
# Comparacao                                                                  #
# --------------------------------------------------------------------------- #
def _deck(itens: list[dict]) -> str:
    dados = {"titulo": "Comparação de pontos", "dePontos": True, "itens": itens}
    return _texto(bytes(gerar_pdf_comparacao(dados, mapas=[_png(), _png()])))


def test_rotulo_do_recorte():
    assert rotulo_do_recorte({}) is None
    assert rotulo_do_recorte({"recorte": None}) is None
    assert rotulo_do_recorte({"recorte": {"tipo": "raio_2km"}}) == "raio de 2 km"
    assert (
        rotulo_do_recorte({"recorte": {"tipo": "carro_10min", "area_km2": 38.24}})
        == "10 min de carro, sem trânsito, 38,2 km2"
    )
    # O texto do front (o da ficha) tem precedencia.
    assert (
        rotulo_do_recorte({"recorte": {"tipo": "raio_2km", "rotulo": "Raio de 2 km"}})
        == "Raio de 2 km"
    )


def test_deck_sem_recorte_nao_ganha_linha_nova():
    texto = _deck(
        [
            {"rotulo": "Santana", "indice": 0, "porDimensao": []},
            {"rotulo": "Tucuruvi", "indice": 1, "porDimensao": []},
        ]
    )
    assert "raio de" not in texto
    assert "recortes de tamanhos diferentes" not in texto


def test_deck_so_de_raio_1km_sai_igual_ao_deck_sem_recorte():
    # O front manda `recorte` em todo item de ponto, inclusive no raio de 1 km. Num deck so'
    # de 1 km o rotulo nao informa nada (o tamanho e' o mesmo) e mudaria capa, fotos e
    # Recomendacao do deck de sempre.
    base = [
        {"rotulo": "Santana", "indice": 0, "porDimensao": []},
        {"rotulo": "Tucuruvi", "indice": 1, "porDimensao": []},
    ]
    um_km = {"tipo": "raio_1km", "rotulo": "raio de 1 km", "area_km2": 3.14, "fator_regua": 1}
    com_recorte = [{**item, "recorte": dict(um_km)} for item in base]
    assert rotulos_dos_recortes(com_recorte) == [None, None]
    assert _deck(com_recorte) == _deck(base)
    assert "raio de 1 km" not in _deck(com_recorte)


def test_deck_imprime_o_recorte_de_cada_item():
    texto = _deck(
        [
            {
                "rotulo": "Santana",
                "indice": 0,
                "porDimensao": [],
                "recorte": {"tipo": "raio_2km", "fator_regua": 4.0, "area_km2": 12.57},
            },
            {
                "rotulo": "Tucuruvi",
                "indice": 1,
                "porDimensao": [],
                "recorte": {"tipo": "raio_1km", "fator_regua": 1.0, "area_km2": 3.14},
            },
        ]
    )
    assert "Santana (raio de 2 km)" in texto  # capa
    assert "lidera em 0 de 0 parâmetros - raio de 2 km" in texto  # recomendacao
    assert texto.count("raio de 2 km") >= 3  # capa, mapas e recomendacao
    assert "recortes de tamanhos diferentes" in texto
    # Num deck MISTO o raio de 1 km tambem e' dito: ali ele distingue.
    assert "Tucuruvi (raio de 1 km)" in texto


def test_minimo_dos_cards_cita_a_area_do_recorte_e_a_meta_escalada() -> None:
    """Subtitulo dos Big Numbers: o minimo para um recorte do tamanho analisado."""
    from motor_expansao.dashboard import censo_report as cr

    padrao = cr._minimos_dos_cards(cr._RECORTE_PADRAO)
    assert padrao[0] == "Mínimo para 3,14 km2: " + cr._format_number(cr._METAS.pop_total_raio, 0)
    assert "(média, qualquer área)" in padrao[1]
    assert set(padrao) == {0, 1, 2, 3, 4, 5}  # academias e mercado ocupado sem minimo proprio

    dois = cr._contexto_recorte(cr.recorte_pdf("raio_2km", fator_regua=4.0, area_km2=12.6))
    m2 = cr._minimos_dos_cards(dois)
    assert m2[0] == "Mínimo para 12,57 km2: " + cr._format_number(cr._METAS.pop_total_raio * 4, 0)
    assert m2[4].endswith(cr._format_number(cr._METAS.sam_fitness_potencial * 4, 0) + " alunos")
    # media nao escala
    assert m2[1] == padrao[1]
    # raio de 1 km explicito continua sendo o padrao (PDF identico)
    um = cr._contexto_recorte(cr.recorte_pdf("raio_1km", fator_regua=1.0, area_km2=3.14))
    assert um is cr._RECORTE_PADRAO
    for texto in (*padrao.values(), *m2.values()):
        texto.encode("latin-1")


# --------------------------------------------------------------------------- #
# 5 min de carro (DEC-074, Emenda 1)                                           #
# --------------------------------------------------------------------------- #
def test_recorte_pdf_dos_5_min_nomeia_5_min_em_latin1():
    rec = cr.recorte_pdf("carro_5min", fator_regua=1.01, area_km2=1.01 * math.pi)
    assert rec["rotulo_curto"] == "5 min de carro (sem trânsito)"
    ctx = cr._contexto_recorte(rec)
    assert ctx.onde == "em 5 min de carro"
    assert ctx.onde_longo == "em 5 min de carro, sem trânsito"
    assert ctx.artigo_nome == "a isócrona de 5 min de carro"
    textos = (ctx.rotulo_capa, ctx.rotulo_longo, ctx.onde, ctx.de_longo, ctx.descricao_censo)
    assert not any("10 min" in t for t in textos)
    for t in textos:
        t.encode("latin-1")
    # As metas de total escalam pelo fator, como nos 10 min.
    assert ctx.metas.pop_total_raio == pytest.approx(cr._METAS.pop_total_raio * 1.01)


def test_recorte_pdf_dos_10_min_nao_mudou():
    ctx = cr._contexto_recorte(_iso_recorte())
    assert ctx.rotulo_capa == "10 min de carro (sem trânsito)"
    assert ctx.de_longo == "da isócrona de 10 min de carro (sem trânsito)"
    assert ctx.descricao_censo == "isócrona de 10 min de carro sem trânsito (76,97 km2)"


def test_onde_e_rodape_do_mapa_dos_5_min(monkeypatch):
    from motor_expansao.dashboard.censo_point import GEOMETRIA_TIPO_ISOCRONA_CARRO_5MIN

    assert censo_map.onde_do_recorte(None, GEOMETRIA_TIPO_ISOCRONA_CARRO_5MIN) == (
        "em 5 min de carro"
    )
    camadas = _espiar_camadas(monkeypatch)
    censo_map.render_mapas_censitarios_combinados(
        LAT,
        LNG,
        _setores(),
        basemap=False,
        geometria_wgs84=_isocrona(),
        geometria_tipo=GEOMETRIA_TIPO_ISOCRONA_CARRO_5MIN,
    )
    assert camadas[0]["rodape_recorte"] == "Isocrona 5 min de carro (sem transito)"
    assert camadas[0]["valor_ponto"].startswith("Densidade em 5 min de carro: ")


def test_rotulo_do_recorte_dos_5_min_no_deck():
    assert (
        rotulo_do_recorte({"recorte": {"tipo": "carro_5min", "area_km2": 3.17}})
        == "5 min de carro, sem trânsito, 3,2 km2"
    )
