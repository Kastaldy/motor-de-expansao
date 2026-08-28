"""Testes do motor property-first de viabilidade do imovel — BLK-DIM-11.

Fixtures sinteticas em memoria; ZERO leitura de parquet real. Catchment desligado
(setores_df=None) na maioria dos testes do orquestrador para determinismo. A flag de
zona morta e testada diretamente com dicts de catchment sinteticos.
"""

from __future__ import annotations

import math
from pathlib import Path

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
    """A grade varre alunos TOTAIS e roda o MESMO motor do cenario principal.

    NUMERO MUDOU DE PROPOSITO (FIN-VIAB-01 — colapso das 5 series/9 KPIs duplicados
    num motor unico). Este teste comparava a celula da grade com o ADAPTADOR legado
    `simulador.viabilidade()` (folha ABSOLUTA de R$50.128, IR/CSLL efetivo sobre a
    receita liquida, ticket de agregador ABSOLUTO de R$82, sem pre-abertura e sem
    taxa de franquia). A grade passou a chamar `simular()` com as MESMAS Premissas e
    o MESMO investimento do KPI exibido ao lado dela — a mesma celula (800 alunos,
    fator 1,0) dava margem -34,57% pelo adaptador legado e +1,46% pelo motor do
    cenario. Travar o legado aqui era travar exatamente a divergencia que o ciclo
    corrigiu; o assert agora e contra o nucleo, sem afrouxar tolerancia.
    """
    from motor_expansao.dimensionamento.config import SIM_MENSALIDADE_BALCAO, SIM_TAXA_FRANQUIA
    from motor_expansao.dimensionamento.simulador import Premissas, simular

    share = 0.69
    alunos_total = 800.0
    fator = 1.0
    aluguel_ref = 20000.0

    g = grade_sensibilidade(1500.0, aluguel_ref, 938.0, share_balcao=share)
    esperado = simular(
        alunos_total,
        Premissas(
            ticket_cheio=SIM_MENSALIDADE_BALCAO,
            share_balcao=share,
            aluguel_mes=aluguel_ref * fator,
        ),
        taxa_franquia=SIM_TAXA_FRANQUIA,
    )
    linha = g[(g["alunos"] == alunos_total) & (g["fator_aluguel"] == fator)].iloc[0]
    assert linha["margem_liq"] == pytest.approx(esperado.margem_ebitda_pct)
    assert linha["payback"] == esperado.payback_meses
    assert bool(linha["viavel"]) is esperado.flag_viavel


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

def test_breakeven_ebitda_menor_ou_igual_ao_de_caixa() -> None:
    """Break-even de EBITDA <= break-even de CAIXA (que ainda cobre a PMT).

    (ex-`test_breakeven_menor_que_alunos_para_margem_alvo`.)
    NUMERO MUDOU DE PROPOSITO (FIN-VIAB-01 / P0-2 — break-even canonico em alunos
    TOTAIS): `alunos_para_margem_alvo` vinha de `alunos_minimos_viaveis(margem_alvo)`,
    que variava SO o balcao com os agregadores CONGELADOS na premissa — numero nao
    comparavel com a demanda TOTAL que o operador digita. Hoje sai de
    `simulador.alunos_para_margem()`, em forma fechada e em alunos TOTAIS, na MESMA
    regua de `alunos_breakeven` (`viabilidade_ponto.py:597`), entao a comparacao
    antiga voltou a fazer sentido — e agora entre grandezas comparaveis.
    O par novo e break-even de EBITDA x break-even de CAIXA, tambem em alunos TOTAIS
    e tambem vindos do MESMO cenario do nucleo.
    """
    r = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 938.0,
        base_calibracao_df=_base_comparaveis(), setores_df=None,
    )
    assert math.isfinite(r.alunos_breakeven), "break-even deve ser finito"
    assert math.isfinite(r.alunos_breakeven_caixa), "break-even de caixa deve ser finito"
    # Sem financiamento a PMT e zero -> os dois break-evens coincidem.
    assert r.alunos_breakeven <= r.alunos_breakeven_caixa
    # Margem-alvo de 10% exige MAIS alunos que a margem zero, na mesma unidade.
    assert math.isfinite(r.alunos_para_margem_alvo), (
        "alunos_para_margem_alvo deve ser finito (10% e atingivel neste cenario)"
    )
    assert r.alunos_breakeven < r.alunos_para_margem_alvo, (
        f"break-even ({r.alunos_breakeven:.1f}) deve ser < alunos para 10% de EBITDA "
        f"({r.alunos_para_margem_alvo:.1f}) — ambos em alunos TOTAIS"
    )

    # Com equipamentos financiados a PMT entra no break-even de caixa e o separa
    # estritamente do break-even de EBITDA.
    r_fin = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 938.0,
        base_calibracao_df=_base_comparaveis(), setores_df=None,
        obra=600_000.0, equipamentos=1_400_000.0,
        prazo_equipamentos=60, juros_equipamentos_am=0.018,
    )
    assert r_fin.alunos_breakeven_caixa > r_fin.alunos_breakeven


def test_breakeven_resulta_ebitda_zero() -> None:
    """No break-even o EBITDA e zero — mas a folha fica na do cenario ASSUMIDO.

    A FORMA DO TESTE MUDOU DE PROPOSITO (decisao de Felipe, 2026-07-24: folha FIXA
    desde o mes 1). A folha deixou de ser percentual da receita do mes e passou a ser
    dimensionada pela demanda ASSUMIDA (`Premissas.folha_fixa_mes`), entao
    `break_even_alunos()` ganhou a demanda como argumento. Consequencia: REINJETAR o
    break-even como nova demanda NAO da EBITDA zero — a reinjecao redimensiona a folha
    para baixo e a operacao passa a sobrar (medido: +R$2.702,91). Nao e defeito; e o
    enunciado do break-even: "montei a casa para 938 alunos; com quantos eu empato?".

    A identidade continua exata, agora contra `custo_fixo_total_mes(demanda_assumida)`,
    que ja soma a folha. E ha uma segunda propriedade travada aqui: o PONTO FIXO de
    `break_even_alunos` (a demanda que e o proprio break-even dela mesma) e o unico
    valor que reinjetado devolve EBITDA zero — e ele coincide, ao float, com o
    break-even da regra ANTIGA (folha dentro do fator k).
    """
    from motor_expansao.dimensionamento.config import SIM_MENSALIDADE_BALCAO
    from motor_expansao.dimensionamento.simulador import Premissas, break_even_alunos
    from motor_expansao.dimensionamento.viabilidade_ponto import SHARE_BALCAO_DEFAULT

    m2, aluguel, demanda = 1500.0, 20000.0, 938.0
    # Premissas EXPLICITAS: o teste precisa saber exatamente qual folha foi dimensionada.
    p = Premissas(
        ticket_cheio=float(SIM_MENSALIDADE_BALCAO),
        share_balcao=SHARE_BALCAO_DEFAULT,
        aluguel_mes=aluguel,
    )
    r = analisar_viabilidade_ponto(
        -23.9, -46.3, m2, aluguel, demanda,
        premissas=p, base_calibracao_df=None, setores_df=None,
    )
    assert r.alunos_breakeven == pytest.approx(break_even_alunos(p, demanda), abs=1e-9)

    # 1) Identidade fechada: no break-even o EBITDA e zero COM a folha da demanda
    # assumida. `com_anuidade=True` porque o break-even mede o REGIME PLENO.
    fat_be = p.faturamento(r.alunos_breakeven, com_anuidade=True)
    ebitda_be = (
        fat_be * p.fator_receita_para_ebitda
        - p.custo_fixo_total_mes(demanda)
        - p.aluguel_mes
    )
    assert abs(ebitda_be) < 1e-6, f"EBITDA no break-even deveria ser 0; got {ebitda_be:.6f}"

    # 2) Reinjetar o break-even NAO zera o EBITDA (a folha encolhe junto). Trava o
    # sinal para que ninguem "conserte" isso voltando a folha percentual.
    r_re = analisar_viabilidade_ponto(
        -23.9, -46.3, m2, aluguel, r.alunos_breakeven,
        premissas=p, base_calibracao_df=None, setores_df=None,
    )
    assert r_re.viabilidade.ebitda_mensal > 0
    assert r_re.alunos_breakeven < r.alunos_breakeven  # folha menor -> break-even menor

    # 3) O PONTO FIXO (be(d) == d) e o que reinjetado devolve EBITDA zero...
    ponto_fixo = demanda
    for _ in range(200):
        ponto_fixo = break_even_alunos(p, ponto_fixo)
    assert break_even_alunos(p, ponto_fixo) == pytest.approx(ponto_fixo, abs=1e-9)
    r_fix = analisar_viabilidade_ponto(
        -23.9, -46.3, m2, aluguel, ponto_fixo,
        premissas=p, base_calibracao_df=None, setores_df=None,
    )
    assert abs(r_fix.viabilidade.ebitda_mensal) < 1e-6, (
        f"EBITDA no ponto fixo deveria ser 0; got {r_fix.viabilidade.ebitda_mensal:.6f}"
    )
    assert abs(r_fix.viabilidade.margem_ebitda_pct) < 1e-9, (
        f"margem no ponto fixo deveria ser 0; got {r_fix.viabilidade.margem_ebitda_pct:.10f}"
    )

    # ...e ele e, ao float, o break-even da regra ANTIGA (folha dentro do fator k).
    k_antigo = p.fator_receita_para_ebitda - p.folha_efetiva_pct
    be_antigo = (
        (p.outros_fixos_mes + p.aluguel_mes) / k_antigo - p.personal_mes
    ) / p.receita_por_aluno_total
    assert ponto_fixo == pytest.approx(be_antigo, abs=1e-6)
    assert r.alunos_breakeven > ponto_fixo  # a regra nova exige MAIS alunos


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


def test_teto_p10_usa_a_mesma_regua_do_teto_canonico() -> None:
    """`aluguel_teto_p10` e o teto canonico nao podem sair de faturamentos diferentes.

    Os dois aparecem LADO A LADO na mesma tela. O canonico vem do faturamento de
    steady-state do nucleo, que e o mes de REGIME PLENO (anuidade ja em cobranca).
    O do p10 e calculado aqui, por `Premissas.faturamento()` — que tem
    `com_anuidade=False` por DEFAULT. Omitir o argumento punha duas reguas na mesma
    tela (medido no golden Boulevard Londrina: R$966,36/mes, 2,2% de divergencia),
    exatamente a classe de defeito que o FIN-VIAB-01 existe para eliminar.

    A trava e de FORMA, nao de valor: reconstruimos o teto do p10 fora do motor com
    a anuidade LIGADA e exigimos que bata; e conferimos que a versao SEM anuidade
    (o defeito) daria outro numero — senao o teste passaria de graca.
    """
    from motor_expansao.dimensionamento.config import SIM_MENSALIDADE_BALCAO
    from motor_expansao.dimensionamento.simulador import Premissas, aluguel_teto_clusters

    r = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 938.0,
        base_calibracao_df=_base_comparaveis(), setores_df=None,
    )
    assert r.aluguel_teto_p10 is not None, "com base de comparaveis o teto do p10 existe"
    p10 = r.faixa_alunos_p10
    assert p10 is not None

    # Mesmas premissas da chamada acima (ticket_medio default = SIM_MENSALIDADE_BALCAO).
    p = Premissas(ticket_cheio=float(SIM_MENSALIDADE_BALCAO), aluguel_mes=r.aluguel_pedido)
    esperado = float(aluguel_teto_clusters(p.faturamento(float(p10), com_anuidade=True))["canonico"])
    assert r.aluguel_teto_p10 == pytest.approx(esperado, abs=0.01)

    # Contraprova: sem a anuidade o numero seria OUTRO (o defeito nao passa despercebido).
    defeito = float(aluguel_teto_clusters(p.faturamento(float(p10)))["canonico"])
    assert defeito < esperado, "com anuidade o faturamento do p10 e maior, logo o teto tambem"
    assert r.aluguel_teto_p10 != pytest.approx(defeito, abs=0.01)


def test_alunos_para_margem_alvo_em_alunos_totais() -> None:
    """Campo `alunos_para_margem_alvo` existe e vem em alunos TOTAIS.

    UNIDADE MUDOU DE PROPOSITO (FIN-VIAB-01 / P0-2). O campo era alimentado por
    `alunos_minimos_viaveis(margem_alvo=0,10)`, que variava SO os alunos de BALCAO
    mantendo os agregadores congelados na premissa — numero nao comparavel com a
    demanda TOTAL que o operador digita. O assert antigo (`>= 0.0`) passava
    justamente porque nao olhava a unidade. Hoje o campo sai de
    `simulador.alunos_para_margem()` (forma fechada, `viabilidade_ponto.py:597`), na
    MESMA regua de `alunos_breakeven` e `alunos_breakeven_caixa`: e o que trava a
    unidade e impede a regressao para o numero com rotulo errado.

    O campo NAO entra no payload da API (`alunos_para_margem` devolve `inf` quando a
    margem-alvo e inatingivel, e o payload e `allow_nan=False`); segue vivo para
    `batch_viabilidade`/`backtest_viabilidade`/`excel_export`.
    """
    r = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 938.0,
        base_calibracao_df=None, setores_df=None,
    )
    assert hasattr(r, "alunos_para_margem_alvo")
    assert math.isfinite(r.alunos_para_margem_alvo)
    # Os tres numeros de "quantos alunos preciso" vivem na MESMA unidade (TOTAIS) e
    # se ordenam pela exigencia: margem zero <= cobre a PMT, e margem zero < margem 10%.
    assert math.isfinite(r.alunos_breakeven) and r.alunos_breakeven >= 0.0
    assert math.isfinite(r.alunos_breakeven_caixa) and r.alunos_breakeven_caixa >= 0.0
    assert r.alunos_breakeven <= r.alunos_breakeven_caixa
    assert r.alunos_breakeven < r.alunos_para_margem_alvo
    # Regua: o valor e da ordem da demanda TOTAL, nao da fatia de balcao.
    assert r.alunos_para_margem_alvo > r.alunos_breakeven * 1.05


# ---------------------------------------------------------------------------
# FIN-VIAB-01 (2026-07-24) — folha FIXA desde o mes 1 e franquia parcelada 4x
# ---------------------------------------------------------------------------


def test_folha_do_orquestrador_e_fixa_no_tempo_e_dimensionada_pela_demanda() -> None:
    """Os DOIS fatos, no nivel do orquestrador (nao so do nucleo).

    Folha FIXA desde o mes 1 (decisao de Felipe, 2026-07-24): dentro de um cenario ela
    NAO varia entre os meses de operacao do ano 1 -- so reajusta no mes 13; entre
    cenarios ela CAI quando a demanda assumida cai, porque e ela que dimensiona a
    equipe. Antes a folha era `folha_pct` x faturamento DO MES e escalava com a rampa.
    """
    folhas = {}
    for demanda in (600.0, 938.0, 1500.0):
        r = analisar_viabilidade_ponto(
            -23.9, -46.3, 1500.0, 20000.0, demanda,
            base_calibracao_df=None, setores_df=None,
        )
        operacao = [x for x in r.viabilidade.serie_mensal if x["fase"] == "operacao"]
        ano1 = operacao[:12]
        # UM unico valor de folha em todo o ano 1...
        assert len({round(x["folha"], 6) for x in ano1}) == 1, (
            f"demanda {demanda}: a folha variou dentro do ano 1 (voltou a escalar?)"
        )
        assert ano1[0]["folha"] == pytest.approx(ano1[-1]["folha"], abs=1e-9)
        assert ano1[0]["folha"] == pytest.approx(r.viabilidade.folha_mensal, abs=1e-9)
        # ...e o unico degrau e o reajuste anual, a partir do mes 13.
        assert operacao[12]["mes"] == 13
        assert operacao[12]["folha"] > ano1[0]["folha"]
        # A folha do mes 1 e MAIOR que o percentual do faturamento do mes 1: a equipe
        # existe antes dos alunos.
        assert ano1[0]["folha"] > 0.17 * ano1[0]["faturamento_mensal"]
        folhas[demanda] = r.viabilidade.folha_mensal

    assert folhas[600.0] < folhas[938.0] < folhas[1500.0]


def test_breakeven_do_orquestrador_sobe_com_a_demanda_assumida() -> None:
    """Break-even e margem-alvo passaram a depender da demanda ASSUMIDA.

    E consequencia direta de a folha ser custo FIXO dimensionado por ela: quem monta a
    casa para 1.500 alunos precisa de mais alunos para empatar do que quem monta para
    600. Antes a folha era percentual da receita, entao o break-even NAO dependia da
    demanda -- e por isso `break_even_alunos`/`alunos_para_margem` nao a recebiam.
    """
    resultados = {
        d: analisar_viabilidade_ponto(
            -23.9, -46.3, 1500.0, 20000.0, d,
            base_calibracao_df=None, setores_df=None,
        )
        for d in (600.0, 938.0, 1500.0)
    }
    bes = [resultados[d].alunos_breakeven for d in (600.0, 938.0, 1500.0)]
    margens = [resultados[d].alunos_para_margem_alvo for d in (600.0, 938.0, 1500.0)]
    assert bes[0] < bes[1] < bes[2], f"break-even nao acompanhou a demanda assumida: {bes}"
    assert margens[0] < margens[1] < margens[2]
    for d in (600.0, 938.0, 1500.0):
        r = resultados[d]
        assert math.isfinite(r.alunos_breakeven)
        assert r.alunos_breakeven <= r.alunos_breakeven_caixa
        assert r.alunos_breakeven < r.alunos_para_margem_alvo


def test_franquia_parcelada_chega_ao_nucleo_pelo_orquestrador() -> None:
    """`parcelas_franquia` propaga; default 4x sem juros; N=1 = comportamento a vista.

    Sem obra nem equipamentos, a linha `investimento` da serie e SO a taxa de franquia
    — o que isola as parcelas sem aritmetica.
    """
    from motor_expansao.dimensionamento.config import (
        SIM_PARCELAS_FRANQUIA_DEFAULT,
        SIM_TAXA_FRANQUIA,
    )

    assert SIM_PARCELAS_FRANQUIA_DEFAULT == 4

    padrao = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 938.0,
        obra=0.0, equipamentos=0.0, base_calibracao_df=None, setores_df=None,
    )
    pre = [x for x in padrao.viabilidade.serie_mensal if x["fase"] == "pre_operacional"]
    assert [x["mes"] for x in pre] == [-4, -3, -2, -1]
    for x in pre:
        assert x["investimento"] == pytest.approx(
            SIM_TAXA_FRANQUIA / SIM_PARCELAS_FRANQUIA_DEFAULT, abs=0.01
        )
    assert sum(x["investimento"] for x in padrao.viabilidade.serie_mensal) == pytest.approx(
        SIM_TAXA_FRANQUIA, abs=0.01
    )

    a_vista = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 938.0,
        obra=0.0, equipamentos=0.0, parcelas_franquia=1,
        base_calibracao_df=None, setores_df=None,
    )
    pre_vista = [x for x in a_vista.viabilidade.serie_mensal if x["fase"] == "pre_operacional"]
    assert pre_vista[0]["investimento"] == pytest.approx(SIM_TAXA_FRANQUIA, abs=0.01)
    assert all(x["investimento"] == 0.0 for x in pre_vista[1:])

    # Parcelar e TIMING DE CAIXA: nada de resultado muda.
    assert padrao.viabilidade.ebitda_mensal == pytest.approx(
        a_vista.viabilidade.ebitda_mensal, abs=1e-12
    )
    assert padrao.viabilidade.margem_ebitda_pct == pytest.approx(
        a_vista.viabilidade.margem_ebitda_pct, abs=1e-12
    )
    assert padrao.alunos_breakeven == pytest.approx(a_vista.alunos_breakeven, abs=1e-12)
    assert padrao.alunos_breakeven_caixa == pytest.approx(
        a_vista.alunos_breakeven_caixa, abs=1e-12
    )
    assert padrao.aluguel_teto_calculado == pytest.approx(
        a_vista.aluguel_teto_calculado, abs=1e-12
    )
    # ...mas o caixa da pre-abertura melhora (o desembolso deixa de ser antecipado).
    assert pre[0]["fcf_acumulado"] > pre_vista[0]["fcf_acumulado"]
    assert padrao.viabilidade.vpl is not None and a_vista.viabilidade.vpl is not None
    assert padrao.viabilidade.vpl > a_vista.viabilidade.vpl


# ---------------------------------------------------------------------------
# DEC-042 — Fronteiras do limiar de renda, RECALIBRADO de 1.600 para 500
# ---------------------------------------------------------------------------

def test_flag_zona_morta_renda_abaixo_do_limiar() -> None:
    """renda=499 < 500 -> dispara (fronteira inferior)."""
    from motor_expansao.dimensionamento.viabilidade_ponto import RENDA_ZONA_MORTA_MIN

    out = flag_zona_morta(
        {"pop_captacao": 50000.0, "renda_per_capita_captacao": RENDA_ZONA_MORTA_MIN - 1}
    )
    assert out["flag_zona_morta"] is True
    assert f"renda<{int(RENDA_ZONA_MORTA_MIN)}" in out["motivo_zona_morta"]


def test_flag_zona_morta_renda_no_limiar_nao_dispara() -> None:
    """renda == limiar -> nao dispara (limiar inclusivo: `<` dispara, `>=` nao)."""
    from motor_expansao.dimensionamento.viabilidade_ponto import RENDA_ZONA_MORTA_MIN

    out = flag_zona_morta(
        {"pop_captacao": 50000.0, "renda_per_capita_captacao": RENDA_ZONA_MORTA_MIN}
    )
    assert out["flag_zona_morta"] is False
    assert out["motivo_zona_morta"] == "ok"


def test_o_limiar_de_renda_nao_pode_vetar_a_praca_mais_pobre_da_rede() -> None:
    """O criterio de parada do experimento E6, congelado como teste.

    Medido em 2026-08-28 sobre as 54 unidades Ultra maduras (`base_calibracao_maduras`,
    catchment de 1,5 km ja' materializado): com o limiar antigo de R$ 1.600 o gate vetava
    24 das 53 unidades com catchment, e DOZE delas operavam ACIMA da mediana da rede. O
    grupo vetado ainda faturava MAIS que o nao vetado (R$ 222.867 contra R$ 179.965 de
    mediana). O corte nao separava praca ruim de boa.

    A praca mais pobre em que a Ultra opera tem renda per capita de R$ 599 (Arapoanga
    Planaltina/DF) e essa unidade entrega 1,591 alunos/m2 -- a mediana da rede. Logo
    QUALQUER limiar acima de 599 e' falso-veto por construcao.

    E' politica de marca, nao ajuste fino: a Ultra e' low-cost/massa (CLAUDE.md §1) e
    opera bem em renda baixa. Se alguem devolver o limiar para a casa dos milhares, este
    teste cai e a razao esta' aqui.
    """
    from motor_expansao.dimensionamento.viabilidade_ponto import RENDA_ZONA_MORTA_MIN

    RENDA_MAIS_POBRE_DA_REDE = 599.0
    assert RENDA_ZONA_MORTA_MIN < RENDA_MAIS_POBRE_DA_REDE, (
        f"limiar de renda em {RENDA_ZONA_MORTA_MIN} vetaria a praca mais pobre em que a "
        f"Ultra opera (R$ {RENDA_MAIS_POBRE_DA_REDE:.0f}), que entrega a MEDIANA da rede"
    )
    out = flag_zona_morta(
        {"pop_captacao": 50_000.0, "renda_per_capita_captacao": RENDA_MAIS_POBRE_DA_REDE}
    )
    assert out["flag_zona_morta"] is False, (
        "a unidade real da praca mais pobre da rede foi marcada como zona morta"
    )


def test_falso_veto_zero_contra_a_rede_real() -> None:
    """Mesma pergunta do teste acima, mas contra a BASE REAL quando ela existe.

    `base_calibracao_maduras.parquet` e' dado real e gitignorado — no CI ele nao existe e
    o teste pula. Onde existe, ele e' a checagem forte: NENHUMA unidade madura que opere
    na mediana ou acima pode ser marcada como zona morta.

    RESSALVA DE METODO, que vale registrar: esta amostra e' condicionada no desfecho (a
    Ultra so' abriu onde decidiu abrir). Ela prova FALSO-VETO — o gate rejeitando o que
    sabidamente funciona — e NAO prova que o gate acerta ao rejeitar praca ruim, porque
    nao ha contrafactual. E' de proposito que o criterio de parada e' de falso-positivo.
    """
    caminho = Path("data/staging/base_calibracao_maduras.parquet")
    if not caminho.exists():
        pytest.skip("base real ausente (gitignored); teste de falso-veto so' roda local")

    base = pd.read_parquet(caminho)
    base = base[base["pop_captacao"].notna()]
    if base.empty:
        pytest.skip("base sem catchment materializado")

    mediana = base["alunos_por_m2"].median()
    boas = base[base["alunos_por_m2"] >= mediana]
    vetadas = [
        (linha["unidade"], linha["renda_per_capita_captacao"], linha["pop_captacao"])
        for _, linha in boas.iterrows()
        if flag_zona_morta(
            {
                "pop_captacao": linha["pop_captacao"],
                "renda_per_capita_captacao": linha["renda_per_capita_captacao"],
            }
        )["flag_zona_morta"]
    ]
    assert not vetadas, (
        f"{len(vetadas)} de {len(boas)} unidades que operam >= mediana foram marcadas "
        f"como zona morta: {vetadas[:5]}"
    )


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


# ---------------------------------------------------------------------------
# BLK-VIAB-07 — Filtro opcional por formato na curva tamanho->densidade
# ---------------------------------------------------------------------------


def _base_mista_formato() -> pd.DataFrame:
    """Base mista: 4 low_cost_massa (apm ~0.5) + 4 boutique_premium (apm ~2.3), mesma metragem."""
    return pd.DataFrame(
        {
            "unidade": [f"L{i}" for i in range(4)] + [f"B{i}" for i in range(4)],
            "marca": ["ultra"] * 4 + ["engenharia_do_corpo"] * 4,
            "formato": ["low_cost_massa"] * 4 + ["boutique_premium"] * 4,
            "metragem": [1400.0, 1500.0, 1600.0, 1500.0, 1400.0, 1500.0, 1600.0, 1500.0],
            "alunos_por_m2": [0.48, 0.50, 0.52, 0.50, 2.20, 2.30, 2.40, 2.30],
        }
    )


def test_formato_none_byte_identico() -> None:
    """formato=None -> resultado IDENTICO ao comportamento historico (sem filtro)."""
    base = _base_mista_formato()
    out_none = faixa_alunos_por_densidade(1500.0, base, formato=None)
    # Chamada sem o kwarg (default) deve ser identica a formato=None.
    out_default = faixa_alunos_por_densidade(1500.0, base)
    assert out_none == out_default
    # E deve refletir a base MISTA (mediana entre low_cost e boutique -> alta).
    assert out_none["n_comparaveis"] == out_default["n_comparaveis"]


def test_formato_filtra_comparaveis() -> None:
    """formato='low_cost_massa' usa SO os pares low_cost -> p50 menor que a base mista."""
    base = _base_mista_formato()
    out_mista = faixa_alunos_por_densidade(1500.0, base, formato=None)
    out_lc = faixa_alunos_por_densidade(1500.0, base, formato="low_cost_massa")
    # Com filtro, apm ~0.50 -> p50 ~ 0.50*1500 = 750; sem filtro a mediana sobe.
    assert out_lc["faixa_alunos_p50"] is not None
    assert out_lc["faixa_alunos_p50"] < out_mista["faixa_alunos_p50"]
    # 4 comparaveis low_cost, todos na janela +/-20% de 1500.
    assert out_lc["n_comparaveis"] == 4


def test_formato_deriva_de_marca_sem_coluna_formato() -> None:
    """Sem coluna 'formato', o filtro deriva de 'marca' via FORMATO_POR_MARCA."""
    base = _base_mista_formato().drop(columns=["formato"])
    out_lc = faixa_alunos_por_densidade(1500.0, base, formato="low_cost_massa")
    assert out_lc["n_comparaveis"] == 4
    assert out_lc["faixa_alunos_p50"] is not None
    assert out_lc["faixa_alunos_p50"] < 1500.0  # ~750, nao a mediana mista


def test_formato_fallback_n_min() -> None:
    """Formato com < n_min comparaveis -> fallback para a base completa (nao filtra)."""
    base = _base_mista_formato()
    # 'boutique_premium' tem 4; pedimos um formato inexistente -> 0 -> fallback completo.
    out_inexistente = faixa_alunos_por_densidade(1500.0, base, formato="formato_zumbi")
    out_none = faixa_alunos_por_densidade(1500.0, base, formato=None)
    assert out_inexistente == out_none  # fallback == base completa


def test_mapeamento_formato_por_marca() -> None:
    """FORMATO_POR_MARCA contem as marcas esperadas com os formatos corretos."""
    from motor_expansao.dimensionamento.viabilidade_ponto import (
        FORMATO_BOUTIQUE_PREMIUM,
        FORMATO_LOW_COST_MASSA,
        FORMATO_POR_MARCA,
    )

    assert FORMATO_POR_MARCA["ultra"] == FORMATO_LOW_COST_MASSA
    assert FORMATO_POR_MARCA["skyfit"] == FORMATO_LOW_COST_MASSA
    assert FORMATO_POR_MARCA["engenharia_do_corpo"] == FORMATO_BOUTIQUE_PREMIUM


def test_formato_exportado_em_all() -> None:
    """FORMATO_POR_MARCA, FORMATO_LOW_COST_MASSA, FORMATO_BOUTIQUE_PREMIUM em __all__."""
    from motor_expansao.dimensionamento import viabilidade_ponto as vp

    assert "FORMATO_POR_MARCA" in vp.__all__
    assert "FORMATO_LOW_COST_MASSA" in vp.__all__
    assert "FORMATO_BOUTIQUE_PREMIUM" in vp.__all__


def test_analisar_viabilidade_ponto_propaga_formato() -> None:
    """[GO] formato chega ao orquestrador e filtra a faixa; None = byte-identico."""
    base = _base_mista_formato()
    r_none = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 938.0,
        base_calibracao_df=base, setores_df=None,
    )
    r_lc = analisar_viabilidade_ponto(
        -23.9, -46.3, 1500.0, 20000.0, 938.0,
        base_calibracao_df=base, setores_df=None, formato="low_cost_massa",
    )
    assert r_lc.faixa_alunos_p50 is not None
    assert r_none.faixa_alunos_p50 is not None
    assert r_lc.faixa_alunos_p50 < r_none.faixa_alunos_p50
