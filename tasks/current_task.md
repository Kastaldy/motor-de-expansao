# Current Task

## Bloco atual

ID: BLK-TP-06-FU1
Nome: Re-validação do residual com candidatos de recalibração (seleção que alimenta o TP-09)
Status: APROVADO PELO QA (2026-07-02) — bloco entrega veredito HONESTO e REPRODUZÍVEL. Candidato A = NAO_APLICAR (NO-GO válido, DEC-008); NÃO aplicar ao BLK-TP-09. QA reproduziu o NO-GO contra os parquets reais (números batem EXATO: baseline +0,3119, A +0,2692, Δ pareado completo −0,0427 IC95[−0,0477,−0,0379], fora −0,0193); suíte full 1290 passed/1 skipped/0 falhas; READ-ONLY M1 (mtimes intactos). Próximo: Fechamento manual (completed.md via 6.2 [ad-hoc no-op] + commit por path; atualizar "Depende de" do BLK-TP-09). Snapshot QA: context/handoff/20260702-180732-qa.md
Tipo: modelagem (análise/seleção de candidatos — READ-ONLY sobre o M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner (REVISAR c/ novos artefatos) → [REVISÃO HUMANA] → Builder → QA
Skill atual: QA (próxima)
Próxima Skill: QA

## VEREDITO do Builder (2026-07-02) — Candidato A = NAO_APLICAR (NO-GO honesto)
- Baseline (completo) reproduz o TP-06: R²_oof_log +0,3119, IC95 [+0,2977, +0,3250], rho_oof +0,4615, n=16.411.
- Candidato A (completo): R²_oof_log +0,2692, IC95 [+0,2553, +0,2819] — PIOR que o baseline.
- Δ pareado (A − baseline): COMPLETO −0,0427 IC95 [−0,0477, −0,0379]; FORA (não-metro) −0,0193 IC95 [−0,0232, −0,0157]. Ambos inteiramente abaixo de zero → NÃO vence em nenhum recorte.
- Dedup fino no join: +1.748.710 somados / −157.840 dedupados. Enriquecer a oferta consumida DERRUBA o poder preditivo out-of-fold → NÃO recomendar ao BLK-TP-09 aplicar o Candidato A. NO-GO válido (DEC-008).
- Artefatos: `src/motor_expansao/demanda_revelada/revalidacao_residual_candidatos.py` (NOVO), `tests/unit/demanda_revelada/test_revalidacao_residual_candidatos.py` (NOVO, 18 passed), `data/analysis/revalidacao_residual_candidatos.md` (NOVO, gitignored). READ-ONLY M1: mtime dos 4 oficiais + hexagonos_mercado_mapeado.parquet inalterado.
Gate humano: APROVADO pelo usuário em 2026-07-02 — SÓ Candidato A agora (baseline + A, dedup fino por (hex,rede)); Candidato C ADIADO.
Candidato C (futuro): usar capacidade de CLUBE real de data/validacao/ — `Sky Fit dados.xlsx` (SkyFit), `academias_engenharia_do_corpo.xlsx` (Engenharia), `KPIs_Smart_2025_02 (1).xlsx` (Smart Fit) [gitignored, dados reais, anti-PII]. As medianas ~340 do TP-08-FU são footprint de bairro, NÃO capacidade de clube.

## Retomada (2026-07-02) — plano REVISADO pelo Planner com os artefatos reais (snapshot context/handoff/20260702-170214-planner.md)
- `data/staging/oferta_academias_menores_rede_h3.parquet` (LONGO hex_id×rede_menor; 7.250 linhas, 14 redes, Σ 1.920.955 alunos) → dedup FINO por par (hex,rede). **Medido no join (16.411 hexes): 91,7% (1.748.710 alunos) são adição legítima; 8,3% (157.840) duplicados.**
- `data/staging/capacidade_media_por_rede.parquet` (13 redes; 10 com flag_confiavel N≥10) → capacidade POR REDE do Candidato C. **CORREÇÃO: medianas reais são baixas (13–723, global ~340) e para academias de BAIRRO (panobianco/velocity/bio_ritmo/...), NÃO Smart/Sky/Engenharia; as grandes numerosas caem no fallback.**
- Estrutura da oferta consumida verificada por recompute (max abs diff 0.0): `oferta_consumida_mercado = oferta_efetiva_mapeada_2km·2500` (Σ concorrentes 2 km distância-decaída). Candidato C exige reproduzir o 2 km-decay via BallTree local ponderando por capacidade da rede (o `n_unid_rede_por_hex` do plano pausado estava geometricamente errado).
- Módulo novo: `src/motor_expansao/demanda_revelada/revalidacao_residual_candidatos.py` (baseline + A + C + [A+C]); relatório `data/analysis/revalidacao_residual_candidatos.md`; testes `tests/unit/demanda_revelada/test_revalidacao_residual_candidatos.py`.
- Decisões ao gate: (A) regra do dedup fino por (hex,rede); (C) fallback de capacidade das redes sem N≥10 = 2.500 (recomendado); (D) rodar A+C combinado (recomendado sim); (E) critério de vence = IC95 do Δ pareado sem cruzar zero + sobreviver fora de SP/MG/RJ.

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
