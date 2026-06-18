@echo off
setlocal EnableExtensions
title Agent Workflow Backend

set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%agent-workflow\backend"

if "%AGENT_WORKFLOW_HOST%"=="" set "AGENT_WORKFLOW_HOST=127.0.0.1"
if "%AGENT_WORKFLOW_PORT%"=="" set "AGENT_WORKFLOW_PORT=8000"

echo.
echo ==========================================
echo  Agent Workflow Backend
echo ==========================================
echo Root:    %ROOT_DIR%
echo Backend: %BACKEND_DIR%
echo Host:    %AGENT_WORKFLOW_HOST%
echo Port:    %AGENT_WORKFLOW_PORT%
echo.

if not exist "%BACKEND_DIR%\app\main.py" (
  echo [ERROR] Backend entrypoint not found:
  echo         %BACKEND_DIR%\app\main.py
  echo.
  pause
  exit /b 1
)

cd /d "%BACKEND_DIR%"
if errorlevel 1 (
  echo [ERROR] Cannot enter backend directory:
  echo         %BACKEND_DIR%
  echo.
  pause
  exit /b 1
)

if not exist "logs" mkdir "logs"
set "LOG_FILE=%CD%\logs\start.log"
echo [%DATE% %TIME%] start.bat launched > "%LOG_FILE%"

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
)

echo Checking Python...
%PYTHON_EXE% --version
if errorlevel 1 (
  echo.
  echo [ERROR] Python is not available. Install Python 3.11+ or create .venv.
  echo [%DATE% %TIME%] Python check failed >> "%LOG_FILE%"
  echo.
  pause
  exit /b 1
)

echo.
echo Checking port %AGENT_WORKFLOW_PORT%...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$port = [int]$env:AGENT_WORKFLOW_PORT; $items = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue; if ($items) { $items | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { $p = Get-Process -Id $_ -ErrorAction SilentlyContinue; if ($p) { Write-Output ('PID {0} {1}' -f $_, $p.ProcessName) } else { Write-Output ('PID {0}' -f $_) } }; exit 2 }"
if errorlevel 2 (
  echo.
  echo [ERROR] Port %AGENT_WORKFLOW_PORT% is already in use.
  echo         The backend may already be running.
  echo         Dashboard: http://%AGENT_WORKFLOW_HOST%:%AGENT_WORKFLOW_PORT%/dashboard
  echo.
  echo To use a different port:
  echo   set AGENT_WORKFLOW_PORT=8001
  echo   start.bat
  echo.
  echo [%DATE% %TIME%] Port %AGENT_WORKFLOW_PORT% is already in use >> "%LOG_FILE%"
  pause
  exit /b 2
)

echo.
echo Checking backend dependencies...
%PYTHON_EXE% -c "import fastapi, sqlalchemy, uvicorn" >nul 2>nul
if errorlevel 1 (
  echo Installing backend dependencies...
  echo [%DATE% %TIME%] Installing dependencies >> "%LOG_FILE%"
  %PYTHON_EXE% -m pip install -e ".[dev]"
  if errorlevel 1 (
    echo.
    echo [ERROR] Dependency installation failed.
    echo         See: %LOG_FILE%
    echo [%DATE% %TIME%] Dependency installation failed >> "%LOG_FILE%"
    echo.
    pause
    exit /b 1
  )
)

echo.
echo Starting Agent Workflow Backend...
echo Dashboard: http://%AGENT_WORKFLOW_HOST%:%AGENT_WORKFLOW_PORT%/dashboard
echo Press Ctrl+C to stop the server.
echo [%DATE% %TIME%] Starting uvicorn >> "%LOG_FILE%"
echo.

%PYTHON_EXE% -m uvicorn app.main:app --host "%AGENT_WORKFLOW_HOST%" --port "%AGENT_WORKFLOW_PORT%"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo Backend process exited with code %EXIT_CODE%.
echo [%DATE% %TIME%] Uvicorn exited with code %EXIT_CODE% >> "%LOG_FILE%"
echo.
pause
exit /b %EXIT_CODE%
