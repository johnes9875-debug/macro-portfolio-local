@echo off
REM Order memos: show each memo's verdict and whether it passes validation.
cd /d "%~dp0\.."
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
set PYTHONPATH=%CD%\src
python -m macro_portfolio.memo status %*
pause
