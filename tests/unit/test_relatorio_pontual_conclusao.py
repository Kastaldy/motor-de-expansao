"""Testes da pagina de CONCLUSAO do Relatorio Pontual Censitario.

Cobre (a) a regua tri-estado por gate, (b) os invariantes que a regua nao pode violar
-- indecidivel nunca reprova, zero numero de faturamento no parecer --, (c) a insercao
da pagina no PDF e (d) o golden dos 5 pontos reais do Recife que calibraram os cortes
(aprovados por Vinicius em 2026-08-06). READ-ONLY sobre o M1; sem PII.
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


# --------------------------------------------------------------------------- #
# Base                                                                        #
# --------------------------------------------------------------------------- #
def test_cenario_limpo_e_aprovado_sem_observacoes():
    parecer = _parecer()
    assert parecer.status == CONCLUSAO_APROVADO
    assert parecer.eliminatorios == ()
    assert parecer.ressalvas == ()


# --------------------------------------------------------------------------- #
# Retorno: E1 (falha nos DOIS) x R1 (falha em UM)                             #
# --------------------------------------------------------------------------- #
def test_e1_margem_e_payback_juntos_reprovam():
    parecer = _parecer(viab={"margem_ebitda_pct": 0.21, "payback_meses": 58.0})
    assert parecer.status == CONCLUSAO_REPROVADO
    assert len(parecer.eliminatorios) == 1


def test_r1_so_payback_estourado_e_ressalva():
    """Falhar so no prazo NAO reprova: e ponto negociavel, nao morto (decisao 2026-08-06)."""
    parecer = _parecer(viab={"margem_ebitda_pct": 0.34, "payback_meses": 44.0})
    assert parecer.status == CONCLUSAO_RESSALVAS
    assert parecer.eliminatorios == ()
    assert "Prazo de retorno" in _texto(parecer)


def test_r1_so_margem_baixa_e_ressalva():
    parecer = _parecer(viab={"margem_ebitda_pct": 0.24, "payback_meses": 30.0})
    assert parecer.status == CONCLUSAO_RESSALVAS
    assert parecer.eliminatorios == ()
    assert "Margem operacional" in _texto(parecer)


@pytest.mark.parametrize("payback", [None, float("inf")])
def test_payback_ausente_ou_infinito_conta_como_nao_paga(payback):
    """`> 60 meses` na pagina anterior e FALHA conhecida, nao dado ausente."""
    parecer = _parecer(viab={"margem_ebitda_pct": 0.21, "payback_meses": payback})
    assert parecer.status == CONCLUSAO_REPROVADO


def test_margem_exatamente_na_regua_passa():
    """Comparacao e `<` -- bater a regua na mosca aprova, como em `_cor_por_meta`."""
    parecer = _parecer(viab={"margem_ebitda_pct": 0.30, "payback_meses": 36.0})
    assert parecer.status == CONCLUSAO_APROVADO


def test_payload_legado_sem_reguas_rebaixa_mas_nunca_reprova():
    """Sem os limites nao da para saber se falhou em um criterio ou nos dois."""
    viab = {k: v for k, v in _VIAB_OK.items() if k not in {"margem_viavel_min", "payback_viavel_max"}}
    viab["flag_viavel"] = False
    parecer = _avaliar_conclusao(_RESULT_OK, _RESIDUAL_OK, _INFO_OK, viab)
    assert parecer.status == CONCLUSAO_RESSALVAS
    assert parecer.eliminatorios == ()


# --------------------------------------------------------------------------- #
# Aluguel pedido x faixas de aluguel-teto: E2 x R2                            #
# --------------------------------------------------------------------------- #
def test_e2_aluguel_acima_da_excecao_reprova():
    parecer = _parecer(info={"aluguel_pedido": 99_001.0})
    assert parecer.status == CONCLUSAO_REPROVADO


def test_r2_aluguel_entre_teto_e_excecao_e_ressalva():
    parecer = _parecer(info={"aluguel_pedido": 70_000.0})
    assert parecer.status == CONCLUSAO_RESSALVAS
    assert "renegociação" in _texto(parecer)


def test_aluguel_no_teto_exato_passa():
    assert _parecer(info={"aluguel_pedido": 66_000.0}).status == CONCLUSAO_APROVADO


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
    assert parecer.status == CONCLUSAO_REPROVADO


@pytest.mark.parametrize("pe_direito", [2.0, 3.49, None, float("nan")])
def test_pe_direito_saiu_da_regua_e_nao_decide_mais_nada(pe_direito):
    """Retirado por Vinicius (2026-08-07). Continua digitado e impresso na pagina de
    informacoes do imovel, mas nao reprova, nao rebaixa e nao cobra preenchimento."""
    parecer = _parecer(info={"pe_direito_m": pe_direito})
    assert parecer.status == CONCLUSAO_APROVADO
    assert parecer.ressalvas == ()
    assert "direito" not in _texto(parecer)


@pytest.mark.parametrize("metragem", [AREA_IDEAL_MIN_M2 - 1, AREA_IDEAL_MAX_M2 + 1])
def test_r3_metragem_fora_da_faixa_ideal_e_so_ressalva(metragem):
    parecer = _parecer(info={"metragem_m2": metragem})
    assert parecer.status == CONCLUSAO_RESSALVAS
    assert parecer.eliminatorios == ()


@pytest.mark.parametrize("metragem", [AREA_IDEAL_MIN_M2, AREA_IDEAL_MAX_M2])
def test_bordas_da_faixa_ideal_sao_inclusivas(metragem):
    assert _parecer(info={"metragem_m2": metragem}).status == CONCLUSAO_APROVADO


# --------------------------------------------------------------------------- #
# Zona morta, extrapolacao, metas e mercado                                   #
# --------------------------------------------------------------------------- #
def test_e4_zona_morta_reprova_e_traduz_o_motivo():
    parecer = _parecer(viab={"flag_zona_morta": True, "motivo_zona_morta": "pop<5000"})
    assert parecer.status == CONCLUSAO_REPROVADO
    assert "população de captação abaixo de 5.000" in _texto(parecer)


def test_motivo_de_zona_morta_desconhecido_sai_como_veio():
    parecer = _parecer(viab={"flag_zona_morta": True, "motivo_zona_morta": "criterio_novo"})
    assert "criterio_novo" in _texto(parecer)


def test_r5_fora_do_envelope_de_calibracao_e_ressalva():
    parecer = _parecer(viab={"flag_fora_envelope": True})
    assert parecer.status == CONCLUSAO_RESSALVAS
    assert "incerteza" in _texto(parecer)


def test_r4_meta_censitaria_nao_atingida_e_ressalva():
    parecer = _parecer(result={"pop_total_raio": 4_000})
    assert parecer.status == CONCLUSAO_RESSALVAS
    assert "População total no raio" in _texto(parecer)


def test_r7_mercado_consumido_e_ressalva_e_nao_eliminatorio():
    """Saturacao e leitura de disputa, nao sentenca -- decisao de Vinicius, 2026-08-06."""
    parecer = _parecer(residual={"oferta_efetiva_disponivel": 0})
    assert parecer.status == CONCLUSAO_RESSALVAS
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
    assert parecer.status == CONCLUSAO_RESSALVAS
    assert any("Residual Fitness" in linha for linha in parecer.ressalvas)


# --------------------------------------------------------------------------- #
# INVARIANTE: indecidivel nunca reprova                                       #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("campo", ["metragem_m2", "aluguel_pedido"])
def test_r6_campo_essencial_ausente_vira_ressalva_nunca_reprovacao(campo):
    parecer = _parecer(info={campo: None})
    assert parecer.status == CONCLUSAO_RESSALVAS
    assert parecer.eliminatorios == ()
    assert "não pôde ser avaliado" in _texto(parecer)


def test_sem_info_do_imovel_nenhum_gate_fisico_dispara():
    parecer = _avaliar_conclusao(_RESULT_OK, _RESIDUAL_OK, None, _VIAB_OK)
    assert parecer.status == CONCLUSAO_RESSALVAS
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
    assert parecer.status == CONCLUSAO_RESSALVAS
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


def test_sem_viabilidade_nao_ha_pagina_de_conclusao():
    """API e bot nao mandam `viabilidade` -- o PDF deles segue identico ao de hoje."""
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(_MIN_RESULT, None)
    assert b"/Count 7" in pdf_bytes
    assert _TIT_CONCLUSAO not in pdf_bytes


def test_com_viabilidade_a_pagina_entra_antes_do_credito():
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        _RESULT_PDF, None, residual=_RESIDUAL_OK, info_imovel=_INFO_OK, viabilidade=_VIAB_OK
    )
    assert b"/Count 10" in pdf_bytes  # 7 base + info + numeros + conclusao
    assert _TIT_CONCLUSAO in pdf_bytes
    assert b"APROVADO" in pdf_bytes  # selo; ver `test_selo_carimba_o_status...`
    assert b"PARA COMIT" in pdf_bytes  # linha de apoio do selo
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
    "Aprovado" daria falso positivo em qualquer um dos tres estados.
    """
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        _RESULT_PDF,
        None,
        residual=_RESIDUAL_OK,
        info_imovel=_INFO_OK,
        viabilidade={**_VIAB_OK, **viab_extra},
    )
    assert esperado in pdf_bytes


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
    from motor_expansao.dashboard.censo_report import _conclusao_itens

    parecer = _parecer(
        info={"metragem_m2": 900},  # eliminatorio
        viab={"flag_fora_envelope": True},  # ressalva
    )
    itens = _conclusao_itens(parecer)
    severidades = [sev for _txt, sev in itens]
    assert severidades == sorted(severidades, key=lambda s: s != "eliminatorio")


def test_parecer_limpo_vira_um_card_de_confirmacao():
    from motor_expansao.dashboard.censo_report import _conclusao_itens

    itens = _conclusao_itens(_parecer())
    assert len(itens) == 1
    assert itens[0][1] == "confirmacao"


def test_conteudo_e_centralizado_verticalmente_na_area():
    """Com pouco conteudo a coluna NAO comeca colada na banda de titulo."""
    from motor_expansao.dashboard.censo_report import (
        _CONCLUSAO_AREA_BASE,
        _CONCLUSAO_AREA_TOPO,
        _CONCLUSAO_SELO_H,
    )

    folga = (_CONCLUSAO_AREA_BASE - _CONCLUSAO_AREA_TOPO - _CONCLUSAO_SELO_H) / 2
    assert folga > 0  # o selo sobra espaco dos dois lados
    # E a area de conteudo termina acima da nota metodologica.
    from motor_expansao.dashboard.censo_report import _CONCLUSAO_NOTA_Y

    assert _CONCLUSAO_AREA_BASE <= _CONCLUSAO_NOTA_Y


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
    por zona morta, contra o invariante de que indecidivel nunca reprova."""
    parecer = _parecer(viab={flag: float("nan")})
    assert parecer.status == CONCLUSAO_APROVADO
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
    assert parecer.status == CONCLUSAO_RESSALVAS
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
    """INVARIANTE FORTE: se o motor diz que o cenario nao fecha, o parecer nao aprova."""
    for viavel, parecer, dados, info in _matriz_cenarios():
        if not viavel:
            assert parecer.status != CONCLUSAO_APROVADO, (
                f"cenario inviavel aprovado: {dados} {info}"
            )


def test_conclusao_mais_dura_que_a_tela_sempre_diz_o_porque():
    """A Conclusao pode reprovar o que a tela aprovou (ela olha o IMOVEL e a PRACA, nao
    so o cenario financeiro) -- mas nunca em silencio."""
    divergencias = 0
    for viavel, parecer, _dados, _info in _matriz_cenarios():
        if viavel and parecer.status == CONCLUSAO_REPROVADO:
            divergencias += 1
            assert parecer.eliminatorios, "reprovou sem eliminatorio que explique"
    assert divergencias > 0  # a matriz precisa exercitar o caso, senao o teste e' vazio


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
_RECIFE = [
    (
        "Av. Pinheiros, 1212",
        CONCLUSAO_APROVADO,
        dict(pop_total_raio=24_001, renda_per_capita_media_raio=5_366.85,
             domicilios_total_raio=8_770, renda_domiciliar_total_raio=10_085.75),
        dict(sam_fitness_potencial=12_239, oferta_efetiva_disponivel=10_684),
        dict(metragem_m2=1_932, aluguel_pedido=45_000, pe_direito_m=4.00),
        dict(margem_ebitda_pct=0.399, payback_meses=34,
             aluguel_teto_faixas={"ideal": 54_137.41, "teto": 72_183.22, "excecao": 108_274.83}),
    ),
    (
        "Av. Gen. Mac Arthur, 1653",
        CONCLUSAO_RESSALVAS,
        dict(pop_total_raio=23_805, renda_per_capita_media_raio=1_680.05,
             domicilios_total_raio=8_951, renda_domiciliar_total_raio=8_270.96),
        dict(sam_fitness_potencial=12_078, oferta_efetiva_disponivel=4_253),
        dict(metragem_m2=1_912, aluguel_pedido=75_000, pe_direito_m=7.00),
        dict(margem_ebitda_pct=0.312, payback_meses=44,
             aluguel_teto_faixas={"ideal": 53_584.18, "teto": 71_445.57, "excecao": 107_168.35}),
    ),
    (
        "R. Sao Miguel, 600",
        CONCLUSAO_RESSALVAS,
        dict(pop_total_raio=29_037, renda_per_capita_media_raio=8_554.26,
             domicilios_total_raio=10_597, renda_domiciliar_total_raio=17_068.47),
        dict(sam_fitness_potencial=7_765, oferta_efetiva_disponivel=6_804),
        dict(metragem_m2=1_349, aluguel_pedido=40_000, pe_direito_m=9.00),
        dict(margem_ebitda_pct=0.320, payback_meses=57,
             aluguel_teto_faixas={"ideal": 38_001.32, "teto": 50_668.43, "excecao": 76_002.64}),
    ),
    (
        "Estr. do Arraial, 3851",
        CONCLUSAO_REPROVADO,
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
        CONCLUSAO_REPROVADO,
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
    assert parecer.status == esperado, f"{nome}: {_texto(parecer)}"


def test_golden_recife_distribuicao():
    """1 aprovado / 2 com ressalvas / 2 reprovados -- a calibracao aprovada no gate."""
    contagem = {CONCLUSAO_APROVADO: 0, CONCLUSAO_RESSALVAS: 0, CONCLUSAO_REPROVADO: 0}
    for _nome, esperado, *_resto in _RECIFE:
        contagem[esperado] += 1
    assert contagem == {CONCLUSAO_APROVADO: 1, CONCLUSAO_RESSALVAS: 2, CONCLUSAO_REPROVADO: 2}


def test_rosa_e_silva_reprova_pela_regua_financeira_e_nao_pelo_mercado():
    """A DECISAO de 2026-08-06 tirou 'mercado consumido' dos eliminatorios: o residual
    zero deste ponto tem de aparecer como RESSALVA, com a reprovacao vindo de outro gate."""
    _nome, _esperado, result, residual, info, viab = _RECIFE[4]
    dados = _viab_normalizado({**viab, "premissas": {"margem_viavel_min": 0.30, "payback_viavel_max": 36}})
    parecer = _avaliar_conclusao(result, residual, info, dados)
    assert parecer.status == CONCLUSAO_REPROVADO
    assert all("Mercado" not in linha for linha in parecer.eliminatorios)
    assert any("Mercado já consumido" in linha for linha in parecer.ressalvas)
