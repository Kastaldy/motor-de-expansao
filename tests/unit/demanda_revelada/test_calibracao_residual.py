"""BLK-TP-06: testes offline (seed-fixo, sem I/O de rede) da validacao residual->demanda.

Fixtures SINTETICAS (nunca a fonte real NAO_ABRA/): join demanda x mercado com colunas
agregadas do contrato. Cobre: anti-PII, LOO/k-fold honesto (R2 in-sample so auditoria, fora
do veredito), intervalos + flag_extrapolacao, alvo=`membros` / preditor=`score_oportunidade_
residual` (anti-inversao dos 2 tipos; `alunos_parceiras` nunca alvo), demanda nunca como
preditor geografico (asserção de FEATURES), isolamento de import, IC determinista (R2 e rho),
GO/NO-GO (sinal forte->GO; ruido->NO-GO).
"""

from __future__ import annotations

import ast
import inspect
import re

import numpy as np
import pandas as pd
import pytest

from motor_expansao.demanda_revelada import calibracao_residual as m
from motor_expansao.demanda_revelada.calibracao_residual import (
    FEATURES_PRINCIPAIS,
    CalibracaoResidualResult,
    _assert_sem_pii_no_relatorio,
    _join_demanda_residual,
    calibrar_residual_demanda,
    correlacoes_bivariadas,
    preparar_dados,
    relatorio_calibracao,
)
from motor_expansao.demanda_revelada.contrato import COLUNAS_PII_PROIBIDAS


# --------------------------------------------------------------------------- #
# Fixtures sinteticas (join demanda x mercado ja resolvido)
# --------------------------------------------------------------------------- #
def _hexes(n: int) -> list[str]:
    return [f"87a{i:012x}ffff" for i in range(n)]


@pytest.fixture
def join_forte() -> pd.DataFrame:
    """Join onde membros CRESCE monotonicamente com o score residual + ruido pequeno.

    Sinal forte e estavel -> deve generalizar out-of-fold (esperado GO).
    """
    rng = np.random.default_rng(7)
    n = 400
    score = rng.uniform(0.0, 100.0, n)
    # log1p(membros) ~ linear no score => membros cresce forte com o score.
    log_mem = 0.06 * score + rng.normal(0.0, 0.3, n)
    membros = np.expm1(np.clip(log_mem, 0.0, None)).round().astype(int)
    oferta = np.clip(score * 25.0 + rng.normal(0.0, 100.0, n), 0.0, None)
    n_acad = rng.integers(0, 30, n)
    return pd.DataFrame(
        {
            "hex_id": _hexes(n),
            "membros": membros,
            "alunos_parceiras": (n_acad * rng.uniform(2.0, 40.0, n)).round().astype(int),
            "n_acad_parceiras": n_acad,
            "score_oportunidade_residual": score,
            "oferta_efetiva_disponivel": oferta,
            "uf": np.where(np.arange(n) % 3 == 0, "SP", np.where(np.arange(n) % 3 == 1, "MG", "RJ")),
        }
    )


@pytest.fixture
def join_ruido() -> pd.DataFrame:
    """Join onde membros e INDEPENDENTE do score residual (ruido puro).

    O residual nao ordena a demanda -> nao deve generalizar (esperado NO-GO; IC cruza zero).
    """
    rng = np.random.default_rng(42)
    n = 400
    score = rng.uniform(0.0, 100.0, n)
    membros = rng.integers(0, 5000, n)  # sem relacao com score
    oferta = rng.uniform(0.0, 3000.0, n)  # sem relacao
    n_acad = rng.integers(0, 30, n)
    return pd.DataFrame(
        {
            "hex_id": _hexes(n),
            "membros": membros,
            "alunos_parceiras": (n_acad * rng.uniform(2.0, 40.0, n)).round().astype(int),
            "n_acad_parceiras": n_acad,
            "score_oportunidade_residual": score,
            "oferta_efetiva_disponivel": oferta,
            "uf": ["SP"] * n,
        }
    )


# --------------------------------------------------------------------------- #
# Testes
# --------------------------------------------------------------------------- #
def test_anti_pii(join_forte):
    """Nenhuma coluna de COLUNAS_PII_PROIBIDAS como TOKEN isolado no relatorio/result."""
    res = calibrar_residual_demanda(join_forte)
    texto = relatorio_calibracao(res).lower()
    # o proprio guard nao deve levantar sobre a saida honesta
    _assert_sem_pii_no_relatorio(relatorio_calibracao(res))
    for col in COLUNAS_PII_PROIBIDAS:
        assert re.search(rf"\b{re.escape(col.lower())}\b", texto) is None, (
            f"PII '{col}' vazou no relatorio"
        )
    # o result nao carrega campo com nome de coluna proibida
    for campo in vars(res):
        assert campo not in COLUNAS_PII_PROIBIDAS


def test_loo_honesto_r2_insample_fora_do_veredito(join_forte):
    """R2 in-sample existe rotulado como auditoria e NUNCA decide o veredito (DEC-008)."""
    res = calibrar_residual_demanda(join_forte)
    # o campo existe (auditoria) mas com rotulo literal no relatorio
    assert hasattr(res, "r2_insample")
    texto = relatorio_calibracao(res)
    assert "apenas auditoria -- NAO usar como desempenho" in texto
    # o veredito NAO pode depender do r2_insample: mesmo se ele for alto, o gate usa oof.
    # Sanidade: o gate GO exige IC oof > 0, nao o in-sample.
    if res.go and res.tipo_go == "ancora_r2":
        assert res.ic95_r2_oof[0] > 0.0
    if res.go and res.tipo_go == "suporte_rho":
        assert res.ic95_rho_oof[0] > 0.0


def test_intervalos_e_flag_extrapolacao_presentes(join_forte):
    """IC95 (R2 e rho) ordenados; pct_extrapolacao finito; flag global bool."""
    res = calibrar_residual_demanda(join_forte)
    assert res.ic95_r2_oof[0] <= res.ic95_r2_oof[1]
    assert res.ic95_rho_oof[0] <= res.ic95_rho_oof[1]
    assert np.isfinite(res.pct_extrapolacao)
    assert isinstance(res.flag_extrapolacao_padrao_global, bool)
    # secundario reportado separado, com IC
    assert isinstance(res.r2_oof_secundario, float)
    assert res.ic95_r2_oof_secundario[0] <= res.ic95_r2_oof_secundario[1]


def test_alvo_membros_preditor_score_nao_inverte(join_forte):
    """Alvo = membros; preditor = score_oportunidade_residual; alunos_parceiras nunca alvo."""
    # preparar_dados deve produzir X = score (1 coluna) e y = log1p(membros)
    X, y, meta = preparar_dados(join_forte, secundario=False)
    assert X.shape[1] == 1
    assert meta["features"] == list(FEATURES_PRINCIPAIS)
    assert FEATURES_PRINCIPAIS == ("score_oportunidade_residual",)
    # y deve ser log1p(membros): expm1(y) ~ membros originais (subset finito)
    membros = pd.to_numeric(join_forte["membros"], errors="coerce").to_numpy(float)
    assert np.allclose(np.expm1(y), membros, atol=1e-6)
    # `membros` NUNCA e feature; `alunos_parceiras` NUNCA e alvo nem feature principal.
    assert "membros" not in FEATURES_PRINCIPAIS
    assert "alunos_parceiras" not in FEATURES_PRINCIPAIS
    # correlacoes bivariadas: alunos_parceiras aparece SO como covariavel (chave), nunca alvo.
    corr = correlacoes_bivariadas(join_forte)
    assert "score_oportunidade_residual" in corr
    assert "alunos_parceiras" in corr  # cross-check, nao alvo


def test_demanda_nunca_preditor_geografico(join_forte):
    """`membros`/colunas da demanda nao aparecem em FEATURES (DEC-009)."""
    for feat in FEATURES_PRINCIPAIS:
        assert "membros" not in feat
        assert "alunos_parceiras" not in feat
    # o codigo-fonte da preparacao principal usa score como preditor e membros so como alvo (y).
    src = inspect.getsource(preparar_dados)
    # `membros` aparece so no contexto do alvo (log1p) -- garantimos que score e o preditor principal.
    assert "score_oportunidade_residual" in src


def test_isolamento_import():
    """O modulo nao importa de pipelines.m1/dashboard/censo/api/config (DEC-012)."""
    src = inspect.getsource(m)
    tree = ast.parse(src)
    mods: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mods.append(node.module or "")
        elif isinstance(node, ast.Import):
            mods.extend(a.name for a in node.names)
    proibidos = ("pipelines.m1", "dashboard", "censo", "motor_expansao.api")
    bad = [mod for mod in mods if any(p in mod for p in proibidos)]
    assert not bad, f"imports proibidos no modulo: {bad}"
    # `config` da raiz (import direto de `config`): nao pode ser importado.
    assert "config" not in mods
    # rede extra: nenhuma LINHA de import textual referencia os proibidos (docstring nao conta)
    linhas_import = [
        ln for ln in src.splitlines() if ln.strip().startswith(("import ", "from "))
    ]
    for ln in linhas_import:
        for proibido in ("pipelines.m1", "dashboard", "censo_", "motor_expansao.api"):
            assert proibido not in ln, f"import textual proibido '{proibido}': {ln!r}"


def test_ic_determinista_r2_e_rho(join_forte):
    """Mesma seed -> mesmo IC95 de R2 e de rho, e mesmo R2/rho oof (reprodutibilidade)."""
    r1 = calibrar_residual_demanda(join_forte)
    r2 = calibrar_residual_demanda(join_forte)
    assert r1.ic95_r2_oof == pytest.approx(r2.ic95_r2_oof)
    assert r1.ic95_rho_oof == pytest.approx(r2.ic95_rho_oof)
    assert r1.r2_oof_log == pytest.approx(r2.r2_oof_log)
    assert r1.rho_oof == pytest.approx(r2.rho_oof)


def test_go_nogo_criterio(join_forte, join_ruido):
    """Sinal forte -> go=True; ruido -> go=False (ancora e suporte falham)."""
    forte = calibrar_residual_demanda(join_forte)
    ruido = calibrar_residual_demanda(join_ruido)
    assert forte.go is True
    assert forte.veredito == "GO"
    assert forte.tipo_go in {"ancora_r2", "suporte_rho"}
    # sinal forte: ao menos o alinhamento monotonico com IC positivo
    assert forte.rho_oof > 0.0

    assert ruido.go is False
    assert ruido.veredito == "NO-GO"
    # NO-GO: ancora falha (R2<=limiar OU IC cruza zero) E suporte falha (rho<limiar OU IC cruza zero)
    ancora_ok = ruido.r2_oof_log > 0.05 and ruido.ic95_r2_oof[0] > 0.0
    suporte_ok = ruido.rho_oof >= 0.30 and ruido.ic95_rho_oof[0] > 0.0
    assert not ancora_ok
    assert not suporte_ok


def test_join_demanda_residual_inner():
    """`_join_demanda_residual` faz inner por hex_id e traz so colunas agregadas."""
    dem = pd.DataFrame(
        {
            "hex_id": ["a", "b", "c"],
            "membros": [10, 20, 30],
            "alunos_parceiras": [1, 2, 3],
            "n_acad_parceiras": [1, 1, 1],
        }
    )
    mkt = pd.DataFrame(
        {
            "hex_id": ["b", "c", "d"],
            "score_oportunidade_residual": [5.0, 6.0, 7.0],
            "oferta_efetiva_disponivel": [100.0, 200.0, 300.0],
            "uf": ["SP", "MG", "RJ"],
        }
    )
    j = _join_demanda_residual(dem, mkt)
    assert len(j) == 2  # b, c
    assert set(j["hex_id"]) == {"b", "c"}
    # nenhuma coluna PII entra
    for col in COLUNAS_PII_PROIBIDAS:
        assert col not in j.columns


def test_result_tipo(join_forte):
    """O orquestrador devolve o dataclass esperado com campos-chave finitos."""
    res = calibrar_residual_demanda(join_forte)
    assert isinstance(res, CalibracaoResidualResult)
    assert res.n_join == len(join_forte)
    assert res.n_treinamento <= res.n_join
    assert 0.0 < res.pct_cobertura_universo < 100.0
    assert res.metodo_validacao in {"kfold_5x5", "kfold_10x5", "loo"}
    assert isinstance(res.concentracao_uf, dict)
