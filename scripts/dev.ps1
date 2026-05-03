# SlideNote 개발 서버 일괄 실행 (Windows PowerShell)
# 사용법: .\scripts\dev.ps1

$Root = Split-Path -Parent $PSScriptRoot

# 백엔드 실행
$backendPath = Join-Path $Root "src\backend"
$backendJob = Start-Job -ScriptBlock {
    param($path)
    Set-Location $path
    python -W ignore -m uvicorn main:app --reload --port 8000
} -ArgumentList $backendPath

Write-Host "[1/2] 백엔드 시작 중 (FastAPI :8000)..." -ForegroundColor Cyan

# 프론트엔드 실행
$frontendPath = Join-Path $Root "src\frontend"
$frontendJob = Start-Job -ScriptBlock {
    param($path)
    Set-Location $path
    npm run dev
} -ArgumentList $frontendPath

Write-Host "[2/2] 프론트엔드 시작 중 (Vite :5174)..." -ForegroundColor Cyan

Write-Host ""
Write-Host "SlideNote 실행 중" -ForegroundColor Green
Write-Host "  백엔드:     http://localhost:8000"
Write-Host "  API 문서:   http://localhost:8000/docs"
Write-Host "  프론트엔드: http://localhost:5174"
Write-Host ""
Write-Host "종료: Ctrl+C" -ForegroundColor Yellow

# 로그 스트리밍
try {
    while ($true) {
        Receive-Job -Job $backendJob  | ForEach-Object { Write-Host "[BE] $_" }
        Receive-Job -Job $frontendJob | ForEach-Object { Write-Host "[FE] $_" }
        Start-Sleep -Milliseconds 500
    }
} finally {
    Stop-Job  -Job $backendJob, $frontendJob
    Remove-Job -Job $backendJob, $frontendJob -Force
}
