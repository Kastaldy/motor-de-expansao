# Current Task

## Bloco atual

ID: BLK-DIM-02R
Nome: Huff com validação real (OSM, saturação, sem vazamento)
Status: aprovado (APROVADO)
Tipo: modelagem estatística (calibração gravitacional; READ-ONLY sobre M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [no loop: guard automático] → Builder → QA
Skill atual: QA (concluído)
Próxima Skill: Fechamento (Passo 6.0)

## Veredito QA (2026-06-15)
APROVADO. Suíte FULL 919 passed, 4 skipped; ruff/mypy limpos; import streamlit_app ok.
Anti-vazamento confirmado (share_huff sem alvo na assinatura; LOO exclui a unidade-alvo;
sem `where(isnan,y,...)` no código). Correlação LOO NEGATIVA (-0.254, IC [-0.357,-0.143]):
"GO" técnico gerado por gate simétrico |corr|>=0.15 conforme plano aprovado e backlog (sem
regra de direção positiva); direção anti-intuitiva está explicitada e qualificada na §3/§5 do
relatório (baseline empatado -0.244, AUC 0.383). Ressalva média: não é endosso da geometria Huff.

## Objetivo
Calibrar o modelo gravitacional de Huff com concorrência OSM real, remover o fallback
previsor=alvo (vazamento latente do spike), e validar LOO se o β gravitacional é
distinguível de zero. READ-ONLY sobre o M1.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/loop-20260615-124342 (branch autônomo do loop)

## Contexto de antecedente
- BLK-DIM-08 completado (2026-06-15): NO-GO honesto da tese residual (AUC 0.48, IC [0.42, 0.54])
- BLK-DIM-07: raio_variavel_aceito_para_estabilidade (CV penetração 1.15→0.47)
- Gate de sequência: BLK-DIM-08 agora em completed.md → BLK-DIM-02R elegível

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- PRD.md, CLAUDE.md, README.md, .env.example, .github/workflows/ci.yml e outros arquivos do worktree
