"""Bloco A / commit A8 — a regua absoluta deixa de ser propriedade do modulo.

`calibrar_renda_setor_2022` produz o **score primario operacional do Brasil**. Este
commit nao troca ancora nenhuma: entrega a CAPACIDADE de receber ancoras, com default
nos quatro numeros de sempre. O que este arquivo prova, em ordem de importancia:

1. **O Brasil nao se moveu.** Chamar sem `ancoras` da exatamente o mesmo resultado de
   antes do commit, e nas fronteiras exatas — e a unica coisa que justifica um diff num
   arquivo CRITICO passar sem recomputar artefato.
2. **O parametro funciona.** Com ancoras argentinas, a nota muda na direcao certa.
3. **`Perfil.ancoras()` encaixa direto.** E a costura com o Bloco B: o exportador passa
   `PERFIL.ancoras()` sem conversao, porque e o MESMO tipo.
4. **`ancoras` e keyword-only.** Um terceiro posicional cairia onde `pop_abs` deveria ir.

Spec: `docs/spec_bloco_a_perfil.md` §4.2.
"""

from __future__ import annotations

import numpy as np
import pytest

from motor_expansao.perfil import PERFIL_BR_EMBARCADO, Ancoras, carregar_perfil
from motor_expansao.pipelines.calibrar_renda_setor_2022 import (
    ANCORAS_BR,
    POP_ABS_MAX,
    POP_ABS_MIN,
    RENDA_ABS_MAX,
    RENDA_ABS_MIN,
    calcular_score_calibrado,
    nota_pop_absoluta,
    nota_renda_absoluta,
)

#: Ancoras argentinas medidas (universo povoado, 5.148 hexagonos, 2026-08-31):
#: renda p05 = 342,4 -> piso 350; p99 = 926,2, max 1.141,1 -> teto 1.000 (satura 0,29%).
#: Populacao e a MESMA grade do Brasil — hexagono H3 res 7 dos dois lados.
ANCORAS_AR = Ancoras(renda_min=350.0, renda_max=1_000.0, pop_min=1_000.0, pop_max=100_000.0)


# --------------------------------------------------------------------------------
# 1. O Brasil nao se moveu
# --------------------------------------------------------------------------------


def test_ancoras_br_sao_as_constantes_do_modulo() -> None:
    """`ANCORAS_BR` e MONTADA a partir das constantes, nao as substitui. As constantes
    continuam existindo com o mesmo valor no mesmo lugar porque
    `test_regua_absoluta_censitaria.py:22-25` as importa por nome."""
    assert ANCORAS_BR == Ancoras(300.0, 4_000.0, 1_000.0, 100_000.0)
    assert ANCORAS_BR.renda_min == RENDA_ABS_MIN
    assert ANCORAS_BR.renda_max == RENDA_ABS_MAX
    assert ANCORAS_BR.pop_min == POP_ABS_MIN
    assert ANCORAS_BR.pop_max == POP_ABS_MAX


@pytest.mark.parametrize(
    ("renda", "esperado"),
    [
        (0.0, 0.0),  # abaixo do piso satura em 0
        (300.0, 0.0),  # o piso vale 0
        (1_150.0, 100.0 * 850.0 / 3_700.0),  # meio da escala, linear
        (4_000.0, 100.0),  # o teto vale 100
        (8_756.0, 100.0),  # o maximo medido no Brasil satura
    ],
)
def test_nota_renda_default_e_a_regua_de_sempre(renda: float, esperado: float) -> None:
    obtido = float(nota_renda_absoluta(np.array([renda]))[0])
    assert obtido == pytest.approx(esperado)


@pytest.mark.parametrize(
    ("pop", "esperado"),
    [
        (500.0, 0.0),  # abaixo do piso satura em 0
        (1_000.0, 0.0),  # o piso vale 0
        (10_000.0, 50.0),  # log: 10.000 e a raiz de 1.000 x 100.000
        (100_000.0, 100.0),  # o teto vale 100
        (141_507.0, 100.0),  # o maximo medido no Brasil satura
    ],
)
def test_nota_pop_default_e_a_regua_de_sempre(pop: float, esperado: float) -> None:
    obtido = float(nota_pop_absoluta(np.array([pop]))[0])
    assert obtido == pytest.approx(esperado)


def test_default_e_ancoras_br_explicito_dao_o_MESMO_array() -> None:
    """Byte a byte, sobre uma grade que cobre as duas escalas inteiras. E este teste que
    autoriza o merge sem recomputar o artefato nacional."""
    renda = np.linspace(0.0, 9_000.0, 601)
    pop = np.logspace(0.0, 5.5, 601)
    for a, b in (
        (nota_renda_absoluta(renda), nota_renda_absoluta(renda, ancoras=ANCORAS_BR)),
        (nota_pop_absoluta(pop), nota_pop_absoluta(pop, ancoras=ANCORAS_BR)),
    ):
        np.testing.assert_array_equal(a, b)

    sem = calcular_score_calibrado(renda, pop)
    com = calcular_score_calibrado(renda, pop, ancoras=ANCORAS_BR)
    for antes, depois in zip(sem, com, strict=True):
        np.testing.assert_array_equal(antes, depois)


def test_score_completo_em_pontos_conhecidos() -> None:
    """Ancora numerica dura: 0,60 x nota_renda + 0,40 x nota_pop + ajuste executivo,
    clipado em 0-100. Se o ajuste executivo mudar, este teste acusa."""
    hex_score, adj, score = calcular_score_calibrado(
        np.array([4_000.0, 300.0]), np.array([100_000.0, 1_000.0])
    )
    # Renda 100 e pop 100 -> hex 100, e o ajuste de "ambos >= 75" soma +5, mas o clip
    # final segura em 100.
    assert hex_score[0] == pytest.approx(100.0)
    assert adj[0] == pytest.approx(5.0)
    assert score[0] == pytest.approx(100.0)
    # Renda 0 e pop 0 -> hex 0, ajuste de "ambos < 25" tira 5 e 3, e o clip segura em 0.
    assert hex_score[1] == pytest.approx(0.0)
    assert score[1] == pytest.approx(0.0)


# --------------------------------------------------------------------------------
# 2. O parametro funciona
# --------------------------------------------------------------------------------


def test_ancoras_argentinas_mudam_a_nota_de_renda() -> None:
    """USD 700 e classe media alta na escala argentina (p95 = 740) e quase nada na
    brasileira. E exatamente por isso que copiar a ancora de RENDA entre paises seria
    erro real: R$ e USD nao tem relacao, e as distribuicoes tampouco."""
    valor = np.array([700.0])
    br = float(nota_renda_absoluta(valor)[0])
    ar = float(nota_renda_absoluta(valor, ancoras=ANCORAS_AR)[0])
    assert br == pytest.approx(100.0 * 400.0 / 3_700.0)  # ~10,8
    assert ar == pytest.approx(100.0 * 350.0 / 650.0)  # ~53,8
    assert ar > br


def test_ancoras_de_populacao_coincidem_entre_br_e_ar() -> None:
    """NAO e coincidencia a ser desconfiada: e a MESMA unidade, hexagono H3 res 7 dos
    dois lados. A coluna se chama `pop_total_setor_2022` porque isso e a procedencia do
    atributo (Censo por setor, atribuido ao hexagono), nao a granularidade da linha."""
    pop = np.array([1_000.0, 10_000.0, 100_000.0])
    np.testing.assert_array_equal(
        nota_pop_absoluta(pop), nota_pop_absoluta(pop, ancoras=ANCORAS_AR)
    )


def test_ancora_nova_propaga_ate_o_score() -> None:
    """`calcular_score_calibrado` tem de REPASSAR as ancoras para as duas notas. Se
    esquecesse de uma, o score sairia meio brasileiro e meio argentino, sem erro."""
    renda, pop = np.array([700.0]), np.array([10_000.0])
    _, _, br = calcular_score_calibrado(renda, pop)
    _, _, ar = calcular_score_calibrado(renda, pop, ancoras=ANCORAS_AR)
    assert ar[0] > br[0]
    # 0,60 x 53,8 + 0,40 x 50,0 = 52,3; sem ajuste (nenhum termo passa de 75 nem cai
    # abaixo de 25).
    assert ar[0] == pytest.approx(0.60 * (100.0 * 350.0 / 650.0) + 0.40 * 50.0)


# --------------------------------------------------------------------------------
# 3. A costura com o Bloco B
# --------------------------------------------------------------------------------


def test_perfil_ancoras_encaixa_sem_conversao() -> None:
    """`Perfil.ancoras()` devolve o MESMO tipo que o pipeline aceita. E o que permite ao
    exportador do Bloco B fazer `calcular_score_calibrado(..., ancoras=PERFIL.ancoras())`
    sem uma linha de adaptacao — e o que evita dois dataclasses estruturalmente iguais
    mas distintos nesse ponto de costura."""
    do_perfil = carregar_perfil(PERFIL_BR_EMBARCADO).ancoras()
    assert isinstance(do_perfil, Ancoras)
    assert do_perfil == ANCORAS_BR

    renda, pop = np.array([1_500.0]), np.array([15_000.0])
    np.testing.assert_array_equal(
        calcular_score_calibrado(renda, pop)[2],
        calcular_score_calibrado(renda, pop, ancoras=do_perfil)[2],
    )


# --------------------------------------------------------------------------------
# 4. Keyword-only
# --------------------------------------------------------------------------------


def test_ancoras_e_keyword_only() -> None:
    """Sem o `*`, um terceiro posicional cairia onde `pop_abs` deveria ir — e o score
    sairia errado em silencio, num artefato nacional."""
    with pytest.raises(TypeError):
        nota_renda_absoluta(np.array([1_000.0]), ANCORAS_AR)  # type: ignore[misc]
    with pytest.raises(TypeError):
        calcular_score_calibrado(np.array([1_000.0]), np.array([5_000.0]), ANCORAS_AR)  # type: ignore[misc]
