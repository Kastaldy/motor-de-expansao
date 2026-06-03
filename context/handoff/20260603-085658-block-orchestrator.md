# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner — depois pausa OBRIGATÓRIA para [aprovação humana + DEC] antes do Builder (criticidade crítica).

## Bloco refinado
BLK-FIX-06 — Hexágonos do litoral recortados pelo pipeline. A geração da base nacional H3 (`base_h3_brasil.py`) mantém um hexágono apenas quando seu CENTROIDE cai dentro do polígono do Brasil. Hexes costeiros cujo centroide cai na água — mesmo com a maior parte da célula sobre terra povoada (ex.: Praia Grande, litoral do RJ) — são descartados na geração da base, ANTES de qualquer enriquecimento ou score. Resultado visível em produção: faixas litorâneas povoadas sem hexes no mapa.

Causa-raiz confirmada em file:line (bate com a hipótese do backlog):
- `src/motor_expansao/pipelines/m1/base_h3_brasil.py:184-188` — constrói os pontos de centroide via `h3.cell_to_latlng(hex_id)` + `shapely.points(...)`.
- `src/motor_expansao/pipelines/m1/base_h3_brasil.py:189` — `mask = shapely.intersects(brasil_geom, chunk_centroids)`: o filtro é EXCLUSIVAMENTE por centroide. Não há teste de interseção do polígono do hex com o Brasil.
- `src/motor_expansao/pipelines/m1/base_h3_brasil.py:190-194` — descarta (`removidos += 1`) todo hex cujo centroide não intersecta o Brasil.
- `src/motor_expansao/pipelines/m1/base_h3_brasil.py:356-364` — loga os removidos como "hexagonos sem centroide no Brasil ... (centroide em mar/fronteira)".
- Nota importante: o docstring (linha 3) e o comentário (linhas 181-183) afirmam que o critério de centroide foi escolhido para PRESERVAR costeiros vs. um `covers` mais estrito; isso é meia-verdade — ele preserva o hex com centroide em terra que toca o mar na borda, mas continua descartando o hex com centroide na água. É exatamente esse segundo caso (centroide no mar, terra povoada na célula) o gap do litoral. A correção precisa de um critério de INTERSEÇÃO terra×polígono-do-hex, não de centroide.

## Objetivo
Incluir no universo do M1 os hexágonos litorâneos que sobrepõem terra/população real (hoje descartados pelo filtro de centróide em `base_h3_brasil.py`), sem distorcer o M1, mediante DEC e quantificando o impacto ANTES de regenerar qualquer artefato oficial.

## Escopo permitido
- Diagnóstico/anteprojeto pelo Planner (read-only): especificar a troca do critério de centroide por INTERSEÇÃO do polígono do hex com o polígono do Brasil, OU critério híbrido "centroide-ou-interseção com limiar de área de terra" (definir limiar candidato), reusando `_hex_polygon` (já existe em `base_h3_brasil.py:120-121`, hoje sem uso). O Planner propõe o critério; a escolha final (interseção pura vs. híbrido com limiar) faz parte do que vai à DEC.
- OBRIGATÓRIO antes de qualquer regeneração: QUANTIFICAR o impacto — nº de hexes que entram (por UF e total), e o delta em contagens, percentis nacionais (`renda_pct_nacional`, `pop_pct_nacional`, `score_percentil_nacional`) e `score_priorizacao` dos hexes já existentes (já que percentis nacionais se deslocam ao mudar o universo). Esse delta é o insumo central da DEC.
- Repro do bug: validar que Praia Grande e o litoral do RJ voltam a aparecer com o critério revisado.
- SOMENTE APÓS DEC APROVADA: alterar o critério geométrico em `base_h3_brasil.py` (e, se o critério exigir, um parâmetro em `config.py`); regenerar os artefatos oficiais do M1 de forma auditável e reprodutível; manter testes do pipeline verdes (acrescentar teste do novo critério, ex.: caso sintético de hex costeiro com centroide na água mas área de terra > limiar entra).
- Housekeeping de fim de ciclo: `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md`, snapshots em `context/handoff/`, e a nova DEC em `CLAUDE.md §8`.

## Fora de escopo
- Qualquer regeneração de artefato M1 SEM DEC aprovada (proibido o Builder regenerar artefatos antes da DEC).
- Mudar pesos/fórmula do score (`renda=0.40` / `pop=0.60`, `PESOS_HEX_SCORE_ESTRUTURAL`, fórmula de `score_priorizacao`/`hex_score_estrutural`) — DEC-001 vigente e fora deste bloco.
- Alterar parâmetros canônicos do CLAUDE.md §3 (`H3_RESOLUTION=7`, `DIST_MIN_ULTRA_KM`, `RENDA_MIN`, `AREA_*`, `M1_*`) — exceto, eventualmente, ADICIONAR um novo parâmetro de critério geométrico se a DEC aprovar a forma híbrida (não alterar os existentes).
- Resolver qualquer outro BLK ou bug; um bloco por vez.
- Tocar nas camadas paralelas (censitário, híbrido, mercado/residual) ou recalcular score nelas.

## Arquivos que devem ser lidos
- `c:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\CLAUDE.md` (§1 papéis das camadas, §2 regra de criticidade, §3 núcleo M1/score oficial e parâmetros canônicos, §4 artefatos, §8 DEC-001)
- `c:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\src\motor_expansao\pipelines\m1\base_h3_brasil.py` (filtro 184-194; `_hex_polygon` 120-121; log 356-364)
- `c:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\config.py` (parâmetros canônicos / `M1_POP_MINIMA_PROXY`)
- `c:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\docs\m1_outputs_oficiais.md` (lista exata de artefatos oficiais regenerados)
- `c:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\src\motor_expansao\pipelines\m1\hex_enrichment.py` (consome a base; entender propagação de percentis/score ao mudar o universo)
- `c:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\src\motor_expansao\pipelines\m1\fase1_bi_exports.py` (gera artefatos executivos/BI)
- testes do pipeline da base H3 (localizar em `tests/` o que cobre `base_h3_brasil` / `gerar_hexagonos_validos_uf`)

## Arquivos que podem ser alterados (SOMENTE conforme gate da esteira)
- Planner (read-only, sem código): apenas escreve plano + snapshots de handoff.
- Builder (SOMENTE após DEC aprovada):
  - `src/motor_expansao/pipelines/m1/base_h3_brasil.py` (critério geométrico)
  - `config.py` (somente se a DEC aprovar novo parâmetro de critério; não alterar os canônicos existentes)
  - testes do pipeline (novo teste do critério)
  - artefatos oficiais do M1 (regeneração controlada e auditável — APÓS DEC)
  - `CLAUDE.md` §8 (nova DEC), `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md`, `context/handoff*`
- Possível atualização de `docs/m1_outputs_oficiais.md` / relatório `data/reports/base_h3_brasil.md` se contagens mudarem.

## Artefatos oficiais do M1 que seriam REGENERADOS (CRÍTICO + DEC)
Da CLAUDE.md §3 / `docs/m1_outputs_oficiais.md` — mudar o universo de hexes desloca contagens e percentis nacionais, logo TODOS estes são regenerados:
- `data/staging/brasil_estrutural.parquet`
- `data/staging/brasil_priorizados.parquet`
- `data/staging/hexagonos_brasil_oportunidades.parquet`
- `data/outputs/hexagonos_brasil_dashboard.parquet`
- `data/outputs/hexagonos_mapa_sample.parquet`
- `data/outputs/top_oportunidades_resumo.csv`
- `data/outputs/resumo_por_uf.csv`
- (derivado, não oficial, mas a re-materializar) `data/outputs/hexagonos_dashboard_enriquecido/uf=XX/parte-*.parquet`
- (upstream) `data/staging/brasil/uf=XX/hexagonos.parquet` (saída direta de `base_h3_brasil.py`)

## Critérios de aceite
- Critério geométrico revisado cobre o litoral povoado: repro confirma que Praia Grande e litoral do RJ voltam a aparecer (hexes com terra/população real deixam de ser descartados).
- Impacto no M1 QUANTIFICADO (nº de hexes que entram por UF e total; delta de contagens, percentis nacionais e `score_priorizacao`) e APROVADO em DEC ANTES de regenerar artefatos.
- DEC registrada em CLAUDE.md §8 (formato dos DEC existentes: ID, data, criticidade, status/aprovador, decisão, evidência-chave/delta, referências).
- Artefatos oficiais regenerados de forma reprodutível e auditável (mesmo comando/seed; relatório `data/reports/base_h3_brasil.md` atualizado).
- Testes do pipeline verdes, incluindo um teste novo do critério (caso sintético de hex costeiro com centroide em água e área de terra acima do limiar passando a ser mantido; e um caso totalmente em mar continuando descartado).
- Nenhuma mudança em pesos/fórmula/parâmetros canônicos; M1 segue como camada executiva.

## Criticidade classificada
**CRÍTICA** — a correção altera a base de hexes do M1 e regenera artefatos oficiais (`brasil_estrutural`, `brasil_priorizados`, `hexagonos_*`, dashboard/sample/CSVs). Pela CLAUDE.md §2 ("ALTERAÇÃO de ... qualquer artefato M1 → Crítica (aprovação obrigatória + DEC)") e §8 (precedente DEC-001), a classificação CRÍTICA é OBRIGATÓRIA e não opcional. Exige aprovação humana explícita + DEC registrada antes do Builder.

## Esteira recomendada
Block Orchestrator → Planner → **[REVISÃO/APROVAÇÃO HUMANA + DEC]** → Builder → QA (QA sempre Opus 4.8).

## Riscos identificados
- ALTO: mexe na base do M1; mudar o universo de hexes desloca percentis nacionais e, portanto, `score_priorizacao` de hexes JÁ existentes (não só dos novos). Risco de regressão silenciosa no ranking executivo. Mitigação: quantificar o delta ANTES, DEC explícita, validação de não-regressão.
- Sobre-inclusão: interseção pura pode incluir hexes majoritariamente oceânicos (pouca terra). Mitigação: avaliar limiar de área de terra (critério híbrido) e reportar a distribuição de área de terra dos hexes que entram.
- Custo/reprodutibilidade: regenerar a base depende de malhas IBGE (cache em `data/raw/ibge/`); garantir refresh controlado e execução determinística.
- Tamanho de artefatos (~1.6 GB) e re-materialização do enriquecido particionado; janela e espaço.
- Falsa sensação de segurança pelo comentário do código (linhas 181-183) que sugere que costeiros já são preservados — o Builder deve não confiar no comentário e validar com repro real.

## Guardrails ativos (CLAUDE.md)
- §2: "LEITURA/ANÁLISE de score sem escrita em artefato M1 → Alta; ALTERAÇÃO de fórmula, pesos, ou qualquer artefato M1 → Crítica (aprovação obrigatória + DEC)." Este bloco ALTERA artefatos M1 → Crítica + DEC.
- §1: M1 é a camada EXECUTIVA; nenhuma trilha paralela altera o M1 sem aprovação explícita. Preservar 100% das linhas/colunas oficiais do M1 ao tocar camadas paralelas.
- §3: parâmetros canônicos (`H3_RESOLUTION=7` etc.), pesos `renda=0.40`/`pop=0.60` e fórmula de `score_priorizacao` INALTERÁVEIS neste bloco; campos/artefatos mínimos do score oficial preservados.
- §8 DEC-001: pesos/fórmula do M1 mantidos; este bloco NÃO reabre recalibração de pesos — apenas o universo geográfico de hexes, e mesmo assim só com DEC.
- §2 (geral): toda mudança relevante entra com teste; nenhum PR sobe com CI quebrado; staging em Parquet; CSVs do projeto `sep=";"`, `encoding="utf-8-sig"`.
- Guardrail permanente (§5): visualizações/análise/mapa não recalculam score sem aprovação — aqui a regeneração é deliberada e SÓ ocorre sob DEC.
