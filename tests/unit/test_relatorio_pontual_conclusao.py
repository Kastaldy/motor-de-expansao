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
    PE_DIREITO_MIN,
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


def test_e3_pe_direito_abaixo_do_minimo_reprova():
    parecer = _parecer(info={"pe_direito_m": PE_DIREITO_MIN - 0.1})
    assert parecer.status == CONCLUSAO_REPROVADO


def test_pe_direito_no_minimo_exato_passa():
    assert _parecer(info={"pe_direito_m": PE_DIREITO_MIN}).status == CONCLUSAO_APROVADO


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
@pytest.mark.parametrize("campo", ["metragem_m2", "aluguel_pedido", "pe_direito_m"])
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
    assert parecer.status == CONCLUSAO_APROVADO


def test_valores_nan_nao_disparam_gate():
    parecer = _parecer(info={"metragem_m2": float("nan"), "pe_direito_m": float("nan")})
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
        _MIN_RESULT, None, residual=_RESIDUAL_OK, info_imovel=_INFO_OK, viabilidade=_VIAB_OK
    )
    assert b"/Count 10" in pdf_bytes  # 7 base + info + numeros + conclusao
    assert _TIT_CONCLUSAO in pdf_bytes
    assert "Aprovado".encode("latin-1") in pdf_bytes
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
    _conclusao_cards_aluguel(pdf, dados, info, 36.0, 888.0, (0, 167, 157))
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


def test_status_reprovado_chega_aos_bytes_do_pdf():
    pdf_bytes = gerar_pdf_relatorio_pontual_classico(
        _MIN_RESULT,
        None,
        residual=_RESIDUAL_OK,
        info_imovel=_INFO_OK,
        viabilidade={**_VIAB_OK, "margem_ebitda_pct": 0.21, "payback_meses": None},
    )
    assert b"Reprovado" in pdf_bytes


def test_pagina_de_conclusao_nao_usa_caractere_fora_de_latin1():
    """Fora de latin-1 (travessao, bullet, seta) vira '?' silencioso no core font."""
    parecer = _parecer(
        info={"metragem_m2": 900, "pe_direito_m": 3.0, "aluguel_pedido": 99_999.0},
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
