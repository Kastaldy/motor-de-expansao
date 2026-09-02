# SPEC — Portal de seleção de país na raiz `ultra-expansao.tech`

- Data: 2026-08-31 | Status: **PRONTA PARA CODAR** | Decidida por Felipe em 2026-08-31
- **Dono do arquivo: esta spec.** `docs/plano_multipais.md` e `docs/decisions/` têm outros donos e **não** são alterados por aqui — o ponteiro para esta spec é costurado depois, por outra pessoa.
- Bloco sugerido: **BLK-INTL-13**. Criticidade: **CRITICA** — exige a label `critica-aprovada` do Felipe (§8). **Não** é `loop-safe`.
- Depende de: **BLK-INTL-05** (criação dos grupos `expansao_*` no Authelia). Ler o §9 **antes** de abrir a branch.
- Esforço: **1 a 2 dias**, dos quais mais da metade é a migração de cache do 301 e o aviso ao time — não é código.

---

## 0. O que foi conferido, e o que não deu para conferir

**Toda referência `arquivo:linha` abaixo foi lida no working tree em 2026-08-31.** Onde eu não consegui
executar a verificação, está dito com todas as letras — não há afirmação de comportamento que eu não
tenha lido no repositório ou que não esteja marcada como pendente de teste no ar.

| Afirmação | Onde | Confere? |
|---|---|---|
| O bloco raiz **só** redireciona, não serve nada | `Caddyfile:19-22` — `import sec_headers` + `redir https://piloto.ultra-expansao.tech{uri} permanent` | ✅ exatamente nas linhas 19-22 |
| O `forward_auth` do piloto já copia os grupos | `Caddyfile:68-71` — `copy_headers Remote-User Remote-Groups Remote-Email` | ✅ exatamente nas linhas 68-71 |
| Já existe precedente de `route { forward_auth … }` neste arquivo | `Caddyfile:35-42` (bloco `/tiles/*` do dashboard) | ✅ — e o §2.1 explica por que ele **precisa** ser um `route` |
| O snippet de cabeçalhos comuns, e por que a CSP ficou de fora | `Caddyfile:1-17`, motivo nas linhas 4-6 | ✅ |
| O serviço `caddy` e seus volumes | `docker-compose.prod.yml:256-278`; volumes em `:268-274` | ✅ `./Caddyfile:/etc/caddy/Caddyfile:ro` (269), `caddy_data:/data` (270), `caddy_config:/config` (271), `/opt/motor-expansao/logs/caddy:/var/log/caddy` (274) |
| O Authelia monta o diretório inteiro do repo | `docker-compose.prod.yml:287-288` — `./authelia:/config` | ✅ |
| `session.cookies[0].domain` cobre a raiz | `authelia/configuration.yml:56-59` — `domain: ultra-expansao.tech` | ✅ **não muda nada** (§6.3) |
| `default_redirection_url` aponta para o dashboard | `authelia/configuration.yml:59` | ✅ `https://dashboard.ultra-expansao.tech` |
| `access_control` nega por padrão e tem **duas** regras, sem `subject` | `authelia/configuration.yml:80-86` (`default_policy: deny` na 81; regras em `:83-86`) | ✅ |
| 19 usuários, todos num único grupo `ultra_team` | `authelia/users_database.yml` — 19 `displayname`; `groups: [ultra_team]` em `:12`, `:19`, `:26`, … `:138` | ✅ |
| `Caddyfile`, `docker-compose*` e `authelia/` são CRITICO no guard | `scripts/loop_guard.py:122-124` | ✅ (`.dockerignore` é CRITICO em `:121`) |
| Um diretório novo na raiz **entra** nas imagens | `Dockerfile.web:43` e `Dockerfile.api:33` fazem `COPY . .` | ✅ — daí o §5.2 |
| O padrão para tirar arquivo de deploy da imagem já existe | `.dockerignore:39-42` — *"Configurações de deploy (montados via volume)"*: `Caddyfile`, `authelia/`, `.env` | ✅ |
| A DEC-046 recusa **seletor de país em runtime** | `docs/decisions/DEC-046.md:6` (item 1) | ✅ — texto citado no §1.2 |
| Deploy sempre manual, por digest | `CLAUDE.md:131-137` (§6) e a ressalva da DEC-016 em `CLAUDE.md:144` | ✅ |
| Repo na VPS em `/opt/motor-expansao/app` | `docs/infra_producao.md:772`, `:824` | ✅ — é o que faz o bind relativo `./portal` funcionar (§5.2) |

**Uma decisão de desenho que esta spec fecha, e que vale ler antes do §5.4:** a página filtra países
por **renderização** (`if` de template por país), nunca por CSS. Uma primeira versão do `index.html`
emitia os dois cartões sempre e escondia um com `display:none` — o corpo HTTP continuava dizendo
quais países existem, para qualquer usuário autenticado. Isso contradizia o próprio §6.2 (o motivo de
a raiz exigir `one_factor` em vez de `bypass`) e reprovava três aceites do §7.2. **A regra passa a ser
explícita e testada** (§7.4, asserts 11 e 12): conteúdo controlado por permissão **não é emitido** —
e isso vale também para o **comentário HTML**, que viaja no corpo como qualquer outro byte.

**O que NÃO deu para conferir aqui, e por quê:**

1. **A versão exata do Caddy em produção.** `docker-compose.prod.yml:257` pina `image: caddy:2-alpine`
   — **tag flutuante**. Não há `docker` nesta máquina (`docker: command not found`), então não pude
   rodar `caddy version`. Isto é, por si só, um achado: o repositório pina `web` e `api` por **digest
   imutável** (`docker-compose.prod.yml:151` e `:28`, ambos com `:?` fail-closed) e deixa a porta de
   entrada num ponteiro móvel. **Não é escopo desta spec resolver** — mas o §7.1 exige registrar o
   número da versão no PR, e é o candidato natural a virar um bloco próprio.
   As peças de Caddy que esta spec usa — `route` com ordem literal, matcher `header` com curinga
   (`*x*`), `not`, conjunção por linhas dentro de um matcher nomeado, `request_header`, `templates`,
   `vars` — são todas de Caddy 2 e nenhuma é recente; o próprio `Caddyfile:59` já assume `>= 2.5`.
   Ainda assim: **§7.1 é `caddy validate` antes de qualquer reload.**
2. **A semântica de `query escolher=*` com valor vazio** (`?escolher` sem `=1`) — **resolvida na
   documentação, pendente de execução.** O matcher `query` do Caddy compara `paramVal[0] == v || v == "*"`:
   o curinga casa a **presença da chave** com qualquer valor, **inclusive vazio**. Logo `?escolher` nu
   funciona. Isso é leitura da documentação/código do matcher, **não** execução — não há `caddy` nesta
   máquina. O aceite §7.2 item 7 continua testando as duas formas, agora para **confirmar** um
   comportamento esperado em vez de descobrir um desconhecido. **A forma canônica publicada segue
   `?escolher=1`** (§4.2), e o motivo não é mais a dúvida: é ter **uma** grafia só no dia da virada,
   porque esse link é o antídoto da armadilha A e duas grafias em circulação custam caro exatamente ali.

---

## 1. Por que este portal existe

### 1.1 O problema, em uma frase

O colaborador salva **um** favorito. Hoje esse favorito é a raiz, e a raiz é um atalho fixo para o
Brasil (`Caddyfile:21`). Com a Argentina entrando, um atalho fixo para um país obriga cada pessoa a
saber de cor o subdomínio do país dela — e obriga quem tem dois países a manter dois favoritos e a
lembrar qual é qual. O portal troca isso por: **um endereço, que sabe para onde te mandar.**

Comportamento pedido, e é só isto:

| O usuário tem acesso a | O que acontece ao abrir `https://ultra-expansao.tech/` |
|---|---|
| **um** país | vai direto para o piloto daquele país. Não vê seletor nenhum. |
| **vários** países | vê a página de escolha — **com os países que ele pode abrir, e só eles** |
| **nenhum** país | vê uma explicação em português dizendo a quem pedir acesso — nomeadamente: *"Fale com o Felipe — é liberação de grupo, leva minutos"* (§5.4). Não um 403 seco, e muito menos o 404 cru do Caddy. |

### 1.2 Por que isto NÃO contradiz a DEC-046 — e este parágrafo precisa sobreviver a qualquer edição

A DEC-046 (`docs/decisions/DEC-046.md:6`) recusa, textualmente:

> *"Não existe seletor de país em runtime, não existe eixo de país em chave de cache, em rota, em
> payload ou em `localStorage`."*

O que ela está protegendo é uma propriedade de **correção**, não de estilo: há **35** `@functools.lru_cache`
em `web/server/app.py` e **5** em `src/motor_expansao/api/service.py`, e nenhum deles tem país na chave.
`carregar_uf("SC")` só é inequívoco porque existe **uma** SC por processo. Um seletor que trocasse a
base servida **dentro** do app rechavearia os 40 caches — e o defeito sairia como fator de renda de um
país no PDF do outro, calado.

**Este portal não é esse seletor, e a diferença é verificável, não retórica:**

1. **Ele não serve dado nenhum.** Não lê `MOTOR_DATA_DIR`, não abre parquet, não tem `lru_cache`, não
   tem processo Python. Ele lê um cabeçalho HTTP e devolve ou um `302` ou um arquivo estático de uma
   tela.
2. **Ele não roda dentro do container de país nenhum.** Roda no `caddy`
   (`docker-compose.prod.yml:256-278`), que já é o único processo que fala com os dois. **Não infla a
   imagem do Brasil nem a da Argentina** — e o §5.2 fecha isso com uma linha no `.dockerignore`, não
   com uma promessa.
3. **Depois do redirect ele sai da frente.** O navegador termina a requisição em
   `piloto.ultra-expansao.tech` ou em `piloto-ar.ultra-expansao.tech`. Cada país segue com **seu
   processo, seu cache e seu `perfil.json`**, exatamente como a DEC-046 manda.

> **A frase que resolve a discussão:** este é um **roteador de porta de entrada**, não um seletor de
> tenant. Ele decide um **destino**; a DEC-046 proíbe decidir uma **base**. O eixo de país continua
> sendo propriedade do deploy — o portal apenas para de exigir que o humano decore qual deploy é o
> dele.

---

## 2. O bloco de Caddy

### 2.1 Armadilha nº 1 — `route` é obrigatório, e não é estilo

Fora de um `route`, o Caddy **reordena** as diretivas pela ordem canônica dele, não pela ordem escrita.
Nessa ordem, **`redir` vem antes de `forward_auth`**. Um bloco escrito assim:

```caddy
# ERRADO — não copie
forward_auth authelia:9091 { … copy_headers Remote-Groups }
handle @so_br { redir https://piloto.ultra-expansao.tech{uri} 302 }
```

executa o `redir` **antes** de o `forward_auth` ter rodado. `Remote-Groups` ainda não existe, nenhum
matcher de país casa, e **todo mundo cai no caso "nenhum país"** — um bug que não aparece em
`caddy validate`, só no ar, e que parece "os grupos não estão chegando".

Dentro de `route { … }` a ordem é a **escrita**. É exatamente por isso que o bloco `/tiles/*` do
dashboard já é um `route` (`Caddyfile:35-42`) — há precedente no próprio arquivo.

### 2.2 Armadilha nº 2 — a ordem dos matchers, e como matá-la em vez de documentá-la

A escrita ingênua dos matchers é esta:

```caddy
# ERRADO — não copie
@br header Remote-Groups *expansao_br*
@ar header Remote-Groups *expansao_ar*
```

Quem tem **os dois** grupos casa **os dois** matchers. Como `handle` é primeiro-que-casa-vence, a
correção passa a depender de o caso "ambos" ser avaliado **antes** dos casos simples — ou seja, passa
a depender de o próximo leitor não reordenar dois blocos que parecem intercambiáveis. Num arquivo que
custa `critica-aprovada` por edição, isso é uma armadilha cara.

**A escolha desta spec é não conviver com a ordem: matar a sobreposição.** Cada matcher de país
carrega a negação dos outros:

```caddy
@so_br {
    header Remote-Groups *expansao_br*
    not header Remote-Groups *expansao_ar*
}
```

Duas linhas dentro de um matcher nomeado são uma **conjunção** (E lógico) — é assim que se compõe
`E` no Caddyfile. Com as negações, `@so_br`, `@so_ar`, `@sem_pais` e o fallback ficam **mutuamente
exclusivos e exaustivos** sobre os 4 casos possíveis (`nenhum`, `br`, `ar`, `ambos`), e **a ordem
deles deixa de importar**.

> **Sobra exatamente UMA dependência de ordem, e ela é intencional: `@escolher` tem de vir primeiro**,
> porque ele sobrepõe todos os outros de propósito (§4.2). Uma dependência de ordem cabe na cabeça de
> quem revisa; quatro não cabem.

**Cuidado com o curinga.** `*expansao_ar*` é **substring**: um grupo futuro chamado `expansao_argentina`
casaria como se fosse `expansao_ar`. A regra que fecha isso é de **nomenclatura**, e vale a pena estar
escrita: **nenhum grupo `expansao_*` pode ser prefixo ou substring de outro.** O teste do §7.4 verifica
isso mecanicamente contra o `users_database.yml`.

### 2.3 O bloco, pronto para colar

Substitui integralmente as linhas **19-22** do `Caddyfile`.

```caddy
# ── PORTAL DE SELECAO DE PAIS (raiz) ────────────────────────────────────────────
# Decidido em 2026-08-31. Spec: docs/spec_portal_selecao_pais.md.
#
# POR QUE ISTO NAO CONTRADIZ A DEC-046: este bloco nao serve dado nenhum. Ele le UM
# cabecalho (Remote-Groups, que o Authelia ja entrega) e devolve ou um 302 ou uma
# tela estatica. Nao ha processo de pais aqui, nao ha cache, nao ha MOTOR_DATA_DIR.
# A DEC-046 proibe escolher a BASE em runtime; isto escolhe o DESTINO e sai da frente.
# Cada pais segue com seu processo, seu cache e seu perfil.json.
ultra-expansao.tech, www.ultra-expansao.tech {
    import sec_headers

    # CSP estrita SO neste host. O comentario do topo deste arquivo (linhas 4-6) tira a
    # CSP do snippet comum porque ela quebraria o mapa da SPA (deck.gl/maplibre usam
    # worker/blob e tiles). O portal nao tem mapa, nao tem script e nao tem asset
    # externo — entao ele pode pagar a CSP que o piloto ainda nao pode.
    header Content-Security-Policy "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'none'"

    root * /srv/portal

    # ── MATCHERS ────────────────────────────────────────────────────────────────
    # ARMADILHA DE ORDEM (spec §2.2): a versao ingenua (`@br header Remote-Groups
    # *expansao_br*`, sozinha) casa TAMBEM para quem tem BR+AR, e ai a correcao passa a
    # depender de o caso "ambos" ser avaliado ANTES — ou seja, de ninguem reordenar dois
    # `handle` que parecem intercambiaveis. As negacoes abaixo tornam os matchers
    # MUTUAMENTE EXCLUSIVOS, e ai a ordem deles deixa de importar. Varias linhas dentro
    # de um matcher nomeado sao uma CONJUNCAO (E logico).
    # A UNICA ordem que importa e' `@escolher` vir primeiro, porque ele sobrepoe todos
    # os outros de proposito.

    # Saida manual (spec §4.2): pula TODO redirect automatico e devolve o seletor,
    # inclusive para quem so tem um pais. Sem isto, o atalho de um pais vira cela — nao
    # ha caminho de volta ao seletor sem deslogar.
    @escolher query escolher=*

    @so_br {
        header Remote-Groups *expansao_br*
        not header Remote-Groups *expansao_ar*
    }
    @so_ar {
        header Remote-Groups *expansao_ar*
        not header Remote-Groups *expansao_br*
    }
    # Nenhum pais. NAO e' 403: e' uma pagina que explica a quem pedir acesso.
    @sem_pais {
        not header Remote-Groups *expansao_*
    }

    # Sinalizadores para a pagina (spec §5.4): dizem quais cartoes RENDERIZAR. NAO sao
    # controle de acesso — o acesso de verdade e' o forward_auth de CADA host de pais.
    # A pagina le X-Portal-*, NUNCA Remote-Groups direto (spec §5.4).
    @tem_br header Remote-Groups *expansao_br*
    @tem_ar header Remote-Groups *expansao_ar*

    # ── ORDEM DE EXECUCAO ───────────────────────────────────────────────────────
    # `route` e' OBRIGATORIO, nao estilo (spec §2.1). Fora dele o Caddy reordena pela
    # ordem canonica, na qual `redir` vem ANTES de `forward_auth`: o redirect dispararia
    # sem Remote-Groups e TODO MUNDO cairia no caso "sem pais". Dentro de `route` a
    # ordem e' a escrita. Mesmo motivo do bloco /tiles/* do dashboard (linhas 35-42).
    route {
        forward_auth authelia:9091 {
            uri /api/authz/forward-auth
            copy_headers Remote-User Remote-Groups Remote-Email
        }

        # Nada nesta origem pode ser cacheado. Reforco da migracao 301 -> 302 (spec §4.1):
        # sem isto, um intermediario poderia guardar a escolha de um usuario.
        header Cache-Control "no-store"

        # ANTI-SPOOF: apagar SEMPRE antes de setar. Sem as duas linhas de remocao, um
        # cliente que mandasse `X-Portal-Ar: 1` a mao teria o cabecalho preservado (o
        # `request_header` so sobrescreve quando o matcher casa) e veria o cartao da
        # Argentina. Ele nao ABRIRIA a Argentina — o forward_auth de piloto-ar barra —
        # mas veria que ela existe. Custa duas linhas fechar.
        # O SEGUNDO vetor de spoof e' `Remote-Groups` forjado, e quem o fecha e' o
        # `copy_headers` do forward_auth acima: ele faz `set`, nao `add`, e sobrescreve
        # o valor que o cliente mandou. Os DOIS sao testados no §7.2 item 9.
        request_header -X-Portal-Br
        request_header -X-Portal-Ar
        request_header @tem_br X-Portal-Br 1
        request_header @tem_ar X-Portal-Ar 1

        # 1) A saida manual vence tudo. UNICA ordem que importa neste bloco.
        #    `templates` NAO E' OPCIONAL: e' ele que executa os `if` por pais do
        #    index.html. Sem ele a pagina sai com as acoes de template em texto e
        #    ninguem ve cartao nenhum. O §7.4 assert 9 verifica que os DOIS handle
        #    que servem o index.html tem esta linha.
        handle @escolher {
            rewrite * /index.html
            templates
            file_server
        }

        # 2) Um pais e SO ele: vai direto. 302, NUNCA `permanent`/301 — spec §4.1.
        #    Navegador cacheia 301 indefinidamente; quem ganhasse um segundo pais
        #    depois nunca mais veria o seletor.
        handle @so_br { redir https://piloto.ultra-expansao.tech{uri} 302 }
        handle @so_ar { redir https://piloto-ar.ultra-expansao.tech{uri} 302 }

        # 3) Nenhum pais: explicacao em portugues, nao 403 seco e MUITO menos o 404
        #    cru do Caddy. `portal/sem-acesso.html` TEM de existir antes deste bloco
        #    entrar no ar: enquanto o BLK-INTL-05 nao criar os grupos, este e' o caso
        #    dos 19 usuarios, ou seja, de 100% da empresa (spec §9).
        #    SEM `templates` aqui, de proposito: a pagina nao tem nada condicional e
        #    nao pode nem poder listar pais nenhum (spec §5.4).
        handle @sem_pais {
            rewrite * /sem-acesso.html
            file_server
        }

        # 4) Sobrou: DOIS OU MAIS paises. Este e' o portal, e e' o FALLBACK — nunca uma
        #    combinacao enumerada. E' o que faz este bloco crescer em N e nao em 2^N
        #    quando entrarem CO/MX/PE/PY (spec §3).
        handle {
            rewrite * /index.html
            templates
            file_server
        }
    }
}
```

> **As duas linhas que costumam sumir numa revisao apressada:** `templates` nos **dois** `handle` que
> servem o `index.html`, e as **duas remocoes incondicionais** de `X-Portal-*`. Sem a primeira, a
> filtragem por pais nao acontece; sem a segunda, ela acontece a favor de quem forjou o cabecalho.
> Ambas viraram assert no §7.4.

---

## 3. Como isto escala do 3º ao 6º país

**A escada é aceitável, e a defesa é esta.**

**O que se recusou.** Enumerar combinações. Para N países, os casos "vários" são `2^N − N − 1`: com 6
países isso é **57** blocos `handle`. Está fora de questão, e não é opinião — é o motivo pelo qual o
caso "vários" desta spec é o **fallback** e não uma lista.

**O que se escolheu, e como cresce.** Por país novo entram exatamente três coisas mecânicas:

1. um matcher `@so_<pais>` com 1 linha positiva e `N−1` negações;
2. um `handle @so_<pais> { redir https://piloto-<pais>.ultra-expansao.tech{uri} 302 }`;
3. um par `@tem_<pais>` / `request_header` (a linha do `set` **e** a da remoção incondicional — §2.3),
   mais um cartão dentro do seu próprio `if` no `index.html` (§5.4).

Total de `handle`: **N + 2** (linear). Total de linhas de matcher: ~N² — para N=6, cerca de **75
linhas** no bloco inteiro. É longo, não é complexo: cada linha diz uma coisa e nenhuma depende de
outra.

**Por que não generalizar mais.** Três caminhos foram considerados e recusados, com o motivo:

| Caminho | Por que não |
|---|---|
| Regex único sobre `Remote-Groups` que decide "exatamente um" (via `map` ou matcher `expression`/CEL) | Vira uma linha que **ninguém revisa de verdade**. Num arquivo que custa `critica-aprovada` por edição (`scripts/loop_guard.py:123`), o custo de revisão é o recurso escasso — não o número de linhas. E o modo de falha de um regex errado é **silencioso** (manda para o país errado); o da escada é **visível no primeiro login**. |
| Um serviço mínimo que calcula o destino | Um container novo **na porta de entrada** — nova causa de indisponibilidade total, novo digest para pinar, novo alvo. E contradiz o §1.2: "o portal não serve dado nenhum" deixaria de ser verdade por construção. |
| Deixar a página estática decidir em JS | O navegador não tem os grupos, e dar os grupos ao navegador é abrir a lista de países a quem não os tem. |

**O que transforma "escada" em "escada verificada".** O conjunto é **fechado e conhecido** (6 países,
um lançamento por vez, separados por semanas). O que torna a repetição segura não é a disciplina de
quem edita — é o teste do §7.4, que lê o `Caddyfile` e falha se algum `@so_<pais>` deixar de negar
todos os outros. **Reabrir esta decisão** se aparecer um 7º país fora da lista de 6, ou se a régua
deixar de ser "país" (ex.: acesso por região dentro de um país) — aí o eixo mudou e a forma tem de
mudar junto.

---

## 4. As três armadilhas

### 4.1 Armadilha A — o 301 já cacheado, e a migração

**O fato.** `Caddyfile:21` usa `permanent`, que é **301**. Navegadores cacheiam 301 de forma
agressiva e **sem prazo**: uma vez visto, o navegador nem pergunta ao servidor de novo. Consequências,
as duas:

- **Para frente:** se alguém que só tem o Brasil ganhar a Argentina depois, o navegador continua
  pulando direto para o piloto brasileiro e ele **nunca** vê o seletor. O acesso novo existe e é
  invisível.
- **Para trás, e é o pior:** **quem já visitou a raiz JÁ TEM o 301 guardado.** Trocar o `Caddyfile`
  não limpa cache de ninguém. Na virada, essas pessoas continuam caindo direto no Brasil.

**A resolução, em três partes.**

1. **`302` daqui em diante, sem exceção.** Nunca mais `permanent` nesta origem. Não é preferência: um
   301 é uma afirmação de que o destino nunca muda, e o destino deste host **é** função de quem
   pergunta. Reforçado por `header Cache-Control "no-store"` dentro do `route`.
2. **A saída para quem já tem o 301 envenenado — e ela é elegante:** a chave de cache HTTP **inclui a
   query string**. `https://ultra-expansao.tech/?escolher=1` é uma URL **diferente** de
   `https://ultra-expansao.tech/`, e portanto **nunca foi 301**. O mesmo `?escolher` da armadilha B é
   também o antídoto da armadilha A. **O aviso ao time divulga esse link, não a raiz nua.** Quem usar
   o link vê o seletor na hora, sem limpar nada; a partir daí o 301 velho deixa de importar porque a
   pessoa já sabe o caminho.
3. **Para quem insistir em digitar a raiz nua:** limpar os dados do site. O texto do aviso já traz o
   passo, sem jargão.

**Texto do aviso ao time — pronto para enviar, no dia do deploy:**

> **Mudou o endereço de entrada do Motor de Expansão**
>
> A partir de hoje, `ultra-expansao.tech` deixa de ser um atalho fixo para o piloto do Brasil e passa
> a ser a **porta de entrada de todos os países**. Salve **só** esse endereço.
>
> - Se você tem acesso a **um país**, nada muda na prática: você continua caindo direto nele.
> - Se você tem acesso a **mais de um**, vai aparecer uma tela para escolher.
> - Para **trocar de país sem deslogar**, use: **https://ultra-expansao.tech/?escolher=1**
>
> **Se ao abrir `ultra-expansao.tech` você for jogado direto no Brasil mesmo tendo outro país:** o seu
> navegador guardou o atalho antigo — ele era permanente e não expira sozinho. Duas saídas, escolha
> uma:
> 1. use o link **https://ultra-expansao.tech/?escolher=1** (funciona na hora, não precisa limpar nada); ou
> 2. limpe os dados do site: no Chrome, abra `ultra-expansao.tech`, clique no cadeado ao lado do
>    endereço → *Configurações do site* → *Excluir dados*, e recarregue.
>
> Se depois disso aparecer a tela dizendo que você não tem acesso a nenhum país, fale com o Felipe —
> é liberação de grupo, leva minutos.

### 4.2 Armadilha B — sair do país único sem deslogar

Quem cai direto no país único precisa de um caminho de volta ao seletor. **Sem isso o atalho vira
cela**: a única forma de trocar seria deslogar, e deslogar não muda os grupos — não resolveria nada,
só pareceria resolver.

**Resolução: `?escolher`.** O matcher `@escolher` é o **primeiro** `handle` dentro do `route` e
sobrepõe todos os outros de propósito, inclusive `@so_br`/`@so_ar`. Ele devolve o seletor sempre,
mesmo para quem tem um só país (nesse caso a página mostra um cartão só — e é a resposta certa: ela
diz, sem ambiguidade, "você tem acesso a um país").

**Duas obrigações que vêm junto:**

1. **A própria página do seletor tem de linkar para ela mesma.** Cada país no `index.html` é um link
   para `https://piloto[-xx].ultra-expansao.tech/`; a página precisa também de um rodapé com um
   **`<a href="/?escolher=1">` clicável** (não um `<code>` para a pessoa transcrever — o endereço é
   justamente o que ela precisa guardar, e transcrever é onde a grafia se perde). Entregue em
   `portal/index.html` e em `portal/sem-acesso.html`. E **o piloto** deveria ganhar um link de volta
   ("trocar de país") apontando para `https://ultra-expansao.tech/?escolher=1` — isso é `web/` e
   **não é escopo desta spec**; fica anotado no §10 como item adjacente, com dono a definir.
2. **A forma canônica é `?escolher=1`, e é a única grafia publicada.** O matcher está escrito
   `@escolher query escolher=*` — chave presente com qualquer valor. O curinga do matcher `query`
   casa também o **valor vazio** (`paramVal[0] == v || v == "*"`), então `?escolher` nu funciona;
   confirmado na documentação do Caddy, **a confirmar por execução** no §7.2 item 7. Mesmo assim
   **tudo o que for publicado usa `=1`**: aviso ao time (§4.1), rodapé das duas páginas e §7.2. Uma
   grafia só — este link é o antídoto da armadilha A, e o dia da virada é o pior momento para duas
   versões de um endereço circularem.

### 4.3 Armadilha C — a raiz deixa de ser atalho para o Brasil

**É mudança visível, é o efeito desejado, e precisa estar dita antes de acontecer.** Quem tinha a raiz
salva esperando o piloto brasileiro passa a ver o seletor — ou continua caindo direto, se tiver só o
Brasil, que é o caso da maioria hoje (19 usuários, todos em `ultra_team`).

**O que reduz o impacto a quase zero, e por que:** depois do BLK-INTL-05 **todos os 19 recebem
`expansao_br`** (§9), e só quem precisar da Argentina recebe `expansao_ar`. Logo, **no dia da virada a
esmagadora maioria cai em `@so_br`** e o comportamento observável é idêntico ao de hoje — a menos do
código 302 no lugar do 301, que é invisível para o usuário.

**O que não se deve fazer:** manter um alias tipo `br.ultra-expansao.tech` ou uma "raiz legada" que
continue mandando todo mundo para o Brasil. Seria um segundo endereço a manter, com um segundo
comportamento, e ressuscitaria exatamente o problema de decorar subdomínio que o portal existe para
matar.

**O que fica registrado como aceito:** por alguns dias haverá gente perguntando "por que apareceu essa
tela". A resposta é o aviso do §4.1, enviado **no mesmo dia** do deploy — não depois.

---

## 5. Onde a página estática mora

### 5.1 Por que não cabe em nenhum volume existente

O container do `caddy` tem quatro volumes (`docker-compose.prod.yml:268-274`) e **nenhum serve**:

| Volume | Linha | Por que não |
|---|---|---|
| `./Caddyfile:/etc/caddy/Caddyfile:ro` | 269 | é um **arquivo**, não um diretório |
| `caddy_data:/data` | 270 | volume nomeado que o **Caddy administra** (certificados, estado do ACME). Escrever conteúdo nosso ali é sequestrar o diretório de estado de outro programa |
| `caddy_config:/config` | 271 | idem — o `autosave.json` do Caddy vive aqui |
| `/opt/motor-expansao/logs/caddy:/var/log/caddy` | 274 | diretório de log, com rotação do próprio Caddy (`Caddyfile:60-67`) |

> **Alternativa considerada e recusada:** embutir o HTML no próprio `Caddyfile` com `respond` e string
> entre crases. Funciona, e **não exigiria mexer no compose**. Recusada porque colaria a **cópia** da
> página (que muda com frequência e é de baixo risco) ao **roteamento** (que é CRITICO e custa
> `critica-aprovada` por edição — `scripts/loop_guard.py:123`). Cada ajuste de texto passaria a exigir
> a label do Felipe. Fica anotada como o plano B se, por algum motivo, o bind mount não puder entrar.

### 5.2 A decisão: `portal/` na raiz do repo, montado read-only

**Dois arquivos novos**, sem assets externos, sem JS, sem fonte remota — **os dois entregues**:

```
portal/
  index.html        # o seletor (com os `if` por país do §5.4 + o ramo "sem acesso" do ?escolher)
  sem-acesso.html   # a explicação de quem não tem país nenhum, sem listar país nenhum
```

**Os dois são obrigatórios, e o segundo não é acessório.** O `handle @sem_pais` do §2.3 faz
`rewrite * /sem-acesso.html`; se o arquivo não existir, o `file_server` devolve o **404 cru do Caddy,
em inglês**, e — enquanto o BLK-INTL-05 não criar os grupos — isso é o que 100% da empresa vê ao abrir
a raiz (§9). Trocar um 403 seco por um 404 em inglês seria piorar exatamente a coisa que o §1.1 existe
para consertar.

**Uma linha nova no compose**, no serviço `caddy` (`docker-compose.prod.yml:268-274`), irmã da que já
monta o `Caddyfile`:

```yaml
      - ./portal:/srv/portal:ro                                 # portal de selecao de pais (spec docs/spec_portal_selecao_pais.md)
```

O bind relativo funciona porque na VPS o repo está em `/opt/motor-expansao/app`
(`docs/infra_producao.md:772`, `:824`) — é o mesmo mecanismo que já entrega `./Caddyfile` (269) e
`./authelia` (288). **Não é volume novo de classe nova; é irmão de dois que já existem.**

### 5.3 A linha do `.dockerignore` que é obrigatória, e não opcional

`Dockerfile.web:43` e `Dockerfile.api:33` fazem `COPY . .`. **Um diretório novo na raiz entra nas duas
imagens por padrão** — exatamente o que a restrição "este portal não pode inflar a imagem de país
nenhum" proíbe. O padrão para evitar isso já existe no arquivo (`.dockerignore:39-42`, seção
*"Configurações de deploy (montados via volume)"*, com `Caddyfile`, `authelia/` e `.env`). A entrada
nova vai **nessa seção**:

```
# Configurações de deploy (montados via volume)
Caddyfile
authelia/
portal/
.env
```

Sem essa linha o portal **passa** no aceite funcional e **falha** na restrição — é o tipo de coisa que
só aparece meses depois, num `docker history`. Por isso o §7.5 é um teste, não uma lembrança.

### 5.4 Como a página sabe quais países mostrar

A página é estática e **não tem como saber** os grupos do usuário — a menos que o Caddy conte a ela.
Conta, com peças de fábrica e sem serviço novo:

1. Dentro do `route`, `request_header @tem_br X-Portal-Br 1` marca a **requisição** (não a resposta) —
   precedido das duas remoções incondicionais que fecham o spoof (§2.3).
2. A diretiva `templates` no `handle` faz o Caddy executar o arquivo servido como template Go, com o
   objeto `.Req` disponível. **Ela é requisito de funcionamento, não gancho opcional** — ver "o modo
   degradado não existe", abaixo.
3. No `index.html`, o teste é uma string vazia ou não — semântica de fábrica do template Go, sem
   função auxiliar nenhuma. As duas leituras ficam em **variáveis no topo do `<body>`**, para o
   cabeçalho ser lido uma vez e a condição de "nenhum país" poder ser escrita como `or`:

```html
{{- $br := .Req.Header.Get "X-Portal-Br" -}}
{{- $ar := .Req.Header.Get "X-Portal-Ar" -}}
{{if or $br $ar}}
  <ul class="grade">
    {{if $br}}<li class="pais pais--br">… cartão do Brasil …</li>{{end}}
    {{if $ar}}<li class="pais pais--ar">… cartão da Argentina …</li>{{end}}
  </ul>
{{else}}
  <section class="sem-acesso">… mesma explicação de sem-acesso.html, sem nomear país …</section>
{{end}}
```

**Um mecanismo só, e é este.** `X-Portal-*` é o **único** canal pelo qual a página sabe de países. A
página **não** lê `Remote-Groups`. Os dois chegam ao Caddy e os dois funcionariam; `X-Portal-*` foi
escolhido por três motivos verificáveis:

- **o anti-spoof fica legível**: são as duas remoções incondicionais do §2.3, e cabem numa revisão de
  arquivo CRITICO. Com `Remote-Groups` a defesa passa a depender de o leitor saber que `copy_headers`
  faz `set` e não `add`;
- **desacopla a página do formato do `Remote-Groups`** (hoje `a,b,c` sem espaço) — a página não
  precisa saber separar lista nenhuma, nem sobreviver a um `a, b, c` futuro;
- **nada vindo do usuário é interpolado no HTML.** `{{.Req.Header.Get "Remote-Groups"}}` cru injetaria
  o **nome do grupo** no documento, e `templates` executa como template de **texto**, sem escape de
  HTML: um grupo com `'`, `"` ou `<` quebraria o atributo e, no limite, o documento. Os nomes vêm de
  um arquivo administrado, então não é vetor de usuário — é um modo de falha calado que sai de graça
  ao não injetar nada. O assert 10 do §7.4 fecha o resto com uma regex de nome de grupo.

**O caso que os dois artefatos precisam cobrir junto: `?escolher=1` sem nenhum país.** `@escolher`
vence `@sem_pais` de propósito (§4.2), então esse usuário recebe o `index.html`, **não** o
`sem-acesso.html`. Sem o ramo `else` acima ele veria uma **grade vazia, sem explicação nenhuma** — o
pior dos estados, porque não diz nem que está tudo bem nem o que fazer. Por isso o `index.html`
carrega o mesmo bloco de explicação, com o mesmo texto do `sem-acesso.html` e **sem nomear país
nenhum** (é o mesmo usuário do §6.2). Verificado pelo item 12 do §7.2.

**O modo degradado não existe, e essa é a decisão.** Sem `templates`, a página sai com as ações de
template em texto e ninguém vê cartão nenhum: falha **alta e visível na primeira requisição**. A
alternativa — degradar para "lista todos os países" — foi recusada: ela é silenciosa e insegura ao
mesmo tempo, porque mostra o roteiro de expansão a quem não tem acesso a país nenhum e oferece portas
que devolvem 403. **Entre falhar barulhento e vazar calado, falha barulhento.** O assert 9 do §7.4
verifica que os dois `handle` que servem o `index.html` têm a diretiva.

**Requisitos da página** (valem para os dois arquivos):

- HTML e CSS inline, **zero** script, **zero** asset externo — a CSP do bloco (`default-src 'none'`)
  bloqueia qualquer um, de propósito.
- Rodapé com o link `?escolher=1` **clicável** (`<a href="/?escolher=1">`, não um `<code>` para
  transcrever) e a frase de como pedir acesso.
- **A frase de suporte é uma só, e é esta:** *"Fale com o Felipe — é liberação de grupo, leva
  minutos."* É o mesmo destinatário que o aviso do §4.1 já publica; ficar genérico ("o time
  responsável") obrigaria a pessoa a descobrir a quem perguntar exatamente no momento em que ela não
  consegue entrar. **Se o Felipe indicar um canal (e-mail, grupo interno), troca-se nos três lugares
  ao mesmo tempo**: aviso do §4.1, `index.html` e `sem-acesso.html`.
- **Filtragem é de RENDERIZAÇÃO, nunca de CSS.** Um cartão que o usuário não pode abrir **não é
  emitido**; `display:none` sobre conteúdo controlado por permissão está proibido nestes dois
  arquivos. Esconder por CSS deixa o nome e o host do país no corpo HTTP — que é exatamente o
  vazamento que o §6.2 fecha ao exigir `one_factor` na raiz, e o que os aceites 6, 8 e 9 do §7.2
  verificam com `grep` sobre o corpo.
- **Comentário HTML viaja no corpo.** Nenhum comentário destes arquivos pode nomear um país, um host
  `piloto-<pais>` ou um grupo `expansao_<pais>` concreto — o `grep` dos aceites 6, 8 e 9 não distingue
  comentário de conteúdo, e o leitor humano que abrir "ver código-fonte" também não. O bloco de Caddy
  concreto, com os nomes reais, mora aqui no §2.3; a página aponta para cá em vez de repeti-lo.
- `sem-acesso.html` **não** lista país nenhum: diz que a conta está sem acesso atribuído e a quem
  pedir. Listar países ali devolveria o vazamento que o §6.2 fecha. Ele também **não** recebe
  `templates` — não tem nada condicional, e não ter a diretiva é uma garantia a menos para revisar.
- `templates` só aparece nos dois `handle` do portal. **Nunca** num `handle` que faz `reverse_proxy` —
  ali ele passaria a executar a resposta do upstream como template.

---

## 6. O que muda no Authelia

### 6.1 `default_redirection_url` — `authelia/configuration.yml:59`

```yaml
# antes
      default_redirection_url: https://dashboard.ultra-expansao.tech
# depois
      default_redirection_url: https://ultra-expansao.tech
```

**Por quê.** É para onde o Authelia manda quem faz login direto em `auth.ultra-expansao.tech` sem um
destino pedido. Hoje ele manda para o `dashboard`, que — desde a DEC-022 — é só um
`redir … permanent` para o piloto brasileiro (`Caddyfile:44-46`). Ou seja: **o login pousa no Brasil,
por hardcode, com um 301 no meio.** Com o portal existindo, o pouso certo é o portal.

**Bônus não óbvio:** trocar o valor **contorna** um segundo 301 envenenado. O redirect do `dashboard`
também é `permanent` (`Caddyfile:45`); apontar o pouso para outro host sai fora dessa entrada de cache
em vez de tentar consertá-la.

### 6.2 A raiz precisa de regra de `access_control` — `authelia/configuration.yml:80-86`

`default_policy: deny` (`:81`) e não há regra para a raiz. **Sem regra nova, o `forward_auth` da raiz é
negado** e o usuário toma um erro cru, sem nem ver tela de login. Acrescentar, **antes** das duas
regras que já existem:

```yaml
access_control:
  default_policy: deny
  rules:
    # A raiz e' o PORTAL DE SELECAO DE PAIS (docs/spec_portal_selecao_pais.md). Precisa de
    # login por DOIS motivos, e os dois valem:
    #  (1) sem login o Authelia nao entrega Remote-Groups, e o portal nao teria como saber
    #      para onde mandar — todo visitante cairia no caso "sem pais";
    #  (2) `bypass` faria a pagina do seletor ser publica, e ela DIZ QUAIS PAISES EXISTEM.
    #      Isso e' o roteiro de expansao internacional, aberto a quem digitar o dominio.
    # `domain` casa o host EXATO no Authelia (nao pega subdominio sem `*.`), entao esta
    # regra nao alarga nada.
    - domain:
        - ultra-expansao.tech
        - www.ultra-expansao.tech
      policy: one_factor
    - domain: dashboard.ultra-expansao.tech
      policy: one_factor
    - domain: piloto.ultra-expansao.tech
      policy: one_factor
```

**Fica de fora desta spec:** a regra de `piloto-ar.ultra-expansao.tech`. Ela pertence ao
**BLK-INTL-08 (Bloco E)**, que sobe o host argentino, não a este. Está listada no §10 (item 13) como
adjacente, para não ser esquecida — **um portal que aponta para um host sem regra manda a pessoa para
um 403; um portal que aponta para um host que nem existe no `Caddyfile` manda a pessoa para um erro
de TLS.** É por isso que o §9 fixa `BLK-INTL-08` **antes** deste bloco.

### 6.3 O que **não** muda — e é bom que não mude

`session.cookies[0].domain` já é `ultra-expansao.tech` (`authelia/configuration.yml:57`), o **apex**.
Cookie de apex vale para o apex e para todos os subdomínios: a sessão SSO **já funciona na raiz** e
continua valendo ao pular para `piloto` ou `piloto-ar`. **Nenhuma mudança de sessão é necessária** — e
isso é o que garante que o pulo do portal para o país é instantâneo, sem segunda tela de login.

Também não mudam: `expiration: 8h` (`:20`), `inactivity: 30m` (`:41`) e `remember_me: 8h` (`:55`). O
comentário das linhas 17-55 conta o incidente de 06/08/2026, quando mexer nesses números derrubou o
login da rede inteira por ~4h. **Este bloco não os toca, e nenhuma implementação deste portal tem
motivo para tocá-los.**

---

## 7. Critério de aceite

### 7.1 Antes de qualquer reload — sintaxe e versão

```bash
# LOCAL (precisa de docker; nesta maquina de spec nao havia — por isso e' passo de aceite)
docker run --rm -v "$PWD/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2-alpine \
  caddy validate --adapter caddyfile --config /etc/caddy/Caddyfile
docker run --rm -v "$PWD/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2-alpine \
  caddy fmt --diff /etc/caddy/Caddyfile      # esperado: diff VAZIO

# NA VPS (guardrail do CLAUDE.md §6: UM comando por vez, com confirmacao explicita)
cd /opt/motor-expansao/app
docker compose -f docker-compose.prod.yml exec caddy caddy version   # ANOTAR NO PR (§0, item 1)
docker compose -f docker-compose.prod.yml exec caddy caddy validate --config /etc/caddy/Caddyfile
docker compose -f docker-compose.prod.yml up -d caddy    # o bind ./portal e' novo -> recriar, nao `reload`
```

> `caddy reload` **não basta neste deploy**: o volume `./portal` é novo e volume só entra na recriação
> do container. Nos deploys **seguintes**, que só mudem o `Caddyfile` ou o HTML, `reload` (ou nada, no
> caso do HTML — o bind é ao vivo) resolve.

### 7.2 Comportamento, com sessão real

Com `C='authelia_session=<cookie de uma sessao valida>'`:

| # | Comando | Esperado |
|---|---|---|
| 1 | `curl -sSI https://ultra-expansao.tech/ \| head -1` | **302** (sem cookie) |
| 2 | `curl -sSI https://ultra-expansao.tech/ \| grep -i '^location'` | aponta para **`auth.ultra-expansao.tech`** — **jamais 200**, senão a lista de países é pública (§6.2) |
| 3 | *(usuário só com `expansao_br`)* `curl -sSI -H "Cookie: $C" https://ultra-expansao.tech/` | `HTTP/2 302` + `location: https://piloto.ultra-expansao.tech/` |
| 4 | mesma requisição, `grep -c 301` | **0**. Se der 1, o `permanent` sobreviveu — falha dura |
| 5 | *(usuário com `expansao_br` **e** `expansao_ar`)* mesma requisição | `HTTP/2 200`, e o corpo tem **os dois** cartões |
| 6 | *(usuário só com `expansao_br`)* `curl -sS -H "Cookie: $C" 'https://ultra-expansao.tech/?escolher=1'` | `200`, corpo com **um** cartão (Brasil), **nenhuma** menção à Argentina |
| 7 | idem com `'…/?escolher'` (sem valor) | `200`. **Se der 302, anotar no PR** que `query escolher=*` exige valor nesta versão — e manter `?escolher=1` como forma canônica (§4.2) |
| 8 | *(usuário sem grupo `expansao_*`)* `curl -sS -H "Cookie: $C" https://ultra-expansao.tech/` | `200` com `sem-acesso.html`. **Sem** nome de país nenhum no corpo — `grep -ci 'brasil\|argentina\|piloto'` tem de dar **0**, e o `grep` vale para os comentários HTML também (§5.4) |
| 9a | `curl -sS -H "Cookie: $C" -H 'Remote-Groups: expansao_ar' 'https://ultra-expansao.tech/?escolher=1'` *(usuário só com BR)* | corpo **sem** o cartão da Argentina. **Este é o vetor real**: `Remote-Groups` é o cabeçalho que o cliente pode forjar e que o `copy_headers` do `forward_auth` sobrescreve (`set`, não `add`) |
| 9b | idem com `-H 'X-Portal-Ar: 1'` | corpo **sem** o cartão da Argentina — prova as duas remoções incondicionais do §2.3. **Sozinho este teste não prova nada** (nada garantiria que a página lê esse cabeçalho); ele só tem valor ao lado do 9a |
| 10 | `curl -sSI -H "Cookie: $C" https://ultra-expansao.tech/ \| grep -i 'cache-control'` | `no-store` |
| 11 | `curl -sSI -H "Cookie: $C" https://ultra-expansao.tech/ \| grep -i 'content-security-policy'` | presente, `default-src 'none'` |
| 12 | *(usuário sem grupo `expansao_*`)* `curl -sS -H "Cookie: $C" 'https://ultra-expansao.tech/?escolher=1'` | `200` com o `index.html` no ramo "sem acesso": a **explicação em português**, **nenhum** cartão, **nenhum** nome de país. É o caso em que `@escolher` vence `@sem_pais` (§4.2) e o único que não passa pelo `sem-acesso.html` — sem o ramo `else` do §5.4 daria uma grade vazia |
| 13 | `curl -sS -H "Cookie: $C" 'https://ultra-expansao.tech/?escolher=1' \| grep -c '{{'` | **0**. Se der mais que 0, `templates` não está ligado num dos dois `handle` e a página saiu crua (§5.4) |

**Passo manual que nenhum `curl` cobre (é o ponto inteiro da armadilha A):** num navegador que **já
visitou a raiz antes da mudança**, abrir `https://ultra-expansao.tech/` e observar o comportamento; se
pular direto, confirmar que **`?escolher=1` funciona sem limpar cache**. É esta observação que valida o
texto do aviso do §4.1 — e ela precisa ser feita antes de o aviso ser enviado.

**Receita de depuração (temporária, remover depois).** Se os matchers não casarem, o suspeito nº 1 é o
cabeçalho não estar chegando. Colar como **primeiro** `handle` dentro do `route`:

```caddy
        handle /_debug_grupos {
            respond "user={http.request.header.Remote-User} grupos={http.request.header.Remote-Groups}" 200
        }
```

Corpo vazio em `grupos=` prova que ou o `forward_auth` não rodou antes (armadilha do §2.1) ou os
grupos ainda não existem (§9). **Este bloco não pode ser mergeado** — ele expõe identidade em texto.

### 7.3 Governança

`python scripts/loop_guard.py` sobre o diff deve acusar **CRITICO** para `Caddyfile`,
`docker-compose.prod.yml`, `.dockerignore` e `authelia/configuration.yml`. **Se não acusar, o guard
está quebrado** — e isso é um bug maior que este bloco.

### 7.4 Teste novo — `tests/unit/test_caddy_portal_paises.py`

É o que converte a escada do §3 de disciplina em verificação. Lê o `Caddyfile` (e, nos dois últimos,
o `users_database.yml` e as páginas) como texto e afirma:

1. para **cada** `@so_<pais>` encontrado, existe **uma** linha `not header Remote-Groups *expansao_<outro>*`
   para **cada** outro país declarado — a escada nunca fica pela metade;
2. o bloco raiz **não** contém a palavra `permanent`;
3. cada `handle @so_<pais>` redireciona com **`302`** explícito;
4. o `handle @escolher` é o **primeiro** `handle` dentro do `route` (a única ordem que importa, §2.2);
5. `forward_auth` aparece **antes** de qualquer `handle` dentro do `route` (armadilha §2.1);
6. **nenhum grupo `expansao_*` do `authelia/users_database.yml` é substring de outro** (armadilha do
   curinga, §2.2);
7. `portal/` está no `.dockerignore` (§5.3);
8. `portal/index.html` não referencia `http://` nem `https://` fora dos hosts `*.ultra-expansao.tech`
   (a CSP `default-src 'none'` bloquearia, e é melhor falhar no CI que no ar);
9. **os dois `handle` que servem `/index.html` contêm a diretiva `templates`** — o `handle @escolher` e
   o `handle` de fallback. Sem ela a filtragem por país simplesmente não acontece, e o modo de falha é
   uma página crua servida a todo mundo (§5.4). No mesmo assert: `templates` **não** aparece no
   `handle @sem_pais` nem em nenhum `handle` que faça `reverse_proxy`;
10. **todo grupo do `users_database.yml` casa `^[a-z0-9_]+$`** — uma linha de regex que fecha, junto
    com o assert 6, as duas armadilhas de nome de grupo: a do curinga de substring (§2.2) e a de um
    nome com `'`, `"` ou `<` chegar a um contexto que o trate como texto. Nada é interpolado no HTML
    hoje (§5.4), e este assert é o que impede que volte a ser sem ninguém perceber;
11. **nenhuma das duas páginas de `portal/` esconde conteúdo de país por CSS**: nem `display:none`
    sobre `.pais`, nem seletor de classe sobre grupo (`[class*="expansao_"]`). Filtragem é de
    renderização (§5.4) — este assert é o que impede o vazamento do §6.2 de voltar como "só um
    `display:none`";
12. **fora dos blocos `if` por país, `portal/index.html` não contém nome de país nem host
    `piloto-<pais>`**, e `portal/sem-acesso.html` não os contém em lugar nenhum — **comentário HTML
    incluído**, porque ele viaja no corpo (§5.4). É a versão em CI dos aceites 6, 8 e 9 do §7.2.

### 7.5 Definição de pronto

Os 14 itens do §7.2 verdes (1-8, 9a, 9b, 10-13) · o passo manual do navegador feito · `loop_guard`
acusando CRITICO · os **12 asserts** do §7.4 verdes · **o aviso do §4.1 enviado no mesmo dia** ·
versão do Caddy anotada no PR.

---

## 8. Criticidade e governança

- **Classe: CRITICO.** Quatro dos arquivos alterados casam a lista CRITICO do guard:
  `docker-compose` (`scripts/loop_guard.py:122`), `Caddyfile` (`:123`), `^authelia/` (`:124`) e
  `.dockerignore` (`:121`).
- **Exige a label `critica-aprovada` do próprio Felipe** para merge. Pela DEC-016 (`CLAUDE.md:144`),
  Baixa/Média fazem auto-merge com 4 checks verdes; **Crítica não** — o merge segue humano, e a label
  é do dono, não do revisor.
- **Não é `loop-safe`.** Pelo critério do `CLAUDE.md:141`, um bloco que toca VPS/deploy nunca pode ser
  `loop-safe`. **Não colocar** a linha `| **Autonomia** | loop-safe |` na tabela deste bloco em
  `tasks/backlog.md` — é essa ausência que mantém o loop fora daqui.
- **Deploy manual, sempre** (`CLAUDE.md:131-137`, §6). Aqui não há imagem para pinar por digest — o
  `caddy` não é imagem nossa — então o análogo do digest é o §7.1: **anotar a versão do Caddy no PR**,
  para que "o que estava no ar" seja recuperável depois. Guardrail absoluto do §6 vale integralmente:
  **um comando por vez na VPS, com confirmação explícita para cada um.**
- **`portal/` deveria entrar como GOVERNANCA no guard**, não CRITICO: é conteúdo servido em produção,
  mas não decide roteamento nem acesso. Entrada sugerida em `_DENY_GOVERNANCA`
  (`scripts/loop_guard.py:163-201`), na vizinhança do `^web/` (`:184`):
  `(r"^portal/", "portal de selecao de pais servido na raiz")`.
  Sem isso, o loop pode editar a página da porta de entrada dentro de um bloco "Média" auto-mergeável.
- **Rollback**: reverter os quatro arquivos e `docker compose … up -d caddy authelia`. É barato — não
  há estado, não há migração de dado, e nenhuma imagem de aplicação é tocada. **O que não volta com o
  rollback é o cache do navegador**: quem já pegou o 302 não fica preso (302 não é cacheado), então o
  rollback é limpo nos dois sentidos. É mais um motivo para o 302 além da armadilha A.

---

## 9. Dependência: os grupos não existem ainda

**O fato.** `authelia/users_database.yml` tem **19 usuários, todos e apenas** em `ultra_team`
(`:12`, `:19`, `:26`, … `:138`). **Nenhum `expansao_br`, nenhum `expansao_ar`.** Os grupos por país
nascem no **BLK-INTL-05 (Bloco D)**.

**O que acontece se o portal subir antes.** `Remote-Groups: ultra_team` não casa `*expansao_*`, então
`@sem_pais` casa para **todos**. **Os 19 usuários veem a tela de "sem acesso"** e a porta de entrada da
empresa vira um beco: o piloto só fica alcançável por quem digitar `piloto.ultra-expansao.tech` de
cabeça. É indisponibilidade total do caminho normal, sem erro no log, sem alerta.

**Ordem correta, e ela tem quatro passos:**

1. **BLK-INTL-05 primeiro.** `expansao_br` para **os 19** (aditivo — `ultra_team` **fica**, porque as
   duas regras de `access_control` que já existem não têm `subject` e portanto não dependem de grupo:
   remover `ultra_team` não quebraria nada hoje, mas é mudança sem necessidade num arquivo CRITICO).
   `expansao_ar` só para quem deve ter Argentina.
2. **Provar que os grupos chegam ao Caddy**, com a receita do §7.2: `grupos=` tem de trazer
   `ultra_team,expansao_br`. **Não presumir** — é justamente esta suposição que o §2.1 mostra
   falhando de forma silenciosa.
3. **O host argentino, que é o BLK-INTL-08 (Bloco E)** — `piloto-ar.ultra-expansao.tech` no
   `Caddyfile` **e** a regra de `access_control` correspondente (§6.2). Hoje o `Caddyfile` tem cinco
   hosts (linhas 19, 24, 32, 49, 54) e nenhum é o argentino, e o `access_control` tem duas regras
   (`authelia/configuration.yml:82-86`). **Antes deste passo, `handle @so_ar` redireciona para um host
   que não existe** — o usuário toma erro de TLS/host desconhecido, que é pior de diagnosticar que um
   403 porque nem chega ao Authelia.
4. **Só então o portal** (este bloco).

**A ordem, em uma linha: `BLK-INTL-05` → `BLK-INTL-08` → `BLK-INTL-13`.** Os dois últimos escrevem no
**mesmo `Caddyfile`** e no **mesmo `docker-compose.prod.yml`**, os dois são CRITICO e os dois
serializam na label `critica-aprovada` do Felipe. **Quem escreve primeiro no `Caddyfile` é o
BLK-INTL-08** — ele acrescenta um bloco de host novo, que não toca as linhas 19-22; o BLK-INTL-13
substitui as linhas 19-22 depois, e já nasce apontando para um host que existe. Na ordem inversa há
conflito de merge garantido e uma janela em que o cartão da Argentina leva ao vazio.

**Se houver pressa — e há um jeito seguro de antecipar metade disto.** O trabalho da armadilha A (a
migração 301→302) é o que tem prazo longo, porque depende de cache de navegador esvaziando na cabeça
das pessoas. Dá para começá-lo **antes** do BLK-INTL-05, em duas etapas:

- **Etapa 1 — hoje, sem grupos, risco praticamente nulo.** Trocar **apenas** `permanent` por `302` em
  `Caddyfile:21` e enviar a primeira metade do aviso. Comportamento observável: **idêntico ao de
  hoje**. Ganho: o 301 envenenado para de ser criado a partir de agora, e a base de cache pára de
  crescer enquanto o resto é construído.
- **Etapa 2 — depois do BLK-INTL-05.** O bloco inteiro do §2.3, mais o Authelia do §6, mais a segunda
  metade do aviso.

Recomendo as duas etapas. Elas separam a mudança **arriscada** (roteamento por grupo) da mudança
**lenta** (cache), e deixam cada uma falhar sozinha.

---

## 10. Arquivos que mudam

**Deste bloco (BLK-INTL-13):**

| # | Arquivo | O quê | Classe |
|---|---|---|---|
| 1 | `C:\dev\motor-de-expansao\Caddyfile` | substituir as linhas **19-22** pelo bloco do §2.3 | **CRITICO** (`loop_guard.py:123`) |
| 2 | `C:\dev\motor-de-expansao\portal\index.html` | **novo, ENTREGUE** — o seletor, com um `if` por país e o ramo `else` de "sem acesso" (§5.4). Exige `templates` nos dois `handle` | novo (ver item 8) |
| 3 | `C:\dev\motor-de-expansao\portal\sem-acesso.html` | **novo, ENTREGUE** — a explicação, sem listar país nenhum e sem `templates` | novo (ver item 8) |
| 4 | `C:\dev\motor-de-expansao\.dockerignore` | +1 linha `portal/` na seção das linhas **39-42** | **CRITICO** (`loop_guard.py:121`) |
| 5 | `C:\dev\motor-de-expansao\docker-compose.prod.yml` | +1 volume `./portal:/srv/portal:ro` no serviço `caddy` (**268-274**) | **CRITICO** (`loop_guard.py:122`) |
| 6 | `C:\dev\motor-de-expansao\authelia\configuration.yml` | linha **59** (`default_redirection_url`) + regra da raiz em **80-86** | **CRITICO** (`loop_guard.py:124`) |
| 7 | `C:\dev\motor-de-expansao\tests\unit\test_caddy_portal_paises.py` | **novo** — os 12 asserts do §7.4 | teste |
| 8 | `C:\dev\motor-de-expansao\scripts\loop_guard.py` | +1 entrada `^portal/` em `_DENY_GOVERNANCA` (**163-201**), ao lado do `^web/` (`:184`) | GOVERNANCA |
| 9 | `C:\dev\motor-de-expansao\docs\infra_producao.md` | runbook: recriar `caddy` (não `reload`) no 1º deploy; como editar a página depois | doc |
| 10 | `C:\dev\motor-de-expansao\tasks\backlog.md` | abrir **BLK-INTL-13** sob a epic `BLK-INTL`, **sem** o marcador `loop-safe`, com `Depende de: BLK-INTL-05` | GOVERNANCA (`loop_guard.py:168`) |

**Fora deste bloco, mas que sem eles o portal aponta para o vazio:**

| # | Arquivo | O quê | Dono |
|---|---|---|---|
| 11 | `C:\dev\motor-de-expansao\authelia\users_database.yml` | grupos `expansao_br` (19 usuários) e `expansao_ar` | **BLK-INTL-05** |
| 12 | `C:\dev\motor-de-expansao\Caddyfile` | bloco do host `piloto-ar.ultra-expansao.tech` — **escreve ANTES deste bloco** no mesmo arquivo CRITICO (§9) | **BLK-INTL-08** (Bloco E) |
| 13 | `C:\dev\motor-de-expansao\authelia\configuration.yml` | regra `access_control` de `piloto-ar` | **BLK-INTL-08** (Bloco E) |
| 14 | `C:\dev\motor-de-expansao\web\` | link "trocar de país" → `https://ultra-expansao.tech/?escolher=1` dentro do piloto (§4.2, obrigação 1) | **a definir** |
| 15 | `C:\dev\motor-de-expansao\docs\plano_multipais.md` | ponteiro para esta spec | **outra pessoa** — não é editado por aqui |
| 16 | `C:\dev\motor-de-expansao\docs\decisions\DEC-0XX.md` | registrar a decisão do portal (recomendado). **Pegar o ID por `ls docs/decisions/DEC-*.md` no momento do commit, não na abertura da branch** — foi assim que a DEC-045 foi tomada debaixo do plano multipaís | a criar |
