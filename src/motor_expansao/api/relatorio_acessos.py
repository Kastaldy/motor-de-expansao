"""Relatório de acessos do piloto por usuário — agregado da trilha (DEC-027).

Pedido do Felipe (2026-08-18): "quem logou e quais abas acessou (agregado)", puxável
pelo Telegram sob demanda (comando `/acessos` no chat de operações) e enviado
automaticamente a cada 3h no mesmo chat de alertas (cron da VPS,
`scripts/cron/run_relatorio_acessos.sh`).

O QUE o relatório mostra (e o que NÃO mostra, de propósito): usuário, janela de
atividade do dia e o CONJUNTO de abas acessadas — nunca rota, query, ponto
consultado ou qualquer detalhe do que a pessoa fez. O detalhe fino continua só na
trilha bruta (`docs/trilha_acesso_piloto.md`).

O DIA do relatório é o dia LOCAL (BRT, UTC-3 fixo — São Paulo não tem horário de
verão desde 2019). A trilha grava um arquivo por dia UTC, então um dia BRT vive em
DOIS arquivos (o do mesmo nome e o do dia UTC seguinte, que carrega 21h–24h BRT);
o gerador lê os dois e filtra pelo dia BRT — sem isso, entre 21h e meia-noite BRT
o relatório negaria o dia inteiro (defeito pego na revisão adversarial).

Texto SEM parse_mode/Markdown de propósito: nome de usuário vem cru do Authelia
(`ana_souza` tem underscore) e derrubaria o parse do Telegram; texto puro elimina
a classe inteira (injeção de formatação + 400 can't parse entities).

READ-ONLY: este módulo só LÊ a trilha; nunca escreve nada além do POST ao Telegram.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

#: Prefixo de rota -> aba de EXIBIÇÃO. Espelho de apresentação das
#: `REGRAS_DE_ACESSO` de `web/server/acesso.py` — rota liberada por mais de uma
#: aba (ex.: `/api/relatorio/pontual`) é atribuída aqui à aba onde o uso acontece
#: na prática. O teste de contrato `test_relatorio_acessos.py::
#: test_agrupamento_cobre_as_regras_de_acesso` trava a consistência entre os dois
#: (mudou lá, o CI aponta aqui).
AGRUPAMENTO_ABAS: tuple[tuple[str, str], ...] = (
    ("/api/rede/", "executiva"),
    ("/api/executiva/", "executiva"),
    ("/api/simulador/", "viabilidade"),
    ("/api/faixa-alunos", "viabilidade"),
    ("/api/viabilidade", "viabilidade"),
    ("/api/relatorio/pontual", "viabilidade"),
    ("/api/geocode", "mapa"),
    ("/api/resolver-ponto", "mapa"),
    ("/api/ponto", "mapa"),
    ("/api/cobertura/", "mapa"),
    ("/api/relatorio/municipal", "mapa"),
    # O deck de comparacao sai das telas de mapa (hexagonos no Explorar, pontos no
    # modo de imovel) — nao da Viabilidade, que ele nao carrega por DEC-009.
    ("/api/relatorio/comparacao", "mapa"),
    ("/api/uf/", "mapa"),
    ("/api/municipio/", "mapa"),
    ("/api/municipios/", "mapa"),
    ("/api/estados", "oportunidades"),
    # Ranking nacional por hexagono (DEC-044): a outra leitura do MESMO Modo 3,
    # entao conta na mesma aba que o ranking de estados.
    ("/api/hexagonos", "oportunidades"),
    # O dossie e' gesto da aba imobiliaria; a LISTA, liberada tambem para "mapa",
    # e' buscada sozinha pelo Mapa Territorial a cada UF (camada de pins + secao do
    # hexagono) — na pratica o grosso das chamadas vem de la', entao e' la' que ela
    # conta (mesma logica do relatorio pontual, atribuido a viabilidade).
    ("/api/oportunidades/", "imobiliaria"),
    ("/api/oportunidades", "mapa"),
    # Gestos da tela imobiliaria (rotas no-op da trilha): contam SEMPRE na aba
    # imobiliaria, mesmo quando disparados do Mapa Territorial — a query `origem`
    # e' que diz de onde vieram; aqui a pergunta e' "quanto a camada foi usada".
    ("/api/imobiliaria/evento/", "imobiliaria"),
    # A foto do balao e' disparada pelo Mapa Territorial, que e' onde o pino mora: das
    # duas abas que a LIBERAM, "mapa" e' onde o uso acontece na pratica (mesma logica do
    # relatorio pontual, atribuido a viabilidade).
    ("/api/foto-concorrente/", "mapa"),
)

#: Camada de LABEL (CLAUDE.md §2): valor bruto sem acento; exibição acentuada.
LABEL_ABA = {
    "executiva": "Executiva",
    "imobiliaria": "Imobiliária",
    "mapa": "Mapa",
    "oportunidades": "Oportunidades",
    "viabilidade": "Viabilidade",
}

#: Fuso de exibição/agrupamento. Fixo UTC-3 (ver docstring do módulo).
_FUSO_BRT = timedelta(hours=-3)

#: Rotas AUDITADAS na trilha mas INVISÍVEIS nas métricas de uso (prefixos): o
#: painel de acessos (aba restrita, emenda DEC-027 de 2026-08-19) observaria a si
#: mesmo — o admin abrindo o painel inflaria as próprias contagens e viraria ruído
#: no relatório de 3/3h. O painel usa este MESMO filtro (`evento_valido`), então
#: Telegram e aba nunca divergem.
ROTAS_FORA_DA_METRICA: tuple[str, ...] = ("/api/acessos",)

_PREFIXO_TRILHA = "acesso-"
_SUFIXO_TRILHA = ".jsonl"

#: Teto do sendMessage é 4096; blocos de 3900 deixam folga para o cabeçalho de
#: continuação sem nunca partir uma linha ao meio.
_TETO_BLOCO_TELEGRAM = 3900


def _aba_da_rota(rota: str) -> str | None:
    for prefixo, aba in AGRUPAMENTO_ABAS:
        if rota.startswith(prefixo):
            return aba
    return None


def _quando_brt(bruto: object) -> datetime | None:
    """Timestamp da linha convertido para BRT; None se ilegível."""
    try:
        return datetime.fromisoformat(str(bruto)) + _FUSO_BRT
    except (ValueError, TypeError):
        return None


def evento_valido(r: object) -> bool:
    """Se a linha da trilha conta como USO: objeto JSON, não-diagnóstico, não-painel.

    Filtro ÚNICO das duas superfícies de métrica (relatório do Telegram e aba
    Acessos do piloto): descarta linha que não seja objeto, requisição de
    diagnóstico interno (user-agent `curl`) e as rotas do próprio painel
    (`ROTAS_FORA_DA_METRICA` — auditadas na trilha, fora das contagens).
    """
    if not isinstance(r, dict) or "curl" in str(r.get("agente", "")):
        return False
    return not str(r.get("rota", "")).startswith(ROTAS_FORA_DA_METRICA)


def agregar_acessos(linhas: Iterable[str], dia_brt: date | None = None) -> dict[str, dict]:
    """`{usuario: {"ini", "fim" (HH:MM BRT), "acoes", "abas" (set)}}`.

    Com `dia_brt`, só entram linhas daquele dia LOCAL. Linha ilegível ou que não
    seja um objeto JSON é ignorada (a trilha é rastro, não transação), assim como
    as requisições de diagnóstico interno (user-agent `curl`) e as do painel de
    acessos (`evento_valido`).
    """
    usuarios: dict[str, dict] = {}
    for bruta in linhas:
        try:
            r = json.loads(bruta)
        except (ValueError, TypeError):
            continue
        if not evento_valido(r):
            continue
        momento = _quando_brt(r.get("quando"))
        if dia_brt is not None and (momento is None or momento.date() != dia_brt):
            continue
        nome = str(r.get("usuario") or "desconhecido")
        u = usuarios.setdefault(nome, {"ini": None, "fim": None, "acoes": 0, "abas": set()})
        u["acoes"] += 1
        if momento is not None:
            hhmm = momento.strftime("%H:%M")
            u["ini"] = min(u["ini"] or hhmm, hhmm)
            u["fim"] = max(u["fim"] or hhmm, hhmm)
        aba = _aba_da_rota(str(r.get("rota", "")))
        if aba:
            u["abas"].add(aba)
    return usuarios


def arquivos_do_dia_brt(diretorio: Path, dia_brt: date) -> list[Path]:
    """Os DOIS arquivos UTC que compõem um dia BRT (ver docstring do módulo)."""
    return [
        diretorio / f"{_PREFIXO_TRILHA}{d.isoformat()}{_SUFIXO_TRILHA}"
        for d in (dia_brt, dia_brt + timedelta(days=1))
    ]


def gerar_relatorio(diretorio: Path, agora_utc: datetime | None = None) -> str:
    """Texto pronto para o Telegram (texto PURO, sem Markdown), acentuação correta."""
    agora = agora_utc or datetime.now(UTC)
    agora_brt = agora + _FUSO_BRT
    dia_brt = agora_brt.date()
    cabecalho = (
        f"📊 Acessos do piloto — {agora_brt.strftime('%d/%m')} "
        f"(até {agora_brt.strftime('%H:%M')} BRT)"
    )

    linhas: list[str] = []
    for arquivo in arquivos_do_dia_brt(Path(diretorio), dia_brt):
        try:
            linhas.extend(arquivo.read_text(encoding="utf-8").splitlines())
        except OSError:
            continue  # arquivo do dia UTC seguinte normalmente ainda nao existe

    usuarios = agregar_acessos(linhas, dia_brt=dia_brt)
    if not usuarios:
        return f"{cabecalho}\n\nNenhum acesso registrado hoje ainda."

    corpo: list[str] = []
    for nome, u in sorted(usuarios.items(), key=lambda kv: kv[1]["ini"] or "99:99"):
        abas = ", ".join(LABEL_ABA.get(a, a) for a in sorted(u["abas"]))
        janela = f"{u['ini']}–{u['fim']}" if u["ini"] else "—"
        corpo.append(f"• {nome} — {janela} · {abas or 'só entrou'}")
    plural = "usuário" if len(usuarios) == 1 else "usuários"
    return f"{cabecalho}\n{len(usuarios)} {plural} hoje:\n" + "\n".join(corpo)


def relatorio_vazio(texto: str) -> bool:
    return "Nenhum acesso registrado" in texto


def _blocos(texto: str, teto: int = _TETO_BLOCO_TELEGRAM) -> list[str]:
    """Parte o texto por LINHAS em blocos abaixo do teto do Telegram (4096)."""
    blocos: list[str] = []
    atual: list[str] = []
    tamanho = 0
    for linha in texto.splitlines():
        if atual and tamanho + len(linha) + 1 > teto:
            blocos.append("\n".join(atual))
            atual, tamanho = ["(continuação)"], len("(continuação)")
        atual.append(linha)
        tamanho += len(linha) + 1
    if atual:
        blocos.append("\n".join(atual))
    return blocos


def enviar_telegram(texto: str, token: str, chat_id: str) -> None:
    """POST sendMessage em texto puro, por blocos.

    Em falha, levanta RuntimeError com STATUS + description truncada — NUNCA a URL
    (o `raise_for_status` do requests embute o token na mensagem do HTTPError, e o
    stderr do cron vai para log em disco; defeito pego na revisão adversarial).
    Mesmo padrão do `_enviar` do bot.
    """
    import requests  # noqa: PLC0415 — mesmo cliente HTTP do bot

    for bloco in _blocos(texto):
        resposta = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": bloco},
            timeout=30,
        )
        if not resposta.ok:
            try:
                descricao = str(resposta.json().get("description", ""))[:120]
            except ValueError:
                descricao = ""
            raise RuntimeError(f"sendMessage falhou: HTTP {resposta.status_code} {descricao}")


def main(argv: list[str] | None = None) -> int:
    """CLI do cron: imprime o relatório; com `--enviar`, manda ao chat de alertas.

    Credenciais SÓ por env (nunca argumento, para não vazar em `ps`):
    `API_TELEGRAM_TOKEN` e `MONITOR_TELEGRAM_CHAT_ID`. `--pular-vazio` evita o
    ruído de madrugada: relatório sem nenhum usuário não é enviado (só logado).
    """
    parser = argparse.ArgumentParser(description="Relatório de acessos do piloto (trilha DEC-027)")
    parser.add_argument("--dir", default="/app/logs/acesso", help="diretório da trilha")
    parser.add_argument("--enviar", action="store_true", help="envia ao chat de alertas")
    parser.add_argument("--pular-vazio", action="store_true",
                        help="não envia quando não houve acesso no dia")
    args = parser.parse_args(argv)

    texto = gerar_relatorio(Path(args.dir))
    print(texto)
    if not args.enviar:
        return 0
    if args.pular_vazio and relatorio_vazio(texto):
        print(">> relatório vazio; envio pulado (--pular-vazio)")
        return 0
    token = os.environ.get("API_TELEGRAM_TOKEN", "").strip()
    chat_id = os.environ.get("MONITOR_TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("!! API_TELEGRAM_TOKEN/MONITOR_TELEGRAM_CHAT_ID ausentes", file=sys.stderr)
        return 1
    try:
        enviar_telegram(texto, token, chat_id)
    except RuntimeError as erro:
        # Mensagem controlada (sem token). Traceback aqui iria para o log do cron.
        print(f"!! {erro}", file=sys.stderr)
        return 1
    print(">> enviado ao chat de alertas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
