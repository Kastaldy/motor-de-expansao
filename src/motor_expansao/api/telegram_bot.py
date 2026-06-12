"""Cliente Telegram da API GeoEspacial (BLK-API-07 / G4) — bot conversacional.

Bot de long-polling (via `requests`), DESACOPLADO: consome o `POST /analisar` por
HTTP. Proposito unico: receber uma localizacao e devolver o Relatorio Pontual
Censitario 1.5 km (PDF). Maquina simples por chat:

  acesso por SENHA -> menu (/start) -> [Relatorio | Ajuda]
  qualquer localizacao enviada (Maps link / "lat,lng" / endereco+CEP) -> PDF.

Ponto plugavel: `geo` (geocoding endereco+CEP -> coordenada).

Rodar (com a API no ar):
    API_TELEGRAM_TOKEN=... python -m motor_expansao.api.telegram_bot
"""

from __future__ import annotations

import json
import socket
from collections.abc import Callable
from typing import Any

import requests
import urllib3.util.connection as _urllib3_cn

from motor_expansao.api import geo
from motor_expansao.api.coord import CoordenadaInvalidaError, parse_maps_url
from motor_expansao.api.settings import Settings, get_settings

# Forca IPv4: nesta rede o IPv6 do api.telegram.org da timeout (~20s) e travava
# TODA chamada ao Telegram. Sem isso, ate o /start demora ~22s por mensagem.
_urllib3_cn.allowed_gai_family = lambda: socket.AF_INET

# Sessao unica: reusa a conexao TCP/TLS (evita re-handshake a cada chamada).
_session = requests.Session()

_TELEGRAM = "https://api.telegram.org/bot{token}/{method}"

_KB_MENU = [["Relatorio"], ["Ajuda"]]

_SAUDACAO = (
    "👋 Olá! Eu sou o *Paulo*, assistente de estudos geoespaciais da *Ultra*.\n\n"
    "Eu gero o *Relatorio Pontual Censitario* (raio de 1.5 km) de qualquer ponto — "
    "com populacao, renda, densidade e score do entorno, em PDF.\n\n"
    "🔒 Este bot e de uso restrito.\n"
    "Para continuar, envie a *senha* de acesso."
)

_SENHA_INCORRETA = "🔒 Senha incorreta. Tente novamente — envie a *senha* de acesso."

_PEDIR_LOGIN = (
    "✅ Senha correta!\n\n"
    "Antes de comecar, *como posso te chamar?*\n"
    "Envie seu nome ou login (fica registrado em cada estudo)."
)

# Instrucoes de localizacao — claras sobre QUANDO/COMO e que endereco e o ultimo caso.
_PEDIR_LOCAL = (
    "📍 *Me envie a localizacao do ponto agora.* Escolha uma forma:\n\n"
    "1️⃣ *Link do Google Maps* — cole o link (mais simples)\n"
    "2️⃣ *Latitude e longitude* — ex.: `-21.9180,-46.6855`\n"
    "3️⃣ *Endereco + CEP* — usar so se NAO tiver as opcoes acima "
    "(ainda em ajuste, menos preciso)\n\n"
    "É so enviar a mensagem — eu gero o relatorio em PDF. 📄"
)

_GERANDO = (
    "⏳ Recebi! Estou localizando o ponto e gerando o *Relatorio Pontual Censitario* "
    "em PDF. Pode levar cerca de 2 minutos — ja te aviso aqui. 📄"
)

_AJUDA = (
    "ℹ️ *Sobre o Paulo*\n\n"
    "Sou o assistente de estudos geoespaciais da *Ultra*. A partir de um ponto, gero "
    "o *Relatorio Pontual Censitario* (raio de 1.5 km) em PDF — com populacao, renda, "
    "densidade e score do entorno.\n\n"
    "*Comandos:*\n"
    "• *Relatorio* — me peca para gerar um estudo\n"
    "• *Ajuda* — mostra esta descricao\n"
    "• /start — recomeca\n\n"
    "As 3 formas de localizacao estao no passo de *Relatorio*."
)


# --- estado por chat (so o acesso precisa de estado) ------------------------
# PERSISTIDO em disco (settings.bot_sessoes_path): sem isso, todo restart do bot
# apagava quem estava logado e a pessoa tinha que digitar a senha de novo.
_sessoes: dict[int, dict] = {}


def _sessao(chat_id: int) -> dict:
    return _sessoes.setdefault(chat_id, {"autorizado": False})


def _carregar_sessoes(settings: Settings) -> None:
    """Carrega as sessoes do disco no arranque (chaves chat_id voltam a int)."""
    try:
        dados = json.loads(settings.bot_sessoes_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return
    if isinstance(dados, dict):
        for chat_id, sessao in dados.items():
            try:
                _sessoes[int(chat_id)] = sessao
            except (TypeError, ValueError):
                continue


def _salvar_sessoes(settings: Settings) -> None:
    """Grava as sessoes no disco (best-effort; nunca derruba o bot se falhar)."""
    try:
        path = settings.bot_sessoes_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({str(k): v for k, v in _sessoes.items()}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


# --- chamadas a API GeoEspacial --------------------------------------------


def _headers(settings: Settings) -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.api_call_token}"}


def consultar_pdf(payload: dict, settings: Settings) -> bytes | None:
    url = f"{settings.api_base_url}{settings.api_prefix}/analisar?formato=pdf"
    try:
        # 240s: o 1o PDF pode demorar (cold load dos parquets); o normal e ~10s.
        resp = _session.post(url, json=payload, headers=_headers(settings), timeout=240)
    except requests.RequestException:
        return None
    if resp.status_code == 200 and resp.content[:4] == b"%PDF":
        return resp.content
    return None


def _erro_api(payload: dict, settings: Settings) -> str:
    """Mensagem de erro amigavel quando o PDF nao sai (404 base, timeout, etc.)."""
    url = f"{settings.api_base_url}{settings.api_prefix}/analisar"
    try:
        resp = _session.post(url, json=payload, headers=_headers(settings), timeout=60)
        if resp.status_code == 200:
            # O ponto e VALIDO (o JSON resolveu), mas o PDF nao voltou — em geral
            # timeout na 1a geracao. NAO chamar isso de "Erro 200".
            return ("O ponto e valido, mas a geracao do PDF demorou demais. "
                    "Tente enviar a mesma localizacao de novo (a 2a costuma sair rapido).")
        return resp.json().get("detail", f"Erro {resp.status_code}")
    except (requests.RequestException, ValueError):
        return "Nao consegui falar com a API."


# --- localizacao -> (lat, lng, nome) ---------------------------------------


def resolver_local(texto: str, settings: Settings) -> tuple[float, float, str] | None:
    """Maps link (curto ou completo) / 'lat,lng' / endereco+CEP -> (lat, lng, nome).

    O `nome` prioriza o ENDERECO/ESTABELECIMENTO do link (/maps/place/...) quando existe,
    mesmo que o link tambem traga coordenada — assim a capa do PDF mostra o nome, nao a
    coordenada. So cai para "lat, lng" quando nao ha nome (ex.: pino solto / lat,lng cru).
    """
    # 1) Parse direto: link COMPLETO do Maps ou "lat,lng" (sem rede).
    try:
        lat, lng = parse_maps_url(texto)
        nome = geo.extrair_endereco_de_place_url(texto) or geo.nome_do_local(lat, lng, settings)
        return lat, lng, nome
    except CoordenadaInvalidaError:
        pass
    # 2) Tem URL e nao parseou -> link COMPACTADO: expande (segue redirect).
    expandido = geo.expandir_link_curto(texto)
    if expandido != texto:
        # Nome do place na URL expandida (vale tanto p/ link com coord quanto sem).
        nome_place = geo.extrair_endereco_de_place_url(expandido)
        try:
            lat, lng = parse_maps_url(expandido)
            nome = nome_place or geo.nome_do_local(lat, lng, settings)
            return lat, lng, nome
        except CoordenadaInvalidaError:
            pass
        # 2b) Link de /place SEM coordenada na URL: geocoda o endereco extraido.
        if nome_place:
            resultado = geo.geocodificar_endereco(nome_place, settings)
            if resultado is not None:
                return resultado
    # 3) Endereco + CEP digitado direto (geocoding).
    return geo.geocodificar_endereco(texto, settings)


# --- maquina de estados -----------------------------------------------------


def _msg(texto: str, keyboard: list | None = None) -> dict:
    return {"text": texto, "keyboard": keyboard}


def processar(
    chat_id: int,
    texto: str,
    settings: Settings,
    notify: Callable[[str], None] | None = None,
) -> list[dict]:
    """Processa uma mensagem e devolve acoes a enviar.

    Acao: {"text": str, "keyboard": list|None} ou {"pdf": bytes}. Testavel
    (nao toca a rede do Telegram).

    `notify`: callback opcional para enviar um aviso INTERMEDIARIO antes do trabalho
    pesado (geocoding ~14s + geracao do PDF). Sem ele (testes) nada e enviado no meio;
    no bot real, o loop passa um notify que manda "⏳ Gerando..." na hora, pra pessoa
    nao achar que travou.
    """
    s = _sessao(chat_id)
    t = (texto or "").strip()
    low = t.lower()

    # 1. Acesso por senha (saudacao na 1a interacao).
    if not s.get("autorizado"):
        if t == settings.bot_senha:
            s["autorizado"] = True
            s["etapa"] = "login"
            return [_msg(_PEDIR_LOGIN)]
        if not s.get("saudou"):
            s["saudou"] = True
            return [_msg(_SAUDACAO)]
        return [_msg(_SENHA_INCORRETA)]

    # 2. Login (nome/identificador) — uma vez, logo apos a senha.
    if s.get("etapa") == "login":
        s["login"] = t.strip() or "anonimo"
        s["etapa"] = None
        return [
            _msg(f"Prazer, *{s['login']}*! 👋", _KB_MENU),
            _msg(_PEDIR_LOCAL, _KB_MENU),
        ]

    # 2. Comandos.
    if low in ("/start", "menu", "/menu", "relatorio", "relatório", "/relatorio"):
        return [_msg(_PEDIR_LOCAL, _KB_MENU)]
    if low in ("ajuda", "/ajuda", "/help"):
        return [_msg(_AJUDA, _KB_MENU)]
    # "Analisar" foi removido — trata um toque no botao fantasma (teclado antigo
    # em cache no Telegram) de forma limpa e ja troca o teclado para o atual.
    if low in ("analisar", "/analisar"):
        return [_msg("Esse botao saiu. 🙂 Toque em *Relatorio* para gerar um estudo.", _KB_MENU)]

    # 3. Qualquer outra mensagem = localizacao -> PDF.
    # Avisa ANTES do trabalho pesado (geocoding ~14s + PDF) pra nao parecer travado.
    if notify is not None:
        notify(_GERANDO)
    local = resolver_local(t, settings)
    if local is None:
        return [_msg("❌ Nao consegui localizar. Tente link do Maps, `lat,lng` ou endereco+CEP.", _KB_MENU)]
    lat, lng, nome = local
    # rotulo: nome do endereco/estabelecimento na capa do PDF (no lugar da coordenada).
    payload = {"lat": lat, "lng": lng, "rotulo": nome}
    pdf = consultar_pdf(payload, settings)
    if pdf is None:
        return [_msg(f"⚠️ {_erro_api(payload, settings)}", _KB_MENU)]
    # Rastreio: quem pediu o estudo (login) + onde.
    print(f"[ESTUDO] login={s.get('login', '?')} chat={chat_id} coord={lat},{lng} local={nome}")
    return [
        _msg(f"📄 Relatorio de *{nome}*\n_Solicitado por {s.get('login', '?')}_"),
        {"pdf": pdf},
        _msg("Pronto! Envie outra localizacao quando quiser.", _KB_MENU),
    ]


# --- loop de long-polling ---------------------------------------------------


def _tg(token: str, method: str, **params: Any) -> dict:
    resp = _session.post(_TELEGRAM.format(token=token, method=method), json=params, timeout=70)
    resp.raise_for_status()
    return resp.json()


def _enviar(token: str, chat_id: int, acao: dict) -> None:
    if "pdf" in acao:
        _session.post(
            _TELEGRAM.format(token=token, method="sendDocument"),
            data={"chat_id": chat_id},
            files={"document": ("relatorio_pontual_censitario.pdf", acao["pdf"], "application/pdf")},
            timeout=120,
        )
        return

    # IMPORTANTE: so incluir reply_markup quando ha teclado. Mandar
    # `reply_markup: null` faz o Telegram recusar ("object expected as reply markup").
    base = {"chat_id": chat_id, "text": acao["text"]}
    if acao.get("keyboard"):
        base["reply_markup"] = {"keyboard": acao["keyboard"], "resize_keyboard": True}
    url = _TELEGRAM.format(token=token, method="sendMessage")

    # Tenta com Markdown; se o Telegram recusar (ex.: entidades mal formadas),
    # REENVIA em texto puro — garante que a resposta sempre chega.
    resp = _session.post(url, json={**base, "parse_mode": "Markdown"}, timeout=70)
    if not resp.ok:
        print(f"[WARN] Markdown recusado ({resp.status_code}): "
              f"{resp.json().get('description', '')[:120]} -> reenviando texto puro", flush=True)
        resp2 = _session.post(url, json=base, timeout=70)
        if not resp2.ok:
            print(f"[ERRO] texto puro tambem falhou ({resp2.status_code}): "
                  f"{resp2.json().get('description', '')[:120]}", flush=True)


def _configurar_menu_comandos(token: str) -> None:
    """Define o menu de comandos do bot (substitui qualquer lista antiga, ex.: /analisar)."""
    comandos = [
        {"command": "start", "description": "Iniciar / pedir acesso"},
        {"command": "relatorio", "description": "Gerar um relatorio"},
        {"command": "ajuda", "description": "Sobre o bot"},
    ]
    try:
        # Limpa primeiro (remove comandos antigos como /analisar), depois define os atuais.
        _tg(token, "deleteMyCommands")
        _tg(token, "setMyCommands", commands=comandos)
        print("Menu de comandos atualizado (sem /analisar).", flush=True)
    except requests.RequestException as exc:
        print(f"[WARN] nao consegui atualizar o menu de comandos: {exc}", flush=True)


def main() -> None:
    settings = get_settings()
    token = settings.telegram_token
    if not token:
        raise SystemExit("Defina API_TELEGRAM_TOKEN (env ou .env) com o token do @BotFather.")

    _configurar_menu_comandos(token)
    _carregar_sessoes(settings)  # restaura quem ja estava logado antes do restart
    print(f"Bot no ar. API em {settings.api_base_url}. Ctrl+C para sair.")
    offset: int | None = None
    while True:
        try:
            updates = _tg(token, "getUpdates", offset=offset, timeout=30)
        except requests.RequestException as exc:
            print(f"getUpdates falhou: {exc}")
            continue
        for upd in updates.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message") or upd.get("edited_message")
            if not msg or "text" not in msg:
                continue
            chat_id = msg["chat"]["id"]
            try:
                # Feedback imediato enquanto processa (PDF leva alguns segundos).
                try:
                    _tg(token, "sendChatAction", chat_id=chat_id, action="typing")
                except requests.RequestException:
                    pass

                # notify: manda "⏳ Gerando..." na hora que `processar` entra no
                # caminho de localizacao->PDF, antes do geocoding/PDF (trabalho lento).
                def _notify(texto_aviso: str, _cid: int = chat_id) -> None:
                    try:
                        _tg(token, "sendChatAction", chat_id=_cid, action="upload_document")
                    except requests.RequestException:
                        pass
                    try:
                        _enviar(token, _cid, _msg(texto_aviso))
                    except Exception:
                        pass

                for acao in processar(chat_id, msg["text"], settings, notify=_notify):
                    _enviar(token, chat_id, acao)
                _salvar_sessoes(settings)  # persiste login/autorizacao apos cada msg
            except Exception as exc:  # nunca deixa um erro derrubar o loop nem sumir calado
                print(f"[ERRO] ao responder {chat_id}: {type(exc).__name__}: {exc}", flush=True)
                try:
                    _session.post(
                        _TELEGRAM.format(token=token, method="sendMessage"),
                        json={"chat_id": chat_id, "text": "⚠️ Ocorreu um erro ao processar. Tente novamente."},
                        timeout=30,
                    )
                except requests.RequestException:
                    pass


if __name__ == "__main__":
    main()
