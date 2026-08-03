"""Contrato DOC <-> CODIGO: a prosa canonica nao pode contradizer o codigo.

Fecha o furo diagnosticado em `docs/refatoracao/review.md` (Fase 0, rank #2) e reaberto pelo
BLK-GRAPH-01: `tests/contracts/test_parametros_canonicos.py` se declara o contrato
"CLAUDE.md secao 3 <-> config", mas compara CODIGO com CODIGO (dict `CANONICAL` hardcoded).
Editar o `CLAUDE.md` nao quebrava nada -- e por isso 8 afirmacoes de doc envelheceram sem
ninguem notar (pesos do M1 invertidos, 4 tabs que eram 5, 8 paginas que eram 9, ...).

Assinatura mecanica do defeito que este arquivo trava: um fato vive duplicado em prosa e em
codigo; o lado do codigo fica pinado por teste; o lado da prosa fica pinado por NADA; um commit
muda o codigo e simplesmente nao inclui o `.md`. Aqui a prosa passa a ser lida e comparada.

PRINCIPIO DE PROJETO -- ancora ausente e FALHA, nunca skip. Um gate que se cala quando nao acha
a secao e pior que gate nenhum: da a sensacao de cobertura sem cobrir. Se um heading for
renomeado, este teste quebra e obriga a atualizar a ancora conscientemente.

NAO coberto aqui, com motivo:
  - contagem de linhas de parquet (ex.: 1.542.531 em `relatorio_pontual_censitario.md`): depende
    de artefato de dados que nao existe no CI;
  - identificador citado em doc que nao existe no codigo (ex.: o antigo `DIST_MIN_ULTRA_AINDA_KM`):
    uma varredura generica de `MAIUSCULAS` em prosa gera falso-positivo demais, e gate ruidoso
    acaba desligado.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from motor_expansao import config as config_mod
from motor_expansao.core import constants as core_constants
from motor_expansao.dashboard import relatorio_municipal as relmun_mod

RAIZ = Path(__file__).resolve().parents[2]
CLAUDE_MD = RAIZ / "CLAUDE.md"
FONTES_MD = RAIZ / "docs" / "fontes_dados_gratuitas.md"
RELMUN_MD = RAIZ / "docs" / "relatorio_municipal_template.md"

#: Como consertar quando este arquivo falha. Vai junto de toda mensagem de erro.
_COMO_CONSERTAR = (
    "O CODIGO e a fonte de verdade; corrija a PROSA para bater com ele "
    "(ou, se a mudanca de codigo foi intencional e aprovada, atualize os dois no MESMO PR)."
)


def _ler(caminho: Path) -> str:
    assert caminho.is_file(), f"doc canonico ausente: {caminho.relative_to(RAIZ)}"
    return caminho.read_text(encoding="utf-8")


def _bloco_python_apos(texto: str, heading: str, *, origem: str) -> str:
    """Devolve o 1o bloco ```python``` que aparece DEPOIS de `heading`.

    Falha explicitamente se o heading sumiu (rename de secao) ou se o bloco nao existe.
    """
    pos = texto.find(heading)
    assert pos != -1, (
        f"{origem}: heading {heading!r} nao encontrado. Se a secao foi renomeada, "
        f"atualize a ancora NESTE teste -- de proposito, para a mudanca ser consciente."
    )
    m = re.search(r"```python\n(.*?)```", texto[pos:], re.DOTALL)
    assert m is not None, f"{origem}: nenhum bloco ```python``` apos {heading!r}."
    return m.group(1)


def _atribuicoes(bloco: str) -> dict[str, object]:
    """`NOME = <literal>` -> dict. Ignora comentario, linha vazia e expressao nao-literal."""
    out: dict[str, object] = {}
    for linha in bloco.splitlines():
        linha = linha.split("#", 1)[0].strip()
        m = re.fullmatch(r"([A-Z][A-Z0-9_]*)\s*=\s*(.+)", linha)
        if not m:
            continue
        try:
            out[m.group(1)] = ast.literal_eval(m.group(2))
        except (ValueError, SyntaxError):
            continue  # expressao (ex.: chamada de funcao) -- fora do escopo deste contrato
    return out


def _pesos_da_formula(bloco: str, *, origem: str) -> tuple[float, float]:
    """Extrai (peso_renda, peso_pop) de `100 * (A * renda_pct_... + B * pop_pct_...)`."""
    renda = re.search(r"([0-9]*\.?[0-9]+)\s*\*\s*renda_pct_nacional", bloco)
    pop = re.search(r"([0-9]*\.?[0-9]+)\s*\*\s*pop_pct_nacional", bloco)
    assert renda and pop, (
        f"{origem}: nao consegui ler os pesos de `hex_score_estrutural`. O bloco precisa manter "
        f"a forma `A * renda_pct_nacional + B * pop_pct_nacional`."
    )
    return float(renda.group(1)), float(pop.group(1))


# ---------------------------------------------------------------------------
# 1. CLAUDE.md secao 3 -- bloco de parametros canonicos  <->  config.Settings
# ---------------------------------------------------------------------------


def test_parametros_da_secao_3_batem_com_o_config(monkeypatch):
    """Le o bloco ```python``` de "### Parametros canonicos" e compara com os DEFAULTS."""
    bloco = _bloco_python_apos(_ler(CLAUDE_MD), "### Parametros canonicos", origem="CLAUDE.md §3")
    doc = _atribuicoes(bloco)
    assert doc, "CLAUDE.md §3: bloco de parametros vazio ou ilegivel."

    for chave in doc:
        monkeypatch.delenv(chave, raising=False)
    s = config_mod.Settings()

    faltando = [k for k in doc if not hasattr(s, k)]
    assert not faltando, (
        f"CLAUDE.md §3 declara parametro(s) que NAO existem em config.Settings: {faltando}. "
        f"{_COMO_CONSERTAR}"
    )

    divergentes = {
        k: (v, getattr(s, k)) for k, v in doc.items() if getattr(s, k) != v
    }
    assert not divergentes, (
        "CLAUDE.md §3 diverge do config -- "
        + "; ".join(f"{k}: doc={d!r} codigo={c!r}" for k, (d, c) in divergentes.items())
        + f". {_COMO_CONSERTAR}"
    )


def test_secao_3_nao_omite_parametro_canonico_do_m1():
    """Omissao tambem e' drift: foi assim que `M1_HEX_LAND_FRACTION_MIN` ficou fora da prosa.

    Todo `M1_*` com default no `Settings` precisa aparecer no bloco da secao 3.
    """
    bloco = _bloco_python_apos(_ler(CLAUDE_MD), "### Parametros canonicos", origem="CLAUDE.md §3")
    doc = set(_atribuicoes(bloco))
    no_codigo = {
        k for k in vars(config_mod.Settings()) if k.startswith("M1_")
    } or {k for k in dir(config_mod.settings) if k.startswith("M1_")}
    ausentes = sorted(no_codigo - doc)
    assert not ausentes, (
        f"parametro(s) M1_* no codigo mas AUSENTES do bloco canonico do CLAUDE.md §3: {ausentes}. "
        f"A secao 3 e' a fonte curta canonica -- omitir um parametro que muda o comportamento do "
        f"M1 esconde o drift em vez de registra-lo."
    )


# ---------------------------------------------------------------------------
# 2. Formula do score oficial em PROSA (2 copias)  <->  PESOS_HEX_SCORE_ESTRUTURAL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("caminho", "heading", "origem"),
    [
        (CLAUDE_MD, "### Score oficial", "CLAUDE.md §3"),
        (FONTES_MD, "## 4. Score oficial", "docs/fontes_dados_gratuitas.md §4"),
    ],
)
def test_formula_do_score_em_prosa_bate_com_os_pesos(caminho, heading, origem):
    """A formula esta duplicada em 2 docs; foi UMA delas que ficou invertida por ~2 meses.

    Defeito real: os pesos foram invertidos no codigo em ef325d8 (2026-05-12) e so 2 das 3
    copias da formula foram atualizadas.
    """
    pesos = core_constants.PESOS_HEX_SCORE_ESTRUTURAL
    esperado = (pesos["renda_per_capita"], pesos["populacao_proxy"])
    obtido = _pesos_da_formula(_bloco_python_apos(_ler(caminho), heading, origem=origem), origem=origem)
    assert obtido == esperado, (
        f"{origem}: a formula do score diz renda={obtido[0]} / pop={obtido[1]}, mas "
        f"PESOS_HEX_SCORE_ESTRUTURAL diz renda={esperado[0]} / pop={esperado[1]}. "
        f"CUIDADO ao ler: 0.60/0.40 E' legitimo no `score_dominio_hibrido` e no "
        f"`score_setor_2022_calibrado` -- e essa coincidencia que fez o erro passar. "
        f"Pesos do M1 so mudam com DEC (DEC-001). {_COMO_CONSERTAR}"
    )


# ---------------------------------------------------------------------------
# 4. Paginas do Relatorio Municipal em prosa  <->  PDF_SECTION_HEADERS
# ---------------------------------------------------------------------------


def test_paginas_do_relatorio_municipal_batem_com_o_pdf():
    """Trava o titulo da secao E o numero de headings `### Pagina N`.

    Defeito real: o slide "Visao Geral do Municipio" entrou em 45a8f30 (BLK-RELMUN-01-FU1) e o
    template ficou em 8 paginas por ~1 mes, mesmo tendo sido editado depois.
    """
    reais = len(relmun_mod.PDF_SECTION_HEADERS)
    texto = _ler(RELMUN_MD)

    m = re.search(r"##\s*Estrutura\s*\((\d+)\s*p[áa]ginas?/slides?\)", texto)
    assert m is not None, (
        "relatorio_municipal_template.md: nao achei `## Estrutura (N páginas/slides)`. "
        "Se o heading mudou, atualize a ancora neste teste de proposito."
    )
    declarado = int(m.group(1))
    assert declarado == reais, (
        f"relatorio_municipal_template.md declara {declarado} paginas, mas PDF_SECTION_HEADERS "
        f"tem {reais}. {_COMO_CONSERTAR}"
    )

    headings = re.findall(r"(?m)^###\s*P[áa]gina\s+(\d+)\s*[—-]", texto)
    assert len(headings) == reais, (
        f"relatorio_municipal_template.md tem {len(headings)} headings `### Página N` "
        f"para {reais} paginas reais. {_COMO_CONSERTAR}"
    )
    assert [int(h) for h in headings] == list(range(1, reais + 1)), (
        f"headings de pagina fora de sequencia: {headings}. Ao inserir uma pagina, renumere as "
        f"seguintes (foi o que faltou no BLK-RELMUN-01-FU1)."
    )
