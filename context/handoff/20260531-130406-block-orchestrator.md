# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-SCORE-03 — Proposta de recalibração + DEC.**

Bloco CRÍTICO por definição (toca `score_priorizacao` / pesos / fórmula do M1).
A execução é dividida por um GATE DE APROVAÇÃO HUMANA OBRIGATÓRIA:

- **Fase 1 (esta entrega, do Planner):** APENAS proposta técnica fundamentada +
  minuta de DEC. NENHUMA escrita em qualquer artefato/código do M1.
- **Fase 2 (Builder, somente depois do gate):** só ocorre se a string
  `APROVADO POR [usuário] EM [data]` aparecer no handoff e a recomendação da DEC
  for "recalibrar". Se a recomendação for "não recalibrar", o ciclo encerra na DEC.

Insumo factual único: `data/analysis/relatorio_backtest.md` (BLK-SCORE-02,
read-only, gitignored). Resumo do que o backtest mostra:
- `score_priorizacao` (M1): rho AGG = **-0.004** (p=0.948), IC95% bootstrap
  **[-0.104, +0.094]** → poder preditivo essencialmente **NULO** (IC atravessa zero).
- Decomposição dos componentes: `renda_pct_nacional` rho=+0.067 (p=0.214, n.s.) e
  `pop_pct_nacional` rho=+0.095 (p=0.077, n.s.). Pop é **marginalmente** maior que
  renda em magnitude, mas **ambos são fracos e não-significativos**.
- `score_setor_2022_calibrado` (censitário, camada PARALELA) é o único positivo
  significativo (rho=+0.148, IC [+0.052, +0.251]) — mas NÃO é o M1 e mexer nele
  está fora deste bloco.
- `score_oportunidade_residual` é negativo (rho=-0.257) — também camada paralela.

## Objetivo
Decidir, com honestidade analítica, **se** o backtest justifica recalibrar os
pesos/fórmula do `score_priorizacao` do M1 e, em caso afirmativo, propor a mudança
exata + minuta de DEC. A recomendação pode legitimamente ser
**"não recalibrar"**, **"recalibração mínima"** ou **"coletar mais dados antes"**
se os dados não sustentarem mudança. O Planner NÃO deve forçar uma alteração de
peso só porque o bloco se chama "recalibração".

## Escopo permitido
Fase 1 (Planner — esta entrega):
- Avaliar criticamente o `relatorio_backtest.md` e julgar se há base estatística
  para alterar pesos/fórmula do M1. Enunciar explicitamente as limitações que
  enfraquecem qualquer recalibração (maturação indisponível, heterogeneidade de
  desfecho entre redes, N pequeno em EngCorpo/domínio, precisão de hex variável,
  rótulo EngCorpo estimado — ver §5 do relatório).
- Produzir UMA recomendação clara entre: (a) NÃO recalibrar; (b) recalibração
  mínima/justificada com pesos antigos→novos explícitos; (c) coletar mais dados.
- Se (b): especificar pesos exatos propostos (ex.: `renda`/`pop`), o impacto
  esperado no ranking M1 (qualitativo, sem regerar artefatos), e os campos
  da fórmula afetados.
- Redigir a minuta de DEC (será a primeira DEC formal numerada do repo, sugerir
  `DEC-001`) com: contexto, evidência do backtest, decisão, justificativa, data,
  pesos antigos vs. novos (se houver), e plano de reversão. A DEC vai em
  `CLAUDE.md` (DECISIONS.md NÃO existe no repo).
- Definir os critérios de aceite verificáveis que o Builder/QA usarão na Fase 2.

Fase 2 (Builder — SOMENTE pós-gate, e somente se DEC = "recalibrar"):
- Alterar `PESOS_HEX_SCORE_ESTRUTURAL` em `core/constants.py` e/ou a fórmula em
  `core/scoring.py` exatamente conforme a DEC aprovada.
- Atualizar `tests/unit/test_scoring.py` para os novos pesos.
- Regerar artefatos via pipeline **em staging primeiro**, nunca sobrescrevendo
  Parquets de produção sem o passo de staging.
- Registrar a nova versão de proveniência (o manifesto BLK-OPS-03 lê os pesos
  direto de `PESOS_HEX_SCORE_ESTRUTURAL`, então o `_manifest.json` reflete a
  mudança ao rerodar `write_manifest`/`fase1_bi_exports`).

## Fora de escopo
- Qualquer escrita em código/artefato do M1 ANTES da string
  `APROVADO POR [usuário] EM [data]` no handoff.
- Alterar o `score_setor_2022_calibrado` (censitário), `score_oportunidade_residual`
  (residual) ou `score_dominio_hibrido` — são camadas paralelas; este bloco é só M1.
- Tocar em qualquer canônico que não seja peso/fórmula aprovado na DEC
  (`H3_RESOLUTION=7`, `DIST_MIN_ULTRA_KM=1.0`, `RENDA_MIN`, `AREA_*`, `PE_DIREITO_MIN`,
  cortes de percentil, `M1_*`).
- Reabrir/alterar o backtest do BLK-SCORE-02 ou gerar novos dados de validação.
- Mudar a lógica do `ajuste_executivo` ou os `PERCENTIL_CORTE_*` sem que a DEC
  os nomeie explicitamente.

## Arquivos que devem ser lidos
- `CLAUDE.md` (pesos canônicos 0.40/0.60, guardrails M1, regra de criticidade 2026-05-30, ausência de DEC formal).
- `tasks/current_task.md` (BLK-SCORE-03 ativo, contexto de abertura).
- `tasks/backlog.md` linhas ~58-103 (escopo em 2 fases, critérios, validações, guardrails).
- `data/analysis/relatorio_backtest.md` (insumo factual; ler na íntegra, inclusive §5 Limitações).
- `src/motor_expansao/core/scoring.py` (`calcular_hex_score_estrutural`, `score_priorizacao`).
- `src/motor_expansao/core/constants.py` (`PESOS_HEX_SCORE_ESTRUTURAL`, `PESOS_HEX_SCORE_FINAL`, cortes).
- `src/motor_expansao/pipelines/m1/provenance.py` (manifesto lê pesos; reflete recalibração).
- `tests/unit/test_scoring.py` (testes a atualizar se houver mudança de peso).

## Arquivos que podem ser alterados
Fase 1 (Planner): NENHUM arquivo de código/artefato M1. O Planner só produz seu
próprio handoff/minuta de DEC.

Fase 2 (Builder — só pós-gate e só se DEC = recalibrar):
- `src/motor_expansao/core/constants.py` (apenas `PESOS_HEX_SCORE_ESTRUTURAL` e o que a DEC nomear).
- `src/motor_expansao/core/scoring.py` (apenas a fórmula que a DEC nomear).
- `tests/unit/test_scoring.py` (sincronizar com novos pesos).
- `CLAUDE.md` (registrar a DEC e atualizar os pesos canônicos da §3, se mudarem).
- `data/outputs/` (regeneração via pipeline, staging primeiro).

## Critérios de aceite
1. **DEC registrada** em `CLAUDE.md` com: contexto, evidência do backtest citada,
   decisão (recalibrar / não recalibrar / coletar dados), justificativa, data e
   plano de reversão. Numeração sugerida `DEC-001` (primeira DEC formal do repo).
2. Se a decisão for recalibrar: **pesos antigos (0.40/0.60) vs. novos documentados**
   lado a lado, e **ranking M1 antes/depois** comparado com diferenças explicadas.
3. Se a decisão for NÃO recalibrar / coletar dados: a DEC justifica explicitamente
   por que os dados não sustentam mudança (IC atravessa zero, componentes n.s.,
   limitações de §5) — e o ciclo encerra sem tocar M1 (aceite válido).
4. **Proveniência (BLK-OPS-03)** reflete a versão: pós-recalibração, `_manifest.json`
   mostra os novos pesos (auto via `PESOS_HEX_SCORE_ESTRUTURAL`).
5. **Suíte verde**: `pytest -q tests/unit/test_scoring.py` e `pytest -q` completo
   (baseline atual: 532 passed, 1 skipped). Testes de fórmula atualizados para os novos pesos.
6. **Staging primeiro**: regeneração de `data/outputs/` nunca sobrescreve produção
   sem passo de staging.
7. QA confirma explicitamente que canônicos não-pesos (`H3_RESOLUTION=7`,
   `DIST_MIN_ULTRA_KM=1.0`, etc.) NÃO foram tocados.

## Criticidade classificada
crítica

## Esteira recomendada
Block Orchestrator → Planner → `[APROVAÇÃO HUMANA OBRIGATÓRIA]` → Builder → QA

## Riscos identificados
- **Viés de confirmação / recalibração forçada:** o nome do bloco sugere mudar
  pesos; o risco é o Planner propor uma alteração não justificada. Mitigação: o
  backtest mostra rho≈0 com IC atravessando zero e componentes não-significativos
  → "não recalibrar" é um resultado legítimo e deve ser considerado em pé de igualdade.
- **Confundir camada paralela com M1:** o único score positivo significativo é o
  censitário (paralelo), NÃO o M1. Recalibrar o M1 com base na performance do
  censitário seria erro de escopo.
- **Inferência causal sobre N pequeno / dados ruidosos:** maturação indisponível,
  EngCorpo estimado, hex por centroide de cidade — qualquer recalibração herda
  esse ruído. A DEC deve declarar essas limitações.
- **Sobrescrita acidental de produção:** regeneração sem staging destruiria os
  Parquets oficiais. Guardrail de staging-primeiro é obrigatório na Fase 2.
- **Pular o gate humano:** Builder não pode iniciar sem a string de aprovação
  explícita no handoff.

## Guardrails ativos
- Bloco CRÍTICO: aprovação humana OBRIGATÓRIA após o Planner e antes do Builder
  (`APROVADO POR [usuário] EM [data]`). Sem essa string, ZERO escrita em M1.
- Não expandir escopo: um bloco por vez; só M1; só pesos/fórmula nomeados na DEC.
- Guardrail permanente do M1: nenhuma camada paralela ou visualização recalcula
  `score_priorizacao`/`hex_score_estrutural`/carteira/plano/artefatos sem aprovação.
- Staging sempre em Parquet; regeneração de outputs em staging antes de produção.
- DEC vai em `CLAUDE.md` (DECISIONS.md não existe).
- Worktree pré-sujo `M CLAUDE.md` NÃO deve ser commitado neste ciclo; commit só
  por path, nunca `git add -A`.
- Não fazer commits nem `git add` nesta fase de orquestração/planejamento.
