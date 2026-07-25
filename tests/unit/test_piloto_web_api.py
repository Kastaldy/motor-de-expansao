"""Smoke de contrato + guardrail READ-ONLY do backend do piloto web (web/server/app.py).

Roda no CI (job `test`) SEM os parquets: o backend degrada gracioso sem os dados
(base_calibracao=None -> faixa=None; setores_df=None -> sem catchment), entao os
endpoints respondem mesmo assim. Chama as funcoes de rota DIRETO (sem TestClient/httpx)
— testa a logica sem depender de httpx nem subir servidor.

Guardrail: o backend do piloto e READ-ONLY sobre o M1 (nao escreve artefato oficial).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot_app  # noqa: E402  (backend do piloto; web/server no sys.path acima)


def test_health_ok() -> None:
    # /api/health: liveness + diagnostico (data_dir etc.); basta o status ok.
    assert pilot_app.health().get("status") == "ok"


def test_faixa_alunos_contrato() -> None:
    body = pilot_app.faixa_alunos(m2=1500)
    assert set(body) >= {"p10", "p50", "p90", "n_comparaveis"}


def test_viabilidade_contrato_e_coerencia() -> None:
    """Contrato `viabilidade_payload_v1` (FIN-VIAB-01).

    O payload antigo tinha DUAS series (`fcf_serie` acumulada e `fco_serie` mensal),
    montadas no backend, mais `dre.payback`/`dre.roic` que SOBRESCREVIAM os do motor —
    a duplicacao que fazia o card dizer 35 e o grafico 33. Agora existe UMA serie
    (`serie_mensal`, do nucleo) e o payback/retorno sao os do motor, sem override.
    """
    body = pilot_app.viabilidade(
        pilot_app.ViabilidadeIn(
            lat=-23.5,
            lng=-46.6,
            m2=1500,
            aluguel=30000,
            demanda=1600,
            ticket=177,
            obra=800_000,
            equipamentos=700_000,
        )
    )
    assert body["versao"] == pilot_app.VIABILIDADE_PAYLOAD_VERSAO
    assert set(body) >= {
        "premissas",
        "dre",
        "investimento",
        "retorno",
        "break_even",
        "aluguel_teto",
        "faixa_alunos",
        "serie_mensal",
        "split",
        "grade",
    }
    # As series duplicadas do backend NAO existem mais.
    assert "fcf_serie" not in body and "fco_serie" not in body

    dre = body["dre"]
    assert set(dre) >= {
        "faturamento", "deducoes", "impostos", "custos_op", "custos_variaveis",
        "folha", "custos_fixos", "ebitda", "margem", "ir_csll", "resultado_apos_ir",
    }
    # Cascata coerente: as PARCELAS do custo vem do motor, nao por diferenca.
    assert dre["custos_op"] == pytest.approx(
        dre["custos_variaveis"] + dre["folha"] + dre["custos_fixos"], abs=0.05
    )
    assert dre["faturamento"] - dre["deducoes"] - dre["impostos"] - dre["custos_op"] == (
        pytest.approx(dre["ebitda"], abs=0.05)
    )
    # margem em FRACAO (0,3873 = 38,73%), como todo percentual do payload.
    assert 0.0 <= dre["margem"] <= 1.0

    # Aluguel-teto = % do faturamento bruto steady (unica definicao do sistema).
    teto = body["aluguel_teto"]
    assert teto["base"] == "faturamento_bruto"
    assert teto["ideal"] < teto["teto"] < teto["excecao"]
    # Card grande usa o TETO (20%), nao a excecao (decisao de Felipe 2026-07-24).
    assert teto["canonico"] == pytest.approx(teto["teto"])
    assert teto["teto"] == pytest.approx(0.20 * dre["faturamento"], rel=1e-4)

    # Retorno DESALAVANCADO = (EBITDA - IR) x12 / investimento total (capex + franquia).
    inv = body["investimento"]
    assert inv["investimento_total"] == pytest.approx(800_000 + 700_000 + 160_000)
    assert body["retorno"]["otica"] == "desalavancada"
    assert body["retorno"]["retorno_anual_desalavancado"] == pytest.approx(
        (dre["resultado_apos_ir"] * 12) / inv["investimento_total"], abs=1e-3
    )

    # Break-even em alunos TOTAIS (comparavel com a demanda digitada); o de caixa
    # (que cobre a PMT) e sempre >= o de EBITDA.
    be = body["break_even"]
    assert be["unidade"] == "alunos_totais"
    assert be["caixa"] >= be["ebitda"]

    # A UNICA serie: M-4..M-1 de pre-abertura + M1..M60 de operacao, com o CAPEX dentro.
    serie = body["serie_mensal"]
    assert [linha["mes"] for linha in serie[:4]] == [-4, -3, -2, -1]
    assert all(linha["fase"] == "pre_operacional" for linha in serie[:4])
    assert serie[0]["fcf_acumulado"] < 0  # o acumulado parte do desembolso
    assert serie[-1]["mes"] == body["premissas"]["horizonte_meses"]
    assert body["acumulado_mes_final"] == pytest.approx(serie[-1]["fcf_acumulado"])

    # FOLHA FIXA desde o mes 1 (decisao de Felipe, 2026-07-24): a folha da serie NAO
    # acompanha a rampa de alunos -- ela e dimensionada pelo faturamento MADURO e paga
    # inteira desde o mes 1. O `dre.folha` do topo e a folha de QUALQUER mes do ano 1.
    operacao = [linha for linha in serie if linha["fase"] == "operacao"]
    ano1 = operacao[:12]
    assert len({linha["folha"] for linha in ano1}) == 1, "a folha voltou a escalar"
    assert ano1[0]["folha"] == pytest.approx(dre["folha"], abs=0.01)
    assert ano1[0]["ebitda_mensal"] < 0  # o mes 1 nasce no vermelho por causa dela
    assert operacao[12]["folha"] > ano1[0]["folha"]  # reajuste anual so no mes 13

    # TAXA DE FRANQUIA PARCELADA (mesma decisao): N parcelas iguais nos meses de
    # contrato 1..N, e a SOMA das parcelas == taxa_franquia.
    n_parcelas = inv["parcelas_franquia"]
    assert n_parcelas >= 1
    assert inv["franquia_parcela"] == pytest.approx(inv["taxa_franquia"] / n_parcelas, abs=0.01)
    parcelas = [linha for linha in serie if linha["mes_contrato"] <= n_parcelas]
    assert [linha["mes_contrato"] for linha in parcelas] == list(range(1, n_parcelas + 1))


def test_backend_e_read_only() -> None:
    """Guardrail: o backend do piloto NAO escreve artefato (READ-ONLY sobre o M1)."""
    src = (_SERVER / "app.py").read_text(encoding="utf-8")
    proibidos = [".to_parquet(", ".to_csv(", ".to_feather(", "shutil.rmtree("]
    achados = [p for p in proibidos if p in src]
    assert not achados, f"backend do piloto deve ser READ-ONLY; escrita encontrada: {achados}"
