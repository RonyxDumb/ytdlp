"""Only localhost media is downloaded; no third-party videos or accounts."""
from __future__ import annotations

import base64
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ytdlp_windows.download import DownloadJob
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
