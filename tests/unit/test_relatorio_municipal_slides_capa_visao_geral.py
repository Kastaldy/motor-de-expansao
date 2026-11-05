"""Capa, rodape e slide 2 (Visao Geral) do Relatorio Municipal -- pedido de Juan, 2026-10-20.

- capa sem a marca "Ultra Academia | <solicitante> | <report_id>" (as demais paginas mantem);
- nenhuma pagina com a linha de rodape "Relatorio gerado pelo Motor ... | score M1 INALTERADO":
  a versao do contrato passa a viajar nos metadados do PDF (/Keywords);
- slide 2: mapa sem legenda, sem nomes e sem o amarelo do fallback municipal; os bairros
  aprovados viram uma tabela a direita, no lugar dos paineis de contagem.
"""

from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image

from motor_expansao.dashboard import relatorio_municipal as rm
from motor_expansao.dashboard.relatorio_municipal import (
    _COR_APROVADO_MUNICIPAL,
    UNIDADE_HEXAGONO,
    VERSAO_CONTRATO_MUNICIPAL,
    agregar_municipio,
    bairros_aprovados,
    gerar_pdf_relatorio_municipal,
    render_mapas_municipio,
)
from tests.unit.test_relatorio_municipal import (
    _bairros_geo_sample,
    _keywords_do_pdf,
    _paginas_do_pdf,
    _sample_df,
)

_paginas = _paginas_do_pdf


def _visao_geral(paginas: list[str]) -> str:
    return next(p for p in paginas if p.startswith("Visão Geral do Município"))


def _geo_ligado(df) -> dict:
    """Bairros sinteticos ligados aos hexes de `_sample_df`: Centro fica com os 2 destacados
    (oferta >= 2000), Bela Vista com os 2 reprovados."""
    geo = _bairros_geo_sample()
    hexes = list(df["hex_id"])
    geo["bairros"][0]["pesos_hex"] = {hexes[0]: 1.0, hexes[1]: 1.0}
    geo["bairros"][1]["pesos_hex"] = {hexes[2]: 1.0, hexes[3]: 1.0}
    return geo


def _pdf(*, unidade: str = "bairro", com_bairros: bool = True, report_id: str | None = "rid-123"):
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP",
                            bairros_geo=_geo_ligado(df) if com_bairros else None)
    mapas = render_mapas_municipio(df, res, basemap=False, unidade=unidade)
    return gerar_pdf_relatorio_municipal(res, mapas, solicitante="Analista Teste",
                                         report_id=report_id, unidade=unidade)


def test_capa_sem_marca_dagua_e_demais_paginas_com():
    paginas = _paginas(_pdf())
    assert "Ultra Academia | Analista Teste" not in paginas[0]
    assert all("Ultra Academia | Analista Teste" in p for p in paginas[1:])


def test_nenhuma_pagina_tem_o_rodape_e_a_versao_vai_para_os_metadados():
    pdf_bytes = _pdf()
    for i, texto in enumerate(_paginas(pdf_bytes), start=1):
        assert "Relatório gerado pelo Motor" not in texto, f"rodape na pagina {i}"
        assert "INALTERADO" not in texto, f"carimbo de versao na pagina {i}"
    keywords = _keywords_do_pdf(pdf_bytes)
    assert VERSAO_CONTRATO_MUNICIPAL in keywords
    assert "report_id=rid-123" in keywords


def test_versao_nos_metadados_mesmo_sem_report_id():
    assert VERSAO_CONTRATO_MUNICIPAL in _keywords_do_pdf(_pdf(report_id=None))


def test_cobertura_hexagono_sem_amarelo_e_sem_legenda(monkeypatch):
    df = _sample_df()
    # Um aprovado via fallback municipal: ate 2026-10-20 saia em amarelo-ambar.
    df["fonte_populacao_corte"] = ["setor_2022", "total_municipal", "setor_2022", "setor_2022"]
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")

    escritos: list[str] = []
    original = rm._draw_text

    def _espia(draw, xy, texto, *a, **kw):
        escritos.append(str(texto))
        return original(draw, xy, texto, *a, **kw)

    monkeypatch.setattr(rm, "_draw_text", _espia)
    png = render_mapas_municipio(df, res, basemap=False, unidade=UNIDADE_HEXAGONO)["cobertura"]
    arr = np.asarray(Image.open(BytesIO(png)).convert("RGB")).astype(int)
    perto = np.abs(arr - np.array(_COR_APROVADO_MUNICIPAL)).sum(axis=2) < 40
    assert int(perto.sum()) == 0, "o amarelo do fallback municipal ainda aparece no mapa"

    escritos.clear()
    rm._render_mapa_municipio(df, camada="cobertura", municipio_result=res, basemap=False)
    assert not any(t.startswith(("Aprovado", "Reprovado")) for t in escritos), escritos
    # O Resumo tambem perdeu a legenda (Juan, 2026-10-21: "em nenhuma hipotese"), e sem ela o
    # amarelo do fallback nao teria explicacao: o aprovado sai todo verde, como no Espaco.
    escritos.clear()
    png = rm._render_mapa_municipio(df, camada="resumo", municipio_result=res, basemap=False)
    assert not any(t.startswith(("Aprovado", "Reprovado")) for t in escritos), escritos
    arr = np.asarray(Image.open(BytesIO(png)).convert("RGB")).astype(int)
    perto = np.abs(arr - np.array(_COR_APROVADO_MUNICIPAL)).sum(axis=2) < 40
    assert int(perto.sum()) == 0, "o amarelo do fallback municipal ainda aparece no Resumo"


def test_bairros_aprovados_so_os_destacados_em_ordem_alfabetica():
    geo = _bairros_geo_sample(com_sobra=True)
    geo["metricas_mercado"] = True
    geo["bairros"][0]["destacado"] = True   # Centro
    geo["bairros"][1]["destacado"] = False  # Bela Vista
    geo["bairros"][2]["destacado"] = True   # a sobra nunca entra
    assert bairros_aprovados(geo) == ["Centro"]
    # Sem as metricas de mercado nao da para dizer quem e' aprovado.
    assert bairros_aprovados(_bairros_geo_sample()) is None


def test_slide2_lista_os_bairros_aprovados_nos_dois_modos():
    for unidade in ("bairro", UNIDADE_HEXAGONO):
        p2 = _visao_geral(_paginas(_pdf(unidade=unidade)))
        assert "BAIRROS APROVADOS" in p2, unidade
        assert "REGIÕES CONSIDERADAS" not in p2, unidade
        assert "Centro" in p2, unidade
        assert "Bela Vista" not in p2, unidade
        assert "As páginas seguintes consideram apenas" in p2, unidade


def test_slide2_sem_bairro_na_base_mantem_os_paineis():
    p2 = _visao_geral(_paginas(_pdf(com_bairros=False)))
    assert "REGIÕES CONSIDERADAS" in p2
    assert "BAIRROS APROVADOS" not in p2


def test_zoom_da_visao_geral_fecha_nos_bairros_aprovados_sem_cortar_nenhum():
    geo = _bairros_geo_sample()
    geo["bairros"][0]["destacado"] = True   # Centro
    geo["bairros"][1]["destacado"] = False  # Bela Vista, ao lado
    minx, miny, maxx, maxy = rm._bounds_bairros_aprovados(geo)
    xs = [x for x, _ in geo["bairros"][0]["aneis"][0]]
    ys = [y for _, y in geo["bairros"][0]["aneis"][0]]
    assert minx <= min(xs) and maxx >= max(xs) and miny <= min(ys) and maxy >= max(ys)
    # O vizinho reprovado fica de fora do enquadramento (fora a margem minima).
    assert maxx < max(x for x, _ in geo["bairros"][1]["aneis"][0])
    geo["bairros"][0]["destacado"] = False
    assert rm._bounds_bairros_aprovados(geo) is None


def test_zoom_da_visao_geral_hexagono_muda_o_quadro():
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    antes = rm._render_mapa_municipio(df, camada="cobertura", municipio_result=res, basemap=False)
    depois = render_mapas_municipio(df, res, basemap=False, unidade=UNIDADE_HEXAGONO)["cobertura"]
    assert antes != depois, "o quadro da Visao Geral nao fechou nos aprovados"


def _grade_de_bairros(n_lado: int, lado: float = 2000.0) -> dict:
    """`n_lado x n_lado` bairros quadrados lado a lado, no formato de `carregar_bairros_geo`."""
    from tests.unit.test_relatorio_municipal import _bairro_quadrado

    bairros = [
        _bairro_quadrado(f"B{i:02d}-{j:02d}", -5_190_000.0 + i * lado, -2_700_000.0 + j * lado, lado,
                         pop=1000.0 + i + j)
        for i in range(n_lado) for j in range(n_lado)
    ]
    return {"bairros": bairros, "contorno": [], "n_bairros": len(bairros), "n_setores": 100,
            "sem_localidade": 0, "cobertura": 1.0}


def test_dividir_bairros_numera_todos_uma_vez_e_respeita_o_teto():
    geo = _grade_de_bairros(10)  # 100 bairros
    div = rm.dividir_bairros_em_partes(geo, max_numerados=None)  # a divisao, sem o teto
    nomes = [str(b["nome"]) for b in geo["bairros"]]
    assert sorted(div["numero"]) == sorted(nomes)
    assert sorted(div["numero"].values()) == list(range(1, 101))
    assert len(div["partes"]) > 1
    assert all(len(p) <= rm._BAIRROS_POR_PARTE for p in div["partes"])
    # Cada bairro esta' em exatamente um lugar: uma parte ou o mapa geral.
    todos = [n for p in div["partes"] for n in p] + div["avulsos"]
    assert sorted(todos) == sorted(nomes)
    # Deterministica: a pagina refaz a divisao e tem de chegar no mesmo indice do mapa.
    assert rm.dividir_bairros_em_partes(geo, max_numerados=None)["numero"] == div["numero"]


def test_com_centenas_de_bairros_so_os_mais_populosos_ganham_numero():
    """CNEFE (DEC-076): Sao Jose dos Campos tem 331 bairros e numerar todos dava 40 paginas."""
    geo = _grade_de_bairros(10)  # 100 bairros; pop = 1000 + i + j
    div = rm.dividir_bairros_em_partes(geo)
    assert len(div["numero"]) == rm._BAIRROS_NUMERADOS_MAX == 40
    assert div["n_total"] == 100 and len(div["fora"]) == 60
    pop = {str(b["nome"]): b["pop"] for b in geo["bairros"]}
    assert min(pop[n] for n in div["numero"]) >= max(pop[n] for n in div["fora"])
    assert not set(div["fora"]) & set(div["numero"])


def test_dividir_bairros_corta_no_vazio_e_deixa_o_rural_isolado_no_mapa_geral():
    geo = _grade_de_bairros(5)  # 25 bairros juntos...
    from tests.unit.test_relatorio_municipal import _bairro_quadrado

    # ...e um bairro rural a 200 km: nao pode puxar o zoom de nenhuma parte.
    geo["bairros"].append(_bairro_quadrado("Rural", -5_190_000.0, -2_900_000.0, 4000.0, pop=50.0))
    div = rm.dividir_bairros_em_partes(geo)
    assert "Rural" in div["avulsos"]
    assert all("Rural" not in p for p in div["partes"])
    assert div["numero"]["Rural"] == max(div["numero"].values())


def test_bairros_oficiais_em_partes_gera_uma_pagina_por_parte():
    df = _sample_df()
    geo = _grade_de_bairros(8)  # 64 bairros
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", bairros_geo=geo)
    mapas = render_mapas_municipio(df, res, basemap=False)
    div = rm.dividir_bairros_em_partes(geo)
    k = len(div["partes"])
    assert k > 1
    assert {f"bairros_parte_{i}" for i in range(1, k + 1)} <= set(mapas)
    paginas = _paginas(gerar_pdf_relatorio_municipal(res, mapas))
    texto = " ".join(paginas)
    assert "PARTES DO MUNICÍPIO (40 de 64 bairros)" in texto
    assert "Numerados os 40 bairros mais populosos dos 64" in texto
    for i in range(1, k + 1):
        assert any(f"Parte {i} de {k}" in p for p in paginas), i


def test_todo_bairro_sem_numero_ganha_a_parte_do_numerado_mais_proximo():
    """SJC (2026-10-22): so' os 40 numerados tinham cor e o cinza cobria 84% do municipio."""
    geo = _grade_de_bairros(10)  # 100 bairros: 40 numerados, 60 de fora
    div = rm.dividir_bairros_em_partes(geo)
    assert set(div["parte_de"]) == {str(b["nome"]) for b in geo["bairros"]} - set(div["avulsos"])
    for k, parte in enumerate(div["partes"]):
        assert all(div["parte_de"][n] == k for n in parte)
    centro = {str(b["nome"]): b["rotulo_xy"] for b in geo["bairros"]}

    def _d2(a: str, b: str) -> float:
        return (centro[a][0] - div["ponto"][b][0]) ** 2 + (centro[a][1] - div["ponto"][b][1]) ** 2

    numerados = [n for p in div["partes"] for n in p]
    for nome in div["fora"]:
        perto = min(numerados, key=lambda n: (_d2(nome, n), div["numero"][n]))
        assert div["parte_de"][nome] == div["parte_de"][perto], nome
    assert rm.dividir_bairros_em_partes(geo)["parte_de"] == div["parte_de"]


def test_bairros_oficiais_pinta_o_municipio_inteiro_nas_cores_das_partes(monkeypatch):
    df = _sample_df()
    geo = _grade_de_bairros(10)
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", bairros_geo=geo)
    chamadas: list[dict] = []
    original = rm._render_mapa_bairros

    def _espia(bairros_geo, **kw):
        chamadas.append(kw)
        return original(bairros_geo, **kw)

    monkeypatch.setattr(rm, "_render_mapa_bairros", _espia)
    render_mapas_municipio(df, res, basemap=False, unidade=UNIDADE_HEXAGONO)
    div = rm.dividir_bairros_em_partes(geo)
    geral = next(c for c in chamadas if c.get("marcadores"))
    # Nenhum bairro em cinza: os de fora na cor clara da sua parte, os numerados na cheia.
    assert set(geral["cor_por_bairro"]) == set(div["parte_de"])
    assert not geral["apagados"]
    assert geral["cor_clara"] == set(div["fora"])
    assert not geral.get("so_contorno"), "a visao geral mostra as partes em cor cheia"
    for k, parte in enumerate(div["partes"]):
        mapa = next(c for c in chamadas if c.get("titulo") == f"Bairros oficiais - parte {k + 1}")
        da_parte = {n for n, kk in div["parte_de"].items() if kk == k}
        assert set(mapa["cor_por_bairro"]) == da_parte
        assert mapa["cor_clara"] == da_parte - set(parte)
        assert set(mapa["numeros"]) == set(parte)
        # Paginas das partes: o LIMITE do bairro, nao a cor cheia (Juan, 2026-10-22).
        assert mapa["so_contorno"] is True


def test_pagina_da_parte_contorna_o_bairro_na_cor_forte_sem_preencher():
    from tests.unit.test_relatorio_municipal import _bairro_quadrado

    lado = 40_000.0
    geo = {"bairros": [_bairro_quadrado("Unico", -5_190_000.0, -2_700_000.0, lado, pop=1000.0)],
           "contorno": [], "n_bairros": 1, "n_setores": 1, "sem_localidade": 0, "cobertura": 1.0}
    png = rm._render_mapa_bairros(geo, basemap=False, cor_por_bairro={"Unico": rm.ULTRA_LARANJA},
                                  so_contorno=True)
    img = np.asarray(Image.open(BytesIO(png)).convert("RGB")).astype(int)
    meio = img[img.shape[0] // 2, img.shape[1] // 2]
    assert all(v >= 240 for v in meio), f"o bairro saiu preenchido: {meio}"
    laranja = np.abs(img - np.array(rm.ULTRA_LARANJA)).sum(axis=2) < 25
    assert laranja.sum() > 1_000, "o contorno na cor da parte nao saiu forte"


def test_cor_da_parte_sai_cheia_e_nao_bege():
    """A composicao antiga aplicava o alpha tres vezes: o laranja da parte 3 saia bege."""
    from tests.unit.test_relatorio_municipal import _bairro_quadrado

    lado = 40_000.0
    geo = {"bairros": [_bairro_quadrado("Unico", -5_190_000.0, -2_700_000.0, lado, pop=1000.0)],
           "contorno": [], "n_bairros": 1, "n_setores": 1, "sem_localidade": 0, "cobertura": 1.0}

    def _centro(png: bytes) -> tuple[int, int, int]:
        img = np.asarray(Image.open(BytesIO(png)).convert("RGB")).astype(int)
        r, g, b = img[img.shape[0] // 2, img.shape[1] // 2]
        return int(r), int(g), int(b)

    r, g, b = _centro(rm._render_mapa_bairros(
        geo, basemap=False, cor_por_bairro={"Unico": rm.ULTRA_LARANJA}))
    # Laranja (243, 146, 0) com alpha 185 sobre o fundo (245, 245, 245): ~ (243, 173, 67).
    assert r > 230 and b < 90 and r - b > 150, (r, g, b)
    r2, _g2, b2 = _centro(rm._render_mapa_bairros(
        geo, basemap=False, cor_por_bairro={"Unico": rm.ULTRA_LARANJA}, cor_clara={"Unico"}))
    assert b2 > b and r2 > 230, "o tom claro tem de ser mais claro que o cheio, na mesma cor"


def test_partes_dizem_quantos_bairros_cada_cor_tem():
    df = _sample_df()
    geo = _grade_de_bairros(8)  # 64 bairros, 40 numerados
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", bairros_geo=geo)
    paginas = _paginas(gerar_pdf_relatorio_municipal(res, render_mapas_municipio(df, res, basemap=False)))
    geral = next(p for p in paginas if "PARTES DO MUNICÍPIO" in p)
    div = rm.dividir_bairros_em_partes(geo)
    com_total = 0
    for k, parte in enumerate(div["partes"]):
        total = sum(1 for kk in div["parte_de"].values() if kk == k)
        if total > len(parte):
            com_total += 1
            assert f"Parte {k + 1} - {len(parte)} de {total} bairros" in geral, (k, geral)
    assert com_total, "nenhuma parte recebeu bairro sem numero: o teste nao exercitou nada"
    assert "no tom mais claro da parte mais próxima" in geral
    assert "aparecem em cinza" not in geral


def test_numero_do_espaco_sai_num_circulo_por_cima_do_mapa(monkeypatch):
    """SJC (2026-10-22): o branco de 7 pt sumia sob as ruas e os nomes do fundo de ruas."""
    df = _sample_df()
    df["oferta_efetiva_disponivel"] = [4451.0, 6300.0, 500.0, 2100.0]
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    mapas = render_mapas_municipio(df, res, basemap=False)
    circulos: list[tuple[int, float]] = []
    original = rm._UltraPDF.ellipse

    def _espia(self, x, y, w, h, *a, **kw):
        if w == h:
            circulos.append((self.page_no(), w))
        return original(self, x, y, w, h, *a, **kw)

    monkeypatch.setattr(rm._UltraPDF, "ellipse", _espia)
    paginas = _paginas(gerar_pdf_relatorio_municipal(res, mapas))
    n_pag = 1 + next(i for i, p in enumerate(paginas) if p.startswith("Como chegamos ao Espaço"))
    pontos = res["espaco_rotulos"]["pontos"]
    assert pontos and all(t in paginas[n_pag - 1] for _x, _y, t in pontos)
    assert sum(1 for pag, w in circulos if pag == n_pag and w >= 13.0) == len(pontos)


def test_resumo_na_ordem_espaco_concorrentes_ultra_e_a_pagina_que_explica_o_espaco():
    paginas = _paginas(_pdf())
    i = next(k for k, p in enumerate(paginas) if p.startswith("Resumo da Região"))
    resumo = paginas[i]
    assert resumo.index("Espaço para academias") < resumo.index("Unidades Concorrentes") < resumo.index(
        "Unidades Ultra")
    explica = paginas[i + 1]
    assert explica.startswith("Como chegamos ao Espaço para academias")
    # Desde 2026-10-20 a pagina e' o MAPA com quantas academias cabem em cada regiao + o total.
    assert "ESPAÇO PARA ACADEMIAS" in explica and "ONDE CABEM MAIS" in explica
    assert "COMO LER ESTE NÚMERO" not in explica


def test_mapas_tematicos_por_bairro_sem_nome_em_placa(monkeypatch):
    """Nenhum mapa por bairro escreve o nome do bairro (2026-10-20); so' numero nos Oficiais."""
    df = _sample_df()
    geo = _geo_ligado(df)
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", bairros_geo=geo)
    escritos: list[str] = []
    original = rm._draw_text

    def _espia(draw, xy, texto, *a, **kw):
        escritos.append(str(texto))
        return original(draw, xy, texto, *a, **kw)

    monkeypatch.setattr(rm, "_draw_text", _espia)
    render_mapas_municipio(df, res, basemap=False)
    assert not any(t in ("Centro", "Bela Vista") for t in escritos), escritos


def test_ordem_do_relatorio_apresenta_mapas_oportunidade_estrategia_sintese():
    """Ordem pedida por Juan em 2026-10-20 (sem as paginas da praca, que sao condicionais)."""
    paginas = _paginas(_pdf())
    titulos = [p.splitlines()[0] if p else "" for p in paginas]
    esperado = ("Bairros Oficiais", "Score Censitário", "Residual Fitness",
                "Visão Geral do Município", "Resumo da Região", "Como chegamos ao Espaço",
                "Expansão de Domínio", "Bairros por Zona", "Síntese",
                "Espaço e academias")
    pos = [next(i for i, t in enumerate(titulos) if t.startswith(e)) for e in esperado]
    assert pos == sorted(pos), list(zip(esperado, pos, strict=True))


def test_legenda_do_score_traz_a_faixa_de_cada_cor():
    paginas = _paginas(_pdf())
    score = next(p for p in paginas if p.startswith("Score Censitário"))
    for faixa in ("70 ou mais", "50 a 70", "30 a 50", "abaixo de 30"):
        assert faixa in score, faixa


def test_legenda_do_score_mostra_a_renda_observada_de_cada_faixa():
    geo = _bairros_geo_sample()
    geo["bairros"][0].update(score=80.0, renda_pc=3000.0, densidade=12000.0)  # Centro: Alto
    geo["bairros"][1].update(score=40.0, renda_pc=900.0, densidade=8000.0)    # Bela Vista: Medio
    faixas = rm.renda_por_faixa_de_score(geo)
    assert faixas["Alto potencial"] == {"renda": (3000.0, 3000.0), "densidade": (12000.0, 12000.0), "n": 1,
                                        "renda_tipo": "per capita"}
    assert faixas["Médio"]["renda"] == (900.0, 900.0)
    assert "Médio-alto" not in faixas
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", bairros_geo=geo)
    paginas = _paginas(gerar_pdf_relatorio_municipal(res, render_mapas_municipio(df, res, basemap=False)))
    score = next(p for p in paginas if p.startswith("Score Censitário"))
    assert "R$ 3.000" in score and "R$ 900" in score
    assert "12.000 hab./km²" in score
    # A explicacao diz que o score NAO e' so' renda.
    assert "O que é o score censitário" in score and "relaciona renda e população" in score
    assert "sem bairro" in score  # faixas sem nenhum bairro dizem isso, nao inventam renda


def test_legenda_do_score_usa_a_renda_domiciliar_quando_o_bairro_a_tem():
    df = _sample_df()
    geo = _geo_ligado(df)
    geo["bairros"][0].update(score=80.0, densidade=12000.0)
    geo["bairros"][1].update(score=40.0, densidade=8000.0)
    hexes = list(df["hex_id"])
    dom = {h: 3000.0 for h in hexes}
    dom[hexes[0]] = 9000.0
    dom[hexes[1]] = 11000.0  # se os dois pontos cairem no mesmo hexagono, vale o ultimo
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", bairros_geo=geo,
                            renda_domiciliar_por_hex=dom)
    mapas = render_mapas_municipio(df, res, basemap=False)
    centro = next(b for b in res["bairros_geo"]["bairros"] if b["nome"] == "Centro")
    esperado = sum(dom[h] for h in set(centro["pesos_hex"])) / len(set(centro["pesos_hex"]))
    assert centro["renda_dom"] == esperado  # media dos hexagonos dele, pesos iguais
    score = next(p for p in _paginas(gerar_pdf_relatorio_municipal(res, mapas))
                 if p.startswith("Score Censitário"))
    assert "renda domiciliar média" in score
    assert "R$ " + f"{esperado:,.0f}".replace(",", ".") in score
    assert "quartil" not in score  # a nota do 1o ao 3o quartil saiu (2026-10-20)


def test_crescimento_compara_saldo_e_salario_com_a_mediana_da_uf_e_explica_a_confiabilidade():
    import pandas as pd

    from motor_expansao.dashboard import relatorio_praca as rp

    base = pd.DataFrame({
        "cres_chave_nome": ["SP|A", "SP|B", "SP|C", "RJ|D"],
        "dim_empresas_por1k": [60.0, 70.0, 80.0, 999.0],
        "cres_salario": [2000.0, 2200.0, 2400.0, 9999.0],
        "cres_salario_var": [5.0, 6.3, 8.0, 99.0],
    })
    ref = rp.referencias_da_uf(base, "SP")
    assert ref == {"salario": 2200.0, "salario_var": 6.3}  # a RJ nao entra
    linha = {
        "cres_tendencia": "estavel", "cres_saldo_empresas": 1308738, "dim_empresas_por1k": 110.0,
        "cres_dims": "Empresas:110.0:/mil:99:2020–2025", "cres_salario": 3005, "cres_salario_var": 1.0,
        "cres_confiab": "alta", "cres_vinculos": 5426281,
    }
    c = rp.resumir_crescimento(linha, uf="SP", referencias=ref)
    linhas = dict(c.linhas)
    assert linhas["Saldo de empresas 2020-2025"] == "1.308.738"
    # 2026-10-21 (Juan): sem o saldo por mil habitantes; o salario numa linha so', com a
    # variacao de 12 meses do lado e a mediana do estado (salario e variacao) embaixo.
    assert not any("por mil" in r for r in linhas)
    assert linhas["Salário de contratação"] == "R$ 3.005 (+1,0% em 12 meses)"
    assert c.subtitulos["Salário de contratação"] == (
        "mediana SP: R$ 2.200 (37% acima); variação na mediana: +6,3%"
    )
    assert not any(r.startswith(("Mediana de admiss", "Variação do salário")) for r in linhas)
    # Confiabilidade alta nao vira linha: ela so' importa quando a leitura de emprego e' fragil.
    assert not any("onfiabilidade" in r or "empregos formais" in r for r in linhas)
    fragil = dict(rp.resumir_crescimento({**linha, "cres_confiab": "baixa", "cres_vinculos": 3200},
                                         uf="SP", referencias=ref).linhas)
    assert fragil["Atenção: poucos empregos formais"] == "3 mil vínculos (leitura frágil)"
    # Sem referencias (caminho do Pontual), nenhuma mediana aparece.
    sem = rp.resumir_crescimento(linha, uf="SP")
    assert dict(sem.linhas)["Salário de contratação"] == "R$ 3.005 (+1,0% em 12 meses)"
    assert "Salário de contratação" not in sem.subtitulos


def test_barra_de_escala_dos_mapas_da_praca_mede_metro_de_chao():
    import math

    from motor_expansao.dashboard import relatorio_praca_mapas as rpm

    # Quadro em torno de Sao Paulo (~ -23,55): 1 km de chao = 1 km / cos(lat) em unidades 3857.
    y = 6_378_137.0 * math.asinh(math.tan(math.radians(-23.55)))
    q = rpm._Quadro((-5_190_000.0, y - 10_000.0, -5_170_000.0, y + 10_000.0), 1600, 1000)
    disco_px = q.metros_em_px(1000.0, -23.55)
    barra_px = 1000.0 / q.metros_de_chao_por_px()
    assert abs(disco_px - barra_px) / disco_px < 0.005


def test_residual_mostra_o_total_das_regioes_aprovadas():
    paginas = _paginas(_pdf())
    residual = next(p for p in paginas if p.startswith("Residual Fitness"))
    assert "Nas regiões aprovadas" in residual and "município inteiro" in residual


def test_saldo_de_empresas_traz_abertas_e_fechadas_embaixo_quando_o_artefato_tem():
    from motor_expansao.dashboard import relatorio_praca as rp

    linha = {"cres_tendencia": "estavel", "cres_saldo_empresas": 1308738,
             "cres_dims": "Empresas:110.0:/mil:99:2020–2025",
             "cres_aberturas_empresas": 2380294, "cres_fechamentos_empresas": 1071556}
    c = rp.resumir_crescimento(linha, uf="SP")
    assert c.subtitulos == {"Saldo de empresas 2020-2025": "2.380.294 abertas - 1.071.556 fechadas"}
    # Artefato antigo, sem as duas colunas: so' o saldo, sem subtitulo.
    del linha["cres_aberturas_empresas"], linha["cres_fechamentos_empresas"]
    assert rp.resumir_crescimento(linha, uf="SP").subtitulos == {}


def test_academias_por_hex_somam_o_espaco_do_resumo():
    df = _sample_df()
    df["oferta_efetiva_disponivel"] = [4451.0, 6300.0, 500.0, 2100.0]  # 3 aprovados
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    acad = res["academias_por_hex"]
    assert sum(acad.values()) == res["espaco_para_academias"]  # 12851/2500 = 5,1 -> 5
    assert set(acad) <= set(df["hex_id"][df["oferta_efetiva_disponivel"] >= 2000])
    assert "espaco" in render_mapas_municipio(df, res, basemap=False)


def test_numeros_do_mapa_de_espaco_saem_como_texto_do_pdf_e_nao_no_png(monkeypatch):
    df = _sample_df()
    df["oferta_efetiva_disponivel"] = [4451.0, 6300.0, 500.0, 2100.0]
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    mapas = render_mapas_municipio(df, res, basemap=False)
    pontos = res["espaco_rotulos"]["pontos"]
    assert {t for _x, _y, t in pontos} == {str(n) for n in res["academias_por_hex"].values()}
    pagina = next(p for p in _paginas(gerar_pdf_relatorio_municipal(res, mapas))
                  if p.startswith("Como chegamos ao Espaço"))
    for _x, _y, t in pontos:
        assert t in pagina


def test_regua_da_sintese_e_a_medida_na_producao():
    """A régua da Síntese é a da emenda de 2026-10-29 da DEC-011, medida com
    `scripts/medir_regua_sintese.py` na base da produção de 2026-10-25 (313 cidades com 100 mil+).

    A primeira, de uma base local e sem script, punha 247 das 313 cidades em "Mercado maduro" e 293
    em "Residual abaixo da maioria". Trocar estes números é remedir com o script e registrar na DEC,
    não editar à mão.
    """
    assert rm._SINTESE_PENETRACAO_TERCOS == (33.0, 42.3, 49.8)
    assert rm._SINTESE_RESIDUAL_MIL_TERCOS == (78.0, 90.0, 104.0)


def test_sintese_le_a_penetracao_e_o_residual_da_cidade():
    # Régua da emenda de 2026-10-29 da DEC-011: 33,0 / 42,3 / 49,8% e 78 / 90 / 104 por mil hab.
    assert rm._texto_penetracao_sintese(65.8).startswith("Mercado maduro")  # São Paulo em 25/10
    assert rm._texto_penetracao_sintese(42.3).startswith("Mercado em desenvolvimento")
    assert rm._texto_penetracao_sintese(20.0).startswith("Mercado com espaço")
    assert rm._texto_penetracao_sintese(0.0).startswith("Mercado sem academias")
    assert "(mediana das cidades com 100 mil+ hab.: 42,3%)" in rm._texto_penetracao_sintese(42.3)
    _v, alto = rm._texto_residual_sintese(
        {"residual_total_alunos": 200_000, "pop_total_municipio": 1_000_000, "soma_oferta_amarelos": 150_000})
    assert alto.startswith("Residual acima da maioria das cidades grandes") and "75% dele" in alto
    _v, baixo = rm._texto_residual_sintese({"residual_total_alunos": 60_000, "pop_total_municipio": 1_000_000})
    assert baixo.startswith("Residual abaixo da maioria das cidades grandes")
    _v, meio = rm._texto_residual_sintese({"residual_total_alunos": 90_000, "pop_total_municipio": 1_000_000})
    assert meio.startswith("Residual na faixa típica das cidades grandes")
    assert "(mediana das cidades grandes: 90)" in meio
    # A regua e' a MEDIANA (2026-10-21): "media" no texto contradizia o numero citado.
    assert all("média" not in t for t in (alto, baixo, meio))


def test_top_por_coluna_ordena_pelo_valor_e_desempata():
    import pandas as pd

    from motor_expansao.dashboard import relatorio_praca as rp

    hexes = pd.DataFrame({"hex_id": list("abcdef"), "score_setor_2022_calibrado": [100, 100, 100, 90, 80, None],
                          "oferta_efetiva_disponivel": [0, 500, 9000, 9999, 1, 5]})
    top = rp.top_por_coluna(hexes, rp.COL_SCORE_SOCIO, n=3, desempate=rp.COL_RESIDUAL)
    assert list(top["hex_id"]) == ["c", "b", "a"] and list(top["posicao"]) == [1, 2, 3]
    assert list(rp.top_por_coluna(hexes, rp.COL_RESIDUAL, n=2)["hex_id"]) == ["d", "c"]


def test_onde_crescer_mostra_densidade_e_nao_score_nas_tabelas():
    from tests.unit.test_relatorio_municipal_praca import _df_cidade, _praca, _resultado

    df = _df_cidade(2)
    pagina = next(p for p in _paginas(gerar_pdf_relatorio_municipal(_resultado(df), None, praca=_praca(df)))
                  if p.startswith("Onde crescer"))
    assert "Densidade (hab/km2)" in pagina
    assert "Score socioeconômico" not in pagina.replace("\n", " ")


def test_empate_no_teto_do_score_desempata_por_renda_e_populacao_sem_teto():
    import pandas as pd

    from motor_expansao.dashboard import relatorio_praca as rp

    hexes = pd.DataFrame({
        "hex_id": ["pobre_cheio", "rico_vazio", "rico_cheio"],
        "score_setor_2022_calibrado": [100.0, 100.0, 100.0],
        "renda_per_capita_setor_2022_calibrada": [4_500.0, 9_000.0, 9_000.0],
        rp.COL_POPULACAO: [60_000.0, 5_000.0, 60_000.0],
        "oferta_efetiva_disponivel": [9_000.0, 8_000.0, 0.0],
    })
    top = rp.top_por_coluna(rp.com_socio_sem_teto(hexes), rp.COL_SCORE_SOCIO, desempate=rp.COL_SOCIO_SEM_TETO)
    # Renda e gente maiores primeiro, mesmo com residual 0 -- o residual nao decide esta lista.
    assert list(top["hex_id"]) == ["rico_cheio", "rico_vazio", "pobre_cheio"]


def test_mapa_onde_crescer_duas_listas_nao_pinta_fora_do_quadro():
    from io import BytesIO

    import numpy as np
    from PIL import Image

    from motor_expansao.dashboard import relatorio_praca as rp
    from motor_expansao.dashboard import relatorio_praca_mapas as rpm
    from tests.unit.test_relatorio_municipal_praca import _df_cidade

    hexes = rp.preparar_hexes_da_cidade(_df_cidade(3), None)
    top_r = rp.top_por_coluna(hexes, rp.COL_RESIDUAL, n=2)
    png = rpm.render_onde_crescer_duas_listas(hexes, top_r, rp.top_por_coluna(hexes, rp.COL_SCORE_SOCIO, n=2),
                                              basemap=False)
    arr = np.asarray(Image.open(BytesIO(png)).convert("RGB")).astype(int)
    # Acima e abaixo da caixa do mapa (titulo e rodape) nao pode haver nenhum hexagono pintado.
    fora = np.concatenate([arr[: rpm._MAP_TOP - 2, :, :], arr[rpm._H - 50:, :, :]], axis=0)
    for cor in (rpm._COR_TOP, rpm._COR_TOP_SOCIO):
        assert int((np.abs(fora - np.array(cor)).sum(axis=2) < 30).sum()) == 0


def test_hexagono_nas_duas_listas_sai_cortado_com_as_duas_cores():
    import h3
    from PIL import Image

    from motor_expansao.dashboard import relatorio_praca_mapas as rpm

    h = h3.latlng_to_cell(-23.2, -45.9, 7)
    lat, lng = h3.cell_to_latlng(h)
    quadro = rpm._Quadro(rpm._bounds_de_pontos([lat - 0.02, lat + 0.02], [lng - 0.02, lng + 0.02],
                                               margem=0.02), rpm._W, rpm._H)
    camada = Image.new("RGBA", (rpm._W, rpm._H), (0, 0, 0, 0))
    cx, cy, meia = rpm._desenhar_hex_dividido(camada, quadro, h, rpm._COR_TOP, rpm._COR_TOP_SOCIO)
    assert camada.getpixel((int(cx - meia / 2), int(cy)))[:3] == rpm._COR_TOP
    assert camada.getpixel((int(cx + meia / 2), int(cy)))[:3] == rpm._COR_TOP_SOCIO


def test_sem_tarja_de_pendente_mesmo_com_a_variavel_antiga(monkeypatch):
    """As tarjas de lembrete sairam com a DEC-077 (2026-10-22): as areas que elas marcavam
    (Expansao de Dominio, Bairros por Zona e o card de zonas) deixam o PDF do Brasil ate'
    chegarem os dados do gestor. A variavel antiga nao pode trazer nada de volta."""
    from tests.unit.test_relatorio_municipal_praca import _df_cidade, _praca, _resultado

    df = _df_cidade(2)
    monkeypatch.setenv("MOTOR_RELMUN_TARJAS_PENDENTES", "1")
    texto = " ".join(_paginas(gerar_pdf_relatorio_municipal(_resultado(df), None, praca=_praca(df))))
    assert "PENDENTE" not in texto


def test_tabela_de_aprovados_lista_os_mais_populosos_e_fecha_com_o_total():
    from fpdf import FPDF

    nomes = [f"Bairro {i:03d}" for i in range(168)]
    pop = {n: float(i) for i, n in enumerate(nomes)}  # o 167 e' o mais populoso
    pdf = FPDF(orientation="L", unit="pt", format=(540, 960))
    pdf.add_page()
    rm._tabela_bairros_aprovados(pdf, nomes, 600.0, 90.0, 320.0, 400.0, cor=(0, 0, 0), pop=pop)
    texto = _paginas(bytes(pdf.output()))[0]
    assert "BAIRROS APROVADOS (168)" in texto and "os 60 mais populosos" in texto
    assert "Bairro 167" in texto and "Bairro 000" not in texto
    assert "+ 108 outros" in texto
