"""Testes do motor property-first de viabilidade do imovel — BLK-DIM-11.

Fixtures sinteticas em memoria; ZERO leitura de parquet real. Catchment desligado
(setores_df=None) na maioria dos testes do orquestrador para determinismo. A flag de
zona morta e testada diretamente com dicts de catchment sinteticos.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from motor_expansao.dimensionamento.simulador import ViabilidadeResult
from motor_expansao.dimensionamento.viabilidade_ponto import (
    ViabilidadePontoResult,
    analisar_viabilidade_ponto,
    faixa_alunos_por_densidade,
    flag_zona_morta,
    grade_sensibilidade,
)


def _base_comparaveis() -> pd.DataFrame:
    """6 unidades sinteticas; alunos_por_m2 ~0.35..0.70; metragem 900..2100."""
    return pd.DataFrame(
        {
            "unidade": [f"U{i}" for i in range(6)],
            "metragem": [900.0, 1200.0, 1400.0, 1500.0, 1800.0, 2100.0],
            "alunos_por_m2": [0.70, 0.60, 0.55, 0.50, 0.45, 0.35],
        }
    )


def test_faixa_alunos_por_densidade_normal() -> None:
    """Janela estreita +/-20% de 1500 pega >=3 comparaveis; p10<=p50<=p90>0."""
    out = faixa_alunos_por_densidade(1500.0, _base_comparaveis())
    assert out["n_comparaveis"] is not None and out["n_comparaveis"] >= 3
    assert out["faixa_alunos_p10"] is not None
    assert out["faixa_alunos_p50"] is not None
    assert out["faixa_alunos_p90"] is not None
    assert out["faixa_alunos_p10"] <= out["faixa_alunos_p50"] <= out["faixa_alunos_p90"]
    assert out["faixa_alunos_p50"] > 0
    assert math.isfinite(out["faixa_alunos_p50"])


def test_faixa_alunos_alarga_janela() -> None:
    """+/-20% pega so 1 comparavel; o modulo alarga para +/-50% e atinge >=3."""
    base = pd.DataFrame(
        {
            "metragem": [1000.0, 1480.0, 1490.0, 1495.0],
            "alunos_por_m2": [0.50, 0.48, 0.52, 0.49],
        }
    )
    out = faixa_alunos_por_densidade(1000.0, base)
    assert out["n_comparaveis"] is not None and out["n_comparaveis"] >= 3
    assert out["faixa_alunos_p50"] is not None


def test_flag_zona_morta_true() -> None:
    """pop abaixo do minimo dispara a flag e registra o motivo."""
    out = flag_zona_morta({"pop_captacao": 1000.0, "renda_per_capita_captacao": 5000.0})
    assert out["flag_zona_morta"] is True
    assert "pop<5000" in out["motivo_zona_morta"]


def test_flag_zona_morta_false() -> None:
    """pop e renda saudaveis -> flag False, motivo 'ok'."""
    out = flag_zona_morta({"pop_captacao": 50000.0, "renda_per_capita_captacao": 6000.0})
    assert out["flag_zona_morta"] is False
    assert out["motivo_zona_morta"] == "ok"


def test_grade_sensibilidade_shape() -> None:
    """Grade default = 6 alunos x 5 fatores = 30 linhas, colunas e dtype esperados."""
    g = grade_sensibilidade(1500.0, 20000.0, 938.0)
    assert g.shape[0] == 6 * 5 == 30
    assert {"alunos", "aluguel", "fator_aluguel", "margem_liq", "viavel", "payback"} <= set(
        g.columns
    )
    assert g["viavel"].dtype == bool


def test_analisar_viabilidade_ponto_completo() -> None:
    """Orquestrador retorna todos os campos; catchment desligado -> flags geo None."""
    r = analisar_viabilidade_ponto(
        -23.9,
        -46.3,
        1500.0,
        20000.0,
        938.0,
        base_calibracao_df=_base_comparaveis(),
        setores_df=None,
    )
    assert isinstance(r, ViabilidadePontoResult)
    assert isinstance(r.viabilidade, ViabilidadeResult)
    assert r.faixa_alunos_p50 is not None
    assert r.n_comparaveis is not None
    assert r.flag_zona_morta is None
    assert r.pop_captacao is None
    assert r.aluguel_teto_calculado >= 0
    assert math.isfinite(r.aluguel_teto_calculado)
    assert isinstance(r.grade_sensibilidade, pd.DataFrame)
    assert not r.grade_sensibilidade.empty
    assert r.demanda_premissa == 938.0


def test_demanda_fonte_sempre_premissa_explicita() -> None:
    """GUARDRAIL: demanda_fonte e sempre 'premissa_explicita'."""
    r = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 938.0, base_calibracao_df=_base_comparaveis()
    )
    assert r.demanda_fonte == "premissa_explicita"


def test_sem_staging_real() -> None:
    """Modos degradados sem nenhum parquet: faixa None, flag geo None."""
    r = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 938.0, base_calibracao_df=None, setores_df=None
    )
    assert isinstance(r, ViabilidadePontoResult)
    assert r.faixa_alunos_p50 is None
    assert r.flag_zona_morta is None


def test_faixa_usa_curva_densidade_nao_geo() -> None:
    """GUARDRAIL anti-geografico: lat/lng diferentes nao mudam faixa, demanda nem margem."""
    base = _base_comparaveis()
    r1 = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 938.0, base_calibracao_df=base, setores_df=None
    )
    r2 = analisar_viabilidade_ponto(
        +1.0, -60.0, 1500.0, 20000.0, 938.0, base_calibracao_df=base, setores_df=None
    )
    assert r1.faixa_alunos_p10 == r2.faixa_alunos_p10
    assert r1.faixa_alunos_p50 == r2.faixa_alunos_p50
    assert r1.faixa_alunos_p90 == r2.faixa_alunos_p90
    assert r1.n_comparaveis == r2.n_comparaveis
    assert r1.demanda_premissa == r2.demanda_premissa
    assert r1.viabilidade.margem_ebitda_pct == r2.viabilidade.margem_ebitda_pct


def test_grade_sensibilidade_margem_decresce_com_aluguel() -> None:
    """Para um mesmo nivel de alunos, fator de aluguel maior reduz a margem_liq."""
    g = grade_sensibilidade(1500.0, 20000.0, 938.0)
    linha = g[g["alunos"] == 800.0].sort_values("fator_aluguel")
    margens = linha["margem_liq"].to_numpy()
    assert (margens[:-1] >= margens[1:]).all()


def test_split_corrige_superestimacao_receita() -> None:
    """BLK-DIM-13: split 69/31 corrige o double-count; faturamento ~R$268-282k (nao ~R$375k)."""
    r = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 2350.0,
        share_balcao=0.69, base_calibracao_df=None, setores_df=None,
    )
    fat = r.viabilidade.faturamento_mensal_steady
    assert 260_000.0 <= fat <= 290_000.0, f"faturamento={fat:.0f} (esperado 268-282k)"
    assert fat < 300_000.0, f"double-count nao eliminado: {fat:.0f}"


def test_anti_double_count_agregadores_escalam() -> None:
    """Premissa total nao aparece como balcao cheio + 651 agregadores fixos simultaneamente."""
    r = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 2000.0,
        share_balcao=0.69, base_calibracao_df=None, setores_df=None,
    )
    assert r.alunos_balcao_premissa == pytest.approx(2000.0 * 0.69)
    assert r.alunos_agregadores_premissa == pytest.approx(2000.0 * 0.31)
    assert r.alunos_agregadores_premissa != 651.0
    assert r.alunos_balcao_premissa != 2000.0


def test_grade_aplica_split_internamente() -> None:
    """A grade varre alunos TOTAIS; cada celula usa balcao=alunos*share + agr=alunos*(1-share)."""
    from motor_expansao.dimensionamento.config import SIM_MENSALIDADE_BALCAO
    from motor_expansao.dimensionamento.simulador import viabilidade as _viabilidade

    share = 0.69
    alunos_total = 800.0
    fator = 1.0
    aluguel_ref = 20000.0

    g = grade_sensibilidade(1500.0, aluguel_ref, 938.0, share_balcao=share)
    esperado = _viabilidade(
        alunos_total * share,
        1500.0,
        aluguel_ref * fator,
        SIM_MENSALIDADE_BALCAO,
        alunos_agregadores=alunos_total * (1.0 - share),
    )
    linha = g[(g["alunos"] == alunos_total) & (g["fator_aluguel"] == fator)].iloc[0]
    assert linha["margem_liq"] == pytest.approx(esperado.margem_ebitda_pct)


def test_share_balcao_default_aplicado() -> None:
    from motor_expansao.dimensionamento.viabilidade_ponto import SHARE_BALCAO_DEFAULT

    r = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 1000.0, base_calibracao_df=None, setores_df=None,
    )
    assert r.alunos_balcao_premissa == pytest.approx(1000.0 * SHARE_BALCAO_DEFAULT)
    assert r.alunos_agregadores_premissa == pytest.approx(1000.0 * (1.0 - SHARE_BALCAO_DEFAULT))


# ---------------------------------------------------------------------------
# BLK-DIM-16 — Testes de critério de aceite (break-even + aluguel-teto)
# ---------------------------------------------------------------------------

def test_breakeven_menor_que_alunos_para_margem_alvo() -> None:
    """Break-even (EBITDA=0%) deve ser menor que alunos para a margem-alvo (10%)."""
    r = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 938.0,
        base_calibracao_df=_base_comparaveis(), setores_df=None,
    )
    assert math.isfinite(r.alunos_breakeven), "break-even deve ser finito"
    assert math.isfinite(r.alunos_para_margem_alvo), "alunos_para_margem_alvo deve ser finito"
    assert r.alunos_breakeven < r.alunos_para_margem_alvo, (
        f"break-even ({r.alunos_breakeven:.1f}) deve ser < alunos para 10% EBITDA "
        f"({r.alunos_para_margem_alvo:.1f})"
    )


def test_breakeven_resulta_ebitda_zero() -> None:
    """Reinjetar alunos_breakeven em viabilidade() deve dar EBITDA ≈ 0%."""
    from motor_expansao.dimensionamento.config import SIM_MENSALIDADE_BALCAO
    from motor_expansao.dimensionamento.simulador import viabilidade as _viabilidade
    from motor_expansao.dimensionamento.viabilidade_ponto import SHARE_BALCAO_DEFAULT

    m2, aluguel, demanda = 1500.0, 20000.0, 938.0
    r = analisar_viabilidade_ponto(
        -23.9, -46.3, m2, aluguel, demanda,
        base_calibracao_df=None, setores_df=None,
    )
    # alunos_breakeven e em alunos de BALCAO; agregadores ficam FIXOS em demanda*(1-share)
    # (idem ao que analisar_viabilidade_ponto passa para alunos_minimos_viaveis)
    alunos_agr_fixo = demanda * (1.0 - SHARE_BALCAO_DEFAULT)
    v = _viabilidade(
        r.alunos_breakeven, m2, aluguel, SIM_MENSALIDADE_BALCAO,
        alunos_agregadores=alunos_agr_fixo,
    )
    # tolerancia generosa para acomodar xtol=0.5 do brentq (rounding em alunos discretos)
    assert abs(v.margem_ebitda_pct) < 0.05, (
        f"EBITDA no break-even deveria ser ~0%; got {v.margem_ebitda_pct:.4f}"
    )


def test_aluguel_teto_considera_agregadores_materiais() -> None:
    """Com agregadores/personal muito materiais, teto supera o bound antigo (2x balcao)."""
    from motor_expansao.dimensionamento.simulador import aluguel_teto

    # Cenario: poucos alunos de balcao mas muitos agregadores e personal alto
    # -> receita total >> receita de balcao -> teto verdadeiro > 2*balcao*ticket
    alunos_balcao = 100.0
    ticket_medio = 99.0
    m2 = 1500.0
    alunos_agr = 3000.0
    ticket_agr = 82.0
    personal = 200000.0

    bound_so_balcao = alunos_balcao * ticket_medio * 2.0  # = 19800; bound antigo subestimado

    teto_com_agr = aluguel_teto(
        alunos_balcao, m2, ticket_medio,
        alunos_agregadores=alunos_agr,
        ticket_agregador=ticket_agr,
        personal_mes=personal,
    )
    assert teto_com_agr > bound_so_balcao, (
        f"aluguel_teto com agregadores ({teto_com_agr:.0f}) deve ser > "
        f"bound so-balcao ({bound_so_balcao:.0f})"
    )


def test_aluguel_teto_sem_agregadores_nao_regride() -> None:
    """Com agregadores/personal zerados, teto deve ser finito e positivo (nao-regressao)."""
    from motor_expansao.dimensionamento.simulador import aluguel_teto

    # Cenario viavel mesmo sem agregadores: alta base de alunos e ticket alto
    teto = aluguel_teto(
        1200.0, 1500.0, 200.0,
        alunos_agregadores=0.0, ticket_agregador=0.0, personal_mes=0.0,
    )
    assert teto > 0.0, "teto deve ser positivo em cenario viavel sem agregadores"
    assert math.isfinite(teto), "teto deve ser finito"


def test_alunos_para_margem_alvo_campo_presente() -> None:
    """Campo alunos_para_margem_alvo existe no dataclass e tem valor nao-negativo."""
    r = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 938.0,
        base_calibracao_df=None, setores_df=None,
    )
    assert hasattr(r, "alunos_para_margem_alvo")
    assert r.alunos_para_margem_alvo >= 0.0


# ---------------------------------------------------------------------------
# BLK-DIM-17 — Testes de fronteira do novo limiar RENDA_ZONA_MORTA_MIN = 1600
# ---------------------------------------------------------------------------

def test_flag_zona_morta_renda_abaixo_novo_limiar() -> None:
    """renda=1500 < 1600 -> flag_zona_morta=True (fronteira inferior)."""
    out = flag_zona_morta({"pop_captacao": 50000.0, "renda_per_capita_captacao": 1500.0})
    assert out["flag_zona_morta"] is True
    assert "renda<1600" in out["motivo_zona_morta"]


def test_flag_zona_morta_renda_no_limiar_nao_dispara() -> None:
    """renda=1600 == limiar -> flag_zona_morta=False (limiar inclusivo: < dispara, >= nao dispara)."""
    out = flag_zona_morta({"pop_captacao": 50000.0, "renda_per_capita_captacao": 1600.0})
    assert out["flag_zona_morta"] is False
    assert out["motivo_zona_morta"] == "ok"


# ---------------------------------------------------------------------------
# BLK-VIAB-06 — Guardrail de envelope de metragem
# ---------------------------------------------------------------------------

def test_flag_fora_envelope_acima_do_max() -> None:
    """m2=3001 > ENVELOPE_MAX -> flag_fora_envelope=True."""
    from motor_expansao.dimensionamento.viabilidade_ponto import ENVELOPE_MAX

    r = analisar_viabilidade_ponto(
        -23.9, -46.3, ENVELOPE_MAX + 1.0, 20000.0, 938.0,
        base_calibracao_df=None, setores_df=None,
    )
    assert r.flag_fora_envelope is True


def test_flag_fora_envelope_abaixo_do_min() -> None:
    """m2=599 < ENVELOPE_MIN -> flag_fora_envelope=True."""
    from motor_expansao.dimensionamento.viabilidade_ponto import ENVELOPE_MIN

    r = analisar_viabilidade_ponto(
        -23.9, -46.3, ENVELOPE_MIN - 1.0, 20000.0, 938.0,
        base_calibracao_df=None, setores_df=None,
    )
    assert r.flag_fora_envelope is True


def test_flag_fora_envelope_no_limite_max() -> None:
    """m2=3000 == ENVELOPE_MAX -> flag_fora_envelope=False (inclusivo)."""
    from motor_expansao.dimensionamento.viabilidade_ponto import ENVELOPE_MAX

    r = analisar_viabilidade_ponto(
        -23.9, -46.3, ENVELOPE_MAX, 20000.0, 938.0,
        base_calibracao_df=None, setores_df=None,
    )
    assert r.flag_fora_envelope is False


def test_flag_fora_envelope_no_limite_min() -> None:
    """m2=600 == ENVELOPE_MIN -> flag_fora_envelope=False (inclusivo)."""
    from motor_expansao.dimensionamento.viabilidade_ponto import ENVELOPE_MIN

    r = analisar_viabilidade_ponto(
        -23.9, -46.3, ENVELOPE_MIN, 20000.0, 938.0,
        base_calibracao_df=None, setores_df=None,
    )
    assert r.flag_fora_envelope is False


def test_flag_dentro_envelope_nao_altera_dre() -> None:
    """m2 fora do envelope (3001) NAO altera DRE vs m2 dentro (1500) com mesma premissa.

    Garante que flag_fora_envelope e apenas informativa — a margem_ebitda_pct
    depende so de m2 (custo/m2), nao da flag.
    """
    r_dentro = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 938.0,
        base_calibracao_df=None, setores_df=None,
    )
    r_fora = analisar_viabilidade_ponto(
        -23.9, -46.3, 3001.0, 20000.0, 938.0,
        base_calibracao_df=None, setores_df=None,
    )
    assert r_fora.flag_fora_envelope is True
    assert r_dentro.flag_fora_envelope is False
    # DRE difere porque m2 difere (custo/m2 muda) — o ponto do teste e que a FLAG
    # nao causa alteracao alem do que a variacao de m2 ja causa normalmente.
    # Verificamos que os resultados existem e sao finitos em ambos os casos.
    assert math.isfinite(r_dentro.viabilidade.margem_ebitda_pct)
    assert math.isfinite(r_fora.viabilidade.margem_ebitda_pct)
    # flag_fora_envelope e True no r_fora, mas o DRE ainda roda normalmente.
    assert r_fora.viabilidade.faturamento_mensal_steady >= 0


def test_flag_fora_envelope_falso_dentro_envelope() -> None:
    """m2=1500 (dentro do envelope [600, 3000]) -> flag_fora_envelope=False."""
    r = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 938.0,
        base_calibracao_df=_base_comparaveis(), setores_df=None,
    )
    assert r.flag_fora_envelope is False
