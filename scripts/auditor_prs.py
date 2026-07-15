#!/usr/bin/env python3
"""Auditor de PRs (BLK-ORQ-23) — routine diaria READ-ONLY que da visao do que esta aberto/mergeando
e mede o gatilho de suspensao da DEC-016, sem virar gargalo.

O que faz (1x/dia, via .github/workflows/auditor-prs.yml):
  1. le os PRs ABERTOS + status de CI + labels + mergeabilidade (READ-ONLY);
  2. classifica cada PR em `auto-merge` / `revisar` / `bloqueio`;
  3. conta os INCIDENTES da DEC-016 nos ultimos 90 dias (revert na main, CI da main quebrado,
     e merge de PR critico/governanca SEM a label humana = bypass do guard); 2+ -> alerta de SUSPENSAO;
  4. manda UM aviso ao grupo Telegram de ops (mesmo bot do Motor) + comenta numa issue fixa.

READ-ONLY (criterios de aceite): NAO aplica label, NAO mergeia, NAO faz push, NAO altera o M1.
A unica escrita e o resumo (Telegram + comentario na issue de historico). O gate e deterministico
(checks + labels) — o Auditor INFORMA, nao decide. Anti-PII: o aviso lista numero/titulo/link do PR,
NUNCA conteudo de diff.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import urllib.parse
import urllib.request

REQUIRED_CHECKS = {"test", "guard", "review-gate", "claude-review"}
# Checks "tecnicos": vermelho = problema de codigo/qualidade (bloqueio), nao espera de humano.
CHECKS_TECNICOS = {"test", "claude-review"}
# Checks de "portao": vermelho normalmente = falta label humana (revisar), nao defeito.
CHECKS_PORTAO = {"guard", "review-gate"}
PREFIXO_CRIT = "criticidade:"
JANELA_DIAS = 90
LIMIAR_SUSPENSAO = 2


# --------------------------------------------------------------------------- funcoes PURAS (testadas)
def nivel_criticidade(labels: set[str]) -> str | None:
    """Extrai `baixa|media|alta|critica` da label `criticidade:*`, ou None se ausente."""
    for lb in labels:
        if lb.startswith(PREFIXO_CRIT):
            nivel = lb[len(PREFIXO_CRIT) :]
            if nivel in {"baixa", "media", "alta", "critica"}:
                return nivel
    return None


def classificar_pr(pr: dict) -> tuple[str, str]:
    """Classifica UM PR em (`auto-merge`|`revisar`|`bloqueio`, motivo).

    `pr` = {draft:bool, mergeable:str, labels:set[str], checks:{nome:estado}} onde estado in
    {"pass","fail","pending"}. Distingue defeito tecnico (bloqueio) de espera por humano (revisar).
    """
    if pr.get("draft"):
        return ("revisar", "rascunho (draft) — nao mergeia ate sair de draft")

    checks = pr.get("checks", {})
    labels = pr.get("labels", set())
    crit = nivel_criticidade(labels)
    falhando = {n for n, s in checks.items() if s == "fail" and n in REQUIRED_CHECKS}

    # 1) defeito tecnico -> bloqueio
    tecnicos = falhando & CHECKS_TECNICOS
    if tecnicos:
        return ("bloqueio", "check(s) vermelho(s): " + ", ".join(sorted(tecnicos)))
    if pr.get("mergeable") == "CONFLICTING":
        return ("bloqueio", "conflito com a main (precisa rebase/merge)")

    precisa_humano = (
        crit is None
        or (crit == "critica" and "critica-aprovada" not in labels)
        or (crit in {"alta", "critica"} and "aprovado-humano" not in labels)
    )

    # 2) portao vermelho -> normalmente espera de humano; com label presente, e defeito a investigar
    portao = falhando & CHECKS_PORTAO
    if portao:
        if precisa_humano:
            return ("revisar", "aguarda aprovacao humana (gate: " + ", ".join(sorted(portao)) + ")")
        return ("bloqueio", "gate vermelho COM label presente — investigar: " + ", ".join(sorted(portao)))

    # 3) nada vermelho: falta label humana? -> revisar
    if crit == "critica" and "critica-aprovada" not in labels:
        return ("revisar", "Critica: aguarda `critica-aprovada` do dono")
    if crit == "alta" and "aprovado-humano" not in labels:
        return ("revisar", "Alta: aguarda `aprovado-humano`")
    if crit is None:
        return ("revisar", "sem label de criticidade (aguarda auto-criticidade/humano)")

    # 4) Baixa/Media (ou Alta/Critica ja aprovada) sem vermelho -> candidato a auto-merge
    pendentes = {n for n, s in checks.items() if s == "pending" and n in REQUIRED_CHECKS}
    if pendentes:
        return ("auto-merge", "aguardando CI (" + ", ".join(sorted(pendentes)) + ")")
    return ("auto-merge", "4 checks verdes — fecha sozinho")


def avaliar_incidentes(reverts: int, ci_falhas: int, bypass_guard: int) -> dict:
    """Agrega os sinais de incidente da DEC-016 (janela de 90d). `suspender` quando >= 2."""
    total = reverts + ci_falhas + bypass_guard
    return {
        "reverts": reverts,
        "ci_falhas": ci_falhas,
        "bypass_guard": bypass_guard,
        "total": total,
        "suspender": total >= LIMIAR_SUSPENSAO,
    }


_EMOJI = {"auto-merge": "🟢", "revisar": "🟡", "bloqueio": "🔴"}


def compor_relatorio(prs: list[dict], incid: dict, data_str: str, *, capado: bool = False) -> str:
    """Monta o texto do aviso (Telegram/issue). `prs` = [{number,title,url,estado,motivo}].
    Anti-PII: usa numero/titulo/link, NUNCA diff.
    """
    por_estado = {"auto-merge": 0, "revisar": 0, "bloqueio": 0}
    for p in prs:
        por_estado[p["estado"]] = por_estado.get(p["estado"], 0) + 1

    linhas = [f"🔎 Auditor de PRs — {data_str}", ""]
    linhas.append(
        f"{len(prs)} PR(s) aberto(s): "
        f"🟢 {por_estado['auto-merge']} auto-merge · "
        f"🟡 {por_estado['revisar']} revisar · "
        f"🔴 {por_estado['bloqueio']} bloqueio"
    )
    linhas.append("")
    # bloqueio e revisar primeiro (o que pede acao), auto-merge por ultimo.
    ordem = {"bloqueio": 0, "revisar": 1, "auto-merge": 2}
    for p in sorted(prs, key=lambda x: (ordem[x["estado"]], x["number"])):
        titulo = p["title"] if len(p["title"]) <= 70 else p["title"][:67] + "..."
        linhas.append(f"{_EMOJI[p['estado']]} #{p['number']} {titulo}")
        linhas.append(f"    {p['motivo']} — {p['url']}")
    if not prs:
        linhas.append("(nenhum PR aberto)")

    linhas.append("")
    linhas.append(
        f"Incidentes DEC-016 (90d): total {incid['total']} "
        f"(reverts na main {incid['reverts']} · CI da main quebrado {incid['ci_falhas']} · "
        f"bypass do guard {incid['bypass_guard']})"
    )
    if incid["suspender"]:
        linhas.append(
            f"🚨 SUSPENSAO recomendada do auto-merge: {incid['total']} incidentes em 90 dias "
            f"(>= {LIMIAR_SUSPENSAO}). Ver kill-switch em docs/portao_merge_orq21.md."
        )
    if capado:
        linhas.append("(auditoria de merges limitada aos mais recentes; contagem pode subestimar.)")
    linhas.append("")
    linhas.append(
        "READ-ONLY — o Auditor informa, nao decide. PII: so links de PR, sem diff. "
        "Cobertura v1: segredos/PII sao barrados pelo gitleaks do CI no PR (nao re-auditados aqui)."
    )
    return "\n".join(linhas)


# --------------------------------------------------------------------------- coleta (I/O; defensiva)
def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _gh_json(*args: str):
    proc = _run(["gh", *args])
    if proc.returncode != 0 or not proc.stdout.strip():
        print(f"::warning::gh {' '.join(args)} falhou: {proc.stderr.strip()[:200]}")
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def _estado_check(c: dict) -> tuple[str, str] | None:
    """Normaliza um item de statusCheckRollup para (nome, 'pass'|'fail'|'pending')."""
    nome = c.get("name") or c.get("context") or ""
    if nome not in REQUIRED_CHECKS:
        return None
    concl = (c.get("conclusion") or "").upper()
    status = (c.get("status") or c.get("state") or "").upper()
    if concl in {"SUCCESS"} or status == "SUCCESS":
        return (nome, "pass")
    if concl in {"FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"} or status in {"FAILURE", "ERROR"}:
        return (nome, "fail")
    return (nome, "pending")


def coletar_prs_abertos() -> list[dict]:
    dados = _gh_json(
        "pr", "list", "--state", "open", "--limit", "100",
        "--json", "number,title,url,isDraft,mergeable,labels,statusCheckRollup",
    )
    if not dados:
        return []
    prs = []
    for pr in dados:
        checks: dict[str, str] = {}
        for c in pr.get("statusCheckRollup") or []:
            norm = _estado_check(c)
            if norm:
                checks[norm[0]] = norm[1]
        labels = {lb["name"] for lb in pr.get("labels") or []}
        estado, motivo = classificar_pr(
            {
                "draft": pr.get("isDraft", False),
                "mergeable": pr.get("mergeable", "UNKNOWN"),
                "labels": labels,
                "checks": checks,
            }
        )
        prs.append(
            {
                "number": pr["number"],
                "title": pr["title"],
                "url": pr["url"],
                "estado": estado,
                "motivo": motivo,
            }
        )
    return prs


def contar_reverts(desde: str) -> int:
    proc = _run(["git", "log", "origin/main", f"--since={desde}", "--grep=^Revert", "--oneline"])
    if proc.returncode != 0:
        return 0
    return sum(1 for ln in proc.stdout.splitlines() if ln.strip())


def contar_ci_falhas_main(desde_dt: _dt.datetime) -> int:
    dados = _gh_json(
        "run", "list", "--workflow", "ci.yml", "--branch", "main", "--limit", "100",
        "--json", "conclusion,createdAt",
    )
    if not dados:
        return 0
    n = 0
    for r in dados:
        if (r.get("conclusion") or "").lower() != "failure":
            continue
        try:
            criado = _dt.datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00"))
        except (ValueError, KeyError):
            continue
        if criado >= desde_dt:
            n += 1
    return n


def _loop_guard_classes(numero: int) -> set[str]:
    diff = _run(["gh", "pr", "diff", str(numero), "--name-only"])
    if diff.returncode != 0 or not diff.stdout.strip():
        return set()
    guard = subprocess.run(
        ["python", "scripts/loop_guard.py", "--stdin", "--json"],
        input=diff.stdout, capture_output=True, text=True, check=False,
    )
    try:
        data = json.loads(guard.stdout)
    except json.JSONDecodeError:
        return set()
    return {v.get("classe", "") for v in data.get("violacoes", [])}


def contar_bypass_guard(desde: str, limite: int = 40) -> tuple[int, bool]:
    """PRs mergeados nos ultimos 90d que tocaram critico/governanca SEM a label humana exigida
    (= bypass do guard, tipicamente admin-merge indevido). Retorna (contagem, capado)."""
    dados = _gh_json(
        "pr", "list", "--state", "merged", "--limit", str(limite),
        "--search", f"merged:>={desde}", "--json", "number,labels",
    )
    if not dados:
        return (0, False)
    capado = len(dados) >= limite
    n = 0
    for pr in dados:
        classes = _loop_guard_classes(pr["number"])
        if not classes:
            continue
        labels = {lb["name"] for lb in pr.get("labels") or []}
        if "critico" in classes and "critica-aprovada" not in labels:
            n += 1
        elif "governanca" in classes and "aprovado-humano" not in labels:
            n += 1
    return (n, capado)


def enviar_telegram(texto: str) -> None:
    token = os.environ.get("API_TELEGRAM_TOKEN", "")
    chat = os.environ.get("MONITOR_TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        print("::warning::API_TELEGRAM_TOKEN/MONITOR_TELEGRAM_CHAT_ID ausentes; pulo o Telegram.")
        return
    dados = urllib.parse.urlencode({"chat_id": chat, "text": texto, "disable_web_page_preview": "true"}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=dados)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 (host fixo do Telegram)
            print(f"Telegram: HTTP {resp.status}")
    except Exception as exc:  # noqa: BLE001 — routine nao pode quebrar por rede
        print(f"::warning::falha ao enviar Telegram: {exc}")


def comentar_issue(texto: str) -> None:
    numero = os.environ.get("AUDITOR_ISSUE_NUMBER", "").strip()
    if not numero:
        print("AUDITOR_ISSUE_NUMBER nao definido; pulo o comentario na issue (so Telegram).")
        return
    proc = _run(["gh", "issue", "comment", numero, "--body", texto])
    if proc.returncode != 0:
        print(f"::warning::falha ao comentar na issue #{numero}: {proc.stderr.strip()[:200]}")


def main() -> int:
    hoje = os.environ.get("AUDITOR_HOJE", "")  # ISO 'YYYY-MM-DD' opcional (testes/repro); senao usa a env do runner
    if hoje:
        agora = _dt.datetime.fromisoformat(hoje).replace(tzinfo=_dt.UTC)
    else:
        # No runner, `date` do ambiente e confiavel; Date.now() do processo tambem.
        agora = _dt.datetime.now(_dt.UTC)
    data_str = agora.strftime("%Y-%m-%d")
    desde_dt = agora - _dt.timedelta(days=JANELA_DIAS)
    desde = desde_dt.strftime("%Y-%m-%d")

    prs = coletar_prs_abertos()
    reverts = contar_reverts(desde)
    ci_falhas = contar_ci_falhas_main(desde_dt)
    bypass, capado = contar_bypass_guard(desde)
    incid = avaliar_incidentes(reverts, ci_falhas, bypass)

    relatorio = compor_relatorio(prs, incid, data_str, capado=capado)
    print(relatorio)
    enviar_telegram(relatorio)
    comentar_issue(relatorio)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
