from __future__ import annotations

import ctypes
import os
import sys
import tkinter as tk
from tkinter import messagebox

from ytdlp_windows import VERSION


def main() -> int:
    if "--version" in sys.argv:
        print(VERSION)
        return 0
    if os.name == "nt":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    from ytdlp_windows.ui import App

    smoke = "--smoke-test" in sys.argv
    mutex = None
    if os.name == "nt" and not smoke:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel.CreateMutexW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        mutex = kernel.CreateMutexW(None, False, "Local\\YtDlpWindows")
        if mutex and ctypes.get_last_error() == 183:
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("YtDlp", "YtDlp è già aperto.", parent=root)
            root.destroy()
            kernel.CloseHandle(mutex)
            return 0
    root = tk.Tk()
    try:
        app = App(root, smoke=smoke)
        if smoke:
            root.update()
            app.url.set("https://example.com/video.mp4")
            app.handle("progress", {"percent": 42.5, "downloaded": 425000, "total": 1000000,
                                    "speed": 85000, "eta": 7, "finished": False})
            root.update()
            assert "42.5%" in app.status.get()
            assert float(app.bar["value"]) == 42.5
            assert app.entry.winfo_width() > 250
            from ytdlp_windows.formats import FORMATS
            app.format_choice.current(next(i for i, profile in enumerate(FORMATS) if profile.id == "mp3"))
            app.choose_format()
            assert app.format_id == "mp3"
            assert app.download_button.cget("text") == "Scarica audio"
            app.set_busy(True)
            assert str(app.format_choice.cget("state")) == "disabled"
            app.set_busy(False)
            assert str(app.format_choice.cget("state")) == "readonly"
            assert app.format_choice.winfo_width() > 250
            app.handle("cancelled", {"text": "Prova annullamento"})
            assert "annullato" in app.status.get()
            root.update()
            root.destroy()
        else:
            root.mainloop()
    finally:
        if mutex:
            kernel.CloseHandle(mutex)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
