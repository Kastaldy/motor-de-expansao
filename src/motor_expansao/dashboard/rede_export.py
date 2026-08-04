"""Exports da Visao Executiva: CSV, XLSX e PDF - BLK-EXEC-10/11.

READ-ONLY: nada aqui escreve em disco. Todo gerador devolve **bytes** e quem chama decide o
que fazer com eles -- e' o que permite ao backend do piloto continuar passando no guardrail
AST (`test_modulos_de_rede_sao_read_only_por_ast`).

Duas escolhas que parecem detalhe e nao sao:

* **`csv.writer` sobre `StringIO`, nunca `DataFrame.to_csv`.** O guardrail AST reprova
  `to_csv` por nome; e o CSV da casa e' `sep=";"` com `utf-8-sig` (regra do `CLAUDE.md` §2),
  que e' o que o Excel em pt-BR abre sem pedir nada.
* **Numero com virgula decimal**, tambem por causa do Excel pt-BR: com ponto, a planilha
  importa faturamento como texto e o time perde a soma.

A entrada e' o MESMO payload que a tela recebe. Nao ha uma segunda fonte de verdade: se a
carteira e o CSV divergirem, e' porque alguem calculou duas vezes -- e isso e' justamente o
defeito mais caro deste projeto.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from io import BytesIO, StringIO
from typing import Any

from motor_expansao.dashboard.pdf_base import (
    BRANCO,
    CINZA_CLARO,
    CINZA_TEXTO,
    COR_SEVERIDADE,
    PAGINA_ALTURA,
    PAGINA_LARGURA,
    ULTRA_MAGENTA,
    ULTRA_TURQUESA,
    UltraPDF,
    ascii_seguro,
    cartao,
    faixa_de_titulo,
    linha_de_tabela,
    rodape,
)

CSV_SEPARADOR = ";"
CSV_ENCODING = "utf-8-sig"
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Colunas do export tabular. Ordem pensada para leitura: quem e' -> como esta -> por que.
COLUNAS_CARTEIRA: tuple[tuple[str, str], ...] = (
    ("nome", "Unidade"),
    ("uf", "UF"),
    ("cidade", "Cidade"),
    ("consultor", "Consultor"),
    ("master_franquia", "Master franquia"),
    ("master", "Master (Growth)"),
    ("coorte_rotulo", "Maturidade"),
    ("meses_operacao", "Meses de operação"),
    ("severidade_rotulo", "Diagnóstico"),
    ("alertas_texto", "Alertas"),
    ("faixa_faturamento_rotulo", "Faixa de faturamento"),
)

# Metricas exportadas com o quarteto completo (valor, M-1, ranking, % vs media).
METRICAS_CARTEIRA: tuple[tuple[str, str], ...] = (
    ("faturamento", "Faturamento"),
    ("ativos", "Alunos ativos"),
    ("pagantes", "Recorrentes"),
    ("agregadores", "Agregadores"),
    ("receita_por_recorrente", "Receita por recorrente"),
    ("churn_pct", "Churn %"),
    ("conversao_pct", "Conversão %"),
    ("nps", "NPS"),
    ("saldo_operacional", "Saldo operacional"),
    ("pct_agregador_alunos", "Dependência de agregador %"),
)


# ---------------------------------------------------------------------------
# Formatacao
# ---------------------------------------------------------------------------


def _br(valor: object, casas: int = 0) -> str:
    """Numero em pt-BR (milhar com ponto, decimal com virgula). Vazio se nao houver dado."""
    if valor is None:
        return ""
    try:
        numero = float(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(valor)
    if numero != numero:  # NaN
        return ""
    texto = f"{numero:,.{casas}f}"
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _celula(valor: object) -> str:
    """Valor para a celula do CSV/XLSX: numero em pt-BR, texto como veio."""
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if isinstance(valor, (int, float)):
        return _br(valor, 0 if float(valor).is_integer() else 2)
    return "" if valor is None else str(valor)


def _linhas_carteira(payload: Mapping[str, Any]) -> tuple[list[str], list[list[str]]]:
    """Cabecalho + linhas do export tabular, a partir do payload da carteira."""
    cabecalho = [rotulo for _, rotulo in COLUNAS_CARTEIRA]
    for _, rotulo in METRICAS_CARTEIRA:
        cabecalho += [rotulo, f"{rotulo} (M-1)", f"{rotulo} (ranking)", f"{rotulo} (% vs média)"]

    linhas: list[list[str]] = []
    for unidade in payload.get("unidades", []):
        alertas = "; ".join(a.get("titulo", "") for a in unidade.get("alertas", []))
        registro = dict(unidade)
        registro["alertas_texto"] = alertas
        linha = [_celula(registro.get(chave)) for chave, _ in COLUNAS_CARTEIRA]
        metricas = unidade.get("metricas", {})
        for chave, _ in METRICAS_CARTEIRA:
            metrica = metricas.get(chave) or {}
            rank = metrica.get("rank")
            total = metrica.get("rank_total")
            linha += [
                _celula(metrica.get("atual")),
                _celula(metrica.get("m1")),
                f"{int(rank)}/{int(total)}" if rank and total else "",
                _celula(metrica.get("vs_media_pct")),
            ]
        linhas.append(linha)
    return cabecalho, linhas


# ---------------------------------------------------------------------------
# CSV / XLSX
# ---------------------------------------------------------------------------


def carteira_csv(payload: Mapping[str, Any]) -> bytes:
    """CSV da carteira, no dialeto da casa (`;` + utf-8-sig)."""
    cabecalho, linhas = _linhas_carteira(payload)
    buffer = StringIO()
    escritor = csv.writer(buffer, delimiter=CSV_SEPARADOR, lineterminator="\r\n")
    escritor.writerow(cabecalho)
    escritor.writerows(linhas)
    return buffer.getvalue().encode(CSV_ENCODING)


def carteira_xlsx(payload: Mapping[str, Any]) -> bytes:
    """XLSX da carteira, com a aba de metodo junto.

    A segunda aba nao e' enfeite: sem ela, a planilha circula pela rede sem dizer de que
    competencia e' o numero nem qual regua acendeu cada alerta.
    """
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    cabecalho, linhas = _linhas_carteira(payload)
    livro = openpyxl.Workbook()
    aba = livro.active
    aba.title = "Carteira"
    aba.append(cabecalho)
    for linha in linhas:
        aba.append(linha)

    negrito_branco = Font(bold=True, color="FFFFFF")
    fundo = PatternFill("solid", fgColor="00A79D")
    for celula in aba[1]:
        celula.font = negrito_branco
        celula.fill = fundo
        celula.alignment = Alignment(wrap_text=True, vertical="center")
    aba.freeze_panes = "B2"
    for indice, titulo in enumerate(cabecalho, start=1):
        letra = openpyxl.utils.get_column_letter(indice)
        aba.column_dimensions[letra].width = min(max(12, len(titulo) + 2), 34)

    metodo = livro.create_sheet("Método")
    for linha in _linhas_de_metodo(payload):
        metodo.append(linha)
    metodo.column_dimensions["A"].width = 30
    metodo.column_dimensions["B"].width = 96

    saida = BytesIO()
    livro.save(saida)
    return saida.getvalue()


def _linhas_de_metodo(payload: Mapping[str, Any]) -> list[list[str]]:
    linhas = [
        ["Fonte", "Growth API (growth_api_historico.parquet) - camada paralela, read-only M1"],
        ["Competência", str(payload.get("mes", ""))],
        ["Dia de referência", str(payload.get("referencia", ""))],
        ["Comparação M-1", str(payload.get("referencia_m1", ""))],
        ["Diagnóstico calculado em", str(payload.get("competencia_diagnostico", ""))],
        ["", ""],
        ["Réguas vigentes", ""],
    ]
    for chave, regua in (payload.get("reguas") or {}).items():
        limiar = regua.get("limiar")
        sentido = {"acima": "acima de", "abaixo": "abaixo de", "persistencia": "por"}.get(
            str(regua.get("sentido")), ""
        )
        meses = regua.get("meses")
        detalhe = (
            f"{sentido} {_br(limiar, 1)} {regua.get('unidade', '')}"
            if meses is None
            else f"{sentido} {int(meses)} meses fechados seguidos"
        )
        linhas.append([str(regua.get("rotulo", chave)), detalhe.strip()])
    linhas.append(["", ""])
    for nota in payload.get("notas", []):
        linhas.append(["Nota", str(nota)])
    return linhas


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

_LINHAS_POR_PAGINA = 22


def carteira_pdf(payload: Mapping[str, Any]) -> bytes:
    """PDF da carteira: capa com os KPIs da rede + tabela paginada por prioridade."""
    pdf = UltraPDF()
    unidades: Sequence[Mapping[str, Any]] = payload.get("unidades", [])
    subtitulo = f"Competência {payload.get('mes', '')} - até {payload.get('referencia', '')}"

    pdf.add_page()
    faixa_de_titulo(pdf, "Rede Ultra - carteira", subtitulo)
    _cartoes_da_rede(pdf, payload)
    _resumo_do_semaforo(pdf, payload)
    rodape(pdf, _texto_do_rodape(payload))

    cabecalho = [
        (30.0, "#", "L"),
        (176.0, "Unidade", "L"),
        (34.0, "UF", "L"),
        (96.0, "Consultor", "L"),
        (86.0, "Maturidade", "L"),
        (92.0, "Faturamento", "R"),
        (62.0, "Ativos", "R"),
        (56.0, "Churn", "R"),
        (48.0, "NPS", "R"),
        (206.0, "Diagnóstico", "L"),
    ]
    for inicio in range(0, max(len(unidades), 1), _LINHAS_POR_PAGINA):
        bloco = unidades[inicio : inicio + _LINHAS_POR_PAGINA]
        pdf.add_page()
        faixa_de_titulo(pdf, "Carteira por prioridade", subtitulo, rgb=ULTRA_MAGENTA)
        y = 76.0
        linha_de_tabela(pdf, 36.0, y, cabecalho, negrito=True, fundo=CINZA_CLARO)
        y += 18.0
        for posicao, unidade in enumerate(bloco, start=inicio + 1):
            metricas = unidade.get("metricas", {})
            severidade = str(unidade.get("severidade", "ok"))
            resumo = str(unidade.get("resumo", ""))
            linha_de_tabela(
                pdf,
                36.0,
                y,
                [
                    (30.0, str(posicao), "L"),
                    (176.0, str(unidade.get("nome", ""))[:30], "L"),
                    (34.0, str(unidade.get("uf", "")), "L"),
                    (96.0, str(unidade.get("consultor") or "-")[:16], "L"),
                    (86.0, str(unidade.get("coorte_rotulo", ""))[:14], "L"),
                    (92.0, _br(_valor(metricas, "faturamento")), "R"),
                    (62.0, _br(_valor(metricas, "ativos")), "R"),
                    (56.0, _br(_valor(metricas, "churn_pct"), 1), "R"),
                    (48.0, _br(_valor(metricas, "nps"), 0), "R"),
                    (206.0, resumo[:74], "L"),
                ],
                cor=COR_SEVERIDADE.get(severidade, CINZA_TEXTO),
            )
            y += 16.0
        rodape(pdf, _texto_do_rodape(payload))

    return bytes(pdf.output())


def _valor(metricas: Mapping[str, Any], chave: str) -> object:
    return (metricas.get(chave) or {}).get("atual")


def _cartoes_da_rede(pdf: UltraPDF, payload: Mapping[str, Any]) -> None:
    kpis = payload.get("kpis", {})
    cartoes = [
        ("Faturamento no período", _br(_valor(kpis, "faturamento")), "R$"),
        ("Alunos ativos", _br(_valor(kpis, "ativos")), ""),
        ("Churn", _br(_valor(kpis, "churn_pct"), 1) + "%", "média ponderada"),
        ("Receita por recorrente", "R$ " + _br(_valor(kpis, "receita_por_recorrente"), 2), ""),
        ("NPS", _br(_valor(kpis, "nps"), 1), f"meta {int(payload.get('meta_nps', 60))}"),
    ]
    largura = (PAGINA_LARGURA - 72 - 4 * 12) / 5
    for indice, (rotulo, valor, apoio) in enumerate(cartoes):
        cartao(
            pdf,
            36.0 + indice * (largura + 12),
            84.0,
            largura,
            72.0,
            rotulo=rotulo,
            valor=valor,
            apoio=apoio,
        )


def _resumo_do_semaforo(pdf: UltraPDF, payload: Mapping[str, Any]) -> None:
    semaforo = payload.get("semaforo", {})
    total = sum(int(v or 0) for v in semaforo.values()) or 1
    pdf.set_text_color(*CINZA_TEXTO)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(36, 182)
    pdf.cell(400, 16, ascii_seguro("Como está a rede"))

    y = 210.0
    for chave, rotulo in (
        ("alta", "Prioridade alta"),
        ("media", "Atenção"),
        ("ok", "Sem alerta"),
        ("sem_base", "Sem base de comparação"),
    ):
        quantidade = int(semaforo.get(chave, 0) or 0)
        pdf.set_fill_color(*COR_SEVERIDADE[chave])
        pdf.rect(36, y, 10, 10, style="F")
        pdf.set_text_color(*CINZA_TEXTO)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_xy(52, y - 1)
        pdf.cell(300, 12, ascii_seguro(f"{rotulo}: {quantidade} unidades ({quantidade / total:.0%})"))
        largura_barra = 420.0 * quantidade / total
        pdf.set_fill_color(*COR_SEVERIDADE[chave])
        pdf.rect(300, y, max(largura_barra, 0.5), 10, style="F")
        y += 22.0

    notas = payload.get("notas", [])
    pdf.set_text_color(120, 120, 120)
    pdf.set_font("Helvetica", "", 8.5)
    for indice, nota in enumerate(notas[:4]):
        pdf.set_xy(36, 320 + indice * 13)
        pdf.cell(PAGINA_LARGURA - 72, 11, ascii_seguro(f"- {nota}"))


def _texto_do_rodape(payload: Mapping[str, Any]) -> str:
    """As reguas vigentes VAO no rodape: e' impossivel a tela dizer uma e o motor aplicar
    outra."""
    reguas = payload.get("reguas") or {}
    partes = []
    for regua in reguas.values():
        limiar = regua.get("limiar")
        if regua.get("meses") is not None:
            partes.append(f"{regua.get('rotulo')}: {int(regua['meses'])} meses")
        else:
            sinal = ">" if regua.get("sentido") == "acima" else "<"
            partes.append(f"{regua.get('rotulo')}: {sinal} {_br(limiar, 1)}")
    return ascii_seguro(
        "Fonte: Growth API - camada paralela, read-only sobre o M1. Réguas: "
        + " | ".join(partes)
    )


def ficha_pdf(payload: Mapping[str, Any]) -> bytes:
    """PDF da ficha de uma unidade: identidade, quarteto, coorte e recomendacoes."""
    unidade = payload.get("unidade", {})
    diagnostico = payload.get("diagnostico", {})
    pdf = UltraPDF()
    pdf.add_page()
    faixa_de_titulo(
        pdf,
        str(unidade.get("nome", "Unidade")),
        f"{unidade.get('uf', '')} - competencia {payload.get('mes', '')}",
    )

    pdf.set_text_color(*CINZA_TEXTO)
    pdf.set_font("Helvetica", "", 10)
    identidade = " | ".join(
        parte
        for parte in (
            str(unidade.get("cidade") or ""),
            f"Consultor: {unidade.get('consultor') or 'a atribuir'}",
            f"Master: {unidade.get('master_franquia') or unidade.get('master') or '-'}",
            f"Maturidade: {unidade.get('coorte_rotulo') or '-'}",
            f"Inaugurada em {unidade.get('inauguracao') or '-'}",
        )
        if parte
    )
    pdf.set_xy(36, 68)
    pdf.cell(PAGINA_LARGURA - 72, 12, ascii_seguro(identidade))

    severidade = str(diagnostico.get("severidade", "ok"))
    pdf.set_fill_color(*COR_SEVERIDADE.get(severidade, CINZA_TEXTO))
    pdf.rect(36, 88, 300, 22, style="F")
    pdf.set_text_color(*BRANCO)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(44, 92)
    pdf.cell(290, 14, ascii_seguro(str(diagnostico.get("severidade_rotulo", ""))))

    metricas = payload.get("metricas", {})
    cabecalho = [
        (220.0, "Métrica", "L"),
        (110.0, "Mês", "R"),
        (110.0, "M-1", "R"),
        (110.0, "Ranking", "R"),
        (130.0, "% vs média da rede", "R"),
        (200.0, "Coorte (mediana)", "R"),
    ]
    y = 124.0
    linha_de_tabela(pdf, 36.0, y, cabecalho, negrito=True, fundo=CINZA_CLARO)
    y += 18.0
    referencias = (payload.get("coorte") or {}).get("metricas", {})
    for chave, rotulo in METRICAS_CARTEIRA:
        metrica = metricas.get(chave) or {}
        if metrica.get("atual") is None:
            continue
        rank, total = metrica.get("rank"), metrica.get("rank_total")
        casas = 1 if chave.endswith("_pct") or chave == "nps" else 0
        referencia = (referencias.get(chave) or {}).get("p50")
        linha_de_tabela(
            pdf,
            36.0,
            y,
            [
                (220.0, rotulo, "L"),
                (110.0, _br(metrica.get("atual"), casas), "R"),
                (110.0, _br(metrica.get("m1"), casas), "R"),
                (110.0, f"{int(rank)}/{int(total)}" if rank and total else "-", "R"),
                (130.0, _br(metrica.get("vs_media_pct"), 1) + "%" if metrica.get("vs_media_pct") is not None else "-", "R"),
                (200.0, _br(referencia, casas) if referencia is not None else "-", "R"),
            ],
        )
        y += 15.0

    y += 8.0
    coorte = payload.get("coorte") or {}
    pdf.set_text_color(120, 120, 120)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_xy(36, y)
    pdf.cell(
        PAGINA_LARGURA - 72,
        11,
        ascii_seguro(
            f"Comparada com {coorte.get('n', 0)} unidades - base: {coorte.get('base_rotulo', '-')}"
        ),
    )

    recomendacoes = diagnostico.get("recomendacoes") or []
    if recomendacoes:
        pdf.add_page()
        faixa_de_titulo(
            pdf,
            "O que fazer",
            str(unidade.get("nome", "")),
            rgb=ULTRA_TURQUESA,
        )
        y = 84.0
        for item in recomendacoes[:6]:
            pdf.set_text_color(*ULTRA_MAGENTA)
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_xy(36, y)
            pdf.cell(PAGINA_LARGURA - 72, 14, ascii_seguro(str(item.get("titulo", ""))))
            y += 18.0
            pdf.set_text_color(*CINZA_TEXTO)
            pdf.set_font("Helvetica", "", 9.5)
            pdf.set_xy(36, y)
            pdf.multi_cell(PAGINA_LARGURA - 72, 12, ascii_seguro(str(item.get("corpo", ""))))
            y = pdf.get_y() + 12.0
            if y > PAGINA_ALTURA - 70:
                break
    rodape(pdf, _texto_do_rodape(payload))
    return bytes(pdf.output())
