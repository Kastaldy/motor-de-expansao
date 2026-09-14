"""Aviso da atualizacao trimestral no chat de ops do Telegram (bot "Paulo").

Reusa `enviar_telegram` de `motor_expansao.api.relatorio_acessos` — o molde ja'
paga duas dividas que este modulo NAO quer pagar de novo: particao por blocos
abaixo do teto de 4096 do Telegram, e falha SEM vazar o token (o HTTPError do
requests embute a URL, e stderr de cron vai para log em disco).

O texto e' voltado ao usuario, logo ACENTUADO (CLAUDE.md §2), e e' HONESTO sobre o
que a rodada move: a SERIE de Emprego (CAGED, mensal), o rotulo de periodo e
`cres_salario`/`cres_salario_var`. O percentual da dimensao e o veredito
(`dim_emprego_pct` -> `pos_emprego` -> `v_classe`) vem do CSV anual do projeto TEC
— raiz externa LIDA, nunca regenerada pelo job — e ficam parados ate' aquela safra
avancar; renda, PIB, empresas e populacao seguem anuais e o satelite e' 2016-2023
estatico. Fingir que tudo atualizou seria o "documento com numero que envelhece
calado" em forma de mensagem.

Credenciais por ambiente (`API_TELEGRAM_TOKEN` + `MONITOR_TELEGRAM_CHAT_ID`, as
mesmas do healthcheck e do relatorio de acessos); `--stdout` imprime em vez de
enviar (modo seco do wrapper e testes).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def _linha_vereditos(contagem: dict[str, int]) -> str:
    if not contagem:
        return "sem leitura"
    partes = [f"{k}: {v}" for k, v in sorted(contagem.items(), key=lambda kv: -kv[1])]
    return ", ".join(partes)


def montar_sucesso(resumo: dict[str, Any]) -> str:
    meses = resumo.get("meses_caged_novos") or []
    if meses:
        legivel = ", ".join(meses)
        linha_caged = f"CAGED incorporou {len(meses)} mês(es) novo(s): {legivel}."
    else:
        linha_caged = "CAGED já estava em dia (nenhum mês novo publicado no PDET)."
    linhas = [
        "🟢 [Motor] Camada de crescimento municipal atualizada.",
        linha_caged,
        f"Emprego agora cobre até {resumo.get('emprego_ate', '?')}.",
        (
            f"Artefato: {resumo.get('municipios', '?')} municípios "
            f"({resumo.get('colunas_municipal', '?')} colunas) e "
            f"{resumo.get('hexes', '?')} hexágonos."
        ),
        (
            f"Vereditos: {_linha_vereditos(resumo.get('vereditos_depois') or {})} "
            "(inalterados por construção numa rodada só-CAGED: derivam do CSV "
            "anual do TEC)."
        ),
        (
            "Lembrete de idade por dimensão: o percentual e o veredito de Emprego "
            "só avançam com a safra do TEC; renda, população e empresas seguem "
            "nas safras anuais; prédios (satélite) cobre 2016-2023."
        ),
    ]
    if not resumo.get("publicado", True):
        linhas.insert(1, "(rodada de validação: NADA foi publicado no staging)")
    return "\n".join(linhas)


def montar_falha(etapa: str) -> str:
    """A descricao da etapa vem do WRAPPER e ja' carrega o estado do staging.

    Nada de linha fixa "staging intacto" aqui: ela seria FALSA quando a falha vem
    depois da publicacao (prova de legibilidade, restart) — e uma mensagem que se
    contradiz custa mais que nenhuma (defeito pego na revisao adversarial).
    """
    return "\n".join(
        [
            "🔴 [Motor] Atualização trimestral do crescimento municipal FALHOU.",
            f"Etapa: {etapa}.",
            "Log: /var/log/motor-snapshots/atualizacao_crescimento_latest.log",
        ]
    )


def enviar(texto: str, stdout: bool = False) -> None:
    if stdout:
        print(texto)
        return
    token = os.environ.get("API_TELEGRAM_TOKEN", "")
    chat = os.environ.get("MONITOR_TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        raise SystemExit(
            "API_TELEGRAM_TOKEN/MONITOR_TELEGRAM_CHAT_ID ausentes no ambiente — "
            "o wrapper exporta os dois a partir do .env do compose."
        )
    import requests  # noqa: PLC0415 — mesmo cliente HTTP do molde

    from motor_expansao.api.relatorio_acessos import enviar_telegram

    try:
        enviar_telegram(texto, token, chat)
    except requests.RequestException as exc:
        # ConnectionError/Timeout do requests embutem a URL (com o token) na
        # mensagem, e stderr de cron vai para log em disco — relanca so' a classe.
        raise RuntimeError(f"envio ao Telegram falhou: {type(exc).__name__}") from None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    grupo = ap.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--resumo", type=Path, help="JSON gravado pelo atualizar.py")
    grupo.add_argument("--falha", type=str, help="nome da etapa que falhou")
    ap.add_argument("--stdout", action="store_true", help="imprime em vez de enviar")
    args = ap.parse_args(argv)

    if args.falha:
        texto = montar_falha(args.falha)
    else:
        resumo = json.loads(args.resumo.read_text(encoding="utf-8"))
        texto = montar_sucesso(resumo)
    enviar(texto, stdout=args.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
