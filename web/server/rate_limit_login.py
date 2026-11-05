"""Rate-limit por IP de `/api/login` (solidificacao do pentest, item 2 do achado #1).

Complementa o `_SEM_LOGIN` do `app.py`, e os dois eixos sao diferentes de proposito:
  * `_SEM_LOGIN` limita o CUSTO -- quantas verificacoes Argon2 (64 MiB cada) rodam ao
    MESMO TEMPO; cheio, devolve 503 por carga.
  * este modulo limita a TAXA por ORIGEM -- quantas tentativas um mesmo IP faz numa janela;
    estourou, devolve 429 ANTES do Argon2. E' o que corta varredura de login e flood de um
    unico cliente, que o semaforo de custo sozinho nao distingue de trafego legitimo.

CHAVE = o IP que a BORDA observou, nunca o que o cliente DIZ. O Caddy anexa o IP real do
peer ao FIM do `X-Forwarded-For`; lemos o ULTIMO elemento. Ler o PRIMEIRO (que o cliente
dita) deixaria um `X-Forwarded-For` forjado criar um balde novo a cada requisicao e evadir
o teto -- exatamente o furo #7 do pentest (a borda hoje nao tem `trusted_proxies` e repassa
o XFF de entrada). Ler o ultimo e' robusto a isso SEM depender da config do Caddy: anexando
ou substituindo, o ultimo elemento e' sempre o peer que o Caddy viu.

EM MEMORIA e por WORKER: reinicia com o processo e, se um dia o `web` subir com `--workers`,
o teto efetivo multiplica pelo numero de workers -- aceito, e fica declarado. O dict e'
limitado (`_MAX_IPS`) podando o IP menos-recente, para uma enxurrada de IPs distintos nao
crescer a memoria sem teto.
"""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict

#: Teto de tentativas por IP na janela. 20/60s e' folgado para humano e corta flood/varredura.
MAX_TENTATIVAS = max(1, int(os.environ.get("MOTOR_LOGIN_RATE_MAX", "20")))
#: Largura da janela deslizante, em segundos.
JANELA_S = max(1, int(os.environ.get("MOTOR_LOGIN_RATE_JANELA_S", "60")))
#: Teto de IPs rastreados (poda o menos-recente). Barra crescimento por IPs distintos.
_MAX_IPS = 10_000

_lock = threading.Lock()
_marcas: OrderedDict[str, list[float]] = OrderedDict()


def ip_observado_pelo_edge(xff: str | None, fallback: str | None) -> str:
    """O IP que a borda viu: ULTIMO elemento do `X-Forwarded-For`, ou o fallback.

    Ver o docstring do modulo: o ultimo elemento e' o que o Caddy anexa (o peer real),
    imune ao prefixo que o cliente injeta. `fallback` e' o `request.client.host` (em
    producao, o proprio Caddy -- igual para todos, por isso so' serve de ultimo recurso).
    """
    if xff:
        partes = [p.strip() for p in xff.split(",") if p.strip()]
        if partes:
            return partes[-1]
    return fallback or "desconhecido"


def sob_limite(ip: str, *, agora: float | None = None) -> bool:
    """`True` se `ip` JA' estourou o teto na janela; registra a tentativa quando NAO estourou.

    Nao registrar quando ja' estourou e' deliberado (mesma logica da trava por conta): a
    tentativa recusada NAO prolonga a janela, senao o bloqueio nunca drenaria. `agora` e'
    injetavel para teste; por padrao usa `time.monotonic()` (imune a acerto de relogio).
    Thread-safe: `/api/login` e' rota sync e roda no threadpool.
    """
    t = time.monotonic() if agora is None else agora
    corte = t - JANELA_S
    with _lock:
        marcas = _marcas.get(ip)
        if marcas is None:
            marcas = []
            _marcas[ip] = marcas
        marcas[:] = [m for m in marcas if m > corte]
        estourou = len(marcas) >= MAX_TENTATIVAS
        if not estourou:
            marcas.append(t)
        _marcas.move_to_end(ip)
        while len(_marcas) > _MAX_IPS:
            _marcas.popitem(last=False)
        return estourou


def _resetar_para_teste() -> None:
    """Zera o estado. SO' para teste -- a producao nunca chama."""
    with _lock:
        _marcas.clear()
