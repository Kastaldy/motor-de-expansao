"""Nenhuma função cacheada do piloto pode guardar o perfil do país sem ser limpa no teste.

## O que este contrato guarda

A **DEC-047** decide que o país é propriedade do DEPLOY: um binário, N containers, **um
país por processo**. É essa premissa que torna corretos os 39 `@lru_cache` de
`web/server/app.py`, nenhum deles com país na chave — `_perfil_do_cliente()` pode cachear
para sempre porque, em produção, o perfil nunca muda dentro do processo.

Em teste a premissa é quebrada de propósito: cinco casos trocam `app.PERFIL` para o perfil
da Argentina. O `monkeypatch` devolve o atributo e **não tem como devolver um `lru_cache`**
— então o payload argentino sobrevive ao teste que o criou e contamina os seguintes. Foi o
que aconteceu com `test_perfil_front_espelha_o_python.py`, que passava sozinho e falhava
com `'Argentina' == 'Brasil'` depois de `test_piloto_web_acesso_banco.py`.

A fixture autouse `_limpar_cache_do_perfil_do_cliente` (em `tests/conftest.py`) limpa a
única função nessa situação hoje. Este teste existe para que a **segunda** não passe
despercebida: se alguém cachear outra função que alcance `PERFIL`, é aqui que fica
vermelho, com a instrução do que fazer.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_APP = _REPO / "web" / "server" / "app.py"

#: A lista é deliberadamente pequena. Ela não é "o que existe" — é o que a fixture de
#: `conftest.py` sabe limpar. Crescer esta lista sem crescer a fixture não conserta nada.
CACHES_LIMPOS_PELA_FIXTURE = {"_perfil_do_cliente"}


def _e_cacheada(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(
        "lru_cache" in ast.unparse(d) or "functools.cache" in ast.unparse(d)
        for d in fn.decorator_list
    )


def _alcanca_perfil(nome: str, defs: dict[str, ast.AST], vistos: set[str]) -> bool:
    """`PERFIL` lido direto, ou por uma chamada a outra função do mesmo módulo."""
    if nome in vistos or nome not in defs:
        return False
    vistos.add(nome)
    fn = defs[nome]
    corpo = ast.Module(body=fn.body, type_ignores=[])  # type: ignore[attr-defined]
    for no in ast.walk(corpo):
        if isinstance(no, ast.Name) and no.id == "PERFIL":
            return True
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name):
            if _alcanca_perfil(no.func.id, defs, vistos):
                return True
    return False


def _cacheadas_que_alcancam_perfil() -> set[str]:
    arvore = ast.parse(_APP.read_text(encoding="utf-8"))
    defs = {
        n.name: n
        for n in ast.walk(arvore)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    return {
        n.name
        for n in defs.values()
        if _e_cacheada(n) and _alcanca_perfil(n.name, defs, set())
    }


def test_toda_cache_que_le_o_PERFIL_e_limpa_entre_testes() -> None:
    achadas = _cacheadas_que_alcancam_perfil()
    escapando = achadas - CACHES_LIMPOS_PELA_FIXTURE
    assert not escapando, (
        f"função(ões) cacheada(s) que leem PERFIL e a fixture não limpa: {sorted(escapando)}.\n"
        "Em produção isso é correto (DEC-047: um país por processo). Em teste, um caso que "
        "troque `app.PERFIL` para a Argentina deixa o valor cacheado para o resto do "
        "processo e contamina todo teste seguinte, em SILÊNCIO.\n"
        "Conserto: acrescente a função a `_limpar_cache_do_perfil_do_cliente` em "
        "`tests/conftest.py` e a `CACHES_LIMPOS_PELA_FIXTURE` aqui."
    )


def test_a_fixture_nao_lista_funcao_que_deixou_de_existir() -> None:
    """A lista some junto com a função: uma entrada órfã daria falsa sensação de cobertura."""
    arvore = ast.parse(_APP.read_text(encoding="utf-8"))
    nomes = {
        n.name
        for n in ast.walk(arvore)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    orfas = CACHES_LIMPOS_PELA_FIXTURE - nomes
    assert not orfas, f"listadas aqui e inexistentes em app.py: {sorted(orfas)}"


def test_a_fixture_do_conftest_de_fato_menciona_cada_uma() -> None:
    """O elo fraco é a lista e a fixture divergirem — e as duas vivem em arquivos diferentes."""
    fonte = (_REPO / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert "_limpar_cache_do_perfil_do_cliente" in fonte, "a fixture sumiu do conftest"
    for nome in CACHES_LIMPOS_PELA_FIXTURE:
        assert nome in fonte, f"`{nome}` está na lista e a fixture do conftest não o limpa"
