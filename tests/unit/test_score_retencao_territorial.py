"""Testes unitarios para BLK-LTV-04 — score_retencao_territorial.

Fixtures 100% sinteticas em memoria; NUNCA le parquet real (exceto o teste
mtime-M1, que apenas ESTATIA os artefatos, sem depender do conteudo). Cobre o
plano aprovado (DEC-014): schema exato, determinismo do seed, N por dobra,
NO-GO alcancavel sem excecao e SEM gerar parquet, imports proibidos, READ-ONLY
M1 por mtime, clip 0-100 e flag_extrapolacao.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from motor_expansao.lifetime import score_retencao_territorial as mod
from motor_expansao.lifetime.score_retencao_territorial import (
    ALVO,
    FEATURE_BASE,
    VERSAO_CONTRATO,
    W_CAP,
    W_RET,
    _veredito_no_go,
    calcular_score_retencao,
    run,
    validar_eixo_retencao,
)


# ---------------------------------------------------------------------------
# Helpers de fixture sintetica
# ---------------------------------------------------------------------------
def _df_calibracao_forte(n: int = 56, seed: int = 7) -> pd.DataFrame:
    """Calibracao sintetica onde score_priorizacao PREVE o alvo (sinal forte).

    Gera um sinal out-of-fold facil de recuperar -> util p/ exercitar o caminho
    GO (schema/score). `_chave_unidade` presente p/ o merge de maturidade.
    """
    rng = np.random.default_rng(seed)
    score = rng.uniform(10, 90, size=n)
    renda = rng.uniform(2000, 9000, size=n)
    conc = rng.integers(0, 8, size=n).astype(float)
    alvo = 5.0 * score + rng.normal(scale=8.0, size=n)  # forte, quase linear
    return pd.DataFrame(
        {
            "hex_id": [f"87a{i:012x}" for i in range(n)],
            "UNIDADE": [f"UNIDADE {i}" for i in range(n)],
            "_chave_unidade": [f"UNIDADE {i}" for i in range(n)],
            "score_priorizacao": score,
            "renda_per_capita": renda,
            "n_concorrentes_mapeados_1km": conc,
            ALVO: alvo,
        }
    )


def _df_calibracao_nula(n: int = 56, seed: int = 11) -> pd.DataFrame:
    """Calibracao sintetica de SINAL NULO (alvo independente das features).

    Exercita o NO-GO honesto: nenhum modelo out-of-fold supera o baseline.
    """
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "hex_id": [f"87a{i:012x}" for i in range(n)],
            "UNIDADE": [f"UNIDADE {i}" for i in range(n)],
            "_chave_unidade": [f"UNIDADE {i}" for i in range(n)],
            "score_priorizacao": rng.uniform(10, 90, size=n),
            "renda_per_capita": rng.uniform(2000, 9000, size=n),
            "n_concorrentes_mapeados_1km": rng.integers(0, 8, size=n).astype(float),
            ALVO: rng.normal(size=n),  # ruido puro
        }
    )


def _df_hexes(n: int = 100, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "hex_id": [f"87b{i:012x}" for i in range(n)],
            "score_priorizacao": rng.uniform(0, 100, size=n),
            "renda_per_capita": rng.uniform(1000, 12000, size=n),
            "n_concorrentes_mapeados_1km": rng.integers(0, 12, size=n).astype(float),
        }
    )


# ---------------------------------------------------------------------------
# Schema exato do output
# ---------------------------------------------------------------------------
def test_schema_exato_do_output():
    cal = _df_calibracao_forte()
    hexes = _df_hexes()
    out = calcular_score_retencao(hexes, cal, (FEATURE_BASE,))
    esperado = [
        "hex_id",
        "captacao_norm",
        "retencao_prevista_territorial",
        "retencao_norm",
        "w_cap",
        "w_ret",
        "score_retencao",
        "flag_extrapolacao",
        "versao_contrato",
    ]
    assert list(out.columns) == esperado
    assert out["hex_id"].dtype == object
    assert out["captacao_norm"].dtype == np.float64
    assert out["retencao_prevista_territorial"].dtype == np.float64
    assert out["retencao_norm"].dtype == np.float64
    assert out["w_cap"].dtype == np.float64
    assert out["w_ret"].dtype == np.float64
    assert out["score_retencao"].dtype == np.float64
    assert out["flag_extrapolacao"].dtype == bool
    assert (out["versao_contrato"] == VERSAO_CONTRATO).all()
    assert (out["w_cap"] == W_CAP).all()
    assert (out["w_ret"] == W_RET).all()


# ---------------------------------------------------------------------------
# Determinismo do seed (mesma entrada -> mesmo score/IC byte-a-byte)
# ---------------------------------------------------------------------------
def test_determinismo_score():
    cal = _df_calibracao_forte()
    hexes = _df_hexes()
    out1 = calcular_score_retencao(hexes, cal, (FEATURE_BASE,))
    out2 = calcular_score_retencao(hexes, cal, (FEATURE_BASE,))
    pd.testing.assert_frame_equal(out1, out2)


def test_determinismo_validacao_ic():
    cal = _df_calibracao_forte()
    r1 = validar_eixo_retencao(cal)
    r2 = validar_eixo_retencao(cal)
    m1 = r1.melhor()
    m2 = r2.melhor()
    assert m1 is not None and m2 is not None
    assert m1.r2_oof == m2.r2_oof
    assert m1.r2_ci_low == m2.r2_ci_low
    assert m1.r2_ci_high == m2.r2_ci_high
    assert m1.rho_oof == m2.rho_oof
    assert m1.rho_ci_low == m2.rho_ci_low
    assert m1.rho_ci_high == m2.rho_ci_high


# ---------------------------------------------------------------------------
# N por dobra correto (kfold 5x5 ou LOO; nenhuma dobra vazia)
# ---------------------------------------------------------------------------
def test_protocolo_kfold_para_n_grande():
    cal = _df_calibracao_forte(n=56)
    res = validar_eixo_retencao(cal)
    base = res.base_sozinho()
    assert base is not None
    assert base.protocolo == "kfold_5x5"
    assert base.n == 56


def test_protocolo_loo_para_n_pequeno():
    cal = _df_calibracao_forte(n=20)
    res = validar_eixo_retencao(cal)
    base = res.base_sozinho()
    assert base is not None
    assert base.protocolo == "loo"
    assert base.n == 20


def test_oof_predictions_sem_dobra_vazia():
    # oof cobre TODOS os pontos (cada ponto predito fora-de-fold, sem NaN).
    rng = np.random.default_rng(1)
    x = rng.uniform(size=(56, 1))
    y = (3.0 * x[:, 0] + rng.normal(scale=0.1, size=56))
    oof, proto = mod._oof_predictions(x, y)
    assert proto == "kfold_5x5"
    assert oof.shape == (56,)
    assert np.isfinite(oof).all()


# ---------------------------------------------------------------------------
# NO-GO alcancavel (sinal nulo) sem excecao E sem gerar parquet
# ---------------------------------------------------------------------------
def test_no_go_alcancavel_sem_excecao():
    cal = _df_calibracao_nula()
    res = validar_eixo_retencao(cal)
    veredito, justificativa = _veredito_no_go(res)  # NUNCA levanta
    assert veredito == "NO-GO"
    assert isinstance(justificativa, str) and justificativa


def test_run_no_go_nao_gera_parquet(tmp_path: Path):
    # Monta um root sintetico com os parquets de staging exigidos (sinal nulo).
    staging = tmp_path / "data" / "staging"
    staging.mkdir(parents=True)
    (tmp_path / "data" / "analysis").mkdir(parents=True)

    cal = _df_calibracao_nula()
    cal_disk = cal.drop(columns=["_chave_unidade"])  # run() deriva a chave
    cal_disk.to_parquet(staging / "unidade_territorio_retencao.parquet", index=False)

    growth = pd.DataFrame(
        {
            "unidade": [f"UNIDADE {i}" for i in range(len(cal))],
            "inauguracao": ["01/01/2022"] * len(cal),
        }
    )
    growth.to_parquet(staging / "growth_api_historico.parquet", index=False)

    veredito, _res = run(root=tmp_path)
    assert veredito == "NO-GO"
    # NO-GO: parquet de score NAO gerado (DEC-014 decisao 2).
    assert not (staging / "score_retencao_territorial.parquet").exists()
    # Relatorio documentando o NO-GO foi escrito.
    assert (tmp_path / "data" / "analysis" / "relatorio_score_retencao.md").exists()


# ---------------------------------------------------------------------------
# Imports proibidos em lifetime/
# ---------------------------------------------------------------------------
def test_no_extra_m1_imports():
    src = inspect.getsource(mod)
    banned = [
        "import motor_expansao.pipelines.m1",
        "from motor_expansao.pipelines.m1",
        "from motor_expansao.dashboard",
        "import motor_expansao.dashboard",
        "from motor_expansao.censo",
        "import motor_expansao.censo",
        "from motor_expansao.api",
        "import motor_expansao.api",
        "import sklearn",
        "from sklearn",
    ]
    for b in banned:
        assert b not in src, f"Import proibido detectado: {b}"


# ---------------------------------------------------------------------------
# READ-ONLY M1 por mtime dos 4 artefatos oficiais
# ---------------------------------------------------------------------------
_M1_ARTEFATOS = (
    "brasil_estrutural.parquet",
    "brasil_priorizados.parquet",
    "hexagonos_brasil_oportunidades.parquet",
    "hexagonos_brasil_dashboard.parquet",
)


def _repo_root() -> Path:
    # tests/unit/test_...py -> parents[2] = raiz do repo
    return Path(__file__).resolve().parents[2]


def test_run_readonly_m1_por_mtime():
    root = _repo_root()
    staging = root / "data" / "staging"
    artefatos = [staging / nome for nome in _M1_ARTEFATOS]
    existentes = [p for p in artefatos if p.exists()]
    if not existentes:
        pytest.skip("artefatos M1 oficiais nao presentes no ambiente")
    antes = {p: p.stat().st_mtime_ns for p in existentes}
    run(root=root)  # roda de verdade sobre os parquets reais
    depois = {p: p.stat().st_mtime_ns for p in existentes}
    for p in existentes:
        assert antes[p] == depois[p], f"artefato M1 alterado (mtime): {p}"


# ---------------------------------------------------------------------------
# clip 0-100 e flag_extrapolacao em fixture com feature fora do envelope
# ---------------------------------------------------------------------------
def test_clip_0_100():
    cal = _df_calibracao_forte()
    hexes = _df_hexes(n=200)
    out = calcular_score_retencao(hexes, cal, (FEATURE_BASE,))
    assert (out["score_retencao"] >= 0.0).all()
    assert (out["score_retencao"] <= 100.0).all()
    assert (out["retencao_norm"] >= 0.0).all()
    assert (out["retencao_norm"] <= 100.0).all()


def test_flag_extrapolacao_marca_fora_do_envelope():
    cal = _df_calibracao_forte()
    # Um hex com score_priorizacao muito acima do envelope de calibracao.
    hexes = pd.DataFrame(
        {
            "hex_id": ["87b000000000000", "87b000000000001"],
            "score_priorizacao": [50.0, 9999.0],  # 2o hex fora do [q05,q95]
            "renda_per_capita": [5000.0, 5000.0],
            "n_concorrentes_mapeados_1km": [2.0, 2.0],
        }
    )
    out = calcular_score_retencao(hexes, cal, (FEATURE_BASE,))
    flags = dict(zip(out["hex_id"], out["flag_extrapolacao"], strict=True))
    assert flags["87b000000000001"] is np.True_ or bool(flags["87b000000000001"]) is True
    assert bool(flags["87b000000000000"]) is False


# ---------------------------------------------------------------------------
# nao muta o input
# ---------------------------------------------------------------------------
def test_nao_muta_inputs():
    cal = _df_calibracao_forte()
    hexes = _df_hexes()
    cal_copy = cal.copy()
    hexes_copy = hexes.copy()
    calcular_score_retencao(hexes, cal, (FEATURE_BASE,))
    pd.testing.assert_frame_equal(cal, cal_copy)
    pd.testing.assert_frame_equal(hexes, hexes_copy)
