@echo off
cd /d "%~dp0"
call tools\_python.bat
if not defined PY (
    echo Python was not found. See the README.
    pause
    exit /b 1
)
echo Close the HR app window first if it is running.
echo.
"%PY%" tools\reset_data.py
echo.
pause
