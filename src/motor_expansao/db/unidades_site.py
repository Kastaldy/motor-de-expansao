"""Unidades Ultra incluídas pelo site (migration 024, DEC-085).

Growth e líderes incluem uma unidade pelo Mapa; ela vive aqui até o cron de domingo levá-la ao
`unidades_ultra_mapeadas.parquet`. As regras moram em dois lugares que se cobrem:

* no BANCO (024): remover é marcar, e a trigger de guarda recusa mexer numa unidade com 1 dia
  ou mais — nem o `app` consegue;
* AQUI: a mesma conferência, com a linha TRAVADA (`FOR UPDATE`) na transação do UPDATE, para a
  tela receber um recado legível (409) em vez do erro da trigger.

O que este módulo NÃO decide: se o nome é repetido, se o ponto está perto de outra unidade, se
cai no país. Isso precisa do cadastro inteiro (parquet + site), e mora em
`motor_expansao.cadastro_ultra`, que o script da conta `deploy` também usa.

Todo SQL fica em constante nomeada (convenção do pacote, `banco_conexao.md` §7).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from ..cadastro_ultra import UnidadeDoSite
from .postgres import conexao, transacao

COLUNAS = (
    "u.id_unidade_site, u.pais, u.nome_unidade_site, u.uf_unidade_site, u.cidade_unidade_site, "
    "u.lat_unidade_site, u.lng_unidade_site, u.hex_id_res7, u.criada_em_unidade_site, "
    "u.id_usuario_criou, quem.nome_usuario, u.alterada_em_unidade_site, u.removida_em_unidade_site"
)

# As VIVAS do país do deploy, com o nome de quem incluiu (para a lista do primeiro dia).
SQL_LISTAR_VIVAS = f"""
SELECT {COLUNAS}
FROM unidades_ultra_site u
JOIN usuarios quem ON quem.id_usuario = u.id_usuario_criou
WHERE u.pais = %s AND u.removida_em_unidade_site IS NULL
ORDER BY u.criada_em_unidade_site, u.id_unidade_site
"""

SQL_CRIAR = """
INSERT INTO unidades_ultra_site
  (pais, nome_unidade_site, uf_unidade_site, cidade_unidade_site, lat_unidade_site,
   lng_unidade_site, hex_id_res7, id_usuario_criou)
VALUES (%(pais)s, %(unidade)s, %(uf)s, %(cidade)s, %(lat)s, %(lng)s, %(hex)s, %(autor)s)
RETURNING id_unidade_site
"""

# `pais` no WHERE: a unidade de outro país não existe para este deploy (404, não 403). O prazo é
# medido pelo RELÓGIO DO BANCO, o mesmo que a trigger de guarda usa.
SQL_TRAVAR = """
SELECT removida_em_unidade_site, criada_em_unidade_site > now() - interval '24 hours'
FROM unidades_ultra_site
WHERE id_unidade_site = %s AND pais = %s
FOR UPDATE
"""

SQL_ALTERAR = """
UPDATE unidades_ultra_site
SET nome_unidade_site = %(unidade)s, uf_unidade_site = %(uf)s, cidade_unidade_site = %(cidade)s,
    lat_unidade_site = %(lat)s, lng_unidade_site = %(lng)s, hex_id_res7 = %(hex)s,
    alterada_em_unidade_site = now(), alterada_por = %(autor)s
WHERE id_unidade_site = %(id)s
"""

SQL_AGORA = "SELECT now()"

SQL_REMOVER = """
UPDATE unidades_ultra_site
SET removida_em_unidade_site = now(), removida_por = %(autor)s
WHERE id_unidade_site = %(id)s
"""


class UnidadeDesconhecida(LookupError):
    """O id não existe neste país (404)."""


class UnidadeRemovida(ValueError):
    """A unidade já foi removida: não se altera nem se remove de novo (409)."""


class PrazoEncerrado(ValueError):
    """Passou 1 dia desde a inclusão: a correção agora é por PR (409)."""


MENSAGEM_PRAZO = (
    "Passou o prazo de 1 dia para alterar ou remover esta unidade pelo site. A correção agora é "
    "feita pelo time de tecnologia, por PR."
)


def _unidade(linha: Sequence[Any]) -> UnidadeDoSite:
    (ident, pais, nome, uf, cidade, lat, lng, hexa, criada, autor, nome_autor, alterada, removida) = linha
    return UnidadeDoSite(
        id_unidade_site=int(ident),
        pais=str(pais),
        unidade=str(nome),
        uf=str(uf),
        cidade=str(cidade),
        lat=float(lat),
        lng=float(lng),
        hex_id_res7=str(hexa),
        criada_em=criada,
        id_usuario_criou=int(autor),
        nome_quem_criou=None if nome_autor is None else str(nome_autor),
        alterada_em=alterada,
        removida_em=removida,
    )


def listar_vivas(pais: str) -> list[UnidadeDoSite]:
    """As unidades do site ainda não removidas, do país pedido, em ordem de inclusão."""
    with conexao() as con:
        linhas = con.execute(SQL_LISTAR_VIVAS, (pais,)).fetchall()
    return [_unidade(linha) for linha in linhas]


def _parametros(unidade: str, uf: str, cidade: str, lat: float, lng: float, hexa: str) -> dict[str, Any]:
    return {
        "unidade": unidade,
        "uf": uf,
        "cidade": cidade,
        "lat": float(lat),
        "lng": float(lng),
        "hex": hexa,
    }


def incluir(
    *,
    pais: str,
    unidade: str,
    uf: str,
    cidade: str,
    lat: float,
    lng: float,
    hex_id_res7: str,
    autor: int,
) -> int:
    """Grava a unidade nova e devolve o id."""
    with transacao(id_usuario=autor) as con:
        linha = con.execute(
            SQL_CRIAR,
            {"pais": pais, "autor": autor, **_parametros(unidade, uf, cidade, lat, lng, hex_id_res7)},
        ).fetchone()
    return int(linha[0])


def _travar(con: Any, id_unidade_site: int, pais: str) -> None:
    linha = con.execute(SQL_TRAVAR, (id_unidade_site, pais)).fetchone()
    if linha is None:
        raise UnidadeDesconhecida(f"Unidade {id_unidade_site} não encontrada.")
    removida_em, no_prazo = linha
    if removida_em is not None:
        raise UnidadeRemovida("Esta unidade já foi removida.")
    if not no_prazo:
        raise PrazoEncerrado(MENSAGEM_PRAZO)


def alterar(
    id_unidade_site: int,
    *,
    pais: str,
    unidade: str,
    uf: str,
    cidade: str,
    lat: float,
    lng: float,
    hex_id_res7: str,
    autor: int,
) -> None:
    """Corrige nome, UF, cidade ou coordenada, só no primeiro dia."""
    with transacao(id_usuario=autor) as con:
        _travar(con, id_unidade_site, pais)
        con.execute(
            SQL_ALTERAR,
            {"id": id_unidade_site, "autor": autor, **_parametros(unidade, uf, cidade, lat, lng, hex_id_res7)},
        )


def remover(id_unidade_site: int, *, pais: str, autor: int) -> None:
    """Marca como removida, só no primeiro dia. Nada sai do banco."""
    with transacao(id_usuario=autor) as con:
        _travar(con, id_unidade_site, pais)
        con.execute(SQL_REMOVER, {"id": id_unidade_site, "autor": autor})


def agora_do_banco() -> datetime:
    """O relógio que a trigger usa: a composição de domingo mede o prazo por ele."""
    with conexao() as con:
        return con.execute(SQL_AGORA).fetchone()[0]
