$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$StateFile = Join-Path $RepoRoot ".tools\public-tunnel-state.json"

function Stop-ProcessTree {
    param([int]$TargetProcessId)

    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$TargetProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        Stop-ProcessTree -TargetProcessId $child.ProcessId
    }

    $process = Get-Process -Id $TargetProcessId -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $TargetProcessId -Force
        Write-Host "Stopped process $TargetProcessId"
    }
}

if (-not (Test-Path $StateFile)) {
    Write-Host "No public tunnel state file found."
    exit 0
}

$state = Get-Content $StateFile -Raw | ConvertFrom-Json
$pids = @($state.tunnel_pid, $state.server_pid) | Where-Object { $_ }

foreach ($processId in $pids) {
    Stop-ProcessTree -TargetProcessId $processId
}

Remove-Item $StateFile -Force
Write-Host "Public tunnel stopped."
