from __future__ import annotations

import base64
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ytdlp_windows import RELEASE_ASSET
from ytdlp_windows.download import FILE, PROGRESS, DownloadJob, build_command, parse_line, stop_process
from ytdlp_windows.github import Asset, Cancelled, GitHubClient, GitHubError, choose_release, trusted_asset_url
from ytdlp_windows.resolver import Resolved, find_player, parse_player, supports, validate_url
from ytdlp_windows.runtime import RuntimeManager, Tools, extract_tool
from ytdlp_windows.updater import UPDATE_SCRIPT, extract_application


def release(version, **extra):
    return {"tag_name": "windows-v" + version, "draft": False, "prerelease": False,
            "assets": [{"name": RELEASE_ASSET, "url": "https://api.github.com/repos/a/b/releases/assets/1",
                        "size": 1234, "digest": "sha256:" + "a" * 64, "state": "uploaded"}], **extra}


class ReleaseTests(unittest.TestCase):
    def test_numeric_version_and_android_filter(self):
        android = release("99.0.0", tag_name="android-v99.0.0")
        result = choose_release([release("1.9.0"), android, release("1.10.0"), release("2.0.0", prerelease=True)], "1.0.0")
        self.assertEqual(result.version, "1.10.0")

    def test_equal_and_older_do_not_update(self):
        self.assertIsNone(choose_release([release("1.0.0"), release("0.9.9")], "1.0.0"))

    def test_draft_malformed_and_missing_asset_ignored(self):
        self.assertIsNone(choose_release([release("2.0.0", draft=True), release("3.0.0-rc1"), release("4.0.0", assets=[])]))

    def test_missing_digest_refused(self):
        raw = release("2.0.0")
        del raw["assets"][0]["digest"]
        with self.assertRaises(GitHubError):
            choose_release([raw])

    def test_pagination(self):
        client = GitHubClient()
        with patch.object(client, "json", side_effect=[[release("0.1.0")] * 100, [release("1.2.0")]]) as get:
            self.assertEqual(client.check_update().version, "1.2.0")
            self.assertEqual(get.call_count, 2)

    def test_asset_host_validation(self):
        for url in ("http://github.com/a", "https://api.github.com.evil.test/a", "https://evil.test/a", "https://x@api.github.com/a"):
            self.assertFalse(trusted_asset_url(url))
        self.assertTrue(trusted_asset_url("https://release-assets.githubusercontent.com/a"))

    def test_auth_header_not_forwarded_to_cdn(self):
        client = GitHubClient("test-token")
        redirect = urllib.error.HTTPError("https://api.github.com/asset", 302, "Found",
                                         {"Location": "https://release-assets.githubusercontent.com/file"}, None)
        with patch.object(client.opener, "open", side_effect=[redirect, io.BytesIO(b"ok")]) as get:
            client.open("https://api.github.com/asset", binary=True)
            self.assertEqual(get.call_args_list[0].args[0].get_header("Authorization"), "Bearer test-token")
            self.assertIsNone(get.call_args_list[1].args[0].get_header("Authorization"))

    def test_private_repository_error_explains_access(self):
        client = GitHubClient()
        error = urllib.error.HTTPError("https://api.github.com/repo", 404, "Not Found", {}, None)
        with patch.object(client.opener, "open", side_effect=error):
            with self.assertRaisesRegex(GitHubError, "Contents: Read-only"):
                client.open("https://api.github.com/repo")


class VerifiedDownloadTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.target = Path(self.directory.name) / "app.zip"
        self.content = b"verified package"
        self.asset = Asset("app.zip", "https://api.github.com/asset", len(self.content), hashlib.sha256(self.content).hexdigest())
        self.client = GitHubClient()

    def test_verified_file_committed_atomically(self):
        with patch.object(self.client, "open", return_value=io.BytesIO(self.content)):
            self.client.download(self.asset, self.target)
        self.assertEqual(self.target.read_bytes(), self.content)
        self.assertFalse(self.target.with_suffix(".zip.part").exists())

    def test_corrupt_file_does_not_replace_existing_target(self):
        self.target.write_bytes(b"previous")
        with patch.object(self.client, "open", return_value=io.BytesIO(b"x" * len(self.content))):
            with self.assertRaisesRegex(GitHubError, "SHA-256"):
                self.client.download(self.asset, self.target)
        self.assertEqual(self.target.read_bytes(), b"previous")
        self.assertFalse(self.target.with_suffix(".zip.part").exists())

    def test_cancelled_download_leaves_no_installation(self):
        cancelled = threading.Event()
        cancelled.set()
        with self.assertRaises(Cancelled):
            self.client.download(self.asset, self.target, cancel=cancelled)
        self.assertFalse(self.target.exists())

    def test_truncated_file_refused(self):
        with patch.object(self.client, "open", return_value=io.BytesIO(self.content[:2])):
            with self.assertRaises(GitHubError):
                self.client.download(self.asset, self.target)


class ResolverTests(unittest.TestCase):
    def config(self, host="vixcloud.cc", token="abc"):
        return f'''window.masterPlaylist = {{ params: {{'token': '{token}', 'expires': '123'}}, url: 'https://{host}/playlist/25?existing=1' }};'''

    def test_supported_domains_and_foreign_hosts(self):
        self.assertTrue(supports("https://vixcloud.cc/embed/25"))
        self.assertTrue(supports("https://vixcloud.co/embed/25"))
        self.assertTrue(supports("https://streamingcommunityz.day/it/watch/25"))
        self.assertFalse(supports("https://vixcloud.cc.evil.test/embed/25"))
        self.assertFalse(supports("https://other.example/embed/25"))

    def test_bad_input_rejected(self):
        for url in ("file:///C:/file", "--exec=x", "https://user:pass@example.com/", "https://example.com:abc/v", "https://example.com/\narg"):
            with self.assertRaises(ValueError):
                validate_url(url)

    def test_player_parameters_preserved(self):
        result = parse_player(self.config(), "https://vixcloud.cc/embed/25?canPlayFHD=1&scz=1&lang=it", "Test")
        params = urllib.parse.parse_qs(urllib.parse.urlsplit(result.url).query)
        self.assertEqual(params, {"existing": ["1"], "token": ["abc"], "expires": ["123"], "h": ["1"], "scz": ["1"], "lang": ["it"]})
        self.assertEqual(result.referer, "https://vixcloud.cc/embed/25?canPlayFHD=1&scz=1&lang=it")

    def test_legacy_host_and_base64_title(self):
        title = base64.b64encode("Video di prova".encode()).decode()
        result = parse_player(self.config("vixcloud.co"), "https://vixcloud.co/embed/25?t=" + urllib.parse.quote(title))
        self.assertEqual(result.title, "Video di prova")

    def test_playlist_host_and_missing_token_refused(self):
        for content in (self.config("evil.test"), self.config(token="")):
            with self.assertRaises(ValueError):
                parse_player(content, "https://vixcloud.cc/embed/25")

    def test_iframe_html_decoding(self):
        url = find_player('<iframe src="https://vixcloud.cc/embed/25?lang=it&amp;scz=1"></iframe>', "https://example.com")
        self.assertIn("lang=it&scz=1", url)


class DownloadTests(unittest.TestCase):
    def test_progress_known_and_unknown_size(self):
        kind, progress = parse_line(PROGRESS + json.dumps({"downloaded_bytes": 42, "total_bytes": 100}))
        self.assertEqual(kind, "progress")
        self.assertEqual(progress["percent"], 42)
        self.assertIsNone(parse_line(PROGRESS + '{"downloaded_bytes": 42}')[1]["percent"])

    def test_malformed_progress_does_not_crash(self):
        self.assertEqual(parse_line(PROGRESS + "not-json")[0], "log")

    def test_final_path_is_json_decoded(self):
        path = 'C:\\Users\\Nome Utente\\Downloads\\video è.mp4'
        self.assertEqual(parse_line(FILE + json.dumps(path)), ("file", {"path": path}))

    def test_arguments_are_not_shell_code(self):
        tools = Tools(Path("C:/tools/yt-dlp.exe"), Path("C:/tools/ffmpeg.exe"), Path("C:/tools/deno.exe"))
        url = "https://example.com/v?x=$(touch+bad)&y=1"
        command = build_command(tools, Resolved(url), Path("C:/Users/A & B/Download"))
        self.assertEqual(command[-2:], ["--", url])
        self.assertIn("C:/Users/A & B/Download", command)
        self.assertIn("--ignore-config", command)

    def test_remote_title_is_not_interpreted_as_format_string(self):
        tools = Tools(Path("yt-dlp.exe"), Path("ffmpeg.exe"), Path("deno.exe"))
        command = build_command(tools, Resolved("https://example.com/v", title="%(title)s & X\\1"), Path("out"))
        index = command.index("--replace-in-metadata")
        self.assertEqual(command[index + 2], "^.*$")
        self.assertEqual(command[index + 3], "%(title)s & X\\\\1")

    def test_cancel_before_start_prevents_child_creation(self):
        events = []
        job = DownloadJob(lambda *event: events.append(event))
        job.cancelled.set()
        with tempfile.TemporaryDirectory() as directory, patch("subprocess.Popen") as popen:
            job.run("https://example.com/video", Path(directory))
            popen.assert_not_called()
        self.assertEqual(events[-1][0], "cancelled")


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_update_extracts_only_expected_executable(self):
        archive = self.root / "update.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("../../outside.txt", b"bad")
            package.writestr("YtDlp.exe", b"MZ" + b"0" * 100_000)
        target = extract_application(archive, self.root)
        self.assertEqual(target.name, "YtDlp.exe")
        self.assertFalse((self.root.parent / "outside.txt").exists())

    def test_non_executable_update_refused(self):
        archive = self.root / "update.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("YtDlp.exe", b"no" + b"0" * 100_000)
        with self.assertRaises(GitHubError):
            extract_application(archive, self.root)

    def test_shared_ffmpeg_dlls_are_installed(self):
        archive = self.root / "ffmpeg.zip"
        payload = self.root / "payload"
        payload.mkdir()
        with zipfile.ZipFile(archive, "w") as package:
            for name in ("ffmpeg.exe", "ffprobe.exe", "avcodec-62.dll"):
                package.writestr("release/bin/" + name, b"binary")
            package.writestr("release/LICENSE.txt", b"license")
        extract_tool(archive, payload, "ffmpeg")
        self.assertTrue((payload / "avcodec-62.dll").is_file())
        self.assertTrue((payload / "licenses/LICENSE.txt").is_file())

    def test_runtime_ignores_incomplete_cached_installation(self):
        runtime = RuntimeManager(self.root)
        parent = self.root / "yt-dlp"
        parent.mkdir()
        (parent / "current.json").write_text('{"directory": "missing"}', "utf-8")
        self.assertIsNone(runtime._cached("yt-dlp"))

    @unittest.skipUnless(os.name == "nt", "PowerShell requires Windows")
    def test_update_script_parses(self):
        script = self.root / "update.ps1"
        script.write_text(UPDATE_SCRIPT, "utf-8-sig")
        command = "param($p) $t=$null; $e=$null; [System.Management.Automation.Language.Parser]::ParseFile($p,[ref]$t,[ref]$e) | Out-Null; if($e.Count){exit 1}"
        result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", "& {" + command + "}", str(script)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))


@unittest.skipUnless(os.name == "nt", "Windows-specific behavior")
class WindowsTests(unittest.TestCase):
    def test_credential_manager_roundtrip_and_delete(self):
        from ytdlp_windows import credentials
        with patch.object(credentials, "TARGET", "YtDlpTest/" + str(os.getpid())):
            try:
                credentials.save_token("test-local-credential")
                self.assertEqual(credentials.read_token(), "test-local-credential")
            finally:
                credentials.save_token("")
            self.assertEqual(credentials.read_token(), "")

    def test_cancel_stops_child_process_tree(self):
        process = subprocess.Popen([sys.executable, "-c", "import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); print(p.pid,flush=True); time.sleep(60)"], stdout=subprocess.PIPE, text=True)
        child = int(process.stdout.readline())
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x00100000, False, child)
        try:
            self.assertTrue(handle)
            stop_process(process)
            self.assertEqual(kernel.WaitForSingleObject(handle, 5000), 0)
            self.assertIsNotNone(process.poll())
        finally:
            if process.poll() is None:
                stop_process(process)
            if handle:
                kernel.CloseHandle(handle)


if __name__ == "__main__":
    unittest.main()
