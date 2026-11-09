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
from datetime import datetime

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


# --- Trava de tentativas por (CONTA, IP) -- 09/11/2026 ------------------------------------
#
# O PROBLEMA QUE ELA FECHA. A trava do banco (`eventos.contar_recusas_recentes`) conta por CONTA:
# cinco senhas erradas em 15 min barravam a conta para TODO MUNDO, inclusive para a dona dela com
# a senha certa. Quem soubesse um login mantinha a dona dele sem entrar, mandando cinco
# tentativas a cada janela. A janela movel fazia a tranca se soltar sozinha, mas nao impedia
# de renova-la.
#
# A REGRA AGORA. As cinco recusas contam por (conta, IP de origem): quem erra de um IP tranca so'
# AQUELE IP para AQUELA conta, e a dona entra do dela. O teto por conta do banco continua, mais
# alto (`sessoes.MAX_TENTATIVAS_CONTA`), como rede contra o ataque espalhado por muitos IPs.
#
# EM MEMORIA, e nao no banco, por causa do P15: o IP nao e' gravado em `eventos`, e esta trava
# nao abre essa porta. O custo, declarado como o do rate-limit acima: reinicia com o processo e
# vale por worker. Reiniciar SOLTA as travas por IP -- e e' o teto da conta, no banco, que segue
# segurando o volume nesse intervalo.

#: Teto de pares (conta, IP) rastreados; poda o menos recente, como `_MAX_IPS`.
_MAX_PARES = 20_000

_lock_par = threading.Lock()
_recusas_par: OrderedDict[tuple[int, str], list[float]] = OrderedDict()


def _vivas(marcas: list[float], *, agora: float, janela_s: float, piso: float | None) -> list[float]:
    """As recusas que ainda contam: dentro da janela e depois do piso (redefinicao)."""
    corte = agora - janela_s
    if piso is not None and piso > corte:
        corte = piso
    return [m for m in marcas if m > corte]


def reservar_tentativa_par(
    id_usuario: int,
    ip: str,
    *,
    maximo: int,
    janela_s: float,
    redefinida_em: datetime | None = None,
    agora: float | None = None,
) -> bool:
    """Checa e RESERVA a tentativa no mesmo lock. `True` = o par ja' estava trancado.

    E' a UNICA porta de entrada da trava por par: a checagem e a contagem sao o mesmo gesto.
    `redefinida_em` e' o mesmo piso que o banco usa -- o admin que redefine a senha confirmou a
    identidade por fora, e as recusas de ANTES deixam de contar em todas as origens. O relogio
    e' o de PAREDE (`time.time`), porque o piso vem do banco como data.

    A revisao do 8ebfa11c mediu a corrida de ler primeiro e so' contar DEPOIS do
    Argon2: com 4 recusas, 6 requisicoes simultaneas (o teto do semaforo) liam 4 < 5 e eram
    todas avaliadas -- 10 tentativas por janela em vez de 5. Aqui a marca entra ANTES da
    verificacao, atomica com a checagem. Quem acerta a senha chama `limpar_par`; quem nem
    chega a ser avaliado (semaforo cheio) chama `desfazer_reserva_par`. A tentativa barrada
    NAO reserva nada, pela regra de sempre: senao a tranca nunca drenaria.
    """
    t = time.time() if agora is None else agora
    piso = redefinida_em.timestamp() if redefinida_em is not None else None
    chave = (id_usuario, ip)
    with _lock_par:
        marcas = _recusas_par.get(chave, [])
        marcas = _vivas(marcas, agora=t, janela_s=janela_s, piso=piso)
        if len(marcas) >= maximo:
            _recusas_par[chave] = marcas
            return True
        marcas.append(t)
        _recusas_par[chave] = marcas
        _recusas_par.move_to_end(chave)
        while len(_recusas_par) > _MAX_PARES:
            _recusas_par.popitem(last=False)
        return False


def desfazer_reserva_par(id_usuario: int, ip: str) -> None:
    """Devolve a reserva de uma tentativa que NAO foi avaliada (semaforo cheio, 503)."""
    with _lock_par:
        marcas = _recusas_par.get((id_usuario, ip))
        if marcas:
            marcas.pop()


def limpar_par(id_usuario: int, ip: str) -> None:
    """O acerto zera o par, como no banco: quem provou saber a senha nao fica com recusa velha.

    So' o PAR do acerto -- e nao a conta inteira -- porque o acerto da dona num IP nao pode
    destrancar o IP de quem esta' tentando adivinhar a senha dela em outro.
    """
    with _lock_par:
        _recusas_par.pop((id_usuario, ip), None)


def _resetar_para_teste() -> None:
    """Zera o estado. SO' para teste -- a producao nunca chama."""
    with _lock:
        _marcas.clear()
    with _lock_par:
        _recusas_par.clear()
