---
name: clickup-sync
description: Audita e sincroniza o ClickUp contra o trabalho real no GitHub, aplicando a rubrica de pontuação correta (que o agente já errou por adivinhação). Respeita o RATE LIMIT da API (estourar bloqueia ~24 h). Cobre frentes, pontos por complexidade, volume operacional, regra de documentação, critério temporal, comprometido x bônus, convenções de assignee/creator e o gap-audit GitHub↔ClickUp. Use ao pedir "audite o ClickUp", "pontue a semana", "sincronize as tarefas", "confira as pontuações".
---

# /clickup-sync — rubrica + gap-audit GitHub↔ClickUp

A rubrica vive na cabeça do Felipe; sem esta referência o agente inventa e o placar sai errado.
Use os tools MCP `clickup_*`. Esta skill é **alinhada** à `produtividade-clickup-ultra` (também em
`.claude/skills/` deste repo): lá vivem a criação de tarefas, o painel mensal e o template; aqui, a
auditoria contra o GitHub. **Em caso de divergência, a regra desta seção de rubrica e a da
`produtividade-clickup-ultra` devem ser a mesma — se não forem, pare e pergunte.**

## ⚠️ RATE LIMIT DA API DO CLICKUP — LER ANTES DE QUALQUER CHAMADA
Estourar o limite **bloqueia o acesso por ~24 h** (episódio recorrente com os agentes do Felipe) — isso
para o time inteiro, muito mais caro que uma tarefa lenta. **Respeitar o limite é prioridade sobre
velocidade: a tarefa pode demorar mais, o bloqueio não é aceitável.**

Referência: a API REST do ClickUp limita por token (100 req/min nos planos Free/Unlimited/Business;
excedeu → HTTP 429, com `X-RateLimit-Remaining`/`X-RateLimit-Reset` na resposta). Os tools MCP
`clickup_*` consomem essa mesma cota — **cada chamada de tool conta**, inclusive leituras.

Regras obrigatórias:
1. **Orçar antes de começar.** Estimar quantas chamadas a tarefa vai fazer e informar o número ao
   Felipe. Acima de ~50 chamadas, pedir confirmação antes de executar.
2. **Nunca chamar em paralelo.** Chamadas `clickup_*` sempre **sequenciais**, uma por vez — nada de
   vários tools ClickUp no mesmo bloco, nem subagentes/workflows batendo no ClickUp ao mesmo tempo.
3. **Ritmo máximo ~1 chamada a cada 2 s** (≤ 30/min, metade do teto). Em lotes grandes, pausar
   (`Monitor`/espera curta) em vez de disparar em sequência rápida.
4. **Preferir chamada em massa a chamada por item.** Usar `clickup_filter_tasks` paginado (já traz
   tags, assignees, datas, subtarefas) em vez de `clickup_get_task` por tarefa. Só abrir tarefa
   individual quando o dado não vier na listagem.
5. **Ler uma vez, reusar.** Salvar o resultado das listagens no scratchpad (JSON) e trabalhar sobre o
   arquivo; nunca repetir a mesma consulta para "conferir".
6. **Escritas agrupadas e mínimas.** Montar a lista completa de correções, obter a confirmação do
   Felipe **uma vez** e aplicar só o que muda (não reescrever tarefa que já está certa).
7. **Ao primeiro sinal de limite (429, "rate limit", "too many requests") — PARAR.** Não tentar de novo
   em loop (é exatamente o retry que transforma o aviso em bloqueio de 24 h). Salvar o progresso no
   scratchpad (o que já foi lido/aplicado e o que falta), reportar ao Felipe e só retomar quando ele
   mandar.
8. Se o acesso já estiver bloqueado, **não insistir**: avisar e parar.

## Princípio central (inegociável)
- Cada **frente** é lida na sua própria unidade. **NUNCA** somar pontos entre frentes, **NUNCA** montar
  "pontos totais" por pessoa nem ranking geral.
- Números saem de código sobre as etiquetas lidas do ClickUp — nunca estimados de cabeça.

## Rubrica de pontuação (canônica — NÃO adivinhar)

### Frentes e unidades
| Frente | O que é | Unidade |
|---|---|---|
| `Operacional` | repetitivo: scraping/coleta, estudos de ponto | **itens** (volume) |
| `Projeto` | dev, engenharia, deploy, feature | **pontos** de sizing |
| `Análise` | estudo/relatório aprofundado, não repetitivo | **pontos** de sizing |

- **Operacional pontua** — em **itens**, não na escala de complexidade (episódio real: o agente escreveu
  "Operacional não pontua"; está errado). **1 item por tarefa ou subtarefa** com etiqueta `Operacional`,
  salvo quando a quantidade vem embutida (ver lote abaixo).
- **Projeto / Análise:** por complexidade — `Baixa` = 1 · `Média` = 3 · `Alta` = 8.

### Etiquetas (nomes exatos, com acento)
- Frente: `Operacional` · `Projeto` · `Análise` — **exatamente uma** por tarefa.
- Complexidade: `Baixa` · `Média` · `Alta` — **só** em Projeto/Análise. Operacional **não** recebe.
- Sem certeza da frente: não chutar; deixar sem etiqueta e listar para revisão.

### Calibragem do sizing
- `Baixa` = unidade com significado (~meia diária para cima). Micro-passo de 15–30 min **não** é tarefa de
  topo: é subtarefa do entregável-pai.
- **Subtarefa de Projeto/Análise não recebe Complexidade → vale 0.** Pontua-se no nível do entregável.
- **Tarefa-pai/épico sem Complexidade → vale 0** (contam as subtarefas pontuadas). **Nunca** somar pai +
  subtarefas — é dupla contagem.
- **1 bloco ≠ 1 tarefa.** Uma tarefa = uma **entrega concreta** (pode agrupar vários blocos, ou um bloco
  virar várias tarefas). Não mapear 1:1 mecanicamente.

### Documentação NÃO é `Alta` (erro recorrente)
O agente classificou várias vezes como `Alta` tarefas que eram **só documentação**. Regra:
- Tarefa/PR **apenas de documentação** — atualizar runbook, CLAUDE.md, README, backlog/`completed.md`,
  corrigir texto/drift de doc, registrar algo já decidido — **sem decisão nova nem entrega relevante** →
  **`Baixa`**. Nunca `Média`/`Alta` pelo tamanho do diff ou pela extensão do texto.
- Housekeeping/bookkeeping de fechamento de bloco (`completed.md`, ponteiro de backlog) faz parte da
  entrega do bloco — **não** vira tarefa pontuada à parte.
- O que sobe o sizing é o **trabalho por trás** do documento (análise medida, decisão de produto,
  investigação), não o documento. Uma DEC que registra uma análise real é pontuada pela **análise**
  (normalmente na tarefa da análise/implementação), não por ser um `.md` longo.
- Na dúvida entre `Baixa` e algo maior para uma tarefa de doc: **perguntar ao Felipe**.

### Estudos de ponto e scraping = Operacional (volume)
- **Estudo de ponto** (~30–40 min, repetível, em lote) = **1 item Operacional** cada, apesar da palavra
  "estudo". Só vai para `Análise` o estudo/relatório aprofundado e único (horas/dias).
- **Scraping:** cada coletor/academia coletada = 1 item. Lote de 30 academias = 30 itens, não 1.
- **Registro em lote:** uma tarefa por pessoa por mês na lista **"Rotina de Estudos"**
  (`list_id = 901713566217`), etiqueta `Operacional`, campo **Frente** = Operacional, sem Complexidade,
  nome `Estudos de ponto p/ expansão — <Mês>/<Ano> (<N> estudos)` e marcador `[VOL_OPERACIONAL: <N>]`
  na descrição.
- **Quantidade lida:** `[VOL_OPERACIONAL: N]` → senão `(N estudos)` no nome → senão **1**.

### Multi-responsável
Tarefa conjunta: **cada** responsável recebe os pontos/itens **integrais**. Não dividir.

## Critério temporal — a que mês/semana a entrega pertence
- Vale a **data de conclusão** (`date_closed`), **nunca** `created_date`.
- **Grace de 3 dias corridos na virada do mês:** tarefa com `due_date` no mês X concluída nos dias 01–03
  de X+1 conta em **X**. Sem `due_date`, não há grace: vale `date_closed` puro.
- **Espelho nas duas pontas:** ao apurar X, trazer o que tinha prazo em X e fechou em 01–03 de X+1, e
  **retirar** de X o que tinha prazo em X-1 e fechou em 01–03 de X.
- Converter timestamps para **BRT (UTC-3)** antes de decidir o dia.
- Puxar com `clickup_filter_tasks` (`date_closed_from`/`date_closed_to` cobrindo o período + 3 dias),
  `include_closed=true`, `subtasks=true`, paginando `page` até `count < 100`.

## Comprometido x bônus
- **Comprometido** = tarefa criada (`created_date`) **até o 20º dia corrido** do mês.
- **Bônus** = criada do dia 21 em diante e concluída no mês.
- Taxa honesta = comprometidas concluídas ÷ comprometidas totais. **Nunca** apresentar "disponível =
  entregue = 100%".
- Os dois filtros são independentes (criada dia 20, prazo no mês, fechada dia 02 do mês seguinte =
  comprometida **e** conta no mês).
- O cálculo completo (código Python) está no FLUXO 3 da `produtividade-clickup-ultra` — **executar
  aquele código**, não recalcular à mão.

## Convenções
- **Assignee:** ao concluir/mover uma tarefa, confirmar que ela está atribuída à pessoa certa (o agente já
  fechou tarefa esquecendo de reatribuir — seguia com outra pessoa). Conferir `assignee` explicitamente.
- **Creator vs assignee:** distinguir quem criou de quem executa; a pontuação segue o executor.
- **IDs de pessoa:** Juan `101182134` · Vinícius `101182135` · Felipe `296609800`. Para outros nomes,
  `clickup_resolve_assignees`.
- **Campo Frente:** `7adab26a-ff95-408e-b8b0-14f8a249e96e` → Operacional `3c64ee76-ff6a-448f-8888-1817591988de`.

## Gap-audit GitHub↔ClickUp
1. **GitHub** — PRs mergeados no período (repo `Kastaldy/motor-de-expansao`):
   ```
   gh pr list --state merged --search "merged:AAAA-MM-DD..AAAA-MM-DD" --limit 200 \
     --json number,title,headRefName,author,mergedAt,labels,files
   ```
   Agrupar por `BLK-ID` (título/branch) e por entrega concreta. Marcar os PRs **só de documentação**
   (todos os `files` em `docs/`, `tasks/`, `*.md`) para aplicar a regra de documentação.
2. **ClickUp** — tarefas do período por assignee (`clickup_filter_tasks`/`clickup_search`), com o critério
   temporal acima.
3. **Reportar os gaps**, por frente:
   - (a) trabalho mergeado **sem tarefa**;
   - (b) tarefa **não concluída** apesar do merge;
   - (c) **assignee errado**;
   - (d) **pontuação divergente da rubrica** — em especial: doc-only com `Média`/`Alta`; Complexidade em
     Operacional ou em subtarefa; pai + subtarefas pontuados juntos; estudo de ponto em `Análise`;
     etiqueta de frente ausente ou duplicada;
   - (e) **mês errado** (pelo `date_closed` + grace, não pela criação).
4. Aplicar correções **sob confirmação** (`clickup_update_task`/`clickup_create_task`,
   `clickup_add_tag_to_task`/`clickup_remove_tag_from_task`).

## Guardrails
- Nunca inferir regra de pontuação nova; se a rubrica não cobrir um caso, **perguntar**, não adivinhar.
- Read-only sobre o repositório; escreve só no ClickUp, sob confirmação.
- **Rate limit acima de tudo:** chamadas sequenciais, orçadas e espaçadas; ao primeiro 429, parar e reportar.
- Resultado sempre **por frente**; nunca um número único por pessoa.
