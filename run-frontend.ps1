# GigaBoard Frontend Development Server
# Usage: .\run-frontend.ps1              — прокси API на localhost:8000 (uvicorn на хосте)
#         .\run-frontend.ps1 -DockerNginx — API через nginx Docker (только FRONTEND_PORT, например :3000)

param(
    [switch]$DockerNginx
)

Write-Host "🎨 Starting GigaBoard Frontend..." -ForegroundColor Cyan
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

if ($DockerNginx) {
    $env:VITE_DEV_PROXY_TARGET = "http://localhost:3000"
    Write-Host "→ VITE_DEV_PROXY_TARGET=http://localhost:3000 (полный стек в Docker, см. FRONTEND_PORT в .env)" -ForegroundColor Yellow
}

npm --workspace apps/web run dev
