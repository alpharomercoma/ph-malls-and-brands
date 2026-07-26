"""Fisher Mall scraper (Quezon Avenue and Malabon branches).

The store list pages render one floor at a time; each floor tab calls
``loadlevel(<Level>, <branch>)``, which fetches:

    content/fishermall/<branch>/loadlevel.php?level=<Level Name>

The response is an HTML fragment of tenant tiles. The tenant name sits in the
popover markup as ``<b class='txt_popover'>Name</b>``; the same popover repeats
the floor. Floor names are branch-specific (Malabon has mezzanines, Quezon
Avenue has a Parkway and Upper Basement), so they are listed per branch here
and re-verified on each run against the page's own loadlevel() calls.
"""

from __future__ import annotations

import html as htmllib
import re

from mallscape_core.models import Mall, Store
from mallscape_scrape.scrapers.base import MallChainScraper

BASE = "https://fishermall.com.ph/"

MALLS = {
    "quezonave": {
        "name": "Fisher Mall Quezon Avenue",
        "page": "storelistqave",
        "region": "metro-manila",
        "address": "Quezon Avenue corner Roosevelt Avenue, Quezon City",
        "levels": [
            "Upper Basement", "Lower Ground", "Upper Ground", "Second Floor",
            "Third Floor", "Fourth Floor", "Roof Deck", "Food Hall", "Parkway",
        ],
    },
    "malabon": {
        "name": "Fisher Mall Malabon",
        "page": "storelistmlb",
        "region": "metro-manila",
        "address": "C-4 Road corner Dagat-dagatan Avenue, Brgy. Longos, Malabon",
        "levels": [
            "First Floor", "Second Floor", "Second Floor Mezzanine", "Third Floor",
            "Fourth Floor", "Fourth Floor Mezzanine", "Roof Deck", "Food Hall",
        ],
    },
}

_LOADLEVEL = re.compile(r"loadlevel\('([^']+)','([^']+)'\)")
_NAME = re.compile(r"txt_popover'>\s*([^<]+?)\s*</b>", re.I)


class FishermallScraper(MallChainScraper):
    chain = "fishermall"

    def discover_malls(self) -> list[Mall]:
        malls = []
        for slug, cfg in MALLS.items():
            # re-read the floor tabs live so a new floor is never missed silently
            try:
                page = self.fetcher.get_text(BASE + cfg["page"])
                live = sorted({lvl for lvl, br in _LOADLEVEL.findall(page) if br == slug})
            except Exception as exc:
                self.warn(f"{slug}: could not read floor tabs ({type(exc).__name__})")
                live = []
            if live and set(live) != set(cfg["levels"]):
                added = sorted(set(live) - set(cfg["levels"]))
                removed = sorted(set(cfg["levels"]) - set(live))
                self.warn(f"{slug}: floor list changed (added={added} removed={removed})")
            malls.append(
                Mall(
                    chain=self.chain,
                    mall_id=slug,
                    mall_name=cfg["name"],
                    region=cfg["region"],
                    address=cfg["address"],
                    source_url=BASE + cfg["page"],
                    extra={"levels": live or cfg["levels"]},
                )
            )
        return malls

    def scrape_mall(self, mall: Mall) -> list[Store]:
        stores: list[Store] = []
        for level in mall.extra["levels"]:
            try:
                fragment = self.fetcher.get_text(
                    f"{BASE}content/fishermall/{mall.mall_id}/loadlevel.php",
                    {"level": level},
                )
            except Exception as exc:
                self.warn(f"{mall.mall_id}/{level}: {type(exc).__name__}")
                continue
            for raw in _NAME.findall(fragment):
                name = re.sub(r"\s+", " ", htmllib.unescape(raw)).strip()
                if not name:
                    continue
                stores.append(
                    Store(
                        chain=self.chain,
                        mall_id=mall.mall_id,
                        store_name_raw=name,
                        floor=level,
                        source="fishermall-html",
                    )
                )
        return stores
