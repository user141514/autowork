@echo off
setlocal EnableExtensions

title WeChat Requirement Review Workbench

set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%agent-workflow\backend"
set "AGENT_WORKFLOW_START_PAGE=review-workbench?view=wechat-directory"
if "%AGENT_WORKFLOW_OPEN_BROWSER%"=="" set "AGENT_WORKFLOW_OPEN_BROWSER=true"

rem This launcher is intentionally conservative:
rem - it opens the review workbench;
rem - it does not enable real WeChat sending;
rem - it does not enable personal WeChat UIAutomation polling;
rem - it can read already imported messages and already-readable local SQLite copies through the backend UI.

if "%AGENT_WORKFLOW_PERSONAL_WECHAT_ENABLED%"=="" set "AGENT_WORKFLOW_PERSONAL_WECHAT_ENABLED=false"
if "%AGENT_WORKFLOW_WECHAT_SEND_ENABLED%"=="" set "AGENT_WORKFLOW_WECHAT_SEND_ENABLED=false"

echo.
echo ==========================================
echo  WeChat Requirement Review Workbench
echo ==========================================
echo Root:    %ROOT_DIR%
echo Backend: %BACKEND_DIR%
echo Page:    /%AGENT_WORKFLOW_START_PAGE%
echo Personal WeChat enabled: %AGENT_WORKFLOW_PERSONAL_WECHAT_ENABLED%
echo WeChat send enabled:     %AGENT_WORKFLOW_WECHAT_SEND_ENABLED%
echo Directory mode:          strict display-name search, latest-message-first sorting
echo.

if not exist "%ROOT_DIR%start_review_workbench.bat" (
  echo [ERROR] Missing base launcher:
  echo         %ROOT_DIR%start_review_workbench.bat
  echo.
  pause
  exit /b 1
)

call "%ROOT_DIR%start_review_workbench.bat" %*
exit /b %ERRORLEVEL%
