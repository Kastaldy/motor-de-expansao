from __future__ import annotations

import base64
import re
from functools import cache
from pathlib import Path

import pandas as pd

LAT_MIN, LAT_MAX = -34.0, 6.0
LNG_MIN, LNG_MAX = -75.0, -28.0

COMPETITOR_COLUMNS = [
    "rede",
    "rede_label",
    "nome_unidade",
    "lat",
    "lng",
    "cidade",
    "uf",
    "data_coleta",
    "arquivo_origem",
    "status_registro",
]

# ── helpers ────────────────────────────────────────────────────────────────────

def _std(rede: str, label: str) -> dict[str, str]:
    return {
        "rede": rede,
        "rede_label": label,
        "nome": "nome_unidade",
        "lat": "latitude",
        "lng": "longitude",
        "data_coleta": "data_coleta",
    }


# ── specs e brands ─────────────────────────────────────────────────────────────

COMPETITOR_SPECS: dict[str, dict[str, str]] = {
    "unidades_smart_fit.csv":        _std("smart_fit",        "Smart Fit"),
    "unidades_bluefit.csv":          _std("bluefit",          "Bluefit"),
    "unidades_panobianco.csv":       _std("panobianco",       "Panobianco"),
    "unidades_26fit.csv":            _std("26fit",            "26Fit"),
    "unidades_a_fitness.csv":        _std("a_fitness",        "A Fitness"),
    "unidades_aera_pilates.csv":     _std("aera_pilates",     "Aera Pilates"),
    "unidades_allp_fit.csv":         _std("allp_fit",         "Allp Fit"),
    "unidades_alpha_fitness.csv":    _std("alpha_fitness",    "Alpha Fitness"),
    "unidades_bio_ritmo.csv":        _std("bio_ritmo",        "Bio Ritmo"),
    "unidades_biohit.csv":           _std("biohit",           "Biohit"),
    "unidades_bodytech.csv":         _std("bodytech",         "Bodytech"),
    "unidades_cia_athletica.csv":    _std("cia_athletica",    "CIA Athletica"),
    "unidades_contorno_do_corpo.csv":    _std("contorno_do_corpo",    "Contorno do Corpo"),
    "unidades_engenharia_do_corpo.csv":  _std("engenharia_do_corpo",  "Engenharia do Corpo"),
    "unidades_evolve.csv":           _std("evolve",           "Evolve"),
    "unidades_evoque.csv":           _std("evoque",           "Evoque"),
    "unidades_feira_fitness.csv":    _std("feira_fitness",    "Feira Fitness"),
    "unidades_formula.csv":          _std("formula",          "Fórmula Academia"),
    "unidades_gavioes.csv":          _std("gavioes",          "Gavioes"),
    "unidades_greenlife.csv":        _std("greenlife",        "Greenlife"),
    "unidades_jab_house.csv":        _std("jab_house",        "Jab House"),
    "unidades_kore.csv":             _std("kore",             "Kore Studios"),
    "unidades_live.csv":             _std("live",             "Live Academia"),
    "unidades_motion_fit.csv":       _std("motion_fit",       "Motion Fit"),
    "unidades_my_box.csv":           _std("my_box",           "My Box"),
    "unidades_pacer.csv":            _std("pacer",            "Pacer"),
    "unidades_phd_sports.csv":       _std("phd_sports",       "PhD Sports"),
    "unidades_pratique.csv":         _std("pratique",         "Pratique"),
    "unidades_pro3.csv":             _std("pro3",             "Pro3"),
    "unidades_race_bootcamp.csv":    _std("race_bootcamp",    "Race Bootcamp"),
    "unidades_red_fitness.csv":      _std("red_fitness",      "Red Fitness"),
    "unidades_redfit.csv":           _std("redfit",           "Redfit"),
    "unidades_selfit.csv":           _std("selfit",           "Selfit"),
    "unidades_skyfit.csv":           _std("skyfit",           "Skyfit"),
    "unidades_tonus_gym.csv":        _std("tonus_gym",        "Tonus Gym"),
    "unidades_velocity.csv":         _std("velocity",         "Velocity"),
    "unidades_vidya_studio.csv":     _std("vidya_studio",     "Vidya Studio"),
    "unidades_world_gym.csv":        _std("world_gym",        "World Gym"),
    "unidades_xprime.csv":           _std("xprime",           "Xprime"),
}

COMPETITOR_BRANDS: dict[str, dict[str, str]] = {
    "smart_fit":       {"label": "Smart Fit",        "short": "SF",  "bg": "#FFE600", "fg": "#111111"},
    "bluefit":         {"label": "Bluefit",           "short": "BF",  "bg": "#174EA6", "fg": "#FFFFFF"},
    "panobianco":      {"label": "Panobianco",        "short": "P",   "bg": "#F97316", "fg": "#FFFFFF"},
    "26fit":           {"label": "26Fit",             "short": "26",  "bg": "#22C55E", "fg": "#FFFFFF"},
    "aera_pilates":    {"label": "Aera Pilates",      "short": "AP",  "bg": "#A855F7", "fg": "#FFFFFF"},
    "allp_fit":        {"label": "Allp Fit",          "short": "AL",  "bg": "#3B82F6", "fg": "#FFFFFF"},
    "alpha_fitness":   {"label": "Alpha Fitness",     "short": "AF",  "bg": "#EF4444", "fg": "#FFFFFF"},
    "bio_ritmo":       {"label": "Bio Ritmo",         "short": "BR",  "bg": "#06B6D4", "fg": "#FFFFFF"},
    "bodytech":        {"label": "Bodytech",          "short": "BT",  "bg": "#1E293B", "fg": "#FFFFFF"},
    "cia_athletica":   {"label": "CIA Athletica",     "short": "CA",  "bg": "#0EA5E9", "fg": "#FFFFFF"},
    "contorno_do_corpo":    {"label": "Contorno do Corpo",    "short": "CC",  "bg": "#EC4899", "fg": "#FFFFFF"},
    "engenharia_do_corpo":  {"label": "Engenharia do Corpo",  "short": "EC",  "bg": "#0D9488", "fg": "#FFFFFF"},
    "evoque":          {"label": "Evoque",            "short": "EV",  "bg": "#78716C", "fg": "#FFFFFF"},
    "gavioes":         {"label": "Gavioes",           "short": "GV",  "bg": "#84CC16", "fg": "#111111"},
    "greenlife":       {"label": "Greenlife",         "short": "GL",  "bg": "#16A34A", "fg": "#FFFFFF"},
    "jab_house":       {"label": "Jab House",         "short": "JH",  "bg": "#DC2626", "fg": "#FFFFFF"},
    "kore":            {"label": "Kore Studios",      "short": "KO",  "bg": "#7C3AED", "fg": "#FFFFFF"},
    "live":            {"label": "Live Academia",     "short": "LV",  "bg": "#F59E0B", "fg": "#111111"},
    "phd_sports":      {"label": "PhD Sports",        "short": "PhD", "bg": "#0F172A", "fg": "#FFFFFF"},
    "pratique":        {"label": "Pratique",          "short": "PR",  "bg": "#10B981", "fg": "#FFFFFF"},
    "race_bootcamp":   {"label": "Race Bootcamp",     "short": "RB",  "bg": "#FF6B00", "fg": "#FFFFFF"},
    "red_fitness":     {"label": "Red Fitness",       "short": "RF",  "bg": "#B91C1C", "fg": "#FFFFFF"},
    "selfit":          {"label": "Selfit",            "short": "SF2", "bg": "#0284C7", "fg": "#FFFFFF"},
    "tonus_gym":       {"label": "Tonus Gym",         "short": "TG",  "bg": "#9333EA", "fg": "#FFFFFF"},
    "velocity":        {"label": "Velocity",          "short": "VL",  "bg": "#475569", "fg": "#FFFFFF"},
    "vidya_studio":    {"label": "Vidya Studio",      "short": "VS",  "bg": "#E11D48", "fg": "#FFFFFF"},
    "world_gym":       {"label": "World Gym",         "short": "WG",  "bg": "#1D4ED8", "fg": "#FFFFFF"},
    "xprime":          {"label": "Xprime",            "short": "XP",  "bg": "#0891B2", "fg": "#FFFFFF"},
    "a_fitness":       {"label": "A Fitness",         "short": "AFI", "bg": "#8B5CF6", "fg": "#FFFFFF"},
    "biohit":          {"label": "Biohit",            "short": "BHT", "bg": "#059669", "fg": "#FFFFFF"},
    "evolve":          {"label": "Evolve",            "short": "EVL", "bg": "#EA580C", "fg": "#FFFFFF"},
    "feira_fitness":   {"label": "Feira Fitness",     "short": "FEI", "bg": "#CA8A04", "fg": "#FFFFFF"},
    "formula":         {"label": "Fórmula Academia",  "short": "FM",  "bg": "#BE123C", "fg": "#FFFFFF"},
    "motion_fit":      {"label": "Motion Fit",        "short": "MTF", "bg": "#0369A1", "fg": "#FFFFFF"},
    "my_box":          {"label": "My Box",            "short": "MYB", "bg": "#7F1D1D", "fg": "#FFFFFF"},
    "pacer":           {"label": "Pacer",             "short": "PCA", "bg": "#134E4A", "fg": "#FFFFFF"},
    "pro3":            {"label": "Pro3",              "short": "P3",  "bg": "#1E3A5F", "fg": "#FFFFFF"},
    "redfit":          {"label": "Redfit",            "short": "RDF", "bg": "#C2410C", "fg": "#FFFFFF"},
    "skyfit":          {"label": "Skyfit",            "short": "SKY", "bg": "#0C4A6E", "fg": "#FFFFFF"},
}

# logo filenames dentro de concorrentes/
COMPETITOR_LOGO_FILES: dict[str, str] = {
    "smart_fit":           "logo_smart_fit.png",
    "bluefit":             "logo_bluefit.png",
    "panobianco":          "logo_panobianco.png",
    "26fit":               "logo_26fit.png",
    "a_fitness":           "logo_a_fitness.png",
    "aera_pilates":        "logo_aera_pilates.png",
    "allp_fit":            "logo_allp_fit.png",
    "alpha_fitness":       "logo_alpha_fitness.png",
    "bio_ritmo":           "logo_bio_ritmo.png",
    "biohit":              "logo_biohit.png",
    "bodytech":            "logo_bodytech.png",
    "cia_athletica":       "logo_cia_athletica.png",
    "contorno_do_corpo":   "logo_contorno_do_corpo.png",
    "engenharia_do_corpo": "logo_engenharia_do_corpo.png",
    "evolve":              "logo_evolve.png",
    "evoque":              "logo_evoque.png",
    "feira_fitness":       "logo_feira_fitness.png",
    "formula":             "logo_formula.png",
    "gavioes":             "logo_gavioes.png",
    "greenlife":           "logo_greenlife.png",
    "jab_house":           "logo_jab_house.png",
    "kore":                "logo_kore.png",
    "live":                "logo_live.png",
    "motion_fit":          "logo_motion_fit.png",
    "my_box":              "logo_my_box.png",
    "pacer":               "logo_pacer.png",
    "phd_sports":          "logo_phd_sports.png",
    "pratique":            "logo_pratique.png",
    "pro3":                "logo_pro3.png",
    "race_bootcamp":       "logo_race_bootcamp.png",
    "red_fitness":         "logo_red_fitness.png",
    "redfit":              "logo_redfit.png",
    "selfit":              "logo_selfit.png",
    "skyfit":              "logo_skyfit.png",
    "tonus_gym":           "logo_tonus_gym.png",
    "velocity":            "logo_velocity.png",
    "vidya_studio":        "logo_vidya_studio.png",
    "world_gym":           "logo_world_gym.png",
    "xprime":              "logo_xprime.png",
}

ULTRA_LOGO_FILE = "logo_ultra.png"

# cache de logos PNG: rede -> icon_data; "__ultra__" para Ultra
_ICON_CACHE: dict[str, dict] = {}


def _png_to_pin_svg(png_b64: str, *, pin_bg: str, pin_stroke: str = "#FFFFFF") -> str:
    """Gera SVG de pin de mapa com logo PNG clipada em circulo branco interno."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'
        ' width="128" height="128" viewBox="0 0 128 128">'
        "<defs><clipPath id=\"lc\"><circle cx=\"64\" cy=\"47\" r=\"27\"/></clipPath></defs>"
        f'<path d="M64 6C40.8 6 22 24.8 22 48c0 31.5 42 74 42 74s42-42.5 42-74'
        f'C106 24.8 87.2 6 64 6z" fill="{pin_bg}" stroke="{pin_stroke}" stroke-width="6"/>'
        '<circle cx="64" cy="47" r="27" fill="#FFFFFF"/>'
        f'<image href="data:image/png;base64,{png_b64}"'
        ' x="37" y="20" width="54" height="54" clip-path="url(#lc)"'
        ' preserveAspectRatio="xMidYMid meet"/>'
        "</svg>"
    )


def _png_icon_data(path: Path, *, pin_bg: str = "#FFFFFF") -> dict[str, object] | None:
    """Le PNG, envolve em pin SVG e retorna icon_data para pydeck IconLayer."""
    if not path.exists():
        return None
    try:
        png_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        svg = _png_to_pin_svg(png_b64, pin_bg=pin_bg)
        encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        return {"url": f"data:image/svg+xml;base64,{encoded}", "width": 128, "height": 128, "anchorY": 122}
    except Exception:
        return None


def preload_logos(competitors_dir: Path, ultra_dir: Path | None = None) -> None:
    """Le logos PNG locais e popula _ICON_CACHE. App funciona sem esses arquivos."""
    for rede, filename in COMPETITOR_LOGO_FILES.items():
        pin_bg = COMPETITOR_BRANDS.get(rede, {}).get("bg", "#FFFFFF")
        icon = _png_icon_data(competitors_dir / filename, pin_bg=pin_bg)
        if icon is not None:
            _ICON_CACHE[rede] = icon
    if ultra_dir is not None:
        icon = _png_icon_data(ultra_dir / ULTRA_LOGO_FILE, pin_bg=ULTRA_BRAND["bg"])
        if icon is not None:
            _ICON_CACHE["__ultra__"] = icon


# ── I/O ────────────────────────────────────────────────────────────────────────

def _empty_competitors() -> pd.DataFrame:
    return pd.DataFrame(columns=COMPETITOR_COLUMNS)


def _read_csv(path: Path) -> pd.DataFrame:
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            df = pd.read_csv(path, sep=";", dtype=str, encoding=encoding)
            if len(df.columns) >= 2:
                return df
            # provavelmente sep=","
            df2 = pd.read_csv(path, sep=",", dtype=str, encoding=encoding)
            if len(df2.columns) >= 2:
                return df2
            return df
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return pd.read_csv(path, sep=";", dtype=str)


def _find_column(df: pd.DataFrame, expected: str | None) -> str | None:
    if not expected:
        return None
    if expected in df.columns:
        return expected
    normalized = {str(column).strip().lower(): column for column in df.columns}
    return normalized.get(expected.strip().lower())


def _coord_in_brazil(value: float, *, axis: str) -> bool:
    if axis == "lat":
        return LAT_MIN <= value <= LAT_MAX
    return LNG_MIN <= value <= LNG_MAX


def _parse_coordinate(value: object, *, axis: str) -> float | None:
    if pd.isna(value):
        return None

    text = str(value).strip()
    if not text:
        return None

    normalized = text.replace(",", ".")
    direct = pd.to_numeric(normalized, errors="coerce")
    if pd.notna(direct) and _coord_in_brazil(float(direct), axis=axis):
        return float(direct)

    digits = re.sub(r"\D", "", text)
    if not digits:
        return None

    sign = -1 if text.lstrip().startswith("-") else 1
    numeric = int(digits)
    for decimals in range(4, min(len(digits), 10) + 1):
        candidate = sign * numeric / (10**decimals)
        if _coord_in_brazil(candidate, axis=axis):
            return float(candidate)

    return None


def _series_or_empty(df: pd.DataFrame, column: str | None) -> pd.Series:
    if column and column in df.columns:
        return df[column].astype("string").fillna("").str.strip()
    return pd.Series([""] * len(df), index=df.index, dtype="string")


def _normalize_frame(path: Path, spec: dict[str, str]) -> pd.DataFrame:
    raw = _read_csv(path)
    nome_col = _find_column(raw, spec.get("nome"))
    lat_col = _find_column(raw, spec.get("lat"))
    lng_col = _find_column(raw, spec.get("lng"))
    cidade_col = _find_column(raw, spec.get("cidade"))
    uf_col = _find_column(raw, spec.get("uf"))
    data_col = _find_column(raw, spec.get("data_coleta"))
    status_col = _find_column(raw, spec.get("status"))

    if not nome_col or not lat_col or not lng_col:
        return _empty_competitors()

    out = pd.DataFrame(
        {
            "rede": spec["rede"],
            "rede_label": spec["rede_label"],
            "nome_unidade": _series_or_empty(raw, nome_col),
            "lat": raw[lat_col].map(lambda value: _parse_coordinate(value, axis="lat")),
            "lng": raw[lng_col].map(lambda value: _parse_coordinate(value, axis="lng")),
            "cidade": _series_or_empty(raw, cidade_col),
            "uf": _series_or_empty(raw, uf_col).str.upper(),
            "data_coleta": _series_or_empty(raw, data_col),
            "arquivo_origem": path.name,
            "status_registro": _series_or_empty(raw, status_col),
        }
    )

    valid_coord = out["lat"].notna() & out["lng"].notna()
    out["status_registro"] = out["status_registro"].where(out["status_registro"] != "", "valido")
    out = out.loc[valid_coord].copy()
    return out[COMPETITOR_COLUMNS]


def load_competitor_points(competitors_dir: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for filename, spec in COMPETITOR_SPECS.items():
        path = competitors_dir / filename
        if path.exists():
            frame = _normalize_frame(path, spec)
            if not frame.empty:
                frames.append(frame)

    if not frames:
        return _empty_competitors()

    competitors = pd.concat(frames, ignore_index=True)
    competitors = competitors.drop_duplicates(subset=["rede", "lat", "lng"], keep="first")
    competitors = competitors.sort_values(["rede_label", "nome_unidade"], kind="stable").reset_index(drop=True)
    return competitors[COMPETITOR_COLUMNS]


# ── icons ──────────────────────────────────────────────────────────────────────

@cache
def _competitor_icon_svg(rede: str) -> dict[str, object]:
    brand = COMPETITOR_BRANDS.get(
        str(rede),
        {"label": "Concorrente", "short": "C", "bg": "#64748B", "fg": "#FFFFFF"},
    )
    short = str(brand["short"])[:3]
    bg = brand["bg"]
    fg = brand["fg"]
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
      <path d="M64 6C40.8 6 22 24.8 22 48c0 31.5 42 74 42 74s42-42.5 42-74C106 24.8 87.2 6 64 6z" fill="{bg}" stroke="#FFFFFF" stroke-width="7"/>
      <circle cx="64" cy="49" r="32" fill="rgba(255,255,255,0.18)"/>
      <text x="64" y="60" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="30" font-weight="800" fill="{fg}">{short}</text>
    </svg>
    """.strip()
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return {"url": f"data:image/svg+xml;base64,{encoded}", "width": 128, "height": 128, "anchorY": 122}


def competitor_icon_data(rede: str) -> dict[str, object]:
    if rede in _ICON_CACHE:
        return _ICON_CACHE[rede]
    return _competitor_icon_svg(rede)


def competitor_legend_entries(redes: list[str] | pd.Series | None = None) -> list[dict[str, str]]:
    if redes is None:
        ordered_redes = list(COMPETITOR_BRANDS)
    else:
        ordered_redes = [rede for rede in COMPETITOR_BRANDS if rede in set(redes)]
    return [
        {
            "rede": rede,
            "label": COMPETITOR_BRANDS[rede]["label"],
            "short": COMPETITOR_BRANDS[rede]["short"],
            "bg": COMPETITOR_BRANDS[rede]["bg"],
            "fg": COMPETITOR_BRANDS[rede]["fg"],
        }
        for rede in ordered_redes
    ]


# ── Ultra Academia ────────────────────────────────────────────────────────────

ULTRA_BRAND = {"label": "Ultra Academia", "short": "UA", "bg": "#C8001E", "fg": "#FFFFFF"}

ULTRA_COLUMNS = ["nome_unidade", "lat", "lng", "cidade", "uf", "arquivo_origem"]


def _empty_ultra() -> pd.DataFrame:
    return pd.DataFrame(columns=ULTRA_COLUMNS)


def load_ultra_points(ultra_path: Path) -> pd.DataFrame:
    if not ultra_path.exists():
        return _empty_ultra()
    try:
        raw = None
        for encoding in ("latin-1", "utf-8-sig", "utf-8"):
            try:
                raw = pd.read_csv(ultra_path, sep=";", dtype=str, encoding=encoding, skiprows=1)
                break
            except UnicodeDecodeError:
                continue
        if raw is None or raw.empty:
            return _empty_ultra()
    except Exception:
        return _empty_ultra()

    unidade_col = _find_column(raw, "UNIDADE")
    lat_col = _find_column(raw, "Latitude")
    lng_col = _find_column(raw, "Longitude")
    cidade_col = _find_column(raw, "CIDADE")
    estado_col = _find_column(raw, "ESTADO")

    if not unidade_col or not lat_col or not lng_col:
        return _empty_ultra()

    out = pd.DataFrame({
        "nome_unidade": _series_or_empty(raw, unidade_col),
        "lat": raw[lat_col].map(lambda v: _parse_coordinate(v, axis="lat")),
        "lng": raw[lng_col].map(lambda v: _parse_coordinate(v, axis="lng")),
        "cidade": _series_or_empty(raw, cidade_col),
        "uf": _series_or_empty(raw, estado_col).str.upper(),
        "arquivo_origem": ultra_path.name,
    })

    valid_coord = out["lat"].notna() & out["lng"].notna()
    return out.loc[valid_coord].reset_index(drop=True)[ULTRA_COLUMNS]


@cache
def _ultra_icon_svg() -> dict[str, object]:
    bg = ULTRA_BRAND["bg"]
    fg = ULTRA_BRAND["fg"]
    short = ULTRA_BRAND["short"]
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
      <path d="M64 6C40.8 6 22 24.8 22 48c0 31.5 42 74 42 74s42-42.5 42-74C106 24.8 87.2 6 64 6z" fill="{bg}" stroke="#FFFFFF" stroke-width="7"/>
      <circle cx="64" cy="49" r="32" fill="rgba(255,255,255,0.18)"/>
      <text x="64" y="60" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="30" font-weight="800" fill="{fg}">{short}</text>
    </svg>
    """.strip()
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return {"url": f"data:image/svg+xml;base64,{encoded}", "width": 128, "height": 128, "anchorY": 122}


def ultra_icon_data() -> dict[str, object]:
    if "__ultra__" in _ICON_CACHE:
        return _ICON_CACHE["__ultra__"]
    return _ultra_icon_svg()


def ultra_legend_entry() -> dict[str, str]:
    return {
        "label": ULTRA_BRAND["label"],
        "short": ULTRA_BRAND["short"],
        "bg": ULTRA_BRAND["bg"],
        "fg": ULTRA_BRAND["fg"],
    }


# ── atlas de icones (BLK-FIX-07 Fase A) ──────────────────────────────────────────
# Atlas unico por escopo de redes presentes: rasteriza UMA imagem PNG que concatena
# os pins (um por rede + Ultra) e devolve um iconMapping. Cada linha da IconLayer
# passa a carregar SO a string da chave (rede / "__ultra__") em get_icon, em vez de
# repetir a data-URI base64 do logo por linha. Logos 100% preservados (mesma arte:
# balao na cor da marca + logo PNG no circulo, ou sigla no fallback), agora empacotada
# uma vez. Camada visual de apoio (CLAUDE.md §2): nao altera score nem artefatos M1.

ATLAS_TILE = 128
_ATLAS_ANCHOR_Y = 122
_ATLAS_CIRCLE_CX = 64
_ATLAS_CIRCLE_CY = 47
_ATLAS_CIRCLE_R = 27

# Cache modulo-nivel (analogo a _ICON_CACHE) keyed pelo frozenset de chaves do atlas;
# evita reconstruir o atlas a cada rerun do Streamlit para o mesmo conjunto de redes.
# Mantem o modulo livre de Streamlit (sem @st.cache_data).
_ATLAS_CACHE: dict[frozenset[str], tuple[str, dict[str, dict[str, int | bool]]]] = {}


def _extract_embedded_logo_png(icon_url: str) -> bytes | None:
    """Extrai os bytes da logo PNG embutida no SVG de pin (`_png_to_pin_svg`).

    `_ICON_CACHE[rede]["url"]` e um data:image/svg+xml com a logo PNG embutida em
    `<image href="data:image/png;base64,...">`. Retorna os bytes da PNG ou None
    (ex.: fallback de sigla, que e SVG sem PNG embutida)."""
    try:
        if "image/svg" not in icon_url or "base64," not in icon_url:
            return None
        svg = base64.b64decode(icon_url.split("base64,", 1)[1]).decode("utf-8")
        match = re.search(r"data:image/png;base64,([A-Za-z0-9+/=]+)", svg)
        if not match:
            return None
        return base64.b64decode(match.group(1))
    except Exception:
        return None


def _render_pin_tile(key: str) -> object:
    """Rasteriza um tile 128x128 (RGBA) do pin para `key` (rede ou "__ultra__"),
    espelhando a geometria de `_png_to_pin_svg` (balao 128x128; circulo branco
    cx=64,cy=47,r=27; anchorY=122). Usa o logo PNG do _ICON_CACHE quando existe;
    senao desenha a sigla da marca (mesmo fallback visual de hoje)."""
    from PIL import Image, ImageDraw, ImageFont

    if key == "__ultra__":
        brand: dict[str, str] = dict(ULTRA_BRAND)
    else:
        brand = dict(
            COMPETITOR_BRANDS.get(
                key,
                {"label": "Concorrente", "short": "C", "bg": "#64748B", "fg": "#FFFFFF"},
            )
        )
    pin_bg = str(brand.get("bg", "#64748B"))
    fg = str(brand.get("fg", "#FFFFFF"))
    short = str(brand.get("short", "C"))[:3]

    tile = Image.new("RGBA", (ATLAS_TILE, ATLAS_TILE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tile)

    # balao do pin (teardrop) na cor da marca, contorno branco
    draw.polygon(
        [
            (64, 6), (40, 18), (25, 42), (30, 70), (64, 122), (98, 70), (103, 42), (88, 18),
        ],
        fill=pin_bg,
        outline="#FFFFFF",
    )
    draw.ellipse([22, 6, 106, 90], fill=pin_bg, outline="#FFFFFF", width=6)
    # circulo branco interno (onde vai o logo / sigla)
    cx, cy, r = _ATLAS_CIRCLE_CX, _ATLAS_CIRCLE_CY, _ATLAS_CIRCLE_R
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#FFFFFF")

    logo_png = _extract_embedded_logo_png(str(_ICON_CACHE.get(key, {}).get("url", "")))
    if logo_png is not None:
        try:
            import io

            logo = Image.open(io.BytesIO(logo_png)).convert("RGBA")
            side = r * 2
            logo = logo.resize((side, side), Image.Resampling.LANCZOS)
            # mascara circular para clipar o logo no circulo (espelha clipPath do SVG)
            mask = Image.new("L", (side, side), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, side - 1, side - 1], fill=255)
            tile.paste(logo, (cx - r, cy - r), mask)
            return tile
        except Exception:
            pass

    # fallback: sigla da marca centrada no circulo
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont
    try:
        font = ImageFont.truetype("arialbd.ttf", 26)
    except Exception:
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 26)
        except Exception:
            font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), short, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw / 2 - bbox[0], cy - th / 2 - bbox[1]), short, fill=fg, font=font)
    return tile


def build_icon_atlas(
    redes: list[str],
) -> tuple[str, dict[str, dict[str, int | bool]]]:
    """Monta um atlas PNG unico com um tile 128x128 por chave em `redes` (redes de
    concorrentes e/ou "__ultra__") e o iconMapping correspondente.

    Retorna `(atlas_data_uri, icon_mapping)`:
      - `atlas_data_uri`: `data:image/png;base64,...` (string UNICA do atlas).
      - `icon_mapping`: `{chave: {"x","y","width","height","anchorY","mask"}}`.

    Cache por `frozenset(redes)`. Preserva os logos (fonte = `_ICON_CACHE`/pins de
    hoje). Nao altera score nem artefatos M1 (camada visual)."""
    from PIL import Image

    keys = sorted({str(r) for r in redes})
    if not keys:
        keys = ["__ultra__"]
    cache_key = frozenset(keys)
    cached = _ATLAS_CACHE.get(cache_key)
    if cached is not None:
        return cached

    n = len(keys)
    atlas = Image.new("RGBA", (ATLAS_TILE * n, ATLAS_TILE), (0, 0, 0, 0))
    mapping: dict[str, dict[str, int | bool]] = {}
    for i, key in enumerate(keys):
        tile = _render_pin_tile(key)
        atlas.paste(tile, (i * ATLAS_TILE, 0))  # type: ignore[arg-type]
        mapping[key] = {
            "x": i * ATLAS_TILE,
            "y": 0,
            "width": ATLAS_TILE,
            "height": ATLAS_TILE,
            "anchorY": _ATLAS_ANCHOR_Y,
            "mask": False,
        }

    import io

    buffer = io.BytesIO()
    atlas.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    atlas_data_uri = f"data:image/png;base64,{encoded}"

    result = (atlas_data_uri, mapping)
    _ATLAS_CACHE[cache_key] = result
    return result


# ── logo quadrada para relatorios (BLK-RELPON-09) ──────────────────────────────
# Marcador de concorrente/Ultra dos PDFs (Relatorio Pontual Censitario e Relatorio
# Municipal): a PROPRIA logo num quadrado, SEM balao e SEM mascara circular. NAO
# substitui `_render_pin_tile` -- que segue alimentando `build_icon_atlas`/pydeck com o
# tile 128x128 e `anchorY=122` (e a paridade de BLK-WEB-02/07). As duas coexistem.
# Camada visual (CLAUDE.md §5): nao altera score, faixas nem artefatos M1.
_SQUARE_LOGO_RADIUS = 3
_SQUARE_LOGO_BORDER_PX = 2
_SQUARE_LOGO_SHADOW_PX = 2
_SQUARE_LOGO_SHADOW_RGBA = (0, 0, 0, 60)


def _render_square_logo_tile(
    key: str,
    size: int = 30,
    *,
    border: bool = True,
    shadow: bool = True,
) -> object:
    """Rasteriza um tile RGBA `size` x `size` com a logo QUADRADA de `key`.

    `key` e a rede do concorrente ou "__ultra__". O tile e um quadrado de cantos
    levemente arredondados (o "card"), SEM balao e SEM mascara circular:
      - ha logo PNG no `_ICON_CACHE` -> placa BRANCA + a logo inteira em CONTAIN
        (preserva a proporcao; nunca estica);
      - nao ha logo (ou falha ao abrir) -> placa na COR DA MARCA + sigla, que e a
        unica pista de identidade no fallback.
    O canvas tem exatamente `size` x `size`; com `shadow=True` a sombra ocupa os
    `_SQUARE_LOGO_SHADOW_PX` px inferiores-direitos DENTRO do canvas, logo o card
    mede `size - _SQUARE_LOGO_SHADOW_PX`. `border`/`shadow` sao desligaveis (o PDF
    do Relatorio Municipal desenha a logo sobre pagina branca, onde keyline e
    sombra virariam sujeira).

    A ANCORA e decidida no chamador (BLK-RELPON-09, S2b): os relatorios centram o
    quadrado no ponto (`- size // 2` nos dois eixos), porque o marcador nao tem
    ponta. Chamadores tipam o retorno com `cast(Image.Image, ...)` (o modulo nao
    importa PIL no topo; o import e lazy, como em `_render_pin_tile`).
    """
    from PIL import Image, ImageDraw, ImageFont

    size = max(8, int(size))

    if key == "__ultra__":
        brand: dict[str, str] = dict(ULTRA_BRAND)
    else:
        brand = dict(
            COMPETITOR_BRANDS.get(
                key,
                {"label": "Concorrente", "short": "C", "bg": "#64748B", "fg": "#FFFFFF"},
            )
        )
    bg = str(brand.get("bg", "#64748B"))
    fg = str(brand.get("fg", "#FFFFFF"))
    short = str(brand.get("short", "C"))[:3]

    pad = _SQUARE_LOGO_SHADOW_PX if shadow else 0
    bw = _SQUARE_LOGO_BORDER_PX if border else 0

    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tile, "RGBA")
    card = (0, 0, size - 1 - pad, size - 1 - pad)

    if shadow:
        draw.rounded_rectangle(
            (pad, pad, size - 1, size - 1),
            radius=_SQUARE_LOGO_RADIUS,
            fill=_SQUARE_LOGO_SHADOW_RGBA,
        )

    logo_png = _extract_embedded_logo_png(str(_ICON_CACHE.get(key, {}).get("url", "")))
    if logo_png is not None:
        try:
            import io

            # placa branca: logo com transparencia/arte escura precisa de fundo claro
            # para ler sobre o choropleth.
            draw.rounded_rectangle(card, radius=_SQUARE_LOGO_RADIUS, fill=(255, 255, 255, 255))
            inner_w = max(1, (size - pad) - 2 * bw)
            inner_h = inner_w  # o card e quadrado
            logo = Image.open(io.BytesIO(logo_png)).convert("RGBA")
            # CONTAIN: preserva o aspect ratio (nunca estica) e amplia quando preciso
            # (por isso NAO usar Image.thumbnail, que so reduz).
            ratio = min(inner_w / logo.width, inner_h / logo.height)
            new_w = max(1, int(round(logo.width * ratio)))
            new_h = max(1, int(round(logo.height * ratio)))
            logo = logo.resize((new_w, new_h), Image.Resampling.LANCZOS)
            ox = bw + (inner_w - new_w) // 2
            oy = bw + (inner_h - new_h) // 2
            tile.paste(logo, (ox, oy), logo)
            if border:
                draw.rounded_rectangle(
                    card,
                    radius=_SQUARE_LOGO_RADIUS,
                    outline=(255, 255, 255, 255),
                    width=bw,
                )
            return tile
        except Exception:
            pass

    # fallback: placa na cor da marca + sigla centrada
    draw.rounded_rectangle(card, radius=_SQUARE_LOGO_RADIUS, fill=bg)
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont
    try:
        # `load_default(size=)` (Pillow >= 10.1) respeita o tamanho pedido; `truetype`
        # nao serve aqui porque a imagem de producao nao tem fonte de sistema e o
        # fallback degradaria para um bitmap fixo de ~10 px (ver `censo_map._font`).
        font = ImageFont.load_default(size=max(7, int(round(size * 0.42))))
    except Exception:
        font = ImageFont.load_default()
    ccx = ccy = (size - 1 - pad) / 2
    bbox = draw.textbbox((0, 0), short, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((ccx - tw / 2 - bbox[0], ccy - th / 2 - bbox[1]), short, fill=fg, font=font)
    if border:
        draw.rounded_rectangle(
            card,
            radius=_SQUARE_LOGO_RADIUS,
            outline=(255, 255, 255, 255),
            width=bw,
        )
    return tile
