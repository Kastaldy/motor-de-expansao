from __future__ import annotations

import textwrap
from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.dashboard.competitors import (
    _ATLAS_CACHE,
    _ICON_CACHE,
    COMPETITOR_SPECS,
    ULTRA_COLUMNS,
    _ultra_icon_svg,
    build_icon_atlas,
    competitor_icon_data,
    load_ultra_points,
    preload_logos,
    ultra_icon_data,
    ultra_legend_entry,
)
from motor_expansao.dashboard.components import _build_ultra_icon_layer

# ── helpers ────────────────────────────────────────────────────────────────────


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


# ── _build_ultra_icon_layer ────────────────────────────────────────────────────


def _make_ultra_df(n: int = 2) -> pd.DataFrame:
    return pd.DataFrame({
        "nome_unidade": [f"Unidade {i}" for i in range(n)],
        "lat": [-23.55 - i * 0.01 for i in range(n)],
        "lng": [-46.63 - i * 0.01 for i in range(n)],
        "cidade": ["Sao Paulo"] * n,
        "uf": ["SP"] * n,
        "arquivo_origem": ["Ultra.csv"] * n,
    })


def _make_reference_df() -> pd.DataFrame:
    return pd.DataFrame({
        "lat": [-23.54, -23.56],
        "lng": [-46.62, -46.64],
    })


def test_build_ultra_icon_layer_retorna_layer_valido():
    layer = _build_ultra_icon_layer(_make_ultra_df(), _make_reference_df())
    assert layer is not None


def test_build_ultra_icon_layer_ultra_vazio_retorna_none():
    layer = _build_ultra_icon_layer(pd.DataFrame(columns=ULTRA_COLUMNS), _make_reference_df())
    assert layer is None


def test_build_ultra_icon_layer_ultra_none_retorna_none():
    layer = _build_ultra_icon_layer(None, _make_reference_df())
    assert layer is None


def test_build_ultra_icon_layer_reference_vazia_retorna_none():
    layer = _build_ultra_icon_layer(_make_ultra_df(), pd.DataFrame())
    assert layer is None


def test_build_ultra_icon_layer_filtra_fora_do_bounding_box():
    ultra = pd.DataFrame({
        "nome_unidade": ["Distante"],
        "lat": [5.0],
        "lng": [-46.63],
        "cidade": ["Manaus"],
        "uf": ["AM"],
        "arquivo_origem": ["Ultra.csv"],
    })
    layer = _build_ultra_icon_layer(ultra, _make_reference_df())
    assert layer is None


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


def test_build_ultra_icon_layer_usa_atlas():
    """_build_ultra_icon_layer produz layer com icon_atlas/icon_mapping e get_icon
    apontando para a chave (sem icon_data por linha)."""
    layer = _build_ultra_icon_layer(_make_ultra_df(), _make_reference_df())
    assert layer is not None
    assert layer.icon_atlas is not None
    assert layer.icon_mapping is not None
    assert "__ultra__" in layer.icon_mapping
    assert str(layer.get_icon) in ("icon_key", "@@=icon_key")
    payload = pd.DataFrame(layer.data)
    assert "icon_data" not in payload.columns
    assert "icon_key" in payload.columns
