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

import http.server
import re
import socketserver
from functools import partial
from pathlib import Path

from mallscape_core import config, storage
from mallscape_website import bundle as bundle_mod

BUNDLE_RE = re.compile(r'data-bundle="[^"]*"')
DATE_RE = re.compile(r'data-snapshot="[^"]*"')
STALE_BUNDLE = re.compile(r"^data-[0-9a-f]{12}\.json$")


def run(run_date: str) -> Path:
    site = config.SITE_DIR
    index = site / "index.html"
    if not index.exists():
        raise SystemExit(
            f"site template missing at {index}. The static assets are checked in, "
            f"not generated; restore them from git."
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
    print(f"[website] {name} ({size_kb:,.0f} KB) -> {site}")
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
