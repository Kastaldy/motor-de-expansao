# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-TP-04 — Calibração da curva tamanho→densidade do BLK-DIM com alunos/unidade (Demanda Revelada)

## Objetivo
Usar `alunos_parceiras` da camada Demanda Revelada (`demanda_revelada_h3.parquet`) como fonte de alunos
observados para calibrar/validar a função `faixa_alunos_por_densidade` do `viabilidade_ponto.py`, ampliando
a base de comparáveis além das 54 unidades Ultra — sob a disciplina DEC-008 (LOO/k-fold vs baseline,
sem R² in-sample, intervalos + flag de extrapolação) e respeitando a DEC-009 (preditor = metragem,
NUNCA geografia).

## Escopo permitido
- Criar/estender um módulo em `src/motor_expansao/demanda_revelada/` (ex.: `calibracao_curva.py`) que:
  - Leia `data/staging/demanda_revelada_h3.parquet` (coluna `alunos_parceiras`, `n_acad_parceiras`) e
    `data/staging/base_calibracao_multirede.parquet` (colunas `alunos_reais`, `metragem`, `marca`) como fontes de alunos observados.
  - Derive `alunos_por_unidade = alunos_parceiras / n_acad_parceiras` (somente hexes com
    `n_acad_parceiras >= 1`) como proxy de alunos/unidade — SEM metragem associada (ver Riscos).
  - Documente limitações da amostra e estratégia de uso (validação cruzada indireta ou análise de
    distribuição de densidade observada).
  - Valide a curva existente (percentis da `base_calibracao_multirede`) com LOO vs baseline e forneça
    intervalos de predição (p10/p50/p90) + flag de extrapolação para hexes fora do envelope m².
  - Produza relatório `data/analysis/calibracao_curva_densidade.md` (gitignored) com achados e veredito
    GO/NO-GO.
- Atualizar testes em `tests/unit/dimensionamento/` ou `tests/unit/demanda_revelada/` cobrindo:
  - Anti-PII: nenhuma coluna proibida (COLUNAS_PII_PROIBIDAS) no artefato de calibração.
  - LOO honesto: R² in-sample não exposto; critério de NO-GO documentado.
  - Intervalos de predição presentes nos outputs.
- Atualizar `tasks/backlog.md` (mover BLK-TP-04 para concluído) e `tasks/completed.md`.

## Fora de escopo
- Qualquer alteração em `score_priorizacao`, `hex_score_estrutural`, pesos (`renda=0.40`/`pop=0.60`),
  carteira, plano, artefatos oficiais do M1 (`brasil_estrutural.parquet`, `brasil_priorizados.parquet`,
  `hexagonos_brasil_oportunidades.parquet`, `hexagonos_brasil_dashboard.parquet`).
- Reintroduzir regressão geográfica de demanda (pop, renda, concorrência) como preditor da curva
  (DEC-009 — PROIBIDO). A curva prediz alunos a partir de m², NUNCA de lat/lng.
- Acrescentar metragem às 16.575 linhas do parquet `demanda_revelada_h3.parquet` — a fonte (academias
  parceiras do TotalPass/WellHub) não tem m² no dump; inferir metragem seria fabricar dado.
- Alterar o método de interseção setorial, raio 1,5 km, parâmetros M1 (§3 CLAUDE.md).
- Alterar `viabilidade_ponto.py` / `faixa_alunos_por_densidade` sem aprovação explícita de Felipe —
  qualquer alteração de coeficiente da curva em produção exige gate humano.
- Instalar novas dependências pesadas (scikit-learn, etc.) — usar numpy/scipy da base (DEC-014 precedente).
- UI/dashboard (bloco separado, se necessário).

## Arquivos que devem ser lidos
- `src/motor_expansao/dimensionamento/viabilidade_ponto.py` — função `faixa_alunos_por_densidade`
  (linhas 106–176): curva atual, contrato de `base_calibracao_df` (colunas `alunos_por_m2`, opcional
  `metragem`), percentis p10/p50/p90, flag de extrapolação implícita via janela +/-20%/50%.
- `src/motor_expansao/demanda_revelada/contrato.py` — 9 colunas canônicas, `COLUNAS_PII_PROIBIDAS`,
  `VERSAO_CONTRATO`.
- `src/motor_expansao/demanda_revelada/ingestao.py` — lógica de ingestão e anti-PII.
- `data/staging/demanda_revelada_h3.parquet` — 16.575 hexes; colunas relevantes: `hex_id`,
  `alunos_parceiras` (5.341 hexes com valor > 0), `n_acad_parceiras` (5.919 > 0). SEM metragem.
- `data/staging/base_calibracao_multirede.parquet` — 426 linhas (Ultra 54 + Engenharia 61 + SkyFit 311);
  colunas: `unidade`, `marca`, `uf`, `cidade`, `lat`, `lng`, `alunos_reais`, `metragem`,
  `flag_qualidade_match`. N com metragem + alunos_reais = 112 (Ultra 54 + Engenharia 58; SkyFit:
  metragem AUSENTE).
- `data/staging/unidades_ultra_performance_hex.parquet` — 54 unidades Ultra com `metragem`,
  `alunos_total`, `alunos_por_m2` (todos 54 non-null); fonte primária atual da curva em produção.
- `data/analysis/densidade_contexto.md` — resultado do spike DIM-07: R²_LOO de metragem = +0,096
  (único sinal real); geografia NO-GO; base de 89 unidades (Ultra 53 + Engenharia 36).
- `data/analysis/backtest_dim.md` — BLK-DIM-06: camada 3+4 R² = +0,228 (DRE, alunos reais);
  camada 1 NO-GO; end-to-end NO-GO. Confounds documentados.
- `src/motor_expansao/dimensionamento/base_multirede.py` — como foi construída a base multirede
  (reconciliação de nomes, raio variável, anti-PII).
- `src/motor_expansao/dimensionamento/config.py` — constantes de path e parâmetros do DIM.
- `tests/unit/dimensionamento/test_backtest_dim.py` — referência de estrutura de teste do DIM.
- `CLAUDE.md` §1 (posicionamento Ultra low-cost), §3 (parâmetros canônicos), §4 (DEC-008/DEC-009/
  DEC-012), §5 (guardrails).
- `PRD.md` — se o Planner precisar de regras de produto adicionais do ciclo ativo.

## Arquivos que podem ser alterados
- `src/motor_expansao/demanda_revelada/calibracao_curva.py` — NOVO (módulo de calibração da curva).
- `tests/unit/demanda_revelada/test_calibracao_curva.py` — NOVO (testes do módulo acima).
- `data/analysis/calibracao_curva_densidade.md` — NOVO, gitignored (relatório de achados).
- `tasks/backlog.md` — mover BLK-TP-04 de pendente para concluído.
- `tasks/completed.md` — registro do bloco concluído.
- `context/handoff.md` — atualizado por cada Skill na esteira.
- `context/handoff/` — snapshots append-only.
- `tasks/current_task.md` — atualizado por cada Skill.

  ### Arquivos que NÃO devem ser alterados (guardrail explícito)
  - `src/motor_expansao/dimensionamento/viabilidade_ponto.py` — a função `faixa_alunos_por_densidade`
    usa `base_calibracao_df` injetado pelo chamador; qualquer mudança nos coeficientes/parâmetros
    da curva em produção exige aprovação de Felipe.
  - `data/staging/demanda_revelada_h3.parquet` — READ-ONLY (fonte de dado, não artefato do bloco).
  - `data/staging/base_calibracao_multirede.parquet` — READ-ONLY.
  - `data/staging/unidades_ultra_performance_hex.parquet` — READ-ONLY.
  - Qualquer artefato oficial do M1 (mtime não pode mudar).

## Critérios de aceite
1. Módulo `calibracao_curva.py` criado em `src/motor_expansao/demanda_revelada/` com:
   - função que recebe `demanda_revelada_h3.parquet` e `base_calibracao_multirede.parquet` e retorna
     análise de validação da curva atual (percentis por faixa de m², intervalos de predição, flag de
     extrapolação para pontos fora do envelope de metragem da base).
   - LOO honest cross-validation (k-fold 5×5 ou LOO) vs baseline da média, com IC95 bootstrap; R²
     in-sample AUSENTE dos outputs.
   - Relatório `calibracao_curva_densidade.md` com veredito explícito GO/NO-GO e limitações documentadas.
2. Testes cobrindo: anti-PII (`COLUNAS_PII_PROIBIDAS` não presentes); LOO honesto (sem R² in-sample);
   intervalos de predição presentes; `alunos_parceiras` nunca usado diretamente como preditor geográfico.
3. `suíte completa pytest verde` (0 falhas, 0 erros de coleta).
4. Nenhum artefato oficial do M1 alterado (mtime inalterado).
5. `import` do novo módulo não acrescenta dependências além de numpy/scipy/pandas/pyarrow/h3 (base).
6. `import streamlit_app` continua ok (smoke test).

## Criticidade classificada
Alta — alimenta a modelagem de viabilidade (BLK-DIM); READ-ONLY sobre o M1. Não toca
`score_priorizacao`, pesos, carteira, plano nem artefatos oficiais. Se tocasse qualquer destes,
seria Crítica.

## Esteira recomendada
Block Orchestrator → **Planner** → [REVISÃO HUMANA — modelagem, gate Felipe] → Builder → QA

O gate humano pré-Builder é obrigatório para blocos de modelagem (Alta criticidade com decisão de
produto/metodologia): o Planner apresenta as opções de calibração, os riscos de N e metragem ausente
na Demanda Revelada, e Felipe aprova a abordagem antes de o Builder implementar.

## Riscos identificados

1. **RISCO PRINCIPAL — Metragem ausente na Demanda Revelada (alunos_parceiras).**
   `demanda_revelada_h3.parquet` tem `alunos_parceiras` (soma de alunos das academias parceiras por hex)
   e `n_acad_parceiras` (count de academias), mas **NÃO tem metragem (m²) das parceiras**. A curva de
   calibração é `m² → densidade (alunos/m²)`; sem m² das parceiras, não é possível adicionar esses
   pontos diretamente à base de calibração da curva. O `alunos_parceiras / n_acad_parceiras` dá
   alunos/unidade como proxy, mas sem m² não se calcula `alunos/m²`. Abordagem alternativa aprovada
   pelo Planner + gate humano: usar a distribuição de `alunos/unidade` das parceiras como validação
   cruzada externa (i.e., checar se as faixas de alunos estimadas pela curva Ultra+Engenharia são
   compatíveis com a distribuição das parceiras), sem injetar linhas com m² nulo na base de calibração.

2. **N pequeno da base com metragem.** A base multirede com metragem + alunos_reais tem N=112
   (Ultra 54 + Engenharia 58); SkyFit (311 linhas) não tem metragem. LOO em N=112 é instável;
   k-fold 5×5 com IC bootstrap é a abordagem adequada (DEC-008).

3. **Heterogeneidade de rede na base multirede.** Ultra e Engenharia do Corpo são redes distintas
   em ticket/público. A coluna `marca` existe e deve ser usada como covariável de controle ou
   estratificação, não ignorada.

4. **alunos_parceiras = academias diversas (não só low-cost/Ultra-like).** As academias parceiras
   do dump TotalPass incluem redes diversas; `alunos_por_unidade` dessas parceiras pode ter
   distribuição muito diferente da Ultra. O Planner deve definir se filtrar por tipo de rede
   (low-cost comparável) ou usar o total com disclaimer de heterogeneidade.

5. **Flag de qualidade do match.** `base_calibracao_multirede.parquet` tem `flag_qualidade_match`;
   o Planner deve decidir se filtrar só registros com match de alta qualidade antes do LOO.

6. **Hexes com n_acad_parceiras muito alto (até 123).** `alunos_parceiras / n_acad_parceiras` para
   hexes densos (centros de cidade com 10+ academias) pode ser ruidoso. O Planner deve definir
   critério de corte (ex.: descartar hexes com n_acad >= threshold ou ponderar pelo N).

## Guardrails ativos
- §5 CLAUDE.md (READ-ONLY M1): `score_priorizacao`, `hex_score_estrutural`, pesos, carteira, plano
  e artefatos oficiais são INTOCÁVEIS. Nenhum mtime de artefato M1 pode mudar.
- DEC-008: LOO/k-fold vs baseline da média; R² in-sample BANIDO; intervalos de predição + flag de
  extrapolação obrigatórios.
- DEC-009: demanda é insumo OBSERVADO, NUNCA preditor geográfico de magnitude. PROIBIDO usar qualquer
  coluna geográfica/demográfica (`lat`, `lng`, `pop_total`, `renda_per_capita`, etc.) como preditor
  da curva. A curva prediz alunos a partir de `m²` SOMENTE.
- DEC-012 (anti-PII): consumir apenas a camada agregada (`alunos_parceiras`, `n_acad_parceiras`);
  `COLUNAS_PII_PROIBIDAS` ausentes em todo artefato gerado; testes com fixture sintética (nunca a
  fonte real). A fonte real (`NAO_ABRA/`) NUNCA é versionada.
- §2 CLAUDE.md: sem API ao vivo nem dependência de rede no caminho de calibração.
- §6 CLAUDE.md (VPS): zero comandos na VPS sem confirmação explícita do usuário.
