@echo off
title Arbitrage Calculator Launcher
color 0A

echo ===================================================
echo     ARBITRAGE CALCULATOR INITIALIZATION SEQUENCE
echo ===================================================
echo.
echo [1/3] Terminating any ghost background processes...
powershell -Command "Stop-Process -Name 'node' -Force -ErrorAction SilentlyContinue; Stop-Process -Name 'python' -Force -ErrorAction SilentlyContinue"

echo [2/3] Booting up React Frontend and Node API (Port 5000)...
cd /d "%~dp0"
start "Arbitrage Frontend & API" cmd /k "echo --- FRONTEND BOOTING --- && npm run dev"

timeout /t 5 /nobreak >nul

echo [3/3] Booting up Python ML Semantic Matcher (Port 8000)...
start "Semantic AI Matcher" cmd /k "echo --- ML MATCHER BOOTING --- && .venv\Scripts\python -m backend.main"

echo.
echo ===================================================
echo     ALL SYSTEMS ONLINE!
echo ===================================================
echo The dashboard will be available at: http://localhost:5000
echo.
echo Waiting for Vite Dev Server to finish compiling...
timeout /t 5 /nobreak >nul
echo Opening browser...
start http://localhost:5000
echo.
echo You can now safely close this launcher window!
pause >nul
