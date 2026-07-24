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
# BLK-RELPON-11: `entorno` (mapa de quadra, raio de EXIBICAO ~0,14 km) e' INCONDICIONAL — nao
# depende de `hexes_df`, de setores nem de tiles; por isso entra no set "sem hexes".
_CAMADAS_SEM_HEXES = {
    "densidade",
    "renda",
    "score",
    "renda_domiciliar",
    "concorrentes",
    "entorno",
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
        assert image.size == (900, 680)
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

    assert set(mapas) == _CAMADAS_SEM_HEXES
    for png in mapas.values():
        image = Image.open(BytesIO(png))
        assert image.format == "PNG"
        assert image.size == (720, 520)


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
    assert 'titulo="Concorrentes e Ultra"' in combinador_src


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
    assert capturado["Concorrentes e Ultra"].get("valor_ponto") is None
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
    assert capturado["Concorrentes e Ultra"].get("valor_ponto") is None


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
    assert capturado["Concorrentes e Ultra"].get("valor_ponto") is None


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
    "Socioeconomia - raio 5 km" + o rodape "Raio 5,0 km" (ambos ASCII)."""
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
    assert "Socioeconomia - raio 5 km" in textos
    assert "Raio 5,0 km - EPSG:3857 - fundo de ruas offline" in textos
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


def test_camadas_censitarias_declara_as_8_chaves():
    assert set(censo_map.CAMADAS_CENSITARIAS) == _CAMADAS
    assert len(censo_map.CAMADAS_CENSITARIAS) == 8


def test_rodape_do_png_deriva_do_raio_km_1p5_identico_e_5p0_novo(monkeypatch):
    """DT-5: o rodape passou a derivar de `raio_km`. Com 1.5 a string tem de sair IDENTICA
    ("Raio 1,5 km"); a camada de residual (5 km) sai "Raio 5,0 km" — duas escalas rotuladas."""
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

    assert "Raio 1,5 km - EPSG:3857 - fundo de ruas offline" in textos
    assert "Raio 5,0 km - EPSG:3857 - fundo de ruas offline" in textos
    # Titulos com o raio rotulado dentro do PNG (ASCII puro).
    assert "Socioeconomia - raio 5 km" in textos
    assert "Residual Fitness - raio 5 km" in textos
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
    censitario segue 1,5 km e NAO vem de `config.py`."""
    import motor_expansao.config as config
    from motor_expansao.dashboard.censo_point import RAIO_CENSITARIO_DEFAULT_KM

    assert RAIO_CENSITARIO_DEFAULT_KM == 1.5
    assert censo_map.RAIO_RESIDUAL_DISPLAY_KM == 5.0
    assert not hasattr(config, "RAIO_RESIDUAL_DISPLAY_KM")
    assert censo_map._RESIDUAL_GRID_DISK_K == 5


# ── BLK-RELPON-11: camada "Imagem do Entorno" (mapa de quadra, raio de EXIBICAO ~0,14 km) ──


class _FakeCartoDB:
    Voyager = "fake-voyager-provider"


class _FakeProviders:
    CartoDB = _FakeCartoDB()


class _FakeContextily:
    """Stub de `contextily` que CAPTURA o `zoom` pedido, sem tocar a rede.

    Devolve um mosaico 256x256 preto e um extent unitario — suficiente para o pipeline de
    composicao de `_render_camada` rodar; o teste so olha o `zoom`.
    """

    def __init__(self) -> None:
        self.zooms: list[int] = []
        self.providers = _FakeProviders()

    def set_cache_dir(self, path):  # noqa: D401 - stub
        return None

    def bounds2img(self, minx, miny, maxx, maxy, *, zoom, source, ll=False):
        self.zooms.append(int(zoom))
        return np.zeros((256, 256, 3), dtype=np.uint8), (0.0, 1.0, 0.0, 1.0)


def _instalar_contextily_falso(monkeypatch, tmp_path) -> _FakeContextily:
    import sys

    fake = _FakeContextily()
    monkeypatch.setitem(sys.modules, "contextily", fake)
    # Cache num tmp_path: o teste nao pode criar `data/cache/basemap_tiles/` no repo.
    monkeypatch.setattr(censo_map, "_BASEMAP_CACHE_DIR", tmp_path)
    return fake


def test_camada_entorno_presente_e_png_valido():
    """T1: a camada `entorno` e INCONDICIONAL (sem `hexes_df`, sem tiles) e sai PNG valido."""
    mapas = render_mapas_censitarios_combinados(
        LAT_C,
        LNG_C,
        _setores_um_quadrado(),
        width=1000,
        height=760,
        basemap=False,
    )

    assert "entorno" in mapas
    png = mapas["entorno"]
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    image = Image.open(BytesIO(png))
    assert image.size == (1000, 760)


def test_camada_entorno_nao_desenha_pins_e_e_imune_a_concorrentes():
    """T2: sem pins de concorrente/Ultra (a ~1,82 px/m um pin de 30 px cobre ~16,5 m de solo).

    Teste DIFERENCIAL byte-a-byte, com a MESMA trava anti-vacuo do residual. Este teste NAO passa
    `hexes_df`, entao a `socioeconomia` (BLK-RELPON-13: hex a 5 km) estaria AUSENTE; a sentinela
    passa a ser `score` (setor a 1,5 km, com pins): DEVE reagir aos pontos, senao remover os pins
    de todas as camadas passaria trivialmente.
    """
    setores = _setores_um_quadrado()
    competitors = pd.DataFrame(
        [{"nome_unidade": "Concorrente", "lat": LAT_C, "lng": LNG_C + 0.0004, "rede": "smart_fit"}]
    )
    ultra = pd.DataFrame([{"nome_unidade": "Ultra", "lat": LAT_C + 0.0003, "lng": LNG_C}])

    def _render(com_pontos: bool):
        return render_mapas_censitarios_combinados(
            LAT_C, LNG_C, setores, width=1000, height=760, basemap=False,
            competitors_df=competitors if com_pontos else None,
            ultra_df=ultra if com_pontos else None,
        )

    com, sem = _render(True), _render(False)

    assert com["entorno"] == sem["entorno"], (
        "a camada `entorno` mudou ao receber concorrentes/Ultra -- ela nao pode desenhar pins"
    )
    assert b"Pins: Ultra e concorrentes" not in com["entorno"]
    # Trava anti-vacuo: sem `hexes_df` a `socioeconomia` esta ausente; `score` (setor a 1,5 km)
    # CONTINUA com pins e serve de sentinela.
    assert com["score"] != sem["score"], (
        "a camada `score` deveria continuar desenhando pins"
    )


def test_render_camada_entorno_textos_ascii_e_rodape_sem_raio(monkeypatch):
    """T3: textos da camada nova em ASCII puro (excecao de RENDER ao §2) e rodape SEM "Raio ".

    Chama `_render_camada_entorno` DIRETAMENTE para os textos capturados pertencerem so a esta
    camada (o rodape automatico sairia "Raio 0,1 km" a 0,14 km — enganoso vs o motor de 1,5 km).
    """
    textos: list[str] = []
    real = censo_map._draw_text

    def _spy(draw, xy, text, **kwargs):
        textos.append(text)
        return real(draw, xy, text, **kwargs)

    monkeypatch.setattr(censo_map, "_draw_text", _spy)
    png = censo_map._render_camada_entorno(
        LAT_C, LNG_C, basemap=False, width=1000, height=760
    )
    assert png.startswith(b"\x89PNG\r\n\x1a\n")

    for esperado in (
        "Entorno - mapa de quadra",
        "Ruas e quadras do entorno",
        "Entorno imediato do ponto",
        "Escala de quadra - EPSG:3857 - fundo de ruas offline",
        "Ponto central",
    ):
        assert esperado in textos, f"texto ausente no PNG: {esperado!r}"

    assert "Pins: Ultra e concorrentes" not in textos
    assert not any(t.startswith("Raio ") for t in textos), (
        f"nenhum texto pode prometer raio de analise nesta escala: {textos}"
    )
    # Excecao de RENDER do §2: o font do PNG nao tem glifo acentuado -> ASCII puro.
    assert all(ord(c) < 128 for t in textos for c in t)


def _conta_pixels_do_circulo(png: bytes) -> int:
    """Pixels 'azuis do circulo' (`_CIRCLE_RGBA`=(0,102,255,235) sobre o canvas claro)."""
    arr = np.array(Image.open(BytesIO(png)).convert("RGB"))
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    return int(((b > 200) & (r < 80) & (g < 160)).sum())


def test_camada_entorno_nao_desenha_o_circulo_do_raio():
    """T4: `circle_3857=None` -> zero pixel do circulo azul; a camada `densidade` prova que o
    predicado DETECTA o circulo onde ele existe (sem isso o assert de zero seria vacuo)."""
    mapas = render_mapas_censitarios_combinados(
        LAT_C, LNG_C, _setores_um_quadrado(), width=1000, height=760, basemap=False
    )

    assert _conta_pixels_do_circulo(mapas["entorno"]) == 0
    assert _conta_pixels_do_circulo(mapas["densidade"]) > 0


def test_fetch_basemap_aceita_zoom_bump_local_sem_mexer_na_constante(monkeypatch, tmp_path):
    """T5: `zoom_bump` sobrescreve o bump SO na chamada; a constante global fica `1`."""
    fake = _instalar_contextily_falso(monkeypatch, tmp_path)

    # bbox com span 3857 ~3.759 m e width=1000 -> `_zoom_for_bounds` = 16.
    bounds = (-5_000_000.0, -3_000_000.0, -5_000_000.0 + 3_759.0, -3_000_000.0 + 3_759.0)
    assert censo_map._zoom_for_bounds(bounds[0], bounds[2], 1000) == 16

    censo_map._fetch_basemap(bounds, 1000)
    censo_map._fetch_basemap(bounds, 1000, zoom_bump=0)
    censo_map._fetch_basemap(bounds, 1000, zoom_bump=-1)

    assert fake.zooms == [17, 16, 15]
    assert censo_map._BASEMAP_ZOOM_BUMP == 1


def test_entorno_pede_z18_em_todo_o_brasil(monkeypatch, tmp_path):
    """T6: o frame de quadra pede z18 em toda a faixa de latitude do Brasil e nos 2 canvases
    usados pelos callers de PDF.

    z18 e' ESCOLHA DE PRODUTO do gate visual (Vinicius, 2026-07-22), nao consequencia da
    geometria: o frame resolveria z19 sozinho (dois clampes em 19), e e' o `zoom_bump=-1` de
    `_render_camada_entorno` que desce um nivel. Motivo: o render tem ~1,82 px/m contra
    3,65 px/m do tile z19 -> em z19 o rotulo de rua sai a 2,6-3,3 pt no PDF (ilegivel, e a
    variante CLASSICA que producao entrega e a pior); em z18 dobra. Se este teste quebrar,
    e' porque alguem mexeu no zoom da pagina — confirmar com o gate antes de atualizar.
    """
    fake = _instalar_contextily_falso(monkeypatch, tmp_path)

    pontos = [(-23.55, -46.63), (-33.7, -53.4), (2.82, -60.67)]
    for width, height in ((1000, 760), (1280, 760)):
        for lat, lng in pontos:
            censo_map._render_camada_entorno(
                lat, lng, basemap=True, width=width, height=height
            )

    assert fake.zooms == [18] * 6, fake.zooms


def test_raio_entorno_e_constante_de_render_dentro_da_janela():
    """T7: `RAIO_ENTORNO_DISPLAY_KM` e constante de RENDER (nunca `config.py`) e o lado CURTO do
    frame fica na janela util de 250-400 m, alvo ~300 m. Motor censitario INTOCADO."""
    import motor_expansao.config as config
    from motor_expansao.dashboard.censo_point import RAIO_CENSITARIO_DEFAULT_KM

    assert censo_map.RAIO_ENTORNO_DISPLAY_KM == 0.14
    lado = 2.0 * censo_map.RAIO_ENTORNO_DISPLAY_KM * 1000.0 * (1.0 + censo_map._MAP_FRAME_MARGIN)
    assert 250.0 <= lado <= 400.0
    assert abs(lado - 300.0) <= 10.0
    assert not hasattr(config, "RAIO_ENTORNO_DISPLAY_KM")
    # O raio novo e' de EXIBICAO: o motor censitario segue em 1,5 km.
    assert RAIO_CENSITARIO_DEFAULT_KM == 1.5

    # Invariante do lado CURTO em relacao ao canvas (a resolucao efetiva nao muda com a largura).
    for width, height in ((1000, 760), (1280, 760)):
        minx, miny, maxx, maxy = censo_map._frame_box_metric(
            censo_map.RAIO_ENTORNO_DISPLAY_KM, width, height
        ).bounds
        assert abs(min(maxx - minx, maxy - miny) - lado) < 1e-6


def test_textos_do_entorno_cabem_sem_invadir_a_coluna_da_legenda():
    """T8: titulo/linha de dado nao invadem a coluna da legenda; o subtitulo cabe na coluna."""
    image = Image.new("RGBA", (1000, 760))
    draw = ImageDraw.Draw(image, "RGBA")
    largura_util = 1000 - censo_map._LEGEND_COL_W

    titulo_w = censo_map._text_width(
        draw, censo_map._ENTORNO_TITULO_PNG, censo_map._font(censo_map._FS_TITULO)
    )
    assert 28 + titulo_w <= largura_util

    valor_w = censo_map._text_width(
        draw, censo_map._ENTORNO_VALOR_LINHA, censo_map._font(censo_map._FS_VALOR_RAIO)
    )
    assert 28 + valor_w <= largura_util

    legenda_w = censo_map._text_width(
        draw, censo_map._ENTORNO_LEGENDA_TITULO, censo_map._font(censo_map._FS_LEGENDA_SUBTITULO)
    )
    assert legenda_w <= censo_map._LEGEND_COL_W - 10


def test_camadas_existentes_ficam_byte_identicas_com_os_defaults_novos():
    """T9: `circle_3857: BaseGeometry | None` e `rotulo_escala=None` sao DEFAULT-PRESERVING.

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

    # Prova direta sobre `_render_camada`: com um circulo real + `rotulo_escala=None`
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
    explicito = censo_map._render_camada(circle_3857=circulo, rotulo_escala=None, **comum)
    assert implicito == explicito
