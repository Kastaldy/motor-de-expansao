# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
**Planner** (criticidade Alta → após o Planner haverá gate de aprovação humana, conduzido pelo orquestrador).

## Bloco refinado
**BLK-FIX-07 — Camada de pins de academias escalável (manter logos; alvo ~40k concorrentes).**
Bug de produção no transporte/render do Mapa Territorial: mesmo após o cap dinâmico de hexes do
BLK-FIX-03 (18k para UFs grandes), SP continua estourando "Out of Memory" client-side, enquanto AM
(293k hexes) e BA (94k hexes) funcionam. O fator NÃO é o nº de hexes (já capado e ~idêntico entre
UFs grandes) — são as **camadas de pins de academias** (IconLayer de concorrentes e de Ultra), que
**não têm cap** e **embutem o logo (data-URI base64) por linha**, além de pré-montarem 15 campos de
tooltip por linha. SP concentra o grosso das academias (1.381 pins vs BA 133 vs AM 68), virando
outlier de payload mesmo com poucos hexes. Escala futura: scrapings devem levar o total a >40 mil
pins — a correção precisa ser dimensionada para ~40k desde já. Este bloco NÃO toca M1/score/artefatos.

### Hipóteses de causa-raiz — CONFIRMADAS no código real
- **Logo data-URI por linha (concorrentes):** `_build_competitor_icon_layer` faz
  `comp["icon_data"] = comp["rede"].astype(str).map(competitor_icon_data)`
  (`src/motor_expansao/dashboard/components.py:709`). O dict retornado contém a data-URI base64 SVG do
  logo (`src/motor_expansao/dashboard/competitors.py:363` → `_ICON_CACHE[rede]`, montado em
  `_png_icon_data`, `competitors.py:190-198`, com `data:image/svg+xml;base64,...`). CONFIRMADO.
- **Logo data-URI por linha (Ultra):** `ultra["icon_data"] = [icon] * len(ultra)`
  (`components.py:262`) replica o mesmo dict de data-URI em todas as linhas. CONFIRMADO.
- **15 campos de tooltip por linha, via `.apply(axis=1)`:** concorrentes montam `tooltip_title` +
  `tooltip_line_1..5` e preenchem `6..14` com `""` (`components.py:711-732`); Ultra monta a análoga
  faixa de 15 campos (`components.py:264-281`). Custo O(N) por linha. CONFIRMADO.
- **Sem cap nas IconLayers:** `_build_competitor_icon_layer` passa `data=comp` (conjunto filtrado
  inteiro) direto para `pdk.Layer("IconLayer", ...)` (`components.py:734-746`); não há truncamento
  análogo a `MAP_POINT_LIMIT`. `_filter_competitors_to_reference` (`components.py:690-692`) só faz
  recorte por bbox da referência, sem cap. O mesmo para Ultra (`components.py:283-295`). CONFIRMADO.
- **Padrão enxuto do BLK-FIX-02 nunca aplicado às IconLayers:** `_deck_layer_frame` /
  `_DECK_RENDER_COLUMNS` (`components.py:997-1018`) projeta o DataFrame para apenas as colunas
  consumidas pelo H3HexagonLayer + tooltip, e é chamado SOMENTE para o `map_df` dos hexes
  (`components.py:1137, 1409, 1532, 1689`) — nunca para os frames das IconLayers. CONFIRMADO (essa é
  exatamente a peça que falta replicar para os pins).

Nenhuma hipótese refutada.

## Objetivo
Tornar a camada de pins de concorrentes/Ultra do Mapa Territorial escalável a ~40k concorrentes
mantendo os logos, sem crash de memória client-side (SP real com 1.381 pins deixa de travar), sem
recalcular ou alterar M1/score/carteira/plano/artefatos oficiais.

## Escopo permitido
- **Atlas de ícones compartilhado** (`iconAtlas` + `iconMapping`): o logo entra **uma vez** no atlas
  e cada linha carrega só o **nome da rede** (chave do mapping), eliminando a repetição do data-URI
  base64 por pin. Mantém os logos preservados.
- **Gate por recorte + clustering server-side:** na visão de **UF inteira** (muitos pins), enviar
  **clusters agregados** (contagem por grid/hex), não todos os pins individuais; expandir para
  **pins individuais com logo** quando o recorte é pequeno (município/filtro). Limita o payload
  independentemente do total de 40k. (Nota técnica: `st.pydeck_chart` **não** round-trippa zoom/pan
  ao servidor → o gate é por **recorte/filtro selecionado**, não por zoom client-side ao vivo.)
- **Payload por linha enxuto nas IconLayers:** aplicar o equivalente do `_deck_layer_frame`/
  `_DECK_RENDER_COLUMNS` às IconLayers — tooltip via **template** sobre 2–3 colunas cruas, em vez dos
  15 campos pré-montados por linha.
- **Cap de segurança duro** por camada de pins (fail-safe com aviso "amostrado" ao usuário), análogo
  ao `MAP_POINT_LIMIT`.
- **Medição determinística:** teste que conta linhas/bytes do payload das IconLayers por UF,
  inclusive com **dataset sintético de ~40k concorrentes**, provando o bound antes de o scraping crescer.

## Fora de escopo
- M1/score/`score_priorizacao`/`hex_score_estrutural`/carteira/plano curto prazo/plano de domínio/
  artefatos oficiais do M1 e universo de hexes (intocáveis).
- Trocar o componente de mapa (Bloco 12 mantém `st.pydeck_chart`).
- **Culling por zoom client-side ao vivo** (exigiria componente React custom — eventual follow-up).
- Refazer o cap de hexes do BLK-FIX-03 (já concluído 2026-06-01; complementar, não substitui).
- Mexer na regra de cor de score (faixas canônicas via `RESIDUAL_SCORE_BANDS`).

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/components.py` (`_build_competitor_icon_layer` ~695,
  `_build_ultra_icon_layer` ~231, tooltips ~711-732 e ~264-281, `_filter_competitors_to_reference`
  ~690, builders `build_*_map_figure` ~1021/1300/1470/1660, padrão `_deck_layer_frame`/
  `_DECK_RENDER_COLUMNS` ~997-1018, uso do cap `MAP_POINT_LIMIT`/`MAP_POINT_LIMIT_LARGE`)
- `src/motor_expansao/dashboard/competitors.py` (`competitor_icon_data` ~363, `_png_icon_data` ~190,
  `_png_to_pin_svg` ~174, `preload_logos` ~203, `_ICON_CACHE`, `ultra_icon_data`)
- `src/motor_expansao/dashboard/constants.py` (`MAP_POINT_LIMIT`=35000 ~98, `MAP_POINT_LIMIT_LARGE`
  =18000 ~103 — referência para o cap de pins / limites de cluster)
- `src/motor_expansao/dashboard/pages.py` (render do Mapa Territorial, aviso de "amostrado" ~2535-2540)
- `tests/integration/test_streamlit_app.py` (padrão de teste do app)
- `docs/streamlit_dashboard_m1.md` (governança/uso do dashboard, se precisar registrar a mudança)

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/components.py`
- `src/motor_expansao/dashboard/competitors.py`
- `src/motor_expansao/dashboard/constants.py`
- `src/motor_expansao/dashboard/pages.py`
- `tests/integration/test_streamlit_app.py` (e novo teste de medição de payload, se necessário)
- `docs/streamlit_dashboard_m1.md` (se necessário documentar)
- `tasks/current_task.md` · `tasks/backlog.md` · `tasks/completed.md`
- `context/handoff.md` · `context/handoff/`

## Critérios de aceite
- Com dataset sintético de **40k concorrentes**, o payload das IconLayers por UF fica **≤ limite
  definido** (medição determinística de linhas/bytes); sem crash.
- **SP real (1.381 pins) carrega sem crash** no Mapa Territorial (repro manual + medição).
- **Logos preservados** (via atlas de ícones) e **tooltips preservados** (via template); demais UFs
  (AM, BA, etc.) não regridem.
- **Zero mudança em M1/score/artefatos**; `pickable`/clique nos pins preservado; suíte verde
  (baseline atual `pytest -q`).

## Faseamento sugerido (DECISÃO é do Planner)
- **Fase A:** atlas de ícones + payload enxuto nas IconLayers + cap de segurança duro → resolve o SP
  imediato e dá o maior ganho de payload.
- **Fase B:** clustering server-side por recorte → entrega o alvo de ~40k pins.
- O Planner decide se entrega em **um único ciclo** ou em **duas fases** separadas.

## Criticidade classificada
**Alta.** Bug de produção (OOM client-side no Mapa Territorial) no transporte/render. Confirmado por
leitura do código que NÃO toca M1/score/`hex_score_estrutural`/carteira/plano/artefatos oficiais — as
IconLayers e o `_deck_layer_frame` são camada visual de apoio. Logo, não é Crítica; é Alta, com gate
de aprovação humana após o Planner.

## Esteira recomendada
Block Orchestrator → **Planner → [aprovação humana] → Builder → QA**.

## Riscos identificados
- **Médio-alto:** refator de render das IconLayers + clustering server-side. Regressão visual possível
  (tamanho/anchor do ícone, tooltip, `pickable`/clique).
- Compatibilidade do `iconAtlas`/`iconMapping` com a versão de pydeck/deck.gl em produção (validar que
  o atlas SVG/PNG é aceito como `iconAtlas` único + mapping por nome).
- Limiar do gate por recorte (UF inteira vs município/filtro) precisa de regra explícita e
  determinística — `st.pydeck_chart` não envia zoom/pan ao servidor.
- O cap "amostrado" pode esconder pins; UX deve avisar claramente sem induzir interpretação de score.
- **Mitigação:** faseamento A→B; medição determinística com sintético 40k antes do scraping crescer;
  preservar `pickable` e tooltips em todos os builders que chamam as IconLayers (linhas 1153-1154,
  1425-1426, 1548-1549, 1705-1706, 2734-2742, 2853-2858 em `components.py`).

## Guardrails ativos
- Visualizações, análise radial e interações de mapa NÃO podem recalcular nem alterar
  `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou
  artefatos oficiais do M1 sem aprovação explícita (CLAUDE.md §5).
- Pins/logos de concorrentes e Ultra são camada visual de apoio; não alteram score, ranking, carteira
  nem artefatos oficiais (CLAUDE.md §2).
- Dashboard funciona offline com Parquets locais; não criar dependência de API ao vivo (CLAUDE.md §2/§4).
- Toda mudança relevante entra com teste; nenhum PR sobe com CI quebrado (CLAUDE.md §2).
- Bloco 12 mantém `st.pydeck_chart` com centroide do hex (não trocar componente de mapa).
