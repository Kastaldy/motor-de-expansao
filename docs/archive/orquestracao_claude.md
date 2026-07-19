# Orquestração Claude — Motor de Expansão Ultra Academia
> Estrutura alternativa baseada na análise crítica de `orquestracao_agentes.md`.
> Princípio central: proporcionalidade. O modelo cresce conforme a necessidade real.
> Responsável: Felipe Silva | Versão: Maio 2026

---

# MISSÃO

Evoluir o fluxo atual de single-agent para um modelo estruturado de Skills especializadas, com separação clara entre planejamento, execução, revisão e documentação — sem criar burocracia que supere o benefício.

O modelo segue três fases de maturidade:

- **Fase 1 — Núcleo mínimo**: 4 Skills essenciais, ~8 arquivos novos. Operacional imediatamente.
- **Fase 2 — Expansão controlada**: 7 Skills, backlog estruturado, histórico de decisões.
- **Fase 3 — Orquestração autônoma**: Skills como slash commands e agentes com handoff automatizado.

Toda demanda passa por triagem. A profundidade da esteira depende da criticidade. Tarefas simples não precisam da esteira completa.

---

# DIFERENÇAS EM RELAÇÃO AO PLANO ORIGINAL

| Aspecto | Plano original | Este plano |
|---|---|---|
| Skills imediatas | 14 de uma vez | 4 no início, expansão gradual |
| Arquivos novos | ~30 na implementação | ~8 na Fase 1 |
| CLAUDE.md | Reescrever do zero | Preservar e estender |
| DECISIONS.md | Começar do zero | Migrar decisões existentes |
| Mecanismo de invocação | Não especificado | Passo a passo por fase |
| BLK-001 | Criar estrutura | Criar + validar com ciclo real |
| Cybersecurity/Designer | Obrigatórias | Opcionais, acionadas por contexto |
| Caminho para autonomia | Implícito | Explícito com slash commands |

---

# PRINCÍPIOS DO MODELO

1. O repositório é a fonte de verdade. CLAUDE.md é o ponto de entrada.
2. CLAUDE.md não é reescrito — é estendido com uma seção de Skills quando necessário.
3. Cada Skill lê apenas o contexto necessário para sua etapa.
4. O handoff entre Skills é um arquivo, não uma conversa.
5. A janela de contexto é zerada entre Skills sempre que possível.
6. Nenhuma Skill avança para outro bloco sem autorização explícita.
7. Mudanças em score, ranking, KPI ou artefatos M1 exigem validação especializada.
8. A esteira é proporcional ao risco. Ajustes simples usam fluxo mínimo.
9. Aprovação humana é obrigatória antes de execução crítica.
10. A estrutura evolui conforme validação real — não antes.
11. Guardrails do projeto (score_priorizacao, M1 oficial) são herdados por toda Skill.
12. Documentação fecha o ciclo, não abre.

---

# GUARDRAILS PERMANENTES DO PROJETO

Estes guardrails são herdados por todas as Skills. Nenhuma Skill pode violá-los:

- `score_priorizacao`, `hex_score_estrutural` e artefatos M1 oficiais são imutáveis sem aprovação explícita do usuário.
- Nenhuma camada paralela (censitário, hibrido, mercado, expansão de domínio) altera o M1.
- Dashboard não usa API ao vivo. Funciona offline com Parquets locais.
- Toda mudança relevante entra com teste. Nenhum bloco fecha com CI quebrado.
- Pesos aprovados do score: `renda=0.40`, `pop=0.60`. Alteração exige DEC registrado.
- Parâmetros canônicos: `H3_RESOLUTION=7`, `DIST_MIN_ULTRA_KM=1.0`, `RENDA_MIN=4500.0`.

---

# FASE 1 — NÚCLEO MÍNIMO

## Objetivo

Implementar o fluxo básico de Skills em 1 bloco, testar com um ciclo real e validar que o modelo funciona antes de expandir.

## Skills da Fase 1

| Skill | Papel |
|---|---|
| Block Orchestrator | Aprofunda e delimita um bloco antes da execução |
| Planner | Cria plano técnico detalhado |
| Builder | Executa o bloco aprovado |
| QA/Quality Analyzer | Audita a entrega |

## Arquivos criados na Fase 1

```
tasks/
  current_task.md       ← tarefa ativa única
  backlog.md            ← próximos blocos
  completed.md          ← histórico resumido
context/
  handoff.md            ← passagem entre Skills
prompts/
  block_orchestrator.md
  planner.md
  builder.md
  qa_analyzer.md
```

O que NÃO é criado na Fase 1: DECISIONS.md, ROADMAP.md, ARCHITECTURE.md, DATA_DICTIONARY.md, VALIDATION.md, RUNBOOK.md, AGENTS.md, docs/business_context.md etc. Esses chegam na Fase 2.

## Como operacionar na Fase 1 — Passo a passo

### Passo 1 — Triagem da demanda

Antes de qualquer sessão, classificar a demanda:

| Criticidade | Exemplos | Esteira |
|---|---|---|
| Baixa | ajuste textual, bug isolado, doc simples | Block Orchestrator → Builder |
| Média | nova função, melhoria localizada, nova tela simples | Block Orchestrator → Planner → Builder → QA |
| Alta | nova feature, mudança em pipeline principal | Block Orchestrator → Planner → Builder → QA |
| Crítica | mudança em score, ranking, artefato M1, métrica executiva | Block Orchestrator → Planner → [aprovação humana] → Builder → QA |

### Passo 2 — Abrir o Claude Code

Abrir nova sessão do Claude Code no diretório do projeto. Garantir contexto limpo (`/clear` se necessário).

### Passo 3 — Invocar a Skill

Copiar o conteúdo do arquivo de prompt correspondente em `prompts/` e colar no início da mensagem, seguido da instrução específica da tarefa.

**Exemplo para Block Orchestrator:**
```
[colar conteúdo de prompts/block_orchestrator.md]

Bloco a aprofundar: [nome e descrição do bloco]
```

**Exemplo para Builder:**
```
[colar conteúdo de prompts/builder.md]

Execute o bloco conforme handoff em context/handoff.md.
```

### Passo 4 — Revisar o handoff

Após cada Skill, verificar `context/handoff.md` antes de invocar a próxima. O handoff define escopo, fora de escopo, arquivos envolvidos e critérios de aceite.

### Passo 5 — Aprovação humana (quando crítico)

Para tarefas críticas, revisar o plano gerado pelo Planner antes de invocar o Builder. Aprovar ou ajustar manualmente. Somente depois invocar o Builder.

### Passo 6 — Fechar o ciclo

Após o QA emitir veredito aprovado, atualizar manualmente:
- `tasks/current_task.md` → limpar ou marcar como concluído
- `tasks/completed.md` → registrar resumo da tarefa
- `tasks/backlog.md` → atualizar se houver próximo bloco
- `context/handoff.md` → limpar para o próximo ciclo
- CLAUDE.md → se houver mudança de estado relevante

---

# FASE 2 — EXPANSÃO CONTROLADA

## Pré-requisito

A Fase 2 só começa após a Fase 1 ter sido validada com pelo menos 2 ciclos reais.

## Skills adicionadas na Fase 2

| Skill | Papel |
|---|---|
| Master Orchestrator | Visão macro, priorização de backlog, governança |
| Approver | Revisão formal de plano antes da construção |
| Documentation Skill | Consolidação de docs ao final de cada ciclo |
| Data Agent | Validação de dados, fontes, pipelines, outputs |
| Metrics Agent | Validação de scores, KPIs, fórmulas, rankings |

## Arquivos adicionados na Fase 2

```
DECISIONS.md            ← histórico de decisões (começa com migração do CLAUDE.md)
context/
  active_context.md     ← estado operacional ativo
tasks/
  blocked.md            ← tarefas bloqueadas
prompts/
  master_orchestrator.md
  approver.md
  documenter.md
  data_agent.md
  metrics_agent.md
```

## Como operacionar na Fase 2

### Passo adicional — Master Orchestrator como ponto de entrada

Para tarefas de alta criticidade ou revisão de backlog, invocar o Master Orchestrator antes do Block Orchestrator. O Master define qual tarefa avançar, qual criticidade e qual esteira usar.

### Passo adicional — Approver antes do Builder (alta/crítica)

Para tarefas alta e crítica, o Planner gera o plano, o usuário lê o `context/handoff.md` e invoca o Approver para revisão formal. O Approver emite veredito antes do Builder.

### Passo adicional — Data Agent e Metrics Agent (crítica)

Para tarefas críticas envolvendo dados ou scores, o Builder emite handoff para Data Agent ou Metrics Agent após execução, antes do QA.

### Passo adicional — Documentation Skill ao fechar o ciclo

Em vez de atualizar docs manualmente, invocar a Documentation Skill. Ela consolida tudo e atualiza CLAUDE.md, tasks/, context/ e DECISIONS.md.

---

# FASE 3 — ORQUESTRAÇÃO AUTÔNOMA

## Objetivo

Evoluir as Skills de prompts manuais para slash commands do Claude Code e, em seguida, para agentes com handoff automatizado.

## Pré-requisito

Fase 2 validada com pelo menos 5 ciclos reais. Fluxo de handoff estável e testado.

## Mecanismo de evolução

### Etapa 3.1 — Skills como slash commands do Claude Code

Criar arquivos em `.claude/commands/` com o conteúdo de cada prompt de Skill. O Claude Code reconhece automaticamente esses arquivos como slash commands.

```
.claude/
  commands/
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

Uso: em vez de copiar o prompt manualmente, digitar `/builder` no Claude Code.

### Etapa 3.2 — Hooks de automação via settings.json

Configurar hooks no Claude Code para executar ações automáticas após cada Skill:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "python scripts/validate_handoff.py"
          }
        ]
      }
    ]
  }
}
```

Scripts de validação podem verificar automaticamente se o handoff foi gerado, se os critérios mínimos estão presentes, e sinalizar ao usuário antes de prosseguir.

### Etapa 3.3 — Agentes com loop de handoff

Usando o Claude Code SDK ou a API Anthropic com ferramenta de leitura de arquivos, implementar um orquestrador que:

1. Lê `context/handoff.md` após cada Skill.
2. Identifica a próxima Skill recomendada.
3. Carrega o prompt correspondente de `prompts/`.
4. Invoca a próxima Skill com contexto seletivo.
5. Para quando chega a uma etapa de aprovação humana ou ao final do ciclo.

```python
# Esquema conceitual do orquestrador autônomo (Fase 3.3)
def run_cycle(initial_skill: str, task: str):
    current_skill = initial_skill
    while current_skill and current_skill != "HUMAN_APPROVAL":
        prompt = load_prompt(current_skill)
        context = load_selective_context(current_skill)
        output = invoke_claude(prompt, context, task)
        write_handoff(output)
        current_skill = read_next_skill_from_handoff()
    notify_human_if_approval_required()
```

### Skills adicionadas na Fase 3

| Skill | Fase | Quando acionar |
|---|---|---|
| Frontend Builder | 3 | Features de dashboard ou UI |
| Backend Builder | 3 | Pipelines, APIs, regras de negócio |
| Cybersecurity Agent | 3 | Autenticação, LGPD, APIs externas, deploy |
| Designer/UI | 3 | Redesenho de telas ou nova experiência de usuário |

---

# MODELO COMPLETO DE SKILLS

## Hierarquia de leitura de contexto

Toda Skill deve respeitar esta hierarquia ao decidir quais arquivos ler:

```
1. CLAUDE.md                    ← sempre
2. context/active_context.md    ← quando existir (Fase 2+)
3. tasks/current_task.md        ← sempre que houver tarefa ativa
4. context/handoff.md           ← quando receber de outra Skill
5. PRD.md                       ← quando necessário para regras
6. DECISIONS.md                 ← quando existir e necessário
7. Arquivos-alvo específicos    ← apenas os necessários
```

Não ler o repositório inteiro. Não carregar histórico longo se a tarefa depende apenas do bloco atual.

---

## Skill 1 — Block Orchestrator

**Fase:** 1
**Papel:** Aprofunda e delimita exclusivamente o bloco atual antes de planejamento ou execução.

**Lê:**
- CLAUDE.md
- tasks/current_task.md
- context/handoff.md (se vier de outra Skill)
- PRD.md, trecho relevante

**Produz:**
- Bloco refinado com objetivo claro
- Escopo permitido (explícito)
- Fora de escopo (explícito)
- Arquivos que devem ser lidos
- Arquivos que podem ser alterados
- Agente/Skill recomendada
- Critérios de aceite
- Riscos identificados
- Handoff para próxima etapa

**Não faz:**
- Não implementa
- Não altera arquitetura
- Não resolve múltiplos blocos
- Não expande escopo

---

## Skill 2 — Planner

**Fase:** 1
**Papel:** Transforma um bloco delimitado em plano técnico executável.

**Lê:**
- CLAUDE.md
- tasks/current_task.md
- context/handoff.md
- PRD.md, trecho relevante
- DECISIONS.md, se existir e relevante
- Arquivos-alvo listados no handoff

**Produz:**
- Entendimento da tarefa
- Plano técnico em etapas numeradas
- Arquivos afetados (lista exata)
- Dependências
- Riscos técnicos
- Estratégia de validação
- Critérios de aceite finais
- Handoff para Builder ou Approver

**Não faz:**
- Não implementa
- Não altera código
- Não expande escopo sem registrar decisão
- Não cria plano genérico

**Guardrail embutido:** Se o plano envolver score_priorizacao, hex_score_estrutural, carteira, plano curto prazo ou qualquer artefato M1, sinalizar obrigatoriamente e recomendar passagem por Approver + Data/Metrics Agent.

---

## Skill 3 — Builder

**Fase:** 1
**Papel:** Executa a tarefa aprovada. Faz mudanças mínimas, controladas e rastreáveis.

**Lê:**
- CLAUDE.md
- tasks/current_task.md
- context/handoff.md
- Arquivos-alvo listados no handoff
- CLAUDE.md seção de guardrails antes de qualquer alteração de dados/score

**Produz:**
- Implementação completa do bloco
- Lista de arquivos alterados
- Testes executados e resultado
- Problemas encontrados
- Pendências
- Riscos remanescentes
- Handoff para QA

**Não faz:**
- Não altera escopo
- Não muda regra de negócio sem decisão registrada
- Não refatora fora do escopo
- Não executa múltiplos blocos
- Não avança sem rodar validações mínimas

**Guardrail embutido:**
- Nunca alterar `score_priorizacao`, `hex_score_estrutural` ou artefatos M1 sem aprovação explícita do usuário registrada no handoff.
- Nunca criar dependência de API ao vivo no dashboard de produção.
- Toda mudança em dados deve preservar 100% das linhas e colunas do M1.
- Rodar `python -m pytest -q tests/integration/test_streamlit_app.py` antes de gerar handoff.

---

## Skill 4 — QA/Quality Analyzer

**Fase:** 1
**Papel:** Audita criticamente a entrega. Verifica aderência ao escopo e critérios de aceite.

**Lê:**
- CLAUDE.md
- tasks/current_task.md
- context/handoff.md
- Arquivos alterados pelo Builder
- Logs de teste
- Outputs gerados

**Produz:**
- Veredito: aprovado / aprovado com ressalvas / reprovado
- Justificativa
- Problemas críticos (bloqueadores)
- Problemas médios (não bloqueadores)
- Melhorias opcionais
- Testes faltantes
- Riscos remanescentes
- Handoff para Documentation (Fase 2) ou instrução de fechamento manual

**Não faz:**
- Não implementa features
- Não aprova sem evidência (log de teste ou saída verificável)
- Não ignora fora de escopo
- Não aceita "rodou sem erro" como evidência de qualidade

**Guardrail embutido:**
- Verificar explicitamente que score_priorizacao e artefatos M1 não foram alterados se a tarefa era em camada paralela.
- Verificar que testes passam (`pytest -q` verde) antes de emitir aprovação.

---

## Skill 5 — Master Orchestrator (Fase 2)

**Fase:** 2
**Papel:** Visão geral do projeto, priorização macro, governança do backlog.

**Lê:**
- CLAUDE.md
- tasks/backlog.md
- tasks/current_task.md
- tasks/completed.md
- context/active_context.md
- DECISIONS.md
- PRD.md

**Produz:**
- Diagnóstico do estado atual do projeto
- Priorização do backlog
- Classificação de criticidade da tarefa selecionada
- Esteira recomendada
- Próxima Skill
- Riscos e dependências
- Atualização macro do backlog

**Não faz:**
- Não implementa
- Não entra em detalhe técnico profundo
- Não seleciona múltiplas tarefas para execução simultânea

---

## Skill 6 — Approver (Fase 2)

**Fase:** 2
**Papel:** Revisão formal do plano antes da execução de tarefas alta ou crítica.

**Lê:**
- CLAUDE.md
- tasks/current_task.md
- context/handoff.md
- PRD.md
- DECISIONS.md

**Produz:**
- Veredito: aprovado / aprovado com ressalvas / reprovado
- Justificativa
- Ajustes obrigatórios
- Riscos aceitos
- Riscos não aceitos
- Skill de construção autorizada
- Condições para execução
- Handoff para Builder

**Pode ser executada pelo humano com suporte da IA.** Para tarefas críticas, o ideal é que o usuário revise o handoff do Planner e emita a aprovação, usando o Approver apenas para estruturar e registrar a decisão.

**Guardrail embutido:**
- Nunca aprovar mudança em score ou artefato M1 sem que o usuário tenha lido e confirmado explicitamente.

---

## Skill 7 — Documentation Skill (Fase 2)

**Fase:** 2
**Papel:** Consolidação de documentação ao final de cada ciclo.

**Lê:**
- CLAUDE.md
- tasks/current_task.md, tasks/backlog.md, tasks/completed.md
- DECISIONS.md
- context/handoff.md
- Arquivos alterados no ciclo
- PRD.md, se necessário

**Produz:**
- CLAUDE.md atualizado (estado operacional)
- tasks/ atualizados (mover concluído, atualizar backlog)
- DECISIONS.md atualizado se houver decisão
- context/active_context.md atualizado
- context/handoff.md limpo para próximo ciclo
- Resumo final do ciclo

**Não faz:**
- Não transforma CLAUDE.md em histórico longo
- Não duplica conteúdo entre arquivos
- Não inventa decisões

---

## Skill 8 — Data Agent (Fase 2)

**Fase:** 2
**Papel:** Validação de dados, fontes, cobertura, consistência e outputs analíticos.

**Obrigatória quando:** pipelines, bases de dados, enriquecimento, geodados, outputs analíticos, rankings, scores, modelos, dados executivos.

**Lê:**
- CLAUDE.md
- tasks/current_task.md
- context/handoff.md
- DATA_DICTIONARY.md, se existir
- Outputs ou bases relevantes para a tarefa

**Produz:**
- Diagnóstico dos dados
- Cobertura
- Nulos, duplicidades, outliers
- Consistência
- Problemas encontrados
- Riscos de dados
- Recomendação: aprovado / aprovado com ressalvas / reprovado
- Handoff para Metrics Agent ou QA

**Guardrail embutido:**
- Nunca aceitar fonte sem origem documentada.
- Nunca aceitar output apenas porque o código rodou.
- Verificar se pop_hex_base, renda_per_capita e populacao_proxy seguem semântica definida no CLAUDE.md.

---

## Skill 9 — Metrics Agent (Fase 2)

**Fase:** 2
**Papel:** Validação de scores, KPIs, fórmulas, rankings e interpretação executiva.

**Obrigatória quando:** score, ranking, KPI, indicador executivo, métrica de negócio, comparação entre unidades, priorização, modelo decisório.

**Lê:**
- CLAUDE.md (especialmente seção de score oficial)
- tasks/current_task.md
- context/handoff.md
- PRD.md
- Outputs relevantes

**Produz:**
- Métrica ou score avaliado
- Fórmula utilizada
- Coerência da fórmula
- Interpretação correta
- Limitações
- Riscos de uso executivo
- Recomendação: aprovado / aprovado com ressalvas / reprovado
- Handoff para QA

**Guardrail embutido:**
- Verificar obrigatoriamente se score_priorizacao = clip(hex_score_estrutural + ajuste_executivo, 0, 100).
- Verificar pesos: renda=0.40, pop=0.60.
- Nunca aceitar métrica sem fórmula documentada.
- Nunca aceitar score_dominio_hibrido fora de clip(0.60*score_setor + 0.40*residual, 0, 100).

---

## Skill 10 — Frontend Builder (Fase 3)

**Fase:** 3
**Papel:** Especialização do Builder para interfaces, dashboards e componentes Streamlit.

**Lê adicionalmente ao Builder:**
- docs/streamlit_dashboard_m1.md
- docs/design_guidelines.md, se existir

**Valida:**
- Consistência visual com padrões existentes (RESIDUAL_SCORE_BANDS, score_band_to_color)
- Estados vazios, erro e carregamento
- Carga lazy respeitada (não carregar UFs desnecessárias)
- Render lazy de abas (não renderizar abas inativas)

---

## Skill 11 — Backend Builder (Fase 3)

**Fase:** 3
**Papel:** Especialização do Builder para pipelines, jobs, regras de negócio e contratos de dados.

**Lê adicionalmente ao Builder:**
- docs/m1_outputs_oficiais.md
- docs/modelo_mercado_hexagonos.md
- RUNBOOK.md, se existir

**Valida:**
- Contratos de dados (colunas obrigatórias preservadas)
- Parquet output em staging antes de overwrite de produção
- Testes de integração relevantes

---

## Skill 12 — Cybersecurity Agent (Fase 3)

**Fase:** 3
**Acionar apenas quando:** autenticação, autorização, dados sensíveis, credenciais, APIs externas, deploy, logs com dados pessoais, permissões, LGPD.

**Papel:** Avalia riscos de segurança, privacidade e exposição antes de aprovação final.

**Para o contexto atual do projeto:** raramente acionada. O projeto usa dados públicos IBGE, CSVs internos e roda offline. Ativar principalmente se houver evolução para API web, autenticação de usuário ou integração com sistemas externos.

---

## Skill 13 — Designer/UI (Fase 3)

**Fase:** 3
**Acionar apenas quando:** redesenho de telas, nova experiência de usuário, novo produto visual, onboarding de usuários.

**Para o contexto atual:** raramente acionada. O dashboard segue padrões visuais consolidados. Ativar se houver redesenho significativo ou evolução para produto web interno com múltiplos usuários.

---

# MATRIZ DE CRITICIDADE E ESTEIRAS

## Triagem obrigatória

Toda demanda deve ser classificada antes de iniciar. A classificação determina a esteira.

## Baixa criticidade

**Exemplos:** ajuste textual, bug isolado sem impacto em score, atualização de doc, renomeação, comentário de código.

**Esteira Fase 1:**
```
Block Orchestrator → Builder
```

**Esteira Fase 2:**
```
Block Orchestrator → Builder → Documentation Skill (opcional)
```

**Custo:** baixo.

## Média criticidade

**Exemplos:** nova função auxiliar, melhoria localizada em dashboard, novo componente, ajuste em pipeline auxiliar, nova tela simples.

**Esteira Fase 1:**
```
Block Orchestrator → Planner → Builder → QA
```

**Esteira Fase 2:**
```
Block Orchestrator → Planner → Builder → QA → Documentation Skill
```

**Custo:** médio.

## Alta criticidade

**Exemplos:** nova feature, alteração em pipeline principal, mudança em output consumido pelo usuário, mudança em regra de validação, alteração com dependências entre módulos.

**Esteira Fase 1:**
```
Block Orchestrator → Planner → [revisão humana] → Builder → QA
```

**Esteira Fase 2:**
```
Block Orchestrator → Planner → Approver → Builder → QA → Documentation Skill
```

**Esteira Fase 3:**
```
Master Orchestrator → Block Orchestrator → Planner → Approver
→ Frontend Builder ou Backend Builder → QA → Documentation Skill
```

**Custo:** médio/alto.

## Crítica

**Exemplos:** mudança em score_priorizacao, score_dominio_hibrido, score_oportunidade_residual, mudança em métrica executiva, alteração em modelo analítico, mudança em artefato M1, feature usada para tomada de decisão de expansão.

**Esteira Fase 1:**
```
Block Orchestrator → Planner → [aprovação humana obrigatória] → Builder → QA
```

**Esteira Fase 2:**
```
Master Orchestrator → Block Orchestrator → Planner → Approver (humano)
→ Builder → Data Agent → Metrics Agent → QA → Documentation Skill
```

**Custo:** alto, mas obrigatório.

**Nota:** Para tarefas críticas, o Approver DEVE ser o usuário humano. A IA pode estruturar a revisão, mas a aprovação final é humana.

## Estratégica

**Exemplos:** mudança arquitetural, nova fase do projeto, redesenho de produto, mudança de premissas centrais, alteração estrutural de backlog, definição de roadmap.

**Esteira Fase 2+:**
```
Master Orchestrator → Block Orchestrator → Planner → Approver (humano)
→ Builder (se houver implementação) → QA → Documentation Skill
```

**Custo:** alto.

---

# ESTRUTURA DE ARQUIVOS

## Fase 1 — Arquivos a criar

```
/
├── tasks/
│   ├── current_task.md
│   ├── backlog.md
│   └── completed.md
├── context/
│   └── handoff.md
└── prompts/
    ├── block_orchestrator.md
    ├── planner.md
    ├── builder.md
    └── qa_analyzer.md
```

## Fase 2 — Arquivos adicionais

```
/
├── DECISIONS.md               ← migração das decisões do CLAUDE.md
├── tasks/
│   └── blocked.md
├── context/
│   └── active_context.md
└── prompts/
    ├── master_orchestrator.md
    ├── approver.md
    ├── documenter.md
    ├── data_agent.md
    └── metrics_agent.md
```

## Fase 3 — Arquivos adicionais

```
/
├── AGENTS.md                  ← regras universais das Skills
├── ROADMAP.md                 ← visão macro de fases
├── RUNBOOK.md                 ← comandos e procedimentos
├── .claude/
│   └── commands/              ← Skills como slash commands
│       ├── block-orchestrator.md
│       ├── planner.md
│       ├── builder.md
│       ├── qa-analyzer.md
│       ├── master-orchestrator.md
│       ├── approver.md
│       ├── documenter.md
│       ├── data-agent.md
│       └── metrics-agent.md
├── prompts/
│   ├── frontend_builder.md
│   ├── backend_builder.md
│   ├── cybersecurity_agent.md
│   └── designer_ui.md
└── reports/
    ├── execution_logs/
    │   └── .gitkeep
    ├── validation_reports/
    │   └── .gitkeep
    ├── decision_memos/
    │   └── .gitkeep
    ├── data_reports/
    │   └── .gitkeep
    └── quality_reports/
        └── .gitkeep
```

## O que NÃO mudar (arquivos preservados integralmente)

- `CLAUDE.md` — fonte canônica. Não reescrever. Apenas adicionar seção `## Skills` se necessário.
- `PRD.md` — guia operacional. Mantém formato atual.
- `README.md` — documentação geral. Atualizar apenas a seção de fluxo se relevante.
- `docs/` — contratos técnicos existentes. Não mover nem renomear.

---

# TEMPLATES DE ARQUIVOS

## tasks/current_task.md

```markdown
# Current Task

## Bloco atual

ID:
Nome:
Status: em andamento | aguardando aprovação | concluído
Tipo: feature | bug | pipeline | documentação | estrutura | revisão
Criticidade: baixa | média | alta | crítica | estratégica
Esteira: [Skills na sequência]
Skill atual:
Próxima Skill:
Dependências:

## Objetivo

## Escopo permitido

## Fora de escopo

## Arquivos que devem ser lidos

## Arquivos que podem ser alterados

## Critérios de aceite

## Validações obrigatórias

## Riscos

## Handoff esperado

## Próximo passo após conclusão
```

## tasks/backlog.md

```markdown
# Backlog

## Priorização atual

## Tarefas pendentes

### BLK-XXX — [Nome]

Status: pendente | bloqueado
Criticidade: baixa | média | alta | crítica | estratégica
Prioridade: alta | média | baixa
Tipo: feature | bug | pipeline | documentação | estrutura
Skill recomendada:
Resumo:
Dependências:
Observações:
```

## tasks/completed.md

```markdown
# Completed Tasks

## BLK-XXX — [Nome]

Data:
Resumo:
Arquivos alterados:
Validações:
Decisões relacionadas:
Pendências geradas:
```

## context/handoff.md

```markdown
# Handoff

## Skill que gerou este handoff

## Próxima Skill recomendada

## Resultado ou decisão da etapa anterior

## Escopo autorizado

## Fora de escopo

## Arquivos relevantes para próxima Skill

## Critérios de aceite

## Validações necessárias

## Riscos e alertas

## Guardrails ativos

## Pendências
```

## context/active_context.md (Fase 2)

```markdown
# Active Context

## Fase atual

## Foco atual

## Última entrega

## Próxima prioridade

## Decisões recentes relevantes

## Riscos ativos

## Pontos de atenção para Skills
```

## DECISIONS.md (Fase 2)

Começa com a migração das decisões críticas já existentes no CLAUDE.md. Não começa em branco.

```markdown
# DECISIONS.md

## Como usar

Registrar decisões técnicas, estratégicas, arquiteturais, de dados ou de produto.
Cada decisão deve ter: data, contexto, decisão, justificativa, alternativas, impacto, status.

---

## DEC-001 — Score oficial e pesos aprovados

Data: 2026-05-15
Status: aceita e ativa

### Contexto
Decisão de remover trava de faixa etária 18-45 nos inputs do score. Revisão dos pesos.

### Decisão
score_priorizacao = clip(hex_score_estrutural + ajuste_executivo, 0, 100)
hex_score_estrutural = 100 * (0.40 * renda_pct_nacional + 0.60 * pop_pct_nacional)
Inputs: renda_per_capita e populacao_proxy (= pop_total, sem trava etária).
Pesos: renda=0.40, pop=0.60.

### Impacto
Alteração nos scores nacionais. Qualquer mudança nesses pesos exige nova DEC.

---

## DEC-002 — Parâmetros canônicos do M1

Data: 2026-04-01
Status: aceita e ativa

### Decisão
H3_RESOLUTION=7, DIST_MIN_ULTRA_KM=1.0, RENDA_MIN=4500.0, AREA_MIN_M2=1200.0
AREA_IDEAL_MIN_M2=1500.0, AREA_IDEAL_MAX_M2=2000.0, PE_DIREITO_MIN=3.5

### Impacto
Qualquer mudança nesses parâmetros exige nova DEC e aprovação explícita.

---

## DEC-003 — score_dominio_hibrido

Data: 2026-05-21
Status: aceita e ativa

### Decisão
score_dominio_hibrido = clip(0.60*score_setor_2022_calibrado + 0.40*score_oportunidade_residual, 0, 100)
Fallback para componente único se um dos inputs estiver ausente.

---

## DEC-004 — Adoção de orquestração por Skills

Data: [data de adoção]
Status: aceita

### Contexto
Repositório usava modelo single-agent com CLAUDE.md + PRD.md + prompts manuais.
O modelo funcionava mas apresentava riscos de acúmulo de contexto e falta de rastreabilidade.

### Decisão
Adotar estrutura faseada de Skills especializadas, partindo de 4 Skills core (Fase 1)
e expandindo conforme validação real de ciclos.

### Alternativas consideradas
1. Manter single-agent puro.
2. Implementar 14 Skills imediatamente.
3. Adoção faseada com 4 Skills core — escolhida.

### Impacto
Mais organização e rastreabilidade com menor risco de over-engineering inicial.
```

---

# PROMPTS DAS SKILLS

## prompts/block_orchestrator.md

```
Leia CLAUDE.md. Se existir, leia tasks/current_task.md e context/handoff.md.
Leia o trecho relevante do PRD.md apenas se a tarefa exigir regras de produto.

Atue como Block Orchestrator.

Objetivo:
- Aprofundar exclusivamente o bloco informado abaixo.
- Garantir escopo pequeno, claro e executável.
- Eliminar ambiguidade antes de planejamento ou execução.
- Definir arquivos necessários, Skill recomendada e critérios de aceite.

Guardrails obrigatórios:
- Se o bloco envolver score_priorizacao, hex_score_estrutural, artefatos M1,
  carteira, plano curto prazo ou plano de domínio: sinalizar explicitamente
  e classificar como CRÍTICA independentemente de qualquer outra avaliação.
- Não expandir escopo. Não resolver múltiplos blocos.

Regras:
- Não implemente.
- Não altere arquitetura.
- Não avance para outro bloco.
- Seja objetivo e direto.

Saída obrigatória:
1. Bloco refinado
2. Objetivo claro
3. Escopo permitido (lista explícita)
4. Fora de escopo (lista explícita)
5. Arquivos que devem ser lidos
6. Arquivos que podem ser alterados
7. Critérios de aceite
8. Criticidade classificada: baixa | média | alta | crítica | estratégica
9. Esteira recomendada
10. Próxima Skill recomendada
11. Riscos identificados

Ao final:
- Atualize tasks/current_task.md.
- Atualize context/handoff.md com escopo autorizado, fora de escopo, arquivos,
  critérios de aceite, criticidade e próxima Skill.
- Gere resumo curto e objetivo.
```

## prompts/planner.md

```
Leia CLAUDE.md. Leia tasks/current_task.md e context/handoff.md.
Leia os arquivos-alvo listados no handoff.
Se a tarefa envolver dados, leia docs/m1_outputs_oficiais.md ou docs/modelo_mercado_hexagonos.md
conforme relevante.

Atue como Planner.

Objetivo:
- Transformar o bloco atual em plano técnico claro e executável.
- Mapear arquivos afetados com precisão.
- Identificar dependências e riscos.
- Definir validações obrigatórias.

Guardrails obrigatórios:
- Se o plano tocar score_priorizacao, hex_score_estrutural ou artefatos M1,
  indicar OBRIGATORIAMENTE que a execução exige aprovação humana antes do Builder.
- Parâmetros canônicos: H3_RESOLUTION=7, DIST_MIN_ULTRA_KM=1.0, RENDA_MIN=4500.0.
  Não alterar esses valores sem registrar DEC.
- Staging sempre em Parquet. CSVs locais: sep=";", encoding="utf-8-sig".

Regras:
- Não implemente.
- Não altere código.
- Não expanda escopo sem registrar decisão.
- Se a tarefa for grande demais, divida em blocos menores.

Saída obrigatória:
1. Entendimento da tarefa
2. Plano técnico em etapas numeradas
3. Arquivos afetados (caminho exato)
4. Dependências
5. Riscos técnicos
6. Critérios de aceite finais
7. Validações obrigatórias (comandos exatos quando possível)
8. Fora de escopo
9. Skill recomendada para construção
10. Handoff para Approver ou Builder

Ao final:
- Atualize tasks/current_task.md.
- Atualize context/handoff.md.
- Se houver decisão técnica relevante e DECISIONS.md existir, registre.
- Gere resumo curto e objetivo.
```

## prompts/builder.md

```
Leia CLAUDE.md. Leia tasks/current_task.md e context/handoff.md.
Leia apenas os arquivos-alvo listados no handoff. Não leia o repositório inteiro.

Atue como Builder.

Objetivo:
- Executar apenas o bloco aprovado conforme escopo do handoff.
- Fazer mudanças mínimas, controladas e rastreáveis.
- Rodar validações aplicáveis.
- Preparar handoff para QA.

Guardrails INVIOLÁVEIS:
- NUNCA alterar score_priorizacao, hex_score_estrutural, carteira, plano curto prazo,
  plano domínio ou qualquer artefato oficial do M1 sem aprovação explícita do usuário
  documentada no handoff.
- NUNCA criar dependência de API ao vivo no dashboard de produção.
- NUNCA sobrescrever parquets de produção sem staging intermediário.
- Toda mudança em camada de dados deve preservar 100% das linhas e colunas do M1.
- Staging sempre em Parquet. CSVs locais: sep=";", encoding="utf-8-sig".
- Exceção de legado: data/ultra/Ultra.csv usa sep=";", encoding="latin-1",
  1 linha de metadado antes do cabeçalho.

Regras operacionais:
- Execute apenas um bloco.
- Não execute fora do escopo do handoff.
- Não refatore sem necessidade.
- Não altere regra de negócio sem decisão registrada.
- Não avance para outro bloco.
- Se houver bloqueio, pare e reporte antes de continuar.

Validação obrigatória antes de gerar handoff:
- Rodar: python -m pytest -q tests/integration/test_streamlit_app.py
- Se alterar pipelines, rodar testes relevantes de staging.
- Registrar resultado completo (passed/failed/skipped).

Saída obrigatória:
1. Bloco executado
2. O que foi feito (resumo técnico)
3. Arquivos alterados (lista exata)
4. Validações executadas e resultado
5. Problemas encontrados
6. Pendências
7. Riscos remanescentes
8. Handoff para QA/Quality Analyzer

Ao final:
- Atualize tasks/current_task.md.
- Atualize context/handoff.md.
- Se houver mudança de estado relevante, sinalize para atualização do CLAUDE.md.
- Gere resumo curto e objetivo.
```

## prompts/qa_analyzer.md

```
Leia CLAUDE.md. Leia tasks/current_task.md e context/handoff.md.
Leia os arquivos alterados pelo Builder.
Leia os logs de teste e outputs gerados.

Atue como QA/Quality Analyzer.

Objetivo:
- Auditar criticamente a entrega.
- Verificar aderência ao escopo do handoff.
- Validar critérios de aceite.
- Identificar problemas por severidade.
- Emitir veredito fundamentado.

Guardrails obrigatórios:
- Verificar EXPLICITAMENTE se score_priorizacao, hex_score_estrutural e artefatos M1
  não foram alterados se a tarefa era em camada paralela.
- Não emitir aprovação sem log de teste verde (pytest passou).
- Não aceitar "o código rodou" como evidência de qualidade.
- Verificar se o escopo do handoff foi respeitado (nada a mais, nada a menos).

Regras:
- Não implemente novas features.
- Não aprove sem evidência verificável.
- Não ignore fora de escopo.
- Classifique problemas por severidade: crítico (bloqueador) | médio | leve.

Saída obrigatória:
1. Veredito: aprovado | aprovado com ressalvas | reprovado
2. Justificativa
3. Problemas críticos (lista com impacto)
4. Problemas médios (lista)
5. Melhorias opcionais
6. Testes faltantes
7. Riscos remanescentes
8. Decisão recomendada (fechar ciclo | criar bloco de correção | reabrir)
9. Handoff para Documentation Skill (Fase 2) ou instrução de fechamento manual

Ao final:
- Atualize tasks/current_task.md.
- Se criar correção, adicione à tasks/backlog.md.
- Atualize context/handoff.md.
- Gere resumo curto e objetivo.
```

## prompts/master_orchestrator.md (Fase 2)

```
Leia CLAUDE.md. Leia tasks/backlog.md, tasks/current_task.md, tasks/completed.md.
Se existir, leia context/active_context.md e DECISIONS.md.
Leia PRD.md apenas se necessário para entender uma regra específica.

Atue como Master Orchestrator.

Objetivo:
- Avaliar estado geral do projeto.
- Priorizar backlog com base em valor de negócio, risco e dependências.
- Definir qual tarefa avançar.
- Classificar criticidade e esteira.
- Garantir alinhamento com decisões existentes.

Regras:
- Não implemente código.
- Não entre em detalhe técnico profundo.
- Não selecione múltiplas tarefas para execução simultânea.
- Uma tarefa ativa por vez.

Saída obrigatória:
1. Diagnóstico do estado atual
2. Tarefa mais importante
3. Justificativa da prioridade
4. Criticidade classificada
5. Esteira recomendada
6. Próxima Skill
7. Riscos e dependências
8. Atualizações necessárias no backlog

Ao final:
- Atualize tasks/current_task.md com a tarefa selecionada.
- Atualize tasks/backlog.md se necessário.
- Atualize context/handoff.md.
- Se existir context/active_context.md, atualize.
- Gere resumo curto e objetivo.
```

## prompts/approver.md (Fase 2)

```
Leia CLAUDE.md. Leia tasks/current_task.md e context/handoff.md.
Leia PRD.md trecho relevante. Se existir, leia DECISIONS.md.

Atue como Approver.

Objetivo:
- Revisar plano, escopo e riscos antes da execução.
- Garantir que a construção não comece com ambiguidade.
- Emitir veredito formal.

Guardrails obrigatórios:
- NUNCA aprovar mudança em score_priorizacao, hex_score_estrutural ou artefatos M1
  sem que o usuário humano tenha lido e confirmado explicitamente.
- Reprovar qualquer plano que viole os guardrails do CLAUDE.md.
- Não aprovar plano sem critérios de aceite definidos.

Regras:
- Não implemente.
- Não crie feature.
- Não ignore risco de dados, score ou negócio.
- Seja crítico e objetivo.

Saída obrigatória:
1. Veredito: aprovado | aprovado com ressalvas | reprovado
2. Justificativa
3. Ajustes obrigatórios (se houver)
4. Riscos aceitos
5. Riscos não aceitos
6. Skill de construção autorizada
7. Condições para execução
8. Handoff para Builder

Ao final:
- Atualize context/handoff.md com veredito e condições.
- Se existir DECISIONS.md, registre a decisão se relevante.
- Atualize tasks/current_task.md com status.
- Gere resumo curto e objetivo.
```

## prompts/documenter.md (Fase 2)

```
Leia CLAUDE.md. Leia tasks/current_task.md, tasks/backlog.md, tasks/completed.md.
Leia context/handoff.md. Se existir, leia DECISIONS.md.
Leia os arquivos alterados na última tarefa.

Atue como Documentation Skill.

Objetivo:
- Consolidar documentação após o ciclo.
- Atualizar contexto operacional.
- Reduzir excesso de contexto.
- Garantir rastreabilidade.
- Preparar o projeto para o próximo ciclo.

Regras:
- Não implemente código.
- Não altere regra de negócio.
- Não invente histórico.
- Não transforme CLAUDE.md em relatório longo.
- Não duplique conteúdo entre arquivos.
- CLAUDE.md deve permanecer curto e operacional.

Responsabilidades:
1. Atualizar CLAUDE.md: apenas seção de estado atual e última entrega.
2. Mover tarefa concluída de tasks/current_task.md para tasks/completed.md.
3. Atualizar tasks/backlog.md com próximos blocos.
4. Se existir DECISIONS.md: registrar decisão se houver.
5. Atualizar context/active_context.md se existir.
6. Limpar context/handoff.md para próximo ciclo.

Saída obrigatória:
1. Arquivos documentais atualizados (lista)
2. O que foi consolidado
3. O que foi removido ou enxugado
4. Pendências de documentação
5. Próximo bloco recomendado
6. Resumo final curto

Ao final:
- CLAUDE.md atualizado.
- context/handoff.md limpo.
- Gere resumo curto e objetivo.
```

## prompts/data_agent.md (Fase 2)

```
Leia CLAUDE.md (especialmente seção de variáveis IBGE e semântica de colunas).
Leia tasks/current_task.md e context/handoff.md.
Leia os outputs ou bases relevantes para a tarefa.

Atue como Data Agent.

Objetivo:
- Validar fontes, dados, cobertura, consistência, nulos, duplicidades e outputs.
- Avaliar se os dados estão aptos para uso técnico ou executivo.

Semântica IBGE obrigatória (verificar sempre):
- v0001 = Total de pessoas
- v0002 = Total de domicílios
- v0007 = Domicílios Particulares Ocupados
- v0005 = média de moradores
- pop_hex_base: usa pop_total_setor_2022 quando disponível; fallback populacao_proxy/total_hex_municipio

Guardrails obrigatórios:
- Nunca aceitar fonte sem origem documentada.
- Nunca aceitar output apenas porque o código rodou.
- Verificar se parâmetros canônicos (H3_RESOLUTION=7, DIST_MIN_ULTRA_KM=1.0) foram preservados.
- Verificar cobertura de renda: RR tem cobertura reduzida por supressão IBGE (65,8%).

Regras:
- Não altere regra de negócio.
- Não esconda fragilidade dos dados.
- Seja crítico e objetivo.

Saída obrigatória:
1. Diagnóstico dos dados
2. Cobertura (por UF se relevante)
3. Nulos (colunas críticas)
4. Duplicidades
5. Outliers
6. Consistência com semântica esperada
7. Problemas encontrados
8. Riscos de dados
9. Recomendação: aprovado | aprovado com ressalvas | reprovado
10. Ajustes recomendados
11. Handoff para Metrics Agent ou QA

Ao final:
- Atualize context/handoff.md.
- Gere resumo curto e objetivo.
```

## prompts/metrics_agent.md (Fase 2)

```
Leia CLAUDE.md (especialmente seção de score oficial e guardrails).
Leia tasks/current_task.md e context/handoff.md.
Leia PRD.md trecho relevante.
Leia outputs relevantes para a validação.

Atue como Metrics Agent.

Objetivo:
- Validar scores, KPIs, fórmulas, rankings e interpretação executiva.
- Avaliar coerência analítica e risco de uso executivo.

Fórmulas canônicas a verificar (quando aplicável):
- score_priorizacao = clip(hex_score_estrutural + ajuste_executivo, 0, 100)
- hex_score_estrutural = 100 * (0.40 * renda_pct_nacional + 0.60 * pop_pct_nacional)
- score_dominio_hibrido = clip(0.60 * score_setor_2022_calibrado + 0.40 * score_oportunidade_residual, 0, 100)
- Faixas de cor: RESIDUAL_SCORE_BANDS em 10 pontos (0-10 a 90-100)
- Pesos: renda=0.40, pop=0.60 (DEC-001, imutável sem nova DEC)

Guardrails obrigatórios:
- Nunca aceitar métrica sem fórmula documentada.
- Nunca aceitar score sem premissa documentada.
- Nunca aceitar ranking sem critério de desempate.
- Nunca aprovar alteração de peso sem DEC registrada.

Regras:
- Não altere fórmula sem decisão registrada.
- Não esconda limitações.
- Seja crítico e objetivo.

Saída obrigatória:
1. Métrica ou score avaliado
2. Fórmula utilizada
3. Coerência da fórmula com canônico
4. Interpretação correta
5. Limitações conhecidas
6. Riscos de uso executivo
7. Recomendação: aprovado | aprovado com ressalvas | reprovado
8. Ajustes recomendados
9. Handoff para QA

Ao final:
- Atualize context/handoff.md.
- Se existir DECISIONS.md e houver decisão, registre.
- Gere resumo curto e objetivo.
```

---

# GUIA OPERACIONAL COMPLETO

## Como executar um ciclo — Fluxo mínimo (baixa criticidade)

```
1. Abrir Claude Code. Garantir contexto limpo (/clear se necessário).
2. Colar conteúdo de prompts/block_orchestrator.md + descrever o bloco.
3. Revisar output. Verificar context/handoff.md gerado.
4. Colar conteúdo de prompts/builder.md.
   Builder executa e atualiza context/handoff.md.
5. Revisar arquivos alterados.
6. Atualizar tasks/ manualmente (mover para completed).
```

## Como executar um ciclo — Fluxo padrão (média/alta criticidade)

```
1. Abrir Claude Code. /clear.
2. Invocar Block Orchestrator → revisar handoff.
3. [Nova sessão ou /clear]
4. Invocar Planner → revisar plano técnico no handoff.
5. Para alta criticidade: revisar o plano como usuário antes de prosseguir.
6. [Nova sessão ou /clear]
7. Invocar Builder → revisar alterações e logs de teste.
8. [Nova sessão ou /clear]
9. Invocar QA → revisar veredito.
10. Fechar ciclo: atualizar tasks/ e context/.
```

## Como executar um ciclo — Fluxo crítico (crítica/estratégica)

```
1. Abrir Claude Code. /clear.
2. [Fase 2] Invocar Master Orchestrator → definir tarefa e esteira.
3. [Nova sessão]
4. Invocar Block Orchestrator → revisar handoff.
5. [Nova sessão]
6. Invocar Planner → revisar plano técnico.
7. PAUSA OBRIGATÓRIA: usuário lê o plano e handoff.
   Se a tarefa envolver score/M1, aprovação é do humano.
8. [Fase 2] Invocar Approver para formalizar veredito.
9. [Nova sessão]
10. Invocar Builder → revisar alterações e testes.
11. Se envolver dados: [Nova sessão] Invocar Data Agent.
12. Se envolver score/KPI: [Nova sessão] Invocar Metrics Agent.
13. [Nova sessão]
14. Invocar QA → revisar veredito.
15. [Fase 2] Invocar Documentation Skill para fechar ciclo.
```

## Regras de sessão

- Cada Skill deve idealmente rodar em sessão com contexto limpo.
- Usar `/clear` entre Skills garante que o agente lê apenas o que o prompt especifica.
- Se a tarefa for simples e o contexto for pequeno, múltiplas Skills podem rodar na mesma sessão.
- O handoff em `context/handoff.md` é o mecanismo de continuidade entre sessões.

## Quando usar nova sessão vs continuar

| Situação | Ação |
|---|---|
| Passagem entre Skills de esteiras diferentes | Nova sessão + /clear |
| Aprovação humana intermediária | Pausa + nova sessão |
| Mesmo ciclo, Skills sequenciais simples | Pode continuar na mesma sessão |
| Após Builder rodar testes | Avaliar contexto antes de invocar QA |

---

# GUIA DE MIGRAÇÃO DO ESTADO ATUAL

## O que fazer primeiro (Fase 1)

1. Criar as pastas `tasks/` e `context/` e `prompts/`.
2. Criar os 4 arquivos de prompt: block_orchestrator.md, planner.md, builder.md, qa_analyzer.md.
3. Criar tasks/current_task.md, tasks/backlog.md, tasks/completed.md, context/handoff.md.
4. Migrar o backlog atual do PRD.md para tasks/backlog.md.
5. NÃO alterar CLAUDE.md, PRD.md, README.md nem nenhum arquivo de código.
6. Executar um ciclo real usando a nova estrutura para validar.

## O que fazer na Fase 2 (após validação)

1. Criar DECISIONS.md com as decisões já documentadas (DEC-001 a DEC-003 no mínimo).
2. Criar context/active_context.md com estado atual.
3. Criar tasks/blocked.md.
4. Criar os 5 prompts adicionais.
5. Opcionalmente: adicionar seção `## Skills` ao CLAUDE.md referenciando a estrutura.

## O que NÃO fazer na migração

- Não reescrever CLAUDE.md do zero.
- Não mover docs/ existentes para nova estrutura.
- Não criar ARCHITECTURE.md, DATA_DICTIONARY.md ou VALIDATION.md como documentos formais até ter conteúdo real para preencher.
- Não implementar as 3 fases ao mesmo tempo.

---

# REGRAS DE OPERAÇÃO

## Regra 1 — Toda demanda é classificada antes de iniciar

Classificar criticidade (baixa/média/alta/crítica/estratégica) e definir esteira antes de abrir qualquer sessão.

## Regra 2 — Uma tarefa ativa por vez

tasks/current_task.md contém apenas uma tarefa ativa. O restante fica em backlog.

## Regra 3 — Handoff é obrigatório entre Skills

Toda Skill que prepara trabalho para outra Skill deve atualizar context/handoff.md antes de encerrar.

## Regra 4 — Contexto seletivo

Cada Skill lê apenas os arquivos definidos no seu prompt. Não carregar o repositório inteiro.

## Regra 5 — Aprovação humana antes de execução crítica

Para tarefas críticas (score, artefatos M1, ranking, métrica executiva), o usuário deve ler e aprovar o plano antes do Builder executar.

## Regra 6 — Dados e métricas exigem validação especializada (Fase 2)

Acionar Data Agent e/ou Metrics Agent quando houver: score, ranking, KPI, indicador executivo, output analítico, decisão de negócio baseada em dados.

## Regra 7 — Testes são evidência, não formalidade

O QA não aprova sem log de teste. pytest verde é condição necessária (não suficiente) para aprovação.

## Regra 8 — Documentação fecha o ciclo

Tasks, handoff e CLAUDE.md são atualizados ao final de cada ciclo, não durante.

## Regra 9 — Guardrails não têm exceção

Os guardrails do CLAUDE.md (score_priorizacao, artefatos M1, offline, sep/encoding) valem para todas as Skills em todas as fases.

## Regra 10 — A estrutura evolui conforme necessidade real

Não criar Fase 2 antes de validar Fase 1. Não criar Fase 3 antes de validar Fase 2.

---

# PRIMEIRO BACKLOG

## BLK-001 — Implementar estrutura Fase 1

Status: pendente
Criticidade: alta
Prioridade: alta
Tipo: estrutura
Skill recomendada: Builder (sem esteira completa — bootstrap da própria estrutura)

Objetivo:
Criar arquivos, pastas e prompts da Fase 1. Validar com um ciclo real.

Critérios de aceite:
- tasks/ criada com current_task.md, backlog.md, completed.md.
- context/ criada com handoff.md.
- prompts/ criada com 4 prompts das Skills essenciais.
- Nenhum arquivo de código ou CLAUDE.md foi alterado.
- Um ciclo real usando a estrutura foi executado e documentado.
- Problemas encontrados no ciclo piloto foram registrados em tasks/backlog.md.

## BLK-002 — Ciclo piloto com estrutura Fase 1

Status: pendente (depende de BLK-001)
Criticidade: média
Prioridade: alta
Tipo: operação
Skill recomendada: Block Orchestrator → Planner → Builder → QA

Objetivo:
Selecionar uma tarefa real do projeto e executar o primeiro ciclo usando a Fase 1.
O objetivo é validar que o modelo funciona na prática, não apenas como estrutura.

Critérios de aceite:
- Tarefa real do backlog executada.
- Handoff usado entre pelo menos 2 Skills.
- QA emitiu veredito formal.
- Problemas de atrito no fluxo foram registrados.
- Tasks/ atualizadas ao final.

## BLK-003 — Implementar Fase 2 (após BLK-002 validado)

Status: pendente (depende de BLK-002)
Criticidade: alta
Prioridade: média
Tipo: estrutura
Skill recomendada: Builder

Objetivo:
Criar DECISIONS.md (com migração das decisões existentes), context/active_context.md,
tasks/blocked.md e 5 prompts adicionais (Master Orchestrator, Approver, Documentation,
Data Agent, Metrics Agent).

Critérios de aceite:
- DECISIONS.md com DEC-001 a DEC-003 migrados do CLAUDE.md.
- Novos prompts criados.
- context/active_context.md preenchido com estado atual.
- CLAUDE.md não foi reescrito (apenas atualizado se necessário).

---

# CRITÉRIOS DE ACEITE DA IMPLEMENTAÇÃO DA FASE 1

A Fase 1 só é considerada concluída se:

- [ ] tasks/ existe com current_task.md, backlog.md, completed.md.
- [ ] context/ existe com handoff.md.
- [ ] prompts/ existe com 4 prompts das Skills essenciais.
- [ ] Nenhum arquivo de código foi alterado.
- [ ] CLAUDE.md não foi reescrito — apenas estendido se necessário.
- [ ] PRD.md não foi alterado.
- [ ] Um ciclo real foi executado usando pelo menos 2 Skills.
- [ ] O handoff funcionou como mecanismo de continuidade entre sessões.
- [ ] Problemas encontrados no ciclo piloto foram registrados.
- [ ] O agente reportou o que foi criado, o que não foi criado e por quê.

---

# CHECKLIST DE ACEITE POR CICLO

Para cada ciclo executado com a nova estrutura:

- [ ] Criticidade foi classificada antes de iniciar.
- [ ] Esteira correta foi seguida para a criticidade.
- [ ] Block Orchestrator delimitou escopo explícito.
- [ ] Fora de escopo foi respeitado pelo Builder.
- [ ] Guardrails do CLAUDE.md foram verificados.
- [ ] Testes rodaram e o resultado está documentado.
- [ ] QA emitiu veredito com justificativa.
- [ ] Handoff foi gerado e atualizado entre Skills.
- [ ] Tasks/ foram atualizadas ao final.
- [ ] CLAUDE.md foi atualizado se houve mudança de estado.

---

# NOTAS FINAIS

## Sobre o caminho para autonomia

O objetivo final é ter Skills que se invocam automaticamente via handoff, sem intervenção manual para tarefas de criticidade baixa e média. O caminho é:

1. **Hoje**: prompt manual + /clear entre Skills.
2. **Fase 2**: prompts em .claude/commands/ como slash commands.
3. **Fase 3**: loop de orquestrador que lê handoff e invoca próxima Skill automaticamente.
4. **Autonomia completa**: apenas tarefas críticas e estratégicas requerem aprovação humana.

## Sobre o CLAUDE.md

O CLAUDE.md existente não precisa ser reescrito. Ele já cumpre bem seu papel como fonte canônica. A única adição recomendada é uma seção curta `## Skills` que referencia este arquivo e a estrutura de tasks/ e prompts/ quando eles existirem.

## Sobre a expansão das Skills

Cybersecurity Agent e Designer/UI existem no modelo completo mas não devem ser criados antes de existir uma necessidade real no projeto. O Motor de Expansão atual usa dados públicos e roda offline — o Cybersecurity Agent raramente seria acionado. Designer/UI só faz sentido se houver redesenho significativo do produto.

## Sobre DECISIONS.md

O DECISIONS.md não começa do zero. Começa com a migração das decisões críticas já tomadas e documentadas no CLAUDE.md. Esse é o único jeito de garantir que o histórico não se perde na transição.
