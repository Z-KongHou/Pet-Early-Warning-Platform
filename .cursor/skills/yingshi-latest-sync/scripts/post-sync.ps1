param(
    [string]$RepoRoot = (Get-Location).Path
)

$ErrorActionPreference = "Stop"

$skillDir = Split-Path $PSScriptRoot -Parent
$ensureDb = Join-Path $PSScriptRoot "ensure-local-db-password.ps1"
$migrate = Join-Path $PSScriptRoot "run-migrations.ps1"
$frontendDir = Join-Path $RepoRoot "frontend"

Write-Host "=== Post-sync steps ==="

& $ensureDb -RepoRoot $RepoRoot
& $migrate -RepoRoot $RepoRoot

if (-not (Test-Path $frontendDir)) {
    Write-Warning "frontend/ not found, skipping pnpm install"
    return
}

Push-Location $frontendDir
try {
    if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
        throw "pnpm not found in PATH. Install pnpm or run manually in frontend/."
    }
    Write-Host "Running pnpm install in frontend/"
    pnpm install
    Write-Host "pnpm install completed."
} finally {
    Pop-Location
}

Write-Host "Post-sync finished."
