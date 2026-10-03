$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

foreach ($node in @("server-a", "server-b", "server-c")) {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root'; `$env:NODE_ID='$node'; python -m server.main"
    Write-Host "started $node"
}
