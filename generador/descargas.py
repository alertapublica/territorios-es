"""Downloads with retries and a pause between requests. Never disables TLS verification."""
from __future__ import annotations

import hashlib
import hmac
import http.client
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

USER_AGENT = "territorios-es/0.3 (+https://github.com/alertapublica/territorios-es)"
PAUSE = 2.0

# Hosts that drop connections from GitHub Actions' IPs: read through a relay with a Spanish IP, signed
# with RELAY_CLAVE and located at RELAY_URL (repository secrets). Each host must also be in the relay's
# list of allowed hosts. Without the secrets they are read directly.
VIA_RELAY = {"datacloud.icgc.cat"}


def relay(url: str) -> tuple[str, dict[str, str]]:
    """URL and headers to read `url` with: through the relay if its host needs it and there is a key;
    otherwise direct. The signature, HMAC-SHA256(key, ts + newline + url), expires after 120 s, so it is
    computed on each attempt. GET only."""
    key, base = os.environ.get("RELAY_CLAVE"), os.environ.get("RELAY_URL")
    if not (key and base) or urllib.parse.urlsplit(url).hostname not in VIA_RELAY:
        return url, {}
    ts = str(int(time.time()))
    signature = hmac.new(key.encode(), f"{ts}\n{url}".encode(), hashlib.sha256).hexdigest()
    return base.rstrip("/") + "/?" + urllib.parse.urlencode({"url": url}), {"x-ts": ts, "x-firma": signature}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """For requests that carry a key in a header: urllib would resend it to wherever the server
    redirects, even another host or plain HTTP. The redirect becomes an error instead."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_NO_REDIRECT = urllib.request.build_opener(_NoRedirect)


class Download:
    def __init__(self, url: str, content: bytes):
        self.url = url
        self.content = content
        self.sha256 = hashlib.sha256(content).hexdigest()
        self.retrieved = date.today().isoformat()

    def record(self, **extra) -> dict:
        return {"url": self.url, "sha256": self.sha256, "bytes": len(self.content),
                "retrieved": self.retrieved, **extra}


def fetch(url: str, data: dict | None = None, accept: str | None = None, cache: Path | None = None,
          cache_name: str | None = None, attempts: int = 4, validate=None,
          headers: dict[str, str] | None = None) -> Download:
    """GET (or POST form data). With a cache folder, a file already there is reused. `validate`
    raises on a broken answer (e.g. JSON cut off by a server timeout), which is retried. `headers`
    go with the request (an API key, for example) and are never written anywhere; such a request does
    not follow redirects."""
    if cache and cache_name and (cache / cache_name).exists():
        return Download(url, (cache / cache_name).read_bytes())
    body = urllib.parse.urlencode(data).encode() if data else None
    extra = headers or {}
    headers = {**extra, "User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    error = None
    for attempt in range(attempts):
        if attempt:
            time.sleep(PAUSE * 2 ** attempt)
        try:
            target, signed = relay(url) if body is None else (url, {})
            request = urllib.request.Request(target, data=body, headers={**headers, **signed})
            with (_NO_REDIRECT.open if extra else urllib.request.urlopen)(request, timeout=180) as r:
                content = r.read()
            time.sleep(PAUSE)
            if validate:
                try:
                    validate(content)
                except ValueError as e:
                    error = e
                    continue
            if cache and cache_name:
                cache.mkdir(parents=True, exist_ok=True)
                (cache / cache_name).write_bytes(content)
            return Download(url, content)
        except urllib.error.HTTPError as e:
            error = e
            if e.code not in (429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException) as e:
            error = e
    raise RuntimeError(f"Could not download {url}: {error}")
