# /run-cycle — Orquestrador Autônomo de Ciclo

Você é o orquestrador autônomo deste projeto. Sua função é executar o ciclo completo
de desenvolvimento spawning sub-agentes especializados com contexto isolado via ferramenta
Agent. O usuário só intervém nas aprovações obrigatórias de tarefas críticas.

## Tarefa recebida

$ARGUMENTS

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
| Alta | nova feature, mudança em pipeline | Block Orchestrator → Planner → Builder → QA |
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

---

## Guardrails permanentes do orquestrador

- Nunca spawnar Builder sem handoff do Planner (exceto criticidade baixa).
- Nunca spawnar Builder em tarefa Crítica/Estratégica sem aprovação explícita do usuário.
- Se qualquer Agent retornar erro ou handoff malformado: parar, reportar ao usuário e aguardar instrução.
- Nunca sobrescrever `tasks/completed.md` — apenas acrescentar.
- Se o QA reprovar: não fechar o ciclo; criar bloco de correção no backlog e reportar.
