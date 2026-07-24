"""Simulador financeiro deterministico (DRE fundamentado) e goal-seek.

FONTE UNICA DE VERDADE (FIN-VIAB-01, 2026-07-24)
------------------------------------------------
`gerar_serie_mensal_completa()` constroi UMA linha do tempo de M-4 a M+60 com
TODAS as linhas do DRE mes a mes. Todo KPI novo — payback, TIR, VPL, retorno,
break-even, acumulado, aluguel-teto — deriva dela. Nenhum grafico, endpoint ou
PDF pode recalcular nada por conta propria.

Antes desta reforma existiam CINCO series mensais independentes e NOVE KPIs com
implementacao dupla, o que fazia a tela e o PDF do MESMO cenario divergirem:
payback 35 vs 33, acumulado R$1,89 mi vs R$2,05 mi, aluguel-teto R$55,5 mil vs
R$105,8 mil.

Receita (3 fontes reais):
  - Balcao:      pagantes * ticket * (1 - inadimplencia)
  - Agregadores: alunos_agregadores * (ticket * fator_agregador) * (1 - inadimplencia)
  - Personal:    personal_mes (fixo, sem churn nem inadimplencia)

O custo operacional NAO e 100% fixo — tem tres naturezas, agora EXPLICITAS no
resultado (antes o dataclass so expunha o total e a UI reconstruia por diferenca):
  - variavel (% da receita liquida): royalties + marketing + manutencao + cartoes
  - folha (% do faturamento bruto):  SIM_FOLHA_PCT  [caminho novo]
  - fixo absoluto:                   outros_fixos + aluguel + custo pre-operacional

COMPATIBILIDADE
---------------
`viabilidade()`, `gerar_serie_mensal()`, `aluguel_teto()` e
`alunos_minimos_viaveis()` continuam existindo como ADAPTADORES sobre o mesmo
nucleo, com semantica historica preservada (folha absoluta, IR/CSLL efetivo
sobre a receita liquida, break-even variando so o balcao) para nao quebrar
`backtest_viabilidade`, `batch_viabilidade`, `excel_export`, `risco` e a suite.
O caminho NOVO (`Premissas` + `simular`) e o que o piloto web e o PDF consomem.

READ-ONLY sobre o M1: nao recalcula score_priorizacao nem artefatos oficiais
(DEC-001/DEC-008/DEC-009).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from scipy.optimize import brentq

from motor_expansao.dimensionamento.config import (
    SIM_ALUGUEL_TETO_EXCECAO,
    SIM_ALUGUEL_TETO_IDEAL,
    SIM_ALUGUEL_TETO_TETO,
    SIM_ALUNOS_AGREGADORES_MATURIDADE,
    SIM_ALUNOS_INICIAL,
    SIM_ANUIDADE_APENAS_BALCAO,
    SIM_ANUIDADE_ELEGIVEL_PCT,
    SIM_ANUIDADE_MES_INICIO,
    SIM_ANUIDADE_PRO_RATA,
    SIM_ANUIDADE_VALOR,
    SIM_BASE_PRESUMIDA_PCT,
    SIM_CAPEX_DEFAULT,
    SIM_CAPEX_RENOVACAO,
    SIM_CARENCIA_ALUGUEL_MESES,
    SIM_CARTOES_PCT,
    SIM_CHURN,
    SIM_COFINS,
    SIM_CSLL_ALIQUOTA,
    SIM_CSLL_EFETIVO,
    SIM_CUSTO_PRE_OPERACIONAL_MES,
    SIM_DEVOLUCOES_PCT,
    SIM_FOLHA_PCT,
    SIM_HORIZONTE_MESES,
    SIM_INADIMPLENCIA,
    SIM_IR_EFETIVO,
    SIM_IRPJ_ADICIONAL_ALIQUOTA,
    SIM_IRPJ_ADICIONAL_LIMITE_MES,
    SIM_IRPJ_ALIQUOTA,
    SIM_ISS,
    SIM_MANUTENCAO_PCT,
    SIM_MARGEM_VIAVEL_MIN,
    SIM_MARKETING_PCT,
    SIM_MATURACAO_MESES,
    SIM_MESES_PRE_ABERTURA,
    SIM_OUTROS_FIXOS_MES,
    SIM_PARCELAS_OBRA_DEFAULT,
    SIM_PAYBACK_VIAVEL_MAX,
    SIM_PERSONAL_MES_RECEITA,
    SIM_PESSOAL_MES,
    SIM_PIS,
    SIM_REAJUSTE_ALUGUEL_AA,
    SIM_REAJUSTE_CUSTOS_AA,
    SIM_REAJUSTE_TICKET_AA,
    SIM_ROYALTIES_PCT,
    SIM_SHARE_BALCAO,
    SIM_TAXA_DESCONTO_AA,
    SIM_TAXA_FRANQUIA,
    SIM_TICKET_AGREGADOR,
    SIM_TICKET_AGREGADOR_FATOR,
    SIM_VALOR_RESIDUAL_MES_60,
)

# Modos de apuracao de IR/CSLL.
IR_MODO_FAIXA = "presumido_faixa"    # IRPJ 15% + adicional 10% na faixa + CSLL 9% (base bruta)
IR_MODO_EFETIVO = "efetivo_legado"   # aliquotas efetivas sobre a receita liquida (historico)


# ---------------------------------------------------------------------------
# Premissas
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Premissas:
    """Todo coeficiente que o simulador consome, num objeto so.

    A causa raiz dos achados da auditoria foi cada camada carregar a sua copia
    dos coeficientes. Aqui break-even, aluguel-teto, grade de sensibilidade e
    serie mensal leem EXATAMENTE os mesmos numeros.
    """

    ticket_cheio: float
    share_balcao: float = SIM_SHARE_BALCAO
    ticket_agregador_fator: float = SIM_TICKET_AGREGADOR_FATOR
    personal_mes: float = SIM_PERSONAL_MES_RECEITA
    churn: float = SIM_CHURN
    inadimplencia: float = SIM_INADIMPLENCIA

    devolucoes_pct: float = SIM_DEVOLUCOES_PCT
    pis: float = SIM_PIS
    cofins: float = SIM_COFINS
    iss: float = SIM_ISS

    royalties_pct: float = SIM_ROYALTIES_PCT
    marketing_pct: float = SIM_MARKETING_PCT
    manutencao_pct: float = SIM_MANUTENCAO_PCT
    cartoes_pct: float = SIM_CARTOES_PCT

    # Folha: % do faturamento bruto, OU absoluto quando pessoal_mes_override != None.
    folha_pct: float = SIM_FOLHA_PCT
    pessoal_mes_override: float | None = None

    outros_fixos_mes: float = SIM_OUTROS_FIXOS_MES
    aluguel_mes: float = 0.0
    custo_pre_operacional_mes: float = SIM_CUSTO_PRE_OPERACIONAL_MES

    # IR/CSLL
    ir_modo: str = IR_MODO_FAIXA
    base_presumida_pct: float = SIM_BASE_PRESUMIDA_PCT
    irpj_aliquota: float = SIM_IRPJ_ALIQUOTA
    irpj_adicional_aliquota: float = SIM_IRPJ_ADICIONAL_ALIQUOTA
    irpj_adicional_limite_mes: float = SIM_IRPJ_ADICIONAL_LIMITE_MES
    csll_aliquota: float = SIM_CSLL_ALIQUOTA
    ir_efetivo: float = SIM_IR_EFETIVO
    csll_efetivo: float = SIM_CSLL_EFETIVO

    reajuste_ticket_aa: float = SIM_REAJUSTE_TICKET_AA
    reajuste_aluguel_aa: float = SIM_REAJUSTE_ALUGUEL_AA
    reajuste_custos_aa: float = SIM_REAJUSTE_CUSTOS_AA

    maturacao_meses: int = SIM_MATURACAO_MESES
    alunos_inicial: float = float(SIM_ALUNOS_INICIAL)
    meses_pre_abertura: int = SIM_MESES_PRE_ABERTURA
    horizonte_meses: int = SIM_HORIZONTE_MESES
    carencia_aluguel_meses: int = SIM_CARENCIA_ALUGUEL_MESES

    valor_residual_mes_60: float = SIM_VALOR_RESIDUAL_MES_60
    capex_renovacao: float = SIM_CAPEX_RENOVACAO
    taxa_desconto_aa: float = SIM_TAXA_DESCONTO_AA

    # Override absoluto do ticket de agregador (compat com chamadas historicas).
    ticket_agregador_absoluto: float | None = None

    # Anuidade: R$ por aluno de balcao que completa `anuidade_mes_inicio` meses,
    # cobrada UMA VEZ POR ANO e reconhecida pro-rata mensal.
    anuidade_valor: float = SIM_ANUIDADE_VALOR
    anuidade_mes_inicio: int = SIM_ANUIDADE_MES_INICIO
    anuidade_apenas_balcao: bool = SIM_ANUIDADE_APENAS_BALCAO
    anuidade_elegivel_pct: float | None = SIM_ANUIDADE_ELEGIVEL_PCT
    anuidade_pro_rata: bool = SIM_ANUIDADE_PRO_RATA

    # Contrato da rampa. False (novo): a demanda TOTAL rampa e o mix escala junto —
    # uma unidade nova nao tem volume cheio de Gympass no mes 1. True (historico):
    # so o balcao rampa; agregadores entram no valor de maturidade desde o mes 1.
    # Neste modo `alunos_inicial` esta em unidades de BALCAO.
    rampa_apenas_balcao: bool = False

    @property
    def ticket_agregador(self) -> float:
        """Ticket do agregador ACOPLADO ao ticket cheio (era R$82 absoluto).

        O desacoplamento era o defeito real: quando o studio elevava o ticket de
        R$147 para R$177, o agregador degradava de 55,8% para 46,3% sem ninguem ver.
        """
        if self.ticket_agregador_absoluto is not None:
            return float(self.ticket_agregador_absoluto)
        return self.ticket_cheio * self.ticket_agregador_fator

    @property
    def ticket_blended(self) -> float:
        """Ticket medio efetivo por aluno TOTAL, liquido de churn e inadimplencia.

        E o numero que faltava na tela: R$147 de ticket cheio entram no caixa como
        ~R$120 por aluno. Nao inclui a receita fixa de personal (nao e por aluno).
        """
        s = self.share_balcao
        liq = 1.0 - self.inadimplencia
        return (
            s * (1.0 - self.churn) * self.ticket_cheio * liq
            + (1.0 - s) * self.ticket_agregador * liq
        )

    @property
    def impostos_receita_pct(self) -> float:
        return self.pis + self.cofins + self.iss

    @property
    def custo_variavel_pct(self) -> float:
        return self.royalties_pct + self.marketing_pct + self.manutencao_pct + self.cartoes_pct

    @property
    def folha_efetiva_pct(self) -> float:
        """0 quando ha override absoluto (a folha vira custo fixo)."""
        return 0.0 if self.pessoal_mes_override is not None else self.folha_pct

    @property
    def fator_receita_para_ebitda(self) -> float:
        """Quanto de cada R$1 de faturamento bruto sobra ANTES do custo fixo.

        k = (1 - deducoes) * (1 - impostos - custo_variavel) - folha_pct

        Com os defaults novos: 0,995 * (1 - 0,0665 - 0,1305) - 0,17 = 0,628985.
        O briefing da auditoria supunha 0,92883 (tratando o custo como 100% fixo),
        o que superestimava a contribuicao por aluno em 16,3%.
        """
        return (1.0 - self.devolucoes_pct) * (
            1.0 - self.impostos_receita_pct - self.custo_variavel_pct
        ) - self.folha_efetiva_pct

    @property
    def custo_fixo_base_mes(self) -> float:
        """Custo fixo de steady-state SEM aluguel (que tem carencia propria)."""
        base = self.outros_fixos_mes
        if self.pessoal_mes_override is not None:
            base += self.pessoal_mes_override
        return base

    def contribuicao_por_aluno_total(self) -> float:
        """Quanto cada aluno TOTAL adiciona ao EBITDA (mix balcao/agregador)."""
        return self.ticket_blended * self.fator_receita_para_ebitda

    @property
    def anuidade_elegivel_efetivo(self) -> float:
        """Fracao de alunos que chega ao mes de cobranca da anuidade.

        Derivada do proprio churn quando nao ha override — com churn 6%/mes,
        0,94^12 = 47,6%. Fica atrelada ao churn de proposito: nem todo aluno
        completa 12 meses, e mexer no churn tem que ajustar isto sozinho.
        """
        if self.anuidade_elegivel_pct is not None:
            return max(0.0, min(1.0, float(self.anuidade_elegivel_pct)))
        return (1.0 - self.churn) ** max(int(self.anuidade_mes_inicio), 0)

    @property
    def anuidade_por_aluno_balcao_mes(self) -> float:
        """Receita mensal de anuidade por aluno de balcao, em regime pleno."""
        if self.anuidade_valor <= 0:
            return 0.0
        por_ano = self.anuidade_valor * self.anuidade_elegivel_efetivo
        return por_ano / 12.0 if self.anuidade_pro_rata else por_ano

    @property
    def receita_por_aluno_total(self) -> float:
        """Receita mensal por aluno TOTAL em regime pleno (mensalidade + anuidade).

        E o numero que o break-even precisa: em regime pleno a anuidade ja entrou.
        """
        extra = self.anuidade_por_aluno_balcao_mes * (
            self.share_balcao if self.anuidade_apenas_balcao else 1.0
        )
        return self.ticket_blended + extra

    def faturamento(
        self, alunos_total: float, *, fator_ticket: float = 1.0, com_anuidade: bool = False
    ) -> float:
        """Faturamento bruto para uma demanda TOTAL de alunos (mix padrao)."""
        s = self.share_balcao
        return self.faturamento_por_fonte(
            alunos_total * s, alunos_total * (1.0 - s),
            fator_ticket=fator_ticket, com_anuidade=com_anuidade,
        )

    def faturamento_por_fonte(
        self, alunos_balcao: float, alunos_agregadores: float, *,
        fator_ticket: float = 1.0, com_anuidade: bool = False,
    ) -> float:
        """Faturamento bruto a partir das contagens EXPLICITAS de cada fonte."""
        liq = 1.0 - self.inadimplencia
        base = (
            alunos_balcao * (1.0 - self.churn) * self.ticket_cheio * fator_ticket * liq
            + alunos_agregadores * self.ticket_agregador * fator_ticket * liq
            + self.personal_mes
        )
        return base + (
            self.receita_anuidade(alunos_balcao, alunos_agregadores) if com_anuidade else 0.0
        )

    def receita_anuidade(self, alunos_balcao: float, alunos_agregadores: float) -> float:
        """Receita de anuidade do mes (0 antes do mes de inicio — ver a serie)."""
        base = alunos_balcao if self.anuidade_apenas_balcao else (
            alunos_balcao + alunos_agregadores
        )
        return base * self.anuidade_por_aluno_balcao_mes

    def ir_csll(self, faturamento_bruto: float, receita_liquida: float) -> float:
        if self.ir_modo == IR_MODO_EFETIVO:
            return receita_liquida * (self.ir_efetivo + self.csll_efetivo)
        if faturamento_bruto <= 0:
            return 0.0
        base = faturamento_bruto * self.base_presumida_pct
        irpj = base * self.irpj_aliquota
        adicional = max(0.0, base - self.irpj_adicional_limite_mes) * self.irpj_adicional_aliquota
        csll = base * self.csll_aliquota
        return irpj + adicional + csll


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------


@dataclass
class ViabilidadeResult:
    """Resultado do simulador para um cenario de unidade.

    Campos historicos preservados; parcelas do custo e indicadores de comite
    (TIR/VPL/oticas) sao adicoes do FIN-VIAB-01.
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

    # receita de anuidade embutida no faturamento de steady-state, e o mes de
    # operacao a que a DRE acima se refere (regime pleno). O PDF e a tela LEEM este
    # mes; recalcula-lo era o que fazia o waterfall divergir do card no mesmo slide.
    receita_anuidade_mensal: float = 0.0
    mes_referencia_steady: int = 0

    # parcelas do custo operacional (antes invisiveis fora do motor)
    custos_op_mensal: float = 0.0
    custos_variaveis_mensal: float = 0.0
    folha_mensal: float = 0.0
    custos_fixos_mensal: float = 0.0

    # abaixo do EBITDA
    ir_csll_mensal: float = 0.0
    despesa_financeira_mensal: float = 0.0
    resultado_apos_ir_mensal: float = 0.0

    # investimento
    capex_total: float = 0.0
    taxa_franquia: float = 0.0
    investimento_total: float = 0.0
    pmt_mensal: float = 0.0
    juros_totais: float = 0.0

    # retorno: as duas oticas, NUNCA misturadas
    retorno_anual_desalavancado: float = 0.0
    retorno_anual_equity: float = 0.0
    tir_mensal: float | None = None
    tir_anual: float | None = None
    vpl: float | None = None

    mes_caixa_operacional_positivo: int | None = None
    acumulado_mes_final: float = 0.0
    ticket_blended: float = 0.0
    aluguel_teto: dict[str, float] = field(default_factory=dict)
    alunos_break_even_total: float = 0.0
    alunos_break_even_caixa_total: float = 0.0
    serie_mensal: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers financeiros
# ---------------------------------------------------------------------------


def pmt_price(principal: float, juros_am: float, prazo_meses: int) -> float:
    """Parcela do sistema Price. Juros zero -> parcela simples."""
    if principal <= 0 or prazo_meses <= 0:
        return 0.0
    if juros_am <= 0:
        return principal / prazo_meses
    f = (1.0 + juros_am) ** prazo_meses
    return principal * juros_am * f / (f - 1.0)


def _fator_reajuste(mes: int, taxa_aa: float) -> float:
    """Degrau anual a partir do mes 13. Pre-abertura nao reajusta."""
    if mes < 1 or taxa_aa <= 0:
        return 1.0
    return (1.0 + taxa_aa) ** ((mes - 1) // 12)


def vpl(fluxos: list[tuple[int, float]], taxa_aa: float) -> float:
    """VPL descontando cada fluxo pelo seu periodo (0 = primeiro desembolso)."""
    if taxa_aa <= -1.0:
        return float("nan")
    taxa_am = (1.0 + taxa_aa) ** (1.0 / 12.0) - 1.0
    return sum(v / ((1.0 + taxa_am) ** m) for m, v in fluxos)


def tir_mensal(fluxos: list[tuple[int, float]]) -> float | None:
    """TIR mensal por brentq. None quando nao ha troca de sinal (sem raiz real)."""
    valores = [v for _, v in fluxos]
    if not valores or min(valores) >= 0 or max(valores) <= 0:
        return None

    def _npv(taxa: float) -> float:
        return sum(v / ((1.0 + taxa) ** m) for m, v in fluxos)

    lo, hi = -0.95, 1.0
    try:
        if _npv(lo) * _npv(hi) > 0:
            return None
        return float(brentq(_npv, lo, hi, xtol=1e-9, maxiter=200))
    except (ValueError, RuntimeError):
        return None


def aluguel_teto_clusters(faturamento_bruto: float) -> dict[str, float]:
    """Aluguel-teto como % do faturamento bruto — a UNICA definicao do sistema.

    Substitui a inversao por margem EBITDA que o PDF usava e que devolvia
    R$105.813,13 onde a tela mostrava R$55.535,18 no MESMO cenario.
    O canonico exibido como "aluguel-teto" e o `excecao` (30%).
    """
    if faturamento_bruto <= 0:
        return {"ideal": 0.0, "teto": 0.0, "excecao": 0.0, "canonico": 0.0}
    excecao = faturamento_bruto * SIM_ALUGUEL_TETO_EXCECAO
    return {
        "ideal": faturamento_bruto * SIM_ALUGUEL_TETO_IDEAL,
        "teto": faturamento_bruto * SIM_ALUGUEL_TETO_TETO,
        "excecao": excecao,
        "canonico": excecao,
    }


def alunos_para_margem(p: Premissas, margem_alvo: float) -> float:
    """Alunos TOTAIS necessarios para atingir uma margem EBITDA-alvo.

    Mesma algebra do break-even, com a margem no lugar do zero:

        fat * k - custo_fixo = margem_alvo * fat
        fat = custo_fixo / (k - margem_alvo)

    Substitui o goal-seek por brentq do motor antigo (que variava so o balcao) e
    devolve o numero na MESMA unidade do break-even: alunos totais no mix.
    Retorna inf quando a margem-alvo e inatingivel (margem_alvo >= k).
    """
    k = p.fator_receita_para_ebitda
    receita_aluno = p.receita_por_aluno_total
    if receita_aluno <= 0 or margem_alvo >= k:
        return float("inf")
    fat_alvo = (p.custo_fixo_base_mes + p.aluguel_mes) / (k - margem_alvo)
    return max(0.0, (fat_alvo - p.personal_mes) / receita_aluno)


def break_even_alunos(p: Premissas, *, incluir_pmt: float = 0.0) -> float:
    """Break-even em alunos TOTAIS (o mix balcao/agregador escala junto).

    Forma fechada — o custo variavel e a folha % ja estao dentro de
    `fator_receita_para_ebitda`, entao nao ha solver aqui:

        faturamento_BE = (custo_fixo + aluguel + pmt) / k
        alunos_BE      = (faturamento_BE - personal) / receita_por_aluno_total

    `receita_por_aluno_total` ja inclui a anuidade em regime pleno, entao o
    break-even e medido no MESMO regime que a DRE de steady-state.

    `incluir_pmt > 0` devolve o break-even DE CAIXA (cobre o financiamento).

    Antes, `alunos_minimos_viaveis` variava SO o balcao mantendo os agregadores
    congelados na premissa, e o resultado (632) era rotulado e comparado na tela
    como se fosse alunos totais — contra uma demanda total de 2.304.
    """
    k = p.fator_receita_para_ebitda
    receita_aluno = p.receita_por_aluno_total
    if k <= 0 or receita_aluno <= 0:
        return float("inf")
    custo_fixo = p.custo_fixo_base_mes + p.aluguel_mes + max(0.0, incluir_pmt)
    fat_be = custo_fixo / k
    return max(0.0, (fat_be - p.personal_mes) / receita_aluno)


# ---------------------------------------------------------------------------
# Serie mensal — FONTE UNICA
# ---------------------------------------------------------------------------

_CAMPOS_LINHA = (
    "mes", "mes_contrato", "fase", "alunos_total", "alunos_balcao", "alunos_agregadores",
    "faturamento_mensal", "receita_anuidade",
    "deducoes", "receita_liquida", "impostos", "receita_pos_impostos",
    "custos_variaveis", "folha", "outros_fixos", "aluguel", "custo_pre_operacional",
    "custos_op", "ebitda_mensal", "ir_csll", "juros", "amortizacao", "pmt",
    "investimento", "fcf_mensal", "fcf_acumulado",
)


def gerar_serie_mensal_completa(
    demanda_total: float,
    p: Premissas,
    *,
    obra: float = 0.0,
    parcelas_obra: int = SIM_PARCELAS_OBRA_DEFAULT,
    equipamentos: float = 0.0,
    prazo_equipamentos: int = 0,
    juros_equipamentos_am: float = 0.0,
    taxa_franquia: float = SIM_TAXA_FRANQUIA,
) -> list[dict]:
    """Linha do tempo unica: M-`meses_pre_abertura`..M-1 e M1..M`horizonte`.

    Convencoes:
    - `mes` negativo = pre-abertura (obra); `mes` >= 1 = operacao.
    - `mes_contrato` conta 1..N desde a ENTREGA da unidade (M-4), e e o relogio da
      carencia de aluguel — nao a abertura.
    - O custo operacional e INTEGRAL desde o mes 1 (nao acompanha a rampa de alunos);
      as unicas variacoes legitimas no tempo sao a carencia e o reajuste anual.
    - A PMT e NOMINAL (nao reajusta) e entra no caixa; a parcela de JUROS entra na
      DRE como despesa financeira.
    - O CAPEX aparece INTEIRO nesta serie (obra parcelada + franquia + equipamentos),
      entao payback do grafico e payback do KPI sao por construcao o mesmo numero.
    """
    pre = max(int(p.meses_pre_abertura), 0)
    horizonte = max(int(p.horizonte_meses), 1)
    maturacao = max(int(p.maturacao_meses), 1)
    carencia = max(int(p.carencia_aluguel_meses), 0)

    # A rampa nunca pode DECRESCER: com demanda menor que alunos_inicial, o modelo
    # antigo comecava acima do alvo e caia ao longo dos meses.
    bal_maturidade = float(demanda_total) * p.share_balcao
    agr_maturidade = float(demanda_total) * (1.0 - p.share_balcao)
    piso = bal_maturidade if p.rampa_apenas_balcao else float(demanda_total)
    alunos_inicial = min(float(p.alunos_inicial), piso)

    n_parc_obra = max(int(parcelas_obra), 1) if obra > 0 else 0
    obra_parcela = (obra / n_parc_obra) if n_parc_obra > 0 else 0.0

    financiado = equipamentos > 0 and prazo_equipamentos > 0
    pmt = pmt_price(equipamentos, juros_equipamentos_am, prazo_equipamentos) if financiado else 0.0
    saldo = float(equipamentos) if financiado else 0.0

    serie: list[dict] = []
    acum = 0.0

    for i in range(pre):
        mes = i - pre
        mes_contrato = i + 1
        aluguel_m = 0.0 if mes_contrato <= carencia else p.aluguel_mes
        custos_op = aluguel_m + p.custo_pre_operacional_mes

        invest = 0.0
        if mes_contrato <= n_parc_obra:
            invest += obra_parcela
        if i == 0:
            invest += float(taxa_franquia)
        if not financiado and i == pre - 1:
            invest += float(equipamentos)

        fcf = -custos_op - invest
        acum += fcf
        # dict[str, Any]: a linha e numerica exceto `fase`, que e str.
        linha: dict[str, Any] = dict.fromkeys(_CAMPOS_LINHA, 0.0)
        linha.update(
            mes=mes, mes_contrato=mes_contrato, fase="pre_operacional",
            aluguel=aluguel_m, custo_pre_operacional=p.custo_pre_operacional_mes,
            custos_op=custos_op, ebitda_mensal=-custos_op,
            investimento=invest, fcf_mensal=fcf, fcf_acumulado=acum,
        )
        serie.append(linha)

    for t in range(1, horizonte + 1):
        mes_contrato = pre + t
        f_ticket = _fator_reajuste(t, p.reajuste_ticket_aa)
        f_aluguel = _fator_reajuste(t, p.reajuste_aluguel_aa)
        f_custos = _fator_reajuste(t, p.reajuste_custos_aa)

        frac = min(t / maturacao, 1.0)
        if p.rampa_apenas_balcao:
            bal = alunos_inicial + (bal_maturidade - alunos_inicial) * frac
            agr = agr_maturidade
            alunos_total = bal + agr
        else:
            alunos_total = alunos_inicial + (float(demanda_total) - alunos_inicial) * frac
            bal = alunos_total * p.share_balcao
            agr = alunos_total * (1.0 - p.share_balcao)

        # A anuidade so existe a partir do mes de aniversario da 1a safra.
        com_anuidade = p.anuidade_valor > 0 and t >= max(int(p.anuidade_mes_inicio), 1)
        fat = p.faturamento_por_fonte(bal, agr, fator_ticket=f_ticket, com_anuidade=com_anuidade)
        receita_anuidade = p.receita_anuidade(bal, agr) if com_anuidade else 0.0
        ded = fat * p.devolucoes_pct
        rl = fat - ded
        imp = rl * p.impostos_receita_pct
        rpi = rl - imp
        cvar = rl * p.custo_variavel_pct
        folha = (
            p.pessoal_mes_override if p.pessoal_mes_override is not None else fat * p.folha_pct
        )
        outros = p.outros_fixos_mes * f_custos
        aluguel_m = 0.0 if mes_contrato <= carencia else p.aluguel_mes * f_aluguel
        custos_op = cvar + folha + outros + aluguel_m
        ebitda = rpi - custos_op
        ir = p.ir_csll(fat, rl)

        juros = saldo * juros_equipamentos_am if (financiado and t <= prazo_equipamentos) else 0.0
        pmt_t = pmt if (financiado and t <= prazo_equipamentos) else 0.0
        amort = max(0.0, pmt_t - juros)
        saldo = max(0.0, saldo - amort)

        invest = obra_parcela if mes_contrato <= n_parc_obra else 0.0
        if t == horizonte:
            invest += p.capex_renovacao

        fcf = ebitda - ir - pmt_t - invest
        if t == horizonte:
            fcf += p.valor_residual_mes_60
        acum += fcf

        serie.append(
            {
                "mes": t, "mes_contrato": mes_contrato, "fase": "operacao",
                "alunos_total": alunos_total,
                "alunos_balcao": bal,
                "alunos_agregadores": agr,
                "faturamento_mensal": fat, "receita_anuidade": receita_anuidade,
                "deducoes": ded, "receita_liquida": rl,
                "impostos": imp, "receita_pos_impostos": rpi,
                "custos_variaveis": cvar, "folha": folha, "outros_fixos": outros,
                "aluguel": aluguel_m, "custo_pre_operacional": 0.0,
                "custos_op": custos_op, "ebitda_mensal": ebitda, "ir_csll": ir,
                "juros": juros, "amortizacao": amort, "pmt": pmt_t,
                "investimento": invest, "fcf_mensal": fcf, "fcf_acumulado": acum,
            }
        )

    return serie


def simular(
    demanda_total: float,
    p: Premissas,
    *,
    obra: float = 0.0,
    parcelas_obra: int = SIM_PARCELAS_OBRA_DEFAULT,
    equipamentos: float = 0.0,
    prazo_equipamentos: int = 0,
    juros_equipamentos_am: float = 0.0,
    taxa_franquia: float = SIM_TAXA_FRANQUIA,
) -> ViabilidadeResult:
    """Calcula TODOS os KPIs a partir de UMA serie mensal."""
    serie = gerar_serie_mensal_completa(
        demanda_total, p, obra=obra, parcelas_obra=parcelas_obra,
        equipamentos=equipamentos, prazo_equipamentos=prazo_equipamentos,
        juros_equipamentos_am=juros_equipamentos_am, taxa_franquia=taxa_franquia,
    )
    operacao = [r for r in serie if r["fase"] == "operacao"]
    # O mes de referencia do steady-state e o primeiro em REGIME PLENO: alunos
    # maduros E anuidade ja em cobranca. Sem isso a DRE de steady ficaria sem a
    # anuidade enquanto o break-even ja a considera — duas reguas diferentes.
    mes_ref = max(int(p.maturacao_meses), 1)
    if p.anuidade_valor > 0:
        mes_ref = max(mes_ref, int(p.anuidade_mes_inicio))
    steady = operacao[min(mes_ref, len(operacao)) - 1]

    fat = steady["faturamento_mensal"]
    ebitda = steady["ebitda_mensal"]
    margem = ebitda / fat if fat > 0 else 0.0

    capex_total = float(obra) + float(equipamentos)
    investimento_total = capex_total + float(taxa_franquia)
    pmt = next((r["pmt"] for r in operacao if r["pmt"] > 0), 0.0)

    payback = float("inf")
    for r in serie:
        if r["fcf_acumulado"] >= 0:
            payback = float(r["mes"])
            break

    mes_pos: int | None = None
    for i, r in enumerate(operacao):
        if r["fcf_mensal"] >= 0 and all(q["fcf_mensal"] >= 0 for q in operacao[i:]):
            mes_pos = int(r["mes"])
            break

    # Retorno: numerador e denominador coerentes DENTRO de cada otica.
    #   desalavancada -> resultado ANTES da PMT   / investimento CHEIO (capex+franquia)
    #   equity        -> resultado DEPOIS da PMT  / equity aportado (obra+franquia)
    # O ROIC anterior misturava as duas: numerador antes do financiamento sobre um
    # denominador de capex cheio como se fosse tudo equity — o modelo se beneficiava
    # do financiamento duas vezes.
    resultado_desalav = ebitda - steady["ir_csll"]
    resultado_equity = resultado_desalav - steady["pmt"]
    equity_investido = float(obra) + float(taxa_franquia)
    retorno_desalav = (
        resultado_desalav * 12.0 / investimento_total if investimento_total > 0 else 0.0
    )
    retorno_equity = resultado_equity * 12.0 / equity_investido if equity_investido > 0 else 0.0

    fluxos = [(r["mes_contrato"] - 1, r["fcf_mensal"]) for r in serie]
    tir_m = tir_mensal(fluxos)

    return ViabilidadeResult(
        faturamento_mensal_steady=float(fat),
        receita_liquida=float(steady["receita_liquida"]),
        receita_pos_impostos=float(steady["receita_pos_impostos"]),
        ebitda_mensal=float(ebitda),
        margem_ebitda_pct=float(margem),
        receita_anuidade_mensal=float(steady.get("receita_anuidade", 0.0) or 0.0),
        mes_referencia_steady=int(steady["mes"]),
        payback_meses=float(payback),
        roic_anual=float(retorno_desalav),
        lucro_liquido_mensal=float(resultado_desalav),
        flag_viavel=bool(margem >= SIM_MARGEM_VIAVEL_MIN and payback <= SIM_PAYBACK_VIAVEL_MAX),
        custos_op_mensal=float(steady["custos_op"]),
        custos_variaveis_mensal=float(steady["custos_variaveis"]),
        folha_mensal=float(steady["folha"]),
        custos_fixos_mensal=float(steady["outros_fixos"] + steady["aluguel"]),
        ir_csll_mensal=float(steady["ir_csll"]),
        despesa_financeira_mensal=float(steady["juros"]),
        resultado_apos_ir_mensal=float(resultado_desalav),
        capex_total=float(capex_total),
        taxa_franquia=float(taxa_franquia),
        investimento_total=float(investimento_total),
        pmt_mensal=float(pmt),
        juros_totais=float(sum(r["juros"] for r in serie)),
        retorno_anual_desalavancado=float(retorno_desalav),
        retorno_anual_equity=float(retorno_equity),
        tir_mensal=tir_m,
        tir_anual=((1.0 + tir_m) ** 12 - 1.0) if tir_m is not None else None,
        vpl=float(vpl(fluxos, p.taxa_desconto_aa)),
        mes_caixa_operacional_positivo=mes_pos,
        acumulado_mes_final=float(serie[-1]["fcf_acumulado"]),
        ticket_blended=float(p.ticket_blended),
        aluguel_teto=aluguel_teto_clusters(float(fat)),
        alunos_break_even_total=float(break_even_alunos(p)),
        alunos_break_even_caixa_total=float(break_even_alunos(p, incluir_pmt=pmt)),
        serie_mensal=serie,
    )


# ---------------------------------------------------------------------------
# ADAPTADORES DE COMPATIBILIDADE (semantica historica preservada)
# ---------------------------------------------------------------------------


def _premissas_legado(
    alunos_balcao: float, alunos_agregadores: float, aluguel_mes: float,
    ticket_medio: float, **kw: object,
) -> tuple[Premissas, float]:
    """Traduz a assinatura historica (balcao + agregadores ABSOLUTOS) em Premissas.

    Mantem: folha ABSOLUTA (`pessoal_mes`), IR/CSLL EFETIVO sobre a receita liquida,
    ticket de agregador ABSOLUTO, sem pre-abertura, sem reajuste, sem residual.
    """
    total = float(alunos_balcao) + float(alunos_agregadores)
    share = (float(alunos_balcao) / total) if total > 0 else 1.0
    g = kw.get
    return (
        Premissas(
            ticket_cheio=float(ticket_medio),
            share_balcao=share,
            ticket_agregador_absoluto=float(g("ticket_agregador", SIM_TICKET_AGREGADOR)),  # type: ignore[arg-type]
            personal_mes=float(g("personal_mes", SIM_PERSONAL_MES_RECEITA)),  # type: ignore[arg-type]
            churn=float(g("churn", SIM_CHURN)),  # type: ignore[arg-type]
            inadimplencia=float(g("inadimplencia", SIM_INADIMPLENCIA)),  # type: ignore[arg-type]
            devolucoes_pct=float(g("devolucoes_pct", SIM_DEVOLUCOES_PCT)),  # type: ignore[arg-type]
            pis=float(g("pis", SIM_PIS)), cofins=float(g("cofins", SIM_COFINS)),  # type: ignore[arg-type]
            iss=float(g("iss", SIM_ISS)),  # type: ignore[arg-type]
            royalties_pct=float(g("royalties_pct", SIM_ROYALTIES_PCT)),  # type: ignore[arg-type]
            marketing_pct=float(g("marketing_pct", SIM_MARKETING_PCT)),  # type: ignore[arg-type]
            manutencao_pct=float(g("manutencao_pct", SIM_MANUTENCAO_PCT)),  # type: ignore[arg-type]
            cartoes_pct=float(g("cartoes_pct", SIM_CARTOES_PCT)),  # type: ignore[arg-type]
            pessoal_mes_override=float(g("pessoal_mes", SIM_PESSOAL_MES)),  # type: ignore[arg-type]
            outros_fixos_mes=float(g("outros_fixos_mes", SIM_OUTROS_FIXOS_MES)),  # type: ignore[arg-type]
            aluguel_mes=float(aluguel_mes),
            custo_pre_operacional_mes=0.0,
            ir_modo=IR_MODO_EFETIVO,
            ir_efetivo=float(g("ir_efetivo", SIM_IR_EFETIVO)),  # type: ignore[arg-type]
            csll_efetivo=float(g("csll_efetivo", SIM_CSLL_EFETIVO)),  # type: ignore[arg-type]
            reajuste_ticket_aa=0.0, reajuste_aluguel_aa=0.0, reajuste_custos_aa=0.0,
            maturacao_meses=int(g("maturacao_meses", SIM_MATURACAO_MESES)),  # type: ignore[call-overload]
            alunos_inicial=float(g("alunos_inicial", SIM_ALUNOS_INICIAL)),  # type: ignore[arg-type]
            meses_pre_abertura=0,
            carencia_aluguel_meses=0,
            rampa_apenas_balcao=True,
            # A anuidade e uma linha de receita NOVA (FIN-VIAB-01). O caminho legado
            # tem que continuar reproduzindo o motor antigo ao centavo, entao aqui ela
            # fica desligada; quem quiser a anuidade usa Premissas/simular().
            anuidade_valor=0.0,
        ),
        total,
    )


def _capex_legado(capex: float | None, coef_capex_m2: float | None, m2: float) -> float:
    if capex is None and coef_capex_m2 is not None:
        return float(coef_capex_m2) * float(m2)
    if capex is None:
        return float(SIM_CAPEX_DEFAULT)
    return float(capex)


def viabilidade(
    alunos_maturidade: float, m2: float, aluguel_mes: float, ticket_medio: float, **kw: object
) -> ViabilidadeResult:
    """ADAPTADOR historico. `alunos_maturidade` = alunos de BALCAO.

    Preserva a semantica anterior byte-a-byte para `backtest_viabilidade`,
    `batch_viabilidade`, `excel_export` e `risco`. O caminho novo e `simular()`.
    """
    resto = {k: v for k, v in kw.items() if k != "alunos_agregadores"}
    p, total = _premissas_legado(
        alunos_maturidade,
        float(kw.get("alunos_agregadores", SIM_ALUNOS_AGREGADORES_MATURIDADE)),  # type: ignore[arg-type]
        aluguel_mes, ticket_medio, **resto,
    )
    capex_ef = _capex_legado(
        kw.get("capex"), kw.get("coef_capex_m2"), m2  # type: ignore[arg-type]
    )
    fin_pct = float(kw.get("capex_financiado_pct", 0.0))  # type: ignore[arg-type]
    financiado = capex_ef * fin_pct
    return simular(
        total, p,
        obra=capex_ef - financiado,
        parcelas_obra=1,
        equipamentos=financiado,
        prazo_equipamentos=int(kw.get("prazo_financiamento_meses", 36)) if financiado > 0 else 0,  # type: ignore[call-overload]
        juros_equipamentos_am=float(kw.get("juros_financiamento_am", 0.018)),  # type: ignore[arg-type]
        taxa_franquia=0.0,
    )


def gerar_serie_mensal(
    alunos_maturidade: float, m2: float, aluguel_mes: float, ticket_medio: float, **kw: object
) -> list[dict]:
    """ADAPTADOR historico: 60 linhas de OPERACAO com o shape antigo.

    Campos: mes, alunos_balcao, faturamento_mensal, ebitda_mensal, fcf_acumulado.
    """
    r = viabilidade(alunos_maturidade, m2, aluguel_mes, ticket_medio, **kw)
    return [
        {
            "mes": row["mes"],
            "alunos_balcao": float(row["alunos_balcao"]),
            "faturamento_mensal": float(row["faturamento_mensal"]),
            "ebitda_mensal": float(row["ebitda_mensal"]),
            "fcf_acumulado": float(row["fcf_acumulado"]),
        }
        for row in r.serie_mensal
        if row["fase"] == "operacao"
    ]


def aluguel_teto(
    alunos_maturidade: float, m2: float, ticket_medio: float,
    margem_alvo: float = 0.10, **kwargs: object,
) -> float:
    """DEPRECATED (FIN-VIAB-01) — inversao do aluguel por margem EBITDA-alvo.

    NAO e mais o aluguel-teto do produto: tela e PDF consomem
    `aluguel_teto_clusters()` (% do faturamento). Esta funcao devolvia
    R$105.813,13 onde a tela mostrava R$55.535,18 no mesmo cenario.
    Mantida so para chamadas historicas; sem consumidor no piloto web nem no PDF.
    """

    def _obj(alug: float) -> float:
        return (
            viabilidade(alunos_maturidade, m2, alug, ticket_medio, **kwargs).margem_ebitda_pct
            - margem_alvo
        )

    if _obj(0.0) < 0:
        return 0.0
    _agr = float(kwargs.get("alunos_agregadores", SIM_ALUNOS_AGREGADORES_MATURIDADE))  # type: ignore[arg-type]
    _tag = float(kwargs.get("ticket_agregador", SIM_TICKET_AGREGADOR))  # type: ignore[arg-type]
    _per = float(kwargs.get("personal_mes", SIM_PERSONAL_MES_RECEITA))  # type: ignore[arg-type]
    alug_sup = (alunos_maturidade * ticket_medio + _agr * _tag + _per) * 2.0
    if alug_sup <= 0:
        return 0.0
    if _obj(alug_sup) > 0:
        return float(alug_sup)
    return float(brentq(_obj, 0.0, alug_sup, xtol=1.0, maxiter=100))


def alunos_minimos_viaveis(
    m2: float, aluguel_mes: float, ticket_medio: float,
    margem_alvo: float = 0.0, **kwargs: object,
) -> float:
    """DEPRECATED (FIN-VIAB-01) — break-even variando SO o balcao.

    Os agregadores ficam congelados na premissa, entao o numero NAO e comparavel
    com a demanda total que o operador digita. O canonico e `break_even_alunos()`,
    em alunos TOTAIS com o mix escalando.
    """
    alunos_inicial = float(kwargs.get("alunos_inicial", SIM_ALUNOS_INICIAL))  # type: ignore[arg-type]

    def _obj(alunos: float) -> float:
        return (
            viabilidade(alunos, m2, aluguel_mes, ticket_medio, **kwargs).margem_ebitda_pct
            - margem_alvo
        )

    if _obj(5000.0) < 0:
        return float("inf")
    piso = max(alunos_inicial, 1.0)
    if _obj(piso) >= 0:
        return float(piso)
    return float(brentq(_obj, piso, 5000.0, xtol=0.5, maxiter=100))


def m2_otimo(
    alunos_maturidade: float, aluguel_por_m2: float, ticket_medio: float,
    coef_capex_m2: float, margem_alvo: float = 0.10,
    m2_min: float = 750.0, m2_max: float = 2800.0,
) -> float:
    """Menor m2 em [m2_min, m2_max] que atinge a margem_alvo."""

    def _obj(m2: float) -> float:
        return (
            viabilidade(
                alunos_maturidade, m2, aluguel_mes=aluguel_por_m2 * m2,
                ticket_medio=ticket_medio, coef_capex_m2=coef_capex_m2,
            ).margem_ebitda_pct
            - margem_alvo
        )

    if _obj(m2_min) >= 0:
        return float(m2_min)
    if _obj(m2_max) < 0:
        return float(m2_max)
    return float(brentq(_obj, m2_min, m2_max, xtol=1.0, maxiter=100))


__all__ = [
    "Premissas", "ViabilidadeResult", "simular", "gerar_serie_mensal_completa",
    "break_even_alunos", "alunos_para_margem", "aluguel_teto_clusters", "pmt_price", "tir_mensal", "vpl",
    "IR_MODO_FAIXA", "IR_MODO_EFETIVO",
    "viabilidade", "gerar_serie_mensal", "aluguel_teto", "alunos_minimos_viaveis", "m2_otimo",
]
