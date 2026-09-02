"""Administracao de usuarios: quem existe, com que perfil, e quem mudou o que.

O que esta camada resolve
-------------------------
Antes do banco, mudar o acesso de alguem era editar o `acesso_abas.json` no volume `:rw` -- sem
rebuild, sem deploy. Com o RBAC no banco, a mesma mudanca vira `UPDATE` manual na VPS. Isso e' uma
REGRESSAO de operabilidade, e e' o que este modulo existe para desfazer.

Por que o SQL mora aqui, e nao no `app.py`
------------------------------------------
O CI nao tem Postgres (decisao de 25/08) e quem executa contra banco real e' o Vinicius. Isso impoe
uma consequencia de arquitetura: o SQL precisa ser LOCALIZAVEL -- em arquivos ou num modulo de
queries nomeadas, nunca interpolado no meio da logica de rota. Sem isso, nem o gate de sintaxe
offline (`pglast`) alcanca tudo, nem ha o que revisar antes de rodar.

Uma unidade de trabalho por acao
--------------------------------
Toda escrita daqui faz DUAS coisas na MESMA transacao: muda a linha de `usuarios` e grava o evento
correspondente. Se as duas nao forem atomicas, o sistema fica com estados que ninguem consegue
explicar depois -- perfil trocado sem registro de quem trocou, ou registro de uma troca que nao
aconteceu. O `transacao(id_usuario=...)` carimba o autor para as triggers do D19 (§8.1) e o mesmo
autor vai no `id_usuario` do evento.

As duas pessoas de cada linha
-----------------------------
Em `eventos`, `id_usuario` e' QUEM FEZ e `entidade_id` e' QUEM SOFREU. E' para isso que a D24 pos
`usuario` no `CHECK` de `entidade`. Confundir as duas produz uma trilha que parece certa e responde
errado -- por isso os parametros aqui se chamam `autor` e `id_alvo`, e nunca so' "usuario".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .postgres import conexao, transacao

#: Vocabulario de `tipo` do `docs/eventos_contrato.md` §2.7. Fora desta lista e' defeito.
EVENTO_PERFIL_ALTERADO = "usuario.perfil_alterado"
EVENTO_DESATIVADO = "usuario.desativado"
EVENTO_REATIVADO = "usuario.reativado"

#: Valor de `entidade` para os eventos daqui (D24).
ENTIDADE_USUARIO = "usuario"


class UsuarioDesconhecido(LookupError):
    """`id_usuario` que nao existe. 404 na rota -- nunca criar na hora."""


class PerfilDesconhecido(LookupError):
    """`nome_perfil` fora dos que o seed criou."""


class AlvoEhOAutor(PermissionError):
    """Tentativa de mudar o proprio acesso. Ver `_recusar_auto_alvo`."""


# `login_usuario` e' a chave que casa com o `Remote-User` do Authelia (D23). Vem junto porque e' o
# que a tela mostra e o que a trilha da DEC-027 grava -- sem ele, cruzar as duas exige adivinhacao.
SQL_LISTAR = """
SELECT u.id_usuario, u.login_usuario, u.nome_usuario, u.email,
       p.nome_perfil, u.ativo, u.criado_em_usuario, u.atualizado_em_usuario
FROM usuarios u
JOIN perfis p ON p.id_perfil = u.id_perfil
ORDER BY u.ativo DESC, u.login_usuario
"""

#: A tela precisa das opcoes do seletor. `descricao_perfil` vira rotulo, e por isso ela e' medida
#: por encoding na verificacao -- ver a nota da 012 sobre duplo-encoding.
SQL_PERFIS = """
SELECT p.nome_perfil, p.descricao_perfil, count(pp.id_permissao) AS capacidades
FROM perfis p
LEFT JOIN perfil_permissoes pp ON pp.id_perfil = p.id_perfil
GROUP BY p.nome_perfil, p.descricao_perfil
ORDER BY count(pp.id_permissao), p.nome_perfil
"""

# `FOR UPDATE` trava a linha ate' o fim da transacao. Sem ele, dois admins mexendo na mesma pessoa
# ao mesmo tempo produzem dois eventos com o MESMO `de` -- a trilha diria que o perfil saiu de
# `expansao` duas vezes, e o estado final seria de quem escreveu por ultimo, sem registro disso.
SQL_ESTADO_ATUAL = """
SELECT u.id_usuario, u.login_usuario, p.nome_perfil, u.ativo
FROM usuarios u
JOIN perfis p ON p.id_perfil = u.id_perfil
WHERE u.id_usuario = %s
FOR UPDATE OF u
"""

SQL_ID_DO_PERFIL = "SELECT id_perfil FROM perfis WHERE nome_perfil = %s"

SQL_TROCAR_PERFIL = """
UPDATE usuarios SET id_perfil = %s WHERE id_usuario = %s
"""

SQL_DEFINIR_ATIVO = """
UPDATE usuarios SET ativo = %s WHERE id_usuario = %s
"""

# `entidade`/`entidade_id` = quem SOFREU (D24); `id_usuario` = quem FEZ. Sem PII em `metadados`
# (convencoes §5): nunca login nem e-mail do alvo -- o id basta, e quem le resolve em `usuarios`.
SQL_REGISTRAR_EVENTO = """
INSERT INTO eventos (id_usuario, tipo, entidade, entidade_id, metadados)
VALUES (%s, %s, %s, %s, %s)
"""


@dataclass(frozen=True)
class UsuarioAdmin:
    """Uma linha da tela de administracao."""

    id_usuario: int
    login: str
    nome: str
    email: str
    perfil: str
    ativo: bool

    def como_json(self) -> dict[str, Any]:
        return {
            "id_usuario": self.id_usuario,
            "login": self.login,
            "nome": self.nome,
            "email": self.email,
            "perfil": self.perfil,
            "ativo": self.ativo,
        }


def listar() -> list[UsuarioAdmin]:
    """Todos os usuarios, ativos primeiro. Inclui INATIVOS de proposito.

    Esconder quem foi desativado tornaria a reativacao impossivel pela tela, e e' justamente o
    caso de quem volta de licenca ou muda de area e volta.
    """
    with conexao() as con:
        linhas = con.execute(SQL_LISTAR).fetchall()
    return [
        UsuarioAdmin(
            id_usuario=linha[0],
            login=str(linha[1]),
            nome=str(linha[2]),
            email=str(linha[3]),
            perfil=str(linha[4]),
            ativo=bool(linha[5]),
        )
        for linha in linhas
    ]


def perfis() -> list[dict[str, Any]]:
    """Os perfis do seed, do menor para o maior. A ordem e' a hierarquia da D22."""
    with conexao() as con:
        linhas = con.execute(SQL_PERFIS).fetchall()
    return [
        {"perfil": str(nome), "descricao": str(descricao), "capacidades": int(qtd)}
        for nome, descricao, qtd in linhas
    ]


def _recusar_auto_alvo(id_alvo: int, autor: int) -> None:
    """Ninguem muda o proprio acesso por esta tela.

    Nao e' paternalismo: sao dois modos de falha concretos. Um admin que se rebaixa por engano
    perde a tela que usaria para desfazer -- e o conserto vira `UPDATE` manual na VPS, que e'
    exatamente o que esta tela existe para evitar. E auto-desativacao derruba a propria sessao no
    meio da requisicao seguinte, sem ninguem para reverter se ele for o unico admin.
    """
    if id_alvo == autor:
        raise AlvoEhOAutor(
            "Você não pode alterar o seu próprio acesso por aqui. Peça a outra pessoa do perfil "
            "Growth, ou faça pelo banco se for o único."
        )


def _estado_atual(con: Any, id_alvo: int) -> tuple[str, bool]:
    """Perfil e status de agora, com a linha travada ate' o fim da transacao."""
    linha = con.execute(SQL_ESTADO_ATUAL, (id_alvo,)).fetchone()
    if linha is None:
        raise UsuarioDesconhecido(f"usuário {id_alvo} não existe")
    return str(linha[2]), bool(linha[3])


def _registrar(con: Any, *, autor: int, tipo: str, id_alvo: int, metadados: Any) -> None:
    """Grava o evento na MESMA transacao da mudanca. Ver o cabecalho do modulo."""
    from psycopg.types.json import Jsonb  # import tardio: so' quem escreve paga

    con.execute(
        SQL_REGISTRAR_EVENTO,
        (autor, tipo, ENTIDADE_USUARIO, id_alvo, Jsonb(metadados) if metadados else None),
    )


def alterar_perfil(id_alvo: int, novo_perfil: str, *, autor: int) -> dict[str, Any]:
    """Troca o perfil e registra `usuario.perfil_alterado`. Devolve o de-para aplicado."""
    _recusar_auto_alvo(id_alvo, autor)

    with transacao(id_usuario=autor) as con:
        perfil_antes, _ = _estado_atual(con, id_alvo)

        linha = con.execute(SQL_ID_DO_PERFIL, (novo_perfil,)).fetchone()
        if linha is None:
            raise PerfilDesconhecido(f"perfil '{novo_perfil}' não existe")

        # Nada a fazer e' sucesso, nao erro -- mas NAO gera evento: a trilha registra mudanca, e
        # uma linha `de: growth, para: growth` polui a auditoria com ruido que parece sinal.
        if perfil_antes == novo_perfil:
            return {"id_usuario": id_alvo, "de": perfil_antes, "para": novo_perfil, "mudou": False}

        con.execute(SQL_TROCAR_PERFIL, (linha[0], id_alvo))
        _registrar(
            con,
            autor=autor,
            tipo=EVENTO_PERFIL_ALTERADO,
            id_alvo=id_alvo,
            metadados={"de": perfil_antes, "para": novo_perfil},
        )

    return {"id_usuario": id_alvo, "de": perfil_antes, "para": novo_perfil, "mudou": True}


def definir_ativo(id_alvo: int, ativo: bool, *, autor: int) -> dict[str, Any]:
    """Desativa ou reativa, e registra o evento correspondente.

    Desativar e' o caminho de quem sai da empresa, e ele e' SOFT (D9/D23): a linha fica, o login
    sai do indice unico parcial e volta a ser reutilizavel, e a trilha historica da pessoa
    continua existindo. Nunca apagar -- `eventos.id_usuario` e' `ON DELETE SET NULL`, entao um
    DELETE de verdade orfanaria toda a autoria dela de uma vez.
    """
    _recusar_auto_alvo(id_alvo, autor)

    with transacao(id_usuario=autor) as con:
        _, ativo_antes = _estado_atual(con, id_alvo)

        if ativo_antes == ativo:
            return {"id_usuario": id_alvo, "ativo": ativo, "mudou": False}

        con.execute(SQL_DEFINIR_ATIVO, (ativo, id_alvo))
        _registrar(
            con,
            autor=autor,
            tipo=EVENTO_REATIVADO if ativo else EVENTO_DESATIVADO,
            id_alvo=id_alvo,
            metadados=None,
        )

    return {"id_usuario": id_alvo, "ativo": ativo, "mudou": True}
