"""Unidades da rede no MAPA para quem tem o mapa, sem a Executiva (pedido do Felipe, 11/11/2026).

O seletor UNIDADES do mapa e a ficha da unidade liam `/api/rede/*`, que é da aba `executiva`:
quem só tinha o mapa via o filtro antigo "Faixa M1" e não tirava o relatório de concorrência
das unidades. As rotas `/api/mapa/*` servem o mesmo seletor e o mesmo PDF com SÓ o território
-- nome, cidade, UF, ponto e concorrência --, e nada do financeiro da rede.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

SERVER = Path(__file__).resolve().parents[2] / "web" / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import acesso  # noqa: E402
import app as pilot  # noqa: E402

from tests.unit.test_piloto_web_rede import rede  # noqa: E402,F401  (fixture)
from tests.unit.test_piloto_web_unidades_sem_rede import cadastro_ultra  # noqa: E402,F401  (fixture)

CAMPOS = {"id", "nome", "uf", "cidade", "lat", "lng", "sem_rede"}


def test_a_lista_do_mapa_traz_rede_e_cadastro_so_com_territorio(cadastro_ultra: Path) -> None:  # noqa: F811
    unidades = pilot.mapa_unidades()["unidades"]
    assert unidades, "a lista não pode vir vazia com a base da rede presente"
    assert all(set(u) == CAMPOS for u in unidades)
    da_rede = {u["id"] for u in unidades if not u["sem_rede"]}
    assert da_rede == {u["id"] for u in pilot.rede_carteira()["unidades"]}
    assert {u["nome"] for u in unidades if u["sem_rede"]} == {"Santana", "Vila Guilherme II"}


def test_nada_do_financeiro_da_rede_vaza_pelo_mapa(cadastro_ultra: Path) -> None:  # noqa: F811
    """A trava que justifica a rota própria: aluno, faturamento e franqueado não saem."""
    proibidos = ("faturamento", "metricas", "franqueado", "consultor", "master", "ativos", "pagantes")
    unidade = next(u for u in pilot.mapa_unidades()["unidades"] if not u["sem_rede"])
    ficha = pilot.mapa_unidade(unidade["id"])
    assert set(ficha) == {"unidade", "mapa"}
    texto = repr(pilot.mapa_unidades()) + repr(ficha["unidade"])
    assert not any(p in texto for p in proibidos)


def test_a_ficha_do_mapa_aceita_a_unidade_do_cadastro(cadastro_ultra: Path) -> None:  # noqa: F811
    ficha = pilot.mapa_unidade("cadastro-u2")
    assert ficha["unidade"]["nome"] == "Santana"
    assert ficha["mapa"]["raio_m"] > 0


def test_unidade_desconhecida_da_404(cadastro_ultra: Path) -> None:  # noqa: F811
    for chamada in (
        lambda: pilot.mapa_unidade("nao-existe"),
        lambda: pilot.mapa_unidade("cadastro-nao-existe"),
        lambda: pilot.mapa_unidade_concorrencia_pdf("nao-existe"),
    ):
        with pytest.raises(HTTPException) as erro:
            chamada()
        assert erro.value.status_code == 404


def test_o_pdf_de_concorrencia_sai_pela_porta_do_mapa(cadastro_ultra: Path) -> None:  # noqa: F811
    unidade = next(u for u in pilot.mapa_unidades()["unidades"] if not u["sem_rede"])
    resposta = pilot.mapa_unidade_concorrencia_pdf(unidade["id"])
    assert resposta.media_type == "application/pdf"
    assert resposta.body[:4] == b"%PDF"


def test_o_mapa_basta_e_a_executiva_nao_e_exigida() -> None:
    """Quem tem só o mapa passa; a rede continua só da Executiva."""
    for rota in ("/api/mapa/unidades", "/api/mapa/unidade/x", "/api/mapa/unidade/x/concorrencia.pdf"):
        assert acesso.abas_necessarias(rota) == frozenset({"mapa"})
        assert acesso.superficie_necessaria(rota) == frozenset({"mapa"})
        assert acesso.capacidade_necessaria(rota, "GET") == "territorio.explorar"
    assert acesso.abas_necessarias("/api/rede/carteira") == frozenset({"executiva"})
    assert acesso.capacidade_necessaria("/api/rede/carteira", "GET") == "rede.ver"
