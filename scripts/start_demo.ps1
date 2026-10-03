$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root'; python -m uvicorn monitoring.main:app --host 127.0.0.1 --port 8000"
Write-Host "waiting for monitoring service..."
Start-Sleep -Seconds 3

& "$PSScriptRoot\start_servers.ps1"
Start-Sleep -Seconds 2

Start-Process "http://127.0.0.1:8000"
Write-Host "Dashboard: http://127.0.0.1:8000"
