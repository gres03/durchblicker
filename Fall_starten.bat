@echo off
setlocal
set SCRIPT_DIR=%~dp0

if "%~1"=="" (
    echo Bitte eine JSON-Datei auf dieses Symbol ziehen ^(Rechtsklick -^> "Datei hier ablegen"^).
    pause
    exit /b 1
)

call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
python "%SCRIPT_DIR%start.py" %1

echo.
pause
