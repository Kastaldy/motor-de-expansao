"""O Relatorio Pontual na DIVISA do municipio (relato de Juan, 2026-09-17).

Defeito medido no ponto `-23.60487996805847, -46.57001648894437` (Sao Caetano do Sul, a
**77 m** da divisa com Sao Paulo): `_resolver_e_carregar` resolvia o municipio do PONTO e
carregava **uma unica particao** de `setores_censitarios_2022_geo/`. O raio de 1,0 km, porem,
caia **53% em Sao Caetano e 47% em Sao Paulo** — e os 51 setores do lado paulistano
(~20.079 habitantes, 65% da populacao do raio) simplesmente nao existiam no `setores_df`.

O sintoma VISIVEL era o mapa cortado em linha reta na divisa, mas o dano e' maior: os
Big Numbers (populacao, densidade, renda) saiam calculados sobre meia vizinhanca, e o
gate de zona morta da DEC-042 (`pop < 5.000`) lia essa metade.

Testes puros: geometrias sinteticas e particoes de mentira em `tmp_path`, sem malha IBGE
real, sem base geo materializada e sem rede.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest
from shapely.geometry import box

# --- geografia sintetica -----------------------------------------------------------
# Dois municipios colados, com a divisa em lng = -46.570 (o mesmo desenho do caso real:
# Sao Caetano a oeste, Sao Paulo a leste). Cada "municipio" tem ~0,09 grau (~10 km) de
# lado, folgado para o ponto do miolo ficar longe de qualquer borda.
_DIVISA_LNG = -46.570
_A = box(_DIVISA_LNG - 0.09, -23.65, _DIVISA_LNG, -23.56)  # municipio do PONTO
_B = box(_DIVISA_LNG, -23.65, _DIVISA_LNG + 0.09, -23.56)  # vizinho, colado a leste

_COD_A = "3548807"  # Sao Caetano do Sul
_COD_B = "3550308"  # Sao Paulo

# Ponto a ~70 m a OESTE da divisa: dentro de A, com o raio de 1 km atravessando para B.
_LAT_DIVISA, _LNG_DIVISA = -23.60488, _DIVISA_LNG - 0.0007
# Ponto no MIOLO de A (~7 km da divisa): nenhuma particao vizinha deve ser lida.
_LAT_MIOLO, _LNG_MIOLO = -23.60488, _DIVISA_LNG - 0.065


def _escrever_malha(ibge_dir, features_por_uf: dict[str, list[tuple[str, object]]]) -> None:
    """Escreve `municipios_<UF>.geojson` no formato que `_carregar_malha` le."""
    ibge_dir.mkdir(parents=True, exist_ok=True)
    for uf, features in features_por_uf.items():
        (ibge_dir / f"municipios_{uf}.geojson").write_text(
            json.dumps(
                {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {"codarea": cod},
                            "geometry": geom.__geo_interface__,
                        }
                        for cod, geom in features
                    ],
                }
            ),
            encoding="utf-8",
        )


def _escrever_particao(
    censo_dir,
    uf: str,
    cod_municipio: str,
    nome_municipio: str,
    *,
    lng_base: float,
    n_setores: int = 3,
    nome_distrito: str = "Centro",
) -> None:
    """Grava `uf=XX/cod_municipio=NNNNNNN/part-000.parquet` com setores minimos."""
    from shapely import wkb

    linhas = []
    for i in range(n_setores):
        geom = box(lng_base + i * 0.002, -23.606, lng_base + (i + 1) * 0.002, -23.604)
        minx, miny, maxx, maxy = geom.bounds
        linhas.append(
            {
                "cod_setor": f"{cod_municipio}{i:08d}",
                "uf": uf,
                "cod_municipio": cod_municipio,
                "nome_municipio": nome_municipio,
                "nome_distrito": nome_distrito,
                "geometry_wkb": wkb.dumps(geom),
                "bbox_minx": minx,
                "bbox_miny": miny,
                "bbox_maxx": maxx,
                "bbox_maxy": maxy,
                "pop_total_setor_2022": 1000.0,
                "domicilios_particulares_ocupados_setor_2022": 300.0,
                "renda_responsavel_media_setor_2022": 2500.0,
            }
        )
    destino = censo_dir / f"uf={uf}" / f"cod_municipio={cod_municipio}"
    destino.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(linhas).to_parquet(destino / "part-000.parquet", index=False)


@pytest.fixture
def ambiente(tmp_path):
    """Malha + particoes dos dois municipios colados, com o cache da malha limpo."""
    from motor_expansao.api import service
    from motor_expansao.api.settings import Settings

    ibge_dir = tmp_path / "ibge"
    censo_dir = tmp_path / "geo"
    _escrever_malha(ibge_dir, {"SP": [(_COD_A, _A), (_COD_B, _B)]})
    # Setores de A imediatamente a OESTE da divisa; os de B, a LESTE.
    _escrever_particao(censo_dir, "SP", _COD_A, "Sao Caetano do Sul", lng_base=_DIVISA_LNG - 0.006)
    _escrever_particao(censo_dir, "SP", _COD_B, "Sao Paulo", lng_base=_DIVISA_LNG)

    service._carregar_malha.cache_clear()
    try:
        yield Settings(ibge_dir=ibge_dir, censo_geo_dir=censo_dir), censo_dir
    finally:
        service._carregar_malha.cache_clear()


def _codigos(setores_df) -> set[str]:
    return {str(v) for v in setores_df["cod_municipio"].dropna().unique()}


# --- 1. o caso do bug --------------------------------------------------------------


def test_ponto_na_divisa_enxerga_os_setores_do_municipio_VIZINHO(ambiente) -> None:
    """O CASO DO BUG: a 70 m da divisa, o raio atravessa — os setores dos DOIS lados entram."""
    from motor_expansao.api.service import _resolver_e_carregar

    settings, _ = ambiente
    uf, cod_municipio, setores_df = _resolver_e_carregar(_LAT_DIVISA, _LNG_DIVISA, settings)

    # A identidade do PONTO nao muda: ele continua sendo de Sao Caetano.
    assert (uf, cod_municipio) == ("SP", _COD_A)
    # ...mas a vizinhanca analisada deixa de parar na divisa.
    assert _codigos(setores_df) == {_COD_A, _COD_B}


def test_rotulo_do_municipio_continua_sendo_o_do_PONTO(ambiente) -> None:
    """`_nome_municipio_de` alimenta o painel de perfil: com dois municipios no frame, o
    rotulo tem de seguir o do ponto — nao o primeiro que a concatenacao trouxer."""
    from motor_expansao.api.service import _nome_municipio_de, _resolver_e_carregar

    settings, _ = ambiente
    _uf, _cod, setores_df = _resolver_e_carregar(_LAT_DIVISA, _LNG_DIVISA, settings)
    assert _nome_municipio_de(setores_df) == "Sao Caetano do Sul"


# --- 2. o que NAO pode mudar -------------------------------------------------------


def test_ponto_no_MIOLO_nao_le_particao_nenhuma_a_mais(ambiente, monkeypatch) -> None:
    """A esmagadora maioria dos pontos esta longe de divisa: la o resultado tem de ser
    identico ao de hoje, e nenhuma particao extra pode ser lida (custo de I/O)."""
    from motor_expansao.api.service import _resolver_e_carregar
    from motor_expansao.dashboard import data as dashboard_data

    lidas: list[tuple[str, str | None]] = []
    original = dashboard_data.read_censo_geo_partition

    def espiao(base_dir, uf, cod_municipio=None):
        lidas.append((uf, cod_municipio))
        return original(base_dir, uf, cod_municipio)

    monkeypatch.setattr(dashboard_data, "read_censo_geo_partition", espiao)

    settings, _ = ambiente
    _uf, cod_municipio, setores_df = _resolver_e_carregar(_LAT_MIOLO, _LNG_MIOLO, settings)

    assert cod_municipio == _COD_A
    assert _codigos(setores_df) == {_COD_A}
    assert lidas == [("SP", _COD_A)]


def test_municipio_do_ponto_sem_particao_continua_404(ambiente) -> None:
    """A ausencia que IMPORTA (a do proprio ponto) segue virando 404 `base_geo_ausente` —
    a vizinhanca nova nao pode 'salvar' um ponto sem censo proprio e mascarar o erro."""
    import shutil

    from motor_expansao.api.service import APIError, _resolver_e_carregar

    settings, censo_dir = ambiente
    shutil.rmtree(censo_dir / "uf=SP" / f"cod_municipio={_COD_A}")

    with pytest.raises(APIError) as erro:
        _resolver_e_carregar(_LAT_DIVISA, _LNG_DIVISA, settings)
    assert erro.value.status_code == 404
    assert erro.value.codigo == "base_geo_ausente"


def test_particao_do_VIZINHO_ausente_nao_levanta(ambiente) -> None:
    """Cobertura parcial e' estado normal (o artefato nao tem todos os municipios): o
    vizinho sem particao sai do conjunto em silencio, com o que existir."""
    import shutil

    from motor_expansao.api.service import _resolver_e_carregar

    settings, censo_dir = ambiente
    shutil.rmtree(censo_dir / "uf=SP" / f"cod_municipio={_COD_B}")

    _uf, cod_municipio, setores_df = _resolver_e_carregar(_LAT_DIVISA, _LNG_DIVISA, settings)
    assert cod_municipio == _COD_A
    assert _codigos(setores_df) == {_COD_A}


# --- 3. divisa entre ESTADOS -------------------------------------------------------


def test_divisa_INTERESTADUAL_tambem_funde(tmp_path) -> None:
    """A malha e' indexada por UF, mas a divisa nao sabe disso: ponto na fronteira SP/MG
    tem de enxergar os setores da outra UF (o caso de Extrema/Divinolandia e afins)."""
    from motor_expansao.api import service
    from motor_expansao.api.settings import Settings

    ibge_dir = tmp_path / "ibge"
    censo_dir = tmp_path / "geo"
    _escrever_malha(ibge_dir, {"SP": [(_COD_A, _A)], "MG": [("3125101", _B)]})
    _escrever_particao(censo_dir, "SP", _COD_A, "Municipio SP", lng_base=_DIVISA_LNG - 0.006)
    _escrever_particao(censo_dir, "MG", "3125101", "Municipio MG", lng_base=_DIVISA_LNG)

    settings = Settings(ibge_dir=ibge_dir, censo_geo_dir=censo_dir)
    service._carregar_malha.cache_clear()
    try:
        uf, cod_municipio, setores_df = service._resolver_e_carregar(
            _LAT_DIVISA, _LNG_DIVISA, settings
        )
    finally:
        service._carregar_malha.cache_clear()

    assert (uf, cod_municipio) == ("SP", _COD_A)
    assert _codigos(setores_df) == {_COD_A, "3125101"}
    assert set(setores_df["uf"].astype(str)) == {"SP", "MG"}


# --- 4. o efeito colateral do merge: nome de distrito COLIDE entre municipios -------


def test_perfil_do_distrito_nao_absorve_o_CENTRO_do_vizinho(ambiente) -> None:
    """`agregar_perfil_bairro_distrito` cai para `nome_distrito` quando nao ha `cod_bairro`,
    e casa por NOME. Com dois municipios no mesmo `setores_df`, o "Centro" do vizinho
    entraria no perfil do bairro do ponto — o agregado e' da unidade administrativa que
    CONTEM o ponto (D2), entao o municipio tem de entrar na chave."""
    from motor_expansao.api.service import _resolver_e_carregar
    from motor_expansao.dashboard.censo_point import agregar_perfil_bairro_distrito

    settings, _ = ambiente
    _uf, cod_municipio, setores_df = _resolver_e_carregar(_LAT_DIVISA, _LNG_DIVISA, settings)

    perfil = agregar_perfil_bairro_distrito(
        setores_df,
        nome_distrito="Centro",
        nome_municipio="Sao Caetano do Sul",
        uf="SP",
        cod_municipio=cod_municipio,
    )
    # 3 setores do municipio do ponto — nao os 6 dos dois municipios juntos.
    assert perfil["n_setores_unidade"] == 3
