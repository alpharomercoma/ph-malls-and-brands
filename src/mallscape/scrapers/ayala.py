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

import datetime as dt
import json
import re
from importlib import resources

from ..models import Mall, Store
from .base import MallChainScraper

API = "https://api.ayalamalls.com/api/explore-v2/"

# Order matters: Metro Manila is checked first because provincial place names
# also appear as street names inside MM addresses ("Legazpi Street, Makati").
METRO_MANILA = (
    "makati", "taguig", "pasig", "marikina", "paranaque", "caloocan",
    "mandaluyong", "pasay", "las pinas", "muntinlupa", "malabon", "navotas",
    "valenzuela", "san juan", "pateros", "quezon city", "manila city",
    "metro manila", "bonifacio global city", "bgc",
)
NORTH_LUZON = (
    "pampanga", "angeles city", "tarlac", "bulacan", "nueva ecija",
    "pangasinan", "la union", "ilocos", "cagayan valley", "isabela",
    "benguet", "baguio", "zambales", "subic", "bataan", "aurora", "abra",
)
SOUTH_LUZON = (
    "cavite", "laguna", "batangas", "quezon province", "albay", "legazpi city",
    "camarines", "sorsogon", "masbate", "marinduque", "mindoro", "palawan",
    "naga city", "binan", "santa rosa", "sta rosa", "nuvali", "tagaytay",
    "dasmarinas", "imus", "vermosa",
)
VISAYAS = (
    "cebu", "bacolod", "iloilo", "negros", "panay", "leyte", "samar", "bohol",
    "tacloban", "dumaguete", "ormoc", "capiz", "roxas city", "antique",
    "aklan", "boracay", "siquijor", "biliran", "guimaras",
)
MINDANAO = (
    "davao", "cagayan de oro", "zamboanga", "general santos", "gensan",
    "butuan", "iligan", "cotabato", "surigao", "agusan", "misamis",
    "bukidnon", "pagadian", "tagum", "koronadal", "dipolog", "ozamiz",
    "marawi", "lanao", "sultan kudarat", "basilan", "tawi",
)
REGION_KEYWORDS = (
    ("metro-manila", METRO_MANILA),
    ("north-luzon", NORTH_LUZON),
    ("south-luzon", SOUTH_LUZON),
    ("visayas", VISAYAS),
    ("mindanao", MINDANAO),
)
_QC_ABBREV = re.compile(r"\bq\.?\s?c\.?\b")


def derive_region(text: str, lat: float | None, lon: float | None) -> str | None:
    """Best-effort region bucket from address text, falling back to coordinates."""
    haystack = text.lower()
    if _QC_ABBREV.search(haystack):
        return "metro-manila"
    for region, keywords in REGION_KEYWORDS:
        if any(k in haystack for k in keywords):
            return region
    # coordinate fallback, only for plausible Philippine coordinates
    if lat and lon and 4.5 <= lat <= 21.5 and 116.0 <= lon <= 127.0:
        if lat > 14.8:
            return "north-luzon"
        if lat >= 14.35 and 120.85 <= lon <= 121.15:
            return "metro-manila"
        if lat >= 12.5:
            return "south-luzon"
        if lat >= 9.0:
            return "visayas"
        return "mindanao"
    return None


class AyalaScraper(MallChainScraper):
    chain = "ayala"
    # the API rejects requests without a matching site origin
    extra_headers = {
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

        self._check_known_gaps({m.mall_name.lower() for m in malls})
        return sorted(malls, key=lambda m: m.mall_id)

    def _check_known_gaps(self, api_names: set[str]) -> None:
        """Report Ayala retail properties known to exist but absent from the API.

        Keeps the coverage limit visible in every run report, and tells us when
        a previously missing mall (e.g. Arca South) finally lands in the API so
        it can be dropped from the registry.
        """
        raw = resources.files("mallscape.registry").joinpath("ayala_coverage.json").read_text()
        coverage = json.loads(raw)
        today = dt.date.today().isoformat()
        missing_malls, appeared = [], []
        for entry in coverage["not_in_api"]:
            name = entry["name"].lower()
            if any(name in n or n in name for n in api_names):
                appeared.append(entry["name"])
            elif (
                entry["property_type"] == "mall"
                and entry.get("opened")
                # skip malls that have not opened yet
                and entry["opened"][:10] <= today
            ):
                missing_malls.append(f"{entry['name']} (opened {entry['opened']})")
        if missing_malls:
            self.warn(
                "known Ayala malls with NO official directory in the API — "
                "excluded from store data by necessity: " + "; ".join(missing_malls)
            )
        for name in appeared:
            self.warn(
                f"{name} now appears in the API — remove it from "
                f"registry/ayala_coverage.json so its stores are scraped"
            )

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
                f"in Ayala's API — genuinely absent upstream, not a parse failure)"
            )
        return stores
