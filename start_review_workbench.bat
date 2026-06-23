@echo off
setlocal EnableExtensions

title Agent Workflow Review Workbench

set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%agent-workflow\backend"

if "%AGENT_WORKFLOW_HOST%"=="" set "AGENT_WORKFLOW_HOST=127.0.0.1"
if "%AGENT_WORKFLOW_PORT%"=="" set "AGENT_WORKFLOW_PORT=8000"
if "%AGENT_WORKFLOW_PORT_SEARCH_LIMIT%"=="" set "AGENT_WORKFLOW_PORT_SEARCH_LIMIT=20"
if "%AGENT_WORKFLOW_OPEN_BROWSER%"=="" set "AGENT_WORKFLOW_OPEN_BROWSER=true"
if "%AGENT_WORKFLOW_START_PAGE%"=="" set "AGENT_WORKFLOW_START_PAGE=review-workbench"

echo.
echo ==========================================
echo  Agent Workflow Review Workbench
echo ==========================================
echo Root:    %ROOT_DIR%
echo Backend: %BACKEND_DIR%
echo Host:    %AGENT_WORKFLOW_HOST%
echo Port:    %AGENT_WORKFLOW_PORT% ^(auto-search limit: %AGENT_WORKFLOW_PORT_SEARCH_LIMIT%^)
echo Page:    /%AGENT_WORKFLOW_START_PAGE%
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
set "LOG_FILE=%CD%\logs\start_review_workbench.log"
echo [%DATE% %TIME%] start_review_workbench.bat launched > "%LOG_FILE%"

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

if /i "%~1"=="--check" (
  echo.
  echo Check mode passed. Server was not started.
  echo [%DATE% %TIME%] Check mode passed >> "%LOG_FILE%"
  exit /b 0
)

echo.
echo Searching for an available port...
set "START_PORT=%AGENT_WORKFLOW_PORT%"
set "SELECTED_PORT="
for /f "usebackq tokens=1,2 delims==" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$start = [int]$env:AGENT_WORKFLOW_PORT; $limit = [Math]::Max(1, [int]$env:AGENT_WORKFLOW_PORT_SEARCH_LIMIT); $hostName = $env:AGENT_WORKFLOW_HOST; if ([string]::IsNullOrWhiteSpace($hostName) -or $hostName -eq 'localhost') { $address = [Net.IPAddress]::Parse('127.0.0.1') } elseif ($hostName -eq '0.0.0.0') { $address = [Net.IPAddress]::Any } else { $address = [Net.IPAddress]::Parse($hostName) }; for ($i = 0; $i -lt $limit; $i++) { $port = $start + $i; $listener = $null; try { $listener = [Net.Sockets.TcpListener]::new($address, $port); $listener.Start(); $listener.Stop(); Write-Output ('SELECTED_PORT={0}' -f $port); exit 0 } catch { if ($listener) { try { $listener.Stop() } catch {} }; Write-Output ('BUSY_PORT={0}' -f $port) } }; exit 3"`) do (
  if "%%A"=="BUSY_PORT" echo Port %%B is busy
  if "%%A"=="SELECTED_PORT" set "SELECTED_PORT=%%B"
)
if not defined SELECTED_PORT (
  echo.
  echo [ERROR] No available port found.
  echo         Start port: %START_PORT%
  echo         Search limit: %AGENT_WORKFLOW_PORT_SEARCH_LIMIT%
  echo [%DATE% %TIME%] No available port found from %START_PORT% limit %AGENT_WORKFLOW_PORT_SEARCH_LIMIT% >> "%LOG_FILE%"
  echo.
  pause
  exit /b 3
)
set "AGENT_WORKFLOW_PORT=%SELECTED_PORT%"
set "WORKBENCH_URL=http://%AGENT_WORKFLOW_HOST%:%AGENT_WORKFLOW_PORT%/%AGENT_WORKFLOW_START_PAGE%"
set "DASHBOARD_URL=http://%AGENT_WORKFLOW_HOST%:%AGENT_WORKFLOW_PORT%/dashboard"

echo Selected port: %AGENT_WORKFLOW_PORT%
echo Workbench: %WORKBENCH_URL%
echo Dashboard: %DASHBOARD_URL%
echo [%DATE% %TIME%] Selected port %AGENT_WORKFLOW_PORT% >> "%LOG_FILE%"

if /i "%AGENT_WORKFLOW_OPEN_BROWSER%"=="true" (
  echo Opening browser...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds 2; Start-Process '%WORKBENCH_URL%'" >nul 2>nul
)

echo.
echo Starting backend. Press Ctrl+C to stop.
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
