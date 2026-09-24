@echo off
title Imperial Anti-Piracy Network
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel%==0 (
    python stacker.py %*
) else (
    py stacker.py %*
)

echo.
echo Closed. Press any key to exit.
pause >nul
