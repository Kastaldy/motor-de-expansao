# Current Task

## Bloco atual

ID: BLK-API-01
Nome: Definir arquitetura e contrato da API (G1)
Status: APROVADO (QA 2026-06-10) — ciclo FECHADO pelo orquestrador (housekeeping feito: bloco em completed.md, stub no backlog; commit por path na branch ciclo/BLK-API-01); aguardando MERGE humano. NÃO dispara dry-run (ciclo não altera a orquestração).
Tipo: doc/design (contrato + ADR; zero código de produção)
Criticidade: estratégica
Esteira: Block Orchestrator → Planner → [APROVAÇÃO HUMANA — 6 decisões-chave de contrato ✓ 2026-06-10] → Builder ✓ → QA ✓ (APROVADO)
Skill atual: Fechamento (orquestrador) — concluído
Próxima Skill: Merge humano da branch ciclo/BLK-API-01; depois início do BLK-API-02 (G2)
dry_run: false

## Tiering de modelo (Passo 4) — Estratégica
- Block Orchestrator: opus
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Objetivo
Entregar um contrato de API geoespacial aprovado por Felipe (docs/api_geoespacial_contrato.md + esboço OpenAPI + ADR), suficiente para o Juan implementar G2 sem re-discussão de arquitetura, com a decomposição de BLK-API-02..0N. ZERO código de produção; READ-ONLY M1.

## Branch do ciclo
ciclo/BLK-API-01 (a partir de main @ b1a3e13)

## Worktree pré-sujo (NÃO tocar)
- D data/raw/ibge/malha_brasil.geojson
- D data/raw/ibge/malha_uf_brasil.geojson
(deleções não relacionadas; commitar SÓ paths do ciclo por path, nunca git add -A)

## Paths prováveis do ciclo (a confirmar pelo Planner)
- docs/api_geoespacial_contrato.md (novo)
- docs/api_geoespacial_openapi.yaml (novo, ou bloco no contrato)
- docs/ ADR (nova DEC estilo CLAUDE.md §8) — destino a confirmar
- tasks/backlog.md (decomposição BLK-API-02..0N) + tasks/current_task.md + tasks/completed.md
- README.md / PRD.md (ponteiro mínimo, sem implementar)
- context/handoff.md + context/handoff/

## Fora de escopo (invioláveis)
- Qualquer código de produção em src/motor_expansao/ (exceto, SE decidido no gate, pasta api/ vazia com __init__.py)
- Implementar rotas/handlers, subir container, PostGIS, integração Telegram/WhatsApp (G4)
- Recalcular/alterar M1 (score/pesos/carteira/plano/artefatos oficiais) — §5
- API ao vivo no dashboard de produção
