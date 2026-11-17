# 启动 SiftRepo 后端（不依赖 .env：key 从环境变量读）
# 用法：
#   .\scripts\run_backend.ps1              # 默认 127.0.0.1:8000
#   .\scripts\run_backend.ps1 -Port 8010   # 换端口

param(
    [int]$Port = 8000,
    [string]$HostAddress = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = "utf-8"

# 优先用 conda 环境里的解释器，找不到再退回 PATH 里的 python
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

# 环境自检：缺 key 只提示，不阻止启动（真正用到时才报错）
$missing = @()
foreach ($name in @("DEEPSEEK_API_KEY", "CLOSEAI_API_KEY")) {
    if (-not [Environment]::GetEnvironmentVariable($name)) { $missing += $name }
}

Write-Host ""
Write-Host "Python      : $python"
Write-Host "工作目录    : $root"
Write-Host ("DB_URL      : {0}" -f $(if ($env:DB_URL) { $env:DB_URL } else { "(未设置，代码会回退到 siftrepo)" }))
if ($missing.Count -eq 0) {
    Write-Host "API Key     : DEEPSEEK / CLOSEAI 都已设置" -ForegroundColor Green
} else {
    Write-Host ("API Key     : 缺少 {0} —— 服务能启动，但上传/问答/分析会报错" -f ($missing -join ", ")) -ForegroundColor Yellow
    Write-Host "              设置方法（当前窗口）：" -ForegroundColor Yellow
    Write-Host '              $env:DEEPSEEK_API_KEY="sk-..."' -ForegroundColor Yellow
    Write-Host '              $env:CLOSEAI_API_KEY="sk-..."' -ForegroundColor Yellow
}
Write-Host ""
Write-Host ("启动：http://{0}:{1}   （接口文档 /docs）" -f $HostAddress, $Port) -ForegroundColor Cyan
Write-Host ""

& $python -m uvicorn app.main:app --host $HostAddress --port $Port
