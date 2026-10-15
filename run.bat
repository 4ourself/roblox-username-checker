@echo off
title roblox username checker
chcp 65001 >nul
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py "%~dp0checker.py"
    goto end
)

where python >nul 2>nul
if %errorlevel%==0 (
    python "%~dp0checker.py"
    goto end
)

echo.
echo   python was not found on this computer.
echo   install it from https://www.python.org/downloads/
echo   and tick "Add python.exe to PATH" during the installation.
echo.

:end
echo.
pause >nul
