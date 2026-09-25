# Repasse — o CORTE do P19: o motor passa a autenticar

> **Para quem vai executar.** Este documento é auto-contido: você não precisa conhecer a epic para
> segui-lo. Cada passo diz **o que rodar**, **o que esperar** e **o que fazer se vier diferente**.
> Onde houver `<algo>`, substitua.
>
> **Regra que vale acima de tudo:** se qualquer passo devolver algo que este documento não previu,
> **pare e chame quem repassou**. Nenhum passo aqui é urgente a ponto de justificar adivinhar.
>
> **Pré-requisito obrigatório:** o `docs/repasse_migracoes_p19.md` já foi executado por inteiro
> (migrations 018, 019 e 020 aplicadas). Este documento começa onde aquele termina.

**Duração estimada:** 30 a 45 min, com ~5 min de piloto fora do ar.
**Janela recomendada:** fora do horário de uso, com alguém disponível por telefone.

---

## O que este corte faz, em uma frase

Hoje o **Authelia** confere quem entra, na porta da rua. Depois deste corte, quem confere é o
**próprio motor** — e o Authelia continua de pé, mas só para a instância **argentina**.

## O que ele NÃO faz

- **Não toca na instância AR.** Ela continua atrás do Authelia, por decisão de 25/09/2026: o
  `web_ar` não tem banco, e a sessão própria vive em tabela. O bloco do Caddy dela **não muda**.
- **Não remove o serviço `authelia`.** Ele é compartilhado, e a AR depende dele.
- **Não apaga nem migra dado de ninguém.**

---

## Antes de começar — o que você precisa ter em mãos

| O quê | De onde vem |
|---|---|
| Acesso SSH à VPS | já configurado |
| `WEB_IMAGE` (digest da imagem nova) | job `publish-web` no Actions, depois do merge |
| Senha do dono do banco | com quem repassou |
| Este documento e o `deploy/caddy/piloto-br.Caddyfile.template` | o repositório |

### Os dois merges que precedem tudo

O trabalho está em **duas branches**, e as duas precisam estar na `main` antes de você subir a
imagem. A ordem entre elas é indiferente.

| Branch | O que leva |
|---|---|
| `feat/p19-sessao` | o motor, a rota `/api/verify`, a tela de entrar |
| `feat/p19-chave-no-compose` | a chave `MOTOR_AUTENTICACAO_PROPRIA` no `docker-compose.prod.yml` |

> **Sem a segunda, o corte é impossível de ligar.** O compose não tem `env_file`, então o container
> só recebe o que o bloco `environment:` lista. Pôr a chave no `.env` sem essa branch não faz
> efeito nenhum — e a falha é **muda**: nada quebra, o piloto sobe igual, e parece que a epic não
> funciona.

---

## Passo 0 — Medir quem seria trancado (faça DIAS antes, não na janela)

Este é o único passo que não dá para desfazer depois: se alguém não consegue entrar, você vai
descobrir com a pessoa do outro lado da linha.

```bash
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U reservas_owner -d banco_de_reservas -c \
  "SELECT login_usuario FROM usuarios WHERE ativo AND (senha_hash IS NULL OR senha_hash NOT LIKE '\$argon2id\$%');"
```

**Esperado:** `(0 rows)`.

**Se vier alguma linha:** cada uma é uma pessoa que **não entra** depois do corte. O motor só
aceita senha em formato Argon2id; linha semeada por SQL à mão (`hash_de_teste_*` e afins) é
recusada. **Pare** e resolva antes — quem repassou precisa criar a senha dessas pessoas pela tela
de Acessos.

> **Atenção ao mal-entendido comum:** quem está na **senha inicial compartilhada** entra
> normalmente — essa pessoa tem um hash Argon2id de verdade. O risco não é "estar na senha
> inicial"; é o hash não ser Argon2id.

### Quanta gente já tem senha própria

```bash
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U reservas_owner -d banco_de_reservas -c \
  "SELECT count(*) FILTER (WHERE senha_definida_em_usuario IS NOT NULL) AS propria, count(*) AS total FROM usuarios WHERE ativo;"
```

Isto é informativo, não um portão: quem ainda não trocou usa a senha inicial compartilhada e
consegue entrar. Serve para você saber quantas pessoas vão ver o convite de troca no primeiro
acesso.

---

## Passo 1 — Avisar as pessoas

**Antes de virar a chave**, avise quem usa o piloto. Três coisas:

1. **A tela de login vai mudar de aparência.** É esperado.
2. **A senha é a mesma de sempre** (a que elas usam no Authelia hoje) — desde que já tenham
   trocado pelo piloto. Quem nunca trocou usa a senha inicial compartilhada, que quem repassou
   informa.
3. **Se errarem a senha 5 vezes em 15 minutos, a conta trava.** E o servidor responde a mesma
   mensagem de "senha incorreta" — de propósito, para não avisar a quem varre nomes que acertou
   um. **Quem travar precisa pedir a um administrador para redefinir a senha pelo painel de
   Acessos**, o que destrava na hora.

> Deixe `docker compose -f docker-compose.prod.yml logs -f web` aberto durante a janela: é o
> único lugar onde a trava aparece nomeada.

---

## Passo 2 — Subir a imagem nova

```bash
cd /opt/motor-expansao/app
git pull
# edite o .env: WEB_IMAGE=<digest novo>
docker compose -f docker-compose.prod.yml up -d web
```

**Esperado:** o container reinicia e o piloto continua funcionando **exatamente como antes** — o
Authelia ainda autenticando. A chave ainda está desligada.

**Se o piloto não abrir:** volte o `WEB_IMAGE` para o digest anterior e suba de novo. Nada foi
cortado ainda.

> **A instância AR usa o MESMO `WEB_IMAGE`.** Editar o `.env` muda o digest das duas. O comando
> acima sobe só o `web` do BR, então a AR fica com o arquivo dizendo uma coisa e o processo
> rodando outra — e saltaria de digest no próximo `up -d` que alguém desse nela. Suba a AR também,
> na mesma janela:
> ```bash
> docker compose -f docker-compose.ar.yml up -d web_ar
> ```
> **Esperado:** a AR reinicia e continua atrás do Authelia, sem mudança visível.

---

## Passo 3 — Ligar a chave

```bash
# no .env:  MOTOR_AUTENTICACAO_PROPRIA=1
docker compose -f docker-compose.prod.yml up -d web
```

> **`up -d web`, NÃO `restart web`.** O `restart` não relê o `.env` — o container voltaria com o
> ambiente antigo e nada mudaria. Este é o erro mais fácil de cometer aqui.

**Esperado:** o piloto continua funcionando normalmente. O Authelia ainda está na frente, então
nada muda para quem está usando — mas agora as rotas de login do motor existem.

**Confira que a chave chegou:**

```bash
docker compose -f docker-compose.prod.yml exec web printenv MOTOR_AUTENTICACAO_PROPRIA
```

**Esperado:** `1`.

**Se vier vazio ou "não encontrado":** a branch `feat/p19-chave-no-compose` não está na `main`, ou
o `up -d` não rodou. **Pare** — o passo 4 sem isto derruba o piloto.

---

## Passo 4 — Trocar o bloco do Caddy

**Este é o passo irreversível na prática** (dá para voltar, mas com o piloto fora do ar no meio).

Abra `/opt/motor-expansao/app/Caddyfile` e substitua o bloco de
`piloto.ultra-expansao.tech` pelo conteúdo de `deploy/caddy/piloto-br.Caddyfile.template`.

> **NÃO TOQUE no bloco `piloto-ar.ultra-expansao.tech`.** Ele continua apontando para
> `authelia:9091`, e isso é decisão — a AR não tem banco e cairia inteira.

```bash
docker compose -f docker-compose.prod.yml exec caddy caddy validate --config /etc/caddy/Caddyfile
docker compose -f docker-compose.prod.yml exec caddy caddy reload --config /etc/caddy/Caddyfile
```

**Esperado:** `Valid configuration` e o reload sem erro.

**Atualize o backup cifrado**, senão um restore desfaz o corte em silêncio:

```bash
sops secrets/Caddyfile.enc   # cole o Caddyfile novo
```

---

## Passo 5 — Conferir que funcionou

1. **Abra `https://piloto.ultra-expansao.tech` numa janela anônima.**
   **Esperado:** a nossa tela de entrar (não a do Authelia).
2. **Entre com uma conta de teste.**
   **Esperado:** o piloto abre. Se a pessoa nunca trocou a senha, aparece o convite para trocar —
   com um botão "Agora não", porque a troca é **recomendada**, não obrigatória.
3. **Clique em Sair.**
   **Esperado:** volta para a tela de entrar, e voltar ao piloto **exige entrar de novo**.
4. **Confira que a AR não se mexeu:** abra `https://piloto-ar.ultra-expansao.tech`.
   **Esperado:** a tela do **Authelia**, como sempre foi.

**Se a tela de entrar não aparecer e o piloto der erro:** vá direto para *Se precisar voltar
atrás*, abaixo.

---

## Se precisar voltar atrás

**A ordem é o INVERSO da de ligar. Invertê-la derruba o piloto inteiro.**

1. **Primeiro o Caddy:** devolva o bloco antigo (`forward_auth authelia:9091` cobrindo tudo,
   **sem** o matcher `@protegido`) e recarregue.
2. **Só então a chave:** `MOTOR_AUTENTICACAO_PROPRIA=` (vazia) e
   `docker compose -f docker-compose.prod.yml up -d web`.

> Na ordem contrária, você fica com a chave desligada e o Caddy ainda perguntando ao
> `/api/verify` — que responde 404 com a chave desligada. O Caddy nega tudo que não for uma
> resposta de sucesso, e ninguém entra, **inclusive quem já estava dentro**.

### O que o rollback NÃO desfaz — leia antes de precisar

**Nada no banco precisa ser revertido.** As sessões abertas apenas deixam de ser consultadas.

**Mas as pessoas, sim.** O Authelia nunca soube das senhas criadas depois do corte:

| Quem | O que acontece no rollback |
|---|---|
| Trocou de senha depois do corte | Volta a precisar da senha que usava **antes** dele — a que ela acabou de aposentar |
| Recebeu senha temporária de um admin | Idem, na forma mais grave: ela **nunca escolheu** a senha que o Authelia guarda |
| Foi **criada** depois do corte | **Não entra de jeito nenhum** — não existe conta no Authelia |

**A mitigação, e ela custa pouco:** enquanto durar a janela de observação, **continue cadastrando
toda pessoa nova no `users_database.yml` do Authelia**, como se o corte não tivesse acontecido. É
esse cadastro paralelo que torna o rollback sobrevivível.

**Para saber quem seria afetado**, o banco responde:

```bash
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U reservas_owner -d banco_de_reservas -c \
  "SELECT login_usuario, senha_definida_em_usuario FROM usuarios WHERE senha_definida_em_usuario > '<data do corte>' ORDER BY 2;"
```

---

## Depois do corte — o que muda na operação

| Coisa | Antes | Depois |
|---|---|---|
| **Tirar acesso de alguém** | remover do `users_database.yml` + restart do Authelia | **desativar a linha em `usuarios`** pelo painel de Acessos — a sessão morre na requisição seguinte |
| **Postgres fora do ar** | o piloto continua servindo (só o banco fica indisponível) | **o piloto inteiro fica fora** — sem banco não há sessão, e o Caddy nega tudo |
| **Sessão expirada** | o Authelia redireciona | a SPA leva à nossa tela de entrar |

> **O item do meio é o mais importante para quem recebe alerta de madrugada.** O comentário do
> `healthcheck_vps.sh` ainda diz que o `web` não cai junto com o Postgres — isso deixa de valer
> aqui. Postgres fora = piloto BR indisponível.

---

## Instalar o cron de expurgo (pode ser depois, mas não esqueça)

Ele apaga IP e user-agent das sessões com mais de 90 dias — prazo decidido, não higiene opcional.

```bash
cp /opt/motor-expansao/app/scripts/cron/run_expurgo_sessoes.sh /opt/motor-expansao-infra/
chmod +x /opt/motor-expansao-infra/run_expurgo_sessoes.sh
```

O restante (o smoke com `--simular` e a linha do crontab) está no cabeçalho do próprio script.
Rode o `--simular` primeiro: ele conta e não escreve nada.

---

## Quem chamar

- **Durante a janela:** quem repassou este documento.
- **Se o piloto ficar fora e o rollback não resolver:** o bloco antigo do Caddy está no backup
  cifrado (`sops secrets/Caddyfile.enc`) e no histórico do git.
