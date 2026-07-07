"""Testes do batch de viabilidade coordless (BLK-VIAB-03).

Regra: ZERO leitura de arquivo real. Fixtures sinteticas em memoria; parquets de
fixture em `tmp_path`. `analisar_viabilidade_ponto` e mockado nos testes de
fluxo/ranking para evitar rodar o DRE/brentq real e tornar os asserts
deterministicos.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import motor_expansao.dimensionamento.batch_viabilidade as bv
from motor_expansao.dimensionamento.batch_viabilidade import (
    COLUNAS_SAIDA,
    VERSAO_CONTRATO,
    assign_tier_e_faixa,
    carregar_base_calibracao,
    materializar,
    rodar_batch,
    rodar_candidato,
)

# ---------------------------------------------------------------------------
# Fixtures sinteticas
# ---------------------------------------------------------------------------


def _df_tiers() -> pd.DataFrame:
    """DataFrame de tiers sintetico com os 5 tiers canonicos."""
    return pd.DataFrame(
        [
            {"tier_label": "<1000", "p10": 1000.0, "p50": 1500.0, "p90": 2000.0,
             "flag_extrapolacao": False},
            {"tier_label": "1000-1499", "p10": 1200.0, "p50": 1800.0, "p90": 2500.0,
             "flag_extrapolacao": False},
            {"tier_label": "1500-1999", "p10": 1400.0, "p50": 2000.0, "p90": 3000.0,
             "flag_extrapolacao": False},
            {"tier_label": "2000-2999", "p10": 1600.0, "p50": 2200.0, "p90": 3200.0,
             "flag_extrapolacao": False},
            {"tier_label": ">=3000", "p10": 1800.0, "p50": 2400.0, "p90": 3600.0,
             "flag_extrapolacao": True},
        ]
    )


def _candidato(id_: str, nome: str, area: float, aluguel: float) -> pd.Series:
    return pd.Series(
        {
            "ID": id_,
            "NOME": nome,
            "ÁREA": area,
            "ALUGUEL": aluguel,
            "CIDADE": "TESTELANDIA",
            "ESTADO": "SP",
        }
    )


def _fake_grade() -> pd.DataFrame:
    """Grade 30x6 sintetica (shape identico ao motor real)."""
    linhas = []
    for a in (200.0, 400.0, 600.0, 800.0, 1000.0, 1200.0):
        for f in (0.6, 0.8, 1.0, 1.2, 1.5):
            linhas.append(
                {"alunos": a, "aluguel": 1000.0 * f, "fator_aluguel": f,
                 "margem_liq": 0.1, "viavel": True, "payback": 24.0}
            )
    return pd.DataFrame(
        linhas,
        columns=["alunos", "aluguel", "fator_aluguel", "margem_liq", "viavel", "payback"],
    )


def _make_fake_analisar(teto_por_aluno: float = 50.0):
    """Fabrica um fake de `analisar_viabilidade_ponto`.

    O teto = demanda_premissa * teto_por_aluno (monotonico em demanda), o que
    permite prever teto_p10<teto_p50<teto_p90 nos asserts. Captura as chamadas.
    """
    chamadas: list[dict] = []

    def _fake(**kwargs) -> SimpleNamespace:  # type: ignore[no-untyped-def]
        chamadas.append(kwargs)
        demanda = float(kwargs["demanda_premissa"])
        teto = demanda * teto_por_aluno
        return SimpleNamespace(
            aluguel_teto_calculado=teto,
            alunos_breakeven=100.0,
            alunos_para_margem_alvo=150.0,
            faixa_alunos_p10=300.0,
            faixa_alunos_p50=500.0,
            faixa_alunos_p90=700.0,
            grade_sensibilidade=_fake_grade(),
            viabilidade=SimpleNamespace(
                margem_ebitda_pct=0.22, payback_meses=18.0, flag_viavel=True
            ),
            demanda_fonte="premissa_explicita",
        )

    _fake.chamadas = chamadas  # type: ignore[attr-defined]
    return _fake


# ---------------------------------------------------------------------------
# carregar_base_calibracao
# ---------------------------------------------------------------------------


def test_carregar_base_calibracao_limpa(tmp_path):
    df = pd.DataFrame(
        {
            "metragem": [1000.0, 1500.0, np.nan, 0.0, -50.0, 2000.0],
            "alunos_por_m2": [1.0, 1.5, 2.0, 1.0, 1.0, np.nan],
        }
    )
    p = tmp_path / "ultra.parquet"
    df.to_parquet(p, index=False)

    out = carregar_base_calibracao(p)

    assert list(out.columns) == ["metragem", "alunos_por_m2"]
    assert (out["metragem"] > 0).all()
    assert (out["alunos_por_m2"] > 0).all()
    assert np.isfinite(out.to_numpy()).all()
    # Somente as 2 linhas boas (1000/1.0 e 1500/1.5) sobrevivem.
    assert len(out) == 2


def test_carregar_base_calibracao_deriva_de_alunos_total(tmp_path):
    df = pd.DataFrame({"metragem": [1000.0, 2000.0], "alunos_total": [1200.0, 3000.0]})
    p = tmp_path / "ultra.parquet"
    df.to_parquet(p, index=False)

    out = carregar_base_calibracao(p)

    assert list(out.columns) == ["metragem", "alunos_por_m2"]
    np.testing.assert_allclose(out["alunos_por_m2"].to_numpy(), [1.2, 1.5])


def test_carregar_base_calibracao_vazia_levanta(tmp_path):
    df = pd.DataFrame({"metragem": [0.0, np.nan], "alunos_por_m2": [np.nan, -1.0]})
    p = tmp_path / "ultra.parquet"
    df.to_parquet(p, index=False)

    with pytest.raises(ValueError):
        carregar_base_calibracao(p)


# ---------------------------------------------------------------------------
# assign_tier_e_faixa
# ---------------------------------------------------------------------------


def test_assign_tier_e_faixa_mapeia_correto():
    tiers = _df_tiers()

    label, p10, p50, p90, flag = assign_tier_e_faixa(1500.0, tiers)
    assert label == "1500-1999"
    assert (p10, p50, p90) == (1400.0, 2000.0, 3000.0)
    assert flag is False


def test_assign_tier_e_faixa_extrapolacao_no_tier_alto():
    tiers = _df_tiers()
    label, _p10, _p50, _p90, flag = assign_tier_e_faixa(4000.0, tiers)
    assert label == ">=3000"
    assert flag is True


def test_assign_tier_e_faixa_tier_ausente_levanta():
    tiers = _df_tiers()
    tiers = tiers[tiers["tier_label"] != ">=3000"]
    with pytest.raises(ValueError):
        assign_tier_e_faixa(4000.0, tiers)


# ---------------------------------------------------------------------------
# rodar_candidato
# ---------------------------------------------------------------------------


def test_rodar_candidato_coordless_e_flags(monkeypatch):
    fake = _make_fake_analisar(teto_por_aluno=50.0)
    monkeypatch.setattr(bv, "analisar_viabilidade_ponto", fake)

    # tier 1500-1999: p10=1400,p50=2000,p90=3000 -> teto 70000/100000/150000.
    # aluguel 90000 -> < teto_p50 (nao no-go), > teto_p10 (nao robusto).
    row = _candidato("A1", "CAND_A", 1500.0, 90000.0)
    d = rodar_candidato(row, pd.DataFrame({"metragem": [1], "alunos_por_m2": [1]}),
                        _df_tiers())

    # Coordless: setores_df=None em TODAS as 3 chamadas.
    assert len(fake.chamadas) == 3
    assert all(c["setores_df"] is None for c in fake.chamadas)
    # DEC-009: lat/lng sao os placeholders coordless (nao dados do candidato).
    assert all(c["lat"] == bv.LAT_COORDLESS and c["lng"] == bv.LNG_COORDLESS
               for c in fake.chamadas)

    assert d["aluguel_teto_p10"] == 70000.0
    assert d["aluguel_teto_p50"] == 100000.0
    assert d["aluguel_teto_p90"] == 150000.0
    assert d["margem_seguranca"] == 100000.0 - 90000.0
    assert d["flag_robusto"] is False  # 90000 >= teto_p10 70000
    assert d["flag_no_go"] is False  # 90000 <= teto_p50 100000
    assert d["demanda_p10"] == 1400.0
    assert d["demanda_p50"] == 2000.0
    assert d["demanda_p90"] == 3000.0
    assert d["flag_extrapolacao"] is False


def test_rodar_candidato_flag_robusto_e_no_go(monkeypatch):
    fake = _make_fake_analisar(teto_por_aluno=50.0)
    monkeypatch.setattr(bv, "analisar_viabilidade_ponto", fake)
    tiers = _df_tiers()

    # Robusto: aluguel muito baixo (< teto_p10=70000).
    d_rob = rodar_candidato(_candidato("R", "ROB", 1500.0, 10000.0),
                            pd.DataFrame({"metragem": [1], "alunos_por_m2": [1]}), tiers)
    assert d_rob["flag_robusto"] is True
    assert d_rob["flag_no_go"] is False

    # NO-GO: aluguel acima do teto_p50 (100000).
    d_no = rodar_candidato(_candidato("N", "NOGO", 1500.0, 120000.0),
                           pd.DataFrame({"metragem": [1], "alunos_por_m2": [1]}), tiers)
    assert d_no["flag_no_go"] is True
    assert d_no["flag_robusto"] is False


def test_rodar_candidato_grade_serializa(monkeypatch):
    fake = _make_fake_analisar()
    monkeypatch.setattr(bv, "analisar_viabilidade_ponto", fake)

    d = rodar_candidato(_candidato("G", "GRADE", 1500.0, 50000.0),
                        pd.DataFrame({"metragem": [1], "alunos_por_m2": [1]}),
                        _df_tiers())

    parsed = json.loads(d["grade_sensibilidade_json"])
    assert isinstance(parsed, list)
    reparsed = pd.read_json(d["grade_sensibilidade_json"], orient="records")
    assert reparsed.shape == (30, 6)


# ---------------------------------------------------------------------------
# rodar_batch
# ---------------------------------------------------------------------------


def _candidatos_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"ID": "A", "NOME": "CAND_A", "ÁREA": 1500.0, "ALUGUEL": 50000.0,
             "CIDADE": "C", "ESTADO": "SP"},
            {"ID": "B", "NOME": "CAND_B", "ÁREA": 1500.0, "ALUGUEL": 90000.0,
             "CIDADE": "C", "ESTADO": "SP"},
            {"ID": "C", "NOME": "CAND_C", "ÁREA": 1500.0, "ALUGUEL": 70000.0,
             "CIDADE": "C", "ESTADO": "SP"},
        ]
    )


def _grava_fixtures_batch(tmp_path):
    cand_p = tmp_path / "cand.parquet"
    tiers_p = tmp_path / "tiers.parquet"
    ultra_p = tmp_path / "ultra.parquet"
    _candidatos_df().to_parquet(cand_p, index=False)
    _df_tiers().to_parquet(tiers_p, index=False)
    pd.DataFrame({"metragem": [1500.0, 1600.0], "alunos_por_m2": [1.0, 1.1]}).to_parquet(
        ultra_p, index=False
    )
    return cand_p, tiers_p, ultra_p


def test_rodar_batch_ranking_desc(monkeypatch, tmp_path):
    monkeypatch.setattr(bv, "analisar_viabilidade_ponto", _make_fake_analisar(50.0))
    cand_p, tiers_p, ultra_p = _grava_fixtures_batch(tmp_path)

    df = rodar_batch(cand_p, tiers_p, ultra_p)

    assert len(df) == 3
    # teto_p50 = 100000 fixo (mesmo tier). margem = 100000 - aluguel.
    # A=50k -> 50k ; C=70k -> 30k ; B=90k -> 10k. Ordem DESC: A, C, B.
    assert df["ID"].tolist() == ["A", "C", "B"]
    assert df["margem_seguranca"].is_monotonic_decreasing


def test_rodar_batch_colunas_e_sem_geo_pii(monkeypatch, tmp_path):
    monkeypatch.setattr(bv, "analisar_viabilidade_ponto", _make_fake_analisar())
    cand_p, tiers_p, ultra_p = _grava_fixtures_batch(tmp_path)

    df = rodar_batch(cand_p, tiers_p, ultra_p)

    assert list(df.columns) == COLUNAS_SAIDA
    for col in ("LATITUDE", "LONGITUDE", "LOGRADOURO", "CEP", "BAIRRO", "NÚMERO"):
        assert col not in df.columns


def test_demanda_fonte_premissa_em_todas_linhas(monkeypatch, tmp_path):
    monkeypatch.setattr(bv, "analisar_viabilidade_ponto", _make_fake_analisar())
    cand_p, tiers_p, ultra_p = _grava_fixtures_batch(tmp_path)

    df = rodar_batch(cand_p, tiers_p, ultra_p)

    assert (df["demanda_fonte"] == "premissa_explicita").all()
    assert (df["versao_contrato"] == VERSAO_CONTRATO).all()


def test_determinismo(monkeypatch, tmp_path):
    monkeypatch.setattr(bv, "analisar_viabilidade_ponto", _make_fake_analisar())
    cand_p, tiers_p, ultra_p = _grava_fixtures_batch(tmp_path)

    df1 = rodar_batch(cand_p, tiers_p, ultra_p)
    df2 = rodar_batch(cand_p, tiers_p, ultra_p)

    pd.testing.assert_frame_equal(df1, df2)


# ---------------------------------------------------------------------------
# materializar
# ---------------------------------------------------------------------------


def test_materializar_gera_parquet_e_md(monkeypatch, tmp_path):
    monkeypatch.setattr(bv, "analisar_viabilidade_ponto", _make_fake_analisar())
    cand_p, tiers_p, ultra_p = _grava_fixtures_batch(tmp_path)
    df = rodar_batch(cand_p, tiers_p, ultra_p)
    # Forca um candidato extrapolado para exercitar o aviso do relatorio.
    df.loc[0, "flag_extrapolacao"] = True

    staging = tmp_path / "staging"
    analysis = tmp_path / "analysis"
    parquet_path, md_path = materializar(df, staging, analysis)

    assert parquet_path.exists()
    assert md_path.exists()
    relido = pd.read_parquet(parquet_path)
    assert list(relido.columns) == COLUNAS_SAIDA

    texto = md_path.read_text(encoding="utf-8")
    assert "BLK-VIAB-03" in texto
    assert "Extrapolação de tier" in texto
    assert "DEC-009" in texto
