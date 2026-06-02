param(
    [string]$Version = "v1.0.24-midnight.1",
    [string]$OutputDirectory = "dist"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$outputRoot = Join-Path $repoRoot $OutputDirectory
$stagingRoot = Join-Path $outputRoot "_staging"
$addonRoot = Join-Path $stagingRoot "EvokerAug"
$defaultZipName = "EvokerAug-v1.0.24-midnight.1.zip"
$zipName = if ($PSBoundParameters.ContainsKey("Version")) { "EvokerAug-$Version.zip" } else { $defaultZipName }
$zipPath = Join-Path $outputRoot $zipName

$ignoredDirectories = @(
    ".git",
    ".github",
    ".pytest_cache",
    "dist",
    "tests",
    "scripts"
)

$ignoredFiles = @(
    ".gitignore",
    ".pkgmeta"
)

if (Test-Path -LiteralPath $stagingRoot) {
    Remove-Item -LiteralPath $stagingRoot -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $addonRoot | Out-Null
New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null

$sourceItems = Get-ChildItem -LiteralPath $repoRoot -Force
foreach ($item in $sourceItems) {
    if ($item.PSIsContainer -and ($ignoredDirectories -contains $item.Name)) {
        continue
    }

    if (-not $item.PSIsContainer -and ($ignoredFiles -contains $item.Name)) {
        continue
    }

    Copy-Item -LiteralPath $item.FullName -Destination $addonRoot -Recurse
}

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

Compress-Archive -Path $addonRoot -DestinationPath $zipPath -Force
Remove-Item -LiteralPath $stagingRoot -Recurse -Force

Write-Output $zipPath
