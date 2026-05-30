# Current Task

## Bloco atual

ID: BLK-ARCH-01
Nome: Concluir migração `src/` e remover legado (FATIA-1)
Status: APROVADO (housekeeping 6.0 feito; aguardando commit por path + merge humano)
Tipo: refatoração
Criticidade: alta
Esteira: Block Orchestrator → Planner → [APROVAÇÃO HUMANA: ok 2026-05-29] → Builder → QA
Skill atual: run-cycle (fechamento)
Próxima Skill: —
dry_run: false

## Resultado (APROVADO pelo QA)
- FATIA-1 (núcleo M1 + dashboard): removidos 3 wrappers de raiz; `dashboard/constants.py`+`utils.py`
  movidos para `src/motor_expansao/dashboard/` (imports invertidos, pacote flat removido);
  `ibge_censo.py`+`poi_enrichment.py` para `src/.../pipelines/m1/` (branches mortos `jobs.pipelines.*`
  limpos); `config.py` para `src/motor_expansao/config.py` (branch morto `api.config` limpo). Tudo
  via `git mv`, sem mudar funções/assinaturas/valores.
- `jobs/pipelines/*` NÃO migrado nesta fatia → registrado como BLK-ARCH-01a no backlog.
- Validações (QA re-executou, sem bypass): `pytest -q` → 541 passed, 1 skipped, 0 failed;
  `import streamlit_app` ok; `ruff check .` limpo; `mypy src/` Success (23 arquivos); greps de
  import legado vazios em código vivo.
- Prova de não-mutação M1: 4 artefatos oficiais com sha256 byte-idêntico pré/pós. Params canônicos
  intactos (H3_RESOLUTION=7, pesos 0.40/0.60, DIST_MIN_ULTRA_KM=1.0, RENDA_MIN=4500.0).
- 3 desvios do plano auditados como legítimos pelo QA (teste obsoleto de wrappers; reaponte de
  strings patch/monkeypatch; 1 linha de import em 2 módulos jobs/pipelines exercidos por testes
  em escopo — rewiring mínimo forçado pela remoção do wrapper, sem migração estrutural de jobs/).

## Paths do ciclo (commit por path — NUNCA git add -A)
src/motor_expansao/config.py · src/motor_expansao/dashboard/constants.py ·
src/motor_expansao/dashboard/utils.py · src/motor_expansao/pipelines/m1/ibge_censo.py ·
src/motor_expansao/pipelines/m1/poi_enrichment.py · src/motor_expansao/dashboard/* (imports) ·
src/motor_expansao/pipelines/m1/* (imports) · src/motor_expansao/core/constants.py ·
streamlit_app.py · tests/** (reapontados) ·
jobs/pipelines/{fase_a_censo2022_setores,teste_setor_censitario_2010}.py (só import) ·
dashboard/ (removido) · base_h3_brasil.py + hex_enrichment.py + fase1_bi_exports.py (raiz, removidos) ·
ibge_censo.py + poi_enrichment.py + config.py (raiz, movidos) ·
tasks/current_task.md · tasks/backlog.md · tasks/completed.md · context/handoff.md · context/handoff/

## Pendência humana
- Revisar a branch ciclo/BLK-ARCH-01 e fazer o merge em main (Passo 6.b).
- Este ciclo NÃO altera a orquestração (run-cycle/prompts/esteira) → dry-run 6.c NÃO dispara.
