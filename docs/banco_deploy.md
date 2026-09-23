# Runbook — subir o banco na VPS

> Como o PostgreSQL/PostGIS entra em produção: ordem de subida, provisionamento dos papéis
> (D20), backup, restore e rollback. Complementa o [`banco_conexao.md`](banco_conexao.md),
> que descreve como o motor **fala** com o banco; aqui é como ele **passa a existir**.
>
> Fonte do esquema: repositório `banco-de-reservas`. Nenhum DDL nasce aqui.
> Versão: Setembro 2026 · Executor: Vinícius

## 0. A ordem importa — leia antes de qualquer comando

A sequência abaixo **não é sugestão de organização**. Trocar dois passos de lugar causa
indisponibilidade real:

> **`MOTOR_DATABASE_URL` é o ÚLTIMO passo, e só depois de os usuários existirem.**
> No instante em que ela é preenchida, o RBAC do banco assume o controle das abas
> (`banco_no_comando()` em `web/server/acesso.py`). O comportamento é *deny-by-default*:
> quem o Authelia autentica mas que **não tem linha em `usuarios`** não recebe capacidade
> nenhuma. Ligar a variável com a tabela vazia tranca **todo mundo para fora**, inclusive você.

O caminho de volta é curto e vale saber de antemão: esvaziar `MOTOR_DATABASE_URL` e reiniciar
o `web` devolve o piloto ao comportamento pré-banco em segundos, sem rebuild. Ver §8.

E nada disto vai para a VPS sem ter rodado antes na máquina: o ensaio local está no **§1**.

## 1. Ensaio na máquina, antes da VPS

**Nada sobe sem ter rodado aqui primeiro.** A sequência das seções seguintes é escrita para a VPS,
mas o essencial dela — migrations do zero, provisionamento do D20, RBAC de ponta a ponta, dump e
restore — roda inteiro no PostgreSQL nativo desta máquina, sem Docker.

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

O que **não** tem equivalente local, porque esta máquina não tem Docker:

- o bloco `postgres` do compose subir de fato (tag da imagem, `healthcheck`, `shm_size`,
  `POSTGRES_INITDB_ARGS`);
- a ordem de subida do `depends_on`;
- o `run_backup_banco.sh`, que é bash e fala com `docker exec`.

O que cobre esse resto, na falta de Docker aqui:

1. `tests/contracts/test_compose_banco.py` trava as quatro invariantes estruturais (variável
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

```powershell
$PGBIN = "C:\Program Files\PostgreSQL\18\bin"
& "$PGBIN\createdb" -U postgres banco_de_reservas_ensaio
```

> **`PYTHONPATH` primeiro, ou o Python acha o pacote errado.** O projeto usa layout `src/`, e
> o `motor_expansao` instalado em modo editável aponta para o **checkout principal** — onde o
> módulo `db` não existe, porque ele só vive nesta branch. Estar dentro da worktree não basta:
> o diretório atual não expõe `motor_expansao`. Sem a linha abaixo o erro é
> `No module named motor_expansao.db`, que parece pacote quebrado e não é.
>
> **Não conserte com `pip install -e .` daqui.** Isso repontaria o pacote para esta branch em
> todo o seu Python, e o trabalho no checkout principal passaria a importar código desta branch
> sem aviso nenhum. O `PYTHONPATH` vale só para o terminal onde você o define.

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

```powershell
# Mesma ressalva do §1.2 — se este for um terminal NOVO, repita o PYTHONPATH.
$env:PYTHONPATH = "C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\.claude\worktrees\wt-db\src"

# Os artefatos vivem no CHECKOUT PRINCIPAL, nao aqui: eles sao gitignored e nao
# viajam para a worktree (1 parquet contra 11.252). Apontar para o `data/` daqui da'
# um piloto que sobe e nao carrega nada -- e o sintoma nao acusa a causa.
#
# Ler o diretorio do checkout principal e' seguro: o piloto e' READ-ONLY sobre os
# artefatos, e ha teste que trava isso (`test_leituras_nao_mutam_artefatos`).
$env:MOTOR_DATA_DIR = "C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\data"

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

Ao terminar, `dropdb` nos dois bancos de ensaio.

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
| dono do schema | o próprio compose (`POSTGRES_OWNER_USER`) | DDL das migrations; é o `SECURITY DEFINER` das triggers do D19 | `.env`, e **nunca** no ambiente do `web` |
| `app` | você, no passo 6 | tudo que a aplicação faz | dentro de `MOTOR_DATABASE_URL` |
| `auditoria` | você, no passo 6 | ler `perfil_permissoes_historico` | fora do compose; uso manual |

Dar ao piloto a credencial do dono anula o D19 em silêncio: a promessa de que a aplicação não
consegue apagar o próprio rastro depende inteiramente de ela **não ser dona** das tabelas.

## 3. Preencher o `.env`

Na VPS, em `/opt/motor-expansao/app/.env`, a partir do bloco do `.env.example`:

```bash
openssl rand -hex 24   # uma vez para o dono, outra para `app`, outra para `auditoria`
```

```dotenv
POSTGRES_DB=banco_de_reservas
POSTGRES_OWNER_USER=reservas_owner
POSTGRES_OWNER_PASSWORD=<gerado>
MOTOR_DATABASE_URL=
```

`MOTOR_DATABASE_URL` fica **vazia** por enquanto — é o passo 8.

Gerar as senhas em hexadecimal não é preciosismo: caractere especial (`@ : / ?`) numa URL libpq
precisa de percent-encoding, e o sintoma de esquecer é um erro de *host não encontrado*, que manda
você procurar no lugar errado.

**`.env` mexido pede re-encriptação no SOPS+age.** Já é pendência aberta do BLK-OPS-01 desde os
segredos da API/bot; três senhas novas não é hora de adiar de novo.

## 4. Subir o serviço

**Valide antes de subir.** `config` resolve o compose inteiro e não inicia nada — é onde erro de
sintaxe ou variável faltando aparece de graça, sem container envolvido. É também o único passo desta
seção que não tem equivalente no ensaio local (§1.1):

```bash
cd /opt/motor-expansao/app
docker compose -f docker-compose.prod.yml config --quiet && echo OK
```

```bash
docker compose -f docker-compose.prod.yml up -d postgres
docker compose -f docker-compose.prod.yml logs --tail 30 postgres
docker compose -f docker-compose.prod.yml ps postgres      # tem de dizer (healthy)
```

**Este passo não toca no piloto.** Enquanto `MOTOR_DATABASE_URL` estiver vazia, nada consome o
banco — o container sobe ao lado, isolado, e o `web` sequer o consulta. Subir o serviço e ligar o
banco no piloto (§8) são dois passos com riscos muito diferentes, e estão separados de propósito.

O serviço não expõe porta no host: quem alcança é quem está na `app_net`. O primeiro boot cria o
cluster e instala o PostGIS, e demora mais que os seguintes.

Se a tag `postgis/postgis:18-3.6` não resolver, o `up` falha no `pull` sem criar nada — confira a
tag disponível e ajuste o compose. A restrição real é PostGIS **3.6** (D18) sobre PostgreSQL **18**,
que é a combinação em que o esquema foi validado.

Confira que a versão é a que o esquema assume — o **D18** depende do PostGIS 3.6 para o
`ST_Buffer` em `geography` preservar o SRID:

```bash
docker exec motor_expansao_postgres psql -U reservas_owner -d banco_de_reservas \
  -c "select version(), postgis_full_version();"
```

## 5. Aplicar as migrations

O runner precisa da credencial do **dono** (migration é DDL). Ela é passada na invocação, num
container efêmero, e nunca entra no ambiente do processo `web` que atende requisição:

```bash
export MOTOR_DATABASE_URL_ADMIN='postgresql://reservas_owner:<senha>@postgres:5432/banco_de_reservas'

docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL_ADMIN \
  web python -m motor_expansao.db estado           # o que falta, sem executar nada

docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL_ADMIN \
  web python -m motor_expansao.db aplicar --simular # o SQL que sairia

docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL_ADMIN \
  web python -m motor_expansao.db aplicar

unset MOTOR_DATABASE_URL_ADMIN
```

`-e MOTOR_DATABASE_URL_ADMIN` **sem valor** herda do ambiente: assim a senha não aparece no `argv`
do `docker`, que é legível por qualquer usuário em `ps`.

O runner grava o que aplicou em `migracoes_aplicadas` e recusa reaplicar. Se uma migration falhar,
ela para ali — as anteriores ficam aplicadas e registradas, e a correção é retomar do ponto, não
recomeçar.

## 6. Provisionar `app` e `auditoria` (D20)

O script completo é o `sql/papeis-e-privilegios.md` do repositório `banco-de-reservas`.
Ele **não é migration** — quase tudo é `GRANT`, e por isso vive fora do runner e do controle de
versão de schema.

Rode o conteúdo dele por `psql` dentro do container, trocando as duas senhas de exemplo:

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

Rode os blocos de **validação** e **teste** do próprio documento em seguida. O teste de append-only
tem de ser rodado **depois** do `ALTER TABLE`, ou você lê como sucesso um teste que não rodou.

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

**A senha de quem é criado pela tela vem de `MOTOR_SENHA_INICIAL`,** e ela precisa estar no `.env`
antes do primeiro `Criar usuário` — sem ela a rota responde 503 com mensagem explícita, em vez de
criar alguém com uma senha que ninguém sabe qual é. Cada pessoa recebe o hash Argon2id dela com sal
próprio e nasce marcada para trocar; a troca é em `PATCH /api/me/senha`, que **não** exige a
allowlist do painel — trocar a própria senha não é ato de administração. A coluna `Senha` da tela
diz quem já saiu da inicial, e é a fila que o corte do P19 precisa zerar.

> Se você estiver semeando a mão (o primeiro, ou o `dados-ficticios.md` num banco de ensaio), o
> `senha_hash` que você inserir **não** vai autenticar nada — e desde a 016 isso fica visível:
> `senha_definida_em_usuario` nasce nulo e `deve_trocar_senha_usuario` nasce `TRUE`, o que é a
> verdade sobre uma linha semeada. Para gerar um hash de verdade fora da tela:
> `python -c "from motor_expansao.db import senhas; print(senhas.gerar('<a senha>'))"` (exige o
> extra `auth`).

## 8. Ligar — e o que fazer se der errado

```dotenv
MOTOR_DATABASE_URL=postgresql://app:<senha>@postgres:5432/banco_de_reservas
```

```bash
docker compose -f docker-compose.prod.yml up -d web
```

O host é o **nome do serviço** (`postgres`), não o `container_name`.

Verificação, nesta ordem:

```bash
# 1. o motor concorda com o banco? (tabelas, colunas, índices, papéis, versão)
docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL_ADMIN \
  web python -m motor_expansao.db conferir

# 2. o papel `app` continua incapaz do que nao deve? (F6.2)
docker compose -f docker-compose.prod.yml run --rm web \
  python -m motor_expansao.db privilegios

# 3. o piloto enxerga o banco? — bloco `banco` da rota de admin
#    (o /api/health NÃO olha o banco, de propósito: ver §9)
curl -s https://<dominio>/api/acessos/saude-artefatos | jq .banco
```

E então, na tela: entre com um usuário de cada perfil e confirme que as abas aparecem e somem como
a matriz manda.

**Rollback (segundos, sem rebuild):** esvaziar `MOTOR_DATABASE_URL` e `docker compose up -d web`.
O piloto volta ao `acesso_abas.json` e serve exatamente como antes do banco. O container `postgres`
pode continuar de pé — nada no piloto o consulta enquanto a variável estiver vazia. É o interruptor
de incidente, e ele existe justamente para que "o banco está estranho" nunca vire "o piloto caiu".

**Rollback de migration não existe.** Nenhuma das migrations tem `down`, e é deliberado: desfazer
DDL sobre dado real é onde se perde dado. O caminho de volta é o restore do dump (§10).

## 9. O que passa a ser vigiado

- `scripts/healthcheck_vps.sh` agora vigia **7** containers — `motor_expansao_postgres` entrou na
  lista. Sem essa linha, o banco fora do ar seria invisível: a leitura de parquet continua
  servindo, e só o RBAC começa a negar.
- O **healthcheck do container `web` não consulta o banco**, e isso é escolha. Amarrar os dois faria
  o Docker reiniciar o `web` a cada piscada do Postgres, derrubando junto tudo que não depende dele.
  O `depends_on` é `service_started`, não `service_healthy`, pelo mesmo motivo.
- O `/api/health` segue mudo (pentest Onda B #8): é rota livre. O diagnóstico do banco mora na rota
  de admin.

## 9.1 Expurgo da origem das sessões (retenção do P15)

Instalação do cron: cabeçalho do
[`scripts/cron/run_expurgo_sessoes.sh`](../scripts/cron/run_expurgo_sessoes.sh).
Roda **04:40 UTC (01:40 BRT), diariamente** — e o horário não é arbitrário.

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

Antes de instalar, rode uma vez em modo seco (é o smoke documentado no cabeçalho):

```bash
/opt/motor-expansao-infra/run_expurgo_sessoes.sh --simular
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

```bash
# 1. integridade do arquivo, antes de qualquer coisa
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

Uma tabela só, sem tocar nas outras:

```bash
docker exec -i motor_expansao_postgres \
  pg_restore -U reservas_owner -d banco_de_reservas -t eventos --data-only \
  < banco_de_reservas_<carimbo>.dump
```

**O restore em base limpa faz parte do aceite do BLK-SEC-04**, não é opcional. Backup que ninguém
restaurou é backup que ninguém tem.

## 11. Estado do disco

O volume `postgres_data` é o **único** do compose que nenhum pipeline regenera. `caddy_data` se
refaz sozinho, `bot_data` custa um relogin, os parquets saem dos pipelines. Este não.

`mem_limit: 2g` é teto conservador: a KVM4 tem 16 GB e os tetos de `web` (8g) e `api` (6g) já somam
14. O candidato a estourar isso é o ETL da fase 5 (dissolve por UF) — quando ele existir, **medir
antes de subir o teto**, não depois de um OOM.
