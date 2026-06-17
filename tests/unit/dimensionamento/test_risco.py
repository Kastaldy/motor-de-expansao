"""Testes unitarios para src/motor_expansao/dimensionamento/risco.py (BLK-DIM-14).

Cobertura:
    T1-T2  : p_viavel retorna None para base ausente/vazia
    T3     : p_viavel retorna None para coluna obrigatoria ausente
    T4     : p_viavel retorna None para alunos_por_m2 invalidos (NaN/negativo)
    T5     : p_viavel calcula fracao corretamente (base simples)
    T6     : p_viavel break_even=inf -> 0.0
    T7     : p_viavel janela de m2 estreita (tolerancia)
    T8     : p_viavel alarga janela quando N < n_min
    T9     : p_viavel NAO possui parametros lat/lng (guardrail anti-geografico)
    T10    : p_viavel filtro de formato via coluna 'marca'
    T11    : p_viavel filtro de formato fallback para base inteira quando N < n_min
    T12    : classe_risco GO/ATENCAO/NAO/INDISPONIVEL
    T13    : classe_risco fronteiras exatas dos cutoffs
    T14    : ranking_oportunidades ordena p_viavel DESC, break_even ASC, None no fim
    T15    : RANKING_ATIVO e False
    T16    : ranking_oportunidades nao referenciada em arquivos de render do dashboard
    T17    : constantes de tolerancia sao identicas as de viabilidade_ponto
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.dimensionamento.risco import (
    CUTOFF_ATENCAO,
    CUTOFF_GO,
    FAIXA_M2_TOLERANCIA,
    FAIXA_M2_TOLERANCIA_ALARGADA,
    RANKING_ATIVO,
    classe_risco,
    p_viavel,
    ranking_oportunidades,
)

# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------

def _base(alunos_por_m2: list, metragens: list | None = None, marcas: list | None = None) -> pd.DataFrame:
    """Monta DataFrame minimo de calibracao."""
    data: dict = {"alunos_por_m2": alunos_por_m2}
    if metragens is not None:
        data["metragem"] = metragens
    if marcas is not None:
        data["marca"] = marcas
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# T1-T4: p_viavel -> None para entradas invalidas
# ---------------------------------------------------------------------------

def test_t1_p_viavel_none_quando_base_none() -> None:
    assert p_viavel(1500.0, 1000.0, None) is None


def test_t2_p_viavel_none_quando_base_vazia() -> None:
    df = pd.DataFrame({"alunos_por_m2": []})
    assert p_viavel(1500.0, 1000.0, df) is None


def test_t3_p_viavel_none_sem_coluna_obrigatoria() -> None:
    df = pd.DataFrame({"metragem": [1500.0]})
    assert p_viavel(1500.0, 1000.0, df) is None


def test_t4_p_viavel_none_apm_invalidos() -> None:
    df = pd.DataFrame({"alunos_por_m2": [float("nan"), -1.0, 0.0]})
    assert p_viavel(1500.0, 1000.0, df) is None


# ---------------------------------------------------------------------------
# T5: calculo correto da fracao
# ---------------------------------------------------------------------------

def test_t5_p_viavel_fracao_simples() -> None:
    # 3 comparaveis; break_even = 1500 alunos; m2 = 1000
    # apm * m2: 0.5*1000=500 (nao), 1.5*1000=1500 (nao — >, nao >=), 2.0*1000=2000 (sim)
    df = _base([0.5, 1.5, 2.0])
    p = p_viavel(1000.0, 1500.0, df)
    assert p is not None
    # comparacao ESTRITA: apenas 2000 > 1500 -> 1/3
    assert abs(p - 1 / 3) < 1e-9


def test_t5b_p_viavel_todos_viaveis() -> None:
    df = _base([2.0, 3.0, 4.0])
    p = p_viavel(1000.0, 1000.0, df)
    # 2000>1000, 3000>1000, 4000>1000 -> 1.0
    assert p == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# T6: break_even=inf -> 0.0
# ---------------------------------------------------------------------------

def test_t6_break_even_inf_retorna_zero() -> None:
    df = _base([10.0, 20.0, 30.0])
    p = p_viavel(1000.0, float("inf"), df)
    assert p == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# T7: janela estreita de m2
# ---------------------------------------------------------------------------

def test_t7_janela_estreita_m2() -> None:
    # m2=1000, tolerancia=0.20 -> janela [800, 1200]
    # metragem 900 entra (dentro), 1500 fica fora
    df = _base(
        alunos_por_m2=[2.0, 0.1],
        metragens=[900.0, 1500.0],
    )
    p = p_viavel(1000.0, 1500.0, df, n_min=1)
    # so o comparavel 900 (apm=2.0): 2.0*1000=2000 > 1500 -> p=1.0
    assert p == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# T8: alarga janela quando N < n_min
# ---------------------------------------------------------------------------

def test_t8_alarga_janela_quando_n_abaixo_do_minimo() -> None:
    # janela estreita [1200..1800] so tem 1 item; alargada [750..2250] tem 2
    df = _base(
        alunos_por_m2=[2.0, 0.5, 0.1],
        metragens=[1500.0, 2000.0, 500.0],
    )
    # n_min=3: estreita tem 1, alargada tem 2 (1500 e 2000), ainda < 3 -> usa base inteira
    p = p_viavel(1500.0, 2500.0, df, n_min=3)
    # base inteira: 2.0*1500=3000>2500(sim), 0.5*1500=750 nao, 0.1*1500=150 nao -> 1/3
    assert p == pytest.approx(1 / 3)


def test_t8b_usa_base_inteira_quando_alargada_insuficiente() -> None:
    df = _base(
        alunos_por_m2=[2.0, 3.0],
        metragens=[500.0, 600.0],
    )
    # m2=1500: janela estreita [1200..1800] nao tem nenhum (500,600 fora)
    # janela alargada [750..2250]: tambem nao tem nenhum
    # -> usa base inteira (2 items)
    p = p_viavel(1500.0, 1000.0, df, n_min=3)
    # 2.0*1500=3000>1000 e 3.0*1500=4500>1000 -> 2/2=1.0
    assert p == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# T9: GUARDRAIL — p_viavel NAO tem parametros lat/lng
# ---------------------------------------------------------------------------

def test_t9_guardrail_antideograficou_sem_lat_lng() -> None:
    sig = inspect.signature(p_viavel)
    param_names = set(sig.parameters.keys())
    assert "lat" not in param_names, "p_viavel NAO deve aceitar 'lat' (guardrail anti-geografico)"
    assert "lng" not in param_names, "p_viavel NAO deve aceitar 'lng' (guardrail anti-geografico)"
    assert "latitude" not in param_names
    assert "longitude" not in param_names


# ---------------------------------------------------------------------------
# T10: filtro de formato via coluna 'marca'
# ---------------------------------------------------------------------------

def test_t10_filtro_formato_marca() -> None:
    df = _base(
        alunos_por_m2=[3.0, 0.1, 0.1],
        marcas=["ultra", "outro", "outro"],
    )
    # com formato="ultra": so 1 item (apm=3.0), break_even=2000, 3.0*1000=3000>2000 -> 1.0
    p = p_viavel(1000.0, 2000.0, df, formato="ultra", n_min=1)
    assert p == pytest.approx(1.0)


def test_t10b_filtro_formato_case_insensitive() -> None:
    df = _base(
        alunos_por_m2=[3.0, 0.1],
        marcas=["Ultra", "outro"],
    )
    p = p_viavel(1000.0, 2000.0, df, formato="ULTRA", n_min=1)
    assert p == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# T11: filtro de formato fallback para base inteira quando N < n_min
# ---------------------------------------------------------------------------

def test_t11_formato_fallback_base_inteira() -> None:
    # formato "ultra" teria so 2 items < n_min=3 -> fallback para base inteira (4 items)
    df = _base(
        alunos_por_m2=[3.0, 3.0, 0.1, 0.1],
        marcas=["ultra", "ultra", "outro", "outro"],
    )
    p = p_viavel(1000.0, 2500.0, df, formato="ultra", n_min=3)
    # base inteira: 3.0*1000=3000>2500(sim), 3.0*1000(sim), 0.1*1000=100 nao, 100 nao -> 2/4=0.5
    assert p == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# T12: classe_risco retorna os 4 valores esperados
# ---------------------------------------------------------------------------

def test_t12_classe_risco_go() -> None:
    assert classe_risco(1.0) == "GO"
    assert classe_risco(0.70) == "GO"


def test_t12_classe_risco_atencao() -> None:
    assert classe_risco(0.69) == "ATENCAO"
    assert classe_risco(0.40) == "ATENCAO"


def test_t12_classe_risco_nao() -> None:
    assert classe_risco(0.39) == "NAO"
    assert classe_risco(0.0) == "NAO"


def test_t12_classe_risco_indisponivel() -> None:
    assert classe_risco(None) == "INDISPONIVEL"


# ---------------------------------------------------------------------------
# T13: fronteiras exatas dos cutoffs
# ---------------------------------------------------------------------------

def test_t13_fronteiras_cutoffs() -> None:
    # CUTOFF_GO = 0.70 -> p=0.70 e GO, p=0.6999... e ATENCAO
    assert classe_risco(CUTOFF_GO) == "GO"
    assert classe_risco(CUTOFF_GO - 1e-10) == "ATENCAO"
    # CUTOFF_ATENCAO = 0.40 -> p=0.40 e ATENCAO, p=0.3999... e NAO
    assert classe_risco(CUTOFF_ATENCAO) == "ATENCAO"
    assert classe_risco(CUTOFF_ATENCAO - 1e-10) == "NAO"


# ---------------------------------------------------------------------------
# T14: ranking_oportunidades
# ---------------------------------------------------------------------------

def test_t14_ranking_ordena_p_viavel_desc() -> None:
    imoveis = [
        {"id": "A", "p_viavel": 0.30, "break_even": 1000.0},
        {"id": "B", "p_viavel": 0.80, "break_even": 1000.0},
        {"id": "C", "p_viavel": 0.55, "break_even": 1000.0},
    ]
    ranked = ranking_oportunidades(imoveis)
    assert [im["id"] for im in ranked] == ["B", "C", "A"]


def test_t14b_ranking_desempate_por_break_even_asc() -> None:
    imoveis = [
        {"id": "A", "p_viavel": 0.80, "break_even": 2000.0},
        {"id": "B", "p_viavel": 0.80, "break_even": 1000.0},
    ]
    ranked = ranking_oportunidades(imoveis)
    # mesmo p_viavel: menor break_even na frente
    assert ranked[0]["id"] == "B"


def test_t14c_ranking_none_vai_para_o_fim() -> None:
    imoveis = [
        {"id": "A", "p_viavel": None, "break_even": 500.0},
        {"id": "B", "p_viavel": 0.60, "break_even": 1000.0},
        {"id": "C", "p_viavel": None, "break_even": 1000.0},
    ]
    ranked = ranking_oportunidades(imoveis)
    assert ranked[0]["id"] == "B"
    assert {im["id"] for im in ranked[1:]} == {"A", "C"}


def test_t14d_ranking_nao_muta_lista_original() -> None:
    imoveis = [
        {"id": "A", "p_viavel": 0.20, "break_even": 1000.0},
        {"id": "B", "p_viavel": 0.90, "break_even": 1000.0},
    ]
    original_order = [im["id"] for im in imoveis]
    ranking_oportunidades(imoveis)
    assert [im["id"] for im in imoveis] == original_order


# ---------------------------------------------------------------------------
# T15: RANKING_ATIVO e False
# ---------------------------------------------------------------------------

def test_t15_ranking_ativo_false() -> None:
    assert RANKING_ATIVO is False


# ---------------------------------------------------------------------------
# T16: ranking_oportunidades nao referenciada nos renders do dashboard
# ---------------------------------------------------------------------------

def test_t16_ranking_nao_referenciado_no_dashboard() -> None:
    repo_root = Path(__file__).parent.parent.parent.parent
    arquivos_render = [
        repo_root / "src" / "motor_expansao" / "dashboard" / "pages.py",
        repo_root / "src" / "motor_expansao" / "dashboard" / "components.py",
        repo_root / "streamlit_app.py",
    ]
    for path in arquivos_render:
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        assert "ranking_oportunidades" not in content, (
            f"{path.name} NAO deve referenciar 'ranking_oportunidades' (funcao dormente)"
        )


# ---------------------------------------------------------------------------
# T17: paridade de constantes de tolerancia com viabilidade_ponto
# ---------------------------------------------------------------------------

def test_t17_paridade_constantes_tolerancia() -> None:
    """FAIXA_M2_TOLERANCIA e FAIXA_M2_TOLERANCIA_ALARGADA sao identicas em risco e viabilidade_ponto."""
    from motor_expansao.dimensionamento.viabilidade_ponto import (
        FAIXA_M2_TOLERANCIA as VP_TOLERANCIA,
    )
    from motor_expansao.dimensionamento.viabilidade_ponto import (
        FAIXA_M2_TOLERANCIA_ALARGADA as VP_TOLERANCIA_ALARGADA,
    )
    assert FAIXA_M2_TOLERANCIA == VP_TOLERANCIA, (
        f"risco.FAIXA_M2_TOLERANCIA={FAIXA_M2_TOLERANCIA} "
        f"!= viabilidade_ponto.FAIXA_M2_TOLERANCIA={VP_TOLERANCIA}"
    )
    assert FAIXA_M2_TOLERANCIA_ALARGADA == VP_TOLERANCIA_ALARGADA, (
        f"risco.FAIXA_M2_TOLERANCIA_ALARGADA={FAIXA_M2_TOLERANCIA_ALARGADA} "
        f"!= viabilidade_ponto.FAIXA_M2_TOLERANCIA_ALARGADA={VP_TOLERANCIA_ALARGADA}"
    )
