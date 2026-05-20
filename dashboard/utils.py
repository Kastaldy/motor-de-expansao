from __future__ import annotations

import pandas as pd

from dashboard.constants import RESIDUAL_SCORE_BANDS


def format_int(value: int | float) -> str:
    return f"{int(round(float(value))):,}".replace(",", ".")


def format_score(value: float) -> str:
    if pd.isna(value):
        return "-"
    return f"{float(value):.2f}"


def format_pct(value: float) -> str:
    if pd.isna(value):
        return "-"
    return f"{float(value):.1f}%"


def format_density(value: float) -> str:
    if pd.isna(value):
        return "-"
    return f"{float(value):,.0f}".replace(",", ".")


def hex_to_rgba(value: str, alpha: int) -> list[int]:
    color = value.lstrip("#")
    return [int(color[i : i + 2], 16) for i in (0, 2, 4)] + [alpha]


def score_band_to_color(score, alpha: int = 170) -> list[int]:
    """Maps a 0-100 score to an RGBA color via 10-point RESIDUAL_SCORE_BANDS palette."""
    if pd.isna(score):
        return [120, 120, 140, 70]
    s = float(score)
    idx = min(9, max(0, int(s // 10)))
    _, color_hex = RESIDUAL_SCORE_BANDS[idx]
    return hex_to_rgba(color_hex, alpha)


def _censo_score_to_color(score) -> list[int]:
    """Deprecated: use score_band_to_color. Kept for backward compatibility."""
    return score_band_to_color(score)


def _residual_score_to_color(score) -> list[int]:
    if pd.isna(score):
        return [120, 120, 140, 70]
    s = float(score)
    if s < 10:
        return [148, 18, 18, 190]
    elif s < 20:
        return [185, 35, 35, 185]
    elif s < 30:
        return [220, 65, 65, 178]
    elif s < 40:
        return [220, 105, 20, 175]
    elif s < 50:
        return [240, 148, 30, 170]
    elif s < 60:
        return [238, 200, 40, 165]
    elif s < 70:
        return [150, 210, 80, 165]
    elif s < 80:
        return [80, 195, 60, 165]
    elif s < 90:
        return [25, 168, 50, 165]
    else:
        return [10, 130, 38, 170]
