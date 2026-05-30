# Current Task

## Bloco atual

ID: BLK-ARCH-01b
Nome: Tipar os 14 módulos migrados e remover o override de mypy
Status: aprovado
Tipo: refatoração
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA
Skill atual: QA
Próxima Skill: Fechamento manual (orquestrador: Passo 6.0 + commit por path + merge)
dry_run: false

## Objetivo
Corrigir os ~50 erros de tipo latentes nos 14 módulos de `src/motor_expansao/pipelines/`
listados no bloco `[[tool.mypy.overrides]]` de `pyproject.toml` e remover esse override,
trazendo os módulos ao gate `mypy src/` de verdade — sem alterar comportamento/valores,
score ou artefatos M1 (não-mutação provada por hash sha256 idêntico pré/pós).

## Paths do ciclo (commit por path — NUNCA git add -A)
src/motor_expansao/pipelines/{calcular_colunas_mercado, calcular_penetracao_ultra_hex,
comparar_geofusion_vs_hex, enriquecimento_espacial_hexagonos, normalizar_unidades_ultra,
gerar_carteira_acionavel, modelo_hibrido_expansao, validar_modelo_ultra,
validar_penetracao_ultra_hex, materializar_setores_censitarios_geo, fase_a_censo2022_setores,
validar_fase_a_censo2022, fase_a_piloto_expandido, fase_a_nacional_completo}.py ·
pyproject.toml (remover override) · (eventuais testes tocados) ·
tasks/current_task.md · tasks/backlog.md · tasks/completed.md ·
context/handoff.md · context/handoff/

## Contexto de abertura
- Branch isolado: `ciclo/BLK-ARCH-01b` (criado a partir do HEAD de main, que já contém o merge
  de BLK-ARCH-01a — dependência ✅ satisfeita).
- Worktree limpo na abertura; commitar SÓ por path.
- Este ciclo NÃO altera a orquestração → dry-run 6.c NÃO dispara.
