"""Filinvest Malls scraper (includes Festival Mall).

``filinvestlifemalls.com`` is the live site — ``filinvestmalls.com`` is a
parked domain that bounces to a lander. Each mall has a server-rendered shops
directory at ``/shops-directory/<slug>/`` holding a single table:

    <tr class="sp-1"><td colspan="3">CATEGORY</td></tr>   <- category header
    <tr><td></td><td>Shop Name</td><td>Location / Floor</td></tr>

Category applies to every following row until the next header, so the parser
carries it down. Festival Mall (Alabang) is Filinvest's flagship and is one of
these five malls rather than a separate operator.
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from ..models import Mall, Store
from .base import MallChainScraper

BASE = "https://www.filinvestlifemalls.com/shops-directory/"

# slug -> (display name, region). The site has no machine-readable mall list;
# these five are the complete portfolio per filinvestlifemalls.com's own nav.
MALLS = {
    "festival-mall": ("Festival Mall", "metro-manila", "Filinvest City, Alabang, Muntinlupa"),
    "il-corso": ("IL Corso", "visayas", "Filinvest Cyberzone, Cebu City"),
    "fora": ("Fora Mall", "south-luzon", "Tagaytay City, Cavite"),
    "main-square": ("Main Square", "south-luzon", "Bacoor, Cavite"),
    "dumaguete": ("Filinvest Malls Dumaguete", "visayas", "Dumaguete, Negros Oriental"),
}


class FilinvestScraper(MallChainScraper):
    chain = "filinvest"

    def discover_malls(self) -> list[Mall]:
        return [
            Mall(
                chain=self.chain,
                mall_id=slug,
                mall_name=name,
                region=region,
                address=address,
                source_url=BASE + slug + "/",
            )
            for slug, (name, region, address) in MALLS.items()
        ]

    def scrape_mall(self, mall: Mall) -> list[Store]:
        html = self.fetcher.get_text(f"{BASE}{mall.mall_id}/")
        tree = HTMLParser(html)
        table = tree.css_first("#result table") or tree.css_first("table")
        if table is None:
            self.warn(f"{mall.mall_id}: no directory table found")
            return []

        stores: list[Store] = []
        category: str | None = None
        for row in table.css("tbody tr"):
            cells = row.css("td")
            if not cells:
                continue
            # category header rows span the full table
            if "sp-1" in (row.attributes.get("class") or "") or len(cells) == 1:
                category = _clean(cells[0].text()) or None
                if category:
                    category = category.lower()
                continue
            if len(cells) < 3:
                continue
            name = _clean(cells[1].text())
            floor = _clean(cells[2].text())
            if not name:
                continue
            stores.append(
                Store(
                    chain=self.chain,
                    mall_id=mall.mall_id,
                    store_name_raw=name,
                    category=category,
                    floor=floor or None,
                    source="filinvest-html",
                )
            )
        return stores


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()
