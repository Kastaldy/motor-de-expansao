# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-PERF-01b — Cache dos builders de mapa (`build_map_figure` / `build_hybrid_map_figure` /
`build_residual_heatmap_figure`, via `build_unified_map_figure`) + `@st.fragment` novo para o painel
multi-hex (`_render_multihex_controls` + `_render_multihex_kpis`) com botão "Atualizar mapa" (D1) +
mover o seletor de modo de cor (`mapa_territorial_color_mode`) e overlays para dentro do fragment do
mapa. Camada de display/interação do dashboard Streamlit. READ-ONLY sobre o M1.

## Objetivo
Eliminar o rebuild+re-serialização do deck (0,7–3,3 s Python-side, payload 21–24 MB) em reruns que não
mudam o recorte de dados nem os filtros — troca de modo de cor e add/remove de hex no cenário multi-hex
passam a custar ≈0 (cache hit) em vez de reconstruir o builder do zero — sem jamais servir dado de
UF/filtro errado por um cache mal invalidado.

## Escopo permitido
- **Cache dos builders de mapa** em `src/motor_expansao/dashboard/components.py`: aplicar
  `@st.cache_data` ou `@st.cache_resource` (decisão TÉCNICA do Planner — ver "Riscos") a
  `build_map_figure` (L1407), `build_hybrid_map_figure` (L1661), `build_residual_heatmap_figure`
  (L1851) e/ou ao dispatcher `build_unified_map_figure` (L3028). A chave de cache deve capturar
  TODOS os parâmetros que afetam o deck: UF(s)/cidade(s) selecionadas, modo de cor, overlays
  habilitados, `search_pin`/`search_hex_id`, e um identificador do `df` de entrada (hash de conteúdo
  ou token de versão leve — REV-04 H2 sugere `sha1(hex_id_bytes)[:8]` como mitigação de custo de
  hashing). `multihex_cenario` **NÃO** entra na chave (a layer de destaque é anexada DEPOIS do deck
  cacheado, já é o padrão hoje em `pages.py:4406`).
- **Novo `@st.fragment`** em `src/motor_expansao/dashboard/pages.py` envolvendo
  `_render_multihex_controls` (L2603) + `_render_multihex_kpis` (L2668) — esboço de referência no
  REV-05 (`data/analysis/diagnostico_selecao_hex.md`, seção "Implementação sugerida"). Mutar
  `session_state["multihex_cenario"]` dentro do fragment não pode disparar rerun da aba nem
  reconstruir o builder do mapa.
- **D1 (já decidido por Felipe, não reabrir):** dentro do novo fragment, um botão explícito
  "Atualizar mapa" (+ caption curto) dispara um `st.rerun()` completo para propagar o destaque
  laranja do hex recém-adicionado/removido ao mapa. Sem clicar no botão, os KPIs do painel atualizam
  na hora mas o destaque no mapa fica com o cenário anterior até o próximo rerun completo (troca de
  aba, busca, clique no mapa, ou o próprio botão).
- **Mover para dentro do fragment do mapa** (`render_mapa_pydeck_fragment`, L4087, ou um fragment
  equivalente que o Planner desenhe): o `st.selectbox` `mapa_territorial_color_mode` (L4318) e os
  toggles de overlay que hoje ficam fora do fragment em `render_mapa_territorial` (L4263) — trocar de
  modo/overlay vira rerun do fragment, não da aba.
- **D2 (já decidido por Felipe, não reabrir):** cache SEM `ttl=` — mesmo padrão dos loaders atuais
  (`load_uf_slice`, `load_data` etc., ver `docs/arquitetura_app_atual.md` §6): vive enquanto o
  processo estiver de pé; parquets são `:ro`, só mudam em deploy (que recria o container e zera o
  cache).
- Testes novos/atualizados em `tests/` cobrindo cache hit/miss, invalidação por parâmetro, e
  não-invalidação por `multihex_cenario` (ver Critérios de aceite).
- Rodar `scripts/perf_baseline_app.py` (harness B3/B4 do BLK-REV-01) ANTES (branch/estado atual) e
  DEPOIS (com cache) — os números vão no PR/handoff do Builder, não em novo arquivo de relatório (o
  ciclo restringe paths a `components.py`/`pages.py`/`tests/`/`context/handoff/` — ver
  `tasks/current_task.md`; se o Planner quiser um artefato de evidência, usar um path já dentro da
  lista, ex. anexar a comparação como texto no handoff, não criar `data/analysis/*.md` novo).
- Ajuste estritamente mínimo em `constants.py` **apenas se** for indispensável para o token/chave de
  cache (ex. uma constante de tamanho de amostra do hash) — não alterar `REQUIRED_COLUMNS`,
  `MAP_SOURCE_COLUMNS_M1/HYBRID`, `MAP_POINT_LIMIT*` nem qualquer contrato de coluna existente. Se o
  Planner concluir que isso é necessário, deve justificar explicitamente por que e por que não cabe
  só em `components.py`/`pages.py` (path fora da lista do ciclo exigiria atualizar
  `tasks/current_task.md` explicitamente).

## Fora de escopo
- **BLK-PERF-01c** (tooltip enxuto, 14→5-6 campos) — bloco separado, NÃO tocar `_prepare_m1_tooltip_fields`,
  `_prepare_hybrid_tooltip_fields`, `_apply_hex_tooltip_fields` além do estritamente necessário para o
  cache funcionar (não remover/reduzir campos de tooltip neste bloco).
- Qualquer mudança em `score_priorizacao`, `hex_score_estrutural`, pesos, `pipelines/m1/`, `config.py`,
  carteira, plano curto prazo, plano de domínio ou qualquer artefato oficial do M1 (§5 CLAUDE.md).
- `MAP_POINT_LIMIT*` (caps de mapa) e `_downsample_map_index` — INTOCADOS (guardrail explícito do
  bloco em `tasks/current_task.md`).
- H1 do REV-04 (paletas client-side / componente React customizado deck.gl) — descartado no
  diagnóstico, não reabrir.
- H3 do REV-04 (colunas de cor pré-computadas no parquet) — descartado, sem ganho real.
- MVT/tiles vetoriais, debounce de rerun — fora de escopo, fases separadas (REV-03 #4 / tabela de
  opções REV-05).
- BLK-PERF-01c, raio 1,5 km, método de interseção censitária, geração de PDF (relatório pontual/
  municipal) — INTOCADOS.
- Decisão de rumo arquitetural (rebuild vs. refactor, stack alvo — BLK-REV-07/08/12) — fora deste
  bloco; BLK-PERF é quick win independente da trilha web.
- Reabrir D1/D2 — já decididos por Felipe em 2026-07-10, registrados no bloco do backlog.

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/components.py` — `build_map_figure` (L1407),
  `build_hybrid_map_figure` (L1661), `build_residual_heatmap_figure` (L1851),
  `build_unified_map_figure` (L3028, dispatcher).
- `src/motor_expansao/dashboard/pages.py` — `render_mapa_pydeck_fragment` (L4087),
  `render_mapa_territorial` (L4263), `st.selectbox("mapa_territorial_color_mode", ...)` (L4318),
  `_render_multihex_controls` (L2603), `_render_multihex_kpis` (L2668), anexação da layer de destaque
  multi-hex `_build_multihex_selection_layer` (L4406), releitura de `multihex_ids` (L4467).
- `src/motor_expansao/dashboard/constants.py` — contrato de colunas (`REQUIRED_COLUMNS`,
  `MAP_SOURCE_COLUMNS_M1/HYBRID`), `MAP_POINT_LIMIT*` (confirmar que ficam intocados).
- `data/analysis/diagnostico_troca_cor.md` (REV-04) — causa-raiz da troca de cor, tabela de opções
  H1-H4, recomendação H2 (cache) + H4 (fragment).
- `data/analysis/diagnostico_selecao_hex.md` (REV-05) — causa-raiz do add/remove hex, esboço de
  implementação do fragment multi-hex, ressalvas H3 sobre picklabilidade do `pdk.Deck` e
  `cache_data` vs `cache_resource`.
- `docs/arquitetura_app_atual.md` — §2 (modelo de rerun do Streamlit), §6 (tabela cacheado vs.
  recomputado — confirma que os 3 builders hoje NÃO são cacheados), §7 (fragilidades: caps de mapa,
  dependências opcionais de rede).
- `scripts/perf_baseline_app.py` — harness B3/B4 usado para medir antes/depois.
- `data/analysis/perf_baseline_app_2026.md` — baseline de referência (BLK-REV-01) para comparação.
- `tasks/backlog.md` — bloco `BLK-PERF-01b` (linhas ~1150–1189) e cabeçalho do épico `BLK-PERF`
  (linhas ~1124–1141).
- `tasks/current_task.md` — restrição de paths do ciclo, guardrails, esteira já resolvida.
- Testes existentes de mapa/fragment em `tests/` (localizar via grep por `build_map_figure`,
  `build_hybrid_map_figure`, `build_unified_map_figure`, `render_mapa_territorial`,
  `mapa_territorial_color_mode`, `multihex_cenario` — provavelmente
  `tests/integration/test_streamlit_app.py` e/ou `tests/unit/test_components.py`).

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/components.py`
- `src/motor_expansao/dashboard/pages.py`
- `tests/` (novos/atualizados do ciclo)
- `context/handoff/` (snapshots)

(Lista idêntica à de `tasks/current_task.md` — "Paths do ciclo (commit por path)". Qualquer
necessidade de tocar outro path exige atualizar `tasks/current_task.md` explicitamente antes do
Builder, não silenciosamente.)

## Critérios de aceite
- Harness `scripts/perf_baseline_app.py` B3 (`build_map_figure`) e B4
  (`build_hybrid_map_figure`/`build_residual_heatmap_figure`) rodado ANTES (estado atual, sem cache) e
  DEPOIS (com cache); números registrados no handoff/PR do Builder. Meta: troca de modo de cor em
  cache hit ≈ 0 (vs. 0,7–3,3 s hoje); add/remove hex no cenário não dispara nenhuma chamada aos
  builders (0 rebuild medido/instrumentado).
- Teste de integração explícito de invalidação de cache (contagem de chamadas via mock/spy nos
  builders, não só tempo):
  - Trocar UF → cache MISS (rebuild).
  - Trocar cidade/município → cache MISS.
  - Trocar modo de cor (`mapa_territorial_color_mode`) → MISS na primeira vez nesse modo/recorte;
    HIT ao voltar a um modo já visto no mesmo recorte.
  - Alternar overlay → cache MISS.
  - Nova busca (`search_pin`/`search_hex_id`) que muda o recorte/parâmetros do builder → cache MISS.
  - Adicionar/remover hex em `multihex_cenario` → cache HIT (builder **não** é chamado de novo).
- Teste explícito de que o mapa NUNCA exibe dado de UF/filtro diferente do selecionado: montar dois
  recortes distintos (ex. UF A e UF B), forçar sequência A → B → A e validar que os `hex_id`
  presentes no deck retornado em cada etapa pertencem exclusivamente ao recorte correto daquele
  momento (sem vazamento de cache entre recortes).
- D1 implementado e testado: botão "Atualizar mapa" dentro do fragment multi-hex dispara rerun
  completo (destaque laranja atualizado no deck); sem clicar, KPIs atualizam mas o destaque no mapa
  permanece com o cenário anterior; caption explicando o comportamento presente.
- D2 verificado: nenhum decorator de cache usa `ttl=` (grep no diff deve confirmar ausência).
- Decisão técnica `@st.cache_data` vs. `@st.cache_resource` (com chave manual) registrada no plano
  com justificativa — inclui checagem/teste de que `pdk.Deck` é de fato picklável se `cache_data` for
  escolhido, ou, se `cache_resource`, tratamento explícito do risco de cache compartilhado entre
  sessões concorrentes com recortes diferentes (ver Riscos).
- Suíte pytest completa verde (full suite, sem bypass, sem skip novo não justificado); ruff e mypy
  limpos.
- `git diff` vazio em `src/motor_expansao/pipelines/m1/`, `src/motor_expansao/config.py` e em
  qualquer artefato oficial do M1; `MAP_POINT_LIMIT*` e `_downsample_map_index` sem alteração de
  valor/lógica.
- Validação visual humana (cache + fragment + destaque multi-hex + botão "Atualizar mapa") registrada
  como pendência explícita PÓS-QA — não bloqueia o gate automático do QA, mas deve constar no
  handoff final como item aberto até Felipe validar visualmente.

## Criticidade classificada
Alta — muda o comportamento interativo do coração do dashboard (o mapa); READ-ONLY sobre o M1 (não é
Crítica porque não toca score/pesos/artefatos oficiais — ver Interpretação operacional §2 CLAUDE.md:
"ALTERAÇÃO de fórmula/pesos/artefato M1 → Crítica"; este bloco é display/interação pura).

## Esteira recomendada
Block Orchestrator → Planner → Builder → QA — **sem pausa para gate humano de decisão de produto**: D1
("Atualizar mapa") e D2 (cache sem TTL) já foram decididos por Felipe em 2026-07-10 e estão registrados
no bloco do backlog e neste handoff; não reabrir. A validação visual humana (cache + fragment +
destaque) acontece PÓS-QA, fora da esteira automatizada — não é um gate bloqueante do pipeline
BO→Planner→Builder→QA, mas deve ficar registrada como pendência aberta no handoff final do QA. A única
decisão que resta ao Planner é TÉCNICA (não de produto): `@st.cache_data` vs. `@st.cache_resource` com
chave manual — deve ser resolvida e justificada no plano, não deixada em aberto para o Builder decidir
ad hoc.

## Riscos identificados
- **Risco central do bloco — cache servir dado de UF/filtro errado.** Se a chave de cache não
  capturar TODOS os parâmetros que afetam o deck (UF, cidade, modo, overlays, search_pin/hex_id, e um
  identificador fiel do `df` de entrada), um cache hit pode servir o mapa de um recorte anterior como
  se fosse do recorte atual — o pior desfecho possível para este bloco. Mitigado pelo critério de
  aceite de teste explícito de invalidação + teste "nunca exibe UF/filtro errado" (ambos
  obrigatórios, não opcionais).
- **Picklabilidade do `pdk.Deck`.** REV-05 (H3) levanta que `pdk.Deck` pode não ser serializável por
  pickle por padrão, o que quebraria `@st.cache_data` (baseado em pickle). Se `@st.cache_resource` for
  escolhido no lugar, o cache passa a ser **compartilhado entre sessões** do processo Streamlit — isso
  muda a semântica: duas sessões de usuários diferentes olhando UFs diferentes compartilham o mesmo
  cache global, o que É seguro SE a chave de cache for suficientemente específica (inclui todos os
  parâmetros), mas incorre em risco adicional de crescimento de memória sem bound por sessão (ver
  próximo risco). Esta é uma decisão técnica que o Planner deve resolver e justificar, não deixar
  aberta.
- **Memória sem TTL.** D2 fixa "sem TTL", mas sem limite de entradas (`max_entries`) o cache de
  decks (~10 MB por entrada, REV-04) pode crescer sem bound num processo de uso exploratório
  (usuário trocando muitas UFs/modos/filtros ao longo de uma sessão longa, ou múltiplas sessões
  concorrentes se `cache_resource`). Avaliar se cabe um `max_entries` razoável sem violar D2 (D2 fala
  de TTL, não de tamanho máximo — não é reabrir a decisão de produto, é um detalhe técnico de
  implementação).
- **Dois `@st.fragment` na mesma aba.** `render_mapa_pydeck_fragment` (existente, captura clique) +
  o novo fragment do painel multi-hex coexistem em `render_mapa_territorial`. REV-05 nota
  explicitamente que a interação exata de reruns entre fragments aninhados/paralelos na mesma aba
  **não foi testada**. Risco de dessincronia: o deck cacheado (fora dos fragments, construído em
  `render_mapa_territorial`) pode não refletir o estado mais recente de `multihex_cenario` até o
  próximo rerun completo — isso é o comportamento ESPERADO por D1, mas o Planner deve garantir que a
  UI não sugira o contrário (destaque desatualizado deve ser visualmente óbvio, não silencioso).
- **Mover o seletor de cor para dentro do fragment pode quebrar leitores externos.** Verificar se
  algo fora do fragment (expanders de Análise Pontual, Relatório Pontual Censitário, Relatório
  Municipal) lê `session_state["mapa_territorial_color_mode"]` ou depende do modo de cor atual — se
  sim, o valor ainda está em `session_state` (fragments não isolam session_state), mas a ORDEM de
  execução pode mudar; validar que nada quebra por causa disso.
- **Falso ganho em sessão nova.** Cache elimina o rebuild do builder, mas o primeiro `st.pydeck_chart`
  de uma sessão nova (ou de um recorte nunca visto) ainda paga o custo total (rebuild + to_json);
  isso é esperado e não deve ser confundido com "cache não funcionando" na validação B3/B4 — medir
  cache MISS (primeiro render) separadamente de cache HIT (reruns subsequentes).

## Guardrails ativos
- §5 CLAUDE.md — READ-ONLY M1 permanente: "visualizações, análise radial e interações de mapa não
  podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto
  prazo, plano domínio ou artefatos oficiais do M1 sem aprovação explícita." Este bloco é 100%
  display/interação — nenhuma dessas grandezas é tocada.
- `tasks/current_task.md` — guardrails do ciclo: "caps `MAP_POINT_LIMIT*` e `_downsample_map_index`
  INTOCADOS"; "Display/interação only; mapa nunca pode exibir dado de UF/filtro errado (teste
  explícito de invalidação)."
- §2 CLAUDE.md — "Toda mudança relevante entra com teste; nenhum PR deve subir com CI quebrado."
- Interpretação de criticidade (§1/§2 CLAUDE.md, 2026-05-30): ALTERAÇÃO de fórmula/pesos/artefato M1
  → Crítica; este bloco não altera nenhum desses, permanece Alta.
- D1/D2 já resolvidos por Felipe (2026-07-10) — não reabrir (ver `tasks/backlog.md` bloco
  BLK-PERF-01b).
