param(
    [string]$RepoRoot = (Get-Location).Path,
    [string]$SnapshotRoot = ""
)

$ErrorActionPreference = "Stop"

function Invoke-GitQuiet {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & git @Args 2>$null | Out-Null
    $ErrorActionPreference = $prev
    return $LASTEXITCODE
}

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = & git @Args 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    if ($code -ne 0) {
        throw "git $($Args -join ' ') failed (exit $code): $output"
    }
    return $output
}

$SnapshotRoot = Join-Path $RepoRoot "latest\yingshi"

function Count-Files($path, $filter) {
    if (-not (Test-Path $path)) { return 0 }
    return (Get-ChildItem $path -Recurse -Filter $filter -File -ErrorAction SilentlyContinue).Count
}

Write-Host "=== Yingshi compare: main vs latest ==="
Write-Host "Main repo:     $RepoRoot"
Write-Host "Snapshot:      $SnapshotRoot"
Write-Host ""

if (-not (Test-Path $SnapshotRoot)) {
    throw "Snapshot not found: $SnapshotRoot"
}

$mainBackend = Join-Path $RepoRoot "backend\src\main\java"
$snapBackend = Join-Path $SnapshotRoot "backend\src\main\java"
$mainFrontend = Join-Path $RepoRoot "frontend\src"
$snapFrontend = Join-Path $SnapshotRoot "frontend\src"

Write-Host "Backend Java files:  main=$(Count-Files $mainBackend '*.java')  latest=$(Count-Files $snapBackend '*.java')"
Write-Host "Frontend src files:  main=$(Count-Files $mainFrontend '*')  latest=$(Count-Files $snapFrontend '*')"
Write-Host ""

Push-Location $RepoRoot
try {
    $mainTip = (git rev-parse HEAD).Trim()
    Write-Host "Main HEAD: $mainTip $(git log -1 --oneline)"
} finally {
    Pop-Location
}

Push-Location $SnapshotRoot
try {
    $snapTip = (git rev-parse HEAD).Trim()
    Write-Host "Latest HEAD: $snapTip $(git log -1 --oneline)"
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Commit delta (via merge-base):"

$remoteName = "latest-snapshot-compare"
Push-Location $RepoRoot
try {
    Invoke-GitQuiet remote remove $remoteName | Out-Null
    Invoke-Git remote add $remoteName ($SnapshotRoot -replace '\\', '/') | Out-Null
    Invoke-Git fetch $remoteName main | Out-Null

    $base = (Invoke-Git merge-base HEAD "FETCH_HEAD").Trim()

    $mainAhead = @(Invoke-Git log --oneline "${base}..HEAD")
    $snapAhead = @(Invoke-Git log --oneline "${base}..FETCH_HEAD")

    if ($mainAhead.Count -gt 0) {
        Write-Host "Commits only in main:"
        $mainAhead | ForEach-Object { "  $_" }
    } else {
        Write-Host "Commits only in main: (none)"
    }

    if ($snapAhead.Count -gt 0) {
        Write-Host "Commits only in latest:"
        $snapAhead | ForEach-Object { "  $_" }
    } else {
        Write-Host "Commits only in latest: (none)"
    }

    $treeDiff = Invoke-Git diff --stat HEAD "FETCH_HEAD"
    if (-not $treeDiff) {
        Write-Host "Status: content matches latest (tree identical)."
    } elseif ($snapAhead.Count -gt 0) {
        Write-Host "Status: latest has unpicked changes."
    }
} finally {
    Invoke-GitQuiet remote remove $remoteName | Out-Null
    Pop-Location
}

Write-Host ""
Write-Host "Backend files only in latest:"
$mainJava = @()
if (Test-Path $mainBackend) {
    $mainJava = Get-ChildItem $mainBackend -Recurse -Filter "*.java" | ForEach-Object {
        $_.FullName.Substring($mainBackend.Length + 1)
    }
}
$snapJava = Get-ChildItem $snapBackend -Recurse -Filter "*.java" | ForEach-Object {
    $_.FullName.Substring($snapBackend.Length + 1)
}
Compare-Object $mainJava $snapJava | Where-Object { $_.SideIndicator -eq "=>" } | ForEach-Object { "  + $($_.InputObject)" }

Write-Host ""
Write-Host "Frontend files only in latest:"
$mainFe = @()
if (Test-Path $mainFrontend) {
    $mainFe = Get-ChildItem $mainFrontend -Recurse -File | ForEach-Object {
        $_.FullName.Substring($mainFrontend.Length + 1)
    }
}
$snapFe = Get-ChildItem $snapFrontend -Recurse -File | ForEach-Object {
    $_.FullName.Substring($snapFrontend.Length + 1)
}
Compare-Object $mainFe $snapFe | Where-Object { $_.SideIndicator -eq "=>" } | ForEach-Object { "  + $($_.InputObject)" }
