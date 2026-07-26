"""Megaworld Lifestyle Malls scraper.

The site is a JS app backed by Contentstack (headless CMS). Endpoints and the
delivery credentials were found by observing the site's own network traffic
(2026-07); they are public read-only delivery tokens shipped to every browser:

- ``GET cdn.contentstack.io/v3/content_types/mall/entries`` -> 26 malls
- ``GET cdn.contentstack.io/v3/content_types/tenant/entries`` -> ~2,100 tenants,
  each with ``name``, ``category``, ``shop_type``, ``floor``, ``landline``,
  ``operating_hours`` and a ``reference`` array pointing at its mall's uid.

This is the richest of the chains scraped so far: category *and* sub-type
*and* floor come straight from the API.

Note: ``megaworldlifestylemalls.com`` (no hyphen) is NOT Megaworld — that
domain has lapsed and now redirects to an unrelated ad/scam site. The live
site is ``megaworld-lifestylemalls.com``.
"""

from __future__ import annotations

from ..models import Mall, Store
from .base import MallChainScraper

CDN = "https://cdn.contentstack.io/v3/content_types/"
ENV = "prod-environment"
PAGE = 100


class MegaworldScraper(MallChainScraper):
    chain = "megaworld"
    extra_headers = {
        "api_key": "blt827157d7af7bc6d4",
        "access_token": "cs12c8f62754c81457af4cc5fc",
        "Referer": "https://www.megaworld-lifestylemalls.com/",
    }

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self._by_mall_uid: dict[str, list[dict]] = {}

    def _entries(self, content_type: str) -> list[dict]:
        """Fetch every entry of a Contentstack content type, following skip/limit."""
        out: list[dict] = []
        skip = 0
        total = None
        while True:
            data = self.fetcher.get_json(
                f"{CDN}{content_type}/entries/",
                {"environment": ENV, "include_count": "true", "limit": PAGE, "skip": skip},
            )
            entries = data.get("entries", [])
            if total is None:
                total = int(data.get("count", 0) or 0)
            if not entries:
                break
            out.extend(entries)
            skip += len(entries)
            if total and skip >= total:
                break
        if total and len(out) != total:
            self.warn(f"{content_type}: collected {len(out)} of {total} entries")
        return out

    def discover_malls(self) -> list[Mall]:
        malls = []
        for r in self._entries("mall"):
            malls.append(
                Mall(
                    chain=self.chain,
                    mall_id=r.get("url") or r["uid"],
                    mall_name=(r.get("name") or r.get("title") or "").strip(),
                    address=(r.get("address") or "").strip() or None,
                    mall_code=r["uid"],
                    source_url=f"https://www.megaworld-lifestylemalls.com/malls/{r.get('url', '')}",
                    extra={"uid": r["uid"]},
                )
            )

        # One pass over tenants, bucketed by the mall uid each one references.
        for t in self._entries("tenant"):
            for ref in t.get("reference") or []:
                self._by_mall_uid.setdefault(ref.get("uid"), []).append(t)

        known = {m.extra["uid"] for m in malls}
        orphans = sum(len(v) for k, v in self._by_mall_uid.items() if k not in known)
        if orphans:
            self.warn(f"{orphans} tenants reference a mall uid not in the mall list")
        return sorted(malls, key=lambda m: m.mall_id)

    def scrape_mall(self, mall: Mall) -> list[Store]:
        return [
            Store(
                chain=self.chain,
                mall_id=mall.mall_id,
                store_name_raw=(t.get("name") or "").strip(),
                category=(t.get("category") or "").strip().lower() or None,
                floor=(t.get("floor") or "").strip() or None,
                phone=(t.get("landline") or t.get("mobile") or "").strip() or None,
                source="megaworld-contentstack",
            )
            for t in self._by_mall_uid.get(mall.extra["uid"], [])
            if (t.get("name") or "").strip()
        ]
