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

import re
import sys
from pathlib import Path

import pandas as pd
import pytest

_SERVER = Path(__file__).resolve().parents[2] / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)

from motor_expansao.dashboard.constants import (  # noqa: E402
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


def _faixas_publicadas(camada: dict) -> list[dict]:
    """TUDO que a camada publica como etiqueta: `faixas` + `legenda_mapa`.

    Os guards deste arquivo varriam so' `faixas`. Quando a camada 4 mudou as cores do
    mapa para o campo `legenda_mapa`, o vocabulario de `cres_hex_classe` saiu junto da
    rede de protecao — passaria a deslizar em silencio exatamente como as `faixas`
    deslizaram. Todo campo que vira chip na tela entra por aqui.
    """
    return [*camada["faixas"], *camada.get("legenda_mapa", [])]


# --------------------------------------------------------------------- contrato
def test_payload_tem_as_5_camadas_completas(metodologia):
    camadas = metodologia["camadas"]
    assert [c["n"] for c in camadas] == [1, 2, 3, 4, 5]
    for c in camadas:
        assert c["titulo"] and c["pergunta"] and c["corte"]
        # `faixas` PODE ser vazio desde o BLK-MAPA-CHIP-01: onde o corte da camada iguala
        # todos os itens, ela nao emite chip e nao ha o que publicar como "etiqueta do
        # ranking" (camada 5). O que nao pode e' a camada ficar MUDA — ou publica etiqueta,
        # ou publica a rampa que pinta o mapa.
        assert c["faixas"] or c.get("legenda_mapa"), (
            f"camada {c['n']} nao publica nem etiqueta de ranking nem legenda de mapa"
        )
        for m in c["metricas"]:
            # `fonte` primeiro: a duvida inicial de quem le e' "de onde veio esse numero".
            assert m["nome"] and m["fonte"] and m["resumo"] and m["regra"]
    assert metodologia["parametros"] and metodologia["fontes"]


def test_toda_faixa_declara_escopo_valido(metodologia):
    for c in metodologia["camadas"]:
        for f in _faixas_publicadas(c):
            assert f["escopo"] in ("", "municipio", "uf"), f
            assert f["etiqueta"] and f["condicao"]


# ------------------------------------------------------- coerencia painel x funil
# BLK-MAPA-CHIP-01. Os tres testes que viviam aqui comparavam `faixas` com os nomes da
# rampa e, em seguida, chamavam `pilot._etiqueta` DIRETO com valores que o funil nunca
# entrega — `n_concorrentes_est` = 2 e 99 numa camada cuja base e o white space (n == 0).
# Passavam verdes sobre um vocabulario inalcancavel: era esse o furo. Agora a rampa e
# checada onde ela de fato vive (`legenda_mapa`, o universo que o mapa pinta) e a
# etiqueta do ranking e checada ATRAVES do funil, em
# `tests/unit/test_piloto_web_endpoints.py::test_metodologia_nao_reescreve_o_chip_*`.
@pytest.mark.parametrize(
    ("n", "faixas_do_codigo"),
    [
        (1, {nome for *_r, nome, _cor, _tom in FAIXAS_MAPA_POTENCIAL}),
        (2, {nome for *_r, nome, _cor, _tom in FAIXAS_MAPA_DEMANDA}),
        (3, {nome for *_r, nome, _cor, _tom in FAIXAS_MAPA_DEMANDA}),
        (5, set(FAIXA_LABELS.values())),
    ],
    ids=["potencial", "demanda", "concorrencia", "oportunidade-m1"],
)
def test_a_rampa_do_mapa_vive_em_legenda_mapa(metodologia, n, faixas_do_codigo):
    """A rampa continua publicada — no slot das CORES DO MAPA, com a cor exata.

    Separar `faixas` de `legenda_mapa` nao pode virar "sumir com a legenda": o hexagono
    de score 45 continua laranja no mapa e precisa do bloco correspondente no manual.
    """
    camada = _camada(metodologia, n)
    legenda = camada.get("legenda_mapa") or []
    assert {f["etiqueta"] for f in legenda} == faixas_do_codigo

    for f in legenda:
        assert f["cor"], (
            f"camada {n}: a faixa {f['etiqueta']!r} foi publicada sem cor. A paleta de 5 "
            "`tom` nomeados nao cobre a rampa 1:1 — foi assim que 'Excelente' saiu azul no "
            "manual e verde-escuro no ranking."
        )
        assert f["escopo"] == "", (
            f"camada {n}: a rampa voltou a ser publicada por escopo ({f['escopo']!r}). O mapa "
            "pinta igual nos dois, e publicar duas vezes duplica a linha e a `key` do React."
        )


def test_nenhum_nome_de_faixa_sobrou_na_etiqueta_do_ranking(metodologia):
    """O outro lado: o slot "etiquetas do ranking" nao publica mais nome de faixa.

    Era o defeito medido — o painel anunciava 5 faixas por camada e o ranking emitia UMA,
    porque o corte de cada camada coincide com o piso da ultima. "Amplo: 1.500 a 2.000
    alunos" aparecia logo abaixo de "corte: residual >= 2.000 alunos".
    """
    nomes = (
        {nome for *_r, nome, _cor, _tom in FAIXAS_MAPA_POTENCIAL}
        | {nome for *_r, nome, _cor, _tom in FAIXAS_MAPA_DEMANDA}
        | set(FAIXA_LABELS.values())
    )
    intrusas = {
        (c["n"], f["etiqueta"])
        for c in metodologia["camadas"]
        for f in c["faixas"]
        if f["etiqueta"] in nomes
    }
    assert not intrusas, f"nome de faixa de volta no slot do ranking: {sorted(intrusas)}"


def test_todo_corte_que_satura_declara_por_que(metodologia):
    """Criterio de aceite 3, segunda porta: onde o chip nao pode discriminar, o painel diz.

    Camadas 1, 3 e 5 tem itens sem etiqueta em pelo menos um escopo. Isso so nao e lido
    como bug de render se o campo `corte` explicar que a faixa e constante POR CONSTRUCAO
    do proprio corte.
    """
    esperado = {
        1: "Forte ou Excelente",
        2: "piso exato da faixa Livre",
        3: "Adensar e Disputa",
        5: "prioridade máxima",
    }
    for n, trecho in esperado.items():
        corte = _camada(metodologia, n)["corte"]
        assert trecho in corte, (
            f"camada {n}: o campo `corte` deixou de declarar a saturacao (esperava conter "
            f"{trecho!r}). Texto atual: {corte!r}"
        )


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


def test_camada_4_publica_as_etiquetas_que_o_ranking_emite(metodologia):
    """A camada 4 tinha intersecao VAZIA entre publicado e emitido.

    O painel publicava as quatro classes de `cres_hex_classe` (Em alta / Estável / Sem
    obra nova / Sem medição) no slot que o front rotula "etiquetas do ranking", enquanto
    o chip de cada item saia de `_etiqueta_crescimento`, com vocabulario inteiramente
    outro (posicao relativa a mediana da UF). Nenhuma das quatro publicadas aparecia na
    lista, e nenhuma das emitidas estava no manual.

    O defeito nasceu de uma CORRECAO: `_etiqueta_crescimento` trocou o vocabulario para
    fugir da colisao com `cres_hex_classe`, e o painel ficou com o vocabulario velho.
    Por isso este teste compara CONJUNTOS de verdade, exercitando o funil — as camadas
    1, 2, 3 e 5 ja tinham teste assim; a 4 so' tinha o de "nao filtra".

    Escopo `uf`: no funil municipal o passo 4 sai com `itens: []`, entao nao ha chip.
    """
    c4 = _camada(metodologia, 4)
    publicadas = _etiquetas(c4, "uf")
    assert publicadas, "a camada 4 nao publica etiqueta de ranking nenhuma"

    # Nenhuma etiqueta do escopo `municipio`: la nao existe ranking para explicar.
    assert not _etiquetas(c4, "municipio") - publicadas

    # As cores do MAPA continuam publicadas, mas fora do slot de ranking.
    legenda = {f["etiqueta"] for f in c4.get("legenda_mapa", [])}
    assert legenda == {"Em alta", "Estável", "Sem obra nova", "Sem medição"}
    assert not (legenda & publicadas), (
        "vocabulario da COR DO MAPA voltou para o slot de etiqueta do ranking: "
        f"{sorted(legenda & publicadas)}"
    )

    # Agora o cruzamento de verdade: roda o funil e exige IGUALDADE entre publicado e
    # emitido — a mesma forma das camadas 1, 2, 3 e 5, nao um subconjunto. Subconjunto
    # deixaria passar o outro lado do defeito: etiqueta no manual que o ranking nunca
    # emite, a "faixa inalcancavel" que este arquivo ja pegou tres vezes.
    #
    # O ramo do multiplicador vira `N×` no painel, porque o numero varia com o dado —
    # normalizamos os dois lados para compara-los.
    def _norma(s: str) -> str:
        return re.sub(r"\d+×", "N×", s)

    def _emitidas(cres: list[float], mediana: float) -> set[str]:
        # `len(cres) <= FILA_MAX` de proposito: o passo 4 corta o ranking em
        # `head(FILA_MAX)` por valor DESCENDENTE, entao uma lista maior descartaria
        # justo o municipio em queda — foi assim que a 1a versao deste teste nunca
        # exercitou o ramo "emprego em queda" e mesmo assim ficou verde.
        assert len(cres) <= pilot.FILA_MAX, "o head(FILA_MAX) engoliria uma amostra"
        n = len(cres)
        df = pd.DataFrame(
            {
                "hex_id": [f"8a{i:02d}" for i in range(n)],
                "nome_municipio": [f"Cidade{i}" for i in range(n)],
                "n_concorrentes_est": [0] * n,
                "oferta_efetiva_disponivel": [9000.0 - i * 100 for i in range(n)],
                "score_setor_2022_calibrado": [90.0 - i * 0.5 for i in range(n)],
                "pop_leitura": [30000 - i * 100 for i in range(n)],
                "cres_emp_pct": cres,
                "cres_uf_mediana": [mediana] * n,
                "cres_hex_classe": ["Em alta"] * n,
            }
        )
        return {
            _norma(i["tag"])
            for i in pilot.montar_funil_uf(df, "SP")[3]["itens"]
            if i.get("tag")
        }

    # `_etiqueta_crescimento` tem DOIS caminhos, e so os dois juntos cobrem a lista
    # publicada. Por RAZAO (mediana acima de `_CRESC_PISO_MEDIANA`): queda, multiplos
    # da mediana, perto dela e abaixo.
    razao = _emitidas([-2.0, 30.0, 12.0, 9.0, 6.0, 5.0, 4.0, 2.0, 1.0, 0.5], 5.0)
    # Por DEFESA (mediana degenerada, abaixo do piso): o vocabulario em pontos
    # percentuais, que so acorda no dia em que um recorte novo achatar a mediana da UF.
    defesa = _emitidas([-2.0, 11.0, 3.0, 1.0], 0.5)
    emitidas = razao | defesa
    assert emitidas, "o passo 4 da UF nao emitiu nenhuma etiqueta"
    assert emitidas == {_norma(e) for e in publicadas}, (
        "camada 4 fora de sincronia. Emitidas e nao publicadas: "
        f"{sorted(emitidas - {_norma(e) for e in publicadas})}; "
        f"publicadas e nunca emitidas: {sorted({_norma(e) for e in publicadas} - emitidas)}"
    )


def test_nenhuma_etiqueta_extinta_sobrevive_no_painel(metodologia):
    """Trava a classe inteira do defeito, nao um caso.

    Se alguem reintroduzir um vocabulario aposentado no painel (ou o painel deixar de
    acompanhar uma troca de regua no funil), este teste falha com o nome do intruso.
    """
    intrusos = {
        (c["n"], f["etiqueta"])
        for c in metodologia["camadas"]
        for f in _faixas_publicadas(c)
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
