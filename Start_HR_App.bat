@echo off
cd /d "%~dp0"
title HR resume matcher
call tools\_python.bat

if not defined PY (
    echo.
    echo Python was not found on this computer, and the "runtime" folder is not in this project.
    echo Either copy the WHOLE project folder including the "runtime" folder, or install Python 3.10 or newer from python.org.
    echo.
    pause
    exit /b 1
)

"%PY%" -c "import importlib.util as u, sys; sys.exit(any(u.find_spec(m) is None for m in ('streamlit','streamlit_pdf','pandas','openpyxl','pypdf','docx','mammoth')))" >nul 2>nul
if errorlevel 1 (
    echo Installing the required packages. This is needed only once and needs internet.
    "%PY%" -m pip install -r requirements.txt --quiet --disable-pip-version-check
    if errorlevel 1 (
        echo.
        echo Could not install the packages. Check the internet connection, or ask IT to allow pip.
        echo Alternatively copy the "runtime" folder from the computer where this already works.
        pause
        exit /b 1
    )
)

echo.
echo Starting the app. Your browser will open automatically.
echo Keep this window open while you work. Close it to stop the app.
echo New resumes added to the resumes folder are imported automatically and shown below.
echo.
"%PY%" run_app.py
pause
