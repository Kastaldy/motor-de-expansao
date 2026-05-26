---
name: codex-run-cycle
description: Orchestrate the motor-de-expansao autonomous work cycle in Codex using sub-agents, handoffs, approvals, and the existing tasks/context/prompts files. Use when the user asks to run, port, adapt, or explain the Claude-style /run-cycle workflow in Codex; when a task should be executed through Block Orchestrator, Planner, Builder, and QA roles; or when Codex must coordinate autonomous sub-agents with limited task-specific context.
---

# Codex Run Cycle

## Purpose

Execute the repository's Claude-style orchestration flow in Codex while preserving the same control files, guardrails, and role prompts. The Codex parent agent is the orchestrator; sub-agents are role workers with deliberately narrow context.

## Repository Contract

Use these repo files as the shared protocol:

- `CLAUDE.md`: canonical project rules and guardrails.
- `README.md`: orchestration overview and project map.
- `PRD.md`: active cycle and product context when relevant.
- `tasks/current_task.md`: active task state.
- `tasks/backlog.md`: pending tasks.
- `tasks/completed.md`: completed cycle history.
- `context/handoff.md`: handoff between roles.
- `prompts/block_orchestrator.md`: Block Orchestrator role prompt.
- `prompts/planner.md`: Planner role prompt.
- `prompts/builder.md`: Builder role prompt.
- `prompts/qa_analyzer.md`: QA role prompt.

Prefer reusing these files instead of duplicating their contents in the skill.

## Triggered Workflow

When the user asks to run a cycle, act as the Codex "chefe" and perform this sequence:

1. Read `CLAUDE.md`, `README.md`, `tasks/current_task.md` if present, and `tasks/backlog.md` if the task may reference backlog.
2. If `tasks/current_task.md` has an active task with status other than "sem tarefa ativa", pause and ask the user before overwriting it.
3. Classify criticity:
   - baixa: text tweak, isolated bug, simple docs.
   - media: localized feature, localized improvement, new screen.
   - alta: new feature or pipeline change.
   - critica: score, ranking, official M1 artifact, executive KPI, `score_priorizacao`, `hex_score_estrutural`, official portfolio or short-term plan.
   - estrategica: architecture redesign or new phase.
4. Write `tasks/current_task.md` using the existing Claude format from `.claude/commands/run-cycle.md`.
5. Run the role sequence for the criticity:
   - baixa: Block Orchestrator -> Builder.
   - media: Block Orchestrator -> Planner -> Builder -> QA.
   - alta: Block Orchestrator -> Planner -> human approval -> Builder -> QA.
   - critica or estrategica: Block Orchestrator -> Planner -> human approval -> Builder -> QA.
6. After each role, update `context/handoff.md` with the role's handoff, then read it before continuing.
7. Close the cycle by updating `tasks/current_task.md`, appending to `tasks/completed.md`, and reporting the final verdict.

## Sub-Agent Policy

Use Codex sub-agents when the environment exposes a sub-agent tool such as `multi_agent_v1.spawn_agent`.

- Spawn role-specific sub-agents only because the user requested this orchestration flow.
- Do not pass the full conversation or whole repository by default.
- Prefer `fork_context: false` for role agents.
- Pass only the role prompt, the current task, the current handoff, and the explicitly required file excerpts.
- Use `agent_type: explorer` for Block Orchestrator, Planner, and QA when they only inspect and report.
- Use `agent_type: worker` for Builder when code edits are authorized.
- Tell worker agents they are not alone in the codebase, must not revert unrelated edits, and must list every changed file.
- The parent Codex remains accountable for approvals, filesystem writes to task files, integration, validation, and the final answer.

If no sub-agent tool is available, continue serially with the same role prompts and state files, and tell the user that this run used single-agent fallback.

## Role Execution Pattern

For each role:

1. Read the matching `prompts/*.md`.
2. Read `context/handoff.md` when it exists.
3. Read only the files named by the prior handoff, plus `CLAUDE.md` and `tasks/current_task.md`.
4. Build a prompt that includes:
   - the role prompt;
   - the current task;
   - relevant excerpts only;
   - explicit output requirement: return the full `context/handoff.md` replacement body.
5. Spawn the role sub-agent or execute serially.
6. Validate that the returned handoff contains the required sections from the role prompt.
7. Write the handoff to `context/handoff.md`.
8. Stop and ask the user if the handoff is malformed, the role exceeded scope, or approval is required.

For Builder, require implementation to follow the Planner handoff exactly. For QA, require a review stance: findings and verdict first, test evidence second.

## Approval Gates

Before Builder runs on alta, critica, or estrategica:

1. Present the complete Planner handoff to the user.
2. State that approval is required.
3. Accept only explicit approval such as "aprovar" or a direct equivalent.
4. If the user asks to adjust, rerun Planner with the requested adjustment.
5. If the user cancels, mark the task as cancelled or paused without running Builder.

For critical M1 areas, the Builder handoff must include:

```text
APROVADO POR [usuario] EM [data]
```

## Mandatory Guardrails

- Never run Builder for critica or estrategica without explicit human approval.
- Never change `score_priorizacao`, `hex_score_estrutural`, official M1 artifacts, portfolio, short-term plan, domain plan, or executive KPIs without critical approval.
- Never create a live API dependency for the production Streamlit dashboard.
- Never overwrite production Parquets without staging.
- Preserve official M1 rows and columns when touching parallel data layers.
- Keep every cycle to one block; put new work in backlog.
- Do not overwrite `tasks/completed.md`; append only.
- Respect existing user changes in the worktree and do not revert unrelated edits.

## Validation

Use the validation commands named by the Planner. If Builder changes dashboard code and the handoff does not specify otherwise, run:

```bash
python -m pytest -q tests/integration/test_streamlit_app.py
python -c "import streamlit_app; print('import ok')"
```

If tests cannot run, record the reason in `context/handoff.md` and the final response.

## Final Report

End with a concise report in Portuguese:

```text
## Ciclo concluido

Tarefa: [nome]
Veredito: [APROVADO | APROVADO COM RESSALVAS | REPROVADO | PAUSADO]
Roles executados: [lista]

[resumo em 2-3 linhas]

Proximo passo recomendado: [acao concreta]
```
