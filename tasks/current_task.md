# Current Task

## Bloco atual

ID: BLK-SCORE-01a
Nome: Melhorar match de nome do Engenharia do Corpo
Status: em execução
Tipo: feature (análise / melhoria de match — read-only sobre M1)
Criticidade: Alta (LEITURA/ANÁLISE de score sem escrita em artefato M1 → revisão humana antes do Builder; mesmo padrão do BLK-SCORE-01)
Esteira: Block Orchestrator → Planner → [revisão humana] → Builder → QA
Skill atual: Orquestrador (fechamento)
Próxima Skill: — (ciclo concluído; merge pelo humano)
Status final: APROVADO (QA 2026-05-31)
dry_run: false

## Objetivo
Elevar a cobertura de hex/scores do Engenharia do Corpo (EngCorpo) no `data/analysis/dataset_validacao.parquet`
melhorando o match de nome (remoção de prefixo `EC`/`ECB` + cascata determinística nome_exato → nome_fuzzy
(difflib, cutoff documentado) → fallback cidade+UF, espelhando o padrão aprovado do Skyfit), sem inventar
correspondências, mantendo tudo READ-ONLY sobre o M1 e marcando os não-casados.

## Guardrails do ciclo (do backlog)
- FORA DE ESCOPO: qualquer escrita em artefato M1 ou alteração de score. Apenas leitura e join.
- READ-ONLY sobre o M1; artefato em `data/analysis/`, nunca `data/outputs/`. PII fora de logs/handoff/relatório.
- CSVs do projeto `sep=";"`, `utf-8-sig`. H3_RESOLUTION=7. Sem fuzzy não-determinístico (que quebre o CI).
- Nenhum falso-positivo: exigir concordância cidade+UF no match fuzzy; auditar amostra dos pares aceitos.
- Não-casados marcados (`rotulo_casado=False`/`hex_resolvido=False`), nunca descartados nem casados incorretamente.

## Paths prováveis do ciclo (commit por path — NUNCA git add -A; CLAUDE.md NÃO entra)
- analysis/build_validation_dataset.py (melhoria da etapa de match EngCorpo)
- tests/unit/test_validation_dataset.py (casos novos de match EngCorpo)
- data/analysis/dataset_validacao.parquet · data/analysis/relatorio_auditoria_rotulo.md (regerados — gitignored)
- tasks/current_task.md · tasks/backlog.md · tasks/completed.md
- context/handoff.md · context/handoff/

## Contexto de abertura
- Branch isolado: `ciclo/BLK-SCORE-01a`, criado a partir de `main` (HEAD 1721716, BLK-SCORE-01 já mergeado).
- Worktree pré-sujo (NÃO commitar neste ciclo): `M CLAUDE.md`. Commit SÓ por path; nunca `git add -A`.
- Criticidade Alta ⇒ gate de revisão humana APÓS o Planner, ANTES do Builder.
