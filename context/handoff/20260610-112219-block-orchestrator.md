# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-FIX-11 — Tornar funcionais os 3 overlays "mortos" do Mapa Territorial (Alternativa A)

## Objetivo
Fazer os 3 toggles inertes do Mapa Territorial (`hex_pesquisado`, `descartados_5k`, `ancoras_dominio`) realmente ligarem/desligarem suas camadas, coerentes com a legenda, sem regressão em `concorrentes`/`ultra` e READ-ONLY sobre o M1.

---

## Diagnóstico preciso da causa-raiz (verificado no código)

### 1. `hex_pesquisado` (inerte)
- **Onde está o problema:** no dispatcher `build_unified_map_figure` (`components.py` linhas 2953-3010), `search_pin` e `search_hex_id` são passados incondicionalmente a todos os builders (`build_map_figure`, `build_hybrid_map_figure`, `build_residual_heatmap_figure`). O gate `"hex_pesquisado" in enabled_overlays` nunca é consultado.
- **Cascata interna dos builders:** cada builder executa `if search_pin is not None: layers.append(...)` e `if search_hex_id is not None: layers.append(...)` sem checar o overlay. Pontos exatos: `build_map_figure` linhas 1480-1485; `build_hybrid_map_figure` linhas 1740-1745; `build_residual_heatmap_figure` linhas 1883-1888.
- **Fix necessário:** no dispatcher, adicionar gate antes de passar:
  ```python
  _search_pin = search_pin if "hex_pesquisado" in enabled_overlays else None
  _search_hex_id = search_hex_id if "hex_pesquisado" in enabled_overlays else None
  ```
  E propagar `_search_pin`/`_search_hex_id` a todos os builders no lugar de `search_pin`/`search_hex_id`.

### 2. `descartados_5k` (inerte)
- **Onde está o problema:** a função `_apply_pop_cut_colors` (`components.py` linhas 1116-1130) é chamada incondicionalmente dentro de cada builder, sempre que `flag_pop_min_5k` está presente. O overlay `"descartados_5k"` nunca é passado nem consultado por nenhum builder ou pelo dispatcher.
- **Cascata interna dos builders:** `_apply_pop_cut_colors` também é chamada em `_apply_hex_tooltip_fields` (linhas 505-509 e 527-531) para marcar o tooltip "Descartado <5k hab". Ambos os pontos devem ser gateados.
- **`absent_behavior: show_neutral`** no `OVERLAYS` (`constants.py` linha 424) já indicava que a fiação estava prevista e não concluída.
- **Fix necessário:** o dispatcher deve derivar um flag `show_discarded = "descartados_5k" in enabled_overlays` e passá-lo aos builders; cada builder passa esse flag para `_apply_pop_cut_colors` e para `_apply_hex_tooltip_fields`, que só aplicam a coloração/label de descartado quando `show_discarded=True`. Quando `False`, hexes <5k mantêm a cor do score normal (não somem — continuam visíveis pela cor do score).

### 3. `ancoras_dominio` (inerte — camada não existe ainda)
- **Onde está o problema:** o overlay `"ancoras_dominio"` não tem nenhuma camada pydeck correspondente. As únicas ocorrências são: KPI `build_executive_kpis` (`components.py` linha 2344-2360) que conta linhas do `plano_dominio_df`, e contagem radial em `data.py` (`n_ancoras_dominio`, linhas 813/900). Nenhuma camada de mapa é desenhada.
- **Fonte de dados disponível:** `dominio_df` já flui para `render_mapa_territorial` (`pages.py` linha 2689) e é passado ao dispatcher (`pages.py` linhas 2768). O `plano_expansao_dominio.parquet` contém as colunas `lat`, `lng`, `hex_id` (verificado em `gerar_plano_expansao_dominio.py` linhas 44-45), que são exatamente as `required_cols` declaradas em `OVERLAYS["ancoras_dominio"]` (`constants.py` linhas 410-411).
- **No modo "dominio":** `dominio_df` já é passado como `plano` para `build_dominio_map_figure` (linha 2964), que renderiza hexes coloridos por tese. A camada de `ancoras_dominio` seria ADICIONAL (pins/marcadores sobre os hexes de âncora), não substitui o mapa de domínio.
- **Nos demais modos (m1, hibrido, censitario, residual):** não há nenhuma camada de âncoras — a nova camada precisaria ser injetada pelo dispatcher quando `"ancoras_dominio" in enabled_overlays` E `dominio_df` não estiver vazio.
- **Fix necessário:** criar `_build_ancoras_dominio_layer(dominio_df, selected_ufs, selected_cities)` que retorna um `pdk.Layer` (IconLayer ou ScatterplotLayer) com os hexes âncora filtrados; injetá-lo em cada builder via `deck.layers.append(...)` ou dentro do dispatcher após a chamada ao builder, gateado por `"ancoras_dominio" in enabled_overlays`.

---

## Decisões VISUAIS que precisam de revisão humana antes do Builder

As seguintes decisões de produto/visual **não podem ser tomadas autonomamente** e devem ser aprovadas por Felipe no gate humano (Planner → [REVISÃO HUMANA] → Builder):

1. **Cor/estilo dos pins de âncora de domínio:** que tipo de marcador? (IconLayer com sigla "DOM", ScatterplotLayer com cor sólida, ou reutilizar o atlas de pins de `competitors._render_pin_tile` com uma cor neutra). Cor sugerida: amarelo/laranja para distinguir de concorrentes (vermelho) e Ultra (roxo), mas a decisão é de Felipe.
2. **Tamanho/escala dos marcadores de âncora:** raio/pixel_offset do marcador — depende de quantas âncoras há em tela e da densidade visual desejada.
3. **Comportamento quando `descartados_5k` está DESMARCADO:** hexes <5k passam a ser coloridos pelo score (ficam "normais" no mapa) ou ficam transparentes/ocultos? A proposta natural é "colorir pelo score" (remoção do cinza `_DISCARDED_FILL`), mas pode causar confusão visual se o usuário não souber que estão excluídos do ranking.
4. **Legenda:** `_render_unified_legend` atualmente não tem entrada para `hex_pesquisado`, `descartados_5k` (a entrada de "Descartado <5k" já aparece via `render_pop_cut_legend` sempre, sem gate) nem `ancoras_dominio`. Decisão: a legenda de "Descartado <5k" deve sumir quando o overlay está desmarcado? E qual ícone/legenda para âncoras de domínio?
5. **Estado default dos 3 overlays:** `hex_pesquisado` default=True, `descartados_5k` default=True, `ancoras_dominio` default=False (já declarados em `OVERLAYS`). Confirmar se esses defaults são os corretos para produção.

---

## Escopo permitido
- `src/motor_expansao/dashboard/components.py`: gate de `enabled_overlays` no dispatcher `build_unified_map_figure` (para `hex_pesquisado` e `descartados_5k`); nova função `_build_ancoras_dominio_layer`; modificar `_apply_pop_cut_colors` e `_apply_hex_tooltip_fields` para aceitar `show_discarded: bool`.
- `src/motor_expansao/dashboard/pages.py`: `_render_unified_legend` para gatear `render_pop_cut_legend` e adicionar legenda de âncoras; nenhuma alteração na lógica de dados.
- `src/motor_expansao/dashboard/constants.py`: somente se precisar ajustar metadados do `OVERLAYS` (nenhuma mudança de parâmetros de score).
- `tests/integration/test_streamlit_app.py`: testes cobrindo cada overlay ativo/inativo.

## Fora de escopo
- Recalcular/alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano, artefatos oficiais do M1 (§5 guardrail permanente).
- Mudar `MAP_POINT_LIMIT*`, `COMPETITOR_PIN_LIMIT`, `ULTRA_PIN_LIMIT` sem aprovação explícita.
- Tocar `src/motor_expansao/pipelines/`, `scoring.py`, `config.py` (parâmetros de score).
- Alterar o comportamento dos overlays `concorrentes` e `ultra` (já funcionam corretamente).
- Adicionar overlays novos além dos 3 declarados no `OVERLAYS` de `constants.py`.
- Modo "dominio" do mapa (já tem sua própria camada de hexes; não confundir com `ancoras_dominio`).

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/constants.py` (linhas 394-443): registro `OVERLAYS`, `overlay_available`
- `src/motor_expansao/dashboard/components.py`:
  - linhas 490-532: `_apply_hex_tooltip_fields` (coloração de descartados no tooltip)
  - linhas 1107-1130: `_DISCARDED_FILL`, `_apply_pop_cut_colors`
  - linhas 1215-1240: `_build_search_pin_layer` e `_build_search_hex_layer`
  - linhas 1331-1490: `build_map_figure` (uso de search_pin/search_hex_id e _apply_pop_cut_colors)
  - linhas 1585-1750: `build_hybrid_map_figure` (mesmo padrão)
  - linhas 1771-1890: `build_residual_heatmap_figure` (mesmo padrão)
  - linhas 2930-3010: `build_unified_map_figure` (dispatcher)
- `src/motor_expansao/dashboard/pages.py`:
  - linhas 1794-1819: `_render_unified_legend`
  - linhas 2680-2769: `render_mapa_territorial` (fluxo completo do mapa)
- `src/motor_expansao/pipelines/gerar_plano_expansao_dominio.py` (linhas 43-46): confirmar `lat`, `lng`, `hex_id` no output

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/components.py`
- `src/motor_expansao/dashboard/pages.py`
- `src/motor_expansao/dashboard/constants.py` (somente metadados de overlay, se necessário)
- `tests/integration/test_streamlit_app.py`
- `tasks/backlog.md` (marcar BLK-FIX-07 como superseado formalmente + BLK-FIX-11 como concluído)
- `tasks/current_task.md`, `tasks/completed.md`
- `context/handoff.md`, `context/handoff/`

## Critérios de aceite
- Marcar/desmarcar **Hex pesquisado** remove/restaura o pin e o hex destacado do mapa; `search_pin`/`search_hex_id` não são passados aos builders quando overlay inativo.
- Marcar/desmarcar **Descartados <5k hab** alterna a coloração cinza `_DISCARDED_FILL` (e label de tooltip) nos hexes com `flag_pop_min_5k=False`; hexes continuam visíveis quando desmarcado (coloridos pelo score).
- Marcar **Âncoras Domínio** adiciona uma camada de marcadores sobre os hexes de `dominio_df` no mapa; desmarcar remove a camada.
- Overlays `concorrentes` e `ultra` continuam funcionando sem regressão.
- `_render_unified_legend` é coerente com o estado dos overlays ativos.
- Teste cobrindo cada um dos 3 overlays: ligado vs desligado → camada presente/ausente.
- Suíte + ruff + mypy verdes; git scope ZERO em `pipelines/`, `scoring.py`, `config.py`.
- BLK-FIX-07 formalmente registrado como superseado por BLK-FIX-11.

## Criticidade classificada
Média (display/interação; READ-ONLY M1)

## Esteira recomendada
Block Orchestrator → Planner → [REVISÃO HUMANA das decisões visuais] → Builder (Opus — complexidade atípica para Média: nova camada pydeck + fiação de 3 overlays em 3 arquivos) → QA (Opus 4.8, sempre)

## Riscos identificados
- `ancoras_dominio` exige criar uma camada pydeck NOVA a partir do `dominio_df`; o estilo visual (IconLayer vs ScatterplotLayer) precisa ser decidido no gate humano antes do Builder. Se o Builder tiver que adivinhar o estilo, haverá retrabalho.
- `_apply_pop_cut_colors` e `_apply_hex_tooltip_fields` são chamadas em múltiplos builders (3 builders + 2 pontos de tooltip); o Builder deve alterar **todos** os pontos ou centralizar no dispatcher — risco de esquecimento de um dos pontos.
- `build_dominio_map_figure` não recebe `search_pin`/`search_hex_id` (correto — modo domínio tem layout próprio); o gate de `hex_pesquisado` no dispatcher não precisa cobrir esse builder.
- `dominio_df` pode ser `None` ou vazio (arquivo `plano_expansao_dominio.parquet` não existe em todos os ambientes); a camada de âncoras deve ser no-op silencioso nesse caso (alinhado com `absent_behavior: hide_silently` do overlay).
- Legenda atual de `render_pop_cut_legend` aparece em todos os modos m1/hibrido/censitario/residual incondicionalmente; gatear pela presença do overlay sem abrir uma DEC é aceitável (display-only), mas deve ficar explícito no handoff do Builder.

## Guardrails ativos
- §5 CLAUDE.md (guardrail permanente): visualizações, análise radial e interações de mapa **não podem recalcular ou alterar** `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano domínio ou artefatos oficiais do M1 sem aprovação explícita.
- §2 CLAUDE.md: não criar dependência de API ao vivo no dashboard de produção.
- Pins/logos de concorrentes e Ultra são camada visual de apoio; não alteram score, ranking, carteira nem artefatos oficiais.
- Alteração de fórmula, pesos, ou qualquer artefato M1 → Crítica (aprovação obrigatória + DEC). Este bloco é READ-ONLY sobre o M1.
