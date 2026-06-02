param(
    [string]$Version = "v1.0.24-midnight.1",
    [string]$OutputDirectory = "dist"
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

function Test-AnyWildcardMatch {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value,
        [string[]]$Patterns = @()
    )

    foreach ($pattern in $Patterns) {
        if ($Value -like $pattern) {
            return $true
        }
    }

    return $false
}

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$outputRoot = Resolve-ChildPath -BasePath $repoRoot -ChildPath $OutputDirectory
$stagingRoot = Join-Path $outputRoot "_staging"
$addonRoot = Join-Path $stagingRoot "EvokerAug"
$defaultZipName = "EvokerAug-v1.0.24-midnight.1.zip"
$zipName = if ($PSBoundParameters.ContainsKey("Version")) { "EvokerAug-$Version.zip" } else { $defaultZipName }
$zipPath = Join-Path $outputRoot $zipName
Assert-PathInsideRoot -Path $outputRoot -RootPath $repoRoot -Label "OutputDirectory"
Assert-PathInsideRoot -Path $stagingRoot -RootPath $outputRoot -Label "stagingRoot"
Assert-PathInsideRoot -Path $zipPath -RootPath $outputRoot -Label "zipPath"

$ignoredDirectories = @(
    ".git",
    ".github",
    ".pytest_cache",
    "backups",
    "dist",
    "tests",
    "scripts"
)

$ignoredFiles = @(
    ".gitignore",
    ".pkgmeta",
    "AGENTS.md",
    "AUDIT.md",
    "PLAN.md",
    "NOTES.md",
    "TODO.md",
    "CLAUDE.md"
)

$ignoredDirectoryPatterns = @(
    "*.private"
)

$ignoredFilePatterns = @(
    "*.private.md"
)

$ignoredRelativeDirectories = @(
    "Libs\AceGUI-3.0-SharedMediaWidgets\Libs"
)

if (Test-Path -LiteralPath $stagingRoot) {
    Remove-Item -LiteralPath $stagingRoot -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $addonRoot | Out-Null
New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null

$sourceItems = Get-ChildItem -LiteralPath $repoRoot -Force
foreach ($item in $sourceItems) {
    if ($item.PSIsContainer -and (($ignoredDirectories -contains $item.Name) -or (Test-AnyWildcardMatch -Value $item.Name -Patterns $ignoredDirectoryPatterns))) {
        continue
    }

    if (-not $item.PSIsContainer -and (($ignoredFiles -contains $item.Name) -or (Test-AnyWildcardMatch -Value $item.Name -Patterns $ignoredFilePatterns))) {
        continue
    }

    Copy-Item -LiteralPath $item.FullName -Destination $addonRoot -Recurse
}

foreach ($relativeDirectory in $ignoredRelativeDirectories) {
    $excludedPath = Resolve-ChildPath -BasePath $addonRoot -ChildPath $relativeDirectory
    Assert-PathInsideRoot -Path $excludedPath -RootPath $addonRoot -Label "ignoredRelativeDirectory"
    if (Test-Path -LiteralPath $excludedPath) {
        Remove-Item -LiteralPath $excludedPath -Recurse -Force
    }
}

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

Compress-Archive -Path $addonRoot -DestinationPath $zipPath -Force
Remove-Item -LiteralPath $stagingRoot -Recurse -Force

Write-Output $zipPath
