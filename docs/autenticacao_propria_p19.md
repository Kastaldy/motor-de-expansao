# Autenticação própria do piloto (epic do P19) — escopo

> **O que é.** O levantamento do que a epic do **P19** precisa fazer para o motor passar a autenticar
> e o Authelia sair. Não é especificação de implementação nem cronograma: é o mapa do terreno,
> medido, para que a primeira pessoa a pegar isto não comece descobrindo o que já existe.
>
> **Decisão anterior, não reabrir.** O P19 (`banco-de-reservas/decisoes-pendentes.md`) escolheu a
> opção **(c)** em 01/09/2026 — o motor autentica, o Authelia sai — **contra a recomendação** do
> próprio documento, com o escopo perguntado explicitamente antes. Este documento serve à decisão
> tomada; não a discute.
>
> **Tudo aqui foi medido em 16/09/2026**, salvo o que estiver marcado como **proposta** ou
> **em aberto**. Onde eu não medi, está escrito que não medi.

## 1. O que já existe (e é mais do que parece)

A leitura corrente — inclusive a do próprio P19 — subestima o que está pronto. Medido:

**No banco e no backend (entregues pela D26, migration 016):**

- `db/senhas.py`: `gerar`, `verificar` e política de força, em **Argon2id** com os parâmetros padrão
  do Authelia 4.37+. A escolha foi deliberada para permitir **importar** os hashes existentes.
- `usuarios.senha_hash` guarda PHC de verdade; `senha_definida_em_usuario` e
  `deve_trocar_senha_usuario` dão o ciclo de vida.
- `PATCH /api/me/senha` (a pessoa troca a própria) e, na tela de administração, criar usuário,
  redefinir senha e exigir troca.
- `acesso.login_da_requisicao` é o **funil único** de identidade: hoje lê o header e, no vazio, cai
  na identidade de desenvolvimento (travada em produção por `MOTOR_CADASTRO_DIR`).

**No front:**

- `AvisoSessao.tsx` + `lib/sessao.ts`: **detecção de sessão vencida** por sonda, com trava de mão
  única e sobreposição bloqueante com "Entrar novamente". Erro de rede e backend fora **não**
  disparam, de propósito.
- `BotaoSair.tsx`: botão de sair com confirmação, que hoje navega para o `/logout` do portal
  (`lib/logoff.ts` monta a URL do hostname; devolve `null` em dev, e o diálogo diz que não há sessão
  a encerrar).
- `TrocaDeSenha.tsx` + `lib/troca-de-senha.ts`: tela de troca e a política espelhada no cliente.

**O que falta, então, é menor do que "construir autenticação":** o **formulário de login**, o
**portão de sessão** no backend, e a **troca do critério** de expiração no front.

## 2. O ponto de inserção — e a regra de ordem que decide onde ele vai

Aqui o P19 descreve a epic maior do que ela é. Ele diz que "cada rota passa a validar sessão por
conta própria". **Não é o caso neste código:** o controle de acesso já é um middleware **global**
(`_controle_de_acesso_por_aba`), então a validação de sessão cabe **num ponto só** — não nas ~40
rotas.

**A ordem importa, e é contraintuitiva.** `@app.middleware("http")` empilha cada novo middleware
**por fora**, então **o último declarado roda primeiro**. Em `web/server/app.py`, `_trilha_acesso`
(DEC-027) é declarado **depois** de `_controle_de_acesso_por_aba` — e por isso a trilha **envolve** o
controle, registrando inclusive os 403 que ele devolve:

| Ordem de execução | Middleware | Declarado |
|---|---|---|
| **1º** | `_trilha_acesso` (DEC-027) | por último |
| 2º | `_controle_de_acesso_por_aba` | antes dele |

> **Confira, não confie nesta tabela.** O que vale é a ordem de declaração no arquivo, e ela se lê
> com `grep -n '@app.middleware("http")' -A2 web/server/app.py`. Números de linha envelhecem a cada
> inserção acima deles — e um documento que os cita como fato vira mentira silenciosa, que é a
> família de defeito que a revisão de 16/09/2026 passou o dia corrigindo neste repositório e no
> `banco-de-reservas`. Na data da medição eram 357 e 662, nessa ordem.

O portão de sessão precisa ser declarado **entre os dois** — depois do controle de abas, antes da
trilha — para rodar **antes** do controle e **dentro** da trilha. Nessa posição, um 401 de sessão
inválida é barrado cedo e ainda assim vira linha de auditoria. Declarado fora dessa faixa, ou o 401
some do log, ou a pessoa sem sessão chega ao controle de abas.

## 3. O que precisa continuar público

Hoje nada disso importa: o Authelia barra na borda, e requisição sem sessão **não chega** ao
backend. Depois do corte, o motor é a única porta — e ele serve a SPA:
`app.mount("/", StaticFiles(..., html=True))`, registrado **por último**, depois das rotas de API.

Precisam continuar alcançáveis sem sessão:

- os **estáticos da SPA** e a rota da tela de login (mesmo processo, mesmo host);
- o **endpoint de login** em si;
- `/api/health`, que hoje não tem regra e é mudo por decisão de pentest.

E `/api/me`, que hoje é livre e é a **primeira chamada da SPA**, passa a exigir sessão — é ela que
responde "quem sou eu" depois do login.

## 4. Ninguém pode ficar trancado no corte — e há duas rotas

Medido, e as duas já estão disponíveis:

1. **Importar os hashes do Authelia.** O `users_database.yml` guarda `argon2id`, e a D26 escolheu os
   mesmos parâmetros exatamente para isso. Ninguém redefine senha no dia da virada.
2. **Esvaziar a fila antes.** As pessoas podem definir senha própria **desde já**, e
   `senha_definida_em_usuario` é literalmente a fila: nulo = ainda na senha inicial. O P19 diz, com
   estas palavras, que essa coluna "é a fila que a epic precisa zerar".

As duas se combinam: importar cobre quem não agiu, a fila mede quem já agiu.

**Não medido:** quantas pessoas já têm senha própria hoje. Isso exige consultar o banco em produção,
o que não foi feito daqui.

## 5. Obrigações que a epic herda

- **Evento `login`.** O contrato (`eventos_contrato.md` §2.1) já o especifica — `metadados` com
  `origem` (`web`/`bot`), sem `entidade` — e traz a nota de que ele "ainda não é registrável" porque
  a entrada não passa pelo backend. A epic é o que destrava, e a nota sai junto. `logout` idem, sem
  metadados.
- **Reabrir o P14.** Hoje `senha_hash` é dado que ninguém lê; depois do corte vira a credencial de
  acesso à plataforma. A opção (c) do P14 (restringir a coluna por `GRANT` + função de login
  `SECURITY DEFINER`) foi adiada nomeando só "requisito de LGPD/auditoria" como gatilho — o corte é
  gatilho por si, e o texto do P14 ainda não diz isso.
- **`BLK-SEC-03-FU2`** (revisão de acesso e offboarding) é pré-requisito prático: é dele que sai a
  conciliação entre `users_database.yml` e as linhas de `usuarios`. Já separado do FU1 em
  16/09/2026 justamente por sobreviver ao corte.
- **`BLK-SEC-03-FU1`** (forçar TOTP no Authelia) está **SEM OBJETO desde 22/09/2026**: a decisão 3
  (§7) fechou que 2FA não entra no projeto por agora. Até aquela data ele estava só **adiado**, com
  a ressalva de que "se a epic ganhar data distante, ele volta à mesa" — a decisão do dono substitui
  essa ressalva. Reabrir o FU1 exige reabrir a decisão 3 antes, e não o contrário.

## 6. Armadilhas medidas

- **`python-jose` e `passlib` estão no `pyproject.toml` — e são cilada.** Vivem no extra `api`
  **legado**, que, segundo o comentário ao lado, **nenhum Dockerfile instala** e que arrasta
  SQLAlchemy, psycopg2-binary e Prefect. Usá-los "porque já estão declarados" traz a cascata inteira
  para a imagem do piloto. O `argon2-cffi` que a D26 usa está no extra `auth`, próprio, e **esse** a
  imagem instala.
- **A identidade de desenvolvimento não pode virar porta.** `rbac.login_efetivo` tem duas travas
  (override explícito e o sinal de produção `MOTOR_CADASTRO_DIR`). O portão de sessão precisa
  respeitar as mesmas, senão o modo de dev vira caminho de entrada em produção.
- **Limpar estado no cliente não é logout.** O `BotaoSair` documenta o motivo: a tela pareceria
  deslogada e a requisição seguinte continuaria autenticada. Logout tem de invalidar no servidor.

## 7. Decisões ainda em aberto

Nenhuma destas foi tomada. Estão aqui para não serem descobertas no meio da implementação:

1. ~~**Onde a sessão vive**~~ — **DECIDIDA em 17/09/2026 pela D30: tabela** (`sessoes`,
   `banco-de-reservas/sql/018-sessoes.md`). O "custo de leitura por requisição" que pesava contra
   ela foi **medido e não existe**: as 26 regras de `REGRAS_POR_CAPACIDADE` já chamam
   `rbac.identidade()` a cada requisição guardada, sem cache, e a validação de sessão entra como
   **um JOIN na mesma consulta**. O que decidiu foi a **revogação central** — logout que invalida
   de verdade, troca de senha derrubando sessões, admin expulsando alguém —, que cookie assinado
   não tem. Contra o cookie pesaram também um segredo novo (logo após o `config.py` perder o
   `SECRET_KEY` morto) e dependência nova na imagem: `itsdangerous` não está no `pyproject.toml`
   nem no `constraints.txt`.
2. ~~**Duração da sessão e inatividade**~~ — **DECIDIDA em 17/09/2026, sem `D`** (não toca schema):
   **reproduzir** o Authelia — **8h** de teto absoluto, **30 min** de inatividade — e "lembrar de
   mim" **fiel**, cookie persistente entre fechar e reabrir o navegador com os mesmos 8h (lá o
   `remember_me` já é igual ao `expiration`, então isto reproduz e não estende). Reproduzir em vez
   de escolher porque o comentário da configuração do Authelia registra que mexer nesses números
   **derrubou o login da rede por ~4h em 06/08/2026** — e, com a tabela da D30, o número é coluna,
   então mudá-lo depois é política e não código.
   **Trava de 5 min na inatividade**, por medição: a validação roda em `SET TRANSACTION READ ONLY`,
   onde o servidor recusa escrita, então reescrever `ultimo_acesso_em_sessao` exigiria uma SEGUNDA
   transação por requisição guardada (`set_config` + `UPDATE` + `COMMIT`) sobre um pool de 4
   conexões. Com a trava, a coluna só é reescrita se já tiver mais de 5 min — pior caso, alguém sai
   aos 30 min em vez de ~35. Decidir se vale escrever é de graça: a consulta de validação já
   devolve a coluna.
   **Duas consequências para o front, que esta decisão já resolve:** (i) "lembrar de mim" é
   **caixinha nova** no formulário de login — medido, não existe nada hoje (`lembrar`/`remember`:
   zero ocorrências em `web/src`); (ii) a **sonda de `lib/sessao.ts` deixa de ser necessária para o
   caso de sessão**, porque o portão próprio responde **401** e `relatarAcessoNegado()` já trata 401
   direto, sem sondar. A sonda continua útil só para separar "backend fora do ar" de outras falhas
   de rede — o 302→CORS→`TypeError` que a obrigou a existir morre com o Authelia.
3. ~~**2FA depois do corte**~~ — **DECIDIDA em 22/09/2026, sem `D`** (não toca schema e não entra
   código): **não entra no projeto por agora**, por decisão do dono.
   **A premissa do enunciado anterior estava errada, e foi medida antes de perguntar:** não há 2FA
   a perder. As duas regras do Authelia são `one_factor` (`authelia/configuration.yml`, e o
   `plano_multipais.md` §514 já registrava isso ao tratar de outra coisa), e o `BLK-SEC-03-FU1`
   existia justamente para **ligá-lo** — adiado em 16/09 por configurar 2FA no componente que sai.
   Então o corte não remove nada; o que se decidiu foi **não acrescentar**. O FU1 fica **sem
   objeto** enquanto esta decisão valer.
   **CONSEQUÊNCIA QUE ESTA DECISÃO CRIA, e que o resto da epic herda:** a plataforma segue de
   **fator único**. A senha passa a ser a única barreira, e tudo o que a protege carrega o peso
   sozinho — a trava de 5 tentativas em 15 min, o prazo de 2 h da senha temporária e a revogação
   de sessões na troca. **Nenhum deles tem rede por baixo**, então afrouxar qualquer um é decisão
   de segurança, não de conveniência.

   > **DOIS FORAM AFROUXADOS em 25/09/2026, por decisão do dono — e este parágrafo é o padrão que
   > ele mesmo pré-registrou, então a mudança fica escrita aqui em vez de apagar a frase.**
   > A lista acima tinha um quarto item, *"o bloqueio até a pessoa definir a própria (D31)"*, que
   > valeu de 18/09 a 25/09: quem devia a troca levava 403 em toda rota de dados. **A troca voltou
   > a ser RECOMENDADA** — `/api/me` devolve `deve_trocar` e a SPA abre o modal, que tem "Agora
   > não". E o **piso de senha caiu de 12 para 8 caracteres**.
   >
   > O que isso custa, dito sem suavizar: quem recebe a senha inicial **compartilhada** pode ficar
   > nela indefinidamente, e era essa janela que o bloqueio fechava no primeiro acesso. Com um
   > fator só, o que restou segurando a senha são os **três** itens acima — a trava de tentativas
   > é a que mais pesa agora, porque é a única que limita VOLUME.
   >
   > O 8 continua sendo o piso do próprio NIST SP 800-63B para senha escolhida por pessoa, então a
   > política não saiu da referência que a justifica; o que encurtou foi a folga. Quem for mexer
   > de novo em `MINIMO_DE_CARACTERES`, em `MAX_TENTATIVAS` ou em `JANELA_TENTATIVAS_MIN` precisa
   > ler este bloco antes: depois destas duas mudanças, elas deixaram de ser independentes.

   Custo operacional evitado, e que pesou: cadastrar TOTP exige as pessoas presentes, uma a uma
   (`infra_producao.md:1026`), e perder o celular viraria um SEGUNDO caminho de recuperação, com
   toda a discussão da decisão 4 repetida.
4. **Recuperação de senha** — hoje não existe caminho nenhum: quem esquece depende de um admin
   redefinir pela tela. Autoatendimento exige e-mail, que o piloto não envia.
5. **A borda.** O Caddy deixa de fazer *forward-auth*; o que fica no lugar (e o que acontece com os
   headers `Remote-*` que o RBAC lê hoje) é decisão de infraestrutura, com execução na VPS sob o §6.

## 8. O que este documento não é

Não é cronograma, não escolhe biblioteca e não desenha telas. E não substitui o P19 no
`banco-de-reservas`, que continua sendo onde a **decisão** mora — aqui está o **terreno** dela.
