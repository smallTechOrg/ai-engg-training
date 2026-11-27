@echo off
rem Windows entry point: runs setup.ps1 without needing a changed PowerShell execution policy.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
exit /b %errorlevel%
