"""BLK-MA-17-FU4: a dedup de cadeias passa a casar por NOME, não só por distância.

**O defeito, medido no insumo real em 2026-08-18.** Entre 150 m (o limiar antigo) e 1 km havia
**438 pares** de mesma rede entre o feed e `concorrentes_mapeados`, e **407 deles (92,9%) tinham o
nome batendo** — a mesma academia contada duas vezes. Não era defeito latente como o FU1/FU2: essas
duplicatas estavam **inflando a pressão competitiva no dado de produção**.

Efeito da correção, medido: **320** unidades colapsam a mais (sobreviventes `1.171 -> 851`), a
pressão média cai de `62,775` para `62,479`, **2.829 de 19.329 academias (14,6%)** mudam de valor
com delta máximo de `-20,82` pts, e o `Spearman` contra a régua anterior é `0,9980718`.

O que estes testes protegem:

  1. **A duplicata longe casa** — é o ganho, e ele não existe sem o nome.
  2. **A irmã numerada não casa** — é o custo que a regra de ordinal evita.
  3. **O limite de distância continua valendo** — nome igual a 5 km é outra unidade.
  4. **Sem nome no insumo, nada muda** — a passagem é opcional e degrada para o comportamento
     anterior, que é o que mantém compatível quem chama sem a coluna.

READ-ONLY sobre o M1.
"""

from __future__ import annotations

import pandas as pd

from motor_expansao.vulnerabilidade.identidade import DIST_MAX_MESMO_NOME_M
from motor_expansao.vulnerabilidade.pressao_competitiva import dedup_cadeias_do_feed

_LAT, _LNG = -23.5500, -46.6300
_GRAU_LAT_M = 111_320.0


def _norte(metros: float) -> float:
    return _LAT + metros / _GRAU_LAT_M


def _feed(linhas: list[tuple[str, str, float, str]]) -> pd.DataFrame:
    """`(chave, rede, metros ao norte, nome)`."""
    return pd.DataFrame(
        {
            "fonte": ["wellhub"] * len(linhas),
            "chave_snapshot": [c for c, _, _, _ in linhas],
            "rede": [r for _, r, _, _ in linhas],
            "lat": [_norte(m) for _, _, m, _ in linhas],
            "lng": [_LNG] * len(linhas),
            "nome": [n for _, _, _, n in linhas],
        }
    )


def _mapeados(linhas: list[tuple[str, float, str]]) -> pd.DataFrame:
    """`(rede, metros ao norte, nome)` — já no formato de `_pontos_validos_frame`."""
    return pd.DataFrame(
        {
            "rede": [r for r, _, _ in linhas],
            "lat": [_norte(m) for _, m, _ in linhas],
            "lng": [_LNG] * len(linhas),
            "nome": [n for _, _, n in linhas],
        }
    )


# --------------------------------------------------------------------------- #
# 1. O ganho: duplicata que a distância não alcançava                          #
# --------------------------------------------------------------------------- #
def test_duplicata_a_940m_colapsa_pelo_nome() -> None:
    """O par real mais extremo medido: `SKYFIT ACADEMIA - BACABAL` x `Bacabal (MA)`.

    A 940 m, seis vezes o limiar de distância. Sem a passagem por nome, esta unidade entrava na
    oferta como se fosse uma segunda academia.
    """
    feed = _feed([("k1", "skyfit", 940.0, "SKYFIT ACADEMIA - BACABAL")])
    mapeados = _mapeados([("skyfit", 0.0, "Bacabal (MA)")])
    sobreviventes, mapa = dedup_cadeias_do_feed(feed, mapeados)

    assert len(sobreviventes) == 0, "a duplicata a 940 m tinha de colapsar pelo nome"
    assert mapa[("wellhub", "k1")] == 0, "o representante e' o ponto MAPEADO"


def test_o_representante_e_o_mais_proximo_entre_os_que_casam() -> None:
    """Com dois pins da mesma rede e nome compatível, vence o mais perto — determinismo."""
    feed = _feed([("k1", "panobianco", 0.0, "Panobianco Extrema")])
    mapeados = _mapeados(
        [("panobianco", 900.0, "EXTREMA"), ("panobianco", 300.0, "Extrema Unidade")]
    )
    _sobreviventes, mapa = dedup_cadeias_do_feed(feed, mapeados)
    assert mapa[("wellhub", "k1")] == 1, "colapsou no mais distante"


# --------------------------------------------------------------------------- #
# 2. O custo evitado: irmã numerada                                            #
# --------------------------------------------------------------------------- #
def test_unidade_numerada_da_mesma_rede_NAO_colapsa() -> None:
    """`Carpina` e `Carpina 2` a 582 m são DUAS academias.

    Sem a regra de ordinal, o discriminante idêntico (Jaccard `1,00`) as colapsaria e o mapa
    perderia um concorrente real — o modo de falha medido em 31 pares.
    """
    feed = _feed([("k1", "match_fit", 582.0, "Match Fit Carpina 2")])
    mapeados = _mapeados([("match_fit", 0.0, "Carpina")])
    sobreviventes, mapa = dedup_cadeias_do_feed(feed, mapeados)

    assert len(sobreviventes) == 1, "a irma numerada foi apagada"
    assert mapa[("wellhub", "k1")] == len(mapeados), "deveria ter posicao propria (sobrevivente)"


def test_bairro_diferente_na_mesma_cidade_NAO_colapsa() -> None:
    """`AD3 - Tubarão - Humaitá` x `- Premium`: Jaccard `0,50`, abaixo do limiar."""
    feed = _feed([("k1", "ad3", 600.0, "AD3 - Tubarão - Humaitá")])
    mapeados = _mapeados([("ad3", 0.0, "AD3 - Tubarão - Premium")])
    sobreviventes, _mapa = dedup_cadeias_do_feed(feed, mapeados)
    assert len(sobreviventes) == 1


# --------------------------------------------------------------------------- #
# 3. A distância continua sendo um teto                                        #
# --------------------------------------------------------------------------- #
def test_nome_identico_alem_do_teto_NAO_colapsa() -> None:
    """O nome não vale a qualquer distância: além de `DIST_MAX_MESMO_NOME_M` são outras unidades.

    Sem este teto, duas `Smart Fit Centro` em cidades diferentes colapsariam uma na outra.
    """
    longe = float(DIST_MAX_MESMO_NOME_M) + 800.0
    feed = _feed([("k1", "skyfit", longe, "SkyFit Bacabal")])
    mapeados = _mapeados([("skyfit", 0.0, "Bacabal (MA)")])
    sobreviventes, _mapa = dedup_cadeias_do_feed(feed, mapeados)
    assert len(sobreviventes) == 1, "nome igual a 2 km nao pode colapsar"


def test_rede_diferente_com_nome_igual_NAO_colapsa() -> None:
    """A passagem por nome só compara dentro da MESMA rede."""
    feed = _feed([("k1", "bluefit", 400.0, "Bluefit Jardim Paulista")])
    mapeados = _mapeados([("selfit", 0.0, "Selfit Jardim Paulista")])
    sobreviventes, _mapa = dedup_cadeias_do_feed(feed, mapeados)
    assert len(sobreviventes) == 1


# --------------------------------------------------------------------------- #
# 4. Degradação: sem nome, comportamento anterior                              #
# --------------------------------------------------------------------------- #
def test_sem_coluna_de_nome_a_passagem_nao_roda() -> None:
    """Compatibilidade: quem chama sem `nome` recebe exatamente o resultado de antes do FU4."""
    feed = _feed([("k1", "skyfit", 940.0, "SKYFIT ACADEMIA - BACABAL")]).drop(columns=["nome"])
    mapeados = _mapeados([("skyfit", 0.0, "Bacabal (MA)")])
    sobreviventes, _mapa = dedup_cadeias_do_feed(feed, mapeados)
    assert len(sobreviventes) == 1, "sem nome, a duplicata a 940 m sobrevive — como antes"


def test_nome_vazio_no_insumo_mapeado_nao_quebra() -> None:
    """Insumo antigo, sem nome do lado mapeado: a passagem simplesmente não dispara."""
    feed = _feed([("k1", "skyfit", 940.0, "SKYFIT ACADEMIA - BACABAL")])
    mapeados = _mapeados([("skyfit", 0.0, "")])
    sobreviventes, _mapa = dedup_cadeias_do_feed(feed, mapeados)
    assert len(sobreviventes) == 1


# --------------------------------------------------------------------------- #
# A ordem das passagens                                                        #
# --------------------------------------------------------------------------- #
def test_a_distancia_curta_tem_precedencia_sobre_o_nome() -> None:
    """Um pin a 10 m colapsa pelo piso, sem consultar nome — a passagem barata vem primeiro."""
    feed = _feed([("k1", "skyfit", 10.0, "SkyFit Qualquer Coisa")])
    mapeados = _mapeados([("outra_rede", 0.0, "Nome Totalmente Diferente")])
    sobreviventes, mapa = dedup_cadeias_do_feed(feed, mapeados)
    assert len(sobreviventes) == 0, "o piso de 50 m deveria ter colapsado"
    assert mapa[("wellhub", "k1")] == 0
