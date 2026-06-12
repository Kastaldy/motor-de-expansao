# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner → [REVISÃO HUMANA leve — D1/D2/D3] → Builder → QA

## Bloco refinado
BLK-MAP-01 — Filtro individual de concorrentes nos overlays do Mapa Territorial

## Objetivo
Adicionar um controle de seleção de redes no Mapa Territorial que filtre `competitors_df` antes de `build_unified_map_figure`, fazendo com que pins, clusters, legenda e tooltips reflitam apenas as redes selecionadas, sem tocar em nenhum cálculo do motor.

## Escopo permitido
- `src/motor_expansao/dashboard/pages.py` — novo controle de UI de seleção de redes em `render_mapa_territorial`; aplicar filtro em `competitors_df` ANTES de `build_unified_map_figure` (ponto único de aplicação, em torno de `pages.py:2749`); passar o `competitors_df` filtrado tanto para `_render_unified_legend` (linha 2765) quanto para `build_unified_map_figure` (linha 2774).
- `src/motor_expansao/dashboard/components.py` — `render_competitor_legend` (linha 196) já recebe `competitors_df` e deriva as entradas de `competitors_df["rede"]`; com o DataFrame filtrado passado por `pages.py`, a legenda refletirá automaticamente a seleção. Verificar se há ajuste necessário para o caso de DataFrame vazio (D2).
- `tests/integration/test_streamlit_app.py` e/ou testes de unidade de `components.py` — cobrindo: (a) seleção de uma rede → só ela renderiza; (b) seleção vazia → comportamento conforme D2; (c) "todas" selecionadas → retrocompatibilidade.

## Fora de escopo
- Qualquer recálculo ou alteração de `score_priorizacao`, `hex_score_estrutural`, carteira, plano, residual, SAM, canibalização ou artefatos oficiais do M1 (READ-ONLY absoluto; §5 CLAUDE.md).
- Overlay de Ultra (`ultra_df`), âncoras de domínio (`ancoras_dominio`), overlay `descartados_5k` — intocados (BLK-FIX-11).
- Quebrar otimizações de performance: carga lazy por UF, fonte de mapa enxuta, caps de pontos (`COMPETITOR_PIN_LIMIT=6000`).
- Dependência de API ao vivo.
- Alteração de `COMPETITOR_BRANDS`, `load_competitor_points`, `_build_competitor_icon_layer`, `_build_competitor_cluster_layer` — essas funções recebem o DataFrame já filtrado e não precisam mudar.
- Alteração de `build_unified_map_figure` — o dispatcher já recebe `competitors_df` e delega; o filtro acontece ANTES dele, em `pages.py`.

## Pontos de código onde o filtro deve ser aplicado

| Local | File:line | O que mudar |
|---|---|---|
| **Controle de UI (novo `st.multiselect` de redes)** | `pages.py` ~ linha 2749 (logo após o `st.multiselect` de overlays) | Derivar lista de redes de `competitors_df["rede"].unique()`, ordená-las via `COMPETITOR_BRANDS`, exibir multiselect com default = todas; produzir `selected_redes: list[str]`. |
| **Aplicação do filtro (ponto único)** | `pages.py` ~ linha 2749–2765 (entre o multiselect e `_render_unified_legend`) | `competitors_df_filtered = competitors_df[competitors_df["rede"].isin(selected_redes)]` (ou `None`/vazio se D2 = esconde tudo). Passar `competitors_df_filtered` nas duas chamadas a seguir. |
| **Legenda de concorrentes** | `pages.py:2765` → `_render_unified_legend(..., competitors_df=competitors_df_filtered, ...)` | Já repassa para `render_competitor_legend(competitors_df)` em `components.py:1825`; com o DF filtrado, a legenda automaticamente reflete só as redes selecionadas. Nenhuma mudança em `components.py` esperada, salvo ajuste defensivo para DF vazio (D2). |
| **Builders de mapa** | `pages.py:2774` → `build_unified_map_figure(..., competitors_df=competitors_df_filtered, ...)` | `_comp = competitors_df_filtered if "concorrentes" in enabled_overlays else None` (linha 3031 de `components.py` já trata o `None`; com o DF filtrado passado, pins/clusters/tooltips refletem a seleção sem mudança nos builders). |

**Nota:** o cap `COMPETITOR_PIN_LIMIT` em `_build_competitor_icon_layer` (`components.py:834`) incide sobre o subconjunto filtrado — comportamento correto e sem mudança de código.

## Decisões abertas para o gate humano (leve)

### D1 — Estilo do controle de UI
- **Opção A (recomendada pelo backlog):** `st.multiselect` separado de redes (simples, consistente com o multiselect de overlays existente).
- **Opção B:** checkboxes por rede com logo (mais visual, mais código).
- **Opção C:** integração no multiselect de overlays existente (uma entrada por rede; polui o controle de overlays).
- **Recomendação do backlog:** Opção A.

### D2 — Semântica de seleção vazia
- **Opção A (recomendada pelo backlog):** seleção vazia → esconde todos os concorrentes (passa `None` ou DF vazio para o builder; legenda de concorrentes desaparece).
- **Opção B:** seleção vazia → cai de volta para "todas" (mais tolerante a erros de clique, mas comportamento menos intuitivo).
- **Recomendação do backlog:** Opção A (esconde tudo).

### D3 — Escopo da lista de redes exibida no controle
- **Opção A (recomendada pelo backlog):** todas as redes presentes em `competitors_df` carregado (estável; não muda com o recorte de UF/cidade).
- **Opção B:** apenas as redes presentes no recorte/bbox atual do mapa (mais dinâmica; requer filtragem adicional antes do controle).
- **Recomendação do backlog:** Opção A (estável, sem custo extra).

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/pages.py` (render_mapa_territorial ~ linhas 2743–2780; _render_unified_legend ~ linhas 1795–1829)
- `src/motor_expansao/dashboard/components.py` (render_competitor_legend ~ linha 196; build_unified_map_figure ~ linha 3008; _comp gate ~ linha 3031; _build_competitor_icon_layer ~ linha 818; _build_competitor_cluster_layer ~ linha 878)
- `src/motor_expansao/dashboard/competitors.py` (COMPETITOR_BRANDS ~ linha 83; load_competitor_points ~ linha 323)
- `tests/integration/test_streamlit_app.py`

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/pages.py`
- `src/motor_expansao/dashboard/components.py` (apenas `render_competitor_legend` se ajuste defensivo para DF vazio for necessário; nada de score/builders)
- `tests/integration/test_streamlit_app.py` (e/ou testes de unidade de components)

## Critérios de aceite
- Selecionar uma ou mais redes exibe APENAS os concorrentes dessas redes (pins/clusters/legenda/tooltips coerentes com a seleção).
- "Todas" selecionadas = comportamento atual (retrocompatibilidade byte-a-byte em relação ao fluxo existente).
- Seleção vazia: comportamento conforme D2 aprovado pelo humano.
- Cap `COMPETITOR_PIN_LIMIT` e caption "amostrado" continuam operando sobre o subconjunto filtrado.
- Nenhum score/artefato M1 alterado (READ-ONLY; verificável por ausência de escrita em parquet/CSV oficial).
- `ruff` e `mypy` limpos.
- Suíte pytest verde (sem regressões; novos testes cobrindo os 3 cenários: uma rede, vazia, todas).

## Criticidade classificada
Média

## Esteira recomendada
Block Orchestrator (concluído) → **Planner** → [REVISÃO HUMANA leve — humano escolhe D1/D2/D3] → Builder → QA (sempre Opus 4.8)

## Riscos identificados
- **Controle de UI visível mesmo quando overlay "concorrentes" está desligado:** o multiselect de redes deve ser renderizado condicionalmente (só quando "concorrentes" está em `enabled_overlays`) para evitar confusão de UX.
- **Lista de redes derivada de `competitors_df` pode estar vazia** (dados não carregados): o controle precisa ser suprimido ou exibir mensagem informativa quando `competitors_df` for None/vazio.
- **Ordering da lista de redes:** derivar de `COMPETITOR_BRANDS` para exibição consistente; redes sem entrada em `COMPETITOR_BRANDS` (fallback genérico) devem aparecer no final ou usar o valor bruto da coluna `rede`.
- **Rerun do Streamlit a cada mudança de seleção:** padrão esperado com `st.multiselect`; sem impacto diferente do comportamento atual de outros controles. Nenhum risco de performance além do já existente (carga lazy por UF permanece inalterada; o filtro é só um `.isin()` sobre o DF já em memória).
- **Nenhum risco de recálculo de M1:** o filtro acontece inteiramente em `pages.py` sobre `competitors_df` já carregado; os builders e o motor permanecem READ-ONLY.

## Guardrails ativos
- §5 CLAUDE.md (guardrail permanente): visualizações, análise radial e interações de mapa NÃO podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano domínio ou artefatos oficiais do M1 sem aprovação explícita.
- §2 CLAUDE.md: não criar dependência de API ao vivo no dashboard de produção.
- Performance: preservar carga lazy por UF, fonte de mapa enxuta e caps de pontos (`COMPETITOR_PIN_LIMIT`, `MAP_POINT_LIMIT*`).
- BLK-FIX-11: overlays `ultra`, `ancoras_dominio`, `descartados_5k` intocados.
- Interpretação de criticidade (2026-05-30): LEITURA/ANÁLISE de score sem escrita em artefato M1 → Alta; ALTERAÇÃO de fórmula/pesos/artefato M1 → Crítica. Este bloco é visualização pura → Média.
