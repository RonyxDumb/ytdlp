from __future__ import annotations

import json
import math
import os
import subprocess
import threading
from collections import deque
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .formats import DEFAULT_FORMAT, get_format
from .github import Cancelled, check_cancel
from .resolver import Resolved, Resolver, USER_AGENT, validate_url
from .runtime import Emit, RuntimeManager, Tools

PROGRESS = "__YTDLP_PROGRESS__"
POSTPROCESS = "__YTDLP_POSTPROCESS__"
FILE = "__YTDLP_FILE__"


def build_command(tools: Tools, resolved: Resolved, destination: Path,
                  format_id: str = DEFAULT_FORMAT) -> list[str]:
    validate_url(resolved.url)
    profile = get_format(format_id)
    command = [str(tools.ytdlp), "--ignore-config", "--no-plugin-dirs", "--no-playlist",
               "--newline", "--no-colors", "--encoding", "utf-8", "--no-simulate",
               "--windows-filenames", "--trim-filenames", "180", "--no-overwrites", "--continue",
               "--socket-timeout", "20", "--retries", "5", "--fragment-retries", "5",
               "--progress", "--progress-delta", "0.2",
               "--progress-template", "download:" + PROGRESS + "%(progress)j",
               "--progress-template", "postprocess:" + POSTPROCESS + "%(progress)j",
               "--print", "after_move:" + FILE + "%(filepath)j",
               "--ffmpeg-location", str(tools.ffmpeg.parent),
               "--js-runtimes", "deno:" + str(tools.deno),
               "-P", str(destination),
               "-P", "temp:" + str(destination / ".ytdlp-tmp" / profile.id),
               "-o", "%(title).140B [%(id)s] [" + profile.id + "].%(ext)s"]
    italian = parse_qs(urlsplit(resolved.url).query).get("lang") == ["it"]
    command += profile.options(italian)
    if resolved.referer:
        command += ["--referer", resolved.referer, "--user-agent", USER_AGENT]
    if resolved.title:
        # Pass text through --replace-in-metadata, never through an output format string.
        # Escaping backslashes prevents re.sub from interpreting remote title text.
        command += ["--replace-in-metadata", "title", "^.*$", resolved.title.replace("\\", "\\\\")]
    return command + ["--", resolved.url]


def parse_line(line: str) -> tuple[str, dict]:
    line = line.strip()
    try:
        if line.startswith(FILE):
            return "file", {"path": json.loads(line[len(FILE):])}
        if line.startswith(POSTPROCESS):
            return "postprocess", {"text": "Conversione e finalizzazione del file…"}
        if line.startswith(PROGRESS):
            raw = json.loads(line[len(PROGRESS):])
            downloaded = raw.get("downloaded_bytes") or 0
            total = raw.get("total_bytes") or raw.get("total_bytes_estimate")
            percentage = downloaded * 100 / total if total else None
            if percentage is not None and not math.isfinite(percentage):
                percentage = None
            return "progress", {"percent": max(0, min(100, percentage)) if percentage is not None else None,
                                "downloaded": downloaded, "total": total,
                                "speed": raw.get("speed"), "eta": raw.get("eta"),
                                "finished": raw.get("status") == "finished"}
    except (ValueError, TypeError, AttributeError, ZeroDivisionError):
        return "log", {"text": "Risposta di progresso non riconosciuta."}
    return "log", {"text": line}


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True, timeout=15)
    else:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


class DownloadJob:
    def __init__(self, emit: Emit):
        self.emit = emit
        self.cancelled = threading.Event()
        self.process: subprocess.Popen | None = None
        self.thread: threading.Thread | None = None
        self.lock = threading.Lock()

    def start(self, url: str, destination: Path, format_id: str = DEFAULT_FORMAT) -> None:
        validate_url(url)
        get_format(format_id)
        self.thread = threading.Thread(target=self.run, args=(url, destination, format_id), daemon=True)
        self.thread.start()

    def cancel(self) -> None:
        self.cancelled.set()
        with self.lock:
            process = self.process
        if process is not None:
            threading.Thread(target=self._stop, args=(process,), daemon=True).start()

    def _stop(self, process):
        try:
            stop_process(process)
        except (OSError, subprocess.SubprocessError):
            try:
                process.kill()
            except OSError:
                pass

    def run(self, url: str, destination: Path, format_id: str = DEFAULT_FORMAT) -> None:
        try:
            check_cancel(self.cancelled)
            profile = get_format(format_id)
            destination.mkdir(parents=True, exist_ok=True)
            tools = RuntimeManager().ensure(self.cancelled, self.emit)
            self.emit("status", {"text": "Analisi dell'indirizzo…"})
            resolved = Resolver(self.cancelled).resolve(url)
            check_cancel(self.cancelled)
            with self.lock:
                check_cancel(self.cancelled)
                self.process = subprocess.Popen(
                    build_command(tools, resolved, destination, format_id), shell=False,
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    encoding="utf-8", errors="replace", bufsize=1,
                    creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0,
                )
            tail: deque[str] = deque(maxlen=12)
            result = ""
            for line in self.process.stdout:
                check_cancel(self.cancelled)
                kind, payload = parse_line(line)
                if kind == "file":
                    result = payload["path"]
                if kind == "log" and payload.get("text"):
                    tail.append(payload["text"])
                self.emit(kind, payload)
            code = self.process.wait()
            check_cancel(self.cancelled)
            if code != 0:
                raise RuntimeError("\n".join(tail) or f"yt-dlp è terminato con codice {code}.")
            if not result or not Path(result).is_file():
                raise RuntimeError("yt-dlp è terminato senza indicare un file completato. Consulta i dettagli.")
            if profile.extension and Path(result).suffix.lower() != "." + profile.extension:
                raise RuntimeError(f"Il file prodotto non è nel formato {profile.extension.upper()} richiesto.")
            self.emit("done", {"path": result})
        except Cancelled:
            if self.process is not None:
                self._stop(self.process)
            self.emit("cancelled", {"text": "Download annullato. I file parziali permettono di riprovare."})
        except Exception as error:
            if self.process is not None and self.process.poll() is None:
                self._stop(self.process)
            self.emit("error", {"text": str(error)})
        finally:
            if self.process is not None and self.process.stdout is not None:
                self.process.stdout.close()
