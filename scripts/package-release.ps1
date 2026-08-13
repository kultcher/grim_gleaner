[CmdletBinding()]
param(
    [string]$BuildPython = "",
    [string]$NuitkaVersion = "4.1.3",
    [switch]$SkipTests,
    [switch]$Overwrite
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot "..")
)
$distRoot = Join-Path $projectRoot "dist"
$releaseRoot = Join-Path $distRoot "Grim Gleaner"
$buildWorkspace = Join-Path $projectRoot "build\release-package"
$deployOutput = Join-Path $buildWorkspace "executable"
$standaloneOutput = Join-Path $deployOutput "grim_gleaner.dist"
$generatedSpec = Join-Path $buildWorkspace "pysidedeploy.spec"
$specTemplate = Join-Path $projectRoot "packaging\pysidedeploy.spec.template"
$iconPath = Join-Path $projectRoot "packaging\gg_icon.ico"
$archivePath = Join-Path $distRoot "Grim-Gleaner-0.9.1-beta-win64.zip"
$temporaryRoot = [System.IO.Path]::GetFullPath(
    [System.IO.Path]::GetTempPath()
)
$testWorkspace = Join-Path $temporaryRoot (
    "grim-gleaner-package-tests-" + [guid]::NewGuid().ToString("N")
)

function Assert-SafeProjectChild {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$ExpectedParent
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $fullParent = [System.IO.Path]::GetFullPath($ExpectedParent)
    $prefix = $fullParent.TrimEnd('\') + '\'
    if (-not $fullPath.StartsWith(
        $prefix,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to modify a path outside $fullParent`: $fullPath"
    }
}

function Remove-GeneratedPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$ExpectedParent,
        [switch]$Recurse
    )

    Assert-SafeProjectChild -Path $Path -ExpectedParent $ExpectedParent
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        throw "Refusing to remove a generated path that is a reparse point: $Path"
    }
    if ($Recurse) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    else {
        Remove-Item -LiteralPath $Path -Force
    }
}

Assert-SafeProjectChild -Path $buildWorkspace -ExpectedParent $projectRoot
Assert-SafeProjectChild -Path $releaseRoot -ExpectedParent $distRoot
Assert-SafeProjectChild -Path $archivePath -ExpectedParent $distRoot
Assert-SafeProjectChild -Path $testWorkspace -ExpectedParent $temporaryRoot

if (-not $BuildPython) {
    $BuildPython = Join-Path $projectRoot ".venv-build\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $BuildPython -PathType Leaf)) {
    throw @"
Python 3.13 build environment not found at:
$BuildPython

Create it before packaging:
  py -3.13 -m venv .venv-build
  .\.venv-build\Scripts\python.exe -m pip install -e ".[test,release]"
"@
}
$BuildPython = (Resolve-Path -LiteralPath $BuildPython).Path

$pythonVersion = & $BuildPython -c (
    "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
)
if ($LASTEXITCODE -ne 0 -or $pythonVersion.Trim() -ne "3.13") {
    throw "Release builds require Python 3.13; found $pythonVersion"
}

$deployTool = Join-Path (Split-Path $BuildPython) "pyside6-deploy.exe"
if (-not (Test-Path -LiteralPath $deployTool -PathType Leaf)) {
    throw "pyside6-deploy.exe is missing from the build environment."
}
if (-not (Test-Path -LiteralPath $specTemplate -PathType Leaf)) {
    throw "Packaging template is missing: $specTemplate"
}
if (-not (Test-Path -LiteralPath $iconPath -PathType Leaf)) {
    throw "Application icon is missing: $iconPath"
}
$iconBytes = [System.IO.File]::ReadAllBytes($iconPath)
if (
    $iconBytes.Length -lt 22 -or
    [BitConverter]::ToUInt16($iconBytes, 0) -ne 0 -or
    [BitConverter]::ToUInt16($iconBytes, 2) -ne 1 -or
    [BitConverter]::ToUInt16($iconBytes, 4) -lt 1
) {
    throw "Application icon is not a valid ICO container: $iconPath"
}

if ((Test-Path -LiteralPath $releaseRoot) -and -not $Overwrite) {
    throw "Release folder already exists. Remove it or rerun with -Overwrite."
}
if ((Test-Path -LiteralPath $archivePath) -and -not $Overwrite) {
    throw "Release archive already exists. Remove it or rerun with -Overwrite."
}

if (-not $SkipTests) {
    $testTemp = Join-Path $testWorkspace "tmp"
    $testCache = Join-Path $testWorkspace "cache"
    New-Item -ItemType Directory -Path $testWorkspace -Force | Out-Null
    try {
        & $BuildPython -m pytest `
            --basetemp $testTemp `
            -o "cache_dir=$testCache"
        if ($LASTEXITCODE -ne 0) {
            throw "Tests failed; packaging stopped."
        }
    }
    finally {
        Remove-GeneratedPath `
            -Path $testWorkspace `
            -ExpectedParent $temporaryRoot `
            -Recurse
    }
}

if (Test-Path -LiteralPath $buildWorkspace) {
    Remove-GeneratedPath -Path $buildWorkspace -ExpectedParent $projectRoot -Recurse
}
if ($Overwrite -and (Test-Path -LiteralPath $releaseRoot)) {
    Remove-GeneratedPath -Path $releaseRoot -ExpectedParent $distRoot -Recurse
}
if ($Overwrite -and (Test-Path -LiteralPath $archivePath)) {
    Remove-GeneratedPath -Path $archivePath -ExpectedParent $distRoot
}

New-Item -ItemType Directory -Path $deployOutput -Force | Out-Null
New-Item -ItemType Directory -Path $distRoot -Force | Out-Null

$template = Get-Content -LiteralPath $specTemplate -Raw
$spec = $template.Replace("__PROJECT_ROOT__", $projectRoot)
$spec = $spec.Replace("__DEPLOY_OUTPUT__", $deployOutput)
$spec = $spec.Replace("__ICON_PATH__", $iconPath)
$spec = $spec.Replace("__PYTHON_PATH__", $BuildPython)
$spec = $spec.Replace("__NUITKA_VERSION__", $NuitkaVersion)
[System.IO.File]::WriteAllText(
    $generatedSpec,
    $spec,
    [System.Text.UTF8Encoding]::new($false)
)

& $deployTool -c $generatedSpec --force
if ($LASTEXITCODE -ne 0) {
    throw "pyside6-deploy failed."
}

$builtExecutable = Join-Path $standaloneOutput "grim_gleaner.exe"
if (-not (Test-Path -LiteralPath $standaloneOutput -PathType Container)) {
    throw "Expected standalone distribution was not produced: $standaloneOutput"
}
if (-not (Test-Path -LiteralPath $builtExecutable -PathType Leaf)) {
    throw "Expected executable was not produced: $builtExecutable"
}
$standaloneFiles = @(
    Get-ChildItem -LiteralPath $standaloneOutput -Recurse -File
)
if ($standaloneFiles.Count -lt 2) {
    throw "Standalone distribution does not contain its required dependencies."
}

Copy-Item -LiteralPath $standaloneOutput -Destination $releaseRoot -Recurse

& $BuildPython -m gd_affix_relevance.cli assemble-release `
    --project-root $projectRoot `
    --output-dir $releaseRoot
if ($LASTEXITCODE -ne 0) {
    throw "Release resource assembly failed."
}

$requiredPaths = @(
    "grim_gleaner.exe",
    "README.txt",
    "LICENSE.txt",
    "THIRD_PARTY_NOTICES.txt",
    "release-manifest.json",
    "catalog\manifest.json",
    "tags\tags_items.txt",
    "tags\tagsgdx1_items.txt",
    "tags\tagsgdx2_items.txt",
    "tags\tagsgdx3_items.txt",
    "Profiles",
    "Profiles\examples"
)
foreach ($relativePath in $requiredPaths) {
    $candidate = Join-Path $releaseRoot $relativePath
    if (-not (Test-Path -LiteralPath $candidate)) {
        throw "Release validation failed; missing $relativePath"
    }
}

Compress-Archive -LiteralPath $releaseRoot `
    -DestinationPath $archivePath

Write-Host "Release folder: $releaseRoot"
Write-Host "Release archive: $archivePath"
