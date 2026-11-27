@echo off
rem Launcher for Windows:  run | run list | run 01.1 | run doctor
setlocal
cd /d "%~dp0"
where uv >nul 2>nul
if %errorlevel%==0 (
    uv run --quiet labkit %*
    exit /b %errorlevel%
)
if exist "%USERPROFILE%\.local\bin\uv.exe" (
    "%USERPROFILE%\.local\bin\uv.exe" run --quiet labkit %*
    exit /b %errorlevel%
)
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m labkit.cli %*
    exit /b %errorlevel%
)
echo This repo is not set up yet. Run:  setup
exit /b 2
