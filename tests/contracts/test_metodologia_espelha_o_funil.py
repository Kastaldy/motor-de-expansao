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
def test_payload_tem_as_5_camadas_completas(metodologia):
    camadas = metodologia["camadas"]
    assert [c["n"] for c in camadas] == [1, 2, 3, 4, 5]
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


def test_camada_4_declara_que_nao_filtra(metodologia):
    """A camada de crescimento e' CONTEXTO, e o painel tem que dizer isso.

    As outras quatro cortam: cada uma recebe o que a anterior aprovou. Esta nao — ela
    entra entre a concorrencia e a fila sem tirar ninguem e sem reordenar nada. Se o
    texto deixar isso implicito, o leitor conclui que a fila foi ordenada por
    crescimento — e ai atribui a esta camada um poder preditivo que ela declara nao
    ter, e que nada no repo mede.
    """
    c4 = _camada(metodologia, 4)
    assert "não filtra" in c4["corte"]

    # A prova tem que ser A/B, e nao a igualdade `passos[4]["funil_big"] ==
    # passos[2]["funil_big"]` que estava aqui: com 2 hexes ela era verdadeira POR
    # ACIDENTE (a fila e' nlargest(FILA_MAX=10), entao coincide com o white space
    # enquanto houver menos de 10 candidatos) e ficava vermelha com 15, sem nada
    # estar filtrando. Pior: o df nao tinha NENHUMA coluna `cres_*`, entao o caminho
    # COM dado de crescimento — o unico em que a filtragem poderia existir — nunca era
    # exercido. Aqui rodamos o mesmo funil com e sem o dado e exigimos saida identica.
    def _df(com_crescimento: bool) -> pd.DataFrame:
        n = 15  # > FILA_MAX, para a comparacao nao ser trivial
        base = {
            "hex_id": [f"8a{i:02d}" for i in range(n)],
            "nome_municipio": [f"Cidade{i % 4}" for i in range(n)],
            "n_concorrentes_est": [0] * n,
            "oferta_efetiva_disponivel": [9000.0 - i * 100 for i in range(n)],
            "score_setor_2022_calibrado": [90.0 - i * 0.5 for i in range(n)],
            "pop_leitura": [30000 - i * 100 for i in range(n)],
        }
        if com_crescimento:
            # Municipal (broadcast) + por hexagono, como o join real entrega.
            base["cres_emp_pct"] = [(-8.0 if i % 4 == 0 else 22.0) for i in range(n)]
            base["cres_hex_classe"] = [
                ("Sem obra nova" if i % 3 == 0 else "Em alta") for i in range(n)
            ]
        return pd.DataFrame(base)

    sem, com = pilot.montar_funil(_df(False), "Cidade0", {}), pilot.montar_funil(_df(True), "Cidade0", {})
    assert [p["n"] for p in com] == [1, 2, 3, 4, 5]

    # ANTI-VACUIDADE: sem isto o teste passaria mesmo que o ramo com dado nunca
    # rodasse — foi assim que a versao anterior deste teste ficou sem poder. O caso
    # "com" tem que de fato ACENDER a camada 4, e o "sem" tem que degradar.
    assert com[3]["funil_big"] > 0, "o caminho COM crescimento nao ativou a camada 4"
    assert sem[3]["funil_big"] == 0, "o caminho SEM crescimento deveria degradar"
    # O passo 5 (fila) tem que sair igual: mesmos hexes, mesma ordem.
    assert com[4]["hexes"] == sem[4]["hexes"]
    assert [i["hex_id"] for i in com[4]["itens"]] == [i["hex_id"] for i in sem[4]["itens"]]
    # E os passos anteriores tambem — a camada 4 nao pode retroagir sobre eles.
    for n_passo in (0, 1, 2):
        assert com[n_passo]["hexes"] == sem[n_passo]["hexes"]

    # Idem na visao de UF, onde a camada 4 ranqueia municipios.
    sem_uf = pilot.montar_funil_uf(_df(False), "SP")
    com_uf = pilot.montar_funil_uf(_df(True), "SP")
    assert [i["municipio"] for i in com_uf[4]["itens"]] == [
        i["municipio"] for i in sem_uf[4]["itens"]
    ]


def test_camada_5_publica_as_faixas_de_oportunidade_do_m1(metodologia):
    """A fila rotula pela faixa do M1 desde o BLK-MAPA-FAIXAS-01, nao por posicao."""
    publicadas = _etiquetas(_camada(metodologia, 5), "municipio")
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

    assert str(pilot.FILA_MAX) in _camada(metodologia, 5)["corte"]


def test_a_fila_nao_promete_fallback_para_regiao_disputada(metodologia):
    """O #184 removeu o fallback por decisao do dono (2026-08-03); o painel dizia que
    ele existia. Municipio saturado mostra fila VAZIA — se o texto prometer recurso a
    hex disputado, o usuario conclui que a tela esta quebrada."""
    regra = " ".join(m["regra"] for m in _camada(metodologia, 5)["metricas"])
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
    assert passos[4]["itens"] == []
