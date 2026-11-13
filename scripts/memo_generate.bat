@echo off
REM Order memos: write missing memos with Claude + web search (needs memos.api_enabled and ANTHROPIC_API_KEY).
cd /d "%~dp0\.."
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
set PYTHONPATH=%CD%\src
python -m macro_portfolio.memo generate %*
pause
