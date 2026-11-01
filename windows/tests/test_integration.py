"""Only localhost media is downloaded; no third-party videos or accounts."""
from __future__ import annotations

import base64
from functools import partial
import hashlib
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
import shutil
import subprocess
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ytdlp_windows.download import DownloadJob
from ytdlp_windows.formats import FORMATS
from ytdlp_windows.github import GitHubClient
from ytdlp_windows.runtime import RuntimeManager, Tools
from ytdlp_windows.updater import extract_application


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


@unittest.skipUnless(os.name == "nt" and os.environ.get("YTDLP_INTEGRATION") == "1", "Opt-in real Windows download")
class IntegrationTests(unittest.TestCase):
    def test_published_update_can_be_found_and_verified(self):
        client = GitHubClient()
        release = client.check_update(current="0.0.0")
        self.assertIsNotNone(release)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = client.download(release.asset, root / "update.zip")
            executable = extract_application(archive, root)
            with executable.open("rb") as source:
                self.assertEqual(source.read(2), b"MZ")

    def test_official_executable_downloads_local_media(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = base64.b64decode(Path(__file__).with_name("fixture.mp4.b64").read_text())
            source = root / "sample.mp4"
            source.write_bytes(media)
            server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=root))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                events = []
                tools = RuntimeManager(root / "tools").ensure(threading.Event(), lambda *_: None)
                job = DownloadJob(lambda *event: events.append(event))
                with patch("ytdlp_windows.download.RuntimeManager.ensure", return_value=tools):
                    job.run(f"http://127.0.0.1:{server.server_port}/sample.mp4", root / "downloads")
                self.assertEqual(events[-1][0], "done", events)
                result = Path(events[-1][1]["path"])
                self.assertEqual(hashlib.sha256(result.read_bytes()).digest(), hashlib.sha256(media).digest())
                self.assertTrue(any(kind == "progress" for kind, _ in events))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


@unittest.skipUnless(os.environ.get("YTDLP_INTEGRATION") == "1" and
                     (os.name == "nt" or (shutil.which("yt-dlp") and shutil.which("ffmpeg"))),
                     "Opt-in real format conversions with yt-dlp and FFmpeg")
class FormatIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        cls.media = base64.b64decode(Path(__file__).with_name("fixture.mp4.b64").read_text())
        (cls.root / "sample.mp4").write_bytes(cls.media)
        cls.tools = (RuntimeManager(cls.root / "tools").ensure(threading.Event(), lambda *_: None)
                     if os.name == "nt" else Tools(Path(shutil.which("yt-dlp")),
                                                  Path(shutil.which("ffmpeg")), Path("deno")))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=cls.root))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.directory.cleanup()

    def download(self, source, destination, format_id):
        events = []
        job = DownloadJob(lambda *event: events.append(event))
        with patch("ytdlp_windows.download.RuntimeManager.ensure", return_value=self.tools):
            job.run(f"http://127.0.0.1:{self.server.server_port}/{source}", destination, format_id)
        self.assertEqual(events[-1][0], "done", events)
        result = Path(events[-1][1]["path"])
        probe = self.tools.ffmpeg.with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
        info = json.loads(subprocess.check_output([str(probe), "-v", "error", "-show_streams",
                                                  "-show_format", "-of", "json", str(result)]))
        return result, info

    def test_all_formats_and_repeated_download_preserve_previous_video(self):
        destination = self.root / "formats"
        video = None
        audio_codecs = {"mp3": "mp3", "wav": "pcm_s16le", "m4a": "aac",
                        "flac": "flac", "opus": "opus", "ogg": "vorbis"}
        for profile in FORMATS:
            with self.subTest(format=profile.id):
                result, info = self.download("sample.mp4", destination, profile.id)
                if profile.extension:
                    self.assertEqual(result.suffix, "." + profile.extension)
                streams = info["streams"]
                self.assertTrue(any(s["codec_type"] == "audio" for s in streams))
                self.assertEqual(any(s["codec_type"] == "video" for s in streams), not profile.audio)
                if profile.audio:
                    self.assertEqual(streams[0]["codec_name"], audio_codecs[profile.id])
                if profile.id == "mp4":
                    video = result
                if video is not None:
                    self.assertEqual(video.read_bytes(), self.media, "Un altro formato ha alterato il video già scaricato")
        again, _ = self.download("sample.mp4", destination, "mp3")
        self.assertEqual(again.suffix, ".mp3")
        self.assertEqual(video.read_bytes(), self.media)
        # Completed files belong in the destination, not among the intermediates.
        self.assertFalse(any(p.is_file() for p in (destination / ".ytdlp-tmp").rglob("*")))

    def test_mp4_selection_converts_a_webm_source(self):
        source = self.root / "source.webm"
        subprocess.run([str(self.tools.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
                        "-i", str(self.root / "sample.mp4"), "-c:v", "libvpx-vp9", "-c:a", "libopus",
                        str(source)], check=True, timeout=60)
        result, info = self.download("source.webm", self.root / "converted", "mp4")
        self.assertEqual(result.suffix, ".mp4")
        self.assertIn("mp4", info["format"]["format_name"].split(","))
        self.assertTrue(any(s["codec_type"] == "video" for s in info["streams"]))

    def test_separate_h264_and_aac_tracks_can_be_converted_to_webm(self):
        source = self.root / "streams.mpd"
        subprocess.run([str(self.tools.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
                        "-i", str(self.root / "sample.mp4"), "-map", "0", "-c", "copy",
                        "-f", "dash", str(source)], check=True, timeout=60)
        result, info = self.download("streams.mpd", self.root / "dash-converted", "webm")
        self.assertEqual(result.suffix, ".webm")
        self.assertTrue(any(s["codec_type"] == "video" for s in info["streams"]))
        self.assertTrue(any(s["codec_type"] == "audio" for s in info["streams"]))
