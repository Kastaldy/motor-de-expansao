#!/usr/bin/env python
"""Dado um arquivo gerado pelo piloto, diz de qual geração ele veio (D17).

    python scripts/rastrear_arquivo.py "C:/caminho/arquivo.xlsx"

Aceita os quatro artefatos: os três PDFs (Pontual, Municipal, Comparação) e o Simulador
XLSX. A leitura do arquivo usa SÓ a biblioteca padrão — de propósito: quem investiga um
vazamento não deveria precisar do ambiente do projeto para ler o identificador. A consulta
ao banco é o segundo passo, e só ela precisa de `MOTOR_DATABASE_URL`.

O QUE ESTE SCRIPT NÃO FAZ. Ele não prova quem vazou. Ele identifica a GERAÇÃO de onde a
cópia veio — quem pediu o arquivo pode tê-lo enviado a dez pessoas legitimamente. E o
silêncio é ambíguo: um arquivo sem identificador não distingue "alguém limpou os
metadados" de "foi gerado antes do carimbo existir".
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

_RE_UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}"
)


def _do_xlsx(caminho: Path) -> dict[str, str]:
    """`.xlsx` é um ZIP; as duas camadas ficam em `docProps/` e na aba `Afericao`."""
    achados: dict[str, str] = {}
    with zipfile.ZipFile(caminho) as z:
        nomes = set(z.namelist())
        if "docProps/custom.xml" in nomes:
            custom = z.read("docProps/custom.xml").decode("utf-8", "replace")
            for chave in ("report_id", "solicitante"):
                m = re.search(rf'name="{chave}".*?>([^<]+)<', custom)
                if m:
                    achados[chave] = m.group(1)
        if "docProps/core.xml" in nomes:
            core = z.read("docProps/core.xml").decode("utf-8", "replace")
            m = re.search(r"<dc:creator[^>]*>([^<]+)<", core)
            if m:
                achados.setdefault("creator", m.group(1))
            achados.setdefault("report_id", _primeiro_uuid(core))
        # A camada VISÍVEL, caso alguém tenha apagado as propriedades mas não o bloco.
        for parte in nomes:
            if parte.startswith("xl/") and parte.endswith(".xml"):
                achados.setdefault("report_id", _primeiro_uuid(
                    z.read(parte).decode("utf-8", "replace")))
    return {k: v for k, v in achados.items() if v}


def _do_pdf(caminho: Path) -> dict[str, str]:
    """Nos PDFs o id está no `/Info` (não comprimido) e na marca-d'água de cada página."""
    bruto = caminho.read_bytes()
    achados = {"report_id": _primeiro_uuid(bruto.decode("latin-1", "replace"))}
    m = re.search(rb"/Author\s*\(([^)]*)\)", bruto)
    if m:
        achados["creator"] = m.group(1).decode("latin-1", "replace")
    return {k: v for k, v in achados.items() if v}


def _primeiro_uuid(texto: str) -> str:
    m = _RE_UUID.search(texto)
    return m.group(0).lower() if m else ""


def _no_banco(report_id: str) -> None:
    try:
        from motor_expansao.db.postgres import conexao
    except ImportError as exc:
        print(f"\n  (banco não consultado: {exc})")
        return
    try:
        with conexao() as con:
            linha = con.execute(
                """
                SELECT u.login_usuario, u.nome_usuario, e.criado_em_evento, e.ip, e.metadados
                FROM eventos e LEFT JOIN usuarios u ON u.id_usuario = e.id_usuario
                WHERE e.tipo = 'relatorio.gerado' AND e.metadados->>'report_id' = %s
                """,
                (report_id,),
            ).fetchone()
    except Exception as exc:  # noqa: BLE001 — a leitura do arquivo já valeu por si
        print(f"\n  (banco indisponível: {type(exc).__name__}: {exc})")
        return

    print("\nO QUE O BANCO DIZ SOBRE ESSE IDENTIFICADOR")
    if linha is None:
        print("  NENHUM evento com esse id.")
        print("  Isso NÃO quer dizer que o arquivo é falso: pode ser de antes do carimbo,")
        print("  de outra instância, ou o evento pode ter saído por retenção.")
        return
    login, nome, quando, ip, meta = linha
    print(f"  Quem   : {login or '(autoria nula)'}" + (f" — {nome}" if nome else ""))
    print(f"  Quando : {quando}")
    print(f"  O quê  : {meta.get('relatorio')} ({meta.get('formato')}), via {meta.get('origem')}")
    if ip:
        print(f"  De onde: {ip}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    caminho = Path(argv[1])
    if not caminho.is_file():
        print(f"não encontrei o arquivo: {caminho}")
        return 2

    sufixo = caminho.suffix.lower()
    if sufixo == ".xlsx":
        achados = _do_xlsx(caminho)
    elif sufixo == ".pdf":
        achados = _do_pdf(caminho)
    else:
        print(f"não sei ler {sufixo!r} — este script lê .pdf e .xlsx")
        return 2

    print(f"O QUE ESTÁ NO ARQUIVO ({caminho.name})")
    if not achados.get("report_id"):
        print("  Nenhum identificador. O arquivo é anterior ao carimbo, veio de outra")
        print("  instância, ou os metadados foram removidos — não dá para distinguir.")
        return 1
    for rotulo, chave in (
        ("Identificador", "report_id"),
        ("Solicitante  ", "solicitante"),
        ("Autor        ", "creator"),
    ):
        if achados.get(chave):
            print(f"  {rotulo}: {achados[chave]}")

    _no_banco(achados["report_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
