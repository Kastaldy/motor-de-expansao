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

if not defined MOTOR_DATA_DIR (
  set "MOTOR_DATA_DIR=C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\data"
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

echo   Subindo o back-end na porta 8899...
start "Piloto Web - backend" cmd /k "cd /d "%~dp0web\server" && set "MOTOR_DATA_DIR=!MOTOR_DATA_DIR!" && python -m uvicorn app:app --host 127.0.0.1 --port 8899"

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
