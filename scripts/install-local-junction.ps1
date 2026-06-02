param(
    [string]$WowRetailRoot = "C:\Games\World of Warcraft\_retail_",
    [string]$BackupRoot = "backups",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

function Resolve-ChildPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BasePath,
        [Parameter(Mandatory = $true)]
        [string]$ChildPath
    )

    $candidate = if ([System.IO.Path]::IsPathRooted($ChildPath)) {
        $ChildPath
    } else {
        Join-Path $BasePath $ChildPath
    }

    [System.IO.Path]::GetFullPath($candidate)
}

function Assert-PathInsideRoot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$RootPath,
        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    $rootFull = [System.IO.Path]::GetFullPath($RootPath).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    $pathFull = [System.IO.Path]::GetFullPath($Path).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    $rootPrefix = $rootFull + [System.IO.Path]::DirectorySeparatorChar

    if (-not $pathFull.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Label must stay under $rootFull. Got: $pathFull"
    }
}

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
$backupRootPath = Resolve-ChildPath -BasePath $repoRoot -ChildPath $BackupRoot
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupPath = Join-Path $backupRootPath "EvokerAug-installed-$timestamp"
Assert-PathInsideRoot -Path $installedAddonPath -RootPath $addonsRoot -Label "installedAddonPath"
Assert-PathInsideRoot -Path $backupRootPath -RootPath $repoRoot -Label "BackupRoot"
Assert-PathInsideRoot -Path $backupPath -RootPath $backupRootPath -Label "backupPath"

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
