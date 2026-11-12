$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Run setup_windows.ps1 first." }

$TaskName = "MacroPortfolio_Close_Check"
$TaskCommand = '"' + $Python + '" -m macro_portfolio.scheduler'

# Windows checks hourly forever. Python decides whether a new NYSE session is actually due,
# so DST, U.S. holidays, weekends and early closes remain market-calendar driven.
& schtasks.exe /Create /TN $TaskName /TR $TaskCommand /SC HOURLY /MO 1 /F | Out-Null
if ($LASTEXITCODE -ne 0) { throw "schtasks.exe failed with exit code $LASTEXITCODE" }

Write-Host "Installed scheduled task: $TaskName" -ForegroundColor Green
Write-Host "Windows will check hourly; duplicate completed NYSE sessions are skipped automatically."
