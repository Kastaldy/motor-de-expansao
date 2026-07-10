# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (criticidade Estratégica; esteira do loop = BO → Planner → Builder → QA).

## Bloco refinado
**BLK-REV-07 — Avaliação de fundação: Streamlit vs. alternativas (matriz de decisão).**
Pesquisa/relatório que CONSOLIDA os achados dos ciclos REV-01..06 (baseline de
performance + inventário arquitetural + 4 diagnósticos de gargalo: mapa pydeck, troca de
cor, seleção de hex, PDF) numa **avaliação estruturada das 4 opções de stack**, produzindo
uma **matriz de decisão + recomendação PRELIMINAR**. NÃO decide — a decisão real
(rebuild vs refactor) fica no BLK-REV-12 (gate humano + DEC). READ-ONLY sobre o M1.
Entregável único: relatório `data/analysis/avaliacao_stack.md` (gitignored).

## Objetivo
Produzir uma matriz de decisão comparando as 4 opções de stack contra critérios fixos,
com recomendação preliminar fundamentada nas evidências dos REV-01..06 e no espectro
incremental→cirúrgico→rebuild, sem tomar a decisão final (que é do REV-12).

## Ponto de partida OBRIGATÓRIO (topologia REAL de produção — confirmada, NÃO re-descobrir)
Confirmado em `docker-compose.prod.yml`: a produção **já é multi-container**, não um
monólito: `streamlit` + **`api` (FastAPI, `src/motor_expansao/api/`)** + `telegram-bot` +
**`caddy` (reverse proxy 80/443)** + `authelia`. Os **dados vivem na VPS como volumes `:ro`**
(`/opt/motor-expansao/data/...`) — **fora dos containers** — e `streamlit` E `api` já
consomem **os MESMOS volumes read-only**. Consequências que a avaliação DEVE assumir como dadas:
- **"Requisito offline §2" ≠ "sem backend".** Significa **sem serviço EXTERNO ao vivo**.
  A própria `api` na VPS lendo arquivos locais JÁ é o modelo atual e NÃO viola o §2 (tiles/
  geocoding são exceções pontuais DEC-004/010/011). Um frontend web servido pela mesma VPS,
  chamando a `api` que lê os mesmos volumes, preserva o offline 100%.
- **Custo de migração MENOR:** backend (`api`) e reverse proxy (`caddy`) JÁ existem. As
  opções (b)/(d) viram, na prática, **"trocar o container `streamlit` por um frontend estático
  (SPA) servido pelo Caddy já existente"**, reusando/estendendo a `api` e mantendo dados/Caddy/
  Authelia/rede intactos — NÃO é reescrever do zero.
- **NÃO re-litigar o offline §2** (já esclarecido). Partir daqui.

## Opções a avaliar (as 4, sem adicionar/remover)
- **(a) Manter Streamlit + otimizar** — `st.fragment` (já parcial), `@st.cache_data`/
  `@st.cache_resource` nos builders, tooltip enxuto, cap, shared transformer no PDF.
- **(b) Frontend React/Next.js (SPA estático servido pelo Caddy) + a `api` FastAPI existente.**
- **(c) Dash / Panel.**
- **(d) Frontend custom com deck.gl/MapLibre client-side + a `api`.**

## Critérios de avaliação (matriz — colunas obrigatórias)
1. **Performance** — mapa, troca de cor/seleção sob o modelo de rerun (ancorar nos números REV-01..05).
2. **Controle de UX** — progressive disclosure para leigos (dor #5).
3. **Preservação do offline §2** — dado local na VPS (todas as opções conseguem; comparar COMO).
4. **Reuso da `api`/Caddy/volumes já existentes** — quanto de infra já pronta cada opção aproveita.
5. **Velocidade/custo de dev e manutenção por perfil de time** — Python-only vs com frontend (JS/TS).
6. **Risco de migração.**
7. **Espectro incremental→cirúrgico→rebuild** — mapear onde cada opção cai
   (cache+fragment → trocar SÓ o mapa por componente client-side → rebuild do frontend sobre a `api`).

## Evidências de entrada (já produzidas — CITAR, não re-medir)
- **REV-01** `data/analysis/perf_baseline_app_2026.md` — baseline dos 6 caminhos (carga por UF,
  render, troca de cor, multi-hex, PDF). Só lado Python/servidor; browser/WebGL NÃO medido.
- **REV-02** `docs/arquitetura_app_atual.md` — inventário (5 abas, ~14 módulos, carga lazy por
  UF + render lazy de aba + fonte de mapa enxuta; caches sem TTL; grafo de dependências).
- **REV-03** `data/analysis/diagnostico_render_mapa.md` — gargalo do mapa = `deck.to_json()`
  (0,6–1,5 s; payload 21–24 MB; **~65% são as 14 strings de tooltip/hex**; ~1,21 KB/hex,
  linear em N). Opção MVT/deck.gl client-side = maior teto, mas reescrita de alto risco.
- **REV-04** `data/analysis/diagnostico_troca_cor.md` — troca de cor recompõe o builder inteiro;
  fix nº1 = `@st.cache_data` nos builders (só `fill_color` muda entre modos).
- **REV-05** `data/analysis/diagnostico_selecao_hex.md` — add/remove hex reconstrói o mapa
  (700–900 ms) por rerun; fix nº1 = `@st.fragment` no painel multi-hex.
- **REV-06** `data/analysis/diagnostico_pdf.md` — PDF Pontual: 77% do tempo = transformer pyproj
  criado por setor no loop (fix O1 = shared transformer, 86×); independente da escolha de stack.

## Escopo permitido
- Ler os 6 relatórios REV-01..06 + o inventário + o `docker-compose.prod.yml` (topologia).
- Pesquisa das 4 opções (características, prós/contras) e como cada uma se comporta nos
  critérios acima, ancorando os números nas evidências REV-01..06.
- Escrever UM relatório `data/analysis/avaliacao_stack.md` com: (i) resumo executivo;
  (ii) a **matriz de decisão** (4 opções × 7 critérios); (iii) o mapeamento do espectro
  incremental→cirúrgico→rebuild; (iv) **recomendação PRELIMINAR** fundamentada; (v) o que
  fica explicitamente para o REV-12 decidir; (vi) o que NÃO foi medido (browser/WebGL/paint,
  latência real de rede — herdar as caveats dos REV-01..05).
- Pode citar os spikes sucessores (REV-08 = spike deck.gl/MapLibre) como "a evidência empírica
  que confirmaria/refutaria o teto de (d)" — sem executá-los aqui.

## Fora de escopo
- **NÃO DECIDIR** rebuild vs refactor — é do BLK-REV-12 (gate humano + DEC).
- **NÃO implementar** nenhuma otimização nem protótipo (o spike de mapa client-side é o
  BLK-REV-08, manual/NÃO loop-safe; a implementação das otimizações são blocos sucessores).
- **NÃO re-litigar o requisito offline §2** nem re-medir performance (usar REV-01..06).
- **NÃO adicionar/remover opções** além das 4 listadas.
- **NÃO tocar** `src/`, `config.py`, `pipelines/m1/`, artefatos oficiais do M1, nem VPS/deploy/rede.
- Não expandir para outros blocos da epic REV (08..12).

## Arquivos que devem ser lidos
- `/repo/data/analysis/perf_baseline_app_2026.md` (REV-01)
- `/repo/docs/arquitetura_app_atual.md` (REV-02 — inventário; NÃO é `data/analysis/inventario_*`)
- `/repo/data/analysis/diagnostico_render_mapa.md` (REV-03)
- `/repo/data/analysis/diagnostico_troca_cor.md` (REV-04)
- `/repo/data/analysis/diagnostico_selecao_hex.md` (REV-05)
- `/repo/data/analysis/diagnostico_pdf.md` (REV-06)
- `/repo/docker-compose.prod.yml` (topologia real de produção — ponto de partida)
- `/repo/CLAUDE.md` §2/§4/§5 (guardrails offline e READ-ONLY M1)

## Arquivos que podem ser alterados
- `/repo/data/analysis/avaliacao_stack.md` (**CRIAR** — único entregável; gitignored via `data/analysis/`).
- `/repo/context/handoff.md` e snapshot em `/repo/context/handoff/` (fluxo da esteira).
- `/repo/tasks/current_task.md`, `/repo/tasks/backlog.md`, `/repo/tasks/completed.md` (housekeeping no fecho).
- NENHUM arquivo em `src/`, `config.py`, `pipelines/`, `data/outputs|staging` ou artefato M1.

## Critérios de aceite
- `data/analysis/avaliacao_stack.md` existe e está gitignored (`git check-ignore` confirma).
- Contém a **matriz de decisão completa**: as **4 opções (a,b,c,d) × 7 critérios**, preenchida.
- Cada célula/opção **ancora os números nas evidências REV-01..06** (payload 21–24 MB, tooltip
  65%, to_json 0,6–1,5 s, rerun 700–900 ms, PDF transformer 86×, etc.), não em achismo.
- Parte explicitamente da **topologia multi-container real** (não trata a produção como monólito)
  e afirma que `api`/Caddy/volumes já existem, reduzindo o custo de (b)/(d).
- Mapeia o **espectro incremental→cirúrgico→rebuild** e situa cada opção nele.
- Entrega **recomendação PRELIMINAR** clara e diz **explicitamente que a decisão é do REV-12**.
- Seção "o que NÃO foi medido" herdando as caveats de browser/WebGL/rede dos REV-01..05.
- READ-ONLY M1 verificável: `python scripts/loop_guard.py --base HEAD` → GUARD OK; `git diff
  HEAD -- src/motor_expansao/pipelines/m1/ src/motor_expansao/config.py` vazio.

## Criticidade classificada
**Estratégica** (embasa rebuild vs refactor; **READ-ONLY sobre o M1** — NÃO é Crítica porque
NÃO toca score_priorizacao/hex_score_estrutural/carteira/plano/artefatos oficiais; é
pesquisa/relatório que só LÊ). Marcada **loop-safe** no backlog.

## Esteira recomendada
Block Orchestrator (feito) → **Planner** → Builder → QA (autônoma no loop).

## Riscos identificados
- **Viés pró-status-quo ou pró-rebuild:** a matriz deve ser honesta nos DOIS sentidos —
  registrar que (a) tem teto real (rerun/to_json) E que (d)/(b) carregam risco de migração e
  custo de perfil de time (frontend JS/TS num time Python-only). Recomendação PRELIMINAR, não veredito.
- **Tratar a produção como monólito** (erro clássico): a produção é multi-container e a `api`/
  Caddy/volumes já existem — subestimar isso inflaria artificialmente o custo de (b)/(d).
- **Re-litigar o offline §2** (proibido) ou re-medir performance (desnecessário — usar REV-01..06).
- **Confundir o inventário REV-02:** ele está em `docs/arquitetura_app_atual.md`, NÃO em
  `data/analysis/inventario_arquitetural.md` (esse nome do prompt do orquestrador está errado).
- **O loop não enxerga a UI:** este bloco mede/pesquisa o lado Python/arquitetural; a validação
  empírica visual do teto de (d) é o BLK-REV-08 (manual). Anotar isso como limite honesto.
- **Ambiente do loop sem deps opcionais** (`contextily`/`matplotlib`/`openlocationcode`): 4
  falhas + 1 erro na suíte são AMBIENTAIS (herdado do QA do REV-06), NÃO regressão — não bloqueiam
  um bloco de pesquisa que não altera código.

## Guardrails ativos (de CLAUDE.md)
- **§5 guardrail permanente:** visualizações, análises e relatórios são **READ-ONLY sobre o M1** —
  NÃO recalculam `score_priorizacao`, `hex_score_estrutural`, carteira, plano nem artefatos oficiais.
  Pesos `renda=0.40`/`pop=0.60` e fórmula INALTERADOS.
- **§2:** dashboard/produção sem dependência de API ao vivo (offline sobre Parquets locais); a
  `api` lendo volumes locais NÃO viola isso (esclarecido no ponto de partida).
- **§6.1 loop-safe:** READ-ONLY M1; NÃO toca VPS/deploy/segredos; NÃO persiste PII; consome
  `data/staging`/`data/outputs` sem ingestão ao vivo; relatório em `data/analysis` (gitignored).
- **§6:** proibido executar comandos na VPS sem confirmação (não aplicável — bloco não toca VPS).
