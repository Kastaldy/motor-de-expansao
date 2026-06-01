# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-FIX-03 — SP estoura "Out of Memory" no Mapa Territorial (verificar outras UFs grandes).**

Selecionar a UF **SP** no Mapa Territorial derruba a aba do navegador com "Esta página está com
problemas / Código de erro: Out of Memory". É um erro **client-side** (esgotamento do JS heap / WebGL
do navegador ao renderizar ~35k hexágonos H3 no deck.gl/pydeck), **DISTINTO** do `MessageSizeError`
de transporte já curado no BLK-FIX-02.

### Distinção formal vs. BLK-FIX-02 (não confundir — é outro bug)
| | BLK-FIX-02 (concluído) | BLK-FIX-03 (este) |
|---|---|---|
| Erro | `MessageSizeError` | "Out of Memory" (aba do navegador) |
| Camada | **Transporte / server-side** (mensagem WebSocket Tornado > teto) | **Render / client-side** (JS heap + WebGL do navegador) |
| Sintoma | Streamlit recusa a mensagem (~240 MB) | A aba do Chrome trava/morre por falta de memória |
| Causa-raiz curada | LARGURA do payload (map_df inteiro serializado) | (a confirmar) pico de render de ~35k hexes e/ou pico na carga da partição |
| Fix aplicado | `maxMessageSize=500` + `_deck_layer_frame` (só `hex_id/fill_color/line_color/tooltip_*`) | — (objeto deste bloco) |

O fix do BLK-FIX-02 (`_deck_layer_frame`, `components.py:993-1011`) **continua valendo** e já reduz a
largura serializada; mesmo assim SP segue estourando — sinal de que o gargalo restante é a **quantidade
de geometria renderizada** (deck.gl reconstrói cada hexágono H3 em GPU) e/ou o **pico de memória na
carga** da partição inteira antes do cap. Não desfazer o que o BLK-FIX-02 entregou.

## Objetivo
Tornar o Mapa Territorial utilizável para SP — e para qualquer UF grande — sem crash de memória
client-side, sem recalcular ou alterar M1/score/carteira/plano/artefatos oficiais.

## Achado de delimitação (responde ao pedido do usuário: SP é caso único?)
**NÃO assumir que é só SP.** Medição feita sobre `data/outputs/hexagonos_dashboard_enriquecido`
(contagem de linhas por partição `uf=XX`, 1.537.950 linhas, 83 colunas no schema):

| Rank | UF | Hexes (linhas) | Sobrevivem ao cap 35k? |
|---|---|---|---|
| 1 | **AM** | 293.431 | satura (35k) |
| 2 | **PA** | 214.388 | satura (35k) |
| 3 | **MT** | 165.230 | satura (35k) |
| 4 | **MG** | 104.078 | satura (35k) |
| 5 | **BA** | 94.117 | satura (35k) |
| 6 | MS | 69.655 | satura (35k) |
| 7 | RS | 61.672 | satura (35k) |
| 8 | GO | 59.953 | satura (35k) |
| 9 | MA | 53.487 | satura (35k) |
| 10 | **SP** | 47.272 | satura (35k) |

Conclusões que o Planner DEVE usar como hipótese de trabalho:
- **SP NÃO é a maior UF em hexes** — é a 10ª (47k). AM/PA/MT/MG/BA são bem maiores.
- No **render**, todas essas UFs grandes batem no **mesmo teto de 35k** (`MAP_POINT_LIMIT`), logo o
  payload de geometria renderizada é ~idêntico entre elas. Se o OOM fosse puramente do render de 35k
  hexes, **AM/PA/MT também cairiam** (provavelmente igual ou pior). → O Planner deve **reproduzir/medir
  AM, PA, MT, MG, BA além de SP** e descobrir se: (i) todas estouram (problema é o cap 35k em si — então
  abaixar o cap efetivo para UFs grandes resolve geral); ou (ii) só SP/algumas estouram (há fator
  específico além do nº de hexes — ex.: distribuição geográfica/zoom, tooltip, ou ambiente da máquina).
- No **load** (`read_enriched_uf_partition`, `data.py:70-85`: `dataset.to_table(...).to_pandas()` lê a
  partição **inteira**, todas as linhas e as 83 colunas, ANTES do cap), o pico de memória escala com o
  nº de hexes da UF → AM (293k) é o pior caso de carga, não SP. Se o OOM tiver componente de carga, ele
  aparece pior nas UFs maiores que SP.

→ A correção deve mirar "**qualquer UF grande**", não um patch só para SP.

## Escopo permitido (não toca M1)
- Reproduzir e **medir** onde está o pico de memória, distinguindo as três etapas: (1) carga da
  partição (`read_enriched_uf_partition`), (2) montagem/serialização do payload do deck
  (`_deck_layer_frame` → `pdk.Layer`/`pdk.Deck`), (3) render client-side no navegador (JS heap/WebGL).
- Cobrir na medição/repro **SP + AM, PA, MT, MG, BA** (as maiores), para validar se o OOM é geral às
  UFs grandes ou específico de SP.
- Avaliar **cap efetivo menor para UFs grandes** (ex.: reduzir `MAP_POINT_LIMIT` no caminho do Mapa
  Territorial, ou um cap dinâmico por nº de hexes da UF), reusando `_downsample_map_index` /
  `MAP_POINT_LIMIT` / `_deck_layer_frame` já existentes.
- Avaliar **simplificar a camada/geometria** (ex.: reduzir `tooltip_line_*` no payload renderizado,
  desligar `auto_highlight`/`stroked` em UF grande, ou agregar visualmente) sem mudar a regra de cor
  canônica (`score_band_to_color` / `RESIDUAL_SCORE_BANDS`).
- Reduzir o pico de **carga** lendo apenas as colunas necessárias da partição (projeção de colunas no
  `read_enriched_uf_partition`), se a medição mostrar que a carga contribui para o pico.
- Garantir **não-regressão** nas demais UFs e no contrato de clique (BLK-FIX-04 é outro bloco; não
  alterar o comportamento de seleção aqui).

## Fora de escopo
- Recalcular/alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de
  domínio ou qualquer artefato oficial do M1.
- Alterar o **universo de hexes** (inclusão/exclusão de hexes é o BLK-FIX-06, Crítica+DEC).
- Corrigir a seleção por clique (BLK-FIX-04) ou o tema claro (BLK-FIX-05) — blocos próprios.
- Trocar o componente de mapa (decisão do Bloco 12 mantém `st.pydeck_chart`).
- Mexer nas faixas de cor de score (`RESIDUAL_SCORE_BANDS` / `score_band_to_color`).
- Refazer o que o BLK-FIX-02 entregou (`maxMessageSize`, `_deck_layer_frame`).

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/constants.py` — `MAP_POINT_LIMIT=35000` (linha 98), `MAP_SOURCE_COLUMNS_M1`
  (linha 184), `MAP_SOURCE_COLUMNS_HYBRID` (linha 216), `MAP_SORT_COLUMNS`/`MAP_SORT_ASCENDING` (178-179).
- `src/motor_expansao/dashboard/components.py` — `_downsample_map_index` (linha 960), `_deck_layer_frame`
  + `_DECK_RENDER_COLUMNS` (986-1011), `build_map_figure` (1014) e o `pdk.Layer`/`pdk.Deck` do H3 (1121,
  1150-1153); builders análogos: híbrido (1317/1387/1417), residual (1468/1505/1535), domínio (1662/1686).
- `src/motor_expansao/dashboard/pages.py` — `render_mapa_pydeck_fragment` (2519) com
  `st.pydeck_chart(deck, on_select="rerun", ..., height=600)` (2541-2543); `render_mapa_territorial` (2565).
- `src/motor_expansao/dashboard/data.py` — `read_enriched_uf_partition` (70-85, lê partição inteira),
  `_read_parquet_subset` (28-40), `list_partitioned_ufs` (53-67).
- `.streamlit/config.toml` — já tem `maxMessageSize = 500` (BLK-FIX-02); SEM bloco `[theme]` (isso é BLK-FIX-05).
- `tasks/completed.md` — seção `BLK-FIX-02` (linhas ~1704-1756): causa-raiz e fix de transporte, para
  manter a distinção e NÃO regredir.

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/components.py` — cap efetivo / simplificação de camada / payload do deck.
- `src/motor_expansao/dashboard/constants.py` — se cap dinâmico/limites de mapa forem a via escolhida.
- `src/motor_expansao/dashboard/data.py` — projeção de colunas na carga da partição (reduzir pico de load).
- `src/motor_expansao/dashboard/pages.py` — parâmetros do render do Mapa Territorial, se necessário.
- `.streamlit/config.toml` — apenas se a medição indicar ajuste de transporte adicional (improvável; é OOM client-side).
- `tests/integration/test_streamlit_app.py` (e/ou testes unitários dos builders) — cobertura de não-regressão.

## Critérios de aceite
- **SP carrega no Mapa Territorial sem crash** de memória (evidência: medição de memória/payload ou repro
  manual documentado).
- **AM, PA, MT, MG, BA** (UFs maiores que SP) também carregam sem crash — confirmando que a correção vale
  para "qualquer UF grande", não só SP (responde ao pedido explícito do usuário).
- **Demais UFs não regridem** (mapa continua renderizando; cap/ordenação preservados onde não há motivo
  para mudar).
- **Zero mudança em M1/score/artefatos**: sem alteração em `score_priorizacao`, `hex_score_estrutural`,
  carteira, plano ou artefatos oficiais; sem mudar o universo de hexes.
- **Suíte verde** (`pytest -q`; baseline atual `532 passed, 1 skipped`), com teste(s) novos cobrindo o
  comportamento de cap/payload para UF grande.

## Criticidade classificada
**Alta** — confirmada. UF inteira inutilizável em produção, mas o bloco toca apenas render/transporte do
dashboard; **não** toca `score_priorizacao`, `hex_score_estrutural`, carteira, plano nem artefato oficial
do M1. Se durante o Planner/Builder a correção passar a tocar qualquer artefato/score do M1 (não deve),
**reclassificar como CRÍTICA + DEC** e parar para gate humano.

## Esteira recomendada
Block Orchestrator → **Planner** → Builder → QA (sem gate humano, pois não toca M1).

## Riscos identificados
- **Médio (perf/UX):** abaixar o cap para UFs grandes reduz o nº de hexes exibidos — comunicar via
  `build_map_scope_caption` que o mapa está amostrado (já há infra de "capped"); não pode dar a impressão
  de que hexes sumiram do M1.
- O OOM é **client-side** e depende de RAM/GPU da máquina do usuário — a repro pode variar por ambiente.
  Mitigar medindo payload/contagem de geometria (determinístico) além da repro manual.
- Não introduzir regressão no contrato de clique (BLK-FIX-04 já é frágil) ao mexer nos parâmetros do layer.
- Não confundir com BLK-FIX-02: se reaparecer `MessageSizeError`, é regressão de transporte, não este bloco.

## Guardrails ativos (do CLAUDE.md)
- "Guardrail permanente: visualizações, análise radial e interações de mapa não podem recalcular ou
  alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou
  artefatos oficiais do M1 sem aprovação explícita." (§5)
- "Ao tocar em camadas paralelas, preservar 100% das linhas e colunas oficiais do M1." (§2)
- "Regra visual canônica: faixas de 10 pontos via `RESIDUAL_SCORE_BANDS`; M1 colore por
  `score_priorizacao`..." — não alterar a regra de cor. (§5)
- "Toda mudança relevante entra com teste; nenhum PR deve subir com CI quebrado." (§2)
- Commit SÓ por path; nunca `git add -A`; não arrastar `tasks/backlog.md`/`PRD.md` não relacionados
  (worktree pré-sujo: `M tasks/backlog.md`).
