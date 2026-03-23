@echo off
echo Starting BTC Application...

:: Start Backend
start "BTC Backend" cmd /k "cd backend && run_backend.bat"

:: Start Frontend
start "BTC Frontend" cmd /k "run_frontend.bat"

echo Application started in new windows.
