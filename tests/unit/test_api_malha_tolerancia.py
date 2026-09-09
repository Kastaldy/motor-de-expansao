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


# ---------------------------------------------------------------------------
# As mensagens de erro seguem o PERFIL da instancia (2026-09-03)
#
# Ate' aqui as duas mensagens cravavam "IBGE" e "Brasil" — verdade so' para uma
# instancia. A Argentina nao materializa `ibge/municipios_*.geojson` ainda (o
# Relatorio Pontual dela e' trabalho futuro), e o operador via um erro que citava o
# instituto e o pais de OUTRO deploy.
# ---------------------------------------------------------------------------


def test_malha_vazia_nomeia_a_fonte_de_censo_do_PERFIL(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from motor_expansao.api import service
    from motor_expansao.perfil import PERFIL_BR_EMBARCADO, carregar_perfil

    perfil_ar = carregar_perfil(PERFIL_BR_EMBARCADO.parents[1] / "AR" / "perfil.json")
    monkeypatch.setattr(service, "_PERFIL", perfil_ar)
    service._carregar_malha.cache_clear()
    try:
        with pytest.raises(service.APIError) as erro:
            service._carregar_malha(str(tmp_path))  # diretorio vazio: nenhum geojson
        assert "INDEC" in str(erro.value)
        assert "IBGE" not in str(erro.value)
    finally:
        service._carregar_malha.cache_clear()


def test_coordenada_fora_da_malha_nomeia_pais_e_fonte_do_PERFIL(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_resolver_e_carregar` (o ramo 400 REAL, nao uma reimplementacao no teste).

    O import de `dashboard.data` (cadeia que puxa h3) so' acontece DEPOIS deste ramo —
    por isso o teste chega ate' aqui mesmo sem a base geo/censo materializada.
    """
    from motor_expansao.api import service
    from motor_expansao.api.settings import Settings
    from motor_expansao.perfil import PERFIL_BR_EMBARCADO, carregar_perfil

    geojson_dir = tmp_path / "ibge"
    geojson_dir.mkdir()
    (geojson_dir / "municipios_PE.geojson").write_text(
        '{"type": "FeatureCollection", "features": [{"type": "Feature", '
        '"properties": {"codarea": "2610707"}, "geometry": {"type": "Polygon", '
        '"coordinates": [[[-36.0, -8.5], [-35.0, -8.5], [-35.0, -7.5], '
        '[-36.0, -7.5], [-36.0, -8.5]]]}}]}',
        encoding="utf-8",
    )
    settings = Settings(ibge_dir=geojson_dir)

    perfil_ar = carregar_perfil(PERFIL_BR_EMBARCADO.parents[1] / "AR" / "perfil.json")
    monkeypatch.setattr(service, "_PERFIL", perfil_ar)
    service._carregar_malha.cache_clear()
    try:
        with pytest.raises(service.APIError) as erro:
            service._resolver_e_carregar(48.8566, 2.3522, settings)  # Paris: bem longe
        assert erro.value.status_code == 400
        assert "INDEC" in str(erro.value)
        assert "Argentina" in str(erro.value)
        assert "IBGE" not in str(erro.value)
        assert "Brasil" not in str(erro.value)
    finally:
        service._carregar_malha.cache_clear()
