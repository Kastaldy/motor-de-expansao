# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-UI-01 — 2º Recorte: Densidade/Clareza de Dados + Navegação e Fluxo

Refinamento do bloco amplo BLK-UI-01 para o 2º ciclo de entrega. Os recortes anteriores
(BLK-UI-01 sidebar + indicadores; BLK-UI-02 coord/tooltip/densificação; BLK-UI-03 rev. coord/preview/seletor)
resolveram problemas de apresentação imediata. Este recorte foca nas duas frentes priorizadas por Vinicius
em 2026-06-16: (1) reduzir poluição visual de tabelas/KPIs/tooltips e melhorar leitura de números;
(2) melhorar navegação e fluxo entre abas e seções.

## Objetivo
Reduzir sobrecarga visual de KPIs, tabelas e captions nas 5 abas, e tornar a navegação mais fluida e
autodescritiva — sem regredir funcionalidade, score ou performance.

## Candidatos concretos de melhoria

### Frente 1 — Densidade/Clareza de Dados

**F1-A: Colunas em excesso nas tabelas principais (prioridade ALTA — decisão de produto no gate)**
- `render_carteira_expansao` (`pages.py:1399–1444`): tabela principal exibe 25+ colunas simultaneamente.
  Colunas raramente usadas em leitura executiva: "Consumo Conc. (est.)", "Consumo Ultra (real)",
  "Outlier", "Dens. < 5k", "Join Restrito", "Coverage %", "Rank Mun. UF", "Rank Mun. Brasil".
  CANDIDATO: propor um set de ≤ 15 colunas "primárias" visíveis por padrão; demais via expander ou scroll.
  ZERO coluna removida do dataset ou do parquet — apenas redução da densidade visual padrão.
- `render_plano_expansao` (`pages.py:1765–1804`): mesma proliferação (22+ colunas).
- `render_expansao_dominio` (`pages.py:1572–1612`): 17 colunas incluindo "Cluster" e IDs técnicos.

**F1-B: KPIs excessivos na Análise Pontual (prioridade MEDIA)**
- `_render_analise_pontual_multihex` (`pages.py:1949–1965`): 3 linhas de KPIs (4 + 5 + 3 = 12 métricas).
  "Consumo concorrentes", "Consumo Ultra", "Consumo total instalado" se repetem parcialmente na seção
  pontual simples logo abaixo. CANDIDATO: colapsar para ≤ 9 KPIs em ≤ 2 linhas; métricas de consumo
  podem ser caption ou subtabela complementar.
- `render_analise_pontual` simples (`pages.py:2114–2148`): sequência 4+4+3 KPIs (11 total). CANDIDATO:
  consolidar o bloco de consumo (consumo_concorrentes_raio, consumo_ultra_raio) como um caption após
  os 4 KPIs principais, reduzindo para 8 métricas primárias.

**F1-C: Captions técnicas repetidas (prioridade BAIXA)**
- A string "Leitura por centroide H3 res-7: precisão aproximada ~0.5-1 km. Não altera score_priorizacao..."
  aparece em pelo menos 2 lugares (`pages.py:1939–1941`, `pages.py:2089–2091`). CANDIDATO: extrair
  para constante `_CENTROID_DISCLAIMER` em `pages.py`; elimina drift de copy sem alterar conteúdo.

**F1-D: Formatação de números inconsistente (prioridade MEDIA)**
- Verificar via grep se `format_int` (`utils.py`) produz separador de milhar consistente em todos os
  contextos (renda, residual, população). Scores exibidos com 1 casa decimal (correto); verificar se
  o padrão é explícito ou acidental. Se inconsistência confirmada, corrigir em `utils.py` + chamadores
  em `pages.py`. Não alterar lógica de cálculo — apenas saída de exibição.

### Frente 2 — Navegação e Fluxo

**F2-A: Labels longos no segmented_control com 5 abas (prioridade ALTA)**
- `DASHBOARD_TAB_LABELS` (`pages.py:444–450`) tem 5 entradas: "Visao Executiva", "Mapa Territorial",
  "Expansao de Dominio", "Carteira e Plano", "Viabilidade do Imovel". Com 5 itens em tela estreita
  ou zoom padrão, os labels longos comprimem os botões do segmented_control. CANDIDATO: encurtar para
  ≤ 18 chars cada (ex.: "Visão Executiva", "Mapa", "Domínio", "Carteira", "Viabilidade"). Planner
  deve listar todos os testes que verificam esses strings antes de propor a mudança — quebras de assert
  são esperadas e tratáveis.

**F2-B: Estado vazio com comando shell exposto (prioridade MEDIA)**
- `render_carteira_expansao` (`pages.py:1223–1226`), `render_plano_expansao` (`pages.py:1646–1651`),
  `render_expansao_dominio` (`pages.py:1489–1493`): mensagens de estado vazio expõem comandos shell
  Python ao usuário final. CANDIDATO: substituir por texto de produto em 1 frase ("O plano de domínio
  é gerado durante o ciclo de regeneração dos parquets — contate o time de dados se esta tela estiver
  vazia em produção."), sem o `python -m jobs...` visível.

**F2-C: Filtros avançados na sidebar sem distinção de prioridade (prioridade MEDIA)**
- `render_sidebar_filters` (`pages.py:504–543`): filtros "Elegibilidade híbrida", "Cobertura censitária",
  "Qualidade da camada" + checkboxes `top_municipio`/`top_hex_intraurbano` ficam expostos diretamente
  na sidebar, gerando ruído para usuários executivos que só usam UF/cidade/faixa. CANDIDATO: mover
  esses 5 controles para `st.sidebar.expander("Filtros avançados", expanded=False)` colapsado por
  padrão. INVARIANTE OBRIGATÓRIA: `render_uf_selectbox` deve permanecer como PRIMEIRO elemento
  renderizado na sidebar (gate de carga lazy do Bloco 4).

**F2-D: Ausência de separadores de seção no Mapa Territorial (prioridade BAIXA)**
- `render_mapa_territorial` chama `render_analise_territorial` e `render_ranking_priorizacao` sem
  separadores visuais explícitos entre subseções. CANDIDATO: adicionar `st.markdown("---")` e heading
  curto antes de cada subseção, consistente com o padrão já usado em `render_visao_executiva`.

**F2-E: Hero header sem contexto de UF selecionada (prioridade BAIXA — avaliar custo)**
- `render_header` (`pages.py:390–404`) não sabe qual UF está selecionada. CANDIDATO: receber `selected_uf`
  como parâmetro opcional e incluir no subtítulo da hero card. RISCO: exige mudança na assinatura de
  `render_header` e no chamador em `streamlit_app.py:447`. Planner avalia se custo/benefício vale.

## Decisões de produto que precisam de gate humano antes de codar

- **F1-A**: quais colunas são "primárias" vs "secundárias" na Carteira e no Plano (Felipe é usuário
  principal; precisa validar o set antes do Builder).
- **F2-A**: novos labels das 5 abas (impacto em todos os assets e documentação que citam os nomes).
- **F2-C**: usuários que dependem dos filtros avançados na primeira dobra da sidebar precisam ser
  avisados da mudança de comportamento.

## O que FICA PARA RECORTES FUTUROS

- Redesenho de layout ou proporções de grid.
- Troca de `st.dataframe` por componentes custom/ag-grid.
- Mudanças em builders de mapa, layers ou tooltips (Bloco 6 anti-OOM).
- Qualquer mudança funcional na aba "Viabilidade do Imóvel" (apenas label em F2-A).
- Mudanças no fluxo de multi-hex além do colapso de KPIs (F1-B).
- Animações / loading skeletons.
- Novos campos ou colunas derivadas.

## Escopo permitido

- `src/motor_expansao/dashboard/pages.py` — render functions: strings, captions, column sets, expander
- `src/motor_expansao/dashboard/utils.py` — APENAS formatação de números (F1-D), se inconsistência confirmada
- `src/motor_expansao/dashboard/constants.py` — APENAS `DASHBOARD_TAB_LABELS` se F2-A for aceito
- `streamlit_app.py` — APENAS `render_header` se F2-E for aprovado pelo Planner
- `tests/integration/test_streamlit_app.py` — atualizar assertions de string se labels mudarem

## Fora de escopo

- `score_priorizacao`, `hex_score_estrutural`, pesos M1, artefatos oficiais do M1 — ZERO toque.
- `render_mapa_pydeck_fragment` e builders de mapa em `components.py` (Bloco 6).
- Lógica de carga lazy por UF (`load_uf_slice`, Bloco 4) e render lazy (`render_tab_selector` state).
- Qualquer pipeline fora de `dashboard/`.
- `censo_map.py`, `censo_report.py`, `censo_point.py` — INTOCADOS.
- Deploy, VPS, Docker, segredos.

## Arquivos que devem ser lidos (pelo Planner)

- `src/motor_expansao/dashboard/pages.py` (inteiro — 3000+ linhas)
- `src/motor_expansao/dashboard/utils.py` (helpers de formatação)
- `src/motor_expansao/dashboard/constants.py` (`DASHBOARD_TAB_LABELS`)
- `streamlit_app.py` (fluxo `main()` e `render_header`)
- `tests/integration/test_streamlit_app.py` (para mapear quais testes quebram se labels mudarem)
- `tasks/completed.md` (entradas BLK-UI-01, BLK-UI-02, BLK-UI-03 — não reproponr o que já foi feito)

## Arquivos que podem ser alterados

- `src/motor_expansao/dashboard/pages.py`
- `src/motor_expansao/dashboard/utils.py` (somente se F1-D confirmado)
- `src/motor_expansao/dashboard/constants.py` (somente se F2-A aceito)
- `streamlit_app.py` (somente se F2-E aprovado)
- `tests/integration/test_streamlit_app.py`

## Critérios de aceite

1. **F1-A (tabelas)**: tabela principal da Carteira e do Plano exibem ≤ 15 colunas por padrão; colunas
   secundárias acessíveis sem scroll horizontal agressivo; ZERO coluna removida do dataset.
2. **F1-B (KPIs)**: `_render_analise_pontual_multihex` renderiza ≤ 9 KPIs em ≤ 2 linhas sem perder dados.
3. **F1-C (captions)**: a string de disclaimer de centroide existe em exatamente 1 lugar; verificável
   por `grep "centroide H3 res-7" pages.py | wc -l` == 1.
4. **F2-A (labels)**: `DASHBOARD_TAB_LABELS` tem 5 entradas com ≤ 18 chars cada; CSS de hover/ativo
   funciona; assert de string atualizado nos testes.
5. **F2-B (estado vazio)**: mensagens de estado vazio nas 3 abas (Domínio, Carteira, Plano) sem comandos
   shell visíveis; texto legível em 1 frase de produto.
6. **F2-C (filtros avançados)**: os 5 controles avançados estão em `st.sidebar.expander` colapsado;
   `render_uf_selectbox` é PRIMEIRO elemento renderizado na sidebar (verificável no código).
7. **Sem regressão**: `pytest -q` passa com ≤ 3 falhas pré-existentes documentadas na dívida operacional
   (test_csvs_concorrentes_legiveis[csv_path1-223], [csv_path2-472],
   test_parquet_final_respeita_guardrails_do_piloto).
8. **READ-ONLY M1**: `ruff check` limpo; `mypy` sem novos erros; diff não toca `config.py`,
   `pipelines/m1/`, scores, artefatos ou deploy.

## Criticidade classificada
Alta (toca a navegação e apresentação do dashboard de produção; READ-ONLY sobre M1)

## Esteira recomendada
Block Orchestrator (este handoff) → Planner (Opus — design detalhado + fatiamento final dos candidatos +
lista de testes afetados) → [REVISÃO HUMANA — Felipe/Vini aprovam o plano antes de codar] →
Builder (Opus) → QA (Opus 4.8)

## Riscos identificados

1. **F2-A labels**: encurtar labels quebra testes de integração com strings exatas — Planner deve
   listar todos os asserts afetados antes de codar.
2. **F2-C expander sidebar**: mover filtros muda comportamento padrão para usuários que dependem deles
   na primeira dobra — decisão de produto para Felipe/Vini no gate.
3. **F1-A coluna set**: decidir "primárias" vs "secundárias" é decisão de produto (Felipe é usuário
   principal da carteira) — Planner propõe; gate humano decide.
4. **F2-E hero contextual**: exige mudança de assinatura em `render_header` e no chamador `main()` —
   Planner avalia custo/benefício; candidato de baixo impacto se não valer.
5. **Paths pré-sujos**: `data/outputs/setores_censitarios_2022_geo/_metadata.json` e
   `data/reports/relatorio_pontual_censitario_base_geo.md` estão com modificações pré-existentes;
   Builder NÃO deve commitá-los.

## Guardrails ativos

- §2: offline preservado; sem dependência de API ao vivo; CSV sep=";" encoding="utf-8-sig".
- §4 (Blocos 4/5/6): carga lazy por UF, render lazy de abas e fonte de mapa enxuta INTOCADOS.
  INVARIANTE: `render_uf_selectbox` é o PRIMEIRO elemento da sidebar.
- §5 guardrail permanente: visualizações não podem recalcular `score_priorizacao`,
  `hex_score_estrutural`, carteira, plano ou artefatos oficiais do M1.
- Loop guard: diff não pode tocar `config.py`, `pipelines/m1/`, `*scoring*`, artefatos M1,
  `deploy/`, `Dockerfile.*`, compose, Caddy, authelia, `.env`, `secrets/`.
- Paths pré-sujos NÃO commitar: `data/outputs/setores_censitarios_2022_geo/_metadata.json` e
  `data/reports/relatorio_pontual_censitario_base_geo.md`.
