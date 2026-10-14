[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GameFolder,
    [ValidateSet("en", "ru")]
    [string]$Locale = "en",
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if (-not $Python) { $Python = Join-Path $projectRoot ".venv\Scripts\python.exe" }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python not found: $Python. Pass -Python with your development interpreter."
}
$cleanRoot = Join-Path $projectRoot "build\localization-smoke\$Locale\clean"
$outputRoot = Join-Path $projectRoot "build\localization-smoke\$Locale\output"
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $projectRoot "src"
try {
    & $Python -m gd_affix_relevance.cli prepare-game-localization `
        --game-folder $GameFolder --locale $Locale --output-dir $cleanRoot
    if ($LASTEXITCODE -ne 0) { throw "Real ArchiveTool extraction failed." }
    & $Python -m gd_affix_relevance.cli generate-output `
        --catalog-root (Join-Path $projectRoot "artifacts\catalog") `
        --profile-file (Join-Path $projectRoot "artifacts\profiles\examples\Chaos_Pets_Deceiver.json") `
        --source-root $cleanRoot --output-dir $outputRoot --locale $Locale
    if ($LASTEXITCODE -ne 0) { throw "Consolidated generation failed." }
    Write-Host "Smoke test passed. Generated localization: $outputRoot"
    Write-Host "The installed game's Settings files were not changed."
} finally {
    if ($null -eq $previousPythonPath) {
        Remove-Item Env:PYTHONPATH
    } else {
        $env:PYTHONPATH = $previousPythonPath
    }
}
