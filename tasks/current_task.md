# Current Task

## Bloco atual

ID: BLK-UI-05
Nome: Corrigir CSS do seletor de telas (seletores reais do st.segmented_control + !important)
Status: aprovado (QA 2026-06-12; pendente apenas confirmação VISUAL do usuário no navegador)
Tipo: bug (UX/UI — CSS não aplicava)
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA (concluída)
Skill atual: QA (concluído — APROVADO)
Próxima Skill: Fechamento manual + confirmação visual do usuário

## Objetivo
Fazer o destaque do seletor de telas (BLK-UI-04) realmente RENDERIZAR: a aba ativa não ficava
ciano sólido e o gap não aparecia, porque o CSS usava seletores que NÃO casam o DOM real do
`st.segmented_control` no Streamlit 1.58. READ-ONLY M1; só CSS em `inject_styles()`; Bloco 5 intocado.

## Diagnóstico (confirmado contra o frontend instalado do Streamlit 1.58.0)
- O estado ATIVO do `st.segmented_control` é marcado pelo testid `stBaseButton-segmented_controlActive`
  (NÃO por `aria-checked`/`aria-selected`). Confirmado via grep no bundle JS do Streamlit
  (`segmented_control` e `segmented_controlActive` presentes).
- O botão INATIVO é `stBaseButton-segmented_control`.
- A regra ATIVA atual (pages.py:325-333) usa `button[aria-checked="true"]`/`[aria-selected="true"]` →
  nunca casa → aba ativa não vira ciano sólido.
- A regra BASE atual (pages.py:309-319, `[data-testid="stSegmentedControl"] button`) CASA (por isso os
  botões já têm border-radius/borda), mas o gap (304-308) e o fundo distinto podem ser sobrepostos pelo
  CSS emotion do Streamlit (especificidade alta) → faltam `!important`.

## Correção (seletores reais + !important)
- Aba ATIVA: adicionar regra `[data-testid="stBaseButton-segmented_controlActive"]` com
  `background:#19B7FF !important; color:#0A0C18 !important; border-color:#19B7FF !important;
  font-weight:700 !important; box-shadow:0 0 8px rgba(25,183,255,0.35) !important;`
- Botões INATIVOS: adicionar/garantir `[data-testid="stBaseButton-segmented_control"]` com
  `background:rgba(30,38,65,0.88) !important; border:1px solid rgba(25,183,255,0.30) !important;
  color:<muted> !important; border-radius:10px !important;`
- GAP: `[data-testid="stSegmentedControl"] { gap:8px !important; }` (manter display:flex).
- MANTER os seletores `aria-checked`/`stSegmentedControl` já presentes (o teste
  `test_inject_styles_cobre_componentes_baseweb` os verifica) — só ADICIONAR os corretos, não remover.

## Limite de verificação (importante)
- O `pytest` NÃO detecta se o CSS RENDERIZA no navegador (o teste só checa a string no CSS — passou no
  BLK-UI-04 mesmo sem aplicar). Adicionar teste de REGRESSÃO asserindo que o CSS contém
  `stBaseButton-segmented_controlActive`. A confirmação VISUAL final é do usuário (navegador).

## Tiering de modelo (Passo 4) — Média
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-UI-05 (a partir de ciclo/BLK-UI-04 @ HEAD; UI-01..05 ainda não mergeados — stack)

## Escopo permitido
- src/motor_expansao/dashboard/pages.py — SÓ o bloco CSS do `stSegmentedControl` em `inject_styles()` (~304-333)
- tests/integration/test_streamlit_app.py — assert de regressão dos seletores reais

## Fora de escopo (invioláveis)
- recalcular qualquer score ou artefato M1
- tocar `render_tab_selector` ou a lógica de render lazy (Bloco 5) — SÓ CSS
- alterar outros componentes CSS além do bloco do seletor
- recolocar dependência de API ao vivo

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md

dry_run: false
