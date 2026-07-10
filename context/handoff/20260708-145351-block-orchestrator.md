# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Builder

## Bloco refinado
**BLK-MAP-02** — Filtro de marcas de concorrentes do mapa em menu expansível (fechado por padrão)

## Objetivo
Envolver o `st.multiselect("Redes de concorrentes", …)` (pages.py:4382, dentro de `render_mapa_territorial`) num `st.expander(..., expanded=False)` para o filtro nascer fechado e não empurrar o mapa para baixo.

## Escopo permitido
- Arquivo único: `src/motor_expansao/dashboard/pages.py`, bloco `_show_rede_filter` (linhas ~4373–4388).
- Envolver o `st.multiselect` em um `st.expander("Redes de concorrentes", expanded=False):`.
- Preservar integralmente:
  - `key="mapa_territorial_redes_concorrentes"` (NUNCA renomear/acentuar)
  - `options=_all_redes` (valor bruto, sem acentuação)
  - `default=_all_redes` (padrão seleciona todas)
  - `format_func=lambda r: COMPETITOR_BRANDS.get(r, {}).get("label", r)` (label exibição via COMPETITOR_BRANDS — dicionário de exibição preservado)
  - Lógica BLK-MAP-01 (linhas 4391–4396): seleção vazia ⇒ `competitors_df_filtered = None` ⇒ esconde concorrentes
- Lógica de filtragem, legenda e mapa seguem consumindo `competitors_df_filtered` como hoje (zero mudança na lógica de renderização).

## Fora de escopo
- Lógica de filtragem de concorrentes (linhas 4390–4396, que depende de `selected_redes`).
- Estrutura de legenda `_render_unified_legend` e construção de mapa `build_unified_map_figure`.
- Estado de sessão (`st.session_state["mapa_territorial_redes_concorrentes"]`).
- Dicionário `COMPETITOR_BRANDS` ou qualquer constante de marcas.
- Qualquer artefato, score, peso ou fórmula do M1.
- Mudanças em outros widgets ou abas do dashboard.

## Arquivos que devem ser lidos
- `c:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\pages.py` (linhas 4360–4410, confirmar contexto)
- `c:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\CLAUDE.md` §2 (acentuação: só texto visível acentuado, NUNCA identificadores) e §5 (READ-ONLY M1, guardrail permanente)
- `c:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tasks\backlog.md` (BLK-MAP-02, linhas ~1336–1367, para confirmar critérios)

## Arquivos que podem ser alterados
- `c:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\pages.py` (SO bloco _show_rede_filter, linhas ~4373–4388)
- `c:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tests\integration\test_streamlit_app.py` (APENAS SE algum assert travar o label ou posição do widget; DO CONTRÁRIO, deixar intacto)

## Critérios de aceite
1. **Estrutura visual:** Filtro renderiza dentro de um `st.expander` com `expanded=False` (fechado por padrão).
2. **Comportamento preservado:**
   - Abrir o expander revela o multiselect com todas as redes selecionadas por padrão.
   - Selecionar redes produz o mesmo resultado que hoje (filtra concorrentes no mapa).
   - Desselecionar TODAS as redes: `selected_redes` fica vazia ⇒ lógica BLK-MAP-01 (linha 4391) detecta vazio ⇒ `competitors_df_filtered = None` ⇒ concorrentes são ocultados no mapa e legenda. **Este é o comportamento crítico a preservar.**
   - Reselecionar redes: restaura a visualização de concorrentes.
3. **Qualidade de código:**
   - Suite de testes verde (`pytest -q` ≥ baseline, ou explicar qualquer delta).
   - `ruff check src/motor_expansao/dashboard/pages.py` — sem erros.
   - `mypy src/motor_expansao/dashboard/pages.py` — sem erros (type hints intactas).
4. **Acentuação:**
   - Texto "Redes de concorrentes" exibido acentuado (conforme CLAUDE.md §2).
   - Identificadores `key`, `options`, `default`, nomes de variáveis (**SEM acentuação**).
5. **Sem regressão:**
   - Mapa territorial com modos M1/Híbrido/Censitário/Domínio renderiza sem erro.
   - Filtro interativo responde ao clique e mudanças de seleção.

## Criticidade classificada
**Baixa** — mudança de UI localizada (so envolver widget em expander), READ-ONLY sobre o M1 (zero alteração de score/pesos/carteira/plano/artefatos oficiais), sem decisão de produto (apenas UX de compactação do layout).

## Esteira recomendada
1. **Block Orchestrator** (FEITO) — delimitar o bloco sem ambiguidade.
2. **Builder (sonnet)** — implementar envolvimento em expander, preservar lógica BLK-MAP-01, validar smoke test.
3. **QA (opus 4.8)** — rodar suite full, verificar comportamento do filtro (abrir/selecionar/desselecionar/reselecionar), validar ruff+mypy, confirmar mapa territorial em todos os modos.

## Riscos identificados
1. **Quebra da lógica BLK-MAP-01:** Se a indentação do `selected_redes` ou a estrutura condicional (linhas 4391–4396) forem acidentalmente alteradas, o comportamento "seleção vazia ⇒ esconde" pode não funcionar.
2. **Acentuação acidental de identificadores:** Renomear `_all_redes` para `_todas_redes` ou `key="mapa_territorial_redes_concorrentes"` para algo acentuado violaria §2 de CLAUDE.md.
3. **Quebra de teste de posição/label:** Se `test_streamlit_app.py` tiver algum assert que localiza "Redes de concorrentes" por posição no DOM ou por label, será necessário atualizar o teste para esperar a estrutura dentro do expander.
4. **Ciência de estado de sessão:** A chave `key="mapa_territorial_redes_concorrentes"` é consumida por `st.session_state`, então é crítico manter a chave INTACTA.
5. **Múltiplos expanders/renderização lenta:** Envolver o multiselect num expander pode afectar a contagem de widgets ou a renderização em pydeck, porém o impacto esperado é zero (expander é um container leve no Streamlit).

## Guardrails ativos
- **§2 Acentuação (CLAUDE.md):** Todo texto de UI (labels, botões, legendas) deve ter acentuação correta do português. **NUNCA acentuar:** `key=`, estado de sessão, valores brutos de enum, nomes de coluna, slugs/nomes de arquivo. Para exibir acentuado, usar uma camada de LABEL (`{valor_bruto: "Texto Acentuado"}`).
- **§5 READ-ONLY M1 (CLAUDE.md):** Visualizações, análise radial e interações de mapa **não podem** recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou artefatos oficiais do M1 sem aprovação explícita. **Este bloco é 100% READ-ONLY sobre M1.**
- **§1 Posicionamento do Motor (CLAUDE.md):** O M1 é a camada EXECUTIVA (decide municipios); o censitário é a camada PRIMARIA operacional. O mapa territorial e seu filtro de concorrentes são camadas de VISUALIZAÇÃO paralelas ao M1 — zero recálculo ou alteração de scores.
- **Padrão commit-por-path (run-cycle):** Ao fechar, commitar SO os arquivos alterados (pages.py, test_streamlit_app.py se tocado, e arquivos de fechamento em tasks/). Nunca `git add -A`.

## Observações finais para Builder
1. O bloco herda de BLK-MAP-01 (filtro já implementado e testado), o qual **DEVE permanecer intacto em lógica**.
2. O expander será "Redes de concorrentes" — exibição acentuada OK, identificador `key` do multiselect e variável `_all_redes` permanecem sem acentuação.
3. Após envolver no expander, o comportamento esperado é:
   - Expander fechado por padrão → mapa renderiza com todas as redes (default=_all_redes ativa antes do usuário abrir).
   - Usuário abre expander → vê multiselect com todas as redes selecionadas.
   - Usuário desseleciona tudo → vazio (behavior BLK-MAP-01) → esconde concorrentes.
   - Usuário reseleciona → volta a mostrar.
4. A suite de testes deve passar sem mudanças (ou mínimas ajustes de posição no DOM, se algum assert quebrar).

---

**Data/Hora gerada:** 2026-07-08 14:53:51  
**Gerado por:** Block Orchestrator (claude-haiku-4-5-20251001)  
**Snapshot:** append-only, nunca editar após criação
