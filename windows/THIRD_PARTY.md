# Componenti di terze parti

L'eseguibile dell'interfaccia viene creato con Python/Tk e PyInstaller. I motori di download sono processi separati, scaricati dalle release dei rispettivi progetti al primo uso; non sono incorporati nei sorgenti o nello ZIP dell'app.

| Componente | Licenze e sorgenti |
| --- | --- |
| Python | PSF License Agreement: https://docs.python.org/3/license.html |
| Tcl/Tk | Licenze Tcl/Tk: https://www.tcl.tk/software/tcltk/license.html |
| PyInstaller | GPL-2.0-or-later con eccezione per le applicazioni generate: https://pyinstaller.org/en/stable/license.html |
| yt-dlp | Codice principale Unlicense; l'eseguibile ufficiale include componenti aggiuntivi e viene distribuito come GPLv3+: https://github.com/yt-dlp/yt-dlp/blob/master/README.md#licensing |
| Licenze incluse in yt-dlp | https://github.com/yt-dlp/yt-dlp/blob/master/THIRD_PARTY_LICENSES.txt |
| FFmpeg/FFprobe | Build GPL con librerie condivise: https://github.com/yt-dlp/FFmpeg-Builds e https://ffmpeg.org/legal.html |
| Deno | MIT; componenti aggiuntivi: https://github.com/denoland/deno/blob/main/LICENSE.md |

Versione, repository e digest degli strumenti effettivamente scaricati sono registrati accanto a ogni installazione, in `source.json`. I file di licenza presenti negli archivi sono mantenuti nella sottocartella `licenses/`. Le licenze Android preesistenti rimangono in `android/`.
