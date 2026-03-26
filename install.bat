@echo off
title Voice Dispatch — Installer
echo.
echo Starting Voice Dispatch installer...
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if errorlevel 1 (
    echo.
    echo Installation failed. Check the output above for errors.
    echo.
)
pause
