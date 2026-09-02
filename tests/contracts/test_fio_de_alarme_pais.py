"""Bloco A / commit A10 — o fio de alarme da DEC-047.

**A decisão inteira depende de uma coisa: não existe ramo de código por país.** O que
muda entre países são os NÚMEROS e os TEXTOS que o `perfil.json` carrega — nunca o
caminho que o código percorre. É isso que permite um binário, N containers, e é isso que
mantém os ~40 `lru_cache` do `app.py` corretos sem chave de país.

Uma decisão arquitetural sem teste é uma intenção. Este arquivo é o teste.

O que ele procura, e o que NÃO procura
--------------------------------------
Procura **comparação com literal de país**: `pais == "BR"`, `pais === 'AR'`,
`country != "CO"`. É o anti-padrão que a DEC-047 proíbe.

Não procura:

- **Guarda de nulo** (`pais === null`, `if pais is None`). Não é ramo por país: é ramo
  por "não sei o país", que é uma pergunta legítima e diferente.
- **Tabela indexada por país** (`CENSO[pais]`, `UNIDADE[pais]`). É a forma CERTA de
  variar por país — dado, não código. Acrescentar um país vira uma linha de dado.

A diferença não é estética. Medida em 2026-09-02: `web/src/lib/rodape-base.ts` trazia
três tabelas (`UNIDADE`, `CENSO`, `PONTOS`) e **um** ternário,
`pais === 'BR' ? 'IBGE' : 'INDEC'`. As tabelas aceitam a Colômbia com uma linha; o
ternário credita o INDEC a ela. Um teste que reprovasse os dois igualmente seria
desligado na primeira semana; um que reprove só o ternário é o que dá para manter.

Spec: `docs/spec_bloco_a_perfil.md` §5.9 item 3.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_RAIZES = ("src", "web", "scripts")
_SUFIXOS = (".py", ".ts", ".tsx")

#: Diretórios que não são código nosso.
_IGNORAR = {"node_modules", "dist", "__pycache__", ".venv", "build", "coverage"}

#: `<nome de país> <==|!=|===|!==> <literal de 2 letras maiúsculas>`, e o espelho.
#: `\b` nos dois lados para não casar `paisagem` nem `discountry`.
_COMPARACAO = re.compile(
    r"""\b(?:pais|país|country)\b\s*[=!]==?\s*['"][A-Z]{2}['"]"""
    r"""|['"][A-Z]{2}['"]\s*[=!]==?\s*\b(?:pais|país|country)\b""",
)

#: A única exceção: este arquivo, que traz o anti-padrão em `parametrize` para provar
#: que o regex o pega. Docstring e comentário de bloco NÃO precisam de exceção — são
#: removidos antes da varredura, e é por isso que `perfil.py` e `rodape-base.ts`, que
#: citam o padrão para proibi-lo, não aparecem aqui.
_ARQUIVOS_QUE_CITAM_O_PADRAO = {
    "tests/contracts/test_fio_de_alarme_pais.py",
}


def _fontes() -> list[Path]:
    achados: list[Path] = []
    for raiz in _RAIZES:
        base = _REPO / raiz
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.suffix not in _SUFIXOS or not p.is_file():
                continue
            if _IGNORAR & set(p.relative_to(_REPO).parts):
                continue
            achados.append(p)
    return achados


def _linhas_de_docstring(texto: str) -> set[int]:
    """Linhas ocupadas por docstring de módulo, classe ou função.

    Necessário, e não zelo: a docstring de `src/motor_expansao/perfil.py` CITA
    `if pais == "AR"` justamente para proibi-lo, e um `#`-stripper não a alcança — ela é
    uma string, não um comentário. Sem isto, a primeira coisa que este teste acusa é o
    arquivo que implementa a decisão que ele defende.
    """
    import ast  # noqa: PLC0415

    try:
        arvore = ast.parse(texto)
    except SyntaxError:
        return set()
    linhas: set[int] = set()
    for no in ast.walk(arvore):
        corpo = getattr(no, "body", None)
        if not isinstance(corpo, list) or not corpo:
            continue
        primeiro = corpo[0]
        if (
            isinstance(primeiro, ast.Expr)
            and isinstance(primeiro.value, ast.Constant)
            and isinstance(primeiro.value.value, str)
        ):
            fim = primeiro.end_lineno or primeiro.lineno
            linhas.update(range(primeiro.lineno, fim + 1))
    return linhas


def _codigo_ts(texto: str) -> list[tuple[int, str]]:
    """Linhas de TS/TSX fora de comentário — de linha (`//`) e de BLOCO (`/* ... */`).

    O bloco importa: `rodape-base.ts` explica num `/** ... */` por que trocou o ternário
    `pais === 'BR' ? ...` por uma tabela. Um stripper só de `//` acusaria a explicação.
    """
    fora: list[tuple[int, str]] = []
    em_bloco = False
    for n, bruta in enumerate(texto.splitlines(), 1):
        linha = bruta
        if em_bloco:
            fim = linha.find("*/")
            if fim < 0:
                continue
            linha, em_bloco = linha[fim + 2 :], False
        while "/*" in linha:
            ini = linha.find("/*")
            fim = linha.find("*/", ini + 2)
            if fim < 0:
                linha, em_bloco = linha[:ini], True
                break
            linha = linha[:ini] + linha[fim + 2 :]
        corte = linha.find("//")
        if corte >= 0:
            linha = linha[:corte]
        if linha.strip():
            fora.append((n, linha))
    return fora


def _codigo_py(texto: str) -> list[tuple[int, str]]:
    docs = _linhas_de_docstring(texto)
    fora: list[tuple[int, str]] = []
    for n, bruta in enumerate(texto.splitlines(), 1):
        if n in docs:
            continue
        corte = bruta.find("#")
        linha = bruta if corte < 0 else bruta[:corte]
        if linha.strip():
            fora.append((n, linha))
    return fora


def test_nao_ha_ramo_de_codigo_por_pais() -> None:
    ocorrencias: list[str] = []
    for arquivo in _fontes():
        rel = arquivo.relative_to(_REPO).as_posix()
        if rel in _ARQUIVOS_QUE_CITAM_O_PADRAO:
            continue
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        codigo = _codigo_py(texto) if arquivo.suffix == ".py" else _codigo_ts(texto)
        for n, linha in codigo:
            if _COMPARACAO.search(linha):
                ocorrencias.append(f"{rel}:{n}: {linha.strip()}")

    assert not ocorrencias, (
        "A DEC-047 proibe ramo de codigo por pais — o que varia entre paises sao os\n"
        "NUMEROS e os TEXTOS do perfil, nunca o caminho do codigo. Use uma TABELA\n"
        "indexada pelo pais (como `CENSO[pais]` em `rodape-base.ts`), que aceita o\n"
        "proximo pais com uma linha de dado.\n\nAchado em:\n  " + "\n  ".join(ocorrencias)
    )


def test_a_lista_de_excecoes_continua_sendo_so_este_arquivo() -> None:
    """A allowlist nasceu com um item — este arquivo, que cita o padrão para proibi-lo.

    Se ela crescer, o fio de alarme deixou de valer: mudar esta lista tem de ser uma
    decisão visível num PR, não um efeito colateral de fazer o teste passar.
    """
    assert _ARQUIVOS_QUE_CITAM_O_PADRAO == {"tests/contracts/test_fio_de_alarme_pais.py"}


@pytest.mark.parametrize(
    "trecho",
    [
        'if pais == "BR":',
        "if pais === 'AR' {",
        'return country != "CO"',
        "const x = pais === 'BR' ? 1 : 2",
        'if ("BR" == pais)',
    ],
)
def test_o_padrao_pega_o_que_deve_pegar(trecho: str) -> None:
    """Sem isto, um regex quebrado deixaria o teste verde para sempre — e um guarda
    que nunca acusa é indistinguível de um guarda que não existe."""
    assert _COMPARACAO.search(trecho), trecho


@pytest.mark.parametrize(
    "trecho",
    [
        "if pais === null:",
        "if pais is None:",
        "return CENSO[pais]",
        "const u = UNIDADE[pais]",
        "if (paisagem == 'BR')",
        'perfil.pais == perfil_esperado',
    ],
)
def test_o_padrao_nao_pega_o_que_e_legitimo(trecho: str) -> None:
    """Guarda de nulo e tabela indexada por país são a forma CERTA, e um teste que as
    reprovasse seria desligado na primeira semana."""
    assert not _COMPARACAO.search(trecho), trecho
