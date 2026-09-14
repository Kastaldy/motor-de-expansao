"""Dedup de CADEIAS com RAIO AMPLIADO - opt-in, default intacto.

**O buraco que esta passagem alcanca, medido em 2026-09-14 sobre a semana `2026-33`.** As **851
unidades de rede do feed que HOJE sobrevivem** a dedup inteira foram cruzadas contra
`concorrentes_mapeados`: **58** tem um ponto da MESMA rede a `<= 300 m` e mesmo assim nao colapsam.
Estao TODAS na faixa 150-300 m (abaixo de 150 a passagem por DISTANCIA ja' pegou) e em NENHUMA
delas o `mesma_unidade` casa - as duas fontes escrevem o nome de formas que o matcher nao concilia:

    `CT Greenlife`                 x `CT-GREENLIFE`               286 m   Fortaleza
    `PowerFit - Industriario`      x `POWER FIT INDUSTRIARIO`     251 m
    `Premium Academia`             x `Academia Premium`           249 m
    `Marrafit - Parque Cecap`      x `Marra Fit - Unidade Cecap`  187 m
    `Evoque Academia Campo Grande` x `2939`                       181 m   (cadastro nomeia por NUMERO)

Exigir que o nome CASE mataria as 58. Por isso, nesta passagem, o nome entra como **veto** e como
**desempatador**, nunca como exigencia.

**E raio PURO nao serve, o que e' o outro lado da mesma medicao.** Dentro do proprio cadastro ha'
**33 pares da mesma rede entre 150 e 300 m que sao unidades REAIS distintas** (`Bodytech Leblon -
Gal Urquiza` x `Bodytech Leblon - Ataulfo 1100` a 259 m; `Smart Fit Club Homs` x `Paulista` a
162 m; `selfit BAIRRO-DE-FATIMA` x `BAIRRO-DE-FATIMA-II` a 275 m). Um raio de 300 m sem guarda
funde academia real - o falso zero que a DEC-033 existe para matar.

Dai as tres guardas, e a regua composta que elas produzem: **58 -> 54 colapsos**.

O que estes testes protegem:

  1. **O default e' intacto** - sem o parametro, um par a 250 m da mesma rede NAO colapsa.
  2. **O ganho** - com o raio ligado, ele colapsa; e o raio e' mesmo um raio (200 m nao alcanca).
  3. **VETO DE ORDINAL** - `X` x `X II` a 200 m nao colapsa nem com o raio ligado, e o veto filtra
     CANDIDATO a candidato, nao so' o vencedor.
  4. **DESEMPATE POR NOME, e nao por distancia** - o caso `Frei Caneca`, que e' o achado decisivo.
     Travado por MUTACAO: trocar a ordenacao para distancia primeiro faz este teste falhar.
  5. **VETO DE AMBIGUIDADE** - dois candidatos e nenhum nome que desempate: nao colapsa. Com
     candidato UNICO, colapsa - e' o custo residual declarado, e esta' pinado aqui de proposito.
  6. **Determinismo** - mesma entrada, mesma saida; empate resolvido pelo MENOR indice.
  7. **A regra e' ADITIVA** - nenhum colapso de hoje (distancia, nome) deixa de acontecer.
  8. **O ponto de entrada de PRODUCAO** mantem o default, e o parametro chega ate' a dedup.
  9. **A precedencia de PIN usa a MESMA dedup** - pin desenhado e oferta contada nao podem
     discordar.
 10. **O anel do bucket H3 cobre o raio NOVO** - reusar o `k` da passagem 1 faz a dedup deixar de
     achar o vizinho EM SILENCIO, que e' "o erro silencioso mais provavel" do docstring de
     `_k_do_bucket`. Este e' o unico teste que o pega: os pares montados na vertical continuam
     dentro do anel curto, e o mutante `k_raio = k` passava com 20 verdes.

READ-ONLY sobre o M1: nada aqui toca score do M1, pesos, `config.py` ou artefato oficial.
"""

from __future__ import annotations

import inspect
import math

import h3
import numpy as np
import pandas as pd

from motor_expansao.vulnerabilidade.contrato import (
    DEDUP_CADEIA_FEED_M,
    DEDUP_CADEIA_FEED_PISO_M,
    DEDUP_CADEIA_FEED_RAIO_AMPLIADO_M,
    DEDUP_H3_RES,
)
from motor_expansao.vulnerabilidade.identidade import DIST_MAX_MESMO_NOME_M, mesma_unidade
from motor_expansao.vulnerabilidade.pressao_competitiva import (
    _haversine_m,
    _k_do_bucket,
    _pontos_validos_frame,
    calcular_pressao_por_academia,
    dedup_cadeias_do_feed,
)
from motor_expansao.vulnerabilidade.redes_nomeadas import chaves_com_pin_proprio

_RAIO = DEDUP_CADEIA_FEED_RAIO_AMPLIADO_M
_LAT, _LNG = -3.7500, -38.5200  # Fortaleza, onde esta' o par do `CT Greenlife`
_GRAU_LAT_M = 111_320.0


def _norte(metros: float) -> float:
    return _LAT + metros / _GRAU_LAT_M


def _feed(linhas: list[tuple[str, str, float, str]]) -> pd.DataFrame:
    """`(chave, rede, metros ao norte, nome)` -> frame do feed do agregador."""
    return pd.DataFrame(
        {
            "fonte": ["wellhub"] * len(linhas),
            "chave_snapshot": [k for k, _, _, _ in linhas],
            "lat": [_norte(m) for _, _, m, _ in linhas],
            "lng": [_LNG] * len(linhas),
            "rede": [r for _, r, _, _ in linhas],
            "nome": [n for _, _, _, n in linhas],
        }
    )


def _mapeados(linhas: list[tuple[str, float, str]]) -> pd.DataFrame:
    """`(rede, metros ao norte, nome_unidade)` -> o insumo `concorrentes_mapeados` ja' filtrado."""
    return _pontos_validos_frame(
        pd.DataFrame(
            {
                "rede": [r for r, _, _ in linhas],
                "lat": [_norte(m) for _, m, _ in linhas],
                "lng": [_LNG] * len(linhas),
                "nome_unidade": [n for _, _, n in linhas],
                "status_registro": ["valido"] * len(linhas),
            }
        )
    )


# --------------------------------------------------------------------------- #
# 1. O DEFAULT e' intacto - a trava contra a mudanca silenciosa                #
# --------------------------------------------------------------------------- #
def test_default_nao_colapsa_o_par_a_250_m() -> None:
    """Par real `PowerFit - Industriario` x `POWER FIT INDUSTRIARIO`, 251 m: hoje sao DOIS.

    E' o comportamento de hoje, e ele tem de sobreviver a existencia do parametro: quem roda o
    pipeline sem pedir nada nao pode ver `pressao_competitiva` mudar sozinha.
    """
    feed = _feed([("k1", "power_fit", 251.0, "PowerFit - Industriario")])
    mapeados = _mapeados([("power_fit", 0.0, "POWER FIT INDUSTRIARIO")])

    # O caso so' prova algo se as DUAS reguas de hoje recusarem o par.
    assert 251.0 > DEDUP_CADEIA_FEED_M, "abaixo de 150 m a passagem por DISTANCIA ja' pegaria"
    assert not mesma_unidade(
        "PowerFit - Industriario", "POWER FIT INDUSTRIARIO", "power_fit"
    ), "se o matcher casasse, quem colapsaria seria a passagem por NOME"

    sobreviventes, posicoes = dedup_cadeias_do_feed(feed, mapeados)

    assert len(sobreviventes) == 1, "o default colapsou sem o raio ampliado"
    assert posicoes[("wellhub", "k1")] == len(mapeados), "deveria ser sobrevivente, nao colapsada"


def test_raio_none_explicito_e_o_mesmo_que_omitir() -> None:
    """`None` nao e' um valor especial - e' o desligado, e e' o default."""
    feed = _feed([("k1", "power_fit", 251.0, "PowerFit - Industriario")])
    mapeados = _mapeados([("power_fit", 0.0, "POWER FIT INDUSTRIARIO")])

    assert len(dedup_cadeias_do_feed(feed, mapeados, raio_ampliado_m=None)[0]) == 1


# --------------------------------------------------------------------------- #
# 2. O ganho: com o raio ligado, o par colapsa                                 #
# --------------------------------------------------------------------------- #
def test_raio_ligado_colapsa_o_par_a_250_m() -> None:
    """O mesmo par de cima, com o raio ligado, vira UM - e a auto-exclusao aponta para o pin."""
    feed = _feed([("k1", "power_fit", 251.0, "PowerFit - Industriario")])
    mapeados = _mapeados([("power_fit", 0.0, "POWER FIT INDUSTRIARIO")])

    sobreviventes, posicoes = dedup_cadeias_do_feed(feed, mapeados, raio_ampliado_m=_RAIO)

    assert len(sobreviventes) == 0, "o raio ampliado nao colapsou o par de 251 m"
    # Sem isto ela se auto-pressionaria atraves do proprio pin do funil (`sat(1,0)` = 50 pontos).
    assert posicoes[("wellhub", "k1")] == 0


def test_par_real_de_fortaleza_colapsa() -> None:
    """`CT Greenlife` x `CT-GREENLIFE` a 286 m: similaridade `0,0` e candidato UNICO.

    E' o regime mais comum dos 58 - `ct` e' ruido e `greenlife` e' o slug da rede, entao nao sobra
    discriminante NENHUM dos dois lados. O nome nao afirma nada aqui; quem afirma e' o raio, e a
    guarda que sobra e' o veto de ordinal.
    """
    feed = _feed([("k1", "greenlife", 286.0, "CT Greenlife")])
    mapeados = _mapeados([("greenlife", 0.0, "CT-GREENLIFE")])

    assert len(dedup_cadeias_do_feed(feed, mapeados, raio_ampliado_m=_RAIO)[0]) == 0


def test_o_raio_e_mesmo_um_raio() -> None:
    """Com `raio_ampliado_m = 200`, o par de 251 m nao e' alcancado. O parametro e' o alcance."""
    feed = _feed([("k1", "power_fit", 251.0, "PowerFit - Industriario")])
    mapeados = _mapeados([("power_fit", 0.0, "POWER FIT INDUSTRIARIO")])

    assert len(dedup_cadeias_do_feed(feed, mapeados, raio_ampliado_m=200.0)[0]) == 1
    assert len(dedup_cadeias_do_feed(feed, mapeados, raio_ampliado_m=_RAIO)[0]) == 0


def test_fora_do_raio_nao_colapsa_nem_com_o_raio_ligado() -> None:
    """500 m com nome que o matcher recusa: nem a regua antiga nem a nova alcancam."""
    feed = _feed([("k1", "power_fit", 500.0, "PowerFit - Industriario")])
    mapeados = _mapeados([("power_fit", 0.0, "POWER FIT INDUSTRIARIO")])

    assert len(dedup_cadeias_do_feed(feed, mapeados, raio_ampliado_m=_RAIO)[0]) == 1


def test_rede_diferente_no_raio_nao_colapsa() -> None:
    """A guarda de rede nao afrouxa: 250 m nao faz Bluefit virar Selfit.

    E' o mesmo custo que a coluna `300 m PURO` da tabela de `DEDUP_CADEIA_FEED_M` mede - la', 91
    dos 143 colapsos extras eram contra OUTRA rede.
    """
    feed = _feed([("k1", "bluefit", 250.0, "Bluefit Aldeota")])
    mapeados = _mapeados([("selfit", 0.0, "Selfit Aldeota")])

    assert len(dedup_cadeias_do_feed(feed, mapeados, raio_ampliado_m=_RAIO)[0]) == 1


# --------------------------------------------------------------------------- #
# 2b. O ANEL do bucket H3 cobre o raio NOVO                                    #
# --------------------------------------------------------------------------- #
def _distancia(lat_a: float, lng_a: float, lat_b: float, lng_b: float) -> float:
    return float(
        _haversine_m(
            np.array([lat_a]), np.array([lng_a]), np.array([lat_b]), np.array([lng_b])
        )[0]
    )


def _ponto_fora_do_anel_da_passagem_1(lat_base: float) -> tuple[float, float] | None:
    """Ponto entre 150 e 300 m da base cuja CELULA cai fora do `grid_disk` da passagem 1.

    Busca por AZIMUTE em vez de cravar coordenada, no molde de `test_dedup_independentes_bucket`:
    em que celula um ponto cai depende de onde ele pousa na grade H3, e um par que hoje esta fora
    do anel curto poderia deixar de estar com outra versao do `h3` -- o teste ficaria verde sem
    provar nada.
    """
    celula_base = h3.latlng_to_cell(lat_base, _LNG, DEDUP_H3_RES)
    # O anel da passagem 1 sai do limiar DELA (`max(distancia_m, piso_m)` = 150 m), que e' o anel
    # que o mutante `k_raio = k` reusaria.
    anel_curto = set(
        h3.grid_disk(
            celula_base, _k_do_bucket(max(DEDUP_CADEIA_FEED_M, DEDUP_CADEIA_FEED_PISO_M))
        )
    )
    for graus in range(0, 360, 3):
        radianos = math.radians(graus)
        for alvo in (299.0, 290.0, 270.0, 240.0, 210.0, 180.0):
            lat = lat_base + (alvo * math.cos(radianos)) / _GRAU_LAT_M
            lng = _LNG + (alvo * math.sin(radianos)) / (
                _GRAU_LAT_M * math.cos(math.radians(lat_base))
            )
            if h3.latlng_to_cell(lat, lng, DEDUP_H3_RES) in anel_curto:
                continue
            d = _distancia(lat_base, _LNG, lat, lng)
            if DEDUP_CADEIA_FEED_M < d <= _RAIO:
                return lat, lng
    return None


def _base_que_exercita_o_anel() -> tuple[float, float, float]:
    """`(lat_base, lat_par, lng_par)` da primeira base com par FORA do anel da passagem 1."""
    for passo in range(400):
        lat_base = _LAT + passo * 0.00002
        achado = _ponto_fora_do_anel_da_passagem_1(lat_base)
        if achado is not None:
            return lat_base, achado[0], achado[1]
    raise AssertionError("nenhuma base produziu par fora do anel curto - revisar a fixture")


def test_o_k_do_anel_sai_do_raio_novo_e_nao_do_antigo() -> None:
    """Guarda barata contra a regressao para o anel da passagem 1 (ou para um literal)."""
    assert _k_do_bucket(_RAIO) > _k_do_bucket(DEDUP_CADEIA_FEED_M), (
        "o anel de 150 m nao cobre 300 m: o `k` tem de sair do raio NOVO"
    )
    aresta = float(h3.average_hexagon_edge_length(DEDUP_H3_RES, unit="m"))
    assert 28.0 < aresta < 29.0, f"aresta media mudou ({aresta:.2f} m); revisar os comentarios"


def test_par_fora_do_anel_da_passagem_1_ainda_colapsa() -> None:
    """O caso concreto que um `k` sub-coberto perderia -- e perderia EM SILENCIO.

    Uma dedup que nao varre longe o bastante devolve "nenhum colapso", que e' exatamente o que uma
    dedup correta devolve quando nao ha' duplicata: o defeito e' indistinguivel do caso certo, e so'
    um par montado FORA do anel curto o separa. Medido por mutacao em 2026-09-14: com
    `k_raio = k`, os 20 testes anteriores deste arquivo ficavam VERDES; este falha.
    """
    lat_base, lat_par, lng_par = _base_que_exercita_o_anel()

    feed = pd.DataFrame(
        {
            "fonte": ["wellhub"],
            "chave_snapshot": ["k1"],
            "lat": [lat_base],
            "lng": [_LNG],
            "rede": ["power_fit"],
            "nome": ["PowerFit - Industriario"],
        }
    )
    mapeados = _pontos_validos_frame(
        pd.DataFrame(
            {
                "rede": ["power_fit"],
                "lat": [lat_par],
                "lng": [lng_par],
                "nome_unidade": ["POWER FIT INDUSTRIARIO"],
                "status_registro": ["valido"],
            }
        )
    )

    assert len(dedup_cadeias_do_feed(feed, mapeados)[0]) == 1, "o default nao pode alcancar o par"
    assert len(dedup_cadeias_do_feed(feed, mapeados, raio_ampliado_m=_RAIO)[0]) == 0


# --------------------------------------------------------------------------- #
# 3. VETO DE ORDINAL                                                           #
# --------------------------------------------------------------------------- #
def test_veto_de_ordinal_nao_colapsa_a_irma_numerada() -> None:
    """`CONTORNO DO CORPO - CASTELO 3` x `CASTELO-II` a 200 m sao DUAS unidades reais.

    E' um dos 3 dos 58 que este veto derruba, e e' a regra de NEGACAO de `identidade.py`: ordinais
    diferentes = unidades diferentes, por mais parecido que seja o resto.
    """
    feed = _feed([("k1", "contorno_do_corpo", 200.0, "CONTORNO DO CORPO - CASTELO 3")])
    mapeados = _mapeados([("contorno_do_corpo", 0.0, "CASTELO-II")])

    assert len(dedup_cadeias_do_feed(feed, mapeados, raio_ampliado_m=_RAIO)[0]) == 1


def test_o_veto_de_ordinal_filtra_candidato_a_candidato() -> None:
    """A irma numerada MAIS PROXIMA nao pode roubar o colapso da unidade certa.

    Ordinal diferente e' negacao de IDENTIDADE, entao aquele ponto nao e' candidato - ele sai da
    lista, e o proximo do raio ganha. Se o veto julgasse so' o VENCEDOR, a `... II` a 200 m (mesma
    similaridade, menor distancia) venceria a ordenacao e derrubaria o par inteiro em silencio.
    """
    feed = _feed([("k1", "power_fit", 0.0, "PowerFit - Industriario")])
    mapeados = _mapeados(
        [
            ("power_fit", 200.0, "POWER FIT INDUSTRIARIO II"),  # ordinal 2 -> vetada
            ("power_fit", 280.0, "POWER FIT INDUSTRIARIO"),  # a certa, mais LONGE
        ]
    )

    sobreviventes, posicoes = dedup_cadeias_do_feed(feed, mapeados, raio_ampliado_m=_RAIO)

    assert len(sobreviventes) == 0, "o veto de ordinal derrubou o par inteiro, e nao o candidato"
    assert posicoes[("wellhub", "k1")] == 1, "colapsou contra a irma numerada, que e' outra unidade"


# --------------------------------------------------------------------------- #
# 4. DESEMPATE POR NOME, e nao por distancia - o achado decisivo               #
# --------------------------------------------------------------------------- #
def test_desempate_e_pelo_nome_e_nao_pela_menor_distancia() -> None:
    """`BlueFit 24h - Frei Caneca`: DOIS candidatos, e o mais PROXIMO e' o errado.

    O cadastro tem `Frei Caneca` e `Consolacao` a 269 m um do outro. Pelo mais proximo, a unidade
    casaria com o `Consolacao` (171 m) - falso positivo SILENCIOSO, que some no agregado. Ordenando
    por `similaridade_nome` DECRESCENTE e so' depois por distancia, ela casa com o `Frei Caneca`
    (223 m), que e' o certo.

    **Provado por MUTACAO em 2026-09-14:** trocando a chave de ordenacao de
    `(-similaridade, d, indice)` para `(d, -similaridade, indice)` em `dedup_cadeias_do_feed`, este
    teste falha com `posicoes[...] == 0` (o `Consolacao`). Restaurada a ordenacao, volta a verde.
    """
    feed = _feed([("k1", "bluefit", 0.0, "BlueFit 24h - Frei Caneca")])
    mapeados = _mapeados(
        [
            ("bluefit", 171.0, "Consolacao"),  # indice 0 - o mais PROXIMO, e o errado
            ("bluefit", 223.0, "Frei Caneca"),  # indice 1 - o certo, e o mais LONGE
        ]
    )

    # O caso so' prova algo se a passagem por NOME recusar os dois: com `mesma_unidade` casando,
    # quem colapsaria seria ela, e a ordenacao daqui nunca seria exercida.
    assert not mesma_unidade("BlueFit 24h - Frei Caneca", "Frei Caneca", "bluefit")
    assert not mesma_unidade("BlueFit 24h - Frei Caneca", "Consolacao", "bluefit")

    sobreviventes, posicoes = dedup_cadeias_do_feed(feed, mapeados, raio_ampliado_m=_RAIO)

    assert len(sobreviventes) == 0
    assert posicoes[("wellhub", "k1")] == 1, "casou com o mais PROXIMO em vez do de mesmo NOME"


# --------------------------------------------------------------------------- #
# 5. VETO DE AMBIGUIDADE, e o custo residual que ele NAO cobre                 #
# --------------------------------------------------------------------------- #
def test_veto_de_ambiguidade_com_dois_candidatos_sem_nome_em_comum() -> None:
    """`Contorno do Corpo Centro` x `CENTRO`: 2 candidatos, similaridade `0,0` nos dois.

    Nao ha' nome que desempate, e escolher ali seria escolher por DISTANCIA - exatamente o modo de
    falha do `Frei Caneca`. Falso negativo conservador, de proposito. E' 1 dos 58.
    """
    feed = _feed([("k1", "contorno_do_corpo", 0.0, "Contorno do Corpo Centro")])
    mapeados = _mapeados(
        [
            ("contorno_do_corpo", 180.0, "CENTRO"),
            ("contorno_do_corpo", 260.0, "BOA-VIAGEM"),
        ]
    )

    assert len(dedup_cadeias_do_feed(feed, mapeados, raio_ampliado_m=_RAIO)[0]) == 1


def test_candidato_unico_com_similaridade_zero_ainda_colapsa() -> None:
    """O CUSTO RESIDUAL, pinado de proposito: com UM candidato, similaridade `0,0` colapsa.

    E' o regime em que cai `Selfit - Tamarineira` x `CASA-AMARELA` (235,5 m), um dos ~4 pares
    DISTINTOS da inspecao manual dos 58. Fechar este regime zeraria o ganho inteiro - o
    `CT Greenlife` cai nele tambem -, entao o custo e' declarado em vez de evitado. Se alguem
    "consertar" isso um dia, que seja com a medicao na mao e nao em silencio.
    """
    feed = _feed([("k1", "selfit", 235.5, "Selfit - Tamarineira")])
    mapeados = _mapeados([("selfit", 0.0, "CASA-AMARELA")])

    assert len(dedup_cadeias_do_feed(feed, mapeados, raio_ampliado_m=_RAIO)[0]) == 0


def test_ambiguidade_com_nome_que_discrimina_nao_veta() -> None:
    """Dois candidatos, mas UM deles tem nome em comum: o veto nao dispara e o nome decide."""
    feed = _feed([("k1", "power_fit", 0.0, "PowerFit - Industriario")])
    mapeados = _mapeados(
        [
            ("power_fit", 180.0, "BOA-VIAGEM"),  # similaridade 0,0
            ("power_fit", 260.0, "POWER FIT INDUSTRIARIO"),  # 0,5 - e' esta
        ]
    )

    sobreviventes, posicoes = dedup_cadeias_do_feed(feed, mapeados, raio_ampliado_m=_RAIO)

    assert len(sobreviventes) == 0
    assert posicoes[("wellhub", "k1")] == 1


# --------------------------------------------------------------------------- #
# 6. Determinismo                                                              #
# --------------------------------------------------------------------------- #
def test_mesma_entrada_mesma_saida_em_duas_chamadas() -> None:
    """Sem isto o artefato varia por maquina - e ninguem descobre olhando o numero."""
    feed = _feed(
        [
            ("z", "power_fit", 251.0, "PowerFit - Industriario"),
            ("a", "bluefit", 0.0, "BlueFit 24h - Frei Caneca"),
            ("m", "greenlife", 700.0, "CT Greenlife"),
        ]
    )
    mapeados = _mapeados(
        [
            ("power_fit", 0.0, "POWER FIT INDUSTRIARIO"),
            ("bluefit", 171.0, "Consolacao"),
            ("bluefit", 223.0, "Frei Caneca"),
        ]
    )

    primeira, posicoes_primeira = dedup_cadeias_do_feed(feed, mapeados, raio_ampliado_m=_RAIO)
    segunda, posicoes_segunda = dedup_cadeias_do_feed(feed, mapeados, raio_ampliado_m=_RAIO)

    assert primeira["chave_snapshot"].tolist() == segunda["chave_snapshot"].tolist()
    assert posicoes_primeira == posicoes_segunda


def test_empate_perfeito_fica_com_o_MENOR_indice() -> None:
    """Mesmo nome e mesma distancia nos dois candidatos: o indice fecha o empate.

    E' a mesma escolha das passagens antigas, e ela existe para o artefato nao depender da ordem em
    que o `grid_disk` devolve as celulas.
    """
    feed = _feed([("k1", "power_fit", 0.0, "PowerFit - Industriario")])
    mapeados = _mapeados(
        [
            ("power_fit", 260.0, "POWER FIT INDUSTRIARIO"),
            ("power_fit", 260.0, "POWER FIT INDUSTRIARIO"),
        ]
    )

    _sobreviventes, posicoes = dedup_cadeias_do_feed(feed, mapeados, raio_ampliado_m=_RAIO)

    assert posicoes[("wellhub", "k1")] == 0


# --------------------------------------------------------------------------- #
# 7. A regra e' ADITIVA                                                        #
# --------------------------------------------------------------------------- #
def test_o_colapso_de_hoje_por_distancia_continua_acontecendo() -> None:
    """Par a 100 m da mesma rede colapsa com e sem o raio, e pelo MESMO representante."""
    feed = _feed([("k1", "bluefit", 100.0, "Nome Que Nao Casa Com Nada")])
    mapeados = _mapeados([("bluefit", 0.0, "Outro Nome Totalmente Diverso")])

    sem, posicoes_sem = dedup_cadeias_do_feed(feed, mapeados)
    com, posicoes_com = dedup_cadeias_do_feed(feed, mapeados, raio_ampliado_m=_RAIO)

    assert len(sem) == 0 and len(com) == 0
    assert posicoes_sem == posicoes_com


def test_o_colapso_de_hoje_por_nome_alem_do_raio_continua_acontecendo() -> None:
    """`Panobianco Extrema` x `EXTREMA` a 900 m: fora do raio novo, dentro da regua do NOME.

    Se a passagem nova tivesse substituido as anteriores em vez de se somar a elas, este colapso -
    que a passagem por nome faz ate' 1.200 m - sumiria, e sumiria em silencio.
    """
    feed = _feed([("k1", "panobianco", 900.0, "Panobianco Extrema")])
    mapeados = _mapeados([("panobianco", 0.0, "EXTREMA")])

    assert 900.0 > _RAIO and 900.0 < DIST_MAX_MESMO_NOME_M, "o caso so' prova algo nessa faixa"

    sem, posicoes_sem = dedup_cadeias_do_feed(feed, mapeados)
    com, posicoes_com = dedup_cadeias_do_feed(feed, mapeados, raio_ampliado_m=_RAIO)

    assert len(sem) == 0 and len(com) == 0
    assert posicoes_sem == posicoes_com


# --------------------------------------------------------------------------- #
# 8. O ponto de entrada de PRODUCAO                                            #
# --------------------------------------------------------------------------- #
def test_default_do_ponto_de_entrada_de_producao_nao_mudou() -> None:
    """Trava a assinatura de `calcular_pressao_por_academia`, que e' o que a producao chama.

    A trava uma camada abaixo (`dedup_cadeias_do_feed`) NAO pega este caso: trocar o default AQUI
    passa a suite inteira em verde se nenhum teste referenciar o parametro pelo nome no ponto de
    entrada - medido por mutacao no bloco da trava de municipio.
    """
    assert (
        inspect.signature(calcular_pressao_por_academia)
        .parameters["dedup_cadeia_feed_raio_ampliado_m"]
        .default
        is None
    )
    assert inspect.signature(dedup_cadeias_do_feed).parameters["raio_ampliado_m"].default is None


def test_o_raio_chega_ate_a_dedup_pelo_ponto_de_entrada() -> None:
    """Passar o raio em `calcular_pressao_por_academia` tem de MUDAR a oferta de cadeia.

    Sem esta prova, o parametro poderia estar declarado e nunca repassado - e a assinatura travada
    no teste acima daria verde do mesmo jeito.
    """
    academias = pd.DataFrame(
        {
            "fonte": ["wellhub"],
            "chave_snapshot": ["observador"],
            "lat": [_norte(1_000.0)],
            "lng": [_LNG],
        }
    )
    concorrentes = pd.DataFrame(
        {
            "rede": ["power_fit"],
            "lat": [_norte(0.0)],
            "lng": [_LNG],
            "nome_unidade": ["POWER FIT INDUSTRIARIO"],
            "status_registro": ["valido"],
        }
    )
    # A unidade do feed esta' a 749 m do observador, DENTRO do raio de 2 km da pressao: com o raio
    # ampliado ligado ela colapsa contra o pin do cadastro (a 251 m dela) e deixa de pressionar.
    cadeias = _feed([("k1", "power_fit", 251.0, "PowerFit - Industriario")])

    sem = calcular_pressao_por_academia(academias, concorrentes, cadeias_do_feed=cadeias)
    com = calcular_pressao_por_academia(
        academias,
        concorrentes,
        cadeias_do_feed=cadeias,
        dedup_cadeia_feed_raio_ampliado_m=_RAIO,
    )

    assert int(sem["n_cadeias_do_feed_no_raio"].iloc[0]) == 1
    assert int(com["n_cadeias_do_feed_no_raio"].iloc[0]) == 0
    assert float(com["pressao_competitiva"].iloc[0]) < float(sem["pressao_competitiva"].iloc[0])


# --------------------------------------------------------------------------- #
# 9. A precedencia de PIN usa a mesma dedup                                    #
# --------------------------------------------------------------------------- #
def test_pin_proprio_some_quando_o_raio_colapsa_a_unidade() -> None:
    """A duplicata visivel e a oferta fantasma sao o MESMO defeito, por duas portas.

    `chaves_com_pin_proprio` e' a mesma dedup: ligar o raio so' na oferta deixaria na tela o pin
    proprio de uma unidade cuja oferta acabou de ser contada no pin do funil.
    """
    feed = _feed([("k1", "power_fit", 251.0, "PowerFit - Industriario")])
    mapeados = _mapeados([("power_fit", 0.0, "POWER FIT INDUSTRIARIO")])

    assert chaves_com_pin_proprio(feed, mapeados) == {("wellhub", "k1")}
    assert chaves_com_pin_proprio(feed, mapeados, raio_ampliado_m=_RAIO) == set()
