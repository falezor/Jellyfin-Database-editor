param(
    [string]$PayloadX64 = "",
    [string]$PayloadX86 = "",
    [string]$Output = "",
    [string]$Makensis = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$versionLine = Select-String -Path (Join-Path $root "jf_browser.py") -Pattern '^APP_VERSION\s*=\s*["'']([^"'']+)["'']' | Select-Object -First 1
if (-not $versionLine) { throw "APP_VERSION not found in jf_browser.py" }
$version = $versionLine.Matches[0].Groups[1].Value

if (-not $PayloadX64) {
    $PayloadX64 = Join-Path $env:USERPROFILE "Downloads\jellyfin-db-editor_${version}_windows_x64_portable"
}
if (-not $PayloadX86) {
    $PayloadX86 = Join-Path $env:USERPROFILE "Downloads\jellyfin-db-editor_${version}_windows_x86_portable"
}
$PayloadX64 = [IO.Path]::GetFullPath($PayloadX64)
$PayloadX86 = [IO.Path]::GetFullPath($PayloadX86)
foreach ($payload in @($PayloadX64, $PayloadX86)) {
    if (-not (Test-Path (Join-Path $payload "jellyfin-db-editor.exe"))) {
        throw "Payload is not a built portable package: $payload"
    }
    if (-not (Test-Path (Join-Path $payload "_internal\python313.dll"))) {
        throw "Payload is missing _internal\python313.dll: $payload"
    }
}

if (-not $Output) {
    $Output = Join-Path $env:USERPROFILE "Downloads\jellyfin-db-editor_${version}_windows_x86_x64_setup.exe"
}
$Output = [IO.Path]::GetFullPath($Output)
$outputDir = Split-Path -Parent $Output
if ($outputDir) { New-Item -ItemType Directory -Force -Path $outputDir | Out-Null }

$icon = Join-Path $PSScriptRoot "jellyfin-db-editor.ico"
if (-not (Test-Path $icon)) { throw "Missing installer icon: $icon" }

if (-not $Makensis) {
    $Makensis = $env:MAKENSIS
}
if (-not $Makensis) {
    $cmd = Get-Command makensis.exe -ErrorAction SilentlyContinue
    if ($cmd) { $Makensis = $cmd.Source }
}
if (-not $Makensis) {
    foreach ($candidate in @(
        "C:\Program Files (x86)\NSIS\makensis.exe",
        "C:\Program Files\NSIS\makensis.exe",
        "C:\Program Files (x86)\NSIS\Bin\makensis.exe",
        "C:\Program Files\NSIS\Bin\makensis.exe"
    )) {
        if (Test-Path $candidate) { $Makensis = $candidate; break }
    }
}
if (-not $Makensis -or -not (Test-Path $Makensis)) {
    throw "makensis.exe not found. Install NSIS 3.x or pass -Makensis <path>."
}

$script = Join-Path $PSScriptRoot "installer.nsi"
if (Test-Path $Output) { Remove-Item $Output -Force }

Write-Host "Payload x64: $PayloadX64"
Write-Host "Payload x86: $PayloadX86"
Write-Host "Version:     $version"
Write-Host "Output:      $Output"
Write-Host "NSIS:        $Makensis"

& $Makensis `
    "/DPAYLOAD_X64=$PayloadX64" `
    "/DPAYLOAD_X86=$PayloadX86" `
    "/DOUT_FILE=$Output" `
    "/DAPP_VERSION=$version" `
    "/DICON_FILE=$icon" `
    $script

if ($LASTEXITCODE -ne 0) { throw "makensis failed with exit code $LASTEXITCODE" }
if (-not (Test-Path $Output)) { throw "NSIS did not produce $Output" }

$hash = (Get-FileHash $Output -Algorithm SHA256).Hash
$size = (Get-Item $Output).Length
Write-Host ""
Write-Host "Installer: $Output"
Write-Host "Size:      $size bytes"
Write-Host "SHA256:    $hash"
