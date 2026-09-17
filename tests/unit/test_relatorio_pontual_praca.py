"""Leitura da praca: funcoes puras de `dashboard/relatorio_praca.py` e as paginas do Relatorio Pontual.

No pontual entram DUAS paginas (pressao sobre o ponto e como a cidade esta indo, com o hexagono
do ponto), so' quando o chamador passa `praca=` (o piloto web). Sem `praca`, o PDF da API/bot fica
igual. As quatro paginas da cidade ficam no Relatorio Municipal (`test_relatorio_municipal_praca.py`).
"""

from __future__ import annotations

import inspect
from io import BytesIO

import pandas as pd
from PIL import Image

from motor_expansao.dashboard import relatorio_praca as rp
from motor_expansao.dashboard.censo_report import (
    MAP_LAYER_TITLES,
    PDF_SECTION_HEADERS,
    gerar_pdf_relatorio_pontual_classico,
)
from motor_expansao.dashboard.relatorio_praca import (
    TEXTO_SEM_CRESCIMENTO,
    TITULO_COMO_A_CIDADE_ESTA_INDO,
    TITULO_MAPAS_CALOR_CIDADE,
    TITULO_ONDE_CRESCER,
    TITULO_PRESSAO_CONCORRENCIAL,
    PracaDoPonto,
    crescimento_do_hexagono,
    pressao_sobre_ponto,
    quebras_por_quantil,
    resumir_crescimento,
    selecionar_onde_crescer,
    texto_pdf,
)
from motor_expansao.pipelines.pressao_concorrencial_1km import RAIO_INFLUENCIA_M

_LAT, _LNG = -8.0476, -34.8770  # Recife
_RESULT = {"lat": _LAT, "lng": _LNG, "nome_municipio": "RECIFE", "uf": "PE", "raio_km": 1.0}
_CHAVES_NOVAS = ("pressao_raios",)


def _hexes(linhas: list[tuple[str, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        linhas, columns=["hex_id", "oferta_efetiva_disponivel", "renda_domiciliar", "indice_praca"]
    )


# --------------------------------------------------------------------------- #
# Onde crescer                                                                #
# --------------------------------------------------------------------------- #
def test_top5_nao_e_residual_puro():
    df = _hexes(
        [
            # o MAIOR residual da cidade, com renda abaixo da mediana: nao pode entrar
            ("h_pobre_lotado", 20_000.0, 1_500.0, 95.0),
            ("h_a", 3_000.0, 9_000.0, 80.0),
            ("h_b", 2_500.0, 8_000.0, 90.0),
            ("h_c", 1_000.0, 7_000.0, 70.0),
            # empate de indice: desempata pela renda maior
            ("h_d", 900.0, 6_500.0, 60.0),
            ("h_e", 800.0, 6_800.0, 60.0),
            ("h_sem_residual", 0.0, 9_500.0, 99.0),
            ("h_w", 100.0, 1_400.0, 10.0),
            ("h_x", 100.0, 1_000.0, 10.0),
            ("h_y", 100.0, 1_200.0, 10.0),
            ("h_z", 100.0, 1_300.0, 10.0),
        ]
    )
    sel = selecionar_onde_crescer(df)
    ids = sel.hexagonos["hex_id"].tolist()
    assert "h_pobre_lotado" not in ids
    assert "h_sem_residual" not in ids
    assert ids == ["h_b", "h_a", "h_c", "h_e", "h_d"]
    assert sel.hexagonos["posicao"].tolist() == [1, 2, 3, 4, 5]
    assert sel.mediana_renda == 6_500.0
    assert sel.aviso is None


def test_top5_com_menos_de_5_elegiveis_explica():
    df = _hexes(
        [
            ("h_1", 3_000.0, 9_000.0, 80.0),
            ("h_2", 2_000.0, 8_500.0, 70.0),
            ("h_3", 5_000.0, 1_000.0, 90.0),
            ("h_4", 5_000.0, 1_100.0, 90.0),
        ]
    )
    sel = selecionar_onde_crescer(df)
    assert sel.hexagonos["hex_id"].tolist() == ["h_1", "h_2"]
    assert sel.n_elegiveis == 2
    assert sel.aviso is not None and "2" in sel.aviso


def test_top5_avisa_quando_a_renda_e_do_municipio_inteiro():
    # Enriquecido anterior a DEC-045/054/055: a mesma renda municipal em todo hexagono (Recife
    # local, 11/06: R$ 7.207 nos 36). O filtro nao discrimina e o PDF tem de dizer isso.
    df = _hexes([(f"h{i}", 1_000.0 + i, 7_207.0, float(i)) for i in range(8)])
    sel = selecionar_onde_crescer(df)
    assert len(sel.hexagonos) == 5
    assert sel.aviso == rp.TEXTO_RENDA_MUNICIPAL

    granular = _hexes([(f"h{i}", 1_000.0, 5_000.0 + 100 * i, float(i)) for i in range(8)])
    assert selecionar_onde_crescer(granular).aviso != rp.TEXTO_RENDA_MUNICIPAL
    assert not rp.renda_e_municipal(granular)
    por_origem = granular.assign(renda_origem="renda_per_capita")
    assert rp.renda_e_municipal(por_origem)


def test_top5_sem_colunas_devolve_vazio_com_aviso():
    sel = selecionar_onde_crescer(pd.DataFrame({"hex_id": ["a"]}))
    assert sel.hexagonos.empty
    assert sel.aviso


# --------------------------------------------------------------------------- #
# Pressao                                                                     #
# --------------------------------------------------------------------------- #
def test_sobreposicao_usa_raio_oficial():
    # O raio NAO e' redigitado: e' o do modelo de mercado (DEC-051), importado.
    fonte = inspect.getsource(rp)
    assert "RAIO_INFLUENCIA_M" in fonte
    assert "1000" not in fonte.replace("_", "") and "1_000" not in fonte
    assert rp.pressao_sobre_ponto.__kwdefaults__["raio_m"] == RAIO_INFLUENCIA_M

    grau_lat_m = 111_195.0
    conc = pd.DataFrame(
        {
            "rede": ["Smart Fit", "Smart Fit", None],
            # a 500 m, a 900 m e a 1.500 m ao norte
            "lat": [_LAT + 500 / grau_lat_m, _LAT + 900 / grau_lat_m, _LAT + 1500 / grau_lat_m],
            "lng": [_LNG, _LNG, _LNG],
        }
    )
    ultra = pd.DataFrame({"lat": [_LAT - 300 / grau_lat_m], "lng": [_LNG]})
    p = pressao_sobre_ponto(_LAT, _LNG, conc, ultra)
    assert p.raio_m == RAIO_INFLUENCIA_M
    assert p.n_concorrentes_sobre_ponto == 2
    assert p.n_ultra_sobre_ponto == 1
    assert p.n_raios_sobre_ponto == 3
    assert p.redes_sobre_ponto == [("Smart Fit", 2)]
    assert p.n_independentes_sobre_ponto == 0
    assert abs(p.dist_mais_proxima_m - 500.0) < 5.0
    assert p.nome_mais_proxima == "Smart Fit"


def test_pressao_sem_concorrente():
    p = pressao_sobre_ponto(_LAT, _LNG, None, None)
    assert p.n_raios_sobre_ponto == 0
    assert p.dist_mais_proxima_m is None


# --------------------------------------------------------------------------- #
# Crescimento e textos                                                        #
# --------------------------------------------------------------------------- #
def test_cidade_sem_crescimento_mostra_aviso():
    c = resumir_crescimento(None)
    assert not c.disponivel
    assert c.frase == TEXTO_SEM_CRESCIMENTO

    pdf = gerar_pdf_relatorio_pontual_classico(_RESULT, None, praca=_praca(crescimento=c))
    assert TITULO_COMO_A_CIDADE_ESTA_INDO.encode("latin-1") in pdf
    assert TEXTO_SEM_CRESCIMENTO.encode("latin-1") in pdf


def test_crescimento_monta_linhas_e_troca_travessao():
    c = resumir_crescimento(
        {
            "cres_tendencia": "Em alta",
            "cres_emp_pct": 4.23,
            "cres_uf_mediana": 2.0,
            "cres_saldo_empresas": 1234,
            "cres_salario": 2100.4,
            "cres_salario_var": 3.1,
            "cres_confiab": "alta",
            "v_frase": "Cidade em expansao — vale olhar.",
        },
        uf="PE",
    )
    assert c.disponivel
    rotulos = dict(c.linhas)
    assert rotulos["Variação do emprego desde dez/2022"] == "+4,2% (mediana PE: +2,0%)"
    assert rotulos["Saldo de empresas abertas"] == "1.234"
    assert "—" not in c.frase and " - " in c.frase


def test_quebras_por_quantil_ignoram_zero():
    assert quebras_por_quantil([0, 0, 0, 0, 0, 0, 10, 20, 30, 40, 50]) == [10.0, 20.0, 30.0, 40.0, 50.0]
    assert quebras_por_quantil([0, None]) == []


# --------------------------------------------------------------------------- #
# PDF                                                                         #
# --------------------------------------------------------------------------- #
def _png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (400, 300), (0, 167, 157)).save(buf, format="PNG")
    return buf.getvalue()


def _praca(**kw) -> PracaDoPonto:
    base = dict(
        municipio="Recife",
        uf="PE",
        pressao=pressao_sobre_ponto(_LAT, _LNG, None, None),
        crescimento=resumir_crescimento({"cres_tendencia": "Em alta", "v_frase": "Cidade em alta."}),
        crescimento_hex=crescimento_do_hexagono({"cres_hex_taxa": 42.0, "cres_hex_classe": "Em alta"}),
        mapas={k: _png() for k in _CHAVES_NOVAS},
    )
    base.update(kw)
    return PracaDoPonto(**base)


def test_pdf_tem_so_as_duas_paginas_do_ponto():
    chaves = {k for k, _ in MAP_LAYER_TITLES}
    assert set(_CHAVES_NOVAS) <= chaves
    # mapas da cidade e onde crescer sao do municipal: a tupla do pontual nao os conhece
    assert not {"calor_cidade_renda_domiciliar", "calor_cidade_densidade", "onde_crescer"} & chaves

    pdf = gerar_pdf_relatorio_pontual_classico(_RESULT, None, praca=_praca())
    for titulo in (TITULO_PRESSAO_CONCORRENCIAL, TITULO_COMO_A_CIDADE_ESTA_INDO):
        assert titulo.encode("latin-1") in pdf, titulo
    for titulo in (TITULO_MAPAS_CALOR_CIDADE, TITULO_ONDE_CRESCER):
        assert titulo.encode("latin-1") not in pdf, titulo
    assert b"/Count 9" in pdf  # 7 de base + 2 da praca


def test_pdf_mostra_o_hexagono_do_ponto_ao_lado_da_cidade():
    pdf = gerar_pdf_relatorio_pontual_classico(_RESULT, None, praca=_praca())
    assert "No hexágono do ponto".encode("latin-1") in pdf
    assert "Na cidade".encode("latin-1") in pdf
    assert b"+42,0%" in pdf and b"Em alta" in pdf

    sem = _praca(crescimento_hex=crescimento_do_hexagono(None))
    pdf = gerar_pdf_relatorio_pontual_classico(_RESULT, None, praca=sem)
    assert rp.TEXTO_SEM_CRESCIMENTO_HEX.split(".")[0].encode("latin-1") in pdf


def test_crescimento_do_hexagono_compara_com_a_cidade():
    cidade = pd.DataFrame({"cres_hex_taxa": [10.0, 20.0, 30.0, None]})
    h = crescimento_do_hexagono({"cres_hex_taxa": 42.04, "cres_hex_classe": "Estavel"}, cidade)
    assert h.disponivel
    assert h.taxa_texto == "+42,0%"
    assert h.classe == "Estável"  # rotulo acentuado; o valor bruto segue sem acento
    assert h.mediana_cidade_texto == "+20,0%"
    assert "acima da mediana da cidade" in h.frase

    abaixo = crescimento_do_hexagono({"cres_hex_taxa": -3.0, "cres_hex_classe": "Sem obra nova"}, cidade)
    assert abaixo.taxa_texto == "-3,0%" and "abaixo" in abaixo.frase

    # hexagono quase vazio em 2016: nao imprime o outlier cru
    outlier = crescimento_do_hexagono({"cres_hex_taxa": 498_128.7})
    assert outlier.taxa_texto == "acima de +500%"
    assert outlier.mediana_cidade_texto is None and outlier.frase.endswith("2023.")

    fora = crescimento_do_hexagono({"cres_hex_taxa": None})
    assert not fora.disponivel and fora.frase == rp.TEXTO_SEM_CRESCIMENTO_HEX


def test_pdf_pressao_nomeia_a_rede_pelo_rotulo():
    grau_lat_m = 111_195.0
    conc = pd.DataFrame({"rede": ["smart_fit"], "lat": [_LAT + 300 / grau_lat_m], "lng": [_LNG]})
    pdf = gerar_pdf_relatorio_pontual_classico(
        _RESULT, None, praca=_praca(pressao=pressao_sobre_ponto(_LAT, _LNG, conc, None))
    )
    # parenteses saem escapados no stream do PDF; o que importa e' o rotulo no lugar do slug
    assert b"Smart Fit" in pdf and b"smart_fit" not in pdf


def test_pdf_sem_praca_nao_muda():
    pdf = gerar_pdf_relatorio_pontual_classico(_RESULT, None)
    assert b"/Count 7" in pdf
    assert TITULO_PRESSAO_CONCORRENCIAL.encode("latin-1") not in pdf
    # paginas condicionais nao entram na tupla canonica
    assert TITULO_PRESSAO_CONCORRENCIAL not in PDF_SECTION_HEADERS


def test_textos_novos_cabem_em_latin1():
    for nome, valor in vars(rp).items():
        if nome.startswith(("TITULO_", "TEXTO_")):
            valor.encode("latin-1")
    assert texto_pdf("a — b … “c” → ©") == 'a - b ... "c" -> (c)'
    sel = selecionar_onde_crescer(_hexes([("h", 1.0, 1.0, 1.0)]))
    assert sel.aviso is not None
    sel.aviso.encode("latin-1")


def test_mapas_da_praca_renderizam_offline():
    import h3

    from motor_expansao.dashboard import relatorio_praca_mapas as rpm

    centro = h3.latlng_to_cell(_LAT, _LNG, 7)
    celulas = sorted(h3.grid_disk(centro, 2))
    hexes = pd.DataFrame(
        {"hex_id": celulas, "renda_domiciliar": [1_000.0 * (i + 1) for i in range(len(celulas))]}
    )
    png = rpm.render_calor_cidade(
        hexes, "renda_domiciliar", lat=_LAT, lng=_LNG, titulo="Renda", legenda_titulo="R$",
        formatar=lambda v: f"{v:.0f}", paleta=rpm.PALETA_RENDA, basemap=False,
    )
    assert png and Image.open(BytesIO(png)).size == (1400, 1000)
    assert rpm.render_calor_cidade(hexes.assign(renda_domiciliar=0.0), "renda_domiciliar", lat=_LAT, lng=_LNG,
                                   titulo="x", legenda_titulo="x", formatar=str, paleta=rpm.PALETA_RENDA,
                                   basemap=False) is None

    conc = pd.DataFrame({"rede": ["smart_fit", None], "lat": [_LAT + 0.004, _LAT - 0.004], "lng": [_LNG, _LNG]})
    assert rpm.render_pressao_raios(_LAT, _LNG, conc, None, basemap=False)

    top = hexes.head(5).assign(posicao=range(1, 6))
    assert rpm.render_onde_crescer(hexes, top, lat=_LAT, lng=_LNG, basemap=False)
    assert rpm.render_onde_crescer(hexes, top.iloc[0:0], lat=_LAT, lng=_LNG, basemap=False) is None


def test_onde_crescer_pinta_os_numerados_de_verde_na_escala_da_cidade():
    """Na escala de uma capital (~700 hexagonos res-7) cada hexagono tem poucos pixels: o selo
    do numero em cima do centro o cobria inteiro e a pagina saia toda cinza. O hexagono
    escolhido precisa aparecer em verde em volta do proprio centro, e a cidade continuar
    translucida (senao parece area sem dado)."""
    import h3
    import numpy as np

    from motor_expansao.dashboard import relatorio_praca_mapas as rpm

    centro = h3.latlng_to_cell(_LAT, _LNG, 7)
    celulas = sorted(h3.grid_disk(centro, 15))
    hexes = pd.DataFrame({"hex_id": celulas})
    escolhidos = [h3.grid_ring(centro, 12)[i] for i in (0, 12, 24, 36, 48)]
    top = pd.DataFrame({"hex_id": escolhidos, "posicao": range(1, 6)})

    png = rpm.render_onde_crescer(hexes, top, lat=_LAT, lng=_LNG, basemap=False)
    arr = np.asarray(Image.open(BytesIO(png)).convert("RGB")).astype(int)
    verde = np.all(arr == rpm._COR_TOP, axis=-1)
    assert rpm._COR_TOP[1] > rpm._COR_TOP[0] + 60 and rpm._COR_TOP[1] > rpm._COR_TOP[2] + 40

    quadro = rpm._quadro_da_cidade(hexes, _LAT, _LNG)
    for h in escolhidos:
        lat_c, lng_c = h3.cell_to_latlng(h)
        cx, cy = (int(round(v)) for v in quadro.lnglat(lng_c, lat_c))
        janela = verde[cy - 25 : cy + 26, cx - 25 : cx + 26]
        assert janela.sum() >= 150, f"{h}: so {janela.sum()} px verdes em volta do centro"

    # hexagono comum da cidade (longe do pino e dos escolhidos): translucido, o fundo aparece
    lat_c, lng_c = h3.cell_to_latlng(h3.grid_ring(centro, 6)[0])
    cx, cy = (int(round(v)) for v in quadro.lnglat(lng_c, lat_c))
    assert arr[cy, cx].min() >= 200, f"cidade opaca demais: {arr[cy, cx]}"


def test_calor_da_cidade_usa_as_cores_do_slide_mapas_de_calor():
    """As duas imagens da cidade seguem a paleta do slide "Mapas de calor" (faixas da cidade,
    cores do slide): a faixa mais alta sai na cor da ultima faixa do slide."""
    import h3
    import numpy as np

    from motor_expansao.dashboard import relatorio_praca_mapas as rpm
    from motor_expansao.dashboard.constants import DENSIDADE_POP_BANDS, RENDA_MEDIA_DOMICILIAR_BANDS

    centro = h3.latlng_to_cell(_LAT, _LNG, 7)
    celulas = sorted(h3.grid_disk(centro, 4))
    # o hexagono do valor maximo fica longe do pino
    alvo = h3.grid_ring(centro, 4)[0]
    valores = [100.0 * (i + 1) for i in range(len(celulas))]
    valores[celulas.index(alvo)] = 1e9
    hexes = pd.DataFrame({"hex_id": celulas, "v": valores})
    lat_c, lng_c = h3.cell_to_latlng(alvo)

    for paleta, bandas in ((rpm.PALETA_RENDA, RENDA_MEDIA_DOMICILIAR_BANDS), (rpm.PALETA_DENSIDADE, DENSIDADE_POP_BANDS)):
        assert [tuple(c) for c in paleta] == [tuple(b[2][:3]) for b in bandas]
        png = rpm.render_calor_cidade(hexes, "v", lat=_LAT, lng=_LNG, titulo="x", legenda_titulo="x",
                                      formatar=str, paleta=paleta, basemap=False)
        arr = np.asarray(Image.open(BytesIO(png)).convert("RGB")).astype(int)
        quadro = rpm._quadro_da_cidade(hexes, _LAT, _LNG)
        cx, cy = (int(round(v)) for v in quadro.lnglat(lng_c, lat_c))
        assert tuple(arr[cy, cx]) == tuple(bandas[-1][2][:3])


def test_pressao_cola_a_logo_de_cada_academia():
    """Cada academia leva a logo (quadrado de 30 px da rede; marcador de 20 px da independente),
    e nao so' o ponto colorido de 12 px."""
    from unittest import mock

    from motor_expansao.dashboard import relatorio_praca_mapas as rpm

    conc = pd.DataFrame({"rede": ["smart_fit", None], "lat": [_LAT + 0.004, _LAT - 0.004], "lng": [_LNG, _LNG]})
    ultra = pd.DataFrame({"lat": [_LAT], "lng": [_LNG + 0.004]})
    with mock.patch.object(rpm, "_paste_logo_pin", wraps=rpm._paste_logo_pin) as colar:
        assert rpm.render_pressao_raios(_LAT, _LNG, conc, ultra, basemap=False)
    chaves = sorted(c.args[3] for c in colar.call_args_list)
    assert chaves == ["", "__ultra__", "smart_fit"]


# --------------------------------------------------------------------------- #
# Enquadramento do slide "Socioeconomia e Residual Fitness"                   #
# --------------------------------------------------------------------------- #
def test_enquadramento_do_slide_hero_se_ajusta_a_regiao():
    """Capital (vizinhanca inteira povoada) aproxima; hexagonos povoados espalhados abrem o
    quadro; sem a coluna de populacao fica nos 5 km de antes. Sempre dentro de [min, max].
    Criterio e' POPULACAO, nao score: o score existe em hexagono rural tambem."""
    import h3

    from motor_expansao.dashboard import censo_map as cm

    centro = h3.latlng_to_cell(_LAT, _LNG, 7)
    disco = sorted(h3.grid_disk(centro, 7))

    def _base(povoados) -> pd.DataFrame:
        pop = [5_000.0 if h in povoados else 200.0 for h in disco]
        # score em TODOS, como na base real: nao pode decidir o enquadramento
        return pd.DataFrame({"hex_id": disco, "pop_total_setor_2022": pop, "score_setor_2022_calibrado": 40.0})

    r_denso = cm.raio_enquadramento_hex_km(_LAT, _LNG, _base(set(disco)))
    assert cm.RAIO_HERO_MIN_KM <= r_denso < cm.RAIO_RESIDUAL_DISPLAY_KM

    espalhados = {centro, *list(h3.grid_ring(centro, 5))[::5]}
    r_espalhado = cm.raio_enquadramento_hex_km(_LAT, _LNG, _base(espalhados))
    assert r_denso < r_espalhado <= cm.RAIO_HERO_MAX_KM

    assert cm.raio_enquadramento_hex_km(_LAT, _LNG, _base(set())) == cm.RAIO_HERO_MAX_KM
    assert cm.raio_enquadramento_hex_km(_LAT, _LNG, _base({centro})) == cm.RAIO_HERO_MIN_KM

    sem_pop = _base(set(disco)).drop(columns=["pop_total_setor_2022"])
    assert cm.raio_enquadramento_hex_km(_LAT, _LNG, sem_pop) == cm.RAIO_RESIDUAL_DISPLAY_KM
    assert cm.raio_enquadramento_hex_km(_LAT, _LNG, None) == cm.RAIO_RESIDUAL_DISPLAY_KM


def test_os_dois_mapas_do_slide_hero_usam_o_mesmo_enquadramento(monkeypatch):
    from motor_expansao.dashboard import censo_map as cm
    from motor_expansao.dashboard import censo_report

    raios: list[tuple[str, float]] = []

    def _camada(*_a, **k):
        raios.append((k.get("value_col", "oferta_efetiva_disponivel"), k["raio_exibicao_km"]))

    monkeypatch.setattr(cm, "raio_enquadramento_hex_km", lambda *a, **k: 3.7)
    monkeypatch.setattr(cm, "_render_camada_residual_hex", _camada)
    cm.render_mapas_censitarios_combinados(
        _LAT, _LNG, pd.DataFrame(columns=["geometry"]), basemap=False, hexes_df=pd.DataFrame({"hex_id": ["x"]})
    )
    assert raios == [("score_setor_2022_calibrado", 3.7), ("oferta_efetiva_disponivel", 3.7)]
    # imagens maiores no slide: deixaram de ser reduzidas
    assert censo_report._HERO_MAP_SCALE == 1.0
