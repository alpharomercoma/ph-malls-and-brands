"""Integration: stages hand off to each other correctly.

Unit tests cover one function against fixed input. These cover the contract
between stages, which is where the expensive bugs have historically been:
a stage writing where the next one does not read, or a schema drifting.
Everything runs against a temporary data directory, so no network and no
dependency on the committed snapshot.
"""

from __future__ import annotations

from typing import ClassVar

import pandas as pd
import pytest

from mallscape_core import storage

MALLS = pd.DataFrame({
    "chain": ["sm", "sm", "ayala"],
    "mall_id": ["sm-a", "sm-b", "ay-a"],
    "mall_name": ["SM A", "SM B", "Ayala A"],
    "region": ["metro-manila", "visayas", "visayas"],
    "address": [None, None, None],
    "mall_code": ["A", "B", "1"],
    "source_url": ["u", "u", "u"],
    "property_type": ["mall", "residential-retail", "mall"],
    # one placed by the operator, one by the registry, one unplaceable
    "lat": [14.55, 10.31, None],
    "lon": [121.02, 123.90, None],
    "geo_source": ["operator", "osm", None],
    "geo_precision": ["exact", "exact", None],
    "scraped_at": ["2026-01-01"] * 3,
})

STORES = pd.DataFrame({
    "chain": ["sm", "sm", "sm", "ayala"],
    "mall_id": ["sm-a", "sm-a", "sm-b", "ay-a"],
    "store_name_raw": ["JOLLIBEE", "WATSONS", "JOLLIBEE", "JOLLIBEE"],
    "category": ["dining", "wellness", "dining", "dine"],
    "floor": ["2ND FLOOR", "GF", "2F", None],
    "building": [None, None, None, None],
    "phone": ["0917-123-4567", None, None, None],
    "source": ["sm-api"] * 3 + ["ayala-api"],
    "scraped_at": ["2026-01-01"] * 4,
})


@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    storage.write("2026-01-01", storage.SCRAPE, "malls", MALLS)
    storage.write("2026-01-01", storage.SCRAPE, "stores", STORES)
    return "2026-01-01"


def test_clean_reads_stage1_and_writes_stage2(snapshot):
    from mallscape_clean import pipeline as clean_stage

    clean_stage.run(snapshot)
    out = storage.read(snapshot, storage.CLEAN, "stores_clean")
    assert out is not None and len(out) == len(STORES)
    # stage 1 must be untouched by stage 2
    assert storage.read(snapshot, storage.SCRAPE, "stores").equals(STORES)
    # the harmonized category collapses "dining" and "dine"
    assert set(out[out.store_name == "Jollibee"].category_std) == {"dining"}


def test_report_prefers_clean_output(snapshot):
    from mallscape_clean import pipeline as clean_stage
    from mallscape_report import pipeline as report_stage

    clean_stage.run(snapshot)
    report_stage.run(snapshot, quiet=True)
    summary = storage.read(snapshot, storage.REPORT, "brand_summary")
    assert summary is not None
    jollibee = summary[summary.brand_key == "jollibee"].iloc[0]
    assert jollibee.n_malls_total == 3      # present in all three properties
    assert bool(jollibee.in_multiple_chains) is True


def test_website_bundle_matches_snapshot_totals(snapshot):
    from mallscape_clean import pipeline as clean_stage
    from mallscape_website import bundle

    clean_stage.run(snapshot)
    _, data = bundle.build(snapshot)
    assert data["totals"]["properties"] == len(MALLS)
    assert data["totals"]["listings"] == len(STORES)
    assert data["totals"]["malls"] == 2      # one is residential-retail
    assert len(data["malls"]) == len(MALLS)
    assert data["schema"] == 4
    assert "quality" in data
    assert data["brandCategories"]


def test_website_bundle_carries_usable_coordinates(snapshot):
    """The map can only be as good as what reaches the bundle, so the contract
    is checked here rather than in the browser: every plotted property has a
    coordinate inside the country, and an unplaced one is null, not zero."""
    from mallscape_clean import pipeline as clean_stage
    from mallscape_core.geo import in_bounds
    from mallscape_website import bundle

    clean_stage.run(snapshot)
    _, data = bundle.build(snapshot)
    lat_min, lat_max, lon_min, lon_max = 4.5, 21.5, 116.0, 127.0
    placed = [row for row in data["malls"] if row[5] is not None]
    assert data["totals"]["mapped"] == len(placed) == 2
    for row in placed:
        assert in_bounds(row[5], row[6]), row
        assert lat_min <= row[5] <= lat_max and lon_min <= row[6] <= lon_max
        assert data["dict"]["geoSources"][row[7]] in {"operator", "osm", "nominatim"}
        assert data["dict"]["geoPrecisions"][row[8]] in {"exact", "address", "locality"}
    unplaced = [row for row in data["malls"] if row[5] is None]
    assert len(unplaced) == 1
    assert unplaced[0][6] is None and unplaced[0][7] == -1


def test_website_build_keeps_csp_and_tile_url_in_step(snapshot, tmp_path, monkeypatch):
    """A tile host the page's own policy blocks is a blank map with a console
    error and no other symptom, so the build derives one from the other."""
    import shutil

    from mallscape_clean import pipeline as clean_stage
    from mallscape_core import config
    from mallscape_website import pipeline as website_stage

    clean_stage.run(snapshot)
    site = tmp_path / "site"
    shutil.copytree(config.SITE_DIR, site)
    monkeypatch.setattr(config, "SITE_DIR", site)
    monkeypatch.setattr(config, "TILE_URL", "https://tiles.example.org/{z}/{x}/{y}.png")

    website_stage.run(snapshot)
    html = (site / "index.html").read_text()
    assert 'data-tiles="https://tiles.example.org/{z}/{x}/{y}.png"' in html
    assert "img-src 'self' data: https://tiles.example.org;" in html
    assert "tile.openstreetmap.org" not in html

    monkeypatch.setattr(config, "TILE_URL", "not-a-url")
    with pytest.raises(SystemExit):
        website_stage.run(snapshot)


def test_snapshot_contract_rejects_orphan_store():
    malls = MALLS.copy()
    stores = STORES.copy()
    stores.loc[0, "mall_id"] = "missing"
    with pytest.raises(ValueError, match="without a mall"):
        storage.validate_snapshot_frames(malls, stores)


def test_report_fails_loudly_without_stage1(tmp_path, monkeypatch):
    from mallscape_website import bundle

    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    with pytest.raises(SystemExit):
        bundle.build("1999-01-01")


def test_partial_scrape_does_not_drop_other_chains(snapshot, monkeypatch):
    """Re-running one chain must carry the others forward, not replace them."""
    from mallscape_scrape import pipeline as scrape_stage

    class FakeScraper:
        chain = "ayala"
        extra_headers: ClassVar[dict] = {}

        def __init__(self, fetcher):
            self.warnings = []

        def scrape_all(self):
            from mallscape_core.models import Mall, Store
            mall = Mall(chain="ayala", mall_id="ay-a", mall_name="Ayala A")
            return [mall], [Store(chain="ayala", mall_id="ay-a", store_name_raw="NEW")]

    monkeypatch.setattr(scrape_stage, "SCRAPERS", {"sm": object, "ayala": FakeScraper})
    malls, stores = scrape_stage.run(["ayala"], "2026-01-02", rate=1000)
    assert set(malls.chain) == {"sm", "ayala"}          # sm carried forward
    assert set(stores[stores.chain == "sm"].mall_id) == {"sm-a", "sm-b"}
    # carried rows keep their real date; only the rescraped chain is restamped
    assert set(malls[malls.chain == "sm"].scraped_at) == {"2026-01-01"}
    assert set(malls[malls.chain == "ayala"].scraped_at) == {"2026-01-02"}


def test_asset_urls_carry_a_version_that_tracks_their_contents(snapshot, tmp_path, monkeypatch):
    """Code assets keep stable names and are served with a ten minute max-age,
    so without a version in the URL a deploy leaves visitors on the previous
    release's JavaScript with no symptom. This is the guarantee the data bundle
    already gets from being content-hashed."""
    import re
    import shutil

    from mallscape_clean import pipeline as clean_stage
    from mallscape_core import config
    from mallscape_website import pipeline as website_stage

    clean_stage.run(snapshot)
    site = tmp_path / "site"
    shutil.copytree(config.SITE_DIR, site)
    monkeypatch.setattr(config, "SITE_DIR", site)

    website_stage.run(snapshot)
    html = (site / "index.html").read_text()
    versions = set(re.findall(r'[?&]v=([0-9a-f]{8})', html))
    stamped = re.search(r'data-assets="([0-9a-f]{8})"', html)
    assert stamped, "index.html carries no data-assets version"
    assert versions == {stamped.group(1)}, (versions, stamped.group(1))

    # editing any versioned asset must change every asset URL
    before = stamped.group(1)
    (site / "map.js").write_text((site / "map.js").read_text() + "\n// touched\n")
    website_stage.run(snapshot)
    after = re.search(r'data-assets="([0-9a-f]{8})"', (site / "index.html").read_text())
    assert after and after.group(1) != before
