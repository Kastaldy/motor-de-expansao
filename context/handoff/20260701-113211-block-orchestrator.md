# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-LTV-02 — Join territorial (pendurar retenção/LTV no hexágono da unidade)

## Objetivo
Via `hex_id` da ponte `data/staging/unidade_hex.parquet` (BLK-LTV-01 concluído), unir as
métricas de retenção/LTV do Lifetime às features territoriais do Motor e gravar o dataset
analítico `data/staging/unidade_territorio_retencao.parquet` (88 linhas, uma por unidade
Lifetime, incluindo as 32 sem `hex_id`).

## Escopo permitido
- Criar `src/motor_expansao/lifetime/join_territorio_retencao.py` — módulo novo dentro do
  pacote `lifetime` já existente (mesmo pacote do BLK-LTV-01; NÃO criar pacote `ltv/`).
- Criar `tests/unit/test_join_territorio_retencao.py` — testes unitários com fixtures sintéticas.
- Gravar `data/staging/unidade_territorio_retencao.parquet` (artefato novo, NOT oficial do M1).
- Ler (somente leitura) os três insumos descritos abaixo.
- Derivar coluna `prob_cancel_90d_media_absoluta` e emitir log de cobertura.

## Fora de escopo
- NÃO criar `src/motor_expansao/ltv/` — o pacote já se chama `lifetime/` e o novo módulo
  entra dentro dele.
- NÃO alterar nenhum arquivo em `src/motor_expansao/pipelines/m1/`.
- NÃO recalcular nem reescrever `score_priorizacao`, `hex_score_estrutural`, nem qualquer
  artefato oficial do M1 (DEC-001 intacta).
- NÃO escrever em `hexagonos_mercado_mapeado.parquet` nem em qualquer artefato existente
  — somente leitura dos três insumos.
- NÃO usar `brasil_priorizados.parquet` como fonte de features territoriais (só 19 colunas;
  faltam `score_expansao_hibrido`, concorrentes, densidade — incompleto para este fim).
- NÃO importar de `src/motor_expansao/dashboard/`, `src/motor_expansao/pipelines/m1/`,
  `censo_*` ou `api/` no módulo novo.
- NÃO implementar análise de correlação (isso é BLK-LTV-03).
- NÃO implementar score M2 (isso é BLK-LTV-04, bloqueado em gate).

## Arquivos que devem ser lidos

### Insumos do join (schemas confirmados por inspeção real em 2026-07-01)

**`data/staging/unidade_hex.parquet`** — ponte geocodificada (BLK-LTV-01).
- Shape: (88, 9).
- Colunas: `cod_unidade` (object, ex: "01"), `unidade`, `uf`, `lat`, `lng`,
  `hex_id`, `metodo_match`, `match_score`, `fonte_geo`.
- Cobertura real: exato=43, perf_hex=10, fuzzy=4 → 56 com `hex_id` não-nulo;
  sem_match=31, mais 1 implícito → 32 com `hex_id` nulo.

**`data/ultra/unidade_para_motor.parquet`** — métricas Lifetime por unidade.
- Shape: (88, 50). Chave: `COD_UNIDADE` (object, mesmo domínio que `cod_unidade` — atenção
  ao case: bridge usa minúscula, Lifetime usa maiúscula → normalizar no merge).
- Join confirmado: `bridge.cod_unidade == ltv.COD_UNIDADE` → 88/88 matched (1-para-1).
- Colunas obrigatórias a carregar (nomes CONFIRMADOS):
  - Identificação: `COD_UNIDADE`, `UNIDADE`, `UF`, `N_ALUNOS`, `TICKET_MEDIO_UNIDADE`,
    `RECEITA_MENSAL_TOTAL`
  - Retenção 90d: `PROB_CANCEL_90D_MEDIA`, `PROB_CANCEL_90D_P50`
  - Retenção 12M: `P_CANCEL_12M_MEDIA`, `P_CANCEL_12M_P50`,
    `E_MESES_ATIVOS_12M_MEDIANO`
  - LTV: `LTV_PROSPECTIVO_12M_MEDIANO`, `LTV_PROSPECTIVO_12M_MEDIO`,
    `LTV_PROSPECTIVO_12M_TOTAL`
  - Durabilidade: `PCT_LTV_FRAGIL`, `PCT_LTV_EM_RISCO`, `PCT_LTV_DURAVEL`,
    `PCT_LTV_ALTA_DURABILIDADE`
  - Flags de uso: `CONFIABILIDADE_UNIDADE`, `USAR_PROB_ABSOLUTA` ("Sim"/"Nao"),
    `USAR_RANKING` ("Sim"/"Nao")
  - Distribuição de risco: `USAR_PROB_ABSOLUTA` → 59 "Sim" / 29 "Nao"

**`data/staging/hexagonos_mercado_mapeado.parquet`** — features territoriais por hex_id.
- Shape: (1.542.531, 135). Usar `columns=[...]` no `read_parquet` — NÃO carregar todas as
  135 colunas.
- Colunas territoriais a extrair (TODAS confirmadas presentes via inspeção):
  - `hex_id` (chave de join)
  - `renda_per_capita` — 0 nulls nos 56 hexes matched
  - `score_priorizacao` — 0 nulls (READ-ONLY; nunca alterar)
  - `score_expansao_hibrido` — 0 nulls
  - `n_concorrentes_mapeados_1km` — 0 nulls
  - `n_concorrentes_mapeados_2km` — 0 nulls
  - `pop_total_setor_2022` — 7 nulls nos 56 hexes (fallback: NaN, documentar)
  - `densidade_pop_setor_hab_km2` — 7 nulls nos 56 hexes (nome exato; NÃO "densidade")
  - `score_setor_2022_calibrado` — muitos nulls no nacional (~240k); para os 56 hexes
    matched verificar em runtime; manter NaN se ausente
  - `score_oportunidade_residual` — 0 nulls
  - `oferta_efetiva_disponivel` — presente (coluna de contexto de mercado)
  - `flag_canibalizacao_ultra_1km` — 0 nulls (bool)
- Estratégia: filtrar para o subset de 56 `hex_id` ANTES do merge para evitar OOM.

### Código existente de referência (ler para seguir padrão)
- `src/motor_expansao/lifetime/ponte_unidade_hex.py` — padrão: constantes no topo, funções
  puras, `build_*()` + `run(root=None)`, zero imports de m1/censo/dashboard.
- `src/motor_expansao/lifetime/__init__.py`
- `tests/unit/test_ponte_unidade_hex.py` — padrão de teste da trilha (fixtures sintéticas)
- `data/ultra/unidade_para_motor_DICIONARIO.md` — contrato semântico (obrigatório)

## Arquivos que podem ser alterados / criados
- **CRIAR** `src/motor_expansao/lifetime/join_territorio_retencao.py` (módulo novo)
- **CRIAR** `tests/unit/test_join_territorio_retencao.py` (testes novos)
- **GRAVAR** `data/staging/unidade_territorio_retencao.parquet` (artefato novo, não M1)
- `context/handoff.md` e snapshot (orquestração)
- `tasks/current_task.md` (atualização de Skill ativa)

## Schema de saída de `unidade_territorio_retencao.parquet`
88 linhas (todas as unidades Lifetime), com colunas:

| Coluna | Origem | Observação |
|--------|--------|-----------|
| `cod_unidade` | ponte | chave primária |
| `hex_id` | ponte | nulo para 32 sem match |
| `metodo_match` | ponte | exato/fuzzy/perf_hex/sem_match |
| `match_score` | ponte | 0.0 para sem_match |
| `UNIDADE`, `UF` | ltv | nome e estado |
| `N_ALUNOS` | ltv | tamanho da carteira |
| `PROB_CANCEL_90D_MEDIA` | ltv | churn 90d bruto |
| `LTV_PROSPECTIVO_12M_MEDIANO` | ltv | LTV mediano por aluno (grão unidade) |
| `USAR_PROB_ABSOLUTA` | ltv | "Sim"/"Nao" |
| `CONFIABILIDADE_UNIDADE` | ltv | classe de uso |
| demais colunas LTV/retenção | ltv | conforme lista acima |
| `renda_per_capita` | mercado | NaN se hex_id nulo |
| `score_priorizacao` | mercado | NaN se hex_id nulo (READ-ONLY) |
| `score_expansao_hibrido` | mercado | NaN se hex_id nulo |
| `n_concorrentes_mapeados_1km` | mercado | NaN se hex_id nulo |
| `n_concorrentes_mapeados_2km` | mercado | NaN se hex_id nulo |
| `pop_total_setor_2022` | mercado | NaN se hex_id nulo OU setor ausente |
| `densidade_pop_setor_hab_km2` | mercado | NaN se hex_id nulo OU setor ausente |
| `score_setor_2022_calibrado` | mercado | NaN se ausente |
| `score_oportunidade_residual` | mercado | NaN se hex_id nulo |
| `oferta_efetiva_disponivel` | mercado | NaN se hex_id nulo |
| `flag_canibalizacao_ultra_1km` | mercado | NaN se hex_id nulo |
| `prob_cancel_90d_media_absoluta` | derivada | PROB_CANCEL_90D_MEDIA se USAR_PROB_ABSOLUTA=="Sim", NaN caso contrário |

## Critérios de aceite
1. `data/staging/unidade_territorio_retencao.parquet` existe e tem exatamente **88 linhas**.
2. Linhas sem `hex_id` (32 sem_match) têm todas as features territoriais como NaN — não
   são descartadas nem filtradas.
3. Join territorial é LEFT: unidade sem hex → NaN nas features; sem perda de unidades.
4. `prob_cancel_90d_media_absoluta` existe: `PROB_CANCEL_90D_MEDIA` onde
   `USAR_PROB_ABSOLUTA=="Sim"` (59 unidades), NaN caso contrário.
5. `LTV_PROSPECTIVO_12M_MEDIANO` presente no output no grão por unidade (sem re-agregação).
6. Nenhum artefato M1 oficial alterado: mtime de `brasil_priorizados.parquet`,
   `hexagonos_brasil_oportunidades.parquet`, `brasil_estrutural.parquet` e
   `hexagonos_mercado_mapeado.parquet` inalterado após execução.
7. Suíte full verde: `pytest -n auto -q` — zero falhas, zero collection errors.
8. `ruff check src/motor_expansao/lifetime/join_territorio_retencao.py
   tests/unit/test_join_territorio_retencao.py` — All checks passed.
9. `mypy src/` sem novos erros (regressão).
10. Log/print emite: total de linhas, cobertura de `hex_id` (N com hex / N total),
    breakdown de `CONFIABILIDADE_UNIDADE`.
11. Zero imports de `pipelines.m1`, `dashboard`, `censo_*`, `api` no módulo novo.
12. Testes usam fixtures sintéticas (`tmp_path` + `monkeypatch`); nunca leem parquets reais.

## Criticidade classificada
**Média** — join de dados, camada paralela READ-ONLY sobre o M1; sem gate humano obrigatório
antes do Builder.

## Esteira recomendada
Block Orchestrator → **Planner** → Builder → QA

## Riscos identificados
- **Cobertura parcial (56/88 com hex_id):** 32 unidades sem match geográfico (UNIDADE nula
  nos dados reais do Lifetime). O artefato as preserva com NaN territorial. O BLK-LTV-03
  terá N efetivo ~56 para correlação — declarar como confound.
- **Case da chave de join:** bridge usa `cod_unidade` (lowercase), Lifetime usa `COD_UNIDADE`
  (uppercase). Builder deve normalizar antes do merge (`.str.lower()` ou `.str.upper()`).
- **OOM no parquet grande:** `hexagonos_mercado_mapeado.parquet` tem 1,54 M linhas × 135
  colunas. Usar `columns=[...]` no `read_parquet` e filtrar para os 56 hex_ids antes do merge.
- **7 hexes sem dado censitário:** `pop_total_setor_2022` e `densidade_pop_setor_hab_km2`
  são NaN para 7 dos 56 hexes matched. Manter NaN; não imputar.
- **Confound de maturidade (caveat estrutural do epic):** `unidade_para_motor.parquet` não
  tem data de abertura da unidade. Declarar como confound no docstring; não bloqueia este bloco.
- **Haircut semântico:** a regra "haircut ~20% em volume absoluto" aplica-se a estimativas
  volumétricas de churn (`CHURN_ESPERADO_90D_TOTAL`), não ao LTV mediano por aluno. Este
  bloco carrega os campos brutos; a interpretação de haircut deve ser documentada em docstring
  e confirmada pelo Planner.

## Guardrails ativos
- §5 CLAUDE.md (guardrail permanente): READ-ONLY sobre o M1. `score_priorizacao`,
  `hex_score_estrutural`, pesos e artefatos oficiais INALTERADOS. DEC-001 intacta
  (`renda=0.40`/`pop=0.60`).
- Pacote `src/motor_expansao/lifetime/` é DISJUNTO: NUNCA importar de `pipelines.m1`,
  `dashboard`, `censo_*`, `api`.
- `LTV_PROSPECTIVO_12M_*` só no agregado por unidade (grão já correto no parquet de origem).
- `USAR_PROB_ABSOLUTA` respeitado via coluna derivada `prob_cancel_90d_media_absoluta`.
- Tiering de modelo (Média): Planner=sonnet, Builder=sonnet, QA=opus 4.8 (sempre).

---

## Schemas confirmados (inspeção real do repositório em 2026-07-01)

**`data/staging/unidade_hex.parquet`** (88 × 9):
`cod_unidade`, `unidade`, `uf`, `lat`, `lng`, `hex_id`, `metodo_match`, `match_score`, `fonte_geo`
Breakdown metodo_match: exato=43, sem_match=31, perf_hex=10, fuzzy=4. hex_id notna=56.

**`data/ultra/unidade_para_motor.parquet`** (88 × 50):
USAR_PROB_ABSOLUTA: Sim=59, Nao=29. USAR_RANKING: Sim=75, Nao=13.
CONFIABILIDADE: "Absoluto OK"=59, "Apenas Ranking"=16, "Instavel"=6, "Nao usar"=4, "Inconclusivo"=3.
LTV_PROSPECTIVO_12M_MEDIANO: range 1009–2331, nenhum nulo.

**`data/staging/hexagonos_mercado_mapeado.parquet`** (1.542.531 × 135):
Todas as 12 features territoriais listadas acima CONFIRMADAS presentes.
Para os 56 hexes matched: 0 nulls em renda/score_priorizacao/score_expansao_hibrido/concorrentes;
7 nulls em pop_total_setor_2022/densidade; score_setor_2022_calibrado tem muitos nulls nacionais.
`brasil_priorizados.parquet` NÃO usar — incompleto (19 cols; faltam features de concorrência/densidade).
