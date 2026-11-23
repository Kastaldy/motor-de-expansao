"""Os avisos do piloto: o sino dos pedidos dos masters (DEC-090, migration 028).

O aviso e' o EVENTO
-------------------
A trilha (`eventos`) ja' guarda cada gesto do master com quem, quando e o que: o imovel pedido
(`imovel.solicitado`) e o estudo pedido (`estudo.solicitado`). O sino le essas linhas -- nao ha'
tabela de avisos que copie a trilha e possa divergir dela. O que a 028 acrescenta e' so' QUEM
recebe (`usuario_avisos`, alem da capacidade de perfil) e ATE' ONDE cada pessoa leu
(`avisos_lidos`).

Quem recebe
-----------
O estudo vai para o perfil `growth` inteiro (Juan, 19/11/2026: "o time todo da Growth"), pela
capacidade `avisos.estudos_masters`; o imovel vai para quem tem o aviso marcado na aba Acessos
(a Priscila). A lista por pessoa tambem da' o aviso de estudo a quem esta' fora do Growth.

Por que o SQL mora aqui
-----------------------
O mesmo motivo do `eventos.py` e do `usuarios.py`: os guardrails de AST recusam SQL de escrita
em `web/server/app.py`, e a suite unitaria nao tem Postgres -- o SQL precisa ser localizavel.
"""

from __future__ import annotations

from typing import Any

from .eventos import EVENTO_ESTUDO_SOLICITADO, EVENTO_IMOVEL_SOLICITADO
from .postgres import conexao, transacao

#: Os avisos que existem: o identificador (o mesmo do CHECK `chk_usuario_avisos_tipo` da 028), o
#: rotulo de tela e o evento da trilha de onde ele sai. A ordem e' a da tela.
AVISO_ESTUDO_MASTER = "estudo_master"
AVISO_IMOVEL_MASTER = "imovel_master"
AVISOS: dict[str, tuple[str, str]] = {
    AVISO_ESTUDO_MASTER: ("Estudo pedido por um master", EVENTO_ESTUDO_SOLICITADO),
    AVISO_IMOVEL_MASTER: ("Imóvel pedido por um master", EVENTO_IMOVEL_SOLICITADO),
}

#: A capacidade de PERFIL que da' um aviso a todo o perfil (o Growth inteiro recebe o de estudo).
#: Aviso fora daqui so' chega a quem o tem marcado na aba Acessos.
CAPACIDADE_DO_AVISO: dict[str, str] = {AVISO_ESTUDO_MASTER: "avisos.estudos_masters"}

#: Quantos avisos o sino mostra de uma vez: os mais novos.
LIMITE_DA_LISTA = 30

SQL_AVISOS_DA_PESSOA = """
SELECT aviso FROM usuario_avisos WHERE id_usuario = %s ORDER BY aviso
"""

SQL_ULTIMO_LIDO = """
SELECT ultimo_id_evento FROM avisos_lidos WHERE id_usuario = %s
"""

# Os avisos sao os eventos dos tipos que a pessoa recebe, do mais novo para o mais velho, com o
# nome de quem fez o gesto (`nome_usuario`; evento de sistema sai sem nome).
SQL_LISTAR = """
SELECT e.id_evento, e.tipo, e.metadados, e.criado_em_evento, u.nome_usuario
FROM eventos e
LEFT JOIN usuarios u ON u.id_usuario = e.id_usuario
WHERE e.tipo = ANY(%s)
ORDER BY e.id_evento DESC
LIMIT %s
"""

SQL_NAO_LIDOS = """
SELECT count(*) FROM eventos WHERE tipo = ANY(%s) AND id_evento > %s
"""

# "Lido ate'": so' anda para a frente (`GREATEST`), entao duas abas abertas nao fazem o sino voltar
# a contar o que a pessoa ja' viu.
SQL_MARCAR_LIDOS = """
INSERT INTO avisos_lidos (id_usuario, ultimo_id_evento) VALUES (%s, %s)
ON CONFLICT (id_usuario) DO UPDATE
SET ultimo_id_evento = GREATEST(avisos_lidos.ultimo_id_evento, EXCLUDED.ultimo_id_evento),
    lido_em = now()
"""


def avisos_da_pessoa(id_usuario: int) -> frozenset[str]:
    """Os avisos marcados para a pessoa na aba Acessos (`usuario_avisos`)."""
    with conexao() as con:
        linhas = con.execute(SQL_AVISOS_DA_PESSOA, (id_usuario,)).fetchall()
    return frozenset(str(linha[0]) for linha in linhas)


def avisos_que_recebe(id_usuario: int, permissoes: frozenset[str]) -> tuple[str, ...]:
    """Os avisos que chegam a pessoa, na ordem da tela: os do perfil (pela capacidade) e os
    marcados para ela na aba Acessos."""
    marcados = avisos_da_pessoa(id_usuario)
    return tuple(
        aviso
        for aviso in AVISOS
        if aviso in marcados
        or (aviso in CAPACIDADE_DO_AVISO and CAPACIDADE_DO_AVISO[aviso] in permissoes)
    )


def _aviso_do_evento(tipo: str) -> str | None:
    return next((aviso for aviso, (_r, evento) in AVISOS.items() if evento == tipo), None)


def listar(
    id_usuario: int, avisos: tuple[str, ...], limite: int = LIMITE_DA_LISTA
) -> dict[str, Any]:
    """O sino da pessoa: os avisos mais novos dos tipos que ela recebe, quantos ela ainda nao viu
    e ate' onde ja' viu. Sem aviso nenhum, a lista vazia (sem consultar a trilha)."""
    tipos = [AVISOS[a][1] for a in avisos if a in AVISOS]
    if not tipos:
        return {"itens": [], "nao_lidos": 0, "ultimo_lido": 0}
    with conexao() as con:
        linha = con.execute(SQL_ULTIMO_LIDO, (id_usuario,)).fetchone()
        ultimo_lido = int(linha[0]) if linha else 0
        linhas = con.execute(SQL_LISTAR, (tipos, limite)).fetchall()
        nao_lidos = int(con.execute(SQL_NAO_LIDOS, (tipos, ultimo_lido)).fetchone()[0])
    itens = [
        {
            "id": int(id_evento),
            "aviso": _aviso_do_evento(str(tipo)),
            "quando": quando.isoformat() if quando is not None else None,
            "quem": str(nome) if nome else None,
            "dados": dict(metadados or {}),
            "lido": int(id_evento) <= ultimo_lido,
        }
        for id_evento, tipo, metadados, quando, nome in linhas
    ]
    return {"itens": itens, "nao_lidos": nao_lidos, "ultimo_lido": ultimo_lido}


def marcar_lidos(id_usuario: int, ate_id_evento: int) -> None:
    """A pessoa viu os avisos ate' `ate_id_evento` (o mais novo que estava no sino aberto)."""
    with transacao(id_usuario=id_usuario) as con:
        con.execute(SQL_MARCAR_LIDOS, (id_usuario, max(0, int(ate_id_evento))))
