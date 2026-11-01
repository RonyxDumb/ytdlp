"""GitHub credentials stay in Windows Credential Manager, outside settings.json."""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

TARGET = "YtDlp/GitHub/RonyxDumb-ytdlp-android"


class Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p), ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def _api():
    if os.name != "nt":
        raise OSError("Il gestore credenziali richiede Windows.")
    api = ctypes.WinDLL("advapi32", use_last_error=True)
    api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                             ctypes.POINTER(ctypes.POINTER(Credential))]
    api.CredReadW.restype = wintypes.BOOL
    api.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
    api.CredWriteW.restype = wintypes.BOOL
    api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    api.CredDeleteW.restype = wintypes.BOOL
    api.CredFree.argtypes = [ctypes.c_void_p]
    return api


def read_token() -> str:
    if os.name != "nt":
        return ""
    api = _api()
    pointer = ctypes.POINTER(Credential)()
    if not api.CredReadW(TARGET, 1, 0, ctypes.byref(pointer)):
        if ctypes.get_last_error() == 1168:  # ERROR_NOT_FOUND
            return ""
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        cred = pointer.contents
        return ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize).decode("utf-16-le")
    finally:
        api.CredFree(pointer)


def save_token(token: str) -> None:
    api = _api()
    if not token:
        if not api.CredDeleteW(TARGET, 1, 0) and ctypes.get_last_error() != 1168:
            raise ctypes.WinError(ctypes.get_last_error())
        return
    if len(token) > 1024 or any(char.isspace() for char in token):
        raise ValueError("Token GitHub non valido.")
    raw = token.encode("utf-16-le")
    blob = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    cred = Credential()
    cred.Type, cred.TargetName, cred.UserName = 1, TARGET, "GitHub"
    cred.Persist = 2  # CRED_PERSIST_LOCAL_MACHINE, scoped to this Windows user.
    cred.CredentialBlobSize, cred.CredentialBlob = len(raw), blob
    try:
        if not api.CredWriteW(ctypes.byref(cred), 0):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        ctypes.memset(blob, 0, len(raw))
