@echo off
setlocal
set SCRIPT_DIR=%~dp0

call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
python "%SCRIPT_DIR%app.py"

echo.
pause
