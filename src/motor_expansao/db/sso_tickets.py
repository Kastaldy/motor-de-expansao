"""Ticket de uso unico do SSO entre hosts (DEC-083, follow-up Opcao B da DEC-081).

O QUE ESTE MODULO E', E POR QUE ELE EXISTE
------------------------------------------
A DEC-081 deixou os tres hosts (apex + BR + AR) com login proprio, mas o cookie de sessao e'
`__Host-` POR HOST (Opcao F): logar no apex nao loga na BR. Um cookie de DOMINIO foi
REVERTIDO por reabrir fixacao de sessao. O SSO seguro ficou como follow-up: um TICKET de uso
unico entre hosts (Opcao B), e e' isso que este modulo sustenta.

E' o mesmo padrao do `authorization code` do OAuth: o host de ORIGEM (onde a pessoa ja' tem
sessao -- o apex) EMITE um segredo opaco, efemero e de uso unico, que viaja na URL do redirect;
o host de DESTINO o CONSOME e, so' entao, abre uma sessao `__Host-` nova e local (via
`sessoes.abrir`). O ticket NUNCA e' cookie -- entao a Opcao F fica intacta, sem cookie de
dominio plantavel por irmao.

E' a camada de banco do ticket, e NADA MAIS: nao ha' rota nem cookie aqui. Quem chama mora em
`web/server/app.py`: `POST /api/sso/ticket` (emissao, exige sessao) e `GET /api/sso/entrar`
(consumo, publica -- o ticket E' a credencial). O gate de PAIS (DEC-081) e' do chamador: a
emissao confere `pais in paises_da_pessoa`, e a sessao que o consumo abre e' barrada pelo
`_portao_de_sessao` como qualquer outra (o pais do processo tem de estar entre os da pessoa).

POR QUE USO UNICO + TTL CURTO (e nao JWT assinado)
--------------------------------------------------
Um segredo que viaja na URL vaza em log de acesso e em `Referer`. O que o torna seguro e'
exatamente o que o OAuth code faz: ele so' serve UMA vez e por POUCOS segundos. Um JWT
assinado teria validade, mas nao uso unico -- e o ponto do ticket e' NAO ser reutilizavel.
Uso unico exige ESTADO no servidor (uma linha que vira "consumida"), a mesma razao pela qual
a D30 escolheu tabela para a sessao. O consumo e' atomico (`UPDATE ... WHERE consumido_em
IS NULL RETURNING`): dois consumos simultaneos -- replay --, o UPDATE casa a linha UMA vez.

O TOKEN NUNCA ENTRA NO BANCO
----------------------------
Guarda-se o SHA-256 (as mesmas `novo_token`/`hash_do_token` de `sessoes.py`, nao uma segunda
redacao da regra). Token aleatorio de alta entropia -> hash rapido e' o certo; Argon2 por
consumo custaria CPU sem comprar defesa.

CARIMBO DE AUTOR (§3.7)
-----------------------
`emitir` roda numa transacao carimbada com o EMISSOR (ele tem sessao, e' conhecido). `consumir`
e' PRE-AUTENTICACAO -- como `/api/login`, a identidade esta' sendo ESTABELECIDA, e so' se sabe
quem e' DEPOIS do `RETURNING`. Por isso o consumo e' acao de SISTEMA (`id_usuario=None`); logo
em seguida `sessoes.abrir(id_usuario=<o do RETURNING>)` carimba a SESSAO com a pessoa de fato.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .postgres import conexao, transacao
from .sessoes import hash_do_token, novo_token  # MESMA regra de token -- nao duplicar (DEC-044)

_LOG = logging.getLogger("motor.db.sso_tickets")

#: TTL do ticket, em segundos. CURTO de proposito (padrao authorization-code): a janela em que
#: um ticket vazado em log/Referer ainda serviria -- e so' UMA vez. Constante de codigo, nao
#: coluna: a janela e' decisao do EMISSOR; a tabela guarda o `expira_em_ticket` ja' calculado.
TTL_TICKET_S = 60


# --- SQL, em constantes nomeadas (mesma politica de sessoes.py/eventos.py) ----------------

SQL_EMITIR = """
INSERT INTO sso_tickets (id_usuario, token_hash_ticket, pais_destino,
                         expira_em_ticket, id_sessao_origem)
VALUES (%s, %s, %s, now() + make_interval(secs => %s), %s)
RETURNING id_ticket, expira_em_ticket
"""

# USO UNICO + nao-expirado, ATOMICO. O `consumido_em_ticket IS NULL` no WHERE com RETURNING e'
# o que da' o uso unico SEM corrida (molde de `sessoes.SQL_TOCAR`): o UPDATE casa a linha uma
# vez e o replay simultaneo volta vazio. A trava de tempo entra no MESMO WHERE pela mesma
# razao -- decidir no Python abriria janela entre o SELECT e o UPDATE.
SQL_CONSUMIR = """
UPDATE sso_tickets SET consumido_em_ticket = now()
WHERE token_hash_ticket = %s
  AND consumido_em_ticket IS NULL
  AND expira_em_ticket > now()
RETURNING id_usuario, pais_destino
"""

# LER sem consumir: o passo de CONFIRMACAO (DEC-083) mostra "entrar como <login>?" ANTES de
# gastar o ticket -- a vitima de um login-CSRF ve de quem e' a conta e barra. So' leitura
# (`conexao`), nunca marca `consumido_em_ticket`; o gasto e' sempre no `consumir` atomico do
# POST. Junta `usuarios` so' pelo `login_usuario` (exibicao), nunca concede acesso.
SQL_ESPIAR = """
SELECT u.login_usuario, s.pais_destino
FROM sso_tickets s
JOIN usuarios u ON u.id_usuario = s.id_usuario
WHERE s.token_hash_ticket = %s
  AND s.consumido_em_ticket IS NULL
  AND s.expira_em_ticket > now()
"""

# EXPURGO dos tickets velhos (consumidos/expirados) = follow-up da DEC-083, AINDA NAO ligado:
# a tabela cresce 1 linha por handoff e, com TTL de 60s + uso unico, o crescimento e' desprezivel
# a curto prazo. O expurgo sera' um DELETE pelo DONO do schema (o `app` so' tem SELECT/INSERT/
# UPDATE), no CLI `db expurgar`, junto do expurgo de origem das sessoes -- SQL e cadencia na DEC-083.


@dataclass(frozen=True)
class TicketEmitido:
    """O que o emissor precisa para montar o redirect. O `token` NAO se registra em log."""

    token: str
    id_ticket: int
    expira_em: object


@dataclass(frozen=True)
class TicketConsumido:
    """Quem e' o dono do ticket e para qual host (pais) ele valia."""

    id_usuario: int
    pais_destino: str


@dataclass(frozen=True)
class TicketEspiado:
    """O que a pagina de CONFIRMACAO precisa mostrar, SEM gastar o ticket: de quem e' a
    conta (`login`) e para qual host (`pais_destino`)."""

    login: str
    pais_destino: str


def emitir(
    *, id_usuario: int, pais_destino: str, id_sessao_origem: int | None = None
) -> TicketEmitido:
    """Cunha o ticket e devolve o token EM CLARO -- uma unica vez (so' aqui e na URL do redirect).

    `pais_destino` prende o ticket a UM host: o consumo noutro pais e' negado. Quem chama
    (o endpoint de emissao) JA' conferiu que `pais_destino` esta' entre os paises da pessoa
    (gate da DEC-081) -- este modulo nao reabre essa decisao, so' grava o que foi autorizado.
    """
    token = novo_token()
    with transacao(id_usuario=id_usuario) as con:
        linha = con.execute(
            SQL_EMITIR,
            (id_usuario, hash_do_token(token), pais_destino, TTL_TICKET_S, id_sessao_origem),
        ).fetchone()
    if linha is None:  # pragma: no cover - defesa de invariante
        raise RuntimeError("INSERT em sso_tickets nao devolveu RETURNING -- ticket sem id")
    return TicketEmitido(token=token, id_ticket=linha[0], expira_em=linha[1])


def consumir(token: str) -> TicketConsumido | None:
    """Gasta o ticket de forma ATOMICA. `None` = inexistente, ja' consumido ou expirado.

    Os tres motivos de negar caem no MESMO `None` de proposito (molde de `sessoes.validar`): o
    chamador responde igual nos tres (cai no login do host) e distinguir aqui so' contaria ao
    visitante por que falhou. Acao de SISTEMA (`id_usuario=None`): e' pre-autenticacao -- a
    identidade sai DAQUI, pelo `RETURNING`, e e' `sessoes.abrir` que carimba a sessao com ela.
    """
    if not token:
        return None
    with transacao(id_usuario=None) as con:
        linha = con.execute(SQL_CONSUMIR, (hash_do_token(token),)).fetchone()
    if linha is None:
        return None
    return TicketConsumido(id_usuario=linha[0], pais_destino=linha[1])


def espiar(token: str) -> TicketEspiado | None:
    """LE o ticket SEM consumir, para a pagina de confirmacao (DEC-083). `None` = invalido,
    ja' consumido ou expirado. Nao marca nada; o gasto e' sempre no `consumir` do POST."""
    if not token:
        return None
    with conexao() as con:
        linha = con.execute(SQL_ESPIAR, (hash_do_token(token),)).fetchone()
    if linha is None:
        return None
    return TicketEspiado(login=linha[0], pais_destino=linha[1])

