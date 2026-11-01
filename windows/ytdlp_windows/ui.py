from __future__ import annotations

import math
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import VERSION
from .config import default_downloads, load_settings, save_settings
from .credentials import read_token, save_token
from .download import DownloadJob
from .github import Cancelled, GitHubClient, Release
from .resolver import validate_url
from .runtime import RuntimeManager
from .updater import launch_update, prepare_update

BG = "#101217"
CARD = "#1b1e26"
FIELD = "#242833"
TEXT = "#f1f3f7"
MUTED = "#a6aebe"
ACCENT = "#93b5ff"


def bytes_text(size) -> str:
    try:
        value = float(size)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(value):
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024


class App:
    def __init__(self, root: tk.Tk, smoke: bool = False):
        self.root = root
        self.smoke = smoke
        self.events: queue.Queue = queue.Queue()
        self.settings = {} if smoke else load_settings()
        self.job: DownloadJob | None = None
        self.release: Release | None = None
        self.busy = False
        self.checking = False
        self.closing = False
        self.check_after_busy = False
        self.output = ""
        self.token = ""
        if not smoke:
            try:
                self.token = read_token()
            except OSError:
                pass
        self.url = tk.StringVar()
        self.folder = tk.StringVar(value=self.settings.get("destination") or str(default_downloads()))
        self.status = tk.StringVar(value="Pronto per un nuovo download")
        self.detail = tk.StringVar(value="Il progresso apparirà qui")
        self.update_status = tk.StringVar(value=f"Versione {VERSION}")
        self.build()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(80, self.drain)
        if not smoke:
            root.after(1000, self.check_updates)

    def build(self):
        root = self.root
        root.title("YtDlp")
        root.geometry("820x650")
        root.minsize(700, 600)
        root.configure(bg=BG)
        root.option_add("*Font", "{Segoe UI} 10")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("TButton", background=FIELD, foreground=TEXT, borderwidth=0,
                        padding=(15, 10), font=("Segoe UI", 10))
        style.map("TButton", background=[("active", "#343b4b"), ("disabled", "#20232a")],
                  foreground=[("disabled", "#687181")])
        style.configure("Primary.TButton", background=ACCENT, foreground="#111b31", font=("Segoe UI", 10, "bold"))
        style.map("Primary.TButton", background=[("active", "#b1c9ff"), ("disabled", "#38465e")],
                  foreground=[("disabled", "#8493ad")])
        style.configure("TEntry", fieldbackground=FIELD, foreground=TEXT, insertcolor=TEXT,
                        borderwidth=0, padding=12)
        style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=FIELD,
                        borderwidth=0, lightcolor=ACCENT, darkcolor=ACCENT, thickness=9)
        outer = ttk.Frame(root, padding=(30, 26))
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(header, text="↓  YtDlp", font=("Segoe UI", 27, "bold")).pack(side="left")
        self.settings_button = ttk.Button(header, text="Impostazioni", command=self.preferences)
        self.settings_button.pack(side="right", pady=6)
        ttk.Label(outer, text="Un indirizzo. Il tuo video, nei Download.", style="Muted.TLabel").pack(anchor="w", pady=(4, 25))
        card = ttk.Frame(outer, style="Card.TFrame", padding=22)
        card.pack(fill="x")
        tk.Label(card, text="INDIRIZZO DEL VIDEO", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 10))
        row = ttk.Frame(card, style="Card.TFrame")
        row.pack(fill="x")
        self.entry = ttk.Entry(row, textvariable=self.url, font=("Segoe UI", 11))
        self.entry.pack(side="left", fill="x", expand=True, ipady=3)
        self.entry.bind("<Return>", lambda _: self.start_download())
        self.paste_button = ttk.Button(row, text="Incolla", command=self.paste)
        self.paste_button.pack(side="left", padx=(8, 0))
        progress_header = ttk.Frame(card, style="Card.TFrame")
        progress_header.pack(fill="x", pady=(23, 10))
        tk.Label(progress_header, textvariable=self.status, bg=CARD, fg=TEXT,
                 anchor="w", wraplength=600, justify="left").pack(side="left", fill="x", expand=True)
        self.bar = ttk.Progressbar(card, maximum=100)
        self.bar.pack(fill="x")
        tk.Label(card, textvariable=self.detail, bg=CARD, fg=MUTED, anchor="w",
                 wraplength=600, justify="left").pack(fill="x", pady=(10, 17))
        actions = ttk.Frame(card, style="Card.TFrame")
        actions.pack(fill="x")
        self.download_button = ttk.Button(actions, text="Scarica video", style="Primary.TButton", command=self.start_download)
        self.download_button.pack(side="left")
        self.cancel_button = ttk.Button(actions, text="Annulla", command=self.cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=8)
        self.open_button = ttk.Button(actions, text="Apri cartella", command=self.open_folder)
        self.open_button.pack(side="right")
        destination = ttk.Frame(outer)
        destination.pack(fill="x", pady=(18, 16))
        ttk.Label(destination, text="Salva in", style="Muted.TLabel").pack(anchor="w", pady=(0, 5))
        folder_row = ttk.Frame(destination)
        folder_row.pack(fill="x")
        self.folder_label = ttk.Label(folder_row, textvariable=self.folder, style="Muted.TLabel", wraplength=510)
        self.folder_label.pack(side="left", fill="x", expand=True)
        self.choose_button = ttk.Button(folder_row, text="Cambia…", command=self.choose_folder)
        self.choose_button.pack(side="right")
        updates = ttk.Frame(outer)
        updates.pack(fill="x", pady=(0, 14))
        ttk.Label(updates, textvariable=self.update_status, style="Muted.TLabel", wraplength=420).pack(side="left", fill="x", expand=True)
        self.check_button = ttk.Button(updates, text="Verifica aggiornamenti", command=self.check_updates)
        self.check_button.pack(side="right")
        self.update_button = ttk.Button(updates, text="Aggiorna app", command=self.install_update)
        # Show the update action only when a newer Windows release exists.
        bottom = ttk.Frame(outer)
        bottom.pack(fill="both", expand=True)
        ttk.Label(bottom, text="By Francesco Pio Pipino", style="Muted.TLabel", font=("Segoe UI", 9)).pack(side="bottom", anchor="w")
        self.log = tk.Text(bottom, height=4, bg=BG, fg=MUTED, relief="flat", wrap="word",
                           font=("Consolas", 9), state="disabled", highlightthickness=0)
        self.log.pack(fill="both", expand=True, pady=(0, 10))
        self.entry.focus_set()

    def emit(self, kind, payload):
        self.events.put((kind, payload))

    def append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n")
        if int(self.log.index("end-1c").split(".")[0]) > 160:
            self.log.delete("1.0", "40.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def set_progress(self, value=None):
        if value is None:
            if self.bar.cget("mode") != "indeterminate":
                self.bar.configure(mode="indeterminate")
                self.bar.start(14)
        else:
            self.bar.stop()
            self.bar.configure(mode="determinate", value=value)

    def set_busy(self, busy):
        self.busy = busy
        for button in (self.download_button, self.choose_button, self.paste_button, self.settings_button):
            button.configure(state="disabled" if busy else "normal")
        self.entry.configure(state="disabled" if busy else "normal")
        self.check_button.configure(state="disabled" if busy or self.checking else "normal")
        self.update_button.configure(state="disabled" if busy else "normal")
        self.cancel_button.configure(state="normal" if busy and self.job else "disabled")
        if not busy:
            self.job = None
            if self.closing:
                self.root.destroy()
            elif self.check_after_busy:
                self.check_after_busy = False
                self.root.after(100, self.check_updates)

    def paste(self):
        try:
            self.url.set(self.root.clipboard_get().strip())
            self.entry.focus_set()
        except tk.TclError:
            self.status.set("Gli appunti non contengono un indirizzo.")

    def choose_folder(self):
        folder = filedialog.askdirectory(parent=self.root, title="Cartella dei download", initialdir=self.folder.get())
        if folder:
            self.folder.set(folder)
            self.settings["destination"] = folder
            try:
                save_settings(self.settings)
            except OSError as error:
                messagebox.showerror("Impostazioni", str(error), parent=self.root)

    def open_folder(self):
        try:
            path = Path(self.folder.get())
            path.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(path)
        except OSError as error:
            messagebox.showerror("Cartella", str(error), parent=self.root)

    def start_download(self):
        if self.busy:
            return
        try:
            url = validate_url(self.url.get())
        except ValueError as error:
            self.status.set(str(error))
            self.entry.focus_set()
            return
        self.output = ""
        self.job = DownloadJob(self.emit)
        self.set_busy(True)
        self.status.set("Preparazione del download…")
        self.detail.set("Al primo avvio vengono scaricati gli strumenti ufficiali.")
        self.set_progress()
        self.job.start(url, Path(self.folder.get()))

    def cancel(self):
        if self.job:
            self.status.set("Annullamento in corso…")
            self.cancel_button.configure(state="disabled")
            self.job.cancel()

    def check_updates(self):
        if self.busy:
            self.check_after_busy = True
            return
        if self.checking:
            return
        self.checking = True
        self.check_button.configure(state="disabled")
        self.update_status.set("Verifica delle release GitHub…")
        token = self.token

        def worker():
            try:
                release = GitHubClient(token).check_update()
                self.emit("update_result", {"release": release})
            except Exception as error:
                self.emit("update_error", {"text": str(error)})
        threading.Thread(target=worker, daemon=True).start()

    def install_update(self):
        if self.busy or not self.release:
            return
        if not messagebox.askyesno("Aggiorna YtDlp", f"Installare la versione {self.release.version}?\n"
                                  "L'app verrà chiusa e riaperta. I download salvati restano disponibili.", parent=self.root):
            return
        self.set_busy(True)
        self.status.set("Download dell'aggiornamento…")
        self.set_progress()
        release, token = self.release, self.token

        def worker():
            try:
                manifest = prepare_update(GitHubClient(token), release, self.emit)
                self.emit("update_ready", {"manifest": manifest})
            except Exception as error:
                self.emit("error", {"text": str(error)})
        threading.Thread(target=worker, daemon=True).start()

    def refresh_tools(self, window):
        if self.busy:
            return
        window.destroy()
        self.set_busy(True)
        self.status.set("Aggiornamento degli strumenti…")
        self.set_progress()

        def worker():
            try:
                RuntimeManager().ensure(threading.Event(), self.emit, refresh=True)
                self.emit("tools_done", {})
            except Exception as error:
                self.emit("error", {"text": str(error)})
        threading.Thread(target=worker, daemon=True).start()

    def preferences(self):
        window = tk.Toplevel(self.root)
        window.title("Impostazioni · YtDlp")
        window.configure(bg=BG)
        window.geometry("600x375")
        window.resizable(False, False)
        window.transient(self.root)
        frame = ttk.Frame(window, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Aggiornamenti da GitHub", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Il repository è privato. Usa un fine-grained token con accesso a\n"
                  "RonyxDumb/ytdlp-android e permesso Contents: Read-only.\n"
                  "Il token viene salvato nel Gestore credenziali di Windows.",
                  style="Muted.TLabel", justify="left").pack(anchor="w", pady=(10, 16))
        token = tk.StringVar(value=self.token)
        ttk.Entry(frame, textvariable=token, show="•").pack(fill="x")
        ttk.Label(frame, text="Lascia vuoto e salva per rimuovere il token.", style="Muted.TLabel").pack(anchor="w", pady=8)

        def save():
            try:
                value = token.get().strip()
                save_token(value)
                self.token = value
                window.destroy()
                self.check_updates()
            except (OSError, ValueError) as error:
                messagebox.showerror("Credenziali", str(error), parent=window)
        ttk.Button(frame, text="Salva", command=save, style="Primary.TButton").pack(anchor="e", pady=(4, 18))
        ttk.Button(frame, text="Aggiorna motore yt-dlp e strumenti", command=lambda: self.refresh_tools(window)).pack(fill="x")
        window.grab_set()

    def drain(self):
        try:
            # Limit work per frame so a noisy extractor cannot starve the UI.
            for _ in range(100):
                kind, payload = self.events.get_nowait()
                self.handle(kind, payload)
        except queue.Empty:
            pass
        try:
            if self.root.winfo_exists():
                self.root.after(80, self.drain)
        except tk.TclError:
            pass  # The update/close event may have destroyed the window.

    def handle(self, kind, payload):
        if kind == "status":
            self.status.set(payload["text"])
            self.set_progress()
        elif kind in {"prepare", "update_progress"}:
            self.status.set(payload["text"])
            self.set_progress(payload["percent"])
        elif kind == "progress":
            percent = payload["percent"]
            self.set_progress(percent)
            self.status.set("Download in corso" + (f" · {percent:.1f}%" if percent is not None else ""))
            eta = payload.get("eta")
            time_left = f"{int(eta) // 60:02d}:{int(eta) % 60:02d}" if isinstance(eta, (int, float)) and math.isfinite(eta) else "—"
            self.detail.set(f"{bytes_text(payload['downloaded'])} / {bytes_text(payload.get('total'))}"
                            f"   ·   {bytes_text(payload.get('speed'))}/s   ·   Tempo rimasto {time_left}")
            if payload.get("finished"):
                self.status.set("Traccia ricevuta · finalizzazione…")
        elif kind == "postprocess":
            self.status.set(payload["text"])
            self.set_progress()
        elif kind == "log":
            if payload.get("text"):
                self.append_log(payload["text"])
        elif kind == "file":
            self.output = payload["path"]
        elif kind == "done":
            self.set_progress(100)
            self.status.set("Download completato")
            self.detail.set(Path(payload["path"]).name)
            self.set_busy(False)
        elif kind == "tools_done":
            self.set_progress(0)
            self.status.set("Motore e strumenti aggiornati")
            self.detail.set("Pronto per un nuovo download")
            self.set_busy(False)
        elif kind in {"error", "cancelled"}:
            self.set_progress(0)
            self.status.set("Download annullato" if kind == "cancelled" else "Operazione non riuscita")
            self.detail.set(payload["text"][:240])
            self.append_log(payload["text"])
            self.set_busy(False)
        elif kind == "update_result":
            self.checking = False
            self.release = payload["release"]
            self.check_button.configure(state="disabled" if self.busy else "normal")
            if self.release:
                self.update_status.set(f"Nuova versione {self.release.version} disponibile")
                self.update_button.pack(side="right", padx=(0, 8))
                self.update_button.configure(state="disabled" if self.busy else "normal")
            else:
                self.update_status.set(f"Versione {VERSION} · app aggiornata")
                self.update_button.pack_forget()
        elif kind == "update_error":
            self.checking = False
            self.check_button.configure(state="disabled" if self.busy else "normal")
            self.update_status.set(f"Versione {VERSION} · verifica non disponibile")
            self.append_log(payload["text"])
        elif kind == "update_ready":
            try:
                launch_update(payload["manifest"])
                self.root.destroy()
            except OSError as error:
                self.handle("error", {"text": str(error)})

    def close(self):
        if self.busy:
            if self.job:
                if messagebox.askyesno("Chiudi YtDlp", "Annullare il download e chiudere?", parent=self.root):
                    self.closing = True
                    self.cancel()
            else:
                messagebox.showinfo("YtDlp", "Attendi il completamento dell'aggiornamento.", parent=self.root)
        else:
            self.root.destroy()
