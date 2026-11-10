"""Anotações de campo nas academias concorrentes (migration 022).

O que o time vê numa visita — metragem, equipamentos, um comentário — e que a coleta não traz.
É a segunda ESCRITA do piloto que qualquer perfil faz, e por isso as regras moram em dois
lugares que se cobrem:

* no BANCO (022): apagar é marcar, editar grava a versão anterior no histórico, e o histórico
  só a trigger escreve. Nem o dono apaga linha sem desligar trigger.
* AQUI: só o autor edita ou apaga a própria anotação; quem tem `concorrente.ver_autor`
  (Growth) apaga a de qualquer um, como moderação. A checagem é feita com a linha TRAVADA
  (`FOR UPDATE`), na mesma transação do UPDATE, para não haver janela entre conferir e gravar.

O que este módulo NÃO decide: quem vê o nome do autor. Isso é apresentação, e mora em
`web/server/observacoes.py` (`montar_resposta`) — aqui as funções de leitura devolvem o
`id_usuario_autor` cru, e o nome só é buscado (`nomes_dos_autores`) quando a rota já sabe
que a pessoa pode vê-lo.

Todo SQL fica em constante nomeada (convenção do pacote, `banco_conexao.md` §7).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import astuple, dataclass
from datetime import datetime
from typing import Any

from .postgres import conexao, transacao

#: Raio, em GRAUS, da leitura por proximidade: ~165 m de latitude e ~150 m de longitude nas
#: latitudes do Brasil. Acha a anotação quando a chave da academia mudou (a coleta ajustou o
#: nome, ou a re-geocodificação cruzou a célula res-5), sem trazer a vizinha do outro lado da
#: rua: duas unidades da MESMA rede a menos de 150 m uma da outra são raras o bastante para
#: o custo de juntá-las ser menor que o de perder a anotação.
TOLERANCIA_GRAUS = 0.0015

#: As colunas de CONTEUDO, na ordem de `CamposObservacao`. Uma lista so' para leitura, escrita e
#: historico: esquecer uma coluna numa delas e' o defeito da DEC-038 (coluna existe, campo vazio).
COLUNAS_CONTEUDO = (
    "metragem_m2",
    "equipamentos_observacao",
    "vagas_estacionamento",
    "comodidades_observacao",
    "nota_conservacao",
    "nota_fachada",
    "nota_atendimento",
    "alunos_estimados",
    "comentario_observacao",
)
_CONTEUDO = ", ".join(COLUNAS_CONTEUDO)

COLUNAS = (
    f"id_observacao, id_usuario_autor, {_CONTEUDO}, versao_observacao, criada_em_observacao, "
    "atualizada_em_observacao, apagada_em_observacao, apagada_por"
)

SQL_LISTAR = f"""
SELECT {COLUNAS}
FROM observacoes_concorrente
WHERE pais = %(pais)s
  AND (
    chave_concorrente = %(chave)s
    OR (
      rede_concorrente = %(rede)s
      AND lat_concorrente BETWEEN %(lat)s - %(tol)s AND %(lat)s + %(tol)s
      AND lng_concorrente BETWEEN %(lng)s - %(tol)s AND %(lng)s + %(tol)s
    )
  )
ORDER BY criada_em_observacao, id_observacao
"""

SQL_HISTORICO = f"""
SELECT id_observacao, acao_observacao, versao_observacao, {_CONTEUDO},
       registrado_em, registrado_por
FROM observacoes_concorrente_historico
WHERE id_observacao = ANY(%s)
ORDER BY id_observacao, registrado_em, id_observacao_historico
"""

SQL_NOMES = """
SELECT u.id_usuario, u.nome_usuario, p.nome_perfil
FROM usuarios u
JOIN perfis p ON p.id_perfil = u.id_perfil
WHERE u.id_usuario = ANY(%s)
"""

# Contagem para o selo do pino: SÓ a âncora exata. A proximidade fica para o painel, que
# pergunta por UMA academia; aqui a pergunta é por centenas de chaves de uma vez.
SQL_CONTAR = """
SELECT chave_concorrente, count(*)
FROM observacoes_concorrente
WHERE pais = %s AND chave_concorrente = ANY(%s) AND apagada_em_observacao IS NULL
GROUP BY chave_concorrente
"""

SQL_CRIAR = f"""
INSERT INTO observacoes_concorrente
  (pais, chave_concorrente, rede_concorrente, nome_concorrente, lat_concorrente,
   lng_concorrente, id_usuario_autor, {_CONTEUDO})
VALUES (%(pais)s, %(chave)s, %(rede)s, %(nome)s, %(lat)s, %(lng)s, %(autor)s,
        {", ".join(f"%({c})s" for c in COLUNAS_CONTEUDO)})
RETURNING id_observacao, versao_observacao
"""

# `pais` no WHERE: a anotação de outro país não existe para este deploy (404, não 403).
SQL_TRAVAR = """
SELECT id_usuario_autor, versao_observacao, apagada_em_observacao
FROM observacoes_concorrente
WHERE id_observacao = %s AND pais = %s
FOR UPDATE
"""

SQL_EDITAR = f"""
UPDATE observacoes_concorrente
SET {", ".join(f"{c} = %({c})s" for c in COLUNAS_CONTEUDO)}
WHERE id_observacao = %(id)s
RETURNING versao_observacao
"""

SQL_APAGAR = """
UPDATE observacoes_concorrente
SET apagada_em_observacao = now(), apagada_por = %(autor)s
WHERE id_observacao = %(id)s
"""


class ObservacaoDesconhecida(LookupError):
    """O id não existe neste país (404)."""


class NaoEhOAutor(PermissionError):
    """Editar, ou apagar sem moderação, a anotação de outra pessoa (403)."""


class ObservacaoApagada(ValueError):
    """A anotação já foi apagada: não se edita nem se apaga de novo (409)."""


class ConflitoDeVersao(ValueError):
    """Alguém salvou outra versão desde que a pessoa abriu o formulário (409)."""


@dataclass(frozen=True)
class CamposObservacao:
    """O que a pessoa escreve. Mesma ordem de `COLUNAS_CONTEUDO`. Notas de 1 a 10."""

    metragem_m2: int | None = None
    equipamentos: str | None = None
    vagas: int | None = None
    comodidades: str | None = None
    nota_conservacao: int | None = None
    nota_fachada: int | None = None
    nota_atendimento: int | None = None
    alunos_estimados: int | None = None
    comentario: str | None = None

    def como_parametros(self) -> dict[str, Any]:
        return dict(zip(COLUNAS_CONTEUDO, astuple(self), strict=True))


@dataclass(frozen=True)
class Observacao:
    id_observacao: int
    id_usuario_autor: int
    campos: CamposObservacao
    versao: int
    criada_em: datetime
    atualizada_em: datetime
    apagada_em: datetime | None
    apagada_por: int | None


@dataclass(frozen=True)
class RegistroHistorico:
    id_observacao: int
    acao: str
    versao: int
    campos: CamposObservacao
    registrado_em: datetime
    registrado_por: int | None


_N = len(COLUNAS_CONTEUDO)


def _observacao(linha: Sequence[Any]) -> Observacao:
    ident, autor = linha[0], linha[1]
    campos = CamposObservacao(*linha[2 : 2 + _N])
    versao, criada, atualizada, apagada_em, apagada_por = linha[2 + _N :]
    return Observacao(ident, autor, campos, versao, criada, atualizada, apagada_em, apagada_por)


def _registro(linha: Sequence[Any]) -> RegistroHistorico:
    ident, acao, versao = linha[0], linha[1], linha[2]
    campos = CamposObservacao(*linha[3 : 3 + _N])
    registrado_em, registrado_por = linha[3 + _N :]
    return RegistroHistorico(ident, acao, versao, campos, registrado_em, registrado_por)


def listar(*, pais: str, chave: str, rede: str, lat: float, lng: float) -> list[Observacao]:
    """Todas as anotações de UMA academia — vivas e apagadas, em ordem de criação.

    As apagadas vêm junto de propósito: a numeração "Pessoa N" conta todos os autores, senão
    "Pessoa 2" viraria "Pessoa 1" quando alguém apagasse. Quem decide o que cada pessoa vê é
    `montar_resposta`, não a consulta.
    """
    parametros = {
        "pais": pais,
        "chave": chave,
        "rede": rede,
        "lat": float(lat),
        "lng": float(lng),
        "tol": TOLERANCIA_GRAUS,
    }
    with conexao() as con:
        linhas = con.execute(SQL_LISTAR, parametros).fetchall()
    return [_observacao(linha) for linha in linhas]


def historico(ids: Sequence[int]) -> list[RegistroHistorico]:
    """O histórico das anotações pedidas, em ordem real (`clock_timestamp`)."""
    if not ids:
        return []
    with conexao() as con:
        linhas = con.execute(SQL_HISTORICO, (list(ids),)).fetchall()
    return [_registro(linha) for linha in linhas]


def nomes_dos_autores(ids: Iterable[int]) -> dict[int, tuple[str, str]]:
    """`id_usuario -> (nome, perfil)`. Só para quem pode ver o autor — a rota garante."""
    lista = sorted({int(i) for i in ids if i is not None})
    if not lista:
        return {}
    with conexao() as con:
        linhas = con.execute(SQL_NOMES, (lista,)).fetchall()
    return {int(i): (str(nome), str(perfil)) for i, nome, perfil in linhas}


def contar(*, pais: str, chaves: Sequence[str]) -> dict[str, int]:
    """Anotações VIVAS por chave, para o selo do pino."""
    if not chaves:
        return {}
    with conexao() as con:
        linhas = con.execute(SQL_CONTAR, (pais, list(chaves))).fetchall()
    return {str(chave): int(n) for chave, n in linhas}


def criar(
    *,
    pais: str,
    chave: str,
    rede: str,
    nome: str,
    lat: float,
    lng: float,
    autor: int,
    campos: CamposObservacao,
) -> int:
    """Grava a anotação nova e devolve o id. O histórico nasce pela trigger."""
    with transacao(id_usuario=autor) as con:
        linha = con.execute(
            SQL_CRIAR,
            {
                "pais": pais,
                "chave": chave,
                "rede": rede,
                "nome": nome,
                "lat": float(lat),
                "lng": float(lng),
                "autor": autor,
                **campos.como_parametros(),
            },
        ).fetchone()
    return int(linha[0])


def _travar(con: Any, id_observacao: int, pais: str) -> tuple[int, int, datetime | None]:
    linha = con.execute(SQL_TRAVAR, (id_observacao, pais)).fetchone()
    if linha is None:
        raise ObservacaoDesconhecida(f"Anotação {id_observacao} não encontrada.")
    return int(linha[0]), int(linha[1]), linha[2]


def editar(
    id_observacao: int,
    *,
    pais: str,
    autor: int,
    versao: int,
    campos: CamposObservacao,
) -> int:
    """Edita a PRÓPRIA anotação, se ela ainda estiver na versão que a pessoa viu.

    Devolve a versão nova. Moderação não edita: Growth apaga a anotação de outra pessoa, mas
    reescrever as palavras de alguém sob o nome dele é outra coisa.
    """
    with transacao(id_usuario=autor) as con:
        dono, versao_atual, apagada_em = _travar(con, id_observacao, pais)
        if dono != autor:
            raise NaoEhOAutor("Só quem escreveu a anotação pode editá-la.")
        if apagada_em is not None:
            raise ObservacaoApagada("Esta anotação foi apagada e não pode mais ser editada.")
        if versao_atual != versao:
            raise ConflitoDeVersao(
                "Esta anotação mudou desde que você a abriu. Feche e abra de novo para ver a "
                "versão atual."
            )
        linha = con.execute(
            SQL_EDITAR, {"id": id_observacao, **campos.como_parametros()}
        ).fetchone()
    return int(linha[0])


def apagar(id_observacao: int, *, pais: str, autor: int, pode_moderar: bool) -> bool:
    """Marca como apagada. Devolve `True` quando foi moderação (a anotação era de outra pessoa)."""
    with transacao(id_usuario=autor) as con:
        dono, _versao, apagada_em = _travar(con, id_observacao, pais)
        moderacao = dono != autor
        if moderacao and not pode_moderar:
            raise NaoEhOAutor("Só quem escreveu a anotação pode apagá-la.")
        if apagada_em is not None:
            raise ObservacaoApagada("Esta anotação já foi apagada.")
        con.execute(SQL_APAGAR, {"id": id_observacao, "autor": autor})
    return moderacao
