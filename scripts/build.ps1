[CmdletBinding()]
param(
    [switch]$OneFile,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Cannot create .venv. Install Python 3.10-3.13 first." }
}

& $Python -m pip install --disable-pip-version-check -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

if (-not (Test-Path "assets\icon.ico")) {
    & $Python scripts\generate_icon.py
    if ($LASTEXITCODE -ne 0) { throw "Icon generation failed." }
}

if (-not $SkipTests) {
    $env:AUTOCLICKER_DISABLE_FILE_LOG = "1"
    & $Python -m unittest discover -s tests -t . -v
    if ($LASTEXITCODE -ne 0) { throw "Tests failed; build stopped." }
    & $Python run.py --self-test
    if ($LASTEXITCODE -ne 0) { throw "Self-test failed; build stopped." }
}

$env:AUTOCLICKER_ONEFILE = if ($OneFile) { "1" } else { "0" }
& $Python -m PyInstaller --noconfirm --clean AutoClicker.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

if ($OneFile) {
    Write-Host "`nBuild complete: dist\AutoClicker.exe" -ForegroundColor Green
} else {
    Write-Host "`nBuild complete: dist\AutoClicker\AutoClicker.exe (keep the whole folder)" -ForegroundColor Green
}
