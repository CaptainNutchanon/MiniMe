param(
    [string]$AdapterPath = "output\captain-lora",
    [ValidateSet("normalize", "force", "off")]
    [string]$IdentityPolicy = "normalize",
    [string]$BindHost = "127.0.0.1",
    [string]$AccessKey = "",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $RepoRoot "captain-env\Scripts\python.exe"

try {
    [Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $OutputEncoding = [System.Text.UTF8Encoding]::new($false)
} catch {
}

$pathValue = [Environment]::GetEnvironmentVariable("Path", "Process")
if (-not $pathValue) {
    $pathValue = [Environment]::GetEnvironmentVariable("PATH", "Process")
}
if ($pathValue) {
    [Environment]::SetEnvironmentVariable("PATH", $null, "Process")
    [Environment]::SetEnvironmentVariable("Path", $pathValue, "Process")
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:MINIME_ADAPTER_PATH = $AdapterPath
$env:MINIME_IDENTITY_POLICY = $IdentityPolicy
if ($AccessKey) {
    $env:MINIME_ACCESS_KEY = $AccessKey
} else {
    Remove-Item Env:\MINIME_ACCESS_KEY -ErrorAction SilentlyContinue
}

Write-Host "MiniMe server"
Write-Host "  Python:   $Python"
Write-Host "  Adapter:  $AdapterPath"
Write-Host "  Identity: $IdentityPolicy"
Write-Host "  Guard:    light"
Write-Host "  Access:   $(if ($AccessKey) { 'protected' } else { 'open' })"
Write-Host "  URL:      http://$BindHost`:$Port"
if ($AccessKey) {
    Write-Host "  Key URL:  http://127.0.0.1:$Port/?key=$AccessKey"
}

Push-Location $RepoRoot
try {
    & $Python -m uvicorn web_app.server:app --host $BindHost --port $Port
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
