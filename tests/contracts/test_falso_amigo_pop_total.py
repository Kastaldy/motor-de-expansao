"""`pop_total` e' um FALSO AMIGO entre os pacotes — e por isso a Argentina nao a emite.

Duas colunas com o mesmo nome e unidades de observacao diferentes sao a forma mais barata
de produzir um numero plausivel e errado: nada quebra, nenhum teste acende, e a tela
mostra um total com cara de certo. Medido em 2026-09-02:

    pop_total, pacote BRASILEIRO
        e' a populacao do MUNICIPIO, repetida em cada hexagono dele.
        645 de 645 municipios de SP tem um unico valor distinto; o municipio de Sao Paulo
        carrega 11.451.999 nos seus 296 hexagonos (censo 2022: 11.451.245).
        Somada no pais: 79,3 BILHOES — 391x o Brasil.

    pop_total, pacote ARGENTINO (como veio do motor do Juan)
        e' a populacao do HEXAGONO.
        Somada nas 24 provincias: 43,5 milhoes — 94,4% do censo 2022 (46.044.703).

O numero argentino esta CERTO; o que estava errado era a gaveta. A coluna com essa
semantica nos dois lados e' `pop_total_setor_2022` (populacao dos setores/radios
censitarios agregada ao hexagono — no Brasil soma 195,8 milhoes, 96,4% do censo).

O que este arquivo trava:
  1. o exportador argentino entrega a populacao do hexagono em `pop_total_setor_2022`;
  2. ele NAO emite `pop_total` — a Argentina nao tem o total departamental repetido por
     hexagono, e inventa-lo so' para preencher a gaveta recriaria o falso amigo;
  3. a coluna que o mapa corta em 5.000 continua sendo a CAPTACAO, intocada.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from motor_expansao.perfil import PERFIL_BR_EMBARCADO, carregar_perfil
from motor_expansao.pipelines import exportar_piloto_ar as exp

_PERFIL_AR = PERFIL_BR_EMBARCADO.parents[1] / "AR" / "perfil.json"


@pytest.fixture(autouse=True)
def _perfil_argentino(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(exp, "PERFIL", carregar_perfil(_PERFIL_AR))


def _hexagonos(n: int = 5) -> pd.DataFrame:
    import h3

    return pd.DataFrame(
        {
            "h3_id": [h3.latlng_to_cell(-34.6 + i * 0.1, -58.4 + i * 0.1, 7) for i in range(n)],
            "nome_departamento": [f"Depto {i}" for i in range(n)],
            "cod_departamento": [f"{i:05d}" for i in range(n)],
            "hex_score_estrutural": np.linspace(10.0, 95.0, n),
            "score_priorizacao": np.linspace(10.0, 90.0, n),
            "score_oportunidade_residual": np.linspace(5.0, 80.0, n),
            "hex_score_final": np.linspace(8.0, 88.0, n),
            "residual_membros": np.linspace(100.0, 900.0, n),
            "oferta_consumida_mercado": np.linspace(50.0, 400.0, n),
            "capacidade_concorrente_calibrada": np.full(n, 1070.0),
            "sam_membros_potencial": np.linspace(200.0, 1200.0, n),
            # As duas grandezas de populacao, propositalmente DIFERENTES: a captacao
            # (hexagono + 6 vizinhos) e' sempre maior que a celula.
            "pop_captacao": np.linspace(5_000.0, 60_000.0, n),
            "pop_total": np.linspace(500.0, 30_000.0, n),
            "renda_estimada_usd": np.linspace(300.0, 950.0, n),
            "faixa_oportunidade": ["alta"] * n,
        }
    )


def test_a_populacao_do_hexagono_vai_para_pop_total_setor_2022() -> None:
    hx = _hexagonos()
    saida = exp.montar_hexagonos(hx)
    assert "pop_total_setor_2022" in saida.columns
    np.testing.assert_allclose(
        saida["pop_total_setor_2022"].values, hx["pop_total"].values
    )


def test_o_exportador_NAO_emite_pop_total() -> None:
    """A gaveta do falso amigo fica vazia. E' o coracao deste arquivo."""
    saida = exp.montar_hexagonos(_hexagonos())
    assert "pop_total" not in saida.columns, (
        "`pop_total` voltou a ser emitida pelo pacote argentino — no Brasil essa coluna "
        "e' o MUNICIPIO repetido por hexagono, e quem somar as duas juntas erra por 391x"
    )


def test_o_corte_de_5000_continua_caindo_sobre_a_CAPTACAO() -> None:
    """A troca de gaveta nao pode ter mexido no que o mapa corta.

    `_derivar` monta `pop_leitura` na precedencia populacao_corte_hex >
    pop_total_setor_2022 > pop_total. Como a captacao vem primeiro, mover a populacao da
    celula para a segunda posicao da precedencia NAO muda o hexagono que o front acende —
    e este teste e' o que garante que continua assim.
    """
    hx = _hexagonos()
    saida = exp.montar_hexagonos(hx)
    np.testing.assert_allclose(saida["populacao_corte_hex"].values, hx["pop_captacao"].values)
    # A captacao e' MAIOR que a celula em todas as linhas: se um dia as duas colunas
    # vierem iguais, o de-para colapsou e o corte mudou de grandeza sem ninguem ver.
    assert (saida["populacao_corte_hex"] > saida["pop_total_setor_2022"]).all()


def test_as_duas_colunas_sao_grandezas_diferentes_e_nao_se_confundem() -> None:
    """Somar a captacao double-conta; somar a celula, nao.

    Medido no pacote real (15.186 hexagonos): `populacao_corte_hex` soma 288 milhoes,
    6,3x a Argentina, porque o hexagono e os 6 vizinhos se sobrepoem. E' por isso que
    `_COLS_POP_SOMA_UF` (web/server/app.py) exclui a captacao do total por UF.
    """
    saida = exp.montar_hexagonos(_hexagonos())
    assert saida["populacao_corte_hex"].sum() > saida["pop_total_setor_2022"].sum() * 1.5
