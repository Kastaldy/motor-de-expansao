"""`n_concorrentes_est` tem UMA redacao, lida por dois consumidores.

**O defeito que estes testes impedem de voltar.** A DEC-057 trocou a fonte da contagem de
concorrentes de `oferta_consumida_mercado_estimada / capacidade` para
`n_concorrentes_influencia_1km` — porque, desde que cada unidade passou a consumir a capacidade
REAL dela, a divisao deixou de contar academias e passou a contar ALUNOS (um Smart Fit de 5.000
apareceria como "2 concorrentes"). Mas ela trocou em `_derivar` e NAO em
`_hexagonos_acionaveis_brasil`, e as duas passaram a discordar EM PRODUCAO: **2.036 hexagonos
acionaveis pela primeira contra 2.764 pela segunda**, sobre a mesma base e a mesma taxa.

E' exatamente o desencontro que o comentario do bloco de cascata em `app.py` descreve com todas
as letras ("tres redacoes da mesma regra nao dao erro: elas desencontram em silencio, e o Modo 2
passa a discordar do Modo 3") e que a DEC-044 pagou para eliminar. Voltou por atualizacao
PARCIAL — a mesma familia das duas listas gemeas de `RESIDUAL_MERCADO_COLS`.

Por isso os testes aqui sao de FORMA, nao de valor: um teste que so' conferisse o numero
continuaria verde no dia em que alguem reescrevesse a divisao inline num terceiro lugar.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)

#: Os dois consumidores da regra. Se nascer um terceiro, ele entra aqui.
CONSUMIDORES = ("_derivar", "_hexagonos_acionaveis_brasil")


def _frame_onde_as_duas_fontes_DISCORDAM() -> pd.DataFrame:
    """Um hexagono com uma academia GRANDE e outro com duas pequenas.

    A divisao le o primeiro como 2 concorrentes (5.000 / 2.500) e o segundo como 2 tambem —
    apagando a diferenca entre "uma academia grande" e "duas academias". A influencia de 1 km
    le 1 e 2, que e' a verdade. O frame existe para que qualquer confusao entre as duas
    fontes produza numero DIFERENTE, e nao um empate que esconderia a regressao.
    """
    return pd.DataFrame(
        {
            "n_concorrentes_influencia_1km": [1, 2, 0],
            "oferta_consumida_mercado_estimada": [5_000.0, 5_000.0, 0.0],
            "capacidade_default_concorrente_alunos": [2_500.0, 2_500.0, 2_500.0],
        }
    )


# --------------------------------------------------------------------------- #
# A regra                                                                      #
# --------------------------------------------------------------------------- #


def test_a_influencia_de_1km_vence_a_divisao_quando_as_duas_existem() -> None:
    out = pilot._serie_n_concorrentes(_frame_onde_as_duas_fontes_DISCORDAM())
    assert list(out) == [1, 2, 0], "a divisao venceu — a academia GRANDE virou duas"


def test_o_ramo_de_divisao_so_vale_sem_a_coluna_de_influencia() -> None:
    """Artefato ANTERIOR ao BLK-CAPACIDADE-01: capacidade uniforme, divisao e' contagem."""
    df = _frame_onde_as_duas_fontes_DISCORDAM().drop(columns=["n_concorrentes_influencia_1km"])
    assert list(pilot._serie_n_concorrentes(df)) == [2, 2, 0]


def test_sem_fonte_nenhuma_devolve_zero_e_nao_levanta() -> None:
    df = pd.DataFrame({"hex_id": ["a", "b"]})
    out = pilot._serie_n_concorrentes(df)
    assert list(out) == [0, 0]
    assert out.dtype == "int64"


def test_capacidade_zero_nao_vira_infinito() -> None:
    df = pd.DataFrame(
        {
            "oferta_consumida_mercado_estimada": [5_000.0],
            "capacidade_default_concorrente_alunos": [0.0],
        }
    )
    assert list(pilot._serie_n_concorrentes(df)) == [0]


def test_o_resultado_e_sempre_int64() -> None:
    """`_etiqueta` e o payload fazem `int(...)` em cima; float com NaN quebraria a rota."""
    for df in (
        _frame_onde_as_duas_fontes_DISCORDAM(),
        _frame_onde_as_duas_fontes_DISCORDAM().drop(columns=["n_concorrentes_influencia_1km"]),
        pd.DataFrame({"hex_id": ["a"]}),
    ):
        assert pilot._serie_n_concorrentes(df).dtype == "int64"


# --------------------------------------------------------------------------- #
# A forma: uma redacao, e ninguem recalcula por fora                           #
# --------------------------------------------------------------------------- #


def _fonte_de(nome: str) -> str:
    arvore = ast.parse(Path(pilot.__file__).read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef) and no.name == nome:
            return ast.get_source_segment(Path(pilot.__file__).read_text(encoding="utf-8"), no) or ""
    raise AssertionError(f"funcao {nome} nao encontrada em app.py")


def test_os_dois_consumidores_chamam_a_redacao_unica() -> None:
    for nome in CONSUMIDORES:
        assert "_serie_n_concorrentes(" in _fonte_de(nome), (
            f"{nome} nao chama _serie_n_concorrentes — se ela recalcula por conta propria, "
            "o Modo 2 volta a discordar do Modo 3 em silencio (2.036 x 2.764 em producao)"
        )


def test_nenhum_consumidor_recalcula_a_divisao_por_fora() -> None:
    """A assinatura da regressao e' a divisao pela capacidade dentro do consumidor."""
    for nome in CONSUMIDORES:
        fonte = _fonte_de(nome)
        assert "capacidade_default_concorrente_alunos" not in fonte, (
            f"{nome} voltou a dividir pela capacidade na mao. Essa conta pertence ao ramo de "
            "TRAS de _serie_n_concorrentes e conta ALUNOS, nao academias, desde a DEC-057."
        )


def test_a_atribuicao_de_n_concorrentes_est_vem_sempre_da_redacao_unica() -> None:
    """Varre o modulo inteiro: qualquer escrita nova na coluna tem de vir da funcao."""
    texto = Path(pilot.__file__).read_text(encoding="utf-8")
    arvore = ast.parse(texto)
    escritas = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Assign):
            continue
        for alvo in no.targets:
            if (
                isinstance(alvo, ast.Subscript)
                and isinstance(alvo.slice, ast.Constant)
                and alvo.slice.value == "n_concorrentes_est"
            ):
                escritas.append(no)

    assert escritas, "ninguem mais escreve n_concorrentes_est — o teste perdeu o objeto"
    for no in escritas:
        chamada = ast.get_source_segment(texto, no.value) or ""
        assert "_serie_n_concorrentes(" in chamada, (
            f"linha {no.lineno}: n_concorrentes_est recebe algo que nao veio da redacao unica "
            f"({chamada[:80]!r})"
        )
