@echo off
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
python -m macro_portfolio.self_check
pause
