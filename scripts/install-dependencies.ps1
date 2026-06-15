param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$BackendDir = Join-Path $Root 'backend'
$FrontendDir = Join-Path $Root 'frontend'
$VenvDir = Join-Path $Root 'venv'
$Python = Join-Path $VenvDir 'Scripts\python.exe'
$NodeModules = Join-Path $FrontendDir 'node_modules'

function Test-Command($Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-BootstrapPython {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return @($py.Source, '-3')
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return @($python.Source)
    }

    throw 'Python launcher not found. Install Python 3.11+ or ensure py/python is on PATH.'
}

if (-not (Test-Path $Python)) {
    Write-Host "Creating Python virtual environment at $VenvDir ..." -ForegroundColor Yellow
    $bootstrap = Get-BootstrapPython
    if ($bootstrap.Count -gt 1) {
        & $bootstrap[0] $bootstrap[1] -m venv $VenvDir
    } else {
        & $bootstrap[0] -m venv $VenvDir
    }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Python)) {
        throw "Failed to create Python virtual environment at $Python"
    }
}

if ($Force -or -not (& $Python -m pip show Flask 2>$null)) {
    Push-Location $BackendDir
    try {
        & $Python -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) {
            throw 'Backend dependency installation failed.'
        }
    } finally {
        Pop-Location
    }
}

if (-not (Test-Command 'npm')) {
    throw 'npm not found. Install Node.js LTS first.'
}

if ($Force -or -not (Test-Path $NodeModules)) {
    Push-Location $FrontendDir
    try {
        npm install
        if ($LASTEXITCODE -ne 0) {
            throw 'Frontend dependency installation failed.'
        }
    } finally {
        Pop-Location
    }
}

Write-Host 'Dependencies are ready.' -ForegroundColor Green
