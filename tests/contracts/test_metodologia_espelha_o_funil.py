"""Contrato: o painel de Metodologia descreve a régua que o funil DE FATO aplica.

Por que este teste existe: `/api/metodologia` é um manual publicado na mesma tela que
o resultado. Se o texto e o funil divergirem, o usuário não vê um bug — vê uma
explicação convincente e errada, e decide com ela. É a classe de defeito mais cara
deste endpoint, e nenhum teste a cobria: o painel nasceu publicando
"Quente ≥ 90 / Alta ≥ 6.000 alunos / Agora-Próximo-Fila" enquanto o funil, depois do
BLK-MAPA-FAIXAS-01, já etiquetava Desfavorável…Excelente, Saturado…Livre e as faixas de
oportunidade do M1. Os dois lados estavam verdes no CI.

O teste não valida a REDAÇÃO (isso é revisão humana); valida que toda etiqueta
publicada é uma etiqueta que o funil pode emitir, e vice-versa.

READ-ONLY: só chama funções puras (`montar_metodologia`, `_etiqueta`), sem tocar dado.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_SERVER = Path(__file__).resolve().parents[2] / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)

from motor_expansao.dashboard.constants import (  # noqa: E402
    CAPACIDADE_UNIDADE_ALUNOS,
    FAIXA_LABELS,
    FAIXAS_MAPA_DEMANDA,
    FAIXAS_MAPA_POTENCIAL,
)

# Vocabulario que o BLK-MAPA-FAIXAS-01 aposentou. Nenhum deles pode voltar ao painel
# sem voltar tambem ao `_etiqueta` — foi exatamente essa divergencia que o bloco matou.
_EXTINTOS = {"Quente", "Sólido", "Polo", "Emergente", "Agora", "Próximo", "Espera"}


@pytest.fixture(scope="module")
def metodologia() -> dict:
    return pilot.montar_metodologia()


def _etiquetas(camada: dict, escopo: str) -> set[str]:
    return {
        f["etiqueta"] for f in camada["faixas"] if f["escopo"] in ("", escopo)
    }


def _camada(metodologia: dict, n: int) -> dict:
    return next(c for c in metodologia["camadas"] if c["n"] == n)


# --------------------------------------------------------------------- contrato
def test_payload_tem_as_4_camadas_completas(metodologia):
    camadas = metodologia["camadas"]
    assert [c["n"] for c in camadas] == [1, 2, 3, 4]
    for c in camadas:
        assert c["titulo"] and c["pergunta"] and c["corte"]
        assert c["faixas"], f"camada {c['n']} sem faixa publicada"
        for m in c["metricas"]:
            # `fonte` primeiro: a duvida inicial de quem le e' "de onde veio esse numero".
            assert m["nome"] and m["fonte"] and m["resumo"] and m["regra"]
    assert metodologia["parametros"] and metodologia["fontes"]


def test_toda_faixa_declara_escopo_valido(metodologia):
    for c in metodologia["camadas"]:
        for f in c["faixas"]:
            assert f["escopo"] in ("", "municipio", "uf"), f
            assert f["etiqueta"] and f["condicao"]


# ------------------------------------------------------- coerencia painel x funil
def test_camada_1_publica_as_faixas_de_potencial_que_o_funil_emite(metodologia):
    publicadas = _etiquetas(_camada(metodologia, 1), "municipio")
    do_codigo = {nome for _de, _ate, nome, _cor, _tom in FAIXAS_MAPA_POTENCIAL}
    assert publicadas == do_codigo

    # E o funil emite MESMO essas etiquetas, no meio de cada faixa.
    linha = pd.Series({"n_concorrentes_est": 0})
    for de, ate, nome, _cor, _tom in FAIXAS_MAPA_POTENCIAL:
        etiqueta, _tom_item, _cor_item = pilot._etiqueta("score", (de + ate) / 2, 1, linha)
        assert etiqueta == nome, f"score {(de + ate) / 2} -> {etiqueta}, painel diz {nome}"


def test_camada_2_publica_as_faixas_de_demanda_em_alunos(metodologia):
    publicadas = _etiquetas(_camada(metodologia, 2), "municipio")
    do_codigo = {nome for _de, _ate, nome, _cor, _tom in FAIXAS_MAPA_DEMANDA}
    assert publicadas == do_codigo

    # A camada 2 recebe ALUNOS, nao score: a conversao publicada (100 = 2.500 alunos)
    # tem que devolver a mesma faixa que a legenda mostra.
    linha = pd.Series({"n_concorrentes_est": 0})
    for de, ate, nome, _cor, _tom in FAIXAS_MAPA_DEMANDA:
        alunos = ((de + ate) / 2) * CAPACIDADE_UNIDADE_ALUNOS / 100
        etiqueta, _t, _c = pilot._etiqueta("residual", alunos, 1, linha)
        assert etiqueta == nome, f"{alunos} alunos -> {etiqueta}, painel diz {nome}"


def test_camada_3_publica_o_vocabulario_competitivo_no_municipio(metodologia):
    """No municipio a camada 3 rotula por CONCORRENCIA — nao por intensidade de residual.

    Era o defeito: o painel publicava Alta/Média/Baixa e a tela mostrava Livre em todas
    as linhas, porque `montar_funil` passa `metrica_etiqueta="conc. 2 km"`.
    """
    publicadas = _etiquetas(_camada(metodologia, 3), "municipio")
    assert publicadas == {"Livre", "Adensar", "Disputa"}

    for n, esperada in [(0, "Livre"), (pilot.CONC_ADENSAR_MAX, "Adensar"), (99, "Disputa")]:
        linha = pd.Series({"n_concorrentes_est": n})
        etiqueta, _t, _c = pilot._etiqueta("conc. 2 km", 5000.0, 1, linha)
        assert etiqueta == esperada, f"{n} concorrentes -> {etiqueta}, painel diz {esperada}"


def test_camada_4_publica_as_faixas_de_oportunidade_do_m1(metodologia):
    """A fila rotula pela faixa do M1 desde o BLK-MAPA-FAIXAS-01, nao por posicao."""
    publicadas = _etiquetas(_camada(metodologia, 4), "municipio")
    assert publicadas == set(FAIXA_LABELS.values())

    for bruto, rotulo in FAIXA_LABELS.items():
        linha = pd.Series({"_fila": True, "faixa_oportunidade": bruto, "n_concorrentes_est": 0})
        etiqueta, _t, _c = pilot._etiqueta("residual", 5000.0, 1, linha)
        assert etiqueta == rotulo


def test_nenhuma_etiqueta_extinta_sobrevive_no_painel(metodologia):
    """Trava a classe inteira do defeito, nao um caso.

    Se alguem reintroduzir um vocabulario aposentado no painel (ou o painel deixar de
    acompanhar uma troca de regua no funil), este teste falha com o nome do intruso.
    """
    intrusos = {
        (c["n"], f["etiqueta"])
        for c in metodologia["camadas"]
        for f in c["faixas"]
        if f["etiqueta"] in _EXTINTOS
    }
    assert not intrusos, (
        f"o painel publica etiquetas que o funil nao emite mais: {sorted(intrusos)}. "
        "As faixas vigentes vivem em constants.FAIXAS_MAPA_* e em FAIXA_LABELS."
    )


# ------------------------------------------------------------ cortes e parametros
def test_cortes_publicados_batem_com_as_constantes_do_funil(metodologia):
    """Os numeros do texto saem da constante que o funil usa — sem numero a mao."""
    c1 = _camada(metodologia, 1)["corte"]
    assert f"{pilot.SCORE_CORTE_QUENTE:.0f}" in c1
    assert f"{pilot.POP_MIN_ACIONAVEL:,.0f}".replace(",", ".") in c1

    c2 = _camada(metodologia, 2)["corte"]
    assert f"{pilot.OFERTA_DESTAQUE_MIN:,.0f}".replace(",", ".") in c2

    assert str(pilot.FILA_MAX) in _camada(metodologia, 4)["corte"]


def test_a_fila_nao_promete_fallback_para_regiao_disputada(metodologia):
    """O #184 removeu o fallback por decisao do dono (2026-08-03); o painel dizia que
    ele existia. Municipio saturado mostra fila VAZIA — se o texto prometer recurso a
    hex disputado, o usuario conclui que a tela esta quebrada."""
    regra = " ".join(m["regra"] for m in _camada(metodologia, 4)["metricas"])
    assert "aceitando disputa" not in regra
    assert "recorre" not in regra

    # E o codigo de fato nao tem o fallback: sem area livre, a fila sai vazia.
    df = pd.DataFrame(
        {
            "hex_id": ["8a1", "8a2"],
            "nome_municipio": ["Cidade", "Cidade"],
            "n_concorrentes_est": [3, 5],
            "oferta_efetiva_disponivel": [9000.0, 8000.0],
            "score_setor_2022_calibrado": [90.0, 88.0],
            "pop_leitura": [30000, 28000],
        }
    )
    passos = pilot.montar_funil(df, "Cidade", {})
    assert passos[3]["itens"] == []
