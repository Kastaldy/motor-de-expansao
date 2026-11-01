"""Sessao propria do piloto: abrir, validar, tocar e revogar (D30 + decisao 2 do P19).

O QUE ESTE MODULO E', E QUEM O CHAMA
------------------------------------
E' a camada de banco da sessao, e NADA MAIS. Nao ha' rota, nao ha' middleware e nao ha'
cookie aqui -- quem chama e' que decide isso. Quem chama, no caminho de requisicao, mora em
`web/server/app.py`: o portao de sessao (`_portao_de_sessao`), as rotas `/api/login`,
`/api/logout` e `/api/verify`, e as duas que trocam CREDENCIAL -- `PATCH /api/me/senha` e o
`redefinir-senha` do painel --, que derrubam as sessoes da pessoa por `_derrubar_sessoes`.
Com a chave abaixo DESLIGADA -- o estado de producao ate' o corte do P19 --, TODOS param na
leitura dela: o unico contato de uma requisicao com este modulo e' `ligada()`, que e' uma
env e nao toca o banco. (Ate' 24/10/2026 as duas de credencial eram a excecao: chamavam
`revogar_todas_do_usuario` com a chave desligada; desde entao recusam antes, com 404.) Fora
da requisicao, o expurgo da origem roda pelo CLI do dono do schema
(`python -m motor_expansao.db expurgar`, cron diario).

A CHAVE DORMENTE, e por que ela e' obrigatoria
----------------------------------------------
`MOTOR_AUTENTICACAO_PROPRIA` nasce DESLIGADA. Nao e' cautela decorativa: a branch precisa
poder ir para producao sem cortar o login de ninguem, e o Authelia continua na frente ate'
a decisao 5 (o que substitui o `forward_auth` do Caddy) ser executada na VPS. Mesmo idioma
do `MOTOR_DATABASE_URL`: ausente ou vazia devolve o sistema ao comportamento anterior, sem
rebuild e sem tocar no compose.

OS NUMEROS SAO DA DECISAO 2 (COPIADOS DO AUTHELIA) E DA EMENDA DE 14/10/2026
---------------------------------------------------------------------------
8h de teto absoluto, 2h de inatividade, e a trava de 5 min no toque. O 8h e o 5 min nao
foram escolhidos: o comentario da configuracao do Authelia registra que mexer nesses
numeros derrubou o login da rede por ~4h em 06/08/2026. A inatividade nasceu 30 min, copiada
do Authelia (`inactivity: 30m`), e passou a 2h pela EMENDA da DEC-067 (D2) decidida por
Vinicius em 14/10/2026 -- teto de 8h e trava de 5 min mantidos. Eles estao aqui como
CONSTANTE e na COLUNA (`expira_em_sessao`) de proposito -- mudar a politica amanha nao exige
migration, e a emenda provou isso: foi uma linha aqui, nenhuma no schema.

POR QUE O TOQUE TEM TRAVA (medido, nao estimado)
------------------------------------------------
A validacao roda em `conexao()`, que abre a transacao `SET TRANSACTION READ ONLY`: o
servidor RECUSA escrita ali dentro. Entao reescrever `ultimo_acesso_em_sessao` nao pega
carona na consulta -- exige uma SEGUNDA transacao (`set_config` do carimbo + `UPDATE` +
`COMMIT`) sobre um pool de 4 conexoes. Com a trava, a coluna so' e' reescrita quando ja'
tem mais de `TRAVA_TOQUE_MIN`, e o pior caso e' alguem sair aos 120 min em vez de ~125.
Decidir "vale escrever?" e' de GRACA: `validar` ja' devolve o `ultimo_acesso`.

O TOKEN NUNCA ENTRA NO BANCO
----------------------------
Guarda-se o SHA-256 dele. Hash rapido e' o certo aqui, e nao uma inconsistencia com o
Argon2 de `senhas.py`: token e' aleatorio de alta entropia (`secrets.token_urlsafe`), entao
nao ha' dicionario a encarecer -- Argon2 por requisicao custaria CPU sem comprar defesa. O
que o hash compra e' que um dump do banco nao permita se passar por uma sessao viva.

RISCO DECLARADO: DUAS REDACOES DA MESMA REGRA
---------------------------------------------
`SQL_VALIDAR` abaixo e' um SUPERCONJUNTO do `rbac.SQL_IDENTIDADE`: mesma lista de SELECT e
mesmos JOINs, mais a juncao com `sessoes` e o filtro de sessao viva. Duas redacoes da mesma
regra nao dao erro -- desencontram em SILENCIO, que e' a licao da DEC-044 ("tres redacoes
da mesma regra... a terceira estava para nascer"). Escolhi NAO mexer no `rbac.py` hoje,
porque ele esta' no caminho de autorizacao VIVO, e este modulo, com a chave DESLIGADA, nao
passa da leitura de `ligada()` em requisicao nenhuma (ver o topo). O preco disso e' uma
trava por teste: `test_db_sessoes.py` compara a lista de SELECT e os JOINs das duas
constantes e falha se uma mudar sem a outra. No dia em que o portao for LIGADO -- o codigo
ja' existe (`_portao_de_sessao`), dormente atras da chave --, a unificacao e' o primeiro
passo, e ai a trava sai junto.

ATUALIZADO (DEC-081, gate de pais): `up.pais` entrou como 4a coluna COMPARTILHADA nas DUAS
constantes (aqui e no `rbac.SQL_IDENTIDADE`), por `LEFT JOIN usuario_paises`. Isto NAO e' a
unificacao prevista acima -- e' a MESMA regra ganhando uma coluna nos DOIS lugares ao mesmo
tempo. O superconjunto e a trava do `test_db_sessoes` seguem valendo: mudaram JUNTAS, de 3
para 4 colunas compartilhadas, que e' exatamente para isso que a trava existe.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
from dataclasses import dataclass

from .postgres import conexao, transacao
from .rbac import Identidade

_LOG = logging.getLogger("motor.db.sessoes")

#: Liga a autenticacao propria. AUSENTE ou vazia = Authelia segue autenticando, e nenhuma
#: requisicao passa da leitura desta chave. Ver "A CHAVE DORMENTE" no topo.
ENV_AUTENTICACAO_PROPRIA = "MOTOR_AUTENTICACAO_PROPRIA"

#: Decisao 2 do P19 (17/09/2026) reproduzia o Authelia (`expiration: 8h`, `inactivity: 30m`).
#: EMENDA da DEC-067 (D2), 14/10/2026, decidida por Vinicius: inatividade 30 min -> 2h; o teto
#: de 8h e a trava de 5 min ficam. O Authelia da VPS tem de ir junto (`inactivity: 2h`, nunca
#: `0`), e essa troca e' MANUAL -- runbook em `docs/repasse_logout_2h.md`.
DURACAO_SESSAO_H = 8
INATIVIDADE_MIN = 120

#: Trava do toque. Ver "POR QUE O TOQUE TEM TRAVA". Precisao de 5 min sobre um limiar de
#: 120 min e' operacionalmente irrelevante; a escrita por requisicao nao e'.
TRAVA_TOQUE_MIN = 5

#: TRAVA DE TENTATIVAS (decisao de 18/09/2026: cinco). Recusas contadas numa JANELA MOVEL --
#: e a janela nao e' detalhe, e' o que impede a trava de virar arma.
#:
#: A contagem so' existe POR CONTA (o `id_usuario` do evento `login.recusado`). Contar por IP
#: e' impossivel no banco enquanto o **P15** estiver aberto, porque o IP nao e' gravado em
#: `eventos`. Consequencia que precisa estar dita: qualquer pessoa consegue trancar a conta
#: de outra digitando o usuario dela cinco vezes com senha errada. Por isso a tranca e'
#: TEMPORARIA e se solta sozinha quando as recusas velhas saem da janela -- bloqueio
#: permanente entregaria um botao de negar acesso a quem souber um nome de usuario.
MAX_TENTATIVAS = 5
JANELA_TENTATIVAS_MIN = 15

#: Bytes de entropia do token. 32 bytes -> 43 caracteres urlsafe.
_BYTES_DO_TOKEN = 32

# --- SQL, em constantes nomeadas ---------------------------------------------------------
# Mesma politica do `eventos.py`/`usuarios.py`: todo SQL do motor fica LOCALIZAVEL, nunca
# interpolado no meio da logica. Quem executa contra o banco real e' o Vinicius, e ele
# precisa ter o que revisar num lugar so' -- e' tambem o que permite ao gate de sintaxe
# offline (pglast) alcancar tudo.

SQL_ABRIR = """
INSERT INTO sessoes (id_usuario, token_hash_sessao, expira_em_sessao,
                     ip_sessao, user_agent_sessao)
VALUES (%s, %s, now() + make_interval(hours => %s), %s, %s)
RETURNING id_sessao, expira_em_sessao
"""

#: Teto do `user_agent` guardado. MESMO valor da trilha da DEC-027 (`agente`, teto 200), e o
#: mesmo raciocinio: o header vem do cliente e pode ter qualquer tamanho. O excesso e' TRUNCADO
#: aqui, nunca recusado -- a 020 explica por que um `CHECK` de tamanho no banco viraria negacao
#: de servico por cabecalho (login que falha porque alguem mandou um `User-Agent` gigante).
TETO_USER_AGENT = 200

#: Quanto tempo a ORIGEM da sessao (`ip_sessao`, `user_agent_sessao`) pode ficar guardada.
#: Decisao do dono em 23/09/2026, fechando o **P15**: TRES MESES. Nao e' numero novo -- e' o
#: mesmo prazo que a DEC-027 ja' pratica para a trilha de acesso em arquivo, que guarda o
#: MESMO dado (IP e user-agent). Dois prazos diferentes para o mesmo dado seriam duas
#: politicas de privacidade no mesmo sistema.
#:
#: A igualdade ACABOU em 20/10/2026: a emenda 2 da DEC-027 tirou o prazo da trilha em arquivo
#: e deixou este como estava (o escopo dela era so' a trilha). Sao duas politicas desde entao,
#: divergencia declarada na propria emenda; os 90 dias daqui seguem valendo pelo P15.
RETENCAO_ORIGEM_DIAS = 90

#: ANONIMIZA, nao apaga. O que tem prazo e' o DADO PESSOAL, nao o registro da sessao: zeradas
#: as duas colunas, a linha continua respondendo "esta pessoa entrou em tal dia e a sessao foi
#: revogada em tal outro" -- auditoria sem PII. Apagar a linha destruiria esse historico e
#: contrariaria o desenho da 018, em que revogar e' `UPDATE` e nunca `DELETE`.
#:
#: `criado_em_sessao` e' o marco, e nao `expira_em_sessao`: o prazo conta da COLETA do dado.
#:
#: O `WHERE` exige pelo menos uma das duas preenchidas para a operacao ser IDEMPOTENTE -- sem
#: isso, cada execucao reescreveria todas as linhas velhas e o `rowcount` mentiria sobre
#: quanto ainda havia para expurgar.
SQL_EXPURGAR_ORIGEM = """
UPDATE sessoes
SET ip_sessao = NULL, user_agent_sessao = NULL
WHERE criado_em_sessao < now() - make_interval(days => %s)
  AND (ip_sessao IS NOT NULL OR user_agent_sessao IS NOT NULL)
"""

#: Quantas linhas AINDA guardam origem alem do prazo. Serve ao `--simular` e ao operador que
#: quer saber se o expurgo esta' em dia sem escrever nada.
SQL_CONTAR_ORIGEM_VENCIDA = """
SELECT count(*) FROM sessoes
WHERE criado_em_sessao < now() - make_interval(days => %s)
  AND (ip_sessao IS NOT NULL OR user_agent_sessao IS NOT NULL)
"""

# SUPERCONJUNTO do `rbac.SQL_IDENTIDADE` -- ver "RISCO DECLARADO" no topo.
#
# Os tres filtros de sessao viva, e por que cada um existe:
#   * `revogada_em_sessao IS NULL` -> logout, troca de senha e expulsao pelo admin;
#   * `expira_em_sessao > now()`   -> o teto ABSOLUTO de 8h;
#   * `ultimo_acesso_em_sessao > now() - inatividade` -> as 2h paradas (`INATIVIDADE_MIN`).
# O `u.ativo` fica pelo mesmo motivo do D9/D23: desativar alguem tem de negar na requisicao
# SEGUINTE, sem depender de revogar as sessoes dele uma a uma.
#
# `make_interval(mins => %s)` e nao f-string: o SQL deste repo nao se monta por concatenacao
# (politica do `postgres.py`), e um intervalo interpolado seria a primeira excecao.
#
# `deve_trocar_senha_usuario` esteve nesta projecao entre 18/09 e 25/09/2026, quando a troca era
# BLOQUEIO e o portao de sessao precisava do dado a cada requisicao. O dono reverteu para
# RECOMENDADA em 25/09, o unico leitor sumiu, e a coluna saiu daqui: dado lido por requisicao sem
# consumidor e' custo por requisicao. Quem pergunta pelo estado da senha e' `/api/me`, uma vez por
# carga da SPA, por consulta propria (`_estado_da_minha_senha`). A COLUNA no banco continua -- e'
# a projecao desta consulta que nao a carrega mais.
SQL_VALIDAR = """
SELECT u.id_usuario, p.nome_perfil, pe.chave, up.pais,
       u.login_usuario, s.id_sessao, s.ultimo_acesso_em_sessao
FROM sessoes s
JOIN usuarios u ON u.id_usuario = s.id_usuario
JOIN perfis p ON p.id_perfil = u.id_perfil
LEFT JOIN perfil_permissoes pp ON pp.id_perfil = u.id_perfil
LEFT JOIN permissoes pe ON pe.id_permissao = pp.id_permissao
LEFT JOIN usuario_paises up ON up.id_usuario = u.id_usuario
WHERE s.token_hash_sessao = %s
  AND s.revogada_em_sessao IS NULL
  AND s.expira_em_sessao > now()
  AND s.ultimo_acesso_em_sessao > now() - make_interval(mins => %s)
  AND u.ativo
"""

# A TRAVA VIVE NO `WHERE`, e isso nao e' estilo: assim o UPDATE e' idempotente e sem corrida
# -- duas requisicoes simultaneas da mesma sessao nao se atropelam, porque a segunda nao
# encontra linha para atualizar. Decidir no Python custaria um `if` que duas threads podem
# atravessar juntas.
SQL_TOCAR = """
UPDATE sessoes SET ultimo_acesso_em_sessao = now()
WHERE id_sessao = %s
  AND revogada_em_sessao IS NULL
  AND ultimo_acesso_em_sessao < now() - make_interval(mins => %s)
"""

# Revogar e' UPDATE, nunca DELETE: "esta sessao foi encerrada, e quando" e' auditoria, e
# apagar a linha responderia "nunca existiu". E' tambem o privilegio que o `app` tem (D20/D30
# deram `SELECT, INSERT, UPDATE` e recusaram `DELETE`), entao um DELETE aqui seria negado
# pelo banco -- a politica esta' imposta, nao apenas escrita.
SQL_REVOGAR = """
UPDATE sessoes SET revogada_em_sessao = now()
WHERE token_hash_sessao = %s AND revogada_em_sessao IS NULL
"""

# Troca de senha e desligamento derrubam TODAS as sessoes abertas da pessoa. E' a razao pela
# qual a D30 escolheu tabela em vez de cookie assinado: sem estado no servidor, isto nao
# existe.
SQL_REVOGAR_TODAS = """
UPDATE sessoes SET revogada_em_sessao = now()
WHERE id_usuario = %s AND revogada_em_sessao IS NULL
"""


@dataclass(frozen=True)
class SessaoAberta:
    """O que o chamador precisa para montar o cookie. O `token` NAO se registra em log."""

    token: str
    id_sessao: int
    expira_em: object


@dataclass(frozen=True)
class SessaoValida:
    """Quem e' (reusando o `Identidade` do RBAC) + o que o toque precisa decidir."""

    identidade: Identidade
    id_sessao: int
    ultimo_acesso: object


def ligada() -> bool:
    """A autenticacao propria esta' ligada neste deploy?

    Enquanto for `False`, o Authelia autentica e este modulo nao entra em requisicao
    nenhuma. Quem le' isto no caminho quente deve chamar UMA vez por requisicao.
    """
    bruto = os.environ.get(ENV_AUTENTICACAO_PROPRIA, "")
    return bruto.strip().lower() in ("1", "true", "sim", "yes")


def novo_token() -> str:
    """Um token de sessao. `secrets`, nunca `random`: o segundo e' previsivel por desenho."""
    return secrets.token_urlsafe(_BYTES_DO_TOKEN)


def hash_do_token(token: str) -> str:
    """O que vai para o banco. Ver "O TOKEN NUNCA ENTRA NO BANCO" no topo."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def abrir(
    *, id_usuario: int, ip: str | None = None, user_agent: str | None = None
) -> SessaoAberta:
    """Cunha o token, grava a sessao e devolve o token EM CLARO -- uma unica vez.

    O token em claro existe so' aqui e no cookie: o banco guarda o hash, e nao ha' caminho
    de volta. Perder o retorno desta funcao e' perder a sessao (o que e' a propriedade
    desejada, nao um defeito).

    O carimbo de autor (§3.7) vale SEM excecao: quando esta funcao e' chamada, a senha ja'
    foi verificada, entao `id_usuario` e' conhecido -- nao ha' "acao de sistema" aqui.

    `ip` e `user_agent` (020) respondem "de onde esta sessao veio", que e' a pergunta do
    `BLK-SEC-03-FU2` quando se quer saber se a sessao e' da pessoa ou de quem roubou o cookie
    dela. Os DOIS sao opcionais e nulos por default: sessao sem origem conhecida e' estado
    legitimo, e falhar aqui por falta de header derrubaria o login por um dado acessorio.

    **O `ip` TEM DE CHEGAR JA' RESOLVIDO** -- este modulo nao le' header nenhum. Quem resolve
    e' `web/server/app.py::_ip_real_do_xff`, que pega o ULTIMO token do `X-Forwarded-For` (o
    Caddy anexa o peer real ao fim; os da esquerda sao forjaveis, e usar `[0]` foi
    vulnerabilidade real no pentest de 19/08/2026). Reimplementar a resolucao aqui seria uma
    segunda redacao da mesma regra -- e a segunda e' a que esquece a licao.

    **O `ip` e' dado pessoal, e tem PRAZO desde 23/09/2026**: o P15 fechou a retencao em
    `RETENCAO_ORIGEM_DIAS` (90 dias), aplicada pelo expurgo diario (`SQL_EXPURGAR_ORIGEM`), que
    ANONIMIZA as duas colunas em vez de apagar a linha -- revogar sessao e' `UPDATE`, nunca
    `DELETE`, entao nenhuma linha sai daqui sozinha. O que segue em aberto no P15 e' a BASE
    LEGAL, que e' decisao juridica e nao tecnica. Ver a 020 e `docs/banco_deploy.md` §9.1.
    """
    token = novo_token()
    agente = (user_agent or "").strip()[:TETO_USER_AGENT] or None
    with transacao(id_usuario=id_usuario) as con:
        linha = con.execute(
            SQL_ABRIR, (id_usuario, hash_do_token(token), DURACAO_SESSAO_H, ip, agente)
        ).fetchone()
    # `RETURNING` sempre devolve linha num INSERT que nao levantou; se nao devolveu, algo
    # muito errado aconteceu e engolir isso daria uma sessao sem id para revogar depois.
    if linha is None:  # pragma: no cover - defesa de invariante
        raise RuntimeError("INSERT em sessoes nao devolveu RETURNING -- sessao sem id")
    return SessaoAberta(token=token, id_sessao=linha[0], expira_em=linha[1])


def validar(token: str) -> SessaoValida | None:
    """`None` = sem sessao valida. UMA consulta, na mesma ida que a autorizacao ja' fazia.

    Os tres motivos de negar -- revogada, vencida por teto, vencida por inatividade -- caem
    no MESMO `None` de proposito: a resposta ao cliente e' 401 nos tres casos, e distinguir
    aqui convidaria a contar ao visitante qual foi. Quem precisa do detalhe le' a linha.
    """
    if not token:
        return None
    with conexao() as con:
        linhas = con.execute(SQL_VALIDAR, (hash_do_token(token), INATIVIDADE_MIN)).fetchall()
    if not linhas:
        return None

    id_usuario, perfil, _chave, _pais, login, id_sessao, ultimo_acesso = linhas[0]
    # `chave` vem NULL quando o perfil nao tem permissao nenhuma (LEFT JOIN): a pessoa
    # existe e nao pode nada. Distinto de nao existir, e o chamador precisa distinguir.
    chaves = frozenset(linha[2] for linha in linhas if linha[2] is not None)
    # `up.pais` (4a coluna, LEFT JOIN usuario_paises): os paises da pessoa, para o gate da
    # DEC-081. Vazio quando ela nao tem pais -> o gate NEGA (fail-closed).
    paises = frozenset(linha[3] for linha in linhas if linha[3] is not None)
    return SessaoValida(
        # `login_usuario` vem do banco, e nao sintetizado do id. Custa UMA coluna no caminho
        # quente e evita um campo chamado `login` carregando `id:7` -- que e' afirmacao falsa
        # esperando aparecer no primeiro log ou tela que o exiba. E' a mesma razao pela qual
        # o D23 separou os tres papeis: `login_usuario` identifica, `email` contata,
        # `nome_usuario` exibe.
        identidade=Identidade(
            id_usuario=id_usuario,
            login=login,
            perfil=perfil,
            permissoes=chaves,
            paises=paises,
        ),
        id_sessao=id_sessao,
        ultimo_acesso=ultimo_acesso,
    )


def tocar(*, id_sessao: int, id_usuario: int) -> bool:
    """Atualiza `ultimo_acesso_em_sessao` SE ja' passou da trava. `True` = escreveu.

    Devolve se escreveu para o chamador poder medir (e para o teste poder provar a trava).
    A decisao de chamar ou nao e' do chamador: `validar` ja' devolveu o `ultimo_acesso`,
    entao ele consegue evitar ate' a ida ao banco -- e a trava no `WHERE` e' a segunda
    defesa, para o caso de duas requisicoes decidirem ao mesmo tempo.
    """
    with transacao(id_usuario=id_usuario) as con:
        cur = con.execute(SQL_TOCAR, (id_sessao, TRAVA_TOQUE_MIN))
        return bool(getattr(cur, "rowcount", 0))


def revogar(*, token: str, id_usuario: int) -> bool:
    """Logout. `True` = havia sessao viva com este token."""
    with transacao(id_usuario=id_usuario) as con:
        cur = con.execute(SQL_REVOGAR, (hash_do_token(token),))
        derrubou = bool(getattr(cur, "rowcount", 0))
    if not derrubou:
        # Nao e' erro: logout de sessao ja' vencida ou ja' revogada e' idempotente. Fica em
        # `debug` porque o caso normal (clicar em sair duas vezes) passaria por aqui.
        _LOG.debug("logout sem sessao viva correspondente")
    return derrubou


def revogar_todas_do_usuario(*, id_usuario: int, autor: int | None = None) -> int:
    """Derruba TODAS as sessoes abertas da pessoa. Devolve quantas caíram.

    Chamado na troca de senha e no desligamento. `autor` separa QUEM AGIU de QUEM SOFREU:
    na troca da propria senha os dois coincidem, mas um admin redefinindo a senha de outra
    pessoa e' ato DELE -- e o carimbo da §3.7 tem de dizer isso, senao a auditoria atribui
    a acao a' vitima.
    """
    with transacao(id_usuario=id_usuario if autor is None else autor) as con:
        cur = con.execute(SQL_REVOGAR_TODAS, (id_usuario,))
        return int(getattr(cur, "rowcount", 0) or 0)
