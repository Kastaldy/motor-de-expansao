"""O banco tem UMA porta, e a exceção tem nome.

`db/postgres.py` e' a unica porta do motor para o banco (ver o docstring de `db/__init__.py`).
Quem escreve passa por `transacao(id_usuario=...)`, que carimba `app.id_usuario` como PRIMEIRO
comando da transacao -- e e' esse carimbo que as triggers da 009/011 leem para saber quem agiu.

POR QUE ISTO E' TESTE
---------------------
O contrato do carimbo nao e' de uma funcao, e' de TODO caminho de escrita. Uma conexao aberta
fora daqui escreve sem carimbo, e o defeito e' SILENCIOSO nos dois sentidos: nada falha, e a
auditoria passa a registrar `registrado_por = NULL` -- indistinguivel de um `UPDATE` feito a mao.
Quem abrir a segunda conexao provavelmente nao tera' lido o esquema; este teste le por ele.

A EXCECAO TEM NOME, e por isso esta' na allowlist: `db/cli.py` abre conexao propria de proposito
(runner de migration e verificador de privilegio). Ele roda como DONO, nao como `app`, e migration
nao e' ato de RBAC de um usuario -- nao ha' autor a carimbar. Nomear a excecao e' o que separa
"regra com uma porta de servico conhecida" de "regra que ja' nasceu falsa".

QUANDO ESTE TESTE FICAR VERMELHO, a pergunta certa nao e' "como faco passar?", e sim: este novo
caminho escreve? Se escreve, ele tem de usar `transacao()`. Se so' le, `conexao()` ja' resolve, e
ela abre `SET TRANSACTION READ ONLY` -- o servidor recusa a escrita, nao a boa vontade.
"""

from __future__ import annotations

import re
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]

_FONTES = ("src/motor_expansao", "web/server", "scripts")

#: A porta, e a excecao nomeada. Caminhos relativos a `_RAIZ`, com barra normalizada.
_PERMITIDOS = frozenset(
    {
        "src/motor_expansao/db/postgres.py",  # a porta
        "src/motor_expansao/db/cli.py",  # runner de migration: roda como DONO, sem autor
    }
)

#: As formas que de fato ADQUIREM conexao, MEDIDAS no codigo (16/09/2026), nao supostas:
#:   * `psycopg.connect(` -- o caminho do `cli.py`;
#:   * `psycopg_pool`     -- o import do pool, que so' o `postgres.py` faz;
#:   * `.connection()`    -- a retirada do pool, tambem so' no `postgres.py`.
#:
#: NAO basta procurar `ConnectionPool(`: o pool e' instanciado por VARIAVEL (`classe = _driver()`
#: e depois `classe(...)`), entao o nome da classe nunca aparece como chamada. A primeira versao
#: deste teste procurava exatamente isso -- e a metade de baixo a denunciou na PRIMEIRA execucao,
#: que e' precisamente o servico que ela existe para prestar.
#:
#: E NAO alargar para `psycopg` puro: o `db/eventos.py` faz `from psycopg.types.json import Jsonb`,
#: ajudante de TIPO que nao abre conexao nenhuma. Um padrao que o acusasse tornaria este teste um
#: delator de inocente -- e teste assim e' desligado tao rapido quanto teste que nao acusa ninguem.
_ABRE_CONEXAO = re.compile(r"psycopg\.connect\s*\(|psycopg_pool|\.connection\s*\(")


def _arquivos_python() -> list[Path]:
    achados: list[Path] = []
    for fonte in _FONTES:
        caminho = _RAIZ / fonte
        if caminho.exists():
            achados.extend(sorted(caminho.rglob("*.py")))
    return achados


def _quem_abre_conexao() -> set[str]:
    vistos: set[str] = set()
    for arquivo in _arquivos_python():
        if _ABRE_CONEXAO.search(arquivo.read_text(encoding="utf-8")):
            vistos.add(arquivo.relative_to(_RAIZ).as_posix())
    return vistos


def test_ninguem_abre_conexao_fora_da_porta() -> None:
    intrusos = sorted(_quem_abre_conexao() - _PERMITIDOS)
    assert not intrusos, (
        "conexao com o banco aberta fora de `db/postgres.py`, em: "
        + ", ".join(intrusos)
        + ". Se este caminho ESCREVE, ele precisa de `transacao(id_usuario=...)`, que carimba "
        "`app.id_usuario` -- sem isso a auditoria da 009/011 grava `registrado_por` NULO, e o "
        "defeito e' mudo. Se so' le, use `conexao()`, que abre READ ONLY. Excecao de verdade "
        "entra em `_PERMITIDOS` COM o motivo escrito, como o `cli.py`."
    )


def test_a_varredura_ainda_enxerga_as_conexoes_conhecidas() -> None:
    """Sem esta metade, o teste acima e' garantia FALSA.

    Se o padrao parar de casar -- a biblioteca troca de nome, o pool muda de classe, os arquivos
    saem de `_FONTES` --, o primeiro teste fica VERDE para sempre vigiando o vazio. Ele so' tem
    valor enquanto a varredura comprovadamente acha o que JA' existe.
    """
    vistos = _quem_abre_conexao()
    faltando = sorted(_PERMITIDOS - vistos)
    assert not faltando, (
        "a varredura deixou de enxergar conexao em: "
        + ", ".join(faltando)
        + " -- o padrao ou as `_FONTES` pararam de casar com o codigo, e a trava virou decorativa. "
        "Se o arquivo deixou de abrir conexao de verdade, tire-o de `_PERMITIDOS`."
    )
