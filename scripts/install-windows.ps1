<#
.SYNOPSIS
  Install fortiauto as a per-user background task that starts at logon.

.DESCRIPTION
  - No admin rights, no pip, nothing installed into your Python.
  - Copies the fortiauto folder to %LOCALAPPDATA%\fortiauto\app.
  - Registers a Task Scheduler task for YOUR user only: starts at logon,
    runs hidden (pythonw), below-normal priority, keeps running on battery,
    retries if it fails to launch. (The watcher itself never exits on errors.)
  - Falls back to a Startup-folder shortcut if Task Scheduler refuses.
  Undo everything with scripts\uninstall-windows.ps1.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
#>
param(
    [string]$TaskName = 'fortiauto',
    [switch]$NoPrompt  # don't ask for the portal login at the end
)
$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $env:LOCALAPPDATA 'fortiauto\app'

# --- find Python 3.9+ (prefer the py launcher; "python" may be the Store stub)
function Find-Python([string]$launcher, [string[]]$extra) {
    if (-not (Get-Command $launcher -ErrorAction SilentlyContinue)) { return $null }
    # PS 5.1 turns a native command's stderr into a terminating error under
    # 'Stop' (e.g. "No suitable Python runtime found"); treat that as "not found".
    $ErrorActionPreference = 'Continue'
    # no double quotes in the code: Windows PowerShell 5.1 mangles them
    $code = 'import sys; print(sys.executable if sys.version_info >= (3, 9) else 0)'
    try { $out = & $launcher @extra -c $code 2>$null } catch { return $null }
    if ($LASTEXITCODE -eq 0 -and $out -and "$out" -ne '0') { return "$out".Trim() }
    return $null
}
$exe = Find-Python 'py' @('-3')
if (-not $exe) { $exe = Find-Python 'python' @() }
if (-not $exe) { throw 'Python 3.9+ not found. Install it from https://www.python.org/downloads/ and re-run.' }
$pythonw = Join-Path (Split-Path $exe) 'pythonw.exe'
if (-not (Test-Path $pythonw)) { $pythonw = $exe }
Write-Host "Python:  $pythonw"

# --- copy the package (replaces an older copy)
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Remove-Item -Recurse -Force (Join-Path $dest 'fortiauto') -ErrorAction SilentlyContinue
Copy-Item -Recurse (Join-Path $repo 'fortiauto') $dest
Write-Host "Copied:  $dest\fortiauto"

# Stop a previous instance so the new code is used.
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

$user = "$env:USERDOMAIN\$env:USERNAME"
try {
    $action = New-ScheduledTaskAction -Execute $pythonw -Argument '-S -m fortiauto run' -WorkingDirectory $dest
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -Priority 7
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
        -Principal $principal -Description 'Keeps the FortiGate captive portal logged in (fortiauto).' -Force | Out-Null
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Task:    '$TaskName' registered and started (runs at every logon)"
}
catch {
    Write-Warning "Task Scheduler refused ($($_.Exception.Message)); using a Startup-folder shortcut instead."
    $lnk = Join-Path ([Environment]::GetFolderPath('Startup')) "$TaskName.lnk"
    $sh = New-Object -ComObject WScript.Shell
    $s = $sh.CreateShortcut($lnk)
    $s.TargetPath = $pythonw
    $s.Arguments = '-S -m fortiauto run'
    $s.WorkingDirectory = $dest
    $s.WindowStyle = 7
    $s.Save()
    Start-Process -FilePath $pythonw -ArgumentList '-S -m fortiauto run' -WorkingDirectory $dest -WindowStyle Hidden
    Write-Host "Startup: $lnk (started now, and at every logon)"
}

Write-Host ''
if (-not $NoPrompt) {
    $ans = Read-Host 'Save your portal username/password now? (stored in Windows Credential Manager) [Y/n]'
    if ($ans -notmatch '^[nN]') {
        Push-Location $dest
        try { & $exe -S -m fortiauto set-credentials } finally { Pop-Location }
    }
}
Write-Host ''
Write-Host 'Done. fortiauto now runs in the background and at every logon.'
Write-Host 'Change your saved login:'
Write-Host "  cd `"$dest`"; & `"$exe`" -m fortiauto set-credentials"
Write-Host 'Check on it any time:'
Write-Host "  cd `"$dest`"; & `"$exe`" -m fortiauto status"
