[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Path,
    [Parameter(Mandatory=$true)][string]$CertificateThumbprint,
    [string]$SignToolPath,
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $Path)) { throw "File not found: $Path" }
if (-not $SignToolPath) {
    $Command = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($Command) { $SignToolPath = $Command.Source }
}
if (-not $SignToolPath -or -not (Test-Path $SignToolPath)) {
    throw "signtool.exe was not found. Install Windows SDK or pass -SignToolPath."
}

# The certificate stays in the Windows certificate store. No private key or
# password is read from source files or written to logs.
& $SignToolPath sign /fd SHA256 /td SHA256 /tr $TimestampUrl /sha1 $CertificateThumbprint $Path
if ($LASTEXITCODE -ne 0) { throw "Code signing failed: $Path" }
& $SignToolPath verify /pa $Path
if ($LASTEXITCODE -ne 0) { throw "Signature verification failed: $Path" }
Write-Host "Signed and verified: $Path" -ForegroundColor Green
