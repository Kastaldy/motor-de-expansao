"""Testes da pagina de CONCLUSAO do Relatorio Pontual Censitario.

Cobre (a) a regua tri-estado por gate, EM DOIS EIXOS desde a DEC-030 (demografico e
financeiro, sem status agregado), (b) os invariantes que a regua nao pode violar
-- indecidivel nunca reprova, zero numero de faturamento no parecer --, (c) a insercao
da pagina no PDF e (d) o golden dos 5 pontos reais do Recife que calibraram os cortes
(aprovados por Vinicius em 2026-08-06). READ-ONLY sobre o M1; sem PII.

Cada teste de gate assere o status do EIXO que aquele gate alimenta -- e' isso que prova
a particao: um gate financeiro que sujasse o selo demografico (ou o contrario) quebraria
aqui, mesmo que o apontamento saisse escrito na pagina do mesmo jeito.
"""

from __future__ import annotations

import pytest

from motor_expansao.core.constants import (
    AREA_IDEAL_MAX_M2,
    AREA_IDEAL_MIN_M2,
    AREA_MIN_M2,
)
from motor_expansao.dashboard.censo_report import (
    CONCLUSAO_APROVADO,
    CONCLUSAO_EIXO_DEMOGRAFICO,
    CONCLUSAO_EIXO_FINANCEIRO,
    CONCLUSAO_REPROVADO,
    CONCLUSAO_RESSALVAS,
    _avaliar_conclusao,
    _viab_normalizado,
    gerar_pdf_relatorio_pontual_classico,
)
from motor_expansao.dashboard.constants import TEXTO_SEM_DADO

_MIN_RESULT = {
    "lat": -23.55,
    "lng": -46.63,
    "nome_municipio": "SAO PAULO",
    "uf": "SP",
    "raio_km": 1.0,
}

# Cenario base: TUDO passa -> Aprovado. Cada teste vira um gate por vez.
_RESULT_OK = {
    "pop_total_raio": 20_000,
    "renda_per_capita_media_raio": 3_000.0,
    "domicilios_total_raio": 8_000,
    "renda_domiciliar_total_raio": 9_000.0,
    "n_concorrentes": 2,
}
_RESIDUAL_OK = {
    "sam_fitness_potencial": 12_000,
    "oferta_efetiva_disponivel": 9_000,
    "oferta_consumida_mercado_estimada": 3_000,
}
_INFO_OK = {"metragem_m2": 1_800, "aluguel_pedido": 45_000.0, "pe_direito_m": 4.0}
# `_MIN_RESULT` sozinho NAO tem as metricas censitarias, e sem elas o parecer cai na
# ressalva "metas censitarias nao avaliadas" (por design). Os testes que exercitam o
# caminho APROVADO no PDF precisam do result com censo.
_RESULT_PDF = {**_MIN_RESULT, **_RESULT_OK}
_VIAB_OK = {
    "margem_ebitda_pct": 0.40,
    "payback_meses": 30.0,
    "margem_viavel_min": 0.30,
    "payback_viavel_max": 36,
    "flag_viavel": True,
    "flag_fora_envelope": False,
    "flag_zona_morta": False,
    "aluguel_teto_faixas": {"ideal": 50_000.0, "teto": 66_000.0, "excecao": 99_000.0},
}


def _parecer(*, result=None, residual=None, info=None, viab=None):
    """Avalia o cenario base com as sobrescritas pedidas."""
    return _avaliar_conclusao(
        {**_RESULT_OK, **(result or {})},
        {**_RESIDUAL_OK, **(residual or {})},
        {**_INFO_OK, **(info or {})},
        {**_VIAB_OK, **(viab or {})},
    )


def _texto(parecer) -> str:
    return " || ".join(parecer.eliminatorios + parecer.ressalvas)


def _fin(parecer):
    """Eixo FINANCEIRO, com mensagem util quando ele nao existe (modo so-estudo)."""
    assert parecer.financeiro is not None, "parecer sem eixo financeiro"
    return parecer.financeiro


# --------------------------------------------------------------------------- #
# Base                                                                        #
# --------------------------------------------------------------------------- #
def test_cenario_limpo_aprova_os_dois_eixos_sem_observacoes():
    parecer = _parecer()
    assert parecer.demografico.status == CONCLUSAO_APROVADO
    assert _fin(parecer).status == CONCLUSAO_APROVADO
    assert parecer.eliminatorios == ()
    assert parecer.ressalvas == ()


def test_parecer_nao_expoe_status_agregado():
    """DEC-030: nao existe veredito unico do ponto.

    Um agregado (pior-dos-dois) sobreviveria sem nenhum consumidor de render -- a pagina
    carimba um selo por eixo -- e seria lido como "o veredito", que e' exatamente a leitura
    que a DEC-030 aboliu. Este teste e' o que impede o campo de voltar por conveniencia.
    """
    parecer = _parecer()
    assert not hasattr(parecer, "status")


# --------------------------------------------------------------------------- #
# Modo SO-ESTUDO (BLK-CONC-ESTUDO): regua sem imovel e sem financeiro          #
# --------------------------------------------------------------------------- #
def _parecer_estudo(*, result=None, residual=None, info=None, viab=None):
    """Mesmo cenario base, avaliado SO pela base do estudo."""
    return _avaliar_conclusao(
        {**_RESULT_OK, **(result or {})},
        {**_RESIDUAL_OK, **(residual or {})},
        {**_INFO_OK, **(info or {})},
        {**_VIAB_OK, **(viab or {})},
        somente_estudo=True,
    )


def test_so_estudo_nao_tem_eixo_financeiro():
    """DEC-030: `financeiro is None` -- o eixo nao foi aprovado, ele NAO EXISTE aqui.

    E' o que faz a pagina desenhar um selo so. Um `_ConclusaoEixo` vazio sairia "Aprovado"
    e carimbaria verde um eixo que ninguem avaliou.
    """
    assert _parecer_estudo().financeiro is None
    assert _parecer().financeiro is not None


def test_so_estudo_ignora_todos_os_gates_de_imovel_e_retorno():
    """Cenario que reprova em CADA gate financeiro/fisico ao mesmo tempo -> aprovado.

    E o invariante central do modo: esses criterios nao ficam "sem dado", ficam FORA da
    regua. Se algum deles voltasse a disparar aqui, o parecer do bot passaria a reprovar
    ponto por numero que o estudo nao viu.

    A ZONA MORTA saiu deste cenario na DEC-030 -- ela deixou de ser um gate de imovel e
    passou ao eixo demografico, que este modo AVALIA. Ver
    `test_so_estudo_ainda_reprova_por_zona_morta_se_o_flag_chegar`.
    """
    parecer = _parecer_estudo(
        info={"metragem_m2": 400, "aluguel_pedido": 500_000.0},
        viab={
            "margem_ebitda_pct": 0.01,
            "payback_meses": 240.0,
            "flag_viavel": False,
            "flag_fora_envelope": True,
        },
    )
    assert parecer.demografico.status == CONCLUSAO_APROVADO
    assert parecer.eliminatorios == ()
    assert parecer.ressalvas == ()


def test_so_estudo_ainda_reprova_por_zona_morta_se_o_flag_chegar():
    """Mudanca de comportamento ACEITA na DEC-030, sem efeito no bot de producao.

    A zona morta dispara por `pop<5000` / `renda<1600` na captacao: e' juizo sobre a
    PRACA, entao pertence ao eixo demografico, que o so-estudo avalia. Na pratica o caminho
    API/bot chama a pagina com `viabilidade=None` (`api/service.py`), logo `dados_viab` sai
    vazio e o gate nunca tem insumo -- o PDF do bot de producao segue como antes. Este
    teste trava o comportamento para o dia em que esse caminho passar a mandar o payload.
    """
    parecer = _parecer_estudo(
        viab={"flag_zona_morta": True, "motivo_zona_morta": "pop<5000"}
    )
    assert parecer.demografico.status == CONCLUSAO_REPROVADO
    assert "população de captação abaixo de 5.000" in _texto(parecer)
    # Sem payload de viabilidade -- o caminho real do bot -- nao ha flag e nao ha gate.
    assert _avaliar_conclusao(
        _RESULT_OK, _RESIDUAL_OK, None, {}, somente_estudo=True
    ).demografico.status == CONCLUSAO_APROVADO


def test_so_estudo_preserva_as_metas_censitarias_e_o_mercado():
    """O que e' do ESTUDO continua valendo, com o mesmo texto do parecer completo."""
    parecer = _parecer_estudo(
        result={"pop_total_raio": 900},
        residual={"oferta_efetiva_disponivel": 100, "oferta_consumida_mercado_estimada": 11_900},
    )
    assert parecer.demografico.status == CONCLUSAO_RESSALVAS
    texto = _texto(parecer)
    assert "População total no raio" in texto
    assert "Mercado já consumido" in texto


def test_so_estudo_nao_cobra_campo_do_imovel_que_nao_avalia():
    """Sem o modo, um PDF do bot nasceria com 2 ressalvas de 'nao informado' sempre."""
    parecer = _avaliar_conclusao(_RESULT_OK, _RESIDUAL_OK, None, {}, somente_estudo=True)
    assert parecer.demografico.status == CONCLUSAO_APROVADO
    assert parecer.ressalvas == ()


def test_so_estudo_reprova_quando_as_metas_falham_em_bloco():
    """E5: o unico eliminatorio alcancavel sem imovel e sem financeiro (corte de Juan)."""
    parecer = _parecer_estudo(
        result={
            "pop_total_raio": 1,
            "renda_per_capita_media_raio": 1.0,
            "domicilios_total_raio": 1,
            "renda_domiciliar_total_raio": 1.0,
        },
        residual={
            "sam_fitness_potencial": 1,
            "oferta_efetiva_disponivel": 0,
            "oferta_consumida_mercado_estimada": 99_999,
        },
    )
    assert parecer.demografico.status == CONCLUSAO_REPROVADO
    assert len(parecer.eliminatorios) == 1
    assert "metas censitárias" in parecer.eliminatorios[0]


# --------------------------------------------------------------------------- #
# E5: metas censitarias falhando EM BLOCO (corte N=4, BLK-CONC-ESTUDO)         #
# --------------------------------------------------------------------------- #
def _result_com_n_metas_vermelhas(n: int) -> dict:
    """Cenario com EXATAMENTE `n` das 4 metas de `result` abaixo da meta (SAM/Residual ok)."""
    abaixo = {
        "pop_total_raio": 1,
        "renda_per_capita_media_raio": 1.0,
        "domicilios_total_raio": 1,
        "renda_domiciliar_total_raio": 1.0,
    }
    return {chave: valor for chave, valor in list(abaixo.items())[:n]}


@pytest.mark.parametrize("n", [0, 1, 2, 3])
def test_e5_abaixo_do_corte_apenas_rebaixa(n):
    """Ate N-1 metas vermelhas o parecer NAO reprova -- so acumula ressalvas."""
    parecer = _parecer_estudo(result=_result_com_n_metas_vermelhas(n))
    assert parecer.eliminatorios == ()
    assert parecer.demografico.status == (
        CONCLUSAO_APROVADO if n == 0 else CONCLUSAO_RESSALVAS
    )


def test_e5_no_corte_exato_reprova():
    """A borda e' INCLUSIVA (`>=`): 4 metas vermelhas ja reprovam."""
    from motor_expansao.dashboard.censo_report import _CONCLUSAO_METAS_ELIMINATORIO_MIN

    assert _CONCLUSAO_METAS_ELIMINATORIO_MIN == 4
    parecer = _parecer_estudo(result=_result_com_n_metas_vermelhas(4))
    assert parecer.demografico.status == CONCLUSAO_REPROVADO
    assert "4 das 6 metas censitárias" in parecer.eliminatorios[0]


def test_e5_conta_a_lista_crua_e_nao_a_exibida():
    """Com mercado consumido, a linha do Residual some da EXIBICAO -- o gate nao pode
    perde-la junto, senao o mesmo ponto reprovaria ou nao conforme uma decisao de texto."""
    parecer = _parecer_estudo(
        result=_result_com_n_metas_vermelhas(3),
        residual={
            "sam_fitness_potencial": 12_000,
            "oferta_efetiva_disponivel": 0,  # Residual vermelho E mercado consumido
            "oferta_consumida_mercado_estimada": 12_000,
        },
    )
    # 3 de `result` + Residual = 4 na lista crua -> reprova, embora o Residual nao apareca
    # como linha propria entre as ressalvas (ja foi dito pela linha de mercado consumido).
    assert parecer.demografico.status == CONCLUSAO_REPROVADO
    assert "4 das 6" in parecer.eliminatorios[0]
    assert not any(r.startswith("Meta não atingida em Residual") for r in parecer.ressalvas)


def test_e5_constante_de_total_bate_com_a_funcao_real():
    """`_CONCLUSAO_METAS_AVALIADAS` so compoe texto -- se divergir, o PDF mente."""
    from motor_expansao.dashboard.censo_report import (
        _CONCLUSAO_METAS_AVALIADAS,
        _conclusao_metas_vermelhas,
    )

    tudo_zerado = _conclusao_metas_vermelhas(
        {
            "pop_total_raio": 0,
            "renda_per_capita_media_raio": 0.0,
            "domicilios_total_raio": 0,
            "renda_domiciliar_total_raio": 0.0,
        },
        {"sam_fitness_potencial": 0, "oferta_efetiva_disponivel": 0},
    )
    assert len(tudo_zerado) == _CONCLUSAO_METAS_AVALIADAS


def test_e5_nao_vale_no_modo_completo():
    """Escopo fechado por Juan (2026-08-12): o E5 e' do PDF do bot, e so dele.

    O relatorio do piloto web sai EXATAMENTE como antes deste bloco -- as metas seguem
    rebaixando para "com ressalvas" e quem reprova sao os gates de imovel e retorno.
    Divergencia conhecida e aceita: o MESMO ponto pode sair reprovado no bot e com
    ressalvas no web.
    """
    comum = dict(result=_result_com_n_metas_vermelhas(4))
    assert _parecer_estudo(**comum).demografico.status == CONCLUSAO_REPROVADO
    completo = _parecer(**comum)
    assert completo.demografico.status == CONCLUSAO_RESSALVAS
    assert completo.eliminatorios == ()


def test_e5_nao_desloca_o_golden_do_recife():
    """Segunda linha de defesa: nem se o E5 vazar para o modo completo o golden vira.

    O gate ja esta preso ao so-estudo (`test_e5_nao_vale_no_modo_completo`), mas os 5
    pontos reais falham no MAXIMO 1 meta cada -- muito abaixo do corte. Se alguem um dia
    estender o E5 ao modo completo, a calibracao de Vinicius continua de pe.
    """
    from motor_expansao.dashboard.censo_report import (
        _CONCLUSAO_METAS_ELIMINATORIO_MIN,
        _conclusao_metas_vermelhas,
    )

    for nome, _esperado, result, residual, _info, _viab in _RECIFE:
        n = len(_conclusao_metas_vermelhas(result, residual))
        assert n < _CONCLUSAO_METAS_ELIMINATORIO_MIN, f"{nome} passou a disparar o E5 ({n} metas)"


def test_texto_de_aprovacao_so_estudo_nao_afirma_o_que_nao_avaliou():
    """O card de confirmacao do eixo demografico nao pode citar imovel nem retorno.

    No modo so-estudo sai um bloco so, e ele fala da praca. Afirmar envelope do imovel ou
    criterios de retorno seria dizer que avaliou o que este parecer nem enxerga.
    """
    from motor_expansao.dashboard.censo_report import _conclusao_blocos

    (eixo, itens), = _conclusao_blocos(_parecer_estudo(), somente_estudo=True)
    assert eixo == CONCLUSAO_EIXO_DEMOGRAFICO
    (texto, severidade), = itens
    assert severidade == "confirmacao"
    assert "imóvel" not in texto
    assert "retorno" not in texto
    assert "base do estudo" in texto


def test_texto_de_aprovacao_de_cada_eixo_fala_so_do_seu_lado():
    """DEC-030: o texto unico anterior citava envelope do imovel E metas censitarias E
    criterios de retorno na mesma frase -- sob dois selos ele seria falso nos dois lados."""
    from motor_expansao.dashboard.censo_report import _conclusao_blocos

    blocos = dict(_conclusao_blocos(_parecer()))
    (demografico, _sev), = blocos[CONCLUSAO_EIXO_DEMOGRAFICO]
    (financeiro, _sev2), = blocos[CONCLUSAO_EIXO_FINANCEIRO]
    assert "imóvel" not in demografico and "retorno" not in demografico
    assert "censitárias" in demografico
    assert "imóvel" in financeiro and "retorno" in financeiro
    assert "censitárias" not in financeiro


# --------------------------------------------------------------------------- #
# Retorno: E1 (falha nos DOIS) x R1 (falha em UM)                             #
# --------------------------------------------------------------------------- #
def test_e1_margem_e_payback_juntos_reprovam():
    parecer = _parecer(viab={"margem_ebitda_pct": 0.21, "payback_meses": 58.0})
    assert _fin(parecer).status == CONCLUSAO_REPROVADO
    assert len(parecer.eliminatorios) == 1
    # E o eixo da praca segue intacto: retorno ruim nao suja a leitura demografica.
    assert parecer.demografico.status == CONCLUSAO_APROVADO


def test_r1_so_payback_estourado_e_ressalva():
    """Falhar so no prazo NAO reprova: e ponto negociavel, nao morto (decisao 2026-08-06)."""
    parecer = _parecer(viab={"margem_ebitda_pct": 0.34, "payback_meses": 44.0})
    assert _fin(parecer).status == CONCLUSAO_RESSALVAS
    assert parecer.eliminatorios == ()
    assert "Prazo de retorno" in _texto(parecer)


def test_r1_so_margem_baixa_e_ressalva():
    parecer = _parecer(viab={"margem_ebitda_pct": 0.24, "payback_meses": 30.0})
    assert _fin(parecer).status == CONCLUSAO_RESSALVAS
    assert parecer.eliminatorios == ()
    assert "Margem operacional" in _texto(parecer)


@pytest.mark.parametrize("payback", [None, float("inf")])
def test_payback_ausente_ou_infinito_conta_como_nao_paga(payback):
    """`> 60 meses` na pagina anterior e FALHA conhecida, nao dado ausente."""
    parecer = _parecer(viab={"margem_ebitda_pct": 0.21, "payback_meses": payback})
    assert _fin(parecer).status == CONCLUSAO_REPROVADO


def test_margem_exatamente_na_regua_passa():
    """Comparacao e `<` -- bater a regua na mosca aprova, como em `_cor_por_meta`."""
    parecer = _parecer(viab={"margem_ebitda_pct": 0.30, "payback_meses": 36.0})
    assert _fin(parecer).status == CONCLUSAO_APROVADO


def test_payload_legado_sem_reguas_rebaixa_mas_nunca_reprova():
    """Sem os limites nao da para saber se falhou em um criterio ou nos dois."""
    viab = {k: v for k, v in _VIAB_OK.items() if k not in {"margem_viavel_min", "payback_viavel_max"}}
    viab["flag_viavel"] = False
    parecer = _avaliar_conclusao(_RESULT_OK, _RESIDUAL_OK, _INFO_OK, viab)
    assert _fin(parecer).status == CONCLUSAO_RESSALVAS
    assert parecer.eliminatorios == ()


# --------------------------------------------------------------------------- #
# Aluguel pedido x faixas de aluguel-teto: E2 x R2                            #
# --------------------------------------------------------------------------- #
def test_e2_aluguel_acima_da_excecao_reprova():
    parecer = _parecer(info={"aluguel_pedido": 99_001.0})
    assert _fin(parecer).status == CONCLUSAO_REPROVADO


def test_r2_aluguel_entre_teto_e_excecao_e_ressalva():
    parecer = _parecer(info={"aluguel_pedido": 70_000.0})
    assert _fin(parecer).status == CONCLUSAO_RESSALVAS
    assert "renegociação" in _texto(parecer)


def test_aluguel_no_teto_exato_passa():
    assert _fin(_parecer(info={"aluguel_pedido": 66_000.0})).status == CONCLUSAO_APROVADO


def test_observacoes_nao_repetem_os_valores_das_faixas():
    """O teto sai no CARD (decisao de 2026-08-06); a `excecao` e a `ideal` seguem SO como
    regua, e nenhuma das tres precisa ser repetida no texto do apontamento."""
    texto = _texto(_parecer(info={"aluguel_pedido": 99_001.0}))
    for proibido in ("66.000", "99.000", "50.000"):
        assert proibido not in texto


# --------------------------------------------------------------------------- #
# Envelope fisico do imovel: E3 x R3                                          #
# --------------------------------------------------------------------------- #
def test_e3_metragem_abaixo_do_minimo_reprova():
    parecer = _parecer(info={"metragem_m2": AREA_MIN_M2 - 1})
    assert _fin(parecer).status == CONCLUSAO_REPROVADO


@pytest.mark.parametrize("pe_direito", [2.0, 3.49, None, float("nan")])
def test_pe_direito_saiu_da_regua_e_nao_decide_mais_nada(pe_direito):
    """Retirado por Vinicius (2026-08-07). Continua digitado e impresso na pagina de
    informacoes do imovel, mas nao reprova, nao rebaixa e nao cobra preenchimento."""
    parecer = _parecer(info={"pe_direito_m": pe_direito})
    assert _fin(parecer).status == CONCLUSAO_APROVADO
    assert parecer.ressalvas == ()
    assert "direito" not in _texto(parecer)


@pytest.mark.parametrize("metragem", [AREA_IDEAL_MIN_M2 - 1, AREA_IDEAL_MAX_M2 + 1])
def test_r3_metragem_fora_da_faixa_ideal_e_so_ressalva(metragem):
    parecer = _parecer(info={"metragem_m2": metragem})
    assert _fin(parecer).status == CONCLUSAO_RESSALVAS
    assert parecer.eliminatorios == ()


@pytest.mark.parametrize("metragem", [AREA_IDEAL_MIN_M2, AREA_IDEAL_MAX_M2])
def test_bordas_da_faixa_ideal_sao_inclusivas(metragem):
    assert _fin(_parecer(info={"metragem_m2": metragem})).status == CONCLUSAO_APROVADO


# --------------------------------------------------------------------------- #
# Zona morta, extrapolacao, metas e mercado                                   #
# --------------------------------------------------------------------------- #
def test_e4_zona_morta_reprova_o_eixo_demografico_e_traduz_o_motivo():
    """DEC-030: a zona morta e' juizo sobre a PRACA, nao sobre o imovel nem sobre o retorno.

    O flag chega pelo payload de viabilidade, mas o que ele afirma -- `pop<5000` /
    `renda<1600` na captacao -- e' demografico. Com o cenario financeiro limpo, ele reprova
    o selo da praca e deixa o financeiro verde: e' exatamente o conflito que os dois selos
    existem para mostrar, e que o status unico colapsava.
    """
    parecer = _parecer(viab={"flag_zona_morta": True, "motivo_zona_morta": "pop<5000"})
    assert parecer.demografico.status == CONCLUSAO_REPROVADO
    assert _fin(parecer).status == CONCLUSAO_APROVADO
    assert "população de captação abaixo de 5.000" in _texto(parecer)


def test_motivo_de_zona_morta_desconhecido_sai_como_veio():
    parecer = _parecer(viab={"flag_zona_morta": True, "motivo_zona_morta": "criterio_novo"})
    assert "criterio_novo" in _texto(parecer)


def test_r5_fora_do_envelope_de_calibracao_e_ressalva():
    parecer = _parecer(viab={"flag_fora_envelope": True})
    assert _fin(parecer).status == CONCLUSAO_RESSALVAS
    assert "incerteza" in _texto(parecer)


def test_r4_meta_censitaria_nao_atingida_e_ressalva():
    parecer = _parecer(result={"pop_total_raio": 4_000})
    assert parecer.demografico.status == CONCLUSAO_RESSALVAS
    assert _fin(parecer).status == CONCLUSAO_APROVADO
    assert "População total no raio" in _texto(parecer)


def test_r7_mercado_consumido_e_ressalva_e_nao_eliminatorio():
    """Saturacao e leitura de disputa, nao sentenca -- decisao de Vinicius, 2026-08-06."""
    parecer = _parecer(residual={"oferta_efetiva_disponivel": 0})
    assert parecer.demografico.status == CONCLUSAO_RESSALVAS
    assert parecer.eliminatorios == ()
    assert "Mercado já consumido" in _texto(parecer)


def test_mercado_consumido_nao_repete_a_meta_de_residual():
    """As duas regras disparam pelo mesmo residual curto; dizer as duas e redundancia."""
    parecer = _parecer(residual={"oferta_efetiva_disponivel": 0})
    assert sum("Residual" in linha for linha in parecer.ressalvas) == 0
    assert sum("Mercado já consumido" in linha for linha in parecer.ressalvas) == 1


def test_residual_curto_sem_sam_relevante_ainda_marca_a_meta():
    """Sem SAM acima da meta nao ha 'mercado consumido' -- sobra a meta do Residual."""
    parecer = _parecer(
        residual={"sam_fitness_potencial": 500, "oferta_efetiva_disponivel": 100}
    )
    assert parecer.demografico.status == CONCLUSAO_RESSALVAS
    assert any("Residual Fitness" in linha for linha in parecer.ressalvas)


# --------------------------------------------------------------------------- #
# INVARIANTE: indecidivel nunca reprova                                       #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("campo", ["metragem_m2", "aluguel_pedido"])
def test_r6_campo_essencial_ausente_vira_ressalva_nunca_reprovacao(campo):
    parecer = _parecer(info={campo: None})
    assert _fin(parecer).status == CONCLUSAO_RESSALVAS
    assert parecer.eliminatorios == ()
    assert "não pôde ser avaliado" in _texto(parecer)


def test_sem_info_do_imovel_nenhum_gate_fisico_dispara():
    parecer = _avaliar_conclusao(_RESULT_OK, _RESIDUAL_OK, None, _VIAB_OK)
    assert _fin(parecer).status == CONCLUSAO_RESSALVAS
    assert parecer.eliminatorios == ()


def test_result_e_residual_vazios_nao_reprovam():
    """Sem censo/mercado os cards ficam NEUTROS (indecidiveis), nunca vermelhos."""
    parecer = _avaliar_conclusao(None, None, _INFO_OK, _VIAB_OK)
    assert parecer.eliminatorios == ()


def test_censo_ausente_nao_aprova_afirmando_o_que_nao_avaliou():
    """O reverso do invariante de indecidivel, e um defeito REAL corrigido em 2026-08-07:
    ponto sem nenhum setor no raio saia "Aprovado" AFIRMANDO no texto de confirmacao que
    atendia "as metas censitarias do raio" -- que nunca chegaram a ser avaliadas."""
    parecer = _avaliar_conclusao(None, None, _INFO_OK, _VIAB_OK)
    assert parecer.demografico.status == CONCLUSAO_RESSALVAS
    assert parecer.eliminatorios == ()  # falta de dado nao reprova
    assert any("Metas censitárias não avaliadas" in linha for linha in parecer.ressalvas)


def test_censo_parcial_nao_dispara_a_ressalva_de_censo_ausente():
    """A ressalva e' para censo INTEIRO ausente; uma metrica faltando e' outro caso."""
    parecer = _parecer(result={"renda_domiciliar_total_raio": None})
    assert all("não avaliadas" not in linha for linha in parecer.ressalvas)


def test_valores_nan_nao_disparam_gate():
    parecer = _parecer(info={"metragem_m2": float("nan")})
    assert parecer.eliminatorios == ()


# --------------------------------------------------------------------------- #
# INVARIANTE: zero numero de faturamento no parecer                           #
# --------------------------------------------------------------------------- #
def test_parecer_nao_cita_nenhum_numero_de_faturamento():
    """Pedido de Vinicius (2026-08-06). Sentinelas reconheciveis no payload; nenhuma
    pode vazar para o texto -- inclusive as que so aparecem na pagina de Viabilidade."""
    parecer = _parecer(
        viab={
            "margem_ebitda_pct": 0.21,
            "payback_meses": 58.0,
            "faturamento_mensal": 987_654.32,
            "ebitda_mensal": 123_456.78,
            "aluguel_teto": 55_555.55,
            "investimento_total": 2_860_000.0,
            "vpl": 206_140.64,
            "tir_anual": 0.306,
        }
    )
    texto = _texto(parecer)
    for sentinela in ("987.654", "123.456", "55.555", "2.860.000", "206.140", "30,6"):
        assert sentinela not in texto


def test_parecer_de_retorno_e_qualitativo_sem_percentual_nem_prazo():
    """Margem e payback justificam o status, mas o numero fica na pagina de Viabilidade."""
    texto = _texto(_parecer(viab={"margem_ebitda_pct": 0.233, "payback_meses": 44.0}))
    assert "23,3" not in texto and "44" not in texto


# --------------------------------------------------------------------------- #
# Pagina no PDF                                                               #
# --------------------------------------------------------------------------- #
_TIT_CONCLUSAO = "Conclus\xe3o".encode("latin-1")


def _pdf_so_estudo(**kwargs) -> bytes:
    """PDF pelo caminho API/bot: sem `viabilidade` e COM o flag que pede a Conclusao."""
    return gerar_pdf_relatorio_pontual_classico(
        _RESULT_PDF, None, residual=_RESIDUAL_OK, conclusao_so_estudo=True, **kwargs
    )


def test_sem_viabilidade_e_sem_flag_nao_ha_pagina_de_conclusao():
    """Default INTOCADO: quem nao pede, segue com as 7 paginas de sempre.

    E o caminho do piloto web (`web/server/app.py` chama a classica sem o flag): quando o
    operador nao preenche a Viabilidade, o relatorio dele sai exatamente como antes do
    BLK-CONC-ESTUDO. Escopo fechado por Juan em 2026-08-12.
    """
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(_MIN_RESULT, None)
    assert b"/Count 7" in pdf_bytes
    assert _TIT_CONCLUSAO not in pdf_bytes


def test_sem_viabilidade_com_flag_a_pagina_entra_em_modo_so_estudo():
    """BLK-CONC-ESTUDO: com o flag, o caminho API/bot ganha o parecer da base do ESTUDO."""
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        _MIN_RESULT, None, conclusao_so_estudo=True
    )
    assert b"/Count 8" in pdf_bytes
    assert _TIT_CONCLUSAO in pdf_bytes


def test_flag_e_inerte_quando_ha_viabilidade():
    """Com o payload a pagina ja saia -- o flag nao pode duplica-la nem mudar nada."""
    comum = dict(residual=_RESIDUAL_OK, info_imovel=_INFO_OK, viabilidade=_VIAB_OK)
    sem_flag = gerar_pdf_relatorio_pontual_classico(_RESULT_PDF, None, **comum)
    com_flag = gerar_pdf_relatorio_pontual_classico(
        _RESULT_PDF, None, conclusao_so_estudo=True, **comum
    )
    assert sem_flag == com_flag


def test_pagina_so_estudo_nao_imprime_nenhum_numero_financeiro():
    """Sem viabilidade, os cards de aluguel SOMEM -- nao viram dois "n/d" no parecer.

    Sem `info_imovel` de proposito: aquela pagina tambem imprime "Aluguel pedido", e
    inclui-la testaria a pagina errada -- a mesma armadilha que `_bytes_da_faixa_de_aluguel`
    contorna mais abaixo.
    """
    pdf_bytes = _pdf_so_estudo()
    assert _TIT_CONCLUSAO in pdf_bytes
    assert "Aluguel-teto".encode("latin-1") not in pdf_bytes
    assert "Aluguel pedido".encode("latin-1") not in pdf_bytes


def test_selo_aprovado_so_estudo_sem_mencao_a_comite():
    """No PDF do bot o selo verde e' "APROVADO" seco (pedido de Juan, 2026-08-12).

    Esse parecer nao viu imovel nem retorno, entao prometer encaminhamento a comite seria
    prometer um rito que ele nao tem base para disparar. Par deste teste:
    `test_com_viabilidade_a_pagina_entra_antes_do_credito` prova que o modo COMPLETO
    manteve "PARA COMITÊ".
    """
    pdf_bytes = _pdf_so_estudo()
    assert b"APROVADO" in pdf_bytes
    assert b"PARA COMIT" not in pdf_bytes


def test_nota_do_modo_so_estudo_declara_o_que_nao_foi_avaliado():
    """A nota do modo completo AFIRMA ter avaliado imovel e retorno -- aqui seria falso."""
    pdf_bytes = _pdf_so_estudo()
    assert "r\xe9guas do ESTUDO".encode("latin-1") in pdf_bytes
    # A nota declara o corte do E5 -- e' o unico jeito de reprovar neste modo.
    assert b"4 das 6 metas falham ao mesmo tempo" in pdf_bytes


def test_com_viabilidade_a_pagina_entra_antes_do_credito():
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        _RESULT_PDF, None, residual=_RESIDUAL_OK, info_imovel=_INFO_OK, viabilidade=_VIAB_OK
    )
    assert b"/Count 10" in pdf_bytes  # 7 base + info + numeros + conclusao
    assert _TIT_CONCLUSAO in pdf_bytes
    assert b"APROVADO" in pdf_bytes  # selo; ver `test_selo_carimba_o_status...`
    # No modo COMPLETO o selo mantem a linha de apoio: a remocao de 2026-08-12 (pedido de
    # Juan) vale so no PDF do bot -- ver `test_selo_aprovado_so_estudo_sem_mencao_a_comite`.
    assert b"PARA COMIT" in pdf_bytes
    # A pagina de credito continua sendo a ULTIMA do documento.
    assert pdf_bytes.rindex(_TIT_CONCLUSAO) < pdf_bytes.rindex("Realiza\xe7\xe3o".encode("latin-1"))


def _bytes_da_faixa_de_aluguel(dados, info) -> bytes:
    """Renderiza SO a faixa de cards de aluguel, isolada do resto do documento.

    Necessario porque a pagina de Viabilidade tambem imprime "Aluguel-teto" e as TRES
    faixas na linha de detalhe -- assertar ausencia sobre o PDF inteiro testaria a
    pagina errada.
    """
    from motor_expansao.dashboard.censo_report import _conclusao_cards_aluguel, _UltraPDF

    pdf = _UltraPDF()
    pdf.add_page()
    _conclusao_cards_aluguel(pdf, dados, info, 656.0, 250.0, 268.0, (0, 167, 157))
    return bytes(pdf.output())


def test_card_publica_o_aluguel_teto_e_o_pedido():
    """Decisao de Vinicius (2026-08-06): o teto passa a sair impresso, em card proprio."""
    saida = _bytes_da_faixa_de_aluguel(
        {"aluguel_teto": 66_000.0, "aluguel_teto_faixas": {"teto": 66_000.0, "excecao": 99_000.0}},
        {"aluguel_pedido": 45_000.0},
    )
    # "(" e ")" sao delimitadores de string no PDF e saem escapados -- casar sem eles.
    assert b"Aluguel-teto" in saida
    assert b"Aluguel pedido" in saida
    assert b"R$ 66.000,00" in saida  # o teto canonico (2a faixa)
    assert b"R$ 45.000,00" in saida  # o pedido


def test_card_de_teto_nunca_mostra_a_faixa_de_excecao():
    """A 3a faixa (30%) e regua do eliminatorio E2 e nada alem disso."""
    saida = _bytes_da_faixa_de_aluguel(
        {"aluguel_teto": 66_000.0, "aluguel_teto_faixas": {"teto": 66_000.0, "excecao": 99_000.0}},
        {"aluguel_pedido": 45_000.0},
    )
    assert b"R$ 99.000,00" not in saida


def test_faixa_de_aluguel_cai_em_nd_gracioso_sem_dado():
    """Ausencia do dado fica VISIVEL no parecer -- o card nao some."""
    saida = _bytes_da_faixa_de_aluguel({}, None)
    assert TEXTO_SEM_DADO.encode("latin-1") in saida


def test_semaforo_do_aluguel_pedido():
    from motor_expansao.dashboard.censo_report import (
        _CARD_AMBAR_RGB,
        _CARD_NEUTRO_RGB,
        _CARD_VERDE_RGB,
        _CARD_VERMELHO_RGB,
        _cor_aluguel_pedido,
    )

    assert _cor_aluguel_pedido(40_000, 66_000, 99_000) == _CARD_VERDE_RGB
    assert _cor_aluguel_pedido(66_000, 66_000, 99_000) == _CARD_VERDE_RGB  # inclusiva
    assert _cor_aluguel_pedido(70_000, 66_000, 99_000) == _CARD_AMBAR_RGB
    assert _cor_aluguel_pedido(99_001, 66_000, 99_000) == _CARD_VERMELHO_RGB
    # Indecidivel -> neutro, nunca reprovacao visual (mesma regra de `_cor_por_meta`).
    assert _cor_aluguel_pedido(None, 66_000, 99_000) == _CARD_NEUTRO_RGB
    assert _cor_aluguel_pedido(40_000, None, None) == _CARD_NEUTRO_RGB
    assert _cor_aluguel_pedido(float("nan"), 66_000, 99_000) == _CARD_NEUTRO_RGB


def _pdf_completo(**overrides) -> bytes:
    """PDF pelo caminho do piloto web: com viabilidade, logo com os DOIS selos."""
    viab = {**_VIAB_OK, **overrides.pop("viab", {})}
    return gerar_pdf_relatorio_pontual_classico(
        {**_RESULT_PDF, **overrides.pop("result", {})},
        None,
        residual={**_RESIDUAL_OK, **overrides.pop("residual", {})},
        info_imovel={**_INFO_OK, **overrides.pop("info", {})},
        viabilidade=viab,
    )


@pytest.mark.parametrize(
    "viab_extra,esperado",
    [
        ({}, b"APROVADO"),
        ({"payback_meses": 44.0}, b"COM RESSALVAS"),
        ({"margem_ebitda_pct": 0.21, "payback_meses": None}, b"REPROVADO"),
    ],
    ids=["aprovado", "com_ressalvas", "reprovado"],
)
def test_selo_carimba_o_status_nos_bytes_do_pdf(viab_extra, esperado):
    """CAIXA ALTA de proposito: o selo e o unico lugar da pagina com o status assim.

    A nota metodologica cita "Aprovado com ressalvas" em caixa MISTA, entao casar por
    "Aprovado" daria falso positivo em qualquer um dos tres estados. Os tres cenarios aqui
    variam o eixo FINANCEIRO -- a praca segue limpa nos tres, entao "APROVADO" estaria nos
    bytes de qualquer jeito pelo selo demografico. Quem prova a independencia dos dois e'
    `test_os_dois_selos_carimbam_eixos_independentes`, com as linhas de apoio.
    """
    assert esperado in _pdf_completo(viab=viab_extra)


# Linhas de apoio: unicas por (eixo, estado), ao contrario do rotulo principal, que se
# repete nos dois selos. Sao elas que permitem afirmar QUAL selo carimbou o que.
_APOIO_PRACA_OK = "PRA\xc7A SUSTENTA".encode("latin-1")
_APOIO_PRACA_RISCO = "PRA\xc7A COM RISCO".encode("latin-1")
_APOIO_COMITE = "PARA COMIT\xca".encode("latin-1")
_APOIO_FORA_DA_REGUA = "FORA DA R\xc9GUA".encode("latin-1")


def test_os_dois_selos_carimbam_eixos_independentes():
    """DEC-030: praca verde e financeiro vermelho na MESMA pagina.

    O ponto tem metas censitarias folgadas e mercado sobrando, mas nao paga o investimento
    e a margem nao fecha. Antes isso saia como um "REPROVADO" unico e a leitura da praca
    desaparecia; agora os dois carimbos convivem e o conflito e' o proprio resultado.
    """
    pdf_bytes = _pdf_completo(viab={"margem_ebitda_pct": 0.21, "payback_meses": None})
    assert _APOIO_PRACA_OK in pdf_bytes
    assert _APOIO_FORA_DA_REGUA in pdf_bytes
    assert _APOIO_COMITE not in pdf_bytes  # o financeiro NAO foi aprovado


def test_selo_demografico_reage_a_praca_sem_mexer_no_financeiro():
    """O simetrico: mercado consumido rebaixa a praca e deixa o financeiro intacto."""
    pdf_bytes = _pdf_completo(residual={"oferta_efetiva_disponivel": 0})
    assert _APOIO_PRACA_RISCO in pdf_bytes
    assert _APOIO_COMITE in pdf_bytes  # cenario financeiro segue aprovado
    assert _APOIO_PRACA_OK not in pdf_bytes


def test_legendas_identificam_os_dois_selos_no_pdf():
    """Sem legenda, os dois carimbos sao indistinguiveis em forma."""
    pdf_bytes = _pdf_completo()
    assert "DEMOGR\xc1FICO".encode("latin-1") in pdf_bytes
    assert b"FINANCEIRO" in pdf_bytes


# "(" e ")" sao delimitadores de string no PDF: dentro do literal eles saem ESCAPADOS com
# barra invertida. Casar pelo texto cru daria falso NEGATIVO nos asserts de presenca e --
# pior -- falso POSITIVO nos de ausencia, que passariam sem provar nada.
_TITULO_PRACA = "Pra\xe7a \\(demogr\xe1fico\\)".encode("latin-1")
_TITULO_IMOVEL = "Im\xf3vel e retorno \\(financeiro\\)".encode("latin-1")


def test_titulos_de_bloco_amarram_as_observacoes_aos_selos():
    """As observacoes saem agrupadas por eixo, na mesma ordem dos selos."""
    pdf_bytes = _pdf_completo(
        info={"metragem_m2": 1_349}, residual={"oferta_efetiva_disponivel": 0}
    )
    assert _TITULO_PRACA in pdf_bytes
    assert _TITULO_IMOVEL in pdf_bytes
    assert pdf_bytes.index(_TITULO_PRACA) < pdf_bytes.index(_TITULO_IMOVEL)


def test_ponto_ruim_em_tudo_ainda_mostra_os_dois_blocos():
    """O caso que expos o defeito: 10 apontamentos, coluna para ~6.

    Nenhum selo pode ficar carimbado sem uma linha que o explique -- e com os dois eixos
    reprovados, os DOIS eliminatorios tem de estar na pagina, nao so o do primeiro bloco.
    """
    pdf_bytes = _pdf_completo(
        result={
            "pop_total_raio": 4_000, "renda_per_capita_media_raio": 900.0,
            "domicilios_total_raio": 1_400, "renda_domiciliar_total_raio": 2_100.0,
        },
        residual={"sam_fitness_potencial": 18_148, "oferta_efetiva_disponivel": 0},
        info={"metragem_m2": 900, "aluguel_pedido": None},
        viab={
            "margem_ebitda_pct": 0.10, "payback_meses": None, "flag_viavel": False,
            "flag_fora_envelope": True, "flag_zona_morta": True,
            "motivo_zona_morta": "pop<5000; renda<1600",
        },
    )
    assert _TITULO_PRACA in pdf_bytes
    assert _TITULO_IMOVEL in pdf_bytes
    assert "zona morta".encode("latin-1") in pdf_bytes  # eliminatorio do eixo demografico
    assert "abaixo do m\xednimo".encode("latin-1") in pdf_bytes  # eliminatorio do financeiro
    assert "n\xe3o exibido".encode("latin-1") in pdf_bytes  # e a truncagem segue declarada


def test_so_estudo_nao_desenha_o_selo_financeiro():
    """O eixo nao existe naquele parecer -- nao ha o que carimbar."""
    pdf_bytes = _pdf_so_estudo()
    assert "DEMOGR\xc1FICO".encode("latin-1") in pdf_bytes
    assert b"FINANCEIRO" not in pdf_bytes
    assert _TITULO_IMOVEL not in pdf_bytes
    # E o bloco da praca continua rotulado, de par com o unico selo.
    assert _TITULO_PRACA in pdf_bytes


# --------------------------------------------------------------------------- #
# Layout: cards de observacao, corte e centralizacao vertical                  #
# --------------------------------------------------------------------------- #
def test_quantos_cabem_conta_ate_estourar_o_limite():
    from motor_expansao.dashboard.censo_report import (
        _CONCLUSAO_OBS_GAP,
        _conclusao_quantos_cabem,
    )

    # gap entra ENTRE os cards, entao o 3o so cabe se sobrar altura para ele inteiro.
    passo = 30.0 + _CONCLUSAO_OBS_GAP
    assert _conclusao_quantos_cabem((30.0, 30.0, 30.0), 0.0, 2 * passo) == 2
    assert _conclusao_quantos_cabem((30.0, 30.0, 30.0), 0.0, 500.0) == 3
    assert _conclusao_quantos_cabem((30.0,), 0.0, 20.0) == 0
    assert _conclusao_quantos_cabem((), 0.0, 500.0) == 0


@pytest.mark.parametrize("altura", [20.0, 27.0, 33.0, 40.0, 46.0, 53.0, 61.0])
def test_plano_reserva_espaco_para_o_aviso_de_truncamento(altura):
    """REGRESSAO: o loop enchia a coluna ate o limite e a linha "(+N nao exibido(s))"
    saia POR CIMA do ultimo card -- dois textos sobrepostos e ilegiveis.

    Varias alturas de proposito: com UMA so o teste passava mesmo com a correcao
    removida, porque para muitas alturas a reserva e' no-op (sobra folga de qualquer
    jeito). O caso discriminante e' garantido pelo teste seguinte.
    """
    from motor_expansao.dashboard.censo_report import (
        _CONCLUSAO_AREA_BASE,
        _CONCLUSAO_OBS_AVISO_H,
        _conclusao_plano_observacoes,
    )

    alturas = tuple([altura] * 40)  # muito mais do que a coluna comporta
    cabem, y_aviso = _conclusao_plano_observacoes(alturas, 100.0)
    assert 0 < cabem < len(alturas)
    # O aviso tem de caber INTEIRO abaixo do ultimo card desenhado.
    assert y_aviso + _CONCLUSAO_OBS_AVISO_H <= _CONCLUSAO_AREA_BASE


def test_reserva_do_aviso_nao_e_no_op():
    """Prova que a segunda passada de `_conclusao_plano_observacoes` faz efeito: existe
    altura em que ela tira um card do que caberia sem a reserva.

    Sem este teste, apagar o retry deixava a suite inteira VERDE (medido: 58 passed) --
    a fixture antiga usava 40,0, altura em que a reserva nao muda nada.
    """
    from motor_expansao.dashboard.censo_report import (
        _CONCLUSAO_AREA_BASE,
        _conclusao_plano_observacoes,
        _conclusao_quantos_cabem,
    )

    discriminantes = [
        h
        for h in range(15, 80)
        if _conclusao_plano_observacoes(tuple([float(h)] * 40), 100.0)[0]
        < _conclusao_quantos_cabem(tuple([float(h)] * 40), 100.0, _CONCLUSAO_AREA_BASE)
    ]
    assert discriminantes, "a reserva do aviso virou no-op para toda altura testada"


def test_plano_sem_truncamento_nao_desperdica_espaco():
    from motor_expansao.dashboard.censo_report import _conclusao_plano_observacoes

    alturas = (30.0, 30.0)
    cabem, _y = _conclusao_plano_observacoes(alturas, 100.0)
    assert cabem == 2  # cabem folgados: a reserva do aviso nem entra na conta


def _elemento(altura: float, titulo: str = "", offset: float = 0.0):
    from motor_expansao.dashboard.censo_report import (
        _CONCLUSAO_OBS_TITULO_GAP,
        _CONCLUSAO_OBS_TITULO_H,
        _ConclusaoElemento,
    )

    # `altura` e' a do CARD; a do titulo entra por cima, como no render.
    del _CONCLUSAO_OBS_TITULO_H, _CONCLUSAO_OBS_TITULO_GAP
    return _ConclusaoElemento(
        texto="x", severidade="ressalva", titulo=titulo, titulo_offset=offset, altura_card=altura
    )


def test_truncagem_reparte_o_espaco_entre_os_blocos():
    """REGRESSAO da revisao visual da DEC-030: preenchendo na ordem, o 1o bloco tomava a
    coluna inteira e o 2o nao entrava -- o selo daquele eixo ficava carimbado sem UMA linha
    que o explicasse. Por rodadas, os dois blocos sempre aparecem enquanto houver espaco."""
    from motor_expansao.dashboard.censo_report import _conclusao_plano_elementos

    elementos = tuple(
        [_elemento(60.0, titulo="Praça (demográfico)")] + [_elemento(60.0) for _ in range(5)]
        + [_elemento(60.0, titulo="Imóvel e retorno (financeiro)", offset=14.0)]
        + [_elemento(60.0) for _ in range(3)]
    )
    desenhar, _y = _conclusao_plano_elementos(elementos, 100.0)
    assert len(desenhar) < len(elementos), "o cenario precisa truncar, senao nao testa nada"
    assert 0 in desenhar, "o titulo do 1o bloco tem de entrar"
    assert 6 in desenhar, "o titulo do 2o bloco tem de entrar"
    # E o que cada bloco mostra sao os PRIMEIROS itens dele (eliminatorios na frente).
    assert set(desenhar) & set(range(6)) == set(range(len(set(desenhar) & set(range(6)))))


def test_plano_sem_truncamento_desenha_tudo_na_ordem():
    from motor_expansao.dashboard.censo_report import _conclusao_plano_elementos

    elementos = (_elemento(30.0, titulo="A"), _elemento(30.0), _elemento(30.0, titulo="B"))
    desenhar, _y = _conclusao_plano_elementos(elementos, 100.0)
    assert desenhar == (0, 1, 2)


def test_aviso_de_truncagem_conta_o_que_ficou_de_fora_nos_dois_blocos():
    from motor_expansao.dashboard.censo_report import (
        _CONCLUSAO_AREA_BASE,
        _CONCLUSAO_OBS_AVISO_H,
        _conclusao_plano_elementos,
    )

    elementos = tuple(
        [_elemento(70.0, titulo="A")] + [_elemento(70.0) for _ in range(4)]
        + [_elemento(70.0, titulo="B", offset=14.0)] + [_elemento(70.0) for _ in range(4)]
    )
    desenhar, y_aviso = _conclusao_plano_elementos(elementos, 100.0)
    assert 0 < len(desenhar) < len(elementos)
    # O aviso cabe INTEIRO abaixo do ultimo card, como no planejador de bloco unico.
    assert y_aviso + _CONCLUSAO_OBS_AVISO_H <= _CONCLUSAO_AREA_BASE


def test_severidade_colore_o_card_da_observacao():
    """Eliminatorio tingido (salta), ressalva no cinza dos demais cards com a cor so na
    barra -- com 8+ apontamentos, tingir todos deixaria a pagina inteira vermelha."""
    from motor_expansao.dashboard.censo_report import (
        _CARD_NEUTRO_RGB,
        _CARD_VERDE_RGB,
        _CARD_VERMELHO_RGB,
        _CONCLUSAO_OBS_CORES,
    )

    assert _CONCLUSAO_OBS_CORES["eliminatorio"][0] == _CARD_VERMELHO_RGB
    assert _CONCLUSAO_OBS_CORES["ressalva"][0] == _CARD_NEUTRO_RGB
    assert _CONCLUSAO_OBS_CORES["confirmacao"][0] == _CARD_VERDE_RGB
    # Toda severidade tem acento SOLIDO proprio, distinto do fundo.
    for fundo, acento in _CONCLUSAO_OBS_CORES.values():
        assert fundo != acento


def test_itens_ordenam_eliminatorios_antes_das_ressalvas():
    """A ordem vale DENTRO de cada bloco (DEC-030), que e' onde ela e' lida."""
    from motor_expansao.dashboard.censo_report import _conclusao_blocos

    parecer = _parecer(
        info={"metragem_m2": 900},  # eliminatorio, eixo financeiro
        viab={"flag_fora_envelope": True},  # ressalva, eixo financeiro
    )
    for _eixo, itens in _conclusao_blocos(parecer):
        severidades = [sev for _txt, sev in itens]
        assert severidades == sorted(severidades, key=lambda s: s != "eliminatorio")


def test_blocos_seguem_a_ordem_dos_selos():
    """A coluna esquerda e' lida de par com a direita: praca em cima, financeiro embaixo."""
    from motor_expansao.dashboard.censo_report import _conclusao_blocos

    assert [eixo for eixo, _itens in _conclusao_blocos(_parecer())] == [
        CONCLUSAO_EIXO_DEMOGRAFICO,
        CONCLUSAO_EIXO_FINANCEIRO,
    ]


def test_parecer_limpo_vira_um_card_de_confirmacao_por_eixo():
    from motor_expansao.dashboard.censo_report import _conclusao_blocos

    blocos = _conclusao_blocos(_parecer())
    assert len(blocos) == 2
    for _eixo, itens in blocos:
        assert len(itens) == 1
        assert itens[0][1] == "confirmacao"


def test_os_dois_selos_cabem_na_area_util():
    """GUARDA DE ESTOURO SILENCIOSO. `auto_page_break` esta OFF: dois selos altos demais
    nao vazam para a pagina seguinte -- somem por baixo do rodape, sem nenhum aviso.

    Com um selo so a folga era de 102 pt e nada podia dar errado; com dois, `2 x SELO_H +
    GAP` tem de caber nos 400 pt da area, e e' este assert que impede um ajuste de altura
    de estourar em silencio.
    """
    from motor_expansao.dashboard.censo_report import (
        _CONCLUSAO_AREA_BASE,
        _CONCLUSAO_AREA_TOPO,
        _CONCLUSAO_SELO_GAP,
        _CONCLUSAO_SELO_H,
    )

    bloco = 2 * _CONCLUSAO_SELO_H + _CONCLUSAO_SELO_GAP
    folga = (_CONCLUSAO_AREA_BASE - _CONCLUSAO_AREA_TOPO - bloco) / 2
    assert folga > 0  # os selos sobram espaco em cima e embaixo
    # E a area de conteudo termina acima da nota metodologica.
    from motor_expansao.dashboard.censo_report import _CONCLUSAO_NOTA_Y

    assert _CONCLUSAO_AREA_BASE <= _CONCLUSAO_NOTA_Y


def test_geometria_interna_do_selo_reproduz_o_desenho_de_referencia():
    """As fracoes substituiram absolutos (48 / 22 / 14 / 9,5) calibrados para altura 196.

    Na altura de referencia elas tem de devolver EXATAMENTE aqueles numeros -- senao a
    parametrizacao teria mudado a estetica de 2026-08-07 de carona, sem ninguem pedir.
    """
    from motor_expansao.dashboard.censo_report import (
        _CONCLUSAO_SELO_H_REF,
        _CONCLUSAO_SELO_PRINCIPAL_H,
        _CONCLUSAO_SELO_SECUNDARIO_H,
        _CONCLUSAO_SELO_SIMBOLO_TAM,
    )

    assert _CONCLUSAO_SELO_SIMBOLO_TAM * _CONCLUSAO_SELO_H_REF == pytest.approx(48.0, abs=0.1)
    assert _CONCLUSAO_SELO_PRINCIPAL_H * _CONCLUSAO_SELO_H_REF == pytest.approx(22.0, abs=0.1)
    assert _CONCLUSAO_SELO_SECUNDARIO_H * _CONCLUSAO_SELO_H_REF == pytest.approx(14.0, abs=0.1)


# --------------------------------------------------------------------------- #
# Correcoes da revisao adversarial de 2026-08-07                              #
# --------------------------------------------------------------------------- #
def test_texto_da_observacao_chega_aos_bytes_do_pdf():
    """Sem este assert, trocar o desenho do card por `pass` deixava a suite VERDE
    (medido: 76 passed) -- nenhum teste conferia o texto do apontamento no PDF."""
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        _RESULT_PDF,
        None,
        residual=_RESIDUAL_OK,
        info_imovel={**_INFO_OK, "metragem_m2": 1_349},
        viabilidade=_VIAB_OK,
    )
    assert "fora da faixa ideal".encode("latin-1") in pdf_bytes


@pytest.mark.parametrize(
    "bruto,esperado",
    [
        ("pop<5000", "população de captação abaixo de 5.000"),
        ("renda<1600", "renda per capita de captação abaixo de R$ 1.600"),
        # O motor junta com "; " quando pop E renda estao abaixo do piso -- o caso MAIS
        # grave era o unico que nunca traduzia e saia com o token cru no PDF.
        ("pop<5000; renda<1600",
         "população de captação abaixo de 5.000; renda per capita de captação abaixo de R$ 1.600"),
        ("token_novo", "token_novo"),  # desconhecido sai como veio
    ],
)
def test_motivo_de_zona_morta_traduz_token_a_token(bruto, esperado):
    from motor_expansao.dashboard.censo_report import _conclusao_motivo_zona_morta

    assert _conclusao_motivo_zona_morta(bruto) == esperado


def test_zona_morta_composta_nao_vaza_token_cru_para_o_parecer():
    parecer = _parecer(
        viab={"flag_zona_morta": True, "motivo_zona_morta": "pop<5000; renda<1600"}
    )
    texto = _texto(parecer)
    assert "pop<5000" not in texto and "renda<1600" not in texto
    assert "população de captação" in texto and "renda per capita de captação" in texto


@pytest.mark.parametrize("flag", ["flag_zona_morta", "flag_fora_envelope"])
def test_flag_nan_nao_dispara_gate(flag):
    """`NaN` e TRUTHY em Python: com truthiness crua um flag corrompido REPROVAVA o ponto
    por zona morta, contra o invariante de que indecidivel nunca reprova.

    Os dois flags moram em eixos diferentes desde a DEC-030 (`flag_zona_morta` no
    demografico, `flag_fora_envelope` no financeiro), entao os DOIS selos precisam sair
    limpos -- checar so um deixaria metade do invariante sem rede.
    """
    parecer = _parecer(viab={flag: float("nan")})
    assert parecer.demografico.status == CONCLUSAO_APROVADO
    assert _fin(parecer).status == CONCLUSAO_APROVADO
    assert parecer.eliminatorios == ()


def test_gate_e_card_de_aluguel_leem_o_mesmo_par_de_faixas():
    """Payload com `aluguel_teto` ESCALAR e sem `aluguel_teto_faixas` (forma legada, ainda
    aceita por `_viab_normalizado`): o gate ficava MUDO enquanto o card ao lado pintava
    vermelho na mesma pagina -- a divergencia que o FIN-VIAB-01 combateu."""
    from motor_expansao.dashboard.censo_report import (
        _CARD_NEUTRO_RGB,
        _conclusao_faixas_aluguel,
        _cor_aluguel_pedido,
    )

    dados = {"aluguel_teto": 60_000.0}  # sem a chave de faixas
    teto, excecao = _conclusao_faixas_aluguel(dados)
    assert teto == 60_000.0  # o gate ENXERGA o teto pelo fallback
    assert excecao is None

    # E o parecer aponta o aluguel alto em vez de aprovar em silencio.
    parecer = _avaliar_conclusao(
        _RESULT_OK,
        _RESIDUAL_OK,
        {**_INFO_OK, "aluguel_pedido": 95_000.0},
        {**_VIAB_OK, "aluguel_teto": 60_000.0, "aluguel_teto_faixas": None},
    )
    assert _fin(parecer).status == CONCLUSAO_RESSALVAS
    assert "acima do teto" in _texto(parecer)
    # O card usa o MESMO teto, entao nao contradiz o gate.
    assert _cor_aluguel_pedido(95_000.0, teto, excecao) != _CARD_NEUTRO_RGB


# --------------------------------------------------------------------------- #
# Coerencia com o SELO da tela de Viabilidade                                  #
# --------------------------------------------------------------------------- #
# O selo da tela (`ViabilityCharts.Veredito`) e' BINARIO e sai de `dre.flag_viavel`
# (margem >= min E payback <= max). A Conclusao e' TRI-estado e olha mais coisas
# (imovel, censo, mercado), entao os dois NAO sao o mesmo juizo -- e nem deveriam ser.
# O que precisa valer e' COERENCIA, e ela tem duas metades:
#   A) `flag_viavel=False` NUNCA pode virar "Aprovado" -- se o motor diz que o cenario
#      nao fecha, o parecer nao pode aprovar. Este e' o invariante forte.
#   B) `flag_viavel=True` PODE virar "Reprovado" por gate NAO-financeiro (aluguel acima
#      do maximo, metragem abaixo do minimo, zona morta) -- mas nunca em silencio: tem
#      de haver eliminatorio escrito explicando.
#
# Desde a DEC-030 as duas metades apontam para o selo FINANCEIRO, e nao mais para um
# status unico. Nao e' afrouxamento: e' o unico enderecamento que faz sentido, porque o
# selo da tela julga o CENARIO, e o eixo demografico julga a praca -- exigir que um
# problema de praca aparecesse no selo financeiro seria pedir de volta o colapso que a
# DEC-030 desfez. Vale notar que (A) sobrevive por CONSTRUCAO no eixo financeiro: quando
# margem e payback passam mas `flag_viavel` e' False, o ramo final de `_conclusao_retorno`
# ("Cenário fora da régua") ainda rebaixa o eixo -- nenhum caminho o deixa verde.
def _matriz_cenarios():
    """Produto de cenarios com `flag_viavel` DERIVADO da mesma regra do simulador."""
    import itertools

    for margem, payback, aluguel, metragem, censo, residual, env, zona in itertools.product(
        (0.10, 0.2999, 0.30, 0.45),
        (20.0, 36.0, 36.1, None),
        (30_000.0, 66_000.0, 70_000.0, 99_001.0),
        (1_000.0, 1_200.0, 1_800.0, 2_001.0),
        ({}, _RESULT_OK),
        (_RESIDUAL_OK, {"sam_fitness_potencial": 18_000, "oferta_efetiva_disponivel": 0}),
        (False, True),
        (False, True),
    ):
        paga = payback is not None and payback <= 36
        viavel = margem >= 0.30 and paga
        dados = {
            "margem_ebitda_pct": margem, "payback_meses": payback,
            "margem_viavel_min": 0.30, "payback_viavel_max": 36,
            "flag_viavel": viavel, "flag_fora_envelope": env, "flag_zona_morta": zona,
            "motivo_zona_morta": "pop<5000" if zona else None,
            "aluguel_teto_faixas": {"teto": 66_000.0, "excecao": 99_000.0},
        }
        info = {"metragem_m2": metragem, "aluguel_pedido": aluguel}
        yield viavel, _avaliar_conclusao(censo, residual, info, dados), dados, info


def test_selo_reprovado_na_tela_nunca_vira_aprovado_na_conclusao():
    """INVARIANTE FORTE: se o motor diz que o cenario nao fecha, o eixo financeiro nao aprova."""
    for viavel, parecer, dados, info in _matriz_cenarios():
        if not viavel:
            assert parecer.financeiro.status != CONCLUSAO_APROVADO, (
                f"cenario inviavel aprovado: {dados} {info}"
            )


def test_conclusao_mais_dura_que_a_tela_sempre_diz_o_porque():
    """A Conclusao pode reprovar o que a tela aprovou (ela olha o IMOVEL, alem do cenario)
    -- mas nunca em silencio."""
    divergencias = 0
    for viavel, parecer, _dados, _info in _matriz_cenarios():
        if viavel and parecer.financeiro.status == CONCLUSAO_REPROVADO:
            divergencias += 1
            assert parecer.financeiro.eliminatorios, "reprovou sem eliminatorio que explique"
    assert divergencias > 0  # a matriz precisa exercitar o caso, senao o teste e' vazio


def test_eixo_demografico_nao_herda_o_veredito_do_cenario():
    """A outra metade da DEC-030: a praca nao pode ser condenada pelo financeiro.

    Na matriz existem cenarios com `flag_viavel=False` e praca impecavel (`_RESULT_OK` +
    residual folgado, sem zona morta). Antes, o status unico os carimbava REPROVADO e a
    leitura da praca sumia junto. Se alguem reunificar os eixos, este teste cai.
    """
    aprovados_apesar_de_inviavel = sum(
        1
        for viavel, parecer, _dados, _info in _matriz_cenarios()
        if not viavel and parecer.demografico.status == CONCLUSAO_APROVADO
    )
    assert aprovados_apesar_de_inviavel > 0


def test_textos_de_exibicao_do_selo_nao_usam_caractere_fora_de_latin1():
    """BURACO DE COBERTURA fechado na DEC-030, que multiplicou esses textos por 2.

    `test_relatorio_acentuacao_regressao` gera os PDFs SEM viabilidade e sem
    `conclusao_so_estudo`, entao a pagina de Conclusao nunca e' renderizada la -- e o teste
    ao lado so percorre eliminatorios e ressalvas. Ou seja: ate aqui NINGUEM auditava os
    rotulos do selo. Um travessao, bullet ou seta em qualquer um deles viraria "?" no PDF,
    em silencio, no elemento mais visivel da pagina.
    """
    from motor_expansao.dashboard.censo_report import (
        _CONCLUSAO_BLOCO_TITULOS,
        _CONCLUSAO_SELO_LEGENDAS,
        _CONCLUSAO_SELO_TEXTOS,
    )

    textos = [*_CONCLUSAO_SELO_LEGENDAS.values(), *_CONCLUSAO_BLOCO_TITULOS.values()]
    for por_status in _CONCLUSAO_SELO_TEXTOS.values():
        for principal, secundario in por_status.values():
            textos += [principal, secundario]
    for texto in textos:
        texto.encode("latin-1")  # levanta UnicodeEncodeError se houver caractere fora


def test_todo_eixo_tem_texto_para_todo_status():
    """Um status sem entrada explodiria com KeyError DENTRO do render do PDF -- tarde
    demais, e so no cenario que produzisse aquele status."""
    from motor_expansao.dashboard.censo_report import (
        _CONCLUSAO_BLOCO_TITULOS,
        _CONCLUSAO_SELO_LEGENDAS,
        _CONCLUSAO_SELO_TEXTOS,
    )

    eixos = {CONCLUSAO_EIXO_DEMOGRAFICO, CONCLUSAO_EIXO_FINANCEIRO}
    assert set(_CONCLUSAO_SELO_TEXTOS) == eixos
    assert set(_CONCLUSAO_SELO_LEGENDAS) == eixos
    assert set(_CONCLUSAO_BLOCO_TITULOS) == eixos
    for por_status in _CONCLUSAO_SELO_TEXTOS.values():
        assert set(por_status) == {CONCLUSAO_APROVADO, CONCLUSAO_RESSALVAS, CONCLUSAO_REPROVADO}
        # A linha de apoio e' o que distingue os dois selos: nenhuma pode ser vazia.
        assert all(principal and secundario for principal, secundario in por_status.values())


def test_pagina_de_conclusao_nao_usa_caractere_fora_de_latin1():
    """Fora de latin-1 (travessao, bullet, seta) vira '?' silencioso no core font."""
    parecer = _parecer(
        info={"metragem_m2": 900, "aluguel_pedido": 99_999.0},
        residual={"oferta_efetiva_disponivel": 0},
        result={"pop_total_raio": 10},
        viab={"flag_zona_morta": True, "motivo_zona_morta": "pop<5000", "flag_fora_envelope": True},
    )
    for linha in parecer.eliminatorios + parecer.ressalvas:
        linha.encode("latin-1")  # levanta UnicodeEncodeError se houver caractere fora


# --------------------------------------------------------------------------- #
# Golden: os 5 pontos reais do Recife que calibraram a regua                   #
# --------------------------------------------------------------------------- #
# Numeros lidos dos proprios PDFs entregues (paginas 4, 9 e 10). Este golden trava a
# CALIBRACAO aprovada: mudar um corte sem reavaliar estes 5 pontos quebra aqui.
#
# `esperado` virou o PAR (demografico, financeiro) na DEC-030. A coluna financeira
# reproduz, ponto a ponto, os 5 status que Vinicius aprovou em 2026-08-06 -- o golden
# original era, na pratica, um golden do eixo financeiro: os 5 pontos reprovam e ressalvam
# por metragem, aluguel e retorno. A coluna demografica e' o que a separacao revela: 4 dos
# 5 tem a praca limpa, e so Rosa e Silva (residual zero contra SAM de 18.148) sai com
# ressalva. Um ponto que mudasse de coluna aqui teria mudado de EIXO, nao de nota.
_RECIFE = [
    (
        "Av. Pinheiros, 1212",
        (CONCLUSAO_APROVADO, CONCLUSAO_APROVADO),
        dict(pop_total_raio=24_001, renda_per_capita_media_raio=5_366.85,
             domicilios_total_raio=8_770, renda_domiciliar_total_raio=10_085.75),
        dict(sam_fitness_potencial=12_239, oferta_efetiva_disponivel=10_684),
        dict(metragem_m2=1_932, aluguel_pedido=45_000, pe_direito_m=4.00),
        dict(margem_ebitda_pct=0.399, payback_meses=34,
             aluguel_teto_faixas={"ideal": 54_137.41, "teto": 72_183.22, "excecao": 108_274.83}),
    ),
    (
        "Av. Gen. Mac Arthur, 1653",
        (CONCLUSAO_APROVADO, CONCLUSAO_RESSALVAS),
        dict(pop_total_raio=23_805, renda_per_capita_media_raio=1_680.05,
             domicilios_total_raio=8_951, renda_domiciliar_total_raio=8_270.96),
        dict(sam_fitness_potencial=12_078, oferta_efetiva_disponivel=4_253),
        dict(metragem_m2=1_912, aluguel_pedido=75_000, pe_direito_m=7.00),
        dict(margem_ebitda_pct=0.312, payback_meses=44,
             aluguel_teto_faixas={"ideal": 53_584.18, "teto": 71_445.57, "excecao": 107_168.35}),
    ),
    (
        "R. Sao Miguel, 600",
        (CONCLUSAO_APROVADO, CONCLUSAO_RESSALVAS),
        dict(pop_total_raio=29_037, renda_per_capita_media_raio=8_554.26,
             domicilios_total_raio=10_597, renda_domiciliar_total_raio=17_068.47),
        dict(sam_fitness_potencial=7_765, oferta_efetiva_disponivel=6_804),
        dict(metragem_m2=1_349, aluguel_pedido=40_000, pe_direito_m=9.00),
        dict(margem_ebitda_pct=0.320, payback_meses=57,
             aluguel_teto_faixas={"ideal": 38_001.32, "teto": 50_668.43, "excecao": 76_002.64}),
    ),
    (
        "Estr. do Arraial, 3851",
        (CONCLUSAO_APROVADO, CONCLUSAO_REPROVADO),
        dict(pop_total_raio=48_539, renda_per_capita_media_raio=4_022.64,
             domicilios_total_raio=18_177, renda_domiciliar_total_raio=19_620.19),
        dict(sam_fitness_potencial=17_258, oferta_efetiva_disponivel=14_521),
        dict(metragem_m2=1_524, aluguel_pedido=75_000, pe_direito_m=3.50),
        # payback "> 60 meses" no PDF -> None no payload (nao paga no horizonte).
        dict(margem_ebitda_pct=0.233, payback_meses=None,
             aluguel_teto_faixas={"ideal": 42_851.37, "teto": 57_135.16, "excecao": 85_702.74}),
    ),
    (
        "Av. Cons. Rosa e Silva, 1460",
        (CONCLUSAO_RESSALVAS, CONCLUSAO_REPROVADO),
        dict(pop_total_raio=43_673, renda_per_capita_media_raio=3_791.49,
             domicilios_total_raio=17_267, renda_domiciliar_total_raio=8_797.96),
        dict(sam_fitness_potencial=18_148, oferta_efetiva_disponivel=0),
        dict(metragem_m2=1_220, aluguel_pedido=55_000, pe_direito_m=3.50),
        dict(margem_ebitda_pct=0.210, payback_meses=None,
             aluguel_teto_faixas={"ideal": 33_354.13, "teto": 44_472.17, "excecao": 66_708.25}),
    ),
]


@pytest.mark.parametrize(
    "nome,esperado,result,residual,info,viab",
    _RECIFE,
    ids=[caso[0] for caso in _RECIFE],
)
def test_golden_recife(nome, esperado, result, residual, info, viab):
    dados = _viab_normalizado({**viab, "premissas": {"margem_viavel_min": 0.30, "payback_viavel_max": 36}})
    parecer = _avaliar_conclusao(result, residual, info, dados)
    obtido = (parecer.demografico.status, _fin(parecer).status)
    assert obtido == esperado, f"{nome}: {_texto(parecer)}"


def test_golden_recife_distribuicao():
    """Financeiro 1/2/2 -- a calibracao aprovada por Vinicius, intacta apos a DEC-030.

    Demografico 4/1/0: a separacao NAO reabriu a calibracao, so mostrou de onde vinham os
    vereditos. Se um dia a regua da praca ficar mais dura (metas absolutas sao de Felipe,
    DEC-021), e' esta segunda contagem que denuncia o deslocamento.
    """
    vazio = {CONCLUSAO_APROVADO: 0, CONCLUSAO_RESSALVAS: 0, CONCLUSAO_REPROVADO: 0}
    demografico, financeiro = dict(vazio), dict(vazio)
    for _nome, (demo, fin), *_resto in _RECIFE:
        demografico[demo] += 1
        financeiro[fin] += 1
    assert financeiro == {CONCLUSAO_APROVADO: 1, CONCLUSAO_RESSALVAS: 2, CONCLUSAO_REPROVADO: 2}
    assert demografico == {CONCLUSAO_APROVADO: 4, CONCLUSAO_RESSALVAS: 1, CONCLUSAO_REPROVADO: 0}


def test_rosa_e_silva_reprova_pela_regua_financeira_e_nao_pelo_mercado():
    """A DECISAO de 2026-08-06 tirou 'mercado consumido' dos eliminatorios: o residual
    zero deste ponto tem de aparecer como RESSALVA, com a reprovacao vindo de outro gate.

    Este e' o ponto que melhor mostra por que a DEC-030 separou os eixos: o mercado
    consumido e a reprovacao financeira estavam colapsados num "Reprovado" so, e era
    preciso ler a lista inteira para descobrir que a praca nao era o problema. Agora sao
    dois carimbos: praca COM RESSALVAS, financeiro REPROVADO.
    """
    _nome, _esperado, result, residual, info, viab = _RECIFE[4]
    dados = _viab_normalizado({**viab, "premissas": {"margem_viavel_min": 0.30, "payback_viavel_max": 36}})
    parecer = _avaliar_conclusao(result, residual, info, dados)
    assert _fin(parecer).status == CONCLUSAO_REPROVADO
    assert parecer.demografico.status == CONCLUSAO_RESSALVAS
    assert all("Mercado" not in linha for linha in parecer.eliminatorios)
    assert any("Mercado já consumido" in linha for linha in parecer.ressalvas)
    # O apontamento de mercado e' do eixo da PRACA -- nao pode ter vazado para o financeiro.
    assert any("Mercado já consumido" in linha for linha in parecer.demografico.ressalvas)
