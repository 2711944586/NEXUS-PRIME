param(
    [Parameter(Mandatory = $true)]
    [string]$DatabaseUrl,

    [Parameter(Mandatory = $true)]
    [string]$BackendProjectName,

    [Parameter(Mandatory = $true)]
    [string]$FrontendProjectName,

    [string]$ApiBaseUrl,
    [string]$FrontendOrigin,
    [string]$VercelTeam,
    [string]$VercelToken = $env:VERCEL_TOKEN,
    [string]$SecretKey = $env:SECRET_KEY,
    [string]$CorsOrigins,
    [string]$AiApiKey = $(if ($env:AI_API_KEY) { $env:AI_API_KEY } elseif ($env:OPENAI_API_KEY) { $env:OPENAI_API_KEY } else { $env:DEEPSEEK_API_KEY }),
    [string]$AiBaseUrl = $(if ($env:AI_BASE_URL) { $env:AI_BASE_URL } elseif ($env:OPENAI_BASE_URL) { $env:OPENAI_BASE_URL } elseif ($env:DEEPSEEK_BASE_URL) { $env:DEEPSEEK_BASE_URL } else { 'https://api.deepseek.com' }),
    [string]$AiModel = $(if ($env:AI_MODEL) { $env:AI_MODEL } elseif ($env:OPENAI_MODEL) { $env:OPENAI_MODEL } elseif ($env:DEEPSEEK_MODEL) { $env:DEEPSEEK_MODEL } else { 'deepseek-chat' }),
    [string]$DeepseekApiKey = $env:DEEPSEEK_API_KEY,
    [string]$DeepseekBaseUrl = $(if ($env:DEEPSEEK_BASE_URL) { $env:DEEPSEEK_BASE_URL } else { 'https://api.deepseek.com' }),
    [string]$DeepseekModel = $(if ($env:DEEPSEEK_MODEL) { $env:DEEPSEEK_MODEL } else { 'deepseek-chat' }),
    [string]$CloudinaryUrl = $env:CLOUDINARY_URL,
    [string]$RedisUrl = $(if ($env:CACHE_REDIS_URL) { $env:CACHE_REDIS_URL } elseif ($env:REDIS_URL) { $env:REDIS_URL } else { $env:UPSTASH_REDIS_URL }),
    [string]$DemoAdminPassword = $env:NEXUS_DEMO_ADMIN_PASSWORD,
    [string]$DemoUserPassword = $env:NEXUS_DEMO_USER_PASSWORD,
    [string]$SourceSqlite = $(Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..')) 'backend\instance\nexus_prime.db'),
    [int]$SeedMultiplier = 300,
    [switch]$SyncDatabase,
    [switch]$ResetRemoteDatabase,
    [switch]$SeedRemoteWhenEmpty,
    [switch]$ResetAndSeedRemote,
    [switch]$SkipPreflight,
    [switch]$SkipTests,
    [switch]$SkipMigrations,
    [switch]$SkipDataVerify,
    [switch]$SkipBackendDeploy,
    [switch]$SkipFrontendDeploy,
    [switch]$SkipVercelEnv,
    [switch]$SkipApiProbe
)

$ErrorActionPreference = 'Stop'

$Root = Resolve-Path (Join-Path $PSScriptRoot '..')
$BackendDir = Join-Path $Root 'backend'
$FrontendDir = Join-Path $Root 'frontend'
$Python = Join-Path $Root 'venv\Scripts\python.exe'
$NodeModules = Join-Path $FrontendDir 'node_modules'
$InstallScript = Join-Path $Root 'scripts\install-dependencies.ps1'

if (-not $ApiBaseUrl) {
    $ApiBaseUrl = "https://$BackendProjectName.vercel.app/api/v1"
}
if (-not $FrontendOrigin) {
    $FrontendOrigin = "https://$FrontendProjectName.vercel.app"
}
if (-not $CorsOrigins) {
    $CorsOrigins = $FrontendOrigin
}
if (-not $DeepseekApiKey) {
    $DeepseekApiKey = $AiApiKey
}
if (-not $DeepseekBaseUrl) {
    $DeepseekBaseUrl = $AiBaseUrl
}
if (-not $DeepseekModel) {
    $DeepseekModel = $AiModel
}

function Step($Message) {
    Write-Host ''
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Check($Condition, $Message) {
    if (-not $Condition) {
        throw $Message
    }
}

function Redact-SecretText([string]$Value) {
    if (-not $Value) {
        return $Value
    }

    $redacted = $Value
    $redacted = [regex]::Replace($redacted, '(?i)(postgres(?:ql)?://[^:/\s]+:)[^@\s]+(@)', '$1<redacted>$2')
    $redacted = [regex]::Replace($redacted, '(?i)(cloudinary://[^:/\s]+:)[^@\s]+(@)', '$1<redacted>$2')
    $redacted = [regex]::Replace($redacted, '(?i)(token=)[^&\s]+', '$1<redacted>')
    $redacted = [regex]::Replace($redacted, '(?i)(password=)[^&\s]+', '$1<redacted>')
    return $redacted
}

function Format-CommandForLog {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $sensitiveNext = $false
    $formatted = @()
    foreach ($argument in $Arguments) {
        if ($sensitiveNext) {
            $formatted += '<redacted>'
            $sensitiveNext = $false
            continue
        }

        if ($argument -in @('--token', '--target') -or $argument -match '^(?i)-(SecretKey|CloudinaryUrl|DatabaseUrl|DemoAdminPassword|DemoUserPassword|AiApiKey|DeepseekApiKey|RedisUrl)$') {
            $formatted += $argument
            $sensitiveNext = $true
            continue
        }

        if ($argument -match '^(?i)(NEXUS_API_BASE_URL|DATABASE_URL|SECRET_KEY|CLOUDINARY_URL|AI_API_KEY|DEEPSEEK_API_KEY|VERCEL_TOKEN|REDIS_URL|CACHE_REDIS_URL|UPSTASH_REDIS_URL)=') {
            $name, $value = $argument.Split('=', 2)
            $formatted += "$name=$(Redact-SecretText $value)"
            continue
        }

        $formatted += (Redact-SecretText $argument)
    }

    return "$FilePath $($formatted -join ' ')"
}

function Invoke-CommandChecked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )

    $display = Format-CommandForLog -FilePath $FilePath -Arguments $Arguments
    Write-Host $display -ForegroundColor DarkGray
    Push-Location $WorkingDirectory
    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code $LASTEXITCODE`: $display"
        }
    } finally {
        Pop-Location
    }
}

function Invoke-CommandWithInput {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$InputText,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )

    $display = Format-CommandForLog -FilePath $FilePath -Arguments $Arguments
    Write-Host $display -ForegroundColor DarkGray
    Push-Location $WorkingDirectory
    try {
        $InputText | & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code $LASTEXITCODE`: $display"
        }
    } finally {
        Pop-Location
    }
}

function VercelArgs {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )

    $args = @('--yes', 'vercel') + $Arguments + @('--cwd', $WorkingDirectory)
    if ($VercelTeam) {
        $args += @('--scope', $VercelTeam)
    }
    if ($VercelToken) {
        $args += @('--token', $VercelToken)
    }
    return [string[]]$args
}

function Invoke-Vercel {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )

    Invoke-CommandChecked -FilePath 'npx' -Arguments (VercelArgs -Arguments $Arguments -WorkingDirectory $WorkingDirectory) -WorkingDirectory $Root
}

function Set-VercelEnv($ProjectDir, $Name, $Value) {
    if (-not $Value) {
        return
    }
    $args = @('env', 'add', $Name, 'production', '--force', '--yes')
    if ($Name -match 'KEY|SECRET|TOKEN|DATABASE_URL|CLOUDINARY|PASSWORD|REDIS_URL') {
        $args += '--sensitive'
    } else {
        $args += '--no-sensitive'
    }
    Invoke-CommandWithInput -FilePath 'npx' -Arguments (VercelArgs -Arguments $args -WorkingDirectory $ProjectDir) -InputText $Value -WorkingDirectory $Root
}

function Link-VercelProject($ProjectDir, $ProjectName) {
    $args = @('link', '--yes', '--project', $ProjectName)
    if ($VercelTeam) {
        $args += @('--team', $VercelTeam)
    }
    Invoke-Vercel -Arguments $args -WorkingDirectory $ProjectDir
}

Step 'Validate local toolchain and deployment inputs'
Check (Test-Path $BackendDir) 'backend/ directory not found.'
Check (Test-Path $FrontendDir) 'frontend/ directory not found.'
if (-not (Test-Path $Python) -or -not (Test-Path $NodeModules)) {
    Invoke-CommandChecked -FilePath 'powershell' -Arguments @('-ExecutionPolicy', 'Bypass', '-File', $InstallScript) -WorkingDirectory $Root
}
Check (Test-Path $Python) 'Python virtual environment not found at venv/Scripts/python.exe.'
Check ([bool](Get-Command node -ErrorAction SilentlyContinue)) 'Node.js is required.'
Check ([bool](Get-Command npm -ErrorAction SilentlyContinue)) 'npm is required.'
Check ([bool](Get-Command npx -ErrorAction SilentlyContinue)) 'npx is required.'
Check ($DatabaseUrl -match '^postgres(ql)?://') 'DATABASE_URL must be a PostgreSQL connection string.'
Check ($DatabaseUrl -match 'supabase\.com|pooler\.supabase\.com') 'DATABASE_URL must point to Supabase.'
Check ($DatabaseUrl -match 'sslmode=require') 'DATABASE_URL must include sslmode=require.'
Check ($ApiBaseUrl -match '^https://.+/api/v1/?$') 'ApiBaseUrl must use HTTPS and end with /api/v1.'
Check ($FrontendOrigin -match '^https://[^ ]+$') 'FrontendOrigin must use HTTPS.'
Check ([bool]$SecretKey -and $SecretKey.Length -ge 32) 'SecretKey must be at least 32 characters. Set SECRET_KEY or pass -SecretKey.'
if (-not $SkipBackendDeploy) {
    Check ([bool]$CloudinaryUrl) 'CloudinaryUrl is required for persistent avatars and files on Vercel. Set CLOUDINARY_URL or pass -CloudinaryUrl.'
    Check ([bool]$RedisUrl -and $RedisUrl -match '^rediss?://') 'RedisUrl is required for shared production login rate limits. Set REDIS_URL/CACHE_REDIS_URL/UPSTASH_REDIS_URL or pass -RedisUrl.'
}
if ($SyncDatabase) {
    Check (Test-Path $SourceSqlite) "SQLite source database not found: $SourceSqlite"
}
if ($SeedRemoteWhenEmpty -or $ResetAndSeedRemote) {
    Check ([bool]$DemoAdminPassword -and $DemoAdminPassword.Length -ge 12) 'DemoAdminPassword must be at least 12 characters when seeding a remote database. Set NEXUS_DEMO_ADMIN_PASSWORD or pass -DemoAdminPassword.'
    Check ([bool]$DemoUserPassword -and $DemoUserPassword.Length -ge 12) 'DemoUserPassword must be at least 12 characters when seeding a remote database. Set NEXUS_DEMO_USER_PASSWORD or pass -DemoUserPassword.'
    Check ($DemoAdminPassword -ne 'admin123') 'DemoAdminPassword must not use the local demo default admin123.'
    Check ($DemoUserPassword -ne 'password123') 'DemoUserPassword must not use the local demo default password123.'
}

$env:NEXUS_API_BASE_URL = $ApiBaseUrl
$env:FRONTEND_ORIGIN = $FrontendOrigin
$env:CORS_ORIGINS = $CorsOrigins
$env:DATABASE_URL = $DatabaseUrl
$env:AUTH_COOKIE_SECURE = 'true'
$env:AUTH_COOKIE_SAMESITE = 'None'
$env:SESSION_COOKIE_SECURE = 'true'
$env:SESSION_COOKIE_SAMESITE = 'None'
$env:SECRET_KEY = $SecretKey
$env:FLASK_ENV = 'production'
$env:FLASK_CONFIG = 'production'
$env:AI_API_KEY = $AiApiKey
$env:AI_BASE_URL = $AiBaseUrl
$env:AI_MODEL = $AiModel
$env:CLOUDINARY_URL = $CloudinaryUrl
$env:REDIS_URL = $RedisUrl
$env:CACHE_TYPE = 'RedisCache'
$env:CACHE_REDIS_URL = $RedisUrl
$env:REQUIRE_CLOUD_STORAGE_FOR_UPLOADS = 'auto'
$env:NEXUS_DEMO_ADMIN_PASSWORD = $DemoAdminPassword
$env:NEXUS_DEMO_USER_PASSWORD = $DemoUserPassword

if (-not $SkipPreflight) {
    Step 'Run deployment preflight'
    $preflightArgs = @()
    if ($SkipTests) {
        $preflightArgs += '-SkipBackendTests'
    }
    if ($SkipApiProbe) {
        $preflightArgs += '-SkipApiProbe'
    }
    Invoke-CommandChecked -FilePath 'powershell' -Arguments (@('-ExecutionPolicy', 'Bypass', '-File', (Join-Path $Root 'scripts\preflight.ps1')) + $preflightArgs) -WorkingDirectory $Root
}

if (-not $SkipMigrations) {
    Step 'Upgrade Supabase schema'
    Invoke-CommandChecked -FilePath $Python -Arguments @('-m', 'flask', 'db', 'upgrade') -WorkingDirectory $BackendDir
}

if ($SyncDatabase) {
    Step 'Sync local SQLite data to Supabase PostgreSQL'
    $syncArgs = @(
        (Join-Path $BackendDir 'scripts\sync_sqlite_to_postgres.py'),
        '--source', $SourceSqlite,
        '--target', $DatabaseUrl,
        '--require-supabase'
    )
    if ($ResetRemoteDatabase) {
        $syncArgs += '--reset-target'
    }
    Invoke-CommandChecked -FilePath $Python -Arguments $syncArgs -WorkingDirectory $BackendDir
}

if ($SeedRemoteWhenEmpty) {
    Step 'Seed remote database only when empty'
    Invoke-CommandChecked -FilePath $Python -Arguments @(
        (Join-Path $BackendDir 'scripts\database_state.py'),
        '--url', $DatabaseUrl,
        '--require-empty'
    ) -WorkingDirectory $BackendDir
    Invoke-CommandChecked -FilePath $Python -Arguments @(
        '-m', 'flask', 'seed-enterprise',
        '--scale', '3',
        '--multiplier', "$SeedMultiplier",
        '--seed', '20241334'
    ) -WorkingDirectory $BackendDir
}

if ($ResetAndSeedRemote) {
    Step 'Reset and seed remote database by explicit request'
    Invoke-CommandChecked -FilePath $Python -Arguments @(
        '-m', 'flask', 'seed-enterprise',
        '--scale', '3',
        '--multiplier', "$SeedMultiplier",
        '--reset',
        '--seed', '20241334'
    ) -WorkingDirectory $BackendDir
}

if (-not $SkipDataVerify) {
    Step 'Verify Supabase business data'
    Invoke-CommandChecked -FilePath $Python -Arguments @('-m', 'flask', 'status') -WorkingDirectory $BackendDir
    Invoke-CommandChecked -FilePath $Python -Arguments @('-m', 'flask', 'audit-enterprise-data', '--strict') -WorkingDirectory $BackendDir
}

if (-not $SkipBackendDeploy) {
    Step 'Deploy backend API to Vercel'
    Link-VercelProject $BackendDir $BackendProjectName
    if (-not $SkipVercelEnv) {
        Set-VercelEnv $BackendDir 'FLASK_ENV' 'production'
        Set-VercelEnv $BackendDir 'FLASK_CONFIG' 'production'
        Set-VercelEnv $BackendDir 'DATABASE_URL' $DatabaseUrl
        Set-VercelEnv $BackendDir 'SECRET_KEY' $SecretKey
        Set-VercelEnv $BackendDir 'CORS_ORIGINS' $CorsOrigins
        Set-VercelEnv $BackendDir 'FRONTEND_ORIGIN' $FrontendOrigin
        Set-VercelEnv $BackendDir 'AUTH_COOKIE_SECURE' 'true'
        Set-VercelEnv $BackendDir 'AUTH_COOKIE_SAMESITE' 'None'
        Set-VercelEnv $BackendDir 'AI_LOCAL_ANALYSIS' 'true'
        Set-VercelEnv $BackendDir 'AI_BASE_URL' $AiBaseUrl
        Set-VercelEnv $BackendDir 'AI_MODEL' $AiModel
        Set-VercelEnv $BackendDir 'AI_API_KEY' $AiApiKey
        Set-VercelEnv $BackendDir 'DEEPSEEK_BASE_URL' $DeepseekBaseUrl
        Set-VercelEnv $BackendDir 'DEEPSEEK_MODEL' $DeepseekModel
        Set-VercelEnv $BackendDir 'DEEPSEEK_API_KEY' $DeepseekApiKey
        Set-VercelEnv $BackendDir 'NEXUS_RUNTIME_DIR' '/tmp/nexus-prime'
        Set-VercelEnv $BackendDir 'USE_CLOUD_STORAGE' 'auto'
        Set-VercelEnv $BackendDir 'REQUIRE_CLOUD_STORAGE_FOR_UPLOADS' 'auto'
        Set-VercelEnv $BackendDir 'CLOUDINARY_URL' $CloudinaryUrl
        Set-VercelEnv $BackendDir 'CACHE_TYPE' 'RedisCache'
        Set-VercelEnv $BackendDir 'REDIS_URL' $RedisUrl
        Set-VercelEnv $BackendDir 'CACHE_REDIS_URL' $RedisUrl
    }
    $deployArgs = @(
        'deploy', '--prod', '--yes', '--project', $BackendProjectName
    )
    Invoke-Vercel -Arguments $deployArgs -WorkingDirectory $BackendDir
}

if (-not $SkipFrontendDeploy) {
    Step 'Deploy frontend SPA to Vercel'
    Link-VercelProject $FrontendDir $FrontendProjectName
    if (-not $SkipVercelEnv) {
        Set-VercelEnv $FrontendDir 'NEXUS_API_BASE_URL' $ApiBaseUrl
    }
    Invoke-Vercel -Arguments @(
        'deploy', '--prod', '--yes', '--project', $FrontendProjectName,
        '--build-env', "NEXUS_API_BASE_URL=$ApiBaseUrl",
        '--env', "NEXUS_API_BASE_URL=$ApiBaseUrl"
    ) -WorkingDirectory $FrontendDir
}

if (-not $SkipApiProbe) {
    Step 'Probe deployed API'
    $healthUrl = $ApiBaseUrl.TrimEnd('/') + '/health'
    $response = Invoke-WebRequest -UseBasicParsing $healthUrl -TimeoutSec 20
    Check ($response.StatusCode -eq 200) "API health check failed: $healthUrl"
}

Step 'Deployment complete'
Write-Host "Backend API : $ApiBaseUrl"
Write-Host "Frontend SPA: $FrontendOrigin"
Write-Host "Database    : Supabase PostgreSQL"
