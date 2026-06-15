"""Testes BLK-DIM-02R (modelo gravitacional de Huff com validacao LOO real).

Offline, seeds fixos, sem ler parquets reais (sempre injetar `conc_df`/`base`). Coords
brasileiras reais por regiao. A funcao-nucleo `share_huff` e PURA e geometrica; os testes
travam a ausencia de vazamento (alvo nunca no previsor) e a alcancabilidade do NO-GO.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import pytest

from motor_expansao.dimensionamento import config, huff


# --------------------------------------------------------------------------- #
# Fixtures sinteticas
# --------------------------------------------------------------------------- #
@pytest.fixture
def concorrentes_sinteticos() -> pd.DataFrame:
    """~12 concorrentes OSM em 3 regioes reais (RS/SP/DF) + 1 linha NaN p/ filtro."""
    rng = np.random.default_rng(7)
    regioes = [(-30.0, -51.2), (-23.5, -46.6), (-15.8, -47.9)]
    linhas: list[dict] = []
    cid = 0
    for lat0, lng0 in regioes:
        for _ in range(4):
            linhas.append(
                {
                    "concorrente_id": f"c{cid}",
                    "rede": "rede_x",
                    "lat": lat0 + float(rng.normal(0, 0.02)),
                    "lng": lng0 + float(rng.normal(0, 0.02)),
                    "flag_coord_valida": True,
                }
            )
            cid += 1
    # 1 com coord NaN (deve ser filtrada)
    linhas.append(
        {
            "concorrente_id": "c_nan",
            "rede": "rede_y",
            "lat": float("nan"),
            "lng": float("nan"),
            "flag_coord_valida": True,
        }
    )
    # 1 com flag_coord_valida=False (deve ser filtrada)
    linhas.append(
        {
            "concorrente_id": "c_inval",
            "rede": "rede_z",
            "lat": -23.5,
            "lng": -46.6,
            "flag_coord_valida": False,
        }
    )
    return pd.DataFrame(linhas)


@pytest.fixture
def base_huff_sintetica() -> pd.DataFrame:
    """>=30 unidades, 3 marcas; alunos com DEPENDENCIA real do isolamento geometrico.

    Unidades distantes dos concorrentes recebem mais alunos (sinal detectavel de beta>0),
    + ruido. Garante classe viavel/inviavel mista.
    """
    rng = np.random.default_rng(3)
    marcas = ["ultra", "engenharia_do_corpo", "skyfit"]
    # Centros bem separados, com offsets crescentes do "cluster de concorrentes"
    # para criar gradiente de isolamento.
    base_pts = {
        "RS": (-30.0, -51.2),
        "SP": (-23.5, -46.6),
        "DF": (-15.8, -47.9),
    }
    ufs = list(base_pts)
    linhas: list[dict] = []
    for k, marca in enumerate(marcas):
        for i in range(12):
            uf = ufs[i % 3]
            lat0, lng0 = base_pts[uf]
            # offset crescente => mais isolamento => mais alunos
            offset = 0.01 + 0.04 * i
            lat = lat0 + offset + float(rng.normal(0, 0.005))
            lng = lng0 + offset + float(rng.normal(0, 0.005))
            alunos = 1200 + i * 220 + k * 60 + float(rng.normal(0, 80))
            linhas.append(
                {
                    "unidade": f"{marca}_{uf}_{i}",
                    "marca": marca,
                    "uf": uf,
                    "lat": lat,
                    "lng": lng,
                    "alunos_reais": float(max(alunos, 500.0)),
                }
            )
    return pd.DataFrame(linhas)


@pytest.fixture
def base_ruido() -> pd.DataFrame:
    """Base com alunos INDEPENDENTES da geometria -> corr LOO ~0, NO-GO esperado."""
    rng = np.random.default_rng(11)
    base_pts = {"RS": (-30.0, -51.2), "SP": (-23.5, -46.6), "DF": (-15.8, -47.9)}
    ufs = list(base_pts)
    linhas: list[dict] = []
    for i in range(36):
        uf = ufs[i % 3]
        lat0, lng0 = base_pts[uf]
        lat = lat0 + float(rng.normal(0, 0.05))
        lng = lng0 + float(rng.normal(0, 0.05))
        linhas.append(
            {
                "unidade": f"u{i}",
                "marca": ["ultra", "skyfit", "engenharia_do_corpo"][i % 3],
                "uf": uf,
                "lat": lat,
                "lng": lng,
                "alunos_reais": float(rng.uniform(800, 4000)),  # puro ruido
            }
        )
    return pd.DataFrame(linhas)


# --------------------------------------------------------------------------- #
# 1-4: share_huff puro
# --------------------------------------------------------------------------- #
def test_share_huff_pura_sem_concorrentes_eh_um() -> None:
    assert huff.share_huff(1.66, np.array([]), beta=1.5) == 1.0


def test_share_huff_cai_com_mais_concorrentes() -> None:
    poucos = huff.share_huff(1.66, np.array([0.5]), beta=1.5)
    muitos = huff.share_huff(1.66, np.array([0.5, 0.5, 0.5, 0.5]), beta=1.5)
    assert muitos < poucos
    assert 0.0 <= muitos <= 1.0


def test_share_huff_cai_com_beta_maior_quando_proprio_mais_longe() -> None:
    # propria mais LONGE (2.0) que o concorrente (0.5) -> beta maior penaliza a propria.
    s_b1 = huff.share_huff(2.0, np.array([0.5]), beta=0.5)
    s_b3 = huff.share_huff(2.0, np.array([0.5]), beta=3.0)
    assert s_b3 < s_b1


def test_share_huff_no_intervalo_0_1() -> None:
    rng = np.random.default_rng(0)
    for _ in range(200):
        beta = float(rng.uniform(0.1, 5.0))
        d_propria = float(rng.uniform(0.01, 5.0))
        n = int(rng.integers(0, 8))
        dconc = rng.uniform(0.01, 5.0, size=n)
        s = huff.share_huff(d_propria, dconc, beta=beta)
        assert 0.0 <= s <= 1.0


# --------------------------------------------------------------------------- #
# 5: haversine vetorizada
# --------------------------------------------------------------------------- #
def test_haversine_vec_bate_com_escalar() -> None:
    lat0, lng0 = -23.5, -46.6
    lats = np.array([-30.0, -15.8, -25.4])
    lngs = np.array([-51.2, -47.9, -49.2])
    vec = huff._haversine_vec(lat0, lng0, lats, lngs)
    esc = np.array(
        [huff.haversine_km(lat0, lng0, la, lo) for la, lo in zip(lats, lngs, strict=False)]
    )
    assert np.allclose(vec, esc, atol=1e-6)
    # vazio
    assert huff._haversine_vec(lat0, lng0, np.array([]), np.array([])).size == 0


# --------------------------------------------------------------------------- #
# 6: carga de concorrentes
# --------------------------------------------------------------------------- #
def test_carregar_concorrentes_filtra_nan_e_invalidos(
    concorrentes_sinteticos: pd.DataFrame,
) -> None:
    lat, lng = huff._carregar_concorrentes(conc_df=concorrentes_sinteticos)
    # 12 validos (4*3); c_nan e c_inval filtrados.
    assert lat.size == 12
    assert lng.size == 12
    assert np.all(np.isfinite(lat)) and np.all(np.isfinite(lng))


# --------------------------------------------------------------------------- #
# 7-9, 15: calibrar_huff
# --------------------------------------------------------------------------- #
def test_calibrar_huff_retorna_huffmodel_com_campos(
    base_huff_sintetica: pd.DataFrame,
    concorrentes_sinteticos: pd.DataFrame,
) -> None:
    m = huff.calibrar_huff(base_huff_sintetica, conc_df=concorrentes_sinteticos)
    assert isinstance(m, huff.HuffModel)
    assert isinstance(m.beta, float)
    assert huff.BETA_BOUNDS[0] <= m.beta <= huff.BETA_BOUNDS[1]
    assert isinstance(m.beta_ic95, tuple) and len(m.beta_ic95) == 2
    assert isinstance(m.corr_loo_share_alunos, float)
    assert isinstance(m.auc_loo_viavel, float)
    assert m.veredito in {"GO", "NO-GO"}
    assert m.n_treinamento > 0


def test_calibrar_huff_loo_sem_vazamento(
    base_huff_sintetica: pd.DataFrame,
    concorrentes_sinteticos: pd.DataFrame,
) -> None:
    """Chave anti-vazamento: alterar alunos_reais de UMA unidade NAO muda o share_loo dela.

    share_loo[i] e puramente geometrico dado beta, e o beta dela vem das OUTRAS unidades
    (LOO honesto). Spike no alvo da propria unidade nao deve poder mudar seu share -- prova
    de que o alvo nao vaza para o previsor.
    """
    lats = pd.to_numeric(base_huff_sintetica["lat"], errors="coerce").to_numpy(float)
    lngs = pd.to_numeric(base_huff_sintetica["lng"], errors="coerce").to_numpy(float)
    marcas = base_huff_sintetica["marca"].astype(str).to_numpy()
    alunos = pd.to_numeric(base_huff_sintetica["alunos_reais"], errors="coerce").to_numpy(float)
    conc_lat, conc_lng = huff._carregar_concorrentes(conc_df=concorrentes_sinteticos)

    _b, share_loo, _betas = huff._calibrar_beta_loo(lats, lngs, marcas, alunos, conc_lat, conc_lng)

    # Spike no alvo de UMA unidade (idx 0). Geometria intacta.
    alunos2 = alunos.copy()
    alunos2[0] = alunos2[0] * 1000.0
    _b2, share_loo2, _betas2 = huff._calibrar_beta_loo(
        lats, lngs, marcas, alunos2, conc_lat, conc_lng
    )

    # O share da unidade 0 nao pode mudar pelo proprio alvo: o beta dela vem das outras.
    assert np.isclose(share_loo[0], share_loo2[0], atol=1e-9, equal_nan=True)


def test_calibrar_huff_n_insuficiente_levanta(
    concorrentes_sinteticos: pd.DataFrame,
) -> None:
    base = pd.DataFrame(
        {
            "unidade": ["a", "b", "c"],
            "marca": ["ultra", "ultra", "skyfit"],
            "uf": ["SP", "SP", "RS"],
            "lat": [-23.5, -23.6, -30.0],
            "lng": [-46.6, -46.7, -51.2],
            "alunos_reais": [2000.0, 2500.0, 1800.0],
        }
    )
    with pytest.raises(ValueError, match="insuficiente"):
        huff.calibrar_huff(base, conc_df=concorrentes_sinteticos)


def test_calibrar_huff_colunas_obrigatorias(
    concorrentes_sinteticos: pd.DataFrame,
) -> None:
    base = pd.DataFrame({"lat": [-23.5], "lng": [-46.6], "alunos_reais": [2000.0]})
    with pytest.raises(ValueError, match="obrigatorias"):
        huff.calibrar_huff(base, conc_df=concorrentes_sinteticos)


def test_calibrar_huff_conta_outliers_removidos(
    base_huff_sintetica: pd.DataFrame,
    concorrentes_sinteticos: pd.DataFrame,
) -> None:
    base = base_huff_sintetica.copy()
    base.loc[0, "alunos_reais"] = np.nan  # sem alunos -> removida
    base.loc[1, "lat"] = np.nan  # sem coord -> removida
    m = huff.calibrar_huff(base, conc_df=concorrentes_sinteticos)
    assert m.n_outliers_removidos >= 2


# --------------------------------------------------------------------------- #
# 10-11, 15: veredito GO/NO-GO + indistinguivel de zero
# --------------------------------------------------------------------------- #
def test_veredito_go_quando_sinal_forte(
    base_huff_sintetica: pd.DataFrame,
    concorrentes_sinteticos: pd.DataFrame,
) -> None:
    m = huff.calibrar_huff(base_huff_sintetica, conc_df=concorrentes_sinteticos)
    # Com sinal geometrico construido, a correlacao LOO deve ser detectavel.
    assert np.isfinite(m.corr_loo_share_alunos)
    assert abs(m.corr_loo_share_alunos) >= huff.CORR_GO_MIN


def test_veredito_no_go_quando_sem_sinal(
    base_ruido: pd.DataFrame,
    concorrentes_sinteticos: pd.DataFrame,
) -> None:
    """NO-GO e alcancavel: alunos aleatorios -> IC da correlacao cruza zero -> NO-GO."""
    m = huff.calibrar_huff(base_ruido, conc_df=concorrentes_sinteticos)
    assert m.veredito == "NO-GO"
    # IC da correlacao cruza zero (sem sinal).
    lo, hi = m.corr_loo_ic95
    assert lo <= 0.0 <= hi


def test_beta_indistinguivel_de_zero_flag(
    base_ruido: pd.DataFrame,
    concorrentes_sinteticos: pd.DataFrame,
) -> None:
    m = huff.calibrar_huff(base_ruido, conc_df=concorrentes_sinteticos)
    assert m.beta_indistinguivel_de_zero is True


# --------------------------------------------------------------------------- #
# 12-14: relatorio + anti-PII + anti-predicao
# --------------------------------------------------------------------------- #
def test_relatorio_huff_sem_pii_e_secoes(
    base_huff_sintetica: pd.DataFrame,
    concorrentes_sinteticos: pd.DataFrame,
    tmp_path,
) -> None:
    m = huff.calibrar_huff(base_huff_sintetica, conc_df=concorrentes_sinteticos)
    out = tmp_path / "huff_calibracao.md"
    huff.escrever_relatorio_huff(m, path=out)
    texto = out.read_text(encoding="utf-8")
    for sec in ("## 1.", "## 2.", "## 3.", "## 4.", "## 5."):
        assert sec in texto
    assert "READ-ONLY sobre o M1" in texto
    # Nenhum token PII como palavra isolada.
    for token in config.PII_COLUNAS_PROIBIDAS:
        assert not re.search(rf"\b{re.escape(token)}\b", texto, flags=re.IGNORECASE), token


def test_relatorio_huff_nao_tem_predicao_pontual(
    base_huff_sintetica: pd.DataFrame,
    concorrentes_sinteticos: pd.DataFrame,
) -> None:
    m = huff.calibrar_huff(base_huff_sintetica, conc_df=concorrentes_sinteticos)
    texto = huff.relatorio_huff(m)
    assert huff._FRASE_GUARDRAIL in texto
    low = texto.lower()
    assert "este hex tera" not in low
    assert "alunos previstos" not in low


def test_share_huff_nao_aceita_alvo_na_assinatura() -> None:
    """Trava estrutural anti-vazamento: share_huff NAO tem parametro de alvo."""
    import inspect

    params = set(inspect.signature(huff.share_huff).parameters)
    assert "alunos_reais" not in params
    assert "alunos" not in params
    assert "y" not in params
