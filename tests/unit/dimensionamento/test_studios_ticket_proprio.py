"""Studios com TICKET PROPRIO no motor de viabilidade (pedido de 2026-10-05).

O QUE MUDOU
-----------
Antes o studio so' ELEVAVA o ticket cheio no front (escada 147/157/167/177) e somava
SIM_CUSTO_STUDIO ao custo fixo. Agora:

- o "ticket cheio do plano" vira TICKET DE MUSCULACAO e nao depende mais dos studios;
- cada studio (0..3) tem um ticket proprio e atende SIM_STUDIO_SHARE_DEMANDA (8%) da
  demanda TOTAL assumida;
- o split balcao/agregador (SIM_SHARE_BALCAO) vale so' sobre a demanda RESTANTE.
  Ex.: 1.000 alunos com 2 studios -> 80 + 80 nos studios e o split sobre 840
  (579,6 balcao / 260,4 agregador).

Decisoes do dono travadas aqui: o aluno de studio tem o tratamento do BALCAO (fator
(1 - churn), inadimplencia, reajuste anual do ticket e PAGA anuidade); a receita de
studio entra na base da folha (17% do faturamento maduro); o custo fixo por studio
(SIM_CUSTO_STUDIO) continua e reajusta como os demais fixos.

Contraprova central: sem studio o motor e' IDENTICO ao anterior (comparacao `==`, nao
`approx`). Os numeros do golden (`tests/contracts/test_viabilidade_golden.py`) seguem
inalterados, o que prova a mesma coisa contra valores medidos.

READ-ONLY sobre o M1: nao toca score_priorizacao, pesos nem artefatos oficiais.
"""

from __future__ import annotations

import pytest

from motor_expansao.dimensionamento import config as cfg
from motor_expansao.dimensionamento.simulador import (
    Premissas,
    break_even_alunos,
    gerar_serie_mensal_completa,
    simular,
)

TICKET_MUSCULACAO = 147.0
DEMANDA = 2304.0
INVESTIMENTO: dict[str, object] = {
    "obra": 600_000.0,
    "parcelas_obra": 4,
    "equipamentos": 1_400_000.0,
    "prazo_equipamentos": 60,
    "juros_equipamentos_am": 0.018,
    "taxa_franquia": 160_000.0,
}


def _p(**over: object) -> Premissas:
    kw: dict[str, object] = {"ticket_cheio": TICKET_MUSCULACAO, "aluguel_mes": 30_000.0}
    kw.update(over)
    return Premissas(**kw)  # type: ignore[arg-type]


def _operacao(serie: list[dict]) -> list[dict]:
    return [r for r in serie if r["fase"] == "operacao"]


# ---------------------------------------------------------------------------
# 1) O split do pedido
# ---------------------------------------------------------------------------


def test_split_do_exemplo_do_pedido() -> None:
    """1.000 alunos, 2 studios (157, 167) -> (579,6 / 260,4 / (80, 80))."""
    bal, agr, studios = _p(tickets_studios=(157.0, 167.0)).split_alunos(1000.0)
    assert bal == pytest.approx(579.6, abs=1e-9)
    assert agr == pytest.approx(260.4, abs=1e-9)
    assert studios == pytest.approx((80.0, 80.0), abs=1e-9)
    assert len(studios) == 2


@pytest.mark.parametrize("n", [0, 1, 2, 3])
def test_split_conserva_a_demanda_e_cada_studio_leva_8pct(n: int) -> None:
    p = _p(tickets_studios=cfg.SIM_TICKETS_STUDIO_PADRAO[:n])
    bal, agr, studios = p.split_alunos(DEMANDA)
    assert len(studios) == n
    assert bal + agr + sum(studios) == pytest.approx(DEMANDA, abs=1e-9)
    for a in studios:
        assert a == pytest.approx(DEMANDA * cfg.SIM_STUDIO_SHARE_DEMANDA, abs=1e-9)
    restante = DEMANDA * (1.0 - n * cfg.SIM_STUDIO_SHARE_DEMANDA)
    assert bal == pytest.approx(restante * cfg.SIM_SHARE_BALCAO, abs=1e-9)
    assert agr == pytest.approx(restante * (1.0 - cfg.SIM_SHARE_BALCAO), abs=1e-9)


def test_propriedades_de_studio_derivam_do_numero_de_tickets() -> None:
    p = _p(tickets_studios=(157.0, 167.0, 177.0))
    assert p.n_studios == 3
    assert p.share_studios_total == pytest.approx(0.24, abs=1e-12)
    assert p.share_musculacao == pytest.approx(0.76, abs=1e-12)
    assert p.custo_studios_mes == pytest.approx(3 * cfg.SIM_CUSTO_STUDIO, abs=1e-9)

    sem = _p()
    assert sem.n_studios == 0
    assert sem.share_studios_total == 0.0
    assert sem.share_musculacao == 1.0
    assert sem.custo_studios_mes == 0.0


def test_conservacao_de_alunos_em_todo_mes_da_serie() -> None:
    """Rampa inclusive: os studios rampam junto com o total, sem vazar aluno."""
    p = _p(tickets_studios=(157.0, 167.0))
    for linha in _operacao(gerar_serie_mensal_completa(DEMANDA, p)):
        total = linha["alunos_total"]
        soma = linha["alunos_balcao"] + linha["alunos_agregadores"] + linha["alunos_studios"]
        assert soma == pytest.approx(total, abs=1e-9), linha["mes"]
        assert linha["alunos_studios"] == pytest.approx(
            2 * cfg.SIM_STUDIO_SHARE_DEMANDA * total, abs=1e-9
        )


# ---------------------------------------------------------------------------
# 2) O ticket de musculacao e o do agregador nao dependem dos studios
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tickets", [(), (157.0,), (157.0, 167.0), (157.0, 167.0, 177.0)])
def test_ticket_agregador_independe_dos_studios(tickets: tuple[float, ...]) -> None:
    p = _p(tickets_studios=tickets)
    assert p.ticket_cheio == TICKET_MUSCULACAO
    assert p.ticket_agregador == pytest.approx(
        TICKET_MUSCULACAO * cfg.SIM_TICKET_AGREGADOR_FATOR, abs=1e-12
    )
    assert p.ticket_agregador == _p().ticket_agregador


# ---------------------------------------------------------------------------
# 3) Sem studio, o motor e' o de antes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "over",
    [
        {},
        {"anuidade_valor": 0.0},
        {"carencia_aluguel_meses": 4},
        {"anuidade_apenas_balcao": False},
    ],
    ids=["golden", "sem_anuidade", "carencia", "anuidade_todos"],
)
@pytest.mark.parametrize(
    "inv",
    [INVESTIMENTO, {**INVESTIMENTO, "prazo_equipamentos": 0}, {}],
    ids=["financiado", "a_vista", "sem_investimento"],
)
def test_sem_studio_e_bit_a_bit_igual_ao_caso_sem_o_campo(
    over: dict[str, object], inv: dict[str, object]
) -> None:
    sem_campo = _p(**over)
    vazio = _p(tickets_studios=(), **over)
    lista_vazia = _p(tickets_studios=[], **over)  # type: ignore[arg-type]
    assert sem_campo == vazio == lista_vazia

    r0 = simular(DEMANDA, sem_campo, **inv)  # type: ignore[arg-type]
    r1 = simular(DEMANDA, vazio, **inv)  # type: ignore[arg-type]
    assert r0 == r1  # ViabilidadeResult inteiro, serie dentro
    s0 = gerar_serie_mensal_completa(DEMANDA, sem_campo, **inv)  # type: ignore[arg-type]
    s1 = gerar_serie_mensal_completa(DEMANDA, vazio, **inv)  # type: ignore[arg-type]
    assert s0 == s1

    # As colunas novas existem e sao ZERO sem studio.
    for linha in s0:
        assert linha["alunos_studios"] == 0.0
        assert linha["receita_studios"] == 0.0
        assert linha["custo_studios"] == 0.0
    assert r0.alunos_studios_steady == 0.0
    assert r0.receita_studios_mensal == 0.0
    assert r0.custo_studios_mensal == 0.0


def test_sem_studio_split_e_o_historico() -> None:
    p = _p()
    bal, agr, studios = p.split_alunos(1000.0)
    assert (bal, agr, studios) == (1000.0 * p.share_balcao, 1000.0 * (1.0 - p.share_balcao), ())


# ---------------------------------------------------------------------------
# 4) Faturamento de steady pela formula escrita a mao
# ---------------------------------------------------------------------------


def test_faturamento_steady_bate_com_a_formula_manual() -> None:
    """1.000 alunos, studios (157, 167), anuidade ligada: steady no mes 12 (ano 1,
    sem reajuste). Tudo recomposto a mao a partir do config, sem usar o motor."""
    demanda = 1000.0
    p = _p(tickets_studios=(157.0, 167.0))
    r = simular(demanda, p, **INVESTIMENTO)  # type: ignore[arg-type]

    assert r.mes_referencia_steady == cfg.SIM_ANUIDADE_MES_INICIO == 12
    churn = cfg.SIM_CHURN
    liq = 1.0 - cfg.SIM_INADIMPLENCIA
    t_agr = TICKET_MUSCULACAO * cfg.SIM_TICKET_AGREGADOR_FATOR

    bal = 840.0 * cfg.SIM_SHARE_BALCAO          # 579,6
    agr = 840.0 * (1.0 - cfg.SIM_SHARE_BALCAO)  # 260,4
    assert bal == pytest.approx(579.6)
    assert agr == pytest.approx(260.4)

    receita_bal = bal * (1.0 - churn) * TICKET_MUSCULACAO * liq
    receita_agr = agr * t_agr * liq
    receita_studios = 80.0 * 157.0 * (1.0 - churn) * liq + 80.0 * 167.0 * (1.0 - churn) * liq
    elegivel = (1.0 - churn) ** cfg.SIM_ANUIDADE_MES_INICIO
    anuidade_mes = cfg.SIM_ANUIDADE_VALOR * elegivel / 12.0
    # Agregador nao paga anuidade; balcao e STUDIOS pagam.
    anuidade = (bal + 160.0) * anuidade_mes
    esperado = receita_bal + receita_agr + receita_studios + cfg.SIM_PERSONAL_MES_RECEITA + anuidade

    assert r.faturamento_mensal_steady == pytest.approx(esperado, abs=0.01)
    assert r.receita_studios_mensal == pytest.approx(receita_studios, abs=0.01)
    assert r.receita_anuidade_mensal == pytest.approx(anuidade, abs=0.01)
    assert r.alunos_studios_steady == pytest.approx(160.0, abs=1e-9)
    assert r.custo_studios_mensal == pytest.approx(2 * cfg.SIM_CUSTO_STUDIO, abs=1e-9)


def test_receita_de_studio_entra_na_base_da_folha() -> None:
    """Folha = 17% do faturamento MADURO, e o maduro inclui os studios."""
    p = _p(tickets_studios=(157.0, 167.0))
    maduro = p.faturamento_maduro(DEMANDA)
    assert p.folha_fixa_mes(DEMANDA) == pytest.approx(cfg.SIM_FOLHA_PCT * maduro, abs=1e-9)
    bal, agr, studios = p.split_alunos(DEMANDA)
    assert maduro == pytest.approx(
        p.faturamento_por_fonte(bal, agr, alunos_studios=studios, com_anuidade=True), abs=1e-9
    )
    assert p.receita_studios(studios) > 0
    sem_receita_studio = maduro - p.receita_studios(studios)
    assert p.folha_fixa_mes(DEMANDA) > cfg.SIM_FOLHA_PCT * sem_receita_studio


def test_ticket_blended_e_faturamento_sao_a_mesma_regua() -> None:
    """faturamento(x, com_anuidade) == x * receita_por_aluno_total + personal."""
    for anuidade_todos in (False, True):
        p = _p(tickets_studios=(157.0, 167.0, 177.0), anuidade_apenas_balcao=not anuidade_todos)
        x = 1873.0
        assert p.faturamento(x, com_anuidade=True) == pytest.approx(
            x * p.receita_por_aluno_total + p.personal_mes, abs=1e-6
        )
        assert p.faturamento(x) == pytest.approx(x * p.ticket_blended + p.personal_mes, abs=1e-6)


# ---------------------------------------------------------------------------
# 5) Break-even com studios
# ---------------------------------------------------------------------------


def test_break_even_zera_o_ebitda_com_studios() -> None:
    p = _p(tickets_studios=(157.0, 167.0))
    be = break_even_alunos(p, DEMANDA)
    assert 0 < be < float("inf")
    k = p.fator_receita_para_ebitda
    ebitda_no_be = (
        p.faturamento(be, com_anuidade=True) * k
        - p.custo_fixo_total_mes(DEMANDA)
        - p.aluguel_mes
    )
    assert ebitda_no_be == pytest.approx(0.0, abs=1e-6)
    # E o custo fixo do break-even carrega o dos studios.
    assert p.custo_fixo_total_mes(DEMANDA) == pytest.approx(
        p.outros_fixos_mes + 2 * cfg.SIM_CUSTO_STUDIO + p.folha_fixa_mes(DEMANDA), abs=1e-9
    )


# ---------------------------------------------------------------------------
# 6) Custo de studio na serie
# ---------------------------------------------------------------------------


def test_custo_studios_na_serie_reajusta_como_outros_fixos() -> None:
    p = _p(tickets_studios=(157.0, 167.0))
    op = _operacao(gerar_serie_mensal_completa(DEMANDA, p))
    custo = 2 * cfg.SIM_CUSTO_STUDIO
    reaj = 1.0 + cfg.SIM_REAJUSTE_CUSTOS_AA
    por_mes = {linha["mes"]: linha for linha in op}

    assert por_mes[1]["custo_studios"] == pytest.approx(custo, abs=1e-9)
    assert por_mes[12]["custo_studios"] == pytest.approx(custo, abs=1e-9)
    assert por_mes[13]["custo_studios"] == pytest.approx(custo * reaj, abs=1e-9)
    assert por_mes[25]["custo_studios"] == pytest.approx(custo * reaj**2, abs=1e-9)
    for linha in op:
        f = (1.0 + cfg.SIM_REAJUSTE_CUSTOS_AA) ** ((linha["mes"] - 1) // 12)
        # `outros_fixos` da serie JA contem o custo dos studios (nao soma duas vezes).
        assert linha["outros_fixos"] == pytest.approx(
            (p.outros_fixos_mes + custo) * f, abs=1e-6
        )
        assert linha["custo_studios"] == pytest.approx(custo * f, abs=1e-6)


def test_receita_de_studio_reajusta_com_o_ticket() -> None:
    p = _p(tickets_studios=(157.0,))
    por_mes = {r["mes"]: r for r in _operacao(gerar_serie_mensal_completa(DEMANDA, p))}
    # Meses 12 e 13: mesma casa cheia, so o degrau anual do ticket separa os dois.
    assert por_mes[13]["receita_studios"] == pytest.approx(
        por_mes[12]["receita_studios"] * (1.0 + cfg.SIM_REAJUSTE_TICKET_AA), abs=1e-6
    )


# ---------------------------------------------------------------------------
# 7) Validacoes de Premissas
# ---------------------------------------------------------------------------


def test_mais_de_tres_studios_e_recusado() -> None:
    with pytest.raises(ValueError):
        _p(tickets_studios=(157.0, 167.0, 177.0, 187.0))


def test_ticket_de_studio_negativo_e_recusado() -> None:
    with pytest.raises(ValueError):
        _p(tickets_studios=(157.0, -1.0))


def test_studios_com_rampa_apenas_balcao_sao_recusados() -> None:
    with pytest.raises(ValueError):
        _p(tickets_studios=(157.0,), rampa_apenas_balcao=True)
    # Sem studio, o modo historico continua aceito.
    assert _p(rampa_apenas_balcao=True).rampa_apenas_balcao is True


def test_studios_que_consomem_toda_a_demanda_sao_recusados() -> None:
    with pytest.raises(ValueError):
        _p(tickets_studios=(157.0, 167.0), share_demanda_por_studio=0.5)


def test_lista_de_tickets_vira_tupla_de_float() -> None:
    p = _p(tickets_studios=[157, 167])  # type: ignore[arg-type]
    assert p.tickets_studios == (157.0, 167.0)
    assert isinstance(p.tickets_studios, tuple)
    assert all(isinstance(t, float) for t in p.tickets_studios)
    hash(p)  # frozen continua hashable


def test_receita_studios_com_contagem_divergente_e_recusada() -> None:
    p = _p(tickets_studios=(157.0, 167.0))
    with pytest.raises(ValueError):
        p.receita_studios((80.0,))


def test_defaults_de_studio_vem_do_config() -> None:
    p = _p()
    assert p.tickets_studios == ()
    assert p.share_demanda_por_studio == cfg.SIM_STUDIO_SHARE_DEMANDA
    assert p.custo_studio_mes == cfg.SIM_CUSTO_STUDIO


# ---------------------------------------------------------------------------
# 8) Monotonicidade
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("indice", [0, 1])
def test_subir_ticket_de_studio_nao_reduz_faturamento(indice: int) -> None:
    base = (157.0, 167.0)
    maior = tuple(t + 20.0 if i == indice else t for i, t in enumerate(base))
    r_base = simular(DEMANDA, _p(tickets_studios=base), **INVESTIMENTO)  # type: ignore[arg-type]
    r_maior = simular(DEMANDA, _p(tickets_studios=maior), **INVESTIMENTO)  # type: ignore[arg-type]
    assert r_maior.faturamento_mensal_steady > r_base.faturamento_mensal_steady
    assert r_maior.receita_studios_mensal > r_base.receita_studios_mensal
    # O split nao depende do ticket: so a receita se move.
    assert r_maior.alunos_studios_steady == r_base.alunos_studios_steady
    # A folha e' 17% do faturamento maduro, mas k (~0,80) > folha_pct: o EBITDA sobe.
    assert r_maior.ebitda_mensal > r_base.ebitda_mensal


# ---------------------------------------------------------------------------
# PDF: o aluno de studio paga anuidade, entao o texto nao pode dizer "so balcao"
# ---------------------------------------------------------------------------


def test_pdf_linha_receita_cita_studio_quando_ha_studio() -> None:
    from motor_expansao.dashboard.censo_report import _viab_linha_receita

    base = {
        "mes_referencia_steady": 12,
        "receita_anuidade": 2_903.92,
        "faturamento_mensal": 132_776.71,
        "anuidade_valor": 99.0,
        "anuidade_mes_inicio": 12,
        "anuidade_elegivel_pct": 0.476,
        "anuidade_apenas_balcao": True,
    }
    com = _viab_linha_receita({**base, "n_studios": 2})
    sem = _viab_linha_receita({**base, "n_studios": 0})
    assert com is not None and "por aluno de balcão ou de studio" in com
    assert sem is not None and "por aluno de balcão," in sem
    # Pelo payload v1 aninhado (sem a chave plana), o mesmo texto.
    from motor_expansao.dashboard.censo_report import _viab_normalizado

    aninhado = _viab_normalizado({"premissas": {"n_studios": 2, "anuidade_apenas_balcao": True}})
    assert aninhado.get("n_studios") == 2


# ---------------------------------------------------------------------------
# A tabela "Efeito medido" da DEC-068 e' reproduzivel pelo motor
# ---------------------------------------------------------------------------
# Em 05/10/2026 a coluna de payback da DEC saiu de um investimento ARBITRARIO (e nao o do
# caso de referencia) e ficou divergindo do golden em silencio. Este teste trava a linha da
# regra NOVA com o MESMO investimento do golden: se o motor mudar, ou a DEC for refeita com
# outro cenario, um dos dois fica vermelho.

_INV_GOLDEN = {
    "obra": 600_000.0,
    "parcelas_obra": 4,
    "equipamentos": 1_400_000.0,
    "prazo_equipamentos": 60,
    "juros_equipamentos_am": 0.018,
    "taxa_franquia": 160_000.0,
}

# n_studios -> (faturamento, EBITDA, payback, break-even), como na tabela da DEC-068.
_TABELA_DEC_068 = {
    0: (288_258, 113_160, 31.0, 1_152),
    1: (292_979, 110_129, 33.0, 1_201),
    2: (299_398, 108_167, 36.0, 1_244),
    3: (307_514, 107_272, 38.0, 1_281),
}


@pytest.mark.parametrize("n", sorted(_TABELA_DEC_068))
def test_tabela_da_dec_068_bate_com_o_motor(n: int) -> None:
    p = Premissas(
        ticket_cheio=147.0,
        aluguel_mes=30_000.0,
        maturacao_meses=8,
        tickets_studios=cfg.SIM_TICKETS_STUDIO_PADRAO[:n],
    )
    r = simular(2_304, p, **_INV_GOLDEN)
    fat, ebitda, payback, be = _TABELA_DEC_068[n]
    assert round(r.faturamento_mensal_steady) == fat
    assert round(r.ebitda_mensal) == ebitda
    assert r.payback_meses == payback
    assert round(r.alunos_break_even_total) == be

