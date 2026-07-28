# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (criticidade Alta exige planejamento + gate visual humano de Vinicius ANTES do Builder; não pular direto para o Builder).

## Bloco refinado
**BLK-RELPON-13 — Correção do painel Socioeconomia do slide-hero: hexágono H3 a 5 km (padrão residual), não setor.**

Hoje o painel **Socioeconomia** do slide-hero "Socioeconomia e Residual Fitness" (`censo_map.py:1445-1453`) desenha `score_setor_2022_calibrado` por **SETOR** a **1,5 km** — exatamente o mesmo insumo/legenda da camada `score` do grid 2x2 (redundante), e é a única metade do hero ainda em setor/1,5 km enquanto a outra (Residual Fitness) já é hexágono H3 a 5 km. A correção faz a Socioeconomia seguir o **padrão do Residual Fitness** — **mesma métrica e paleta de hoje** (`score_setor_2022_calibrado` colorido por `score_band_to_color`), mas desenhada por **hexágono H3 res-7** num disco `h3.grid_disk(k=5)` no raio de exibição `RAIO_RESIDUAL_DISPLAY_KM=5.0` km, **sem pins**, com **fallback textual** quando faltar `hexes_df`, e as **2 imagens da página um pouco menores**. Espelhar na variante **clássica** (dashboard + bot). O que passa a diferenciar do painel `score` do grid é a **escala/geometria** (grid = setor local 1,5 km; hero = hex regional 5 km, igual ao dashboard), não a métrica. **Render puro, READ-ONLY sobre o M1.**

## Objetivo
Redesenhar o painel Socioeconomia do slide-hero como choropleth de `score_setor_2022_calibrado` por hexágono H3 a 5 km (padrão residual, mesma métrica/paleta), sem pins, com fallback textual, reduzindo um pouco as 2 imagens, com a variante clássica espelhada — mantendo `/Count 8` e as demais 7 camadas byte-idênticas.

## Escopo permitido
1. **Generalizar o render hex** — `_render_camada_residual_hex` (`censo_map.py:995-1085`) e `_hex_polygons_3857` (`censo_map.py:905-967`, valor fixo `oferta_efetiva_disponivel` em **L963**) para aceitar `value_col` + `color_fn`/bandas (e título/legenda/rótulo do valor central parametrizados), reusados por residual e pela nova socioeconomia. O helper de valor central `_residual_hex_central` (`censo_map.py:970-992`, lê `oferta_efetiva_disponivel`) e o rótulo `valor_ponto` também entram na parametrização (ou variante score-específica).
2. **Religar a camada `socioeconomia`** (`censo_map.py:1445-1453`) ao render hex: `value_col="score_setor_2022_calibrado"`, `color_fn=score_band_to_color` (a de hoje, já importada em `censo_map.py:36`), título **"Socioeconomia - raio 5 km"** (ASCII), `pins=[]`, `mostrar_legenda_pins=False`, fallback textual sem `hexes_df` (à risca do residual — chave condicional no dict).
3. **Reduzir um pouco as 2 imagens** em `_socioeconomia_residual_page` (`censo_report.py:549-579`) e na variante clássica — via `_draw_maps_grid`/`_classico_draw_maps_grid` (ajuste de `top`/`bottom`/`gap` ou fator de escala em modo `pack=True`; **nota:** em `pack=True`, `_map_grid_cells_packed` **ignora `margin_x`**, então o ajuste é por `top`/`bottom`/`gap`/escala). **Calibrado no gate visual de Vinicius.**
4. **Espelhar na variante clássica** `_classico_socioeconomia_residual_page` (`censo_report.py:1851-1874`) — dashboard e bot Telegram (o clássico é o DEFAULT em produção).
5. **Atualizar os testes** cujo comportamento mudou de propósito (ver "Critérios de aceite") e adicionar os novos.

## Fora de escopo
- Qualquer escrita/recálculo de `score_priorizacao`, `hex_score_estrutural`, scores censitários, `oferta_efetiva_disponivel`, carteira, plano ou artefatos oficiais do M1.
- Tocar o motor censitário: `setor_censitario_intersecao_area_1p5km` e `RAIO_CENSITARIO_DEFAULT_KM=1,5` **INTOCADOS** — o raio 1,5 km segue valendo no motor e no grid 2x2; muda só a EXIBIÇÃO do painel hero.
- Alterar a métrica (**continua `score_setor_2022_calibrado`**) ou a paleta (**continua `score_band_to_color`**).
- Mexer na camada `score` do grid 2x2, ou em qualquer outra camada (densidade/renda/score/renda_domiciliar/concorrentes/entorno/residual) — devem sair **byte-idênticas**.
- Alterar a contagem de páginas do PDF: **`/Count 8` inalterado**; `CAMADAS_CENSITARIAS` mantém as **mesmas 8 chaves** (reusa `socioeconomia`).
- Adicionar dependência de rede ao vivo / provedor novo / DEC nova. Não é necessária DEC (mesma família visual do BLK-RELPON-10, já aprovado).
- Colar corpo em `CLAUDE.md`/`PRD.md`; commitar `context/handoff.md`, `tasks/current_task.md` (housekeeping cuida) ou `PRD.md`.

## Arquivos que devem ser lidos
- `CLAUDE.md` (§2 acentuação/ASCII-no-PNG; §4 descrição do slide-hero BLK-RELPON-10/11; §5 guardrail READ-ONLY M1).
- `docs/relatorio_pontual_censitario.md` (contrato do Relatório Pontual e das camadas).
- `src/motor_expansao/dashboard/censo_map.py` — `_hex_polygons_3857` (905-967), `_residual_hex_central` (970-992), `_render_camada_residual_hex` (995-1085), montagem da camada `socioeconomia`/`score` (1403-1500), `CAMADAS_CENSITARIAS` (104-113), `RAIO_RESIDUAL_DISPLAY_KM`/`_RESIDUAL_GRID_DISK_K` (120-126), `score_band_to_color` import (36).
- `src/motor_expansao/dashboard/censo_report.py` — `_draw_maps_grid` (454-509), `_socioeconomia_residual_page` (549-579), `_classico_draw_maps_grid` (1794-1821), `_classico_socioeconomia_residual_page` (1851-1874).
- `src/motor_expansao/dashboard/constants.py` — `COLOR_MODES["censitario"]` (593-598: `score_setor_2022_calibrado`).
- `tests/unit/test_relatorio_pontual_censitario_mapa.py` — anti-vácuo/pins (768-781), título+raio (815-841), byte-identidade (1141-1187), 8 chaves (810-812).
- `tests/unit/test_relatorio_pontual_censitario_export.py` — `/Count 8` (várias), **`test_slide_hero_offline_safe_sem_camada_residual` (832-843, asserta `"socioeconomia" in mapas` SEM `hexes_df`)**, presença de chaves/normalize (846-859), grid 2x1/1x1 (862+).

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/censo_map.py`
- `src/motor_expansao/dashboard/censo_report.py`
- `tests/unit/test_relatorio_pontual_censitario_mapa.py`
- `tests/unit/test_relatorio_pontual_censitario_export.py`
- `tasks/completed.md` (append no fechamento — só na Skill de fechamento)
- (potencial) `docs/relatorio_pontual_censitario.md` — atualizar a descrição do painel hero (raio/geometria) se o Builder ajustar o contrato.

## Critérios de aceite
- Painel Socioeconomia do hero = `score_setor_2022_calibrado` colorido por `score_band_to_color`, desenhado por **hexágono H3 res-7** (disco `grid_disk(k=5)`) num raio de **5 km**; título "Socioeconomia - raio 5 km" (ASCII); rodapé do PNG "Raio 5,0 km ...".
- **Sem pins** na camada socioeconomia; **fallback textual** quando faltar `hexes_df` (à risca do residual).
- As **2 imagens da página um pouco menores** (fator aprovado no gate visual de Vinicius).
- Variante **clássica** espelhada (mesma geometria/comportamento no template clássico).
- **`/Count 8`** preservado nas duas variantes; `CAMADAS_CENSITARIAS` continua com as **mesmas 8 chaves**; camadas densidade/renda/score/renda_domiciliar/concorrentes/entorno/residual **byte-idênticas** (`test_camadas_existentes_ficam_byte_identicas...` verde).
- **ASCII** em todos os labels do PNG (a fonte não tem glifo acentuado — exceção de RENDER ao §2).
- **READ-ONLY M1 confirmado por mtime** dos artefatos oficiais (nenhum reescrito).
- **Testes atualizados** (comportamento mudou de propósito): as travas anti-vácuo de pins da socioeconomia em `mapa.py:779-781` e `export.py:998-1001` (agora **sem pins**, como o residual); o assert de título/raio em `mapa.py:839` ("Socioeconomia - raio 1,5 km" → "raio 5 km") e o rodapé de raio; **`export.py:832-837` `test_slide_hero_offline_safe_sem_camada_residual`** (hoje asserta `"socioeconomia" in mapas` SEM `hexes_df` — se a chave virar condicional à risca do residual, este assert precisa refletir a nova regra). Novos testes: socioeconomia é **hex, não setor**, sem pins, com fallback textual sem `hexes_df`, reagindo a `score_setor_2022_calibrado`.
- **Suite verde** (`pytest -q`) sem CI quebrado.
- **Gate visual de Vinicius aprovado** antes do merge.

## Criticidade classificada
**Alta.** Mudança visual no PDF do Relatório Pontual (mesma natureza do BLK-RELPON-10), **render puro READ-ONLY sobre o M1**, que exige gate visual humano (Vinicius) antes do merge. Confirmado por inspeção do código: nenhum ponto do escopo escreve em `score_priorizacao`/`hex_score_estrutural`/pesos/artefatos oficiais — a métrica `score_setor_2022_calibrado` é apenas **lida** do `hexes_df` para colorir. Portanto **NÃO** eleva para Crítica. (Se, na implementação, aparecer qualquer escrita nesses campos, elevar para Crítica + DEC e alertar.)

## Esteira recomendada
Block Orchestrator → **Planner** → `[gate humano/visual — Vinicius: tamanho das 2 imagens + aparência final do hex a 5 km]` → **Builder** → **QA**.

## Riscos identificados
- **[ALTO — gap de teste não listado no backlog]** `test_slide_hero_offline_safe_sem_camada_residual` (`export.py:832-843`) hoje asserta **`"socioeconomia" in mapas` SEM `hexes_df`** (via `_sample_result`, que não passa `hexes_df`). Se a chave `socioeconomia` virar **condicional** ao `hexes_df` (à risca do residual, como pede o backlog), este assert quebra e **precisa ser atualizado** — o backlog NÃO o listou. O Planner deve decidir explicitamente: (a) chave condicional (residual-like) + atualizar este teste; ou (b) manter a chave sempre presente com fallback interno. Recomendação: (a), coerente com "à risca do residual".
- **Valor central da legenda** (`valor_ponto`): o residual mostra `_residual_hex_central` (alunos do hex que contém o ponto). Para a socioeconomia hex é preciso decidir o análogo (score do hex central, "n/d" quando ausente) ou omitir — sub-decisão de produto para o gate visual.
- **Redução das imagens em `pack=True`**: `margin_x` é ignorado em `_map_grid_cells_packed`; o encolhimento tem de vir de `top`/`bottom`/`gap` ou de um fator de escala — calibrar no gate, não chutar.
- **Byte-identidade**: religar a camada `socioeconomia` para o caminho hex NÃO pode alterar as outras 7 camadas nem o caminho `score` do grid; verificar `test_camadas_existentes_ficam_byte_identicas...` e re-render das 7 camadas.
- **Densidade de hexes a 5 km**: à distância de 5 km cabem ~91 hexes (k=5); confirmar que a leitura de `score_setor_2022_calibrado` por hex existe no `hexes_df` servido (a coluna é `optional` no contrato hibrido) — sem a coluna, cair no fallback textual em vez de crashar.

## Guardrails ativos
- **READ-ONLY M1 (§5 CLAUDE.md):** visualizações/render não recalculam nem alteram `score_priorizacao`, `hex_score_estrutural`, scores censitários, `oferta_efetiva_disponivel`, carteira, plano ou artefatos oficiais do M1 sem aprovação explícita. Confirmado por mtime dos artefatos no QA.
- **Motor censitário INTOCADO:** `setor_censitario_intersecao_area_1p5km`, `RAIO_CENSITARIO_DEFAULT_KM=1,5`.
- **Acentuação (§2):** texto de usuário com acentuação correta do português; **exceção de RENDER** — os labels do PNG (fonte sem glifo acentuado) e o PDF fora de latin-1 usam ASCII; título "Socioeconomia - raio 5 km" em ASCII.
- **Estrutura do PDF:** `/Count 8` e as 8 chaves de `CAMADAS_CENSITARIAS` inalteradas; demais camadas byte-idênticas.
- **Sem dependência de API ao vivo** no dashboard de produção; sem provedor/DEC novos.
- **Toda mudança relevante entra com teste; nenhum PR sobe com CI quebrado** (§2).
