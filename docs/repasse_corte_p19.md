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
| Senha do dono do banco (`reservas_owner`) | no `.env` do compose, em `POSTGRES_OWNER_PASSWORD` |
| **Senha do papel `app`** | **com quem repassou** — ela vive DENTRO da `MOTOR_DATABASE_URL` e, se essa variável está vazia (o estado de entrega), o valor não existe em lugar nenhum que você alcance. Foi gerada no provisionamento do banco (`docs/banco_deploy.md`, seção dos três papéis). **Sem ela o Passo 3 para**, e o Passo 3 é o que impede o Passo 5 de apagar o piloto |
| **Seu login na allowlist do painel de Acessos** | a env `MOTOR_ACESSOS_ADMIN_USUARIOS` do `.env`. Sem o seu login lá, o painel responde **404** para você — e é a única ferramenta de criar gente e destravar conta |
| **Uma conta sua no Authelia**, com senha | **com quem repassou.** Estar na allowlist acima não basta: **hoje** o Caddy exige sessão do Authelia no host inteiro, então sem conta no `users_database.yml` o navegador nunca chega no painel de Acessos. Peça que o seu login seja a **mesma string** nos dois lugares |
| **A senha compartilhada que a equipe digita hoje** | **com quem repassou** — ela **não existe em lugar nenhum do servidor**: o `users_database.yml` guarda só o hash, que não se desfaz. Sem ela o Passo 0.b não fecha, porque ele é uma comparação entre dois valores e o servidor só te dá um |
| **`sops` instalado e a chave que decifra `secrets/Caddyfile.enc`** | **com quem repassou.** Teste **antes da janela**: `sops -d secrets/Caddyfile.enc \| head -1` tem de imprimir a primeira linha do Caddyfile. Se recusar, pare e peça — sem isso o último passo do corte não fecha, e o backup cifrado fica descrevendo um Caddyfile que não existe mais |
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

Hoje quem autentica é o Authelia e quem libera as abas é o `acesso_abas.json`. **A tabela
`usuarios` não participa de nada disso.** Ou seja: alguém pode estar usando o piloto há meses sem
ter linha nenhuma no banco. Depois do corte, sem linha em `usuarios` **não há como entrar**.

> **COMPARE CONTRA O AUTHELIA, NÃO CONTRA O `acesso_abas.json`.** O JSON aceita uma entrada
> curinga `"*"`, que dá abas a **qualquer pessoa autenticada** — então ele pode listar três logins
> enquanto vinte pessoas usam o piloto, e uma conferência contra ele passaria **verde** deixando
> dezessete trancadas. A lista de quem consegue entrar hoje é o **`users_database.yml` do
> Authelia**. Se houver `"*"` no JSON, ele não serve como lista de ninguém.

Liste os dois lados e compare:

```bash
cd /opt/motor-expansao/app

# 1) quem consegue AUTENTICAR hoje — esta é a lista que importa
grep -nE '^  [a-zA-Z0-9_.-]+:' authelia/users_database.yml

# 1b) o JSON de abas é DIAGNÓSTICO, não lista: veja se tem curinga
grep -c '"[*]"' /opt/motor-expansao/cadastro/acesso_abas.json

# 2) quem existe no banco
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U reservas_owner -d banco_de_reservas -c \
  "SELECT login_usuario, ativo FROM usuarios ORDER BY login_usuario;"
```

**Esperado:** todo login do `users_database.yml` aparece na tabela, e ativo.

> **Confira também a direção inversa**, que é a que ninguém mede: todo `login_usuario` da tabela tem
> entrada no `users_database.yml`? Quem foi criado pela tela de Acessos e não foi cadastrado lá entra
> normalmente **depois** do corte — e desaparece se houver rollback, porque o Authelia nunca soube
> dele. É a mesma consequência da última linha da tabela de rollback, e ela não nomeia esse caso.

**Se faltar alguém — e é o caso provável:** essas pessoas precisam ser **criadas pela tela de
Acessos** antes do corte. Criar pela tela é o caminho certo porque ele grava o hash da senha
inicial, o perfil e a trilha de quem criou; `INSERT` à mão no banco produz exatamente o hash
inválido que o passo 0.c existe para pegar.

> **Não tente adivinhar o perfil de ninguém.** Quem decide qual perfil cada pessoa recebe é quem
> repassou — os perfis (`expansao`, `consultoria`, `lideres`, `growth`) definem o que ela vê.

> ### A ORDEM AQUI É CONTRAINTUITIVA, e sem ela você fica num impasse
>
> Criar gente pela tela de Acessos **exige o banco configurado** — ou seja, o Passo 3. E o Passo 3
> manda só ser feito depois deste 0.a fechado. Parece circular; a saída é esta:
>
> 1. Faça o **Passo 3** (preencher `MOTOR_DATABASE_URL` e subir o `web`).
> 2. **A partir desse instante o piloto fica degradado para a equipe, e é esperado:** o controle de
>    abas troca do `acesso_abas.json` para o RBAC do banco, que é deny-by-default, então quem ainda
>    não tem linha com perfil **abre o piloto vazio**. Ninguém perde dado; ninguém consegue
>    trabalhar.
> 3. **Você continua entrando no painel de Acessos**, porque ele é liberado pela env
>    `MOTOR_ACESSOS_ADMIN_USUARIOS` e **não** pelo RBAC — é essa independência que desfaz o
>    impasse.
> 4. Crie todas as pessoas, com perfil. À medida que você cria, as abas voltam para cada uma.
>
> **Portanto: faça o Passo 3 e este 0.a na MESMA sessão, com tempo reservado**, e avise a equipe de
> que haverá uma janela em que o piloto abre vazio. Não é o corte ainda — mas a equipe sente.

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

  > **Se você mudar a variável no `.env`, suba o `web` antes de seguir:**
  > ```bash
  > docker compose -f docker-compose.prod.yml up -d web
  > ```
  > Este é o único ponto do documento que edita o `.env` sem subir o container, e a falha é muda: o
  > comando do 0.c usa `run --rm`, que relê o `.env` a cada invocação, então **os hashes ficariam
  > alinhados com o valor novo enquanto o container no ar continua criando gente com o antigo**.
  > Quem fosse criado pela tela de Acessos até o próximo restart receberia a senha velha. Só depois
  > de subir, rode o 0.c.
- **Variável ausente ou vazia:** **pare**. Sem ela ninguém consegue entrar depois do corte e não
  há como criar usuário.

### 0.c — Alinhar os hashes e ver quem sobra

Antes dos dois comandos abaixo, **exporte a credencial do DONO do schema** — e isto não é
formalidade:

```bash
export MOTOR_DATABASE_URL_ADMIN='postgresql://reservas_owner:<senha-do-dono>@postgres:5432/banco_de_reservas'
```

> **Se a senha do dono tiver `@`, `:`, `/` ou `?`, ela precisa de percent-encoding** aqui (`@` vira
> `%40`, `:` vira `%3A`, `/` vira `%2F`, `?` vira `%3F`). Sem isso o erro sai como "autenticação
> falhou" ou "host não encontrado", nunca como "URL malformada".

> **Se você esquecer o `export`, o comando NÃO reclama — ele roda com a credencial errada.** Medido:
> sem essa variável, o runner cai para `MOTOR_DATABASE_URL`, que é a credencial do papel **`app`** —
> e o `app` tem `UPDATE` em `usuarios` por desenho. Ou seja, o passo que este documento chama de "o
> único que não dá para desfazer" reescreveria hashes pela credencial da aplicação, em silêncio,
> sem uma linha de aviso.
>
> **A saída do comando NÃO nomeia o papel conectado** — não há como descobrir pela tela com qual
> credencial ele escreveu. Por isso a conferência é **antes** de rodar, sobre a variável:
> ```bash
> echo "$MOTOR_DATABASE_URL_ADMIN" | cut -d@ -f1
> ```
> Tem de imprimir `postgresql://reservas_owner:<a senha>`. Se sair vazio, o `export` não pegou neste
> terminal — refaça antes de continuar.
>
> **Se vier `ERRO: defina MOTOR_DATABASE_URL_ADMIN (ou MOTOR_DATABASE_URL) com a credencial do DONO
> do schema`:** nem a variável nem o fallback existem. Exporte e repita — nada foi escrito.
>
> Ao terminar o 0.c, `unset MOTOR_DATABASE_URL_ADMIN`. Ela é a credencial que aplica DDL; deixá-la
> no ambiente de uma sessão que continua aberta é o que este repositório evita de propósito.

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

> **Olhe o `N` primeiro, porque é ele que denuncia o pior cenário.** `usuarios ativos` tem de ser
> **igual ao número de logins que você conciliou no 0.a**. Se vier `0`, ou bem abaixo daquilo, o 0.a
> não está fechado: as quatro contagens vêm zeradas, o comando imprime `nada a alinhar` — e isso
> significa **"não há ninguém no banco"**, não "está tudo certo". Seguir daqui leva a um corte em que
> a rede inteira fica trancada. Volte ao 0.a.

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
>
> **Num banco recém-criado essa proteção não se aplica a ninguém**, e é preciso saber disso: "escolheu
> a própria senha" é `senha_definida_em_usuario`, que nasce **nulo em toda linha**, inclusive na sua.
> Se você semeou a si mesmo por SQL com o hash de uma senha **sua**, este comando o substitui pela
> `MOTOR_SENHA_INICIAL` — ele imprime `alinhada: <seu login>`, mas não pede confirmação nem tem como
> saber que aquilo era uma senha escolhida. Semeando com `hash_da_senha_inicial()` (§7 do
> `banco_deploy.md`) o problema não existe: a linha nasce já conferindo.

> **Atenção ao mal-entendido comum:** quem está na senha compartilhada **entra normalmente** —
> essa pessoa tem um hash Argon2id de verdade. O risco não é "estar na senha inicial"; é o hash
> guardado não corresponder à senha que a pessoa digita.

O número `b` diz quantas pessoas vão ver o convite para trocar de senha no primeiro acesso.

---

## Onde fica o painel de Acessos (você vai usá-lo quatro vezes)

Este documento manda criar gente, redefinir senha e destravar conta **pelo painel de Acessos**.
Ele é uma aba do próprio piloto (`https://piloto.ultra-expansao.tech`), chamada **Acessos**, e não
aparece para todo mundo:

- quem o vê é **só** quem está na env `MOTOR_ACESSOS_ADMIN_USUARIOS` (lista separada por vírgula,
  comparada com o seu login, sem diferenciar maiúsculas) — e **"o seu login", hoje, é o seu usuário
  do Authelia**: é a chave que o `grep` do 0.a acabou de listar no `users_database.yml`, não o seu
  usuário de SSH nem o seu e-mail;
- **sem a env preenchida, o painel está desligado para todos** — em produção e em dev;
- quem não pode vê **404**, não "acesso negado": a existência do painel não é anunciada. Então um
  404 aqui é quase sempre "seu login não está na env", e não "a rota não existe".

Confira antes da janela:

```bash
cd /opt/motor-expansao/app && grep '^MOTOR_ACESSOS_ADMIN_USUARIOS=' .env
```

**Se o seu login não estiver ali**, acrescente-o (separado por vírgula) e
`docker compose -f docker-compose.prod.yml up -d web`. **Depois do corte** o painel passa a
identificar você pela sessão, então o seu login também precisa existir em `usuarios` — o Passo 0.a
cobre isso se você se incluir na conciliação.

> **Use a MESMA string nos três lugares:** o seu usuário no Authelia, a entrada em
> `MOTOR_ACESSOS_ADMIN_USUARIOS`, e o `login_usuario` da sua linha em `usuarios`. São namespaces
> diferentes — antes do corte o painel te identifica pelo header do Authelia, depois pela sessão do
> banco — e é justamente por isso que divergir é perigoso: se você se cadastrar em `usuarios` com
> outra grafia (ou com o e-mail), o painel te devolve **404 no instante do corte**, e ele é a única
> ferramenta de destravar conta. Você ficaria sem a chave e sem a fechadura ao mesmo tempo.

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
   um. Duas saídas, e diga as duas: **esperar** — a janela é MÓVEL, então a trava se desfaz
   sozinha quando a tentativa mais antiga completa 15 minutos — ou **pedir a um administrador
   para redefinir a senha** pelo painel de Acessos, o que destrava na hora. A segunda depende de
   haver um administrador disponível; a primeira, não.

> Deixe `docker compose -f docker-compose.prod.yml logs -f web` aberto durante a janela: é o
> único lugar onde a trava aparece nomeada.

---

## Passo 2 — Subir a imagem nova

```bash
cd /opt/motor-expansao/app
git pull
cp .env .env.bak-$(date +%F)     # guarda o digest ATUAL; é para onde você volta
grep '^WEB_IMAGE=' .env          # anote esta linha
# edite o .env: WEB_IMAGE=<digest novo>
docker compose -f docker-compose.prod.yml up -d web
```

> **A cópia não é zelo, é o caminho de volta.** A linha seguinte sobrescreve o `WEB_IMAGE`, e o
> valor antigo deixa de existir no arquivo. Sem a cópia, a instrução de rollback aqui embaixo é
> impossível de executar — e você descobriria isso justamente no momento em que o piloto não abriu.

> **Se você já trocou o `WEB_IMAGE` no runbook das migrations** e nenhuma imagem nova foi publicada
> desde então, este passo é **só conferência**: o `grep` acima tem de mostrar exatamente o digest que
> você recebeu. Não existe um segundo build.

**Esperado:** o container reinicia e o piloto continua funcionando **exatamente como antes** — o
Authelia ainda autenticando. A chave ainda está desligada.

> **A instância ARGENTINA usa o MESMO `WEB_IMAGE`.** Você acabou de editar o `.env`, que é
> compartilhado: a AR ficou com o arquivo dizendo um digest e o processo rodando outro, e
> saltaria de imagem no próximo `up -d` que alguém desse nela. Suba-a também, agora — **uma vez só**:
> ```bash
> docker compose -f docker-compose.ar.yml up -d web_ar
> ```
> **Esperado:** reinicia e continua atrás do Authelia, sem mudança visível.

**Se o piloto não abrir:** volte o `WEB_IMAGE` para o digest anterior e suba de novo. O valor está
na cópia que você fez no começo deste passo:

```bash
grep '^WEB_IMAGE=' .env.bak-$(date +%F)
```

Nada foi cortado ainda.

---

## Passo 3 — Dar ao piloto a credencial do banco

**Sem este passo, o corte apaga o piloto inteiro** — e o apagão começa já no Passo 4, quando
a chave liga: sem banco, `validar()` falha e toda rota `/api/*` responde 503. A sessão vive em tabela, então o motor
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

> **Se a senha tiver `@`, `:`, `/` ou `?`, ela precisa de percent-encoding** — sem isso a libpq
> corta a string no lugar errado e o erro sai como "host não encontrado", que manda você procurar
> rede quando o problema é a senha. Na dúvida, peça uma senha sem esses caracteres.

```bash
docker compose -f docker-compose.prod.yml up -d web
```

> **PARE E LEIA, porque este comando muda o comportamento do piloto NA HORA, antes de qualquer
> chave de autenticação.** Com a variável preenchida, o controle de abas troca de fonte: sai do
> `acesso_abas.json` e passa a ser o RBAC do banco, que é **deny-by-default**. Quem não tiver linha
> em `usuarios` com perfil **perde as abas** — o piloto abre vazio para essa pessoa.
>
> **Portanto: só preencha esta variável depois de o Passo 0.a estar fechado** (todo mundo do
> `authelia/users_database.yml` existe e está ativo em `usuarios`, com perfil — **não** do
> `acesso_abas.json`, que aceita curinga e por isso o próprio 0.a proíbe usar como lista). Se o 0.a
> não estiver fechado,
> **volte para ele** — este passo é o que torna aquela conciliação obrigatória, e não opcional.

**Confira, com o papel certo:**

```bash
docker compose -f docker-compose.prod.yml run --rm web \
  python -m motor_expansao.db privilegios
```

> **Este comando não passa `-e MOTOR_DATABASE_URL`, e é de propósito.** O
> `docker-compose.prod.yml` já injeta a variável no serviço `web` a partir do `.env`
> (`MOTOR_DATABASE_URL: ${MOTOR_DATABASE_URL:-}`), então o `run --rm` a recebe sozinho — é a mesma
> forma que o `docs/banco_deploy.md` usa no §8 para esta mesma conferência. Até 29/09/2026 este bloco
> trazia um `-e MOTOR_DATABASE_URL` **sem valor**, idioma copiado do §5 daquele runbook, onde ele vem
> **depois de um `export`** e por isso herda algo. Aqui não há `export` nenhum antes, então o `-e` era,
> na melhor hipótese, redundante — e, se ele chegasse a sobrescrever com vazio, o erro que aparece é
> exatamente o do próximo parágrafo, cuja explicação manda você conferir o `.env`, que estaria certo.

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

- quem estava usando o piloto **recebe 401 na próxima ação**, vê o pop-up **"Sessão encerrada"** e,
  ao clicar em "Entrar novamente", chega à nossa tela de entrar (`/entrar.html`). O pop-up é a
  etapa do meio, e é sempre assim — não é um estado de erro;
- entre este passo e o próximo, quem entrar passa por **DOIS logins**: o do Authelia, na borda,
  e o nosso, na aplicação. É esperado e é temporário;
- **ver esse pop-up e, depois dele, a nossa tela de entrar é o sinal de que funcionou**, não de que
  quebrou.

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

**Copie o bloco atual antes de tocar nele** — o `Caddyfile` é gitignored, então o que está lá
não existe em nenhum outro lugar, e é dele que você vai precisar se tiver de voltar atrás:

```bash
cd /opt/motor-expansao/app
cp Caddyfile Caddyfile.antes-do-p19
```

**Antes de colar, compare os dois lado a lado.** Este passo substitui o bloco **inteiro**, então
**toda diretiva que exista no bloco vivo e não exista no template desaparece** — compressão
(`encode`), headers, `tls` explícito, outro caminho de log, uma rota extra. O template nasceu depois
do bloco que está no ar e não pode saber o que foi acrescentado à mão lá:

```bash
grep -n -A40 'piloto.ultra-expansao.tech {' Caddyfile.antes-do-p19
```

Leia essa saída contra o template. **Qualquer linha que só exista no bloco vivo precisa ser levada
para o texto novo.** E o `caddy validate` do fim deste passo **não reclama do que faltar** — uma
configuração menor é uma configuração válida. O Passo 6 daria tudo verde e a perda só apareceria
dias depois.

Agora abra o `Caddyfile` e substitua o bloco de `piloto.ultra-expansao.tech` pelo bloco
`piloto.ultra-expansao.tech { … }` do template — **da linha `piloto.ultra-expansao.tech {` até a
chave que a fecha**. As primeiras linhas do template são comentário explicando decisões do projeto:
elas são explicação, não configuração, e não vão para o servidor.

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
   **Esperado:** o piloto **carrega** e, em cima dele, o pop-up bloqueante **"Sessão encerrada"**, com
   o botão **"Entrar novamente"**. Clique nele — **aí** vem a nossa tela de entrar (não a do Authelia).
   > **Por que a tela de entrar não vem de cara, e por que isso está CERTO.** Depois do corte o matcher
   > `@protegido` cobre só `/api/*`, então a raiz e os estáticos passam a ser servidos a quem **não**
   > entrou — está escrito como consequência declarada em
   > `deploy/caddy/piloto-br.Caddyfile.template`. O anônimo recebe o `index.html` e o bundle; a SPA
   > chama `/api/me`, que é o primeiro `/api/*` e volta **401**; e o 401 monta o pop-up
   > (`lib/api.ts` → `relatarAcessoNegado()` → `components/AvisoSessao.tsx`, que não fecha por Esc nem
   > por clique fora). **Só o clique** navega para `/entrar.html`.
   >
   > **O texto do pop-up vai soar errado nesta janela:** ele diz *"Seu acesso expirou e você foi
   > desconectado"*, e você nunca entrou. É o texto de sessão vencida, reaproveitado — **não é sintoma
   > e não se conserta aqui**.
   >
   > **O que seria defeito de verdade:** aparecer a tela do **Authelia** (aí o bloco do Caddy não
   > trocou), ou o piloto abrir **usável, sem pop-up nenhum** (aí a borda não está exigindo sessão).
2. **Entre com uma conta de teste.**
   **Esperado:** o piloto abre. Se a pessoa nunca trocou a senha, aparece o convite para trocar —
   com um botão "Agora não", porque a troca é **recomendada**, não obrigatória.
   > **Mas para quem recebeu uma senha TEMPORÁRIA de um admin, o "Agora não" é armadilha:**
   > essa senha vence em **2 horas**, e depois disso ela não entra mais — precisa de outra
   > redefinição. Quem receber temporária tem de trocar dentro do prazo. Diga isso ao
   > repassar a senha.
3. **Clique em Sair.**
   **Esperado:** volta para a tela de entrar. E voltar ao piloto **exige entrar de novo** — digitando o
   endereço outra vez você cai no **mesmo estado do item 1**: o piloto carrega e o pop-up "Sessão
   encerrada" aparece em cima, sem deixar usar nada. É esse pop-up que prova que a sessão foi revogada
   **no servidor**, e não só apagada no navegador.
4. **Confira que a AR não se mexeu:** abra `https://piloto-ar.ultra-expansao.tech`.
   **Esperado:** um redirecionamento para `auth.ultra-expansao.tech` — e ali a **NOSSA** tela de
   entrar, **não** a do Authelia.
   > **Isso não é o corte vazando para a AR, e é anterior a ele.** O bloco da AR
   > (`deploy/caddy/piloto-ar.Caddyfile.template`) manda o anônimo para
   > `uri /api/verify?rd=https://auth.ultra-expansao.tech` — a **raiz** daquele host —, e a raiz
   > daquele host serve a nossa tela **desde 22/09**, antes desta janela. É o mesmo fato que o item 5
   > registra, logo abaixo; até 29/09/2026 este item afirmava o contrário dele.
   >
   > **Quem autentica a AR continua sendo o Authelia:** o `forward_auth authelia:9091` do bloco dela
   > não é tocado neste corte — o Passo 5 diz, em caixa própria, para **não encostar** nesse bloco.
   >
   > **O que confere que a AR não se mexeu, sem adivinhar:** o bloco `piloto-ar.ultra-expansao.tech`
   > do `Caddyfile` está igual ao que estava (você não o editou no Passo 5), e **uma sessão da AR que
   > já estava aberta continua abrindo o piloto argentino**. **Não use esta janela para testar
   > *entrar* na AR:** esse caminho não foi medido, e um resultado ruim aqui não distingue defeito da
   > AR de pergunta que ninguém fez ainda. Se precisar mesmo entrar na AR, combine antes com quem
   > repassou.
5. **Confira os outros dois endereços do domínio**, que o Passo 5 não tocou e que ninguém
   mediu antes da janela:
   ```bash
   curl -sSI https://auth.ultra-expansao.tech/ | head -1
   curl -sSI https://ultra-expansao.tech/     | head -1
   ```
   O `auth.` continua existindo (a AR depende dele) e o apex deve redirecionar, nunca
   responder 200.

   > **O `auth.` serve a NOSSA tela de entrar, e isso é ESPERADO — não conserte.** Até 29/09/2026
   > este passo avisava que, se isso acontecesse, a pessoa ficaria num beco. Duas coisas mudaram, as
   > duas medidas: o Caddy serve aquela página na raiz do host de auth **desde 22/09** — e vale dizer
   > **como** se sabe disso, porque o `Caddyfile` real é **gitignored**: foi medido na VPS e chegou
   > aqui de segunda mão. **Ninguém confere isso a partir do repositório**, então se o que você vê
   > divergir, é a medição que está velha, não você que errou — pare e chame quem repassou. E desde os
   > PRs #425/#427 a tela **tem saída ali** — no 404 do nosso
   > `/api/login` ela cai no `POST /api/firstfactor`, que naquele host responde 401, porque é o
   > Authelia que atende. Mexer no bloco de `auth.` para "arrumar" isso **quebra a reserva** que
   > mantém o login funcionando para quem chega sem sessão.
   >
   > O que ainda vale conferir ali: que o `auth.` responde (a AR depende dele) e que o apex
   > **redireciona**. Se algum dos dois vier diferente, pare e chame quem repassou.

**Se o item 1 der outra coisa** — a tela do Authelia, ou o piloto abrindo usável sem pop-up, ou erro
que nenhum item previu —, **ou se o item 2 não conseguir entrar:** vá direto para *Se precisar voltar
atrás*, abaixo. O pop-up "Sessão encerrada" do item 1 **não** é esse caso: ele é o esperado.

---

## Se precisar voltar atrás

**A ordem é o INVERSO da de ligar. Invertê-la derruba o piloto inteiro.**

1. **Primeiro o Caddy:** devolva o bloco antigo copiando-o de **`Caddyfile.antes-do-p19`** — a cópia
   que você fez no começo do Passo 5. É o bloco com `forward_auth authelia:9091` cobrindo tudo,
   **sem** o matcher `@protegido`. Depois recarregue, com os mesmos dois comandos do Passo 5:

   ```bash
   cd /opt/motor-expansao/app
   docker compose -f docker-compose.prod.yml exec caddy caddy validate --config /etc/caddy/Caddyfile
   docker compose -f docker-compose.prod.yml exec caddy caddy reload --config /etc/caddy/Caddyfile
   ```

2. **Só então a chave:** `MOTOR_AUTENTICACAO_PROPRIA=` (vazia) e
   `docker compose -f docker-compose.prod.yml up -d web`.

> **A `MOTOR_DATABASE_URL` FICA preenchida — não a esvazie.** Ela não tem nada a ver com quem
> autentica; esvaziá-la devolveria o controle de abas ao `acesso_abas.json` e é uma segunda mudança
> no meio de uma emergência. **Consequência que você precisa esperar:** com ela preenchida o piloto
> segue no RBAC do banco, então quem ainda não tem perfil continua **abrindo o piloto vazio** mesmo
> com o Authelia de volta. Isso **não** é rollback malfeito — é o Passo 3 ainda em vigor, e se
> resolve dando perfil à pessoa pelo painel de Acessos.

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
  "SELECT login_usuario, senha_definida_em_usuario FROM usuarios WHERE senha_definida_em_usuario > '2026-10-01 21:00' ORDER BY 2;"
```

> **Troque `2026-10-01 21:00` pelo horário em que você rodou o Passo 4** (o da chave), **com hora**.
> Se o corte e o rollback caírem no mesmo dia, uma data sem hora devolve a lista errada — e o erro é
> mudo, porque a consulta roda igual.

---

## Depois do corte — o que muda na operação

| Coisa | Antes | Depois |
|---|---|---|
| **Tirar acesso de alguém** | remover do `users_database.yml` + restart do Authelia | **desativar a linha em `usuarios`** pelo painel de Acessos — a sessão morre na requisição seguinte |
| **Postgres fora do ar** | o piloto continua servindo (só o banco fica indisponível) | **o piloto inteiro fica fora** — sem banco não há sessão, e o Caddy nega tudo |
| **Sessão expirada** | o Authelia redireciona | a SPA abre o pop-up "Sessão encerrada" e, no clique, leva à nossa tela de entrar |

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
- **Se o piloto ficar fora e o rollback não resolver:** o bloco antigo do Caddy está em
  **`/opt/motor-expansao/app/Caddyfile.antes-do-p19`** (a cópia do Passo 5) e, se ela tiver se
  perdido, no backup cifrado (`sops -d secrets/Caddyfile.enc`). **Não procure no histórico do git:**
  o `Caddyfile` é gitignored e nunca esteve versionado.
