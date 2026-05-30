# Handoff — QA/Quality Analyzer — BLK-OPS-10 (Automatizar housekeeping no Passo 6)

## Skill que gerou este handoff
QA/Quality Analyzer (re-execução independente; consolidado no orquestrador)

## Próxima Skill recomendada
Fechamento manual → commit por path → merge humano → dry-run autônomo (6.c)

## VEREDITO
APROVADO

## Justificativa
Helper versionado, puro e testado (10 casos verdes), faz o move byte-idêntico (fatia literal,
CRLF preservado); 6.0 + 6.c + checklist do QA atualizados de forma coerente; suíte completa verde
(542 passed) e smoke de CLI contra conteúdo REAL (sem bypass) confirma move/--check/ad-hoc.

## Escopo entregue (4 arquivos substantivos + bookkeeping)
- scripts/housekeeping_move_block.py (NOVO): move_block/verify_moved (puros) + CLI (--check, EXIT_AD_HOC=3).
- tests/unit/test_housekeeping_helper.py (NOVO): 10 testes (fatia literal, stub, append-only,
  BlockNotFound, verify pré/pós, idempotência re-entrante, CRLF byte-identity + verify CRLF, 3 de CLI/rc).
- .claude/commands/run-cycle.md: Passo 6.0 (move via helper, antes de 6.a) + bullet 6.c (dummy block na
  branch, abandona sem merge) + guardrail permanente. Rótulos 6.a–6.d preservados.
- prompts/qa_analyzer.md: seção "Housekeeping de concluídos (fechamento)" exigindo --check + byte-identity
  vs git HEAD + pytest com o teste do helper; ad-hoc → "N/A".

## Notas de implementação do humano — atendidas
1. moved = backlog[start:content_end] (fatia literal por offset de caractere). OK (test_moved_is_literal_byte_identical_slice + CRLF).
2. CLI abre com newline="" + utf-8 (preserva CRLF disco↔memória). OK (test_crlf_*; smoke real CRLF).
3. Caso de idempotência re-entrante (2º move → BlockNotFound). OK (test_idempotent_reentrant_second_move_raises).

## Defeito encontrado e corrigido durante o QA (no-bypass real)
O smoke contra conteúdo REAL (CRLF) reprovou o `--check` inicial: a regex do stub terminava em ` *$`,
que não tolera o `\r` antes do `\n` em CRLF → "stub ausente" falso. Corrigido para `[ \t\r]*$` e
adicionado assert de `verify_moved` em CRLF no teste. (Os testes só com LF não pegavam — o smoke real pegou.)
Também: ruff I001 (import block) no helper, auto-corrigido com `ruff check --fix` (reordenação cosmética).

## Saída literal das validações (re-executadas pelo QA)
### pytest -q (suíte completa)
```
542 passed, 1 skipped, 9 warnings in 139.34s
```
### ruff check scripts/housekeeping_move_block.py tests/unit/test_housekeeping_helper.py
```
All checks passed!
```
### CLI smoke contra cópia do backlog/completed REAIS (CRLF), bloco real BLK-OPS-03
```
move rc=0 ; --check rc=0 (CHECK_OK) ; ad-hoc BLK-NOPE-99 rc=3 (SKIP, sem traceback)
byte-identity: moved (2196 bytes) verbatim em completed=True; stub no backlog=True; heading removido=True; completed append-only=True
```

## Conferência de no-bypass
Sem `--config /dev/null`, sem mock do caminho crítico. O smoke roda o CLI REAL sobre cópia do
backlog/completed REAIS (estrutura/CRLF de produção), não fixture sintética. pytest usa fixtures
legítimas de unidade (prática normal). Validação efetivamente executada.

## Guardrails verificados
- score_priorizacao/artefatos M1 não alterados: sim (N/A — doc/tooling de orquestração).
- Escopo respeitado: sim — só os 4 arquivos + bookkeeping; NÃO tocou M1/CLAUDE.md/conteúdo do backlog.
- Guard de recursão (dry_run: true) intacto: sim (6.c inalterado nesse ponto).

## Decisão recomendada
Fechar ciclo: commit por path → merge humano → (pós-merge) dry-run autônomo 6.c (ciclo ALTERA a orquestração).
