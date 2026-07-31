"""Testes do Relatorio Municipal (BLK-RELMUN-01).

Espelham o teste do Relatorio Pontual (`test_relatorio_pontual_censitario_export.py`):
agregacao, formula D1, 9 paginas/`/Count 9`/`%PDF-1.4`, headers das 9 secoes, fallback sem
`dominio_df`, fallback Pagina 6 sem bairro, fallback sem assets, anti-PII, mapas SEM rede
(`basemap=False`), contagem de pins por H3. NENHUM teste bate na rede.

CA2 (coexistencia): um teste prova que gerar o municipal NAO altera os bytes do Relatorio
Pontual recente nem do classico (isolamento estrito).
"""

from __future__ import annotations

from io import BytesIO

import h3
import numpy as np
import pandas as pd
import pytest
from PIL import Image

from motor_expansao.dashboard.relatorio_municipal import (
    _COR_APROVADO_MUNICIPAL,
    _COR_APROVADO_PROPRIO,
    _COR_REPROVADO,
    _PIN_LOGO_PX,
    CAPACIDADE_UNIDADE,
    PDF_SECTION_HEADERS,
    ULTRA_MAGENTA,
    _fit_contain,
    _hex_destacado_mask,
    _png_dimensions,
    _prettify_rede,
    _texto_zonas_sintese,
    _zonas_geometricas,
    agregar_municipio,
    gerar_payloads_download_relatorio_municipal,
    gerar_pdf_relatorio_municipal,
    render_download_relatorio_municipal,
    render_mapas_municipio,
)

# Strings de PII reais da lamina de contato do .pptx (image24) — NUNCA podem vazar no PDF.
_PII_FORBIDDEN = (
    b"vinicius",
    b"Vinicius",
    b"Vin\xedcius",
    b"96346-2974",
    b"@ultraacademia.com.br",
)


def _hex(lat: float, lng: float) -> str:
    return h3.latlng_to_cell(lat, lng, 7)


def _sample_df() -> pd.DataFrame:
    """4 hexes em SAO PAULO; 2 destacados (oferta>=2000), 2 nao (oferta<2000)."""
    base = [(-23.55, -46.63), (-23.56, -46.64), (-23.54, -46.62), (-23.57, -46.65)]
    rows = []
    for i, (la, lo) in enumerate(base):
        destacado = i < 2
        rows.append(
            {
                "hex_id": _hex(la, lo),
                "lat": la,
                "lng": lo,
                "nome_municipio": "SAO PAULO",
                "cidade": "SAO PAULO",
                "uf": "SP",
                "sam_fitness_potencial": 4000.0 if destacado else 1000.0,
                "oferta_efetiva_disponivel": 4451.0 if destacado else 500.0,
                "score_setor_2022_calibrado": 72.0 - i * 12.0,
                "score_oportunidade_residual": 60.0 - i * 5.0,
                "pop_total_setor_2022": 1500.0,
                "pop_total": 2000.0,
                "renda_per_capita": 3000.0,
                "penetracao_fitness_mercado_estimada": 12.5,
                "oferta_consumida_mercado_estimada": 1000.0 if destacado else 200.0,
            }
        )
    return pd.DataFrame(rows)


def _sample_dominio() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "nome_municipio": "SAO PAULO",
                "cluster_id": "c1",
                "tese_dominio": "dominar_white_space",
                "residual_total_cluster": 900.0,
                "oferta_efetiva_disponivel": 400.0,
            },
            {
                "nome_municipio": "SAO PAULO",
                "cluster_id": "c2",
                "tese_dominio": "abrir_com_disputa",
                "residual_total_cluster": 500.0,
                "oferta_efetiva_disponivel": 200.0,
            },
        ]
    )


def _sample_competitors() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"rede": "smart_fit", "lat": -23.55, "lng": -46.63, "hex_id_res7": _hex(-23.55, -46.63)},
            {"rede": "bio_ritmo", "lat": -23.56, "lng": -46.64, "hex_id_res7": _hex(-23.56, -46.64)},
            # fora do municipio (hex distante) -> nao deve contar
            {"rede": "smart_fit", "lat": -10.0, "lng": -40.0, "hex_id_res7": _hex(-10.0, -40.0)},
        ]
    )


def _sample_ultra() -> pd.DataFrame:
    return pd.DataFrame(
        [{"unidade": "Ultra Teste", "lat": -23.54, "lng": -46.62, "hex_id_res7": _hex(-23.54, -46.62)}]
    )


# ---------------------------------------------------------------------------
# Agregacao (D1, D4, D5, D6, zonas)
# ---------------------------------------------------------------------------


def test_agregar_municipio_formula_espaco_d1():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")

    # 2 destacados, soma 4451*2 = 8902; espaco = round(8902/2500) = 4.
    assert res["n_hex_amarelos"] == 2
    assert res["soma_oferta_amarelos"] == 8902.0
    assert res["espaco_para_academias"] == round(8902.0 / CAPACIDADE_UNIDADE)
    assert res["espaco_para_academias"] == 4
    assert res["n_hex_total"] == 4
    assert res["uf"] == "SP"


def test_cores_aprovados_verdes_blk_relmun_05():
    """BLK-RELMUN-05: aprovado proprio em verde forte; reprovado cinza inalterado.
    BLK-RELMUN-05-FU1 (Vinicius 2026-07-10): fallback municipal ajustado para
    amarelo-ambar (tom mais amarelado), ainda distinguivel do proprio e do cinza."""
    assert _COR_APROVADO_PROPRIO == (20, 170, 80)
    assert _COR_APROVADO_MUNICIPAL == (215, 200, 60)
    assert _COR_REPROVADO == (150, 156, 170)
    assert _COR_APROVADO_PROPRIO != _COR_APROVADO_MUNICIPAL != _COR_REPROVADO


def test_hex_destacado_criterio_so_residual_sem_sam():
    """BLK-RELMUN-03: destacado <=> oferta_efetiva_disponivel>=2000, INDEPENDENTE de SAM.
    Prova que o filtro de SAM foi REMOVIDO: hex com sam<3000 mas oferta>=2000 agora conta
    (antes NAO contava); hex com oferta<2000 NAO conta mesmo com sam alto."""
    df = pd.DataFrame(
        [
            {"sam_fitness_potencial": 1000.0, "oferta_efetiva_disponivel": 2500.0},  # NOVO -> True
            {"sam_fitness_potencial": 9000.0, "oferta_efetiva_disponivel": 500.0},   # -> False
            {"sam_fitness_potencial": 4000.0, "oferta_efetiva_disponivel": 4451.0},  # -> True
        ]
    )
    assert list(_hex_destacado_mask(df)) == [True, False, True]


def test_agregar_municipio_conta_hex_sam_baixo_oferta_alta():
    """BLK-RELMUN-03: hex com sam<3000 e oferta>=2000 entra em n_hex_amarelos e no espaco
    (antes do drop do SAM ele NAO entrava)."""
    df = pd.DataFrame(
        [
            {
                "hex_id": _hex(-23.55, -46.63), "lat": -23.55, "lng": -46.63,
                "nome_municipio": "SAO PAULO", "cidade": "SAO PAULO", "uf": "SP",
                "sam_fitness_potencial": 1000.0, "oferta_efetiva_disponivel": 3000.0,
                "score_setor_2022_calibrado": 50.0, "score_oportunidade_residual": 40.0,
                "pop_total_setor_2022": 1500.0, "pop_total": 2000.0, "renda_per_capita": 3000.0,
                "penetracao_fitness_mercado_estimada": 12.5,
                "oferta_consumida_mercado_estimada": 200.0,
            }
        ]
    )
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    assert res["n_hex_amarelos"] == 1
    assert res["soma_oferta_amarelos"] == 3000.0
    assert res["espaco_para_academias"] == round(3000.0 / CAPACIDADE_UNIDADE)  # == 1


def test_agregar_municipio_mercado_residual_d4_e_score_d5():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")

    # Mercado/Residual = soma de oferta_efetiva_disponivel do municipio (4451*2 + 500*2).
    esperado = 4451.0 * 2 + 500.0 * 2
    assert res["mercado_disponivel_pessoas"] == esperado
    assert res["residual_total_alunos"] == esperado
    # Score medio/max NaN-safe.
    assert res["score_censo_max"] == 72.0
    assert abs(res["score_censo_medio"] - (72 + 60 + 48 + 36) / 4) < 1e-6


def test_agregar_municipio_zonas_d2_d7():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", dominio_df=_sample_dominio())

    zonas = res["zonas"]
    assert res["n_zonas"] == 2
    # Ordenado por residual desc -> c1 (900) e Zona 1 = Ancora central; c2 (500) = Flancos.
    assert zonas[0]["zona_n"] == 1 and zonas[0]["rotulo"] == "Âncora central"
    assert zonas[0]["cluster_id"] == "c1"
    assert zonas[1]["zona_n"] == 2 and zonas[1]["rotulo"] == "Flancos laterais"


def test_agregar_municipio_pins_por_h3_d6():
    df = _sample_df()
    res = agregar_municipio(
        df,
        nome_municipio="SAO PAULO",
        competitors_df=_sample_competitors(),
        ultra_df=_sample_ultra(),
    )

    assert res["n_ultra"] == 1
    # 2 concorrentes dentro do municipio (o 3o cai num hex distante).
    assert res["n_concorrentes"] == 2
    assert res["concorrentes_por_rede"] == {"smart_fit": 1, "bio_ritmo": 1}


# ---------------------------------------------------------------------------
# FU1 — penetracao municipal, prettify de nomes, zonas geometricas
# ---------------------------------------------------------------------------


def test_penetracao_fitness_pct_consumo_sobre_total():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    consumo = 1000.0 * 2 + 200.0 * 2  # 2400
    residual = 4451.0 * 2 + 500.0 * 2  # 9902
    esperado = 100.0 * consumo / (consumo + residual)
    assert res["consumo_total_alunos"] == consumo
    assert abs(res["penetracao_fitness_pct"] - esperado) < 1e-6


def test_penetracao_fitness_pct_denominador_zero_eh_nan():
    df = _sample_df()
    # Zera consumo e oferta -> denominador 0 -> nan.
    df["oferta_efetiva_disponivel"] = 0.0
    df["oferta_consumida_mercado_estimada"] = 0.0
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    import math

    assert math.isnan(res["penetracao_fitness_pct"])


def test_prettify_rede_overrides_e_fallback():
    assert _prettify_rede("allp_fit") == "Allp Fit"
    assert _prettify_rede("bio_ritmo") == "Bio Ritmo"
    assert _prettify_rede("smart_fit") == "Smart Fit"
    assert _prettify_rede("bluefit") == "BlueFit"
    # Fallback generico: title-case trocando "_" por espaco.
    assert _prettify_rede("foo_bar_gym") == "Foo Bar Gym"
    assert _prettify_rede("") == "Concorrente"


def test_zonas_geometricas_ate_3_zonas_com_contagens():
    df = _sample_df()
    out = _zonas_geometricas(df)
    zonas = out["zonas"]
    assert 1 <= len(zonas) <= 3
    rotulos = {z["rotulo"] for z in zonas}
    assert rotulos.issubset({"Âncora central", "Flancos laterais", "Cerco"})
    # Soma das contagens == nro de hexes mapeados em hex_zona.
    assert sum(z["n_hex"] for z in zonas) == len(out["hex_zona"])
    # Numeracao sequencial 1..N.
    assert [z["zona_n"] for z in zonas] == list(range(1, len(zonas) + 1))


def test_zonas_geometricas_em_agregar_municipio():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    assert res["n_zonas_geo"] == len(res["zonas_geo"])
    assert res["n_zonas_geo"] >= 1
    assert isinstance(res["hex_zona_geo"], dict)


def test_zonas_geometricas_fallback_vazio():
    df = _sample_df().drop(columns=["hex_id"])
    out = _zonas_geometricas(df)
    assert out == {"hex_zona": {}, "zonas": []}


def test_agregar_municipio_sem_dominio_zonas_vazias():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", dominio_df=None)
    assert res["zonas"] == []
    assert res["n_zonas"] == 0


def test_agregar_municipio_fallback_cidade():
    df = _sample_df().drop(columns=["nome_municipio"])
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    assert res["n_hex_total"] == 4


# ---------------------------------------------------------------------------
# Mapas offline (sem rede)
# ---------------------------------------------------------------------------


def test_mapas_municipio_offline_sem_rede():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", dominio_df=_sample_dominio())
    mapas = render_mapas_municipio(
        df, res, competitors_df=_sample_competitors(), ultra_df=_sample_ultra(), basemap=False
    )
    assert set(mapas) == {"resumo", "score", "residual", "dominio", "cobertura"}
    for png in mapas.values():
        assert png.startswith(b"\x89PNG")
        assert len(png) > 1000


# ---------------------------------------------------------------------------
# BLK-RELPON-03 — sem letterbox (barra cinza) nos mapas do PDF
# ---------------------------------------------------------------------------


def test_fit_contain_pnl_1000x704_no_painel_540x380_sem_letterbox():
    """PNG re-proporcionado 1000x704 (aspect 1,4205) no painel padronizado 540x380 (1,4211):
    o encaixe CONTAIN cobre o painel nos DOIS eixos com sobra <= 1 pt (barra cinza eliminada)."""
    draw_w, draw_h, x, y = _fit_contain(1000, 704, 540.0, 380.0, x_anchor=34.0, y_anchor=100.0)
    assert abs(draw_h - 380.0) <= 1.0
    assert abs(draw_w - 540.0) <= 1.0
    # Centralizado a partir das ancoras.
    assert abs(x - (34.0 + (540.0 - draw_w) / 2.0)) < 1e-6
    assert abs(y - (100.0 + (380.0 - draw_h) / 2.0)) < 1e-6


def test_fit_contain_documenta_painel_560x380_sobra_lateral():
    """Painel NAO padronizado 560x380 (fallback do gate, NAO usado em producao): com o PNG
    1000x704 a altura domina o `min`, sobrando ~20 pt de largura (barra lateral fina). Este
    teste documenta o trade-off descrito no handoff; a producao usa 540 (sem sobra)."""
    draw_w, draw_h, _x, _y = _fit_contain(1000, 704, 560.0, 380.0)
    assert abs(draw_h - 380.0) <= 1.0  # altura preenchida
    assert (560.0 - draw_w) > 15.0  # sobra horizontal perceptivel (~20 pt) -> por isso 540


@pytest.mark.parametrize("camada", ["resumo", "score", "residual", "dominio", "cobertura"])
def test_render_mapas_municipio_png_altura_704(camada):
    """Smoke: por padrao os 5 PNGs sao gerados com altura 704 (aspect 1,4205 do painel),
    garantindo que o gerador acompanhou a mudanca do encaixe (sem letterbox)."""
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", dominio_df=_sample_dominio())
    mapas = render_mapas_municipio(
        df, res, competitors_df=_sample_competitors(), ultra_df=_sample_ultra(), basemap=False
    )
    dims = _png_dimensions(mapas[camada])
    assert dims is not None
    assert dims == (1000, 704)


def test_mapa_municipal_marcador_ultra_quadrado_blk_relpon_09():
    """BLK-RELPON-09: o marcador da unidade Ultra e a LOGO QUADRADA, nao o balao 34x34.

    Com `_ICON_CACHE` limpo, a Ultra cai no fallback de sigla -> placa na cor da marca
    (#C8001E). `_sample_ultra()` tem exatamente 1 unidade, e nenhuma outra cor do modulo
    e (200,0,30) (ULTRA_MAGENTA/TURQUESA/LARANJA sao distintas), entao a mascara isola o
    marcador. O footprint tem de ser QUADRADO e caber no lado `_PIN_LOGO_PX` -- o balao
    anterior era mais alto que largo e media 34 px.
    """
    from motor_expansao.dashboard.competitors import _ICON_CACHE

    _ICON_CACHE.pop("__ultra__", None)
    try:
        df = _sample_df()
        res = agregar_municipio(df, nome_municipio="SAO PAULO", dominio_df=_sample_dominio())
        # a camada "resumo" e onde `_draw_pins` roda; "cobertura" e gerada sem pins por design
        mapas = render_mapas_municipio(
            df, res, competitors_df=_sample_competitors(), ultra_df=_sample_ultra(), basemap=False
        )
        image = Image.open(BytesIO(mapas["resumo"])).convert("RGB")
        mask = np.all(np.array(image) == np.array([200, 0, 30]), axis=-1)
        ys, xs = np.nonzero(mask)

        # interior do card (26 - 2 de sombra - 2x2 de borda = 20 px) menos a sigla
        assert 250 <= int(mask.sum()) <= 700
        assert 16 <= (int(xs.max()) - int(xs.min()) + 1) <= _PIN_LOGO_PX
        assert 16 <= (int(ys.max()) - int(ys.min()) + 1) <= _PIN_LOGO_PX
    finally:
        _ICON_CACHE.pop("__ultra__", None)


def test_rotulo_de_valor_fica_acima_do_marcador_blk_relpon_09_fu1():
    """BLK-RELPON-09-FU1: o rotulo de Residual Fitness do hexagono vence o marcador.

    Gate visual de Vinicius (2026-07-21): no Municipal os marcadores quadrados cobriam os
    numeros dos hexagonos -- o dado principal da pagina. O FU1 passou os rotulos para uma
    overlay propria, composta DEPOIS de `_draw_pins`.

    Teste DIFERENCIAL e adversarial: posiciona uma unidade Ultra EXATAMENTE no centroide de
    um hex destacado, forcando colisao maxima com o rotulo, e compara a tinta do texto
    (`_CIRCLE_INK`) na caixa do rotulo contra o render SEM nenhum pin. Se a ordem regredir
    (pins por ultimo), a placa opaca de 26 px centrada no mesmo ponto engole o numero e a
    contagem despenca. A tolerancia e estreita de proposito: a placa branca do rotulo tem
    alpha 200, entao o pin por baixo NAO pode remover tinta.
    """
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", dominio_df=_sample_dominio())

    # centroide real do 1o hex destacado (oferta 4451 -> rotulo "4.451")
    hex_destacado = str(df.loc[0, "hex_id"])
    lat_c, lng_c = h3.cell_to_latlng(hex_destacado)
    ultra_no_centro = pd.DataFrame(
        [{"rede": "ultra", "lat": lat_c, "lng": lng_c, "hex_id_res7": hex_destacado}]
    )

    com_pin = render_mapas_municipio(
        df, res, competitors_df=None, ultra_df=ultra_no_centro, basemap=False
    )["resumo"]
    sem_pin = render_mapas_municipio(
        df, res, competitors_df=None, ultra_df=None, basemap=False
    )["resumo"]

    arr_com = np.array(Image.open(BytesIO(com_pin)).convert("RGB")).astype(np.int16)
    arr_sem = np.array(Image.open(BytesIO(sem_pin)).convert("RGB")).astype(np.int16)

    # A UNICA diferenca entre os dois renders e o marcador -> o diff LOCALIZA o pin,
    # sem depender de projecao nem de constante de layout.
    diff = np.any(arr_com != arr_sem, axis=-1)
    assert diff.sum() > 0, "o pin nao foi desenhado; o teste seria vacuo"
    ys, xs = np.nonzero(diff)
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1

    # A sonda e a PLACA MAGENTA do rotulo (BLK-RELPON-09-FU1): e a unica cor do mapa que o
    # marcador nao consegue imitar -- hexes sao verdes/cinza, basemap e claro e as redes sao
    # pretas/azuis/amarelas. Muito mais area que a tinta do texto (fonte 8 e antialiasada).
    # Tolerancia de 25/canal cobre o alpha 240 da placa blendando com o fundo por baixo.
    magenta = np.array(ULTRA_MAGENTA, dtype=np.int16)
    mask_sem = np.all(np.abs(arr_sem[y0:y1, x0:x1] - magenta) <= 25, axis=-1)
    mask_com = np.all(np.abs(arr_com[y0:y1, x0:x1] - magenta) <= 25, axis=-1)
    tinta_sem = int(mask_sem.sum())
    sobreviveu = int((mask_sem & mask_com).sum())

    # (1) a colisao e REAL: ha placa de rotulo debaixo da area do marcador
    assert tinta_sem >= 60, (
        f"sem colisao real ({tinta_sem} px de placa sob o marcador) -- o teste seria vacuo"
    )
    # (2) o marcador cobriu de fato aquela regiao (senao nao houve teste de ordem nenhum)
    assert int(diff[y0:y1, x0:x1].sum()) >= 200, "marcador pequeno demais para provar a ordem"
    # (3) e NENHUM pixel de tinta do numero foi perdido -> os rotulos vencem os pins
    assert sobreviveu >= tinta_sem * 0.9, (
        f"o marcador cobriu o rotulo: {sobreviveu}/{tinta_sem} px de placa sobreviveram "
        "-- a overlay de rotulos precisa ser composta DEPOIS de _draw_pins"
    )


# ---------------------------------------------------------------------------
# PDF (8 paginas / headers / formato)
# ---------------------------------------------------------------------------


def test_pdf_municipal_9_paginas_e_secoes():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", dominio_df=_sample_dominio())
    mapas = render_mapas_municipio(df, res, basemap=False)

    pdf_bytes = gerar_pdf_relatorio_municipal(res, mapas, ultra_dir="data/ultra")

    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert b"/Count 9" in pdf_bytes
    assert len(pdf_bytes) > 15_000
    for header in PDF_SECTION_HEADERS:
        assert header.encode("latin-1") in pdf_bytes
    # Carimbo de versao (D8) no rodape.
    assert b"BLK-RELMUN-01" in pdf_bytes
    # Atribuicao de tiles (DEC-011) no rodape.
    assert b"OpenStreetMap" in pdf_bytes
    assert b"CARTO" in pdf_bytes
    # BLK-RELMUN-03: legenda do criterio de inclusao do hexagono, com o limiar REAL do
    # _hex_destacado_mask (SO Residual Fitness >= 2.000; termo de SAM removido).
    assert b"SAM Fitness" not in pdf_bytes
    assert b"Residual Fitness >= 2.000" in pdf_bytes
    # BLK-RELMUN-05: wording neutro - PDF nao deve mais mencionar "amarelo(s)" como texto exibido.
    assert b"amarelo" not in pdf_bytes.lower()
    assert "hexágonos destacados".encode("latin-1") in pdf_bytes
    # FU1 (slide novo, pos-capa): "Visao Geral do Municipio" com bloco de regioes consideradas.
    assert "Visão Geral do Município".encode("latin-1") in pdf_bytes
    assert "REGIÕES CONSIDERADAS".encode("latin-1") in pdf_bytes
    assert "regiões consideradas nas páginas seguintes".encode("latin-1") in pdf_bytes


def test_agregar_municipio_cobertura_aprovados_reprovados():
    """FU1: agregar expoe n_aprovados/n_reprovados/n_hex_municipio para o slide de cobertura."""
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", dominio_df=_sample_dominio())
    assert res["n_hex_municipio"] == res["n_hex_total"]
    assert res["n_aprovados"] == res["n_hex_amarelos"]
    assert res["n_reprovados"] == res["n_hex_municipio"] - res["n_aprovados"]
    assert res["n_reprovados"] >= 0


def test_mapa_cobertura_offline():
    """FU1: a camada 'cobertura' (aprovados/reprovados do municipio, sem pins) gera PNG offline."""
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", dominio_df=_sample_dominio())
    mapas = render_mapas_municipio(df, res, basemap=False)
    assert mapas["cobertura"].startswith(b"\x89PNG")
    assert len(mapas["cobertura"]) > 1000


def test_pdf_municipal_offline_safe_sem_assets(tmp_path):
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", dominio_df=_sample_dominio())
    mapas = render_mapas_municipio(df, res, basemap=False)

    pdf_bytes = gerar_pdf_relatorio_municipal(res, mapas, ultra_dir=tmp_path)

    assert pdf_bytes.startswith(b"%PDF")
    assert b"/Count 9" in pdf_bytes
    for header in PDF_SECTION_HEADERS:
        assert header.encode("latin-1") in pdf_bytes


def _df_3_aprovados() -> pd.DataFrame:
    """3 hexes APROVADOS (oferta>=2000) em celulas res-7 DISTINTAS e bem separadas
    (~7 km entre si) -> 3 zonas geometricas (Ancora/Flancos/Cerco). Mais 1 reprovado com score
    (prova que a estrategia NAO se espalha para nao-aprovados — decisao de produto 2026-06-24)."""
    coords = [(-23.50, -46.60), (-23.55, -46.65), (-23.60, -46.70)]
    rows = []
    for la, lo in coords:
        rows.append(
            {
                "hex_id": _hex(la, lo),
                "lat": la,
                "lng": lo,
                "nome_municipio": "SAO PAULO",
                "cidade": "SAO PAULO",
                "uf": "SP",
                "sam_fitness_potencial": 4000.0,
                "oferta_efetiva_disponivel": 4451.0,
                "score_setor_2022_calibrado": 72.0,
                "score_oportunidade_residual": 60.0,
                "pop_total_setor_2022": 1500.0,
                "pop_total": 2000.0,
                "renda_per_capita": 3000.0,
                "penetracao_fitness_mercado_estimada": 12.5,
                "oferta_consumida_mercado_estimada": 1000.0,
            }
        )
    # 1 reprovado (sam/oferta baixos) com score notna, em celula distinta.
    rows.append(
        {
            "hex_id": _hex(-23.40, -46.50),
            "lat": -23.40,
            "lng": -46.50,
            "nome_municipio": "SAO PAULO",
            "cidade": "SAO PAULO",
            "uf": "SP",
            "sam_fitness_potencial": 1000.0,
            "oferta_efetiva_disponivel": 500.0,
            "score_setor_2022_calibrado": 60.0,
            "score_oportunidade_residual": 40.0,
            "pop_total_setor_2022": 1500.0,
            "pop_total": 2000.0,
            "renda_per_capita": 3000.0,
            "penetracao_fitness_mercado_estimada": 12.5,
            "oferta_consumida_mercado_estimada": 200.0,
        }
    )
    return pd.DataFrame(rows)


def test_pdf_municipal_fallback_sem_dominio_pagina_6():
    """Sem dominio_df -> Paginas 5-6 usam as zonas GEOMETRICAS (FU1), sem excecao.

    Decisao de produto (2026-06-24): as zonas sao formadas SOMENTE pelos hexes APROVADOS
    (sem fallback para todo o municipio). 3 aprovados em celulas distintas -> 3 zonas.
    """
    df = _df_3_aprovados()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", dominio_df=None)
    mapas = render_mapas_municipio(df, res, basemap=False)

    pdf_bytes = gerar_pdf_relatorio_municipal(res, mapas)

    assert b"/Count 9" in pdf_bytes
    # BLK-RELMUN-02: sem fonte de bairro, a Pagina 6 cai no fallback gracioso por zona
    # geometrica (sem a antiga nota "indisponivel" como texto principal).
    assert b"Bairros indisponiveis na base atual" not in pdf_bytes
    assert "Bairros não mapeados na base IBGE 2022".encode("latin-1") in pdf_bytes
    # FU1: as 3 estrategias geometricas aparecem (3 aprovados em celulas distintas).
    assert "Âncora central".encode("latin-1") in pdf_bytes
    assert b"Flancos laterais" in pdf_bytes
    assert b"Cerco" in pdf_bytes


def test_zonas_geometricas_so_aprovados_sem_fallback():
    """Decisao de produto (2026-06-24): com 1 unico hex aprovado, forma-se SO 1 zona
    (Ancora) — a estrategia NAO se espalha para os hexes nao-aprovados do municipio."""
    df = _df_3_aprovados().copy()
    # Rebaixa 2 dos 3 aprovados -> sobra 1 aprovado; os rebaixados tem score notna.
    df.loc[df.index[1:3], "sam_fitness_potencial"] = 1000.0
    df.loc[df.index[1:3], "oferta_efetiva_disponivel"] = 500.0
    out = _zonas_geometricas(df)
    assert len(out["zonas"]) == 1
    assert out["zonas"][0]["rotulo"] == "Âncora central"
    assert out["zonas"][0]["n_hex"] == 1
    assert len(out["hex_zona"]) == 1


# ---------------------------------------------------------------------------
# BLK-RELMUN-06 — texto dinamico do card 3 (Movimento Recomendado) da Sintese.
# ---------------------------------------------------------------------------


def test_texto_zonas_sintese_0_zonas():
    assert _texto_zonas_sintese(None) == (
        "Movimento Recomendado: hexágonos aprovados insuficientes para zonas de atuação "
        "neste município."
    )
    assert _texto_zonas_sintese([]) == (
        "Movimento Recomendado: hexágonos aprovados insuficientes para zonas de atuação "
        "neste município."
    )


def test_texto_zonas_sintese_1_zona_ancora():
    zonas = [{"rotulo": "Âncora central"}]
    assert _texto_zonas_sintese(zonas) == (
        "Movimento Recomendado: adensar o núcleo central, concentrando a expansão "
        "na região de maior aprovação."
    )


def test_texto_zonas_sintese_2_zonas_ancora_flancos():
    zonas = [{"rotulo": "Âncora central"}, {"rotulo": "Flancos laterais"}]
    assert _texto_zonas_sintese(zonas) == (
        "Movimento Recomendado: adensar o núcleo central e avançar pelos flancos, "
        "capturando os residuais laterais."
    )


def test_texto_zonas_sintese_3_zonas_completas():
    zonas = [
        {"rotulo": "Âncora central"},
        {"rotulo": "Flancos laterais"},
        {"rotulo": "Cerco"},
    ]
    assert _texto_zonas_sintese(zonas) == (
        "Movimento Recomendado: posicionamento periférico, cercar o núcleo pelos "
        "flancos antes da concorrência."
    )


def test_texto_zonas_sintese_presenca_parcial_defensivo():
    """Caso fora da invariante (so Flancos, sem Ancora) — nao lanca excecao; cai no texto
    de 2 zonas por pertencimento de rotulo (comportamento aceito, nao e bug)."""
    zonas = [{"rotulo": "Flancos laterais"}]
    assert _texto_zonas_sintese(zonas) == (
        "Movimento Recomendado: adensar o núcleo central e avançar pelos flancos, "
        "capturando os residuais laterais."
    )


def _assert_card3_wrapped_lines(pdf_bytes: bytes, linhas: list[str]) -> None:
    """Confere o texto do card 3 quebrado nas MESMAS linhas que `multi_cell` produz.

    `multi_cell` emite um comando de texto (Tj) por linha quebrada no content stream do
    PDF; a sentenca INTEIRA (com todas as palavras) NAO aparece como um unico run de bytes
    contiguo quando ela ocupa mais de 1 linha (a largura do card, card_w-32 a 12pt, forca a
    quebra). Por isso o assert e por LINHA (cada uma cabe inteira em 1 Tj), nao pela frase
    completa - caso contrario o teste falharia mesmo com o texto certo renderizado.
    """
    for linha in linhas:
        assert linha.encode("latin-1") in pdf_bytes, linha


def test_pdf_municipal_sintese_texto_zonas_3_zonas():
    """Integracao: 3 aprovados em celulas distintas -> 3 zonas -> texto completo no card 3."""
    df = _df_3_aprovados()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", dominio_df=None)
    mapas = render_mapas_municipio(df, res, basemap=False)
    pdf_bytes = gerar_pdf_relatorio_municipal(res, mapas)

    assert res["n_zonas_geo"] == 3
    _assert_card3_wrapped_lines(
        pdf_bytes,
        [
            "Movimento Recomendado: posicionamento",
            "periférico, cercar o núcleo pelos flancos antes",
            "da concorrência.",
        ],
    )
    # Regressao: cards 1 e 2 e o VALOR do card 3 seguem intocados.
    # Notas: os textos completos dos cards 1/2 tambem quebram em linha (mesma razao do
    # helper acima); usa-se um trecho contido em UMA linha so (nao cruza o wrap).
    assert "fitness atual baixa".encode("latin-1") in pdf_bytes
    assert "academia regular".encode("latin-1") in pdf_bytes
    assert f"{res['n_zonas_geo']} zonas de atuação".encode("latin-1") in pdf_bytes


def test_pdf_municipal_sintese_texto_zonas_2_zonas():
    """Integracao: rebaixa o 3o aprovado -> sobram 2 aprovados -> 2 zonas -> texto de 2 zonas."""
    df = _df_3_aprovados().copy()
    df.loc[df.index[2:3], "sam_fitness_potencial"] = 1000.0
    df.loc[df.index[2:3], "oferta_efetiva_disponivel"] = 500.0
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", dominio_df=None)
    mapas = render_mapas_municipio(df, res, basemap=False)
    pdf_bytes = gerar_pdf_relatorio_municipal(res, mapas)

    assert res["n_zonas_geo"] == 2
    _assert_card3_wrapped_lines(
        pdf_bytes,
        [
            "Movimento Recomendado: adensar o núcleo",
            "central e avançar pelos flancos, capturando",
            "os residuais laterais.",
        ],
    )
    # Notas: os textos completos dos cards 1/2 tambem quebram em linha (mesma razao do
    # helper acima); usa-se um trecho contido em UMA linha so (nao cruza o wrap).
    assert "fitness atual baixa".encode("latin-1") in pdf_bytes
    assert "academia regular".encode("latin-1") in pdf_bytes
    assert f"{res['n_zonas_geo']} zonas de atuação".encode("latin-1") in pdf_bytes


def test_pdf_municipal_sintese_texto_zonas_1_zona():
    """Integracao: so 1 aprovado (padrao de test_zonas_geometricas_so_aprovados_sem_fallback)
    -> 1 zona -> texto de 1 zona (Ancora central)."""
    df = _df_3_aprovados().copy()
    df.loc[df.index[1:3], "sam_fitness_potencial"] = 1000.0
    df.loc[df.index[1:3], "oferta_efetiva_disponivel"] = 500.0
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", dominio_df=None)
    mapas = render_mapas_municipio(df, res, basemap=False)
    pdf_bytes = gerar_pdf_relatorio_municipal(res, mapas)

    assert res["n_zonas_geo"] == 1
    _assert_card3_wrapped_lines(
        pdf_bytes,
        [
            "Movimento Recomendado: adensar o núcleo",
            "central, concentrando a expansão na região",
            "de maior aprovação.",
        ],
    )
    # Notas: os textos completos dos cards 1/2 tambem quebram em linha (mesma razao do
    # helper acima); usa-se um trecho contido em UMA linha so (nao cruza o wrap).
    assert "fitness atual baixa".encode("latin-1") in pdf_bytes
    assert "academia regular".encode("latin-1") in pdf_bytes
    assert f"{res['n_zonas_geo']} zonas de atuação".encode("latin-1") in pdf_bytes


def test_pdf_municipal_sintese_texto_zonas_0_zonas():
    """Integracao: sem hexes relevantes/aprovados -> 0 zonas -> texto de fallback no card 3."""
    df = _sample_df().drop(columns=["hex_id"])
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", dominio_df=None)
    mapas = render_mapas_municipio(df, res, basemap=False)
    pdf_bytes = gerar_pdf_relatorio_municipal(res, mapas)

    assert res["n_zonas_geo"] == 0
    _assert_card3_wrapped_lines(
        pdf_bytes,
        [
            "Movimento Recomendado: hexágonos",
            "aprovados insuficientes para zonas de",
            "atuação neste município.",
        ],
    )
    # Notas: os textos completos dos cards 1/2 tambem quebram em linha (mesma razao do
    # helper acima); usa-se um trecho contido em UMA linha so (nao cruza o wrap).
    assert "fitness atual baixa".encode("latin-1") in pdf_bytes
    assert "academia regular".encode("latin-1") in pdf_bytes
    assert f"{res['n_zonas_geo']} zonas de atuação".encode("latin-1") in pdf_bytes


def test_pdf_municipal_fallback_sem_hexes_relevantes_pagina_5():
    """Sem hexes relevantes -> Pagina 5 cai no texto explicativo, sem excecao."""
    df = _sample_df().drop(columns=["hex_id"])
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", dominio_df=None)
    mapas = render_mapas_municipio(df, res, basemap=False)

    pdf_bytes = gerar_pdf_relatorio_municipal(res, mapas)

    assert b"/Count 9" in pdf_bytes
    assert b"Hexes relevantes insuficientes" in pdf_bytes


def test_pdf_municipal_pagina_6_fallback_sem_bairro():
    """BLK-RELMUN-02: sem `bairros_por_hex` -> Pagina 6 cai no fallback por zona, sem excecao
    e sem a antiga nota 'indisponivel' como texto principal."""
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", dominio_df=_sample_dominio())
    assert res["bairros_por_zona"] == [] or all(
        not z.get("bairros") for z in res["bairros_por_zona"]
    )
    mapas = render_mapas_municipio(df, res, basemap=False)
    pdf_bytes = gerar_pdf_relatorio_municipal(res, mapas)
    assert b"/Count 9" in pdf_bytes
    assert b"Bairros indisponiveis na base atual" not in pdf_bytes
    assert "Bairros não mapeados na base IBGE 2022".encode("latin-1") in pdf_bytes
    # Sem PII no fallback.
    for needle in _PII_FORBIDDEN:
        assert needle not in pdf_bytes


def _bairros_por_hex_sample(df: pd.DataFrame) -> dict[str, str]:
    """Mapa hex_id -> bairro REAL (nomes IBGE-like) para os 4 hexes do _sample_df."""
    hexes = list(df["hex_id"])
    nomes = ["Centro", "Bela Vista", "Cidade Nova", "Cascata"]
    return {str(h): nomes[i % len(nomes)] for i, h in enumerate(hexes)}


def test_agregar_municipio_bairros_por_zona_com_fonte():
    """A2: com `bairros_por_hex`, agregar popula `bairros_por_zona` agrupado por zona."""
    df = _sample_df()
    bairros = _bairros_por_hex_sample(df)
    res = agregar_municipio(
        df, nome_municipio="SAO PAULO", uf="SP", bairros_por_hex=bairros
    )
    bpz = res["bairros_por_zona"]
    assert isinstance(bpz, list) and bpz
    # Cada zona presente reporta os bairros distintos dela.
    todos = {b for z in bpz for b in z["bairros"]}
    assert todos  # pelo menos 1 bairro real agrupado
    assert todos.issubset({"Centro", "Bela Vista", "Cidade Nova", "Cascata"})
    assert res["n_bairros_total"] == sum(z["n_bairros"] for z in bpz)
    # Default None preserva comportamento anterior (sem bairros).
    res_sem = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    assert all(not z.get("bairros") for z in res_sem["bairros_por_zona"])


def test_pdf_municipal_pagina_6_com_bairros_reais():
    """A2: nomes de bairro REAIS aparecem nos bytes do PDF, /Count 9 mantido, sem PII."""
    df = _sample_df()
    bairros = _bairros_por_hex_sample(df)
    res = agregar_municipio(
        df, nome_municipio="SAO PAULO", uf="SP", dominio_df=_sample_dominio(),
        bairros_por_hex=bairros,
    )
    mapas = render_mapas_municipio(df, res, basemap=False)
    pdf_bytes = gerar_pdf_relatorio_municipal(res, mapas)

    assert b"/Count 9" in pdf_bytes
    # Pelo menos um bairro real impresso na Pagina 6.
    assert any(nome.encode("latin-1") in pdf_bytes for nome in ("Centro", "Bela Vista", "Cidade Nova", "Cascata"))
    # Nota de fonte IBGE quando ha bairros (cascata bairro -> subdistrito -> distrito).
    assert b"bairro do setor" in pdf_bytes
    # Sem a nota de fallback nem PII.
    assert b"Bairros indisponiveis na base atual" not in pdf_bytes
    for needle in _PII_FORBIDDEN:
        assert needle not in pdf_bytes


def test_carregar_bairros_por_hex_fallback_sem_dir():
    """A2.3: helper de leitura retorna {} sem censo_geo_dir/cod (offline, sem excecao)."""
    from motor_expansao.dashboard.relatorio_municipal import _carregar_bairros_por_hex

    assert _carregar_bairros_por_hex(None, None, None) == {}
    assert _carregar_bairros_por_hex("SP", "3550308", None) == {}


def test_pdf_municipal_marca_dagua_solicitante():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    mapas = render_mapas_municipio(df, res, basemap=False)

    pdf_bytes = gerar_pdf_relatorio_municipal(res, mapas, solicitante="Analista Teste")

    assert b"Ultra Academia" in pdf_bytes
    assert b"Analista Teste" in pdf_bytes
    # Uma marca d'agua por pagina (8) -> >= 8 ocorrencias.
    assert pdf_bytes.count(b"Ultra Academia") >= 8


def test_pdf_municipal_sem_pii():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", dominio_df=_sample_dominio())
    mapas = render_mapas_municipio(df, res, basemap=False)

    pdf_bytes = gerar_pdf_relatorio_municipal(res, mapas, ultra_dir="data/ultra")

    for needle in _PII_FORBIDDEN:
        assert needle not in pdf_bytes


def test_payloads_e_helper_streamlit_download():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    mapas = render_mapas_municipio(df, res, basemap=False)

    payloads = gerar_payloads_download_relatorio_municipal(res, mapas)
    assert payloads.pdf_bytes.startswith(b"%PDF")
    assert payloads.pdf_filename == "relatorio_municipal_sp_sao_paulo.pdf"

    class DummyStreamlit:
        def __init__(self):
            self.calls = []

        def download_button(self, label, *, data, file_name, mime):
            self.calls.append({"label": label, "data": data, "file_name": file_name, "mime": mime})

    dummy = DummyStreamlit()
    rendered = render_download_relatorio_municipal(dummy, res, mapas)
    assert rendered.pdf_bytes.startswith(b"%PDF")
    assert [c["mime"] for c in dummy.calls] == ["application/pdf"]


# ---------------------------------------------------------------------------
# CA2 — coexistencia: o Relatorio Pontual fica BYTE-A-BYTE intocado.
# ---------------------------------------------------------------------------


def test_coexistencia_relatorio_pontual_intocado():
    """Gerar o municipal NAO altera os bytes do Relatorio Pontual (recente e classico)."""
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
        gerar_pdf_relatorio_pontual_censitario,
    )

    lat_c, lng_c = -23.55, -46.63

    def _to_wgs(local_geom):
        tr = Transformer.from_crs(_local_metric_crs(lat_c, lng_c), CRS_ORIGEM_CENSO, always_xy=True)
        return transform(tr.transform, local_geom)

    def _rec(cod, geom, *, pop, renda, score):
        gw = _to_wgs(geom)
        minx, miny, maxx, maxy = gw.bounds
        return {
            "cod_setor": cod, "uf": "SP", "cod_municipio": "3550308", "nome_municipio": "SAO PAULO",
            "area_setor_m2": float(geom.area), "geometry_wkb": gw.wkb,
            "bbox_minx": minx, "bbox_miny": miny, "bbox_maxx": maxx, "bbox_maxy": maxy,
            "pop_total_setor_2022": pop, "renda_per_capita_setor_2022_calibrada": renda,
            "densidade_pop_setor_hab_km2": pop / (geom.area / 1_000_000.0),
            "score_setor_2022_calibrado": score, "flag_renda_disponivel": True,
            "flag_geometria_valida": True, "qualidade_join_uf": "A",
        }

    setores = pd.DataFrame(
        [
            _rec("355030801000001", box(-700, -700, 0, 700), pop=800, renda=2100, score=64),
            _rec("355030801000002", box(0, -700, 700, 700), pop=1400, renda=2600, score=86),
        ]
    )
    result = analisar_ponto_censitario_setores(lat_c, lng_c, setores)
    mapas_pontual = render_mapas_censitarios_combinados(
        lat_c, lng_c, setores, width=720, height=520, basemap=False
    )

    antes = gerar_pdf_relatorio_pontual_censitario(result, mapas_pontual, ultra_dir="data/ultra")

    # Gera o municipal no meio.
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", dominio_df=_sample_dominio())
    _ = gerar_pdf_relatorio_municipal(res, render_mapas_municipio(df, res, basemap=False))

    depois = gerar_pdf_relatorio_pontual_censitario(result, mapas_pontual, ultra_dir="data/ultra")

    assert antes == depois


# ---------------------------------------------------------------------------
# Fix 2 BLK-PERF-01a: df_pre_filtrado produz resultado identico ao full-scan
# ---------------------------------------------------------------------------


def test_agregar_municipio_prefiltrado_identico_ao_nacional():
    """Fix 2 BLK-PERF-01a: df_pre_filtrado produz resultado identico ao full-scan nacional."""
    df_sp = _sample_df()  # 4 linhas de SAO PAULO
    outras = pd.DataFrame([
        {
            "hex_id": _hex(-3.0, -60.0), "lat": -3.0, "lng": -60.0,
            "nome_municipio": "MANAUS", "cidade": "MANAUS", "uf": "AM",
            "sam_fitness_potencial": 100.0, "oferta_efetiva_disponivel": 100.0,
            "score_setor_2022_calibrado": 30.0, "score_oportunidade_residual": 20.0,
            "pop_total_setor_2022": 500.0, "pop_total": 800.0, "renda_per_capita": 1500.0,
            "penetracao_fitness_mercado_estimada": 5.0,
            "oferta_consumida_mercado_estimada": 50.0,
        }
    ] * 100)  # 100 linhas de outro municipio
    df_nacional = pd.concat([df_sp, outras], ignore_index=True)

    result_full = agregar_municipio(df_nacional, nome_municipio="SAO PAULO", uf="SP")
    df_muni = df_nacional.loc[
        df_nacional["nome_municipio"].astype(str).str.strip().str.casefold() == "sao paulo"
    ].copy()
    result_pre = agregar_municipio(
        df_nacional, nome_municipio="SAO PAULO", uf="SP", df_pre_filtrado=df_muni
    )

    for key in (
        "n_hex_total", "n_hex_amarelos", "soma_oferta_amarelos", "espaco_para_academias",
        "mercado_disponivel_pessoas", "score_censo_max",
    ):
        assert result_full[key] == result_pre[key], f"Divergencia em {key!r}"


# ── BLK-BASEMAP-02/03: basemap self-host no Relatorio Municipal ─────────────────────────────
# O BLK-BASEMAP-02 trocou o fundo pelo tileserver proprio; o BLK-BASEMAP-03 trouxe o overlay de
# rotulos do Pontual para ca, porque o estilo `ultra-maptiler` nao tem `transportation_name` e o
# mapa municipal estava saindo com as ruas desenhadas e SEM nome. Consequencia direta na
# atribuicao: o CARTO volta a ser consumido nos DOIS modos (emenda a DEC-011).


def test_municipal_basemap_source_alterna_por_env(monkeypatch):
    from motor_expansao.dashboard import relatorio_municipal as rm

    class _FakeCartoDB:
        Voyager = "provider-voyager-sentinela"

    fake_ctx = type("_C", (), {"providers": type("_P", (), {"CartoDB": _FakeCartoDB})()})()

    monkeypatch.delenv(rm._BASEMAP_TILES_URL_ENV, raising=False)
    assert rm._basemap_source(fake_ctx) == "provider-voyager-sentinela"

    url = "http://motor_expansao_tileserver:8080/styles/ultra-maptiler/{z}/{x}/{y}@2x.png"
    monkeypatch.setenv(rm._BASEMAP_TILES_URL_ENV, url)
    assert rm._basemap_source(fake_ctx) == url


def _mapa_resumo(*, basemap: bool) -> bytes:
    """PNG da camada `resumo` com a amostra padrao do modulo — atalho dos testes de overlay."""
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", dominio_df=_sample_dominio())
    mapas = render_mapas_municipio(
        df,
        res,
        competitors_df=_sample_competitors(),
        ultra_df=_sample_ultra(),
        basemap=basemap,
    )
    return mapas["resumo"]


def test_municipal_credita_conforme_a_fonte_real_de_cada_modo(monkeypatch):
    # BLK-BASEMAP-06: chegou o "se um dia" que o teste anterior antecipava. A fonte de rotulos
    # virou o proprio tileserver (estilo `ultra-labels`), entao no self-host o CARTO nao serve
    # nem o fundo nem o texto — creditar seria FALSO. No fallback (sem env) o fundo ainda e'
    # Voyager e o credito duplo continua devido.
    from motor_expansao.dashboard import relatorio_municipal as rm

    monkeypatch.delenv(rm._BASEMAP_TILES_URL_ENV, raising=False)
    assert rm._atribuicao_tiles() == "(c) OpenStreetMap, (c) CARTO"

    monkeypatch.setenv(
        rm._BASEMAP_TILES_URL_ENV,
        "http://motor_expansao_tileserver:8080/styles/ultra-maptiler/{z}/{x}/{y}@2x.png",
    )
    assert rm._atribuicao_tiles() == "(c) OpenStreetMap - OpenMapTiles"
    assert "CARTO" not in rm._atribuicao_tiles()

    # Os dois relatorios saem da MESMA caixa: o rodape do Municipal nao pode divergir do Pontual.
    from motor_expansao.dashboard import censo_map as cm

    assert rm._atribuicao_tiles() == cm._atribuicao_tiles()


def test_municipal_compoe_nomes_de_rua_por_cima_dos_hexes(monkeypatch):
    """O overlay de rotulos entra no PNG do mapa municipal (nomes sobre a cor dos hexes).

    Sentinela MAGENTA opaco: nenhuma camada do relatorio usa essa cor, entao encontra-la no PNG
    prova que o mosaico de `_fetch_labels` foi composto. Sem rede — `_fetch_basemap_municipio` e
    `_fetch_labels` sao ambos monkeypatchados.
    """
    from motor_expansao.dashboard import relatorio_municipal as rm

    magenta = (255, 0, 255)

    def _fake_basemap(bounds, _width):
        minx, miny, maxx, maxy = bounds
        return np.asarray(Image.new("RGB", (256, 256), (235, 235, 235))), (minx, maxx, miny, maxy)

    def _fake_labels(bounds, _width, **_kwargs):  # **_kwargs: aceita `zoom_bump=`
        minx, miny, maxx, maxy = bounds
        return Image.new("RGBA", (256, 256), (*magenta, 255)), (minx, maxx, miny, maxy)

    monkeypatch.setattr(rm, "_fetch_basemap_municipio", _fake_basemap)
    monkeypatch.setattr(rm, "_fetch_labels", _fake_labels)

    png = _mapa_resumo(basemap=True)
    arr = np.asarray(Image.open(BytesIO(png)).convert("RGB"))
    achou = ((arr[:, :, 0] == 255) & (arr[:, :, 1] == 0) & (arr[:, :, 2] == 255)).any()
    assert bool(achou), "os nomes de rua nao foram compostos no mapa municipal"


def test_municipal_sem_basemap_nao_busca_rotulos(monkeypatch):
    """Sem fundo de ruas nao ha o que rotular — e o fetch de rede nem chega a acontecer."""
    from motor_expansao.dashboard import relatorio_municipal as rm

    chamou = []
    monkeypatch.setattr(rm, "_fetch_labels", lambda *a, **k: chamou.append(1))

    _mapa_resumo(basemap=False)
    assert chamou == []


def test_municipal_tolera_falha_no_overlay_de_rotulos(monkeypatch):
    """Rotulo e' aditivo: `_fetch_labels` devolvendo None (rede fora) nao pode derrubar a pagina."""
    from motor_expansao.dashboard import relatorio_municipal as rm

    def _fake_basemap(bounds, _width):
        minx, miny, maxx, maxy = bounds
        return np.asarray(Image.new("RGB", (256, 256), (235, 235, 235))), (minx, maxx, miny, maxy)

    monkeypatch.setattr(rm, "_fetch_basemap_municipio", _fake_basemap)
    monkeypatch.setattr(rm, "_fetch_labels", lambda *a, **k: None)

    png = _mapa_resumo(basemap=True)
    assert Image.open(BytesIO(png)).size[0] > 0


# ---------------------------------------------------------------------------
# BLK-RELMUN-05 — recorte territorial dos pins (concorrentes fora do municipio)
# ---------------------------------------------------------------------------
# Bug relatado por Juan (2026-07-31): pedindo Sao Bernardo do Campo, o PDF trazia unidades de
# Santo Andre, Diadema e Sao Paulo. Causa: `_draw_pins` so testava a bbox da IMAGEM (municipio
# + padding de enquadramento), sem filtro territorial. A contagem ja filtrava por hex res-7,
# mas hex res-7 tem ~5 km2 e cruza divisa -> a faixa de fronteira entrava.


def _competidor_vizinho() -> pd.DataFrame:
    """Concorrente num hex que NAO e do municipio, mas perto o bastante p/ cair na bbox."""
    return pd.DataFrame(
        [{"rede": "bluefit", "lat": -23.62, "lng": -46.70, "hex_id_res7": _hex(-23.62, -46.70)}]
    )


def test_mapa_nao_desenha_concorrente_de_fora_do_municipio(monkeypatch):
    """REGRESSAO do bug: `_draw_pins` so pode receber linhas DO municipio.

    Captura os frames entregues a `_draw_pins` em vez de inspecionar pixels: o que se quer
    provar e o recorte, e ler pixel dependeria da geometria do enquadramento (que muda com o
    foco). `_sample_competitors()` tem 3 linhas, sendo 1 num hex distante; somamos um vizinho
    proximo, que e o caso que a bbox deixava passar e o hex nao.
    """
    from motor_expansao.dashboard import relatorio_municipal as rm

    recebidos: list[pd.DataFrame | None] = []

    def _spy(draw, image, frame, project, forced_key, minx, maxx, miny, maxy):
        recebidos.append(None if frame is None else frame.copy())

    monkeypatch.setattr(rm, "_draw_pins", _spy)

    df = _sample_df()
    comp = pd.concat([_sample_competitors(), _competidor_vizinho()], ignore_index=True)
    res = agregar_municipio(df, nome_municipio="SAO PAULO", competitors_df=comp)
    render_mapas_municipio(df, res, competitors_df=comp, ultra_df=_sample_ultra(), basemap=False)

    frames_conc = [f for f in recebidos if f is not None and "rede" in f.columns]
    assert frames_conc, "nenhuma chamada de _draw_pins com concorrentes"
    for frame in frames_conc:
        assert len(frame) == 2, f"vazou pin de fora do municipio: {len(frame)} linhas"
        assert set(frame["rede"]) == {"smart_fit", "bio_ritmo"}
        # O vizinho (bluefit) e o distante nao podem chegar ao desenho.
        assert "bluefit" not in set(frame["rede"])


def test_filtrar_pins_por_poligono_corta_a_faixa_de_fronteira():
    """Com poligono IBGE, um pin DENTRO de hex do municipio mas FORA da divisa e descartado.

    E o vazamento (b): o hex res-7 de `(-23.57, -46.65)` pertence ao municipio de teste, entao
    o filtro por hex aceita o pin; o poligono (que nao cobre esse canto) rejeita.
    """
    from shapely.geometry import box

    from motor_expansao.dashboard.relatorio_municipal import (
        _hexes_do_municipio,
        filtrar_pins_do_municipio,
    )

    df = _sample_df()
    hexes = _hexes_do_municipio(df)
    poligono = box(-46.645, -23.565, -46.615, -23.535)

    pins = pd.DataFrame(
        [
            {"rede": "smart_fit", "lat": -23.55, "lng": -46.63},   # dentro da divisa
            {"rede": "bluefit", "lat": -23.57, "lng": -46.65},     # hex do municipio, fora da divisa
        ]
    )

    # Sem poligono: o filtro por hex aceita os dois (o comportamento historico).
    so_hex = filtrar_pins_do_municipio(pins, hexes_muni=hexes)
    assert set(so_hex["rede"]) == {"smart_fit", "bluefit"}

    # Com poligono: so o que esta de fato dentro do municipio.
    com_poligono = filtrar_pins_do_municipio(pins, hexes_muni=hexes, poligono=poligono)
    assert set(com_poligono["rede"]) == {"smart_fit"}


def test_agregar_municipio_conta_pins_pelo_poligono_quando_disponivel():
    """A contagem do slide 8 tambem passa a respeitar a divisa quando ha poligono."""
    from shapely.geometry import box

    df = _sample_df()
    pins = pd.DataFrame(
        [
            {"rede": "smart_fit", "lat": -23.55, "lng": -46.63},
            {"rede": "bluefit", "lat": -23.57, "lng": -46.65},
        ]
    )

    sem = agregar_municipio(df, nome_municipio="SAO PAULO", competitors_df=pins)
    assert sem["n_concorrentes"] == 2

    com = agregar_municipio(
        df,
        nome_municipio="SAO PAULO",
        competitors_df=pins,
        poligono_municipio=box(-46.645, -23.565, -46.615, -23.535),
    )
    assert com["n_concorrentes"] == 1
    assert com["concorrentes_por_rede"] == {"smart_fit": 1}


def test_carregar_poligono_municipio_degrada_gracioso(tmp_path):
    """Sem `data/ibge` (caso do container Streamlit hoje) devolve None, sem levantar."""
    from motor_expansao.dashboard.relatorio_municipal import carregar_poligono_municipio

    assert carregar_poligono_municipio(None, "SP", "3548708") is None
    assert carregar_poligono_municipio(tmp_path, "SP", None) is None
    assert carregar_poligono_municipio(tmp_path, "SP", "3548708") is None  # dir sem geojson


def test_formatador_municipal_usa_texto_sem_dado_por_extenso():
    """A sigla "n/d" saiu do PDF (pedido de Juan, 2026-07-31)."""
    from motor_expansao.dashboard.constants import TEXTO_SEM_DADO
    from motor_expansao.dashboard.relatorio_municipal import _format_number

    assert _format_number(None) == TEXTO_SEM_DADO
    assert _format_number(float("nan")) == TEXTO_SEM_DADO
    assert TEXTO_SEM_DADO == "Não disponível"
    assert _format_number(1234.0) == "1.234"
