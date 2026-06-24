"""Testes do Relatorio Municipal (BLK-RELMUN-01).

Espelham o teste do Relatorio Pontual (`test_relatorio_pontual_censitario_export.py`):
agregacao, formula D1, 8 paginas/`/Count 8`/`%PDF-1.4`, headers das 8 secoes, fallback sem
`dominio_df`, fallback Pagina 6 sem bairro, fallback sem assets, anti-PII, mapas SEM rede
(`basemap=False`), contagem de pins por H3. NENHUM teste bate na rede.

CA2 (coexistencia): um teste prova que gerar o municipal NAO altera os bytes do Relatorio
Pontual recente nem do classico (isolamento estrito).
"""

from __future__ import annotations

import h3
import pandas as pd

from motor_expansao.dashboard.relatorio_municipal import (
    CAPACIDADE_UNIDADE,
    PDF_SECTION_HEADERS,
    _prettify_rede,
    _zonas_geometricas,
    agregar_municipio,
    gerar_payloads_download_relatorio_municipal,
    gerar_pdf_relatorio_municipal,
    render_download_relatorio_municipal,
    render_mapas_municipio,
)

# Strings de PII reais da lamina de contato do .pptx (image24) — NUNCA podem vazar no PDF.
_PII_FORBIDDEN = (
    b"vinicius",
    b"Vinicius",
    b"Vin\xedcius",
    b"96346-2974",
    b"@ultraacademia.com.br",
)


def _hex(lat: float, lng: float) -> str:
    return h3.latlng_to_cell(lat, lng, 7)


def _sample_df() -> pd.DataFrame:
    """4 hexes em SAO PAULO; 2 destacados (sam>=3000 & oferta>=2000), 2 nao."""
    base = [(-23.55, -46.63), (-23.56, -46.64), (-23.54, -46.62), (-23.57, -46.65)]
    rows = []
    for i, (la, lo) in enumerate(base):
        destacado = i < 2
        rows.append(
            {
                "hex_id": _hex(la, lo),
                "lat": la,
                "lng": lo,
                "nome_municipio": "SAO PAULO",
                "cidade": "SAO PAULO",
                "uf": "SP",
                "sam_fitness_potencial": 4000.0 if destacado else 1000.0,
                "oferta_efetiva_disponivel": 4451.0 if destacado else 500.0,
                "score_setor_2022_calibrado": 72.0 - i * 12.0,
                "score_oportunidade_residual": 60.0 - i * 5.0,
                "pop_total_setor_2022": 1500.0,
                "pop_total": 2000.0,
                "renda_per_capita": 3000.0,
                "penetracao_fitness_mercado_estimada": 12.5,
                "oferta_consumida_mercado_estimada": 1000.0 if destacado else 200.0,
            }
        )
    return pd.DataFrame(rows)


def _sample_dominio() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "nome_municipio": "SAO PAULO",
                "cluster_id": "c1",
                "tese_dominio": "dominar_white_space",
                "residual_total_cluster": 900.0,
                "oferta_efetiva_disponivel": 400.0,
            },
            {
                "nome_municipio": "SAO PAULO",
                "cluster_id": "c2",
                "tese_dominio": "abrir_com_disputa",
                "residual_total_cluster": 500.0,
                "oferta_efetiva_disponivel": 200.0,
            },
        ]
    )


def _sample_competitors() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"rede": "smart_fit", "lat": -23.55, "lng": -46.63, "hex_id_res7": _hex(-23.55, -46.63)},
            {"rede": "bio_ritmo", "lat": -23.56, "lng": -46.64, "hex_id_res7": _hex(-23.56, -46.64)},
            # fora do municipio (hex distante) -> nao deve contar
            {"rede": "smart_fit", "lat": -10.0, "lng": -40.0, "hex_id_res7": _hex(-10.0, -40.0)},
        ]
    )


def _sample_ultra() -> pd.DataFrame:
    return pd.DataFrame(
        [{"unidade": "Ultra Teste", "lat": -23.54, "lng": -46.62, "hex_id_res7": _hex(-23.54, -46.62)}]
    )


# ---------------------------------------------------------------------------
# Agregacao (D1, D4, D5, D6, zonas)
# ---------------------------------------------------------------------------


def test_agregar_municipio_formula_espaco_d1():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")

    # 2 destacados, soma 4451*2 = 8902; espaco = round(8902/2500) = 4.
    assert res["n_hex_amarelos"] == 2
    assert res["soma_oferta_amarelos"] == 8902.0
    assert res["espaco_para_academias"] == round(8902.0 / CAPACIDADE_UNIDADE)
    assert res["espaco_para_academias"] == 4
    assert res["n_hex_total"] == 4
    assert res["uf"] == "SP"


def test_agregar_municipio_mercado_residual_d4_e_score_d5():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")

    # Mercado/Residual = soma de oferta_efetiva_disponivel do municipio (4451*2 + 500*2).
    esperado = 4451.0 * 2 + 500.0 * 2
    assert res["mercado_disponivel_pessoas"] == esperado
    assert res["residual_total_alunos"] == esperado
    # Score medio/max NaN-safe.
    assert res["score_censo_max"] == 72.0
    assert abs(res["score_censo_medio"] - (72 + 60 + 48 + 36) / 4) < 1e-6


def test_agregar_municipio_zonas_d2_d7():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", dominio_df=_sample_dominio())

    zonas = res["zonas"]
    assert res["n_zonas"] == 2
    # Ordenado por residual desc -> c1 (900) e Zona 1 = Ancora central; c2 (500) = Flancos.
    assert zonas[0]["zona_n"] == 1 and zonas[0]["rotulo"] == "Ancora central"
    assert zonas[0]["cluster_id"] == "c1"
    assert zonas[1]["zona_n"] == 2 and zonas[1]["rotulo"] == "Flancos laterais"


def test_agregar_municipio_pins_por_h3_d6():
    df = _sample_df()
    res = agregar_municipio(
        df,
        nome_municipio="SAO PAULO",
        competitors_df=_sample_competitors(),
        ultra_df=_sample_ultra(),
    )

    assert res["n_ultra"] == 1
    # 2 concorrentes dentro do municipio (o 3o cai num hex distante).
    assert res["n_concorrentes"] == 2
    assert res["concorrentes_por_rede"] == {"smart_fit": 1, "bio_ritmo": 1}


# ---------------------------------------------------------------------------
# FU1 — penetracao municipal, prettify de nomes, zonas geometricas
# ---------------------------------------------------------------------------


def test_penetracao_fitness_pct_consumo_sobre_total():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    consumo = 1000.0 * 2 + 200.0 * 2  # 2400
    residual = 4451.0 * 2 + 500.0 * 2  # 9902
    esperado = 100.0 * consumo / (consumo + residual)
    assert res["consumo_total_alunos"] == consumo
    assert abs(res["penetracao_fitness_pct"] - esperado) < 1e-6


def test_penetracao_fitness_pct_denominador_zero_eh_nan():
    df = _sample_df()
    # Zera consumo e oferta -> denominador 0 -> nan.
    df["oferta_efetiva_disponivel"] = 0.0
    df["oferta_consumida_mercado_estimada"] = 0.0
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    import math

    assert math.isnan(res["penetracao_fitness_pct"])


def test_prettify_rede_overrides_e_fallback():
    assert _prettify_rede("allp_fit") == "Allp Fit"
    assert _prettify_rede("bio_ritmo") == "Bio Ritmo"
    assert _prettify_rede("smart_fit") == "Smart Fit"
    assert _prettify_rede("bluefit") == "BlueFit"
    # Fallback generico: title-case trocando "_" por espaco.
    assert _prettify_rede("foo_bar_gym") == "Foo Bar Gym"
    assert _prettify_rede("") == "Concorrente"


def test_zonas_geometricas_ate_3_zonas_com_contagens():
    df = _sample_df()
    out = _zonas_geometricas(df)
    zonas = out["zonas"]
    assert 1 <= len(zonas) <= 3
    rotulos = {z["rotulo"] for z in zonas}
    assert rotulos.issubset({"Ancora central", "Flancos laterais", "Cerco"})
    # Soma das contagens == nro de hexes mapeados em hex_zona.
    assert sum(z["n_hex"] for z in zonas) == len(out["hex_zona"])
    # Numeracao sequencial 1..N.
    assert [z["zona_n"] for z in zonas] == list(range(1, len(zonas) + 1))


def test_zonas_geometricas_em_agregar_municipio():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    assert res["n_zonas_geo"] == len(res["zonas_geo"])
    assert res["n_zonas_geo"] >= 1
    assert isinstance(res["hex_zona_geo"], dict)


def test_zonas_geometricas_fallback_vazio():
    df = _sample_df().drop(columns=["hex_id"])
    out = _zonas_geometricas(df)
    assert out == {"hex_zona": {}, "zonas": []}


def test_agregar_municipio_sem_dominio_zonas_vazias():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", dominio_df=None)
    assert res["zonas"] == []
    assert res["n_zonas"] == 0


def test_agregar_municipio_fallback_cidade():
    df = _sample_df().drop(columns=["nome_municipio"])
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    assert res["n_hex_total"] == 4


# ---------------------------------------------------------------------------
# Mapas offline (sem rede)
# ---------------------------------------------------------------------------


def test_mapas_municipio_offline_sem_rede():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", dominio_df=_sample_dominio())
    mapas = render_mapas_municipio(
        df, res, competitors_df=_sample_competitors(), ultra_df=_sample_ultra(), basemap=False
    )
    assert set(mapas) == {"resumo", "score", "residual", "dominio", "cobertura"}
    for png in mapas.values():
        assert png.startswith(b"\x89PNG")
        assert len(png) > 1000


# ---------------------------------------------------------------------------
# PDF (8 paginas / headers / formato)
# ---------------------------------------------------------------------------


def test_pdf_municipal_8_paginas_e_secoes():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", dominio_df=_sample_dominio())
    mapas = render_mapas_municipio(df, res, basemap=False)

    pdf_bytes = gerar_pdf_relatorio_municipal(res, mapas, ultra_dir="data/ultra")

    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert b"/Count 9" in pdf_bytes
    assert len(pdf_bytes) > 15_000
    for header in PDF_SECTION_HEADERS:
        assert header.encode("latin-1") in pdf_bytes
    # Carimbo de versao (D8) no rodape.
    assert b"BLK-RELMUN-01" in pdf_bytes
    # Atribuicao de tiles (DEC-011) no rodape.
    assert b"OpenStreetMap" in pdf_bytes
    assert b"CARTO" in pdf_bytes
    # AJUSTE 2 (FU1): legenda do criterio de inclusao do hexagono no Slide 2, com os
    # limiares REAIS do _hex_destacado_mask (SAM>=3000 & oferta>=2000).
    assert b"SAM Fitness >= 3.000" in pdf_bytes
    assert b"Residual Fitness >= 2.000" in pdf_bytes
    # FU1 (slide novo, pos-capa): "Visao Geral do Municipio" com bloco de regioes consideradas.
    assert b"Visao Geral do Municipio" in pdf_bytes
    assert b"REGIOES CONSIDERADAS" in pdf_bytes
    assert b"regioes consideradas nas paginas seguintes" in pdf_bytes


def test_agregar_municipio_cobertura_aprovados_reprovados():
    """FU1: agregar expoe n_aprovados/n_reprovados/n_hex_municipio para o slide de cobertura."""
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", dominio_df=_sample_dominio())
    assert res["n_hex_municipio"] == res["n_hex_total"]
    assert res["n_aprovados"] == res["n_hex_amarelos"]
    assert res["n_reprovados"] == res["n_hex_municipio"] - res["n_aprovados"]
    assert res["n_reprovados"] >= 0


def test_mapa_cobertura_offline():
    """FU1: a camada 'cobertura' (aprovados/reprovados do municipio, sem pins) gera PNG offline."""
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", dominio_df=_sample_dominio())
    mapas = render_mapas_municipio(df, res, basemap=False)
    assert mapas["cobertura"].startswith(b"\x89PNG")
    assert len(mapas["cobertura"]) > 1000


def test_pdf_municipal_offline_safe_sem_assets(tmp_path):
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", dominio_df=_sample_dominio())
    mapas = render_mapas_municipio(df, res, basemap=False)

    pdf_bytes = gerar_pdf_relatorio_municipal(res, mapas, ultra_dir=tmp_path)

    assert pdf_bytes.startswith(b"%PDF")
    assert b"/Count 9" in pdf_bytes
    for header in PDF_SECTION_HEADERS:
        assert header.encode("latin-1") in pdf_bytes


def _df_3_aprovados() -> pd.DataFrame:
    """3 hexes APROVADOS (sam>=3000 & oferta>=2000) em celulas res-7 DISTINTAS e bem separadas
    (~7 km entre si) -> 3 zonas geometricas (Ancora/Flancos/Cerco). Mais 1 reprovado com score
    (prova que a estrategia NAO se espalha para nao-aprovados — decisao de produto 2026-06-24)."""
    coords = [(-23.50, -46.60), (-23.55, -46.65), (-23.60, -46.70)]
    rows = []
    for la, lo in coords:
        rows.append(
            {
                "hex_id": _hex(la, lo),
                "lat": la,
                "lng": lo,
                "nome_municipio": "SAO PAULO",
                "cidade": "SAO PAULO",
                "uf": "SP",
                "sam_fitness_potencial": 4000.0,
                "oferta_efetiva_disponivel": 4451.0,
                "score_setor_2022_calibrado": 72.0,
                "score_oportunidade_residual": 60.0,
                "pop_total_setor_2022": 1500.0,
                "pop_total": 2000.0,
                "renda_per_capita": 3000.0,
                "penetracao_fitness_mercado_estimada": 12.5,
                "oferta_consumida_mercado_estimada": 1000.0,
            }
        )
    # 1 reprovado (sam/oferta baixos) com score notna, em celula distinta.
    rows.append(
        {
            "hex_id": _hex(-23.40, -46.50),
            "lat": -23.40,
            "lng": -46.50,
            "nome_municipio": "SAO PAULO",
            "cidade": "SAO PAULO",
            "uf": "SP",
            "sam_fitness_potencial": 1000.0,
            "oferta_efetiva_disponivel": 500.0,
            "score_setor_2022_calibrado": 60.0,
            "score_oportunidade_residual": 40.0,
            "pop_total_setor_2022": 1500.0,
            "pop_total": 2000.0,
            "renda_per_capita": 3000.0,
            "penetracao_fitness_mercado_estimada": 12.5,
            "oferta_consumida_mercado_estimada": 200.0,
        }
    )
    return pd.DataFrame(rows)


def test_pdf_municipal_fallback_sem_dominio_pagina_6():
    """Sem dominio_df -> Paginas 5-6 usam as zonas GEOMETRICAS (FU1), sem excecao.

    Decisao de produto (2026-06-24): as zonas sao formadas SOMENTE pelos hexes APROVADOS
    (sem fallback para todo o municipio). 3 aprovados em celulas distintas -> 3 zonas.
    """
    df = _df_3_aprovados()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", dominio_df=None)
    mapas = render_mapas_municipio(df, res, basemap=False)

    pdf_bytes = gerar_pdf_relatorio_municipal(res, mapas)

    assert b"/Count 9" in pdf_bytes
    # BLK-RELMUN-02: sem fonte de bairro, a Pagina 6 cai no fallback gracioso por zona
    # geometrica (sem a antiga nota "indisponivel" como texto principal).
    assert b"Bairros indisponiveis na base atual" not in pdf_bytes
    assert b"Bairros nao mapeados na base IBGE 2022" in pdf_bytes
    # FU1: as 3 estrategias geometricas aparecem (3 aprovados em celulas distintas).
    assert b"Ancora central" in pdf_bytes
    assert b"Flancos laterais" in pdf_bytes
    assert b"Cerco" in pdf_bytes


def test_zonas_geometricas_so_aprovados_sem_fallback():
    """Decisao de produto (2026-06-24): com 1 unico hex aprovado, forma-se SO 1 zona
    (Ancora) — a estrategia NAO se espalha para os hexes nao-aprovados do municipio."""
    df = _df_3_aprovados().copy()
    # Rebaixa 2 dos 3 aprovados -> sobra 1 aprovado; os rebaixados tem score notna.
    df.loc[df.index[1:3], "sam_fitness_potencial"] = 1000.0
    df.loc[df.index[1:3], "oferta_efetiva_disponivel"] = 500.0
    out = _zonas_geometricas(df)
    assert len(out["zonas"]) == 1
    assert out["zonas"][0]["rotulo"] == "Ancora central"
    assert out["zonas"][0]["n_hex"] == 1
    assert len(out["hex_zona"]) == 1


def test_pdf_municipal_fallback_sem_hexes_relevantes_pagina_5():
    """Sem hexes relevantes -> Pagina 5 cai no texto explicativo, sem excecao."""
    df = _sample_df().drop(columns=["hex_id"])
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", dominio_df=None)
    mapas = render_mapas_municipio(df, res, basemap=False)

    pdf_bytes = gerar_pdf_relatorio_municipal(res, mapas)

    assert b"/Count 9" in pdf_bytes
    assert b"Hexes relevantes insuficientes" in pdf_bytes


def test_pdf_municipal_pagina_6_fallback_sem_bairro():
    """BLK-RELMUN-02: sem `bairros_por_hex` -> Pagina 6 cai no fallback por zona, sem excecao
    e sem a antiga nota 'indisponivel' como texto principal."""
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", dominio_df=_sample_dominio())
    assert res["bairros_por_zona"] == [] or all(
        not z.get("bairros") for z in res["bairros_por_zona"]
    )
    mapas = render_mapas_municipio(df, res, basemap=False)
    pdf_bytes = gerar_pdf_relatorio_municipal(res, mapas)
    assert b"/Count 9" in pdf_bytes
    assert b"Bairros indisponiveis na base atual" not in pdf_bytes
    assert b"Bairros nao mapeados na base IBGE 2022" in pdf_bytes
    # Sem PII no fallback.
    for needle in _PII_FORBIDDEN:
        assert needle not in pdf_bytes


def _bairros_por_hex_sample(df: pd.DataFrame) -> dict[str, str]:
    """Mapa hex_id -> bairro REAL (nomes IBGE-like) para os 4 hexes do _sample_df."""
    hexes = list(df["hex_id"])
    nomes = ["Centro", "Bela Vista", "Cidade Nova", "Cascata"]
    return {str(h): nomes[i % len(nomes)] for i, h in enumerate(hexes)}


def test_agregar_municipio_bairros_por_zona_com_fonte():
    """A2: com `bairros_por_hex`, agregar popula `bairros_por_zona` agrupado por zona."""
    df = _sample_df()
    bairros = _bairros_por_hex_sample(df)
    res = agregar_municipio(
        df, nome_municipio="SAO PAULO", uf="SP", bairros_por_hex=bairros
    )
    bpz = res["bairros_por_zona"]
    assert isinstance(bpz, list) and bpz
    # Cada zona presente reporta os bairros distintos dela.
    todos = {b for z in bpz for b in z["bairros"]}
    assert todos  # pelo menos 1 bairro real agrupado
    assert todos.issubset({"Centro", "Bela Vista", "Cidade Nova", "Cascata"})
    assert res["n_bairros_total"] == sum(z["n_bairros"] for z in bpz)
    # Default None preserva comportamento anterior (sem bairros).
    res_sem = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    assert all(not z.get("bairros") for z in res_sem["bairros_por_zona"])


def test_pdf_municipal_pagina_6_com_bairros_reais():
    """A2: nomes de bairro REAIS aparecem nos bytes do PDF, /Count 9 mantido, sem PII."""
    df = _sample_df()
    bairros = _bairros_por_hex_sample(df)
    res = agregar_municipio(
        df, nome_municipio="SAO PAULO", uf="SP", dominio_df=_sample_dominio(),
        bairros_por_hex=bairros,
    )
    mapas = render_mapas_municipio(df, res, basemap=False)
    pdf_bytes = gerar_pdf_relatorio_municipal(res, mapas)

    assert b"/Count 9" in pdf_bytes
    # Pelo menos um bairro real impresso na Pagina 6.
    assert any(nome.encode("latin-1") in pdf_bytes for nome in ("Centro", "Bela Vista", "Cidade Nova", "Cascata"))
    # Nota de fonte IBGE quando ha bairros (cascata bairro -> subdistrito -> distrito).
    assert b"bairro do setor" in pdf_bytes
    # Sem a nota de fallback nem PII.
    assert b"Bairros indisponiveis na base atual" not in pdf_bytes
    for needle in _PII_FORBIDDEN:
        assert needle not in pdf_bytes


def test_carregar_bairros_por_hex_fallback_sem_dir():
    """A2.3: helper de leitura retorna {} sem censo_geo_dir/cod (offline, sem excecao)."""
    from motor_expansao.dashboard.relatorio_municipal import _carregar_bairros_por_hex

    assert _carregar_bairros_por_hex(None, None, None) == {}
    assert _carregar_bairros_por_hex("SP", "3550308", None) == {}


def test_pdf_municipal_marca_dagua_solicitante():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    mapas = render_mapas_municipio(df, res, basemap=False)

    pdf_bytes = gerar_pdf_relatorio_municipal(res, mapas, solicitante="Analista Teste")

    assert b"Ultra Academia" in pdf_bytes
    assert b"Analista Teste" in pdf_bytes
    # Uma marca d'agua por pagina (8) -> >= 8 ocorrencias.
    assert pdf_bytes.count(b"Ultra Academia") >= 8


def test_pdf_municipal_sem_pii():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", dominio_df=_sample_dominio())
    mapas = render_mapas_municipio(df, res, basemap=False)

    pdf_bytes = gerar_pdf_relatorio_municipal(res, mapas, ultra_dir="data/ultra")

    for needle in _PII_FORBIDDEN:
        assert needle not in pdf_bytes


def test_payloads_e_helper_streamlit_download():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    mapas = render_mapas_municipio(df, res, basemap=False)

    payloads = gerar_payloads_download_relatorio_municipal(res, mapas)
    assert payloads.pdf_bytes.startswith(b"%PDF")
    assert payloads.pdf_filename == "relatorio_municipal_sp_sao_paulo.pdf"

    class DummyStreamlit:
        def __init__(self):
            self.calls = []

        def download_button(self, label, *, data, file_name, mime):
            self.calls.append({"label": label, "data": data, "file_name": file_name, "mime": mime})

    dummy = DummyStreamlit()
    rendered = render_download_relatorio_municipal(dummy, res, mapas)
    assert rendered.pdf_bytes.startswith(b"%PDF")
    assert [c["mime"] for c in dummy.calls] == ["application/pdf"]


# ---------------------------------------------------------------------------
# CA2 — coexistencia: o Relatorio Pontual fica BYTE-A-BYTE intocado.
# ---------------------------------------------------------------------------


def test_coexistencia_relatorio_pontual_intocado():
    """Gerar o municipal NAO altera os bytes do Relatorio Pontual (recente e classico)."""
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
        gerar_pdf_relatorio_pontual_censitario,
    )

    lat_c, lng_c = -23.55, -46.63

    def _to_wgs(local_geom):
        tr = Transformer.from_crs(_local_metric_crs(lat_c, lng_c), CRS_ORIGEM_CENSO, always_xy=True)
        return transform(tr.transform, local_geom)

    def _rec(cod, geom, *, pop, renda, score):
        gw = _to_wgs(geom)
        minx, miny, maxx, maxy = gw.bounds
        return {
            "cod_setor": cod, "uf": "SP", "cod_municipio": "3550308", "nome_municipio": "SAO PAULO",
            "area_setor_m2": float(geom.area), "geometry_wkb": gw.wkb,
            "bbox_minx": minx, "bbox_miny": miny, "bbox_maxx": maxx, "bbox_maxy": maxy,
            "pop_total_setor_2022": pop, "renda_per_capita_setor_2022_calibrada": renda,
            "densidade_pop_setor_hab_km2": pop / (geom.area / 1_000_000.0),
            "score_setor_2022_calibrado": score, "flag_renda_disponivel": True,
            "flag_geometria_valida": True, "qualidade_join_uf": "A",
        }

    setores = pd.DataFrame(
        [
            _rec("355030801000001", box(-700, -700, 0, 700), pop=800, renda=2100, score=64),
            _rec("355030801000002", box(0, -700, 700, 700), pop=1400, renda=2600, score=86),
        ]
    )
    result = analisar_ponto_censitario_setores(lat_c, lng_c, setores)
    mapas_pontual = render_mapas_censitarios_combinados(
        lat_c, lng_c, setores, width=720, height=520, basemap=False
    )

    antes = gerar_pdf_relatorio_pontual_censitario(result, mapas_pontual, ultra_dir="data/ultra")

    # Gera o municipal no meio.
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", dominio_df=_sample_dominio())
    _ = gerar_pdf_relatorio_municipal(res, render_mapas_municipio(df, res, basemap=False))

    depois = gerar_pdf_relatorio_pontual_censitario(result, mapas_pontual, ultra_dir="data/ultra")

    assert antes == depois
