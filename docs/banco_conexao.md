# Conexão com o banco PostgreSQL/PostGIS

> Contrato da fundação de acesso ao banco (`src/motor_expansao/db/`). Cobre o **Marco A**
> da inclusão do banco no motor: o motor fala com o banco, e continua funcionando sem ele.
> Autorização e RBAC são o Marco B e **não** estão aqui; a aplicação de migrations ganhou a §8.
>
> **Estado em 24/10/2026:** a produção roda com o banco ligado desde 23/10/2026 — o RBAC do piloto BR
> vem dele, e o §3 diz o que o piloto faz quando ele falha. Depois do corte do P19, o banco deixa de
> ser opcional (§1).
>
> Responsável: Vinícius · Agosto 2026

## 1. O que este marco entrega

Uma porta única do motor para o banco, que existe **antes** do banco existir. Sem a
variável `MOTOR_DATABASE_URL`, nada é tentado e o piloto se comporta exatamente como antes
— é isso que permite a imagem ir para produção antes de haver serviço de banco no compose.

**O mecanismo continua; a premissa mudou.** Desde 23/10/2026 a produção roda com `MOTOR_DATABASE_URL`
preenchida, e esvaziá-la é o interruptor de incidente do `banco_deploy.md` §8. Depois do corte do P19
(`MOTOR_AUTENTICACAO_PROPRIA` ligada), o banco deixa de ser opcional: a sessão vive em tabela, e sem ele
ninguém entra.

Ainda **não** entrega: migrations aplicáveis, seed de RBAC, substituição do
`web/server/acesso.py`, nem qualquer consulta de domínio.

## 2. Divisão de responsabilidades

Decidido em 25/08/2026: **nenhum comando SQL parte do desenvolvimento.** O banco é
provisionado, migrado e carregado por Vinícius; o motor chega pronto para receber, ligado
por variável de ambiente. A verificação das consultas contra dado real também é dele — a
suíte unitária usa dublês e não abre conexão. Desde 24/10/2026 o check `test` tem também um passo com
PostGIS de verdade, num banco **vazio**: migrations do zero e o login de ponta a ponta
(`banco_deploy.md` §1.5).

## 3. Os três estados

O diagnóstico separa três situações que dão no mesmo para quem usa a tela e são muito
diferentes para quem opera:

| Estado | Quando | O que o motor faz |
|---|---|---|
| **Não configurado** | `MOTOR_DATABASE_URL` ausente/vazia, **ou** o extra `db` não instalado | Roda como sempre. Nenhuma conexão é tentada. |
| **Configurado, fora do ar** | Env definida, banco não responde | O pool reconecta sozinho em segundo plano; o diagnóstico reporta o erro. |
| **Configurado, no ar** | Tudo certo | Leitura e escrita disponíveis. |

"Sem driver" é deliberadamente um caso de *não configurado*, não um erro: quem roda os
pipelines do M1 não precisa de psycopg, e um `import` desprotegido faria o `app.py` falhar
no boot por uma dependência que aquele caminho não usa.

### Com o RBAC no comando: o que o piloto faz quando o banco falha

Desde 23/10/2026 a produção roda com o banco ligado, e o RBAC do piloto BR vem dele
(`web/server/acesso.py`). O pool tem de 1 a 4 conexões e espera até 5 s por uma; cada consulta tem
`statement_timeout` de 2 s e `lock_timeout` de 1 s (`db/postgres.py`). Quando o RBAC fica sem resposta,
o gate e o `/api/me` aplicam a mesma régua, que separa duas falhas:

| Falha | Gate (rota com capacidade) | `/api/me` |
|---|---|---|
| **Queda provada:** o servidor recusou ou derrubou a conexão (`banco_em_falha()`). Vale até o banco voltar a responder | rota sensível — Visão Executiva e rede, dossiê do imóvel, Viabilidade e painel de Acessos — responde **403** "Acesso indisponível no momento. Tente novamente em instantes."; as demais passam para quem o Authelia autenticou, inclusive quem está desativado no banco | mostra só Mapa e Oportunidades |
| **Sem prova de queda** (`BancoSemProvaDeQueda`): pool saturado, `lock_timeout`, `statement_timeout` ou tempo de conexão esgotado | **503** "Piloto ocupado no momento. Tente novamente em instantes.", com `Retry-After: 2` | o **mesmo 503**, no código desde 24/10/2026 (#463, follow-up A); antes — e na imagem no ar nesse dia (`main` em `84429f3e`), até o deploy que leve a mudança —, ele escondia as abas sensíveis de quem as tem, enquanto o gate respondia 503 |

Só a queda provada degrada porque a degradação **libera** as rotas não sensíveis sem checar permissão —
aceitável com o banco fora, um furo com ele no ar e sob carga. A SPA repete o `/api/me` quando recebe
503 (três tentativas ao todo, com 2 s de espera) e, enquanto não sabe as abas, abre como abriria sem
ele: quem barra continua sendo o gate, rota a rota. O log do RBAC indisponível sai uma vez por
episódio, e não por requisição.

**Depois do corte do P19, banco fora é piloto BR fora:** o `/api/verify` responde 503, o Caddy nega
tudo que não for 2xx, e ninguém entra — nem quem já estava dentro.

## 4. Como ligar e testar localmente

```bash
# 1. instalar o driver (extra proprio; nao entra nas dependencias base)
pip install -e ".[db]"

# 2. apontar para o SEU banco
export MOTOR_DATABASE_URL="postgresql://postgres:SENHA@localhost:5432/teste_banco_v2"

# 3. subir o backend
cd web/server && python -m uvicorn app:app --port 8899   # sem MOTOR_DATA_DIR: perfil BR versionado e o data/ do repo (DEC-047); com ela, a subida exige <dir>/perfil.json e, desde 21/10/2026, os insumos da renda com o carimbo k
```

No Windows/PowerShell, o passo 2 é `$env:MOTOR_DATABASE_URL = "postgresql://..."`.

**Conferir:**

```bash
curl -H "Remote-User: <usuario da allowlist>" \
     http://127.0.0.1:8899/api/acessos/saude-artefatos
```

O bloco `banco` da resposta traz `configurado`, `conectado`, `servidor`, `postgis`,
`migracao` e `erro`.

> `migracao` fica `null` enquanto a tabela de controle não existir — que é o estado de um
> banco levantado à mão pelo roteiro `001→010` do `banco-de-reservas`. Não é falha: é a
> falta de registro no runner (a F1.2 existe desde 01/09/2026: `db registrar`/`db aplicar`, §8).

**A segunda metade do teste importa tanto quanto a primeira:** subir **sem**
`MOTOR_DATABASE_URL` e confirmar que tudo funciona como antes. É o que prova que a imagem
pode ir para produção antes do banco. Vale enquanto `MOTOR_AUTENTICACAO_PROPRIA` estiver desligada:
com ela ligada, sem banco ninguém entra (§1).

## 5. Onde o diagnóstico mora, e por que não no `/api/health`

O `/api/health` é rota **livre** e foi emudecido de propósito pelo pentest Onda B #8 — o
inventário que ele servia vazava caminhos absolutos e a descrição de cada artefato. Versão
de servidor, versão de PostGIS e estado de migration são exatamente o mesmo tipo de
reconhecimento, então o bloco `banco` entra em `/api/acessos/saude-artefatos`, que já nasce
atrás do 404 fail-closed do middleware e da allowlist de admin.

Há uma segunda razão, operacional: **o healthcheck do container não pode depender do
banco.** O piloto foi desenhado para servir sem ele; amarrar os dois faria o Docker
reiniciar o `web` a cada piscada do Postgres, derrubando tudo que ainda funcionava.

**Com o banco no comando, a própria rota de diagnóstico depende dele.** `/api/acessos/` exige a
capacidade `acesso.painel_ver`, que é sensível: com o banco fora a rota responde 403, e com ele só
ocupado, 503 (§3) — justamente quando se queria o bloco `banco`. Nessa hora o diagnóstico é pela VPS:
`docker compose -f docker-compose.prod.yml ps postgres`, `... logs --tail 50 postgres` e, no log do
`web`, as linhas `RBAC indisponivel` (banco fora) ou `o RBAC nao respondeu` (banco ocupado; ela sai
do `/api/me`, porque o 503 do gate não tem linha própria).

## 6. Duas portas, e a diferença é imposta pelo banco

```python
from motor_expansao import db

with db.conexao() as con:                      # LEITURA
    linhas = con.execute(SQL).fetchall()

with db.transacao(id_usuario=42) as con:       # ESCRITA
    con.execute(SQL, parametros)
```

**`conexao()` abre a transação com `SET TRANSACTION READ ONLY`.** Não é convenção: o
servidor recusa qualquer escrita ali dentro. Isso importa porque o guardrail que hoje prova
o read-only do piloto (`test_leituras_nao_mutam_artefatos`) funciona por *snapshot do
filesystem* — e um `INSERT` não aparece em snapshot de arquivo. A proteção definitiva é o
papel `app` do **D20**, de pé na produção desde 17/10/2026; antes dele era o `READ ONLY` que cobria o
caminho de leitura, e ele continua lá.

**`transacao()` exige `id_usuario`** e emite `set_config('app.id_usuario', ..., true)` como
primeiro comando. É o insumo das triggers de auditoria do **D19**: sem ele, toda concessão
e revogação de permissão nasce com `registrado_por` nulo — exatamente o dado pelo qual a
auditoria existe. O valor pode ser `None` (ação de sistema, prevista pelo D19), mas o
parâmetro é obrigatório: autor nulo por decisão é legítimo, por esquecimento não.

> **Por que `set_config` e não `SET LOCAL`.** `SET LOCAL app.id_usuario = %s` não aceita
> placeholder, o que forçaria interpolar o valor na string — injeção esperando acontecer. O
> `set_config(..., true)` aceita bind, e o `true` mantém a variável **local à transação**:
> ela morre no commit em vez de vazar para a próxima requisição que pegar aquela conexão do
> pool.

## 7. Convenções adotadas

- **psycopg 3 síncrono, sem ORM.** As rotas do piloto são `def`, não `async def`; um pool
  síncrono encaixa sem reescrever rota. Sem ORM porque o esquema é SQL escrito à mão, com
  triggers `SECURITY DEFINER` e índices parciais que um ORM não expressa e que já foram
  validados em cluster real.
- **Todo SQL fica localizável** — em constantes nomeadas no módulo, nunca interpolado no
  meio da lógica. Quem executa contra o banco real precisa ter o que revisar num lugar só, e
  é o que permite o gate de sintaxe offline alcançar tudo.
- **O submódulo se chama `postgres.py`, não `conexao.py`**, porque `conexao` é o nome da
  função pública: um submódulo homônimo seria sombreado por ela no namespace do pacote.

## 8. Aplicar e conferir migrations

```bash
python -m motor_expansao.db estado      # o que já foi aplicado, o que falta
python -m motor_expansao.db aplicar     # aplica as pendentes, em ordem, registrando
python -m motor_expansao.db registrar --ate 011   # registra sem executar (ver abaixo)
python -m motor_expansao.db conferir    # o banco tem o que o motor espera?
```

> **Rodando de um worktree.** Se você está num worktree (`.claude/worktrees/…`) e o pacote
> `motor_expansao` do seu ambiente foi instalado a partir do checkout principal, o
> `python -m motor_expansao.db` acha a versão instalada — a do checkout principal, que tem este subpacote desde 01/09/2026 — e roda AQUELE código sem aviso; antes disso falhava com
> `No module named motor_expansao.db`. Aponte o `src` do worktree para o path, sem reinstalar nada:
>
> ```powershell
> cd <...>\motor-de-expansao\.claude\worktrees\wt-db
> $env:PYTHONPATH = "src"
> ```
>
> **Não** rode `pip install -e .` a partir do worktree: isso repontaria o pacote instalado e
> afetaria o trabalho no checkout principal — exatamente o que o ambiente isolado evita. O
> `PYTHONPATH` vale só para a sessão do terminal.

**A credencial não é a do piloto.** Aplicar migration é DDL, e o **D20** tira DDL do papel `app`
justamente para que a aplicação não possa desligar a própria trigger de auditoria. A ferramenta lê
`MOTOR_DATABASE_URL_ADMIN` primeiro e só cai para `MOTOR_DATABASE_URL` quando aquela não existe — o
que é o caso do banco de teste local, onde os dois papéis são a mesma pessoa. Em produção, usar a
mesma URL nas duas anula o D20 em silêncio, e quem denuncia é o `privilegios`, que conecta pela
`MOTOR_DATABASE_URL` — o `conferir`, que conecta como dono, passa verde.

**`registrar` existe para o cluster que já rodou o roteiro à mão.** Ele não executa nada: preenche
`migracoes_aplicadas` com as versões cujo efeito já está no banco, usando os hashes do manifesto. É
o caminho para um cluster levantado por `001→010` no pgAdmin entrar no controle de versão sem
reprocessar. A `000` é a única que precisa ir à mão antes — ela cria o próprio registro.

**`conferir` lê catálogo, nunca dado.** Ele checa as extensões, os seis números da §0 da
`verificacao.md`, o `security_definer` e o `search_path` das oito funções (D19/D21/D29), o que está
registrado como aplicado, e o estado do provisionamento — desde o #447, trigger de auditoria fora de
`'A'` reprova. Devolve código 1 se houver qualquer divergência (e lista todas), então serve como passo
de deploy. **Não** confere se os papéis existem, coluna comum, a versão do servidor ou do PostGIS (só a
presença das extensões) nem privilégio de banco: esse é o `privilegios` (`banco_deploy.md` §8).

> **Uma migration editada depois de aplicada é denunciada.** O hash registrado no banco deixa de
> bater com o do arquivo, e as três subcomandos avisam. A `convencoes.md` §7 proíbe isso por prosa;
> aqui vira sinal — o banco fica num estado que nenhum arquivo descreve, e a correção é uma migration
> nova, nunca editar a antiga.

**Mudança no pacote `db/` — migration incluída — é PR CRÍTICO no guard** (`critica-aprovada`;
`banco_deploy.md` §9.0), e o check `test` aplica a cadeia do zero num PostGIS de verdade em todo PR para
a `main` (`banco_deploy.md` §1.5).

## 9. Próximo passo — entregue em setembro de 2026 (subida no `docs/banco_deploy.md`)

O Marco B — migrations aplicáveis, script de conferência, seed dos quatro perfis e
substituição do `acesso.py` pelo RBAC. Detalhe e dependências no plano de inclusão.
