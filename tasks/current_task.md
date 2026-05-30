# Current Task

## Bloco atual

Sem tarefa ativa.

Últimos ciclos (ambos CONCLUÍDOS e mergeados no `main` em 2026-05-29):
- **BLK-OPS-08** — Atualizar actions do CI para Node 24. Esteira Baixa (Block Orchestrator → Builder).
  Branch `ciclo/BLK-OPS-08`, commit `255785c`, merge `4578e37`. Diff cirúrgico de 3 tags
  (checkout@v4→v5, setup-python@v5→v6, docker-publish checkout@v4→v5).
- **BLK-OPS-02b** — Saneamento ruff/mypy + CI bloqueante. Esteira Alta completa
  (Block Orchestrator → Planner → [aprovação humana: Felipe Silva 2026-05-29] → Builder → QA).
  Branch `ciclo/BLK-OPS-02b`, commit `18c668a`. APROVADO pelo QA (re-execução independente):
  ruff 0, mypy 0, pytest 532/1, 4 hashes M1 idênticos, steps ruff/mypy agora bloqueantes no CI.

## Pendência humana
- `git push origin main` (opcional) para publicar os dois merges no GitHub.
- Pós-merge no CI: confirmar que o aviso "Node.js 20 actions are deprecated" sumiu; o CI agora
  REPROVA em qualquer violação ruff/mypy.

## Próximo passo recomendado (backlog)
- **BLK-ARCH-01** — concluir migração `src/` e remover legado (dependência de CI completo verde
  satisfeita; ruff/mypy bloqueantes agora são rede de segurança extra).
