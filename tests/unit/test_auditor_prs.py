"""Testes das funcoes puras do Auditor de PRs (scripts/auditor_prs.py, BLK-ORQ-23)."""
from __future__ import annotations

import importlib.util
import pathlib

_HELPER = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "auditor_prs.py"
_spec = importlib.util.spec_from_file_location("auditor_prs", _HELPER)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

nivel_criticidade = _mod.nivel_criticidade
classificar_pr = _mod.classificar_pr
avaliar_incidentes = _mod.avaliar_incidentes
compor_relatorio = _mod.compor_relatorio

VERDE = dict.fromkeys(["test", "guard", "review-gate", "claude-review"], "pass")


def _pr(*, draft=False, mergeable="MERGEABLE", labels=None, checks=None):
    return {
        "draft": draft,
        "mergeable": mergeable,
        "labels": set(labels or []),
        "checks": dict(checks if checks is not None else VERDE),
    }


# ------------------------------------------------------------------ nivel_criticidade
def test_nivel_criticidade():
    assert nivel_criticidade({"criticidade:baixa", "outra"}) == "baixa"
    assert nivel_criticidade({"criticidade:critica"}) == "critica"
    assert nivel_criticidade({"aprovado-humano"}) is None
    assert nivel_criticidade({"criticidade:invalida"}) is None


# ------------------------------------------------------------------ classificar_pr
def test_baixa_verde_e_auto_merge():
    estado, _ = classificar_pr(_pr(labels={"criticidade:baixa"}))
    assert estado == "auto-merge"


def test_media_verde_e_auto_merge():
    estado, motivo = classificar_pr(_pr(labels={"criticidade:media"}))
    assert estado == "auto-merge"
    assert "verde" in motivo


def test_check_tecnico_vermelho_e_bloqueio():
    checks = {**VERDE, "test": "fail"}
    estado, motivo = classificar_pr(_pr(labels={"criticidade:baixa"}, checks=checks))
    assert estado == "bloqueio"
    assert "test" in motivo


def test_conflito_e_bloqueio():
    estado, motivo = classificar_pr(_pr(labels={"criticidade:baixa"}, mergeable="CONFLICTING"))
    assert estado == "bloqueio"
    assert "conflito" in motivo


def test_alta_sem_aprovado_humano_e_revisar():
    # guard/review-gate vermelhos por falta da label humana -> revisar (nao bloqueio)
    checks = {**VERDE, "guard": "fail", "review-gate": "fail"}
    estado, motivo = classificar_pr(_pr(labels={"criticidade:alta"}, checks=checks))
    assert estado == "revisar"
    assert "humana" in motivo


def test_critica_sem_label_dono_e_revisar():
    estado, motivo = classificar_pr(
        _pr(labels={"criticidade:critica", "aprovado-humano"})  # falta critica-aprovada
    )
    assert estado == "revisar"
    assert "critica-aprovada" in motivo


def test_critica_completa_e_auto_merge():
    estado, _ = classificar_pr(
        _pr(labels={"criticidade:critica", "aprovado-humano", "critica-aprovada"})
    )
    assert estado == "auto-merge"


def test_sem_label_criticidade_e_revisar():
    estado, motivo = classificar_pr(_pr(labels=set()))
    assert estado == "revisar"
    assert "criticidade" in motivo


def test_draft_e_revisar():
    estado, motivo = classificar_pr(_pr(draft=True, labels={"criticidade:baixa"}))
    assert estado == "revisar"
    assert "draft" in motivo


def test_pendente_e_auto_merge_aguardando():
    checks = {**VERDE, "test": "pending"}
    estado, motivo = classificar_pr(_pr(labels={"criticidade:media"}, checks=checks))
    assert estado == "auto-merge"
    assert "aguardando" in motivo


def test_gate_vermelho_com_label_e_bloqueio():
    # Alta COM aprovado-humano mas review-gate vermelho = defeito a investigar, nao espera
    checks = {**VERDE, "review-gate": "fail"}
    estado, motivo = classificar_pr(
        _pr(labels={"criticidade:alta", "aprovado-humano"}, checks=checks)
    )
    assert estado == "bloqueio"
    assert "investigar" in motivo


# ------------------------------------------------------------------ incidentes
def test_incidentes_soma_e_suspensao():
    assert avaliar_incidentes(0, 0, 0)["suspender"] is False
    assert avaliar_incidentes(1, 0, 0)["suspender"] is False
    i = avaliar_incidentes(1, 1, 0)
    assert i["total"] == 2 and i["suspender"] is True
    i2 = avaliar_incidentes(0, 1, 2)
    assert i2["total"] == 3 and i2["suspender"] is True


# ------------------------------------------------------------------ relatorio
def test_relatorio_conta_estados_e_evita_pii():
    prs = [
        {"number": 1, "title": "Bug X", "url": "http://x/1", "estado": "bloqueio", "motivo": "check test vermelho"},
        {"number": 2, "title": "Feat Y", "url": "http://x/2", "estado": "auto-merge", "motivo": "4 checks verdes"},
        {"number": 3, "title": "Doc Z", "url": "http://x/3", "estado": "revisar", "motivo": "Alta: aguarda aprovado-humano"},
    ]
    incid = avaliar_incidentes(0, 0, 0)
    txt = compor_relatorio(prs, incid, "2026-07-15")
    assert "3 PR(s) aberto(s)" in txt
    assert "1 auto-merge" in txt and "1 revisar" in txt and "1 bloqueio" in txt
    # bloqueio aparece antes de auto-merge (ordem de acao)
    assert txt.index("#1") < txt.index("#2")
    # links presentes, sem vazar conteudo de diff
    assert "http://x/1" in txt
    assert "diff" not in txt.split("Cobertura")[0].lower() or "sem diff" in txt.lower()


def test_relatorio_alerta_suspensao():
    incid = avaliar_incidentes(1, 1, 0)  # total 2 -> suspende
    txt = compor_relatorio([], incid, "2026-07-15")
    assert "SUSPENSAO recomendada" in txt
    assert "nenhum PR aberto" in txt
