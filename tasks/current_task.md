# Current Task

## Bloco atual

ID: BLK-ATR-03-FU1
Nome: Re-rodar o teste de estrutura (matriz vs composto) sobre o Huff DENSO
Status: aprovado
Tipo: feature (análise/validação)
Criticidade: alta
Esteira: Block Orchestrator → Planner → Builder → QA (autônoma no loop)
Skill atual: QA (concluída)
Próxima Skill: — (fechamento manual pelo orquestrador: housekeeping move BLK-ATR-03-FU1)

## Resultado do Builder (para o QA)
Veredito honesto: **GO-composto** sobre a base DENSA. Composto R²_oof=+0.5653 (IC95 [+0.5450,+0.5839])
vence o melhor eixo isolado `disputa` (+0.4885) por ganho +0.0768 (> 0.01), não redundante.
Beta denso selecionado OOF = 0.5 (recomputado, não hardcoded). Cobertura Huff (share<1.0) = 96.0%
(vs ~62% no ATR-03 original). n_join=16.411, n_pos_gate=4.630, kfold_5x5.
Comparação ATR-03: composto +0.48 → +0.5653; melhor eixo +0.37 → +0.4885; cobertura 62% → 96%.
Arquivos novos: `src/motor_expansao/demanda_revelada/estrutura_funil_densa.py` +
`tests/unit/demanda_revelada/test_estrutura_funil_densa.py`. Relatório `data/analysis/estrutura_funil_densa.md`
(gitignored, NÃO commitar). ruff+mypy limpos; subset 32 passed; smoke import ok; mtimes M1 + densa INALTERADOS.

## Objetivo
Re-rodar o harness `estrutura_funil` (k-fold 5×5, seed=42, IC95) com o `share_captura_huff` DENSO
(base ATR-01, `concorrentes_densos.parquet`, 10.165 pares, 40 redes) em vez do original (~3,3 mil),
reportar R²_oof atualizado do composto vs eixos isolados vs baseline, e re-emitir o veredito matriz
vs composto. READ-ONLY sobre o M1; veredito em data/analysis/ (gitignored).

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/loop-20260707-123809 (branch do loop autônomo atual)

## Paths do ciclo (commit por path — NUNCA git add -A)
- src/motor_expansao/demanda_revelada/ (módulo novo do FU1 — apenas arquivos novos)
- tests/unit/demanda_revelada/ (testes novos)
- data/analysis/ (relatório gitignored — não commitado)
- tasks/current_task.md, tasks/completed.md, tasks/backlog.md (fechamento)
- context/handoff.md, context/handoff/

## Guardrails
- §5 READ-ONLY M1: zero recálculo de score/pesos/carteira/plano/artefatos oficiais.
- DEC-008: out-of-fold obrigatório vs baseline; R² in-sample BANIDO do veredito; NO-GO é veredito válido.
- DEC-009: `membros` só como ALVO (nunca preditor geográfico de magnitude).
- DEC-012: sem PII pessoal; pacote disjunto (sem import de pipelines/m1/, censo_*, dashboard/, api/, config.py raiz).
- Veredito em data/analysis/ (gitignored); sem materialização em produção.

## Contexto técnico resumido (para o Planner)

**Insumos disponíveis:**
- `data/staging/concorrentes_densos.parquet` — 10.165 pares (hex_id_res7, rede_normalizada), colunas `lat`/`lng` prontas (centroides de hex via h3)
- `data/staging/demanda_revelada_h3.parquet` — 16.575 hexes, coluna `membros` (alvo)
- `src/motor_expansao/demanda_revelada/estrutura_funil.py` — harness PURO `avaliar_estrutura_funil(df_join)` + `escrever_relatorio`
- `src/motor_expansao/demanda_revelada/huff_captura.py` — `calcular_share_por_hex`, BETA_GRID
- `src/motor_expansao/demanda_revelada/concorrentes_densos.py` — `_coords_densas` para extrair lat/lng do parquet denso

**O que precisa ser feito:**
1. Extrair `(conc_lat, conc_lng)` do `concorrentes_densos.parquet` via `_coords_densas`.
2. Recomputar `share_captura_huff` por hex usando `calcular_share_por_hex` com beta selecionado OOF.
3. Substituir o `share_captura_huff` no frame de join (demanda × mercado).
4. Chamar `avaliar_estrutura_funil(df_join_denso)` — função pura, sem I/O.
5. Escrever relatório `data/analysis/estrutura_funil_densa.md` via `escrever_relatorio`.

**Números de referência:**
- ATR-03 original: composto R²_oof = +0,48, melhor eixo = +0,37, cobertura Huff ≈ 62%. Veredito: GO-composto.
- ATR-01 (Huff isolado com base densa): R²_oof = +0,46, rho = +0,71, cobertura = 73%.
- FU1 esperado: composto provavelmente sobe, mas o número precisa ser recomputado honestamente.
