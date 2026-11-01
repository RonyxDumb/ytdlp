from __future__ import annotations

import hashlib
import json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import RELEASE_ASSET, RELEASE_PREFIX, REPOSITORY, VERSION


class Cancelled(Exception):
    pass


class GitHubError(RuntimeError):
    pass


def check_cancel(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise Cancelled()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def trusted_asset_url(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").lower()
    return (parsed.scheme == "https" and parsed.port in (None, 443)
            and not parsed.username and not parsed.password
            and (host in {"api.github.com", "github.com", "release-assets.githubusercontent.com",
                          "objects.githubusercontent.com", "github-releases.githubusercontent.com"}
                 or host.endswith(".githubusercontent.com")))


@dataclass(frozen=True)
class Asset:
    name: str
    url: str
    size: int
    sha256: str

    @classmethod
    def parse(cls, raw: dict) -> "Asset":
        digest = raw.get("digest") or ""
        if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
            raise GitHubError("La release non contiene una verifica SHA-256 valida.")
        if not trusted_asset_url(raw["url"]):
            raise GitHubError("Indirizzo dell'aggiornamento non valido.")
        return cls(raw["name"], raw["url"], int(raw["size"]), digest[7:].lower())


@dataclass(frozen=True)
class Release:
    version: str
    asset: Asset
    notes: str


def version_tuple(version: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Versione non valida")
    return tuple(map(int, version.split(".")))


def choose_release(releases: list[dict], current: str = VERSION) -> Release | None:
    candidates = []
    for release in releases:
        tag = release.get("tag_name", "")
        if release.get("draft") or release.get("prerelease") or not tag.startswith(RELEASE_PREFIX):
            continue
        version = tag[len(RELEASE_PREFIX):]
        try:
            number = version_tuple(version)
        except ValueError:
            continue
        raw_asset = next((a for a in release.get("assets", [])
                          if a.get("name") == RELEASE_ASSET and a.get("state") == "uploaded"), None)
        if raw_asset and number > version_tuple(current):
            candidates.append((number, version, raw_asset, release.get("body") or ""))
    if not candidates:
        return None
    _, version, asset, notes = max(candidates, key=lambda item: item[0])
    return Release(version, Asset.parse(asset), notes)


class GitHubClient:
    def __init__(self, token: str = ""):
        self.token = token
        self.opener = urllib.request.build_opener(NoRedirect())

    def open(self, url: str, binary: bool = False):
        for _ in range(6):
            if not trusted_asset_url(url):
                raise GitHubError("GitHub ha restituito una destinazione non valida.")
            headers = {"User-Agent": f"YtDlp-Windows/{VERSION}",
                       "Accept": "application/octet-stream" if binary else "application/vnd.github+json"}
            # Never forward a GitHub token to a release CDN, even after a redirect.
            if urllib.parse.urlsplit(url).hostname == "api.github.com":
                headers["X-GitHub-Api-Version"] = "2022-11-28"
                if self.token:
                    headers["Authorization"] = "Bearer " + self.token
            try:
                return self.opener.open(urllib.request.Request(url, headers=headers), timeout=30)
            except urllib.error.HTTPError as error:
                if error.code in (301, 302, 303, 307, 308):
                    location = error.headers.get("Location")
                    error.close()
                    if not location:
                        raise GitHubError("Redirect GitHub senza destinazione.") from None
                    url = urllib.parse.urljoin(url, location)
                    continue
                status = error.code
                error.close()
                if status == 404:
                    raise GitHubError("Repository privato o non accessibile. In Impostazioni inserisci un token "
                                      "GitHub con accesso al repository e permesso Contents: Read-only.") from None
                if status == 401:
                    raise GitHubError("Token GitHub non valido o scaduto. Aggiornalo nelle Impostazioni.") from None
                if status in (403, 429):
                    raise GitHubError("Accesso GitHub negato o limite di richieste raggiunto. "
                                      "Controlla i permessi del token o riprova più tardi.") from None
                raise GitHubError(f"GitHub ha risposto HTTP {status}.") from None
            except (urllib.error.URLError, TimeoutError, OSError):
                raise GitHubError("Connessione a GitHub non riuscita. Controlla Internet e riprova.") from None
        raise GitHubError("Troppi redirect da GitHub.")

    def json(self, path: str):
        with self.open("https://api.github.com/" + path.lstrip("/")) as response:
            raw = response.read(8_000_001)
            if len(raw) > 8_000_000:
                raise GitHubError("Risposta GitHub troppo grande.")
            return json.loads(raw)

    def check_update(self, current: str = VERSION) -> Release | None:
        releases = []
        for page in range(1, 21):
            batch = self.json(f"repos/{REPOSITORY}/releases?per_page=100&page={page}")
            if not isinstance(batch, list):
                raise GitHubError("Elenco release non valido.")
            releases.extend(batch)
            if len(batch) < 100:
                return choose_release(releases, current)
        raise GitHubError("Troppe release: verifica gli aggiornamenti dalla pagina GitHub.")

    def download(self, asset: Asset, target: Path,
                 progress: Callable[[int, int], None] = lambda *_: None,
                 cancel: threading.Event | None = None) -> Path:
        if asset.size <= 0 or asset.size > 1_000_000_000:
            raise GitHubError("Dimensione del pacchetto non valida.")
        partial = target.with_name(target.name + ".part")
        target.parent.mkdir(parents=True, exist_ok=True)
        digest, count = hashlib.sha256(), 0
        try:
            check_cancel(cancel)
            with self.open(asset.url, binary=True) as response, partial.open("wb") as output:
                while True:
                    check_cancel(cancel)
                    chunk = response.read(256 * 1024)
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > asset.size:
                        raise GitHubError("Il pacchetto supera la dimensione prevista.")
                    output.write(chunk)
                    digest.update(chunk)
                    progress(count, asset.size)
            check_cancel(cancel)
            if count != asset.size or digest.hexdigest() != asset.sha256:
                raise GitHubError("Verifica SHA-256 non riuscita: il file non verrà installato.")
            partial.replace(target)
            return target
        finally:
            partial.unlink(missing_ok=True)
