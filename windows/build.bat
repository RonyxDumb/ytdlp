@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"
if errorlevel 1 (
  echo Compilazione fallita. Leggi l'errore sopra.
  pause
  exit /b 1
)
start "" "%~dp0dist"
pause
