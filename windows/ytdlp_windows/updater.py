from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from .config import data_dir
from .github import GitHubClient, GitHubError, Release
from .runtime import Emit

# All paths are data in a JSON manifest, never interpolated into PowerShell code.
UPDATE_SCRIPT = r'''param([string]$Manifest)
$ErrorActionPreference = 'Stop'
$m = Get-Content -LiteralPath $Manifest -Raw -Encoding UTF8 | ConvertFrom-Json
$backup = $m.target + '.previous.exe'
$incoming = $m.target + '.incoming.exe'
$replaced = $false
try {
    $running = Get-Process -Id $m.pid -ErrorAction SilentlyContinue
    if ($running) { $running | Wait-Process -Timeout 120 -ErrorAction Stop }
    if (!(Test-Path -LiteralPath $m.source -PathType Leaf)) { throw 'Pacchetto mancante' }
    if ((Get-FileHash -LiteralPath $m.source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $m.hash) {
        throw 'Verifica del file preparato non riuscita'
    }
    Copy-Item -LiteralPath $m.source -Destination $incoming -Force
    Copy-Item -LiteralPath $m.target -Destination $backup -Force
    # A one-file application's bootloader may release its EXE just after Python exits.
    $moved = $false
    for ($attempt = 0; $attempt -lt 100; $attempt++) {
        try {
            Move-Item -LiteralPath $incoming -Destination $m.target -Force
            $moved = $true
            break
        } catch {
            if ($attempt -eq 99) { throw }
            Start-Sleep -Milliseconds 200
        }
    }
    if (!$moved) { throw 'Impossibile sostituire il file' }
    $replaced = $true
    Start-Process -FilePath $m.target -WorkingDirectory (Split-Path -Parent $m.target)
    Remove-Item -LiteralPath $m.stage -Recurse -Force -ErrorAction SilentlyContinue
} catch {
    if ($replaced -and (Test-Path -LiteralPath $backup)) {
        Copy-Item -LiteralPath $backup -Destination $m.target -Force -ErrorAction SilentlyContinue
    }
    $_ | Out-String | Set-Content -LiteralPath $m.log -Encoding UTF8
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "Aggiornamento non riuscito. La versione precedente è stata conservata.`nDettagli: " + $m.log,
        'YtDlp', 'OK', 'Error') | Out-Null
} finally {
    Remove-Item -LiteralPath $incoming -Force -ErrorAction SilentlyContinue
}
'''


def extract_application(archive: Path, destination: Path) -> Path:
    with zipfile.ZipFile(archive) as package:
        members = [m for m in package.infolist() if m.filename == "YtDlp.exe" and not m.is_dir()]
        if len(members) != 1 or not 100_000 <= members[0].file_size <= 200_000_000:
            raise GitHubError("La release non contiene un'applicazione Windows valida.")
        # Never extract arbitrary ZIP paths into the installation directory.
        target = destination / "YtDlp.exe"
        with package.open(members[0]) as source, target.open("wb") as output:
            shutil.copyfileobj(source, output)
    with target.open("rb") as executable:
        if executable.read(2) != b"MZ":
            target.unlink()
            raise GitHubError("Il pacchetto non contiene un eseguibile Windows.")
    return target


def prepare_update(client: GitHubClient, release: Release, emit: Emit) -> Path:
    import hashlib

    if os.name != "nt" or not getattr(sys, "frozen", False):
        raise RuntimeError("L'aggiornamento automatico è disponibile nell'app YtDlp.exe compilata.")
    current = Path(sys.executable).resolve()
    # Check write access before downloading or closing the current app.
    with tempfile.NamedTemporaryFile(prefix=".ytdlp-write-", dir=current.parent):
        pass
    stage = Path(tempfile.mkdtemp(prefix="update-", dir=data_dir()))
    try:
        archive = client.download(release.asset, stage / "update.zip", lambda done, total: emit("update_progress", {
            "percent": done * 100 / total, "text": f"Aggiornamento {release.version} · {done * 100 / total:.0f}%",
        }))
        incoming = extract_application(archive, stage)
        manifest = stage / "manifest.json"
        with incoming.open("rb") as source:
            executable_hash = hashlib.file_digest(source, "sha256").hexdigest()
        manifest.write_text(json.dumps({
            "pid": os.getpid(), "target": str(current), "source": str(incoming),
            "stage": str(stage), "log": str(data_dir() / "update-error.txt"),
            "hash": executable_hash,
        }), "utf-8")
        (stage / "update.ps1").write_text(UPDATE_SCRIPT, "utf-8-sig")
        return manifest
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def launch_update(manifest: Path) -> None:
    system = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    powershell = system / "System32/WindowsPowerShell/v1.0/powershell.exe"
    subprocess.Popen([str(powershell), "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
                      "-ExecutionPolicy", "Bypass", "-File", str(manifest.with_name("update.ps1")), str(manifest)],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                     close_fds=True)
