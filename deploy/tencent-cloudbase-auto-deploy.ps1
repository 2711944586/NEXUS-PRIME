param(
  [string]$EnvId = "constantine-d3gjhwmtz0336c36a",
  [string]$Suffix = "",
  [string]$CloudBaseCliVersion = "3.5.8",
  [string]$TencentSecretId = $env:TENCENTCLOUD_SECRET_ID,
  [string]$TencentSecretKey = $env:TENCENTCLOUD_SECRET_KEY,
  [string]$TencentToken = $env:TENCENTCLOUD_TOKEN,
  [string]$CloudBaseApiKey = $env:CLOUDBASE_API_KEY,
  [string]$Domain = $env:NEXUS_TCB_DOMAIN,
  [string]$ApiBaseUrl = $env:NEXUS_API_BASE_URL,
  [string]$FrontendOrigin = $env:NEXUS_FRONTEND_ORIGIN,
  [string]$BackendEnvFile = $env:NEXUS_TCB_BACKEND_ENV_FILE,
  [switch]$SkipBackend,
  [switch]$SkipFrontend,
  [switch]$SkipRoutes,
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$FrontendDir = Join-Path $RepoRoot "frontend"
$BackendDir = Join-Path $RepoRoot "backend"
$OutputRoot = Join-Path $RepoRoot "output\tencent-cloudbase"
$DistDir = Join-Path $FrontendDir "dist\frontend\browser"

function Write-Step([string]$Message) {
  Write-Host ""
  Write-Host "==> $Message" -ForegroundColor Cyan
}

function Require-Command([string]$Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Required command '$Name' was not found in PATH."
  }
}

function Invoke-Checked {
  param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [Parameter(Mandatory = $true)][string[]]$Arguments,
    [string]$WorkingDirectory = $RepoRoot
  )
  $display = "$FilePath $($Arguments -join ' ')"
  if ($DryRun) {
    Write-Host "[dry-run] $display"
    return ""
  }
  Write-Host $display -ForegroundColor DarkGray
  $output = & $FilePath @Arguments 2>&1
  $exit = $LASTEXITCODE
  if ($output) {
    $output | ForEach-Object { Write-Host $_ }
  }
  if ($exit -ne 0) {
    throw "Command failed with exit code $exit`: $display"
  }
  return ($output -join [Environment]::NewLine)
}

function Invoke-InDirectory {
  param(
    [Parameter(Mandatory = $true)][string]$Directory,
    [Parameter(Mandatory = $true)][scriptblock]$Script
  )
  $previous = Get-Location
  try {
    Set-Location $Directory
    & $Script
  } finally {
    Set-Location $previous
  }
}

function Invoke-Tcb {
  param([Parameter(Mandatory = $true)][string[]]$Arguments)
  $tcb = Get-Command tcb -ErrorAction SilentlyContinue
  if ($tcb) {
    return Invoke-Checked -FilePath $tcb.Source -Arguments $Arguments
  }
  return Invoke-Checked -FilePath "npx" -Arguments (@("--yes", "--package", "@cloudbase/cli@$CloudBaseCliVersion", "tcb") + $Arguments)
}

function Read-EnvFile([string]$Path) {
  $data = @{}
  if (-not $Path -or -not (Test-Path $Path)) {
    return $data
  }
  foreach ($line in Get-Content -LiteralPath $Path) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) {
      continue
    }
    $idx = $trimmed.IndexOf("=")
    if ($idx -le 0) {
      continue
    }
    $key = $trimmed.Substring(0, $idx).Trim()
    $value = $trimmed.Substring($idx + 1).Trim().Trim('"').Trim("'")
    $data[$key] = $value
  }
  return $data
}

function Get-EnvValue($Map, [string]$Name, [string]$Default = "") {
  foreach ($target in @("Process", "User", "Machine")) {
    $fromEnv = [Environment]::GetEnvironmentVariable($Name, $target)
    if ($fromEnv) {
      return $fromEnv
    }
  }
  if ($Map.ContainsKey($Name) -and $Map[$Name]) {
    return $Map[$Name]
  }
  return $Default
}

function New-BackendEnvContent($Map, [string]$PublicOrigin) {
  $databaseUrl = Get-EnvValue $Map "DATABASE_URL"
  $secretKey = Get-EnvValue $Map "SECRET_KEY"
  if (-not $databaseUrl -or $databaseUrl -like "*replace-with*") {
    throw "DATABASE_URL is required. Set it in $BackendEnvFile or as an environment variable."
  }
  if (-not $secretKey -or $secretKey -like "*replace-with*" -or $secretKey.Length -lt 32) {
    throw "SECRET_KEY is required and must be a strong random value with at least 32 characters."
  }

  $cors = Get-EnvValue $Map "CORS_ORIGINS" $PublicOrigin
  if (-not $cors) {
    throw "CORS_ORIGINS or -FrontendOrigin is required for production backend deployment."
  }

  $lines = [System.Collections.Generic.List[string]]::new()
  $names = @(
    "FLASK_APP", "FLASK_CONFIG", "PORT", "NEXUS_RUNTIME_DIR",
    "SECRET_KEY", "DATABASE_URL", "DB_SSL_MODE", "DB_POOL_SIZE", "DB_MAX_OVERFLOW",
    "ALLOW_PRODUCTION_SQLITE",
    "NEXUS_DB_BOOTSTRAP_URL", "NEXUS_DB_BOOTSTRAP_FORCE", "NEXUS_DB_BOOTSTRAP_MIN_USERS", "NEXUS_DB_BOOTSTRAP_MIN_ORDERS",
    "NEXUS_DEPLOYMENT_DIAGNOSTICS",
    "CORS_ORIGINS", "FRONTEND_ORIGIN",
    "SESSION_COOKIE_SECURE", "SESSION_COOKIE_HTTPONLY", "SESSION_COOKIE_SAMESITE",
    "AUTH_COOKIE_SECURE", "AUTH_COOKIE_SAMESITE",
    "REDIS_URL", "CACHE_REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND",
    "ALLOW_PRODUCTION_SIMPLE_CACHE",
    "AI_LOCAL_ANALYSIS", "AI_API_KEY", "AI_BASE_URL", "AI_MODEL",
    "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL",
    "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL",
    "USE_CLOUD_STORAGE", "REQUIRE_CLOUD_STORAGE_FOR_UPLOADS",
    "CLOUDINARY_URL", "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET",
    "OBJECT_STORAGE_PROVIDER", "OBJECT_STORAGE_ENDPOINT", "OBJECT_STORAGE_BUCKET", "OBJECT_STORAGE_REGION",
    "OBJECT_STORAGE_ACCESS_KEY_ID", "OBJECT_STORAGE_ACCESS_KEY_SECRET", "PUBLIC_ASSET_CDN_ORIGIN",
    "LOG_LEVEL", "OTEL_TRACES_ENABLED", "OTEL_SERVICE_NAME", "OTEL_EXPORTER_OTLP_ENDPOINT",
    "WEB_CONCURRENCY", "WEB_THREADS", "WEB_TIMEOUT", "WEB_MAX_REQUESTS", "WEB_MAX_REQUESTS_JITTER"
  )

  $defaults = @{
    FLASK_APP = "run.py"
    FLASK_CONFIG = "production"
    PORT = "5000"
    NEXUS_RUNTIME_DIR = "/tmp/nexus-prime"
    DB_SSL_MODE = "prefer"
    DB_POOL_SIZE = "5"
    DB_MAX_OVERFLOW = "10"
    FRONTEND_ORIGIN = $PublicOrigin
    CORS_ORIGINS = $cors
    SESSION_COOKIE_SECURE = "true"
    SESSION_COOKIE_HTTPONLY = "true"
    SESSION_COOKIE_SAMESITE = "None"
    AUTH_COOKIE_SECURE = "true"
    AUTH_COOKIE_SAMESITE = "None"
    ALLOW_PRODUCTION_SIMPLE_CACHE = "true"
    AI_LOCAL_ANALYSIS = "true"
    USE_CLOUD_STORAGE = "auto"
    REQUIRE_CLOUD_STORAGE_FOR_UPLOADS = "auto"
    LOG_LEVEL = "INFO"
    OTEL_TRACES_ENABLED = "false"
    OTEL_SERVICE_NAME = "nexus-prime-backend"
    WEB_CONCURRENCY = "2"
    WEB_THREADS = "4"
    WEB_TIMEOUT = "120"
    WEB_MAX_REQUESTS = "1000"
    WEB_MAX_REQUESTS_JITTER = "100"
  }

  foreach ($name in $names) {
    $default = ""
    if ($defaults.ContainsKey($name)) {
      $default = $defaults[$name]
    }
    $value = Get-EnvValue $Map $name $default
    if ($null -ne $value -and "$value" -ne "") {
      $escaped = "$value".Replace("`r", "").Replace("`n", "")
      $lines.Add("$name=$escaped")
    }
  }
  return ($lines -join [Environment]::NewLine) + [Environment]::NewLine
}

function Copy-DirectoryClean([string]$Source, [string]$Destination) {
  if (Test-Path $Destination) {
    Remove-Item -LiteralPath $Destination -Recurse -Force
  }
  New-Item -ItemType Directory -Force -Path $Destination | Out-Null
  Copy-Item -LiteralPath $Source -Destination (Split-Path $Destination -Parent) -Recurse -Force
}

function Add-HttpRoute([string]$DomainName, [string]$Path, [string]$Type, [string]$Name, [string]$RewritePrefix = "") {
  if ($SkipRoutes -or -not $DomainName) {
    return
  }
  $routeDomain = $DomainName
  if ($DomainName -like "*.tcloudbase.com" -or $DomainName -like "*.tcloudbaseapp.com") {
    $routeDomain = "*"
  }
  $route = @{
    path = $Path
    upstreamResourceType = $Type
    upstreamResourceName = $Name
    enable = $true
    enableAuth = $false
    enableSafeDomain = $true
    enablePathTransmission = $true
  }
  if ($RewritePrefix) {
    $route["pathRewrite"] = @{ prefix = $RewritePrefix }
  }
  $payload = @{
    domain = $routeDomain
    routes = @($route)
  } | ConvertTo-Json -Depth 8 -Compress
  Invoke-Tcb @("-e", $EnvId, "--yes", "routes", "add", "--data", $payload, "--json")
}

function Update-FrontendStaticAssetPaths([string]$Directory, [string]$BaseHref) {
  if (-not (Test-Path $Directory)) {
    throw "Frontend dist directory was not found: $Directory"
  }
  $normalizedBase = if ($BaseHref.EndsWith("/")) { $BaseHref } else { "$BaseHref/" }
  $assetBase = "${normalizedBase}images/"
  $extensions = @("*.html", "*.css", "*.js")
  foreach ($extension in $extensions) {
    Get-ChildItem -LiteralPath $Directory -Recurse -File -Filter $extension | ForEach-Object {
      $content = Get-Content -LiteralPath $_.FullName -Raw
      $next = [regex]::Replace($content, "(?<=[`"'(])\/images\/", $assetBase)
      $next = [regex]::Replace($next, "(?<=[`"'])(?!$([regex]::Escape($normalizedBase)))images/", $assetBase)
      if ($next -ne $content) {
        Set-Content -LiteralPath $_.FullName -Value $next -Encoding UTF8 -NoNewline
      }
    }
  }
}

Require-Command "node"
Require-Command "npm"
Require-Command "npx"

if (-not $Suffix) {
  $stamp = Get-Date -Format "MMddHHmm"
  $sha = "nogit"
  try {
    $sha = (& git -C $RepoRoot rev-parse --short=7 HEAD 2>$null)
  } catch {
    $sha = "nogit"
  }
  $Suffix = "$stamp-$sha".ToLowerInvariant() -replace "[^a-z0-9-]", "-"
}

$shortSuffix = ($Suffix -replace "[^a-z0-9]", "")
if ($shortSuffix.Length -gt 12) {
  $shortSuffix = $shortSuffix.Substring(0, 12)
}

$BackendServiceName = "nexus-api-$Suffix"
$FrontendCloudPath = "nexus-prime-$Suffix"
$FrontendBaseHref = "/$FrontendCloudPath/"
$FrontendRoutePath = "/$FrontendCloudPath/*"
$BackendRoutePrefix = "api-$shortSuffix"
$BackendRoutePath = "/$BackendRoutePrefix/*"

if ($Domain -and -not $FrontendOrigin) {
  $FrontendOrigin = "https://$Domain"
}
if ($Domain -and -not $ApiBaseUrl) {
  $ApiBaseUrl = "https://$Domain/$BackendRoutePrefix/api/v1"
}
if (-not $SkipFrontend -and -not $ApiBaseUrl) {
  throw "ApiBaseUrl is required for frontend build. Provide -ApiBaseUrl or -Domain."
}
if (-not $FrontendOrigin -and $Domain) {
  $FrontendOrigin = "https://$Domain"
}
Write-Step "CloudBase preflight"
Invoke-Tcb @("--version")

Write-Step "CloudBase login check"
if ($CloudBaseApiKey) {
  Invoke-Tcb @("-e", $EnvId, "login", "--cloudbase-api-key", $CloudBaseApiKey, "--json")
} elseif ($TencentSecretId -and $TencentSecretKey) {
  $loginArgs = @("login", "--apiKeyId", $TencentSecretId, "--apiKey", $TencentSecretKey, "--json")
  if ($TencentToken) {
    $loginArgs += @("--token", $TencentToken)
  }
  Invoke-Tcb $loginArgs
} else {
  try {
    Invoke-Tcb @("-e", $EnvId, "app", "list", "--limit", "1", "--json")
  } catch {
    throw "CloudBase login is required. Set CLOUDBASE_API_KEY or TENCENTCLOUD_SECRET_ID/TENCENTCLOUD_SECRET_KEY, or run: npx --yes --package @cloudbase/cli@$CloudBaseCliVersion tcb login"
  }
}

$summary = [ordered]@{
  envId = $EnvId
  suffix = $Suffix
  backendService = $BackendServiceName
  frontendCloudPath = "/$FrontendCloudPath/"
  frontendBaseHref = $FrontendBaseHref
  apiBaseUrl = $ApiBaseUrl
  domain = $Domain
  frontendRoute = if ($Domain) { $FrontendRoutePath } else { "" }
  backendRoute = if ($Domain) { $BackendRoutePath } else { "" }
}

if (-not $SkipBackend) {
  Write-Step "Prepare backend CloudBase source"
  if (-not $BackendEnvFile) {
    $candidate = Join-Path $RepoRoot ".env.tencent-cloudbase"
    if (Test-Path $candidate) {
      $BackendEnvFile = $candidate
    } else {
      $candidate = Join-Path $RepoRoot ".env.mainland"
      if (Test-Path $candidate) {
        $BackendEnvFile = $candidate
      }
    }
  }
  $backendEnv = Read-EnvFile $BackendEnvFile
  $deploymentDatabaseUrl = Get-EnvValue $backendEnv "DATABASE_URL"
  $bootstrapDatabaseUrl = Get-EnvValue $backendEnv "NEXUS_DB_BOOTSTRAP_URL"
  $stagingBackend = Join-Path $OutputRoot "backend-$Suffix"
  if (Test-Path $stagingBackend) {
    Remove-Item -LiteralPath $stagingBackend -Recurse -Force
  }
  New-Item -ItemType Directory -Force -Path $stagingBackend | Out-Null
  Copy-Item -LiteralPath $BackendDir -Destination (Join-Path $stagingBackend "backend") -Recurse -Force
  $sqliteMatch = [regex]::Match($deploymentDatabaseUrl, "^sqlite:///(.+)$")
  if ($sqliteMatch.Success -and -not $bootstrapDatabaseUrl) {
    $sqliteLeaf = Split-Path $sqliteMatch.Groups[1].Value -Leaf
    if ($sqliteLeaf -and $sqliteLeaf -ne ":memory:") {
      $stagingInstance = Join-Path $stagingBackend "backend\instance"
      if (Test-Path $stagingInstance) {
        $keep = @($sqliteLeaf, "$sqliteLeaf-shm", "$sqliteLeaf-wal")
        Get-ChildItem -LiteralPath $stagingInstance -File |
          Where-Object { $_.Name -like "*.db" -or $_.Name -like "*.db-shm" -or $_.Name -like "*.db-wal" } |
          Where-Object { $keep -notcontains $_.Name } |
          Remove-Item -Force
      }
    }
  }
  if ($sqliteMatch.Success -and $bootstrapDatabaseUrl) {
    $stagingInstance = Join-Path $stagingBackend "backend\instance"
    if (Test-Path $stagingInstance) {
      Get-ChildItem -LiteralPath $stagingInstance -File |
        Where-Object { $_.Name -like "*.db" -or $_.Name -like "*.db-shm" -or $_.Name -like "*.db-wal" } |
        Remove-Item -Force
    }
  }
  Get-ChildItem -LiteralPath (Join-Path $stagingBackend "backend") -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force
  Get-ChildItem -LiteralPath (Join-Path $stagingBackend "backend") -Recurse -File -Filter "*.pyc" |
    Remove-Item -Force
  foreach ($relative in @("backend\tests", "backend\logs", "backend\openapi.json")) {
    $unneeded = Join-Path $stagingBackend $relative
    if (Test-Path $unneeded) {
      Remove-Item -LiteralPath $unneeded -Recurse -Force
    }
  }
  Copy-Item -LiteralPath (Join-Path $RepoRoot "Dockerfile.backend.prod") -Destination (Join-Path $stagingBackend "Dockerfile") -Force
  @"
frontend
node_modules
output
docs
.git
*.pyc
__pycache__
backend/logs
"@ | Set-Content -LiteralPath (Join-Path $stagingBackend ".dockerignore") -Encoding UTF8
  New-BackendEnvContent $backendEnv $FrontendOrigin | Set-Content -LiteralPath (Join-Path $stagingBackend "backend\.env") -Encoding UTF8

  Write-Step "Deploy backend CloudBase CloudRun service"
  Invoke-Tcb @("-e", $EnvId, "cloudrun", "deploy", "-s", $BackendServiceName, "--port", "5000", "--source", $stagingBackend, "--force", "--traffic", "--json")
}

if (-not $SkipFrontend) {
  Write-Step "Build frontend for unique CloudBase path"
  Invoke-InDirectory $FrontendDir {
    $env:NEXUS_API_BASE_URL = $ApiBaseUrl
    $env:NEXUS_SENTRY_ENVIRONMENT = "production-tencent"
    Invoke-Checked -FilePath "npm" -Arguments @("run", "build", "--", "--base-href", $FrontendBaseHref, "--deploy-url", $FrontendBaseHref) -WorkingDirectory $FrontendDir
  }

  Write-Step "Normalize frontend static asset paths"
  Update-FrontendStaticAssetPaths -Directory $DistDir -BaseHref $FrontendBaseHref

  Write-Step "Deploy frontend static hosting"
  Invoke-Tcb @("-e", $EnvId, "hosting", "deploy", $DistDir, $FrontendCloudPath, "--json")
}

if ($Domain) {
  Write-Step "Add non-conflicting HTTP routes"
  if (-not $SkipBackend) {
    Add-HttpRoute -DomainName $Domain -Path $BackendRoutePath -Type "CBR" -Name $BackendServiceName -RewritePrefix "/"
  }
  if (-not $SkipFrontend) {
    Add-HttpRoute -DomainName $Domain -Path $FrontendRoutePath -Type "STATIC_STORE" -Name "staticstore"
  }
}

Write-Step "Deployment summary"
$summary | ConvertTo-Json -Depth 4 | Write-Host

if ($Domain) {
  Write-Host ""
  if (-not $SkipFrontend) {
    Write-Host "Frontend URL: https://$Domain/$FrontendCloudPath/"
  }
  if (-not $SkipBackend) {
    Write-Host "API health:   https://$Domain/$BackendRoutePrefix/health/ready"
  } else {
    Write-Host "API base:     $ApiBaseUrl"
  }
} else {
  Write-Host ""
  Write-Host "Frontend files were deployed under CloudBase static hosting path: /$FrontendCloudPath/"
  Write-Host "Bind a domain or pass -Domain on the next run to create stable HTTP routes automatically."
}

Write-Host ""
Write-Host "Rollback notes:"
Write-Host "  - Keep previous unique paths/services; this script does not delete or overwrite them."
Write-Host "  - To rollback frontend, route the domain prefix back to an older static path."
Write-Host "  - To rollback backend, route the API prefix back to an older CloudRun service or use CloudRun traffic rollback."
