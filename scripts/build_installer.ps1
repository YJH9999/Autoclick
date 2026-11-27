[CmdletBinding()]
param(
    [switch]$SkipTests,
    [string]$IsccPath,
    [string]$CertificateThumbprint,
    [string]$SignToolPath
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$VersionMatch = Select-String -Path "src\autoclicker\__init__.py" -Pattern '__version__\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"'
if (-not $VersionMatch) { throw "Cannot read the application version." }
$Version = $VersionMatch.Matches[0].Groups[1].Value

& (Join-Path $PSScriptRoot "build.ps1") -SkipTests:$SkipTests
if ($LASTEXITCODE -ne 0) { throw "Application build failed." }
if (-not (Test-Path "dist\AutoClicker\AutoClicker.exe")) { throw "Main executable is missing." }
if (-not (Test-Path "dist\AutoClicker\_internal")) { throw "The modular _internal directory is missing." }

if ($CertificateThumbprint) {
    $SignParameters = @{ Path = "dist\AutoClicker\AutoClicker.exe"; CertificateThumbprint = $CertificateThumbprint }
    if ($SignToolPath) { $SignParameters.SignToolPath = $SignToolPath }
    & (Join-Path $PSScriptRoot "sign_file.ps1") @SignParameters
    if ($LASTEXITCODE -ne 0) { throw "Application signing failed." }
}

if (-not $IsccPath) {
    $Candidates = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $IsccPath = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $IsccPath -or -not (Test-Path $IsccPath)) {
    throw "Inno Setup 6.5+ was not found. Install it or pass -IsccPath."
}

& $IsccPath "/DMyAppVersion=$Version" "installer\AutoClicker.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed." }

$SetupName = "AutoClicker-$Version-Windows-Setup.exe"
$SetupPath = Join-Path $Root "dist\installer\$SetupName"
if (-not (Test-Path $SetupPath)) { throw "Installer was not generated: $SetupPath" }

if ($CertificateThumbprint) {
    $SignParameters = @{ Path = $SetupPath; CertificateThumbprint = $CertificateThumbprint }
    if ($SignToolPath) { $SignParameters.SignToolPath = $SignToolPath }
    & (Join-Path $PSScriptRoot "sign_file.ps1") @SignParameters
    if ($LASTEXITCODE -ne 0) { throw "Installer signing failed." }
}

$Hash = (Get-FileHash -Algorithm SHA256 $SetupPath).Hash.ToLowerInvariant()
$ChecksumPath = Join-Path $Root "dist\installer\SHA256SUMS.txt"
[System.IO.File]::WriteAllText($ChecksumPath, "$Hash  $SetupName`r`n", [System.Text.Encoding]::ASCII)

Write-Host "`nInstaller: $SetupPath" -ForegroundColor Green
Write-Host "SHA256:    $Hash"
Write-Host "Checksum:  $ChecksumPath"
Write-Host "Installed layout: AutoClicker.exe + _internal modules, DLLs and resources."
