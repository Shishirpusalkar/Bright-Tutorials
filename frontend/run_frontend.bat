@echo off
echo ============================================================
echo   Starting Frontend (Vite Dev Server)
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/2] Installing dependencies...
call npm.cmd install

echo [2/2] Starting dev server...
echo.
echo Frontend will be available at: http://localhost:5173
echo.

call npm.cmd run dev

pause
