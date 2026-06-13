# Current Task

## Bloco atual

ID: BLK-EST-04
Nome: Trocar a imagem de capa do Relatorio Pontual Censitario (dashboard + API)
Status: APROVADO — deploy VPS pendente (scp, confirmação humana antes de executar)
Tipo: operação (asset de branding + deploy VPS)
Criticidade: baixa
Esteira: Block Orchestrator → Builder → fechamento
Skill atual: run-cycle (fechamento)
Próxima Skill: deploy VPS (scp manual pelo usuário)
dry_run: false

## Tiering de modelo (Passo 4) — Baixa
- Block Orchestrator: sonnet (override +1 vs haiku — precisa raciocinar sobre risco de colisão de layout + escopo do deploy VPS)
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre)

## Objetivo
Trocar a capa do PDF do Relatorio Pontual Censitario (asset `data/ultra/relatorio_capa_bg.png`,
gitignored, lido em runtime do volume) pela nova versão já adicionada por Felipe (1360×763, ~16:9),
nos DOIS caminhos (dashboard + API). Garantir título/subtítulo legíveis sobre ela (zona limpa
inferior-direita do `_cover_page`) e fazer o deploy via scp ao VPS `/opt/motor-expansao/data/ultra/`
(uma cópia atualiza streamlit + api). READ-ONLY sobre o M1.

## Branch do ciclo
ciclo/BLK-EST-04 (a partir de main @ 328cefb)

## Paths do ciclo (commit por path no fechamento)
- src/motor_expansao/dashboard/censo_report.py (SÓ se o render exigir ajuste de layout)
- tasks/current_task.md
- tasks/completed.md
- tasks/backlog.md (stub via helper no 6.0)
- context/handoff.md + context/handoff/
- NOTA: `data/ultra/relatorio_capa_bg.png` é gitignored — NÃO entra em commit; vai ao VPS por scp.

## Fora de escopo (invioláveis)
- score_priorizacao/hex_score_estrutural/pesos/artefatos oficiais do M1 (READ-ONLY)
- método de interseção setor_censitario_intersecao_area_1p5km / raio 1.5 km
- estrutura de 7 páginas/ordem/`/Count`/grid 4x2/`set_compression(False)` do PDF (INTOCADOS)
- PII: asset segue gitignored; `image24.png` nunca embutido
- GUARDRAIL VPS §6: cada comando no servidor com confirmação humana (usuário pré-autorizou o deploy desta tarefa)

## Worktree pré-sujo (não tocar)
- data/raw/ibge/malha_brasil.geojson (D) — não relacionado
- data/raw/ibge/malha_uf_brasil.geojson (D) — não relacionado
