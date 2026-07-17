"""Graficos financeiros de viabilidade em PNG estatico (BLK-RELVIAB-03).

Reproduz, em matplotlib -> PNG (BytesIO), os 4 graficos que a aba de Viabilidade ja
plota em Plotly, para embutir no PDF do Relatorio Pontual (via `pdf.image(BytesIO(...))`).
Backend `Agg` (headless, sem display). Funcoes PURAS: recebem a serie mensal / numeros do
DRE e devolvem `bytes` de um PNG valido — sem I/O de disco, sem estado global, sem
dependencia nova (matplotlib ja e base). READ-ONLY sobre o M1 (nao recalcula score/artefatos).

A serie mensal e a saida de `dimensionamento.simulador.gerar_serie_mensal`: uma lista de
dicts com as chaves `mes`, `alunos_balcao`, `faturamento_mensal`, `ebitda_mensal`,
`fcf_acumulado`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from io import BytesIO
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless: sem display, deterministico.

import matplotlib.pyplot as plt  # noqa: E402  (import apos set do backend, obrigatorio)

# Paleta Ultra (mesmos tons do PDF/dashboard).
_TURQUESA = "#00A79D"
_MAGENTA = "#C23C8E"
_CINZA = "#3C3C3C"
_VERDE = "#1AAA55"

_FIG_W = 6.0
_FIG_H = 3.6
_DPI = 100
# Dimensao nominal do PNG (px) = figsize * dpi. tight_layout NAO altera o figsize.
PNG_WIDTH = int(_FIG_W * _DPI)
PNG_HEIGHT = int(_FIG_H * _DPI)


def _fig_to_png(fig: Any) -> bytes:
    """Serializa a figura como PNG em memoria e fecha a figura (sem vazar estado)."""
    buffer = BytesIO()
    fig.tight_layout()
    fig.savefig(buffer, format="png", dpi=_DPI)
    plt.close(fig)
    return buffer.getvalue()


def _finite(value: Any) -> float | None:
    """float finito ou None (NaN/inf/None viram None)."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _coluna(serie: Sequence[dict], chave: str) -> list[float]:
    return [float(ponto.get(chave, 0.0) or 0.0) for ponto in serie]


def grafico_rampa_alunos(
    serie: Sequence[dict],
    *,
    steady: float | None = None,
    maturacao_mes: int | None = None,
) -> bytes:
    """Rampa de alunos (balcao) ao longo dos meses; steady-state e maturacao como marcos."""
    meses = _coluna(serie, "mes")
    alunos = _coluna(serie, "alunos_balcao")
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), dpi=_DPI)
    ax.plot(meses, alunos, color=_TURQUESA, linewidth=2)
    steady_f = _finite(steady)
    if steady_f is not None:
        ax.axhline(steady_f, color=_MAGENTA, linestyle="--", linewidth=1, label="Steady-state")
        ax.legend(loc="lower right", fontsize=8)
    if maturacao_mes is not None:
        ax.axvline(float(maturacao_mes), color=_CINZA, linestyle=":", linewidth=1)
    ax.set_title("Rampa de alunos (balcao)")
    ax.set_xlabel("Mes")
    ax.set_ylabel("Alunos")
    ax.grid(True, alpha=0.2)
    return _fig_to_png(fig)


def grafico_faturamento_ebitda(serie: Sequence[dict]) -> bytes:
    """Faturamento (barras) e EBITDA (linha) mensais."""
    meses = _coluna(serie, "mes")
    faturamento = _coluna(serie, "faturamento_mensal")
    ebitda = _coluna(serie, "ebitda_mensal")
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), dpi=_DPI)
    ax.bar(meses, faturamento, color=_TURQUESA, alpha=0.55, label="Faturamento")
    ax.plot(meses, ebitda, color=_MAGENTA, linewidth=2, label="EBITDA")
    ax.set_title("Faturamento e EBITDA mensais")
    ax.set_xlabel("Mes")
    ax.set_ylabel("R$ / mes")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.2)
    return _fig_to_png(fig)


def grafico_fcf_acumulado(serie: Sequence[dict], *, payback_meses: float | None = None) -> bytes:
    """Fluxo de caixa acumulado, com marco de payback quando finito."""
    meses = _coluna(serie, "mes")
    fcf = _coluna(serie, "fcf_acumulado")
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), dpi=_DPI)
    ax.fill_between(meses, fcf, color=_TURQUESA, alpha=0.35)
    ax.plot(meses, fcf, color=_TURQUESA, linewidth=1.8)
    ax.axhline(0.0, color=_CINZA, linewidth=0.8)
    payback_f = _finite(payback_meses)
    if payback_f is not None:
        ax.axvline(payback_f, color=_MAGENTA, linestyle="--", linewidth=1, label="Payback")
        ax.legend(loc="lower right", fontsize=8)
    ax.set_title("Fluxo de caixa acumulado")
    ax.set_xlabel("Mes")
    ax.set_ylabel("R$ acumulado")
    ax.grid(True, alpha=0.2)
    return _fig_to_png(fig)


def grafico_dre_waterfall(
    *,
    faturamento_bruto: float,
    receita_liquida: float,
    receita_pos_impostos: float,
    ebitda: float,
) -> bytes:
    """Waterfall do DRE steady-state: Fat. bruto -> Deducoes -> Impostos -> Custos op. -> EBITDA."""
    fat = float(faturamento_bruto or 0.0)
    r_liq = float(receita_liquida or 0.0)
    r_pos = float(receita_pos_impostos or 0.0)
    eb = float(ebitda or 0.0)
    # Passos (rotulo, base, topo). Fat/EBITDA sao barras cheias; os 3 do meio sao decrementos.
    passos = [
        ("Fat. bruto", 0.0, fat, _TURQUESA),
        ("Deducoes", r_liq, fat, _MAGENTA),
        ("Impostos", r_pos, r_liq, _MAGENTA),
        ("Custos op.", eb, r_pos, _MAGENTA),
        ("EBITDA", 0.0, eb, _VERDE),
    ]
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), dpi=_DPI)
    for i, (_rotulo, base, topo, cor) in enumerate(passos):
        ax.bar(i, topo - base, bottom=base, color=cor, width=0.6)
    ax.set_xticks(range(len(passos)))
    ax.set_xticklabels([p[0] for p in passos], rotation=20, fontsize=8, ha="right")
    ax.set_title("DRE steady-state (R$ / mes)")
    ax.set_ylabel("R$ / mes")
    ax.grid(True, axis="y", alpha=0.2)
    return _fig_to_png(fig)
