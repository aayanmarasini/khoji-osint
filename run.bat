@echo off
chcp 65001 >nul
title KHOJI OSINT
where python >nul 2>nul
if %errorlevel%==0 (python "%~dp0khoji.py" %* & pause & exit /b)
where py >nul 2>nul
if %errorlevel%==0 (py "%~dp0khoji.py" %* & pause & exit /b)
echo Python is not installed. Get it from python.org and tick "Add python.exe to PATH".
pause
