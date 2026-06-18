@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%agent-workflow\backend"

if not exist "%BACKEND_DIR%\app\main.py" (
  echo Backend entrypoint not found: %BACKEND_DIR%\app\main.py
  exit /b 1
)

cd /d "%BACKEND_DIR%"

if not exist "logs" mkdir "logs"

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
)

if "%AGENT_WORKFLOW_HOST%"=="" set "AGENT_WORKFLOW_HOST=127.0.0.1"
if "%AGENT_WORKFLOW_PORT%"=="" set "AGENT_WORKFLOW_PORT=8000"

%PYTHON_EXE% -c "import fastapi, sqlalchemy, uvicorn" >nul 2>nul
if errorlevel 1 (
  echo Installing backend dependencies...
  %PYTHON_EXE% -m pip install -e ".[dev]"
  if errorlevel 1 exit /b 1
)

echo Starting Agent Workflow Backend
echo Dashboard: http://%AGENT_WORKFLOW_HOST%:%AGENT_WORKFLOW_PORT%/dashboard
%PYTHON_EXE% -m uvicorn app.main:app --host "%AGENT_WORKFLOW_HOST%" --port "%AGENT_WORKFLOW_PORT%"
