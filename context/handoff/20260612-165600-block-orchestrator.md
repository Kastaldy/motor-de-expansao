# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-UI-06** — Corrigir o GAP entre os botões do seletor de telas (flex-pai real `[data-baseweb="button-group"]` + zerar margem negativa do baseweb)

## Objetivo
Adicionar duas regras CSS em `inject_styles()` que forçam `gap: 8px` no flex-pai real dos botões do seletor e zeram o `margin-right: -1px` que o baseweb injeta para colá-los.

## Diagnóstico confirmado (DOM REAL, Streamlit 1.58.0)
- Cadeia real: `stBaseButton-segmented_control[Active]` → pai `[data-baseweb="button-group"]` (role=radiogroup, display:flex, **`gap: 4px 0px`** — 0px horizontal) → avô `[data-testid="stButtonGroup"]`.
- `[data-testid="stSegmentedControl"]` **NÃO EXISTE** nessa versão — as regras de gap do BLK-UI-04/05 que usavam esse seletor **nunca casaram com o DOM real**.
- Botões com `margin-right: -1px` injetado pelo baseweb, que os funde em grupo visual.

## Âncoras file:line confirmadas
- `inject_styles()` definida em `src/motor_expansao/dashboard/pages.py` **linha 132**.
- Bloco CSS do seletor atual: `pages.py` **linhas 304–335** (começa em `div[data-testid="stSegmentedControl"]`, termina após a regra `stBaseButton-segmented_controlActive`).
- `render_tab_selector()` definida em `pages.py` **linha 442** — **INTOCÁVEL** (Bloco 5; zero alteração de lógica).
- Teste de regressão existente: `tests/integration/test_streamlit_app.py` função `test_inject_styles_cobre_componentes_baseweb` (linha ~4466).

## Escopo permitido
- `src/motor_expansao/dashboard/pages.py` — **SOMENTE** o bloco CSS dentro de `inject_styles()` (linhas 304–335); adicionar as duas novas regras CSS sem remover nenhuma regra existente.
- `tests/integration/test_streamlit_app.py` — adicionar assert de regressão na função `test_inject_styles_cobre_componentes_baseweb` verificando que o CSS contém `[data-baseweb="button-group"]` com `gap` e a regra de `margin: 0` nos botões do seletor.

## Fora de escopo
- `render_tab_selector()` e qualquer linha de lógica Python em `pages.py` (Bloco 5 — intocável).
- Qualquer outro bloco CSS fora do seletor de telas (linhas < 304 ou > 335 no estado atual).
- Score, pesos, fórmula ou artefatos oficiais do M1.
- Outros arquivos além dos dois acima.
- PRD.md, CLAUDE.md, backlog, paths pré-sujos.

## Correção delimitada (NÃO implementar aqui)
1. **Gap horizontal no flex-pai real** — inserir regra:
   ```css
   [data-baseweb="button-group"] { gap: 8px !important; }
   ```
   Sobrescreve o `gap: 4px 0px` nativo → 8px em ambos os eixos; separa os botões horizontalmente.

2. **Zerar a margem negativa** — inserir regra:
   ```css
   [data-testid="stBaseButton-segmented_control"],
   [data-testid="stBaseButton-segmented_controlActive"] { margin: 0 !important; }
   ```
   Remove o `margin-right: -1px` que colapsa os botões.

3. **Manter** todas as regras de cor já presentes (ativa ciano `#19B7FF`, inativo `rgba(30,38,65,0.88)`, hover) e todos os seletores legados (`stSegmentedControl`, `aria-checked`, `aria-selected`, `[data-baseweb="button-group"] button`) — NADA removido.

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/pages.py` — linhas 132–374 (bloco completo de `inject_styles`) e linhas 442–466 (`render_tab_selector`; confirmar byte-idêntico após o Builder).
- `tests/integration/test_streamlit_app.py` — função `test_inject_styles_cobre_componentes_baseweb` (~linha 4466).

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/pages.py` — somente bloco CSS linhas 304–335.
- `tests/integration/test_streamlit_app.py` — somente o corpo de `test_inject_styles_cobre_componentes_baseweb` (adicionar asserts; sem remover nenhum assert existente).

## Critérios de aceite
1. CSS gerado por `inject_styles()` contém a regra `[data-baseweb="button-group"]` com `gap` e `!important`.
2. CSS gerado contém `margin: 0 !important` aplicado a `stBaseButton-segmented_control` e `stBaseButton-segmented_controlActive`.
3. Todas as regras anteriores do bloco 304–335 permanecem presentes (sem remoção).
4. `render_tab_selector()` byte-idêntico ao estado pré-Builder (ausente do `git diff` de lógica).
5. `python -m pytest tests/integration/test_streamlit_app.py -q` — sem falha nova (baseline: 183 passed).
6. `python -m pytest -q` (suíte full) — sem falha nova além das 3 pré-existentes (baseline: 696 passed, 1 skipped, 3 failed).
7. `ruff check` + `mypy` limpos em `pages.py`.
8. **Verificação RENDER (além do pytest)**: após o QA/Builder, o orquestrador ou o usuário confirma visualmente (navegador ou playwright medindo bounding box dos 4 botões) que há ~8px de distância horizontal entre os botões do seletor. O pytest só valida a STRING do CSS — a prova final é o DOM renderizado.

## Criticidade classificada
**Média** (CSS de visualização; READ-ONLY sobre M1; sem impacto em score, artefatos, lógica de render lazy ou Bloco 5)

## Esteira recomendada
Block Orchestrator (concluído) → **Planner** → Builder (sonnet) → QA (opus 4.8 — sempre)

## Tiering de modelo (Média)
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre; nunca abaixo)

## Riscos identificados
- O seletor `[data-baseweb="button-group"]` é mais amplo que o específico do segmented control — pode afetar outros `button-group` do baseweb na UI se existirem; mitigado por inspecionar o DOM e confirmar que só o seletor de telas usa esse componente neste dashboard.
- Os testids `stBaseButton-segmented_control(Active)` podem mudar em versões futuras do Streamlit; mitigados pelos seletores legados (`aria-checked`/`aria-selected`/`[data-baseweb="button-group"] button`) que permanecem como fallback.
- pytest valida apenas a STRING do CSS no HTML gerado, não o render real — a confirmação visual no navegador é obrigatória e insubstituível (registrado explicitamente nos critérios de aceite).

## Guardrails ativos
- `render_tab_selector` e toda a lógica do Bloco 5 são INTOCÁVEIS.
- Visualizações e CSS não podem recalcular nem alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano ou artefatos oficiais do M1.
- Paths pré-sujos NÃO commitar: `data/outputs/setores_censitarios_2022_geo/_metadata.json` e `data/reports/relatorio_pontual_censitario_base_geo.md`.
- Nenhum PR sobe com CI quebrado.
- PRD.md intocado.
