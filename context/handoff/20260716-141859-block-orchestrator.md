# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-REV-08 — Spike técnico: mapa client-side (deck.gl `H3HexagonLayer` / MapLibre) servido por
`st.components.v1.html`, no padrão já provado do BLK-UI-10 (`ui_proto.py`), escalado ao volume real
do cap de produção (18k–35k hexes) + harness de medição (DevTools/Playwright/A-B VPS) — protótipo
DESCARTÁVEL, embasa a decisão de rumo do BLK-REV-12.

## Objetivo
Medir empiricamente o teto de performance do mapa client-side (deck.gl/MapLibre) vs. pydeck/Streamlit
no volume real do cap (18–35k hexes), entregando código de spike + harness de medição + runbook —
SEM decidir rumo (isso é BLK-REV-12) e SEM tocar produção/M1.

## Escopo permitido
- **Protótipo deck.gl `H3HexagonLayer` (ou MapLibre)** via `st.components.v1.html`, seguindo
  EXATAMENTE o padrão de `ui_proto.py` (BLK-UI-10): dados embutidos como JSON inline (sem round-trip
  ao servidor), recorte gerado por função tipo `gerar_recorte_json` cacheado em disco (novo diretório
  isolado, gitignored — NÃO reusar `data/cache/ui_proto/` para não colidir com o PoC do BLK-UI-10),
  layout mínimo reaproveitando `ui_theme.py` se fizer sentido.
- **Trocar Leaflet por deck.gl/MapLibre** e **escalar ao volume real do cap de produção**: usar
  `MAP_POINT_LIMIT = 35000` e `MAP_POINT_LIMIT_LARGE = 18000` (`dashboard/constants.py`) como alvo —
  NÃO os ~500 hexes do PoC Leaflet original. `H3HexagonLayer` aceita `hex_id` cru (sem geometria
  pré-computada) — usar essa vantagem para reduzir o payload JSON.
- **Código isolado/descartável**: novo módulo claramente marcado como spike (padrão de opt-in via env
  var / `session_state`, como `is_proto_enabled()` em `ui_proto.py`), que NÃO é importado por
  `pages.py`/fluxo principal de produção nem substitui nenhuma rota existente.
- **Script Playwright** (dependência JÁ existente — `playwright>=1.44.0` no extra `[scraping]` do
  `pyproject.toml`; NÃO adicionar dependência nova) cronometrando os **4 fluxos de dor** já
  diagnosticados (REV-03 dor #1 render do mapa; REV-04 dor #2 troca de modo de cor; REV-05 dor #3
  seleção de hex/cenário múltiplo; REV-06 dor #4 geração de PDF), parametrizável por URL alvo (não
  deve rodar sozinho contra produção — ver Fora de escopo).
- **Runbook de medição** (markdown) descrevendo passo a passo HUMANO: (i) DevTools contra produção —
  tamanho de frames WebSocket por rerun + tempo clique→paint; (ii) como rodar o script Playwright
  contra `dashboard.ultra-expansao.tech`; (iii) como fazer o A/B final (spike servido pelo Caddy da
  VPS) — deixando explícito, em cada passo que toca a VPS, que exige confirmação humana individual por
  comando (§6).

## Fora de escopo
- Qualquer alteração em `pages.py`/fluxo de produção do dashboard atual; o spike NÃO substitui o mapa
  em produção.
- Qualquer recálculo/alteração de `score_priorizacao`, `hex_score_estrutural`, pesos
  (`PESOS_HEX_SCORE_ESTRUTURAL`), carteira, plano curto prazo, plano de domínio ou qualquer artefato
  oficial do M1 (§5).
- **Executar qualquer comando na VPS** (deploy do spike via Caddy, `git pull`, `docker compose`,
  restart, etc.) sem confirmação humana explícita PARA CADA comando individual (§6). O Builder entrega
  o script/runbook; NÃO os executa contra a VPS de produção.
- **A medição empírica em si** (números reais de FPS, latência clique→paint, tamanho de frame
  WebSocket, resultado do A/B) NÃO é deliverable de código — é ação humana pós-Builder, dentro do gate
  `[REVISÃO HUMANA — visual/perf]` ou depois dele. O Builder não deve inventar/simular números.
- Rodar o script Playwright contra `dashboard.ultra-expansao.tech` de forma autônoma dentro da esteira
  — gerar tráfego real contra produção é decisão humana (mesmo sem exigir shell na VPS, é rede externa
  de produção).
- Decidir rumo (Streamlit+otimizar vs. SPA vs. Dash/Panel vs. deck.gl custom) — isso é o BLK-REV-12
  (gate humano + DEC), não este bloco.
- Adicionar dependência nova ao deploy base/produção (Playwright já está isolado no extra `[scraping]`;
  bibliotecas JS do spike devem vir por CDN, como em `ui_proto.py`, sem entrar no `pyproject.toml`).
- Tocar CI, CODEOWNERS, `config.py`, `deploy/`, segredos, Dockerfiles de produção.

## Arquivos que devem ser lidos
- `CLAUDE.md` (completo — §5 READ-ONLY M1, §6 guardrail VPS)
- `tasks/backlog.md` linhas 849–877 (spec BLK-REV-08 + emenda de 2026-07-10 do Felipe)
- `tasks/completed.md` linhas 7709–7824 (specs BLK-REV-03..07: as 4 dores diagnosticadas + matriz de
  decisão/topologia real de produção do REV-07 — NÃO re-litigar, partir dela)
- `src/motor_expansao/dashboard/ui_proto.py` (padrão canônico a reusar — COMPLETO: `gerar_recorte_json`,
  `_build_leaflet_html`, `render_mapa_leaflet`, `is_proto_enabled`)
- `src/motor_expansao/dashboard/ui_theme.py` (paleta/tema, se o spike quiser reusar estilo)
- `src/motor_expansao/dashboard/constants.py` (`MAP_POINT_LIMIT=35000`, `MAP_POINT_LIMIT_LARGE=18000`,
  `RESIDUAL_SCORE_BANDS`)
- `pyproject.toml` (extra `[scraping]`, confirmar `playwright>=1.44.0` já presente — sem dependência
  nova)
- `docs/infra_producao.md` (topologia VPS/Caddy — só LEITURA, para desenhar o runbook; NUNCA executar
  comando a partir daqui sem confirmação humana)
- `data/analysis/perf_baseline_app_2026.md` (relatório BLK-REV-01, se existir/acessível — referência de
  baseline; pode estar gitignored)

## Arquivos que podem ser alterados
- Novo módulo de spike isolado (nome a definir pelo Planner/Builder — ex.: sob
  `src/motor_expansao/dashboard/` marcado claramente como protótipo opt-in, análogo a `ui_proto.py`, OU
  em `scripts/` se ficar mais isolado ainda de produção)
- Novo script Playwright de medição (ex.: `scripts/` ou local a definir pelo Planner)
- Novo runbook markdown (ex.: `docs/` ou `data/reports/`)
- Novo diretório de cache do recorte do spike (gitignored, isolado de `data/cache/ui_proto/`)
- `tasks/current_task.md`, `context/handoff.md`, `context/handoff/*.md` (bookkeeping do ciclo)
- Testes novos cobrindo o spike/script (se o Planner optar por testar a função de recorte/serialização)

**Fora de alteração:** `pages.py`, `config.py`, `pipelines/m1/`, qualquer artefato M1 oficial,
`deploy/`, `secrets/`, CI, `pyproject.toml` (exceto se precisar confirmar/registrar dependência já
existente — não adicionar nova).

## Critérios de aceite
- Protótipo renderiza hexágonos REAIS do cap de produção (18k–35k, usando
  `MAP_POINT_LIMIT`/`MAP_POINT_LIMIT_LARGE`) via deck.gl `H3HexagonLayer` (ou MapLibre) client-side,
  com `hex_id` cru (sem geometria pré-computada no payload), seguindo o padrão de dados embutidos de
  `ui_proto.py` (sem round-trip ao servidor para pan/zoom/clique).
- Código do spike é isolado e claramente descartável: não é importado pelo fluxo de produção
  (`pages.py`), não substitui nenhuma rota/página existente, `git diff` do bloco confinado a
  arquivo(s) novo(s) de spike + script Playwright + runbook + testes (se houver).
- Zero alteração em `score_priorizacao`/`hex_score_estrutural`/pesos/artefatos oficiais do M1
  (verificável por mtime dos 4 artefatos oficiais + `git diff` fora de `pipelines/m1/`/`config.py`).
- Script Playwright existe, cronometra os 4 fluxos de dor (render do mapa, troca de modo de cor,
  seleção/cenário múltiplo, geração de PDF) e é parametrizável por URL alvo (não hardcoded só para
  produção) — mas NÃO é executado contra `dashboard.ultra-expansao.tech` de forma autônoma pela
  esteira.
- Runbook cobre os 3 sub-entregáveis da emenda (DevTools, Playwright contra produção, A/B via Caddy
  VPS) com nota explícita de que cada comando na VPS exige confirmação humana individual (§6).
- Nenhuma dependência nova no deploy base/produção; Playwright permanece no extra `[scraping]`;
  bibliotecas JS do spike (deck.gl/MapLibre + h3-js) entram por CDN como em `ui_proto.py`.
- Suíte de testes existente permanece verde (NO-BYPASS); ruff/mypy limpos no que for tocado.
- Os NÚMEROS reais de FPS/latência/A-B NÃO são obrigação de entrega deste bloco de código — ficam
  para a execução humana pós-Builder (gate `[REVISÃO HUMANA — visual/perf]`); não inventar métricas.

## Criticidade classificada
Média (confirmada em `tasks/backlog.md` e `tasks/current_task.md`; READ-ONLY sobre o M1 — nenhum
elemento do bloco toca `score_priorizacao`/`hex_score_estrutural`/carteira/plano/artefatos oficiais,
logo NÃO se eleva a Crítica pelo guardrail de escrita em M1).

## Esteira recomendada
Block Orchestrator (concluído) → Planner → `[REVISÃO HUMANA — visual/perf]` → Builder → QA.
Natureza especial: bloco **manual (NÃO loop-safe)** — o loop autônomo NUNCA deve pegar este bloco
(protótipo visual exige ver o render e medir no browser; §6.1 do CLAUDE.md).

## Riscos identificados
- Confundir "spike descartável" com "entrega de produção": risco de o Builder tentar
  integrar/substituir o mapa em `pages.py` — deve ficar isolado e opt-in, como `ui_proto.py`.
- Risco de a esteira autônoma tentar rodar comandos na VPS (deploy do spike via Caddy, git pull,
  restart) sem confirmação humana por comando — violaria o guardrail absoluto do §6.
- Risco de o script Playwright ser executado de fato contra `dashboard.ultra-expansao.tech` dentro da
  esteira autônoma, gerando tráfego real contra produção sem supervisão — deve ficar pronto para uso
  humano, não autoexecutado contra o domínio de produção.
- Ambiguidade "deck.gl H3HexagonLayer" vs. "MapLibre": a emenda cita as duas opções sem forçar
  escolha única — cabe ao Planner decidir (ou comparar as duas) no plano técnico, não a este handoff.
- Risco de o Planner/Builder inventar/estimar números de performance em vez de deixá-los para a
  medição humana real — o critério de aceite deste bloco é o CÓDIGO funcionar, não um número
  específico de FPS.
- Risco de vazamento de escopo para o BLK-REV-12 (decidir rumo rebuild vs. refactor) — este bloco só
  produz o insumo empírico, não a decisão.

## Guardrails ativos
- §5 (CLAUDE.md) — Guardrail permanente: visualizações, análise radial e interações de mapa não podem
  recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano
  de domínio ou artefatos oficiais do M1 sem aprovação explícita. Este bloco é 100% READ-ONLY sobre o
  M1.
- §6 (CLAUDE.md) — GUARDRAIL ABSOLUTO: nunca executar qualquer comando no servidor via MCP (ou
  qualquer tool SSH) sem confirmação explícita do usuário para CADA comando individual. Não encadear
  múltiplos comandos no servidor sem aprovação intermediária. Aplica-se integralmente aos
  sub-entregáveis (ii) e (iii) da emenda (Playwright contra produção e A/B via Caddy VPS).
- §6.1 (CLAUDE.md) — o loop autônomo (`ralph`) só executa blocos marcados `loop-safe` na tabela do
  bloco em `tasks/backlog.md`; BLK-REV-08 está marcado **`manual (NÃO loop-safe)`** — NUNCA deve ser
  pego pelo loop.
- Toda mudança relevante entra com teste; nenhum PR deve subir com CI quebrado (§2).
