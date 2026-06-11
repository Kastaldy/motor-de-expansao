# Current Task

## Bloco atual

ID: BLK-EST-01
Nome: Marca d'água + nome do solicitante nos PDFs
Status: aprovado
Tipo: feature
Criticidade: alta
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA] → Builder → QA
Skill atual: QA (concluído — APROVADO 2026-06-11)
Próxima Skill: Fechamento manual (ciclo pode ser fechado)
dry_run: false

## Builder concluído (2026-06-11)
- Marca d'água diagonal "Ultra Academia [| {solicitante}]" em TODAS as 7 páginas do PDF, via novo
  parâmetro `solicitante: str | None = None` em cascata nas 3 funções de `censo_report.py`.
- `pages.py` INTOCADO (D1 = contrato mínimo). Compressão OFF preservada; anti-PII OK.
- Validações (fallback serial por quebra de xdist no host): pytest impactado+integração 192 passed,
  0 failed; import streamlit_app ok; ruff All checks passed; mypy Success. READ-ONLY M1 confirmado.
- Detalhes em context/handoff.md + snapshot context/handoff/20260611-120806-builder.md.

## Gate humano (REVISÃO HUMANA — Alta) — APROVADO por Felipe/usuário em 2026-06-11
- D1 = contrato mínimo `solicitante: str | None = None` com fallback seguro (None → só "Ultra Academia"). pages.py intocado.
- D2 = opção (b): marca d'água diagonal em TODAS as 7 páginas, texto "Ultra Academia | {solicitante}".
- Liberação explícita para o Builder executar o plano do Planner com essas duas escolhas.

## Objetivo
Todo PDF gerado pelo Relatório Pontual Censitário carrega marca d'água + nome do
solicitante de forma legível e não removível trivialmente, para rastreabilidade (base LGPD),
sem versionar PII e preservando compressão de stream OFF (auditabilidade anti-PII). READ-ONLY M1.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-EST-01 (a partir de main @ 5bb790c)

## Escopo permitido (do backlog)
- src/motor_expansao/dashboard/censo_report.py (composição do PDF sobre fpdf2)
- passar o identificador do solicitante pelo caminho de geração
- teste(s) correspondente(s)

## Fora de escopo (invioláveis)
- versionar PDFs reais (PII)
- embutir o cartão de contato image24.png (anti-PII, §4)
- score/artefatos M1 (READ-ONLY)
- dependência de API ao vivo

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md
