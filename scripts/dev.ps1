param(
    [int]$BackendPort = 5000,
    [int]$FrontendPort = 4200,
    [int]$MaxPortTries = 30,
    [int]$SeedMultiplier = 300,
    [switch]$Install,
    [switch]$Seed,
    [switch]$NoOpen
)

$ErrorActionPreference = 'Stop'

$Root = Resolve-Path (Join-Path $PSScriptRoot '..')
$BackendDir = Join-Path $Root 'backend'
$FrontendDir = Join-Path $Root 'frontend'
$VenvDir = Join-Path $Root 'venv'
$Python = Join-Path $VenvDir 'Scripts\python.exe'
$NodeModules = Join-Path $FrontendDir 'node_modules'
$InstallScript = Join-Path $Root 'scripts\install-dependencies.ps1'

function Test-Command($Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-Port($Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Get-FreePort($PreferredPort, $Label) {
    for ($port = $PreferredPort; $port -lt ($PreferredPort + $MaxPortTries); $port++) {
        if (-not (Test-Port $port)) {
            if ($port -ne $PreferredPort) {
                Write-Host "$Label port $PreferredPort is busy; using $port instead." -ForegroundColor Yellow
            }
            return $port
        }
    }
    throw "No free $Label port found from $PreferredPort to $($PreferredPort + $MaxPortTries - 1)."
}

function Start-DevProcess($Title, $WorkingDirectory, $Command) {
    $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) {
        $pwsh = (Get-Command powershell).Source
    }
    Start-Process -FilePath $pwsh -WorkingDirectory $WorkingDirectory -ArgumentList @(
        '-NoExit',
        '-ExecutionPolicy', 'Bypass',
        '-Command',
        "`$Host.UI.RawUI.WindowTitle = '$Title'; $Command"
    )
}

if ($Install -or -not (Test-Path $Python) -or -not (Test-Path $NodeModules)) {
    $installArgs = @()
    if ($Install) {
        $installArgs += '-Force'
    }
    & powershell -ExecutionPolicy Bypass -File $InstallScript @installArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'Dependency installation failed.'
    }
}

$BackendPort = Get-FreePort $BackendPort 'Backend'
$FrontendPort = Get-FreePort $FrontendPort 'Frontend'

if ($Seed) {
    Push-Location $BackendDir
    $env:FLASK_APP = 'run.py'
    & $Python -m flask seed-enterprise --scale 3 --multiplier $SeedMultiplier --reset --seed 20241334
    & $Python -m flask status
    Pop-Location
}

$RuntimeConfig = Join-Path $FrontendDir 'public\runtime-config.js'
$RuntimeConfigContent = @"
window.NEXUS_RUNTIME_CONFIG = {
  apiBaseUrl: 'http://127.0.0.1:$BackendPort/api/v1'
};
"@
Set-Content -LiteralPath $RuntimeConfig -Value $RuntimeConfigContent -Encoding UTF8

$corsOrigins = "http://localhost:$FrontendPort,http://127.0.0.1:$FrontendPort,http://localhost:4200,http://127.0.0.1:4200"
$backendCommand = "`$env:FLASK_ENV='development'; `$env:PORT='$BackendPort'; `$env:CORS_ORIGINS='$corsOrigins'; & '$Python' run.py"
$frontendCommand = "npm start -- --host 127.0.0.1 --port $FrontendPort"

Start-DevProcess "NEXUS Backend API :$BackendPort" $BackendDir $backendCommand
Start-Sleep -Seconds 2
Start-DevProcess "NEXUS Angular SPA :$FrontendPort" $FrontendDir $frontendCommand

$FrontendUrl = "http://127.0.0.1:$FrontendPort"

if (-not $NoOpen) {
    Start-Sleep -Seconds 4
    Start-Process $FrontendUrl
}

Write-Host ''
Write-Host 'NEXUS dev servers are starting...' -ForegroundColor Green
Write-Host "Backend API : http://127.0.0.1:$BackendPort/api/v1"
Write-Host "Frontend SPA: $FrontendUrl"
if ($Seed) {
    Write-Host "Data        : initialized with scale 3 x $SeedMultiplier, seed 20241334"
}
if ($NoOpen) {
    Write-Host 'Browser    : skipped because -NoOpen was provided'
} else {
    Write-Host 'Browser    : opening automatically'
}
Write-Host ''
Write-Host 'Edit backend/*.py or frontend/src/* files, then refresh the browser. Angular will hot reload automatically.'
