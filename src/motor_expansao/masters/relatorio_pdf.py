"""PDF do relatório trimestral do master — MODELO ANTIGO (estudo de área: onde abrir e metas).

Congelado como "modelo antigo" em 16/11/2026: ainda pode mudar ou ser aprovado para ir ao motor.
O "modelo novo" é este mesmo relatório com slides a mais (como as unidades funcionam em cada
região), em rascunho no BLK-MASTERS-02.

No modelo do estudo de área do time de Expansão.

O molde é o estudo de área do RJ (abr/2026), que o Relatório Municipal do motor já segue: capa
com a foto, faixa de título colorida, cartões de número, tabela de municípios, mapa, bairros
ocupados × disponíveis, Top 5 por população e por renda e a análise de oportunidade. O visual
(capa, fundo das páginas, molduras) é o do Relatório Municipal, importado dele: os dois saem
iguais e mudam juntos.

Ordem das páginas: capa -> visão geral do território -> mapa -> mapas de calor -> onde abrir
mais (comparação entre as regiões) -> bairros -> Top 5 por população -> Top 5 por renda ->
metas -> análise de oportunidade. No modelo novo, as metas saem dali e fecham o relatório, depois
dos slides de funcionamento; no "só os novos" (teste), vêm logo depois deles.

Texto do PDF passa por `_t()`: o core font Helvetica do fpdf2 é latin-1, e o que fica fora
(travessão, seta, aspas curvas, sinal de menos) viraria "?" em silêncio (§2 do CLAUDE.md).
"""

from __future__ import annotations

import io
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import h3  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402
from matplotlib.offsetbox import AnnotationBbox, OffsetImage  # noqa: E402

from motor_expansao.dashboard import pdf_base  # noqa: E402
from motor_expansao.dashboard.constants import (  # noqa: E402
    DENSIDADE_POP_BANDS,
    OFERTA_DISPONIVEL_ALUNOS_BANDS,
    RENDA_MEDIA_DOMICILIAR_BANDS,
)
from motor_expansao.dashboard.relatorio_municipal import (  # noqa: E402
    _NAVY_CAPA,
    ULTRA_BRANCO_GELO,
    ULTRA_LARANJA,
    _draw_full_page_background,
    _draw_title_band,
    _load_branding_assets,
    _rounded_panel,
    _UltraPDF,
)
from motor_expansao.masters.area import POP_MIN_BAIRRO  # noqa: E402
from motor_expansao.masters.mapa import CORES_REGIAO  # noqa: E402
from motor_expansao.masters.territorios import Master  # noqa: E402

TURQUESA = pdf_base.ULTRA_TURQUESA
MAGENTA = pdf_base.ULTRA_MAGENTA
LARANJA = ULTRA_LARANJA
ROXO = (91, 63, 168)
TINTA = (40, 40, 40)
TINTA_2 = (90, 90, 90)
TINTA_3 = (130, 130, 130)
BORDA = (222, 222, 226)
BRANCO = (255, 255, 255)
#: Linhas da tabela de bairros, como no estudo do RJ (verde = disponível, roxo = ocupado).
VERDE_DISPONIVEL = (198, 232, 160)
ROXO_OCUPADO = (200, 186, 232)

W, H = pdf_base.PAGINA_LARGURA, pdf_base.PAGINA_ALTURA
MARGEM = 36.0
TOPO = 72.0  # primeira linha útil abaixo da faixa de título
MESES_LONGOS = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]

_TROCAS = {
    "—": "-",
    "–": "-",
    "−": "-",
    "→": "->",
    "…": "...",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "•": "-",
    "≥": ">=",
    "≤": "<=",
    "≈": "~",
}


def _t(texto: Any) -> str:
    s = str(texto)
    for a, b in _TROCAS.items():
        s = s.replace(a, b)
    return s.encode("latin-1", errors="replace").decode("latin-1")


# --------------------------------------------------------------------------- formatos


def fmt_int(x: float) -> str:
    return "-" if pd.isna(x) else f"{x:,.0f}".replace(",", ".")


def fmt_dec(x: float, casas: int = 1) -> str:
    return (
        "-"
        if pd.isna(x)
        else f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )


def fmt_pct(x: float, sinal: bool = False) -> str:
    if pd.isna(x):
        return "-"
    v = round(100 * x)
    return f"{'+' if sinal and v > 0 else ''}{v}%"


def fmt_reais(x: float) -> str:
    if pd.isna(x):
        return "-"
    if abs(x) >= 1e6:
        return f"R$ {fmt_dec(x / 1e6)} mi"
    return f"R$ {fmt_int(x / 1e3)} mil"


def fmt_renda(x: float) -> str:
    return "-" if pd.isna(x) else f"R$ {fmt_int(x)}"


def fmt_pop(x: float) -> str:
    if pd.isna(x):
        return "-"
    if x >= 1e6:
        return f"{fmt_dec(x / 1e6)} mi"
    return fmt_int(x)


def trimestre_de(ts: pd.Timestamp) -> str:
    return f"{(ts.month - 1) // 3 + 1}º trimestre de {ts.year}"


# --------------------------------------------------------------------------- dados do relatório


@dataclass
class DadosRelatorio:
    master: Master
    gerado_em: pd.Timestamp
    data_ref: pd.Timestamp  # último mês fechado das unidades
    snapshot_mercado: str
    regioes: pd.DataFrame
    unidades: pd.DataFrame
    metas: pd.DataFrame
    metas_resumo: dict[str, Any]
    #: Progresso da meta do contrato (`analise.progresso_meta`); vazio = sem meta na config.
    meta_contrato: dict[str, Any] = field(default_factory=dict)
    #: Estudo de área (`masters.area`): municípios e bairros do território.
    visao: pd.DataFrame = field(default_factory=pd.DataFrame)
    bairros: pd.DataFrame = field(default_factory=pd.DataFrame)
    #: Para os mapas: hexágonos (hex_id, lat, lng, regiao_id, espaco_livre, n_concorrentes),
    #: setores (lat, lng, renda_dom, densidade) e unidades Ultra (lat, lng, do_master).
    hexes: pd.DataFrame = field(default_factory=pd.DataFrame)
    setores_mapa: pd.DataFrame = field(default_factory=pd.DataFrame)
    ultra_pontos: pd.DataFrame = field(default_factory=pd.DataFrame)
    #: O contorno de cada área (`masters.mapa.contorno`), por `regiao_id`: o mapa do território
    #: só demarca a área (19/11/2026). Vazio = o contorno sai dos hexágonos povoados.
    contornos: dict[str, Any] = field(default_factory=dict)
    #: Slides a mais do modelo novo (`masters.funcionamento.montar`); vazio = modelo antigo.
    funcionamento: dict[str, Any] = field(default_factory=dict)
    #: Régua nacional da ocupação do mercado (`analise.referencia_ocupacao`); None = sem régua.
    referencia_ocupacao: dict[str, Any] | None = None
    assets_dir: Path | None = None
    teste: bool = True

    @property
    def tem_area(self) -> bool:
        return not self.bairros.empty


# --------------------------------------------------------------------------- primitivas


def _pagina(
    pdf: _UltraPDF,
    assets: dict[str, bytes | None],
    titulo: str,
    d: DadosRelatorio,
    cor: tuple[int, int, int] = TURQUESA,
) -> float:
    """Página de conteúdo no molde do Relatório Municipal: fundo, faixa de título e o master à direita."""
    pdf.add_page()
    _draw_full_page_background(pdf, assets.get("conteudo"), ULTRA_BRANCO_GELO)
    _draw_title_band(pdf, _t(titulo), rgb=cor)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*BRANCO)
    pdf.set_xy(W - 300, 22)
    pdf.cell(264, 14, _t(d.master.nome_exibicao), align="R")
    return TOPO


def _nota(
    pdf: _UltraPDF, y: float, texto: str, largura: float | None = None, x: float = MARGEM
) -> float:
    pdf.set_xy(x, y)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*TINTA_3)
    pdf.multi_cell(largura or (W - 2 * MARGEM), 11, _t(texto), align="L")
    return pdf.get_y()


Coluna = tuple[str, float, str]  # (título, largura, alinhamento)


def _tabela(
    pdf: _UltraPDF,
    x: float,
    y: float,
    colunas: Sequence[Coluna],
    linhas: Sequence[Sequence[str]],
    *,
    alt_linha: float = 20.0,
    fonte: float = 9.0,
    cor_cabecalho: tuple[int, int, int] = TURQUESA,
    fundo_linha: Callable[[int], tuple[int, int, int] | None] | None = None,
    desenhar_celula: Callable[[_UltraPDF, int, int, float, float, float, float], bool]
    | None = None,
    negrito_primeira: bool = False,
) -> float:
    """Tabela do estudo de área: cabeçalho na cor do relatório, linhas finas e um gancho por célula."""
    largura = sum(c[1] for c in colunas)
    alt_cab = 26.0
    pdf.set_fill_color(*cor_cabecalho)
    pdf.rect(x, y, largura, alt_cab, "F")
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(*BRANCO)
    cx = x
    for titulo, larg, al in colunas:
        linhas_cab = pdf.multi_cell(larg - 6, 10, _t(titulo), dry_run=True, output="LINES")
        n_linhas = len(linhas_cab) if isinstance(linhas_cab, list) else 1
        pdf.set_xy(cx + 3, y + (alt_cab - 10 * n_linhas) / 2)
        pdf.multi_cell(larg - 6, 10, _t(titulo), align=al)
        cx += larg
    y += alt_cab
    for i, lin in enumerate(linhas):
        fundo = fundo_linha(i) if fundo_linha else (BRANCO if i % 2 == 0 else (247, 247, 247))
        if fundo is not None:
            pdf.set_fill_color(*fundo)
            pdf.rect(x, y, largura, alt_linha, "F")
        pdf.set_draw_color(*BORDA)
        pdf.line(x, y + alt_linha, x + largura, y + alt_linha)
        cx = x
        for j, ((_, larg, al), valor) in enumerate(zip(colunas, lin, strict=True)):
            if desenhar_celula and desenhar_celula(pdf, i, j, cx, y, larg, alt_linha):
                cx += larg
                continue
            pdf.set_xy(cx + 3, y)
            pdf.set_font("Helvetica", "B" if (negrito_primeira and j == 0) else "", fonte)
            pdf.set_text_color(*TINTA)
            pdf.cell(larg - 6, alt_linha, _t(valor), align=al)
            cx += larg
        y += alt_linha
    return y


def _kpi(
    pdf: _UltraPDF,
    x: float,
    y: float,
    w: float,
    cor: tuple[int, int, int],
    valor: str,
    rotulo: str,
) -> None:
    """Cartão de número do estudo de área: tarja colorida em cima, número na cor, rótulo embaixo."""
    h = 92.0
    pdf.set_fill_color(*BRANCO)
    pdf.set_draw_color(*BORDA)
    pdf.rect(x, y, w, h, "DF")
    pdf.set_fill_color(*cor)
    pdf.rect(x, y, w, 22, "F")
    pdf.set_text_color(*cor)
    pdf.set_font("Helvetica", "B", 17)
    pdf.set_xy(x, y + 32)
    pdf.cell(w, 20, _t(valor), align="C")
    pdf.set_text_color(*TINTA_2)
    pdf.set_font("Helvetica", "", 10.5)
    pdf.set_xy(x + 8, y + 56)
    pdf.multi_cell(w - 16, 13, _t(rotulo), align="C")


def _faixa_inferior(pdf: _UltraPDF, texto: str, cor: tuple[int, int, int] = MAGENTA) -> None:
    """A tarja de baixo das páginas de mapa do estudo do RJ, com o nome do território."""
    pdf.set_fill_color(*cor)
    pdf.rect(
        0,
        H - 62,
        500,
        62,
        "F",
        round_corners=("TOP_RIGHT",),  # type: ignore[arg-type]  # o stub do fpdf2 só declara bool
        corner_radius=18,
    )
    pdf.set_text_color(*BRANCO)
    pdf.set_font("Helvetica", "", 18)
    pdf.set_xy(36, H - 44)
    pdf.cell(440, 24, _t(texto))


def _png(fig: plt.Figure, dpi: int = 170) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor="white", bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    buf.seek(0)
    return buf


def _rgb(c: tuple[int, int, int]) -> tuple[float, float, float]:
    return (c[0] / 255, c[1] / 255, c[2] / 255)


def _estilo_eixo(ax: plt.Axes) -> None:
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color("#c8c8c8")
    ax.tick_params(colors="#666666", labelsize=8)
    ax.set_axisbelow(True)


# --------------------------------------------------------------------------- mapas


def _poligonos(hex_ids: Sequence[str]) -> list[list[tuple[float, float]]]:
    return [[(lng, lat) for lat, lng in h3.cell_to_boundary(h)] for h in hex_ids]


def _eixo_mapa(ax: plt.Axes, lat_media: float) -> None:
    ax.set_aspect(1 / np.cos(np.radians(lat_media)))
    ax.set_axis_off()


def _cor_regiao(d: DadosRelatorio) -> dict[str, str]:
    return {r.id: CORES_REGIAO[i % len(CORES_REGIAO)] for i, r in enumerate(d.master.regioes)}


def pino_ultra(assets_dir: Path | None, px: int = 64) -> bytes | None:
    """O pino da Ultra do motor: a logo quadrada (`competitors._render_square_logo_tile`, a mesma
    do Relatório Pontual e do mapa), lida de `<assets_dir>/logo_ultra.png`; sem o arquivo, a
    sigla do próprio motor. PNG em bytes."""
    from motor_expansao.dashboard import competitors as C

    base = Path(assets_dir) if assets_dir is not None else Path("data/ultra")
    C.preload_logos(base / "_sem_concorrentes", ultra_dir=base)
    tile = C._render_square_logo_tile("__ultra__", px)
    buf = io.BytesIO()
    tile.save(buf, format="PNG")  # type: ignore[attr-defined]
    return buf.getvalue()


def _contorno_dos_hexagonos(hex_ids: Sequence[str]) -> list[Any]:
    """O contorno da união dos hexágonos, quando o relatório não traz o pronto (`d.contornos`)."""
    from motor_expansao.masters.mapa import contorno

    return contorno(list(hex_ids))


def _mapa_territorio(
    d: DadosRelatorio, tamanho: tuple[float, float], icone: bytes | None = None
) -> io.BytesIO:
    hx = d.hexes
    fig, ax = plt.subplots(figsize=tamanho)
    # Só a DEMARCAÇÃO da área, sem pintar (19/11/2026, Juan: "o mapa está rosa; deixe apenas a
    # demarcação da área", como o mapa da aba do master): o contorno de cada área, em cinza.
    poligonos = [p for r in d.master.regioes for p in d.contornos.get(r.id, [])]
    if not poligonos:
        poligonos = _contorno_dos_hexagonos(list(hx["hex_id"]))
    for poligono in poligonos:
        for anel in poligono:
            ax.plot(
                [p[0] for p in anel],
                [p[1] for p in anel],
                color=_rgb(TINTA_2),
                linewidth=1.3,
                solid_joinstyle="round",
                zorder=2,
            )
    ax.autoscale_view()
    # Hexágono isolado longe do resto (a ilha da Trindade é de Vitória/ES) não espreme o mapa:
    # o enquadramento vai até 3 vezes a distância de 99% dos hexágonos ao centro.
    lat0, lng0 = float(hx["lat"].median()), float(hx["lng"].median())
    dist = np.hypot(hx["lat"] - lat0, (hx["lng"] - lng0) * np.cos(np.radians(lat0)))
    perto = hx[dist <= 3 * float(np.quantile(dist, 0.99))]
    if len(perto) < len(hx):
        folga = 0.03
        ax.set_xlim(float(perto["lng"].min()) - folga, float(perto["lng"].max()) + folga)
        ax.set_ylim(float(perto["lat"].min()) - folga, float(perto["lat"].max()) + folga)
    # Sem o nome das regiões dentro do mapa (18/11, Juan: "estão em cima do mapa, atrapalhando a
    # visualização"): a legenda fica numa linha acima do mapa, na página.
    up = d.ultra_pontos
    if not up.empty:
        # A logo da Ultra no ponto de cada unidade (17/11, Juan), o pino do motor, a MESMA para
        # todas (19/11/2026, Juan: "deixe apenas 'Unidades', junte os dois"; antes as do master e
        # as outras saíam em dois tamanhos). Sem o pino, círculos. A legenda sai fora do mapa.
        img = plt.imread(io.BytesIO(icone), format="png") if icone else None
        if img is None:
            ax.scatter(
                up["lng"],
                up["lat"],
                s=34,
                c="#202020",
                edgecolors="white",
                linewidths=0.8,
                zorder=4,
            )
        else:
            for lng, lat in zip(up["lng"], up["lat"], strict=True):
                ax.add_artist(
                    AnnotationBbox(OffsetImage(img, zoom=0.2), (lng, lat), frameon=False, zorder=4)
                )
    _eixo_mapa(ax, float(hx["lat"].mean()))
    return _png(fig)


def _sobre_branco(rgba: Sequence[float]) -> tuple[float, float, float]:
    """A cor da régua do motor (RGBA 0-255, alfa 150 = a do mapa) como ela aparece sobre o branco."""
    r, g_, b, a = rgba
    f = a / 255
    return (r / 255 * f + 1 - f, g_ / 255 * f + 1 - f, b / 255 * f + 1 - f)


#: Concorrentes que alcançam o hexágono (1 km): a escala do motor, `CONC_1KM_HEX` e
#: `CONC_1KM_ROTULOS` de web/src/lib/colors.ts (paridade travada em teste), com o alfa dos
#: hexágonos do mapa (`HEX_FILL_ALPHA` = 115).
CONC_1KM_HEX = ("#F2C230", "#E8663C", "#B9455A", "#6E7686")
CONC_1KM_ROTULOS = ("1 concorrente", "2 concorrentes", "3 concorrentes", "4 ou mais")
HEX_FILL_ALPHA = 115
#: Sem leitura: o cinza do motor (`SEM_LEITURA_CALOR`, rgba(120,120,140,.24)).
SEM_LEITURA = (120, 120, 140, round(0.24 * 255))


def _hex_rgba(cor: str, alfa: int) -> tuple[int, int, int, int]:
    return (int(cor[1:3], 16), int(cor[3:5], 16), int(cor[5:7], 16), alfa)


#: As faixas dos concorrentes no formato das réguas do motor (teto, rótulo, RGBA).
CONC_1KM_BANDS: list[tuple[float, str, tuple[int, int, int, int]]] = [
    (float(i + 1) if i < 3 else float("inf"), rot, _hex_rgba(cor, HEX_FILL_ALPHA))
    for i, (cor, rot) in enumerate(zip(CONC_1KM_HEX, CONC_1KM_ROTULOS, strict=True))
]


def _rotulo_faixa(rotulo: str) -> str:
    """O rótulo da régua do motor com acento (a régua usa ASCII por causa do PNG da legenda)."""
    return ("até " + rotulo[4:]) if rotulo.startswith("ate ") else rotulo


def classes_do_motor(
    valores: pd.Series,
    faixas: Sequence[tuple[float, str, Sequence[float]]],
    zero: str | None = None,
) -> tuple[np.ndarray, list[tuple[tuple[float, float, float], str]]]:
    """Cor de cada valor pela régua do motor (a 1ª faixa com valor <= teto, como no mapa) e a
    legenda: todas as faixas, mais "sem dado" (vazio) e a classe `zero` (0 ou menos), se houver."""
    v = pd.to_numeric(valores, errors="coerce").to_numpy(dtype=float)
    cores_faixa = [_sobre_branco(c) for _, _, c in faixas]
    tetos = np.array([t for t, _, _ in faixas])
    cinza = _sobre_branco(SEM_LEITURA)
    claro = (0.9, 0.9, 0.9)
    idx = np.clip(np.searchsorted(tetos, np.nan_to_num(v), side="left"), 0, len(faixas) - 1)
    cores = np.array([cores_faixa[i] for i in idx]) if len(v) else np.zeros((0, 3))
    vazio = np.isnan(v)
    nulo = (~vazio) & (v <= 0) if zero else np.zeros(len(v), dtype=bool)
    if len(v):
        cores[vazio] = cinza
        cores[nulo] = claro
    legenda = [(cor, _rotulo_faixa(r)) for cor, (_, r, _) in zip(cores_faixa, faixas, strict=True)]
    if zero and nulo.any():
        legenda.insert(0, (claro, zero))
    if vazio.any():
        legenda.append((cinza, "sem dado"))
    return cores, legenda


def _mapa_calor(
    lng: pd.Series,
    lat: pd.Series,
    cores: np.ndarray,
    tamanho: tuple[float, float],
    hex_ids: Sequence[str] | None = None,
) -> io.BytesIO:
    """Mapa pintado com as cores da régua do motor (`classes_do_motor`); hexágonos ou pontos de
    setor. Sem legenda dentro: ela vai ao lado do mapa, na página (17/11, Juan)."""
    fig, ax = plt.subplots(figsize=tamanho)
    if hex_ids is not None:
        pc = PolyCollection(_poligonos(list(hex_ids)), facecolors=cores, edgecolors="none")
        ax.add_collection(pc)
        ax.autoscale_view()
    else:
        ax.scatter(lng, lat, s=1.2, c=cores, linewidths=0)
    _eixo_mapa(ax, float(lat.mean()) if len(lat) else 0.0)
    return _png(fig)


def _legenda_faixas(
    pdf: _UltraPDF,
    x: float,
    y: float,
    larg: float,
    titulo: str,
    itens: Sequence[tuple[tuple[float, float, float], str]],
) -> None:
    """Legenda ao lado do mapa: a unidade da régua e uma linha por faixa (amostra + rótulo)."""
    pdf.set_xy(x, y)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(*TINTA_2)
    pdf.multi_cell(larg, 10.5, _t(titulo), align="L")
    yy = pdf.get_y() + 4
    pdf.set_font("Helvetica", "", 8.5)
    for cor, rotulo in itens:
        pdf.set_fill_color(*(round(c * 255) for c in cor))
        pdf.set_draw_color(200, 200, 205)
        pdf.set_line_width(0.4)
        pdf.rect(x, yy + 1.5, 11, 9, style="DF")
        pdf.set_xy(x + 16, yy)
        pdf.set_text_color(*TINTA)
        pdf.cell(larg - 16, 12, _t(rotulo))
        yy += 14


def _grafico_regioes(regioes: pd.DataFrame, cores: dict[str, str]) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(4.0, 2.7))
    r = regioes.iloc[::-1]
    ax.barh(
        r["regiao_nome"],
        r["espaco_livre_alunos"] / 1e3,
        color=[cores.get(i, "#999999") for i in r["regiao_id"]],
        height=0.55,
    )
    for i, v in enumerate(r["espaco_livre_alunos"]):
        ax.text(v / 1e3, i, f"  {fmt_int(v / 1e3)} mil", va="center", fontsize=8, color="#333333")
    _estilo_eixo(ax)
    ax.grid(axis="x", color="#ececec")
    ax.set_xlim(0, max(1.0, r["espaco_livre_alunos"].max() / 1e3 * 1.3))
    ax.set_xlabel("Espaço livre (mil alunos)", fontsize=8, color="#666666")
    ax.set_title("Espaço livre por região", fontsize=10, color="#282828", loc="left")
    fig.tight_layout()
    return _png(fig, dpi=200)


# --------------------------------------------------------------------------- páginas


def _capa(pdf: _UltraPDF, d: DadosRelatorio, assets: dict[str, bytes | None]) -> None:
    """Capa do Relatório Municipal (mesmas posições), com o master no lugar do município."""
    pdf.add_page()
    tem_foto = assets.get("capa") is not None
    _draw_full_page_background(pdf, assets.get("capa"), _NAVY_CAPA)
    x, w, al = (478.0, 446.0, "L") if tem_foto else (60.0, W - 120, "C")
    y0 = 300.0 if tem_foto else 170.0
    pdf.set_text_color(*BRANCO)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(x, y0)
    pdf.cell(w, 16, _t("ESTUDO DE ÁREA · RELATÓRIO DO MASTER"), align=al)
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_xy(x, y0 + 24)
    pdf.cell(w, 32, _t("Potencial de Expansão do Território"), align=al)
    pdf.set_font("Helvetica", "", 12.5)
    pdf.set_xy(x, y0 + 64)
    pdf.multi_cell(
        w,
        17,
        _t("Onde abrir mais entre as suas regiões e as metas para os próximos 12 meses"),
        align=al,
    )
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_xy(x, y0 + 112)
    pdf.cell(w, 20, _t(d.master.nome_exibicao), align=al)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_xy(x, y0 + 136)
    ref = d.data_ref
    pdf.cell(
        w,
        16,
        _t(
            f"{trimestre_de(d.gerado_em)} · unidades até {MESES_LONGOS[ref.month - 1]} de {ref.year}"
        ),
        align=al,
    )
    if d.teste:
        pdf.set_xy(W - 210, 24)
        pdf.set_draw_color(*BRANCO)
        pdf.set_line_width(1.2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(170, 24, _t("VERSÃO DE TESTE"), border=1, align="C")
        pdf.set_line_width(0.2)


def _visao_geral(pdf: _UltraPDF, d: DadosRelatorio, assets: dict[str, bytes | None]) -> None:
    y = _pagina(pdf, assets, "Estudo de Área - Visão Geral do território", d)
    pdf.set_xy(MARGEM, y + 2)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*TINTA_2)
    pdf.cell(
        W - 2 * MARGEM,
        16,
        _t(
            f"Para o estudo de {d.master.nome_exibicao} foram considerados os municípios das suas regiões, "
            "em sequência de população:"
        ),
        align="C",
    )
    b = d.bairros
    n_ocup = int(b["ocupado"].sum()) if len(b) else 0
    pop = float(d.visao["populacao"].sum()) if len(d.visao) else float("nan")
    cards = [
        (
            TURQUESA,
            fmt_int(len(d.master.regioes)),
            "Região no contrato" if len(d.master.regioes) == 1 else "Regiões no contrato",
        ),
        (ROXO, fmt_int(n_ocup), "Bairros com Ultra"),
        (LARANJA, fmt_int(len(b)), "Bairros mapeados"),
        (MAGENTA, fmt_pop(pop), "Habitantes no território"),
    ]
    gap = 22.0
    cw = (W - 2 * MARGEM - 3 * gap) / 4
    for i, (cor, valor, rot) in enumerate(cards):
        _kpi(pdf, MARGEM + i * (cw + gap), y + 30, cw, cor, valor, rot)
    yt = y + 136
    if d.visao.empty:
        _nota(pdf, yt, "Sem a base de setores do Censo para este território.")
        return
    cols: list[Coluna] = [
        ("Região", 128, "L"),
        ("Município", 156, "L"),
        ("Área km²", 62, "R"),
        ("População", 80, "R"),
        ("Renda média domiciliar", 92, "R"),
        ("Densidade (hab/km²)", 76, "R"),
        ("Espaço livre (alunos)", 84, "R"),
        ("Bairros mapeados", 70, "R"),
        ("Bairros com Ultra", 70, "R"),
    ]
    por_mun = (
        b.groupby(["uf", "cod_municipio"]).agg(n_b=("localidade", "size"), n_o=("ocupado", "sum"))
        if len(b)
        else pd.DataFrame(columns=["n_b", "n_o"])
    )
    n_linhas = 16
    linhas = []
    for r in d.visao.head(n_linhas).itertuples():
        k = (r.uf, r.cod_municipio)
        nb, no = (por_mun.loc[k, "n_b"], por_mun.loc[k, "n_o"]) if k in por_mun.index else (0, 0)
        linhas.append(
            [
                str(r.regiao_nome),
                f"{r.nome_municipio}",
                fmt_dec(r.area_km2, 0),
                fmt_int(r.populacao),
                fmt_renda(r.renda_dom),
                fmt_int(r.densidade),
                fmt_int(r.espaco_livre),
                fmt_int(nb),
                fmt_int(no) if no else "-",
            ]
        )
    x0 = (W - sum(c[1] for c in cols)) / 2
    yfim = _tabela(pdf, x0, yt, cols, linhas, alt_linha=15.5, fonte=8)
    resto = len(d.visao) - n_linhas
    if resto > 0:
        _nota(
            pdf,
            yfim + 4,
            f"E mais {resto} municípios menores no território, somados nos cartões acima.",
            x=x0,
        )


def _por_area(d: DadosRelatorio) -> list[tuple[DadosRelatorio, str | None]]:
    """O relatório com duas ou mais áreas desenha o mapa e os mapas de calor UMA VEZ POR ÁREA
    (19/11/2026, Juan, no DF/GO: o território junto é Goiás quase inteiro, com o DF minúsculo no
    meio; "um por área: DF e Goiás"). Com uma área, o relatório inteiro, como antes."""
    if len(d.master.regioes) < 2:
        return [(d, None)]
    return [(_recorte_da_area(d, r.id), r.nome) for r in d.master.regioes]


def _recorte_da_area(d: DadosRelatorio, regiao_id: str) -> DadosRelatorio:
    """Os dados dos mapas de UMA área: os hexágonos, os setores, as unidades e os municípios dela."""

    def so(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or "regiao_id" not in df.columns:
            return df
        return df[df["regiao_id"] == regiao_id].reset_index(drop=True)

    regiao = next(r for r in d.master.regioes if r.id == regiao_id)
    return replace(
        d,
        master=replace(d.master, regioes=(regiao,)),
        hexes=so(d.hexes),
        setores_mapa=so(d.setores_mapa),
        ultra_pontos=so(d.ultra_pontos),
        visao=so(d.visao),
        contornos={k: v for k, v in d.contornos.items() if k == regiao_id},
    )


def _titulo_da_area(titulo: str, area: str | None) -> str:
    return f"{titulo}: {area}" if area else titulo


def _pagina_mapa(
    pdf: _UltraPDF, d: DadosRelatorio, assets: dict[str, bytes | None], area: str | None = None
) -> None:
    y = _pagina(
        pdf, assets, _titulo_da_area("Estudo de Área - Mapa do território", area), d, cor=MAGENTA
    )
    if d.hexes.empty:
        _nota(pdf, y, "Sem hexágonos do motor para este território.")
        return
    pino = pino_ultra(d.assets_dir)
    # A legenda numa linha acima do mapa, centrada (18/11, Juan: os nomes dentro do mapa
    # atrapalhavam; "coloque uma legenda em cima"); quebra em mais linhas se não couber.
    itens = legenda_do_mapa(d)
    pdf.set_font("Helvetica", "B", 10.5)
    larg_max = W - 2 * MARGEM
    linhas: list[list[tuple[tuple[str, str], float]]] = [[]]
    usado = 0.0
    for it in itens:
        w_it = 14 + 6 + pdf.get_string_width(_t(it[1])) + 24
        if linhas[-1] and usado + w_it > larg_max:
            linhas.append([])
            usado = 0.0
        linhas[-1].append((it, w_it))
        usado += w_it
    yl = y + 2
    for linha in linhas:
        xl = (W - (sum(w for _, w in linha) - 24)) / 2
        for (tipo, rotulo), w_it in linha:
            if tipo == "unidades":
                if pino:
                    pdf.image(io.BytesIO(pino), x=xl, y=yl, w=14, h=14)
                else:
                    pdf.set_fill_color(32, 32, 32)
                    pdf.rect(xl + 3, yl + 3, 8, 8, style="F", round_corners=True, corner_radius=4)
            else:
                # O limite da área: o traço do contorno do mapa.
                pdf.set_draw_color(*TINTA_2)
                pdf.set_line_width(1.6)
                pdf.line(xl, yl + 7, xl + 14, yl + 7)
            pdf.set_xy(xl + 20, yl)
            pdf.set_font("Helvetica", "B", 10.5)
            pdf.set_text_color(*TINTA)
            pdf.cell(w_it - 20, 14, _t(rotulo))
            xl += w_it
        yl += 20
    # O mapa, centrado, embaixo da legenda.
    topo = yl + 6
    caixa_w, caixa_h = 700.0, (H - 62 - 12) - topo - 16 - 4
    img = _mapa_territorio(d, (caixa_w / 72, caixa_h / 72), pino)
    x = (W - caixa_w) / 2
    _rounded_panel(pdf, x - 8, topo, caixa_w + 16, caixa_h + 16, border_rgb=MAGENTA)
    pdf.image(img, x=x, y=topo + 8, w=caixa_w, h=caixa_h, keep_aspect_ratio=True)
    _faixa_inferior(pdf, d.master.nome_exibicao)


def legenda_do_mapa(d: DadosRelatorio) -> list[tuple[str, str]]:
    """Os itens da legenda do mapa do território: ("limite", nome da área) e ("unidades",
    "Unidades").

    Uma logo só, "Unidades" (19/11/2026, Juan: "tem dois ícones da Ultra; deixe apenas
    'Unidades', junte os dois"), e só quando há unidade no mapa (Ceará e Maranhão, sem nenhuma
    Ultra, mostravam a logo à toa)."""
    itens = [("limite", r.nome) for r in d.master.regioes]
    if not d.ultra_pontos.empty:
        itens.append(("unidades", "Unidades"))
    return itens


def _pagina_calor(
    pdf: _UltraPDF, d: DadosRelatorio, assets: dict[str, bytes | None], area: str | None = None
) -> None:
    y = _pagina(pdf, assets, _titulo_da_area("Estudo de Área - Mapas de calor", area), d)
    if d.setores_mapa.empty or d.hexes.empty:
        _nota(pdf, y, "Sem a base de setores do Censo para os mapas de calor deste território.")
        return
    s, hx = d.setores_mapa, d.hexes
    peso = s["domicilios"].where(s["renda_dom"].notna())
    renda_media = (
        float((s["renda_dom"] * peso).sum() / peso.sum()) if peso.sum() > 0 else float("nan")
    )
    dens_media = (
        float(d.visao["populacao"].sum() / d.visao["area_km2"].sum())
        if len(d.visao)
        else float("nan")
    )
    # Réguas, cores e números do motor (17/11, Juan): as faixas absolutas de
    # `dashboard/constants.py`, as mesmas do mapa e do Relatório Pontual, no lugar dos quintis.
    conc_1km = hx["n_concorrentes_1km"] if "n_concorrentes_1km" in hx else hx["n_concorrentes"]
    paineis = [
        (
            "Renda média domiciliar",
            f"Resultado: {fmt_renda(renda_media)}",
            "R$ por domicílio/mês",
            s,
            classes_do_motor(s["renda_dom"], RENDA_MEDIA_DOMICILIAR_BANDS),
            None,
        ),
        (
            "Densidade demográfica",
            f"Resultado: {fmt_int(dens_media)} hab/km²",
            "hab/km²",
            s,
            classes_do_motor(s["densidade"].where(s["densidade"] > 0), DENSIDADE_POP_BANDS),
            None,
        ),
        (
            "Espaço livre (alunos por hexágono)",
            f"Resultado: {fmt_int(hx['espaco_livre'].sum())} alunos",
            "alunos por hexágono",
            hx,
            classes_do_motor(hx["espaco_livre"], OFERTA_DISPONIVEL_ALUNOS_BANDS),
            list(hx["hex_id"]),
        ),
        (
            "Academias concorrentes",
            f"Resultado: {fmt_int(hx['n_concorrentes'].sum())} academias",
            "academias que alcançam o hexágono (1 km)",
            hx,
            classes_do_motor(conc_1km, CONC_1KM_BANDS, zero="nenhuma"),
            list(hx["hex_id"]),
        ),
    ]
    pw, ph = 420.0, 196.0
    larg_mapa, larg_leg = 268.0, 140.0
    for i, (titulo, resultado, unidade, base, (cores, legenda), hex_ids) in enumerate(paineis):
        x = MARGEM + (i % 2) * (pw + 48)
        yy = y + (i // 2) * (ph + 30)
        pdf.set_xy(x, yy)
        pdf.set_font("Helvetica", "B", 10.5)
        pdf.set_text_color(*TINTA_2)
        pdf.cell(pw / 2, 14, _t(titulo))
        pdf.set_xy(x + pw / 2, yy)
        pdf.cell(pw / 2, 14, _t(resultado), align="R")
        if titulo.startswith("Academias") and not (hx["n_concorrentes"] > 0).any():
            _nota(
                pdf, yy + 30, "Nenhuma academia concorrente mapeada no território.", largura=pw, x=x
            )
            continue
        img = _mapa_calor(
            base["lng"], base["lat"], cores, (larg_mapa / 72, (ph - 18) / 72), hex_ids
        )
        pdf.image(img, x=x, y=yy + 16, w=larg_mapa, h=ph - 18, keep_aspect_ratio=True)
        _legenda_faixas(pdf, x + larg_mapa + 12, yy + 28, larg_leg, unidade, legenda)
    _nota(
        pdf,
        H - 58,
        "Faixas e cores do motor, as mesmas do mapa e do Relatório Pontual. Renda: média domiciliar do Censo 2022 "
        "atualizada pela PNAD. Espaço livre: o residual do motor. Concorrentes: academias de cadeia que alcançam o "
        "hexágono num raio de 1 km (o resultado conta cada academia uma vez).",
    )


def _pagina_regioes(pdf: _UltraPDF, d: DadosRelatorio, assets: dict[str, bytes | None]) -> None:
    y = _pagina(pdf, assets, "Onde abrir mais: comparação entre as suas regiões", d, cor=MAGENTA)
    pdf.set_xy(MARGEM, y)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*TINTA_2)
    pdf.multi_cell(
        W - 2 * MARGEM,
        15,
        _t(
            "Espaço livre = mercado fitness da região menos o que concorrentes e Ultra já atendem. Quanto mais espaço "
            "livre, mais unidades a região comporta antes de saturar."
        ),
    )
    y = pdf.get_y() + 12
    if d.regioes.empty:
        _nota(pdf, y, d.master.nota or "Sem regiões definidas para este master.")
        return
    cols: list[Coluna] = [
        ("Região", 130, "L"),
        ("Tipo", 78, "L"),
        ("População", 72, "R"),
        ("Mercado fitness (alunos)", 80, "R"),
        ("Já ocupado", 56, "R"),
        ("Espaço livre (alunos)", 76, "R"),
        ("Concor- rentes", 52, "R"),
        ("Ultra (abertas e em impl.)", 52, "R"),
    ]
    linhas = [
        [
            r.regiao_nome,
            r.tipo,
            fmt_int(r.populacao),
            fmt_int(r.mercado_alunos),
            fmt_pct(r.pct_ocupado),
            fmt_int(r.espaco_livre_alunos),
            fmt_int(r.n_concorrentes),
            fmt_int(r.n_ultra),
        ]
        for r in d.regioes.itertuples()
    ]
    yfim = _tabela(
        pdf,
        MARGEM,
        y,
        cols,
        linhas,
        alt_linha=28,
        cor_cabecalho=MAGENTA,
        negrito_primeira=True,
        fundo_linha=lambda i: (232, 246, 245) if i == 0 else BRANCO,
    )
    larg_tab = sum(c[1] for c in cols)
    pdf.image(
        _grafico_regioes(d.regioes, _cor_regiao(d)),
        x=MARGEM + larg_tab + 18,
        y=y - 4,
        w=W - 2 * MARGEM - larg_tab - 18,
    )
    texto = (
        "A linha destacada é a região com mais espaço livre. O espaço livre serve para comparar as regiões entre si; "
        "não é previsão de quantos alunos uma unidade nova terá, que depende do imóvel e da operação. "
    )
    texto += " ".join(f"{r.regiao_nome}: {r.nota}" for r in d.regioes.itertuples() if r.nota)
    _nota(pdf, max(yfim + 14, y + 200), texto + f" Mercado: base do motor de {d.snapshot_mercado}.")


def _pagina_bairros(pdf: _UltraPDF, d: DadosRelatorio, assets: dict[str, bytes | None]) -> None:
    y = _pagina(pdf, assets, "Estudo de Área - Bairros", d)
    # Legenda do estudo do RJ: quadrado da cor + rótulo.
    for k, (cor, rot) in enumerate(
        (
            (ROXO_OCUPADO, "Ocupado (Ultra aberta ou em implantação)"),
            (VERDE_DISPONIVEL, "Disponível"),
        )
    ):
        x = W - MARGEM - 370 + k * 250
        pdf.set_fill_color(*cor)
        pdf.rect(x, y + 3, 11, 11, "F")
        pdf.set_xy(x + 16, y)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*TINTA_2)
        pdf.cell(230, 17, _t(rot))
    pdf.set_xy(MARGEM, y)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*TINTA_2)
    pdf.cell(400, 17, _t("Os bairros mais populosos do território"))
    b = d.bairros.head(21)
    cols: list[Coluna] = [
        ("UF", 34, "C"),
        ("Município", 150, "L"),
        ("Bairro", 210, "L"),
        ("Região", 140, "L"),
        ("População", 80, "R"),
        ("Renda média domiciliar", 96, "R"),
        ("Densidade (hab/km²)", 90, "R"),
    ]
    linhas = [
        [
            r.uf,
            r.nome_municipio,
            r.localidade,
            str(r.regiao_nome),
            fmt_int(r.populacao),
            fmt_renda(r.renda_dom),
            fmt_int(r.densidade),
        ]
        for r in b.itertuples()
    ]
    ocup = list(b["ocupado"])
    x0 = (W - sum(c[1] for c in cols)) / 2
    _tabela(
        pdf,
        x0,
        y + 26,
        cols,
        linhas,
        alt_linha=16.5,
        fonte=8,
        fundo_linha=lambda i: ROXO_OCUPADO if ocup[i] else VERDE_DISPONIVEL,
    )
    _nota(
        pdf,
        H - 54,
        "Bairro pelo CNEFE 2022, com a malha do IBGE como reserva (a mesma regra do Relatório Municipal); onde a prefeitura "
        "não tem bairro oficial, aparece o distrito ou a região de planejamento. Ocupado = há unidade Ultra no bairro, aberta ou em implantação (cadastro do motor).",
    )


def _card_top(
    pdf: _UltraPDF,
    x: float,
    y: float,
    w: float,
    pos: int,
    cor: tuple[int, int, int],
    nome: str,
    destaque: str,
    rotulo_destaque: str,
    itens: list[tuple[str, str, tuple[int, int, int]]],
) -> None:
    """Cartão "#1" do estudo do RJ: tarja com a posição, nome, número grande e três linhas de apoio."""
    h = 290.0
    pdf.set_fill_color(*BRANCO)
    pdf.set_draw_color(*BORDA)
    pdf.rect(x, y, w, h, "DF")
    pdf.set_fill_color(*cor)
    pdf.rect(x, y, w, 26, "F")
    pdf.set_text_color(*BRANCO)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_xy(x, y + 3)
    pdf.cell(w, 20, f"#{pos}", align="C")
    pdf.set_text_color(*TINTA)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(x + 8, y + 36)
    pdf.multi_cell(w - 16, 13, _t(nome), align="C", max_line_height=13)
    pdf.set_text_color(*cor)
    pdf.set_font("Helvetica", "B", 22 if len(destaque) <= 9 else 18)
    pdf.set_xy(x, y + 78)
    pdf.cell(w, 28, _t(destaque), align="C")
    pdf.set_text_color(*TINTA_3)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_xy(x, y + 108)
    pdf.cell(w, 11, _t(rotulo_destaque), align="C")
    pdf.set_draw_color(*BORDA)
    pdf.line(x + 10, y + 126, x + w - 10, y + 126)
    yy = y + 134
    for rot, valor, cor_v in itens:
        pdf.set_xy(x + 10, yy)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*TINTA_3)
        pdf.cell(w - 20, 10, _t(rot))
        pdf.set_xy(x + 10, yy + 11)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*cor_v)
        pdf.multi_cell(w - 20, 14, _t(valor), align="L")
        yy = max(yy + 36, pdf.get_y() + 8)


def top5_bairros(bairros: pd.DataFrame, por: str) -> pd.DataFrame:
    """Os 5 bairros SEM Ultra do slide "Top 5": por população (a ordem de `area.bairros`) ou por
    renda domiciliar, entre os de `POP_MIN_BAIRRO` habitantes ou mais. Uma regra só para o slide e
    para o cartão "Alta renda" da Análise de Oportunidade, que a tela do master também mostra. Sem
    bairros (master sem região, ou sem a malha do Censo), nada, sem quebrar."""
    if bairros.empty:
        return bairros
    disp = bairros[~bairros["ocupado"]]
    if por == "populacao":
        return disp.head(5)
    return (
        disp[disp["populacao"] >= POP_MIN_BAIRRO].sort_values("renda_dom", ascending=False).head(5)
    )


def _pagina_top5(
    pdf: _UltraPDF, d: DadosRelatorio, assets: dict[str, bytes | None], por: str
) -> None:
    if por == "populacao":
        titulo, cor = "Top 5 bairros sem Ultra - maior população", TURQUESA
    else:
        titulo, cor = "Top 5 bairros sem Ultra - maior renda", MAGENTA
    top = top5_bairros(d.bairros, por)
    y = _pagina(pdf, assets, f"Estudo de Área - {titulo}", d, cor=cor)
    if top.empty:
        _nota(pdf, y, "Sem bairros sem Ultra com dados neste território.")
        return
    gap = 16.0
    cw = (W - 2 * MARGEM - 4 * gap) / 5
    for i, r in enumerate(top.itertuples()):
        x = MARGEM + i * (cw + gap)
        if por == "populacao":
            destaque, rot = fmt_int(r.populacao), "habitantes"
            itens = [("Renda média domiciliar", fmt_renda(r.renda_dom), MAGENTA)]
        else:
            destaque, rot = fmt_renda(r.renda_dom), "renda média domiciliar"
            itens = [("População", fmt_int(r.populacao), TURQUESA)]
        itens += [
            ("Densidade", f"{fmt_int(r.densidade)} hab/km²", LARANJA),
            ("Município", f"{r.nome_municipio} ({r.uf})", TINTA),
        ]
        _card_top(pdf, x, y + 24, cw, i + 1, cor, r.localidade, destaque, rot, itens)
    nota = "Só bairros sem unidade Ultra aberta ou em implantação. " + (
        "Ordem por população."
        if por == "populacao"
        else f"Ordem por renda, entre os bairros com {fmt_int(POP_MIN_BAIRRO)} habitantes ou mais."
    )
    _nota(pdf, y + 330, nota)


def _bloco_meta(pdf: _UltraPDF, d: DadosRelatorio, y: float) -> float:
    """Meta do contrato: o % atingido, uma barra até a meta e o ritmo que falta. Devolve o y final."""
    mc = d.meta_contrato
    h = 124.0
    _rounded_panel(pdf, MARGEM, y, W - 2 * MARGEM, h, border_rgb=TURQUESA)
    q = mc.get("quantidade")
    prazo = mc.get("prazo")
    prazo_txt = prazo.strftime("%d/%m/%Y") if prazo is not None else "sem prazo informado"
    if not q:
        pdf.set_xy(MARGEM + 20, y + 22)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(*TURQUESA)
        pdf.cell(600, 18, _t("Meta do contrato"))
        pdf.set_xy(MARGEM + 20, y + 48)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(*TINTA_2)
        pdf.multi_cell(
            W - 2 * MARGEM - 40,
            15,
            _t(
                f"A quantidade de aberturas do contrato não está informada para este master (prazo: {prazo_txt}). "
                f"Hoje: {mc.get('n_contam', 0)} unidades abertas contam para a meta e {mc.get('n_pipeline', 0)} estão "
                "assinadas no pipeline."
            ),
            align="L",
        )
        return y + h
    pct = mc["pct"]
    # Número grande à esquerda.
    pdf.set_xy(MARGEM + 16, y + 16)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*TINTA_2)
    pdf.cell(170, 14, _t(f"Meta do contrato até {prazo_txt}"))
    pdf.set_xy(MARGEM + 16, y + 34)
    pdf.set_font("Helvetica", "B", 40)
    pdf.set_text_color(*TURQUESA)
    pdf.cell(170, 44, _t(fmt_pct(pct)))
    pdf.set_xy(MARGEM + 16, y + 82)
    pdf.set_font("Helvetica", "", 10.5)
    pdf.set_text_color(*TINTA_2)
    pdf.multi_cell(170, 13, _t(f"{mc['n_contam']} de {q} unidades abertas"), align="L")
    # Barra até a meta: abertas (cheio), pipeline (claro) e a marca da meta.
    x0, larg = MARGEM + 210, 470.0
    escala = larg / max(q, mc["n_contam"] + mc["n_pipeline"], 1)
    yb = y + 42
    pdf.set_fill_color(236, 236, 236)
    pdf.rect(x0, yb, larg, 22, "F")
    pdf.set_fill_color(*TURQUESA)
    pdf.rect(x0, yb, mc["n_contam"] * escala, 22, "F")
    if mc["n_pipeline"]:
        pdf.set_fill_color(160, 218, 214)
        pdf.rect(x0 + mc["n_contam"] * escala, yb, mc["n_pipeline"] * escala, 22, "F")
    xm = x0 + q * escala
    pdf.set_draw_color(*TINTA)
    pdf.set_line_width(2)
    pdf.line(xm, yb - 8, xm, yb + 30)
    pdf.set_line_width(0.2)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*TINTA)
    pdf.set_xy(xm - 60, yb - 22)
    pdf.cell(120, 12, _t(f"meta: {q}"), align="C")
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*TINTA_2)
    pdf.set_xy(x0, yb + 32)
    pdf.cell(
        larg,
        12,
        _t(
            f"Abertas que contam: {mc['n_contam']}   ·   Assinadas no pipeline: +{mc['n_pipeline']} "
            f"(com elas, {fmt_pct(mc['pct_com_pipeline'])} da meta)"
        ),
    )
    # Leitura à direita.
    xr = x0 + larg + 20
    pdf.set_xy(xr, y + 18)
    if mc["faltam"] == 0:
        texto = f"Meta atingida. Faltam {mc['meses_ate_prazo']} meses para o prazo."
    else:
        texto = (
            f"Faltam {mc['faltam']} unidades em {mc['meses_ate_prazo']} meses: {fmt_dec(mc['ritmo_necessario_mes'])} "
            f"por mês, contra {fmt_dec(mc['ritmo_atual_mes'])} por mês nos últimos 12 meses."
        )
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*TURQUESA if mc["faltam"] == 0 else MAGENTA)
    pdf.multi_cell(W - MARGEM - xr - 12, 14, _t(texto), align="L")
    pdf.set_xy(MARGEM + 16, y + h - 20)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*TINTA_3)
    pdf.cell(
        W - 2 * MARGEM - 32,
        10,
        _t(f"Contam para a meta: {', '.join(mc['contam']) or 'nenhuma'}. {mc.get('fonte', '')}"),
    )
    return y + h


def _pagina_metas(pdf: _UltraPDF, d: DadosRelatorio, assets: dict[str, bytes | None]) -> None:
    mr = d.metas_resumo
    y = _pagina(pdf, assets, "Meta do contrato e metas propostas", d, cor=MAGENTA)
    y = _bloco_meta(pdf, d, y) + 14
    pdf.set_xy(MARGEM, y)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*TINTA)
    pdf.cell(W - 2 * MARGEM, 16, _t("Proposta para os próximos 12 meses, por região"))
    pdf.set_xy(MARGEM, y + 18)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*TINTA_2)
    pdf.multi_cell(
        W - 2 * MARGEM,
        12,
        _t(
            f"Abrir o que já está assinado ({mr['n_pipeline']}) e iniciar novas buscas no ritmo de aberturas dos "
            f"últimos 12 meses ({mr['aberturas_12m']}, mínimo 1), distribuídas pelo espaço livre que sobra depois do pipeline."
        ),
        align="L",
    )
    y = pdf.get_y() + 8
    cols: list[Coluna] = [
        ("Região", 150, "L"),
        ("Tipo", 90, "L"),
        ("Unidades abertas", 76, "R"),
        ("Assinadas (pipeline)", 86, "R"),
        ("Espaço livre após o pipeline (alunos)", 120, "R"),
        ("Novas buscas propostas", 96, "R"),
    ]
    linhas = [
        [
            m.regiao_nome,
            m.tipo,
            fmt_int(m.abertas),
            fmt_int(m.pipeline),
            fmt_int(m.espaco_apos_pipeline),
            fmt_int(m.novas_buscas),
        ]
        for m in d.metas.itertuples()
    ]
    buscas = list(d.metas["novas_buscas"]) if len(d.metas) else []
    yfim = _tabela(
        pdf,
        MARGEM,
        y,
        cols,
        linhas,
        alt_linha=28,
        cor_cabecalho=MAGENTA,
        negrito_primeira=True,
        fundo_linha=lambda i: (232, 246, 245) if buscas[i] > 0 else BRANCO,
    )
    x0 = MARGEM + sum(c[1] for c in cols) + 24
    _rounded_panel(pdf, x0 - 10, y - 6, W - MARGEM - x0 + 10, 190, border_rgb=TURQUESA)
    pdf.set_xy(x0, y)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*TURQUESA)
    pdf.cell(0, 16, _t("Assinadas no pipeline"))
    yy = y + 22
    nomes = {r.id: r.nome for r in d.master.regioes}
    for p in mr["pipeline"]:
        pdf.set_xy(x0, yy)
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(*TINTA)
        pdf.multi_cell(W - MARGEM - x0 - 10, 12, _t(p["unidade"]))
        pdf.set_xy(x0, pdf.get_y())
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*TINTA_2)
        pdf.cell(0, 12, _t(f"{p['fase']} · {nomes.get(p['regiao_id'], 'região não identificada')}"))
        yy = pdf.get_y() + 16
    _nota(
        pdf,
        max(yfim, y + 190) + 10,
        "Proposta para discussão com a Ultra: parte do ritmo real de aberturas e do espaço livre de cada região. "
        "Não substitui nem altera a meta do contrato.",
    )


def _texto_ocupacao(d: DadosRelatorio, ocupado: float, n_ultra: int, n_meus: int) -> str:
    """Quanto do mercado já é atendido, com a régua do país: 32% sozinho não diz se é muito ou pouco."""
    b = d.bairros
    texto = f"Redes e Ultra atendem {fmt_pct(ocupado)} do mercado fitness do território. "
    ref = d.referencia_ocupacao
    if ref:
        texto += (
            f"Para comparar: {ref['mais_ocupada']} é a cidade grande mais ocupada do país, com "
            f"{fmt_pct(ref['mais_ocupada_pct'])}, e a mediana das cidades grandes é {fmt_pct(ref['mediana'])}. "
        )
    texto += (
        "Academias independentes não entram na conta, então a ocupação real é maior. "
        f"Ultra: {fmt_int(n_ultra)} unidades, abertas ou em implantação ({fmt_int(n_meus)} suas), em "
        f"{fmt_int(int(b['ocupado'].sum()) if len(b) else 0)} dos {fmt_int(len(b))} bairros."
    )
    return texto


#: Cor de cada cartão da Análise de Oportunidade, por chave (a tela do master usa a mesma chave).
CORES_ANALISE: dict[str, tuple[int, int, int]] = {
    "magenta": MAGENTA,
    "turquesa": TURQUESA,
    "laranja": LARANJA,
    "roxo": ROXO,
}


def cartoes_da_analise(d: DadosRelatorio) -> list[tuple[str, str, str]]:
    """(cor, título, texto) dos cartões da Análise de Oportunidade: o "onde expandir" do fim do
    estudo do RJ. A aba Expansão da tela do master mostra os mesmos (BLK-MASTERS-04)."""
    b = d.bairros
    disp = b[~b["ocupado"]] if len(b) else b
    n_ultra = len(d.ultra_pontos)
    n_meus = int(d.ultra_pontos["do_master"].sum()) if n_ultra else 0
    ocupado = (
        (d.regioes["consumo_concorrentes"].sum() + d.regioes["consumo_ultra"].sum())
        / d.regioes["mercado_alunos"].sum()
        if len(d.regioes) and d.regioes["mercado_alunos"].sum() > 0
        else float("nan")
    )
    nome = d.master.nome_exibicao
    cards: list[tuple[str, str, str]] = [
        (
            "magenta",
            "Ocupação do mercado",
            _texto_ocupacao(d, ocupado, n_ultra, n_meus),
        ),
    ]
    if len(d.regioes):
        r1 = d.regioes.iloc[0]
        cards.append(
            (
                "turquesa",
                "Potencial total",
                f"{fmt_int(d.regioes['espaco_livre_alunos'].sum() / 1e3)} mil alunos de espaço livre nas "
                f"{len(d.regioes)} regiões de {nome}; a maior parte em {r1['regiao_nome']} "
                f"({fmt_int(r1['espaco_livre_alunos'] / 1e3)} mil).",
            )
        )
    if len(disp):
        top = disp.iloc[0]
        cards.append(
            (
                "laranja",
                "Maior bairro sem Ultra",
                f"{top['localidade']} ({top['nome_municipio']}) lidera com {fmt_int(top['populacao'])} habitantes, "
                "o bairro mais populoso do território ainda sem unidade Ultra.",
            )
        )
        ricos = top5_bairros(b, "renda").head(3)
        if len(ricos):
            lista = ", ".join(
                f"{r.localidade} ({fmt_renda(r.renda_dom)})" for r in ricos.itertuples()
            )
            cards.append(
                (
                    "roxo",
                    "Alta renda",
                    f"{lista} são os bairros sem Ultra de maior renda domiciliar.",
                )
            )
    return cards


def _pagina_analise(pdf: _UltraPDF, d: DadosRelatorio, assets: dict[str, bytes | None]) -> None:
    """Análise de oportunidade: os quatro cartões do fim do estudo do RJ."""
    y = _pagina(pdf, assets, "Análise de Oportunidade", d)
    cw, ch, gap = (W - 2 * MARGEM - 24) / 2, 190.0, 24.0
    for i, (chave, titulo, texto) in enumerate(cartoes_da_analise(d)):
        cor = CORES_ANALISE[chave]
        x = MARGEM + (i % 2) * (cw + gap)
        yy = y + 8 + (i // 2) * (ch + 18)
        pdf.set_fill_color(*BRANCO)
        pdf.set_draw_color(*BORDA)
        pdf.rect(x, yy, cw, ch, "DF")
        pdf.set_fill_color(*cor)
        pdf.rect(x, yy, 5, ch, "F")
        pdf.set_xy(x + 20, yy + 16)
        pdf.set_font("Helvetica", "B", 17)
        pdf.set_text_color(*cor)
        pdf.cell(cw - 40, 22, _t(titulo))
        pdf.set_xy(x + 20, yy + 50)
        pdf.set_font("Helvetica", "", 11.5)
        pdf.set_text_color(*TINTA_2)
        pdf.multi_cell(cw - 40, 16, _t(texto), align="L")


#: "antigo" = os 10 slides; "novo" = os 10 + os slides a mais; "so_novos" = só os slides a mais (teste).
MODELOS = ("antigo", "novo", "so_novos")


def gerar_pdf(d: DadosRelatorio, modelo: str = "antigo") -> bytes:
    if modelo not in MODELOS:
        raise ValueError(f"modelo desconhecido: {modelo!r} (use {MODELOS})")
    assets = _load_branding_assets(d.assets_dir)
    pdf = _UltraPDF()
    pdf.set_compression(True)  # imagens dos mapas: sem compressão o arquivo passa de 20 MB
    pdf.set_title(_t(f"Relatório trimestral - {d.master.nome_exibicao}"))
    pdf.set_author("Motor de Expansão - Ultra Academia")
    if modelo == "so_novos":
        from motor_expansao.masters.relatorio_funcionamento import _slide_metas, gerar_slides

        gerar_slides(pdf, d, assets)
        # As metas depois dos slides novos (17/11, Juan), no slide refeito.
        _slide_metas(pdf, d, assets)
        return _finalizar(pdf, d, tem_capa=False)
    _capa(pdf, d, assets)
    if d.tem_area:
        _visao_geral(pdf, d, assets)
        # Com duas ou mais áreas, o mapa e os mapas de calor de cada uma, em seguida.
        for da, area in _por_area(d):
            _pagina_mapa(pdf, da, assets, area)
            _pagina_calor(pdf, da, assets, area)
    _pagina_regioes(pdf, d, assets)
    if d.tem_area:
        _pagina_bairros(pdf, d, assets)
        _pagina_top5(pdf, d, assets, "populacao")
        _pagina_top5(pdf, d, assets, "renda")
    if modelo == "antigo":
        _pagina_metas(pdf, d, assets)
    if d.tem_area:
        _pagina_analise(pdf, d, assets)
    if modelo == "novo":
        from motor_expansao.masters.relatorio_funcionamento import _slide_metas, gerar_slides

        gerar_slides(pdf, d, assets)
        # No modelo novo, as metas fecham o relatório, no slide refeito (17/11, Juan: depois dos
        # slides de funcionamento; a meta em % por trimestre, embaixo e em destaque).
        _slide_metas(pdf, d, assets)
    return _finalizar(pdf, d, tem_capa=True)


def _finalizar(pdf: _UltraPDF, d: DadosRelatorio, tem_capa: bool) -> bytes:
    """Marca d'água em todas as páginas, menos a capa."""
    marca = _t(
        f"Ultra Academia | Relatório do master {d.master.nome_exibicao} | {trimestre_de(d.gerado_em)} | uso restrito"
    )
    for n in range(2 if tem_capa else 1, pdf.pages_count + 1):
        pdf.page = n
        pdf_base.desenhar_marca(pdf, marca)
    return bytes(pdf.output())
