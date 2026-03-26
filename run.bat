@echo off
title Voice Dispatch — Control Panel
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File run.ps1
pause
