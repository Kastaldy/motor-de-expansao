from __future__ import annotations

import pandas as pd


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


def _censo_score_to_color(score) -> list[int]:
    if pd.isna(score):
        return [120, 120, 140, 100]
    s = float(score)
    if s < 25:
        return [180, 30, 30, 140]
    elif s < 50:
        return [220, 50, 50, 140]
    elif s < 75:
        return [245, 158, 11, 140]
    else:
        return [20, 200, 80, 140]
