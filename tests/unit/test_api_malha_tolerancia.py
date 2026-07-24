"""Tolerancia de "encoste" na malha municipal (`service._MalhaMunicipal.resolver`).

Regressao de producao (relato de Felipe 2026-07-24): coordenadas legitimas de PE eram
rejeitadas com "fora do Brasil". A causa nao era o bounding box (`coord.validar_brasil`,
que aceita Recife folgado), e sim o ponto-em-poligono ESTRITO (`predicate="within"`) contra
a malha IBGE, que e um recorte de TERRA — um ponto na agua a poucas centenas de metros da
praia (orla de Janga/Paulista-PE) nao esta DENTRO de poligono nenhum.

Testes puros: geometrias sinteticas, sem depender da malha IBGE real nem de rede.
"""

from __future__ import annotations

import pytest
from shapely import STRtree
from shapely.geometry import box

from motor_expansao.api.service import _TOLERANCIA_MALHA_GRAUS, _MalhaMunicipal

# "Municipio" quadrado de 1 grau cuja borda LESTE fica em lng=-35.0 (faz as vezes de costa).
_COSTA = box(-36.0, -8.5, -35.0, -7.5)
# Vizinho colado a oeste, para o caso de fresta entre poligonos.
_VIZINHO = box(-37.0, -8.5, -36.0, -7.5)


def _malha() -> _MalhaMunicipal:
    geoms = [_COSTA, _VIZINHO]
    meta = [("PE", "2610707"), ("PE", "2600054")]
    return _MalhaMunicipal(STRtree(geoms), meta, geoms)


def test_ponto_dentro_resolve_pelo_caminho_exato() -> None:
    """Caminho `within` continua valendo e tem prioridade (sem regressao)."""
    assert _malha().resolver(-8.0, -35.5) == ("PE", "2610707")
    assert _malha().resolver(-8.0, -36.5) == ("PE", "2600054")


@pytest.mark.parametrize("graus_fora", [0.001, 0.005, 0.017])
def test_ponto_na_agua_dentro_da_tolerancia_encosta_no_municipio(graus_fora: float) -> None:
    """O CASO DO BUG: ponto a leste da costa (na agua) — nenhum poligono o contem, mas
    ele esta a menos de ~2 km da borda -> resolve no municipio costeiro em vez de None."""
    resolvido = _malha().resolver(-8.0, -35.0 + graus_fora)
    assert resolvido == ("PE", "2610707")


def test_ponto_alem_da_tolerancia_continua_rejeitado() -> None:
    """A tolerancia nao pode virar "aceita qualquer coisa": mar aberto segue None, para o
    400 continuar protegendo contra coordenada realmente fora."""
    assert _malha().resolver(-8.0, -35.0 + _TOLERANCIA_MALHA_GRAUS * 2) is None
    assert _malha().resolver(48.8566, 2.3522) is None  # Paris


def test_tolerancia_cobre_o_circunraio_de_um_hex_res7() -> None:
    """A tolerancia precisa cobrir o pior deslocamento ponto->centroide de um hex res-7
    (~1,5 km), que e a origem pratica do defeito quando o relatorio parte de um hex."""
    km_por_grau = 110.0
    assert _TOLERANCIA_MALHA_GRAUS * km_por_grau >= 1.5
    # ...sem chegar perto de "pular" para um municipio do outro lado de uma baia (~5 km).
    assert _TOLERANCIA_MALHA_GRAUS * km_por_grau <= 5.0


def test_encoste_escolhe_o_municipio_MAIS_PROXIMO() -> None:
    """Na fresta entre dois poligonos, o encoste tem de cair no mais proximo — nao no
    primeiro da arvore."""
    malha = _malha()
    # Levemente a leste da divisa (lng=-36.0) -> lado do COSTA.
    assert malha.resolver(-8.0, -35.999) == ("PE", "2610707")
    # Levemente a oeste -> lado do VIZINHO.
    assert malha.resolver(-8.0, -36.001) == ("PE", "2600054")
