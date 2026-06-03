# Current Task

## Bloco atual

ID: BLK-FIX-06
Nome: Hexágonos do litoral recortados pelo pipeline
Status: aprovado (QA APROVADO, 2026-06-03)
Tipo: bug (toca base M1 → regenera artefatos oficiais)
Criticidade: crítica
Esteira: Block Orchestrator → Planner → [aprovação humana + DEC] → Builder → QA
Skill atual: QA/Quality Analyzer (concluída — VEREDITO APROVADO)
Próxima Skill: Orquestrador (fechamento: 6.0 housekeeping move → 6.a commit por path → 6.b merge humano)
dry_run: false

## Veredito do QA (2026-06-03)
APROVADO. Suíte FULL `python -m pytest -n auto`: **656 passed, 1 skipped, 0 failed** (exit 0);
smoke `import streamlit_app` ok. Verificação INDEPENDENTE da regeneração: total base oficial
= **1.538.424** hexes (contado por mim; +474), Praia Grande `87a810c02ffffff` e RJ
`87a8a078cffffff` presentes em base + oportunidades; oportunidades 1.538.424 linhas / 45 cols
com TODOS os 8 campos mínimos do score; priorizados 307.674. Guardrails: pesos
renda=0.40/pop=0.60 (`constants.py`) e fórmula/score INALTERADOS (nenhum arquivo de score no
diff); canônicos §3 intactos (H3=7, DIST=1.0, RENDA_MIN=4500.0; só ADIÇÃO de
M1_HEX_LAND_FRACTION_MIN=0.20); DEC-002 registrada e APROVADA, DEC-001 e §3 não tocados.
Housekeeping `--check` PRÉ-move: exit 1 "stub ausente no backlog para BLK-FIX-06" (helper
reconhece o bloco — pronto para o 6.0). Escopo respeitado; scratch limpo. Sem bloqueadores.

## Estado da Fase B (Builder, 2026-06-03)
DEC-002 APROVADA (Felipe Silva, 2026-06-03; limiar 0.20) registrada em CLAUDE.md §8.
Artefatos oficiais REGENERADOS offline/determinístico: universo 1.537.950 → **1.538.424**
hexes (+474 costeiros; removidos=218). brasil_priorizados 307.579 → 307.674; enriquecido
particionado 1.538.424 (27 UFs). Repro litoral confirmada nos oficiais (Praia Grande
`87a810c02ffffff`, RJ `87a8a078cffffff` em base+oportunidades+dashboard). Campos mínimos
do score presentes; pesos 0.40/0.60 e fórmula INALTERADOS; colunas oficiais preservadas.
Docstring de base_h3_brasil.py atualizada (híbrido + DEC-002). Scratch limpo (evidência
mantida). Subconjunto de testes: **217 passed, 0 failed, 0 skipped**; `import streamlit_app` ok.
SUÍTE FULL é gate do QA.

## Objetivo
Incluir no universo do M1 os hexágonos litorâneos que sobrepõem terra/população real (hoje descartados por filtro de centróide em `base_h3_brasil.py`), sem distorcer o M1, mediante decisão registrada (DEC) — quantificando o impacto em contagens/percentis/score ANTES de regenerar qualquer artefato oficial.

## Tiering de modelo (Passo 4)
Criticidade CRÍTICA → BO=opus, Planner=opus, Builder=opus, QA=opus (QA sempre Opus 4.8). Sem override.

## Observação de orquestração
Ciclo CRÍTICO + DEC: pausa obrigatória após o Planner para aprovação humana explícita + registro de DEC ANTES de spawnar o Builder. Ciclo NÃO altera a orquestração (run-cycle/prompts/esteira) → NÃO dispara dry-run autônomo (Passo 6.c). dry_run desta execução = false.

## Revisão do plano
v2 (ajuste humano de Felipe Silva, 2026-06-03): limiar candidato 0.30 → **0.20**; default de `M1_HEX_LAND_FRACTION_MIN` = 0.20. Fase A passa a medir um **LEQUE de limiares {0.15, 0.20, 0.25, 0.30}** por re-filtragem barata de um vetor de `fracao_terra` (interseção calculada 1× por hex). O delta CARO (percentis nacionais + `score_priorizacao` + top-20%/UF) é medido por regeneração em scratch para **0.20 E 0.30** (0.15/0.25 só contagem/massa, salvo se barato). DEC-002 ancorada em candidato=0.20.

## Paths do ciclo (commit por path — refinado pelo Planner, v2)
Critério recomendado: HÍBRIDO (centróide-dentro OU fração-de-área-de-terra ≥ M1_HEX_LAND_FRACTION_MIN; candidato 0.20). Builder em 2 fases (A medição em scratch → DEC-002 → B aplicação).
### Fase A (medição — NÃO toca oficiais)
- src/motor_expansao/pipelines/m1/base_h3_brasil.py (critério geométrico híbrido; reusa `_hex_polygon`; novo contador `recuperados_costeiros`; expõe vetor de `fracao_terra` p/ leque)
- src/motor_expansao/config.py (NOVO `M1_HEX_LAND_FRACTION_MIN = 0.20`; canônicos inalterados)
- tests/integration/test_base_h3_brasil.py (casos sintéticos novos: costeiro mantido, mar descartado, interior inalterado, borda 0.20, re-filtragem do leque)
- scripts/medir_impacto_litoral_blk_fix_06.py (NOVO, scratch → `*.tmp.parquet`, `data/staging/brasil_litoral_tmp*/`; interseção 1× + leque {0.15,0.20,0.25,0.30} + delta caro 0.20/0.30)
- data/reports/base_h3_litoral_impacto.md (NOVO, relatório de delta com TABELA por limiar — insumo da DEC)
### Fase A — CONCLUÍDA (Builder, 2026-06-03)
- Critério híbrido + `M1_HEX_LAND_FRACTION_MIN=0.20` + testes implementados; medição em
  scratch executada (exit 0). Relatório: `data/reports/base_h3_litoral_impacto.md`
  (+ `base_h3_litoral_leque.csv`). NENHUM artefato oficial escrito (mtime 2026-05-26 intacto).
- Números-chave: leque 0.15→494 / **0.20→474** / 0.25→428 / 0.30→383 recuperados sobre
  1.537.950. DELTA CARO REAL (0.20 e 0.30): impacto nos hexes existentes ~NULO (mediana 0.0;
  máx score 0.01; 0 hexes além de ±0.5). Top-20%/UF: 0.20 entram 136/saem 41; 0.30 entram
  104/saem 28. Repro: Praia Grande SP `87a810c02ffffff` (frac 0.231, volta em 0.15/0.20) e
  RJ `87a8a078cffffff` (frac 0.401, volta em todos). Validações: 181 passed; import ok.
- Próximo: humano lê o relatório, decide o limiar final (candidato 0.20) e registra a
  **DEC-002** em CLAUDE.md §8 ANTES de liberar a Fase B.

### [CHECKPOINT: aprovação humana + DEC-002 sobre o delta real]
### Fase B (aplicação — SOMENTE após DEC-002)
- artefatos M1 oficiais regenerados (brasil_estrutural/priorizados/oportunidades; dashboard/sample/CSVs; enriquecido particionado)
- data/reports/base_h3_brasil.md (gerado); docs/m1_outputs_oficiais.md (se contagens mudarem)
- CLAUDE.md §8 (DEC-002)
- tasks/current_task.md + tasks/completed.md + tasks/backlog.md (housekeeping)
- context/handoff.md + context/handoff/
