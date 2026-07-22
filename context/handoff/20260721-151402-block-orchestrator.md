# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (Alta → gate humano OBRIGATÓRIO em S1 + régua de cor do residual + registro da reversão do BLK-CENSO-02 ANTES do Builder)

## Bloco refinado
BLK-RELPON-10 — Slide novo "Socioeconomia + Residual Fitness" antes do slide "Mapas de calor" do
Relatório Pontual Censitário (Streamlit + PDF, template recente e clássico).

## Objetivo
Inserir, antes do slide "Mapas de calor" (grid 2x2 de 4 choropleths censitários), um slide novo com
dois mapas lado a lado: "Socioeconomia — raio 1,5 km" (`score_setor_2022_calibrado`, por setor
censitário IBGE) e "Residual Fitness — raio ~5 km" (`oferta_efetiva_disponivel`, por hexágono H3
res-7), cada um com o raio rotulado no próprio mapa para não serem lidos como a mesma escala.

## Escopo permitido
- Camada nova de render em `censo_map.py`: dois mapas lado a lado reaproveitando o motor de
  `_render_camada` (basemap/pins/escala/legenda) — um para o choropleth de setor censitário
  (`score_setor_2022_calibrado`, já existente, só precisa de outro raio de recorte de exibição) e
  um NOVO para hexágonos H3 res-7 (`oferta_efetiva_disponivel`).
- Helper novo de recorte espacial de hexágonos: a partir do `hex_id` do ponto (via
  `h3.latlng_to_cell`, já usado em `data.py:lookup_hex_by_coord`), expandir com `h3.grid_disk` até
  cobrir ~5 km, filtrar o `df` enriquecido por esses `hex_id`s e desenhar os polígonos
  (`h3.cell_to_boundary`) — único precedente de render de hexágono H3 no repo é
  `relatorio_municipal._hex_boundary_mercator` (linhas 758-762), que usa uma projeção mercator
  manual sem `pyproj`; `censo_map.py` hoje usa `pyproj`/`_local_metric_crs`/`_transformer` — o
  Planner decide qual caminho de projeção reusar/unificar.
- Régua de cor absoluta em ALUNOS para `oferta_efetiva_disponivel` (constante nova em
  `constants.py`, no padrão de `DENSIDADE_POP_BANDS`/`RENDA_PER_CAPITA_BANDS` — upper bound, label,
  rgba). **Não existe hoje**: `RESIDUAL_SCORE_BANDS` é para score 0-100, não para alunos. É decisão
  de produto nova (S2), não extração de algo já aprovado.
- Slide novo em `censo_report.py` (função irmã do padrão `_mapas_calor_page`/
  `_classico_mapas_calor_page`), inserido ANTES da chamada de `_mapas_calor_page`/
  `_classico_mapas_calor_page` na orquestração (`gerar_pdf_relatorio_pontual_censitario` linhas
  1960-2027 e `gerar_pdf_relatorio_pontual_classico` linhas 1869-1939). A gêmea `_classico_*` é
  OBRIGATÓRIA — o clássico é o default em produção (`pages.py:3524` chama
  `template="classico"`; `api/service.py:341`).
- Atualizar `PDF_SECTION_HEADERS` (`censo_report.py:27-34`) com o novo cabeçalho de seção, na ordem
  correta.
- Revisar/decidir explicitamente o esquema de `_tema_bicolor` (`censo_report.py:313-324`): os
  ordinais `p1..p4` das páginas de conteúdo alternam turquesa/magenta; inserir uma página antes
  desloca todos os ordinais seguintes e INVERTE a cor de Mapas de calor/Concorrentes/Perfil do
  Bairro/Big Numbers. Documentar a decisão (ex.: novo slide vira ordinal 1 e os demais sobem, ou
  esquema diferente) — não é livre-escolha silenciosa do Builder, deve estar no plano.
- Atualizar TODOS os testes que asserem `/Count` e/ou `PDF_SECTION_HEADERS` nos bytes crus do PDF
  (lista verificada nesta rodada, ver "Arquivos que podem ser alterados" — são 6, não 5).
- Housekeeping: corrigir `CLAUDE.md` §4 (linha ~100, dentro do parágrafo "Motor/UI censitario"),
  que hoje diz "em **5 paginas** ... tira 1x3 ... levando o PDF de 7->5 paginas" — texto já
  DESATUALIZADO mesmo ANTES deste bloco (a realidade já é 6 páginas / grid 2x2 desde o BLK-RELPON-07
  + renda_domiciliar, documentado corretamente só no parágrafo seguinte, linha ~102). Corrigir para
  o estado real ANTES (6 páginas / grid 2x2) e DEPOIS deste bloco (7 páginas, com o slide novo).
- Registrar explicitamente, no gate/plano, a reversão da decisão de produto do BLK-CENSO-02
  (Felipe, 2026-06-05: residual fitness entra no Pontual só como NÚMERO nos Big Numbers, nunca como
  choropleth) — decidir se isso vira emenda a uma DEC existente ou nova DEC.

## Fora de escopo
- BLK-RELPON-11 (página de satélite) — bloco separado, mesmo dependendo deste (mesma churn de
  página/`/Count`/`_tema_bicolor`); não adiantar trabalho dele aqui.
- BLK-RELPON-09 (logo quadrada em formato quadrado) — já commitado nesta pilha de branches
  (`affcc4f`, `228fa4a`); não re-tocar `_render_square_logo_tile`/`_paste_logo_pin`.
- Qualquer alteração em `score_priorizacao`, `hex_score_estrutural`, pesos
  (`PESOS_HEX_SCORE_ESTRUTURAL`), `score_setor_2022_calibrado` (só LEITURA), `flag_sam`, carteira,
  plano curto prazo, plano de domínio ou artefatos oficiais do M1.
- Alterar `setor_censitario_intersecao_area_1p5km` ou `RAIO_CENSITARIO_DEFAULT_KM` — o raio de
  1,5 km do MOTOR de análise fica INTOCADO; o raio de ~5 km é só recorte de EXIBIÇÃO do mapa novo
  de residual.
- Alterar `_render_pin_tile`, `build_icon_atlas` ou o mapa interativo pydeck (fora de escopo,
  território do BLK-RELPON-09/mapa executivo).
- Introduzir provedor de tiles/rede novo (reusar o `contextily`/CartoDB Voyager já existente via
  DEC-004/DEC-011; nenhuma chamada de rede nova).
- Abrir PR. A estratégia de entrega (Vinicius, 2026-07-21) é PR ÚNICO ao final dos 3 blocos
  (RELPON-09+10+11); este ciclo termina em commit no branch `ciclo/BLK-RELPON-10`.
- Editar `tasks/backlog.md` ou `tasks/completed.md`.

## Arquivos que devem ser lidos
- `CLAUDE.md` (completo; §1 posicionamento/camadas, §2 acentuação, §4 estado do Relatório Pontual —
  linha ~100 stale e linha ~102 correta, §5 guardrail READ-ONLY M1)
- `tasks/current_task.md`
- `tasks/backlog.md` (bloco header "Relatório Pontual Censitário — satélite + mapas
  socioeconômico/residual + logo quadrada", linhas 103-145; `### BLK-RELPON-10` inteiro, linhas
  188-227; `### BLK-RELPON-09` e `### BLK-RELPON-11` para contexto de dependência)
- `src/motor_expansao/dashboard/censo_report.py` (completo; focos: 1-54 `PDF_SECTION_HEADERS`/
  `MAP_LAYER_TITLES`, 280-497 `_UltraPDF`/`_tema_bicolor`/`_draw_maps_grid`/`_mapas_calor_page`,
  1493-1657 gêmea clássica `_classico_*`, 1869-2027 as duas funções de orquestração de páginas —
  `gerar_pdf_relatorio_pontual_classico` e `gerar_pdf_relatorio_pontual_censitario`)
- `src/motor_expansao/dashboard/censo_map.py` (completo; focos: 418-468 `_decode_intersections`,
  471-518 projeção/zoom, 521-555 `_fetch_basemap`, 557-742 `_render_camada`, 745-757 legend
  entries, 759+ `render_mapas_censitarios_combinados` — **confirmado: módulo NÃO importa `h3` em
  lugar nenhum hoje**; os 4 choropleths atuais são todos de setor censitário IBGE)
- `src/motor_expansao/dashboard/data.py` (`lookup_hex_by_coord`, linhas 1023-1046 — devolve UMA
  linha, não um recorte de vizinhança)
- `src/motor_expansao/dashboard/relatorio_municipal.py` (linhas ~735-830: `_score_faixa_color`,
  `_lonlat_to_mercator`, `_hex_boundary_mercator` [758-762, único precedente de render de hexágono
  H3 no repo], `_focus_bounds_mercator` — usa projeção mercator manual, SEM `pyproj`)
- `src/motor_expansao/dashboard/constants.py` (linhas 328-368: `RESIDUAL_SCORE_BANDS` [score 0-100,
  formato `(label, hex_str)`], `DENSIDADE_POP_BANDS`/`RENDA_PER_CAPITA_BANDS` [formato `(upper,
  label, rgba)`] — nenhuma em escala de ALUNOS, confirma que S2 não tem precedente)
- `src/motor_expansao/dashboard/pages.py` (linhas ~3419-3540: `render_relatorio_pontual_censitario`
  — onde `lookup_hex_by_coord`/`render_mapas_censitarios_combinados` já são chamados com `df`
  completo em escopo, incluindo `oferta_efetiva_disponivel`)
- Testes que asseram `/Count`/`PDF_SECTION_HEADERS` nos bytes crus (achados por grep nesta rodada —
  **são 6 arquivos, não 5**; ver lista completa abaixo em "Arquivos que podem ser alterados")

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/censo_map.py`
- `src/motor_expansao/dashboard/censo_report.py`
- `src/motor_expansao/dashboard/constants.py` (nova régua de cor em alunos)
- `src/motor_expansao/dashboard/pages.py` (se precisar passar dado extra ao slide novo)
- `CLAUDE.md` (SÓ §4, housekeeping da contagem/estrutura de páginas)
- `tests/unit/test_relatorio_pontual_censitario_export.py` (11 asserts de `/Count 6` +
  `PDF_SECTION_HEADERS`, linhas 148-734)
- `tests/unit/test_relatorio_pontual_info_imovel.py` (linhas 75-111: `/Count 6/7/7/7/8`)
- `tests/unit/test_relatorio_pontual_orquestracao.py` (linhas 77-125: `/Count 6/10/7/8`)
- `tests/unit/test_relatorio_pontual_ui_relviab06.py` (linha 67: `/Count 10`)
- `tests/unit/test_relatorio_pontual_viabilidade.py` (linhas 85-150: `/Count 6/7/8/8/10/8`)
- `tests/unit/test_relatorio_pontual_fotos.py` (**achado nesta rodada, NÃO estava na lista do
  backlog/current_task** — linhas 188-217: `/Count 6/7/7/7`. Confirmar no plano que este arquivo
  entra na mesma churn dos outros 5.)
- Testes novos que o Builder decidir criar para a camada/geometria de hex e para a régua de cor
  em alunos.
- `context/handoff.md`, `context/handoff/*`, `tasks/current_task.md`

## Critérios de aceite
- Slide novo aparece ANTES de "Mapas de calor", com 2 mapas lado a lado: "Socioeconomia — raio
  1,5 km" (`score_setor_2022_calibrado`, setor) e "Residual Fitness — raio ~5 km"
  (`oferta_efetiva_disponivel`, hexágono H3 res-7), cada raio rotulado no próprio mapa.
- Ambas as variantes atualizadas (`gerar_pdf_relatorio_pontual_censitario` E
  `gerar_pdf_relatorio_pontual_classico`) — o clássico é o default em produção e não pode regredir.
- `PDF_SECTION_HEADERS`, `/Count` e a ordem de seções corretos em TODOS os 6 arquivos de teste
  identificados (não apenas os 5 do backlog original).
- `_tema_bicolor`/atribuição de ordinal revisada e DOCUMENTADA explicitamente no plano (não uma
  escolha silenciosa do Builder) — decisão sobre inversão de cor em cascata comunicada no gate.
- Zero escrita/recálculo de `score_priorizacao`, `hex_score_estrutural`,
  `score_setor_2022_calibrado`, `flag_sam`, carteira, plano ou artefatos oficiais M1 — só LEITURA.
- `setor_censitario_intersecao_area_1p5km` e `RAIO_CENSITARIO_DEFAULT_KM` intocados (diff zero
  nessas definições).
- `CLAUDE.md` §4 corrigido (6→7 páginas / grid 2x2 + slide novo descrito).
- S1 (score permanece no grid 2x2) e S2 (régua de cor do residual em alunos) resolvidas via gate
  humano ANTES do Builder, com a decisão registrada no handoff do Planner.
- Reversão do BLK-CENSO-02 registrada explicitamente (emenda a DEC existente ou DEC nova, conforme
  desenho do Planner).
- Suíte completa (pytest) verde, sem regressão; ruff/mypy limpos.
- Nenhum PR aberto ao final deste bloco — commit(s) no branch `ciclo/BLK-RELPON-10`.

## Criticidade classificada
Alta

## Esteira recomendada
Block Orchestrator (concluído) → Planner → `[APROVAÇÃO HUMANA — S1 + régua de cor do residual +
registro da reversão do BLK-CENSO-02]` → Builder → QA → `[GATE VISUAL do Vini]`.

## Riscos identificados
- Lista de arquivos de teste do backlog/current_task estava incompleta: `test_relatorio_pontual_
  fotos.py` também asserta `/Count` e não foi citado. Recomendo ao Planner rodar
  `grep -rn "/Count\|PDF_SECTION_HEADERS" tests/` no início do plano, em vez de confiar só nesta
  lista, para não deixar um arquivo de fora.
- Inversão de cor em cascata (`_tema_bicolor`) pode surpreender no gate visual se não for
  antecipada com screenshot antes/depois — o Planner deve decidir e comunicar o esquema de cor
  final antes do Builder rodar.
- `censo_map.py` hoje tem ZERO import de `h3`; introduzi-lo é mudança arquitetural do módulo — deve
  ser lazy (mesmo padrão de `data.py`/`relatorio_municipal.py`), não import de topo incondicional.
- Dado real já medido (Monte Carlo Voronoi): em raio pequeno a maioria dos hexágonos vale 0
  (68,9% em 1,5 km); mesmo em ~5 km, pontos em áreas rurais/de baixa densidade podem gerar um mapa
  de residual pouco informativo — vale considerar fallback textual, como as demais camadas.
- S2 (régua de cor em alunos) não tem NENHUM precedente no repo — é decisão de produto nova, deve
  ser registrada como tal no gate, não tratada como extração óbvia de algo já aprovado.
- BLK-RELPON-11 depende deste bloco para ordem de página/`/Count`/`_tema_bicolor`; qualquer decisão
  de ordinal/tema tomada aqui deve ficar bem documentada no handoff de fechamento para o BO do
  RELPON-11 não precisar redescobrir do zero.
- Projeção geométrica: `censo_map.py` usa `pyproj`/CRS métrico local; o único precedente de render
  de hexágono H3 (`relatorio_municipal.py`) usa mercator manual sem `pyproj`. O Planner deve decidir
  explicitamente qual caminho seguir para não introduzir uma terceira convenção de projeção no
  módulo censitário.

## Guardrails ativos
- §5 (guardrail permanente): "visualizações, análise radial e interações de mapa não podem
  recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo,
  plano de domínio ou artefatos oficiais do M1 sem aprovação explícita."
- §4 (raio do motor): `setor_censitario_intersecao_area_1p5km` (INTOCADO) e
  `RAIO_CENSITARIO_DEFAULT_KM` — o raio de ~5 km deste bloco é recorte de EXIBIÇÃO do mapa de
  residual, não do método de análise.
- §2 (acentuação): texto ao usuário com acentuação correta; identificadores/valores brutos NUNCA
  acentuados; no PDF (`fpdf2`, latin-1 via `_ascii()`), caracteres fora de latin-1
  (travessão/bullet/seta/reticências/aspas curvas/©) viram "?" silenciosamente — usar pontuação
  ASCII nos textos novos do slide.
- DEC-004/DEC-011 (fundo de ruas online): este bloco reusa o basemap já existente
  (`_fetch_basemap`/CartoDB Voyager); nenhuma expansão de provedor ou escopo de rede.
- Item de gate explícito: este bloco REVERTE a decisão de produto do BLK-CENSO-02 (Felipe,
  2026-06-05 — residual fitness só como número nos Big Numbers, nunca como choropleth). Isso deve
  ser registrado no gate humano do Planner, não silenciado.
