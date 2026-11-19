"""Painel dos masters (DEC-089): as regras de status e a meta, com tabelas sintéticas."""

from __future__ import annotations

import re

import pandas as pd

from motor_expansao.masters.meta import fase_de_exibicao, meses_ate, ordem_da_fase
from motor_expansao.masters.painel import (
    OUTRA_ATRIBUICAO,
    cards,
    data_da_unidade,
    indexar_datas,
    painel_do_master,
)

HOJE = pd.Timestamp("2026-11-18")


def chave(valor: object) -> str:
    """Uma chave simples no lugar da `_chave_unidade` do piloto: caixa alta e sem " - UF"."""
    return re.sub(r"\s*-\s*[A-Z]{2}$", "", str(valor or "").upper().strip())


def _contratos() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "master_id": "alfa",
                "nome": "Alfa",
                "territorio": "DF/GO",
                "tipo_area": "Exclusividade",
                "regioes": ["Distrito Federal", "Goiás"],
                "regioes_tipos": ["Exclusividade", "Exclusividade"],
                "nota": None,
                "meta_quantidade": 5,
                "meta_por_ano": None,
                "meta_prazo": "2027-03-11",
                "conta_tambem": ["Santos"],
                "ordem": 0,
            },
            {
                "master_id": "beta",
                "nome": "Beta",
                "territorio": "SP",
                "tipo_area": "Sem exclusividade",
                "regioes": [],
                "regioes_tipos": [],
                "nota": "Sem território.",
                "meta_quantidade": None,
                "meta_por_ano": 4,
                "meta_prazo": None,
                "conta_tambem": [],
                "ordem": 1,
            },
        ]
    )


def _inauguradas() -> pd.DataFrame:
    return pd.DataFrame(
        [
            # (seção, unidade, UF, meta, operação)
            ("alfa", "Asa Norte", "DF", "alfa", "alfa"),
            ("alfa", "Asa Sul", "DF", "alfa", "alfa"),
            ("alfa", "Ceilândia", "DF", "alfa", "alfa"),
            ("alfa", "Gama", "DF", None, "alfa"),  # meta de "Holding…" (fora da config)
            ("alfa", "Recanto", "DF", "alfa", "alfa"),  # sem par no Growth
            ("alfa", "Formosa", "GO", "alfa", "alfa"),  # inaugura em dezembro
            ("alfa", "Novo Gama", "GO", "alfa", "alfa"),  # no Growth está em DF
            ("beta", "Santos", "SP", "beta", "beta"),  # o contrato do Alfa manda contar
            ("beta", "Bertioga", "SP", "beta", "alfa"),  # meta do Beta, operação do Alfa
        ],
        columns=["master_id", "unidade", "uf", "meta_master_id", "operacao_master_id"],
    )


def _pipeline() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("alfa", "Sudoeste", "Brasília", "DF", "Minuta", True),
            ("alfa", "Lago Sul", None, "DF", "Obras", True),
            ("alfa", "Guará", None, "DF", "sem status", None),
            ("alfa", "Taguatinga Norte", None, "DF", "Obras", False),
            ("alfa", "Águas Lindas", None, "GO", "Pré Venda", True),
            ("beta", "Jandira", None, "SP", "Projeto", True),
        ],
        columns=["master_id", "unidade", "cidade", "uf", "fase", "dentro_territorio"],
    )


def _datas():
    return indexar_datas(
        [
            ("ASA NORTE - DF", "DF", pd.Timestamp("2026-02-10")),
            ("ASA SUL", "DF", pd.Timestamp("2026-03-05")),
            ("CEILANDIA", "DF", pd.Timestamp("2026-08-20")),
            ("Ceilândia", "DF", pd.Timestamp("2026-08-20")),
            ("GAMA - DF", "DF", pd.Timestamp("2025-06-01")),
            ("FORMOSA", "GO", pd.Timestamp("2026-12-10")),
            ("NOVO GAMA", "DF", pd.Timestamp("2024-05-02")),
            ("SANTOS - SP", "SP", pd.Timestamp("2023-01-15")),
            ("BERTIOGA", "SP", pd.Timestamp("2026-01-20")),
            ("SEM DATA", "DF", None),
        ],
        chave,
    )


def _painel(master_id: str = "alfa") -> dict:
    p = painel_do_master(
        master_id, _contratos(), _inauguradas(), _pipeline(), _datas(), chave, HOJE
    )
    assert p is not None
    return p


def test_status_de_cada_unidade() -> None:
    p = _painel()
    operacao = {u["unidade"]: u for u in p["em_operacao"]}
    # Em operação: data no Growth até hoje, ou sem par (marcada) — Formosa abre em dezembro.
    assert set(operacao) == {
        "Asa Norte",
        "Asa Sul",
        "Ceilândia",
        "Gama",
        "Recanto",
        "Novo Gama",
        "Santos",
    }
    assert operacao["Asa Norte"]["inauguracao"] == "2026-02-10"
    assert operacao["Recanto"]["sem_data"] is True and operacao["Recanto"]["inauguracao"] is None
    # Novo Gama: GO na planilha, DF no Growth; o nome é único, então vale.
    assert operacao["Novo Gama"]["inauguracao"] == "2024-05-02"
    # Mais recentes primeiro, as sem data no fim.
    assert [u["unidade"] for u in p["em_operacao"]][:2] == ["Ceilândia", "Asa Sul"]
    assert p["em_operacao"][-1]["unidade"] == "Recanto"
    # Em inauguração: a data futura do Growth e a fase Pré Venda.
    inaug = [(u["unidade"], u["previsao"], u["fase"]) for u in p["em_inauguracao"]]
    assert inaug == [("Formosa", "2026-12-10", None), ("Águas Lindas", None, "Pré Venda")]
    # Contratos assinados: por fase, na ordem de quem está mais perto de abrir; sem status no fim.
    assert [(f["fase"], [u["unidade"] for u in f["unidades"]]) for f in p["assinados"]] == [
        ("Obras", ["Lago Sul", "Taguatinga Norte"]),
        ("Minuta", ["Sudoeste"]),
        ("sem status", ["Guará"]),
    ]
    assert p["resumo"] == {
        "em_operacao": 7,
        "em_inauguracao": 2,
        "assinados": 4,
        "ano": 2026,
        "abertas_no_ano": 3,
    }


def test_quem_conta_para_a_meta() -> None:
    operacao = {u["unidade"]: u for u in _painel()["em_operacao"]}
    # Santos é de outra seção, mas o contrato manda contar.
    assert operacao["Santos"]["conta_para_meta"] is True
    # Gama: meta de "Holding…" na planilha.
    assert operacao["Gama"]["conta_para_meta"] is False
    assert operacao["Gama"]["meta_de"] == OUTRA_ATRIBUICAO
    # Bertioga aparece no Beta (meta dele), com a operação do Alfa.
    beta = {u["unidade"]: u for u in _painel("beta")["em_operacao"]}
    assert beta["Bertioga"]["conta_para_meta"] is True
    assert beta["Bertioga"]["operacao_de"] == "Alfa"
    assert "Santos" in beta and beta["Santos"]["conta_para_meta"] is True


def test_meta_do_ano_e_do_contrato() -> None:
    m = _painel()["meta"]
    # Contam: Asa Norte (1º tri), Asa Sul (1º tri), Ceilândia (3º tri), Novo Gama (2024),
    # Santos (2023) e Recanto (sem data). Formosa ainda não abriu.
    assert m["n_contam"] == 6
    assert m["n_ano"] == 3
    assert [(t["trimestre"], t["novas"], t["acumulado"]) for t in m["trimestres"]] == [
        (1, 2, 2),
        (2, 0, 2),
        (3, 1, 3),
        (4, 0, 3),
    ]
    assert [t["atual"] for t in m["trimestres"]] == [False, False, False, True]
    assert all(t["pct"] is None for t in m["trimestres"])  # sem meta do ano
    assert m["quantidade"] == 5 and m["pct_contrato"] == 6 / 5
    assert m["prazo"] == "2027-03-11" and m["meses_ate_prazo"] == 4
    assert m["sem_data"] == ["Recanto"]

    beta = _painel("beta")["meta"]
    # Meta do ano de 4: Bertioga abriu em janeiro -> 25%.
    assert beta["por_ano"] == 4 and beta["n_ano"] == 1 and beta["pct_ano"] == 0.25
    assert beta["trimestres"][0]["pct"] == 0.25
    assert beta["prazo"] is None and beta["meses_ate_prazo"] is None
    assert beta["quantidade"] is None and beta["pct_contrato"] is None


def test_cards_na_ordem_da_config() -> None:
    lista = cards(_contratos(), _inauguradas(), _pipeline(), _datas(), chave, HOJE)
    assert [c["id"] for c in lista] == ["alfa", "beta"]
    alfa = lista[0]
    # O nome do master e o território à parte (18/11/2026, Juan).
    assert (alfa["nome"], alfa["territorio"]) == ("Alfa", "DF/GO")
    assert alfa["regioes"] == ["Distrito Federal", "Goiás"]
    assert alfa["resumo"]["em_operacao"] == 7
    assert alfa["meta"]["n_contam"] == 6 and alfa["meta"]["prazo"] == "2027-03-11"
    assert (
        painel_do_master("zeta", _contratos(), _inauguradas(), _pipeline(), _datas(), chave, HOJE)
        is None
    )


def test_data_por_nome_so_quando_e_unica() -> None:
    datas = indexar_datas(
        [
            ("CENTRO - SP", "SP", pd.Timestamp("2024-01-01")),
            ("CENTRO - RJ", "RJ", pd.Timestamp("2025-01-01")),
            ("UNICA", "DF", pd.Timestamp("2022-02-02")),
        ],
        chave,
    )
    assert data_da_unidade("Centro", "RJ", datas, chave) == pd.Timestamp("2025-01-01")
    # Nome em duas UFs com datas diferentes e a UF da planilha em nenhuma delas: sem data.
    assert data_da_unidade("Centro", "MG", datas, chave) is None
    assert data_da_unidade("Unica", "GO", datas, chave) == pd.Timestamp("2022-02-02")


def test_fases() -> None:
    assert fase_de_exibicao("sem status II") == "sem status"
    assert fase_de_exibicao(None) == "sem status"
    assert fase_de_exibicao(" Obras ") == "Obras"
    fases = ["sem status", "Minuta", "Outra", "Pré Venda", "Obras"]
    assert sorted(fases, key=ordem_da_fase) == [
        "Pré Venda",
        "Obras",
        "Minuta",
        "Outra",
        "sem status",
    ]
    assert meses_ate(pd.Timestamp("2026-01-31"), HOJE) == 0
