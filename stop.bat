@echo off
chcp 65001 >nul
setlocal

REM ===========================================================================
REM Stock AI Platform - one-click stopper (Windows)
REM ===========================================================================
REM Kills any process listening on port 8000 (backend) and 5173 (frontend).
REM Safe to run anytime; does nothing if those ports are not bound.
REM ===========================================================================

echo.
echo Stopping Stock AI Platform...
echo.

set "FOUND_ANY=0"

REM ---- Backend (uvicorn) on :8000 -------------------------------------------
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
    echo Killing backend pid %%a (port 8000)...
    taskkill /F /PID %%a >nul 2>&1
    set "FOUND_ANY=1"
)

REM ---- Frontend (vite) on :5173 ----------------------------------------------
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173.*LISTENING"') do (
    echo Killing frontend pid %%a (port 5173)...
    taskkill /F /PID %%a >nul 2>&1
    set "FOUND_ANY=1"
)

if "%FOUND_ANY%"=="0" (
    echo Nothing was running on :8000 or :5173.
) else (
    echo Done.
)

echo.
pause
