"""Golden financeiro do simulador de viabilidade (FIN-VIAB-01).

POR QUE ESTE ARQUIVO EXISTE
---------------------------
Ate este ciclo o repo nao tinha NENHUM golden financeiro: os asserts do PDF
contavam paginas, os testes de grafico validavam so a dimensao do PNG e
batch/backtest MOCKAVAM o motor. A suite ficava verde com o produto quebrado --
foi exatamente assim que os 17 defeitos do FIN-VIAB-01 (5 series mensais
independentes, 9 KPIs com implementacao dupla) passaram despercebidos.

O QUE ESTE ARQUIVO TRAVA
------------------------
1. GOLDEN "Boulevard Shopping Londrina": todos os numeros MEDIDOS no motor com a
   ANUIDADE LIGADA, com tolerancia de R$0,01.
2. A linha de ANUIDADE (R$99/ano por aluno de balcao que completa 12 meses,
   reconhecida pro-rata mensal): mes de inicio, elegibilidade derivada do churn,
   exclusao do agregador, aditividade e o deslocamento do mes de referencia.
3. Cinco cenarios de fronteira (p10, p90, carencia, equipamentos a vista e o
   MESMO golden com a anuidade desligada) com o resultado REAL medido --
   inclusive quando o resultado e desconfortavel (o p10 opera ACIMA do
   break-even de EBITDA e mesmo assim NUNCA paga o investimento, porque fica
   abaixo do break-even DE CAIXA).
4. Identidades contabeis mes a mes, parametrizadas sobre os 6 cenarios.
5. As premissas do `config.py`: mudar um coeficiente sem atualizar o golden
   deixa a suite vermelha em vez de mudar o numero do comite em silencio.

REGRA DA ANUIDADE (decidida por Felipe em 2026-07-24, nao rediscutir aqui):
R$99 UMA VEZ POR ANO por aluno de BALCAO que completa 12 meses; agregador nao
paga (o agregador remunera por acesso); elegibilidade DERIVADA do churn
((1-churn)^12 = 47,59% com churn 6%); reconhecimento PRO-RATA MENSAL (99/12) a
partir do mes 12. Consequencia estrutural: o mes de referencia do steady-state
passa de `maturacao_meses` (8) para max(maturacao, anuidade_mes_inicio) = 12,
porque so ai o regime e pleno (alunos maduros E anuidade em cobranca).

FOLHA FIXA DESDE O MES 1 (decisao de Felipe, 2026-07-24; secao 6 deste arquivo)
------------------------------------------------------------------------------
Era o defeito reportado: "a folha esta escalando junto com a unidade". Antes a
folha era `folha_pct` x faturamento DO MES, entao encolhia com a rampa -- o que
equivale a supor que se contrata gente na medida em que o aluno entra. Agora ela
e dimensionada UMA vez pelo faturamento MADURO (`Premissas.folha_fixa_mes()`) e
paga integralmente desde o mes 1, reajustando anualmente como os demais custos.
Consequencias que este arquivo trava:
  - a folha deixou de ser percentual e virou CUSTO FIXO -> `custo_fixo_total_mes()`
    (a propriedade `custo_fixo_base_mes` NAO EXISTE MAIS);
  - `fator_receita_para_ebitda` NAO subtrai mais `folha_pct`: k = 0,798985
    (era 0,628985) -- `folha_efetiva_pct` continua existindo, mas fora do fator;
  - `break_even_alunos(p, demanda_total, *, incluir_pmt=0)` e
    `alunos_para_margem(p, margem_alvo, demanda_total)` passaram a RECEBER a
    demanda assumida, porque e ela que dimensiona a folha.
No golden isso responde por QUASE TODO o deslocamento de indicador -- medido
com a franquia ainda a vista, para nao misturar as duas mudancas: break-even
840,6 -> 1.152,0; payback 28 -> 31; TIR 45,48% -> 38,65%; VPL 986.172,80 ->
847.242,35; acumulado M60 1.795.729,88 -> 1.645.454,56. O mes de STEADY nao
mudou (la o faturamento ja era o maduro), nem o retorno de steady.

TAXA DE FRANQUIA PARCELADA 4x SEM JUROS (mesma decisao; secao 7 deste arquivo)
-----------------------------------------------------------------------------
Antes a taxa saia INTEIRA do caixa no M-4. Agora cai em `parcelas_franquia`
(default 4) parcelas iguais nos meses de CONTRATO 1..N, junto da obra. E SO
timing de caixa: EBITDA, margem e break-even NAO mudam; payback e acumulado M60
tambem NAO, porque as 4 parcelas cabem dentro da janela M-4..M-1. O efeito
isolado e TIR +0,33pp e VPL +R$2.241,80 -- medido aqui contra o cenario
`franquia_a_vista` (`parcelas_franquia=1`), que e a regressao do default.

Convencao do repo (ver `test_parametros_canonicos.py`): casos HARDCODED no
proprio arquivo, sem fixture externa.

READ-ONLY sobre o M1: nao toca score_priorizacao, pesos nem artefatos oficiais.
"""

from __future__ import annotations

import json
import math

import pytest

from motor_expansao.dimensionamento import config as cfg
from motor_expansao.dimensionamento.simulador import (
    Premissas,
    aluguel_teto_clusters,
    alunos_para_margem,
    break_even_alunos,
    gerar_serie_mensal_completa,
    pmt_price,
    simular,
)

# ---------------------------------------------------------------------------
# Caso GOLDEN -- Boulevard Shopping Londrina
# ---------------------------------------------------------------------------

CENTAVO = 0.01          # tolerancia de dinheiro
RATE = 1e-6             # tolerancia de taxa/percentual (fracao, nao pp)

GOLDEN_DEMANDA = 2304.0
GOLDEN_PREMISSAS: dict[str, object] = {
    "ticket_cheio": 147.0,
    "aluguel_mes": 30_000.0,
    "maturacao_meses": 8,
    "carencia_aluguel_meses": 0,
}
GOLDEN_INVESTIMENTO: dict[str, object] = {
    "obra": 600_000.0,
    "parcelas_obra": 4,
    "equipamentos": 1_400_000.0,
    "prazo_equipamentos": 60,
    "juros_equipamentos_am": 0.018,
    "taxa_franquia": 160_000.0,
}

# Cenarios de fronteira: (demanda, overrides de Premissas, overrides de simular).
# p10/p90 sao a faixa de comparaveis do caso golden. `sem_anuidade` e o MESMO
# golden com a linha de anuidade desligada -- serve de contraprova: e o cenario
# que os goldens pinavam antes de a anuidade ser religada. `franquia_a_vista`
# (`parcelas_franquia=1`) e a contraprova do parcelamento em 4x: reproduz o
# comportamento anterior, em que a taxa saia inteira no M-4.
CENARIOS: dict[str, tuple[float, dict, dict]] = {
    "golden": (GOLDEN_DEMANDA, {}, {}),
    "p10": (1189.0, {}, {}),
    "p90": (3034.0, {}, {}),
    "carencia_4": (GOLDEN_DEMANDA, {"carencia_aluguel_meses": 4}, {}),
    "equip_a_vista": (GOLDEN_DEMANDA, {}, {"prazo_equipamentos": 0}),
    "sem_anuidade": (GOLDEN_DEMANDA, {"anuidade_valor": 0.0}, {}),
    "franquia_a_vista": (GOLDEN_DEMANDA, {}, {"parcelas_franquia": 1}),
}


def premissas(**over: object) -> Premissas:
    kw = dict(GOLDEN_PREMISSAS)
    kw.update(over)
    return Premissas(**kw)  # type: ignore[arg-type]


def rodar(demanda: float = GOLDEN_DEMANDA, *, prem: dict | None = None, sim: dict | None = None):
    kw = dict(GOLDEN_INVESTIMENTO)
    kw.update(sim or {})
    return simular(demanda, premissas(**(prem or {})), **kw)  # type: ignore[arg-type]


def cenario(nome: str):
    demanda, prem, sim = CENARIOS[nome]
    return rodar(demanda, prem=prem, sim=sim)


def parcelas_franquia_de(nome: str) -> int:
    """Numero de parcelas da franquia EFETIVO no cenario (default = o do config)."""
    _, _, sim = CENARIOS[nome]
    return int(sim.get("parcelas_franquia", cfg.SIM_PARCELAS_FRANQUIA_DEFAULT))


def folha_fixa_esperada(p: Premissas, demanda_total: float) -> float:
    """Folha mensal reconstruida FORA do motor: folha_pct x faturamento MADURO.

    Deliberadamente NAO usa `p.folha_fixa_mes()`: o ponto e travar a derivacao. O
    faturamento maduro e o de REGIME PLENO a precos do ano 1 -- inclui a anuidade
    quando ela existe, porque o regime pleno a tem. Por isso o cenario sem anuidade
    tem folha MENOR: a base de dimensionamento e menor.
    """
    maduro = p.faturamento(demanda_total, com_anuidade=p.anuidade_valor > 0)
    return p.folha_pct * maduro


def fator_reajuste(mes: int, taxa_aa: float) -> float:
    """Degrau anual a partir do mes 13; pre-abertura (mes < 1) nao reajusta.

    Reimplementado aqui de proposito: o teste NAO pode importar o helper privado
    do motor, senao validaria o motor contra ele mesmo.
    """
    if mes < 1 or taxa_aa <= 0:
        return 1.0
    return (1.0 + taxa_aa) ** ((mes - 1) // 12)


def anuidade_por_aluno_mes(p: Premissas) -> float:
    """Anuidade mensal por aluno ELEGIVEL, reconstruida do zero.

    Deliberadamente NAO usa `p.anuidade_por_aluno_balcao_mes`: o ponto do teste e
    travar a derivacao (valor anual x (1-churn)^mes_inicio, dividido por 12 quando
    pro-rata). Assume a elegibilidade DERIVADA -- nenhum cenario deste arquivo usa
    o override `anuidade_elegivel_pct`.
    """
    if p.anuidade_valor <= 0:
        return 0.0
    elegivel = (1.0 - p.churn) ** int(p.anuidade_mes_inicio)
    por_ano = p.anuidade_valor * elegivel
    return por_ano / 12.0 if p.anuidade_pro_rata else por_ano


def receita_anuidade_esperada(
    p: Premissas, mes: int, alunos_balcao: float, alunos_agregadores: float
) -> float:
    """Receita de anuidade do mes `mes`, reconstruida fora do motor."""
    if p.anuidade_valor <= 0 or mes < max(int(p.anuidade_mes_inicio), 1):
        return 0.0
    base = (
        alunos_balcao
        if p.anuidade_apenas_balcao
        else alunos_balcao + alunos_agregadores
    )
    return base * anuidade_por_aluno_mes(p)


def receita_por_aluno_esperada(p: Premissas) -> float:
    """Receita mensal por aluno TOTAL em regime pleno = ticket blended + anuidade."""
    share = p.share_balcao if p.anuidade_apenas_balcao else 1.0
    return p.ticket_blended + anuidade_por_aluno_mes(p) * share


# ---------------------------------------------------------------------------
# 1) GOLDEN -- Boulevard Shopping Londrina
# ---------------------------------------------------------------------------


def test_golden_tickets():
    p = premissas()
    # Ticket do agregador ACOPLADO ao cheio (era R$82 absoluto e desacoplado).
    assert p.ticket_agregador == pytest.approx(88.20, abs=CENTAVO)
    assert p.ticket_agregador == pytest.approx(p.ticket_cheio * 0.60, abs=1e-9)
    # Blended: liquido de churn e inadimplencia, por aluno TOTAL, sem personal.
    assert p.ticket_blended == pytest.approx(120.23, abs=CENTAVO)
    assert rodar().ticket_blended == pytest.approx(p.ticket_blended, abs=1e-12)
    # A receita por aluno em regime pleno e MAIOR que o blended: a anuidade entra.
    assert p.receita_por_aluno_total == pytest.approx(122.9416524, abs=1e-6)
    assert p.receita_por_aluno_total > p.ticket_blended


def test_golden_premissas_derivadas():
    p = premissas()
    assert p.share_balcao == pytest.approx(0.69, abs=1e-12)
    assert p.impostos_receita_pct == pytest.approx(0.0665, abs=1e-12)
    assert p.custo_variavel_pct == pytest.approx(0.1305, abs=1e-12)
    assert p.horizonte_meses == 60
    assert p.meses_pre_abertura == 4

    # A FOLHA SAIU DO FATOR (decisao de Felipe, 2026-07-24). `folha_efetiva_pct`
    # continua existindo -- ela e o que dimensiona a folha e o que zera quando ha
    # override absoluto -- mas NAO entra mais em k:
    #   k = (1 - deducoes) * (1 - impostos - variavel) = 0,995 * 0,803 = 0,798985
    assert p.folha_efetiva_pct == pytest.approx(0.17, abs=1e-12)
    assert p.fator_receita_para_ebitda == pytest.approx(0.798985, abs=1e-9)
    assert p.fator_receita_para_ebitda == pytest.approx(
        (1.0 - p.devolucoes_pct) * (1.0 - p.impostos_receita_pct - p.custo_variavel_pct),
        abs=1e-12,
    )
    # Trava de FORMA (nao de valor): o k de hoje MENOS a folha_pct e exatamente o k
    # antigo. Se alguem reintroduzir a folha no fator, o assert de cima quebra e este
    # documenta qual era o numero de antes.
    assert p.fator_receita_para_ebitda - p.folha_efetiva_pct == pytest.approx(
        0.628985, abs=1e-9
    )

    # A folha e CUSTO FIXO: dimensionada pelo faturamento MADURO e paga desde o mes 1.
    assert p.folha_fixa_mes(GOLDEN_DEMANDA) == pytest.approx(49_003.79, abs=CENTAVO)
    assert p.folha_fixa_mes(GOLDEN_DEMANDA) == pytest.approx(
        folha_fixa_esperada(p, GOLDEN_DEMANDA), abs=1e-9
    )
    assert p.faturamento_maduro(GOLDEN_DEMANDA) == pytest.approx(288_257.57, abs=CENTAVO)

    # `custo_fixo_base_mes` (so os outros fixos) NAO EXISTE MAIS: virou
    # `custo_fixo_total_mes(demanda)`, que ja soma a folha.
    assert not hasattr(p, "custo_fixo_base_mes")
    assert p.outros_fixos_mes == pytest.approx(38_150.00, abs=CENTAVO)
    assert p.custo_fixo_total_mes(GOLDEN_DEMANDA) == pytest.approx(87_153.79, abs=CENTAVO)
    assert p.custo_fixo_total_mes(GOLDEN_DEMANDA) == pytest.approx(
        p.outros_fixos_mes + p.folha_fixa_mes(GOLDEN_DEMANDA), abs=1e-9
    )


def test_golden_dre():
    r = rodar()
    deducoes = r.faturamento_mensal_steady - r.receita_liquida
    impostos = r.receita_liquida - r.receita_pos_impostos

    # O steady-state e lido no mes 12 (regime pleno: alunos maduros E anuidade).
    assert r.mes_referencia_steady == 12
    assert r.faturamento_mensal_steady == pytest.approx(288_257.57, abs=CENTAVO)
    assert r.receita_anuidade_mensal == pytest.approx(6_241.94, abs=CENTAVO)
    assert deducoes == pytest.approx(1_441.29, abs=CENTAVO)
    assert r.receita_liquida == pytest.approx(286_816.28, abs=CENTAVO)
    assert impostos == pytest.approx(19_073.28, abs=CENTAVO)
    assert r.receita_pos_impostos == pytest.approx(267_743.00, abs=CENTAVO)

    # As TRES parcelas do custo operacional (antes so o total era exposto).
    # A folha nao muda no steady: la o faturamento JA e o maduro que a dimensiona.
    assert r.custos_variaveis_mensal == pytest.approx(37_429.52, abs=CENTAVO)
    assert r.folha_mensal == pytest.approx(49_003.79, abs=CENTAVO)
    assert r.folha_mensal == pytest.approx(
        premissas().folha_fixa_mes(GOLDEN_DEMANDA), abs=1e-9
    )
    assert r.custos_fixos_mensal == pytest.approx(68_150.00, abs=CENTAVO)
    assert r.custos_op_mensal == pytest.approx(154_583.31, abs=CENTAVO)

    assert r.ebitda_mensal == pytest.approx(113_159.69, abs=CENTAVO)
    assert r.margem_ebitda_pct == pytest.approx(0.3925645, abs=RATE)
    # Faixa do adicional de 10% de IRPJ explicita (antes embutida como se TODA
    # a base excedesse o limite).
    assert r.ir_csll_mensal == pytest.approx(29_362.42, abs=CENTAVO)
    assert r.despesa_financeira_mensal == pytest.approx(22_349.12, abs=CENTAVO)
    assert r.resultado_apos_ir_mensal == pytest.approx(83_797.26, abs=CENTAVO)


def test_golden_investimento_e_financiamento():
    r = rodar()
    assert r.capex_total == pytest.approx(2_000_000.00, abs=CENTAVO)
    assert r.taxa_franquia == pytest.approx(160_000.00, abs=CENTAVO)
    assert r.investimento_total == pytest.approx(2_160_000.00, abs=CENTAVO)
    assert r.pmt_mensal == pytest.approx(38_348.75, abs=CENTAVO)
    assert r.juros_totais == pytest.approx(900_925.18, abs=CENTAVO)
    # PMT do resultado == PMT Price do principal financiado.
    assert r.pmt_mensal == pytest.approx(pmt_price(1_400_000.0, 0.018, 60), abs=1e-9)


def test_golden_break_even_em_alunos_totais():
    """NUMERO MUDOU DE PROPOSITO: a folha virou custo FIXO dimensionado pela demanda.

    Antes a folha era percentual da receita do MES, entao encolhia junto com o volume
    e o break-even saia otimista (840,6). A pergunta certa e "montei a casa para 2.304
    alunos; com quantos eu empato?" -- e a folha continua sendo paga integralmente se o
    volume nao vier. Por isso as assinaturas passaram a RECEBER a demanda assumida.
    """
    p = premissas()
    r = rodar()
    # UNIDADE: alunos TOTAIS com o mix 69/31 escalando (antes: 632 alunos de BALCAO,
    # comparados na tela contra uma demanda TOTAL de 2.304).
    assert r.alunos_break_even_total == pytest.approx(1_152.00, abs=0.05)
    assert r.alunos_break_even_caixa_total == pytest.approx(1_542.40, abs=0.05)
    assert r.alunos_break_even_total < r.alunos_break_even_caixa_total
    # A demanda assumida e argumento OBRIGATORIO das duas funcoes (ela dimensiona a folha).
    assert break_even_alunos(p, GOLDEN_DEMANDA) == pytest.approx(
        r.alunos_break_even_total, abs=1e-9
    )
    with pytest.raises(TypeError):
        break_even_alunos(p)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        alunos_para_margem(p, 0.10)  # type: ignore[call-arg]
    # Margem-alvo de 10% na MESMA unidade do break-even (era 1.007,24 com folha percentual).
    assert alunos_para_margem(p, 0.10, GOLDEN_DEMANDA) == pytest.approx(1_322.62, abs=0.05)
    assert alunos_para_margem(p, 0.10, GOLDEN_DEMANDA) > r.alunos_break_even_total

    # Contraprova da regra ANTIGA (folha percentual, diluida pelo volume), reconstruida
    # fora do motor: dava 840,6 -- o numero que o comite via antes.
    k_antigo = p.fator_receita_para_ebitda - p.folha_efetiva_pct
    be_antigo = (
        (p.outros_fixos_mes + p.aluguel_mes) / k_antigo - p.personal_mes
    ) / p.receita_por_aluno_total
    assert be_antigo == pytest.approx(840.64, abs=0.05)
    assert r.alunos_break_even_total > be_antigo


def test_golden_payback_retorno_tir_vpl():
    """Payback/TIR/VPL/acumulado MUDARAM: e quase todo o preco da folha fixa.

    Decomposicao medida, das duas mudancas de 2026-07-24:
      - folha fixa (com a franquia ainda a vista): payback 28 -> 31,
        TIR 45,4822% -> 38,6474%, VPL 986.172,80 -> 847.242,35,
        acumulado M60 1.795.729,88 -> 1.645.454,56;
      - franquia 4x, por cima disso: TIR 38,6474% -> 38,9803% (+0,33pp) e
        VPL 847.242,35 -> 849.484,15 (+R$2.241,80). Payback e acumulado M60 ficam
        IDENTICOS (secao 7).
    O retorno de steady (desalavancado e equity) NAO muda em nenhuma das duas: no
    steady a folha ja era a madura e o parcelamento nao e resultado.
    """
    r = rodar()
    # Payback unico: antes 35 no KPI e 33 no grafico.
    assert r.payback_meses == 31.0
    assert r.mes_caixa_operacional_positivo == 6
    # Otica PADRAO = DESALAVANCADA.
    assert r.retorno_anual_desalavancado == pytest.approx(0.4655403, abs=RATE)
    assert r.roic_anual == pytest.approx(r.retorno_anual_desalavancado, abs=1e-12)
    # Equity e visao SECUNDARIA -- existe, mas nunca no mesmo KPI.
    assert r.retorno_anual_equity == pytest.approx(0.7176080, abs=RATE)
    assert r.tir_anual is not None
    assert r.tir_anual == pytest.approx(0.3898033, abs=RATE)
    # 4a rodada: fluxo DO SOCIO descontado a taxa DO SOCIO (Ke=27,08%, derivada de
    # Ku=25% e Kd=23,87%). Era 849.484,15 a 12% — taxa de projeto num fluxo de socio.
    assert r.vpl == pytest.approx(276_103.24, abs=CENTAVO)
    assert r.vpl_socio == pytest.approx(276_103.24, abs=CENTAVO)
    assert r.vpl_negocio == pytest.approx(312_177.18, abs=CENTAVO)
    assert r.acumulado_mes_final == pytest.approx(1_645_454.56, abs=CENTAVO)
    assert r.flag_viavel is True


def test_golden_aluguel_teto_tres_faixas():
    r = rodar()
    assert r.aluguel_teto["ideal"] == pytest.approx(43_238.64, abs=CENTAVO)
    assert r.aluguel_teto["teto"] == pytest.approx(57_651.51, abs=CENTAVO)
    assert r.aluguel_teto["excecao"] == pytest.approx(86_477.27, abs=CENTAVO)
    # O canonico exibido no card grande e o TETO (20%), nao a excecao (30%) —
    # decisao de Felipe 2026-07-24: o card mostra o limite que a operacao defende;
    # a excecao e caso de excecao, nao referencia. As 3 faixas seguem no detalhe.
    assert r.aluguel_teto["canonico"] == pytest.approx(r.aluguel_teto["teto"], abs=1e-12)
    assert r.aluguel_teto["canonico"] < r.aluguel_teto["excecao"]
    # Base = faturamento bruto steady (nao inversao por margem EBITDA).
    assert r.aluguel_teto == aluguel_teto_clusters(r.faturamento_mensal_steady)


def test_golden_ebitda_do_mes_1_e_negativo():
    """Com a folha FIXA o mes 1 fica MUITO mais negativo: -43.464,47 (era -10.139,56).

    Agora o custo e integral desde o mes 1 INCLUSIVE na folha -- e essa a diferenca.
    A contraprova reconstroi a regra antiga (folha percentual da receita DO MES) fora
    do motor e mostra que ela devolvia exatamente o -10.139,56 de antes.
    """
    p = premissas()
    r = rodar()
    m1 = next(x for x in r.serie_mensal if x["mes"] == 1)
    # O custo e INTEGRAL desde o mes 1 -- ele nao acompanha a rampa de alunos.
    assert m1["ebitda_mensal"] == pytest.approx(-43_464.47, abs=CENTAVO)
    assert m1["alunos_total"] == pytest.approx(725.5, abs=0.01)
    assert m1["custos_op"] == pytest.approx(
        m1["custos_variaveis"] + m1["folha"] + m1["outros_fixos"] + m1["aluguel"], abs=1e-9
    )
    # No mes 1 nao ha anuidade: ninguem completou 12 meses ainda.
    assert m1["receita_anuidade"] == 0.0

    # A folha do mes 1 e a folha MADURA (nao a fracao do faturamento do mes 1): a
    # equipe existe antes dos alunos. Com 725,5 de 2.304 alunos, a folha escalonada
    # seria ~31% da fixa.
    assert m1["folha"] == pytest.approx(49_003.79, abs=CENTAVO)
    assert m1["folha"] == pytest.approx(r.folha_mensal, abs=1e-9)
    assert m1["folha"] > p.folha_pct * m1["faturamento_mensal"]

    # Contraprova da regra ANTIGA, reconstruida fora do motor.
    ebitda_antigo = (
        m1["faturamento_mensal"] * (p.fator_receita_para_ebitda - p.folha_efetiva_pct)
        - p.outros_fixos_mes
        - p.aluguel_mes
    )
    assert ebitda_antigo == pytest.approx(-10_139.56, abs=CENTAVO)
    assert m1["ebitda_mensal"] < ebitda_antigo
    # E a diferenca e EXATAMENTE a folha nao-diluida do mes 1.
    assert ebitda_antigo - m1["ebitda_mensal"] == pytest.approx(
        m1["folha"] - p.folha_pct * m1["faturamento_mensal"], abs=1e-6
    )


def test_golden_serie_tem_a_linha_do_tempo_completa():
    r = rodar()
    assert len(r.serie_mensal) == 64                     # M-4..M-1 + M1..M60
    assert [x["mes"] for x in r.serie_mensal[:4]] == [-4, -3, -2, -1]
    assert r.serie_mensal[4]["mes"] == 1
    assert r.serie_mensal[-1]["mes"] == 60
    assert all(x["fase"] == "pre_operacional" for x in r.serie_mensal[:4])
    assert all(x["fase"] == "operacao" for x in r.serie_mensal[4:])
    # mes_contrato conta 1..N desde a ENTREGA (M-4), nao desde a abertura.
    assert [x["mes_contrato"] for x in r.serie_mensal[:5]] == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# 2) ANUIDADE -- a linha de receita religada em 2026-07-24
# ---------------------------------------------------------------------------


def test_anuidade_zero_ate_o_mes_11_e_constante_do_mes_12_em_diante():
    """R$99/ano so existe depois que a 1a safra completa 12 meses."""
    r = rodar()
    operacao = [x for x in r.serie_mensal if x["fase"] == "operacao"]

    antes = [x for x in operacao if x["mes"] < 12]
    assert [x["mes"] for x in antes] == list(range(1, 12))
    assert all(x["receita_anuidade"] == 0.0 for x in antes), "anuidade vazou antes do mes 12"

    depois = [x for x in operacao if x["mes"] >= 12]
    assert [x["mes"] for x in depois] == list(range(12, 61))
    for x in depois:
        assert x["receita_anuidade"] == pytest.approx(6_241.94, abs=CENTAVO), f"mes {x['mes']}"

    # A pre-abertura nao tem receita nenhuma, muito menos anuidade.
    assert all(x["receita_anuidade"] == 0.0 for x in r.serie_mensal if x["fase"] != "operacao")

    # E o valor de steady exposto no resultado e exatamente o do mes de referencia.
    m12 = next(x for x in operacao if x["mes"] == 12)
    assert r.receita_anuidade_mensal == pytest.approx(m12["receita_anuidade"], abs=1e-12)


def test_anuidade_elegibilidade_deriva_do_churn_sem_constante_paralela():
    """Nem todo aluno chega aos 12 meses: a fracao e (1-churn)^12, nao numero magico.

    Mexer no churn tem de mover a elegibilidade SOZINHO -- sem tocar constante
    nenhuma do config nem passar `anuidade_elegivel_pct`.
    """
    p6 = premissas(churn=0.06)
    p8 = premissas(churn=0.08)

    assert p6.anuidade_elegivel_pct is None        # sem override: e derivada mesmo
    assert p8.anuidade_elegivel_pct is None
    assert p6.anuidade_elegivel_efetivo == pytest.approx(0.94**12, abs=1e-12)
    assert p6.anuidade_elegivel_efetivo == pytest.approx(0.4759203, abs=1e-6)
    assert p8.anuidade_elegivel_efetivo == pytest.approx(0.92**12, abs=1e-12)
    assert p8.anuidade_elegivel_efetivo == pytest.approx(0.3676664, abs=1e-6)
    assert p8.anuidade_elegivel_efetivo < p6.anuidade_elegivel_efetivo

    # Reconhecimento PRO-RATA: 99 x elegibilidade / 12 por aluno de balcao por mes.
    assert p6.anuidade_por_aluno_balcao_mes == pytest.approx(3.9263426, abs=1e-6)
    assert p6.anuidade_por_aluno_balcao_mes == pytest.approx(
        99.0 * 0.94**12 / 12.0, abs=1e-12
    )
    # Sem pro-rata seria o lancamento unico anual (12x maior) -- degrau falso no caixa.
    assert premissas(anuidade_pro_rata=False).anuidade_por_aluno_balcao_mes == pytest.approx(
        99.0 * 0.94**12, abs=1e-12
    )


def test_anuidade_apenas_balcao_exclui_o_agregador():
    """Gympass/TotalPass nao paga anuidade: o agregador remunera por acesso."""
    so_balcao = rodar(prem={"share_balcao": 1.0})
    so_agregador = rodar(prem={"share_balcao": 0.0})
    m12_bal = next(x for x in so_balcao.serie_mensal if x["mes"] == 12)
    m12_agr = next(x for x in so_agregador.serie_mensal if x["mes"] == 12)

    assert m12_bal["alunos_agregadores"] == pytest.approx(0.0, abs=1e-9)
    assert m12_bal["receita_anuidade"] == pytest.approx(9_046.29, abs=CENTAVO)
    assert m12_bal["receita_anuidade"] == pytest.approx(
        GOLDEN_DEMANDA * premissas().anuidade_por_aluno_balcao_mes, abs=1e-6
    )

    # 100% agregador -> anuidade ZERO em todo o horizonte.
    assert m12_agr["alunos_balcao"] == pytest.approx(0.0, abs=1e-9)
    assert m12_agr["receita_anuidade"] == 0.0
    assert all(x["receita_anuidade"] == 0.0 for x in so_agregador.serie_mensal)
    assert so_agregador.receita_anuidade_mensal == 0.0

    # Com a trava desligada o agregador passa a contribuir (contraprova do flag).
    sem_trava = rodar(prem={"share_balcao": 0.0, "anuidade_apenas_balcao": False})
    m12_sem = next(x for x in sem_trava.serie_mensal if x["mes"] == 12)
    assert m12_sem["receita_anuidade"] == pytest.approx(9_046.29, abs=CENTAVO)


def test_anuidade_desloca_o_mes_de_referencia_do_steady_state():
    """Regime pleno = alunos maduros E anuidade em cobranca -> max(8, 12) = 12."""
    com = rodar()
    sem = rodar(prem={"anuidade_valor": 0.0})

    assert com.mes_referencia_steady == 12
    # Desligando a anuidade o mes volta a ser a maturacao pura.
    assert sem.mes_referencia_steady == 8
    assert sem.mes_referencia_steady == premissas().maturacao_meses
    assert sem.receita_anuidade_mensal == 0.0

    # Quem manda e o MAIOR dos dois: maturacao 14 domina o inicio da anuidade (12).
    assert rodar(prem={"maturacao_meses": 14}).mes_referencia_steady == 14
    assert rodar(prem={"maturacao_meses": 14, "anuidade_valor": 0.0}).mes_referencia_steady == 14
    # ...e um inicio de anuidade ANTES da maturacao nao antecipa o steady.
    assert rodar(prem={"anuidade_mes_inicio": 6}).mes_referencia_steady == 8


def test_anuidade_e_aditiva_nao_redistribui_nada():
    """faturamento - receita_anuidade == faturamento do MESMO cenario sem anuidade.

    A anuidade e uma linha NOVA de receita: nao pode canibalizar mensalidade,
    mexer na rampa de alunos nem no mix balcao/agregador.
    """
    com = cenario("golden")
    sem = cenario("sem_anuidade")

    assert com.faturamento_mensal_steady - com.receita_anuidade_mensal == pytest.approx(
        282_015.62, abs=CENTAVO
    )
    assert sem.faturamento_mensal_steady == pytest.approx(282_015.62, abs=CENTAVO)

    # Identidade mes a mes (os dois cenarios tem a MESMA linha do tempo).
    assert len(com.serie_mensal) == len(sem.serie_mensal) == 64
    for a, b in zip(com.serie_mensal, sem.serie_mensal, strict=True):
        assert a["mes"] == b["mes"]
        assert a["alunos_total"] == pytest.approx(b["alunos_total"], abs=1e-9)
        assert a["alunos_balcao"] == pytest.approx(b["alunos_balcao"], abs=1e-9)
        assert a["faturamento_mensal"] - a["receita_anuidade"] == pytest.approx(
            b["faturamento_mensal"], abs=1e-6
        ), f"mes {a['mes']}"

    # A anuidade tambem dimensiona a FOLHA: ela entra no faturamento maduro, logo o
    # cenario sem anuidade tem folha menor (R$47.942,66 x R$49.003,79). E consequencia
    # da regra, nao efeito colateral -- a folha e % do faturamento de regime pleno.
    assert sem.folha_mensal == pytest.approx(47_942.66, abs=CENTAVO)
    assert com.folha_mensal == pytest.approx(49_003.79, abs=CENTAVO)
    assert sem.folha_mensal < com.folha_mensal
    assert sem.folha_mensal == pytest.approx(
        folha_fixa_esperada(premissas(anuidade_valor=0.0), GOLDEN_DEMANDA), abs=1e-9
    )

    # E o efeito no comite: a anuidade melhora todos os indicadores, sem excecao.
    assert sem.ebitda_mensal == pytest.approx(109_233.60, abs=CENTAVO)
    assert sem.margem_ebitda_pct == pytest.approx(0.3873317, abs=RATE)
    assert sem.alunos_break_even_total == pytest.approx(1_166.91, abs=0.05)
    assert sem.alunos_break_even_caixa_total == pytest.approx(1_566.11, abs=0.05)
    assert sem.payback_meses == 32.0
    assert sem.tir_anual == pytest.approx(0.3639585, abs=RATE)
    assert sem.vpl == pytest.approx(212_103.28, abs=CENTAVO)
    assert sem.acumulado_mes_final == pytest.approx(1_503_326.98, abs=CENTAVO)
    assert sem.aluguel_teto["excecao"] == pytest.approx(84_604.69, abs=CENTAVO)

    assert com.ebitda_mensal > sem.ebitda_mensal
    assert com.alunos_break_even_total < sem.alunos_break_even_total
    assert com.payback_meses < sem.payback_meses
    assert com.vpl > sem.vpl


def test_anuidade_entra_no_break_even_na_mesma_regua_da_dre():
    """Break-even e DRE de steady tem de medir o MESMO regime (com anuidade)."""
    p = premissas()
    r = rodar()
    # A receita por aluno do break-even inclui a anuidade, ponderada pelo balcao.
    assert p.receita_por_aluno_total == pytest.approx(receita_por_aluno_esperada(p), abs=1e-9)
    assert p.receita_por_aluno_total - p.ticket_blended == pytest.approx(
        p.anuidade_por_aluno_balcao_mes * p.share_balcao, abs=1e-12
    )
    # Ignorar a anuidade no break-even inflaria a exigencia em ~15 alunos (era ~19 com
    # a folha percentual: agora o k e maior, entao o mesmo custo fixo pede menos aluno
    # marginal -- e a folha do cenario sem anuidade tambem e menor).
    sem = premissas(anuidade_valor=0.0)
    assert break_even_alunos(sem, GOLDEN_DEMANDA) - break_even_alunos(
        p, GOLDEN_DEMANDA
    ) == pytest.approx(14.91, abs=0.05)
    assert r.alunos_break_even_total == pytest.approx(
        break_even_alunos(p, GOLDEN_DEMANDA), abs=1e-9
    )


def test_anuidade_travada_no_config():
    """Mudar a regra da anuidade sem gate vira suite vermelha, nao numero novo."""
    assert cfg.SIM_ANUIDADE_VALOR == pytest.approx(99.0, abs=1e-12)
    assert cfg.SIM_ANUIDADE_MES_INICIO == 12
    assert cfg.SIM_ANUIDADE_APENAS_BALCAO is True
    assert cfg.SIM_ANUIDADE_PRO_RATA is True
    # None = elegibilidade DERIVADA do churn. Um numero aqui vira constante magica
    # paralela e desacopla a elegibilidade do churn.
    assert cfg.SIM_ANUIDADE_ELEGIVEL_PCT is None

    # E os defaults de `Premissas` vem DAI, nao de literal proprio.
    p = Premissas(ticket_cheio=147.0)
    assert p.anuidade_valor == cfg.SIM_ANUIDADE_VALOR
    assert p.anuidade_mes_inicio == cfg.SIM_ANUIDADE_MES_INICIO
    assert p.anuidade_apenas_balcao == cfg.SIM_ANUIDADE_APENAS_BALCAO
    assert p.anuidade_pro_rata == cfg.SIM_ANUIDADE_PRO_RATA
    assert p.anuidade_elegivel_pct == cfg.SIM_ANUIDADE_ELEGIVEL_PCT


# ---------------------------------------------------------------------------
# 3) Cenarios de fronteira
# ---------------------------------------------------------------------------


def test_fronteira_p10_opera_acima_do_break_even_e_ainda_assim_nao_paga():
    """p10 = 1189 alunos. Resultado MEDIDO, nao presumido.

    Fica ACIMA do break-even de EBITDA (914,8) -- EBITDA steady positivo --
    e ABAIXO do break-even DE CAIXA (1.305,2): a operacao se paga, o
    INVESTIMENTO nao. Payback infinito, VPL negativo, TIR inexistente.
    Este e o caso que obriga o payload a mandar `null` explicito (allow_nan=False).

    Os dois break-evens sao MENORES que os do golden (1.152,0 / 1.542,4) porque a
    folha e dimensionada pela demanda ASSUMIDA de cada cenario: com 1.189 alunos
    assumidos monta-se uma equipe menor. O steady nao mudou.
    """
    r = cenario("p10")
    assert 1189.0 > r.alunos_break_even_total            # acima do BE de EBITDA
    assert 1189.0 < r.alunos_break_even_caixa_total      # abaixo do BE de caixa
    assert r.alunos_break_even_total == pytest.approx(914.76, abs=0.05)
    assert r.alunos_break_even_caixa_total == pytest.approx(1_305.16, abs=0.05)
    assert r.faturamento_mensal_steady == pytest.approx(151_177.62, abs=CENTAVO)
    assert r.receita_anuidade_mensal == pytest.approx(3_221.21, abs=CENTAVO)
    # Folha menor que a do golden: a equipe e dimensionada pela demanda assumida.
    assert r.folha_mensal == pytest.approx(25_700.20, abs=CENTAVO)
    assert r.folha_mensal < cenario("golden").folha_mensal
    assert r.ebitda_mensal == pytest.approx(26_938.46, abs=CENTAVO)
    assert r.ebitda_mensal > 0
    assert r.margem_ebitda_pct == pytest.approx(0.1781908, abs=RATE)
    assert r.ir_csll_mensal == pytest.approx(14_448.13, abs=CENTAVO)
    assert math.isinf(r.payback_meses)                   # NUNCA paga o investimento
    assert r.mes_caixa_operacional_positivo is None
    assert r.tir_anual is None                           # sem troca de sinal -> sem raiz
    assert r.vpl == pytest.approx(-1_885_497.58, abs=CENTAVO)
    assert r.acumulado_mes_final == pytest.approx(-2_632_012.43, abs=CENTAVO)
    assert r.retorno_anual_desalavancado == pytest.approx(0.0693907, abs=RATE)
    assert r.retorno_anual_equity == pytest.approx(-0.4082908, abs=RATE)
    assert r.flag_viavel is False


def test_fronteira_p90():
    """p90 = 3034 alunos: folgadamente acima dos dois break-evens."""
    r = cenario("p90")
    assert 3034.0 > r.alunos_break_even_caixa_total
    assert r.faturamento_mensal_steady == pytest.approx(378_004.97, abs=CENTAVO)
    assert r.receita_anuidade_mensal == pytest.approx(8_219.64, abs=CENTAVO)
    assert r.ebitda_mensal == pytest.approx(169_609.46, abs=CENTAVO)
    assert r.margem_ebitda_pct == pytest.approx(0.4486964, abs=RATE)
    assert r.ir_csll_mensal == pytest.approx(39_126.94, abs=CENTAVO)
    assert r.folha_mensal == pytest.approx(64_260.85, abs=CENTAVO)
    assert r.payback_meses == 18.0
    assert r.mes_caixa_operacional_positivo == 5
    assert r.tir_anual == pytest.approx(0.9456790, abs=RATE)
    assert r.vpl == pytest.approx(1_691_321.71, abs=CENTAVO)
    assert r.acumulado_mes_final == pytest.approx(4_445_948.64, abs=CENTAVO)
    assert r.retorno_anual_desalavancado == pytest.approx(0.7249029, abs=RATE)
    assert r.aluguel_teto["excecao"] == pytest.approx(113_401.49, abs=CENTAVO)
    # Mesmo no p90 o mes 1 nasce no vermelho -- e agora MUITO mais fundo (-49.955,69
    # contra -3.238,83): quanto maior a demanda assumida, maior a equipe que ja esta
    # na folha antes de o aluno chegar. O mes 1 nao tem anuidade para socorre-lo.
    m1 = next(x for x in r.serie_mensal if x["mes"] == 1)
    assert m1["ebitda_mensal"] == pytest.approx(-49_955.69, abs=CENTAVO)
    assert m1["folha"] == pytest.approx(r.folha_mensal, abs=1e-9)
    assert m1["receita_anuidade"] == 0.0


def test_fronteira_carencia_desloca_o_inicio_da_cobranca_e_melhora_o_payback():
    """A carencia conta de M-4 (entrega), nao da abertura."""
    sem = cenario("golden")
    com = cenario("carencia_4")

    # Sem carencia: aluguel ja no primeiro mes de contrato, que e M-4.
    assert sem.serie_mensal[0]["mes"] == -4
    assert sem.serie_mensal[0]["aluguel"] == pytest.approx(30_000.00, abs=CENTAVO)

    # Com carencia de 4: mes_contrato 1..4 (= M-4..M-1) isentos; a cobranca comeca
    # no mes_contrato 5, que e o mes 1 de OPERACAO.
    isentos = [x for x in com.serie_mensal if x["mes_contrato"] <= 4]
    assert [x["mes"] for x in isentos] == [-4, -3, -2, -1]
    assert all(x["aluguel"] == 0.0 for x in isentos)
    primeiro_pago = next(x for x in com.serie_mensal if x["aluguel"] > 0)
    assert primeiro_pago["mes_contrato"] == 5
    assert primeiro_pago["mes"] == 1
    assert primeiro_pago["aluguel"] == pytest.approx(30_000.00, abs=CENTAVO)

    # A carencia so muda o CAIXA da pre-abertura: o steady e identico...
    assert com.faturamento_mensal_steady == pytest.approx(sem.faturamento_mensal_steady, abs=1e-9)
    assert com.ebitda_mensal == pytest.approx(sem.ebitda_mensal, abs=1e-9)
    assert com.receita_anuidade_mensal == pytest.approx(sem.receita_anuidade_mensal, abs=1e-9)
    # ...e o payback melhora exatamente 4 aluguels de antecipacao.
    assert com.payback_meses == 28.0
    assert com.payback_meses < sem.payback_meses
    assert com.acumulado_mes_final == pytest.approx(
        sem.acumulado_mes_final + 4 * 30_000.0, abs=CENTAVO
    )
    assert com.acumulado_mes_final == pytest.approx(1_765_454.56, abs=CENTAVO)
    assert com.vpl == pytest.approx(392_591.13, abs=CENTAVO)
    assert com.tir_anual == pytest.approx(0.4569667, abs=RATE)


def test_fronteira_equipamentos_a_vista():
    """prazo_equipamentos=0 -> sem PMT; o desembolso vai para a pre-abertura."""
    fin = cenario("golden")
    vista = cenario("equip_a_vista")

    assert vista.pmt_mensal == 0.0
    assert vista.juros_totais == 0.0
    assert vista.despesa_financeira_mensal == 0.0
    assert all(x["pmt"] == 0.0 and x["juros"] == 0.0 for x in vista.serie_mensal)

    # O desembolso dos equipamentos aparece em M-1 (ultimo mes de pre-abertura), somado
    # a 4a parcela da obra (150.000) E a 4a parcela da franquia (40.000).
    pre = [x for x in vista.serie_mensal if x["fase"] == "pre_operacional"]
    assert pre[-1]["mes"] == -1
    assert pre[-1]["investimento"] == pytest.approx(
        150_000.0 + 40_000.0 + 1_400_000.0, abs=CENTAVO
    )
    assert sum(x["investimento"] for x in pre) == pytest.approx(2_160_000.00, abs=CENTAVO)
    assert vista.serie_mensal[3]["fcf_acumulado"] == pytest.approx(-2_280_000.00, abs=CENTAVO)

    # A otica de retorno NAO quebra: desalavancada identica (nao depende de como o
    # capex foi financiado); equity muda porque o equity aportado passa a ser tudo.
    assert vista.retorno_anual_desalavancado == pytest.approx(
        fin.retorno_anual_desalavancado, abs=1e-12
    )
    assert vista.retorno_anual_equity == pytest.approx(1.3231147, abs=RATE)
    assert vista.investimento_total == pytest.approx(fin.investimento_total, abs=CENTAVO)

    # Sem PMT o break-even de caixa colapsa no break-even de EBITDA.
    assert vista.alunos_break_even_caixa_total == pytest.approx(
        vista.alunos_break_even_total, abs=1e-9
    )

    # Antecipar 1,4 mi piora o payback e melhora o mes de caixa operacional positivo.
    assert vista.payback_meses == 33.0
    assert vista.payback_meses > fin.payback_meses
    assert vista.mes_caixa_operacional_positivo == 4
    assert vista.tir_anual == pytest.approx(0.3173924, abs=RATE)
    # Equipamentos A VISTA: sem divida, D/E=0, entao Ke == Ku e o fluxo do socio E o
    # do negocio -> os dois VPLs coincidem. E a identidade da 4a rodada funcionando.
    assert vista.vpl == pytest.approx(312_177.18, abs=CENTAVO)
    assert vista.vpl_negocio == pytest.approx(vista.vpl_socio, abs=CENTAVO)
    assert vista.taxa_minima_socio_aa == pytest.approx(
        vista.taxa_minima_negocio_aa, abs=1e-12
    )
    assert vista.acumulado_mes_final == pytest.approx(2_546_379.73, abs=CENTAVO)


# ---------------------------------------------------------------------------
# 4) Identidades contabeis -- valem em TODOS os cenarios
# ---------------------------------------------------------------------------

TODOS = list(CENARIOS)


@pytest.mark.parametrize("nome", TODOS)
def test_identidade_ebitda_fecha_com_a_dre(nome):
    r = cenario(nome)
    for x in r.serie_mensal:
        if x["fase"] != "operacao":
            continue
        esperado = (
            x["faturamento_mensal"] - x["deducoes"] - x["impostos"] - x["custos_op"]
        )
        assert x["ebitda_mensal"] == pytest.approx(esperado, abs=1e-6), f"mes {x['mes']}"


@pytest.mark.parametrize("nome", TODOS)
def test_identidade_custos_op_e_a_soma_das_parcelas(nome):
    r = cenario(nome)
    for x in r.serie_mensal:
        if x["fase"] != "operacao":
            continue
        soma = x["custos_variaveis"] + x["folha"] + x["outros_fixos"] + x["aluguel"]
        assert x["custos_op"] == pytest.approx(soma, abs=1e-6), f"mes {x['mes']}"


@pytest.mark.parametrize("nome", TODOS)
def test_identidade_aluguel_respeita_a_carencia(nome):
    demanda, prem, _ = CENARIOS[nome]
    p = premissas(**prem)
    r = cenario(nome)
    for x in r.serie_mensal:
        f_aluguel = fator_reajuste(x["mes"], p.reajuste_aluguel_aa)
        if x["mes_contrato"] <= p.carencia_aluguel_meses:
            assert x["aluguel"] == 0.0, f"mes_contrato {x['mes_contrato']}"
        else:
            assert x["aluguel"] == pytest.approx(
                p.aluguel_mes * f_aluguel, abs=1e-6
            ), f"mes_contrato {x['mes_contrato']}"
    assert demanda > 0  # sanity do parametro


@pytest.mark.parametrize("nome", TODOS)
def test_identidade_anuidade_reconstruida_fora_do_motor(nome):
    """A linha de anuidade da serie tem de bater com a regra reconstruida a mao."""
    _, prem, _ = CENARIOS[nome]
    p = premissas(**prem)
    r = cenario(nome)
    for x in r.serie_mensal:
        if x["fase"] != "operacao":
            continue
        esperado = receita_anuidade_esperada(
            p, int(x["mes"]), x["alunos_balcao"], x["alunos_agregadores"]
        )
        assert x["receita_anuidade"] == pytest.approx(esperado, abs=1e-6), f"mes {x['mes']}"
        # A anuidade NAO sofre reajuste anual: R$99 e nominal.
        assert x["receita_anuidade"] >= 0.0


@pytest.mark.parametrize("nome", TODOS)
def test_identidade_ebitda_reconstruido_a_partir_dos_alunos(nome):
    """EBITDA(m) recomputado SO com alunos_total(m) tem de bater com a serie.

    Reconstrucao independente:
        fat    = faturamento(alunos_total, fator_ticket) + anuidade(m)
        ebitda = fat * k - (outros_fixos + folha_fixa) * f_custos - aluguel(m)

    A FOLHA entra aqui como CUSTO FIXO reajustado, nao dentro de k: ela e dimensionada
    UMA vez pela demanda ASSUMIDA do cenario (nao pelos alunos do mes) e nao varia com
    a rampa. Reconstrui-la como `fat * folha_pct` era exatamente a regra antiga.
    """
    demanda, prem, _ = CENARIOS[nome]
    p = premissas(**prem)
    r = cenario(nome)
    folha_fixa = folha_fixa_esperada(p, demanda)
    for x in r.serie_mensal:
        if x["fase"] != "operacao":
            continue
        m = x["mes"]
        bal = x["alunos_total"] * p.share_balcao
        agr = x["alunos_total"] * (1.0 - p.share_balcao)
        fat = p.faturamento(
            x["alunos_total"], fator_ticket=fator_reajuste(m, p.reajuste_ticket_aa)
        ) + receita_anuidade_esperada(p, int(m), bal, agr)
        assert fat == pytest.approx(x["faturamento_mensal"], abs=1e-6), f"fat mes {m}"
        aluguel = (
            0.0
            if x["mes_contrato"] <= p.carencia_aluguel_meses
            else p.aluguel_mes * fator_reajuste(m, p.reajuste_aluguel_aa)
        )
        f_custos = fator_reajuste(m, p.reajuste_custos_aa)
        ebitda = (
            fat * p.fator_receita_para_ebitda
            - (p.outros_fixos_mes + folha_fixa) * f_custos
            - aluguel
        )
        assert ebitda == pytest.approx(x["ebitda_mensal"], abs=1e-6), f"ebitda mes {m}"
        # A folha da linha e a FIXA reajustada -- independe dos alunos do mes.
        assert x["folha"] == pytest.approx(folha_fixa * f_custos, abs=1e-6), f"folha mes {m}"
        # E a divisao balcao/agregadores segue o mix declarado.
        assert x["alunos_balcao"] == pytest.approx(bal, abs=1e-9)
        assert x["alunos_agregadores"] == pytest.approx(agr, abs=1e-9)


@pytest.mark.parametrize("nome", TODOS)
def test_identidade_break_even_zera_o_ebitda(nome):
    """break_even * receita_por_aluno + personal == faturamento onde o EBITDA e zero.

    A receita por aluno inclui a anuidade em regime pleno -- e a MESMA regua da
    DRE de steady-state, que e lida no mes 12 justamente por isso.

    O custo fixo do lado direito e o `custo_fixo_total_mes(demanda)`: outros fixos MAIS
    a folha dimensionada pela demanda assumida. Era o `custo_fixo_base_mes` (so os
    outros fixos) quando a folha ainda vivia dentro de k.
    """
    demanda, prem, _ = CENARIOS[nome]
    p = premissas(**prem)
    r = cenario(nome)
    receita_aluno = receita_por_aluno_esperada(p)
    # Reconstruido fora do motor, nao lido de `custo_fixo_total_mes`.
    custo_fixo = p.outros_fixos_mes + folha_fixa_esperada(p, demanda)
    assert custo_fixo == pytest.approx(p.custo_fixo_total_mes(demanda), abs=1e-9)

    fat_be = r.alunos_break_even_total * receita_aluno + p.personal_mes
    ebitda_be = fat_be * p.fator_receita_para_ebitda - custo_fixo - p.aluguel_mes
    assert ebitda_be == pytest.approx(0.0, abs=1e-6)
    assert r.alunos_break_even_total == pytest.approx(
        break_even_alunos(p, demanda), abs=1e-9
    )

    # Break-even DE CAIXA: mesma conta, cobrindo tambem a PMT.
    fat_caixa = r.alunos_break_even_caixa_total * receita_aluno + p.personal_mes
    sobra = (
        fat_caixa * p.fator_receita_para_ebitda
        - custo_fixo
        - p.aluguel_mes
        - r.pmt_mensal
    )
    assert sobra == pytest.approx(0.0, abs=1e-6)
    assert r.alunos_break_even_caixa_total == pytest.approx(
        break_even_alunos(p, demanda, incluir_pmt=r.pmt_mensal), abs=1e-9
    )


@pytest.mark.parametrize("nome", TODOS)
def test_identidade_payback_e_o_primeiro_mes_com_acumulado_nao_negativo(nome):
    r = cenario(nome)
    esperado = float("inf")
    for x in r.serie_mensal:
        if x["fcf_acumulado"] >= 0:
            esperado = float(x["mes"])
            break
    if math.isinf(esperado):
        assert math.isinf(r.payback_meses)
    else:
        assert r.payback_meses == esperado
        # ...e o mes anterior ainda estava negativo (nao ha "primeiro" mais cedo).
        anteriores = [x for x in r.serie_mensal if x["mes"] < esperado]
        assert all(x["fcf_acumulado"] < 0 for x in anteriores)


@pytest.mark.parametrize("nome", TODOS)
def test_identidade_capex_do_fluxo_bate_com_o_denominador_do_retorno(nome):
    """O capex que sai no caixa e o mesmo que divide o retorno.

    No caso financiado o principal dos equipamentos entra pela AMORTIZACAO da PMT;
    a vista, entra direto na linha de investimento. Nos dois casos a soma tem de
    fechar com `investimento_total` (obra + equipamentos + taxa de franquia).
    """
    r = cenario(nome)
    investido = sum(x["investimento"] for x in r.serie_mensal)
    amortizado = sum(x["amortizacao"] for x in r.serie_mensal)
    assert investido + amortizado == pytest.approx(r.investimento_total, abs=CENTAVO)
    assert r.investimento_total == pytest.approx(r.capex_total + r.taxa_franquia, abs=CENTAVO)
    # Denominador da otica desalavancada = investimento CHEIO.
    if r.investimento_total > 0:
        resultado = r.ebitda_mensal - r.ir_csll_mensal
        assert r.retorno_anual_desalavancado == pytest.approx(
            resultado * 12.0 / r.investimento_total, abs=1e-9
        )
    # A franquia sai em N parcelas IGUAIS nos meses de CONTRATO 1..N (era inteira no
    # M-4). Isolada por DIFERENCA contra o mesmo cenario com taxa_franquia=0 — a linha
    # `investimento` tambem carrega a obra, entao comparar o valor cheio nao isola nada.
    demanda_c, prem_c, sim_c = CENARIOS[nome]
    sem_franquia = rodar(demanda_c, prem=prem_c, sim={**sim_c, "taxa_franquia": 0.0})
    n = parcelas_franquia_de(nome)
    parcela = r.taxa_franquia / n
    diffs = []
    for a, b in zip(r.serie_mensal, sem_franquia.serie_mensal, strict=True):
        esperado = parcela if a["mes_contrato"] <= n else 0.0
        delta = a["investimento"] - b["investimento"]
        assert delta == pytest.approx(esperado, abs=1e-6), f"mes {a['mes']}"
        diffs.append(delta)
    assert sum(diffs) == pytest.approx(r.taxa_franquia, abs=CENTAVO)
    assert r.serie_mensal[0]["mes_contrato"] == 1
    assert r.serie_mensal[0]["investimento"] >= parcela


@pytest.mark.parametrize("nome", TODOS)
def test_identidade_mes_1_no_vermelho_quando_abaixo_do_break_even(nome):
    r = cenario(nome)
    m1 = next(x for x in r.serie_mensal if x["mes"] == 1)
    if m1["alunos_total"] < r.alunos_break_even_total:
        assert m1["ebitda_mensal"] < 0, f"{nome}: alunos={m1['alunos_total']}"
    else:
        assert m1["ebitda_mensal"] >= 0


@pytest.mark.parametrize("nome", TODOS)
def test_identidade_serie_sem_nan_nem_inf(nome):
    """O payload vai por json.dumps(..., allow_nan=False): nada pode vazar."""
    r = cenario(nome)
    for x in r.serie_mensal:
        for chave, valor in x.items():
            if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                assert math.isfinite(float(valor)), f"{nome} mes {x['mes']}: {chave}={valor}"
    # E o serializador real tem de aceitar a serie sem tratamento nenhum.
    assert json.dumps(r.serie_mensal, allow_nan=False)


@pytest.mark.parametrize("nome", TODOS)
def test_identidade_fcf_acumulado_e_a_soma_corrida_do_fcf(nome):
    r = cenario(nome)
    acum = 0.0
    for x in r.serie_mensal:
        acum += x["fcf_mensal"]
        assert x["fcf_acumulado"] == pytest.approx(acum, abs=1e-6), f"mes {x['mes']}"
    assert r.acumulado_mes_final == pytest.approx(r.serie_mensal[-1]["fcf_acumulado"], abs=1e-9)


@pytest.mark.parametrize("nome", TODOS)
def test_identidade_mes_de_referencia_do_steady_vem_da_serie(nome):
    """`mes_referencia_steady` e um mes REAL da serie e a DRE exposta e a dele.

    O PDF e a tela LEEM este mes do payload; recalcula-lo era o que fazia o
    waterfall plotar um mes diferente do card ao lado no mesmo slide.
    """
    _, prem, _ = CENARIOS[nome]
    p = premissas(**prem)
    r = cenario(nome)

    esperado = max(int(p.maturacao_meses), 1)
    if p.anuidade_valor > 0:
        esperado = max(esperado, int(p.anuidade_mes_inicio))
    assert r.mes_referencia_steady == esperado

    linha = next(x for x in r.serie_mensal if x["mes"] == r.mes_referencia_steady)
    assert linha["fase"] == "operacao"
    assert r.faturamento_mensal_steady == pytest.approx(linha["faturamento_mensal"], abs=1e-12)
    assert r.receita_liquida == pytest.approx(linha["receita_liquida"], abs=1e-12)
    assert r.receita_pos_impostos == pytest.approx(linha["receita_pos_impostos"], abs=1e-12)
    assert r.ebitda_mensal == pytest.approx(linha["ebitda_mensal"], abs=1e-12)
    assert r.receita_anuidade_mensal == pytest.approx(linha["receita_anuidade"], abs=1e-12)
    assert r.custos_op_mensal == pytest.approx(linha["custos_op"], abs=1e-12)
    assert r.ir_csll_mensal == pytest.approx(linha["ir_csll"], abs=1e-12)


# ---------------------------------------------------------------------------
# 5) Trava das premissas do config.py
# ---------------------------------------------------------------------------

# Mudar QUALQUER valor abaixo sem atualizar o golden = suite vermelha. E de proposito:
# cada um destes coeficientes desloca um numero que o comite le.
PREMISSAS_TRAVADAS: dict[str, float | int] = {
    # composicao da receita
    "SIM_FOLHA_PCT": 0.17,
    "SIM_TICKET_AGREGADOR_FATOR": 0.60,
    "SIM_SHARE_BALCAO": 0.69,
    "SIM_INADIMPLENCIA": 0.02,
    "SIM_CHURN": 0.06,
    "SIM_PERSONAL_MES_RECEITA": 5_000,
    # anuidade (R$99/ano por aluno de balcao a partir do mes 12, pro-rata mensal)
    "SIM_ANUIDADE_VALOR": 99.0,
    "SIM_ANUIDADE_MES_INICIO": 12,
    # deducoes, impostos sobre receita e custo variavel
    "SIM_DEVOLUCOES_PCT": 0.005,
    "SIM_PIS": 0.0065,
    "SIM_COFINS": 0.03,
    "SIM_ISS": 0.03,
    "SIM_ROYALTIES_PCT": 0.08,
    "SIM_MARKETING_PCT": 0.02,
    "SIM_MANUTENCAO_PCT": 0.02,
    "SIM_CARTOES_PCT": 0.0105,
    # custo fixo
    "SIM_OUTROS_FIXOS_MES": 38_150.00,
    # aluguel-teto (% do faturamento bruto; canonico = TETO 20%)
    "SIM_ALUGUEL_TETO_IDEAL": 0.15,
    "SIM_ALUGUEL_TETO_TETO": 0.20,
    "SIM_ALUGUEL_TETO_EXCECAO": 0.30,
    # investimento (a franquia e PARCELADA sem juros junto da obra: 4x por default)
    "SIM_TAXA_FRANQUIA": 160_000.0,
    "SIM_PARCELAS_OBRA_DEFAULT": 4,
    "SIM_PARCELAS_FRANQUIA_DEFAULT": 4,
    # reajustes anuais (degrau a partir do mes 13)
    "SIM_REAJUSTE_TICKET_AA": 0.04,
    "SIM_REAJUSTE_ALUGUEL_AA": 0.04,
    "SIM_REAJUSTE_CUSTOS_AA": 0.04,
    # desconto do VPL/TIR
    # 4a rodada: a taxa de desconto generica de 12% virou a taxa minima do NEGOCIO
    # (25% a.a.). A do socio nao e parametro: e derivada em simular().
    "SIM_TAXA_MINIMA_NEGOCIO_AA": 0.25,
    # IR/CSLL -- Lucro Presumido com a faixa do adicional explicita
    "SIM_BASE_PRESUMIDA_PCT": 0.32,
    "SIM_IRPJ_ALIQUOTA": 0.15,
    "SIM_IRPJ_ADICIONAL_ALIQUOTA": 0.10,
    "SIM_IRPJ_ADICIONAL_LIMITE_MES": 20_000.0,
    "SIM_CSLL_ALIQUOTA": 0.09,
    # linha do tempo (INTOCAVEIS por decisao do dono do produto)
    "SIM_MESES_PRE_ABERTURA": 4,
    "SIM_HORIZONTE_MESES": 60,
    "SIM_MATURACAO_MESES": 8,
    "SIM_CARENCIA_ALUGUEL_MESES": 0,
    "SIM_ALUNOS_INICIAL": 500,
    # explicitos em ZERO (o corte em 60 meses ignora residual e renovacao)
    "SIM_CUSTO_PRE_OPERACIONAL_MES": 0.0,
    "SIM_VALOR_RESIDUAL_MES_60": 0.0,
    "SIM_CAPEX_RENOVACAO": 0.0,
}


@pytest.mark.parametrize(("nome_const", "esperado"), sorted(PREMISSAS_TRAVADAS.items()))
def test_premissa_do_config_esta_travada(nome_const, esperado):
    obtido = getattr(cfg, nome_const)
    assert obtido == pytest.approx(esperado, abs=1e-12), (
        f"{nome_const}: config={obtido!r} != golden={esperado!r}. "
        "Se a mudanca e intencional, atualize os numeros do golden no mesmo commit."
    )


def test_defaults_de_premissas_vem_do_config():
    """`Premissas` nao pode carregar coeficiente literal proprio: tudo vem do config."""
    p = Premissas(ticket_cheio=147.0)
    assert p.share_balcao == cfg.SIM_SHARE_BALCAO
    assert p.ticket_agregador_fator == cfg.SIM_TICKET_AGREGADOR_FATOR
    assert p.folha_pct == cfg.SIM_FOLHA_PCT
    assert p.inadimplencia == cfg.SIM_INADIMPLENCIA
    assert p.churn == cfg.SIM_CHURN
    assert p.personal_mes == cfg.SIM_PERSONAL_MES_RECEITA
    assert p.outros_fixos_mes == cfg.SIM_OUTROS_FIXOS_MES
    assert p.taxa_minima_negocio_aa == cfg.SIM_TAXA_MINIMA_NEGOCIO_AA
    assert p.reajuste_ticket_aa == cfg.SIM_REAJUSTE_TICKET_AA
    assert p.reajuste_aluguel_aa == cfg.SIM_REAJUSTE_ALUGUEL_AA
    assert p.reajuste_custos_aa == cfg.SIM_REAJUSTE_CUSTOS_AA
    assert p.carencia_aluguel_meses == cfg.SIM_CARENCIA_ALUGUEL_MESES
    assert p.horizonte_meses == cfg.SIM_HORIZONTE_MESES
    assert p.meses_pre_abertura == cfg.SIM_MESES_PRE_ABERTURA
    assert p.base_presumida_pct == cfg.SIM_BASE_PRESUMIDA_PCT
    assert p.irpj_aliquota == cfg.SIM_IRPJ_ALIQUOTA
    assert p.irpj_adicional_aliquota == cfg.SIM_IRPJ_ADICIONAL_ALIQUOTA
    assert p.irpj_adicional_limite_mes == cfg.SIM_IRPJ_ADICIONAL_LIMITE_MES
    assert p.csll_aliquota == cfg.SIM_CSLL_ALIQUOTA
    assert p.valor_residual_mes_60 == cfg.SIM_VALOR_RESIDUAL_MES_60
    assert p.capex_renovacao == cfg.SIM_CAPEX_RENOVACAO


def test_aluguel_teto_usa_as_faixas_do_config():
    faixas = aluguel_teto_clusters(100_000.0)
    assert faixas["ideal"] == pytest.approx(100_000.0 * cfg.SIM_ALUGUEL_TETO_IDEAL, abs=1e-9)
    assert faixas["teto"] == pytest.approx(100_000.0 * cfg.SIM_ALUGUEL_TETO_TETO, abs=1e-9)
    assert faixas["excecao"] == pytest.approx(100_000.0 * cfg.SIM_ALUGUEL_TETO_EXCECAO, abs=1e-9)
    assert faixas["canonico"] == faixas["teto"]
    # Faturamento zero nao pode virar NaN/inf no payload.
    assert aluguel_teto_clusters(0.0) == {
        "ideal": 0.0, "teto": 0.0, "excecao": 0.0, "canonico": 0.0
    }


# ---------------------------------------------------------------------------
# 6) FOLHA FIXA DESDE O MES 1 (decisao de Felipe, 2026-07-24)
# ---------------------------------------------------------------------------


def test_folha_e_identica_em_todos_os_meses_de_operacao_do_ano_1():
    """A folha do mes 1 e a MESMA do mes 12; o unico degrau e o reajuste no mes 13.

    Era o defeito reportado ("a folha esta escalando junto com a unidade"): com a folha
    percentual da receita do mes, ela crescia mes a mes acompanhando a rampa. Agora a
    unica variacao legitima no tempo e o reajuste anual de custos.
    """
    r = rodar()
    operacao = [x for x in r.serie_mensal if x["fase"] == "operacao"]
    ano1 = operacao[:12]
    assert [x["mes"] for x in ano1] == list(range(1, 13))

    # UM unico valor em todo o ano 1 -- nao uma serie crescente.
    assert len({round(x["folha"], 6) for x in ano1}) == 1
    for x in ano1:
        assert x["folha"] == pytest.approx(49_003.79, abs=CENTAVO), f"mes {x['mes']}"
    assert ano1[0]["folha"] == pytest.approx(ano1[-1]["folha"], abs=1e-9)
    # ...enquanto os ALUNOS triplicam no mesmo intervalo (a folha nao os acompanha).
    assert ano1[-1]["alunos_total"] > 3.0 * ano1[0]["alunos_total"]

    # Reajuste SO a partir do mes 13, em degrau anual de 4%.
    m13 = operacao[12]
    assert m13["mes"] == 13
    assert m13["folha"] == pytest.approx(
        ano1[0]["folha"] * (1.0 + premissas().reajuste_custos_aa), abs=1e-6
    )
    assert m13["folha"] == pytest.approx(50_963.94, abs=CENTAVO)
    # Ano 2 inteiro no MESMO patamar; ano 3 sobe outro degrau.
    assert len({round(x["folha"], 6) for x in operacao[12:24]}) == 1
    assert operacao[24]["folha"] == pytest.approx(
        ano1[0]["folha"] * (1.0 + premissas().reajuste_custos_aa) ** 2, abs=1e-6
    )

    # A pre-abertura nao tem folha nesta linha: o custo dos meses de obra e o
    # `custo_pre_operacional_mes` (default ZERO, explicito no config).
    assert all(x["folha"] == 0.0 for x in r.serie_mensal if x["fase"] != "operacao")


def test_folha_cai_com_demanda_menor_e_ainda_assim_nao_varia_no_tempo():
    """Os DOIS fatos juntos: a folha e dimensionada pela demanda ASSUMIDA...

    ...e, dentro de um mesmo cenario, NAO varia no tempo. Sao coisas distintas e as
    duas tem de valer: o operador que assume 1.189 alunos monta uma equipe menor, mas
    essa equipe existe inteira desde o mes 1.
    """
    p = premissas()
    folhas = {}
    for demanda in (1189.0, 2304.0, 3034.0):
        r = rodar(demanda)
        operacao = [x for x in r.serie_mensal if x["fase"] == "operacao"]
        ano1 = {round(x["folha"], 6) for x in operacao[:12]}
        assert len(ano1) == 1, f"demanda {demanda}: folha variou dentro do ano 1"
        folhas[demanda] = r.folha_mensal
        # ...e e a folha dimensionada por ESTA demanda, reconstruida fora do motor.
        assert r.folha_mensal == pytest.approx(folha_fixa_esperada(p, demanda), abs=1e-9)

    # Monotona crescente na demanda assumida (AFIM, nao proporcional: o faturamento
    # maduro tem a receita FIXA de personal somada por cima da parte por aluno).
    assert folhas[1189.0] < folhas[2304.0] < folhas[3034.0]
    assert folhas[1189.0] == pytest.approx(25_700.20, abs=CENTAVO)
    assert folhas[2304.0] == pytest.approx(49_003.79, abs=CENTAVO)
    assert folhas[3034.0] == pytest.approx(64_260.85, abs=CENTAVO)


def test_folha_e_custo_fixo_e_nao_percentual_da_receita_do_mes():
    """Trava de FORMA: a folha da serie NAO e `folha_pct x faturamento do mes`.

    Sem este assert, uma volta silenciosa a regra antiga passaria: no mes de steady os
    dois calculos coincidem por construcao (la o faturamento JA e o maduro).
    """
    p = premissas()
    r = rodar()
    operacao = [x for x in r.serie_mensal if x["fase"] == "operacao"]

    # No mes de steady as duas reguas coincidem (e por isso o steady nao mudou)...
    steady = next(x for x in operacao if x["mes"] == r.mes_referencia_steady)
    assert steady["folha"] == pytest.approx(
        p.folha_pct * steady["faturamento_mensal"], abs=CENTAVO
    )
    # ...mas na rampa a folha e MUITO maior que o percentual do mes.
    for x in operacao[:7]:
        assert x["folha"] > p.folha_pct * x["faturamento_mensal"], f"mes {x['mes']}"

    # E o custo fixo total do mes 1 (sem aluguel) e outros_fixos + folha.
    m1 = operacao[0]
    assert m1["outros_fixos"] + m1["folha"] == pytest.approx(
        p.custo_fixo_total_mes(GOLDEN_DEMANDA), abs=1e-6
    )
    assert p.custo_fixo_total_mes(GOLDEN_DEMANDA) == pytest.approx(87_153.79, abs=CENTAVO)


def test_ebitda_do_mes_1_e_mais_negativo_do_que_com_folha_escalando():
    """Sinal e ordem de grandeza do mes 1 sob a regra nova, em TODA a faixa.

    A folha fixa e o que joga o mes 1 mais fundo no vermelho -- e quanto maior a
    demanda assumida, mais fundo (a equipe e maior antes de o aluno chegar). O
    comparativo e contra a regra ANTIGA reconstruida fora do motor.
    """
    p = premissas()
    esperado_m1 = {1189.0: -33_549.79, 2304.0: -43_464.47, 3034.0: -49_955.69}
    anteriores = []
    for demanda, alvo in esperado_m1.items():
        r = rodar(demanda)
        m1 = next(x for x in r.serie_mensal if x["mes"] == 1)
        assert m1["ebitda_mensal"] < 0
        assert m1["ebitda_mensal"] == pytest.approx(alvo, abs=CENTAVO)

        antigo = (
            m1["faturamento_mensal"] * (p.fator_receita_para_ebitda - p.folha_efetiva_pct)
            - p.outros_fixos_mes
            - p.aluguel_mes
        )
        assert m1["ebitda_mensal"] < antigo, f"demanda {demanda}: folha fixa tem de doer mais"
        anteriores.append((demanda, m1["ebitda_mensal"]))

    # Monotonia: demanda assumida maior -> mes 1 mais negativo.
    valores = [v for _, v in anteriores]
    assert valores[0] > valores[1] > valores[2]


def test_folha_com_override_absoluto_ignora_a_demanda():
    """Caminho LEGADO: `pessoal_mes_override` continua sendo folha absoluta.

    E o que mantem `viabilidade()`/`gerar_serie_mensal()` reproduzindo o motor antigo.
    Com override, `folha_efetiva_pct` zera (a folha ja e fixa por definicao) e a folha
    NAO depende mais da demanda.
    """
    p = premissas(pessoal_mes_override=cfg.SIM_PESSOAL_MES)
    assert p.folha_efetiva_pct == 0.0
    assert p.folha_fixa_mes(1189.0) == pytest.approx(cfg.SIM_PESSOAL_MES, abs=1e-12)
    assert p.folha_fixa_mes(3034.0) == pytest.approx(cfg.SIM_PESSOAL_MES, abs=1e-12)
    assert p.custo_fixo_total_mes(2304.0) == pytest.approx(
        p.outros_fixos_mes + cfg.SIM_PESSOAL_MES, abs=1e-9
    )
    # ...e na serie a folha do mes 1 e o override, nao a fracao do faturamento.
    r = rodar(prem={"pessoal_mes_override": cfg.SIM_PESSOAL_MES})
    m1 = next(x for x in r.serie_mensal if x["mes"] == 1)
    assert m1["folha"] == pytest.approx(cfg.SIM_PESSOAL_MES, abs=CENTAVO)


# ---------------------------------------------------------------------------
# 7) TAXA DE FRANQUIA PARCELADA 4x SEM JUROS (mesma decisao)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 8])
def test_franquia_sai_em_n_parcelas_iguais_nos_meses_de_contrato_1_a_n(n):
    """N parcelas IGUAIS nos meses de CONTRATO 1..N, e a SOMA == taxa_franquia.

    Isolado: obra e equipamentos ZERADOS, entao a linha `investimento` da serie e SO a
    franquia. Com N > 4 as parcelas passam da abertura e caem nos primeiros meses de
    OPERACAO -- o relogio e o `mes_contrato`, nao o mes de operacao.
    """
    serie = gerar_serie_mensal_completa(
        GOLDEN_DEMANDA, premissas(), obra=0.0, equipamentos=0.0,
        taxa_franquia=160_000.0, parcelas_franquia=n,
    )
    com_desembolso = [x for x in serie if x["investimento"] > 0]
    assert [x["mes_contrato"] for x in com_desembolso] == list(range(1, n + 1))
    for x in com_desembolso:
        assert x["investimento"] == pytest.approx(160_000.0 / n, abs=1e-6)
    assert sum(x["investimento"] for x in serie) == pytest.approx(160_000.0, abs=CENTAVO)
    # O primeiro mes de contrato e o M-4 (entrega), nao o mes 1 de operacao.
    assert com_desembolso[0]["mes"] == -4


def test_franquia_no_default_soma_a_parcela_da_obra_na_pre_abertura():
    """Golden: cada mes M-4..M-1 desembolsa 150.000 de obra + 40.000 de franquia."""
    r = rodar()
    pre = [x for x in r.serie_mensal if x["fase"] == "pre_operacional"]
    assert [x["mes"] for x in pre] == [-4, -3, -2, -1]
    for x in pre:
        assert x["investimento"] == pytest.approx(190_000.00, abs=CENTAVO), f"mes {x['mes']}"
    assert sum(x["investimento"] for x in pre) == pytest.approx(760_000.00, abs=CENTAVO)
    # Nenhuma parcela sobra para os meses de operacao (4 parcelas cabem em 4 meses).
    operacao = [x for x in r.serie_mensal if x["fase"] == "operacao"]
    assert all(x["investimento"] == 0.0 for x in operacao[:-1])
    # E o default vem do config, nao de literal do motor.
    assert cfg.SIM_PARCELAS_FRANQUIA_DEFAULT == 4


def test_parcelas_franquia_1_reproduz_o_comportamento_a_vista():
    """Regressao do default: `parcelas_franquia=1` = taxa INTEIRA no M-4 (regra antiga)."""
    vista = cenario("franquia_a_vista")
    pre = [x for x in vista.serie_mensal if x["fase"] == "pre_operacional"]
    # M-4 carrega a franquia inteira + a 1a parcela da obra; os demais so a obra.
    assert pre[0]["investimento"] == pytest.approx(160_000.0 + 150_000.0, abs=CENTAVO)
    for x in pre[1:]:
        assert x["investimento"] == pytest.approx(150_000.00, abs=CENTAVO)
    assert pre[0]["fcf_acumulado"] == pytest.approx(-340_000.00, abs=CENTAVO)
    # O investimento TOTAL nao muda -- so o momento em que sai do caixa.
    assert sum(x["investimento"] for x in pre) == pytest.approx(760_000.00, abs=CENTAVO)
    assert vista.investimento_total == pytest.approx(
        cenario("golden").investimento_total, abs=CENTAVO
    )


def test_parcelamento_da_franquia_nao_altera_ebitda_margem_nem_break_even():
    """Parcelamento e TIMING DE CAIXA, nao resultado.

    Efeito isolado MEDIDO (usar na documentacao): TIR +0,33pp e VPL +R$2.241,80.
    Payback e acumulado M60 ficam IDENTICOS, porque as 4 parcelas cabem dentro da
    janela M-4..M-1 e no mes 1 o desembolso acumulado ja e o mesmo.
    """
    parcelado = cenario("golden")
    vista = cenario("franquia_a_vista")

    # 1) NADA de resultado muda -- ao float, nao "aproximadamente".
    assert parcelado.faturamento_mensal_steady == pytest.approx(
        vista.faturamento_mensal_steady, abs=1e-12
    )
    assert parcelado.ebitda_mensal == pytest.approx(vista.ebitda_mensal, abs=1e-12)
    assert parcelado.margem_ebitda_pct == pytest.approx(vista.margem_ebitda_pct, abs=1e-12)
    assert parcelado.folha_mensal == pytest.approx(vista.folha_mensal, abs=1e-12)
    assert parcelado.custos_op_mensal == pytest.approx(vista.custos_op_mensal, abs=1e-12)
    assert parcelado.ir_csll_mensal == pytest.approx(vista.ir_csll_mensal, abs=1e-12)
    assert parcelado.alunos_break_even_total == pytest.approx(
        vista.alunos_break_even_total, abs=1e-12
    )
    assert parcelado.alunos_break_even_caixa_total == pytest.approx(
        vista.alunos_break_even_caixa_total, abs=1e-12
    )
    assert parcelado.aluguel_teto == vista.aluguel_teto
    assert parcelado.retorno_anual_desalavancado == pytest.approx(
        vista.retorno_anual_desalavancado, abs=1e-12
    )
    assert parcelado.retorno_anual_equity == pytest.approx(
        vista.retorno_anual_equity, abs=1e-12
    )

    # 2) Nem payback nem acumulado M60: as 4 parcelas cabem na pre-abertura.
    assert parcelado.payback_meses == vista.payback_meses == 31.0
    assert parcelado.acumulado_mes_final == pytest.approx(
        vista.acumulado_mes_final, abs=1e-9
    )
    assert parcelado.acumulado_mes_final == pytest.approx(1_645_454.56, abs=CENTAVO)

    # 3) Mes a mes: o EBITDA e identico; SO investimento/fcf da pre-abertura diferem.
    for a, b in zip(parcelado.serie_mensal, vista.serie_mensal, strict=True):
        assert a["mes"] == b["mes"]
        assert a["ebitda_mensal"] == pytest.approx(b["ebitda_mensal"], abs=1e-12)
        assert a["folha"] == pytest.approx(b["folha"], abs=1e-12)
        if a["fase"] == "operacao":
            assert a["fcf_mensal"] == pytest.approx(b["fcf_mensal"], abs=1e-9), f"mes {a['mes']}"
    difere = [
        a["mes"]
        for a, b in zip(parcelado.serie_mensal, vista.serie_mensal, strict=True)
        if abs(a["investimento"] - b["investimento"]) > 1e-9
    ]
    assert difere == [-4, -3, -2, -1]

    # 4) O que MELHORA e so o valor do dinheiro no tempo.
    assert parcelado.tir_anual is not None and vista.tir_anual is not None
    assert parcelado.tir_anual > vista.tir_anual
    assert parcelado.tir_anual - vista.tir_anual == pytest.approx(0.0033296, abs=1e-6)
    assert parcelado.vpl > vista.vpl
    # O ganho do parcelamento CRESCEU porque a taxa de desconto subiu de 12% para
    # 27,08%: adiar desembolso vale mais quanto mais caro e o dinheiro.
    assert parcelado.vpl - vista.vpl == pytest.approx(4_682.82, abs=CENTAVO)
    assert vista.tir_anual == pytest.approx(0.3864737, abs=RATE)
    assert vista.vpl == pytest.approx(271_420.42, abs=CENTAVO)


def test_franquia_zerada_nao_gera_parcela():
    """Sem taxa de franquia nao ha linha de investimento nenhuma na pre-abertura."""
    serie = gerar_serie_mensal_completa(
        GOLDEN_DEMANDA, premissas(), obra=0.0, equipamentos=0.0,
        taxa_franquia=0.0, parcelas_franquia=4,
    )
    assert all(x["investimento"] == 0.0 for x in serie)
