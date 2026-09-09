"""Bloco A / commit A10 — o símbolo de moeda não volta para `web/src/lib/**`.

O A9 tirou o `R$` dos formatadores. Sem uma guarda, o próximo módulo de formatação o
reintroduz e nada acusa — e o defeito não aparece no Brasil, só numa instância que serve
outra moeda, meses depois, na tela de outra pessoa.

Três decisões deste arquivo, todas MEDIDAS
------------------------------------------
**1. É teste de contrato, não regra de ESLint.** Não há ESLint neste projeto: o
`web/package.json` não traz `eslint` em `devDependencies` e define `"lint": "tsc
--noEmit"`; não existe `eslint.config.*` nem `.eslintrc*` em lugar nenhum. Escrever a
guarda como regra de lint significaria introduzir ESLint + `typescript-eslint` + um passo
de CI — dependência e frente novas, num commit cujo papel é fechar uma porta.

**2. O escopo é `web/src/lib/**`, não `web/src/**`.** Medido: fora de `*.test.*` e fora
de comentário, `web/src` tem 63 ocorrências de `R$` em 15 arquivos. A maioria vive em
`ViabilityScreen.tsx` — os `prefixo="R$"` das caixas e os `title` que explicam a unidade
—, e convertê-los **contrariaria a decisão 0.6**: a viabilidade argentina sobe em REAIS,
com tributo brasileiro, como provisório declarado. Um símbolo parametrizado ali escreveria
"$" numa tela cujos números continuam sendo reais: pior que o provisório assumido, porque
some com o único sinal de que são reais. Saem com o BLK-INTL-11, não antes.

**3. Um seletor só de literal de string não serviria.** Das 11 ocorrências que havia em
`web/src/lib`, apenas 3 eram `Literal` de string; as seis de `brl`/`brlCurto` eram
TEMPLATE literal — exatamente os sítios que este bloco existe para mover. Por isso a
varredura é textual, sobre a linha sem comentário.

Spec: `docs/spec_bloco_a_perfil.md` §2.7 e §5.9 item 6.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_LIB = _REPO / "web" / "src" / "lib"

#: Vazia, e é essa a graça. O A9 moveu as 11 ocorrências que havia aqui — inclusive a de
#: `recomendacao.ts`, que a primeira passada do A9 deixou para trás e esta guarda pegou.
_ALLOWLIST: frozenset[str] = frozenset()

_MOEDA = re.compile(r"R\$")


def _linhas_de_codigo(texto: str) -> list[tuple[int, str]]:
    """Linhas fora de comentário — de linha (`//`) e de bloco (`/* ... */`).

    Separar código de comentário é trabalho de parser, não de `grep`: `web/src/lib` cita
    `R$` legitimamente em comentário de `imovel.ts`, `mascara.ts`, `sparkline.ts`,
    `types.ts`, `exec.ts` e `report.ts`. Um `grep` cru acusaria os seis.
    """
    fora: list[tuple[int, str]] = []
    em_bloco = False
    for n, bruta in enumerate(texto.splitlines(), 1):
        linha = bruta
        if em_bloco:
            fim = linha.find("*/")
            if fim < 0:
                continue
            linha = linha[fim + 2 :]
            em_bloco = False
        # blocos abertos e fechados na mesma linha
        while "/*" in linha:
            ini = linha.find("/*")
            fim = linha.find("*/", ini + 2)
            if fim < 0:
                linha = linha[:ini]
                em_bloco = True
                break
            linha = linha[:ini] + linha[fim + 2 :]
        corte = linha.find("//")
        if corte >= 0:
            linha = linha[:corte]
        if linha.strip():
            fora.append((n, linha))
    return fora


#: Fora do ESCOPO, e isto não é uma exceção tolerada — é uma categoria diferente.
#: `perfil-br.ts` é o perfil brasileiro COMPILADO: `"simbolo": "R$"` ali é o DADO, o
#: lugar onde o símbolo deve estar. O que esta guarda persegue é símbolo cravado em
#: código que FORMATA dinheiro. E o arquivo já tem guarda própria e mais forte:
#: `test_perfil_front_espelha_o_python.py` prova, campo a campo, que ele bate com o
#: `data/perfis/BR/perfil.json`.
_FORA_DO_ESCOPO = frozenset({"perfil-br.ts"})


def _fontes() -> list[Path]:
    return [
        p
        for p in sorted(_LIB.rglob("*.ts"))
        if p.is_file()
        and ".test." not in p.name
        and ".d." not in p.name
        and p.name not in _FORA_DO_ESCOPO
    ]


def test_o_escopo_nao_esta_vazio() -> None:
    """Se um refactor mover `lib/` de lugar, a varredura passaria a olhar para o nada e
    ficaria verde para sempre. Um guarda que não vê arquivo nenhum não é um guarda."""
    assert _LIB.is_dir(), f"{_LIB} nao existe"
    assert len(_fontes()) >= 20, "web/src/lib com menos arquivos que o esperado"


def test_sem_simbolo_de_moeda_cravado_em_web_src_lib() -> None:
    ocorrencias: list[str] = []
    for arquivo in _fontes():
        rel = arquivo.relative_to(_REPO).as_posix()
        if rel in _ALLOWLIST:
            continue
        for n, linha in _linhas_de_codigo(arquivo.read_text(encoding="utf-8")):
            if _MOEDA.search(linha):
                ocorrencias.append(f"{rel}:{n}: {linha.strip()}")

    assert not ocorrencias, (
        "Simbolo de moeda cravado em `web/src/lib`. Use `moeda()` de `lib/perfil.ts` —\n"
        "numa instancia que serve outra moeda, o literal escreve o simbolo errado e\n"
        "nenhum teste brasileiro percebe.\n\nAchado em:\n  " + "\n  ".join(ocorrencias)
    )


def test_a_allowlist_continua_vazia() -> None:
    """Nasceu vazia porque o A9 moveu tudo. Enchê-la tem de ser decisão visível num PR,
    e não o caminho mais curto para fazer o teste passar."""
    assert _ALLOWLIST == frozenset()


def test_o_unico_arquivo_fora_do_escopo_e_o_perfil_compilado() -> None:
    """`perfil-br.ts` é DADO, não código de formatação — e tem guarda própria e mais
    forte no `test_perfil_front_espelha_o_python.py`. Qualquer outro nome entrando aqui
    é uma violação disfarçada de escopo."""
    assert _FORA_DO_ESCOPO == frozenset({"perfil-br.ts"})
    assert (_LIB / "perfil-br.ts").is_file(), "o arquivo excluido tem de existir"


@pytest.mark.parametrize(
    ("fonte", "espera"),
    [
        ("const a = `R$ ${v}`", True),  # template literal — o sitio que mais importa
        ("const a = 'R$'", True),  # literal de string
        ("// custo em R$ por m2", False),  # comentario de linha
        ("/* R$ aqui */ const a = 1", False),  # bloco fechado na mesma linha
        ("const a = 1 /* R$ */", False),
    ],
)
def test_a_varredura_separa_codigo_de_comentario(fonte: str, espera: bool) -> None:
    """Sem estes casos, um bug no separador deixaria a guarda verde para sempre."""
    achou = any(_MOEDA.search(linha) for _, linha in _linhas_de_codigo(fonte))
    assert achou is espera, fonte


def test_bloco_de_varias_linhas_e_ignorado_ate_o_fim() -> None:
    fonte = "/*\n * R$ no meio de um bloco\n */\nconst a = 1\n"
    assert not any(_MOEDA.search(linha) for _, linha in _linhas_de_codigo(fonte))
