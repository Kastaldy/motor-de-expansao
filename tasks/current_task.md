# Current Task

## Bloco atual

ID: BLK-UI-04
Nome: Destaque do seletor de telas (aba ativa em ciano sólido, mais espaço, botões distintos dos cartões)
Status: aprovado
Tipo: feature (UX/UI — CSS)
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA
Skill atual: QA (concluído)
Próxima Skill: Fechamento manual (merge da branch ciclo/BLK-UI-04)

## Objetivo
Refinar SÓ o seletor de telas (`st.segmented_control` das 4 abas) via CSS em `inject_styles()`,
READ-ONLY M1 e sem tocar a lógica de render lazy (Bloco 5):
(1) aba ATIVA com cor bem destacada das demais;
(2) maior espaçamento entre os botões;
(3) fundo dos botões distinto dos cartões de valores ao redor (hoje quase idênticos, então camuflam).

## Observações do usuário (origem, 2026-06-12)
- A tela cujo botão está em exibição deve ficar com cor destacada em relação às outras.
- O distanciamento entre os botões deve ser um pouco maior.
- Todos os botões devem ter cor que os destaque dos cartões de valores ao redor (ficam camuflados).

## Decisão de produto capturada (Felipe/Vini, 2026-06-12)
- Aba ATIVA = **ciano sólido preenchido** (fundo ciano cheio `brand_alt`/#19B7FF, texto escuro, bold)
  — alto contraste. As 3 mudanças serão aplicadas; esta fixa o estilo da ativa.

## Diagnóstico (código real, inject_styles em pages.py)
- Cartões de valores: `stMetric`/`.section-card`/`.model-card` usam
  `background: linear-gradient(180deg, rgba(18,23,42,0.96), rgba(14,19,36,0.96))`.
- Botões INATIVOS do seletor (pages.py:307): `background: rgba(18,23,42,0.92)` — quase IGUAL aos cartões
  → causa da camuflagem. Trocar por um slate mais claro/distinto + borda visível.
- Botão ATIVO (pages.py:320-328): hoje `rgba(25,183,255,0.22)` (tom fraco) → trocar por ciano SÓLIDO.
- Espaçamento: adicionar `gap` ao container do `stSegmentedControl` (Planner confirma o seletor correto).

## Tiering de modelo (Passo 4) — Média
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-UI-04 (a partir de ciclo/BLK-UI-03 @ HEAD; UI-01..04 ainda não mergeados — stack)

## Escopo permitido
- src/motor_expansao/dashboard/pages.py — SÓ o bloco CSS do `stSegmentedControl` em `inject_styles()` (~301-328)
- tests/integration/test_streamlit_app.py — se necessário (ex.: test_inject_styles_cobre_componentes_baseweb)

## Fora de escopo (invioláveis)
- recalcular qualquer score ou artefato M1
- tocar `render_tab_selector` (~426-450) ou a lógica de render lazy de abas (Bloco 5) — SÓ CSS
- alterar outros componentes visuais além do bloco CSS do seletor
- recolocar dependência de API ao vivo

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md

dry_run: false
