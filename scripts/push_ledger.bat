@echo off
REM Commit and push ONLY the ledger/ folder (never .env or data/).
cd /d "%~dp0\.."
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
set PYTHONPATH=%CD%\src
python -m macro_portfolio.ledger push
