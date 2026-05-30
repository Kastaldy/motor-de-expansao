from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from textwrap import wrap
from typing import Any

import pandas as pd
from PIL import Image

from motor_expansao.dashboard.censo_point import METODO_RELATORIO_PONTUAL_CENSITARIO

PDF_SECTION_HEADERS = (
    "Relatorio Pontual Censitario",
    "KPIs",
    "Mapa",
    "Concorrencia",
    "Setores",
    "Metodologia",
    "Qualidade e limites",
)

CSV_SETOR_COLUMNS = [
    "cod_setor",
    "uf",
    "cod_municipio",
    "nome_municipio",
    "area_setor_m2",
    "area_intersecao_m2",
    "peso_area_setor",
    "pop_total_setor_2022",
    "pop_estimada_intersecao",
    "renda_per_capita_setor_2022_calibrada",
    "densidade_pop_setor_hab_km2",
    "score_setor_2022_calibrado",
    "flag_renda_disponivel",
    "flag_geometria_valida",
    "qualidade_join_uf",
]


@dataclass(frozen=True)
class RelatorioCensitarioDownloadPayloads:
    csv_bytes: bytes
    csv_filename: str
    pdf_bytes: bytes
    pdf_filename: str


def _setores_from_result(result: dict[str, Any] | pd.DataFrame) -> pd.DataFrame:
    if isinstance(result, pd.DataFrame):
        setores = result
    else:
        setores = result.get("setores_intersectados", pd.DataFrame())
    if setores is None or setores.empty:
        return pd.DataFrame(columns=CSV_SETOR_COLUMNS)
    columns = [column for column in CSV_SETOR_COLUMNS if column in setores.columns]
    extra = [column for column in setores.columns if column not in columns and not column.startswith("geometry")]
    return setores.loc[:, columns + extra].copy()


def gerar_csv_setores_censitarios(result: dict[str, Any] | pd.DataFrame) -> bytes:
    """Gera CSV em memoria para a tabela auditavel de setores intersectados."""
    setores = _setores_from_result(result)
    return setores.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")


def _format_number(value: Any, decimals: int = 0, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "-"
    number = float(value)
    if decimals <= 0:
        text = f"{number:,.0f}".replace(",", ".")
    else:
        text = f"{number:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text}{suffix}"


def _point_name(result: dict[str, Any]) -> str:
    lat = result.get("lat")
    lng = result.get("lng")
    if lat is None or lng is None:
        return "ponto"
    return f"{float(lat):.5f}_{float(lng):.5f}".replace("-", "m").replace(".", "p")


def _pdf_escape(text: str) -> str:
    safe = text.encode("latin-1", errors="replace").decode("latin-1")
    return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _text_page(lines: list[tuple[str, int]]) -> bytes:
    commands = ["BT"]
    y = 800
    for text, size in lines:
        if text == "":
            y -= 10
            continue
        commands.append(f"/F1 {size} Tf")
        commands.append(f"54 {y} Td ({_pdf_escape(text)}) Tj")
        y -= max(size + 7, 15)
        if y < 54:
            break
    commands.append("ET")
    return "\n".join(commands).encode("latin-1", errors="replace")


def _wrap_text(text: str, width: int = 86) -> list[str]:
    if not text:
        return [""]
    return wrap(text, width=width, break_long_words=False) or [text]


def _kpi_lines(result: dict[str, Any]) -> list[tuple[str, int]]:
    lines: list[tuple[str, int]] = [
        ("Relatorio Pontual Censitario", 20),
        ("KPIs", 15),
    ]
    lat = result.get("lat")
    lng = result.get("lng")
    if lat is not None and lng is not None:
        lines.append((f"Centro: {float(lat):.6f}, {float(lng):.6f}", 11))
    lines.extend(
        [
            (f"Raio analisado: {_format_number(result.get('raio_km'), 1, ' km')}", 11),
            (f"Area do circulo: {_format_number(result.get('area_km2'), 2, ' km2')}", 11),
            (f"Setores intersectados: {_format_number(result.get('n_setores'))}", 11),
            (f"Populacao estimada no raio: {_format_number(result.get('pop_total_raio'))}", 11),
            (
                "Renda per capita media: "
                f"R$ {_format_number(result.get('renda_per_capita_media_raio'), 2)}",
                11,
            ),
            (
                "Densidade populacional: "
                f"{_format_number(result.get('densidade_pop_raio_hab_km2'), 1, ' hab/km2')}",
                11,
            ),
            (f"Score censitario medio: {_format_number(result.get('score_setor_medio'), 2)}", 11),
            (f"Score censitario maximo: {_format_number(result.get('score_setor_max'), 2)}", 11),
            ("", 11),
            ("Concorrencia", 15),
            (f"Concorrentes no raio: {_format_number(result.get('n_concorrentes'))}", 11),
            (f"Unidades Ultra no raio: {_format_number(result.get('n_ultra'))}", 11),
        ]
    )
    return lines


def _point_rows(points: pd.DataFrame, label: str) -> list[str]:
    if points is None or points.empty:
        return [f"{label}: sem pontos no raio."]
    name_col = next((column for column in ("nome_unidade", "nome", "brand", "rede") if column in points.columns), None)
    rows: list[str] = []
    for _, row in points.head(8).iterrows():
        name = str(row.get(name_col, label)) if name_col else label
        dist = _format_number(row.get("dist_km"), 2, " km")
        rows.append(f"{label}: {name} ({dist})")
    return rows


def _details_lines(result: dict[str, Any]) -> list[tuple[str, int]]:
    setores = _setores_from_result(result)
    lines: list[tuple[str, int]] = [("Setores", 15)]
    if setores.empty:
        lines.append(("Nenhum setor intersectado no raio.", 11))
    else:
        sort_col = "pop_estimada_intersecao" if "pop_estimada_intersecao" in setores.columns else setores.columns[0]
        table = setores.sort_values(sort_col, ascending=False, kind="stable").head(10)
        for _, row in table.iterrows():
            sector = row.get("cod_setor", "-")
            pop = _format_number(row.get("pop_estimada_intersecao"))
            peso = _format_number(row.get("peso_area_setor"), 3)
            renda = _format_number(row.get("renda_per_capita_setor_2022_calibrada"), 2)
            lines.append((f"{sector} | pop {pop} | peso {peso} | renda R$ {renda}", 10))
    lines.append(("", 11))
    for text in _point_rows(result.get("concorrentes_raio", pd.DataFrame()), "Concorrente"):
        lines.append((text, 10))
    for text in _point_rows(result.get("ultra_raio", pd.DataFrame()), "Ultra"):
        lines.append((text, 10))
    lines.extend(
        [
            ("", 11),
            ("Metodologia", 15),
            (
                f"Metodo: {result.get('metodo', METODO_RELATORIO_PONTUAL_CENSITARIO)}.",
                11,
            ),
        ]
    )
    method = (
        "O relatorio cruza setores censitarios reais do IBGE 2022 com um circulo metrico "
        "de 1.5 km ao redor da coordenada. Populacao estimada usa peso de area "
        "intersectada; renda e scores sao ponderados por populacao estimada, com fallback "
        "por area quando necessario."
    )
    for line in _wrap_text(method):
        lines.append((line, 10))
    lines.extend([("", 11), ("Qualidade e limites", 15)])
    limits = (
        "A distribuicao intrassetor e aproximada por area. O PDF nao promete precisao "
        "de lote, rua ou quadra e nao altera score_priorizacao, carteira, plano ou "
        "artefatos oficiais do M1."
    )
    for line in _wrap_text(limits):
        lines.append((line, 10))
    return lines


def _jpeg_from_png(png_bytes: bytes) -> tuple[bytes, int, int] | None:
    if not png_bytes:
        return None
    try:
        image = Image.open(BytesIO(png_bytes)).convert("RGB")
    except Exception:
        return None
    output = BytesIO()
    image.save(output, format="JPEG", quality=88, optimize=True)
    return output.getvalue(), image.width, image.height


def _map_content(image_width: int, image_height: int) -> bytes:
    page_w, _page_h = 595, 842
    max_w, max_h = 505, 650
    scale = min(max_w / image_width, max_h / image_height)
    draw_w = image_width * scale
    draw_h = image_height * scale
    x = (page_w - draw_w) / 2
    y = 96
    commands = [
        "BT",
        "/F1 18 Tf",
        f"54 800 Td ({_pdf_escape('Mapa')}) Tj",
        "/F1 10 Tf",
        f"54 778 Td ({_pdf_escape('Mapa censitario estatico, gerado offline para o relatorio.')}) Tj",
        "ET",
        "q",
        f"{draw_w:.2f} 0 0 {draw_h:.2f} {x:.2f} {y:.2f} cm",
        "/Im1 Do",
        "Q",
    ]
    return "\n".join(commands).encode("latin-1")


def _build_pdf(content_pages: list[bytes], image: tuple[bytes, int, int] | None = None) -> bytes:
    objects: dict[int, bytes] = {}
    catalog_num = 1
    pages_num = 2
    font_num = 3
    next_num = 4
    objects[font_num] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"

    image_num: int | None = None
    if image is not None:
        image_bytes, image_width, image_height = image
        image_num = next_num
        next_num += 1
        objects[image_num] = (
            f"<< /Type /XObject /Subtype /Image /Width {image_width} /Height {image_height} "
            f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length {len(image_bytes)} >>\n"
        ).encode("ascii") + b"stream\n" + image_bytes + b"\nendstream"

    page_nums: list[int] = []
    for idx, content in enumerate(content_pages):
        content_num = next_num
        next_num += 1
        objects[content_num] = (
            f"<< /Length {len(content)} >>\n".encode("ascii") + b"stream\n" + content + b"\nendstream"
        )
        page_num = next_num
        next_num += 1
        page_nums.append(page_num)
        xobject = f" /XObject << /Im1 {image_num} 0 R >>" if image_num is not None and idx == 1 else ""
        objects[page_num] = (
            f"<< /Type /Page /Parent {pages_num} 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font_num} 0 R >>{xobject} >> "
            f"/Contents {content_num} 0 R >>"
        ).encode("ascii")

    kids = " ".join(f"{num} 0 R" for num in page_nums)
    objects[catalog_num] = f"<< /Type /Catalog /Pages {pages_num} 0 R >>".encode("ascii")
    objects[pages_num] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_nums)} >>".encode("ascii")

    output = BytesIO()
    output.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    for num in sorted(objects):
        offsets[num] = output.tell()
        output.write(f"{num} 0 obj\n".encode("ascii"))
        output.write(objects[num])
        output.write(b"\nendobj\n")

    xref_offset = output.tell()
    max_num = max(objects)
    output.write(f"xref\n0 {max_num + 1}\n".encode("ascii"))
    output.write(b"0000000000 65535 f \n")
    for num in range(1, max_num + 1):
        output.write(f"{offsets.get(num, 0):010d} 00000 n \n".encode("ascii"))
    output.write(
        f"trailer\n<< /Size {max_num + 1} /Root {catalog_num} 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return output.getvalue()


def gerar_pdf_relatorio_pontual_censitario(
    result: dict[str, Any],
    mapa_png_bytes: bytes | None = None,
) -> bytes:
    """Gera PDF executivo em memoria, sem criar artefatos permanentes."""
    pages = [_text_page(_kpi_lines(result))]
    image = _jpeg_from_png(mapa_png_bytes or b"")
    if image is not None:
        pages.append(_map_content(image[1], image[2]))
    pages.append(_text_page(_details_lines(result)))
    return _build_pdf(pages, image=image)


def gerar_payloads_download_relatorio_censitario(
    result: dict[str, Any],
    mapa_png_bytes: bytes | None = None,
    *,
    filename_prefix: str | None = None,
) -> RelatorioCensitarioDownloadPayloads:
    prefix = filename_prefix or f"relatorio_pontual_censitario_{_point_name(result)}"
    return RelatorioCensitarioDownloadPayloads(
        csv_bytes=gerar_csv_setores_censitarios(result),
        csv_filename=f"{prefix}_setores.csv",
        pdf_bytes=gerar_pdf_relatorio_pontual_censitario(result, mapa_png_bytes),
        pdf_filename=f"{prefix}.pdf",
    )


def render_downloads_relatorio_censitario(
    st_module: Any,
    result: dict[str, Any],
    mapa_png_bytes: bytes | None = None,
    *,
    filename_prefix: str | None = None,
) -> RelatorioCensitarioDownloadPayloads:
    """Renderiza botoes Streamlit e retorna os mesmos bytes para testes/reuso."""
    payloads = gerar_payloads_download_relatorio_censitario(
        result,
        mapa_png_bytes,
        filename_prefix=filename_prefix,
    )
    st_module.download_button(
        "Baixar CSV dos setores",
        data=payloads.csv_bytes,
        file_name=payloads.csv_filename,
        mime="text/csv",
    )
    st_module.download_button(
        "Baixar PDF executivo",
        data=payloads.pdf_bytes,
        file_name=payloads.pdf_filename,
        mime="application/pdf",
    )
    return payloads
