# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-LTV-02 — Join territorial (pendurar retenção/LTV no hexágono da unidade)**

Join de dados entre a ponte geocodificada (`unidade_hex.parquet`), as features territoriais do Motor
(`hexagonos_mercado_mapeado.parquet`) e as métricas de retenção agregadas do Lifetime
(`unidade_para_motor.parquet`). Produz o dataset analítico por unidade que será consumido pela análise
de correlação do BLK-LTV-03.

## Objetivo
Construir `data/staging/unidade_territorio_retencao.parquet`: uma linha por unidade Ultra com `hex_id`
confirmado, as features territoriais do hexágono correspondente e as métricas de retenção/LTV do
Lifetime, respeitando as regras de `USAR_PROB_ABSOLUTA` e o haircut de ~20% documentado no dicionário.

## Escopo permitido
- Ler `data/staging/unidade_hex.parquet` (88 linhas totais; 56 com `hex_id` não-nulo; 32 sem match).
- Ler `data/ultra/unidade_para_motor.parquet` e juntar pela chave `cod_unidade` (lowercase no bridge) ↔ `COD_UNIDADE` (uppercase no Lifetime) — normalizar antes do merge.
- Ler features territoriais por `hex_id` de `data/staging/hexagonos_mercado_mapeado.parquet` (left join — hexes do bridge ausentes no mercado recebem NaN nas features; não descartar linhas).
- Colunas territoriais a extrair de `hexagonos_mercado_mapeado.parquet` (nomes CONFIRMADOS por inspeção real):
  - `renda_per_capita` ✓
  - `score_priorizacao` ✓
  - `score_expansao_hibrido` ✓
  - `n_concorrentes_mapeados_1km` ✓
  - `n_concorrentes_mapeados_2km` ✓
  - `pop_total_setor_2022` ✓
  - `densidade_pop_setor_hab_km2` ✓ (nome real — NÃO "densidade")
  - `score_setor_2022_calibrado` ✓
  - `score_oportunidade_residual` ✓
  - `oferta_efetiva_disponivel` ✓
  - `flag_canibalizacao_ultra_1km` ✓
- Colunas de retenção/LTV a carregar de `unidade_para_motor.parquet` (nomes CONFIRMADOS):
  - `PROB_CANCEL_90D_MEDIA`, `PROB_CANCEL_90D_P50`
  - `P_CANCEL_12M_MEDIA`, `P_CANCEL_12M_P50`
  - `LTV_PROSPECTIVO_12M_MEDIANO`, `LTV_PROSPECTIVO_12M_MEDIO`, `LTV_PROSPECTIVO_12M_TOTAL`
  - `E_MESES_ATIVOS_12M_MEDIANO`
  - `CONFIABILIDADE_UNIDADE`, `USAR_PROB_ABSOLUTA`, `USAR_RANKING`
  - `N_ALUNOS`, `TICKET_MEDIO_UNIDADE`, `RECEITA_MENSAL_TOTAL`
- Derivar coluna `prob_cancel_90d_media_absoluta`: `PROB_CANCEL_90D_MEDIA` quando `USAR_PROB_ABSOLUTA == "Sim"`, `NaN` caso contrário.
- Emitir log/print com: total de linhas, cobertura de `hex_id` (N com hex / N total), breakdown de `CONFIABILIDADE_UNIDADE`.
- Criar módulo novo em `src/motor_expansao/ltv/join_territorial.py` (pacote disjunto).
- Criar `src/motor_expansao/ltv/__init__.py` se não existir.
- Criar testes em `tests/unit/test_ltv_join_territorial.py` (fixtures sintéticas; sem ler parquets reais).
- Escrever `data/staging/unidade_territorio_retencao.parquet` (entregável canônico do bloco).

## Fora de escopo
- NÃO alterar nenhum arquivo em `src/motor_expansao/pipelines/m1/`.
- NÃO recalcular nem reescrever `score_priorizacao`, `hex_score_estrutural`, nem qualquer artefato oficial do M1 (DEC-001 intacta).
- NÃO implementar análise de correlação (isso é BLK-LTV-03).
- NÃO implementar score M2 nem combinação de eixos (isso é BLK-LTV-04, bloqueado em gate).
- NÃO escrever em `hexagonos_mercado_mapeado.parquet` nem em qualquer artefato oficial — somente leitura.
- NÃO usar `brasil_priorizados.parquet` como fonte de features territoriais (só tem `renda_per_capita` e `score_priorizacao`; faltam as demais features necessárias).
- NÃO ingerir dados de aluno individual (PII); o parquet Lifetime já está agregado por unidade.
- NÃO importar de `src/motor_expansao/dashboard/`, `src/motor_expansao/pipelines/m1/` nem `censo_*` no módulo `ltv/`.
- NÃO avançar para BLK-LTV-03 ou BLK-LTV-04.

## Arquivos que devem ser lidos
- `data/staging/unidade_hex.parquet` — ponte geocodificada (88 × 9; 56 com `hex_id` não-nulo)
- `data/ultra/unidade_para_motor.parquet` — 88 unidades com métricas de retenção/LTV (88 × 50)
- `data/ultra/unidade_para_motor_DICIONARIO.md` — dicionário de colunas e regras de uso (obrigatório)
- `data/staging/hexagonos_mercado_mapeado.parquet` — features territoriais por `hex_id` (1.542.531 × 135; ler só as colunas necessárias via `columns=[...]` para evitar OOM)
- `src/motor_expansao/ltv/` — verificar se o pacote já existe antes de criar

## Arquivos que podem ser alterados / criados
- `src/motor_expansao/ltv/__init__.py` — criar se não existir
- `src/motor_expansao/ltv/join_territorial.py` — módulo novo (código do join)
- `tests/unit/test_ltv_join_territorial.py` — testes unitários com fixtures sintéticas
- `data/staging/unidade_territorio_retencao.parquet` — entregável canônico (novo arquivo)

## Arquivos que NÃO devem ser tocados (read-only ou proibidos)
- `data/staging/hexagonos_mercado_mapeado.parquet` (somente leitura)
- `data/staging/brasil_priorizados.parquet` (somente leitura)
- `data/staging/hexagonos_brasil_oportunidades.parquet` (somente leitura)
- `data/staging/brasil_estrutural.parquet` (somente leitura)
- `data/outputs/` — todos os artefatos oficiais do M1
- `src/motor_expansao/pipelines/m1/` — qualquer arquivo

## Critérios de aceite
1. `data/staging/unidade_territorio_retencao.parquet` existe e tem exatamente 88 linhas (todas as unidades do Lifetime preservadas, incluindo as sem `hex_id`).
2. Linhas sem `hex_id` (32 `sem_match`) têm features territoriais todas NaN — não são descartadas.
3. O join por `hex_id` em `hexagonos_mercado_mapeado.parquet` é LEFT (unidade sem hex → NaN nas features territoriais; sem perda de unidades).
4. Coluna `prob_cancel_90d_media_absoluta` existe: `PROB_CANCEL_90D_MEDIA` quando `USAR_PROB_ABSOLUTA == "Sim"`, `NaN` caso contrário.
5. `LTV_PROSPECTIVO_12M_MEDIANO` está presente como coluna no output (grão por unidade, conforme parquet de origem).
6. Nenhum artefato M1 oficial foi alterado: mtime de `brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet`, `brasil_estrutural.parquet` e `hexagonos_mercado_mapeado.parquet` inalterado após a execução.
7. Testes em `tests/unit/test_ltv_join_territorial.py` passam com `pytest -q`.
8. `ruff check src/motor_expansao/ltv/ tests/unit/test_ltv_join_territorial.py` sem erros.
9. `mypy src/` sem novos erros (regressão).
10. Log/print emite: total de linhas, cobertura de `hex_id` (N com hex / N total), breakdown de `CONFIABILIDADE_UNIDADE`.

## Criticidade classificada
**Média** (join de dados; camada paralela READ-ONLY sobre o M1)

## Esteira recomendada
Block Orchestrator → **Planner** → Builder → QA (sem gate humano intermediário)

## Riscos identificados
- **Cobertura parcial do bridge (56/88 com hex_id):** 32 unidades sem match geográfico. O join não pode silenciá-las — devem entrar com features NaN e o log deve reportar explicitamente. O BLK-LTV-03 usará o subconjunto com `hex_id` para correlação, mas o artefato guarda todas as 88 linhas.
- **Chave de join `cod_unidade` vs `COD_UNIDADE`:** o bridge usa caixa baixa, o Lifetime usa maiúscula. O Builder deve normalizar antes do merge (ex.: `.str.upper()` ou `.str.lower()` em ambos os lados).
- **Tamanho de `hexagonos_mercado_mapeado.parquet` (1,5M linhas × 135 cols):** usar `columns=[...]` no `read_parquet` para carregar só as colunas necessárias; filtrar por `hex_id` no subset (only ~56 hex_ids únicos) antes do merge para evitar OOM.
- **Confound de maturidade (caveat estrutural do epic):** `unidade_para_motor.parquet` não tem data de abertura da unidade. O artefato entregue por este bloco não controla maturidade — declarar como confound no docstring/comentário; não bloqueia este bloco.
- **`LTV_PROSPECTIVO_12M_*` só no agregado por unidade:** o parquet de origem já está no grão correto (1 linha/unidade); manter a semântica sem re-agregar.

## Guardrails ativos
- §5 (CLAUDE.md): READ-ONLY sobre o M1. Nenhuma coluna/artefato M1 alterado. DEC-001 intacta (`renda=0.40`/`pop=0.60`, `score_priorizacao`, `hex_score_estrutural` INALTERADOS).
- O módulo `src/motor_expansao/ltv/` é DISJUNTO — nunca importa de `pipelines/m1/`, `censo_*`, `dashboard/`.
- `LTV_PROSPECTIVO_12M_*` só no agregado por unidade (garantido pelo grão do parquet de origem).
- `USAR_PROB_ABSOLUTA` respeitado via coluna derivada `prob_cancel_90d_media_absoluta`.
- Haircut ~20% em volume absoluto: documentar via comentário/docstring no módulo; a aplicação numérica fica para BLK-LTV-03 (este bloco apenas carrega os campos brutos).
- `N=88` exige bootstrap/IC na análise — responsabilidade de BLK-LTV-03, não deste bloco.

---

## Schemas confirmados (inspeção real do repositório em 2026-07-01)

**`data/staging/unidade_hex.parquet`** (88 × 9):
Colunas: `cod_unidade`, `unidade`, `uf`, `lat`, `lng`, `hex_id`, `metodo_match`, `match_score`, `fonte_geo`
Cobertura: exato=43, perf_hex=10, fuzzy=4 (56 com hex_id); sem_match=32.

**`data/ultra/unidade_para_motor.parquet`** (88 × 50):
Chave: `COD_UNIDADE` (str), `UNIDADE`, `UF`. Todas as 50 colunas presentes; `USAR_PROB_ABSOLUTA` e `USAR_RANKING` são strings ("Sim"/"Não").

**`data/staging/hexagonos_mercado_mapeado.parquet`** (1.542.531 × 135):
Fonte principal das features. Todas as 11 features solicitadas CONFIRMADAS presentes.
`brasil_priorizados.parquet` NÃO usar como fonte — incompleto (só 19 colunas, faltam `score_expansao_hibrido`, concorrentes, pop_setor, densidade).
