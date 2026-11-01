$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (!(Test-Path '.venv/Scripts/python.exe')) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Installa Python 3.13 x64 e aggiungilo al PATH.' }
    }
    $python = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    & $python -m pip install --disable-pip-version-check -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Installazione PyInstaller fallita.' }
    & $python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Test falliti.' }
    & $python tools/build.py
    if ($LASTEXITCODE -ne 0) { throw 'Build eseguibile fallita.' }
    Write-Host 'App pronta: windows/dist/YtDlp-Windows-x64.zip'
} finally {
    Pop-Location
}
