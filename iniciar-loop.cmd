@echo off
REM ============================================================================
REM  Loop autonomo (ralph) do Motor de Expansao — lancador de 1 clique.
REM  Duplo-clique neste arquivo OU rode no terminal:  iniciar-loop.cmd
REM
REM  Pre-requisitos (uma vez):
REM    1) Docker Desktop instalado e aberto.
REM    2) No .env da raiz, a linha:  CLAUDE_CODE_OAUTH_TOKEN=<token>
REM       (gere o token com:  claude setup-token )
REM
REM  O container roda isolado, escreve SO neste repo, num branch de trabalho,
REM  e NUNCA faz merge/push/deploy. Detalhes: docs/loop_autonomo.md
REM ============================================================================
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\iniciar_loop.ps1"
