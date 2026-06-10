# Backlog

## Priorização atual

Próximo ciclo recomendado: **BLK-API-01 — Definir arquitetura e contrato da API (G1)** — bloco de
design/decisão **Estratégico** com gate humano para as 6 decisões-chave de contrato (formato de saída,
auth, escopo de endpoints, entrada, raio, reprodutibilidade). Pré-requisito de G2/G3/G4. Só docs,
READ-ONLY M1. Ver seção "Projeto — API GeoEspacial".
Em paralelo (trilha do Vini, dashboard/PDF/UX): BLK-FIX-07..11, BLK-SAM-01, BLK-EST-01/02, BLK-UI-01.
BLK-CENSO-01/02/03 (refino do Relatório Pontual Censitário): **concluídos** (ver tasks/completed.md).

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

### BLK-FIX-07 — Overlays do mapa territorial não funcionando

> ⚠️ **SUPERSEADO por BLK-FIX-11 (2026-06-09)** — ver seção "Novos blocos". A tarefa ClickUp `86e1rtefy`
> passa a ser rastreada pelo **BLK-FIX-11** (Alternativa A: fiar os 3 overlays mortos). Mantido aqui só por histórico.

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (display/render; READ-ONLY sobre M1) |
| **Prioridade** | **Alta** (urgent no ClickUp) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA das decisões visuais]` → Builder → QA |
| **Status** | Pendente |
| **Responsável sugerido** | Vini |
| **ClickUp** | `86e1rtefy` — https://app.clickup.com/t/86e1rtefy |

**Contexto / hipótese:** as camadas de overlay do Mapa Territorial (toggles de concorrentes/Ultra/score)
não renderizam ou não respondem ao controle. Hipótese: regressão no controle de camadas/`pydeck` em
`src/motor_expansao/dashboard/pages.py` (`render_mapa_territorial`) ou nos builders de layer em
`components.py` (filtro de `scope`/cap de pontos descartando o overlay antes do render — eco do
BLK-FIX-06-C). Planner confirma se é toggle de UI, layer pydeck ou dado ausente.

**Objetivo:** restaurar a exibição e o controle dos overlays no Mapa Territorial.

**Escopo permitido:** `pages.py`/`components.py` (controle e build de camadas), testes de
`test_streamlit_app.py`. Só display/interação.

**Fora de escopo:** recalcular score/carteira/plano; alterar artefatos M1; mudar o cap de pontos sem aprovação.

**Critérios de aceite:** overlays aparecem e respondem ao toggle; teste cobrindo a camada antes invisível;
suíte + ruff + mypy verdes; READ-ONLY M1 comprovado (git scope vazio em pipelines/scoring.py/config.py).

**Guardrail:** visualização não recalcula nem altera M1 (§5).

---

### BLK-FIX-08 — SAM não calcula em alguns hexágonos/municípios (RR, AC e outros)

> ⚠️ **SUPERSEADO por BLK-SAM-01 (2026-06-09)** — ver seção "Novos blocos". A tarefa ClickUp `86e1rte9n`
> passa a ser rastreada pelo **BLK-SAM-01** (redefine o gate do SAM: Faixa M1 + pop ≥ 5000), que **absorve**
> a preocupação de cobertura (fallback de pop em RR/AC/AM). Mantido aqui só por histórico.

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (altera valor da camada PARALELA de mercado/residual; **não** é M1 oficial, mas exige revisão) |
| **Prioridade** | **Alta** (urgent no ClickUp) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Responsável sugerido** | Vini |
| **ClickUp** | `86e1rte9n` — https://app.clickup.com/t/86e1rte9n |

**Contexto / hipótese:** `sam_fitness_potencial` fica vazio/zerado em UFs de baixa cobertura censitária
(RR, AC, AM — exatamente as de supressão IBGE/classe C). Hipótese: o fallback de `pop_hex_base`
(`pop_total_setor_2022` → `populacao_proxy / total_hex_municipio`) não cobre esses hexes, ou `cod_municipio`
ausente quebra o join da camada de mercado. Planner confirma a origem no cálculo do mercado
(`calcular_colunas_mercado` / `hexagonos_mercado_mapeado.parquet`).

**Objetivo:** SAM calculado (ou marcado explicitamente como "sem base", não silenciosamente vazio) nessas UFs.

**Escopo permitido (camada PARALELA, não M1 oficial):** cálculo de mercado/residual e seu fallback de
população; se houver regeneração de parquets paralelos, seguir a **ordem canônica** (hibrido → mercado →
`calcular_colunas_mercado` → carteira → plano → dominio → residual → `fase1_bi_exports`).

**Fora de escopo (inviolável):** `score_priorizacao`/`hex_score_estrutural`/pesos/artefatos oficiais do M1
(DEC-001 vigente); inventar população onde não há base auditável.

**Critérios de aceite:** SAM presente ou rotulado em RR/AC/AM com causa documentada; repro de ≥1 hex antes
quebrado; parquets paralelos regenerados de forma reprodutível se necessário; ZERO escrita em M1 oficial;
suíte + ruff + mypy verdes.

**Guardrail:** não toca o M1 oficial; mudança restrita à camada de mercado/residual paralela.

---

### BLK-FIX-09 — Remover "BYD" do PDF de estudos

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (conteúdo do relatório; READ-ONLY sobre M1) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Responsável sugerido** | Vini |
| **ClickUp** | `86e1rtebk` — https://app.clickup.com/t/86e1rtebk |

**Contexto / hipótese:** entrada espúria "BYD" (marca não-fitness) aparece no PDF de estudos — provavelmente
um pin/logo de POI ou registro indevido na base de concorrentes (`concorrentes/` logos/Unidades) ou no
lookup do relatório. Planner localiza a origem (dado vs render).

**Objetivo:** o "BYD" não aparece mais no PDF/relatório.

**Escopo permitido:** `src/motor_expansao/dashboard/censo_report.py` / `censo_map.py` (filtro de render) e/ou
saneamento da fonte de concorrentes consumida pelo relatório.

**Fora de escopo:** alterar score/artefatos M1; mexer no método de interseção/raio 1.5 km.

**Critérios de aceite:** PDF sem "BYD"; teste cobrindo a exclusão; suíte verde; READ-ONLY M1.

**Guardrail:** relatório é camada de visualização (§5).

---

### BLK-FIX-10 — Diminuir tamanho da pré-visualização dos estudos

| Campo | Valor |
|---|---|
| **Criticidade** | **Baixa** (layout/UX; READ-ONLY sobre M1) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Status** | Pendente |
| **Responsável sugerido** | Vini |
| **ClickUp** | `86e1rteea` — https://app.clickup.com/t/86e1rteea |

**Contexto / hipótese:** a pré-visualização do estudo no dashboard renderiza grande demais. Hipótese:
`st.image`/container de preview sem largura controlada em `pages.py`.

**Objetivo:** preview em tamanho adequado (largura/altura controladas), sem afetar o PDF exportado.

**Escopo permitido:** layout do preview em `pages.py` + teste de smoke.

**Fora de escopo:** alterar o PDF final; score/artefatos M1.

**Critérios de aceite:** preview menor/legível; export inalterado; suíte verde; READ-ONLY M1.

---

### BLK-EST-01 — Marca d'água + nome do usuário solicitante nos PDFs

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (rastreabilidade/LGPD + identidade do solicitante no documento) |
| **Prioridade** | **Alta** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Responsável sugerido** | Vini |
| **ClickUp** | `86e1rteq7` — https://app.clickup.com/t/86e1rteq7 |
| **Relacionado** | ClickUp `86e1rtezm` (logs de rastreio LGPD, do Felipe) |

**Contexto:** anexar marca d'água + nome do usuário que solicitou o estudo no PDF, para rastreabilidade
(base LGPD). A identidade do solicitante vem da sessão autenticada (Authelia). Coordenar com a tarefa de
logs LGPD do Felipe para padronizar a fonte do "solicitante".

**Objetivo:** todo PDF gerado carrega marca d'água + nome do solicitante de forma legível e não removível trivialmente.

**Escopo permitido:** `src/motor_expansao/dashboard/censo_report.py` (composição do PDF sobre `fpdf2`);
passar o identificador do solicitante pelo caminho de geração.

**Fora de escopo:** versionar PDFs reais (PII); embutir o cartão de contato `image24.png` (anti-PII, §4);
score/artefatos M1.

**Critérios de aceite:** marca d'água + solicitante presentes no PDF; fonte do nome definida e testada;
sem PII versionada; compressão de stream OFF preservada (auditabilidade anti-PII); suíte verde; READ-ONLY M1.

**Guardrail:** anti-PII do §4 preservado; sem dependência de API ao vivo.

---

### BLK-EST-02 — Melhorar visual e template dos estudos automatizados

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (template/visual; READ-ONLY sobre M1) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA das decisões visuais]` → Builder → QA |
| **Status** | Pendente |
| **Responsável sugerido** | Vini |
| **ClickUp** | `86e1rteju` — https://app.clickup.com/t/86e1rteju |
| **Depende de** | precedência do BLK-CENSO-02/03 (template `fpdf2` 16:9 + 7 páginas já estabelecido) |

**Contexto:** evoluir o template/visual dos estudos (continuação do BLK-CENSO-02/03). Decisões visuais
**exigem gate humano** do Felipe (precedente dos ciclos CENSO). Cada iteração visual implica rebuild de
imagem + redeploy por digest na VPS + assets de branding no volume (footgun BLK-CENSO-02).

**Objetivo:** template mais limpo/profissional, mantendo as 7 páginas e o conteúdo READ-ONLY.

**Escopo permitido:** `censo_report.py` / `censo_map.py` + assets de branding em `data/ultra/` (gitignored).

**Fora de escopo:** recalcular qualquer score; método de interseção/raio; PII no PDF.

**Critérios de aceite:** visual aprovado por Felipe (gate); 7 páginas e Big Numbers READ-ONLY preservados;
suíte verde; READ-ONLY M1; deploy registrado.

**Guardrail:** §5 (visualização) + §4 (anti-PII) + DEC-004 (basemap só na geração).

---

### BLK-UI-01 — Refatoração UX/UI da plataforma Motor de Expansão

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (mexe na navegação/estrutura do dashboard de produção; READ-ONLY sobre M1) |
| **Prioridade** | **Média** (estratégico — exige planejamento antes de executar) |
| **Esteira** | Block Orchestrator → Planner (design detalhado) → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente (não iniciar sem plano aprovado) |
| **Responsável sugerido** | Vini |
| **ClickUp** | `86e1rtey2` — https://app.clickup.com/t/86e1rtey2 |

**Contexto:** refatoração ampla de UX/UI das 4 abas (Visão Executiva, Mapa Territorial, Expansão de
Domínio, Carteira e Plano). Por ser amplo e tocar muitos arquivos do dashboard, requer **plano detalhado +
gate humano** antes de execução, e fatiamento em sub-blocos para não colidir com os bugs acima.

**Objetivo:** melhorar usabilidade/consistência visual sem regressão de funcionalidade nem do M1.

**Escopo permitido:** `dashboard/` (pages/components/utils/constants visuais), preservando carga lazy por UF,
render lazy de abas e fonte de mapa enxuta (Blocos 4–6).

**Fora de escopo:** score/pesos/artefatos M1; recolocar dependência de API ao vivo; quebrar os contratos de
performance já entregues.

**Critérios de aceite:** plano aprovado antes de codar; sem regressão funcional (suíte verde); UX validada
por Felipe; READ-ONLY M1.

**Guardrail:** §5 (visualização) + preservar otimizações de performance do dashboard.

---

## Novos blocos (2026-06-09, pedido de Felipe)

> Dois blocos derivados da análise de código com Felipe em 2026-06-09: (1) redefinição das condições
> do SAM (`BLK-SAM-01`) e (2) correção concreta dos overlays mortos do Mapa Territorial (`BLK-FIX-11`,
> Alternativa A). Ambos têm bloco "irmão" mais antigo/vago no backlog — ver a nota "Relacionado" em cada um.
> Causas-raiz abaixo estão **ancoradas no código** (file:line), confirmadas em leitura de 2026-06-09.

### BLK-SAM-01 — Redefinir condições de cálculo do SAM (Faixa M1 + população ≥ 5000)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (altera o VALOR da camada PARALELA de mercado/residual; **não** é M1 oficial, mas redefine semântica → exige revisão humana) |
| **Prioridade** | **Alta** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA das decisões de produto]` → Builder → QA |
| **Status** | Pendente |
| **Responsável sugerido** | Vini |
| **ClickUp** | `86e1rte9n` — https://app.clickup.com/t/86e1rte9n |
| **Relacionado** | **Supersede o BLK-FIX-08** (mesma tarefa ClickUp `86e1rte9n`, "SAM não calculando…"): este bloco é a versão precisa/decidida; BLK-FIX-08 marcado como superseado. **Absorve** a preocupação de cobertura do BLK-FIX-08 — fallback de população em UFs de baixa cobertura censitária (RR/AC/AM): rotular SAM como "sem base" em vez de zerar silenciosamente quando não há população auditável (ver decisão #2). |

**Contexto / estado atual (ancorado no código):** hoje o SAM é gateado em
`src/motor_expansao/pipelines/calcular_colunas_mercado.py` por:
- `flag_sam = flag_viavel & top_municipio & ~flag_canibalizacao_ultra_1km` (≈ linha 274);
- `flag_sam_fitness = flag_sam & (tam_populacao_hex > 0)` (≈ linha 279);
- `sam_fitness_potencial = where(flag_sam_fitness, tam_fitness_potencial, 0.0)` (≈ linha 280).

Consequência observada: hexes com **boa Faixa M1** podem ter `sam_fitness_potencial = 0` por estarem fora do
top_municipio, canibalizados, ou sem `tam_populacao_hex > 0` (sem limiar mínimo de população).

**Objetivo (pedido de Felipe):** o SAM deve ser calculado **para hexes nas Faixas M1
`baixa`, `media`, `alta` e `prioridade_maxima`** (ou seja, excluindo `descartado` e `inviavel`), **e** que
contenham **pelo menos 5000 de população**. Hexes fora dessas faixas ou abaixo de 5000 hab → SAM = 0
(ou rótulo explícito "sem base"), sem zeragem silenciosa por outras causas.

**Decisões de produto — TODAS RESOLVIDAS por Felipe em 2026-06-09** (registrar como nova DEC no CLAUDE.md §8 na execução; o Builder implementa direto, sem novo gate de produto):
1. **[RESOLVIDO por Felipe, 2026-06-09]** Gate redefinido assim: **manter** `~flag_canibalizacao_ultra_1km`
   como filtro; **substituir** `top_municipio` pelos novos critérios — **Faixa M1 ∈ {baixa, media, alta,
   prioridade_maxima}** *e* **pop ≥ 5000**. Resultado pretendido:
   `flag_sam = faixa_oportunidade.isin({baixa,media,alta,prioridade_maxima}) & (pop_corte ≥ 5000) & ~flag_canibalizacao_ultra_1km`
   (sobre o campo de população decidido em #2). Consequência aceita da remoção do `top_municipio`:
   o SAM passa a ser calculado **fora do recorte M1** (municípios não-top), desde que faixa+pop satisfaçam.
   **Sub-decisão do `flag_viavel` — [RESOLVIDA por Felipe, 2026-06-09]:** **manter** `flag_viavel` como guarda
   adicional. Motivo (verificado nos dados 2026-06-09): `flag_viavel` **não** embute piso de 5000 — sua parte de
   população é só `hex_sem_populacao=False` (= `populacao_proxy ≥ 1`); logo **não é redundante** com a nova regra
   e não a entrega sozinho. A **única** sobreposição é a faixa (`flag_viavel` já exige faixa ∉ {descartado,inviavel},
   = o mesmo conjunto {baixa,media,alta,prioridade_maxima}); mantê-lo é inofensivo e **preserva de brinde o filtro de
   renda** (`renda_target_proxy ≥ RENDA_MIN`). Gate efetivo: `flag_viavel & faixa∈{…} & (pop_corte ≥ 5000) & ~canibal`.
2. **[RESOLVIDO por Felipe, 2026-06-09] Campo de população do corte de 5000 = `populacao_corte_hex` / `flag_pop_min_5k`**
   (a régua operacional `POP_MIN_ACIONAVEL=5000` que o dashboard **já tem**, em `data.py::derive_pop_cut_columns`:
   setor 2022 quando granular, fallback total municipal `pop_total`). **NÃO** usar `pop_hex_base`/`tam_populacao_hex`.
   Justificativa (medido nos dados de 2026-06-09): `pop_hex_base` é a população do setor **rateada por hexágono**
   (mediana nacional ≈ **5** hab; **97,4%** dos 196.715 hexes com SAM>0 têm `pop_hex_base < 5000`) — cortar 5000 sobre
   ela **aniquilaria ~97% do SAM**. A régua `populacao_corte_hex` é a noção de "5k habitantes" pretendida (no recorte
   SP, só ~14% dos hexes com SAM>0 a passam — filtro forte, não aniquilador). **Atenção de implementação:**
   `populacao_corte_hex`/`flag_pop_min_5k` hoje são derivados na **camada do dashboard** (`data.py`), não na de mercado;
   o Builder precisa torná-los disponíveis em `calcular_colunas_mercado` (mover/compartilhar `derive_pop_cut_columns`
   ou recomputar a mesma regra no pipeline), sem duplicar a lógica de forma divergente.
3. **[RESOLVIDO] Limiar inclusivo `≥ 5000`** (conforme "pelo menos 5000"); coerente com `flag_pop_min_5k` (`.ge(5000)`).

**Escopo permitido (camada PARALELA, não M1 oficial):** o gate do SAM em `calcular_colunas_mercado.py`
(`flag_sam`/`flag_sam_fitness`/`sam_fitness_potencial`) e, se necessário, parâmetro do limiar 5000 em
`config.py`/`constants.py`. Se houver regeneração de parquets paralelos, seguir a **ordem canônica**:
híbrido → mercado → `calcular_colunas_mercado` → carteira → plano → domínio → residual → `fase1_bi_exports`.

**Fora de escopo (inviolável):** `score_priorizacao`/`hex_score_estrutural`/pesos/`faixa_oportunidade`/
artefatos oficiais do M1 (DEC-001 vigente; a Faixa M1 é **lida**, não recalculada); inventar população onde
não há base auditável.

**Critérios de aceite:**
- SAM calculado exatamente para Faixa M1 ∈ {baixa, media, alta, prioridade_maxima} **e** população ≥ 5000
  (campo confirmado no gate); demais hexes com SAM = 0 ou rótulo explícito.
- As 3 decisões acima resolvidas e registradas (idealmente como nova DEC no CLAUDE.md §8).
- Repro de ≥1 hex que **passa a calcular** e ≥1 que **passa a zerar** sob a nova regra, com causa documentada.
  **Repro de referência (verificado nos dados de 2026-06-09)** — hex `87a91b18dffffff` (Santo Amaro da Imperatriz/SC):
  hoje tem `sam_fitness_potencial ≈ 7,28` (SAM>0) porque passa em tudo (`flag_viavel=True`, `top_municipio=True`,
  `canibal=False`, faixa `prioridade_maxima`, `score_priorizacao=75,84`) e o gate atual só exige `tam_populacao_hex>0`
  (= **35,4** hab, setor 2022 rateado). Sob a nova regra, `populacao_corte_hex = 35,4` → `flag_pop_min_5k=False`
  → **SAM deve passar a 0**. É o caso canônico de "pop < 5000 com SAM" que motivou o bloco.
- Parquets paralelos regenerados de forma reprodutível, se necessário; **ZERO escrita em M1 oficial**.
- Suíte + ruff + mypy verdes (incluindo testes novos do gate em `tests/integration/test_modelo_mercado_hexagonos.py`).

**Guardrail:** não toca o M1 oficial; mudança restrita à camada de mercado/residual paralela (§4/§5).

---

### BLK-FIX-11 — Tornar funcionais os 3 overlays "mortos" do Mapa Territorial (Alternativa A)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (display/interação; READ-ONLY sobre M1) |
| **Prioridade** | **Alta** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA das decisões visuais]` → Builder → QA |
| **Status** | Pendente |
| **Responsável sugerido** | Vini |
| **ClickUp** | `86e1rtefy` — https://app.clickup.com/t/86e1rtefy |
| **Relacionado** | **Supersede o BLK-FIX-07** (mesma tarefa ClickUp `86e1rtefy`, "Overlays do mapa territorial não funcionando"). Leitura de 2026-06-09: `concorrentes`/`ultra` **funcionam**; os 3 abaixo é que estão mortos. BLK-FIX-07 marcado como superseado. |

**Contexto / causa-raiz (ancorada no código):** o registro `OVERLAYS` em
`src/motor_expansao/dashboard/constants.py` (≈ linha 394) declara **5 overlays** e o multiselect
`render_mapa_territorial` (`pages.py` ≈ linha 2733) os expõe todos. Porém, no dispatcher
`build_unified_map_figure` (`components.py` ≈ linhas 2953-2957) e na legenda `_render_unified_legend`
(`pages.py` ≈ linhas 1816-1819) **apenas `"concorrentes"` e `"ultra"`** são lidos de `enabled_overlays`.
Os outros três aparecem no multiselect mas marcar/desmarcar **não muda nada no mapa**:
- **`hex_pesquisado`** — `search_pin`/`search_hex_id` são passados **incondicionalmente** aos builders
  (`pages.py` ≈ linhas 2766-2767); o id `"hex_pesquisado"` nunca é consultado.
- **`descartados_5k`** — a coloração de descartados é aplicada **sempre** dentro dos builders quando existe
  `flag_pop_min_5k` (`components.py` ≈ linhas 505, 527, 1117); `"descartados_5k"` nunca é lido. *(Nota: o
  `absent_behavior` dele é `show_neutral`, indício de que a fiação foi prevista e não concluída.)*
- **`ancoras_dominio`** — `"ancoras_dominio"` nunca é desenhado como camada de mapa; as únicas ocorrências
  são um KPI e a contagem radial, não o multiselect.

**Objetivo:** **Alternativa A** — fazer os 3 toggles funcionarem de verdade:
- `hex_pesquisado`: só passar/renderizar o pin e o hex pesquisado quando `"hex_pesquisado" in enabled_overlays`.
- `descartados_5k`: propagar a flag aos builders e **pular** a coloração/camada de descartados <5k quando
  desmarcado (mantendo o comportamento atual quando marcado).
- `ancoras_dominio`: desenhar de fato uma camada de âncoras de domínio (a partir do `dominio_df`) quando
  marcado; ocultar quando desmarcado.

**Escopo permitido:** `components.py` (gate de `enabled_overlays` no dispatcher + builders; nova camada de
âncoras), `pages.py` (passar `enabled_overlays`/`dominio_df` ao caminho de busca e descartados; legenda
coerente com o que está ligado), `constants.py` se ajustar `OVERLAYS`, e testes em
`tests/integration/test_streamlit_app.py`. Só display/interação.

**Fora de escopo:** recalcular score/carteira/plano; alterar artefatos M1; mudar o cap de pontos
(`MAP_POINT_LIMIT*`/`COMPETITOR_PIN_LIMIT`/`ULTRA_PIN_LIMIT`) sem aprovação.

**Critérios de aceite:**
- Marcar/desmarcar **Hex pesquisado**, **Descartados <5k hab** e **Âncoras Domínio** muda o mapa de forma
  visível e coerente com a legenda; `concorrentes`/`ultra` seguem funcionando (sem regressão).
- Teste cobrindo cada um dos 3 overlays antes inertes (ligado vs desligado → camada presente/ausente).
- Suíte + ruff + mypy verdes; READ-ONLY M1 comprovado (git scope vazio em `pipelines/`/`scoring.py`/`config.py`).
- Decisão registrada sobre encerrar/superseder **BLK-FIX-07**.

**Guardrail:** visualização não recalcula nem altera M1 (§5).

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

### BLK-API-01 — Definir arquitetura e contrato da API (G1)

| Campo | Valor |
|---|---|
| **Criticidade** | **Estratégica** (nova fase: stand-up de uma API; redesenho de superfície de consumo do motor) |
| **Prioridade** | **Alta** (urgent no ClickUp; G1 é pré-requisito de G2/G3/G4) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — decisões-chave de contrato]` → Builder → QA |
| **Status** | Pendente |
| **Responsável sugerido** | Felipe |
| **ClickUp** | `86e1rtfe3` — https://app.clickup.com/t/86e1rtfe3 (subtarefa de `86e1rtfcy`) |
| **Toca dados/artefatos** | **Não** (bloco de design; só docs) |

**Contexto:** G1 é a fundação do projeto API. É um bloco **de design/decisão, sem código de produção** —
produz o contrato e o ADR que destravam G2 (backend) e definem em quantos blocos o resto se quebra. O
scaffold FastAPI já existe em `fora_primeira_fase/api_postgis/` (`main.py` esqueletado) e o extra `[api]`
já está no `pyproject.toml`; G1 decide o que dele se aproveita e o layout final em `src/motor_expansao/api/`.

**Objetivo:** entregar um contrato de API aprovado por Felipe, suficiente para o Juan implementar G2 sem
re-discussão de arquitetura, e um ADR registrando as decisões.

**Entregáveis (Builder escreve, após o gate):**
- `docs/api_geoespacial_contrato.md` — contrato técnico: layout do pacote `src/motor_expansao/api/`,
  fronteira "importa-não-edita `censo_*`", lista de endpoints, schemas de request/response, auth, erros,
  versionamento, e a **decomposição de G2+ em blocos** (`BLK-API-02..0N` com escopo de cada um).
- Esboço **OpenAPI** dos endpoints do MVP (arquivo `docs/api_geoespacial_openapi.yaml` ou bloco no contrato).
- **ADR** (estilo das DECs do CLAUDE.md §8) registrando as decisões-chave abaixo, para entrar como nova DEC.
- Atualização mínima do README/PRD apontando para o contrato (sem implementar a API).

**Escopo permitido:** `docs/` (contrato + OpenAPI + ADR), `tasks/`, e edição de texto do README/PRD.
**NENHUM** código de produção neste bloco.

**Fora de escopo:** implementar rotas/handlers; subir container; PostGIS; integração Telegram/WhatsApp
(G4); qualquer escrita em `src/motor_expansao/` (exceto, se decidido no gate, criar a pasta `api/` **vazia**
com `__init__.py` como marcação de layout — sem lógica); recalcular/alterar M1 (§5).

**Decisões que EXIGEM gate humano** (o Planner apresenta cada uma com as opções e sua recomendação;
**Felipe decide no Passo 5 antes do Builder**; o Builder só redige o contrato com as escolhas confirmadas):

1. **Formato de saída da API** *(ponto-chave citado por Felipe)*
   - (a) JSON estruturado com os KPIs do ponto (leve, bot renderiza a mensagem).
   - (b) PDF binário (o relatório de 7 páginas) inline na resposta.
   - (c) **[recomendado]** Ambos por negociação — `/analisar` retorna JSON por padrão e `?formato=pdf`
     (ou `Accept: application/pdf`) devolve o relatório; reaproveita `analisar_ponto_censitario_setores`
     + `gerar_pdf_relatorio_pontual_censitario`.
   - (d) JSON + link para o PDF gerado sob demanda.

2. **Autenticação** (uso interno + bots)
   - (a) API key estática por header (`X-API-Key`) — mais simples.
   - (b) **[recomendado]** Token por consumidor/bot — permite rastrear **quem** pediu o estudo (casa com
     BLK-EST-01: marca d'água + solicitante no PDF / logs LGPD).
   - (c) Reuso do Authelia/JWT já em produção.

3. **Superfície de endpoints do MVP** (define quanto G2 entrega)
   - (a) **[recomendado]** Mínimo: `GET /health` + `POST /analisar` (ponto censitário 1.5 km).
   - (b) Acrescentar lookup de hex M1 / camada de mercado já no MVP.
   - → A escolha alimenta diretamente a decomposição de `BLK-API-02..0N`.

4. **Entrada de coordenada**
   - (a) Apenas `{lat, lng}`.
   - (b) **[recomendado]** `{lat, lng}` **e** link do Google Maps (parser extrai a coordenada) — os bots
     receberão link colado pelo usuário (o roadmap do PDF prevê "parser de links Maps").

5. **Raio de análise no MVP**
   - (a) **[recomendado]** Fixo 1.5 km (igual ao Relatório Pontual Censitário — motor intocado).
   - (b) Parametrizável (exige validar limites e revalidar o método de interseção).

6. **Carimbo de versão/reprodutibilidade**
   - **[recomendado]** Incluir a versão do contrato/score no JSON e no rodapé do PDF (item de
     reprodutibilidade do PDF estratégico), para estudos antigos seguirem interpretáveis.

**Critérios de aceite:** contrato + OpenAPI + ADR escritos e coerentes entre si; todas as 6 decisões acima
resolvidas e registradas no ADR com a opção escolhida; decomposição de G2+ em blocos explícita; fronteira
"importa-não-edita `censo_*`" e "on-demand, PostGIS fora do MVP" registradas; **zero código de produção**
(git scope só em `docs/`, `tasks/`, `README.md`/`PRD.md`); suíte + ruff + mypy verdes (bloco de docs não
deve quebrar nada); READ-ONLY M1 comprovado (sem escrita em `pipelines/`/`config.py`/scoring).

**Guardrail:** §2 (fontes canônicas) + §5 (READ-ONLY M1) + §6 (deploy/VPS é humano — não se aplica aqui,
pois G1 não faz deploy). API ao vivo no dashboard de produção **não** é introduzida por este bloco.

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
| **Criticidade** | **Alta** (LEITURA/ANÁLISE + engenharia de dados; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Depende de** | **BLK-SCORE-02**, **BLK-SCORE-03 (DEC-001)**, **BLK-SCORE-04** |
| **Status** | Pendente |
| **Origem** | pergunta do usuário "dá para modelar demanda potencial por hex?" (2026-05-31) |

**Contexto / por que existe:** BLK-SCORE-02/04 mostraram que NÃO é possível, hoje, treinar um modelo
preditivo confiável de demanda. Três bloqueios estruturais: (1) **viés de seleção** — o único
desfecho (`alunos_recorrentes`) só existe onde JÁ há unidade; não há observação de demanda em hexes
vazios (sem contrafactual); (2) **alvo enviesado/ruidoso** — desfecho pós-seleção e pós-maturação,
sem `maturacao_status` real, heterogêneo entre redes; (3) **sinal exógeno ≈ nulo** — features de
mercado/competição com IC cruzando zero, OLS conjunto R²≈0.034; o sinal que sobra é endógeno (rede
própria). Conclusão: o gargalo é de DADOS, não de algoritmo. Este bloco é o **pré-requisito de
engenharia de dados ANTES de qualquer modelagem** — NÃO é um bloco de ML.

**Objetivo:** avaliar, read-only, a VIABILIDADE de obter (a) um sinal de **maturação** por unidade
(data de abertura ou proxy auditável) e (b) ao menos um **proxy de demanda EXÓGENO** — independente
da existência de academia no hex. Entregar um diagnóstico de disponibilidade/qualidade de fontes +
recomendação GO/NO-GO para um futuro bloco de modelagem, SEM construir modelo nem alterar score.

**Escopo permitido (read-only, diagnóstico):**
- Inventariar fontes candidatas de demanda exógena e checar cobertura/granularidade por hex/município:
  - **Penetração Wellhub/Gympass** (já há `sinal_wellhub`, `n_parcerias_wellhub` no dataset de
    validação — medir cobertura e se é exógeno ou colado a unidades existentes);
  - dados de **mobilidade/fluxo** ou **busca/intenção** (avaliar se há fonte acessível offline/legal,
    sem criar dependência de API ao vivo — guardrail do projeto);
  - sinais demográfico-comportamentais já no censo/IBGE não usados (faixa etária, vínculo formal,
    renda do trabalho) que correlacionem com propensão a academia.
- Avaliar viabilidade de **maturação**: existe data de abertura por unidade (Ultra real; concorrentes
  via mapeamento)? Que proxy auditável (ex.: primeira aparição em snapshot) seria aceitável?
- Estimar, com o que houver, se algum proxy exógeno tem correlação não-trivial com `alunos_recorrentes`
  CONTROLANDO maturação (reusar `analysis/score_backtest.py`/`feature_backtest_mercado.py`).
- Produzir relatório `data/analysis/viabilidade_demanda.md` (gitignored) com: matriz de fontes ×
  (cobertura, granularidade, exógena S/N, custo/risco de obtenção), achado de correlação controlada
  (se viável), e **recomendação GO/NO-GO** para um eventual `BLK-SCORE-06 — modelo de demanda`.

**Fora de escopo (invioláveis):**
- Construir/treinar qualquer modelo preditivo (isso seria o BLK-SCORE-06, só com GO + seu gate).
- Qualquer escrita/recálculo de M1 (`scoring.py`/`constants.py`/pesos/artefatos) — DEC-001 vigente.
- Criar dependência de API ao vivo no dashboard de produção (guardrail do CLAUDE.md).
- Inventar proxy de maturação/idade sem base auditável (lição do BLK-SCORE-02 §5).
- Saída fora de `data/analysis/`; qualquer PII (`nome_unidade`) no relatório.

**Arquivos a ler:** `data/analysis/relatorio_backtest.md`, `data/analysis/relatorio_backtest_mercado.md`,
`data/analysis/dataset_validacao.parquet` (colunas `sinal_wellhub`/`n_parcerias_wellhub`/`maturacao_status`),
`CLAUDE.md` §8 (DEC-001) e §4 (camadas), `analysis/feature_backtest_mercado.py` (reuso).
**Arquivos a alterar (read-only sobre M1):** novo script de diagnóstico em `analysis/` + testes
sintéticos; relatório em `data/analysis/` (gitignored). NENHUM artefato M1.

**Critérios de aceite:**
- Relatório `data/analysis/viabilidade_demanda.md` com matriz de fontes + veredito GO/NO-GO fundamentado.
- Diagnóstico explícito de maturação (disponível? proxy aceitável?) e de pelo menos 1 proxy exógeno.
- Se houver correlação controlada, reportada com incerteza (IC, N, confounds); sem forçar significância.
- ZERO escrita em M1/artefatos oficiais; ZERO PII; reprodutível (seed fixo; script versionado).

**Guardrails específicos:** READ-ONLY sobre M1; diagnóstico de viabilidade, NÃO modelagem; sem
dependência de API ao vivo; alimenta a decisão sobre os gates G1/G2/+contrafactual da DEC-001.

**Risco:** baixo (read-only). O valor é evitar investir em ML sobre dados que não identificam demanda;
o entregável é um GO/NO-GO honesto, não um modelo.

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
