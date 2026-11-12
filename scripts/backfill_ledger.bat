@echo off
REM Record every archived run under outputs\runs into ledger\ (safe to re-run).
cd /d "%~dp0\.."
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
set PYTHONPATH=%CD%\src
python -m macro_portfolio.ledger backfill
python -m macro_portfolio.ledger push
