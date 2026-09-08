Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  LogiScan — Docker Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$dockerInstalled = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerInstalled) {
    Write-Host "Docker not found! Please install Docker Desktop:" -ForegroundColor Red
    Write-Host "https://docs.docker.com/desktop/install/windows-install/" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Building and starting LogiScan..." -ForegroundColor Green
Set-Location deployment
docker compose up -d --build

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  LogiScan is running!" -ForegroundColor Green
Write-Host "  Dashboard: http://localhost:8501" -ForegroundColor Yellow
Write-Host "  API Docs:  http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Run 'docker compose down' in deployment/ to stop" -ForegroundColor Gray
