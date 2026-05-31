# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-SCORE-02 — Poder preditivo dos scores vs. desfecho.** Análise estatística
ESTRITAMENTE READ-ONLY sobre o M1: mede, sobre o dataset rotulado de validação
(`data/analysis/dataset_validacao.parquet`, 441 linhas), quanto cada score do
projeto (M1 `score_priorizacao`, censitário `score_setor_2022_calibrado`,
residual `score_oportunidade_residual`, domínio `score_dominio_hibrido`) prevê o
desfecho observado `alunos_recorrentes` — por rede e no agregado —, decompõe o M1
em renda × população para testar EMPIRICAMENTE o peso 0.40/0.60, e relata os
achados. NÃO altera pesos, fórmula nem qualquer artefato oficial do M1 (isso é o
BLK-SCORE-03). O entregável é só um relatório de achados com números.

## Objetivo
Produzir `data/analysis/relatorio_backtest.md` respondendo, com números e
incerteza honesta, qual score melhor prevê recorrentes, se o 0.40/0.60 se
sustenta, e onde score alto ≠ desfecho bom — sem nenhuma proposta de mudança.

## Escopo permitido
- Análise exploratória: correlação score × `alunos_recorrentes` (Spearman/Pearson,
  com intervalo de confiança / p-valor), por rede e no agregado.
- Comparar os 4 scores entre si por poder preditivo do desfecho.
- Decomposição do M1: separar o sinal de renda (`renda_pct_nacional`) vs.
  população (`pop_pct_nacional`) — qual componente carrega o sinal? — testando
  empiricamente se 0.40/0.60 se sustenta. Os componentes NÃO estão no
  `dataset_validacao.parquet`; vêm de `data/staging/brasil_priorizados.parquet`
  por join read-only em `hex_id` (ver "Riscos").
- Identificar casos de score alto × desfecho baixo (e vice-versa), com hipótese
  (ex.: saturação de concorrente, maturação, qualidade de rótulo Skyfit/EngCorpo).
- Novo script `analysis/score_backtest.py` (fim a fim, gera o relatório) + testes.
- Relatório em `data/analysis/` (markdown + figuras opcionais), SEM proposta de mudança.

## Fora de escopo
- **Alterar pesos, fórmula ou qualquer artefato oficial do M1** (`score_priorizacao`,
  `hex_score_estrutural`, `core/scoring.py`, `core/constants.py`, parquets oficiais,
  carteira, plano). Isso é o **BLK-SCORE-03** (CRÍTICA, exige DEC + aprovação humana).
- Propor recalibração ou novo peso — proibido até no texto do relatório (só achados).
- Escrever em `data/outputs/` (artefatos de produto M1). Saída só em `data/analysis/`.
- Rebuild do dataset (`build_validation_dataset.py`) ou mudança em sua lógica.
- Expandir para outros blocos. Um bloco por vez.

⚠️ **ALERTA EXPLÍCITO:** QUALQUER escrita em fórmula/peso/artefato M1 está FORA DE
ESCOPO neste bloco e pertence ao BLK-SCORE-03. Este bloco apenas LÊ scores e mede
poder preditivo. Pela regra de interpretação do CLAUDE.md (2026-05-30):
"LEITURA/ANÁLISE de score sem escrita em artefato M1 → Alta".

## Arquivos que devem ser lidos
- `data/analysis/dataset_validacao.parquet` — entrada principal (gitignored, 441 linhas).
- `src/motor_expansao/core/scoring.py` — fórmula oficial e helpers de percentil.
- `src/motor_expansao/core/constants.py` — `PESOS_HEX_SCORE_ESTRUTURAL`
  (renda=0.40, populacao=0.60), `PERCENTIL_CORTE_*`.
- `data/staging/brasil_priorizados.parquet` — ÚNICA fonte (read-only, join por
  `hex_id`) dos componentes `renda_pct_nacional`, `pop_pct_nacional`,
  `hex_score_estrutural`, `ajuste_executivo`, `renda_per_capita`, `pop_total`,
  `populacao_proxy` (NÃO existem no dataset_validacao).
- `analysis/build_validation_dataset.py` — referência do esquema/origem das colunas
  (NÃO alterar): confirma `alunos_recorrentes` e a constante de maturação.

## Arquivos que podem ser alterados
- `analysis/score_backtest.py` (novo)
- `data/analysis/relatorio_backtest.md` (novo, gitignored) + figuras opcionais
  (ex.: `data/analysis/fig_*.png`, também gitignored)
- `tests/unit/test_score_backtest.py` (novo, se aplicável)
- Arquivos de fluxo: `tasks/current_task.md`, `tasks/backlog.md`,
  `tasks/completed.md`, `context/handoff.md`, `context/handoff/`

## Colunas reais do dataset (confirmadas lendo o repo)
- **Desfecho:** `alunos_recorrentes` (float; 410/441 não-nulos). Origem por rede
  (`alunos_origem`): Ultra=`alunos_total` (54), Skyfit=`Alunos EVO` (326),
  EngCorpo=`Alunos Totais` (61). Qualidade em `rotulo_confiabilidade`:
  380 `medido` (Ultra+Skyfit) / 61 `estimado` (EngCorpo). `alunos_medido` bool.
- **Scores disponíveis** (não-nulos / usáveis = score+desfecho ambos presentes):
  - `score_priorizacao` (M1): 364 não-nulos / **353 usáveis**
    (Ultra 53, Skyfit 266, EngCorpo 34).
  - `score_setor_2022_calibrado` (censitário): 382 / **370 usáveis**.
  - `score_oportunidade_residual` (residual): 390 / **377 usáveis**.
  - `score_dominio_hibrido` (domínio): apenas 43 / **43 usáveis** — MUITO esparso
    (cobertura parcial vinda de `plano_expansao_dominio.parquet`, 500 hexes).
  - Flags de disponibilidade: `score_*_disponivel` (bool) por score.
- **Componentes do M1** para a decomposição (renda vs. pop): `renda_pct_nacional`,
  `pop_pct_nacional` NÃO existem no dataset_validacao; obter por join read-only de
  `brasil_priorizados.parquet` em `hex_id`.
- **Maturação disponível?: NÃO.** A coluna existe (`maturacao_status`) porém é a
  constante única `maturacao_indisponivel` nas 441 linhas (sem data de abertura
  confiável). Não há proxy de idade/maturação no dataset. ⇒ o critério de aceite
  "controlar por maturação" NÃO pode ser cumprido com dado real — ver Riscos; o
  Planner deve decidir tratamento (declarar limitação explícita no relatório e/ou
  buscar proxy fora de escopo só se aprovado).
- Outras colunas úteis: `rede`, `uf`, `nome_municipio`, `hex_id`, `metragem_m2`
  (EngCorpo permite alunos/m²), `sinal_wellhub`/`n_parcerias_wellhub`, `hex_origem`/
  `hex_precisao` (precisão do hex: `unidade` vs `cidade_centroide` — qualidade do join).

## Critérios de aceite
- Relatório responde, com números: (a) qual score melhor prevê recorrentes
  (ranking por correlação, por rede e agregado, com p-valor/IC); (b) o 0.40/0.60
  se sustenta? (decomposição renda × pop sobre os componentes joinados); (c) ≥1
  caso score alto ≠ desfecho bom, com hipótese do porquê.
- Aborda maturação: como NÃO há dado de maturação, registrar explicitamente a
  limitação e o viés que ela introduz (não comparar unidade nova com madura).
- `pytest -q` sem nada quebrado.
- `python analysis/score_backtest.py` roda fim a fim e (re)gera o relatório.
- Read-only: nenhuma escrita em `scoring.py`/`constants.py`/artefatos M1/`data/outputs/`.

## Criticidade classificada
Alta

## Esteira recomendada
Block Orchestrator → Planner → [revisão humana] → Builder → QA

## Riscos identificados
- **Sem maturação real** (`maturacao_status` é constante): o critério "controlar
  por maturação" não tem dado de suporte. Tratar como limitação declarada; o
  Planner decide se há proxy aceitável (idade ≈ não há) ou se fica como ressalva.
- **N pequeno por rede / domínio esparso:** EngCorpo só 34 usáveis, e
  `score_dominio_hibrido` só 43 no total ⇒ conclusões sobre domínio são frágeis;
  não forçar significância, reportar IC largo.
- **Componentes do M1 fora do dataset:** decomposição renda×pop exige join
  read-only com `brasil_priorizados.parquet` por `hex_id`; risco de hexes sem
  match (cobertura parcial) — reportar taxa de match e usar só linhas casadas.
- **Heterogeneidade de desfecho entre redes:** `alunos_recorrentes` vem de fontes
  distintas (Alunos EVO vs Alunos Totais vs alunos_total) e confiabilidades
  diferentes (medido vs estimado); correlações entre redes podem não ser
  comparáveis em nível — preferir análise dentro de rede + ranks. EngCorpo é
  estimado (alunos/m²×metragem), tratar com cautela.
- **Precisão de hex variável:** parte das unidades caiu por `cidade_centroide`
  (não `unidade`); o score do hex pode não refletir o ponto exato. Considerar
  segmentar/ponderar por `hex_precisao`.
- **Risco de scope-creep para BLK-SCORE-03:** qualquer tentação de "ajustar o peso
  já que renda/pop X" deve ser bloqueada — só achados, sem proposta.

## Guardrails ativos
- `M1_SCORE_OFICIAL = "score_priorizacao"`; pesos aprovados renda=0.40, pop=0.60
  (`PESOS_HEX_SCORE_ESTRUTURAL`) — somente LEITURA neste bloco.
- "Nenhuma trilha paralela pode alterar o M1 sem aprovação explícita."
- Regra de criticidade (CLAUDE.md 2026-05-30): LEITURA/ANÁLISE de score sem escrita
  em artefato M1 → Alta (revisão humana antes do Builder); ALTERAÇÃO de fórmula/
  pesos/artefato M1 → Crítica + DEC (= BLK-SCORE-03, fora deste bloco).
- Staging/saída: artefato de análise vai para `data/analysis/` (gitignored),
  NUNCA `data/outputs/`. PII fora de logs/handoff/relatório (só agregados).
- Não commitar dados brutos de validação (gitignored). Commit SÓ por path; nunca
  `git add -A`; `CLAUDE.md` (pré-sujo) NÃO entra neste ciclo.
- Guardrail permanente: visualizações/análises não podem recalcular nem alterar
  `score_priorizacao`, `hex_score_estrutural`, carteira, plano ou artefatos M1.
