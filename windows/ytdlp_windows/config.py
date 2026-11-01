from __future__ import annotations

import json
import os
from pathlib import Path


def data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
    path = base / "YtDlp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_downloads() -> Path:
    # Respect the Windows Downloads known folder, including user redirection.
    if os.name == "nt":
        import ctypes
        import uuid

        guid = (ctypes.c_ubyte * 16).from_buffer_copy(
            uuid.UUID("374de290-123f-4565-9164-39c4925e467b").bytes_le
        )
        value = ctypes.c_void_p()
        shell = ctypes.WinDLL("shell32")
        shell.SHGetKnownFolderPath.argtypes = [ctypes.c_void_p, ctypes.c_uint32,
                                              ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        shell.SHGetKnownFolderPath.restype = ctypes.c_long
        if shell.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(value)) == 0:
            try:
                return Path(ctypes.wstring_at(value)) / "YtDlp"
            finally:
                ole = ctypes.WinDLL("ole32")
                ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
                ole.CoTaskMemFree(value)
    return Path.home() / "Downloads" / "YtDlp"


def load_settings() -> dict:
    try:
        value = json.loads((data_dir() / "settings.json").read_text("utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(value: dict) -> None:
    target = data_dir() / "settings.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), "utf-8")
    temporary.replace(target)
