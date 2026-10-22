"""`GET /api/municipio-do-ponto`: coordenada -> (UF, municipio) no nome do seletor.

Defeito de 21/10/2026 (Vinicius): escolher uma unidade Ultra levava o mapa a "Todos os
municipios" na primeira tentativa -- a carteira trazia `cidade` vazia e, de dentro de outra
cidade, o hexagono da unidade nao estava no payload aberto. A rota resolve o municipio pela
COORDENADA, contra a mesma malha municipal do `/api/ponto`, e devolve o nome na grafia de
`/api/municipios/{uf}` (a lista do seletor).

Hermetico: malha, artefato enriquecido e censo sao fabricados em `tmp_path`. Um caso extra
usa a malha REAL do repositorio quando ela esta' materializada.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi import HTTPException

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import acesso  # noqa: E402
import app as pilot  # noqa: E402

ROTA = "/api/municipio-do-ponto"


def _quadrado(lng0: float, lat0: float, lng1: float, lat1: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[[lng0, lat0], [lng1, lat0], [lng1, lat1], [lng0, lat1], [lng0, lat0]]],
    }


def _geojson(pasta: Path, uf: str, feats: list[tuple[str, dict]]) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    corpo = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"codarea": cod}, "geometry": g} for cod, g in feats
        ],
    }
    (pasta / f"municipios_{uf}.geojson").write_text(json.dumps(corpo), encoding="utf-8")


# Dois municipios vizinhos em SP e um em GO, quadrados de 0,1 grau.
SP_CAPITAL = ("3550308", _quadrado(-46.70, -23.60, -46.60, -23.50))
SBC = ("3548708", _quadrado(-46.70, -23.70, -46.60, -23.60))
GO_ALG = ("5200258", _quadrado(-48.40, -15.80, -48.30, -15.70))
DENTRO_SP = (-23.55, -46.65)
DENTRO_SBC = (-23.65, -46.65)
DENTRO_GO = (-15.75, -48.35)


@pytest.fixture()
def dados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ibge = tmp_path / "ibge"
    _geojson(ibge, "SP", [SP_CAPITAL, SBC])
    _geojson(ibge, "GO", [GO_ALG])

    enriquecido = tmp_path / "enriquecido"
    (enriquecido / "uf=SP").mkdir(parents=True)
    # SBC sem codigo no artefato (o M1 ja' deixou cod nulo em UFs inteiras): o nome vem do
    # censo e casa pelo nome normalizado.
    pd.DataFrame(
        {
            "hex_id": ["a", "b", "c"],
            "cod_municipio": pd.Series(["3550308", "3550308", None], dtype="string"),
            "nome_municipio": pd.Series(
                ["São Paulo", "São Paulo", "São Bernardo do Campo"], dtype="category"
            ),
        }
    ).to_parquet(enriquecido / "uf=SP" / "part-0.parquet")

    censo = tmp_path / "censo"
    for uf, cod, nome in (
        ("SP", "3548708", "SAO BERNARDO DO CAMPO"),
        ("GO", "5200258", "Águas Lindas de Goiás"),
    ):
        pasta = censo / f"uf={uf}" / f"cod_municipio={cod}"
        pasta.mkdir(parents=True)
        pd.DataFrame({"nome_municipio": [nome]}).to_parquet(pasta / "part-000.parquet")

    monkeypatch.setattr(pilot, "IBGE_DIR", ibge)
    monkeypatch.setattr(pilot, "ENRICHED_DIR", enriquecido)
    monkeypatch.setattr(pilot, "CENSO_GEO_DIR", censo)
    pilot._nomes_m1_da_uf.cache_clear()
    yield tmp_path
    pilot._nomes_m1_da_uf.cache_clear()


# --------------------------------------------------------------------------- #
# Resolucao                                                                    #
# --------------------------------------------------------------------------- #
def test_ponto_conhecido_devolve_o_municipio_na_grafia_do_seletor(dados: Path) -> None:
    corpo = pilot.municipio_do_ponto(*DENTRO_SP)
    assert corpo == {
        "uf": "SP",
        "municipio": "São Paulo",
        "cod_municipio": "3550308",
        "no_seletor": True,
    }
    # e' o mesmo nome que a lista do seletor (`/api/municipios/{uf}`) escreve
    nomes = pilot._nomes_m1_da_uf("SP")[1].values()
    assert corpo["municipio"] in nomes


def test_sem_codigo_no_artefato_o_nome_do_censo_casa_pelo_nome_normalizado(dados: Path) -> None:
    corpo = pilot.municipio_do_ponto(*DENTRO_SBC)
    assert corpo["municipio"] == "São Bernardo do Campo"  # a grafia do SELETOR, nao a do censo
    assert corpo["cod_municipio"] == "3548708"
    assert corpo["no_seletor"] is True


def test_uf_sem_artefato_devolve_o_nome_do_censo_e_avisa(dados: Path) -> None:
    """A coordenada manda na UF: aqui GO, mesmo que o cadastro dissesse DF."""
    corpo = pilot.municipio_do_ponto(*DENTRO_GO)
    assert corpo == {
        "uf": "GO",
        "municipio": "Águas Lindas de Goiás",
        "cod_municipio": "5200258",
        "no_seletor": False,
    }


def test_sem_nome_nenhum_devolve_uf_e_codigo(dados: Path) -> None:
    for arq in (dados / "censo" / "uf=GO").rglob("*.parquet"):
        arq.unlink()
    corpo = pilot.municipio_do_ponto(*DENTRO_GO)
    assert corpo["uf"] == "GO" and corpo["cod_municipio"] == "5200258"
    assert corpo["municipio"] is None and corpo["no_seletor"] is False


def test_fora_do_bounding_box_do_pais_e_400(dados: Path) -> None:
    with pytest.raises(HTTPException) as exc:
        pilot.municipio_do_ponto(38.7223, -9.1393)  # Lisboa
    assert exc.value.status_code == 400


def test_dentro_do_pais_e_fora_da_malha_e_404(dados: Path) -> None:
    with pytest.raises(HTTPException) as exc:
        pilot.municipio_do_ponto(-10.0, -50.0)  # nenhum quadrado a menos de 2 km
    assert exc.value.status_code == 404
    assert "município" in exc.value.detail  # texto de usuario acentuado


def test_nao_le_o_artefato_m1_inteiro(dados: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Rota LEVE: nunca a particao inteira de `carregar_uf` (dezenas de segundos numa UF fria)."""

    def _proibido(*_a, **_k):
        raise AssertionError("municipio-do-ponto nao pode chamar carregar_uf")

    monkeypatch.setattr(pilot, "carregar_uf", _proibido)
    assert pilot.municipio_do_ponto(*DENTRO_SP)["municipio"] == "São Paulo"


_MALHA_REAL = (pilot.PERFIL.raiz / "ibge").glob("municipios_SP.geojson")


@pytest.mark.skipif(not any(_MALHA_REAL), reason="malha municipal real nao materializada")
def test_malha_real_resolve_a_avenida_paulista() -> None:
    pilot._nomes_m1_da_uf.cache_clear()
    corpo = pilot.municipio_do_ponto(-23.5613, -46.6565)
    assert (corpo["uf"], corpo["cod_municipio"]) == ("SP", "3550308")


# --------------------------------------------------------------------------- #
# Gate de acesso (os tres portoes + os espelhos da trilha)                     #
# --------------------------------------------------------------------------- #
def test_rota_registrada_no_app() -> None:
    assert ROTA in {getattr(r, "path", "") for r in pilot.app.routes}


def test_gate_de_aba_e_o_mesmo_da_lista_de_municipios() -> None:
    assert acesso.abas_necessarias(ROTA) == acesso.abas_necessarias("/api/municipios/SP")
    assert acesso.abas_necessarias(ROTA) == frozenset({"mapa", "oportunidades"})


def test_quem_nao_ve_o_mapa_leva_403_e_quem_ve_passa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mapa = tmp_path / "acesso_abas.json"
    mapa.write_text(json.dumps({"ana": ["executiva"], "bia": ["mapa"]}), encoding="utf-8")
    monkeypatch.setenv("MOTOR_ACESSO_ABAS_PATH", str(mapa))
    acesso._cache = None
    try:
        assert acesso.motivo_bloqueio(ROTA, "ana") is not None
        assert acesso.motivo_bloqueio(ROTA, "bia") is None
    finally:
        acesso._cache = None


def test_capacidade_do_banco_e_a_da_exploracao_do_territorio() -> None:
    assert acesso.capacidade_necessaria(ROTA, "GET") == "territorio.explorar"
    assert acesso.capacidade_necessaria(ROTA, "GET") == acesso.capacidade_necessaria(
        "/api/municipios/SP", "GET"
    )


def test_gate_de_pais_exige_a_malha_municipal() -> None:
    assert acesso.rota_exige_malha_municipal(ROTA)
    assert acesso.motivo_bloqueio_pais(ROTA, pilot.PERFIL) is None
    sem_malha = dataclasses.replace(pilot.PERFIL, malha_municipal_disponivel=False)
    assert "malha municipal" in (acesso.motivo_bloqueio_pais(ROTA, sem_malha) or "")


def test_prefixo_nao_captura_as_rotas_vizinhas() -> None:
    """Sem barra, o prefixo novo nao pode engolir `/api/municipio/` nem `/api/municipios/`."""
    assert (
        acesso.capacidade_necessaria("/api/municipio/SP/Campinas", "GET") == "territorio.explorar"
    )
    assert not acesso.rota_exige_malha_municipal("/api/municipio/SP/Campinas")
    assert not acesso.rota_exige_malha_municipal("/api/municipios/SP")
