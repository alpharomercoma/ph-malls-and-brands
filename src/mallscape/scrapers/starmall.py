"""Starmall scraper (Vista Land's Starmalls chain).

Each mall has a ``/stores-<slug>/`` page whose directory is rendered by an
Elementor "filterable gallery" widget. The store cards are not in the page
markup directly — they sit inside a JSON-escaped blob in an inline attribute,
so the parser unescapes that blob first and then parses the HTML fragments:

    <div class="... eael-cf-<category>"> ...
      <h5 class="fg-item-title">STORE NAME</h5>
      <p>Contact Number:<br/>8842-7099</p><p>Location:<br/>Level 2</p>

Only four Starmalls exist; Vista Land's separate "Vista Mall" brand publishes
no tenant directory at all (see registry/vista_coverage.json).
"""

from __future__ import annotations

import html as htmllib
import re

from selectolax.parser import HTMLParser

from ..models import Mall, Store
from .base import MallChainScraper

BASE = "https://starmalls.com.ph/"

MALLS = {
    "alabang": ("Starmall Alabang", "metro-manila", "Alabang-Zapote Road, Las Pinas City"),
    "edsa-shaw": ("Starmall EDSA-Shaw", "metro-manila", "EDSA cor. Shaw Blvd., Mandaluyong City"),
    "san-jose-del-monte": ("Starmall San Jose del Monte", "north-luzon", "San Jose del Monte, Bulacan"),
    "talisay": ("Starmall Talisay Cebu", "visayas", "Talisay City, Cebu"),
}

_TITLE = re.compile(r'fg-item-title[^>]*>([^<]+)<', re.I)
_CATEGORY = re.compile(r"eael-cf-([a-z0-9-]+)", re.I)


class StarmallScraper(MallChainScraper):
    chain = "starmall"

    def discover_malls(self) -> list[Mall]:
        return [
            Mall(
                chain=self.chain,
                mall_id=slug,
                mall_name=name,
                region=region,
                address=address,
                source_url=f"{BASE}stores-{slug}/",
            )
            for slug, (name, region, address) in MALLS.items()
        ]

    def scrape_mall(self, mall: Mall) -> list[Store]:
        raw = self.fetcher.get_text(f"{BASE}stores-{mall.mall_id}/")
        # the gallery items live inside a JSON-escaped attribute blob
        blob = raw.replace("\\u0022", '"').replace("\\u003C", "<").replace("\\u003E", ">")
        blob = blob.replace("\\/", "/").replace("\\n", "\n").replace("\\t", "\t")
        blob = htmllib.unescape(blob)

        stores: list[Store] = []
        seen: set[str] = set()
        for chunk in blob.split("eael-filterable-gallery-item-wrap")[1:]:
            m = _TITLE.search(chunk)
            if not m:
                continue
            name = re.sub(r"\s+", " ", htmllib.unescape(m.group(1))).strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())

            cats = [c.lower() for c in _CATEGORY.findall(chunk[:400]) if c.lower() != "all"]
            fragment = HTMLParser(chunk[: chunk.find("</div></div></div>") + 20 or None])
            text = re.sub(r"\s+", " ", fragment.text(separator="\n"))
            phone = _after(text, "Contact Number:")
            floor = _after(text, "Location:")
            stores.append(
                Store(
                    chain=self.chain,
                    mall_id=mall.mall_id,
                    store_name_raw=name,
                    category=cats[0] if cats else None,
                    floor=floor,
                    phone=phone,
                    source="starmall-html",
                )
            )
        return stores


def _after(text: str, label: str) -> str | None:
    """Pull the value that follows a 'Label:' marker in the card text."""
    i = text.find(label)
    if i < 0:
        return None
    rest = text[i + len(label):].strip()
    value = rest.split("Contact Number:")[0].split("Location:")[0]
    # the card fragment can carry trailing markup scraps past the value
    value = value.split("<")[0]
    value = re.sub(r"\s+", " ", value).strip(" |/<> ")
    return value or None
