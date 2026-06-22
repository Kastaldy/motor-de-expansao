# Backlog

## Priorização atual

Próximo ciclo recomendado: **BLK-API-01 — Definir arquitetura e contrato da API (G1)** — bloco de
design/decisão **Estratégico** com gate humano para as 6 decisões-chave de contrato (formato de saída,
auth, escopo de endpoints, entrada, raio, reprodutibilidade). Pré-requisito de G2/G3/G4. Só docs,
READ-ONLY M1. Ver seção "Projeto — API GeoEspacial".
Em paralelo (trilha do Vini, dashboard/PDF/UX): BLK-FIX-07..11, BLK-SAM-01, BLK-EST-01/02, BLK-UI-01.
BLK-CENSO-01/02/03 (refino do Relatório Pontual Censitário): **concluídos** (ver tasks/completed.md).

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

### BLK-DIM-18 — Fix: faixa de alunos pela metragem ausente em produção (fallback para parquet de unidades)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (feature completamente invisível em prod; sem dado exibido no campo) |
| **Prioridade** | **Alta** — fix de produção |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Status** | Pendente |
| **Autonomia** | NAO LOOP SAFE, Mexe em Produção e VPS
| **Depende de** | — |

**Contexto / por que existe:** `load_base_calibracao()` em `streamlit_app.py` lê `data/staging/base_calibracao_multirede.parquet` — arquivo gerado pelo pipeline `base_multirede.py` (BLK-DIM-07/08) que **não existe em produção** (não foi regenerado após o pivô DEC-009). Por isso a seção "Faixa de alunos plausível pela metragem" sempre cai no `st.info("indisponível")`. O arquivo `data/staging/unidades_ultra_performance_hex.parquet` (54 unidades Ultra com `metragem` e `alunos_reais`) **sempre existe** e serve como fallback direto.

**Objetivo:** adicionar fallback na `load_base_calibracao()` para, quando o multirede não existir, tentar o `unidades_ultra_performance_hex.parquet` (que tem as mesmas colunas `metragem` e `alunos_reais` já consumidas pela função).

**Escopo permitido:**
- `streamlit_app.py`, função `load_base_calibracao()`: após verificar `BASE_CALIBRACAO_PATH.exists()`, tentar `STAGING_DIR / "unidades_ultra_performance_hex.parquet"` como fallback antes de retornar `pd.DataFrame()`.
- Derivar `alunos_por_m2` no fallback (mesma lógica já existente).
- Atualizar ou adicionar 1 teste cobrindo o caminho de fallback.

**Fora de escopo (invioláveis):** regenerar o multirede (outro ciclo), tocar `viabilidade_ponto.py`/`simulador.py`, M1, artefatos oficiais.

**Critérios de aceite:** com apenas `unidades_ultra_performance_hex.parquet` presente, a faixa p10/p50/p90 é exibida no dashboard; suite verde; nenhuma coluna M1 alterada.

**Arquivos prováveis:** `streamlit_app.py` (função `load_base_calibracao`), `tests/`.

**Risco:** baixo — READ-ONLY; só adiciona um path de fallback sem remover o caminho atual.

---

- BLK-DIM-19 (concluído 2026-06-22) — ver tasks/completed.md


---

### BLK-DIM-20 — UI: parâmetros de fluxo de caixa editáveis (capex parcelado — equipamentos e tecnologia)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (enriquece o simulador financeiro; READ-ONLY sobre M1) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Autonomia** | **loop-safe** — READ-ONLY sobre M1; toca só `simulador.py`, `viabilidade_ponto.py`, `pages.py`, testes; sem VPS/deploy/segredos/PII/ingestão ao vivo. NÃO toca `config.py` do M1 nem `dimensionamento/config.py` (constantes novas ficam nos próprios módulos). |
| **Depende de** | **BLK-DIM-19** (teto de payback e display corretos antes de expandir parâmetros) |

**Contexto / por que existe:** hoje o investimento inicial (capex) entra como lump-sum no mês 0, e o payback é calculado contra o FCF acumulado. Na prática, equipamentos e tecnologia são **parcelados** (planilha Ultra: 36 meses, juros 1,8% a.m.). O simulador atual não tem esse custo mensal de financiamento, então o payback simulado é otimista. Felipe quer que o operador possa configurar esses parâmetros.

**Objetivo:** adicionar ao simulador financeiro e à UI os parâmetros de financiamento do capex, calculando a PMT mensal como custo adicional durante o prazo de parcelamento.

**Escopo permitido:**

*`simulador.py` — novos parâmetros em `viabilidade()`:*
- `capex_financiado_pct: float = 0.0` — % do capex financiado (0 = tudo próprio, padrão atual).
- `prazo_financiamento_meses: int = 36` — prazo de parcelamento (default da planilha).
- `juros_financiamento_am: float = 0.018` — taxa mensal (default 1,8% a.m.).
- PMT mensal calculada via `pmt = C * r * (1+r)^n / ((1+r)^n - 1)` onde `C = capex_efetivo * capex_financiado_pct`. A PMT entra no loop de payback como custo financeiro nos meses `1..prazo_financiamento_meses` (abaixo da linha do EBITDA — não altera `margem_ebitda_pct`, só o `fcf_t` e o payback).

*`viabilidade_ponto.py`:* pass-through dos 3 novos parâmetros em `analisar_viabilidade_ponto()` e em `grade_sensibilidade()`.

*`pages.py` — expander "Parâmetros avançados":*
- `capex_total` (`st.number_input`, default `SIM_CAPEX_DEFAULT = 2.340.000`).
- `pct_financiado` (`st.slider`, 0–100%, default 0%).
- `prazo_financiamento_meses` (`st.number_input`, default 36, visível só se `pct_financiado > 0`).
- `juros_am_pct` (`st.number_input`, default 1,8%, visível só se `pct_financiado > 0`).
- Caption explicando: "Equipamentos e tecnologia parcelados conforme planilha padrão (36 meses, 1,8% a.m.). A PMT entra como custo financeiro no FCF (não altera EBITDA)."

**Fora de escopo (invioláveis):** `config.py` do M1, `dimensionamento/config.py`, pesos/formula/artefatos M1, cálculo de `margem_ebitda_pct` (EBITDA é pré-financiamento, conforme spec §8.2).

**Critérios de aceite:** com `pct_financiado > 0`, o payback aumenta em relação ao cenário sem financiamento (efeito esperado); `margem_ebitda_pct` inalterada entre os dois cenários (a PMT não entra no EBITDA); grade de sensibilidade propagada corretamente; suite verde.

**Arquivos prováveis:** `src/motor_expansao/dimensionamento/simulador.py`, `src/motor_expansao/dimensionamento/viabilidade_ponto.py`, `src/motor_expansao/dashboard/pages.py`, `tests/`.

**Risco:** baixo-médio — a PMT é cálculo determinístico; o risco é introduzir regressão no payback sem financiamento (deve ficar idêntico ao atual quando `pct_financiado = 0`).

---

### BLK-DIM-21 — UI: gráficos financeiros e curva de maturidade na aba de viabilidade

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (enriquecimento visual; READ-ONLY sobre M1) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Autonomia** | **loop-safe** — READ-ONLY sobre M1; toca só `simulador.py`, `pages.py`, testes; usa `plotly` já dep (`plotly>=5.20.0`); sem VPS/deploy/segredos/PII/ingestão ao vivo. NÃO toca `config.py` do M1 nem `dimensionamento/config.py`. |
| **Depende de** | **BLK-DIM-19** (payback/flag corretos), **BLK-DIM-20** (parâmetros de fluxo de caixa disponíveis para refletir nos gráficos) |

**Contexto / por que existe:** a aba de viabilidade hoje exibe só métricas estáticas (cards). Felipe quer visualizações financeiras — curva de maturidade, faturamento projetado e payback visual — para facilitar a leitura do cenário. Felipe tem um exemplo visual de referência (compartilhar antes da execução do Builder para calibrar layout/cores).

**Objetivo:** adicionar 4 gráficos Plotly à seção de resultados da viabilidade, mantendo os cards existentes e usando cores Ultra (turquesa `#00BFB3`, cinza-escuro `#2E3040`, branco, com vermelho para negativo).

**Escopo permitido:**

*`simulador.py` — nova função `gerar_serie_mensal()`:*
Extrai a lógica do loop interno de maturação e retorna `list[dict]` com campos:
`mes`, `alunos_balcao`, `faturamento_mensal`, `ebitda_mensal`, `fcf_acumulado`.
A assinatura espelha a de `viabilidade()` para receber os mesmos parâmetros (incluindo os novos do BLK-DIM-20). NÃO duplica lógica — o loop existente em `viabilidade()` pode delegar para esta função.

*`pages.py` — 4 gráficos via `st.plotly_chart(..., use_container_width=True)` após os cards:*
1. **Curva de maturidade**: linha `alunos_balcao` por mês (1–60), com linha tracejada de steady-state e anotação do ponto de maturação. Título: "Rampa de alunos (balcão)".
2. **Faturamento e EBITDA mensal**: barras empilhadas por mês (faturamento bruto) + linha sobreposição de EBITDA. Faturamento em turquesa; EBITDA positivo em verde, negativo em vermelho.
3. **FCF acumulado**: área preenchida por mês; linha horizontal em 0; anotação do payback (ponto onde FCF ≥ 0). Área positiva em turquesa translúcido, negativa em vermelho translúcido.
4. **DRE breakdown (steady-state)**: barras horizontais empilhadas mostrando: faturamento → deduções → impostos → custos variáveis → custos fixos (pessoal + outros) → aluguel → EBITDA. Útil para entender onde vai a margem.

Todos os gráficos com fundo branco/cinza-claro, fonte legível, sem borda excessiva — padrão Ultra Clean (referência: BLK-EST-02 do relatório censitário).

**Fora de escopo (invioláveis):** `config.py` do M1, `dimensionamento/config.py`, score/pesos/artefatos M1, alterar os cards existentes (preservar métricas numéricas), adicionar dependências além do plotly já disponível.

**Critérios de aceite:** 4 gráficos renderizados sem erro para qualquer combinação válida de inputs; FCF acumulado mostra visualmente o ponto de payback; curva de maturidade termina no steady-state; suite verde (testes de smoke do módulo `simulador.py` para `gerar_serie_mensal`).

**Arquivos prováveis:** `src/motor_expansao/dimensionamento/simulador.py` (nova função), `src/motor_expansao/dashboard/pages.py`, `tests/`.

**Risco:** baixo — plotly disponível; o risco principal é regressão de performance (carregar 4 charts no Streamlit). Mitigação: renderizar só após submit do formulário (já é o comportamento atual dos cards).

---

### BLK-DIM-22 — UI: exportar simulador de viabilidade como Excel

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (novo entregável; READ-ONLY sobre M1) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Autonomia** | **loop-safe** — READ-ONLY sobre M1; toca só `pages.py` + novo módulo `dimensionamento/excel_export.py`; usa `openpyxl` já dep (`openpyxl>=3.1.0`); sem VPS/deploy/segredos/PII/ingestão ao vivo. NÃO toca `config.py` do M1 nem `dimensionamento/config.py`. |
| **Depende de** | **BLK-DIM-19** (payback/flag corretos), **BLK-DIM-20** (parâmetros de fluxo de caixa), **BLK-DIM-21** (série mensal disponível em `ViabilidadeResult` para exportar a curva) |

**Contexto / por que existe:** o operador precisa levar o resultado do simulador para reuniões/decisões fora do dashboard. Felipe quer o export no template padrão Ultra (cores turquesa/branco/cinza-escuro), equivalente ao "ULTRA padrão - Simulador Financeiro.xlsx" mas preenchido com os dados do ponto analisado.

**Objetivo:** botão `st.download_button` que gera, em memória, um `.xlsx` com 4 abas com visual Ultra, sem tocar artefatos M1 nem persistir em disco no servidor.

**Escopo permitido:**

*Novo arquivo `src/motor_expansao/dimensionamento/excel_export.py`:*
- Função `gerar_excel_viabilidade(result: ViabilidadePontoResult, *, nome_ponto: str = "") -> bytes`.
- 4 abas com `openpyxl`:
  - **"Resumo"**: cabeçalho com logo/nome Ultra (texto), ponto analisado (lat/lng/m²/aluguel/demanda), KPIs (break-even, aluguel-teto, margem EBITDA, payback, ROIC, faturamento, EBITDA, flag viável). Fundo de cabeçalho turquesa `#00BFB3`, texto branco; linhas de dado em branco/cinza-claro alternados.
  - **"DRE"**: tabela linha-a-linha do DRE no steady-state (faturamento bruto → deduções → receita líquida → impostos → custos variáveis → custos fixos → EBITDA → IR/CSLL → lucro líquido). Formatação monetária `R$ #.##0,00`. Fonte dos valores: campos do `ViabilidadeResult`.
  - **"Sensibilidade"**: grade alunos × aluguel com `margem_liq` — células coloridas (verde para margem ≥ 10%, amarelo para 0–10%, vermelho para negativo). Reproduz a tabela que já existe no dashboard.
  - **"Curva"**: série mensal (meses 1–60) com colunas `Mês`, `Alunos Balcão`, `Faturamento`, `EBITDA`, `FCF Acumulado`. Dados de `gerar_serie_mensal()` (BLK-DIM-21). Se a série não estiver disponível, omitir a aba com nota.
- Retorna `bytes` (não escreve em disco no servidor — LGPD/anti-PII).

*`pages.py` — após os gráficos:*
- `st.download_button("⬇ Exportar Excel", data=excel_bytes, file_name=f"viabilidade_{lat:.4f}_{lng:.4f}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")`.
- Gerar os bytes via `gerar_excel_viabilidade(result, nome_ponto=endereco_resolv_se_disponivel)`.

**Fora de escopo (invioláveis):** `config.py` do M1, score/pesos/artefatos M1, escrever em disco no servidor (`to_excel(path)` proibido — usar `BytesIO`), incluir dados PII de alunos reais.

**Critérios de aceite:** download gera arquivo `.xlsx` válido abrível no Excel/LibreOffice; 4 abas presentes; cores Ultra aplicadas; valor da grade de sensibilidade idêntico ao exibido no dashboard; suite verde (teste de smoke: `len(gerar_excel_viabilidade(result)) > 0`).

**Arquivos prováveis:** `src/motor_expansao/dimensionamento/excel_export.py` (novo), `src/motor_expansao/dashboard/pages.py`, `tests/`.

**Risco:** baixo — openpyxl disponível; risco de formatação complexa (colorir células condicional). Mitigação: começar com formatação simples e refinar após validação visual de Felipe.

---

- BLK-OPS-11 (concluído 2026-05-31) — ver tasks/completed.md


---

- BLK-SEC-01 (concluído 2026-06-01) — ver tasks/completed.md


---

- BLK-SEC-02 (concluído 2026-06-02) — ver tasks/completed.md

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
