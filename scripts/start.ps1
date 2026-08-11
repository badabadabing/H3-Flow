param(
    [string]$ComfyRoot,
    [string]$ComfyUrl = 'http://127.0.0.1:8188',
    [string]$ComfyStartScript,
    [int]$Port = 4173,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$bridge = Join-Path $projectRoot 'bridge.py'

if (-not (Test-Path -LiteralPath $bridge -PathType Leaf)) {
    throw "H3 Flow bridge not found: $bridge"
}
if ($ComfyRoot -and -not (Test-Path -LiteralPath $ComfyRoot -PathType Container)) {
    throw "ComfyUI root not found: $ComfyRoot"
}
if ($ComfyStartScript -and -not (Test-Path -LiteralPath $ComfyStartScript -PathType Leaf)) {
    throw "ComfyUI start script not found: $ComfyStartScript"
}

$env:H3_FLOW_PROJECT_ROOT = $projectRoot
$env:H3_FLOW_COMFY_URL = $ComfyUrl
if ($ComfyRoot) { $env:H3_FLOW_COMFY_ROOT = (Resolve-Path -LiteralPath $ComfyRoot).Path }
if ($ComfyStartScript) { $env:H3_FLOW_START_SCRIPT = (Resolve-Path -LiteralPath $ComfyStartScript).Path }

$pythonCommand = Get-Command py -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    throw 'Python launcher "py" was not found. Install Python 3.11 or newer.'
}

$process = Start-Process -FilePath $pythonCommand.Source -ArgumentList @('-3', '-X', 'utf8', $bridge, '--port', $Port) -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru
$baseUrl = "http://127.0.0.1:$Port"
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    Start-Sleep -Milliseconds 250
    if ($process.HasExited) { throw "H3 Flow exited during startup with code $($process.ExitCode)." }
    try {
        Invoke-RestMethod -Uri "$baseUrl/api/status" -TimeoutSec 3 | Out-Null
        if (-not $NoBrowser) { Start-Process $baseUrl }
        [pscustomobject]@{ Status = 'started'; Pid = $process.Id; Url = $baseUrl }
        return
    }
    catch { }
}

if (-not $process.HasExited) { Stop-Process -Id $process.Id }
throw "H3 Flow did not become ready on $baseUrl."
