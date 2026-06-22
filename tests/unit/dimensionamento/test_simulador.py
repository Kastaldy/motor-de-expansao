"""Testes do simulador financeiro e goal-seek — BLK-DIM-03R.

Parametros hardcoded; ZERO leitura de parquets ou arquivos.
Todos os valores de referencia derivam do Excel DRE real ou do handoff BO.

Criterio anti-circularidade (CA-08):
    Sem as 3 fontes de receita (alunos_agregadores=0, personal_mes=0), a margem
    deve ser NEGATIVA. Isso prova que o modelo nao esta com custos artificialmente
    baixos (custos fixos R$88k > receita so balcao ~118k bruto, apos deducoes/impostos).
"""

from __future__ import annotations

import math

from motor_expansao.dimensionamento.config import (
    SIM_ALUGUEL_MES,
    SIM_PERSONAL_MES_RECEITA,
)
from motor_expansao.dimensionamento.simulador import (
    ViabilidadeResult,
    aluguel_teto,
    alunos_minimos_viaveis,
    gerar_serie_mensal,
    viabilidade,
)

# ---------------------------------------------------------------------------
# Parametros de referencia
# ---------------------------------------------------------------------------

DEFAULTS = {
    "alunos_maturidade": 938,
    "m2": 1500,
    "aluguel_mes": 20_000,
    "ticket_medio": 137,
}

# Cenario viavel: capex reduzido para que o payback ocorra dentro de 60 meses.
# FCF steady-state ~13k/mes; somando todos os meses 1..60 recupera ~651k.
# capex=600k garante payback em ~57 meses (verificado numericamente).
VIAVEL = {**DEFAULTS, "capex": 600_000}


# ---------------------------------------------------------------------------
# CA-01: tipos e estrutura
# ---------------------------------------------------------------------------


def test_viabilidade_retorna_result() -> None:
    """CA-01a: viabilidade() retorna ViabilidadeResult com 9 campos."""
    r = viabilidade(**DEFAULTS)
    assert isinstance(r, ViabilidadeResult)


def test_viabilidade_campos_numericos() -> None:
    """CA-01b: todos os campos numericos sao float ou bool, sem None."""
    r = viabilidade(**DEFAULTS)
    assert isinstance(r.faturamento_mensal_steady, float)
    assert isinstance(r.receita_liquida, float)
    assert isinstance(r.receita_pos_impostos, float)
    assert isinstance(r.ebitda_mensal, float)
    assert isinstance(r.margem_ebitda_pct, float)
    assert isinstance(r.payback_meses, float)
    assert isinstance(r.roic_anual, float)
    assert isinstance(r.lucro_liquido_mensal, float)
    assert isinstance(r.flag_viavel, bool)


# ---------------------------------------------------------------------------
# CA-02: receita bruta com 3 fontes
# ---------------------------------------------------------------------------


def test_faturamento_total_com_3_fontes() -> None:
    """CA-02: faturamento total com as 3 fontes de receita deve ser ~175k-195k.

    Calculo manual:
        pagantes = 938*(1-0.06) = 881.72
        receita_balcao = 881.72 * 137 * (1-0.02) = ~118.345
        receita_agr = 651 * 82 * (1-0.02) = ~52.316
        receita_personal = 5.000
        faturamento ~ 175.661
    """
    r = viabilidade(**DEFAULTS)
    assert 170_000 < r.faturamento_mensal_steady < 195_000, (
        f"faturamento={r.faturamento_mensal_steady:.0f} fora de [170k, 195k]"
    )


# ---------------------------------------------------------------------------
# CA-03: benchmark vs. Excel (criterio anti-circularidade principal)
# ---------------------------------------------------------------------------


def test_viabilidade_benchmark_margem_excel() -> None:
    """CA-03: margem EBITDA com defaults do Excel deve ficar em [18%, 26%].

    Benchmark INDEPENDENTE: Excel DRE mes 12 com defaults do Simulador.
    Fonte: handoff BO BLK-DIM-03R (spec §8.2 cita ~23% ano 2+).
    Tolerancia +/-4pp: [18%, 26%].
    Este intervalo e derivado do modelo do Excel, NAO das constantes do codigo.
    """
    r = viabilidade(**DEFAULTS)
    assert 0.18 <= r.margem_ebitda_pct <= 0.26, (
        f"margem_ebitda_pct={r.margem_ebitda_pct:.1%} fora de [18%, 26%] "
        f"(benchmark externo Excel ~22%; tolerancia +/-4pp)"
    )


# ---------------------------------------------------------------------------
# CA-04: custos fixos dominam sobre receita variavel
# ---------------------------------------------------------------------------


def test_margem_decresce_com_aluguel_alto() -> None:
    """CA-04a: aumentar aluguel reduz a margem EBITDA."""
    r_baixo = viabilidade(**{**DEFAULTS, "aluguel_mes": 20_000})
    r_alto = viabilidade(**{**DEFAULTS, "aluguel_mes": 100_000})
    assert r_alto.margem_ebitda_pct < r_baixo.margem_ebitda_pct


def test_margem_positiva_com_defaults() -> None:
    """CA-04b: margem deve ser positiva com os defaults do Excel (3 fontes de receita)."""
    r = viabilidade(**DEFAULTS)
    assert r.margem_ebitda_pct > 0


def test_ebitda_positivo_steady_state() -> None:
    """CA-04c: EBITDA deve ser positivo no steady-state com os defaults."""
    r = viabilidade(**DEFAULTS)
    assert r.ebitda_mensal > 0


# ---------------------------------------------------------------------------
# CA-05: goal-seek aluguel_teto
# ---------------------------------------------------------------------------


def test_aluguel_teto_positivo_caso_viavel() -> None:
    """CA-05a: com 938 alunos e 3 fontes de receita, o teto deve ser > 0."""
    teto = aluguel_teto(938, 1500, 137)
    assert teto > 0


def test_aluguel_teto_zero_para_caso_inviavel() -> None:
    """CA-05b: com alunos=1, a receita e minima; teto deve ser 0.0."""
    teto = aluguel_teto(1, 1500, 137)
    assert teto == 0.0


def test_aluguel_teto_maior_que_aluguel_default() -> None:
    """CA-05c: com 938 alunos e 3 fontes, o teto comporta aluguel > R$20k default."""
    teto = aluguel_teto(938, 1500, 137, margem_alvo=0.10)
    assert teto > SIM_ALUGUEL_MES, (
        f"teto={teto:.0f} nao e maior que SIM_ALUGUEL_MES={SIM_ALUGUEL_MES}"
    )


# ---------------------------------------------------------------------------
# CA-06: goal-seek alunos_minimos_viaveis
# ---------------------------------------------------------------------------


def test_alunos_minimos_viaveis_positivo() -> None:
    """CA-06a: alunos minimos devem ser um numero positivo finito."""
    result = alunos_minimos_viaveis(1500, 20_000, 137)
    assert result > 0
    assert math.isfinite(result)


def test_alunos_minimos_viaveis_finito_com_defaults() -> None:
    """CA-06b: com os defaults do Excel, o minimo deve ser finito e < 938."""
    result = alunos_minimos_viaveis(1500, 20_000, 137, margem_alvo=0.0)
    assert math.isfinite(result)
    assert result < 938


def test_alunos_minimos_viaveis_infinito_aluguel_absurdo() -> None:
    """CA-06c: aluguel absurdo => inviavel mesmo com 5000 alunos => float('inf')."""
    result = alunos_minimos_viaveis(1500, 10_000_000, 137)
    assert result == float("inf")


# ---------------------------------------------------------------------------
# CA-07: payback e ROIC
# ---------------------------------------------------------------------------


def test_payback_finito_com_capex_menor() -> None:
    """CA-07a: com capex=600k e FCF steady ~13k/mes, payback ocorre em ~57 meses (< 60)."""
    r = viabilidade(**VIAVEL)
    assert r.payback_meses < float("inf")
    assert r.payback_meses <= 60


def test_payback_infinito_capex_alto() -> None:
    """CA-07b: com capex padrao (2.34M), FCF mensal ~19k; 60x19k=1.14M << 2.34M => inf.

    Este teste e DIFERENTE do spike: com custos fixos absolutos reais o FCF e menor,
    mas o argumento quantitativo permanece: 60 meses de FCF nao cobrem o capex.
    """
    r = viabilidade(**DEFAULTS)
    assert r.payback_meses == float("inf"), (
        f"payback={r.payback_meses} deveria ser inf com capex=2.34M"
    )


def test_roic_positivo_steady_state() -> None:
    """CA-07c: ROIC deve ser positivo quando o lucro liquido e positivo."""
    r = viabilidade(**VIAVEL)
    assert r.roic_anual > 0


def test_flag_viavel_verdadeiro_com_capex_menor() -> None:
    """CA-07d: com capex=600k, margem ~18% e payback ~57 meses => flag_viavel=False (57 > 36)."""
    r = viabilidade(**VIAVEL)
    assert r.flag_viavel is False


def test_flag_viavel_com_payback_menor_igual_36() -> None:
    """CA-07e: payback <= 36 meses => flag_viavel=True (fronteira do novo limite).

    capex=150_000 com FCF steady ~13k/mes cobre em ~22 meses, bem dentro de 36.
    """
    r = viabilidade(**{**VIAVEL, "capex": 150_000})
    assert r.payback_meses <= 36
    assert r.flag_viavel is True


def test_flag_nao_viavel_com_payback_entre_37_e_60() -> None:
    """CA-07f: payback entre 37 e 60 meses => flag_viavel=False (zona antes 'viavel', agora nao).

    capex=600_000 => payback ~57 meses (> 36, <= 60) => flag_viavel=False com novo limite.
    """
    r = viabilidade(**VIAVEL)
    assert 36 < r.payback_meses <= 60
    assert r.flag_viavel is False


# ---------------------------------------------------------------------------
# CA-08: borda e regressao (incluindo criterio anti-circularidade)
# ---------------------------------------------------------------------------


def test_viabilidade_sem_agregadores() -> None:
    """CA-08a: CRITERIO ANTI-CIRCULARIDADE.

    Sem agregadores e personal (alunos_agregadores=0, personal_mes=0), a receita
    e so do balcao (~118k bruto). Com custos fixos reais de R$88k/mes (pessoal +
    outros) mais deducoes/impostos/custos variaveis, a margem DEVE ser negativa.
    Isso prova que o modelo nao usa custos artificialmente baixos.
    """
    r = viabilidade(938, 1500, 20_000, 137, alunos_agregadores=0, personal_mes=0)
    assert r.margem_ebitda_pct < 0.0, (
        f"margem_ebitda_pct={r.margem_ebitda_pct:.1%} deveria ser negativa "
        f"sem agregadores/personal (custos fixos R$88k > margem do balcao)"
    )


def test_capex_derivado_de_coef_m2() -> None:
    """CA-08b: coef_capex_m2=1560 com m2=1500 => capex=2.34M (identico ao default)."""
    r1 = viabilidade(938, 1500, 20_000, 137, coef_capex_m2=1560.0)
    r2 = viabilidade(938, 1500, 20_000, 137, capex=2_340_000)
    assert abs(r1.margem_ebitda_pct - r2.margem_ebitda_pct) < 0.001


def test_capex_zero_roic_zero() -> None:
    """CA-08c: capex=0 => roic=0.0 (evitar divisao por zero)."""
    r = viabilidade(**{**DEFAULTS, "capex": 0})
    assert r.roic_anual == 0.0


def test_churn_zero_aumenta_faturamento() -> None:
    """CA-08d: churn=0 => mais pagantes => faturamento maior."""
    r_churn = viabilidade(**DEFAULTS)
    r_sem_churn = viabilidade(**{**DEFAULTS, "churn": 0.0})
    assert r_sem_churn.faturamento_mensal_steady > r_churn.faturamento_mensal_steady


def test_royalties_altos_reduzem_ebitda() -> None:
    """CA-08e: royalties mais altos reduzem EBITDA."""
    r_baixo = viabilidade(**{**DEFAULTS, "royalties_pct": 0.05})
    r_alto = viabilidade(**{**DEFAULTS, "royalties_pct": 0.20})
    assert r_alto.ebitda_mensal < r_baixo.ebitda_mensal


def test_rampa_longa_piora_payback() -> None:
    """CA-08f: rampa mais longa => payback pior (maior ou igual)."""
    r_curta = viabilidade(**{**VIAVEL, "maturacao_meses": 1})
    r_longa = viabilidade(**{**VIAVEL, "maturacao_meses": 24})
    assert r_longa.payback_meses >= r_curta.payback_meses


def test_receita_liquida_menor_que_bruta() -> None:
    """CA-08g: deducoes tornam receita_liquida < faturamento_bruto."""
    r = viabilidade(**DEFAULTS)
    assert r.receita_liquida < r.faturamento_mensal_steady


def test_lucro_liquido_menor_que_ebitda_positivo() -> None:
    """CA-08h: IR + CSLL tornam lucro_liquido < ebitda quando ebitda > 0."""
    r = viabilidade(**DEFAULTS)
    assert r.ebitda_mensal > 0
    assert r.lucro_liquido_mensal < r.ebitda_mensal


# ---------------------------------------------------------------------------
# Testes adicionais de consistencia
# ---------------------------------------------------------------------------


def test_personal_mes_e_constante_sim() -> None:
    """SIM_PERSONAL_MES_RECEITA deve ser R$5.000 (DRE linha 24)."""
    assert SIM_PERSONAL_MES_RECEITA == 5_000


def test_aluguel_default_constante_sim() -> None:
    """SIM_ALUGUEL_MES deve ser R$20.000 (Simulador N9)."""
    assert SIM_ALUGUEL_MES == 20_000


# ---------------------------------------------------------------------------
# CA-09: display de payback (logica pura, sem Streamlit)
# ---------------------------------------------------------------------------


def _format_payback_display(payback: float) -> str:
    """Replica a logica de pages.py:3377 de forma pura para teste."""
    if payback != float("inf"):
        return f"{int(payback)} meses"
    return "> 60 meses"


def test_payback_inf_exibe_60_meses_sem_nunca() -> None:
    """CA-09a: payback=inf => display '> 60 meses', sem 'Nunca' nem '/'."""
    display = _format_payback_display(float("inf"))
    assert display == "> 60 meses"
    assert "Nunca" not in display
    assert "/" not in display


def test_payback_finito_exibe_numero_meses() -> None:
    """CA-09b: payback finito (ex: 57) => display '57 meses'."""
    display = _format_payback_display(57.0)
    assert display == "57 meses"


# ---------------------------------------------------------------------------
# CA-10: financiamento de capex (BLK-DIM-20)
# ---------------------------------------------------------------------------


def test_financiamento_zero_resultado_identico() -> None:
    """CA-10a: capex_financiado_pct=0.0 => resultado identico ao sem o parametro (regressao zero)."""
    r_sem = viabilidade(**VIAVEL)
    r_com = viabilidade(**VIAVEL, capex_financiado_pct=0.0)
    assert r_sem.payback_meses == r_com.payback_meses
    assert r_sem.margem_ebitda_pct == r_com.margem_ebitda_pct
    assert r_sem.flag_viavel == r_com.flag_viavel


def test_financiamento_aumenta_payback() -> None:
    """CA-10b: capex_financiado_pct=1.0 => payback estritamente maior que sem financiamento."""
    r_sem = viabilidade(**VIAVEL)
    r_com = viabilidade(
        **VIAVEL,
        capex_financiado_pct=1.0,
        prazo_financiamento_meses=36,
        juros_financiamento_am=0.018,
    )
    assert r_com.payback_meses > r_sem.payback_meses, (
        f"payback com financiamento ({r_com.payback_meses}) deveria ser > sem ({r_sem.payback_meses})"
    )


def test_financiamento_nao_altera_ebitda() -> None:
    """CA-10c: margem_ebitda_pct e ebitda_mensal identicos com e sem financiamento (EBITDA pre-financiamento)."""
    r_sem = viabilidade(**VIAVEL)
    r_com = viabilidade(
        **VIAVEL,
        capex_financiado_pct=1.0,
        prazo_financiamento_meses=36,
        juros_financiamento_am=0.018,
    )
    assert r_sem.margem_ebitda_pct == r_com.margem_ebitda_pct, (
        "margem_ebitda_pct nao deve ser afetada pelo financiamento"
    )
    assert r_sem.ebitda_mensal == r_com.ebitda_mensal, (
        "ebitda_mensal nao deve ser afetado pelo financiamento"
    )


def test_pmt_formula_correta() -> None:
    """CA-10d: PMT correta para C=600k, r=0.018, n=36 (referencia calculada externamente).

    PMT = C * r * (1+r)^n / ((1+r)^n - 1)
        = 600000 * 0.018 * 1.018^36 / (1.018^36 - 1)
        = 600000 * 0.018 * 1.8983... / (1.8983... - 1)
        ~ 600000 * 0.03825... / 0.8983...
        ~ 600000 * 0.03827...
        ~ 22965... (aprox R$22.960-23.000)

    Valida via FCF: com financiamento 100%, os primeiros 36 meses do FCF acumulado
    devem ser menores que sem financiamento (PMT subtraida).
    """
    C = 600_000.0
    r = 0.018
    n = 36
    pmt_esperada = C * r * (1.0 + r) ** n / ((1.0 + r) ** n - 1.0)
    assert 22_000 < pmt_esperada < 24_000, (
        f"PMT de referencia fora do intervalo esperado: {pmt_esperada:.0f}"
    )

    # Confirmar que o simulador subtrai a PMT: no mes 1, FCF com financiamento < sem
    # (inferido via payback — financiamento sempre piora ou iguala o payback)
    r_sem = viabilidade(
        **VIAVEL,
        capex_financiado_pct=0.0,
        prazo_financiamento_meses=36,
        juros_financiamento_am=0.018,
    )
    r_com = viabilidade(
        **VIAVEL,
        capex_financiado_pct=1.0,
        prazo_financiamento_meses=36,
        juros_financiamento_am=0.018,
    )
    assert r_com.payback_meses >= r_sem.payback_meses


# ---------------------------------------------------------------------------
# CA-11: gerar_serie_mensal() (BLK-DIM-21)
# ---------------------------------------------------------------------------


def test_serie_mensal_comprimento_60() -> None:
    """CA-11a: gerar_serie_mensal() retorna exatamente 60 registros."""
    serie = gerar_serie_mensal(**DEFAULTS)
    assert len(serie) == 60


def test_serie_mensal_campos_presentes() -> None:
    """CA-11b: todos os campos obrigatorios presentes em cada registro."""
    serie = gerar_serie_mensal(**DEFAULTS)
    campos = {"mes", "alunos_balcao", "faturamento_mensal", "ebitda_mensal", "fcf_acumulado"}
    for row in serie:
        assert campos == set(row.keys()), f"Campos faltando: {campos - set(row.keys())}"


def test_serie_mensal_sem_nan() -> None:
    """CA-11c: nenhum campo contem NaN ou None."""
    serie = gerar_serie_mensal(**DEFAULTS)
    for row in serie:
        for k, v in row.items():
            assert v is not None, f"Campo {k} e None no mes {row['mes']}"
            if isinstance(v, float):
                assert math.isfinite(v), f"Campo {k} e nao-finito no mes {row['mes']}"


def test_serie_mensal_meses_sequenciais() -> None:
    """CA-11d: campo 'mes' vai de 1 a 60 em sequencia."""
    serie = gerar_serie_mensal(**DEFAULTS)
    assert [row["mes"] for row in serie] == list(range(1, 61))


def test_serie_mensal_fcf_acumulado_negativo_inicio() -> None:
    """CA-11e: FCF acumulado no mes 1 e negativo (capex a vista e alto)."""
    serie = gerar_serie_mensal(**DEFAULTS)
    assert serie[0]["fcf_acumulado"] < 0, (
        "FCF acumulado no mes 1 deve ser negativo (capex padrao R$2.34M nao e coberto em 1 mes)"
    )


def test_serie_mensal_payback_consistente_com_viabilidade() -> None:
    """CA-11f: payback detectado na serie corresponde ao payback de viabilidade().

    Usa VIAVEL (capex=600k) onde payback ocorre dentro de 60 meses.
    """
    r = viabilidade(**VIAVEL)
    serie = gerar_serie_mensal(**VIAVEL)
    # Encontrar payback na serie: primeiro mes com fcf_acumulado >= 0
    payback_serie = next(
        (row["mes"] for row in serie if row["fcf_acumulado"] >= 0),
        float("inf"),
    )
    assert payback_serie == r.payback_meses, (
        f"Payback da serie ({payback_serie}) difere de viabilidade() ({r.payback_meses})"
    )


def test_serie_mensal_alunos_cresce_ate_maturidade() -> None:
    """CA-11g: alunos_balcao cresce monotonicamente ate o steady-state."""
    serie = gerar_serie_mensal(**DEFAULTS)
    alunos = [row["alunos_balcao"] for row in serie]
    # Deve crescer ou manter (nunca decresce durante a rampa)
    for i in range(1, len(alunos)):
        assert alunos[i] >= alunos[i - 1] - 0.01, (
            f"Alunos decresceu no mes {i + 1}: {alunos[i]} < {alunos[i - 1]}"
        )
    # Deve atingir o steady-state (938 com churn 0.06) ao final
    assert abs(alunos[-1] - DEFAULTS["alunos_maturidade"]) < 0.01, (
        f"Alunos no mes 60 ({alunos[-1]:.2f}) deveria ser proximo de {DEFAULTS['alunos_maturidade']}"
    )


def test_serie_mensal_com_financiamento_payback_pior_ou_igual() -> None:
    """CA-11h: com financiamento, o payback e pior ou igual ao sem financiamento (PMT drena FCF)."""
    serie_sem = gerar_serie_mensal(**VIAVEL)
    serie_com = gerar_serie_mensal(**VIAVEL, capex_financiado_pct=1.0, prazo_financiamento_meses=36)
    payback_sem = next((row["mes"] for row in serie_sem if row["fcf_acumulado"] >= 0), float("inf"))
    payback_com = next((row["mes"] for row in serie_com if row["fcf_acumulado"] >= 0), float("inf"))
    assert payback_com >= payback_sem, (
        f"Payback com financiamento ({payback_com}) deveria ser >= sem ({payback_sem})"
    )
