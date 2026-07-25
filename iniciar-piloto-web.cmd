@echo off
setlocal enabledelayedexpansion
title Piloto Web - Motor de Expansao Ultra

rem ===========================================================================
rem  Sobe o piloto web completo em um clique.
rem
rem    front-end  ->  http://localhost:5000   (Vite + React + deck.gl)
rem    back-end   ->  http://127.0.0.1:8899   (FastAPI, relatorios em PDF)
rem
rem  Os parquets sao gitignored e vivem no checkout da main; MOTOR_DATA_DIR
rem  aponta para la. Ajuste a linha abaixo se o seu caminho for outro.
rem ===========================================================================

cd /d "%~dp0"

rem Os parquets sao gitignored e vivem no checkout da main. Este script pode estar
rem rodando de um WORKTREE (.claude\worktrees\<nome>), entao subimos ate achar
rem o data\outputs\hexagonos_dashboard_enriquecido. NAO cravar caminho de usuario:
rem o default antigo apontava para "C:\Users\Felipe Silva\Downloads..." e nao
rem existia na maquina de quem rodava — foi a primeira coisa a falhar ao abrir o repo.
if not defined MOTOR_DATA_DIR (
  set "MOTOR_DATA_DIR=%~dp0data"
  if not exist "%~dp0data\outputs\hexagonos_dashboard_enriquecido" (
    rem worktree: .claude\worktrees\<nome>\  ->  sobe 3 niveis ate a raiz do repo
    for %%I in ("%~dp0..\..\..") do set "MOTOR_DATA_DIR=%%~fI\data"
  )
)

echo.
echo   Motor de Expansao - piloto web
echo   ------------------------------------------------------------
echo   dados : !MOTOR_DATA_DIR!
echo.

if not exist "!MOTOR_DATA_DIR!\outputs\hexagonos_dashboard_enriquecido" (
  echo   [ERRO] Base de hexagonos nao encontrada em:
  echo          !MOTOR_DATA_DIR!\outputs\hexagonos_dashboard_enriquecido
  echo.
  echo   Defina MOTOR_DATA_DIR apontando para o data\ do checkout da main
  echo   e rode de novo.
  echo.
  pause
  exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
  echo   [ERRO] python nao encontrado no PATH.
  pause
  exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
  echo   [ERRO] npm nao encontrado no PATH. Instale o Node.js.
  pause
  exit /b 1
)

if not exist "web\node_modules" (
  echo   Primeira execucao: instalando dependencias do front...
  pushd web
  call npm install
  popd
  echo.
)

rem --reload: sem ele o backend serve BYTECODE VELHO depois de qualquer mudanca em
rem Python, e o sintoma aparece como erro de HTTP em vez de 'codigo desatualizado'.
rem Aconteceu duas vezes em 2026-07-24/25: HTTP 405 no botao do Excel (a rota nova nao
rem existia no processo em memoria, entao o POST caia no StaticFiles, que so aceita
rem GET) e depois a planilha saindo com a formula ANTIGA da folha. O front (Vite) ja
rem recarrega sozinho; o Python nao recarregava.
echo   Subindo o back-end na porta 8899...
start "Piloto Web - backend" cmd /k "cd /d "%~dp0web\server" && set "MOTOR_DATA_DIR=!MOTOR_DATA_DIR!" && python -m uvicorn app:app --host 127.0.0.1 --port 8899 --reload --reload-dir . --reload-dir ..\..\src\motor_expansao"

echo   Subindo o front-end na porta 5000...
start "Piloto Web - frontend" cmd /k "cd /d "%~dp0web" && npm run dev"

echo.
echo   Abrindo http://localhost:5000 ...
echo   (a primeira leitura de uma UF carrega a particao inteira e demora)
echo.

rem Da um tempo para o Vite ligar antes de abrir o browser.
timeout /t 6 /nobreak >nul
start "" "http://localhost:5000"

echo   Pronto. Feche as duas janelas abertas para encerrar o piloto.
echo.
pause
