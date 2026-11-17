# 启动 SiftRepo 前端（Streamlit）
# 用法： .\scripts\run_frontend.ps1
# 需要后端已经在跑；默认连 http://127.0.0.1:8000

param(
    [string]$ApiUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = "utf-8"

$candidates = @(
    "D:\conda\envs\siftrepo\python.exe",
    "python"
)
$python = $null
foreach ($candidate in $candidates) {
    if ($candidate -eq "python") {
        if (Get-Command python -ErrorAction SilentlyContinue) { $python = "python"; break }
    }
    elseif (Test-Path $candidate) {
        $python = $candidate
        break
    }
}

if (-not $python) {
    Write-Host "[x] 没找到 Python：请先 conda activate siftrepo" -ForegroundColor Red
    exit 1
}

# 前端通过这个变量找后端（代码里读 SIFTREPO_API_URL）
$env:SIFTREPO_API_URL = $ApiUrl

Write-Host ""
Write-Host "Python   : $python"
Write-Host "后端地址 : $ApiUrl"
Write-Host ""

# 先探一下后端在不在，省得前端白起
try {
    $probe = Invoke-WebRequest -Uri "$ApiUrl/projects" -UseBasicParsing -TimeoutSec 5
    Write-Host "后端状态 : 可用（GET /projects -> $([int]$probe.StatusCode)）" -ForegroundColor Green
}
catch {
    Write-Host "后端状态 : 连不上 —— 先在另一个窗口跑 .\scripts\run_backend.ps1" -ForegroundColor Yellow
}

Write-Host "启动前端：http://127.0.0.1:8501" -ForegroundColor Cyan
Write-Host ""

& $python -m streamlit run frontend/app.py
