@echo off
rem Double-click to remove fortiauto, including your saved login and logs.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\uninstall-windows.ps1" -Purge
pause
