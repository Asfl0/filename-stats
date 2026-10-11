@echo off
REM ============================================================
REM  build.bat - one-click build entry (double-click to run)
REM  It uses the project-local portable Python (build\python).
REM  All text here is ASCII on purpose to avoid codepage issues.
REM ============================================================
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

setlocal
set "HERE=%~dp0"
set "PY=%HERE%python\python.exe"

if not exist "%PY%" (
    echo [build.bat] Portable Python not found at:
    echo             %PY%
    echo [build.bat] build.py will download it automatically.
    set "PY=python"
)

echo [build.bat] Using interpreter: %PY%
"%PY%" "%HERE%build.py" %*
set RC=%ERRORLEVEL%
echo [build.bat] Exit code: %RC%
endlocal
