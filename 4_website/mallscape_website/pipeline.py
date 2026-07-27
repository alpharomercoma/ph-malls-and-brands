"""Stage 4 entry point: emit the data bundle and the page that reads it.

The static assets (``index.html``, ``styles.css``, ``app.js``) are checked into
``4_website/site/`` and are not generated. Only the data bundle is generated,
under a content-hashed filename, and ``index.html`` is rewritten to point at it.

That split is deliberate:

* the bundle name changes whenever the data changes, so a host can cache it
  immutably and a viewer always gets the newest data without a stale cache;
* the page itself stays reviewable in git as ordinary source rather than as a
  string inside a Python file.

The output directory is a plain folder of static files, which is exactly what
GitHub Pages, Vercel, or ``python -m http.server`` each want.
"""

from __future__ import annotations

import hashlib
import http.server
import re
import socketserver
import urllib.parse
from functools import partial
from pathlib import Path

from mallscape_core import config, storage
from mallscape_website import bundle as bundle_mod

BUNDLE_RE = re.compile(r'data-bundle="[^"]*"')
DATE_RE = re.compile(r'data-snapshot="[^"]*"')
TILES_RE = re.compile(r'data-tiles="[^"]*"')
TILE_ATTR_RE = re.compile(r'data-tile-attribution="[^"]*"')
TILE_REF_RE = re.compile(r'data-tile-referrer="[^"]*"')
# Scoped to the policy's own content attribute. A bare `img-src [^;]*;` also
# matches the words "img-src" in the comment above the tag, and rewrote that
# instead, leaving the real policy untouched.
CSP_RE = re.compile(r'(?s)(<meta http-equiv="Content-Security-Policy"\s+content=")([^"]*)(")')
IMG_SRC_RE = re.compile(r"img-src [^;]*;")
STALE_BUNDLE = re.compile(r"^data-[0-9a-f]{12}\.json$")

# Checked into 4_website/site/ and served from the page's own origin, because
# the CSP allows no remote script or style. A missing one is a broken map, so
# the build refuses rather than deploying a tab that fails when opened.
VENDORED = ("vendor/leaflet.js", "vendor/leaflet.css")

# Code assets keep stable names, and the deploy host serves them with a ten
# minute max-age. Without a version in the URL a deploy leaves visitors running
# the previous release's JavaScript against this release's page, with no
# symptom. The data bundle already solves this by being content-hashed; these
# get the same guarantee through a query string.
VERSIONED = ("app.js", "map.js", "styles.css", "vendor/leaflet.js", "vendor/leaflet.css")
ASSET_VERSION_RE = re.compile(r'data-assets="[^"]*"')
ASSET_QUERY_RE = re.compile(r'(href|src)="(styles\.css|app\.js)\?v=[^"]*"')


def asset_version(site: Path) -> str:
    """One short hash over every cacheable asset. Any change to any of them
    changes every asset URL, which is blunt and correct: they are deployed
    together and are only ever valid together."""
    digest = hashlib.sha256()
    for name in VERSIONED:
        digest.update((site / name).read_bytes())
    return digest.hexdigest()[:8]


def tile_origin(tile_url: str) -> str:
    """The scheme and host the tile template will request, for the CSP.

    Deriving this instead of writing it twice is the point: the policy and the
    URL cannot drift apart, and pointing MALLSCAPE_TILE_URL at another server
    keeps working without anyone remembering to edit the header.
    """
    parts = urllib.parse.urlsplit(tile_url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise SystemExit(
            f"MALLSCAPE_TILE_URL must be an absolute http(s) URL, got {tile_url!r}"
        )
    if "{z}" not in tile_url or "{x}" not in tile_url or "{y}" not in tile_url:
        raise SystemExit(
            f"MALLSCAPE_TILE_URL must be a tile template containing {{z}}, {{x}} "
            f"and {{y}}, got {tile_url!r}"
        )
    return f"{parts.scheme}://{parts.netloc}"


def run(run_date: str) -> Path:
    site = config.SITE_DIR
    index = site / "index.html"
    if not index.exists():
        raise SystemExit(
            f"site template missing at {index}. The static assets are checked in, "
            f"not generated; restore them from git."
        )
    missing = [name for name in VENDORED if not (site / name).exists()]
    if missing:
        raise SystemExit(
            f"vendored map assets missing from {site}: {', '.join(missing)}. "
            f"They are checked in; restore them from git."
        )

    digest, data = bundle_mod.build(run_date)
    name = f"data-{digest}.json"
    (site / name).write_text(bundle_mod.dumps(data))

    # drop superseded bundles so the deploy directory holds exactly one
    for old in site.glob("data-*.json"):
        if old.name != name and STALE_BUNDLE.match(old.name):
            old.unlink()

    html = index.read_text()
    html, n = BUNDLE_RE.subn(f'data-bundle="{name}"', html, count=1)
    if n != 1:
        raise SystemExit("index.html has no data-bundle attribute to update")
    html = DATE_RE.sub(f'data-snapshot="{run_date}"', html, count=1)

    # The tile URL and the policy that has to permit it are written from the
    # same value, in the same place, so no configuration change can leave the
    # page requesting an origin its own CSP blocks.
    origin = tile_origin(config.TILE_URL)
    version = asset_version(site)
    for pattern, replacement, what in (
        (ASSET_VERSION_RE, f'data-assets="{version}"', "data-assets attribute"),
        (TILES_RE, f'data-tiles="{config.TILE_URL}"', "data-tiles attribute"),
        (TILE_ATTR_RE, f'data-tile-attribution="{config.TILE_ATTRIBUTION}"', "data-tile-attribution attribute"),
        (TILE_REF_RE, f'data-tile-referrer="{config.TILE_REFERRER_POLICY}"', "data-tile-referrer attribute"),
    ):
        html, n = pattern.subn(replacement, html, count=1)
        if n != 1:
            raise SystemExit(f"index.html has no {what} to update")

    def rewrite_policy(match: re.Match) -> str:
        policy, n = IMG_SRC_RE.subn(f"img-src 'self' data: {origin};", match.group(2), count=1)
        if n != 1:
            raise SystemExit("the Content-Security-Policy in index.html has no img-src directive")
        return match.group(1) + policy + match.group(3)

    html, n = ASSET_QUERY_RE.subn(rf'\1="\2?v={version}"', html)
    if n != 2:
        raise SystemExit(
            f"expected styles.css and app.js to carry ?v= in index.html, rewrote {n}"
        )

    html, n = CSP_RE.subn(rewrite_policy, html, count=1)
    if n != 1:
        raise SystemExit("index.html has no Content-Security-Policy meta tag to update")
    index.write_text(html)

    # Keep a copy inside the snapshot so the run is self-describing, pruning
    # superseded copies for the same reason the site directory is pruned: a
    # directory holding several bundles cannot say which one is current.
    snapshot_dir = storage.stage_dir(run_date, storage.WEBSITE)
    for old in snapshot_dir.glob("data-*.json"):
        if old.name != name and STALE_BUNDLE.match(old.name):
            old.unlink()
    storage.write_text(run_date, storage.WEBSITE, name, bundle_mod.dumps(data))

    size_kb = (site / name).stat().st_size / 1024
    mapped = data["totals"]["mapped"]
    print(f"[website] {name} ({size_kb:,.0f} KB) -> {site}")
    print(f"[website] map: {mapped}/{data['totals']['properties']} properties plotted, tiles {origin}")
    print(f"[website] assets v{version}")
    return site


def serve(port: int | None = None) -> None:
    port = port or config.SITE_PORT
    directory = str(config.SITE_DIR)
    handler = partial(_QuietHandler, directory=directory)
    with socketserver.TCPServer(("", port), handler) as httpd:
        httpd.allow_reuse_address = True
        print(f"[website] serving {directory} at http://localhost:{port}")
        print("[website] press Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[website] stopped")


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Static handler that mirrors the caching and security headers the
    production hosts apply, so local behaviour matches deployed behaviour."""

    def end_headers(self):
        if self.path.startswith("/data-") and self.path.endswith(".json"):
            # content-hashed: safe to cache forever
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass
