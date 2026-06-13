# Loop autônomo (ralph) — Motor de Expansão

Deixa o Claude trabalhar **100% autônomo** os blocos **`loop-safe`** do `tasks/backlog.md`, dentro de
um **container Docker isolado**, enquanto você faz outras coisas. O loop entrega um **branch** para
você revisar — **nunca** faz merge, push nem deploy, e **nunca** toca o M1, a VPS ou segredos.

> Padrão "ralph": rodar o agente num laço sobre o mesmo prompt até terminar. Aqui é domado por
> guardrails: container sem credencial, testes como gate, e um **guard automático** que substitui o
> gate humano dos blocos Alta.

## ⚡ Início rápido (1 clique)
**Uma vez:** abra o Docker Desktop e adicione ao `.env` da raiz a linha
`CLAUDE_CODE_OAUTH_TOKEN=<token>` (gere com `claude setup-token`).

**Depois, sempre que quiser rodar:** dê **duplo-clique em `iniciar-loop.cmd`** (na raiz do projeto).
Ou, no terminal, qualquer um destes:
```powershell
.\iniciar-loop.cmd
# ou
powershell -ExecutionPolicy Bypass -File scripts\iniciar_loop.ps1
```
O lançador faz tudo sozinho: confere o Docker, lê **só o token** do `.env`, **cria um branch de
trabalho** se você estiver na `main`, **builda a imagem** na primeira vez, **mascara o `.env`** dentro
do container (as credenciais Growth/UX **nunca entram** — fica credential-free) e **roda o loop**. Ao
terminar, ele te diz o branch e como revisar. Para ajustar o nº de iterações: `$env:MAX_ITERS = 20`
antes de rodar (default 10).

> O resto deste documento é a referência detalhada (o que o lançador faz por baixo e como operar manual).

## O que é "loop-safe"
Um bloco do backlog marcado `| **Autonomia** | loop-safe ... |`. Critério: **READ-ONLY sobre o M1**,
**não toca VPS/deploy/segredos**, **não persiste PII**, e **consome `data/staging`** (sem ingestão ao
vivo na Growth API — o container não tem credencial). Hoje: **BLK-DIM-01, -02, -03, -04**
(`BLK-DIM-03` é o melhor para começar: Média, determinístico, sem dependências).

Para tornar um bloco novo elegível: adicione a linha `Autonomia: loop-safe` à tabela dele — isso é a
**pré-aprovação humana** que autoriza o loop a rodá-lo sem o gate interativo.

## As 4 redes de segurança (substituem o humano no loop)
1. **Container sem credencial** — o `run-ralph-loop.sh` **aborta** se achar `VPS_`, `SSH_PRIVATE_KEY`,
   `CLICKUP_WRITE`, `DEPLOY_KEY`, `GROWTH_API_*` no ambiente. Sem chave de VPS → impossível deployar.
2. **Guard de M1/VPS** (`scripts/loop_guard.py`) — após cada iteração, inspeciona o `git diff` do loop
   e **aborta + escreve `RELATORIO-BLOQUEIO.md`** se tocar `config.py`, `pipelines/m1/`, `*scoring*`,
   artefatos M1 (`brasil_*`/`hexagonos_brasil*`), `deploy/`, `Dockerfile.{streamlit,api}`,
   `docker-compose*`, `Caddyfile*`, `authelia/`, `.env*`, `secrets/`, `.github/workflows/`.
3. **Testes = gate** — `ruff check .` + `pytest -q` no QA, **sem bypass**; não avança com teste vermelho.
4. **Sem merge/push/deploy** — o loop só **commita por path** no branch atual. Revisão e merge são seus.

## Pré-requisitos
- **Docker Desktop** na sua máquina Windows (não precisa ser a VPS — é build, não produção).
- **Plano Max basta** — não precisa de API key. O container usa um **token da sua assinatura**.
- **Nada** de chave de VPS / ClickUp-write / `.env` da Growth API no `docker run`.

## 0. (uma vez) Branch de trabalho
O loop commita no branch atual e **nunca** faz merge/push. Crie um branch ANTES de rodar:
```bash
git switch -c ciclo/loop-dim
```

## 1. (uma vez) Token da assinatura + build da imagem
No **host** (onde você já está logado no Claude com o Max), gere um token:
```bash
claude setup-token          # imprime o token; copie (não fica salvo)
```
Build da imagem do loop (o `.dockerignore` já exclui `data/` 2.7G, então o contexto é pequeno):
```bash
docker build -t motor-loop -f Dockerfile.loop .
```

## 2. Disparar o loop autônomo
Monta o repo como volume (o agente escreve SÓ aqui) e passa o **token da assinatura** (não API key).
No PowerShell (Windows), use `${PWD}`:
```powershell
docker run --rm -it `
  -e CLAUDE_CODE_OAUTH_TOKEN="<token-colado>" `
  -e MAX_ITERS=10 `
  -v "${PWD}:/repo" `
  motor-loop
```
No Git Bash / WSL:
```bash
docker run --rm -it \
  -e CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN" \
  -e MAX_ITERS=10 \
  -v "$(pwd)":/repo \
  motor-loop
```
O loop vai: pegar o próximo `BLK-*` **loop-safe**, Planner→Builder→QA, rodar `ruff`/`pytest`, fechar o
bloco com **commit por path**, rodar o **guard de M1/VPS**, e seguir. Para quando todos os loop-safe
passam (cria `LOOP_DONE`) ou trava (3× no mesmo erro, ou guard → `RELATORIO-BLOQUEIO.md`).

> **Cota:** o uso headless (`claude -p`) na assinatura puxa de uma cota mensal separada do uso
> interativo do Max. Um loop longo consome dela. `MAX_ITERS` limita o gasto — comece com **10** e
> acompanhe nas primeiras rodadas. (Os sub-agentes do `/run-cycle` usam Opus no QA — pesado; vigie.)

### Por que os parquets de `data/staging` aparecem dentro do container
São **gitignored** e estão na sua máquina; o `-v "${PWD}:/repo"` os monta. O loop os **lê** para os
blocos de modelagem (DIM-01/03/04) — mas **não** os commita (seguem ignorados).

## 3. Acompanhar
- `git log --oneline` e `git diff main...HEAD` no branch `ciclo/loop-*` — veja o que foi feito.
- `tasks/completed.md` cresce conforme os blocos fecham; `context/handoff/` guarda os snapshots.
- Se aparecer `RELATORIO-BLOQUEIO.md`, o loop travou (erro 3× ou guard) — leia, ajuste e rode de novo.

## 4. Revisar e fechar (passo HUMANO, fora do loop)
1. Revise o branch: `git diff` dos blocos; rode `pytest -q` e `ruff check .` você mesmo.
2. Faça o **merge** na `main` (PR + revisão). O loop nunca faz merge.
3. **Deploy** (se aplicável) é passo humano separado, com credenciais reais, fora do container.

## Limites conhecidos (honestos)
- **Ingestão ao vivo (Growth API) NÃO roda no loop** — o container é credential-free por decisão. Se um
  bloco loop-safe precisar de dados novos, materialize-os antes (passo humano) ou rode o bloco de
  ingestão (Alta, com gate) fora do loop. O `BLK-DIM-00` já materializou a base atual.
- **Blocos que tocam M1/VPS/produção nunca são loop-safe** — por construção, o guard os bloqueia.
- O loop é **otimista**: confia nos testes. Cobertura fraca de teste num bloco = risco. Por isso a
  revisão humana do branch antes do merge continua obrigatória.
