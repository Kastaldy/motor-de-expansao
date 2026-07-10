# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-PERF-01c — Tooltip enxuto do mapa (14/8 → 7 linhas por hexágono, nos 4 modos M1/Híbrido/Censitário/Residual)

## Objetivo
Reduzir os campos de tooltip renderizados no payload `deck.to_json()` dos 4 modos de mapa (M1, Híbrido,
Censitário, Residual) para o conjunto de 7 linhas já APROVADO por Felipe (D4, 2026-07-10, gate resolvido
upfront — não reabrir): Título (Município/UF) + Faixa M1 + Score do modo ativo + Score censitário +
Habitantes + Renda per capita + Residual Fitness (1 linha), cortando o payload em ≥50%.

## Escopo permitido
- Editar `src/motor_expansao/dashboard/components.py`:
  - `_prepare_m1_tooltip_fields` (~L633) e `_prepare_hybrid_tooltip_fields` (~L711): preparar os campos
    formatados necessários para as 7 linhas aprovadas nos modos que hoje as usam.
  - `_apply_hex_tooltip_fields` (~L549, `mode="m1"` L582-602 e `mode="hybrid"` L551-580): reduzir para 7
    linhas + título (+ sufixo "- Descartado <5k hab" quando aplicável). `mode="hybrid"` é reusado por
    Híbrido, Censitário (`build_hybrid_map_figure`, cor via `color_col`) E Residual
    (`build_residual_heatmap_figure` também chama `_apply_hex_tooltip_fields(mode="hybrid")`, ~L1990) —
    ajustar esse caminho cobre 3 dos 4 modos de uma vez.
  - `_apply_residual_tooltip_fields` (~L493-546): hoje gera `tooltip_residual_1/2/3` (3 partes: Residual
    fitness+Score residual+quartil / SAM fitness+Consumo concorrentes / Consumo Ultra+Share Ultra).
    Consolidar em 1 linha "Residual Fitness" (conteúdo exato a critério do Planner/Builder, mantendo o
    essencial: `oferta_efetiva_disponivel`).
  - Templates HTML `_shared_map_tooltip` (~L1117, hoje 14 linhas) e `_hybrid_compact_tooltip` (~L1157,
    hoje 8 linhas, controlada por `_HYBRID_TOOLTIP_SHOW_DETAIL=False` ~L1154): reduzir/alinhar para 7
    linhas. Decidir explicitamente se M1 passa a reusar `_hybrid_compact_tooltip` renomeado/genérico ou
    se ganha template próprio — documentar a escolha (ver Riscos).
  - Adicionar "Faixa M1" ao tooltip de Híbrido/Censitário/Residual (hoje ausente lá), reusando
    `faixa_label`/`faixa_oportunidade` já calculado em `_prepare_m1_tooltip_fields` — sem duplicar lógica.
  - `pages.py` **só se o Planner justificar necessidade explícita** (nota do `current_task.md`).
- Medir `deck.to_json()` antes/depois (script scratch em `data/analysis/` ou nota no handoff do Builder)
  para pelo menos 1 recorte por modo (M1, Híbrido, Censitário, Residual).
- Atualizar testes existentes de tooltip em `tests/integration/test_streamlit_app.py` que fixam valores/
  índices do layout antigo (ver lista em Riscos) + adicionar testes novos que verificam a AUSÊNCIA dos
  campos cortados e a PRESENÇA exata dos 7 aprovados.
- Acentuação correta (§2 CLAUDE.md) em labels de exibição novas/alteradas.

## Fora de escopo
- Reabrir D4 (o conjunto de 7 campos). Decisão de produto já tomada por Felipe em 2026-07-10.
- Modo Domínio (`build_dominio_map_figure`, ~L2043-2218): já usa tooltip próprio e compacto (7 linhas
  preenchidas de 14), NÃO faz parte dos "4 modos" do Objetivo — não tocar.
- IconLayers de pins: Ultra (`_build_ultra_icon_layer`/`build_ultra_presence_map`, 4 linhas), Concorrentes
  (`_build_competitor_icon_layer`, 5 linhas) e Cluster de concorrentes (~L1027-1032, 3 linhas) — já enxutos,
  fora do escopo (D4 fala de hexágono, não de pin).
- Cache/fragments do BLK-PERF-01b (`build_unified_map_figure_cached`, `MAP_FIGURE_CACHE_MAX_ENTRIES`,
  `_map_frame_token`, `@st.fragment` em `pages.py:4099`) — recém-mergeados, não mexer no mecanismo. Ver
  nota de risco sobre interação com o conteúdo do tooltip.
- Downsample/cap (`_downsample_map_index`, `MAP_POINT_LIMIT*`, `MAP_SOURCE_COLUMNS_M1/HYBRID`) —
  INTOCADOS.
- Opções 1 (baixar cap), 3 (`@st.fragment`, já aplicada), 4 (tiles vetoriais/MVT) e 5 (memoização por hash
  de params) do `diagnostico_render_mapa.md` — fora deste bloco (só a Opção 2, tooltip enxuto).
- Qualquer alteração em `score_priorizacao`, `hex_score_estrutural`, pesos, carteira, plano ou artefatos
  oficiais do M1 (§5 guardrail — dado não muda, só o que é serializado no payload do mapa).
- Deploy: pós-merge NÃO deployar sem autorização explícita de Felipe (guardrail do dia, já em
  `tasks/current_task.md`).

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/components.py` (funções listadas em Escopo permitido, com números de
  linha aproximados acima; ler também `build_map_figure` ~L1474-1654, `build_hybrid_map_figure`
  ~L1728-1918, `build_residual_heatmap_figure` ~L1918-2043, `build_unified_map_figure` ~L3095-3191,
  `_icon_layer_frame`/`_ICON_RENDER_COLUMNS` ~L1441-1471, `_search_hex_payload`/`_build_search_pin_layer`
  ~L1277-1330, `build_unified_map_figure_cached` ~L77-116)
- `data/analysis/diagnostico_render_mapa.md` (REV-03, contexto do payload)
- `tasks/backlog.md` (bloco "### BLK-PERF-01c", ~L1155-1183)
- `tasks/current_task.md` (objetivo, paths do ciclo, guardrails do dia)
- `tests/integration/test_streamlit_app.py` (ver linhas específicas em Riscos)
- `CLAUDE.md` §2 (acentuação) e §5 (guardrail M1/visualização)

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/components.py`
- `tests/integration/test_streamlit_app.py` (asserts atualizados + testes novos)
- `context/handoff.md` e `context/handoff/` (snapshots)
- `tasks/current_task.md`
- `src/motor_expansao/dashboard/pages.py` — **só se o Planner justificar necessidade explícita**

## Critérios de aceite
- Payload `deck.to_json()` medido antes/depois para pelo menos 1 recorte por modo (M1, Híbrido,
  Censitário, Residual); redução ≥50% documentada (meta do bloco).
- Tooltip final tem exatamente os 7 campos aprovados (+ sufixo "- Descartado <5k hab" no título quando
  `show_discarded` aplicável — sufixo é informação do corte de pop, NÃO conta como uma das 7 linhas e
  DEVE ser preservado) nos 4 modos M1/Híbrido/Censitário/Residual.
- Campos cortados confirmadamente ausentes: fonte geográfica, score estrutural, qualidade join, coverage,
  viável, prioridade, rank intraurbano, top intraurbano, elegibilidade, outlier espacial, motivo
  editorial, e as linhas extras de residual (SAM fitness/consumo concorrentes/consumo Ultra/share Ultra
  deixam de ter linha própria).
- Modo Domínio e IconLayers de pins (Ultra/Concorrentes/Cluster) com conteúdo/contagem de linhas
  inalterados em relação ao estado atual.
- Suíte pytest completa verde (full suite via orquestrador, não só subset do Builder).
- ruff + mypy limpos.
- Acentuação correta (§2) nas labels novas/alteradas; identificadores (`tooltip_line_N`, chaves de
  `session_state`, valores de enum) NÃO acentuados.
- `score_priorizacao`/`hex_score_estrutural`/pesos/artefatos oficiais do M1 com mtime inalterado
  (nenhuma escrita nesta trilha).
- Nenhum deploy realizado nesta esteira (aguarda autorização explícita de Felipe).

## Criticidade classificada
Média

## Esteira recomendada
Planner → Builder → QA (sem pausa humana adicional — D4 já resolvido por Felipe em 2026-07-10;
validação visual humana do tooltip nos 4 modos ocorre pós-QA/pré-deploy, fora desta esteira automatizada).

## Riscos identificados
- **Asserts existentes que fixam o layout antigo e VÃO quebrar** (não são ajuste cosmético, são reescrita):
  `tests/integration/test_streamlit_app.py` L1695-1701 (M1: `tooltip_line_3/10/11/12/13/14`), L1737-1739
  (M1), L1798-1809 (Híbrido: `tooltip_line_1..8`), L344 (itera `_shared_map_tooltip()`+
  `_hybrid_compact_tooltip()` — precisa continuar válido com o novo template), L1501-1502 (lista
  `tooltip_line_1..14` usada em teste de `_search_hex_payload`/frame), L614-619 (lista de 5 colunas de
  tooltip usada em teste de icon layer — conferir se é sobre concorrentes/Ultra, não deveria mudar mas
  merece revisão).
- **`_shared_map_tooltip()` é reusado por 3 consumidores**: `build_map_figure` (M1, alvo da mudança),
  `build_ultra_presence_map` (~L1708, ícone Ultra, só usa 4 linhas — inofensivo reduzir template) e
  `build_dominio_map_figure` (~L2212, Domínio, usa exatamente 7 linhas hoje — fora de escopo, não mexer
  no conteúdo). Se o Builder simplesmente encolher `_shared_map_tooltip()` de 14→7 em vez de criar um
  template dedicado ao M1, o comportamento do Domínio coincide por acaso (7=7), mas é acoplamento
  acidental — recomendo decisão explícita (template compartilhado vs. dedicado) documentada no diff.
- **"Faixa M1" não existe hoje na prep Híbrida**: `_prepare_hybrid_tooltip_fields` (~L711) não
  ensura/computa `faixa_oportunidade`/`faixa_label` (isso só existe em `_prepare_m1_tooltip_fields`,
  ~L655-660). Precisa reusar a lógica sem duplicar código nem quebrar quando `faixa_oportunidade` está
  ausente no df híbrido (hoje o híbrido roda sobre o df unificado que TEM a coluna M1, mas confirmar).
- **Colisão de conteúdo no modo Censitário**: "Score do modo ativo" e "Score censitário" (uma das 7
  linhas aprovadas) apontam para a MESMA métrica quando `color_mode == "censitario"`. D4 não endereçou
  esse caso explicitamente — é detalhe técnico de exibição (linha duplicada é aceitável, não reabre D4),
  mas o Builder deve decidir e documentar (ex.: manter as duas linhas mesmo iguais, por consistência
  entre os 4 modos).
- **Interação com o cache do BLK-PERF-01b** (`@st.cache_data` em `build_unified_map_figure_cached`,
  ~L77-116): a chave de cache é `df_token`/`competitors_token`/`ultra_token`/`dominio_token` (hash de
  CONTEÚDO dos DataFrames) + parâmetros explícitos (`color_mode`, UFs, cidades, etc.) — **não inclui**
  hash do código de tooltip como parâmetro. Streamlit invalida `st.cache_data` por mudança de código-fonte
  da função DECORADA (`build_unified_map_figure_cached`), mas essa função não muda de fonte — só as
  funções que ela chama internamente (`build_map_figure`/`_apply_hex_tooltip_fields`, dentro do MESMO
  módulo `components.py`) mudam. Não confirmado se isso é suficiente para invalidar em processo já rodando
  com hot-reload; em produção deploy = restart de container, então o risco é só operacional em dev local.
  Builder/QA não precisam resolver isso via teste automatizado, mas devem estar cientes ao validar
  visualmente pós-mudança (reiniciar o processo local se o tooltip parecer não ter mudado).
- **Locais que preenchem linhas vazias até 14** (não quebram com template menor — deck.gl ignora colunas
  extras — mas ficam cosmeticamente desatualizados): `_search_hex_payload` (~L1278, `range(1,15)`),
  `_build_search_pin_layer` (~L1319, `range(3,15)`), `build_dominio_map_figure` (~L2165, `range(8,15)`).
  Limpeza é opcional, não é critério de aceite bloqueante.

## Guardrails ativos
- §5 CLAUDE.md: "visualizações, análise radial e interações de mapa não podem recalcular ou alterar
  `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou artefatos
  oficiais do M1 sem aprovação explícita." Este bloco só reduz o que é SERIALIZADO no payload do mapa;
  nenhum dado sai do `df` fonte.
- §2 CLAUDE.md: acentuação correta em texto voltado ao usuário (labels do tooltip); NUNCA acentuar
  identificadores (`tooltip_line_N`, `key=`, `session_state`, valores brutos de enum/categoria, nomes de
  coluna).
- Guardrail do dia (`tasks/current_task.md`): pós-merge NÃO deployar sem autorização explícita de Felipe.
- Guardrail do dia (`tasks/current_task.md`): não tocar o cache/fragments do BLK-PERF-01b além do
  necessário (recém-mergeados).
