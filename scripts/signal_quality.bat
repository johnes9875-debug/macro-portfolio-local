@echo off
REM Re-score all recorded signals against what happened since (writes ledger\signal_quality*.csv/json).
cd /d "%~dp0\.."
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
set PYTHONPATH=%CD%\src
python -c "from macro_portfolio.runtime import repository_root; from macro_portfolio.signal_eval import evaluate; import json; print(json.dumps(evaluate(repository_root()), indent=1, default=float))"
pause
