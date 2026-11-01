"""Port of Android 1.2's public VixCloud resolver. Does not evaluate JavaScript."""
from __future__ import annotations

import base64
import html
import http.cookiejar
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser

from .github import check_cancel

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
PLAYER_HOSTS = {"vixcloud.co", "vixcloud.cc"}


def validate_url(url: str) -> str:
    url = url.strip()
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError:
        raise ValueError("Inserisci un indirizzo HTTP o HTTPS valido.") from None
    if (parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or any(ord(c) < 32 for c in url)
            or port is not None and not 0 < port <= 65535):
        raise ValueError("Inserisci un indirizzo HTTP o HTTPS valido, senza credenziali.")
    return url


def is_player(url: str) -> bool:
    parsed = urllib.parse.urlsplit(validate_url(url))
    return parsed.hostname.lower() in PLAYER_HOSTS and bool(re.fullmatch(r"/embed/\d+/?", parsed.path))


def supports(url: str) -> bool:
    parsed = urllib.parse.urlsplit(validate_url(url))
    host = parsed.hostname.lower()
    return is_player(url) or (bool(re.fullmatch(r"(?:www\.)?streamingcommunity[a-z0-9-]*\.[a-z.]+", host))
                              and bool(re.fullmatch(r"/(?:[a-z]{2}/)?(?:watch|iframe)/\d+/?", parsed.path)))


@dataclass(frozen=True)
class Resolved:
    url: str
    referer: str = ""
    title: str = ""


class Page(HTMLParser):
    def __init__(self, content: str):
        super().__init__(convert_charrefs=True)
        self.iframes: list[str] = []
        self.data: dict | None = None
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "iframe" and values.get("src"):
            self.iframes.append(values["src"])
        if values.get("data-page"):
            self.data = json.loads(values["data-page"])


def find_player(content: str, base_url: str) -> str:
    for iframe in Page(content).iframes:
        url = urllib.parse.urljoin(base_url, iframe)
        if is_player(url):
            return url
    raise ValueError("Il sito non ha fornito un player pubblico VixCloud.")


def with_query(url: str, params: list[tuple[str, str]]) -> str:
    parsed = urllib.parse.urlsplit(validate_url(url))
    query = parsed.query + ("&" if parsed.query else "") + urllib.parse.urlencode(params)
    return urllib.parse.urlunsplit(parsed._replace(query=query, fragment=""))


def parse_player(content: str, player_url: str, title: str = "Video") -> Resolved:
    if not is_player(player_url):
        raise ValueError("Indirizzo player inatteso.")
    match = re.search(r'''window\.masterPlaylist\s*=\s*\{\s*params\s*:\s*\{([\s\S]*?)\}\s*,\s*url\s*:\s*['"]([^'"]+)['"]''', content)
    if not match:
        raise ValueError("Configurazione VixCloud non riconosciuta: il sito potrebbe aver cambiato player.")
    playlist = match[2].replace("\\/", "/")
    parsed = urllib.parse.urlsplit(validate_url(playlist))
    if parsed.hostname.lower() not in PLAYER_HOSTS or not re.fullmatch(r"/playlist/\d+/?", parsed.path):
        raise ValueError("Destinazione playlist inattesa.")
    params = [(key, value) for key, value in re.findall(r'''['"]([a-zA-Z0-9_]+)['"]\s*:\s*['"]([^'"]*)['"]''', match[1]) if value]
    if not any(key == "token" for key, _ in params):
        raise ValueError("Token del player mancante.")
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(player_url).query)
    if query.get("canPlayFHD"):
        params.append(("h", "1"))
    if query.get("scz"):
        params.append(("scz", "1"))
    params.append(("lang", query.get("lang", ["en"])[0]))
    if title == "Video" and query.get("t"):
        try:
            title = base64.b64decode(query["t"][0], validate=True).decode("utf-8")
        except (ValueError, UnicodeError):
            pass
    return Resolved(with_query(playlist, params), player_url, title)


class HttpOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Resolver:
    def __init__(self, cancel: threading.Event):
        self.cancel = cancel
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), HttpOnlyRedirect())

    def get(self, url: str, referer: str = "") -> str:
        check_cancel(self.cancel)
        headers = {"User-Agent": USER_AGENT, "Cache-Control": "no-cache"}
        if referer:
            headers["Referer"] = referer
        request = urllib.request.Request(validate_url(url), headers=headers)
        chunks, size = [], 0
        with self.opener.open(request, timeout=20) as response:
            while True:
                check_cancel(self.cancel)
                chunk = response.read(65536)
                if not chunk:
                    break
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError("Pagina del player troppo grande.")
                chunks.append(chunk)
        return b"".join(chunks).decode("utf-8", errors="replace")

    def resolve(self, url: str) -> Resolved:
        validate_url(url)
        if not supports(url):
            return Resolved(url)
        title, player = "Video", url
        if not is_player(url):
            request = with_query(url, [("_ytdlp", str(time.time_ns()))]) if "/iframe/" in urllib.parse.urlsplit(url).path else url
            page = Page(self.get(request))
            if page.data:
                props = page.data.get("props", {})
                if props.get("redirectToLogin"):
                    raise ValueError("Questa pagina richiede autenticazione, non gestita dall'app.")
                title = (props.get("title") or {}).get("name", "Video")
                if props.get("episode"):
                    title += " - " + props["episode"].get("name", "Episodio")
                if not props.get("embedUrl"):
                    raise ValueError("La pagina non contiene l'indirizzo del player.")
                player = urllib.parse.urljoin(url, props["embedUrl"])
            else:
                player = next((urllib.parse.urljoin(url, item) for item in page.iframes
                               if is_player(urllib.parse.urljoin(url, item))), "")
                if not player:
                    raise ValueError("Il sito non ha fornito un player pubblico VixCloud.")
            if not is_player(player):
                fresh = with_query(player, [("_ytdlp", str(time.time_ns()))])
                player = find_player(self.get(fresh, url), player)
        return parse_player(self.get(player, url), player, title)
