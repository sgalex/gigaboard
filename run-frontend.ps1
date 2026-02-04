# GigaBoard Frontend Development Server
# Usage: .\run-frontend.ps1 from project root

Write-Host "🎨 Starting GigaBoard Frontend..." -ForegroundColor Cyan
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot
npm --workspace apps/web run dev
