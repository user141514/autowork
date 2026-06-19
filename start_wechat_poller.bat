@echo off
setlocal EnableExtensions
title Autowork WeChat Poller

set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%agent-workflow\backend"

echo.
echo ==========================================
echo  Autowork WeChat Poller
echo ==========================================
echo.
echo Reads only the whitelisted group names you enter.
echo Only @WorkBot messages enter the task intake flow.
echo This script does not create WorkDocs, run agents, or touch Git.
echo.

if not exist "%BACKEND_DIR%\scripts\poll_wechat_messages.py" (
  echo [ERROR] Poller script not found:
  echo         %BACKEND_DIR%\scripts\poll_wechat_messages.py
  echo.
  pause
  exit /b 1
)

set "WECHAT_ROOMS="
set /p "WECHAT_ROOMS=Enter WeChat group name(s), comma-separated: "
if "%WECHAT_ROOMS%"=="" (
  echo.
  echo [ERROR] Group name cannot be empty.
  echo.
  pause
  exit /b 2
)

cd /d "%BACKEND_DIR%"
if errorlevel 1 (
  echo.
  echo [ERROR] Cannot enter backend directory:
  echo         %BACKEND_DIR%
  echo.
  pause
  exit /b 1
)

if not exist "logs" mkdir "logs"
if not exist ".agent-work\prompts" mkdir ".agent-work\prompts"
set "LOG_FILE=%CD%\logs\wechat-poller-start.log"
echo [%DATE% %TIME%] start_wechat_poller.bat launched > "%LOG_FILE%"

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
)

echo.
echo Checking Python...
%PYTHON_EXE% --version
if errorlevel 1 (
  echo.
  echo [ERROR] Python is not available. Install Python 3.11+ or create .venv in backend.
  echo [%DATE% %TIME%] Python check failed >> "%LOG_FILE%"
  echo.
  pause
  exit /b 1
)
for /f "usebackq delims=" %%P in (`%PYTHON_EXE% -c "import sys; print(sys.executable)"`) do set "PYTHON_PATH=%%P"
echo Python executable: %PYTHON_PATH%
echo [%DATE% %TIME%] Python executable: %PYTHON_PATH% >> "%LOG_FILE%"

echo.
echo Checking backend dependencies...
%PYTHON_EXE% -c "import fastapi, sqlalchemy" >nul 2>nul
if errorlevel 1 (
  echo Installing backend dependencies...
  echo [%DATE% %TIME%] Installing backend dependencies >> "%LOG_FILE%"
  %PYTHON_EXE% -m pip install -e ".[dev]"
  if errorlevel 1 (
    echo.
    echo [ERROR] Backend dependency installation failed.
    echo         Log: %LOG_FILE%
    echo [%DATE% %TIME%] Backend dependency installation failed >> "%LOG_FILE%"
    echo.
    pause
    exit /b 1
  )
)

echo.
echo Checking wxauto/wxautox...
%PYTHON_EXE% -c "import importlib.util, sys; sys.exit(0 if (importlib.util.find_spec('wxauto') or importlib.util.find_spec('wxautox')) else 1)" >nul 2>nul
if errorlevel 1 (
  echo.
  echo [ERROR] wxauto/wxautox is not installed.
  echo         This legacy UIAutomation launcher no longer installs wxautox automatically.
  echo         Prefer start_wechat_db_poller.bat for local database polling.
  echo         If you still want this legacy path, install a compatible library manually.
  echo [%DATE% %TIME%] wxauto/wxautox missing >> "%LOG_FILE%"
  echo.
  pause
  exit /b 1
)

for /f "usebackq delims=" %%T in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz'"`) do set "POLL_SINCE=%%T"

set "AGENT_WORKFLOW_PERSONAL_WECHAT_ENABLED=true"
set "AGENT_WORKFLOW_ALLOWED_WECHAT_ROOMS=%WECHAT_ROOMS%"
if "%AGENT_WORKFLOW_WECHAT_READ_LIMIT%"=="" set "AGENT_WORKFLOW_WECHAT_READ_LIMIT=50"

echo.
echo Starting monitor:
echo   Rooms: %AGENT_WORKFLOW_ALLOWED_WECHAT_ROOMS%
echo   Since: %POLL_SINCE%
echo   Read limit: %AGENT_WORKFLOW_WECHAT_READ_LIMIT%
echo   Prompt drafts: %CD%\.agent-work\prompts
echo.
echo Keep Windows WeChat Desktop open and logged in.
echo Press Ctrl+C to stop.
echo [%DATE% %TIME%] Starting poller rooms=%AGENT_WORKFLOW_ALLOWED_WECHAT_ROOMS% since=%POLL_SINCE% >> "%LOG_FILE%"
echo.

%PYTHON_EXE% scripts\poll_wechat_messages.py --resolve-rooms --interval 30 --since "%POLL_SINCE%" --show-new --write-agent-prompts ".agent-work\prompts"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo WeChat poller exited with code %EXIT_CODE%.
echo [%DATE% %TIME%] Poller exited with code %EXIT_CODE% >> "%LOG_FILE%"
echo.
pause
exit /b %EXIT_CODE%
