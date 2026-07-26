"""Araneta City scraper (Araneta Group, Cubao).

``aranetacity.com`` renders each venue's tenant list server-side at
``/shopping/<slug>``, as a flat run of gallery items:

    <div class="gallery-item">
      <a href="/establishment/478"> <img alt="HANDYMAN"> </a>
      <div class="caption"><h4>HANDYMAN</h4><p>LGF</p></div>

The ``<p>`` under the caption is the floor code (LGF/UGF/2F/…). There is no
pagination — the "pagination" token in the page belongs to a Swiper carousel
config, not the directory.

Araneta City is one operator running several adjacent venues in Cubao. The
four shopping malls are scraped as ``property_type="mall"``; the remaining
retail venues in the complex (Farmers Market, the Cyberpark towers, Shopwise,
the New Frontier Theater and Fiesta Carnival arcades) are listed in
``registry/araneta_coverage.json`` — they are office/market/arcade retail
rather than malls.
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from ..models import Mall, Store
from .base import MallChainScraper

BASE = "https://aranetacity.com"

MALLS = {
    "gateway-mall": ("Gateway Mall", "General Roxas Ave., Araneta City, Cubao, Quezon City"),
    "gateway-mall-2-shop": ("Gateway Mall 2", "Araneta City, Cubao, Quezon City"),
    "ali-mall": ("Ali Mall", "General Roxas Ave., Araneta City, Cubao, Quezon City"),
    "farmers-plaza": ("Farmers Plaza", "General Araneta St., Araneta City, Cubao, Quezon City"),
}


class AranetaScraper(MallChainScraper):
    chain = "araneta"

    def discover_malls(self) -> list[Mall]:
        return [
            Mall(
                chain=self.chain,
                # the CMS slug carries a "-shop" suffix for Gateway 2; keep the
                # mall_id clean and stash the slug for fetching
                mall_id=slug.removesuffix("-shop"),
                mall_name=name,
                region="metro-manila",
                address=address,
                source_url=f"{BASE}/shopping/{slug}",
                extra={"slug": slug},
            )
            for slug, (name, address) in MALLS.items()
        ]

    def scrape_mall(self, mall: Mall) -> list[Store]:
        html = self.fetcher.get_text(f"{BASE}/shopping/{mall.extra['slug']}")
        tree = HTMLParser(html)
        stores: list[Store] = []
        # No dedupe by name: a brand with outlets on two floors is two real
        # tenants, and brand-presence analysis already dedupes per mall.
        for item in tree.css("div.gallery-item"):
            heading = item.css_first("h4")
            if heading is None:
                continue
            name = re.sub(r"\s+", " ", heading.text(strip=True))
            if not name:
                continue
            floor_node = item.css_first(".caption p")
            floor = re.sub(r"\s+", " ", floor_node.text(strip=True)) if floor_node else ""
            stores.append(
                Store(
                    chain=self.chain,
                    mall_id=mall.mall_id,
                    store_name_raw=name,
                    floor=floor or None,
                    source="araneta-html",
                )
            )
        if not stores:
            self.warn(f"{mall.mall_id}: no gallery-item tenants found — markup may have changed")
        return stores
