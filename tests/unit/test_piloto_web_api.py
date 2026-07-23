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
    # contrato dos campos-chave do payload
    assert set(body) >= {
        "dre",
        "fcf_serie",
        "fco_serie",
        "mes_operacao_positiva",
        "aluguel_teto",
        "melhoria_payback",
    }
    dre = body["dre"]
    assert set(dre) >= {"faturamento", "ebitda", "lucro_liquido", "margem", "payback", "roic"}
    # DRE NAO expoe mais a linha de financiamento (reforma revertida no nucleo)
    assert "financiamento" not in dre and "resultado_franqueado" not in dre

    # aluguel-teto por CLUSTERS (nao mais escalar): ideal/teto/excecao = 15/20/30% do fat
    teto = body["aluguel_teto"]
    assert teto is not None and set(teto) == {"ideal", "teto", "excecao"}
    assert teto["ideal"] < teto["teto"] < teto["excecao"]
    assert teto["teto"] == pytest.approx(0.20 * dre["faturamento"], rel=1e-4)

    # ROIC DESALAVANCADO = lucro liquido anual / investimento total (capex + franquia 160k)
    investimento = 800_000 + 700_000 + 160_000
    assert dre["roic"] == pytest.approx((dre["lucro_liquido"] * 12) / investimento, abs=1e-3)

    # fco_serie e o resultado MENSAL (nao acumulado): comeca em M-4 (obras/pre-abertura, item
    # Felipe 2026-07-23) e segue ate a operacao. Os 4 primeiros meses (obras, com capex+aluguel)
    # sao negativos; a operacao comeca no mes 1.
    fco = body["fco_serie"]
    assert fco and [p["mes"] for p in fco[:4]] == [-4, -3, -2, -1]
    assert all(p["fcf"] < 0 for p in fco[:4])  # obras: desembolso de capex + aluguel
    assert any(p["mes"] == 1 for p in fco)  # operacao comeca no mes 1
    # fcf_serie (payback) parte de -(investimento): primeiro ponto e negativo
    assert body["fcf_serie"] and body["fcf_serie"][0]["fcf"] < 0


def test_backend_e_read_only() -> None:
    """Guardrail: o backend do piloto NAO escreve artefato (READ-ONLY sobre o M1)."""
    src = (_SERVER / "app.py").read_text(encoding="utf-8")
    proibidos = [".to_parquet(", ".to_csv(", ".to_feather(", "shutil.rmtree("]
    achados = [p for p in proibidos if p in src]
    assert not achados, f"backend do piloto deve ser READ-ONLY; escrita encontrada: {achados}"
