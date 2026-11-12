$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Streamlit = Join-Path $Root ".venv\Scripts\streamlit.exe"
if (-not (Test-Path $Streamlit)) { throw "Run setup_windows.ps1 first." }
$TaskName = "MacroPortfolio_Dashboard"
$Args = "run `"$Root\app.py`" --server.address 127.0.0.1 --server.port 8501"
$Action = New-ScheduledTaskAction -Execute $Streamlit -Argument $Args -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Starts local Macro Portfolio dashboard at logon" -Force | Out-Null
Write-Host "Installed dashboard autostart task. Open http://127.0.0.1:8501 after logon." -ForegroundColor Green
