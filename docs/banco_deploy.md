# Runbook — subir o banco na VPS

> Como o PostgreSQL/PostGIS entra em produção: ordem de subida, provisionamento dos papéis
> (D20), backup, restore e rollback. Complementa o [`banco_conexao.md`](banco_conexao.md),
> que descreve como o motor **fala** com o banco; aqui é como ele **passa a existir**.
>
> Fonte do esquema: repositório `banco-de-reservas`. Nenhum DDL nasce aqui.
> Versão: Setembro 2026 · Executor: Vinícius · Estado: §1 a §7 executados na VPS em 17/10/2026 e o §8 (ligar) em 23/10/2026 — desde então o RBAC do piloto BR vem do banco, e a autenticação própria (P19, `MOTOR_AUTENTICACAO_PROPRIA`) segue desligada; os crons do expurgo (§9.1) e do backup (§10) ficaram no crontab do usuário `deploy`, fora do caminho deste roteiro

## 0. A ordem importa — leia antes de qualquer comando

A sequência abaixo **não é sugestão de organização**. Trocar dois passos de lugar causa
indisponibilidade real:

> **`MOTOR_DATABASE_URL` é o ÚLTIMO passo, e só depois de os usuários existirem.**
> No instante em que ela é preenchida, o RBAC do banco assume o controle das abas
> (`banco_no_comando()` em `web/server/acesso.py`). O comportamento é *deny-by-default*:
> quem o Authelia autentica mas que **não tem linha em `usuarios`** não recebe capacidade
> nenhuma. Ligar a variável com a tabela vazia tranca **todo mundo para fora**, inclusive você.

O caminho de volta é curto e vale saber de antemão: esvaziar `MOTOR_DATABASE_URL` e recriar
o `web` (`up -d web`; um `restart` não relê o `.env`) devolve o piloto ao comportamento pré-banco em
segundos, sem rebuild. Ver §8. **Esse interruptor só existe até o corte do P19:** com a autenticação
própria ligada, sem banco ninguém entra.

E nada disto vai para a VPS sem ter rodado antes na máquina: o ensaio local está no **§1**.

## 1. Ensaio na máquina, antes da VPS

**Nada sobe sem ter rodado aqui primeiro.** A sequência das seções seguintes é escrita para a VPS,
mas o essencial dela — migrations do zero, provisionamento do D20, RBAC de ponta a ponta, dump e
restore — roda inteiro no PostgreSQL nativo desta máquina, sem Docker. O bloco `postgres` do
compose, o backup e o restore em cluster novo pedem Docker (§1.1).

### 1.1 O que o ensaio local prova, e o que não prova

| Cobre | Como |
|---|---|
| Migrations `000→016` num banco vazio | runner nativo, sem container |
| O script do D20 (papéis, `GRANT`, `ENABLE ALWAYS TRIGGER`) | `psql` local |
| A ordem do §0 — ligar a URL com `usuarios` vazia trancar todo mundo | backend local + `MOTOR_DEV_USUARIO` |
| RBAC por perfil: abas que aparecem e somem | mesma coisa |
| `conferir`: o motor concorda com o banco | runner nativo |
| Dump, checksum e **restore em base limpa** | `pg_dump`/`pg_restore` 18.4 locais |
| O papel `app` é mesmo incapaz do que não deve (F6.2) | `python -m motor_expansao.db privilegios` |
| Migrations do zero no PostGIS de produção, login de ponta a ponta, `conferir` (fora o D20) e as consultas do `privilegios` — **sem** o veredito dele como `app` | CI, em todo PR para a `main` (`scripts/ci/banco_de_ensaio.sh`, §1.5) |

O que o PostgreSQL nativo **não** cobre:

- o bloco `postgres` do compose subir de fato (tag da imagem, `healthcheck`, `shm_size`,
  `POSTGRES_INITDB_ARGS`, o caminho do volume e o initdb da imagem);
- a ordem de subida do `depends_on`;
- o `run_backup_banco.sh`, que é bash e fala com `docker exec`;
- o restore num **cluster novo** (o §1.4 restaura no mesmo cluster — ver §10).

Desde 24/10/2026 o CI cobre parte do primeiro item: sobe a mesma imagem do compose, com o
`shm_size`, o `POSTGRES_INITDB_ARGS` e o `tmpfs` lidos dele (§1.5). O `healthcheck`, o volume e o
`depends_on` continuam só no ensaio em Docker.

> **Isso deixou de ser hipotético em 13/10/2026.** O ensaio em Docker Desktop (cópia local do
> compose, imagem `web` da `main`, Caddy + Authelia de teste, do §4 ao corte do P19) achou **dois
> defeitos no bloco `postgres` que o ensaio nativo não tinha como ver**, ambos corrigidos no compose
> e travados em `tests/contracts/test_compose_banco.py`:
>
> 1. o volume montava em `/var/lib/postgresql/data`, e a imagem 18+ (PGDATA em
>    `/var/lib/postgresql/18/docker`) **recusa subir** assim — o `up -d postgres` morria no 1º boot;
> 2. o `10_postgis.sh` da imagem instalava `postgis_topology`, `fuzzystrmatch` e
>    `postgis_tiger_geocoder`, criava `template_postgis` e fixava `search_path` — e o `privilegios`
>    **reprovava** o banco recém-nascido. O compose agora esconde o initdb da imagem com `tmpfs`.
>
> E um terceiro no runbook: o restore em cluster novo (§10). Para mudança no bloco `postgres`,
> o ensaio em Docker é o que vale; o nativo continua servindo para migration e RBAC.

O que cobre esse resto, quando não houver Docker à mão:

1. `tests/contracts/test_compose_banco.py` trava as invariantes estruturais (as duas do ensaio de 13/10/2026 acima — volume na raiz e `tmpfs` sobre o initdb — e mais quatro: variável
   fail-closed documentada, sem porta no host, `web` não refém da saúde do banco, volume nomeado).
2. `docker compose config` na VPS **valida sem subir nada** — é o primeiro comando do §4, e falha
   barulhento em erro de sintaxe ou variável faltando.
3. `docker compose up -d postgres` **sozinho não toca no piloto**. Enquanto `MOTOR_DATABASE_URL`
   estiver vazia, nada consome o banco: o container sobe ao lado, isolado. Subir o serviço e ligar o
   banco no piloto são dois passos com riscos completamente diferentes, e é por isso que estão
   separados neste runbook.

Se quiser fechar também esses três, o caminho é Docker Desktop nesta máquina — aí o `docker
compose -f docker-compose.prod.yml up -d postgres` roda igual, e só as imagens `WEB_IMAGE`/
`API_IMAGE` precisariam de um valor qualquer para o compose interpolar.

### 1.2 Banco de ensaio — separado do de teste

Use um banco **novo**, e não o `teste_banco_v2` (o banco de teste em uso): o ponto do ensaio é
provar a sequência desde o zero, e um banco que já tem as migrations aplicadas não prova isso — e
um ensaio que dropa o banco de trabalho custa caro por nada.

**Na estação de desenvolvimento, PowerShell — não é o seu passo:**
```powershell
$PGBIN = "C:\Program Files\PostgreSQL\18\bin"
& "$PGBIN\createdb" -U postgres banco_de_reservas_ensaio
```

> **`PYTHONPATH` primeiro, ou o Python acha o pacote errado.** O projeto usa layout `src/`, e
> o `motor_expansao` instalado em modo editável aponta para o **checkout principal** — onde o
> módulo `db` também existe (está na `main` desde 01/09/2026), mas é o DE LÁ que roda, não o desta worktree. Estar dentro da worktree não basta:
> o diretório atual não expõe `motor_expansao`. Sem a linha abaixo o erro é
> silencioso: o comando roda o `db` do checkout principal sem aviso (até 01/09/2026, quando o módulo só existia na branch, era `No module named motor_expansao.db`).
>
> **Não conserte com `pip install -e .` daqui.** Isso repontaria o pacote para esta branch em
> todo o seu Python, e o trabalho no checkout principal passaria a importar código desta branch
> sem aviso nenhum. O `PYTHONPATH` vale só para o terminal onde você o define.

**Na estação de desenvolvimento, PowerShell — não é o seu passo:**
```powershell
$env:PYTHONPATH = "C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\.claude\worktrees\wt-db\src"
$env:MOTOR_DATABASE_URL_ADMIN = "postgresql://postgres:SENHA@localhost:5432/banco_de_reservas_ensaio"
python -m motor_expansao.db estado
python -m motor_expansao.db aplicar --simular
python -m motor_expansao.db aplicar
python -m motor_expansao.db conferir
```

Em seguida, o `sql/papeis-e-privilegios.md` do `banco-de-reservas` — por `psql` ou pelo Query Tool
do pgAdmin, tanto faz desde 02/09 —, exatamente como no
§6 — inclusive os blocos de validação e teste dele, e o de append-only **depois** do `ALTER TABLE`.

### O guardrail read-only, reposto (F6.2)

Provisionado o D20, prove que ele pegou — **com a credencial do `app`, não a de dono**:

**Na estação de desenvolvimento, PowerShell — não é o seu passo:**
```powershell
$env:PYTHONPATH = "C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\.claude\worktrees\wt-db\src"
$env:MOTOR_DATABASE_URL = "postgresql://app:SENHA@localhost:5432/banco_de_reservas_ensaio"
python -m motor_expansao.db privilegios
```

**Por que isto existe.** O piloto provava ser read-only de duas formas: AST sobre o `app.py` e
snapshot do filesystem em runtime. A segunda parou de valer no dia em que ele ganhou banco — um
`INSERT` não aparece em snapshot de arquivo. Ela não falhou: **deixou de cobrir, sem avisar**,
que é o pior jeito de uma rede de segurança sumir.

O que a repõe não é outro teste de código, é o **privilégio**: com o D20 de pé, a escrita
indevida deixa de ser improvável e passa a ser impossível. O comando confere, por catálogo e
sem escrever nada, que o papel do piloto não cria objeto, não escreve no histórico de
permissões, não altera nem apaga evento, não cria tabela temporária, não é dono das tabelas
auditadas — e que consegue o que precisa, inclusive a `USAGE` na sequence de `eventos`, cuja
falta só apareceria em runtime.

> **Rodando com a credencial de dono, quase tudo reprova — e é o esperado.** O dono pode tudo;
> é essa a razão de o piloto não usar a credencial dele. Se você conectar como `app` e ainda
> assim reprovar, o provisionamento não está completo.

### 1.3 Exercitar o RBAC sem Authelia

O backend aceita identidade de desenvolvimento quando não há `Remote-User` na frente:

**Na estação de desenvolvimento, PowerShell — não é o seu passo:**
```powershell
# Mesma ressalva do §1.2 — se este for um terminal NOVO, repita o PYTHONPATH.
$env:PYTHONPATH = "C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\.claude\worktrees\wt-db\src"

# Os artefatos vivem no CHECKOUT PRINCIPAL, nao aqui: eles sao gitignored e nao
# viajam para a worktree (1 parquet contra 11.252). Apontar para o `data/` daqui da'
# um piloto que sobe e nao carrega nada -- e o sintoma nao acusa a causa.
#
# Ler o diretorio do checkout principal e' seguro: o piloto e' READ-ONLY sobre os
# artefatos, e ha teste que trava isso (`test_leituras_nao_mutam_artefatos`).
$env:MOTOR_DATA_DIR = "C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\data"   # desde 21/10/2026 (#472), com esta env a subida também exige os insumos da renda e o carimbo k em staging\censo2022_hex_da_malha.parquet

# OBRIGATORIO desde o merge da main (Bloco A / DEC-047): com MOTOR_DATA_DIR definida,
# `resolver_perfil()` e FAIL-CLOSED e exige um `perfil.json` na RAIZ dela. O checkout
# principal NAO tem esse arquivo, e o sintoma nao e' tela vazia -- e' o `app.py` nao
# IMPORTAR, com `PerfilInvalidoError: perfil.json ausente em ...`, porque o perfil e'
# resolvido no import, uma vez por processo.
#
# ATENCAO: `data/perfil.json` NAO e' gitignored. Ele vai aparecer no `git status` do
# CHECKOUT PRINCIPAL (que esta noutra branch) -- e' passo de maquina, nao de repositorio,
# entao nao commite. Os perfis versionados vivem em `data/perfis/<PAIS>/perfil.json`.
Copy-Item "C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\.claude\worktrees\wt-db\data\perfis\BR\perfil.json" `
          "C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\data\perfil.json"

# NAO defina o MOTOR_CADASTRO_DIR: ele e' o SINAL DE PRODUCAO, e a presenca dele
# desliga a identidade de dev -- voce ficaria sem `Remote-User` e sem
# `MOTOR_DEV_USUARIO`. Se precisar do cadastro da Visao Executiva, ligue junto o
# override: $env:MOTOR_DEV_IDENTIDADE = "1"
$env:MOTOR_DATABASE_URL = "postgresql://app:SENHA@localhost:5432/banco_de_reservas_ensaio"
$env:MOTOR_DEV_USUARIO = "vinicius.teste"   # um login_usuario que exista em `usuarios`

# Sem esta, a aba de Acessos é 404 PARA TODOS — por construção, e não por defeito:
# a allowlist do painel é de env e vive fora do RBAC (emenda da DEC-027). Vazia =
# painel desligado. É ela que libera também a tela de administração de usuários.
$env:MOTOR_ACESSOS_ADMIN_USUARIOS = "vinicius.teste"

# SÓ se você também for exercitar o cadastro da Visão Executiva: `MOTOR_CADASTRO_DIR`
# é o SINAL DE PRODUÇÃO, e a presença dele DESLIGA a identidade de dev — você ficaria
# sem `Remote-User` e sem `MOTOR_DEV_USUARIO`, ou seja, sem identidade nenhuma.
# O override explícito reabre o modo de dev:
#   $env:MOTOR_DEV_IDENTIDADE = "1"

python -m uvicorn app:app --app-dir web/server --port 8899
```

Em outro terminal, a SPA — o Vite já faz proxy de `/api` para a `:8899`:

**Na estação de desenvolvimento, PowerShell — não é o seu passo:**
```powershell
cd web
npm run dev     # abre em http://localhost:5000
```

Duas travas impedem isso de vazar para produção: `MOTOR_DEV_IDENTIDADE` como override explícito e,
na ausência dele, a presença de `MOTOR_CADASTRO_DIR` — o sinal de produção — que faz a env de
desenvolvimento ser ignorada aconteça o que acontecer.

**Ensaie primeiro o modo de falha**, não só o feliz: ligue `MOTOR_DATABASE_URL` com a tabela
`usuarios` ainda vazia e confirme que ninguém entra. É o cenário do §0, e é melhor vê-lo aqui do que
na VPS.

Depois, um `MOTOR_DEV_USUARIO` de cada perfil, conferindo contra a matriz da migration `012`.

### Dois perfis ao mesmo tempo

A identidade em dev vem do `MOTOR_DEV_USUARIO` **do processo do backend**, então trocar de perfil
exigiria reiniciar. Comparar lado a lado é melhor, e sai com duas instâncias — o Vite lê a porta
e o alvo do proxy de env:

**Na estação de desenvolvimento, PowerShell — não é o seu passo:**
```powershell
# Terminal 1 — backend growth (vê tudo, inclusive a aba de Acessos)
$env:MOTOR_DEV_USUARIO = "vinicius.teste"
$env:MOTOR_ACESSOS_ADMIN_USUARIOS = "vinicius.teste"
python -m uvicorn app:app --app-dir "C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\.claude\worktrees\wt-db\web\server" --port 8899

# Terminal 2 — backend expansão (11 capacidades, sem carteira e sem Acessos)
$env:MOTOR_DEV_USUARIO = "ana.teste"
$env:MOTOR_ACESSOS_ADMIN_USUARIOS = ""
python -m uvicorn app:app --app-dir "C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\.claude\worktrees\wt-db\web\server" --port 8898

# Terminal 3 — SPA do growth
cd web; npm run dev                       # http://localhost:5000

# Terminal 4 — SPA da expansão
$env:MOTOR_WEB_PORT = "5001"
$env:MOTOR_API_URL  = "http://127.0.0.1:8898"
cd web; npm run dev                       # http://localhost:5001
```

Os dois backends compartilham o MESMO banco e o mesmo papel `app` — o que muda é só quem cada um
diz ser. É exatamente o recorte que se quer exercitar: a mesma aplicação, a mesma credencial de
banco, e o acesso decidido pela linha em `usuarios`.

> Cada terminal precisa do `PYTHONPATH`, do `MOTOR_DATA_DIR` (o do **checkout principal** — ver
> acima), da `MOTOR_DATABASE_URL` e do `PGPASSWORD` — env de PowerShell não atravessa janelas. E repare no
> `MOTOR_ACESSOS_ADMIN_USUARIOS` vazio no segundo: a aba de Acessos vive fora do RBAC, numa
> allowlist de env, então é assim que se prova que ela some (404, e o ícone nem aparece no Dock).

> **`strictPort` está ligado de propósito.** Se o Vite escolhesse outra porta em silêncio ao
> achar a 5001 ocupada, você olharia a tela do perfil errado sem nenhum sinal disso — e o teste
> inteiro passaria a medir outra coisa.

E, com um Growth, exercite a **administração de usuários** da aba de Acessos — ela só aparece com
o `MOTOR_ACESSOS_ADMIN_USUARIOS` preenchido: troque o perfil de
outra pessoa, desative e reative. Confira depois, no banco, que cada ação virou linha em `eventos`
com `id_usuario` = você e `entidade_id` = o alvo — se os dois vierem trocados, a auditoria responde
ao contrário e parece certa.

### 1.4 Ensaiar o restore

A parte do backup que precisa de prova não é o dump — é a volta.

**Na estação de desenvolvimento, PowerShell — não é o seu passo:**
```powershell
& "$PGBIN\pg_dump"    -U postgres -d banco_de_reservas_ensaio -Fc --no-owner -f ensaio.dump
& "$PGBIN\pg_restore" --list ensaio.dump | Out-Null
& "$PGBIN\createdb"   -U postgres banco_de_reservas_volta
& "$PGBIN\pg_restore" -U postgres -d banco_de_reservas_volta --no-owner ensaio.dump
& "$PGBIN\psql" -U postgres -d banco_de_reservas_volta `
    -c "select count(*) from usuarios;" `
    -c "select count(*) from perfil_permissoes_historico;"
```

Os números têm de bater com os do banco de origem. **Backup que ninguém restaurou é backup que
ninguém tem** — e é aqui, e não na VPS, que se descobre.

> **Este ensaio restaura no MESMO cluster, e por isso esconde um defeito.** Os papéis `app`,
> `auditoria` e `etl` são do cluster e continuam lá; num servidor novo eles **não existem**, e o dump
> não os leva. O caso do servidor perdido está no §10, "Restaurar num servidor novo".

Ao terminar, `dropdb` nos dois bancos de ensaio.

### 1.5 O banco de ensaio no CI (desde 24/10/2026)

O check obrigatório `test` tem um PostgreSQL de verdade. Depois da suíte unitária, que continua sem
nenhuma variável de banco, o passo **"Banco de ensaio — migrations do zero e integração contra o
PostGIS de produção"** roda `bash scripts/ci/banco_de_ensaio.sh verificar`, que:

1. sobe a MESMA imagem do serviço `postgres` do `docker-compose.prod.yml` (em 24/10/2026, `postgis/postgis:18-3.6`),
   com o `shm_size`, o `POSTGRES_INITDB_ARGS` e o `tmpfs` sobre o initdb lidos do compose — não há cópia
   para envelhecer. O banco é `banco_de_reservas_ensaio`, o dono é `reservas_owner`, a senha é aleatória
   a cada execução (mascarada no log, nunca gravada em arquivo) e a porta fica só em `127.0.0.1:55432`;
2. roda `db aplicar` no banco vazio: a cadeia inteira, da `000` até a última;
3. exige que o `db estado` feche — manifesto igual a registradas, sem `pendentes:` nem `ATENCAO`. O
   `estado` sai com código 0 mesmo com pendência, por isso quem confere é o script;
4. exige que um segundo `db aplicar` responda `nada a aplicar.`;
5. roda `tests/integration/test_login_ponta_a_ponta.py` com `MOTOR_BANCO_DE_ENSAIO_OBRIGATORIO=1`.

**Pular é falhar**, por duas travas: com a variável, todo pulo do teste por ambiente ausente vira falha,
com o mesmo motivo; e o script confere o junit no fim — zero pulados e pelo menos um teste rodado. Fora
do CI a variável não existe, e o teste continua pulando com o motivo escrito — desde que o terminal
não tenha uma URL de banco de ensaio (`MOTOR_DATABASE_URL_ADMIN` ou `MOTOR_DATABASE_URL`): com ela,
ele roda e escreve naquele banco (cria usuário, redefine senha, grava em `eventos`).

**O que fica de fora: o D20 e o banco com dados.** O D20 vive no `banco-de-reservas` e não é recriado no
CI — um D20 recriado provaria o recriado, e não o real. Sem ele, o teste cobra o que dá para cobrar: o
`db conferir` tem de reprovar **só** nas duas triggers de auditoria em `'O'` (o fail-closed do #447), com
extensões, os seis números da §0, o endurecimento das funções e o registro das migrations passando; e o
`db privilegios`, sem papel `app` para conectar, roda como dono e tem de reprovar **exatamente** pela
lista `PRIVILEGIOS_COMO_DONO_SEM_D20` do teste (10 itens porque o dono pode tudo, 3 da seção 2, 2 da
seção 6 e 2 da seção 7). Um problema a mais reprova o CI, porque reprovaria também na VPS. O veredito
de verdade do `privilegios`, conectado como `app`, continua manual (§1.2 e VPS). E a cadeia roda num
banco **vazio**: uma migration que só falha com linhas na tabela (`NOT NULL` sem default numa tabela
povoada, `CHECK` que o dado antigo viola) passa no CI e quebra no `db aplicar` da VPS. Esse ensaio
continua manual, sobre uma cópia com dados — por exemplo, a base temporária do teste de restauração
(§10).

**Custo:** de 35 a 50 s a mais no job `test` (cinco medições em 24/10/2026, na máquina e com a imagem já
baixada: 33, 39, 42, 45 e 49 s, duas no Python 3.11 do job); o grosso é o argon2 dos testes de `alinhar-senhas`. O download da imagem (~240 MB
comprimidos) corre em segundo plano, num passo anterior (`pre-baixar`), atrás da suíte unitária. A tag é
resolvida a cada execução, como num `docker compose pull`, e o digest que rodou sai no log
(`imagem resolvida: …`): uma reconstrução nova da tag no Docker Hub pode deixar o CI vermelho sem
mudança de código — é o aviso de que o próximo `pull` em produção também quebraria.

**A trava de destino do teste tem duas partes.** Ele recusa banco cujo nome não tenha `ensaio` ou `test`,
e recusa uma `MOTOR_DATABASE_URL` que aponte para outro servidor, porta ou banco que não o da
`MOTOR_DATABASE_URL_ADMIN` — é por ela que a aplicação escreve. O caso do §1.2, dono e `app` no MESMO
banco, segue aceito. Quem roda à mão e recebe `RECUSADO: MOTOR_DATABASE_URL …` aponta as duas para o
mesmo banco de ensaio, ou tira a variável do terminal. A trava tem teste próprio, que roda na suíte
comum, sem banco: `tests/integration/test_trava_de_destino_do_ensaio.py`. O `verificar` nem chega a
ela: ignora a `MOTOR_DATABASE_URL` do terminal (faz `unset` e avisa).

**Reproduzir na máquina** — Git Bash, na raiz da árvore, com o Docker no ar e o pacote desta árvore no
caminho:

**Na estação de desenvolvimento, Git Bash — não é o seu passo:**
```bash
PYTHONPATH="$PWD/src" CI_BANCO_NOME=ci_banco_ensaio_local \
  bash scripts/ci/banco_de_ensaio.sh verificar
CI_BANCO_NOME=ci_banco_ensaio_local bash scripts/ci/banco_de_ensaio.sh derrubar
```

- `CI_BANCO_NOME` tem de começar com `ci_banco_`: é a trava para o `derrubar` nunca apagar container
  alheio (o laboratório `motor_expansao_*` roda na mesma máquina);
- `CI_BANCO_PORTA` (padrão 55432) e `CI_BANCO_DIR` (log do download e junit) são opcionais;
  `CI_BANCO_IMAGEM` troca a imagem só fora do CI — por exemplo, para ensaiar contra o digest exato da
  VPS antes de um upgrade — e é recusada no Actions;
- o `verificar` recusa começar se já existir um container com o mesmo nome, e no fim o deixa no ar para
  inspeção; o `derrubar` o remove junto com o volume anônimo dos dados;
- com o banco fora do ar, o teste desiste em até 10 s.

**Ao acrescentar uma checagem ao `privilegios`** que o dono reprova por construção, inclua o rótulo dela
em `PRIVILEGIOS_COMO_DONO_SEM_D20` (`tests/integration/test_login_ponta_a_ponta.py`), com a causa ao
lado; senão o passo do banco no CI reprova, e a mensagem diz isso. Checagem nova do `conferir` que
dependa do D20 pede o mesmo no teste do `conferir`, que em 24/10/2026 só reconhece as triggers fora de `'A'`.

`scripts/ci/` é CRÍTICO no guard (§9.0): quem controla o script controla o veredito do `test`.

## 2. Pré-condições

- **O ensaio do §1 rodou inteiro nesta máquina.** Nada sobe sem isso, e a ordem não é negociável:
  migrations do zero, D20, RBAC por perfil (inclusive o modo de falha) e restore conferido.
- Fase 2 aprovada: `docker-compose.prod.yml` é **Crítico**, então o merge exige a label
  `critica-aprovada` (DEC-016).
- Imagem `web` já em produção com o módulo `motor_expansao.db`. Sem ela, o runner de migration
  não existe no container e o passo 5 falha.
- `psql` **não** é necessário no host: tudo roda dentro dos containers.

Os três papéis e por que eles são três, não um:

| Papel | Quem cria | Para quê | Onde a credencial vive |
|---|---|---|---|
| dono do schema | o próprio compose (`POSTGRES_OWNER_USER`) | DDL das migrations; é o `SECURITY DEFINER` das triggers do D19 | `.env` (`POSTGRES_OWNER_PASSWORD`), e **nunca** no ambiente do `web` |
| `app` | você, no passo 6 | tudo que a aplicação faz | dentro de `MOTOR_DATABASE_URL`; na instalação de 17/10/2026, também em `MOTOR_APP_DB_PASSWORD` no `.env`, que o compose não lê |
| `auditoria` | você, no passo 6 | ler `perfil_permissoes_historico` | fora do compose; uso manual (a senha ficou no `.env` como `MOTOR_AUDITORIA_DB_PASSWORD`, que o compose não lê) |

Dar ao piloto a credencial do dono anula o D19 em silêncio: a promessa de que a aplicação não
consegue apagar o próprio rastro depende inteiramente de ela **não ser dona** das tabelas.

## 3. Preencher o `.env`

Na VPS, em `/opt/motor-expansao/app/.env`, a partir do bloco do `.env.example`:

**No terminal da VPS:**
```bash
openssl rand -hex 24   # TRÊS vezes: dono, `app` e `auditoria`
```

> **São três, e o quarto papel não tem senha.** O script do §6 cria um terceiro papel — o **`etl`** —
> mas desde 28/09/2026 ele nasce **`NOLOGIN`**, justamente porque tem `TRUNCATE` em `municipios`,
> `distritos` e `bairros`, que o próprio script chama de "o privilégio mais destrutivo concedido neste
> schema". **Não há quarta senha a gerar nem a guardar.**
>
> A carga de referência que usa o `etl` roda a cada ~10 anos. Quando for a hora:
> `ALTER ROLE etl LOGIN PASSWORD '<gerada na hora>';`, e `ALTER ROLE etl NOLOGIN;` de volta ao
> terminar.

**No arquivo `.env` — não é comando, é conteúdo para editar:**
```dotenv
POSTGRES_DB=banco_de_reservas
POSTGRES_OWNER_USER=reservas_owner
POSTGRES_OWNER_PASSWORD=<gerado>
MOTOR_DATABASE_URL=
```

`MOTOR_DATABASE_URL` fica **vazia** por enquanto — é o passo 8.

> **APAGUE a linha legada `POSTGRES_DB=motor_expansao`**, que vem no bloco da API legada no topo do
> `.env.example`. Não basta escrever o bloco do banco depois dela: para o compose vale o **último**
> valor, mas os dois scripts de cron deste projeto (`run_expurgo_sessoes.sh` e `run_backup_banco.sh`)
> leem o `.env` com `grep … | head -1` — o **primeiro**. Com a legada no topo, os dois passam a
> apontar para um banco que não existe e falham todas as noites. Falham **alto** — o comando estoura, o
> script sai com erro e o log fica sem a linha de fim —, mas sem o monitor `banco` do §9 a falha fica só
> no log, e falha que ninguém lê se confunde com sucesso. Nada no
> `docker-compose.prod.yml` consome o bloco legado. Confirme com `grep -n '^POSTGRES_DB=' .env` — com
> **`-n`**, e não `-c`: o `-c` só conta linhas, e um `.env` em que sobrou **só a legada** também dá `1`.
> Tem de aparecer **uma** linha, com `banco_de_reservas`.

> **A senha do dono é gravada DENTRO do cluster no primeiro boot, e trocá-la aqui depois não a muda.**
> Por isso ela precisa estar definitiva **antes de qualquer `up`** — as do `app` e do `auditoria` só
> nascem no §6, muito depois, e podem ser decididas até lá. E note que o serviço
> `web` declara `depends_on: postgres`: um `up -d web` já sobe o banco e roda esse primeiro boot.

Gerar as senhas em hexadecimal não é preciosismo: caractere especial (`@ : / ?`) numa URL libpq
precisa de percent-encoding, e o sintoma de esquecer é um erro de *host não encontrado*, que manda
você procurar no lugar errado.

**`.env` mexido pede re-encriptação no SOPS+age.** Era pendência aberta do BLK-OPS-01 desde os
segredos da API/bot, fechada na instalação de 17/10/2026 (`secrets/env.enc.env` refeito no #462, já com as senhas do banco); repita a cada mudança do `.env`. **E o cifrado já venceu:** o de 17/10/2026 não tem a linha
`MOTOR_DATABASE_URL`, acrescentada ao `.env` no §8 em 23/10/2026, e restaurado como está subiria o piloto
com o banco desligado, sem erro nenhum. Refazê-lo é pela estação do Vinicius — o `sops` e a chave age
não ficam na VPS.

## 4. Subir o serviço

**Valide antes de subir.** `config` resolve o compose inteiro e não inicia nada — é onde erro de
sintaxe ou variável faltando aparece de graça, sem container envolvido. É também o único passo desta
seção que não tem equivalente no ensaio local (§1.1):

**No terminal da VPS:**
```bash
cd /opt/motor-expansao/app
docker compose -f docker-compose.prod.yml config --quiet && echo OK
```

**No terminal da VPS:**
```bash
docker compose -f docker-compose.prod.yml up -d postgres
docker compose -f docker-compose.prod.yml logs --tail 30 postgres
docker compose -f docker-compose.prod.yml ps postgres      # tem de dizer (healthy)
```

**Este passo não toca no piloto.** Enquanto `MOTOR_DATABASE_URL` estiver vazia, nada consome o
banco — o container sobe ao lado, isolado, e o `web` sequer o consulta. Subir o serviço e ligar o
banco no piloto (§8) são dois passos com riscos muito diferentes, e estão separados de propósito.

O serviço não expõe porta no host: quem alcança é quem está na `app_net`. O primeiro boot cria o
cluster e demora mais que os seguintes. **Ele não instala o PostGIS** — o initdb da imagem fica
escondido pelo `tmpfs` do compose, e quem cria `postgis` e `citext` é a migration `001` (§5).
Confira que o banco nasceu limpo:

**No terminal da VPS:**
```bash
docker exec motor_expansao_postgres psql -U reservas_owner -d banco_de_reservas -Atc   "select string_agg(extname, ',') from pg_extension"
```

**Esperado:** `plpgsql` e nada mais. Se aparecer `postgis_topology` ou `postgis_tiger_geocoder`, o
compose da VPS está sem o `tmpfs` — pare aqui: o `privilegios` do §8 vai reprovar.

Se a tag `postgis/postgis:18-3.6` não resolver, o `up` falha no `pull` sem criar nada — confira a
tag disponível e ajuste o compose. A restrição real é PostGIS **3.6** (D18) sobre PostgreSQL **18**,
que é a combinação em que o esquema foi validado.

Confira que a versão é a que o esquema assume — o **D18** depende do PostGIS 3.6 para o
`ST_Buffer` em `geography` preservar o SRID:

**No terminal da VPS:**
```bash
docker exec motor_expansao_postgres psql -U reservas_owner -d banco_de_reservas \
  -c "select version(), postgis_full_version();"
```

## 5. Aplicar as migrations

O runner precisa da credencial do **dono** (migration é DDL). Ela é passada na invocação, num
container efêmero, e nunca entra no ambiente do processo `web` que atende requisição:

**No terminal da VPS:**
```bash
export MOTOR_DATABASE_URL_ADMIN='postgresql://reservas_owner:<senha>@postgres:5432/banco_de_reservas'

docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL_ADMIN \
  web python -m motor_expansao.db estado           # o que falta, sem executar nada

docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL_ADMIN \
  web python -m motor_expansao.db aplicar --simular # QUAIS versoes seriam aplicadas

docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL_ADMIN \
  web python -m motor_expansao.db aplicar

unset MOTOR_DATABASE_URL_ADMIN
```

`-e MOTOR_DATABASE_URL_ADMIN` **sem valor** herda do ambiente: assim a senha não aparece no `argv`
do `docker`, que é legível por qualquer usuário em `ps`.

> **O `--simular` NÃO imprime SQL** — ele lista as versões (`a aplicar: 000, 001, …`) e encerra com
> `(--simular: nada foi executado)`. O código retorna antes de ler o arquivo de migration
> (`db/cli.py`: o `return` do `--simular` vem **antes** do `read_text`). Até 01/10/2026 o comentário
> acima dizia "o SQL que sairia", e isso enganava num ponto caro: as migrations são o único passo
> **sem volta** deste runbook, e o operador concluía ter revisado o SQL sem ter visto nenhum. A saída
> do `--simular` **lembra** a do `estado` logo acima — as duas começam listando versões —, e é daí que
> vem a impressão. Distinguir é fácil, se você olhar: o `estado` imprime uma linha por migration, e o
> `--simular`, duas ao todo.
>
> **Se você quiser mesmo ler o SQL antes de aplicar**, ele está em
> `src/motor_expansao/db/migracoes/*.sql`, em arquivos numerados na mesma ordem que o `estado` lista.

**Esperado, num banco novo:** o `estado` imprime `migrations no manifesto: 21`,
`registradas no banco: 0`, uma linha por arquivo, e termina com uma linha `pendentes:` listando de
`000` a `020`. Se o manifesto não disser 21, ou se houver alguma já registrada, **pare**.

> A faixa `000→016` citada no §1.1 é do ensaio de maio e **não** é o que você vai ver.

O runner grava o que aplicou em `migracoes_aplicadas` e recusa reaplicar. Se uma migration falhar,
ela para ali — as anteriores ficam aplicadas e registradas, e a correção é retomar do ponto, não
recomeçar.

## 6. Provisionar `app` e `auditoria` (D20)

O script completo é o `sql/papeis-e-privilegios.md` do repositório `banco-de-reservas`.
Ele **não é migration** — quase tudo é `GRANT`, e por isso vive fora do runner e do controle de
versão de schema.

**Rode as seções 1 a 7, mais duas do fim — e nunca as outras duas:**

| Rode | NÃO rode |
|---|---|
| seções **1 a 7** — é onde vive todo o provisionamento | a **seção 8**: é a lista do que *não* fazer |
| os **seis testes negativos** da seção *Testar* | **"Desfazer o provisionamento"**, no fim do arquivo — ela dropa os três papéis que você acabou de criar |
| a seção **"Conferir o que ficou concedido"** | |

A conferência não é opcional: ela é o **único** lugar que verifica o papel `etl` (espera 12 linhas
para `app`, 1 para `auditoria` e 3 para `etl`), e o comando `privilegios` do motor não olha o `etl`.
Ela **não** pega o no-op do `FOR ROLE` descrito abaixo: ela olha
`GRANT` de tabela, e default privileges vivem em `pg_default_acl`, que nenhuma consulta do script
toca. Para conferir esse, à mão, depois de rodar a seção 6:

**Dentro do `psql`:**
```sql
SELECT defaclrole::regrole, defaclobjtype, defaclacl FROM pg_default_acl;
```

**Esperado:** o `defaclrole` das duas linhas tem de ser **`reservas_owner`**.

> **Olhe o PAPEL, não a contagem — e isto foi medido.** São **duas linhas nos dois cenários**: com o
> `FOR ROLE reservas_owner` correto, e também com o `FOR ROLE postgres` que esta seção manda trocar.
> A diferença aparece só na coluna `defaclrole`. Num cluster onde o papel `postgres` **existe** — uma
> instalação nativa, por exemplo —, colar as duas linhas sem trocar o papel **não dá erro nenhum** e
> grava o no-op silencioso; e a partir daí o `conferir`, o `privilegios` e a conferência de
> 12 / 1 / 3 **passam todos verdes** sobre um banco em que toda tabela futura nasce invisível para o
> `app`. Quem ler "duas linhas: ok" aprova exatamente esse estado.

**Troque as DUAS senhas de exemplo** (`app` e `auditoria`) e rode por `psql` dentro do container.
**O `etl` não tem senha de exemplo — ele nasce `NOLOGIN`. Não invente uma para ele:** dar-lhe `LOGIN`
reabre o buraco que a correção de 28/09 fechou, e nada a jusante acusa (a conferência fecha em 3
linhas com ou sem `LOGIN`, e o `privilegios` do motor não olha o `etl`).

**No terminal da VPS:**
```bash
docker exec -it motor_expansao_postgres \
  psql -U reservas_owner -d banco_de_reservas
```

Três pontos do script que não são "boa prática de segurança" genérica:

- **`ALTER TABLE ... ENABLE ALWAYS TRIGGER`** (§7) é o único DDL do arquivo. Sem ele, um papel que
  receba `SET ON PARAMETER session_replication_role` desliga todas as triggers da sessão e escreve
  sem deixar rastro.
- **`GRANT USAGE ON SEQUENCE`** (§4). `GRANT INSERT` na tabela **não** cobre a sequence do
  `BIGSERIAL`: sem essa linha, todo `INSERT` do `app` morre por permissão negada.
- **A seção 8 lista o que não fazer** — em particular, `REVOKE ALL ON ALL FUNCTIONS` derruba o
  `EXECUTE` das ~1200 funções `ST_*` e quebra o PostGIS inteiro. Leia antes de "reforçar".
- **`ALTER DEFAULT PRIVILEGES FOR ROLE postgres` (seção 6) precisa virar `FOR ROLE reservas_owner`** —
  duas ocorrências. O compose cria o banco com `POSTGRES_USER: ${POSTGRES_OWNER_USER}`, então um papel
  chamado `postgres` **nunca é criado**: a colagem morre ali com `role "postgres" does not exist`. E se
  ele existisse, as duas linhas seriam um no-op silencioso e toda tabela criada depois nasceria
  invisível para o `app`. Há outras duas ocorrências no "Desfazer", que você não vai rodar, e **uma
  quinta, em prosa**, na caixa "Duas pegadinhas" logo abaixo do bloco: um `sed -i` global acha
  **cinco** e reescreve a explicação junto. Troque as duas linhas da seção 6 à mão, ou ancore o padrão
  no início da linha (`^ALTER DEFAULT PRIVILEGES FOR ROLE postgres`), que casa só os quatro comandos.
  *Até 24/10/2026 esta linha dizia que um `sed` global acharia quatro.*
- **O bloco de prova da seção 7** (o do `session_replication_role`) é opcional e **escreve em tabela de
  negócio**, deixando duas linhas permanentes no histórico. O próprio script oferece a saída de pulá-lo.

Rode os blocos de **validação** e **teste** do próprio documento em seguida. O teste de append-only
tem de ser rodado **depois** do `ALTER TABLE`, ou você lê como sucesso um teste que não rodou.

> **NÃO rode agora o bloco de append-only "com autor" — deixe-o para depois de criar a primeira
> pessoa (§7).** Ele exige um usuário ativo, e este passo roda **antes** do §7. A guarda que o recusa é
> um `DO` à parte, e no `psql` em modo padrão (autocommit, sem `ON_ERROR_STOP`) o erro dela não segura
> os comandos seguintes: medido em 02/10/2026 num Postgres 18 com `usuarios` vazia, a mensagem sai, o
> resto do bloco roda e ficam duas linhas permanentes de histórico com `registrado_por` **NULO**, numa
> tabela append-only. Rode agora só os seis testes negativos por catálogo. *Até 24/10/2026 esta caixa
> dizia que o bloco "vai abortar aqui, e é esperado".*

## 7. Semear os usuários reais

As migrations `012` e `013` trazem perfis, capacidades e a matriz — **não trazem pessoas**. Os
usuários são dado operacional com PII (nome, e-mail, `login_usuario`) e por isso **nunca** entram
em arquivo de migration versionado no git.

O `login_usuario` tem de ser exatamente o `Remote-User` que o Authelia entrega — é a chave que casa
a pessoa autenticada com a linha do banco (D23). Confira contra o
`authelia/users_database.yml` antes de inserir, e não contra a memória de ninguém.

Deixe **pelo menos um** usuário do perfil Growth pronto antes do passo 8: é o único que enxerga o
painel de Acessos, e é por ele que você verifica que o RBAC subiu certo.

**Só o primeiro precisa de SQL.** A partir dele, a aba de Acessos faz o resto — **criar** (D26),
trocar perfil e ativar/desativar, com autor e de-para registrados em `eventos`. O primeiro é
manual porque criar exige autor, e autor exige alguém já cadastrado; do segundo em diante a tela
resolve.

**Mas a tela grava só no banco.** Quem entra também precisa nascer no
`authelia/users_database.yml`, que é quem autentica até o **P19** ser executado — a tela avisa isso
depois de criar, com o login a cadastrar. Enquanto o Authelia autenticar, os dois cadastros andam
juntos e é preciso lembrar dos dois; uma linha em `usuarios` sem a entrada de lá aparece na lista e
não entra.

**Depois de pôr a `MOTOR_SENHA_INICIAL` no `.env`, suba o `web`:**

**No terminal da VPS:**
```bash
unset MOTOR_DATABASE_URL     # com o banco ligado, todo `up` começa assim (§9.0)
docker compose -f docker-compose.prod.yml up -d web
docker compose -f docker-compose.prod.yml exec -T web printenv MOTOR_SENHA_INICIAL | grep -c .   # 1, sem imprimir a senha
```

Editar o `.env` não alcança container em execução, e o `web` que está no ar subiu antes de a variável
existir. Sem isso, o primeiro `Criar usuário` responde 503.

**A senha de quem é criado pela tela vem de `MOTOR_SENHA_INICIAL`,** e ela precisa estar no `.env`
antes do primeiro `Criar usuário` — sem ela a rota responde 503 com mensagem explícita, em vez de
criar alguém com uma senha que ninguém sabe qual é. Cada pessoa recebe o hash Argon2id dela com sal
próprio e nasce marcada para trocar; a troca é em `PATCH /api/me/senha`, que **não** exige a
allowlist do painel — trocar a própria senha não é ato de administração. A coluna **`Senha (banco)`**
da tela diz quem já definiu senha no banco (selo `própria` ou `inicial`).

**Mas a senha do banco só vale com o login próprio ligado** (decisão do dono, 24/10/2026). O cadeado
"Trocar a minha senha", o "Redefinir senha" e o "Exigir troca" só aparecem, e só funcionam, com
`MOTOR_AUTENTICACAO_PROPRIA` ligada; com ela desligada, `PATCH /api/me/senha` e as duas rotas de admin
respondem 404, e quem confere a senha na entrada é o Authelia — então, até o corte do P19, ninguém sai
da inicial. Na produção, a `MOTOR_SENHA_INICIAL` foi sorteada na instalação (não é a senha compartilhada
do Authelia), e a marca de troca (`deve_trocar_senha_usuario`) foi desligada nos 20 em 17/10/2026. Para
o corte, a decisão é trocá-la pela compartilhada e rodar o `db alinhar-senhas`, que remarca a troca
de quem nunca definiu a própria: o convite do primeiro acesso, que tem "Agora não" — a troca é
recomendada, não obrigatória (decisão de 25/09/2026; roteiro do corte em `docs/repasse_corte_p19.md`).

**Na produção, o cadeado escondido e o 404 só valem depois do deploy da imagem que os traz.** A que estava no ar em 24/10/2026
(digest `d1cc438e…`, `main` em `84429f3e`) é anterior: ainda mostra o cadeado aos 20 — que recusa todos,
porque pede a inicial sorteada — e ainda oferece Redefinir senha e Exigir troca, que gravam só no banco.
Até esse deploy, rodar o `alinhar-senhas` antes da janela abre o convite de troca para os 20 (aviso no
0.c do `docs/repasse_corte_p19.md`).

### O SQL do primeiro cadastro

Antes do `INSERT`, gere o hash **da senha inicial**. É esta função, e não a `gerar()`, que produz o
mesmo estado de quem nasce pela tela:

**No terminal da VPS:**
```bash
cd /opt/motor-expansao/app
docker compose -f docker-compose.prod.yml run --rm \
  web python -c "from motor_expansao.db import senhas; print(senhas.hash_da_senha_inicial())"
```

A saída começa com `$argon2id$`. Copie-a e use-a no `INSERT`:

**No terminal da VPS:**
```bash
docker exec -it motor_expansao_postgres psql -U reservas_owner -d banco_de_reservas
```

**Dentro do `psql`:**
```sql
INSERT INTO usuarios (nome_usuario, email, login_usuario, senha_hash, id_perfil)
VALUES (
  'Nome Completo da Pessoa',
  'pessoa@ultraacademia.com.br',
  'login_dela_no_authelia',
  '<cole aqui o hash gerado acima>',
  (SELECT id_perfil FROM perfis WHERE nome_perfil = 'growth')
);
```

São **cinco colunas, e são exatamente as cinco `NOT NULL` sem default** depois de `001`→`020`; o
resto tem default (`ativo` nasce `TRUE`, `deve_trocar_senha_usuario` também). São as mesmas cinco que
a tela escreve — `SQL_CRIAR` em `db/usuarios.py`. Os perfis disponíveis são `growth`, `expansao`,
`consultoria` e `lideres`; o primeiro tem de ser `growth`, pelo motivo acima.

> **Por que `hash_da_senha_inicial()` e não `gerar('<a senha>')`.** A `gerar()` produz o hash de uma
> senha **arbitrária**. Ela autentica — mas só com aquela senha, que mais ninguém tem — e o
> `alinhar-senhas` da preparação do corte a **substitui** pela senha inicial, sem pedir confirmação,
> porque `senha_definida_em_usuario` nasce nulo em toda linha semeada à mão. Com
> `hash_da_senha_inicial()` a linha nasce na classe `sem_propria_ok` e aquele comando não tem nada a
> fazer nela (travado por `tests/unit/test_db_cli.py`).
>
> Um `senha_hash` **improvisado**, que não seja um PHC Argon2id, não autentica ninguém: `verificar`
> recusa qualquer coisa que não comece com `$argon2id$`.

> **O `login_usuario` tem de ser a MESMA STRING da chave do `authelia/users_database.yml`.** A caixa
> não importa — a coluna é `CITEXT` e a allowlist do painel compara com `casefold()`. O que não pode
> divergir é o texto: usar o e-mail de um lado e o nome de usuário do outro deixa a pessoa de fora.

### Conferir antes de ligar

Depois do cadastro, e de novo no momento do corte, rode o conferidor. Ele responde, pessoa a
pessoa, se **quem entra hoje** (Authelia) **existe no banco, ativo, e com as mesmas abas** que vê
pelo `acesso_abas.json`: acusa `FALTA NO BANCO` (perde tudo ao ligar), `falta no Authelia` (está no
banco e não entra), inativo e abas que mudam. Só lê, e nunca imprime hash, senha nem e-mail. A lista
muda ao vivo (cada `Criar usuário` da tela e cada edição do Authelia mexem nela), então o resultado
que vale é o do instante do corte, não o de ontem. Saída `0` = tudo casa; `1` = pendência.
**Depois de 23/10/2026, a coluna de abas compara com um `acesso_abas.json` congelado naquele dia, que
não vale mais no BR:** o que importa agora é Authelia × banco. Rode-o depois de cada mudança de cadastro
e, obrigatoriamente, antes do corte do P19 — quem foi só desativado no Authelia e segue ativo no banco
volta a entrar quando o banco passar a autenticar.

O script fica no checkout (`/opt/motor-expansao/app/scripts/conferir_usuarios_banco.py`), que
**não** se atualiza sozinho — confira que ele está lá antes. O arquivo do Authelia é `root:600` no
host, por isso a leitura passa pelo container, e o `grep` leva só as linhas de login, nunca o hash.
Precisa de `bash` (as `<(...)` não existem em `sh`):

**No terminal da VPS:**
```bash
cd /opt/motor-expansao/app
docker exec -i motor_expansao_postgres psql -v ON_ERROR_STOP=1 -At -F '|' \
    -U reservas_owner -d banco_de_reservas \
    -c "$(python3 scripts/conferir_usuarios_banco.py --sql)" \
  | python3 scripts/conferir_usuarios_banco.py \
    <(docker exec motor_expansao_authelia grep -E '^users: *(#.*)?$|^  [^ #][^:]*: *(#.*)?$|^    disabled: *[Tt]rue *(#.*)?$' /config/users_database.yml) \
    <(docker exec motor_expansao_web cat /app/cadastro/acesso_abas.json)
```

Usuário com `disabled: true` no Authelia não entra hoje: sai como `desativ.` e é coerente se
estiver inativo (ou ausente) no banco. **Não** o cadastre ativo para zerar uma pendência — isso
daria acesso a quem hoje está bloqueado. Se o conferidor ler zero logins do Authelia, ele sai `2`
(arquivo errado ou recuo diferente), nunca `0`.

Uma mudança de abas **já decidida** (alguém que ganha uma aba ao passar a um perfil do banco) é
declarada no fim do comando, com `--aceitar login:+aba,-aba`; ela sai como `ACEITA` e só vale se a
mudança real for **exatamente** a declarada. Pendência que ninguém decidiu não se aceita: resolve-se
no cadastro (tela de Acessos ou Authelia) e roda-se de novo até sair `0`.

## 8. Ligar — e o que fazer se der errado

**Executado em 23/10/2026.** A linha `MOTOR_DATABASE_URL` foi acrescentada ao `.env` e o `web`, recriado
na mesma imagem (digest `d1cc438e…`, `main` em `84429f3e`). Desde então o RBAC do piloto BR vem do banco,
e o `acesso_abas.json` deixou de valer para o BR (a instância AR, sem banco, segue no `acesso_abas.json` dela). A autenticação
própria (`MOTOR_AUTENTICACAO_PROPRIA`, P19) continua desligada: quem confere a senha na entrada ainda é o
Authelia. O roteiro abaixo fica para uma reinstalação e como referência do interruptor.

**Antes de preencher, o conferidor do §7 ("Conferir antes de ligar") tem de sair `0` — rode-o
de novo agora, não confie no de ontem.** E confira que o seu login está na allowlist do painel:

**No terminal da VPS:**
```bash
grep '^MOTOR_ACESSOS_ADMIN_USUARIOS=' .env
```

No instante em que a URL é preenchida, quem não tem linha no banco perde as abas — e o painel de
Acessos é a sua saída. Ele pede esta variável **e** a capacidade `acesso.painel_ver` do RBAC (perfil
`growth`, §7). Se o seu login não estiver nela, o painel responde 404 **para você**, e sem a sua linha
`growth` no banco, 403 — justamente quando ele é a única ferramenta de destravar.

**No arquivo `.env` — não é comando, é conteúdo para editar:**
```dotenv
MOTOR_DATABASE_URL=postgresql://app:<senha>@postgres:5432/banco_de_reservas
```

**No terminal da VPS:**
```bash
unset MOTOR_DATABASE_URL     # esquecida no terminal, mesmo vazia, ela venceria o .env (§9.0)
docker compose -f docker-compose.prod.yml up -d web
docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' motor_expansao_web | grep -c '^MOTOR_DATABASE_URL=postgresql://app:'   # 1, sem imprimir a URL
```

O host é o **nome do serviço** (`postgres`), não o `container_name`.

Verificação, nesta ordem:

**Re-exporte a credencial do dono**, que o §5 desfez com `unset`:

**No terminal da VPS:**
```bash
export MOTOR_DATABASE_URL_ADMIN='postgresql://reservas_owner:<senha>@postgres:5432/banco_de_reservas'
```

Sem ela o runner cai **em silêncio** para a credencial do `app`, e então o comando **estoura** com
`permission denied for table migracoes_aplicadas` — o `app` não tem privilégio naquela tabela. O
fallback é mudo; o resultado não é.

**No terminal da VPS:**
```bash
# 1. o motor concorda com o banco? Confere as extensões PRESENTES (postgis, citext), os seis
#    números da §0 (tabelas, índices, CHECK, FK, triggers, colunas geométricas), as 8 funções
#    endurecidas, as migrations registradas e, desde o #447, as triggers de auditoria em 'A'
#    (fora de 'A', reprova). NÃO confere: se os papéis existem, coluna comum, a VERSÃO do
#    servidor ou do PostGIS (é o `select postgis_full_version()` do §4) nem privilégio de
#    banco -- isso é do `privilegios`, a verificação 2.
docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL_ADMIN \
  web python -m motor_expansao.db conferir

# 2. o papel `app` continua incapaz do que nao deve? (F6.2)
docker compose -f docker-compose.prod.yml run --rm web \
  python -m motor_expansao.db privilegios

# 3. o piloto enxerga o banco? — bloco `banco` da rota de admin
#    (o /api/health NÃO olha o banco, de propósito: ver §9)
#
#    ATENÇÃO: esta rota fica atrás do forward_auth e da allowlist. Um `curl` sem sessão
#    recebe o redirecionamento de login, e o `jq` responde `parse error` — que se lê como
#    "o banco está quebrado". Abra no NAVEGADOR, já logado:
#      https://piloto.ultra-expansao.tech/api/acessos/saude-artefatos
```

E então, na tela: entre com um usuário de cada perfil e confirme que as abas aparecem e somem como
a matriz manda.

**Rollback (segundos, sem rebuild):** esvaziar `MOTOR_DATABASE_URL` e `docker compose up -d web`.
O piloto volta ao `acesso_abas.json` e serve exatamente como antes do banco. O container `postgres`
pode continuar de pé — nada no piloto o consulta enquanto a variável estiver vazia. É o interruptor
de incidente, e ele existe justamente para que "o banco está estranho" nunca vire "o piloto caiu".

**Três ressalvas desde que o banco foi ligado (23/10/2026):**

1. o `acesso_abas.json` ficou congelado naquele dia — a tela grava só no banco —, então quem foi criado
   ou mudado pela tela depois disso perde ou muda de acesso no rollback;
2. também aqui, `unset MOTOR_DATABASE_URL` antes do `up` (§9.0): uma variável não vazia esquecida no
   terminal vence a linha esvaziada do `.env`, e o `web` volta a subir com o banco;
3. **depois do corte do P19 o interruptor deixa de existir:** sem banco ninguém entra (o `/api/verify`
   responde 503). A volta passa a ser desfazer primeiro o P19 (roteiro em `docs/repasse_corte_p19.md`) e
   só então, se for o caso, o banco.

O kit da estação do Vinicius tem este rollback em script simulado (`passo8c-desfazer.sh`): esvazia só a
linha da URL, recria só o `web`, mostra quem muda de acesso e se recusa a rodar com o P19 ligado.

**Rollback de migration não existe.** Nenhuma das migrations tem `down`, e é deliberado: desfazer
DDL sobre dado real é onde se perde dado. O caminho de volta é o restore do dump (§10).

## 9. O que passa a ser vigiado

- `scripts/healthcheck_vps.sh` agora vigia **8** containers — `motor_expansao_postgres` entrou na
  lista. Sem essa linha, o banco fora do ar seria invisível: a leitura de parquet continua
  servindo, e só o RBAC começa a negar. **A cópia instalada na VPS (`/opt/motor-monitoring/`, crontab
  do root) é antiga e não tem essa linha** (24/10/2026): instalar a do repositório é passo do Felipe,
  comando a comando. E a gravidade muda no corte do P19: dali em diante, banco fora é o piloto BR fora.
- O **healthcheck do container `web` não consulta o banco**, e isso é escolha. Amarrar os dois faria
  o Docker reiniciar o `web` a cada piscada do Postgres, derrubando junto tudo que não depende dele.
  O `depends_on` é `service_started`, não `service_healthy`, pelo mesmo motivo.
- O `/api/health` segue mudo (pentest Onda B #8): é rota livre. O diagnóstico do banco mora na rota
  de admin — que também depende do RBAC: com o banco fora ou só ocupado, ela responde 403 ou 503, e o
  diagnóstico passa a ser por SSH (`banco_conexao.md` §5).

### O monitor do banco — `healthcheck_vps.sh banco` (diário)

O `containers` só sabe se o `motor_expansao_postgres` está de pé e não está `unhealthy` (o
`pg_isready` do compose). O subcomando `banco` cuida do resto: o backup, o expurgo da origem das
sessões e a saúde de dentro do banco. Sem ele, falha de backup ou de expurgo deixa só uma linha de
log — os dois wrappers saem com erro e mais nada.

Cada aspecto tem chave de estado própria em `/var/lib/motor-monitoring/`: um defeito não silencia o
outro, e a recuperação diz o que voltou.

| Chave | Nível | Dispara quando | O que fazer |
|---|---|---|---|
| `banco_dump` | FAIL | nenhum `*.dump` em `diario/`; o mais novo com mais de 26 h pelo **carimbo do nome** (o mtime mente depois de um restore ou `rsync`); arquivo vazio; sem a assinatura `PGDMP` do `-Fc`; sem o `.sha256`; ou sha256 que não bate | ler o log do backup; dump corrompido: refazer o backup à mão e investigar o disco |
| `banco_semanal` | FAIL | nenhuma cópia em `semanal/`, a mais nova com mais de 8 dias (o alerta diz "N dias e M h") ou inutilizável pelas mesmas regras | o backup de domingo falhou; numa instalação nova, o alerta dura até o primeiro domingo |
| `banco_backup` | FAIL | log ausente; log sem nenhuma execução registrada; ou a última execução sem a linha de fim, começada há mais de 60 min. O alerta traz o último `!!` do script, com `NOME=valor` e credencial em URL mascarados | ler o log: os motivos comuns são o container fora do ar e o `.env` sem as credenciais do dono |
| `banco_offbox` | AVISO 🟡 | a última execução que terminou foi só local (`!! AVISO: copia off-box DESLIGADA` / `fim (somente local)`) | risco aceito enquanto o restic não é decidido: lembrete semanal, e 🟢 quando a cópia off-box for ligada |
| `banco_expurgo` | FAIL | log ausente; só simulações (`--simular` não conta); a última execução real sem a linha de fim, começada há mais de 60 min; ou com mais de 26 h (uma simulação depois não rejuvenesce a idade) | a retenção de 90 dias da origem das sessões (P15) não está sendo aplicada, e o backup das 05:10 pode guardar o que deveria ter saído |
| `banco_medicao` | FAIL | o `docker exec` no container falhou, passou de 60 s ou devolveu algo fora do formato | monitor cego conta como falha; as quatro chaves abaixo ficam como estavam |
| `banco_tamanho` | FAIL | banco acima de 5120 MB | ver quais tabelas cresceram antes de subir o limiar |
| `banco_conexoes` | FAIL | conexões ≥ 80% do `max_connections` | no teto, o Postgres recusa conexão nova, inclusive a do pool do piloto |
| `banco_transacoes` | FAIL | sessão `idle in transaction` parada há mais de 10 min | ela segura lock e impede o VACUUM; achar em `pg_stat_activity` (`pg_terminate_backend` encerra) |
| `banco_locks` | FAIL | sessão esperando lock há mais de 5 min | `pg_blocking_pids(pid)` mostra quem bloqueia |

**Nível AVISO (🟡).** É a mesma máquina de estados do FAIL — alerta na transição, lembrete enquanto
durar, 🟢 na recuperação —, com lembrete semanal em vez de horário. Serve para risco conhecido e aceito:
vermelho todo dia por ele ensinaria o grupo a ignorar o canal. Na primeira rodada em produção, um 🟡 do
`banco_offbox` é esperado (restic desligado).

**Variáveis**, todas opcionais. Os defaults são os caminhos do runbook, com teste travando a paridade com
os wrappers:

| Variável | Default | O que controla |
|---|---|---|
| `MONITOR_BANCO_BACKUP_DIR` | `/opt/motor-expansao/backups/banco` | raiz dos dumps (`diario/` e `semanal/`) |
| `MONITOR_BANCO_BACKUP_LOG` | `/var/log/motor-monitoring/backup_banco.log` | log do `run_backup_banco.sh` |
| `MONITOR_BANCO_EXPURGO_LOG` | `/var/log/motor-monitoring/expurgo_sessoes.log` | log do `run_expurgo_sessoes.sh` |
| `MONITOR_BANCO_CONTAINER` | `motor_expansao_postgres` | container onde a saúde interna é medida |
| `MONITOR_BANCO_DUMP_MAX_HORAS` | `26` | idade máxima do dump diário mais novo |
| `MONITOR_BANCO_SEMANAL_MAX_DIAS` | `8` | idade máxima da cópia semanal mais nova |
| `MONITOR_BANCO_EXPURGO_MAX_HORAS` | `26` | idade máxima da última execução real do expurgo |
| `MONITOR_BANCO_EM_ANDAMENTO_MIN` | `60` | execução sem a linha de fim e mais nova que isto está em andamento: fica sem veredito |
| `MONITOR_BANCO_TAMANHO_MAX_MB` | `5120` | guarda de crescimento fora do esperado, não de capacidade (o disco é do `host`); subir quando chegar carga legítima, como o ETL da fase 5 |
| `MONITOR_BANCO_CONEXOES_PCT_MAX` | `80` | conexões abertas, em % do `max_connections` |
| `MONITOR_BANCO_OCIOSA_MAX_MIN` | `10` | `idle in transaction` mais antiga, em minutos |
| `MONITOR_BANCO_LOCK_MAX_MIN` | `5` | espera por lock mais antiga, em minutos |
| `MONITOR_BANCO_TIMEOUT_S` | `60` | teto do `docker exec` da medição |
| `MONITOR_AVISO_REMIND_SECS` | `604800` (7 dias) | lembrete do nível AVISO (vale para o script inteiro) |

**A linha do crontab do root** aponta os três caminhos para a conta `deploy`, onde backup e expurgo
rodam desde 17/10/2026 (§9.1 e §10):

**No crontab do root (`crontab -e`, na VPS) — é linha de crontab, não comando:**
```cron
0 12 * * * MONITOR_BANCO_BACKUP_DIR=/home/deploy/backups/banco MONITOR_BANCO_BACKUP_LOG=/home/deploy/logs/backup_banco.log MONITOR_BANCO_EXPURGO_LOG=/home/deploy/logs/expurgo_sessoes.log /opt/motor-monitoring/healthcheck_vps.sh banco
```

**Por que 12:00 UTC (09:00 BRT).** O backup roda às 05:10 e o expurgo às 04:40: na hora do check, o dump
do dia tem ~7 h, e um dia sem backup deixa o anterior com ~31 h. O limiar de 26 h só pega o dia perdido
no próprio dia se o check rodar mais de 2 h depois do backup. Se backup e expurgo mudarem de conta,
mudam só as três variáveis de caminho.

**Segredos.** A medição roda dentro do container, com as variáveis do próprio container
(`$POSTGRES_USER`, `$POSTGRES_DB`, `$POSTGRES_PASSWORD`) expandidas lá dentro. O monitor não lê segredo
do banco no `.env` (o único segredo que ele toca é o token do bot, no envio do alerta), não ecoa saída
do container (só números validados) e mascara a linha `!!` que copia do log.

**Rodada manual.** Ela não imprime nada no terminal: o resultado vai para o log e, se houver transição,
para o Telegram.

**No terminal da VPS, como root:**
```bash
MONITOR_BANCO_BACKUP_DIR=/home/deploy/backups/banco MONITOR_BANCO_BACKUP_LOG=/home/deploy/logs/backup_banco.log MONITOR_BANCO_EXPURGO_LOG=/home/deploy/logs/expurgo_sessoes.log /opt/motor-monitoring/healthcheck_vps.sh banco
tail -20 /var/log/motor-monitoring/healthcheck.log
```

**Instalar é passo do Felipe (root), comando a comando**, e ainda não foi feito (24/10/2026): copiar a
versão do repositório — por `scp`, a partir da `main`, porque o checkout da VPS está parado num commit
antigo e não aceita `git pull` — para `/opt/motor-monitoring/healthcheck_vps.sh` e acrescentar a linha
acima. A cópia instalada é antiga (nem o `postgres` ela vigia), então a troca traz junto tudo o que ela
não tem, e o que já está agendado pode começar em FAIL. Os testes ficam em
`tests/unit/test_healthcheck_banco.py` (30 casos): travam a paridade dos defaults e das frases de início
e de fim com os wrappers, a cadência do lembrete nos dois níveis e cada `MONITOR_BANCO_*` funcionando de
verdade. Se um wrapper mudar a frase que escreve no log, o teste avisa antes de o monitor passar a dizer
"nenhuma execução registrada" na VPS.

## 9.0 Deploy com o banco ligado: imagem nova e migrations futuras

Desde 23/10/2026 todo deploy do `web` acontece com o banco ligado. As migrations viajam **dentro da
imagem**, e uma imagem nova que traga uma `021` quebra rotas vivas se subir antes de o banco ter o que
ela espera (o caso do P19 está no §9.0.1, passo 5). Por isso o digest é o **último** passo. O `pull` e o
`up` em si seguem o `docs/deploy_piloto_web.md` §5; este roteiro é o que vem antes e em volta deles. O
molde é a aplicação das migrations do P19 (§9.0.1).

**Antes, no PR.** Mexer em `src/motor_expansao/db/` (migrations incluídas), num cron do banco (arquivo de
`scripts/cron/` com `banco` ou `sessoes` no caminho) ou em `scripts/ci/` é **CRÍTICO** no
`scripts/loop_guard.py`: o check `guard` só passa com a label `critica-aprovada` de um dos donos
(DEC-016/DEC-019), e o loop autônomo aborta. O conferidor (`scripts/conferir_usuarios_banco.py`), o
rastreio de vazamento (`scripts/rastrear_arquivo.py`) e o contrato da porta única
(`tests/contracts/test_conexao_por_uma_porta_so.py`) são GOVERNANÇA (`aprovado-humano`). O `guard` julga
pelo `loop_guard.py` da `main`, então a regra vale a partir do merge que a trouxe. E o check `test` já
terá aplicado a cadeia inteira do zero num PostGIS 18 vazio (§1.5) — o que não prova a migration contra
um banco com dados.

**1. `estado` com a imagem NOVA, antes de trocar o digest.** O `WEB_IMAGE` na frente do comando vale só
para ele: o `.env` não muda, e o que está no ar segue na imagem antiga.

**No terminal da VPS:**
```bash
cd /opt/motor-expansao/app
export MOTOR_DATABASE_URL_ADMIN='postgresql://reservas_owner:<senha>@postgres:5432/banco_de_reservas'
NOVA='ghcr.io/kastaldy/motor-de-expansao/motor-expansao-web@sha256:<digest novo>'
WEB_IMAGE="$NOVA" docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL_ADMIN \
  web python -m motor_expansao.db estado
```

Sem linha `pendentes:` e sem `ATENCAO`, não há migration nova: vá direto ao passo 6. Com `ATENCAO`,
pare — é migration editada depois de aplicada, ou banco sem o registro (`banco_conexao.md` §8).

**2. Havendo pendente, pare o `web` — ou aplique com `lock_timeout`.** Migration que altera tabela do
caminho quente pega `ACCESS EXCLUSIVE` e espera sem fim por uma sessão parada em `idle in transaction`;
enquanto ela espera, as consultas do RBAC desistem em 1 s (o `lock_timeout` do pool) e o piloto responde
503. Com o `web` parado isso não acontece, e ele é o único serviço que fala com o banco: o `web_ar` não
recebe `MOTOR_DATABASE_URL`. A alternativa com ele de pé está no §9.0.1, passo 2: `psql` com `SET lock_timeout` antes de cada
migration — e por esse caminho o runner não registra o que foi aplicado; no passo 3, troque o `aplicar`
por `registrar --ate <NNN>` (`banco_conexao.md` §8).

**No terminal da VPS:**
```bash
docker compose -f docker-compose.prod.yml stop web     # o piloto BR sai do ar até o passo 6
```

**3. `aplicar`, com a credencial do dono e a imagem nova.**

**No terminal da VPS:**
```bash
WEB_IMAGE="$NOVA" docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL_ADMIN \
  web python -m motor_expansao.db aplicar --simular
WEB_IMAGE="$NOVA" docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL_ADMIN \
  web python -m motor_expansao.db aplicar
```

Se o `aplicar` parar no meio, as anteriores ficam aplicadas e registradas, e a correção é retomar
(§5). Não há rollback de migration (§8).

**4. Conferir os `GRANT` da tabela nova.** O D20 da produção foi colado com o `ALTER DEFAULT PRIVILEGES
FOR ROLE reservas_owner` que o §6 manda, então tabela criada por migration nasce com `SELECT`, `INSERT`
e `UPDATE` para o `app`, e a sequence dela com `USAGE` — e nada para o `auditoria`. Confira contra a
política da tabela, como dono:

**Dentro do `psql`:**
```sql
\dp <tabela_nova>
\dp <tabela_nova>_<coluna>_seq
```

- tabela append-only, como `eventos`: `REVOKE UPDATE ON <tabela_nova> FROM app;`;
- tabela que o piloto só lê: revogue `INSERT` e `UPDATE` **e** o `USAGE` da sequence — o `privilegios`
  reprova `USAGE` sem `INSERT`, e `INSERT` sem `USAGE`;
- `DELETE` nunca vem por padrão: se a aplicação precisar, é `GRANT DELETE` explícito, com a decisão
  registrada;
- leve o mesmo `GRANT` às seções 3 e 4 do `sql/papeis-e-privilegios.md`, no `banco-de-reservas`: numa
  instalação do zero o D20 roda depois de todas as migrations, e o default privilege só alcança tabela
  criada depois dele.

**5. `conferir` e `privilegios`, com a imagem nova** — o código dela já sabe da tabela nova:

**No terminal da VPS:**
```bash
WEB_IMAGE="$NOVA" docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL_ADMIN \
  web python -m motor_expansao.db conferir           # CONFERENCIA OK
unset MOTOR_DATABASE_URL                               # a URL do app tem de vir do .env
WEB_IMAGE="$NOVA" docker compose -f docker-compose.prod.yml run --rm \
  web python -m motor_expansao.db privilegios        # PRIVILEGIOS OK, conectado como app
```

**6. Só então trocar o digest.** No `.env`, `WEB_IMAGE` passa ao digest novo. O `web_ar` usa o MESMO
`WEB_IMAGE` e sobe junto:

**No terminal da VPS:**
```bash
unset MOTOR_DATABASE_URL
docker compose -f docker-compose.prod.yml pull web
docker compose -f docker-compose.prod.yml up -d web
docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' motor_expansao_web | grep -c '^MOTOR_DATABASE_URL=postgresql://app:'   # tem de dar 1
docker compose -f docker-compose.ar.yml pull web_ar
docker compose -f docker-compose.ar.yml up -d web_ar
unset MOTOR_DATABASE_URL_ADMIN
```

**Em TODO `up` que alcance o `web` com o banco ligado — deploy, rollback, troca de variável, e também
o `up -d caddy`, que depende dele —, `unset MOTOR_DATABASE_URL` antes e a contagem acima depois.** O compose dá preferência à variável do terminal
sobre o `.env`, e o ensaio achou o caso perigoso: uma `MOTOR_DATABASE_URL` **vazia** herdada do shell
vence a linha do `.env`, e o `web` sobe sem banco, sem erro nenhum — antes do corte do P19, de volta ao
`acesso_abas.json` congelado de 23/10/2026; depois do corte, **com todo mundo trancado para fora**. A
contagem confere sem imprimir a URL, que carrega a senha do `app`. E `restart` não relê o `.env`: ele
mantém o ambiente do container — é o que faz o `docker restart` diário da ingestão da Growth (06:30
UTC); para reler, é `up -d <serviço>`.

## 9.0.1 O molde: aplicar as migrations do P19 (018, 019, 020) — ORDEM QUE IMPORTA

Auditoria de 23/09/2026 antes da primeira aplicação em produção — que acabou não vindo por aqui: o banco de produção nasceu em 17/10/2026 com as 21 migrations de uma vez (§5), então esta seção só vale para um banco que já tenha `000`–`017`. **A ordem abaixo não é
preferência: cada passo evita uma falha concreta, e três delas não apareceram no ensaio local
porque lá o banco nasce limpo e sem tráfego.**

### 1. Ver o que produção realmente tem

**No terminal da VPS:**
```bash
docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL_ADMIN \
  web python -m motor_expansao.db estado
```

Se aparecer pendente **abaixo de 018** cujo efeito já esteja no banco, use
`registrar --ate <NNN>` antes de aplicar. Motivo: `aplicar` roda **todas** as pendentes em
ordem, e a [013](https://github.com/Kastaldy/banco-de-reservas) falha de propósito em tabela
com linhas (`ADD COLUMN login_usuario CITEXT NOT NULL` sem default). O lote morreria ali e as
018/019/020 nunca chegariam.

### 2. Parar o `web`, ou pôr `lock_timeout`

A 019 faz `ALTER TABLE usuarios` — que pega `ACCESS EXCLUSIVE` na tabela do caminho quente do
RBAC. Uma sessão parada `idle in transaction` sobre `usuarios` faz o `ALTER` **esperar
indefinidamente**, e a fila de locks bloqueia todo `SELECT` em `usuarios` enquanto isso: o
RBAC inteiro para. Nenhuma das três migrations define `lock_timeout`, e o ensaio não pegou
isso porque lá não há tráfego.

Com o `web` parado o problema não existe. Se preferir aplicar com ele de pé, use `psql` e
`SET lock_timeout = '3s';` antes de cada uma.

### 3. Aplicar a 018 **e conceder o privilégio na sequência**

**No terminal da VPS:**
```bash
docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL_ADMIN \
  web python -m motor_expansao.db aplicar
```

**A `sessoes` nasce SEM privilégio para o papel `app`, e isso é silencioso.** O
`ALTER DEFAULT PRIVILEGES` do `papeis-e-privilegios.md` §6 diz `FOR ROLE postgres`, e só
alcança objetos criados por *aquele* papel — mas o dono do schema aqui é **`reservas_owner`**. (Vale
para um D20 colado com o `FOR ROLE postgres` do script; com o `FOR ROLE reservas_owner` que o §6 manda —
o da produção —, a tabela nasce com `SELECT`, `INSERT` e `UPDATE` para o `app`: §9.0, passo 4.)
A tabela criada pela migration não herda nada, e o sintoma só apareceria no dia da virada da
chave: `permission denied for table sessoes`, com todo mundo fora da plataforma. O próprio
documento nomeia a armadilha ("as tabelas novas nascem sem `GRANT` e ninguém percebe").

Rode, como dono, as duas linhas do `papeis-e-privilegios.md` que cobrem a sessão:

**Dentro do `psql`:**
```sql
GRANT SELECT, INSERT, UPDATE ON sessoes TO app;
GRANT USAGE ON SEQUENCE sessoes_id_sessao_seq TO app;   -- sem ela, todo login morre
```

### 4. Aplicar 019 e 020

Sem surpresa: o `CHECK` da 019 **não pode** reprovar linha existente (a coluna nasce na mesma
transação, então toda linha tem `NULL` e a segunda perna é verdadeira), e a 020 só acrescenta
colunas anuláveis.

### 5. **Só então** trocar o digest da imagem

**A imagem nova quebra rotas VIVAS se as migrations não vierem antes.** `PATCH /api/me/senha`
e `POST /api/acessos/usuarios/{id}/redefinir-senha` escrevem `senha_expira_em_usuario` e
**não** estão atrás da chave `MOTOR_AUTENTICACAO_PROPRIA` — verificado, zero ocorrências de
`ligada()` nas duas. Sem a 019, as duas respondem 500 (`UndefinedColumn`) para qualquer
pessoa que tente trocar a própria senha. *Desde 24/10/2026 (decisão do dono), as duas respondem 404 com
a chave desligada; a regra — migration antes do digest — continua valendo para qualquer rota viva
(§9.0).*

O caminho inverso é seguro: a imagem antiga não conhece as colunas novas, e o `CHECK` não a
atinge.

### 6. Conferir

**No terminal da VPS:**
```bash
... web python -m motor_expansao.db conferir      # espera 12 / 49 / 14 / 12 / 7 / 7
... web python -m motor_expansao.db privilegios   # com a URL do `app`, não a de dono
```

Desde 23/09/2026 o `privilegios` **cobre `sessoes`** (SELECT/INSERT/UPDATE + a sequence, e
`DELETE` negado). Antes disso ele passaria verde no cenário do passo 3 — o comando que existe
para provar o D20 não olhava a tabela nova.

### 7. Instalar o cron do expurgo

Só depois das três aplicadas — ver §9.1.

## 9.1 Expurgo da origem das sessões (retenção do P15)

Instalação do cron: cabeçalho do
[`scripts/cron/run_expurgo_sessoes.sh`](../scripts/cron/run_expurgo_sessoes.sh).
Roda **04:40 UTC (01:40 BRT), diariamente** — e o horário não é arbitrário.

**Na produção ele não está nesse caminho.** Desde 17/10/2026 roda no crontab da conta `deploy` (e não
do root), com o script em `/home/deploy/motor-infra/run_expurgo_sessoes.sh` (idêntico ao do
repositório) e o log em `/home/deploy/logs/expurgo_sessoes.log` — a linha do crontab passa `LOG_CRON`
com esse caminho. A receita do cabeçalho (`/opt/motor-expansao-infra`, log em
`/var/log/motor-monitoring/`, crontab do root) segue como a genérica; o risco de a conta `deploy` sair
está no §10. Em 24/10/2026 ele não tem o que zerar: sessão só nasce no login próprio, que segue desligado.

**A ordem entre este cron e o backup É a política de retenção.** O expurgo zera
`ip_sessao`/`user_agent_sessao` além de 90 dias; o backup, 30 minutos depois, dumpa o banco
inteiro e a cópia semanal fica 28 dias. Invertida a ordem, cada dump carregaria os IPs já
vencidos e a cópia off-box os guardaria por quatro semanas — a retenção de 90 dias viraria 118
na prática, sem ninguém perceber. Há teste guardando a ordem
(`tests/unit/test_wrapper_cron_expurgo_sessoes.py`), porque nenhum dos dois arquivos garante
isso sozinho.

**Anonimiza, não apaga.** O que tem prazo é o dado pessoal, não o registro da sessão: a linha
permanece e continua respondendo "entrou em tal dia, revogada em tal outro". Apagar contrariaria
o desenho da [018](https://github.com/Kastaldy/banco-de-reservas), em que revogar é `UPDATE` e
nunca `DELETE` — o papel `app` nem tem `DELETE`.

Antes de **agendar** no crontab — com o arquivo já copiado, que são os passos 1 a 3 da instalação no
cabeçalho —, rode uma vez em modo seco. É o smoke documentado lá, o passo 4 de 5: o caminho abaixo só
existe depois do `cp`.

**No terminal da VPS:**
```bash
/opt/motor-expansao-infra/run_expurgo_sessoes.sh --simular
# na produção (conta deploy): LOG_CRON=/home/deploy/logs/expurgo_sessoes.log /home/deploy/motor-infra/run_expurgo_sessoes.sh --simular
```

**O prazo e a consulta não estão no script.** Vivem em `db/sessoes.py`
(`RETENCAO_ORIGEM_DIAS`, `SQL_EXPURGAR_ORIGEM`), com teste e sabotagem; o wrapper só orquestra.
Mudar o prazo é mudar uma constante, não editar shell — e há teste que recusa SQL dentro do
wrapper.

**O que este cron NÃO fecha:** a **base legal** do P15, que é decisão jurídica e não técnica.
O prazo foi decidido em 23/09/2026 (3 meses); o fundamento, não.

## 10. Backup e restore

Instalação do cron: cabeçalho do [`scripts/cron/run_backup_banco.sh`](../scripts/cron/run_backup_banco.sh).
Roda 05:10 UTC (02:10 BRT) — dentro da janela do BLK-SEC-04 e 50 min antes da coleta de domingo.

**O que está instalado na produção (desde 17/10/2026) não segue o caminho do cabeçalho** — decisão do
dia, porque as pastas do runbook são do root:

- crontab da conta **`deploy`** (não do root), às 05:10 UTC, com o script em
  `/home/deploy/motor-infra/run_backup_banco.sh` (idêntico ao do repositório); a linha do crontab passa
  `BACKUP_DIR=/home/deploy/backups/banco` e `LOG_CRON=/home/deploy/logs/backup_banco.log`, e o `.env`
  lido continua sendo o `/opt/motor-expansao/app/.env`;
- dumps `-Fc` em `/home/deploy/backups/banco/diario` e `/home/deploy/backups/banco/semanal` (pastas 700),
  cada um com o seu `.sha256`; retenção de 7 dias no diário e de 28 no semanal, com a cópia semanal feita
  por hardlink aos domingos;
- **cópia off-box (restic) DESLIGADA**: destino e custo são decisão do Felipe. Até lá cada execução
  termina em `fim (somente local)`, e os dumps moram no mesmo disco do banco;
- **risco**: tudo isso mora numa conta pessoal. O offboarding padrão dela (`userdel -r`, §4 do
  `docs/acesso_deploy_colaborador.md`) apagaria os crons e os dumps sem aviso, e tirá-la do grupo
  `docker` faria backup e expurgo falharem toda noite. Se a conta mudar, mudam junto os três caminhos
  do monitor (§9).

A receita do cabeçalho (`/opt/motor-expansao-infra`, `/opt/motor-expansao/backups/banco`, crontab do
root) continua sendo a genérica, e é ela o default do script e do monitor.

**Por que isto existe.** O BLK-SEC-04 aceitou o risco em 13/07 porque "quase tudo é regenerável
pelos pipelines". RBAC, eventos, áreas de estudo e contratos nascem no app e **nenhum pipeline os
regenera** — é o gatilho de reabertura que o próprio bloco nomeia. O dump é `-Fc` (custom) e não SQL
puro justamente para permitir `pg_restore -t`: restaurar uma tabela sem derrubar o resto era o
"restore granular" listado como gap aceito.

**Cópia off-box é restic, não rclone.** O dump carrega e-mail, `login_usuario`, `senha_hash` e o `ip`
das **sessões** — `eventos.ip` nunca teve produtor, e quem passou a guardar IP foi `sessoes`, pela
migration 020 (23/09/2026). O restic cifra antes de o arquivo sair da máquina, com chave que o dono do bucket não
tem. Sync de arquivo cru entregaria PII em claro a um terceiro. A senha do repositório é a chave de
decifração: perdê-la é perder todo o backup — guarde a cópia no mesmo cofre do SOPS+age.

### Restaurar

Nunca por cima do banco vivo. Restaure num banco novo, confira, e só então decida.

**No terminal da VPS:**
```bash
# 1. integridade do arquivo, antes de qualquer coisa -- DENTRO da pasta do dump, porque o
#    .sha256 guarda só o nome (na produção: cd /home/deploy/backups/banco/diario, como deploy)
sha256sum -c banco_de_reservas_<carimbo>.dump.sha256

# 2. base limpa ao lado da de produção
docker exec motor_expansao_postgres \
  createdb -U reservas_owner banco_de_reservas_restore

# 3. restaurar
docker exec -i motor_expansao_postgres \
  pg_restore -U reservas_owner -d banco_de_reservas_restore --no-owner \
  < banco_de_reservas_<carimbo>.dump

# 4. conferir — e é aqui que se sabe se o backup presta
docker exec motor_expansao_postgres psql -U reservas_owner -d banco_de_reservas_restore \
  -c "select count(*) from usuarios;" \
  -c "select count(*) from perfil_permissoes_historico;"
```

Os passos acima restauram no **mesmo** cluster, onde os papéis do D20 já existem.

**Mas a base restaurada volta SEM a seção 2 do D20 — recole-a sempre que ela for continuar existindo.**
O `REVOKE TEMPORARY ON DATABASE` é privilégio **de banco**: vive em `pg_database.datacl`, no catálogo do
cluster, e um `pg_dump` de um banco só não o leva. `createdb` + `pg_restore` devolve uma base com os
privilégios padrão, em que `PUBLIC` cria tabela temporária — medido em 02/10/2026: origem com
`has_database_privilege('public', …, 'TEMPORARY')` = `f`, base restaurada = `t`. Isso reabre o caminho da
forja que o **D21** fechou (tabela temporária própria + a função `SECURITY DEFINER` da 009 gravam linha
de auditoria com o privilégio do dono), e o `conferir` não olha privilégio de banco: passa verde na base
restaurada.

**No terminal da VPS:**
```bash
docker exec -i motor_expansao_postgres psql -U reservas_owner -d banco_de_reservas_restore <<'SQL'
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT  USAGE  ON SCHEMA public TO app, auditoria, etl;
DO $$ BEGIN
  EXECUTE format('REVOKE TEMPORARY ON DATABASE %I FROM PUBLIC', current_database());
END $$;
SELECT has_database_privilege('public', current_database(), 'TEMPORARY') AS publico_cria_temp;
SQL
```

`publico_cria_temp` tem de vir **`f`**. Quem pega a falta disso é o `privilegios`, com a credencial do
`app` (a senha está no `.env`, em `MOTOR_APP_DB_PASSWORD`) apontada para a base restaurada — sem a
recolagem, ele reprova em `criar tabela temporaria`:

**No terminal da VPS:**
```bash
cd /opt/motor-expansao/app
export MOTOR_DATABASE_URL='postgresql://app:<senha do app>@postgres:5432/banco_de_reservas_restore'
docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL web python -m motor_expansao.db privilegios
unset MOTOR_DATABASE_URL     # OBRIGATÓRIO: esquecida no terminal, ela vence o .env no próximo `up` (§9.0)
```

### Restaurar num servidor novo

É o caso do disco perdido — e o único em que o backup é a última linha. Medido no ensaio de
13/10/2026: o `pg_restore` puro num cluster novo devolve os **dados idênticos**, mas termina com
**21 erros** ("errors ignored on restore") e o piloto **não conecta**. O dump não leva o que é do
cluster ou da database: os **papéis** (`app`, `auditoria`, `etl`) e o **`REVOKE TEMPORARY ON
DATABASE`** do D20 §2. Os `GRANT` de tabela e o `ENABLE ALWAYS TRIGGER` vêm no dump — desde que os
papéis existam antes. **E o dump precisa ter saído do disco:** com a cópia off-box desligada (acima), os
dumps moram no mesmo disco do banco, e perder um é perder os dois. O `.env` com as senhas vem do backup
cifrado (`secrets/env.enc.env`, §3).

Com o `postgres` do compose de pé no servidor novo (§3 e §4), **nesta ordem**:

1. `sha256sum -c` no arquivo, como acima;
2. **D20 seção 1** (os três papéis, com as senhas do `.env`: `MOTOR_APP_DB_PASSWORD` e
   `MOTOR_AUDITORIA_DB_PASSWORD`, nomes da instalação de 17/10/2026; o `etl` nasce `NOLOGIN`) — dentro
   do `psql`, como no §6;
3. `pg_restore --no-owner` direto no `banco_de_reservas` — **zero erros** é o esperado;
4. **D20 seção 2** (schema e `REVOKE TEMPORARY`) — o `REVOKE CREATE` e o `GRANT USAGE` são no-op
   ali, o `REVOKE TEMPORARY` não;
5. `conferir` e `privilegios` (§8): os dois **OK**, e as contagens batendo com as de origem.

**Não** rode as migrations nem as seções 3 a 7 do D20 por cima: o dump já trouxe o schema, os
`GRANT` e os triggers em `A`.

### Restaurar uma tabela só

Sem tocar nas outras — **são dois comandos, e a sequence é o segundo `-t`**:

**No terminal da VPS:**
```bash
# 1. esvaziar a tabela ANTES. `--data-only` não substitui linha: ele INSERE, e colide na chave
#    primária se a tabela tiver qualquer linha. Como DONO -- o `app` não tem TRUNCATE.
docker exec motor_expansao_postgres \
  psql -U reservas_owner -d banco_de_reservas_restore \
  -c "TRUNCATE eventos RESTART IDENTITY;"

# 2. a tabela E A SEQUENCE dela. Sem o segundo `-t`, as linhas voltam e o contador NÃO -- e o
#    próximo INSERT da aplicação morre em chave duplicada.
docker exec -i motor_expansao_postgres \
  pg_restore -U reservas_owner -d banco_de_reservas_restore \
  -t eventos -t eventos_id_evento_seq --data-only \
  < banco_de_reservas_<carimbo>.dump
```

> **Os dois modos de falhar, medidos em 02/10/2026 num Postgres 18.4** (até 24/10/2026 este bloco era
> um comando só, sem o `TRUNCATE` e sem a sequence). **Sem esvaziar antes**, o `pg_restore` morre em
> `eventos_pkey`, não restaura nada e sai com código 1 — o modo barato, porque o erro é visível.
> **Esvaziando, mas sem a sequence**, é o caro: `-t eventos` deixa de fora a entrada `SEQUENCE SET` que
> o dump carrega, e as linhas voltam com o contador atrás — o restore parece certo, e cada evento novo
> da aplicação estoura em `eventos_pkey` até alguém rodar `setval` à mão.
>
> O restore granular é o que o **BLK-SEC-04** aceitou como mitigação, e é por ele que o dump é `-Fc`.

> **O `-d` aqui é a base restaurada, e não a de produção — de propósito, porque o passo 1 é um
> `TRUNCATE`.** Se o alvo for mesmo produção, ele joga fora o que estiver lá agora: confira o que você
> tem antes, e não rode isso numa base viva sem o dump do momento na mão.

### Teste de restauração (aceite do BLK-SEC-04)

Restaurar o dump mais novo numa base **temporária** do mesmo cluster, comparar com o banco real tabela a
tabela e apagar a temporária. O banco real só é lido e nada no piloto aponta para a base temporária, por
isso não precisa de janela. Ainda não rodou na produção (24/10/2026); o kit da estação do Vinicius
automatiza a sequência (`backup3-restaurar-teste.sh`), apagando a temporária mesmo se algo falhar no
meio. Como `deploy`, a conta dona das pastas do backup:

**No terminal da VPS:**
```bash
cd /home/deploy/backups/banco/diario     # na receita do runbook: /opt/motor-expansao/backups/banco/diario
D=$(ls banco_de_reservas_*.dump | sort | tail -1); echo "$D"    # o mais novo pelo CARIMBO do nome, não pelo mtime
sha256sum -c "$D.sha256"                 # tem de dizer OK; se não disser, PARE

C=motor_expansao_postgres; T=banco_de_reservas_restore_teste
q() { docker exec "$C" psql -X -At -U reservas_owner -d "$1" -c "$2"; }
q banco_de_reservas "select count(*) from pg_database where datname = '$T'"    # tem de dar 0
```

**Se der 1, PARE:** já existe uma base com esse nome — de um teste que morreu no meio, ou de alguém
usando —, e este procedimento nunca a sobrescreve nem a apaga. Descubra de quem é antes.

**No terminal da VPS:**
```bash
docker exec "$C" createdb -U reservas_owner "$T"
docker exec -i "$C" pg_restore -U reservas_owner -d "$T" --no-owner < "$D"; echo "código $?"   # 0, sem linha 'pg_restore: error'
for t in $(q banco_de_reservas "select table_name from information_schema.tables where table_schema = 'public' and table_type = 'BASE TABLE' order by 1"); do
  echo "$t real=$(q banco_de_reservas "select count(*) from public.\"$t\"") restaurado=$(q "$T" "select count(*) from public.\"$t\"")"
done
```

**Como ler a comparação.** Contagem igual em todas as tabelas: o backup restaura. Com o banco ligado,
tabelas como `eventos` crescem depois do dump das 05:10, e o real fica com mais linhas; aí a tabela só
conta como **igual até o dump** se as linhas com chave até a maior chave restaurada baterem exatamente.
Para `eventos`:

**No terminal da VPS:**
```bash
M=$(q "$T" "select coalesce(max(id_evento), 0) from eventos")
q banco_de_reservas "select count(*) from eventos where id_evento <= $M"    # tem de dar exatamente o 'restaurado' de eventos
```

Qualquer outra diferença — o restaurado com **mais** linhas que o real, a contagem até a chave que não
bate, uma tabela sem chave numérica simples que mudou — é **DIFERENTE**, e o backup não está provado. No
fim — e também se algo falhar no meio —, apague a temporária, e só ela:

**No terminal da VPS:**
```bash
docker exec "$C" dropdb -U reservas_owner "$T"
```

Ela dispensa a seção 2 recolada (acima) porque vive minutos e é apagada; base restaurada que for
continuar existindo não dispensa.

**O restore em base limpa faz parte do aceite do BLK-SEC-04**, não é opcional. Backup que ninguém
restaurou é backup que ninguém tem — e backup restaurado sem a seção 2 recolada volta com a auditoria
forjável.

## 11. Estado do disco

O volume `postgres_data` é o **único** do compose que nenhum pipeline regenera. `caddy_data` se
refaz sozinho, `bot_data` custa um relogin, os parquets saem dos pipelines. Este não.

`mem_limit: 2g` é teto conservador: a KVM4 tem 16 GB, e só os tetos de `web` (8g) e `api` (6g) — sem contar o `web_ar` (2g, `docker-compose.ar.yml`, na mesma VPS) — já somam
14; com o do `postgres` e o do `web_ar`, os tetos declarados chegam a **18 GB num host de 16 GB**
(`telegram-bot`, `caddy` e `authelia` nem têm teto; e o `tileserver`, outra stack na mesma VPS, declara
mais 1500m no `openmaptiles-infra/docker-compose.yml` do repositório). Teto não reserva memória, e a soma só morde se
vários encostarem nele ao mesmo tempo, mas não sobra folga para subir nenhum sem medir. O candidato a
estourar isso é o ETL da fase 5 (dissolve por UF) — quando ele existir, **medir
antes de subir o teto**, não depois de um OOM.

## 12. Trocar a senha de um papel

Para reagir a vazamento ou por rotina. As senhas ficam no `.env` de `/opt/motor-expansao/app` — o `etl`
não tem, porque nasce `NOLOGIN` (§3). No banco, a troca é o `\password <papel>` do `psql`, como dono: ele
pede a senha nova duas vezes e a manda já cifrada, sem deixá-la no histórico do terminal nem no log do
Postgres. Gere a senha em hexadecimal (§3) e troque a linha do `.env` sem imprimir o arquivo.

**No terminal da VPS:**
```bash
docker exec -it motor_expansao_postgres psql -U reservas_owner -d banco_de_reservas
```

**Dentro do `psql`:**
```sql
\password app
```

| Papel | No `.env` | E depois |
|---|---|---|
| dono (`reservas_owner`) | `POSTGRES_OWNER_PASSWORD` | nada a recriar: backup e expurgo releem o `.env` a cada execução, e o `POSTGRES_PASSWORD` do compose só vale no initdb (§3). Quem exportar a `MOTOR_DATABASE_URL_ADMIN` daí em diante usa a nova |
| `app` | `MOTOR_APP_DB_PASSWORD` **e** a senha dentro da `MOTOR_DATABASE_URL` | edite o `.env` **antes** do `\password`, para a janela ficar curta; logo depois dele, `unset MOTOR_DATABASE_URL`, `up -d web` e a contagem do §9.0. Até o `web` ser recriado, conexão nova do pool falha na senha, e o RBAC pode ficar indisponível por alguns segundos (`banco_conexao.md` §3); depois do corte do P19, o login e as sessões também |
| `auditoria` | `MOTOR_AUDITORIA_DB_PASSWORD` | nada: nenhum serviço a usa |

Depois de qualquer troca, refaça o backup cifrado do `.env` (`secrets/env.enc.env`, §3); senão um
restore pelo SOPS devolve a senha velha.
