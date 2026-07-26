"""Rate-limited, cached HTTP client shared by all scrapers.

Every response body is cached under the run's raw-data directory, so parser
iterations (and validation re-runs on the same day) never re-hit the sites.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
from pathlib import Path

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 mallscape-research/0.1"
)


class FetchError(Exception):
    pass


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        # 403: SM's WAF rate-limits sustained clients; blocks lift after a
        # cooldown, so back off hard and retry rather than dying mid-run
        return exc.response.status_code in (403, 429, 500, 502, 503, 504)
    return False


class Fetcher:
    def __init__(self, cache_dir: Path, rate: float = 3.0, timeout: float = 30.0):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = 1.0 / rate
        self._last_request = 0.0
        self.client = httpx.Client(
            headers={
                "User-Agent": USER_AGENT,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "*/*",
            },
            timeout=timeout,
            follow_redirects=True,
        )
        self.requests_made = 0
        self.cache_hits = 0

    def _cache_path(self, url: str, params: dict | None) -> Path:
        qs = urllib.parse.urlencode(sorted(params.items())) if params else ""
        key = hashlib.md5(f"{url}?{qs}".encode()).hexdigest()[:16]
        parsed = urllib.parse.urlparse(url)
        stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", parsed.netloc + parsed.path).strip("_")
        return self.cache_dir / f"{stem}__{key}"

    def _throttle(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    @retry(
        retry=retry_if_exception(_retryable),
        wait=wait_exponential(multiplier=2, min=5, max=300),
        stop=stop_after_attempt(8),
        reraise=True,
    )
    def _request(self, url: str, params: dict | None) -> str:
        self._throttle()
        resp = self.client.get(url, params=params)
        resp.raise_for_status()
        self.requests_made += 1
        return resp.text

    def get_text(self, url: str, params: dict | None = None, force: bool = False) -> str:
        cache = self._cache_path(url, params)
        if cache.exists() and not force:
            self.cache_hits += 1
            return cache.read_text(encoding="utf-8")
        body = self._request(url, params)
        cache.write_text(body, encoding="utf-8")
        return body

    def get_json(self, url: str, params: dict | None = None, force: bool = False):
        body = self.get_text(url, params, force=force)
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            # poisoned cache entry (e.g. an HTML error page) — drop and refetch once
            cache = self._cache_path(url, params)
            if cache.exists() and not force:
                cache.unlink()
                return self.get_json(url, params, force=True)
            raise FetchError(f"Non-JSON response from {url}: {body[:200]!r}") from exc

    def close(self) -> None:
        self.client.close()
