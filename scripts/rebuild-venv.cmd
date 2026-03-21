@echo off
setlocal

powershell -ExecutionPolicy Bypass -NoLogo -NoProfile -File "%~dp0rebuild-venv.ps1" %*

endlocal
