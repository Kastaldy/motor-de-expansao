# Current Task

## Bloco atual

ID: BLK-TP-06-FU1
Nome: Re-validação do residual com candidatos de recalibração (seleção que alimenta o TP-09)
Status: PAUSADO (gate humano 2026-07-02) — bloqueado por dependência de dado
Tipo: modelagem (análise/seleção de candidatos — READ-ONLY sobre o M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [PAUSADO no gate] → (retomar após BLK-TP-08-FU) → Builder → QA
Skill atual: Planner (concluído; ciclo pausado)
Próxima Skill: RETOMAR após BLK-TP-08-FU

## Motivo da pausa (decisão de Felipe no gate, 2026-07-02)
O plano revisado (candidatos A = incluir academias menores na saturação + dedup de rede; C = capacidade
POR REDE) esbarrou em 2 lacunas de dado confirmadas pelo Planner:
1. **Sem rótulo de rede** nas academias menores (o `Nome_Academia` foi dropado no anti-PII do TP-08) →
   dedup FINO por rede é impossível hoje.
2. **Médias por rede só para 2 de 28** (SkyFit 2.295, Engenharia 3.283 em base_calibracao_multirede);
   Smart Fit / Blue Fit / Panobianco NÃO estão no repo.
Decisão: PAUSAR o FU1 e **fechar o dado primeiro** via BLK-TP-08-FU (re-ingestão do 03_Competidores.xlsx
com `rede_menor` classificado na fronteira anti-PII → habilita dedup fino E médias por rede a partir de
`Alunos_Academia` das filiais classificadas). Retomar o FU1 (A+C completos) depois.
Plano detalhado preservado em context/handoff/20260702-154210-planner.md (snapshot).

## Objetivo
Reproduzir o baseline do TP-06 (residual atual vs demanda observada, +0,31 out-of-fold) e construir/validar
CANDIDATOS de residual — (A) residual descontando a oferta das academias menores do TP-08 COM dedup;
(B) residual com a recalibração proposta no TP-06 — cada um validado out-of-fold vs baseline (DEC-008),
comparando se algum candidato BATE o +0,31 de forma robusta e sem depender do caveat de ~1% metropolitano.
É o gate honesto (READ-ONLY, sem DEC) que decide SE o TP-09 se justifica e QUAL candidato aplicar.

## Contexto crítico
- TP-08 INGERIU a oferta das academias menores (`data/staging/oferta_academias_menores_h3.parquet`,
  `oferta_menores_v1`), mas NÃO a integrou ao residual → a fórmula do residual hoje é IDÊNTICA à validada
  no TP-06. Um rerun ingênuo daria o mesmo +0,31 (inútil) — por isso este bloco testa CANDIDATOS.
- Dedup do TP-08: 62,7% dos alunos das academias menores já caem em hex coberto por rede mapeada →
  integrar a oferta SEM dedup dupla-conta. O candidato (A) precisa tratar isso.
- READ-ONLY: NÃO altera a fórmula do residual em produção nem regenera parquets de mercado. Aplicar o
  vencedor = BLK-TP-09 (DEC + gate). Este bloco só MEDE e RECOMENDA.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: opus (override +1: escopo dos candidatos de residual + dedup da oferta TP-08 é não-trivial)
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-TP-06-FU1 (criada a partir de main @ HEAD 3ab5e8c).

## Bloco ad-hoc
Derivado da conversa (não vem do backlog). No fechamento: Passo 6.0 é no-op (ad-hoc) → resumo vai a
completed.md via Passo 6.2; ao final, atualizar o "Depende de" do BLK-TP-09 no backlog para citar este FU1.

## Guardrails
- §5 (READ-ONLY M1): zero recálculo de score_priorizacao/hex_score_estrutural/pesos/carteira/plano/artefatos oficiais.
- NÃO alterar a fórmula de `score_oportunidade_residual` em produção nem regenerar `hexagonos_mercado_mapeado.parquet`.
- DEC-008: LOO/k-fold vs baseline da média; R² in-sample BANIDO; IC95 bootstrap seed fixa; intervalos + flag de extrapolação; comparação de candidatos out-of-fold; NO-GO é resultado válido.
- DEC-009: demanda OBSERVADA como alvo; PROIBIDO usar como preditor geográfico de magnitude.
- DEC-012 (anti-PII): só camadas agregadas; zero PII; fixtures sintéticas; fonte real nunca versionada.
- Isolamento: módulo da camada paralela NÃO importa de pipelines/m1, dashboard, censo_*, api.
