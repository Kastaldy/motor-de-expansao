"""Bloco B — o exportador argentino RECOMPUTA o score, não o renomeia.

`src/motor_expansao/pipelines/exportar_piloto_ar.py` veio do repositório do Juan
(`juancalu/motor-argentina`) em 2026-09-02. O de-para original mandava, e o `HANDOFF.md`
§4 documentava:

    score_setor_2022_calibrado ← hex_score_estrutural

**Isso não pode ser honrado, e o motivo é de semântica, não de nome.** O
`hex_score_estrutural` argentino é um PERCENTIL (0,40·renda_pct + 0,60·pop_pct, percentis
nacionais); a coluna `score_setor_2022_calibrado` é aquela sobre a qual o funil aplica o
corte de 30, que é ABSOLUTO. Renomear faz um número de 0-100 virar outro número de 0-100 —
e nada acusa.

**Medido no pacote entregue, 42.388 hexágonos (2026-09-02):** sob o percentil renomeado,
12,9% passariam o corte de 30; sob o recompute nas âncoras argentinas, 5,5%. O Brasil fica
em 2,2%. Ou seja, o corte de "hexágono quente" sairia **2,3× mais permissivo** na Argentina
do que a régua pretende.

Este arquivo é a rede que impede a renomeação de voltar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from motor_expansao.perfil import PERFIL_BR_EMBARCADO, carregar_perfil
from motor_expansao.pipelines import exportar_piloto_ar as exp
from motor_expansao.pipelines.calibrar_renda_setor_2022 import (
    ANCORAS_BR,
    calcular_score_calibrado,
)

_PERFIL_AR = PERFIL_BR_EMBARCADO.parents[1] / "AR" / "perfil.json"


@pytest.fixture(autouse=True)
def _perfil_argentino(monkeypatch: pytest.MonkeyPatch):
    """O módulo lê `PERFIL` de escopo de módulo, preenchido por `main()`."""
    monkeypatch.setattr(exp, "PERFIL", carregar_perfil(_PERFIL_AR))


def _hexagonos(n: int = 5) -> pd.DataFrame:
    """Frame mínimo com as colunas que `montar_hexagonos` consome."""
    import h3

    celulas = [h3.latlng_to_cell(-34.6 + i * 0.1, -58.4 + i * 0.1, 7) for i in range(n)]
    return pd.DataFrame(
        {
            "h3_id": celulas,
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
            "pop_captacao": np.linspace(1_000.0, 60_000.0, n),
            "pop_total": np.linspace(500.0, 30_000.0, n),
            "renda_estimada_usd": np.linspace(300.0, 950.0, n),
            "faixa_oportunidade": ["alta"] * n,
        }
    )


# --------------------------------------------------------------------------------
# O recompute
# --------------------------------------------------------------------------------


def test_o_score_do_mapa_NAO_e_o_estrutural_renomeado() -> None:
    """Se alguém devolver a renomeação, é aqui que aparece."""
    hx = _hexagonos()
    saida = exp.montar_hexagonos(hx)
    assert not np.allclose(
        saida["score_setor_2022_calibrado"].values, hx["hex_score_estrutural"].values
    ), "o score voltou a ser o `hex_score_estrutural` renomeado"


def test_o_score_do_mapa_sai_das_ANCORAS_do_perfil() -> None:
    hx = _hexagonos()
    ar = carregar_perfil(_PERFIL_AR)
    _, _, esperado = calcular_score_calibrado(
        hx["renda_estimada_usd"].values, hx["pop_total"].values, ancoras=ar.ancoras()
    )
    np.testing.assert_allclose(
        exp.montar_hexagonos(hx)["score_setor_2022_calibrado"].values, esperado
    )


def test_as_ancoras_ARGENTINAS_mudam_o_resultado() -> None:
    """Prova que a régua usada é a do perfil e não o default brasileiro.

    Sem isto, `score_do_pais` poderia estar chamando a função com `ANCORAS_BR` e o teste
    acima passaria igual — o default é justamente o brasileiro.
    """
    renda = np.array([700.0])  # p95 argentino, quase nada na régua brasileira
    pop = np.array([15_000.0])
    ar = carregar_perfil(_PERFIL_AR)
    _, _, com_ar = calcular_score_calibrado(renda, pop, ancoras=ar.ancoras())
    _, _, com_br = calcular_score_calibrado(renda, pop, ancoras=ANCORAS_BR)
    assert com_ar[0] > com_br[0] + 10.0
    np.testing.assert_allclose(exp.score_do_pais(renda, pop), com_ar)


def test_o_estrutural_argentino_continua_vindo_com_o_NOME_dele() -> None:
    """Ele não some — vira coluna de auditoria. O que não pode é ocupar o lugar da outra."""
    hx = _hexagonos()
    saida = exp.montar_hexagonos(hx)
    np.testing.assert_allclose(
        saida["hex_score_estrutural_ar"].values, hx["hex_score_estrutural"].values
    )


def test_o_de_para_de_mercado_nao_carrega_mais_o_score() -> None:
    assert "hex_score_estrutural" not in exp.MERCADO_DE_PARA
    assert "score_setor_2022_calibrado" not in exp.MERCADO_DE_PARA.values()


# --------------------------------------------------------------------------------
# O que o exportador DERIVA — e que não existe no parquet cru
# --------------------------------------------------------------------------------


def test_deriva_o_que_o_pacote_cru_nao_tem() -> None:
    """É a razão de este arquivo ter vindo para cá.

    `hex_id`, `lat`, `lng`, `cidade` e `cod_municipio` **não existem** no parquet
    entregue: quem os deriva é este script. Enquanto ele vivesse só no repositório do
    Juan, a ponte entre o pacote e a instância no ar era dependência de PESSOA.
    """
    hx = _hexagonos()
    saida = exp.montar_hexagonos(hx)
    for coluna in ("hex_id", "lat", "lng", "cidade", "cod_municipio"):
        assert coluna in saida.columns, coluna
        assert coluna not in hx.columns, f"`{coluna}` já vinha no cru — premissa mudou"
    # lat/lng saem do índice H3, e têm de cair na Argentina.
    assert (saida["lat"] < -20).all() and (saida["lat"] > -56).all()
    assert (saida["lng"] < -53).all() and (saida["lng"] > -74).all()


def test_a_rede_ultra_e_zero_e_isso_e_resposta_nao_ausencia() -> None:
    """O projeto argentino é greenfield. Zero é o número CERTO, e vem explícito."""
    saida = exp.montar_hexagonos(_hexagonos())
    assert (saida["n_unidades_ultra_performance_hex"] == 0).all()
    assert (saida["n_unidades_ultra_2km"] == 0).all()


# --------------------------------------------------------------------------------
# O que NÃO veio junto
# --------------------------------------------------------------------------------


def test_nao_ha_MOTOR_PAIS_no_exportador_importado() -> None:
    """O original instruía `MOTOR_PAIS=AR` para o piloto tratar o uplift como identidade.

    A env nunca existiu nesta plataforma e não vai existir — país escolhendo caminho de
    execução é o que a DEC-047 proíbe. O mesmo defeito (renda 63% acima da real) é
    resolvido por `reguas.uplift_composicao = 1.0` no perfil argentino.

    As menções que sobram são de COMENTÁRIO, explicando por que a variável não entrou.
    """
    import ast
    import inspect

    fonte = inspect.getsource(exp)
    # Fora de comentário E fora da docstring do módulo: as duas citam a variável para
    # explicar por que ela NÃO entrou, e um filtro só de `#` não alcança a docstring.
    arvore = ast.parse(fonte)
    doc = arvore.body[0]
    linhas_doc = set(range(doc.lineno, (doc.end_lineno or doc.lineno) + 1))
    codigo = [
        linha
        for n, linha in enumerate(fonte.splitlines(), 1)
        if "MOTOR_PAIS" in linha
        and n not in linhas_doc
        and not linha.lstrip().startswith("#")
    ]
    assert not codigo, f"MOTOR_PAIS voltou como código: {codigo}"


def test_o_uplift_argentino_e_identidade() -> None:
    """A defesa que substituiu a env, no lugar onde ela agora vive."""
    assert carregar_perfil(_PERFIL_AR).reguas.uplift_composicao == 1.0
