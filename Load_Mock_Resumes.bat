@echo off
cd /d "%~dp0"
call tools\_python.bat
if not defined PY (
    echo Python was not found. See the README.
    pause
    exit /b 1
)
"%PY%" tools\load_mock_resumes.py
echo.
pause
