"""Testes BLK-DIM-08 (teste discriminativo do mercado residual).

Offline, seeds fixos, sem censo/xlsx reais. Fixtures sinteticas montam JA as colunas
que `validar_raio_variavel`/`derivar_densidade_marca_propria` produziriam, entao os
Testes B/C/sanidade entram direto sem IO. Coords brasileiras reais por macro-regiao.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from motor_expansao.dimensionamento import residual_discriminacao as rd


# --------------------------------------------------------------------------- #
# Fixtures sinteticas
# --------------------------------------------------------------------------- #
@pytest.fixture
def base_sintetica() -> pd.DataFrame:
    """30 unidades (10/marca), 3 macro-regioes, residual correlacionado com viabilidade."""
    rng = np.random.default_rng(0)
    marcas = ["ultra", "engenharia_do_corpo", "skyfit"]
    # (uf, lat, lng) por regiao
    regioes = {
        "Sul": ("RS", -30.0, -51.2),
        "Sudeste": ("SP", -23.5, -46.6),
        "CO_Norte": ("DF", -15.8, -47.9),
    }
    reg_keys = list(regioes)
    linhas: list[dict] = []
    for k, marca in enumerate(marcas):
        for i in range(10):
            reg = reg_keys[i % 3]
            uf, lat0, lng0 = regioes[reg]
            lat = lat0 + float(rng.normal(0, 0.05))
            lng = lng0 + float(rng.normal(0, 0.05))
            # alunos de 800 a 5000, com tendencia por indice
            alunos = 800 + i * 420 + k * 80 + float(rng.normal(0, 120))
            alunos = float(max(alunos, 500.0))
            # residual correlacionado positivamente (fraco-moderado) com alunos + ruido
            residual = max(0.0, (alunos - 1500.0) / 50.0 + float(rng.normal(0, 8.0)))
            linhas.append({
                "unidade": f"{marca}_{i}",
                "marca": marca,
                "uf": uf,
                "lat": lat,
                "lng": lng,
                "alunos_reais": alunos,
                "score_oportunidade_residual": residual,
                "oferta_efetiva_disponivel": residual * 10.0,
                "renda_per_capita_hex": 3000.0 + float(rng.normal(0, 300)),
                "pop_total_hex": 8000.0 + float(rng.normal(0, 1000)),
                "pop_captacao_fixo_1p5": 9000.0 + float(rng.normal(0, 800)),
                "pop_captacao_variavel": 10000.0 + float(rng.normal(0, 800)),
                "raio_km": 1.5,
                "n_concorrentes_km2": 2.0,
                "n_mesma_marca_no_raio": int(i % 3),
                "hex_match_ok": True,
            })
    df = pd.DataFrame(linhas)
    return rd.calcular_residual_no_raio_variavel(df)


@pytest.fixture
def base_e_mercado_sinteticos() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Base de 4 unidades + mercado cujos hex_id casam (computados via h3)."""
    import h3

    coords = [(-30.0, -51.2), (-23.5, -46.6), (-15.8, -47.9), (-25.4, -49.2)]
    base = pd.DataFrame({
        "unidade": [f"u{i}" for i in range(4)],
        "marca": ["ultra", "skyfit", "engenharia_do_corpo", "ultra"],
        "uf": ["RS", "SP", "DF", "PR"],
        "lat": [c[0] for c in coords],
        "lng": [c[1] for c in coords],
        "alunos_reais": [2500, 1200, 3000, 1800],
    })
    hex_ids = [h3.latlng_to_cell(la, lo, rd.H3_RES) for la, lo in coords]
    mercado = pd.DataFrame({
        "hex_id": hex_ids,
        "score_oportunidade_residual": [5.0, 1.0, 8.0, 2.0],
        "oferta_efetiva_disponivel": [50.0, 10.0, 80.0, 20.0],
        "renda_per_capita": [3200.0, 3000.0, 3500.0, 2800.0],
        "pop_total": [9000.0, 8000.0, 10000.0, 7000.0],
    })
    return base, mercado


# --------------------------------------------------------------------------- #
# 1. Enriquecimento
# --------------------------------------------------------------------------- #
def test_enriquecer_base_shape(base_e_mercado_sinteticos):
    base, mercado = base_e_mercado_sinteticos
    out = rd.enriquecer_base_com_residual(base_df=base, mercado_df=mercado)
    for col in ("hex_id", "score_oportunidade_residual", "oferta_efetiva_disponivel",
                "hex_match_ok"):
        assert col in out.columns
    assert len(out) == 4  # todas com coord
    assert out["hex_match_ok"].sum() >= 1


def test_assert_sem_pii_no_enriquecimento(base_e_mercado_sinteticos):
    base, mercado = base_e_mercado_sinteticos
    base_pii = base.assign(nome=["a", "b", "c", "d"])
    with pytest.raises(ValueError, match="PII"):
        rd.enriquecer_base_com_residual(base_df=base_pii, mercado_df=mercado)


# --------------------------------------------------------------------------- #
# 2. flag_viavel / penetracao
# --------------------------------------------------------------------------- #
def test_flag_viavel_piso_2000():
    df = pd.DataFrame({
        "alunos_reais": [1999, 2000, 2001, np.nan],
        "pop_captacao_variavel": [10000, 10000, 10000, 10000],
    })
    out = rd.calcular_residual_no_raio_variavel(df)
    assert out["flag_viavel"].tolist() == [0, 1, 1, 0]
    assert rd.PISO_VIABILIDADE_ALUNOS == 2000


# --------------------------------------------------------------------------- #
# 3-4. Teste B
# --------------------------------------------------------------------------- #
def test_teste_b_retorna_dict_com_auc(base_sintetica):
    res = rd.teste_b_discriminacao(base_sintetica)
    for k in ("auc_residual", "auc_baseline", "delta_auc", "ic95_residual", "veredito"):
        assert k in res


def test_auc_sempre_entre_0_e_1(base_sintetica):
    res = rd.teste_b_discriminacao(base_sintetica)
    for k in ("auc_residual", "auc_baseline", "auc_penetracao_loo"):
        v = res[k]
        assert np.isnan(v) or (0.0 <= v <= 1.0)
    lo, hi = res["ic95_residual"]
    for v in (lo, hi):
        assert np.isnan(v) or (0.0 <= v <= 1.0)


def test_teste_b_classe_unica_nao_levanta():
    df = pd.DataFrame({
        "unidade": [f"u{i}" for i in range(6)],
        "marca": ["ultra"] * 6,
        "uf": ["SP"] * 6,
        "alunos_reais": [3000, 3100, 3200, 3300, 3400, 3500],  # todos viaveis
        "score_oportunidade_residual": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        "pop_captacao_fixo_1p5": [9000.0] * 6,
        "renda_per_capita_hex": [3000.0] * 6,
        "pop_captacao_variavel": [10000.0] * 6,
        "hex_match_ok": [True] * 6,
    })
    res = rd.teste_b_discriminacao(df)
    assert res["veredito"] == "INDEFINIDO"


# --------------------------------------------------------------------------- #
# 5. Teste C
# --------------------------------------------------------------------------- #
def test_teste_c_decomposicao_retorna_componentes(base_sintetica):
    res = rd.teste_c_decomposicao_variancia(base_sintetica)
    for k in ("var_explicada_regiao", "var_explicada_marca", "var_explicada_dominio",
              "coef_dominio", "metodo"):
        assert k in res
    if res["metodo"] != "indefinido":
        soma = (res["var_explicada_regiao"] + res["var_explicada_marca"]
                + res["var_explicada_dominio"])
        # componentes + residual <= 1 (cada >= -tol); soma das explicadas <= 1 + tol
        assert soma <= 1.0 + 1e-6


# --------------------------------------------------------------------------- #
# 6. Anti-circularidade LOO
# --------------------------------------------------------------------------- #
def test_guardrail_anti_circular_penetracao():
    # 3 unidades no mesmo uf com penetracoes conhecidas; checa LOO da do meio.
    df = pd.DataFrame({
        "uf": ["SP", "SP", "SP"],
        "penetracao_observada": [0.10, 0.20, 0.30],
    })
    loo = rd._penetracao_loo_por_grupo(df, "penetracao_observada", "uf")
    # unidade do meio (0.20): media das OUTRAS = (0.10 + 0.30)/2 = 0.20, NAO inclui 0.20 propria
    assert loo.iloc[1] == pytest.approx(0.20)
    # unidade 0 (0.10): (0.20 + 0.30)/2 = 0.25
    assert loo.iloc[0] == pytest.approx(0.25)
    # valor proprio NUNCA entra: para a unidade 2 (0.30) -> (0.10+0.20)/2 = 0.15
    assert loo.iloc[2] == pytest.approx(0.15)


def test_penetracao_loo_grupo_unitario_nan():
    df = pd.DataFrame({"uf": ["SP", "RJ"], "penetracao_observada": [0.1, 0.2]})
    loo = rd._penetracao_loo_por_grupo(df, "penetracao_observada", "uf")
    assert loo.isna().all()  # cada grupo tem n==1 -> sem vizinho


# --------------------------------------------------------------------------- #
# 7. Sanidade
# --------------------------------------------------------------------------- #
def test_sanidade_casos_retorna_tnr():
    # inviaveis em residual baixo, viaveis em residual alto -> TNR alto
    df = pd.DataFrame({
        "alunos_reais": [500, 600, 700, 3000, 3500, 4000],
        "score_oportunidade_residual": [0.1, 0.2, 0.3, 50.0, 60.0, 70.0],
        "pop_captacao_variavel": [10000.0] * 6,
        "hex_match_ok": [True] * 6,
    })
    san = rd.sanidade_casos(df)
    assert 0.0 <= san["true_negative_rate"] <= 1.0
    assert san["true_negative_rate"] > 0.5


# --------------------------------------------------------------------------- #
# 8. Relatorio
# --------------------------------------------------------------------------- #
def _resultado_minimo(base_sintetica) -> dict:
    return {
        "enriquecimento": {"n_com_coord": 30, "n_hex_match": 30, "n_com_alunos": 30},
        "teste_b": rd.teste_b_discriminacao(base_sintetica),
        "teste_c": rd.teste_c_decomposicao_variancia(base_sintetica),
        "sanidade": rd.sanidade_casos(base_sintetica),
        "metricas_raio": {"veredito": "raio_fixo_mantido"},
        "marcas_resumo": {"ultra": {"n": 10, "alunos_medio": 2500.0}},
    }


def test_escrever_relatorio_sem_pii(base_sintetica, tmp_path):
    res = _resultado_minimo(base_sintetica)
    out = tmp_path / "rel.md"
    rd.escrever_relatorio(res, path=out)
    txt = out.read_text(encoding="utf-8")
    import re

    from motor_expansao.dimensionamento import config
    txt_low = txt.lower()
    # PII tokens nao podem aparecer como PALAVRA isolada (substring em prose nao conta,
    # ex.: "tel" dentro de "cautela"). O guard real (`assert_sem_pii`) e por nome de coluna.
    for tok in config.PII_COLUNAS_PROIBIDAS:
        assert not re.search(rf"\b{re.escape(tok.lower())}\b", txt_low), tok
    assert "READ-ONLY sobre o M1" in txt


def test_saida_nao_tem_predicao_pontual_de_alunos(base_sintetica, tmp_path):
    res = _resultado_minimo(base_sintetica)
    out = tmp_path / "rel.md"
    rd.escrever_relatorio(res, path=out)
    txt = out.read_text(encoding="utf-8")
    assert "NUNCA previsao pontual" in txt
    assert "este hex tera" not in txt.lower()
    assert "alunos previstos" not in txt.lower()


def test_relatorio_tem_secoes_obrigatorias(base_sintetica, tmp_path):
    res = _resultado_minimo(base_sintetica)
    out = tmp_path / "rel.md"
    rd.escrever_relatorio(res, path=out)
    txt = out.read_text(encoding="utf-8")
    for sec in ("## 1.", "## 2.", "## 3.", "## 4.", "## 5."):
        assert sec in txt
    assert "Veredito GO/NO-GO" in txt
