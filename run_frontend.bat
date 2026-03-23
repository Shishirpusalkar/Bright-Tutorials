@echo off
echo Starting BTC Frontend...
cd /d "%~dp0\frontend"
npm run dev -- --host 127.0.0.1
