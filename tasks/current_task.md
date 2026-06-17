# Current Task

## Bloco atual

ID: BLK-FIX-14
Nome: Isolamento do teste flaky test_classico_template_recente_inalterado
Status: APROVADO (QA 2026-06-17 11:54) — ciclo pronto para fechamento manual
Tipo: bug (isolamento de teste; READ-ONLY sobre M1)
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA (concluído)
Skill atual: QA (concluído)
Próxima Skill: Fechamento manual (merge humano)

## Objetivo
Identificar o teste poluidor que faz `test_classico_template_recente_inalterado` falhar na suíte
full serial (vazamento de estado global, provável em fpdf/censo_report ou cache de módulo) e corrigir
o ISOLAMENTO (só em tests/), deixando `python -m pytest -q` verde de forma reproduzível — sem mascarar.

## Classificação (Passo 2)
Bloco é Baixa no backlog, mas a própria nota prevê "Média se virar investigação ampla de isolamento
da suíte". O núcleo do trabalho É uma bisseção suite-wide + correção de vazamento de estado, e o
critério de aceite exige um gate de QA que re-rode a suíte full reproduzível → classificado MÉDIA.
Sem gate humano (Média não exige).

## Tiering de modelo (Passo 4) — Média + override
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: opus  (OVERRIDE +1 vs tabela Média: investigação de isolamento — bisseção + vazamento de
  estado global em fpdf/cache — é atipicamente sutil e há risco de "mascarar flakiness" se mal feita)
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-FIX-14 (criada a partir de main / HEAD e7b0f94)

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md

## Escopo permitido
- tests/** (fixtures/teardown/conftest.py); no máximo um ajuste de teardown/reset em helper de teste.
- NÃO alterar a lógica de produção de censo_report.py sem nova decisão.

## Fora de escopo
- score/pesos/artefatos M1; mudar a geração de PDF; mascarar com -p no:xdist ou skip.

## Diagnóstico Block Orchestrator (2026-06-17)
- Poluidor: externo ao arquivo (teste em posição 847; arquivo começa em 827; arquivo inteiro passa em 22)
- Vetor principal de estado global: `_ICON_CACHE` e `_ATLAS_CACHE` em `competitors.py` + `@functools.cache` em `_competitor_icon_svg`/`_ultra_icon_svg`
- `censo_report.py` confirmado sem lru_cache / variáveis mutáveis / estado de módulo
- Poluidor na faixa 1-826 (antes do arquivo export); test_streamlit_app.py (208-406) não usa preload_logos
- Candidato prioritário a investigar: test_api_analisar.py (scope=module, gera PDFs, posições 31-40) e test_api_geo.py
- Handoff: context/handoff/20260617-111443-block-orchestrator.md

## Resultado Builder (2026-06-17 11:42)
- Causa REAL confirmada empiricamente: NÃO era estado global (`_ICON_CACHE`/`_ATLAS_CACHE` ficam VAZIOS antes/depois; teste falha até ISOLADO). Era a hipótese ALTERNATIVA do Planner: `fpdf2` 2.8.7 carimba `/CreationDate` (+ `/ID` derivado) com `datetime.now()` por instância → `antes != depois` quando as 2 gerações cruzam a virada de segundo.
- Fix (só tests/): `tests/conftest.py` novo com fixture autouse scope=function `_freeze_fpdf_clock` que congela `datetime.now()` em `fpdf.fpdf`/`fpdf.output`. Produção intocada; sem skip/xfail/no:xdist.
- Validação: target isolado 1 passed; export file 22 passed; repro determinístico falha sem fixture e passa com; FULL serial 964 passed, 1 skipped, 0 failed; import ok; ruff+mypy limpos.
