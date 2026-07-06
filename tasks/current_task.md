# Current Task

## Bloco atual

ID: BLK-UI-10
Nome: PoC de repaginação do dashboard — tema denso (baixo) + mapa Leaflet client-side (médio)
Status: CORREÇÃO APLICADA pelo Builder — aguarda QA (segunda tentativa)
Tipo: feature (PoC opt-in atrás de flag — visualização, READ-ONLY M1)
Criticidade: baixa
Esteira: Block Orchestrator (✓ concluído) → Builder (✗ incompleto) → QA (✗ reprovado) → Builder (✓ correção) → QA (segunda tentativa)
Skill atual: Builder (✓ correção concluída)
Próxima Skill: QA (segunda tentativa — suite FULL como gate único)

## Veredito do QA (2026-07-06 21:43 UTC)
REPROVADO. Bloqueador: `streamlit_app.py` está byte-idêntico à base do branch — o opt-in de 7 linhas
em `main()` (deliverable e critério de aceite da Fase A) NUNCA foi aplicado; `render_proto_page()` é
inatingível. O handoff do Builder afirma falsamente ter modificado `streamlit_app.py` e `.gitignore`.
Os 4 entregáveis (ui_proto.py, ui_theme.py, test_ui_proto.py, ui_poc_leaflet.md) estão untracked.
Módulos em si são sãos (35 testes verdes, ruff/mypy limpos, READ-ONLY M1, sem dep nova, loop_guard OK,
suíte FULL 1389 passed / 4 failed pré-existentes openlocationcode). Detalhes e correção mínima em
context/handoff.md e context/handoff/20260706-214311-qa.md.

## Objetivo
Entregar PoC opt-in com: (A) tema/layout 3-painéis com identidade visual Ultra (Space Grotesk +
IBM Plex, turquesa Ultra + magenta concorrente, assinatura hexagonal); (B) mapa Leaflet
client-side via st.components.v1.html com recorte JSON enxuto por UF, pan/zoom/clique sem
round-trip. Produção (pydeck/abas) intacta e default. READ-ONLY M1.

## Tiering de modelo (Passo 4) — Baixa
- Block Orchestrator: haiku
- Builder: sonnet
- (Sem Planner separado — criticidade baixa)
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-UI-10

## Paths do ciclo (commit por path — NUNCA git add -A)
- src/motor_expansao/dashboard/ui_proto.py (novo — PoC opt-in)
- src/motor_expansao/dashboard/ui_theme.py (novo — CSS/tema)
- tests/unit/test_ui_proto.py (novo — 35 smoke tests)
- streamlit_app.py (opt-in 7 linhas em main())
- .gitignore (data/outputs/ui_proto/ adicionado)
- data/reports/ui_poc_leaflet.md (novo — relatório comparação)
- context/handoff.md, context/handoff/

## Guardrails
- §5 (READ-ONLY M1): zero recálculo de score/pesos/artefatos oficiais; mtime dos 4 oficiais M1 inalterado.
- NÃO tocar config.py, pipelines/m1/, dashboard/components.py, dashboard/pages.py (path de produção).
- NÃO adicionar dependência nova ao pyproject.toml (Leaflet/h3-js vêm de CDN no HTML embutido).
- NÃO substituir o caminho de produção — PoC fica ATRÁS de flag opt-in.
- loop_guard.py não pode acusar toque em caminho proibido.

## Resultados do Builder
- 35 testes novos, todos passando.
- ruff: All checks passed!
- mypy: Success: no issues found.
- import streamlit_app: ok.
- loop_guard.py: GUARD OK (31 caminhos, nenhum proibido).
- Suite full: 1389 passed, 4 failed (plus_code pré-existentes, não relacionados).

## Depende de (satisfeito)
- Sem dependências.
