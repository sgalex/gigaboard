# GigaBoard Backend Development Server
# Usage: .\run-backend.ps1 from project root

Write-Host "🚀 Starting GigaBoard Backend..." -ForegroundColor Green
cd $PSScriptRoot
Set-Location apps\backend
& "$PSScriptRoot\.venv\Scripts\python.exe" run_dev.py
