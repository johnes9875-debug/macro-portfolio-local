@echo off
REM Show the paper account: NAV, cash, performance vs SPY, open orders.
cd /d "%~dp0\.."
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
set PYTHONPATH=%CD%\src
python -m macro_portfolio.paper status
pause
