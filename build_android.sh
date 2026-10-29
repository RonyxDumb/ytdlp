#!/usr/bin/env bash
set -euo pipefail
# Compila nel container per evitare problemi con i permessi dei file su Windows.
mkdir -p /tmp/ytdlp-build
cp -r app build.gradle settings.gradle gradle.properties /tmp/ytdlp-build/
cd /tmp/ytdlp-build
gradle --no-daemon testDebugUnitTest assembleDebug
mkdir -p /src/output
cp app/build/outputs/apk/debug/app-debug.apk /src/output/YtDlp.apk
printf '\nAPK pronta: output/YtDlp.apk\n'
