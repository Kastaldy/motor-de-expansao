from __future__ import annotations

import pandas as pd
from pyproj import Transformer
from shapely.geometry import box
from shapely.ops import transform

from motor_expansao.dashboard.censo_map import render_mapas_censitarios_combinados
from motor_expansao.dashboard.censo_point import (
    CRS_ORIGEM_CENSO,
    _local_metric_crs,
    analisar_ponto_censitario_setores,
)
from motor_expansao.dashboard.censo_report import (
    PDF_SECTION_HEADERS,
    gerar_csv_setores_censitarios,
    gerar_payloads_download_relatorio_censitario,
    gerar_pdf_relatorio_pontual_censitario,
    gerar_pdf_relatorio_pontual_classico,
    render_downloads_relatorio_censitario,
)

LAT_C = -23.55
LNG_C = -46.63


def _to_wgs_geometry(local_geom):
    transformer = Transformer.from_crs(_local_metric_crs(LAT_C, LNG_C), CRS_ORIGEM_CENSO, always_xy=True)
    return transform(transformer.transform, local_geom)


def _sector_record(cod_setor: str, local_geom, *, pop: float, renda: float, score: float):
    geom_wgs = _to_wgs_geometry(local_geom)
    minx, miny, maxx, maxy = geom_wgs.bounds
    return {
        "cod_setor": cod_setor,
        "uf": "SP",
        "cod_municipio": "3550308",
        "nome_municipio": "SAO PAULO",
        "area_setor_m2": float(local_geom.area),
        "geometry_wkb": geom_wgs.wkb,
        "bbox_minx": minx,
        "bbox_miny": miny,
        "bbox_maxx": maxx,
        "bbox_maxy": maxy,
        "pop_total_setor_2022": pop,
        "renda_per_capita_setor_2022_calibrada": renda,
        "densidade_pop_setor_hab_km2": pop / (local_geom.area / 1_000_000.0),
        "score_setor_2022_calibrado": score,
        "flag_renda_disponivel": True,
        "flag_geometria_valida": True,
        "qualidade_join_uf": "A",
    }


def _sample_result():
    setores = pd.DataFrame(
        [
            _sector_record("355030801000001", box(-700, -700, 0, 700), pop=800, renda=2100, score=64),
            _sector_record("355030801000002", box(0, -700, 700, 700), pop=1400, renda=2600, score=86),
        ]
    )
    competitors = pd.DataFrame(
        [{"nome_unidade": "Smart Fit Teste", "lat": LAT_C, "lng": LNG_C + 0.004, "rede": "smart_fit"}]
    )
    ultra = pd.DataFrame([{"nome_unidade": "Ultra Teste", "lat": LAT_C + 0.003, "lng": LNG_C}])
    result = analisar_ponto_censitario_setores(
        LAT_C,
        LNG_C,
        setores,
        competitors_df=competitors,
        ultra_df=ultra,
    )
    mapas = render_mapas_censitarios_combinados(
        LAT_C,
        LNG_C,
        setores,
        competitors_df=competitors,
        ultra_df=ultra,
        width=720,
        height=520,
        basemap=False,
    )
    return result, mapas


def test_export_csv_setores_censitarios_gera_bytes_utf8_sig_com_sep_ponto_virgula():
    result, _ = _sample_result()

    csv_bytes = gerar_csv_setores_censitarios(result)

    assert csv_bytes.startswith(b"\xef\xbb\xbf")
    text = csv_bytes.decode("utf-8-sig")
    assert "cod_setor;uf;cod_municipio" in text
    assert "355030801000001" in text
    assert "geometry_wkb" not in text


_RESIDUAL_OK = {
    "score_oportunidade_residual": 42.5,
    "oferta_efetiva_disponivel": 1200.0,
    "sam_fitness_potencial": 3000.0,
    "oferta_consumida_mercado_estimada": 1800.0,
}

# Strings de PII reais da lamina de contato do .pptx (image24) — NUNCA podem vazar no PDF.
_PII_FORBIDDEN = (
    b"vinicius",
    b"Vinicius",
    b"Vin\xedcius",
    b"96346-2974",
    b"@ultraacademia.com.br",
)


def _count_layer_titles(pdf_bytes: bytes) -> int:
    """Conta as 3 paginas de choropleth por TITULO (densidade/renda/score).

    A camada Concorrentes (so-pins) vive na pagina "Concorrentes" (`_competitors_page`),
    contada a parte. "Score censitario" tambem aparece no Big Numbers, mas o titulo da
    pagina de choropleth e o mesmo texto — a contagem por titulo segue == 3.
    """
    titulos = (b"Populacao - Densidade", b"Renda per capita", b"Score censitario")
    return sum(1 for titulo in titulos if titulo in pdf_bytes)


def test_export_pdf_executivo_gera_bytes_com_secoes_obrigatorias_e_mapa():
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(
        result, mapas, residual=_RESIDUAL_OK, ultra_dir="data/ultra"
    )

    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert len(pdf_bytes) > 15_000
    for header in PDF_SECTION_HEADERS:
        assert header.encode("latin-1") in pdf_bytes
    # Estrutura de 7 paginas (capa, pop, renda, score, concorrentes, big numbers, credito).
    assert b"/Count 7" in pdf_bytes
    # 3 paginas de choropleth (densidade/renda/score) contadas por titulo; a camada
    # Concorrentes (so-pins) e a 4a imagem de mapa, embutida na pagina de Concorrentes.
    assert _count_layer_titles(pdf_bytes) == 3
    assert pdf_bytes.count(b"/Subtype /Image") >= 4
    assert b"setor_censitario_intersecao_area_1p5km" in pdf_bytes


def test_pdf_embute_tres_camadas():
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(result, mapas, ultra_dir="data/ultra")

    assert _count_layer_titles(pdf_bytes) == 3


def test_pdf_big_numbers_com_residual_e_nd():
    result, mapas = _sample_result()

    pdf_com = gerar_pdf_relatorio_pontual_censitario(result, mapas, residual=_RESIDUAL_OK)
    # Rotulos das 8 metricas presentes (4x2). NB: parenteses literais sao escapados (\( \)) no
    # stream PDF, entao verificamos o prefixo antes do "(alunos)"/"(est.)".
    for rotulo in (
        b"Populacao total no raio",
        b"Renda per capita media",
        b"Score censitario medio",
        b"Score censitario maximo",
        b"SAM Fitness",
        b"Residual Fitness",
        b"Concorrentes no raio",
        b"Consumo concorrentes",
    ):
        assert rotulo in pdf_com
    # SAM e Residual Fitness saem em ALUNOS (numero), nao score: sam=3000, residual=1200, consumo=1800.
    assert b"3.000" in pdf_com
    assert b"1.200" in pdf_com
    assert b"1.800" in pdf_com

    # Sem residual -> "n/d" auditavel.
    pdf_sem = gerar_pdf_relatorio_pontual_censitario(result, mapas, residual=None)
    assert b"n/d" in pdf_sem


def test_pdf_offline_safe_sem_assets(tmp_path):
    """Sem os assets de branding -> PDF valido com fundo solido, sem excecao."""
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(
        result, mapas, residual=_RESIDUAL_OK, ultra_dir=tmp_path
    )

    assert pdf_bytes.startswith(b"%PDF")
    assert b"/Count 7" in pdf_bytes
    for header in PDF_SECTION_HEADERS:
        assert header.encode("latin-1") in pdf_bytes


def test_pdf_sem_pii_de_pessoas():
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(
        result, mapas, residual=_RESIDUAL_OK, ultra_dir="data/ultra"
    )

    for needle in _PII_FORBIDDEN:
        assert needle not in pdf_bytes


def test_pdf_marca_dagua_com_solicitante():
    """Com solicitante -> marca d'agua "Ultra Academia | {solicitante}" embutida (stream OFF)."""
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(
        result, mapas, residual=_RESIDUAL_OK, solicitante="Analista Teste"
    )

    assert b"Ultra Academia" in pdf_bytes
    assert b"Analista Teste" in pdf_bytes
    # 7 paginas preservadas e camadas de choropleth intactas (marca d'agua nao cria paginas).
    assert b"/Count 7" in pdf_bytes
    assert _count_layer_titles(pdf_bytes) == 3


def test_pdf_marca_dagua_sem_solicitante():
    """Sem solicitante (None) -> so "Ultra Academia"; default seguro sem nome (anti-PII)."""
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(
        result, mapas, residual=_RESIDUAL_OK, solicitante=None
    )

    assert b"Ultra Academia" in pdf_bytes
    assert b"Analista Teste" not in pdf_bytes
    assert b"/Count 7" in pdf_bytes
    assert _count_layer_titles(pdf_bytes) == 3


def test_pdf_marca_dagua_em_todas_as_paginas():
    """D2=todas as 7 paginas: a marca d'agua "Ultra Academia" aparece >= 7x nos bytes crus."""
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(
        result, mapas, residual=_RESIDUAL_OK, solicitante="Analista Teste"
    )

    # Uma ocorrencia da marca d'agua por pagina (7) -> contagem minima verificavel >= 7.
    assert pdf_bytes.count(b"Ultra Academia") >= 7


def test_pdf_atribuicao_de_tiles_no_rodape():
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(result, mapas)

    assert b"OpenStreetMap" in pdf_bytes
    assert b"CARTO" in pdf_bytes


def test_pdf_footer_cita_voyager():
    # Atribuicao de tiles segue valida no PDF (rodape do credit_page). O nome do provedor
    # "Voyager" vive no PNG do mapa (embutido como imagem, nao texto raw), entao verificamos
    # o provedor na constante do modulo de mapa (base CLARA Voyager, BLK-CENSO-03).
    result, mapas = _sample_result()
    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(result, mapas)
    assert b"OpenStreetMap" in pdf_bytes
    assert b"CARTO" in pdf_bytes
    import motor_expansao.dashboard.censo_map as m

    assert m._BASEMAP_PROVIDER_ATTR == "Voyager"


def test_pdf_retrocompat_aceita_bytes_unico_legado():
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(result, mapas["densidade"])

    assert pdf_bytes.startswith(b"%PDF-1.4")
    # Bytes unico legado -> so a camada de densidade recebe mapa; renda/score ficam sem mapa.
    assert b"Populacao - Densidade" in pdf_bytes
    assert b"Mapa indisponivel para esta camada." in pdf_bytes
    # Apenas 1 mapa real + (capa/credito reusam o asset de capa) -> conta de mapas reais via titulo.
    assert _count_layer_titles(pdf_bytes) == 3  # titulos das 3 paginas existem; mapas, nao


def test_pdf_concorrentes_contagem_total_e_mais_n_quando_excede_10():
    """D4=B (BLK-EST-02): >10 redes no raio -> cabecalho com '(N no total)' e '... e mais N'.

    Sem PII: os nomes vem da coluna de UNIDADE (`rede`/`nome_unidade`), nunca de pessoa.
    """
    setores = pd.DataFrame(
        [
            _sector_record("355030801000001", box(-700, -700, 0, 700), pop=800, renda=2100, score=64),
            _sector_record("355030801000002", box(0, -700, 700, 700), pop=1400, renda=2600, score=86),
        ]
    )
    # 12 concorrentes + 1 Ultra = 13 redes (>10) bem dentro do raio de 1.5 km.
    competitors = pd.DataFrame(
        [
            {
                "nome_unidade": f"Rede Teste {i}",
                "lat": LAT_C + 0.0001 * i,
                "lng": LNG_C + 0.0001 * i,
                "rede": f"rede_{i}",
            }
            for i in range(12)
        ]
    )
    ultra = pd.DataFrame([{"nome_unidade": "Ultra Teste", "lat": LAT_C + 0.0002, "lng": LNG_C}])
    result = analisar_ponto_censitario_setores(
        LAT_C, LNG_C, setores, competitors_df=competitors, ultra_df=ultra
    )
    mapas = render_mapas_censitarios_combinados(
        LAT_C, LNG_C, setores, competitors_df=competitors, ultra_df=ultra,
        width=720, height=520, basemap=False,
    )

    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(result, mapas, residual=_RESIDUAL_OK)

    total = len(result["concorrentes_raio"]) + len(result["ultra_raio"])
    assert total > 10
    # NB: parenteses literais sao escapados (\( \)) no stream PDF -> verifica o miolo " no total".
    assert f"{total} no total".encode("latin-1") in pdf_bytes
    assert f"... e mais {total - 10}".encode("latin-1") in pdf_bytes
    # Contrato preservado.
    assert b"/Count 7" in pdf_bytes
    for needle in _PII_FORBIDDEN:
        assert needle not in pdf_bytes


def test_pdf_concorrentes_sem_contagem_quando_ate_10():
    """D4=B: <=10 redes -> cabecalho simples, sem sufixo de total nem '... e mais'."""
    result, mapas = _sample_result()  # 1 concorrente + 1 Ultra = 2 redes
    pdf_bytes = gerar_pdf_relatorio_pontual_censitario(result, mapas, residual=_RESIDUAL_OK)

    assert b"Redes no raio de 1.5 km" in pdf_bytes
    assert b"no total" not in pdf_bytes
    assert b"... e mais" not in pdf_bytes


def test_payloads_e_helper_streamlit_expoem_downloads_csv_pdf():
    result, mapas = _sample_result()

    payloads = gerar_payloads_download_relatorio_censitario(
        result,
        mapas,
        filename_prefix="teste_relatorio",
        residual=_RESIDUAL_OK,
    )

    assert payloads.csv_filename == "teste_relatorio_setores.csv"
    assert payloads.pdf_filename == "teste_relatorio.pdf"
    assert payloads.csv_bytes
    assert payloads.pdf_bytes.startswith(b"%PDF")

    class DummyStreamlit:
        def __init__(self):
            self.calls = []

        def download_button(self, label, *, data, file_name, mime):
            self.calls.append(
                {"label": label, "data": data, "file_name": file_name, "mime": mime}
            )

    dummy = DummyStreamlit()
    rendered = render_downloads_relatorio_censitario(
        dummy,
        result,
        mapas,
        filename_prefix="teste_relatorio",
    )

    assert rendered.pdf_bytes.startswith(b"%PDF")
    assert [call["mime"] for call in dummy.calls] == ["text/csv", "application/pdf"]
    assert [call["file_name"] for call in dummy.calls] == [
        "teste_relatorio_setores.csv",
        "teste_relatorio.pdf",
    ]


# ---------------------------------------------------------------------------
# BLK-EST-05 — variante "Apresentacao Classica Ultra"
# ---------------------------------------------------------------------------


def test_classico_gera_7_paginas_e_secoes():
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        result, mapas, residual=_RESIDUAL_OK, ultra_dir="data/ultra"
    )

    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert b"/Count 7" in pdf_bytes
    for header in PDF_SECTION_HEADERS:
        assert header.encode("latin-1") in pdf_bytes
    assert _count_layer_titles(pdf_bytes) == 3
    assert pdf_bytes.count(b"/Subtype /Image") >= 4


def test_classico_link_clicavel_na_realizacao():
    result, mapas = _sample_result()

    # Com endereco real -> a query do link e o proprio endereco.
    pdf_com_end = gerar_pdf_relatorio_pontual_classico(
        result, mapas, residual=_RESIDUAL_OK, rotulo="Av Teste, 100"
    )
    assert b"https://www.google.com/maps/search/" in pdf_com_end
    assert b"Link para localizacao do ponto:" in pdf_com_end
    assert b"Av%20Teste" in pdf_com_end or b"Av Teste" in pdf_com_end

    # Sem rotulo -> a query cai na coordenada do result.
    pdf_sem_end = gerar_pdf_relatorio_pontual_classico(result, mapas, residual=_RESIDUAL_OK)
    assert b"https://www.google.com/maps/search/" in pdf_sem_end


def test_classico_offline_safe_sem_assets(tmp_path):
    """Sem qualquer asset (incl. icone_ultra.png) -> PDF valido, sem excecao."""
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        result, mapas, residual=_RESIDUAL_OK, ultra_dir=tmp_path
    )

    assert pdf_bytes.startswith(b"%PDF")
    assert b"/Count 7" in pdf_bytes
    for header in PDF_SECTION_HEADERS:
        assert header.encode("latin-1") in pdf_bytes


def test_classico_sem_pii_de_pessoas():
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        result, mapas, residual=_RESIDUAL_OK, ultra_dir="data/ultra"
    )

    for needle in _PII_FORBIDDEN:
        assert needle not in pdf_bytes


def test_classico_marca_dagua_solicitante():
    result, mapas = _sample_result()

    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        result, mapas, residual=_RESIDUAL_OK, solicitante="Analista Teste"
    )

    assert b"Ultra Academia | Analista Teste" in pdf_bytes
    assert pdf_bytes.count(b"Ultra Academia") >= 7


def test_classico_template_recente_inalterado():
    """Gerar o classico NAO altera os bytes do template recente (isolamento)."""
    result, mapas = _sample_result()

    antes = gerar_pdf_relatorio_pontual_censitario(
        result, mapas, residual=_RESIDUAL_OK, ultra_dir="data/ultra"
    )
    _ = gerar_pdf_relatorio_pontual_classico(
        result, mapas, residual=_RESIDUAL_OK, ultra_dir="data/ultra"
    )
    depois = gerar_pdf_relatorio_pontual_censitario(
        result, mapas, residual=_RESIDUAL_OK, ultra_dir="data/ultra"
    )

    assert antes == depois


def test_downloads_roteia_template_classico():
    """`template="classico"` roteia ao gerador classico; sem template = recente (default)."""
    result, mapas = _sample_result()

    p_classico = gerar_payloads_download_relatorio_censitario(
        result, mapas, filename_prefix="t", residual=_RESIDUAL_OK, template="classico"
    )
    p_recente = gerar_payloads_download_relatorio_censitario(
        result, mapas, filename_prefix="t", residual=_RESIDUAL_OK
    )

    assert p_classico.pdf_bytes.startswith(b"%PDF")
    assert p_recente.pdf_bytes.startswith(b"%PDF")
    # O classico tem a banda magenta de rodape + link clicavel -> bytes diferentes do recente.
    assert p_classico.pdf_bytes != p_recente.pdf_bytes
    assert b"Link para localizacao do ponto:" in p_classico.pdf_bytes
    assert b"Link para localizacao do ponto:" not in p_recente.pdf_bytes
