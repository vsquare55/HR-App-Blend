@echo off
cd /d "%~dp0"
echo This builds the "runtime" folder so the project runs on a computer WITHOUT Python.
echo Run it once on a computer where the app already works. It needs internet and takes a few minutes.
echo.
where py >nul 2>nul && (set "PY=py") || (set "PY=python")
"%PY%" tools\build_runtime.py
echo.
pause
