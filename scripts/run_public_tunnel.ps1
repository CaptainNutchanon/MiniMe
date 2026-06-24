param(
    [string]$AdapterPath = "output\captain-lora",
    [ValidateSet("normalize", "force", "off")]
    [string]$IdentityPolicy = "normalize",
    [int]$Port = 8000,
    [string]$AccessKey = "",
    [switch]$DownloadCloudflared,
    [switch]$Background
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ToolsDir = Join-Path $RepoRoot ".tools"
$LocalCloudflared = Join-Path $ToolsDir "cloudflared.exe"
$StateFile = Join-Path $ToolsDir "public-tunnel-state.json"
$ServerOutLog = Join-Path $ToolsDir "minime-server.out.log"
$ServerErrLog = Join-Path $ToolsDir "minime-server.err.log"
$TunnelOutLog = Join-Path $ToolsDir "cloudflared.out.log"
$TunnelErrLog = Join-Path $ToolsDir "cloudflared.err.log"

function New-AccessKey {
    $bytes = New-Object byte[] 18
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

function Stop-ProcessTree {
    param([int]$TargetProcessId)

    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$TargetProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        Stop-ProcessTree -TargetProcessId $child.ProcessId
    }

    $process = Get-Process -Id $TargetProcessId -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $TargetProcessId -Force
    }
}

$cloudflaredCommand = Get-Command cloudflared -ErrorAction SilentlyContinue
if ($cloudflaredCommand) {
    $Cloudflared = $cloudflaredCommand.Source
} elseif (Test-Path $LocalCloudflared) {
    $Cloudflared = $LocalCloudflared
} elseif ($DownloadCloudflared) {
    New-Item -ItemType Directory -Path $ToolsDir -Force | Out-Null
    Write-Host "Downloading cloudflared..."
    Invoke-WebRequest `
        -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" `
        -OutFile $LocalCloudflared
    $Cloudflared = $LocalCloudflared
} else {
    throw "cloudflared.exe not found. Re-run with -DownloadCloudflared or install cloudflared first."
}

if (-not $AccessKey) {
    $AccessKey = New-AccessKey
}

$EncodedKey = [uri]::EscapeDataString($AccessKey)
$ServerScript = Join-Path $PSScriptRoot "run_server.ps1"
$ServerArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $ServerScript,
    "-AdapterPath",
    $AdapterPath,
    "-IdentityPolicy",
    $IdentityPolicy,
    "-BindHost",
    "127.0.0.1",
    "-Port",
    $Port,
    "-AccessKey",
    $AccessKey
)

Write-Host "MiniMe public tunnel"
Write-Host "  Local URL: http://127.0.0.1:$Port/?key=$EncodedKey"
Write-Host "  Access key: $AccessKey"
Write-Host ""
Write-Host "When cloudflared prints a https://*.trycloudflare.com URL, share it with this suffix:"
Write-Host "  /?key=$EncodedKey"
Write-Host ""
Write-Host "Keep this window open while friends are testing."
Write-Host ""

if ($Background) {
    Remove-Item $ServerOutLog, $ServerErrLog, $TunnelOutLog, $TunnelErrLog -ErrorAction SilentlyContinue

    $server = Start-Process `
        -FilePath "powershell.exe" `
        -ArgumentList $ServerArgs `
        -WindowStyle Hidden `
        -RedirectStandardOutput $ServerOutLog `
        -RedirectStandardError $ServerErrLog `
        -PassThru

    Start-Sleep -Seconds 2

    $tunnel = Start-Process `
        -FilePath $Cloudflared `
        -ArgumentList @("tunnel", "--url", "http://127.0.0.1:$Port") `
        -WindowStyle Hidden `
        -RedirectStandardOutput $TunnelOutLog `
        -RedirectStandardError $TunnelErrLog `
        -PassThru

    $TunnelUrl = $null
    for ($i = 0; $i -lt 90; $i++) {
        $outText = Get-Content $TunnelOutLog -Raw -ErrorAction SilentlyContinue
        $errText = Get-Content $TunnelErrLog -Raw -ErrorAction SilentlyContinue
        $combined = "$outText`n$errText"
        if ($combined -match "https://[a-zA-Z0-9.-]+\.trycloudflare\.com") {
            $TunnelUrl = $Matches[0]
            break
        }
        Start-Sleep -Seconds 1
    }

    $state = [ordered]@{
        server_pid = $server.Id
        tunnel_pid = $tunnel.Id
        port = $Port
        access_key = $AccessKey
        tunnel_url = $TunnelUrl
        share_url = if ($TunnelUrl) { "$TunnelUrl/?key=$EncodedKey" } else { $null }
        server_stdout_log = $ServerOutLog
        server_stderr_log = $ServerErrLog
        tunnel_stdout_log = $TunnelOutLog
        tunnel_stderr_log = $TunnelErrLog
    }
    $state | ConvertTo-Json | Set-Content -Path $StateFile -Encoding UTF8

    if ($TunnelUrl) {
        Write-Host "Tunnel is running in background."
        Write-Host "Share URL: $TunnelUrl/?key=$EncodedKey"
    } else {
        Write-Host "Tunnel started, but no public URL was found yet."
        Write-Host "Check logs:"
        Write-Host "  $TunnelOutLog"
        Write-Host "  $TunnelErrLog"
    }
    Write-Host "State file: $StateFile"
    Write-Host "Stop with: powershell -NoProfile -ExecutionPolicy Bypass -File scripts\stop_public_tunnel.ps1"
    exit 0
}

$server = Start-Process -FilePath "powershell.exe" -ArgumentList $ServerArgs -WindowStyle Hidden -PassThru

try {
    Start-Sleep -Seconds 2
    & $Cloudflared tunnel --url "http://127.0.0.1:$Port"
} finally {
    if ($server -and -not $server.HasExited) {
        Stop-ProcessTree -TargetProcessId $server.Id
    }
}
