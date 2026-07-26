"""End to end: the built site actually works in a browser.

These drive the real artifacts in `4_website/site`, so they catch what static
analysis cannot: a bundle the page cannot parse, a filter that returns nothing,
a layout that overflows on a phone. They are skipped when the site has not been
built or when Playwright is unavailable, so the default test run stays offline
and fast.

Run the full pipeline first:  uv run mallscape build
"""

from __future__ import annotations

import json
import re
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer

import pytest

from mallscape_core import config

SITE = config.SITE_DIR
pytestmark = pytest.mark.e2e

playwright = pytest.importorskip("playwright.sync_api", reason="playwright not installed")


def _bundle_name() -> str:
    html = (SITE / "index.html").read_text()
    m = re.search(r'data-bundle="([^"]+)"', html)
    assert m, "index.html has no data-bundle attribute"
    return m.group(1)


@pytest.fixture(scope="module")
def server():
    if not (SITE / "index.html").exists():
        pytest.skip("site not built; run `uv run mallscape build`")
    handler = partial(SimpleHTTPRequestHandler, directory=str(SITE))
    with TCPServer(("127.0.0.1", 0), handler) as httpd:
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
        httpd.shutdown()


def test_bundle_is_valid_and_referenced(server):
    """The page must point at a bundle that exists and parses."""
    name = _bundle_name()
    path = SITE / name
    assert path.exists(), f"index.html references {name}, which is not on disk"
    data = json.loads(path.read_text())
    assert data["schema"] == 1
    assert data["totals"]["properties"] > 0
    assert len(data["edges"]) % 2 == 0


@pytest.fixture(scope="module")
def page(server):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page()
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(server, wait_until="networkidle")
        pg.wait_for_selector(".row", timeout=15000)
        pg.errors = errors
        yield pg
        browser.close()


def test_loads_without_script_errors(page):
    assert page.errors == [], f"page errors: {page.errors}"
    assert page.locator("#app").is_visible()
    assert page.locator("#error").is_hidden()


def test_renders_only_a_window_of_rows(page):
    """11k results must not all reach the DOM."""
    total = int(re.sub(r"[^0-9]", "", page.locator("#count").inner_text()))
    assert total > 1000
    assert page.locator(".row").count() < 60


def test_search_filters(page):
    page.fill("#q", "jollibee")
    page.wait_for_timeout(300)
    assert page.locator(".row").count() > 0
    first = page.locator(".row").first.inner_text().lower()
    assert "jollibee" in first
    page.fill("#q", "")
    page.wait_for_timeout(300)


def test_no_results_state_is_explicit(page):
    page.fill("#q", "zzzzznotarealbrand")
    page.wait_for_timeout(300)
    assert page.locator("#empty").is_visible()
    page.fill("#q", "")
    page.wait_for_timeout(300)


def test_switching_view_changes_columns(page):
    # the header is uppercased by CSS, so compare case-insensitively
    page.click("#tab-malls")
    page.wait_for_timeout(200)
    assert page.locator("#col-3").inner_text().lower().startswith("listings")
    page.click("#tab-brands")
    page.wait_for_timeout(200)
    assert page.locator("#col-3").inner_text().lower().startswith("malls")


def test_no_horizontal_overflow_on_mobile(page):
    page.set_viewport_size({"width": 360, "height": 720})
    page.wait_for_timeout(200)
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
    )
    assert overflow is False
    page.set_viewport_size({"width": 1280, "height": 800})


def test_store_names_are_never_treated_as_markup(page):
    """Data is written with textContent, so a name containing tags stays text."""
    injected = page.evaluate(
        """() => {
            const cell = document.querySelector('.row .name');
            return cell ? cell.querySelectorAll('*').length : -1;
        }"""
    )
    assert injected == 0


def test_filters_are_multi_select_and_cross_filter(page):
    """Within a facet values OR together; across facets they AND."""
    page.click("#dd-chain > button")
    page.click('.dd-opt[data-facet="chain"][data-value="ayala"]')
    page.wait_for_timeout(250)
    one = int(re.sub(r"[^0-9]", "", page.locator("#count").inner_text()))

    page.click('.dd-opt[data-facet="chain"][data-value="sm"]')
    page.wait_for_timeout(250)
    two = int(re.sub(r"[^0-9]", "", page.locator("#count").inner_text()))
    assert two > one, "adding a second operator must widen the result set"

    page.click("#dd-region > button")
    page.click('.dd-opt[data-facet="region"][data-value="visayas"]')
    page.wait_for_timeout(250)
    narrowed = int(re.sub(r"[^0-9]", "", page.locator("#count").inner_text()))
    assert narrowed < two, "adding a region must narrow the result set"

    page.click("#reset")
    page.wait_for_timeout(250)
    assert page.locator("#reset").is_hidden()


def test_impossible_options_are_disabled_not_hidden(page):
    page.click("#dd-chain > button")
    page.click('.dd-opt[data-facet="chain"][data-value="starmall"]')
    page.wait_for_timeout(300)
    page.click("#dd-region > button")
    page.wait_for_timeout(150)
    options = page.locator('.dd-opt[data-facet="region"]')
    assert options.count() > 0
    # every option stays visible; unreachable ones are disabled
    assert page.locator('.dd-opt[data-facet="region"]:disabled').count() > 0
    page.click("#reset")
    page.wait_for_timeout(200)
