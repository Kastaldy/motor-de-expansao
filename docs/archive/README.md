# `docs/archive/` — histórico preservado

Documentos **já implementados ou superados** que saíram do caminho de leitura primária, mas são
preservados para auditoria (o git também preserva o histórico). **Não** são fonte de verdade; cada um
aponta para o que o substituiu.

- `orquestracao_agentes.md` · `orquestracao_claude.md` — planos originais da esteira de agentes
  (maio/2026). A esteira descrita **já existe**: `.claude/commands/run-cycle.md`, `prompts/`,
  `.github/workflows/` (guard/claude-review), `REVIEW.md`. Orquestração viva = **/run-cycle + DEC-016**.
- `PLANO_ORQUESTRACAO_V2.md` — rascunho do plano ORQ (BLK-ORQ-10…18), **implementado** sob os IDs
  ORQ-20…27 e formalizado na **DEC-016** (`docs/decisions/DEC-016.md`). Mantido como registro.
- `PROMPT_PRD.md` — prompt do fluxo single-agent antigo ("execute o próximo bloco do PRD"), substituído
  pela esteira `/run-cycle` que lê `tasks/backlog.md`.
- `relatorio_analise_mercado.md` — snapshot analítico de maio/2026.

Fonte de verdade atual: `CLAUDE.md` (regras) · `tasks/backlog.md` (roadmap) · `docs/README.md` (índice).
