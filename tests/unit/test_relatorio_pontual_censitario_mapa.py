from __future__ import annotations

from io import BytesIO

import numpy as np
import pandas as pd
from PIL import Image, ImageChops, ImageDraw
from pyproj import Transformer
from shapely.geometry import box
from shapely.ops import transform

import motor_expansao.dashboard.censo_map as censo_map
from motor_expansao.dashboard.censo_map import (
    _CHOROPLETH_ALPHA,
    _color_for_densidade,
    render_mapas_censitarios_combinados,
)
from motor_expansao.dashboard.censo_point import CRS_ORIGEM_CENSO, _local_metric_crs
from motor_expansao.dashboard.competitors import _ICON_CACHE
from motor_expansao.dashboard.constants import DENSIDADE_POP_BANDS

LAT_C = -23.55
LNG_C = -46.63

# BLK-RELPON-13: `socioeconomia` passou a ser HEXAGONO H3 a 5 km (score_setor_2022_calibrado),
# CONDICIONAL ao `hexes_df` como o `residual` — sem hexes desenhaveis a chave e' AUSENTE. Junto
# do `residual` (choropleth de hexagonos H3 no raio de EXIBICAO de 5 km), tambem CONDICIONAL.
# BLK-RELPON-14: a camada `entorno` (mapa de quadra do BLK-RELPON-11) foi REMOVIDA por completo,
# entao o set "sem hexes" voltou a 5 chaves e a tupla canonica a 7.
_CAMADAS_SEM_HEXES = {
    "densidade",
    "renda",
    "score",
    "renda_domiciliar",
    "concorrentes",
}
_CAMADAS = _CAMADAS_SEM_HEXES | {"socioeconomia", "residual"}


def _to_wgs_geometry(local_geom):
    transformer = Transformer.from_crs(_local_metric_crs(LAT_C, LNG_C), CRS_ORIGEM_CENSO, always_xy=True)
    return transform(transformer.transform, local_geom)


def _sector_record(
    cod_setor: str,
    local_geom,
    *,
    pop: float = 1000.0,
    renda: float = 2000.0,
    score: float = 70.0,
    densidade: float | None = None,
    moradores: float = 3.0,
) -> dict[str, object]:
    geom_wgs = _to_wgs_geometry(local_geom)
    minx, miny, maxx, maxy = geom_wgs.bounds
    dens = densidade if densidade is not None else pop / (local_geom.area / 1_000_000.0)
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
        "avg_moradores_domicilio_setor_2022": moradores,
        "renda_responsavel_media_setor_2022": renda * moradores,
        "densidade_pop_setor_hab_km2": dens,
        "score_setor_2022_calibrado": score,
        "flag_renda_disponivel": True,
        "flag_geometria_valida": True,
        "qualidade_join_uf": "A",
    }


def _all_colors(png: bytes):
    image = Image.open(BytesIO(png))
    return image.getcolors(maxcolors=1_000_000) or []


def test_mapas_combinados_gera_png_com_setores_pins_legenda_e_escala(tmp_path):
    setores = pd.DataFrame(
        [
            _sector_record("355030801000001", box(-700, -700, 0, 700), pop=800, score=40),
            _sector_record("355030801000002", box(0, -700, 700, 700), pop=1400, score=85),
        ]
    )
    competitors = pd.DataFrame(
        [{"nome_unidade": "Concorrente", "lat": LAT_C, "lng": LNG_C + 0.004, "rede": "smart_fit"}]
    )
    ultra = pd.DataFrame([{"nome_unidade": "Ultra", "lat": LAT_C + 0.003, "lng": LNG_C}])

    mapas = render_mapas_censitarios_combinados(
        LAT_C,
        LNG_C,
        setores,
        competitors_df=competitors,
        ultra_df=ultra,
        width=900,
        height=680,
        basemap=False,
    )

    assert set(mapas) == _CAMADAS_SEM_HEXES
    for camada, png in mapas.items():
        (tmp_path / f"mapa_{camada}.png").write_bytes(png)
        assert png.startswith(b"\x89PNG\r\n\x1a\n"), camada
        assert len(png) > 10_000, camada
        image = Image.open(BytesIO(png))
        if camada == "concorrentes":
            # Concorrentes e recortada (sem titulo/legenda) -> menor que o frame cheio.
            assert image.size[0] < 900 and image.size[1] < 680, camada
        else:
            assert image.size == (900, 680), camada
        assert len(_all_colors(png)) > 20, camada


def test_mapas_combinados_trata_estado_vazio_sem_concorrentes():
    mapas = render_mapas_censitarios_combinados(
        LAT_C,
        LNG_C,
        pd.DataFrame(),
        width=720,
        height=520,
        basemap=False,
    )

    # main (BLK-RELPON-13): sem `hexes_df` as camadas de hexagono ficam AUSENTES -> set "sem hexes".
    # piloto: itera com a CHAVE porque `concorrentes` e' recortada e tem tamanho proprio (abaixo).
    assert set(mapas) == _CAMADAS_SEM_HEXES
    for camada, png in mapas.items():
        image = Image.open(BytesIO(png))
        assert image.format == "PNG"
        if camada == "concorrentes":
            # Concorrentes e recortada (sem titulo/legenda) -> menor que o frame cheio.
            assert image.size[0] < 720 and image.size[1] < 520, camada
        else:
            assert image.size == (720, 520), camada


def test_mapa_censitario_faixas_fixas_nao_quartil():
    # Dois setores em faixas de densidade distintas: 800 -> faixa 1 (Reds claro),
    # 12.000 -> faixa 4 (Reds escuro). As cores devem casar com DENSIDADE_POP_BANDS,
    # NAO com quartis relativos dos dois valores.
    # RGB casa a faixa fixa (nao quartil); alpha do FILL e o canonico do choropleth
    # (mais transparente que a faixa da legenda, para as ruas aparecerem).
    assert _color_for_densidade(800.0)[:3] == DENSIDADE_POP_BANDS[0][2][:3]
    assert _color_for_densidade(12_000.0)[:3] == DENSIDADE_POP_BANDS[3][2][:3]
    assert _color_for_densidade(800.0)[3] == _CHOROPLETH_ALPHA
    assert _color_for_densidade(800.0) != _color_for_densidade(12_000.0)

    setores = pd.DataFrame(
        [
            _sector_record("355030801000001", box(-700, -700, 0, 700), densidade=800.0),
            _sector_record("355030801000002", box(0, -700, 700, 700), densidade=12_000.0),
        ]
    )
    mapas = render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores, width=800, height=600, basemap=False
    )
    # Fatia p/ RGB: o canvas agora e RGBA (fundo transparente), entao getcolors devolve
    # tuplas de 4 canais; a swatch solida da legenda tem alpha 255 e RGB == a faixa.
    colors = {c[:3] for _count, c in _all_colors(mapas["densidade"])}
    # A cor RGB exata da faixa 1 (clara) deve aparecer no PNG da densidade.
    assert DENSIDADE_POP_BANDS[0][2][:3] in colors


def test_mapa_censitario_ponto_central_pin_vermelho():
    # Ponto central = PIN VERMELHO (nao mais bolinha azul). A camada de concorrentes e
    # so-pins (BLK-CENSO-03: sem choropleth) e nao tem pin de rede aqui -> os unicos pixels
    # vermelhos na area do mapa vem do pin do ponto central.
    setores = pd.DataFrame(
        [_sector_record("355030801000001", box(-700, -700, 700, 700), pop=1000, score=88)]
    )
    mapas = render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores, width=800, height=600, basemap=False
    )
    image = Image.open(BytesIO(mapas["concorrentes"])).convert("RGB")
    # Recorta a area do mapa (exclui a legenda a direita, que tambem tem um pin de amostra).
    map_area = image.crop((28, 92, 515, 546))
    reds = sum(
        count
        for count, (r, g, b) in (map_area.getcolors(maxcolors=1_000_000) or [])
        if r > 180 and g < 90 and b < 90
    )
    # cor antiga (20,96,181) do ponto central: b ~181. NAO confundir com o circulo do
    # raio, que passou a ser AZUL VIVIDO (0,102,255 -> ~(19,113,254), b~254) por pedido
    # de Vini 2026-06-17; por isso o teto b < 215 isola a bolinha antiga do circulo novo.
    blues_old = sum(
        count
        for count, (r, g, b) in (map_area.getcolors(maxcolors=1_000_000) or [])
        if 150 < b < 215 and r < 60 and 70 < g < 130
    )
    assert reds > 0
    assert blues_old == 0


def test_mapa_censitario_marcador_quadrado_concorrente_e_ultra():
    """BLK-RELPON-09: marcador de concorrente/Ultra e a LOGO QUADRADA, nao o balao.

    Teste DIFERENCIAL (renderiza a MESMA camada com e sem pins): a camada
    "concorrentes" e so-pins (sem choropleth) e seu titulo/legenda sao estaticos, entao
    as duas imagens diferem EXCLUSIVAMENTE pelos 2 tiles colados. Prova (a) que os dois
    marcadores foram desenhados, (b) que sao 2 clusters separados, (c) que o footprint e
    QUADRADO (~`_PIN_LOGO_PX`), (d) que a ancora e o CENTRO do quadrado (S2b) e (e) a
    identidade de marca por lado. Substitui a contagem de "pixels avermelhados" antiga,
    que media o BALAO (`ULTRA_BRAND["bg"]`) e deixou de existir.
    """
    # `_ICON_CACHE` e estado de modulo e outros testes o populam: sem os pops, a placa
    # viria BRANCA (ramo com logo) e as cores de marca abaixo nao existiriam.
    _ICON_CACHE.pop("smart_fit", None)
    _ICON_CACHE.pop("__ultra__", None)
    try:
        setores = pd.DataFrame(
            [_sector_record("355030801000001", box(-700, -700, 700, 700), pop=1000, score=60)]
        )
        competitors = pd.DataFrame(
            [{"nome_unidade": "Smart Fit", "lat": LAT_C, "lng": LNG_C + 0.004, "rede": "smart_fit"}]
        )
        ultra = pd.DataFrame([{"nome_unidade": "Ultra", "lat": LAT_C, "lng": LNG_C - 0.004}])

        base = render_mapas_censitarios_combinados(
            LAT_C, LNG_C, setores, width=800, height=600, basemap=False
        )
        com_pins = render_mapas_censitarios_combinados(
            LAT_C,
            LNG_C,
            setores,
            competitors_df=competitors,
            ultra_df=ultra,
            width=800,
            height=600,
            basemap=False,
        )
        img_base = Image.open(BytesIO(base["concorrentes"])).convert("RGB")
        img_pins = Image.open(BytesIO(com_pins["concorrentes"])).convert("RGB")

        diff = ImageChops.difference(img_base, img_pins)
        mask = np.array(diff.convert("L")) > 0
        ys, xs = np.nonzero(mask)

        # dois quadrados de 30x30 (+sombra) ~ 1.800 px; o teto prova que NAO foi a
        # figura inteira que mudou.
        assert 1200 <= int(mask.sum()) <= 2600

        # dois clusters horizontais separados, cada um com o footprint do quadrado
        uniq = sorted(set(int(v) for v in xs))
        clusters: list[tuple[int, int]] = []
        atual = [uniq[0]]
        for anterior, seguinte in zip(uniq[:-1], uniq[1:], strict=True):
            if seguinte - anterior >= 10:
                clusters.append((atual[0], atual[-1]))
                atual = [seguinte]
            else:
                atual.append(seguinte)
        clusters.append((atual[0], atual[-1]))
        assert len(clusters) == 2
        for x0, x1 in clusters:
            assert 26 <= (x1 - x0 + 1) <= 34
        assert 26 <= (ys.max() - ys.min() + 1) <= 34

        # ancora CENTRADA (S2b): o centro vertical do marcador coincide com a PONTA do
        # pin vermelho central (mesma latitude). Com ancora na base cairia ~15 px acima.
        vermelho = np.all(np.array(img_base) == np.array([220, 38, 38]), axis=-1)
        vermelho[:, 800 - censo_map._LEGEND_COL_W :] = False  # exclui o pin da legenda
        ys_vermelho, _xs_vermelho = np.nonzero(vermelho)
        ponta_cy = int(ys_vermelho.max())
        assert abs(((ys.min() + ys.max()) / 2) - ponta_cy) <= 3

        # identidade de marca por lado: Ultra (#C8001E) a OESTE (LNG_C - 0.004),
        # Smart Fit (#FFE600) a LESTE. Ambas vem do fallback de sigla (cache limpo).
        arr_pins = np.array(img_pins)
        (esq_x0, esq_x1), (dir_x0, dir_x1) = clusters
        ultra_mask = np.all(arr_pins == np.array([200, 0, 30]), axis=-1)
        smart_mask = np.all(arr_pins == np.array([255, 230, 0]), axis=-1)
        assert ultra_mask[:, esq_x0 : esq_x1 + 1].sum() > 0
        assert smart_mask[:, dir_x0 : dir_x1 + 1].sum() > 0
    finally:
        _ICON_CACHE.pop("smart_fit", None)
        _ICON_CACHE.pop("__ultra__", None)


def test_fetch_basemap_sem_contextily_devolve_none(monkeypatch):
    # Sem o extra [basemap] (import contextily falha) -> _fetch_basemap retorna None,
    # sem levantar. Garante o caminho de CI sem internet nem dependencia opcional.
    import builtins

    real_import = builtins.__import__

    def _no_contextily(name, *args, **kwargs):
        if name == "contextily":
            raise ImportError("no contextily")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_contextily)
    assert censo_map._fetch_basemap((-5_000_000, -3_000_000, -4_999_000, -2_999_000), 800) is None


def test_mapa_censitario_fallback_offline_sem_tiles(monkeypatch):
    # Forca basemap=True mas com o fetch de tiles indisponivel (sem internet/contextily):
    # NAO deve levantar; gera PNG sobre canvas branco. Mockamos _fetch_basemap para
    # devolver None (resultado do try/except interno) e garantimos que nao quebra.
    setores = pd.DataFrame(
        [_sector_record("355030801000001", box(-700, -700, 700, 700), pop=1000, score=60)]
    )
    monkeypatch.setattr(censo_map, "_fetch_basemap", lambda *a, **k: None)
    mapas = censo_map.render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores, width=800, height=600, basemap=True
    )
    assert set(mapas) == _CAMADAS_SEM_HEXES
    for png in mapas.values():
        assert png.startswith(b"\x89PNG\r\n\x1a\n")


# ── BLK-CENSO-03: base CLARA Voyager + camada Concorrentes so-pins ──────────────


def test_basemap_provider_attr_e_voyager():
    import motor_expansao.dashboard.censo_map as m

    assert m._BASEMAP_PROVIDER_ATTR == "Voyager", (
        f"Esperado 'Voyager' (base clara), obtido '{m._BASEMAP_PROVIDER_ATTR}'"
    )


def test_overlay_usa_pixels_escuros_nao_claros():
    import motor_expansao.dashboard.censo_map as m

    # STREET_CEIL deve existir (novo) e STREET_FLOOR NAO deve existir (removido).
    assert hasattr(m, "_STREET_CEIL"), "Falta _STREET_CEIL (overlay pixels escuros)"
    assert not hasattr(m, "_STREET_FLOOR"), "_STREET_FLOOR deve ser removido (era do Dark Matter)"
    # Sanidade: CEIL entre 100 e 220 (razoavel para Voyager).
    assert 100 < m._STREET_CEIL < 220


def test_dark_map_ink_e_escuro():
    import motor_expansao.dashboard.censo_map as m

    r, g, b = m._DARK_MAP_INK[:3]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    assert lum < 100, f"_DARK_MAP_INK deve ser escuro para tema claro, luminancia={lum:.1f}"


def test_camada_concorrentes_pins_pura_sem_choropleth():
    # A camada "concorrentes" nao deve ter choropleth: na regiao central sem pins, o fundo
    # deve ser quase uniforme (apenas basemap/canvas), com variancia de cor MENOR que a
    # camada densidade (que tem choropleth de faixas).
    import numpy as np

    setores = pd.DataFrame(
        [
            _sector_record("355030801000001", box(-700, -700, 0, 700), densidade=10000.0),
            _sector_record("355030801000002", box(0, -700, 700, 700), densidade=500.0),
        ]
    )
    mapas = render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores, width=800, height=600, basemap=False
    )
    crop_box = (100, 150, 400, 450)
    dens_arr = np.array(Image.open(BytesIO(mapas["densidade"])).convert("RGB").crop(crop_box))
    conc_arr = np.array(Image.open(BytesIO(mapas["concorrentes"])).convert("RGB").crop(crop_box))
    dens_var = float(dens_arr.std())
    conc_var = float(conc_arr.std())
    assert conc_var < dens_var, (
        "Camada concorrentes deveria ser mais uniforme (sem choropleth) que densidade. "
        f"std concorrentes={conc_var:.1f}, std densidade={dens_var:.1f}"
    )


def test_camada_score_tem_choropleth_e_legenda():
    # BLK-CENSO-03-FU5: a camada "score" deve ter choropleth (modo de cor ativo), ao contrario
    # da "concorrentes" (so-pins). A variancia de cor na regiao central deve ser MAIOR na score
    # que na concorrentes (que nao tem choropleth).
    import numpy as np

    setores = pd.DataFrame(
        [
            _sector_record("355030801000001", box(-700, -700, 0, 700), score=15.0),
            _sector_record("355030801000002", box(0, -700, 700, 700), score=95.0),
        ]
    )
    mapas = render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores, width=800, height=600, basemap=False
    )
    assert "score" in mapas
    crop_box = (100, 150, 400, 450)
    score_arr = np.array(Image.open(BytesIO(mapas["score"])).convert("RGB").crop(crop_box))
    conc_arr = np.array(Image.open(BytesIO(mapas["concorrentes"])).convert("RGB").crop(crop_box))
    assert float(score_arr.std()) > float(conc_arr.std()), (
        "Camada score deveria ter choropleth (mais variada) que a concorrentes (so-pins)."
    )


def test_atribuicao_tiles_constante_e_legenda_arredondada_disponiveis():
    """D7=C subset seguro + D8=B (BLK-EST-02): constante de atribuicao definida e legenda usa
    amostras arredondadas (rounded_rectangle). Garante o caminho de render limpo sem quebrar.
    """
    import inspect

    import motor_expansao.dashboard.censo_map as m

    # D8=B: a atribuicao CARTO/OSM e uma constante reutilizavel no rodape do PNG.
    assert m._ATRIBUICAO_TILES == "(c) OpenStreetMap, (c) CARTO"
    # D7=C subset seguro: a legenda passou a desenhar amostras arredondadas + separador.
    legend_src = inspect.getsource(m._draw_legend_camada)
    assert "rounded_rectangle" in legend_src
    assert "draw.line" in legend_src  # separador faixas x pins
    # D6=A: titulos dos mapas SEM o prefixo repetitivo "Relatorio Pontual Censitario - ".
    combinador_src = inspect.getsource(m.render_mapas_censitarios_combinados)
    assert "Relatorio Pontual Censitario - " not in combinador_src
    assert 'titulo="Densidade populacional"' in combinador_src
    # Camada Concorrentes (pedido Felipe 2026-07-23): SEM titulo interno e SEM legenda
    # (o mapa e so-pins; titulo/legenda eram redundantes com a barra do slide).
    assert "mostrar_legenda=False" in combinador_src


# ── BLK-RELPON-05: faixa "<variavel> no ponto" por camada ───────────────────────


def test_valor_ponto_repassado_aos_4_choropleths_nao_a_concorrentes(monkeypatch):
    # O ponto (0,0) cai dentro do setor A (renda/score distintos do B) -> os 4
    # choropleths (densidade/renda/score/renda domiciliar) devem receber `valor_ponto` nao-None
    # com o rotulo correspondente; a camada Concorrentes deve receber `valor_ponto=None`.
    setores = pd.DataFrame(
        [
            _sector_record("355030801000001", box(-700, -700, 0, 700), renda=1900, score=55),
            _sector_record("355030801000002", box(0, -700, 700, 700), renda=4200, score=95),
        ]
    )

    capturado: dict[str, dict] = {}
    original = censo_map._render_camada

    def _spy(*, titulo, **kwargs):
        capturado[titulo] = kwargs
        return original(titulo=titulo, **kwargs)

    monkeypatch.setattr(censo_map, "_render_camada", _spy)

    censo_map.render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores, width=800, height=600, basemap=False
    )

    assert capturado["Densidade populacional"]["valor_ponto"] is not None
    assert "Densidade" in capturado["Densidade populacional"]["valor_ponto"]
    assert capturado["Renda per capita"]["valor_ponto"] is not None
    assert "Renda" in capturado["Renda per capita"]["valor_ponto"]
    assert capturado["Score censitario"]["valor_ponto"] is not None
    assert "Score" in capturado["Score censitario"]["valor_ponto"]
    assert capturado["Renda media domiciliar"]["valor_ponto"] is not None
    assert "Renda dom." in capturado["Renda media domiciliar"]["valor_ponto"]
    # A camada Concorrentes nunca recebe o kwarg `valor_ponto` (fica no default None de
    # `_render_camada`, ver assinatura) -- byte-a-byte igual ao render antigo.
    # Camada Concorrentes: titulo interno agora "" (removido; pedido Felipe 2026-07-23) e
    # nunca recebe `valor_ponto` (fica no default None de `_render_camada`).
    assert capturado[""].get("valor_ponto") is None
    # BLK-RELPON-06 (D1): a faixa REVERTE de "no ponto" para "no raio" -- trava a reversao.
    for titulo in (
        "Densidade populacional",
        "Renda per capita",
        "Score censitario",
        "Renda media domiciliar",
    ):
        assert "no raio" in capturado[titulo]["valor_ponto"]
        assert "no ponto" not in capturado[titulo]["valor_ponto"]


def test_valor_raio_nao_e_nd_quando_setor_nao_cobre_o_ponto_mas_intersecta_raio(monkeypatch):
    # BLK-RELPON-06 (D1): unico setor NAO cobre o ponto central (0,0) -- so intersecta
    # parcialmente o raio -- mas isso NAO produz "n/d": a faixa agora mostra os agregados
    # do RAIO (n_setores=1, pop_total_raio nao-None), que sao valores REAIS aqui (sob
    # BLK-RELPON-05 a faixa vinha do lookup "setor que contem o ponto" e dava n/d neste
    # cenario; a semantica mudou).
    setores = pd.DataFrame(
        [_sector_record("355030801000003", box(1000, -500, 2500, 500), renda=2000, score=60)]
    )

    capturado: dict[str, dict] = {}
    original = censo_map._render_camada

    def _spy(*, titulo, **kwargs):
        capturado[titulo] = kwargs
        return original(titulo=titulo, **kwargs)

    monkeypatch.setattr(censo_map, "_render_camada", _spy)

    censo_map.render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores, width=800, height=600, basemap=False
    )

    assert "n/d" not in capturado["Densidade populacional"]["valor_ponto"]
    assert "n/d" not in capturado["Renda per capita"]["valor_ponto"]
    assert "n/d" not in capturado["Score censitario"]["valor_ponto"]
    assert capturado["Renda per capita"]["valor_ponto"] == "Renda no raio: R$ 2.000"
    assert capturado["Score censitario"]["valor_ponto"] == "Score no raio: 60"
    # Camada Concorrentes: titulo interno agora "" (removido; pedido Felipe 2026-07-23) e
    # nunca recebe `valor_ponto` (fica no default None de `_render_camada`).
    assert capturado[""].get("valor_ponto") is None


def test_valor_raio_e_nd_quando_setor_fora_do_raio(monkeypatch):
    # BLK-RELPON-06 (D1): o "n/d" de verdade e quando NAO ha setores intersectados no raio
    # (geometria de test_motor_censitario_exclui_setor_fora_do_raio) -- n_setores=0.
    setores = pd.DataFrame(
        [_sector_record("355030801000030", box(3000, 3000, 3500, 3500), renda=2000, score=60)]
    )

    capturado: dict[str, dict] = {}
    original = censo_map._render_camada

    def _spy(*, titulo, **kwargs):
        capturado[titulo] = kwargs
        return original(titulo=titulo, **kwargs)

    monkeypatch.setattr(censo_map, "_render_camada", _spy)

    censo_map.render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores, width=800, height=600, basemap=False
    )

    assert "n/d" in capturado["Densidade populacional"]["valor_ponto"]
    assert "n/d" in capturado["Renda per capita"]["valor_ponto"]
    assert "n/d" in capturado["Score censitario"]["valor_ponto"]
    # Camada Concorrentes: titulo interno agora "" (removido; pedido Felipe 2026-07-23) e
    # nunca recebe `valor_ponto` (fica no default None de `_render_camada`).
    assert capturado[""].get("valor_ponto") is None


def test_valor_ponto_muda_pixels_do_png():
    # Mesmo setores_df, exceto a renda do unico setor (que tambem cobre o ponto): os
    # bytes do PNG "renda" devem diferir (a faixa do RAIO muda com a renda -- unico setor,
    # entao a media ponderada do raio == o valor daquele setor); os bytes do "concorrentes"
    # devem ser IDENTICOS (essa camada nao e afetada por `valor_ponto`).
    setor_cobre_ponto = box(-700, -700, 700, 700)

    setores_a = pd.DataFrame(
        [_sector_record("355030801000004", setor_cobre_ponto, renda=1800.0, score=50)]
    )
    setores_b = pd.DataFrame(
        [_sector_record("355030801000004", setor_cobre_ponto, renda=5200.0, score=50)]
    )

    mapas_a = render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores_a, width=800, height=600, basemap=False
    )
    mapas_b = render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores_b, width=800, height=600, basemap=False
    )

    assert mapas_a["renda"] != mapas_b["renda"]
    assert mapas_a["concorrentes"] == mapas_b["concorrentes"]


def test_fallback_offline_canvas_claro(monkeypatch):
    # Sem basemap (tiles indisponivel): canvas deve ser CLARO, nao escuro.
    monkeypatch.setattr(censo_map, "_fetch_basemap", lambda *a, **k: None)
    mapas = censo_map.render_mapas_censitarios_combinados(
        LAT_C, LNG_C, pd.DataFrame(), width=600, height=400, basemap=True
    )
    img = Image.open(BytesIO(mapas["densidade"])).convert("RGB")
    left, top, right, bottom = censo_map._map_box(600, 400)
    # BLK-RELPON-06 (D4): com `_MAP_TOP`/`_LEGEND_COL_W` novos a caixa 600x400 encolheu
    # o bastante para o pixel EXATAMENTE central cair na ponta do pin vermelho do ponto
    # central (sempre desenhado no centro do frame projetado). Amostra perto de um canto
    # do interior da caixa -- fora do circulo de 1.5 km (que fica inscrito no frame) e do
    # pin -- para continuar testando so o fundo do canvas de fallback.
    cx, cy = left + 20, top + 20
    r, g, b = img.getpixel((cx, cy))
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    assert lum > 180, f"Canvas fallback deveria ser claro, luminancia={lum:.1f} (r={r},g={g},b={b})"


def test_shared_transformer_bytes_identicos():
    """Fix 1 BLK-PERF-01a: transformer compartilhado — PNGs identicos em 2 chamadas consecutivas."""
    setores = pd.DataFrame([
        _sector_record("355030801000001", box(-700, -700, 0, 700), pop=800, score=40),
        _sector_record("355030801000002", box(0, -700, 700, 700), pop=1400, score=85),
    ])
    mapas_a = render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores, width=600, height=460, basemap=False
    )
    mapas_b = render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores, width=600, height=460, basemap=False
    )
    for camada in ("densidade", "renda", "score", "renda_domiciliar", "concorrentes"):
        assert mapas_a[camada] == mapas_b[camada], f"PNG nao-deterministico na camada {camada}"


# ── BLK-RELPON-06 (D3): fonte TrueType embutida do Pillow (determinística) ──────────────


def test_font_escala_com_o_size():
    # O bug de producao era exatamente `_font(20)` e `_font(60)` renderizarem IGUAL (bitmap
    # fixo ~10px do load_default() SEM size). Prova que o `size` passa a ser respeitado.
    small = censo_map._font(20).getbbox("A")
    big = censo_map._font(40).getbbox("A")
    small_w, small_h = small[2] - small[0], small[3] - small[1]
    big_w, big_h = big[2] - big[0], big[3] - big[1]
    assert big_w > small_w
    assert big_h > small_h


def test_font_nao_chama_truetype_do_sistema_no_proprio_codigo():
    # Trava o determinismo Windows<->VPS do D3: o CODIGO de `_font` nao deve chamar
    # `ImageFont.truetype(...)` (arial.ttf so existe no Windows; a imagem de producao
    # python:3.11-slim nao tem fonte alguma). NB: `ImageFont.load_default(size=...)` usa
    # `truetype` internamente sobre os BYTES da fonte embutida do Pillow (nao um path de
    # disco) -- por isso a checagem e por INSPECAO DE CODIGO-FONTE (ignorando comentarios),
    # nao por monkeypatch de `ImageFont.truetype` (que quebraria o proprio `load_default`).
    import inspect

    src = inspect.getsource(censo_map._font)
    code_lines = [line for line in src.splitlines() if not line.strip().startswith("#")]
    code = "\n".join(code_lines)
    assert "truetype(" not in code
    assert "arial" not in code.lower()


def test_font_nao_depende_de_ttf_do_sistema():
    # `_font` funciona mesmo com o Pillow sem NENHUMA fonte TrueType do sistema instalada
    # (caso da imagem python:3.11-slim): usa so a fonte embutida do proprio Pillow.
    font = censo_map._font(20)
    assert font.getbbox("A") is not None


# ── BLK-RELPON-06 (D4): contrato de legibilidade em codigo (nao so revisao visual) ──────


def test_legenda_corpo_atinge_o_alvo_de_legibilidade_no_pdf():
    # Slide "Mapas de calor" em grid 2x2 (PNG 1000x760). A ALTURA da celula limita a escala.
    from motor_expansao.dashboard.censo_report import (
        _CLASSICO_MAPS_TOP,
        _PAGE_H,
        _map_grid_cells,
    )

    png_w, png_h = 1000.0, 760.0
    # Variante RECENTE (top=60): celula ~454x221 -> legenda ~9,3pt >= 9pt (contrato mantido).
    cell_r = _map_grid_cells(60.0, _PAGE_H - 26.0, 20.0, 12.0)[0]
    ratio_r = min(cell_r[2] / png_w, cell_r[3] / png_h)
    assert censo_map._FS_LEGENDA_CORPO * ratio_r >= 9.0
    # Variante CLASSICA (o PDF que o dashboard baixa; header fixo banda+titulo em top ~122): a
    # celula 2x2 e mais baixa (~454x190) -> legenda cai para ~8pt. E' o piso legivel ACEITO para
    # caber 4 mapas no espaco menor do classico (nao ha altura para 9pt com 4 mapas ali).
    cell_c = _map_grid_cells(_CLASSICO_MAPS_TOP, _PAGE_H - 26.0, 20.0, 12.0)[0]
    ratio_c = min(cell_c[2] / png_w, cell_c[3] / png_h)
    assert censo_map._FS_LEGENDA_CORPO * ratio_c >= 8.0


def test_rotulo_mais_longo_da_legenda_cabe_na_coluna():
    from motor_expansao.dashboard.constants import (
        OFERTA_DISPONIVEL_ALUNOS_BANDS,
        RENDA_MEDIA_DOMICILIAR_BANDS,
        RENDA_PER_CAPITA_BANDS,
    )

    image = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(image, "RGBA")
    font = censo_map._font(censo_map._FS_LEGENDA_CORPO)
    orcamento = censo_map._LEGEND_COL_W - 78
    # As duas camadas de renda usam o MESMO formato compacto de rotulo (per capita e domiciliar);
    # o rotulo mais longo de cada uma deve caber na coluna estreita da legenda.
    # BLK-RELPON-10: a regua de residual em ALUNOS entra na mesma verificacao (rotulo mais longo
    # "5.001-10.000", 12 chars vs 14 do pior caso "R$ 2.001-3.500") -> travado por teste.
    for bands in (
        RENDA_PER_CAPITA_BANDS,
        RENDA_MEDIA_DOMICILIAR_BANDS,
        OFERTA_DISPONIVEL_ALUNOS_BANDS,
    ):
        rotulo_mais_longo = max((label for _upper, label, _color in bands), key=len)
        largura = censo_map._text_width(draw, rotulo_mais_longo, font)
        assert largura <= orcamento, (
            f"Rotulo '{rotulo_mais_longo}' ({largura}px) nao cabe no orcamento de "
            f"{orcamento}px da coluna de legenda (_LEGEND_COL_W={censo_map._LEGEND_COL_W})"
        )


def test_legenda_subtitulo_mais_longo_nao_transborda_do_canvas():
    # Regressao real encontrada no ajuste visual: "Renda per capita (R$/pessoa)" a
    # `_FS_LEGENDA_TITULO`/`_FS_LEGENDA_CORPO` transbordava do canvas (o subtitulo e
    # desenhado em x=legend_x, sem o +68 de indentacao dos rotulos/captions).
    # `_FS_LEGENDA_SUBTITULO` (fonte dedicada, menor) deve caber no restante do canvas.
    image = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(image, "RGBA")
    font = censo_map._font(censo_map._FS_LEGENDA_SUBTITULO)
    largura = censo_map._text_width(draw, "Renda per capita (R$/pessoa)", font)
    orcamento = censo_map._LEGEND_COL_W - 10
    assert largura <= orcamento, (
        f"Subtitulo ({largura}px) nao cabe no orcamento de {orcamento}px "
        f"(_FS_LEGENDA_SUBTITULO={censo_map._FS_LEGENDA_SUBTITULO})"
    )


def test_legenda_caption_pins_nao_transborda_do_canvas():
    # Regressao real encontrada no ajuste visual: "Pins: Ultra e concorrentes" a
    # `_FS_LEGENDA_CORPO` (32px) transbordava do canvas (largura ~362px > orcamento da
    # coluna). `_FS_LEGENDA_CAPTION` (fonte dedicada, menor) deve caber com folga dentro
    # do canto direito do canvas, para QUALQUER largura de canvas (a coluna e ancorada em
    # `width - _LEGEND_COL_W`, entao o orcamento ate a borda e constante).
    image = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(image, "RGBA")
    font = censo_map._font(censo_map._FS_LEGENDA_CAPTION)
    largura = censo_map._text_width(draw, "Pins: Ultra e concorrentes", font)
    orcamento = censo_map._LEGEND_COL_W - 68 - 10
    assert largura <= orcamento, (
        f"Caption ({largura}px) nao cabe no orcamento de {orcamento}px "
        f"(_FS_LEGENDA_CAPTION={censo_map._FS_LEGENDA_CAPTION})"
    )


# ── BLK-RELPON-10: camada de Residual Fitness por hexagono (raio de EXIBICAO 5 km) ──────────


def _hexes_sinteticos(lat: float = LAT_C, lng: float = LNG_C, k: int = 5) -> pd.DataFrame:
    """Disco H3 res-7 em torno do ponto, com `oferta_efetiva_disponivel` (residual) e
    `score_setor_2022_calibrado` (socioeconomia BLK-RELPON-13) variando por faixa."""
    import h3

    centro = h3.latlng_to_cell(lat, lng, 7)
    celulas = list(h3.grid_disk(centro, k))
    # Valores que cruzam TODAS as 6 faixas (0 / 1.250 / 2.500 / 5.000 / 10.000 / inf).
    valores = [float(i % 6) * 2_600.0 for i in range(len(celulas))]
    # Score censitario 0-100 cruzando as faixas de 20 pontos (BLK-RELPON-13: socioeconomia hex).
    scores = [float((i % 10) * 11) for i in range(len(celulas))]
    return pd.DataFrame(
        {
            "hex_id": celulas,
            "oferta_efetiva_disponivel": valores,
            "score_setor_2022_calibrado": scores,
        }
    )


def _setores_um_quadrado() -> pd.DataFrame:
    return pd.DataFrame(
        [_sector_record("355030801000001", box(-700, -700, 700, 700), pop=1000, score=70)]
    )


def test_camada_residual_presente_com_hexes_df_e_png_valido():
    mapas = render_mapas_censitarios_combinados(
        LAT_C,
        LNG_C,
        _setores_um_quadrado(),
        width=1000,
        height=760,
        basemap=False,
        hexes_df=_hexes_sinteticos(),
    )

    assert set(mapas) == _CAMADAS
    png = mapas["residual"]
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    image = Image.open(BytesIO(png))
    assert image.size == (1000, 760)
    # Choropleth de fato desenhado (varias faixas de cor no canvas).
    assert len(_all_colors(png)) > 20


def test_camada_residual_nao_desenha_pins_blk_relpon_10_fu1():
    """BLK-RELPON-10-FU1: a camada `residual` (5 km) NAO desenha pins de concorrente/Ultra.

    Gate visual de Vinicius (2026-07-22): a area a 5 km e ~11x a de 1,5 km (r^2), entao a
    densidade de logos cobria o choropleth -- medido na amostra da Av. Paulista, onde os
    marcadores tapavam quase todos os hexagonos. Quem esta instalado ja aparece na pagina
    "Concorrentes"; este mapa responde ONDE HA ESPACO, e a cor e o dado dele.

    Teste DIFERENCIAL: renderiza duas vezes, com e sem pontos, e exige que o PNG do
    `residual` seja BYTE-IDENTICO -- prova que nenhum pixel do mapa depende dos pontos.
    BLK-RELPON-13: a `socioeconomia` virou hex a 5 km SEM pins -> tambem imune aos pontos
    (byte-identica). A sentinela anti-vacuo passa a ser a camada `score` (setor a 1,5 km, que
    MANTEM pins): sem ela, remover os pins de TODAS as camadas passaria trivialmente no teste.
    """
    setores = _setores_um_quadrado()
    hexes = _hexes_sinteticos()
    # pontos bem no centro do frame -> cairiam dentro dos dois mapas se houvesse pins
    competitors = pd.DataFrame(
        [{"nome_unidade": "Concorrente", "lat": LAT_C, "lng": LNG_C + 0.004, "rede": "smart_fit"}]
    )
    ultra = pd.DataFrame([{"nome_unidade": "Ultra", "lat": LAT_C + 0.003, "lng": LNG_C}])

    def _render(com_pontos: bool):
        return render_mapas_censitarios_combinados(
            LAT_C, LNG_C, setores, width=1000, height=760, basemap=False, hexes_df=hexes,
            competitors_df=competitors if com_pontos else None,
            ultra_df=ultra if com_pontos else None,
        )

    com, sem = _render(True), _render(False)

    # (1) residual e imune aos pontos -> nenhum pin foi desenhado
    assert com["residual"] == sem["residual"], (
        "a camada `residual` mudou ao receber concorrentes/Ultra -- ela nao pode desenhar pins"
    )
    # (2) e a legenda nao promete pins que nao existem
    assert b"Pins: Ultra e concorrentes" not in com["residual"]

    # (3) socioeconomia (BLK-RELPON-13: hex a 5 km SEM pins) tambem e imune aos pontos.
    assert com["socioeconomia"] == sem["socioeconomia"], (
        "a camada `socioeconomia` (hex a 5 km) nao pode desenhar pins"
    )
    # (4) trava anti-vacuo: `score` (setor a 1,5 km) CONTINUA com pins, senao o teste (1)
    # passaria trivialmente caso alguem removesse os pins de todas as camadas.
    assert com["score"] != sem["score"], (
        "a camada `score` deveria continuar desenhando pins"
    )


def test_camada_residual_ausente_sem_hexes_df_ou_sem_hex_no_disco():
    setores = _setores_um_quadrado()
    # (a) sem `hexes_df` -> chave ausente (default preserva todos os callers antigos).
    sem = render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores, width=800, height=600, basemap=False
    )
    assert "residual" not in sem
    # (b) `hexes_df` sem NENHUM hex do disco (hex de outra regiao) -> chave ausente, sem excecao.
    import h3

    longe = pd.DataFrame(
        {
            "hex_id": [h3.latlng_to_cell(-3.119, -60.0217, 7)],  # Manaus, longe de SP
            "oferta_efetiva_disponivel": [5_000.0],
        }
    )
    vazio = render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores, width=800, height=600, basemap=False, hexes_df=longe
    )
    assert "residual" not in vazio
    # (c) DataFrame vazio -> idem.
    assert "residual" not in render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores, width=800, height=600, basemap=False, hexes_df=pd.DataFrame()
    )


# ── BLK-RELPON-13: socioeconomia do slide-hero = hexagono H3 a 5 km (score_setor_2022_calibrado) ──


def test_socioeconomia_e_hexagono_nao_setor_a_5km(monkeypatch):
    """A `socioeconomia` do slide-hero passou a ser o choropleth de `score_setor_2022_calibrado`
    por hexagono H3 res-7 no raio de EXIBICAO de 5 km (mesma bbox/geometria do residual), nao mais
    o setor a 1,5 km. Prova indireta: com `hexes_df`, a chave existe, e PNG valido e emite o titulo
    "Socioeconomia" (ASCII).

    BLK-RELPON-14: os 5 km deixaram de ser REPRESENTADOS — o titulo perdeu o sufixo "- raio 5 km"
    e o rodape perdeu o prefixo "Raio 5,0 km". O enquadramento continua em 5 km
    (`RAIO_RESIDUAL_DISPLAY_KM`, INTOCADO); quem identifica o ponto e' a borda do hex central."""
    textos: list[str] = []
    real = censo_map._draw_text

    def _spy(draw, xy, text, **kwargs):
        textos.append(text)
        return real(draw, xy, text, **kwargs)

    monkeypatch.setattr(censo_map, "_draw_text", _spy)
    mapas = render_mapas_censitarios_combinados(
        LAT_C,
        LNG_C,
        _setores_um_quadrado(),
        width=1000,
        height=760,
        basemap=False,
        hexes_df=_hexes_sinteticos(),
    )

    assert "socioeconomia" in mapas
    png = mapas["socioeconomia"]
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    image = Image.open(BytesIO(png))
    assert image.size == (1000, 760)
    assert len(_all_colors(png)) > 20
    assert "Socioeconomia" in textos
    assert "EPSG:3857 - fundo de ruas offline" in textos
    # Nenhum texto do painel de 5 km promete raio de analise (nem no titulo, nem no rodape).
    assert not any(t.startswith("Socioeconomia - raio") for t in textos)
    assert not any(t.startswith("Raio 5,0 km") for t in textos)
    # Legenda com a escala de score (0-100), nao a de residual (alunos).
    assert "Score censitario (0-100)" in textos


def test_socioeconomia_ausente_sem_hexes_df_ou_sem_coluna_score():
    """CONDICIONAL como o residual: sem `hexes_df`, sem a coluna `score_setor_2022_calibrado`
    ou sem hex no disco, a chave `socioeconomia` e AUSENTE (fallback textual do PDF), sem excecao."""
    setores = _setores_um_quadrado()
    # (a) sem `hexes_df` -> chave ausente.
    sem = render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores, width=800, height=600, basemap=False
    )
    assert "socioeconomia" not in sem
    # (b) `hexes_df` SEM a coluna de score (so hex_id + oferta) -> ausente, sem excecao.
    import h3

    centro = h3.latlng_to_cell(LAT_C, LNG_C, 7)
    so_oferta = pd.DataFrame(
        {"hex_id": list(h3.grid_disk(centro, 5)), "oferta_efetiva_disponivel": 3_000.0}
    )
    sem_col = render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores, width=800, height=600, basemap=False, hexes_df=so_oferta
    )
    assert "socioeconomia" not in sem_col
    # ... mas o `residual` (que tem a coluna) CONTINUA presente -> prova que so a socioeconomia caiu.
    assert "residual" in sem_col
    # (c) `hexes_df` de outra regiao (hex fora do disco) -> ausente.
    longe = pd.DataFrame(
        {
            "hex_id": [h3.latlng_to_cell(-3.119, -60.0217, 7)],  # Manaus, longe de SP
            "score_setor_2022_calibrado": [80.0],
        }
    )
    fora = render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores, width=800, height=600, basemap=False, hexes_df=longe
    )
    assert "socioeconomia" not in fora


def test_socioeconomia_reage_ao_score_setor_2022_calibrado():
    """A cor depende do dado: dois `hexes_df` com `score_setor_2022_calibrado` diferentes por hex
    produzem PNGs de socioeconomia DIFERENTES (trava anti-constante)."""
    import h3

    setores = _setores_um_quadrado()
    centro = h3.latlng_to_cell(LAT_C, LNG_C, 7)
    celulas = list(h3.grid_disk(centro, 5))

    def _render(scores: list[float]) -> bytes:
        hexes = pd.DataFrame({"hex_id": celulas, "score_setor_2022_calibrado": scores})
        mapas = render_mapas_censitarios_combinados(
            LAT_C, LNG_C, setores, width=1000, height=760, basemap=False, hexes_df=hexes
        )
        return mapas["socioeconomia"]

    baixos = _render([float((i % 10) * 3) for i in range(len(celulas))])  # 0-27 (faixas baixas)
    altos = _render([float(90 + (i % 10)) for i in range(len(celulas))])  # 90-99 (faixa alta)
    assert baixos != altos


def test_camadas_censitarias_declara_as_7_chaves():
    # BLK-RELPON-14: eram 8 com a `entorno`; a camada de quadra saiu e a tupla voltou a 7.
    assert set(censo_map.CAMADAS_CENSITARIAS) == _CAMADAS
    assert len(censo_map.CAMADAS_CENSITARIAS) == 7
    assert "entorno" not in censo_map.CAMADAS_CENSITARIAS


def test_rodape_do_png_deriva_do_raio_km_1p5_identico_e_paineis_de_hex_sem_raio(monkeypatch):
    """DT-5: o rodape deriva de `raio_km`. Com 1.5 a string tem de sair IDENTICA ("Raio 1,5 km").

    BLK-RELPON-14: os paineis de hexagono passam `raio_km=None` -> o rodape sai SEM o prefixo de
    raio ("EPSG:3857 - ...") e os titulos perdem o sufixo "- raio 5 km". Os 5 km viraram so
    ENQUADRAMENTO; representa-los contradizia o motor censitario de 1,5 km."""
    textos: list[str] = []
    real = censo_map._draw_text

    def _spy(draw, xy, text, **kwargs):
        textos.append(text)
        return real(draw, xy, text, **kwargs)

    monkeypatch.setattr(censo_map, "_draw_text", _spy)
    render_mapas_censitarios_combinados(
        LAT_C,
        LNG_C,
        _setores_um_quadrado(),
        width=1000,
        height=760,
        basemap=False,
        hexes_df=_hexes_sinteticos(),
    )

    # As 4 camadas de setor (1,5 km) seguem rotulando o raio, byte-a-byte como antes.
    assert "Raio 1,5 km - EPSG:3857 - fundo de ruas offline" in textos
    # Os 2 paineis de hexagono (5 km) usam o rodape SEM prefixo de raio.
    assert "EPSG:3857 - fundo de ruas offline" in textos
    assert not any(t.startswith("Raio 5,0 km") for t in textos)
    # Titulos dos paineis de hexagono SEM o raio (ASCII puro).
    assert "Socioeconomia" in textos
    assert "Residual Fitness" in textos
    assert not any("raio 5 km" in t for t in textos)
    assert "Residual disponivel (alunos)" in textos


def test_faixa_de_cor_do_residual_por_valor_absoluto():
    from motor_expansao.dashboard.constants import OFERTA_DISPONIVEL_ALUNOS_BANDS as BANDS

    # 0 exato cai na 1a faixa ("sem residual"; `val <= upper` captura o zero).
    assert censo_map._color_for_bands(0.0, BANDS) == BANDS[0][2]
    assert censo_map._color_for_bands(1_000.0, BANDS) == BANDS[1][2]
    assert censo_map._color_for_bands(3_000.0, BANDS) == BANDS[3][2]
    assert censo_map._color_for_bands(26_405.0, BANDS) == BANDS[-1][2]  # max nacional medido
    # NaN (hex ausente do df) -> cor de "sem dado", DISTINTA da faixa "sem residual" (2 excecoes,
    # 2 cores, como no BLK-FIX-06-C).
    assert censo_map._color_for_bands(float("nan"), BANDS) == censo_map._FILL_SEM_DADO
    assert censo_map._FILL_SEM_DADO[:3] != BANDS[0][2][:3]


def test_labels_da_regua_de_residual_sem_acento_para_legenda_png():
    """Excecao de RENDER ao §2 (mesma de `test_band_renda_media_domiciliar_sem_acento...`):
    a legenda do choropleth e rasterizada num PNG cujo font (`ImageFont.load_default`) NAO tem
    glifo acentuado -> qualquer acento vira tofu box. Rotulos em ASCII puro."""
    from motor_expansao.dashboard.constants import OFERTA_DISPONIVEL_ALUNOS_BANDS as BANDS

    labels = [label for _upper, label, _color in BANDS]
    assert not any(any(ord(ch) > 127 for ch in s) for s in labels)
    assert len(labels) == 6


def test_formatadores_e_faixa_superior_do_hexagono():
    assert censo_map._format_valor_residual(3_506.0) == "3.506"
    assert censo_map._format_valor_residual(None) == "n/d"
    assert censo_map._format_valor_residual(float("nan")) == "n/d"
    assert censo_map._legenda_valor_hex("Residual", "3.506") == "Residual no hexagono: 3.506"
    # Faixa superior do hex central usa o MESMO valor do lookup por hex_id (nao soma o disco).
    import h3

    centro = h3.latlng_to_cell(LAT_C, LNG_C, 7)
    hexes = pd.DataFrame(
        {"hex_id": [centro], "oferta_efetiva_disponivel": [3_506.0]}
    )
    assert censo_map._residual_hex_central(LAT_C, LNG_C, hexes) == 3_506.0
    assert censo_map._residual_hex_central(LAT_C, LNG_C, pd.DataFrame()) is None


def test_frame_box_metric_puro_reproduz_o_calculo_do_caller():
    """Refactor sem mudanca de comportamento: o helper puro devolve o MESMO retangulo que o
    calculo antes inline (lado menor = raio*(1+margem); aspect da area de mapa)."""
    width, height = 1280, 760
    frame = censo_map._frame_box_metric(1.5, width, height)
    minx, miny, maxx, maxy = frame.bounds
    base_half = 1.5 * 1000.0 * (1.0 + censo_map._MAP_FRAME_MARGIN)
    inner_w, inner_h = censo_map._map_inner_dims(width, height)
    aspect = inner_w / inner_h
    assert maxy - miny == 2 * base_half
    assert abs((maxx - minx) - 2 * base_half * aspect) < 1e-6
    # O frame de 5 km e' proporcionalmente maior pelo mesmo fator de raio.
    frame5 = censo_map._frame_box_metric(censo_map.RAIO_RESIDUAL_DISPLAY_KM, width, height)
    b5 = frame5.bounds
    assert abs((b5[3] - b5[1]) / (maxy - miny) - (5.0 / 1.5)) < 1e-9


def test_raio_de_exibicao_nao_toca_o_raio_do_motor():
    """RD-1 (READ-ONLY M1): o raio de 5 km e' constante de RENDER de `censo_map`; o raio do motor
    censitario segue 1,5 km e NAO vem de `config.py`.

    BLK-RELPON-14: o VALOR nao muda — 5,0 km continua definindo o ENQUADRAMENTO dos paineis de
    hexagono. Encolhe-lo reintroduziria o mosaico chapado de 3 a 5 hexes da DEC-011. O que saiu
    foi a REPRESENTACAO do raio (circulo azul + rotulo), nao o raio."""
    import motor_expansao.config as config
    from motor_expansao.dashboard.censo_point import RAIO_CENSITARIO_DEFAULT_KM

    assert RAIO_CENSITARIO_DEFAULT_KM == 1.5
    assert censo_map.RAIO_RESIDUAL_DISPLAY_KM == 5.0
    assert not hasattr(config, "RAIO_RESIDUAL_DISPLAY_KM")
    assert censo_map._RESIDUAL_GRID_DISK_K == 5


# ── BLK-RELPON-14: raio dos paineis de hexagono deixa de ser REPRESENTADO ──────────────────
# A camada "Imagem do Entorno" (BLK-RELPON-11) foi removida por completo — com ela sairam o
# `_render_camada_entorno`, o `RAIO_ENTORNO_DISPLAY_KM`, os `_ENTORNO_*` e o override
# `zoom_bump` de `_fetch_basemap` (unico chamador que passava valor diferente do global).
# O que fica coberto aqui: nos paineis de 5 km (Socioeconomia/Residual) o circulo azul do raio
# NAO e' mais desenhado e quem identifica o ponto e' a BORDA FINA do hexagono que o contem.


def _conta_pixels_do_circulo(png: bytes) -> int:
    """Pixels 'azuis do circulo' (`_CIRCLE_RGBA`=(0,102,255,235) sobre o canvas claro).

    O mesmo azul agora desenha a borda do hex central nos paineis de 5 km, entao o predicado
    serve tanto para provar a AUSENCIA do circulo quanto a PRESENCA da borda — o que separa os
    dois casos e' a GEOMETRIA dos pixels (ver os testes abaixo), nao a cor.
    """
    arr = np.array(Image.open(BytesIO(png)).convert("RGB"))
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    return int(((b > 200) & (r < 80) & (g < 160)).sum())


def _mascara_azul(png: bytes) -> np.ndarray:
    """Mascara booleana (H x W) dos pixels do azul `_CIRCLE_RGBA` no PNG."""
    arr = np.array(Image.open(BytesIO(png)).convert("RGB"))
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    return (b > 200) & (r < 80) & (g < 160)


def test_paineis_de_hexagono_nao_desenham_o_circulo_do_raio(monkeypatch):
    """(a) `circle_3857=None` nos dois paineis de 5 km -> nenhum circulo azul FECHADO no frame.

    O azul continua no canvas (agora como borda do hex central), entao a prova nao pode ser
    "zero pixel azul": e' geometrica. O circulo do raio ficava INSCRITO no frame (lado menor
    quase inteiro); a borda do hex central ocupa uma fracao pequena em torno do centro. Logo,
    a extensao vertical dos pixels azuis tem de ser MUITO menor que a altura util do mapa.
    A camada `densidade` (1,5 km, que MANTEM o circulo) e' a trava anti-vacuo: la a extensao
    vertical do azul ocupa quase toda a altura util.
    """
    mapas = render_mapas_censitarios_combinados(
        LAT_C,
        LNG_C,
        _setores_um_quadrado(),
        width=1000,
        height=760,
        basemap=False,
        hexes_df=_hexes_sinteticos(),
    )
    _left, top, _right, bottom = censo_map._map_box(1000, 760)
    altura_util = float(bottom - top)

    def _extensao_vertical(png: bytes) -> float:
        ys, _xs = np.nonzero(_mascara_azul(png))
        assert ys.size > 0, "nenhum pixel azul encontrado"
        return float(ys.max() - ys.min() + 1)

    # Trava anti-vacuo: na `densidade` o circulo do raio ocupa quase toda a altura util.
    assert _extensao_vertical(mapas["densidade"]) > 0.8 * altura_util

    # Nos paineis de 5 km sobra so a borda do hex central -> extensao MUITO menor.
    for camada in ("socioeconomia", "residual"):
        assert _extensao_vertical(mapas[camada]) < 0.4 * altura_util, (
            f"a camada `{camada}` ainda parece desenhar o circulo do raio"
        )

    # E o parametro chega mesmo como `None` (prova direta, sem depender do pixel).
    capturado: dict[str, dict] = {}
    original = censo_map._render_camada

    def _spy(*, titulo, **kwargs):
        capturado[titulo] = kwargs
        return original(titulo=titulo, **kwargs)

    monkeypatch.setattr(censo_map, "_render_camada", _spy)
    render_mapas_censitarios_combinados(
        LAT_C, LNG_C, _setores_um_quadrado(), width=1000, height=760, basemap=False,
        hexes_df=_hexes_sinteticos(),
    )
    for titulo in ("Socioeconomia", "Residual Fitness"):
        assert capturado[titulo]["circle_3857"] is None
        assert capturado[titulo]["raio_km"] is None
    # As camadas de 1,5 km seguem com circulo + raio rotulado (nada mudou nelas).
    assert capturado["Densidade populacional"]["circle_3857"] is not None
    assert capturado["Densidade populacional"]["raio_km"] == 1.5


def test_hex_central_e_o_unico_marcado_para_a_borda_de_destaque():
    """(b) `_hex_polygons_3857` devolve como `destaque` o hex que CONTEM o ponto — e so ele."""
    import h3
    from shapely.geometry import Point

    hexes = _hexes_sinteticos()
    to_3857_local = censo_map._transformer(
        censo_map._local_metric_crs(LAT_C, LNG_C), censo_map.CRS_WEB_MERCATOR
    )
    to_3857_wgs = censo_map._transformer(CRS_ORIGEM_CENSO, censo_map.CRS_WEB_MERCATOR)
    frame_3857 = censo_map._project_geometry(
        censo_map._frame_box_metric(censo_map.RAIO_RESIDUAL_DISPLAY_KM, 1000, 760), to_3857_local
    )

    records, values, destaque = censo_map._hex_polygons_3857(
        LAT_C, LNG_C, hexes, frame_3857, to_3857_wgs
    )
    assert len(records) > 1  # ha vizinhos desenhados alem do central
    assert len(values) == len(records)
    assert destaque is not None

    # O destaque CONTEM o ponto central projetado -> e' o hex do `h3.latlng_to_cell(...,7)`.
    ponto_3857 = Point(*to_3857_local.transform(0.0, 0.0))
    assert destaque.buffer(1.0).contains(ponto_3857)
    assert censo_map._hex_id_central(LAT_C, LNG_C) == h3.latlng_to_cell(LAT_C, LNG_C, 7)

    # Exatamente UM dos poligonos desenhados e' o destaque; os demais (nao-centrais) nao sao.
    iguais = [g for g, _idx in records if g.equals(destaque)]
    assert len(iguais) == 1
    nao_centrais = [g for g, _idx in records if not g.equals(destaque)]
    assert nao_centrais, "o disco deveria trazer hexes vizinhos"
    for geom in nao_centrais:
        assert not geom.buffer(-1.0).contains(ponto_3857)

    # Sem hex central no `hexes_df` (so um vizinho) nao ha destaque -- e nao levanta.
    centro = h3.latlng_to_cell(LAT_C, LNG_C, 7)
    vizinhos = [c for c in h3.grid_disk(centro, 1) if c != centro]
    so_vizinho = pd.DataFrame(
        {"hex_id": vizinhos[:1], "oferta_efetiva_disponivel": [1_000.0]}
    )
    _recs, _vals, sem_destaque = censo_map._hex_polygons_3857(
        LAT_C, LNG_C, so_vizinho, frame_3857, to_3857_wgs
    )
    assert sem_destaque is None


def test_borda_de_destaque_desenhada_so_no_poligono_marcado():
    """(b) `_render_camada(destaque_3857=...)` contorna SO o poligono marcado.

    Dois quadrados DISJUNTOS (A marcado, B nao): os pixels azuis tem de ficar todos dentro da
    caixa de A, nenhum dentro da de B. Sem o `destaque_3857` nao sai pixel azul nenhum (o
    `circle_3857=None` deste caminho garante que o azul so pode vir da borda).
    """
    to_3857 = censo_map._transformer(
        censo_map._local_metric_crs(LAT_C, LNG_C), censo_map.CRS_WEB_MERCATOR
    )
    frame = censo_map._project_geometry(
        censo_map._frame_box_metric(censo_map.RAIO_RESIDUAL_DISPLAY_KM, 1000, 760), to_3857
    )
    quadrado_a = censo_map._project_geometry(box(-3_000, -1_500, -1_000, 1_500), to_3857)
    quadrado_b = censo_map._project_geometry(box(1_000, -1_500, 3_000, 1_500), to_3857)

    comum = dict(
        titulo="Residual Fitness",
        legenda_titulo="Residual disponivel (alunos)",
        legenda_entries=censo_map._bands_legend_entries(DENSIDADE_POP_BANDS),
        color_fn=_color_for_densidade,
        source_values=pd.Series([1_000.0, 1_000.0], dtype="float64"),
        sector_records_3857=[(quadrado_a, 0), (quadrado_b, 1)],
        circle_3857=None,
        center_3857=to_3857.transform(0.0, 0.0),
        pins=[],
        ultra_pins=[],
        basemap=None,
        bounds=frame.bounds,
        lat=LAT_C,
        lng=LNG_C,
        raio_km=None,
        n_setores=2,
        width=1000,
        height=760,
    )

    sem_borda = censo_map._render_camada(**comum)
    com_borda = censo_map._render_camada(destaque_3857=quadrado_a, **comum)

    assert _conta_pixels_do_circulo(sem_borda) == 0  # sem circulo e sem destaque -> sem azul
    assert com_borda != sem_borda
    mask = _mascara_azul(com_borda)
    assert int(mask.sum()) > 0

    minx, miny, maxx, maxy = frame.bounds
    left, top, right, bottom = censo_map._map_box(1000, 760)
    inner_w, inner_h = right - left - 24, bottom - top - 24
    scale = min(inner_w / (maxx - minx), inner_h / (maxy - miny))
    offset_x = left + 12 + (inner_w - (maxx - minx) * scale) / 2
    offset_y = top + 12 + (inner_h - (maxy - miny) * scale) / 2

    def _caixa_px(geom):
        gx0, gy0, gx1, gy1 = geom.bounds
        x0 = offset_x + (gx0 - minx) * scale
        x1 = offset_x + (gx1 - minx) * scale
        y0 = offset_y + (maxy - gy1) * scale
        y1 = offset_y + (maxy - gy0) * scale
        return x0, y0, x1, y1

    ax0, ay0, ax1, ay1 = _caixa_px(quadrado_a)
    bx0, by0, bx1, by1 = _caixa_px(quadrado_b)
    ys, xs = np.nonzero(mask)
    folga = censo_map._HEX_CENTRAL_LINEWIDTH + 2
    assert xs.min() >= ax0 - folga and xs.max() <= ax1 + folga
    assert ys.min() >= ay0 - folga and ys.max() <= ay1 + folga
    # Nenhum pixel azul na caixa do poligono NAO marcado.
    na_caixa_b = mask[int(by0) : int(by1) + 1, int(bx0) : int(bx1) + 1]
    assert int(na_caixa_b.sum()) == 0, "um hex nao-central recebeu borda de destaque"


def test_borda_de_destaque_reusa_o_azul_do_circulo_e_e_fina():
    """A borda nova reusa `_CIRCLE_RGBA` (nenhuma paleta destes paineis tem azul) e e' FINA."""
    assert censo_map._HEX_CENTRAL_EDGE_COLOR == censo_map._CIRCLE_RGBA
    assert 1 <= censo_map._HEX_CENTRAL_LINEWIDTH <= 4


def test_simbolos_do_slide_de_quadra_sairam_do_modulo():
    """BLK-RELPON-14: nada da camada removida pode sobrar (constantes orfas viram lixo)."""
    for nome in (
        "_render_camada_entorno",
        "RAIO_ENTORNO_DISPLAY_KM",
        "_ENTORNO_TITULO_PNG",
        "_ENTORNO_VALOR_LINHA",
        "_ENTORNO_LEGENDA_TITULO",
    ):
        assert not hasattr(censo_map, nome), f"simbolo orfao ainda no modulo: {nome}"
    # DIVERGENCIA DELIBERADA vs `main` (reconciliacao de 2026-07-29): la o override `zoom_bump`
    # saiu junto com a camada de quadra, seu unico chamador. AQUI ele FICA — o piloto tem outros
    # DOIS chamadores, e nao sao cosmeticos: sao a mitigacao de tempo/quota de tiles que corrigiu
    # o estouro de timeout do Relatorio Pontual (`d6b9b65`). Remove-lo reintroduziria o defeito.
    # O teste segue ESTRITO: exige o parametro E os dois valores explicitos nas chamadas, para
    # que a mitigacao nao seja apagada em silencio num merge futuro.
    import inspect
    import pathlib

    assert "zoom_bump" in inspect.signature(censo_map._fetch_basemap).parameters
    assert censo_map._BASEMAP_ZOOM_BUMP == 1
    fonte = pathlib.Path(censo_map.__file__).read_text(encoding="utf-8")
    assert "zoom_bump=-1" in fonte, "frame de 5 km perdeu a mitigacao de zoom do piloto"
    assert "zoom_bump=0" in fonte, "frame de 1,5 km perdeu a mitigacao de zoom do piloto"


def test_camadas_existentes_ficam_byte_identicas_com_os_defaults_novos():
    """`circle_3857: BaseGeometry | None` e `destaque_3857=None` sao DEFAULT-PRESERVING.

    Renderiza as camadas antigas duas vezes — uma pelo caminho normal (defaults) e outra com os
    parametros novos passados EXPLICITAMENTE com os valores default — e exige igualdade
    byte-a-byte. (Preferido a hashes literais: nao envelhece com mudancas legitimas de fonte.)
    """
    from shapely.geometry import Point

    setores = _setores_um_quadrado()
    mapas = render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores, width=1000, height=760, basemap=False,
        hexes_df=_hexes_sinteticos(),
    )
    assert set(mapas) == _CAMADAS

    # Prova direta sobre `_render_camada`: com um circulo real + `destaque_3857=None`
    # explicito, a saida bate byte-a-byte com a chamada que omite os dois parametros.
    to_3857 = censo_map._transformer(
        censo_map._local_metric_crs(LAT_C, LNG_C), censo_map.CRS_WEB_MERCATOR
    )
    circulo = censo_map._project_geometry(Point(0, 0).buffer(1_500.0, quad_segs=96), to_3857)
    frame = censo_map._project_geometry(
        censo_map._frame_box_metric(1.5, 1000, 760), to_3857
    )
    comum = dict(
        titulo="Densidade populacional",
        legenda_titulo="Densidade (hab/km2)",
        legenda_entries=censo_map._bands_legend_entries(DENSIDADE_POP_BANDS),
        color_fn=_color_for_densidade,
        source_values=pd.Series([1_000.0], dtype="float64"),
        sector_records_3857=[],
        center_3857=to_3857.transform(0.0, 0.0),
        pins=[],
        ultra_pins=[],
        basemap=None,
        bounds=frame.bounds,
        lat=LAT_C,
        lng=LNG_C,
        raio_km=1.5,
        n_setores=0,
        width=1000,
        height=760,
    )
    implicito = censo_map._render_camada(circle_3857=circulo, **comum)
    explicito = censo_map._render_camada(circle_3857=circulo, destaque_3857=None, **comum)
    assert implicito == explicito
# ── Overlay de RÓTULOS por cima do choropleth (mapa de calor legível) ────────────────────
# Sem rede: monkeypatch de `_fetch_basemap`/`_fetch_labels`. A base é cinza (sem magenta) e o
# tileset de rótulos é magenta OPACO; se o magenta aparece na camada de choropleth, os nomes
# foram compostos POR CIMA da cor — a leitura que o formato legível exige (nomes de rua/bairro
# sobre o heat, não soterrados). `_fetch_labels` recebe (bounds_3857, width) e devolve
# (Image RGBA, extent) no mesmo contrato do basemap.

_ROTULO_MAGENTA = (255, 0, 255)


def _fake_basemap_cinza(bounds, _width, *, zoom_bump=None):
    # `zoom_bump` e' keyword-only no `_fetch_basemap` real desde o BLK-RELPON-11 (a camada
    # `entorno` passa -1 p/ forcar z18). O fake precisa aceita-lo: `render_mapas_censitarios_
    # combinados` monta TODAS as camadas, inclusive a de quadra, e sem isso o patch estoura
    # TypeError antes de chegar no que estes testes medem.
    minx, miny, maxx, maxy = bounds
    return Image.new("RGBA", (256, 256), (235, 235, 235, 255)), (minx, maxx, miny, maxy)


def _fake_labels_magenta(bounds, _width):
    minx, miny, maxx, maxy = bounds
    return Image.new("RGBA", (256, 256), (*_ROTULO_MAGENTA, 255)), (minx, maxx, miny, maxy)


def _setores_dois_faixas() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _sector_record("355030801000001", box(-700, -700, 0, 700), pop=800, score=40),
            _sector_record("355030801000002", box(0, -700, 700, 700), pop=1400, score=85),
        ]
    )


def test_labels_overlay_compoe_rotulos_por_cima_do_choropleth(monkeypatch):
    monkeypatch.setattr(censo_map, "_fetch_basemap", _fake_basemap_cinza)
    monkeypatch.setattr(censo_map, "_fetch_labels", _fake_labels_magenta)
    mapas = render_mapas_censitarios_combinados(
        LAT_C, LNG_C, _setores_dois_faixas(), width=800, height=600, basemap=True
    )
    dens_cores = {c[:3] for _count, c in _all_colors(mapas["densidade"])}
    assert _ROTULO_MAGENTA in dens_cores  # rótulos compostos POR CIMA da cor
    # a camada só-pins (concorrentes) NÃO recebe overlay de rótulos (mantém o basemap nativo)
    conc_cores = {c[:3] for _count, c in _all_colors(mapas["concorrentes"])}
    assert _ROTULO_MAGENTA not in conc_cores


def test_labels_overlay_desligado_nao_compoe_rotulos(monkeypatch):
    monkeypatch.setattr(censo_map, "_fetch_basemap", _fake_basemap_cinza)
    monkeypatch.setattr(censo_map, "_fetch_labels", _fake_labels_magenta)
    mapas = render_mapas_censitarios_combinados(
        LAT_C, LNG_C, _setores_dois_faixas(), width=800, height=600,
        basemap=True, labels_overlay=False,
    )
    dens_cores = {c[:3] for _count, c in _all_colors(mapas["densidade"])}
    assert _ROTULO_MAGENTA not in dens_cores


# ── BLK-BASEMAP-02: basemap self-host (OpenMapTiles) via env var ────────────────────────────
# A troca do provedor e' resolvida em runtime por `_basemap_source`, NAO por constante fixa: sem
# `API_BASEMAP_TILES_URL` o caminho e' byte-identico ao Voyager de sempre (o que CI/dev exercitam)
# e com ela o `contextily` recebe o template de URL cru do tileserver proprio. Emenda a DEC-004.


class _FakeCartoDB:
    Voyager = "provider-voyager-sentinela"


class _FakeCtx:
    providers = type("_P", (), {"CartoDB": _FakeCartoDB})()


def test_basemap_source_usa_voyager_sem_env(monkeypatch):
    monkeypatch.delenv(censo_map._BASEMAP_TILES_URL_ENV, raising=False)
    assert censo_map._basemap_source(_FakeCtx()) == "provider-voyager-sentinela"


def test_basemap_source_usa_self_host_com_env(monkeypatch):
    url = "http://motor_expansao_tileserver:8080/styles/ultra-maptiler/{z}/{x}/{y}@2x.png"
    monkeypatch.setenv(censo_map._BASEMAP_TILES_URL_ENV, url)
    assert censo_map._basemap_source(_FakeCtx()) == url


def test_basemap_source_ignora_env_vazia(monkeypatch):
    # Env var presente porem VAZIA (caso classico de `.env` com `API_BASEMAP_TILES_URL=`) nao pode
    # virar uma URL vazia entregue ao contextily -> cairia em erro e o PDF sairia sem ruas.
    monkeypatch.setenv(censo_map._BASEMAP_TILES_URL_ENV, "")
    assert censo_map._basemap_source(_FakeCtx()) == "provider-voyager-sentinela"


def test_atribuicao_do_pontual_credita_osm_e_carto_nos_dois_modos(monkeypatch):
    # No Pontual o credito NAO muda com o self-host: o dado do tileserver e' OpenStreetMap e os
    # ROTULOS continuam vindo do CARTO (`_LABELS_TILE_URL`, BLK-RELPON-07) -> os dois sao devidos.
    assert censo_map._ATRIBUICAO_TILES == "(c) OpenStreetMap, (c) CARTO"
    assert "cartocdn.com" in censo_map._LABELS_TILE_URL


# ── BLK-BASEMAP-03 (emenda DEC-004): grade de tiles e cache do overlay de rótulos ───────────
# O achado MÉDIA da revisão do PR #154 era exatamente isto: os 2 testes de overlay acima fazem
# monkeypatch de `_fetch_labels` INTEIRA, então a aritmética Web Mercator -> índice de tile e o
# caminho de rede/cache nunca eram exercitados. Aqui eles são, sem rede.


def test_labels_grid_cobre_o_bbox_pedido():
    """A faixa de tiles tem de CONTER o bbox — e o extent devolvido, idem (grade é discreta)."""
    bounds = (-5_200_000.0, -2_800_000.0, -5_195_000.0, -2_795_000.0)
    zoom, tx0, tx1, ty0, ty1, tile_m = censo_map._labels_grid(bounds, 1000)

    assert tx0 <= tx1 and ty0 <= ty1
    assert tile_m == censo_map._EARTH_M / (2**zoom)

    ex_minx, ex_maxx, ex_miny, ex_maxy = censo_map._labels_extent(tx0, tx1, ty0, ty1, tile_m)
    assert ex_minx <= bounds[0] and ex_miny <= bounds[1]
    assert ex_maxx >= bounds[2] and ex_maxy >= bounds[3]


def test_labels_grid_y_cresce_para_o_sul():
    """Convenção XYZ: `y` cresce para o SUL. Um bbox mais ao norte tem de ter `ty` MENOR."""
    largura = 4_000.0
    norte = (-5_200_000.0, -2_000_000.0, -5_200_000.0 + largura, -2_000_000.0 + largura)
    sul = (-5_200_000.0, -3_000_000.0, -5_200_000.0 + largura, -3_000_000.0 + largura)

    _z_n, _tx0n, _tx1n, ty0_norte, _ty1n, _tn = censo_map._labels_grid(norte, 1000)
    _z_s, _tx0s, _tx1s, ty0_sul, _ty1s, _ts = censo_map._labels_grid(sul, 1000)
    assert ty0_norte < ty0_sul


def test_labels_grid_respeita_o_teto_de_zoom_19():
    """Bbox minúsculo pediria zoom altíssimo; o teto é 19, igual ao do `_fetch_basemap`."""
    zoom, *_ = censo_map._labels_grid((-5_200_000.0, -2_800_000.0, -5_199_999.0, -2_799_999.0), 1000)
    assert zoom == 19


def test_labels_extent_e_o_retangulo_dos_tiles_inteiros():
    """Extent = borda dos tiles inteiros: largura = (tx1-tx0+1) tiles, altura = (ty1-ty0+1)."""
    tile_m = 1000.0
    ex_minx, ex_maxx, ex_miny, ex_maxy = censo_map._labels_extent(10, 12, 20, 21, tile_m)
    assert abs((ex_maxx - ex_minx) - 3 * tile_m) < 1e-6
    assert abs((ex_maxy - ex_miny) - 2 * tile_m) < 1e-6


def _png_bytes(cor) -> bytes:
    buf = BytesIO()
    Image.new("RGBA", (512, 512), cor).save(buf, format="PNG")
    return buf.getvalue()


def test_labels_tile_grava_no_cache_e_reusa_sem_segunda_ida_a_rede(monkeypatch, tmp_path):
    """DEC-004 mitigação (a): o 2º pedido do MESMO tile sai do disco, sem tocar a rede.

    Era a dívida ALTA do PR #154: `_fetch_basemap` herda cache do `ctx.set_cache_dir()`, mas o
    overlay usava `urllib` cru e rebaixava o mosaico inteiro a cada PDF.
    """
    monkeypatch.setattr(censo_map, "_LABELS_CACHE_DIR", tmp_path / "labels")
    idas = []

    class _Resp:
        def __enter__(self_inner):
            return self_inner

        def __exit__(self_inner, *_a):
            return False

        def read(self_inner):
            return _png_bytes((10, 20, 30, 255))

    def _fake_urlopen(_req, timeout=None):
        idas.append(1)
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    primeiro = censo_map._labels_tile(17, 40_000, 60_000)
    assert len(idas) == 1
    assert (tmp_path / "labels" / "17_40000_60000.png").is_file()

    segundo = censo_map._labels_tile(17, 40_000, 60_000)
    assert len(idas) == 1, "o 2o pedido foi a rede — o cache nao pegou"
    assert primeiro.getpixel((0, 0)) == segundo.getpixel((0, 0))


def test_labels_tile_rebaixa_quando_o_cache_esta_corrompido(monkeypatch, tmp_path):
    """PNG truncado no disco não pode derrubar o render — rebaixa como se não existisse."""
    cache = tmp_path / "labels"
    cache.mkdir(parents=True)
    (cache / "17_1_2.png").write_bytes(b"nao sou um png")
    monkeypatch.setattr(censo_map, "_LABELS_CACHE_DIR", cache)

    class _Resp:
        def __enter__(self_inner):
            return self_inner

        def __exit__(self_inner, *_a):
            return False

        def read(self_inner):
            return _png_bytes((99, 0, 0, 255))

    monkeypatch.setattr("urllib.request.urlopen", lambda _r, timeout=None: _Resp())
    assert censo_map._labels_tile(17, 1, 2).getpixel((0, 0))[0] == 99


def test_labels_tile_nao_quebra_quando_o_cache_nao_e_gravavel(monkeypatch, tmp_path):
    """Cache é otimização: falha de ESCRITA é engolida e o tile sai da rede normalmente."""
    monkeypatch.setattr(censo_map, "_LABELS_CACHE_DIR", tmp_path / "labels")

    class _Resp:
        def __enter__(self_inner):
            return self_inner

        def __exit__(self_inner, *_a):
            return False

        def read(self_inner):
            return _png_bytes((7, 7, 7, 255))

    monkeypatch.setattr("urllib.request.urlopen", lambda _r, timeout=None: _Resp())

    def _mkdir_explode(*_a, **_k):
        raise OSError("disco read-only")

    monkeypatch.setattr(censo_map.Path, "mkdir", _mkdir_explode)
    assert censo_map._labels_tile(17, 5, 5).getpixel((0, 0))[0] == 7


def test_fetch_labels_devolve_none_quando_a_rede_falha(monkeypatch, tmp_path):
    """Contrato de degradação graciosa: sem rede -> None -> o mapa sai SEM nomes, sem exceção."""
    monkeypatch.setattr(censo_map, "_LABELS_CACHE_DIR", tmp_path / "labels")

    def _explode(*_a, **_k):
        raise OSError("sem rede")

    monkeypatch.setattr(censo_map, "_labels_grid", _explode)
    assert censo_map._fetch_labels((-5_200_000.0, -2_800_000.0, -5_195_000.0, -2_795_000.0), 1000) is None


def test_fetch_labels_tolera_tile_faltando(monkeypatch, tmp_path):
    """Um tile 404 no meio do mosaico não invalida os outros — o resto compõe normal."""
    monkeypatch.setattr(censo_map, "_LABELS_CACHE_DIR", tmp_path / "labels")
    chamadas = {"n": 0}

    def _tile_intermitente(_zoom, _tx, _ty):
        chamadas["n"] += 1
        if chamadas["n"] % 2 == 0:
            raise OSError("404")
        return Image.new("RGBA", (512, 512), (0, 255, 0, 255))

    monkeypatch.setattr(censo_map, "_labels_tile", _tile_intermitente)
    out = censo_map._fetch_labels((-5_200_000.0, -2_800_000.0, -5_150_000.0, -2_750_000.0), 1000)

    assert out is not None
    canvas, _extent = out
    arr = np.asarray(canvas)
    assert bool(((arr[:, :, 1] == 255) & (arr[:, :, 3] == 255)).any()), (
        "nenhum tile bom entrou no mosaico"
    )


def test_fetch_labels_devolve_none_quando_nenhum_tile_entra(monkeypatch, tmp_path):
    """Rede 100% fora -> None, NAO um mosaico transparente.

    Regressão real do BLK-RELPON-07: o `except Exception: continue` por tile engolia todas as
    falhas e a função devolvia canvas vazio + extent, contrariando o próprio docstring ("QUALQUER
    falha -> None"). O chamador então compunha uma camada inteiramente transparente achando que
    tinha rótulos. Mesmo critério da DEC-018 para a foto de satélite.
    """
    monkeypatch.setattr(censo_map, "_LABELS_CACHE_DIR", tmp_path / "labels")

    def _todo_tile_falha(_zoom, _tx, _ty):
        raise OSError("CDN fora")

    monkeypatch.setattr(censo_map, "_labels_tile", _todo_tile_falha)
    bounds = (-5_200_000.0, -2_800_000.0, -5_195_000.0, -2_795_000.0)
    assert censo_map._fetch_labels(bounds, 1000) is None


def test_labels_timeout_por_tile_limita_o_pior_caso():
    """Teto por tile explícito: 8 s. Documenta o pior caso do mosaico contra CDN em blackhole."""
    assert censo_map._LABELS_TIMEOUT_S <= 8
