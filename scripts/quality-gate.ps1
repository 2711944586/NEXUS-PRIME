param(
    [switch]$SkipDocx,
    [switch]$SkipDataAudit,
    [switch]$SkipBackendTests,
    [switch]$SkipFrontendTests,
    [switch]$SkipBuild,
    [switch]$SkipApiContractAudit,
    [switch]$SkipChartAudit,
    [switch]$SkipShellAudit,
    [switch]$SkipLayoutAudit,
    [switch]$SkipDeploymentReadinessAudit,
    [switch]$SkipPreflight,
    [switch]$SkipDeliveryAssets,
    [switch]$NoInstall,
    [switch]$KeepDevServers
)

$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$BackendDir = Join-Path $Root 'backend'
$FrontendDir = Join-Path $Root 'frontend'
$Python = Join-Path $Root 'venv\Scripts\python.exe'
$NodeModules = Join-Path $FrontendDir 'node_modules'
$InstallScript = Join-Path $Root 'scripts\install-dependencies.ps1'
$OutputDir = Join-Path $Root 'output\quality-gate'
$StartedProcesses = New-Object System.Collections.Generic.List[System.Diagnostics.Process]
$RuntimeConfigTouched = $false

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

function Get-PowerShellExecutable {
    $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
    if ($pwsh) {
        return $pwsh
    }
    $windowsPowerShell = (Get-Command powershell -ErrorAction SilentlyContinue).Source
    if ($windowsPowerShell) {
        return $windowsPowerShell
    }
    throw 'PowerShell is required to run quality gate helper scripts.'
}

function Step($Message) {
    Write-Host ''
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Check-Toolchain {
    Step 'Toolchain'
    if ((-not (Test-Path $Python) -or -not (Test-Path $NodeModules)) -and -not $NoInstall) {
        & (Get-PowerShellExecutable) -ExecutionPolicy Bypass -File $InstallScript
        if ($LASTEXITCODE -ne 0) {
            throw 'Dependency installation failed.'
        }
    }
    if (-not (Test-Path $Python)) {
        throw 'Python virtual environment is missing. Run scripts/install-dependencies.ps1.'
    }
    if (-not (Test-Path $NodeModules)) {
        throw 'frontend/node_modules is missing. Run scripts/install-dependencies.ps1.'
    }
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw 'npm is required.'
    }
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        throw 'node is required.'
    }
    Write-Host 'OK  local Python and Node dependencies are available' -ForegroundColor Green
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [hashtable]$Environment = @{}
    )

    $display = "$FilePath $($Arguments -join ' ')"
    Write-Host $display -ForegroundColor DarkGray
    $oldEnvironment = @{}
    foreach ($key in $Environment.Keys) {
        $oldEnvironment[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
        [Environment]::SetEnvironmentVariable($key, [string]$Environment[$key], 'Process')
    }
    Push-Location $WorkingDirectory
    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code $LASTEXITCODE`: $display"
        }
    } finally {
        Pop-Location
        foreach ($key in $Environment.Keys) {
            [Environment]::SetEnvironmentVariable($key, $oldEnvironment[$key], 'Process')
        }
    }
}

function Test-Port([int]$Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Test-Http($Url) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 3
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    } catch {
        return $false
    }
}

function Get-FreePort([int]$PreferredPort, [int]$MaxTries = 40) {
    for ($port = $PreferredPort; $port -lt ($PreferredPort + $MaxTries); $port++) {
        if (-not (Test-Port $port)) {
            return $port
        }
    }
    throw "No free port found from $PreferredPort to $($PreferredPort + $MaxTries - 1)."
}

function Wait-Http {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSeconds = 120
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Http $Url) {
            return
        }
        Start-Sleep -Seconds 2
    }
    throw "Timed out waiting for $Url"
}

function Start-QualityProcess {
    param(
        [Parameter(Mandatory = $true)][string]$Title,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$Command
    )

    $pwsh = Get-PowerShellExecutable
    $process = Start-Process -FilePath $pwsh -WorkingDirectory $WorkingDirectory -PassThru -WindowStyle Hidden -ArgumentList @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-Command',
        "`$Host.UI.RawUI.WindowTitle = '$Title'; $Command"
    )
    $StartedProcesses.Add($process) | Out-Null
    return $process
}

function Get-ChildProcessIds([int]$ParentId) {
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ParentId" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        Get-ChildProcessIds ([int]$child.ProcessId)
        [int]$child.ProcessId
    }
}

function Stop-StartedProcesses {
    if ($KeepDevServers) {
        Write-Host 'kept quality-gate dev servers because -KeepDevServers was provided' -ForegroundColor Yellow
        return
    }
    foreach ($process in $StartedProcesses) {
        $ids = @(Get-ChildProcessIds $process.Id) + @($process.Id)
        foreach ($id in $ids | Select-Object -Unique) {
            Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
        }
    }
}

function Restore-RuntimeConfig {
    param([switch]$Force)
    if ((-not $Force -and -not $script:RuntimeConfigTouched) -or $KeepDevServers) {
        return
    }
    $runtimeConfig = Join-Path $FrontendDir 'public\runtime-config.js'
    $runtimeConfigContent = @"
window.NEXUS_RUNTIME_CONFIG = {
  apiBaseUrl: ''
};
"@
    Set-Content -LiteralPath $runtimeConfig -Value $runtimeConfigContent -Encoding UTF8
    Write-Host 'restored frontend/public/runtime-config.js to environment fallback' -ForegroundColor DarkGray
}

function Ensure-LayoutServers {
    $backendPort = Get-FreePort 5000
    $frontendPort = Get-FreePort 4200

    $runtimeConfig = Join-Path $FrontendDir 'public\runtime-config.js'
    $runtimeConfigContent = @"
window.NEXUS_RUNTIME_CONFIG = {
  apiBaseUrl: 'http://127.0.0.1:$backendPort/api/v1'
};
"@
    Set-Content -LiteralPath $runtimeConfig -Value $runtimeConfigContent -Encoding UTF8
    $script:RuntimeConfigTouched = $true

    $backendLog = Join-Path $OutputDir "backend-$backendPort.log"
    $corsOrigins = "http://localhost:$frontendPort,http://127.0.0.1:$frontendPort,http://localhost:4200,http://127.0.0.1:4200"
    $backendCommand = "`$env:FLASK_ENV='development'; `$env:PORT='$backendPort'; `$env:CORS_ORIGINS='$corsOrigins'; & '$Python' run.py *> '$backendLog'"
    Start-QualityProcess "NEXUS Quality Backend :$backendPort" $BackendDir $backendCommand | Out-Null
    Wait-Http "http://127.0.0.1:$backendPort/api/v1/health" 90

    $frontendLog = Join-Path $OutputDir "frontend-$frontendPort.log"
    $frontendCommand = "`$env:NEXUS_API_BASE_URL='http://127.0.0.1:$backendPort/api/v1'; npm start -- --host 127.0.0.1 --port $frontendPort *> '$frontendLog'"
    Start-QualityProcess "NEXUS Quality Frontend :$frontendPort" $FrontendDir $frontendCommand | Out-Null
    Wait-Http "http://127.0.0.1:$frontendPort/auth/login" 180

    return "http://127.0.0.1:$frontendPort"
}

function Set-PreflightEnvironment {
    $env:NEXUS_API_BASE_URL = 'https://nexus-prime-api.vercel.app/api/v1'
    $env:FRONTEND_ORIGIN = 'https://nexus-prime-web.vercel.app'
    $env:CORS_ORIGINS = $env:FRONTEND_ORIGIN
    $env:DATABASE_URL = 'postgresql://postgres.project-ref:password@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require'
    $env:AUTH_COOKIE_SECURE = 'true'
    $env:AUTH_COOKIE_SAMESITE = 'None'
    $env:SESSION_COOKIE_SECURE = 'true'
    $env:SESSION_COOKIE_SAMESITE = 'None'
    $env:SECRET_KEY = 'quality-gate-local-preflight-secret-32-characters'
    $env:CLOUDINARY_URL = 'cloudinary://api_key:api_secret@cloud_name'
    $env:CACHE_TYPE = 'RedisCache'
    $env:REDIS_URL = 'redis://quality-gate-cache.example.com:6379/0'
    $env:CACHE_REDIS_URL = $env:REDIS_URL
    $env:AI_API_KEY = 'quality-gate-placeholder-ai-key'
    $env:AI_BASE_URL = 'https://api.deepseek.com'
    $env:AI_MODEL = 'deepseek-chat'
}

try {
    Check-Toolchain

    if (-not $SkipDocx) {
        Step 'Generate final DOCX report'
        Invoke-Checked $Python @('scripts\generate_final_report_docx.py') $Root
    }

    if (-not $SkipDataAudit) {
        Step 'Backend data coverage'
        Invoke-Checked $Python @('-m', 'flask', 'status') $BackendDir @{ FLASK_APP = 'run.py' }
        Invoke-Checked $Python @('-m', 'flask', 'audit-enterprise-data', '--strict') $BackendDir @{ FLASK_APP = 'run.py' }
    }

    if (-not $SkipBackendTests) {
        Step 'Backend tests'
        Invoke-Checked $Python @('-m', 'pytest', '-q') $BackendDir @{ FLASK_APP = 'run.py' }
    }

    if (-not $SkipFrontendTests) {
        Step 'Frontend tests'
        Invoke-Checked 'npm' @('test', '--', '--watch=false') $FrontendDir
    }

    if (-not $SkipBuild) {
        Step 'Frontend production build'
        Invoke-Checked 'npm' @('run', 'build') $FrontendDir
    }

    if (-not $SkipApiContractAudit) {
        Step 'Frontend/backend API contract audit'
        $reportPath = Join-Path $OutputDir 'api-contracts.json'
        Invoke-Checked $Python @('scripts\audit-api-contracts.py', '--json-output', $reportPath) $Root
    }

    if (-not $SkipChartAudit) {
        Step 'Frontend chart audit'
        Invoke-Checked 'npm' @('run', 'audit:charts') $FrontendDir
    }

    if (-not $SkipShellAudit -or -not $SkipLayoutAudit -or -not $SkipDeploymentReadinessAudit) {
        Step 'Frontend layout audit'
        $frontendBaseUrl = Ensure-LayoutServers
        if (-not $SkipShellAudit) {
            Step 'Frontend shell interaction audit'
            Invoke-Checked 'npm' @('run', 'audit:shell') $FrontendDir @{ NEXUS_AUDIT_BASE_URL = $frontendBaseUrl }
        }
        if (-not $SkipLayoutAudit) {
            Invoke-Checked 'npm' @('run', 'audit:layout') $FrontendDir @{ NEXUS_AUDIT_BASE_URL = $frontendBaseUrl }
        }
        if (-not $SkipDeploymentReadinessAudit) {
            Step 'Deployment readiness and ERP maturity audit'
            Invoke-Checked 'npm' @('run', 'audit:deployment-readiness') $FrontendDir @{ NEXUS_AUDIT_BASE_URL = $frontendBaseUrl }
        }
        Restore-RuntimeConfig
    }

    if (-not $SkipPreflight) {
        Step 'Deployment preflight'
        Set-PreflightEnvironment
        Invoke-Checked (Get-PowerShellExecutable) @(
            '-ExecutionPolicy', 'Bypass',
            '-File', (Join-Path $Root 'scripts\preflight.ps1'),
            '-SkipApiProbe',
            '-SkipBuild',
            '-SkipBackendTests'
        ) $Root
    }

    Restore-RuntimeConfig -Force

    if (-not $SkipDeliveryAssets) {
        Step 'Delivery assets audit'
        $reportPath = Join-Path $OutputDir 'delivery-assets.json'
        Invoke-Checked $Python @('scripts\audit-delivery-assets.py', '--json-output', $reportPath) $Root
    }

    Write-Host ''
    Write-Host 'Quality gate passed.' -ForegroundColor Green
} finally {
    Stop-StartedProcesses
    Restore-RuntimeConfig
}
