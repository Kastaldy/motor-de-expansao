# Contrato — Enriquecimento de Vulnerabilidade para M&A (Plano B)

> **[canônico]** contrato dos sinais de vulnerabilidade de academias independentes (funil de M&A).
> Responsável: Felipe Silva | Estratégia e Growth | Ultra Academia
> Versão: 2026-07-23 (BLK-MA-01 — design/contrato; **ZERO código de produção**)
> Regra de manutenção: manter curto; a implementação é dos blocos sucessores BLK-MA-02..07.

Este documento fixa o contrato dos sinais de vulnerabilidade de concorrentes independentes, a
metodologia do **score de vulnerabilidade** (heurística transparente, **não** modelo preditivo) e o
registro das decisões de produto D1–D8 confirmadas no gate humano de 2026-07-23 (Vinicius). É a
especificação que os blocos BLK-MA-02..06 vão implementar; nenhum extrator, score, join, entregável
ou cron é escrito neste bloco.

---

## 1. Cabeçalho, status e guardrails invariantes

- **Camada PARALELA, READ-ONLY sobre o M1 (§5).** O `score_vulnerabilidade` é um score de negócio para
  o funil de aquisição (M&A); **não** é `score_priorizacao` nem `hex_score_estrutural`. Este trabalho
  **não** recalcula nem altera pesos do M1 (`renda=0.40`/`pop=0.60`), `score_priorizacao`,
  `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou qualquer artefato oficial do
  M1. Imposto por código (`scripts/loop_guard.py` + `.github/workflows/guard.yml`).
- **Anti-PII por construção (DEC-012).** Só agregados por `hex_id` (H3 res-7); geometria deriva do
  `hex_id`, nunca da coordenada GPS bruta; a fonte real nunca é versionada (gitignored); os testes usam
  fixtures **sintéticas**. Detalhe na seção 11.
- **Extensão do lote de scrapers (DEC-013), não pipeline novo.** O enriquecimento consome o histórico de
  snapshots dos 90 coletores já automatizados na VPS; o recompute do score entra como **passo** do
  runner semanal já pré-aprovado (`run_weekly_90.sh`), não como cron novo. Detalhe na seção 12.
- **Sem API externa ao vivo (§2).** O Plano B usa **apenas** fontes internas já coletadas + o diff dos
  snapshots semanais. **Não há dependência de API externa** e, portanto, **este bloco NÃO cria DEC**. O
  dashboard segue offline sobre Parquets locais. Qualquer rota de reputação pública externa (Google
  Places) fica no sucessor opcional **BLK-MA-07**, com gate e DEC próprios — único ponto onde o desvio
  do §2 pode reaparecer.
- **Acentuação (§2).** Prosa em português acentuado; **identificadores, valores de enum e nomes de
  coluna em ASCII** (ex.: `score_oportunidade_residual`, `oferta_efetiva_disponivel`,
  `sam_fitness_potencial`, `hex_id_res7`, `concorrente_id`, `abrir_agora`, `independente`,
  `flag_serie_imatura`). CSV do projeto sempre `sep=";"` / `encoding="utf-8-sig"`.

---

## 2. Objetivo do epic + a INVERSÃO da tese de M&A

**Objetivo.** Produzir uma lista priorizada de alvos de **aquisição (M&A)**: academias independentes
**vulneráveis** (candidatas a fechar ou a serem compradas) situadas em **mercado quente** (onde a Ultra
tem demanda e interesse de presença). É um funil comercial, não uma decisão de score do M1.

> ### INVERSÃO da tese (registrar em destaque — load-bearing para o BLK-MA-05)
> **Comprar (M&A) NÃO é o mesmo que abrir.** Abrir uma unidade nova quer **residual ALTO** (mercado com
> capacidade não atendida). Comprar quer o **OPOSTO**: **demanda ALTA + residual BAIXO (mercado
> saturado)** — é justamente onde já não cabe abrir, mas cabe adquirir quem já opera. Logo o BLK-MA-05
> **NÃO** deve reutilizar a lógica de `tese_entrada = "abrir_agora"` (que exige `flag_white_space`
> e residual alto). O cruzamento com o "hexágono quente" da seção 9 é deliberadamente invertido.

---

## 3. D1 — Universo de "academia independente" e a fonte que retém identidade

**Decisão do gate (D1 = FASEADO).**

- **MVP = hex-level agregado (Opção A, 100% anti-PII).** O entregável do MVP é agregado por hexágono:
  "hexes com concentração de independentes vulneráveis perto de mercado quente" — só categorias,
  contagens e flags, sem identidade de estabelecimento. **Entra já** em BLK-MA-02/04/05, sem bloqueio.
- **Nomeação por-academia (Opção B) = DEFERIDA** atrás de confirmação (BLK-MA-03).
- **Nuance factual (a registrar).** O **nome** do estabelecimento **EXISTE** nos CSVs brutos TP/WH: em
  `src/motor_expansao/demanda_revelada/concorrentes_densos.py`, a função `_ler_csv_tp_wh` (linha 127) lê
  a coluna `nome` (linhas 130–138), usa-a **só em memória** para classificar a rede e a **descarta na
  fronteira** — a saída (linhas 139–141) é apenas `hex_id_res7` / `rede_normalizada` / `fonte`. Portanto
  a lista NOMEADA é **VIÁVEL no futuro** via extensão de ingestão que **retenha**
  `nome_estabelecimento` + `hex_id_res7`. O nome/endereço de um estabelecimento comercial é **dado de
  NEGÓCIO público**, distinto da PII de reviewer/funcionário que a DEC-012 protege. O artefato nomeado é
  então **gitignored** (fonte real fora do versionamento).
- **Definição de "independente".** Academia do universo raspado que **NÃO** é uma das 28 cadeias de
  `concorrentes_mapeados` (classificação `independente` do classificador, **ou** marca com contagem de
  unidades `== 1`). **Reconciliar "28 scrapers legados vs 90 coletores da DEC-013"** quando o BLK-MA-02
  materializar o universo (os independentes de bairro vivem nos agregadores WellHub/TotalPass; a camada
  anti-PII colapsa tudo `< 3 filiais` em `independente`, categoria sem identidade — daí a Opção B exigir
  a extensão de ingestão).

---

## 4. Contrato dos 6 sinais

Sinais 1–4 são obrigatórios; 5 e 6 são opcionais (fora do MVP). Direção `↑vuln` = quanto maior o valor
bruto do sinal, maior a vulnerabilidade. Todo componente normalizado `vi ∈ [0,1]` tem `1 = máxima
vulnerabilidade` (seção 8).

| # | Sinal | Direção ↑vuln | Fonte real | Coluna / artefato | Maturidade | Tratamento n/d / imaturo | Condicional? |
|---|---|---|---|---|---|---|---|
| 1 | Presença/ausência em agregadores WellHub/TotalPass | menos agregadores → mais vuln (canal do público low-cost) | ingestão TP/WH (reuso via `fonte`) | derivada da `fonte` do universo raspado | madura (cadência mensal do agregador) | ausência **é** o sinal (0 agregadores); staleness do ativo mensal marcada | Não (obrigatório) |
| 2 | Rating in-app WellHub/TotalPass | nota mais baixa → mais vuln | **CSVs brutos TP/WH (não retidos hoje)** | `rating` — **`n/d` PERMANENTE no Plano B** | inativo no MVP | renormaliza para fora (seção 8) | **Sim** — `n/d` permanente (ver seção 7 / D3); só reativa em BLK-MA-07 |
| 3 | Churn/permanência (diff de snapshots) | sumiu recente / "piscando" → mais vuln | histórico de snapshots (seção 6) | derivada de `concorrente_id` entre semanas | imatura até `MIN_SEMANAS=8` | série imatura → `flag_serie_imatura`, renormaliza (não penaliza) | Não (obrigatório, gated por maturidade) |
| 4 | Staleness (diff de snapshots) | mais semanas sem mudança → mais vuln | histórico de snapshots (`hash_campos_raspados`) | `semanas_sem_mudanca` | só interpretável após série `>= STALE_SEMANAS=12` | série imatura → renormaliza (não penaliza) | Não (obrigatório, gated por maturidade) |
| 5 | Tendência de popularidade no agregador | inclinação negativa de membros → mais vuln | série do agregador / Demanda Revelada | `membros` / `alunos_parceiras` | precisa de série; fora do MVP | fora do MVP → renormaliza | **Sim** (opcional) |
| 6 | Pressão competitiva (independente espremida) | pressão maior → mais vuln | camada de mercado | `pressao_concorrencial_score_2km` (`hexagonos_mercado_mapeado.parquet`) | madura | fora do MVP → renormaliza | **Sim** (opcional) |

---

## 5. Mapa "4 sinais originais → Plano B"

Os quatro sinais concebidos originalmente (a partir da ideia de agregadores + reviews) mapeiam para os
sinais do Plano B assim:

| Sinal original | Sinal(is) do Plano B |
|---|---|
| Avaliação média (nota in-app) | **(2)** rating in-app |
| Δ de reviews em 3 meses | **(3)** churn/permanência + **(5)** tendência de popularidade |
| Presença em agregadores | **(1)** presença/ausência em agregadores |
| Última atualização do cadastro | **(4)** staleness |

Consequência: com o **D3 = Não** (seção 7), o sinal 2 fica `n/d` permanente no Plano B, e o "Δ de
reviews" é aproximado pelos sinais internos (3) e (5), sem depender de nota externa.

---

## 6. D2 — Snapshots semanais (churn + staleness)

**Decisão do gate (D2 = default do Planner).**

- **Chave.** Snapshot semanal chaveado por `concorrente_id` (sha1 já existente de `rede|nome|lat|lng`).
- **Payload por linha (sem crus além do hash).**
  `{snapshot_date, concorrente_id, hex_id_res7, rede, hash_campos_raspados}` — **sem** nome/coordenadas
  brutas; a única "impressão digital" dos campos raspados é o `hash_campos_raspados`.
- **Local / retenção.** `data/staging/snapshots_concorrentes/semana=AAAA-SS/parte-*.parquet`
  (**gitignored**, vive na VPS). Retenção rolante **26 semanas** (6 meses).
- **Derivação dos sinais.**
  - Churn (sinal 3): o `concorrente_id` aparece / some / reaparece ("piscando") entre semanas.
  - Staleness (sinal 4): nº de semanas desde a última mudança de `hash_campos_raspados`.
- **Ramp-up / maturidade.** `flag_serie_imatura = True` até `MIN_SEMANAS = 8` snapshots; enquanto
  imatura, os sinais 3/4 **NÃO penalizam** (são renormalizados para fora do score — seção 8). Staleness
  só é interpretável após a série atingir `STALE_SEMANAS = 12`. Mitiga falso churn no início da série
  (o cron acumula snapshots desde ~26/06/2026).

---

## 7. D3 — Rating de agregador (sinal 2)

**Decisão do gate (D3 = NÃO carregam a nota).**

- **Fato de código.** Os CSVs brutos TP/WH **não** têm rating no caminho de ingestão atual:
  `_ler_csv_tp_wh` (`concorrentes_densos.py:127`) produz **só** `hex_id_res7` / `rede_normalizada` /
  `fonte`; qualquer nota estaria no ruído textual descartado na fronteira.
- **Consequência.** O **sinal 2 fica `n/d` PERMANENTE no Plano B.** O framework o mantém **DEFINIDO**
  (por completude do contrato), porém **INATIVO no MVP** — o score do Plano B roda em **S1 / S3 / S4**
  renormalizados (seção 8). O `n/d` do sinal 2 **NÃO trava** BLK-MA-03/04.
- **Onde a reputação/nota volta.** Qualquer sinal de reputação — nota in-app, se um dia surgir uma fonte
  que a carregue, **ou** reputação externa (Google Places) — é consolidado na trilha **BLK-MA-07**
  (opcional/futuro, com gate + DEC próprios). Esse é o único ponto onde o desvio do §2 reaparece.

---

## 8. D4 — Score de vulnerabilidade (metodologia)

**Decisão do gate (D4).** Heurística ponderada, normalizada e **AUDITÁVEL**. **NÃO é modelo preditivo**
(sem treino em desfecho; validar que o score "prevê" aquisição/fechamento seria bloco próprio sob a
DEC-008, com LOO/k-fold vs baseline, sem R² in-sample).

### 8.1 Componentes `vi ∈ [0,1]` (`1 = máxima vulnerabilidade`)

- `v1` — presença em agregador: `0` agregadores → `1.0`; `1` → `0.5`; `2` → `0.0`.
- `v2` — rating in-app (CONDICIONAL, `n/d` permanente no Plano B): `1 − normaliza(rating)`, ex.:
  `1 − (rating − 1) / (5 − 1)`; `n/d` → renormaliza para fora.
- `v3` — churn/permanência: sumiu recente → `1.0`; "piscando" (some/reaparece) → `0.7`; estável →
  `0.0`.
- `v4` — staleness: `min(semanas_sem_mudanca / STALE_SEMANAS, 1)`; série imatura → renormaliza para fora.
- `v5` (opcional) — tendência de popularidade: inclinação negativa de `membros` / `alunos_parceiras`
  normalizada; entra só quando a série permitir.
- `v6` (opcional) — pressão competitiva: `pressao_concorrencial_score_2km / 100` (independente
  espremida); coluna já materializada em `hexagonos_mercado_mapeado.parquet`.

### 8.2 Normalização

**Percentil por universo** (robusto a outliers) para os sinais contínuos (rating, staleness,
popularidade, pressão); flags graduados para os categóricos (S1/S3). Tudo em `[0,1]`, com `↑ = ↑vuln`.

### 8.3 Pesos

Pesos-alvo dos 4 obrigatórios (somam `1,00`):

| Sinal | Peso-alvo |
|---|---|
| S1 (presença) | 0,15 |
| S2 (rating) | 0,25 |
| S3 (churn) | 0,35 |
| S4 (staleness) | 0,25 |

**Churn (S3) domina** — é o proxy mais forte de fechamento/venda.

**Pesos EFETIVOS no Plano B** (S2 fora por D3 → **RENORMALIZAÇÃO** dos 3 restantes, dividindo pela soma
`0,15 + 0,35 + 0,25 = 0,75`):

| Sinal | Aritmética | Peso efetivo |
|---|---|---|
| S1 | 0,15 / 0,75 | ≈ 0,20 |
| S3 | 0,35 / 0,75 | ≈ 0,467 |
| S4 | 0,25 / 0,75 | ≈ 0,333 |

Conjunto maduro de 6 sinais (ilustrativo, soma `1,00`): `S1=0,12 · S2=0,20 · S3=0,28 · S4=0,20 ·
S5=0,10 · S6=0,10`.

### 8.4 Sinal ausente / imaturo

**RENORMALIZAR** (dropar o peso do sinal ausente/imaturo e reescalar os restantes para somar `1`) — mais
auditável que imputar um neutro `0,5`. Flags de qualidade obrigatórias:

- `n_sinais_disponiveis` — quantos sinais entraram no score da linha;
- `flag_serie_imatura` — a série de snapshots ainda não atingiu `MIN_SEMANAS`;
- `flag_score_provisorio` — quando S3 **e** S4 estão imaturos e o score depende só de S1 (e S2 quando
  ativo).

### 8.5 Saída

`score_vulnerabilidade ∈ [0,100] = 100 · Σ(wi · vi)` com os pesos **renormalizados**, acompanhado dos
componentes `vi` por sinal (para auditoria) e das flags de qualidade.

---

## 9. D5 — Hexágono quente + cruzamento de M&A

**Decisão do gate (D5).**

- **Métrica de "hexágono quente para M&A" (com a INVERSÃO da seção 2):**
  `sam_fitness_potencial` **alto** (top quartil do universo) **AND** `score_oportunidade_residual < 25`
  (**saturado** — residual ≈ `< ~625` alunos, sendo `2500` alunos = 1 unidade grande proxy). É demanda
  **ALTA + residual BAIXO**, o OPOSTO de `abrir_agora`.
- **Distância academia ↔ hex = k=1.** A academia está "próxima de hex quente" se o seu `hex_id_res7`
  **ou** qualquer vizinho em `h3.grid_disk(k=1)` for quente (adjacência ~2–3 km, sem geometria pesada).
- **Colunas verificadas** em `carteira_expansao_acionavel.parquet`: `score_oportunidade_residual`,
  `oferta_efetiva_disponivel`, `sam_fitness_potencial`, `tese_entrada`, `score_priorizacao`.
- **Join READ-ONLY (molde `enriquecer_outputs_residual_mercado.py:68-82`).** Left-join do "hotness"
  (carteira/mercado) **na** lista de academias por `academia.hex_id_res7 == carteira.hex_id`, com
  asserts de invariância: `len` inalterado (`validate="many_to_one"`), e `score_priorizacao` +
  ranks (`rank_brasil` / `rank_uf` / `rank_carteira_brasil` / `rank_carteira_uf`) idênticos (`.equals`)
  antes/depois. **A camada M&A LÊ essas colunas; NUNCA escreve de volta** em carteira, mercado ou
  artefatos do M1.
- **Prioridade de M&A** = `f(score_vulnerabilidade da academia, demanda do hex, saturação do hex)`,
  ordenada de forma descendente para o comercial.

---

## 10. D6 — Entregável

**Decisão do gate (D6 = default do Planner).**

- **Camada scored:** `data/staging/vulnerabilidade_ma_academias.parquet` (**gitignored** se carregar
  identidade — Opção B do D1).
- **Lista curada para o comercial:** `data/outputs/alvos_ma_priorizados.csv`, `sep=";"`,
  `encoding="utf-8-sig"`. Exemplo de cabeçalho (hex-level do MVP, sem identidade):

  ```csv
  hex_id_res7;uf;n_independentes_vulneraveis;score_vulnerabilidade_medio;sam_fitness_potencial;score_oportunidade_residual;hex_quente;n_sinais_disponiveis;flag_serie_imatura
  ```

- **Sem overlay de dashboard no MVP** (opcional/futuro). Se por-academia (nomeado), o artefato é
  **gitignored** (fonte real fora do versionamento, DEC-012).

---

## 11. D7 — Anti-PII

**Decisão do gate (D7 = default do Planner).**

- **Persistir SÓ agregados** (contagens, médias, flags de churn/staleness, `hash_campos_raspados`).
  **NUNCA** texto/autor de review nem coordenada GPS bruta — a geometria deriva do `hex_id` (DEC-012).
- **Nome/endereço de estabelecimento** (dado de negócio) é permitido **apenas** no artefato NOMEADO da
  Opção B, que então é **gitignored**.
- **Fixtures sintéticas** nos testes; a fonte real (CSVs brutos TP/WH, snapshots) fica **fora do
  versionamento** e vive na VPS. Reafirma a DEC-012.

---

## 12. D8 — Integração ao cron

**Decisão do gate (D8 = default do Planner).**

- **Dois relógios.** Churn/staleness (S3/S4) saem do snapshot semanal dos 90 coletores →
  `run_weekly_90.sh` (DEC-013). Presença/rating de agregador (S1/S2) dependem do cron **mensal** dos
  agregadores WellHub/TotalPass, que ainda é **FUTURO/pendente** (`infra_producao.md`, § Pendentes).
- **Passo semanal.** Anexar o recompute do `score_vulnerabilidade` como **passo** do runner semanal
  **APÓS** a regen da camada mercado/residual (para o hotness estar fresco), estritamente **READ-ONLY**
  sobre o M1. Os sinais de agregador são consumidos do **ativo mensal mais recente**, marcados com flag
  de **staleness** quando desatualizados.
- **DEC-013 cobre** a extensão do lote — **não é pipeline novo**. Runbook detalhado em BLK-MA-06.

---

## 13. Decomposição BLK-MA-02..07

Ajustada pelo **D3 = Não** (rating fora do MVP → movido para BLK-MA-07):

| Bloco | Escopo | D amarradas |
|---|---|---|
| **BLK-MA-02** | Extrator de churn+staleness do histórico de snapshots (100% interno) + flags de série imatura (ramp-up). É o núcleo 100%-reuso do Plano B. | D2 (S3/S4) |
| **BLK-MA-03** | Presença em agregador (**sinal 1**, reuso via `fonte`) + (opcional/deferido) extensão de ingestão para o universo NOMEADO (D1-B, retém `nome_estabelecimento`); anti-PII por construção; fixtures sintéticas. **Rating (sinal 2) NÃO entra aqui (D3=Não)** — movido para BLK-MA-07. | sinal 1 + D1 |
| **BLK-MA-04** | Score de vulnerabilidade (D4) sobre S1/S3/S4 (Plano B) + normalização + flags de qualidade. | D4 + D7 |
| **BLK-MA-05** | Lista priorizada de M&A (cruzamento com o hex quente, D5, **COM a INVERSÃO**) + entregável. | D5 + D6 |
| **BLK-MA-06** | Integração ao cron semanal da VPS + runbook. | D8 |
| **BLK-MA-07** | (Opcional/futuro, **gate + DEC próprios**) reputação/nota — in-app se surgir fonte **OU** externa (Google Places). Único ponto que reabre o §2. | — |

D7 (anti-PII) é transversal a BLK-MA-02..05.

---

## 14. Guardrails e referências

**Guardrails ativos.**

- **§5 — READ-ONLY sobre o M1:** o `score_vulnerabilidade` é PARALELO; joins/análises não recalculam
  nem alteram `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de
  domínio ou artefatos oficiais. Pesos `renda=0.40` / `pop=0.60` INTOCADOS.
- **DEC-012 — anti-PII:** camada H3 res-7 sem PII; geometria do `hex_id`; só agregados; fonte real
  gitignored; fixtures sintéticas.
- **DEC-013 — coleta recorrente na VPS:** BLK-MA é **extensão** desse lote, não pipeline novo.
- **§2 — sem API ao vivo:** Plano B sem dependência de API externa; dashboard offline sobre Parquets;
  acentuação correta em texto de usuário, nunca em identificadores; CSV `sep=";"` / `utf-8-sig`.
- **Sem DEC neste bloco:** a rota Google Places/§2 foi descartada no Plano B → BLK-MA-01 **não** cria
  DEC (reputação externa e seu eventual DEC ficam no BLK-MA-07).

**Referências.**

- `docs/decisions/DEC-012.md` (anti-PII / Demanda Revelada), `docs/decisions/DEC-013.md` (coleta
  recorrente na VPS).
- `docs/modelo_mercado_hexagonos.md` (colunas de mercado/residual: `pressao_concorrencial_score_2km`,
  `sam_fitness_potencial`, `oferta_efetiva_disponivel`, `score_oportunidade_residual`, `tese_entrada`).
- `src/motor_expansao/pipelines/enriquecer_outputs_residual_mercado.py:68-82` (molde defensivo de join
  READ-ONLY).
- `src/motor_expansao/demanda_revelada/concorrentes_densos.py:127` (`_ler_csv_tp_wh` — confirma que o
  rating não é retido e que o `nome` é lido e dropado na fronteira).
- `docs/infra_producao.md` (runbook do cron semanal GymScraping — D2/D8).
- `CLAUDE.md` §1/§2/§4/§5/§6/§8.

---

## 15. Registro das decisões D1–D8 (gate de 2026-07-23, Vinicius)

| # | Questão | Opção escolhida no gate | Default do Planner |
|---|---|---|---|
| **D1** | Universo de "academia independente" e fonte que retém identidade | **FASEADO** — MVP hex-level agregado (Opção A, anti-PII) entra já; nomeação por-academia (Opção B) **deferida** atrás de confirmação dos CSVs brutos (nome existe na fonte, é dado de negócio). Independente = fora das 28 cadeias (`independente` ou marca com unidades `== 1`); reconciliar 28 scrapers vs 90 coletores no BLK-MA-02. | Entregar Opção A primeiro; Opção B atrás de confirmação. |
| **D2** | Fonte/retenção dos snapshots (churn/staleness) | **Default aceito** — snapshots por `concorrente_id` + `hash_campos_raspados` em `data/staging/snapshots_concorrentes/semana=AAAA-SS/` (gitignored, VPS); retenção 26 semanas; `MIN_SEMANAS=8`; `STALE_SEMANAS=12`; série imatura marcada e neutra. | Idem (Opção A). |
| **D3** | Rating de agregador (sinal 2) | **NÃO carregam a nota** — sinal 2 fica `n/d` PERMANENTE no Plano B; score roda em S1/S3/S4 renormalizados; reputação/nota só no BLK-MA-07 (gate + DEC próprios). | Sinal 2 CONDICIONAL, `n/d` não penaliza, renormaliza. |
| **D4** | Fórmula/pesos do score de vulnerabilidade | **Pesos S1=0,15 / S2=0,25 / S3=0,35 / S4=0,25** (churn domina); efetivos no Plano B (S2 fora): **S1≈0,20 / S3≈0,467 / S4≈0,333** (`0,15/0,75`, `0,35/0,75`, `0,25/0,75`); normalização percentil-por-universo; RENORMALIZAÇÃO para sinal ausente/imaturo; flags de qualidade; **NÃO-preditivo**. Saída `score_vulnerabilidade ∈ [0,100] = 100·Σ(wi·vi)` + componentes `vi` + flags. | Idem, com S5/S6 fora do MVP. |
| **D5** | Hexágono quente + distância + INVERSÃO | **Quente = `sam_fitness_potencial` alto (top quartil) AND `score_oportunidade_residual < 25` (saturado)**; distância **k=1** (`h3.grid_disk(k=1)`); **INVERSÃO** (demanda alta + residual baixo, oposto de `abrir_agora`) registrada; join READ-ONLY no molde `:68-82` com asserts de invariância. | Idem (Opção A + k=1 + join com asserts). |
| **D6** | Entregável | **Default aceito** — Parquet `data/staging/vulnerabilidade_ma_academias.parquet` (gitignored se nomeado) + CSV `data/outputs/alvos_ma_priorizados.csv` (`sep=";"`/`utf-8-sig`); sem overlay de dashboard no MVP. | Idem. |
| **D7** | Anti-PII | **Default aceito** — só agregados; nome/endereço só no artefato nomeado (gitignored); fixtures sintéticas; fonte real fora do versionamento (DEC-012). | Idem. |
| **D8** | Integração ao cron | **Default aceito** — passo no `run_weekly_90.sh` **pós-regen** mercado/residual (READ-ONLY); sinais de agregador do ativo mensal mais recente com flag de staleness; DEC-013 cobre a extensão do lote. | Idem. |
