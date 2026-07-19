# PLANO-ORQ-V2 — Arquitetura de Agentes v2 (Motor de Expansão / DEG)

> **Status:** proposta aprovada para implantação · **Owner:** Felipe (Tech Lead DEG)
> **Objetivo:** eliminar o gate humano único, paralelizar execução e ativar trabalho autônomo 24h — mantendo os guardrails permanentes (M1 read-only, loop_guard, QA no modelo forte, deploy manual por digest).
>
> Este documento é auto-contido e escrito para ser executado por agentes (Claude Code) bloco a bloco, seguindo o padrão da casa: 1 bloco = 1 branch `ciclo/<ID>` = 1 PR = 1 tarefa ClickUp.

---

## 0. Diagnóstico (por que este plano existe)

| Dor | Causa raiz | Solução neste plano |
|---|---|---|
| Trabalho paralisado esperando 1 agente terminar | 1 sessão = 1 bloco por vez, mesmo em arquivos diferentes | Worktrees paralelas (BLK-ORQ-14) |
| Backlog fica para trás sem execução/revisão automática | Loop autônomo depende de alguém "ligar" | Routine garimpeiro na nuvem (BLK-ORQ-13) |
| Pesquisas rasas | Modelo/arquitetura de pesquisa single-shot | Painel multiagente + Deep Research (BLK-ORQ-17) |
| Time parado em gates desnecessários | Todo output converge para o Felipe; permissão pedida comando a comando | DEC-016 + allowlist + Plan Mode (BLK-ORQ-10/11) |

---

## 1. DEC-016 — Matriz de Autonomia por Criticidade

> **Texto pronto para o CLAUDE.md §8 (ou DECISIONS.md quando BLK-ORQ-02 migrar).**

**DEC-016 — Matriz de Autonomia por Criticidade**

- **Evidência:** o gate humano único (Felipe) é o gargalo dominante da esteira; blocos aprovados ficam dias/semanas em fila (caso BLK-TP-09). Revisão automatizada por agente + CI verde cobre o risco de blocos de baixa criticidade.
- **O que muda:** a aprovação deixa de ser "Felipe por padrão" e passa a ser função da criticidade do bloco:

| Criticidade | Executa | Revisa | Aprova/Merge | Deploy |
|---|---|---|---|---|
| **Baixa** (loop-safe) | Agente (local ou routine) | Code Review app + QA agente | **Automático** se CI verde + 0 achados de severidade alta | Manual (Felipe) |
| **Média** | Agente | Code Review app + QA agente | **Humano em 5 min** (lê resumo + achados, não o diff inteiro) — Felipe, Vini ou Juan conforme domínio | Manual (Felipe) |
| **Alta** | Agente com gate pré-Builder | Painel (QA + Code Review) | **Humano por domínio**: Vini (dashboard/PDF/scrapers), Juan (API/bot), Felipe (demais) | Manual (Felipe) |
| **Crítica** (M1, fórmulas, pesos, config.py, deploy, segredos, CI) | Agente somente após DEC + plano aprovado | Painel completo | **Somente Felipe** + DEC registrada | Manual (Felipe) |

- **O que fica intocado:** M1 read-only por padrão; loop_guard aborta diffs em M1/config/deploy/segredos/CI; suíte FULL como gate único sem bypass; QA sempre no modelo mais forte; deploy por digest sempre manual; NO-GO segue sendo desfecho válido.
- **Gatilho de reabertura:** 2 incidentes causados por merge automático em janela de 90 dias → merge automático de Baixa é suspenso e a DEC é revisada.

---

## 2. Fase 0 — Destravar o gate (Sprint 1)

### BLK-ORQ-10 — Instalar e calibrar Code Review app

| Campo | Valor |
|---|---|
| Criticidade | Média |
| Prioridade | P0 |
| Esteira | /run-cycle |
| Status | Backlog |
| Dependências | Nenhuma |
| Autonomia | Agente executa; Felipe instala o GitHub App (ação de conta) |

**Escopo:**
1. Felipe instala o Claude GitHub App no repo `motor-de-expansao` e ativa Code Review em modo automático (review a cada push de PR).
2. Agente cria `REVIEW.md` na raiz calibrando a revisão. Conteúdo mínimo:

```markdown
# REVIEW.md — critérios de revisão automatizada

## Bloqueadores (severidade alta)
- Qualquer diff em src/motor_expansao/pipelines/m1/**, config.py, Dockerfile*, .github/workflows/** sem DEC referenciada na descrição do PR
- Leitura de NAO_ABRA/** ou introdução de PII em staging/outputs
- Validação in-sample (R² sem out-of-fold) — viola DEC-008
- Chamada de rede em código do dashboard sem DEC aprovando exceção
- Alteração de contrato de export BI sem atualização de teste

## Atenção (severidade média)
- Mudança sem teste correspondente
- CSV fora do padrão sep=";" encoding utf-8-sig
- Acentuação em identificadores (permitida apenas em texto de usuário)
- Dependência nova fora do constraints.txt

## Estilo do relatório
- Resumo executivo em 3 linhas no topo (o aprovador lê isto, não o diff)
- Referenciar DECs por número quando aplicável
```

**Critérios de aceite:** PR de teste aberto recebe review automático com comentários inline; achado de severidade alta em arquivo M1 é corretamente sinalizado como bloqueador.

---

### BLK-ORQ-11 — Allowlist de permissões + Plan Mode padrão

| Campo | Valor |
|---|---|
| Criticidade | Média |
| Prioridade | P0 |
| Esteira | /run-cycle |
| Status | Backlog |
| Dependências | Nenhuma |
| Autonomia | Agente executa integralmente |

**Escopo:** criar/atualizar `.claude/settings.json` (versionado) do repo:

```json
{
  "permissions": {
    "allow": [
      "Bash(pytest*)",
      "Bash(python -m pytest*)",
      "Bash(ruff*)",
      "Bash(mypy*)",
      "Bash(git status)",
      "Bash(git diff*)",
      "Bash(git log*)",
      "Bash(git add*)",
      "Bash(git worktree list)",
      "Bash(uv pip list*)",
      "Read(./src/**)",
      "Read(./tests/**)",
      "Read(./docs/**)",
      "Read(./tasks/**)"
    ],
    "deny": [
      "Bash(ssh*)",
      "Bash(scp*)",
      "Bash(docker*)",
      "Bash(gh workflow run*)",
      "Read(./NAO_ABRA/**)",
      "Read(./.env*)",
      "Write(./src/motor_expansao/pipelines/m1/**)",
      "Write(./config.py)",
      "Write(./.github/**)"
    ]
  }
}
```

> Nota: `Write` em M1/config/CI negado **por padrão** — blocos Críticos com DEC aprovada usam sessão com override explícito e consciente (`/permissions`), nunca o default.

Adicionar ao `CLAUDE.md` a convenção operacional: *"Todo bloco começa em Plan Mode. O plano ancorado em file:line é apresentado e aprovado UMA vez; a execução segue sem novos pedidos de permissão para comandos da allowlist."*

**Critérios de aceite:** sessão de teste roda `pytest` e `ruff` sem prompt de permissão; tentativa de `ssh` ou leitura de `NAO_ABRA/` é bloqueada; arquivo versionado e documentado no CLAUDE.md.

---

### BLK-ORQ-12 — Routine "Zelador" (semanal, nuvem)

| Campo | Valor |
|---|---|
| Criticidade | Baixa |
| Prioridade | P0 |
| Esteira | Configuração manual (claude.ai → Routines) + bloco de doc |
| Status | Backlog |
| Dependências | GitHub App instalado (BLK-ORQ-10) |
| Autonomia | Felipe configura (1x); routine roda sozinha depois |

**Prompt da routine (agendar: segundas 07:00 BRT):**

```
Você é o Zelador do repo motor-de-expansao. Toda segunda:
1. Liste branches ciclo/* e claude/* sem PR aberto há mais de 3 dias.
2. Compare tasks/backlog.md e tasks/completed.md com o estado real:
   blocos marcados como concluídos sem nota de CONCLUSÃO, blocos em
   execução sem branch correspondente.
3. Liste PRs abertos há mais de 5 dias sem merge, com o motivo aparente
   (CI vermelho, aguardando aprovação, conflito).
4. NÃO altere nada. Apenas produza um relatório curto em português com
   no máximo 15 linhas, formato: [ITEM] → [AÇÃO SUGERIDA] → [DONO].
5. Poste o relatório como issue no repo com título
   "Zelador — semana <data>" e label "ops".
```

> A notificação chega ao Telegram de ops via o alerta de issues já existente (ou adicionar webhook issue→Telegram como sub-tarefa).

**Critérios de aceite:** primeira execução identifica corretamente pelo menos os casos conhecidos (padrão BLK-TP-09: branch aprovada sem PR); issue criada com formato correto.

---

### BLK-ORQ-13 — Routine "Garimpeiro" (noturna, nuvem)

| Campo | Valor |
|---|---|
| Criticidade | Alta (configura execução autônoma) |
| Prioridade | P0 |
| Esteira | Gate humano pré-ativação (Felipe revisa o prompt e o escopo) |
| Status | Backlog |
| Dependências | BLK-ORQ-10, BLK-ORQ-11, DEC-016 registrada |
| Autonomia | Após ativação, roda sozinha; só executa blocos `loop-safe` |

**Prompt da routine (agendar: diária 02:00 BRT):**

```
Você é o Garimpeiro do repo motor-de-expansao. Toda noite:
1. Leia CLAUDE.md integralmente (regras e DECs) e tasks/backlog.md.
2. Selecione o PRIMEIRO bloco com marcador explícito "loop-safe" e
   status pendente, sem dependências abertas. Se não houver, encerre
   informando "fila vazia".
3. Execute o bloco seguindo os critérios de aceite dele.
   REGRAS INVIOLÁVEIS:
   - NUNCA modifique src/motor_expansao/pipelines/m1/**, config.py,
     Dockerfile*, .github/**, segredos ou qualquer artefato de deploy.
   - NUNCA acesse rede externa além de clonar o repo.
   - Consuma apenas dados de staging.
4. Rode a suíte COMPLETA de testes + ruff + mypy.
5. Se TUDO verde: commit na branch claude/<ID-do-bloco>, abra PR com a
   nota de CONCLUSÃO no corpo (padrão do bloco) e o resumo dos testes.
6. Se algo falhar: NÃO abra PR. Abra issue "Garimpeiro — diagnóstico
   <ID>" com o diagnóstico e o log resumido.
7. Nunca faça merge. Nunca toque em main.
```

**Passo de processo associado (adicionar ao ritual de backlog de segunda):** revisar em lote quais blocos novos recebem o marcador `loop-safe` (critério inalterado: READ-ONLY M1, sem VPS/rede/PII, consome só staging, não é PoC visual).

**Critérios de aceite:** rodada supervisionada (Felipe assiste a primeira execução) conclui 1 bloco loop-safe real com PR correto; rodada com bloco projetado para falhar gera issue de diagnóstico e nenhum PR.

**Nota de orçamento:** routines/uso programático podem consumir pool de créditos separado da assinatura (verificar em Configurações → Uso). Monitorar consumo na primeira quinzena e registrar no bloco.

---

## 3. Fase 1 — Paralelismo distribuído (Sprint 2)

### BLK-ORQ-14 — Worktrees como prática padrão

| Campo | Valor |
|---|---|
| Criticidade | Baixa |
| Prioridade | P1 |
| Esteira | /run-cycle |
| Status | Backlog |
| Dependências | BLK-ORQ-11 |
| Autonomia | Agente executa integralmente |

**Escopo:**
1. Criar `scripts/worktree_bloco.sh`:

```bash
#!/usr/bin/env bash
# Uso: ./scripts/worktree_bloco.sh BLK-REV-03
set -euo pipefail
ID="$1"
WT=~/wt/"${ID,,}"
git worktree add "$WT" -b "ciclo/${ID}" 2>/dev/null || git worktree add "$WT" "ciclo/${ID}"
echo "Worktree pronta: $WT"
echo "Próximo passo: cd $WT && claude"
```

2. Criar `scripts/worktree_limpar.sh` (remove worktrees de branches já mergeadas).
3. Documentar no `CLAUDE.md` a convenção: **cada pessoa mantém 2–3 blocos em voo** (1 ativo em execução + 1–2 em revisão/especificação); worktree é obrigatória para o segundo bloco simultâneo em diante.

**Critérios de aceite:** dois blocos reais executados em paralelo por worktrees sem conflito; scripts com testes de fumaça; doc atualizada.

---

### BLK-ORQ-15 — Três esteiras por domínio

| Campo | Valor |
|---|---|
| Criticidade | Média (organizacional) |
| Prioridade | P1 |
| Esteira | Decisão de gestão (Felipe) + bloco de doc |
| Status | Backlog |
| Dependências | DEC-016 |
| Autonomia | Humana |

**Escopo:** formalizar no `CLAUDE.md` (seção de papéis) e no ClickUp:
- **Felipe** — arquitetura, blocos Críticos, DECs, deploy.
- **Vinícius** — dashboard/PDF/UX, scrapers (inclui o fix do coletor que retorna 0 unidades e zera dados — promover a bloco P1 na esteira dele).
- **Juan** — API GeoEspacial, bot Telegram, Estudos sob Demanda.
- Cada um habilita Agent Teams (experimental) na própria máquina: `"CLAUDE_CODE_EXPERIMENTal_AGENT_TEAMS": "1"` → corrigir para maiúsculas: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` no settings pessoal (não versionado).
- Aprovação de blocos **Alta** passa a ser por domínio (DEC-016).

**Critérios de aceite:** 1 bloco Alta aprovado por Vini ou Juan sem participação do Felipe; mapa de domínios publicado.

---

## 4. Fase 2 — Loop autônomo paralelo (Sprint 3–4)

### BLK-ORQ-16 — Garimpeiro multi-bloco

| Campo | Valor |
|---|---|
| Criticidade | Alta |
| Prioridade | P2 |
| Esteira | Gate humano pré-Builder |
| Status | Backlog |
| Dependências | BLK-ORQ-13 estável por ≥2 semanas |
| Autonomia | Após aprovação, autônoma |

**Escopo:** evoluir o Garimpeiro para processar até 2–3 blocos loop-safe por noite em paralelo, com lock por bloco (padrão `current_tasks/<ID>.lock` no estilo do harness do compilador C da Anthropic) para evitar colisão entre execuções. Manter: 1 PR por bloco, suíte FULL por bloco, zero merge.

**Critérios de aceite:** noite com 2 blocos concluídos em PRs independentes sem colisão; lock impedindo execução duplicada comprovado em teste.

---

## 5. Fase 3 — Pesquisa profunda + bookkeeping vivo (Sprint 4+)

### BLK-ORQ-17 — Painel de pesquisa multiagente

| Campo | Valor |
|---|---|
| Criticidade | Baixa (read-only) |
| Prioridade | P2 |
| Esteira | Interativa |
| Status | Backlog |
| Dependências | Agent Teams habilitado |
| Autonomia | Alta (read-only) |

**Escopo:** criar 4 agentes customizados versionados em `.claude/agents/` (todos read-only, `model: opus`, effort alto):
- `pesquisa-demografo.md` — Censo 2022, renda, densidade por setor.
- `pesquisa-concorrencia.md` — redes fitness, preços, saturação.
- `pesquisa-imobiliario.md` — oferta comercial, faixas de aluguel.
- `advogado-do-diabo.md` — só procura razões para NO-GO; proibido de concordar.

Template de invocação (documentar no CLAUDE.md):

```
Crie um agent team para estudar viabilidade de expansão em <CIDADE>.
Spawn os 4 agentes de pesquisa de .claude/agents/. Cada um trabalha
independente, sem ver os achados dos demais. Ao final, sintetize
confrontando explicitamente os achados do advogado-do-diabo com os
outros três. Formato de saída: parecer GO/ATTENTION/NO-GO com
evidências e incertezas (IC quando houver dado).
```

Para varreduras externas amplas (fontes públicas, GeoFusion independence), usar o recurso **Research** do claude.ai como etapa prévia e alimentar o painel com o resultado.

**Critérios de aceite:** 1 estudo real (cidade do pipeline) executado pelo painel; parecer confrontado com estudo anterior single-agent para comparação de profundidade.

---

### BLK-ORQ-18 — Hooks → baixa automática no ClickUp

| Campo | Valor |
|---|---|
| Criticidade | Média |
| Prioridade | P2 |
| Esteira | /run-cycle |
| Status | Backlog |
| Dependências | BLK-ORQ-14; MCP ClickUp configurado |
| Autonomia | Agente executa; validação humana da 1ª sincronização |

**Escopo:** hook `Stop`/pós-conclusão que, ao registrar nota de CONCLUSÃO num bloco, atualiza a tarefa ClickUp correspondente (status + comentário com link do PR), seguindo as regras da skill `produtividade-clickup-ultra` (atribuição por `date_closed`, tags de frente/complexidade). Reconciliação: o Zelador (BLK-ORQ-12) passa a apontar divergências residuais.

**Critérios de aceite:** bloco fechado gera baixa correta no ClickUp sem ação manual; regras da skill respeitadas (validar com auditoria da quinzena).

---

## 6. Métricas de sucesso (medir antes e depois)

**Baseline (extrair da auditoria de junho/2026 antes da Fase 1):**

| Métrica | Como medir | Baseline jun/26 | Meta 90 dias |
|---|---|---|---|
| Blocos concluídos/mês por frente | `completed.md` + ClickUp | (preencher) | +50–100% |
| Latência mediana bloco pronto → merge | timestamps PR | (preencher) | < 24h |
| Tempo do Felipe por aprovação (Média) | amostragem manual | ~45 min | ≤ 5 min |
| Blocos em voo simultâneos por pessoa | observação semanal | 1 | 2–3 |
| Blocos executados fora do horário humano | PRs do Garimpeiro | 0 | ≥ 8/mês |
| Branches órfãs > 3 dias | relatório do Zelador | (preencher) | 0 |
| Incidentes por merge automático | pós-mortems | — | 0 (gatilho DEC-016) |

---

## 7. Guardrails permanentes (inalterados)

1. M1 read-only por padrão; alteração só com DEC + gate Felipe.
2. loop_guard aborta diff em M1/config/deploy/segredos/CI.
3. Suíte FULL de testes como gate único, sem bypass; QA no modelo mais forte.
4. Deploy sempre manual, por digest imutável, pelo Felipe.
5. Anti-PII por construção; `NAO_ABRA/` nunca acessível a agente.
6. PoC visual nunca é loop-safe.
7. NO-GO é desfecho válido e documentado.
8. **Novo:** merge automático limitado a criticidade Baixa; suspenso automaticamente pelo gatilho da DEC-016.

## 8. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Merge automático deixa passar defeito | Escopo restrito a Baixa/loop-safe + Code Review bloqueante em severidade alta + gatilho de suspensão (DEC-016) |
| Consumo de cota (5h/semanal) com teams | Teams só para blocos que se dividem limpo; subagentes para o resto; monitorar Configurações → Uso |
| Custo do pool programático (routines) | Medir na 1ª quinzena; se exceder, Garimpeiro reduz para 3x/semana |
| Agent Teams é experimental | Uso restrito a pesquisa (read-only) e blocos não-críticos; fallback = subagentes |
| Colisão entre execuções paralelas | 1 bloco = 1 branch = 1 worktree; lock file no Garimpeiro multi-bloco |
| Vini/Juan aprovando além do domínio | Mapa de domínios explícito no CLAUDE.md; Crítica segue exclusiva do Felipe |

---

*Fim do plano. Ordem de execução sugerida: DEC-016 → BLK-ORQ-11 → BLK-ORQ-10 → BLK-ORQ-12 → BLK-ORQ-13 → Fase 1 → Fase 2 → Fase 3.*