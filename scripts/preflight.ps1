param(
    [string]$ApiBaseUrl = $env:NEXUS_API_BASE_URL,
    [string]$FrontendOrigin = $env:FRONTEND_ORIGIN,
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [switch]$SkipBuild,
    [switch]$SkipBackendTests,
    [switch]$SkipApiProbe,
    [switch]$NoInstall,
    [switch]$AllowMissingDependencies
)

$ErrorActionPreference = 'Stop'

$Root = Resolve-Path (Join-Path $PSScriptRoot '..')
$BackendDir = Join-Path $Root 'backend'
$FrontendDir = Join-Path $Root 'frontend'
$Python = Join-Path $Root 'venv\Scripts\python.exe'
$NodeModules = Join-Path $FrontendDir 'node_modules'
$InstallScript = Join-Path $Root 'scripts\install-dependencies.ps1'

$failures = New-Object System.Collections.Generic.List[string]

function Step($Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Check($Condition, $Message) {
    if ($Condition) {
        Write-Host "OK  $Message" -ForegroundColor Green
    } else {
        Write-Host "ERR $Message" -ForegroundColor Red
        $failures.Add($Message) | Out-Null
    }
}

function Warn($Condition, $Message) {
    if ($Condition) {
        Write-Host "OK  $Message" -ForegroundColor Green
    } else {
        Write-Host "WARN $Message" -ForegroundColor Yellow
    }
}

function ReadText($Path) {
    if (Test-Path $Path) {
        return Get-Content $Path -Raw
    }
    return ''
}

function IsHttpsUrl($Value) {
    return [bool]($Value -match '^https://[^ ]+$')
}

$retiredName = 'rail' + 'way'
$retiredConfigName = $retiredName + '.json'
$retiredPattern = "$retiredName|up\.$retiredName|$($retiredName.ToUpperInvariant())_ENVIRONMENT"

Step 'Retired platform configuration'
$retiredFiles = @(
    Join-Path $Root $retiredConfigName
    Join-Path $BackendDir $retiredConfigName
)
foreach ($retiredFile in $retiredFiles) {
    Check (-not (Test-Path $retiredFile)) "$($retiredFile.Replace($Root, '').TrimStart('\')) is removed"
}
$activeScanRoots = @($BackendDir, $FrontendDir, (Join-Path $Root 'scripts'), (Join-Path $Root '.github')) |
    Where-Object { Test-Path $_ }
$retiredMatches = $activeScanRoots |
    ForEach-Object { Get-ChildItem -Path $_ -Recurse -File -Force } |
    Where-Object {
        $_.FullName -notmatch '\\(node_modules|dist|output|\.angular|venv|legacy)\\' -and
        $_.Length -lt 1048576
    } |
    Select-String -Pattern $retiredPattern -CaseSensitive:$false -ErrorAction SilentlyContinue
Check (-not $retiredMatches) 'active project files contain no retired platform references'

Step 'Legacy comparison snapshot'
$legacySnapshot = Join-Path $Root 'legacy\monolith-flask'
Check (Test-Path $legacySnapshot) 'legacy/monolith-flask is retained for upgrade comparison'

Step 'Toolchain'
Check (Test-Path $BackendDir) 'backend/ exists'
Check (Test-Path $FrontendDir) 'frontend/ exists'
if (-not $NoInstall -and (-not (Test-Path $Python) -or -not (Test-Path $NodeModules))) {
    & powershell -ExecutionPolicy Bypass -File $InstallScript
    Check ($LASTEXITCODE -eq 0) 'missing local dependencies were restored'
}
if ($AllowMissingDependencies) {
    Warn (Test-Path $Python) 'Python virtualenv exists at venv/Scripts/python.exe'
} else {
    Check (Test-Path $Python) 'Python virtualenv exists at venv/Scripts/python.exe'
}
Check ([bool](Get-Command npm -ErrorAction SilentlyContinue)) 'npm is available'
Check ([bool](Get-Command node -ErrorAction SilentlyContinue)) 'node is available'
if ($AllowMissingDependencies) {
    Warn (Test-Path $NodeModules) 'frontend/node_modules exists'
} else {
    Check (Test-Path $NodeModules) 'frontend/node_modules exists'
}

Step 'Frontend deployment configuration'
$vercelConfig = Join-Path $FrontendDir 'vercel.json'
Check (Test-Path $vercelConfig) 'frontend/vercel.json exists'
if (Test-Path $vercelConfig) {
    $vercelJson = Get-Content $vercelConfig -Raw | ConvertFrom-Json
    Check ($vercelJson.framework -eq 'angular') 'Vercel framework is angular'
    Check ($vercelJson.buildCommand -eq 'npm run build') 'Vercel buildCommand is npm run build'
    Check ($vercelJson.outputDirectory -eq 'dist/frontend/browser') 'Vercel outputDirectory is dist/frontend/browser'
    $hasSpaRewrite = $false
    foreach ($rewrite in @($vercelJson.rewrites)) {
        if ($rewrite.source -eq '/(.*)' -and $rewrite.destination -eq '/index.html') {
            $hasSpaRewrite = $true
        }
    }
    Check $hasSpaRewrite 'Vercel SPA rewrite targets /index.html'
    Check (-not $vercelJson.env -and -not $vercelJson.build.env) 'Vercel secrets are not stored in vercel.json'
}

Step 'Backend deployment configuration'
$backendVercelConfig = Join-Path $BackendDir 'vercel.json'
Check (Test-Path (Join-Path $BackendDir 'server.py')) 'backend/server.py exists for Vercel Flask deployment'
Check (Test-Path $backendVercelConfig) 'backend/vercel.json exists'
if (Test-Path $backendVercelConfig) {
    $backendVercelJson = Get-Content $backendVercelConfig -Raw | ConvertFrom-Json
    Check ($backendVercelJson.framework -eq 'flask') 'Backend Vercel framework is flask'
    Check ($backendVercelJson.installCommand -eq 'pip install -r requirements.txt') 'Backend Vercel installCommand is pip install -r requirements.txt'
    Check ($backendVercelJson.functions.'server.py') 'Backend Vercel server.py function config exists'
}

$frontendEnvExample = Join-Path $FrontendDir '.env.example'
Check (Test-Path $frontendEnvExample) 'frontend/.env.example exists'
if (Test-Path $frontendEnvExample) {
    $frontendEnvText = ReadText $frontendEnvExample
    Check ($frontendEnvText -match 'NEXUS_API_BASE_URL=') 'frontend/.env.example documents NEXUS_API_BASE_URL'
}

$deployScript = Join-Path $Root 'scripts\deploy-supabase-vercel.ps1'
Check (Test-Path $deployScript) 'scripts/deploy-supabase-vercel.ps1 exists'

$syncScript = Join-Path $BackendDir 'scripts\sync_sqlite_to_postgres.py'
Check (Test-Path $syncScript) 'backend/scripts/sync_sqlite_to_postgres.py exists'
$dbStateScript = Join-Path $BackendDir 'scripts\database_state.py'
Check (Test-Path $dbStateScript) 'backend/scripts/database_state.py exists'

$gitIgnoreText = ReadText (Join-Path $Root '.gitignore')
Check ($gitIgnoreText -notmatch '!backend/instance/nexus_prime\.db') 'local SQLite database is not re-included in .gitignore'
Check ($gitIgnoreText -match 'frontend/public/runtime-config\.js') 'runtime-config.js is ignored as generated runtime config'

$runtimeConfig = ReadText (Join-Path $FrontendDir 'public\runtime-config.js')
Check ($runtimeConfig -notmatch '127\.0\.0\.1|localhost') 'runtime-config.js is not hard-coded to localhost'
Check ($runtimeConfig -notmatch $retiredPattern) 'runtime-config.js contains no retired platform URL'
Check ([bool]$ApiBaseUrl) 'NEXUS_API_BASE_URL is set for production runtime config'
if ($ApiBaseUrl) {
    Check ($ApiBaseUrl -match '^https://.+/api/v1/?$') 'NEXUS_API_BASE_URL uses HTTPS and ends with /api/v1'
    Check ($ApiBaseUrl -notmatch "127\.0\.0\.1|localhost|$retiredPattern") 'NEXUS_API_BASE_URL is not localhost or retired platform'
}

$prodEnvironment = ReadText (Join-Path $FrontendDir 'src\environments\environment.prod.ts')
Check ($prodEnvironment -notmatch "$retiredPattern|localhost|127\.0\.0\.1") 'environment.prod.ts contains no local or retired platform API URL'
Check ($prodEnvironment -notmatch 'admin123|password123') 'environment.prod.ts contains no local demo passwords'
Check ($prodEnvironment -match 'demoAccounts:\s*\{\s*\}') 'production environment disables demo account shortcuts'

$angularConfig = ReadText (Join-Path $FrontendDir 'angular.json')
Check ($angularConfig -match 'environment\.prod\.ts') 'Angular production build replaces environment.ts with environment.prod.ts'

$runtimeWriter = ReadText (Join-Path $FrontendDir 'scripts\write-runtime-config.mjs')
Check ($runtimeWriter -match 'NEXUS_API_BASE_URL') 'runtime config writer reads NEXUS_API_BASE_URL'
Check ($runtimeWriter -match 'VERCEL' -and $runtimeWriter -match 'process\.exit\(1\)') 'Vercel build fails when NEXUS_API_BASE_URL is missing'

$deployScriptText = ReadText $deployScript
Check ($deployScriptText -match 'ResetAndSeedRemote') 'deploy script uses explicit ResetAndSeedRemote for destructive reseed'
Check ($deployScriptText -match 'database_state\.py') 'deploy script checks remote database state before SeedRemoteWhenEmpty'
Check ($deployScriptText -match 'DemoAdminPassword' -and $deployScriptText -match 'DemoUserPassword') 'deploy script requires custom remote demo passwords'
Check ($deployScriptText -match 'NEXUS_DEMO_ADMIN_PASSWORD' -and $deployScriptText -match 'NEXUS_DEMO_USER_PASSWORD') 'deploy script reads remote demo passwords from environment'
Check ($deployScriptText -match 'Format-CommandForLog' -and $deployScriptText -match 'Redact-SecretText') 'deploy script redacts sensitive command output'
Check ($deployScriptText -match "--token'\\s*,\\s*'--target" -or ($deployScriptText -match '--token' -and $deployScriptText -match '--target')) 'deploy script redacts Vercel token and database target arguments'
$seedBlock = [regex]::Match($deployScriptText, 'if \(\$SeedRemoteWhenEmpty\) \{(?<body>.*?)\n\}', [System.Text.RegularExpressions.RegexOptions]::Singleline)
Check ($seedBlock.Success -and $seedBlock.Groups['body'].Value -notmatch '--reset') 'SeedRemoteWhenEmpty does not reset existing data'
Check ($seedBlock.Success -and $seedBlock.Groups['body'].Value -notmatch '--admin-password|--user-password') 'SeedRemoteWhenEmpty does not echo demo passwords as command arguments'
Check ($deployScriptText -match "DemoAdminPassword -ne 'admin123'" -and $deployScriptText -match "DemoUserPassword -ne 'password123'") 'deploy script rejects default demo passwords for remote seeds'

$frontendPackage = Get-Content (Join-Path $FrontendDir 'package.json') -Raw | ConvertFrom-Json
Check ($frontendPackage.scripts.prebuild -match 'write-runtime-config\.mjs') 'frontend prebuild writes runtime-config.js'

Step 'Frontend maintainability checks'
$navigationSource = ReadText (Join-Path $FrontendDir 'src\app\core\navigation.ts')
Check ($navigationSource -match 'DESKTOP_DOCK_KEYS' -and $navigationSource -match 'MOBILE_DOCK_KEYS') 'Dock visibility keys are centralized in core/navigation.ts'
Check ($navigationSource -match 'dockItemsByKeys') 'Dock key ordering helper is centralized'

$authServiceSource = ReadText (Join-Path $FrontendDir 'src\app\core\auth.service.ts')
Check ($authServiceSource -notmatch 'localStorage\.setItem\(USER_KEY') 'AuthService does not persist user profiles in localStorage'
Check ($authServiceSource -match 'sessionStorage\.setItem\(USER_KEY') 'AuthService keeps only session-scoped user profile cache'
$loginPageSource = ReadText (Join-Path $FrontendDir 'src\app\pages\login.page.ts')
Check ($loginPageSource -notmatch 'admin123|password123') 'login page does not hard-code local demo passwords'
$visualAssetsSource = ReadText (Join-Path $FrontendDir 'src\app\core\visual-assets.ts')
Check ($visualAssetsSource -match 'COMMAND_CENTER_PHOTOS') 'visual asset registry exists for command center photos'
foreach ($imageName in @(
    'plant-floor.jpg',
    'warehouse-aisles.jpg',
    'industrial-manufacturing.jpg',
    'operations-team-wide.jpg',
    'finance-dashboard-wide.jpg',
    'analytics-office-wide.jpg',
    'planning-desk-wide.jpg',
    'control-dashboard-wide.jpg',
    'mobile-workflow-wide.jpg',
    'quality-inspection-wide.jpg',
    'maintenance-technician-wide.jpg',
    'contracts-desk-wide.jpg',
    'integration-monitor-wide.jpg',
    'data-quality-wide.jpg',
    'service-workorders-wide.jpg',
    'budget-planning-wide.jpg',
    'mobile-scanner-wide.jpg'
)) {
    Check (Test-Path (Join-Path $FrontendDir "public\images\$imageName")) "frontend/public/images/$imageName exists"
}

Step 'Backend deployment configuration'
$backendEnvExample = Join-Path $BackendDir '.env.example'
Check (Test-Path $backendEnvExample) 'backend/.env.example exists'
if (Test-Path $backendEnvExample) {
    $backendEnvText = ReadText $backendEnvExample
    foreach ($key in @('DATABASE_URL', 'CORS_ORIGINS', 'FRONTEND_ORIGIN', 'AUTH_COOKIE_SECURE', 'AUTH_COOKIE_SAMESITE', 'LOGIN_RATE_LIMIT_ATTEMPTS', 'LOGIN_RATE_LIMIT_WINDOW_SECONDS', 'CACHE_TYPE', 'REDIS_URL', 'CACHE_REDIS_URL', 'SECRET_KEY', 'FLASK_CONFIG', 'NEXUS_RUNTIME_DIR', 'UPLOAD_FOLDER', 'UPLOAD_FILES_FOLDER', 'UPLOAD_AVATARS_FOLDER', 'UPLOAD_LIBRARY_FOLDER', 'AI_API_KEY', 'AI_BASE_URL', 'AI_MODEL', 'AI_REQUEST_TIMEOUT_SECONDS', 'AI_CONNECT_TIMEOUT_SECONDS', 'OPENAI_API_KEY', 'DEEPSEEK_BASE_URL', 'DEEPSEEK_MODEL', 'REQUIRE_CLOUD_STORAGE_FOR_UPLOADS')) {
        Check ($backendEnvText -match "$key=") "backend/.env.example documents $key"
    }
    Check ($backendEnvText -match 'sslmode=require') 'backend/.env.example documents Supabase SSL mode'
    Check ($backendEnvText -match 'CLOUDINARY_URL=') 'backend/.env.example documents Cloudinary for persistent uploads'
}
foreach ($storagePath in @(
    'backend\storage\uploads\files\.gitkeep',
    'backend\storage\uploads\avatars\.gitkeep',
    'backend\storage\uploads\library\.gitkeep'
)) {
    Check (Test-Path (Join-Path $Root $storagePath)) "$storagePath keeps dedicated upload storage"
}
$backendProcfile = Join-Path $BackendDir 'Procfile'
Check (Test-Path $backendProcfile) 'backend/Procfile exists for independent API hosts'
if (Test-Path $backendProcfile) {
    $procfileText = ReadText $backendProcfile
    Check ($procfileText -match 'gunicorn run:app') 'backend/Procfile starts gunicorn run:app'
    Check ($procfileText -notmatch $retiredPattern) 'backend/Procfile contains no retired platform wording'
}

Step 'Supabase/PostgreSQL configuration'
Check ([bool]$DatabaseUrl) 'DATABASE_URL is set'
if ($DatabaseUrl) {
    Check ($DatabaseUrl -match '^postgres(ql)?://') 'DATABASE_URL uses PostgreSQL'
    Check ($DatabaseUrl -match 'supabase\.com|pooler\.supabase\.com') 'DATABASE_URL targets Supabase'
    Check ($DatabaseUrl -match 'sslmode=require') 'DATABASE_URL requires SSL'
}

Step 'Cross-origin auth settings'
Check ([bool]$FrontendOrigin) 'FRONTEND_ORIGIN is set'
if ($FrontendOrigin) {
    Check (IsHttpsUrl $FrontendOrigin) 'FRONTEND_ORIGIN uses HTTPS'
    Check ($FrontendOrigin -notmatch '127\.0\.0\.1|localhost') 'FRONTEND_ORIGIN is not localhost'
}

$corsOrigins = $env:CORS_ORIGINS
Check ([bool]$corsOrigins) 'CORS_ORIGINS is set'
if ($FrontendOrigin -and $corsOrigins) {
    Check ($corsOrigins.Split(',').Trim() -contains $FrontendOrigin) 'CORS_ORIGINS includes FRONTEND_ORIGIN'
}
Check ($env:AUTH_COOKIE_SECURE -eq 'true') 'AUTH_COOKIE_SECURE=true for cross-site production cookies'
Check ($env:AUTH_COOKIE_SAMESITE -eq 'None') 'AUTH_COOKIE_SAMESITE=None for Vercel/API cross-site cookies'
Check ([bool]$env:SECRET_KEY -and $env:SECRET_KEY.Length -ge 32) 'SECRET_KEY is set and at least 32 characters'
Check ([bool]$env:CLOUDINARY_URL) 'CLOUDINARY_URL is set for persistent production avatars and files'
$sharedCacheUrl = if ($env:CACHE_REDIS_URL) { $env:CACHE_REDIS_URL } elseif ($env:REDIS_URL) { $env:REDIS_URL } else { $env:UPSTASH_REDIS_URL }
Check ($env:CACHE_TYPE -eq 'RedisCache' -or [bool]$sharedCacheUrl) 'production login rate limit uses shared Redis cache'
if ($sharedCacheUrl) {
    Check ($sharedCacheUrl -match '^rediss?://') 'shared cache URL uses redis:// or rediss://'
}
Warn ([bool]($env:AI_API_KEY -or $env:OPENAI_API_KEY -or $env:DEEPSEEK_API_KEY)) 'External AI key is set; local analysis remains available when omitted'

if (-not $SkipApiProbe -and $ApiBaseUrl) {
    Step 'API health probe'
    try {
        $healthUrl = $ApiBaseUrl.TrimEnd('/') + '/health'
        $response = Invoke-WebRequest -UseBasicParsing $healthUrl -TimeoutSec 12
        Check ($response.StatusCode -eq 200) "API health returns 200 at $healthUrl"
        $readyUrl = $ApiBaseUrl.TrimEnd('/') + '/health/ready'
        $readyResponse = Invoke-WebRequest -UseBasicParsing $readyUrl -TimeoutSec 12
        Check ($readyResponse.StatusCode -eq 200) "API readiness returns 200 at $readyUrl"
    } catch {
        Check $false "API health probe failed: $($_.Exception.Message)"
    }
}

if (-not $SkipBuild) {
    Step 'Frontend build'
    Push-Location $FrontendDir
    try {
        npm run build
        Check (Test-Path (Join-Path $FrontendDir 'dist\frontend\browser\index.html')) 'Angular production build emitted dist/frontend/browser/index.html'
    } finally {
        Pop-Location
    }
}

if (-not $SkipBackendTests) {
    Step 'Backend tests'
    Push-Location $BackendDir
    try {
        $env:FLASK_APP = 'run.py'
        & $Python -m pytest
        Check ($LASTEXITCODE -eq 0) 'pytest completed successfully'
    } finally {
        Pop-Location
    }
}

if ($failures.Count) {
    Write-Host ''
    Write-Host 'Preflight failed:' -ForegroundColor Red
    foreach ($failure in $failures) {
        Write-Host "- $failure" -ForegroundColor Red
    }
    exit 1
}

Write-Host ''
Write-Host 'Preflight completed. Review WARN lines before production deployment.' -ForegroundColor Green
