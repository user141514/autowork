@echo off
setlocal EnableExtensions
title Autowork WeChat DB Poller

set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%agent-workflow\backend"

echo.
echo ==========================================
echo  Autowork WeChat Database Poller
echo ==========================================
echo.
echo Reads a readable SQLite MSG.db copy.
echo It does not decrypt WeChat databases or extract keys.
echo Only selected StrTalker values are imported.
echo.

if not exist "%BACKEND_DIR%\scripts\poll_wechat_database.py" (
  echo [ERROR] Database poller script not found:
  echo         %BACKEND_DIR%\scripts\poll_wechat_database.py
  echo.
  pause
  exit /b 1
)

set "WECHAT_DB_PATH="
set /p "WECHAT_DB_PATH=Enter readable MSG.db path: "
if "%WECHAT_DB_PATH%"=="" (
  echo.
  echo [ERROR] MSG.db path cannot be empty.
  echo.
  pause
  exit /b 2
)
if not exist "%WECHAT_DB_PATH%" (
  echo.
  echo [ERROR] MSG.db path does not exist:
  echo         %WECHAT_DB_PATH%
  echo.
  pause
  exit /b 2
)

set "WECHAT_TALKERS="
set /p "WECHAT_TALKERS=Enter StrTalker or fuzzy fragment(s), comma-separated: "
if "%WECHAT_TALKERS%"=="" (
  echo.
  echo [ERROR] StrTalker input cannot be empty.
  echo.
  pause
  exit /b 2
)

set "POLL_SINCE="
set /p "POLL_SINCE=Start time, blank means now (example 2026-06-19 10:30): "
if "%POLL_SINCE%"=="" (
  for /f "usebackq delims=" %%T in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz'"`) do set "POLL_SINCE=%%T"
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
set "LOG_FILE=%CD%\logs\wechat-db-poller-start.log"
echo [%DATE% %TIME%] start_wechat_db_poller.bat launched > "%LOG_FILE%"

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
  %PYTHON_EXE% -m pip install -e ".[dev]" >> "%LOG_FILE%" 2>&1
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
echo Starting database monitor:
echo   DB: %WECHAT_DB_PATH%
echo   Talkers/fragments: %WECHAT_TALKERS%
echo   Since: %POLL_SINCE%
echo   Prompt drafts: %CD%\.agent-work\prompts
echo.
echo If the DB is encrypted, this script will stop with WECHAT_DATABASE_NOT_READABLE.
echo Press Ctrl+C to stop.
echo [%DATE% %TIME%] Starting DB poller db=%WECHAT_DB_PATH% talkers=%WECHAT_TALKERS% since=%POLL_SINCE% >> "%LOG_FILE%"
echo.

%PYTHON_EXE% scripts\poll_wechat_database.py --db-path "%WECHAT_DB_PATH%" --talkers "%WECHAT_TALKERS%" --resolve-talkers --interval 3 --since "%POLL_SINCE%" --show-new --write-agent-prompts ".agent-work\prompts"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo WeChat database poller exited with code %EXIT_CODE%.
echo [%DATE% %TIME%] DB poller exited with code %EXIT_CODE% >> "%LOG_FILE%"
echo.
pause
exit /b %EXIT_CODE%
