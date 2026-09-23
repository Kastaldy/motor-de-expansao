from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from motor_expansao.dashboard.competitors import (
    _ATLAS_CACHE,
    _ICON_CACHE,
    COMPETITOR_SPECS,
    ULTRA_COLUMNS,
    _render_pin_tile,
    _render_square_logo_tile,
    _ultra_icon_svg,
    build_icon_atlas,
    competitor_icon_data,
    load_ultra_points,
    preload_logos,
    ultra_icon_data,
    ultra_legend_entry,
)

# ── helpers ────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _caches_restaurados():
    """Snapshot/restauração dos caches GLOBAIS de ícones a cada teste.

    Os testes populam e limpam `_ICON_CACHE`/`_ATLAS_CACHE` inline; sem esta rede,
    um assert que falhe no meio deixaria o cache poluído e contaminaria os testes
    seguintes da mesma sessão (falhas em cascata dependentes de ordem).
    """
    icon_antes = dict(_ICON_CACHE)
    atlas_antes = dict(_ATLAS_CACHE)
    try:
        yield
    finally:
        _ICON_CACHE.clear()
        _ICON_CACHE.update(icon_antes)
        _ATLAS_CACHE.clear()
        _ATLAS_CACHE.update(atlas_antes)


def _write_ultra_csv(path: Path, rows: str) -> Path:
    path.write_text(
        '"Ultra - codCamada:test"\n' + rows,
        encoding="latin-1",
    )
    return path


# ── load_ultra_points ──────────────────────────────────────────────────────────


def test_load_ultra_arquivo_ausente_retorna_vazio(tmp_path):
    df = load_ultra_points(tmp_path / "nao_existe.csv")
    assert df.empty
    assert list(df.columns) == ULTRA_COLUMNS


def test_load_ultra_arquivo_vazio_retorna_vazio(tmp_path):
    p = tmp_path / "Ultra.csv"
    p.write_text("", encoding="latin-1")
    df = load_ultra_points(p)
    assert df.empty


def test_load_ultra_carrega_unidades_validas(tmp_path):
    p = tmp_path / "Ultra.csv"
    _write_ultra_csv(
        p,
        textwrap.dedent("""\
            "UNIDADE";"ESTADO";"CIDADE";"Latitude";"Longitude"
            "Plaza / SP";"SP";"Sao Paulo";"-23,6198";"-46,6265"
            "Mooca / SP";"SP";"Sao Paulo";"-23,5599";"-46,5995"
        """),
    )
    df = load_ultra_points(p)
    assert len(df) == 2
    assert list(df.columns) == ULTRA_COLUMNS
    assert df["uf"].iloc[0] == "SP"
    assert df["lat"].iloc[0] == pytest.approx(-23.6198, abs=1e-3)
    assert df["lng"].iloc[0] == pytest.approx(-46.6265, abs=1e-3)


def test_load_ultra_descarta_coordenadas_invalidas(tmp_path):
    p = tmp_path / "Ultra.csv"
    _write_ultra_csv(
        p,
        textwrap.dedent("""\
            "UNIDADE";"ESTADO";"CIDADE";"Latitude";"Longitude"
            "Valida";"SP";"Sao Paulo";"-23,5599";"-46,5995"
            "Sem lat";"SP";"SP";"";"-46,5995"
            "Fora do brasil";"SP";"SP";"10,0";"-46,5995"
        """),
    )
    df = load_ultra_points(p)
    assert len(df) == 1
    assert df["nome_unidade"].iloc[0] == "Valida"


def test_load_ultra_arquivo_sem_coluna_lat_retorna_vazio(tmp_path):
    p = tmp_path / "Ultra.csv"
    _write_ultra_csv(
        p,
        textwrap.dedent("""\
            "UNIDADE";"ESTADO";"CIDADE"
            "Sem coords";"SP";"SP"
        """),
    )
    df = load_ultra_points(p)
    assert df.empty


def test_load_ultra_nome_unidade_normalizado(tmp_path):
    p = tmp_path / "Ultra.csv"
    _write_ultra_csv(
        p,
        textwrap.dedent("""\
            "UNIDADE";"ESTADO";"CIDADE";"Latitude";"Longitude"
            "  Vila Mariana / SP  ";"SP";"Sao Paulo";"-23,5891";"-46,6421"
        """),
    )
    df = load_ultra_points(p)
    assert df["nome_unidade"].iloc[0].strip() == "Vila Mariana / SP"


# ── ultra_icon_data ────────────────────────────────────────────────────────────


def test_ultra_icon_data_retorna_chaves_esperadas():
    icon = ultra_icon_data()
    assert "url" in icon
    assert "width" in icon
    assert "height" in icon
    assert "anchorY" in icon
    assert str(icon["url"]).startswith("data:image/")


def test_ultra_icon_svg_fallback_contem_ua():
    import base64
    icon = _ultra_icon_svg()
    url = str(icon["url"])
    b64 = url.split("base64,", 1)[1]
    svg = base64.b64decode(b64).decode("utf-8")
    assert "UA" in svg


_MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_preload_logos_carrega_logo_png_da_ultra(tmp_path):
    concorrentes_dir = tmp_path / "concorrentes"
    concorrentes_dir.mkdir()
    ultra_dir = tmp_path / "ultra"
    ultra_dir.mkdir()
    (ultra_dir / "logo_ultra.png").write_bytes(_MINIMAL_PNG)
    _ICON_CACHE.pop("__ultra__", None)
    preload_logos(concorrentes_dir, ultra_dir=ultra_dir)
    assert "__ultra__" in _ICON_CACHE
    icon = ultra_icon_data()
    # Logo PNG e embutida dentro de um SVG de pin
    assert str(icon["url"]).startswith("data:image/svg+xml;base64,")
    _ICON_CACHE.pop("__ultra__", None)


def test_preload_logos_ultra_emite_pin_com_cor_da_marca(tmp_path):
    import base64
    concorrentes_dir = tmp_path / "concorrentes"
    concorrentes_dir.mkdir()
    ultra_dir = tmp_path / "ultra"
    ultra_dir.mkdir()
    (ultra_dir / "logo_ultra.png").write_bytes(_MINIMAL_PNG)
    _ICON_CACHE.pop("__ultra__", None)
    preload_logos(concorrentes_dir, ultra_dir=ultra_dir)
    icon = ultra_icon_data()
    url = str(icon["url"])
    svg = base64.b64decode(url.split("base64,", 1)[1]).decode("utf-8")
    assert "#C8001E" in svg  # cor do pin Ultra
    assert "data:image/png;base64," in svg  # logo embutida
    _ICON_CACHE.pop("__ultra__", None)


def test_preload_logos_carrega_logo_png_de_concorrente(tmp_path):
    concorrentes_dir = tmp_path / "concorrentes"
    concorrentes_dir.mkdir()
    (concorrentes_dir / "logo_smart_fit.png").write_bytes(_MINIMAL_PNG)
    _ICON_CACHE.pop("smart_fit", None)
    preload_logos(concorrentes_dir)
    assert "smart_fit" in _ICON_CACHE
    icon = competitor_icon_data("smart_fit")
    assert str(icon["url"]).startswith("data:image/svg+xml;base64,")
    _ICON_CACHE.pop("smart_fit", None)


def _tile_tem_logo(key: str) -> bool:
    """O tile quadrado leva a logo (placa branca) e nao a placa solida do fallback."""
    tile = _render_square_logo_tile(key, 64, border=False, shadow=False)
    cores = {px[:3] for px in tile.getdata() if px[3] == 255}
    return len(cores) > 2


def test_marcador_independente_tem_a_logo_do_wellhub_sem_o_png_no_diretorio(tmp_path):
    """Relato do Juan (2026-09-17): no PDF pontual as independentes saiam sem a logo do
    Wellhub. O `logo_wellhub.png` nao chega ao diretorio montado em producao (o sync so
    copia as redes do registro) — a arte do pacote cobre essa ausencia."""
    from motor_expansao.dashboard.competitors import CHAVE_AGREGADOR

    concorrentes_dir = tmp_path / "concorrentes"
    concorrentes_dir.mkdir()
    (concorrentes_dir / "logo_smart_fit.png").write_bytes(_MINIMAL_PNG)
    _ICON_CACHE.pop(CHAVE_AGREGADOR, None)
    preload_logos(concorrentes_dir)
    assert CHAVE_AGREGADOR in _ICON_CACHE
    assert _tile_tem_logo(CHAVE_AGREGADOR)


def test_logo_wellhub_do_diretorio_vence_a_do_pacote(tmp_path):
    import base64

    from motor_expansao.dashboard.competitors import AGREGADOR_LOGO_FILE, CHAVE_AGREGADOR

    concorrentes_dir = tmp_path / "concorrentes"
    concorrentes_dir.mkdir()
    (concorrentes_dir / AGREGADOR_LOGO_FILE).write_bytes(_MINIMAL_PNG)
    _ICON_CACHE.pop(CHAVE_AGREGADOR, None)
    preload_logos(concorrentes_dir)
    url = str(_ICON_CACHE[CHAVE_AGREGADOR]["url"])
    svg = base64.b64decode(url.split("base64,", 1)[1]).decode("utf-8")
    assert base64.b64encode(_MINIMAL_PNG).decode("ascii") in svg


def test_arte_do_wellhub_do_pacote_e_a_mesma_do_piloto():
    from motor_expansao.dashboard.competitors import AGREGADOR_LOGO_PACOTE

    piloto = Path(__file__).resolve().parents[2] / "web" / "public" / "logo-wellhub.png"
    assert AGREGADOR_LOGO_PACOTE.read_bytes() == piloto.read_bytes()


def test_a_arte_do_totalpass_e_CONVERSAO_FIEL_e_nao_copia_de_bytes():
    """`[DEC-066]` O invariante do TotalPass e' DIFERENTE do WellHub, e de proposito.

    O do WellHub e' igualdade de BYTES: a arte do piloto ja' e' PNG e foi copiada. O original do
    TotalPass e' JPEG -- e `_png_to_pin_svg` crava `data:image/png` no `href` e recorta a logo num
    circulo, entao um JPEG entraria mentindo sobre o proprio tipo e com os cantos brancos dentro
    do recorte. A arte empacotada e' CONVERSAO; exigir "mesmos bytes" seria falso por construcao,
    e o que se pode exigir de uma conversao e' mesmos PIXELS.
    """
    from PIL import Image

    from motor_expansao.dashboard.competitors import AGREGADOR_TP_LOGO_PACOTE

    piloto = Path(__file__).resolve().parents[2] / "web" / "public" / "logo-totalpass.jpg"
    origem = Image.open(piloto).convert("RGB")
    empacotada = Image.open(AGREGADOR_TP_LOGO_PACOTE).convert("RGB")
    assert empacotada.size == origem.size
    assert list(empacotada.getdata()) == list(origem.getdata())


def test_marcador_do_totalpass_tem_a_logo_propria_sem_o_png_no_diretorio(tmp_path):
    """Gemeo do teste do WellHub: a arte do PACOTE cobre a ausencia no diretorio montado.

    E' o estado real de producao -- o `sync_concorrentes_dashboard` so' copia as redes do
    registro, e foi por isso que as independentes sairam sem logo ate' 2026-09-17.
    """
    from motor_expansao.dashboard.competitors import CHAVE_AGREGADOR_TP

    concorrentes_dir = tmp_path / "concorrentes"
    concorrentes_dir.mkdir()
    _ICON_CACHE.pop(CHAVE_AGREGADOR_TP, None)
    preload_logos(concorrentes_dir)
    assert CHAVE_AGREGADOR_TP in _ICON_CACHE
    assert _tile_tem_logo(CHAVE_AGREGADOR_TP)


def _cores_opacas(key: str) -> set[tuple[int, int, int]]:
    tile = _render_square_logo_tile(key, 64, border=False, shadow=False)
    return {px[:3] for px in tile.getdata() if px[3] == 255}


def _bytes_do_tile(key: str) -> bytes:
    tile = _render_square_logo_tile(key, 64, border=False, shadow=False)
    return tile.tobytes()


def test_ambos_COM_arte_compoe_as_duas_logos(tmp_path):
    """`[DEC-066 / fatia 2]` M2: placa branca com as DUAS logos, uma por metade.

    O criterio NAO e' o `_tile_tem_logo` do arquivo: ele exige "mais de 2 cores opacas", e a placa
    bipartida SEM arte ja' tem rosa, verde e branco — aprovaria os dois estados, e um teste que
    passa nos dois nao prova nenhum. Aqui o que prova e' a DIFERENCA entre os dois renders.
    """
    from motor_expansao.dashboard.competitors import (
        CHAVE_AGREGADOR,
        CHAVE_AGREGADOR_TP,
        CHAVE_AMBOS,
    )

    for chave in (CHAVE_AGREGADOR, CHAVE_AGREGADOR_TP):
        _ICON_CACHE.pop(chave, None)
    sem_arte = _bytes_do_tile(CHAVE_AMBOS)

    preload_logos(tmp_path / "vazio")  # cai na arte do PACOTE, que viaja sempre
    com_arte = _bytes_do_tile(CHAVE_AMBOS)

    assert com_arte != sem_arte, "com as duas artes no cache o M2 tem de sair diferente da B5"
    assert (255, 255, 255) in _cores_opacas(CHAVE_AMBOS), "o M2 tem placa BRANCA sob as logos"


def test_ambos_SEM_arte_cai_na_placa_bipartida_B5(tmp_path):
    """`[DEC-066 / fatia 2]` A degradacao escolhida — e a que MAIS importa.

    Sem arte a cor sozinha continua dizendo "esta nos dois": metade rosa, metade verde. Se isto
    virasse placa solida, o terceiro estado sumiria exatamente onde a arte nao chega.
    """
    from motor_expansao.dashboard.competitors import (
        AGREGADOR_BRAND,
        AGREGADOR_TP_BRAND,
        CHAVE_AGREGADOR,
        CHAVE_AGREGADOR_TP,
        CHAVE_AMBOS,
    )

    def _rgb(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    for chave in (CHAVE_AGREGADOR, CHAVE_AGREGADOR_TP):
        _ICON_CACHE.pop(chave, None)
    cores = _cores_opacas(CHAVE_AMBOS)
    assert _rgb(str(AGREGADOR_BRAND["bg"])) in cores, "falta a metade do Wellhub"
    assert _rgb(str(AGREGADOR_TP_BRAND["bg"])) in cores, "falta a metade do TotalPass"


def test_a_arte_de_AMBOS_e_a_composicao_EXATA_das_duas_atuais():
    """`[DEC-066 / fatia 2]` O asset composto nao pode envelhecer em silencio.

    A web precisa de um ARQUIVO (a `IconLayer` do deck.gl recebe URL, nao desenho), enquanto o PDF
    compoe em tempo de render. Um terceiro arquivo tem um modo de falha proprio: trocar a logo de um
    dos apps deixa o composto VALIDO como imagem e FALSO como informacao -- e invisivel, porque nada
    quebra.

    Este teste fecha isso: os pixels do arquivo tem de ser exatamente os da composicao das artes de
    HOJE. Trocar qualquer uma das duas origens sem regerar o asset fica VERMELHO.
    """
    from PIL import Image

    from motor_expansao.dashboard.competitors import compor_arte_ambos

    arquivo = Path(__file__).resolve().parents[2] / "web" / "public" / "logo-ambos.png"
    assert arquivo.exists(), "o asset do terceiro estado nao foi gerado"
    do_disco = Image.open(arquivo).convert("RGBA")
    esperado = compor_arte_ambos()
    assert isinstance(esperado, Image.Image)
    assert do_disco.size == esperado.size
    assert list(do_disco.getdata()) == list(esperado.getdata()), (
        "o asset composto divergiu das artes atuais -- regere `web/public/logo-ambos.png`"
    )


def test_a_chave_sai_da_coluna_fontes_da_academia():
    """`[DEC-066 / fatia 2]` O coracao da fatia: virgula -> `__ambos__`.

    Sem a coluna (artefato anterior ao `alvos_ma_nomeados_v8`) cai na `fonte` e reproduz o desenho
    de hoje — o fallback nao inventa estado novo.
    """
    from motor_expansao.dashboard.competitors import (
        CHAVE_AGREGADOR,
        CHAVE_AGREGADOR_TP,
        CHAVE_AMBOS,
        chave_agregador_da_fonte,
    )

    assert chave_agregador_da_fonte("wellhub", "totalpass,wellhub") == CHAVE_AMBOS
    assert chave_agregador_da_fonte("totalpass", "totalpass") == CHAVE_AGREGADOR_TP
    assert chave_agregador_da_fonte("wellhub", "wellhub") == CHAVE_AGREGADOR
    # artefato antigo: a coluna nao existe
    assert chave_agregador_da_fonte("totalpass", None) == CHAVE_AGREGADOR_TP
    assert chave_agregador_da_fonte(None, None) == CHAVE_AGREGADOR


def test_celula_NULAVEL_do_pandas_nao_levanta():
    """`pd.NA` nao e' `None`: `str(x or "")` LEVANTA nele, e derrubou os mapas em 2026-09-22.

    O caso `None` ja' estava coberto acima -- e foi justamente isso que deu a falsa sensacao de
    cobertura. Numa coluna de dtype `string` o ausente e' `pd.NA`, e `bool(pd.NA)` e' `TypeError`
    por definicao. `api/service.py` monta essas colunas como `pd.Series([pd.NA] * n,
    dtype="string")` quando o artefato e' anterior ao `alvos_ma_nomeados_v8`, entao este era o
    valor REAL em producao, em toda linha sem rede.

    `NaN` entra junto porque e' o ausente do dtype NAO nulavel -- os dois chegam aqui conforme o
    artefato, e nenhum dos dois pode derrubar o desenho.
    """
    import pandas as pd

    from motor_expansao.dashboard.competitors import (
        CHAVE_AGREGADOR,
        CHAVE_AGREGADOR_TP,
        CHAVE_AMBOS,
        chave_agregador_da_fonte,
    )

    for ausente in (pd.NA, float("nan"), None, ""):
        assert chave_agregador_da_fonte(ausente, ausente) == CHAVE_AGREGADOR
        assert chave_agregador_da_fonte("totalpass", ausente) == CHAVE_AGREGADOR_TP
    # Ausente no 1o argumento NAO pode mascarar a procedencia declarada no 2o.
    assert chave_agregador_da_fonte(pd.NA, "totalpass") == CHAVE_AGREGADOR_TP
    assert chave_agregador_da_fonte(pd.NA, "totalpass,wellhub") == CHAVE_AMBOS


def test_os_dois_apps_se_distinguem_por_COR_e_nao_so_por_arte():
    """`[DEC-066]` Sem PNG nenhum o tile cai na placa SOLIDA da marca.

    Se a cor fosse a mesma, o fallback apagaria a distincao exatamente onde ela mais importa: em
    producao, onde a arte do agregador nao chega ao diretorio montado. Por isso cada app tem COR,
    e nao so' logo -- o pino verde/rosa continua respondendo "de qual app e' esta academia?".
    """
    from motor_expansao.dashboard.competitors import (
        AGREGADOR_BRAND,
        AGREGADOR_TP_BRAND,
        ARTE_AGREGADOR,
        CHAVE_AGREGADOR,
        CHAVE_AGREGADOR_TP,
        CHAVE_AMBOS,
        CHAVES_AGREGADOR,
    )

    assert AGREGADOR_BRAND["bg"] != AGREGADOR_TP_BRAND["bg"]
    # `[DEC-066 / fatia 2]` TRES chaves, DUAS artes — e a assimetria e' o DESENHO, nao esquecimento:
    # `__ambos__` COMPOE as duas artes existentes em vez de ter a sua. Ate' a fatia 2 este teste
    # afirmava a igualdade dos dois conjuntos, e a segunda assercao nem chegava a rodar quando a
    # primeira caia — por isso as duas sao reapontadas juntas.
    assert len(CHAVES_AGREGADOR) == 3
    assert set(ARTE_AGREGADOR) == {CHAVE_AGREGADOR, CHAVE_AGREGADOR_TP}
    assert CHAVE_AMBOS in CHAVES_AGREGADOR
    assert CHAVE_AMBOS not in ARTE_AGREGADOR, "o terceiro estado COMPOE, nao tem arte propria"
    assert len({nome for nome, _caminho in ARTE_AGREGADOR.values()}) == 2


def test_preload_logos_sem_arquivos_nao_quebra_o_app(tmp_path):
    concorrentes_dir = tmp_path / "sem_logos"
    concorrentes_dir.mkdir()
    _ICON_CACHE.pop("smart_fit", None)
    preload_logos(concorrentes_dir)
    icon = competitor_icon_data("smart_fit")
    assert str(icon["url"]).startswith("data:image/svg+xml;base64,")


def test_skyfit_nao_esta_no_competitor_specs():
    assert "SkyFit_unidades_geocodificado.csv" not in COMPETITOR_SPECS


# ── ultra_legend_entry ─────────────────────────────────────────────────────────


def test_ultra_legend_entry_retorna_campos():
    entry = ultra_legend_entry()
    assert "label" in entry
    assert "short" in entry
    assert "bg" in entry
    assert "fg" in entry
    assert entry["short"] == "UA"


# ── BLK-FIX-07: atlas de icones (preserva logos) ────────────────────────────────


def test_build_icon_atlas_preserva_logos(tmp_path):
    """Com _ICON_CACHE populado por preload_logos (logo PNG), build_icon_atlas
    retorna atlas data-URI PNG nao-vazio e mapping com x/y/width/height/anchorY."""
    concorrentes_dir = tmp_path / "concorrentes"
    concorrentes_dir.mkdir()
    (concorrentes_dir / "logo_smart_fit.png").write_bytes(_MINIMAL_PNG)
    _ICON_CACHE.pop("smart_fit", None)
    _ATLAS_CACHE.clear()
    preload_logos(concorrentes_dir)

    atlas, mapping = build_icon_atlas(["smart_fit"])
    assert atlas.startswith("data:image/png;base64,")
    assert len(atlas) > len("data:image/png;base64,")
    assert set(mapping.keys()) == {"smart_fit"}
    tile = mapping["smart_fit"]
    for key in ("x", "y", "width", "height", "anchorY"):
        assert key in tile
    assert tile["width"] == 128
    assert tile["height"] == 128
    assert tile["anchorY"] == 122
    _ICON_CACHE.pop("smart_fit", None)
    _ATLAS_CACHE.clear()


def test_build_icon_atlas_ultra(tmp_path):
    ultra_dir = tmp_path / "ultra"
    ultra_dir.mkdir()
    (ultra_dir / "logo_ultra.png").write_bytes(_MINIMAL_PNG)
    _ICON_CACHE.pop("__ultra__", None)
    _ATLAS_CACHE.clear()
    preload_logos(tmp_path / "concorrentes_inexistente", ultra_dir=ultra_dir)

    atlas, mapping = build_icon_atlas(["__ultra__"])
    assert atlas.startswith("data:image/png;base64,")
    assert "__ultra__" in mapping
    assert mapping["__ultra__"]["anchorY"] == 122
    _ICON_CACHE.pop("__ultra__", None)
    _ATLAS_CACHE.clear()


def test_build_icon_atlas_fallback_sigla_sem_logo():
    """Rede sem logo PNG no cache: atlas ainda e gerado (balao + sigla)."""
    _ICON_CACHE.pop("bluefit", None)
    _ATLAS_CACHE.clear()
    atlas, mapping = build_icon_atlas(["bluefit"])
    assert atlas.startswith("data:image/png;base64,")
    assert "bluefit" in mapping
    _ATLAS_CACHE.clear()


# ── BLK-RELPON-09: logo quadrada (relatorios) ──────────────────────────────────


def _valid_png(color: tuple[int, int, int, int] = (0, 128, 255, 255), side: int = 8) -> bytes:
    """PNG REAL (decodificavel pelo Pillow) para exercitar o ramo "tem logo".

    `_MINIMAL_PNG` acima e um stream deliberadamente minimo que o Pillow NAO consegue
    decodificar (`OSError: broken data stream when reading image file`): serve aos
    testes de cache/SVG (que so olham a data-URI), mas ao RASTERIZAR cai sempre no
    fallback de sigla. Para provar a placa branca do ramo com logo e preciso um PNG
    de verdade.
    """
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGBA", (side, side), color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_square_logo_tile_geometria_quadrada_com_sombra():
    """Tile RGBA quadrado exatamente do tamanho pedido, card opaco e sombra visivel."""
    _ICON_CACHE.pop("bluefit", None)
    tile = _render_square_logo_tile("bluefit", 30)
    assert tile.size == (30, 30)
    assert tile.mode == "RGBA"
    # centro do card: opaco (o card cobre o miolo do tile)
    assert tile.getpixel((15, 15))[3] == 255
    # faixa de sombra a DIREITA do card (o canto (29,29) e arredondado pelo radius=3,
    # entao a prova da sombra sai no meio do lado, nao no vertice).
    sombra = tile.getpixel((29, 15))
    assert 0 < sombra[3] < 255


def test_square_logo_tile_fallback_usa_cor_da_marca():
    """Sem logo no cache, a placa fica na COR DA MARCA (unica pista de identidade)."""
    _ICON_CACHE.pop("bluefit", None)
    tile = _render_square_logo_tile("bluefit", 30)
    cores = tile.getcolors(maxcolors=1_000_000) or []
    # #174EA6 = bg do bluefit em COMPETITOR_BRANDS
    marca = sum(n for n, cor in cores if cor == (23, 78, 166, 255))
    assert marca >= 250


def test_square_logo_tile_com_logo_real_usa_placa_branca(tmp_path):
    """Com logo PNG no cache: placa BRANCA + logo; a cor da marca (sigla) nao aparece."""
    ultra_dir = tmp_path / "ultra"
    ultra_dir.mkdir()
    (ultra_dir / "logo_ultra.png").write_bytes(_valid_png((0, 128, 255, 255)))
    _ICON_CACHE.pop("__ultra__", None)
    preload_logos(tmp_path / "concorrentes_inexistente", ultra_dir=ultra_dir)

    tile = _render_square_logo_tile("__ultra__", 30)
    cores = {cor for _n, cor in tile.getcolors(maxcolors=1_000_000) or []}
    assert (200, 0, 30, 255) not in cores  # #C8001E: sinal de que caiu no fallback
    assert (255, 255, 255, 255) in cores  # placa/keyline branca
    assert (0, 128, 255, 255) in cores  # a propria logo, em CONTAIN
    _ICON_CACHE.pop("__ultra__", None)


def test_square_logo_tile_sem_borda_sem_sombra():
    """`border=False, shadow=False` (PDF sobre pagina branca): sem pixel de sombra."""
    _ICON_CACHE.pop("bluefit", None)
    tile = _render_square_logo_tile("bluefit", 24, border=False, shadow=False)
    assert tile.size == (24, 24)
    cores = {cor for _n, cor in tile.getcolors(maxcolors=1_000_000) or []}
    # rounded_rectangle nao faz antialias -> comparacao exata e segura
    assert (0, 0, 0, 60) not in cores


def test_render_pin_tile_geometria_128_preservada_blk_relpon_09():
    """GUARDA: `_render_pin_tile` (balao 128x128) segue INTOCADO pelo BLK-RELPON-09.

    E o contrato de que `build_icon_atlas`/pydeck dependem (tile 128 px, anchorY=122).
    """
    _ICON_CACHE.pop("__ultra__", None)
    tile = _render_pin_tile("__ultra__")
    assert tile.size == (128, 128)
    assert tile.mode == "RGBA"
    cores = {cor for _n, cor in tile.getcolors(maxcolors=1_000_000) or []}
    assert (200, 0, 30, 255) in cores  # balao na cor da marca Ultra (#C8001E)


# ── logo por slug: a segunda passada do preload e o nome de exibicao ───────────
#
# O registro (`COMPETITOR_LOGO_FILES`) so' conhece as redes brasileiras, nome a nome.
# A base argentina serve `logo_<slug>.png` num diretorio proprio e a coluna `rede` traz
# o NOME DE EXIBICAO ("Megatlón", "ON FIT") — sem estas duas pontes, todo pin do PDF
# caia no fallback de sigla "C" com a logo certa parada no disco (Juan, 2026-09-08).

# PNG minimo valido (1x1 px) — mesmo fixture de tests/unit/test_api_skeleton.py
_PNG_1PX = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_slug_rede_normaliza_nome_de_exibicao():
    """A regra e' a MESMA do exportador argentino, que grava os arquivos."""
    from motor_expansao.dashboard.competitors import slug_rede

    assert slug_rede("Megatlón") == "megatlon"
    assert slug_rede("ON FIT") == "on_fit"
    assert slug_rede("SportClub (parceira)") == "sportclub_parceira"
    assert slug_rede("") == ""


def test_preload_descobre_logo_por_convencao_no_diretorio(tmp_path):
    """`logo_<slug>.png` fora do registro vira entrada de cache sob o slug."""
    (tmp_path / "logo_sportclub.png").write_bytes(_PNG_1PX)
    _ICON_CACHE.pop("sportclub", None)
    preload_logos(tmp_path)
    assert "sportclub" in _ICON_CACHE


def test_icone_da_rede_aceita_nome_de_exibicao(tmp_path):
    """Quem pinta o pin recebe "SportClub"; o cache e' indexado por `sportclub`."""
    from motor_expansao.dashboard.competitors import icone_da_rede

    (tmp_path / "logo_sportclub.png").write_bytes(_PNG_1PX)
    _ICON_CACHE.pop("sportclub", None)
    preload_logos(tmp_path)
    assert icone_da_rede("SportClub") == _ICON_CACHE["sportclub"]


def test_rede_sem_logo_continua_no_fallback_de_sigla():
    """Sem arquivo e fora do registro, nada muda: placa generica de sigla "C"."""
    icon = competitor_icon_data("Academia Que Nao Existe")
    assert icon  # o fallback SVG sempre desenha algo
    assert "svg" in str(icon.get("url", ""))
