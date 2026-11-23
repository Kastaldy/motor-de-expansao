"""Relatorio Pontual, Brasil (pedido de 2026-11-23): a independente sem o disco de 750 m.

Na pagina "Pressao concorrencial" do pontual, a academia independente fica so' com a logo do
Wellhub (o marcador do agregador), sem o disco ambar. Rede e Ultra seguem com o disco. E' o
mesmo pedido que o Relatorio Municipal BR ja' atende desde o #548 (`raio_independente=False`).

So' DESENHO: a independente segue nas contagens do painel ("Raios sobre o ponto", "Redes sobre o
ponto"), e a nota diz isso. O criterio "e' Brasil" e' o mesmo do municipal e da leitura sem
veredito do pontual: a instancia com a regua da recomendacao (`leitura=True`). A Argentina, sem
regua, sai como antes.
"""

from __future__ import annotations

import pandas as pd
import pytest

from motor_expansao.dashboard import praca_do_ponto
from motor_expansao.dashboard import relatorio_praca_mapas as rpm
from motor_expansao.dashboard.censo_report import gerar_pdf_relatorio_pontual_classico
from motor_expansao.dashboard.relatorio_praca import TITULO_PRESSAO_CONCORRENCIAL
from tests.unit.test_relatorio_municipal import _paginas_do_pdf
from tests.unit.test_relatorio_municipal_praca import _elipses
from tests.unit.test_relatorio_pontual_praca import _LAT, _LNG, _RESULT, _praca

# Uma rede, duas independentes (sem `rede`) e uma Ultra, todas a ~330 m do ponto.
_CONC = pd.DataFrame(
    {"rede": ["smart_fit", None, None], "lat": [_LAT, _LAT + 0.003, _LAT - 0.003], "lng": [_LNG + 0.003, _LNG, _LNG]}
)
_ULTRA = pd.DataFrame({"lat": [_LAT + 0.002], "lng": [_LNG - 0.002]})


def _espiar_desenho(monkeypatch: pytest.MonkeyPatch) -> tuple[list, list[str], list[str], list[str]]:
    """(elipses, chaves das logos coladas, itens da legenda, subtitulos) de um render."""
    chamadas = _elipses(monkeypatch)
    marcas: list[str] = []
    real_pin = rpm._paste_logo_pin
    monkeypatch.setattr(
        rpm, "_paste_logo_pin", lambda img, x, y, chave, **k: (marcas.append(chave), real_pin(img, x, y, chave, **k))[1]
    )
    itens: list[str] = []
    real_legenda = rpm._legenda
    monkeypatch.setattr(
        rpm, "_legenda", lambda d, t, it, **k: (itens.extend(r for r, _ in it), real_legenda(d, t, it, **k))[1]
    )
    subtitulos: list[str] = []
    real_base = rpm._base
    monkeypatch.setattr(
        rpm, "_base", lambda q, t, s, **k: (subtitulos.append(s), real_base(q, t, s, **k))[1]
    )
    return chamadas, marcas, itens, subtitulos


def _cores_dos_discos(chamadas: list) -> list[tuple]:
    # O disco de academia e' o unico circulo PREENCHIDO do raio do mapa: o do ponto e o da
    # legenda sao so' contorno. Raio em ponto flutuante: compara com folga de meio px.
    raio_disco = max(r for r, _f, _w in chamadas)
    return [f[:3] for r, f, _w in chamadas if r >= raio_disco - 0.5 and f is not None]


# --------------------------------------------------------------------------- #
# Mapa                                                                        #
# --------------------------------------------------------------------------- #
def test_pressao_do_ponto_sem_raio_da_independente_mantem_a_logo_dela(monkeypatch):
    chamadas, marcas, itens, subtitulos = _espiar_desenho(monkeypatch)

    assert rpm.render_pressao_raios(_LAT, _LNG, _CONC, _ULTRA, basemap=False, raio_independente=False)

    assert _cores_dos_discos(chamadas) == [rpm._COR_CADEIA, rpm._COR_ULTRA]
    # As duas independentes seguem no mapa como marca: chave "" = logo do Wellhub (DEC-066).
    assert marcas.count("") == 2
    assert sorted(set(marcas)) == ["", "__ultra__", "smart_fit"]
    assert "Independente, sem raio" in itens and "Academia independente" not in itens
    assert subtitulos == ["Area de influencia de 750 m por rede e Ultra"]
    # Texto desenhado em PNG so' em ASCII: a fonte embutida do Pillow nao tem glifo acentuado.
    assert all(t.isascii() for t in [*itens, *subtitulos])


def test_pressao_do_ponto_por_default_segue_com_o_raio_da_independente(monkeypatch):
    chamadas, marcas, itens, subtitulos = _espiar_desenho(monkeypatch)

    assert rpm.render_pressao_raios(_LAT, _LNG, _CONC, _ULTRA, basemap=False)

    indep = rpm._COR_INDEPENDENTE
    assert _cores_dos_discos(chamadas) == [rpm._COR_CADEIA, indep, indep, rpm._COR_ULTRA]
    assert marcas.count("") == 2
    assert "Academia independente" in itens and "Independente, sem raio" not in itens
    assert subtitulos == ["Area de influencia de 750 m por academia"]


# --------------------------------------------------------------------------- #
# Montagem: o Brasil (`leitura=True`) pede o mapa sem o raio                  #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(("leitura", "com_raio"), [(True, False), (False, True)])
def test_montagem_do_pontual_tira_o_raio_so_no_brasil(monkeypatch, leitura, com_raio):
    pedidos: list[dict] = []
    monkeypatch.setattr(
        praca_do_ponto.rpm, "render_pressao_raios", lambda *a, **k: (pedidos.append(k), b"png")[1]
    )
    praca = praca_do_ponto.montar_praca_do_ponto(
        _LAT,
        _LNG,
        uf="PE",
        nome_municipio="Recife",
        hexes_cidade=pd.DataFrame({"hex_id": pd.Series([], dtype="string")}),
        linha_crescimento=None,
        carregar_crescimento_hex=lambda: None,
        comp_df=_CONC,
        ultra_df=_ULTRA,
        leitura=leitura,
        rotulo_tendencia={},
        basemap=False,
    )
    assert pedidos and all(k.get("raio_independente", True) is com_raio for k in pedidos)
    assert praca.independente_sem_raio is (not com_raio)
    # So' desenho: a independente segue na contagem do painel nos dois paises.
    assert praca.pressao.n_independentes_sobre_ponto == 2
    assert praca.mapas["pressao_raios"] == b"png"


# --------------------------------------------------------------------------- #
# Nota da pagina                                                              #
# --------------------------------------------------------------------------- #
def _texto_da_pressao(pdf: bytes) -> str:
    paginas = _paginas_do_pdf(pdf)
    achadas = [p for p in paginas if TITULO_PRESSAO_CONCORRENCIAL in p]
    assert len(achadas) == 1
    return " ".join(achadas[0].split())


def test_nota_da_pressao_do_ponto_no_brasil_diz_que_a_independente_segue_na_conta():
    texto = _texto_da_pressao(gerar_pdf_relatorio_pontual_classico(_RESULT, None, praca=_praca(independente_sem_raio=True)))
    assert "em volta de uma rede ou da Ultra" in texto
    assert "As independentes aparecem só com a logo, sem círculo" in texto
    assert "seguem na contagem ao lado" in texto


def test_nota_da_pressao_do_ponto_fora_do_brasil_fica_igual():
    texto = _texto_da_pressao(gerar_pdf_relatorio_pontual_classico(_RESULT, None, praca=_praca()))
    assert "em volta de uma academia, a leitura do relatório" in texto
    assert "independentes aparecem" not in texto
