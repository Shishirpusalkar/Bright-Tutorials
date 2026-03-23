@echo off
echo Cleaning NPM Cache and Reinstalling...

cd /d "%~dp0"

echo 1. Clearing NPM Cache...
call npm cache clean --force

echo 2. Removing potential lock files and modules...
if exist package-lock.json del package-lock.json
if exist node_modules rmdir /s /q node_modules

echo 3. Installing dependencies...
call npm install

echo 4. Starting Server...
npm run dev

pause
