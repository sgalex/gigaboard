# GigaBoard Backend Development Server
# Usage: .\run-backend.ps1 from project root

Write-Host "🚀 Starting GigaBoard Backend..." -ForegroundColor Green
cd $PSScriptRoot
Set-Location apps\backend
$env:PYTHONUNBUFFERED = "1"
& "$PSScriptRoot\.venv\Scripts\python.exe" -u run_dev.py
