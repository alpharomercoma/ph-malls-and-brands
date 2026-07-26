"""Ayala Malls scraper.

The public site is a React SPA; its data comes from a JSON API discovered by
observing the ``/explore/mall-directory`` page's network traffic (2026-07):

- ``GET https://api.ayalamalls.com/api/explore-v2/malls`` -> 32 malls with
  ``id``, ``name``, ``slugName``, ``location`` (street address), lat/lng.
- ``GET .../explore-v2/stores/list?mallSlug=<slug>&category=all`` -> that
  mall's full directory, one record per store with a ``category``
  (shop | dine | services | essentials | entertainment).

Passing an empty ``mallSlug`` returns every store chain-wide in one response;
we use that as a completeness cross-check against the per-mall sum.

Ayala publishes no region field, so region is derived from the address text
(city/province keywords) with a lat/lng fallback, to stay comparable with the
SM and Robinsons region buckets. No floor/level data is exposed by this API
(the site renders floors via Mappedin's map SDK), so ``floor`` stays null.
"""

from __future__ import annotations

from typing import ClassVar

from mallscape_core.geo import derive_region
from mallscape_core.models import Mall, Store
from mallscape_scrape import coverage
from mallscape_scrape.scrapers.base import MallChainScraper

API = "https://api.ayalamalls.com/api/explore-v2/"

class AyalaScraper(MallChainScraper):
    chain = "ayala"
    # the API rejects requests without a matching site origin
    extra_headers: ClassVar[dict[str, str]] = {
        "Origin": "https://www.ayalamalls.com",
        "Referer": "https://www.ayalamalls.com/",
    }

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self._bulk_counts: dict[str, int] = {}

    def discover_malls(self) -> list[Mall]:
        records = self.fetcher.get_json(API + "malls")
        malls = []
        for r in records:
            address = (r.get("location") or "").strip() or None
            region = derive_region(
                f"{r.get('name', '')} {address or ''}", r.get("latitude"), r.get("longitude")
            )
            if region is None:
                self.warn(f"could not derive region for {r['slugName']} ({address!r})")
            malls.append(
                Mall(
                    chain=self.chain,
                    mall_id=r["slugName"],
                    mall_name=r["name"].strip(),
                    region=region,
                    address=address,
                    mall_code=r["id"],
                    source_url=f"https://www.ayalamalls.com/explore/mall-directory/{r['slugName']}",
                    extra={"explore_enabled": r.get("explore")},
                )
            )

        # Completeness cross-check: one bulk call returns every store chain-wide.
        bulk = self.fetcher.get_json(
            API + "stores/list", {"mallSlug": "", "category": "all"}
        )
        for row in bulk:
            slug = row.get("mallSlug")
            self._bulk_counts[slug] = self._bulk_counts.get(slug, 0) + 1
        unknown = set(self._bulk_counts) - {m.mall_id for m in malls}
        if unknown:
            self.warn(f"stores reference malls missing from /malls: {sorted(unknown)}")

        coverage.report_gaps(self, {m.mall_name for m in malls})
        return sorted(malls, key=lambda m: m.mall_id)

    def scrape_mall(self, mall: Mall) -> list[Store]:
        rows = self.fetcher.get_json(
            API + "stores/list", {"mallSlug": mall.mall_id, "category": "all"}
        )
        stores = [
            Store(
                chain=self.chain,
                mall_id=mall.mall_id,
                store_name_raw=(r.get("merchantName") or "").strip(),
                category=r.get("category") or None,
                source="ayala-api",
            )
            for r in rows
            if (r.get("merchantName") or "").strip()
        ]
        expected = self._bulk_counts.get(mall.mall_id)
        if expected is not None and len(rows) != expected:
            self.warn(
                f"{mall.mall_id}: per-mall list has {len(rows)} stores but the "
                f"chain-wide list has {expected}"
            )
        if not rows and mall.extra.get("explore_enabled") is False:
            self.warn(
                f"{mall.mall_id}: no directory published (mall has explore=false "
                f"in Ayala's API - genuinely absent upstream, not a parse failure)"
            )
        return stores
