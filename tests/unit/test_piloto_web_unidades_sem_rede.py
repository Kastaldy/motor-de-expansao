"""Unidades do cadastro das Ultra SEM dado na Growth na busca do Mapa (pedido do Juan, 14/10).

A busca listava só a base da Growth, e unidade que ainda não opera (em contrato, em
pré-venda: Santana) não aparecia. Nenhuma base diz o status, então o rótulo é neutro e a
ficha é só de território. Barra Funda (lista de exclusão da rede) e ICN ficam de fora.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

SERVER = Path(__file__).resolve().parents[2] / "web" / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import app as pilot  # noqa: E402

from tests.unit.test_piloto_web_rede import _limpar_caches, rede  # noqa: E402,F401  (fixture)


@pytest.fixture
def cadastro_ultra(rede: Path, monkeypatch: pytest.MonkeyPatch) -> Path:  # noqa: F811
    """O cadastro das Ultra com uma unidade da rede e quatro que a Growth não tem."""
    caminho = rede / "staging" / "unidades_ultra_mapeadas.parquet"
    pd.DataFrame(
        [
            ("u1", "Botafogo / RJ", "RJ", "Rio de Janeiro", -22.9519, -43.1840),  # está na Growth
            ("u2", "Santana", "SP", "São Paulo", -23.485085, -46.617685),  # em contrato
            ("u3", "Barra Funda / SP", "SP", "São Paulo", -23.5262, -46.6669),  # excluída da rede
            ("u4", "ICN - Taboão", "SP", "Taboão da Serra", -23.6100, -46.7800),  # não é unidade
            ("u5", "Vila Guilherme II", "SP", "São Paulo", -23.503368, -46.603510),
        ],
        columns=["ultra_id", "unidade", "uf", "cidade", "lat", "lng"],
    ).assign(flag_coord_valida=True).to_parquet(caminho)
    monkeypatch.setattr(pilot, "ULTRA_MAPEADAS_PARQUET", caminho)
    _limpar_caches()
    return caminho


def test_busca_lista_as_unidades_do_cadastro_que_a_growth_nao_tem(cadastro_ultra: Path) -> None:
    unidades = pilot.rede_unidades_sem_rede()["unidades"]
    nomes = [u["nome"] for u in unidades]
    assert nomes == ["Santana", "Vila Guilherme II"]
    santana = unidades[0]
    assert santana["id"] == "cadastro-u2" and santana["uf"] == "SP" and santana["cidade"] == "São Paulo"
    assert santana["lat"] == pytest.approx(-23.485085) and santana["lng"] == pytest.approx(-46.617685)


def test_unidade_da_growth_barra_funda_e_icn_ficam_fora(cadastro_ultra: Path) -> None:
    nomes = {u["nome"] for u in pilot.rede_unidades_sem_rede()["unidades"]}
    assert "Botafogo / RJ" not in nomes  # já sai pela carteira, com a ficha completa
    assert "Barra Funda / SP" not in nomes  # EXCLUIDAS_NOME_CRU
    assert not any(n.upper().startswith("ICN") for n in nomes)  # pedido do Juan


def test_carteira_e_contagens_da_rede_nao_mudam(cadastro_ultra: Path) -> None:
    """A unidade sem dado na rede não entra em conta nenhuma da Visão Executiva."""
    ids = {u["id"] for u in pilot.rede_carteira()["unidades"]}
    assert not any(i.startswith("cadastro-") for i in ids)


def test_ficha_da_unidade_sem_rede_traz_so_territorio(cadastro_ultra: Path) -> None:
    ficha = pilot.rede_unidade_sem_rede("cadastro-u2")
    assert set(ficha) == {"unidade", "mapa"}
    assert ficha["unidade"]["nome"] == "Santana"
    assert ficha["mapa"]["lat"] == pytest.approx(-23.485085) and ficha["mapa"]["raio_m"] > 0


def test_ficha_e_pdf_de_unidade_fora_do_cadastro_dao_404(cadastro_ultra: Path) -> None:
    from fastapi import HTTPException

    for chamada in (
        lambda: pilot.rede_unidade_sem_rede("cadastro-nao-existe"),
        lambda: pilot.rede_unidade_sem_rede("cadastro-u3"),  # Barra Funda
        lambda: pilot.rede_unidade_concorrencia_pdf("cadastro-nao-existe"),
    ):
        with pytest.raises(HTTPException) as erro:
            chamada()
        assert erro.value.status_code == 404


def test_pdf_de_concorrencia_sai_para_a_unidade_sem_rede(cadastro_ultra: Path) -> None:
    resposta = pilot.rede_unidade_concorrencia_pdf("cadastro-u2")
    assert resposta.body.startswith(b"%PDF")


def test_sem_cadastro_a_lista_vem_vazia(rede: Path) -> None:  # noqa: F811
    assert pilot.rede_unidades_sem_rede() == {"unidades": []}


def test_rotas_novas_registradas_e_atras_da_aba_executiva() -> None:
    import acesso

    registradas = {getattr(r, "path", None) for r in pilot.app.routes}
    for rota in ("/api/rede/unidades-sem-rede", "/api/rede/unidade-sem-rede/{unidade_id}"):
        assert rota in registradas
        assert any(
            rota.startswith(prefixo) and abas == frozenset({"executiva"})
            for prefixo, abas in acesso.REGRAS_DE_ACESSO
        )
