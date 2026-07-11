# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-RELPON-05 — Legenda superior por mapa com o valor do dado no setor do ponto (Relatório Pontual Censitário, 1,5 km).

## Objetivo
Em cada mapa alvo do Relatório Pontual Censitário, exibir uma legenda/faixa superior com o valor da variável daquele mapa lido no setor censitário que CONTÉM o ponto pesquisado (não o agregado do raio), formatado por variável, com "n/d" quando ausente.

## Escopo permitido
- `src/motor_expansao/dashboard/censo_point.py` — em `analisar_ponto_censitario_setores`: adicionar o LOOKUP do setor que contém o ponto (`Point(lng, lat)` dentro do polígono do setor, no mesmo CRS métrico local já usado para a interseção) e expor no `result` os valores desse setor específico (ex.: `renda_per_capita_setor_ponto`, `densidade_pop_setor_ponto`, `score_setor_2022_calibrado_ponto`, e o identificador do setor, ex. `cod_setor_ponto`), todos `None`/ausentes quando o ponto não cai em nenhum setor válido. É SÓ LEITURA/derivação adicional a partir de dados já carregados — não altera `setores_intersectados`, agregados do raio (`pop_total_raio`, `renda_per_capita_media_raio`, `score_setor_medio`, `score_setor_max`), nem o método `setor_censitario_intersecao_area_1p5km`/`RAIO_CENSITARIO_DEFAULT_KM`.
- `src/motor_expansao/dashboard/censo_map.py` — em `_render_camada`/`render_mapas_censitarios_combinados`: desenhar a faixa/legenda superior por camada, recebendo o(s) valor(es) já formatado(s) como STRING(s) por parâmetro(s) OPCIONAL(is) novo(s) com default `None` (padrão da emenda 2026-06-12 da DEC-005 — `None` = render idêntico ao atual, sem a faixa). Não mexer em `_draw_legend_camada` (legenda de faixas existente, canto superior-direito) nem no layout do mapa/circulo/pins/basemap/street overlay.
- `src/motor_expansao/dashboard/censo_report.py` — repassar os valores por camada (calculados a partir do novo lookup de `censo_point.py`) até a chamada de `render_mapas_censitarios_combinados`/`_render_camada`/`_mapas_calor_page`/`_classico_mapas_calor_page`, e formatar por variável (moeda para renda, `hab/km2` para densidade, inteiro 0-100 para score). Não alterar contagem/ordem de páginas, grid de Big Numbers, marca d'água ou `set_compression(False)`.
- Tratamento explícito de dado ausente ("n/d") quando o ponto cai fora de qualquer setor da malha ou o setor não tem o valor (ex. `flag_renda_disponivel=False`).
- Testes cobrindo: (a) lookup do setor do ponto em `censo_point.py` (ponto dentro de setor conhecido, ponto fora da malha → "ausente"/None); (b) presença/valor da legenda superior no PNG/PDF gerado.

## Fora de escopo
- Método de interseção `setor_censitario_intersecao_area_1p5km`, `RAIO_CENSITARIO_DEFAULT_KM`, raio 1,5 km.
- Contagem, ordem e estrutura das páginas do PDF (capa, mapas de calor, concorrentes, big numbers, realização/crédito), grid de Big Numbers 4x2, marca d'água anti-PII, `set_compression(False)`, `pdf_version`.
- `score_priorizacao`, `hex_score_estrutural`, pesos (`renda=0.40`/`pop=0.60`), carteira, plano curto prazo, plano de domínio, qualquer artefato oficial do M1.
- Relatório Municipal (`relatorio_municipal.py`) e qualquer UI interativa do dashboard fora do Relatório Pontual.
- Qualquer dependência de rede nova (o basemap de tiles já existente via DEC-004 fica intocado).
- Decidir D1/D2/D3 (ver seção de riscos/gate abaixo) — o Planner deve levá-las ao gate humano, não resolvê-las por conta própria.

## Arquivos que devem ser lidos
- `CLAUDE.md` (§2, §4, §5, DEC-004, DEC-005 emenda 2026-06-12)
- `tasks/backlog.md` (bloco BLK-RELPON-05, linha ~1604)
- `src/motor_expansao/dashboard/censo_point.py` (`analisar_ponto_censitario_setores`, `_decode_geometry`, `_local_metric_crs`, `_transformer`, `_bbox_prefilter`)
- `src/motor_expansao/dashboard/censo_map.py` (`_render_camada`, `render_mapas_censitarios_combinados`, `_draw_legend_camada`, `MAPA_CENSITARIO_METRICAS`, `CAMADAS_CENSITARIAS`)
- `src/motor_expansao/dashboard/censo_report.py` (`_mapas_calor_page`, `_classico_mapas_calor_page`, `_draw_maps_grid`, `_map_grid_cells`, chamadas a `render_mapas_censitarios_combinados`)
- `docs/relatorio_pontual_censitario.md` (contrato vigente do relatório)
- `tests/` — suíte censitária existente (localizar `test_censo_point.py`/`test_censo_map.py`/`test_censo_report.py` equivalentes para seguir o padrão de teste já usado)

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/censo_point.py`
- `src/motor_expansao/dashboard/censo_map.py`
- `src/motor_expansao/dashboard/censo_report.py`
- Testes correspondentes em `tests/` (unit/integration da trilha censitária/relatório pontual)
- `docs/relatorio_pontual_censitario.md` (se o Planner/Builder julgar necessário documentar o novo campo/legenda)

## Critérios de aceite
- Cada mapa alvo do Relatório Pontual (conforme D1 decidido no gate) exibe a legenda/faixa superior com o valor correto da variável no setor que CONTÉM o ponto (não o agregado do raio, não o hex).
- Quando o ponto cai fora de qualquer setor da malha (ou o setor não tem o valor), a legenda mostra "n/d" — sem exceção.
- Formatação por variável aplicada conforme D2 (moeda para renda, `hab/km2` para densidade, score inteiro 0-100).
- `setor_censitario_intersecao_area_1p5km`, `RAIO_CENSITARIO_DEFAULT_KM`, contagem/ordem/estrutura de páginas, grid de Big Numbers, marca d'água anti-PII e `set_compression(False)` permanecem byte-a-byte intocados nos caminhos que NÃO passam os novos parâmetros opcionais (chamada do dashboard sem os novos parâmetros = render idêntico ao atual).
- `score_priorizacao`/pesos/artefatos oficiais do M1: zero alteração (nenhum arquivo de `pipelines/m1` ou artefato oficial tocado).
- Testes novos cobrindo lookup do setor do ponto (dentro/fora da malha) e presença/conteúdo da legenda superior no PNG/PDF; suíte completa (`pytest -q`) verde; `ruff`/`mypy` limpos.
- Revisão visual do PDF aprovada por humano antes do merge (exigência do próprio bloco no backlog).

## Criticidade classificada
Média

## Esteira recomendada
Block Orchestrator → Planner → [confirmação humana — decisões de produto D1/D2/D3, ver Riscos] → Builder → QA (QA sempre Opus).

## Riscos identificados
- **Decisões de produto pendentes (D1/D2/D3), NÃO resolvidas por este handoff — o Planner deve apresentá-las explicitamente no gate humano antes do Builder:**
  - **D1 — Quais mapas recebem a legenda superior:** os 3 choropleths (Densidade/Renda/Score) certamente sim; o mapa "Concorrentes e Ultra" é SÓ-pins (sem choropleth) — ele tem um "valor" análogo no setor do ponto (ex.: nº de concorrentes/Ultra no setor, ou nº de concorrentes no raio) ou fica sem essa legenda?
  - **D2 — Formato/unidade exibido por variável:** casas decimais de renda (ex. `R$ 2.567` vs `R$ 2.567,00`), arredondamento de densidade (`hab/km2` inteiro ou 1 casa), score inteiro vs 1 casa decimal; texto exato do rótulo (ex. `"Renda: R$ 2.567"` vs `"Renda no setor: R$ 2.567"`).
  - **D3 — Confirmar a fonte do valor = setor que contém o ponto** (centroide do ponto dentro do polígono do setor), distinto do agregado ponderado do raio 1,5 km (`*_media_raio`) e distinto de qualquer valor por hex H3 — este bloco assume que "o setor do ponto" é literalmente o polígono IBGE cujo interior contém `(lat,lng)`; se o ponto cair na fronteira entre 2 setores ou fora de qualquer setor da malha, o comportamento (desempate/"n/d") também deve ser confirmado no gate.
- Risco técnico: o ponto pode cair FORA de qualquer setor da malha (área sem cobertura IBGE, ex. água/orla) mesmo estando dentro do raio de 1,5 km onde há setores parcialmente intersectados — o lookup precisa tratar esse caso como "ausente"/"n/d" sem lançar exceção e sem confundir com "sem setores intersectados no raio" (mensagem já existente no mapa).
- Risco de regressão visual: adicionar uma faixa superior nova pode colidir por espaço com o título já desenhado em `_render_camada` (`_draw_text(draw, (28, 22), titulo, ...)`) — o Builder precisa escolher uma posição que não sobreponha título/legenda de faixas/basemap; isso é decisão de implementação (não de produto), mas o Planner deve alertar o Builder.
- Risco de manter o `pins_only=True` (camada Concorrentes) consistente: hoje essa camada pula o choropleth e a legenda de faixas; se D1 incluir essa camada, a legenda superior precisa funcionar mesmo com `sector_records_3857` vazio/irrelevante para essa camada.

## Guardrails ativos
- READ-ONLY sobre o M1: NÃO tocar `score_priorizacao`, `hex_score_estrutural`, pesos (`renda=0.40`/`pop=0.60`), carteira, plano curto prazo, plano de domínio, artefatos oficiais do M1.
- NÃO tocar método de interseção `setor_censitario_intersecao_area_1p5km`, raio 1,5 km, `RAIO_CENSITARIO_DEFAULT_KM`, estrutura/contagem/ordem de páginas do PDF, grid de Big Numbers, marca d'água anti-PII, `set_compression(False)`.
- Extensão de `censo_*` deve seguir o padrão da emenda 2026-06-12 da DEC-005: parâmetros novos OPCIONAIS com default `None` = comportamento idêntico ao dashboard atual (byte-a-byte quando não usados).
- Toda mudança relevante entra com teste (CLAUDE.md §2); nenhum PR sobe com CI quebrado.
- Acentuação correta em todo texto voltado ao usuário (labels da legenda, "n/d", rótulos de variável); NUNCA acentuar identificadores de código/coluna/chave.
- No PDF (fpdf2/Helvetica/latin-1 via `_ascii()`): usar só pontuação ASCII nos textos novos da legenda (sem travessão `—`, bullet `•`, seta `→`, aspas curvas) — caracteres fora de latin-1 viram "?" silenciosamente.
- Um bloco por vez; não expandir escopo; não implementar nada nesta etapa (Block Orchestrator).
