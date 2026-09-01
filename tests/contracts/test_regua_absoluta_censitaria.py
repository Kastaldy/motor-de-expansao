"""Contrato da REGUA ABSOLUTA do score censitario (2026-08-26).

Ate esta data o score era `100*(0,60*renda_pct_NACIONAL + 0,40*pop_pct_MUNICIPAL)`. O termo de
populacao era percentil DENTRO do municipio, entao toda cidade produzia seus proprios "melhores
hexagonos" no teto da escala, por construcao. Efeitos medidos no artefato de producao:

  - Goiania (pop mediana 7.421, renda R$ 952) chegava a 96,2 no p90; Sao Paulo (35.570 e
    R$ 1.696) so' a 94,2 -- a cidade menor e mais pobre pontuava MAIS.
  - Dos 104.835 hexes com score >= 70, a populacao MEDIANA era 9 habitantes. Oriximina/PA tinha
    hexes de 0,2 habitante com score 70,3.
  - No grao do setor, com densidade real, o setor ralo batia o denso em 37% a 73% dos pares
    (72.623 setores de 11 capitais).

Estes testes travam as propriedades que a regua absoluta precisa ter. Sao propriedades, nao
valores de safra: nao quebram quando o Censo for atualizado.
"""
from __future__ import annotations

import numpy as np

from motor_expansao.pipelines.calibrar_renda_setor_2022 import (
    POP_ABS_MAX,
    POP_ABS_MIN,
    RENDA_ABS_MAX,
    RENDA_ABS_MIN,
    calcular_score_calibrado,
    nota_pop_absoluta,
    nota_renda_absoluta,
)


def _score(renda: float, pop: float) -> float:
    return float(calcular_score_calibrado(np.array([renda]), np.array([pop]))[2][0])


def test_score_e_absoluto_nao_depende_do_contexto():
    """O MESMO par (renda, populacao) da o MESMO score, isolado ou dentro de qualquer conjunto.

    Era isso que o percentil municipal quebrava: o score de um hexagono dependia dos vizinhos
    de municipio, entao o mesmo lugar valia coisas diferentes conforme a cidade em volta.
    """
    isolado = _score(1_696.0, 35_570.0)
    em_lote = float(
        calcular_score_calibrado(
            np.array([100.0, 1_696.0, 9_000.0]),
            np.array([1.0, 35_570.0, 200_000.0]),
        )[2][1]
    )
    assert isolado == em_lote


def test_sao_paulo_pontua_acima_de_goiania():
    """Perfis medianos reais das duas capitais; a inversao que motivou a mudanca."""
    sao_paulo = _score(1_696.0, 35_570.0)
    goiania = _score(952.0, 7_421.0)
    assert sao_paulo > goiania, f"SP {sao_paulo:.1f} deveria superar Goiania {goiania:.1f}"


def test_hexagono_praticamente_vazio_nao_tira_nota_alta():
    """Oriximina/PA: 0,2 habitante e renda R$ 1.012 tirava 70,3 na regua antiga."""
    assert _score(1_011.8, 0.2) < 30.0


def test_nao_satura_no_topo_realista():
    """A cauda alta precisa continuar ordenavel -- foi a doenca do M1 (81% das unidades em 100)."""
    a = _score(2_600.0, 30_000.0)
    b = _score(3_200.0, 70_000.0)
    c = _score(3_900.0, 95_000.0)
    assert a < b < c, f"topo empatando: {a:.2f} / {b:.2f} / {c:.2f}"


def test_monotonia_nos_dois_termos():
    assert _score(2_000.0, 20_000.0) > _score(1_000.0, 20_000.0)
    assert _score(2_000.0, 40_000.0) > _score(2_000.0, 20_000.0)


def test_ancoras_delimitam_as_notas():
    assert nota_renda_absoluta(np.array([RENDA_ABS_MIN]))[0] == 0.0
    assert nota_renda_absoluta(np.array([RENDA_ABS_MAX]))[0] == 100.0
    assert nota_renda_absoluta(np.array([RENDA_ABS_MIN - 500]))[0] == 0.0
    assert nota_renda_absoluta(np.array([RENDA_ABS_MAX * 3]))[0] == 100.0
    assert nota_pop_absoluta(np.array([POP_ABS_MIN]))[0] == 0.0
    assert nota_pop_absoluta(np.array([POP_ABS_MAX]))[0] == 100.0
    assert nota_pop_absoluta(np.array([0.0]))[0] == 0.0


def test_populacao_e_log_e_renda_e_linear():
    """A escolha de escala nao pode inverter sem alguem decidir.

    Populacao e' muito assimetrica (p50 3.561 contra p95 28.845 no universo povoado), entao
    entra em LOG: dobrar a populacao vale o mesmo ganho em qualquer ponto da escala. Renda entra
    LINEAR, que e' mais legivel e discrimina melhor no topo.
    """
    dobra_baixo = nota_pop_absoluta(np.array([4_000.0]))[0] - nota_pop_absoluta(np.array([2_000.0]))[0]
    dobra_alto = nota_pop_absoluta(np.array([64_000.0]))[0] - nota_pop_absoluta(np.array([32_000.0]))[0]
    assert abs(dobra_baixo - dobra_alto) < 1e-9, "populacao deixou de ser log"

    passo_baixo = nota_renda_absoluta(np.array([1_300.0]))[0] - nota_renda_absoluta(np.array([800.0]))[0]
    passo_alto = nota_renda_absoluta(np.array([3_300.0]))[0] - nota_renda_absoluta(np.array([2_800.0]))[0]
    assert abs(passo_baixo - passo_alto) < 1e-9, "renda deixou de ser linear"


def test_corte_do_funil_bate_com_a_escala():
    """`SCORE_CORTE_QUENTE` foi de 70 para 30 junto com a troca de escala.

    Se alguem devolver o corte para 70 sem devolver a escala, a camada 1 do funil cai de
    11.255 para 148 hexes -- em silencio.
    """
    # Le do FONTE em vez de importar: `web/server/app.py` puxa modulos que so' existem no
    # sys.path do container do piloto (ex.: `acesso`), e o contrato aqui e' sobre o numero.
    import re  # noqa: PLC0415
    from pathlib import Path as _P  # noqa: PLC0415

    fonte = _P("web/server/app.py").read_text(encoding="utf-8")
    m = re.search(r"^SCORE_CORTE_QUENTE\s*=\s*([0-9.]+)", fonte, re.M)
    assert m, "SCORE_CORTE_QUENTE nao encontrado em web/server/app.py"
    SCORE_CORTE_QUENTE = float(m.group(1))

    assert SCORE_CORTE_QUENTE == 30.0
    # um perfil de praca real (renda mediana da rede, porte urbano) tem de passar o corte
    assert _score(1_500.0, 15_000.0) >= SCORE_CORTE_QUENTE


def test_reversao_para_percentil_nao_depende_de_backup():
    """Voltar atras tem de ser um comando, nao arqueologia.

    `recalcular_score_absoluto` reescreve o score in-place nos parquets censitarios, e o Censo
    bruto nao vive na estacao -- entao, sem isto, reverter exigiria reprocessar uma fonte que
    nao esta aqui. A saida e' que os percentis (`renda_pct_nacional_calibrado`,
    `pop_pct_municipal`) sao PRESERVADOS, e a formula antiga se reconstitui deles.
    Medido contra o backup do artefato nacional em 2026-08-26: erro maximo 0,0 exato.
    """
    import pandas as pd  # noqa: PLC0415

    from motor_expansao.pipelines.recalcular_score_absoluto import (  # noqa: PLC0415
        recalcular,
        reverter,
    )

    original = pd.DataFrame(
        {
            "renda_per_capita_setor_2022_calibrada": [500.0, 1_500.0, 3_000.0, 900.0],
            "pop_total_setor_2022": [800.0, 15_000.0, 60_000.0, 3.0],
            "renda_pct_nacional_calibrado": [0.10, 0.55, 0.95, 0.40],
            "pop_pct_municipal": [0.20, 0.60, 0.90, 0.80],
        }
    )
    # score ANTIGO, como o artefato tinha antes da troca de regua
    antigo, _ = reverter(original.copy())
    esperado = antigo["score_setor_2022_calibrado"].tolist()

    # aplica a regua nova e depois reverte
    novo, _ = recalcular(antigo.copy())
    assert novo["score_setor_2022_calibrado"].tolist() != esperado, "a regua nova nao mudou nada"

    voltou, _ = reverter(novo.copy())
    assert voltou["score_setor_2022_calibrado"].tolist() == esperado
