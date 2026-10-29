@echo off
setlocal
cd /d "%~dp0"
echo === YtDlp - Build Android ===
where docker >nul 2>nul
if errorlevel 1 (
 echo Installa Docker Desktop e avvialo, poi riapri questo file.
 pause
 exit /b 1
)
docker info >nul 2>nul
if errorlevel 1 (
 echo Avvia Docker Desktop e attendi che il motore sia pronto.
 pause
 exit /b 1
)
docker build -t ytdlp-android-builder .
if errorlevel 1 goto failed
docker run --rm -v "%cd%:/src" ytdlp-android-builder
if errorlevel 1 goto failed
echo APK pronta in output\YtDlp.apk
start "" "%cd%\output"
pause
exit /b 0
:failed
echo Build fallita. Leggi l'errore sopra e verifica la connessione Internet.
pause
exit /b 1
