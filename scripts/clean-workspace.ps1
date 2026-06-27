param(
    [switch]$StopDevServers,
    [switch]$RemoveDependencies,
    [switch]$PurgeUploads,
    [switch]$PurgeAvatars
)

$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Resolve-InRoot([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    if (-not $resolved.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean outside workspace: $resolved"
    }
    return $resolved
}

function Remove-Target([string]$RelativePath) {
    $target = Resolve-InRoot (Join-Path $Root $RelativePath)
    if ($target) {
        for ($attempt = 1; $attempt -le 5; $attempt++) {
            try {
                Remove-Item -LiteralPath $target -Recurse -Force
                break
            } catch {
                if ($attempt -eq 5) {
                    throw
                }
                Start-Sleep -Milliseconds (250 * $attempt)
            }
        }
        Write-Host "removed $RelativePath"
    }
}

function Remove-FileTarget([string]$RelativePath) {
    $target = Resolve-InRoot (Join-Path $Root $RelativePath)
    if ($target) {
        for ($attempt = 1; $attempt -le 6; $attempt++) {
            try {
                Remove-Item -LiteralPath $target -Force
                Write-Host "removed $RelativePath"
                return
            } catch {
                if ($attempt -eq 6) {
                    Write-Warning "kept locked file $RelativePath; close the owning process and rerun clean-workspace.ps1"
                    return
                }
                Start-Sleep -Milliseconds (300 * $attempt)
            }
        }
    }
}

function Restore-RuntimeConfig {
    $runtimeConfig = Join-Path $Root 'frontend\public\runtime-config.js'
    $runtimeDir = Split-Path -Parent $runtimeConfig
    if (-not (Test-Path -LiteralPath $runtimeDir)) {
        New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
    }
    @"
window.NEXUS_RUNTIME_CONFIG = {
  apiBaseUrl: ''
};
"@ | Set-Content -LiteralPath $runtimeConfig -Encoding UTF8
    Write-Host 'restored frontend\public\runtime-config.js fallback'
}

function Get-WorkspaceProcessInfo([int]$ProcessId) {
    $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    if (-not $processInfo) {
        return $null
    }
    $commandLine = [string]$processInfo.CommandLine
    if ($commandLine.IndexOf($Root, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
        return $null
    }
    return $processInfo
}

function Stop-WorkspaceProcess([int]$ProcessId, [string]$Reason) {
    $processInfo = Get-WorkspaceProcessInfo $ProcessId
    if (-not $processInfo) {
        return
    }
    if ($processInfo.Name -notmatch '^(node|npm|ng|python|pythonw)\.exe$') {
        return
    }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "stopped $($processInfo.Name) ($Reason)"
}

if ($StopDevServers) {
    $ports = @(5000, 5001) + (4200..4230) + (4300..4310)
    for ($attempt = 1; $attempt -le 4; $attempt++) {
        $processIds = Get-NetTCPConnection -LocalPort $ports -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
        if (-not $processIds) {
            break
        }
        foreach ($processId in $processIds) {
            Stop-WorkspaceProcess $processId 'workspace dev port'
        }
        Start-Sleep -Milliseconds (500 * $attempt)
    }

    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine -and
            $_.CommandLine.IndexOf($Root, [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
            $_.Name -match '^(node|npm|ng|python|pythonw)\.exe$' -and
            ($_.CommandLine -match 'run\.py|@angular\\cli|ng\.js|ng serve|npm.*start')
        } |
        ForEach-Object {
            Stop-WorkspaceProcess ([int]$_.ProcessId) 'workspace dev process'
        }
}

$targets = @(
    '.playwright-cli',
    '.pytest_cache',
    'output',
    'frontend\output',
    'frontend\.angular',
    'frontend\dist',
    'backend\.pytest_cache'
)

if ($RemoveDependencies) {
    $targets += @(
        'frontend\node_modules',
        'venv'
    )
}

foreach ($target in $targets) {
    Remove-Target $target
}

$backendDir = Resolve-InRoot (Join-Path $Root 'backend')
if ($backendDir) {
    Get-ChildItem -LiteralPath $backendDir -Directory -Recurse -Force -Filter '__pycache__' -ErrorAction SilentlyContinue |
        ForEach-Object {
            $resolved = Resolve-InRoot $_.FullName
            if ($resolved) {
                Remove-Item -LiteralPath $resolved -Recurse -Force
                Write-Host "removed $($resolved.Substring($Root.Length + 1))"
            }
        }
}

foreach ($file in @(
    'backend\instance\nexus_prime.db-wal',
    'backend\instance\nexus_prime.db-shm',
    'backend\logs\nexus_prime.log'
)) {
    Remove-FileTarget $file
}

$uploads = Resolve-InRoot (Join-Path $Root 'backend\storage\uploads')
if ($uploads -and $PurgeUploads) {
    Get-ChildItem -LiteralPath $uploads -Force | Where-Object {
        $_.Name -ne '.gitkeep' -and $_.Name -ne 'avatars' -and $_.Name -ne 'files' -and $_.Name -ne 'library'
    } | ForEach-Object {
        $resolved = Resolve-InRoot $_.FullName
        if ($resolved) {
            Remove-Item -LiteralPath $resolved -Recurse -Force
            Write-Host "removed $($resolved.Substring($Root.Length + 1))"
        }
    }
} elseif ($uploads) {
    Write-Host 'kept backend\storage\uploads; pass -PurgeUploads to remove uploaded attachments'
}

$fileDir = Resolve-InRoot (Join-Path $Root 'backend\storage\uploads\files')
if ($fileDir -and $PurgeUploads) {
    Get-ChildItem -LiteralPath $fileDir -Force | Where-Object { $_.Name -ne '.gitkeep' } | ForEach-Object {
        $resolved = Resolve-InRoot $_.FullName
        if ($resolved) {
            Remove-Item -LiteralPath $resolved -Recurse -Force
            Write-Host "removed $($resolved.Substring($Root.Length + 1))"
        }
    }
}

$avatarDir = Resolve-InRoot (Join-Path $Root 'backend\storage\uploads\avatars')
if ($avatarDir -and $PurgeUploads -and $PurgeAvatars) {
    Get-ChildItem -LiteralPath $avatarDir -Force | Where-Object { $_.Name -ne '.gitkeep' } | ForEach-Object {
        $resolved = Resolve-InRoot $_.FullName
        if ($resolved) {
            Remove-Item -LiteralPath $resolved -Recurse -Force
            Write-Host "removed $($resolved.Substring($Root.Length + 1))"
        }
    }
}

$libraryDir = Resolve-InRoot (Join-Path $Root 'backend\storage\uploads\library')
if ($libraryDir -and $PurgeUploads) {
    Get-ChildItem -LiteralPath $libraryDir -Force | Where-Object { $_.Name -ne '.gitkeep' } | ForEach-Object {
        $resolved = Resolve-InRoot $_.FullName
        if ($resolved) {
            Remove-Item -LiteralPath $resolved -Recurse -Force
            Write-Host "removed $($resolved.Substring($Root.Length + 1))"
        }
    }
}

Restore-RuntimeConfig
Write-Host 'workspace clean complete'
