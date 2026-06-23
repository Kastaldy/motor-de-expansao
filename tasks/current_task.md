# Current Task

## Bloco atual

ID: BLK-DIM-22
Nome: UI: exportar simulador de viabilidade como Excel
Status: aprovado
Tipo: novo entregável UI (READ-ONLY sobre M1)
Criticidade: média
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA] → Builder → QA
Skill atual: QA
Próxima Skill: nenhuma (loop encerrado)

## Objetivo
Adicionar botão `st.download_button` em `pages.py` que gera, em memória, um `.xlsx` com 4 abas (Resumo, DRE, Sensibilidade, Curva) com visual Ultra (turquesa/branco/cinza-escuro), usando `openpyxl` (já dep). Novo módulo `src/motor_expansao/dimensionamento/excel_export.py` com função `gerar_excel_viabilidade(result, *, nome_ponto) -> bytes`. Sem escrita em disco no servidor (BytesIO), sem PII, sem tocar M1.

## Dependências confirmadas
- BLK-DIM-19 (concluído 2026-06-22): payback/flag corretos
- BLK-DIM-20 (concluído 2026-06-22): parâmetros de fluxo de caixa
- BLK-DIM-21 (concluído 2026-06-22): `gerar_serie_mensal()` disponível em `simulador.py`

## Modo
LOOP AUTÔNOMO — sem gate humano (bloco loop-safe, READ-ONLY sobre M1)

## Tiering de modelo (Média)
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus (sempre)

## Handoff disponível
`context/handoff.md` — gerado pelo Block Orchestrator em 2026-06-22-153850
