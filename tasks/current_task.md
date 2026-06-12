# Current Task

## Bloco atual

ID: BLK-UI-06
Nome: Corrigir o GAP do seletor de telas (flex-pai real + zerar margem negativa do baseweb)
Status: aprovado
Tipo: bug (UX/UI — CSS gap não aplicava)
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA
Skill atual: QA (concluído — APROVADO)
Próxima Skill: Fechamento manual

## Objetivo
O realce da aba ativa (BLK-UI-05) funcionou, mas o GAP entre os botões do seletor ainda não aparece.
Corrigir o espaçamento horizontal entre os botões do `st.segmented_control`. READ-ONLY M1; só CSS em
`inject_styles()`; Bloco 5 (lógica) intocado.

## Diagnóstico (DOM REAL renderizado, via playwright contra o app rodando — Streamlit 1.58.0)
Cadeia de ancestrais a partir de um botão do seletor:
- botão `stBaseButton-segmented_control[Active]` → `margin-right: -1px` (o baseweb "cola" os botões sobrepondo a borda)
- pai flex `[data-baseweb="button-group"]` (role="radiogroup", display:flex) → **`gap: 4px 0px`** = 0px de gap HORIZONTAL (o 4px é row-gap, só vale se quebrar linha)
- avô `[data-testid="stButtonGroup"]` (display:block)
- **O testid `stSegmentedControl` NÃO EXISTE nessa versão** — por isso a regra de gap do BLK-UI-04/05
  (em `[data-testid="stSegmentedControl"]`) nunca casou.

## Correção (DOM-verificada)
1. **Gap horizontal no flex-pai real**: `[data-baseweb="button-group"] { gap: 8px !important; }`
   (sobrescreve o `gap: 4px 0px` → 8px nos dois eixos; separa os botões horizontalmente).
2. **Zerar a margem negativa dos botões**: 
   `[data-testid="stBaseButton-segmented_control"], [data-testid="stBaseButton-segmented_controlActive"] { margin: 0 !important; }`
   (remove o `margin-right: -1px` que conecta os botões).
3. Manter as regras de cor já funcionando (ativa ciano sólido, inativo distinto) e os seletores legados
   `stSegmentedControl`/`aria-checked` (o teste os verifica) — só corrigir o GAP.
4. **Teste de regressão**: assert de que o CSS contém `[data-baseweb="button-group"]` com `gap` e a regra
   de `margin: 0` nos botões do seletor.

## Verificação (desta vez COM render real)
- Após o Builder, o ORQUESTRADOR roda playwright contra o app: seleciona uma UF, mede o bounding box dos
  4 botões do seletor e confirma que há ~8px de distância horizontal entre eles (gap real renderizado).
- pytest segue valendo para regressão de string, mas a prova é a medição do DOM + confirmação do usuário.

## Tiering de modelo (Passo 4) — Média
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-UI-06 (a partir de ciclo/BLK-UI-05 @ HEAD; UI-01..06 ainda não mergeados — stack)

## Escopo permitido
- src/motor_expansao/dashboard/pages.py — SÓ o bloco CSS do seletor em `inject_styles()` (~304-335)
- tests/integration/test_streamlit_app.py — assert de regressão do gap

## Fora de escopo (invioláveis)
- recalcular qualquer score ou artefato M1
- tocar `render_tab_selector` ou a lógica de render lazy (Bloco 5) — SÓ CSS
- alterar outros componentes CSS além do bloco do seletor
- recolocar dependência de API ao vivo

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md

dry_run: false
