@echo off
REM Approve the latest ledger\paper\orders\*_proposed.csv after you have edited it.
REM Orders fill at the next US market open after approval, on the next pipeline run.
cd /d "%~dp0\.."
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
set PYTHONPATH=%CD%\src
python -m macro_portfolio.paper approve %*
python -m macro_portfolio.ledger push
pause
