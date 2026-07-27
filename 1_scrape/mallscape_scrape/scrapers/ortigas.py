"""Ortigas Land malls scraper (Greenhills, Estancia, Tiendesitas, The Strip).

``ortigasmalls.com`` is a Laravel + Inertia app: the whole page state, including
the full store directory, is embedded in the ``data-page`` attribute as JSON.
No separate API call is made, so one request per mall yields everything:

    props.selectedMall.floors[].stores[]  ->  {name, location, type, contact_number}

The mall is selected with ``?selectedMall=<id>`` (ids come from
``props.malls``). Floor labels live on the floor object (e.g. "GH Mall, LGF").

Greenhills' directory covers the whole Greenhills complex - GH Mall,
Shoppesville, Bridgeway, VMall, Promenade, Connecticut Arcade and so on - which
is why its floor list is far longer than a single building's.

Many store slots are map-coordinate placeholders with every field null; those
are skipped.
"""

from __future__ import annotations

import html as htmllib
import json
import re

from mallscape_core.models import Mall, Store
from mallscape_scrape.scrapers.base import MallChainScraper

BASE = "https://ortigasmalls.com/mall-directory"
_DATA_PAGE = re.compile(r'data-page="([^"]+)"')

REGION = "metro-manila"
ADDRESSES = {
    "greenhills": "Ortigas Avenue, Greenhills, San Juan City",
    "estancia": "Capitol Commons, Meralco Ave., Pasig City",
    "tiendesitas": "Frontera Verde, Ortigas Ave. cor. C-5, Pasig City",
    "the-strip": "Capitol Commons, Pasig City",
}


class OrtigasScraper(MallChainScraper):
    chain = "ortigas"

    def _page_props(self, params: dict | None = None) -> dict:
        html = self.fetcher.get_text(BASE, params)
        match = _DATA_PAGE.search(html)
        if not match:
            raise ValueError("no data-page payload - the site may have changed framework")
        return json.loads(htmllib.unescape(match.group(1)))["props"]

    def discover_malls(self) -> list[Mall]:
        props = self._page_props()
        malls = []
        for entry in props.get("malls", []):
            slug = re.sub(r"[^a-z0-9]+", "-", entry["name"].lower()).strip("-")
            malls.append(
                Mall(
                    chain=self.chain,
                    mall_id=slug,
                    mall_name=entry["name"],
                    region=REGION,
                    address=ADDRESSES.get(slug),
                    mall_code=str(entry["id"]),
                    source_url=f"{BASE}?selectedMall={entry['id']}",
                    extra={"id": entry["id"]},
                )
            )
        if not malls:
            self.warn("no malls in props.malls")
        return malls

    def _category_names(self, props: dict) -> dict[str, str]:
        """Map ``store.type`` ids to their labels.

        ``type`` is a foreign key, not a category name: the directory ships
        ``1``, ``4``, ``7``, ``9`` and the lookup sits beside it in
        ``props.categories``. Storing the id was silently discarding a real
        category for 1,075 listings, because everything downstream saw an
        integer where it expected a word.
        """
        names = {}
        for entry in props.get("categories") or []:
            key, label = _text(entry.get("id")), _text(entry.get("name"))
            if key and label:
                names[key] = label.lower()
        if not names:
            self.warn("props.categories is empty - category ids cannot be resolved")
        return names

    def scrape_mall(self, mall: Mall) -> list[Store]:
        props = self._page_props({"selectedMall": mall.extra["id"]})
        categories = self._category_names(props)
        selected = props.get("selectedMall") or {}
        if str(selected.get("id")) != str(mall.extra["id"]):
            self.warn(
                f"{mall.mall_id}: asked for id {mall.extra['id']} but got "
                f"{selected.get('slug')} - selection param may have changed"
            )
            return []

        stores: list[Store] = []
        for floor in selected.get("floors") or []:
            floor_name = (floor.get("name") or "").strip() or None
            for record in floor.get("stores") or []:
                # several fields come back as ints (category id, unit number)
                name = _text(record.get("name"))
                if not name:
                    # map-coordinate placeholder slot, not a tenant
                    continue
                type_id = _text(record.get("type"))
                if type_id and type_id not in categories:
                    self.warn(
                        f"{mall.mall_id}: category id {type_id!r} is not in "
                        f"props.categories - the lookup changed"
                    )
                stores.append(
                    Store(
                        chain=self.chain,
                        mall_id=mall.mall_id,
                        store_name_raw=name,
                        category=categories.get(type_id) or None,
                        floor=_text(record.get("location")) or floor_name,
                        phone=_text(record.get("contact_number")) or None,
                        source="ortigas-inertia",
                    )
                )
        return stores


def _text(value) -> str:
    """Several Inertia fields arrive as ints (category id, unit number)."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()
