param(
    [string]$WowRetailRoot = "C:\Games\World of Warcraft\_retail_",
    [string]$BackupRoot = "backups",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$tocPath = Join-Path $repoRoot "EvokerAug.toc"
if (-not (Test-Path -LiteralPath $tocPath)) {
    throw "EvokerAug.toc was not found under source root: $repoRoot"
}

$wowRoot = (Resolve-Path -LiteralPath $WowRetailRoot).Path
$addonsRoot = Join-Path $wowRoot "Interface\AddOns"
if (-not (Test-Path -LiteralPath $addonsRoot)) {
    throw "WoW AddOns directory was not found: $addonsRoot"
}

$installedAddonPath = Join-Path $addonsRoot "EvokerAug"
$backupRootPath = Join-Path $repoRoot $BackupRoot
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupPath = Join-Path $backupRootPath "EvokerAug-installed-$timestamp"

Write-Output "Source: $repoRoot"
Write-Output "Install link: $installedAddonPath"
Write-Output "Backup root: $backupRootPath"

if (-not $Apply) {
    Write-Output "Dry run only. Re-run with -Apply to move the installed folder into backups and create the junction."
    exit 0
}

New-Item -ItemType Directory -Force -Path $backupRootPath | Out-Null

if (Test-Path -LiteralPath $installedAddonPath) {
    $installed = Get-Item -LiteralPath $installedAddonPath
    if ($installed.LinkType -eq "Junction" -and $installed.Target -eq $repoRoot) {
        Write-Output "Existing EvokerAug junction already points at source root."
        exit 0
    }

    Move-Item -LiteralPath $installedAddonPath -Destination $backupPath
    Write-Output "Backed up existing install to: $backupPath"
}

New-Item -ItemType Junction -Path $installedAddonPath -Target $repoRoot | Out-Null
Write-Output "Created junction: $installedAddonPath -> $repoRoot"
