from __future__ import annotations

from io import BytesIO

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw
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
from motor_expansao.dashboard.constants import DENSIDADE_POP_BANDS

LAT_C = -23.55
LNG_C = -46.63

# BLK-RELPON-10: alem das 4 camadas de 1,5 km + concorrentes, a orquestradora produz
# `socioeconomia` (slide-hero, mesmo choropleth de score a 1,5 km), INCONDICIONAL. `residual`
# e' CONDICIONAL ao `hexes_df` (nao passado aqui) -> ausente do set offline.
# BLK-RELPON-14: a camada `entorno` (mapa de quadra do BLK-RELPON-11) foi REMOVIDA por completo,
# entao o set offline voltou a 6 chaves e a tupla canonica a 7.
_CAMADAS = {
    "densidade",
    "renda",
    "score",
    "renda_domiciliar",
    "socioeconomia",
    "concorrentes",
}


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

    assert set(mapas) == _CAMADAS
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

    assert set(mapas) == _CAMADAS
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


def test_mapa_censitario_pin_com_logo_concorrente_e_ultra():
    setores = pd.DataFrame(
        [_sector_record("355030801000001", box(-700, -700, 700, 700), pop=1000, score=60)]
    )
    competitors = pd.DataFrame(
        [{"nome_unidade": "Smart Fit", "lat": LAT_C, "lng": LNG_C + 0.004, "rede": "smart_fit"}]
    )
    ultra = pd.DataFrame([{"nome_unidade": "Ultra", "lat": LAT_C, "lng": LNG_C - 0.004}])

    mapas = render_mapas_censitarios_combinados(
        LAT_C,
        LNG_C,
        setores,
        competitors_df=competitors,
        ultra_df=ultra,
        width=800,
        height=600,
        basemap=False,
    )
    image = Image.open(BytesIO(mapas["concorrentes"])).convert("RGB")
    # O pin Ultra usa a cor da marca (#C8001E -> ~(200,0,30)); deve haver pixels avermelhados
    # fora do choropleth (o pin e desenhado por _render_pin_tile).
    reds = sum(
        1
        for _count, (r, g, b) in image.getcolors(maxcolors=1_000_000) or []
        if r > 150 and g < 80 and b < 80
    )
    assert reds > 0


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
    assert set(mapas) == _CAMADAS
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
        RENDA_MEDIA_DOMICILIAR_BANDS,
        RENDA_PER_CAPITA_BANDS,
    )

    image = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(image, "RGBA")
    font = censo_map._font(censo_map._FS_LEGENDA_CORPO)
    orcamento = censo_map._LEGEND_COL_W - 78
    # As duas camadas de renda usam o MESMO formato compacto de rotulo (per capita e domiciliar);
    # o rotulo mais longo de cada uma deve caber na coluna estreita da legenda.
    for bands in (RENDA_PER_CAPITA_BANDS, RENDA_MEDIA_DOMICILIAR_BANDS):
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


# ── BLK-RELPON-14: raio do painel de hexagono deixa de ser REPRESENTADO ────────────────────
# A camada "Imagem do Entorno" (BLK-RELPON-11) foi removida por completo — com ela sairam o
# `_render_camada_entorno`, o `RAIO_ENTORNO_DISPLAY_KM` e os `_ENTORNO_*`.
# O que fica coberto aqui: no painel de 5 km (Residual Fitness) o circulo azul do raio NAO e'
# mais desenhado nem rotulado, e quem identifica o ponto e' a BORDA FINA do hexagono que o
# contem. As camadas de 1,5 km (inclusive a `socioeconomia` desta branch) seguem INTOCADAS.


def _hexes_sinteticos(lat: float = LAT_C, lng: float = LNG_C, k: int = 5) -> pd.DataFrame:
    """Disco H3 res-7 em torno do ponto, com `oferta_efetiva_disponivel` variando por faixa."""
    import h3

    centro = h3.latlng_to_cell(lat, lng, 7)
    celulas = list(h3.grid_disk(centro, k))
    # Valores que cruzam TODAS as 6 faixas (0 / 1.250 / 2.500 / 5.000 / 10.000 / inf).
    valores = [float(i % 6) * 2_600.0 for i in range(len(celulas))]
    return pd.DataFrame({"hex_id": celulas, "oferta_efetiva_disponivel": valores})


def _setores_um_quadrado() -> pd.DataFrame:
    return pd.DataFrame(
        [_sector_record("355030801000001", box(-700, -700, 700, 700), pop=1000, score=70)]
    )


def _mascara_azul(png: bytes) -> np.ndarray:
    """Mascara booleana (H x W) dos pixels do azul `_CIRCLE_RGBA` no PNG.

    O mesmo azul agora desenha a borda do hex central no painel de 5 km, entao o predicado serve
    tanto para provar a AUSENCIA do circulo quanto a PRESENCA da borda — o que separa os dois
    casos e' a GEOMETRIA dos pixels (ver os testes abaixo), nao a cor.
    """
    arr = np.array(Image.open(BytesIO(png)).convert("RGB"))
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    return (b > 200) & (r < 80) & (g < 160)


def _conta_pixels_do_circulo(png: bytes) -> int:
    return int(_mascara_azul(png).sum())


def test_camadas_censitarias_declara_as_7_chaves():
    # BLK-RELPON-14: eram 8 com a `entorno`; a camada de quadra saiu e a tupla voltou a 7.
    assert len(censo_map.CAMADAS_CENSITARIAS) == 7
    assert "entorno" not in censo_map.CAMADAS_CENSITARIAS
    assert _CAMADAS | {"residual"} == set(censo_map.CAMADAS_CENSITARIAS)


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


def test_raio_de_exibicao_nao_toca_o_raio_do_motor():
    """RD-1 (READ-ONLY M1): o raio de 5 km e' constante de RENDER de `censo_map`; o raio do motor
    censitario segue 1,5 km e NAO vem de `config.py`.

    BLK-RELPON-14: o VALOR nao muda — 5,0 km continua definindo o ENQUADRAMENTO do painel de
    hexagono. Encolhe-lo reintroduziria o mosaico chapado de 3 a 5 hexes da DEC-011. O que saiu
    foi a REPRESENTACAO do raio (circulo azul + rotulo), nao o raio."""
    import motor_expansao.config as config
    from motor_expansao.dashboard.censo_point import RAIO_CENSITARIO_DEFAULT_KM

    assert censo_map.RAIO_RESIDUAL_DISPLAY_KM == 5.0
    assert not hasattr(config, "RAIO_RESIDUAL_DISPLAY_KM")
    assert RAIO_CENSITARIO_DEFAULT_KM == 1.5
    assert censo_map._RESIDUAL_GRID_DISK_K == 5


def test_painel_de_hexagono_nao_desenha_o_circulo_do_raio(monkeypatch):
    """`circle_3857=None`/`raio_km=None` no painel de 5 km -> nenhum circulo azul no frame.

    O azul continua no canvas (agora como borda do hex central), entao a prova nao pode ser
    "zero pixel azul": e' geometrica. O circulo do raio ficava INSCRITO no frame (lado menor
    quase inteiro); a borda do hex central ocupa uma fracao pequena em torno do centro. Logo, a
    extensao vertical dos pixels azuis tem de ser MUITO menor que a altura util do mapa. A camada
    `densidade` (1,5 km, que MANTEM o circulo) e' a trava anti-vacuo.
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
    # No painel de 5 km sobra so a borda do hex central -> extensao MUITO menor.
    assert _extensao_vertical(mapas["residual"]) < 0.4 * altura_util, (
        "a camada `residual` ainda parece desenhar o circulo do raio"
    )

    # E os parametros chegam mesmo como `None` (prova direta, sem depender do pixel).
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
    assert capturado["Residual Fitness"]["circle_3857"] is None
    assert capturado["Residual Fitness"]["raio_km"] is None
    # As camadas de 1,5 km seguem com circulo + raio rotulado (nada mudou nelas).
    assert capturado["Densidade populacional"]["circle_3857"] is not None
    assert capturado["Densidade populacional"]["raio_km"] == 1.5


def test_titulo_e_rodape_do_painel_de_hexagono_sem_raio(monkeypatch):
    """O titulo perde o sufixo "- raio 5 km" e o rodape perde o prefixo "Raio 5,0 km".

    As 4 camadas de setor (1,5 km) seguem rotulando o raio, byte-a-byte como antes.
    """
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
    assert "EPSG:3857 - fundo de ruas offline" in textos
    assert "Residual Fitness" in textos
    assert not any(t.startswith("Raio 5,0 km") for t in textos)
    assert not any("raio 5 km" in t for t in textos)
    assert "Residual disponivel (alunos)" in textos


def test_hex_central_e_o_unico_marcado_para_a_borda_de_destaque():
    """`_hex_polygons_3857` devolve como `destaque` o hex que CONTEM o ponto — e so ele."""
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
    """`_render_camada(destaque_3857=...)` contorna SO o poligono marcado.

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
    """A borda nova reusa `_CIRCLE_RGBA` (nenhuma paleta deste painel tem azul) e e' FINA."""
    assert censo_map._HEX_CENTRAL_EDGE_COLOR == censo_map._CIRCLE_RGBA
    assert 1 <= censo_map._HEX_CENTRAL_LINEWIDTH <= 4


def test_camadas_existentes_ficam_byte_identicas_com_o_default_novo():
    """`destaque_3857=None` e' DEFAULT-PRESERVING: passar o default explicitamente nao muda o PNG."""
    to_3857 = censo_map._transformer(
        censo_map._local_metric_crs(LAT_C, LNG_C), censo_map.CRS_WEB_MERCATOR
    )
    circulo = censo_map._project_geometry(
        censo_map._frame_box_metric(1.5, 1000, 760).centroid.buffer(1_500.0, quad_segs=96), to_3857
    )
    quadrado = censo_map._project_geometry(box(-700, -700, 700, 700), to_3857)
    comum = dict(
        titulo="Densidade populacional",
        legenda_titulo="Densidade (hab/km2)",
        legenda_entries=censo_map._bands_legend_entries(DENSIDADE_POP_BANDS),
        color_fn=_color_for_densidade,
        source_values=pd.Series([1_000.0], dtype="float64"),
        sector_records_3857=[(quadrado, 0)],
        center_3857=to_3857.transform(0.0, 0.0),
        pins=[],
        ultra_pins=[],
        basemap=None,
        bounds=censo_map._project_geometry(
            censo_map._frame_box_metric(1.5, 1000, 760), to_3857
        ).bounds,
        lat=LAT_C,
        lng=LNG_C,
        raio_km=1.5,
        n_setores=1,
        width=1000,
        height=760,
    )
    implicito = censo_map._render_camada(circle_3857=circulo, **comum)
    explicito = censo_map._render_camada(circle_3857=circulo, destaque_3857=None, **comum)
    assert implicito == explicito
