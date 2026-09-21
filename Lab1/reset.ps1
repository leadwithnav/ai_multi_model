# Reset script for Lab 1 Quality, Cost, Latency Benchmark (Windows PowerShell)
$ErrorActionPreference = "Stop"

$LAB_DIR = $PSScriptRoot
$REPO_DIR = Join-Path $LAB_DIR "..\order-flow-service"

if (-not (Test-Path (Join-Path $REPO_DIR ".git"))) {
    Write-Error "ERROR: order-flow-service repository not found."
    exit 1
}

Push-Location $REPO_DIR
git reset --hard HEAD
git clean -fd
Pop-Location

$RAW_DIR = Join-Path $LAB_DIR "artifacts\raw"
$RES_DIR = Join-Path $LAB_DIR "artifacts\results"

if (-not (Test-Path $RAW_DIR)) { New-Item -ItemType Directory -Path $RAW_DIR -Force | Out-Null }
if (-not (Test-Path $RES_DIR)) { New-Item -ItemType Directory -Path $RES_DIR -Force | Out-Null }

Write-Host "Repository reset to baseline." -ForegroundColor Green
