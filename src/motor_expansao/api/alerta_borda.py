"""Alerta de borda — varreduras COM ASSINATURA contra os hosts do piloto.

Pedido do Felipe (2026-09-23), depois da investigação do "login desconhecido": a
tela de entrar é a primeira rota do produto servida SEM autenticação, e com ela a
internet anônima passou a bater na nossa porta. O alerta existe para separar, na
borda, o ruído de fundo da tentativa dirigida.

POR QUE POR ASSINATURA, E NÃO POR VOLUME — a pergunta do Felipe foi exatamente
essa ("esse log de borda não seria poluído pelos varredores inofensivos?"), e ele
estava certo. Medido em 21 dias do access log de produção:

  * 5.716 requisições barradas no total;
  * 4.488 delas (78%) são o NOSSO PRÓPRIO healthcheck, que bate em `/` a cada
    poucos minutos e é barrado como qualquer anônimo;
  * 85% de tudo pede só `/` — crawler comercial, não ataque.

Um limiar de volume dispararia todo dia por causa de nós mesmos. A regra de
ASSINATURA — pedir um caminho que só faz sentido se você está procurando segredo
ou CMS alheio — é o que separa os dois.

MAS ASSINATURA SOZINHA NÃO BASTA, e isso só apareceu ao rodar a regra contra o
log inteiro (36 dias, 745 requisições com assinatura, de 102 pares IP-dia). A
sondagem de fundo é CONTÍNUA: 23 dos 36 dias têm pelo menos uma, quase sempre um
IP pedindo `.env` uma ou duas vezes e indo embora. Um aviso diário por
assinatura falaria em 2 de cada 3 dias — de novo o ruído que o Felipe apontou,
só que mais caro, porque agora pareceria alarme.

Por isso existe `notavel()`: o texto é gerado sempre (e fica disponível sob
demanda), mas o ENVIO só acontece quando o dia sai do fundo — qualquer 2xx, ou
volume/fan-out acima do normal. Aplicado ao mesmo log, isso dá **10 dias em 36
(0,28/dia)** e acerta exatamente os eventos que importam: a janela de 19–26/08
(6 a 13 IPs por dia) e os dois estouros de 20 e 21/09 (255 e 251 requisições).
Os 13 dias de trickle de um IP só ficam de fora, que é o ponto.

O QUE É ALERTA, E O QUE É SÓ NOTA. Nenhuma das 556 requisições de sondagem
medidas obteve 2xx — todas morreram no `forward_auth` ou no 404. Por isso a linha
que importa no texto não é a contagem, é `atendidas`: sondagem barrada é rotina da
internet; sondagem ATENDIDA é incidente. O texto diz os dois, e nunca resume um no
outro.

JANELA FECHADA, SEM ESTADO. O relatório cobre um dia BRT INTEIRO e já terminado
(ontem, por padrão). Isso dispensa guardar "o que já foi alertado" em disco — não
há estado para corromper, reprocessar é idempotente, e o mesmo IP não é anunciado
duas vezes. O custo é a latência: uma varredura é contada no dia seguinte. Aceito
de propósito, porque não há nada a conter em tempo real (o `forward_auth` já
barrou); o alerta é para SABER, não para reagir em minutos.

READ-ONLY: só lê o access log do Caddy e faz o POST ao Telegram.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
from collections import defaultdict
from collections.abc import Iterable, Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from motor_expansao.api.relatorio_acessos import enviar_telegram

#: BRT fixo (UTC-3). São Paulo não tem horário de verão desde 2019 — mesma
#: premissa (e mesma dívida, se um dia voltar) do `relatorio_acessos`.
_BRT = timedelta(hours=-3)

#: Assinaturas de sondagem: rótulo -> regex sobre a URI em minúsculas.
#:
#: Cada uma foi vista no access log de produção, não inventada. O rótulo vai no
#: texto do alerta porque "3 requisições suspeitas" não dá para julgar, e
#: "procurou .env e .git" dá.
#:
#: O que NÃO entra aqui, e por quê: `/` sozinho (é o que todo crawler pede),
#: `/favicon.ico`, `/robots.txt` e qualquer rota NOSSA. A regra só aceita caminho
#: que não tem leitura inocente neste servidor — não servimos WordPress, não
#: servimos PHP, e nenhum cliente legítimo pede uma chave privada por HTTP.
ASSINATURAS: tuple[tuple[str, str], ...] = (
    ("arquivo .env", r"\.env(\b|$|\.|/)"),
    ("repositório .git", r"/\.git(/|$)"),
    ("WordPress", r"/(wp-admin|wp-content|wp-includes|wp-login|wp-json)"),
    ("XML-RPC", r"/xmlrpc\.php"),
    ("phpMyAdmin", r"/(phpmyadmin|pma|myadmin)(/|$)"),
    ("chave SSH", r"(id_rsa|id_dsa|\.ssh/|authorized_keys)"),
    ("dump de banco", r"\.(sql|sql\.gz|dump|bak)(\b|$)"),
    ("REST do WordPress", r"[?&]rest_route="),
    ("shell PHP", r"\.php(\b|$)"),
    ("config exposta", r"/(config|configuration|settings)\.(json|yml|yaml|php|ini)(\b|$)"),
)

_ASSINATURAS_COMPILADAS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (rotulo, re.compile(padrao)) for rotulo, padrao in ASSINATURAS
)

#: Limiares de NOTABILIDADE — o dia só vira mensagem enviada se cruzar um deles.
#: Calibrados contra os 36 dias de log de produção (ver o docstring do módulo): o
#: fundo é 1 IP com 1–3 requisições, e os dois eventos reais foram 4 e 1 IPs com
#: ~250 requisições cada, mais uma janela de 6–13 IPs/dia. `5` e `20` passam por
#: cima do fundo inteiro e por baixo de todos os eventos — não são redondos por
#: estética, são o vale entre as duas populações.
MINIMO_IPS_NOTAVEL = 5
MINIMO_REQS_NOTAVEL = 20

#: Quantos IPs no máximo o texto lista antes de resumir. Uma varredura
#: distribuída poderia trazer centenas; o teto evita transformar o alerta em
#: parede de texto (o Telegram parte em 4096, mas ninguém lê 300 linhas).
TETO_IPS_NO_TEXTO = 25


def assinaturas_da_uri(uri: str) -> list[str]:
    """Rótulos de assinatura que a URI dispara (vazio = requisição comum)."""
    alvo = uri.lower()
    return [rotulo for rotulo, padrao in _ASSINATURAS_COMPILADAS if padrao.search(alvo)]


def _dia_brt_do_ts(ts: float) -> date:
    return (datetime.fromtimestamp(ts, UTC) + _BRT).date()


def _hora_brt_do_ts(ts: float) -> str:
    return (datetime.fromtimestamp(ts, UTC) + _BRT).strftime("%H:%M")


def ler_linhas(diretorio: Path) -> Iterator[str]:
    """Linhas de todos os access logs do Caddy — vivos e rotacionados (.gz).

    Ler o `.gz` NÃO é zelo: a rotação do Caddy é por TAMANHO, não por dia, então
    o dia de ontem pode ter sido cortado no meio e metade dele estar no arquivo
    comprimido. Sem isso o alerta perderia justamente o dia de mais tráfego, que
    é o que enche o arquivo e dispara a rotação.
    """
    if not diretorio.is_dir():
        return
    for arquivo in sorted(diretorio.iterdir()):
        nome = arquivo.name
        if not nome.endswith((".log", ".log.gz")) or "access" not in nome:
            continue
        try:
            if nome.endswith(".gz"):
                with gzip.open(arquivo, "rt", encoding="utf-8", errors="replace") as fh:
                    yield from fh
            else:
                with arquivo.open("r", encoding="utf-8", errors="replace") as fh:
                    yield from fh
        except OSError:
            continue  # arquivo em rotação neste instante; o próximo run pega


def agregar_sondagens(linhas: Iterable[str], dia_brt: date) -> dict[str, dict]:
    """Agrupa por IP as requisições COM assinatura do dia BRT pedido.

    Devolve, por IP: total de sondagens, quantas foram ATENDIDAS (2xx — a única
    contagem que transforma nota em incidente), assinaturas disparadas, hosts
    visados, primeira e última hora, e um exemplo de URI e de user-agent.
    """
    por_ip: dict[str, dict] = defaultdict(
        lambda: {
            "total": 0,
            "atendidas": 0,
            "assinaturas": set(),
            "hosts": set(),
            "ini": None,
            "fim": None,
            "exemplo": "",
            "agente": "",
        }
    )
    for linha in linhas:
        linha = linha.strip()
        if not linha or linha[0] != "{":
            continue
        try:
            evento = json.loads(linha)
        except ValueError:
            continue
        ts = evento.get("ts")
        pedido = evento.get("request")
        if not isinstance(ts, (int, float)) or not isinstance(pedido, dict):
            continue
        if _dia_brt_do_ts(float(ts)) != dia_brt:
            continue
        uri = str(pedido.get("uri") or "")
        rotulos = assinaturas_da_uri(uri)
        if not rotulos:
            continue

        ip = str(pedido.get("client_ip") or pedido.get("remote_ip") or "?")
        reg = por_ip[ip]
        reg["total"] += 1
        status = evento.get("status")
        if isinstance(status, int) and 200 <= status < 300:
            reg["atendidas"] += 1
        reg["assinaturas"].update(rotulos)
        if host := str(pedido.get("host") or ""):
            reg["hosts"].add(host)
        hora = _hora_brt_do_ts(float(ts))
        if reg["ini"] is None or hora < reg["ini"]:
            reg["ini"] = hora
        if reg["fim"] is None or hora > reg["fim"]:
            reg["fim"] = hora
        if not reg["exemplo"]:
            reg["exemplo"] = uri[:120]
        if not reg["agente"]:
            agentes = (pedido.get("headers") or {}).get("User-Agent") or []
            if agentes:
                reg["agente"] = str(agentes[0])[:80]
    return dict(por_ip)


def _dia_padrao() -> date:
    """Ontem em BRT — a última janela FECHADA (ver o docstring do módulo)."""
    return (datetime.now(UTC) + _BRT).date() - timedelta(days=1)


def notavel(por_ip: dict[str, dict]) -> bool:
    """O dia sai do ruído de fundo? (ver `MINIMO_*_NOTAVEL` e o docstring.)

    Qualquer 2xx é notável SOZINHO, sem limiar nenhum: uma sondagem atendida é a
    única coisa aqui que muda o estado do sistema, e esperar ela se repetir 20
    vezes para avisar seria o desenho errado.
    """
    if not por_ip:
        return False
    if any(r["atendidas"] for r in por_ip.values()):
        return True
    if len(por_ip) >= MINIMO_IPS_NOTAVEL:
        return True
    return sum(r["total"] for r in por_ip.values()) >= MINIMO_REQS_NOTAVEL


def gerar_alerta(diretorio: Path, dia_brt: date | None = None) -> str:
    # `dia` resolvido UMA vez: `_dia_padrao()` chamado duas vezes poderia cair em
    # dias diferentes se a virada acontecesse entre as duas chamadas.
    dia = dia_brt or _dia_padrao()
    return montar_texto(dia, agregar_sondagens(ler_linhas(diretorio), dia))


def montar_texto(dia: date, por_ip: dict[str, dict]) -> str:
    cabecalho = f"Borda — varreduras com assinatura em {dia.strftime('%d/%m/%Y')} (BRT)"
    if not por_ip:
        return f"{cabecalho}\n\nNenhuma sondagem com assinatura."

    atendidas = sum(r["atendidas"] for r in por_ip.values())
    total = sum(r["total"] for r in por_ip.values())
    plural = "IP" if len(por_ip) == 1 else "IPs"
    veredito = (
        f"ATENÇÃO: {atendidas} requisição(ões) de sondagem foram ATENDIDAS (2xx)."
        if atendidas
        else "Todas barradas (nenhuma resposta 2xx)."
    )
    corpo = [cabecalho, f"{len(por_ip)} {plural} · {total} requisições · {veredito}", ""]

    ordem = sorted(por_ip.items(), key=lambda kv: (-kv[1]["atendidas"], -kv[1]["total"]))
    for ip, reg in ordem[:TETO_IPS_NO_TEXTO]:
        marca = " [ATENDIDA]" if reg["atendidas"] else ""
        corpo.append(f"• {ip} — {reg['total']}x · {reg['ini']}–{reg['fim']}{marca}")
        corpo.append(f"  procurou: {', '.join(sorted(reg['assinaturas']))}")
        corpo.append(f"  em: {', '.join(sorted(reg['hosts'])) or '—'} · ex.: {reg['exemplo']}")
        if reg["agente"]:
            corpo.append(f"  agente: {reg['agente']}")
    if len(ordem) > TETO_IPS_NO_TEXTO:
        corpo.append(f"(+{len(ordem) - TETO_IPS_NO_TEXTO} IPs não listados)")
    return "\n".join(corpo)


def alerta_vazio(texto: str) -> bool:
    return "Nenhuma sondagem com assinatura" in texto


def main(argv: list[str] | None = None) -> int:
    """CLI do cron: imprime o alerta; com `--enviar`, manda ao chat de alertas.

    Credenciais SÓ por env (nunca argumento, para não vazar em `ps`), igual ao
    `relatorio_acessos`: `API_TELEGRAM_TOKEN` e `MONITOR_TELEGRAM_CHAT_ID`.
    """
    parser = argparse.ArgumentParser(description="Alerta de varredura na borda (access log do Caddy)")
    parser.add_argument("--dir", default="/var/log/caddy", help="diretório dos access logs")
    parser.add_argument("--dia", default=None, help="dia BRT AAAA-MM-DD (padrão: ontem)")
    parser.add_argument("--enviar", action="store_true", help="envia ao chat de alertas")
    parser.add_argument("--pular-vazio", action="store_true",
                        help="não envia quando não houve sondagem no dia")
    parser.add_argument("--so-notavel", action="store_true",
                        help="só envia quando o dia sai do ruído de fundo (é o que o cron usa)")
    args = parser.parse_args(argv)

    dia = date.fromisoformat(args.dia) if args.dia else _dia_padrao()
    por_ip = agregar_sondagens(ler_linhas(Path(args.dir)), dia)
    texto = montar_texto(dia, por_ip)
    print(texto)
    if not args.enviar:
        return 0
    if args.pular_vazio and not por_ip:
        print(">> sem sondagem; envio pulado (--pular-vazio)")
        return 0
    if args.so_notavel and not notavel(por_ip):
        print(">> dia dentro do ruído de fundo; envio pulado (--so-notavel)")
        return 0
    token = os.environ.get("API_TELEGRAM_TOKEN", "").strip()
    chat_id = os.environ.get("MONITOR_TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("!! API_TELEGRAM_TOKEN/MONITOR_TELEGRAM_CHAT_ID ausentes", file=sys.stderr)
        return 1
    try:
        enviar_telegram(texto, token, chat_id)
    except RuntimeError as erro:
        print(f"!! {erro}", file=sys.stderr)
        return 1
    print(">> enviado ao chat de alertas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
