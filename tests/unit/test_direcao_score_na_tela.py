"""A tela declara a DIREÇÃO do score, e a direção declarada bate com a do contrato.

Por que este teste existe (revisão de Vinicius, 2026-08-14): o tooltip mostrava
`Score 63,0 / 100` sem eixo. No resto do piloto, TODO score segue a convenção "alto = melhor
oportunidade de ABRIR" — `score_priorizacao` do M1, `score_setor_2022_calibrado`,
`score_oportunidade_residual`. O score da camada de M&A mede o oposto: quanto MAIOR, mais cercada
está a academia. Um número de 0 a 100 sem eixo declarado, numa tela cujos vizinhos usam a convenção
inversa, é lido ao contrário — e foi.

O teste trava DUAS coisas que só juntas resolvem o problema:

  1. **A tela declara a direção.** Se a seta/nota sumir numa refatoração, a ambiguidade volta em
     silêncio: nada quebra, o número continua lá, e só um leitor atento percebe.
  2. **A direção declarada é a VERDADEIRA.** Este é o elo que impede o pior caso: alguém inverter
     o domínio de um componente no contrato (`V3_POR_STATUS_CHURN`, `_V1_POR_N_AGREGADORES`) e a
     tela seguir afirmando o eixo antigo. Aí a tela não fica ambígua — fica ERRADA, que é pior.

READ-ONLY: lê o TSX e as constantes, não escreve nada.
"""

from __future__ import annotations

import re
from pathlib import Path

from motor_expansao.vulnerabilidade.contrato import V3_POR_STATUS_CHURN

_REPO = Path(__file__).resolve().parents[2]
_HEXMAP = _REPO / "web" / "src" / "components" / "HexMap.tsx"

# `{/* ... */}` do JSX e `/* ... */` soltos. Multi-linha, não guloso.
_COMENTARIO = re.compile(r"\{?/\*.*?\*/\}?", re.DOTALL)


def _tooltip_da_independente() -> str:
    """O trecho do TSX que desenha o balão da academia independente."""
    fonte = _HEXMAP.read_text(encoding="utf-8")
    inicio = fonte.index("{indepHover && (")
    fim = fonte.index("{pinHover &&", inicio)
    return fonte[inicio:fim]


def _texto_exibido() -> str:
    """O mesmo trecho SEM comentários — só o que o operador de fato vê.

    A distinção importa: o guard de vocabulário protege a TELA, não o código-fonte. Um comentário
    que explica *por que* a palavra é proibida precisa poder citá-la; foi o primeiro falso positivo
    deste teste. Sem essa separação, a única forma de manter o guard verde seria apagar a
    explicação — punindo exatamente o comentário que impede a regra de ser desfeita por engano.
    """
    return _COMENTARIO.sub(" ", _tooltip_da_independente())


def test_a_tela_declara_a_direcao_do_numero() -> None:
    """Sem o eixo escrito, "63 de 100" é lido pela convenção dos vizinhos — que é a inversa."""
    bloco = _texto_exibido()
    assert "maior = mais cercada" in bloco, (
        "o tooltip da independente perdeu a declaração de direção. Sem ela, o operador lê o "
        "número pela convenção dos outros scores do piloto (alto = melhor), que aqui é o INVERSO."
    )
    assert bloco.count("↑") >= 2, "a seta tem de acompanhar os dois números, não só um"


def test_a_direcao_declarada_e_a_do_contrato() -> None:
    """O elo que impede a tela de afirmar um eixo que o contrato deixou de ter.

    `↑ = ↑ vulnerabilidade` é o §8.1 literal. Se alguém inverter o domínio de um componente, este
    teste falha e obriga a revisar a frase da tela junto — em vez de deixar os dois divergirem.
    """
    # O churn é o componente mais expressivo da direção: sumir do agregador é o sinal MÁXIMO.
    assert V3_POR_STATUS_CHURN["sumiu_recente"] == 1.0
    assert V3_POR_STATUS_CHURN["estavel"] == 0.0
    assert V3_POR_STATUS_CHURN["piscando"] > V3_POR_STATUS_CHURN["estavel"]

    # E o sinal 1: MENOS agregadores -> mais vulnerável -> componente MAIOR.
    from motor_expansao.vulnerabilidade.score import _V1_POR_N_AGREGADORES

    assert _V1_POR_N_AGREGADORES[1] > _V1_POR_N_AGREGADORES[2], (
        "o `v1` deixou de ser crescente na vulnerabilidade; a frase de direção do tooltip "
        "('maior = mais cercada') passou a mentir e precisa ser revista junto"
    )


def test_a_tela_nao_usa_o_vocabulario_vedado_pela_dec_028() -> None:
    """Enquanto S3/S4 estiverem imaturos, o número não pode ser rotulado de vulnerabilidade.

    Declarar a direção NÃO é licença para nomear o eixo de "fragilidade": o composto é hoje
    `30 + 40·v6`, isto é, pressão — afirmar fragilidade da academia seria vender o sinal 6 com o
    rótulo do 3, que é o que a DEC-028 proíbe.
    """
    exibido = _texto_exibido().lower()
    for proibido in ("vulnerab", "frágil", "fragil", "alvo de m&a", "aquisi"):
        assert proibido not in exibido, f"vocabulário vedado pela DEC-028 no tooltip: {proibido}"


def test_a_redundancia_entre_os_dois_numeros_e_declarada() -> None:
    """No regime `s1,s6` os dois números têm correlação 1,0 — e a tela diz isso.

    Deixar implícito faria o operador procurar significado numa diferença que não existe: o `s1`
    contribui 30 pontos FIXOS (um agregador em disco), então o composto é a pressão reescalada.
    """
    bloco = _texto_exibido()
    assert "s1,s6" in bloco, "a nota de composição sumiu ou deixou de ser condicionada ao regime"
    assert "acompanha a pressão" in bloco
