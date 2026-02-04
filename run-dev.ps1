# GigaBoard Full Stack Development
# Запускает Backend и Frontend одновременно

Write-Host "[*] Starting GigaBoard Full Stack..." -ForegroundColor Green
Write-Host ""

$BackendPath = Join-Path $PSScriptRoot "apps\backend"
$jobs = @()

# Start Backend
Write-Host "[Backend] Starting Backend (port 8000)..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    param($root)
    Set-Location "$root\apps\backend"
    & "$root\.venv\Scripts\python.exe" run_dev.py
} -ArgumentList $PSScriptRoot
$jobs += $backendJob
Start-Sleep -Seconds 3

# Start Frontend
Write-Host "[Frontend] Starting Frontend (port 5173)..." -ForegroundColor Cyan
$frontendJob = Start-Job -ScriptBlock {
    param($root)
    Set-Location $root
    npm --workspace apps/web run dev
} -ArgumentList $PSScriptRoot
$jobs += $frontendJob

Write-Host ""
Write-Host "[OK] Services starting..." -ForegroundColor Green
Write-Host "   Backend:  http://localhost:8000" -ForegroundColor Yellow
Write-Host "   API Docs: http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "   Frontend: http://localhost:5173" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop all services" -ForegroundColor White

# Wait for jobs and stream output
try {
    while ($true) {
        foreach ($job in $jobs) {
            $output = Receive-Job -Job $job 2>&1
            if ($output) {
                Write-Host $output
            }
        }
        Start-Sleep -Milliseconds 100
        
        # Check if any job failed
        $failed = $jobs | Where-Object { $_.State -eq 'Failed' }
        if ($failed) {
            Write-Host "[ERROR] Some services failed to start" -ForegroundColor Red
            break
        }
    }
} finally {
    Write-Host ""
    Write-Host "[STOP] Stopping services..." -ForegroundColor Yellow
    $jobs | Stop-Job
    $jobs | Remove-Job
    Write-Host "[OK] All services stopped" -ForegroundColor Green
}
