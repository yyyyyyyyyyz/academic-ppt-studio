param(
    [int]$Port = 8000,
    [switch]$RebuildFrontend
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendDir = Join-Path $RepoRoot "frontend"
$DistIndex = Join-Path $FrontendDir "dist\index.html"
$PythonExe = Join-Path $RepoRoot "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    throw "Backend Python venv not found at $PythonExe"
}

if ($RebuildFrontend -or -not (Test-Path $DistIndex)) {
    Write-Host "[1/2] Building frontend production bundle..." -ForegroundColor Cyan
    $PortableNode = "D:\node-portable\node-v24.22.0-win-x64"
    if (Test-Path $PortableNode) {
        $env:PATH = "$PortableNode;" + $env:PATH
    }
    npm --prefix $FrontendDir run build
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend build failed with exit code $LASTEXITCODE"
    }
}

$LanIps = @()
try {
    $LanIps = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notlike "127.*" -and
            $_.IPAddress -notlike "169.254.*" -and
            $_.InterfaceAlias -notmatch "Loopback|vEthernet"
        } |
        Select-Object -ExpandProperty IPAddress -Unique
} catch {
    $LanIps = @()
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkRed
Write-Host "  Academic Studio - Single-Port Shareable Server" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor DarkRed
Write-Host "  Local URL  : http://127.0.0.1:$Port/" -ForegroundColor Green
foreach ($ip in $LanIps) {
    Write-Host "  LAN Share  : http://${ip}:$Port/" -ForegroundColor Cyan
}
Write-Host "  Public URL : Run in another terminal ->" -ForegroundColor Yellow
Write-Host "               cloudflared tunnel --url http://127.0.0.1:$Port" -ForegroundColor Gray
Write-Host "  AI Mode    : BYOK headers + local deterministic fallback" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor DarkRed
Write-Host ""

$env:LLM_PROVIDER_MODE = "auto"
$env:FIGURE_PROVIDER_MODE = "local"

& $PythonExe -m uvicorn app.main:app --app-dir (Join-Path $RepoRoot "backend") --host 0.0.0.0 --port $Port
