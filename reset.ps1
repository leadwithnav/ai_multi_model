# Reset script for Lab 1 Quality, Cost, Latency Benchmark (Windows PowerShell)
$ErrorActionPreference = "Stop"

$LAB_DIR = $PSScriptRoot
$REPO_URL = "https://github.com/leadwithnav/ai_multi_model.git"

# Determine target git repository location
$GIT_TARGET = $LAB_DIR
if (Test-Path (Join-Path $LAB_DIR "order-flow-service\.git")) {
    $GIT_TARGET = Join-Path $LAB_DIR "order-flow-service"
} elseif (Test-Path (Join-Path $LAB_DIR "..\order-flow-service\.git")) {
    $GIT_TARGET = Join-Path $LAB_DIR "..\order-flow-service"
}

if (-not (Test-Path (Join-Path $GIT_TARGET ".git"))) {
    Write-Host "Cloning repository from $REPO_URL..." -ForegroundColor Yellow
    git clone $REPO_URL $LAB_DIR
} else {
    Push-Location $GIT_TARGET
    git remote set-url origin $REPO_URL
    git fetch origin
    git reset --hard HEAD
    git clean -fd
    Pop-Location
}

$RAW_DIR = Join-Path $LAB_DIR "artifacts\raw"
$RES_DIR = Join-Path $LAB_DIR "artifacts\results"

if (-not (Test-Path $RAW_DIR)) { New-Item -ItemType Directory -Path $RAW_DIR -Force | Out-Null }
if (-not (Test-Path $RES_DIR)) { New-Item -ItemType Directory -Path $RES_DIR -Force | Out-Null }

Write-Host "Repository reset to baseline ($REPO_URL)." -ForegroundColor Green
