@echo off
title Options Trading Platform Launcher
color 0A

echo ======================================================================
echo           OPTIONS TRADING PLATFORM - OPEN MARKET LAUNCHER
echo ======================================================================
echo.

set "ROOT_DIR=%~dp0"
set "SERVER_DIR=%ROOT_DIR%stock webpage - Copy\server"
set "APP_DIR=%ROOT_DIR%stock webpage - Copy\app"
set "OPTIONS_DIR=%ROOT_DIR%OPTIONS"

echo [1/4] Starting Backend API Server (Port 4000)...
start "Backend API Server [Port 4000]" cmd /k "cd /d "%SERVER_DIR%" && node index.js"
timeout /t 3 /nobreak >nul

echo [2/4] Starting Frontend Web Interface (Port 5173)...
start "Frontend UI [Port 5173]" cmd /k "cd /d "%APP_DIR%" && npm run dev"
timeout /t 2 /nobreak >nul

echo.
echo Opening Upstox Morning Login in your Browser...
start http://localhost:4000/login

echo.
echo ======================================================================
echo  IMPORTANT MORNING STEP:
echo  1. An Upstox login page has opened in your browser.
echo  2. Enter your Phone Number, OTP, and 6-digit PIN.
echo  3. Once you see "Upstox authentication successful", press any key below!
echo ======================================================================
echo.
pause

echo.
echo [3/4] Starting Upstox Market Feed Recorder (recorder.py)...
start "Upstox Feed Recorder [recorder.py]" cmd /k "cd /d "%OPTIONS_DIR%" && python recorder.py"
timeout /t 3 /nobreak >nul

echo [4/4] Starting Python Quant Execution Engine (runner.py)...
start "Python Quant Engine [runner.py]" cmd /k "cd /d "%OPTIONS_DIR%" && python runner.py"

echo.
echo Opening Options Dashboard: http://localhost:5173/#/options
start http://localhost:5173/#/options

echo.
echo ======================================================================
echo  SYSTEM RUNNING! All 4 components are active for the market session:
echo   1. Express Backend (Port 4000)
echo   2. React Frontend (Port 5173)
echo   3. Upstox Feed Recorder (recorder.py - Live WebSockets)
echo   4. Quant Engine (runner.py - Greeks, VWOIM, Signals)
echo ======================================================================
echo.
timeout /t 5 >nul
