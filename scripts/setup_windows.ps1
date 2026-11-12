$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Host "Python launcher 'py' was not found. Install Python 3.11 64-bit and rerun." -ForegroundColor Red
    exit 1
}

# Require Python 3.11 for the standard Windows build.
try {
    $Py311 = py -3.11 -c "import sys; print(sys.executable)"
} catch {
    Write-Host "Python 3.11 is not available through the Python launcher." -ForegroundColor Red
    Write-Host "Install Python 3.11 64-bit, reopen PowerShell, and rerun this script." -ForegroundColor Red
    exit 1
}

$VenvPython = ".\.venv\Scripts\python.exe"

# Rebuild a stale virtual environment if it was created with another Python version.
if (Test-Path $VenvPython) {
    $VenvVersion = & $VenvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($VenvVersion.Trim() -ne "3.11") {
        Write-Host "Existing .venv uses Python $VenvVersion; recreating with Python 3.11..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force .venv
    }
}

if (-not (Test-Path $VenvPython)) {
    py -3.11 -m venv .venv
}

& $VenvPython -m pip install --upgrade pip setuptools wheel
& $VenvPython -m pip install -r requirements.txt
& $VenvPython -m pip install -e .
& $VenvPython -m ipykernel install --user --name macroportfolio --display-name "MacroPortfolio Python 3.11"

Copy-Item .env.example .env -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Run tests:      scripts\run_tests.bat"
Write-Host "Start Jupyter:  scripts\start_jupyter.bat"
Write-Host "Production run: scripts\run_once.bat"
Write-Host "Dashboard:      scripts\start_dashboard.bat"
