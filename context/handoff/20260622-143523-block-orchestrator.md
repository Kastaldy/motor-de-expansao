# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-DIM-19 — Fix: flag de viável (payback 60 → 36 meses) e exibir payback real (remover "Nunca")**

Duas correções de produto aprovadas por Felipe (2026-06-22):
1. `flag_viavel` em `ViabilidadeResult` usa `payback_meses <= 60`; mudar para `<= 36`.
2. O card "Payback" no dashboard exibe `"> 60 / nunca"` quando `payback == float("inf")`; substituir pelo texto `"> 60 meses"` (sempre mostrar número, nunca o texto "Nunca").

## Objetivo
Corrigir o teto de payback de 60 para 36 meses no simulador e eliminar o texto "Nunca" do display de payback no dashboard, atualizando os testes afetados.

## Escopo permitido
- `src/motor_expansao/dimensionamento/simulador.py` linha 302: `payback_meses <= 60` → `payback_meses <= 36`.
- `src/motor_expansao/dimensionamento/simulador.py` linha 74 (docstring de `ViabilidadeResult`): atualizar `payback_meses <= 60` para `payback_meses <= 36`.
- `src/motor_expansao/dashboard/pages.py` linha 3377: substituir `f"> 60 / nunca"` por `"> 60 meses"` (mantendo o `else` mas com texto correto).
- `tests/unit/dimensionamento/test_simulador.py` linha 193: `assert r.payback_meses <= 60` — permanece correto como verificação do valor numérico (~57 meses); NÃO alterar esse assert.
- `tests/unit/dimensionamento/test_simulador.py` linhas 214-217 (CA-07d): `test_flag_viavel_verdadeiro_com_capex_menor` — payback ~57 meses > 36 ⇒ `flag_viavel` passa a ser `False`; atualizar docstring e asserção de `True` para `False`.
- Adicionar testes de fronteira: payback ≤ 36 meses → `flag_viavel=True`; payback entre 37 e 60 meses → `flag_viavel=False`.
- Adicionar teste de display: `payback == float("inf")` → string exibida é `"> 60 meses"` (não contém "Nunca").

## Fora de escopo (invioláveis)
- `/repo/src/motor_expansao/config.py` (config.py do M1) — não tocar.
- `/repo/src/motor_expansao/dimensionamento/config.py` — não tocar.
- `RENDA_MIN`, pesos/fórmula do M1, `score_priorizacao`, `hex_score_estrutural`, artefatos oficiais.
- `flag_viavel` dos hexágonos M1 (campo nos datasets de hexágonos, completamente distinto de `ViabilidadeResult.flag_viavel`).
- `viabilidade_ponto.py` — não é o arquivo onde fica a constante de payback.
- Qualquer outro arquivo não listado no escopo permitido.

## Arquivos que devem ser lidos
- `/repo/src/motor_expansao/dimensionamento/simulador.py` (linhas 60-85 docstring; linhas 295-314 `flag_viavel`)
- `/repo/src/motor_expansao/dashboard/pages.py` (linhas 3370-3390 card Payback)
- `/repo/tests/unit/dimensionamento/test_simulador.py` (linhas 1-50 fixtures; linhas 184-220 CA-07a/CA-07d)

## Arquivos que podem ser alterados
- `/repo/src/motor_expansao/dimensionamento/simulador.py`
- `/repo/src/motor_expansao/dashboard/pages.py`
- `/repo/tests/unit/dimensionamento/test_simulador.py`

## Critérios de aceite
- `viabilidade(capex=600_000, ...)` (cenário VIAVEL, payback ~57 meses): `flag_viavel is False` (57 > 36).
- Cenário com payback ≤ 36 meses (ex.: capex suficientemente baixo): `flag_viavel is True`.
- Cenário com `payback == float("inf")`: o display do card retorna a string `"> 60 meses"` e NÃO contém "Nunca" nem "/".
- Docstring de `ViabilidadeResult.flag_viavel` menciona `payback_meses <= 36`.
- `pytest -q` verde (sem falhas, sem regressões na suite completa).
- `ruff check` e `mypy` limpos nos arquivos alterados.
- Nenhum artefato M1 alterado; `config.py` intocado; `flag_viavel` dos hexágonos intocado.

## Criticidade classificada
Média

## Esteira recomendada
Block Orchestrator → **Planner** → Builder → QA

## Riscos identificados
- **Confusão entre dois `flag_viavel`**: `ViabilidadeResult.flag_viavel` (camada DIM, `simulador.py`) é completamente distinto do campo `flag_viavel` nos datasets de hexágonos M1. O Builder NÃO deve tocar o segundo.
- **CA-07a (`test_payback_finito_com_capex_menor`)**: o assert `r.payback_meses <= 60` permanece correto como verificação do valor numérico do payback (~57), não da flag. O Builder deve deixar esse assert intocado e só atualizar CA-07d.
- **Display `"> 60 meses"`**: a janela de simulação do loop permanece 60 meses; o texto `"> 60 meses"` é semanticamente correto (payback não ocorreu dentro dos 60 meses simulados). Não alterar a janela de simulação.

## Guardrails ativos
- READ-ONLY sobre M1: não recalcula `score_priorizacao`, `hex_score_estrutural`, carteira, plano, artefatos oficiais.
- Visualizações e interações de mapa não podem recalcular ou alterar artefatos oficiais do M1 sem aprovação explícita (§5 CLAUDE.md).
- `config.py` e `PRD.md` são fontes canônicas de parâmetros — não alterar.
- Bloco loop-safe: sem toque em VPS/deploy/segredos/PII/ingestão ao vivo.
