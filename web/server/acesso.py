"""Controle TEMPORARIO de acesso por aba do piloto web (pedido do Felipe, 2026-08-13).

O Authelia AUTENTICA (quem entra no piloto); este modulo AUTORIZA (que aba cada
usuario pode usar). O usuario chega no header `Remote-User`, que o Caddy ja repassa
atras do Authelia — nao ha sessao propria nem banco. A solucao definitiva e' o banco
de identidade (plano de 2026-08-07); este modulo existe para morrer quando ele chegar.

O mapa `usuario -> [abas]` vive num JSON EDITAVEL EM PRODUCAO, no volume `:rw` do
cadastro (DEC-023) — trocar o acesso de alguem nao exige rebuild nem deploy, so'
editar o arquivo (relido a cada mudanca de mtime).

Regras de degradacao (BLK-SEC-05 — fail-CLOSED nas abas sensiveis em PRODUCAO):
  - Controle indisponivel (SEM arquivo, JSON invalido, mount sumiu):
      * em PRODUCAO  -> NEGA as abas SENSIVEIS (`ABAS_SENSIVEIS`: financeiro da rede +
        PII de franqueado + a rota de ESCRITA); mantem as nao-sensiveis (`mapa`,
        `oportunidades`) para nao trancar 100% o piloto por um typo. + log de ERRO.
      * em DEV/local -> fail-OPEN historico (todas as abas), para nao atrapalhar o dev.
    O que e' "producao": `_fail_closed_ativo()` (env `MOTOR_CADASTRO_DIR` setado pelo
    compose, ou override explicito `MOTOR_ACESSO_FAIL_CLOSED`).
  - Arquivo ok e usuario fora do mapa       -> entrada "*" se existir; senao NENHUMA.

READ-ONLY sobre o M1: este modulo so' le um JSON de configuracao; nao toca dado.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor_expansao.perfil import Perfil

_LOG = logging.getLogger("piloto.acesso")

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parents[2]

# Valores brutos de aba — identificadores SEM acento (regra do CLAUDE.md §2). A SPA
# usa exatamente estes nomes em `web/src/lib/acesso.ts`; mudou aqui, muda la' junto.
ABAS_VALIDAS = frozenset({"executiva", "imobiliaria", "mapa", "oportunidades", "viabilidade"})

# Abas com dado SENSIVEL (financeiro da rede, PII de franqueado/consultor, ESCRITA) —
# negadas no fail-CLOSED quando o controle cai em producao (BLK-SEC-05). `executiva`
# cobre `/api/rede/` (carteira + PUT cadastro) e `/api/executiva/`; `viabilidade` cobre
# `/api/simulador/` e `/api/faixa-alunos`; `imobiliaria` cobre o DOSSIE do coletor
# (`/api/oportunidades/{id}/dossie`), que carrega contato de corretor. `mapa` e
# `oportunidades` (analitico agregado) seguem no fail-closed.
#
# Consequencia deliberada: com o controle caido em producao, ninguem baixa dossie —
# mas a LISTA agregada continua servindo os pins do Mapa Territorial, porque quem
# perde `imobiliaria` no fail-closed ainda tem `mapa` (decisao do Felipe, 2026-08-24:
# "todos os usuarios com acesso ao mapa tambem tem acesso a esses imoveis").
ABAS_SENSIVEIS = frozenset({"executiva", "imobiliaria", "viabilidade"})

# Que abas LIBERAM cada rota (basta ter UMA delas). Casamento por PREFIXO do path.
# Rota sem regra = livre para qualquer usuario autenticado (health, catalogos, /api/me);
# o teste de cobertura em tests/unit/test_piloto_web_acesso.py obriga toda rota nova
# do app a aparecer aqui OU na lista explicita de rotas livres.
#
# A aba "mapa" cobre tambem o modo de PONTO (tela 'ponto' = Explorar + ficha por cima).
# `/api/viabilidade` aceita mapa OU viabilidade por HISTORICO: o BlocoViabilidadePonto (a
# secao "Fecha a conta?" da ficha de ponto) chamava a mesma rota que a tela de
# Viabilidade. Ele SAIU em 2026-10-14 (a ficha ganhou o botao "Simulador", que leva a
# tela de Viabilidade), entao hoje so' a tela de Viabilidade chama esta rota. A regra
# ficou INALTERADA de proposito: estreitar para {viabilidade} e' mudanca de permissao, e
# pede decisao propria (e o ajuste de tests/unit/test_piloto_web_acesso.py e de
# docs/plano_multipais.md). `/api/relatorio/pontual` aceita mapa OU viabilidade porque quem
# a chama e' a tela de Viabilidade E o botao "Estudo" da ficha de ponto (aba "mapa"), este
# no modo so'-estudo, sem dado financeiro.
#
# `/api/relatorio/comparacao` fica so' em "mapa", e NAO em "viabilidade": o deck compara
# contexto de entorno e nao carrega DRE, payback nem teto de aluguel — por DEC-009 a
# viabilidade e' premissa digitada sobre um imovel concreto, e a comparacao nao a tem.
# Quem dispara sao as duas telas cobertas por "mapa" (comparacao de hexagonos no Explorar
# e comparacao de pontos no modo de imovel).
REGRAS_DE_ACESSO: tuple[tuple[str, frozenset[str]], ...] = (
    ("/api/rede/", frozenset({"executiva"})),
    ("/api/executiva/", frozenset({"executiva"})),
    ("/api/geocode", frozenset({"mapa"})),
    ("/api/resolver-ponto", frozenset({"mapa"})),
    # Por PREFIXO, cobre tambem `POST /api/ponto/geometria` (a area desenhada, DEC-071):
    # e' a mesma ficha com o poligono no lugar do raio, entao o gate e' o mesmo.
    ("/api/ponto", frozenset({"mapa"})),
    ("/api/cobertura/", frozenset({"mapa"})),
    ("/api/relatorio/comparacao", frozenset({"mapa"})),
    ("/api/relatorio/municipal", frozenset({"mapa"})),
    ("/api/relatorio/pontual", frozenset({"mapa", "viabilidade"})),
    ("/api/viabilidade", frozenset({"mapa", "viabilidade"})),
    ("/api/faixa-alunos", frozenset({"viabilidade"})),
    # Aluguel de referencia (DEC-080): semente do aluguel na mesma tela, mesmo gate.
    ("/api/aluguel-referencia", frozenset({"viabilidade"})),
    # Viabilidade v2 (DEC-078 ampliada): estado e sugestao da demanda. Mesmo gate da faixa
    # de alunos, que e' a outra fonte da semente da demanda na mesma tela.
    ("/api/demanda-v2", frozenset({"viabilidade"})),
    ("/api/simulador/", frozenset({"viabilidade"})),
    ("/api/uf/", frozenset({"mapa", "oportunidades"})),
    ("/api/municipio/", frozenset({"mapa", "oportunidades"})),
    ("/api/municipios/", frozenset({"mapa", "oportunidades"})),
    # Coordenada -> municipio (a unidade escolhida leva o cabecalho a' cidade dela,
    # 21/10/2026). MESMO gate de `/api/municipios/`: devolve so' o NOME de um municipio,
    # o mesmo dado que a lista ja' entrega a quem ve o mapa. Sem a barra no prefixo, nao
    # casa por acidente com `/api/municipio/` nem com `/api/municipios/`.
    ("/api/municipio-do-ponto", frozenset({"mapa", "oportunidades"})),
    ("/api/estados", frozenset({"oportunidades"})),
    # Ranking NACIONAL por hexagono (DEC-044). MESMO gate de `/api/estados`: e' a
    # outra leitura do Modo 3 ("ver as melhores oportunidades"), sobre a mesma
    # cascata e o mesmo dado -- so' muda a unidade (hexagono no lugar de estado) e
    # a ordem dos passos (ranqueia o pais, depois filtra). Dar-lhe um gate mais
    # FROUXO abriria por uma porta o que a outra fecha; um mais DURO esconderia do
    # operador de `oportunidades` a versao boa da propria tela dele.
    ("/api/hexagonos", frozenset({"oportunidades"})),
    # Camada imobiliaria (aba PROPRIA `imobiliaria` desde 2026-08-24; ate' entao a tela
    # reusava o gate de `oportunidades`, o que impedia restringir os imoveis sem tirar o
    # funil de expansao de quem o usa). O DOSSIE (PDF do coletor, carrega contato de
    # corretor) fica SO' na aba imobiliaria; a LISTA (agregado sem PII) tambem serve a
    # camada de pins e a secao da ficha do hexagono no Mapa Territorial, entao "mapa" a
    # libera. O prefixo com barra vem ANTES: o casamento e' first-match por startswith.
    ("/api/oportunidades/", frozenset({"imobiliaria"})),
    ("/api/oportunidades", frozenset({"mapa", "imobiliaria"})),
    # Eventos de tela da camada imobiliaria (rotas no-op cujo VALOR e' a linha que o
    # middleware da trilha grava — molde do `/api/ciencia-confidencialidade`). Aceita
    # "mapa" porque o pin do Mapa Territorial tambem abre ficha de imovel.
    ("/api/imobiliaria/evento/", frozenset({"mapa", "imobiliaria"})),
    # Foto da UNIDADE concorrente, desenhada no balao do pino do Mapa Territorial.
    # MESMO gate de `/api/municipio/`, que e' a rota que serve o payload de pins onde o
    # nome do arquivo aparece: quem recebe a lista de pins ja' recebeu o nome da foto, e
    # negar a imagem depois de entregar o nome nao protegeria nada — so' deixaria o balao
    # quebrado para o operador de `oportunidades`. Mais FROUXO tambem nao: a foto e' base
    # servida, e nao bundle do produto, entao ela nao pode vazar para quem nao ve o mapa.
    ("/api/foto-concorrente/", frozenset({"mapa", "oportunidades"})),
    # A MESMA foto, emoldurada para virar icone do pino. Gate igual ao da foto crua de
    # proposito: e' o mesmo arquivo, servido em outra roupa — dar-lhe regra diferente
    # deixaria uma das duas portas mais larga que a outra sobre o mesmo dado.
    ("/api/pin-concorrente/", frozenset({"mapa", "oportunidades"})),
)


# ============================================================================
# Gate de PAÍS (Bloco C / DEC-047) — "esta INSTÂNCIA oferece esta rota de verdade?"
#
# É uma pergunta DIFERENTE da que `REGRAS_DE_ACESSO` responde. Aquela e' sobre o
# USUÁRIO ("este Remote-User pode?"), casada por UNIÃO (basta UMA aba da lista) e
# fail-open por desenho — sem ela, o piloto trancaria por completo se o JSON de
# cadastro sumisse. Esta e' sobre a INSTÂNCIA ("este deploy tem a superfície para
# responder isto?"), casada por CONJUNÇÃO (a superfície exigida tem de estar em
# `perfil.superficies`) e fail-CLOSED por desenho — sem ela, uma instância que nunca
# declarou `oportunidades` serviria o funil inteiro para qualquer usuário com "mapa".
#
# Herdar `REGRAS_DE_ACESSO` para isto NÃO fecha nada, nas duas direções: `/api/uf/`
# aceita `{"mapa", "oportunidades"}` (união), e a Argentina TEM "mapa" — passaria por
# uma tabela que so' verificasse a interseção. O gate de país precisa da SUA PRÓPRIA
# tabela, com sua própria semântica. Precedente já no repo: a DEC-037 deu à aba
# `imobiliaria` um gate próprio em vez de esticar a tabela de união — mesmo
# movimento, um nível acima.
#
# `ponto` e `municipal` NÃO SÃO ABAS (moram dentro de `mapa` — ver `ABA_DA_TELA` em
# `web/src/lib/acesso.ts`), então não pertencem a este dicionário: elas dependem de
# um recurso que `superficies` não modela (a malha adm2), e por isso têm tabela e
# checagem PRÓPRIAS logo abaixo (`ROTAS_QUE_EXIGEM_MALHA_MUNICIPAL`).
SUPERFICIE_DA_ROTA: tuple[tuple[str, frozenset[str]], ...] = (
    ("/api/rede/", frozenset({"executiva"})),
    ("/api/executiva/", frozenset({"executiva"})),
    ("/api/geocode", frozenset({"mapa"})),
    ("/api/cobertura/", frozenset({"mapa"})),
    ("/api/relatorio/comparacao", frozenset({"mapa"})),
    ("/api/viabilidade", frozenset({"viabilidade"})),
    ("/api/faixa-alunos", frozenset({"viabilidade"})),
    # Aluguel de referencia (DEC-080): semente do aluguel na mesma tela, mesmo gate.
    ("/api/aluguel-referencia", frozenset({"viabilidade"})),
    # `/api/demanda-v2` (DEC-078 ampliada) NAO entra aqui: ela e' rota de MALHA, com
    # checagem propria em `ROTAS_QUE_EXIGEM_MALHA_MUNICIPAL` (e o gate do usuario e' o da
    # viabilidade em `REGRAS_DE_ACESSO`).
    ("/api/simulador/", frozenset({"viabilidade"})),
    ("/api/uf/", frozenset({"mapa"})),
    ("/api/municipio/", frozenset({"mapa"})),
    ("/api/municipios/", frozenset({"mapa"})),
    # As DUAS leituras do Modo 3 (DEC-044) — ranking nacional por estado e por
    # hexágono — são o FUNIL, servidas fora de qualquer UF escolhida. Diferente de
    # `/api/uf/`: aqui não há "mapa" alternativo, porque não há mapa de uma UF por
    # trás — é a mesma pergunta de `oportunidades`, so' que na escala do país.
    ("/api/estados", frozenset({"oportunidades"})),
    ("/api/hexagonos", frozenset({"oportunidades"})),
    # O prefixo com barra vem ANTES, mesmo motivo de `REGRAS_DE_ACESSO`: o dossiê
    # (PII de corretor) exige `imobiliaria`; a LISTA agregada, sem PII, alimenta os
    # pins e a ficha do hexágono do Mapa Territorial e por isso basta "mapa".
    ("/api/oportunidades/", frozenset({"imobiliaria"})),
    ("/api/oportunidades", frozenset({"mapa"})),
    ("/api/imobiliaria/evento/", frozenset({"mapa"})),
    ("/api/foto-concorrente/", frozenset({"mapa"})),
    ("/api/pin-concorrente/", frozenset({"mapa"})),
)

# `/api/ponto`, `/api/resolver-ponto`, `/api/municipio-do-ponto`,
# `/api/relatorio/municipal` e `/api/relatorio/pontual` NÃO estão em
# `SUPERFICIE_DA_ROTA`: elas resolvem
# coordenada -> município via a malha adm2 (`api/service._carregar_malha`), um
# recurso que `perfil.superficies` não modela (ver a nota do campo em
# `motor_expansao.perfil.Perfil.malha_municipal_disponivel`). Sem a malha, o
# resultado de HOJE não é degradação graciosa: `_carregar_malha` levanta 500
# ("Malha ... ausente ou vazia") na primeira coordenada, e `/api/relatorio/pontual`
# e `/api/ponto` propagam esse 500 sem capturar — a diferença exata entre "a
# ferramenta quebrou" e "esta instância não tem isto ainda" que este gate existe
# para fazer. `/api/viabilidade` e `/api/faixa-alunos` ficam DE FORA desta lista de
# proposito: o catchment ali é CONTEXTO opcional (try/except -> None), nunca
# propaga a falha — não há nada para este gate proteger.
ROTAS_QUE_EXIGEM_MALHA_MUNICIPAL: frozenset[str] = frozenset(
    {
        "/api/ponto",
        "/api/resolver-ponto",
        # Coordenada -> municipio pela mesma malha (`_carregar_malha`): sem ela, 500 na
        # primeira unidade escolhida -- o mesmo motivo das outras quatro.
        "/api/municipio-do-ponto",
        "/api/relatorio/municipal",
        "/api/relatorio/pontual",
        # A v2 le a malha de setores na isocrona (DEC-078 ampliada): sem malha, 404 honesto.
        "/api/demanda-v2",
    }
)


def superficie_necessaria(path: str) -> frozenset[str] | None:
    """Superfície(s) que esta rota exige da INSTÂNCIA; `None` = sem exigência própria."""
    for prefixo, superficies in SUPERFICIE_DA_ROTA:
        if path.startswith(prefixo):
            return superficies
    return None


def rota_exige_malha_municipal(path: str) -> bool:
    return any(path.startswith(prefixo) for prefixo in ROTAS_QUE_EXIGEM_MALHA_MUNICIPAL)


def motivo_bloqueio_pais(path: str, perfil: Perfil) -> str | None:
    """`None` = a INSTÂNCIA oferece esta rota; string = detail do 404 que a nega.

    404, nunca 403: a pergunta aqui não é "este usuário pode" (isso é
    `motivo_bloqueio`, que devolve 403) — é "este deploy tem isto de verdade". Fingir
    que a rota existe e negar por permissão prometeria uma superfície que a instância
    não tem; 404 é a resposta honesta, e é o que permite ao front simplesmente
    ESCONDER o que não veio na lista, em vez de mostrar um botão que sempre falha.
    """
    exigidas = superficie_necessaria(path)
    if exigidas is not None and not exigidas.issubset(perfil.superficies):
        faltando = sorted(exigidas - set(perfil.superficies))
        nomes = ", ".join(repr(f) for f in faltando)
        return (
            f"Esta instância ({perfil.nome}) não oferece "
            f"{'a superfície' if len(faltando) == 1 else 'as superfícies'} {nomes}."
        )
    if rota_exige_malha_municipal(path) and not perfil.malha_municipal_disponivel:
        return (
            f"Esta instância ({perfil.nome}) ainda não tem a malha municipal "
            "necessária para esta função."
        )
    return None

# Rotas /api/* deliberadamente livres (qualquer usuario autenticado):
#   /api/health      — healthcheck do container (curl interno, sem Remote-User)
#   /api/ufs         — catalogo de UFs, carregado pelo App antes de saber a tela
#   /api/metodologia — manual do funil, conteudo explicativo sem dado sensivel
#   /api/me          — e' a rota que DIZ a SPA o que esconder
# `/api/ciencia-confidencialidade` e' livre de proposito: TODO usuario autenticado ve o
# pop-up de entrada e o clique no OK precisa virar linha da trilha (DEC-027) — restringir
# por aba deixaria usuarios sem aba nenhuma fora do registro de ciencia.
#
# `/api/me/senha` (D26) e' livre pelo mesmo tipo de razao, e vale dizer por que ela NAO tem
# capacidade: trocar a propria senha e' a unica coisa que so' a propria pessoa deveria poder
# fazer, e exigir capacidade para isso obrigaria a promover todo mundo a Growth para depois
# rebaixar. Ela tambem fica FORA do `PREFIXO_ROTAS_ACESSOS` de proposito: sob `/api/acessos/`
# ela levaria 404 seco de quem nao administra o painel, e definir a propria senha nao e' ato
# de administracao.
#
# A ausencia de gate nao afrouxa nada, porque o ALVO NAO E' PARAMETRO: a rota resolve a
# identidade de quem pediu e `trocar_a_propria_senha` so' aceita `autor`, escrevendo so' na
# linha dele. Nao existe forma de chamar isso para outra pessoa -- nem por id, nem por login.
ROTAS_LIVRES = frozenset(
    {
        "/api/health",
        "/api/ufs",
        "/api/metodologia",
        "/api/me",
        "/api/me/senha",
        "/api/ciencia-confidencialidade",
        # P19/D30: entrar e sair. Livres para os portoes de ABA e de PAIS de proposito --
        # aqueles decidem o que a pessoa PODE, e aqui ela ainda nao e' ninguem. Quem decide
        # se estas duas atendem e' o portao de SESSAO (ver `ROTAS_PUBLICAS_SEM_SESSAO`), que
        # e' camada propria e separada. Sem esta declaracao, o
        # `test_toda_rota_do_app_tem_regra_ou_e_livre_declarada` reprova -- e reprova com
        # razao: rota `/api/*` sem decisao e' decisao que faltou tomar.
        "/api/login",
        "/api/logout",
        # P19/D4 da DEC-067: o `forward_auth` do Caddy bate AQUI a cada requisicao protegida.
        # Livre dos portoes de ABA e de PAIS pela mesma razao das duas de cima -- e uma a mais,
        # que e' a que importa: quem pergunta e' a BORDA, antes de existir identidade nenhuma.
        # Um gate de aba sobre ela transformaria "esta pessoa nao ve a aba Executiva" em "a
        # borda nao consegue autenticar ninguem", e o piloto inteiro cairia com 403.
        "/api/verify",
        # P19/DEC-081: o `forward_auth` do APEX bate aqui. Igual a `/api/verify`, mas
        # PAIS-NEUTRO (so' valida sessao, nunca o pais) -- o apex e' o seletor e tem de admitir
        # qualquer autenticado, inclusive quem nao tem o pais do processo que serve o apex.
        "/api/verify-sessao",
    }
)

# --- Troca de senha PENDENTE: por que NAO ha' gate aqui -------------------------
# Entre 18/09/2026 e 25/09/2026 este arquivo teve `ROTAS_COM_TROCA_PENDENTE` e
# `bloqueio_por_troca_pendente`: quem devia a troca levava 403 em tudo fora de cinco rotas.
# O dono reverteu em 25/09 -- a troca e' RECOMENDADA, nao obrigatoria.
#
# O registro fica porque a ausencia de gate aqui e' ESCOLHA, e nao lacuna: sem esta nota, a
# proxima leitura de `deve_trocar_senha_usuario` neste arquivo parece um controle que alguem
# esqueceu de escrever. Quem convida para a troca e' `/api/me` (`_estado_da_minha_senha`), que
# devolve `{"deve_trocar", "propria"}` para a SPA abrir o modal -- e o modal tem "Agora nao".
#
# Se um dia a obrigatoriedade voltar, o lugar e' este arquivo com lista PROPRIA (nunca reusando
# `ROTAS_LIVRES`, que e' mais larga e serviria `/api/ufs` e `/api/metodologia` a quem ainda esta'
# na senha temporaria -- licao da DEC-037), e as rotas de saida sao obrigatorias: `/api/me`,
# `/api/me/senha`, `/api/login`, `/api/logout`, `/api/health`, mais a SPA e os estaticos. Sem
# elas o bloqueio vira armadilha e destravar cada pessoa exige ir ao banco.

# --- Portao de SESSAO (epic do P19, decisao 1 = D30) ----------------------------
# Camada NOVA e separada das outras tres. As de cima respondem "o que esta pessoa pode?";
# esta responde "ha' alguem aqui?". Enquanto o Authelia autentica, ela esta' DORMENTE --
# `sessoes.ligada()` (env `MOTOR_AUTENTICACAO_PROPRIA`) manda, e sem ela nada neste bloco
# entra em requisicao nenhuma.

#: O que atende SEM sessao depois do corte. Curto de proposito, e cada item tem razao:
#:   * `/api/login`  -- e' por onde se obtem a sessao; exigi-la aqui e' impossivel;
#:   * `/api/logout` -- idempotente, e recusar logout a quem perdeu a sessao e' absurdo;
#:   * `/api/health` -- emudecido por decisao de pentest e usado pelo healthcheck do
#:     container, que nao tem cookie nenhum. Amarrar os dois faria o Docker reiniciar o
#:     `web` por falta de login.
#:   * `/api/verify` -- e' o `forward_auth` do D4 (DEC-067). Exigir sessao dela seria
#:     circular: o portao a 401 antes de ela poder DIZER se ha' sessao, e a borda leria esse
#:     401 como "ninguem esta' autenticado" para TODA requisicao do piloto. Ela nao e'
#:     publica por descuido -- ela e' a rota que RESPONDE a pergunta, e por isso valida o
#:     cookie por conta propria, dentro dela.
#: NAO entra aqui `/api/me`: ela e' a PRIMEIRA chamada da SPA e passa a exigir sessao --
#: e' ela que responde "quem sou eu" DEPOIS do login (escopo do P19, §3).
#:
#: ESTA LISTA TEM UMA SEGUNDA REDACAO, e ela e' declarada de proposito: o matcher
#: `@protegido` do `deploy/caddy/piloto-br.Caddyfile.template` repete estes caminhos, porque
#: o Caddy precisa saber o que NAO mandar ao `forward_auth` antes de falar com o backend.
#: Duas redacoes da mesma regra desencontram em SILENCIO (licao da DEC-044), entao
#: `test_piloto_web_verify.py` compara as duas e falha se uma andar sem a outra.
ROTAS_PUBLICAS_SEM_SESSAO = frozenset(
    {"/api/login", "/api/logout", "/api/health", "/api/verify", "/api/verify-sessao"}
)

#: Nome do cookie. `__Host-` e' o prefixo MAIS restritivo: o NAVEGADOR so' aceita o cookie com
#: `Secure`, `Path=/` e SEM `Domain`, e por isso ele fica TRANCADO a um host -- um subdominio
#: irmao de `ultra-expansao.tech` NAO consegue planta-lo. E' o que fecha a FIXACAO de sessao, e
#: e' o que o BR ja' roda em producao.
#:
#: A DEC-081 chegou a trocar por `__Secure-`+`Domain=.ultra-expansao.tech` para ter um login
#: UNICO num cookie so' (apex+BR+AR); a revisao adversarial de 2026-10-30 mediu que isso REABRE
#: a fixacao -- o `__Secure-` PERMITE `Domain`, entao um irmao comprometido (XSS ou DNS pendente)
#: planta o cookie, e a checagem de `Origin` nao barra a escrita SAME-ORIGIN da propria vitima.
#: Opcao F (2026-10-30): o cookie VOLTA a `__Host-` por host -- cada host com a sua sessao, login
#: por host. O login unico SEGURO (por "ticket" de uso unico entre hosts, sem cookie
#: compartilhado plantavel) fica como follow-up (Opcao B). Nao ha' `DOMINIO_COOKIE` de proposito:
#: `Domain` e' justamente o atributo que o `__Host-` proibe. Em dev (http) o prefixo nao vale --
#: dai o nome alternativo.
COOKIE_SESSAO = "__Host-motor_sessao"
COOKIE_SESSAO_DEV = "motor_sessao"

#: Headers que CARREGAM IDENTIDADE e que o cliente NAO pode ditar quando o portao manda.
#: Sao dois, e a lista foi medida: `remote-user` tem 19 leitores em `app.py`, e `remote-email`
#: e' lido pelo `_autor` da rota de cadastro E pelo fallback da trilha da DEC-027
#: (`_registrar_acesso` faz `remote-user or remote-email`). Sobrescrever so' o primeiro
#: deixaria um `Remote-Email` forjado virar o AUTOR registrado na auditoria -- porta fechada
#: e janela aberta. `Remote-Name`/`Remote-Groups` ficam fora porque tem ZERO leitores
#: (medido): o Caddy os copia e nada no piloto os consome.
HEADERS_DE_IDENTIDADE = ("remote-user", "remote-email")


def em_producao() -> bool:
    """Este processo roda em PRODUCAO? Leitor publico do mesmo sinal que o resto do modulo.

    Existe porque o `app.py` precisa decidir os flags do cookie de sessao (`Secure` e o
    prefixo `__Host-`, que exigem https) e alcancar `_fail_closed_ativo` de fora seria furar
    o `_` de um modulo vizinho. O SINAL e' o mesmo de sempre -- `MOTOR_CADASTRO_DIR`, o
    volume `:rw` que so' o compose monta --, e reusa-lo evita um SEGUNDO conceito de "estou
    em producao" que possa divergir do primeiro (§ do `rbac.login_efetivo`).
    """
    return _fail_closed_ativo()


def rota_publica_sem_sessao(path: str) -> bool:
    """`True` = atende sem sessao. Estaticos da SPA inclusos (nao comecam com `/api/`).

    A SPA e a tela de login moram no MESMO processo e host (`app.mount("/", StaticFiles...)`),
    entao sem esta regra a pessoa nao teria de onde digitar a senha: o portao negaria o HTML
    que contem o formulario, e o unico estado alcancavel seria 401 em tela branca.
    """
    if not path.startswith("/api/"):
        return True
    return path in ROTAS_PUBLICAS_SEM_SESSAO


#: Rotas `/api/*` que, mesmo exigindo SESSAO, NAO passam pelo gate de PAIS (DEC-081). Sao as
#: self-routes de que o APEX precisa: o apex e' servido por um processo de UM pais (ex.: BR),
#: mas tem de funcionar para quem so' tem OUTRO pais -- senao um usuario so'-AR tomaria 403 em
#: `/api/me` e nunca veria os cartoes dos paises dele. Elas resolvem a identidade do PROPRIO
#: chamador (nao servem dado territorial de pais nenhum), entao sao seguras fora do gate.
ROTAS_PAIS_NEUTRO = frozenset(
    {"/api/me", "/api/me/senha", "/api/ciencia-confidencialidade"}
)


def rota_exige_pais(path: str) -> bool:
    """`True` = esta rota passa pelo gate de PAIS da DEC-081 (nega se o pais do processo nao
    estiver entre os paises da pessoa).

    So' rotas `/api/*` que exigem sessao e NAO sao pais-neutras. Estaticos, rotas publicas e as
    self-routes do apex ficam de fora. FAIL-CLOSED: rota `/api/*` nova nasce GATEADA -- para ser
    pais-neutra, tem de entrar em `ROTAS_PAIS_NEUTRO` explicitamente.
    """
    if not path.startswith("/api/"):
        return False
    if rota_publica_sem_sessao(path):
        return False
    return path not in ROTAS_PAIS_NEUTRO

# --- Aba Acessos (emenda DEC-027, 2026-08-19): controle PROPRIO, mais forte ------
# O painel de acessos expoe atividade do TIME (dado pessoal), entao NAO entra no
# mecanismo de abas do JSON: nada de curinga "*", nada de fail-open — a rota so'
# existe para quem estiver na allowlist da env `MOTOR_ACESSOS_ADMIN_USUARIOS`
# (comparada com o Remote-User do Authelia, case-insensitive). Sem a env setada, o
# painel esta DESLIGADO para todo mundo, em dev e em producao. Quem nao pode ve
# 404 (nao 403): a existencia do painel nao e' anunciada.
# `ABA_ACESSOS` fica FORA de `ABAS_VALIDAS` de proposito: o parser do JSON descarta
# o valor se alguem tentar concede-lo por la (permissao fantasma impossivel).
ABA_ACESSOS = "acessos"
PREFIXO_ROTAS_ACESSOS = "/api/acessos/"
ENV_ADMIN_ACESSOS = "MOTOR_ACESSOS_ADMIN_USUARIOS"


def usuarios_admin_acessos() -> frozenset[str]:
    """Allowlist da env (separada por virgula), normalizada para comparacao."""
    bruto = os.environ.get(ENV_ADMIN_ACESSOS, "")
    return frozenset(u.strip().casefold() for u in bruto.split(",") if u.strip())


def login_da_requisicao(usuario: object) -> str | None:
    """QUEM esta pedindo: o header, ou a identidade de DEV quando nao ha header.

    E' a UNICA resolucao de identidade do piloto, e ela precisa ser unica. Chamava-se
    `_login_para_allowlist` e servia so' a allowlist do painel; virou publica em 10/09
    porque a TRILHA (DEC-027) lia o header cru e caia em "desconhecido" em toda
    requisicao de desenvolvimento -- o mesmo defeito que o `d2e4264` ja' tinha
    consertado aqui, reaparecendo na camada vizinha.

    Sem isto o painel era INALCANCAVEL na maquina de quem desenvolve. Nao ha Authelia
    local, entao nao ha `Remote-User`; a identidade vem do `MOTOR_DEV_USUARIO`, que o
    RBAC ja' honra em `abas_do_usuario_por_banco` -- mas a allowlist nao honrava. As duas
    camadas liam a MESMA pessoa de fontes diferentes, e o resultado era 404 em todo o
    `/api/acessos/`, inclusive na tela de administracao de usuarios.

    NAO afrouxa producao: quem resolve a identidade de dev e' o `rbac.login_efetivo`, com
    as duas travas que ele ja' tem -- override explicito e, na ausencia dele, o sinal de
    producao (`MOTOR_CADASTRO_DIR`) mandando. Havendo header, ele vence sempre.
    """
    nome = normalizar_usuario(usuario)
    if nome is not None:
        return nome
    try:
        from motor_expansao.db import rbac
    except ImportError:
        return None
    return rbac.login_efetivo(None)


def pode_ver_acessos(usuario: object) -> bool:
    """Se este Remote-User pode usar o painel de acessos (deny-by-default)."""
    nome = login_da_requisicao(usuario)
    if nome is None:
        return False
    return nome.casefold() in usuarios_admin_acessos()


def bloqueio_acessos(path: str, usuario: object) -> bool:
    """`True` = rota do painel para quem nao pode: o middleware devolve 404."""
    if not path.startswith(PREFIXO_ROTAS_ACESSOS):
        return False
    return not pode_ver_acessos(usuario)


def caminho_do_mapa() -> Path:
    """Onde mora o JSON `usuario -> [abas]`.

    Default: `acesso_abas.json` dentro do MESMO volume `:rw` do cadastro (DEC-023) —
    em producao, `/opt/motor-expansao/cadastro/acesso_abas.json`. Override por env
    `MOTOR_ACESSO_ABAS_PATH` (testes e casos especiais).
    """
    explicito = os.environ.get("MOTOR_ACESSO_ABAS_PATH")
    if explicito:
        return Path(explicito)
    cadastro = Path(os.environ.get("MOTOR_CADASTRO_DIR", str(_REPO_ROOT / "data" / "cadastro")))
    return cadastro / "acesso_abas.json"


# Cache do parse, invalidado por (caminho, mtime): editar o arquivo em producao vale
# na requisicao seguinte, sem restart e sem custo de reparse a cada request.
_cache: tuple[str, int, dict[str, frozenset[str]]] | None = None


def _ler_mapa() -> dict[str, frozenset[str]] | None:
    """`None` = controle DESLIGADO (fail-open); dict = controle ativo."""
    global _cache
    path = caminho_do_mapa()
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        _cache = None
        return None

    if _cache is not None and _cache[0] == str(path) and _cache[1] == mtime:
        return _cache[2]

    try:
        bruto = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(bruto, dict):
            raise ValueError("a raiz do JSON deve ser um objeto usuario -> [abas]")
        mapa: dict[str, frozenset[str]] = {}
        for usuario, abas in bruto.items():
            if usuario.startswith("_"):
                continue  # chave de comentario ("_comentario": "...")
            if not isinstance(abas, list):
                raise ValueError(f"as abas de {usuario!r} devem ser uma lista")
            # Aba desconhecida e' descartada em silencio aqui, mas o deploy valida.
            mapa[usuario] = frozenset(a for a in abas if a in ABAS_VALIDAS)
    except (OSError, ValueError) as erro:
        _LOG.warning(
            "acesso_abas.json ilegivel (%s) — controle de abas DESLIGADO (fail-open)",
            erro,
        )
        _cache = None
        return None

    _cache = (str(path), mtime, mapa)
    return mapa


def normalizar_usuario(valor: object) -> str | None:
    """Primeiro valor string nao vazio, ou None.

    Mesmo racional do `_autor` do app: chamada direta da rota (suite sem TestClient)
    entrega o proprio objeto `Header` como default, e ele nao pode virar um usuario.
    """
    if isinstance(valor, str) and valor.strip():
        return valor.strip()
    return None


def _fail_closed_ativo() -> bool:
    """Em falha de controle, NEGAR abas sensiveis (producao) ou fail-open (dev)?

    Override explicito: `MOTOR_ACESSO_FAIL_CLOSED` ('1'/'true' liga, '0'/'false' desliga).
    Sem override: liga quando `MOTOR_CADASTRO_DIR` esta setado — o volume :rw do cadastro
    so' existe em producao (compose); em dev local a var nao esta setada -> fail-open.
    """
    override = os.environ.get("MOTOR_ACESSO_FAIL_CLOSED")
    if override is not None:
        return override.strip().lower() in ("1", "true", "sim", "yes")
    return bool(os.environ.get("MOTOR_CADASTRO_DIR"))


# Throttle do log de fail-closed: loga UMA vez por episodio (senao seria 1 erro por
# request enquanto o controle estiver caido). Resetado quando o controle volta.
_fail_closed_logado = False


def abas_do_usuario(usuario: str | None) -> frozenset[str]:
    """Abas que este usuario pode usar, segundo o JSON vigente."""
    global _fail_closed_logado
    mapa = _ler_mapa()
    if mapa is None:
        # Controle indisponivel (arquivo ausente/ilegivel/mount sumiu).
        if _fail_closed_ativo():
            # Fail-CLOSED em producao (BLK-SEC-05): nega as abas SENSIVEIS; mantem as
            # nao-sensiveis para nao trancar 100% o piloto por um typo no JSON.
            if not _fail_closed_logado:
                _LOG.error(
                    "acesso_abas.json indisponivel em PRODUCAO — fail-closed: abas "
                    "sensiveis (%s) NEGADAS ate o controle voltar.",
                    ", ".join(sorted(ABAS_SENSIVEIS)),
                )
                _fail_closed_logado = True
            return ABAS_VALIDAS - ABAS_SENSIVEIS
        return ABAS_VALIDAS  # dev/local: fail-open historico
    _fail_closed_logado = False  # controle voltou -> permite logar de novo no proximo episodio
    if usuario is None:
        # Sem identidade NAO ha curinga. "*" quer dizer "qualquer usuario AUTENTICADO", e quem
        # chega sem `Remote-User` nem identidade de dev nao e' usuario nenhum. Ate' 15/09 este
        # ramo nao existia e o curinga caia tambem sobre `None`: com `{"*": ["mapa",
        # "oportunidades"]}` no JSON, 18 rotas atendiam requisicao ANONIMA (medido). Nao vazava
        # porque o Authelia injeta o header em toda requisicao -- mas e' a porta que abre no dia
        # em que ele sair (P19), e a unica defesa da instancia AR, que roda so' com o JSON.
        return frozenset()
    if usuario in mapa:
        return mapa[usuario]
    # Curinga NUNCA concede aba sensivel (pentest Onda B #14): executiva/imobiliaria/
    # viabilidade (financeiro da rede + PII + escrita) exigem concessao NOMINAL no JSON,
    # nunca por "*". Espelha o fail-closed (linha 248, `ABAS_VALIDAS - ABAS_SENSIVEIS`):
    # um typo `{"*": ["executiva"]}` liberaria financeiro a TODO autenticado.
    return mapa.get("*", frozenset()) - ABAS_SENSIVEIS


def abas_necessarias(path: str) -> frozenset[str] | None:
    """Abas que liberam esta rota; `None` = rota sem controle."""
    for prefixo, abas in REGRAS_DE_ACESSO:
        if path.startswith(prefixo):
            return abas
    return None


def motivo_bloqueio(path: str, usuario: object) -> str | None:
    """`None` = pode passar; string = detail do 403 que o middleware devolve.

    A identidade sai de `login_da_requisicao`, como em todo o resto -- e nao do header cru, que
    era o que esta funcao lia ate' 15/09. Com o JSON no comando e sem Authelia na frente
    (desenvolvimento), o header cru e' sempre vazio: a pessoa de `MOTOR_DEV_USUARIO` nunca recebia
    as abas NOMINAIS dela, so' o curinga -- e, com o curinga fechado para quem nao tem identidade,
    passaria a nao receber nada. Em producao nada muda: havendo header, e' ele; e o sinal de
    producao desliga a identidade de dev.
    """
    necessarias = abas_necessarias(path)
    if necessarias is None:
        return None
    if necessarias & abas_do_usuario(login_da_requisicao(usuario)):
        return None
    return "Seu usuário não tem acesso a esta área do piloto. Fale com o Felipe."


# ═══════════════════════════════════════════════════════════════════════════════
# Camada de BANCO (F4.2) — o que este módulo foi escrito para virar
# ═══════════════════════════════════════════════════════════════════════════════
#
# O mecanismo de abas acima permanece INTACTO, e continua sendo o caminho quando não há
# banco configurado: o piloto tem de subir sem ele, e um deploy que ligue os dois ao mesmo
# tempo seria irreversível na prática. Enquanto `MOTOR_DATABASE_URL` não existir, nada muda.
#
# A diferença entre os dois modelos não é de implementação, é de granularidade. A "aba" nunca
# foi a unidade real: o casamento sempre foi por PREFIXO DE ROTA, e a DEC-037 fez o recorte
# mais fino do sistema entre DUAS ROTAS DA MESMA TELA — o dossiê do imóvel (com contato de
# corretor) restrito, e a lista agregada liberada porque alimenta os pins do Mapa. O banco
# modela `recurso.acao`, que é o que isso sempre foi.
#
# E ele acrescenta o que o modelo por aba não expressa: o MÉTODO HTTP. Hoje `/api/rede/`
# libera ver a carteira e editar o cadastro pela mesma chave, indistinguíveis. Com o método
# no gate, `rede.ver` e `rede.cadastro_editar` viram permissões separadas de verdade.

#: (prefixo, métodos que exigem esta capacidade ou None = todos, capacidade).
#: ORDEM SIGNIFICATIVA — first-match, como as `REGRAS_DE_ACESSO`. Duas precedências
#: importam e são frágeis se reordenadas:
#:   * `/api/rede/cadastro` com métodos de ESCRITA vem antes de `/api/rede/`, senão editar
#:     o cadastro cairia em `rede.ver` e a separação do D22 não valeria nada;
#:   * `/api/oportunidades/` (dossiê) antes de `/api/oportunidades` (lista) — a barra final
#:     é o que separa os dois, e é a distinção que a DEC-037 existe para fazer.
REGRAS_POR_CAPACIDADE: tuple[tuple[str, tuple[str, ...] | None, str], ...] = (
    ("/api/rede/cadastro", ("PUT", "POST", "PATCH", "DELETE"), "rede.cadastro_editar"),
    ("/api/rede/", None, "rede.ver"),
    ("/api/executiva/", None, "rede.ver"),
    ("/api/geocode", None, "ponto.analisar"),
    ("/api/resolver-ponto", None, "ponto.analisar"),
    ("/api/ponto", None, "ponto.analisar"),
    ("/api/cobertura/", None, "ponto.analisar"),
    ("/api/relatorio/comparacao", None, "relatorio.comparacao"),
    ("/api/relatorio/municipal", None, "relatorio.municipal"),
    ("/api/relatorio/pontual", None, "relatorio.pontual"),
    ("/api/viabilidade", None, "viabilidade.calcular"),
    ("/api/faixa-alunos", None, "viabilidade.simular"),
    ("/api/aluguel-referencia", None, "viabilidade.simular"),
    ("/api/demanda-v2", None, "viabilidade.simular"),
    ("/api/simulador/", None, "viabilidade.simular"),
    ("/api/uf/", None, "territorio.explorar"),
    ("/api/municipio/", None, "territorio.explorar"),
    ("/api/municipios/", None, "territorio.explorar"),
    ("/api/municipio-do-ponto", None, "territorio.explorar"),
    ("/api/estados", None, "territorio.ranking_nacional"),
    # Ranking NACIONAL de hexagonos (DEC-044) — mesma natureza de `/api/estados`: a fila
    # pronta sem escolher estado. No modelo por aba as duas sao `oportunidades`.
    ("/api/hexagonos", None, "territorio.ranking_nacional"),
    # Foto e pino da unidade concorrente: camada VISUAL do Mapa Territorial. No modelo por
    # aba sao `{mapa, oportunidades}`; aqui `territorio.explorar` nao perde ninguem, porque
    # todo perfil da D22 que tem o ranking tem tambem a exploracao.
    ("/api/foto-concorrente/", None, "territorio.explorar"),
    ("/api/pin-concorrente/", None, "territorio.explorar"),
    ("/api/oportunidades/", None, "imovel.dossie_ver"),
    ("/api/oportunidades", None, "imovel.listar"),
    ("/api/imobiliaria/evento/", None, "imovel.registrar_gesto"),
    # ORDEM SIGNIFICATIVA: a escrita vem antes da regra generica do painel, como
    # `/api/rede/cadastro` vem antes de `/api/rede/`. Ver o painel (a trilha de quem usou
    # o que) e' LEITURA; mudar quem entra e' outra coisa, e por isso outra capacidade (D25).
    ("/api/acessos/usuarios", ("POST", "PATCH", "PUT", "DELETE"), "acesso.usuario_gerir"),
    ("/api/acessos/", None, "acesso.painel_ver"),
)

#: Capacidades equivalentes às `ABAS_SENSIVEIS`: são estas que o fail-closed nega quando o
#: banco cai em produção. Financeiro da rede, PII de corretor, escrita e o painel de acessos.
CAPACIDADES_SENSIVEIS = frozenset(
    {
        "rede.ver",
        "rede.cadastro_editar",
        "imovel.dossie_ver",
        "viabilidade.calcular",
        "viabilidade.simular",
        "acesso.painel_ver",
        "acesso.usuario_gerir",
    }
)


def banco_no_comando() -> bool:
    """O RBAC do banco manda? Só quando ele está configurado E o driver existe."""
    try:
        from motor_expansao import db
    except ImportError:
        return False
    return db.configurado()


def capacidade_necessaria(path: str, metodo: str) -> str | None:
    """Capacidade que libera esta rota+método; `None` = rota sem controle."""
    for prefixo, metodos, capacidade in REGRAS_POR_CAPACIDADE:
        if not path.startswith(prefixo):
            continue
        if metodos is not None and metodo.upper() not in metodos:
            continue  # a regra é de escrita e o método não é: cai para a próxima
        return capacidade
    return None


#: Throttle do log de RBAC indisponivel: UMA linha por episodio, como o `_fail_closed_logado`
#: do JSON. Sem ele, cada pedido degradado gravava um ERROR -- milhares por segundo num mapa
#: com o banco fora, e o erro que importa se perdia no meio. Volta a `False` quando o banco
#: responde de novo, no gate ou no `/api/me` (`_rbac_respondeu`).
_rbac_indisponivel_logado = False

#: O que o `/api/me` ja' disse no log sobre o RBAC sem resposta NESTE episodio: `None` (nada --
#: o RBAC respondeu desde a ultima linha), `"sem_prova"` (a rota respondeu 503) ou
#: `"degradado"` (escondeu as abas sensiveis). Sem isto, cada abertura de SPA durante um
#: incidente gravava um ERROR (#463, follow-up A) -- a mesma inundacao que o
#: `_rbac_indisponivel_logado` acima resolveu no gate. Guarda o CASO, e nao um bool: a passagem
#: de um para o outro muda o que a pessoa recebe (503 x abas escondidas) e merece a sua linha;
#: repetir o mesmo caso, nao.
_episodio_rbac_no_me: str | None = None


def primeira_vez_no_episodio_do_me(caso: str) -> bool:
    """`True` se o `/api/me` ainda nao registrou ESTE caso no episodio corrente: quem chama loga.

    Uma linha por episodio, no molde do `_rbac_indisponivel_logado`. O episodio acaba quando o
    RBAC responde de novo, no `/api/me` ou no gate (`_rbac_respondeu`).
    """
    global _episodio_rbac_no_me
    if _episodio_rbac_no_me == caso:
        return False
    _episodio_rbac_no_me = caso
    return True


def _rbac_respondeu() -> None:
    """O banco respondeu ao RBAC: o proximo episodio de indisponibilidade volta a logar.

    Zera os DOIS throttles, o do gate e o do `/api/me`. Um so' teria o defeito de esquecer o
    outro: o banco volta, a pessoa navega sem recarregar a SPA (so' o gate ve' a volta), e a
    proxima queda chegava muda no `/api/me` porque o episodio anterior nunca tinha fechado ali.
    """
    global _rbac_indisponivel_logado, _episodio_rbac_no_me
    _rbac_indisponivel_logado = False
    _episodio_rbac_no_me = None


class RbacSemProvaDeQueda(RuntimeError):
    """O RBAC nao respondeu, e nada prova que o banco caiu: 503, nao degradacao.

    A degradacao (`motivo_bloqueio_banco_indisponivel`) LIBERA as rotas nao sensiveis sem
    checar permissao -- aceitavel com o banco FORA, um furo com ele no ar. Sem prova de
    queda, toda rota controlada recebe 503: nenhuma capacidade e' presumida.

    Vale tambem para o `/api/me` desde 24/10/2026 (#463, follow-up A): la' a degradacao
    ESCONDE abas, e com o banco vivo e ocupado isso tirava de quem as tem a executiva, a
    imobiliaria e a viabilidade -- enquanto o gate, pela mesma falha, respondia 503.
    """


def banco_em_falha() -> bool:
    """O ultimo uso do banco terminou em `BancoIndisponivel`? Sem o pacote, `False`."""
    try:
        from motor_expansao.db import postgres
    except ImportError:
        return False
    return postgres.banco_em_falha()


def motivo_bloqueio_banco_indisponivel(path: str, metodo: str, erro: object) -> str | None:
    """A resposta do gate quando o banco NAO respondeu -- a degradação, isolada.

    Fica numa função própria para o middleware dar a MESMA resposta sem chegar a perguntar
    ao banco (fila de threads do banco cheia, `app.FilaDoBancoCheia`): duas cópias desta
    regra divergiriam em silêncio. Não faz I/O.
    """
    necessaria = capacidade_necessaria(path, metodo)
    if necessaria is None:
        return None
    if not _fail_closed_ativo():
        return None  # dev: fail-open histórico
    global _rbac_indisponivel_logado
    if not _rbac_indisponivel_logado:
        _rbac_indisponivel_logado = True
        _LOG.error("RBAC indisponivel (%s) — negando capacidades sensiveis", erro)
    if necessaria in CAPACIDADES_SENSIVEIS:
        return "Acesso indisponível no momento. Tente novamente em instantes."
    return None


def motivo_bloqueio_por_banco(path: str, metodo: str, usuario: object) -> str | None:
    """`None` = pode passar; string = detail do 403.

    Degradação idêntica à do JSON, e pelo mesmo raciocínio: banco fora do ar em PRODUÇÃO
    nega as capacidades sensíveis e mantém as demais, para não trancar o piloto inteiro por
    um incidente de infraestrutura; em dev, fail-open. O que muda é só de onde vem a
    resposta quando tudo está no ar.
    """
    necessaria = capacidade_necessaria(path, metodo)
    if necessaria is None:
        return None

    from motor_expansao import db
    from motor_expansao.db import rbac

    try:
        quem = rbac.identidade(normalizar_usuario(usuario))
    except db.BancoSemProvaDeQueda as erro:
        # Pool saturado, lock, statement timeout: o banco esta' (ou pode estar) NO AR. So'
        # degrada se OUTRA chamada ja' provou a queda e nenhuma terminou bem desde entao.
        if not banco_em_falha():
            raise RbacSemProvaDeQueda(str(erro)) from erro
        return motivo_bloqueio_banco_indisponivel(path, metodo, erro)
    except (db.BancoIndisponivel, db.BancoNaoConfigurado) as erro:
        return motivo_bloqueio_banco_indisponivel(path, metodo, erro)

    _rbac_respondeu()  # banco respondeu: o proximo episodio volta a logar

    if quem is None or not quem.pode(necessaria):
        return "Seu usuário não tem acesso a esta área do piloto. Fale com o Felipe."
    return None


#: Capacidade que SUSTENTA cada aba da SPA. O `/api/me` responde em ABAS mesmo com o banco
#: no comando — o contrato do front não muda, e `web/src/lib/acesso.ts` continua valendo.
#:
#: A escolha de UMA capacidade por aba (e não "qualquer uma que a aba use") é o que faz a
#: interface contar a mesma história que o gate: a aba aparece quando a pessoa consegue
#: fazer o que aquela superfície existe para fazer, não quando ela alcança um pedaço solto.
#:
#: Conferido contra os quatro perfis da D22 — o resultado reproduz exatamente as abas que
#: cada um tinha no `acesso_abas.json`:
#:   expansao    -> mapa, oportunidades, imobiliaria, viabilidade
#:   consultoria -> executiva
#:   lideres     -> as cinco
#:   growth      -> as cinco (+ acessos, que vem da env)
CAPACIDADE_QUE_SUSTENTA_A_ABA: dict[str, str] = {
    "mapa": "territorio.explorar",
    "oportunidades": "territorio.ranking_nacional",
    "imobiliaria": "imovel.dossie_ver",
    "viabilidade": "viabilidade.simular",
    "executiva": "rede.ver",
}


def abas_do_usuario_por_banco(usuario: object) -> frozenset[str]:
    """Abas derivadas das capacidades do RBAC. Mesma degradação -- e mesma régua de PROVA -- do gate.

    `ABA_ACESSOS` fica de fora aqui, como no outro caminho: ela vem da allowlist de env e
    é somada pela rota. A capacidade `acesso.painel_ver` existe no banco e governa a ROTA,
    mas não anuncia a aba — as duas camadas são independentes de propósito (DEC-027).

    SEM PROVA DE QUEDA, LEVANTA `RbacSemProvaDeQueda` (#463, follow-up A). `BancoSemProvaDeQueda`
    e' SUBCLASSE de `BancoIndisponivel` (`db/postgres.py`), e o `except` generico que estava aqui
    a pegava como "banco fora": com o banco VIVO mas ocupado (pool saturado, lock, statement
    timeout), o `/api/me` escondia executiva, imobiliaria e viabilidade de quem as tem -- e a
    SPA ainda tirava a pessoa da tela em que ela estava --, enquanto o gate
    (`motivo_bloqueio_por_banco`), pela MESMA falha, respondia 503. A interface e o portao
    contavam historias diferentes sobre a mesma pessoa. A regra agora e' a do gate: degradar so'
    com a queda PROVADA (`banco_em_falha`); sem ela, quem chama responde 503.
    """
    from motor_expansao import db
    from motor_expansao.db import rbac

    try:
        quem = rbac.identidade(normalizar_usuario(usuario))
    except db.BancoSemProvaDeQueda as erro:
        # A MESMA decisao do gate, na mesma ordem: so' degrada se OUTRA chamada ja' provou a
        # queda e nenhuma terminou bem desde entao.
        if not banco_em_falha():
            raise RbacSemProvaDeQueda(str(erro)) from erro
        return _abas_com_o_rbac_fora(erro)
    except (db.BancoIndisponivel, db.BancoNaoConfigurado) as erro:
        return _abas_com_o_rbac_fora(erro)
    _rbac_respondeu()
    if quem is None:
        return frozenset()
    return frozenset(
        aba
        for aba, capacidade in CAPACIDADE_QUE_SUSTENTA_A_ABA.items()
        if quem.pode(capacidade)
    )


def _abas_com_o_rbac_fora(erro: object) -> frozenset[str]:
    """A degradação do `/api/me` com o banco FORA -- a mesma do gate, em abas.

    Em produção esconde as sensíveis e mantém Mapa e Oportunidades; em dev, fail-open
    histórico. O log sai UMA vez por episódio (`primeira_vez_no_episodio_do_me`): antes era um
    ERROR a cada abertura de SPA durante o incidente.
    """
    if not _fail_closed_ativo():
        return ABAS_VALIDAS  # dev: fail-open histórico
    if primeira_vez_no_episodio_do_me("degradado"):
        _LOG.error("RBAC indisponivel no /api/me (%s) — escondendo abas sensiveis", erro)
    return ABAS_VALIDAS - ABAS_SENSIVEIS
