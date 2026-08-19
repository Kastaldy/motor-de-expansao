"""Residual sem concorrente do modelo de 1 km — com foco no hexagono SATURADO.

POR QUE ESTE ARQUIVO EXISTE. A primeira versao de `web/server/pressao_1km.py`
reconstruia `sam - consumo_ultra` como

    oferta_efetiva_disponivel + oferta_consumida_mercado_estimada

Isso so' vale enquanto `oferta_efetiva_disponivel` NAO bateu no clip em zero que o
Bloco 5 aplica (`calcular_colunas_mercado.py:379`). Em hexagono saturado — aquele em
que concorrentes + Ultra ja consomem mais que o SAM — a soma devolvia o consumo das
concorrentes, INFLANDO o residual exatamente nos hexes mais disputados, que sao o
motivo de a chave de 1 km existir.

Nao roda com parquet: monta o DataFrame na mao com as colunas do contrato.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import pressao_1km  # noqa: E402  (web/server no sys.path acima)

CAP = pressao_1km.CAPACIDADE_ULTRA_PROXY


def _hex(**over: float) -> pd.DataFrame:
    """Um hexagono com o contrato minimo; `over` sobrescreve o que o teste precisa."""
    base = {
        "hex_id": "87a8100000fffff",
        "sam_fitness_potencial": 1_000.0,
        "oferta_consumida_mercado_estimada": 0.0,
        "oferta_consumida_ultra_real": 0.0,
        "n_unidades_ultra_2km": 0.0,
        "oferta_efetiva_disponivel": 1_000.0,
    }
    base.update(over)
    return pd.DataFrame([base])


def test_nao_saturado_a_inversao_continua_exata() -> None:
    """Onde a oferta nao bateu no clip, o resultado nao muda: `sam - ultra`."""
    # sam=1000, merc_2km=200, ultra=300 -> oferta = 1000-200-300 = 500 (>0, nao saturou)
    df = _hex(
        oferta_consumida_mercado_estimada=200.0,
        oferta_consumida_ultra_real=300.0,
        oferta_efetiva_disponivel=500.0,
    )
    assert pressao_1km.disponivel_sem_concorrente(df).iloc[0] == 700.0  # 1000 - 300


def test_saturado_usa_ultra_real_e_nao_infla() -> None:
    """O caso do bug: a soma ingenua daria 1000; o certo e' `sam - ultra` = 200."""
    # sam=1000, ultra=800, merc_2km=1000 -> 1000-1000-800 < 0 -> oferta CLIPADA em 0
    df = _hex(
        oferta_consumida_mercado_estimada=1_000.0,
        oferta_consumida_ultra_real=800.0,
        oferta_efetiva_disponivel=0.0,
    )
    ingenuo = 0.0 + 1_000.0  # o que a versao antiga devolvia
    assert pressao_1km.disponivel_sem_concorrente(df).iloc[0] == 200.0
    assert ingenuo == 1_000.0  # trava o contraste: 5x o valor correto


def test_saturado_sem_ultra_real_cai_no_proxy_por_unidades() -> None:
    """`ultra_real == 0` -> Bloco 5 usa `n_unidades_ultra_2km * CAP`."""
    # sam=9000, ultra_real=0, n_2km=2 -> ultra_est = 5000 -> sem_conc = 4000
    df = _hex(
        sam_fitness_potencial=9_000.0,
        oferta_consumida_mercado_estimada=8_000.0,
        oferta_consumida_ultra_real=0.0,
        n_unidades_ultra_2km=2.0,
        oferta_efetiva_disponivel=0.0,
    )
    assert pressao_1km.disponivel_sem_concorrente(df).iloc[0] == 9_000.0 - 2 * CAP


def test_saturado_sem_insumo_de_ultra_devolve_nan_e_nao_um_chute() -> None:
    """Sem `n_unidades_ultra_2km` a reproducao e' impossivel: NaN, nunca numero errado."""
    df = _hex(
        oferta_consumida_mercado_estimada=1_000.0,
        oferta_efetiva_disponivel=0.0,
    ).drop(columns=["n_unidades_ultra_2km"])
    assert math.isnan(pressao_1km.disponivel_sem_concorrente(df).iloc[0])


def test_coluna_pronta_tem_prioridade_sobre_a_reproducao() -> None:
    """Se o artefato um dia trouxer `oferta_consumida_ultra_estimada`, ela manda."""
    df = _hex(
        oferta_consumida_mercado_estimada=1_000.0,
        oferta_consumida_ultra_real=800.0,
        oferta_efetiva_disponivel=0.0,
    )
    df["oferta_consumida_ultra_estimada"] = 950.0
    assert pressao_1km.disponivel_sem_concorrente(df).iloc[0] == 50.0  # 1000 - 950


def test_sem_conc_nunca_fica_negativo() -> None:
    """Ultra sozinha consumindo mais que o SAM -> piso em zero, nao numero negativo."""
    df = _hex(
        sam_fitness_potencial=500.0,
        oferta_consumida_mercado_estimada=100.0,
        oferta_consumida_ultra_real=900.0,
        oferta_efetiva_disponivel=0.0,
    )
    assert pressao_1km.disponivel_sem_concorrente(df).iloc[0] == 0.0


def test_regimes_misturados_no_mesmo_frame() -> None:
    """Saturado e nao saturado convivem: cada linha segue a sua regra."""
    df = pd.DataFrame(
        [
            # nao saturado -> 1000 - 300 = 700
            {
                "hex_id": "a",
                "sam_fitness_potencial": 1_000.0,
                "oferta_consumida_mercado_estimada": 200.0,
                "oferta_consumida_ultra_real": 300.0,
                "n_unidades_ultra_2km": 0.0,
                "oferta_efetiva_disponivel": 500.0,
            },
            # saturado -> 1000 - 800 = 200 (a soma ingenua daria 1000)
            {
                "hex_id": "b",
                "sam_fitness_potencial": 1_000.0,
                "oferta_consumida_mercado_estimada": 1_000.0,
                "oferta_consumida_ultra_real": 800.0,
                "n_unidades_ultra_2km": 0.0,
                "oferta_efetiva_disponivel": 0.0,
            },
        ]
    )
    assert list(pressao_1km.disponivel_sem_concorrente(df)) == [700.0, 200.0]
