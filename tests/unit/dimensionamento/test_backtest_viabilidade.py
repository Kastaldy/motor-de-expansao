"""Testes do backtest LOO do motor de viabilidade (BLK-VIAB-04).

Regra: ZERO leitura de arquivo real. Fixtures sinteticas em memoria; parquets de
fixture em `tmp_path`. `analisar_viabilidade_ponto` e mockado nos testes de
fluxo/ranking (via monkeypatch do atributo de modulo) para tornar os asserts
deterministicos e nao rodar o DRE/brentq real — EXCETO o teste que prova a
execucao real do motor sem mock.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import motor_expansao.dimensionamento.backtest_viabilidade as bkt
from motor_expansao.dimensionamento.backtest_viabilidade import (
    COLUNAS_SAIDA,
    TICKET_PLACEHOLDER_ENG,
    VERSAO_CONTRATO,
    analisar_viabilidade_ponto,
    calcular_loo_base,
    calcular_metricas_agregadas,
    carregar_eng_corpo,
    carregar_ultra,
    materializar,
    rodar_backtest,
    rodar_unidade_loo,
)

# ---------------------------------------------------------------------------
# Fixtures sinteticas
# ---------------------------------------------------------------------------


def _df_ultra_fake(n: int = 6) -> pd.DataFrame:
    """DataFrame Ultra sintetico coerente (indice 0..n-1)."""
    metragens = np.linspace(1000.0, 2500.0, n)
    apm = np.linspace(2.0, 3.0, n)  # alunos_por_m2 coerente
    alunos = metragens * apm
    return pd.DataFrame(
        {
            "unidade": [f"UN{i}" for i in range(n)],
            "metragem": metragens,
            "alunos_total": alunos,
            "ticket_medio_aluno": np.linspace(60.0, 90.0, n),
            "alunos_por_m2": apm,
        }
    ).reset_index(drop=True)


def _fake_res(
    *,
    p10: float | None = 1000.0,
    p50: float | None = 1500.0,
    p90: float | None = 2000.0,
    n_comparaveis: int | None = 5,
    breakeven: float = 800.0,
    margem_alvo: float = 1000.0,
    aluguel_teto: float = 30000.0,
    flag_viavel: bool = True,
) -> SimpleNamespace:
    """SimpleNamespace imitando ViabilidadePontoResult."""
    return SimpleNamespace(
        faixa_alunos_p10=p10,
        faixa_alunos_p50=p50,
        faixa_alunos_p90=p90,
        n_comparaveis=n_comparaveis,
        alunos_breakeven=breakeven,
        alunos_para_margem_alvo=margem_alvo,
        aluguel_teto_calculado=aluguel_teto,
        viabilidade=SimpleNamespace(flag_viavel=flag_viavel),
        demanda_fonte="premissa_explicita",
    )


def _mock_motor_captura(monkeypatch, *, res_factory=None):
    """Monkeypatcha o motor no modulo bkt e devolve a lista de kwargs capturados."""
    capturas: list[dict] = []

    def fake(**kwargs):
        capturas.append(kwargs)
        if res_factory is not None:
            return res_factory(**kwargs)
        return _fake_res()

    monkeypatch.setattr(bkt, "analisar_viabilidade_ponto", fake)
    return capturas


# ---------------------------------------------------------------------------
# 1-2. carregar_ultra
# ---------------------------------------------------------------------------


def test_carregar_ultra_retorna_df(tmp_path):
    p = tmp_path / "ultra.parquet"
    _df_ultra_fake(5).to_parquet(p, index=False)
    df = carregar_ultra(p)
    assert len(df) == 5
    for col in ("unidade", "metragem", "alunos_total", "ticket_medio_aluno", "alunos_por_m2"):
        assert col in df.columns
    # indice resetado 0..4
    assert list(df.index) == [0, 1, 2, 3, 4]


def test_carregar_ultra_falha_col_ausente(tmp_path):
    p = tmp_path / "ultra_bad.parquet"
    df = _df_ultra_fake(4).drop(columns=["alunos_total"])
    df.to_parquet(p, index=False)
    with pytest.raises(ValueError):
        carregar_ultra(p)


# ---------------------------------------------------------------------------
# 3-4. calcular_loo_base
# ---------------------------------------------------------------------------


def test_calcular_loo_base_exclui_idx():
    df = _df_ultra_fake(6)
    base = calcular_loo_base(df, 2)
    assert len(base) == len(df) - 1
    assert "UN2" not in set(base["unidade"])


def test_calcular_loo_base_reset_index():
    df = _df_ultra_fake(6)
    base = calcular_loo_base(df, 3)
    assert list(base.index)[0] == 0
    assert list(base.index) == list(range(len(df) - 1))


# ---------------------------------------------------------------------------
# 5-6. rodar_unidade_loo — kwargs do motor
# ---------------------------------------------------------------------------


def test_rodar_unidade_loo_chama_motor(monkeypatch):
    df = _df_ultra_fake(6)
    capt = _mock_motor_captura(monkeypatch)
    row = df.iloc[2]
    rodar_unidade_loo(row, df, 2)
    assert len(capt) == 1
    kw = capt[0]
    assert kw["setores_df"] is None
    assert kw["lat"] == 0.0 and kw["lng"] == 0.0
    base_passada = kw["base_calibracao_df"]
    # a propria unidade NAO esta na base LOO passada ao motor
    assert "UN2" not in set(base_passada["unidade"])
    assert len(base_passada) == len(df) - 1


def test_rodar_unidade_loo_demanda_premissa_e_alunos_real(monkeypatch):
    df = _df_ultra_fake(6)
    capt = _mock_motor_captura(monkeypatch)
    for idx in range(len(df)):
        rodar_unidade_loo(df.iloc[idx], df, idx)
    for idx, kw in enumerate(capt):
        # DEC-009: demanda_premissa == alunos_total real (NUNCA lat/lng)
        assert kw["demanda_premissa"] == pytest.approx(float(df.iloc[idx]["alunos_total"]))
        assert kw["ticket_medio"] == pytest.approx(float(df.iloc[idx]["ticket_medio_aluno"]))


# ---------------------------------------------------------------------------
# 7-8. faixa_contem_real
# ---------------------------------------------------------------------------


def test_faixa_contem_real_true(monkeypatch):
    df = _df_ultra_fake(6)
    row = df.iloc[2]
    alunos_real = float(row["alunos_total"])
    _mock_motor_captura(
        monkeypatch,
        res_factory=lambda **kw: _fake_res(p10=0.0, p50=alunos_real, p90=alunos_real + 1),
    )
    out = rodar_unidade_loo(row, df, 2)
    assert out["faixa_contem_real"] is True


def test_faixa_contem_real_false(monkeypatch):
    df = _df_ultra_fake(6)
    row = df.iloc[2]
    alunos_real = float(row["alunos_total"])
    _mock_motor_captura(
        monkeypatch,
        res_factory=lambda **kw: _fake_res(
            p10=alunos_real + 1000, p50=alunos_real + 2000, p90=alunos_real + 3000
        ),
    )
    out = rodar_unidade_loo(row, df, 2)
    assert out["faixa_contem_real"] is False


# ---------------------------------------------------------------------------
# 9-10. rodar_backtest + versao_contrato
# ---------------------------------------------------------------------------


def test_rodar_backtest_n_rows(monkeypatch):
    df = _df_ultra_fake(6)
    _mock_motor_captura(monkeypatch)
    out = rodar_backtest(df)
    assert len(out) == 6
    for col in COLUNAS_SAIDA:
        assert col in out.columns


def test_versao_contrato(monkeypatch):
    assert VERSAO_CONTRATO == "viabilidade_backtest_v1"
    df = _df_ultra_fake(4)
    _mock_motor_captura(monkeypatch)
    out = rodar_backtest(df)
    assert (out["versao_contrato"] == "viabilidade_backtest_v1").all()
    assert (out["demanda_fonte"] == "premissa_explicita").all()


# ---------------------------------------------------------------------------
# 11-12. metricas agregadas
# ---------------------------------------------------------------------------


def test_calcular_metricas_mae():
    df = pd.DataFrame(
        {
            "alunos_real": [100.0, 200.0, 300.0],
            "faixa_alunos_p50_predito": [110.0, 190.0, 330.0],
            "faixa_contem_real": [True, True, False],
            "flag_viavel": [True, True, False],
            "flag_extrapolacao": [False, False, True],
        }
    )
    met = calcular_metricas_agregadas(df)
    # MAE = mean(|10|, |-10|, |30|) = 50/3
    assert met["mae"] == pytest.approx(50.0 / 3.0)
    assert met["n"] == 3


def test_calcular_metricas_vies():
    df = pd.DataFrame(
        {
            "alunos_real": [100.0, 200.0, 300.0],
            "faixa_alunos_p50_predito": [110.0, 190.0, 330.0],
            "faixa_contem_real": [True, True, False],
            "flag_viavel": [True, True, False],
            "flag_extrapolacao": [False, False, True],
        }
    )
    met = calcular_metricas_agregadas(df)
    # vies = mean(10, -10, 30) = 30/3 = 10 (SEM valor absoluto)
    assert met["vies"] == pytest.approx(30.0 / 3.0)


# ---------------------------------------------------------------------------
# Motor real (sem mock) + anti-PII + relatorio
# ---------------------------------------------------------------------------


def test_motor_importado_real_nao_mock():
    # o simbolo importado no modulo aponta ao motor real (nao hardcoded/mock)
    assert bkt.analisar_viabilidade_ponto is analisar_viabilidade_ponto
    from motor_expansao.dimensionamento import viabilidade_ponto as vp

    assert analisar_viabilidade_ponto is vp.analisar_viabilidade_ponto
    # execucao REAL do motor (sem monkeypatch) num df pequeno -> N linhas, faixas float
    df = _df_ultra_fake(5)
    out = rodar_backtest(df)
    assert len(out) == 5
    assert (out["demanda_fonte"] == "premissa_explicita").all()
    assert out["faixa_alunos_p50_predito"].map(lambda v: isinstance(v, float)).all()


def test_sem_pii_em_saida(monkeypatch):
    df = _df_ultra_fake(6)
    _mock_motor_captura(monkeypatch)
    out = rodar_backtest(df)
    proibidas = {"nome", "cpf", "email", "latitude", "longitude", "logradouro"}
    for col in out.columns:
        assert col.lower() not in proibidas


def test_gerar_relatorio_cria_arquivo_com_MAE(tmp_path, monkeypatch):
    df = _df_ultra_fake(6)
    _mock_motor_captura(monkeypatch)
    out = rodar_backtest(df)
    met = calcular_metricas_agregadas(out)
    md = materializar(out, met, tmp_path)
    assert md.exists()
    texto = md.read_text(encoding="utf-8")
    assert "MAE" in texto


# ---------------------------------------------------------------------------
# carregar_eng_corpo (BLK-VIAB-04-FU) — fixture xlsx sintetica em tmp_path
# ---------------------------------------------------------------------------


def test_carregar_eng_corpo_mapeia_schema_e_aplica_mask(tmp_path):
    """Loader casa colunas por substring (acento/²), computa apm, ticket=placeholder e dropa lixo."""
    # Colunas com decoys ('Total Alunos Ativos') para provar o match nao-ambiguo de 'Alunos Totais'.
    raw = pd.DataFrame(
        {
            "ID": [1, 2, 3, 4],
            "Unidade": ["EC Alfa", "EC Beta", "EC Gama", "EC Ruim"],
            "Metragem M²": [1000.0, 2000.0, 3600.0, 0.0],  # ultima invalida (metragem 0)
            "Total Alunos Ativos": [1800, 4000, 7000, 10],
            "Alunos Totais": [2000, 4400, 7200, 12],
        }
    )
    caminho = tmp_path / "eng.xlsx"
    raw.to_excel(caminho, sheet_name="Academias", index=False)

    out = carregar_eng_corpo(caminho)

    # A linha invalida (metragem 0) foi dropada; indice resetado 0..2.
    assert len(out) == 3
    assert list(out.index) == [0, 1, 2]
    assert set(out.columns) == {
        "unidade",
        "metragem",
        "alunos_total",
        "ticket_medio_aluno",
        "alunos_por_m2",
    }
    # Mapeou 'Alunos Totais' (nao 'Total Alunos Ativos') e computou apm = alunos/metragem.
    assert out.loc[0, "alunos_total"] == 2000.0
    assert out.loc[0, "alunos_por_m2"] == pytest.approx(2.0)
    # Ticket e o placeholder (ausente na fonte).
    assert (out["ticket_medio_aluno"] == TICKET_PLACEHOLDER_ENG).all()
    # Nenhuma coluna de geo/PII propagada.
    assert not {"lat", "lng", "latitude", "longitude"} & set(out.columns)


def test_carregar_eng_corpo_saida_e_compativel_com_rodar_backtest(tmp_path, monkeypatch):
    """A base Eng entra em rodar_backtest sem colisao de schema (mesmas colunas de carregar_ultra)."""
    raw = pd.DataFrame(
        {
            "Unidade": [f"EC {i}" for i in range(6)],
            "Metragem M²": np.linspace(1000.0, 2500.0, 6),
            "Alunos Totais": np.linspace(1000.0, 2500.0, 6) * 2.2,
        }
    )
    caminho = tmp_path / "eng.xlsx"
    raw.to_excel(caminho, sheet_name="Academias", index=False)
    df_eng = carregar_eng_corpo(caminho)

    _mock_motor_captura(monkeypatch)
    out = rodar_backtest(df_eng)
    assert len(out) == len(df_eng)
    assert list(out.columns) == COLUNAS_SAIDA
