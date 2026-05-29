# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Execução conduzida pelo ORQUESTRADOR (main loop / run-cycle) diretamente no VPS, comando-a-comando com aprovação explícita do usuário (GUARDRAIL §6) — NÃO delegar a um sub-agente Builder autônomo. Em seguida: Fechamento.

## Bloco refinado
BLK-OPS-06 — Alinhar checkout do VPS via `git pull --ff-only`

## Objetivo
Trazer o checkout git de `/opt/motor-expansao/app` no VPS de produção para `origin/main` via fast-forward, materializando os 5 `secrets/*.enc.*` como arquivos rastreados e eliminando o estado "atrás do origin".

## Escopo permitido
- Conduzir, comando-a-comando e com aprovação explícita do usuário (§6), a sequência VPS abaixo via MCP `ssh-vps-ultra`.
- Sequência EXATA (4 passos):
  1. READ-ONLY: `git -C /opt/motor-expansao/app status`
  1b. READ-ONLY: `git -C /opt/motor-expansao/app rev-parse HEAD`
  2. READ-ONLY: `git -C /opt/motor-expansao/app fetch --dry-run`
  3. ESCRITA (único comando que escreve): `git -C /opt/motor-expansao/app pull --ff-only` — abortar se não for fast-forward.
  4. VERIFICAÇÃO (read-only): confirmar `secrets/*.enc.*` presentes e tracked (`git -C /opt/motor-expansao/app ls-files secrets/`) e que `git -C /opt/motor-expansao/app rev-parse HEAD` == `origin/main`.
- Atualizar artefatos de controle no fechamento (tasks/completed.md, current_task.md, backlog.md, context/).

## Fora de escopo
- Qualquer comando no VPS sem aprovação individual do usuário (§6).
- `git reset`, `git merge` não-ff, `git checkout --force`, stash, descarte de untracked — se o pull NÃO for fast-forward, ABORTAR e reportar; não forçar.
- `docker compose` rebuild/restart — NÃO é necessário (só materialização de arquivos `.enc.*` rastreados; nenhuma imagem/serviço muda).
- Encriptar/desencriptar segredos, tocar chave age, ou ler conteúdo de `.enc.*`.
- `git push` do main local (ahead 3 do origin) — pré-requisito OPCIONAL e separado; NÃO necessário para os `.enc.*` (já no origin via `a2a4cea`). Não executar neste bloco salvo decisão explícita.
- score_priorizacao / hex_score_estrutural / carteira / plano / artefatos M1 — intocados.

## Arquivos que devem ser lidos
- CLAUDE.md (§6 — guardrail VPS absoluto)
- tasks/current_task.md
- tasks/backlog.md (entrada BLK-OPS-06)
- context/handoff.md (este)

## Arquivos que podem ser alterados
- tasks/current_task.md, tasks/completed.md, tasks/backlog.md (controle, no fechamento)
- context/handoff.md, context/handoff/ (snapshots)
- NENHUM arquivo de código local, config.py, data/ ou artefato M1.
- ATENÇÃO: `tasks/backlog.md` tem 92 linhas de edição pré-existente NÃO relacionada (migração de blocos) e `PRD.md` (M) é alheio ao ciclo — NÃO arrastar ao commit por path do fechamento.

## Critérios de aceite
- Passos 1, 1b, 2 executados como read-only, cada um aprovado individualmente.
- Passo 3 (`pull --ff-only`) executado SOMENTE após aprovação; resultado é fast-forward limpo (sem conflito, sem merge commit). Se não for ff: abortado e reportado, sem forçar.
- Pós-pull: `git rev-parse HEAD` no VPS == `origin/main` (deve conter o commit `a2a4cea`).
- `git ls-files secrets/` no VPS lista os 5 `.enc.*` (env.enc.env, Caddyfile.enc, authelia.configuration.enc.yaml, authelia.users_database.enc.yaml, authelia.db.sqlite3.enc) como tracked.
- Nenhum rebuild/restart de docker realizado nem necessário.
- Nenhum segredo em texto puro exposto; chave age privada nunca tocou o VPS.

## Criticidade classificada
BAIXA. Operação de git read-mostly (1 único comando de escrita, fast-forward) que apenas materializa arquivos `.enc.*` já versionados no origin. NÃO toca score_priorizacao, hex_score_estrutural, carteira, plano nem artefatos oficiais do M1 → não se enquadra em CRÍTICA. Risco operacional contido pela cláusula `--ff-only` e pela aprovação comando-a-comando do §6.

## Esteira recomendada
Block Orchestrator (este handoff) → execução VPS conduzida pelo ORQUESTRADOR (main loop) diretamente, comando-a-comando sob §6 (NÃO Builder autônomo) → Fechamento (atualizar tasks/, registrar em completed.md, commit por path do controle do ciclo).

## Riscos identificados
- Pull não fast-forward (checkout do VPS divergiu localmente / tem commits ou alterações locais não esperadas): `--ff-only` aborta automaticamente — reportar e NÃO forçar; reavaliar com o usuário.
- Arquivos `.enc.*` que no FU5 estavam untracked e foram removidos via `rm`: ao puxar, vêm como tracked do origin; se houver resíduo untracked com mesmo nome no working tree, o pull pode reclamar de overwrite — nesse caso ABORTAR e reportar (não `rm`/`checkout --force` sem aprovação).
- `.gitattributes` marca `.enc.*` como `binary` (evita conversão CRLF) — checkout no Linux do VPS é seguro; só registrar.
- Conectividade/permissão SSH MCP — fora do controle do bloco; se falhar, reportar.

## Guardrails ativos
- GUARDRAIL ABSOLUTO §6: nenhum comando no VPS sem confirmação explícita do usuário, comando a comando; não encadear comandos sem aprovação intermediária.
- Block Orchestrator NÃO executa nada no VPS — apenas refina, classifica e produz handoff.
- Guardrail permanente M1: nenhuma alteração de score_priorizacao/hex_score_estrutural/carteira/plano/artefatos oficiais (não aplicável aqui — não tocados).
- Um bloco por vez; sem expansão de escopo.
