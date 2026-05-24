param(
    [string]$RepoRoot = (Get-Location).Path,
    [string]$User = "root",
    [string]$Password = "23050929",
    [string]$HostName = "localhost",
    [int]$Port = 3306,
    [string]$MySqlExe = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
)

$ErrorActionPreference = "Stop"

$migrationsDir = Join-Path $RepoRoot "backend\sql\migrations"

if (-not (Test-Path $MySqlExe)) {
    throw "mysql client not found: $MySqlExe"
}

if (-not (Test-Path $migrationsDir)) {
    Write-Host "No migrations directory: $migrationsDir"
    return
}

$files = Get-ChildItem $migrationsDir -Filter "*.sql" | Sort-Object Name

if ($files.Count -eq 0) {
    Write-Host "No migration files found."
    return
}

foreach ($file in $files) {
    Write-Host "Running: $($file.Name)"
    $sourcePath = $file.FullName.Replace('\', '/')
    & $MySqlExe -h $HostName -P $Port -u $User "-p$Password" -e "source $sourcePath"
}

Write-Host "All migrations finished."
