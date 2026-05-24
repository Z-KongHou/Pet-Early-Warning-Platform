param(
    [string]$RepoRoot = (Get-Location).Path,
    [string]$Password = "23050929"
)

$ErrorActionPreference = "Stop"

$configPath = Join-Path $RepoRoot "backend\src\main\resources\application.yml"

if (-not (Test-Path $configPath)) {
    throw "application.yml not found: $configPath"
}

$content = Get-Content $configPath -Raw

# Match only spring.datasource.password (line after username: root)
$pattern = '(?m)(^\s*username:\s*root\s*\r?\n\s*password:\s*).+$'
if ($content -match $pattern) {
    $newContent = [regex]::Replace($content, $pattern, "`${1}$Password", 1)
    if ($newContent -ne $content) {
        Set-Content -Path $configPath -Value $newContent -NoNewline
        Write-Host "Updated spring.datasource.password to $Password in application.yml"
    } else {
        Write-Host "spring.datasource.password already set to $Password"
    }
} else {
    throw "Could not find spring.datasource.password in application.yml"
}
