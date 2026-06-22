# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-DIM-17 — Fix: limiar de renda da zona morta (3.000 → 1.600)

## Objetivo
Alterar a constante `RENDA_ZONA_MORTA_MIN` de `3_000.0` para `1_600.0` em `viabilidade_ponto.py` e adicionar testes de fronteira do novo limiar para que o critério de aceite seja verificável.

## Escopo permitido
- Alterar `RENDA_ZONA_MORTA_MIN: float = 3_000.0` → `1_600.0` na linha 38 de `src/motor_expansao/dimensionamento/viabilidade_ponto.py`.
- Adicionar testes em `tests/unit/dimensionamento/test_viabilidade_ponto.py` que verifiquem explicitamente o comportamento de fronteira do novo limiar: `flag_zona_morta` deve disparar com `renda_per_capita_captacao < 1600.0` e NÃO disparar com `renda_per_capita_captacao >= 1600.0` (quando pop está acima do mínimo).
- Verificar e corrigir qualquer outro local que compare diretamente com o valor `3_000`/`3000` referente a `RENDA_ZONA_MORTA_MIN` em `src/` e `tests/`.

## Fora de escopo
- `src/motor_expansao/config.py` (M1 oficial) — `RENDA_MIN = 4_500.0` não tem relação; intocado.
- `src/motor_expansao/dimensionamento/config.py` — intocado.
- Qualquer pipeline, script de scoring, artefato M1 (`brasil_estrutural.parquet`, `brasil_priorizados.parquet`, etc.).
- `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio.
- Lógica interna de `flag_zona_morta()` — a assinatura e implementação da função ficam inalteradas; só a constante que lhe é passada muda.
- VPS, deploy, segredos, ingestão ao vivo.

## Arquivos que devem ser lidos
- `/repo/src/motor_expansao/dimensionamento/viabilidade_ponto.py` (inteiro — constante na linha 38, uso na linha 316, exportação na linha 402)
- `/repo/tests/unit/dimensionamento/test_viabilidade_ponto.py` (inteiro — verificar testes de `flag_zona_morta` existentes e confirmar ausência de asserts sobre o valor 3000)

## Arquivos que podem ser alterados
- `/repo/src/motor_expansao/dimensionamento/viabilidade_ponto.py` — apenas a linha da constante `RENDA_ZONA_MORTA_MIN`.
- `/repo/tests/unit/dimensionamento/test_viabilidade_ponto.py` — adicionar testes de fronteira do limiar de renda (1600).

## Critérios de aceite
- `RENDA_ZONA_MORTA_MIN == 1600.0` no módulo após a mudança (verificável por `grep` ou `python -c "from motor_expansao.dimensionamento.viabilidade_ponto import RENDA_ZONA_MORTA_MIN; assert RENDA_ZONA_MORTA_MIN == 1600.0"`).
- `flag_zona_morta({"pop_captacao": 50000.0, "renda_per_capita_captacao": 1500.0})` retorna `flag_zona_morta=True` (renda abaixo do novo limiar).
- `flag_zona_morta({"pop_captacao": 50000.0, "renda_per_capita_captacao": 1600.0})` retorna `flag_zona_morta=False` (exatamente no limiar não dispara).
- Nenhum assert sobre o valor `3000`/`3_000` referente a `RENDA_ZONA_MORTA_MIN` permanece nos testes sem atualização.
- Suite `pytest -q` verde sem alteração de score, pesos ou artefatos M1.
- `ruff check` e `mypy` limpos nos arquivos alterados.

## Criticidade classificada
Média

## Esteira recomendada
Block Orchestrator → Planner → Builder → QA

## Riscos identificados
- Risco baixo: a mudança é uma constante de alerta/exibição; não altera cálculo de margem, payback, ROIC nem o M1.
- Os testes existentes de `flag_zona_morta` usam `renda=5000.0` e `renda=6000.0` — nenhum asserta o valor `3000` explicitamente; portanto nenhum teste quebra automaticamente com a mudança. O Builder deve ADICIONAR testes de fronteira em `1600.0` para que o critério de aceite seja verificável.
- Confirmar na fase de Builder se há outros arquivos além de `viabilidade_ponto.py` que hardcodam `3_000` referindo-se a `RENDA_ZONA_MORTA_MIN` (grep inicial não encontrou, mas verificar em `src/` e `tests/` completos antes de fechar).

## Guardrails ativos
- READ-ONLY sobre M1: não tocar `score_priorizacao`, `hex_score_estrutural`, carteira, plano, artefatos oficiais (CLAUDE.md §5 guardrail permanente).
- `RENDA_MIN = 4_500.0` em `config.py` do M1: INTOCADO (parâmetro canônico §3).
- Nenhum PR sobe com CI quebrado (CLAUDE.md §2).
- Modo loop autônomo: bloco marcado `loop-safe`; sem gate humano interativo.
