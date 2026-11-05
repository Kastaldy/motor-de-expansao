"""Emenda 2 da DEC-077 (05/11/2026): no Premium o score censitario >= 50 sai e entra renda
domiciliar >= R$ 5.000 (regua BR 2026-11_v1). A populacao minima de 10.000 e o resto ficam.

A renda e a MESMA do Mata Virgem (a do card). Como 5.000 > 4.500, um Premium nunca prova que
nao e Mata Virgem pela renda: a prova vem do residual abaixo de 2.000 (ou estimado).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.recomendacao import (
    RegraRecomendacaoInvalida,
    carregar_regra,
    classificar,
    limpar_cache,
    recomendar,
)
from motor_expansao.recomendacao import carregador as carregador_mod
from motor_expansao.recomendacao.nucleo import ItemRecomendado, linhas_que_precisam_de_renda
from tests.unit.recomendacao_fixtures import (
    PROCEDENCIA,
    RECORTE_BR,
    REGRA_2026_11,
    hexes,
    linha,
    mv,
    premium,
    regra_teste,
)

_DIR_BR = carregador_mod.DIR_REGRA / "BR"


def _rec(df: pd.DataFrame, regra=REGRA_2026_11):
    return recomendar(df, regra, renda=PROCEDENCIA, recorte=RECORTE_BR)


def _ids(resultado) -> list[str]:
    return [v.hex_id for v in resultado.vagas if isinstance(v, ItemRecomendado)]


# ---------------------------------------------------------------------------
# Nucleo
# ---------------------------------------------------------------------------


def test_premium_entra_pela_renda_e_o_score_nao_decide() -> None:
    df = hexes(
        [
            premium("renda_alta_score_baixo", renda=6000.0, score=10.0),
            premium("renda_baixa_score_alto", renda=4000.0, score=95.0),
            premium("sem_score", renda=7000.0, score=None),
        ]
    )
    assert set(_ids(_rec(df).premium)) == {"renda_alta_score_baixo", "sem_score"}


def test_limite_de_renda_do_premium_e_inclusivo() -> None:
    df = hexes([premium("no_corte", renda=5000.0), premium("abaixo", renda=4999.99)])
    assert _ids(_rec(df).premium) == ["no_corte"]


def test_populacao_minima_do_premium_continua() -> None:
    df = hexes(
        [
            premium("populoso", renda=6000.0, populacao=10000.0),
            premium("pequeno", renda=6000.0, populacao=9999.0),
        ]
    )
    assert _ids(_rec(df).premium) == ["populoso"]


def test_mata_virgem_nunca_vira_premium() -> None:
    """Renda >= 5.000 e residual >= 2.000: e Mata Virgem, nao Premium."""
    df = hexes([mv("mv", renda=8000.0, residual=3000.0, populacao=50000.0)])
    r = _rec(df)
    assert _ids(r.mata_virgem) == ["mv"] and _ids(r.premium) == []


def test_premium_exige_residual_medido() -> None:
    df = hexes([premium("estimado", renda=6000.0, medido=False)])
    assert _ids(_rec(df).premium) == []


def test_ordem_do_premium_segue_a_populacao() -> None:
    df = hexes(
        [
            premium("menor", renda=9000.0, populacao=15000.0),
            premium("maior", renda=5500.0, populacao=40000.0),
        ]
    )
    assert _ids(_rec(df).premium) == ["maior", "menor"]


def test_sem_renda_conta_no_premium_e_sem_score_zera() -> None:
    df = hexes([premium("sem_renda", renda=None), premium("sem_score", renda=6000.0, score=None)])
    sem_dado = dict(_rec(df).premium.sem_dado)
    assert sem_dado["sem_renda"] == 1
    assert sem_dado["sem_score"] == 0


def test_regua_v1_por_score_segue_aplicavel() -> None:
    """Rollback: a 2026-10_v1 (score >= 50) continua decidindo pelo score."""
    df = hexes([premium("score_alto", renda=3000.0, score=70.0)])
    assert _ids(_rec(df, regra=regra_teste()).premium) == ["score_alto"]
    assert _ids(_rec(df).premium) == []


def test_linhas_que_precisam_de_renda_incluem_todo_candidato_do_premium() -> None:
    """Com o criterio de renda, o candidato do Premium com score baixo tambem precisa da renda."""
    df = hexes(
        [
            linha("pop_alta_score_baixo", residual=100.0, populacao=20000.0, score=5.0),
            linha("pop_baixa", residual=100.0, populacao=5000.0, score=5.0),
        ]
    )
    precisa = linhas_que_precisam_de_renda(df, REGRA_2026_11)
    assert list(precisa) == [True, False]


def test_classificar_marca_premium_pela_renda() -> None:
    df = hexes([premium("p", renda=6000.0, score=1.0)])
    out = classificar(df, REGRA_2026_11, renda_disponivel=True)
    assert bool(out["premium_elegivel"].iloc[0])


def test_payload_publica_o_criterio_de_renda() -> None:
    p = _rec(hexes([premium("p", renda=6000.0)])).para_payload()
    assert p["regra"]["premium"]["renda_domiciliar_min"] == 5000.0
    assert p["regra"]["premium"]["score_min"] is None
    assert p["regra"]["premium"]["populacao_min"] == 10000.0
    json.dumps(p)


# ---------------------------------------------------------------------------
# Carregador
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _sem_fixacao(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(carregador_mod.ENV_VERSAO, raising=False)
    limpar_cache()
    yield
    limpar_cache()


def _v2() -> dict:
    return json.loads((_DIR_BR / "2026-11_v1.json").read_text(encoding="utf-8"))


def _gravar(raiz: Path, dados: dict) -> None:
    d = raiz / "BR"
    d.mkdir(parents=True, exist_ok=True)
    (d / "2026-11_v1.json").write_text(json.dumps(dados), encoding="utf-8")
    (d / "VIGENTE").write_text("2026-11_v1\n", encoding="utf-8")


def test_vigente_e_a_2026_11_v1_por_renda() -> None:
    r = carregar_regra("BR")
    assert r is not None and r.versao == "2026-11_v1"
    assert r.premium.renda_domiciliar_min == 5000.0 and r.premium.score_min is None
    assert r.premium.populacao_min == 10000.0
    assert r.mata_virgem.renda_domiciliar_min == 4500.0


def test_premium_com_os_dois_criterios_e_erro(tmp_path: Path) -> None:
    dados = _v2()
    dados["premium"]["score_min"] = 50.0
    _gravar(tmp_path, dados)
    with pytest.raises(RegraRecomendacaoInvalida, match="EXATAMENTE um criterio"):
        carregar_regra("BR", raiz=tmp_path)


def test_premium_sem_criterio_e_erro(tmp_path: Path) -> None:
    dados = _v2()
    del dados["premium"]["renda_domiciliar_min"]
    _gravar(tmp_path, dados)
    with pytest.raises(RegraRecomendacaoInvalida, match="EXATAMENTE um criterio"):
        carregar_regra("BR", raiz=tmp_path)


@pytest.mark.parametrize("valor", [0, -1.0, "5000", True])
def test_renda_do_premium_invalida_nomeia_o_campo(tmp_path: Path, valor: object) -> None:
    dados = copy.deepcopy(_v2())
    dados["premium"]["renda_domiciliar_min"] = valor
    _gravar(tmp_path, dados)
    with pytest.raises(RegraRecomendacaoInvalida, match="premium.renda_domiciliar_min"):
        carregar_regra("BR", raiz=tmp_path)
