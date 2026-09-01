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
o `web` devolve o piloto ao comportamento pré-banco em segundos, sem rebuild. Ver §7.

## 1. Pré-condições

- Fase 2 aprovada: `docker-compose.prod.yml` é **Crítico**, então o merge exige a label
  `critica-aprovada` (DEC-016).
- Imagem `web` já em produção com o módulo `motor_expansao.db`. Sem ela, o runner de migration
  não existe no container e o passo 4 falha.
- `psql` **não** é necessário no host: tudo roda dentro dos containers.

Os três papéis e por que eles são três, não um:

| Papel | Quem cria | Para quê | Onde a credencial vive |
|---|---|---|---|
| dono do schema | o próprio compose (`POSTGRES_OWNER_USER`) | DDL das migrations; é o `SECURITY DEFINER` das triggers do D19 | `.env`, e **nunca** no ambiente do `web` |
| `app` | você, no passo 5 | tudo que a aplicação faz | dentro de `MOTOR_DATABASE_URL` |
| `auditoria` | você, no passo 5 | ler `perfil_permissoes_historico` | fora do compose; uso manual |

Dar ao piloto a credencial do dono anula o D19 em silêncio: a promessa de que a aplicação não
consegue apagar o próprio rastro depende inteiramente de ela **não ser dona** das tabelas.

## 2. Preencher o `.env`

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

`MOTOR_DATABASE_URL` fica **vazia** por enquanto — é o passo 7.

Gerar as senhas em hexadecimal não é preciosismo: caractere especial (`@ : / ?`) numa URL libpq
precisa de percent-encoding, e o sintoma de esquecer é um erro de *host não encontrado*, que manda
você procurar no lugar errado.

**`.env` mexido pede re-encriptação no SOPS+age.** Já é pendência aberta do BLK-OPS-01 desde os
segredos da API/bot; três senhas novas não é hora de adiar de novo.

## 3. Subir o serviço

```bash
cd /opt/motor-expansao/app
docker compose -f docker-compose.prod.yml up -d postgres
docker compose -f docker-compose.prod.yml logs --tail 30 postgres
docker compose -f docker-compose.prod.yml ps postgres      # tem de dizer (healthy)
```

O serviço não expõe porta no host: quem alcança é quem está na `app_net`. O primeiro boot cria o
cluster e instala o PostGIS, e demora mais que os seguintes.

Confira que a versão é a que o esquema assume — o **D18** depende do PostGIS 3.6 para o
`ST_Buffer` em `geography` preservar o SRID:

```bash
docker exec motor_expansao_postgres psql -U reservas_owner -d banco_de_reservas \
  -c "select version(), postgis_full_version();"
```

## 4. Aplicar as migrations

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

## 5. Provisionar `app` e `auditoria` (D20)

O script completo é o `sql/papeis-e-privilegios.md` do repositório `banco-de-reservas`.
Ele **não é migration** — quase tudo é `GRANT`, e por isso vive fora do runner e do controle de
versão de schema.

Rode o conteúdo dele por `psql` dentro do container, trocando as duas senhas de exemplo:

```bash
docker exec -it motor_expansao_postgres \
  psql -U reservas_owner -d banco_de_reservas -v DBNAME=banco_de_reservas
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

## 6. Semear os usuários reais

As migrations `012` e `013` trazem perfis, capacidades e a matriz — **não trazem pessoas**. Os
usuários são dado operacional com PII (nome, e-mail, `login_usuario`) e por isso **nunca** entram
em arquivo de migration versionado no git.

O `login_usuario` tem de ser exatamente o `Remote-User` que o Authelia entrega — é a chave que casa
a pessoa autenticada com a linha do banco (D23). Confira contra o
`authelia/users_database.yml` antes de inserir, e não contra a memória de ninguém.

Deixe **pelo menos um** usuário do perfil Growth pronto antes do passo 7: é o único que enxerga o
painel de Acessos, e é por ele que você verifica que o RBAC subiu certo.

## 7. Ligar — e o que fazer se der errado

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

# 2. o piloto enxerga o banco? — bloco `banco` da rota de admin
#    (o /api/health NÃO olha o banco, de propósito: ver §8)
curl -s https://<dominio>/api/acessos/saude-artefatos | jq .banco
```

E então, na tela: entre com um usuário de cada perfil e confirme que as abas aparecem e somem como
a matriz manda.

**Rollback (segundos, sem rebuild):** esvaziar `MOTOR_DATABASE_URL` e `docker compose up -d web`.
O piloto volta ao `acesso_abas.json` e serve exatamente como antes do banco. O container `postgres`
pode continuar de pé — nada no piloto o consulta enquanto a variável estiver vazia. É o interruptor
de incidente, e ele existe justamente para que "o banco está estranho" nunca vire "o piloto caiu".

**Rollback de migration não existe.** Nenhuma das migrations tem `down`, e é deliberado: desfazer
DDL sobre dado real é onde se perde dado. O caminho de volta é o restore do dump (§9).

## 8. O que passa a ser vigiado

- `scripts/healthcheck_vps.sh` agora vigia **7** containers — `motor_expansao_postgres` entrou na
  lista. Sem essa linha, o banco fora do ar seria invisível: a leitura de parquet continua
  servindo, e só o RBAC começa a negar.
- O **healthcheck do container `web` não consulta o banco**, e isso é escolha. Amarrar os dois faria
  o Docker reiniciar o `web` a cada piscada do Postgres, derrubando junto tudo que não depende dele.
  O `depends_on` é `service_started`, não `service_healthy`, pelo mesmo motivo.
- O `/api/health` segue mudo (pentest Onda B #8): é rota livre. O diagnóstico do banco mora na rota
  de admin.

## 9. Backup e restore

Instalação do cron: cabeçalho do [`scripts/cron/run_backup_banco.sh`](../scripts/cron/run_backup_banco.sh).
Roda 05:10 UTC (02:10 BRT) — dentro da janela do BLK-SEC-04 e 50 min antes da coleta de domingo.

**Por que isto existe.** O BLK-SEC-04 aceitou o risco em 13/07 porque "quase tudo é regenerável
pelos pipelines". RBAC, eventos, áreas de estudo e contratos nascem no app e **nenhum pipeline os
regenera** — é o gatilho de reabertura que o próprio bloco nomeia. O dump é `-Fc` (custom) e não SQL
puro justamente para permitir `pg_restore -t`: restaurar uma tabela sem derrubar o resto era o
"restore granular" listado como gap aceito.

**Cópia off-box é restic, não rclone.** O dump carrega e-mail, `login_usuario`, `senha_hash` e o `ip`
dos eventos. O restic cifra antes de o arquivo sair da máquina, com chave que o dono do bucket não
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

## 10. Estado do disco

O volume `postgres_data` é o **único** do compose que nenhum pipeline regenera. `caddy_data` se
refaz sozinho, `bot_data` custa um relogin, os parquets saem dos pipelines. Este não.

`mem_limit: 2g` é teto conservador: a KVM4 tem 16 GB e os tetos de `web` (8g) e `api` (6g) já somam
14. O candidato a estourar isso é o ETL da fase 5 (dissolve por UF) — quando ele existir, **medir
antes de subir o teto**, não depois de um OOM.
