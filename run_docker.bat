@echo off
echo ===========================================
echo   LogiScan — Docker Setup for Windows
echo ===========================================
echo.

REM Check Docker
docker --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Docker not found! Please install Docker Desktop:
    echo https://docs.docker.com/desktop/install/windows-install/
    pause
    exit /b 1
)

echo Starting LogiScan...
cd deployment
docker compose up -d --build

echo.
echo ===========================================
echo   LogiScan is running!
echo   Dashboard: http://localhost:8501
echo   API Docs:  http://localhost:8000/docs
echo ===========================================
echo.
echo Press any key to stop...
pause >nul
docker compose down
