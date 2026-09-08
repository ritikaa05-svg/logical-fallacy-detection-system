@echo off
setlocal enabledelayedexpansion
TITLE LogiScan Native Launcher

set PID_FILE_BACKEND=%TEMP%\logiscan_backend.pid

echo Cleaning up old LogiScan instances...
if exist "%PID_FILE_BACKEND%" (
    set /p OLD_PID=<"%PID_FILE_BACKEND%"
    tasklist /FI "PID eq !OLD_PID!" 2>nul | findstr /I "python.exe uvicorn.exe" >nul 2>nul
    if !errorlevel! equ 0 (
        taskkill /F /PID !OLD_PID! >nul 2>nul
        timeout /t 1 /nobreak >nul
    )
    del "%PID_FILE_BACKEND%" 2>nul
)

:: Kill any leftover processes on our ports
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>nul
)

:: Python check
python --version >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: Python not found. Please install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

:: Node.js check
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo Warning: Node.js not found. Install from https://nodejs.org to build the SPA.
    echo The API will still be available at http://localhost:8000/docs
)

:: Virtual environment
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat

:: Install Python dependencies
pip install -q -r backend\requirements.txt 2>nul || pip install -r backend\requirements.txt

:: Build React frontend
where node >nul 2>nul
if !errorlevel! equ 0 (
    if not exist "frontend\dist" (
        echo Installing frontend dependencies...
        cd frontend && npm ci --silent && cd ..
        echo Building React frontend...
        cd frontend && npm run build && cd ..
    ) else (
        echo Frontend build found.
    )
)

:: Start backend and capture PID via PowerShell
echo Starting backend...
powershell -Command "$p = Start-Process -FilePath 'uvicorn' -ArgumentList 'backend.app.main:app','--host','0.0.0.0','--port','8000','--log-level','warning' -WindowStyle Hidden -PassThru; Write-Output $p.Id" > "%PID_FILE_BACKEND%"
set /p BACKEND_PID=<"%PID_FILE_BACKEND%"

:: Wait for backend to be ready
echo Waiting for backend...
for /l %%i in (1,1,30) do (
    >nul 2>nul powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8000/api/v1/health/live' -TimeoutSec 2 -UseBasicParsing; exit 0 } catch { exit 1 }"
    if !errorlevel! equ 0 (
        echo Backend ready.
        goto :backend_ready
    )
    timeout /t 1 /nobreak >nul
)
echo Warning: Backend health check timed out, continuing anyway...
:backend_ready

echo ===========================================
echo   LogiScan v1.2 is running!
echo   SPA:  http://localhost:8000
echo   API:  http://localhost:8000/docs
echo   - Close this window to stop all services.
echo ===========================================

:: Keep window open and wait
:wait_loop
timeout /t 5 /nobreak >nul
if exist "%PID_FILE_BACKEND%" (
    set /p BACKEND_PID=<"%PID_FILE_BACKEND%"
    tasklist /FI "PID eq !BACKEND_PID!" 2>nul | findstr /I "python.exe uvicorn.exe" >nul 2>nul
    if !errorlevel! neq 0 (
        echo Backend process died. Check logs above for errors.
        pause
        exit /b 1
    )
)
goto :wait_loop
