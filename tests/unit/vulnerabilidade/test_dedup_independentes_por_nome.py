"""Dedup de INDEPENDENTES por NOME dentro da MESMA fonte - opt-in, default intacto.

**O buraco que este parametro alcanca, medido em 2026-09-10 sobre a semana `2026-33`.**
`dedup_independentes` so' colapsa entre fontes DIFERENTES, e nesta estacao so' ha' WellHub: a
guarda de fonte zera a dedup inteira e **nenhuma das 19.329 independentes e' deduplicada hoje**.
Pares reais que sobrevivem: `Studio Plena Forma` x `Academia Plena Forma` a **0,0 m**,
`Academia Life Gym` x `Life Gym` a **0,77 m**, `Krypton Orly` x `Krypton - Jd.Orly` a **0,0 m**.

**E por que a correcao e' o NOME e nao o raio** - o pedido original era subir o raio para 300 m:

    | raio  | pares proximos | mesmo estabelecimento | academias DISTINTAS que o raio apagaria |
    |-------|----------------|-----------------------|-----------------------------------------|
    |  50 m |   543          |  64 (11,79%)          |   479                                   |
    | 150 m | 1.878          |  70 ( 3,73%)          | 1.808                                   |
    | 300 m | 5.239          |  81 ( 1,55%)          | 5.158                                   |

A 300 m, 98,45% dos pares proximos sao academias distintas. Apagar concorrente real e' o falso zero
que a DEC-033 existe para matar - o raio puro anda na direcao errada, e o nome nao precisa de raio
grande (64 dos 81 pares ja' estao a menos de 50 m).

O que estes testes protegem:

  1. **O default e' intacto** - sem o parametro, nada colapsa dentro da mesma fonte. E' a trava que
     impede o numero de mudar sozinho para quem roda o pipeline hoje.
  2. **A duplicata da mesma fonte colapsa quando o nome casa** - e' o ganho.
  3. **O vizinho de nome diferente NAO colapsa**, por mais perto que esteja - e' o custo evitado, e
     e' o que separa esta regra de "subir o raio".
  4. **A irma numerada nao colapsa** - a regra de negacao por ordinal continua valendo.
  5. **O teto de distancia continua valendo** - nome igual longe demais sao duas academias.
  6. **Sem a coluna `nome`, a passagem degrada** para o comportamento anterior.
  7. **A dedup ENTRE fontes segue como era** - o parametro acrescenta uma passagem, nao substitui.

READ-ONLY sobre o M1: nada aqui toca score do M1, pesos, `config.py` ou artefato oficial.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from motor_expansao.vulnerabilidade.contrato import DEDUP_INDEPENDENTES_NOME_M
from motor_expansao.vulnerabilidade.identidade import mesmo_estabelecimento
from motor_expansao.vulnerabilidade.pressao_competitiva import dedup_independentes

_LAT, _LNG = -23.5500, -46.6300
_GRAU_LAT_M = 111_320.0


def _norte(metros: float) -> float:
    return _LAT + metros / _GRAU_LAT_M


def _frame(linhas: list[tuple[str, str, float, str]], *, com_nome: bool = True) -> pd.DataFrame:
    """`(fonte, chave, metros ao norte, nome)`."""
    dados: dict[str, list[object]] = {
        "fonte": [f for f, _, _, _ in linhas],
        "chave_snapshot": [k for _, k, _, _ in linhas],
        "lat": [_norte(m) for _, _, m, _ in linhas],
        "lng": [_LNG] * len(linhas),
    }
    if com_nome:
        dados["nome"] = [n for _, _, _, n in linhas]
    return pd.DataFrame(dados)


# --------------------------------------------------------------------------- #
# 1. O DEFAULT e' intacto - a trava contra a mudanca silenciosa                #
# --------------------------------------------------------------------------- #
def test_default_nao_colapsa_nada_dentro_da_mesma_fonte() -> None:
    """Sem o parametro, duas linhas WellHub de nome IDENTICO a 0 m continuam sendo duas.

    E' o comportamento de hoje, e ele tem de sobreviver a existencia do parametro novo: quem roda o
    pipeline sem pedir nada nao pode ver `pressao_competitiva` mudar.
    """
    base = _frame(
        [
            ("wellhub", "k1", 0.0, "Academia Plena Forma"),
            ("wellhub", "k2", 0.0, "Academia Plena Forma"),
        ]
    )
    sobreviventes, mapa = dedup_independentes(base)

    assert len(sobreviventes) == 2, "o default colapsou dentro da mesma fonte"
    assert mapa[("wellhub", "k1")] != mapa[("wellhub", "k2")]


def test_default_explicito_none_e_o_mesmo_que_omitir() -> None:
    """`nome_mesma_fonte_m=None` nao e' um valor especial de ligacao - e' o desligado."""
    base = _frame([("wellhub", "k1", 0.0, "Box Insano"), ("wellhub", "k2", 2.0, "Box Insano")])
    assert len(dedup_independentes(base, nome_mesma_fonte_m=None)[0]) == 2


# --------------------------------------------------------------------------- #
# 2. O ganho: a duplicata da MESMA fonte colapsa quando o nome casa            #
# --------------------------------------------------------------------------- #
def test_par_real_studio_plena_forma_colapsa_com_o_parametro() -> None:
    """`Studio Plena Forma` x `Academia Plena Forma` a 0,0 m - par real do feed."""
    base = _frame(
        [
            ("wellhub", "k1", 0.0, "Studio Plena Forma"),
            ("wellhub", "k2", 0.0, "Academia Plena Forma"),
        ]
    )
    sobreviventes, mapa = dedup_independentes(base, nome_mesma_fonte_m=DEDUP_INDEPENDENTES_NOME_M)

    assert len(sobreviventes) == 1, "a duplicata da mesma fonte tinha de colapsar pelo nome"
    assert mapa[("wellhub", "k1")] == mapa[("wellhub", "k2")] == 0, (
        "a colapsada precisa apontar para a posicao da sobrevivente, senao a auto-exclusao "
        "zera a parcela errada"
    )


def test_nome_generico_identico_colapsa_pelo_ramo_de_igualdade_exata() -> None:
    """`Academia Fitness` x `Academia Fitness`: discriminante VAZIO dos dois lados.

    `similaridade_nome` devolve `0` no caso vazio - de proposito e conservadoramente. Sem o ramo de
    igualdade exata do nome normalizado, estes 5 pares medidos ficariam de fora.
    """
    assert mesmo_estabelecimento("Academia Fitness", "ACADEMIA FITNESS.") is True
    base = _frame(
        [
            ("wellhub", "k1", 0.0, "Academia Fitness"),
            ("wellhub", "k2", 1.0, "ACADEMIA FITNESS."),
        ]
    )
    assert len(dedup_independentes(base, nome_mesma_fonte_m=150.0)[0]) == 1


# --------------------------------------------------------------------------- #
# 3. O custo evitado: o vizinho perto com nome diferente NAO colapsa           #
# --------------------------------------------------------------------------- #
def test_vizinho_a_zero_metro_com_nome_diferente_NAO_colapsa() -> None:
    """`Cross Matilha` x `Studio Renata Simoes` a 0,0 m - par REAL, duas academias distintas.

    E' o caso que refuta "sobe o raio": a 300 m, 98,45% dos pares de independentes proximas sao
    exatamente isto. O nome e' o que separa os dois casos, e a distancia sozinha nao separa nada.
    """
    base = _frame(
        [
            ("wellhub", "k1", 0.0, "Cross Matilha"),
            ("wellhub", "k2", 0.0, "Studio Renata Simoes"),
        ]
    )
    assert len(dedup_independentes(base, nome_mesma_fonte_m=300.0)[0]) == 2


def test_irma_numerada_da_mesma_fonte_NAO_colapsa() -> None:
    """`Iron Gym` x `Iron Gym 2`: discriminante identico, ordinal diferente -> duas academias."""
    base = _frame([("wellhub", "k1", 5.0, "Iron Gym"), ("wellhub", "k2", 0.0, "Iron Gym 2")])
    assert len(dedup_independentes(base, nome_mesma_fonte_m=150.0)[0]) == 2


# --------------------------------------------------------------------------- #
# 4. Os tetos: distancia e coluna ausente                                      #
# --------------------------------------------------------------------------- #
def test_nome_identico_alem_do_limiar_NAO_colapsa() -> None:
    """Duas `Box Insano` a 400 m com o parametro em 150 m continuam sendo duas."""
    base = _frame([("wellhub", "k1", 0.0, "Box Insano"), ("wellhub", "k2", 400.0, "Box Insano")])
    assert len(dedup_independentes(base, nome_mesma_fonte_m=150.0)[0]) == 2
    assert len(dedup_independentes(base, nome_mesma_fonte_m=500.0)[0]) == 1


def test_sem_coluna_nome_a_passagem_degrada_em_silencio_controlado() -> None:
    """Pedir a passagem sem a coluna `nome` nao levanta - degrada para o comportamento anterior."""
    base = _frame(
        [("wellhub", "k1", 0.0, "Box Insano"), ("wellhub", "k2", 2.0, "Box Insano")],
        com_nome=False,
    )
    assert len(dedup_independentes(base, nome_mesma_fonte_m=150.0)[0]) == 2


# --------------------------------------------------------------------------- #
# 5. A passagem ANTIGA (entre fontes) segue como era                           #
# --------------------------------------------------------------------------- #
def test_dedup_entre_fontes_por_distancia_continua_valendo_com_o_parametro() -> None:
    """TotalPass x WellHub a 40 m colapsam por DISTANCIA, com nomes que nao se parecem.

    O parametro ACRESCENTA uma passagem; se ele tivesse substituido a antiga, este par (que e' o
    defeito que `DEDUP_INDEPENDENTES_M` existe para fechar) voltaria a contar em dobro.
    """
    base = _frame(
        [
            ("totalpass", "k1", 0.0, "Cross Matilha"),
            ("wellhub", "k2", 40.0, "Studio Renata Simoes"),
        ]
    )
    assert len(dedup_independentes(base)[0]) == 1
    assert len(dedup_independentes(base, nome_mesma_fonte_m=150.0)[0]) == 1


def test_default_do_ponto_de_entrada_de_producao_nao_mudou() -> None:
    """Trava a assinatura de `calcular_pressao_por_academia`, que e' o que a producao chama.

    A trava de comportamento uma camada abaixo (`dedup_independentes`) NAO pega este caso:
    medido por mutacao, trocar os dois defaults AQUI passava a suite inteira em verde
    (571 passed), porque nenhum teste referenciava os parametros novos pelo nome. E o pedido
    era explicito -- o comportamento de hoje continua sendo o default, e quem rodar o
    pipeline nao pode ver o numero mudar sozinho.
    """
    import inspect

    from motor_expansao.vulnerabilidade.contrato import DEDUP_CADEIA_FEED_M
    from motor_expansao.vulnerabilidade.pressao_competitiva import calcular_pressao_por_academia

    p = inspect.signature(calcular_pressao_por_academia).parameters
    # `None` = passagem por nome DESLIGADA nas independentes.
    assert p["dedup_independentes_nome_m"].default is None
    # O raio das cadeias segue o do contrato -- 300 m so' entra por DEC.
    assert p["dedup_cadeia_feed_m"].default == DEDUP_CADEIA_FEED_M
    assert DEDUP_CADEIA_FEED_M == 150.0


# --------------------------------------------------------------------------- #
# 8. O DESEMPATE entre fontes (DEC-063) - o nome escolhe, a distancia so' decide o empate          #
# --------------------------------------------------------------------------- #
def test_entre_fontes_o_nome_vence_o_candidato_mais_proximo() -> None:
    """O caso `Agoge`, sintetizado: colapsar no mais PERTO apagava a academia errada.

    Ate' a DEC-063 a passagem por distancia pegava o PRIMEIRO candidato na ordem do `grid_disk` --
    arbitraria -- e dava `break`. Medido em 91 pares, o escolhido era OUTRA academia, e o erro era
    DUPLO: a unidade sumia dentro de quem ela nao e', e a gemea verdadeira sobrevivia em separado.
    No dado real: `Academia Agoge` colapsava contra `SCoccorese - Pilates` a 0,0 m tendo
    `Agoge Academia` a 3,3 m.

    Ordem estavel `(fonte, chave)`: as `totalpass` viram ocupantes primeiro, a `wellhub` colapsa.
    """
    base = _frame(
        [
            ("totalpass", "a", 0.0, "SCoccorese - Pilates"),
            ("totalpass", "b", 30.0, "Academia Agoge"),
            ("wellhub", "z", 5.0, "Agoge Academia"),
        ]
    )
    sobreviventes, mapa = dedup_independentes(base)

    assert len(sobreviventes) == 2, "as duas do TotalPass sao da MESMA fonte: nunca colapsam"
    assert mesmo_estabelecimento("Agoge Academia", "Academia Agoge") is True
    assert mapa[("wellhub", "z")] == 1, (
        "colapsou no vizinho mais PROXIMO (o pilates, posicao 0) em vez da gemea pelo NOME"
    )


def test_entre_fontes_sem_casamento_de_nome_vence_o_mais_proximo() -> None:
    """Sem nome que case, o desempate cai na distancia - e nao no primeiro que o bucket devolver.

    O nome DESEMPATA e nunca EXIGE: exigi-lo recusaria 3.060 colapsos reais a mediana de 6,2 m,
    porque as duas fontes escrevem o nome de formas que o matcher nao concilia.
    """
    base = _frame(
        [
            ("totalpass", "a", 0.0, "Alfa Fitness"),
            ("totalpass", "b", 30.0, "Beta Fitness"),
            ("wellhub", "z", 5.0, "Gama Fitness"),
        ]
    )
    sobreviventes, mapa = dedup_independentes(base)

    assert len(sobreviventes) == 2
    assert mapa[("wellhub", "z")] == 0, "sem casamento de nome, o representante e' o mais proximo"


def test_o_desempate_vale_no_caminho_PADRAO_sem_o_parametro_da_mesma_fonte() -> None:
    """A trava contra o defeito que quase entrou: o desempate amarrado ao opt-in errado.

    O vetor de nomes so' era preenchido quando `nome_mesma_fonte_m` estava ligado -- e o default
    dele e' `None`. Amarrado assim, o desempate entre fontes ficaria INERTE na configuracao de
    producao: verde, e sem fazer nada. Este teste chama SEM o parametro de proposito.
    """
    base = _frame(
        [
            ("totalpass", "a", 0.0, "Studio Pina"),
            ("totalpass", "b", 20.0, "Academia Vida Fitness"),
            ("wellhub", "z", 3.0, "ACADEMIA VIDA FITNESS"),
        ]
    )
    _sobreviventes, mapa = dedup_independentes(base)  # sem `nome_mesma_fonte_m`
    assert mapa[("wellhub", "z")] == 1, "o desempate nao vale sem o opt-in da MESMA fonte"


def test_sem_coluna_nome_o_desempate_cai_na_distancia_sem_quebrar() -> None:
    """Frame sem `nome` continua valido: o desempate degrada para distancia, nao levanta."""
    base = _frame(
        [
            ("totalpass", "a", 0.0, "irrelevante"),
            ("totalpass", "b", 30.0, "irrelevante"),
            ("wellhub", "z", 5.0, "irrelevante"),
        ],
        com_nome=False,
    )
    _sobreviventes, mapa = dedup_independentes(base)
    assert mapa[("wellhub", "z")] == 0


def test_a_ligacao_de_producao_repassa_o_parametro_da_mesma_fonte(monkeypatch) -> None:
    """O defeito que este teste previne JA' ACONTECEU: implementada, testada e SEM CHAMADOR.

    `nome_mesma_fonte_m` existe desde 2026-09-10 e `_pressao_por_academia` nunca a repassou, entao
    ela ficava no default `None` e as 70 duplicatas internas do WellHub seguiam intactas -- cada uma
    se AUTO-PRESSIONANDO (`Imperio Fitness Academia` e `IMPERIO FITNESS ACADEMIA`, ambas
    43,33 -> 30,00). A DEC-062 chegou a registrar que criou o opt-in e nao o ligou.

    Guardar a EXISTENCIA do parametro nao teria pego isso; e' preciso guardar a CHAMADA.
    """
    from motor_expansao.vulnerabilidade import alvos_ma as m_alvos
    from motor_expansao.vulnerabilidade import pressao_competitiva as m_pressao

    capturado: dict[str, object] = {}

    def _falso(academias, concorrentes, **kwargs):  # noqa: ANN001, ANN003
        capturado.update(kwargs)
        return pd.DataFrame({"fonte": [], "chave_snapshot": [], "pressao_competitiva": []})

    monkeypatch.setattr(m_pressao, "calcular_pressao_por_academia", _falso)
    monkeypatch.setattr(m_pressao, "ler_concorrentes", lambda _p: pd.DataFrame())

    academias = pd.DataFrame(
        {
            "fonte": ["wellhub"],
            "chave_snapshot": ["k"],
            "nome": ["Academia X"],
            "lat": [_LAT],
            "lng": [_LNG],
            "rede": ["independente"],
        }
    )
    caminho = Path(m_alvos.__file__)  # existe; so' precisa passar no `.exists()`
    m_alvos._pressao_por_academia(caminho, academias)

    assert capturado.get("dedup_independentes_nome_m") == DEDUP_INDEPENDENTES_NOME_M, (
        "a passagem por NOME da mesma fonte voltou a ficar sem chamador"
    )
