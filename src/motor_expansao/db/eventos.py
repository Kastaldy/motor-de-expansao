"""Eventos de ARTEFATO: o produtor que faltava para o D17.

O que esta camada resolve
-------------------------
O D17 pede rastrear um PDF vazado de volta a quem o gerou. O banco estava pronto ha'
tres migrations -- `eventos.metadados` e' `jsonb` e existe o indice PARCIAL
`idx_eventos_metadados_report_id ... WHERE tipo = 'relatorio.gerado'`, feito sob medida
para essa busca (a 005 o criou). Mas `report_id` nao existia em NENHUMA linha do codigo:
nenhum era cunhado, nenhum carimbado, nenhum evento gravado. O indice esperava uma linha
que nunca chegava.

Por que cunhar e gravar na MESMA funcao
---------------------------------------
Separar as duas coisas deixaria existir um id que nao virou linha -- e o contrato e'
explicito: "Um `relatorio.gerado` sem `report_id` nao cumpre o D17 e nao deve ser
gravado" (`docs/eventos_contrato.md` §2.2). O inverso tambem vale: um id carimbado no
PDF sem evento no banco e' uma promessa de rastreio que o banco nao pode cumprir. Aqui as
duas nascem juntas, e quem chama recebe o id de volta ja' gravado.

Por que o SQL mora aqui, e nao na rota
--------------------------------------
Dois guardrails de AST batem em `web/server/app.py` se o INSERT subir para la':
`test_backend_read_only_por_ast` e `test_backend_nao_tem_sql_de_escrita_embutido`. Nao e'
burocracia: o CI nao tem Postgres, entao o SQL precisa ser LOCALIZAVEL para haver o que
revisar antes de rodar contra banco real. Mesmo raciocinio do `usuarios.py`.

O que este modulo NAO decide
----------------------------
Se o relatorio deve sair quando o banco esta fora. Isso e' politica de produto e vive no
chamador -- ver a nota em `web/server/app.py`, na rota do Pontual.
"""

from __future__ import annotations

import uuid
from typing import Any

from .postgres import transacao

#: Vocabulario de `tipo` do `docs/eventos_contrato.md` §2.2. Fora desta lista e' defeito.
EVENTO_RELATORIO_GERADO = "relatorio.gerado"
EVENTO_DOSSIE_BAIXADO = "dossie.baixado"

#: As chaves de alvo sao CONTRATO, e o defeito de errar uma e' SILENCIOSO: a escrita passa,
#: o evento cai fora do indice parcial, e ninguem descobre ate' a tabela crescer. O contrato
#: diz, com todas as letras: "Gravar `id_imovel` ou `imovel` poe o evento fora dos indices".
CHAVES_DE_ALVO = ("hex_id", "imovel_id", "unidade_id")

# `entidade`/`entidade_id` ficam NULOS aqui, e isso e' a emenda ao D17 (D24): a segunda
# metade da convencao so' vale quando o alvo e' LINHA deste banco. Relatorio sobre hexagono
# ou imovel poe o alvo em `metadados` -- os ids do motor sao textuais (`im_3f2a9b`, indice
# H3 de 15 caracteres) e `entidade_id` e' BIGINT.
SQL_REGISTRAR_RELATORIO = """
INSERT INTO eventos (id_usuario, tipo, entidade, entidade_id, metadados)
VALUES (%s, %s, NULL, NULL, %s)
"""


# Mesma forma do INSERT acima, e constante PROPRIA de proposito: reusar a do relatorio faria o
# nome mentir sobre o que a instrucao grava, e as duas podem divergir amanha (o dossie nao tem
# `report_id` -- ele nao e' gerado pelo motor, vem pronto do coletor).
SQL_REGISTRAR_DOSSIE = """
INSERT INTO eventos (id_usuario, tipo, entidade, entidade_id, metadados)
VALUES (%s, %s, NULL, NULL, %s)
"""


class AlvoForaDoContrato(ValueError):
    """Chave de alvo que os indices parciais nao conhecem. Ver `CHAVES_DE_ALVO`."""


def novo_report_id() -> str:
    """Um identificador de relatorio. UUID4, em minusculas, sem chaves.

    UUID4 e nao sequencial de proposito: o id vai IMPRESSO num arquivo que pode circular
    fora da empresa, e um contador anunciaria quantos relatorios o motor ja' gerou.
    """
    return str(uuid.uuid4())


def registrar_relatorio(
    *,
    autor: int | None,
    relatorio: str,
    formato: str,
    origem: str = "web",
    alvo: dict[str, str] | None = None,
    report_id: str | None = None,
) -> str:
    """Grava `relatorio.gerado` e devolve o `report_id` -- cunhado aqui se nao vier pronto.

    `autor` e' `id_usuario` de quem pediu, e pode ser `None`: o D19 preve acao de sistema
    com autoria nula, e e' melhor um evento com autor nulo que evento nenhum. Mas quem
    chama deve passar o autor sempre que souber -- um `relatorio.gerado` anonimo cumpre
    metade do D17 (diz que o arquivo existiu, nao diz de quem).

    `relatorio` distingue Pontual de Municipal de Comparacao; `formato` distingue pdf de
    xlsx. Os dois sao necessarios: a §2.2 poe os quatro relatorios sob o MESMO `tipo`, e
    `formato` sozinho nao separa Pontual de Municipal, que sao ambos PDF.

    `alvo` e' opcional e as chaves sao fechadas (`CHAVES_DE_ALVO`) -- ver o comentario
    delas. Levanta `AlvoForaDoContrato` em chave desconhecida, em vez de gravar um evento
    que os indices nao alcancam.
    """
    if alvo:
        fora = sorted(set(alvo) - set(CHAVES_DE_ALVO))
        if fora:
            raise AlvoForaDoContrato(
                f"chave(s) de alvo fora do contrato: {', '.join(fora)}. "
                f"O contrato fecha em {', '.join(CHAVES_DE_ALVO)} -- outra chave poe o "
                "evento fora dos indices parciais, e o defeito e' silencioso."
            )

    identificador = report_id or novo_report_id()
    metadados: dict[str, Any] = {
        "report_id": identificador,
        "relatorio": relatorio,
        "formato": formato,
        "origem": origem,
    }
    if alvo:
        metadados.update(alvo)

    from psycopg.types.json import Jsonb  # import tardio: so' quem escreve paga

    with transacao(id_usuario=autor) as con:
        con.execute(
            SQL_REGISTRAR_RELATORIO,
            (autor, EVENTO_RELATORIO_GERADO, Jsonb(metadados)),
        )
    return identificador


def registrar_dossie_baixado(*, autor: int | None, imovel_id: str, origem: str = "web") -> None:
    """Grava `dossie.baixado` -- o PDF do coletor, o unico artefato com PII de corretor.

    Linha propria no contrato (§2.2), e nao um `relatorio.gerado` a mais, por duas razoes que
    andam juntas: o motor NAO o gera (vem pronto do coletor imobiliario, DEC-037) e ele carrega
    contato de corretor. Nao ha `report_id` para carimbar -- o arquivo nao passa pela nossa
    geracao --, entao o rastreio possivel e' pelo par (quem, quando), e o alvo em `metadados`.

    `imovel_id` e' a chave que o contrato fecha (`CHAVES_DE_ALVO`) e que o indice parcial da 014
    conhece. `entidade`/`entidade_id` ficam nulos pela emenda do D24: o id do imovel e' TEXTUAL
    (`im_3f2a9b`) e `entidade_id` e' BIGINT.

    `autor` pode ser `None` pelo mesmo motivo do `registrar_relatorio`: o D19 preve acao de
    autoria nula, e meio evento -- "este dossie foi baixado" -- vale mais que evento nenhum.
    """
    from psycopg.types.json import Jsonb  # import tardio: so' quem escreve paga

    metadados: dict[str, Any] = {"imovel_id": imovel_id, "origem": origem}
    with transacao(id_usuario=autor) as con:
        con.execute(
            SQL_REGISTRAR_DOSSIE,
            (autor, EVENTO_DOSSIE_BAIXADO, Jsonb(metadados)),
        )
