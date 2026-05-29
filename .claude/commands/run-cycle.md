# /run-cycle — Orquestrador Autônomo de Ciclo

Você é o orquestrador autônomo deste projeto. Sua função é executar o ciclo completo
de desenvolvimento spawning sub-agentes especializados com contexto isolado via ferramenta
Agent. O usuário só intervém nas aprovações obrigatórias de tarefas altas e críticas.

## Tarefa recebida

$ARGUMENTS

---

## Passo 0 — Branch do ciclo (git isolado)

Antes de carregar contexto:

1. Capture o estado inicial do git: `git rev-parse --abbrev-ref HEAD` e `git status --porcelain`.
2. Crie/use um branch isolado `ciclo/<ID-do-bloco>` a partir do HEAD atual: `git switch -c ciclo/<ID>` (ou `git switch ciclo/<ID>` se já existir — ciclo re-entrante). NÃO use `git stash` nem `git checkout .` global.
3. **Worktree pré-sujo:** o worktree pode conter edições não relacionadas (ex.: `M PRD.md`). Branch a partir do HEAD atual NÃO toca o working tree, então essas edições permanecem. Regra explícita: commite apenas os arquivos do ciclo por path (`git add <paths-do-ciclo>`), NUNCA `git add -A`/`git add .`. Liste os paths do ciclo no `current_task.md`/handoff.
4. **Ciclo re-entrante:** se a branch `ciclo/<ID>` já existe, retome nela sem recriar; o estado em `context/handoff/` e `context/handoff.md` indica em que Skill o ciclo parou.

---

## Passo 1 — Carregar contexto inicial

Leia os seguintes arquivos:
- `CLAUDE.md` — completo
- `tasks/current_task.md` — verificar se há tarefa ativa
- `tasks/backlog.md` — para localizar ID se a tarefa vier do backlog

Se `current_task.md` tiver tarefa com status diferente de "sem tarefa ativa",
alerte o usuário e aguarde confirmação antes de sobrescrever.

---

## Passo 2 — Classificar criticidade

| Criticidade | Exemplos | Esteira |
|---|---|---|
| Baixa | ajuste textual, bug isolado, doc simples | Block Orchestrator → Builder |
| Média | nova função, melhoria localizada, nova tela | Block Orchestrator → Planner → Builder → QA |
| Alta | nova feature, mudança em pipeline | Block Orchestrator → Planner → [aprovação humana] → Builder → QA |
| Crítica | score, ranking, artefato M1, KPI executivo | Block Orchestrator → Planner → [aprovação humana] → Builder → QA |
| Estratégica | redesenho arquitetural, nova fase | Block Orchestrator → Planner → [aprovação humana] → Builder → QA |

Qualquer menção a `score_priorizacao`, `hex_score_estrutural`, pesos do score ou
artefatos M1 oficiais → classificar como **Crítica** obrigatoriamente.

---

## Passo 3 — Registrar em tasks/current_task.md

Escreva o arquivo com este formato:

```
# Current Task

## Bloco atual

ID: [ID do backlog ou BLK-YYYYMMDD-NN]
Nome: [nome curto]
Status: em execução
Tipo: [feature | bug | performance | manutenção | refatoração | doc | operação]
Criticidade: [baixa | média | alta | crítica | estratégica]
Esteira: [Skills na sequência]
Skill atual: run-cycle
Próxima Skill: Block Orchestrator

## Objetivo
[uma frase do que deve ser entregue]
```

---

## Passo 4 — Executar a esteira com sub-agentes

Para cada Skill da esteira, use a ferramenta **Agent** para spawnar um sub-agente
com contexto isolado. Cada Agent recebe apenas os arquivos que precisa — não o
repositório inteiro.

### Como construir o prompt de cada Agent

Antes de spawnar cada sub-agente:
1. Leia o arquivo de prompt correspondente em `prompts/` (ex: `prompts/block_orchestrator.md`)
2. Leia o `context/handoff.md` atual (se existir)
3. Monte o prompt do Agent incluindo: conteúdo do prompt da Skill + conteúdo dos
   arquivos que ela precisa ler + instrução para escrever `context/handoff.md` ao final

Após cada Agent retornar, leia `context/handoff.md` para identificar a próxima Skill
e qualquer alerta antes de prosseguir.

**Handoff versionado (append-only).** Cada Agent (Block Orchestrator, Planner, Builder **e QA**) grava DUAS cópias com conteúdo idêntico: (1) `context/handoff.md` (corrente) e (2) `context/handoff/AAAAMMDD-HHMMSS-<slug>.md` (snapshot append-only, COM segundos no carimbo; slugs: `block-orchestrator`, `planner`, `builder`, `qa`). Ver a convenção em `context/handoff/README.md`. O orquestrador verifica que a cópia versionada foi criada antes de prosseguir; se faltar, cria a partir do `context/handoff.md` corrente com o slug correto (inclui `qa`). Nunca edite snapshots já existentes.

### Sequência por criticidade

**Baixa:**
```
Agent(Block Orchestrator) → lê handoff → Agent(Builder) → reportar ao usuário
```

**Média / Alta:**
```
Agent(Block Orchestrator) → lê handoff → Agent(Planner) → lê handoff
→ Agent(Builder) → lê handoff → Agent(QA) → reportar veredito ao usuário
```

**Crítica / Estratégica:**
```
Agent(Block Orchestrator) → lê handoff → Agent(Planner) → lê handoff
→ PARAR: apresentar handoff.md ao usuário e aguardar aprovação explícita
→ somente após aprovação confirmada: Agent(Builder) → lê handoff → Agent(QA)
→ reportar veredito ao usuário
```

### Contexto isolado por Skill

Cada Agent deve receber **apenas** o que a Skill precisa:

**Block Orchestrator:** CLAUDE.md + tasks/current_task.md + context/handoff.md (se vier de outra Skill) + trecho relevante do PRD.md

**Planner:** CLAUDE.md + tasks/current_task.md + context/handoff.md + arquivos-alvo listados no handoff

**Builder:** CLAUDE.md + tasks/current_task.md + context/handoff.md + arquivos-alvo listados no handoff

**QA:** CLAUDE.md + tasks/current_task.md + context/handoff.md + arquivos alterados listados no handoff

---

## Passo 5 — Pausa de aprovação (Crítica/Estratégica)

Quando a esteira exigir aprovação humana:

1. Exiba o conteúdo completo de `context/handoff.md` ao usuário
2. Exiba esta mensagem:

```
⚠ APROVAÇÃO NECESSÁRIA

Esta tarefa é classificada como [Crítica/Estratégica].
O Planner gerou o plano técnico acima.

Responda com uma das opções:
- "aprovar" — Builder será executado conforme o plano
- "ajustar: [instrução]" — plano será revisado antes da execução
- "cancelar" — ciclo encerrado sem execução
```

3. Aguarde a resposta do usuário antes de spawnar o Builder.

---

## Passo 6 — Fechar o ciclo

Após o QA emitir veredito:

1. Atualize `tasks/current_task.md` com status final (aprovado | reprovado | correção pendente)
2. Atualize `tasks/completed.md` com resumo do ciclo
3. Se QA criou novo bloco de correção, adicione a `tasks/backlog.md`
4. Reporte ao usuário:

```
## Ciclo concluído

Tarefa: [nome]
Veredito: [APROVADO | APROVADO COM RESSALVAS | REPROVADO]
Skills executadas: [lista]

[resumo de 2-3 linhas do que foi feito]

Próximo passo recomendado: [próxima tarefa do backlog ou ação]
```

Ordem de fechamento (execução): **(6.a) commit por path → (6.b) merge pelo humano → (6.c) dry-run autônomo → (6.d) rollback se preciso**.

5. **(6.a) Commit isolado por path.** Commite apenas os arquivos do ciclo + os handoffs versionados: `git add <paths> context/handoff.md context/handoff/`, mensagem com o ID do bloco. NÃO inclua `PRD.md` ou outros arquivos não relacionados. Este commit é o que viabiliza o merge e o dry-run dos passos seguintes.
6. **(6.b) Merge — ator: humano.** O **humano** revisa a branch `ciclo/<ID>` e faz o merge na branch base. O orquestrador NÃO faz o merge sozinho. Após o merge, segue-se o dry-run autônomo (6.c).
7. **(6.c) Dry-run autônomo pós-merge (gate — só para ciclos que alteram a orquestração).**
   - **Escopo (quando dispara):** o dry-run SÓ dispara quando o ciclo recém-fechado alterou a própria orquestração — `.claude/commands/run-cycle.md`, `prompts/*.md`, `.codex/skills/codex-run-cycle/SKILL.md` ou a esteira. Ciclos normais (que não tocam a orquestração) NÃO disparam dry-run.
   - **Execução autônoma:** o ORQUESTRADOR roda o dry-run sozinho — não é o humano que conduz. Ele dispara um ciclo trivial com tarefa dummy de criticidade **Baixa** e a flag `dry_run: true` registrada no `current_task.md`.
   - **Guard de recursão (obrigatório):** no início do Passo 6, cheque "sou um dry-run?" lendo `dry_run: true` no `current_task.md`. **Se sim, NÃO dispare outro dry-run** — quebra a recursão na profundidade 1; o dry-run executa a esteira até o fim e encerra sem reentrar aqui.
   - **Verificações automáticas:** o orquestrador valida sozinho — commit isolado por path via `git log --oneline -3`, handoffs versionados via `ls context/handoff/` (formato `AAAAMMDD-HHMMSS-<slug>.md`, incluindo `qa` quando a esteira o inclui), e via `git status` que nenhuma edição não relacionada (ex.: `PRD.md`) foi arrastada.
   - **Em caso de falha:** REVERTER de forma NÃO-destrutiva (preferir `git switch <branch-anterior>` / `git restore`) e **reportar**. Rollback destrutivo continua exigindo confirmação humana (ver 6.d).
   - **Papel do humano:** ler o relatório do dry-run, não conduzi-lo.
8. **(6.d) Guardrail de rollback (preferir não-destrutivo).** Se o ciclo falhar no meio — preferir `git switch <branch-anterior>` (abandona a branch do ciclo sem apagar trabalho) ou `git restore --staged <path>` para desfazer staging. Marque EXPLICITAMENTE como destrutivo qualquer `git reset --hard`/`git branch -D` e exija confirmação humana antes; nunca rode reset destrutivo que alcance `PRD.md` ou edições não relacionadas.

---

## Guardrails permanentes do orquestrador

- Nunca spawnar Builder sem handoff do Planner (exceto criticidade baixa).
- Nunca spawnar Builder em tarefa Crítica/Estratégica sem aprovação explícita do usuário.
- Se qualquer Agent retornar erro ou handoff malformado: parar, reportar ao usuário e aguardar instrução.
- Nunca sobrescrever `tasks/completed.md` — apenas acrescentar.
- Se o QA reprovar: não fechar o ciclo; criar bloco de correção no backlog e reportar.
- **Branch/commit isolado por ciclo:** Um branch/commit isolado por ciclo (`ciclo/<ID>`); commitar só os paths do ciclo, nunca `git add -A`/`git add .`; nunca arrastar nem reverter edições não relacionadas (ex.: `PRD.md`).
- **Rollback não-destrutivo:** Rollback preferencialmente não-destrutivo (`git switch`, `git restore --staged`); `git reset --hard`/`git branch -D` só com confirmação humana explícita e nunca alcançando edições não relacionadas.
- **Handoff versionado append-only:** Cada Skill (incluindo o QA) grava cópia append-only em `context/handoff/AAAAMMDD-HHMMSS-<slug>.md`; nunca editar snapshots existentes.
- **NO-BYPASS de validação:** Nenhum veredito de QA pode se basear em "verde" obtido contornando a config/artefatos reais (`--config /dev/null`, fixture que não casa as `creation_rules` reais, mock do caminho crítico). Verde por bypass = validação NÃO-EXECUTADA; o ciclo não fecha como APROVADO. (Justificativa: episódio dos 5 defeitos do BLK-OPS-01.)
- **Dry-run autônomo de orquestração:** ciclos que alteram a própria orquestração (run-cycle / prompts / esteira) disparam, **após o merge feito pelo humano**, um dry-run AUTÔNOMO conduzido pelo orquestrador (tarefa dummy Baixa + `dry_run: true`), com guard de recursão na profundidade 1. Ciclos normais NÃO disparam dry-run. O humano lê o relatório; não conduz o dry-run.
