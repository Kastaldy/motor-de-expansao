"""Guarda do BLK-SAUDE-01: um 5xx do piloto nunca sai sem dizer POR QUÊ no log.

## O defeito que isto impede de voltar

`web/server/app.py` tinha, no gerador do Relatório Municipal, um
`except Exception as exc: raise HTTPException(500, f"...: {exc}")` que **não logava nada** —
`str(exc)` ia só no corpo da resposta HTTP, e ninguém guarda corpo de resposta. Medido em
2026-09-29 sobre a trilha da DEC-027: **33 × 500** nessa rota entre 31/08 e 22/09/2026, e
**nenhum** com causa recuperável. A investigação precisou reconstruir `uf`+`município` por
aritmética de Content-Length do log do Caddy (`bytes_read = 26 + bytes UTF-8 do nome do
município`), testar ~15 das 33 combinações contra produção — e todas voltaram 200. A causa
raiz daquele incidente está perdida para sempre.

Some-se a isso o driver de log `json-file` atrelado ao ciclo de vida do container
(BLK-SAUDE-07): todo deploy apaga o histórico. Um 5xx sem linha de log é, na prática, um
defeito que ninguém poderá diagnosticar nunca.

## O que esta guarda mede, e por que é AST e não texto

A regra é de ORDEM DE EXECUÇÃO: existe uma chamada de log **antes** do `raise`, **dentro do
mesmo handler**. Posição de texto não mede isso — foi a lição das duas versões erradas da
guarda de `entrar-bundle.test.ts` (uma mediu o docstring, a outra mediu declaração em vez de
chamada). Aqui se anda na árvore sintática: para cada `ast.ExceptHandler` que levanta
`HTTPException` com status 5xx literal, procura-se uma chamada `<algo com LOG>.<nível>(...)`
com `lineno` menor que a do `raise`.

**Nível de log é julgamento do autor, não da guarda:** exceção nomeada e esperada (banco
fora, volume sem permissão) merece `warning`/`error` com `exc_info=True`; genérica de causa
desconhecida merece `exception`. A guarda exige que ALGO seja dito, não como.

## Por que ela não passa vazia

Uma guarda que varre e não acha nada passaria feliz se o caminhamento quebrasse (renomear
`HTTPException`, mudar o import, trocar o literal por constante). Por isso há um teste que
ANCORA no caso conhecido: o handler do Relatório Municipal tem de ser ENCONTRADO e tem de
logar. Se ele desaparecer do radar, é a guarda que está cega, não o código que ficou limpo.

## O QUE ELA NÃO VÊ, declarado

Ela só reconhece `raise HTTPException(<literal 5xx>, ...)`. Um handler que faça
`raise _erro_de_usuarios(erro)` — o tradutor de exceções das rotas de administração, que
devolve 503 para `BancoNaoConfigurado` — produz um 5xx **invisível** a esta varredura, porque
o status nasce dentro do helper e seguir isso exigiria análise interprocedural. Hoje há um
caso assim (`_identidade_do_admin`, BLK-SAUDE-02) e ele loga por decisão do autor, não por
exigência da guarda. Não é um furo a tapar com um caso especial pelo nome do helper: isso
envelhece no primeiro renome. É um limite a saber ao ler um verde daqui.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

RAIZ_SERVIDOR = Path(__file__).resolve().parents[2] / "web" / "server"

#: Status que significam "o servidor falhou". 5xx e nada mais: 4xx é resposta ao pedido.
STATUS_5XX = frozenset({500, 501, 502, 503, 504, 505})

#: Métodos de logger. `log` entra porque `_LOG.log(nivel, ...)` é chamada válida.
NIVEIS = frozenset({"exception", "error", "warning", "critical", "info", "debug", "log"})


def _eh_chamada_de_log(no: ast.AST) -> bool:
    """`_LOG_FALHA.exception(...)`, `_LOG_D17.warning(...)`, `logger.error(...)`."""
    if not isinstance(no, ast.Call):
        return False
    func = no.func
    if not isinstance(func, ast.Attribute) or func.attr not in NIVEIS:
        return False
    alvo = func.value
    nome = alvo.id if isinstance(alvo, ast.Name) else str(getattr(alvo, "attr", ""))
    return "LOG" in nome.upper() or "log" in nome.lower()


def _status_do_raise(no: ast.Raise) -> int | None:
    """O status de `raise HTTPException(503, ...)` / `(status_code=503, ...)`, se literal."""
    exc = no.exc
    if not isinstance(exc, ast.Call):
        return None
    func = exc.func
    nome = func.id if isinstance(func, ast.Name) else str(getattr(func, "attr", ""))
    if nome != "HTTPException":
        return None
    if exc.args and isinstance(exc.args[0], ast.Constant) and isinstance(exc.args[0].value, int):
        return exc.args[0].value
    for kw in exc.keywords:
        if kw.arg == "status_code" and isinstance(kw.value, ast.Constant):
            valor = kw.value.value
            return valor if isinstance(valor, int) else None
    return None


def _handlers_com_5xx(caminho: Path) -> list[tuple[int, int, bool, str]]:
    """`(linha do except, status, loga_antes, tipo capturado)` por handler que levanta 5xx."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    achados: list[tuple[int, int, bool, str]] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.ExceptHandler):
            continue
        dentro = list(ast.walk(no))
        for filho in dentro:
            if not isinstance(filho, ast.Raise):
                continue
            status = _status_do_raise(filho)
            if status not in STATUS_5XX:
                continue
            loga_antes = any(
                _eh_chamada_de_log(c) and getattr(c, "lineno", 1 << 30) < filho.lineno
                for c in dentro
            )
            tipo = ast.unparse(no.type) if no.type else "(bare except)"
            achados.append((no.lineno, status, loga_antes, tipo))
    return achados


def _arquivos() -> list[Path]:
    return sorted(p for p in RAIZ_SERVIDOR.glob("*.py") if p.name != "__init__.py")


def test_todo_handler_que_levanta_5xx_loga_antes() -> None:
    """A guarda. Varre `web/server/` inteiro, não só `app.py`.

    O diretório e não o arquivo de propósito: em 2026-09-29 só `app.py` tinha o padrão (6
    handlers, 6 sem log), e um arquivo novo não pode reintroduzi-lo sem a suíte reclamar.
    """
    mudos: list[str] = []
    for arquivo in _arquivos():
        for linha, status, loga, tipo in _handlers_com_5xx(arquivo):
            if not loga:
                mudos.append(f"{arquivo.name}:{linha} — `except {tipo}` levanta {status} sem logar")
    assert not mudos, (
        "5xx sem log é defeito que ninguém poderá diagnosticar (o log do container morre "
        "no deploy, BLK-SAUDE-07). Acrescente `_LOG_FALHA.exception(...)` — ou "
        "`.warning(..., exc_info=True)` para condição esperada — ANTES do raise:\n  "
        + "\n  ".join(mudos)
    )


def test_a_guarda_encontra_o_caso_conhecido_e_nao_passa_vazia() -> None:
    """Âncora: o handler do Relatório Municipal existe e loga.

    Sem isto, a guarda acima passaria por VACUIDADE se o caminhamento quebrasse — renomear
    `HTTPException` no import, trocar o `500` literal por constante, ou mover a rota para
    outro módulo deixariam a varredura sem nenhum handler e a suíte verde.
    """
    app = RAIZ_SERVIDOR / "app.py"
    achados = _handlers_com_5xx(app)
    assert achados, "a varredura não achou NENHUM handler de 5xx em app.py — a guarda cegou"

    genericos_500 = [a for a in achados if a[1] == 500 and a[3] == "Exception"]
    assert genericos_500, (
        "o `except Exception` que devolve 500 no Relatório Municipal saiu do radar da "
        "guarda; se ele foi removido de verdade, atualize esta âncora — se não, a guarda "
        "parou de enxergar"
    )
    for linha, _status, loga, _tipo in genericos_500:
        assert loga, f"app.py:{linha} — o `except Exception` genérico voltou a engolir a causa"


def test_o_logger_de_falha_nao_carrega_identidade() -> None:
    """`piloto.falha` não pode virar um segundo cadastro de acesso sem governança.

    Quem fez o quê é a trilha da DEC-027, que tem retenção declarada de 90 dias e poda
    (`acesso_log.podar`). O log do container não tem retenção, não tem poda e não tem
    allowlist de leitura — colocar login de pessoa nele criaria um registro de acesso
    paralelo e permanente. Esta guarda é de FORMA: nenhuma chamada do `_LOG_FALHA` menciona
    `remote_user`, `usuario` ou `login` nos argumentos.
    """
    app = RAIZ_SERVIDOR / "app.py"
    arvore = ast.parse(app.read_text(encoding="utf-8"), filename=str(app))
    proibidos = {"remote_user", "usuario", "login", "email"}
    vazamentos: list[str] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call) or not _eh_chamada_de_log(no):
            continue
        alvo = no.func.value  # type: ignore[union-attr]
        if not (isinstance(alvo, ast.Name) and alvo.id == "_LOG_FALHA"):
            continue
        for arg in [*no.args, *(kw.value for kw in no.keywords)]:
            for dentro in ast.walk(arg):
                if isinstance(dentro, ast.Name) and dentro.id in proibidos:
                    vazamentos.append(f"app.py:{no.lineno} passa `{dentro.id}` ao _LOG_FALHA")
    assert not vazamentos, (
        "identidade de pessoa vai para a trilha da DEC-027, não para o log do container:\n  "
        + "\n  ".join(vazamentos)
    )


@pytest.mark.parametrize(
    ("fonte", "espera_loga"),
    [
        # Loga antes: o caso certo.
        (
            """
try:
    f()
except ValueError as e:
    _LOG.exception("falhou")
    raise HTTPException(500, "x") from e
""",
            True,
        ),
        # Loga DEPOIS do raise: inalcançável, não conta.
        (
            """
try:
    f()
except ValueError as e:
    raise HTTPException(500, "x") from e
    _LOG.exception("falhou")
""",
            False,
        ),
        # Log em OUTRO handler não cobre este.
        (
            """
try:
    f()
except KeyError:
    _LOG.exception("outro")
except ValueError as e:
    raise HTTPException(503, "x") from e
""",
            False,
        ),
        # 4xx não é 5xx: fora do escopo da guarda.
        (
            """
try:
    f()
except ValueError as e:
    raise HTTPException(404, "x") from e
""",
            None,
        ),
    ],
)
def test_a_regra_de_ordem_e_de_escopo_esta_certa(
    fonte: str, espera_loga: bool | None, tmp_path: Path
) -> None:
    """Contrato do detector, em fonte sintético.

    `espera_loga=None` quer dizer "este handler não deve nem aparecer na varredura". Os dois
    casos do meio são os que uma guarda de TEXTO daria como aprovados — log depois do
    `raise` e log em handler vizinho —, e são exatamente as duas maneiras de a guarda
    mentir.
    """
    arquivo = tmp_path / "amostra.py"
    arquivo.write_text(fonte, encoding="utf-8")
    achados = _handlers_com_5xx(arquivo)
    if espera_loga is None:
        assert not achados, "um 4xx entrou na varredura de 5xx"
        return
    assert len(achados) == 1, f"esperava 1 handler de 5xx, vi {len(achados)}"
    assert achados[0][2] is espera_loga
