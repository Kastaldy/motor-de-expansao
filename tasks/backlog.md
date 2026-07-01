# Backlog

## Priorização atual

Próximo ciclo recomendado: **BLK-API-01 — Definir arquitetura e contrato da API (G1)** — bloco de
design/decisão **Estratégico** com gate humano para as 6 decisões-chave de contrato (formato de saída,
auth, escopo de endpoints, entrada, raio, reprodutibilidade). Pré-requisito de G2/G3/G4. Só docs,
READ-ONLY M1. Ver seção "Projeto — API GeoEspacial".
Em paralelo (trilha do Vini, dashboard/PDF/UX): BLK-FIX-07..11, BLK-SAM-01, BLK-EST-01/02, BLK-UI-01.
BLK-CENSO-01/02/03 (refino do Relatório Pontual Censitário): **concluídos** (ver tasks/completed.md).

**Candidato ao loop autônomo (2026-06-24): `BLK-UI-10` — PoC de repaginação visual do dashboard**
(tema denso + mapa Leaflet client-side, inspirado no `NAO_ABRA/totalpass_final*.html`). É o único bloco
novo **`loop-safe`** disponível: Baixa criticidade, READ-ONLY M1, sem VPS/deploy/dependência nova de base,
PoC opt-in que não substitui produção. Sem dependências pendentes — pode ser pego pelo loop a qualquer
momento. Ver seção "Projeto — Repaginação visual do dashboard (UX/UI)".

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

## Relatório Municipal — novo formato (2026-06-19, pedido de Vini)

> Novo formato de relatório que **coexiste** com o Relatório Pontual Censitário atual (que analisa
> uma região a partir do **raio de um ponto central**). O novo é um **relatório de município**:
> fica disponível para **geração e download após a seleção de um município** no dashboard. O escopo
> exato dos dados sai de um **template** que o Vini enviará e que será analisado como base, com
> ajustes ao longo do ciclo. Família do Relatório Censitário (malha real IBGE 2022), camada de
> visualização/relatório — **READ-ONLY sobre o M1** (§5 guardrail).

- BLK-RELMUN-01 (concluído 2026-06-22) — ver tasks/completed.md

- BLK-RELMUN-02 (concluído 2026-06-24) — ver tasks/completed.md



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

### BLK-SEC-03 — Hardening do VPS (firewall, fail2ban, updates, SSH, 2FA)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (exposição do servidor de produção) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Origem** | revisão de robustez 2026-05-31 (acesso root SSH; sem hardening documentado) |

**Contexto / gap:** o `docs/infra_producao.md` mostra acesso como `root` via SSH e atualização de
sistema **manual mensal**; não há menção a firewall (ufw), fail2ban, `unattended-upgrades`, política de
SSH (desabilitar login por senha / limitar root) nem 2FA obrigatório no Authelia (hoje "opcional").

**Objetivo:** reduzir a superfície de ataque do VPS de produção sem quebrar o deploy atual.

**Escopo permitido (cada passo via MCP com confirmação individual — guardrail do projeto):**
- `ufw` liberando só 22/80/443; `fail2ban` no SSH; `unattended-upgrades` para patches de segurança.
- SSH: desabilitar autenticação por senha (manter chave), avaliar usuário não-root para operação.
- Authelia: avaliar **forçar 2FA** para o grupo `ultra_team`.
- **Revisão de acesso (least-privilege):** auditar quem está no `ultra_team` em
  `authelia/users_database.yml`, remover acessos obsoletos e definir processo de offboarding
  (revogar usuário ao sair). Documentar a periodicidade da revisão.
- Documentar tudo em `docs/infra_producao.md` (seção de hardening) com rollback de cada item.

**Fora de escopo:** trocar provedor/arquitetura; mudar M1/dashboard.

**Critérios de aceite:**
- Firewall ativo (regras mínimas), fail2ban e unattended-upgrades rodando; SSH sem senha.
- Dashboard e deploy continuam funcionando (smoke + login OK após cada mudança).
- Cada alteração no VPS feita com confirmação individual; documentada com rollback.

**Risco:** médio-alto (mexer em SSH/firewall pode trancar o acesso). Mitigação: alterar um item por vez,
manter sessão aberta de teste, ter rollback pronto ANTES de aplicar regras de SSH/ufw.

**Atualização (2026-06-12, pós-deploy API/bot):** subiram 2 containers novos (`motor_expansao_api`,
`motor_expansao_telegram_bot`). **NÃO mudam a superfície de firewall:** a API não publica porta no host
(só rede interna `app_net`); o bot é long-polling (conexão de SAÍDA ao Telegram). A regra `ufw` "só
22/80/443" segue correta. Considerar no escopo: (i) a imagem da API embute **Google Chrome** (superfície
maior, porém interna) — manter `unattended-upgrades`/rebuild via CI em dia; (ii) `unattended-upgrades`
e o alerta de "container reiniciando" (cruza com BLK-SEC-05) agora abrangem também api/bot.

---

### BLK-SEC-04 — Backup automatizado dos dados de produção (parquets) + restore testado

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (continuidade de dados; não toca M1/score) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Origem** | revisão de robustez 2026-05-31 (BLK-OPS-01 cobre segredos, não dados) |

**Contexto / gap:** o BLK-OPS-01 entregou backup/DR dos **segredos**, mas os **dados** de produção
(`/opt/motor-expansao/data/outputs/`, ~1.6 GB de parquets do M1) hoje só têm "manter cópia local na
máquina de dev" como backup — manual e frágil. Não há snapshot periódico nem restore testado.

**Objetivo:** garantir recuperação dos parquets de produção após perda/corrupção, com restore provado.

**Escopo permitido:**
- Definir destino de backup (snapshot do provedor, bucket S3-compatível, ou cópia versionada off-box).
- Job agendado (cron na janela 2h–5h BRT, fora do pico) que faz snapshot dos `data/outputs/`.
- Política de retenção (ex.: diários 7d / semanais 4w) e verificação de integridade (checksum).
- **Restore testado** em pasta limpa (igual ao rigor do BLK-OPS-01) + runbook em `docs/`.

**Fora de escopo:** versionar parquets no git (são grandes/gerados); recalcular M1.

**Critérios de aceite:**
- Backup automatizado rodando com retenção definida; checksums conferem.
- Restore validado end-to-end (arquivos íntegros) e documentado.
- Sem PII em logs; sem dependência de API ao vivo no dashboard.

**Risco:** baixo. Atenção a custo/espaço do destino e a não competir com usuários (janela noturna).

**Atualização (2026-06-12, pós-deploy API/bot):** o conjunto de dados de produção cresceu além de
`data/outputs/`. Estender o escopo de backup para:
- **`data/ibge/`** (~49 MB, malha municipal) e **`data/staging/`** (~213 MB: `concorrentes_mapeados`,
  `unidades_ultra_mapeadas`, `hexagonos_mercado_mapeado`) — **obrigatórios para a API** (`data/ibge` é
  o que resolve lat,lng→município; sem ele a API dá 500). São regeneráveis, mas hoje só existem como
  cópia manual; incluir no snapshot evita re-scp lento.
- **Volume `bot_data`** (sessões do bot Telegram) — pequeno; perdê-lo só desloga os usuários (baixa
  prioridade, mas trivial de incluir).
- **Secrets do `.env`**: o `.env` ganhou `API_TOKENS`/`API_API_CALL_TOKEN`/`API_TELEGRAM_TOKEN`/
  `API_BOT_SENHA`/`API_IMAGE`. O backup de segredos é do **BLK-OPS-01** (SOPS+age) — sinalizar lá que o
  `.env` deve ser **re-encriptado** para capturar os novos segredos (cruza com BLK-OPS-01, não com este).

---

### BLK-SEC-05 — Observabilidade: monitoramento, alertas e runbook de incidente

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (contraparte detectiva dos controles preventivos; não toca M1/score) |
| **Prioridade** | **Média-Alta** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Origem** | revisão de robustez 2026-05-31 (ponto cego de detecção identificado) |

**Contexto / gap:** os blocos BLK-SEC-01..04 são **preventivos**; falta o lado **detectivo**. Hoje não
há como saber quando algo dá errado: sem alerta de uptime (queda do dashboard só é vista por
`docker logs` manual), sem alerta de segurança (tentativas de login no Authelia, disparos do
fail2ban — ver BLK-SEC-03, uso anômalo de CPU/memória/disco), e sem runbook de resposta a incidente
geral (o BLK-OPS-01 cobre só regeneração de segredos). Controle preventivo sem detecção é
meia-segurança: portas trancadas, mas sem alarme.

**Objetivo:** detectar e ser notificado de falhas e eventos de segurança em tempo hábil, e ter um
plano claro de resposta — proporcional a um dashboard interno (nada de SIEM/enterprise).

**Escopo permitido (leve, sem stack pesada):**
- **Uptime/health externo** do dashboard (ex.: monitor HTTP simples/UptimeRobot-like ou cron + alerta)
  com notificação (e-mail/webhook) quando cair.
- **Alertas de host:** disco cheio, memória/swap saturada, container reiniciando (reusa `docker stats`,
  `df -h` do runbook; transformar em check agendado com alerta).
- **Sinais de segurança:** expor/alertar disparos do fail2ban e falhas de login do Authelia
  (logs já existem; falta o alerta).
- **Retenção/rotação de logs** dos containers (evitar disco cheio por log infinito).
- **Runbook de incidente** em `docs/` (VPS comprometido / vazamento / indisponibilidade): passos de
  contenção, quem aciona, como isolar, e ligação com o DR de segredos (BLK-OPS-01) e o backup de
  dados (BLK-SEC-04).

**Fora de escopo:** SIEM, APM completo, tracing distribuído, on-call formal — exagero para o contexto.

**Arquivos prováveis:** `docs/infra_producao.md` (seção de monitoramento + runbook de incidente),
`docker-compose.prod.yml` (logging/retention), eventual script de health-check agendado.

**Critérios de aceite:**
- Queda do dashboard gera notificação comprovada (teste: derrubar o container num horário combinado).
- Alertas de disco/memória e de eventos de segurança (fail2ban/Authelia) configurados e testados.
- Rotação de logs ativa (sem crescimento ilimitado).
- Runbook de incidente documentado e revisado; zero mudança em M1/artefatos.

**Risco:** baixo. Cuidado para não gerar alarme ruidoso (calibrar limiares) nem expor segredos nos
canais de alerta.

**Atualização (2026-06-12, pós-deploy API/bot — ESCOPO ESTENDIDO):** este bloco foi escrito em
2026-05-31, **antes** da API GeoEspacial e do bot Telegram existirem; o uptime cobria só o dashboard.
Agora há 3 serviços a monitorar. Incluir no escopo de uptime/health:
- **Dashboard** (Streamlit): edge `https://dashboard.ultra-expansao.tech` (302→Authelia = vivo) e/ou
  `docker exec ... /_stcore/health` (porta 8501 não publicada no host).
- **API GeoEspacial**: `GET /health` na porta **8077** (interna `app_net`) → checar via
  `docker exec motor_expansao_api curl -fsS http://127.0.0.1:8077/health` (sem porta no host; cron na VPS).
- **Bot Telegram**: liveness = container `motor_expansao_telegram_bot` Up + log de polling sem erro
  (sem endpoint HTTP; checar `docker ps`/`docker logs`). Opcional: o cron pode bater no
  `/api/v1/analisar` com um token interno como smoke fim-a-fim.
- **Containers reiniciando** (`Restarting`/crash-loop) e o volume `bot_data`/disco — já no escopo de host.
Critério adicional: queda de **qualquer um dos 3** (dashboard, api, bot) gera notificação testada.
Nota de implementação: como api/bot não têm porta no host, o check mais simples é um **cron na própria
VPS** (`docker exec`/`docker ps`) com alerta por webhook/e-mail, em vez de monitor HTTP externo.

---

- BLK-ORQ-01 (concluído 2026-06-02) — ver tasks/completed.md


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

### BLK-PROD-03 — Avaliar hex_id como category com benchmark

Status: pendente
Criticidade: média
Prioridade: baixa
Tipo: performance
Skill recomendada: /run-cycle
Resumo: hex_id é chave de join; avaliar se category ajuda ou prejudica performance.
Requer benchmark antes de qualquer mudança.
Dependências: nenhuma

---

### BLK-PROD-02 — Limpar leftovers de staging

Status: pendente
Criticidade: baixa
Prioridade: baixa
Tipo: manutenção
Skill recomendada: /run-cycle
Resumo: Remover data/outputs/*.tmp.parquet e diretório tmp_codex_runtime/.
Dependências: aprovação explícita do usuário para remoção de arquivos.
Observações: não executar sem confirmação explícita. Risco de remoção indevida.

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

### BLK-PROD-06 — Relatório semanal de movimentação concorrencial

Status: pendente
Criticidade: alta
Prioridade: baixa
Tipo: feature / analytics
Skill recomendada: /run-cycle
Resumo: Snapshots, deltas por rede/cidade e impacto nas oportunidades.
Dependências: definição de fonte de dados concorrencial automatizável.

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

### BLK-TP-03 — Vazio competitivo do concorrente low-cost (feature/overlay)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (camada de visualização/análise; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir. |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — produto/UX]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-TP-01**. |
| **Autonomia** | candidato a **loop-safe** se restrito a análise/parquet; **manual** se virar overlay no dashboard (decisão de produto). |

**Objetivo.** Identificar hexes com demanda paga relevante a >5km do concorrente low-cost de referência
e **sem** unidade dele no hex — tese de entrada low-cost mais limpa (demanda comprovada, concorrente
direto ausente). Protótipo exploratório apontou ~231 hexes res-7 candidatos. Possível overlay no Mapa
Territorial (§5, camada visual de apoio — não altera score/ranking/carteira).

**Critérios de aceite.** Lista/camada de vazios competitivos reproduzível; READ-ONLY M1; suíte verde.
**Guardrail.** §5; pins/camadas de concorrente são apoio visual (CLAUDE.md §2).

---

### BLK-TP-04 — Calibração da curva tamanho→densidade do BLK-DIM com alunos/unidade

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (alimenta a modelagem de viabilidade; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir. |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — modelagem]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-TP-01** + epic **BLK-DIM** (DIM-03R/06). |
| **Autonomia** | **manual (NÃO loop-safe)** — decisão de modelagem. |

**Objetivo.** Usar `alunos_parceiras` (amostra real de alunos/unidade por tier; n≈27 mil no protótipo)
como insumo para calibrar/validar a curva tamanho→densidade do `viabilidade_ponto.py` (BLK-DIM), com a
disciplina metodológica da DEC-008 (LOO vs baseline; banir R² in-sample; intervalos + flag de
extrapolação). Liga-se à DEC-009 (dimensionamento é a parte que funciona; consome demanda, não a prevê).

**Critérios de aceite.** Curva calibrada/validada por LOO vs baseline, documentada; READ-ONLY M1.
**Guardrail.** §5; DEC-008/DEC-009.

---

- BLK-TP-05 (concluído 2026-06-30) — ver tasks/completed.md


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

### BLK-LTV-01 — Tabela-ponte `unidade_hex` (geocodificar unidades → H3 res-7)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (preparação de dados; **READ-ONLY sobre o M1**). |
| **Prioridade** | Alta (destrava o epic). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | — (insumos já no repo). |
| **Autonomia** | candidato **loop-safe** (READ-ONLY M1, sem VPS/deploy/segredos, sem PII, consome `data/ultra`+`data/staging`). |

**Objetivo.** Produzir `data/staging/unidade_hex.parquet` mapeando cada `COD_UNIDADE`/`UNIDADE` do
Lifetime → `lat`/`lng` → `hex_id` (H3 res-7, `H3_RESOLUTION=7`). Geocodificar por nome contra
`Ultra.csv` (147) com fallback ao `unidades_ultra_performance_hex.parquet` (54); fuzzy match com
verificação; emitir **relatório de qualidade de match** (casados exato/fuzzy/sem match, por UF e por
`CONFIABILIDADE_UNIDADE`). **Critérios de aceite.** Ponte reproduzível; % de cobertura reportado (não
silenciar não-casados); READ-ONLY M1; suíte verde. **Guardrail.** `Ultra.csv` = `sep=";"`,
`latin-1`, 1 linha de metadado (CLAUDE.md §2).

---

### BLK-LTV-02 — Join territorial (pendurar retenção/LTV no hexágono da unidade)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (join de dados; **READ-ONLY sobre o M1**). |
| **Prioridade** | Alta. |
| **Esteira** | Block Orchestrator → Planner → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-LTV-01**. |
| **Autonomia** | candidato **loop-safe**. |

**Objetivo.** Via `hex_id` da ponte, anexar a cada unidade as features territoriais do Motor
(`renda_per_capita`, densidade, `score_priorizacao`, `score_expansao_hibrido`,
`n_concorrentes_mapeados_1km/2km`, `pop_total_setor_2022`…) e as métricas de retenção agregadas
(`PROB_CANCEL_90D_MEDIA`, `LTV_PROSPECTIVO_12M_MEDIANO`), respeitando `USAR_PROB_ABSOLUTA`/haircut.
Entregável: `data/staging/unidade_territorio_retencao.parquet`. **Critérios de aceite.** 100% das
linhas do M1 preservadas nas leituras; nenhuma escrita em artefato M1; suíte verde.

---

### BLK-LTV-03 — Análise de correlação território × retenção/LTV `[GATE DE DECISÃO]`

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (gate de decisão do eixo; **READ-ONLY sobre o M1**). |
| **Prioridade** | Alta. |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — decisão do eixo]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-LTV-02**. |
| **Autonomia** | **manual (NÃO loop-safe)** — gate de decisão humano. |

**Objetivo.** Correlacionar território (renda, densidade, `score_priorizacao`, concorrência) ×
`PROB_CANCEL_90D_MEDIA` e `LTV_PROSPECTIVO_12M_MEDIANO`, **controlando por maturidade quando houver
dado** (ver caveat estrutural do epic). Método DEC-008: **Spearman + bootstrap/IC**, sem R² in-sample;
scatter + significância. **Gate de decisão:** correlação **fraca** → o epic vira consolidação de dados
(entrega LTV-01/02 como ativo, sem score); **forte** → avança para BLK-LTV-04. **Critérios de aceite.**
rho + IC bootstrap por par de variáveis, confounds declarados (maturidade, N, seleção de sobreviventes),
veredito GO/NO-GO honesto; READ-ONLY M1.

---

### BLK-LTV-04 — Score M2 territorial de retenção (SÓ se BLK-LTV-03 = GO) `[requer DEC + gate humano]`

| Campo | Valor |
|---|---|
| **Criticidade** | **Crítica/Estratégica** (cria um eixo de score novo). |
| **Prioridade** | Condicional ao GO do LTV-03. |
| **Esteira** | Block Orchestrator → Planner → `[APROVAÇÃO HUMANA + DEC]` → Builder → QA. |
| **Status** | Bloqueado (depende do gate de LTV-03). |
| **Depende de** | **BLK-LTV-03 = GO**. |
| **Autonomia** | **manual (NÃO loop-safe)** — cria score; exige DEC registrada. |

**Objetivo.** Compor um score de expansão paralelo (M2) ponderando captação + LTV/retenção territorial,
como **camada paralela READ-ONLY sobre o M1** (não altera `score_priorizacao`/pesos/artefatos; exige
**DEC** própria antes do Builder, análoga à disciplina da DEC-001/DEC-008). **Critérios de aceite.**
Definição de pesos aprovada em DEC; validação LOO/k-fold vs baseline; READ-ONLY M1; suíte verde.

---

## Projeto — Repaginação visual do dashboard (UX/UI)

- BLK-UI-11 (concluído 2026-06-29) — ver tasks/completed.md


---

### BLK-UI-10 — PoC de repaginação do dashboard: tema denso (baixo) + mapa Leaflet client-side (médio)

| Campo | Valor |
|---|---|
| **Criticidade** | **Baixa** (camada de **visualização/PoC**; **READ-ONLY sobre o M1**; não substitui o caminho de produção). |
| **Prioridade** | A definir por Felipe/Vini. |
| **Esteira** | Block Orchestrator → Planner → Builder → QA. No modo loop, o gate humano é substituído pelo guard automático (`scripts/loop_guard.py`). |
| **Status** | Pendente. |
| **Depende de** | — (consome parquets já existentes em `data/outputs`/`data/staging`). |
| **Autonomia** | **loop-safe** — READ-ONLY M1, sem VPS/deploy/segredos, sem PII, **sem dependência nova de base** (Leaflet/h3-js por CDN via `st.components.v1.html`, igual ao `NAO_ABRA/totalpass_final*.html`), consome só `data/outputs`/`data/staging`; ver `docs/loop_autonomo.md`. |

**Contexto.** Comparação feita em 2026-06-24 (Felipe): o HTML `NAO_ABRA/totalpass_final (72) (1).html`
é um SPA estático (Leaflet + h3-js por CDN, ~1.500 linhas, dados embutidos como arrays JS, 100%
client-side) — leve e bonito porque é *vitrine* de um recorte pré-cozido. O nosso Streamlit é o *motor*
(server-side, base nacional de 1,54 M hexes + malha censitária, re-roda o script a cada clique, pydeck
re-renderizado). O objetivo deste bloco é **provar**, sem reescrever o motor, dois ganhos do HTML:
(A) layout denso + tema escuro coeso e (B) mapa interativo client-side fluido. NÃO é migração para SPA;
é PoC opt-in atrás de flag, com o caminho de produção (pydeck/abas atuais) **intacto e default**.

**Objetivo.** Entregar um protótipo navegável e testado que demonstre:
- **Fase A (esforço baixo — tema/layout):** uma camada de tema (CSS injetado) + layout 3-painéis
  (faixa superior + painel esquerdo de KPIs/filtros + mapa + painel direito de resultado), com a
  densidade do HTML mas seguindo a **"Direção visual"** abaixo (NÃO copiar a paleta/tipografia do
  totalpass cru — ver porquê). Só estilo/estrutura de container — **zero** mudança em dados, score,
  ranking ou nas funções de cálculo.
- **Fase B (esforço médio — mapa client-side):** um mapa **Leaflet** renderizado via
  `st.components.v1.html` (CDN, sem pip novo) que consome um **recorte JSON enxuto por UF/cidade**
  pré-agregado a partir dos parquets existentes (padrão "dados embutidos" do HTML), com pan/zoom/clique
  fluidos **sem rerun do servidor**. Comparar peso percebido e responsividade vs. o pydeck atual num
  pequeno relatório (`data/reports/ui_poc_leaflet.md`).

**Escopo permitido (estritamente loop-safe).**
- Código novo isolado em `src/motor_expansao/dashboard/` (ex.: `ui_proto.py` + helper de tema), exposto
  como **página/aba OPT-IN atrás de um flag** (env/`session_state`), nunca como substituto do render
  atual. As funções de produção (`build_map_figure`, abas, pydeck) ficam **byte-a-byte preservadas**.
- O recorte JSON é uma **VIEW derivada read-only** dos parquets; gravar, se necessário, em
  `data/outputs/ui_proto/` (ou cache `data/cache/`), **nunca** como artefato oficial do M1 (não entra na
  lista do §3/`docs/m1_outputs_oficiais.md`) e **sem PII**.
- Testes novos (render do tema sem erro, geração do recorte JSON determinística, fallback quando o
  parquet/UF não existe). Suíte verde.

**Direção visual (destilada da skill `frontend-design` — embutida aqui para o loop NÃO depender do
plugin; o container do loop tem `$HOME` próprio e não enxerga o `~/.claude` do host).**
O agente deve seguir estes tokens como decisão tomada, não reinventar. O `totalpass` é referência de
**densidade e ergonomia** (3 painéis, cards compactos, mono nos números), **não** de paleta: o "dark +
verde-ácido" dele é um dos defaults genéricos de IA. Ancore na **identidade real da Ultra** e no motivo
do produto (o hexágono H3).

- **Subject / tese.** Não é "mais um dashboard escuro": é a **sala de controle da expansão territorial**
  de uma rede low-cost/massa (CLAUDE.md §1). O herói da tela é o **mapa**, não um número grande.
- **Paleta (4–6 tokens; dark por legibilidade de mapa, mas NÃO o verde do totalpass).** Use a cor da
  marca Ultra como acento único e reserve magenta para semântica de concorrente — convenção que o
  projeto **já** usa (`Ultra=turquesa, conc.=magenta`, BLK-EST-02). Sugestão de tokens (o agente pode
  refinar a partir dos assets em `data/ultra/`, mas mantendo a semântica):
  `--bg:#0b1016` (fundo carvão-azulado, mais quente que o `#080c14` do totalpass) ·
  `--panel:#121a24` · `--line:#1f2c3a` · `--ultra:#1fd1c4` (turquesa Ultra = acento/ações/ativo) ·
  `--conc:#ff3d8b` (magenta = SÓ concorrente) · `--text:#dce6f0` / `--muted:#7d97ad`.
  Score/faixas de mapa continuam usando `RESIDUAL_SCORE_BANDS`/faixas GeoFusion já canônicas — a
  paleta de UI é a moldura, não recolore dado.
- **Tipografia (par deliberado, NÃO o Inter/JetBrains default do totalpass; tudo via Google Fonts CDN,
  loop-safe).** Display/títulos: **Space Grotesk** (caráter técnico/cartográfico, combina com "motor").
  Corpo/UI: **IBM Plex Sans** (pedigree de engenharia, distinto do Inter). Dados (hex_id, lat/lng,
  scores, m²): **IBM Plex Mono** — mono é justificável aqui porque o dado **é** o subject. Escala de
  tipo clara (ex.: 11/13/18/30) com pesos intencionais.
- **Signature (a UMA coisa memorável).** O **hexágono H3** é o motivo do produto inteiro — use-o como
  assinatura: cards de KPI com canto/recorte hexagonal sutil ou um marcador hex no lugar do "dot"
  genérico de legenda. Gaste a ousadia só aqui; o resto fica quieto e disciplinado (conselho "tire um
  acessório antes de sair").
- **Estrutura é informação, não decoração.** Nada de numeração 01/02/03 decorativa — só se houver
  sequência real. Eyebrows/labels devem codificar algo verdadeiro (UF, faixa, tese de entrada).
- **Cópia (microcopy) na voz do operador.** Rótulos pelo que a pessoa controla ("Filtrar por UF",
  "Gerar relatório"), voz ativa, sentence case, mesmo verbo do início ao fim do fluxo. Estado vazio é
  convite à ação ("Selecione um município no mapa"), erro diz o que houve e como resolver — sem
  apologia nem mood.
- **Piso de qualidade (sem alarde).** Responsivo até telas estreitas, foco de teclado visível,
  `prefers-reduced-motion` respeitado (anima no máximo a carga inicial/hover — excesso de animação
  cheira a "gerado por IA"). Contraste AA no texto sobre os painéis.
- **Anti-default checklist (rodar antes de fechar a Fase A).** (1) A paleta NÃO é o verde-ácido do
  totalpass nem cream+serif+terracota nem broadsheet hairline? (2) O par tipográfico não é o que eu
  usaria em qualquer projeto? (3) Existe UMA assinatura (hex) e o resto é contido? (4) Algum elemento
  decora sem significar? Se sim, corte. Anotar o que foi escolhido e por quê no relatório do bloco.

**Fora de escopo (NÃO fazer — manteria fora do loop-safe).** Tocar `config.py`, `pipelines/m1`,
qualquer `*scoring*`/artefato oficial do M1, `Dockerfile.streamlit`/compose/Caddy/CI/`.env`/`secrets/`;
**adicionar dependência de base** ao `pyproject.toml` (Leaflet/h3-js vêm de CDN no HTML embutido);
deploy ao VPS; recalcular score/ranking/carteira/plano; persistir qualquer PII; substituir o caminho de
produção do dashboard. Promover o PoC a default é **decisão humana** num bloco sucessor.

**Critérios de aceite.**
- Fase A: tema + layout 3-painéis renderizam numa página opt-in; produção (pydeck/abas) inalterada e
  ainda default; teste de smoke do render verde. A **"Direção visual"** foi seguida (paleta turquesa
  Ultra + magenta só-concorrente, par Space Grotesk/IBM Plex, assinatura hexagonal) e o **anti-default
  checklist** está respondido no relatório do bloco.
- Fase B: mapa Leaflet client-side carrega um recorte JSON de ≥1 UF, com clique→detalhe sem round-trip;
  recorte gerado de forma reprodutível e sem PII; relatório curto comparando peso/responsividade.
- READ-ONLY M1 comprovado (zero diff em score/pesos/artefatos oficiais); **nenhuma** dep nova de base;
  suíte verde; `loop_guard.py` não acusa toque em caminho proibido.

**Guardrail.** §2 (sem dependência de API ao vivo na carga do dashboard — o CDN do Leaflet só carrega no
PoC opt-in, com fallback gracioso, espelhando a mitigação da DEC-004); §5 (visualização não recalcula
nem altera M1); §6.1 (critérios loop-safe). Precedente de desvio cosmético restrito a um caminho: DEC-004.

---
