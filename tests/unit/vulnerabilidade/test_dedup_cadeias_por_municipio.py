"""Dedup de CADEIAS com TRAVA DE MUNICIPIO - opt-in, default intacto.

**O buraco que esta regra alcanca, medido em 2026-09-11 sobre a semana `2026-33`.** Rodando o
desempatador oficial (`mesma_unidade`) entre o feed do agregador e `concorrentes_mapeados`, dentro
da MESMA rede, sobram **98 pares** que sao a mesma unidade. Deles, **84 estao no MESMO municipio** -
e os 84 estao **acima do teto de 1.200 m** (`DIST_MAX_MESMO_NOME_M`): 72 entre 1,2 e 5 km, 12 acima
de 5 km, **ZERO abaixo**. Nao e' o mundo sendo assim; e' a regua de hoje ja' ter colapsado tudo que
cabia sob o proprio teto, e o resto ser divergencia de GEOCODIFICACAO grande demais:

    `Bodytech - Recreio Shopping` x `Bodytech Recreio Shopping`   11.373 m   Rio de Janeiro
    `Panobianco Vera Cruz`        x `VERA CRUZ`                   21.152 m   Sao Paulo
    `Greenlife Messejana`         x `GREENLIFE-MESSEJANA`          4.670 m   Fortaleza

**E por que o municipio e' OBRIGATORIO, e nao um detalhe de implementacao.** Tirar o teto sem ele
funde academias REAIS - no mesmo dado, `Selfit Itabaiana` (Itabaiana/SE) casa o nome com `ITABAIANA`
a **1.740 km**, e `Panobianco Cianortinho` (Cianorte/PR) com `CIANORTINHO` a **2.642 km**. Apagar
concorrente real e' o falso zero que a DEC-033 existe para matar. O municipio e' o que separa
duplicata de homonimo.

O que estes testes protegem:

  1. **O default e' intacto** - sem o mapa, nada muda para quem roda o pipeline hoje.
  2. **A duplicata de mesmo municipio colapsa sem teto** - e' o ganho.
  3. **O homonimo de outra praca NAO colapsa** - e' o custo evitado, e e' a regra inteira.
  4. **Municipio desconhecido de um lado nao casa** - a direcao conservadora.
  5. **Municipio nao substitui o nome** - mesma rede no mesmo municipio, nomes diferentes, seguem
     duas unidades.
  6. **A negacao por ordinal continua valendo** - `Carpina` x `Carpina 2` sao duas.
  7. **A regra e' ADITIVA** - nenhum colapso de hoje deixa de acontecer.
  8. **O ponto de entrada de PRODUCAO** (`calcular_pressao_por_academia`) mantem o default, e o
     parametro chega ate' a dedup de verdade.

READ-ONLY sobre o M1: nada aqui toca score do M1, pesos, `config.py` ou artefato oficial.
"""

from __future__ import annotations

import h3
import pandas as pd

from motor_expansao.vulnerabilidade.contrato import H3_RES_CONTRATO
from motor_expansao.vulnerabilidade.identidade import DIST_MAX_MESMO_NOME_M
from motor_expansao.vulnerabilidade.pressao_competitiva import (
    _pontos_validos_frame,
    calcular_pressao_por_academia,
    dedup_cadeias_do_feed,
)
from motor_expansao.vulnerabilidade.redes_nomeadas import chaves_com_pin_proprio

_LAT, _LNG = -22.9800, -43.4000  # Recreio dos Bandeirantes, o caso decisivo
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


def _mapa(*pares: tuple[float, str]) -> dict[str, str]:
    """`(metros ao norte, municipio)` -> mapa `hex_id_res7 -> municipio`, como o parquet do M1."""
    return {
        h3.latlng_to_cell(_norte(m), _LNG, H3_RES_CONTRATO): municipio for m, municipio in pares
    }


# --------------------------------------------------------------------------- #
# 1. O DEFAULT e' intacto - a trava contra a mudanca silenciosa                #
# --------------------------------------------------------------------------- #
def test_default_nao_colapsa_a_duplicata_distante() -> None:
    """Sem o mapa, o par real do Recreio a 11.373 m continua contando DUAS vezes.

    E' o comportamento de hoje, e ele tem de sobreviver a existencia do parametro: quem roda o
    pipeline sem pedir nada nao pode ver `pressao_competitiva` mudar sozinha.
    """
    feed = _feed([("k1", "bodytech", 11_373.0, "Bodytech - Recreio Shopping")])
    mapeados = _mapeados([("bodytech", 0.0, "Bodytech Recreio Shopping")])

    sobreviventes, mapa = dedup_cadeias_do_feed(feed, mapeados)

    assert len(sobreviventes) == 1, "o default colapsou sem o mapa de municipio"
    assert mapa[("wellhub", "k1")] == len(mapeados), "deveria ser sobrevivente, nao colapsada"


def test_mapa_vazio_e_o_mesmo_que_omitir() -> None:
    """`{}` nao e' um valor especial de ligacao - e' o desligado, como `None`."""
    feed = _feed([("k1", "bodytech", 11_373.0, "Bodytech - Recreio Shopping")])
    mapeados = _mapeados([("bodytech", 0.0, "Bodytech Recreio Shopping")])

    assert len(dedup_cadeias_do_feed(feed, mapeados, municipio_por_hex=None)[0]) == 1
    assert len(dedup_cadeias_do_feed(feed, mapeados, municipio_por_hex={})[0]) == 1


# --------------------------------------------------------------------------- #
# 2. O ganho: mesmo municipio colapsa SEM teto de distancia                    #
# --------------------------------------------------------------------------- #
def test_duplicata_de_mesmo_municipio_colapsa_muito_alem_do_teto() -> None:
    """Par real: `Bodytech - Recreio Shopping` x `Bodytech Recreio Shopping`, 11.373 m, Rio."""
    feed = _feed([("k1", "bodytech", 11_373.0, "Bodytech - Recreio Shopping")])
    mapeados = _mapeados([("bodytech", 0.0, "Bodytech Recreio Shopping")])
    mapa_mun = _mapa((11_373.0, "Rio de Janeiro"), (0.0, "Rio de Janeiro"))

    assert 11_373.0 > DIST_MAX_MESMO_NOME_M, "o caso so' prova algo acima do teto"

    sobreviventes, posicoes = dedup_cadeias_do_feed(feed, mapeados, municipio_por_hex=mapa_mun)

    assert len(sobreviventes) == 0, "a duplicata de mesmo municipio deveria ter colapsado"
    # E a auto-exclusao aponta para o ponto do funil que a absorveu - sem isso ela se
    # auto-pressionaria atraves do proprio pin.
    assert posicoes[("wellhub", "k1")] == 0


def test_par_real_de_sao_paulo_a_21km_colapsa() -> None:
    """`Panobianco Vera Cruz` x `VERA CRUZ` a 21.152 m - o par mais distante da lista."""
    feed = _feed([("k1", "panobianco", 21_152.0, "Panobianco Vera Cruz")])
    mapeados = _mapeados([("panobianco", 0.0, "VERA CRUZ")])
    mapa_mun = _mapa((21_152.0, "Sao Paulo"), (0.0, "Sao Paulo"))

    assert len(dedup_cadeias_do_feed(feed, mapeados, municipio_por_hex=mapa_mun)[0]) == 0


# --------------------------------------------------------------------------- #
# 3. O custo evitado: o homonimo de OUTRA praca nao colapsa                    #
# --------------------------------------------------------------------------- #
def test_homonimo_de_outro_municipio_NAO_colapsa() -> None:
    """`Selfit Itabaiana` x `ITABAIANA` a 1.740 km sao DUAS academias reais.

    E' a razao de existir da trava. Sem o municipio, tirar o teto apagaria este concorrente - o
    falso zero que a DEC-033 existe para matar.
    """
    feed = _feed([("k1", "selfit", 1_740_000.0, "Selfit Itabaiana")])
    mapeados = _mapeados([("selfit", 0.0, "ITABAIANA")])
    mapa_mun = _mapa((1_740_000.0, "Itabaiana"), (0.0, "Campina Grande"))

    sobreviventes, _posicoes = dedup_cadeias_do_feed(feed, mapeados, municipio_por_hex=mapa_mun)

    assert len(sobreviventes) == 1, "colapsou homonimo de outro municipio - a trava esta frouxa"


def test_homonimo_de_outro_municipio_nao_colapsa_nem_perto() -> None:
    """Municipios vizinhos, nome que casa, 3 km: a regra NOVA nao dispara.

    O par so' continua sujeito a regua ANTIGA (teto de 1.200 m), que 3 km tambem recusa.
    """
    feed = _feed([("k1", "panobianco", 3_000.0, "Panobianco Cianortinho")])
    mapeados = _mapeados([("panobianco", 0.0, "CIANORTINHO")])
    mapa_mun = _mapa((3_000.0, "Cianorte"), (0.0, "Terra Boa"))

    assert len(dedup_cadeias_do_feed(feed, mapeados, municipio_por_hex=mapa_mun)[0]) == 1


# --------------------------------------------------------------------------- #
# 4. Municipio DESCONHECIDO: a direcao conservadora                            #
# --------------------------------------------------------------------------- #
def test_municipio_ausente_de_um_lado_nao_casa() -> None:
    """Hex fora do mapa = municipio desconhecido. Afirmar identidade ali produz o `ITABAIANA`."""
    feed = _feed([("k1", "bodytech", 11_373.0, "Bodytech - Recreio Shopping")])
    mapeados = _mapeados([("bodytech", 0.0, "Bodytech Recreio Shopping")])

    so_o_feed = _mapa((11_373.0, "Rio de Janeiro"))
    so_o_cadastro = _mapa((0.0, "Rio de Janeiro"))

    assert len(dedup_cadeias_do_feed(feed, mapeados, municipio_por_hex=so_o_feed)[0]) == 1
    assert len(dedup_cadeias_do_feed(feed, mapeados, municipio_por_hex=so_o_cadastro)[0]) == 1


def test_desconhecido_NAO_casa_com_desconhecido() -> None:
    """O buraco que so' a mutacao revelou: os DOIS lados fora do mapa nao podem casar entre si.

    Com o mapa armado (nao vazio) mas sem cobrir nenhum dos dois pontos, tratar "municipio
    desconhecido" como um municipio em si faria `Selfit Itabaiana` x `ITABAIANA` colapsarem a
    1.740 km -- exatamente o homonimo que a trava existe para recusar, entrando pela porta do
    vazio. Medido por mutacao em 2026-09-11: sem este teste, o mutante sobrevivia com 15 verdes.
    """
    feed = _feed([("k1", "selfit", 1_740_000.0, "Selfit Itabaiana")])
    mapeados = _mapeados([("selfit", 0.0, "ITABAIANA")])
    # Mapa NAO vazio (a passagem esta armada), mas nenhum dos dois pontos esta nele.
    mapa_alheio = _mapa((500_000.0, "Cidade Que Nao Entra No Caso"))

    assert len(dedup_cadeias_do_feed(feed, mapeados, municipio_por_hex=mapa_alheio)[0]) == 1


# --------------------------------------------------------------------------- #
# 5-6. O municipio NAO substitui o nome                                        #
# --------------------------------------------------------------------------- #
def test_mesma_rede_mesmo_municipio_com_nomes_diferentes_seguem_duas() -> None:
    """Duas unidades da mesma rede na mesma cidade e' o caso COMUM, nao uma duplicata."""
    feed = _feed([("k1", "selfit", 6_000.0, "Selfit Barra")])
    mapeados = _mapeados([("selfit", 0.0, "Selfit Tijuca")])
    mapa_mun = _mapa((6_000.0, "Rio de Janeiro"), (0.0, "Rio de Janeiro"))

    assert len(dedup_cadeias_do_feed(feed, mapeados, municipio_por_hex=mapa_mun)[0]) == 1


def test_irma_numerada_no_mesmo_municipio_nao_colapsa() -> None:
    """`Carpina` x `Carpina 2`: a negacao por ordinal vem antes de tudo, e continua valendo."""
    feed = _feed([("k1", "smart_fit", 4_000.0, "Smart Fit Carpina 2")])
    mapeados = _mapeados([("smart_fit", 0.0, "Smart Fit Carpina")])
    mapa_mun = _mapa((4_000.0, "Carpina"), (0.0, "Carpina"))

    assert len(dedup_cadeias_do_feed(feed, mapeados, municipio_por_hex=mapa_mun)[0]) == 1


def test_rede_diferente_no_mesmo_municipio_nao_colapsa() -> None:
    """A guarda de rede nao afrouxa: municipio igual nao faz Bluefit virar Selfit."""
    feed = _feed([("k1", "bluefit", 5_000.0, "Bluefit Meier")])
    mapeados = _mapeados([("selfit", 0.0, "Selfit Meier")])
    mapa_mun = _mapa((5_000.0, "Rio de Janeiro"), (0.0, "Rio de Janeiro"))

    assert len(dedup_cadeias_do_feed(feed, mapeados, municipio_por_hex=mapa_mun)[0]) == 1


# --------------------------------------------------------------------------- #
# 7. A regra e' ADITIVA, e deterministica                                      #
# --------------------------------------------------------------------------- #
def test_o_colapso_de_hoje_por_distancia_continua_acontecendo() -> None:
    """Par a 100 m da mesma rede colapsa com e sem o mapa, e pelo MESMO representante.

    Se a passagem nova tivesse substituido as anteriores em vez de se somar a elas, o defeito que
    `DEDUP_CADEIA_FEED_M` fecha voltaria - e voltaria em silencio.
    """
    feed = _feed([("k1", "bluefit", 100.0, "Nome Que Nao Casa Com Nada")])
    mapeados = _mapeados([("bluefit", 0.0, "Outro Nome Totalmente Diverso")])
    mapa_mun = _mapa((100.0, "Rio de Janeiro"), (0.0, "Rio de Janeiro"))

    sem, mapa_sem = dedup_cadeias_do_feed(feed, mapeados)
    com, mapa_com = dedup_cadeias_do_feed(feed, mapeados, municipio_por_hex=mapa_mun)

    assert len(sem) == 0 and len(com) == 0
    assert mapa_sem == mapa_com


def test_a_passagem_por_municipio_e_deterministica_na_ordem_de_entrada() -> None:
    """Mesma entrada embaralhada -> mesmo sobrevivente. Sem isso o artefato varia por maquina."""
    feed = _feed(
        [
            ("z", "bodytech", 11_373.0, "Bodytech - Recreio Shopping"),
            ("a", "bodytech", 11_400.0, "Bodytech Recreio  Shopping"),
        ]
    )
    mapeados = _mapeados([("bodytech", 0.0, "Bodytech Recreio Shopping")])
    mapa_mun = _mapa(
        (11_373.0, "Rio de Janeiro"), (11_400.0, "Rio de Janeiro"), (0.0, "Rio de Janeiro")
    )

    direto, posicoes_direto = dedup_cadeias_do_feed(feed, mapeados, municipio_por_hex=mapa_mun)
    invertido, posicoes_invertido = dedup_cadeias_do_feed(
        feed.iloc[::-1].reset_index(drop=True), mapeados, municipio_por_hex=mapa_mun
    )

    assert direto["chave_snapshot"].tolist() == invertido["chave_snapshot"].tolist()
    assert posicoes_direto == posicoes_invertido


# --------------------------------------------------------------------------- #
# 8. O ponto de entrada de PRODUCAO                                            #
# --------------------------------------------------------------------------- #
def test_default_do_ponto_de_entrada_de_producao_nao_mudou() -> None:
    """Trava a assinatura de `calcular_pressao_por_academia`, que e' o que a producao chama.

    A trava uma camada abaixo (`dedup_cadeias_do_feed`) NAO pega este caso - medido por mutacao no
    bloco anterior: trocar o default AQUI passava a suite inteira em verde, porque nenhum teste
    referenciava o parametro novo pelo nome no ponto de entrada.
    """
    import inspect

    assert (
        inspect.signature(calcular_pressao_por_academia)
        .parameters["dedup_cadeia_feed_municipio_por_hex"]
        .default
        is None
    )
    assert inspect.signature(dedup_cadeias_do_feed).parameters["municipio_por_hex"].default is None


def test_o_mapa_chega_ate_a_dedup_pelo_ponto_de_entrada() -> None:
    """Passar o mapa em `calcular_pressao_por_academia` tem de MUDAR a oferta de cadeia.

    Sem esta prova, o parametro poderia estar declarado e nunca repassado - e a assinatura travada
    no teste acima daria verde do mesmo jeito.
    """
    academias = pd.DataFrame(
        {
            "fonte": ["wellhub"],
            "chave_snapshot": ["observador"],
            "lat": [_norte(500.0)],
            "lng": [_LNG],
        }
    )
    concorrentes = pd.DataFrame(
        {
            "rede": ["bodytech"],
            "lat": [_norte(11_000.0)],
            "lng": [_LNG],
            "nome_unidade": ["Bodytech Recreio Shopping"],
            "status_registro": ["valido"],
        }
    )
    # A unidade do feed esta a 500 m do observador, DENTRO do raio de 2 km: com a trava ela colapsa
    # contra o pin do cadastro (a 10,5 km), e a pressao que ela exercia some.
    cadeias = _feed([("k1", "bodytech", 0.0, "Bodytech - Recreio Shopping")])
    mapa_mun = _mapa((0.0, "Rio de Janeiro"), (11_000.0, "Rio de Janeiro"))

    sem = calcular_pressao_por_academia(academias, concorrentes, cadeias_do_feed=cadeias)
    com = calcular_pressao_por_academia(
        academias,
        concorrentes,
        cadeias_do_feed=cadeias,
        dedup_cadeia_feed_municipio_por_hex=mapa_mun,
    )

    assert int(sem["n_cadeias_do_feed_no_raio"].iloc[0]) == 1
    assert int(com["n_cadeias_do_feed_no_raio"].iloc[0]) == 0
    assert float(com["pressao_competitiva"].iloc[0]) < float(sem["pressao_competitiva"].iloc[0])


# --------------------------------------------------------------------------- #
# 9. A precedencia de PIN usa a mesma dedup                                    #
# --------------------------------------------------------------------------- #
def test_pin_proprio_some_quando_a_trava_colapsa_a_unidade() -> None:
    """A duplicata visivel e a oferta fantasma sao o MESMO defeito, por duas portas.

    `chaves_com_pin_proprio` e' a mesma dedup: ligar a trava so' na oferta deixaria na tela
    justamente o pin em dobro que ela colapsa.
    """
    feed = _feed([("k1", "bodytech", 11_373.0, "Bodytech - Recreio Shopping")])
    mapeados = _mapeados([("bodytech", 0.0, "Bodytech Recreio Shopping")])
    mapa_mun = _mapa((11_373.0, "Rio de Janeiro"), (0.0, "Rio de Janeiro"))

    assert chaves_com_pin_proprio(feed, mapeados) == {("wellhub", "k1")}
    assert chaves_com_pin_proprio(feed, mapeados, municipio_por_hex=mapa_mun) == set()
