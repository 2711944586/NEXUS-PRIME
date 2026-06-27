param(
    [int]$BackendPort = 5001,
    [int]$FrontendPort = 4200,
    [int]$MaxPortTries = 30,
    [int]$StartupTimeoutSeconds = 90,
    [int]$SeedMultiplier = 300,
    [switch]$Help,
    [switch]$Install,
    [switch]$NoInstall,
    [switch]$Seed,
    [switch]$NoOpen,
    [switch]$NoWait,
    [switch]$CheckOnly,
    [switch]$Docker,
    [switch]$Build,
    [switch]$ResetWorkspace
)

$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$BackendDir = Join-Path $Root 'backend'
$FrontendDir = Join-Path $Root 'frontend'
$VenvDir = Join-Path $Root 'venv'
$Python = Join-Path $VenvDir 'Scripts\python.exe'
$NodeModules = Join-Path $FrontendDir 'node_modules'
$InstallScript = Join-Path $Root 'scripts\install-dependencies.ps1'
$CleanScript = Join-Path $Root 'scripts\clean-workspace.ps1'
$RuntimeConfig = Join-Path $FrontendDir 'public\runtime-config.js'
$BackendEntry = Join-Path $BackendDir 'run.py'
$FrontendPackage = Join-Path $FrontendDir 'package.json'
$ComposeFile = Join-Path $Root 'docker-compose.yml'

function Test-Command($Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-FirstEnv([string[]]$Names, [string]$Default = '') {
    foreach ($name in $Names) {
        $value = [Environment]::GetEnvironmentVariable($name)
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            return $value
        }
    }
    return $Default
}

function Show-DevHelp {
    Write-Host @"
NEXUS Prime dev startup

Usage:
  .\scripts\dev.ps1 [options]
  .\start-dev.bat [options]

Common local options:
  -Install          Force dependency installation before startup.
  -NoInstall       Fail fast if venv or node_modules are missing.
  -Seed            Reset and seed local demo data before startup.
  -NoWait          Start backend/frontend windows without readiness probes.
  -NoOpen          Do not open the browser automatically.
  -CheckOnly       Validate prerequisites and ports without starting servers.

Port and timeout options:
  -BackendPort     Preferred backend port. Default: 5001.
  -FrontendPort    Preferred frontend port. Default: 4200.
  -MaxPortTries    Number of sequential ports to try if preferred ports are busy.
  -StartupTimeoutSeconds
                   Readiness probe timeout for backend and frontend.

Docker options:
  -Docker          Use docker compose for postgres, redis, backend, worker, beat, frontend.
  -Build           Rebuild Docker images during docker compose startup.
  -CheckOnly       With -Docker, also validate docker-compose.yml without starting containers.
  -ResetWorkspace   Stop workspace dev processes and clear local build caches before startup.

Examples:
  .\scripts\dev.ps1 -CheckOnly
  .\scripts\dev.ps1 -Install
  .\scripts\dev.ps1 -Docker -Build
  .\scripts\dev.ps1 -Docker -CheckOnly
"@
}

function Test-Port($Port) {
    try {
        return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    } catch {
        return $false
    }
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

function ConvertTo-SingleQuotedPowerShellString([string]$Value) {
    return "'" + ($Value -replace "'", "''") + "'"
}

function Assert-PathExists($Path, $Label) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label not found: $Path"
    }
}

function Assert-CommandExists($Name, $Hint) {
    if (-not (Test-Command $Name)) {
        throw "$Name not found. $Hint"
    }
}

function Test-DevPrerequisites {
    $issues = @()
    if (-not (Test-Path -LiteralPath $BackendEntry)) {
        $issues += "Missing backend entry: $BackendEntry"
    }
    if (-not (Test-Path -LiteralPath $FrontendPackage)) {
        $issues += "Missing frontend package.json: $FrontendPackage"
    }
    if (-not (Test-Path -LiteralPath $InstallScript)) {
        $issues += "Missing dependency installer: $InstallScript"
    }
    if (-not (Test-Path -LiteralPath $Python)) {
        $issues += "Missing Python virtualenv: $Python"
    }
    if (-not (Test-Path -LiteralPath $NodeModules)) {
        $issues += "Missing frontend dependencies: $NodeModules"
    }
    if (-not (Test-Command 'npm')) {
        $issues += 'npm is not available on PATH.'
    }
    if (-not (Test-Command 'node')) {
        $issues += 'node is not available on PATH.'
    }
    return $issues
}

function Assert-DockerComposeReady {
    if (-not (Test-Command 'docker')) {
        throw 'Docker CLI not found. Install Docker Desktop before using .\scripts\dev.ps1 -Docker.'
    }
    if (-not (Test-Path -LiteralPath $ComposeFile)) {
        throw "Docker Compose file not found: $ComposeFile"
    }

    $composeVersion = & docker compose version 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw 'docker compose is not available. Update Docker Desktop or enable the Compose plugin.'
    }
    return $composeVersion
}

function Assert-DockerComposeConfig {
    $composeArgs = @('compose', '--project-directory', $Root, '--file', $ComposeFile, 'config', '--quiet')
    & docker @composeArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'docker compose config validation failed.'
    }
}

function Write-RuntimeConfig([string]$ApiBaseUrl) {
    Assert-CommandExists 'node' 'Install Node.js LTS and reopen this terminal.'

    $previousApiBase = $env:NEXUS_LOCAL_API_BASE_URL
    $previousRuntimeLocal = $env:NEXUS_RUNTIME_CONFIG_LOCAL
    try {
        Push-Location $FrontendDir
        $env:NEXUS_LOCAL_API_BASE_URL = $ApiBaseUrl
        $env:NEXUS_RUNTIME_CONFIG_LOCAL = '1'
        & node 'scripts/write-runtime-config.mjs' '--local'
        if ($LASTEXITCODE -ne 0) {
            throw 'Writing frontend runtime config failed.'
        }
    } finally {
        Pop-Location
        $env:NEXUS_LOCAL_API_BASE_URL = $previousApiBase
        $env:NEXUS_RUNTIME_CONFIG_LOCAL = $previousRuntimeLocal
    }
}

function Start-DevProcess($Title, $WorkingDirectory, $Command) {
    $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) {
        $pwsh = (Get-Command powershell).Source
    }

    $safeTitle = ConvertTo-SingleQuotedPowerShellString $Title
    return Start-Process -FilePath $pwsh -WorkingDirectory $WorkingDirectory -ArgumentList @(
        '-NoProfile',
        '-NoExit',
        '-ExecutionPolicy', 'Bypass',
        '-Command',
        "`$Host.UI.RawUI.WindowTitle = $safeTitle; $Command"
    ) -PassThru
}

function Wait-HttpEndpoint($Label, $Url, [int]$TimeoutSeconds) {
    if ($TimeoutSeconds -le 0) {
        return $true
    }

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastError = $null

    Write-Host "Waiting for ${Label}: $Url"
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
                Write-Host "$Label is ready." -ForegroundColor Green
                return $true
            }
            $lastError = "HTTP $($response.StatusCode)"
        } catch {
            $lastError = $_.Exception.Message
        }
        Start-Sleep -Seconds 2
    }

    Write-Warning "$Label did not become ready within $TimeoutSeconds seconds."
    if ($lastError) {
        Write-Warning "Last $Label check: $lastError"
    }
    return $false
}

if ($Help) {
    Show-DevHelp
    return
}

Assert-PathExists $BackendDir 'Backend directory'
Assert-PathExists $FrontendDir 'Frontend directory'
Assert-PathExists $BackendEntry 'Backend entry'
Assert-PathExists $FrontendPackage 'Frontend package manifest'
Assert-PathExists $InstallScript 'Dependency installer'

$BackendPort = Get-FreePort $BackendPort 'Backend'
$FrontendPort = Get-FreePort $FrontendPort 'Frontend'

$ApiBaseUrl = "http://127.0.0.1:$BackendPort/api/v1"
$FrontendUrl = "http://127.0.0.1:$FrontendPort"
$BackendHealthUrl = "$ApiBaseUrl/health/live"

if ($Docker) {
    $composeVersion = Assert-DockerComposeReady
    Assert-DockerComposeConfig

    $env:BACKEND_PORT = [string]$BackendPort
    $env:FRONTEND_PORT = [string]$FrontendPort
    $env:FRONTEND_ORIGIN = $FrontendUrl
    $env:CORS_ORIGINS = "http://localhost:$FrontendPort,http://127.0.0.1:$FrontendPort"
    $env:NEXUS_API_BASE_URL = $ApiBaseUrl
    $env:NEXUS_SENTRY_DSN = Get-FirstEnv @('NEXUS_SENTRY_DSN', 'SENTRY_DSN')
    $env:NEXUS_SENTRY_ENVIRONMENT = Get-FirstEnv @('NEXUS_SENTRY_ENVIRONMENT', 'NODE_ENV') 'local'
    $env:NEXUS_SENTRY_RELEASE = Get-FirstEnv @('NEXUS_SENTRY_RELEASE', 'VERCEL_GIT_COMMIT_SHA')
    $env:NEXUS_SENTRY_TRACES_SAMPLE_RATE = Get-FirstEnv @('NEXUS_SENTRY_TRACES_SAMPLE_RATE') '0'

    if ($CheckOnly) {
        Write-Host 'NEXUS Docker startup check passed.' -ForegroundColor Green
        Write-Host "Compose     : $composeVersion"
        Write-Host "Compose file: $ComposeFile"
        Write-Host "Backend API : $ApiBaseUrl"
        Write-Host "Frontend SPA: $FrontendUrl"
        Write-Host 'No containers were started because -CheckOnly was provided.'
        return
    }

    $composeArgs = @('compose', '--project-directory', $Root, '--file', $ComposeFile, 'up', '-d')
    if ($Build) {
        $composeArgs += '--build'
    }
    & docker @composeArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'docker compose up failed.'
    }

    if ($NoWait) {
        Write-Host 'Readiness waiting skipped because -NoWait was provided.' -ForegroundColor Yellow
    } else {
        Wait-HttpEndpoint 'Backend API' $BackendHealthUrl $StartupTimeoutSeconds | Out-Null
        Wait-HttpEndpoint 'Frontend SPA' $FrontendUrl $StartupTimeoutSeconds | Out-Null
    }

    if (-not $NoOpen -and -not $NoWait) {
        Start-Process $FrontendUrl
    }

    Write-Host ''
    Write-Host 'NEXUS Docker dev stack is running.' -ForegroundColor Green
    Write-Host "Backend API : $ApiBaseUrl"
    Write-Host "Frontend SPA: $FrontendUrl"
    Write-Host 'Services    : postgres, redis, backend, worker, beat, frontend'
    Write-Host 'Logs        : docker compose logs -f'
    Write-Host 'Stop        : docker compose down'
    return
}

if ($CheckOnly) {
    $issues = Test-DevPrerequisites
    if ($issues.Count -gt 0) {
        Write-Host 'NEXUS dev startup check failed:' -ForegroundColor Red
        foreach ($issue in $issues) {
            Write-Host " - $issue"
        }
        Write-Host ''
        Write-Host 'Run .\scripts\dev.ps1 -Install to restore missing dependencies.' -ForegroundColor Yellow
        exit 1
    }

    Write-Host 'NEXUS dev startup check passed.' -ForegroundColor Green
    Write-Host "Backend API : $ApiBaseUrl"
    Write-Host "Frontend SPA: $FrontendUrl"
    Write-Host "Health probe: $BackendHealthUrl"
    Write-Host "Start cmd   : .\scripts\dev.ps1 -BackendPort $BackendPort -FrontendPort $FrontendPort"
    Write-Host 'No servers were started because -CheckOnly was provided.'
    return
}

Assert-CommandExists 'npm' 'Install Node.js LTS and reopen this terminal.'

if ($ResetWorkspace) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $CleanScript -StopDevServers
    if ($LASTEXITCODE -ne 0) {
        throw 'Workspace cleanup failed.'
    }
}

if ($Install -or -not (Test-Path $Python) -or -not (Test-Path $NodeModules)) {
    if ($NoInstall) {
        throw 'Dependencies are missing and -NoInstall was provided. Run .\scripts\dev.ps1 -Install first.'
    }

    $installArgs = @()
    if ($Install) {
        $installArgs += '-Force'
    }
    & powershell -NoProfile -ExecutionPolicy Bypass -File $InstallScript @installArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'Dependency installation failed.'
    }
}

if ($Seed) {
    Push-Location $BackendDir
    try {
        $env:FLASK_APP = 'run.py'
        & $Python -m flask seed-enterprise --scale 3 --multiplier $SeedMultiplier --reset --seed 20241334
        if ($LASTEXITCODE -ne 0) {
            throw 'Enterprise seed failed.'
        }
        & $Python -m flask status
        if ($LASTEXITCODE -ne 0) {
            throw 'Backend status check failed after seeding.'
        }
    } finally {
        Pop-Location
    }
}

Write-RuntimeConfig $ApiBaseUrl

$corsOrigins = "http://localhost:$FrontendPort,http://127.0.0.1:$FrontendPort,http://localhost:4200,http://127.0.0.1:4200"
$backendCommand = "`$env:FLASK_APP='run.py'; `$env:FLASK_ENV='development'; `$env:FLASK_CONFIG='development'; `$env:PYTHONUNBUFFERED='1'; `$env:PORT='$BackendPort'; `$env:FRONTEND_ORIGIN='$FrontendUrl'; `$env:CORS_ORIGINS='$corsOrigins'; & $(ConvertTo-SingleQuotedPowerShellString $Python) run.py"
$frontendCommand = "`$env:NEXUS_API_BASE_URL='$ApiBaseUrl'; `$env:NEXUS_LOCAL_API_BASE_URL='$ApiBaseUrl'; `$env:NEXUS_RUNTIME_CONFIG_LOCAL='1'; npm start -- --host 127.0.0.1 --port $FrontendPort"

$backendProcess = Start-DevProcess "NEXUS Backend API :$BackendPort" $BackendDir $backendCommand
Start-Sleep -Seconds 2
$frontendProcess = Start-DevProcess "NEXUS Angular SPA :$FrontendPort" $FrontendDir $frontendCommand

if ($NoWait) {
    $backendReady = $true
    $frontendReady = $true
    Write-Host 'Readiness waiting skipped because -NoWait was provided.' -ForegroundColor Yellow
} else {
    $backendReady = Wait-HttpEndpoint 'Backend API' $BackendHealthUrl $StartupTimeoutSeconds
    $frontendReady = Wait-HttpEndpoint 'Frontend SPA' $FrontendUrl $StartupTimeoutSeconds
}

if (-not $NoOpen -and -not $NoWait -and $frontendReady) {
    Start-Process $FrontendUrl
}

Write-Host ''
Write-Host 'NEXUS dev servers are starting...' -ForegroundColor Green
Write-Host "Backend API : $ApiBaseUrl"
Write-Host "Frontend SPA: $FrontendUrl"
Write-Host "Runtime cfg : frontend/public/runtime-config.js -> $ApiBaseUrl"
Write-Host "Backend PID : $($backendProcess.Id)"
Write-Host "Frontend PID: $($frontendProcess.Id)"
if ($Seed) {
    Write-Host "Data        : initialized with scale 3 x $SeedMultiplier, seed 20241334"
}
if ($NoOpen) {
    Write-Host 'Browser    : skipped because -NoOpen was provided'
} elseif ($NoWait) {
    Write-Host 'Browser    : skipped because -NoWait was provided'
} elseif (-not $frontendReady) {
    Write-Host 'Browser    : not opened because the frontend did not become ready in time'
} else {
    Write-Host 'Browser    : opening automatically'
}
if (-not $backendReady) {
    Write-Host 'Backend    : still starting or unhealthy; check the backend window for details' -ForegroundColor Yellow
}
Write-Host ''
Write-Host 'Edit backend/*.py or frontend/src/* files, then refresh the browser. Angular will hot reload automatically.'
