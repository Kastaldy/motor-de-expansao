# Repasse — o CORTE do P19: o motor passa a autenticar

> **Para quem vai executar.** Este documento é auto-contido: você não precisa conhecer a epic para
> segui-lo. Cada passo diz **o que rodar**, **o que esperar** e **o que fazer se vier diferente**.
> Onde houver `<algo>`, substitua.
>
> **Regra que vale acima de tudo:** se qualquer passo devolver algo que este documento não previu,
> **pare e chame quem repassou**. Nenhum passo aqui é urgente a ponto de justificar adivinhar.
>
> **Pré-requisito obrigatório:** o banco foi criado pelo `docs/banco_deploy.md` §1 a §7 (feito na produção em 17/10/2026, já com as 21 migrations) ou, se já existia, atualizado pelo `docs/repasse_migracoes_p19.md`
> (migrations 018, 019 e 020 aplicadas). Este documento começa onde aquele termina. **Na produção,
> cumprido:** o banco nasceu do zero com as 21 (`000` a `020`), e o `repasse_migracoes_p19.md` não se
> aplica a ela.

**Estado em 24/10/2026:** o corte **não foi feito**. Já estão prontos o banco (17/10/2026: 21
migrations, D20 com `conferir` e `privilegios` OK, 20 usuários, 4 perfis) e a **ligação dele no site**
(23/10/2026: a `MOTOR_DATABASE_URL` entrou no `.env` e o `web` foi recriado na mesma imagem; desde
então o RBAC do BR vem do banco, e o `acesso_abas.json` deixou de valer para o BR). A chave
`MOTOR_AUTENTICACAO_PROPRIA` segue **desligada**: quem autentica é 100% o Authelia. Duas decisões de
Vinicius, de 24/10/2026, entram neste roteiro: a senha do dia do corte é a **compartilhada** do
Authelia (Passo 0.b), e o cadeado "Trocar a minha senha", "Redefinir senha" e "Exigir troca" só
aparecem, e só funcionam, com a chave ligada (Passos 4 e 6).

**Duração estimada:** 45 a 60 min. **Os Passos 4 e 5 são uma sequência contínua** — a partir da
chave ligada, quem usa o piloto já é levado à nossa tela de entrar, então não interrompa entre
eles. O Passo 0 e a conferência do Passo 3 (a credencial do banco está no ar desde 23/10/2026) podem
ser feitos antes, com calma.
**Janela recomendada:** fora do horário de uso, com alguém disponível por telefone, e longe das
06:30 UTC: o cron diário da Growth reinicia o `web` nessa hora (`docker restart`, que mantém o
ambiente, mas tira o `web` do ar por alguns instantes no meio das conferências).

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
| Acesso SSH à VPS | já configurado: a conta `deploy` (`ssh -i ~/.ssh/id_ultra_deploy deploy@<vps>`, grupos `docker` e `motor-ops`, sem `sudo`; o endereço está em `docs/infra_producao.md`). O que exige root fica com o Felipe: o healthcheck e, se a conta não puder escrever no `Caddyfile`, o Passo 5 e o rollback |
| `WEB_IMAGE` (digest da imagem nova) | job `publish-web` no Actions, depois do merge do código de 24/10/2026 — o que esconde o cadeado e os gestos de senha enquanto a chave estiver desligada (Passos 0.c e 2) |
| Senha do dono do banco (`reservas_owner`) | no `.env` do compose, em `POSTGRES_OWNER_PASSWORD` — o 0.c a lê de lá sem imprimi-la, e você não precisa copiá-la |
| Senha do papel `app` | **não precisa mais:** a `MOTOR_DATABASE_URL` está preenchida desde 23/10/2026 (o Passo 3 virou conferência), e a senha do `app` fica no `.env` em `MOTOR_APP_DB_PASSWORD` — o compose não lê essa variável; a senha vai dentro da URL. Até 24/10/2026 esta linha mandava pedir a senha a quem repassou e citava o `.env` só como exceção: desde a instalação de 17/10/2026 ela está lá (#462) |
| **Seu login na allowlist do painel de Acessos** | a env `MOTOR_ACESSOS_ADMIN_USUARIOS` do `.env`. Sem o seu login lá, o painel responde **404** para você — e é a única ferramenta de criar gente e destravar conta |
| **Uma conta sua no Authelia**, com senha | **com quem repassou.** Estar na allowlist acima não basta: **hoje** o Caddy exige sessão do Authelia no host inteiro, então sem conta no `users_database.yml` o navegador nunca chega no painel de Acessos. Peça que o seu login seja a **mesma string** nos dois lugares |
| **O PERFIL de cada pessoa que você for criar** | **com quem repassou.** O Passo 0.a manda criar pela tela quem falta, e o próprio passo diz *"não tente adivinhar o perfil de ninguém"* — então sem essa lista o 0.a **não fecha**. `login`, nome e e-mail você tira do `users_database.yml` (`displayname` e `email` estão lá, ao lado do login); o perfil é o único dos quatro que não existe na VPS, porque ele nasce com este trabalho |
| **A senha compartilhada que a equipe digita hoje** | **com quem repassou** — ela **não existe em lugar nenhum do servidor**: o `users_database.yml` guarda só o hash, que não se desfaz. Sem ela o Passo 0.b não fecha: é ela que vai para a `MOTOR_SENHA_INICIAL` (decisão de 24/10/2026) |
| **`sops` e a chave age que decifra `secrets/`** | **na estação do Vinicius** — não ficam na VPS, então os backups cifrados do fim do Passo 5 se refazem de lá, não do servidor. Teste **antes da janela**, na estação: `sops -d secrets/Caddyfile.enc \| head -1` tem de imprimir a primeira linha do Caddyfile. Se recusar, pare e peça — sem isso o último passo do corte não fecha, e o backup cifrado fica descrevendo um Caddyfile que não existe mais |
| Este documento e o `deploy/caddy/piloto-br.Caddyfile.template` | o repositório — o template vai à VPS por `scp` no Passo 5, porque o checkout de lá é antigo e não o tem |

### Antes de marcar a janela — o que tem de estar de pé

Depois do corte o banco vira **ponto único** do login do BR: Postgres fora = ninguém entra, e o
interruptor do banco (esvaziar a `MOTOR_DATABASE_URL`, §8 do `docs/banco_deploy.md`) deixa de existir.
Por isso, antes de marcar a data:

- **O healthcheck da `main` instalado na VPS, com o subcomando `banco`.** Em 24/10/2026, o que roda
  em `/opt/motor-monitoring/healthcheck_vps.sh` (crontab do root) é uma cópia antiga, que não vigia
  nem o container do Postgres. A da `main` vigia os 8 containers (o do Postgres entre eles), tem o
  check `auth` (`/api/me` com um cookie de sessão falso: 401 = OK, 200 = API aberta, 503 = banco
  fora, que depois do corte é ninguém entrar; a sonda com cookie é de 24/10/2026, e a anterior, sem
  cookie, não enxergava o banco) e o `banco` (backup, expurgo e saúde interna, diário; a linha
  do crontab, com os três caminhos da conta `deploy`, está no comentário do próprio script).
  Instalar é passo do Felipe (root), comando a comando, e a troca traz junto os outros monitores da
  `main`, que podem começar em FAIL.
- **Um restore testado** a partir de um dump real (`docs/banco_deploy.md` §10): depois do corte o
  banco é a fonte das credenciais.
- **A cópia fora da máquina (restic) — recomendada.** Em 24/10/2026, banco e dumps ficam no mesmo
  disco; destino e custo são decisão do Felipe.
- **A entrada "banco fora" no Runbook de incidente** (`docs/infra_producao.md`): sintomas,
  diagnóstico por SSH e quando voltar atrás.
- **`deve_trocar` remarcado nos 20**, o que o `alinhar-senhas` faz (Passo 0.c).

### Os dois merges que precedem tudo — e eles JÁ ESTÃO na `main`

O trabalho vinha em duas branches, e as duas **já foram incorporadas**. Elas foram **apagadas** na
incorporação, como é o padrão deste repositório — então **não procure pelos nomes**, que não existem
mais. Procure pelos merges, que são permanentes.

| O que leva | Pedido | Merge na `main` |
|---|---|---|
| o motor, a rota `/api/verify`, a tela de entrar | **#417** | `f38703b` |
| a chave `MOTOR_AUTENTICACAO_PROPRIA` no `docker-compose.prod.yml` | **#416** | `f5b5e9b` |

**Confira você mesmo** — até 29/09/2026 esta seção mandava procurar as branches pelo nome, o que é
impossível depois de apagadas. **E confira pela sua máquina, não pela VPS** (até 24/10/2026 o bloco
abaixo rodava lá): o `/opt/motor-expansao/app` da VPS é um checkout do root parado num commit antigo
(`302487e`, de 19/08/2026), com o `docker-compose.prod.yml` trocado à mão pelo da `main` em
17/10/2026. Não dá para dar `git pull` nele, o histórico dele não diz o que está no ar, e o `scripts/`
e o `deploy/` dele não têm os arquivos deste corte. Os dois merges já estão na imagem que está no ar
(`main` em `84429f3e`).

**Na sua máquina, num checkout do repositório:**
```bash
git fetch origin
git merge-base --is-ancestor f38703b origin/main && echo "o motor esta na main"
git merge-base --is-ancestor f5b5e9b origin/main && echo "a chave esta na main"
```

**No terminal da VPS** — o compose que vale é o que está lá:
```bash
grep -n MOTOR_AUTENTICACAO_PROPRIA /opt/motor-expansao/app/docker-compose.prod.yml
```

O último é o que de fato importa: a variável tem de aparecer dentro do bloco `environment:` do
serviço `web`. Se qualquer um dos três não fechar, **pare**.

> **Sem a segunda, o corte é impossível de ligar.** O compose não tem `env_file`, então o container
> só recebe o que o bloco `environment:` lista. Pôr a chave no `.env` sem essa branch não faz
> efeito nenhum — e a falha é **muda**: nada quebra, o piloto sobe igual, e parece que a epic não
> funciona.

---

## Passo 0 — Garantir que ninguém fica trancado (faça DIAS antes, não na janela)

Este é o único passo que não dá para desfazer depois: se alguém não consegue entrar, você vai
descobrir com a pessoa do outro lado da linha.

**São três conferências, nesta ordem.** A primeira é a que tranca a equipe inteira se for pulada;
as outras duas trancavam pessoas individuais — **na produção, pular o 0.b e o 0.c também tranca
todo mundo**: em 24/10/2026, os 20 hashes são da senha sorteada em 17/10/2026, que ninguém conhece.

### 0.a — Todo mundo que usa o piloto EXISTE na tabela `usuarios`?

**Este é o passo que, pulado, tranca a equipe inteira** — e ele não tem nada a ver com senha.

Hoje quem autentica é o Authelia. Quem libera as abas do BR é o banco, desde 23/10/2026 (até ali
era o `acesso_abas.json`) — mas **a tabela `usuarios` ainda não decide quem ENTRA**. Ou seja: alguém
pode entrar pelo Authelia sem ter linha ativa no banco (e ver o piloto vazio). Depois do corte, sem
linha ativa em `usuarios` **não há como entrar**.

> **COMPARE CONTRA O AUTHELIA, NÃO CONTRA O `acesso_abas.json`.** O JSON aceita uma entrada
> curinga `"*"`, que dá abas a **qualquer pessoa autenticada** — então ele pode listar três logins
> enquanto vinte pessoas usam o piloto, e uma conferência contra ele passaria **verde** deixando
> dezessete trancadas. A lista de quem consegue entrar hoje é o **`users_database.yml` do
> Authelia**. Se houver `"*"` no JSON, ele não serve como lista de ninguém. E desde 23/10/2026 ele
> nem governa mais as abas do BR.

Liste os dois lados e compare:

**No terminal da VPS:**
```bash
cd /opt/motor-expansao/app

# 1) quem consegue AUTENTICAR hoje — esta é a lista que importa
# As DUAS listas, e compare quantas linhas cada uma devolve: a segunda pega login com espaço
# ou `@`, que a primeira NÃO vê (classe de caracteres). Se os números diferirem, a diferença são
# as pessoas que a primeira deixaria de fora -- medido em 05/10/2026, num arquivo de quatro
# pessoas a primeira devolveu 2. Use a SEGUNDA para listar.
docker exec motor_expansao_authelia grep -nE '^  [a-zA-Z0-9_.-]+:' /config/users_database.yml   # no host o arquivo é root:600 (banco_deploy.md §7)
docker exec motor_expansao_authelia grep -nE '^  [^ #].*:'         /config/users_database.yml

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

**O conferidor faz as duas direções de uma vez**, pessoa a pessoa, e só lê (nunca imprime senha,
hash nem e-mail). O checkout da VPS não tem o script, então ele sai da imagem no ar. Precisa de
`bash` (as `<(...)` não existem em `sh`), e o `-I` impede o `python3` de carregar módulo plantado
no `/tmp`, de onde o script roda:

**No terminal da VPS:**
```bash
cd /opt/motor-expansao/app
docker exec motor_expansao_web cat /app/scripts/conferir_usuarios_banco.py > /tmp/conferir_usuarios_banco.py
docker exec -i motor_expansao_postgres psql -v ON_ERROR_STOP=1 -At -F '|' \
    -U reservas_owner -d banco_de_reservas \
    -c "$(python3 -I /tmp/conferir_usuarios_banco.py --sql)" \
  | python3 -I /tmp/conferir_usuarios_banco.py \
    <(docker exec motor_expansao_authelia grep -E '^users: *(#.*)?$|^  [^ #][^:]*: *(#.*)?$|^    disabled: *([Tt][Rr][Uu][Ee]|[Yy][Ee][Ss]|[Oo][Nn]) *(#.*)?$' /config/users_database.yml) \
    <(docker exec motor_expansao_web cat /app/cadastro/acesso_abas.json)
```

Leia as linhas `FALTA NO BANCO` (entra hoje e ficaria trancado), `falta no Authelia` (está no banco
e não entra hoje — mas entra depois do corte) e, a mais traiçoeira, **`desativado no Authelia, mas
ATIVO no banco`**: quem foi tirado só do Authelia **volta a entrar** quando o banco passar a
autenticar — desative essa pessoa no painel antes do corte. As linhas `abas mudam` comparam com o
`acesso_abas.json`, que não vale mais para o BR, então não são pendência deste corte (e podem fazer o
código de saída vir `1` sozinhas). A lista muda a cada cadastro: rode de novo **no dia**, logo antes
do Passo 4.

**Se faltar alguém** — os 20 de 17/10/2026 foram conciliados na instalação, mas a lista muda a
cada cadastro —, essas pessoas precisam ser **criadas pela tela de
Acessos** antes do corte. Criar pela tela é o caminho certo porque ele grava o hash da senha
inicial, o perfil e a trilha de quem criou; `INSERT` à mão no banco produz exatamente o hash
inválido que o passo 0.c existe para pegar.

> **Não tente adivinhar o perfil de ninguém.** Quem decide qual perfil cada pessoa recebe é quem
> repassou — os perfis (`expansao`, `consultoria`, `lideres`, `growth`) definem o que ela vê.

> ### A ORDEM AQUI É CONTRAINTUITIVA, e sem ela você fica num impasse
>
> **Na produção este impasse já foi atravessado:** o banco está ligado desde 23/10/2026 (o Passo 3
> foi feito), então criar pela tela funciona agora. O resto deste quadro vale para um ambiente
> montado do zero.
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
> este passo é a versão mínima dele — e essa versão mínima foi feita com o conferidor na instalação do
> banco e antes de ligá-lo (17 e 23/10/2026). O que segue pendente no bloco é a política de saída nos dois cadastros e a
> periodicidade da revisão.

### 0.b — A senha do dia do corte é a compartilhada: trocar a `MOTOR_SENHA_INICIAL`

Hoje quase todo mundo usa **uma senha compartilhada** no Authelia. O motor também tem a sua, na
variável `MOTOR_SENHA_INICIAL`, e é o hash dela que o banco guarda de cada pessoa. **Na produção as
duas são diferentes:** a `MOTOR_SENHA_INICIAL` foi sorteada na instalação (17/10/2026), ninguém a
conhece, e os 20 hashes do banco são dela.

**Decidido por Vinicius em 24/10/2026: a senha do dia do corte é a COMPARTILHADA do Authelia.** A
`MOTOR_SENHA_INICIAL` é trocada por ela, e o 0.c regrava os hashes. Quem usa senha pessoal no Authelia
(como o Felipe) também entra no dia com a compartilhada — a senha pessoal não existe no banco — e define a
dele no convite do primeiro acesso; por isso não é preciso medir quem tem senha pessoal lá. A escolha
contraria de propósito o `.env.example` ("nunca a mesma de nenhum outro sistema"): é a única saída que
não depende de repassar senha a 20 pessoas durante a janela.

**Troque sem imprimir a senha.** O bloco lê a senha do teclado sem eco e grava a linha entre aspas
simples: sem aspas, o `.env` do compose interpreta `$` e ` #` (medido em 24/10/2026: `ab$cd #ef`
vira `ab`). Aspa simples dentro da senha não cabe nessa forma, e o bloco para sem escrever.

**No terminal da VPS:**
```bash
cd /opt/motor-expansao/app
cp -n .env .env.bak-$(date +%F)-antes-senha-p19   # o caminho de volta; -n não sobrescreve a do dia
grep -c '^MOTOR_SENHA_INICIAL=' .env  # tem de ser 1
IFS= read -rs S && echo "(lida)"     # digite a senha compartilhada; nada aparece na tela
S="$S" python3 -I - <<'PY'
import os, sys
s = os.environ["S"]
if not s or "'" in s:
    sys.exit("PAROU: senha vazia ou com aspa simples -- nada foi escrito")
linhas = open(".env", encoding="utf-8").read().split("\n")
i = [n for n, l in enumerate(linhas) if l.startswith("MOTOR_SENHA_INICIAL=")]
if len(i) != 1:
    sys.exit("PAROU: esperava 1 linha MOTOR_SENHA_INICIAL, achei %d -- nada foi escrito" % len(i))
linhas[i[0]] = "MOTOR_SENHA_INICIAL='" + s + "'"
open(".env", "w", encoding="utf-8", newline="").write("\n".join(linhas))
print("MOTOR_SENHA_INICIAL trocada; as outras linhas ficaram como estavam")
PY
unset S
```

**Agora suba o `web` — antes do 0.c:**
```bash
unset MOTOR_DATABASE_URL MOTOR_SENHA_INICIAL MOTOR_AUTENTICACAO_PROPRIA   # no terminal, mesmo vazia, uma delas venceria o .env
docker compose -f docker-compose.prod.yml up -d --no-deps web
```

> **A ordem não é opcional.** O 0.c roda **dentro do `web` no ar** (`docker exec`) e alinha os hashes
> com a `MOTOR_SENHA_INICIAL` do processo dele — a mesma com que a tela de Acessos cria gente. Sem este
> `up`, o container segue com a senha sorteada: o `--simular` do 0.c sai com `c` = 0 e `b` = `N` (os
> hashes ainda conferem com ela), o que se lê fácil como "nada a fazer", e quem fosse criado pela tela
> continuaria recebendo a senha velha. E `restart` não serve: ele não relê o `.env` — nem o diário das
> 06:30 UTC. (Até 25/10/2026 o 0.c rodava num `run --rm`, que relia o `.env` sozinho, e o risco era o
> inverso: hashes da senha nova com o container no ar criando gente com a velha.)
>
> **O `--no-deps` recria só o `web`.** O `web` declara `depends_on: postgres`, e sem ele o `up`
> converge o `postgres` junto: se a config do banco tiver mudado — uma `POSTGRES_OWNER_PASSWORD`
> trocada no `.env` basta —, o compose recria o `postgres` no meio do passo (medido em 25/10/2026, no
> Compose 2.33 e no 5.6). É a forma do kit (`p19c-senha.sh`) e vale para todo `up` deste documento; até
> 25/10/2026 os comandos daqui não a tinham.

**Confira, sem imprimir, que o `web` recebeu exatamente a senha que você digitou:**
```bash
IFS= read -rs S; printf '%s' "$S" | docker compose -f docker-compose.prod.yml exec -T web \
  python -c 'import hmac, os, sys; d = sys.stdin.read(); e = os.environ.get("MOTOR_SENHA_INICIAL", "").strip(); print("IGUAIS" if d and hmac.compare_digest(d.encode(), e.encode()) else "DIFERENTES")'; unset S
```

**Esperado:** `IGUAIS`. **Se vier `DIFERENTES`,** devolva o `.env` (no mesmo dia,
`cat .env.bak-$(date +%F)-antes-senha-p19 > .env`), suba o `web` de novo (o `unset` e o
`up -d --no-deps web` acima) e **pare**: o 0.c gravaria um hash que não abre com a senha que a equipe
digita.

### 0.c — Alinhar os hashes e ver quem sobra

> **Antes de rodar fora da janela, confira a imagem no ar.** O alinhar **remarca a troca de senha**
> de cada pessoa que ele regrava (ver o fim deste passo), e só a imagem com o código de 24/10/2026
> esconde o convite e o cadeado enquanto a chave estiver desligada. Com ela, o 0.c roda dias antes da
> janela sem nada visível para a equipe; com a imagem anterior, o convite abriria para os 20 antes do
> corte, oferecendo trocar uma senha do banco que ainda não abre porta nenhuma.
>
> **No terminal da VPS:**
> ```bash
> docker exec motor_expansao_web grep -c LOGIN_PROPRIO_DESLIGADO_TROCA /app/web/server/app.py
> ```
> Maior que `0`: é a imagem certa. `0` (ou erro): faça o Passo 2 antes — ele só esconde o que hoje não
> funciona — ou deixe o 0.c para a janela, logo antes do Passo 4.

**O alinhar escreve com a credencial do DONO do schema (`reservas_owner`) — e o jeito de entregá-la
não é formalidade.** O `alinhar-senhas` procura primeiro a `MOTOR_DATABASE_URL_ADMIN` e, sem ela, cai
**em silêncio** para a `MOTOR_DATABASE_URL`, que é a credencial do papel **`app`** — a que o `web` no
ar tem no ambiente desde 23/10/2026, com `UPDATE` em `usuarios` por desenho. O passo que este
documento chama de "o único que não dá para desfazer" reescreveria hashes pela credencial da
aplicação, sem uma linha de aviso, e a saída do comando **não nomeia o papel conectado**.

Por isso ele não é chamado direto. Dois programas pequenos, **os mesmos do kit** (`p19c-senha.sh`),
fazem a entrega:

- o `url_dono.py` monta a URL do dono a partir do `.env` (`POSTGRES_DB`, `POSTGRES_OWNER_USER` e
  `POSTGRES_OWNER_PASSWORD`) e a escreve **só no pipe** da função `alinhar`, nunca na tela. Por isso
  ele **nunca se roda sozinho**: fora do pipe, a saída dele é a tela, e a URL sairia nela com a senha
  do dono (medido em 25/10/2026);
- o `alinhar.py` roda **dentro do `web` no ar** (`docker exec -i`), com a `MOTOR_SENHA_INICIAL` que o
  0.b pôs lá. Ele lê a URL da **entrada padrão** e recusa se ela não chegou, em vez de deixar o comando
  cair na do `app`; conecta, **imprime o papel** e recusa se ele não for `reservas_owner`; e só então
  chama o `alinhar-senhas`.

A senha do dono não vai para argumento de comando (que o `ps` mostra), variável exportada, ambiente do
`docker exec`, arquivo nem tela. **Até 25/10/2026 este passo mandava
`export MOTOR_DATABASE_URL_ADMIN=...` e `docker compose run --rm -e MOTOR_DATABASE_URL_ADMIN ...`**, e
a revisão de segurança mediu no laboratório (`strace` e `docker inspect`) que assim a URL do dono
ficava no ambiente do processo `docker compose` e na `Config.Env` do container descartável: um
`docker inspect` dele a imprimiria — o modo exato do vazamento de 17/10/2026.

**Prepare os dois programas uma vez por terminal** (se a sessão cair, refaça este bloco). A pasta
temporária guarda só código, nunca a senha:

**No terminal da VPS:**
```bash
cd /opt/motor-expansao/app
P19=$(mktemp -d)
cat > "$P19/url_dono.py" <<'PY'
# Monta a URL do DONO do schema a partir do .env e a escreve SO' na saida padrao (que vai direto para um pipe).
# Valida o formato antes; se reprovar, nao escreve nada e sai com 3.
import re
import sys

v = {}
for linha in open(".env", encoding="utf-8").read().split("\n"):
    if "=" in linha and not linha.lstrip().startswith("#"):
        k, x = linha.split("=", 1)
        v.setdefault(k, []).append(x)
db, papel, pw = v.get("POSTGRES_DB", []), v.get("POSTGRES_OWNER_USER", []), v.get("POSTGRES_OWNER_PASSWORD", [])
if (len(pw) != 1 or not re.fullmatch(r"[0-9a-f]{48}", pw[0]) or db != ["banco_de_reservas"]
        or len(papel) != 1 or not re.fullmatch(r"[a-z_][a-z0-9_]*", papel[0])):
    sys.exit(3)
sys.stdout.write("postgresql://%s:%s@postgres:5432/%s\n" % (papel[0], pw[0], db[0]))
PY
cat > "$P19/alinhar.py" <<'PY'
# Roda DENTRO do container do web no ar: `db alinhar-senhas` com a credencial do DONO, que chega pela ENTRADA
# PADRAO (1a linha) e so' existe dentro deste processo -- nao vai para argumento, para o ambiente do `docker
# exec` nem para arquivo. Usa a MOTOR_SENHA_INICIAL do proprio container: a mesma com que o site cria gente.
# Antes de alinhar, prova que a credencial e' mesmo a do dono (sem a do dono, o runner cairia para a
# MOTOR_DATABASE_URL do `app` em silencio). Uso: alinhar.py <papel do dono> [--simular]
import os
import sys

dono, args = sys.argv[1], sys.argv[2:]
url = sys.stdin.readline().strip()
if not url.startswith("postgresql://"):
    print("ALINHAR_ERRO=sem-credencial-do-dono")
    sys.exit(97)
os.environ["MOTOR_DATABASE_URL_ADMIN"] = url
del url
try:
    import psycopg

    with psycopg.connect(os.environ["MOTOR_DATABASE_URL_ADMIN"], connect_timeout=10) as con:
        papel = con.execute("select current_user").fetchone()[0]
except Exception as erro:  # o tipo basta: a mensagem poderia citar a conexao
    print("ALINHAR_ERRO=conexao:" + type(erro).__name__)
    sys.exit(96)
print("PAPEL_ALINHAR=" + str(papel))
if papel != dono:
    print("ALINHAR_ERRO=papel-errado")
    sys.exit(96)
from motor_expansao.db import cli

try:
    rc = cli.main(["alinhar-senhas"] + args)
except SystemExit as saida:
    print("ALINHAR_ERRO=saida:" + type(saida.code).__name__)
    rc = 95
print("RC_ALINHAR=%d" % rc)
sys.exit(rc)
PY
alinhar() { python3 -I "$P19/url_dono.py" | docker exec -i motor_expansao_web python -c "$(cat "$P19/alinhar.py")" reservas_owner "$@"; }
```

> **Na produção a senha do dono está no `.env`** (`POSTGRES_OWNER_PASSWORD`, gerada em hexadecimal na
> instalação). O `url_dono.py` só aceita a forma da instalação — uma linha de cada, a senha com 48
> caracteres hexadecimais e o banco `banco_de_reservas` —, e por isso a URL nunca precisa de
> percent-encoding; fora dessa forma ele não escreve nada, e o `alinhar.py` recusa. Até 25/10/2026
> este passo ensinava a codificar `@ : / ?` na senha, para a URL digitada à mão.

**Rode primeiro o `--simular`, que não escreve nada — sempre:**

**No terminal da VPS:**
```bash
alinhar --simular
```

**Esperado:** o papel, as contagens e o código de saída:

```
PAPEL_ALINHAR=reservas_owner
usuarios ativos: <N>
  ja' escolheram a propria senha, hash ok : <a>
  na senha inicial e JA' CONFEREM         : <b>
  na senha inicial e NAO conferem         : <c>
  escolheram, mas o hash esta' QUEBRADO   : <d>

(--simular: nada foi escrito) seriam alinhadas:
    <um login por linha: as c pessoas>
RC_ALINHAR=0
```

> **A primeira linha é a conferência do papel, e ela vem antes de qualquer escrita:** tem de ser
> `PAPEL_ALINHAR=reservas_owner`. O `alinhar.py` faz a mesma conferência por conta própria e não chama
> o `alinhar-senhas` com outro papel — mas leia a linha: é ela que diz com qual credencial este passo
> vai escrever. (Até 25/10/2026 a conferência era um `echo` da variável exportada passado por `cut`.)
>
> **Se vier outra coisa, nada foi escrito.** O que cada saída quer dizer:
>
> | Se vier | Quer dizer | O que fazer |
> |---|---|---|
> | `PAPEL_ALINHAR=<outro>` e `ALINHAR_ERRO=papel-errado` | a credencial montada do `.env` conectou, mas com outro papel: a linha `POSTGRES_OWNER_USER` não é `reservas_owner` | pare e chame quem repassou; a conferência das linhas do dono, logo abaixo, mostra qual delas |
> | `ALINHAR_ERRO=sem-credencial-do-dono` | o `url_dono.py` não montou a URL: o terminal não está em `/opt/motor-expansao/app` (aí vem antes um `FileNotFoundError` do `.env`), ou uma das três linhas `POSTGRES_*` falta, se repete ou saiu da forma da instalação | `cd /opt/motor-expansao/app` e repita; persistindo, a conferência das linhas do dono, logo abaixo |
> | `ALINHAR_ERRO=conexao:OperationalError` | o banco não respondeu: o `postgres` está fora do ar, ou recusou a senha | `docker compose -f docker-compose.prod.yml ps postgres`: sem ele na lista, é o incidente "banco fora" do `docs/infra_producao.md`; com ele `(healthy)`, a senha do `.env` não é a do banco — pare e chame quem repassou |
> | `Error response from daemon: container ... is not running` (ou `No such container`), seguido de um `BrokenPipeError` do `url_dono.py`, que ficou sem ter para quem entregar a URL | o `web` está fora do ar, e o alinhar roda dentro dele | suba-o como no 0.b (o `unset` e o `up -d --no-deps web`) e repita |
>
> **A conferência das linhas do dono** — as três que o `url_dono.py` lê, cada uma uma vez só e na forma da
> instalação. Imprime só contagens, nunca a linha:
>
> **No terminal da VPS:**
> ```bash
> cd /opt/motor-expansao/app
> for r in '^POSTGRES_DB=' '^POSTGRES_DB=banco_de_reservas$' '^POSTGRES_OWNER_USER=' '^POSTGRES_OWNER_USER=reservas_owner$' '^POSTGRES_OWNER_PASSWORD=' '^POSTGRES_OWNER_PASSWORD=[0-9a-f]{48}$'; do printf '%s ' "$(grep -cE "$r" .env)"; done; echo
> ```
> Tem de imprimir `1 1 1 1 1 1`, na ordem: banco, banco com o nome certo, dono, dono `reservas_owner`, senha,
> senha com 48 caracteres hexadecimais. Um `0` aponta a linha que falta ou saiu da forma; um `2` (ou mais), a
> linha repetida — por exemplo, a `POSTGRES_DB=motor_expansao` legada do `.env.example` (`docs/banco_deploy.md` §3).

> **Olhe o `N` primeiro, porque é ele que denuncia o pior cenário.** `usuarios ativos` tem de ser
> **igual ao número de logins que você conciliou no 0.a** (20 em 24/10/2026), e `d` tem de ser 0.
> Se o `N` vier `0`, ou bem abaixo daquilo, o 0.a não está fechado: as quatro contagens vêm zeradas, o comando imprime `nada a alinhar` — e isso
> significa **"não há ninguém no banco"**, não "está tudo certo". Seguir daqui leva a um corte em que
> a rede inteira fica trancada. Volte ao 0.a.

- **`c` maior que zero:** são pessoas que estão na senha compartilhada mas cujo hash guardado não
  corresponde a ela — elas **não entrariam**. **Depois da troca do 0.b, `c` deve sair igual a `N` −
  `a`:** os hashes guardados são da senha sorteada, então ninguém na senha inicial confere com a nova
  (se sair `0`, com `b` = `N`, o `web` no ar ainda tem a senha sorteada: volte ao `up` e à conferência
  do 0.b). Rode o comando **sem** `--simular` para consertar:

  ```bash
  alinhar
  ```

  Ele confere o papel de novo, nomeia cada pessoa que alinhou (`alinhada: <login>`) e termina com
  `ALINHADAS: <c>` e `RC_ALINHAR=0`. Rode `alinhar --simular` de novo e confira que `c` virou **0**
  (`nada a alinhar`).

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
>
> **Na produção é exatamente este o caso, e é o esperado:** ninguém definiu senha no banco, então os
> 20 são regravados — inclusive quem conduz o corte e quem usa senha pessoal no Authelia (0.b).

> **Atenção ao mal-entendido comum:** quem está na senha compartilhada **entra normalmente** —
> essa pessoa tem um hash Argon2id de verdade. O risco não é "estar na senha inicial"; é o hash
> guardado não corresponder à senha que a pessoa digita.

**O alinhar remarca a troca.** `SQL_ALINHAR_SENHA_INICIAL` grava `deve_trocar_senha_usuario = TRUE`
em cada pessoa que ele regrava (o `c` da primeira simulação), e isso desfaz, para elas, o desmarcar
de 17/10/2026. Depois do corte, o convite de troca abre para elas no primeiro acesso — com "Agora
não", porque a troca é recomendada, não obrigatória (decisão de 25/09/2026) —, e é ele que tira cada
pessoa da senha compartilhada. Quem já conferia (`b`) não é tocado e fica com a marca que tinha. Com
a chave desligada nada disso aparece: é a razão da conferência da imagem no começo deste passo.

**Ao terminar o 0.c, limpe o terminal:**

**No terminal da VPS:**
```bash
rm -rf "$P19"; unset -f alinhar; unset P19
```

Não há senha para apagar — ela só existiu no pipe e no processo do container, que termina com cada
comando —, mas a pasta e a função não têm por que ficar. (Até 25/10/2026 o passo terminava com
`unset MOTOR_DATABASE_URL_ADMIN`.)

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
  404 aqui é quase sempre "seu login não está na env", e não "a rota não existe";
- **desde 23/10/2026, com o banco no comando, as rotas do painel exigem também a capacidade no
  banco** (`acesso.painel_ver` para ver, `acesso.usuario_gerir` para mudar — as do perfil `growth`):
  na allowlist sem esse perfil, a aba aparece e as rotas respondem **403**;
- **"Redefinir senha" e "Exigir troca" só aparecem com a chave ligada** (Passo 4) e, na sua
  própria linha, ficam desabilitados — a sua senha se troca pelo cadeado. Antes da chave, as rotas deles respondem 404.

Confira antes da janela:

**No terminal da VPS:**
```bash
cd /opt/motor-expansao/app && grep '^MOTOR_ACESSOS_ADMIN_USUARIOS=' .env
```

**Se o seu login não estiver ali**, acrescente-o (separado por vírgula) e, com o `unset` do 0.b
antes, `docker compose -f docker-compose.prod.yml up -d --no-deps web`. **Depois do corte** o painel passa a
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

**Antes de virar a chave**, avise quem usa o piloto. Cinco coisas:

1. **A tela de entrar não muda: é a mesma que a equipe já usa** — a nossa, servida no endereço
   `auth.` desde 22/09/2026. O que muda: na primeira ação depois da virada aparece o pop-up
   **"Sessão encerrada"** (é só clicar em **"Entrar novamente"**), e a senha passa a ser conferida
   pelo piloto, não mais pelo Authelia. Durante a virada (entre os Passos 4 e 5) quem entrar faz
   **dois** logins; é esperado e dura minutos.
2. **Usuário e senha.** O usuário é o **mesmo de hoje** — atenção ao exemplo cinza do campo, que diz
   `nome.sobrenome`: os logins usam sublinhado (`nome_sobrenome`), e a tela não converte um no outro.
   A senha é a **compartilhada de hoje** (decisão de 24/10/2026, Passo 0.b), para todo mundo —
   **inclusive quem usa senha pessoal no Authelia (como o Felipe)**: a pessoal não existe no banco. No
   primeiro acesso abre o convite para criar a própria senha (no mínimo 8 caracteres e diferente da
   compartilhada; pode ser a pessoal de antes). Ele tem "Agora não", mas aceitar é o recomendado — e,
   depois de trocar, a tela pede para entrar de novo com a senha nova.
3. **Se errarem a senha 5 vezes em 15 minutos, a conta trava.** E o servidor responde a mesma
   mensagem de "senha incorreta" — de propósito, para não avisar a quem varre nomes que acertou
   um. Duas saídas, e diga as duas: **esperar** — a janela é MÓVEL, então a trava se desfaz
   sozinha quando a tentativa mais antiga completa 15 minutos — ou **pedir a um administrador
   para redefinir a senha** pelo painel de Acessos, o que destrava na hora. A segunda depende de
   haver um administrador disponível; a primeira, não. Os administradores são os da allowlist do
   painel (`MOTOR_ACESSOS_ADMIN_USUARIOS`).
4. **Quanto dura a sessão.** Com **"Manter conectado"** marcado, ela sobrevive a fechar e reabrir o
   navegador; sem a caixa, termina quando o navegador fecha. Nos dois casos, **8 h** é o teto, e
   **2 h parado** desconecta.
5. **A senha temporária** (a que um administrador gera para quem esqueceu a senha) vale **2 h**:
   troque ao entrar.

> Deixe `docker compose -f docker-compose.prod.yml logs -f web` aberto durante a janela: é o
> único lugar onde a trava aparece nomeada.

---

## Passo 2 — Subir a imagem nova

A imagem nova é a que traz o código de 24/10/2026 — o que esconde o cadeado e os gestos de senha
enquanto a chave estiver desligada. Os merges do P19 já estão na imagem no ar; sem imagem nova
publicada, este passo é só conferência.

**No terminal da VPS:**
```bash
cd /opt/motor-expansao/app
cp -n .env .env.bak-$(date +%F)  # -n = NÃO sobrescreve se já existir (leia o aviso abaixo)
grep '^WEB_IMAGE=' .env          # anote esta linha
# edite o .env: WEB_IMAGE=<digest novo>
unset MOTOR_DATABASE_URL MOTOR_SENHA_INICIAL MOTOR_AUTENTICACAO_PROPRIA   # ver o 0.b
docker compose -f docker-compose.prod.yml up -d --no-deps web
```

> **Não há `git pull` aqui** (até 24/10/2026 havia): o checkout da VPS é do root, está num commit
> antigo, e nada deste passo depende dele — a imagem vem do registro, pelo digest.

> **A cópia não é zelo, é o caminho de volta.** A edição do `WEB_IMAGE` que este bloco pede escreve
> por cima do valor antigo, e ele deixa de existir no arquivo. Sem a cópia, a instrução de rollback aqui embaixo é
> impossível de executar — e você descobriria isso justamente no momento em que o piloto não abriu.
>
> **O `-n` é o que protege contra rodar este passo DUAS vezes no mesmo dia** — o que é exatamente o
> que se faz depois de um erro. O nome do arquivo tem a data, então a segunda execução escreveria em
> cima da primeira: a cópia passaria a guardar o digest **novo**, e o rollback devolveria a imagem
> que você está tentando desfazer. Sem erro nenhum, com um digest de aparência perfeita. Com `-n`, a
> segunda execução simplesmente não toca no arquivo.

> **Se você já trocou o `WEB_IMAGE` antes de chegar aqui** — no runbook das migrations, no
> *Movimento 1* do pacote de repasse do banco novo, ou para o 0.c rodar fora da janela — e nenhuma
> imagem nova foi publicada desde então,
> este passo é **só conferência**: o `grep` acima tem de mostrar exatamente o digest que
> você recebeu. Não existe um segundo build.

**Esperado:** o container reinicia e o piloto continua funcionando **exatamente como antes** — o
Authelia ainda autenticando. A chave ainda está desligada. O que muda na tela vem do código de
24/10/2026: o cadeado "Trocar a minha senha" sai do menu, o painel de Acessos perde "Redefinir
senha" e "Exigir troca" (os três voltam no Passo 4), e a coluna da senha passa a se chamar
"Senha (banco)".

> **A instância ARGENTINA usa o MESMO `WEB_IMAGE`.** Você acabou de editar o `.env`, que é
> compartilhado: a AR ficou com o arquivo dizendo um digest e o processo rodando outro, e
> saltaria de imagem no próximo `up -d` que alguém desse nela. Suba-a também, agora — **uma vez só**:
>
> **No terminal da VPS:**
> ```bash
> docker compose -f docker-compose.ar.yml up -d --no-deps web_ar
> ```
> **Esperado:** reinicia e continua atrás do Authelia, sem mudança visível.

**Se o piloto não abrir:** volte o `WEB_IMAGE` para o digest anterior e suba de novo. O valor está
na cópia que você fez no começo deste passo — e **confirme que ela é de verdade a cópia antiga**,
comparando as duas linhas:

**No terminal da VPS:**
```bash
grep '^WEB_IMAGE=' .env.bak-$(date +%F)   # o valor de volta
grep '^WEB_IMAGE=' .env                   # o que está no ar agora
```

**As duas linhas têm de ser DIFERENTES.** Se vierem iguais, a cópia não é mais a antiga — e aí ela
não serve para voltar. O digest anterior estará em `.env.bak-antes-do-p19`, se o pacote de repasse do
banco foi seguido; se não estiver em nenhum dos dois, **pare e chame quem repassou** antes de
inventar um valor.

Nada foi cortado ainda.

---

## Passo 3 — Conferir a credencial do banco (dada em 23/10/2026)

**Feito na produção em 23/10/2026:** a `MOTOR_DATABASE_URL` (papel `app`) entrou no `.env` e o `web`
foi recriado com ela; desde então o RBAC do BR vem do banco. Aqui sobra a conferência — e ela não é
formalidade: **sem banco, o corte apaga o piloto inteiro**, e o apagão começaria já no Passo 4, quando
a chave liga: sem banco, `validar()` falha e toda rota `/api/*` responde 503. A sessão vive em tabela,
e a chave do Passo 4 **não avisa** que o banco falta: ela não consulta o banco, só a própria variável.

**No terminal da VPS** (só contagens; nada aqui imprime a URL, que leva a senha do `app`):
```bash
cd /opt/motor-expansao/app
grep -c '^MOTOR_DATABASE_URL=postgresql://app:' .env
docker compose -f docker-compose.prod.yml exec web python -c 'import os; print("web com a URL:", bool(os.environ.get("MOTOR_DATABASE_URL")))'
```

**Esperado:** `1` e `web com a URL: True`. **Se não vier,** pare: o estado esperado desde 23/10/2026 é
a URL preenchida, e ligar ou desligar o banco é o §8 do `docs/banco_deploy.md`, fora deste documento.

> **Não confira com `grep '^MOTOR_DATABASE_URL=' .env`** — até 24/10/2026 este passo mandava fazer
> isso, e ele imprime a URL inteira, com a senha do `app`.

**Confira, com o papel certo:**

**No terminal da VPS:**
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

**Se vier `ERRO: defina MOTOR_DATABASE_URL`:** a variável não chegou ao container — confira o
`.env` e se não há uma `MOTOR_DATABASE_URL` no seu terminal, que, mesmo vazia, venceria o `.env`
(`unset MOTOR_DATABASE_URL`).
**Se vier muitos `FALHA` e um recado sobre o dono:** você usou a credencial do **dono** em vez da
do `app`. Troque — usar a do dono anula o isolamento de privilégios inteiro.

---

## Passo 4 — Ligar a chave

**No terminal da VPS:**
```bash
cd /opt/motor-expansao/app
grep -c '^MOTOR_AUTENTICACAO_PROPRIA=' .env   # 1 = a linha existe; 0 = não existe; mais que 1 = pare
# 1: edite a linha para  MOTOR_AUTENTICACAO_PROPRIA=1
# 0: acrescente-a no fim:  printf '\nMOTOR_AUTENTICACAO_PROPRIA=1\n' >> .env
grep '^MOTOR_AUTENTICACAO_PROPRIA=' .env      # UMA linha: MOTOR_AUTENTICACAO_PROPRIA=1 (este valor não é segredo)
unset MOTOR_DATABASE_URL MOTOR_SENHA_INICIAL MOTOR_AUTENTICACAO_PROPRIA
docker compose -f docker-compose.prod.yml up -d --no-deps web
```

> **A linha pode não existir no `.env`:** a da `MOTOR_DATABASE_URL` não existia em 23/10/2026 e foi
> acrescentada no fim. Os dois casos estão acima; o que importa é sair com **uma** linha só.

> **`up -d --no-deps web`, NÃO `restart web`.** O `restart` não relê o `.env` — o container voltaria com o
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
  quebrou;
- **e o que o código de 24/10/2026 escondia volta a aparecer** para quem entra pela nossa tela: o
  cadeado "Trocar a minha senha" no menu, o convite de troca para quem o 0.c alinhou e, no painel de
  Acessos, "Redefinir senha" e "Exigir troca". Antes da chave eles não aparecem, e as rotas deles
  respondem 404. A conferência é no Passo 6, item 2.

Por isso o Passo 5 é a continuação natural deste, e não um passo para outro dia.

**Confira que a chave chegou:**

**No terminal da VPS:**
```bash
docker compose -f docker-compose.prod.yml exec web printenv MOTOR_AUTENTICACAO_PROPRIA
```

**Esperado:** `1`.

**Se vier vazio ou "não encontrado":** o `up -d` não rodou, ou a chave não está no bloco
`environment:` do compose — o que o **#416** (merge `f5b5e9b`) levou para a `main`, e que o compose
da VPS tem desde a troca de 17/10/2026. Confira no arquivo da VPS:

**No terminal da VPS:**
```bash
grep -n MOTOR_AUTENTICACAO_PROPRIA docker-compose.prod.yml
```

**Pare** — o passo 5 sem isto derruba o piloto.

---

## Passo 5 — Trocar o bloco do Caddy

**Este é o passo que fecha o corte.** Dá para voltar (ver *Se precisar voltar atrás*), mas com o
piloto fora do ar no meio. O que a equipe SENTE começou no passo anterior, com a chave.

**Quem executa depende de quem pode escrever no `Caddyfile`** — e a escrita tem de ser no MESMO
arquivo (mesmo inode): o Caddy o recebe por bind de ARQUIVO (`./Caddyfile:/etc/caddy/Caddyfile:ro`, no
`docker-compose.prod.yml`), e um editor que troca o arquivo ao salvar deixa o container lendo o
antigo — o `caddy reload` recarrega o bloco velho dizendo OK. Foi assim que o Caddyfile divergiu em
22/09/2026 (comentário do `docker-compose.prod.yml`). Confira antes da janela:

**No terminal da VPS:**
```bash
cd /opt/motor-expansao/app
stat -c '%U:%G %a inode=%i' Caddyfile
docker exec motor_expansao_caddy stat -c 'inode visto pelo container=%i' /etc/caddy/Caddyfile
test -w Caddyfile && echo "a conta pode escrever" || echo "a conta NAO pode escrever"
```

Os dois inodes têm de ser iguais — se não forem, pare: o Caddy está lendo uma versão antiga do
arquivo. **Se a conta `deploy` não puder escrever**, este passo e o rollback
ficam com o Felipe (root) — ou ele ajusta antes, sem trocar o inode:
`chgrp motor-ops Caddyfile && chmod 664 Caddyfile`.

**Copie o bloco atual antes de tocar nele** — o `Caddyfile` é gitignored, então o que está lá
não existe em nenhum outro lugar, e é dele que você vai precisar se tiver de voltar atrás:

**No terminal da VPS:**
```bash
cd /opt/motor-expansao/app
cp -n Caddyfile Caddyfile.antes-do-p19   # -n: rodar de novo não troca a cópia de antes pela de depois
```

O `-n` também preservaria uma cópia velha, de uma tentativa anterior a esta janela. Se o arquivo já
existia, confira antes de seguir: `cmp Caddyfile Caddyfile.antes-do-p19` não pode acusar diferença
antes do corte. Se acusar, renomeie a cópia velha e copie de novo.

**Leve o template à VPS** — o checkout de lá não o tem. **Na sua máquina, num checkout da `main`:**
```bash
scp -i ~/.ssh/id_ultra_deploy deploy/caddy/piloto-br.Caddyfile.template deploy@<vps>:~/
```
O template também está dentro da imagem no ar (na versão do commit dela), se preferir lê-lo de lá:
`docker exec motor_expansao_web cat /app/deploy/caddy/piloto-br.Caddyfile.template`. Se quem
executa este passo for o Felipe, como root, o `~` dele é outro: o `scp` deixa o template em
`/home/deploy/`.

**Antes de colar, compare os dois lado a lado.** Este passo substitui o bloco **inteiro**, então
**toda diretiva que exista no bloco vivo e não exista no template desaparece** — compressão
(`encode`), headers, `tls` explícito, outro caminho de log, uma rota extra. O template nasceu depois
do bloco que está no ar e não pode saber o que foi acrescentado à mão lá:

**No terminal da VPS:**
```bash
grep -n -A40 'piloto.ultra-expansao.tech {' Caddyfile.antes-do-p19
```

Leia essa saída contra o template. **Qualquer linha que só exista no bloco vivo precisa ser levada
para o texto novo.** E o `caddy validate` do fim deste passo **não reclama do que faltar** — uma
configuração menor é uma configuração válida. O Passo 6 daria tudo verde e a perda só apareceria
dias depois.

Agora monte o arquivo novo **numa cópia**, não no `Caddyfile` —
`cp Caddyfile.antes-do-p19 ~/Caddyfile.novo` — e, nessa cópia, substitua o bloco de
`piloto.ultra-expansao.tech` pelo bloco `piloto.ultra-expansao.tech { … }` do template —
**da linha `piloto.ultra-expansao.tech {` até a chave que a fecha**. As primeiras linhas do template são comentário explicando decisões do projeto:
elas são explicação, não configuração, e não vão para o servidor.

> **NÃO TOQUE no bloco `piloto-ar.ultra-expansao.tech`.** Ele continua apontando para
> `authelia:9091`, e isso é decisão — a AR não tem banco e cairia inteira.

**No terminal da VPS:**
```bash
cd /opt/motor-expansao/app
cat ~/Caddyfile.novo > Caddyfile    # grava no MESMO inode; nunca mv, nem editor que troque o arquivo
docker exec motor_expansao_caddy cat /etc/caddy/Caddyfile | cmp - Caddyfile && echo "o container ve o arquivo novo"
docker compose -f docker-compose.prod.yml exec caddy caddy validate --config /etc/caddy/Caddyfile
docker compose -f docker-compose.prod.yml exec caddy caddy reload --config /etc/caddy/Caddyfile
```

**Esperado:** `o container ve o arquivo novo`, `Valid configuration` e o reload sem erro. **Se o
`validate` reprovar,** devolva o arquivo (`cat Caddyfile.antes-do-p19 > Caddyfile`) e pare: sem o
reload, o Caddy segue servindo o bloco antigo.

**Atualize os backups cifrados — o do `Caddyfile` e o do `.env` —**, senão um restore desfaz o
corte em silêncio, ou junta um `Caddyfile` de depois do corte com um `.env` sem a chave (apagão).
**Pela sua máquina, não pela VPS:** o `sops` e a chave age ficam na estação do Vinicius (até
24/10/2026 este passo mandava rodar o `sops` no servidor). O texto em claro sai da VPS por `ssh` e
entra direto no `sops`, sem passar pela tela nem pelo disco. Numa branch nova criada da `main`, na raiz
do repositório:

**Na sua máquina (Git Bash):**
```bash
set -o pipefail
ssh -i ~/.ssh/id_ultra_deploy deploy@<vps> 'docker exec motor_expansao_caddy cat /etc/caddy/Caddyfile' \
  | sops encrypt --input-type binary --output-type binary --filename-override secrets/Caddyfile.enc \
  > secrets/Caddyfile.enc.novo && mv secrets/Caddyfile.enc.novo secrets/Caddyfile.enc
ssh -i ~/.ssh/id_ultra_deploy deploy@<vps> "grep -E '^[A-Za-z_][A-Za-z0-9_]*=' /opt/motor-expansao/app/.env" \
  | sops encrypt --input-type dotenv --output-type dotenv --filename-override secrets/env.enc.env \
  > secrets/env.enc.env.novo 2>/dev/null && mv secrets/env.enc.env.novo secrets/env.enc.env
sops -d --input-type binary --output-type binary secrets/Caddyfile.enc | grep -c 'forward_auth @protegido web:8899'   # 1
grep -c '^MOTOR_AUTENTICACAO_PROPRIA=ENC\[' secrets/env.enc.env                                               # 1
```

Só as linhas `VAR=valor` do `.env` vão para o cifrado: o `sops` guardaria comentário em texto puro. O
erro do segundo `sops` vai para `/dev/null` de propósito: a mensagem dele pode repetir uma linha do
`.env`, com senha; se ele falhar, o `mv` não roda e a última conferência sai `0`. O
PR toca `secrets/`, que o guard trata como CRÍTICO (`critica-aprovada`). O `secrets/env.enc.env` da
`main` é de 17/10/2026 e não tem nem a `MOTOR_DATABASE_URL` de 23/10, então refazê-lo é devido mesmo
antes do corte.

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
   **Confira também o que só existe com a chave ligada (código de 24/10/2026):** o convite abre para
   quem o 0.c alinhou; o cadeado **"Trocar a minha senha"** aparece no menu; e, no painel de Acessos,
   **"Redefinir senha"** e **"Exigir troca"** aparecem nas linhas dos outros (na sua, desabilitados), na tabela
   com a coluna **"Senha (banco)"**. Se você trocar a sua senha agora, a troca derruba a sessão desta
   aba: a tela de sucesso diz **"Entre de novo com a senha nova"**, e o botão leva à tela de entrar —
   é o esperado, não erro.
   > **Mas para quem recebeu uma senha TEMPORÁRIA de um admin, o "Agora não" é armadilha:**
   > essa senha vence em **2 horas**, e depois disso ela não entra mais — precisa de outra
   > redefinição. Quem receber temporária tem de trocar dentro do prazo. Diga isso ao
   > repassar a senha.
   > **E cuidado com VOCÊ MESMO aqui: cinco senhas erradas travam a SUA conta.** A régua do
   > Passo 1 (`MAX_TENTATIVAS = 5` numa janela **móvel** de 15 min) vale para todo mundo,
   > inclusive para quem está conduzindo o corte. A tela diz *"Muitas tentativas seguidas.
   > Por segurança, o acesso ficou bloqueado — aguarde alguns minutos antes de tentar de
   > novo, ou peça a um administrador para redefinir a sua senha"* — e **a segunda metade
   > dessa frase não serve para você neste momento**: o administrador é você, e o painel de
   > Acessos está atrás do login que você acabou de perder. A não ser que outra pessoa da
   > allowlist já esteja logada numa outra aba, a única saída é **esperar**: a janela
   > desliza, então o que destrava é a mais antiga das cinco tentativas completar 15 minutos.
   > Não há relógio fixo para olhar.
   >
   > **Isto NÃO é o corte ter falhado, e não é motivo para voltar atrás.** Esperar quinze
   > minutos é muito mais barato que executar um rollback — que é uma mudança de verdade, na
   > borda, com o piloto fora do ar no meio.
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
6. **Confira a API com uma sessão falsa** — é o que o check `auth` do healthcheck da `main` repete a
   cada 5 min:
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' -H 'Cookie: __Host-motor_sessao=sonda-do-healthcheck' \
     https://piloto.ultra-expansao.tech/api/me
   ```
   **Esperado:** `401`. `200` quer dizer que a API respondeu sem sessão válida — volte atrás. `503`
   quer dizer que o `/api/verify` não conseguiu consultar o banco, e então ninguém entra — volte
   atrás. O cookie falso é o que faz este item conferir o banco: sem cookie, o `/api/verify`
   responde 401 sem consultá-lo, e um banco fora também daria `401`. O valor do cookie não é
   segredo: não existe sessão com ele.

**Se o item 1 der outra coisa** — a tela do Authelia, ou o piloto abrindo usável sem pop-up, ou erro
que nenhum item previu —, **ou se o item 2 não conseguir entrar:** vá direto para *Se precisar voltar
atrás*, abaixo. O pop-up "Sessão encerrada" do item 1 **não** é esse caso: ele é o esperado.

---

## Se precisar voltar atrás

**A ordem é o INVERSO da de ligar. Invertê-la derruba o piloto inteiro.**

1. **Primeiro o Caddy:** devolva o bloco antigo **inteiro**, copiando-o de **`Caddyfile.antes-do-p19`**
   — a cópia que você fez no começo do Passo 5. É o bloco com `forward_auth authelia:9091` cobrindo
   tudo, **sem** o matcher `@protegido`. Reapontar só a linha do `forward_auth` deixaria o
   `@protegido` de pé — a raiz e os estáticos servidos a quem não entrou —, e o `caddy validate`
   aprova isso sem reclamar. Quem executa é quem executou o Passo 5, e a escrita é no mesmo inode,
   pela mesma razão. Se nada mais mudou no arquivo desde o Passo 5, devolva-o inteiro, como abaixo;
   se outro bloco mudou nesse meio-tempo, monte uma cópia em que só o bloco
   `piloto.ultra-expansao.tech { … }` volta ao de antes e grave-a do mesmo jeito. Depois recarregue:

   ```bash
   cd /opt/motor-expansao/app
   cat Caddyfile.antes-do-p19 > Caddyfile    # mesmo inode
   docker exec motor_expansao_caddy cat /etc/caddy/Caddyfile | cmp - Caddyfile && echo "o container ve o arquivo devolvido"
   docker compose -f docker-compose.prod.yml exec caddy caddy validate --config /etc/caddy/Caddyfile
   docker compose -f docker-compose.prod.yml exec caddy caddy reload --config /etc/caddy/Caddyfile
   ```

2. **Só então a chave:** `MOTOR_AUTENTICACAO_PROPRIA=` (vazia),
   `unset MOTOR_DATABASE_URL MOTOR_SENHA_INICIAL MOTOR_AUTENTICACAO_PROPRIA` e
   `docker compose -f docker-compose.prod.yml up -d --no-deps web` — **`up -d`, NÃO `restart`**: o `restart` não
   relê o `.env`, e o `web` voltaria com a chave ligada.

> **A `MOTOR_DATABASE_URL` FICA preenchida — não a esvazie.** Ela não tem nada a ver com quem
> autentica; esvaziá-la devolveria o controle de abas ao `acesso_abas.json` e é uma segunda mudança
> no meio de uma emergência. **Consequência que você precisa esperar:** com ela preenchida o piloto
> segue no RBAC do banco, então quem ainda não tem perfil continua **abrindo o piloto vazio** mesmo
> com o Authelia de volta. Isso **não** é rollback malfeito — é o Passo 3 ainda em vigor, e se
> resolve dando perfil à pessoa pelo painel de Acessos.
>
> **E depois do corte o interruptor do banco deixa de existir:** sem banco ninguém entra. Para
> desligar o banco, desfaça primeiro o P19 (esta seção) e só então esvazie a URL (§8 do
> `docs/banco_deploy.md`).

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
esse cadastro paralelo que torna o rollback sobrevivível — e o recado da tela de Acessos, depois de
criar alguém com a chave ligada, lembra disso.

**Para saber quem seria afetado**, o banco responde:

**No terminal da VPS:**
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
| **Tirar acesso de alguém** | remover do `users_database.yml` + restart do Authelia, e desativar a linha em `usuarios` pelo painel (desde 23/10/2026 as abas do BR vêm do banco) | **desativar a linha em `usuarios`** pelo painel de Acessos — a sessão morre na requisição seguinte. Durante a janela de observação, tire também do `users_database.yml`: senão um rollback devolve o acesso. Nos dois casos, o bot sai à parte (`bot_allowlist.json`; `docs/infra_producao.md`, "Revogar usuário") |
| **Postgres fora do ar** | o piloto continua no ar, com o RBAC degradado (desde 23/10/2026 as abas vêm do banco; detalhe no Runbook de incidente do `docs/infra_producao.md`) | **o piloto inteiro fica fora** — sem banco não há sessão, e o Caddy nega tudo |
| **Sessão expirada** | o Authelia redireciona | a SPA abre o pop-up "Sessão encerrada" e, no clique, leva à nossa tela de entrar |

> **O item do meio é o mais importante para quem recebe alerta de madrugada.** O comentário do
> `healthcheck_vps.sh` já separa as duas fases (antes do corte o `web` não cai junto com o Postgres) — a segunda passa a valer
> aqui. Postgres fora = piloto BR indisponível. Por isso o healthcheck da `main` tem de estar
> instalado antes (ver *Antes de marcar a janela*): o que rodava na VPS em 24/10/2026 não vigia o
> Postgres.

---

## O cron de expurgo (instalado em 17/10/2026)

Ele apaga IP e user-agent das sessões com mais de 90 dias — prazo decidido, não higiene opcional.

**Já está instalado, e fora do caminho de root que o cabeçalho do script descreve** (decisão de
17/10/2026): roda às 04:40 UTC no crontab da conta `deploy`, por `~/motor-infra/run_expurgo_sessoes.sh`,
com log em `~/logs/expurgo_sessoes.log` — 30 min antes do backup das 05:10, que é a ordem que a
retenção exige (`docs/banco_deploy.md` §9.1). Até o corte ele não tem o que fazer: sessão só nasce no
login próprio. **Depois do corte**, confira no log que ele segue rodando; o subcomando `banco` do
healthcheck da `main` vigia isso.

> **Risco declarado:** o offboarding padrão da conta `deploy` (`userdel -r`) apagaria em silêncio este
> cron, o do backup e os dumps em `/home/deploy/backups/banco`. Quem revogar essa conta tem de mover os
> dois crons antes.

---

## Quem chamar

- **Durante a janela:** quem repassou este documento.
- **Se o piloto ficar fora e o rollback não resolver:** o bloco antigo do Caddy está em
  **`/opt/motor-expansao/app/Caddyfile.antes-do-p19`** (a cópia do Passo 5) e, se ela tiver se
  perdido, no backup cifrado **de antes do corte** — o `secrets/Caddyfile.enc` anterior ao commit que
  o refez no Passo 5, decifrado na estação do Vinicius (`sops -d`; é lá que ficam o `sops` e a chave).
  **O `Caddyfile` em claro nunca esteve versionado:** é gitignored.
