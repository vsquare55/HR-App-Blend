@echo off
rem Finds the Python to use and sets PY. Used by the other .bat files.
rem 1) the Python that travels inside this folder (runtime\python)  2) the "py" launcher  3) "python"
set "PY="
set "ROOT=%~dp0.."
if exist "%ROOT%\runtime\python\python.exe" (
    set "PY=%ROOT%\runtime\python\python.exe"
    set "PYTHONNOUSERSITE=1"
    goto :eof
)
where py >nul 2>nul && set "PY=py"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
