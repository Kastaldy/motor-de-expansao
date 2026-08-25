"""BLK-MA-17-FU3: o caminho de PRODUÇÃO da pressão passa a ser exercitado.

`_pressao_por_academia` é o único chamador de `calcular_pressao_por_academia` em código de
produção, e até este bloco **nenhum teste a executava** — as duas ocorrências em `tests/` só
inspecionavam `inspect.signature(...)`. Consequência medida na revisão adversarial de 2026-08-17:

  1. **A partição independente/cadeia podia ser INVERTIDA** e 448 testes seguiam verdes. No insumo
     real isso movia **94,5%** das linhas (pressão média `62,775 -> 71,371`, máximo `+49,76` pts)
     sem deixar nenhum tell no artefato: `universo_oferta` sai idêntico nos dois casos, e
     `calcular_pressao_por_academia` nunca valida o CONTEÚDO dos frames que recebe.
  2. **A ordem do concat `[pontos_mapeados ; sobreviventes]`** podia ser invertida e 437 testes
     seguiam verdes, devolvendo `pressao = 50,0` de auto-pressão — os exatos 50 pontos que a
     DEC-034 diz ter fechado, e apagando o concorrente real a 1,5 km.

Por que os testes do BLK-MA-17 não pegam o (2): os dois de auto-exclusão degeneram o caso —
`test_5` roda com `offset = 0` e `test_6` com zero sobreviventes, então em nenhum deles existe
simultaneamente ponto mapeado E sobrevivente. E o `test_14b` filtra explicitamente o outro ramo do
dicionário (`pos < offset`). O arranjo que faltava é justamente o de PRODUÇÃO: ponto mapeado **e**
sobrevivente **e** o sobrevivente sendo a própria academia observada.

READ-ONLY sobre o M1: nada aqui toca score, pesos, `config.py` ou artefato oficial.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.vulnerabilidade import contrato as c
from motor_expansao.vulnerabilidade.alvos_ma import _pressao_por_academia

# Observador no centro; os pontos orbitam ao norte dele.
_LAT, _LNG = -23.5500, -46.6300
_GRAU_LAT_M = 111_320.0


def _norte(metros: float) -> float:
    return _LAT + metros / _GRAU_LAT_M


def _parquet_mapeados(tmp_path: Path, pontos: list[tuple[str, float]]) -> Path:
    """Grava um `concorrentes_mapeados` mínimo: `(rede, metros ao norte)`."""
    caminho = tmp_path / "concorrentes_mapeados.parquet"
    pd.DataFrame(
        {
            "rede": [rede for rede, _ in pontos],
            "lat": [_norte(m) for _, m in pontos],
            "lng": [_LNG] * len(pontos),
            "status_registro": ["valido"] * len(pontos),
        }
    ).to_parquet(caminho)
    return caminho


def _feed(linhas: list[tuple[str, str, float]]) -> pd.DataFrame:
    """Feed cru do agregador: `(chave_snapshot, rede, metros ao norte)`."""
    return pd.DataFrame(
        {
            "fonte": ["wellhub"] * len(linhas),
            "chave_snapshot": [chave for chave, _, _ in linhas],
            "rede": [rede for _, rede, _ in linhas],
            "lat": [_norte(m) for _, _, m in linhas],
            "lng": [_LNG] * len(linhas),
        }
    )


# --------------------------------------------------------------------------- #
# Mutante 1 — a partição independente/cadeia                                   #
# --------------------------------------------------------------------------- #
def test_a_particao_manda_cada_lado_do_feed_para_o_peso_certo(tmp_path: Path) -> None:
    """Independente pesa `0,5`; unidade de rede pesa `1,0`. Inverter a partição derruba isto.

    Duas rodadas SEPARADAS, de propósito. Se as duas naturezas entrassem na mesma rodada à mesma
    distância, a inversão trocaria os dois valores de coluna e os números continuariam iguais — o
    teste passaria com a partição ao contrário, que é exatamente o buraco que este bloco fecha.
    """
    # Pin mapeado a 10 km: existe para o insumo não faltar, mas está fora do raio de 2 km e longe
    # demais para colapsar a unidade de rede da rodada B (o limiar é 150 m).
    caminho = _parquet_mapeados(tmp_path, [("smart_fit", 10_000.0)])

    so_independente = _feed(
        [("obs", c.CATEGORIA_INDEPENDENTE, 0.0), ("ind", c.CATEGORIA_INDEPENDENTE, 500.0)]
    )
    so_rede = _feed([("obs", c.CATEGORIA_INDEPENDENTE, 0.0), ("red", "bluefit", 500.0)])

    a, _ = _pressao_por_academia(caminho, so_independente, com_oferta_do_feed=True)
    b, _ = _pressao_por_academia(caminho, so_rede, com_oferta_do_feed=True)
    assert a is not None and b is not None

    obs_a = a[a["chave_snapshot"] == "obs"].iloc[0]
    obs_b = b[b["chave_snapshot"] == "obs"].iloc[0]

    # A vizinha INDEPENDENTE cai no lado das independentes, e só nele.
    assert obs_a["oferta_independentes"] > 0.0
    assert obs_a["oferta_cadeias_do_feed"] == 0.0
    assert obs_a["n_independentes_no_raio"] == 1
    assert obs_a["n_cadeias_do_feed_no_raio"] == 0

    # A vizinha de REDE cai no lado das cadeias do feed, e só nele.
    assert obs_b["oferta_cadeias_do_feed"] > 0.0
    assert obs_b["oferta_independentes"] == 0.0
    assert obs_b["n_cadeias_do_feed_no_raio"] == 1
    assert obs_b["n_independentes_no_raio"] == 0

    # A assinatura da partição: mesma distância, peso exatamente 2x.
    razao = c.PESO_OFERTA_CADEIA / c.PESO_OFERTA_INDEPENDENTE
    assert obs_b["oferta_cadeias_do_feed"] == pytest.approx(
        obs_a["oferta_independentes"] * razao, rel=1e-9
    )


def test_a_flag_oferta_so_cadeias_desliga_mesmo_o_universo_ampliado(tmp_path: Path) -> None:
    """`--oferta-so-cadeias` reproduz o número histórico. Hoje só a assinatura era inspecionada."""
    caminho = _parquet_mapeados(tmp_path, [("smart_fit", 10_000.0)])
    feed = _feed(
        [
            ("obs", c.CATEGORIA_INDEPENDENTE, 0.0),
            ("ind", c.CATEGORIA_INDEPENDENTE, 500.0),
            ("red", "bluefit", 800.0),
        ]
    )

    ampliado, _ = _pressao_por_academia(caminho, feed, com_oferta_do_feed=True)
    historico, _ = _pressao_por_academia(caminho, feed, com_oferta_do_feed=False)
    assert ampliado is not None and historico is not None

    obs_amp = ampliado[ampliado["chave_snapshot"] == "obs"].iloc[0]
    obs_hist = historico[historico["chave_snapshot"] == "obs"].iloc[0]

    assert obs_amp["universo_oferta"] == c.UNIVERSO_OFERTA_COM_INDEPENDENTES
    assert obs_amp["oferta_independentes"] > 0.0
    assert obs_amp["oferta_cadeias_do_feed"] > 0.0

    assert obs_hist["universo_oferta"] == c.UNIVERSO_OFERTA_CADEIAS
    assert obs_hist["oferta_independentes"] == 0.0
    assert obs_hist["oferta_cadeias_do_feed"] == 0.0
    assert obs_hist["n_independentes_no_raio"] == 0
    assert obs_hist["n_cadeias_do_feed_no_raio"] == 0
    # Sem os dois insumos, o único ponto é o pin a 10 km, fora do raio: pressão zerada.
    assert obs_hist["pressao_competitiva"] == 0.0


# --------------------------------------------------------------------------- #
# Mutante 2 — a ordem do concat `[pontos_mapeados ; sobreviventes]`            #
# --------------------------------------------------------------------------- #
def test_sobrevivente_do_feed_com_pin_mapeado_presente_nao_se_auto_pressiona(
    tmp_path: Path,
) -> None:
    """O arranjo de PRODUÇÃO: `offset > 0` **e** sobrevivente **e** ele é o observador.

    `posicao_por_chave` devolve `offset + len(mantidos)`, que só é válido se o chamador concatenar
    exatamente `[pontos_mapeados ; sobreviventes]`. Inverter a ordem do concat faz a auto-exclusão
    apontar para o pin errado: a academia passa a se pressionar com `sat(1,0) = 50,0` e o
    concorrente real a 1,5 km desaparece do `dist_concorrente_mais_proximo_m`.
    """
    # Um pin mapeado a 1,5 km: dentro do raio de 2 km (então É contado), mas muito além dos 150 m
    # do limiar de dedup — logo a unidade de rede do feed SOBREVIVE, que é a condição do teste.
    caminho = _parquet_mapeados(tmp_path, [("smart_fit", 1_500.0)])
    feed = _feed([("r1", "bluefit", 0.0)])

    saida, _ = _pressao_por_academia(caminho, feed, com_oferta_do_feed=True)
    assert saida is not None
    linha = saida.iloc[0]

    # A academia NÃO se vê: o único concorrente é o pin a 1,5 km.
    assert linha["n_concorrentes_no_raio"] == 1
    assert linha["n_cadeias_do_feed_no_raio"] == 0
    assert linha["dist_concorrente_mais_proximo_m"] == pytest.approx(1_498.3, abs=2.0)
    assert linha["oferta_ponderada"] == pytest.approx(0.2508, abs=1e-3)
    assert linha["pressao_competitiva"] == pytest.approx(20.05, abs=0.1)

    # As assinaturas exatas da auto-pressão, que o concat invertido produziria.
    assert linha["pressao_competitiva"] != pytest.approx(50.0)
    assert linha["dist_concorrente_mais_proximo_m"] > 1_000.0
