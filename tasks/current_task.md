# Current Task

## Bloco atual

ID: BLK-PROD-03
Nome: Avaliar hex_id como category com benchmark
Status: aguardando QA
Tipo: benchmark/relatório (READ-ONLY sobre o M1)
Criticidade: Média
Esteira: Block Orchestrator (concluído) → Builder (concluído) → QA
Skill atual: Builder (concluído)
Próxima Skill: QA

## Objetivo
Materializar relatório `data/analysis/benchmark_hexid_category.md` com benchmark reprodutível
de string vs category em carga/join dos parquets de staging.
NÃO alterar código de produção (decisão pré-fixada não atingida).

## Decisão pré-fixada (confirmada na delimitação)
A mudança NÃO deve ser aplicada:
- hex_id é 100% única em todos os parquets (cardinalidade = N linhas)
- Merge/join: category 23% MAIS LENTO
- Memória hex_id: category +40 MB MAIOR (pior)
- Ganho de 15% em tempo OU memória NÃO atingido

## Branch do ciclo
ciclo/loop-20260707-123809

## Guardrails
- §5 READ-ONLY M1: nenhuma escrita em config.py/pipelines/m1/artefatos oficiais.
- §6.1 loop-safe: sem VPS, sem rede, escreve só data/analysis.
- loop_guard.py limpo obrigatório.
