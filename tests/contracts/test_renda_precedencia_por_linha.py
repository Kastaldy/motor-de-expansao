"""CONTRATO: a precedencia da renda do hexagono e' UMA redacao, e escolhe por LINHA.

DUAS travas, contra dois defeitos distintos que este repo ja' pagou:

1. POR LINHA, NAO POR COLUNA (DEC-058). A redacao antiga parava na primeira coluna
   PRESENTE e usava so' ela no frame inteiro. Como o artefato nacional tem
   `renda_per_capita_setor_2022_calibrada` no schema, `renda_origem` saia ESCALAR e o aviso
   `renda_municipal` do payload nascia constante `False` em 1.542.531 de 1.542.531
   hexagonos -- quatro ramos de rotulo do front inalcancaveis. Pior, 234.147 hexagonos
   (15,18%) tem essa coluna presente e NULA na propria linha, com a municipal disponivel
   ao lado, e nao exibiam renda nenhuma. Mesma familia da DEC-038: "a coluna existe"
   tratado como "o valor existe".

2. UMA REDACAO, N CONSUMIDORES (licao da DEC-044). A regra vivia escrita duas vezes --
   `_derivar` (leitura por particao `uf=XX`) e `_hexagonos_acionaveis_brasil` (varredura
   nacional da rota `/api/hexagonos`). Duas redacoes da mesma regra nao dao erro: elas
   desencontram em SILENCIO, meses depois e longe da causa. Consertar so' uma seria
   reproduzir exatamente o defeito que a DEC-044 nomeou.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)


def _frame_com_lacuna() -> pd.DataFrame:
    """A FORMA REAL dos 234.147: coluna de setor PRESENTE, valor nulo em UMA das linhas."""
    return pd.DataFrame(
        {
            "hex_id": ["a", "b", "c"],
            "renda_per_capita_setor_2022_calibrada": [1500.0, np.nan, 900.0],
            "renda_per_capita": [1400.0, 1800.0, 800.0],
        }
    )


def test_serie_renda_escolhe_por_linha_preservando_a_precedencia() -> None:
    valor, origem = pilot._serie_renda(_frame_com_lacuna())

    # Precedencia mantida onde ha setor...
    assert valor.tolist() == [1500.0, 1800.0, 900.0]
    assert origem.tolist() == [
        "renda_per_capita_setor_2022_calibrada",
        "renda_per_capita",
        "renda_per_capita_setor_2022_calibrada",
    ]


def test_renda_origem_nunca_e_escalar() -> None:
    """Trava de FORMA: um valor por linha, e mais de um valor distinto no mesmo frame.

    Qualquer redacao que devolva a mesma origem para o frame inteiro (o defeito de 2026-09)
    morre aqui -- inclusive uma que, por acaso, escolha a coluna "certa".
    """
    derivado = pilot._derivar(_frame_com_lacuna())
    origem = derivado["renda_origem"]

    assert isinstance(origem, pd.Series)
    assert len(origem) == 3
    assert origem.nunique() > 1, "renda_origem constante: a escolha voltou a ser por COLUNA"


def test_ausencia_total_de_renda_nao_vira_origem_municipal() -> None:
    """Sem valor em nenhuma coluna: origem `None`, nao a string da municipal.

    `renda_municipal` do payload le' `renda_origem == "renda_per_capita"`. Se a ausencia
    total colapsasse nessa string, o front afirmaria "estimativa municipal" sobre um
    tooltip vazio.
    """
    df = pd.DataFrame(
        {
            "hex_id": ["a"],
            "renda_per_capita_setor_2022_calibrada": [np.nan],
            "renda_per_capita": [np.nan],
        }
    )
    valor, origem = pilot._serie_renda(df)
    assert np.isnan(valor.iloc[0])
    assert origem.iloc[0] is None


def test_frame_sem_nenhuma_das_colunas_nao_estoura() -> None:
    valor, origem = pilot._serie_renda(pd.DataFrame({"hex_id": ["a", "b"]}))
    assert valor.isna().all()
    assert origem.isna().all()
    assert len(valor) == 2


def test_as_duas_superficies_leem_a_mesma_redacao() -> None:
    """`_derivar` E a varredura nacional chamam `_serie_renda` -- nao uma copia da regra.

    Fonte, e nao comportamento, de proposito: a rota nacional depende do artefato de 1,5 M
    de linhas em disco e nao roda no CI, entao a unica trava barata contra uma SEGUNDA
    redacao nascer ali e' esta.
    """
    for funcao in (pilot._derivar, pilot._hexagonos_acionaveis_brasil):
        fonte = inspect.getsource(inspect.unwrap(funcao))
        assert "_serie_renda(" in fonte, (
            f"{funcao.__name__} deixou de usar `_serie_renda` -- provavel segunda redacao "
            "da precedencia da renda (ver DEC-044)"
        )
