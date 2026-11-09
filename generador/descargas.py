"""Downloads with retries and a pause between requests. Never disables TLS verification."""
from __future__ import annotations

import hashlib
import http.client
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

USER_AGENT = "territorios-es/0.1 (+https://github.com/alertapublica/territorios-es)"
PAUSE = 2.0


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
          cache_name: str | None = None, attempts: int = 4, validate=None) -> Download:
    """GET (or POST form data). With a cache folder, a file already there is reused. `validate`
    raises on a broken answer (e.g. JSON cut off by a server timeout), which is retried."""
    if cache and cache_name and (cache / cache_name).exists():
        return Download(url, (cache / cache_name).read_bytes())
    body = urllib.parse.urlencode(data).encode() if data else None
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    error = None
    for attempt in range(attempts):
        if attempt:
            time.sleep(PAUSE * 2 ** attempt)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=180) as r:
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
