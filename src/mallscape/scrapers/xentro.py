"""XentroMalls scraper (community malls).

``xentromall.com.ph`` is a parked domain; the live site is
``www.xentromalls.com``. Each property has a ``/mall-locator/<slug>/`` page
whose "Shops" tab lists tenants as plain ``<li>`` items inside
``div.zn_text_box`` blocks.

The upstream data is rough: some list items merge several brands into one line
("ROBINSONS SUPERMARKET HOT TICKET FASHION SHOP"), and there is no floor or
category. Names are captured verbatim — brand normalization happens downstream
in ``normalize.py`` rather than by guessing at split points here.

The portfolio mixes XentroMall-branded malls with other names the same group
operates (Montalban Town Center, ShopKing, Northstar Mall, Sta. Ana Public
Market …), all served from the same locator.
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from ..models import Mall, Store
from .base import MallChainScraper

BASE = "https://www.xentromalls.com"
LOCATOR = f"{BASE}/mall-locator/"
_SLUG = re.compile(r'href="[^"]*?/mall-locator/([a-z0-9-]+)/"')
# nav/footer lists are short; tenant blocks are long runs of short upper-case names
MIN_TENANTS_PER_BLOCK = 3
# markers unique to the leasing-requirements checklist rendered in the same markup
_LEASING_FORM = re.compile(
    r"letter of intent|duly accomplished|information sheet|background of the company"
    r"|credit & character|gross sales|architectural perspective|utility requirements"
    r"|letter of authority|target market|future plans|business expansion",
    re.I,
)


class XentroScraper(MallChainScraper):
    chain = "xentro"

    def discover_malls(self) -> list[Mall]:
        html = self.fetcher.get_text(LOCATOR)
        slugs = sorted(set(_SLUG.findall(html)))
        if not slugs:
            self.warn("no mall slugs found on /mall-locator/")
        malls = []
        for slug in slugs:
            name = slug.replace("-", " ").title()
            name = re.sub(r"\bXentro Mall\b", "XentroMall", name)
            malls.append(
                Mall(
                    chain=self.chain,
                    mall_id=slug,
                    mall_name=name,
                    source_url=f"{LOCATOR}{slug}/",
                )
            )
        return malls

    def scrape_mall(self, mall: Mall) -> list[Store]:
        html = self.fetcher.get_text(f"{LOCATOR}{mall.mall_id}/")
        tree = HTMLParser(html)

        # address sits in the page header near the mall name
        stores: list[Store] = []
        seen: set[str] = set()
        for block in tree.css("div.zn_text_box"):
            items = block.css("li")
            if len(items) < MIN_TENANTS_PER_BLOCK:
                continue
            # The same markup holds the leasing-requirements checklist. Casing
            # does not separate them (some malls list tenants in mixed case),
            # but the checklist has a distinctive vocabulary.
            texts = [re.sub(r"\s+", " ", i.text(strip=True)).strip() for i in items]
            texts = [t for t in texts if t]
            if not texts or any(_LEASING_FORM.search(t) for t in texts):
                continue
            for item in items:
                name = re.sub(r"\s+", " ", item.text(strip=True)).strip()
                # skip nav-ish entries and prose
                if not name or len(name) > 90 or name.lower() in seen:
                    continue
                if any(c in name for c in ("©", "@")) or name.endswith("."):
                    continue
                seen.add(name.lower())
                stores.append(
                    Store(
                        chain=self.chain,
                        mall_id=mall.mall_id,
                        store_name_raw=name,
                        source="xentro-html",
                    )
                )
        return stores
