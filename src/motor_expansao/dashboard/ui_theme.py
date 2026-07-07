"""ui_theme.py — Tema visual Ultra para o PoC de repaginacao do dashboard (BLK-UI-10).

Contem apenas CSS injetado + helpers de paleta/tipografia.
NAO recalcula score, pesos, carteira, artefatos do M1.
Opt-in atrás de flag `ULTRA_PROTO=1` / `session_state["show_ui_proto"]`.

Paleta aprovada (handoff BO 2026-07-06):
  --bg:#0b1016  --panel:#121a24  --line:#1f2c3a
  --ultra:#1fd1c4 (turquesa, acento único)
  --conc:#ff3d8b  (magenta, só-concorrente)
  --text:#dce6f0  --muted:#7d97ad

Tipografia:
  Display/títulos : Space Grotesk (caráter técnico/cartográfico)
  Corpo/UI        : IBM Plex Sans (engenharia)
  Dados (hex,lat) : IBM Plex Mono (mono justificável — o dado é o subject)
"""
from __future__ import annotations

import streamlit as st

# ──────────────────────────────────────────────────────────────
# Paleta canônica (nunca editada; consultar handoff BLK-UI-10)
# ──────────────────────────────────────────────────────────────
PROTO_PALETTE: dict[str, str] = {
    "bg": "#0b1016",
    "panel": "#121a24",
    "line": "#1f2c3a",
    "ultra": "#1fd1c4",   # turquesa — acento único da Ultra
    "conc": "#ff3d8b",    # magenta — só para concorrentes
    "text": "#dce6f0",
    "muted": "#7d97ad",
    "panel_border": "#1f2c3a",
    "data_bg": "#0e1620",  # fundo de valores de dados (mono)
}

# ──────────────────────────────────────────────────────────────
# CSS completo do protótipo
# ──────────────────────────────────────────────────────────────
_FONTS_CDN = (
    "https://fonts.googleapis.com/css2?"
    "family=Space+Grotesk:wght@400;500;600;700&"
    "family=IBM+Plex+Sans:wght@400;500;600&"
    "family=IBM+Plex+Mono:wght@400;500&"
    "display=swap"
)

_CSS = """
/* ======================================================
   Ultra Academia — PoC Dashboard (BLK-UI-10)
   Prefixo .ui-proto- em todas as classes; sem * nem body
   para não conflitar com o CSS global do Streamlit.
   ====================================================== */

/* Fonts CDN — fallback gracioso: se não carregar, usa
   a sans-serif do SO sem quebrar o layout. */
@import url('{fonts}');

/* ──────────────────────────────────────────────────────
   Variáveis CSS
   ────────────────────────────────────────────────────── */
.ui-proto-root {{
  --bg:     {bg};
  --panel:  {panel};
  --line:   {line};
  --ultra:  {ultra};
  --conc:   {conc};
  --text:   {text};
  --muted:  {muted};
  --data-bg:{data_bg};
  --font-display: 'Space Grotesk', system-ui, sans-serif;
  --font-body:    'IBM Plex Sans', system-ui, sans-serif;
  --font-mono:    'IBM Plex Mono', 'Cascadia Code', monospace;
  --radius-card:  10px;
  --radius-chip:  6px;
}}

/* ──────────────────────────────────────────────────────
   Wrapper raiz do protótipo
   ────────────────────────────────────────────────────── */
.ui-proto-root {{
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-body);
  font-size: 0.95rem;
  line-height: 1.5;
}}

/* ──────────────────────────────────────────────────────
   Faixa superior (header strip)
   ────────────────────────────────────────────────────── */
.ui-proto-header {{
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.65rem 1rem;
  background: var(--panel);
  border-bottom: 1px solid var(--line);
  font-family: var(--font-display);
  font-size: 1.1rem;
  font-weight: 600;
  letter-spacing: 0.01em;
}}

.ui-proto-header .ui-proto-badge {{
  display: inline-block;
  padding: 0.18rem 0.55rem;
  border-radius: 4px;
  background: var(--ultra);
  color: var(--bg);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}}

/* ──────────────────────────────────────────────────────
   Layout 3 painéis (sidebar esq + centro + sidebar dir)
   Implementado via st.columns; estas classes decoram
   cada coluna individualmente.
   ────────────────────────────────────────────────────── */
.ui-proto-sidebar {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-card);
  padding: 0.75rem;
}}

.ui-proto-sidebar h3 {{
  font-family: var(--font-display);
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
  margin: 0 0 0.65rem;
  border-bottom: 1px solid var(--line);
  padding-bottom: 0.4rem;
}}

.ui-proto-map-panel {{
  background: var(--data-bg);
  border: 1px solid var(--line);
  border-radius: var(--radius-card);
  overflow: hidden;
  position: relative;
}}

/* ──────────────────────────────────────────────────────
   KPI cards com assinatura hexagonal
   A assinatura H3 aparece no canto superior-direito do
   card como um hexágono recortado (clip-path).
   Apenas UM motivo de assinatura — o resto é contido.
   ────────────────────────────────────────────────────── */
.ui-proto-kpi {{
  position: relative;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-card);
  padding: 0.75rem 0.85rem;
  overflow: hidden;
  margin-bottom: 0.55rem;
}}

/* Faixa de cor na borda esquerda — indica tipo de métrica */
.ui-proto-kpi::before {{
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
  background: var(--ultra);
  border-radius: var(--radius-card) 0 0 var(--radius-card);
}}

.ui-proto-kpi.ui-proto-kpi--conc::before {{
  background: var(--conc);
}}

/* Assinatura hexagonal: ornamento de fundo (clip-path hexágono H3).
   Um único elemento decorativo — sem significado semântico,
   mas ancorando a identidade do projeto sem poluir a leitura. */
.ui-proto-kpi::after {{
  content: '';
  position: absolute;
  right: -12px;
  top: 50%;
  transform: translateY(-50%);
  width: 48px;
  height: 54px;
  background: rgba(31, 209, 196, 0.07);
  clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
  pointer-events: none;
}}

.ui-proto-kpi.ui-proto-kpi--conc::after {{
  background: rgba(255, 61, 139, 0.07);
}}

.ui-proto-kpi__label {{
  font-size: 0.73rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 0.3rem;
}}

.ui-proto-kpi__value {{
  font-family: var(--font-mono);
  font-size: 1.35rem;
  font-weight: 500;
  color: var(--text);
  line-height: 1.15;
}}

.ui-proto-kpi__sub {{
  font-size: 0.75rem;
  color: var(--muted);
  margin-top: 0.15rem;
}}

/* ──────────────────────────────────────────────────────
   Painel de detalhe de hexágono (sidebar direita)
   ────────────────────────────────────────────────────── */
.ui-proto-detail {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-card);
  padding: 0.75rem;
  font-size: 0.85rem;
}}

.ui-proto-detail__title {{
  font-family: var(--font-display);
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--ultra);
  margin-bottom: 0.5rem;
}}

.ui-proto-detail__row {{
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.28rem 0;
  border-bottom: 1px solid var(--line);
}}

.ui-proto-detail__row:last-child {{
  border-bottom: none;
}}

.ui-proto-detail__key {{
  color: var(--muted);
  font-size: 0.78rem;
}}

.ui-proto-detail__val {{
  font-family: var(--font-mono);
  color: var(--text);
  font-size: 0.78rem;
  text-align: right;
}}

/* ──────────────────────────────────────────────────────
   Legenda de score (chips coloridos)
   ────────────────────────────────────────────────────── */
.ui-proto-legend {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.5rem;
}}

.ui-proto-legend-chip {{
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.22rem 0.5rem;
  border-radius: var(--radius-chip);
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--line);
  font-size: 0.72rem;
  color: var(--muted);
}}

.ui-proto-legend-dot {{
  width: 8px;
  height: 8px;
  border-radius: 2px;
  flex-shrink: 0;
}}

/* ──────────────────────────────────────────────────────
   Aviso de opt-in (banner discreto no topo)
   ────────────────────────────────────────────────────── */
.ui-proto-banner {{
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.45rem 0.75rem;
  background: rgba(31, 209, 196, 0.08);
  border: 1px solid rgba(31, 209, 196, 0.25);
  border-radius: var(--radius-chip);
  font-size: 0.78rem;
  color: var(--muted);
  margin-bottom: 0.6rem;
}}

.ui-proto-banner strong {{
  color: var(--ultra);
}}

/* ──────────────────────────────────────────────────────
   Acessibilidade
   ────────────────────────────────────────────────────── */

/* Contraste AA (4.5:1) garantido por construção:
   --text:#dce6f0 sobre --panel:#121a24 → ratio ~11:1
   --muted:#7d97ad sobre --panel:#121a24 → ratio ~4.6:1 */

/* Foco de teclado visível */
.ui-proto-root *:focus-visible {{
  outline: 2px solid var(--ultra);
  outline-offset: 2px;
}}

/* prefers-reduced-motion: desabilita transições */
@media (prefers-reduced-motion: reduce) {{
  .ui-proto-root *,
  .ui-proto-root *::before,
  .ui-proto-root *::after {{
    transition: none !important;
    animation: none !important;
  }}
}}
""".format(
    fonts=_FONTS_CDN,
    **PROTO_PALETTE,
)


def inject_ultra_theme() -> None:
    """Injeta o CSS do tema Ultra no PoC opt-in.

    Deve ser chamado APENAS dentro de `render_proto_page()`.
    NAO afeta o layout de produção (o CSS é prefixado com `.ui-proto-`).
    """
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)


def kpi_card_html(
    label: str,
    value: str,
    sub: str = "",
    *,
    conc: bool = False,
) -> str:
    """Gera HTML de um KPI card com assinatura hexagonal.

    Args:
        label: Rótulo do KPI (exibido em uppercase pequeno).
        value: Valor principal (exibido em mono).
        sub: Texto secundário opcional.
        conc: Se True, usa cor de concorrente (magenta) em vez da turquesa Ultra.

    Returns:
        String HTML pronta para st.markdown(unsafe_allow_html=True).
    """
    modifier = " ui-proto-kpi--conc" if conc else ""
    sub_html = f'<div class="ui-proto-kpi__sub">{sub}</div>' if sub else ""
    return (
        f'<div class="ui-proto-kpi{modifier}">'
        f'<div class="ui-proto-kpi__label">{label}</div>'
        f'<div class="ui-proto-kpi__value">{value}</div>'
        f"{sub_html}"
        f"</div>"
    )


def detail_panel_html(fields: dict[str, str], title: str = "Hexágono") -> str:
    """Gera HTML do painel de detalhe de um hexágono.

    Args:
        fields: Mapeamento chave → valor a exibir.
        title: Título do painel.

    Returns:
        String HTML pronta para st.markdown(unsafe_allow_html=True).
    """
    rows = "".join(
        f'<div class="ui-proto-detail__row">'
        f'<span class="ui-proto-detail__key">{k}</span>'
        f'<span class="ui-proto-detail__val">{v}</span>'
        f"</div>"
        for k, v in fields.items()
    )
    return (
        f'<div class="ui-proto-detail">'
        f'<div class="ui-proto-detail__title">{title}</div>'
        f"{rows}"
        f"</div>"
    )
