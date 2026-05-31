# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-SCORE-04 — Backtest read-only multivariado das features mercado/censitárias vs. desfecho.**
Continuação analítica direta do BLK-SCORE-02 (mesmo método/estilo/script), respondendo à
pergunta levantada no BLK-SCORE-03: "outras variáveis além de pop/renda ajudam / são
significativas?". MEDE poder preditivo INDIVIDUAL e CONJUNTO das features reais das camadas
mercado/competição e censitária contra o desfecho `alunos_recorrentes`. NÃO cria nem altera
score. Read-only estrito sobre o M1 e todos os artefatos oficiais.

## Objetivo
Produzir evidência quantitativa (read-only) de quais features das camadas mercado/censitária
correlacionam com `alunos_recorrentes`, por rede (ultra/skyfit/engcorpo) e no agregado (AGG),
para fundamentar — com dado, não com palpite — um eventual enriquecimento FUTURO dos scores
OPERACIONAIS (censitário/mercado). O resultado é base de EVIDÊNCIA; qualquer mudança de score
posterior é outro bloco com seu próprio gate. Conecta ao gate G4 da DEC-001 (reabertura do M1
só sob pré-requisitos + sinal significativo, e ainda assim em bloco crítico separado).

## Escopo permitido
- Reusar `analysis/score_backtest.py` (funções puras: `correlate`, `correlate_by_cell`,
  `bootstrap_ci_spearman`, `pairwise_valid`, e estilo de `build_report`). Importar — NÃO duplicar
  a lógica.
- Criar UM script novo (sugerido `analysis/feature_backtest_mercado.py`) que:
  - carrega `data/analysis/dataset_validacao.parquet` (441 linhas; `hex_id`, `rede`,
    `alunos_recorrentes`, `score_setor_2022_calibrado` já presentes) e
    `data/staging/hexagonos_mercado_mapeado.parquet` lendo SÓ as colunas candidatas + `hex_id`
    (a fonte tem 1.537.950 linhas × 131 cols — nunca carregar inteira; dedup por `hex_id`
    com `drop_duplicates(subset=['hex_id'], keep='first')` antes do join, igual a `join_componentes`);
  - faz LEFT-JOIN por `hex_id` (dataset à esquerda) e REPORTA a taxa de match das linhas com
    `hex_id` (no BLK-SCORE-02 o match foi 357/391 = 91,3%; 50 linhas sem hex);
  - para cada feature candidata roda `correlate_by_cell` (Spearman rho + Pearson r + p; AGG +
    por rede; N_MIN=10; `to_numeric` coerce) e `bootstrap_ci_spearman` (seed=42, n_boot=2000)
    no AGG quando N>=30;
  - produz `data/analysis/relatorio_backtest_mercado.md`: tabela por feature × célula
    (rho/p/r/p/N/flag), ranking por |rho| no AGG, e seção de Limitações herdadas do BLK-SCORE-02.
- Leitura de sinal CONJUNTO OPCIONAL e PURAMENTE diagnóstica: regressão multivariável simples
  (OLS / `numpy.linalg.lstsq` ou `scipy`) ou importância relativa, SÓ para ler "quais features
  carregam sinal além de pop/renda". NÃO materializa nenhum score novo, NÃO escreve coeficientes
  em artefato algum, fica só no relatório. Padronizar/normalizar features só em memória.
- Marcar como **"indefinido"** (não calcular correlação) toda feature com input constante /
  variância zero na subamostra casada — `correlate` já devolve `motivo='variancia_zero'`; o
  relatório deve exibir isso em vez de inventar correlação.
- Testes unitários sintéticos novos (se houver função pura própria, ex.: leitura de OLS
  diagnóstico ou montagem do relatório de features), estilo `tests/unit/test_score_backtest.py`,
  SEM depender do parquet real gitignored (CI não tem as fontes). Sugerido
  `tests/unit/test_feature_backtest_mercado.py`.

## Fora de escopo
- Qualquer escrita/recálculo de `score_priorizacao`, `hex_score_estrutural`, pesos (0.40/0.60),
  `scoring.py`, `constants.py`, carteira, plano, ou qualquer artefato oficial / `data/outputs/`.
- Criar um score novo, persistir coeficientes de regressão, propor nova fórmula ou peso.
- Editar o M1 a partir das colunas zeradas (`n_domicilios`/`densidade_dom`) — DEC-001 trava isso.
- Qualquer saída fora de `data/analysis/` (gitignored). Sem PII (`nome_unidade` nunca no relatório).
- Mexer no `relatorio_backtest.md` do BLK-SCORE-02 (é outro artefato; este é novo).
- Geocodificação, dashboard, deploy, comandos no VPS.
- Commits/`git add` (o Builder/QA cuidam disso no fim; aqui não).

## Arquivos que devem ser lidos
- `CLAUDE.md` — §1 Norte reenquadrada (M1 = executiva; censitário = primária operacional),
  §2 regra de criticidade (M1 read-only → Alta), §4 camada mercado, §8 DEC-001 (gates G1–G4).
- `tasks/current_task.md` — bloco ativo BLK-SCORE-04.
- `tasks/backlog.md` (linhas ~63-114) — escopo, colunas candidatas, método, critérios de aceite.
- `analysis/score_backtest.py` — funções puras a REUSAR (`correlate`, `correlate_by_cell`,
  `bootstrap_ci_spearman`, `pairwise_valid`, `join_componentes`, `build_report`, `load_inputs`).
- `tests/unit/test_score_backtest.py` — padrão de teste sintético a espelhar.
- `data/analysis/relatorio_backtest.md` — método e §5 Limitações do BLK-SCORE-02 a herdar.
- `docs/modelo_mercado_hexagonos.md` — contrato das colunas mercado/residual (definição das
  features candidatas, antes de interpretá-las).

## Arquivos que podem ser alterados
- `analysis/feature_backtest_mercado.py` (NOVO — script do backtest de features).
- `tests/unit/test_feature_backtest_mercado.py` (NOVO — testes sintéticos das funções puras próprias).
- `data/analysis/relatorio_backtest_mercado.md` (NOVO; gitignored — saída gerada pelo script).
- (se reaproveitar import e for estritamente necessário expor uma função pura já existente, pode
  tocar `analysis/score_backtest.py` SÓ para `import`/refactor não-comportamental — preferir NÃO
  alterá-lo; se alterar, manter todos os testes existentes verdes.)

## Critérios de aceite
1. `data/analysis/relatorio_backtest_mercado.md` com: tabela por feature × célula
   (Spearman rho / p / Pearson r / p / N / flag), ranking por |rho| no AGG, IC95% bootstrap no
   AGG para N>=30, e seção de Limitações herdada do BLK-SCORE-02 (§5).
2. Taxa de match do join `hex_id` reportada explicitamente no relatório.
3. Features com input constante / variância zero na amostra casada marcadas **"indefinido"**
   (não inventar correlação).
4. (Se feita) leitura de sinal conjunto reportada SÓ como diagnóstico, sem score novo nem
   coeficientes persistidos em artefato.
5. ZERO escrita em M1 / artefatos oficiais / `data/outputs/`; ZERO PII no relatório.
6. Reprodutível: seed fixo = 42; script versionado; figuras (se houver) sob try/except,
   gitignored, nunca derrubam a execução.
7. Testes novos sintéticos passam; suite existente continua verde (baseline 532 passed).

## Criticidade classificada
Alta

## Esteira recomendada
Block Orchestrator → Planner → [REVISÃO HUMANA] → Builder → QA

## Riscos identificados
- **Colinearidade entre features de mercado.** Várias derivam da mesma base de concorrentes/oferta
  (`n_concorrentes_*`, `oferta_efetiva_*`, `gap_competitivo_2km`, `pressao_concorrencial_score_2km`,
  `share_*_2km`). Correlações individuais serão redundantes; o sinal conjunto (OLS/importância)
  pode ficar instável. Reportar a redundância; o Planner pode podar features colineares.
- **Features near-constant na subamostra casada.** Verificado na fonte nacional:
  `n_unidades_ultra_1km`/`n_unidades_ultra_2km` têm nunique=4 (0–3) no Brasil inteiro — na
  subamostra de ~357 hexes casados podem ficar quase constantes → cair em "variância_zero".
  Aplicar a marcação "indefinido", não forçar.
- **Sentinela em `dist_concorrente_mais_proximo_m`.** max ≈ 1.2e6 m (hex sem concorrente mapeado
  no raio recebe distância gigante). Pode distorcer Pearson; Spearman é mais robusto, mas avaliar
  se trata como valor real ou marca como ausente. Decisão do Planner — documentar a escolha.
- **`score_setor_2022_calibrado` já existe no `dataset_validacao`** (e na fonte mercado). Ao juntar,
  evitar sobrescrever a coluna do dataset; usar sufixo (`_merc`, padrão de `join_componentes`) ou
  selecionar explicitamente. Decidir QUAL coluna usar como âncora e registrar (são datasets
  diferentes; idealmente reusar a já presente no dataset para coerência com o BLK-SCORE-02, que
  reportou rho +0.148).
- **Cobertura censitária ~84,7%** das features de setor na fonte (`pop_total_setor_2022`,
  `densidade_pop_setor_hab_km2`, `score_setor_2022_calibrado`); na subamostra casada o N pode cair.
- **Confounds herdados do BLK-SCORE-02 (§5):** maturação indisponível (constante única), desfecho
  heterogêneo entre redes, EngCorpo estimado (alunos/m²×metragem), hex por centroide de cidade em
  parte das linhas, N pequeno por rede. Relatar incerteza; não forçar significância; cuidado com
  correlações espúrias e com p-hacking ao testar muitas features (mencionar multiplicidade de testes).
- **Tamanho da fonte (1,5M linhas).** Carregar `hexagonos_mercado_mapeado.parquet` inteiro é caro;
  ler só `columns=[...]` necessárias e dedup por `hex_id`.

## Guardrails ativos
- READ-ONLY ESTRITO sobre o M1 e TODOS os artefatos oficiais (`score_priorizacao`,
  `hex_score_estrutural`, pesos 0.40/0.60, `scoring.py`, `constants.py`, carteira, plano,
  `data/outputs/`, `brasil_*.parquet`, `hexagonos_brasil_*.parquet`). Só MEDE; não cria/altera score.
- Saída exclusivamente em `data/analysis/` (gitignored). Sem PII (sem `nome_unidade`) no relatório.
- DEC-001 vigente: M1 não recalibra; `n_domicilios`/`densidade_dom` são placeholders zerados e
  ficam FORA deste bloco. Este bloco alimenta o gate G4 com evidência, não o aciona.
- Criticidade Alta ⇒ REVISÃO HUMANA obrigatória após o Planner, antes do Builder.
- Reprodutibilidade: seed=42, n_boot=2000, N_MIN=10 (idênticos ao BLK-SCORE-02).
- Commit só por path; nunca `git add -A`. Sem commits nesta etapa.
- Nenhum comando no VPS / MCP SSH.
