# Guia de Uso Prático — Sistema de Skills
> Como operar o orquestrador autônomo em cada fase de maturidade.
> Atualizado em: 2026-05-25

---

# FASE 1 — NÚCLEO MÍNIMO (ATUAL)

## O que está disponível agora

| Componente | Arquivo | Status |
|---|---|---|
| Slash command `/run-cycle` | `.claude/commands/run-cycle.md` | ativo |
| Block Orchestrator | `prompts/block_orchestrator.md` | ativo |
| Planner | `prompts/planner.md` | ativo |
| Builder | `prompts/builder.md` | ativo |
| QA/Quality Analyzer | `prompts/qa_analyzer.md` | ativo |
| Tarefa ativa | `tasks/current_task.md` | ativo |
| Backlog | `tasks/backlog.md` | ativo |
| Histórico | `tasks/completed.md` | ativo |
| Canal de handoff | `context/handoff.md` | ativo |

## Como usar — o fluxo padrão

### 1. Abrir o Claude Code no diretório do projeto

```bash
cd motor-de-expansao
claude
```

### 2. Invocar o orquestrador com a descrição da tarefa

```
/run-cycle adicionar filtro de UF na sidebar do dashboard, aba Mapa Territorial
```

O orquestrador vai:
1. Classificar a criticidade automaticamente
2. Exibir a esteira que será executada
3. Spawn Block Orchestrator → escreve `context/handoff.md`
4. Spawn Planner → atualiza `context/handoff.md`
5. **Exibir o plano e pedir aprovação** (se alta/crítica)
6. Spawn Builder → implementa e roda testes
7. Spawn QA → audita e emite veredito
8. Exibir relatório final com ações manuais para fechar o ciclo

### 3. Interação do usuário durante o ciclo

O único momento em que você precisa digitar algo durante o ciclo (além do comando inicial) é a aprovação antes do Builder, para tarefas de criticidade alta ou crítica:

```
=== PLANO TÉCNICO — AGUARDANDO APROVAÇÃO ===
...
Aprovado para executar o Builder?
```

Digite `sim` para continuar ou `não` para encerrar e ajustar.

Para tarefas de baixa ou média criticidade, o ciclo roda sem interrupção.

### 4. Fechar o ciclo (ação manual)

Após o veredito do QA, o orquestrador exibe as ações necessárias:

```
Ações manuais para fechar o ciclo:
1. Mova a tarefa de tasks/current_task.md para tasks/completed.md
2. Atualize tasks/backlog.md se houver próximo bloco
3. Se houve mudança de estado relevante, atualize CLAUDE.md
```

Copie o conteúdo relevante de `tasks/current_task.md` para `tasks/completed.md`
e limpe `tasks/current_task.md`.

## Exemplos de invocação por criticidade

### Baixa criticidade — sem interrupção
```
/run-cycle corrigir texto do tooltip de consumo fitness na aba Expansão de Domínio
```
Esteira: Block Orchestrator → Builder
Interação: nenhuma durante o ciclo.

### Média criticidade — sem interrupção
```
/run-cycle adicionar coluna 'data_abertura' na tabela de carteira da aba Carteira e Plano
```
Esteira: Block Orchestrator → Planner → Builder → QA
Interação: nenhuma durante o ciclo.

### Alta criticidade — uma pausa
```
/run-cycle implementar filtro de score mínimo na aba Mapa Territorial com persistência em session_state
```
Esteira: Block Orchestrator → Planner → [PAUSA] → Builder → QA
Interação: aprovação antes do Builder.

### Crítica — pausa com alerta
```
/run-cycle ajustar peso da renda no score_priorizacao de 0.40 para 0.35
```
Esteira: Block Orchestrator → Planner → [PAUSA OBRIGATÓRIA + ALERTA] → Builder → QA
Interação: aprovação obrigatória com leitura do alerta de guardrail.

## Quando NÃO usar /run-cycle

| Situação | O que fazer |
|---|---|
| Tarefa estratégica (mudança arquitetural, nova fase) | Use /run-cycle mas encerre após o Planner — execute separadamente |
| Tarefa já em andamento em tasks/current_task.md | Feche o ciclo anterior antes de iniciar novo |
| Dúvida sobre escopo antes de iniciar | Converse com o agente primeiro, depois /run-cycle |
| Exploração de código sem intenção de alterar | Use o Claude Code diretamente sem /run-cycle |

## O que acontece internamente (para referência)

```
Você: /run-cycle [descrição]
  │
  ▼
Orquestrador lê CLAUDE.md + classifica criticidade
  │
  ▼
spawn Block Orchestrator (sub-agente isolado)
  → lê prompts/block_orchestrator.md
  → lê CLAUDE.md, tasks/current_task.md
  → escreve context/handoff.md
  │
  ▼ (se média/alta/crítica)
spawn Planner (sub-agente isolado)
  → lê prompts/planner.md
  → lê context/handoff.md + arquivos-alvo
  → atualiza context/handoff.md com plano
  │
  ▼ (se alta/crítica)
Orquestrador exibe plano → aguarda "sim"
  │
  ▼
spawn Builder (sub-agente isolado)
  → lê prompts/builder.md
  → lê CLAUDE.md (guardrails) + context/handoff.md
  → implementa → roda testes
  → atualiza context/handoff.md com resultado
  │
  ▼ (se média/alta/crítica)
spawn QA (sub-agente isolado)
  → lê prompts/qa_analyzer.md
  → lê context/handoff.md + arquivos alterados
  → emite veredito
  → atualiza context/handoff.md
  │
  ▼
Orquestrador exibe relatório final + ações manuais
```

---

# FASE 2 — EXPANSÃO CONTROLADA (PRÓXIMA)

## Pré-requisito

Fase 1 validada com pelo menos 2 ciclos reais usando /run-cycle.
Problemas de atrito documentados e resolvidos.

## O que será adicionado

| Componente | Arquivo | O que muda |
|---|---|---|
| Master Orchestrator | `prompts/master_orchestrator.md` | Prioriza backlog e define esteira |
| Approver | `prompts/approver.md` | Formaliza aprovação de planos críticos |
| Documentation Skill | `prompts/documenter.md` | Fecha o ciclo automaticamente |
| Data Agent | `prompts/data_agent.md` | Valida dados antes do QA |
| Metrics Agent | `prompts/metrics_agent.md` | Valida scores e KPIs antes do QA |
| Registro de decisões | `DECISIONS.md` | Migração das decisões do CLAUDE.md |
| Contexto ativo | `context/active_context.md` | Estado operacional entre ciclos |
| Tarefas bloqueadas | `tasks/blocked.md` | Rastreio de bloqueios |

## Como /run-cycle evolui na Fase 2

O comando ganha dois novos comportamentos:

**1. Fechamento automático do ciclo** — em vez de ações manuais, a Documentation Skill
fecha o ciclo, atualiza tasks/, context/ e CLAUDE.md automaticamente.

**2. Rota de dados/métricas** — para tarefas críticas com dados ou scores, o ciclo
inclui Data Agent e/ou Metrics Agent entre o Builder e o QA:

```
Builder → Data Agent → Metrics Agent → QA → Documentation Skill
```

Para ativar na Fase 2, basta criar os arquivos de prompt — o run-cycle.md
será atualizado para reconhecer e acionar as novas Skills.

## DECISIONS.md — como preencher ao iniciar a Fase 2

O DECISIONS.md começa com as decisões já tomadas, migradas do CLAUDE.md:

- DEC-001: Score oficial e pesos (renda=0.40, pop=0.60) — 2026-05-15
- DEC-002: Parâmetros canônicos M1 (H3_RESOLUTION, DIST_MIN_ULTRA_KM etc.)
- DEC-003: score_dominio_hibrido = clip(0.60*censitário + 0.40*residual)
- DEC-004: Adoção da estrutura de Skills

O template está em `orquestracao_claude.md`, seção DECISIONS.md.

---

# FASE 3 — ORQUESTRAÇÃO AUTÔNOMA (FUTURA)

## Pré-requisito

Fase 2 validada com pelo menos 5 ciclos reais. Handoff estável e sem ambiguidades.

## O que muda

### Slash commands nativos para cada Skill

Mover os prompts de `prompts/` para `.claude/commands/`:

```
.claude/commands/
  block-orchestrator.md   → /block-orchestrator
  planner.md              → /planner
  builder.md              → /builder
  qa-analyzer.md          → /qa-analyzer
  master-orchestrator.md  → /master-orchestrator
  approver.md             → /approver
  documenter.md           → /documenter
  data-agent.md           → /data-agent
  metrics-agent.md        → /metrics-agent
```

Isso permite invocar Skills individualmente quando necessário,
sem precisar do /run-cycle para ciclos simples.

### Hooks de validação automática

Configurar hooks em `.claude/settings.json` para validar o handoff
após cada escrita em `context/handoff.md`:

```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write",
      "hooks": [{
        "type": "command",
        "command": "python scripts/validate_handoff.py"
      }]
    }]
  }
}
```

### Skills adicionadas na Fase 3

| Skill | Quando acionar |
|---|---|
| Frontend Builder | Features de dashboard, UI, componentes Streamlit |
| Backend Builder | Pipelines, jobs, regras de negócio, contratos de dados |
| Cybersecurity Agent | Deploy, autenticação, LGPD, APIs externas |
| Designer/UI | Redesenho de telas, novo produto visual |

### Caminho para autonomia total

```
Hoje (Fase 1):    /run-cycle → orquestra sub-agentes → pausa para alta/crítica
Fase 2:           + fechamento automático + Data/Metrics Agents
Fase 3:           + slash commands individuais + hooks + novas Skills
Autonomia total:  apenas crítica e estratégica passam por aprovação humana
```

---

# REFERÊNCIA RÁPIDA

## Esteiras por criticidade

| Criticidade | Esteira Fase 1 | Pausa humana |
|---|---|---|
| Baixa | Orchestrator → Builder | não |
| Média | Orchestrator → Planner → Builder → QA | não |
| Alta | Orchestrator → Planner → **[PAUSA]** → Builder → QA | sim |
| Crítica | Orchestrator → Planner → **[PAUSA + ALERTA]** → Builder → QA | obrigatória |
| Estratégica | Orchestrator → Planner → **[ENCERRA]** | sim, sempre |

## Tiering de modelo por agente (custo proporcional à complexidade)

Desde BLK-ORQ-01 (2026-06-02), o orquestrador escolhe o modelo de cada sub-agente pela criticidade
(proxy de complexidade) × papel — gastando o mínimo em tarefas simples:

| Agente | Baixa | Média | Alta | Crítica/Estratégica |
|---|---|---|---|---|
| Block Orchestrator | haiku | sonnet | sonnet | opus |
| Planner | sonnet | sonnet | opus | opus |
| Builder | sonnet | sonnet | opus | opus |
| **QA** | **opus** | **opus** | **opus** | **opus** |

- **QA roda SEMPRE em Opus 4.8** (regra dura, nunca rebaixado).
- Override ±1 nível só com justificativa de 1 linha; pisos: QA nunca sai de Opus, nunca abaixo de haiku.
- O dry-run de orquestração (Passo 6.c) usa a coluna Baixa (BO=haiku, Builder=sonnet) → barato/rápido.

Política canônica em `.claude/commands/run-cycle.md` (Passo 4 → "Seleção de modelo por agente").

## Arquivos do sistema

| Arquivo | Papel | Quem escreve |
|---|---|---|
| `tasks/current_task.md` | Tarefa ativa única | Block Orchestrator, Builder, QA |
| `tasks/backlog.md` | Próximos blocos | usuário + QA (correções) |
| `tasks/completed.md` | Histórico | usuário (manual na Fase 1) |
| `context/handoff.md` | Canal entre Skills | cada Skill ao concluir |
| `prompts/*.md` | Instruções de cada Skill | não alterar sem planejamento |
| `.claude/commands/run-cycle.md` | Orquestrador autônomo | não alterar sem planejamento |

## Arquivos canônicos (não alterar via Skills)

| Arquivo | Papel |
|---|---|
| `CLAUDE.md` | Fonte canônica do projeto. Atualizar apenas ao fechar ciclos relevantes. |
| `PRD.md` | Guia operacional. Atualizar apenas quando regra mudar. |
| `config.py` | Parâmetros canônicos do M1. Nunca via Skills sem aprovação. |

## Quando o ciclo dá errado

| Problema | Solução |
|---|---|
| Sub-agente não escreveu handoff | Verificar `context/handoff.md`. Reinvocar a Skill manualmente. |
| Builder excedeu escopo | QA reprovará. Criar bloco de correção no backlog. |
| Testes falharam | Builder reporta no handoff. QA reprovará. Corrigir e reinvocar Builder. |
| Aprovação negada | Ajustar `tasks/current_task.md` ou `context/handoff.md` e reinvocar /run-cycle. |
| Tarefa crítica sem aprovação | Orquestrador não avança. Digitar "sim" ou encerrar. |
