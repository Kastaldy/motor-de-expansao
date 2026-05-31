# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-SCORE-01a — Melhorar match de nome do Engenharia do Corpo (EngCorpo).**
No BLK-SCORE-01 (mergeado), o match do EngCorpo no `dataset_validacao.parquet` ficou em ~31/61 unidades
porque foi feito por **nome exato normalizado** (`normalize_name` + `join_label_by_name` em
`analysis/build_validation_dataset.py::load_engcorpo`). A planilha de desfecho
(`data/validacao/academias_engenharia_do_corpo.xlsx`, sheet `Academias`) prefixa cada unidade com
`EC -`/`ECB -` (ex.: `EC - VACARIA, RS`), enquanto o staging
(`data/staging/concorrentes_mapeados.parquet`, `rede=="engenharia_do_corpo"`) e o CSV de coordenadas
(`concorrentes/unidades_engenharia_do_corpo.csv`) usam o nome cru (`Vacaria, RS`). Removendo o prefixo +
fuzzy determinístico (difflib, cutoff documentado) + fallback cidade+UF, a recuperação sobe para ~38/61.
Tudo **READ-ONLY sobre o M1** (só leitura/join; grava em `data/analysis/`, gitignored).

Confirmado em disco (2026-05-31): `concorrentes/unidades_engenharia_do_corpo.csv` e
`concorrentes/Unidades/unidades_engenharia_do_corpo.csv` existem, ambos com schema
`nome_unidade;latitude;longitude;data_coleta` (`sep=";"`, `utf-8-sig`; ex.: `Vacaria, RS;-28.5002326;-50.9329859;2026-05-26`)
— mesma convenção de nome cru do staging, viável como fonte de coordenadas para resolver hex via `latlng_to_h3`.

## Objetivo
Elevar materialmente o match do EngCorpo (acima do baseline 31/61) no `dataset_validacao.parquet`
espelhando a cascata determinística já aprovada do Skyfit, sem inventar correspondências e marcando os não-casados — tudo read-only sobre o M1.

## Escopo permitido
- Em `analysis/build_validation_dataset.py`, melhorar **apenas a etapa de match EngCorpo** (`load_engcorpo` e helpers de normalização):
  - Normalização que **remove o prefixo `EC`/`ECB`** (incl. variantes com hífen/espaço, ex.: `EC -`, `ECB -`) e ruído, dos dois lados do join.
  - **Cascata determinística** espelhando o padrão Skyfit (`match_skyfit_coords`): `nome_exato` → `nome_fuzzy` (difflib `get_close_matches`, **cutoff documentado**, ex.: ≥0.80) → fallback `cidade+UF`.
- **Avaliar** usar `concorrentes/unidades_engenharia_do_corpo.csv` (e/ou `concorrentes/Unidades/unidades_engenharia_do_corpo.csv`) como fonte de coordenadas direta para resolver hex via `latlng_to_h3` (mesma abordagem coords-por-CSV + match-por-nome do Skyfit), em vez de depender só do hex do staging. Verificar schema/coords/duplicidade entre os dois CSVs antes de escolher (Planner decide a fonte canônica).
- Anexar `hex_origem`/`hex_precisao` ao EngCorpo (colunas já existem no esquema) refletindo a origem do match (ex.: `nome_exato`/`nome_fuzzy`/`cidade_centroide`/`hex_staging`/`latlng`/`nao_resolvido`).
- Adicionar casos de teste em `tests/unit/test_validation_dataset.py` para a nova lógica EngCorpo (fixtures sintéticas, sem dados reais).
- Regenerar os 2 artefatos em `data/analysis/`: `dataset_validacao.parquet` e `relatorio_auditoria_rotulo.md` (ambos gitignored).

## Fora de escopo
- Qualquer escrita em artefato M1 ou alteração de score/fórmula/peso/carteira/plano. **Apenas leitura e join.**
- Fuzzy **não-determinístico** (qualquer coisa que quebre o CI / dependa de ordenação ambígua ou de seed).
- Geocodificação de endereço **ao vivo** (BLK-PROD-05) — só leitura de arquivo local.
- Alterar a lógica de Ultra ou Skyfit, ou o restante do esquema; não expandir para BLK-SCORE-02/03.
- Tocar `CLAUDE.md` ou commitar o `M CLAUDE.md` pré-sujo do worktree.

## Arquivos que devem ser lidos
- `analysis/build_validation_dataset.py` (etapa de match EngCorpo atual + padrão de cascata Skyfit `match_skyfit_coords`/`normalize_name_skyfit` a espelhar)
- `data/validacao/academias_engenharia_do_corpo.xlsx` (sheet `Academias` — desfecho; nomes prefixados `EC -`/`ECB -`)
- `data/staging/concorrentes_mapeados.parquet` (`rede=="engenharia_do_corpo"`, `status_registro=="valido"` — hex via nome cru)
- `concorrentes/unidades_engenharia_do_corpo.csv` (coords; `nome_unidade;latitude;longitude;data_coleta`; `sep=";"`, `utf-8-sig`)
- `concorrentes/Unidades/unidades_engenharia_do_corpo.csv` (coords alternativas — comparar com a de cima)
- `context/handoff/20260530-235959-planner.md` (seção `## REVISÃO 2 — Skyfit FINAL (SUPERSEDE)` — padrão de cascata determinística aprovado)
- `tests/unit/test_validation_dataset.py` (padrão de fixtures sintéticas já existente)

## Arquivos que podem ser alterados
- `analysis/build_validation_dataset.py` (melhoria da etapa de match EngCorpo)
- `tests/unit/test_validation_dataset.py` (casos novos de match EngCorpo)
- `data/analysis/dataset_validacao.parquet` (regerado — gitignored)
- `data/analysis/relatorio_auditoria_rotulo.md` (regerado — gitignored)
- Arquivos de fluxo do ciclo: `tasks/current_task.md`, `tasks/backlog.md`, `tasks/completed.md`, `context/handoff.md`, `context/handoff/`
- **NÃO alterar:** `CLAUDE.md`; qualquer artefato/código do M1; `data/validacao/README.md`.

## Critérios de aceite
- Match EngCorpo **materialmente acima do baseline 31/61** (alvo de referência ~38/61); cada unidade casada tem `hex_origem`/`hex_precisao` coerentes.
- Não-casados **marcados** (`rotulo_casado=False`/`hex_resolvido=False`), **nunca descartados** nem casados de forma incorreta.
- Cascata **determinística**: mesmo input → mesmo output; verde no CI sem dados reais (toda a lógica coberta por fixtures sintéticas).
- **Nenhum falso-positivo**: validar uma amostra dos pares fuzzy aceitos — cidade/UF devem bater (exigir concordância cidade+UF no tier fuzzy).
- `relatorio_auditoria_rotulo.md` atualizado com a nova cobertura EngCorpo por `hex_origem` e a lista **agregada, sem PII** de não-casados remanescentes.
- Validações obrigatórias verdes:
  - `pytest -q tests/unit/test_validation_dataset.py`
  - `pytest -q` (sem regressão; baseline **532 passed, 1 skipped**)
  - `python -m analysis.build_validation_dataset` (regenera dataset + relatório fim a fim)
- Read-only confirmado: `git status` limpo nos paths oficiais do M1.

## Criticidade classificada
Alta

> Justificativa (CLAUDE.md, regra de criticidade decidida em 2026-05-30): "LEITURA/ANÁLISE de score sem
> escrita em artefato M1 → Alta (revisão humana antes do Builder)". Este bloco é **READ-ONLY sobre o M1**:
> só lê fontes (planilha/staging/CSV/scores) e grava artefatos derivados em `data/analysis/` (gitignored).
> **NÃO é Crítica** porque não toca `score_priorizacao`, `hex_score_estrutural`, fórmula, pesos, carteira,
> plano curto prazo, plano de domínio nem qualquer artefato oficial do M1. Mesmo padrão do BLK-SCORE-01.

## Esteira recomendada
Block Orchestrator → Planner → [revisão humana] → Builder → QA

## Riscos identificados
- **Falso-positivo no fuzzy** (casar unidade errada da mesma cidade ou homônimo) → mitigar exigindo concordância de **cidade+UF** no tier fuzzy e auditando amostra dos pares aceitos; cutoff documentado e conservador.
- **Divergência de convenção de nome** (`EC -`/`ECB -` na planilha vs. nome cru no staging/CSV) → normalização tem de remover o prefixo nos **dois lados** antes de comparar.
- **Duas fontes de coords EngCorpo** (`concorrentes/` vs `concorrentes/Unidades/`) podem divergir/duplicar → o Planner deve escolher a fonte canônica e tratar duplicatas de forma determinística (primeira ocorrência por chave).
- **Não-determinismo em CI** se a cascata depender de ordenação ambígua → fixar ordem (ordem do arquivo, dedup `keep="first"`), espelhando `match_skyfit_coords`.
- **PII** (nomes de unidade) vazar em log/handoff/relatório → manter apenas agregados no relatório e no stdout.
- **Cardinalidade** (62 planilha vs 63 staging) → diffs vão para a auditoria, não falham o build; nenhuma unidade descartada.
- **Regressão acidental** na lógica Ultra/Skyfit ao mexer em helpers compartilhados (`normalize_name`) → preferir helper EngCorpo-específico para não alterar o comportamento já validado das outras redes.

## Guardrails ativos
- READ-ONLY sobre o M1: nenhuma escrita em parquet/CSV oficial do M1; nenhum recálculo de `score_priorizacao`/`hex_score_estrutural`/carteira/plano/artefatos oficiais (CLAUDE.md §3, §5 guardrail permanente).
- Artefatos de saída em `data/analysis/`, **nunca** em `data/outputs/`; ambos gitignored. PII fora de logs/handoff/relatório.
- CSVs do projeto: `sep=";"`, `encoding="utf-8-sig"` (CLAUDE.md §2). `H3_RESOLUTION = 7` (CLAUDE.md §3).
- Sem fuzzy não-determinístico; toda mudança relevante entra com teste; nenhum PR sobe com CI quebrado (CLAUDE.md §2).
- Criticidade Alta ⇒ **gate de revisão humana APÓS o Planner, ANTES do Builder**.
- Commit **só por path** (NUNCA `git add -A`); `CLAUDE.md` NÃO entra no commit (worktree pré-sujo `M CLAUDE.md` não deve ser commitado).
- Um bloco por vez: não resolver BLK-SCORE-02/03 nem expandir escopo.
