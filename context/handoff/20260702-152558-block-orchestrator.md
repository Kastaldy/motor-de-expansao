# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (esteira Alta com gate humano de modelagem antes do Builder)

## Bloco refinado
**BLK-TP-06-FU1 — Re-validação do residual com candidatos de recalibração (seleção que alimenta o TP-09).**

Bloco AD-HOC (não vem do backlog), de MODELAGEM / seleção de candidatos, READ-ONLY sobre o M1. O BLK-TP-06 já provou, out-of-fold, que o `score_oportunidade_residual` ATUAL prevê a demanda paga observada (`membros`) com `R2_oof_log = +0,3119` (IC95 [+0,2977; +0,3250]; rho_oof +0,4615) — GO honesto, com uma PROPOSTA de recalibração DOCUMENTADA (não aplicada). O BLK-TP-08 ingeriu a oferta de academias menores (WellHub/TotalPass, `oferta_menores_v1`) mas NÃO a integrou ao residual — logo a fórmula do residual hoje é IDÊNTICA à validada no TP-06 e um rerun ingênuo daria exatamente o mesmo +0,31 (inútil). Este FU1 constrói e valida DOIS residuais CANDIDATOS (em memória / artefato de análise) contra o mesmo alvo observado e COMPARA out-of-fold com o baseline, para decidir SE o BLK-TP-09 (aplicação, com DEC + gate) se justifica e QUAL candidato aplicar.

## Objetivo
Reproduzir o baseline do TP-06 e construir/validar out-of-fold (DEC-008) dois residuais candidatos — (A) residual descontando a oferta das academias menores do TP-08 COM dedup, (B) residual com a recalibração proposta no relatório do TP-06 — comparando se algum bate o +0,31 de forma robusta (IC da diferença não cruzando zero) sem depender do caveat de ~1% metropolitano; é o gate honesto READ-ONLY que decide se o TP-09 se justifica.

## Escopo permitido
- Reproduzir o **baseline** do TP-06 (residual atual vs `log1p(membros)`, out-of-fold) reusando o harness já existente em `src/motor_expansao/demanda_revelada/calibracao_residual.py` (`calibrar_residual_demanda`, k-fold 5×5 seed=42, IC95 bootstrap 2000, R² in-sample banido do veredito) — confirmar que reproduz `R2_oof_log ≈ +0,31`.
- Construir, **EM MEMÓRIA / apenas como coluna candidata**, o **Candidato A** = residual que DESCONTA a fração NÃO-duplicada da oferta das academias menores (`data/staging/oferta_academias_menores_h3.parquet`), casada por `hex_id`, aplicando o dedup vs `concorrentes_mapeados.parquet` (chave `hex_id_res7`); e o **Candidato B** = residual com os parâmetros de recalibração propostos na §6 do relatório do TP-06.
- Validar CADA candidato out-of-fold vs baseline pelo MESMO harness/seed e COMPARAR (métrica-âncora `R2_oof_log`; suporte `rho_oof`; IC95 bootstrap seed-fixa). Reportar o veredito honesto de qual (se algum) candidato SUPERA o baseline de forma robusta.
- Reportar o caveat obrigatório de cobertura (~1% do universo / viés metropolitano do Sudeste) e verificar que o ganho de qualquer candidato NÃO depende só do recorte metropolitano (ex.: robustez sob subamostra fora de SP/MG/RJ, ou reportar explicitamente a limitação).
- Materializar o resultado como **relatório em `data/analysis/` (gitignored, sem PII)** e, se necessário, um módulo novo de comparação de candidatos dentro do pacote disjunto `demanda_revelada/` + testes com fixture sintética.

## Fora de escopo
- APLICAR qualquer candidato: editar `src/motor_expansao/pipelines/calcular_colunas_mercado.py`, alterar a fórmula de `score_oportunidade_residual`/`oferta_efetiva_disponivel` em produção ou regenerar `data/staging/hexagonos_mercado_mapeado.parquet` e derivados. Isso é o BLK-TP-09 (DEC + gate humano), NÃO este bloco.
- Tocar QUALQUER artefato oficial do M1 (`score_priorizacao`, `hex_score_estrutural`, pesos renda=0,40/pop=0,60, carteira, plano curto prazo, plano de domínio, parquets oficiais).
- Gerar um parquet de mercado novo/oficial. A saída é análise (relatório) + possível módulo/teste, não um artefato de mercado.
- Usar `membros` (ou qualquer coluna da camada de demanda) como PREDITOR geográfico de magnitude ou ajuste do score (DEC-009): `membros` é ALVO OBSERVADO, jamais feature.
- Reingerir/reprocessar a fonte real em `NAO_ABRA/` ou tocar PII; expandir para res-8 ou para outras camadas.
- Resolver o BLK-TP-09 ou qualquer outro bloco. Um bloco por vez.

## Construção dos 3 cenários (baseline / A / B) — confirmado nos dados
Todos os artefatos existem e o join é viável. Chave de join canônica = `hex_id` (res-7); a exceção é `concorrentes_mapeados.parquet`, cuja chave é `hex_id_res7` (usada SÓ para o dedup do Candidato A, não no join do modelo).

- **Baseline (reproduz TP-06):** join inner `demanda_revelada_h3` × `hexagonos_mercado_mapeado` por `hex_id` → **16.411 hexes** (bate o relatório do TP-06). Alvo `log1p(membros)`; preditor `score_oportunidade_residual` atual. Esperado: `R2_oof_log ≈ +0,3119`, `rho_oof ≈ +0,4615`, top-3 UF SP 29,1% / MG 12,7% / RJ 9,2%.
  - Colunas do mercado disponíveis: `hex_id`, `score_oportunidade_residual`, `oferta_efetiva_disponivel`, `uf` (o harness já as lê). Fórmula de produção (doc §5.6): `oferta_efetiva_disponivel = max(sam_fitness_potencial − oferta_consumida_total_estimada, 0)`; `score_oportunidade_residual = clip(100·oferta_efetiva_disponivel/2500, 0, 100)`.

- **Candidato A (desconta oferta das academias menores, COM dedup):** `oferta_academias_menores_h3.parquet` tem **6.785 hexes**, `Σ alunos_academias_menores = 1.920.955`, `Σ n_academias_menores = 24.045`. Dedup vs `concorrentes_mapeados` (por `hex_id_res7`): **1.425 hexes** em sobreposição; **62,7% dos alunos** das academias menores (1.203.919 de 1.920.955) já caem em hex coberto por rede mapeada → integrar SEM dedup dupla-conta. Cobertura sobre o join do modelo: dos 16.411 hexes do baseline, **6.265 (38,2%)** têm oferta de academias menores; nesses, `Σ alunos_menores = 1.906.550`. A construção candidata (a AFINAR pelo Planner/gate) é do tipo `oferta_efetiva_ajustada = f(oferta_efetiva_disponivel, alunos_academias_menores_NÃO_duplicados)` → `residual_candidato_A = clip(100·oferta_efetiva_ajustada/2500, 0, 100)`, tudo EM MEMÓRIA.

- **Candidato B (recalibração proposta no TP-06):** parâmetros vêm da §6 do relatório `data/analysis/calibracao_residual_demanda.md` (gitignored, já lido). Três alavancas propostas: (i) **capacidade default 2.500 alunos/unidade** recalibrada pela razão observada `membros`/`oferta_efetiva_disponivel` no recorte metropolitano; (ii) **peso de `oferta_efetiva_disponivel`** (comparado ao modelo secundário que isola o componente-fonte, `R2_oof = +0,261`); (iii) **faixa de corte / normalização 0-100** — reavaliar o `clip(100·oferta/2500,0,100)` contra a distribuição de `membros`. O relatório NÃO fixa valores numéricos finais → é AMBIGUIDADE para o gate (ver Riscos).

Harness/reuso confirmado: `motor_expansao.dimensionamento.aderencia` (`ALPHA_GRID=[0.01,0.1,1.0,10.0,100.0]`, `LIMIAR_R2_GO=0.05`) e `backtest_dim` (`_r2`,`_rmse`) importam OK e já são reusados pelo `calibracao_residual.py` (pacote irmão, NÃO M1/censo/dashboard).

## Arquivos que devem ser lidos
- `CLAUDE.md` (§1 posicionamento low-cost/Smart Fit; §4 camada mercado/residual e `score_oportunidade_residual`/`oferta_efetiva_disponivel`; §5 guardrail permanente; DEC-008; DEC-009; DEC-012; DEC-013)
- `tasks/current_task.md`
- `src/motor_expansao/demanda_revelada/calibracao_residual.py` (harness de validação out-of-fold a REUSAR/ESTENDER — join, `log1p(membros)`, k-fold 5×5 seed=42, IC95 bootstrap, `CalibracaoResidualResult`, `relatorio_calibracao`)
- `src/motor_expansao/demanda_revelada/oferta_academias_menores.py` (contrato `oferta_menores_v1`, `gerar_relatorio_qualidade`/dedup por `hex_id`)
- `src/motor_expansao/demanda_revelada/contrato.py` (`COLUNAS_PII_PROIBIDAS`, `H3_RES_CONTRATO`)
- `data/analysis/calibracao_residual_demanda.md` (relatório do TP-06 — §6 "Proposta de recalibração", parâmetros do Candidato B)
- `docs/modelo_mercado_hexagonos.md` (§5.6: como `oferta_efetiva_disponivel` compõe o residual; nota BLK-TP-08 sobre a oferta não-integrada)
- Schemas dos parquets (READ-ONLY, agregado): `data/staging/hexagonos_mercado_mapeado.parquet`, `data/staging/demanda_revelada_h3.parquet`, `data/staging/oferta_academias_menores_h3.parquet`, `data/staging/concorrentes_mapeados.parquet`

## Arquivos que podem ser alterados
- `src/motor_expansao/demanda_revelada/` — NOVO módulo de comparação de candidatos (ex.: `comparacao_residual_candidatos.py`), disjunto (nunca importa de `pipelines/m1/`, `censo_*`, `dashboard/`, `api`, `config.py` raiz). Pode ESTENDER (não quebrar) o harness de `calibracao_residual.py`.
- `tests/unit/` — testes novos do módulo de comparação, SÓ com fixture sintética (nunca fonte real / PII).
- `data/analysis/` — relatório novo de comparação de candidatos (gitignored, sem PII) — ex.: `comparacao_residual_candidatos.md`.
- `tasks/`, `context/handoff*` — bookkeeping do ciclo (o próprio Planner/Builder/QA).
- (Fechamento) `tasks/backlog.md` — atualizar o "Depende de" do BLK-TP-09 para citar este FU1 (passo pós-merge, ad-hoc).

## Critérios de aceite
- O baseline reproduz o TP-06 dentro de tolerância determinística (mesmo seed): `R2_oof_log ≈ +0,3119` e `n_join = 16.411`. Divergência material = defeito.
- Cada candidato (A e B) é validado pelo MESMO harness/seed (k-fold 5×5, IC95 bootstrap 2000, seed=42), com `R2_oof_log` (âncora) + `rho_oof` (suporte) + IC95, e a COMPARAÇÃO vs baseline é explícita (idealmente IC da DIFERENÇA de R2_oof, não cruzando zero, para declarar "candidato vence").
- O veredito por candidato é honesto (DEC-008): NO-GO / "não supera o baseline" é resultado VÁLIDO; R² in-sample nunca entra no veredito; flag de extrapolação e caveat de ~1% metropolitano reportados.
- O Candidato A aplica dedup (não dupla-conta os 62,7% de alunos já cobertos); a construção do desconto está documentada e reproduzível.
- Os parâmetros do Candidato B rastreiam explicitamente a §6 do relatório do TP-06.
- ZERO escrita em artefato M1/mercado: `mtime` de `hexagonos_mercado_mapeado.parquet` e dos 4 oficiais do M1 inalterado; `calcular_colunas_mercado.py` intocado; nenhum parquet de mercado novo.
- Anti-PII: nenhuma coluna de `COLUNAS_PII_PROIBIDAS` em qualquer frame/relatório; testes só com fixture sintética; fonte real (`NAO_ABRA/`) não tocada.
- Suíte verde (ruff + pytest do escopo impactado + smoke); CI sem regressão.

## Criticidade classificada
**Alta.** É modelagem READ-ONLY sobre o M1 (não altera fórmula/pesos/artefatos oficiais nem regenera parquets de mercado) — logo NÃO é Crítica pelo guardrail do §5. Mas alimenta a decisão de um score de PRODUÇÃO (o TP-09) e envolve escopo não-trivial (construção do desconto com dedup + parâmetros de recalibração) → exige REVISÃO HUMANA de modelagem antes do Builder.

## Esteira recomendada
Block Orchestrator → Planner → **[REVISÃO HUMANA — modelagem]** → Builder → QA.

## Riscos identificados
- **Ambiguidade A — construção do Candidato A (dedup):** definir EXATAMENTE como descontar. Opções para o gate: (i) subtrair apenas a fração NÃO-duplicada dos `alunos_academias_menores` (excluir hexes que sobrepõem `concorrentes_mapeados`), (ii) subtrair por hex com peso/capacidade por tipo de academia menor (planos TP0–TP7), (iii) tratar capacidade dos menores diferente da capacidade default de 2.500. Sem decisão, a dupla-contagem (62,7% dos alunos) contamina o candidato.
- **Ambiguidade B — parâmetros do Candidato B:** o relatório do TP-06 (§6) LISTA alavancas (capacidade 2.500, peso de oferta, faixa de corte) mas NÃO fixa valores numéricos finais. O gate precisa decidir os valores concretos (ex.: capacidade recalibrada pela razão `membros`/`oferta` observada, com IC) ou o Builder derivá-los-á de forma reprodutível e documentada.
- **Ambiguidade C — critério de "candidato vence":** recomendar que "vence" = `R2_oof_log` do candidato supera o baseline com o **IC95 da DIFERENÇA não cruzando zero** (não basta ponto-estimativa maior). Definir no gate.
- **Ambiguidade D — caveat metropolitano (~1%):** a amostra cobre ~1,06% do universo, concentrada em SP/MG/RJ. Risco de o ganho de um candidato ser artefato do recorte metropolitano. Definir como controlar (subamostra fora de SP/MG/RJ, ou reportar explicitamente a limitação de generalização nacional).
- **Risco de vazamento de escopo:** tentação de já "aplicar o vencedor" — proibido; aplicação é BLK-TP-09 (DEC + gate).
- **Risco de sobreajuste a ruído** se qualquer candidato for declarado GO sem IC robusto (DEC-008); ruído de coords ~1 km atenua o sinal no join res-7.

## Guardrails ativos
- **§5 (READ-ONLY sobre o M1):** zero recálculo/alteração de `score_priorizacao`, `hex_score_estrutural`, pesos (renda=0,40/pop=0,60), carteira, plano curto prazo, plano de domínio ou qualquer artefato oficial do M1. NÃO alterar a fórmula de `score_oportunidade_residual` em produção nem regenerar `hexagonos_mercado_mapeado.parquet`/derivados. Candidatos existem só EM MEMÓRIA / relatório de análise.
- **DEC-008:** validação out-of-fold (k-fold repetido) SEMPRE vs baseline da média; R² in-sample BANIDO do veredito; IC95 bootstrap seed-fixa; intervalos + flag de extrapolação; comparação de candidatos out-of-fold; NO-GO é resultado VÁLIDO.
- **DEC-009:** `membros` (demanda) é ALVO OBSERVADO; PROIBIDO usar `membros`/qualquer coluna da camada de demanda como preditor geográfico de magnitude ou ajuste do score.
- **DEC-012 (anti-PII / isolamento):** pacote `demanda_revelada/` DISJUNTO — nunca importa de `pipelines/m1/`, `censo_*`, `dashboard/`, `api` nem `config.py` raiz; zero coluna de `COLUNAS_PII_PROIBIDAS` em qualquer frame/saída; fonte real (`NAO_ABRA/`) nunca tocada; testes só com fixture sintética.
- **DEC-013:** a oferta das academias menores entra só na camada de mercado/residual (candidata), com DEDUP; READ-ONLY sobre o M1 e censitário.
- **Não expandir escopo; um bloco por vez; não implementar (Block Orchestrator).**
