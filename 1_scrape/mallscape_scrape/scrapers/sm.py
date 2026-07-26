"""SM Supermalls scraper.

Uses the same JSON endpoints the site's own JS calls (verified 2026-07):

- ``GET /list-of-malls?region=<r>&keyword=&page=<n>``  -> paginated mall list
- ``GET /tenants?category=all&subCategory=all&mallCode=<CODE>&keyword=all&``
  ``floor=all&building=all&order=order_name&asc=asc&page=<n>`` -> paginated tenants

Gotchas: filter params must literally be the string ``all`` (empty strings
return ``[]``), and responses are 12 items per page.
"""

from __future__ import annotations

from mallscape_core import config
from mallscape_core.models import Mall, Store
from mallscape_scrape.scrapers.base import MallChainScraper

BASE = "https://www.smsupermalls.com/"
PAGE_SIZE = 12
MAX_PAGES = config.MAX_PAGES  # loop guard; largest mall is ~30 pages

# Region buckets used by the site's filter checkboxes. Together they cover
# all malls (verified: 36+25+22+10+8+20+5 = 126 in 2026-07).
REGIONS = [
    "metro-manila",
    "north-luzon",
    "south-luzon",
    "visayas",
    "mindanao",
    "smdc",
    "others",
]


def classify_property_type(name: str, region: str | None) -> str:
    """SM's directory lists more than malls.

    SM Prime reports roughly 80-90 *malls* in the Philippines, but this API
    returns 126 entries: the geographic buckets hold the actual malls, while
    the `smdc` bucket is SM's residential developer (condo retail podiums) and
    `others` mixes in amusement parks and office annexes. Classify so chain
    comparisons can filter to real malls instead of overstating SM's footprint.
    """
    n = name.lower()
    if "sky ranch" in n:
        return "amusement-park"
    if any(k in n for k in ("annex", "building", "bldg", "tower")):
        return "office-annex"
    if region == "smdc" or n.startswith("smdc"):
        return "residential-retail"
    return "mall"


class SMScraper(MallChainScraper):
    chain = "sm"

    def _mall_pages(self, region: str):
        """Yield mall records for one region filter, following pagination."""
        page = 0
        seen = 0
        while page < MAX_PAGES:
            data = self.fetcher.get_json(
                BASE + "list-of-malls",
                {"region": region, "keyword": "", "page": page},
            )
            malls = data.get("malls", {}) if isinstance(data, dict) else {}
            counts = int(malls.get("counts", 0) or 0)
            batch = malls.get("data", [])
            if not batch:
                break
            yield from batch
            seen += len(batch)
            if seen >= counts:
                break
            page += 1

    def discover_malls(self) -> list[Mall]:
        by_code: dict[str, Mall] = {}
        for record in self._mall_pages("all"):
            mall = Mall(
                chain=self.chain,
                mall_id=record["mall_label"],
                mall_name=record["mall_name"].strip(),
                address=(record.get("mall_address") or "").replace("\r\n", ", ").strip() or None,
                mall_code=record["mall_code"],
                source_url=record.get("mall_url"),
            )
            by_code[mall.mall_code] = mall

        # Second pass per region bucket to tag each mall with its region.
        for region in REGIONS:
            for record in self._mall_pages(region):
                mall = by_code.get(record["mall_code"])
                if mall is None:
                    self.warn(f"mall {record['mall_code']} in region={region} missing from region=all")
                else:
                    mall.region = region
        untagged = [m.mall_id for m in by_code.values() if m.region is None]
        if untagged:
            self.warn(f"{len(untagged)} malls without region: {untagged}")

        for mall in by_code.values():
            mall.property_type = classify_property_type(mall.mall_name, mall.region)
        counts: dict[str, int] = {}
        for mall in by_code.values():
            counts[mall.property_type] = counts.get(mall.property_type, 0) + 1
        print(f"[{self.chain}] property types: {counts}")
        return sorted(by_code.values(), key=lambda m: m.mall_id)

    def scrape_mall(self, mall: Mall) -> list[Store]:
        # Deduplicate on (slug, name, floor, building): SM's pagination is not
        # a stable sort, so a tenant can repeat across page boundaries. The key
        # deliberately includes floor/building because ~1% of records have an
        # empty tenant_slug - keying on slug alone silently merged genuinely
        # distinct outlets of the same brand within one mall.
        by_slug: dict[str, Store] = {}
        page = 0
        expected = None
        while page < MAX_PAGES:
            data = self.fetcher.get_json(
                BASE + "tenants",
                {
                    "category": "all",
                    "subCategory": "all",
                    "mallCode": mall.mall_code,
                    "keyword": "all",
                    "floor": "all",
                    "building": "all",
                    "order": "order_name",
                    "asc": "asc",
                    "page": page,
                },
            )
            if not isinstance(data, dict):  # API returns bare [] for no results
                break
            payload = data.get("data", {})
            expected = int(payload.get("counts", 0) or 0)
            batch = payload.get("data", [])
            if not batch:
                break
            for t in batch:
                # ~1% of records carry an empty tenant_slug, so the key must
                # also carry floor/building - otherwise two genuinely distinct
                # outlets of one brand in the same mall collapse into one, and
                # which floor survives depends on the (unstable) page order.
                slug = (
                    t.get("tenant_slug") or "",
                    (t.get("tenant_display_name") or "").strip(),
                    (t.get("tenant_floor") or "").strip(),
                    (t.get("tenant_building") or "").strip(),
                )
                by_slug.setdefault(
                    slug,
                    Store(
                        chain=self.chain,
                        mall_id=mall.mall_id,
                        store_name_raw=(t.get("tenant_display_name") or "").strip(),
                        category=t.get("tenant_cat_slug") or None,
                        floor=(t.get("tenant_floor") or "").strip() or None,
                        building=(t.get("tenant_building") or "").strip() or None,
                        source="sm-api",
                    ),
                )
            if len(by_slug) >= expected:
                break
            page += 1

        stores = list(by_slug.values())
        # `counts` still runs ahead of what pagination serves for some malls
        # (hidden/inactive tenants); verified unrecoverable via asc/desc/floor
        # ordering and per-category sweeps. The threshold is deliberately loose
        # for that reason - it is a smoke alarm for a broken mall, not a
        # completeness assertion.
        if expected:
            shortfall = (expected - len(stores)) / expected
            if not stores:
                self.warn(f"{mall.mall_id}: API reports {expected} tenants but served none")
            elif shortfall > 0.20:
                self.warn(
                    f"{mall.mall_id}: only {len(stores)} of {expected} reported "
                    f"tenants served ({shortfall:.0%} short) - investigate"
                )
        return stores
