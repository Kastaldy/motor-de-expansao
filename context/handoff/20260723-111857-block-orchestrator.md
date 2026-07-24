# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (criticidade Média com gate humano de produto embutido na esteira; NÃO é Crítica — o score é PARALELO, READ-ONLY sobre o M1).

## Bloco refinado
BLK-MA-01 — Contrato e decisões do enriquecimento de vulnerabilidade (design, Plano B).

Bloco de **design/contrato — ZERO código de produção**. Fixa o contrato dos sinais de vulnerabilidade de concorrentes (M&A), a metodologia do score paralelo e resolve/confirma as 8 decisões de produto D1–D8, confirmando a decomposição BLK-MA-02..07. É camada de ENRIQUECIMENTO sobre os scrapers já existentes (GymScraping, DEC-013) — NÃO cria pipeline novo. Rota escolhida por Vinicius (2026-07-06): **PLANO B — sem Google Places** (sinais só de fontes internas já coletadas + diff de snapshots semanais) → **sem dependência de API externa ao vivo → sem DEC**. Reputação pública externa fica no sucessor opcional BLK-MA-07 (gate + DEC próprios).

## Objetivo
Fixar em documento o contrato dos sinais de vulnerabilidade (1–4 obrigatórios + 5/6 opcionais), a metodologia do score paralelo READ-ONLY e resolver/confirmar D1–D8 no gate humano, com a decomposição BLK-MA-02+ confirmada — sem código de produção e sem DEC de API externa.

## Escopo permitido
- Produzir o **contrato/documento de design** (novo doc em `docs/`, ex.: `docs/vulnerabilidade_ma_contrato.md`) que fixe:
  - Os 6 sinais do Plano B e sua direção de vulnerabilidade: (1) presença/ausência em agregadores WellHub/TotalPass; (2) rating in-app WellHub/TotalPass; (3) churn/permanência via diff dos snapshots semanais; (4) staleness via diff dos snapshots; (5, opcional) tendência de popularidade no agregador; (6, opcional) pressão competitiva (colunas já materializadas em `hexagonos_mercado_mapeado.parquet`).
  - O mapa dos 4 sinais originais → Plano B (avaliação média→(2); Δ reviews 3m→(3)+(5); presença agregadores→(1); última atualização→(4)).
  - A metodologia do score de vulnerabilidade: heurística **transparente e auditável** (composição ponderada normalizada), NÃO modelo preditivo treinado em desfecho.
- Resolver/confirmar **D1–D8** e registrar as decisões de produto tomadas no gate humano (pesos/limiares do score + definição de "hexágono quente").
- Confirmar a **decomposição BLK-MA-02..07** (extrator churn+staleness; join de agregadores; score; lista M&A; cron; reputação externa opcional).
- Explicitar guardrails: §5 (score paralelo READ-ONLY M1), DEC-012/anti-PII (só agregados; fonte real fora do versionamento; fixtures sintéticas), DEC-013 (extensão do lote de scrapers).
- Atualizar o índice `docs/README.md` para apontar o novo contrato.
- No fechamento: append em `tasks/completed.md`.

## Fora de escopo
- Escrever QUALQUER código de produção (extratores, score, join, entregável, cron) — isso é BLK-MA-02..06.
- Tocar `score_priorizacao`, `hex_score_estrutural`, pesos (`renda=0.40`/`pop=0.60`), carteira, plano curto prazo, plano de domínio ou qualquer artefato oficial do M1.
- `flag_sam`/gate do SAM (DEC-006/DEC-007).
- **Google Places / qualquer API externa de reputação** (movido para BLK-MA-07, com gate/DEC próprios).
- Persistir PII (texto/autor de review, coords GPS brutas, nomes).
- Criar DEC de API externa (rota descartada no Plano B → sem DEC).
- Editar `config.py`, `src/motor_expansao/pipelines/m1/`, artefatos oficiais, `PRD.md`, `context/handoff.md`, `tasks/current_task.md` como commit do bloco.
- Ingestão ao vivo / dependência de API no dashboard (§2 não é desafiado — dashboard segue offline sobre Parquets).

## Arquivos que devem ser lidos
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\CLAUDE.md` (§1 papéis das camadas, §2 regras operacionais + acentuação/CSV, §4 camadas paralelas/mercado-residual/Demanda Revelada, §5 guardrail READ-ONLY, §6 VPS/cron GymScraping, §8 DEC-012/DEC-013).
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tasks\backlog.md` (bloco BLK-MA-01, linhas ~1271–1385, e o intro do epic M&A ~1256–1269).
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\demanda_revelada\concorrentes_densos.py` (função `_ler_csv_tp_wh`, linha 127 — caminho de ingestão do sinal 2).
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\docs\decisions\DEC-012.md` (anti-PII / Demanda Revelada).
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\docs\decisions\DEC-013.md` (coleta recorrente de concorrentes na VPS + integração ao residual).
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\docs\modelo_mercado_hexagonos.md` (contrato de colunas de mercado/residual — para D5/D6/sinal 6).
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\pipelines\enriquecer_outputs_residual_mercado.py` (linhas 68–82 — padrão defensivo de join READ-ONLY para D5).
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\docs\README.md` (índice de docs — a atualizar).
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\docs\infra_producao.md` (runbook do cron semanal GymScraping — para D2/D8).

## Arquivos que podem ser alterados
- `docs/vulnerabilidade_ma_contrato.md` (NOVO — nome sugerido; o contrato/design é o entregável).
- `docs/README.md` (índice — apontar o novo contrato).
- `tasks/completed.md` (append no fechamento do bloco).
- NUNCA: `config.py`, `src/motor_expansao/pipelines/m1/`, artefatos oficiais do M1, qualquer código de produção, `PRD.md`, `context/handoff.md`, `tasks/current_task.md`.

## Critérios de aceite
- Contrato dos sinais internos (1–4 obrigatórios + 5/6 opcionais) e do score de vulnerabilidade definido em `docs/`.
- D1–D8 resolvidas/confirmadas no gate humano de produto (com destaque para pesos/limiares do score e definição de "hexágono quente").
- Decomposição BLK-MA-02..07 confirmada (com BLK-MA-07 marcado opcional/futuro com gate + DEC próprios).
- Guardrails §5 (READ-ONLY M1) / anti-PII (DEC-012) / DEC-013 explicitados no documento.
- **Sem DEC de API externa** (rota Google descartada, movida ao BLK-MA-07).
- ZERO código de produção neste bloco (só docs/contrato).
- Acentuação correta em texto de usuário/documento (§2); CSV, se houver exemplo, `sep=";"`/`utf-8-sig`.

## Criticidade classificada
**Média** — com **gate humano de produto embutido** na esteira. Justificativa da NÃO-elevação para Crítica: o score é PARALELO (vulnerabilidade de concorrentes para M&A), READ-ONLY sobre o M1; NÃO é `score_priorizacao`/`hex_score_estrutural` nem toca carteira/plano/artefatos oficiais. O guardrail do BO (elevar a Crítica se tocar M1) NÃO dispara aqui porque o bloco é design/contrato de camada paralela e não escreve nada no M1. Guardrail READ-ONLY M1 registrado explicitamente abaixo.

## Esteira recomendada
Block Orchestrator (este) → **Planner** → **[confirmação humana — produto: pesos/limiares do score de vulnerabilidade + definição de "hexágono quente"]** → **Builder** → **QA (Opus 4.8)**. O gate humano é obrigatório antes do Builder.

## Riscos identificados
- **RISCO ALTO — sinal 2 (rating in-app) NÃO existe no caminho de ingestão atual (claim mais load-bearing do Plano B) — CONFIRMADO por leitura de código.** `src/motor_expansao/demanda_revelada/concorrentes_densos.py`, função `_ler_csv_tp_wh` (linhas 127–141): produz **SÓ** `hex_id_res7`, `rede_normalizada`, `fonte` — sem coluna de rating. As colunas de entrada lidas são apenas `nome`/`latitude`/`longitude`; qualquer nota estaria no "ruído textual" que é **dropado na fronteira** (drop-PII). Consequência: enquanto os CSVs BRUTOS TP/WH (na VPS, gitignored) não forem confirmados carregando a nota **E** a ingestão não for estendida para preservá-la, o sinal 2 é **AQUISIÇÃO** (novo insumo + extensão de código), NÃO "reuso"/"já coletado". O contrato do BLK-MA-01 deve tratar o sinal 2 como CONDICIONAL: marcar "n/d" e não travar BLK-MA-03/04 até a confirmação; o rótulo "já coletado" cai para este sinal. Ação para o gate: confirmar (com o Vini) se os CSVs brutos na VPS têm a nota antes de BLK-MA-03/04 dependerem dela.
- **Ramp-up dos snapshots (sinais 3/4).** O cron GymScraping roda desde ~26/06 (~1,5 mês). A série de snapshots é curta → churn/staleness ainda imaturos. D2 deve fixar: janela de staleness, tratamento de série imatura (marcar imaturo/não penalizar) e onde/retenção dos snapshots. Risco de falso churn no início da série.
- **D1 — universo de "independente" ambíguo.** Os "28 scrapers citados" vs. os "90 coletores da DEC-013" precisam ser reconciliados no gate; critério de não-rede (ex.: contagem de unidades da marca == 1) a fixar sobre `concorrentes_mapeados`.
- **D5 — inversão da tese de M&A.** "Comprar" quer demanda ALTA + residual BAIXO (mercado saturado) — INVERSÃO do sinal de abrir unidade nova (residual alto). O contrato deve registrar explicitamente essa inversão para o Builder do BLK-MA-05 não replicar a lógica de "abrir". Join com `carteira_expansao_acionavel.parquet`/`concorrentes_mapeados.hex_id_res7` deve seguir o padrão defensivo de `enriquecer_outputs_residual_mercado.py:68-82` (asserts de `score_priorizacao`/ranks/cardinalidade inalterados).
- **Anti-PII (D7).** Persistir só agregados (rating médio, contagens, flags de churn/staleness); nunca texto/autor de review nem coords brutas. Fonte real fora do versionamento; fixtures sintéticas (DEC-012). Risco de vazamento de PII se o rating for ingerido sem o drop na fronteira.
- **Escopo criativo.** Risco de o Planner/Builder implementarem código antecipadamente (é design/contrato); reforçar ZERO código de produção.

## Guardrails ativos
- **§5 — READ-ONLY sobre o M1 (registrado explicitamente):** a vulnerabilidade é um score PARALELO; visualizações/análises/joins não podem recalcular nem alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou artefatos oficiais do M1 sem aprovação explícita. Pesos `renda=0.40`/`pop=0.60` INTOCADOS.
- **DEC-012 (anti-PII):** camada de Demanda Revelada H3 res-7 sem PII; geometria deriva do `hex_id`, nunca da coord GPS bruta; persistir só agregados; fonte real gitignored; fixtures sintéticas.
- **DEC-013:** coleta recorrente de concorrentes (GymScraping) automatizada na VPS + integração ao residual READ-ONLY M1; BLK-MA é EXTENSÃO desse lote, não pipeline novo.
- **§2 (NÃO desafiado no Plano B):** sem API externa ao vivo; sem dependência de API no dashboard de produção; dashboard segue offline sobre Parquets. Acentuação correta em texto de usuário, nunca em identificadores; CSV do projeto `sep=";"`/`utf-8-sig`.
- **Sem DEC:** a rota Google Places/§2 foi descartada no Plano B → BLK-MA-01 NÃO cria DEC (a reputação externa e seu eventual DEC ficam no BLK-MA-07).

## Verificação de código (registro auditável — sinal 2)
- Arquivo: `src/motor_expansao/demanda_revelada/concorrentes_densos.py` (nota: o caminho no backlog dizia `pipelines/demanda_revelada/...` mas o módulo real está em `src/motor_expansao/demanda_revelada/`).
- Função: `_ler_csv_tp_wh`, linha 127.
- Colunas de saída reais (linhas 139–141): `hex_id_res7`, `rede_normalizada`, `fonte`. **Nenhuma coluna de rating.**
- Colunas de entrada lidas (linhas 133–138): `latitude`, `longitude`, `nome` (para classificar a rede em memória); tudo mais dropado como ruído textual/PII na fronteira.
- Veredito: claim do backlog **CONFIRMADA**. Sinal 2 marcado como RISCO (aquisição, não reuso) — ver seção Riscos.
