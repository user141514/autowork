@echo off
setlocal EnableExtensions
title Autowork WeChat Text Import

set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%agent-workflow\backend"

echo.
echo ==========================================
echo  Autowork WeChat Text Import
echo ==========================================
echo.
echo Paste/export WeChat chat text to a .txt/.md/.csv/.json file first.
echo This tool imports that file into the local workflow database.
echo.

set "CHAT_NAME="
set /p "CHAT_NAME=Enter chat/group name: "
if "%CHAT_NAME%"=="" (
  echo.
  echo [ERROR] Chat/group name cannot be empty.
  echo.
  pause
  exit /b 2
)

set "CHAT_FILE="
set /p "CHAT_FILE=Enter chat text file path: "
if "%CHAT_FILE%"=="" (
  echo.
  echo [ERROR] File path cannot be empty.
  echo.
  pause
  exit /b 2
)
if not exist "%CHAT_FILE%" (
  echo.
  echo [ERROR] File does not exist:
  echo         %CHAT_FILE%
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

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
)

echo.
echo Importing...
%PYTHON_EXE% scripts\import_wechat_text.py --chat "%CHAT_NAME%" --file "%CHAT_FILE%"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo Import exited with code %EXIT_CODE%.
echo.
pause
exit /b %EXIT_CODE%
