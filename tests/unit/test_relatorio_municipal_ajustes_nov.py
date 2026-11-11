"""Ajustes do Relatorio Municipal pedidos em 2026-11-10 (Brasil).

Um teste por pedido, todos no BRASIL (`resposta_unica`, DEC-077 / `regra` no servico). A
Argentina, sem regua, sai IDENTICA: cada pedido tem o seu contraponto argentino aqui ou nos
testes de sempre (`test_relatorio_municipal_praca.py`, `..._slides_capa_visao_geral.py`).

1. Mapas de calor com as FAIXAS FIXAS do piloto (nao mais os quintis da cidade).
2. Pressao concorrencial: a independente perde o circulo de 1 km no mapa (segue na conta).
3. "Como a cidade esta indo" antes de "Pressao concorrencial".
4. Onde crescer sem a linha "Vaga vazia".
5. Partes dos Bairros Oficiais nomeadas pela direcao (Norte, Leste...), com observacao.
6. Notas dos mapas de bairros resumidas, uma ideia por linha.
7. Bairros Oficiais sem a reserva do IBGE: setor que o CNEFE nao nomeia fica sem cor.

Pedidos de 2026-11-11 (mesmo PR):
8. "Como chegamos ao Espaco para academias" logo depois de "Pressao concorrencial".
9. Onde crescer: o segmento sem NENHUMA regiao (ou indisponivel) fica sem tabela, e o motivo vai
   para a nota. A tabela com regiao segue so' com as linhas preenchidas (item 4).
"""
from __future__ import annotations

from io import BytesIO

import h3
import numpy as np
import pandas as pd
import pytest
from PIL import Image

from motor_expansao import recomendacao
from motor_expansao.dashboard import relatorio_municipal as rm
from motor_expansao.dashboard import relatorio_praca_mapas as rpm
from motor_expansao.dashboard.constants import DENSIDADE_POP_BANDS, RENDA_MEDIA_DOMICILIAR_BANDS
from motor_expansao.dashboard.relatorio_municipal import (
    CHAVE_RESPOSTA_UNICA,
    agregar_municipio,
    carregar_bairros_geo,
    gerar_pdf_relatorio_municipal,
    render_mapas_municipio,
)
from motor_expansao.dashboard.relatorio_praca import (
    TITULO_COMO_A_CIDADE_ESTA_INDO,
    TITULO_PRESSAO_CONCORRENCIAL,
)
from tests.unit.test_bairro_cnefe import _COD, _UF, _escrever_artefato, ambiente  # noqa: F401
from tests.unit.test_relatorio_municipal import _paginas_do_pdf, _sample_df
from tests.unit.test_relatorio_municipal_praca import (
    _LAT,
    _LNG,
    _df_cidade,
    _elipses,
    _praca,
    _resultado,
)
from tests.unit.test_relatorio_municipal_recomendacao_unica import (
    _ROTULOS,
    _linhas_por_segmento,
    _nota,
    _onde_crescer,
    _praca_br,
    _rec,
    _regra,
)
from tests.unit.test_relatorio_municipal_slides_capa_visao_geral import _grade_de_bairros


def _indice_da_pagina(paginas: list[str], titulo: str) -> int:
    return next(i for i, p in enumerate(paginas) if p.startswith(titulo))


# --------------------------------------------------------------------------- #
# 1. Mapas de calor: faixas fixas do piloto                                    #
# --------------------------------------------------------------------------- #
def _espiar(monkeypatch: pytest.MonkeyPatch, nome: str) -> list[dict]:
    chamadas: list[dict] = []
    real = getattr(rpm, nome)

    def _espia(*a, **k):
        chamadas.append(k)
        return real(*a, **k)

    monkeypatch.setattr(rpm, nome, _espia)
    return chamadas


def test_calor_com_faixas_fixas_pinta_pelo_corte_do_piloto_e_mostra_a_regua_inteira(monkeypatch):
    centro = h3.latlng_to_cell(_LAT, _LNG, 7)
    celulas = sorted(h3.grid_disk(centro, 2))
    # Um hexagono em cada faixa da renda domiciliar (2.000 / 4.000 / 8.000 / 14.000), o resto sem
    # valor: com quintis, cinco valores dariam cinco cores quaisquer; com a regua, a cor do corte.
    alvo = dict(zip(celulas[::4], [1_500.0, 3_000.0, 6_000.0, 10_000.0, 20_000.0], strict=False))
    hexes = pd.DataFrame({"hex_id": celulas, "v": [alvo.get(c, float("nan")) for c in celulas]})

    itens: list[str] = []
    textos: list[str] = []
    real_legenda, real_texto = rpm._legenda, rpm._draw_text
    monkeypatch.setattr(rpm, "_legenda", lambda d, t, it, **k: (itens.extend(r for r, _ in it), real_legenda(d, t, it, **k))[1])
    monkeypatch.setattr(rpm, "_draw_text", lambda d, xy, txt, **k: (textos.append(str(txt)), real_texto(d, xy, txt, **k))[1])

    png = rpm.render_calor_cidade(hexes, "v", titulo="x", legenda_titulo="x",
                                  faixas=RENDA_MEDIA_DOMICILIAR_BANDS, basemap=False)
    assert itens == [b[1] for b in RENDA_MEDIA_DOMICILIAR_BANDS] + ["Sem dado"]
    assert not any("quintis" in t for t in textos)
    assert any("Faixas fixas" in t for t in textos)

    arr = np.asarray(Image.open(BytesIO(png)).convert("RGB")).astype(int)
    quadro = rpm._quadro_da_cidade(hexes, None, None)
    for (hid, _v), banda in zip(alvo.items(), RENDA_MEDIA_DOMICILIAR_BANDS, strict=True):
        lat, lng = h3.cell_to_latlng(hid)
        cx, cy = (int(round(v)) for v in quadro.lnglat(lng, lat))
        assert tuple(arr[cy, cx]) == tuple(banda[2][:3]), hid


def _praca_com_espias(tmp_path, monkeypatch, *, brasil: bool):
    df = _df_cidade(2).assign(cod_municipio="3550308")
    calor = _espiar(monkeypatch, "render_calor_cidade")
    pressao = _espiar(monkeypatch, "render_pressao_cidade")
    if brasil:
        rec = _rec(hexes=list(df["hex_id"]))
        monkeypatch.setattr(recomendacao, "montar_recomendacao", lambda *a, **k: rec)
        _praca_br(tmp_path, df, regra=_regra())
    else:
        _praca_br(tmp_path, df)
    return calor, pressao


def test_no_brasil_a_praca_usa_as_faixas_fixas_e_tira_o_raio_da_independente(tmp_path, monkeypatch):
    calor, pressao = _praca_com_espias(tmp_path, monkeypatch, brasil=True)
    assert calor and all("paleta" not in k for k in calor)
    # Os mapas saem em paralelo: a regua e' conferida pelo titulo, nao pela ordem de chamada.
    regua = {"Renda media domiciliar": RENDA_MEDIA_DOMICILIAR_BANDS, "Densidade demografica": DENSIDADE_POP_BANDS}
    assert all(k["faixas"] is regua[k["titulo"]] for k in calor)
    assert pressao and all(k.get("raio_independente") is False for k in pressao)


def test_na_argentina_a_praca_segue_com_quintis_e_raio_da_independente(tmp_path, monkeypatch):
    calor, pressao = _praca_com_espias(tmp_path, monkeypatch, brasil=False)
    assert calor and all("faixas" not in k and "paleta" in k for k in calor)
    assert pressao and all(k.get("raio_independente", True) is True for k in pressao)


def test_nota_do_calor_no_brasil_fala_de_faixas_fixas_e_nao_de_quintis():
    df = _df_cidade(2)
    br = _paginas_do_pdf(gerar_pdf_relatorio_municipal({**_resultado(df), CHAVE_RESPOSTA_UNICA: True},
                                                       None, praca=_praca(df)))
    calor = " ".join(br[_indice_da_pagina(br, "Mapas de calor da cidade")].split())
    assert "quintis" not in calor
    assert "faixas fixas, as mesmas do piloto" in calor
    ar = _paginas_do_pdf(gerar_pdf_relatorio_municipal(_resultado(df), None, praca=_praca(df)))
    assert "quintis" in " ".join(ar[_indice_da_pagina(ar, "Mapas de calor da cidade")].split())


# --------------------------------------------------------------------------- #
# 2. Pressao: independente sem raio                                            #
# --------------------------------------------------------------------------- #
def test_pressao_da_cidade_sem_raio_da_independente_mantem_a_marca_dela(monkeypatch):
    df = _df_cidade(2)
    conc = pd.DataFrame({"rede": ["smart_fit", None, None],
                         "lat": [_LAT, _LAT + 0.003, _LAT - 0.003], "lng": [_LNG] * 3})
    ultra = pd.DataFrame({"lat": [_LAT + 0.001], "lng": [_LNG + 0.002]})
    chamadas = _elipses(monkeypatch)
    marcas: list[str] = []
    real_pin = rpm._paste_logo_pin
    monkeypatch.setattr(rpm, "_paste_logo_pin", lambda img, x, y, chave, **k: (marcas.append(chave), real_pin(img, x, y, chave, **k))[1])
    itens: list[str] = []
    real_legenda = rpm._legenda
    monkeypatch.setattr(rpm, "_legenda", lambda d, t, it, **k: (itens.extend(r for r, _ in it), real_legenda(d, t, it, **k))[1])

    rpm.render_pressao_cidade(df, conc, ultra, basemap=False, raio_independente=False)

    # Raio em ponto flutuante: cada disco sai da sua posicao, entao compara com folga de meio px.
    raio_disco = max(r for r, _f, _w in chamadas)
    discos = [f[:3] for r, f, _w in chamadas if r >= raio_disco - 0.5 and f is not None]
    assert discos == [rpm._COR_CADEIA, rpm._COR_ULTRA], discos
    assert marcas.count("") == 2  # as duas independentes seguem no mapa, como marca
    assert "Academia independente" not in itens
    assert "Independente, sem raio" in itens


def test_nota_da_pressao_no_brasil_diz_que_a_independente_segue_na_conta():
    df = _df_cidade(2)
    br = _paginas_do_pdf(gerar_pdf_relatorio_municipal({**_resultado(df), CHAVE_RESPOSTA_UNICA: True},
                                                       None, praca=_praca(df)))
    pressao = " ".join(br[_indice_da_pagina(br, TITULO_PRESSAO_CONCORRENCIAL)].split())
    assert "independentes aparecem sem círculo" in pressao
    assert "seguem na conta do residual" in pressao


# --------------------------------------------------------------------------- #
# 3. Ordem: Como a cidade esta indo antes da Pressao                          #
# --------------------------------------------------------------------------- #
def test_no_brasil_como_a_cidade_esta_indo_vem_antes_da_pressao():
    df = _df_cidade(2)
    br = _paginas_do_pdf(gerar_pdf_relatorio_municipal({**_resultado(df), CHAVE_RESPOSTA_UNICA: True},
                                                       None, praca=_praca(df)))
    assert (_indice_da_pagina(br, TITULO_COMO_A_CIDADE_ESTA_INDO) + 1
            == _indice_da_pagina(br, TITULO_PRESSAO_CONCORRENCIAL))
    ar = _paginas_do_pdf(gerar_pdf_relatorio_municipal(_resultado(df), None, praca=_praca(df)))
    assert (_indice_da_pagina(ar, TITULO_PRESSAO_CONCORRENCIAL) + 1
            == _indice_da_pagina(ar, TITULO_COMO_A_CIDADE_ESTA_INDO))


# --------------------------------------------------------------------------- #
# 4. Onde crescer sem "Vaga vazia"                                             #
# --------------------------------------------------------------------------- #
def test_onde_crescer_imprime_so_as_regioes_que_atendem_a_regua():
    onde = _onde_crescer(_praca(_df_cidade(2), recomendacao=_rec(), rotulos_recomendacao=_ROTULOS))
    assert "Vaga vazia" not in onde
    linhas = _linhas_por_segmento(onde)
    assert [linha[0] for linha in linhas["mata_virgem"]] == ["1", "2", "3"]
    assert [linha[0] for linha in linhas["premium"]] == ["1", "2", "3", "4", "5"]
    nota = _nota(onde)
    assert "Vaga vazia" not in nota and "Linha em branco" not in nota
    assert f"Menos de {_regra().vagas_por_segmento} linhas = só essas regiões atendem à régua." in nota


# --------------------------------------------------------------------------- #
# 9. Onde crescer: segmento sem nenhuma regiao fica sem tabela                 #
# --------------------------------------------------------------------------- #
def _y_da_nota(monkeypatch: pytest.MonkeyPatch, rec) -> float:
    """O `y` da nota do "Onde crescer": desce com as linhas preenchidas e sobe quando a tabela sai
    (nao ha linha vazia ocupando lugar)."""
    ys: list[float] = []
    real = rm._draw_note

    def _espia(pdf, x, y, w, texto, *a, **k):
        if texto.startswith("Mata Virgem = "):
            ys.append(y)
        return real(pdf, x, y, w, texto, *a, **k)

    monkeypatch.setattr(rm, "_draw_note", _espia)
    _onde_crescer(_praca(_df_cidade(2), recomendacao=rec, rotulos_recomendacao=_ROTULOS))
    monkeypatch.undo()
    assert len(ys) == 1, ys
    return ys[0]


def test_onde_crescer_ocupa_so_o_lugar_das_linhas_preenchidas(monkeypatch):
    cheia = _y_da_nota(monkeypatch, _rec(n_mata_virgem=5, n_premium=5))
    parcial = _y_da_nota(monkeypatch, _rec(n_mata_virgem=3, n_premium=5))
    so_premium = _y_da_nota(monkeypatch, _rec(n_mata_virgem=0, n_premium=5))
    nenhuma = _y_da_nota(monkeypatch, _rec(n_mata_virgem=0, n_premium=0))
    assert cheia > parcial > so_premium > nenhuma


def test_onde_crescer_cheio_nao_explica_tabela_curta_nem_ausente():
    onde = _onde_crescer(_praca(_df_cidade(2), recomendacao=_rec(n_mata_virgem=5, n_premium=5),
                                rotulos_recomendacao={**_ROTULOS, "mv3": "Vila A", "mv4": "Vila B"}))
    assert "Menos de" not in _nota(onde) and "sem tabela" not in _nota(onde)


def test_onde_crescer_segmento_sem_nenhuma_regiao_fica_sem_tabela():
    onde = _onde_crescer(_praca(_df_cidade(2), recomendacao=_rec(n_mata_virgem=0, n_premium=4),
                                rotulos_recomendacao=_ROTULOS))
    assert "Mata Virgem (ordem" not in onde  # a tabela inteira sai
    linhas = _linhas_por_segmento(onde)
    assert list(linhas) == ["premium"]
    assert [linha[0] for linha in linhas["premium"]] == ["1", "2", "3", "4"]  # sem 5a linha
    nota = _nota(onde)
    assert "Mata Virgem sem tabela: nenhuma região atende à régua neste recorte." in nota
    assert f"Menos de {_regra().vagas_por_segmento} linhas = só essas regiões atendem à régua." in nota


def _aviso(onde: str) -> str:
    """O texto antes da nota, numa linha so' (titulos das tabelas e o aviso sem tabela)."""
    return " ".join(onde[:onde.index("Mata Virgem = ")].split())


def test_onde_crescer_sem_nenhuma_regiao_avisa_que_nao_ha_regiao_viavel():
    """Pedido de 2026-11-11: sem tabela nenhuma, um aviso em destaque no lugar delas."""
    onde = _onde_crescer(_praca(_df_cidade(2), recomendacao=_rec(n_mata_virgem=0, n_premium=0),
                                rotulos_recomendacao=_ROTULOS))
    assert "Vaga vazia" not in onde
    assert _linhas_por_segmento(onde) == {}
    aviso = _aviso(onde)
    assert "SEM REGIÃO VIÁVEL" in aviso
    assert "Nenhuma região de São Paulo tem métricas viáveis para expansão neste recorte." in aviso
    nota = _nota(onde)
    assert "sem tabela" not in nota  # o aviso ja' diz; a nota nao repete
    assert "Menos de" not in nota and "Linha em branco" not in nota


def test_onde_crescer_indisponivel_avisa_a_falta_de_dado_sem_veredito_sobre_a_cidade():
    """Falta de dado nao e' cidade inviavel: o aviso diz "indisponivel" e o motivo, uma vez."""
    onde = _onde_crescer(_praca(_df_cidade(2), recomendacao=_rec(indisponivel=True)))
    motivo = "Renda indisponível: recomendação suspensa até a base ser corrigida"
    assert _linhas_por_segmento(onde) == {}
    aviso = _aviso(onde)
    assert "RECOMENDAÇÃO INDISPONÍVEL" in aviso
    assert f"{motivo}." in aviso
    assert " ".join(onde.split()).count(motivo) == 1  # so' no aviso
    assert "métricas viáveis" not in onde and "SEM REGIÃO VIÁVEL" not in onde
    nota = _nota(onde)
    assert "sem tabela" not in nota
    assert "Menos de" not in nota and "Linha em branco" not in nota


def test_onde_crescer_com_alguma_tabela_nao_mostra_o_aviso():
    onde = _onde_crescer(_praca(_df_cidade(2), recomendacao=_rec(n_mata_virgem=0, n_premium=4),
                                rotulos_recomendacao=_ROTULOS))
    assert "SEM REGIÃO VIÁVEL" not in onde and "RECOMENDAÇÃO INDISPONÍVEL" not in onde


# --------------------------------------------------------------------------- #
# 8. "Como chegamos ao Espaco" logo depois da Pressao                          #
# --------------------------------------------------------------------------- #
_COMO_CHEGAMOS = "Como chegamos ao Espaço para academias"
_RESUMO = "Resumo da Região"


def test_no_brasil_como_chegamos_ao_espaco_vem_logo_depois_da_pressao():
    df = _df_cidade(2)
    br = _paginas_do_pdf(gerar_pdf_relatorio_municipal({**_resultado(df), CHAVE_RESPOSTA_UNICA: True},
                                                       None, praca=_praca(df)))
    assert _indice_da_pagina(br, TITULO_PRESSAO_CONCORRENCIAL) + 1 == _indice_da_pagina(br, _COMO_CHEGAMOS)
    assert _indice_da_pagina(br, _COMO_CHEGAMOS) + 1 == _indice_da_pagina(br, _RESUMO)
    # Argentina: a ordem de sempre, o Resumo e logo depois a conta do espaco.
    ar = _paginas_do_pdf(gerar_pdf_relatorio_municipal(_resultado(df), None, praca=_praca(df)))
    assert _indice_da_pagina(ar, _RESUMO) + 1 == _indice_da_pagina(ar, _COMO_CHEGAMOS)


def test_no_brasil_sem_a_praca_como_chegamos_segue_depois_do_resumo():
    """Sem as paginas da praca nao ha Pressao: a conta do espaco fica onde sempre esteve."""
    df = _df_cidade(2)
    br = _paginas_do_pdf(gerar_pdf_relatorio_municipal({**_resultado(df), CHAVE_RESPOSTA_UNICA: True}, None))
    assert _indice_da_pagina(br, _RESUMO) + 1 == _indice_da_pagina(br, _COMO_CHEGAMOS)


# --------------------------------------------------------------------------- #
# 5-6. Bairros Oficiais: partes por direcao e notas curtas                     #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("ponto", "rumo"),
    [((0.0, 90.0), "Norte"), ((64.0, 64.0), "Nordeste"), ((90.0, 0.0), "Leste"),
     ((64.0, -64.0), "Sudeste"), ((0.0, -90.0), "Sul"), ((-64.0, -64.0), "Sudoeste"),
     ((-90.0, 0.0), "Oeste"), ((-64.0, 64.0), "Noroeste"), ((10.0, 10.0), "Centro")],
)
def test_rumo_da_parte_pela_direcao_do_centro(ponto, rumo):
    # Raio do municipio = 100: a menos de 25 do centro e' "Centro".
    assert rm.rumo_da_parte(ponto, (0.0, 0.0), 100.0) == rumo


def test_um_bairro_muito_longe_nao_faz_a_parte_virar_centro():
    """Previa de 2026-11-10 (Sao Paulo): com o raio = maior distancia, Marsilac (46 km ao sul)
    inflava o "Centro" e a Zona Leste inteira saia "Centro". O raio e' a distancia MEDIANA."""
    def _b(nome, x, y):
        return {"nome": nome, "rotulo_xy": (float(x), float(y)), "pop": 1.0}

    miolo = [_b(f"M{i}", (i % 3) * 100.0, (i // 3) * 100.0) for i in range(9)]
    leste = [_b(f"L{i}", 3_000.0 + i * 50.0, 0.0) for i in range(5)]
    longe = [_b("Rural", 0.0, -40_000.0)]
    parte_de = {b["nome"]: 0 for b in leste}
    rumo = rm._rumos_das_partes(miolo + leste + longe, [[b["nome"] for b in leste]], parte_de, {})
    assert rumo != ["Centro"]


def test_divisao_traz_um_rumo_por_parte():
    div = rm.dividir_bairros_em_partes(_grade_de_bairros(8))
    assert len(div["rumo"]) == len(div["partes"]) > 1
    assert set(div["rumo"]) <= {"Norte", "Nordeste", "Leste", "Sudeste", "Sul", "Sudoeste", "Oeste",
                                "Noroeste", "Centro"}


def _pdf_partes(monkeypatch, *, brasil: bool) -> tuple[list[str], list[list[str]], dict]:
    df = _sample_df()
    # 64 bairros: 40 numerados, em partes; nomes vindos do CNEFE, como no Brasil com o artefato.
    geo = {**_grade_de_bairros(8), "fonte_bairro": "cnefe"}
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", bairros_geo=geo)
    if brasil:
        res[CHAVE_RESPOSTA_UNICA] = True
    notas: list[list[str]] = []
    real = rm._draw_notas
    monkeypatch.setattr(rm, "_draw_notas", lambda pdf, x, y, w, linhas, **k: (notas.append(list(linhas)), real(pdf, x, y, w, linhas, **k))[1])
    mapas = render_mapas_municipio(df, res, basemap=False)
    return _paginas_do_pdf(gerar_pdf_relatorio_municipal(res, mapas)), notas, rm.dividir_bairros_em_partes(geo)


def test_no_brasil_cada_parte_ganha_o_nome_da_direcao_e_o_painel_explica(monkeypatch):
    paginas, _notas, div = _pdf_partes(monkeypatch, brasil=True)
    geral = " ".join(paginas[1].split())
    assert "bairros (nº" not in geral
    for k, rumo in enumerate(div["rumo"]):
        assert f"Parte {k + 1} - {rumo}" in geral
        assert any(f"Parte {k + 1} de {len(div['partes'])} - {rumo}" in p for p in paginas), k
    assert "Como cada parte foi nomeada" in geral


def test_no_brasil_as_notas_dos_bairros_sao_curtas_e_uma_ideia_por_linha(monkeypatch):
    paginas, notas, div = _pdf_partes(monkeypatch, brasil=True)
    k = len(div["partes"])
    assert len(notas) == 1 + k  # visao geral + uma por parte
    for linhas in notas:
        assert 1 <= len(linhas) <= 3
        assert all(len(linha) <= 150 for linha in linhas)
    geral, parte = " ".join(notas[0]), " ".join(notas[1])
    assert f"{k} partes, cada uma com página própria e zoom" in geral
    assert "Numerados os 40 bairros mais populosos de 64" in geral
    assert "O CNEFE não nomeia todos os setores" in geral
    assert "o mini-mapa mostra onde a parte fica" in parte
    texto = " ".join(" ".join(p.split()) for p in paginas)
    for velho in ("para os números caberem", "dissolvidos pelo bairro do Cadastro",
                  "Cada bairro desta parte com o contorno", "camada de display"):
        assert velho not in texto, velho


def test_na_argentina_as_partes_seguem_so_numeradas(monkeypatch):
    paginas, notas, _div = _pdf_partes(monkeypatch, brasil=False)
    geral = " ".join(paginas[1].split())
    assert "bairros (nº" in geral and "Como cada parte foi nomeada" not in geral
    assert notas == []


# --------------------------------------------------------------------------- #
# 7. Sem a reserva do IBGE nos Bairros Oficiais                                #
# --------------------------------------------------------------------------- #
def test_leitura_sem_reserva_deixa_sem_bairro_o_setor_que_o_cnefe_nao_nomeia(ambiente):  # noqa: F811
    settings, raiz = ambiente
    sem_artefato = carregar_bairros_geo(_UF, _COD, settings.censo_geo_dir)
    assert "sem_reserva_ibge" not in sem_artefato  # sem CNEFE a malha e' a fonte, nao a reserva

    _escrever_artefato(raiz)
    com = carregar_bairros_geo(_UF, _COD, settings.censo_geo_dir)
    # A leitura de sempre (que o resto do relatorio usa) continua com a reserva...
    assert {b["nome"] for b in com["bairros"]} == {"Jardim Satélite", "Setor Socioeconômico 14", "Zona rural"}
    # ...e a dos Bairros Oficiais, sem ela: o setor so' do IBGE vai para a sobra, sem cor.
    sem = com["sem_reserva_ibge"]
    nomes = {b["nome"] for b in sem["bairros"] if not b["sobra"]}
    assert nomes == {"Jardim Satélite", "Zona rural"}
    assert any(b["sobra"] for b in sem["bairros"])
    assert sem["n_bairros"] == com["n_bairros"] - 1
    assert sem["cobertura"] < com["cobertura"]
    assert sem["contorno"] == com["contorno"]


def test_bairros_oficiais_do_brasil_leem_a_leitura_sem_reserva(monkeypatch):
    df = _sample_df()
    com_reserva = _grade_de_bairros(2)  # 4 bairros
    sem_reserva = {**_grade_de_bairros(2), "bairros": _grade_de_bairros(2)["bairros"][:3], "n_bairros": 3}
    geo = {**com_reserva, "fonte_bairro": "cnefe", "sem_reserva_ibge": sem_reserva}
    vistos: list[int] = []
    real = rm._render_mapa_bairros
    monkeypatch.setattr(rm, "_render_mapa_bairros", lambda g, **k: (vistos.append(len(g.get("bairros") or [])), real(g, **k))[1])

    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", bairros_geo=geo)
    res[CHAVE_RESPOSTA_UNICA] = True
    render_mapas_municipio(df, res, basemap=False)
    assert vistos[0] == 3

    vistos.clear()
    res_ar = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", bairros_geo=geo)
    render_mapas_municipio(df, res_ar, basemap=False)
    assert vistos[0] == 4
