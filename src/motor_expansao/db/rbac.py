"""Identidade e permissao a partir do banco — o que substitui o `acesso_abas.json`.

Duas perguntas, uma consulta
----------------------------
Quem esta autenticado (`Remote-User`, o username do Authelia) precisa virar duas coisas: o
`id_usuario` que o `app.id_usuario` do D19 carimba em toda escrita, e o conjunto de chaves de
permissao que decide o que a pessoa alcanca. As duas saem de uma consulta so' -- separa-las
custaria duas idas ao banco por requisicao para responder sobre a mesma pessoa.

Deny-by-default, como hoje
--------------------------
`Remote-User` que nao existe em `usuarios` (ou existe e esta inativo) nao recebe permissao nenhuma,
e NAO e' criado na hora. E' o mesmo comportamento do `acesso_abas.json`: quem nao esta no mapa nao
tem aba nenhuma -- o motor nunca teve auto-cadastro, e passar a ter aqui seria transformar
"autenticado no Authelia" em "autorizado no piloto", que sao coisas diferentes.

Sem cache, de proposito
-----------------------
Uma consulta indexada por requisicao. O piloto ja' le particoes Parquet de centenas de MB por UF;
um `SELECT` por indice unico nao e' o gargalo. E cache de autorizacao tem um custo que este sistema
nao deveria pagar: revogar acesso deixaria de valer na hora. Hoje o JSON e' relido por mtime, ou
seja, mudanca vale na requisicao seguinte -- consultar sempre e' MAIS rigoroso que isso, nao menos.

Quem aplica a politica de falha nao e' este modulo
--------------------------------------------------
Banco fora do ar levanta `BancoIndisponivel` daqui. A decisao entre negar tudo, negar so' as
capacidades sensiveis ou liberar em dev e' do chamador -- e' la' que a regra do `acesso.py` vive
(fail-closed nas sensiveis em producao, fail-open em dev), e ela nao deve ser reescrita aqui.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from .postgres import conexao

_LOG = logging.getLogger("motor.db.rbac")

#: Identidade assumida em DESENVOLVIMENTO, quando nao ha Authelia na frente. Ver `_dev_ativo`:
#: ela e' ignorada em producao e nunca sobrescreve um header real.
ENV_DEV_USUARIO = "MOTOR_DEV_USUARIO"

#: Override explicito do sinal de producao (mesmo formato do `MOTOR_ACESSO_FAIL_CLOSED`).
ENV_DEV_IDENTIDADE = "MOTOR_DEV_IDENTIDADE"

#: Sinal de PRODUCAO, herdado do `acesso.py`: o volume `:rw` do cadastro so' existe no compose.
#: Reusar o mesmo sinal evita um segundo conceito de "estou em producao" que possa divergir.
ENV_SINAL_PRODUCAO = "MOTOR_CADASTRO_DIR"

# `ativo` no WHERE nao e' redundante com o indice unico parcial (D9/D23): o indice garante que
# nao ha DOIS logins iguais entre ativos, mas um login pode existir numa linha INATIVA. Sem o
# filtro, alguem desativado voltaria a ser resolvido -- e o piloto ja' barra login de inativo.
SQL_IDENTIDADE = """
SELECT u.id_usuario, p.nome_perfil, pe.chave
FROM usuarios u
JOIN perfis p ON p.id_perfil = u.id_perfil
LEFT JOIN perfil_permissoes pp ON pp.id_perfil = u.id_perfil
LEFT JOIN permissoes pe ON pe.id_permissao = pp.id_permissao
WHERE u.login_usuario = %s AND u.ativo
"""


@dataclass(frozen=True)
class Identidade:
    """Quem e', e o que pode. `id_usuario` alimenta o `app.id_usuario` do D19."""

    id_usuario: int
    login: str
    perfil: str
    permissoes: frozenset[str]

    def pode(self, chave: str) -> bool:
        return chave in self.permissoes


def _dev_ativo() -> bool:
    """A identidade de desenvolvimento vale aqui?

    Duas travas, porque um modo que deixa alguem "ser qualquer usuario" e' exatamente o tipo de
    porta dos fundos que vaza para producao: (1) override explicito, se alguem precisar desligar
    em dev; (2) na ausencia dele, o sinal de producao MANDA -- havendo `MOTOR_CADASTRO_DIR`, a
    env de dev e' ignorada, aconteca o que acontecer.
    """
    override = os.environ.get(ENV_DEV_IDENTIDADE)
    if override is not None:
        return override.strip().lower() in ("1", "true", "sim", "yes")
    return not os.environ.get(ENV_SINAL_PRODUCAO)


def login_efetivo(remote_user: str | None) -> str | None:
    """O login a usar: o header quando existe; em dev, a env como ultimo recurso.

    A ordem importa e nao pode inverter. O header SEMPRE vence: em producao ele e' o unico
    caminho, e mesmo em dev, se ele veio, e' ele que vale. A env so' preenche o vazio de quando
    nao ha Caddy nem Authelia na frente -- que e' o estado de quem roda o backend na propria
    maquina e, sem isto, nao consegue exercitar autorizacao NENHUMA.
    """
    if isinstance(remote_user, str) and remote_user.strip():
        return remote_user.strip()
    if not _dev_ativo():
        return None
    dev = os.environ.get(ENV_DEV_USUARIO, "").strip()
    if dev:
        _LOG.warning("identidade de DESENVOLVIMENTO em uso: %s (sem Remote-User)", dev)
        return dev
    return None


def identidade(remote_user: str | None) -> Identidade | None:
    """`None` = nao autorizado. Levanta `BancoIndisponivel` se o banco estiver fora."""
    login = login_efetivo(remote_user)
    if login is None:
        return None

    with conexao() as con:
        linhas = con.execute(SQL_IDENTIDADE, (login,)).fetchall()

    if not linhas:
        return None  # nao existe, ou existe inativo -- os dois casos negam

    id_usuario = linhas[0][0]
    perfil = linhas[0][1]
    # `chave` vem NULL quando o perfil nao tem permissao nenhuma (LEFT JOIN): a pessoa existe e
    # nao pode nada. E' diferente de nao existir, e o chamador precisa poder distinguir os dois.
    chaves = frozenset(chave for _, _, chave in linhas if chave is not None)
    return Identidade(id_usuario=id_usuario, login=login, perfil=perfil, permissoes=chaves)
