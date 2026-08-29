"""BLK-MA-17-FU2: `dedup_cadeias_do_feed` passa a comparar o feed CONTRA SI MESMO entre fontes.

A dedup que a DEC-034 criou casava cada unidade do feed **só** contra `concorrentes_mapeados`;
nunca comparava unidades do feed entre si. `dedup_independentes` faz o oposto — insere o
sobrevivente no bucket e colapsa linhas de `fonte` diferentes. A camada ficou **assimétrica**: o
lado das independentes protegido contra a duplicata TotalPass x WellHub, e o lado das cadeias não.

**O que isso custa quando o TotalPass entrar.** A mesma unidade de rede listada pelos dois
agregadores a poucos metros, e longe de qualquer pin mapeado (o recorte das **1.171** sobreviventes
de hoje), produz DUAS linhas de oferta. As gêmeas se pressionam — `49,96` pontos onde não há
concorrente nenhum — e o dano **não para nelas**: as duas viram dois pontos independentes no array
concatenado, e a auto-exclusão zera apenas a posição do próprio observador. Logo **qualquer academia
dentro dos 2 km enxerga dois concorrentes onde há um**, com `n_concorrentes_no_raio` `+1` e a oferta
daquele endereço em dobro. As três réguas visíveis no pin que a DEC-034 lista (`pressao`, `n_conc`,
`dist_m`) se movem para terceiros.

**Efeito hoje: exatamente nulo.** O snapshot `2026-33` é 100% WellHub (`22.173` linhas, fonte
única) e o diretório do TotalPass não existe em disco. O gatilho não exige mudar código: basta
um CSV dele aparecer entre os coletores, porque `coordenadas_por_chave()` lê os três
diretórios por default e seu único dedup é
`drop_duplicates(subset=["fonte","chave_snapshot"])`, que por construção não colapsa entre
fontes.

**A restrição que decide o desenho.** Colapsar dentro da MESMA fonte está proibido, e foi medido:
dos 5 pares de cadeias do feed a `<= 50 m`, os cinco são `wellhub x wellhub` e **três são redes
distintas dividindo prédio** (`skyfit` x `panobianco` a 2,9 m; `selfit` x `power_fit` a 22,5 m;
`force_one` x `world_gym` a 39,9 m). A guarda de fonte os pula por construção — é o que mantém o
efeito de hoje em zero.

READ-ONLY sobre o M1.
"""

from __future__ import annotations

import pandas as pd
import pytest

from motor_expansao.vulnerabilidade import contrato as c
from motor_expansao.vulnerabilidade.pressao_competitiva import (
    _pontos_validos_frame,
    calcular_pressao_por_academia,
    dedup_cadeias_do_feed,
)

_LAT, _LNG = -23.5500, -46.6300
_GRAU_LAT_M = 111_320.0


def _norte(metros: float) -> float:
    return _LAT + metros / _GRAU_LAT_M


def _observador(fonte: str = "wellhub", chave: str = "obs", *, metros: float = 0.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "fonte": [fonte],
            "chave_snapshot": [chave],
            "lat": [_norte(metros)],
            "lng": [_LNG],
        }
    )


def _mapeados(pontos: list[tuple[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "rede": [rede for rede, _ in pontos],
            "lat": [_norte(m) for _, m in pontos],
            "lng": [_LNG] * len(pontos),
            "status_registro": ["valido"] * len(pontos),
        }
    )


def _sem_cadeias() -> pd.DataFrame:
    return pd.DataFrame({"rede": [], "lat": [], "lng": [], "status_registro": []})


def _feed(linhas: list[tuple[str, str, str, float]]) -> pd.DataFrame:
    """`(fonte, chave, rede, metros ao norte)`."""
    return pd.DataFrame(
        {
            "fonte": [f for f, _, _, _ in linhas],
            "chave_snapshot": [k for _, k, _, _ in linhas],
            "rede": [r for _, _, r, _ in linhas],
            "lat": [_norte(m) for _, _, _, m in linhas],
            "lng": [_LNG] * len(linhas),
        }
    )


# --------------------------------------------------------------------------- #
# A dedup em si                                                                #
# --------------------------------------------------------------------------- #
def test_gemea_em_fontes_distintas_colapsa() -> None:
    """A mesma Bluefit no TotalPass e no WellHub a 3 m: uma unidade, não duas."""
    feed = _feed(
        [("totalpass", "r1", "bluefit", 0.0), ("wellhub", "r1", "bluefit", 3.0)]
    )
    # Pin mapeado a 6,7 km: existe para o `offset` não ser zero, mas não qualifica ninguém.
    pontos = _pontos_validos_frame(_mapeados([("smart_fit", 6_700.0)]))
    sobreviventes, mapa = dedup_cadeias_do_feed(feed, pontos)

    assert len(sobreviventes) == 1, "a gemea entre fontes tinha de colapsar"
    offset = len(pontos)
    # `totalpass` < `wellhub` na ordem estável: a primeira sobrevive.
    assert mapa[("totalpass", "r1")] == offset
    assert mapa[("wellhub", "r1")] == offset, "a colapsada aponta para a sobrevivente"


def test_mesma_fonte_a_menos_de_50m_continua_valendo_por_duas() -> None:
    """Os 3 pares reais de redes distintas dividindo prédio não podem ser apagados.

    É a guarda que mantém o efeito deste bloco em ZERO sobre o dado de hoje: todos os pares de
    cadeias a `<= 50 m` no snapshot `2026-33` são da mesma fonte.
    """
    feed = _feed(
        [("wellhub", "a", "skyfit", 0.0), ("wellhub", "b", "panobianco", 2.9)]
    )
    pontos = _pontos_validos_frame(_mapeados([("smart_fit", 6_700.0)]))
    sobreviventes, mapa = dedup_cadeias_do_feed(feed, pontos)

    assert len(sobreviventes) == 2, "MESMA fonte nunca colapsa — sao duas academias reais"
    offset = len(pontos)
    assert sorted([mapa[("wellhub", "a")], mapa[("wellhub", "b")]]) == [offset, offset + 1]


def test_o_pin_mapeado_tem_precedencia_sobre_a_gemea_do_feed() -> None:
    """Quem já está desenhado no funil absorve — a segunda passagem só roda se a primeira falhar."""
    feed = _feed(
        [("totalpass", "r1", "bluefit", 0.0), ("wellhub", "r1", "bluefit", 3.0)]
    )
    pontos = _pontos_validos_frame(_mapeados([("bluefit", 1.0)]))
    sobreviventes, mapa = dedup_cadeias_do_feed(feed, pontos)

    assert len(sobreviventes) == 0, "as duas colapsam contra o pin do funil"
    offset = len(pontos)
    assert mapa[("totalpass", "r1")] < offset, "o representante tem de ser o ponto MAPEADO"
    assert mapa[("wellhub", "r1")] < offset


def test_fonte_unica_nao_muda_nada() -> None:
    """O estado de hoje: com uma fonte só, a segunda passagem nunca dispara."""
    feed = _feed(
        [
            ("wellhub", "a", "bluefit", 0.0),
            ("wellhub", "b", "bluefit", 3.0),
            ("wellhub", "c", "bluefit", 6.0),
        ]
    )
    pontos = _pontos_validos_frame(_mapeados([("smart_fit", 6_700.0)]))
    sobreviventes, _mapa = dedup_cadeias_do_feed(feed, pontos)

    assert len(sobreviventes) == 3, "fonte unica: nenhuma linha pode colapsar contra outra do feed"


# --------------------------------------------------------------------------- #
# O efeito na pressão — a pressão fantasma de 49,96 e o dano a terceiros       #
# --------------------------------------------------------------------------- #
def test_a_gemea_nao_se_auto_pressiona() -> None:
    """Sem a dedup entre fontes, a academia sente a própria gêmea: `49,96` pontos do nada.

    É o recorte das 1.171 sobreviventes — território sem concorrente nenhum lido como metade da
    escala de pressão.
    """
    feed = _feed(
        [("totalpass", "r1", "bluefit", 0.0), ("wellhub", "r1", "bluefit", 3.0)]
    )
    out = calcular_pressao_por_academia(
        _observador("totalpass", "r1"), _sem_cadeias(), cadeias_do_feed=feed
    )

    assert float(out["pressao_competitiva"].iloc[0]) == 0.0, (
        "a academia se auto-pressionou atraves da propria gemea de outra fonte"
    )
    assert float(out["oferta_cadeias_do_feed"].iloc[0]) == 0.0
    assert int(out["n_concorrentes_no_raio"].iloc[0]) == 0
    assert pd.isna(out["dist_concorrente_mais_proximo_m"].iloc[0])


def test_terceiro_no_raio_conta_UM_concorrente_e_nao_dois() -> None:
    """O dano que não para no par: a auto-exclusão só protege o próprio observador.

    Quem está a 500 m das gêmeas não é nenhuma das duas, então nada o protege de contar o mesmo
    endereço duas vezes. É por aqui que `n_conc` e `oferta` se moviam para terceiros.
    """
    feed = _feed(
        [("totalpass", "r1", "bluefit", 500.0), ("wellhub", "r1", "bluefit", 503.0)]
    )
    out = calcular_pressao_por_academia(
        _observador("wellhub", "obs"), _sem_cadeias(), cadeias_do_feed=feed
    )

    assert int(out["n_concorrentes_no_raio"].iloc[0]) == 1, (
        "o mesmo endereco contou duas vezes para um terceiro"
    )
    assert int(out["n_cadeias_do_feed_no_raio"].iloc[0]) == 1

    # E a oferta é a de UMA unidade de rede, não a de duas.
    uma_so = _feed([("totalpass", "r1", "bluefit", 500.0)])
    referencia = calcular_pressao_por_academia(
        _observador("wellhub", "obs"), _sem_cadeias(), cadeias_do_feed=uma_so
    )
    assert float(out["oferta_ponderada"].iloc[0]) == pytest.approx(
        float(referencia["oferta_ponderada"].iloc[0])
    )


def test_a_decomposicao_continua_fechando_com_a_segunda_passagem() -> None:
    """O invariante do `_assert_universo_e_decomposicao` vale com gêmeas colapsadas no meio."""
    feed = _feed(
        [
            ("totalpass", "r1", "bluefit", 400.0),
            ("wellhub", "r1", "bluefit", 403.0),
            ("wellhub", "r2", "selfit", 900.0),
        ]
    )
    independentes = pd.DataFrame(
        {
            "fonte": ["wellhub"],
            "chave_snapshot": ["i1"],
            "lat": [_norte(600.0)],
            "lng": [_LNG],
        }
    )
    out = calcular_pressao_por_academia(
        _observador("wellhub", "obs"),
        _sem_cadeias(),
        independentes=independentes,
        cadeias_do_feed=feed,
    )

    assert out["universo_oferta"].iloc[0] == c.UNIVERSO_OFERTA_COM_INDEPENDENTES
    assert int(out["n_cadeias_do_feed_no_raio"].iloc[0]) == 2, "3 linhas, 1 colapsada"
    assert int(out["n_independentes_no_raio"].iloc[0]) == 1
    assert int(out["n_concorrentes_no_raio"].iloc[0]) == 3
