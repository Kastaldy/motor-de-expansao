"""Simulador financeiro deterministico (DRE fundamentado) e goal-seek (BLK-DIM-03R).

Replica a linha de resultado do DRE do Excel com as 3 fontes de receita reais:
  - Balcao:    pagantes * ticket * (1 - inadimplencia)
  - Agregadores: alunos_agregadores * ticket_agregador * (1 - inadimplencia)
  - Personal:  personal_mes (fixo, sem churn nem inadimplencia)

Custos fixos sao ABSOLUTOS (R$/mes), nao ratios — eliminando os numeros magicos
pessoal_pct/outros_custos_pct/custo_fixo_base_mes do spike BLK-DIM-03.

READ-ONLY sobre o M1: nao recalcula score_priorizacao nem artefatos oficiais (DEC-001).

Nota sobre benchmark (spec §8.2):
    Com os defaults do Excel (938 balcao + 651 agr + R$5k personal, aluguel R$20k,
    ticket R$137/R$82, custos fixos reais: pessoal R$50.128 + outros R$38.150),
    a margem_ebitda_pct fica ~22% (benchmark externo ~23% ano 2+; tolerancia +/-4pp).
    O criterio anti-circularidade esta em CA-08: sem agregadores/personal, a margem
    fica NEGATIVA (custos fixos R$88k > receita so balcao), provando que o modelo
    nao esta com custos artificialmente baixos.
"""

from __future__ import annotations

from dataclasses import dataclass

from scipy.optimize import brentq

from motor_expansao.dimensionamento.config import (
    SIM_ALUNOS_AGREGADORES_MATURIDADE,
    SIM_ALUNOS_INICIAL,
    SIM_CAPEX_DEFAULT,
    SIM_CARTOES_PCT,
    SIM_CHURN,
    SIM_COFINS,
    SIM_CSLL_EFETIVO,
    SIM_DEVOLUCOES_PCT,
    SIM_IR_EFETIVO,
    SIM_ISS,
    SIM_MANUTENCAO_PCT,
    SIM_MARKETING_PCT,
    SIM_MATURACAO_MESES,
    SIM_OUTROS_FIXOS_MES,
    SIM_PERSONAL_MES_RECEITA,
    SIM_PESSOAL_MES,
    SIM_PIS,
    SIM_ROYALTIES_PCT,
    SIM_TICKET_AGREGADOR,
)


@dataclass
class ViabilidadeResult:
    """Resultado do simulador financeiro para um cenario de unidade.

    Campos:
    -------
    faturamento_mensal_steady:
        Receita bruta total no steady-state (balcao + agregadores + personal).
    receita_liquida:
        Faturamento menos deducoes (faturamento x devolucoes_pct).
    receita_pos_impostos:
        Receita liquida menos PIS, COFINS e ISS.
    ebitda_mensal:
        receita_pos_impostos menos custos operacionais totais (variaveis + fixos + aluguel).
    margem_ebitda_pct:
        ebitda_mensal / faturamento_mensal_steady (sobre bruto, consistente com spec §8.2).
    payback_meses:
        Meses ate FCF acumulado zerar (com rampa de maturacao e PMT de financiamento
        se capex_financiado_pct > 0); float('inf') se nunca dentro de 60 meses.
    roic_anual:
        NOPAT anual / capex total (em fracao; 0.0 se capex == 0).
    lucro_liquido_mensal:
        ebitda_mensal - IR - CSLL (steady-state).
    flag_viavel:
        True se margem_ebitda_pct >= 0.10 E payback_meses <= 36.
    """

    faturamento_mensal_steady: float
    receita_liquida: float
    receita_pos_impostos: float
    ebitda_mensal: float
    margem_ebitda_pct: float
    payback_meses: float
    roic_anual: float
    lucro_liquido_mensal: float
    flag_viavel: bool


def viabilidade(
    alunos_maturidade: float,
    m2: float,
    aluguel_mes: float,
    ticket_medio: float,
    *,
    # Parametros de demanda — agregadores e personal (Caminho B, D1)
    alunos_agregadores: float = SIM_ALUNOS_AGREGADORES_MATURIDADE,
    ticket_agregador: float = SIM_TICKET_AGREGADOR,
    personal_mes: float = SIM_PERSONAL_MES_RECEITA,
    # Parametros de churn / inadimplencia
    churn: float = SIM_CHURN,
    inadimplencia: float = 0.02,
    # Parametros de capex
    capex: float | None = None,
    coef_capex_m2: float | None = None,
    # Parametros de financiamento de capex (capex parcelado — equipamentos/tecnologia)
    capex_financiado_pct: float = 0.0,   # fracao do capex financiado (0.0 = pagamento a vista; sem PMT)
    prazo_financiamento_meses: int = 36,  # prazo do parcelamento em meses (default planilha)
    juros_financiamento_am: float = 0.018,  # taxa de juros mensal (default 1,8% a.m.)
    # Ratios % do DRE (defaults do JSON via constantes config.py)
    royalties_pct: float = SIM_ROYALTIES_PCT,
    marketing_pct: float = SIM_MARKETING_PCT,
    manutencao_pct: float = SIM_MANUTENCAO_PCT,
    cartoes_pct: float = SIM_CARTOES_PCT,
    devolucoes_pct: float = SIM_DEVOLUCOES_PCT,
    # Impostos (regime presumido; defaults do JSON)
    pis: float = SIM_PIS,
    cofins: float = SIM_COFINS,
    iss: float = SIM_ISS,
    ir_efetivo: float = SIM_IR_EFETIVO,
    csll_efetivo: float = SIM_CSLL_EFETIVO,
    # Custos fixos ABSOLUTOS (defaults das constantes config.py)
    pessoal_mes: float = SIM_PESSOAL_MES,
    outros_fixos_mes: float = SIM_OUTROS_FIXOS_MES,
    # Rampa de maturacao
    maturacao_meses: int = SIM_MATURACAO_MESES,
    alunos_inicial: float = float(SIM_ALUNOS_INICIAL),
) -> ViabilidadeResult:
    """Calcula viabilidade financeira de uma unidade (DRE com 3 fontes de receita).

    Replica o DRE do Excel com 3 linhas de receita independentes:
      - Balcao:    pagantes_balcao * ticket_medio * (1 - inadimplencia)
      - Agregadores: alunos_agregadores * ticket_agregador * (1 - inadimplencia)
      - Personal:  personal_mes (fixo, sem churn nem inadimplencia no Excel)

    Custos fixos sao ABSOLUTOS (pessoal_mes + outros_fixos_mes + aluguel_mes),
    nao ratios sobre receita.

    A rampa de maturacao afeta SOMENTE o balcao; agregadores e personal ficam
    constantes durante a rampa (fiel ao Excel).

    Parameters
    ----------
    alunos_maturidade:
        Alunos balcao na maturidade (ex.: 938).
    m2:
        Metragem da unidade em m2 (usado para derivar capex via coef_capex_m2 se capex=None).
    aluguel_mes:
        Aluguel mensal em R$.
    ticket_medio:
        Mensalidade balcao em R$ por aluno.
    alunos_agregadores:
        Alunos via canais agregadores na maturidade (default 651; Simulador E11).
    ticket_agregador:
        Mensalidade agregadores em R$ por aluno (default R$82; aba Simulador linha 11).
    personal_mes:
        Receita fixa de personal trainer em R$/mes (default R$5.000; DRE linha 24).
        ATENCAO: diferente de pessoal_mes (custo de folha).
    churn:
        Taxa de churn mensal do balcao (fracao; default 0.06; Simulador E12).
        Nao se aplica a agregadores (Excel os modela separadamente).
    inadimplencia:
        Taxa de inadimplencia (balcao + agregadores; fracao; default 0.02).
    capex:
        Investimento inicial total em R$. Se None, e derivado de coef_capex_m2 * m2;
        se ambos None, usa SIM_CAPEX_DEFAULT (R$2.340.000; Simulador R9 cenario 0).
    coef_capex_m2:
        Coeficiente de capex por m2 (R$/m2). Usado se capex=None e coef_capex_m2 fornecido.
    capex_financiado_pct:
        Fracao do capex efetivo financiado (0.0 a 1.0; default 0.0 = pagamento a vista).
        Com 0.0, o comportamento e identico ao atual (nenhuma PMT gerada).
    prazo_financiamento_meses:
        Prazo do parcelamento em meses (default 36). So usado se capex_financiado_pct > 0.
    juros_financiamento_am:
        Taxa de juros mensal do financiamento em fracao (default 0.018 = 1,8% a.m.).
        Se 0.0, a PMT e calculada como parcela simples (C / n), sem juros.
    royalties_pct:
        Royalties sobre receita liquida (fracao; default 0.08; Simulador N11).
    marketing_pct:
        Marketing sobre receita liquida (fracao; default 0.02; DRE F63).
    manutencao_pct:
        Manutencao sobre receita liquida (fracao; default 0.02; DRE F67).
    cartoes_pct:
        Taxas de cartao sobre receita liquida (fracao; default 0.0105; DRE F79).
    devolucoes_pct:
        Deducoes sobre faturamento bruto (fracao; default 0.005; DRE F30).
    pis:
        PIS sobre receita liquida (fracao; default 0.0065; Tributos E38).
    cofins:
        COFINS sobre receita liquida (fracao; default 0.03; Tributos E40).
    iss:
        ISS sobre receita liquida (fracao; default 0.03; Tributos E42).
    ir_efetivo:
        IR efetivo sobre receita liquida, regime presumido (fracao; default 0.08; Tributos E44).
    csll_efetivo:
        CSLL efetivo sobre receita liquida, regime presumido (fracao; default 0.0288; Tributos E46).
    pessoal_mes:
        Custo fixo absoluto de pessoal/folha em R$/mes (default R$50.128,16; DRE linha 55).
        ATENCAO: diferente de personal_mes (receita de personal trainer).
    outros_fixos_mes:
        Outros custos fixos absolutos em R$/mes (default R$38.150; DRE linhas 52-59,69).
        Inclui IPTU, agua/luz, limpeza, tecnologia, assessorias, outros.
    maturacao_meses:
        Meses de rampa de maturacao do balcao (default 8; Simulador E13).
    alunos_inicial:
        Alunos balcao no inicio da operacao (default 500; Simulador E9).

    Returns
    -------
    ViabilidadeResult
    """
    # -----------------------------------------------------------------------
    # 1. Pagantes balcao (churn aplica-se somente ao balcao)
    # -----------------------------------------------------------------------
    pagantes_balcao = alunos_maturidade * (1.0 - churn)

    # -----------------------------------------------------------------------
    # 2. Receitas brutas — 3 fontes independentes
    # -----------------------------------------------------------------------
    receita_balcao = pagantes_balcao * ticket_medio * (1.0 - inadimplencia)
    receita_agr = alunos_agregadores * ticket_agregador * (1.0 - inadimplencia)
    receita_personal = personal_mes  # fixo, sem churn nem inadimplencia
    faturamento = receita_balcao + receita_agr + receita_personal

    # -----------------------------------------------------------------------
    # 3. Deducoes sobre faturamento total
    # -----------------------------------------------------------------------
    devolucoes = faturamento * devolucoes_pct
    receita_liquida = faturamento - devolucoes

    # -----------------------------------------------------------------------
    # 4. Impostos sobre receita liquida (regime presumido)
    # -----------------------------------------------------------------------
    total_impostos = receita_liquida * (pis + cofins + iss)
    receita_pos_impostos = receita_liquida - total_impostos

    # -----------------------------------------------------------------------
    # 5. Custos operacionais variaveis (% sobre receita_liquida)
    # -----------------------------------------------------------------------
    custos_variaveis = receita_liquida * (
        royalties_pct + marketing_pct + manutencao_pct + cartoes_pct
    )

    # -----------------------------------------------------------------------
    # 6. Custos fixos absolutos
    # -----------------------------------------------------------------------
    custos_fixos = pessoal_mes + outros_fixos_mes + aluguel_mes

    # -----------------------------------------------------------------------
    # 7. EBITDA mensal
    # -----------------------------------------------------------------------
    total_custos_op = custos_variaveis + custos_fixos
    ebitda = receita_pos_impostos - total_custos_op

    # -----------------------------------------------------------------------
    # 8. Margem EBITDA (sobre faturamento bruto, consistente com spec §8.2)
    # -----------------------------------------------------------------------
    margem_ebitda_pct = ebitda / faturamento if faturamento > 0 else 0.0

    # -----------------------------------------------------------------------
    # 9. IR e CSLL (sobre receita liquida, regime presumido)
    # -----------------------------------------------------------------------
    ir = receita_liquida * ir_efetivo
    csll = receita_liquida * csll_efetivo
    lucro_liquido = ebitda - ir - csll

    # -----------------------------------------------------------------------
    # 10. Capex: parametro direto > coef_capex_m2 * m2 > default do Excel
    # -----------------------------------------------------------------------
    capex_efetivo: float
    if capex is None and coef_capex_m2 is not None:
        capex_efetivo = coef_capex_m2 * m2
    elif capex is None:
        capex_efetivo = float(SIM_CAPEX_DEFAULT)
    else:
        capex_efetivo = float(capex)

    # -----------------------------------------------------------------------
    # 11. Rampa de maturacao (payback)
    # A rampa afeta SOMENTE o balcao (alunos_inicial -> alunos_maturidade).
    # Agregadores e personal mantêm valor constante durante a rampa (fiel ao Excel).
    # -----------------------------------------------------------------------
    fcf_acum = -capex_efetivo
    payback_meses: float = float("inf")
    _maturacao_meses = max(maturacao_meses, 1)  # evitar divisao por zero

    # -----------------------------------------------------------------------
    # 11a. PMT de financiamento (calculada UMA VEZ, antes do loop)
    # Afeta SOMENTE o fcf_t no loop (custo financeiro pos-EBITDA).
    # margem_ebitda_pct e ebitda_mensal NAO sao alterados pela PMT.
    # -----------------------------------------------------------------------
    _C = capex_efetivo * capex_financiado_pct
    if _C > 0 and juros_financiamento_am > 0:
        _r = juros_financiamento_am
        _n = prazo_financiamento_meses
        _pmt = _C * _r * (1.0 + _r) ** _n / ((1.0 + _r) ** _n - 1.0)
    elif _C > 0:
        # juros zero: parcela simples (sem encargos)
        _pmt = _C / max(prazo_financiamento_meses, 1)
    else:
        _pmt = 0.0

    for t in range(1, 61):
        frac = min(t / _maturacao_meses, 1.0)
        al_t = alunos_inicial + (alunos_maturidade - alunos_inicial) * frac
        pag_t = al_t * (1.0 - churn)
        fat_balcao_t = pag_t * ticket_medio * (1.0 - inadimplencia)
        fat_agr_t = alunos_agregadores * ticket_agregador * (1.0 - inadimplencia)
        fat_t = fat_balcao_t + fat_agr_t + personal_mes
        dev_t = fat_t * devolucoes_pct
        rl_t = fat_t - dev_t
        imp_t = rl_t * (pis + cofins + iss)
        rpi_t = rl_t - imp_t
        cvar_t = rl_t * (royalties_pct + marketing_pct + manutencao_pct + cartoes_pct)
        cfix_t = pessoal_mes + outros_fixos_mes + aluguel_mes
        eb_t = rpi_t - cvar_t - cfix_t
        ir_t = rl_t * (ir_efetivo + csll_efetivo)
        fcf_t = eb_t - ir_t
        if _pmt > 0 and t <= prazo_financiamento_meses:
            fcf_t -= _pmt
        fcf_acum += fcf_t
        if payback_meses == float("inf") and fcf_acum >= 0:
            payback_meses = float(t)

    # -----------------------------------------------------------------------
    # 12. ROIC anual (sobre steady-state)
    # -----------------------------------------------------------------------
    nopat_anual = lucro_liquido * 12.0
    roic_anual = nopat_anual / capex_efetivo if capex_efetivo > 0 else 0.0

    # -----------------------------------------------------------------------
    # 13. flag_viavel
    # -----------------------------------------------------------------------
    flag_viavel = (margem_ebitda_pct >= 0.10) and (payback_meses <= 36)

    return ViabilidadeResult(
        faturamento_mensal_steady=float(faturamento),
        receita_liquida=float(receita_liquida),
        receita_pos_impostos=float(receita_pos_impostos),
        ebitda_mensal=float(ebitda),
        margem_ebitda_pct=float(margem_ebitda_pct),
        payback_meses=float(payback_meses),
        roic_anual=float(roic_anual),
        lucro_liquido_mensal=float(lucro_liquido),
        flag_viavel=bool(flag_viavel),
    )


def aluguel_teto(
    alunos_maturidade: float,
    m2: float,
    ticket_medio: float,
    margem_alvo: float = 0.10,
    **kwargs: object,
) -> float:
    """Calcula o aluguel maximo (teto) que ainda atinge a margem_alvo.

    Usa brentq para inverter a funcao viabilidade: encontra o maior aluguel_mes
    tal que margem_ebitda_pct >= margem_alvo.

    Parameters
    ----------
    alunos_maturidade:
        Alunos na maturidade (balcao).
    m2:
        Metragem da unidade em m2.
    ticket_medio:
        Mensalidade media por aluno em R$.
    margem_alvo:
        Margem EBITDA minima desejada (fracao; default 0.10).
    **kwargs:
        Demais parametros repassados para viabilidade() (incluindo alunos_agregadores,
        ticket_agregador, personal_mes, pessoal_mes, outros_fixos_mes, etc.).

    Returns
    -------
    float
        Aluguel teto em R$/mes. Retorna 0.0 se inviavel mesmo com aluguel=0.
    """

    def _obj(alug: float) -> float:
        return (
            viabilidade(alunos_maturidade, m2, alug, ticket_medio, **kwargs).margem_ebitda_pct  # type: ignore[arg-type]
            - margem_alvo
        )

    # Verificar se e viavel com aluguel=0
    if _obj(0.0) < 0:
        return 0.0  # nem com aluguel zero atinge a margem

    # Limite superior: aluguel absurdamente alto (maior que qualquer receita possivel)
    # Usa receita TOTAL (balcao + agregadores + personal) para nao capar quando eles sao materiais
    _alunos_agr = float(kwargs.get("alunos_agregadores", SIM_ALUNOS_AGREGADORES_MATURIDADE))  # type: ignore[arg-type]
    _ticket_agr = float(kwargs.get("ticket_agregador", SIM_TICKET_AGREGADOR))  # type: ignore[arg-type]
    _personal = float(kwargs.get("personal_mes", SIM_PERSONAL_MES_RECEITA))  # type: ignore[arg-type]
    _receita_total = alunos_maturidade * ticket_medio + _alunos_agr * _ticket_agr + _personal
    alug_sup = _receita_total * 2.0
    if alug_sup <= 0:
        return 0.0

    if _obj(alug_sup) > 0:
        return float(alug_sup)  # defensivo

    return float(brentq(_obj, 0.0, alug_sup, xtol=1.0, maxiter=100))


def alunos_minimos_viaveis(
    m2: float,
    aluguel_mes: float,
    ticket_medio: float,
    margem_alvo: float = 0.0,
    **kwargs: object,
) -> float:
    """Calcula o numero minimo de alunos na maturidade para atingir a margem_alvo.

    Usa brentq para inverter a funcao viabilidade.

    Parameters
    ----------
    m2:
        Metragem da unidade em m2.
    aluguel_mes:
        Aluguel mensal em R$.
    ticket_medio:
        Mensalidade media por aluno em R$.
    margem_alvo:
        Margem EBITDA minima desejada (fracao; default 0.0).
    **kwargs:
        Demais parametros repassados para viabilidade().

    Returns
    -------
    float
        Alunos minimos (balcao). Retorna float('inf') se inviavel mesmo com 5000 alunos.
    """
    alunos_inicial = float(kwargs.get("alunos_inicial", SIM_ALUNOS_INICIAL))  # type: ignore[arg-type]

    def _obj(alunos: float) -> float:
        return (
            viabilidade(alunos, m2, aluguel_mes, ticket_medio, **kwargs).margem_ebitda_pct  # type: ignore[arg-type]
            - margem_alvo
        )

    # Verificar se mesmo com muitos alunos (5000) atinge a margem
    if _obj(5000.0) < 0:
        return float("inf")  # inviavel em qualquer cenario razoavel

    # Verificar piso
    alunos_piso = max(alunos_inicial, 1.0)
    if _obj(alunos_piso) >= 0:
        return float(alunos_piso)

    return float(brentq(_obj, alunos_piso, 5000.0, xtol=0.5, maxiter=100))


def m2_otimo(
    alunos_maturidade: float,
    aluguel_por_m2: float,
    ticket_medio: float,
    coef_capex_m2: float,
    margem_alvo: float = 0.10,
    m2_min: float = 750.0,
    m2_max: float = 2800.0,
) -> float:
    """Encontra o menor m2 em [m2_min, m2_max] que atinge a margem_alvo.

    Considera aluguel_mes = aluguel_por_m2 * m2 e capex = coef_capex_m2 * m2.
    Usa os defaults SIM_* para os demais parametros (incluindo as 3 fontes de receita).

    Parameters
    ----------
    alunos_maturidade:
        Alunos na maturidade (balcao).
    aluguel_por_m2:
        Aluguel mensal por m2 (R$/m2/mes).
    ticket_medio:
        Mensalidade media por aluno em R$.
    coef_capex_m2:
        Capex por m2 (R$/m2).
    margem_alvo:
        Margem EBITDA minima desejada (fracao; default 0.10).
    m2_min:
        Limite inferior do intervalo de busca (default 750 m2).
    m2_max:
        Limite superior do intervalo de busca (default 2800 m2).

    Returns
    -------
    float
        Menor m2 que atinge a margem_alvo, dentro de [m2_min, m2_max].
        Retorna m2_min se ja atingir a margem no minimo; m2_max se nao atingir em nenhum.
    """

    def _obj(m2: float) -> float:
        return (
            viabilidade(
                alunos_maturidade,
                m2,
                aluguel_mes=aluguel_por_m2 * m2,
                ticket_medio=ticket_medio,
                coef_capex_m2=coef_capex_m2,
            ).margem_ebitda_pct
            - margem_alvo
        )

    if _obj(m2_min) >= 0:
        return float(m2_min)
    if _obj(m2_max) < 0:
        return float(m2_max)

    return float(brentq(_obj, m2_min, m2_max, xtol=1.0, maxiter=100))
