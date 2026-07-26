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
