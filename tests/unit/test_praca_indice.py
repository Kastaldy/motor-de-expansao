"""Contrato do indice conjuntivo da praca (camada 5 do funil).

O que estes testes protegem: a Dor 1 do dono -- "a camada 5 esta' jogando recomendacao
apenas em periferias". A causa media era que a fila ordenava por
`oferta_efetiva_disponivel`, que e' populacao quase pura (Spearman 0,995), e dentro de
uma cidade a maior populacao esta' na periferia densa. `rho(residual, renda)` foi medido
NEGATIVO nas 8 maiores capitais.

Sao testes de PROPRIEDADE, nao de numeros congelados: travam o que a regua promete
(absolutismo, ancoras, ausencia de aniquilacao, peso declarado), nao um valor de
producao que muda quando o dado muda.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SERVER = Path(__file__).resolve().parents[2] / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import praca_indice as pi  # noqa: E402


# ------------------------------------------------------------------ ancoras
def test_ancoras_da_nota_de_demanda():
    """As ancoras sao o contrato publicado na metodologia; nao podem deslizar."""
    notas = pi.nota_demanda([pi.DEMANDA_MIN_ALUNOS, pi.DEMANDA_MAX_ALUNOS])
    assert notas.iloc[0] == pytest.approx(0.0)
    assert notas.iloc[1] == pytest.approx(100.0)

    # O meio da escala LOG (nao da linear): 2.000 * sqrt(10) = 6.324,55 alunos.
    meio = pi.DEMANDA_MIN_ALUNOS * np.sqrt(pi.DEMANDA_MAX_ALUNOS / pi.DEMANDA_MIN_ALUNOS)
    assert pi.nota_demanda([meio]).iloc[0] == pytest.approx(50.0)


def test_nota_de_demanda_satura_e_nao_extrapola():
    """Acima do teto a nota nao passa de 100: so' se abre uma unidade por vez."""
    assert pi.nota_demanda([pi.DEMANDA_MAX_ALUNOS * 5]).iloc[0] == pytest.approx(100.0)
    assert pi.nota_demanda([0.0]).iloc[0] == pytest.approx(0.0)


def test_nota_de_demanda_e_absoluta_nao_relativa():
    """O mesmo residual da' a mesma nota em qualquer recorte.

    E' o ponto inteiro da DEC-040 aplicado ao segundo eixo: um numero que muda de
    significado conforme o conjunto em que e' calculado nao serve para comparar praca
    entre cidades.
    """
    sozinho = pi.nota_demanda([8_000.0]).iloc[0]
    entre_grandes = pi.nota_demanda([8_000.0, 19_000.0, 18_000.0]).iloc[0]
    entre_pequenos = pi.nota_demanda([8_000.0, 2_100.0, 2_050.0]).iloc[0]
    assert sozinho == pytest.approx(entre_grandes) == pytest.approx(entre_pequenos)


def test_nota_de_demanda_e_monotonica():
    valores = [2_000, 3_000, 5_000, 9_000, 15_000, 20_000]
    notas = pi.nota_demanda(valores).tolist()
    assert notas == sorted(notas)
    assert len(set(notas)) == len(notas), "a regua nao pode empatar dentro da faixa util"


# ------------------------------------------------------------------ indice
def test_peso_declarado_e_o_peso_aplicado():
    """Se alguem mexer nos pesos sem mexer no contrato, este teste cai."""
    assert pi.PESO_SOCIO + pi.PESO_DEMANDA == pytest.approx(1.0)
    assert pi.indice_praca([100.0], [0.0]).iloc[0] == pytest.approx(100.0 * pi.PESO_SOCIO)
    assert pi.indice_praca([0.0], [100.0]).iloc[0] == pytest.approx(100.0 * pi.PESO_DEMANDA)


def test_praca_excelente_e_disputada_nao_e_aniquilada():
    """Pedido explicito do dono: praca muito boa e ja' saturada SEGUE na lista.

    E' por isso que a combinacao e' soma ponderada e nao produto. Com produto, uma praca
    de nota socioeconomica 95 e demanda no piso (nota 0) zeraria e sumiria da fila.
    """
    excelente_disputada = pi.indice_praca([95.0], [0.0]).iloc[0]
    mediana_folgada = pi.indice_praca([35.0], [60.0]).iloc[0]
    assert excelente_disputada > 0.0
    assert excelente_disputada > mediana_folgada


def test_ordenacao_premia_quem_e_bom_nos_dois_eixos():
    """O coracao da Dor 1: entre iguais na soma bruta, ganha quem tem os dois eixos."""
    df = pd.DataFrame(
        {
            "nome": ["so_demanda", "equilibrada", "so_socio"],
            "ns": [20.0, 60.0, 90.0],
            "nd": [100.0, 60.0, 20.0],
        }
    )
    df["indice"] = pi.indice_praca(df["ns"], df["nd"])
    ordem = df.sort_values("indice", ascending=False)["nome"].tolist()
    # `so_demanda` -- a periferia densa e pobre -- deixa de liderar a fila.
    assert ordem[-1] == "so_demanda"
    assert ordem[0] == "so_socio"


def test_a_reforma_muda_de_fato_a_fila():
    """Guarda contra reversao silenciosa do peso para 0/100 (a ordenacao antiga).

    Cenario minimo com a assinatura da dor: o hexagono de maior residual e' o de pior
    perfil socioeconomico. Sob a regua antiga ele lidera; sob a nova, nao.
    """
    df = pd.DataFrame(
        {
            "nome": ["periferia_densa", "praca_boa"],
            "residual": [19_000.0, 4_000.0],
            "score": [31.0, 85.0],
        }
    )
    df["nd"] = pi.nota_demanda(df["residual"])
    df["indice"] = pi.indice_praca(df["score"], df["nd"])

    antiga = df.sort_values("residual", ascending=False)["nome"].tolist()
    nova = df.sort_values("indice", ascending=False)["nome"].tolist()
    assert antiga[0] == "periferia_densa"
    assert nova[0] == "praca_boa"


# ------------------------------------------------------------------ rotulos
def test_quadrantes_particionam_o_plano_sem_buraco_nem_sobreposicao():
    ns = [80.0, 80.0, 20.0, 20.0, 50.0]
    nd = [80.0, 20.0, 80.0, 20.0, 50.0]
    esperado = ["prioridade", "praca_forte", "volume", "marginal", "prioridade"]
    assert pi.rotulo_quadrante(ns, nd).tolist() == esperado


def test_todo_rotulo_bruto_tem_label_e_explicacao_de_exibicao():
    """Regra de acentuacao do CLAUDE.md: valor bruto sem acento, exibicao acentuada."""
    brutos = set(pi.QUADRANTE_LABELS)
    assert brutos == set(pi.QUADRANTE_EXPLICACAO)
    assert brutos == {"prioridade", "praca_forte", "volume", "marginal"}
    for chave in brutos:
        assert chave.isascii() and chave.islower()
    # E o inverso: a camada de exibicao e' a que carrega acento.
    assert any(not texto.isascii() for texto in pi.QUADRANTE_LABELS.values())
