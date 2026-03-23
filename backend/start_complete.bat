@echo off
echo ============================================================
echo   BTC AI Test System - Complete Setup and Startup
echo ============================================================
echo.

:: Step 1: Navigate to backend
cd /d "%~dp0\backend"

:: Step 2: Activate virtual environment
echo [1/5] Activating virtual environment...
call .venv\Scripts\activate

:: Step 3: Install/Update dependencies
echo [2/5] Installing dependencies...
pip install -q pandas openpyxl

:: Step 4: Run database migrations
echo [3/5] Running database migrations...
python -m alembic upgrade head

:: Step 5: Start Ollama (in background)
echo [4/5] Starting Ollama (Mistral AI)...
start /min cmd /c "ollama run mistral"

:: Step 6: Start Backend
echo [5/5] Starting Backend Server...
echo.
echo ============================================================
echo   System Ready!
echo   - Backend: http://localhost:8000
echo   - Frontend: Run run_frontend.bat in another terminal
echo   - Ollama: Running in background
echo ============================================================
echo.

for /f "tokens=5" %%a in ('netstat -aon ^| find ":8000" ^| find "LISTENING"') do taskkill /f /pid %%a 2>nul
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

pause
