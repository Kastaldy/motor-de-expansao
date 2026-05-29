# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Builder — porém a EXECUÇÃO não pode ser delegada a subagente isolado.
Para criticidade baixa a esteira nominal é Block Orchestrator → Builder, MAS os passos
efetivos deste bloco (git push outward-facing + comandos no VPS) DEVEM ser conduzidos
pelo orquestrador no loop principal, interativamente, com confirmação humana comando a
comando. Justificativa: CLAUDE.md §6 (GUARDRAIL ABSOLUTO — nenhum comando no VPS sem
confirmação explícita por comando) + o push é ação outward-facing (publica no GitHub).

## Bloco refinado
BLK-OPS-07 — Sincronizar VPS 100% com o `main` local (git push + pull).
Fechar a sincronização deixada parcialmente pendente pelo BLK-OPS-06. O VPS
(`/opt/motor-expansao/app`) ficou em `8218f38` no fechamento do BLK-OPS-06; o `main`
local e o `origin/main` hoje estão ambos em `76fc89e`. Falta apenas levar o checkout do
VPS de `8218f38` → `76fc89e` via `git pull --ff-only`.

## Achado de pré-execução (read-only, JÁ confirmado pelo orquestrador — NÃO re-executar)
- `git fetch origin` já foi rodado: `origin/main` HEAD == `main` HEAD == `76fc89e`;
  ahead/behind = `0 0`.
- **Consequência: o `git push origin main` (passo 1 do backlog) é NO-OP** — o GitHub já
  tem tudo até `76fc89e` (FU4 `97195e3`, BLK-OPS-05, BLK-OPS-06 `f36adfe`,
  BLK-PRD-01 `3d1ca1a`/`76fc89e`). O push pode ser PULADO; se rodado, é confirmação
  inócua ("Everything up-to-date"). A decisão de pular deve ser confirmada com o humano.
- Trabalho remanescente REAL = só o lado VPS: `git pull --ff-only` para `8218f38 → 76fc89e`.

## Objetivo
Deixar o checkout do VPS (`/opt/motor-expansao/app`) refletindo 100% o `main`/`origin/main`
em `76fc89e`, via `git pull --ff-only`, sem rebuild de containers.

## Escopo permitido
- (Opcional/confirmação) `git push origin main` da máquina local — esperado NO-OP.
- Comandos READ-ONLY no VPS para diagnóstico antes do pull (status, rev-parse HEAD, fetch --dry-run).
- `git -C /opt/motor-expansao/app pull --ff-only` no VPS (fast-forward; abortar se não for FF).
- Verificação pós-pull no VPS (rev-parse HEAD, status -s).
- Commit de controle no fechamento (apenas arquivos de controle, por path).

## Fora de escopo
- Qualquer alteração de código, `config.py`, score, carteira, plano, artefatos oficiais do M1.
- Qualquer edição em `CLAUDE.md` ou `PRD.md`.
- Rebuild/restart de Docker (`docker compose build/up`) — a mudança é só de arquivos
  versionados, nenhuma imagem/serviço muda.
- Encadear comandos no VPS sem aprovação intermediária.
- `git pull` com merge/rebase (apenas `--ff-only`).
- Reescrever/mover blocos do backlog.

## Arquivos que devem ser lidos
- `CLAUDE.md` (§6 guardrails de VPS).
- `tasks/current_task.md`.
- `tasks/backlog.md` (bloco BLK-OPS-07 e antecedente BLK-OPS-06).
- `context/handoff.md` (este).

## Arquivos que podem ser alterados (somente no fechamento, por path)
- `tasks/current_task.md`
- `tasks/completed.md`
- `tasks/backlog.md` (marcar BLK-OPS-07 concluído)
- `context/handoff.md`
- `context/handoff/` (snapshots append-only)

## Sequência exata de comandos sugerida (todos com gate humano por comando — §6)
0. (local, opcional/confirmação) `git push origin main` — esperado "Everything up-to-date"
   (NO-OP). Confirmar com o humano se vai rodar ou pular.
1. (VPS, read-only) `git -C /opt/motor-expansao/app status`
2. (VPS, read-only) `git -C /opt/motor-expansao/app rev-parse HEAD`  (esperado: `8218f38`)
3. (VPS, read-only) `git -C /opt/motor-expansao/app fetch --dry-run`  (confirmar o range que viria)
4. (VPS) `git -C /opt/motor-expansao/app pull --ff-only`  (aplicar; abortar se não for fast-forward)
5. (VPS, verificação) `git -C /opt/motor-expansao/app rev-parse HEAD`  (esperado: `76fc89e`)
6. (VPS, verificação) `git -C /opt/motor-expansao/app rev-parse origin/main`  (deve == `76fc89e`)
7. (VPS, verificação) `git -C /opt/motor-expansao/app status -s`  (limpo, salvo untracked
   conhecidos: `authelia/`, `Caddyfile.backup.*`, `docker-compose.prod.yml.backup.*`)

## Critérios de aceite (verificáveis)
- VPS `git rev-parse HEAD` == `76fc89e` (== `origin/main`).
- VPS `git status -s` sem mudanças inesperadas (apenas os untracked conhecidos listados acima).
- Pull foi fast-forward (sem merge commit, sem rebase).
- NENHUM rebuild/restart de Docker executado.
- Se o push foi rodado: saída "Everything up-to-date" (confirmando o NO-OP).

## Criticidade classificada
baixa
Razão: não toca `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo,
plano de domínio, nem qualquer artefato oficial do M1 (mantida em baixa pela ausência de
gatilho de elevação do prompt do Block Orchestrator). É operação de sincronização git.
O guardrail de execução (gate humano por comando no VPS) é tratado pela esteira, não eleva
a criticidade do bloco em si.

## Esteira recomendada
Block Orchestrator → Builder (execução conduzida pelo orquestrador no loop principal,
interativa, com confirmação humana comando a comando no VPS; NÃO delegar a subagente isolado).

## Riscos identificados
- O pull no VPS pode não ser fast-forward se o checkout tiver divergido localmente
  (commits/edições no servidor). Mitigação: `--ff-only` aborta com segurança; o passo 1
  (status) e o passo 3 (fetch --dry-run) detectam isso antes.
- Untracked conhecidos no VPS (`authelia/`, `Caddyfile.backup.*`,
  `docker-compose.prod.yml.backup.*`) podem poluir o `status -s`; são esperados e não bloqueiam.
- Risco de execução sem gate humano por comando — proibido por §6; mitigado pela esteira
  (não delegar a subagente; orquestrador conduz no loop principal).
- O push, embora NO-OP, é outward-facing: confirmar a decisão (rodar/pular) com o humano.

## Guardrails ativos (de CLAUDE.md §6)
- MCP `ssh-vps-ultra` conecta em `root@2.25.137.241` (Hostinger KVM4, produção).
- GUARDRAIL ABSOLUTO: nunca executar qualquer comando no servidor via MCP (ou qualquer
  tool SSH) sem confirmação explícita do usuário para CADA comando individual (inclui
  `git pull`, `docker compose`, `chmod`, `rm`, etc.).
- Não encadear múltiplos comandos no servidor sem aprovação intermediária.
- Guardrail M1: visualizações/análise não podem recalcular/alterar score, carteira, plano
  ou artefatos oficiais — não aplicável aqui (nada de código/M1 é tocado), mas reafirmado.
- Nota de orquestração: ciclo operacional; NÃO altera run-cycle/prompts/esteira →
  NÃO dispara dry-run pós-merge.
