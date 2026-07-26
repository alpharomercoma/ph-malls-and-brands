"""Chain-scraper interface. Adding a new mall chain = one new subclass."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from mallscape_core.models import Mall, Store
from mallscape_scrape.fetch import Fetcher


class MallChainScraper(ABC):
    chain: str  # short id, e.g. "sm"
    # extra HTTP headers this chain's endpoints require (e.g. CORS Origin)
    extra_headers: ClassVar[dict[str, str]] = {}

    def __init__(self, fetcher: Fetcher):
        self.fetcher = fetcher
        self.warnings: list[str] = []

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)
        print(f"  [warn:{self.chain}] {msg}")

    @abstractmethod
    def discover_malls(self) -> list[Mall]: ...

    @abstractmethod
    def scrape_mall(self, mall: Mall) -> list[Store]: ...

    def scrape_all(self) -> tuple[list[Mall], list[Store]]:
        malls = self.discover_malls()
        print(f"[{self.chain}] discovered {len(malls)} malls")
        stores: list[Store] = []
        for i, mall in enumerate(malls, 1):
            try:
                mall_stores = self.scrape_mall(mall)
            except Exception as exc:  # one mall must not kill the whole run
                self.warn(f"FAILED {mall.mall_id}: {type(exc).__name__}: {exc}")
                continue
            if not mall_stores:
                self.warn(f"0 stores for {mall.mall_id}")
            stores.extend(mall_stores)
            print(f"[{self.chain}] {i}/{len(malls)} {mall.mall_id}: {len(mall_stores)} stores")
        return malls, stores
