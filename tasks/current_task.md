# Current Task

## Bloco atual

ID: BLK-DIM-20
Nome: UI: parâmetros de fluxo de caixa editáveis (capex parcelado — equipamentos e tecnologia)
Status: aguardando QA
Tipo: enriquecimento do simulador financeiro (READ-ONLY sobre M1)
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA
Skill atual: Builder
Próxima Skill: QA

## Objetivo
Adicionar três parâmetros de financiamento de capex (`capex_financiado_pct`, `prazo_financiamento_meses`, `juros_financiamento_am`) em `viabilidade()` (`simulador.py`), calcular PMT mensal e subtrair do FCF no loop de payback (sem afetar EBITDA), e expor os novos campos no expander "Parametros avancados" do dashboard (`pages.py`).

## Modo
LOOP AUTÔNOMO — sem gate humano (bloco loop-safe, READ-ONLY sobre M1)

## Tiering de modelo (Média)
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus (sempre)

## Handoff disponível
`context/handoff.md` — gerado pelo Block Orchestrator em 2026-06-22 15:02:29
