"""Contrato: `web/src/lib/faixas.ts` ESPELHA `constants.FAIXAS_MAPA_*` (BLK-MAPA-FAIXAS-01).

Por que o espelho existe: a legenda do mapa e desenhada pelo React (TypeScript) e a
etiqueta de cada item do ranking e calculada pelo backend (Python). Se as duas listas
divergirem, a MESMA regiao aparece com dois nomes na mesma tela — foi exatamente o
defeito medido em 2026-08-03 (2.400 alunos = "Baixa" na etiqueta e "Livre" na legenda),
que motivou unificar a regua.

Nao da para o front importar o modulo Python, entao a copia e inevitavel; o que este
teste garante e que ela nao SILENCIA. Mesmo padrao de `SCORE_BANDS_HEX` x
`RESIDUAL_SCORE_BANDS`, so que verificado.

READ-ONLY: le os dois arquivos, nao escreve nada.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from motor_expansao.dashboard.constants import (
    CAPACIDADE_UNIDADE_ALUNOS,
    FAIXAS_MAPA_DEMANDA,
    FAIXAS_MAPA_POTENCIAL,
    faixa_do_score,
)

_FAIXAS_TS = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "faixas.ts"

# `{ de: 0, ate: 20, nome: 'Saturado', cor: '#B92323' },`
_LINHA = re.compile(
    r"\{\s*de:\s*(\d+),\s*ate:\s*(\d+),\s*nome:\s*'([^']+)',\s*cor:\s*'(#[0-9A-Fa-f]{6})'\s*\}"
)


def _faixas_do_ts(nome_const: str) -> list[tuple[int, int, str, str]]:
    """Extrai uma lista de faixas do `faixas.ts` por parse textual (sem Node)."""
    fonte = _FAIXAS_TS.read_text(encoding="utf-8")
    inicio = fonte.index(f"export const {nome_const}")
    # Ancora no "= [" e nao no primeiro "]": a anotacao de tipo `FaixaNomeada[]` vem
    # ANTES do array e fecharia o bloco vazio.
    abre = fonte.index("= [", inicio) + len("= [")
    fim = fonte.index("]", abre)
    bloco = fonte[abre:fim]
    return [(int(a), int(b), nome, cor) for a, b, nome, cor in _LINHA.findall(bloco)]


@pytest.mark.parametrize(
    ("const_py", "const_ts"),
    [
        (FAIXAS_MAPA_POTENCIAL, "FAIXAS_POTENCIAL"),
        (FAIXAS_MAPA_DEMANDA, "FAIXAS_DEMANDA"),
    ],
)
def test_ts_espelha_o_python(const_py, const_ts):
    do_ts = _faixas_do_ts(const_ts)
    # O Python carrega um 5o campo (`tom` do chip) que a legenda do front nao usa.
    do_py = [(de, ate, nome, cor) for de, ate, nome, cor, _tom in const_py]
    assert do_ts == do_py, (
        f"{const_ts} em faixas.ts divergiu de constants.py. O Python e a FONTE DA "
        f"VERDADE — ajuste o .ts.\n  python: {do_py}\n  ts ...: {do_ts}"
    )


@pytest.mark.parametrize("faixas", [FAIXAS_MAPA_POTENCIAL, FAIXAS_MAPA_DEMANDA])
def test_faixas_cobrem_0_a_100_sem_lacuna_nem_sobreposicao(faixas):
    assert faixas[0][0] == 0
    assert faixas[-1][1] == 100
    for anterior, atual in zip(faixas, faixas[1:], strict=False):
        # `ate` de uma e' o `de` da seguinte: score sem faixa (lacuna) ou com duas
        # (sobreposicao) seria bug silencioso na etiqueta.
        assert atual[0] == anterior[1]


def test_faixa_do_score_nos_limites():
    # Limite inferior INCLUSIVO, superior EXCLUSIVO; 100 fecha na ultima.
    assert faixa_do_score(0, FAIXAS_MAPA_DEMANDA)[0] == "Saturado"
    assert faixa_do_score(19.9, FAIXAS_MAPA_DEMANDA)[0] == "Saturado"
    assert faixa_do_score(20, FAIXAS_MAPA_DEMANDA)[0] == "Restrito"
    assert faixa_do_score(100, FAIXAS_MAPA_DEMANDA)[0] == "Livre"
    # Fora da escala satura em vez de estourar (o score do M1 ja vem clipado, mas a
    # etiqueta converte de alunos e pode passar de 100).
    assert faixa_do_score(250, FAIXAS_MAPA_DEMANDA)[0] == "Livre"
    assert faixa_do_score(-5, FAIXAS_MAPA_DEMANDA)[0] == "Saturado"
    assert faixa_do_score(None, FAIXAS_MAPA_DEMANDA) == ("", "")


def test_regressao_do_defeito_de_campinas():
    """2.400 alunos NAO podem mais sair como 'Baixa'.

    Era o caso concreto que expunha as duas reguas: 2.400 alunos e 96% da capacidade
    de uma unidade (2.500), entao a legenda dizia "Livre" enquanto a etiqueta, com
    corte proprio em 3.000, dizia "Baixa".
    """
    score = 100.0 * 2400 / CAPACIDADE_UNIDADE_ALUNOS
    nome, _tom = faixa_do_score(score, FAIXAS_MAPA_DEMANDA)
    assert nome == "Livre"


def test_narrativa_do_funil_nao_usa_vocabulario_de_faixa_extinta():
    """O texto do funil nao pode citar nome de faixa que nao existe mais.

    Defeito real (Juan, 2026-08-03): as faixas viraram Desfavoravel/Fraco/Promissor/
    Forte/Excelente, mas a narrativa e o `funil_unit` continuaram dizendo "hexagonos
    quentes" — palavra que sumiu da legenda. A tela ficou falando dois idiomas: o
    painel dizia "134 hexagonos quentes" e a legenda ao lado nao tinha nenhum bloco
    com esse nome.

    Este teste varre os TEXTOS de usuario de `web/server/app.py` atras de termos
    aposentados. Nao olha nome de variavel: `quentes` como identificador Python
    segue valido (e' o subconjunto filtrado), o que nao pode e' vazar para a tela.
    """
    app_py = Path(__file__).resolve().parents[2] / "web" / "server" / "app.py"
    fonte = app_py.read_text(encoding="utf-8")

    # So linhas de texto exibido: narrativa, funil_unit, funil_from e f-strings de UI.
    suspeitas = [
        linha.strip()
        for linha in fonte.splitlines()
        if ("hexágonos quentes" in linha or "Hexágono quente" in linha)
    ]
    assert not suspeitas, (
        "vocabulario de faixa extinta ('quente') voltou aos textos do funil; as faixas "
        f"atuais estao em constants.FAIXAS_MAPA_POTENCIAL. Linhas: {suspeitas}"
    )


def test_narrativa_da_uf_concorda_em_numero():
    """'em 1 municípios' era plural fixo — defeito visivel na tela do Juan."""
    app_py = Path(__file__).resolve().parents[2] / "web" / "server" / "app.py"
    fonte = app_py.read_text(encoding="utf-8")
    assert "'município' if n_munis == 1 else 'municípios'" in fonte, (
        "a narrativa da UF voltou a usar plural fixo; com 1 municipio sai 'em 1 municípios'"
    )
