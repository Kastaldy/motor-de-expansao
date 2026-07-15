#!/usr/bin/env python3
"""Auto-criticidade — aplica a label `criticidade:<nivel>` do bloco quando o PR ainda nao tem
nenhuma.

Contexto (DEC-016 / BLK-ORQ-20): o `review-gate` EXIGE exatamente uma label `criticidade:*`,
conferida contra o campo Criticidade do bloco em `tasks/backlog.md` da BASE. Ele apenas VALIDA a
label; nada a APLICAVA. Este script fecha esse buraco: le o bloco do PR (por titulo/branch) no
backlog da BASE e aplica a label correspondente, **espelhando exatamente o mapa do review-gate**
(guard.yml) para nunca divergir.

Seguranca:
- roda no workflow `auto-criticidade.yml` em `pull_request_target` (a partir da BASE, sem checkout
  nem execucao de codigo do PR);
- so aplica UMA label de METADADO (`criticidade:*`); NUNCA aplica `aprovado-humano`/`critica-aprovada`
  (as labels de aprovacao HUMANA continuam 100% manuais);
- **no-op** se o PR ja tem uma label de criticidade (nao briga com o humano) OU se o bloco nao for
  unicamente identificavel no backlog da base (PR de housekeeping/ad-hoc, ou bloco novo ainda fora
  da base) -> nesse caso o passo manual/`review-gate` decide, como hoje.

Isto NAO decide merge nem afrouxa nenhum portao: Alta/Critica seguem exigindo `aprovado-humano`/
`critica-aprovada`; o `guard` de paths (M1/CI/deploy/...) segue independente. Apenas remove o passo
manual de declarar a criticidade que ja e deterministica a partir do backlog.
"""
from __future__ import annotations

import os
import re
import subprocess
import unicodedata

PREFIXO = "criticidade:"
# Espelho EXATO de guard.yml (review-gate). Manter em sincronia (test garante o mapa).
NIVEIS = {"baixa", "media", "alta", "critica"}
ORDEM_CRITICIDADE = {"baixa": 0, "media": 1, "alta": 2, "critica": 3}
MAPA_BACKLOG = {
    "baixa": "baixa",
    "media": "media",
    "alta": "alta",
    "critica": "critica",
    "estrategica": "critica",
}


def sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )


def criticidade_do_bloco(backlog: str, branch: str, titulo: str) -> str | None:
    """Nivel de criticidade (`baixa|media|alta|critica`) do bloco casado por branch+titulo contra o
    backlog da base, ou None se nao houver bloco UNICO identificavel / sem campo Criticidade util.

    Espelha o cross-check do review-gate: candidatos = IDs `BLK-*` do backlog contidos em
    branch+titulo; desempata pelo mais ESPECIFICO; ambiguidade (>1) ou nenhum -> None; a criticidade
    de uma FAIXA ("Alta/Critica") e o MAXIMO.
    """
    linhas = backlog.splitlines()
    ids_backlog = [
        m.group(1)
        for linha in linhas
        if (m := re.match(r"^#{2,4}\s*(BLK-[A-Z0-9]+(?:-[0-9A-Za-z]+)+)", linha))
    ]
    alvo = f"{branch} {titulo}".lower()
    candidatos = sorted({bid for bid in ids_backlog if bid.lower() in alvo})
    maximais = [
        c
        for c in candidatos
        if not any(c != outro and c.lower() in outro.lower() for outro in candidatos)
    ]
    if len(maximais) != 1:
        return None
    bloco = maximais[0]
    inicio = next(
        (
            i
            for i, linha in enumerate(linhas)
            if re.match(rf"^#{{2,4}}\s*{re.escape(bloco)}\b", linha)
        ),
        None,
    )
    if inicio is None:
        return None

    campo = ""
    for linha in linhas[inicio + 1 : inicio + 80]:
        if re.match(r"^#{2,4}\s", linha):
            break
        alinhado = linha.strip()
        tabela = re.match(r"^\|\s*\*{0,2}Criticidade\*{0,2}\s*\|(.+)$", alinhado)
        simples = re.match(r"^\*{0,2}Criticidade\*{0,2}\s*:\s*(.+)$", alinhado)
        if tabela:
            campo = tabela.group(1).rsplit("|", 1)[0]
            break
        if simples:
            campo = simples.group(1)
            break
    if not campo:
        return None

    # So o "cabecalho" do campo conta (antes do parentese explicativo).
    cabecalho = sem_acento(campo.split("(")[0]).lower()
    niveis = {
        MAPA_BACKLOG[p] for p in re.findall(r"[a-z]+", cabecalho) if p in MAPA_BACKLOG
    }
    if not niveis:
        return None
    return max(niveis, key=lambda n: ORDEM_CRITICIDADE[n])


def _gh(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=False)


def main() -> int:
    repo = os.environ["REPO"]
    pr = os.environ["PR_NUMBER"]
    branch = os.environ.get("PR_BRANCH", "")
    titulo = os.environ.get("PR_TITULO", "")

    labels_proc = _gh("api", f"repos/{repo}/issues/{pr}/labels", "--jq", ".[].name")
    if labels_proc.returncode != 0:
        # fail-safe: nao conseguiu ler labels -> nao mexe (o review-gate ainda protege).
        print(f"::warning::nao consegui ler labels do PR #{pr}; no-op.")
        return 0
    labels = {ln.strip() for ln in labels_proc.stdout.splitlines() if ln.strip()}
    ja = sorted(ln for ln in labels if ln.startswith(PREFIXO))
    if ja:
        print(f"criticidade ja definida ({', '.join(ja)}) -> no-op (nao brigo com o humano).")
        return 0

    with open("tasks/backlog.md", encoding="utf-8") as fh:
        backlog = fh.read()
    nivel = criticidade_do_bloco(backlog, branch, titulo)
    if not nivel:
        print(
            "bloco nao unicamente identificavel no backlog da base (housekeeping/ad-hoc ou bloco "
            "novo) -> no-op; a label fica para o passo manual/review-gate."
        )
        return 0

    label = f"{PREFIXO}{nivel}"
    print(f"aplicando `{label}` (bloco identificado no backlog da base).")
    add = _gh("pr", "edit", pr, "--repo", repo, "--add-label", label)
    if add.returncode != 0:
        print(f"::warning::falha ao aplicar `{label}`: {add.stderr.strip()}")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
