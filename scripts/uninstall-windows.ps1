<#
.SYNOPSIS
  Remove everything install-windows.ps1 added.

.PARAMETER Purge
  Also delete saved credentials, config, state and log.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\uninstall-windows.ps1 -Purge
#>
param(
    [string]$TaskName = 'fortiauto',
    [switch]$Purge
)
$ErrorActionPreference = 'Continue'

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed task '$TaskName'"
}

$lnk = Join-Path ([Environment]::GetFolderPath('Startup')) "$TaskName.lnk"
if (Test-Path $lnk) { Remove-Item -Force $lnk; Write-Host "Removed $lnk" }

# Stop a running copy started from the Startup shortcut.
Get-CimInstance Win32_Process -Filter "Name like 'python%'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*fortiauto*' -and $_.CommandLine -like '* run*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host "Stopped PID $($_.ProcessId)" }

$app = Join-Path $env:LOCALAPPDATA 'fortiauto'
if (Test-Path $app) { Remove-Item -Recurse -Force $app; Write-Host "Removed $app" }

if ($Purge) {
    cmdkey /delete:fortiauto 2>$null | Out-Null
    $data = Join-Path $env:APPDATA 'fortiauto'
    if (Test-Path $data) { Remove-Item -Recurse -Force $data }
    Write-Host 'Removed saved credentials, config, state and log'
}
Write-Host 'fortiauto is uninstalled.'
