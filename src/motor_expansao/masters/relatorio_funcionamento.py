"""Slide a mais do modelo novo (BLK-MASTERS-02, rascunho): "Comportamento da região".

Entra depois dos 10 slides do modelo antigo, um por região com unidades suficientes, no layout B4
escolhido no Claude Design (16/11/2026): os traços que a pesquisa viu andar com o faturamento no
DF, medidos na região e agrupados pela leitura. Em cima, cartões com número grande para o que
ANDA com o faturamento na região (junto ou ao contrário); embaixo, uma linha cinza com o que
ficou sem relação clara; depois, a faixa curta do fluxo pendular e uma nota de duas linhas.

Número grande = valor típico das unidades acima da média da rede sobre o das abaixo ("2,6x
maior", "4,3x menor"; abaixo de 1,25x vira %). Só dados, sem veredito: nenhuma unidade é
nomeada. Região sem dado fica fora (citada na nota); sem nenhuma, a seção não sai
(`so_com_dados`). Dados em `masters.funcionamento`. READ-ONLY sobre o M1.
"""

from __future__ import annotations

import io
from dataclasses import replace
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from motor_expansao.masters import funcionamento as F
from motor_expansao.masters.meta import fase_de_exibicao, ordem_da_fase
from motor_expansao.masters.relatorio_pdf import (
    BRANCO,
    MAGENTA,
    MARGEM,
    TINTA,
    TOPO,
    TURQUESA,
    Coluna,
    DadosRelatorio,
    H,
    W,
    _estilo_eixo,
    _pagina,
    _png,
    _t,
    _tabela,
    _UltraPDF,
    fmt_dec,
    fmt_int,
    fmt_pct,
    fmt_renda,
    trimestre_de,
)

MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

# Paleta do protótipo B4 (cores da Ultra; textos com contraste >= 4,5:1 sobre o fundo).
TINTA_2 = (85, 85, 85)
BORDA_CARTAO = (228, 228, 232)
FUNDO_SEM_RELACAO = (239, 239, 241)
SEPARADOR = (210, 210, 214)
COR_ABAIXO = (184, 188, 194)
COR_OUTRAS = (169, 173, 179)
NAVY = (30, 28, 58)

#: Estilo de cada leitura: número grande, selo (fundo, texto) e ícone (fundo do círculo, traço).
ESTILOS: dict[str, dict[str, Any]] = {
    "anda junto": {
        "numero": (0, 135, 127),
        "selo": ((224, 244, 242), (0, 112, 106)),
        "icone": ((224, 244, 242), "#00706A"),
    },
    "anda ao contrário": {
        "numero": MAGENTA,
        "selo": ((248, 227, 238), (156, 44, 111)),
        "icone": ((248, 227, 238), "#9C2C6F"),
    },
}
ESTILO_NEUTRO: dict[str, Any] = {
    "numero": (107, 107, 107),
    "selo": ((237, 237, 237), TINTA_2),
    "icone": ((237, 237, 237), "#555555"),
}

#: Ícones de traço (24x24, contorno), os mesmos do protótipo; o fpdf2 desenha SVG direto.
ICONES = {
    "iso_renda_pc__pe_15": '<circle cx="12" cy="12" r="9"/><path d="M14.5 9.2c-.5-1-1.5-1.5-2.6-1.5-1.5 '
    '0-2.6.8-2.6 2s1.1 1.7 2.6 2 2.7.9 2.7 2.2-1.2 2-2.7 2c-1.2 0-2.3-.6-2.8-1.6M12 6v1.7M12 16v1.8"/>',
    "iso_pop__carro_5": '<circle cx="9" cy="8" r="3.2"/><path d="M3.5 19c.6-3 2.8-5 5.5-5s4.9 2 5.5 5"/>'
    '<circle cx="17" cy="9" r="2.4"/><path d="M16 14.2c2.4.2 4 1.9 4.5 4.3"/>',
    "tam_metragem_m2": '<rect x="3.5" y="3.5" width="17" height="17" rx="1.5"/>'
    '<path d="M3.5 9h4M3.5 14.5h4M9 3.5v4M14.5 3.5v4"/>',
    "rampa_ativos_m3": '<path d="M4 19.5h16"/><path d="M5 16l4.5-5 3.5 3 6-7"/><path d="M15 7h4v4"/>',
    "cad_mod_studios": '<path d="M6.5 6.5v11M17.5 6.5v11M3.5 9.5v5M20.5 9.5v5M6.5 12h11"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "predio": '<path d="M4 20.5h16"/><rect x="6" y="4" width="8" height="16.5" rx="1"/>'
    '<path d="M14 9h4v11.5M9 8h2M9 11.5h2M9 15h2"/>',
}

#: Traços que só entram no slide quando diferenciam as que faturam mais (fora da linha cinza).
SO_QUANDO_DIFERENCIA = frozenset({"cad_mod_studios"})

#: O padrão em palavras, por traço, nas que faturam acima: (anda junto, anda ao contrário).
PADRAO_FRASE: dict[str, tuple[str, str]] = {
    "iso_pop__carro_5": ("mais população em 5 min de carro", "menos população em 5 min de carro"),
    "iso_renda_pc__pe_15": (
        "mais renda por pessoa em 15 min a pé",
        "menos renda por pessoa em 15 min a pé",
    ),
    "tam_metragem_m2": ("mais metragem", "menos metragem"),
    "cad_mod_studios": ("estúdio com mais frequência", "estúdio com menos frequência"),
    "rampa_ativos_m3": ("mais alunos no 3º mês de vida", "menos alunos no 3º mês de vida"),
}

#: Cores das linhas dos gráficos de mês de vida: a região (cheia) e o resto da rede (tracejada).
COR_LINHA_REGIAO = (0, 167, 157)
COR_LINHA_RESTO = (154, 158, 165)

#: Abaixo desta razão (acima / abaixo) o número grande sai em %, não em "x vezes".
RAZAO_EM_VEZES = 1.25


def _janela(fn: dict[str, Any]) -> str:
    ini, fim = (pd.Period(p, freq="M") for p in fn["janela"].split(".."))
    return f"{MESES_CURTOS[ini.month - 1]}/{ini.year} a {MESES_CURTOS[fim.month - 1]}/{fim.year}"


def _fmt_traco(formato: str, v: float) -> str:
    if pd.isna(v):
        return "-"
    if formato == "reais":
        return fmt_renda(v)
    if formato == "mil":
        return f"{fmt_int(v / 1e3)} mil"
    if formato == "m2":
        return f"{fmt_int(v)} m²"
    if formato == "sim_nao":
        return fmt_pct(v)
    return fmt_int(v)


def _rotulo_leitura(t: dict[str, Any]) -> str:
    """O selo em palavras: "maior, fatura mais" em vez de estatística.

    "Ao contrário" sai pelo avesso, sempre do lado que fatura mais: "menor, fatura mais" (e não
    "maior, fatura menos", que soa como "ter mais é ruim").
    """
    sim_nao = t.get("formato") == "sim_nao"
    return {
        "anda junto": "com, fatura mais" if sim_nao else "maior, fatura mais",
        "anda ao contrário": "sem, fatura mais" if sim_nao else "menor, fatura mais",
        "sem relação clara": "sem diferença clara",
    }.get(t["leitura"], t["leitura"])


def _acerto_do_selo(t: dict[str, Any]) -> float:
    """Em quantas comparações de duas unidades o selo acontece (ao contrário: o complemento)."""
    a = t.get("acerto", float("nan"))
    return 1 - a if t["leitura"] == "anda ao contrário" and pd.notna(a) else a


def comparacao(t: dict[str, Any]) -> tuple[str, str] | None:
    """Número grande e o complemento: acima da média sobre abaixo ("2,6x" + "maior nas que...").

    Sim/não (estúdio): a parte das unidades com o traço, "mais comum" ou "menos comum". None quando
    um dos lados tem menos de `N_MIN_GRUPO` unidades ou não há valor.
    """
    a, b = t["acima"], t["abaixo"]
    if t["n_acima"] < F.N_MIN_GRUPO or t["n_abaixo"] < F.N_MIN_GRUPO:
        return None
    sim_nao = t.get("formato") == "sim_nao"
    if sim_nao and pd.notna(a) and pd.notna(b) and b == 0 and a > 0:
        return fmt_pct(a), "têm, contra nenhuma das que faturam abaixo"
    if not (pd.notna(a) and pd.notna(b) and a > 0 and b > 0):
        return None
    razao = a / b
    if sim_nao:
        mais, menos = "mais comum", "menos comum"
    else:
        mais, menos = "maior", "menor"
    vezes, lado = (razao, mais) if razao >= 1 else (1 / razao, menos)
    if vezes >= RAZAO_EM_VEZES:
        return f"{fmt_dec(vezes)}×", f"{lado} nas que faturam acima"
    pct = round((vezes - 1) * 100)
    if pct == 0:
        return "=", "igual nos dois lados"
    return f"{pct}%", f"{lado} nas que faturam acima"


def _icone(pdf: _UltraPDF, chave: str, x: float, y: float, lado: float, cor: str) -> None:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
        f'stroke="{cor}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{ICONES[chave]}</svg>'
    )
    pdf.image(io.BytesIO(svg.encode("utf-8")), x=x, y=y, w=lado, h=lado)


def _selo(
    pdf: _UltraPDF,
    x: float,
    y: float,
    leitura: str,
    cores: tuple[tuple[int, int, int], tuple[int, int, int]] | None = None,
) -> float:
    """Selo arredondado com a leitura (ou outro texto, com `cores` = fundo, texto); devolve a largura."""
    fundo, texto = cores or ESTILOS.get(leitura, ESTILO_NEUTRO)["selo"]
    pdf.set_font("Helvetica", "B", 10)
    larg = pdf.get_string_width(_t(leitura)) + 18
    pdf.set_fill_color(*fundo)
    pdf.rect(x, y, larg, 20, style="F", round_corners=True, corner_radius=9)
    pdf.set_xy(x, y)
    pdf.set_text_color(*texto)
    pdf.cell(larg, 20, _t(leitura), align="C")
    return larg


#: A contagem embaixo do selo, por traço: a metade da região onde estão (junto, ao contrário).
CONTAGEM_FRASE: dict[str, tuple[str, str]] = {
    "iso_pop__carro_5": ("mais população", "menos população"),
    "iso_renda_pc__pe_15": ("mais renda", "menos renda"),
    "tam_metragem_m2": ("mais metragem", "menos metragem"),
    "rampa_ativos_m3": ("mais alunos no 3º mês", "menos alunos no 3º mês"),
}
#: Sim/não: o nome do traço depois de "têm" / "não têm".
SIM_NAO_OBJETO = {"cad_mod_studios": "estúdio"}


def frase_contagem(t: dict[str, Any]) -> str | None:
    """O número real embaixo do selo: "**8 das 11** que faturam acima estão na metade das unidades
    da região com menos população".

    Conta unidades, não comparações: "75 de cada 100" (pares de unidades) era lido como 75 unidades
    da região (Juan, 17/11). None sem selo de relação ou sem unidade acima com o dado.
    """
    k, n = t.get("do_lado"), t.get("n_acima", 0)
    if k is None or not n:
        return None
    junto = t["leitura"] == "anda junto"
    base = f"**{k} das {n}** que faturam acima"
    if t.get("formato") == "sim_nao":
        objeto = SIM_NAO_OBJETO.get(t["col"], t["rotulo"].lower())
        return f"{base} {'têm' if junto else 'não têm'} {objeto}"
    # Sem "típica" (17/11): "abaixo da mediana" vira "na metade com menos".
    lados = CONTAGEM_FRASE.get(t["col"], ("valor maior", "valor menor"))
    return f"{base} estão na metade das unidades da região com {lados[0] if junto else lados[1]}"


def _altura_contagem(pdf: _UltraPDF, larg: float, t: dict[str, Any]) -> float:
    frase = frase_contagem(t)
    if not frase:
        return 0.0
    pdf.set_font("Helvetica", "", 10)
    lin = pdf.multi_cell(larg, 13, _t(frase), dry_run=True, output="LINES", markdown=True)
    return 13.0 * (len(lin) if isinstance(lin, list) else 1)


def _contagem_txt(pdf: _UltraPDF, x: float, y: float, larg: float, t: dict[str, Any]) -> None:
    frase = frase_contagem(t)
    if not frase:
        return
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*TINTA_2)
    pdf.set_xy(x, y)
    pdf.multi_cell(larg, 13, _t(frase), align="L", markdown=True)


def _selo_leitura(pdf: _UltraPDF, x: float, y: float, t: dict[str, Any]) -> float:
    """O selo do traço: cor pela leitura, texto em palavras."""
    return _selo(pdf, x, y, _rotulo_leitura(t), ESTILOS.get(t["leitura"], ESTILO_NEUTRO)["selo"])


def _bolinha(pdf: _UltraPDF, x: float, y: float, cor: tuple[int, int, int], d: float = 8) -> None:
    pdf.set_fill_color(*cor)
    pdf.ellipse(x, y, d, d, "F")


def _cartao(
    pdf: _UltraPDF,
    x: float,
    y: float,
    larg: float,
    alt: float,
    t: dict[str, Any],
    h_pe: float | None = None,
) -> None:
    """Cartão de um traço; `h_pe` = altura da contagem igual em todos (selos alinhados)."""
    est = ESTILOS.get(t["leitura"], ESTILO_NEUTRO)
    pdf.set_fill_color(*BRANCO)
    pdf.set_draw_color(*BORDA_CARTAO)
    pdf.set_line_width(0.8)
    pdf.rect(x, y, larg, alt, style="DF", round_corners=True, corner_radius=12)
    # Ícone no círculo e o nome do traço (até 2 linhas).
    fundo_icone, cor_icone = est["icone"]
    pdf.set_fill_color(*fundo_icone)
    pdf.ellipse(x + 18, y + 16, 32, 32, "F")
    _icone(pdf, t["col"], x + 25, y + 23, 18, cor_icone)
    pdf.set_font("Helvetica", "B", 12.5 if larg > 260 else 11.5)
    pdf.set_text_color(*TINTA)
    w_nome = larg - 58 - 8
    linhas = pdf.multi_cell(w_nome, 14, _t(t["rotulo"]), dry_run=True, output="LINES")
    n_lin = len(linhas) if isinstance(linhas, list) else 1
    pdf.set_xy(x + 58, y + 32 - 7 * n_lin)
    pdf.multi_cell(w_nome, 14, _t(t["rotulo"]), align="L")
    # Número grande (acima sobre abaixo) e os valores: no meio, entre o nome e o pé; maiores no
    # cartão alto.
    alto = alt >= 280
    h_num = 64.0 if alto else 56.0
    comp = comparacao(t)
    numero, complemento = (
        comp if comp else ("-", f"menos de {F.N_MIN_GRUPO} unidades num dos lados")
    )
    # No cartão alto o complemento vai embaixo do número, numa linha (ao lado, quebrava em 4).
    pdf.set_font("Helvetica", "", 11 if alto else 10.5)
    linhas_comp = pdf.multi_cell(larg - 36, 14, _t(complemento), dry_run=True, output="LINES")
    h_comp = 14.0 * (len(linhas_comp) if isinstance(linhas_comp, list) else 1)
    h_bloco = h_num + (h_comp + 12 if alto else 0) + 16
    # Pé do cartão (de baixo para cima): a contagem e o selo.
    h_frase = h_pe if h_pe is not None else _altura_contagem(pdf, larg - 36, t)
    y_frase = y + alt - 16 - h_frase
    y_selo = y_frase - 6 - 20
    topo_area, fim_area = y + 56, y_selo - 8
    y_num = topo_area + max((fim_area - topo_area - h_bloco) / 2, 2.0)
    pdf.set_font("Helvetica", "B", (54 if larg > 260 else 46) + (8 if alto else 0))
    pdf.set_text_color(*est["numero"])
    w_num = pdf.get_string_width(_t(numero))
    pdf.set_xy(x + 18, y_num)
    pdf.cell(w_num, h_num, _t(numero))
    pdf.set_font("Helvetica", "", 11 if alto else 10.5)
    pdf.set_text_color(*TINTA_2)
    if alto:
        pdf.set_xy(x + 18, y_num + h_num - 4)
        pdf.multi_cell(larg - 36, 14, _t(complemento), align="L")
        y_val = y_num + h_num + h_comp + 8
    else:
        resto = larg - 18 - w_num - 10 - 14
        pdf.set_xy(x + 18 + w_num + 10, y_num + h_num / 2 - 12)
        pdf.multi_cell(
            max(resto, 60), 13, _t(complemento.replace(" faturam", "\nfaturam", 1)), align="L"
        )
        y_val = y_num + h_num
    # Os dois valores típicos.
    pdf.set_font("Helvetica", "B", 13 if alto else 12)
    pdf.set_text_color(*TINTA)
    _bolinha(pdf, x + 18, y_val + 3, TURQUESA)
    v_acima = _t(_fmt_traco(t["formato"], t["acima"]))
    pdf.set_xy(x + 30, y_val - 1)
    pdf.cell(pdf.get_string_width(v_acima) + 4, 14, v_acima)
    x_ab = x + 30 + pdf.get_string_width(v_acima) + 18
    _bolinha(pdf, x_ab, y_val + 3, COR_ABAIXO)
    pdf.set_font("Helvetica", "", 13 if alto else 12)
    pdf.set_text_color(*TINTA_2)
    pdf.set_xy(x_ab + 12, y_val - 1)
    pdf.cell(120, 14, _t(_fmt_traco(t["formato"], t["abaixo"])))
    # No pé: o selo e, embaixo, o número real (quantas das que faturam acima estão desse lado).
    _selo_leitura(pdf, x + 18, y_selo, t)
    _contagem_txt(pdf, x + 18, y_frase, larg - 36, t)


def _linha_sem_relacao(pdf: _UltraPDF, y: float, tracos: list[dict[str, Any]]) -> float:
    """A linha cinza com o que ficou sem relação clara (ou sem leitura); devolve o fim."""
    alt = 40.0 + 18.0 * (len(tracos) - 1)
    pdf.set_fill_color(*FUNDO_SEM_RELACAO)
    pdf.rect(MARGEM, y, W - 2 * MARGEM, alt, style="F", round_corners=True, corner_radius=10)
    pdf.set_xy(MARGEM + 16, y + 13)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*TINTA_2)
    pdf.cell(170, 14, _t("Sem diferença clara na região"))
    pdf.set_draw_color(*SEPARADOR)
    pdf.set_line_width(0.8)
    pdf.line(MARGEM + 196, y + 11, MARGEM + 196, y + alt - 11)
    for i, t in enumerate(tracos):
        yy = y + 11 + 18 * i
        _icone(pdf, t["col"], MARGEM + 210, yy, 16, "#555555")
        comp = comparacao(t)
        if t["leitura"] == "poucas unidades":
            detalhe = f"só {t['n']} unidades com o dado (mínimo {F.N_MIN_RELACAO})"
        elif comp:
            detalhe = (
                f"{comp[0]} {comp[1]} ({_fmt_traco(t['formato'], t['acima'])} × "
                f"{_fmt_traco(t['formato'], t['abaixo'])})"
            )
        else:
            detalhe = f"menos de {F.N_MIN_GRUPO} unidades num dos lados"
        pdf.set_xy(MARGEM + 232, yy)
        pdf.set_font("Helvetica", "", 11.5)
        pdf.set_text_color(*TINTA)
        pdf.cell(600, 16, _t(f"**{t['rotulo']}** · {detalhe}"), markdown=True)
    return y + alt


def tracos_do_slide(
    regiao: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(cartões, linha cinza): o que anda com o faturamento e o resto que aparece no slide."""
    com = [t for t in regiao["tracos"] if t["leitura"] in ("anda junto", "anda ao contrário")]
    sem = [t for t in regiao["tracos"] if t not in com and t["col"] not in SO_QUANDO_DIFERENCIA]
    return com, sem


def frases_padrao(regiao: dict[str, Any]) -> list[tuple[str, str]]:
    """O padrão encontrado em frases, na ordem dos cartões: ("**menos população ...** (4,3× menor)", leitura).

    O lado vem do selo (junto = mais, ao contrário = menos); o número entre parênteses é o do
    cartão, e sai quando falta ou aponta para o outro lado.
    """
    frases = []
    for t in tracos_do_slide(regiao)[0]:
        lados = PADRAO_FRASE.get(t["col"])
        if lados is None:
            continue
        junto = t["leitura"] == "anda junto"
        frase = f"**{lados[0] if junto else lados[1]}**"
        comp = comparacao(t)
        if comp and " nas que faturam acima" in comp[1]:
            lado = comp[1].split(" nas que")[0]
            if lado in (("maior", "mais comum") if junto else ("menor", "menos comum")):
                frase += f" ({comp[0]} {lado})"
        frases.append((frase, t["leitura"]))
    return frases


def _slide_apresentacao(
    pdf: _UltraPDF,
    d: DadosRelatorio,
    assets: dict[str, bytes | None],
    regiao: dict[str, Any],
) -> None:
    """Abre a região: a análise feita, o padrão encontrado e quantas unidades entraram na conta."""
    fn = d.funcionamento
    _pagina(pdf, assets, f"Padrões das unidades: {regiao['rotulo']}", d, cor=MAGENTA)
    # Coluna da esquerda: a região, a frase da pesquisa e o padrão.
    larg_esq = 500.0
    y = TOPO + 50
    pdf.set_xy(MARGEM, y)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(0, 135, 127)
    pdf.cell(larg_esq, 12, _t('PESQUISA "PADRÕES DAS UNIDADES"'))
    pdf.set_xy(MARGEM, y + 16)
    pdf.set_font("Helvetica", "B", 34)
    pdf.set_text_color(*NAVY)
    pdf.cell(larg_esq, 40, _t(regiao["rotulo"]))
    frases = frases_padrao(regiao)
    pdf.set_xy(MARGEM, y + 66)
    pdf.set_font("Helvetica", "", 15)
    pdf.set_text_color(*TINTA)
    pdf.multi_cell(
        larg_esq,
        20,
        _t(
            "Foi feita uma análise sobre os padrões das unidades desta região, e "
            + (
                "**foi encontrado um padrão** entre as que faturam mais."
                if frases
                else "**nenhuma característica separou** as que faturam mais."
            )
        ),
        align="L",
        markdown=True,
    )
    y = pdf.get_y() + 18
    if frases:
        pdf.set_xy(MARGEM, y)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*TINTA_2)
        pdf.cell(larg_esq, 15, _t("As unidades que faturam mais têm:"))
        y += 26
        for frase, leitura in frases:
            cor = MAGENTA if leitura == "anda ao contrário" else TURQUESA
            _bolinha(pdf, MARGEM + 2, y + 5, cor, 8)
            pdf.set_xy(MARGEM + 18, y)
            pdf.set_font("Helvetica", "", 13)
            pdf.set_text_color(*TINTA)
            pdf.cell(larg_esq - 18, 18, _t(frase), markdown=True)
            y += 27
    # Cartão da direita: quantas unidades foram analisadas.
    x = MARGEM + larg_esq + 36
    larg = W - MARGEM - x
    yc = TOPO + 50
    # Sem a média da rede (17/11, Juan: tirar qualquer menção a ela neste slide).
    _cartao_vazio(pdf, x, yc, larg, 276)
    pdf.set_xy(x + 24, yc + 22)
    pdf.set_font("Helvetica", "B", 72)
    pdf.set_text_color(0, 135, 127)
    pdf.cell(larg - 48, 76, _t(str(regiao["n_maduras"])))
    pdf.set_xy(x + 24, yc + 104)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*TINTA)
    pdf.cell(larg - 48, 20, _t("unidades analisadas"))
    pdf.set_xy(x + 24, yc + 130)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*TINTA_2)
    pdf.multi_cell(
        larg - 48,
        15,
        _t(
            f"das {regiao['n_total']} unidades da região, para chegar a esses números: as que têm os "
            f"12 meses de {_janela(fn)} fechados"
        ),
        align="L",
    )
    pdf.set_draw_color(*SEPARADOR)
    pdf.set_line_width(0.8)
    pdf.line(x + 24, yc + 196, x + larg - 24, yc + 196)
    meia = (larg - 48) / 2
    for k, (numero, rotulo, cor) in enumerate(
        (
            (regiao["n_acima"], "faturam mais", (0, 135, 127)),
            (regiao["n_abaixo"], "faturam menos", TINTA_2),
        )
    ):
        xx = x + 24 + k * meia
        pdf.set_xy(xx, yc + 208)
        pdf.set_font("Helvetica", "B", 28)
        pdf.set_text_color(*cor)
        pdf.cell(meia, 32, _t(str(numero)))
        pdf.set_xy(xx, yc + 242)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*TINTA_2)
        pdf.multi_cell(meia - 10, 13, _t(rotulo), align="L")


def _slide_comportamento(
    pdf: _UltraPDF,
    d: DadosRelatorio,
    assets: dict[str, bytes | None],
    regiao: dict[str, Any],
) -> None:
    """Os cartões do que diferencia as que faturam mais e a linha cinza; sem texto em volta."""
    _pagina(pdf, assets, f"Comportamento da região: {regiao['rotulo']}", d, cor=MAGENTA)
    com_relacao, sem_relacao = tracos_do_slide(regiao)
    # Altura dos cartões (até 290) e o conjunto centrado entre a faixa de título e o rodapé.
    n = len(com_relacao)
    gap = 14.0
    larg = (W - 2 * MARGEM - gap * (n - 1)) / n if n else 0.0
    cinza = 40.0 + 18.0 * (len(sem_relacao) - 1) + 14.0 if sem_relacao else 0.0
    util = 425.0
    alt = min(max(util - 30.0 - cinza, 196.0 if larg > 300 else 214.0), 290.0) if n else 0.0
    total = 30.0 + alt + cinza
    # Título e legenda na mesma linha.
    y = TOPO + 8 + max((util - total) / 2, 8.0)
    pdf.set_xy(MARGEM, y)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*TINTA)
    pdf.cell(
        600,
        16,
        _t(
            "O que diferencia as que faturam mais na região"
            if com_relacao
            else "Nenhum traço diferenciou as que faturam mais na região"
        ),
    )
    pdf.set_font("Helvetica", "", 10.5)
    x_leg = W - MARGEM - 222
    for rot, cor in (("Acima da média", TURQUESA), ("Abaixo da média", COR_ABAIXO)):
        _bolinha(pdf, x_leg, y + 3.5, cor, 9)
        pdf.set_xy(x_leg + 13, y)
        pdf.set_text_color(*TINTA_2)
        pdf.cell(95, 16, _t(rot))
        x_leg += 112
    y += 30
    if com_relacao:
        h_pe = max(_altura_contagem(pdf, larg - 36, t) for t in com_relacao)
        for i, t in enumerate(com_relacao):
            _cartao(pdf, MARGEM + i * (larg + gap), y, larg, alt, t, h_pe)
        y += alt + 14
    if sem_relacao:
        _linha_sem_relacao(pdf, y, sem_relacao)


def _cartao_vazio(pdf: _UltraPDF, x: float, y: float, larg: float, alt: float) -> None:
    pdf.set_fill_color(*BRANCO)
    pdf.set_draw_color(*BORDA_CARTAO)
    pdf.set_line_width(0.8)
    pdf.rect(x, y, larg, alt, style="DF", round_corners=True, corner_radius=12)


# --------------------------------------------------------------------------- rampa de maturação


def _legenda_linhas(
    pdf: _UltraPDF, x: float, y: float, itens: list[tuple[str, tuple[int, int, int], bool]]
) -> None:
    """Legenda de linhas lado a lado: amostra (cheia ou tracejada) e o texto."""
    pdf.set_font("Helvetica", "", 10)
    for rotulo, cor, tracejada in itens:
        pdf.set_draw_color(*cor)
        pdf.set_line_width(1.6 if tracejada else 2.6)
        if tracejada:
            pdf.set_dash_pattern(dash=4, gap=3)
        pdf.line(x, y + 6, x + 24, y + 6)
        pdf.set_dash_pattern()
        pdf.set_xy(x + 30, y)
        pdf.set_text_color(*TINTA)
        larg = pdf.get_string_width(_t(rotulo))
        pdf.cell(larg + 2, 12, _t(rotulo))
        x += 30 + larg + 26


def _legenda_regiao_resto(
    pdf: _UltraPDF, x: float, y: float, regiao: str, n_reg: int, com_resto: bool
) -> None:
    """A região (linha cheia, com quantas unidades) e o resto da rede (tracejada).

    "Resto da Rede", sem o número (17/11, Juan). Antes: "Resto da rede: 33 unidades"; a versão em
    duas linhas, com "fora do território", foi testada e desfeita no mesmo dia.
    """
    itens = [(f"{regiao}: {n_reg} unidades", COR_LINHA_REGIAO, False)]
    if com_resto:
        itens.append(("Resto da Rede", COR_LINHA_RESTO, True))
    _legenda_linhas(pdf, x, y, itens)


def _grafico_mes_de_vida(
    curva: list[float], curva_resto: list[float] | None, marco: int | None, larg: float, alto: float
) -> Any:
    """Curva do 1º ao 12º mês em % do 12º: região (cheia, com o 1º, o 3º e o mês em que estabiliza)
    e resto da rede (tracejada), com a linha dos 90% (estabilizar)."""
    meses = list(range(1, F.MESES_RAMPA + 1))
    reg = list(curva[: F.MESES_RAMPA])
    resto = list(curva_resto[: F.MESES_RAMPA]) if curva_resto else None
    fig, ax = plt.subplots(figsize=(larg, alto))
    ax.axhline(1.0, color="#d6d6da", lw=1, zorder=0)
    ax.axhline(F.MARCO_RAMPA, color="#9fded9", lw=1, ls=":", zorder=0)
    ax.annotate(
        "90%",
        (F.MESES_RAMPA + 0.35, F.MARCO_RAMPA),
        va="center",
        fontsize=8.5,
        color="#4cc3b9",
        annotation_clip=False,
    )
    if resto:
        ax.plot(meses, resto, "--", color="#9a9ea5", lw=2)
    ax.plot(meses, reg, "-", color="#00A79D", lw=3, marker="o", ms=5, mec="white", mew=1.1)
    # Rótulos do 1º e do 3º mês e do mês em que estabiliza, longe da linha do resto da rede.
    for k in sorted({1, 3} | ({marco} if marco else set())):
        v = reg[k - 1]
        ref = resto[k - 1] if resto else float("nan")
        if pd.notna(v):
            ax.annotate(
                fmt_pct(v),
                (k, v),
                xytext=(4, -16) if k == 1 else (0, -16 if pd.notna(ref) and v < ref else 8),
                textcoords="offset points",
                ha="left" if k == 1 else "center",
                fontsize=10,
                color="#00706A",
                weight="bold",
            )
    _estilo_eixo(ax)
    ax.tick_params(labelsize=9)
    ax.grid(axis="y", color="#eeeeee")
    ax.set_xticks(meses, [f"{k}º" for k in meses])
    ax.set_xlim(0.6, F.MESES_RAMPA + 0.9)
    ax.set_ylim(0, 1.12)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: fmt_pct(v)))
    ax.set_xlabel("mês de vida da unidade", fontsize=9, color="#666666")
    fig.tight_layout(pad=0.4)
    return _png(fig, dpi=200)


def _manchete(pdf: _UltraPDF, y: float, texto: str) -> float:
    """A frase-resumo numa faixa clara com o traço turquesa; devolve o fim."""
    larg_m = W - 2 * MARGEM - 44
    pdf.set_font("Helvetica", "B", 15)
    lin = pdf.multi_cell(larg_m, 21, _t(texto), dry_run=True, output="LINES")
    alt = 21.0 * (len(lin) if isinstance(lin, list) else 1) + 26
    pdf.set_fill_color(230, 246, 244)
    pdf.rect(MARGEM, y, W - 2 * MARGEM, alt, style="F", round_corners=True, corner_radius=10)
    pdf.set_fill_color(*TURQUESA)
    pdf.rect(MARGEM, y, 5, alt, style="F")
    pdf.set_xy(MARGEM + 24, y + 13)
    pdf.set_text_color(*TINTA)
    pdf.multi_cell(larg_m, 21, _t(texto), align="L")
    return y + alt


def _cartao_curva(
    pdf: _UltraPDF,
    x: float,
    y: float,
    larg: float,
    alt: float,
    d: DadosRelatorio,
    regiao: dict[str, Any],
    g: dict[str, Any],
    resto: dict[str, Any] | None,
    item: dict[str, Any] | None,
    o_que: str,
) -> None:
    """Um cartão: em quantos meses estabiliza (número grande) e a curva dos 12 meses embaixo."""
    _cartao_vazio(pdf, x, y, larg, alt)
    numero = f"{item['meses']} meses" if item else "-"
    pdf.set_xy(x + 18, y + 12)
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_text_color(0, 135, 127)
    w_num = pdf.get_string_width(_t(numero)) + 4
    pdf.cell(w_num, 32, _t(numero))
    # O número real por trás do mês (17/11: sem "unidade típica"): quantas já tinham estabilizado.
    rotulo = (
        f"até o {item['meses']}º mês, {item['ja']} das {item['n']} unidades da região já tinham "
        f"estabilizado {o_que}" + ("" if item["estavel"] else " (depois, ainda oscila)")
        if item
        else f"{o_que.capitalize()} não chegam a 90% do 12º mês"
    )
    pdf.set_xy(x + 18 + w_num + 8, y + 14)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*TINTA)
    pdf.multi_cell(larg - 36 - w_num - 8, 14, _t(rotulo), align="L")
    titulo = "Alunos" if o_que == "os alunos" else "Faturamento"
    pdf.set_xy(x + 18, y + 52)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*TINTA_2)
    pdf.cell(larg - 36, 12, _t(f"{titulo} em cada mês de vida, em % do 12º mês"))
    _legenda_regiao_resto(pdf, x + 18, y + 70, regiao["rotulo"], g["n"], resto is not None)
    larg_img = larg - 20
    alto_img = alt - 92 - 8
    pdf.image(
        _grafico_mes_de_vida(
            g["curva"],
            resto["curva"] if resto else None,
            item["meses"] if item else None,
            larg_img / 72,
            alto_img / 72,
        ),
        x=x + 10,
        y=y + 90,
        w=larg_img,
        h=alto_img,
    )


def _slide_rampa(
    pdf: _UltraPDF,
    d: DadosRelatorio,
    assets: dict[str, bytes | None],
    regiao: dict[str, Any],
) -> None:
    """A frase-resumo e, lado a lado, as curvas de alunos e de faturamento, cada uma com o tempo
    que leva para estabilizar (17/11: com uma curva só, o leitor achava que ela valia para os dois)."""
    fn = d.funcionamento
    reg, outras = fn["rampa"]["grupos"][regiao["id"]], fn["rampa"]["outras"]
    rp_resto = outras if outras["n"] >= F.N_MIN_GRUPO else None
    ft_bloco = fn.get("faturamento", {})
    ft = ft_bloco.get("grupos", {}).get(regiao["id"])
    ft = ft if ft and ft["n"] >= F.N_MIN_GRUPO else None
    ft_resto = ft_bloco.get("outras")
    ft_resto = ft_resto if ft_resto and ft_resto["n"] >= F.N_MIN_GRUPO else None
    ritmo = ritmo_maturacao(reg, rp_resto, ft, ft_resto)
    itens = {it["chave"]: it for it in ritmo["itens"]}
    _pagina(pdf, assets, f"Rampa de maturação: {regiao['rotulo']}", d, cor=MAGENTA)
    y = TOPO + 10
    if ritmo["manchete"]:
        y = _manchete(pdf, y, ritmo["manchete"]) + 14
    alt = H - 62 - y
    cartoes = [(reg, rp_resto, itens.get("alunos"), "os alunos")]
    if ft:
        cartoes.append((ft, ft_resto, itens.get("faturamento"), "o faturamento"))
    gap = 16.0
    larg = (W - 2 * MARGEM - gap * (len(cartoes) - 1)) / len(cartoes)
    for i, (g, resto, item, o_que) in enumerate(cartoes):
        _cartao_curva(
            pdf, MARGEM + i * (larg + gap), y, larg, alt, d, regiao, g, resto, item, o_que
        )


# --------------------------------------------------------------------------- ritmo e inauguração

#: Exemplo da retenção da inauguração: quantos alunos a mais ficam numa inauguração deste tamanho
#: (Juan, 17/11: "8 a cada 100 parece um número pequeno").
EXEMPLO_ALUNOS_INAUGURACAO = 1500

#: Até onde se olha se o nível se mantém depois de estabilizar (o 12º mês é o 100%).
MESES_ATE_12 = 12

#: Ritmo pelo mês em que a unidade típica passa de 90% do 12º mês, região menos resto da rede:
#: 3 meses ou mais depois = "demora mais"; 2 = "um pouco mais"; 2 ou mais antes = "mais rápido".
RITMO_ALUNOS = {
    "mais": "os alunos demoram mais para chegar",
    "pouco": "os alunos demoram um pouco mais para chegar",
    "igual": "os alunos chegam no mesmo ritmo",
    "rapido": "os alunos chegam mais rápido",
}
RITMO_FATURAMENTO = {
    "mais": "o faturamento demora mais para estabilizar",
    "pouco": "o faturamento demora um pouco mais para estabilizar",
    "igual": "o faturamento estabiliza no mesmo ritmo",
    "rapido": "o faturamento estabiliza mais rápido",
}


def _ritmo(m: int | None, m_resto: int | None) -> str | None:
    """ "mais", "pouco", "igual" ou "rapido" (None sem os dois meses para comparar)."""
    if m_resto is None:
        return None
    if m is None:
        return "mais"
    dif = m - m_resto
    if dif >= 3:
        return "mais"
    if dif == 2:
        return "pouco"
    if dif <= -2:
        return "rapido"
    return "igual"


def ritmo_maturacao(
    rp: dict[str, Any] | None,
    rp_resto: dict[str, Any] | None,
    ft: dict[str, Any] | None,
    ft_resto: dict[str, Any] | None,
) -> dict[str, Any]:
    """A manchete-resumo e quantos meses alunos e faturamento levam para estabilizar.

    Estabilizar = a unidade típica chegar a 90% do 12º mês. Itens: {"chave", "meses", "resto"
    (None sem o resto da rede), "estavel" (não volta abaixo de 90% até o 12º mês)}.
    """
    partes: list[str] = []
    itens: list[dict[str, Any]] = []
    for chave, g, o, frases in (
        ("alunos", rp, rp_resto, RITMO_ALUNOS),
        ("faturamento", ft, ft_resto, RITMO_FATURAMENTO),
    ):
        if not g:
            continue
        m, mr = g["mes_marco"], (o or {}).get("mes_marco")
        ritmo = _ritmo(m, mr if o else None)
        if ritmo:
            partes.append(frases[ritmo])
        if m:
            depois = [v for v in g["curva"][m - 1 : MESES_ATE_12] if pd.notna(v)]
            itens.append(
                {
                    "chave": chave,
                    "meses": m,
                    "resto": mr if o else None,
                    "estavel": all(v >= F.MARCO_RAMPA for v in depois),
                    "ja": g.get("ja_no_marco", 0),
                    "n": g["n"],
                }
            )
    manchete = (
        # Sem "Comparado ao resto da rede" (17/11, Juan): a legenda do gráfico já diz contra quem.
        "Nesta região, " + " e ".join(partes) + "." if partes else None
    )
    return {"manchete": manchete, "itens": itens}


# --------------------------------------------------------------------------- faturamento e tendência


def _png_fixo(fig: Any, dpi: int = 200, fundo: str = "white") -> io.BytesIO:
    """PNG no tamanho exato da figura (sem recorte automático), para caber certo no cartão."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor=fundo)
    plt.close(fig)
    buf.seek(0)
    return buf


def _grafico_calendario(
    reg: dict[str, Any], outras: dict[str, Any], larg: float = 12.0, alto: float = 1.2
) -> Any:
    """Alunos novos por mês do ano contra a média do ano: barras da região, traço das outras.

    `larg`/`alto` em polegadas: o slide passa o espaço livre do cartão (17/11, Juan: "o gráfico
    pode aumentar, como não tem nada embaixo"); rótulos e traços crescem com a altura."""
    meses = np.arange(12)
    vals = np.array(reg["calendario"], dtype=float)
    out = np.array(outras["calendario"], dtype=float)
    escala = min(max(alto / 1.2, 1.0), 1.4)
    fig, ax = plt.subplots(figsize=(larg, alto))
    fig.subplots_adjust(left=0.01, right=0.99, top=0.97, bottom=0.2 / max(alto / 1.2, 1.0))
    cores = ["#00A79D" if (pd.notna(v) and v >= 0) else "#C23C8E" for v in vals]
    ax.bar(meses, np.nan_to_num(vals), width=0.55, color=cores)
    ax.scatter(
        meses,
        out,
        marker="_",
        s=150 * escala**2,
        color="#555555",
        linewidths=1.4 * escala,
        zorder=3,
    )
    for m, v, o in zip(meses, vals, out, strict=True):
        if pd.isna(v):
            continue
        ref = o if pd.notna(o) else v
        topo, base = max(v, ref, 0), min(v, ref, 0)
        ax.annotate(
            fmt_pct(v, True),
            (m, topo if v >= 0 else base),
            xytext=(0, 3 if v >= 0 else -3),
            textcoords="offset points",
            ha="center",
            va="bottom" if v >= 0 else "top",
            fontsize=8 * escala,
            color="#333333",
            weight="bold",
        )
    ax.axhline(0, color="#9a9a9a", lw=0.8)
    ax.set_xticks(meses, MESES_CURTOS)
    ax.tick_params(axis="x", length=0, labelsize=8.5 * escala)
    ax.yaxis.set_visible(False)
    tudo = np.abs(np.concatenate([vals, out]))
    lim = float(np.nanmax(tudo)) if np.isfinite(tudo).any() else 0.5
    # Folga para o rótulo; no gráfico alto (o do slide), menos folga e barras maiores.
    folga = 1.6 if alto <= 1.2 else 1.3
    ax.set_ylim(-lim * folga, lim * folga)
    for lado in ("top", "right", "left", "bottom"):
        ax.spines[lado].set_visible(False)
    return _png_fixo(fig)


def textos_conclusao(
    regiao: dict[str, Any],
    reg: dict[str, Any],
    app: float,
    viz: dict[str, Any] | None = None,
) -> list[str]:
    """Os achados menores da região, um por frase (com **negrito** na abertura): agregadores,
    quem entra na inauguração e outra Ultra a até 5 min (veio do slide "O 1º ano", 17/11).
    Faturamento e renda saíram (17/11).

    `reg`: o grupo de `faturamento_tendencia`; `app`: a parte dos alunos que vem de agregador
    (comportamento); `viz`: quantas têm outra Ultra a até 5 min (o ponto só sai nos grupos de
    `VIZINHA_5MIN_GRUPOS`, onde a pesquisa achou o efeito). Sem o resto da rede nos agregadores
    (17/11, Juan: tirar "(resto da rede: +7%)" e "(resto da rede: 49%)").
    """

    def variou(v: float, sobe: str, desce: str) -> str:
        return f"{sobe if v >= 0 else desce} {round(abs(v) * 100)}%"

    pontos: list[str] = []
    v_app = reg["var"].get("agregadores")
    if v_app is not None and pd.notna(v_app):
        # "Agregadores" no lugar de "Alunos de app" (17/11, Juan: só "Agregadores").
        frase = f"**Agregadores:** {variou(v_app, 'cresceram', 'caíram')} em 12 meses"
        ja, n = reg.get("app_ja_tinha"), reg.get("n_var", 0)
        if ja is not None and n and ja == n:
            frase += ", nas mesmas unidades, que já aceitavam agregadores um ano antes"
        if pd.notna(app):
            frase += f"; hoje são {fmt_pct(app)} dos alunos"
        pontos.append(frase + ".")
    # Quem entra na inauguração (veio do 1º ano): o exemplo de 1.500 alunos. Só com diferença clara
    # (18/11, Juan: em SP, tirar "Quem entra na inauguração fica quase igual").
    grupo = regiao["conferencia"]["grupo"]
    ret = F.RETENCAO_ABERTURA.get(grupo or "", F.RETENCAO_ABERTURA["rede"])
    clara = ret["pontos"] >= 3 and ret["a_favor"] >= ret["n"] * 2 / 3
    a_mais = fmt_int(round(ret["pontos"] / 100 * EXEMPLO_ALUNOS_INAUGURACAO, -1))
    exemplo = fmt_int(EXEMPLO_ALUNOS_INAUGURACAO)
    onde = f"{ret['a_favor']} das {ret['n']} unidades" + ("" if grupo else ", número da rede")
    if clara:
        pontos.append(
            f"**Quem entra na inauguração fica mais:** numa inauguração com {exemplo} alunos, cerca de "
            f"{a_mais} a mais seguem ativos depois de 1 ano, comparado com quem entra nos meses "
            f"seguintes (aconteceu em {onde})."
        )
    if viz and grupo in VIZINHA_5MIN_GRUPOS:
        pontos.append(
            "**Outra Ultra a até 5 min de carro:** a unidade nova recebe cerca de 15% menos alunos "
            f"novos no 1º ano. Na região, {viz['viz5']} das {viz['n_viz5']} estão assim."
        )
    return pontos


#: Onde o ponto "Outra Ultra a até 5 min" aparece: só no grupo da pesquisa em que o efeito existe.
#: O -15% vem da rede (rodada 31: -11% de alunos novos a cada 0,7 Ultra a mais a 5 min), puxado pelo
#: DF: sem ele, a faixa chega a zero. Em SP não há como medir (18/11, Juan: "tire de SP e mantenha
#: em DF").
VIZINHA_5MIN_GRUPOS = frozenset({"DF"})

#: A conclusão de toda região: o que esta análise é, e o que ela não é.
CONCLUSAO = (
    "Esta análise não é uma regra nem uma receita para faturar mais: é um padrão que encontramos "
    "nas unidades desta região, que pode ajudar na abertura de outras unidades."
)


def texto_validade(
    g: dict[str, Any],
    val: dict[str, Any] | None,
    data_ref: pd.Timestamp,
    gerado_em: pd.Timestamp,
) -> str | None:
    """A anotação de até quando a análise de padrões da região vale (18/11, Juan).

    `g`: o grupo de `comportamento` (região com padrões); `val`: o de `validade`. O relatório em que
    todas as unidades abertas hoje terão 12 meses = o mês dos dados delas mais o atraso de hoje entre
    os dados e o relatório (dados até ago/2026 no relatório de nov/2026 = 3 meses).
    """
    if not val or not val.get("n"):
        return None
    ref = pd.Period(data_ref, freq="M")
    ate = f"{MESES_CURTOS[ref.month - 1]}/{ref.year}"
    n, total, mes = g["n_maduras"], val["n"], val.get("mes_todas")
    if mes is None or n >= total or pd.Period(mes, freq="M") <= ref:
        return f"Esta análise usou as {n} unidades da região (dados até {ate})."
    atraso = (pd.Period(gerado_em, freq="M") - ref).n
    quando = (pd.Period(mes, freq="M") + atraso).to_timestamp()
    return (
        f"Esta análise usou {n} das {total} unidades da região (dados até {ate}). Vale até o "
        f"relatório do {trimestre_de(quando)}, quando as {total} terão 12 meses de dados e ela poderá "
        "ser refeita com todas."
    )


def _slide_conclusao(
    pdf: _UltraPDF,
    d: DadosRelatorio,
    assets: dict[str, bytes | None],
    regiao: dict[str, Any],
) -> None:
    """Os achados menores em pontos e o gráfico de alunos novos por mês (a frase final foi para o
    último slide, 17/11)."""
    fn = d.funcionamento
    td = fn["tendencia"]
    reg, resto = td["grupos"][regiao["id"]], td["outras"]
    pontos = textos_conclusao(
        regiao,
        reg,
        regiao.get("pct_agregador_alunos", float("nan")),
        fn.get("ocupacao", {}).get("grupos", {}).get(regiao["id"]),
    )
    # Título sem "Conclusão" (17/11, Juan): a faixa diz o que o slide traz.
    _pagina(pdf, assets, f"Outros achados: {regiao['rotulo']}", d, cor=MAGENTA)
    # Alturas para centrar o conjunto: achados (até três numa linha), calendário e a frase final.
    gap = 28.0
    por_linha = len(pontos) if len(pontos) <= 3 else 2
    larg = (W - 2 * MARGEM - gap * (por_linha - 1)) / por_linha
    fonte, linha = 11.5, 16.0
    pdf.set_font("Helvetica", "", fonte)
    alturas = []
    for p in pontos:
        lin = pdf.multi_cell(larg - 16, linha, _t(p), dry_run=True, output="LINES", markdown=True)
        alturas.append(linha * (len(lin) if isinstance(lin, list) else 1))
    # A frase final saiu daqui: fecha o último slide, em destaque (17/11, Juan). Os achados ficam
    # no alto e o gráfico ocupa o resto da página (17/11: "o gráfico pode aumentar").
    y = TOPO + 22
    # Os achados, lado a lado.
    for k in range(0, len(pontos), por_linha):
        alt_linha = max(alturas[k : k + por_linha])
        for i, p in enumerate(pontos[k : k + por_linha]):
            x = MARGEM + i * (larg + gap)
            _bolinha(pdf, x, y + 4.5, TURQUESA, 6)
            pdf.set_xy(x + 14, y)
            pdf.set_font("Helvetica", "", fonte)
            pdf.set_text_color(51, 51, 51)
            pdf.multi_cell(larg - 16, linha, _t(p), align="L", markdown=True)
        y += alt_linha + 12
    # Quando os alunos chegam: o gráfico do calendário.
    y += 8
    alt_cal = H - 58 - y
    _cartao_vazio(pdf, MARGEM, y, W - 2 * MARGEM, alt_cal)
    pdf.set_xy(MARGEM + 18, y + 10)
    pdf.set_font("Helvetica", "B", 11.5)
    pdf.set_text_color(*TINTA)
    pdf.cell(
        560, 14, _t("Quando os alunos chegam: alunos novos em cada mês, contra a média do ano")
    )
    pdf.set_xy(MARGEM + 18, y + 25)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*TINTA_2)
    pdf.cell(
        700,
        11,
        _t("barras = região (verde acima, rosa abaixo da média do ano); traço = resto da rede"),
    )
    larg_g, alto_g = W - 2 * MARGEM - 20, alt_cal - 40 - 12
    pdf.image(
        _grafico_calendario(reg, resto, larg_g / 72, alto_g / 72),
        x=MARGEM + 10,
        y=y + 40,
        w=larg_g,
        h=alto_g,
    )


# --------------------------------------------------------------------------- metas

#: Fundo do cartão da meta: o magenta da Ultra bem claro, para destacar.
FUNDO_META = (252, 238, 246)


def _n_linhas(pdf: _UltraPDF, larg: float, alt: float, texto: str) -> int:
    """Quantas linhas o texto (com **negrito**) ocupa na largura, na fonte atual."""
    lin = pdf.multi_cell(larg, alt, _t(texto), dry_run=True, output="LINES", markdown=True)
    return len(lin) if isinstance(lin, list) else 1


def assinadas_por_fase(pipeline: list[dict[str, Any]]) -> list[tuple[str, list[str]]]:
    """As assinadas agrupadas por fase, da mais perto de abrir à mais longe."""
    # A ordem e o rótulo das fases vêm de `masters.meta`, a mesma regra da tela Masters.
    grupos: dict[str, list[str]] = {}
    for item in pipeline:
        grupos.setdefault(fase_de_exibicao(item.get("fase")), []).append(str(item["unidade"]))
    return sorted(grupos.items(), key=lambda kv: ordem_da_fase(kv[0]))


def _grafico_meta_trimestre(
    trimestres: list[dict[str, Any]],
    com_pct: bool,
    larg: float,
    alto: float,
    gerado_em: pd.Timestamp | None = None,
) -> Any:
    """Os 4 trimestres do ano: % da meta do ano (ou abertas no ano, sem a meta) até o fim de cada
    um. Turquesa onde houve abertura, cinza onde não houve; trimestre que não começou fica vazio.

    O trimestre em que o relatório é gerado (`atual`) leva borda tracejada e o rótulo "este
    relatório (dd/mm)": ainda está em andamento (17/11, Juan: "sinalize que é o mês que está sendo
    gerado o relatório")."""
    x = np.arange(len(trimestres))
    y = [
        0.0 if t["futuro"] else (t["pct"] * 100 if com_pct else t["acumulado"]) for t in trimestres
    ]
    fig, ax = plt.subplots(figsize=(larg, alto))
    cores = ["#00A79D" if t["novas"] > 0 else "#d9dce0" for t in trimestres]
    barras = ax.bar(x, y, width=0.62, color=cores)
    for barra, t in zip(barras, trimestres, strict=True):
        if t.get("atual"):
            barra.set_edgecolor("#C23C8E")
            barra.set_linestyle("--")
            barra.set_linewidth(1.6)
    topo = max(y) if any(y) else 1.0
    if com_pct:
        topo = max(topo, 100.0)
        # A linha para na borda do gráfico; o rótulo fica na margem, sem a linha por baixo.
        ax.hlines(100, -0.6, len(x) - 0.4, color="#C23C8E", lw=1.4, ls="--", zorder=0)
        ax.annotate(
            "meta do ano",
            (len(x) - 0.4, 100),
            xytext=(5, 0),
            textcoords="offset points",
            va="center",
            fontsize=8.5,
            color="#C23C8E",
            weight="bold",
            annotation_clip=False,
        )
    for xi, yi, t in zip(x, y, trimestres, strict=True):
        if t["futuro"]:
            continue
        ax.annotate(
            (f"{round(yi)}%" if com_pct else fmt_int(yi))
            + (f"  (+{t['novas']})" if t["novas"] else ""),
            (xi, yi),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color="#00706A" if t["novas"] else "#777777",
            weight="bold",
        )
    _estilo_eixo(ax)
    ax.spines["left"].set_visible(False)
    ax.set_yticks([])
    quando = f"\nde {gerado_em:%d/%m}" if gerado_em is not None else ""
    rotulos = [
        # Trimestre futuro só com o nome, em cinza claro: "(ainda não começou)" se sobrepunha ao
        # vizinho e, em duas linhas, era cortado (18/11, na simulação do relatório de fev/2027).
        f"{t['trimestre'].quarter}º tri"
        for t in trimestres
    ]
    # O aviso do trimestre do relatório vai DENTRO da barra tracejada (no eixo, a 2ª linha era
    # cortada e, numa linha só, encostava no trimestre ao lado); barra baixa, logo acima dela.
    for xi, yi, t in zip(x, y, trimestres, strict=True):
        if t.get("atual"):
            dentro = yi >= topo * 0.45
            ax.annotate(
                # Três linhas curtas, para caber na largura da barra.
                f"em andamento:\nrelatório{quando}",
                (float(xi), yi / 2 if dentro else yi),
                xytext=(0, 0 if dentro else 18),
                textcoords="offset points",
                ha="center",
                va="center" if dentro else "bottom",
                fontsize=7,
                color="#C23C8E",
                weight="bold",
                linespacing=1.3,
                annotation_clip=False,
            )
    ax.set_xticks(x, rotulos)
    ax.tick_params(axis="x", labelsize=9, length=0)
    for rotulo, t in zip(ax.get_xticklabels(), trimestres, strict=True):
        if t.get("atual"):
            rotulo.set_color("#C23C8E")
            rotulo.set_fontweight("bold")
        elif t.get("futuro"):
            rotulo.set_color("#B5B5BA")
    ax.set_xlim(-0.6, len(x) - 0.4)
    # Espaço em cima para o aviso do trimestre atual quando a barra dele é baixa.
    baixo = any(t.get("atual") and yi < topo * 0.45 for yi, t in zip(y, trimestres, strict=True))
    ax.set_ylim(0, topo * (1.9 if baixo else 1.2))
    if not any(t["novas"] for t in trimestres):
        ax.text(
            (len(x) - 1) / 2,
            topo * 0.9,
            "nenhuma abertura neste ano até agora",
            ha="center",
            va="center",
            fontsize=9.5,
            color="#777777",
        )
    # Margem à direita para o rótulo "meta do ano" caber inteiro.
    fig.subplots_adjust(left=0.01, right=0.86, top=0.97, bottom=0.2)
    # Fundo do cartão da meta, para o gráfico não virar um quadro branco dentro dele.
    fundo = "#{:02x}{:02x}{:02x}".format(*FUNDO_META)
    ax.set_facecolor(fundo)
    return _png_fixo(fig, fundo=fundo)


def _slide_metas(pdf: _UltraPDF, d: DadosRelatorio, assets: dict[str, bytes | None]) -> None:
    """Meta do contrato e metas propostas, refeito (17/11, Juan): a proposta para 12 meses e as
    assinadas em cima; embaixo, em destaque, a meta do ano (a meta é anual: 4 trimestres) em % até o
    fim de cada trimestre, subindo a cada trimestre com abertura. Sem a meta do ano, as abertas no
    ano que contam para a meta no lugar do %."""
    mr, mc = d.metas_resumo, d.meta_contrato
    y0 = _pagina(pdf, assets, "Meta do contrato e metas propostas", d, cor=MAGENTA) + 10
    gap = 14.0
    larg_total = W - 2 * MARGEM
    larg_prop, larg_ass = 548.0, larg_total - 548.0 - gap
    # ---- em cima: a proposta e as assinadas, com a mesma altura
    sub_prop = (
        (
            "Abrir a 1 assinada"
            if mr["n_pipeline"] == 1
            else f"Abrir as {mr['n_pipeline']} assinadas"
        )
        + " e iniciar novas buscas no ritmo de aberturas dos últimos "
        f"12 meses ({mr['aberturas_12m']}, mínimo 1), pelo espaço livre de cada região."
    )
    pdf.set_font("Helvetica", "", 9)
    n_sub = _n_linhas(pdf, larg_prop - 32, 11.5, sub_prop)
    alt_linha = 22.0
    alt_prop = 14 + 16 + 4 + 11.5 * n_sub + 8 + 26 + alt_linha * len(d.metas) + 14
    fases = assinadas_por_fase(mr["pipeline"])
    texto_ass = "\n".join(f"**{f} ({len(us)}):** {', '.join(us)}" for f, us in fases)
    n_ass = _n_linhas(pdf, larg_ass - 32, 12.5, texto_ass) if fases else 1
    alt_ass = 14 + 16 + 8 + 12.5 * n_ass + 14
    alt_cima = max(alt_prop, alt_ass)
    _cartao_vazio(pdf, MARGEM, y0, larg_prop, alt_cima)
    pdf.set_xy(MARGEM + 16, y0 + 14)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*TINTA)
    pdf.cell(larg_prop - 32, 16, _t("Proposta para os próximos 12 meses, por região"))
    pdf.set_xy(MARGEM + 16, y0 + 34)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*TINTA_2)
    pdf.multi_cell(larg_prop - 32, 11.5, _t(sub_prop), align="L")
    cols: list[Coluna] = [
        ("Região", 150, "L"),
        ("Unidades abertas", 76, "R"),
        ("Assinadas (pipeline)", 86, "R"),
        ("Espaço livre após as assinadas (alunos)", 116, "R"),
        ("Novas buscas propostas", 88, "R"),
    ]
    buscas = list(d.metas["novas_buscas"]) if len(d.metas) else []
    _tabela(
        pdf,
        MARGEM + 16,
        y0 + 34 + 11.5 * n_sub + 8,
        cols,
        [
            [
                m.regiao_nome,
                fmt_int(m.abertas),
                fmt_int(m.pipeline),
                fmt_int(m.espaco_apos_pipeline),
                fmt_int(m.novas_buscas),
            ]
            for m in d.metas.itertuples()
        ],
        alt_linha=alt_linha,
        cor_cabecalho=MAGENTA,
        negrito_primeira=True,
        fundo_linha=lambda i: (232, 246, 245) if buscas[i] > 0 else BRANCO,
    )
    x_ass = MARGEM + larg_prop + gap
    _cartao_vazio(pdf, x_ass, y0, larg_ass, alt_cima)
    pdf.set_xy(x_ass + 16, y0 + 14)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*TINTA)
    pdf.cell(larg_ass - 32, 16, _t(f"Assinadas no pipeline: {mr['n_pipeline']}"))
    pdf.set_xy(x_ass + 16, y0 + 38)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(51, 51, 51)
    pdf.multi_cell(
        larg_ass - 32,
        12.5,
        _t(texto_ass or "Nenhuma assinada no pipeline."),
        align="L",
        markdown=True,
    )
    # ---- a frase final do relatório, embaixo e em destaque (17/11, Juan: "ir para o último
    # slide e aumentar para ficar bem destacado"): faixa turquesa, branco, negrito, grande.
    fonte_fim, linha_fim = 16.5, 22.0
    com_frase = F.tem_dados(d.funcionamento)
    pdf.set_font("Helvetica", "B", fonte_fim)
    n_fim = _n_linhas(pdf, larg_total - 56, linha_fim, CONCLUSAO)
    alt_fim = linha_fim * n_fim + 26 if com_frase else 0.0
    # Até quando a análise vale, embaixo da faixa, à direita (18/11, Juan; só nas regiões com os
    # padrões: DF e SP).
    notas_val = (
        [
            t
            for g in F.so_com_dados(d.funcionamento)["comportamento"]["grupos"]
            if (
                t := texto_validade(
                    g,
                    d.funcionamento.get("validade", {}).get(g["id"]),
                    d.data_ref,
                    d.gerado_em,
                )
            )
        ]
        if com_frase
        else []
    )
    pdf.set_font("Helvetica", "", 9)
    lin_val = [_n_linhas(pdf, larg_total, 12, t) for t in notas_val]
    alt_nota = 12.0 * sum(lin_val) + 5 if notas_val else 0.0
    y_fim = H - 48 - alt_fim - alt_nota + (0 if com_frase else gap)
    # ---- no meio, em destaque: a meta do contrato
    y_meta = y0 + alt_cima + gap
    alt_meta = y_fim - gap - y_meta
    pdf.set_fill_color(*FUNDO_META)
    pdf.set_draw_color(*MAGENTA)
    pdf.set_line_width(1.4)
    pdf.rect(MARGEM, y_meta, larg_total, alt_meta, style="DF", round_corners=True, corner_radius=12)
    pdf.set_line_width(0.2)
    q, por_ano, ano = mc.get("quantidade"), mc.get("por_ano"), mc.get("ano")
    prazo = mc.get("prazo")
    tri = mc.get("trimestres") or []
    xl, larg_esq = MARGEM + 22, 262.0
    pdf.set_xy(xl, y_meta + 16)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*MAGENTA)
    pdf.cell(larg_esq, 18, _t(f"Meta de aberturas de {ano}"))
    pdf.set_xy(xl, y_meta + 36)
    pdf.set_font("Helvetica", "B", 34)
    pdf.cell(larg_esq, 38, _t(fmt_pct(mc["pct_ano"]) if por_ano else fmt_int(mc.get("n_ano", 0))))
    linhas: list[str] = []
    if por_ano:
        linhas.append(f"da meta do ano: **{mc['n_ano']} de {por_ano} unidades** abertas em {ano}")
    else:
        linhas.append(f"unidades abertas em {ano} que contam para a meta")
        linhas.append("**Meta do ano não informada**: com ela, vira %")
    if q:
        linhas.append(
            f"contrato: {mc['n_contam']} de {q} unidades ({fmt_pct(mc['pct'])})"
            + (f", prazo {prazo.strftime('%d/%m/%Y')}" if prazo is not None else "")
        )
    else:
        linhas.append(f"desde o início: {mc.get('n_contam', 0)} contam para a meta")
        if prazo is not None:
            linhas.append(f"prazo do contrato: {prazo.strftime('%d/%m/%Y')}")
    if mc.get("sem_data"):
        n = len(mc["sem_data"])
        linhas.append(
            "1 sem data de inauguração, fora da conta do ano"
            if n == 1
            else f"{n} sem data de inauguração, fora da conta do ano"
        )
    pdf.set_xy(xl, y_meta + 78)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*TINTA)
    for lin in linhas:
        pdf.set_x(xl)
        pdf.multi_cell(larg_esq, 12.5, _t(lin), align="L", markdown=True)
        pdf.set_y(pdf.get_y() + 2)
    # O gráfico por trimestre, à direita.
    xg = xl + larg_esq + 22
    larg_g = MARGEM + larg_total - 18 - xg
    pdf.set_xy(xg, y_meta + 16)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*TINTA)
    pdf.cell(
        larg_g,
        16,
        _t(
            f"% da meta de {ano} até o fim de cada trimestre"
            if por_ano
            else f"Unidades abertas em {ano} que contam para a meta, até o fim de cada trimestre"
        ),
    )
    pdf.set_xy(xg, y_meta + 32)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*TINTA_2)
    pdf.cell(
        larg_g,
        12,
        _t("em turquesa, os trimestres com abertura (entre parênteses, quantas); zera a cada ano"),
    )
    if com_frase:
        pdf.set_fill_color(*TURQUESA)
        pdf.rect(
            MARGEM, y_fim, larg_total, alt_fim, style="F", round_corners=True, corner_radius=12
        )
        pdf.set_xy(MARGEM + 28, y_fim + 13)
        pdf.set_font("Helvetica", "B", fonte_fim)
        pdf.set_text_color(*BRANCO)
        pdf.multi_cell(larg_total - 56, linha_fim, _t(CONCLUSAO), align="C")
        pdf.set_xy(MARGEM, y_fim + alt_fim + 5)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*TINTA_2)
        for t in notas_val:
            pdf.set_x(MARGEM)
            pdf.multi_cell(larg_total, 12, _t(t), align="R")
    if tri:
        alto_g = alt_meta - 52 - 10
        pdf.image(
            _grafico_meta_trimestre(tri, bool(por_ano), larg_g / 72, alto_g / 72, d.gerado_em),
            x=xg,
            y=y_meta + 50,
            w=larg_g,
            h=alto_g,
        )


def gerar_slides(pdf: _UltraPDF, d: DadosRelatorio, assets: dict[str, bytes | None]) -> int:
    """Por região com unidades suficientes: Padrões das unidades (apresentação), Comportamento,
    Rampa de maturação e Outros achados (o "O 1º ano da unidade" entrou nele em 17/11).

    A rampa e o padrão de faturamento só saem quando a região tem `N_MIN_GRUPO` unidades com o 1º
    ano completo; devolve quantos slides saíram.
    """
    d = replace(d, funcionamento=F.so_com_dados(d.funcionamento))
    rampas = d.funcionamento.get("rampa", {}).get("grupos", {})
    feitos = 0
    for g in d.funcionamento["comportamento"]["grupos"]:
        _slide_apresentacao(pdf, d, assets, g)
        _slide_comportamento(pdf, d, assets, g)
        feitos += 2
        if rampas.get(g["id"], {}).get("n", 0) >= F.N_MIN_GRUPO:
            _slide_rampa(pdf, d, assets, g)
            feitos += 1
        if g["id"] in d.funcionamento.get("tendencia", {}).get("grupos", {}):
            _slide_conclusao(pdf, d, assets, g)
            feitos += 1
    return feitos
