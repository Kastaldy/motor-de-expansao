# Current Task

## Bloco atual

ID: BLK-REV-07
Nome: Avaliação de fundação — Streamlit vs. alternativas (matriz de decisão)
Status: APROVADO (QA) — ciclo concluído, bloco movido para completed.md
Tipo: pesquisa/análise (READ-ONLY sobre o M1; loop-safe)
Criticidade: Estratégica
Esteira: Block Orchestrator → Planner → Builder → QA (autônoma no loop)
Skill atual: QA (concluído)
Próxima Skill: Fechamento manual (sucessor de decisão = BLK-REV-12, gate humano)

## Veredito QA (2026-07-10)
APROVADO. Relatório `data/analysis/avaliacao_stack.md` (gitignored) entregue no escopo:
matriz 4×7 + espectro incremental→cirúrgico→rebuild + recomendação preliminar que difere a
decisão ao REV-12. READ-ONLY M1 confirmado (loop_guard GUARD OK; diff M1/config canônico vazio;
zero código de produção alterado). Suíte full: 1524 passed, 4 skipped; as 4 falhas + 1 erro são
deps opcionais ausentes (openlocationcode/matplotlib), pré-existentes, NÃO regressão deste ciclo.
Housekeeping via helper versionado: --check EXIT=1 antes → move → EXIT=0 depois. ruff clean,
import ok, helper tests 10 passed.

## Objetivo
Pesquisa estruturada das opções de stack (a: Streamlit + otimizar / b: React SPA + FastAPI
existente / c: Dash-Panel / d: deck.gl+MapLibre + api) com critérios: performance de mapa e
troca de cor, controle de UX, preservação offline §2, reuso da api/Caddy/volumes já existentes,
velocidade de dev por perfil de time. Entrega: matriz de decisão + recomendação preliminar.
A DECISÃO final fica no REV-12. Relatório em `data/analysis/avaliacao_stack.md`. READ-ONLY M1.

## Branch do ciclo
ciclo/BLK-REV-07

## Guardrails
- §5 READ-ONLY M1; §6.1 loop-safe; data/analysis (gitignored).
- A DECISÃO de rebuild vs refactor é do REV-12 (gate humano); este bloco só pesquisa.
- Partir da topologia REAL de produção (multi-container: streamlit + api + caddy + authelia).
- NÃO re-litigar o requisito offline §2 (já esclarecido na descrição do bloco).
