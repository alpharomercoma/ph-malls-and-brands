"""WalterMart Community Malls scraper.

The main site (``waltermart.com.ph``) sits behind an sgcaptcha bot challenge,
but the mall subdomain ``malls.waltermart.com.ph`` serves plain HTML with no
challenge:

- ``/malls/`` -> every mall, grouped under region headings, each linking to a
  per-mall slug.
- ``/malls/<slug>/`` -> the mall page, whose "View All" links name the
  categories that mall actually has (food-choices, shops, cybermart, wellness,
  services, amusement — but only the ones present).
- ``/malls/<slug>/<category>`` -> the full category listing. Store details ride
  on ``a.wm-store`` data attributes (``data-name``, ``data-address``,
  ``data-operatinghours``, ``data-contactnumber``).

The mall page itself caps each category carousel at 10 items, so the category
pages are the authoritative source and are what this scraper reads.
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from ..models import Mall, Store
from .base import MallChainScraper

BASE = "https://malls.waltermart.com.ph"
REGION_HEADINGS = {
    "metro manila": "metro-manila",
    "north luzon": "north-luzon",
    "central luzon": "north-luzon",
    "south luzon": "south-luzon",
    "visayas": "visayas",
    "mindanao": "mindanao",
}


class WaltermartScraper(MallChainScraper):
    chain = "waltermart"

    def discover_malls(self) -> list[Mall]:
        html = self.fetcher.get_text(f"{BASE}/malls/")
        tree = HTMLParser(html)
        malls: dict[str, Mall] = {}
        region: str | None = None

        for node in tree.root.traverse(include_text=False):
            if node.tag in ("h1", "h2", "h3", "h4", "h5"):
                label = re.sub(r"\s+", " ", node.text(strip=True)).lower()
                if label in REGION_HEADINGS:
                    region = REGION_HEADINGS[label]
                continue
            if node.tag != "a":
                continue
            href = (node.attributes.get("href") or "").strip()
            # mall links are bare relative slugs like "north-edsa"
            if not href or href.startswith(("http", "/", "#", "mailto")):
                continue
            slug = href.strip("/")
            if slug in malls:
                continue
            name = re.sub(r"\s+", " ", node.text(strip=True)) or slug.replace("-", " ").title()
            malls[slug] = Mall(
                chain=self.chain,
                mall_id=slug,
                mall_name=f"WalterMart {name}" if not name.lower().startswith("walter") else name,
                region=region,
                source_url=f"{BASE}/malls/{slug}/",
            )
        if not malls:
            self.warn("no malls parsed from /malls/ — page structure may have changed")
        return sorted(malls.values(), key=lambda m: m.mall_id)

    def scrape_mall(self, mall: Mall) -> list[Store]:
        page = self.fetcher.get_text(f"{BASE}/malls/{mall.mall_id}/")
        tree = HTMLParser(page)

        # "View All" links name exactly the categories this mall has
        categories = []
        for a in tree.css("a"):
            href = (a.attributes.get("href") or "").strip()
            if "view all" in a.text(strip=True).lower() and href and "/" not in href:
                categories.append(href)
        if not categories:
            categories = ["food-choices", "shops", "cybermart", "wellness", "services", "amusement"]

        by_name: dict[str, Store] = {}
        for category in dict.fromkeys(categories):
            try:
                html = self.fetcher.get_text(f"{BASE}/malls/{mall.mall_id}/{category}")
            except Exception as exc:
                self.warn(f"{mall.mall_id}/{category}: {type(exc).__name__}")
                continue
            for node in HTMLParser(html).css("a.wm-store"):
                attrs = node.attributes
                name = re.sub(r"\s+", " ", (attrs.get("data-name") or "")).strip()
                if not name:
                    continue
                phone = (attrs.get("data-contactnumber") or "").strip()
                by_name.setdefault(
                    name.lower(),
                    Store(
                        chain=self.chain,
                        mall_id=mall.mall_id,
                        store_name_raw=name,
                        category=category.replace("-", " "),
                        phone=phone if phone not in ("", "-") else None,
                        source="waltermart-html",
                    ),
                )
        return list(by_name.values())
