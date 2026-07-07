# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-ATR-03 — Testar a estrutura de leitura: matriz de eixos vs score composto (GO/NO-GO)

## Objetivo
Validar out-of-fold (k-fold 5×5 seed=42/IC95) se um score composto dos 3 eixos de atratividade prevê a demanda observada (`membros`) melhor que cada eixo isolado e melhor que a matriz — emitindo veredito honesto GO/NO-GO em `data/analysis/` (gitignored), sem materializar nada em produção.

## Decisão A vs B (questão central do BO)

**Decisão: OPÇÃO A — usar `share_captura_huff` existente em `hexagonos_mercado_mapeado.parquet`.**

Justificativa:
1. **O teste de estrutura é independente da base de concorrentes.** O objetivo do ATR-03 é responder SE o composto dos 3 eixos agrega sobre os eixos isolados/matriz. Essa resposta é válida com qualquer versão do share_huff — o sinal já tem rho=−0,581 vs membros (Spearman, n=16.411). A questão "densificar melhora o sinal?" foi tratada pelo ATR-01 (código pronto, re-validação empírica ficou como ressalva do QA).
2. **`concorrentes_densos.parquet` NÃO está materializado.** O QA do ATR-01 aprovou com ressalva explícita de que `executar()` (operação cara: ~32k conc × 16k hexes) não foi rodada. Materializar agora seria operação pesada fora do escopo do ATR-03.
3. **Cobertura do share existente é suficiente para o teste.** No join demanda×mercado (n=16.411 hexes), 28,1% têm `share_captura_huff < 1.0` (competitivos). O eixo de disputa é metro-centric — exatamente onde a demanda revelada existe. A degradação graciosa fora do metrô já é requisito explícito do backlog.
4. **Bloqueio de dependência evitado.** Se o ATR-03 esperasse o parquet denso, adicionaria operação pesada sem garantia no loop autônomo. Manter o ATR-03 agnóstico ao parquet denso é mais robusto e coerente com o padrão dos BLK-DIM.

**Nota para o Builder:** o módulo `estrutura_funil.py` DEVE aceitar um parâmetro `conc_path` para permitir substituição futura do arquivo de concorrentes (padrão de `huff_captura.py`). Se o parquet denso existir, pode ser passado externamente — mas NÃO é requisito de aceite do ATR-03.

## Escopo permitido
- Criar `src/motor_expansao/demanda_revelada/estrutura_funil.py` (módulo novo; pacote DISJUNTO)
- Criar `tests/unit/demanda_revelada/test_estrutura_funil.py` (fixtures sintéticas; zero PII)
- Criar `data/analysis/estrutura_funil.md` (veredito gitignored)
- Atualizar `tasks/current_task.md`, `tasks/backlog.md`, `tasks/completed.md` no fechamento
- Atualizar `context/handoff.md` e `context/handoff/` em cada fase

## Fora de escopo
- NÃO materializar `data/staging/concorrentes_densos.parquet` neste bloco
- NÃO chamar `concorrentes_densos.executar()` (operação cara; ressalva do ATR-01 QA)
- NÃO recalcular `score_priorizacao`, `hex_score_estrutural`, carteira, plano, artefatos M1
- NÃO alterar `hexagonos_mercado_mapeado.parquet` nem qualquer artefato M1 oficial
- NÃO importar de `pipelines/m1/`, `dashboard/`, `censo_*`, `api`, `config.py` raiz
- NÃO materializar nada em produção (só `data/analysis/` gitignored)
- NÃO alterar `huff_captura.py` (módulo estável; só IMPORTAR)
- NÃO implementar visualizações (isso é BLK-ATR-04)

## Arquivos que devem ser lidos
- `/repo/CLAUDE.md` — guardrails e parâmetros
- `/repo/tasks/backlog.md` — linhas 1007–1040 (BLK-ATR-03)
- `/repo/src/motor_expansao/demanda_revelada/huff_captura.py` — harness k-fold 5×5, padrão de validação a reutilizar
- `/repo/src/motor_expansao/demanda_revelada/calibracao_residual.py` — harness IC bootstrap, `_selecionar_alpha_e_oof`, constantes SEED/N_BOOTSTRAP
- `/repo/src/motor_expansao/demanda_revelada/contrato.py` — COLUNAS_PII_PROIBIDAS, H3_RES_CONTRATO
- `/repo/src/motor_expansao/dimensionamento/aderencia.py` — LIMIAR_R2_GO, ALPHA_GRID
- `/repo/src/motor_expansao/dimensionamento/backtest_dim.py` — `_r2`, `_rmse`
- `/repo/src/motor_expansao/pipelines/calcular_colunas_mercado.py` — lógica do `flag_gate_atratividade` (linhas ~291–300)
- `/repo/src/motor_expansao/pipelines/pop_corte.py` — `derive_pop_cut_columns` (para computar gate inline)
- `/repo/data/analysis/huff_captura.md` — métricas do eixo Huff (BLK-TP-07; baseline de referência)
- `/repo/data/analysis/calibracao_residual_demanda.md` — métricas do eixo residual (BLK-TP-06)
- `/repo/tasks/completed.md` — entradas BLK-ATR-01 e BLK-ATR-02

## Arquivos que podem ser alterados
- `/repo/src/motor_expansao/demanda_revelada/estrutura_funil.py` (NOVO — criar)
- `/repo/tests/unit/demanda_revelada/test_estrutura_funil.py` (NOVO — criar)
- `/repo/data/analysis/estrutura_funil.md` (NOVO — gitignored; veredito GO/NO-GO)
- `/repo/tasks/current_task.md` (atualização de fase)
- `/repo/context/handoff.md` e `/repo/context/handoff/` (cada fase)
- `/repo/tasks/backlog.md` + `/repo/tasks/completed.md` (só no fechamento do QA)

## Critérios de aceite
1. `estrutura_funil.py` no pacote `demanda_revelada/` (pacote DISJUNTO; sem imports proibidos; `loop_guard` GUARD OK)
2. Valida out-of-fold (k-fold 5×5 seed=42) os seguintes modelos vs alvo `log1p(membros)`:
   - Baseline: média (âncora do R²)
   - Eixo 1 isolado: `score_priorizacao` (sociodemografia)
   - Eixo 2 isolado: `score_oportunidade_residual` (mercado)
   - Eixo 3 isolado: `share_captura_huff` (disputa, degradação graciosa onde share=1.0)
   - Eixo 2b isolado (auditoria): `score_setor_2022_calibrado` (censitário, se disponível no join)
   - Composto: combinação linear Ridge dos 3 eixos (pesos aprendidos out-of-fold)
3. IC95 bootstrap seed=42 para R²_oof de cada modelo; R² in-sample BANIDO do veredito
4. `membros` só como ALVO (nunca preditor); share_huff puro (não recebe o alvo)
5. Gate ATR-02 aplicado inline: `populacao_corte_hex >= 5000 AND renda_per_capita >= 1500` (usando `pop_corte.derive_pop_cut_columns` + coluna `renda_per_capita` do mercado); N pós-gate reportado
6. Degradação graciosa documentada: onde share=1.0 (sem concorrentes na janela), o composto usa 2 eixos (sociodemo + residual); flag `flag_huff_disponivel` + % de hexes afetados
7. Veredito GO/NO-GO honesto: composto GO só se vencer materialmente o melhor eixo isolado E não for redundante; default = matriz; NO-GO é resultado válido (DEC-008)
8. Caveat de cobertura ~1% explícito no relatório; caveat de viés metropolitano
9. mtime dos 4 artefatos M1 oficiais inalterado
10. `pytest tests/unit/demanda_revelada/test_estrutura_funil.py` verde (fixtures sintéticas)
11. `ruff check src/motor_expansao/demanda_revelada/estrutura_funil.py` limpo
12. `import streamlit_app` ok
13. `python scripts/loop_guard.py --base ciclo/loop-20260706-152137` GUARD OK

## Dados disponíveis (confirmados no ambiente)
- `data/staging/demanda_revelada_h3.parquet`: 16.575 hexes; coluna `membros` (alvo)
- `data/staging/hexagonos_mercado_mapeado.parquet`: 1.542.531 hexes com `share_captura_huff` (não-null 100%), `score_priorizacao`, `score_oportunidade_residual`, `score_setor_2022_calibrado` (não-null em ~96% do join), `renda_per_capita`
- Join inner demanda×mercado: n=16.411 hexes; 28,1% com share<1.0 (competitivos)
- Spearman bivariado vs membros (n≈16.411): `share_captura_huff` rho=−0,581 (p≈0); `score_priorizacao` rho=+0,490 (p≈0); `score_oportunidade_residual` rho=+0,517 (p≈0); `score_setor_2022_calibrado` rho=+0,234 (p≈0, n≈15.752)
- `flag_gate_atratividade`: lógica em `calcular_colunas_mercado.py` (~l.291); parquet de staging ainda NÃO regenerado com esta coluna → Builder computa inline

## Criticidade classificada
Alta (decide a arquitetura do funil; READ-ONLY sobre o M1; loop-safe)

## Esteira recomendada
Block Orchestrator → **Planner** → Builder → QA (autônoma no loop)

Modelo por papel (Alta):
- Planner: opus
- Builder: opus
- QA: opus 4.8

## Riscos identificados
1. **Eixo Huff com share=1.0 em ~72% do join** (monopólio local): o Planner deve desenhar o tratamento explícito — flag `flag_huff_disponivel` + sub-análise separada para os ~28% competitivos, com nota de que o eixo Huff é informativo apenas onde há concorrentes na janela.
2. **gate_atratividade não materializado no parquet atual**: o Builder computa inline com `pop_corte + renda_per_capita`. Risco baixo — lógica já existe em `calcular_colunas_mercado.py` (~l.291–300).
3. **N após gate**: o N pós-gate reduzirá a partir de 16.411. O Planner deve prever fallback (se N cair abaixo de N_PISO_KFOLD=200, usar k=10; se cair abaixo de N_PISO_LOO=30, usar LOO + flag_global).
4. **"Vencer a matriz" precisa ser definido operacionalmente**: matriz não é modelo estatístico. O benchmark mais rigoroso = melhor eixo isolado. O composto GO só se R²_oof_composto > max(R²_oof_eixo_isolado) E IC não cruza zero E não é redundante (correlação dos pesos com o melhor eixo < 0,95).
5. **Multicolinearidade dos eixos**: rho residual×share ≈ −0,42 no metrô. Ridge trata, mas as correlações cruzadas devem ser reportadas como covariáveis bivariadas ANTES do modelo.

## Guardrails ativos
- §5 READ-ONLY M1: nenhuma escrita em `score_priorizacao`/`hex_score_estrutural`/carteira/plano/artefatos oficiais; mtime dos 4 oficiais inalterado.
- DEC-008: out-of-fold vs baseline SEMPRE; R² in-sample só campo de auditoria rotulado (nunca no veredito); IC95 seed=42; flag de extrapolação; NO-GO é resultado VÁLIDO.
- DEC-009: `membros` é ALVO OBSERVADO; PROIBIDO usar como preditor geográfico de magnitude ou ajuste do score.
- DEC-012: pacote `demanda_revelada/` DISJUNTO — nunca importa de `pipelines/m1/`, `censo_*`, `dashboard/`, `api`, `config.py` raiz; zero PII em artefato/log/teste; fixtures sintéticas nos testes.
- loop_guard: o diff não pode tocar `config.py`/`pipelines/m1`/`*scoring*`/artefatos M1/`deploy/`/`Dockerfile.*`/compose/Caddy/authelia/`.env`/`secrets/`/CI.
