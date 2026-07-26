"""Gaisano Malls / GMall scraper (DSG Sons Group, Davao).

``gaisanomalls.com/mall-directory/`` renders the entire chain-wide tenant table
server-side and then hands it to a client-side DataTable for paging. That means
one plain HTTP request returns every row — no browser, no pagination:

    <tr><td>GMall of Davao</td><td>Euro Baker Bakeshop</td>
        <td>Lower Ground Floor</td><td>0</td><td>Food</td></tr>

Columns are branch, tenant, floor, an unused numeric column, and category. The
branch column is what splits the rows across malls, so ``discover_malls``
derives the mall list from the table itself rather than a hardcoded roster —
a new GMall branch appears automatically.
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from mallscape_core.models import Mall, Store
from mallscape_scrape.scrapers.base import MallChainScraper

DIRECTORY = "https://gaisanomalls.com/mall-directory/"

# DSG Sons operates in Mindanao plus one Cebu mall
REGION_BY_KEYWORD = (
    ("cebu", "visayas"),
    ("davao", "mindanao"),
    ("toril", "mindanao"),
    ("digos", "mindanao"),
    ("tagum", "mindanao"),
    ("gensan", "mindanao"),
    ("general santos", "mindanao"),
)


def _region(name: str) -> str | None:
    low = name.lower()
    for keyword, region in REGION_BY_KEYWORD:
        if keyword in low:
            return region
    return None


class GmallScraper(MallChainScraper):
    chain = "gmall"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self._rows_by_mall: dict[str, list[tuple[str, str, str]]] = {}
        self._filter_branches: list[str] = []

    def _load_table(self) -> None:
        if self._rows_by_mall:
            return
        html = self.fetcher.get_text(DIRECTORY)
        self._filter_branches = sorted(
            set(re.findall(r'tenant-filter-branch[^>]*value="([^"]+)"', html))
        )
        tree = HTMLParser(html)
        for row in tree.css("tr"):
            cells = [re.sub(r"\s+", " ", c.text(strip=True)) for c in row.css("td")]
            # branch, tenant, floor, [unused numeric], category — the numeric
            # column renders empty, so rows arrive with 4 or 5 cells
            if len(cells) < 4:
                continue
            branch, tenant, floor = cells[0], cells[1], cells[2]
            category = cells[-1]
            if not branch or not tenant:
                continue
            self._rows_by_mall.setdefault(branch, []).append((tenant, floor, category))
        if not self._rows_by_mall:
            self.warn("no tenant rows parsed from the mall directory table")

    def discover_malls(self) -> list[Mall]:
        self._load_table()
        # The branch radio filter is the authoritative roster. Deriving malls
        # from the table's rows alone dropped Cebu and GenSan entirely (they
        # have zero tenant rows), hiding a 2-of-6 mall undercount.
        branches = set(self._filter_branches) | set(self._rows_by_mall)
        missing = sorted(b for b in self._filter_branches if b not in self._rows_by_mall)
        if missing:
            self.warn(
                f"branch(es) offered by the site filter with no tenant rows: "
                f"{missing} — included as zero-store malls"
            )
        malls = []
        for branch in sorted(branches):
            slug = re.sub(r"[^a-z0-9]+", "-", branch.lower()).strip("-")
            region = _region(branch)
            if region is None:
                self.warn(f"could not derive region for branch {branch!r}")
            malls.append(
                Mall(
                    chain=self.chain,
                    mall_id=slug,
                    mall_name=branch,
                    region=region,
                    source_url=DIRECTORY,
                    extra={"branch": branch},
                )
            )
        return malls

    def scrape_mall(self, mall: Mall) -> list[Store]:
        self._load_table()
        return [
            Store(
                chain=self.chain,
                mall_id=mall.mall_id,
                store_name_raw=tenant,
                category=category.lower() or None,
                floor=floor or None,
                source="gmall-html",
            )
            for tenant, floor, category in self._rows_by_mall.get(mall.extra["branch"], [])
        ]
