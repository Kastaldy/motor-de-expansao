"""Recomendacao escrita quando a praca esta com o mercado consumido.

O parecer ja dizia o NUMERO ("residual X contra potencial Y") e parava ali. Esta linha
responde a pergunta seguinte -- da para entrar? -- em texto, e SO' aparece quando o
mercado esta de fato consumido.
"""

from __future__ import annotations

from motor_expansao.dashboard.censo_report import (
    _CONCLUSAO_RECOMENDACAO_DISPUTA,
    _avaliar_conclusao,
)

_RESULT = {
    "pop_total_raio": 20_000,
    "renda_per_capita_media_raio": 3_000.0,
    "domicilios_total_raio": 8_000,
    "renda_domiciliar_total_raio": 9_000.0,
    "n_concorrentes": 6,
}
# SAM alto E residual abaixo da meta (2.000) -> mercado consumido.
_RESIDUAL_CONSUMIDO = {
    "sam_fitness_potencial": 12_000,
    "oferta_efetiva_disponivel": 400,
    "oferta_consumida_mercado_estimada": 11_600,
}
_RESIDUAL_FOLGADO = {
    "sam_fitness_potencial": 12_000,
    "oferta_efetiva_disponivel": 9_000,
    "oferta_consumida_mercado_estimada": 3_000,
}


def _ressalvas(residual: dict) -> list[str]:
    parecer = _avaliar_conclusao(_RESULT, residual, None, {}, somente_estudo=True)
    return list(parecer.demografico.ressalvas)


def test_praca_consumida_ganha_a_recomendacao():
    assert _CONCLUSAO_RECOMENDACAO_DISPUTA in _ressalvas(_RESIDUAL_CONSUMIDO)


def test_a_recomendacao_vem_depois_do_numero_que_a_justifica():
    ressalvas = _ressalvas(_RESIDUAL_CONSUMIDO)
    numero = next(i for i, t in enumerate(ressalvas) if t.startswith("Mercado já consumido"))
    assert ressalvas[numero + 1] == _CONCLUSAO_RECOMENDACAO_DISPUTA


def test_praca_com_residual_nao_recomenda_disputa():
    assert _CONCLUSAO_RECOMENDACAO_DISPUTA not in _ressalvas(_RESIDUAL_FOLGADO)


def test_sem_dado_de_mercado_nao_recomenda_nada():
    # Indecidivel nunca vira veredito: sem SAM/residual a recomendacao nao sai.
    assert _CONCLUSAO_RECOMENDACAO_DISPUTA not in _ressalvas({})


def test_a_recomendacao_nao_crava_metragem():
    # A area das concorrentes NAO existe em `competitors.py`; a frase diz a direcao
    # sem inventar o alvo numerico.
    assert "m²" not in _CONCLUSAO_RECOMENDACAO_DISPUTA
    assert "metragem" in _CONCLUSAO_RECOMENDACAO_DISPUTA
