"""SM Supermalls scraper.

Uses the same JSON endpoints the site's own JS calls (verified 2026-07):

- ``GET /list-of-malls?region=<r>&keyword=&page=<n>``  -> paginated mall list
- ``GET /tenants?category=all&subCategory=all&mallCode=<CODE>&keyword=all&``
  ``floor=all&building=all&order=order_name&asc=asc&page=<n>`` -> paginated tenants

Gotchas: filter params must literally be the string ``all`` (empty strings
return ``[]``), and responses are 12 items per page.
"""

from __future__ import annotations

from ..models import Mall, Store
from .base import MallChainScraper

BASE = "https://www.smsupermalls.com/"
PAGE_SIZE = 12
MAX_PAGES = 500  # loop guard; largest mall is ~30 pages

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
        return sorted(by_code.values(), key=lambda m: m.mall_id)

    def scrape_mall(self, mall: Mall) -> list[Store]:
        stores: list[Store] = []
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
                stores.append(
                    Store(
                        chain=self.chain,
                        mall_id=mall.mall_id,
                        store_name_raw=(t.get("tenant_display_name") or "").strip(),
                        category=t.get("tenant_cat_slug") or None,
                        floor=(t.get("tenant_floor") or "").strip() or None,
                        building=(t.get("tenant_building") or "").strip() or None,
                        source="sm-api",
                    )
                )
            if len(stores) >= expected:
                break
            page += 1
        if expected is not None and len(stores) != expected:
            self.warn(f"{mall.mall_id}: collected {len(stores)} of {expected} tenants")
        return stores
