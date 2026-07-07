# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-ATR-01 — Densificar a base de concorrentes do Huff (TotalPass/WellHub/Unidades) + re-validar o GO**

Criar um novo módulo `concorrentes_densos.py` em `src/motor_expansao/demanda_revelada/` que ingere os ~93 CSVs locais das três fontes (~32.667 linhas brutas), executa dedup por `(hex_id_res7, rede_normalizada)` entre fontes e contra `concorrentes_mapeados.parquet` (3.296 registros), materializa `data/staging/concorrentes_densos.parquet` e invoca `calibrar_huff_captura()` do `huff_captura.py` existente com o novo conjunto de coordenadas, re-validando o GO do BLK-TP-07 (R²_oof +0,4391, IC95 [+0,4251, +0,4523], β=0,5) usando o **mesmo harness k-fold 5×5 seed=42/IC95** — números antes/depois no relatório `data/analysis/huff_captura_densa.md`.

## Objetivo
Ampliar de ~3.300 para ~32.000+ a base de concorrentes bruta do Huff, medir quanto a cobertura de hexes competitivos (share < 1,0) cresce com a base densa, e confirmar se o GO do BLK-TP-07 se mantém ou melhora fora-de-fold.

## Contexto técnico consolidado

### Fontes de entrada
| Fonte | Arquivos | Linhas brutas | Separador | Colunas-chave |
|---|---|---|---|---|
| TotalPass | `concorrentes/totalpass/csvs/` (27 UF) | ~15.986 | `;` | `slug`, `nome`, `latitude`, `longitude`, `uf` |
| WellHub | `concorrentes/wellhub/csvs/` (27 UF) | ~12.769 | `;` | `slug`, `nome`, `latitude`, `longitude`, `uf` |
| Unidades | `concorrentes/Unidades/` (39 redes) | ~3.912 | `;` | `nome_unidade`, `latitude`, `longitude` |
| **Total bruto** | **93 arquivos** | **~32.667** | — | — |

### Base atual (`concorrentes_mapeados.parquet`)
- 3.296 linhas; colunas: `concorrente_id`, `rede`, `nome_unidade`, `lat`, `lng`, `data_coleta`, `arquivo_origem`, `flag_coord_valida`, `flag_duplicado_rede_coord`, `status_registro`, `hex_id_res7`
- Dominada por Smart Fit (999), Panobianco (455), Bluefit (225), Selfit (218), Pratique (164)
- Fator de expansão esperado: ~10× em linhas brutas antes de dedup

### Motor Huff existente (`huff_captura.py`)
- Função principal: `calibrar_huff_captura(df_join, conc_lat, conc_lng, *, limiar_r2, limiar_rho, beta_grid, dir_validacao, incluir_sensibilidades)` → `HuffCapturaResult`
- `executar(dem_path, conc_path, mkt_path, out_path)` é o orquestrador; lê parquets, escreve relatório MD
- Para re-validar com base densa: basta passar `conc_lat`/`conc_lng` derivados do centroide dos hexes do novo parquet; alvo `membros` (16.575 hexes, `demanda_revelada_h3.parquet`) permanece intocado
- D2 do Huff: coordenadas de concorrente usadas são centroide do hex (`h3.cell_to_latlng`), nunca lat/lng bruto de PII — padrão a replicar

### Padrão de ingestão existente a seguir
- `oferta_academias_menores.py`: lê xlsx → deriva `hex_id_res7` na fronteira → dropa PII imediatamente → agrega por hex. Padrão de derivação de hex a replicar para os CSVs.
- `classificacao_rede_menor.py`: normaliza nome → token matching com 28 redes conhecidas → `rede_menor`; colapsa N<3 → `independente`. O vocabulário de 28 tokens deve ser **reutilizado** para normalizar `rede_normalizada` em TotalPass e WellHub.
- **Diferença chave:** dado de estabelecimento concorrente (nome/endereço/lat-long de academia) é **público** — DEC-012 não se aplica. O nome da rede PODE e DEVE ser usado para dedup.

### Estratégia de dedup (definida pelo BO)
Dedup em dois níveis sequenciais, chave `(hex_id_res7, rede_normalizada)`:

**Nível 1 — Intra-fonte:** dentro de cada CSV (UF para TP/WH, rede para Unidades), eliminar linhas com mesmo `(hex_id_res7, rede_normalizada)`.

**Nível 2 — Inter-fonte + contra base atual:** após consolidar as três fontes, eliminar `(hex_id_res7, rede_normalizada)` já presente em outra fonte ou em `concorrentes_mapeados.parquet`. A entrada sobrevivente representa UMA academia daquela rede naquele hex.

**`rede_normalizada` por fonte:**
- **TotalPass e WellHub:** token-matching sobre `nome` usando o vocabulário dos 28 tokens de `classificacao_rede_menor.py`; fallback `independente`.
- **Unidades:** rede canônica = nome do arquivo sem prefixo e extensão (`unidades_<rede>.csv` → `rede = nome_arquivo[9:-4]`). Mais confiável que token-matching pois a rede já está explícita.
- **base_atual (`concorrentes_mapeados`):** usar coluna `rede` diretamente.

### Colunas mínimas do `concorrentes_densos.parquet`
| Coluna | Tipo | Descrição |
|---|---|---|
| `hex_id_res7` | str | H3 res-7 — chave de join com `demanda_revelada_h3` |
| `lat` | float64 | centroide do hex via `h3.cell_to_latlng(hex_id_res7)` (não coord GPS bruta) |
| `lng` | float64 | idem |
| `rede_normalizada` | str | categoria de rede (token ou nome de arquivo) |
| `fonte` | str | `totalpass` | `wellhub` | `unidades` | `base_atual` |
| `flag_da_base_atual` | bool | True se veio de `concorrentes_mapeados.parquet` |
| `versao_contrato` | str | `concorrentes_densos_v1` |

**Design:** `lat`/`lng` derivados de `h3.cell_to_latlng(hex_id_res7)` — não a coordenada GPS bruta. Isso garante consistência com o `share_hex()` do Huff (D2) e elimina ruído de arredondamento GPS entre fontes.

### Re-validação do GO
- **Alvo:** `membros` em `demanda_revelada_h3.parquet` (16.575 hexes) — INALTERADO
- **Harness:** `calibrar_huff_captura(df_join, conc_lat_densa, conc_lng_densa)` — mesmo k-fold 5×5 seed=42/IC95
- **Baseline de comparação:** R²_oof_log = +0,4391, IC95 [+0,4251, +0,4523], β=0,5 (BLK-TP-07)
- **Métricas extras antes/depois:** `n_hex_share_lt_1` (hexes onde share_huff < 1,0), `pct_hex_competitivo`
- **Relatório:** `data/analysis/huff_captura_densa.md` (gitignored) — mesmo formato de `huff_captura.md`
- **Veredito honesto:** GO se R²_oof > 0,05 AND IC95_inf > 0 AND supera baseline geométrico; NO-GO é resultado válido (DEC-008)

### Cross-check NAO_ABRA/ (READ-ONLY, opcional/qualitativo)
`NAO_ABRA/01_SmartFit.xlsx` e `NAO_ABRA/03_Competidores.xlsx` podem ser usados **somente** para medir overlap/precisão qualitativa (ex: "quantas Smart Fit da base densa coincidem com o Excel?"). **Nunca integrar** ao parquet de produção nem ao Huff. O Planner pode tornar essa etapa opcional via flag `incluir_crosscheck=False` (padrão nos testes).

## Escopo permitido
- Criar `src/motor_expansao/demanda_revelada/concorrentes_densos.py` (ingestão + dedup + materialização + relatório de dedup)
- Criar `tests/unit/test_concorrentes_densos.py` com fixtures sintéticas (sem ler CSVs reais)
- Materializar `data/staging/concorrentes_densos.parquet` (gitignored, camada paralela)
- Re-executar `calibrar_huff_captura()` com a nova base; gravar `data/analysis/huff_captura_densa.md` (gitignored)
- Atualizar `src/motor_expansao/demanda_revelada/__init__.py` para expor o novo módulo

## Fora de escopo
- Alterar `huff_captura.py`, `oferta_academias_menores.py`, `classificacao_rede_menor.py` ou qualquer módulo existente
- Integrar a base densa ao `hexagonos_mercado_mapeado.parquet` ou artefatos de residual/mercado (isso é BLK-TP-09 sob gate humano — DEC-013 §3)
- Alterar `concorrentes_mapeados.parquet` (a base densa é parquet SEPARADO; a base atual fica intacta)
- Qualquer import de `pipelines/m1/`, `dashboard/`, `censo_*`, `api/`, `config.py`
- Integrar WellHub/TotalPass ao residual (epic futura, dedup de capacidade + Huff por tipo)
- Usar `NAO_ABRA/` para produção; cross-check qualitativo apenas
- Alterar pesos, fórmula, carteira, plano ou qualquer artefato M1 oficial

## Arquivos que devem ser lidos
- `/repo/src/motor_expansao/demanda_revelada/huff_captura.py` — interface de `calibrar_huff_captura` e `executar`; padrão D2 (centroide do hex)
- `/repo/src/motor_expansao/demanda_revelada/classificacao_rede_menor.py` — vocabulário de 28 tokens para `rede_normalizada`
- `/repo/src/motor_expansao/demanda_revelada/oferta_academias_menores.py` — padrão de derivação de `hex_id` na fronteira
- `/repo/src/motor_expansao/demanda_revelada/contrato.py` — `H3_RES_CONTRATO`, `COLUNAS_PII_PROIBIDAS`
- `/repo/data/staging/concorrentes_mapeados.parquet` — base atual (colunas, volume, redes presentes)
- `/repo/concorrentes/totalpass/csvs/unidades_totalpass_sp.csv` — amostra de formato TotalPass
- `/repo/concorrentes/wellhub/csvs/unidades_wellhub_sp.csv` — amostra de formato WellHub
- `/repo/concorrentes/Unidades/unidades_smart_fit.csv` — amostra de formato Unidades

## Arquivos que podem ser alterados/criados
- `src/motor_expansao/demanda_revelada/concorrentes_densos.py` — NOVO
- `src/motor_expansao/demanda_revelada/__init__.py` — export do novo módulo
- `tests/unit/test_concorrentes_densos.py` — NOVO
- `data/staging/concorrentes_densos.parquet` — NOVO (gitignored)
- `data/analysis/huff_captura_densa.md` — NOVO (gitignored)
- `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md` — fechamento
- `context/handoff.md`, `context/handoff/` — passagem de handoff entre skills

## Critérios de aceite
1. `concorrentes_densos.parquet` materializado com as colunas mínimas definidas; `versao_contrato = "concorrentes_densos_v1"`.
2. Dedup documentado no relatório: total bruto por fonte, duplicatas intra-fonte, inter-fonte e contra base atual, total líquido final.
3. `lat`/`lng` no parquet derivados de `h3.cell_to_latlng(hex_id_res7)` — não coordenadas GPS brutas.
4. `calibrar_huff_captura()` re-executado com os novos `conc_lat`/`conc_lng`; relatório `huff_captura_densa.md` com R²_oof/IC95/β antes e depois + cobertura `pct_hex_competitivo` antes e depois.
5. Veredito de GO/NO-GO honesto em `huff_captura_densa.md`; NO-GO é resultado válido (DEC-008).
6. Zero import de `pipelines/m1`, `dashboard`, `censo_*`, `api`, `config.py` no módulo novo.
7. Testes usam fixtures sintéticas — a suíte nunca lê CSVs reais de `concorrentes/`.
8. Suíte completa verde (as 4 falhas pré-existentes de `openlocationcode` são não-regressivas e documentadas se ainda presentes).
9. `import streamlit_app` ok.
10. mtime dos 4 artefatos M1 oficiais inalterado (`brasil_estrutural.parquet`, `brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet`, `hexagonos_brasil_dashboard.parquet`).

## Criticidade classificada
**Alta** — amplia base de modelagem de um sinal de captura; READ-ONLY sobre o M1. Não recalibra `score_priorizacao`/pesos/artefatos. Ingestão de ~32k registros locais (CSV, sem API ao vivo) e re-validação out-of-fold de um GO já estabelecido.

## Esteira recomendada
Block Orchestrator → **Planner** → Builder (opus) → QA (opus 4.8)

## Riscos identificados
1. **Dedup conservador por hex:** dedup por `(hex_id_res7, rede_normalizada)` trata uma academia por célula H3 (~5 km²). Uma rede com múltiplas unidades no mesmo hex resulta em uma entrada. Para o Huff geométrico isso é aceitável (share já considera distância ao centroide do hex, não endereços individuais).
2. **Volume de redes desconhecidas (TP/WH):** ~29k de TotalPass+WellHub incluem redes não mapeadas nos 28 tokens — fallback `independente` absorve. Reportar volume de `independente` no relatório.
3. **Arredondamento GPS nas Unidades:** scraper arredonda coords; ao derivar `hex_id` pode divergir marginalmente. Mitigação: usar a coord fornecida para derivar o hex; aceitável na escala res-7.
4. **Impacto no R²_oof incerto:** mais concorrentes pode dispersar share → reduzir R²_oof ou aumentar cobertura. O resultado é incerto — NO-GO é resultado válido.
5. **Desempenho do Huff com 32k concorrentes:** produto cartesiano haversine 16.575 × 32.667 pode ser lento. O Planner deve prever filtro de raio (ex: `RAIO_FILTRO_KM = 10`) antes de calcular share, análogo ao `n_conc_no_raio_hex()` existente.

## Guardrails ativos
- **§5 CLAUDE.md (READ-ONLY M1):** zero recálculo de `score_priorizacao`/`hex_score_estrutural`/carteira/plano/artefatos; mtime dos 4 oficiais M1 inalterado.
- **DEC-008:** re-validação out-of-fold vs baseline; R² in-sample BANIDO; IC95 seed=42; flag de extrapolação.
- **DEC-009:** `membros` é ALVO OBSERVADO; NUNCA preditor geográfico de magnitude; proibido usar `concorrentes_densos` como preditor de demanda.
- **DEC-012:** aplica-se **só ao dado pessoal** da Demanda Revelada; nome/lat-long de estabelecimento concorrente é dado público — PODE ser usado para dedup por rede.
- **DEC-013 §3:** WellHub/TotalPass são ativos brutos; integração ao residual é epic futura sob gate humano.
- **Isolamento de pacote:** `concorrentes_densos.py` NÃO importa de `pipelines/m1/`, `dashboard/`, `censo_*`, `api/`, `config.py`.
- **Loop-safe:** sem VPS/deploy/segredos; escreve só `data/staging/` e `data/analysis/` (gitignored); ingestão CSV LOCAL.
