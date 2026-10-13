"""Estilo único dos gráficos do relatório BLK-UNI.

Todos os scripts de gráfico importam daqui (``from _estilo import *``).
Figura 16:9 (12 x 6,75 pol.), 200 dpi, PNG, fundo branco, DejaVu Sans.

Regras de cor:
- TEXTO para todo texto; CINZA / CINZA_CLARO para contexto;
- CINZA_ESCURO para a "regra atual";
- DESTAQUE (uma cor só) para o que importa;
- valor real sempre como losango REAL;
- selo âmbar (AMBAR) no canto superior direito para EXPLORATÓRIO / PRELIMINAR /
  EM AVALIAÇÃO / ILUSTRAÇÃO / DESCRITIVO; chip CONFIRMADO na cor de destaque.

Uso típico::

    fig = figura()
    y_topo = cabecalho(fig, "Título = mensagem", "subtítulo", selo="EXPLORATÓRIO")
    y_base = rodape(fig, "Fonte: ... · N = 18", nota="...")
    ax = fig.add_axes([0.2, y_base + 0.05, 0.75, y_topo - y_base - 0.1])
    ...
    conferir("mediana do erro", calculado, esperado, tol=0.005)
    salvar(fig, "s1_regra_achata", df)
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import matplotlib.colors  # noqa: E402
import matplotlib.lines  # noqa: E402
import matplotlib.patches  # noqa: E402
import matplotlib.ticker  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402

try:  # saída UTF-8 no console do Windows
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

# --------------------------------------------------------------------------- caminhos
SCRIPTS = Path(__file__).resolve().parent
RELATORIO = SCRIPTS.parent
UNI = RELATORIO.parent  # data/analysis/uni
ANALYSIS = UNI.parent  # data/analysis
POI = ANALYSIS / "poi"
REPO = ANALYSIS.parent.parent
GRAFICOS = RELATORIO / "graficos"
DADOS = RELATORIO / "dados"

# --------------------------------------------------------------------------- cores
TEXTO = "#1F2328"
CINZA = "#8C959F"  # contexto
CINZA_CLARO = "#D8DEE4"  # contexto leve, linhas de ligação
CINZA_ESCURO = "#57606A"  # regra atual
DESTAQUE = "#0B6E99"  # o que importa (uma cor só)
AMBAR = "#9A6700"  # selo de cautela
REAL = "#1F2328"  # valor real (losango)
FUNDO = "#FFFFFF"
GRADE = "#EAEEF2"


def misturar(cor: str, t: float, fundo: str = "#FFFFFF") -> str:
    """Mistura `cor` com o fundo: t = 1 é a cor pura, t = 0 é o fundo."""
    c = np.array(matplotlib.colors.to_rgb(cor))
    f = np.array(matplotlib.colors.to_rgb(fundo))
    return matplotlib.colors.to_hex(f + t * (c - f))


DESTAQUE_CLARO = misturar(DESTAQUE, 0.45)  # destaque claro (segunda camada)
DESTAQUE_MUITO_CLARO = misturar(DESTAQUE, 0.12)  # faixas de fundo
CINZA_FUNDO = "#F4F6F8"  # fundo de caixas de texto
CINZA_MUITO_CLARO = "#EEF1F4"  # faixas de fundo neutras

# --------------------------------------------------------------------------- figura
LARGURA_POL, ALTURA_POL, DPI = 12.0, 6.75, 200
MARGEM_X = 0.035  # margem lateral (fração da figura)

TAM_TITULO = 16
TAM_SUBTITULO = 10.5
TAM_TEXTO = 10
TAM_NOTA = 9
TAM_RODAPE = 8

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": TAM_TEXTO,
        "text.color": TEXTO,
        "axes.labelcolor": TEXTO,
        "axes.edgecolor": CINZA_CLARO,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "axes.facecolor": FUNDO,
        "axes.labelsize": TAM_NOTA + 0.5,
        "xtick.color": CINZA_ESCURO,
        "ytick.color": CINZA_ESCURO,
        "xtick.labelsize": TAM_NOTA,
        "ytick.labelsize": TAM_NOTA,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "grid.color": GRADE,
        "grid.linewidth": 0.7,
        "figure.facecolor": FUNDO,
        "savefig.facecolor": FUNDO,
        "legend.frameon": False,
        "legend.fontsize": TAM_NOTA,
        "hatch.color": CINZA,
        "hatch.linewidth": 0.6,
        "text.parse_math": False,  # "R$ 20 mil" não vira fórmula
    }
)

MENOS = "−"  # sinal de menos tipográfico


def figura() -> plt.Figure:
    return plt.figure(figsize=(LARGURA_POL, ALTURA_POL), dpi=DPI)


# --------------------------------------------------------------------------- medição de texto
def _renderer(fig):
    return fig.canvas.get_renderer()


def largura_texto(fig, texto: str, tamanho: float, peso: str = "normal") -> float:
    """Largura de uma linha de texto, em fração da largura da figura."""
    r = _renderer(fig)
    fp = FontProperties(family="DejaVu Sans", size=tamanho, weight=peso)
    w, _, _ = r.get_text_width_height_descent(texto, fp, ismath=False)
    return w / (fig.get_figwidth() * fig.dpi)


def quebrar(fig, texto: str, largura: float, tamanho: float, peso: str = "normal") -> str:
    """Quebra `texto` em linhas que caibam em `largura` (fração da figura).

    Respeita quebras de linha já existentes ("\\n")."""
    saida = []
    for paragrafo in texto.split("\n"):
        palavras = paragrafo.split(" ")
        linha = ""
        for p in palavras:
            cand = p if not linha else linha + " " + p
            if largura_texto(fig, cand, tamanho, peso) <= largura or not linha:
                linha = cand
            else:
                saida.append(linha)
                linha = p
        saida.append(linha)
    return "\n".join(saida)


def altura_linhas(fig, n_linhas: int, tamanho: float, entrelinha: float = 1.25) -> float:
    """Altura aproximada de n linhas de texto, em fração da altura da figura."""
    return n_linhas * tamanho * entrelinha / 72 / fig.get_figheight()


# --------------------------------------------------------------------------- selos e chips
def _cracha(fig, x_dir: float, y_topo: float, texto: str, cor: str) -> float:
    """Desenha um crachá (texto branco em caixa colorida) alinhado à direita em x_dir.
    Devolve a largura ocupada (fração da figura)."""
    t = fig.text(
        x_dir,
        y_topo,
        texto,
        ha="right",
        va="top",
        fontsize=8.5,
        fontweight="bold",
        color="white",
        bbox=dict(boxstyle="round,pad=0.45,rounding_size=0.6", fc=cor, ec="none"),
    )
    bb = t.get_window_extent(renderer=_renderer(fig)).transformed(fig.transFigure.inverted())
    return bb.width + 0.012


def selos(fig, selo: str | None = None, chip: str | None = None, y_topo: float = 0.962) -> float:
    """Selo âmbar (cautela) e/ou chip CONFIRMADO no canto superior direito.

    Devolve a largura total reservada à direita (fração da figura)."""
    x = 1 - MARGEM_X
    usado = 0.0
    if selo:
        w = _cracha(fig, x, y_topo, selo, AMBAR)
        x -= w + 0.008
        usado += w + 0.008
    if chip:
        w = _cracha(fig, x, y_topo, chip, DESTAQUE)
        usado += w + 0.008
    return usado


# --------------------------------------------------------------------------- cabeçalho e rodapé
def cabecalho(
    fig,
    titulo: str,
    subtitulo: str = "",
    selo: str | None = None,
    chip: str | None = None,
) -> float:
    """Título (= mensagem, negrito), subtítulo e selos. Devolve o y (fração) da base do bloco."""
    reservado = selos(fig, selo, chip)
    x0 = MARGEM_X
    largura = 1 - 2 * MARGEM_X - (reservado + 0.01 if reservado else 0)
    tam = TAM_TITULO
    while tam > 13 and largura_texto(fig, titulo, tam, "bold") > largura:
        tam -= 0.5
    if largura_texto(fig, titulo, tam, "bold") <= largura:
        txt = titulo
    else:  # duas linhas equilibradas, em corpo 15
        tam = 15
        palavras = titulo.split(" ")
        melhor = None
        for k in range(1, len(palavras)):
            a, b = " ".join(palavras[:k]), " ".join(palavras[k:])
            wa, wb = largura_texto(fig, a, tam, "bold"), largura_texto(fig, b, tam, "bold")
            if max(wa, wb) <= largura and (melhor is None or max(wa, wb) < melhor[0]):
                melhor = (max(wa, wb), a + "\n" + b)
        txt = melhor[1] if melhor else quebrar(fig, titulo, largura, tam, "bold")
    n = txt.count("\n") + 1
    y = 0.965
    fig.text(x0, y, txt, ha="left", va="top", fontsize=tam, fontweight="bold", color=TEXTO, linespacing=1.15)
    y -= altura_linhas(fig, n, tam, 1.2) + 0.012
    if subtitulo:
        largura_sub = 1 - 2 * MARGEM_X
        sub = quebrar(fig, subtitulo, largura_sub, TAM_SUBTITULO)
        ns = sub.count("\n") + 1
        fig.text(x0, y, sub, ha="left", va="top", fontsize=TAM_SUBTITULO, color=CINZA_ESCURO, linespacing=1.2)
        y -= altura_linhas(fig, ns, TAM_SUBTITULO, 1.25)
    return y - 0.01


def rodape(fig, fonte: str, nota: str | None = None) -> float:
    """Rodapé 'Fonte: … · N = …' e, acima dele, uma nota opcional. Devolve o y do topo do bloco."""
    largura = 1 - 2 * MARGEM_X
    y = 0.018
    f = quebrar(fig, fonte, largura, TAM_RODAPE)
    nf = f.count("\n") + 1
    fig.text(MARGEM_X, y, f, ha="left", va="bottom", fontsize=TAM_RODAPE, color=CINZA_ESCURO, linespacing=1.25)
    y += altura_linhas(fig, nf, TAM_RODAPE, 1.3) + 0.006
    if nota:
        n = quebrar(fig, nota, largura, TAM_RODAPE + 0.5)
        nn = n.count("\n") + 1
        fig.text(MARGEM_X, y, n, ha="left", va="bottom", fontsize=TAM_RODAPE + 0.5, color=TEXTO, linespacing=1.25)
        y += altura_linhas(fig, nn, TAM_RODAPE + 0.5, 1.3) + 0.004
    # fio separador acima do rodapé
    fig.add_artist(
        matplotlib.lines.Line2D([MARGEM_X, 1 - MARGEM_X], [y + 0.004, y + 0.004], color=CINZA_CLARO, lw=0.8)
    )
    return y + 0.01


def caixa(
    fig,
    x: float,
    y_topo: float,
    largura: float,
    texto: str,
    tamanho: float = TAM_NOTA,
    fundo: str = CINZA_FUNDO,
    borda: str | None = None,
    cor_texto: str = TEXTO,
    titulo: str | None = None,
    cor_titulo: str = TEXTO,
    barra: str | None = None,
) -> float:
    """Caixa de texto com fundo claro (fração da figura). Devolve o y da base da caixa."""
    pad = 0.012
    corpo = quebrar(fig, texto, largura - 2 * pad, tamanho)
    n = corpo.count("\n") + 1
    h = altura_linhas(fig, n, tamanho, 1.3)
    ht = 0.0
    tt = None
    if titulo:
        tt = quebrar(fig, titulo, largura - 2 * pad, tamanho + 0.5, "bold")
        ht = altura_linhas(fig, tt.count("\n") + 1, tamanho + 0.5, 1.3) + 0.006
    altura = h + ht + 2 * pad
    fig.add_artist(
        matplotlib.patches.FancyBboxPatch(
            (x, y_topo - altura),
            largura,
            altura,
            boxstyle="round,pad=0,rounding_size=0.008",
            transform=fig.transFigure,
            fc=fundo,
            ec=borda or "none",
            lw=0.9,
        )
    )
    if barra:
        fig.add_artist(
            matplotlib.patches.Rectangle(
                (x, y_topo - altura), 0.004, altura, transform=fig.transFigure, fc=barra, ec="none"
            )
        )
    y = y_topo - pad
    if tt:
        fig.text(x + pad, y, tt, ha="left", va="top", fontsize=tamanho + 0.5, fontweight="bold",
                 color=cor_titulo, linespacing=1.3)
        y -= ht
    fig.text(x + pad, y, corpo, ha="left", va="top", fontsize=tamanho, color=cor_texto, linespacing=1.3)
    return y_topo - altura


def eixo_limpo(ax, grade: str | None = "x"):
    """Espinhas discretas, grade leve só no eixo pedido ('x', 'y', 'both' ou None)."""
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(CINZA_CLARO)
    if grade:
        ax.grid(True, axis=grade, color=GRADE, lw=0.7, zorder=0)
        ax.set_axisbelow(True)
    ax.tick_params(colors=CINZA_ESCURO, length=0)


# --------------------------------------------------------------------------- números pt-BR
def num(v: float, casas: int = 0, sinal: bool = False) -> str:
    """Número em pt-BR: vírgula decimal, ponto de milhar, menos tipográfico."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    s = f"{abs(v):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if v < 0 and float(s.replace(".", "").replace(",", ".")) != 0:
        return MENOS + s
    return ("+" + s) if (sinal and v > 0) else s


def pct(v: float, casas: int = 0, sinal: bool = False) -> str:
    """Percentual (v já em pontos percentuais: -17 -> '−17%')."""
    return num(v, casas, sinal) + "%"


def mil(v_reais: float, casas: int = 0, prefixo: bool = True) -> str:
    """Reais -> 'R$ 183 mil'."""
    s = num(v_reais / 1000, casas)
    return f"R$ {s} mil" if prefixo else f"{s} mil"


def formatador_num(casas: int = 0, sufixo: str = "", sinal: bool = False):
    return matplotlib.ticker.FuncFormatter(lambda v, _: num(v, casas, sinal) + sufixo)


# --------------------------------------------------------------------------- nomes de unidade
_ACENTOS = {
    "ACLIMACAO": "Aclimação", "ADMINISTRACAO": "Administração", "AGUAS": "Águas", "AMERICAS": "Américas",
    "ANDRE": "André", "ANTONIO": "Antônio", "APURA": "Apurá", "BOQUEIRAO": "Boqueirão",
    "BOTANICO": "Botânico", "BRASILANDIA": "Brasilândia", "BUTANTA": "Butantã", "CAMBUI": "Cambuí",
    "CARAPICUIBA": "Carapicuíba", "CEILANDIA": "Ceilândia", "CESARIO": "Cesário", "CHACARA": "Chácara",
    "FAMILIA": "Família", "GONCALO": "Gonçalo", "GUARUJA": "Guarujá", "ICARAI": "Icaraí",
    "JUNDIAI": "Jundiaí", "NUCLEO": "Núcleo", "PARANOA": "Paranoá", "PATIO": "Pátio",
    "PAULINIA": "Paulínia", "PICARRAS": "Piçarras", "SAO": "São", "STO": "Sto.", "TAUBATE": "Taubaté",
    "UNAI": "Unaí", "VALPARAISO": "Valparaíso",
}
_SIGLAS = {"CPA", "POA", "QNM24", "QNM33", "QNN32", "II", "III"}
_MINUSCULAS = {"DE", "DA", "DAS", "DO", "DOS", "E"}


def nome_unidade(nome: str, uf: str | None = None) -> str:
    """'BUTANTA', 'SP' -> 'Butantã (SP)'. Camada de rótulo: não altera o valor bruto."""
    palavras = []
    for i, p in enumerate(str(nome).strip().split()):
        up = p.upper()
        if up in _ACENTOS:
            palavras.append(_ACENTOS[up])
        elif up in _SIGLAS:
            palavras.append(up)
        elif up in _MINUSCULAS and i > 0:
            palavras.append(up.lower())
        else:
            palavras.append(p.capitalize())
    s = " ".join(palavras)
    return f"{s} ({uf})" if uf else s


def nome_de_id(unidade_id: str) -> str:
    """'recanto-das-emas-df' -> 'Recanto das Emas (DF)'."""
    partes = unidade_id.split("-")
    uf = partes[-1].upper()
    return nome_unidade(" ".join(partes[:-1]).upper(), uf)


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


# --------------------------------------------------------------------------- leitura de tabelas .md
def tabela_md(texto: str, cabecalho_contem: str) -> pd.DataFrame:
    """Lê a primeira tabela Markdown cujo cabeçalho contém `cabecalho_contem`."""
    linhas = texto.splitlines()
    for i, ln in enumerate(linhas):
        if ln.strip().startswith("|") and cabecalho_contem in ln:
            cab = [c.strip() for c in ln.strip().strip("|").split("|")]
            dados = []
            for ln2 in linhas[i + 2:]:
                if not ln2.strip().startswith("|"):
                    break
                dados.append([c.strip() for c in ln2.strip().strip("|").split("|")])
            return pd.DataFrame(dados, columns=cab)
    raise ValueError(f"tabela com '{cabecalho_contem}' não encontrada")


def numero_br(s: str) -> float:
    """'1,352' (milhar en) ou '1.352' / '0,74' / '-17%' -> float. Heurística para os .md do estudo."""
    s = str(s).strip().replace("−", "-").replace("%", "").replace("R$", "").strip()
    if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", s):  # milhar com vírgula (formato en)
        return float(s.replace(",", ""))
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", s):  # milhar com ponto (formato br)
        return float(s.replace(".", "").replace(",", "."))
    return float(s.replace(",", "."))


# --------------------------------------------------------------------------- conferência e gravação
CONFERENCIAS: list[dict] = []


def conferir(item: str, calculado: float, esperado: float, tol: float = 0.0) -> float:
    """Compara o valor calculado com o esperado pelo roteiro. Imprime OK ou AVISO e registra."""
    ok = abs(float(calculado) - float(esperado)) <= tol + 1e-12
    CONFERENCIAS.append({"item": item, "calculado": calculado, "esperado": esperado, "ok": ok})
    print(("OK    " if ok else "AVISO ") + f"{item}: calculado {calculado} · esperado {esperado}")
    return calculado


def salvar(fig, id_: str, dados: pd.DataFrame) -> None:
    """Grava graficos/<id>.png e dados/<id>.csv (sep=';', utf-8-sig).

    Se alguma conferência divergiu, o CSV ganha a coluna `aviso_divergencia`."""
    GRAFICOS.mkdir(parents=True, exist_ok=True)
    DADOS.mkdir(parents=True, exist_ok=True)
    png = GRAFICOS / f"{id_}.png"
    fig.savefig(png, dpi=DPI, facecolor=FUNDO)
    plt.close(fig)
    df = dados.copy()
    falhas = [c for c in CONFERENCIAS if not c["ok"]]
    if falhas:
        df["aviso_divergencia"] = " | ".join(
            f"{c['item']}: calculado {c['calculado']} x esperado {c['esperado']}" for c in falhas
        )
    csv = DADOS / f"{id_}.csv"
    df.to_csv(csv, sep=";", encoding="utf-8-sig", index=False)
    print(f"gravado: {png}")
    print(f"gravado: {csv}")
    print(f"conferências: {len(CONFERENCIAS) - len(falhas)} ok, {len(falhas)} aviso(s)")
