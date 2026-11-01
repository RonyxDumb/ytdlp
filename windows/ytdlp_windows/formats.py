"""Output profiles shared by the download worker and the format picker."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DownloadFormat:
    id: str
    label: str
    extension: str | None
    audio: bool
    description: str

    def options(self, italian: bool = False) -> list[str]:
        audio = "ba[format_id=audio-Italian]/" if italian else ""
        if self.audio:
            return ["-f", audio + "ba[language^=it]/ba/b", "--extract-audio",
                    "--audio-format", "vorbis" if self.id == "ogg" else self.id,
                    "--audio-quality", "0"]
        video = "bv*+ba[format_id=audio-Italian]/" if italian else ""
        options = ["-f", video + "bv*+ba[language^=it]/bv*+ba/b"]
        if self.id == "mp4":
            options += ["-S", "vcodec:h264,acodec:aac,ext:mp4:m4a",
                        "--merge-output-format", "mp4/mkv", "--recode-video", "mp4"]
        elif self.id == "mkv":
            options += ["--merge-output-format", "mkv", "--remux-video", "mkv"]
        elif self.id == "webm":
            options += ["-S", "vcodec:vp9,acodec:opus,ext:webm",
                        "--merge-output-format", "webm/mkv", "--recode-video", "webm"]
        return options


FORMATS = (
    DownloadFormat("mp4", "Video · MP4", "mp4", False, "Video e audio. Conversione in MP4 se necessaria."),
    DownloadFormat("mkv", "Video · MKV", "mkv", False, "Video e audio nel contenitore MKV, senza ricodifica."),
    DownloadFormat("webm", "Video · WebM", "webm", False, "Video e audio. La conversione in WebM può richiedere tempo."),
    DownloadFormat("auto", "Video · Automatico", None, False, "Formato scelto dal sito e da yt-dlp, senza conversione forzata."),
    DownloadFormat("mp3", "Solo audio · MP3", "mp3", True, "Solo audio, qualità variabile migliore. Conversione se necessaria."),
    DownloadFormat("wav", "Solo audio · WAV", "wav", True, "Audio PCM non compresso: file grandi, qualità della sorgente."),
    DownloadFormat("m4a", "Solo audio · M4A", "m4a", True, "Solo audio in M4A, con conversione AAC se necessaria."),
    DownloadFormat("flac", "Solo audio · FLAC", "flac", True, "Compressione senza perdita; non migliora la qualità della sorgente."),
    DownloadFormat("opus", "Solo audio · Opus", "opus", True, "Solo audio con compressione Opus."),
    DownloadFormat("ogg", "Solo audio · OGG", "ogg", True, "Solo audio Vorbis nel contenitore OGG."),
)
DEFAULT_FORMAT = "mp4"


def get_format(format_id: str) -> DownloadFormat:
    for profile in FORMATS:
        if profile.id == format_id:
            return profile
    raise ValueError("Formato di download non supportato.")
