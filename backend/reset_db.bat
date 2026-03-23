@echo off
cls
echo ==========================================
echo    BRIGHT TUTORIALS - DATABASE RESET
echo ==========================================
echo.
cd /d "%~dp0"

if exist .venv\Scripts\activate (
    call .venv\Scripts\activate
)

echo Running clearing script...
python clear_db.py

echo Seeding initial admin data...
python -m app.initial_data

echo.
echo Database reset complete!
pause

REM Run migrations
echo Running migrations...
alembic upgrade head

REM Seed initial data
echo Seeding initial data...
python -m app.initial_data

echo Database reset complete!
pause
