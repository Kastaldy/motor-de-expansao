# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

> Após o Planner, o ciclo **PARA** para **[APROVAÇÃO HUMANA + registro de DEC própria]** (DEC-0XX em CLAUDE.md §8) ANTES do Builder. Não é loop-safe (cria eixo de score).

## Bloco refinado
**BLK-LTV-04 — Score M2 territorial de retenção.** Compor um **eixo de score paralelo (M2)** que pondera captação + LTV/retenção territorial por hexágono, como **camada paralela READ-ONLY sobre o M1**. É o sucessor CONDICIONAL do BLK-LTV-03, que fechou **GO**: o sinal território→retenção sobrevive ao controle de maturidade (sinal mais forte `score_priorizacao × LTV_PROSPECTIVO_12M_MEDIANO` rho=+0.391, IC95[+0.183,+0.573], p=0.0029, N=56; parcial maturidade+renda +0.306, IC[+0.034,+0.550]). O M1 (`score_priorizacao`, pesos renda=0.40/pop=0.60, artefatos oficiais) NÃO é tocado — `score_priorizacao` só pode ser LIDO como feature. Insumo canônico: `data/staging/unidade_territorio_retencao.parquet` (88×36; join unidade→hex→retenção/LTV do BLK-LTV-02).

## Objetivo
Definir e validar (honestamente, LOO/k-fold vs baseline da média) um score M2 territorial que pondere captação + retenção/LTV, com pesos aprovados em DEC, sem jamais alterar o M1.

## Escopo permitido
- Código novo VIVE no pacote disjunto **`src/motor_expansao/lifetime/`** (mesmo pacote do BLK-LTV-03; NÃO criar `m2/` novo salvo decisão explícita do Planner — manter a trilha coesa). O pacote NUNCA importa de `pipelines/m1/`, `dashboard/`, `censo_*`, `api`.
- **LER** (READ-ONLY): `data/staging/unidade_territorio_retencao.parquet` (insumo principal, 88×36); `data/ultra/unidade_para_motor.parquet` (Lifetime: `PROB_CANCEL_90D_*`, `LTV_PROSPECTIVO_12M_*`, `CONFIABILIDADE_UNIDADE`, `USAR_PROB_ABSOLUTA`, `USAR_RANKING`, `TICKET_MEDIO_UNIDADE`); `data/staging/growth_api_historico.parquet` (campo `inauguracao`, 89 unidades — SÓ como **covariável de controle de maturidade na validação**, jamais como feature do score por hex); features territoriais lidas do próprio parquet do epic (`score_priorizacao`, `score_expansao_hibrido`, `score_oportunidade_residual`, `renda_per_capita`, `densidade_pop_setor_hab_km2`, `score_setor_2022_calibrado`, `n_concorrentes_mapeados_1km`).
- **GRAVAR**: (a) o(s) módulo(s) `.py` do M2 em `lifetime/` + testes em `tests/unit/`; (b) o output do score M2 e o relatório de validação em caminhos **NÃO oficiais e gitignored** — sugestão: parquet do M2 em `data/staging/` com nome próprio (ex.: `score_m2_territorial_retencao.parquet`, NÃO reusar nenhum artefato M1) e o relatório em `data/analysis/` (gitignored, padrão do BLK-LTV-03). O Planner FIXA os nomes exatos.
- Definir a **fórmula/pesos do M2** e o método de validação (a APROVAR em DEC + gate humano — não implementar antes).

## Fora de escopo
- Recalcular/alterar `score_priorizacao`, `hex_score_estrutural`, pesos (renda=0.40/pop=0.60), carteira, plano curto prazo, plano de domínio ou QUALQUER artefato oficial do M1 (§3/§5; DEC-001).
- Escrever em `brasil_estrutural.parquet`, `brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet`, `hexagonos_brasil_dashboard.parquet` ou qualquer parquet oficial (mtime desses DEVE ficar inalterado).
- Usar maturidade (idade da unidade / `inauguracao`) como FEATURE do score territorial por hex — é atributo de UNIDADE, não de hex candidato; serve SÓ de covariável de CONTROLE na validação.
- Usar qualquer coluna do M2 como preditor GEOGRÁFICO de magnitude de demanda ou como ajuste do `score_priorizacao` (DEC-009).
- R² in-sample como desempenho; `fit(X,y)→predict(X)` (DEC-008 — banido).
- Integrar o M2 ao dashboard, à API, ao pipeline de mercado ou à VPS (blocos sucessores, fora deste).
- Resolver os 32 unidades sem hex_id / fechar cobertura de geocodificação (foi trabalho do BLK-LTV-01/02; aqui é confound declarado).

## Arquivos que devem ser lidos
- `CLAUDE.md` (§1, §3, §5 guardrail permanente; DEC-001, DEC-008, DEC-009).
- `tasks/current_task.md` (tarefa ativa BLK-LTV-04).
- `tasks/backlog.md` (bloco BLK-LTV-04 ~942–956; epic BLK-LTV ~899–928 — regras canônicas do insumo Lifetime: `LTV_PROSPECTIVO_12M_*` só no agregado por unidade; respeitar `USAR_PROB_ABSOLUTA`; haircut ~20% no volume absoluto; N=88 exige bootstrap/IC).
- `src/motor_expansao/lifetime/correlacao_territorio_retencao.py` (base de código da trilha; padrão de metodologia/relatório/guardrails a reusar).
- `data/ultra/unidade_para_motor_DICIONARIO.md` (contrato das colunas Lifetime + regra de `CONFIABILIDADE_UNIDADE`).
- `data/staging/unidade_territorio_retencao.parquet` (dataset canônico do M2).

## Arquivos que podem ser alterados
- `src/motor_expansao/lifetime/` (novo módulo do M2; ou submódulo, a critério do Planner — dentro deste pacote).
- `tests/unit/` (novos testes do M2).
- `data/analysis/` e `data/staging/<nome_novo_do_m2>.parquet` (outputs gitignored / NÃO oficiais — nomes exatos fixados pelo Planner).
- `context/handoff.md` + snapshot (Planner na sua vez), `tasks/current_task.md` (orquestração).
- **PROIBIDO alterar**: `config.py`, qualquer coisa em `pipelines/m1/`, os 4 artefatos oficiais do M1, `dashboard/`, `censo_*`, `api/`.

## Critérios de aceite
- **Pesos/fórmula do M2 aprovados em DEC própria** (DEC-0XX registrada em CLAUDE.md §8) + aprovação humana explícita ANTES do Builder.
- Validação **LOO/k-fold vs baseline da média** (DEC-008): PROIBIDO R² in-sample e `fit(X,y)→predict(X)`; toda métrica de desempenho é out-of-fold.
- **N pequeno (56)** ⇒ IC (bootstrap) obrigatório em toda estimativa de desempenho + **flag de extrapolação**; IC cruzando zero é desfecho honesto (não forçar sucesso).
- **READ-ONLY M1 comprovado**: mtime dos 4 artefatos M1 (`brasil_estrutural`, `brasil_priorizados`, `hexagonos_brasil_oportunidades`, `hexagonos_brasil_dashboard`) IDÊNTICO antes/depois de rodar o M2; nenhuma escrita nesses paths.
- Output do M2 gravado SÓ em caminho não oficial/gitignored; determinismo (seed fixo) e reprodutibilidade byte-estável do relatório.
- `lifetime/` sem imports de `pipelines/m1`/`dashboard`/`censo_*`/`api` (teste dedicado, como no BLK-LTV-03).
- Regras do insumo respeitadas: `LTV_PROSPECTIVO_12M_*` só no agregado por unidade; `USAR_PROB_ABSOLUTA`/`CONFIABILIDADE_UNIDADE` respeitados (unidades sem prob. absoluta confiável só no eixo de ranking); haircut ~20% no volume absoluto quando aplicável.
- Suíte verde (`pytest -n auto`), ruff limpo, mypy `src/` sem erros novos, smoke `import streamlit_app` ok.

## Criticidade classificada
**Estratégica** (cria um eixo de score novo — camada paralela; NÃO altera o M1 oficial, por isso não é "Crítica" no sentido de tocar artefato M1, mas é Estratégica por instituir uma nova superfície de score e exigir DEC própria + gate humano). Alerta explícito: qualquer desvio que ESCREVA em `score_priorizacao`/`hex_score_estrutural`/artefatos M1 reclassifica IMEDIATAMENTE para **Crítica** e viola DEC-001 — não é permitido.

## Esteira recomendada
Block Orchestrator → **Planner** → **[APROVAÇÃO HUMANA + DEC própria (DEC-0XX)]** → Builder → QA.
O ciclo PARA após o Planner para o gate humano + registro de DEC. Tiering de modelo: todos em opus; QA sempre em Opus 4.8.

## Riscos identificados
- **N pequeno (N=56 no eixo ranking; 44/49 em subconjuntos)** — variância alta; exige IC + flag de extrapolação; validação LOO/k-fold pode dar desempenho fraco/negativo (desfecho honesto legítimo, pode NÃO justificar o score — o Planner deve prever um critério de NO-GO honesto).
- **Seleção de sobreviventes** — as 88 são unidades OPERANDO; fechadas não entram ⇒ pode subestimar o efeito do território na retenção.
- **32 de 88 unidades sem hex_id (36%)** — possível viés geográfico; o universo N=56 pode não representar a rede inteira.
- **Colinearidade** entre `renda_per_capita` ↔ `score_priorizacao` ↔ `score_expansao_hibrido` (score deriva de renda+pop) — cuidado ao combinar features no M2; renda pura colapsa sob controle de maturidade (o carregador é o COMPOSTO `score_priorizacao`, não renda isolada).
- **Confound de maturidade** — sinal território→retenção mistura LOCALIZAÇÃO com TEMPO DE OPERAÇÃO; `inauguracao` (growth_api_historico) permite CONTROLAR na validação (gate G1 da DEC-001 satisfeito para validação), mas maturidade NÃO pode virar feature do score por hex.
- **Tentação de escopo** — não integrar M2 ao dashboard/API/mercado/VPS; não recalibrar o M1. Um bloco por vez.

## Guardrails ativos
- **§5 (guardrail permanente)**: visualizações/análises/scores paralelos NÃO podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou artefatos oficiais do M1 sem aprovação explícita. READ-ONLY sobre o M1.
- **DEC-001**: pesos `renda=0.40`/`pop=0.60` e a fórmula do `score_priorizacao` INALTERADOS; nenhum artefato M1 regerado. `score_priorizacao` só pode ser LIDO como feature do M2.
- **DEC-008**: metodologia de validação honesta — LOO/k-fold repetido SEMPRE contra baseline da média; BANIR R² in-sample e `fit(X,y)→predict(X)`; começar simples; toda saída com intervalo de predição + flag de extrapolação; N pequeno exige IC.
- **DEC-009**: o M2 é score de RETENÇÃO territorial, NÃO preditor de magnitude de demanda; demanda entra como premissa, nunca prevista pela geografia; proibido reintroduzir regressão geográfica de demanda como preditor.
- **§1**: Ultra é low-cost/massa (Smart Fit é comparável de mesmo segmento); o M1 é a camada EXECUTIVA e não pode ser subvertido por camada paralela.
- **Pacote disjunto `lifetime/`**: não importa de `pipelines/m1/`, `dashboard/`, `censo_*`, `api`.
- **Este bloco EXIGE DEC registrada + gate humano ANTES do Builder** (Estratégica, cria score).
