# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-DIM-08 — Teste discriminativo do mercado residual (performers × underperformers) + estrutura regional

## Objetivo
Medir, honestamente via LOO-CV, se o mercado residual endereçável (`oferta_efetiva_disponivel` / `score_oportunidade_residual` recalculados no raio variável do DIM-07) discrimina unidades viáveis (≥2.000 alunos) das inviáveis (<2.000) melhor que `pop+renda` em raio fixo, separando os efeitos região × marca × domínio para evitar vazamento do efeito de domínio da Engenharia-Sul para "mercado intrínseco".

## Contexto dos dados (auditado pelo BO)

### Base multi-rede (BLK-DIM-07)
- Arquivo: `data/staging/base_calibracao_multirede.parquet` (426 linhas, 9 colunas)
- Colunas: `unidade`, `marca`, `uf`, `cidade`, `lat`, `lng`, `alunos_reais`, `metragem`, `flag_qualidade_match`
- **275 unidades com coordenada**; **267 com alunos_reais** — N efetivo ≈ 267 (o parquet ainda não tem `raio_km` nem `pop_captacao_*` — essas colunas saem de `validar_raio_variavel()`, que deve ser re-executada no Builder)
- Marcas: Ultra 54 (98% match), Engenharia 61 (62%), SkyFit 311 (59%)
- Piso de viabilidade: `PISO_VIABILIDADE_ALUNOS = 2.000` (exportado de `base_multirede.py`)
- Labels: 166 viáveis (≥2k) / 101 inviáveis (<2k) dentre os 267 com alunos

### Estrutura regional (relevante para Teste C)
- 23 UFs representadas; SP concentra 126 unidades (47% do N)
- Domínio Engenharia-Sul: 25 unidades em RS+SC+PR (80% viáveis, média 3.190 alunos) — caso de domínio real confirmado; é o confundidor que o Teste C deve isolar

### Parquet residual (H3)
- `data/staging/hexagonos_mercado_mapeado.parquet`: colunas `score_oportunidade_residual`, `oferta_efetiva_disponivel`, `hex_id`, `lat`, `lng`, `uf`, `nome_municipio`, `renda_per_capita`, `pop_total`
- O join das unidades da base_calibracao com o hex residual se faz via `h3.latlng_to_cell(lat, lng, resolution=7)` (mesmo H3_RESOLUTION=7 do M1)

### Baseline para Teste B
- Baseline do M1: `pop_total + renda_per_capita` em raio fixo 1,5 km — o DIM-07 confirmou R²_LOO ≈ −0,005 para raio fixo; o residual deve bater esse baseline no AUC de discriminação

## Escopo permitido

### Módulo a criar
- `src/motor_expansao/dimensionamento/residual_discriminacao.py` — análise READ-ONLY; não altera parquets nem M1

### O módulo deve implementar

1. **`enriquecer_base_com_residual(base_path, mercado_path) -> pd.DataFrame`**: faz o join unidade com hex H3 (h3.latlng_to_cell resolution=7) para trazer `score_oportunidade_residual`, `oferta_efetiva_disponivel`, `renda_per_capita` (hex), `pop_total` (hex) para cada unidade com coordenada. Flag `hex_match_ok` para transparência.

2. **`enriquecer_com_raio_e_dominio(base, conc_path, geo_base_dir) -> tuple[pd.DataFrame, dict]`**: chama `validar_raio_variavel()` (de `base_multirede.py`) para obter `raio_km`, `pop_captacao_variavel` e `n_concorrentes_km2`; depois chama `derivar_densidade_marca_propria()` para `n_mesma_marca_no_raio` (controle de domínio). Retorna (base_enriquecida, metricas_raio).

3. **`calcular_residual_no_raio_variavel(base) -> pd.DataFrame`**: penetração observada = `alunos_reais / pop_captacao_variavel`; flag `flag_viavel = alunos_reais >= PISO_VIABILIDADE_ALUNOS`. Prepara base analítica para os testes B e C.

4. **`teste_b_discriminacao(base) -> dict`**: Teste B — discriminação LOO:
   - Feature principal: `score_oportunidade_residual` (hex H3)
   - Baseline: `pop_captacao_fixo_1p5` × `renda_per_capita` (raio fixo, como no DIM-01R)
   - Métrica: **AUC ROC com IC bootstrap** (N=1.000 reamostras) para cada feature vs. `flag_viavel`
   - Anti-circularidade: penetração regional calculada leave-one-unit-out (cada unidade excluída do cluster de UF ao estimar a penetração média do cluster)
   - Reportar: AUC residual vs. AUC baseline, delta AUC, IC 95%, p-valor de permutação (N=500), veredito GO/NO-GO com limiar `AUC > 0.55 E IC inferior > 0.50`

5. **`teste_c_decomposicao_variancia(base) -> dict`**: Teste C — decomposição região × marca × domínio:
   - Variável resposta: `log(penetracao_observada)` (leave-one-unit-out por UF-cluster)
   - Efeitos: (a) `regiao` = cluster de UF (macro-região Sul/Sudeste/CO+Norte/Nordeste se células ralas); (b) `marca` = dummy ultra/engenharia/skyfit; (c) `dominio` = `n_mesma_marca_no_raio` (variável contínua)
   - Método: OLS com dummies (scipy.stats ou numpy direto; sem dependência nova) + variância explicada por componente via ANOVA-sequencial (SS tipo I); se N célula ≥ 5 e convergência, tentar MixedLM como alternativa — fallback gracioso para OLS
   - Anti-circularidade: penetração do cluster = média das OUTRAS unidades do cluster (leave-one-unit-out)
   - Caso Engenharia-Sul: reportar coeficiente de domínio e uplift estimado por unidade adicional de marca própria no catchment, com IC 95% (se N ≥ 5)
   - Penetração-base líquida de domínio: penetração predita para `n_mesma_marca_no_raio = 0` (nova entrada sem saturação própria), reportada por macro-região com IC

6. **`sanidade_casos(base) -> dict`**: verifica se as unidades <2k caem de fato em hexes de `score_oportunidade_residual` baixo (quartil inferior do dataset de treino). True negative rate.

7. **`escrever_relatorio(resultado, path) -> None`**: materializa `data/analysis/residual_discriminacao.md` (gitignored) com:
   - Header obrigatório: "READ-ONLY sobre o M1 (DEC-001/DEC-008). Sem PII."
   - Seção 1: resumo do enriquecimento (N base, N com hex match, N com coord+alunos)
   - Seção 2: Teste B — tabela AUC + IC + veredito GO/NO-GO
   - Seção 3: Teste C — tabela de variância explicada por componente + coeficiente de domínio + penetração-base líquida por macro-região
   - Seção 4: Sanidade dos casos (<2k) — true negative rate
   - Seção 5: Veredito consolidado da tese residual com ressalvas de confounds (N ralo em células, viés de seleção, heterogeneidade marcas)
   - NUNCA reportar "este hex terá N alunos" — saída como score/ranking/discriminação

### Testes a criar
- `tests/unit/dimensionamento/test_residual_discriminacao.py` — fixtures sintéticas (nunca tocam xlsx reais nem censo):
  - Fixture mínima: DataFrame com 30 unidades sintéticas (10 por marca, 3 regiões, `alunos_reais` variando de 800 a 5.000, `lat/lng` sintéticos de coordenadas brasileiras reais, `score_oportunidade_residual` e `oferta_efetiva_disponivel` derivados)
  - Testes obrigatórios: `test_enriquecer_base_shape`, `test_flag_viavel_piso_2000`, `test_teste_b_retorna_dict_com_auc`, `test_auc_sempre_entre_0_e_1`, `test_teste_c_decomposicao_retorna_componentes`, `test_escrever_relatorio_sem_pii`, `test_saida_nao_tem_predicao_pontual_de_alunos`, `test_guardrail_anti_circular_penetracao`, `test_sanidade_casos_retorna_tnr`, `test_relatorio_tem_secoes_obrigatorias`
  - Cobertura mínima: 10 testes, todos offline (sem IO de parquets reais, sem censo)

## Fora de escopo
- Modelo de Huff completo (BLK-DIM-02R)
- Recalibração de score M1 (`score_priorizacao`, pesos, `hex_score_estrutural`, artefatos oficiais)
- Qualquer escrita em `data/staging/hexagonos_mercado_mapeado.parquet` ou outros artefatos oficiais
- Recalibração da camada Expansão de Domínio (efeito de domínio aqui é só diagnóstico/insumo para bloco futuro)
- Geocoding online (todas as coords são locais)
- PII em qualquer artefato de saída
- Previsão pontual de alunos ("este hex terá N alunos") — proibido explicitamente por guardrail Felipe 2026-06-15
- BLK-DIM-09 (crosswalk manual da cauda ambígua) — bloco separado e condicional
- Alterações em `config.py` (raiz M1), `src/motor_expansao/pipelines/m1/`, arquivos em `data/staging/brasil_*.parquet`, `data/outputs/`, `streamlit_app.py`, `src/motor_expansao/dashboard/`

## Arquivos que devem ser lidos
- `/repo/src/motor_expansao/dimensionamento/base_multirede.py` — funções a reusar: `validar_raio_variavel`, `derivar_densidade_marca_propria`, `PISO_VIABILIDADE_ALUNOS`, `haversine_km`, `RAIO_KM_FIXO_BASELINE`, `CONCORRENTES_PATH`, `SAIDA_BASE`
- `/repo/src/motor_expansao/dimensionamento/aderencia.py` — padrão LOO honesto; `_r2_loo_para_alpha` reutilizável
- `/repo/src/motor_expansao/dimensionamento/catchment_batch.py` — `calcular_catchment_unidade`, `GEO_BASE_DIR_DEFAULT`
- `/repo/src/motor_expansao/dimensionamento/config.py` — `STAGING_DIR`, `RAIO_CATCHMENT_KM`, `PII_COLUNAS_PROIBIDAS`
- `/repo/src/motor_expansao/dimensionamento/growth_api_client.py` — `assert_sem_pii`
- `/repo/tests/unit/dimensionamento/test_base_multirede.py` — padrão de fixtures sintéticas a seguir
- `/repo/data/analysis/catchment_variavel.md` — métricas do DIM-07 (veredito `raio_variavel_aceito_para_estabilidade`; CV 1,15→0,47; R²_LOO ≈ 0)
- `/repo/tasks/backlog.md` (linhas 440–535) — spec completa do BLK-DIM-08
- `/repo/CLAUDE.md` — guardrails §2, §3, §5 (M1 READ-ONLY), §6.1 (loop-safe); DEC-001, DEC-008

## Arquivos que podem ser alterados
- `src/motor_expansao/dimensionamento/residual_discriminacao.py` — CRIAR (módulo novo)
- `tests/unit/dimensionamento/test_residual_discriminacao.py` — CRIAR (testes novos)
- `data/analysis/residual_discriminacao.md` — CRIAR (gitignored, gerado ao rodar com dados reais)
- `src/motor_expansao/dimensionamento/__init__.py` — exportar o novo módulo se necessário (mínimo)

NUNCA alterar: `config.py` (raiz M1), `src/motor_expansao/pipelines/m1/`, `data/staging/brasil_*.parquet`, `data/staging/hexagonos_brasil_*.parquet`, `data/outputs/`, `streamlit_app.py`, `src/motor_expansao/dashboard/`

## Critérios de aceite
- `ruff check src/motor_expansao/dimensionamento/residual_discriminacao.py` — zero erros
- `mypy src/motor_expansao/dimensionamento/residual_discriminacao.py` — limpo ou só stubs externos conhecidos
- `pytest tests/unit/dimensionamento/test_residual_discriminacao.py -v` — todos os ≥10 testes passam (offline)
- Suite completa `pytest -q` — sem regressão nos 130 testes existentes do módulo `dimensionamento/`
- `data/analysis/residual_discriminacao.md` materializado com: AUC+IC do Teste B, decomposição de variância do Teste C, veredito GO/NO-GO explícito, flag de confounds
- Relatório NÃO contém previsão pontual de alunos sem ressalva de IC/ranking
- `assert_sem_pii(base_enriquecida)` não levanta em nenhum ponto do pipeline
- ZERO escrita em artefatos M1 (verificado pelo `loop_guard.py` no diff do commit)
- Reprodutível: rodando o módulo com os parquets disponíveis, gera o relatório

## Criticidade classificada
Alta

## Esteira recomendada
Block Orchestrator → Planner → [guard automático no loop] → Builder → QA

## Riscos identificados
- **N ralo em células região×marca×domínio:** SP concentra 47% do N, quase tudo SkyFit; Engenharia está concentrada no Sul (25 un.). Células com <5 observações não suportam regressão — Builder deve colapsar UFs em macro-regiões (Sul, Sudeste, CO+Norte, Nordeste) e reportar flag `n_celula_insuficiente` quando N < 5
- **Anti-circularidade da penetração LOO:** penetração regional NÃO pode incluir a própria unidade sendo avaliada (vazamento de desfecho para feature). Builder deve usar leave-one-unit-out estrito por UF/cluster. Testes devem verificar a exclusão
- **Join unidade com hex H3:** h3.latlng_to_cell pode falhar para lat/lng inválidos; coordenadas sintéticas nos testes devem ser brasileiras reais (ex.: SP: -23.5, -46.6) para H3 correto. Verificar que `h3` está no ambiente (já é dep do projeto)
- **Confundidor viés de seleção:** as 3 redes não são amostra aleatória; Ultra 98% match, SkyFit/Engenharia 59%/62%. Underperformers podem estar sub-representados nas redes com match mais baixo — qualificar o GO/NO-GO com esse confundidor
- **`oferta_efetiva_disponivel` do hex H3 não é do catchment variável:** é a oferta do hex H3 res=7 (~1 km²), não do catchment da unidade. Builder deve documentar essa limitação e usar como proxy, não como verdade do catchment
- **scipy MixedLM com grupos pequenos:** se não converge (comum com grupos desbalanceados), fallback para OLS com dummies de macro-região; documentar a escolha no relatório
- **Heterogeneidade de ticket entre marcas:** premissa de ticket similar (~±10-15%) confirmada pelo backlog mas não verificada nos dados; Builder deve reportar média de `alunos_reais` por marca para confirmar

## Guardrails ativos
- READ-ONLY M1 (DEC-001/DEC-008): zero escrita em `score_priorizacao`, `hex_score_estrutural`, pesos `renda=0.40`/`pop=0.60`, ou qualquer artefato em `data/staging/brasil_*.parquet`/`data/outputs/`
- Anti-circularidade LOO: penetração regional SEMPRE calculada leave-one-unit-out; raio variável derivado de densidade+oferta concorrente, NUNCA de `alunos_reais`
- Anti-PII: `assert_sem_pii(base)` antes de qualquer `to_parquet`; nomes de unidade em relatório apenas como rótulo não-pessoal; `data/validacao/*.xlsx` NUNCA em disco de saída
- Output como score/ranking, NUNCA previsão pontual: proibido reportar "este hex terá N alunos"; saída é AUC, IC, variância explicada, penetração-base por macro-região (agregado), veredito GO/NO-GO
- Loop-safe confirmado: bloco não toca VPS/deploy/segredos/CI; consome só `data/staging` (parquets locais); guard `loop_guard.py` verifica o diff após o Builder
- NO-GO é resultado válido: se AUC ≤ 0.55 ou IC inferior ≤ 0.50, o veredito é NO-GO honesto da tese residual — não forçar GO
