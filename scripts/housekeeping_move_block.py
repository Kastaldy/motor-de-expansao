"""Helper de housekeeping do /run-cycle (BLK-OPS-10).

Move um bloco concluído de ``tasks/backlog.md`` para ``tasks/completed.md`` de forma
**byte-idêntica** e deixa um stub de 1 linha no backlog.

Garantias de design:
- ``moved = backlog[start:end]`` é uma **fatia literal** (offsets de caractere) do texto
  original do backlog — nada de round-trip via ``split('\\n')``/``join``.
- O CLI abre os arquivos com ``newline=""`` (sem tradução de quebras) e ``encoding="utf-8"``,
  preservando CRLF no Windows e garantindo byte-identity disco<->memória.
- Re-entrância: mover o mesmo bloco duas vezes levanta ``BlockNotFound`` na 2a chamada (após o
  1o move o heading ``### BLK-XXX`` já virou stub).

Funções puras (``move_block`` / ``verify_moved``) + CLI fino. Sem dependências externas.
"""

from __future__ import annotations

import argparse
import re
import sys

#: Código de saída do CLI quando o bloco não está no backlog (ciclo ad-hoc → no-op).
EXIT_AD_HOC = 3


class BlockNotFound(Exception):
    """O bloco ``### {block_id}`` não existe no texto do backlog."""


def _heading_pattern(block_id: str) -> re.Pattern[str]:
    # Casa "### BLK-XXX" no início da linha; ``(?=\s|$)`` evita que "BLK-OPS-02"
    # case dentro de "BLK-OPS-02b".
    return re.compile(r"(?m)^### +" + re.escape(block_id) + r"(?=\s|$)")


def _content_span(backlog: str, block_id: str) -> tuple[int, int]:
    """Offsets (start, content_end) do bloco no texto original.

    ``start`` = início do heading ``### {block_id}``.
    ``content_end`` = fim do conteúdo do bloco, EXCLUINDO o separador ``---`` e linhas em
    branco finais que antecedem o próximo heading (``### `` / ``## ``) ou o EOF.
    """
    m = _heading_pattern(block_id).search(backlog)
    if m is None:
        raise BlockNotFound(block_id)
    start = m.start()
    nxt = re.compile(r"(?m)^#{2,3} ").search(backlog, m.end())
    raw_end = nxt.start() if nxt else len(backlog)
    raw_block = backlog[start:raw_end]
    # Run final de linhas em branco e/ou linhas "---" (LF ou CRLF).
    sep = re.search(r"(?:[ \t]*---[ \t\r]*\n|[ \t\r]*\n)+\Z", raw_block)
    content_end = raw_end - (len(sep.group(0)) if sep else 0)
    return start, content_end


def move_block(
    backlog: str, completed: str, block_id: str, date: str
) -> tuple[str, str, str]:
    """Move ``block_id`` do backlog para completed.

    Retorna ``(novo_backlog, novo_completed, moved)`` onde ``moved`` é a fatia literal
    byte-idêntica do bloco. Levanta ``BlockNotFound`` se o bloco não existir.
    """
    start, content_end = _content_span(backlog, block_id)
    moved = backlog[start:content_end]
    nl = "\r\n" if "\r\n" in backlog else "\n"
    stub = f"- {block_id} (concluído {date}) — ver tasks/completed.md"
    new_backlog = backlog[:start] + stub + nl + backlog[content_end:]
    new_completed = completed.rstrip("\r\n") + nl + nl + "---" + nl + nl + moved
    if not new_completed.endswith("\n"):
        new_completed += nl
    return new_backlog, new_completed, moved


#: Token de ID de bloco. ``findall`` devolve o token INTEIRO, então comparação por igualdade
#: distingue ``BLK-FIX-06`` de ``BLK-FIX-06-C`` (o furo de colisão de prefixo de um ``grep``).
_BLK_TOKEN = re.compile(r"BLK-[A-Za-z0-9-]+")


def is_done(completed: str, block_id: str) -> bool:
    """True se ``completed.md`` marca ``block_id`` como concluído — por HEADING, não por prosa.

    BLK-ORQ-24: a conclusão é medida SÓ em linhas de heading (``## `` ou ``### ``) que contenham o
    ID como **token exato**. Cobre os dois marcadores reais de fechamento:

    * ``### BLK-X — título`` (bloco íntegro movido pelo helper, modo merge-humano); e
    * ``## Fechamento de ciclo — BLK-X (data)`` (resumo do ciclo, modo auto-merge, em que o move é
      diferido e este é o ÚNICO marcador).

    NÃO conta menção em PROSA: ``completed.md`` está cheio de forward-references a blocos que
    estavam ABERTOS quando o resumo foi escrito ("Sucessor: BLK-X", "Próximo recomendado: BLK-Y",
    "depende de BLK-Z") — um teste de substring faria a seleção do loop PULAR para sempre um bloco
    loop-safe ainda aberto. A igualdade de token (não substring) evita a colisão de prefixo.
    """
    for line in completed.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("## ", "### ")) and block_id in _BLK_TOKEN.findall(stripped):
            return True
    return False


def emit_delta(backlog: str, completed: str) -> list[str]:
    """IDs a stubar no PR de housekeeping em lote (BLK-ORQ-24 / modo auto-merge).

    O delta é DETERMINÍSTICO: cada bloco que (i) ainda tem heading ``### BLK-X`` ABERTO no
    ``backlog.md`` E (ii) já tem heading de conclusão em ``completed.md``. Ambos os lados usam
    ``_heading_pattern`` (fronteira de palavra), então ``BLK-FIX-06`` aberto no backlog não é
    arrastado por ``BLK-FIX-06-C`` concluído em completed — o furo de colisão de prefixo que um
    ``grep`` de substring teria. Retorna a lista na ordem em que os headings aparecem no backlog.
    """
    ids: list[str] = []
    for m in re.finditer(r"(?m)^### +(BLK-[A-Za-z0-9-]+?)(?=\s|$)", backlog):
        block_id = m.group(1)
        if is_done(completed, block_id) and block_id not in ids:
            ids.append(block_id)
    return ids


def verify_moved(backlog: str, completed: str, block_id: str) -> None:
    """Confirma o estado pós-move. Levanta ``AssertionError`` se algo falhar."""
    stub_re = re.compile(
        r"(?m)^- "
        + re.escape(block_id)
        + r" \(concluído \d{4}-\d{2}-\d{2}\) — ver tasks/completed\.md[ \t\r]*$"
    )
    if not stub_re.search(backlog):
        raise AssertionError(f"stub ausente no backlog para {block_id}")
    if _heading_pattern(block_id).search(backlog):
        raise AssertionError(f"bloco {block_id} ainda tem heading no backlog")
    if not _heading_pattern(block_id).search(completed):
        raise AssertionError(f"bloco {block_id} ausente em completed.md")


def _read(path: str) -> str:
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def _write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Housekeeping: move bloco concluído do backlog para completed (byte-idêntico)."
    )
    ap.add_argument(
        "block_id",
        nargs="?",
        help="ID do bloco, ex.: BLK-OPS-09 (dispensável só no modo --emit-delta)",
    )
    ap.add_argument("--date", help="data de conclusão AAAA-MM-DD (obrigatória no modo move)")
    ap.add_argument("--backlog", default="tasks/backlog.md")
    ap.add_argument("--completed", default="tasks/completed.md")
    ap.add_argument(
        "--check",
        action="store_true",
        help="apenas verifica (verify_moved); não escreve nada",
    )
    ap.add_argument(
        "--is-done",
        action="store_true",
        help="sai 0 se o bloco tem heading de conclusão em completed.md (fronteira de palavra), "
        "1 caso contrário; não escreve nada. Consumido pela seleção do loop (BLK-ORQ-24).",
    )
    ap.add_argument(
        "--emit-delta",
        action="store_true",
        help="lista (um ID por linha) os blocos ainda com heading no backlog E já concluídos em "
        "completed.md — a lista a stubar no PR de housekeeping em lote (BLK-ORQ-24). block_id é ignorado.",
    )
    args = ap.parse_args(argv)

    backlog = _read(args.backlog)
    completed = _read(args.completed)

    if args.emit_delta:
        for bid in emit_delta(backlog, completed):
            print(bid)
        return 0

    if not args.block_id:
        ap.error("block_id é obrigatório (exceto no modo --emit-delta)")

    if args.is_done:
        done = is_done(completed, args.block_id)
        print(f"{args.block_id}: {'DONE' if done else 'ABERTO'} em {args.completed}")
        return 0 if done else 1

    if args.check:
        try:
            verify_moved(backlog, completed, args.block_id)
        except AssertionError as exc:
            print(f"FALHA --check: {exc}", file=sys.stderr)
            return 1
        print(f"OK: {args.block_id} movido (stub no backlog + bloco em completed.md).")
        return 0

    if not args.date:
        ap.error("--date é obrigatória no modo move")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        ap.error("--date deve estar no formato AAAA-MM-DD")

    try:
        new_backlog, new_completed, moved = move_block(
            backlog, completed, args.block_id, args.date
        )
    except BlockNotFound:
        # Ciclo ad-hoc (tarefa fora do backlog): nada a mover. Sinaliza no-op limpo.
        print(
            f"SKIP: {args.block_id} não está em {args.backlog} "
            f"(ciclo ad-hoc, fora do backlog) — nada a mover.",
            file=sys.stderr,
        )
        return EXIT_AD_HOC
    _write(args.backlog, new_backlog)
    _write(args.completed, new_completed)
    print(
        f"OK: movido {args.block_id} ({len(moved)} bytes) -> {args.completed}; "
        f"stub em {args.backlog}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
