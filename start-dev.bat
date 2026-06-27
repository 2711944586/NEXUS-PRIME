@echo off
setlocal
chcp 65001 >nul
title NEXUS Prime Dev Launcher
cd /d "%~dp0"
set "CLEAN_SCRIPT=%~dp0scripts\clean-workspace.ps1"
set "DEV_SCRIPT=%~dp0scripts\dev.ps1"
where pwsh >nul 2>nul
if %errorlevel%==0 (
  pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%DEV_SCRIPT%" -ResetWorkspace %*
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%DEV_SCRIPT%" -ResetWorkspace %*
)
if errorlevel 1 pause
