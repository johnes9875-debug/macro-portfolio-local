@echo off
REM Propose paper orders from the latest run now, even if this month's were already proposed.
cd /d "%~dp0\.."
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
set PYTHONPATH=%CD%\src
python -m macro_portfolio.paper propose --force
pause
