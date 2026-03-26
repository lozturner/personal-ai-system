@echo off
title Voice Dispatch System
cd /d "%~dp0"
call venv\Scripts\activate.bat
python -m voice_dispatch.watchdog_runner
pause
