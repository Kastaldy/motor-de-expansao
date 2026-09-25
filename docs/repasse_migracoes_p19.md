# Repasse — aplicar as migrations do P19 (018, 019, 020) na VPS

> **Para quem vai executar.** Este documento é auto-contido: você não precisa conhecer a epic
> para segui-lo. Cada passo diz **o que rodar**, **o que esperar** e **o que fazer se vier
> diferente**. Onde houver `<algo>`, substitua.
>
> **Regra que vale acima de tudo:** se qualquer passo devolver algo que este documento não
> previu, **pare e chame quem repassou**. Nenhum passo aqui é urgente a ponto de justificar
> adivinhar.

**Data do ensaio:** 23/09/2026 · **Ensaiado contra:** PostgreSQL 18.4 + PostGIS, banco de
ensaio com as 21 migrations aplicadas · **Duração estimada:** 20 a 30 min, com ~10 min de
piloto fora do ar.

---

## O que este repasse faz, em uma frase

Acrescenta três migrations ao banco de produção e concede dois privilégios. **Nada muda para
quem usa a plataforma**: a autenticação própria continua desligada e o Authelia segue
autenticando. É preparação, não virada de chave.

---

## Antes de começar — três coisas que precisam estar prontas

| # | Pré-requisito | Como conferir |
|---|---|---|
| 1 | A imagem nova do `web` publicada, com as migrations dentro | você recebeu o **digest** (`ghcr.io/kastaldy/motor-de-expansao/motor-expansao-web@sha256:…`) |
| 2 | Acesso SSH à VPS como root | `ssh` conecta |
| 3 | A senha do papel **dono** do banco (`reservas_owner`) | está no `.env` do compose, em `POSTGRES_OWNER_PASSWORD` |

Se faltar qualquer um, **não comece** — o passo 4 é irreversível sem restore.

---

## Passo 1 — Apontar o compose para a imagem nova (ainda sem trocar o que está no ar)

```bash
cd /opt/motor-expansao/app
cp .env .env.bak-$(date +%F)          # rede de segurança: volta em um `cp`
nano .env                              # troque WEB_IMAGE pelo digest novo
docker compose -f docker-compose.prod.yml config --quiet && echo OK
```

**Esperado:** a palavra `OK`, e nada mais.

**Por que isto não derruba nada:** editar o `.env` não mexe no container que está rodando. Os
passos seguintes usam `run --rm`, que cria um container **descartável** com a imagem nova — é
dele que saem as migrations. O que atende as pessoas continua na imagem antiga até o passo 7.

**Se vier erro:** o `config` falhou, então há erro de sintaxe ou variável faltando. Restaure
com `cp .env.bak-<data> .env` e chame quem repassou. Nada foi alterado no banco.

---

## Passo 2 — Parar o piloto (começa a janela de indisponibilidade)

```bash
docker compose -f docker-compose.prod.yml stop web
```

**Esperado:** `Container motor_expansao_web  Stopped`.

**Por que parar, e por que isto não é excesso de zelo:** a migration 019 altera a tabela
`usuarios`, e para isso o PostgreSQL precisa de um bloqueio exclusivo nela. Se alguém estiver
com uma sessão aberta e parada sobre essa tabela, o comando **espera indefinidamente** — e,
enquanto espera, **todo acesso à `usuarios` fica na fila**. Como é ela que responde "quem é
você e o que pode ver", o sistema inteiro travaria, sem erro e sem fim. Com o piloto parado,
essa situação não pode acontecer.

A partir daqui as pessoas veem o piloto fora do ar. **Some quando o passo 7 terminar.**

---

## Passo 3 — Ver o que o banco de produção já tem

```bash
export MOTOR_DATABASE_URL_ADMIN='postgresql://reservas_owner:<senha-do-dono>@postgres:5432/banco_de_reservas'

docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL_ADMIN \
  web python -m motor_expansao.db estado
```

**Esperado:** uma lista terminando em

```
  --  018  018-sessoes.sql
  --  019  019-senha-temporaria.sql
  --  020  020-sessao-origem.sql

pendentes: 018, 019, 020
```

**PARE E CHAME se aparecer qualquer pendente com número MENOR que 018.** O comando do passo 4
aplica **todas** as pendentes em ordem, e uma delas (a 013) falha de propósito quando a tabela
já tem gente cadastrada. O lote morreria ali e as três que interessam nunca seriam aplicadas.
Isso tem conserto, mas exige uma decisão que não cabe neste documento.

> `-e MOTOR_DATABASE_URL_ADMIN` **sem valor depois do `=`** é intencional: assim a senha é
> herdada do ambiente e não aparece na lista de processos, que qualquer usuário da máquina
> consegue ler.

---

## Passo 4 — Aplicar as três migrations

Primeiro em modo seco, que **não escreve nada**:

```bash
docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL_ADMIN \
  web python -m motor_expansao.db aplicar --simular
```

**Esperado:** `a aplicar: 018, 019, 020` e `(--simular: nada foi executado)`.

Agora para valer:

```bash
docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL_ADMIN \
  web python -m motor_expansao.db aplicar
```

**Esperado:**

```
a aplicar: 018, 019, 020
  aplicada 018  018-sessoes.sql
  aplicada 019  019-senha-temporaria.sql
  aplicada 020  020-sessao-origem.sql
```

**Se falhar no meio:** as anteriores ficam aplicadas **e registradas** — o runner não
"desfaz". Não rode de novo às cegas: anote a mensagem, chame quem repassou, e o conserto é
retomar do ponto onde parou.

---

## Passo 5 — Conceder dois privilégios (**o passo que se esquece**)

```bash
docker exec -it motor_expansao_postgres psql -U reservas_owner -d banco_de_reservas
```

Dentro do `psql`, cole as duas linhas:

```sql
GRANT SELECT, INSERT, UPDATE ON sessoes TO app;
GRANT USAGE ON SEQUENCE sessoes_id_sessao_seq TO app;
```

Saia com `\q`.

**Esperado:** `GRANT` duas vezes.

**Por que este passo existe, e por que ele é fácil de pular.** A migration 018 cria uma tabela
nova (`sessoes`). No PostgreSQL, tabela nova **não herda** permissão de ninguém: o papel que a
aplicação usa (`app`) simplesmente não a enxerga. Existe uma regra no banco que deveria cobrir
tabelas futuras, mas ela foi escrita para objetos criados pelo papel `postgres`, e aqui quem
cria é o `reservas_owner` — então ela não alcança.

**Isto foi ensaiado, não deduzido.** Em 23/09/2026 reproduzimos o cenário num banco de teste,
com tudo provisionado menos estas duas linhas. Resultado ao tentar abrir uma sessão:

```
InsufficientPrivilege -> permissão negada para tabela sessoes
```

Na prática, no dia em que a autenticação própria fosse ligada, **ninguém conseguiria entrar** —
e o erro apareceria longe da causa, dias ou semanas depois. Com as duas linhas aplicadas, a
mesma sessão abriu, validou e foi revogada normalmente.

---

## Passo 6 — Conferir que tudo ficou certo

```bash
docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL_ADMIN \
  web python -m motor_expansao.db conferir
```

**Esperado:** os seis números exatamente assim, e a última linha `CONFERENCIA OK`:

```
  ok  tabelas: 12 (esperado 12)
  ok  indices: 49 (esperado 49)
  ok  constraints CHECK: 14 (esperado 14)
  ok  chaves estrangeiras: 12 (esperado 12)
  ok  triggers: 7 (esperado 7)
  ok  colunas geometricas: 7 (esperado 7)
```

> **Vai sair um AVISO junto, e ele é ESPERADO aqui — não pare por causa dele.** Depois dos seis
> números, o comando imprime uma seção `== provisionamento (D20) ==` e, no fim dela:
>
> ```
>   AVISO: este papel tem INSERT direto em perfil_permissoes_historico. Num
>   cluster de teste isso e' esperado (voce conecta como dono); em PRODUCAO
>   significa que o D20 nao esta de pe e a auditoria da 009 nao protege nada.
> ```
>
> Ele sai **sempre neste passo**, e não é sintoma de nada: o passo 3 exportou
> `MOTOR_DATABASE_URL_ADMIN`, que é a credencial do **dono do schema** — e o dono tem INSERT em
> qualquer tabela dele por construção. O aviso existe para o caso de alguém rodar este comando
> com a credencial da **aplicação**; aí ele seria grave.
>
> Quem responde de verdade por essa pergunta é o comando logo abaixo, que roda com a credencial
> do piloto. É o resultado **dele** que decide se o D20 está de pé.

Agora a checagem de privilégios, **com a credencial da aplicação** (não a de dono):

```bash
docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL \
  web python -m motor_expansao.db privilegios
```

**Esperado:** `PRIVILEGIOS OK: o papel do piloto nao consegue o que nao deve, e consegue o que
precisa.`

**Se vier `PRIVILEGIOS COM 2 PROBLEMA(S)` citando `escrever em sessoes` e `usar a sequence de
sessoes`:** o passo 5 não pegou. Volte e refaça — é exatamente o que este comando existe para
detectar, e foi ensaiado devolvendo essa mensagem.

---

## Passo 7 — Subir o piloto na imagem nova (fecha a janela)

```bash
docker compose -f docker-compose.prod.yml up -d web
docker compose -f docker-compose.prod.yml ps web        # precisa dizer (healthy)
unset MOTOR_DATABASE_URL_ADMIN
```

**Esperado:** o container sobe e o `ps` mostra `(healthy)` em até ~1 min.

Confirme pelo navegador que o piloto abre e que dá para navegar normalmente. **Nada deve ter
mudado visualmente** — se mudou, é sinal de que algo saiu do previsto.

**O `unset` não é detalhe:** deixa a senha do dono fora do ambiente do terminal.

---

## Se precisar voltar atrás

**Durante os passos 1–3:** nada foi alterado. Restaure o `.env` (`cp .env.bak-<data> .env`) e
suba o `web` (`up -d web`).

**Depois do passo 4:** o caminho seguro **não é** desfazer as migrations — é voltar a imagem:

```bash
nano .env                                  # WEB_IMAGE = digest ANTIGO
docker compose -f docker-compose.prod.yml up -d web
```

A imagem antiga convive sem problema com as colunas novas: ela simplesmente não as conhece. As
migrations podem ficar aplicadas — não atrapalham.

---

## O que este repasse **não** faz

- **Não liga a autenticação própria.** A chave `MOTOR_AUTENTICACAO_PROPRIA` continua desligada,
  e o Authelia segue autenticando. Virar essa chave é outro movimento, e ele tem documento
  próprio: **`docs/repasse_corte_p19.md`**. Comece por ele quando for a hora — ele pressupõe
  este aqui já executado.
- **Não instala o cron de expurgo.** O passo está em `docs/repasse_corte_p19.md` (seção final),
  porque o caminho de cópia não é óbvio: o script vive em `/opt/motor-expansao/app/scripts/cron/`
  depois do `git pull`, e precisa ser copiado para `/opt/motor-expansao-infra/`.
- **Não toca em dado de ninguém.** As três migrations só acrescentam tabela e colunas vazias.

---

## Ficha rápida (para ter ao lado durante a execução)

| Passo | Comando | Esperado |
|---|---|---|
| 1 | `docker compose ... config --quiet` | `OK` |
| 2 | `docker compose ... stop web` | `Stopped` — **piloto fora do ar** |
| 3 | `... db estado` | `pendentes: 018, 019, 020` |
| 4 | `... db aplicar --simular` → `... db aplicar` | `aplicada 018/019/020` |
| 5 | `psql` → os dois `GRANT` | `GRANT` ×2 |
| 6 | `... db conferir` / `... db privilegios` | `CONFERENCIA OK` / `PRIVILEGIOS OK` |
| 7 | `docker compose ... up -d web` | `(healthy)` — **piloto no ar** |
