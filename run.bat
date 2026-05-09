@echo off
chcp 65001 >nul
setlocal

REM ===========================================================================
REM Stock AI Platform - one-click runner (Windows)
REM ===========================================================================
REM What this script does (in order):
REM   1. Copy .env.example to .env on first run.
REM   2. Verify .venv exists.
REM   3. Run Alembic migrations (creates stock_ai.db if missing).
REM   4. Seed mock data on first run.
REM   5. Install frontend dependencies on first run.
REM   6. Launch backend (uvicorn :8000) in a new window.
REM   7. Launch frontend (vite :5173) in a new window.
REM   8. Open the dashboard in your default browser.
REM
REM Stop with: stop.bat (or close the two opened windows manually).
REM ===========================================================================

cd /d "%~dp0"

echo.
echo === Stock AI Platform ===
echo.

REM ---- 1. Copy .env if missing -----------------------------------------------
if not exist ".env" (
    echo [1/7] .env not found - copying from .env.example...
    copy ".env.example" ".env" >nul
) else (
    echo [1/7] .env already exists - skipping.
)

REM ---- 2. Verify venv --------------------------------------------------------
if not exist ".venv\bin\python.exe" (
    echo.
    echo [ERROR] .venv\bin\python.exe not found.
    echo.
    echo  This project uses a uv-style venv. Create it once with:
    echo    python -m venv .venv
    echo    .venv\bin\python.exe -m pip install -e .
    echo.
    pause
    exit /b 1
)
echo [2/7] venv OK.

REM ---- 3. Alembic migration --------------------------------------------------
echo [3/7] Running Alembic migration (upgrade head)...
set "PYTHONUTF8=1"
".venv\bin\alembic.exe" upgrade head
if errorlevel 1 (
    echo.
    echo [ERROR] Alembic migration failed. See message above.
    pause
    exit /b 1
)

REM ---- 4. Seed mock data only when the DB is empty --------------------------
REM   We probe the DB itself instead of relying on a flag file, so the
REM   launcher works correctly even when the operator already has a
REM   populated stock_ai.db from a previous session.
".venv\bin\python.exe" scripts\check_seeded.py
if errorlevel 1 (
    echo [4/7] DB has no stocks rows - seeding mock data...
    ".venv\bin\python.exe" scripts\seed_mock_data.py
    if errorlevel 1 (
        echo.
        echo [WARN] seed_mock_data.py failed - continuing anyway.
        echo You can re-run later with:  .venv\bin\python.exe scripts\seed_mock_data.py
    )
) else (
    echo [4/7] Mock data already loaded - skipping seed.
)

REM ---- 5. Install frontend dependencies on first run -------------------------
if not exist "frontend\node_modules" (
    echo [5/7] Installing frontend dependencies ^(first run, ~1-2 minutes^)...
    pushd frontend
    call npm install
    set "INSTALL_RC=%errorlevel%"
    popd
    if not "%INSTALL_RC%"=="0" (
        echo.
        echo [ERROR] npm install failed. Is Node.js installed and on PATH?
        pause
        exit /b 1
    )
) else (
    echo [5/7] frontend\node_modules exists - skipping npm install.
)

REM ---- 6. Pre-flight: free up ports 8000 and 5173 ---------------------------
REM   Re-running run.bat (or any leftover from a previous session) would fail
REM   to bind the ports. We proactively kill anything LISTENING on the two
REM   target ports so the launcher is fully idempotent — clicking run.bat
REM   twice cleanly restarts both services.
set "FREED_PORTS=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
    echo [6/7] Port 8000 in use ^(pid %%a^) - stopping...
    taskkill /F /PID %%a >nul 2>&1
    set "FREED_PORTS=1"
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173.*LISTENING"') do (
    echo [6/7] Port 5173 in use ^(pid %%a^) - stopping...
    taskkill /F /PID %%a >nul 2>&1
    set "FREED_PORTS=1"
)
if "%FREED_PORTS%"=="1" (
    REM Give the OS a moment to actually release the sockets before binding.
    timeout /t 2 /nobreak >nul
)

REM ---- 6b. Launch backend in a new window ------------------------------------
echo [6/7] Launching backend ^(uvicorn :8000^)...
start "Stock AI - Backend (uvicorn :8000)" cmd /k "chcp 65001 >nul && set PYTHONUTF8=1 && .venv\bin\uvicorn.exe app.main:app --reload --port 8000"

REM Give the backend a moment to bind the port before opening the frontend.
timeout /t 3 /nobreak >nul

REM ---- 7. Launch frontend in a new window ------------------------------------
echo [7/7] Launching frontend ^(vite :5173^)...
start "Stock AI - Frontend (vite :5173)" cmd /k "chcp 65001 >nul && cd frontend && npm run dev"

REM Wait for vite to actually be ready before opening the browser.
timeout /t 5 /nobreak >nul

REM ---- 8. Open browser -------------------------------------------------------
start "" "http://127.0.0.1:5173/"

echo.
echo ===========================================================================
echo  Stock AI Platform is running:
echo    Backend  http://127.0.0.1:8000   (Swagger UI: /docs, health: /health)
echo    Frontend http://127.0.0.1:5173
echo ===========================================================================
echo.
echo  This launcher window can now be closed.
echo  The backend and frontend keep running in their own windows.
echo  To stop everything, run:  stop.bat
echo.
echo  Safe by default:
echo    KILL_SWITCH_ENABLED=true  /  REAL_TRADING_ENABLED=false
echo    REAL_ORDER_DRY_RUN=true   /  KIS_ORDER_ENABLED=false
echo  Real KIS orders will NEVER fire unless you explicitly flip these in
echo  .env per RUNBOOK_REAL_TRADING.md.
echo.
pause
