# Reset script for Lab 2 Multi-Model Benchmark (Windows PowerShell)
$ErrorActionPreference = "Stop"

$LAB_DIR = $PSScriptRoot
$REPO_URL = "https://github.com/leadwithnav/ai_multi_model.git"

# Determine target git repository location
$GIT_TARGET = $LAB_DIR
if (Test-Path (Join-Path $LAB_DIR "..\order-flow-service\.git")) {
    $GIT_TARGET = Join-Path $LAB_DIR "..\order-flow-service"
} elseif (Test-Path (Join-Path $LAB_DIR "order-flow-service\.git")) {
    $GIT_TARGET = Join-Path $LAB_DIR "order-flow-service"
} elseif (Test-Path (Join-Path $LAB_DIR "..\.git")) {
    $GIT_TARGET = Join-Path $LAB_DIR ".."
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

# Ensure generated test file is removed if left over from Task 4
$GEN_TEST = Join-Path $LAB_DIR "..\order-flow-service\tests\test_inventory_generated.py"
if (Test-Path $GEN_TEST) { Remove-Item $GEN_TEST -Force }

Write-Host "Repository reset to baseline ($REPO_URL)." -ForegroundColor Green
