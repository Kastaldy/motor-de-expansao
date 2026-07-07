"""Testes do BLK-ATR-03: estrutura de leitura da atratividade (matriz vs composto).

Fixtures 100% SINTETICAS (zero PII, zero leitura de arquivo real; DEC-012). O determinismo vem
da seed 42; fixtures pequenas -> asserts de SINAL/VEREDITO, nao de valor exato de R2.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from motor_expansao.demanda_revelada import estrutura_funil as ef


# --------------------------------------------------------------------------- #
# Fixtures sinteticas
# --------------------------------------------------------------------------- #
def _base_gate(n: int = 400, *, seed: int = 0) -> pd.DataFrame:
    """DataFrame sintetico que PASSA o gate (pop >= 5000, renda >= 1500)."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "hex_id": [f"87abc{i:07d}ffff" for i in range(n)],
            "renda_per_capita": rng.uniform(1800.0, 6000.0, n),
            "populacao_corte_hex": rng.uniform(6000.0, 30000.0, n),
            "uf": rng.choice(["SP", "RJ", "MG"], n),
        }
    )


def _df_sinal_forte(n: int = 400, *, seed: int = 42) -> pd.DataFrame:
    """Fixture onde os 3 eixos combinados carregam sinal complementar sobre membros."""
    rng = np.random.default_rng(seed)
    df = _base_gate(n, seed=seed)
    socio = rng.uniform(0, 100, n)
    merc = rng.uniform(0, 100, n)
    share = rng.uniform(0.2, 1.0, n)  # 1-share e o eixo disputa
    df["score_priorizacao"] = socio
    df["score_oportunidade_residual"] = merc
    df["share_captura_huff"] = share
    df["score_setor_2022_calibrado"] = rng.uniform(0, 100, n)
    # membros depende dos 3 eixos (complementar) + ruido pequeno -> composto vence eixo isolado.
    linear = 0.9 * socio + 0.9 * merc + 40.0 * (1.0 - share)
    df["membros"] = np.clip(linear + rng.normal(0, 8, n), 0, None).round()
    return df


def _df_redundante(n: int = 400, *, seed: int = 7) -> pd.DataFrame:
    """Fixture onde 1 eixo domina e os outros sao ruido -> composto ~ melhor eixo (redundante)."""
    rng = np.random.default_rng(seed)
    df = _base_gate(n, seed=seed)
    socio = rng.uniform(0, 100, n)
    df["score_priorizacao"] = socio
    df["score_oportunidade_residual"] = rng.uniform(0, 100, n)  # ruido
    df["share_captura_huff"] = np.full(n, 1.0)  # monopolio total -> disputa = 0
    df["score_setor_2022_calibrado"] = rng.uniform(0, 100, n)
    df["membros"] = np.clip(2.0 * socio + rng.normal(0, 5, n), 0, None).round()
    return df


def _df_ruido(n: int = 400, *, seed: int = 3) -> pd.DataFrame:
    """Fixture onde os eixos nao tem relacao com membros -> R2_oof <= 0 (matriz)."""
    rng = np.random.default_rng(seed)
    df = _base_gate(n, seed=seed)
    df["score_priorizacao"] = rng.uniform(0, 100, n)
    df["score_oportunidade_residual"] = rng.uniform(0, 100, n)
    df["share_captura_huff"] = rng.uniform(0.2, 1.0, n)
    df["score_setor_2022_calibrado"] = rng.uniform(0, 100, n)
    df["membros"] = rng.integers(0, 500, n).astype(float)
    return df


# --------------------------------------------------------------------------- #
# Gate ATR-02
# --------------------------------------------------------------------------- #
def test_gate_atratividade_filtra():
    df = pd.DataFrame(
        {
            "hex_id": ["a", "b", "c", "d"],
            "renda_per_capita": [2000.0, 1000.0, 5000.0, 1600.0],
            "populacao_corte_hex": [8000.0, 9000.0, 3000.0, 7000.0],
        }
    )
    df_pos, meta = ef.aplicar_gate_atratividade(df)
    # a: pop ok + renda ok -> passa; b: renda<1500; c: pop<5000; d: pop ok + renda ok -> passa
    assert set(df_pos["hex_id"]) == {"a", "d"}
    assert meta["n_pre_gate"] == 4
    assert meta["n_pos_gate"] == 2


def test_gate_computa_populacao_corte_inline():
    # Sem populacao_corte_hex: usa pop_total (municipal) por fallback.
    df = pd.DataFrame(
        {
            "hex_id": ["a", "b"],
            "renda_per_capita": [2000.0, 2000.0],
            "pop_total": [9000.0, 1000.0],
        }
    )
    df_pos, meta = ef.aplicar_gate_atratividade(df)
    assert set(df_pos["hex_id"]) == {"a"}
    assert meta["n_pos_gate"] == 1


# --------------------------------------------------------------------------- #
# Normalizacao dos eixos
# --------------------------------------------------------------------------- #
def test_normalizacao_0_100():
    df = _df_sinal_forte(60)
    out = ef.normalizar_eixos(df)
    for col in (ef.FEAT_SOCIODEMO, ef.FEAT_MERCADO, ef.FEAT_DISPUTA):
        vals = out[col].to_numpy()
        assert np.nanmin(vals) >= 0.0
        assert np.nanmax(vals) <= 100.0


def test_share_invertido_flag_huff():
    df = _base_gate(5)
    df["score_priorizacao"] = [10, 20, 30, 40, 50]
    df["score_oportunidade_residual"] = [10, 20, 30, 40, 50]
    df["share_captura_huff"] = [1.0, 0.5, 1.0, 0.3, 0.8]
    df["membros"] = [1, 2, 3, 4, 5]
    out = ef.normalizar_eixos(df)
    flag = out["flag_huff_disponivel"].to_numpy()
    assert list(flag) == [False, True, False, True, True]
    # 1-share: menor share (0.3) -> maior disputa -> maior percentil.
    disputa = out[ef.FEAT_DISPUTA].to_numpy()
    assert disputa[3] == max(disputa)  # share 0.3 e o menor -> disputa maxima


# --------------------------------------------------------------------------- #
# Vereditos
# --------------------------------------------------------------------------- #
def test_composto_go_quando_sinal_complementar():
    res = ef.avaliar_estrutura_funil(_df_sinal_forte(500))
    assert res.veredito == "GO-composto"
    assert res.go is True
    assert res.redundante is False
    assert res.modelos["composto"].r2_oof > res.r2_melhor_eixo


def test_no_go_quando_redundante():
    res = ef.avaliar_estrutura_funil(_df_redundante(500))
    # composto ~ melhor eixo (socio domina) -> matriz por redundancia OU ganho insuficiente.
    assert res.veredito == "matriz"
    assert res.go is False


def test_no_go_quando_ruido():
    res = ef.avaliar_estrutura_funil(_df_ruido(500))
    assert res.veredito == "matriz"
    assert res.modelos["composto"].r2_oof <= ef.LIMIAR_R2_GO or res.modelos["composto"].ic95_r2[0] <= 0.0


def test_r2_insample_fora_do_veredito():
    # Mesmo com R2_insample potencialmente alto, R2_oof de ruido -> matriz.
    res = ef.avaliar_estrutura_funil(_df_ruido(500))
    comp = res.modelos["composto"]
    # in-sample existe como auditoria, mas o veredito e matriz apesar disso.
    assert np.isfinite(comp.r2_insample)
    assert res.veredito == "matriz"


# --------------------------------------------------------------------------- #
# DEC-009: membros nunca e feature
# --------------------------------------------------------------------------- #
def test_membros_nunca_feature():
    res = ef.avaliar_estrutura_funil(_df_sinal_forte(300))
    for m in res.modelos.values():
        for feat in m.features:
            assert "membros" not in feat.lower()
    for feat in res.coefs_composto:
        assert "membros" not in feat.lower()


# --------------------------------------------------------------------------- #
# Relatorio sem PII
# --------------------------------------------------------------------------- #
def test_relatorio_sem_pii():
    res = ef.avaliar_estrutura_funil(_df_sinal_forte(300))
    texto = ef.relatorio_estrutura_funil(res)
    # nao deve levantar
    ef._assert_sem_pii_no_relatorio(texto)
    assert "BLK-ATR-03" in texto
    assert ef._ROTULO_INSAMPLE in texto


# --------------------------------------------------------------------------- #
# Censitario ausente gracioso
# --------------------------------------------------------------------------- #
def test_censitario_ausente_gracioso():
    df = _df_sinal_forte(300)
    df = df.drop(columns=["score_setor_2022_calibrado"])
    res = ef.avaliar_estrutura_funil(df)
    assert "censitario" not in res.modelos  # sem eixo de auditoria, sem exceção
    assert res.veredito in {"GO-composto", "matriz"}


# --------------------------------------------------------------------------- #
# Fallback LOO
# --------------------------------------------------------------------------- #
def test_fallback_loo():
    res = ef.avaliar_estrutura_funil(_df_sinal_forte(25))
    assert res.metodo_validacao == "loo"
    assert res.flag_extrapolacao_padrao_global is True


# --------------------------------------------------------------------------- #
# Colunas obrigatorias
# --------------------------------------------------------------------------- #
def test_colunas_obrigatorias_ausentes_levanta():
    df = _df_sinal_forte(50).drop(columns=["share_captura_huff"])
    with pytest.raises(ValueError, match="obrigatorias"):
        ef.avaliar_estrutura_funil(df)


def test_gate_sem_viavel_levanta():
    df = _df_sinal_forte(50)
    df["renda_per_capita"] = 100.0  # todos abaixo do piso
    with pytest.raises(ValueError, match="viavel"):
        ef.avaliar_estrutura_funil(df)


# --------------------------------------------------------------------------- #
# Determinismo (seed)
# --------------------------------------------------------------------------- #
def test_determinismo_seed():
    df = _df_sinal_forte(300)
    r1 = ef.avaliar_estrutura_funil(df)
    r2 = ef.avaliar_estrutura_funil(df)
    assert r1.modelos["composto"].r2_oof == r2.modelos["composto"].r2_oof
    assert r1.veredito == r2.veredito
