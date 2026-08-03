from __future__ import annotations

import pandas as pd
from pyproj import Transformer
from shapely.geometry import box
from shapely.ops import transform

from motor_expansao.dashboard.censo_map import render_mapas_censitarios_combinados
from motor_expansao.dashboard.censo_point import (
    CRS_ORIGEM_CENSO,
    METODO_RELATORIO_PONTUAL_CENSITARIO,
    RAIO_CENSITARIO_DEFAULT_KM,
    _local_metric_crs,
    analisar_ponto_censitario_setores,
)
from motor_expansao.dashboard.censo_report import (
    _CARD_NEUTRO_RGB,
    _CARD_VERDE_RGB,
    _CARD_VERMELHO_RGB,
    _META_DOMICILIOS_TOTAL_RAIO,
    _META_POP_TOTAL_RAIO,
    _META_RENDA_DOMICILIAR_TOTAL_RAIO,
    PDF_SECTION_HEADERS,
    _cor_consumo_concorrentes,
    _cor_por_meta,
    gerar_csv_setores_censitarios,
    gerar_payloads_download_relatorio_censitario,
    gerar_pdf_relatorio_pontual_censitario,
    gerar_pdf_relatorio_pontual_classico,
    render_downloads_relatorio_censitario,
)
from motor_expansao.dashboard.constants import RENDA_MEDIA_DOMICILIAR_BANDS, TEXTO_SEM_DADO

LAT_C = -23.55
LNG_C = -46.63


def _to_wgs_geometry(local_geom):
    transformer = Transformer.from_crs(_local_metric_crs(LAT_C, LNG_C), CRS_ORIGEM_CENSO, always_xy=True)
    return transform(transformer.transform, local_geom)


def _sector_record(cod_setor: str, local_geom, *, pop: float, renda: float, score: float):
    geom_wgs = _to_wgs_geometry(local_geom)
    minx, miny, maxx, maxy = geom_wgs.bounds
    return {
        "cod_setor": cod_setor,
        "uf": "SP",
        "cod_municipio": "3550308",
        "nome_municipio": "SAO PAULO",
        "area_setor_m2": float(local_geom.area),
        "geometry_wkb": geom_wgs.wkb,
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
            _sector_record("355030801000001", box(-700, -700, 0, 700), pop=800, renda=2100, score=64),
            _sector_record("355030801000002", box(0, -700, 700, 700), pop=1400, renda=2600, score=86),
        ]
    )
    competitors = pd.DataFrame(
        [{"nome_unidade": "Smart Fit Teste", "lat": LAT_C, "lng": LNG_C + 0.004, "rede": "smart_fit"}]
    )
    ultra = pd.DataFrame([{"nome_unidade": "Ultra Teste", "lat": LAT_C + 0.003, "lng": LNG_C}])
    result = analisar_ponto_censitario_setores(
        LAT_C,
        LNG_C,
        setores,
        competitors_df=competitors,
        ultra_df=ultra,
    )
    mapas = render_mapas_censitarios_combinados(
        LAT_C,
        LNG_C,
        setores,
        competitors_df=competitors,
        ultra_df=ultra,
        width=720,
        height=520,
        basemap=False,
    )
    return result, mapas


def test_export_csv_setores_censitarios_gera_bytes_utf8_sig_com_sep_ponto_virgula():
    result, _ = _sample_result()

    csv_bytes = gerar_csv_setores_censitarios(result)

    assert csv_bytes.startswith(b"\xef\xbb\xbf")
    text = csv_bytes.decode("utf-8-sig")
    assert "cod_setor;uf;cod_municipio" in text
    assert "355030801000001" in text
    assert "geometry_wkb" not in text


_RESIDUAL_OK = {
    "score_oportunidade_residual": 42.5,
    "oferta_efetiva_disponivel": 1200.0,
    "sam_fitness_potencial": 3000.0,
    "oferta_consumida_mercado_estimada": 1800.0,
}

# BLK-RELPON-07: dict sintetico no formato de `agregar_perfil_bairro_distrito`.
_PERFIL_BAIRRO_OK = {
    "unidade_tipo": "bairro",
    "unidade_nome": "Bairro Teste",
    "n_setores_unidade": 3,
    "populacao_total": 12345.0,
    "domicilios_total": 4321.0,
    "area_total_m2": 2_000_000.0,
    "densidade_hab_km2": 6172.5,
    "renda_media_domiciliar": 3210.55,
    "metodo_renda_perfil_bairro": "renda_responsavel_media_ponderada_por_domicilios",
    "flag_perfil_disponivel": True,
    "municipio_nome": "SAO PAULO",
    "uf": "SP",
}

# Strings de PII reais da lamina de contato do .pptx (image24) — NUNCA podem vazar no PDF.
_PII_FORBIDDEN = (
    b"vinicius",
    b"Vinicius",
    b"Vin\xedcius",
    b"96346-2974",
    b"@ultraacademia.com.br",
)


def test_export_pdf_executivo_gera_bytes_com_secoes_obrigatorias_e_mapa():
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(
        result, mapas, residual=_RESIDUAL_OK, ultra_dir="data/ultra"
    )

    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert len(pdf_bytes) > 15_000
    for header in PDF_SECTION_HEADERS:
        assert header.encode("latin-1") in pdf_bytes
    # BLK-RELPON-01 + -07 + -10 + -14: 7 paginas (capa, socioeconomia+residual, mapas de calor,
    # concorrentes, perfil do bairro/distrito, big numbers, credito); os choropleths censitarios
    # foram consolidados no slide unico "Mapas de calor" (grid 2x2) e a pagina "Imagem do
    # Entorno" (BLK-RELPON-11) saiu no BLK-RELPON-14 (8 -> 7).
    assert b"/Count 7" in pdf_bytes
    # 3 choropleths (densidade/renda/score) embutidos SEPARADAMENTE no slide unico + 1 pins
    # na pagina de Concorrentes = >= 4 imagens de mapa (nao pre-compostas).
    assert pdf_bytes.count(b"/Subtype /Image") >= 5
    # DEC-021: o rotulo acompanha o raio. Vindo da constante, o teste segue valido em
    # qualquer raio futuro e ainda prova que o metodo VAI para dentro do PDF.
    assert METODO_RELATORIO_PONTUAL_CENSITARIO.encode("latin-1") in pdf_bytes


def test_pdf_embute_quatro_choropleths_no_slide_unico():
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(result, mapas, ultra_dir="data/ultra")

    # Os 3 choropleths sao embutidos separadamente no slide "Mapas de calor" (+ pins) -> >= 4.
    assert pdf_bytes.count(b"/Subtype /Image") >= 5


def test_pdf_big_numbers_com_residual_e_nd():
    result, mapas = _sample_result()
    # BLK-RELPON-08: injeta o novo agregado do raio direto no result (os setores sinteticos de
    # `_sample_result` nao tem `domicilios_particulares_ocupados_setor_2022`, entao o motor deixa
    # o campo em None -- mais simples injetar aqui do que enriquecer os setores).
    result["domicilios_total_raio"] = 4200.0

    pdf_com = gerar_pdf_relatorio_pontual_censitario(result, mapas, residual=_RESIDUAL_OK)
    # Rotulos das 8 metricas presentes (4x2). NB: parenteses literais sao escapados (\( \)) no
    # stream PDF, entao verificamos o prefixo antes do "(alunos)"/"(est.)".
    for rotulo in (
        "População total no raio".encode("latin-1"),
        "Renda per capita média".encode("latin-1"),
        "Número de domicílios".encode("latin-1"),
        "Renda média domiciliar".encode("latin-1"),
        b"SAM Fitness",
        b"Residual Fitness",
        b"Concorrentes no raio",
        b"Consumo concorrentes",
    ):
        assert rotulo in pdf_com
    # Score censitario medio REMOVIDO do PDF em 2026-07-17 (fica so em result/CSV) -> grade 4x2.
    assert "Score censitário médio".encode("latin-1") not in pdf_com
    # BLK-RELPON-08: o card "Score censitario maximo" foi REMOVIDO do PDF (fica so em result/CSV).
    assert "Score censitário máximo".encode("latin-1") not in pdf_com
    # BLK-RELPON-08: numero de domicilios do raio formatado com 0 casas.
    assert b"4.200" in pdf_com
    # SAM e Residual Fitness saem em ALUNOS (numero), nao score: sam=3000, residual=1200, consumo=1800.
    assert b"3.000" in pdf_com
    assert b"1.200" in pdf_com
    assert b"1.800" in pdf_com

    # Sem residual -> `TEXTO_SEM_DADO` auditavel (era a sigla "n/d" ate 2026-07-31).
    pdf_sem = gerar_pdf_relatorio_pontual_censitario(result, mapas, residual=None)
    assert TEXTO_SEM_DADO.encode("latin-1") in pdf_sem


def test_pdf_big_numbers_ordem_linha_1():
    """A linha 1 do grid 4x2 segue Populacao -> Renda per capita -> Domicilios -> Renda domiciliar.

    Com `set_compression(False)`, o texto e cru no content stream e a ordem de aparicao dos
    rotulos reflete a ordem de desenho dos cards.
    """
    result, mapas = _sample_result()
    result["domicilios_total_raio"] = 4200.0

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(result, mapas, residual=_RESIDUAL_OK)

    pos_pop = pdf_bytes.index("População total no raio".encode("latin-1"))
    pos_renda = pdf_bytes.index("Renda per capita média".encode("latin-1"))
    pos_dom = pdf_bytes.index("Número de domicílios".encode("latin-1"))
    pos_renda_dom = pdf_bytes.index("Renda média domiciliar".encode("latin-1"))

    assert pos_pop < pos_renda < pos_dom < pos_renda_dom


def test_map_grid_cells_packed_proporcao_empacotado_sem_sobreposicao():
    """Mapas de calor: celulas com a proporcao do mapa, empacotadas (sem vao branco) e iguais."""
    from motor_expansao.dashboard.censo_report import _map_grid_cells_packed

    aspect = 1000.0 / 760.0
    cells = _map_grid_cells_packed(aspect, top=58.0, bottom=540.0 - 22.0, gap=10.0)
    assert len(cells) == 4
    for _x, _y, w, h in cells:
        assert abs(w / h - aspect) < 0.02  # proporcao do mapa (retangular)
    (x0, _y0, w0, h0), (x1, _y1, w1, h1) = cells[0], cells[1]
    assert (w0, h0) == (w1, h1)  # grid uniforme
    assert abs((x1 - (x0 + w0)) - 10.0) < 1e-6  # colado: so o gap de 10 entre colunas


def test_map_grid_cells_packed_scale_encolhe_e_mantem_centrado():
    """BLK-RELPON-13: `scale` encolhe as celulas do slide-hero e mantem o grid centrado.

    Trava a MECANICA (scale=1.0 -> geometria IDENTICA; scale<1.0 -> menor, mesma proporcao,
    mesmo centro), NAO o valor de `_HERO_MAP_SCALE`, que e' calibravel no gate visual.
    """
    from motor_expansao.dashboard.censo_report import _PAGE_W, _map_grid_cells_packed

    aspect = 1000.0 / 760.0
    kw = {"top": 58.0, "bottom": 518.0, "gap": 10.0, "cols": 2, "rows": 1}
    base = _map_grid_cells_packed(aspect, **kw)
    assert _map_grid_cells_packed(aspect, scale=1.0, **kw) == base  # default preserva

    menor = _map_grid_cells_packed(aspect, scale=0.8, **kw)
    assert len(menor) == len(base)
    for i in range(len(base)):
        _xb, _yb, wb, hb = base[i]
        _xm, _ym, wm, hm = menor[i]
        assert wm < wb and hm < hb  # encolheu nas duas dimensoes
        assert abs(wm / hm - wb / hb) < 1e-6  # proporcao do mapa preservada

    def _centro(cells):
        xs = [c[0] for c in cells] + [c[0] + c[2] for c in cells]
        ys = [c[1] for c in cells] + [c[1] + c[3] for c in cells]
        return (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0

    cx_base, cy_base = _centro(base)
    cx_menor, cy_menor = _centro(menor)
    assert abs(cx_base - cx_menor) < 1e-6  # segue centrado na horizontal
    assert abs(cy_base - cy_menor) < 1e-6  # e na vertical
    assert abs(cx_base - _PAGE_W / 2.0) < 1e-6  # centrado na pagina


def test_cor_por_meta_verde_vermelho_neutro():
    """BLK-RELPON-08 (D3/Q2): helper puro de cor por meta simples (>= meta -> verde)."""
    # DEC-021: os valores de prova derivam da META, nao de literais. Com a meta reescalada
    # de 10.000 para 4.444 (area de 1,5 -> 1,0 km), o antigo literal 5_000 virou APROVADO e o
    # teste passou a afirmar o contrario do que queria — deixando de cobrir o caso vermelho.
    assert _cor_por_meta(_META_POP_TOTAL_RAIO * 1.2, _META_POP_TOTAL_RAIO) == _CARD_VERDE_RGB
    assert _cor_por_meta(_META_POP_TOTAL_RAIO, _META_POP_TOTAL_RAIO) == _CARD_VERDE_RGB  # inclusiva
    assert _cor_por_meta(_META_POP_TOTAL_RAIO * 0.5, _META_POP_TOTAL_RAIO) == _CARD_VERMELHO_RGB
    assert _cor_por_meta(None, _META_POP_TOTAL_RAIO) == _CARD_NEUTRO_RGB
    assert _cor_por_meta(float("nan"), _META_POP_TOTAL_RAIO) == _CARD_NEUTRO_RGB
    # domicilios_total_raio / _META_DOMICILIOS_TOTAL_RAIO (3000) -- campo NOVO.
    # Mesma razao do bloco de populacao: derivar da meta em vez de fixar 3.500/3.000/2.999,
    # que foram escolhidos contra a meta de 1,5 km (DEC-021 reescalou para 1.333).
    assert _cor_por_meta(_META_DOMICILIOS_TOTAL_RAIO * 1.17, _META_DOMICILIOS_TOTAL_RAIO) == _CARD_VERDE_RGB
    assert _cor_por_meta(_META_DOMICILIOS_TOTAL_RAIO, _META_DOMICILIOS_TOTAL_RAIO) == _CARD_VERDE_RGB  # inclusiva
    assert _cor_por_meta(_META_DOMICILIOS_TOTAL_RAIO - 1, _META_DOMICILIOS_TOTAL_RAIO) == _CARD_VERMELHO_RGB
    assert _cor_por_meta(None, _META_DOMICILIOS_TOTAL_RAIO) == _CARD_NEUTRO_RGB
    assert _cor_por_meta(float("nan"), _META_DOMICILIOS_TOTAL_RAIO) == _CARD_NEUTRO_RGB


def test_renda_media_domiciliar_fica_verde_a_partir_de_4000():
    """Gate visual BLK-RELPON-13 (Vinicius, 2026-07-24): meta baixada de 6.200 para 4.000.

    Trava a REGRA pedida ("verde a partir de 4000") no valor de fronteira, nao so no simbolo:
    4.000 e' verde (inclusiva), 3.999 e' vermelho. Cobre a faixa 4.000-6.199, que ANTES do
    gate saia vermelha.
    """
    assert _META_RENDA_DOMICILIAR_TOTAL_RAIO == 4_000.0  # a meta pedida no gate
    assert _cor_por_meta(4_000, _META_RENDA_DOMICILIAR_TOTAL_RAIO) == _CARD_VERDE_RGB  # inclusiva
    assert _cor_por_meta(3_999, _META_RENDA_DOMICILIAR_TOTAL_RAIO) == _CARD_VERMELHO_RGB
    assert _cor_por_meta(5_000, _META_RENDA_DOMICILIAR_TOTAL_RAIO) == _CARD_VERDE_RGB  # era vermelho
    assert _cor_por_meta(None, _META_RENDA_DOMICILIAR_TOTAL_RAIO) == _CARD_NEUTRO_RGB
    assert _cor_por_meta(float("nan"), _META_RENDA_DOMICILIAR_TOTAL_RAIO) == _CARD_NEUTRO_RGB


def test_meta_renda_domiciliar_corta_em_4000():
    """Regressao de producao (bot do Telegram, relato de Felipe 2026-07-24): o card
    "Renda media domiciliar" saia VERMELHO com renda acima de R$ 4.000 porque a meta
    da `main` ainda era 6.200 (o corte 4.000 pedido em 2026-07-23 so existia no piloto).
    Trava o valor E o comportamento nas duas bordas da faixa 4.000-6.200."""
    assert _META_RENDA_DOMICILIAR_TOTAL_RAIO == 4_000.0
    # A faixa que estava errada: >= 4.000 e < 6.200 tem de sair VERDE.
    assert _cor_por_meta(4_000.0, _META_RENDA_DOMICILIAR_TOTAL_RAIO) == _CARD_VERDE_RGB  # inclusiva
    assert _cor_por_meta(4_532.10, _META_RENDA_DOMICILIAR_TOTAL_RAIO) == _CARD_VERDE_RGB
    assert _cor_por_meta(6_199.0, _META_RENDA_DOMICILIAR_TOTAL_RAIO) == _CARD_VERDE_RGB
    # Abaixo do corte segue vermelho; sem dado segue neutro (nunca falsa reprovacao).
    assert _cor_por_meta(3_999.0, _META_RENDA_DOMICILIAR_TOTAL_RAIO) == _CARD_VERMELHO_RGB
    assert _cor_por_meta(None, _META_RENDA_DOMICILIAR_TOTAL_RAIO) == _CARD_NEUTRO_RGB


def test_bands_renda_domiciliar_cortam_em_4000():
    """A regua do choropleth acompanha a meta: 2.000 / 4.000 / 8.000 / 14.000 (Felipe
    2026-07-23). Rotulos SEM acento (o font do PNG da legenda nao renderiza 'a')."""
    limites = [limite for limite, _rotulo, _rgba in RENDA_MEDIA_DOMICILIAR_BANDS]
    assert limites == [2_000.0, 4_000.0, 8_000.0, 14_000.0, float("inf")]
    rotulos = [rotulo for _limite, rotulo, _rgba in RENDA_MEDIA_DOMICILIAR_BANDS]
    assert rotulos[1] == "R$ 2.001-4.000"
    assert rotulos[2] == "R$ 4.001-8.000"
    assert all("á" not in r for r in rotulos)


def test_cor_consumo_concorrentes_regra_assimetrica():
    """BLK-RELPON-08 (D3): vermelho SO quando SAM>=2000 E Residual<2000; espelhado no card Concorrentes."""
    # (a) mercado consumido: SAM alto E Residual baixo -> vermelho.
    assert _cor_consumo_concorrentes(3_000, 1_200) == _CARD_VERMELHO_RGB
    # (b) SAM alto E Residual alto -> verde.
    assert _cor_consumo_concorrentes(3_000, 2_500) == _CARD_VERDE_RGB
    # (c) SAM baixo (independente do Residual) -> verde.
    assert _cor_consumo_concorrentes(1_500, 500) == _CARD_VERDE_RGB
    assert _cor_consumo_concorrentes(1_500, 5_000) == _CARD_VERDE_RGB
    # (d) sem dado em SAM OU Residual (isoladamente) -> neutro.
    assert _cor_consumo_concorrentes(None, 1_200) == _CARD_NEUTRO_RGB
    assert _cor_consumo_concorrentes(3_000, None) == _CARD_NEUTRO_RGB
    assert _cor_consumo_concorrentes(float("nan"), 1_200) == _CARD_NEUTRO_RGB
    assert _cor_consumo_concorrentes(3_000, float("nan")) == _CARD_NEUTRO_RGB


def test_pdf_offline_safe_sem_assets(tmp_path):
    """Sem os assets de branding -> PDF valido com fundo solido, sem excecao."""
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(
        result, mapas, residual=_RESIDUAL_OK, ultra_dir=tmp_path
    )

    assert pdf_bytes.startswith(b"%PDF")
    assert b"/Count 7" in pdf_bytes
    for header in PDF_SECTION_HEADERS:
        assert header.encode("latin-1") in pdf_bytes


def test_pdf_sem_pii_de_pessoas():
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(
        result, mapas, residual=_RESIDUAL_OK, ultra_dir="data/ultra"
    )

    for needle in _PII_FORBIDDEN:
        assert needle not in pdf_bytes


def test_pdf_marca_dagua_com_solicitante():
    """Com solicitante -> marca d'agua "Ultra Academia | {solicitante}" embutida (stream OFF)."""
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(
        result, mapas, residual=_RESIDUAL_OK, solicitante="Analista Teste"
    )

    assert b"Ultra Academia" in pdf_bytes
    assert b"Analista Teste" in pdf_bytes
    # 7 paginas preservadas e choropleths intactos (marca d'agua nao cria paginas).
    assert b"/Count 7" in pdf_bytes
    assert pdf_bytes.count(b"/Subtype /Image") >= 5


def test_pdf_marca_dagua_sem_solicitante():
    """Sem solicitante (None) -> so "Ultra Academia"; default seguro sem nome (anti-PII)."""
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(
        result, mapas, residual=_RESIDUAL_OK, solicitante=None
    )

    assert b"Ultra Academia" in pdf_bytes
    assert b"Analista Teste" not in pdf_bytes
    assert b"/Count 7" in pdf_bytes
    assert pdf_bytes.count(b"/Subtype /Image") >= 5


def test_pdf_marca_dagua_em_todas_as_paginas():
    """BLK-RELPON-01 + -07 + -10 + -14: marca d'agua "Ultra Academia" em TODAS as 7 paginas ->
    >= 7x nos bytes crus."""
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(
        result, mapas, residual=_RESIDUAL_OK, solicitante="Analista Teste"
    )

    # Uma ocorrencia da marca d'agua por pagina (7) -> contagem minima verificavel >= 7.
    assert pdf_bytes.count(b"Ultra Academia") >= 7


def test_pdf_atribuicao_de_tiles_no_rodape():
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(result, mapas)

    assert b"OpenStreetMap" in pdf_bytes
    assert b"CARTO" in pdf_bytes


def test_pdf_footer_cita_voyager():
    # Atribuicao de tiles segue valida no PDF (rodape do credit_page). O nome do provedor
    # "Voyager" vive no PNG do mapa (embutido como imagem, nao texto raw), entao verificamos
    # o provedor na constante do modulo de mapa (base CLARA Voyager, BLK-CENSO-03).
    result, mapas = _sample_result()
    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(result, mapas)
    assert b"OpenStreetMap" in pdf_bytes
    assert b"CARTO" in pdf_bytes
    import motor_expansao.dashboard.censo_map as m

    assert m._BASEMAP_PROVIDER_ATTR == "Voyager"


def test_pdf_retrocompat_aceita_bytes_unico_legado():
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(result, mapas["densidade"])

    assert pdf_bytes.startswith(b"%PDF-1.4")
    # Bytes unico legado -> so a camada de densidade recebe mapa; renda/score caem no fallback.
    # O slide unico "Mapas de calor" existe e as 2 celulas sem PNG mostram a mensagem de fallback.
    assert b"Mapas de calor" in pdf_bytes
    assert "Mapa indisponível para esta camada.".encode("latin-1") in pdf_bytes
    # Estrutura de 7 paginas preservada.
    assert b"/Count 7" in pdf_bytes


def test_pdf_estrutura_inalterada_com_faixa_valor_ponto_blk_relpon_05():
    """BLK-RELPON-05: a faixa "<variavel> no ponto" nos PNGs de mapa e assada no PNG (Pillow),
    sem tocar o fluxo fpdf2 -- estrutura de paginas/imagens/headers do PDF permanece
    IDENTICA (regressao leve de estrutura)."""
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(
        result, mapas, residual=_RESIDUAL_OK, ultra_dir="data/ultra"
    )

    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert b"/Count 7" in pdf_bytes
    assert pdf_bytes.count(b"/Subtype /Image") >= 5
    for header in PDF_SECTION_HEADERS:
        assert header.encode("latin-1") in pdf_bytes
    # DEC-021: o rotulo acompanha o raio. Vindo da constante, o teste segue valido em
    # qualquer raio futuro e ainda prova que o metodo VAI para dentro do PDF.
    assert METODO_RELATORIO_PONTUAL_CENSITARIO.encode("latin-1") in pdf_bytes


def test_pdf_concorrentes_contagem_total_e_mais_n_quando_excede_10():
    """>10 redes no raio -> cabecalho com '(N no total)' + caption "Concorrentes: ...".

    Sem PII: os nomes vem da coluna de UNIDADE (`rede`/`nome_unidade`), nunca de pessoa.
    """
    setores = pd.DataFrame(
        [
            _sector_record("355030801000001", box(-700, -700, 0, 700), pop=800, renda=2100, score=64),
            _sector_record("355030801000002", box(0, -700, 700, 700), pop=1400, renda=2600, score=86),
        ]
    )
    # 12 concorrentes + 1 Ultra = 13 redes (>10) bem dentro do raio de 1.5 km.
    competitors = pd.DataFrame(
        [
            {
                "nome_unidade": f"Rede Teste {i}",
                "lat": LAT_C + 0.0001 * i,
                "lng": LNG_C + 0.0001 * i,
                "rede": f"rede_{i}",
            }
            for i in range(12)
        ]
    )
    ultra = pd.DataFrame([{"nome_unidade": "Ultra Teste", "lat": LAT_C + 0.0002, "lng": LNG_C}])
    result = analisar_ponto_censitario_setores(
        LAT_C, LNG_C, setores, competitors_df=competitors, ultra_df=ultra
    )
    mapas = render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores, competitors_df=competitors, ultra_df=ultra,
        width=720, height=520, basemap=False,
    )

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(result, mapas, residual=_RESIDUAL_OK)

    total = len(result["concorrentes_raio"]) + len(result["ultra_raio"])
    assert total > 10
    # Slide Concorrentes (pedido Felipe 2026-07-23): mapa centralizado + faixa inferior
    # com as redes no raio (caption). >10 redes -> cabecalho com "(N no total)".
    # NB: parenteses literais sao escapados (\( \)) no stream PDF -> verifica o miolo " no total".
    assert f"{total} no total".encode("latin-1") in pdf_bytes
    # A caption lista os concorrentes (deduplicados por rede, sem PII).
    assert b"Concorrentes:" in pdf_bytes
    # Contrato preservado.
    assert b"/Count 7" in pdf_bytes
    for needle in _PII_FORBIDDEN:
        assert needle not in pdf_bytes


def test_pdf_concorrentes_sem_contagem_quando_ate_10():
    """D4=B: <=10 redes -> cabecalho simples, sem sufixo de total nem '... e mais'."""
    result, mapas = _sample_result()  # 1 concorrente + 1 Ultra = 2 redes
    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(result, mapas, residual=_RESIDUAL_OK)

    raio_txt = f"{RAIO_CENSITARIO_DEFAULT_KM:.1f}".replace(".", ",")
    assert f"Redes no raio de {raio_txt} km".encode("latin-1") in pdf_bytes
    assert b"no total" not in pdf_bytes
    assert b"... e mais" not in pdf_bytes


def test_payloads_e_helper_streamlit_expoem_downloads_csv_pdf():
    result, mapas = _sample_result()

    payloads = gerar_payloads_download_relatorio_censitario(
        result,
        mapas,
        filename_prefix="teste_relatorio",
        residual=_RESIDUAL_OK,
    )

    assert payloads.csv_filename == "teste_relatorio_setores.csv"
    assert payloads.pdf_filename == "teste_relatorio.pdf"
    assert payloads.csv_bytes
    assert payloads.pdf_bytes.startswith(b"%PDF")

    class DummyStreamlit:
        def __init__(self):
            self.calls = []

        def download_button(self, label, *, data, file_name, mime):
            self.calls.append(
                {"label": label, "data": data, "file_name": file_name, "mime": mime}
            )

    dummy = DummyStreamlit()
    rendered = render_downloads_relatorio_censitario(
        dummy,
        result,
        mapas,
        filename_prefix="teste_relatorio",
    )

    assert rendered.pdf_bytes.startswith(b"%PDF")
    assert [call["mime"] for call in dummy.calls] == ["text/csv", "application/pdf"]
    assert [call["file_name"] for call in dummy.calls] == [
        "teste_relatorio_setores.csv",
        "teste_relatorio.pdf",
    ]


# ---------------------------------------------------------------------------
# BLK-EST-05 — variante "Apresentacao Classica Ultra"
# ---------------------------------------------------------------------------


def test_classico_gera_7_paginas_e_secoes():
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        result, mapas, residual=_RESIDUAL_OK, ultra_dir="data/ultra"
    )

    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert b"/Count 7" in pdf_bytes
    for header in PDF_SECTION_HEADERS:
        assert header.encode("latin-1") in pdf_bytes
    # 3 choropleths embutidos separadamente no slide "Mapas de calor" + 1 pins = >= 4 imagens.
    assert pdf_bytes.count(b"/Subtype /Image") >= 5


def test_classico_link_clicavel_na_realizacao():
    result, mapas = _sample_result()

    # Com endereco real -> a query do link e o proprio endereco.
    pdf_com_end = gerar_pdf_relatorio_pontual_classico(
        result, mapas, residual=_RESIDUAL_OK, rotulo="Av Teste, 100"
    )
    assert b"https://www.google.com/maps/search/" in pdf_com_end
    assert "Link para localização do ponto:".encode("latin-1") in pdf_com_end
    assert b"Av%20Teste" in pdf_com_end or b"Av Teste" in pdf_com_end

    # Sem rotulo -> a query cai na coordenada do result.
    pdf_sem_end = gerar_pdf_relatorio_pontual_classico(result, mapas, residual=_RESIDUAL_OK)
    assert b"https://www.google.com/maps/search/" in pdf_sem_end


def test_classico_offline_safe_sem_assets(tmp_path):
    """Sem qualquer asset (incl. icone_ultra.png) -> PDF valido, sem excecao."""
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        result, mapas, residual=_RESIDUAL_OK, ultra_dir=tmp_path
    )

    assert pdf_bytes.startswith(b"%PDF")
    assert b"/Count 7" in pdf_bytes
    for header in PDF_SECTION_HEADERS:
        assert header.encode("latin-1") in pdf_bytes


def test_classico_sem_pii_de_pessoas():
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        result, mapas, residual=_RESIDUAL_OK, ultra_dir="data/ultra"
    )

    for needle in _PII_FORBIDDEN:
        assert needle not in pdf_bytes


def test_classico_marca_dagua_solicitante():
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        result, mapas, residual=_RESIDUAL_OK, solicitante="Analista Teste"
    )

    assert b"Ultra Academia | Analista Teste" in pdf_bytes
    assert pdf_bytes.count(b"Ultra Academia") >= 6


def test_geracoes_repetidas_sao_deterministas():
    """Gerar o classico entre duas geracoes nao altera os bytes (isolamento entre chamadas).

    BLK-RELPON-14: com o gerador unificado o "recente" e' wrapper do classico, entao este teste
    passou a travar o DETERMINISMO da geracao (nenhum estado de modulo vaza de uma chamada para
    a seguinte), nao mais o isolamento entre dois templates distintos.
    """
    result, mapas = _sample_result()

    antes = gerar_pdf_relatorio_pontual_censitario(
        result, mapas, residual=_RESIDUAL_OK, ultra_dir="data/ultra"
    )
    _ = gerar_pdf_relatorio_pontual_classico(
        result, mapas, residual=_RESIDUAL_OK, ultra_dir="data/ultra"
    )
    depois = gerar_pdf_relatorio_pontual_censitario(
        result, mapas, residual=_RESIDUAL_OK, ultra_dir="data/ultra"
    )

    assert antes == depois


def test_downloads_os_dois_ramos_de_template_produzem_o_mesmo_pdf():
    """BLK-RELPON-14: unificado o gerador, `template="classico"` e o default produzem o MESMO PDF.

    O ramo `else` continua passando pelo simbolo legado `gerar_pdf_relatorio_pontual_censitario`
    (hoje wrapper depreciado) para nao quebrar quem faz spy/patch nesse nome — mas o resultado
    e' byte-a-byte igual, com a estetica classica (banda magenta de rodape + link clicavel).
    """
    result, mapas = _sample_result()

    p_classico = gerar_payloads_download_relatorio_censitario(
        result, mapas, filename_prefix="t", residual=_RESIDUAL_OK, template="classico"
    )
    p_default = gerar_payloads_download_relatorio_censitario(
        result, mapas, filename_prefix="t", residual=_RESIDUAL_OK
    )

    assert p_classico.pdf_bytes.startswith(b"%PDF")
    assert p_default.pdf_bytes.startswith(b"%PDF")
    assert p_classico.pdf_bytes == p_default.pdf_bytes
    for pdf_bytes in (p_classico.pdf_bytes, p_default.pdf_bytes):
        assert "Link para localização do ponto:".encode("latin-1") in pdf_bytes


# ---------------------------------------------------------------------------
# BLK-RELPON-01 — slide unico consolidado "Mapas de calor" (3 choropleths lado a lado)
# ---------------------------------------------------------------------------


def _boxes_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    """True se dois bounding boxes (x, y, w, h) tem interseccao de area positiva."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def test_slide_unico_quatro_mapas_sem_sobreposicao():
    """As 4 celulas do grid 2x2 nao se sobrepoem e estao contidas na area de conteudo.

    Variante recente (top=60, bottom=_PAGE_H-26, margin_x=20) e classica (top ~122).
    """
    from motor_expansao.dashboard.censo_report import (
        _CLASSICO_MAPS_TOP,
        _CLASSICO_MARGIN,
        _PAGE_H,
        _PAGE_W,
        _map_grid_cells,
    )

    # Recente.
    top, bottom, margin_x, gap = 60.0, _PAGE_H - 26.0, 20.0, 12.0
    cells = _map_grid_cells(top, bottom, margin_x, gap)
    assert len(cells) == 4
    for i in range(4):
        x, y, w, h = cells[i]
        assert x >= margin_x - 1e-6
        assert x + w <= _PAGE_W - margin_x + 1e-6
        assert y >= top - 1e-6
        assert y + h <= bottom + 1e-6
        for j in range(i + 1, 4):
            assert not _boxes_overlap(cells[i], cells[j])

    # Classico (topo mais baixo por causa da banda + titulo de secao).
    top_c, bottom_c, margin_c = _CLASSICO_MAPS_TOP, _PAGE_H - 26.0, _CLASSICO_MARGIN
    cells_c = _map_grid_cells(top_c, bottom_c, margin_c, 12.0)
    assert len(cells_c) == 4
    assert top_c >= 100.0  # abaixo da banda classica + titulo de secao
    for i in range(4):
        x, y, w, h = cells_c[i]
        assert x >= margin_c - 1e-6
        assert x + w <= _PAGE_W - margin_c + 1e-6
        assert y >= top_c - 1e-6
        assert y + h <= bottom_c + 1e-6
        for j in range(i + 1, 4):
            assert not _boxes_overlap(cells_c[i], cells_c[j])


def test_slide_unico_count_7_e_titulo_mapas_de_calor():
    """As duas variantes tem 7 paginas e o titulo de faixa "Mapas de calor" no slide unico.

    (Historico do nome: era `..._count_5_...` e ja asseria 6 — passou a 7 com o slide-hero
    "Socioeconomia e Residual Fitness", subiu a 8 com a "Imagem do Entorno" do BLK-RELPON-11 e
    VOLTOU a 7 no BLK-RELPON-14, que removeu essa pagina.)
    """
    result, mapas = _sample_result()

    pdf_recente = gerar_pdf_relatorio_pontual_censitario(result, mapas, residual=_RESIDUAL_OK)
    assert b"/Count 7" in pdf_recente
    assert b"Mapas de calor" in pdf_recente

    pdf_classico = gerar_pdf_relatorio_pontual_classico(result, mapas, residual=_RESIDUAL_OK)
    assert b"/Count 7" in pdf_classico
    assert b"Mapas de calor" in pdf_classico


def test_slide_unico_offline_safe_por_camada():
    """Camada ausente no slide unico -> gera sem excecao, com fallback textual; /Count 7 preservado."""
    result, mapas = _sample_result()
    # So densidade + concorrentes; renda e score AUSENTES -> fallback nas 2 celulas.
    mapas_parciais = {"densidade": mapas["densidade"], "concorrentes": mapas["concorrentes"]}

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(
        result, mapas_parciais, residual=_RESIDUAL_OK
    )

    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert b"/Count 7" in pdf_bytes
    assert b"Mapas de calor" in pdf_bytes
    assert "Mapa indisponível para esta camada.".encode("latin-1") in pdf_bytes


def test_slide_unico_quatro_imagens_embutidas():
    """Os 4 choropleths do grid 2x2 sao embutidos SEPARADAMENTE (nao pre-compostos).

    Piso de `>= 5` imagens: os 4 do grid + a de Concorrentes. E piso, nao igualdade, porque a
    pagina "Socioeconomia e Residual Fitness" soma mais imagens quando as camadas de hexagono
    estao presentes; travar em igualdade quebraria a cada camada nova.
    """
    result, mapas = _sample_result()

    pdf_recente = gerar_pdf_relatorio_pontual_censitario(result, mapas, residual=_RESIDUAL_OK)
    assert pdf_recente.count(b"/Subtype /Image") >= 5

    pdf_classico = gerar_pdf_relatorio_pontual_classico(result, mapas, residual=_RESIDUAL_OK)
    assert pdf_classico.count(b"/Subtype /Image") >= 5


# ---------------------------------------------------------------------------
# BLK-RELPON-07 — pagina "Perfil do Bairro/Distrito" (entre Concorrentes e Big Numbers)
# ---------------------------------------------------------------------------


def test_perfil_bairro_page_presente_com_4_metricas_recente():
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(
        result, mapas, perfil_bairro=_PERFIL_BAIRRO_OK, residual=_RESIDUAL_OK
    )

    for rotulo in (
        "População".encode("latin-1"),
        "Densidade demográfica".encode("latin-1"),
        "Domicílios".encode("latin-1"),
        "Renda média".encode("latin-1"),
    ):
        assert rotulo in pdf_bytes
    assert "Bairro Teste".encode("latin-1") in pdf_bytes
    assert "Perfil do Bairro/Distrito".encode("latin-1") in pdf_bytes
    assert b"/Count 7" in pdf_bytes


def test_perfil_bairro_page_nd_quando_perfil_bairro_none():
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(result, mapas, residual=_RESIDUAL_OK)

    assert b"/Count 7" in pdf_bytes
    assert "Perfil do Bairro/Distrito".encode("latin-1") in pdf_bytes
    assert "Perfil não disponível".encode("latin-1") in pdf_bytes


def test_classico_perfil_bairro_page_presente_e_nd():
    result, mapas = _sample_result()

    pdf_com = gerar_pdf_relatorio_pontual_classico(
        result, mapas, perfil_bairro=_PERFIL_BAIRRO_OK, residual=_RESIDUAL_OK
    )
    assert "Bairro Teste".encode("latin-1") in pdf_com
    assert "Perfil do Bairro/Distrito".encode("latin-1") in pdf_com
    assert b"/Count 7" in pdf_com

    pdf_sem = gerar_pdf_relatorio_pontual_classico(result, mapas, residual=_RESIDUAL_OK)
    assert "Perfil não disponível".encode("latin-1") in pdf_sem
    assert b"/Count 7" in pdf_sem


# ---------------------------------------------------------------------------
# BLK-RELPON-10 — slide-hero "Socioeconomia e Residual Fitness" (antes de "Mapas de calor")
# ---------------------------------------------------------------------------


def test_tema_bicolor_ordinal_zero_e_magenta_sem_mexer_nos_existentes():
    """DT-4: o slide novo e o ordinal 0 -> magenta, SEM alterar p1..p4 (zero cascata)."""
    from motor_expansao.dashboard.censo_report import (
        ULTRA_MAGENTA,
        ULTRA_TURQUESA,
        _tema_bicolor,
    )

    assert _tema_bicolor(0) == (ULTRA_MAGENTA, ULTRA_TURQUESA)
    assert _tema_bicolor(1) == (ULTRA_TURQUESA, ULTRA_MAGENTA)
    assert _tema_bicolor(2) == (ULTRA_MAGENTA, ULTRA_TURQUESA)
    assert _tema_bicolor(3) == (ULTRA_TURQUESA, ULTRA_MAGENTA)
    assert _tema_bicolor(4) == (ULTRA_MAGENTA, ULTRA_TURQUESA)


def _spy_titulos(monkeypatch, modulo, nome_funcao, alvo: list):
    real = getattr(modulo, nome_funcao)

    def _spy(pdf, *args, **kwargs):
        # `_draw_title_band(pdf, title, *, rgb=...)`;
        # `_classico_title_band(pdf, banda_texto, titulo_secao, assets, *, rgb=...)`.
        titulo = args[0] if nome_funcao == "_draw_title_band" else args[1]
        alvo.append((titulo, kwargs.get("rgb")))
        return real(pdf, *args, **kwargs)

    monkeypatch.setattr(modulo, nome_funcao, _spy)


def test_sequencia_de_titulo_e_cor_das_5_paginas_de_conteudo_nas_2_variantes(monkeypatch):
    """DT-4 travado por teste: a ordem/cor das paginas de conteudo nas DUAS variantes.

    Socioeconomia e Residual Fitness=magenta -> Mapas de calor=turquesa ->
    Concorrentes=magenta -> Perfil=turquesa -> Big Numbers=magenta. BLK-RELPON-14: a pagina
    "Imagem do Entorno" (ordinal -1) saiu; como os ordinais sao ABSOLUTOS, as paginas que
    ficaram mantem EXATAMENTE a cor que ja tinham (zero cascata).
    """
    import motor_expansao.dashboard.censo_report as cr

    result, mapas = _sample_result()

    recente: list = []
    _spy_titulos(monkeypatch, cr, "_draw_title_band", recente)
    cr.gerar_pdf_relatorio_pontual_censitario(result, mapas, residual=_RESIDUAL_OK)
    # BLK-RELPON-14: o "recente" e' wrapper do classico -> a banda CLASSICA cobre as 4
    # primeiras paginas de conteudo e o Big Numbers reusa `_draw_title_band`.
    assert recente == [("Big Numbers", cr.ULTRA_MAGENTA)]

    classico: list = []
    _spy_titulos(monkeypatch, cr, "_classico_title_band", classico)
    cr.gerar_pdf_relatorio_pontual_classico(result, mapas, residual=_RESIDUAL_OK)
    assert classico == [
        ("Socioeconomia e Residual Fitness", cr.ULTRA_MAGENTA),
        ("Mapas de calor", cr.ULTRA_TURQUESA),
        ("Concorrentes", cr.ULTRA_MAGENTA),
        ("Perfil do Bairro/Distrito", cr.ULTRA_TURQUESA),
    ]


def test_slide_hero_presente_nas_2_variantes_com_7_paginas():
    result, mapas = _sample_result()

    for gerar in (gerar_pdf_relatorio_pontual_censitario, gerar_pdf_relatorio_pontual_classico):
        pdf_bytes = gerar(result, mapas, residual=_RESIDUAL_OK)
        assert b"/Count 7" in pdf_bytes
        assert b"Socioeconomia e Residual Fitness" in pdf_bytes
        assert b"Mapas de calor" in pdf_bytes
    assert "Socioeconomia e Residual Fitness" in PDF_SECTION_HEADERS
    # ASCII puro (latin-1-safe, sem travessao/bullet/reticencias).
    assert all(ord(ch) < 128 for ch in "Socioeconomia e Residual Fitness")


def test_slide_hero_offline_safe_sem_camada_residual():
    """Sem `hexes_df` NEM `socioeconomia` NEM `residual` existem (BLK-RELPON-13: ambas viraram
    hexagono a 5 km, CONDICIONAIS ao `hexes_df`) -> as DUAS celulas do slide-hero caem no fallback
    TEXTUAL ("Mapa indisponivel"), sem excecao, e a estrutura de 7 paginas e preservada."""
    result, mapas = _sample_result()
    assert "residual" not in mapas  # `_sample_result` nao passa `hexes_df`
    assert "socioeconomia" not in mapas  # BLK-RELPON-13: agora tambem condicional ao `hexes_df`

    for gerar in (gerar_pdf_relatorio_pontual_censitario, gerar_pdf_relatorio_pontual_classico):
        pdf_bytes = gerar(result, mapas, residual=_RESIDUAL_OK)
        assert pdf_bytes.startswith(b"%PDF-1.4")
        assert b"/Count 7" in pdf_bytes
        assert "Mapa indisponível para esta camada.".encode("latin-1") in pdf_bytes


def test_map_layer_titles_inclui_as_chaves_novas_senao_os_pngs_sumiriam():
    """Sem estas chaves em `MAP_LAYER_TITLES`, `_normalize_mapas` descartaria os PNGs novos
    em SILENCIO. `densidade` tem de continuar no indice 0 (titulo do caminho legado de bytes)."""
    from motor_expansao.dashboard.censo_report import MAP_LAYER_TITLES, _normalize_mapas_by_key

    chaves = [k for k, _t in MAP_LAYER_TITLES]
    assert chaves[0] == "densidade"
    assert "socioeconomia" in chaves
    assert "residual" in chaves
    passou = dict(_normalize_mapas_by_key({"socioeconomia": b"A", "residual": b"B"}))
    assert passou == {"socioeconomia": b"A", "residual": b"B"}
    # BLK-RELPON-14: `entorno` saiu do registro -> a chave e' descartada em silencio (a camada
    # tambem deixou de ser produzida em `censo_map`), que e' o comportamento desejado agora.
    assert dict(_normalize_mapas_by_key({"entorno": b"E"})) == {}


def test_grid_de_mapas_aceita_2x1_e_1x1_e_mantem_o_default_2x2():
    """DT-3: `cols`/`rows` keyword-only com default nos valores atuais -> o caminho 2x2 fica
    identico; o slide-hero pede 2 celulas lado a lado, sem sobreposicao. O caso 1x1 (1 celula
    unica preenchendo a altura util) segue coberto como MECANICA do helper, mesmo sem pagina
    que o use hoje (o slide de quadra saiu no BLK-RELPON-14)."""
    from motor_expansao.dashboard.censo_report import (
        _map_grid_cells,
        _map_grid_cells_packed,
    )

    assert len(_map_grid_cells(58.0, 518.0, 20.0, 10.0)) == 4
    assert len(_map_grid_cells_packed(1000.0 / 760.0, top=58.0, bottom=518.0, gap=10.0)) == 4

    duas = _map_grid_cells_packed(
        1000.0 / 760.0, top=58.0, bottom=518.0, gap=10.0, cols=2, rows=1
    )
    assert len(duas) == 2
    (x0, y0, w0, h0), (x1, y1, w1, h1) = duas
    assert x0 + w0 <= x1 + 1e-6  # lado a lado, sem sobrepor
    assert abs(y0 - y1) < 1e-9 and abs(h0 - h1) < 1e-9  # mesma linha, mesma altura
    assert abs(w0 - w1) < 1e-9

    # 1x1: uma celula so, sem o clamp de `max_total_w` -> preenche os 460 pt de
    # altura util (top=58 .. bottom=518) sem deixar vao branco, e nao transborda o `bottom`.
    assert len(_map_grid_cells(58.0, 518.0, 20.0, 10.0, cols=1, rows=1)) == 1
    uma = _map_grid_cells_packed(
        1280.0 / 760.0, top=58.0, bottom=518.0, gap=10.0, cols=1, rows=1
    )
    assert len(uma) == 1
    assert abs(uma[0][3] - 460.0) < 1e-6
    assert uma[0][1] + uma[0][3] <= 518.0 + 1e-6


# ---------------------------------------------------------------------------
# BLK-RELPON-14 — a pagina "Imagem do Entorno" (BLK-RELPON-11) foi REMOVIDA por completo
# (camada PNG + paginas do PDF + constantes orfas). O PDF base voltou a 7 paginas e o
# gerador ficou UNICO: o "recente" virou wrapper depreciado do classico.
# ---------------------------------------------------------------------------


def test_pagina_entorno_saiu_do_pdf_nas_2_variantes():
    """Nenhum vestigio do slide removido: titulo fora dos bytes e `entorno` fora dos registros."""
    from motor_expansao.dashboard.censo_report import MAP_LAYER_TITLES

    result, mapas = _sample_result()

    for gerar in (gerar_pdf_relatorio_pontual_censitario, gerar_pdf_relatorio_pontual_classico):
        pdf_bytes = gerar(result, mapas, residual=_RESIDUAL_OK)
        assert b"/Count 7" in pdf_bytes
        assert b"Imagem do Entorno" not in pdf_bytes

    assert len(PDF_SECTION_HEADERS) == 7
    assert "Imagem do Entorno" not in PDF_SECTION_HEADERS
    # A camada tambem deixou de ser produzida em `censo_map` -> a chave sai do registro.
    assert "entorno" not in [k for k, _t in MAP_LAYER_TITLES]


def test_wrapper_censitario_e_identico_ao_classico_e_avisa_depreciacao():
    """BLK-RELPON-14: `gerar_pdf_relatorio_pontual_censitario` virou WRAPPER FINO do classico.

    Contrato do wrapper: (a) emite `DeprecationWarning`, (b) devolve os MESMOS bytes que
    `gerar_pdf_relatorio_pontual_classico` para a mesma entrada (unificacao do gerador -- a
    estetica classica venceu) e (c) repassa os kwargs opcionais que so a classica aceitava.
    NB: a fixture de `conftest.py` congela o `/CreationDate` do fpdf2, entao a igualdade
    byte-a-byte nao e' flaky por causa do relogio.
    """
    import warnings

    result, mapas = _sample_result()
    kwargs = dict(residual=_RESIDUAL_OK, perfil_bairro=_PERFIL_BAIRRO_OK, rotulo="Av Teste, 100")

    with warnings.catch_warnings(record=True) as capturados:
        warnings.simplefilter("always")
        pdf_wrapper = gerar_pdf_relatorio_pontual_censitario(result, mapas, **kwargs)

    assert any(issubclass(w.category, DeprecationWarning) for w in capturados), (
        f"o wrapper deve emitir DeprecationWarning; capturado: {[w.category for w in capturados]}"
    )
    pdf_classico = gerar_pdf_relatorio_pontual_classico(result, mapas, **kwargs)
    assert pdf_wrapper == pdf_classico
    assert b"/Count 7" in pdf_wrapper

    # Superset da assinatura antiga: os kwargs que so a classica aceitava passam pelo wrapper.
    pdf_extra = gerar_pdf_relatorio_pontual_censitario(
        result, mapas, **kwargs, fotos=None, info_imovel=None, viabilidade=None
    )
    assert pdf_extra == pdf_classico


def test_pdf_nao_contem_a_sigla_nd_em_lugar_nenhum(tmp_path):
    """A sigla "n/d" NAO pode sobrar em NENHUM byte de texto do PDF (pedido de Juan).

    Existe porque a troca por `TEXTO_SEM_DADO` foi feita em duas rodadas e as duas passaram
    por cima de textos de INTERFACE que usavam a sigla dentro de uma string maior, com aspas
    diferentes das que a varredura procurava: a legenda dos Big Numbers ("cinza = 'n/d'
    (dado ausente para o ponto)") e o fallback da capa ("coordenada n/d"). Os dois saiam
    impressos, entao o relatorio mostrava "Não disponível" nos cards e "n/d" logo abaixo.

    Testar os FORMATADORES um a um nao pega isso -- nenhum dos dois passa por
    `_format_number`. So a varredura dos bytes do artefato final pega, e e por isso que este
    teste olha o PDF inteiro em vez de funcoes escolhidas a dedo.

    Gera SEM imagens (`mapas=None` + `ultra_dir` vazio) pelo mesmo motivo do teste de
    acentuacao: o binario PNG dos mapas/branding traria bytes arbitrarios e daria falso
    positivo. `result` minimo de proposito -> as metricas caem no caminho "sem dado", que e
    exatamente o cenario onde a sigla aparecia.
    """
    result = {"lat": -23.55, "lng": -46.63, "nome_municipio": "SAO PAULO", "uf": "SP", "raio_km": 1.5}
    pdf = gerar_pdf_relatorio_pontual_classico(result, None, ultra_dir=tmp_path)

    assert b"n/d" not in pdf, (
        "a sigla 'n/d' voltou ao PDF -- todo texto de dado ausente tem de usar TEXTO_SEM_DADO"
    )
    # Sanity: o cenario de fato exercita o caminho "sem dado" (senao o teste seria vacuo).
    assert TEXTO_SEM_DADO.encode("latin-1") in pdf
