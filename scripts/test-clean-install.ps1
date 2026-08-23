[CmdletBinding()]
param(
    [string]$Python = "",
    [switch]$PrepareOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot "..")
)
$buildRoot = Join-Path $projectRoot "build"
$testRoot = Join-Path $buildRoot "clean-install-test"
$applicationRoot = Join-Path $testRoot "Grim Gleaner"
$settingsRoot = Join-Path $testRoot "application-settings"
$documentsRoot = Join-Path $testRoot "Documents"
$fakeGameRoot = Join-Path $testRoot "Fake Grim Dawn"

function Assert-SafeTestPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $fullBuildRoot = [System.IO.Path]::GetFullPath($buildRoot)
    $prefix = $fullBuildRoot.TrimEnd('\') + '\'
    if (-not $fullPath.StartsWith(
        $prefix,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to modify a path outside $fullBuildRoot`: $fullPath"
    }
}

Assert-SafeTestPath -Path $testRoot

if (-not $Python) {
    $Python = Join-Path $projectRoot ".venv\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw @"
Python environment not found at:
$Python

Create the development environment first, or pass -Python with its interpreter.
"@
}
$Python = (Resolve-Path -LiteralPath $Python).Path

if (Test-Path -LiteralPath $testRoot) {
    $testItem = Get-Item -LiteralPath $testRoot -Force
    if ($testItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        throw "Refusing to remove a clean-install workspace that is a reparse point."
    }
    Remove-Item -LiteralPath $testRoot -Recurse -Force
}

New-Item -ItemType Directory -Path $applicationRoot -Force | Out-Null
New-Item -ItemType Directory -Path $settingsRoot -Force | Out-Null
New-Item -ItemType Directory `
    -Path (Join-Path $documentsRoot "My Games\Grim Dawn\Settings") `
    -Force | Out-Null
New-Item -ItemType Directory -Path $fakeGameRoot -Force | Out-Null
New-Item -ItemType File `
    -Path (Join-Path $fakeGameRoot "Grim Dawn.exe") `
    -Force | Out-Null

& $Python -m gd_affix_relevance.cli assemble-release `
    --project-root $projectRoot `
    --output-dir $applicationRoot
if ($LASTEXITCODE -ne 0) {
    throw "Release resource assembly failed."
}

$catalogManifest = Join-Path $applicationRoot "catalog\manifest.json"
$baseTags = Join-Path $applicationRoot "tags\tags_items.txt"
if (-not (Test-Path -LiteralPath $catalogManifest -PathType Leaf)) {
    throw "Clean-install catalog is missing: $catalogManifest"
}
if (-not (Test-Path -LiteralPath $baseTags -PathType Leaf)) {
    throw "Clean-install tags are missing: $baseTags"
}

Write-Host "Fresh-install sandbox prepared at:"
Write-Host "  $testRoot"
Write-Host "When prompted for Grim Dawn, select the safe fake installation:"
Write-Host "  $fakeGameRoot"

if ($PrepareOnly) {
    Write-Host ""
    Write-Host "Launch later from this checkout with:"
    Write-Host "  `$env:GRIM_GLEANER_APP_ROOT = '$applicationRoot'"
    Write-Host "  `$env:GRIM_GLEANER_SETTINGS_ROOT = '$settingsRoot'"
    Write-Host "  `$env:GRIM_GLEANER_DOCUMENTS_ROOT = '$documentsRoot'"
    Write-Host "  & '$Python' -m gd_affix_relevance.ui.app"
    return
}

$savedApplicationRoot = [Environment]::GetEnvironmentVariable(
    "GRIM_GLEANER_APP_ROOT",
    "Process"
)
$savedSettingsRoot = [Environment]::GetEnvironmentVariable(
    "GRIM_GLEANER_SETTINGS_ROOT",
    "Process"
)
$savedDocumentsRoot = [Environment]::GetEnvironmentVariable(
    "GRIM_GLEANER_DOCUMENTS_ROOT",
    "Process"
)
try {
    $env:GRIM_GLEANER_APP_ROOT = $applicationRoot
    $env:GRIM_GLEANER_SETTINGS_ROOT = $settingsRoot
    $env:GRIM_GLEANER_DOCUMENTS_ROOT = $documentsRoot
    & $Python -m gd_affix_relevance.ui.app
    if ($LASTEXITCODE -ne 0) {
        throw "Grim Gleaner exited with code $LASTEXITCODE."
    }
}
finally {
    [Environment]::SetEnvironmentVariable(
        "GRIM_GLEANER_APP_ROOT",
        $savedApplicationRoot,
        "Process"
    )
    [Environment]::SetEnvironmentVariable(
        "GRIM_GLEANER_SETTINGS_ROOT",
        $savedSettingsRoot,
        "Process"
    )
    [Environment]::SetEnvironmentVariable(
        "GRIM_GLEANER_DOCUMENTS_ROOT",
        $savedDocumentsRoot,
        "Process"
    )
}
