# Current Task

## Bloco atual

ID: BLK-EST-05
Nome: PDF "Apresentação Clássica Ultra" (template GeoFusion) do Relatório Pontual Censitário
Status: aprovado (QA APROVADO em 2026-06-15; suite full serial 891 passed, 1 skipped)
Tipo: feature (variante de render PDF; READ-ONLY sobre M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [gate humano / revisão visual Felipe+Vini] → Builder → QA
Skill atual: QA/Quality Analyzer (auditoria concluída — APROVADO)
Próxima Skill: Fechamento manual (orquestrador: housekeeping BLK-EST-05 + commit por path; merge humano)
dry_run: false

## Objetivo
Implementar em produção a variante "Apresentação Clássica Ultra" do PDF do Relatório Pontual
Censitário (estrutura/dados do motor novo + estética GeoFusion antiga), como variante em
`censo_report.py`, sem alterar o template recente e sem tocar o M1.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus (sempre)

## Branch do ciclo
ciclo/BLK-EST-05 (a partir do HEAD atual = 10eb641, que contém o bloco BLK-EST-05 no backlog;
BLK-FIX-13 ainda não mergeado em main — merge pelo humano pendente)

## Gate humano
Após o Planner: PARAR e apresentar o plano técnico + gate visual (Felipe+Vini) antes do Builder.

## Paths pré-sujos / alheios que ACOMPANHAM o working tree (NÃO commitar)
- data/outputs/setores_censitarios_2022_geo/_metadata.json (M) — alheio
- data/reports/relatorio_pontual_censitario_base_geo.md (M) — alheio
- data/outputs/SIMULACAO_relatorio_caiubi_classico.pdf (untracked) — simulação descartável; NÃO commitar

## Fora de escopo (invioláveis)
- score/pesos/artefatos M1 (READ-ONLY; DEC-001)
- método de interseção e raio 1,5 km (INTOCADOS)
- alterar o template recente (comportamento preservado byte-a-byte sem o param)
- versionar PDF/PII real; dependência de API ao vivo no dashboard; selo GO/NO-GO
