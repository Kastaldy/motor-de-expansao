# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-UI-05 — Corrigir CSS do seletor de telas (seletores reais do `st.segmented_control` + `!important`)

## Objetivo
Adicionar os seletores reais do DOM do Streamlit 1.58 (`stBaseButton-segmented_controlActive` / `stBaseButton-segmented_control`) com `!important` ao bloco CSS de `inject_styles()` em `pages.py`, de modo que a aba ativa fique ciano sólido e o gap apareça no navegador.

## Diagnóstico confirmado

### Âncoras confirmadas via leitura do código:
- `inject_styles()` começa em **`pages.py:132`**.
- Bloco CSS do `stSegmentedControl`:
  - GAP: **`pages.py:304-308`** — `div[data-testid="stSegmentedControl"]` com `display:flex; gap:8px` (sem `!important` → pode ser sobreposto pelo emotion do Streamlit).
  - Botões INATIVOS: **`pages.py:309-319`** — `[data-testid="stSegmentedControl"] button` (casa o DOM real, sem `!important`).
  - Botões HOVER: **`pages.py:320-324`**.
  - Botões ATIVOS: **`pages.py:325-333`** — usa `button[aria-checked="true"]`/`button[aria-selected="true"]` → **NUNCA CASA** o DOM real do Streamlit 1.58; defect confirmado.
- `render_tab_selector()` começa em **`pages.py:440`** — INTOCÁVEL (lógica de Bloco 5).
- Teste de regressão existente: **`tests/integration/test_streamlit_app.py:4466`** — `test_inject_styles_cobre_componentes_baseweb` verifica strings `"stSegmentedControl"`, `'aria-checked="true"'`/`'aria-selected="true"'`, e `"#19B7FF"`.

### Causa raiz:
O Streamlit 1.58 marca o botão ativo com `data-testid="stBaseButton-segmented_controlActive"` (NÃO com `aria-checked`/`aria-selected`). Os seletores atuais (linhas 325-333) nunca casam → aba ativa não recebe fundo ciano. O CSS emotion do Streamlit tem especificidade alta e sobrepõe as regras sem `!important`.

## Escopo permitido
- `src/motor_expansao/dashboard/pages.py` — SOMENTE o bloco CSS do `stSegmentedControl` dentro de `inject_styles()` (linhas ~304-333). Adicionar novas regras com os seletores reais + `!important`; NÃO remover os seletores `aria-checked`/`aria-selected` existentes (o teste os exige).
- `tests/integration/test_streamlit_app.py` — adicionar assert de regressão verificando que o CSS contém `"stBaseButton-segmented_controlActive"` (e opcionalmente `"stBaseButton-segmented_control"`).

## Correção prescrita

### Regras a ADICIONAR (não substituir) em `inject_styles()`:

**Aba ATIVA** (adicionar após/junto do bloco `aria-checked` existente, linhas 325-333):
```css
[data-testid="stBaseButton-segmented_controlActive"] {
    background: #19B7FF !important;
    color: #0A0C18 !important;
    border-color: #19B7FF !important;
    font-weight: 700 !important;
    box-shadow: 0 0 8px rgba(25,183,255,0.35) !important;
}
```

**Botões INATIVOS** (adicionar seletor `stBaseButton-segmented_control` com `!important`):
```css
[data-testid="stBaseButton-segmented_control"] {
    background: rgba(30,38,65,0.88) !important;
    border: 1px solid rgba(25,183,255,0.30) !important;
    color: <COLORS["muted"]> !important;
    border-radius: 10px !important;
}
```

**GAP** (reforçar com `!important` o seletor existente em linhas 304-308):
```css
div[data-testid="stSegmentedControl"],
div[data-testid="stSegmentedControl"] > div {
    display: flex !important;
    gap: 8px !important;
}
```

## Limite de verificação
- `pytest` NÃO detecta se o CSS renderiza no navegador — verifica apenas a presença das strings no CSS gerado. O teste do BLK-UI-04 passou mesmo sem o CSS aplicar visualmente.
- A confirmação VISUAL final (aba ativa fica ciano sólido, gap aparece) é responsabilidade do USUÁRIO no navegador.
- O assert de regressão a adicionar (`"stBaseButton-segmented_controlActive" in css`) evita regressão futura de remoção acidental, mas NÃO substitui a confirmação visual.

## Fora de escopo
- Recalcular qualquer score ou artefato M1
- Tocar `render_tab_selector()` (pages.py:440+) ou qualquer lógica de render lazy (Bloco 5) — SÓ CSS
- Alterar CSS de outros componentes além do bloco do seletor de telas (~linhas 304-333)
- Recolocar dependência de API ao vivo
- Mergear branches ou tocar outros arquivos além dos dois listados acima
- Alterar PRD.md, CLAUDE.md, `data/outputs/setores_censitarios_2022_geo/_metadata.json`, `data/reports/relatorio_pontual_censitario_base_geo.md`

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/pages.py` (linhas 132-355: `inject_styles()` completa)
- `src/motor_expansao/dashboard/pages.py` (linhas 440-470: `render_tab_selector()` — para confirmar que NÃO será tocada)
- `tests/integration/test_streamlit_app.py` (linhas 4466-4483: teste existente `test_inject_styles_cobre_componentes_baseweb`)
- `src/motor_expansao/dashboard/constants.py` (verificar `COLORS["muted"]` e `COLORS["text"]`)

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/pages.py` — SÓ bloco CSS dentro de `inject_styles()` (~linhas 304-333)
- `tests/integration/test_streamlit_app.py` — adicionar assert de regressão em `test_inject_styles_cobre_componentes_baseweb`

## Critérios de aceite
- O CSS gerado por `inject_styles()` contém o seletor `stBaseButton-segmented_controlActive` com `#19B7FF !important`.
- O CSS gerado contém o seletor `stBaseButton-segmented_control` com `!important`.
- Os seletores `aria-checked="true"` e `aria-selected="true"` PERMANECEM no CSS (não foram removidos).
- O seletor `stSegmentedControl` PERMANECE no CSS.
- O teste `test_inject_styles_cobre_componentes_baseweb` continua passando.
- Novo assert de regressão `"stBaseButton-segmented_controlActive" in css` adicionado e passando.
- `render_tab_selector()` (pages.py:440+) NÃO foi alterada — confirmar via diff.
- Suite completa `pytest -q` passa sem novos failures (baseline: 696 passed, 1 skipped, 3 failed pre-existentes).
- `ruff check` e `mypy` limpos sobre os arquivos alterados.
- Nenhum artefato M1 foi tocado.

## Criticidade classificada
Média (bug-fix CSS localizado; READ-ONLY sobre M1; sem risco a artefatos oficiais)

## Esteira recomendada
Block Orchestrator (concluído) → **Planner** → Builder (sonnet) → QA (opus 4.8)

## Tiering de modelo
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre)

## Riscos identificados
- O `pytest` não valida render visual; o assert de regressão só garante presença da string — confirmação visual obrigatória pelo usuário.
- O Streamlit pode mudar os testids em versões futuras; os seletores `aria-checked`/`aria-selected` legados funcionam como fallback documentado e DEVEM ser mantidos.
- Branch stack (ciclo/BLK-UI-05 sobre ciclo/BLK-UI-04): o Builder deve operar sobre a branch correta.
- Paths pré-sujos (`data/outputs/setores_censitarios_2022_geo/_metadata.json` e `data/reports/relatorio_pontual_censitario_base_geo.md`) NÃO devem ser commitados.

## Guardrails ativos
- Guardrail permanente (CLAUDE.md §5): visualizações e interações de mapa não podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou artefatos oficiais do M1 sem aprovação explícita.
- Bloco 5 INTOCÁVEL: `render_tab_selector` e a lógica de `st.segmented_control`/`session_state` não podem ser alteradas (CLAUDE.md §4).
- CLAUDE.md §6: NUNCA executar comandos no VPS sem confirmação explícita do usuário para cada comando individual.
