# Backlog

## Priorização atual (2026-07-10)

Próximo ciclo recomendado: **epic BLK-PERF (quick wins de performance do dashboard)** — implementação
dos fixes já diagnosticados pelo épico BLK-REV (REV-01..07 concluídos, mergeados na main via PR #81).
Ordem: **BLK-PERF-01a** (loop-safe, PDF 86×) → **BLK-PERF-01b** (cache/fragment, manual) →
**BLK-PERF-01c** (tooltip enxuto, manual, decisão de produto). Em paralelo (humanos): BLK-REV-08 (spike
deck.gl, Juan) e BLK-REV-09 (UX, Vini) — insumos do gate BLK-REV-12. Ver seção "Epic BLK-PERF".

**Candidato ao loop autônomo (2026-07-10): `BLK-PERF-01a` — shared transformer no render censitário +
pré-filtro do municipal.** Único bloco novo **`loop-safe`** disponível: determinístico/headless
(saída byte-comparável + harness `scripts/perf_baseline_app.py` como instrumento de aceite), READ-ONLY
M1, sem VPS/rede/dependência nova. Sem dependências pendentes — pode ser pego pelo loop a qualquer
momento. Ver seção "Epic BLK-PERF".

**Trilha BLK-DIM — PONTO DE DECISÃO (2026-06-15):** a sub-trilha de "estressar o dado interno"
(DIM-07→08) está **concluída** e deu **três NO-GOs honestos** — a demanda/viabilidade NÃO é previsível
pela geografia de mercado que temos. O dimensionamento por m² (DIM-03R/06) é a parte que funciona, mas
consome demanda, não a produz. **Próximo passo = decisão de Felipe na bifurcação `BLK-DIM-10`**: Caminho A
(repaginar o motor para viabilidade/break-even, ROI imediato) e/ou Caminho B (BLK-DIM-DATA, a aposta de
buscar o sinal que falta). Recomendação: A agora + B como aposta. Ver BLK-DIM-10.

- **BLK-CENSO-01** (repaginação do relatório: camadas combinadas + fundo de ruas + faixas GeoFusion +
  pins com logo) — **concluído** em 2026-06-05 (FU1–FU5 deployados na VPS). Ver tasks/completed.md.
- Bugs de produção do dashboard (BLK-FIX-03..06) — todos **concluídos** em 2026-06-03.

> Blocos BLK-OPS-02/03/04, BLK-ARCH-01 e BLK-SCORE-01/02/03 originados do "Programa de
> Melhorias — Referência do Master Orchestrator" (PRD.md), migrados em 2026-05-29.
> Mapa de dependências e ordem recomendada do programa: ver §3 do PRD.md original.
> Ordem deste backlog: arquitetura (BLK-ARCH-01) à frente da trilha de score (BLK-SCORE-*).

---

## Bugs de produção do dashboard — TOPO DE PRIORIDADE (2026-06-01)

> Reportados por Felipe a partir do dashboard em produção (`dashboard.ultra-expansao.tech`).
> Cada bug é um bloco BLK-FIX próprio. Nenhum toca M1/score, **exceto BLK-FIX-06** (litoral),
> que altera a base de hexes do M1 e regenera artefatos oficiais → **Crítica + DEC**.
> Causas-raiz abaixo são **hipóteses** ancoradas no código (file:line) a confirmar pelo Planner.

- BLK-FIX-03 (concluído 2026-06-01) — ver tasks/completed.md

- BLK-FIX-03-FU1 (concluído 2026-06-01) — ver tasks/completed.md


---

- BLK-FIX-04 (concluído 2026-06-01) — ver tasks/completed.md


---

- BLK-FIX-05 (concluído 2026-06-01) — ver tasks/completed.md


---

- BLK-FIX-06 (concluído 2026-06-03) — ver tasks/completed.md

---

- BLK-FIX-06-C (concluído 2026-06-03) — ver tasks/completed.md



---

## Relatório Pontual Censitário — repaginação (2026-06-05, pedido de Felipe)

> Pedido de Felipe a partir do uso real do relatório (PDFs anexados: estudo GeoFusion de
> referência + exemplo do relatório atual com símbolos "esquisitos"). Objetivo: tornar o
> relatório pontual censitário **utilizável no dia a dia** — uma exportação só, com renda +
> população + concorrentes juntos, fundo de ruas, faixas de cor padronizadas e pins com logo.
> Execução **faseada**: BLK-CENSO-01 (função) e depois BLK-CENSO-02 (template/visual).
> Decisões de produto **já aprovadas por Felipe** em 2026-06-05 (ver cada bloco).
> READ-ONLY sobre M1: nenhuma das mudanças recalcula `score_priorizacao`, scores censitários,
> carteira, plano ou artefatos oficiais — é camada de visualização/relatório (§5 guardrail).

- BLK-CENSO-01 (concluído 2026-06-05) — ver tasks/completed.md


---

- BLK-CENSO-02 (concluído 2026-06-05) — ver tasks/completed.md


---

- BLK-CENSO-03 (concluído 2026-06-08) — ver tasks/completed.md


---

## Relatório Pontual Censitário — polimento de layout (2026-07-01, pedido de Vini)

> Pedido de Vinicius a partir do uso real do Relatório Pontual (variante **classico**, em produção
> via dashboard e API). Hoje os três mapas de calor censitários — **População/Densidade, Renda e
> Score** — ocupam **um slide cada** (páginas 2, 3 e 4 do PDF de 7 páginas). Objetivo: **consolidá-los
> em UM único slide**, lado a lado, **sem sobreposição** entre eles nem sobre o restante do conteúdo
> (faixa de título, rodapé, marca d'água). READ-ONLY sobre o M1 (§5 guardrail): nada recalcula score,
> intersecção de setores, raio de 1,5 km ou artefatos oficiais.

- BLK-RELPON-01 (concluído 2026-07-01) — ver tasks/completed.md


---

## Relatório Municipal — novo formato (2026-06-19, pedido de Vini)

> Novo formato de relatório que **coexiste** com o Relatório Pontual Censitário atual (que analisa
> uma região a partir do **raio de um ponto central**). O novo é um **relatório de município**:
> fica disponível para **geração e download após a seleção de um município** no dashboard. O escopo
> exato dos dados sai de um **template** que o Vini enviará e que será analisado como base, com
> ajustes ao longo do ciclo. Família do Relatório Censitário (malha real IBGE 2022), camada de
> visualização/relatório — **READ-ONLY sobre o M1** (§5 guardrail).

- BLK-RELMUN-01 (concluído 2026-06-22) — ver tasks/completed.md

- BLK-RELMUN-02 (concluído 2026-06-24) — ver tasks/completed.md

- BLK-RELMUN-03 (concluído 2026-07-02) — ver tasks/completed.md

- BLK-RELMUN-04 (concluído 2026-07-02) — ver tasks/completed.md



---

## Relatório Municipal — mapas com barra cinza (2026-07-01, pedido de Vini)

> Pedido de Vinicius a partir do uso real do Relatório Municipal: os mapas não preenchem todo o
> espaço disponível do painel, sobrando uma **barra cinza** (fundo do painel) acima/abaixo do mapa.
> Quer o mapa estendido para cobrir essa área cinza. Camada de visualização/relatório — **READ-ONLY
> sobre o M1** (§5 guardrail): nada recalcula score, gate do SAM, faixas ou artefatos oficiais.

- BLK-RELPON-03 (concluído 2026-07-01) — ver tasks/completed.md


---

## Trilha colaborador (Vini) — dashboard / PDF / UX (2026-06-09)

> Blocos derivados das tarefas pendentes do Vini (Vinícius, ClickUp id 101182135) na lista
> Motor de Expansão. Trilha de **visualização/relatório/UX**, executável em **paralelo** à trilha
> M1/infra/score do Felipe (arquivos quase disjuntos). Convenção: 1 bloco = 1 commit = 1 tarefa ClickUp.
> Fluxo: branch `ciclo/<ID>` → PR para `main` → CI verde → merge+deploy pelo Felipe
> (ver `docs/handoff_colaborador_run_cycle.md`).
> **READ-ONLY sobre o M1** em TODOS abaixo: nenhum recalcula `score_priorizacao`, pesos ou artefatos
> oficiais — é camada de visualização/relatório (§5 guardrail), **exceto BLK-FIX-08** (toca a camada
> PARALELA de mercado/residual, não o M1 oficial — ver o bloco).
> Causas-raiz são **hipóteses ancoradas no código** a confirmar pelo Planner.

- BLK-FIX-07 (concluído 2026-06-10) — ver tasks/completed.md


---

- BLK-FIX-08 (concluído 2026-06-10) — ver tasks/completed.md

- BLK-FIX-09 (concluído 2026-06-11) — ver tasks/completed.md


---

- BLK-FIX-10 (concluído 2026-06-12) — ver tasks/completed.md


---

- BLK-EST-03 (concluído 2026-06-15) — ver tasks/completed.md
- BLK-FIX-13 (concluído 2026-06-15) — ver tasks/completed.md
- BLK-EST-05 (concluído 2026-06-15) — ver tasks/completed.md


---

- BLK-FIX-07 (SUPERSEDED por BLK-FIX-13 em 2026-06-15) — o data-drift de `test_csvs_concorrentes_legiveis` foi resolvido pelo teste robusto a drift do BLK-FIX-13 (Vini); suíte verde confirmada no merge do PR #28 (3/3 passed). Ver tasks/completed.md (BLK-FIX-13).

---

- BLK-UI-01 (concluído 2026-06-16) — ver tasks/completed.md


---

- BLK-UI-07 (concluído 2026-06-19) — ver tasks/completed.md


---

- BLK-UI-09 (concluído 2026-06-19) — ver tasks/completed.md


---

## Novos blocos (2026-06-09, pedido de Felipe)

> Dois blocos derivados da análise de código com Felipe em 2026-06-09: (1) redefinição das condições
> do SAM (`BLK-SAM-01`) e (2) correção concreta dos overlays mortos do Mapa Territorial (`BLK-FIX-11`,
> Alternativa A). Ambos têm bloco "irmão" mais antigo/vago no backlog — ver a nota "Relacionado" em cada um.
> Causas-raiz abaixo estão **ancoradas no código** (file:line), confirmadas em leitura de 2026-06-09.

- BLK-SAM-01 (concluído 2026-06-10) — ver tasks/completed.md

- BLK-FIX-11 (concluído 2026-06-10) — ver tasks/completed.md

- BLK-SAM-02 (concluído 2026-06-10) — ver tasks/completed.md



---

## Projeto — API GeoEspacial (lista ClickUp `API GeoEspacial` / projeto `PROJETOS - DEG`)

> API complementar ao Motor de Expansão para integração com Telegram/WhatsApp, dando autonomia
> de estudos geoespaciais internos. Tarefa-pai ClickUp `86e1rtfcy`. Subtarefas: G1 (arquitetura/contrato,
> Felipe), G2 (backend/rotas, Juan), G3 (integração com o motor, Felipe+Juan), G4 (Telegram/WhatsApp, Juan).
> **Decisão de fonte (Felipe, 2026-06-09):** a API serve o relatório **on-demand a partir do motor**
> (importa `analisar_ponto_censitario_setores` + geradores de mapa/PDF e lê os Parquets locais de
> `data/outputs/setores_censitarios_2022_geo/`); **PostGIS fica como evolução futura, fora do MVP**.
> **Fronteira inegociável:** a API **importa, não edita** a camada `censo_*` (`censo_point.py`/`censo_map.py`/
> `censo_report.py`) — trata-os como interface estável, para não colidir com a trilha do Vini (dashboard/PDF).
> Código novo da API mora em `src/motor_expansao/api/` (pasta disjunta); dependências só no extra `[api]`
> do `pyproject.toml`, fora do deploy base do Streamlit. **READ-ONLY sobre o M1** (§5 guardrail): nada
> recalcula `score_priorizacao`, pesos, carteira, plano ou artefatos oficiais.

- BLK-API-01 (concluído 2026-06-10) — ver tasks/completed.md


- BLK-API-02 (concluído 2026-06-12) — ver tasks/completed.md


- BLK-API-03 (concluído 2026-06-12) — ver tasks/completed.md


- BLK-API-04 (concluído 2026-06-12) — ver tasks/completed.md


### BLK-API-05 — Endpoints estendidos M1/mercado (CONDICIONAL — roadmap pós-MVP)

| Campo | Valor |
|---|---|
| **Criticidade** | A definir (depende de reabrir a Decisão 3 para (b)) |
| **Status** | **Roadmap / condicional** — NÃO faz parte do MVP (Decisão 3 = (a)) |
| **ClickUp** | G3 (futuro) |

**Escopo (só se materializado):** `POST /lookup-hex` (lookup de hex M1) e/ou `GET /mercado/...` (camada
de mercado/residual), **READ-ONLY** (apenas leitura de artefatos; nada recalcula score/carteira/plano).
Permanece como roadmap até nova decisão de Felipe.

- BLK-API-06 (concluído 2026-06-12) — ver tasks/completed.md


- BLK-API-07 (concluído 2026-06-12) — ver tasks/completed.md


---

- BLK-API-08 (concluído 2026-06-12) — ver tasks/completed.md



---

- BLK-EST-04 (concluído 2026-06-12) — ver tasks/completed.md


---

## Tarefas pendentes

- BLK-OPS-06 (concluído 2026-05-29) — ver tasks/completed.md
- BLK-OPS-07 (concluído 2026-05-29) — ver tasks/completed.md
- BLK-PRD-01 (concluído 2026-05-29) — ver tasks/completed.md
- BLK-OPS-02 (concluído 2026-05-29) — ver tasks/completed.md
- BLK-OPS-02b (concluído 2026-05-29) — ver tasks/completed.md
- BLK-OPS-08 (concluído 2026-05-29) — ver tasks/completed.md

---

- BLK-OPS-03 (concluído 2026-05-30) — ver tasks/completed.md


---

- BLK-OPS-04 (concluído 2026-05-30) — ver tasks/completed.md



- BLK-FIX-01 (concluído 2026-05-30) — ver tasks/completed.md



- BLK-FIX-02 (concluído 2026-05-30) — ver tasks/completed.md


---

- BLK-SCORE-01 (concluído 2026-05-31) — ver tasks/completed.md


---

- BLK-SCORE-01a (concluído 2026-05-31) — ver tasks/completed.md


---

- BLK-SCORE-02 (concluído 2026-05-31) — ver tasks/completed.md


---

- BLK-SCORE-03 (concluído 2026-05-31) — ver tasks/completed.md


---

- BLK-SCORE-04 (concluído 2026-05-31) — ver tasks/completed.md


---

### BLK-SCORE-05 — Viabilidade de proxy exógeno de demanda (pré-requisito de modelagem)

| Campo | Valor |
|---|---|
| **Status** | **SUPERSEDED por BLK-DIM-00..04 em 2026-06-12** |

**Supersessão (2026-06-12, decisão de Felipe).** O SCORE-05 era um diagnóstico read-only de
"existe proxy exógeno de demanda + maturação para tentar modelar?". Essa pergunta é exatamente a
**Camada 1 (aderência/penetração calibrada)** do novo `modelo_dimensionamento_expansao.md` (CEO),
que a subsume e melhora: em vez de só diagnosticar, calibra com validação honesta (LOO-CV vs
baseline) e entrega um motor inverso de 4 camadas (Potencial → Captura → Dimensionamento m² →
Viabilidade financeira). A **disciplina de GO/NO-GO honesto** e os bloqueios estruturais
(viés de seleção, alvo pós-maturação, sinal exógeno ≈ nulo) do SCORE-05 foram DOBRADOS no
**BLK-DIM-01**. Camada paralela, **READ-ONLY sobre o M1** — DEC-001 (não recalibrar `score_priorizacao`)
permanece intacta. Detalhe e decomposição abaixo (epic BLK-DIM).

---

## Epic BLK-DIM — Motor de Dimensionamento e Viabilidade de Unidades (camada paralela)

> **Origem:** `modelo_dimensionamento_expansao.md` (raiz do repo; spec/handoff do CEO, 2026-06-10),
> derivado dos testes do projeto externo `Análise Preditiva` (base de 54 academias). Substitui o
> BLK-SCORE-05.
>
> **Tese:** inverter a lógica — partir do potencial de mercado de cada região → dimensionar o imóvel
> ideal (m²/vagas) → fechar a conta financeira (faturamento, aluguel-teto, margem, payback, ROIC).
> 4 camadas: **1. Potencial** (hex → alunos potenciais via aderência calibrada) · **2. Captura**
> (market share via Huff/gravitacional) · **3. Dimensionamento** (alunos-alvo → m² pela curva de
> densidade) · **4. Unit economics** (determinística). As camadas 3-4 são prototipáveis JÁ; 1-2 são
> o coração e dependem de calibração nas unidades maduras.
>
> **Guardrail do epic (todos os blocos):** camada PARALELA, **READ-ONLY sobre o M1** — não toca
> `score_priorizacao`/`hex_score_estrutural`/pesos/artefatos oficiais (DEC-001 vigente). Não cria
> dependência de API ao vivo no dashboard de produção. Sem PII (`nome_unidade`) em relatórios.
>
> **Metodologia não-negociável (todos os blocos de modelagem — §7 do spec):** métrica oficial =
> **LOO-CV ou k-fold repetido SEMPRE contra baseline da média**; BANIR R² in-sample e
> `fit(X,y)→predict(X)`; começar simples (linear regularizado/GLM), só subir complexidade se ganhar
> honestamente sobre o baseline; toda saída com **intervalo de predição + flag de extrapolação**.
>
> **Sequenciamento recomendado:** **DIM-03 primeiro** (determinístico, usa só dados que já temos,
> valor imediato e desacoplado) → DIM-00 → DIM-01 (gate GO/NO-GO) → DIM-02 → DIM-04. Camadas 1-2 só
> avançam se as lacunas de dados fecharem em DIM-00.
>
> **Insumos — auditoria de 2026-06-12 (estado real do repo):**
> - ✅ EXISTE: 54 unidades Ultra com faturamento/pagantes/alunos/**metragem m²**/ticket/alunos-por-m²
>   (`data/staging/unidades_ultra_performance_hex.parquet`, 57 cols); concorrência OSM 3.296 unidades
>   ~35 redes com lat/lng (`data/staging/concorrentes_mapeados.parquet`); camada de mercado/residual
>   (`hexagonos_mercado_mapeado.parquet`, 135 cols); helper de catchment `analisar_entorno_ponto`
>   (1,5 km); backtest helpers (`analysis/score_backtest.py`, `feature_backtest_mercado.py`).
> - ❌ FALTA no repo (Felipe vai disponibilizar — 2026-06-12): **série diária das ~60 maduras**
>   (vendas/cancelamentos/churn/rampa de maturação); **datas de abertura por unidade**
>   (`maturacao_status` é constante `maturacao_indisponivel` em 100% hoje — gate G1 da DEC-001 segue
>   aberto); **`ULTRA padrão - Simulador Financeiro.xlsx`**; `modelo_demanda.py`/`teste_densidade.py`
>   (referência portável). m²/capacidade real de concorrentes (hoje só proxy 2.500 alunos).

---

- BLK-DIM-00 (concluído 2026-06-13) — ver tasks/completed.md


---

> **Spikes BLK-DIM-01..04** (1ª rodada do loop, 2026-06-13): **auditados e SUPERSEDED**, mantidos
> como referência nos branches `ciclo/BLK-DIM-01..04` (não mergeados — ver BLK-LOOP-02). Detalhe e
> motivo de cada um em `tasks/completed.md`.
>
> - BLK-DIM-01 → superseded por **BLK-DIM-01R** (R²=0.897 era artefato de fixture).
> - BLK-DIM-02 → superseded por **BLK-DIM-02R** (fallback previsor=alvo, vazamento).
> - BLK-DIM-03 → superseded por **BLK-DIM-03R** (números mágicos calibrados ao teste).
> - BLK-DIM-04 → superseded por **BLK-DIM-06** (backtest in-sample disfarçado).

---

- BLK-DIM-01R (concluído 2026-06-13) — ver tasks/completed.md


---

- BLK-DIM-05 (concluído 2026-06-13) — ver tasks/completed.md


---

- BLK-DIM-06 (concluído 2026-06-13) — ver tasks/completed.md



---

- BLK-DIM-07 (concluído 2026-06-15) — ver tasks/completed.md
- BLK-DIM-08 (concluído 2026-06-15) — ver tasks/completed.md
- BLK-DIM-02R (concluído 2026-06-15) — ver tasks/completed.md



---

### BLK-DIM-10 — Bifurcação estratégica da epic: demanda não é previsível pela geografia de mercado (decisão de Felipe)

| Campo | Valor |
|---|---|
| **Criticidade** | **Estratégica** (define o rumo da epic BLK-DIM; READ-ONLY sobre M1) |
| **Esteira** | `[DECISÃO HUMANA — Felipe]` — NÃO loop-safe (escolha de produto/rota) |
| **Status** | **RESOLVIDO pela evidência (2026-06-15)** — registro de decisão; não é mais trabalho aberto |
| **Origem** | síntese dos resultados DIM-01R / DIM-05 / DIM-08 / DIM-02R + spike de densidade (2026-06-15) |

> **RESOLUÇÃO (2026-06-15):** o spike de densidade (`data/analysis/densidade_contexto.md`) fechou a
> dúvida — a geografia **também** não prevê a densidade (alunos/m²) (4º NO-GO; R²_LOO −0,01), e o único
> sinal usável é a **curva tamanho→densidade** (metragem, R²_LOO +0,10). A base geográfica interna está
> **esgotada**. Decisão tomada: **Caminho A vira o rumo agora** → materializado no **BLK-DIM-11** (esteira
> property-first / viabilidade). **Caminho B (BLK-DIM-DATA) é REDEFINIDO**: só faz sentido atrás de
> **atributos de imóvel** (visibilidade, fluxo, esquina) — NÃO de mais dado demográfico, que 4 NO-GOs já
> provaram não carregar sinal. **Formalizado como DEC-009** (CLAUDE.md §8, aprovada por Felipe em
> 2026-06-15). Este bloco fica como **registro de decisão** (não loop-safe, não é tarefa); a execução
> é o BLK-DIM-11 (engine, concluído) + BLK-DIM-12 (UI).

**Onde chegamos (evidência):** depois de **estressar ao máximo o dado interno** (sub-trilha DIM-07→08 + spike de densidade),
temos **três NO-GOs honestos** convergindo: a demanda/viabilidade de um ponto **NÃO é previsível a partir
da geografia de mercado** que temos (pop, renda, concorrência, residual), em raio nenhum, com feature
nenhuma disponível.

| Camada | Veredito |
|---|---|
| 1 — Potencial (pop+renda, DIM-01R) | NO-GO (R²_LOO −0,01) |
| 1 — + features exógenas (DIM-05) | NO-GO |
| 1 — residual discrimina viabilidade? (DIM-08) | **NO-GO (AUC 0,48 ≈ acaso)** |
| 2 — Captura/Huff (DIM-02R) | GO técnico, mas não agrega (LOO −0,25) |
| 3+4 — Dimensionamento m² + DRE (DIM-03R/06) | **GO** (R²=+0,23, bate baseline) |

A metade que **funciona** é o dimensionamento por m² — mas ele **consome** demanda como entrada, não a
produz. O sinal que separa uma Carapicuíba (1.299) de uma vencedora (6.251) está provavelmente em
**execução/operação, micro-localização ou variáveis demográficas que faltam** (idade 18-45, vínculo CLT),
não na geografia agregada.

**A bifurcação (escolher o rumo):**

- **Caminho A — Repaginar o motor para VIABILIDADE / BREAK-EVEN (ROI imediato, usa o que funciona):**
  inverter a pergunta de *"quantos alunos este ponto terá?"* (sem resposta) para *"quantos alunos este
  imóvel **precisa** para ser viável, e isso é plausível aqui?"*. Usa o goal-seek que o DIM-03R já tem
  (alunos mínimos viáveis, aluguel-teto). A demanda entra como **premissa explícita** (input humano ou
  faixa de comparáveis), nunca como previsão cravada. Entregável sem dado novo. → viraria um bloco
  sucessor (ex.: BLK-DIM-11).
- **Caminho B — BLK-DIM-DATA (a aposta):** buscar o sinal que falta (microdados IBGE idade 18-45 / CLT, ou
  proxy Gympass/Wellhub) e re-rodar a calibração. É o único caminho que poderia **restaurar previsão de
  verdade** — mas pode dar NO-GO de novo (§5/DEC-001 avisaram que o sinal pode ser intrinsecamente fraco).
  Bloco já existe (BLK-DIM-DATA), manual/não loop-safe.

**Cautela registrada:** o método de **comparáveis/análogos** NÃO é um atalho — o DIM-08 mostrou que os
eixos atuais (pop/renda/concorrência) não separam viável de inviável, então "pontos parecidos" nesses
eixos teriam resultados igualmente dispersos. Só ajudaria com eixos novos (tipo de cidade, visibilidade,
imóvel) — o que recai na questão de dado (Caminho B).

**Recomendação (Claude):** fazer os dois em ordem — **A agora** (entrega valor sem dado novo e repaginia o
papel do motor de "prever alunos" para "stress-testar viabilidade") e **B como aposta** (o teste honesto de
"é dado ou é intrínseco?"). Se B vier NO-GO, encerra-se a questão com evidência e fica-se com o motor de
viabilidade — que já é valioso.

**Guardrail:** READ-ONLY sobre o M1 (DEC-001/DEC-008) em qualquer caminho; a priorização de **onde** olhar
segue com o M1/censitário (camada executiva, intacta) — o que se perde é só a contagem fina de alunos por
ponto, não a triagem regional. Após a escolha de Felipe, formalizar como **DEC-009** (CLAUDE.md §8).

---

- BLK-DIM-11 (concluído 2026-06-15) — ver tasks/completed.md


---

- BLK-DIM-12 (concluído 2026-06-15) — ver tasks/completed.md


---

- BLK-DIM-13 (concluído 2026-06-17) — ver tasks/completed.md


---

- BLK-DIM-14 (concluído 2026-06-17) — ver tasks/completed.md


---

- BLK-DIM-16 (concluído 2026-06-17) — ver tasks/completed.md


---

### BLK-DIM-09 — Crosswalk manual das unidades não-casadas (CONDICIONAL — só se o match do 07 deixar lacuna material)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (recupera N perdido no join; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Depende de** | **BLK-DIM-07** (lista de não-casadas + taxa de match) |
| **Status** | Pendente (condicional — só dispara se o match automático do 07 ficar abaixo do aceitável) |
| **Autonomia** | **manual (NÃO loop-safe)** — resolver nomes ambíguos (várias unidades por cidade, nome interno vs. cidade) exige julgamento humano; NÃO marcar loop-safe. |

**Contexto:** o geocoding online deixou de ser necessário — SkyFit (`concorrentes/Unidades/unidades_skyfit.csv`,
481 coords) e Engenharia (`.../unidades_engenharia_do_corpo.csv`, 62 coords) **já têm lat/lng locais**. O
problema real não é coordenada, é o **join por nome**: match exato normalizado = **0%** (convenções
divergentes — ver caveat do BLK-DIM-07). O 07 resolve o grosso por chave cidade+UF (SkyFit) e crosswalk
fuzzy (Engenharia); este bloco só existe para a **cauda de unidades ambíguas** que sobrar (ex.: várias
SkyFit na mesma cidade; nome interno da Engenharia sem cidade explícita).

**Objetivo:** se a taxa de match automático do 07 ficar abaixo do aceitável, construir um **crosswalk
revisado por humano** (`unidade_alunos ↔ unidade_coords`) para as não-casadas, anexar à base multi-rede e
**re-rodar o BLK-DIM-08** com N recuperado, reportando o ganho/perda honesto.

**Escopo permitido (só se acionado):** crosswalk manual auditável (CSV de-para versionável SEM PII —
só identificadores de unidade); reanexar à base; re-rodar discriminação/variância; reportar quantas
unidades foram recuperadas e o impacto no veredito.

**Fora de escopo (invioláveis):** geocoding online (desnecessário); persistir PII/endereço bruto;
score/pesos/artefatos M1; dependência de API ao vivo no dashboard; "casar por centroide de cidade" quando
há várias unidades na mesma cidade (ambiguidade tem que ser resolvida, não chutada).

**Critérios de aceite:** crosswalk revisado e auditável; nº de unidades recuperadas reportado;
BLK-DIM-08 re-rodado com veredito honesto de ganho/perda; ZERO PII em disco; ZERO M1.

**Risco:** baixo (trabalho manual pequeno). Pode concluir que a cauda não-casada é imaterial → a sub-trilha
encerra com o N do 07 (resultado válido).

---

### BLK-DIM-DATA — Aquisição de dado para destravar a Camada 1 (demanda) — o gargalo real

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (engenharia de dados pesada/aquisição externa; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA OBRIGATÓRIA]` → Builder → QA |
| **Depende de** | **BLK-DIM-01R** (estabeleceu o NO-GO e a estrutura de calibração) |
| **Status** | Pendente |
| **Autonomia** | **manual (NÃO loop-safe)** — downloads grandes/fontes externas; NÃO se limita a `data/staging`; exige gate humano. NÃO marcar loop-safe. |

**Contexto / por que existe:** o BLK-DIM-01R provou, com dado real (n=53, alvo `log(pagantes)` absoluto,
LOO honesto), que a demanda **NÃO é calibrável** com pop+renda (`R²_LOO=−0,013`, NO-GO) e o BLK-DIM-05
mostrou que as features disponíveis no Censo 2022 **Básico** não ajudam. As features que decidiriam a
demanda (**faixa etária 18-45**, vínculo formal/CLT, % ocupados) **não existem no Censo Básico por
setor** — exigem microdados/amostra do IBGE (~10 GB) ou um proxy exógeno. **O gargalo é DADO, não
algoritmo** (exatamente o que a DEC-001 e o §5 do spec avisaram). Este bloco ataca o gargalo.

**Objetivo:** avaliar (viabilidade/custo/legalidade) e, se viável, **materializar** ao menos um sinal
novo que possa virar a Camada 1 de NO-GO → GO, e **re-rodar a calibração do BLK-DIM-01R** com ele,
reportando honestamente se o `R²_LOO` melhora materialmente.

**Escopo permitido (candidatos — diagnosticar antes de baixar tudo):**
- **Microdados/amostra Censo 2022 IBGE**: faixa etária 18-45, vínculo formal, renda do trabalho por
  setor/área de ponderação. Avaliar cobertura, granularidade (área de ponderação ≠ setor), tamanho e
  licença antes de baixar. Materializar features por catchment (reuso do helper censitário).
- **Proxy exógeno de demanda**: penetração Wellhub/Gympass (já há `sinal_wellhub`/`n_parcerias_wellhub`
  no dataset de validação) — medir cobertura e se é exógeno ou colado a unidades existentes.
- **Reduzir viés de seleção**: a rede já tem ~88 unidades na Growth API (vs 53 maduras) — incorporar
  mais unidades (incl. em rampa, com `inauguracao`) para ampliar N e a variação de contexto.
- Re-rodar `aderencia.py` (BLK-DIM-01R) com a(s) feature(s) nova(s); LOO-CV vs baseline; veredito.

**Fora de escopo (invioláveis):** score/pesos/artefatos M1 (READ-ONLY; DEC-001); dependência de API ao
vivo no dashboard; persistir PII (microdados podem ter PII — agregar na borda, nunca em disco);
inventar feature sem fonte auditável; alterar o método/raio censitário.

**Critérios de aceite:** diagnóstico de disponibilidade/custo/legalidade das fontes; se houver fonte
viável, feature materializada por catchment + re-calibração honesta com veredito GO/NO-GO documentado
(IC/N/confounds); ZERO PII em disco; ZERO escrita em M1; reprodutível.

**Risco:** médio-alto de esforço (download/limpeza de microdados é pesado). O resultado pode seguir
NO-GO — e isso encerra honestamente a questão "dá para modelar demanda por hex hoje?". **Não loop-safe:
exige decisão humana sobre quais fontes baixar e validação de licença/LGPD.**

---

- BLK-DIM-17 (concluído 2026-06-22) — ver tasks/completed.md


---

- BLK-DIM-18 (concluído 2026-07-01) — ver tasks/completed.md



---

### BLK-SEC-03 — Hardening do VPS: fechar SSH por senha, fail2ban e 2FA (re-escopado 2026-07-13)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (exposição do servidor de produção) |
| **Prioridade** | **Alta** (subiu 2026-07-13: SSH root+senha aberto à internet é o maior risco atual) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Origem** | revisão de robustez 2026-05-31; **re-escopado por inventário read-only da VPS em 2026-07-13** |
| **Autonomia** | **manual (NÃO loop-safe)** — cada comando na VPS exige confirmação individual (§6) |

**Inventário real (2026-07-13, read-only na VPS):** parte do bloco original JÁ ESTÁ FEITA —
`ufw` **ATIVO** liberando só 22/80/443 (v4+v6); `unattended-upgrades` **INSTALADO** (falta confirmar a
config periódica ativa); rotação de log do Docker já configurada (`daemon.json`, 10m×3 — era escopo do
SEC-05). **Gaps reais que restam:** `sshd` com `passwordauthentication yes` + `permitrootlogin yes`
(**root por SENHA aberto à internet — o maior risco do servidor hoje**); `fail2ban` **INATIVO**
(brute-force de senha nem é banido); 2FA do Authelia opcional; revisão de acesso do `ultra_team` nunca
feita; deploy key `gymscraping_deploy` em `/root/.ssh/` (auditar que segue read-only no repo do scraper).

**Objetivo:** fechar os gaps restantes sem quebrar deploy, coleta semanal nem o acesso do time.

**Escopo re-priorizado (cada passo via MCP com confirmação individual — §6):**
1. **P1 — SSH sem senha:** `PasswordAuthentication no` + `PermitRootLogin prohibit-password` (o acesso
   real já é por chave). ANTES de aplicar: validar console web da Hostinger como porta dos fundos e
   manter uma 2ª sessão SSH aberta durante a mudança.
2. **P2 — `fail2ban` ativo** no sshd (jail default; banir brute-force).
3. **P3 — confirmar `unattended-upgrades`** aplicando patches de segurança (APT::Periodic + dry-run).
4. **P4 — Authelia:** avaliar forçar 2FA no grupo `ultra_team` + revisão de acesso em
   `authelia/users_database.yml` (remover obsoletos; definir offboarding e periodicidade da revisão).
5. Documentar em `docs/infra_producao.md` (seção hardening) com rollback de cada item.

**Fora de escopo:** trocar provedor/arquitetura; mudar M1/dashboard; superfície de rede dos containers
(API/bot não publicam porta no host — já correto); ufw (já feito).

**Critérios de aceite:**
- Login por senha REJEITADO (teste real de fora) e login por chave OK; fail2ban banindo (teste).
- unattended-upgrades comprovadamente aplicando security patches.
- Dashboard, deploy, API/bot e coleta semanal seguem funcionando após cada mudança.
- Cada alteração com confirmação individual; documentada com rollback.

**Risco:** médio-alto (lockout de SSH). Mitigação: um item por vez, 2ª sessão aberta, console web da
Hostinger validado ANTES do P1, rollback documentado antes de cada passo.

---

### BLK-SEC-04 — Backup automatizado dos dados de produção + restore testado (re-escopado 2026-07-13)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (continuidade de dados; não toca M1/score) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → `[DECISÃO HUMANA: destino/custo]` → Builder → QA |
| **Status** | Pendente — **bloqueado por 1 decisão de Felipe: o DESTINO do backup** |
| **Origem** | revisão de robustez 2026-05-31 (BLK-OPS-01 cobre segredos, não dados) |
| **Autonomia** | **manual (NÃO loop-safe)** — VPS + decisão de custo |

**Gap (confirmado no inventário 2026-07-13):** continua NÃO existindo backup dos dados de produção —
só a cópia manual na máquina de dev. Disco da VPS folgado (34G/194G usados), mas backup no MESMO disco
não é DR (perde-se junto).

**Decisão que trava o bloco (Felipe):** o destino — (a) **snapshot/backup nativo da Hostinger** (mais
simples, custo do plano, restore do disco inteiro), (b) **bucket S3-compatível** via rclone/restic
(custo baixo/mês, restore granular por arquivo), ou (c) **cópia agendada off-box** para máquina do time
(custo zero, depende da máquina estar ligada). Definido o destino, o resto é execução de 1 sessão.

**Escopo (ordem de prioridade do que copiar):**
1. `/opt/motor-expansao/data/outputs/` (~1,6 GB, parquets servidos ao dashboard) — crítico.
2. `data/ibge/` (~49 MB) + `data/staging/` (~213 MB) — obrigatórios para a API (sem `data/ibge` a API
   dá 500); regeneráveis, mas o re-scp é lento.
3. Volume `bot_data` (sessões do bot Telegram) — trivial; perder = usuários deslogados.
4. `/opt/gymscraping-infra/` (runner + **relatórios de crescimento históricos** — pequenos e NÃO
   regeneráveis: são a série temporal da concorrência; DEC-013). Os dados coletados em si são
   regeneráveis pela coleta semanal (baixa prioridade).
5. NÃO versionar parquet no git; NÃO copiar `NAO_ABRA/`/PII para o destino.

**Mecânica:** job cron na janela 2h–5h BRT (não colidir com a coleta de domingo 06:00 UTC); retenção
diários 7d / semanais 4w; checksum; **restore testado em pasta limpa** (rigor do BLK-OPS-01) + runbook
em `docs/`.

**Cruzamento com BLK-OPS-01 (segredos):** o `.env` ganhou segredos novos desde o backup original
(`API_TOKENS`/`API_API_CALL_TOKEN`/`API_TELEGRAM_TOKEN`/`API_BOT_SENHA`/`API_IMAGE`) → **re-encriptar o
`.env` no SOPS+age como passo deste ciclo** (atualização do OPS-01, não processo novo).

**Critérios de aceite:** backup automático com retenção; checksums conferem; restore validado
end-to-end e documentado; `.env` re-encriptado; zero PII no destino.

**Risco:** baixo. Atenção ao custo do destino e à janela noturna.

---

- BLK-SEC-05 (concluído 2026-07-13) — ver tasks/completed.md



---

### BLK-ORQ-02 — Implementar estrutura Fase 2

Status: pendente (depende de BLK-ORQ-01 validado)
Criticidade: alta
Prioridade: média
Tipo: estrutura
Skill recomendada: /run-cycle
Resumo: Criar DECISIONS.md com migração das decisões do CLAUDE.md (DEC-001 a DEC-003),
context/active_context.md, tasks/blocked.md e 5 prompts adicionais
(master_orchestrator, approver, documenter, data_agent, metrics_agent).
Dependências: BLK-ORQ-01
Observações: CLAUDE.md não deve ser reescrito, apenas estendido com seção ## Skills.

---

- BLK-PROD-03 (concluído 2026-07-07) — ver tasks/completed.md



---

### BLK-PROD-01 — Refatoração completa do repositório

Status: pendente
Criticidade: estratégica
Prioridade: média
Tipo: refatoração
Skill recomendada: /run-cycle (fluxo estratégico)
Resumo: Migrado do PRD.md. Próxima etapa de planejamento estrutural do repositório.
Dependências: nenhuma bloqueadora
Observações: requer planejamento detalhado antes de execução. Não iniciar sem aprovação.

---

### BLK-PROD-05 — Geocodificação offline/online de endereço

Status: pendente
Criticidade: alta
Prioridade: baixa
Tipo: feature
Skill recomendada: /run-cycle
Resumo: Implementar geocodificação de endereço apenas se dependência externa for
aprovada ou base local viável identificada.
Dependências: aprovação de dependência externa ou base local.

---

- BLK-PROD-06 (concluído 2026-07-07) — ver tasks/completed.md


---

### BLK-PROD-07 — Cenários salvos por usuário e histórico de decisão

Status: pendente
Criticidade: alta
Prioridade: baixa
Tipo: feature
Skill recomendada: /run-cycle
Resumo: Apenas se o dashboard evoluir para produto web interno com múltiplos usuários.
Dependências: decisão de produto sobre evolução para web interno.

---

## Epic BLK-VIAB — Integração de Viabilidade de Imóvel Candidato (imóvel-first; camada paralela READ-ONLY sobre o M1)

> Continuidade da **DEC-009** (property-first) e do motor `dimensionamento/viabilidade_ponto.py` (BLK-DIM-11 concluído).
> Costura o produto completo: **imóvel real → curva m²→alunos → DRE → margem de segurança (aluguel-teto vs pedido)**,
> com a **demanda SEMPRE como premissa explícita** (NUNCA prevista pela geografia — DEC-009). A triagem demográfica
> entra só como CONTEXTO do catchment, não como pré-filtro.
> **READ-ONLY sobre o M1 em TODOS os blocos** (§5): nenhum recalcula `score_priorizacao`/pesos/carteira/plano/artefatos
> oficiais. Saídas em `data/staging/` (paralela, gitignored) + `data/analysis/` (gitignored).
> **Achado 2026-07-07 embutido nos guardrails:** o alvo de demanda honesto é **alunos_totais reais** (Ultra+Smart+Eng+Sky),
> NÃO `membros` (agregador corporativo, ~1/3 da demanda, e circular com o Huff). Ver memória
> `huff-membros-circularidade-teto-demanda`.
> **NÃO entram nesta epic loop-safe (blocos HUMANOS separados):** geocoding ao vivo dos endereços (rede — DEC-010),
> a tela do operador no dashboard (UI — lição do BLK-UI-10), e a materialização do ranking como artefato de comitê
> (DEC + gate, padrão BLK-ATR-05).

- BLK-VIAB-01 (concluído 2026-07-07) — ver tasks/completed.md


---

- BLK-VIAB-02 (concluído 2026-07-07) — ver tasks/completed.md


---

- BLK-VIAB-03 (concluído 2026-07-07) — ver tasks/completed.md


---

- BLK-VIAB-04 (concluído 2026-07-07) — ver tasks/completed.md


---

- BLK-VIAB-05 (concluído 2026-07-08) — ver tasks/completed.md

> **Roadmap de produto (síntese 2026-07-08, `docs/estado_dos_modelos.md`).** Os blocos abaixo
> operacionalizam o produto property-first. Ordem de valor: **VIAB-09 (UI end-to-end)** é o de maior
> impacto; VIAB-06/07 são loop-safe (guardrail + alavanca de precisão); VIAB-08/10 são humanos
> (rede/dado externo). READ-ONLY sobre o M1 em todos.

- BLK-VIAB-06 (concluído 2026-07-08) — ver tasks/completed.md


---

- BLK-VIAB-07 (concluído 2026-07-08) — ver tasks/completed.md


---

### BLK-VIAB-08 — Geocoding + catchment dos imóveis candidatos

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (rede ao vivo — precedente DEC-010; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — rede/anti-PII]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-VIAB-01** (candidatos limpos com `flag_sem_coord`). |
| **Autonomia** | **manual (NÃO loop-safe)** — geocoding é rede ao vivo (DEC-010/Nominatim); loop não faz ingestão ao vivo; exige gate humano. NÃO marcar loop-safe. |

**Contexto.** Os 23 candidatos limpos (BLK-VIAB-01) estão **100% sem coordenada**; o catchment do motor
(pop/renda do entorno, flag de zona-morta) só roda com `lat/lng` (hoje o batch VIAB-03 roda coordless).

**Objetivo.** Geocodificar os endereços (reusando `maps_geocoder`/Nominatim, DEC-010: cache local, fallback,
anti-PII) e ligar o `setores_df` (catchment) no batch de viabilidade, ativando pop/renda do entorno + zona-morta.

**Guardrail.** DEC-010 (cache `data/cache/geocode/`, fallback offline gracioso, timeout, anti-PII); §5 READ-ONLY M1.

---

### BLK-VIAB-09 — UI de Viabilidade de Imóvel no dashboard (produto end-to-end)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (superfície do produto property-first; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini) — **maior impacto do roadmap**. |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — UX/visual]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-VIAB-03** (batch/ranking) + **BLK-VIAB-06** (guardrail de envelope). BLK-VIAB-08 (catchment) opcional/aditivo. |
| **Autonomia** | **manual (NÃO loop-safe)** — UI exige revisão visual humana (lição do BLK-UI-10: loop marca verde por teste, mas UX precisa de olho). NÃO marcar loop-safe. |

**Contexto.** Motor (`viabilidade_ponto`), batch e ranking por margem de segurança já existem e estão validados
(BLK-VIAB-03/04). Falta a **tela do operador** — o "produto completo" property-first da DEC-009.

**Objetivo.** Aba/seção no dashboard onde o operador traz um imóvel (m² + aluguel + endereço) — ou seleciona da
base — e recebe: faixa de alunos (p10/p50/p90), break-even, **aluguel-teto vs pedido (margem de segurança)**,
grade de sensibilidade demanda×aluguel, e o **aviso de envelope** (BLK-VIAB-06). Demanda SÓ como premissa (DEC-009).

**Guardrail.** §5 READ-ONLY M1 (visualização não recalcula score/carteira/plano/artefatos); usa faixas, não pontos.

> **RE-ESCOPO (2026-07-10, varredura de código — aprovado por Felipe):** a tela do operador **JÁ EXISTE**
> (`render_viabilidade_ponto`, `pages.py:3572`, aba "Viabilidade" — entregue nos BLK-DIM-12..16): faixa
> p10/p50/p90, break-even, aluguel-teto vs pedido, grade de sensibilidade, contexto de catchment/zona-morta,
> projeção 60 meses e export Excel já renderizam. **Escopo restante deste bloco:** (i) exibir o aviso de
> extrapolação quando `resultado.flag_fora_envelope` (BLK-VIAB-06 — hoje a UI NÃO lê a flag; zero matches
> de "envelope" em `dashboard/`); (ii) expor o param opcional `formato` (BLK-VIAB-07, GO −9,1 p.p. MAPE)
> na chamada de `pages.py:3750-3764` (selectbox opcional, default None = comportamento atual);
> (iii) OPCIONAL: seletor "carregar candidato da base" lendo `imoveis_candidatos_limpos.parquet`;
> (iv) testes de integração da tela (hoje zero). **Complexidade revista: Baixa** (Média só se incluir iii).

---

### BLK-VIAB-10 — Aquisição de metragem externa para ampliar a curva

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (destrava a melhoria da curva; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[GATE HUMANO — aquisição/licença de dado]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | — (relacionado a **BLK-DIM-DATA**; e ao NO-GO do **BLK-VIAB-05**). |
| **Autonomia** | **manual (NÃO loop-safe)** — aquisição de dado externo (fora de `data/staging`); exige gate humano. NÃO marcar loop-safe. |

**Contexto.** A curva de densidade só tem **112 unidades com metragem** (Ultra 54 + Eng Corpo 58). Smart Fit e
Sky Fit têm alunos totais mas **nenhuma coluna de metragem** — por isso o BLK-VIAB-05 bloqueou. O gargalo para
melhorar a curva é **metragem por unidade**, não alunos.

**Objetivo.** Adquirir metragem por unidade de mais redes low-cost (fonte externa a disponibilizar) para ampliar
a base de calibração DENTRO do formato Ultra, e revalidar a curva (reabre BLK-VIAB-05 sob DEC-008).

**Guardrail.** §5 READ-ONLY M1; procedência/licença do dado no gate humano.

---

## Epic BLK-REV — Revisão séria do app: pesquisa e planejamento (Desempenho + Arquitetura + UX/UI)

> **Objetivo:** revisar a estrutura INTEIRA do app para achar pontos fortes/fracos e planejar o produto mais
> otimizado e completo possível — **incluindo avaliar refazer o app noutra stack web** (sair do Streamlit se a
> evidência justificar). **Épico 100% de PESQUISA e PLANEJAMENTO: nenhum bloco implementa produção.** Cada bloco
> entrega um RELATÓRIO/PROPOSTA (gitignored em `data/analysis/` ou em `docs/`). As DECISÕES (rebuild vs refactor,
> stack alvo, direção de UX) são **gate humano + DEC** no bloco de síntese (BLK-REV-12). **READ-ONLY sobre o M1**
> em todos os blocos.
>
> **Dores relatadas por Felipe (2026-07-08), que ancoram a pesquisa:** (1) lag ao **renderizar o mapa**; (2) lag
> na **troca de modos de cor/heat maps** (M1/Censitário/Residual…); (3) lag na **seleção de hexes + inclusão no
> cenário múltiplo**; (4) lag ao **gerar PDF Pontual e Municipal**; (5) app **poluído e pouco usual para leigos**.
>
> **Divisão de autonomia:** MEDIÇÃO/DIAGNÓSTICO/pesquisa de arquitetura (REV-01..07) é **loop-safe** (headless,
> determinística, READ-ONLY, entrega relatório). O que exige **ver o app renderizado, julgamento de design ou
> decisão** (spike visual, UX, síntese) é **humano** (lição BLK-UI-10: o loop não enxerga a UI). **Caveat honesto:**
> o loop mede o lado **Python/servidor** (data prep, serialização, recompute do rerun, geometria, tiles); a medição
> de **paint/interação no browser** é complemento **manual**, anotado no relatório.

- BLK-REV-01 (concluído 2026-07-08) — ver tasks/completed.md


---

- BLK-REV-02 (concluído 2026-07-08) — ver tasks/completed.md


---

- BLK-REV-03 (concluído 2026-07-08) — ver tasks/completed.md


---

- BLK-REV-04 (concluído 2026-07-08) — ver tasks/completed.md


---

- BLK-REV-05 (concluído 2026-07-08) — ver tasks/completed.md


---

- BLK-REV-06 (concluído 2026-07-10) — ver tasks/completed.md


---

- BLK-REV-07 (concluído 2026-07-10) — ver tasks/completed.md


---

### BLK-REV-08 — Spike técnico: mapa client-side (deck.gl/MapLibre) servido por API — teto de performance

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (embasa empiricamente o REV-07; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — visual/perf]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-REV-07** (ou BLK-REV-03). |
| **Autonomia** | **manual (NÃO loop-safe)** — protótipo VISUAL throwaway; exige VER o render e medir FPS/interação no browser (lição BLK-UI-10). NÃO marcar loop-safe. |

**Contexto.** Para embasar o REV-07, medir empiricamente o teto de performance do mapa client-side vs pydeck/Streamlit.
**Objetivo.** Spike **descartável**: servir os hexes H3 por um endpoint e renderizar client-side (deck.gl
`H3HexagonLayer` / MapLibre), medindo FPS, latência de troca de cor e de seleção vs o app atual. Protótipo, **NÃO
produção**.
**Guardrail.** §5 READ-ONLY M1; código de spike isolado, descartado após medir.

> **Emenda (2026-07-10, Felipe):** (a) **partir do padrão já provado do `ui_proto.py`** (BLK-UI-10:
> `st.components.v1.html` + dados embutidos + recorte por UF em `data/cache/ui_proto/`), trocando Leaflet
> por deck.gl `H3HexagonLayer`/MapLibre e **escalando ao volume real do cap (18–35k hexes)** — a pergunta
> que o PoC Leaflet (~500 hexes) não respondeu; `H3HexagonLayer` aceita `hex_id` cru (sem enviar geometria).
> (b) **Incluir a medição VPS↔cliente como sub-entregável:** (i) DevTools contra a produção — tamanho real
> dos frames WebSocket por rerun e tempo clique→paint (fecha o caveat iii dos REV-01..06); (ii) script
> Playwright (dep já no extra `[scraping]`) cronometrando os 4 fluxos de dor ponta-a-ponta contra
> `dashboard.ultra-expansao.tech`; (iii) A/B final: spike servido pelo Caddy da VPS, medido pelo mesmo
> script — comparação Streamlit vs client-side na mesma rede real. Prioridade ELEVADA (2026-07-10): com o
> time poliglota (ver emenda do REV-12), este é o número que decide o rumo no REV-12.

---

### BLK-REV-09 — Avaliação heurística de UX + estudo de "clutter" para leigos

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (dor #5; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — UX]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | — (avaliação do app renderizado). |
| **Autonomia** | **manual (NÃO loop-safe)** — exige VER o app renderizado + julgamento humano de UX; o loop não enxerga a UI. NÃO marcar loop-safe. |

**Contexto.** Dor #5 — app "poluído e pouco usual para leigos".
**Objetivo.** Heuristic evaluation (Nielsen), inventário de poluição visual/densidade/jargão, e **jobs-to-be-done
por persona** (executivo, operador, leigo). Relatório de problemas priorizados por severidade × esforço.
**Guardrail.** §5 READ-ONLY M1.

---

### BLK-REV-10 — Arquitetura de informação e fluxos-alvo (proposta de redesign)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (reduz complexidade sem perder poder; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — design]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-REV-09** (dores de UX priorizadas). |
| **Autonomia** | **manual (NÃO loop-safe)** — design/UX; exige julgamento humano. NÃO marcar loop-safe. |

**Contexto.** Reduzir a complexidade para leigos sem perder poder para power users.
**Objetivo.** Redesenhar a **arquitetura de informação** em torno dos fluxos core (triagem→viabilidade, per
`docs/estado_dos_modelos.md`); **progressive disclosure** (modo simples p/ leigo vs avançado); wireframes de baixa
fidelidade por persona. Usar o guia `frontend-design`.
**Guardrail.** §5 READ-ONLY M1.

---

### BLK-REV-11 — Sistema visual / design language (research)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (linguagem visual coerente; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — design]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | — (pode ir em paralelo à trilha de UX). |
| **Autonomia** | **manual (NÃO loop-safe)** — design; exige julgamento visual humano. NÃO marcar loop-safe. |

**Contexto.** Consolidar a linguagem visual (a direção **turquesa Ultra + magenta concorrente** do BLK-UI-10;
tipografia; componentes) e o sistema de dataviz dos mapas/gráficos.
**Objetivo.** Proposta de **design system** (tokens, componentes, paletas acessíveis light/dark) reusando os guias
`frontend-design` e `dataviz`.
**Guardrail.** §5 READ-ONLY M1.

---

### BLK-REV-12 — Síntese executiva + decisão de rumo (rebuild vs refactor) + roadmap faseado (DEC + gate)

| Campo | Valor |
|---|---|
| **Criticidade** | **Estratégica** (decide o rumo do produto; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[GATE HUMANO + DEC]` → (implementação vira epic próprio). |
| **Status** | Pendente. |
| **Depende de** | **BLK-REV-01..11** (todos os relatórios de perf, arquitetura e UX). |
| **Autonomia** | **manual (NÃO loop-safe)** — decisão estratégica; gate humano obrigatório + DEC. NÃO marcar loop-safe. |

**Contexto.** Consolidar tudo numa recomendação acionável.
**Objetivo.** Relatório executivo que junta **perf** (REV-01..06), **arquitetura** (REV-07/08) e **UX** (REV-09..11)
numa **recomendação de rumo** (rebuild vs refactor incremental), **stack alvo**, direção de UX e **roadmap faseado**
(esforço × risco × valor por fase). Registrar **DEC** com a decisão. A implementação vira **epic próprio** (fora deste
épico de pesquisa).
**Guardrail.** §5 READ-ONLY M1; este bloco decide o PLANO, não implementa.

> **Emenda (2026-07-10, Felipe):** o critério 5 da matriz do BLK-REV-07 ("custo de dev por perfil de
> time") foi avaliado assumindo time **Python-only** — premissa INCORRETA: o time é **poliglota** (JS/TS
> inclusive; Vini fez os scrapers e o PoC HTML/Leaflet do BLK-UI-10, Juan mantém bot + API). Na decisão,
> **reponderar o "−" das opções (b)/(d) para "0/+"** nesse critério — o que aproxima o rebuild sobre a
> infra existente (SPA servida pelo Caddy + `api` FastAPI já em produção). Insumos adicionais exigidos
> para decidir: o teto empírico do client-side em escala real e a latência VPS↔cliente medida (ambos do
> BLK-REV-08 emendado). Os quick wins (epic BLK-PERF) NÃO conflitam com nenhum rumo: 01a é server-side
> permanente; 01b/c mantêm a produção usável durante a eventual migração e viram a régua de comparação da SPA.

---

## Epic BLK-PERF — Quick wins de performance do dashboard (implementação dos fixes diagnosticados no BLK-REV)

> **Origem (2026-07-10, aprovado por Felipe):** implementação dos fixes com causa-raiz isolada e ganho
> estimado pelos diagnósticos **BLK-REV-03/04/05/06** (concluídos; relatórios em `data/analysis/`,
> inventário em `docs/arquitetura_app_atual.md`). Diferente do épico BLK-REV (pesquisa-only), este epic
> **IMPLEMENTA** — mas SÓ na camada de display/render do dashboard e relatórios. **READ-ONLY sobre o M1
> em todos os blocos** (§5): nenhum recalcula `score_priorizacao`/`hex_score_estrutural`/pesos/carteira/
> plano/artefatos oficiais; raio 1,5 km e método de intersecção INTOCADOS.
>
> **Instrumento de aceite (todos os blocos):** re-rodar `scripts/perf_baseline_app.py` (harness do
> BLK-REV-01) ANTES/DEPOIS e registrar a comparação no PR — o ganho tem de aparecer no número, não na
> narrativa. Baseline de referência: `data/analysis/perf_baseline_app_2026.md`.
>
> **Relação com a trilha web (REV-07/08/12):** o BLK-PERF-01a é **permanente** (server-side; os PDFs
> continuam no backend em qualquer stack). O 01b/01c são específicos do Streamlit — o custo (dias) compra
> produção usável durante a trilha web e a régua honesta de comparação para a eventual SPA.
> **Estratégia de branch:** 1 bloco = 1 branch `ciclo/<ID>` = 1 PR — independentes entre si e da trilha
> web (superfícies disjuntas; a SPA viverá em diretório novo + extensões da `api/`).

---

- BLK-PERF-01a (concluído 2026-07-10) — ver tasks/completed.md


---

- BLK-PERF-01b (concluído 2026-07-10) — ver tasks/completed.md


---

- BLK-PERF-01c (concluído 2026-07-10) — ver tasks/completed.md


---

- BLK-PERF-01d (concluído 2026-07-10) — ver tasks/completed.md


---

## Epic BLK-TP — Camada de Demanda Revelada (camada paralela, READ-ONLY sobre o M1)

> Epic que incorpora ao Motor um **sinal externo, georreferenciado e anônimo de demanda paga por
> academia** (membros pagantes por região), agregado em H3. Motivação: a DEC-009 encerrou a previsão
> de *magnitude de demanda* pela geografia interna (renda/pop têm sinal nulo no M1 — DEC-001); faltava
> um sinal de **demanda observada**. Uma **análise exploratória interna (2026-06-24)** indicou que essa
> demanda paga por hex correlaciona forte com a nossa camada residual (Spearman **+0,52** vs.
> `score_oportunidade_residual`) e com alunos efetivamente capturados (**+0,75**) — primeira validação
> externa positiva forte de uma camada do Motor.
> **READ-ONLY sobre o M1 em TODOS os blocos:** nenhum recalcula `score_priorizacao`, pesos, carteira,
> plano ou artefatos oficiais (§5 guardrail). A **demanda entra como insumo observado, NUNCA como
> preditor geográfico de magnitude** (DEC-009 intacta).
> **Anti-PII por construção:** o insumo bruto tem PII na origem; a ingestão consome **apenas dados já
> agregados** e descarta qualquer identificador/coordenada individual na fronteira de entrada (§4).
> Sugere registrar **DEC-012** (adoção da camada) ao iniciar o BLK-TP-01.

- BLK-TP-01 (concluído 2026-06-24) — ver tasks/completed.md


---

- BLK-TP-02 (concluído 2026-06-25) — ver tasks/completed.md


---

- BLK-TP-03 (concluído 2026-07-02) — ver tasks/completed.md


---

### BLK-TP-03-FU1 — Overlay dos vazios competitivos no Mapa Territorial (Opção B)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (camada de visualização/overlay no dashboard; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — UX: cor/toggle/tooltip]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-TP-03** (concluído — parquet `data/staging/vazios_competitivos_lc.parquet`, 229 hexes). |
| **Autonomia** | **manual (NÃO loop-safe)** — toca `src/motor_expansao/dashboard/` (decisão de produto/UX). |

**Objetivo.** Expor os hexes de "vazio competitivo" (parquet gerado no BLK-TP-03) como **overlay visual
READ-ONLY** no Mapa Territorial: toggle na sidebar (default OFF) + camada de realce (contorno/cor
distinta) sobre os 229 hexes, com tooltip de `membros_gt5km_concorrente_lc`/`uf`/`nome_municipio`/
`score_priorizacao`. É a **Opção B** deferida no gate humano do BLK-TP-03 (Opção A = só parquet foi a
escolhida). Camada visual de apoio (§2) — não altera score/ranking/carteira/plano/artefatos.

**Plano técnico já detalhado** no handoff do Planner do BLK-TP-03 (passos 6–9):
`context/handoff/20260702-104651-planner.md` — inclui a exigência de LER `constants.py`
(`MAP_POINT_LIMIT`, `MAP_SOURCE_COLUMNS_*`) e `_downsample_map_index` ANTES de codar, para não
regredir o cap dos 4 modos do mapa (M1/Híbrido/Censitário/Residual).

**Critérios de aceite.** Toggle default OFF; layer só desenha os hexes do parquet; leitura lazy/cacheada
offline (sem rede — §2); parquet ausente → toggle oculto/desabilitado com mensagem clara; score/
carteira/plano do dashboard inalterados com overlay ON; cap dos 4 modos inalterado; teste de
integração cobre o toggle/layer; suíte verde; `import streamlit_app` ok.
**Guardrail.** §5 (READ-ONLY M1); §2 (sem API ao vivo); pins/camadas de concorrente são apoio visual
(CLAUDE.md §2). NÃO tocar `_downsample_map_index`/`MAP_POINT_LIMIT`/`MAP_SOURCE_COLUMNS_*`.

---

- BLK-TP-04 (concluído 2026-07-02) — ver tasks/completed.md



---

- BLK-TP-06 (concluído 2026-07-02) — ver tasks/completed.md


---

- BLK-TP-07 (concluído 2026-07-03) — ver tasks/completed.md



---

### BLK-TP-09 — Integração do sinal de captura validado à camada de mercado/residual (agnóstico de mecanismo; DEC + gate)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta/Crítica** (altera a **FÓRMULA de um score ATIVO** da camada paralela de mercado/residual e **regenera** os parquets que alimentam dashboard/API; **READ-ONLY sobre o M1 OFICIAL**). **Exige DEC registrada + gate humano obrigatório** antes do Builder. |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA OBRIGATÓRIA + DEC]` → Builder → QA. |
| **Status** | **Habilitado por um candidato vencedor (BLK-TP-07 = GO) — pendente de DEC + gate.** RE-ESCOPADO em 2026-07-04: era "aplicar a recalibração do residual do TP-06"; passou a ser **agnóstico de mecanismo — integrar o SINAL DE CAPTURA VALIDADO** à camada de mercado/residual. Motivo: a via original (mexer na *oferta consumida* do residual) foi **testada e esgotada** out-of-fold, honestamente (DEC-008), sem candidato material — **BLK-TP-06-FU1** Candidato A (somar as menores cru, dedup fino) = **NO-GO** (Δ −0,0427); **BLK-TP-06-FU2** Candidato C (capacidade de clube real `data/validacao/` + decay 2 km) = **C1 RUÍDO** (Δ +0,0019, idêntico ao baseline em 97,3% dos hexes) / **C2 NO-GO** (Δ −0,0312). O candidato que **venceu materialmente** veio por OUTRO mecanismo: **BLK-TP-07 (GO)** — Huff/gravitacional de captura por hexágono vs demanda observada `membros` (R²_oof_log +0,4391 IC95 [+0,4251,+0,4523], β=0,5, **supera o baseline geométrico +0,2922 ⇒ a distância AGREGA**; n_join 16.575, ~1% do universo, viés Sudeste). O TP-07 **validou o sinal, mas NÃO integrou nada**. Este bloco é essa **integração** — segue exigindo **DEC + gate humano** e medição de impacto/cobertura. |
| **Depende de** | **BLK-TP-07** (candidato vencedor = GO honesto out-of-fold, concluído 2026-07-03 — `demanda_revelada/huff_captura.py`). Histórico da via esgotada (contexto, não bloqueio): BLK-TP-06 (GO +0,3119), BLK-TP-06-FU1 (A NO-GO), BLK-TP-06-FU2 (C ruído/NO-GO). |
| **Autonomia** | **manual (NÃO loop-safe)** — muda um score em produção; NUNCA loop-safe. |

**Contexto.** A trilha de melhorar o `score_oportunidade_residual` **pela oferta consumida** (subtrair/recapacitar
concorrência no próprio residual) foi exaurida sem ganho material (TP-06-FU1/FU2, acima). O sinal que **venceu**
apareceu por um mecanismo diferente: tratar a concorrência como **captura gravitacional (Huff) no ponto/hex
candidato**, validada contra a demanda **observada** (`membros`) — o **BLK-TP-07** deu o **GO honesto** (out-of-fold,
supera o baseline geométrico ⇒ a geometria de distância agrega, não é só "contar concorrente perto"). O TP-07
implementou e validou o motor de captura (`demanda_revelada/huff_captura.py`, READ-ONLY, sem integrar), mas **não
tocou** `score_oportunidade_residual`/carteira/plano. Este bloco é a **aplicação/integração** desse sinal — e por
isso exige DEC + gate.

**Objetivo.** Integrar o sinal de captura Huff validado (TP-07) à **camada paralela de mercado/residual** — seja
como componente/ajuste de `score_oportunidade_residual`, seja como coluna acionável nova casada por `hex_id` (a
forma exata é decisão do Planner + gate/DEC) — em `src/motor_expansao/pipelines/calcular_colunas_mercado.py`,
**medindo o impacto** (antes/depois: quantos hexes mudam de faixa, deslocamento de distribuição) e **regenerando**
a camada pela **ordem canônica** (`híbrido → mercado → calcular_colunas_mercado → carteira → plano → domínio →
residual → fase1_bi_exports`). **READ-ONLY sobre o M1 OFICIAL**: `score_priorizacao`, `hex_score_estrutural`,
pesos (renda 0.40/pop 0.60), carteira/plano do M1 e os 4 artefatos oficiais permanecem **INTOCADOS** (mtime
inalterado) — muda-se apenas a camada paralela de mercado/residual.

**Critérios de aceite.** DEC registrada e aprovada ANTES do Builder (a DEC define a FORMA de integração e a
função exata); medição de impacto documentada (antes/depois, hexes que mudam de faixa); regeneração reprodutível
pela ordem canônica; **cobertura/viés do sinal (~1% metropolitano, viés Sudeste — herdado do TP-07/TP-06)
explicitamente tratado** — o GO é de ~1% do universo, então a integração **não pode piorar/enviesar os 99% sem
sinal** (ex.: aplicar só onde há cobertura, ou como camada acionável separada em vez de sobrescrever o residual
nacional); artefatos oficiais do M1 com **mtime inalterado**; suíte verde; `import streamlit_app` ok.
**Guardrail.** §5 (READ-ONLY M1 OFICIAL — só a camada paralela muda, e com DEC); DEC-008 (a integração tem de ser
justificada pela validação **out-of-fold** do TP-07, não por R² in-sample); DEC-009 (demanda `membros` é ALVO de
validação, NUNCA vira preditor geográfico de magnitude no artefato de produção); DEC-012 (anti-PII).

---

## Epic BLK-ATR — Funil de Atratividade de Hexágonos (gate de viabilidade + leitura multi-eixo; camada paralela READ-ONLY sobre o M1)

**Objetivo do epic.** Formalizar a decisão de "onde entrar" como um **funil de duas etapas**, paralelo e
READ-ONLY sobre o M1: **(1) um gate absoluto de viabilidade** (piso fixo de população e renda per capita —
abaixo dele nem entra na conversa) e **(2) uma leitura multi-eixo dentro do viável** que cruza os três eixos
ortogonais de atratividade — **sociodemografia** (renda/densidade), **tamanho de mercado** (residual/demanda
observada) e **disputa competitiva** (share de captura Huff do BLK-TP-07). Nenhuma camada bate o martelo
sozinha; todas informam. Motivação: o residual sozinho "desiste" de regiões ricas-mas-saturadas (competição
alta zera a demanda não atendida) e o Huff sozinho também penaliza saturação — falta o eixo de **atração**
sociodemográfica para contrabalançar as duas lentes de competição. Este epic testa, honestamente, se combinar
os eixos agrega valor preditivo real sobre a demanda observada, e só então materializa.
**READ-ONLY sobre o M1** (não recalibra `score_priorizacao`/`hex_score_estrutural`/pesos nem regenera
artefatos oficiais; DEC-001 intacta). Metodologia obrigatória DEC-008 (out-of-fold vs baseline, R² in-sample
banido, IC95, flag de extrapolação). DEC-009 (demanda observada é ALVO de validação, nunca preditor de
magnitude). DEC-012 aplica-se **só ao dado pessoal** da Demanda Revelada; o dado de **estabelecimento**
concorrente (nome/endereço/lat-long de academia — público, coletado por scraper) **não é PII pessoal** e é
usado normalmente, inclusive o nome para dedup por rede.

**Sequência:** BLK-ATR-01 (densifica o Huff) + BLK-ATR-02 (gate) → BLK-ATR-03 (testa a estrutura) →
BLK-ATR-04 (visualiza os resultados) → **[revisão humana]** → BLK-ATR-05 (materializa em produção; NÃO
loop-safe). Os quatro primeiros são de **análise/validação, 100% autônomos (loop-safe)**; o último toca
produção e exige DEC + gate humano.

---

- BLK-ATR-01 (concluído 2026-07-06) — ver tasks/completed.md



---

- BLK-ATR-03 (concluído 2026-07-06) — ver tasks/completed.md


---

- BLK-ATR-04 (concluído 2026-07-06) — ver tasks/completed.md


---

- BLK-ATR-01-FU1 (concluído 2026-07-07) — ver tasks/completed.md


---

- BLK-ATR-03-FU1 (concluído 2026-07-07) — ver tasks/completed.md


---

### BLK-ATR-05 — Materializar a estrutura escolhida (gate + matriz/composto) em produção (DEC + gate humano)

| Campo | Valor |
|---|---|
| **Criticidade** | **Crítica** (materializa o funil na camada de um score ATIVO e regenera parquets de dashboard/API; **READ-ONLY sobre o M1 OFICIAL**). **Exige DEC registrada + gate humano obrigatório** antes do Builder. |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA OBRIGATÓRIA + DEC]` → Builder → QA. |
| **Status** | Em espera (condicional ao veredito do BLK-ATR-03 + decisão humana). |
| **Depende de** | **BLK-ATR-03** (estrutura decidida: matriz ou composto GO) + **BLK-ATR-04** (visualização para a decisão). |
| **Autonomia** | **manual (NÃO loop-safe)** — muda a camada de um score em produção e exige gate humano; NUNCA loop-safe (o loop não tem gate). |

**Contexto.** Após BLK-ATR-03 decidir a estrutura e BLK-ATR-04 dar os números, este bloco a materializa na
camada paralela de mercado — o gate de viabilidade (BLK-ATR-02) + a leitura escolhida (matriz de eixos
normalizados na mesma régua **ou** score composto validado) — para consumo no dashboard/API.

**Objetivo.** Materializar o funil na camada de mercado (`calcular_colunas_mercado.py` ou módulo paralelo),
medindo impacto (antes/depois: hexes por faixa/quadrante) e regenerando a camada pela **ordem canônica**
(`híbrido → mercado → calcular_colunas_mercado → carteira → plano → domínio → residual → fase1_bi_exports`).
**READ-ONLY sobre o M1 OFICIAL**: `score_priorizacao`/`hex_score_estrutural`/pesos/carteira/plano/4 artefatos
oficiais **INTOCADOS** (mtime inalterado).

**Critérios de aceite.** DEC registrada e aprovada ANTES do Builder; medição de impacto documentada;
regeneração reprodutível pela ordem canônica; cobertura/viés ~1% metropolitano explicitamente tratado (não
enviesar os 99% sem sinal de disputa); artefatos oficiais do M1 com **mtime inalterado**; suíte verde;
`import streamlit_app` ok.
**Guardrail.** §5 (READ-ONLY M1 OFICIAL — só a camada paralela muda, e com DEC); DEC-008 (justificado pela
validação out-of-fold do BLK-ATR-03); DEC-009 (demanda não vira preditor de magnitude); DEC-012 (dado pessoal
protegido).

---

## Epic BLK-LTV — Integração Lifetime × Motor de Expansão (eixo retenção territorial, camada paralela READ-ONLY sobre o M1)

**Objetivo do epic.** Validar se o perfil do território prevê a retenção/LTV da carteira, para a
expansão passar a priorizar "onde a demanda **permanece**", não só "onde há demanda". Se validado,
compor um eixo de score paralelo (M2) que pondere captação + retenção/LTV territorial. **READ-ONLY
sobre o M1** (não recalibra `score_priorizacao`/`hex_score_estrutural`/pesos nem regenera artefatos
oficiais; DEC-001 intacta). Metodologia obrigatória DEC-008: Spearman + **bootstrap/IC** (N pequeno),
sem R² in-sample; controlar por maturidade quando houver dado.

**Insumo (Lifetime).** `data/ultra/unidade_para_motor.parquet` — 88 unidades com `PROB_CANCEL_90D_*`,
`LTV_PROSPECTIVO_12M_*`, `CONFIABILIDADE_UNIDADE`, `USAR_PROB_ABSOLUTA`, `USAR_RANKING`
(dicionário em `unidade_para_motor_DICIONARIO.md`). Chave lógica: `COD_UNIDADE`; chave de join real
disponível: **nome da unidade** (`UNIDADE`), pois nem o Lifetime nem as bases geo têm `COD_UNIDADE`.

**Fonte de geocodificação (confirmada no repo).** `data/ultra/Ultra.csv` (legado: `sep=";"`,
`encoding="latin-1"`, 1 linha de metadado) — 147 unidades com `UNIDADE`/`ESTADO`/`CIDADE`/`Latitude`/
`Longitude`. Complemento: `data/staging/unidades_ultra_performance_hex.parquet` (54 unidades já com
`hex_id`/features territoriais). Cobertura medida (2026-07-01): match exato de nome Lifetime↔Ultra.csv
= 34/88; fuzzy ≥0.8 recupera mais (≈43 contra o perf-hex) — fechar cobertura é trabalho do BLK-LTV-01.

**Regras (do pedido, canônicas para o epic).** Usar `LTV_PROSPECTIVO_12M_*` só no **agregado por
unidade** (validado); respeitar `USAR_PROB_ABSOLUTA` por unidade (unidades sem prob. absoluta confiável
entram só no eixo de ranking); aplicar **haircut ~20%** em volume absoluto; **N=88 exige bootstrap/IC**.

**Caveat estrutural (registrar, não bloqueia LTV-01/02).** `unidade_para_motor.parquet` **não tem data
de abertura / idade da unidade** (as métricas de tempo são tenure de aluno, não idade da unidade) → o
"controlar por maturidade" do BLK-LTV-03 esbarra no **mesmo gap do gate G1 da DEC-001**. Sem esse
controle, a correlação território×retenção fica confundida por maturidade; tratar como confound
declarado no relatório.

---

- BLK-LTV-01 (concluído 2026-07-01) — ver tasks/completed.md



---

- BLK-LTV-03 (concluído 2026-07-01) — ver tasks/completed.md


---

- BLK-LTV-04 (concluído 2026-07-01) — ver tasks/completed.md


---

## Projeto — Repaginação visual do dashboard (UX/UI)

- BLK-UI-11 (concluído 2026-06-29) — ver tasks/completed.md


---

- BLK-UI-10 (concluído 2026-07-06) — ver tasks/completed.md


---

## Relatório Pontual Censitário — geração em lote (2026-07-06, pedido de Vini)

> Espelha o **BLK-RELMUN-04** (Relatório Municipal em lote), agora para o **Relatório Pontual
> Censitário** (raio 1,5 km). Diferença estrutural: o municipal itera sobre um *multiselect* de
> municípios já existente; o pontual é dirigido por **um endereço/coordenada pesquisado por vez** →
> o mecanismo de lote é **acumular os endereços pesquisados** numa fila antes de gerar. Camada de
> visualização/relatório — **READ-ONLY sobre o M1** (§5).

- BLK-RELPON-04 (concluído 2026-07-06) — ver tasks/completed.md


---

## Epic BLK-ACENTO — Correção de acentuação e escrita (plataforma + relatórios)

> Origem: tarefa ClickUp **"Resolver Problemas de Escrita e Acentuação no Motor"** (`86e26mtn5`,
> lista *Motor de Expansão*, prioridade **urgente**, criador Felipe Castaldi, responsável Vinicius).
> Descrição: *"Resolva todos os problemas de gramática e escrita no site e nos relatórios gerados
> pelo Motor de Expansão."* Esclarecimento de Vinicius (2026-07-06): o problema é a **acentuação de
> TUDO** — tanto a plataforma (dashboard Streamlit) quanto os relatórios gerados (PDF/CSV); **muitas
> palavras não contêm acento** (ex.: "Relatorio", "Analise", "Nao", "concluido", "endereco",
> "ultimo", "Populacao", "municipio", "regiao", "voce", "opcao").
>
> **Diagnóstico técnico (auditoria 2026-07-06, ancorado no código):** a ausência de acento é
> majoritariamente **estilo/hábito herdado**, NÃO uma exigência técnica. No PDF, o core font
> `Helvetica` do `fpdf2` codifica em **`latin-1`**, que **cobre integralmente** os acentos
> portugueses (á â ã à ç é ê í ó ô õ ú ü); o helper `_ascii()` (`censo_report.py:170-172`,
> `relatorio_municipal.py:211-213`) reduz a latin-1 com `errors="replace"` e seu comentário-fonte
> (`censo_report.py:16-17`) generalizou incorretamente para "ASCII sem acento". Logo, **acentuar o
> texto-fonte é seguro hoje, sem trocar fonte/biblioteca.** O CSV é `utf-8-sig`
> (`censo_report.py:148`) — acentos seguros. Estado atual JÁ é misto (ex.: `pages.py:551`
> "Expansão de Domínio" já acentuado), reforçando que é descuido, não regra.
>
> **A ARMADILHA REAL não é o acento** e sim a **tipografia "esperta"**: travessão `—`/`–`, bullet
> `•`, seta `→`, reticências `…`, aspas curvas `" " ' '` e `©` estão FORA de latin-1 e viram `"?"`
> **silenciosamente** via `errors="replace"` no PDF. Todo texto-fonte de PDF deve usar ASCII simples
> para pontuação (hífen `-`, aspas retas `"`, "(c)") mesmo tendo acento nas letras.
>
> **READ-ONLY sobre o M1 (§5):** esta epic corrige APENAS texto voltado ao usuário. NÃO toca
> `score_priorizacao`/`hex_score_estrutural`/pesos/carteira/plano/artefatos oficiais, nem a lógica.
> É um trabalho de **display**, com a disciplina crítica de **jamais acentuar identificadores**.
>
> **Guardrail permanente (não regredir depois):** a regra de acentuação foi promovida a **CLAUDE.md
> §2** (fonte canônica lida antes de qualquer tarefa, inclusive pelos sub-agentes do `/run-cycle`),
> para que TODO trabalho POSTERIOR a esta epic mantenha a acentuação correta em strings novas/editadas
> e respeite a lista de proibições (identificadores). Esta epic é a correção retroativa; a §2 é a
> prevenção contínua.

**NÃO ACENTUAR (quebra lógica) — lista canônica de proibições (todos os sub-blocos):**
- `key=` de widgets Streamlit e chaves de `st.session_state` (ex.: `coord_search_input`,
  `dashboard_active_tab`, `relpon_lote_fila`, `btn_gerar_pdf_topo`, `multihex_cenario`) —
  `pages.py:802,1592,2472-2660,3096-3368`.
- Seletores CSS `.st-key-*` em `inject_styles` (`pages.py:154,358-448`) — ecoam as `key=` acima.
- **Valores brutos de enum/categoria** comparados em lógica E produzidos pelo pipeline core:
  `FAIXA_ORDEM = ["prioridade_maxima","alta","media","baixa","descartado","inviavel"]`
  (`constants.py:90-97`), exibido CRU no `st.multiselect` (`pages.py:668-671`), usado em
  `.isin(selected_faixas)` (`data.py:499`, `components.py:1706`) e como chave do dict de cores
  (`constants.py:289-292`); origem em `src/motor_expansao/core/constants.py`,
  `pipelines/calcular_colunas_mercado.py`, `pipelines/m1/*`. Também `HYBRID_ELIGIBILITY_ORDER`,
  `COVERAGE_BUCKET_ORDER`, `JOIN_QUALITY_ORDER` (`constants.py:86-88`), `template="classico"`,
  `METODO_RELATORIO_*` (`censo_point.py:15`, `relatorio_municipal.py:58`). **Solução: camada de
  LABEL DE EXIBIÇÃO (`{valor_bruto: "Texto Acentuado"}`) — nunca tocar o literal usado na lógica.**
- Nomes de coluna de DataFrame (`score_priorizacao`, `nome_municipio`, `renda_per_capita`,
  `faixa_oportunidade`, `cod_municipio`, ...) — schema compartilhado com o M1/pipeline.
- Slugs/nomes de arquivo — JÁ protegidos por `_slug()`/`unicodedata` (`relatorio_municipal.py:216-221`)
  e `_relmun_key_slug` (`pages.py:3194`); não mexer.

**Decomposição (sequência recomendada):** BLK-ACENTO-01 (UI dashboard) -> BLK-ACENTO-02 (relatórios
PDF/CSV). Sub-blocos independentes (podem ir em PRs separados); cada um traz seus próprios testes.

---

- BLK-ACENTO-01 (concluído 2026-07-08) — ver tasks/completed.md


---

- BLK-ACENTO-02 (concluído 2026-07-08) — ver tasks/completed.md


---

- BLK-MAP-02 (concluído 2026-07-08) — ver tasks/completed.md


---

- BLK-RELMUN-05 (concluído 2026-07-08) — ver tasks/completed.md


---

- BLK-RELMUN-06 (concluído 2026-07-10) — ver tasks/completed.md


---

- BLK-RELPON-05 (concluído 2026-07-10) — ver tasks/completed.md


---
