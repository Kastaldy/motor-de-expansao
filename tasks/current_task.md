# Current Task

## Bloco atual

ID: BLK-RELPON-04
Nome: Relatório Pontual em lote (fila de endereços pesquisados)
Status: CICLO FECHADO — APROVADO. A ressalva do QA foi RESOLVIDA: após reboot da máquina o
  bloqueio Smart App Control do DLL do h3 sumiu; a suíte rodou de verdade. Housekeeping OK +
  commit por path feito; merge = humano (6.b).
Tipo: feature (UI)
Criticidade: média
Esteira: Block Orchestrator → Planner → [confirmação humana — produto: D1/D2/D3] → Builder → QA (concluído)
Skill atual: Fechamento (orquestrador) CONCLUÍDO
Skill anterior: QA (concluído em 2026-07-06)
Próxima Skill: revisão + merge da branch ciclo/BLK-RELPON-04 pelo humano (6.b). Sem dry-run (não tocou orquestração).

## Resultado da suíte (pós-reboot, execução REAL — 2026-07-06)
- `import h3` OK (v4.5.0) e `import streamlit_app` OK após reinício da máquina (Smart App Control
  deixou de bloquear o DLL nativo do h3).
- Focado: `pytest -q tests/integration/test_streamlit_app.py` → **230 passed**.
- Suíte cheia: `pytest -q` → **1337 passed, 1 skipped, 1 failed**.
- A ÚNICA falha (`tests/unit/test_score_retencao_territorial.py::test_run_readonly_m1_por_mtime`) é
  PRÉ-EXISTENTE e ALHEIA a este bloco: `FileNotFoundError data/staging/unidade_territorio_retencao.parquet`
  (dado gitignored ausente da camada M2/BLK-LTV-04). Confirmado por `git stash` dos 3 arquivos do ciclo:
  a falha PERSISTE em árvore limpa → não é regressão do BLK-RELPON-04. NO-BYPASS honrado.
- housekeeping: bloco movido para completed.md (stub no backlog) + `--check` OK; test_housekeeping_helper 10 passed.

## Resultado do QA (2026-07-06)
- VEREDITO: APROVADO COM RESSALVA. ruff/mypy/py_compile limpos; READ-ONLY M1 confirmado (git diff
  vazio em censo_*/pipelines/config.py; 4 artefatos oficiais intactos); anti-PII OK (só session_state,
  sem persistência em disco/log); D1/D2/D3 = Opção A implementados; CSS 260px + isolamento de keys OK;
  12 testes novos bem-formados por INSPEÇÃO (não executados aqui).
- RESSALVA: `pytest`/`import streamlit_app` bloqueados por Smart App Control (DLL do h3), reproduzido
  identicamente ao Builder (incl. `import h3` isolado). NO-BYPASS honrado — sem verde fabricado.
- housekeeping --check: falha esperada pré-move ("stub ausente"), helper reconhece o bloco; move é do
  orquestrador no fechamento.

## Bloqueio de ambiente sinalizado pelo Builder (ler antes de rodar a suite)
`pytest`/`import streamlit_app` NÃO puderam ser executados de fato nesta máquina: uma política
de Controle de Aplicativo (WDAC/Smart App Control) em nível de SO está bloqueando o carregamento
do binário nativo do pacote `h3` (evidência: `import h3` isolado já falha; log de eventos do
Windows mostra o MESMO tipo de bloqueio atingindo um DLL de terceiros alheio ao projeto nos
mesmos minutos da sessão — não é causado por este bloco). `ruff`/`mypy`/`py_compile` rodaram
limpos nos arquivos tocados. O QA deve tentar `pytest -n auto` no seu próprio ambiente; se o
mesmo bloqueio ocorrer, escalar para o usuário antes de fechar o ciclo (NO-BYPASS).

## Gate humano (produto) — CONFIRMADO em 2026-07-06
- D1 = N botões rotulados por endereço (Opção A, recomendada). Sem `.zip`.
- D2 = botão explícito "+ Adicionar à fila" (Opção A, recomendada).
- D3 = fila única compartilhada entre topo e inferior (Opção A, recomendada).
Plano do Planner segue sem alterações.

## Objetivo
Permitir gerar Relatórios Pontuais em lote acumulando os endereços pesquisados numa fila de
`session_state`, com geração N-a-N (progresso i/N) e dois modos de download (lote + só o último),
nos dois pontos da página (topo e inferior), READ-ONLY sobre o M1.

## Tiering de modelo (Passo 4) — Média
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-RELPON-04 (criada a partir de main @ HEAD 1466040).

## Paths do ciclo (commit por path — NUNCA git add -A)
- src/motor_expansao/dashboard/pages.py (fila, botões de lote, CSS width)
- tests/ (testes da fila/lote de UI)
- tasks/current_task.md, tasks/completed.md, tasks/backlog.md (fechamento)
- context/handoff.md, context/handoff/

## Guardrails
- §5 READ-ONLY M1: zero recálculo de score/pesos/carteira/plano/artefatos oficiais.
- Núcleo `censo_*` (`setor_censitario_intersecao_area_1p5km`, raio 1,5 km, páginas do PDF, marca d'água
  anti-PII, `set_compression(False)`) — só CONSUMIR, não alterar.
- Anti-PII: fila de endereços vive só em `session_state` (efêmera); NUNCA persistida em disco/log.
- Reusar `gerar_payloads_relatorio_pontual_para_pin` e `render_coord_search_sidebar` sem alterar núcleo.
- Largura de botão via regra CSS 260px do `inject_styles` (adicionar novas `st-key`), NÃO `use_container_width`.
- Sem dependência de rede nova (§2; geocoding/tiles já cobertos por DEC-010/DEC-004).

## Worktree pré-sujo
- ` M tasks/backlog.md` já existia antes do ciclo; commitar apenas paths do ciclo por path.
