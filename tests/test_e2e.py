"""End to end: the built site actually works in a browser.

These drive the real artifacts in `4_website/site`, so they catch what static
analysis cannot: a bundle the page cannot parse, a filter that returns nothing,
a layout that overflows on a phone. They are skipped when the site has not been
built or when Playwright is unavailable, so the default test run stays offline
and fast.

Run the full pipeline first:  uv run mallscape build
"""

from __future__ import annotations

import base64
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
    assert data["schema"] == 4
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
    # The map is the default view, so there is no table row to wait for.
    pg.wait_for_selector("#app:not([hidden])", timeout=15000)
    pg.errors = errors
    yield pg
    pg.close()


def test_loads_without_script_errors(page):
    assert page.errors == [], f"page errors: {page.errors}"
    assert page.locator("#app").is_visible()
    assert page.locator("#error").is_hidden()


def test_renders_only_a_window_of_rows(page):
    """11k results must not all reach the DOM."""
    _open_brands(page)
    total = int(re.sub(r"[^0-9]", "", page.locator("#count").inner_text()))
    assert total > 1000
    assert page.locator(".row").count() < 60


def test_search_filters(page):
    _open_brands(page)
    page.fill("#q", "jollibee")
    page.wait_for_timeout(300)
    assert page.locator(".row").count() > 0
    first = page.locator(".row").first.inner_text().lower()
    assert "jollibee" in first
    page.fill("#q", "")
    page.wait_for_timeout(300)


def test_reach_and_its_denominator_follow_the_operator_filter(page):
    """Reach replaced an unlabelled bar. Both the count and the percentage have
    to move with the filters, and the header has to name what they divide by."""
    page.click("#tab-brands")
    page.wait_for_timeout(250)
    page.fill("#q", "bpi")
    page.wait_for_timeout(300)
    before = page.locator(".row").first.locator(".reach").inner_text()
    before_header = page.locator("#col-3").inner_text()
    page.click("#dd-chain > button")
    page.click('.dd-opt[data-facet="chain"][data-value="ayala"]')
    page.wait_for_timeout(400)
    assert page.locator(".row").first.locator(".reach").inner_text() != before
    header = page.locator("#col-3").inner_text()
    assert header != before_header
    assert "malls" in header.lower(), header
    page.click("#reset")
    page.fill("#q", "")
    page.wait_for_timeout(300)


def test_no_results_state_is_explicit(page):
    _open_brands(page)
    page.fill("#q", "zzzzznotarealbrand")
    page.wait_for_timeout(300)
    assert page.locator("#empty").is_visible()
    page.fill("#q", "")
    page.wait_for_timeout(300)


def test_map_is_the_default_view(browser, server):
    """The map is the landing view, and there are only two tabs: the property
    table was the map's side list with extra columns. Uses its own page so a
    fresh load is genuinely fresh."""
    pg = browser.new_page()
    try:
        pg.goto(server, wait_until="load")
        pg.wait_for_selector("#app:not([hidden])", timeout=15000)
        assert pg.locator(".tabs button").all_inner_texts() == ["Map", "Brands"]
        assert pg.locator("#tab-map").get_attribute("aria-selected") == "true"
        assert pg.locator("#mapPanel").is_visible()
        assert pg.locator("#listPanel").is_hidden()
    finally:
        pg.close()


def test_filter_scope_is_visible_and_region_is_geographic(page):
    page.click("#dd-chain > button")
    page.click('.dd-opt[data-facet="chain"][data-value="sm"]')
    page.wait_for_timeout(200)
    assert "Operator: SM" in page.locator("#scope").inner_text()
    assert page.locator('.dd-opt[data-facet="region"][data-value="smdc"]').count() == 0
    page.click("#reset")


def test_help_controls_open_explanations(page):
    _open_brands(page)
    helps = page.locator(".help")
    # three stat tiles plus the Reach column. The Share column and two tiles
    # were removed because they could not explain themselves.
    assert helps.count() == 4
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
    _open_brands(page)
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
    _open_brands(page)
    page.click("#help-rank")
    text = page.locator(".help-popover").inner_text()
    assert "carry this brand" in text
    # the denominator has to be stated, not implied: that was the whole failure
    # of the column this one replaced
    assert "matching your filters" in text
    assert "malls" in text
    page.locator("body").click(position={"x": 5, "y": 5})


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


def _open_brands(page):
    """Land on the brand table. The map is the default view, so any test that
    reads rows or column headers has to ask for this view explicitly."""
    if page.locator("#tab-brands").get_attribute("aria-selected") != "true":
        page.click("#tab-brands")
    page.wait_for_selector(".row", timeout=15000)


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


def test_map_library_is_injected_not_bundled(browser, server):
    """Leaflet is 147 KB and is injected at runtime rather than shipped in the
    critical path, so the page renders before it arrives. The map is now the
    default view, so it does load on first paint - but only after the app has
    painted, and never as a blocking tag in the document."""
    pg = browser.new_page()
    try:
        requested: list[str] = []
        pg.on("request", lambda r: requested.append(r.url))
        pg.goto(server, wait_until="load")
        pg.wait_for_selector("#app:not([hidden])", timeout=15000)
        served = (SITE / "index.html").read_text()
        assert "vendor/leaflet.js" not in served, "Leaflet is a blocking tag in the document"
        pg.wait_for_function("() => Boolean(window.L)", timeout=20000)
        assert any("leaflet.js" in url for url in requested)
    finally:
        pg.close()


def test_brand_query_reaches_the_map(page):
    """Searching a brand in the map view filters property names and finds
    nothing. The brand chips are the bridge, and the empty state has to say so
    rather than showing a blank map."""
    page.click("#tab-map")
    page.wait_for_selector("#mapPanel:not([hidden])", timeout=10000)
    page.fill("#q", "uniqlo")
    page.wait_for_timeout(500)
    hits = page.locator("#hits")
    assert hits.is_visible()
    assert "No property is named" in hits.inner_text()
    chip = hits.locator(".chip--hit").first
    expected = int(re.sub(r"[^0-9]", "", chip.inner_text()))
    chip.click()
    page.wait_for_timeout(1500)
    assert page.locator("#focus").is_visible()
    assert int(re.sub(r"[^0-9]", "", page.locator("#mapcount").inner_text())) == expected
    assert page.input_value("#q") == ""
    page.click("#focus")
    page.wait_for_timeout(400)


def test_stat_tiles_follow_the_filters(page):
    """Five static totals above a filtered table taught readers to distrust the
    numbers that did move."""
    page.click("#reset") if page.locator("#reset").is_visible() else None
    page.wait_for_timeout(300)
    before = page.locator(".stat b").first.inner_text()
    page.click("#dd-region > button")
    page.click('.dd-opt[data-facet="region"][data-value="visayas"]')
    page.wait_for_timeout(500)
    assert page.locator(".stat b").first.inner_text() != before
    assert page.locator(".stat").count() == 3
    page.click("#reset")
    page.wait_for_timeout(300)


def test_tiles_identify_the_page_without_leaking_the_path(page):
    """OpenStreetMap's usage policy requires a Referer or an identifying
    User-Agent, and a browser cannot set the second. The page sends no referrer
    at all, so tile requests arrived unattributable and were refused.

    The override is deliberately narrow: the document keeps `no-referrer`, and
    only the tile images opt into sending an origin. A blanket relaxation would
    leak the referrer to every future destination as well.
    """
    _open_map(page)
    policy = page.evaluate(
        "() => { const t = document.querySelector('#map img.leaflet-tile');"
        " return t && t.referrerPolicy; }"
    )
    assert policy == "strict-origin-when-cross-origin", (
        f"tile images must opt into sending an origin, got {policy!r}"
    )
    # the document-level default must stay restrictive
    meta = page.evaluate(
        "() => document.querySelector('meta[name=referrer]')?.content"
    )
    assert meta == "no-referrer", meta
    page.click("#tab-brands")
    page.wait_for_timeout(200)


def _dominant_colour(page, clip):
    """The most common pixel in a screenshot of `clip`, as 'r,g,b'.

    The screenshot is decoded by the browser that produced it. Reading pixels is
    the point: this bug is invisible to the DOM, so a test that asks the DOM
    anything cannot fail on it.
    """
    png = page.screenshot(clip=clip)
    return page.evaluate(
        """async (b64) => {
            const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
            const bitmap = await createImageBitmap(new Blob([bytes], { type: 'image/png' }));
            const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
            const ctx = canvas.getContext('2d');
            ctx.drawImage(bitmap, 0, 0);
            const { data } = ctx.getImageData(0, 0, bitmap.width, bitmap.height);
            const tally = new Map();
            for (let i = 0; i < data.length; i += 4) {
                const key = `${data[i]},${data[i + 1]},${data[i + 2]}`;
                tally.set(key, (tally.get(key) || 0) + 1);
            }
            return [...tally].sort((a, b) => b[1] - a[1])[0][0];
        }""",
        base64.b64encode(png).decode(),
    )


def _rgb(page, selector, prop="background-color"):
    css = page.evaluate(
        "([s, p]) => getComputedStyle(document.querySelector(s)).getPropertyValue(p)",
        [selector, prop],
    )
    return ",".join(re.findall(r"\d+", css)[:3])


def test_overlays_paint_above_the_map(page):
    """Leaflet numbers its own panes 400 to 700 and its controls 800. Those stay
    Leaflet's business only if something contains them, and nothing did:
    `.leaflet-container` is positioned with `z-index: auto`, so it opens no
    stacking context and all of it competed in the root context against ours.
    A dropdown at z-index 20 opened *behind* the tiles.

    Every DOM-level check passes while that is broken. The panel is visible,
    has a real bounding box, and even wins elementFromPoint, because
    `.leaflet-tile-container` sets `pointer-events: none` and hit testing
    therefore reaches straight through the pixels covering it. So this reads the
    pixels: inside an open panel, over the map, the dominant colour has to be
    the panel's own background.
    """
    _open_map(page)
    page.wait_for_timeout(600)          # let the tiles settle so the map is opaque
    surface = _rgb(page, ".dd-panel")
    map_box = page.locator("#map").bounding_box()

    for facet in ("chain", "region", "category"):
        page.click(f"#dd-{facet} > button")
        panel = page.locator(f"#dd-{facet} .dd-panel")
        assert panel.is_visible(), f"{facet} panel did not open"
        box = panel.bounding_box()
        overlap = box["y"] + box["height"] - map_box["y"]
        assert overlap > 20, (
            f"the {facet} panel stops {-overlap:.0f}px short of the map, so this "
            f"test would pass whether or not the bug is present"
        )
        # the strip of panel that hangs over the map, inset to avoid its border
        clip = {
            "x": box["x"] + 4,
            "y": map_box["y"] + 4,
            "width": box["width"] - 8,
            "height": min(overlap, 60) - 8,
        }
        assert _dominant_colour(page, clip) == surface, (
            f"the {facet} dropdown is painted behind the map"
        )
        page.locator("body").click(position={"x": 5, "y": 5})

    page.click("#tab-brands")
    page.wait_for_timeout(200)


def test_stat_tooltips_paint_above_the_controls(page):
    """The same bug one block further up, and the one the map's fix caused.

    Stat tooltips hang down from the tiles into the control bar, and the two can
    be open together: opening a dropdown dismisses a tooltip, but opening a
    tooltip leaves a dropdown alone. Layering both blocks equally let tree order
    decide, and the control bar won and cut the last line off every explanation.

    Both surfaces are var(--surface-2), so a dominant colour cannot tell them
    apart. What can is whether the strip changes at all when the tooltip opens.
    """
    _open_map(page)
    controls = page.locator(".controls").bounding_box()
    page.click(".stat:first-child .help")
    pop = page.locator(".help-popover")
    assert pop.is_visible()
    box = pop.bounding_box()
    overlap = box["y"] + box["height"] - controls["y"]
    assert overlap > 10, (
        f"the tooltip stops {-overlap:.0f}px short of the controls, so this test "
        f"would pass whether or not the bug is present"
    )
    clip = {
        "x": box["x"] + 4,
        "y": controls["y"] + 2,
        "width": box["width"] - 8,
        "height": min(overlap, 40) - 4,
    }
    covered = page.screenshot(clip=clip)
    page.locator("body").click(position={"x": 5, "y": 5})
    assert page.locator(".help-popover").count() == 0
    bare = page.screenshot(clip=clip)
    assert covered != bare, "the stat tooltip is painted behind the control bar"
    page.click("#tab-brands")
    page.wait_for_timeout(200)
