# Current Task

## Bloco atual

ID: BLK-CENSO-03
Nome: Relatório censitário — refino visual do mapa (base CLARA + camada só-concorrentes + aspect retangular)
Status: APROVADO (QA 2026-06-08) — ciclo FECHADO pelo orquestrador (housekeeping feito; bloco em completed.md; commit por path na branch ciclo/BLK-CENSO-03); aguardando MERGE humano + OPS (aprovação visual final de Felipe + rebuild imagem + redeploy por digest na VPS, gated §6)
Tipo: feature
Criticidade: média
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA das decisões visuais: RESOLVIDA upfront 2026-06-08] → Builder → QA (APROVADO)
Skill atual: Fechamento (orquestrador) — concluído
Próxima Skill: Merge pelo humano da branch ciclo/BLK-CENSO-03 + OPS de deploy
dry_run: false

## Decisões do gate visual (coletadas upfront por Felipe em 2026-06-08, autorização "de uma só vez")
- **Base clara = CartoDB Voyager COM labels** (substitui a Dark Matter do FU3). Manter a legibilidade
  de ruas/nomes do FU3 INVERTENDO a recolocação de tinta: numa base CLARA, recolocar os pixels
  ESCUROS nativos do tile (luminância < cutoff), nunca edge-detection (FU1/FU2 descartados).
- **Camada só-concorrentes = SUBSTITUIR a atual "Concorrentes"** (que hoje tem choropleth de score de
  contexto) por basemap + pins de concorrentes/Ultra + ponto central, SEM choropleth. Relatório segue
  com 3 mapas (Densidade / Renda / Concorrentes-pura).
- **Conflito verde = MANTER rampas atuais** (renda amarelo→laranja→verde; score RESIDUAL_SCORE_BANDS)
  confiando na base. NOTA/trade-off: Voyager carrega verde de vegetação; Builder/QA devem usar
  contraste/contorno/saturação para que renda-alta e score-alto não se confundam com mato. Se a
  checagem visual reprovar, vira follow-up (não trocar paleta neste ciclo sem nova aprovação).

## Tiering de modelo (Passo 4)
- Block Orchestrator: sonnet (Média)
- Planner: sonnet (Média)
- Builder: opus (override +1 da tabela Média=sonnet — inverter overlay de tinta clara→escura sobre
  base clara, refactor da camada Concorrentes p/ sem-choropleth, frame retangular e coerência das
  paletas; alto risco de regressão visual/manipulação de pixel)
- QA: opus 4.8 (sempre)

## Objetivo
Aproximar o Relatório Pontual Censitário do padrão GeoFusion: trocar a base ESCURA (Dark Matter) por
base CLARA Voyager mantendo ruas/nomes nítidos por cima da cor, substituir a camada Concorrentes por
uma versão SÓ-concorrentes (sem choropleth), preservar o formato retangular, tudo READ-ONLY sobre M1.

## Paths prováveis do ciclo (a confirmar/expandir pelo Planner)
- src/motor_expansao/dashboard/censo_map.py (basemap/overlay/paletas/camadas)
- src/motor_expansao/dashboard/constants.py (rampas/cortes, se necessário)
- src/motor_expansao/dashboard/pages.py (UI das camadas)
- src/motor_expansao/dashboard/censo_report.py (páginas do PDF)
- tests correspondentes (test_relatorio_pontual_censitario_export.py, test_streamlit_app.py, censo_map)
- docs/relatorio_pontual_censitario.md + CLAUDE.md §4 + DEC-004 (se mudar provedor de tiles)

## Fora de escopo (invioláveis)
- Recálculo/escrita de M1 (score/pesos/carteira/plano/artefatos oficiais)
- Mudar o método de interseção `setor_censitario_intersecao_area_1p5km` ou o raio fixo de 1.5 km
- Tornar o dashboard interativo dependente de internet (tiles só na geração — DEC-004)
- Reusar edge-detection (FIND_EDGES) — reprovado por Felipe (FU1/FU2)
- Template/branding final do PDF (isso é o BLK-CENSO-02, já concluído)
