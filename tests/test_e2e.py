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
    assert data["schema"] == 3
    assert data["totals"]["properties"] > 0
    assert len(data["edges"]) % 2 == 0


@pytest.fixture(scope="module")
def browser():
    """One browser for the module. Playwright's sync API cannot be entered
    twice from the same thread, so tests that need their own page share this
    rather than launching again."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        instance = p.chromium.launch()
        yield instance
        instance.close()


@pytest.fixture(scope="module")
def page(browser, server):
    pg = browser.new_page()
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(server, wait_until="networkidle")
    pg.wait_for_selector(".row", timeout=15000)
    pg.errors = errors
    yield pg
    pg.close()


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


def test_brand_counts_and_bars_follow_operator_filter(page):
    page.fill("#q", "bpi")
    page.wait_for_timeout(300)
    row = page.locator(".row").first
    before = row.locator(".n").inner_text()
    before_width = row.locator(".bar").evaluate("node => node.style.width")
    page.click("#dd-chain > button")
    page.click('.dd-opt[data-facet="chain"][data-value="ayala"]')
    page.wait_for_timeout(300)
    row = page.locator(".row").first
    assert row.locator(".n").inner_text() != before
    assert row.locator(".bar").evaluate("node => node.style.width") != before_width
    page.click("#reset")
    page.wait_for_timeout(200)


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


def test_filter_scope_is_visible_and_region_is_geographic(page):
    page.click("#dd-chain > button")
    page.click('.dd-opt[data-facet="chain"][data-value="sm"]')
    page.wait_for_timeout(200)
    assert "Operator: SM" in page.locator("#scope").inner_text()
    assert page.locator('.dd-opt[data-facet="region"][data-value="smdc"]').count() == 0
    page.click("#reset")


def test_help_controls_open_explanations(page):
    helps = page.locator(".help")
    assert helps.count() == 6
    for i in range(helps.count()):
        helps.nth(i).click()
        assert page.locator(".help-popover").is_visible()
        assert page.locator(".help-popover").inner_text()
        page.locator("body").click(position={"x": 5, "y": 5})
        assert page.locator(".help-popover").count() == 0


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


def test_column_help_describes_the_current_view(page):
    """The right-hand columns mean different things per view, so their
    explanations have to change with it. Stale wording is worse than none."""
    page.click("#tab-brands")
    page.wait_for_timeout(250)
    page.click("#help-rank")
    assert "carry this brand" in page.locator(".help-popover").inner_text()
    page.locator("body").click(position={"x": 5, "y": 5})

    page.click("#tab-malls")
    page.wait_for_timeout(250)
    page.click("#help-rank")
    text = page.locator(".help-popover").inner_text()
    assert "listings this property publishes" in text
    assert "brand" not in text.split("A brand")[0]
    page.locator("body").click(position={"x": 5, "y": 5})

    # the Share column is the least self-evident thing on the page
    page.click("#help-share")
    assert page.locator(".help-popover").is_visible()
    assert "share of all listings" in page.locator(".help-popover").inner_text()
    page.locator("body").click(position={"x": 5, "y": 5})
    page.click("#tab-brands")
    page.wait_for_timeout(200)


def test_tooltips_are_legible_not_label_styled(page):
    """The popover sits inside .stat span and .thead, whose own span rules match
    it directly with higher specificity. When they win, the tooltip renders as
    tiny uppercase letter-spaced text and reads as a stray label rather than an
    explanation, which is indistinguishable from having no tooltip."""
    page.click(".stat .help")
    pop = page.locator(".help-popover")
    assert pop.is_visible()
    style = pop.evaluate(
        "n => { const c = getComputedStyle(n);"
        " return { t: c.textTransform, s: parseFloat(c.fontSize), l: c.letterSpacing }; }"
    )
    assert style["t"] == "none", f"tooltip is text-transformed: {style}"
    assert style["s"] >= 12, f"tooltip text too small: {style}"
    assert style["l"] == "normal", f"tooltip is letter-spaced: {style}"
    page.locator("body").click(position={"x": 5, "y": 5})


def test_operator_count_matches_the_data(page):
    """The subtitle used to hardcode the operator count and went stale when a
    chain was removed."""
    shown = int(page.locator("#opcount").inner_text())
    page.click("#dd-chain > button")
    assert page.locator('.dd-opt[data-facet="chain"]').count() == shown
    page.locator("body").click(position={"x": 5, "y": 5})


# ---------- map ----------


def _open_map(page):
    page.click("#tab-map")
    page.wait_for_selector("#mapPanel:not([hidden])", timeout=10000)
    # Leaflet is fetched on first use, so the first open is the slow one.
    page.wait_for_selector("#map .leaflet-marker-pane, #map .leaflet-overlay-pane path", timeout=20000)


def _plotted(page):
    return page.locator("#map .leaflet-overlay-pane path").count() + page.locator("#map .cluster").count()


def test_map_plots_the_properties(page):
    _open_map(page)
    assert page.locator("#error").is_hidden()
    assert _plotted(page) > 0, "map opened but drew nothing"
    shown = int(re.sub(r"[^0-9]", "", page.locator("#mapcount").inner_text()))
    total = json.loads((SITE / _bundle_name()).read_text())["totals"]["mapped"]
    assert shown == total
    page.click("#tab-brands")
    page.wait_for_timeout(200)


def test_map_respects_the_filters(page):
    """The map is the property result set drawn geographically, so a filter has
    to move it. A map that ignores the controls above it is worse than no map."""
    _open_map(page)
    before = int(re.sub(r"[^0-9]", "", page.locator("#mapcount").inner_text()))
    page.click("#dd-region > button")
    page.click('.dd-opt[data-facet="region"][data-value="visayas"]')
    page.wait_for_timeout(400)
    after = int(re.sub(r"[^0-9]", "", page.locator("#mapcount").inner_text()))
    assert 0 < after < before
    assert _plotted(page) > 0
    page.click("#reset")
    page.wait_for_timeout(300)
    page.click("#tab-brands")
    page.wait_for_timeout(200)


def test_map_reports_what_it_cannot_draw(page):
    """Properties without a resolvable coordinate are stated, not dropped."""
    data = json.loads((SITE / _bundle_name()).read_text())
    unplaced = data["totals"]["properties"] - data["totals"]["mapped"]
    _open_map(page)
    note = page.locator("#mapnote").inner_text()
    assert "Circle area shows listing count" in note
    if unplaced:
        assert "no resolvable location" in note
    assert "OpenStreetMap" in note
    page.click("#tab-brands")
    page.wait_for_timeout(200)


def test_brand_focus_moves_to_the_map(page):
    page.fill("#q", "jollibee")
    page.wait_for_timeout(300)
    page.locator(".row").first.click()
    page.wait_for_selector(".detail .chip--map", timeout=5000)
    expected = int(re.sub(r"[^0-9]", "", page.locator(".detail .chip--map").inner_text()))
    page.click(".detail .chip--map")
    page.wait_for_selector("#mapPanel:not([hidden])", timeout=10000)
    assert page.locator("#focus").is_visible()
    assert "jollibee" in page.locator("#focus").inner_text().lower()
    assert int(re.sub(r"[^0-9]", "", page.locator("#mapcount").inner_text())) == expected
    # the focus is a filter, so it must be dismissible from where it is shown
    page.click("#focus")
    page.wait_for_timeout(400)
    assert page.locator("#focus").is_hidden()
    page.fill("#q", "")
    page.wait_for_timeout(300)
    page.click("#tab-brands")
    page.wait_for_timeout(200)


def test_map_does_not_overflow_on_a_phone(page):
    page.set_viewport_size({"width": 375, "height": 720})
    _open_map(page)
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 0, f"page scrolls horizontally by {overflow}px with the map open"
    box = page.locator("#map").bounding_box()
    assert box["width"] <= 375 and box["height"] >= 280
    page.set_viewport_size({"width": 1280, "height": 900})
    page.click("#tab-brands")
    page.wait_for_timeout(200)


def test_map_library_is_not_loaded_until_the_map_is_opened(browser, server):
    """147 KB of Leaflet on a page nobody scrolls to the map on is a cost with
    no benefit, so it is injected on first use. This is what proves that."""
    pg = browser.new_page()
    try:
        requested: list[str] = []
        pg.on("request", lambda r: requested.append(r.url))
        pg.goto(server, wait_until="load")
        pg.wait_for_selector(".row", timeout=15000)
        assert not any("leaflet" in url for url in requested), "Leaflet loaded on first paint"
        pg.click("#tab-map")
        pg.wait_for_function("() => Boolean(window.L)", timeout=20000)
        assert any("leaflet.js" in url for url in requested)
    finally:
        pg.close()
