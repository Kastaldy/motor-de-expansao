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

**Duração estimada:** 45 a 60 min. **Os Passos 4 e 5 são uma sequência contínua** — a partir da
chave ligada, quem usa o piloto já é levado à nova tela de entrar, então não interrompa entre
eles. O Passo 3 (credencial do banco) pode ser feito antes, com calma.
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

## Passo 0 — Garantir que ninguém fica trancado (faça DIAS antes, não na janela)

Este é o único passo que não dá para desfazer depois: se alguém não consegue entrar, você vai
descobrir com a pessoa do outro lado da linha.

**São três conferências, nesta ordem.** A primeira é a que tranca a equipe inteira se for pulada;
as outras duas trancam pessoas individuais.

### 0.a — Todo mundo que usa o piloto EXISTE na tabela `usuarios`?

**Este é o passo que, pulado, tranca a equipe inteira** — e ele não tem nada a ver com senha.

Hoje quem libera o acesso é o arquivo `acesso_abas.json`, e quem autentica é o Authelia. **A
tabela `usuarios` não participa disso.** Ou seja: alguém pode estar usando o piloto há meses sem
ter linha nenhuma no banco. Depois do corte, sem linha em `usuarios` **não há como entrar**.

Liste os dois lados e compare:

```bash
cd /opt/motor-expansao/app

# 1) quem tem acesso hoje (o arquivo que o piloto lê)
cat /opt/motor-expansao/cadastro/acesso_abas.json

# 2) quem existe no banco
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U reservas_owner -d banco_de_reservas -c \
  "SELECT login_usuario, ativo FROM usuarios ORDER BY login_usuario;"
```

**Esperado:** todo login do arquivo aparece na tabela, e ativo.

**Se faltar alguém — e é o caso provável:** essas pessoas precisam ser **criadas pela tela de
Acessos** antes do corte. Criar pela tela é o caminho certo porque ele grava o hash da senha
inicial, o perfil e a trilha de quem criou; `INSERT` à mão no banco produz exatamente o hash
inválido que o passo 0.c existe para pegar.

> **Não tente adivinhar o perfil de ninguém.** Quem decide qual perfil cada pessoa recebe é quem
> repassou — os perfis (`expansao`, `consultoria`, `lideres`, `growth`) definem o que ela vê.

> **Contexto que ajuda a dimensionar:** esta conciliação entre o `users_database.yml` do Authelia
> e as linhas de `usuarios` é o conteúdo do bloco **`BLK-SEC-03-FU2`**, que o levantamento do P19
> já declarava "pré-requisito prático" do corte e que segue **pendente**. Se ele não foi feito,
> este passo é a versão mínima dele.

### 0.b — As duas senhas compartilhadas são a MESMA?

Hoje quase todo mundo usa **uma senha compartilhada** no Authelia. O motor também tem a sua, na
variável `MOTOR_SENHA_INICIAL`. Se as duas forem a mesma string, ninguém percebe o corte.

```bash
cd /opt/motor-expansao/app
grep '^MOTOR_SENHA_INICIAL=' .env
```

Compare com a senha que a equipe usa hoje para entrar.

- **Iguais:** ótimo. Siga para o 0.c.
- **Diferentes:** o corte vai funcionar, mas **todo mundo vai precisar da outra senha**. Duas
  saídas: mudar `MOTOR_SENHA_INICIAL` no `.env` para a senha que a equipe já conhece (e então o
  0.c é obrigatório, porque os hashes guardados continuam sendo os antigos), ou avisar a equipe
  da senha nova. **Decida isto com quem repassou** — não escolha sozinho.
- **Variável ausente ou vazia:** **pare**. Sem ela ninguém consegue entrar depois do corte e não
  há como criar usuário.

### 0.c — Alinhar os hashes e ver quem sobra

```bash
docker compose -f docker-compose.prod.yml run --rm \
  -e MOTOR_DATABASE_URL_ADMIN -e MOTOR_SENHA_INICIAL \
  web python -m motor_expansao.db alinhar-senhas --simular
```

> `--simular` **não escreve nada**. Rode assim primeiro, sempre.

**Esperado:** quatro contagens, e o que interessa são as duas últimas:

```
usuarios ativos: <N>
  ja' escolheram a propria senha, hash ok : <a>
  na senha inicial e JA' CONFEREM         : <b>
  na senha inicial e NAO conferem         : <c>
  escolheram, mas o hash esta' QUEBRADO   : <d>
```

- **`c` maior que zero:** são pessoas que estão na senha compartilhada mas cujo hash guardado não
  corresponde a ela — elas **não entrariam**. Rode o comando **sem** `--simular` para consertar:

  ```bash
  docker compose -f docker-compose.prod.yml run --rm \
    -e MOTOR_DATABASE_URL_ADMIN -e MOTOR_SENHA_INICIAL \
    web python -m motor_expansao.db alinhar-senhas
  ```

  Ele nomeia cada pessoa que alinhou. Rode o `--simular` de novo e confira que `c` virou **0**.

- **`d` maior que zero:** o comando **lista os logins e não os toca**, de propósito. Essas pessoas
  escolheram uma senha e o hash dela está inválido; consertar significaria **apagar a senha que
  elas escolheram**. Leve a lista a quem repassou: o caminho é redefinir cada uma pela tela de
  Acessos (senha temporária, válida 2 h) e combinar o repasse por telefone. **Não siga para o
  passo 1 com `d` maior que zero sem essa decisão tomada.**

> **O comando nunca toca em quem escolheu a própria senha** — e isso inclui **você/o dono**. É a
> propriedade que o torna seguro de rodar na preparação: ele conserta só quem está na senha
> compartilhada, para quem a senha compartilhada **é** a senha por definição.

> **Atenção ao mal-entendido comum:** quem está na senha compartilhada **entra normalmente** —
> essa pessoa tem um hash Argon2id de verdade. O risco não é "estar na senha inicial"; é o hash
> guardado não corresponder à senha que a pessoa digita.

O número `b` diz quantas pessoas vão ver o convite para trocar de senha no primeiro acesso.

---

## Passo 1 — Avisar as pessoas

**Antes de virar a chave**, avise quem usa o piloto. Três coisas:

1. **A tela de login vai mudar de aparência.** É esperado.
2. **Qual senha usar**, e isto depende do que o passo 0 encontrou: quem foi criado pela tela de
   Acessos (inclusive agora, na preparação) nasce na **senha inicial compartilhada** — a
   `MOTOR_SENHA_INICIAL`. Se ela for a mesma que a equipe já digita no Authelia (passo 0.b),
   ninguém precisa decorar nada novo. Se não for, **avise qual é** antes da janela.
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

## Passo 3 — Dar ao piloto a credencial do banco

**Sem este passo, o Passo 5 apaga o piloto inteiro.** A sessão vive em tabela, então o motor
precisa de credencial de banco para autenticar alguém — e ele **não avisa** que ela falta: a chave
do Passo 4 não consulta o banco, só a própria variável.

```bash
cd /opt/motor-expansao/app
grep '^MOTOR_DATABASE_URL=' .env
```

**Se vier vazia** — e é o estado de entrega —, preencha com a credencial do papel **`app`** (nunca
a do dono):

```
MOTOR_DATABASE_URL=postgresql://app:<senha-do-papel-app>@postgres:5432/banco_de_reservas
```

```bash
docker compose -f docker-compose.prod.yml up -d web
```

> **PARE E LEIA, porque este comando muda o comportamento do piloto NA HORA, antes de qualquer
> chave de autenticação.** Com a variável preenchida, o controle de abas troca de fonte: sai do
> `acesso_abas.json` e passa a ser o RBAC do banco, que é **deny-by-default**. Quem não tiver linha
> em `usuarios` com perfil **perde as abas** — o piloto abre vazio para essa pessoa.
>
> **Portanto: só preencha esta variável depois de o Passo 0.a estar fechado** (todo mundo do
> `acesso_abas.json` existe e está ativo em `usuarios`, com perfil). Se o 0.a não estiver fechado,
> **volte para ele** — este passo é o que torna aquela conciliação obrigatória, e não opcional.

**Confira, com o papel certo:**

```bash
docker compose -f docker-compose.prod.yml run --rm -e MOTOR_DATABASE_URL   web python -m motor_expansao.db privilegios
```

**Esperado:** `PRIVILEGIOS OK: o papel do piloto nao consegue o que nao deve, e consegue o que
precisa.` A primeira linha da saída diz `papel conectado:` — tem de ser **`app`**.

**Se vier `ERRO: defina MOTOR_DATABASE_URL`:** a variável não chegou ao container — confira que
você editou o `.env` da pasta certa e rodou o `up -d`.
**Se vier muitos `FALHA` e um recado sobre o dono:** você usou a credencial do **dono** em vez da
do `app`. Troque — usar a do dono anula o isolamento de privilégios inteiro.

---

## Passo 4 — Ligar a chave

```bash
# no .env:  MOTOR_AUTENTICACAO_PROPRIA=1
docker compose -f docker-compose.prod.yml up -d web
```

> **`up -d web`, NÃO `restart web`.** O `restart` não relê o `.env` — o container voltaria com o
> ambiente antigo e nada mudaria. Este é o erro mais fácil de cometer aqui.

**Esperado — e isto NÃO é "nada muda": o corte fica visível agora.** Até 25/09/2026 este
documento dizia que o piloto continuaria funcionando normalmente porque o Authelia ainda está na
frente. **É falso**, e a leitura errada faria você achar que quebrou algo quando na verdade
funcionou: com a chave ligada, o portão de sessão **apaga os headers de identidade que o Authelia
injeta** e passa a exigir o nosso cookie em toda rota `/api/*` que não seja
`login`/`logout`/`health`/`verify`. Ninguém tem esse cookie neste instante.

Então, a partir deste comando:

- quem estava usando o piloto **recebe 401 na próxima ação** e é levado para a nossa tela de
  entrar (`/entrar.html`);
- entre este passo e o próximo, quem entrar passa por **DOIS logins**: o do Authelia, na borda,
  e o nosso, na aplicação. É esperado e é temporário;
- **ver a nossa tela de entrar aqui é o sinal de que funcionou**, não de que quebrou.

Por isso o Passo 5 é a continuação natural deste, e não um passo para outro dia.

**Confira que a chave chegou:**

```bash
docker compose -f docker-compose.prod.yml exec web printenv MOTOR_AUTENTICACAO_PROPRIA
```

**Esperado:** `1`.

**Se vier vazio ou "não encontrado":** a branch `feat/p19-chave-no-compose` não está na `main`, ou
o `up -d` não rodou. **Pare** — o passo 5 sem isto derruba o piloto.

---

## Passo 5 — Trocar o bloco do Caddy

**Este é o passo que fecha o corte.** Dá para voltar (ver *Se precisar voltar atrás*), mas com o
piloto fora do ar no meio. O que a equipe SENTE começou no passo anterior, com a chave.

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

## Passo 6 — Conferir que funcionou

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
