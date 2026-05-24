param(
    [string]$RepoRoot = (Get-Location).Path,
    [switch]$DryRun,
    [switch]$SkipPostSync
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
$postSync = Join-Path $PSScriptRoot "post-sync.ps1"

if (-not (Test-Path $SnapshotRoot)) {
    throw "Snapshot not found: $SnapshotRoot"
}

$remoteName = "latest-snapshot"
$snapshotGit = Join-Path $SnapshotRoot ".git"
if (-not (Test-Path $snapshotGit)) {
    throw "Snapshot is not a git repo: $SnapshotRoot"
}

$didCherryPick = $false

Push-Location $RepoRoot
try {
    if (-not (Test-Path (Join-Path $RepoRoot ".git"))) {
        throw "Main repo is not a git repository: $RepoRoot"
    }

    $status = git status --porcelain
    if ($status) {
        Write-Warning "Working tree has uncommitted changes. Cherry-pick may conflict."
        Write-Host $status
    }

    Invoke-GitQuiet remote remove $remoteName | Out-Null
    Invoke-Git remote add $remoteName ($SnapshotRoot -replace '\\', '/') | Out-Null
    Invoke-Git fetch $remoteName main | Out-Null

    $base = (Invoke-Git merge-base HEAD "FETCH_HEAD").Trim()
    $head = (Invoke-Git rev-parse "FETCH_HEAD").Trim()

    Write-Host "Cherry-pick range: ${base}..${head}"
    $treeDiff = Invoke-Git diff --stat HEAD "FETCH_HEAD"
    if (-not $treeDiff) {
        Write-Host "Already up to date — tree matches latest snapshot (no cherry-pick needed)."
    } else {
        $pending = @(Invoke-Git log --oneline "${base}..FETCH_HEAD")
        if (-not $pending -or $pending.Count -eq 0) {
            Write-Host "Already up to date — no commits to cherry-pick."
        } elseif ($DryRun) {
            Write-Host "Dry run — would cherry-pick:"
            $pending
        } else {
            $pending
            Invoke-Git cherry-pick "${base}..FETCH_HEAD" | Out-Null
            Write-Host "Cherry-pick completed."
            $didCherryPick = $true
        }
    }

    Invoke-GitQuiet remote remove $remoteName | Out-Null
} catch {
    Invoke-GitQuiet remote remove $remoteName | Out-Null
    throw
} finally {
    Pop-Location
}

if (-not $DryRun -and -not $SkipPostSync) {
    & $postSync -RepoRoot $RepoRoot
}

if ($DryRun) {
    Write-Host "Dry run — post-sync skipped."
}
