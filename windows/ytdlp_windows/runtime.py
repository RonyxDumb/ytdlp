"""Install official Windows tools on first use; never run partial downloads."""
from __future__ import annotations

import json
import shutil
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable

from .config import data_dir
from .github import Asset, GitHubClient, GitHubError, check_cancel

Emit = Callable[[str, dict], None]


@dataclass(frozen=True)
class Tools:
    ytdlp: Path
    ffmpeg: Path
    deno: Path


SPECS = {
    "yt-dlp": ("yt-dlp/yt-dlp", "yt-dlp.exe", "yt-dlp.exe"),
    "ffmpeg": ("yt-dlp/FFmpeg-Builds", "ffmpeg-master-latest-win64-gpl-shared.zip", "ffmpeg.exe"),
    "deno": ("denoland/deno", "deno-x86_64-pc-windows-msvc.zip", "deno.exe"),
}


def extract_tool(archive: Path, destination: Path, kind: str) -> None:
    """Flatten only runtime binaries and licenses; ignore paths supplied by the ZIP."""
    with zipfile.ZipFile(archive) as package:
        total = 0
        for member in package.infolist():
            if member.is_dir():
                continue
            path = PurePosixPath(member.filename.replace("\\", "/"))
            name = path.name
            lower = name.lower()
            binary = (lower in {"ffmpeg.exe", "ffprobe.exe"} or lower.endswith(".dll")) if kind == "ffmpeg" else lower == "deno.exe"
            license_file = lower.startswith(("license", "copying", "notice", "readme")) and path.suffix.lower() in {".txt", ".md", ""}
            if not binary and not license_file:
                continue
            total += member.file_size
            if member.file_size > 400_000_000 or total > 800_000_000:
                raise GitHubError("Archivio dello strumento troppo grande.")
            target = destination / (name if binary else "licenses/" + name)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise GitHubError("L'archivio contiene file duplicati.")
            with package.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    expected = {"ffmpeg.exe", "ffprobe.exe"} if kind == "ffmpeg" else {"deno.exe"}
    if any(not (destination / name).is_file() for name in expected):
        raise GitHubError("Archivio incompleto: mancano eseguibili necessari.")


class RuntimeManager:
    def __init__(self, root: Path | None = None):
        self.root = root or data_dir() / "tools"
        self.client = GitHubClient()  # Public tools do not receive the private repository token.

    def _cached(self, kind: str) -> Path | None:
        try:
            metadata = json.loads((self.root / kind / "current.json").read_text("utf-8"))
            path = (self.root / kind / metadata["directory"] / SPECS[kind][2]).resolve()
            if not path.is_relative_to((self.root / kind).resolve()) or not path.is_file():
                return None
            if kind == "ffmpeg" and not path.with_name("ffprobe.exe").is_file():
                return None
            return path
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def install(self, kind: str, cancel: threading.Event, emit: Emit, refresh: bool = False) -> Path:
        check_cancel(cancel)
        existing = self._cached(kind)
        if existing and not refresh:
            return existing
        emit("status", {"text": f"Preparazione di {kind}…"})
        repository, asset_name, executable = SPECS[kind]
        release = self.client.json(f"repos/{repository}/releases/latest")
        raw = next((a for a in release.get("assets", []) if a.get("name") == asset_name), None)
        if raw is None:
            raise GitHubError(f"La release ufficiale di {kind} non contiene il pacchetto Windows.")
        asset = Asset.parse(raw)
        directory = asset.sha256[:24]
        parent = self.root / kind
        final = parent / directory
        parent.mkdir(parents=True, exist_ok=True)
        # An interrupted installation is staged separately and never selected by current.json.
        with tempfile.TemporaryDirectory(prefix="prepare-", dir=parent) as temporary:
            stage = Path(temporary)
            package = stage / asset_name
            self.client.download(asset, package, lambda done, total: emit("prepare", {
                "text": f"Scaricamento {kind} · {done / 1048576:.1f} / {total / 1048576:.1f} MB",
                "percent": done * 100 / total,
            }), cancel)
            check_cancel(cancel)
            payload = stage / "payload"
            payload.mkdir()
            if package.suffix == ".zip":
                extract_tool(package, payload, kind)
            else:
                shutil.move(str(package), payload / executable)
            (payload / "source.json").write_text(json.dumps({
                "repository": repository, "release": release["tag_name"],
                "sha256": asset.sha256, "source": release["html_url"],
            }, indent=2), "utf-8")
            if not final.exists():
                payload.replace(final)
        check_cancel(cancel)
        pointer = parent / "current.tmp"
        pointer.write_text(json.dumps({"directory": directory}), "utf-8")
        pointer.replace(parent / "current.json")
        return final / executable

    def ensure(self, cancel: threading.Event, emit: Emit, refresh: bool = False) -> Tools:
        return Tools(*(self.install(kind, cancel, emit, refresh) for kind in SPECS))
