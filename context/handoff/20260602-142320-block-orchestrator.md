# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-ORQ-01 — Otimização de tempo de execução do /run-cycle (Fase 1 / Tier 1).**
Reduzir o tempo de relógio da esteira `/run-cycle` atacando APENAS os três gargalos de
ganho-alto/risco-mínimo do Tier 1, sem tocar M1/score/artefatos oficiais e sem enfraquecer
nenhum guardrail de processo. Os três itens em escopo:
1. **Eliminar a leitura dupla de contexto:** o orquestrador (`run-cycle.md`, Passo 4) passa
   CAMINHOS dos arquivos ao sub-agente, NÃO o conteúdo embutido; o sub-agente lê os arquivos
   por conta própria via Read. Remover a redundância correspondente nos `prompts/*.md` (cada um
   já manda "Leia CLAUDE.md completo"). Isolamento de contexto e os handoffs versionados
   permanecem intactos.
2. **Instalar `pytest-xdist`** como dependência `[dev]` no `pyproject.toml` e passar a rodar
   `pytest -n auto` no Builder e no QA. Cobertura/contagem de testes inalterada.
3. **Suíte full uma única vez por ciclo (no gate do QA):** o Builder valida com o subconjunto de
   testes impactado + smoke import (`python -c "import streamlit_app"`); a suíte completa
   (`pytest -n auto`) roda 1× no QA, não em ambos.

## Objetivo
Cortar o tempo de relógio do `/run-cycle` (alvo: redução ≥30% no overhead de orquestração de um
ciclo média) preservando integralmente qualidade de entrega, cobertura de testes e os
handoffs/guardrails de processo.

## Escopo permitido
- **Passo 4 do `run-cycle.md`:** trocar "orquestrador embute conteúdo dos arquivos no prompt do
  sub-agente" por "orquestrador passa a LISTA DE CAMINHOS; o sub-agente lê". Manter "Contexto
  isolado por Skill" (a lista de arquivos por papel continua) e todo o bloco de "Handoff
  versionado (append-only)".
- **`prompts/block_orchestrator.md`, `prompts/planner.md`, `prompts/builder.md`,
  `prompts/qa_analyzer.md`:** ajustar a seção "Leitura obrigatória" de cada um para deixar
  explícito que o sub-agente lê os arquivos a partir dos CAMINHOS recebidos (responsabilidade
  única de leitura no sub-agente), removendo a duplicação que pressupunha conteúdo embutido pelo
  orquestrador. Não alterar objetivo, guardrails nem formato de saída desses prompts.
- **`prompts/builder.md` — seção "Validação obrigatória":** permitir validação por subconjunto
  impactado + smoke import em vez de suíte full; usar `pytest -n auto` quando rodar testes.
  NÃO remover o smoke `import streamlit_app` nem a regra de registrar o resultado completo no
  handoff.
- **`prompts/qa_analyzer.md` — re-execução obrigatória:** a suíte completa roda 1× aqui, com
  `pytest -n auto`. Preservar INTEGRALMENTE a maquinaria NO-BYPASS (re-execução por conta
  própria, proibição de `--config /dev/null`/fixture-fora-do-caminho-real/mock do caminho
  crítico, episódio dos 5 defeitos do BLK-OPS-01, housekeeping `--check`).
- **`pyproject.toml`:** adicionar `pytest-xdist` (com bound de versão coerente com o estilo do
  arquivo) ao array `dev` de `[project.optional-dependencies]`. Nada mais.
- **`tasks/current_task.md`:** atualizar campos de andamento/próxima Skill (já feito por este
  handoff).
- **`tasks/backlog.md` + `tasks/completed.md`:** SOMENTE no fechamento (Passo 6.0) via
  `scripts/housekeeping_move_block.py` — nunca à mão.
- **`context/handoff.md` + `context/handoff/`:** handoffs do ciclo.
- **CLAUDE.md §5:** nota curta de fechamento SE a baseline/fluxo de validação mudar (decisão do
  Builder/QA no fechamento; não obrigatório no plano).

## Fora de escopo
- **TODO o Tier 2 e Tier 3** (promover a blocos próprios depois de medir a Fase 1):
  - (T2) Escopar a re-validação anti-bypass do QA por perfil de ciclo (`tooling/infra` vs `código`).
  - (T2) Tiering de modelo (agentes mecânicos em modelo rápido).
  - (T2) Fundir Block Orchestrator + Planner em baixa/média.
  - (T3) Enxugar `prompts/qa_analyzer.md` (mover narrativa do BLK-OPS-01 para `docs/`);
    arquivar snapshots antigos de `context/handoff/`.
- Qualquer alteração em M1 / `score_priorizacao` / `hex_score_estrutural` / carteira / plano
  curto prazo / plano de domínio / artefatos oficiais do M1.
- Remover ou enfraquecer QUALQUER guardrail de processo (lista em "Guardrails ativos").
- Reduzir cobertura de teste ou qualidade da documentação/handoffs.
- Alterar o CI (`.github/workflows/ci.yml`) — ele continua `python -m pytest -q` serial. Levar
  `pytest-xdist` ao CI NÃO faz parte da Fase 1 (ver Riscos). Tocar o CI seria expansão de escopo.
- `.codex/skills/codex-run-cycle/SKILL.md` — Codex foi descontinuado (MEMORY: Codex descontinuado);
  não manter paridade. Citado no Passo 6.c do `run-cycle.md` apenas como gatilho histórico.
- BLK-ORQ-02 (Fase 2 / estrutura) — bloco separado, depende deste.

## Arquivos que devem ser lidos
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/CLAUDE.md`
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/tasks/current_task.md`
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/tasks/backlog.md` (bloco BLK-ORQ-01, ~linha 345)
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/.claude/commands/run-cycle.md`
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/prompts/block_orchestrator.md`
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/prompts/planner.md`
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/prompts/builder.md`
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/prompts/qa_analyzer.md`
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/pyproject.toml`
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/context/handoff/README.md`
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/.github/workflows/ci.yml` (apenas para entender a paridade CI; NÃO alterar)

## Arquivos que podem ser alterados
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/.claude/commands/run-cycle.md` (Passo 4)
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/prompts/block_orchestrator.md` (Leitura obrigatória)
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/prompts/planner.md` (Leitura obrigatória)
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/prompts/builder.md` (Leitura obrigatória + Validação obrigatória)
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/prompts/qa_analyzer.md` (Leitura obrigatória + comando de suíte → `-n auto`)
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/pyproject.toml` (array `dev` em `[project.optional-dependencies]`)
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/tasks/current_task.md`
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/tasks/backlog.md` (SOMENTE via helper de housekeeping no fechamento)
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/tasks/completed.md` (SOMENTE via helper de housekeeping no fechamento)
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/context/handoff.md`
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/context/handoff/` (snapshots novos)
- `c:/Users/Felipe Silva/Downloads/motor-de-expansao/motor-de-expansao/CLAUDE.md` (§5 — nota curta opcional no fechamento, somente se baseline/fluxo mudar)

## Critérios de aceite
- Passo 4 do `run-cycle.md` instrui o orquestrador a passar CAMINHOS (não conteúdo); os 4
  `prompts/*.md` deixam claro que o sub-agente lê os arquivos pelos caminhos — sem perda de
  isolamento de contexto e com os handoffs versionados intactos.
- `pytest-xdist` presente no array `dev` do `pyproject.toml`; `pytest -n auto` roda verde com a
  MESMA contagem de testes (sem perda de cobertura). Baseline de contagem a confirmar pelo
  Builder/QA no ambiente (CLAUDE.md §5 cita `532 passed, 1 skipped`; o diagnóstico do bloco cita
  651 testes — divergência de ambiente/momento a registrar no ciclo, não a "corrigir").
- Builder valida com subconjunto impactado + smoke `import streamlit_app`; suíte full executada
  ≥1× no gate do QA (e não em ambos).
- Handoffs versionados append-only, NO-BYPASS, commit por path, rollback não-destrutivo,
  dry-run autônomo de orquestração e housekeeping via helper PRESERVADOS e demonstrados.
- **Dry-run autônomo pós-merge (Passo 6.c) EXECUTADO e reportado** — este ciclo altera a
  orquestração (`run-cycle.md` + `prompts/*`).
- Documentação coerente (`run-cycle.md`/`prompts/*` sem contradição interna após o ajuste); nota
  no CLAUDE.md §5 se a baseline/fluxo de validação mudar.
- Tempo de relógio do ciclo de referência registrado antes/depois (medir com o MESMO ciclo para
  não concluir por ruído).

## Criticidade classificada
**Alta** — CONFIRMADA. Justificativa: o bloco altera a própria orquestração
(`.claude/commands/run-cycle.md` + `prompts/*.md`), o que dispara o dry-run autônomo obrigatório
do Passo 6.c e exige aprovação humana antes do Builder. NÃO toca `score_priorizacao`,
`hex_score_estrutural`, pesos, carteira, plano nem qualquer artefato oficial do M1 — portanto NÃO
é Crítica pela regra do M1. Permanece Alta (não rebaixar) por mexer no processo que governa todos
os ciclos futuros.

## Esteira recomendada
Block Orchestrator → Planner → **[APROVAÇÃO HUMANA OBRIGATÓRIA]** → Builder → QA → fechamento
(housekeeping via helper → commit por path → merge humano → **dry-run autônomo Passo 6.c**).

## Riscos identificados
- **Médio — mexe no processo, não no produto.** Mitigação: faseamento (só Tier 1), dry-run de
  orquestração obrigatório e nenhuma remoção de guardrail.
- **Paridade CI vs local com `pytest-xdist`:** o CI roda `python -m pytest -q` SERIAL (linha 45 de
  `.github/workflows/ci.yml`). Adicionar `pytest-xdist` ao `[dev]` é seguro (o CI instala `.[dev]`
  mas não usa `-n auto`); porém isso cria assimetria local(paralelo)/CI(serial). Risco real:
  teste com dependência de ordem/estado compartilhado pode passar serial e falhar em paralelo (ou
  vice-versa). Mitigação: o Builder/QA deve confirmar `pytest -n auto` verde com a MESMA contagem;
  se houver flakiness por paralelismo, é sinal de teste mal-isolado a tratar — NÃO mascarar com
  `-p no:xdist`. Levar `-n auto` ao CI fica FORA do escopo (Tier 2/bloco próprio).
- **Redução do escopo de validação do Builder pode mascarar regressão** se o "subconjunto
  impactado" for mal escolhido. Mitigação: smoke `import streamlit_app` mantido SEMPRE + suíte
  full no QA como rede de segurança; o Builder registra quais testes rodou e por quê.
- **Divergência na contagem de testes** entre o que o diagnóstico cita (651) e o baseline do
  CLAUDE.md (532 passed, 1 skipped) e o CI (3.11, só `.[dev]`). Não é defeito a corrigir; o ciclo
  deve apenas registrar a contagem observada no ambiente e garantir que `-n auto` não a altera.
- **Recursão do dry-run:** o Passo 6.c dispara um dry-run autônomo; o guard de recursão (prof. 1,
  via `dry_run: true` no `current_task.md`) deve estar respeitado para não reentrar.
- **Não confundir "passar caminho" com "perder isolamento":** o sub-agente continua recebendo
  APENAS os arquivos da sua Skill (a lista por papel do "Contexto isolado por Skill" permanece);
  muda só QUEM faz a leitura (sub-agente, não orquestrador).

## Guardrails ativos
- **Score/M1 intocados (do CLAUDE.md):** visualizações, análises e qualquer mudança não podem
  recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo,
  plano de domínio ou artefatos oficiais do M1 sem aprovação explícita. Esta tarefa NÃO toca nada
  disso.
- **Parâmetros canônicos imutáveis:** `H3_RESOLUTION=7`, `DIST_MIN_ULTRA_KM=1.0`,
  `RENDA_MIN=4500.0`, pesos `renda=0.40`/`pop=0.60` (DEC-001). Inalterados.
- **Handoff versionado append-only:** cada Skill grava `context/handoff.md` (corrente) +
  `context/handoff/AAAAMMDD-HHMMSS-<slug>.md` (snapshot, com segundos); nunca editar snapshots
  existentes. PRESERVAR.
- **NO-BYPASS de validação:** nenhum veredito de QA pode se basear em "verde" obtido contornando
  config/artefatos reais (`--config /dev/null`, fixture fora do caminho real, mock do caminho
  crítico). PRESERVAR integralmente (episódio dos 5 defeitos do BLK-OPS-01).
- **Branch/commit isolado por path:** branch `ciclo/BLK-ORQ-01`; commitar SÓ os paths do ciclo
  (`git add <paths>`), nunca `git add -A`/`git add .`; nunca arrastar `PRD.md` ou edições não
  relacionadas. PRESERVAR.
- **Rollback não-destrutivo:** preferir `git switch`/`git restore --staged`; `git reset --hard`/
  `git branch -D` só com confirmação humana e nunca alcançando edições não relacionadas. PRESERVAR.
- **Dry-run autônomo de orquestração (Passo 6.c):** este ciclo altera a orquestração → dispara
  dry-run autônomo após o merge humano (tarefa dummy Baixa + `dry_run: true`, guard de recursão
  prof. 1). OBRIGATÓRIO.
- **Housekeeping via helper (Passo 6.0):** mover o bloco BLK-ORQ-01 de `backlog.md` para
  `completed.md` SOMENTE via `scripts/housekeeping_move_block.py` no fechamento; QA exige
  `--check` verde antes do veredito. PRESERVAR.
- **Aprovação humana obrigatória antes do Builder** (criticidade Alta). PARAR após o Planner.
- **Sem dependência de API ao vivo no dashboard de produção.** Não aplicável a esta tarefa, mas
  ativo.
