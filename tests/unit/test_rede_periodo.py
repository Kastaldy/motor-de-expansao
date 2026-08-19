"""Fechamento de um intervalo LIVRE de datas sobre a base Growth.

A base mistura cumulativas que resetam no dia 1 com snapshots do dia. Num mês civil isso
se resolve pegando o último dia; num intervalo qualquer, não: é preciso fatiar por mês,
descontar a base de cada porção e somar as parcelas. Os testes daqui travam essa conta e,
antes de tudo, travam a EQUIVALÊNCIA -- para um mês civil inteiro, `fechamento_periodo`
tem de devolver exatamente o `fechamento_mensal` daquele mês. Se a equivalência cair, a
tela passa a mostrar dois números diferentes para o mesmo julho.
"""

from __future__ import annotations

import time

import pandas as pd
import pytest

from motor_expansao.dashboard import rede_metricas as rm
from tests.unit.rede_fixtures import base, mes, unidade_saudavel

MAIO = (pd.Timestamp("2026-05-01"), pd.Timestamp("2026-05-31"))

# 31 dias em maio/dezembro e 30 em abril: totais escolhidos para dar R$ 10.000 por dia
# redondos, então cada parcela esperada se lê de cabeça.
FATURAMENTO_31_DIAS = 310_000.0
FATURAMENTO_30_DIAS = 300_000.0


def _uma(fech: pd.DataFrame) -> pd.Series:
    assert len(fech) == 1, f"esperava uma unidade, vieram {len(fech)}"
    return fech.iloc[0]


# ---------------------------------------------------------------------------
# Equivalencia com o fechamento mensal (o teste que segura a tela)
# ---------------------------------------------------------------------------


def _base_dois_meses() -> pd.DataFrame:
    """Abril + maio com três perfis: normal, NPS sentinela e unidade que abriu em maio."""
    return rm.preparar_base(
        base(
            unidade_saudavel("A", 2026, 4, snapshots={"pagantes": 1_000.0, "NPS": 70.0}),
            unidade_saudavel(
                "A",
                2026,
                5,
                snapshots={"pagantes": 950.0, "NPS": 72.0, "ativos_total": 1_300.0},
                cumulativas={"faturamento": 280_000.0, "cancelados": 55.0, "vendas": 90.0},
            ),
            unidade_saudavel("B", 2026, 4, snapshots={"pagantes": 400.0, "NPS": 10.0}),
            unidade_saudavel(
                "B",
                2026,
                5,
                snapshots={"pagantes": 380.0, "NPS": 999.0, "em_cobranca": 40.0},
                cumulativas={"visitas": 150.0, "convertidos": 60.0, "cancelados": 12.0},
            ),
            # Só existe em maio: inaugurou dentro do mês. Fecha os dois lados do churn sem
            # base (`pagantes_m1` e `pagantes_inicio` nulos) na mesma tacada.
            unidade_saudavel("C", 2026, 5, inauguracao="10/05/2026"),
        )
    )


def test_periodo_de_um_mes_civil_reproduz_o_fechamento_mensal() -> None:
    """O contrato central: "maio" e "01/05 a 31/05" são o MESMO número, coluna a coluna.

    Vale para as cumulativas (parcela única, sem base a descontar porque o mês começa no
    dia 1), para os snapshots, para as derivadas e para o churn -- cujo denominador muda
    de nome (`pagantes_m1` -> `pagantes_inicio`) mas não de valor quando a série do mês
    anterior existe.
    """
    df = _base_dois_meses()
    mensal = rm.fechamento_mensal(df)
    mensal = mensal[mensal["competencia"] == "2026-05"].set_index("unidade_id")
    periodo = rm.fechamento_periodo(df, *MAIO).set_index("unidade_id")

    assert list(periodo.index) == list(mensal.index), "mesma ordem e as mesmas unidades"

    comuns = [c for c in mensal.columns if c in periodo.columns]
    assert len(comuns) > 30, f"comparação rasa demais: só {len(comuns)} colunas em comum"
    for coluna in comuns:
        pd.testing.assert_series_equal(
            periodo[coluna],
            mensal[coluna],
            check_dtype=False,
            check_names=False,
            obj=f"coluna {coluna}",
        )

    # ...e o que só mudou de nome tem de bater também.
    assert list(periodo["periodo_completo"]) == list(mensal["mes_completo"])
    assert list(periodo["operacao_periodo_cheio"]) == list(mensal["operacao_mes_cheio"])
    pd.testing.assert_series_equal(
        periodo["pagantes_inicio"],
        mensal["pagantes_m1"],
        check_dtype=False,
        check_names=False,
    )
    assert float(periodo.loc["a-sp", "pagantes_inicio"]) == 1_000.0, "a base veio de abril"
    assert pd.isna(periodo.loc["c-sp", "churn_pct"]), "sem mês anterior, churn é desconhecido"


def test_equivalencia_tambem_no_mes_incompleto() -> None:
    """Mês civil com coleta parcial: incompleto dos dois lados, com o mesmo agregado.

    A régua de completude é a mesma (`DIAS_MINIMOS_MES_COMPLETO` + tolerância de fim de
    mês); o que o intervalo não pode fazer é se declarar fechado só porque somou 25 dias.
    """
    df = rm.preparar_base(base(unidade_saudavel("X", 2026, 5, dias=12)))
    mensal = _uma(rm.fechamento_mensal(df))
    periodo = _uma(rm.fechamento_periodo(df, *MAIO))

    assert bool(mensal["mes_completo"]) is False
    assert bool(periodo["periodo_completo"]) is False
    assert int(periodo["dias_com_dado"]) == 12
    assert periodo["dia_ref"] == pd.Timestamp("2026-05-12")
    assert float(periodo["faturamento"]) == pytest.approx(float(mensal["faturamento"]))


def test_periodo_completo_exige_mes_civil_inteiro() -> None:
    """26 dias de coleta impecáveis não fazem de "06/05 a 31/05" um mês fechado.

    As réguas do time (faixa de faturamento, diagnóstico) são limiares de MÊS INTEIRO.
    Marcar um recorte de 26 dias como completo faria o diagnóstico rodar sobre ele.
    """
    df = rm.preparar_base(base(unidade_saudavel("X", 2026, 5)))
    assert bool(_uma(rm.fechamento_periodo(df, *MAIO))["periodo_completo"]) is True
    quase = rm.fechamento_periodo(df, pd.Timestamp("2026-05-06"), pd.Timestamp("2026-05-31"))
    assert int(_uma(quase)["dias_com_dado"]) == 26
    assert bool(_uma(quase)["periodo_completo"]) is False


# ---------------------------------------------------------------------------
# Cumulativas: a subtracao da base e a soma das parcelas
# ---------------------------------------------------------------------------


def test_intervalo_no_meio_do_mes_desconta_a_base() -> None:
    """De 11 a 20 vale o que ACONTECEU nesses dias, não o acumulado desde o dia 1.

    Sem descontar o valor do dia 10, o intervalo herdaria dez dias que não lhe pertencem.
    """
    df = rm.preparar_base(
        base(mes("X", 2026, 5, cumulativas={"faturamento": FATURAMENTO_31_DIAS}))
    )
    linha = _uma(rm.fechamento_periodo(df, pd.Timestamp("2026-05-11"), pd.Timestamp("2026-05-20")))
    assert float(linha["faturamento"]) == pytest.approx(100_000.0)
    assert float(linha["faturamento"]) != pytest.approx(200_000.0), "isto seria o MTD do dia 20"
    assert int(linha["dias_com_dado"]) == 10


def test_intervalo_cruza_a_virada_de_mes_somando_parcelas() -> None:
    """21/04 a 10/05 = (abril até o fim - abril até 20) + (maio até 10).

    Pegar o último valor do intervalo devolveria só os dez dias de maio - o reset do dia
    1 apagou abril. Somar os valores diários contaria o acumulado dezenas de vezes.
    """
    df = rm.preparar_base(
        base(
            mes(
                "X",
                2026,
                4,
                cumulativas={"faturamento": FATURAMENTO_30_DIAS},
                snapshots={"pagantes": 1_000.0},
            ),
            mes(
                "X",
                2026,
                5,
                cumulativas={"faturamento": FATURAMENTO_31_DIAS},
                snapshots={"pagantes": 900.0},
            ),
        )
    )
    linha = _uma(rm.fechamento_periodo(df, pd.Timestamp("2026-04-21"), pd.Timestamp("2026-05-10")))
    assert float(linha["faturamento"]) == pytest.approx(200_000.0)
    assert float(linha["faturamento"]) != pytest.approx(100_000.0), "só a parcela de maio"
    assert int(linha["dias_com_dado"]) == 20
    assert linha["dia_ref"] == pd.Timestamp("2026-05-10")
    # O snapshot atravessa a virada sem somar: vale a foto do ÚLTIMO mês da janela.
    assert float(linha["pagantes"]) == 900.0
    assert float(linha["pagantes_inicio"]) == 1_000.0, "a véspera de 21/04 ainda é abril"


def test_intervalo_cruza_a_virada_de_ano() -> None:
    """A virada de ano é só mais uma virada de mês -- desde que a competência seja Period.

    Comparar competência como texto ("2025-12" > "2026-01") inverteria a ordem dos meses e
    a parcela de dezembro sairia como se fosse a mais recente.
    """
    df = rm.preparar_base(
        base(
            mes("X", 2025, 12, cumulativas={"faturamento": FATURAMENTO_31_DIAS}),
            mes("X", 2026, 1, cumulativas={"faturamento": FATURAMENTO_31_DIAS}),
        )
    )
    linha = _uma(rm.fechamento_periodo(df, pd.Timestamp("2025-12-21"), pd.Timestamp("2026-01-10")))
    # dezembro: 310.000 - 200.000 = 110.000; janeiro: 100.000 - 0 = 100.000.
    assert float(linha["faturamento"]) == pytest.approx(210_000.0)
    assert int(linha["dias_com_dado"]) == 21
    assert linha["dia_ref"] == pd.Timestamp("2026-01-10")
    # `meses_operacao` conta até o mês de FIM do intervalo (jan/2026, não dez/2025).
    assert int(linha["meses_operacao"]) == 72


def test_estorno_dentro_do_mes_nao_e_clampado() -> None:
    """Parcela NEGATIVA é legítima: `cancelados` cai em 36,7% dos unidade-mês por estorno.

    Zerar o negativo inventaria cancelamento que a unidade não teve -- e o churn da janela
    sairia maior do que a realidade justamente onde a operação consertou o registro.
    """
    df = rm.preparar_base(
        base(
            unidade_saudavel(
                "X", 2026, 5, dias=6, trajetoria={"cancelados": [10, 20, 30, 40, 25, 25]}
            )
        )
    )
    linha = _uma(rm.fechamento_periodo(df, pd.Timestamp("2026-05-04"), pd.Timestamp("2026-05-06")))
    assert float(linha["cancelados"]) == pytest.approx(-5.0), "25 (dia 6) - 30 (dia 3)"


def test_dia_faltando_na_serie_usa_o_ultimo_dia_com_dado() -> None:
    """Buraco na ingestão: a ponta escorrega para o último dia COM DADO, sem interpolar.

    Vale nas duas pontas -- a base do intervalo também recua até onde há registro.
    """
    linhas = mes("X", 2026, 5, cumulativas={"faturamento": FATURAMENTO_31_DIAS})
    com_buracos = [linha for linha in linhas if linha["data"] not in ("10/05/2026", "20/05/2026")]
    df = rm.preparar_base(base(com_buracos))
    linha = _uma(rm.fechamento_periodo(df, pd.Timestamp("2026-05-11"), pd.Timestamp("2026-05-20")))
    # fim = dia 19 (190.000); base = dia 9 (90.000), porque o dia 10 não existe.
    assert float(linha["faturamento"]) == pytest.approx(100_000.0)
    assert int(linha["dias_com_dado"]) == 9
    assert linha["dia_ref"] == pd.Timestamp("2026-05-19")


def test_intervalo_de_um_dia_devolve_o_dia() -> None:
    """Ponta a ponta no mesmo dia: [15, 15] é o que aconteceu no dia 15, não o MTD dele."""
    df = rm.preparar_base(
        base(mes("X", 2026, 5, cumulativas={"faturamento": FATURAMENTO_31_DIAS}))
    )
    dia = pd.Timestamp("2026-05-15")
    linha = _uma(rm.fechamento_periodo(df, dia, dia))
    assert float(linha["faturamento"]) == pytest.approx(10_000.0)
    assert int(linha["dias_com_dado"]) == 1
    assert linha["dia_ref"] == dia
    assert bool(linha["periodo_completo"]) is False


# ---------------------------------------------------------------------------
# Snapshots e a base do churn
# ---------------------------------------------------------------------------


def test_snapshot_pega_o_ultimo_dia_com_dado_e_nao_o_primeiro() -> None:
    """`pagantes` é foto: vale o fim da janela, nunca o começo nem o pico."""
    df = rm.preparar_base(
        base(
            unidade_saudavel(
                "X", 2026, 5, dias=4, trajetoria={"pagantes": [1_000, 1_100, 900, 950]}
            )
        )
    )
    inicio = pd.Timestamp("2026-05-01")
    ate_o_dia_4 = _uma(rm.fechamento_periodo(df, inicio, pd.Timestamp("2026-05-04")))
    ate_o_dia_3 = _uma(rm.fechamento_periodo(df, inicio, pd.Timestamp("2026-05-03")))
    assert float(ate_o_dia_4["pagantes"]) == 950.0
    assert float(ate_o_dia_3["pagantes"]) == 900.0


def test_pagantes_inicio_vem_do_ultimo_dia_antes_do_intervalo() -> None:
    """A base do churn é a foto da VÉSPERA, mesmo que ela esteja em outro mês.

    Diferente do mensal de propósito: ali o denominador é o fechamento de `competencia-1`;
    aqui é o último dia com dado anterior a `inicio`, que é o que "a janela começou com"
    quer dizer quando a janela não respeita o calendário.
    """
    df = rm.preparar_base(
        base(
            unidade_saudavel("X", 2026, 4, snapshots={"pagantes": 1_000.0}),
            unidade_saudavel(
                "X", 2026, 5, snapshots={"pagantes": 900.0}, cumulativas={"cancelados": 62.0}
            ),
        )
    )
    linha = _uma(rm.fechamento_periodo(df, pd.Timestamp("2026-05-11"), pd.Timestamp("2026-05-20")))
    assert float(linha["pagantes_inicio"]) == 900.0, "a véspera é 10/05, já dentro de maio"
    # cancelados do intervalo = 62 * 20/31 - 62 * 10/31 = 20; churn = 20 / 900.
    assert float(linha["cancelados"]) == pytest.approx(20.0)
    assert float(linha["churn_pct"]) == pytest.approx(100.0 * 20.0 / 900.0)


def test_sem_dado_antes_do_intervalo_o_churn_e_desconhecido() -> None:
    """Nunca inf, nunca divisão por zero: sem base, churn é NaN.

    São dois casos distintos e o resultado é o mesmo -- unidade que não tem histórico
    antes da janela e unidade cuja véspera registrou zero recorrente. Um número inventado
    aqui pintaria de vermelho quem só é nova (e ainda quebraria o JSON com `Infinity`).
    """
    df = rm.preparar_base(
        base(
            unidade_saudavel("SEM HISTORICO", 2026, 5, cumulativas={"cancelados": 40.0}),
            unidade_saudavel("ZERADA", 2026, 4, snapshots={"pagantes": 0.0}),
            unidade_saudavel(
                "ZERADA", 2026, 5, snapshots={"pagantes": 500.0}, cumulativas={"cancelados": 40.0}
            ),
            unidade_saudavel("COM HISTORICO", 2026, 4, snapshots={"pagantes": 800.0}),
            unidade_saudavel(
                "COM HISTORICO",
                2026,
                5,
                snapshots={"pagantes": 780.0},
                cumulativas={"cancelados": 40.0},
            ),
        )
    )
    fech = rm.fechamento_periodo(df, *MAIO).set_index("unidade_cru")
    assert pd.isna(fech.loc["SEM HISTORICO", "pagantes_inicio"])
    assert pd.isna(fech.loc["SEM HISTORICO", "churn_pct"])
    assert pd.isna(fech.loc["ZERADA", "churn_pct"]), "denominador zero não vira inf"
    assert float(fech.loc["COM HISTORICO", "churn_pct"]) == pytest.approx(5.0)
    assert not fech["churn_pct"].isin([float("inf"), float("-inf")]).any(), "JSON não tem Infinity"


# ---------------------------------------------------------------------------
# Gate de comparabilidade e bordas
# ---------------------------------------------------------------------------


def test_unidade_inaugurada_dentro_do_intervalo_nao_e_comparavel() -> None:
    """Mesmo gate do mensal, contra a ponta ESQUERDA da janela.

    Quem abriu no dia 10 não operou o intervalo inteiro: o número é real, mas comparar
    com quem operou os 31 dias mede data de abertura, não desempenho.
    """
    df = rm.preparar_base(
        base(
            unidade_saudavel("NOVA", 2026, 5, inauguracao="10/05/2026"),
            unidade_saudavel("NA VIRADA", 2026, 5, inauguracao="01/05/2026"),
            unidade_saudavel("VELHA", 2026, 5, inauguracao="01/01/2020"),
        )
    )
    fech = rm.fechamento_periodo(df, *MAIO).set_index("unidade_cru")
    assert bool(fech.loc["NOVA", "operacao_periodo_cheio"]) is False
    assert bool(fech.loc["NA VIRADA", "operacao_periodo_cheio"]) is True, "inaugurou EM `inicio`"
    assert bool(fech.loc["VELHA", "operacao_periodo_cheio"]) is True
    # ...e num intervalo que começa DEPOIS da inauguração ela volta a ser comparável.
    tarde = rm.fechamento_periodo(df, pd.Timestamp("2026-05-11"), pd.Timestamp("2026-05-31"))
    assert bool(tarde.set_index("unidade_cru").loc["NOVA", "operacao_periodo_cheio"]) is True


@pytest.mark.parametrize(
    "descricao, inicio, fim",
    [
        ("intervalo invertido", pd.Timestamp("2026-05-31"), pd.Timestamp("2026-05-01")),
        ("intervalo sem dado", pd.Timestamp("2027-01-01"), pd.Timestamp("2027-01-31")),
    ],
)
def test_intervalo_sem_resposta_devolve_vazio(
    descricao: str, inicio: pd.Timestamp, fim: pd.Timestamp
) -> None:
    """Vazio com as MESMAS colunas: a tela quebra pela coluna que falta, não pelo `len`."""
    df = rm.preparar_base(base(unidade_saudavel("X", 2026, 5)))
    vazio = rm.fechamento_periodo(df, inicio, fim)
    assert not len(vazio), descricao
    assert set(vazio.columns) <= set(rm.fechamento_periodo(df, *MAIO).columns)
    for coluna in ("unidade_id", "faturamento", "churn_pct", "pagantes_inicio", "periodo_completo"):
        assert coluna in vazio.columns


def test_base_vazia_nao_quebra() -> None:
    vazio = rm.fechamento_periodo(pd.DataFrame(), *MAIO)
    assert not len(vazio)
    assert "pagantes_inicio" in vazio.columns


def test_fechamento_periodo_e_vetorizado() -> None:
    """Teto de tempo que impede o laço Python por unidade (o mesmo do fechamento mensal).

    100 unidades x 12 meses ~ o dobro da rede real, com o intervalo cruzando 11 viradas de
    mês -- que é o caminho caro (uma parcela por unidade-mês).
    """
    grupos = [
        unidade_saudavel(f"U{i:03d}", 2026, numero_mes)
        for i in range(100)
        for numero_mes in range(1, 13)
    ]
    df = rm.preparar_base(base(*grupos))
    inicio = time.perf_counter()
    fech = rm.fechamento_periodo(df, pd.Timestamp("2026-01-15"), pd.Timestamp("2026-12-15"))
    duracao = time.perf_counter() - inicio
    assert len(fech) == 100
    assert duracao < 3.0, f"fechamento_periodo levou {duracao:.2f}s - laço por unidade?"
