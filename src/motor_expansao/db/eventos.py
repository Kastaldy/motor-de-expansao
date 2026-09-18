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

#: Os dois gestos da §2.4 que sobem para `eventos`. Os outros cinco ficam so' na trilha de 90
#: dias: marcar visita e' DECISAO DE NEGOCIO sobre um imovel, abrir uma aba nao e'.
EVENTO_VISITA_MARCADA = "imovel.visita_marcada"
EVENTO_VISITA_DESMARCADA = "imovel.visita_desmarcada"

#: §2.5. SEM alvo de proposito -- ver a correcao de 16/09 naquela secao: nem o pedido nem o
#: backend conhecem `hex_id`/`imovel_id`, e derivar da coordenada e' o que a §2.2 recusa.
EVENTO_VIABILIDADE_CALCULADA = "viabilidade.calculada"

#: §2.1, destravados pela epic do P19 (D30). Ate' aqui o contrato os listava como "ainda nao
#: registravel", e o motivo nao era falta de coluna: enquanto o Authelia autentica, a entrada
#: nao passa pelo motor -- o piloto so' recebe o `Remote-User` ja' resolvido.
#:
#: E ISTO NAO E' CONVENIENCIA DE AUDITORIA, E' REPOSICAO. O `docs/trilha_acesso_piloto.md` §22
#: registra que as tentativas de login do Authelia -- sucesso E falha, com usuario e IP -- sao a
#: CAMADA 3 da trilha, a que "responde quem entrou e quando". O corte remove essa camada, e
#: sem estes dois eventos ela nao teria substituto nenhum.
#:
#: `metadados` leva SO' `origem`, pela regra da §2.7: "nunca o login nem o e-mail do alvo em
#: `metadados`" -- e' PII, e o `id_usuario` do carimbo ja' identifica a pessoa. `logout` nao
#: leva metadado algum, porque nao ha' o que qualificar numa saida explicita.
EVENTO_LOGIN = "login"
EVENTO_LOGOUT = "logout"

#: Tentativa RECUSADA. Nao existia no contrato ate' 18/09/2026 -- a §2.1 previa so' o
#: sucesso, e a propria nota de la' registrava a falta como decisao em aberto da epic.
#:
#: O QUE ELE PODE CARREGAR E' PEQUENO, E POR DECISAO ALHEIA A ESTE ARQUIVO:
#:   * o IP fica FORA -- o P15 (base legal e prazo de retencao) segue aberto, e ha' teste
#:     de contrato que recusa qualquer `INSERT` em `eventos` mencionando a coluna. Quem
#:     guarda o IP da tentativa e' a trilha da DEC-027, em arquivo, por 90 dias;
#:   * o LOGIN DIGITADO fica fora -- a §2.7 proibe login e e-mail em `metadados` (PII), e
#:     e' exatamente o unico identificador quando o usuario digitado nao existe.
#:
#: Sobra o que importa: quando o login EXISTE, o `id_usuario` vai na coluna de autor, e a
#: pergunta "quantas tentativas falhas contra esta conta" passa a ter resposta. Quando nao
#: existe, a linha sai com autoria nula -- e e' o `usuario_conhecido` dos metadados que
#: separa SENHA ERRADA de VARREDURA DE NOMES, que sao incidentes diferentes.
EVENTO_LOGIN_RECUSADO = "login.recusado"

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

# Idem, e pela mesma razao de nome: o que se grava aqui e' gesto sobre imovel, nao artefato.
SQL_REGISTRAR_VISITA = """
INSERT INTO eventos (id_usuario, tipo, entidade, entidade_id, metadados)
VALUES (%s, %s, NULL, NULL, %s)
"""

# Idem. Aqui `entidade` nula nao e' emenda do D24 e sim ausencia real: a analise nao declara alvo.
SQL_REGISTRAR_VIABILIDADE = """
INSERT INTO eventos (id_usuario, tipo, entidade, entidade_id, metadados)
VALUES (%s, %s, NULL, NULL, %s)
"""

# Acesso (§2.1). Constante propria pelo mesmo motivo das outras quatro: reusar faria o nome
# mentir sobre o que a instrucao grava, e as duas podem divergir amanha -- `login` tem
# `metadados` e `logout` nao tem nenhum, entao ja' nascem diferentes no CHAMADOR.
SQL_REGISTRAR_ACESSO = """
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


def registrar_visita(
    *, autor: int | None, imovel_id: str, marcada: bool, origem: str = "web"
) -> None:
    """Grava `imovel.visita_marcada` ou `_desmarcada` -- decisao de negocio sobre um imovel.

    UMA funcao com o estado no parametro, e nao duas quase iguais: os dois eventos tem a mesma
    forma e a mesma chave de alvo, e o que muda e' so' o `tipo`. Duas copias divergiriam no dia
    em que uma ganhasse campo e a outra nao.

    `marcada` e' o estado RESULTANTE do gesto, como a tela ja' carimba -- "marcou" e "desmarcou"
    respondem perguntas diferentes na auditoria (quantos imoveis entraram na fila de visita, e
    quantos sairam), e colapsar os dois num `visita_alternada` perderia a direcao.

    `imovel_id` e' obrigatorio: sem alvo, o evento fica FORA do indice parcial da 014 e nao
    responde nada. Quem chama decide o que fazer sem ele -- ver a nota no `app.py`.
    """
    from psycopg.types.json import Jsonb  # import tardio: so' quem escreve paga

    metadados: dict[str, Any] = {"imovel_id": imovel_id, "origem": origem}
    tipo = EVENTO_VISITA_MARCADA if marcada else EVENTO_VISITA_DESMARCADA
    with transacao(id_usuario=autor) as con:
        con.execute(SQL_REGISTRAR_VISITA, (autor, tipo, Jsonb(metadados)))


def registrar_viabilidade(
    *, autor: int | None, m2: float, aluguel: float, demanda: float, origem: str = "web"
) -> None:
    """Grava `viabilidade.calculada` -- as PREMISSAS da analise, sem alvo.

    SEM ALVO, e isso e' medido, nao esquecido: `ViabilidadeIn` carrega `lat`/`lng` e as
    premissas, e nenhuma das duas telas que chamam a rota conhece `hex_id` ou `imovel_id`.
    Derivar o hexagono da coordenada e' o que a §2.2 recusa ("afirmaria um alvo que o pedido
    nao declarou") e gravar a coordenada e' o que a §4 proibe. Ver a correcao de 16/09 na §2.5.

    O evento vale assim -- e' o OPOSTO da regra da visita, de proposito. La' o alvo e' o
    conteudo inteiro e sem ele nao se grava; aqui o conteudo e' a premissa e o ato e' a
    analise. `demanda` entra porque a DEC-009 a define como premissa explicita do operador,
    nunca prevista, e e' ela que governa o calculo.

    Nenhum numero derivado entra: break-even, payback e aluguel-teto sao SAIDA do motor, e
    `eventos` registra o que a pessoa pediu, nao o que o motor respondeu.
    """
    from psycopg.types.json import Jsonb  # import tardio: so' quem escreve paga

    metadados: dict[str, Any] = {
        "m2": m2,
        "aluguel": aluguel,
        "demanda": demanda,
        "origem": origem,
    }
    with transacao(id_usuario=autor) as con:
        con.execute(
            SQL_REGISTRAR_VIABILIDADE,
            (autor, EVENTO_VIABILIDADE_CALCULADA, Jsonb(metadados)),
        )


def registrar_login(*, autor: int, origem: str = "web") -> None:
    """Grava `login` (§2.1). Destravado pela epic do P19 -- ver as constantes no topo.

    `autor` e' OBRIGATORIO e nao aceita `None`, ao contrario dos outros produtores deste
    modulo: um `login` de autoria nula nao responde a pergunta que o evento existe para
    responder ("quem entrou e quando"), e no momento em que esta funcao e' chamada a senha
    JA' foi verificada -- logo o id e' sempre conhecido. Nao ha' login de sistema.

    `metadados` leva SO' `origem`. A §2.7 e' explicita: "nunca o login nem o e-mail do alvo
    em `metadados`" -- e' PII, e o `id_usuario` do carimbo ja' identifica a pessoa.
    """
    from psycopg.types.json import Jsonb  # import tardio: so' quem escreve paga

    # A frase acima vira CODIGO aqui. `transacao` aceita `id_usuario=None` (acao de sistema,
    # D19), e `_normalizar_autor` devolve `None` sem reclamar -- entao, sem esta guarda, um
    # `login` de autoria nula passaria em silencio e o evento nao responderia a unica
    # pergunta que existe para responder. Afirmacao em docstring sem trava no codigo e' o
    # defeito que esta base ja' pagou caro: ver a nota do `ip` em `005-eventos.md` (P15).
    if autor is None:
        raise ValueError("login sem autor: a senha ja' foi verificada, o id e' sempre conhecido")

    with transacao(id_usuario=autor) as con:
        con.execute(SQL_REGISTRAR_ACESSO, (autor, EVENTO_LOGIN, Jsonb({"origem": origem})))


def registrar_login_recusado(
    *, autor: int | None, usuario_conhecido: bool, origem: str = "web"
) -> None:
    """Grava `login.recusado` (§2.1). Tentativa que NAO entrou.

    `autor` aceita `None` aqui -- ao contrario de `registrar_login`, e a diferenca e' o
    ponto inteiro desta funcao: numa recusa por usuario INEXISTENTE nao ha' id a carimbar,
    e a acao de autoria nula e' informacao legitima (D19). Numa recusa por SENHA ERRADA de
    conta existente, o id vai preenchido -- e e' o que torna a linha util.

    `usuario_conhecido` NAO e' PII e nao vaza nada para quem tenta: ele vive no banco, nunca
    na resposta HTTP, que continua sendo a mesma para os dois casos justamente para nao
    entregar a lista de quem trabalha aqui.

    O QUE ESTA FUNCAO NAO RESOLVE, e precisa estar dito: ela REGISTRA, nao BARRA. Continua
    nao havendo estrangulamento de tentativa em lugar nenhum do piloto (medido), e o
    `regulation:` do Authelia sai no corte. Gravar uma linha por tentativa tambem significa
    que quem martelar o login escreve no banco -- a trilha em arquivo ja' tem a mesma
    propriedade, mas em `eventos` isso e' tabela append-only cujo expurgo e' operacao a
    parte (§8.2 do esquema). Limitar a tentativa e' a decisao 3 da epic, e e' ela que fecha
    os dois assuntos de uma vez.
    """
    from psycopg.types.json import Jsonb  # import tardio: so' quem escreve paga

    metadados = {"origem": origem, "usuario_conhecido": usuario_conhecido}
    with transacao(id_usuario=autor) as con:
        con.execute(SQL_REGISTRAR_ACESSO, (autor, EVENTO_LOGIN_RECUSADO, Jsonb(metadados)))


def registrar_logout(*, autor: int) -> None:
    """Grava `logout` (§2.1). SEM metadados -- o contrato nao preve nenhum.

    `NULL` em `metadados`, e nao `{}`: um objeto vazio afirmaria que ha' payload e ele esta'
    vazio, quando a verdade e' que este evento nao tem payload. A distincao importa para
    quem consulta -- `metadados IS NULL` e `metadados = '{}'` respondem coisas diferentes.
    """
    with transacao(id_usuario=autor) as con:
        con.execute(SQL_REGISTRAR_ACESSO, (autor, EVENTO_LOGOUT, None))
